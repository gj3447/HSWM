from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


HERE = Path(__file__).resolve().parent
VERIFIER_PATH = HERE / "verify_hswm_research_programme_longinus.py"
SPEC = importlib.util.spec_from_file_location("hswm_programme_longinus", VERIFIER_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture()
def manifest() -> dict:
    return json.loads(MODULE.MANIFEST_PATH.read_text(encoding="utf-8"))


def test_exact_manifest_and_injected_negative_pass(manifest: dict) -> None:
    receipt = MODULE.validate_manifest(manifest)
    assert receipt["status"] == "PASS"
    assert receipt["scientific_status"] == "UNJUDGED"
    assert receipt["injected_negative_caught"] is True


def test_cli_emits_machine_readable_receipt() -> None:
    completed = subprocess.run(
        [sys.executable, str(VERIFIER_PATH)],
        cwd=MODULE.HSWM_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["status"] == "PASS"
    assert receipt["ledger_validation"]["status"] == "PASS"


def test_hash_drift_is_rejected(manifest: dict) -> None:
    broken = deepcopy(manifest)
    broken["bindings"][0]["sha256"] = "0" * 64
    broken["bindings"][0]["chain"]["sha256"] = "0" * 64
    with pytest.raises(MODULE.BindingError, match="SHA drift"):
        MODULE.validate_manifest(broken, inject_negative=False)


def test_scientific_promotion_is_rejected(manifest: dict) -> None:
    broken = deepcopy(manifest)
    broken["authority"]["scientific_status"] = "PROGRESSIVE"
    with pytest.raises(MODULE.BindingError, match="fail-closed"):
        MODULE.validate_manifest(broken, inject_negative=False)


def test_missing_gap_is_rejected(manifest: dict) -> None:
    broken = deepcopy(manifest)
    broken["required_gaps"].pop()
    with pytest.raises(MODULE.BindingError, match="required-gap set drift"):
        MODULE.validate_manifest(broken, inject_negative=False)


def test_reordered_longinus_chain_is_rejected(manifest: dict) -> None:
    broken = deepcopy(manifest)
    chain = broken["bindings"][0]["chain"]
    kg_node = chain.pop("kg_node")
    chain["kg_node"] = kg_node
    with pytest.raises(MODULE.BindingError, match="seven-layer chain"):
        MODULE.validate_manifest(broken, inject_negative=False)


def test_verified_proxmox_snapshot_is_accepted(manifest: dict, tmp_path: Path) -> None:
    snapshot = tmp_path / "research-20260726-230000"
    fake_hswm = snapshot / "COMPAT_SOURCES/CDROOT/SYMPOSIUM/GIT/HSWM"
    fake_hswm.mkdir(parents=True)
    receipt_path = snapshot / "RUNTIME_EVIDENCE/SYNC_RECEIPT.json"
    receipt_path.parent.mkdir()
    receipt_path.write_text(
        json.dumps(
            {
                "snapshot": str(snapshot),
                "verified": True,
                "stale_mappings": [],
            }
        ),
        encoding="utf-8",
    )

    mode = MODULE.verify_git_provenance(manifest["programme"], root=fake_hswm)

    assert mode == "SNAPSHOT_CONTENT_HASH_PLUS_SYNC_RECEIPT"


def test_stale_proxmox_snapshot_is_rejected(manifest: dict, tmp_path: Path) -> None:
    snapshot = tmp_path / "research-20260726-230001"
    fake_hswm = snapshot / "COMPAT_SOURCES/CDROOT/SYMPOSIUM/GIT/HSWM"
    fake_hswm.mkdir(parents=True)
    receipt_path = snapshot / "RUNTIME_EVIDENCE/SYNC_RECEIPT.json"
    receipt_path.parent.mkdir()
    receipt_path.write_text(
        json.dumps(
            {
                "snapshot": str(snapshot),
                "verified": True,
                "stale_mappings": ["COMPAT_SOURCES/CDROOT/SYMPOSIUM/GIT"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(MODULE.BindingError, match="explicitly stale"):
        MODULE.verify_git_provenance(manifest["programme"], root=fake_hswm)


def test_proxmox_snapshot_uses_catalogue_root(tmp_path: Path) -> None:
    snapshot = tmp_path / "research-20260726-230002"
    fake_hswm = snapshot / "COMPAT_SOURCES/CDROOT/SYMPOSIUM/GIT/HSWM"

    assert MODULE.infer_symposium_root(fake_hswm) == snapshot
