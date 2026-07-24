"""ooptdd v2 harness — run a receipt and append a chained record.

  uv run python -m ooptdd.run_receipt receipts/receipt_cosine_floor.py \
      --source learned_v3_additive.py --source weight_field.py

The harness:
  1. extracts the module-level LOCK dict from the receipt via AST
     (ast.literal_eval — the receipt module is never imported),
  2. hashes the receipt file and every --source file,
  3. executes the receipt in a subprocess (real execution gate),
  4. appends a chained record (fail-closed) to receipts/receipt_log.jsonl,
  5. exits with the receipt's own exit code, or 2 if the chain append failed.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys

from ooptdd.receipt_log import append, canonical, file_sha, sha256_hex, verify

DEFAULT_LOG = os.path.join("receipts", "receipt_log.jsonl")


def extract_lock(receipt_path: str) -> dict:
    """Statically extract the module-level LOCK dict (no import side effects)."""
    tree = ast.parse(open(receipt_path, "r", encoding="utf-8").read(), filename=receipt_path)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "LOCK":
                    return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "LOCK":
            return ast.literal_eval(node.value)
    raise ValueError(f"{receipt_path}: no module-level LOCK dict found (v2 requires an explicit locked trace)")


def main() -> int:
    ap = argparse.ArgumentParser(description="run an ooptdd receipt and chain the result")
    ap.add_argument("receipt", help="path to the receipt .py")
    ap.add_argument("--source", action="append", default=[], help="source file to bind (repeatable)")
    ap.add_argument("--log", default=DEFAULT_LOG, help="chain log path (default receipts/receipt_log.jsonl)")
    ap.add_argument("--kind", default="receipt", choices=["receipt", "audit"])
    ap.add_argument("--auditor-id", default=None, help="required when --kind audit")
    ap.add_argument("--target-hash", default=None, help="audited receipt record hash (audit kind)")
    ap.add_argument("--mutation-target", default=None,
                    help="module to mutate (path) for an automated mutation score (v2.1)")
    ap.add_argument("--max-mutants", type=int, default=12, help="cap on mutants executed")
    args = ap.parse_args()

    receipt_id = os.path.splitext(os.path.basename(args.receipt))[0]
    lock = extract_lock(args.receipt)
    record = {
        "kind": args.kind,
        "receipt_id": receipt_id,
        "receipt_sha": file_sha(args.receipt),
        "source_shas": {s: file_sha(s) for s in args.source},
        "lock_sha": sha256_hex(canonical(lock)),
        "status": "self-valid",
        "mutation_score": None,
        "attestation": None,
    }
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
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
