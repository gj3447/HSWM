#!/usr/bin/env python3
"""Conformance tests for deterministic slow/fast HSWM bond weighting."""
from __future__ import annotations

import math

import pytest

from hswm_bond_readout import (
    QueryBondWeight,
    normalize_query_logits,
    rank_bonds,
)
from hswm_open_composition import SemanticWeight


def neutral_weights(*edge_ids: str) -> tuple[SemanticWeight, ...]:
    return tuple(SemanticWeight(edge_id, 0.0) for edge_id in edge_ids)


def test_neutral_weights_preserve_base_order_and_scores_exactly():
    ranked = rank_bonds(
        {"b": 0.5, "a": 0.5, "c": -0.2},
        neutral_weights("a", "b", "c"),
    )
    assert [item.edge_id for item in ranked] == ["a", "b", "c"]
    assert {item.edge_id: item.score for item in ranked} == {
        "a": 0.5,
        "b": 0.5,
        "c": -0.2,
    }


def test_slow_semantic_weight_is_consumed_and_cannot_raise_score():
    ranked = rank_bonds(
        {"a": 0.8, "b": 0.7},
        (SemanticWeight("a", -0.25), SemanticWeight("b", 0.0)),
        slow_scale=1.0,
    )
    assert [item.edge_id for item in ranked] == ["b", "a"]
    by_id = {item.edge_id: item for item in ranked}
    assert by_id["a"].score == pytest.approx(0.55)
    assert by_id["b"].score == 0.7
    assert all(item.score <= item.base_score for item in ranked)


def test_query_logit_normalization_is_shift_invariant_and_max_zero():
    left = normalize_query_logits({"a": 3.0, "b": 1.5, "c": -2.0})
    right = normalize_query_logits({"a": 103.0, "b": 101.5, "c": 98.0})
    assert left == right
    assert max(item.relative_logit for item in left) == 0.0
    assert all(item.relative_logit <= 0.0 for item in left)


def test_query_bond_weights_rerank_inside_the_same_candidate_set():
    query = normalize_query_logits({"a": -2.0, "b": 0.0, "c": -1.0})
    ranked = rank_bonds(
        {"a": 0.9, "b": 0.8, "c": 0.7},
        neutral_weights("a", "b", "c"),
        query_weights=query,
        query_scale=0.2,
    )
    assert [item.edge_id for item in ranked] == ["b", "a", "c"]
    assert {item.edge_id for item in ranked} == {"a", "b", "c"}


@pytest.mark.parametrize(
    "slow",
    [
        (SemanticWeight("a", 0.0),),
        (SemanticWeight("a", 0.0), SemanticWeight("b", 0.0), SemanticWeight("c", 0.0)),
        (SemanticWeight("a", 0.0), SemanticWeight("a", 0.0)),
    ],
)
def test_slow_weights_require_exact_unique_candidate_coverage(slow):
    with pytest.raises(ValueError):
        rank_bonds({"a": 1.0, "b": 0.0}, slow)


def test_query_weights_require_exact_unique_candidate_coverage():
    with pytest.raises(ValueError):
        rank_bonds(
            {"a": 1.0, "b": 0.0},
            neutral_weights("a", "b"),
            query_weights=(QueryBondWeight("a", 0.0),),
        )
    with pytest.raises(ValueError):
        rank_bonds(
            {"a": 1.0},
            neutral_weights("a"),
            query_weights=(QueryBondWeight("a", 0.0), QueryBondWeight("a", 0.0)),
        )


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan, True, "1"])
def test_nonfinite_or_nonnumeric_query_logits_fail_closed(value):
    with pytest.raises(ValueError):
        normalize_query_logits({"a": value})


@pytest.mark.parametrize("scale", [-0.1, math.inf, math.nan, True])
def test_invalid_scales_fail_closed(scale):
    with pytest.raises(ValueError):
        rank_bonds({"a": 1.0}, neutral_weights("a"), slow_scale=scale)


def test_positive_query_relative_potential_is_rejected():
    with pytest.raises(ValueError):
        QueryBondWeight("a", 0.01)


def test_deterministic_under_mapping_and_weight_reordering():
    left = rank_bonds(
        {"c": 0.1, "a": 0.3, "b": 0.2},
        (SemanticWeight("c", -0.1), SemanticWeight("a", 0.0),
         SemanticWeight("b", -0.1)),
    )
    right = rank_bonds(
        {"b": 0.2, "c": 0.1, "a": 0.3},
        (SemanticWeight("b", -0.1), SemanticWeight("a", 0.0),
         SemanticWeight("c", -0.1)),
    )
    assert left == right
