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

from ooptdd.receipt_log import append, canonical, file_sha, sha256_hex, verify

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


def anchor_chain_head(tree_name: str, node_tag: str, rec: dict, log_path: str,
                      base_url: str = DEFAULT_LAKATOS_URL) -> tuple[bool, str]:
    """Post the chain head as a LakatoTree research event (tamper-evidence anchor)."""
    token = os.environ.get("LAKATOS_API_TOKEN", "")
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
    args = ap.parse_args()

    receipt_id = os.path.splitext(os.path.basename(args.receipt))[0]
    lock = extract_lock(args.receipt)
    binding, binding_problems = verify_lock_binding(args.receipt, lock)
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

    proc = subprocess.run([sys.executable, args.receipt])
    record["exit_code"] = proc.returncode
    record["verdict"] = "VALID" if proc.returncode == 0 else ("INVALID" if proc.returncode == 1 else "ERROR")

    if args.mutation_target:
        from ooptdd.mutate import mutation_score
        repo_root = os.path.dirname(os.path.abspath(args.receipt)) or "."
        # receipts live in receipts/; the repo root is its parent when applicable
        if os.path.basename(repo_root) == "receipts":
            repo_root = os.path.dirname(repo_root)
        ms = mutation_score(args.mutation_target, os.path.abspath(args.receipt),
                            repo_root=repo_root, max_mutants=args.max_mutants)
        record["mutation_score"] = {"killed": ms["killed"], "total": ms["total"]}
        print(f"\nMUTATION SCORE: {ms['killed']}/{ms['total']} killed"
              + (f" | survivors: {ms['survivors']}" if ms["survivors"] else "")
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
        print(f"anchor: {'OK ' + detail if anchored else 'FAILED (receipt verdict unaffected): ' + detail}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
