"""Fail-closed contract for a blinded, independently operated dual judgment.

This module only compares externally supplied evidence descriptors.  It never
starts Inspect, imports a model provider, verifies a signature cryptographically,
or promotes a result to a scientific claim, Permit, HSWM transition, or learning
event.  Cryptographic verification remains an explicit external-audit step.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Any, Mapping

from hswm.evaluation.inspect_outer_runner import INSPECT_AI_REQUIREMENT
from hswm.experiments.swm0w_beacon import canonical_sha256
from hswm.infrastructure.occurrence_integrity import (
    ContentDescriptorV1,
    OccurrenceIntegrityError,
    RoleBindingV1,
)


SCHEMA = "hswm-occurrence-dual-evaluation/v1"
CLAIM_CEILING = (
    "DUAL_EVALUATION_INTEGRITY_CONTRACT_ONLY_NOT_OUTCOME_TRUTH_NOT_PERMIT_"
    "NOT_G0_NOT_G1_NOT_CANONICAL_LEARNING"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,159}$")


class DualEvaluationError(ValueError):
    """The bounded dual-evaluation wire contract is malformed."""


class DualEvaluationTerminal(str, Enum):
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"
    VOID_EVALUATOR_DISAGREEMENT = "VOID_EVALUATOR_DISAGREEMENT"
    VOID_EVALUATOR_NONINDEPENDENT = "VOID_EVALUATOR_NONINDEPENDENT"
    SEALED_CANDIDATE_REQUIRES_EXTERNAL_SIGNATURE_AUDIT = (
        "SEALED_CANDIDATE_REQUIRES_EXTERNAL_SIGNATURE_AUDIT"
    )


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise DualEvaluationError(f"{name} must be a bounded ASCII identifier")
    return value


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise DualEvaluationError(f"{name} must be a lowercase SHA-256")
    return value


def _descriptor(value: Any, name: str) -> ContentDescriptorV1:
    if not isinstance(value, ContentDescriptorV1):
        raise DualEvaluationError(f"{name} must be an exact content descriptor")
    return value


@dataclass(frozen=True, slots=True)
class ExternalSignatureEvidenceV1:
    """A signature-verification carrier supplied by an external verifier.

    ``cryptographically_verified`` is deliberately a claimed input, rather
    than a locally inferred fact.  A false value can therefore be represented
    and deterministically blocks sealing instead of being mistaken for success.
    """

    scheme: str
    authority: str
    signed_envelope: ContentDescriptorV1
    verification_receipt: ContentDescriptorV1
    signed_payload_sha256: str
    cryptographically_verified: bool

    def __post_init__(self) -> None:
        if self.scheme not in {"dsse", "cms", "openpgp"}:
            raise DualEvaluationError("signature scheme is not allowlisted")
        _identifier(self.authority, "signature authority")
        _descriptor(self.signed_envelope, "signed envelope")
        _descriptor(self.verification_receipt, "signature verification receipt")
        _digest(self.signed_payload_sha256, "signed_payload_sha256")
        if type(self.cryptographically_verified) is not bool:
            raise DualEvaluationError("cryptographically_verified must be a boolean")

    def canonical(self) -> dict[str, Any]:
        return {
            "authority": self.authority,
            "cryptographically_verified": self.cryptographically_verified,
            "scheme": self.scheme,
            "signed_envelope": self.signed_envelope.canonical(),
            "signed_payload_sha256": self.signed_payload_sha256,
            "verification_receipt": self.verification_receipt.canonical(),
        }


@dataclass(frozen=True, slots=True)
class InspectJudgmentAV1:
    """Pinned Inspect judgment declaration; this does not execute Inspect."""

    occurrence_uid: str
    evaluator: RoleBindingV1
    inspect_requirement: str
    implementation: ContentDescriptorV1
    task: ContentDescriptorV1
    scorer: ContentDescriptorV1
    config: ContentDescriptorV1
    input: ContentDescriptorV1
    output: ContentDescriptorV1
    canonical_decision_score_sha256: str
    blind_to_arm_identity: bool
    signature: ExternalSignatureEvidenceV1 | None

    def __post_init__(self) -> None:
        _identifier(self.occurrence_uid, "occurrence_uid")
        if not isinstance(self.evaluator, RoleBindingV1) or self.evaluator.role != "evaluator_a":
            raise DualEvaluationError("judgment A requires an evaluator_a role binding")
        if self.inspect_requirement != INSPECT_AI_REQUIREMENT:
            raise DualEvaluationError(
                f"judgment A requires exactly {INSPECT_AI_REQUIREMENT}"
            )
        for name in ("implementation", "task", "scorer", "config", "input", "output"):
            _descriptor(getattr(self, name), name)
        _digest(self.canonical_decision_score_sha256, "canonical_decision_score_sha256")
        if self.blind_to_arm_identity is not True:
            raise DualEvaluationError("judgment A must be blind to arm identity")
        if self.signature is not None and not isinstance(self.signature, ExternalSignatureEvidenceV1):
            raise DualEvaluationError("judgment A signature has an invalid type")
        if self.signature is not None and self.signature.signed_payload_sha256 != self.unsigned_sha256():
            raise DualEvaluationError("judgment A signature does not bind its exact unsigned record")

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "blind_to_arm_identity": self.blind_to_arm_identity,
            "canonical_decision_score_sha256": self.canonical_decision_score_sha256,
            "config": self.config.canonical(),
            "evaluator": self.evaluator.canonical(),
            "implementation": self.implementation.canonical(),
            "input": self.input.canonical(),
            "inspect_requirement": self.inspect_requirement,
            "occurrence_uid": self.occurrence_uid,
            "output": self.output.canonical(),
            "scorer": self.scorer.canonical(),
            "schema": SCHEMA,
            "task": self.task.canonical(),
        }

    def unsigned_sha256(self) -> str:
        return canonical_sha256(self.unsigned_canonical())

    def canonical(self) -> dict[str, Any]:
        return {
            **self.unsigned_canonical(),
            "signature": (
                None if self.signature is None else self.signature.canonical()
            ),
        }


@dataclass(frozen=True, slots=True)
class IndependentJudgmentBV1:
    """Externally operated B judgment; its implementation must differ from A."""

    occurrence_uid: str
    evaluator: RoleBindingV1
    implementation: ContentDescriptorV1
    task: ContentDescriptorV1
    scorer: ContentDescriptorV1
    config: ContentDescriptorV1
    input: ContentDescriptorV1
    output: ContentDescriptorV1
    canonical_decision_score_sha256: str
    blind_to_arm_identity: bool
    signature: ExternalSignatureEvidenceV1 | None

    def __post_init__(self) -> None:
        _identifier(self.occurrence_uid, "occurrence_uid")
        if not isinstance(self.evaluator, RoleBindingV1) or self.evaluator.role != "evaluator_b":
            raise DualEvaluationError("judgment B requires an evaluator_b role binding")
        for name in ("implementation", "task", "scorer", "config", "input", "output"):
            _descriptor(getattr(self, name), name)
        _digest(self.canonical_decision_score_sha256, "canonical_decision_score_sha256")
        if self.blind_to_arm_identity is not True:
            raise DualEvaluationError("judgment B must be blind to arm identity")
        if self.signature is not None and not isinstance(self.signature, ExternalSignatureEvidenceV1):
            raise DualEvaluationError("judgment B signature has an invalid type")
        if self.signature is not None and self.signature.signed_payload_sha256 != self.unsigned_sha256():
            raise DualEvaluationError("judgment B signature does not bind its exact unsigned record")

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "blind_to_arm_identity": self.blind_to_arm_identity,
            "canonical_decision_score_sha256": self.canonical_decision_score_sha256,
            "config": self.config.canonical(),
            "evaluator": self.evaluator.canonical(),
            "implementation": self.implementation.canonical(),
            "input": self.input.canonical(),
            "occurrence_uid": self.occurrence_uid,
            "output": self.output.canonical(),
            "scorer": self.scorer.canonical(),
            "schema": SCHEMA,
            "task": self.task.canonical(),
        }

    def unsigned_sha256(self) -> str:
        return canonical_sha256(self.unsigned_canonical())

    def canonical(self) -> dict[str, Any]:
        return {
            **self.unsigned_canonical(),
            "signature": (
                None if self.signature is None else self.signature.canonical()
            ),
        }


@dataclass(frozen=True, slots=True)
class DualEvaluationAssessmentV1:
    terminal: DualEvaluationTerminal
    claim_ceiling: str
    reason: str
    evidence_sha256: str
    binding_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.terminal, DualEvaluationTerminal):
            raise DualEvaluationError("dual evaluation terminal is invalid")
        _digest(self.evidence_sha256, "evidence_sha256")
        _digest(self.binding_sha256, "binding_sha256")
        if not isinstance(self.claim_ceiling, str) or not self.claim_ceiling:
            raise DualEvaluationError("claim_ceiling must be non-empty")
        if not isinstance(self.reason, str) or not self.reason:
            raise DualEvaluationError("reason must be non-empty")

    def canonical(self) -> dict[str, str]:
        return {
            "claim_ceiling": self.claim_ceiling,
            "evidence_sha256": self.evidence_sha256,
            "binding_sha256": self.binding_sha256,
            "reason": self.reason,
            "schema": SCHEMA,
            "terminal": self.terminal.value,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.canonical(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _independent(left: RoleBindingV1, right: RoleBindingV1) -> bool:
    """Require distinct subject, credential, account, issuer, and control domain."""

    return not any(
        getattr(left, field) == getattr(right, field)
        for field in ("subject", "account", "admin_domain", "key_ref", "issuer")
    )


def _evidence_digest(
    judgment_a: InspectJudgmentAV1 | None,
    judgment_b: IndependentJudgmentBV1 | None,
) -> str:
    return canonical_sha256(
        {
            "schema": SCHEMA,
            "judgment_a": None if judgment_a is None else judgment_a.canonical(),
            "judgment_b": None if judgment_b is None else judgment_b.canonical(),
        }
    )


def dual_evaluation_binding_sha256(
    judgment_a: InspectJudgmentAV1 | None,
    judgment_b: IndependentJudgmentBV1 | None,
) -> str:
    """Project the exact fields shared with the central integrity receipts.

    The schema and keys intentionally match
    ``occurrence_integrity.dual_evaluation_binding_sha256``.  This lets the
    completion boundary detect a swapped evaluator, configuration, output, or
    signature carrier without importing one evaluator representation into the
    other.
    """

    def project(
        judgment: InspectJudgmentAV1 | IndependentJudgmentBV1 | None,
    ) -> dict[str, Any] | None:
        if judgment is None or judgment.signature is None:
            return None
        return {
            "blind_to_arm_identity": judgment.blind_to_arm_identity,
            "config": judgment.config.canonical(),
            "implementation": judgment.implementation.canonical(),
            "input": judgment.input.canonical(),
            "occurrence_uid": judgment.occurrence_uid,
            "output": judgment.output.canonical(),
            "role": judgment.evaluator.canonical(),
            "score_sha256": judgment.canonical_decision_score_sha256,
            "scorer": judgment.scorer.canonical(),
            "signature_audit": judgment.signature.verification_receipt.canonical(),
            "signature_receipt": judgment.signature.signed_envelope.canonical(),
            "task": judgment.task.canonical(),
        }

    return canonical_sha256(
        {
            "judgment_a": project(judgment_a),
            "judgment_b": project(judgment_b),
            "schema": "hswm-dual-evaluation-binding/v1",
        }
    )


def assess_dual_evaluation(
    judgment_a: InspectJudgmentAV1 | None,
    judgment_b: IndependentJudgmentBV1 | None,
) -> DualEvaluationAssessmentV1:
    """Fail closed over externally supplied judgments; never execute evaluators."""

    evidence_sha256 = _evidence_digest(judgment_a, judgment_b)
    binding_sha256 = dual_evaluation_binding_sha256(judgment_a, judgment_b)
    if judgment_a is None or judgment_b is None:
        return DualEvaluationAssessmentV1(
            DualEvaluationTerminal.BLOCKED_EXTERNAL,
            CLAIM_CEILING,
            "both externally supplied judgments are required",
            evidence_sha256,
            binding_sha256,
        )
    if judgment_a.occurrence_uid != judgment_b.occurrence_uid:
        return DualEvaluationAssessmentV1(
            DualEvaluationTerminal.VOID_EVALUATOR_DISAGREEMENT,
            CLAIM_CEILING,
            "judgments bind different occurrence UIDs",
            evidence_sha256,
            binding_sha256,
        )
    if not _independent(judgment_a.evaluator, judgment_b.evaluator):
        return DualEvaluationAssessmentV1(
            DualEvaluationTerminal.VOID_EVALUATOR_NONINDEPENDENT,
            CLAIM_CEILING,
            "evaluator roles do not have independent identity and control bindings",
            evidence_sha256,
            binding_sha256,
        )
    if judgment_a.implementation.sha256 == judgment_b.implementation.sha256:
        return DualEvaluationAssessmentV1(
            DualEvaluationTerminal.VOID_EVALUATOR_NONINDEPENDENT,
            CLAIM_CEILING,
            "evaluator implementations are not distinct",
            evidence_sha256,
            binding_sha256,
        )
    if judgment_a.input != judgment_b.input:
        return DualEvaluationAssessmentV1(
            DualEvaluationTerminal.VOID_EVALUATOR_DISAGREEMENT,
            CLAIM_CEILING,
            "judgments do not bind the same exact input descriptor",
            evidence_sha256,
            binding_sha256,
        )
    if judgment_a.canonical_decision_score_sha256 != judgment_b.canonical_decision_score_sha256:
        return DualEvaluationAssessmentV1(
            DualEvaluationTerminal.VOID_EVALUATOR_DISAGREEMENT,
            CLAIM_CEILING,
            "canonical decision/score digests disagree",
            evidence_sha256,
            binding_sha256,
        )
    signatures = (judgment_a.signature, judgment_b.signature)
    if any(signature is None or not signature.cryptographically_verified for signature in signatures):
        return DualEvaluationAssessmentV1(
            DualEvaluationTerminal.BLOCKED_EXTERNAL,
            CLAIM_CEILING,
            "signature evidence is missing or not externally cryptographically verified",
            evidence_sha256,
            binding_sha256,
        )
    return DualEvaluationAssessmentV1(
        DualEvaluationTerminal.SEALED_CANDIDATE_REQUIRES_EXTERNAL_SIGNATURE_AUDIT,
        CLAIM_CEILING,
        "exact blinded agreement is only a candidate pending independent signature audit",
        evidence_sha256,
        binding_sha256,
    )


__all__ = [
    "CLAIM_CEILING",
    "SCHEMA",
    "DualEvaluationAssessmentV1",
    "DualEvaluationError",
    "DualEvaluationTerminal",
    "ExternalSignatureEvidenceV1",
    "IndependentJudgmentBV1",
    "InspectJudgmentAV1",
    "assess_dual_evaluation",
    "dual_evaluation_binding_sha256",
]
