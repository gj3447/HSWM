from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.validate_hswm_research_ledger import (
    LedgerValidationError,
    validate_ledger,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = REPO_ROOT / "research/HSWM_RESEARCH_LEDGER.v1.json"
VALIDATOR_PATH = REPO_ROOT / "scripts/validate_hswm_research_ledger.py"


@pytest.fixture()
def ledger() -> dict:
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def validate(candidate: dict, *, verify_files: bool = False) -> dict:
    return validate_ledger(
        candidate,
        ledger_path=LEDGER_PATH,
        verify_files=verify_files,
    )


def test_authoritative_ledger_and_local_hashes_pass(ledger: dict) -> None:
    receipt = validate(ledger, verify_files=True)
    assert receipt["status"] == "PASS"
    assert receipt["active_tree"] == "LakatosTree_HSWM_20260719"
    assert receipt["hypotheses_checked"] == 7
    assert receipt["local_hashes_verified"] is True


def test_cli_default_path_passes() -> None:
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["status"] == "PASS"
    assert receipt["hypotheses_checked"] == 7


def test_duplicate_hypothesis_id_is_rejected(ledger: dict) -> None:
    broken = deepcopy(ledger)
    duplicate = deepcopy(broken["hypotheses"][0])
    duplicate["title"] = "Injected duplicate"
    broken["hypotheses"].append(duplicate)
    with pytest.raises(LedgerValidationError, match="duplicate hypothesis_id"):
        validate(broken)


def test_missing_hypothesis_id_is_rejected(ledger: dict) -> None:
    broken = deepcopy(ledger)
    del broken["hypotheses"][0]["hypothesis_id"]
    with pytest.raises(LedgerValidationError, match="hypothesis_id"):
        validate(broken)


def test_unknown_state_is_rejected(ledger: dict) -> None:
    broken = deepcopy(ledger)
    broken["hypotheses"][0]["state"] = "looks_promising"
    with pytest.raises(LedgerValidationError, match="unknown value"):
        validate(broken)


def test_missing_claimed_artifact_hash_is_rejected(ledger: dict) -> None:
    broken = deepcopy(ledger)
    del broken["hypotheses"][0]["prereg_refs"][0]["sha256"]
    with pytest.raises(LedgerValidationError, match="missing required fields: sha256"):
        validate(broken)


def test_local_artifact_hash_drift_is_rejected(ledger: dict) -> None:
    broken = deepcopy(ledger)
    broken["hypotheses"][0]["prereg_refs"][0]["sha256"] = "0" * 64
    with pytest.raises(LedgerValidationError, match="SHA-256 drift"):
        validate(broken, verify_files=True)


def test_second_active_tree_is_rejected(ledger: dict) -> None:
    broken = deepcopy(ledger)
    broken["predecessor_trees"][0]["status"] = "ACTIVE"
    with pytest.raises(LedgerValidationError, match="exactly one ACTIVE"):
        validate(broken)


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "/Users/lagyeongjun/CD/SYMPOSIUM/GIT/HSWM",
        "../HSWM",
        "~/HSWM",
    ],
)
def test_unsafe_active_root_is_rejected(ledger: dict, unsafe_path: str) -> None:
    broken = deepcopy(ledger)
    broken["programme_authority"]["active_roots"][0]["path"] = unsafe_path
    with pytest.raises(LedgerValidationError, match="unsafe"):
        validate(broken)


@pytest.mark.parametrize("promoted_state", ["progressive", "canonical"])
def test_scientific_promotion_without_judge_is_rejected(
    ledger: dict, promoted_state: str
) -> None:
    broken = deepcopy(ledger)
    candidate = broken["hypotheses"][2]
    candidate["state"] = promoted_state
    candidate["judge_refs"] = []
    candidate["lakato_refs"] = []
    with pytest.raises(LedgerValidationError, match="without independent judge evidence"):
        validate(broken)


def test_scientific_promotion_without_lakato_readback_is_rejected(
    ledger: dict,
) -> None:
    broken = deepcopy(ledger)
    candidate = broken["hypotheses"][2]
    candidate["state"] = "progressive"
    candidate["judge_refs"] = [
        {
            "artifact_id": "injected-judge-receipt",
            "kind": "judge_receipt",
            "path": "judge://independent/injected",
            "sha256": "1" * 64,
            "availability": "remote",
            "claim_boundary": "Injected structural test fixture only."
        }
    ]
    candidate["lakato_refs"] = []
    with pytest.raises(LedgerValidationError, match="without LakatoTree readback"):
        validate(broken)


def test_duplicate_artifact_id_is_rejected(ledger: dict) -> None:
    broken = deepcopy(ledger)
    duplicate_id = broken["hypotheses"][0]["prereg_refs"][0]["artifact_id"]
    broken["hypotheses"][1]["prereg_refs"][0]["artifact_id"] = duplicate_id
    with pytest.raises(LedgerValidationError, match="duplicate artifact_id"):
        validate(broken)
