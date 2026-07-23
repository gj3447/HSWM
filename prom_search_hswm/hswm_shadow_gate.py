#!/usr/bin/env python3
"""Pure reducer for Phase-B shadow-gated n-ary topology absorption.

The active field (場) is never mutated in place.  Each absorption round stages
an immutable candidate: a list of topology operations (ADD / SPLIT / MERGE /
SUPERSEDE) over the active hyperedge set.  The candidate is applied to a
shadow copy, three probes are measured on a fresh validation epoch, and a pure
gate function returns PASS/FAIL with typed rejection reasons.

Supersession discipline: no in-place mutation.  A superseded edge stays in the
ledger with ``invalid_at_round`` set; retrieval reads only edges whose
``invalid_at_round is None``.

No IO, no randomness: every function here is deterministic given its inputs.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping, Sequence


# ---------------------------------------------------------------------------
# Shadow gate (probe metrics -> verdict)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateThresholds:
    canary_epsilon: float = 0.01
    canary_min_preservation: float = 98.0
    fresh_delta_min: float = -0.01
    target_gain_min: float = 0.03
    min_canary_n: int = 20
    min_target_n: int = 10


DEFAULT_THRESHOLDS = GateThresholds()

# Fail-closed order: structural slice problems outrank measured harms, and
# harms to untouched knowledge outrank absence of gain.  The first entry of
# this tuple that fired becomes the primary rejection reason.
REASON_PRIORITY: tuple[str, ...] = (
    "insufficient_canary_slice",
    "insufficient_target_slice",
    "canary_harm",
    "fresh_harm",
    "no_target_gain",
)


@dataclass(frozen=True)
class GateVerdict:
    passed: bool
    reasons: tuple[str, ...]
    primary_reason: str | None


def canary_preservation(
    pre_scores: Sequence[float],
    post_scores: Sequence[float],
    epsilon: float,
) -> float:
    """100 * (1 - regression rate); a regression is post < pre - epsilon."""
    if len(pre_scores) != len(post_scores):
        raise ValueError("pre/post score length mismatch")
    if not pre_scores:
        raise ValueError("canary probe requires at least one query")
    regressed = sum(
        1 for pre, post in zip(pre_scores, post_scores) if post < pre - epsilon
    )
    return 100.0 * (1.0 - regressed / len(pre_scores))


def mean_delta(pre_scores: Sequence[float], post_scores: Sequence[float]) -> float:
    if len(pre_scores) != len(post_scores):
        raise ValueError("pre/post score length mismatch")
    if not pre_scores:
        raise ValueError("probe requires at least one query")
    return sum(post - pre for pre, post in zip(pre_scores, post_scores)) / len(pre_scores)


def evaluate_gate(
    *,
    canary_preservation_pct: float,
    fresh_delta: float,
    target_delta: float,
    canary_n: int,
    target_n: int,
    thresholds: GateThresholds = DEFAULT_THRESHOLDS,
) -> GateVerdict:
    """AND of the three preregistered gate conditions plus slice sufficiency.

    PASS requires all of:
      * canary slice large enough to be meaningful (>= min_canary_n)
      * target slice large enough to be meaningful (>= min_target_n)
      * canary_preservation >= canary_min_preservation (98%)
      * fresh non-inferiority: fresh_delta >= fresh_delta_min (-0.01)
      * target improvement: target_delta >= target_gain_min (+0.03)
    """
    fired: list[str] = []
    if canary_n < thresholds.min_canary_n:
        fired.append("insufficient_canary_slice")
    if target_n < thresholds.min_target_n:
        fired.append("insufficient_target_slice")
    if canary_preservation_pct < thresholds.canary_min_preservation:
        fired.append("canary_harm")
    if fresh_delta < thresholds.fresh_delta_min:
        fired.append("fresh_harm")
    if target_delta < thresholds.target_gain_min:
        fired.append("no_target_gain")
    reasons = tuple(reason for reason in REASON_PRIORITY if reason in fired)
    return GateVerdict(
        passed=not reasons,
        reasons=reasons,
        primary_reason=reasons[0] if reasons else None,
    )


# ---------------------------------------------------------------------------
# Topology operations and supersession ledger
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HyperEdge:
    edge_id: str
    members: tuple[int, ...]  # sorted unique document indices
    origin: str  # "base" | "add" | "split" | "merge"
    valid_at_round: int
    invalid_at_round: int | None  # None => active


@dataclass(frozen=True)
class TopologyOp:
    kind: str  # "ADD" | "SPLIT" | "MERGE" | "SUPERSEDE"
    edge_ids: tuple[str, ...]  # parent edge ids (empty for ADD)
    member_sets: tuple[tuple[int, ...], ...]  # new edge members (empty for SUPERSEDE)


def edge_id_for(origin: str, members: Sequence[int], valid_at_round: int) -> str:
    encoded = json.dumps(
        {
            "origin": origin,
            "members": sorted(set(int(member) for member in members)),
            "valid_at_round": valid_at_round,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def canonical_members(members: Sequence[int]) -> tuple[int, ...]:
    return tuple(sorted(set(int(member) for member in members)))


def active_edges(edges: Sequence[HyperEdge]) -> tuple[HyperEdge, ...]:
    return tuple(edge for edge in edges if edge.invalid_at_round is None)


def apply_ops(
    edges: Sequence[HyperEdge],
    ops: Sequence[TopologyOp],
    round_index: int,
) -> tuple[tuple[HyperEdge, ...], tuple[dict[str, object], ...]]:
    """Apply candidate ops, returning (new ledger, ledger entries).

    The input ledger is never mutated; superseded parents remain in the
    returned ledger with ``invalid_at_round=round_index``.  Raises ValueError
    on any op that references a missing or already-superseded parent
    (fail-closed: a malformed candidate never partially applies).
    """
    ledger: dict[str, HyperEdge] = {edge.edge_id: edge for edge in edges}
    if len(ledger) != len(edges):
        raise ValueError("duplicate edge_id in ledger")
    order: list[str] = [edge.edge_id for edge in edges]
    entries: list[dict[str, object]] = []

    def supersede(edge_id: str, op_kind: str) -> None:
        parent = ledger.get(edge_id)
        if parent is None:
            raise ValueError(f"{op_kind}: unknown parent edge {edge_id}")
        if parent.invalid_at_round is not None:
            raise ValueError(f"{op_kind}: parent {edge_id} already superseded")
        ledger[edge_id] = HyperEdge(
            edge_id=parent.edge_id,
            members=parent.members,
            origin=parent.origin,
            valid_at_round=parent.valid_at_round,
            invalid_at_round=round_index,
        )
        entries.append(
            {
                "op": "SUPERSEDE",
                "edge_id": edge_id,
                "invalid_at_round": round_index,
                "via": op_kind,
            }
        )

    def add(origin: str, members: Sequence[int]) -> HyperEdge:
        canonical = canonical_members(members)
        if len(canonical) < 2:
            raise ValueError(f"{origin}: edge needs at least 2 members")
        new_id = edge_id_for(origin, canonical, round_index)
        existing = ledger.get(new_id)
        if existing is not None and existing.invalid_at_round is None:
            return existing  # deterministic dedup: identical live edge is a no-op
        edge = HyperEdge(
            edge_id=new_id,
            members=canonical,
            origin=origin,
            valid_at_round=round_index,
            invalid_at_round=None,
        )
        ledger[new_id] = edge
        order.append(new_id)
        entries.append(
            {
                "op": "ADD",
                "edge_id": new_id,
                "origin": origin,
                "n_members": len(canonical),
                "valid_at_round": round_index,
            }
        )
        return edge

    for op in ops:
        if op.kind == "ADD":
            if len(op.member_sets) != 1:
                raise ValueError("ADD expects exactly one member set")
            add("add", op.member_sets[0])
        elif op.kind == "SPLIT":
            if len(op.edge_ids) != 1 or len(op.member_sets) != 2:
                raise ValueError("SPLIT expects one parent and two child sets")
            parent = ledger.get(op.edge_ids[0])
            if parent is None or parent.invalid_at_round is not None:
                raise ValueError(f"SPLIT: parent {op.edge_ids[0]} not active")
            union = canonical_members(op.member_sets[0] + op.member_sets[1])
            if union != parent.members:
                raise ValueError("SPLIT: children do not partition parent members")
            supersede(op.edge_ids[0], "SPLIT")
            add("split", op.member_sets[0])
            add("split", op.member_sets[1])
        elif op.kind == "MERGE":
            if len(op.edge_ids) != 2 or len(op.member_sets) != 1:
                raise ValueError("MERGE expects two parents and one merged set")
            parents = []
            for parent_id in op.edge_ids:
                parent = ledger.get(parent_id)
                if parent is None or parent.invalid_at_round is not None:
                    raise ValueError(f"MERGE: parent {parent_id} not active")
                parents.append(parent)
            expected = canonical_members(parents[0].members + parents[1].members)
            if canonical_members(op.member_sets[0]) != expected:
                raise ValueError("MERGE: merged set is not the parent union")
            for parent_id in op.edge_ids:
                supersede(parent_id, "MERGE")
            add("merge", op.member_sets[0])
        elif op.kind == "SUPERSEDE":
            if len(op.edge_ids) != 1:
                raise ValueError("SUPERSEDE expects exactly one parent")
            supersede(op.edge_ids[0], "SUPERSEDE")
        else:
            raise ValueError(f"unknown op kind {op.kind!r}")

    return tuple(ledger[edge_id] for edge_id in order), tuple(entries)


__all__ = [
    "DEFAULT_THRESHOLDS",
    "GateThresholds",
    "GateVerdict",
    "HyperEdge",
    "REASON_PRIORITY",
    "TopologyOp",
    "active_edges",
    "apply_ops",
    "canary_preservation",
    "edge_id_for",
    "evaluate_gate",
    "mean_delta",
]
