"""Deterministic episode-indexed eligibility tags for HSWM P1.

Retrieval emits immutable activation traces.  After the sealed environment has
identified the winning traces, this module converts their contribution into a
normalized per-edge credit assignment.  There is deliberately no wall clock,
decay, model call, persistence, or active-weight mutation here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from hswm_weight_snapshot import canonical_sha256


TRACE_SCHEMA_VERSION = "hswm-p1-activation-trace/v1"
TAG_SCHEMA_VERSION = "hswm-p1-eligibility-tag/v1"


class EligibilityContractError(ValueError):
    """An activation trace or eligibility tag violates the P1 contract."""


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise EligibilityContractError(f"{label} must be non-empty text")
    return value


def _sha(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise EligibilityContractError(f"{label} must be a lowercase SHA-256")
    return value


def _positive(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EligibilityContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise EligibilityContractError(f"{label} must be finite and positive")
    return result


@dataclass(frozen=True)
class ActivationTraceV1:
    trace_id: str
    episode_id: str
    question_id: str
    query_sha256: str
    snapshot_id: str
    target_id: str
    edge_ids: tuple[str, ...]
    raw_contribution: float
    schema_version: str = TRACE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _sha(self.trace_id, "trace_id")
        _text(self.episode_id, "episode_id")
        _text(self.question_id, "question_id")
        _sha(self.query_sha256, "query_sha256")
        _sha(self.snapshot_id, "snapshot_id")
        _text(self.target_id, "target_id")
        normalized_edges = tuple(self.edge_ids)
        if not normalized_edges or any(
            not isinstance(edge, str) or not edge for edge in normalized_edges
        ):
            raise EligibilityContractError("edge_ids must be non-empty text values")
        if len(set(normalized_edges)) != len(normalized_edges):
            raise EligibilityContractError("a trace cannot repeat an edge")
        object.__setattr__(self, "edge_ids", normalized_edges)
        object.__setattr__(
            self,
            "raw_contribution",
            _positive(self.raw_contribution, "raw_contribution"),
        )
        if self.schema_version != TRACE_SCHEMA_VERSION:
            raise EligibilityContractError("unsupported activation trace schema")
        if self.trace_id != canonical_sha256(self.unsigned()):
            raise EligibilityContractError("trace_id does not match canonical trace")

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "question_id": self.question_id,
            "query_sha256": self.query_sha256,
            "snapshot_id": self.snapshot_id,
            "target_id": self.target_id,
            "edge_ids": list(self.edge_ids),
            "raw_contribution": self.raw_contribution,
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "trace_id": self.trace_id}


def make_activation_trace(
    *,
    episode_id: str,
    question_id: str,
    query_sha256: str,
    snapshot_id: str,
    target_id: str,
    edge_ids: Iterable[str],
    raw_contribution: float,
) -> ActivationTraceV1:
    unsigned = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "episode_id": _text(episode_id, "episode_id"),
        "question_id": _text(question_id, "question_id"),
        "query_sha256": _sha(query_sha256, "query_sha256"),
        "snapshot_id": _sha(snapshot_id, "snapshot_id"),
        "target_id": _text(target_id, "target_id"),
        "edge_ids": list(edge_ids),
        "raw_contribution": _positive(raw_contribution, "raw_contribution"),
    }
    return ActivationTraceV1(trace_id=canonical_sha256(unsigned), **{
        key: value for key, value in unsigned.items() if key != "schema_version"
    })


@dataclass(frozen=True, order=True)
class EligibilityTagV1:
    edge_id: str
    tag_strength: float
    episode_id: str
    snapshot_id: str
    source_trace_ids: tuple[str, ...]
    tag_id: str
    schema_version: str = TAG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _text(self.edge_id, "edge_id")
        strength = _positive(self.tag_strength, "tag_strength")
        if strength > 1.0:
            raise EligibilityContractError("tag_strength must be <= 1")
        object.__setattr__(self, "tag_strength", strength)
        _text(self.episode_id, "episode_id")
        _sha(self.snapshot_id, "snapshot_id")
        normalized = tuple(sorted(self.source_trace_ids))
        if not normalized or len(set(normalized)) != len(normalized):
            raise EligibilityContractError("source_trace_ids must be non-empty and unique")
        for trace_id in normalized:
            _sha(trace_id, "source_trace_id")
        object.__setattr__(self, "source_trace_ids", normalized)
        _sha(self.tag_id, "tag_id")
        if self.schema_version != TAG_SCHEMA_VERSION:
            raise EligibilityContractError("unsupported eligibility tag schema")
        if self.tag_id != canonical_sha256(self.unsigned()):
            raise EligibilityContractError("tag_id does not match canonical tag")

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "edge_id": self.edge_id,
            "tag_strength": self.tag_strength,
            "episode_id": self.episode_id,
            "snapshot_id": self.snapshot_id,
            "source_trace_ids": list(self.source_trace_ids),
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "tag_id": self.tag_id}


def derive_eligibility_tags(
    episode_id: str, winning_traces: Iterable[ActivationTraceV1]
) -> tuple[EligibilityTagV1, ...]:
    """Normalize best-trace contribution over edges; returned strengths sum to 1."""

    traces = tuple(winning_traces)
    if not traces:
        return ()
    if any(not isinstance(trace, ActivationTraceV1) for trace in traces):
        raise EligibilityContractError("winning_traces must contain ActivationTraceV1")
    if any(trace.episode_id != episode_id for trace in traces):
        raise EligibilityContractError("winning trace belongs to a different episode")
    if len({trace.trace_id for trace in traces}) != len(traces):
        raise EligibilityContractError("winning traces must be unique")
    snapshot_ids = {trace.snapshot_id for trace in traces}
    if len(snapshot_ids) != 1:
        raise EligibilityContractError("one tag batch must bind one weight snapshot")

    edge_credit: dict[str, float] = {}
    edge_traces: dict[str, set[str]] = {}
    for trace in traces:
        share = trace.raw_contribution / len(trace.edge_ids)
        for edge_id in trace.edge_ids:
            edge_credit[edge_id] = edge_credit.get(edge_id, 0.0) + share
            edge_traces.setdefault(edge_id, set()).add(trace.trace_id)
    total = math.fsum(edge_credit.values())
    if not math.isfinite(total) or total <= 0.0:
        raise EligibilityContractError("eligibility credit total must be positive")

    strengths = {edge_id: credit / total for edge_id, credit in edge_credit.items()}
    # Force exact normalization onto the lexicographically final edge so the
    # candidate's total tagged budget is deterministic across runtimes.
    final_edge = sorted(strengths)[-1]
    strengths[final_edge] = 1.0 - math.fsum(
        strength for edge_id, strength in strengths.items() if edge_id != final_edge
    )

    tags = []
    snapshot_id = next(iter(snapshot_ids))
    for edge_id in sorted(strengths):
        unsigned = {
            "schema_version": TAG_SCHEMA_VERSION,
            "edge_id": edge_id,
            "tag_strength": strengths[edge_id],
            "episode_id": episode_id,
            "snapshot_id": snapshot_id,
            "source_trace_ids": sorted(edge_traces[edge_id]),
        }
        tags.append(
            EligibilityTagV1(
                tag_id=canonical_sha256(unsigned),
                **{key: value for key, value in unsigned.items() if key != "schema_version"},
            )
        )
    if not math.isclose(math.fsum(tag.tag_strength for tag in tags), 1.0, abs_tol=1e-15):
        raise EligibilityContractError("eligibility tags failed normalization")
    return tuple(tags)


__all__ = [
    "ActivationTraceV1",
    "EligibilityContractError",
    "EligibilityTagV1",
    "TAG_SCHEMA_VERSION",
    "TRACE_SCHEMA_VERSION",
    "derive_eligibility_tags",
    "make_activation_trace",
]
