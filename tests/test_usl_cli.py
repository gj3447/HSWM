from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

from hswm.cells.conditional import Reject
from hswm.infrastructure.usl_cli import preview_usl_request


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "_research/usl_adapter/examples/preview.v1.json"
EXAMPLE_V2 = ROOT / "_research/usl_adapter/examples/preview.v2.json"


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


def test_v2_cli_preserves_meaning_json_order_for_usl_hashes() -> None:
    path = ROOT / "_research/usl_adapter/examples/preview.v2.json"
    for action in ("project", "preview"):
        request = json.loads(path.read_text())
        if action == "project":
            checks = request.pop("preview")["checks"]
            request.update({key: checks[key] for key in ("allowed_reads", "now", "revision")})
        # Invoke main through stdin-independent argv with a temporary request.
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "request.json"
            input_path.write_text(json.dumps(request, ensure_ascii=False))
            output = subprocess.run([sys.executable, "-m", "hswm.infrastructure.usl_cli", action,
                                     "--request", str(input_path)], cwd=ROOT, capture_output=True, text=True)
        assert output.returncode == 0, output.stderr
        result = json.loads(output.stdout)
        projection = result["adapter"] if action == "preview" else result
        for meaning in projection["meanings"]:
            raw = json.dumps(meaning["definition"], ensure_ascii=False, separators=(",", ":")).encode()
            assert meaning["digest"] == "sha256:" + sha256(raw).hexdigest()


def test_usl_cli_accepts_v2_and_rejects_resigned_report_drift(tmp_path: Path) -> None:
    command = [sys.executable, "-m", "hswm.infrastructure.usl_cli", "preview", "--request"]
    good = subprocess.run([*command, str(EXAMPLE_V2)], cwd=ROOT, capture_output=True, text=True)
    assert good.returncode == 0, good.stderr
    projected = json.loads(good.stdout)["adapter"]
    assert projected["schema_version"] == "hswm-usl-observation-projection/v2"
    assert projected["usl"]["report_schema"] == "usl-program-observation/v2"

    request = json.loads(EXAMPLE_V2.read_text())
    request["report"]["readScope"]["links"] = []
    payload = {key: value for key, value in request["report"].items() if key != "observationDigest"}
    request["report"]["observationDigest"] = "sha256:" + __import__("hashlib").sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    bad_path = tmp_path / "v2-resigned-invalid.json"
    bad_path.write_text(json.dumps(request))
    bad = subprocess.run([*command, str(bad_path)], cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode == 2
    assert json.loads(bad.stderr)["status"] == "REJECTED"
