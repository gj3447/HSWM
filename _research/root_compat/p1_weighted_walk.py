"""Strict K<=2 max-product walker with immutable slow-weight readout traces."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Mapping, Sequence

from typed_composition import TypedCompositionGraphV1, TypedEvidenceArcV1


@dataclass(frozen=True)
class WeightedWalkPolicyV1:
    mu: float = 0.1
    fanout_exponent: float = 0.5

    def __post_init__(self) -> None:
        if not math.isfinite(self.mu) or self.mu < 0.0:
            raise ValueError("mu must be finite and non-negative")
        if not math.isfinite(self.fanout_exponent) or self.fanout_exponent < 0.0:
            raise ValueError("fanout_exponent must be finite and non-negative")


@dataclass(frozen=True)
class WeightedPathV1:
    target: int
    target_id: str
    depth: int
    edge_ids: tuple[str, ...]
    raw_contribution: float


@dataclass(frozen=True)
class WeightedWalkResultV1:
    k1_scores: tuple[float, ...]
    k2_scores: tuple[float, ...]
    selected_paths: tuple[WeightedPathV1, ...]
    strict_depth2_targets: int

    def path_by_target_id(self) -> dict[str, WeightedPathV1]:
        return {path.target_id: path for path in self.selected_paths}


@dataclass(frozen=True)
class _State:
    score: float
    target: int
    active_claim_id: str | None
    joins: frozenset[str]
    nodes: frozenset[int]
    edge_ids: tuple[str, ...]


def _prefer(candidate: _State, prior: _State | None) -> bool:
    if prior is None or candidate.score > prior.score:
        return True
    return candidate.score == prior.score and candidate.edge_ids < prior.edge_ids


def walk_scores_weighted_strict(
    static_scores: Sequence[float],
    graph: TypedCompositionGraphV1,
    *,
    seeds: Sequence[int],
    edge_log_salience: Mapping[str, float],
    relation_quality: Callable[[TypedEvidenceArcV1], float],
    policy: WeightedWalkPolicyV1 = WeightedWalkPolicyV1(),
) -> WeightedWalkResultV1:
    """Preserve T3 semantics while multiplying every traversed arc by exp(ell)."""

    if len(static_scores) != graph.n_targets:
        raise ValueError("static score vector length differs from graph")
    seed_tuple = tuple(seeds)
    if len(set(seed_tuple)) != len(seed_tuple) or any(
        isinstance(seed, bool) or not isinstance(seed, int) or seed < 0 or seed >= graph.n_targets
        for seed in seed_tuple
    ):
        raise ValueError("seeds must be unique valid target ordinals")
    if set(edge_log_salience) != {arc.arc_id for arc in graph.arcs}:
        raise ValueError("slow-weight domain must exactly match graph arc IDs")
    weights: dict[str, float] = {}
    for edge_id, log_weight in edge_log_salience.items():
        if isinstance(log_weight, bool) or not isinstance(log_weight, (int, float)):
            raise ValueError("slow weights must be numeric")
        value = float(log_weight)
        if not math.isfinite(value) or value > 0.0:
            raise ValueError("slow weights must be finite and <= 0")
        weights[edge_id] = math.exp(value)

    static = tuple(float(value) for value in static_scores)
    if any(not math.isfinite(value) for value in static):
        raise ValueError("static scores must be finite")
    adjacency: list[list[TypedEvidenceArcV1]] = [[] for _ in range(graph.n_targets)]
    for arc in graph.arcs:
        adjacency[arc.source_target].append(arc)
    for row in adjacency:
        row.sort(key=lambda arc: (arc.target_target, arc.arc_id))

    best1: dict[int, _State] = {}
    hop1: list[_State] = []
    for seed in seed_tuple:
        base = max(static[seed], 0.0)
        row = adjacency[seed]
        if base <= 0.0 or not row:
            continue
        fanout = len(row) ** (-policy.fanout_exponent)
        for arc in row:
            quality = float(relation_quality(arc))
            if not math.isfinite(quality) or quality < 0.0:
                raise ValueError("relation quality must be finite and non-negative")
            score = base * fanout * quality * weights[arc.arc_id]
            if score <= 0.0:
                continue
            state = _State(
                score=score,
                target=arc.target_target,
                active_claim_id=arc.target_claim_id,
                joins=frozenset((arc.join_entity_id,)),
                nodes=frozenset((seed, arc.target_target)),
                edge_ids=(arc.arc_id,),
            )
            hop1.append(state)
            if _prefer(state, best1.get(state.target)):
                best1[state.target] = state

    best2: dict[int, _State] = {}
    for prior in hop1:
        if prior.active_claim_id is None:
            continue
        row = [
            arc
            for arc in adjacency[prior.target]
            if arc.source_claim_id == prior.active_claim_id
        ]
        if not row:
            continue
        fanout = len(row) ** (-policy.fanout_exponent)
        for arc in row:
            if arc.target_target in prior.nodes or arc.join_entity_id in prior.joins:
                continue
            quality = float(relation_quality(arc))
            if not math.isfinite(quality) or quality < 0.0:
                raise ValueError("relation quality must be finite and non-negative")
            score = prior.score * fanout * quality * weights[arc.arc_id]
            if score <= 0.0:
                continue
            state = _State(
                score=score,
                target=arc.target_target,
                active_claim_id=arc.target_claim_id,
                joins=prior.joins | {arc.join_entity_id},
                nodes=prior.nodes | {arc.target_target},
                edge_ids=prior.edge_ids + (arc.arc_id,),
            )
            if _prefer(state, best2.get(state.target)):
                best2[state.target] = state

    k1 = list(static)
    k2 = list(static)
    selected: list[WeightedPathV1] = []
    for target in range(graph.n_targets):
        one = best1.get(target)
        two = best2.get(target)
        c1 = one.score if one is not None else 0.0
        c2 = two.score if two is not None else 0.0
        k1[target] += policy.mu * c1
        chosen = two if two is not None and (one is None or _prefer(two, one)) else one
        contribution = max(c1, c2)
        k2[target] += policy.mu * contribution
        if chosen is not None:
            selected.append(
                WeightedPathV1(
                    target=target,
                    target_id=graph.target_ids[target],
                    depth=len(chosen.edge_ids),
                    edge_ids=chosen.edge_ids,
                    raw_contribution=contribution,
                )
            )
    return WeightedWalkResultV1(
        k1_scores=tuple(k1),
        k2_scores=tuple(k2),
        selected_paths=tuple(selected),
        strict_depth2_targets=len(best2),
    )


__all__ = [
    "WeightedPathV1",
    "WeightedWalkPolicyV1",
    "WeightedWalkResultV1",
    "walk_scores_weighted_strict",
]
