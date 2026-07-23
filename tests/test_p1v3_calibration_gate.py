from __future__ import annotations

from copy import deepcopy

import pytest

from hswm_weight_snapshot import canonical_sha256
from p1v2_prompt_parity import ARM_IDS
from p1v3_calibration_gate import (
    PolicyCalibrationError,
    evaluate_policy_calibration,
)


def _observation(case_id: str, *, typed: int, no_memory: int):
    arms = {}
    for arm in ARM_IDS:
        match = typed if arm == "T1_typed_lesson" else no_memory
        answer = "right" if match else "wrong"
        arms[arm] = {
            "answers_sha256": canonical_sha256({"case": case_id, "answer": answer}),
            "set_match": match,
            "logical_call_count": 1,
        }
    return {
        "case_id": case_id,
        "arms": arms,
        "budget": {"logical_model_calls": 4, "token_parity": True},
        "gold_boundary": {
            "gold_sent_to_answer_port": False,
            "gold_opened_only_after_all_arm_answers": True,
            "gold_values_published": False,
        },
    }


def test_calibration_passes_only_with_headroom_disagreement_and_improvement():
    observations = [
        _observation("cal:1", typed=1, no_memory=0),
        _observation("cal:2", typed=1, no_memory=1),
        _observation("cal:3", typed=1, no_memory=1),
    ]
    receipt = evaluate_policy_calibration(
        observations,
        calibration_case_ids=("cal:1", "cal:2", "cal:3"),
        future_heldout_case_ids=("heldout:1", "heldout:2"),
        environment_sha256="1" * 64,
    )

    assert receipt["gate_status"] == "CALIBRATION_PASS"
    assert receipt["heldout_freeze_authorized"] is True
    assert receipt["heldout_outcomes_inspected"] is False
    unsigned = dict(receipt)
    declared = unsigned.pop("calibration_receipt_sha256")
    assert declared == canonical_sha256(unsigned)


def test_calibration_rejects_the_p1v2_ceiling_pattern():
    observations = [
        _observation(f"cal:{index}", typed=1, no_memory=1)
        for index in range(3)
    ]
    receipt = evaluate_policy_calibration(
        observations,
        calibration_case_ids=tuple(f"cal:{index}" for index in range(3)),
        future_heldout_case_ids=("heldout:1",),
        environment_sha256="2" * 64,
    )

    assert receipt["gate_status"] == "CALIBRATION_REJECT"
    assert receipt["heldout_freeze_authorized"] is False
    assert receipt["reasons"] == [
        "no_memory_baseline_at_or_near_ceiling",
        "typed_policy_did_not_change_enough_answers",
        "typed_policy_did_not_improve_enough_answers",
    ]


def test_calibration_refuses_heldout_overlap_or_parity_drift():
    observations = [
        _observation("cal:1", typed=1, no_memory=0),
        _observation("cal:2", typed=1, no_memory=1),
        _observation("cal:3", typed=1, no_memory=1),
    ]
    with pytest.raises(PolicyCalibrationError, match="overlap"):
        evaluate_policy_calibration(
            observations,
            calibration_case_ids=("cal:1", "cal:2", "cal:3"),
            future_heldout_case_ids=("cal:3",),
            environment_sha256="3" * 64,
        )

    tampered = deepcopy(observations)
    tampered[0]["budget"]["token_parity"] = False
    with pytest.raises(PolicyCalibrationError, match="parity"):
        evaluate_policy_calibration(
            tampered,
            calibration_case_ids=("cal:1", "cal:2", "cal:3"),
            future_heldout_case_ids=("heldout:1",),
            environment_sha256="3" * 64,
        )
