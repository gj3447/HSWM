from __future__ import annotations

import math

import pytest

from p1_weighted_walk import walk_scores_weighted_strict
from typed_composition import (
    SelectorSpanV1,
    TypedEvidenceArcV1,
    make_typed_graph,
)


def _selector(source_id: str, role: str) -> SelectorSpanV1:
    exact = f"{source_id}-{role}"
    return SelectorSpanV1(
        source_id=source_id,
        role_id=f"role:{source_id}:{role}",
        role=role,
        text_scope="body",
        start=0,
        end=len(exact),
        exact=exact,
        source_text_sha256="1" * 64,
    )


def _arc(
    arc_id: str,
    source: int,
    target: int,
    *,
    source_claim: str,
    target_claim: str,
    join: str,
) -> TypedEvidenceArcV1:
    source_id = f"target:{source}"
    target_id = f"target:{target}"
    return TypedEvidenceArcV1(
        arc_id=arc_id,
        source_target=source,
        target_target=target,
        source_id=source_id,
        target_id=target_id,
        source_claim_id=source_claim,
        target_claim_id=target_claim,
        source_predicate=_selector(source_id, "predicate"),
        target_predicate=_selector(target_id, "predicate"),
        source_argument_role="subject",
        target_argument_role="object",
        join_entity_id=join,
        source_selector=_selector(source_id, "source"),
        target_selector=_selector(target_id, "target"),
    )


def _graph():
    return make_typed_graph(
        ("target:0", "target:1", "target:2", "target:3"),
        (
            _arc(
                "edge:a", 0, 1, source_claim="claim:0", target_claim="claim:1", join="join:a"
            ),
            _arc(
                "edge:b", 1, 2, source_claim="claim:1", target_claim="claim:2", join="join:b"
            ),
            _arc(
                "edge:c", 1, 3, source_claim="claim:wrong", target_claim="claim:3", join="join:c"
            ),
        ),
    )


def test_weighted_walker_preserves_strict_continuity_and_emits_best_trace():
    graph = _graph()
    result = walk_scores_weighted_strict(
        (1.0, 0.0, 0.0, 0.0),
        graph,
        seeds=(0,),
        edge_log_salience={"edge:a": 0.0, "edge:b": -math.log(2), "edge:c": 0.0},
        relation_quality=lambda _arc: 1.0,
    )

    assert result.strict_depth2_targets == 1
    assert result.k1_scores == pytest.approx((1.0, 0.1, 0.0, 0.0))
    assert result.k2_scores == pytest.approx((1.0, 0.1, 0.05, 0.0))
    assert result.path_by_target_id()["target:2"].edge_ids == ("edge:a", "edge:b")
    assert "target:3" not in result.path_by_target_id()


def test_weighted_walker_requires_exact_topology_weight_domain():
    graph = _graph()
    with pytest.raises(ValueError, match="exactly match"):
        walk_scores_weighted_strict(
            (1.0, 0.0, 0.0, 0.0),
            graph,
            seeds=(0,),
            edge_log_salience={"edge:a": 0.0, "edge:b": 0.0},
            relation_quality=lambda _arc: 1.0,
        )
