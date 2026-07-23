from __future__ import annotations

from copy import deepcopy

import pytest

from hswm_weight_snapshot import canonical_sha256
from p1v2_l0_harness import build_lakato_evidence_record
from p1v2_l0_judge import L0JudgeError, judge_l0, make_contradiction_receipt
from p1v2_prompt_parity import ARM_IDS


def _observation():
    arms = {}
    for arm in ARM_IDS:
        typed = arm == "T1_typed_lesson"
        arms[arm] = {
            "request_sha256": canonical_sha256({"arm": arm}),
            "answers_sha256": canonical_sha256({"answer": "right" if typed else "wrong"}),
            "set_match": int(typed),
            "user_prompt_tokens": 100,
            "logical_call_count": 1,
        }
    value = {
        "schema_version": "hswm-p1v2-l0-observation/v1",
        "case_id": "case:1",
        "question_sha256": "1" * 64,
        "document_ids": ["source:1"],
        "parity_receipt_sha256": "2" * 64,
        "answer_adapter_identity": "fixture",
        "arms": arms,
        "measurements": {
            "typed_minus_no_memory": 1,
            "typed_minus_raw_transcript": 1,
            "typed_minus_shuffled_or_removed": 1,
        },
        "budget": {
            "logical_model_calls": 4,
            "user_prompt_tokens_per_arm": 100,
            "token_parity": True,
        },
        "gold_boundary": {
            "gold_sent_to_answer_port": False,
            "gold_opened_only_after_all_arm_answers": True,
            "gold_values_published": False,
        },
    }
    value["observation_sha256"] = canonical_sha256(value)
    return value


def _evidence():
    return build_lakato_evidence_record(
        programme="LakatosTree_HSWM_20260719",
        branch="P1v2-typed-verdict-lesson",
        conjecture="typed lesson actuates heldout behavior",
        preregistration_sha256="3" * 64,
        prediction_receipt_sha256="4" * 64,
        data_manifest_sha256="5" * 64,
        harness_command=("python", "p1v2_l0_measure.py"),
        harness_cwd="/frozen/hswm",
        git_commit="6" * 40,
        environment={"python": "3.11"},
        observations=(_observation(),),
    )


def _budget():
    value = {
        "schema_version": "hswm-p1v2-l0-budget-manifest/v1",
        "measurement_state": "FROZEN_UNRUN",
        "parity": {"case_plans": [{
            "case_id": "case:1",
            "parity_receipt_sha256": "2" * 64,
            "target_input_tokens_per_arm": 100,
        }]},
        "scientific_judgment_emitted": False,
    }
    value["budget_manifest_sha256"] = canonical_sha256(value)
    return value


def _contradiction(rejected=True):
    return make_contradiction_receipt(
        candidate_lesson_sha256="7" * 64,
        admission_guard_sha256="8" * 64,
        rejected=rejected,
        error_class="Type6EnvironmentError" if rejected else None,
    )


def test_independent_judge_passes_positive_and_kills_injected_negative():
    positive = judge_l0(_evidence(), _budget(), _contradiction(True))
    negative = judge_l0(_evidence(), _budget(), _contradiction(False))

    assert positive["verdict"] == "PASS"
    assert positive["criteria"]["typed_actuation_case_count"] == 1
    assert negative["verdict"] == "KILL"
    assert negative["criteria"]["contradicted_lesson_rejected"] is False


def test_judge_refuses_token_parity_or_evidence_tamper():
    budget = _budget()
    budget["parity"]["case_plans"][0]["target_input_tokens_per_arm"] = 101
    budget["budget_manifest_sha256"] = canonical_sha256({
        key: value for key, value in budget.items() if key != "budget_manifest_sha256"
    })
    with pytest.raises(L0JudgeError, match="call/token budget"):
        judge_l0(_evidence(), budget, _contradiction())

    evidence = deepcopy(_evidence())
    evidence["verdict"] = "PASS"
    with pytest.raises(ValueError, match="must not contain a verdict"):
        judge_l0(evidence, _budget(), _contradiction())
