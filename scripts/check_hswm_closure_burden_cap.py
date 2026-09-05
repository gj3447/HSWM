#!/usr/bin/env python3
"""Report the HSWM closure burden cap against git history.

The cap is read from the closure-plan bundle so the number, window, and core
paths have exactly one home.  The script only reports; it never edits history,
never asserts a pass in CI, and is not a research result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v1.json"


def load_cap(bundle_path: Path) -> dict[str, Any]:
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    caps = [
        row["properties"]
        for row in data["nodes"]
        if row["properties"].get("plan_graph_role") == "BURDEN_CAP"
    ]
    if len(caps) != 1:
        raise SystemExit("bundle must carry exactly one burden cap")
    return caps[0]


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def commits_after(start: str, limit: int) -> list[str]:
    output = _git("rev-list", "--reverse", f"{start}..HEAD")
    commits = [line for line in output.splitlines() if line]
    return commits[:limit]


def touched_paths(commit: str) -> list[str]:
    output = _git("diff-tree", "--no-commit-id", "--name-only", "-r", commit)
    return [line for line in output.splitlines() if line]


def evaluate(cap: dict[str, Any], commits: list[str]) -> dict[str, Any]:
    prefixes = tuple(cap["core_path_prefixes"])
    core: list[str] = []
    rows: list[dict[str, Any]] = []
    for commit in commits:
        paths = touched_paths(commit)
        is_core = any(path.startswith(prefixes) for path in paths)
        if is_core:
            core.append(commit)
        rows.append({"commit": commit[:12], "core": is_core, "paths": len(paths)})
    share = (len(core) / len(commits)) if commits else 0.0
    window_full = len(commits) >= cap["window_commits"]
    status = (
        "WINDOW_OPEN"
        if not window_full and share >= cap["min_core_share"]
        else "WINDOW_OPEN_BELOW_SHARE"
        if not window_full
        else "WITHIN_CAP"
        if share >= cap["min_core_share"]
        else "CAP_VIOLATED"
    )
    return {
        "window_start_commit": cap["window_start_commit"],
        "window_commits": cap["window_commits"],
        "commits_observed": len(commits),
        "core_commits": len(core),
        "core_share": round(share, 4),
        "min_core_share": cap["min_core_share"],
        "v3_run_by": cap["v3_run_by"],
        "status": status,
        "violation_disposition": cap["violation_disposition"],
        "claim_boundary": "effort-allocation report only; not a research result and not a CI gate",
        "commits": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    cap = load_cap(args.bundle)
    report = evaluate(cap, commits_after(cap["window_start_commit"], int(cap["window_commits"])))
    if not args.verbose:
        report.pop("commits")
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
