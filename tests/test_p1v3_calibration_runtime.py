from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from hswm_weight_snapshot import canonical_sha256
from p1v2_prompt_parity import ARM_IDS
from p1v3_calibration_gate import evaluate_policy_calibration
from p1v3_calibration_measure import build_calibration_evidence
from p1v3_calibration_preflight import (
    FROZEN_MODULES,
    P1V3CalibrationPreflightError,
    build_calibration_budget,
    verify_development_boundary,
)
from p1v3_prepare import build_policy_manifests


class CharacterPadder:
    tokenizer_identity = "fixture-chat-character-tokenizer:v1"
    padding_identity = "fixture-character-padding:v1"

    def count_prompt_tokens(self, prompt):
        return len(prompt)

    def pad_memory_context(self, memory_context, *, target_prompt_tokens, render_prompt):
        padded = memory_context
        while self.count_prompt_tokens(render_prompt(padded)) < target_prompt_tokens:
            padded += "x"
        return padded


def _manifests():
    articles = []
    questions = []
    for index in range(12):
        title = f"Person{index}"
        value = f"job{index}"
        articles.append({
            "title": title,
            "article": f"The occupation of {title} is {value}.",
        })
        questions.append({
            "id": f"case:{index}",
            "type": 6,
            "question": f"Who is the person whose occupation is {value}?",
        })
    return build_policy_manifests(
        questions,
        articles,
        universe="fixture-seed3",
        dataset_file_sha256={"articles.json": "1" * 64},
        generation_receipt_sha256="2" * 64,
    )


def _observation(case_id: str, *, typed: int, no_memory: int):
    arms = {}
    for arm in ARM_IDS:
        match = typed if arm == "T1_typed_lesson" else no_memory
        arms[arm] = {
            "answers_sha256": canonical_sha256({
                "case_id": case_id, "arm": arm, "match": match
            }),
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


def test_calibration_budget_is_development_only_and_exactly_twelve_calls():
    public, development, _heldout = _manifests()
    budget = build_calibration_budget(
        public=public,
        development=development,
        padder=CharacterPadder(),
        public_file_sha256="3" * 64,
        development_file_sha256="4" * 64,
        deployment_receipt_sha256="5" * 64,
        deployment_file_sha256="6" * 64,
        module_sha256={module: "7" * 64 for module in FROZEN_MODULES},
        model="fixed-model",
        model_revision="revision-1",
    )

    assert budget["measurement_state"] == "FROZEN_UNRUN"
    assert budget["data"]["calibration_case_count"] == 3
    assert budget["data"]["future_heldout_case_count"] == 6
    assert budget["data"]["heldout_sidecar_loaded"] is False
    assert budget["data"]["heldout_outcomes_inspected"] is False
    assert budget["parity"]["physical_model_calls_total"] == 12
    assert "heldout" not in inspect.signature(build_calibration_budget).parameters
    assert "verdict" not in str(budget).casefold()


def test_development_boundary_rejects_a_rebound_heldout_outcome():
    public, development, heldout = _manifests()
    public = deepcopy(public)
    development = deepcopy(development)
    heldout_case_id, heldout_row = next(iter(heldout["cases"].items()))
    development["cases"][heldout_case_id] = heldout_row
    unsigned = dict(development)
    unsigned.pop("development_sidecar_sha256")
    development["development_sidecar_sha256"] = canonical_sha256(unsigned)
    public["development_sidecar_sha256"] = development[
        "development_sidecar_sha256"
    ]
    public_unsigned = dict(public)
    public_unsigned.pop("public_manifest_sha256")
    public["public_manifest_sha256"] = canonical_sha256(public_unsigned)

    with pytest.raises(P1V3CalibrationPreflightError, match="case cut|heldout"):
        verify_development_boundary(public, development)


def test_calibration_evidence_binds_gate_without_scientific_self_judgment():
    observations = [
        _observation("cal:1", typed=1, no_memory=0),
        _observation("cal:2", typed=1, no_memory=1),
        _observation("cal:3", typed=1, no_memory=1),
    ]
    gate = evaluate_policy_calibration(
        observations,
        calibration_case_ids=("cal:1", "cal:2", "cal:3"),
        future_heldout_case_ids=("heldout:1",),
        environment_sha256="8" * 64,
    )
    budget = {
        "budget_manifest_sha256": "9" * 64,
        "data": {
            "public_manifest_sha256": "a" * 64,
            "development_sidecar_sha256": "b" * 64,
            "heldout_sidecar_sha256": "c" * 64,
        },
    }
    evidence = build_calibration_evidence(
        budget=budget,
        gate_receipt=gate,
        observations=observations,
        command=("python", "p1v3_calibration_measure.py"),
        cwd="/frozen/code",
        runtime_commit="d" * 40,
        environment={"host": "fixture"},
    )

    assert evidence["calibration_gate"]["gate_status"] == "CALIBRATION_PASS"
    assert evidence["data_boundary"]["heldout_sidecar_loaded"] is False
    assert evidence["scientific_judgment_emitted"] is False
    assert "verdict" not in str(evidence).casefold()
    unsigned = dict(evidence)
    declared = unsigned.pop("evidence_sha256")
    assert declared == canonical_sha256(unsigned)
