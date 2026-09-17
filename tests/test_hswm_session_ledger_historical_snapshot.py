"""Repository Git history independently checks the ledger's fixed commit window."""

from __future__ import annotations

from pathlib import Path
import subprocess

from scripts import build_hswm_session_ledger_2026_09_06 as builder


ROOT = Path(__file__).resolve().parents[1]


def test_every_window_commit_is_ledgered_once_with_the_right_core_flag() -> None:
    log = subprocess.run(
        ["git", "log", f"{builder.WINDOW_START_COMMIT}..{builder.COMMITS[-1]['sha']}", "--format=%x1e%H", "--name-only", "--reverse"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    observed = {}
    for chunk in log.split("\x1e")[1:]:
        lines = [line for line in chunk.strip("\n").split("\n") if line]
        observed[lines[0]] = any(path.startswith(builder.CORE_PATH_PREFIXES) for path in lines[1:])
    ledgered = {row["sha"]: row["core"] for row in builder.COMMITS}
    assert ledgered == observed
    positions = [row["position"] for row in builder.COMMITS]
    assert positions == list(range(1, len(builder.COMMITS) + 1))
    assert sum(1 for row in builder.COMMITS if row["core"]) == 27
