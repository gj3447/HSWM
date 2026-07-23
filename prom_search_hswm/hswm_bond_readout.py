#!/usr/bin/env python3
"""Deterministic bond-weight application for HSWM readouts.

This module is the missing narrow waist between weights stored by the open HSWM
manifest and retrieval scorers such as B2.  It deliberately does not learn,
persist, promote, or judge weights.  A learner may emit query logits and the
plasticity loop may activate slow ``SemanticWeight`` snapshots, but this module
only validates and applies them:

    score(e | q) = base(e | q) + lambda_s * ell(e) + lambda_q * a(e | q)

``ell`` is the durable, query-independent log salience already represented by
``SemanticWeight``.  ``a`` is a volatile query/bond potential obtained by
subtracting the maximum raw logit for the current candidate set.  Both live in
the canonical ``<= 0`` relative-potential domain.  The normalization loses only
an additive constant, so it preserves every ordering implied by the raw logits.

Honest boundary: this module establishes deterministic weight-to-readout
binding.  It is not evidence that any learned weight improves retrieval.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping

from hswm_open_composition import SemanticWeight


FORMULA_VERSION = "hswm-bond-readout/v1"


def _require_text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _finite_float(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{label} must be finite")
    return out


def _nonnegative_scale(value: float, label: str) -> float:
    out = _finite_float(value, label)
    if out < 0.0:
        raise ValueError(f"{label} must be >= 0")
    return out


@dataclass(frozen=True, order=True)
class QueryBondWeight:
    """Volatile query-relative bond potential; never durable HSWM salience."""

    edge_id: str
    relative_logit: float

    def __post_init__(self) -> None:
        _require_text(self.edge_id, "edge_id")
        value = _finite_float(self.relative_logit, "relative_logit")
        if value > 0.0:
            raise ValueError("relative_logit must be <= 0")
        object.__setattr__(self, "relative_logit", 0.0 if value == 0.0 else value)

    def canonical(self) -> dict:
        return {"edge_id": self.edge_id, "relative_logit": self.relative_logit}


@dataclass(frozen=True)
class RankedBond:
    edge_id: str
    base_score: float
    slow_log_salience: float
    query_relative_logit: float
    score: float

    def canonical(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "base_score": self.base_score,
            "slow_log_salience": self.slow_log_salience,
            "query_relative_logit": self.query_relative_logit,
            "score": self.score,
        }


def normalize_query_logits(raw_logits: Mapping[str, float]) -> tuple[QueryBondWeight, ...]:
    """Compile arbitrary finite logits into canonical max-zero potentials."""
    if not isinstance(raw_logits, Mapping) or not raw_logits:
        raise ValueError("raw_logits must be a non-empty mapping")
    values: dict[str, float] = {}
    for edge_id, raw in raw_logits.items():
        _require_text(edge_id, "query-logit edge_id")
        if edge_id in values:
            raise ValueError(f"duplicate query-logit edge_id {edge_id}")
        values[edge_id] = _finite_float(raw, f"query logit for {edge_id}")
    maximum = max(values.values())
    return tuple(
        QueryBondWeight(edge_id, values[edge_id] - maximum)
        for edge_id in sorted(values)
    )


def _exact_values(items: Iterable, *, edge_ids: set[str], value_attr: str,
                  label: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in items:
        edge_id = getattr(item, "edge_id", None)
        _require_text(edge_id, f"{label} edge_id")
        if edge_id in values:
            raise ValueError(f"duplicate {label} edge_id {edge_id}")
        values[edge_id] = _finite_float(getattr(item, value_attr, None),
                                        f"{label} value for {edge_id}")
    observed = set(values)
    if observed != edge_ids:
        raise ValueError(
            f"{label} must cover the candidate set exactly; "
            f"missing={sorted(edge_ids - observed)}, extra={sorted(observed - edge_ids)}"
        )
    return values


def rank_bonds(
    base_scores: Mapping[str, float],
    slow_weights: Iterable[SemanticWeight],
    *,
    query_weights: Iterable[QueryBondWeight] | None = None,
    slow_scale: float = 1.0,
    query_scale: float = 1.0,
) -> tuple[RankedBond, ...]:
    """Apply exact-coverage slow/fast potentials and rank score-desc/id-asc.

    Candidate identity comes exclusively from ``base_scores``.  Both weight
    planes must cover that set exactly; missing weights never silently default.
    Pass ``query_weights=None`` for a neutral volatile plane.
    """
    if not isinstance(base_scores, Mapping) or not base_scores:
        raise ValueError("base_scores must be a non-empty mapping")
    base: dict[str, float] = {}
    for edge_id, score in base_scores.items():
        _require_text(edge_id, "base-score edge_id")
        if edge_id in base:
            raise ValueError(f"duplicate base-score edge_id {edge_id}")
        base[edge_id] = _finite_float(score, f"base score for {edge_id}")
    edge_ids = set(base)
    slow = _exact_values(
        slow_weights,
        edge_ids=edge_ids,
        value_attr="log_salience",
        label="slow weight",
    )
    if any(value > 0.0 for value in slow.values()):
        raise ValueError("slow log salience must be <= 0")
    if query_weights is None:
        query = {edge_id: 0.0 for edge_id in edge_ids}
    else:
        query = _exact_values(
            query_weights,
            edge_ids=edge_ids,
            value_attr="relative_logit",
            label="query weight",
        )
        if any(value > 0.0 for value in query.values()):
            raise ValueError("query relative logits must be <= 0")
    slow_scale = _nonnegative_scale(slow_scale, "slow_scale")
    query_scale = _nonnegative_scale(query_scale, "query_scale")

    ranked = tuple(
        RankedBond(
            edge_id=edge_id,
            base_score=base[edge_id],
            slow_log_salience=slow[edge_id],
            query_relative_logit=query[edge_id],
            score=(base[edge_id]
                   + slow_scale * slow[edge_id]
                   + query_scale * query[edge_id]),
        )
        for edge_id in sorted(edge_ids)
    )
    return tuple(sorted(ranked, key=lambda item: (-item.score, item.edge_id)))


__all__ = [
    "FORMULA_VERSION",
    "QueryBondWeight",
    "RankedBond",
    "normalize_query_logits",
    "rank_bonds",
]
