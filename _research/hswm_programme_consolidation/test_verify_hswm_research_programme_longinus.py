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
