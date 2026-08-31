"""Adversarial checks for the pre-outcome confirmatory readiness gate."""

from __future__ import annotations

from copy import deepcopy

import pytest

from _research.dnrd5.canonical_json import canonical_bytes
from _research.dnrd5.confirmatory_revision_protocol import (
    STATUS,
    ConfirmatoryProtocolRefusal,
    validate_confirmatory_readiness,
)


def _descriptor(char: str) -> dict[str, object]:
    return {"sha256": char * 64, "byte_length": 1}


def _manifest() -> dict[str, object]:
    artifacts = {
        name: _descriptor(char)
        for name, char in zip(
            ("task_generator", "probe_commitment", "placebo_commitment", "w0_forks", "assignment", "model_runtime", "decoding", "evaluator_program", "judge_program", "permit_policy", "analysis_program"),
            "123456789ab",
            strict=True,
        )
    }
    return {
        "schema_version": "hswm-dnrd5-confirmatory-revision-readiness/v1",
        "status": STATUS,
        "study_id": "HSWM-DNRD-5-CONFIRMATORY-REVISION-V1",
        "study_binding": "c" * 64,
        "source": {"commit": "d" * 40, "tree": "e" * 40, "protocol_sha256": "f" * 64},
        "artifacts": artifacts,
        "call_budget": {"block_count": 300, "calls_per_block": 9, "total_calls": 2700, "retry": "FORBIDDEN_NO_REPLACEMENT_NO_RESUME"},
        "arms": ["ACTIVE", "OUTCOME_INDEPENDENT_SHAM", "DELAYED_NO_CREDIT", "EXACT_W0_ROLLBACK"],
        "control_contract": {"sham": "OUTCOME_INDEPENDENT_SHAM", "delayed": "DELAYED_NO_CREDIT", "rollback": "EXACT_W0_ROLLBACK"},
        "seals": ["STUDY_BINDING", "TASK_AND_PRIVATE_COMMITMENTS", "W0_AND_OPAQUE_FORKS", "FUTURE_RANDOMNESS_AND_ASSIGNMENT", "MODEL_RUNTIME_AND_DECODING", "INDEPENDENT_EVALUATOR_AND_JUDGE", "IMMUTABLE_EVIDENCE_DESTINATION"],
        "principals": {"transition_executor": "executor", "revision_proposer": "proposer", "outcome_evaluator": "evaluator", "credit_adjudicator": "adjudicator", "independent_judge": "judge", "permit_authorizer": "authorizer"},
        "evaluator": {"blind_to": ["arm", "clone", "probe_order", "canonical_state", "feedback_source"], "hidden_answer_custody": "SEPARATE_PRIVATE_CUSTODY_COMMITTED_PRE_OUTCOME", "outcome_source": "INDEPENDENT_EXECUTABLE_EVALUATOR", "judge_source": "INDEPENDENT_POST_SEAL_REIMPLEMENTATION", "post_seal_write_access": False, "independent_reimplementation_required": True},
        "evidence_destination": {"append_only": True, "immutable_raw_artifacts": True, "external_to_runner": True, "pre_outcome_seal_required": True},
        "claim_ceiling": {"passing_readiness_establishes": "STRUCTURAL_PRE_OUTCOME_ELIGIBILITY_ONLY", "passing_readiness_does_not_establish": "EXECUTION_OUTCOME_TRUTH_CAUSAL_CREDIT_OR_LLM_BEHAVIOR_IMPROVEMENT"},
    }


def test_valid_readiness_remains_explicitly_non_evidential() -> None:
    result = validate_confirmatory_readiness(canonical_bytes(_manifest()))
    assert result["readiness_status"] == STATUS
    assert result["total_calls"] == 2700
    assert result["execution_occurred"] is False
    assert result["outcome_truth_established"] is False
    assert result["causal_credit_established"] is False
    assert result["llm_revision_improvement_established"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda x: x["call_budget"].__setitem__("total_calls", 1),
        lambda x: x["call_budget"].__setitem__("retry", "ALLOWED"),
        lambda x: x.__setitem__("arms", list(reversed(x["arms"]))),
        lambda x: x["control_contract"].__setitem__("sham", "NO_CONTROL"),
        lambda x: x["seals"].pop(),
        lambda x: x["principals"].__setitem__("independent_judge", "evaluator"),
        lambda x: x["evaluator"].__setitem__("blind_to", []),
        lambda x: x["evidence_destination"].__setitem__("append_only", False),
        lambda x: x["claim_ceiling"].__setitem__("passing_readiness_establishes", "CAUSAL_EFFECT"),
    ],
)
def test_critical_causal_safeguard_mutations_refuse(mutate) -> None:
    candidate = deepcopy(_manifest())
    mutate(candidate)
    with pytest.raises(ConfirmatoryProtocolRefusal):
        validate_confirmatory_readiness(canonical_bytes(candidate))
