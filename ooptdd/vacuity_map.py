"""ooptdd v2.4 — vacuity map: mutation-score every harvested test file.

Pairs each test file with its most likely subject module, runs a pytest-runner
mutation scan, and ranks files so the most vacuous tests surface first.

Pairing rule (deterministic, documented):
  1. name match: tests/test_foo_bar.py -> repo_root/foo_bar.py when it exists
  2. else the first repo-root module imported by the test that is not a shared
     utility (metrics/synth/np helpers) — the import graph is the honest signal
  3. else UNPAIRED (skipped, listed separately — never guessed silently)

Usage (repo root):
  .venv/bin/python -m ooptdd.vacuity_map --workers 4 --max-mutants 6
Writes receipts/vacuity_map_<date>.json and prints the ranked table.
"""
from __future__ import annotations

import argparse
import ast
import datetime
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

from ooptdd.mutate import mutation_score

SHARED = {"metrics", "synth", "numpy", "np", "pytest", "weight_field"}


def repo_modules(repo_root: str) -> set[str]:
    return {os.path.splitext(f)[0] for f in os.listdir(repo_root) if f.endswith(".py")}


def infer_target(test_path: str, repo_root: str, modules: set[str]) -> str | None:
    base = os.path.splitext(os.path.basename(test_path))[0]
    if base.startswith("test_"):
        candidate = base[len("test_"):]
        if candidate in modules:
            return candidate
    try:
        tree = ast.parse(open(test_path, "r", encoding="utf-8").read(), filename=test_path)
    except SyntaxError:
        return None
    for node in tree.body:
        mod = None
        if isinstance(node, ast.Import):
            mod = node.names[0].name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mod = node.module.split(".")[0]
        if mod and mod in modules and mod not in SHARED:
            return mod
    return None


def scan_one(job: dict) -> dict:
    ms = mutation_score(
        os.path.join(job["repo_root"], job["target"] + ".py"),
        job["test_path"], repo_root=job["repo_root"],
        max_mutants=job["max_mutants"], timeout_per_run=job["timeout"],
        runner="pytest",
    )
    return {**job, "killed": ms["killed"], "total": ms["total"],
            "survivors": ms["survivors"], "errors": ms["errors"]}


def scan_group(jobs: list[dict]) -> list[dict]:
    """Scan all jobs of ONE target module sequentially (in-place patch safety)."""
    return [scan_one(j) for j in jobs]


def main() -> int:
    ap = argparse.ArgumentParser(description="mutation-score every harvested test file")
    ap.add_argument("--tests-dir", default="tests")
    ap.add_argument("--max-mutants", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=30, help="per mutant run timeout (s)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    repo_root = os.path.abspath(".")
    modules = repo_modules(repo_root)
    files = sorted(os.path.join(args.tests_dir, f) for f in os.listdir(args.tests_dir)
                   if f.startswith("test_") and f.endswith(".py"))
    jobs, unpaired = [], []
    for f in files:
        if any(x in f for x in args.exclude):
            continue
        target = infer_target(f, repo_root, modules)
        if target is None:
            unpaired.append(f)
            continue
        jobs.append({"test_path": os.path.abspath(f), "target": target,
                     "repo_root": repo_root, "max_mutants": args.max_mutants,
                     "timeout": args.timeout})

    print(f"pairs: {len(jobs)}, unpaired: {len(unpaired)} — scanning with {args.workers} workers…",
          flush=True)
    # in-place patching is per-module: group jobs by target so parallel workers
    # never patch the same module file concurrently (groups run in parallel,
    # jobs inside a group run sequentially within one worker).
    groups: dict[str, list[dict]] = {}
    for j in jobs:
        groups.setdefault(j["target"], []).append(j)

    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(scan_group, g): g for g in groups.values()}
        done = 0
        for fut in as_completed(futs):
            for r in fut.result():
                results.append(r)
                done += 1
                print(f"[{done}/{len(jobs)}] {os.path.basename(r['test_path']):<42} "
                      f"vs {r['target']:<28} {r['killed']}/{r['total']}", flush=True)

    results.sort(key=lambda r: (r["killed"] / max(r["total"], 1), r["test_path"]))
    date = datetime.date.today().isoformat()
    out_path = args.out or os.path.join("receipts", f"vacuity_map_{date}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"date": date, "max_mutants": args.max_mutants,
                   "results": results, "unpaired": unpaired}, fh, indent=1)

    print("\n=== VACUITY MAP (weakest first) ===")
    for r in results:
        score = r["killed"] / max(r["total"], 1)
        flag = "🔴" if score == 0 else ("🟡" if score < 0.5 else "🟢")
        print(f"{flag} {r['killed']}/{r['total']:<3} {os.path.basename(r['test_path']):<42} -> {r['target']}")
    if unpaired:
        print("\nunpaired (no subject module inferred):", ", ".join(os.path.basename(u) for u in unpaired))
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
