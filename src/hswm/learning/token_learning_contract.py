"""Minimal bridge from sealed LLM activity to durable HSWM learning.

The default contract keeps only the causal spine:
trajectory -> eligibility -> external outcome -> activated weight -> causal test.
Raw token storage and unactivated candidates are not learning receipts.  A
single content-addressed causal-test receipt owns replay, equal-budget, and
removal checks instead of forcing four independent governance artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from hswm_weight_snapshot import WeightCandidateV1, canonical_sha256
from hswm_weight_store import ACTIVATION_RECEIPT_SCHEMA_VERSION, ActivationReceiptV1
from p1_eligibility_tag import EligibilityTagV1, make_activation_trace
from p1_m_commit import OutcomeReceiptV1


TRAJECTORY_SCHEMA_VERSION = "hswm-token-trajectory/v2"
LEARNING_RECEIPT_SCHEMA_VERSION = "hswm-token-learning-receipt/v2"
EvidenceLevel = Literal["OBSERVED_ONLY", "DURABLE_UPDATE", "CAUSALLY_VALIDATED"]
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
    """A token trajectory or learning receipt breaks the causal spine."""


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


@dataclass(frozen=True)
class TokenTrajectoryV2:
    """Minimal, content-addressed LLM activity sealed before its outcome."""

    trajectory_id: str
    episode_id: str
    function_id: str
    decision_kind: DecisionKind
    parent_trajectory_ids: tuple[str, ...]
    model_context_sha256: str
    snapshot_id: str
    input_sha256: str
    output_sha256: str
    token_count: int
    action_sha256: str
    used_edge_ids: tuple[str, ...]
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
            "model_context_sha256",
            "snapshot_id",
            "input_sha256",
            "output_sha256",
            "action_sha256",
            "pre_outcome_seal_sha256",
        ):
            _sha(getattr(self, label), label)
        _positive_int(self.token_count, "token_count")
        edges = tuple(sorted(self.used_edge_ids))
        if not edges or len(set(edges)) != len(edges):
            raise TokenLearningContractError("used_edge_ids must be non-empty and unique")
        if any(not isinstance(edge, str) or not edge for edge in edges):
            raise TokenLearningContractError("used_edge_ids must contain non-empty text")
        object.__setattr__(self, "used_edge_ids", edges)
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
            "model_context_sha256": self.model_context_sha256,
            "snapshot_id": self.snapshot_id,
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
            "token_count": self.token_count,
            "action_sha256": self.action_sha256,
            "used_edge_ids": list(self.used_edge_ids),
            "pre_outcome_seal_sha256": self.pre_outcome_seal_sha256,
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "trajectory_id": self.trajectory_id}

    def activation_trace(self):
        return make_activation_trace(
            episode_id=self.episode_id,
            question_id=self.trajectory_id,
            query_sha256=self.input_sha256,
            snapshot_id=self.snapshot_id,
            target_id=f"llm-function:{self.function_id}",
            edge_ids=self.used_edge_ids,
            raw_contribution=1.0,
        )


def make_token_trajectory(
    *,
    episode_id: str,
    function_id: str,
    decision_kind: DecisionKind,
    model_context_sha256: str,
    snapshot_id: str,
    input_sha256: str,
    output_sha256: str,
    token_count: int,
    action_sha256: str,
    used_edge_ids: Iterable[str],
    pre_outcome_seal_sha256: str,
    parent_trajectory_ids: Iterable[str] = (),
) -> TokenTrajectoryV2:
    unsigned = {
        "schema_version": TRAJECTORY_SCHEMA_VERSION,
        "episode_id": _text(episode_id, "episode_id"),
        "function_id": _text(function_id, "function_id"),
        "decision_kind": decision_kind,
        "parent_trajectory_ids": sorted(parent_trajectory_ids),
        "model_context_sha256": _sha(model_context_sha256, "model_context_sha256"),
        "snapshot_id": _sha(snapshot_id, "snapshot_id"),
        "input_sha256": _sha(input_sha256, "input_sha256"),
        "output_sha256": _sha(output_sha256, "output_sha256"),
        "token_count": _positive_int(token_count, "token_count"),
        "action_sha256": _sha(action_sha256, "action_sha256"),
        "used_edge_ids": sorted(used_edge_ids),
        "pre_outcome_seal_sha256": _sha(
            pre_outcome_seal_sha256, "pre_outcome_seal_sha256"
        ),
    }
    return TokenTrajectoryV2(
        trajectory_id=canonical_sha256(unsigned),
        **{key: value for key, value in unsigned.items() if key != "schema_version"},
    )


@dataclass(frozen=True)
class TokenLearningReceiptV2:
    receipt_id: str
    episode_id: str
    snapshot_id: str
    trajectory_ids: tuple[str, ...]
    eligibility_tag_ids: tuple[str, ...]
    outcome_receipt_id: str
    activation_receipt_id: str | None
    active_snapshot_id: str | None
    causal_test_receipt_sha256: str | None
    evidence_level: EvidenceLevel
    schema_version: str = LEARNING_RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _sha(self.receipt_id, "receipt_id")
        _text(self.episode_id, "episode_id")
        _sha(self.snapshot_id, "snapshot_id")
        for label in ("trajectory_ids", "eligibility_tag_ids"):
            values = tuple(sorted(getattr(self, label)))
            if not values or len(set(values)) != len(values):
                raise TokenLearningContractError(f"{label} must be non-empty and unique")
            for value in values:
                _sha(value, label)
            object.__setattr__(self, label, values)
        _sha(self.outcome_receipt_id, "outcome_receipt_id")
        for label in (
            "activation_receipt_id",
            "active_snapshot_id",
            "causal_test_receipt_sha256",
        ):
            value = getattr(self, label)
            if value is not None:
                _sha(value, label)
        if (self.activation_receipt_id is None) != (self.active_snapshot_id is None):
            raise TokenLearningContractError("activation receipt and snapshot must travel together")
        if self.causal_test_receipt_sha256 is not None and self.activation_receipt_id is None:
            raise TokenLearningContractError("causal evidence requires durable activation")
        if self.evidence_level not in {
            "OBSERVED_ONLY",
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
            "eligibility_tag_ids": list(self.eligibility_tag_ids),
            "outcome_receipt_id": self.outcome_receipt_id,
            "activation_receipt_id": self.activation_receipt_id,
            "active_snapshot_id": self.active_snapshot_id,
            "causal_test_receipt_sha256": self.causal_test_receipt_sha256,
            "evidence_level": self.evidence_level,
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "receipt_id": self.receipt_id}


def _validate_trajectory_graph(trajectories: tuple[TokenTrajectoryV2, ...]) -> None:
    by_id = {item.trajectory_id: item for item in trajectories}
    remaining = set(by_id)
    resolved: set[str] = set()
    while remaining:
        ready = {
            item_id
            for item_id in remaining
            if set(by_id[item_id].parent_trajectory_ids) <= resolved
        }
        if not ready:
            outside = any(
                not set(by_id[item_id].parent_trajectory_ids) <= by_id.keys()
                for item_id in remaining
            )
            message = (
                "parent trajectory is outside the sealed episode graph"
                if outside
                else "trajectory graph contains a cycle"
            )
            raise TokenLearningContractError(message)
        remaining -= ready
        resolved |= ready


def _validate_activation(receipt: ActivationReceiptV1) -> None:
    if receipt.schema_version != ACTIVATION_RECEIPT_SCHEMA_VERSION:
        raise TokenLearningContractError("unsupported activation receipt schema")
    if receipt.receipt_id != canonical_sha256(receipt.unsigned()):
        raise TokenLearningContractError("activation receipt digest mismatch")


def make_token_learning_receipt(
    trajectories: Iterable[TokenTrajectoryV2],
    tags: Iterable[EligibilityTagV1],
    *,
    outcome: OutcomeReceiptV1,
    candidate: WeightCandidateV1 | None = None,
    activation: ActivationReceiptV1 | None = None,
    causal_test_receipt_sha256: str | None = None,
) -> TokenLearningReceiptV2:
    """Bind one causal spine; reject candidates that were never activated."""

    trajectories = tuple(trajectories)
    tags = tuple(tags)
    if not trajectories or any(not isinstance(item, TokenTrajectoryV2) for item in trajectories):
        raise TokenLearningContractError("trajectories must contain TokenTrajectoryV2")
    if not tags or any(not isinstance(item, EligibilityTagV1) for item in tags):
        raise TokenLearningContractError("tags must contain EligibilityTagV1")
    if len({item.trajectory_id for item in trajectories}) != len(trajectories):
        raise TokenLearningContractError("trajectories must be unique")
    _validate_trajectory_graph(trajectories)

    episode_ids = {item.episode_id for item in trajectories}
    snapshot_ids = {item.snapshot_id for item in trajectories}
    if len(episode_ids) != 1 or len(snapshot_ids) != 1:
        raise TokenLearningContractError("one receipt must bind one episode and snapshot")
    episode_id = next(iter(episode_ids))
    snapshot_id = next(iter(snapshot_ids))
    if outcome.episode_id != episode_id:
        raise TokenLearningContractError("outcome belongs to a different episode")

    traces = tuple(item.activation_trace() for item in trajectories)
    trace_ids = {trace.trace_id for trace in traces}
    tag_sources: set[str] = set()
    for tag in tags:
        if tag.episode_id != episode_id or tag.snapshot_id != snapshot_id:
            raise TokenLearningContractError("eligibility tag crosses episode or snapshot")
        if not set(tag.source_trace_ids) <= trace_ids:
            raise TokenLearningContractError("eligibility tag cites an unbound trace")
        tag_sources.update(tag.source_trace_ids)
    if tag_sources != trace_ids:
        raise TokenLearningContractError("every trajectory must contribute to eligibility")

    if (candidate is None) != (activation is None):
        raise TokenLearningContractError(
            "candidate and durable activation must travel together; candidate-only is not learning"
        )
    if candidate is not None and activation is not None:
        if candidate.base_snapshot_id != snapshot_id:
            raise TokenLearningContractError("candidate targets a different snapshot")
        tag_ids = {tag.tag_id for tag in tags}
        if not {delta.eligibility_tag_sha256 for delta in candidate.deltas} <= tag_ids:
            raise TokenLearningContractError("candidate delta cites an unbound eligibility tag")
        _validate_activation(activation)
        if (
            activation.candidate_id != candidate.candidate_id
            or activation.base_snapshot_id != snapshot_id
        ):
            raise TokenLearningContractError("activation does not bind the candidate base")

    if causal_test_receipt_sha256 is not None:
        _sha(causal_test_receipt_sha256, "causal_test_receipt_sha256")
        if activation is None:
            raise TokenLearningContractError("causal evidence requires durable activation")
        evidence_level: EvidenceLevel = "CAUSALLY_VALIDATED"
    elif activation is not None:
        evidence_level = "DURABLE_UPDATE"
    else:
        evidence_level = "OBSERVED_ONLY"

    unsigned = {
        "schema_version": LEARNING_RECEIPT_SCHEMA_VERSION,
        "episode_id": episode_id,
        "snapshot_id": snapshot_id,
        "trajectory_ids": sorted(item.trajectory_id for item in trajectories),
        "eligibility_tag_ids": sorted(tag.tag_id for tag in tags),
        "outcome_receipt_id": outcome.receipt_id,
        "activation_receipt_id": None if activation is None else activation.receipt_id,
        "active_snapshot_id": None if activation is None else activation.active_snapshot_id,
        "causal_test_receipt_sha256": causal_test_receipt_sha256,
        "evidence_level": evidence_level,
    }
    return TokenLearningReceiptV2(
        receipt_id=canonical_sha256(unsigned),
        **{key: value for key, value in unsigned.items() if key != "schema_version"},
    )


# Short compatibility aliases for callers that imported the one-day-old V1 names.
TokenTrajectoryV1 = TokenTrajectoryV2
TokenLearningReceiptV1 = TokenLearningReceiptV2

__all__ = [
    "DECISION_KINDS",
    "DecisionKind",
    "EvidenceLevel",
    "LEARNING_RECEIPT_SCHEMA_VERSION",
    "TRAJECTORY_SCHEMA_VERSION",
    "TokenLearningContractError",
    "TokenLearningReceiptV1",
    "TokenLearningReceiptV2",
    "TokenTrajectoryV1",
    "TokenTrajectoryV2",
    "make_token_learning_receipt",
    "make_token_trajectory",
]
