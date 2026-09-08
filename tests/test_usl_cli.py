from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from hswm.cells.conditional import Reject
from hswm.infrastructure.usl_cli import preview_usl_request


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "_research/usl_adapter/examples/preview.v1.json"


def test_usl_readiness_and_expiry_change_existing_hswm_preview() -> None:
    request = json.loads(EXAMPLE.read_text())
    ready = preview_usl_request(request)
    assert ready["preview"]["status"] == "DESIGN_ONLY_NO_EXECUTION"
    assert ready["preview"]["hypothetical_next_step"]["kind"] == "ACTION_PROPOSAL"
    assert ready["adapter"]["observations"][0]["value"] is True
    assert [p["role"] for p in ready["adapter"]["links"][0]["participants"]] == ["code", "target", "context"]
    request["preview"]["checks"]["now"] += 120
    stale = preview_usl_request(request)
    assert stale["preview"]["hypothetical_next_step"]["kind"] == "OBSERVE"
    assert stale["adapter"]["observations"] == []
    assert stale["adapter"]["status"] == "UNRESOLVED"
    assert "no semantic truth" in stale["adapter"]["mapping_loss"]


def test_usl_preview_rejects_extra_observations_and_nonboolean_domain() -> None:
    request = json.loads(EXAMPLE.read_text())
    injected = deepcopy(request)
    injected["preview"]["observations"] = [{"role": "usl", "field": "references_resolve", "value": True}]
    with pytest.raises(Reject):
        preview_usl_request(injected)
    request["preview"]["domain"][0]["values"] = [0, 1]
    with pytest.raises(Reject, match="Boolean"):
        preview_usl_request(request)


def test_usl_cli_emits_json_and_rejects_malformed_discriminators(tmp_path: Path) -> None:
    command = [sys.executable, "-m", "hswm.infrastructure.usl_cli", "preview", "--request"]
    good = subprocess.run([*command, str(EXAMPLE)], cwd=ROOT, capture_output=True, text=True)
    assert good.returncode == 0, good.stderr
    assert json.loads(good.stdout)["adapter"]["status"] == "READY"
    request = json.loads(EXAMPLE.read_text())
    request["plan"]["resources"][0]["locator"]["kind"] = []
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(request))
    bad = subprocess.run([*command, str(bad_path)], cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode == 2
    assert json.loads(bad.stderr)["status"] == "REJECTED"
    assert "Traceback" not in bad.stderr
