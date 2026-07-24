from __future__ import annotations

from copy import deepcopy

import pytest

from hswm_weight_snapshot import canonical_sha256
from p1v2_prompt_parity import ARM_IDS
from p1v3_calibration_gate import evaluate_policy_calibration
from p1v3_calibration_measure import build_calibration_evidence
from p1v3_heldout_judge import judge_heldout
from p1v3_heldout_measure import build_heldout_evidence
from p1v3_heldout_preflight import (
    FROZEN_MODULES,
    P1V3HeldoutPreflightError,
    build_heldout_budget,
)
from p1v3_prepare import build_policy_manifests


class CharacterPadder:
    tokenizer_identity = "fixture-tokenizer:v1"
    padding_identity = "fixture-padding:v1"

    def count_prompt_tokens(self, prompt):
        return len(prompt)

    def pad_memory_context(self, memory_context, *, target_prompt_tokens, render_prompt):
        while len(render_prompt(memory_context)) < target_prompt_tokens:
            memory_context += "x"
        return memory_context


def _manifests():
    articles = [
        {"title": f"P{i}", "article": f"The occupation of P{i} is job{i}."}
        for i in range(12)
    ]
    questions = [
        {
            "id": f"case:{i}",
            "type": 6,
            "question": f"Who is the person whose occupation is job{i}?",
        }
        for i in range(12)
    ]
    return build_policy_manifests(
        questions,
        articles,
        universe="fixture-seed3",
        dataset_file_sha256={"articles.json": "1" * 64},
        generation_receipt_sha256="2" * 64,
    )


def _gate_observation(case_id, *, no_memory):
    arms = {
        arm: {
            "answers_sha256": canonical_sha256({
                "case": case_id, "answer": "right" if arm == ARM_IDS[0] else no_memory
            }),
            "set_match": 1 if arm == ARM_IDS[0] else no_memory,
            "logical_call_count": 1,
        }
        for arm in ARM_IDS
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


def _calibration(public, development, *, passed=True):
    calibration_ids = [row["case_id"] for row in public["splits"]["calibration"]]
    observations = [
        _gate_observation(case_id, no_memory=0 if passed else 1)
        for case_id in calibration_ids
    ]
    gate = evaluate_policy_calibration(
        observations,
        calibration_case_ids=calibration_ids,
        future_heldout_case_ids=[row["case_id"] for row in public["splits"]["heldout"]],
        environment_sha256=public["public_manifest_sha256"],
    )
    return build_calibration_evidence(
        budget={
            "budget_manifest_sha256": "3" * 64,
            "data": {
                "public_manifest_sha256": public["public_manifest_sha256"],
                "development_sidecar_sha256": development[
                    "development_sidecar_sha256"
                ],
                "heldout_sidecar_sha256": public["heldout_sidecar_sha256"],
            },
        },
        gate_receipt=gate,
        observations=observations,
        command=("python", "calibrate"),
        cwd="/fixture",
        runtime_commit="4" * 40,
        environment={"host": "fixture"},
    )


def _build_budget(*, calibration_passed=True):
    public, development, heldout = _manifests()
    calibration = _calibration(public, development, passed=calibration_passed)
    separation = {
        "public": {"manifest_sha256": public["public_manifest_sha256"]},
        "development": {
            "sidecar_sha256": development["development_sidecar_sha256"]
        },
        "heldout": {
            "sidecar_sha256": heldout["heldout_sidecar_sha256"],
            "file_sha256": "7" * 64,
        },
    }
    budget = build_heldout_budget(
        public=public,
        development=development,
        calibration_evidence=calibration,
        sidecar_separation=separation,
        padder=CharacterPadder(),
        public_file_sha256="5" * 64,
        development_file_sha256="6" * 64,
        heldout_file_sha256="7" * 64,
        sidecar_separation_receipt_file_sha256="d" * 64,
        calibration_evidence_file_sha256="8" * 64,
        deployment_receipt_sha256="9" * 64,
        deployment_file_sha256="a" * 64,
        module_sha256={module: "b" * 64 for module in FROZEN_MODULES},
        model="fixed-model",
        model_revision="revision-1",
    )
    return public, budget


def _heldout_observation(case_id, *, improves):
    rows = {}
    for arm in ARM_IDS:
        label = "same" if not improves else ("typed" if arm == ARM_IDS[0] else "base")
        rows[arm] = {
            "request_sha256": canonical_sha256({"case": case_id, "arm": arm}),
            "answers_sha256": canonical_sha256({"case": case_id, "answer": label}),
            "set_match": 1 if (arm == ARM_IDS[0] or not improves) else 0,
            "user_prompt_tokens": 100,
            "logical_call_count": 1,
        }
    observation = {
        "schema_version": "hswm-p1v2-l0-observation/v1",
        "case_id": case_id,
        "question_sha256": "c" * 64,
        "document_ids": ["doc:1", "doc:2"],
        "parity_receipt_sha256": "d" * 64,
        "answer_adapter_identity": "e" * 64,
        "arms": rows,
        "measurements": {},
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
    observation["observation_sha256"] = canonical_sha256(observation)
    return observation


def _evidence(public, budget, improvements):
    case_ids = [row["case_id"] for row in public["splits"]["heldout"]]
    return build_heldout_evidence(
        preregistration_sha256="f" * 64,
        prediction_receipt_sha256="1" * 64,
        budget=budget,
        observations=[
            _heldout_observation(case_id, improves=index < improvements)
            for index, case_id in enumerate(case_ids)
        ],
        command=("python", "measure"),
        cwd="/fixture",
        runtime_commit="2" * 40,
        environment={"host": "fixture"},
    )


def test_heldout_budget_requires_pass_and_freezes_twenty_four_calls():
    public, development, heldout = _manifests()
    separation = {
        "public": {"manifest_sha256": public["public_manifest_sha256"]},
        "development": {
            "sidecar_sha256": development["development_sidecar_sha256"]
        },
        "heldout": {
            "sidecar_sha256": heldout["heldout_sidecar_sha256"],
            "file_sha256": "7" * 64,
        },
    }
    with pytest.raises(P1V3HeldoutPreflightError, match="did not authorize"):
        build_heldout_budget(
            public=public,
            development=development,
            calibration_evidence=_calibration(public, development, passed=False),
            sidecar_separation=separation,
            padder=CharacterPadder(),
            public_file_sha256="5" * 64,
            development_file_sha256="6" * 64,
            heldout_file_sha256="7" * 64,
            sidecar_separation_receipt_file_sha256="d" * 64,
            calibration_evidence_file_sha256="8" * 64,
            deployment_receipt_sha256="9" * 64,
            deployment_file_sha256="a" * 64,
            module_sha256={module: "b" * 64 for module in FROZEN_MODULES},
            model="fixed-model",
            model_revision="revision-1",
        )
    _public, budget = _build_budget()
    assert budget["data"]["heldout_case_count"] == 6
    assert budget["parity"]["physical_model_calls_total"] == 24
    assert budget["score_contract"]["minimum_typed_improvements_for_pass"] == 3
    assert "verdict" not in str(budget).casefold()


def test_independent_judge_passes_and_kills_at_frozen_threshold():
    public, budget = _build_budget()
    passed = judge_heldout(
        evidence=_evidence(public, budget, 6),
        budget=budget,
        judge_script_sha256="3" * 64,
    )
    assert passed["verdict"] == "PASS"
    assert passed["value"] == 6
    killed = judge_heldout(
        evidence=_evidence(public, budget, 2),
        budget=budget,
        judge_script_sha256="3" * 64,
    )
    assert killed["verdict"] == "KILL"
    assert killed["value"] == 2


def test_independent_judge_rejects_measurement_self_judgment():
    public, budget = _build_budget()
    evidence = deepcopy(_evidence(public, budget, 6))
    evidence["verdict"] = "PASS"
    unsigned = dict(evidence)
    unsigned.pop("evidence_sha256")
    evidence["evidence_sha256"] = canonical_sha256(unsigned)
    with pytest.raises(Exception, match="verdict key"):
        judge_heldout(
            evidence=evidence, budget=budget, judge_script_sha256="3" * 64
        )
