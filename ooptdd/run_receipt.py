"""ooptdd v2 harness — run a receipt and append a chained record.

  uv run python -m ooptdd.run_receipt receipts/receipt_cosine_floor.py \
      --source learned_v3_additive.py --source weight_field.py \
      --mutation-target learned_v3_additive.py \
      --anchor-tree LakatosTree_HSWM_20260719 --anchor-node d1-ooptdd-floor-scope-correction

The harness:
  1. extracts the module-level LOCK dict from the receipt via AST
     (ast.literal_eval — the receipt module is never imported),
  2. verifies LOCK↔check binding (v2.2): if the receipt declares LOCK_CHECKS
     {lock_key: result_variable}, every LOCK key must be mapped, every mapped
     variable must exist, and every mapped variable must gate the final verdict,
  3. hashes the receipt file and every --source file,
  4. executes the receipt in a subprocess (real execution gate),
  5. appends a chained record (fail-closed) to receipts/receipt_log.jsonl,
  6. optionally anchors the chain head hash to LakatoTree (--anchor-tree/node;
     token from LAKATOS_API_TOKEN env),
  7. exits with the receipt's own exit code, 2 on chain/binding failure.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import urllib.request

from ooptdd.receipt_log import append, canonical, file_sha, load, sha256_hex, verify

DEFAULT_LOG = os.path.join("receipts", "receipt_log.jsonl")
DEFAULT_LAKATOS_URL = "http://127.0.0.1:55170"


def _extract_dict_assign(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
    return None


def extract_lock(receipt_path: str) -> dict:
    """Statically extract the module-level LOCK dict (no import side effects)."""
    tree = ast.parse(open(receipt_path, "r", encoding="utf-8").read(), filename=receipt_path)
    lock = _extract_dict_assign(tree, "LOCK")
    if lock is None:
        raise ValueError(f"{receipt_path}: no module-level LOCK dict found (v2 requires an explicit locked trace)")
    return lock


def verify_lock_binding(receipt_path: str, lock: dict) -> tuple[str, list[str]]:
    """v2.2 — machine-check that LOCK prose is bound to verdict-gating code.

    A receipt may declare LOCK_CHECKS = {lock_key: result_variable | [variables]}.
    If present:
      - every LOCK key must be mapped, except keys starting with "not_" which are
        documented non-claims (nothing is asserted, so nothing needs a check),
      - every mapped variable must be assigned somewhere in the receipt,
      - every mapped variable must appear in the boolean expression that decides
        the final verdict (the `ok = ...` assignment) — a check that cannot
        fail the run is decoration.
    Returns ("verified" | "absent" | "broken", problems).
    """
    tree = ast.parse(open(receipt_path, "r", encoding="utf-8").read(), filename=receipt_path)
    checks = _extract_dict_assign(tree, "LOCK_CHECKS")
    if checks is None:
        return "absent", ["LOCK_CHECKS not declared — lock prose is not machine-bound (transitional warning)"]
    problems: list[str] = []
    for key in lock:
        if key.startswith("not_"):
            continue
        if key not in checks:
            problems.append(f"LOCK key '{key}' has no check mapping (prose without code)")
    assigned_names = {
        t.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
        for t in node.targets if isinstance(t, ast.Name)
    }
    gating_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ok" for t in node.targets):
            gating_names |= {n.id for n in ast.walk(node.value) if isinstance(n, ast.Name)}
    for key, var in checks.items():
        vars_ = [var] if isinstance(var, str) else list(var)
        for v in vars_:
            if v not in assigned_names:
                problems.append(f"check variable '{v}' (for '{key}') is never assigned")
            elif v not in gating_names:
                problems.append(f"check variable '{v}' (for '{key}') does not gate the final verdict")
    return ("broken" if problems else "verified"), problems


def previous_anchor(log_path: str, receipt_id: str) -> dict | None:
    """The last anchor this chain recorded for `receipt_id`, from the chain itself.

    v3.1 chains every anchoring attempt as kind="anchor" (run_receipt below), so
    the local file remembers what it has already published without asking the
    tree. That memory is what lets a new anchor carry a link to its predecessor.
    """
    prev = None
    for r in load(log_path):
        if r.get("kind") == "anchor" and r.get("receipt_id") == receipt_id \
                and r.get("verdict") == "VALID":
            prev = r
    return prev


def anchor_chain_head(tree_name: str, node_tag: str, rec: dict, log_path: str,
                      base_url: str = DEFAULT_LAKATOS_URL) -> tuple[bool, str]:
    """Post the chain head as a LakatoTree research event (tamper-evidence anchor)."""
    token = os.environ.get("LAKATOS_API_TOKEN", "")
    # v3.1 — carry a link to the anchor this one extends. Anchors used to be
    # independent snapshots, so a rewriter could edit an old record, rehash the
    # tail and publish a fresh head: each anchor was individually consistent with
    # the file at the moment it was posted, and nothing said they had to form a
    # chain. prev_anchor_seq/hash make each anchor a claim about its predecessor,
    # so the sequence can be walked (fire_drill anchor-check).
    #
    # Honest scope: this is a link, not a proof. A transparency-log witness gets
    # an O(log N) Merkle consistency proof and verifies it BEFORE co-signing, and
    # a quorum of independent witnesses is what actually defeats a split view.
    # Here the log states its own predecessor and the checker compares. It raises
    # the cost of a rewrite (every anchor must be re-posted coherently) rather
    # than making one impossible.
    prev = previous_anchor(log_path, rec["receipt_id"])
    payload = {
        "event_id": f"ooptdd-chain-head-{rec['receipt_id']}-seq{rec['seq']}",
        "realm": "agent",
        "actor": "ooptdd-harness",
        "action": "ooptdd_chain_head_anchor",
        "evidence_refs": [f"{log_path}#seq{rec['seq']}", f"receipt_sha:{rec['receipt_sha'][:12]}"],
        "payload": {
            "receipt_id": rec["receipt_id"],
            "seq": str(rec["seq"]),
            "hash": rec["hash"],
            "verdict": rec["verdict"],
            "lock_sha": rec["lock_sha"],
            "mutation_score": json.dumps(rec.get("mutation_score")),
            # "" when this is the first anchor — an absent link and a broken one
            # must not look alike.
            "prev_anchor_seq": str(prev.get("target_seq", "")) if prev else "",
            "prev_anchor_hash": str(prev.get("target_hash", "")) if prev else "",
        },
    }
    req = urllib.request.Request(
        f"{base_url}/api/tree/{tree_name}/node/{node_tag}/event",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return True, r.read().decode()[:150]
    except Exception as e:  # anchor is additive evidence; never mask the receipt verdict
        return False, str(e)


def parse_measured(stdout: str) -> tuple[dict | None, bool]:
    """v2.10 (G3): extract the receipt's LAST well-formed `MEASURED {json}` line.

    Returns (payload, saw_line). payload is None when no line parsed — the
    record then carries measured=None (honest absence), never a guessed value.
    """
    payload, saw = None, False
    for line in stdout.splitlines():
        if line.startswith("MEASURED "):
            saw = True
            try:
                payload = json.loads(line[len("MEASURED "):])
            except json.JSONDecodeError:
                pass  # keep the last GOOD parse; a broken trailing line degrades to the previous one
    return payload, saw


def main() -> int:
    ap = argparse.ArgumentParser(description="run an ooptdd receipt and chain the result")
    ap.add_argument("receipt", help="path to the receipt .py")
    ap.add_argument("--source", action="append", default=[], help="source file to bind (repeatable)")
    ap.add_argument("--log", default=DEFAULT_LOG, help="chain log path (default receipts/receipt_log.jsonl)")
    ap.add_argument("--kind", default="receipt", choices=["receipt", "audit"])
    ap.add_argument("--auditor-id", default=None, help="required when --kind audit")
    ap.add_argument("--target-hash", default=None, help="audited receipt record hash (audit kind)")
    ap.add_argument("--author", default=os.environ.get("OOPTDD_AUTHOR"),
                    help="receipt author identity for R1 no-self-audit (default: OOPTDD_AUTHOR env)")
    ap.add_argument("--mutation-target", default=None,
                    help="module to mutate (path) for an automated mutation score (v2.1)")
    ap.add_argument("--max-mutants", type=int, default=12, help="cap on mutants executed")
    ap.add_argument("--anchor-tree", default=None, help="LakatoTree tree name for chain-head anchoring")
    ap.add_argument("--anchor-node", default=None, help="LakatoTree node tag for chain-head anchoring")
    ap.add_argument("--anchor-url", default=DEFAULT_LAKATOS_URL, help="LakatoTree base URL")
    ap.add_argument("--require-anchor", action="store_true",
                    default=os.environ.get("OOPTDD_REQUIRE_ANCHOR") == "1",
                    help="a failed anchor post fails the run (exit 3). Default from "
                         "OOPTDD_REQUIRE_ANCHOR=1. Without it the anchor is decoration: "
                         "v2 printed 'receipt verdict unaffected' and exited on the receipt's "
                         "own code, so a green run proved nothing outside this process.")
    args = ap.parse_args()

    receipt_id = os.path.splitext(os.path.basename(args.receipt))[0]
    lock = extract_lock(args.receipt)
    binding, binding_problems = verify_lock_binding(args.receipt, lock)
    # v3 XLOCKS: migrated claims bind prose to predicate SOURCE (docstring ==
    # prose, drift = broken). Static extraction only — the receipt is never
    # imported by the harness.
    from ooptdd.xlocks import extract_xlocks, parse_xlocks_result, verify_xlock_prose
    xlocks_meta = extract_xlocks(args.receipt)
    if xlocks_meta:
        prose_problems = verify_xlock_prose(lock, xlocks_meta)
        if prose_problems:
            binding, binding_problems = "broken", binding_problems + prose_problems
        else:
            print(f"xlocks: {len(xlocks_meta)} predicate lock(s) — prose bound to predicate source")
    print(f"lock-binding: {binding}" + (f" — {binding_problems}" if binding_problems else ""))
    if binding == "broken":
        return 2

    record = {
        "kind": args.kind,
        "receipt_id": receipt_id,
        "receipt_sha": file_sha(args.receipt),
        "source_shas": {s: file_sha(s) for s in args.source},
        "lock_sha": sha256_hex(canonical(lock)),
        "lock_binding": binding,
        "status": "self-valid",
        "mutation_score": None,
        "measured": None,
        "xlocks": None,
        "attestation": None,
    }
    if args.author:
        record["author_id"] = args.author  # R1 (v2.6): no-self-audit is only enforceable with a recorded author
    if args.kind == "audit":
        if not args.auditor_id or not args.target_hash:
            print("audit records require --auditor-id and --target-hash", file=sys.stderr)
            return 2
        record["auditor_id"] = args.auditor_id
        record["target_hash"] = args.target_hash

    # v2.10: capture stdout to harvest the MEASURED line (G3), then echo it
    # back so the operator's readback is unchanged.
    proc = subprocess.run([sys.executable, args.receipt], capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    record["exit_code"] = proc.returncode
    record["verdict"] = "VALID" if proc.returncode == 0 else ("INVALID" if proc.returncode == 1 else "ERROR")
    measured, saw_measured = parse_measured(proc.stdout)
    record["measured"] = measured
    if measured is not None:
        print(f"measured: {len(measured)} metrics captured into the chain record")
    elif saw_measured:
        print("measured: WARNING — MEASURED line(s) present but none parsed; recorded as absent")
    else:
        print("measured: absent (receipt emits no MEASURED line; flagged, not trusted)")

    if xlocks_meta:
        xr = parse_xlocks_result(proc.stdout) or {}
        merged = {}
        for key, meta in xlocks_meta.items():
            runtime = xr.get(key)
            entry = {"predicate_sha": meta["predicate_sha"], "strategy": meta["strategy"]}
            if runtime is None:
                entry["engine"] = "missing"
                entry["ok"] = False  # declared but not executed: fail-closed, not silently trusted
            else:
                entry.update(runtime)  # receipt-emitted evidence (incl. signed-oracle riders)
                entry.setdefault("ok", False)
                entry.setdefault("engine", "unknown")
            merged[key] = entry
        record["xlocks"] = merged
        bad = {k: v for k, v in merged.items() if not v.get("ok") and proc.returncode == 0}
        print(f"xlocks chained: " + ", ".join(
            f"{k}[{v.get('engine')} ok={v.get('ok')}]" for k, v in merged.items()))
        if bad:
            print(f"xlocks WARNING: receipt exited 0 but predicate lock(s) not green: {list(bad)}", file=sys.stderr)

    if args.mutation_target:
        from ooptdd.mutate import mutation_score
        repo_root = os.path.dirname(os.path.abspath(args.receipt)) or "."
        # receipts live in receipts/; the repo root is its parent when applicable
        if os.path.basename(repo_root) == "receipts":
            repo_root = os.path.dirname(repo_root)
        ms = mutation_score(args.mutation_target, os.path.abspath(args.receipt),
                            repo_root=repo_root, max_mutants=args.max_mutants)
        # v2.7: chain the FULL picture, not just killed/total — a raw 8/12 reads
        # weak unless the record also carries the allowlist-adjusted denominator
        # (documented equivalents) and the open-gap count (honest holes).
        record["mutation_score"] = {
            "killed": ms["killed"],
            "total": ms["total"],
            "effective_total": ms["effective_total"],
            "equivalents": len(ms["equivalents"]),
            "open_gaps": len(ms["survivors"]),
            "survivors": ms["survivors"],
            "errors": ms["errors"],
            # a sampled score is meaningless without the pool it sampled and the
            # operator table that built the pool; both are chained so two scores
            # can be told apart instead of silently compared
            "sites_available": ms["sites_available"],
            "sample_seed": ms["sample_seed"],
            "operator_set": ms["operator_set"],
        }
        print(f"\nMUTATION SCORE: {ms['killed']}/{ms['total']} killed"
              f" [sampled from {ms['sites_available']} sites,"
              f" seed={ms['sample_seed']}, ops={ms['operator_set']}]"
              f" (effective {ms['killed']}/{ms['effective_total']} after {len(ms['equivalents'])} documented equivalents)"
              + (f" | open gaps: {ms['survivors']}" if ms["survivors"] else "")
              + (f" | errors: {ms['errors']}" if ms["errors"] else ""))

    try:
        rec = append(args.log, record)
    except ValueError as e:
        print(f"chain append refused: {e}", file=sys.stderr)
        return 2
    print(f"\nCHAINED: seq={rec['seq']} verdict={rec['verdict']} hash={rec['hash'][:12]}… log={args.log}")
    ok, errors = verify(args.log)
    print(f"chain verify after append: {'OK' if ok else 'BROKEN: ' + json.dumps(errors)}")

    if args.anchor_tree or args.anchor_node:
        if not (args.anchor_tree and args.anchor_node):
            print("anchoring requires both --anchor-tree and --anchor-node", file=sys.stderr)
            return 2
        anchored, detail = anchor_chain_head(args.anchor_tree, args.anchor_node, rec,
                                             args.log, base_url=args.anchor_url)
        print(f"anchor: {'OK ' + detail if anchored else 'FAILED: ' + detail}")
        # v3.0 — chain the anchoring attempt as its own record, success or not.
        # The anchored payload lives on another machine; the chain deserves a
        # local, hash-linked statement of whether that hand-off happened, so
        # "was this ever anchored?" is answerable from the chain instead of
        # from someone's memory of a console line.
        try:
            append(args.log, {
                "kind": "anchor",
                "receipt_id": receipt_id,
                "receipt_sha": rec["receipt_sha"],
                "source_shas": {},
                "lock_sha": rec["lock_sha"],
                "lock_binding": rec.get("lock_binding", "absent"),
                "verdict": "VALID" if anchored else "INVALID",
                "exit_code": 0 if anchored else 1,
                "status": "anchored" if anchored else "anchor-failed",
                "target_hash": rec["hash"],
                "target_seq": rec["seq"],
                "anchor_tree": args.anchor_tree,
                "anchor_node": args.anchor_node,
                "anchor_url": args.anchor_url,
                "anchor_detail": detail[:300],
                "mutation_score": None,
                "attestation": None,
            })
        except ValueError as e:
            print(f"anchor record not chained: {e}", file=sys.stderr)
        if not anchored and args.require_anchor:
            print("anchor REQUIRED and not established — the run is not green outside this "
                  "process (exit 3)", file=sys.stderr)
            return 3
        if not anchored:
            print("NOTE: anchor failed and --require-anchor was not set; this receipt rests on "
                  "local evidence alone. ooptdd.gate will not call it DONE.", file=sys.stderr)
    elif args.require_anchor:
        print("--require-anchor given without --anchor-tree/--anchor-node", file=sys.stderr)
        return 2
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
