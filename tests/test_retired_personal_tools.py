from __future__ import annotations

import json
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPLOADER = ROOT / "bin_hswm_cellular_lakatotree_upload.py"
REMOTE_APPLY = ROOT / "bin_hswm_cellular_lakatotree_apply_remote.sh"


def test_lakatotree_uploader_refuses_mutation_without_network():
    result = subprocess.run(
        [sys.executable, str(UPLOADER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stderr)
    assert result.returncode == 2
    assert payload["status"] == "REFUSED"
    assert "RETIRED" in payload["reason"]


def test_lakatotree_packet_validation_remains_available():
    result = subprocess.run(
        [sys.executable, str(UPLOADER), "--validate-only"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["status"] == "PACKET_VALID_HISTORICAL_READ_ONLY"
    assert payload["mutation_allowed"] is False
    assert payload["scientific_status"] == "UNJUDGED"


def test_remote_apply_is_a_non_executable_retired_tombstone():
    assert not (REMOTE_APPLY.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
    result = subprocess.run(
        ["bash", str(REMOTE_APPLY)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "RETIRED" in result.stderr
