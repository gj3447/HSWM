"""Evidence-receipted max-semiring composition over role-bound target links.

This module is a research kernel, not a deployable readout.  It exists to test
one narrow hypothesis without weakening ``traversal.py``'s certified diffusion
guards: can an exact, source-bound relation path improve retrieval when the
same static field, embeddings, candidates, and scores are held fixed?

The kernel preserves the strongest path instead of averaging neighbouring
mass.  That distinction matters on sparse evidence graphs: a single exact
title reference is a candidate proof path, whereas diffusion treats it as low
``n_eff`` and correctly refuses under its own policy.  Every non-null arc has
an exact source selector so a score promotion can be replayed to text.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
import math
from typing import Iterable, Literal

import numpy as np


Direction = Literal["forward", "reverse", "bidirectional"]


@dataclass(frozen=True)
class EvidenceArcV1:
    """One directed ``document subject -> referenced title`` relation."""

    source_target: int
    target_target: int
    source_id: str
    selector_start: int
    selector_end: int
    selector_exact: str
    anchor_label: str

    def __post_init__(self) -> None:
        if self.source_target < 0 or self.target_target < 0:
            raise ValueError("target indices must be non-negative")
        if self.source_target == self.target_target:
            raise ValueError("self arcs are not compositional evidence")
        if self.selector_start < 0 or self.selector_end <= self.selector_start:
            raise ValueError("arc selector must be a non-empty range")
        if self.selector_end - self.selector_start != len(self.selector_exact):
            raise ValueError("arc selector range and exact text length disagree")
        if not self.source_id or not self.selector_exact or not self.anchor_label:
            raise ValueError("arc evidence fields must be non-empty")


@dataclass(frozen=True)
class CompositionGraphV1:
    n_targets: int
    target_ids: tuple[str, ...]
    arcs: tuple[EvidenceArcV1, ...]
    topology_sha256: str
    is_null_control: bool = False


@dataclass(frozen=True)
class CompositionPolicyV1:
    seed_k: int
    hops: int
    mu: float
    direction: Direction = "bidirectional"
    fanout_exponent: float = 0.5
    max_fanout: int = 64

    def __post_init__(self) -> None:
        if self.seed_k < 1 or self.hops < 1:
            raise ValueError("seed_k and hops must be positive")
        if not math.isfinite(self.mu) or self.mu < 0:
            raise ValueError("mu must be finite and non-negative")
        if self.direction not in ("forward", "reverse", "bidirectional"):
            raise ValueError(f"unsupported direction {self.direction!r}")
        if not math.isfinite(self.fanout_exponent) or self.fanout_exponent < 0:
            raise ValueError("fanout_exponent must be finite and non-negative")
        if self.max_fanout < 1:
            raise ValueError("max_fanout must be positive")


@dataclass(frozen=True)
class PathStepV1:
    source_target: int
    target_target: int
    arc_index: int
    selector_exact: str


@dataclass(frozen=True)
class PromotedPathV1:
    target: int
    raw_path_score: float
    residual: float
    steps: tuple[PathStepV1, ...]


@dataclass(frozen=True)
class CompositionReceiptV1:
    topology_sha256: str
    policy: CompositionPolicyV1
    seed_targets: tuple[int, ...]
    reached_targets: int
    promoted_paths: tuple[PromotedPathV1, ...]
    trip_reason: str | None
    research_only: bool = True


def _topology_digest(n_targets: int, target_ids: tuple[str, ...],
                     arcs: tuple[EvidenceArcV1, ...], is_null: bool) -> str:
    payload = {
        "schema": "hswm-composition-graph/v1",
        "n_targets": n_targets,
        "target_ids": target_ids,
        "is_null_control": is_null,
        "arcs": [
            {
                "source_target": a.source_target,
                "target_target": a.target_target,
                "source_id": a.source_id,
                "selector_start": a.selector_start,
                "selector_end": a.selector_end,
                "selector_exact": a.selector_exact,
                "anchor_label": a.anchor_label,
            }
            for a in arcs
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()


def make_graph(target_ids: Iterable[str], arcs: Iterable[EvidenceArcV1], *,
               is_null_control: bool = False) -> CompositionGraphV1:
    """Canonicalize and validate an evidence graph."""
    ids = tuple(target_ids)
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("target_ids must be non-empty and unique")
    ordered = tuple(sorted(set(arcs), key=lambda a: (
        a.source_target, a.target_target, a.source_id,
        a.selector_start, a.selector_end, a.anchor_label,
    )))
    n = len(ids)
    if any(a.source_target >= n or a.target_target >= n for a in ordered):
        raise ValueError("arc references a target outside the candidate universe")
    return CompositionGraphV1(
        n_targets=n,
        target_ids=ids,
        arcs=ordered,
        topology_sha256=_topology_digest(n, ids, ordered, is_null_control),
        is_null_control=is_null_control,
    )


@lru_cache(maxsize=32)
def _adjacency(graph: CompositionGraphV1, direction: Direction
               ) -> tuple[tuple[tuple[int, int], ...], ...]:
    rows: list[list[tuple[int, int]]] = [[] for _ in range(graph.n_targets)]
    for ai, arc in enumerate(graph.arcs):
        if direction in ("forward", "bidirectional"):
            rows[arc.source_target].append((arc.target_target, ai))
        if direction in ("reverse", "bidirectional"):
            rows[arc.target_target].append((arc.source_target, ai))
    return tuple(tuple(sorted(set(row))) for row in rows)


def _path_key(path: tuple[PathStepV1, ...]) -> tuple[tuple[int, int, int], ...]:
    return tuple((step.source_target, step.target_target, step.arc_index) for step in path)


def compose_scores(static_scores: np.ndarray, graph: CompositionGraphV1,
                   policy: CompositionPolicyV1
                   ) -> tuple[np.ndarray, np.ndarray, CompositionReceiptV1]:
    """Return ``static + mu * max_path_residual`` and its evidence receipt.

    Query information enters only through ``static_scores`` and seed selection.
    The graph and transition weights are query-independent.  ``mu=0`` is an
    early bit-identical floor.  Reached-path scores are standardized only over
    reached targets; unreachable targets receive an exact zero residual.
    """
    static = np.asarray(static_scores, dtype=np.float64)
    if static.shape != (graph.n_targets,) or not np.isfinite(static).all():
        raise ValueError("static_scores must be one finite score per target")
    seed_k = min(policy.seed_k, graph.n_targets)
    seeds = tuple(int(i) for i in np.argsort(-static, kind="stable")[:seed_k])
    zero = np.zeros_like(static)
    if policy.mu == 0:
        return static.copy(), zero, CompositionReceiptV1(
            topology_sha256=graph.topology_sha256, policy=policy,
            seed_targets=seeds, reached_targets=0, promoted_paths=(),
            trip_reason="mu=0 certified floor",
        )

    adj = _adjacency(graph, policy.direction)
    # A path starts with non-negative retrieval support.  Negative cosine must
    # not become positive merely by multiplying two negatives along a path.
    current = {i: max(float(static[i]), 0.0) for i in seeds}
    current_paths: dict[int, tuple[PathStepV1, ...]] = {i: () for i in seeds}
    reached: dict[int, float] = {}
    reached_paths: dict[int, tuple[PathStepV1, ...]] = {}
    fanout_trips = 0
    for _ in range(policy.hops):
        nxt: dict[int, float] = {}
        nxt_paths: dict[int, tuple[PathStepV1, ...]] = {}
        for source, parent_score in sorted(current.items()):
            row = adj[source]
            if not row:
                continue
            if len(row) > policy.max_fanout:
                fanout_trips += 1
                continue
            weight = float(len(row)) ** (-policy.fanout_exponent)
            candidate_score = parent_score * weight
            for target, ai in row:
                arc = graph.arcs[ai]
                step = PathStepV1(
                    source_target=source, target_target=target, arc_index=ai,
                    selector_exact=arc.selector_exact,
                )
                candidate_path = current_paths[source] + (step,)
                old = nxt.get(target, -math.inf)
                # Stable path-index tie-break makes receipts bit-reproducible.
                if candidate_score > old or (
                    candidate_score == old and
                    _path_key(candidate_path) < _path_key(nxt_paths.get(target, candidate_path))
                ):
                    nxt[target] = candidate_score
                    nxt_paths[target] = candidate_path
                old_all = reached.get(target, -math.inf)
                if candidate_score > old_all or (
                    candidate_score == old_all and
                    _path_key(candidate_path) < _path_key(reached_paths.get(target, candidate_path))
                ):
                    reached[target] = candidate_score
                    reached_paths[target] = candidate_path
        current, current_paths = nxt, nxt_paths

    if not reached:
        reason = "all evidence paths tripped fanout guard" if fanout_trips else "no evidence path from seeds"
        return static.copy(), zero, CompositionReceiptV1(
            topology_sha256=graph.topology_sha256, policy=policy,
            seed_targets=seeds, reached_targets=0, promoted_paths=(),
            trip_reason=reason,
        )

    raw = np.zeros_like(static)
    for target, value in reached.items():
        raw[target] = value
    reached_ids = np.array(sorted(reached), dtype=np.int64)
    reached_values = raw[reached_ids]
    residual = np.zeros_like(static)
    if reached_values.size > 1 and float(reached_values.std()) > 0:
        residual[reached_ids] = (
            (reached_values - float(reached_values.mean())) /
            float(reached_values.std())
        )
    else:
        residual[reached_ids] = reached_values
    final = static + policy.mu * residual
    promoted = tuple(
        PromotedPathV1(
            target=int(target), raw_path_score=float(raw[target]),
            residual=float(residual[target]), steps=reached_paths[int(target)],
        )
        for target in reached_ids if residual[target] > 0
    )
    trip = None
    if fanout_trips:
        trip = f"partial: {fanout_trips} seed/frontier nodes exceeded max_fanout"
    return final, residual, CompositionReceiptV1(
        topology_sha256=graph.topology_sha256, policy=policy,
        seed_targets=seeds, reached_targets=len(reached),
        promoted_paths=promoted, trip_reason=trip,
    )


def degree_preserving_shuffle(graph: CompositionGraphV1, seed: int,
                              attempts_per_arc: int = 40) -> CompositionGraphV1:
    """Directed double-edge swaps preserving every in/out degree exactly.

    Shuffled arcs deliberately carry ``NULL_CONTROL`` selectors: they are a
    topology falsifier, never evidence and never eligible for deployment.
    """
    if seed < 0 or attempts_per_arc < 1:
        raise ValueError("seed must be non-negative and attempts_per_arc positive")
    pairs = [(a.source_target, a.target_target) for a in graph.arcs]
    if len(pairs) < 2:
        return make_graph(graph.target_ids, graph.arcs, is_null_control=True)
    rng = np.random.default_rng(seed)
    occupied = set(pairs)
    for _ in range(attempts_per_arc * len(pairs)):
        i, j = (int(x) for x in rng.integers(0, len(pairs), size=2))
        if i == j:
            continue
        a, b = pairs[i]
        c, d = pairs[j]
        if a == c or b == d:
            continue
        p, q = (a, d), (c, b)
        if p[0] == p[1] or q[0] == q[1] or p in occupied or q in occupied:
            continue
        occupied.remove((a, b)); occupied.remove((c, d))
        pairs[i], pairs[j] = p, q
        occupied.add(p); occupied.add(q)
    null_arcs = tuple(
        EvidenceArcV1(
            source_target=a, target_target=b,
            source_id=f"null-control:{seed}", selector_start=0,
            selector_end=len("NULL_CONTROL"), selector_exact="NULL_CONTROL",
            anchor_label="NULL_CONTROL",
        )
        for a, b in pairs
    )
    return make_graph(graph.target_ids, null_arcs, is_null_control=True)
