"""Fail-closed bridge from LLM token trajectories to HSWM macro-learning.

Token counts and transcripts are observations, not learning.  This module binds
content-addressed, pre-outcome LLM trajectories to the existing HSWM
eligibility, external-outcome, weight-candidate, and CAS-activation contracts.
Only a durable update with separate causal and removal evidence may support a
claim that HSWM learned a coordination rule.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Literal

from hswm_weight_snapshot import WeightCandidateV1, canonical_sha256
from hswm_weight_store import (
    ACTIVATION_RECEIPT_SCHEMA_VERSION,
    ActivationReceiptV1,
)
from p1_eligibility_tag import (
    ActivationTraceV1,
    EligibilityTagV1,
    make_activation_trace,
)
from p1_m_commit import OutcomeReceiptV1


TRAJECTORY_SCHEMA_VERSION = "hswm-token-trajectory/v1"
LEARNING_RECEIPT_SCHEMA_VERSION = "hswm-token-learning-receipt/v1"
EvidenceLevel = Literal[
    "OBSERVED_ONLY",
    "CANDIDATE_ONLY",
    "DURABLE_UPDATE",
    "CAUSALLY_VALIDATED",
]
DecisionKind = Literal[
    "SPAWN",
    "DELEGATE",
    "COMMUNICATE",
    "TOOL_USE",
    "AGGREGATE",
    "STOP",
    "TASK_ACTION",
]
DECISION_KINDS: tuple[DecisionKind, ...] = (
    "SPAWN",
    "DELEGATE",
    "COMMUNICATE",
    "TOOL_USE",
    "AGGREGATE",
    "STOP",
    "TASK_ACTION",
)


class TokenLearningContractError(ValueError):
    """A token trajectory or learning receipt violates causal ordering."""


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise TokenLearningContractError(f"{label} must be non-empty text")
    return value


def _sha(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise TokenLearningContractError(f"{label} must be a lowercase SHA-256")
    return value


def _positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise TokenLearningContractError(f"{label} must be a positive integer")
    return value


def _positive_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TokenLearningContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise TokenLearningContractError(f"{label} must be finite and positive")
    return result


@dataclass(frozen=True)
class TokenTrajectoryV1:
    """Content-addressed LLM activity sealed before its outcome is known.

    Raw prompts and responses are deliberately absent.  Their digests preserve
    identity without turning a possibly sensitive transcript archive into a
    falsely labelled learning mechanism.
    """

    trajectory_id: str
    episode_id: str
    function_id: str
    decision_kind: DecisionKind
    parent_trajectory_ids: tuple[str, ...]
    model_revision_sha256: str
    function_registry_sha256: str
    snapshot_id: str
    input_sha256: str
    output_sha256: str
    input_token_count: int
    output_token_count: int
    external_action_sha256: str
    tool_receipt_sha256s: tuple[str, ...]
    used_edge_ids: tuple[str, ...]
    raw_contribution: float
    pre_outcome_seal_sha256: str
    schema_version: str = TRAJECTORY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _sha(self.trajectory_id, "trajectory_id")
        _text(self.episode_id, "episode_id")
        _text(self.function_id, "function_id")
        if self.decision_kind not in DECISION_KINDS:
            raise TokenLearningContractError("unknown orchestration decision kind")
        parents = tuple(sorted(self.parent_trajectory_ids))
        if len(set(parents)) != len(parents):
            raise TokenLearningContractError("parent trajectories must be unique")
        for parent in parents:
            _sha(parent, "parent_trajectory_id")
        object.__setattr__(self, "parent_trajectory_ids", parents)
        for label in (
            "model_revision_sha256",
            "function_registry_sha256",
            "snapshot_id",
            "input_sha256",
            "output_sha256",
            "external_action_sha256",
            "pre_outcome_seal_sha256",
        ):
            _sha(getattr(self, label), label)
        _positive_int(self.input_token_count, "input_token_count")
        _positive_int(self.output_token_count, "output_token_count")
        tool_receipts = tuple(self.tool_receipt_sha256s)
        if len(set(tool_receipts)) != len(tool_receipts):
            raise TokenLearningContractError("tool receipts must be unique")
        for receipt in tool_receipts:
            _sha(receipt, "tool_receipt_sha256")
        object.__setattr__(self, "tool_receipt_sha256s", tool_receipts)
        edges = tuple(sorted(self.used_edge_ids))
        if not edges or len(set(edges)) != len(edges):
            raise TokenLearningContractError("used_edge_ids must be non-empty and unique")
        if any(not isinstance(edge, str) or not edge for edge in edges):
            raise TokenLearningContractError("used_edge_ids must contain non-empty text")
        object.__setattr__(self, "used_edge_ids", edges)
        object.__setattr__(
            self,
            "raw_contribution",
            _positive_float(self.raw_contribution, "raw_contribution"),
        )
        if self.schema_version != TRAJECTORY_SCHEMA_VERSION:
            raise TokenLearningContractError("unsupported token trajectory schema")
        if self.trajectory_id != canonical_sha256(self.unsigned()):
            raise TokenLearningContractError("trajectory_id does not match canonical trajectory")

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "function_id": self.function_id,
            "decision_kind": self.decision_kind,
            "parent_trajectory_ids": list(self.parent_trajectory_ids),
            "model_revision_sha256": self.model_revision_sha256,
            "function_registry_sha256": self.function_registry_sha256,
            "snapshot_id": self.snapshot_id,
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
            "input_token_count": self.input_token_count,
            "output_token_count": self.output_token_count,
            "external_action_sha256": self.external_action_sha256,
            "tool_receipt_sha256s": list(self.tool_receipt_sha256s),
            "used_edge_ids": list(self.used_edge_ids),
            "raw_contribution": self.raw_contribution,
            "pre_outcome_seal_sha256": self.pre_outcome_seal_sha256,
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "trajectory_id": self.trajectory_id}

    def activation_trace(self) -> ActivationTraceV1:
        """Project this sealed trajectory into the existing eligibility core."""

        return make_activation_trace(
            episode_id=self.episode_id,
            question_id=self.trajectory_id,
            query_sha256=self.input_sha256,
            snapshot_id=self.snapshot_id,
            target_id=f"llm-function:{self.function_id}",
            edge_ids=self.used_edge_ids,
            raw_contribution=self.raw_contribution,
        )


def make_token_trajectory(
    *,
    episode_id: str,
    function_id: str,
    decision_kind: DecisionKind,
    parent_trajectory_ids: Iterable[str] = (),
    model_revision_sha256: str,
    function_registry_sha256: str,
    snapshot_id: str,
    input_sha256: str,
    output_sha256: str,
    input_token_count: int,
    output_token_count: int,
    external_action_sha256: str,
    tool_receipt_sha256s: Iterable[str] = (),
    used_edge_ids: Iterable[str],
    raw_contribution: float,
    pre_outcome_seal_sha256: str,
) -> TokenTrajectoryV1:
    unsigned = {
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
        "episode_id": _text(episode_id, "episode_id"),
        "function_id": _text(function_id, "function_id"),
        "decision_kind": decision_kind,
        "parent_trajectory_ids": sorted(parent_trajectory_ids),
        "model_revision_sha256": _sha(model_revision_sha256, "model_revision_sha256"),
        "function_registry_sha256": _sha(
            function_registry_sha256, "function_registry_sha256"
        ),
        "snapshot_id": _sha(snapshot_id, "snapshot_id"),
        "input_sha256": _sha(input_sha256, "input_sha256"),
        "output_sha256": _sha(output_sha256, "output_sha256"),
        "input_token_count": _positive_int(input_token_count, "input_token_count"),
        "output_token_count": _positive_int(output_token_count, "output_token_count"),
        "external_action_sha256": _sha(
            external_action_sha256, "external_action_sha256"
        ),
        "tool_receipt_sha256s": list(tool_receipt_sha256s),
        "used_edge_ids": sorted(used_edge_ids),
        "raw_contribution": _positive_float(raw_contribution, "raw_contribution"),
        "pre_outcome_seal_sha256": _sha(
            pre_outcome_seal_sha256, "pre_outcome_seal_sha256"
        ),
    }
    return TokenTrajectoryV1(
        trajectory_id=canonical_sha256(unsigned),
        **{key: value for key, value in unsigned.items() if key != "schema_version"},
    )


@dataclass(frozen=True)
class TokenLearningReceiptV1:
    receipt_id: str
    episode_id: str
    snapshot_id: str
    trajectory_ids: tuple[str, ...]
    activation_trace_ids: tuple[str, ...]
    eligibility_tag_ids: tuple[str, ...]
    outcome_receipt_id: str
    candidate_id: str | None
    activation_receipt_id: str | None
    active_snapshot_id: str | None
    causal_evaluation_receipt_sha256: str | None
    fixed_context_replay_receipt_sha256: str | None
    matched_budget_receipt_sha256: str | None
    removal_ablation_receipt_sha256: str | None
    evidence_level: EvidenceLevel
    schema_version: str = LEARNING_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _sha(self.receipt_id, "receipt_id")
        _text(self.episode_id, "episode_id")
        _sha(self.snapshot_id, "snapshot_id")
        for label, values in (
            ("trajectory_ids", self.trajectory_ids),
            ("activation_trace_ids", self.activation_trace_ids),
            ("eligibility_tag_ids", self.eligibility_tag_ids),
        ):
            normalized = tuple(sorted(values))
            if not normalized or len(set(normalized)) != len(normalized):
                raise TokenLearningContractError(f"{label} must be non-empty and unique")
            for value in normalized:
                _sha(value, label)
            object.__setattr__(self, label, normalized)
        _sha(self.outcome_receipt_id, "outcome_receipt_id")
        for label in (
            "candidate_id",
            "activation_receipt_id",
            "active_snapshot_id",
            "causal_evaluation_receipt_sha256",
            "fixed_context_replay_receipt_sha256",
            "matched_budget_receipt_sha256",
            "removal_ablation_receipt_sha256",
        ):
            value = getattr(self, label)
            if value is not None:
                _sha(value, label)
        if self.evidence_level not in {
            "OBSERVED_ONLY",
            "CANDIDATE_ONLY",
            "DURABLE_UPDATE",
            "CAUSALLY_VALIDATED",
        }:
            raise TokenLearningContractError("unknown evidence level")
        if self.schema_version != LEARNING_RECEIPT_SCHEMA_VERSION:
            raise TokenLearningContractError("unsupported token learning receipt schema")
        if self.receipt_id != canonical_sha256(self.unsigned()):
            raise TokenLearningContractError("learning receipt digest mismatch")

    @property
    def supports_learned_coordination_claim(self) -> bool:
        return self.evidence_level == "CAUSALLY_VALIDATED"

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "snapshot_id": self.snapshot_id,
            "trajectory_ids": list(self.trajectory_ids),
            "activation_trace_ids": list(self.activation_trace_ids),
            "eligibility_tag_ids": list(self.eligibility_tag_ids),
            "outcome_receipt_id": self.outcome_receipt_id,
            "candidate_id": self.candidate_id,
            "activation_receipt_id": self.activation_receipt_id,
            "active_snapshot_id": self.active_snapshot_id,
            "causal_evaluation_receipt_sha256": self.causal_evaluation_receipt_sha256,
            "fixed_context_replay_receipt_sha256": self.fixed_context_replay_receipt_sha256,
            "matched_budget_receipt_sha256": self.matched_budget_receipt_sha256,
            "removal_ablation_receipt_sha256": self.removal_ablation_receipt_sha256,
            "evidence_level": self.evidence_level,
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "receipt_id": self.receipt_id}


def _validate_activation_receipt(receipt: ActivationReceiptV1) -> None:
    if receipt.schema_version != ACTIVATION_RECEIPT_SCHEMA_VERSION:
        raise TokenLearningContractError("unsupported activation receipt schema")
    if receipt.receipt_id != canonical_sha256(receipt.unsigned()):
        raise TokenLearningContractError("activation receipt digest mismatch")


def _validate_trajectory_graph(trajectories: tuple[TokenTrajectoryV1, ...]) -> None:
    by_id = {item.trajectory_id: item for item in trajectories}
    for item in trajectories:
        if item.trajectory_id in item.parent_trajectory_ids:
            raise TokenLearningContractError("trajectory cannot parent itself")
        if not set(item.parent_trajectory_ids) <= by_id.keys():
            raise TokenLearningContractError(
                "parent trajectory is outside the sealed episode graph"
            )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(trajectory_id: str) -> None:
        if trajectory_id in visiting:
            raise TokenLearningContractError("trajectory graph contains a cycle")
        if trajectory_id in visited:
            return
        visiting.add(trajectory_id)
        for parent_id in by_id[trajectory_id].parent_trajectory_ids:
            visit(parent_id)
        visiting.remove(trajectory_id)
        visited.add(trajectory_id)

    for trajectory_id in sorted(by_id):
        visit(trajectory_id)


def make_token_learning_receipt(
    trajectories: Iterable[TokenTrajectoryV1],
    tags: Iterable[EligibilityTagV1],
    *,
    outcome: OutcomeReceiptV1,
    candidate: WeightCandidateV1 | None = None,
    activation: ActivationReceiptV1 | None = None,
    causal_evaluation_receipt_sha256: str | None = None,
    fixed_context_replay_receipt_sha256: str | None = None,
    matched_budget_receipt_sha256: str | None = None,
    removal_ablation_receipt_sha256: str | None = None,
) -> TokenLearningReceiptV1:
    """Bind the causal chain and classify its strongest honest evidence level."""

    trajectory_tuple = tuple(trajectories)
    tag_tuple = tuple(tags)
    if not trajectory_tuple or any(
        not isinstance(item, TokenTrajectoryV1) for item in trajectory_tuple
    ):
        raise TokenLearningContractError("trajectories must contain TokenTrajectoryV1")
    if not tag_tuple or any(not isinstance(item, EligibilityTagV1) for item in tag_tuple):
        raise TokenLearningContractError("tags must contain EligibilityTagV1")
    if len({item.trajectory_id for item in trajectory_tuple}) != len(trajectory_tuple):
        raise TokenLearningContractError("trajectories must be unique")
    _validate_trajectory_graph(trajectory_tuple)
    episode_ids = {item.episode_id for item in trajectory_tuple}
    snapshot_ids = {item.snapshot_id for item in trajectory_tuple}
    if len(episode_ids) != 1 or len(snapshot_ids) != 1:
        raise TokenLearningContractError("one receipt must bind one episode and snapshot")
    episode_id = next(iter(episode_ids))
    snapshot_id = next(iter(snapshot_ids))
    if outcome.episode_id != episode_id:
        raise TokenLearningContractError("outcome belongs to a different episode")

    traces = tuple(item.activation_trace() for item in trajectory_tuple)
    trace_ids = {trace.trace_id for trace in traces}
    tag_sources: set[str] = set()
    for tag in tag_tuple:
        if tag.episode_id != episode_id or tag.snapshot_id != snapshot_id:
            raise TokenLearningContractError("eligibility tag crosses episode or snapshot")
        if not set(tag.source_trace_ids) <= trace_ids:
            raise TokenLearningContractError("eligibility tag cites an unbound trace")
        tag_sources.update(tag.source_trace_ids)
    if tag_sources != trace_ids:
        raise TokenLearningContractError("every trajectory must contribute to eligibility")

    candidate_id = None
    if candidate is not None:
        if candidate.base_snapshot_id != snapshot_id:
            raise TokenLearningContractError("candidate targets a different snapshot")
        tag_ids = {tag.tag_id for tag in tag_tuple}
        delta_tag_ids = {delta.eligibility_tag_sha256 for delta in candidate.deltas}
        if not delta_tag_ids <= tag_ids:
            raise TokenLearningContractError("candidate delta cites an unbound eligibility tag")
        candidate_id = candidate.candidate_id

    if activation is not None:
        if candidate is None:
            raise TokenLearningContractError("activation requires a bound candidate")
        _validate_activation_receipt(activation)
        if (
            activation.candidate_id != candidate.candidate_id
            or activation.base_snapshot_id != snapshot_id
        ):
            raise TokenLearningContractError("activation does not bind the candidate base")

    causal_bundle = (
        causal_evaluation_receipt_sha256,
        fixed_context_replay_receipt_sha256,
        matched_budget_receipt_sha256,
        removal_ablation_receipt_sha256,
    )
    if any(value is None for value in causal_bundle) and any(
        value is not None for value in causal_bundle
    ):
        raise TokenLearningContractError(
            "causal evaluation, fixed-context replay, matched-budget, and removal "
            "receipts are an inseparable bundle"
        )
    if causal_bundle[0] is not None:
        if activation is None:
            raise TokenLearningContractError("causal evidence requires a durable activation")
        for label, value in zip(
            (
                "causal_evaluation_receipt_sha256",
                "fixed_context_replay_receipt_sha256",
                "matched_budget_receipt_sha256",
                "removal_ablation_receipt_sha256",
            ),
            causal_bundle,
        ):
            _sha(value, label)

    if causal_bundle[0] is not None:
        evidence_level: EvidenceLevel = "CAUSALLY_VALIDATED"
    elif activation is not None:
        evidence_level = "DURABLE_UPDATE"
    elif candidate is not None:
        evidence_level = "CANDIDATE_ONLY"
    else:
        evidence_level = "OBSERVED_ONLY"

    unsigned = {
        "schema_version": LEARNING_RECEIPT_SCHEMA_VERSION,
        "episode_id": episode_id,
        "snapshot_id": snapshot_id,
        "trajectory_ids": sorted(item.trajectory_id for item in trajectory_tuple),
        "activation_trace_ids": sorted(trace_ids),
        "eligibility_tag_ids": sorted(tag.tag_id for tag in tag_tuple),
        "outcome_receipt_id": outcome.receipt_id,
        "candidate_id": candidate_id,
        "activation_receipt_id": None if activation is None else activation.receipt_id,
        "active_snapshot_id": None if activation is None else activation.active_snapshot_id,
        "causal_evaluation_receipt_sha256": causal_bundle[0],
        "fixed_context_replay_receipt_sha256": causal_bundle[1],
        "matched_budget_receipt_sha256": causal_bundle[2],
        "removal_ablation_receipt_sha256": causal_bundle[3],
        "evidence_level": evidence_level,
    }
    return TokenLearningReceiptV1(
        receipt_id=canonical_sha256(unsigned),
        **{key: value for key, value in unsigned.items() if key != "schema_version"},
    )


__all__ = [
    "DECISION_KINDS",
    "DecisionKind",
    "EvidenceLevel",
    "LEARNING_RECEIPT_SCHEMA_VERSION",
    "TRAJECTORY_SCHEMA_VERSION",
    "TokenLearningContractError",
    "TokenLearningReceiptV1",
    "TokenTrajectoryV1",
    "make_token_learning_receipt",
    "make_token_trajectory",
]
