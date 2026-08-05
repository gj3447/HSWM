"""ooptdd v2.3 — test harvester: wrap existing pytest files as chain records.

The ceremony-free coverage path: instead of writing new receipts by hand,
harvest the existing test suite. Each test file is executed as-is; its module
docstring becomes a HARVESTED lock (weaker than a hand-written LOCK — recorded
honestly as lock_binding="harvested", never "verified").

Anti-vacuity rules (a harvest that proves nothing must not look green):
  - pytest exit 0 AND >=1 test passed           -> VALID
  - pytest exit != 0                            -> INVALID
  - collection error / no tests ran / timeout   -> ERROR (not VALID)

Usage:
  .venv/bin/python -m ooptdd.harvest tests/                       # harvest all
  .venv/bin/python -m ooptdd.harvest tests/test_additive_floor.py # one file
  .venv/bin/python -m ooptdd.harvest tests/ --exclude judge --exclude bge_m3
  .venv/bin/python -m ooptdd.harvest tests/test_x.py \
      --mutation-target learned_v3_additive.py                  # vacuity scan
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys

from ooptdd.receipt_log import append, canonical, file_sha, sha256_hex

DEFAULT_LOG = os.path.join("receipts", "receipt_log.jsonl")

_SUMMARY = re.compile(r"(\d+)\s+(passed|failed|skipped|error|warnings)")


def harvested_lock(test_path: str) -> dict:
    """Module docstring becomes the harvested lock; absence is recorded, not hidden."""
    try:
        tree = ast.parse(open(test_path, "r", encoding="utf-8").read(), filename=test_path)
        doc = ast.get_docstring(tree)
    except SyntaxError:
        doc = None
    first = (doc or "").strip().split("\n\n")[0].strip()
    return {"harvested_claim": first or "(no module docstring — file-name lock only)",
            "harvested_from": os.path.basename(test_path)}


def run_pytest(test_path: str, timeout: int) -> dict:
    """Execute one test file; return counts + verdict with anti-vacuity rules."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-q", "-p", "no:cacheprovider"],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"verdict": "ERROR", "reason": f"timeout>{timeout}s",
                "passed": 0, "failed": 0, "skipped": 0}
    counts = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
    for n, kind in _SUMMARY.findall(proc.stdout):
        if kind in counts:
            counts[kind] = int(n)
    tail = "\n".join(proc.stdout.splitlines()[-3:])
    if proc.returncode == 5 or (counts["passed"] == 0 and counts["failed"] == 0):
        return {"verdict": "ERROR", "reason": "no tests collected (vacuous harvest refused)",
                "tail": tail, **counts}
    return {"verdict": "VALID" if proc.returncode == 0 else "INVALID",
            "reason": "" if proc.returncode == 0 else tail, **counts}


def harvest_file(test_path: str, log_path: str, timeout: int) -> dict:
    lock = harvested_lock(test_path)
    res = run_pytest(test_path, timeout)
    record = {
        "kind": "harvest",
        "receipt_id": os.path.splitext(os.path.basename(test_path))[0],
        "receipt_sha": file_sha(test_path),
        "source_shas": {},
        "lock_sha": sha256_hex(canonical(lock)),
        "lock_binding": "harvested",
        "verdict": res["verdict"],
        "exit_code": 0 if res["verdict"] == "VALID" else 1,
        "tests": {"passed": res["passed"], "failed": res["failed"], "skipped": res["skipped"]},
        "status": "self-valid",
        "mutation_score": None,
        "attestation": None,
    }
    if res["verdict"] == "ERROR":
        record["error_reason"] = res.get("reason", "")[:300]
    return append(log_path, record)


def main() -> int:
    ap = argparse.ArgumentParser(description="harvest existing pytest files into the ooptdd chain")
    ap.add_argument("paths", nargs="+", help="test files or directories")
    ap.add_argument("--exclude", action="append", default=[], help="substring filter (repeatable)")
    ap.add_argument("--timeout", type=int, default=120, help="per-file pytest timeout (s)")
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--mutation-target", default=None,
                    help="after harvesting, run a vacuity scan of each VALID file against this module")
    ap.add_argument("--max-mutants", type=int, default=8)
    args = ap.parse_args()

    files: list[str] = []
    for p in args.paths:
        if os.path.isdir(p):
            files.extend(sorted(os.path.join(p, f) for f in os.listdir(p)
                                if f.startswith("test_") and f.endswith(".py")))
        else:
            files.append(p)
    files = [f for f in files if not any(x in f for x in args.exclude)]
    if not files:
        print("no test files matched", file=sys.stderr)
        return 2

    n_valid = n_invalid = n_error = 0
    for f in files:
        rec = harvest_file(f, args.log, args.timeout)
        t = rec["tests"]
        line = (f"seq={rec['seq']:>3} {rec['verdict']:<7} {rec['receipt_id']:<42} "
                f"passed={t['passed']} failed={t['failed']} skipped={t['skipped']}")
        if rec["verdict"] == "ERROR":
            line += f" | {rec.get('error_reason', '')[:80]}"
            n_error += 1
        elif rec["verdict"] == "VALID":
            n_valid += 1
        else:
            n_invalid += 1
        print(line)

        if args.mutation_target and rec["verdict"] == "VALID":
            from ooptdd.mutate import mutation_score
            ms = mutation_score(args.mutation_target, os.path.abspath(f),
                                repo_root=os.path.abspath("."), max_mutants=args.max_mutants,
                                runner="pytest")
            print(f"      mutation: {ms['killed']}/{ms['total']} killed"
                  f" [of {ms['sites_available']} sites, ops={ms['operator_set']}]"
                  + (f" | survivors {ms['survivors'][:3]}" if ms["survivors"] else ""))

    print(f"\nHARVEST: {n_valid} VALID, {n_invalid} INVALID, {n_error} ERROR "
          f"of {len(files)} files -> {args.log}")
    return 0 if n_invalid == 0 and n_error == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
