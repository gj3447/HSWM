from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from p1v2_l0_diagnose import L0DiagnosisError, diagnose_l0_inertness


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    return json.loads((ROOT / "receipts" / name).read_text(encoding="utf-8"))


def test_real_r2_measurement_is_baseline_ceiling_and_inert():
    diagnosis = diagnose_l0_inertness(
        _load("p1v2_l0_measurement_r2_512_evidence_20260724.json"),
        _load("p1v2_l0_judge_r2_512_20260724.json"),
    )

    assert diagnosis["diagnosis"] == "BASELINE_CEILING_AND_INTERVENTION_INERT"
    assert diagnosis["metrics"] == {
        "case_count": 6,
        "no_memory_exact_set_match_count": 6,
        "typed_exact_set_match_count": 6,
        "all_four_arms_identical_answer_count": 6,
        "typed_changed_no_memory_answer_count": 0,
        "typed_improved_no_memory_count": 0,
    }
    assert diagnosis["same_environment_reuse_allowed"] is False


def test_diagnosis_rejects_unbound_judge_receipt():
    receipt = _load("p1v2_l0_judge_r2_512_20260724.json")
    tampered = deepcopy(receipt)
    tampered["evidence_sha256"] = "0" * 64

    with pytest.raises(L0DiagnosisError, match="self-hash"):
        diagnose_l0_inertness(
            _load("p1v2_l0_measurement_r2_512_evidence_20260724.json"),
            tampered,
        )
