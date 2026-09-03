from __future__ import annotations

from dataclasses import replace

import pytest

from hswm.evaluation.inspect_outer_runner import INSPECT_AI_REQUIREMENT
from hswm.evaluation.occurrence_dual_evaluator import (
    CLAIM_CEILING,
    DualEvaluationError,
    DualEvaluationTerminal,
    ExternalSignatureEvidenceV1,
    IndependentJudgmentBV1,
    InspectJudgmentAV1,
    assess_dual_evaluation,
)
from hswm.infrastructure.occurrence_integrity import ContentDescriptorV1, RoleBindingV1


def descriptor(seed: str) -> ContentDescriptorV1:
    return ContentDescriptorV1("application/json", seed * 64, 1)


def role(name: str) -> RoleBindingV1:
    return RoleBindingV1(
        name,
        f"issuer-{name}",
        f"subject-{name}",
        f"account-{name}",
        f"admin-{name}",
        f"key-{name}",
        ("evaluate",),
    )


def signed_a(*, verified: bool = True) -> InspectJudgmentAV1:
    unsigned = InspectJudgmentAV1(
        "g0-occurrence-1",
        role("evaluator_a"),
        INSPECT_AI_REQUIREMENT,
        descriptor("a"),
        descriptor("b"),
        descriptor("c"),
        descriptor("d"),
        descriptor("e"),
        descriptor("f"),
        "1" * 64,
        True,
        None,
    )
    signature = ExternalSignatureEvidenceV1(
        "dsse",
        "verifier-a",
        descriptor("2"),
        descriptor("9"),
        unsigned.unsigned_sha256(),
        verified,
    )
    return replace(unsigned, signature=signature)


def signed_b(*, verified: bool = True) -> IndependentJudgmentBV1:
    unsigned = IndependentJudgmentBV1(
        "g0-occurrence-1",
        role("evaluator_b"),
        descriptor("3"),
        descriptor("4"),
        descriptor("5"),
        descriptor("6"),
        descriptor("e"),
        descriptor("7"),
        "1" * 64,
        True,
        None,
    )
    signature = ExternalSignatureEvidenceV1(
        "dsse",
        "verifier-b",
        descriptor("8"),
        descriptor("a"),
        unsigned.unsigned_sha256(),
        verified,
    )
    return replace(unsigned, signature=signature)


def test_exact_blinded_agreement_is_only_an_externally_audited_candidate() -> None:
    assessment = assess_dual_evaluation(signed_a(), signed_b())
    assert assessment.terminal is DualEvaluationTerminal.SEALED_CANDIDATE_REQUIRES_EXTERNAL_SIGNATURE_AUDIT
    assert "NOT_G0" in assessment.claim_ceiling
    assert assessment.claim_ceiling == CLAIM_CEILING
    assert assessment.canonical_json() == assessment.canonical_json()


def test_missing_or_unverified_external_signature_blocks() -> None:
    assert assess_dual_evaluation(replace(signed_a(), signature=None), signed_b()).terminal is DualEvaluationTerminal.BLOCKED_EXTERNAL
    assert assess_dual_evaluation(signed_a(verified=False), signed_b()).terminal is DualEvaluationTerminal.BLOCKED_EXTERNAL
    assert assess_dual_evaluation(None, signed_b()).terminal is DualEvaluationTerminal.BLOCKED_EXTERNAL


def test_decision_or_exact_input_disagreement_is_terminal_void() -> None:
    a, b = signed_a(), signed_b()
    disagreement = replace(b, canonical_decision_score_sha256="0" * 64, signature=None)
    assert assess_dual_evaluation(a, disagreement).terminal is DualEvaluationTerminal.VOID_EVALUATOR_DISAGREEMENT
    different_input = replace(b, input=descriptor("9"), signature=None)
    assert assess_dual_evaluation(a, different_input).terminal is DualEvaluationTerminal.VOID_EVALUATOR_DISAGREEMENT


def test_same_person_credential_or_implementation_is_not_independent() -> None:
    a, b = signed_a(), signed_b()
    shared_account = replace(b, evaluator=replace(b.evaluator, account=a.evaluator.account), signature=None)
    assert assess_dual_evaluation(a, shared_account).terminal is DualEvaluationTerminal.VOID_EVALUATOR_NONINDEPENDENT
    shared_implementation = replace(b, implementation=a.implementation, signature=None)
    assert assess_dual_evaluation(a, shared_implementation).terminal is DualEvaluationTerminal.VOID_EVALUATOR_NONINDEPENDENT


def test_adversarial_binding_and_version_drift_are_rejected_at_construction() -> None:
    a = signed_a()
    with pytest.raises(DualEvaluationError, match="exactly inspect-ai==0.3.260"):
        replace(a, inspect_requirement="inspect-ai==0.3.261", signature=None)
    with pytest.raises(DualEvaluationError, match="does not bind"):
        replace(
            a,
            signature=ExternalSignatureEvidenceV1(
                "dsse", "verifier-a", descriptor("2"), descriptor("9"),
                "0" * 64, True
            ),
        )
    with pytest.raises(DualEvaluationError, match="blind"):
        replace(a, blind_to_arm_identity=False, signature=None)
