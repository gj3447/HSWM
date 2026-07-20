"""H3 typed-composition teeth: depth necessity, controls, and receipts."""
from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import numpy as np
import pytest

import typed_composition as tc


def _span(source_id: str, role: str, exact: str, *, start: int = 0) -> tc.SelectorSpanV1:
    return tc.SelectorSpanV1(
        source_id=source_id,
        role_id=f"role:{source_id}:{role}:{start}:{exact}",
        role=role,
        text_scope="body",
        start=start,
        end=start + len(exact),
        exact=exact,
        source_text_sha256=sha256(f"{source_id}:body".encode()).hexdigest(),
    )


def _arc(
    arc_id: str,
    source: int,
    target: int,
    predicate: str,
    role: str,
    join: str,
    *,
    target_predicate: str | None = None,
    source_claim_id: str | None = None,
    target_claim_id: str | None = None,
    origin: str | None = None,
) -> tc.TypedEvidenceArcV1:
    ids = ("work", "composer", "city", "noise_source", "wrong_city")
    source_id, target_id = ids[source], ids[target]
    return tc.TypedEvidenceArcV1(
        arc_id=arc_id,
        source_target=source,
        target_target=target,
        source_id=source_id,
        target_id=target_id,
        source_claim_id=source_claim_id or f"claim:{source_id}",
        target_claim_id=target_claim_id,
        source_predicate=_span(source_id, "predicate", predicate),
        target_predicate=(
            _span(target_id, "predicate", target_predicate)
            if target_predicate is not None else None
        ),
        source_argument_role=role,
        target_argument_role="subject",
        join_entity_id=join,
        source_selector=_span(source_id, role, target_id, start=20),
        target_selector=_span(target_id, "subject", target_id),
        origin=origin or (
            "verified_shared_entity"
            if target_claim_id is not None else "verified_nary_title"
        ),
    )


def _graph() -> tc.TypedCompositionGraphV1:
    # work --composed/composer--> composer --born/birthplace--> city
    # The disconnected edge is only the matched target-shuffle partner.
    return tc.make_typed_graph(
        ("work", "composer", "city", "noise_source", "wrong_city"),
        (
            _arc(
                "a0-composer", 0, 1, "composed", "composer", "entity:composer",
                target_predicate="born", target_claim_id="claim:composer",
            ),
            _arc(
                "a1-birthplace", 1, 2, "born", "birthplace", "entity:city",
                target_predicate="located", target_claim_id="claim:city",
            ),
            _arc(
                "a2-decoy", 3, 4, "founded", "headquarters", "entity:wrong",
                target_predicate="incorporated", target_claim_id="claim:wrong_city",
            ),
        ),
    )


def _scores() -> np.ndarray:
    # Exactly one seed under seed_k=1.  City is deliberately absent from B1.
    return np.array([1.0, 0.10, 0.0, 0.20, -0.10], dtype=np.float64)


def _policy(**changes) -> tc.TypedCompositionPolicyV1:
    base = tc.TypedCompositionPolicyV1(
        seed_k=1,
        max_hops=2,
        mu=0.25,
        fanout_exponent=0.0,
        max_fanout=4,
        max_join_degree=4,
    )
    return replace(base, **changes)


def test_two_hop_typed_path_beats_matched_k1_and_preserves_full_receipt():
    scores = _scores()
    query = "Which composer composed the work, and in which birthplace were they born?"
    final, contribution, receipt = tc.compose_typed_scores(
        query, scores, _graph(), _policy(),
    )

    assert final[2] > scores[2]
    assert contribution[2] > 0
    assert receipt.first_reachable_at_depth_2 == 1
    assert receipt.depth_2_promotions == 1
    assert receipt.h3_composition_status == "PASS"
    assert receipt.k1_ablation is not None
    assert 2 not in receipt.k1_ablation.promoted_targets
    assert 2 in receipt.k1_ablation.full_over_k1_promoted_targets

    path = next(item for item in receipt.promoted_paths if item.target == 2)
    assert path.selected_depth == 2
    assert path.intermediate_targets == (1,)
    assert path.intermediate_target_ids == ("composer",)
    assert [step.source_predicate.exact for step in path.steps] == [
        "composed", "born",
    ]
    assert [
        (step.source_claim_id, step.target_claim_id) for step in path.steps
    ] == [
        ("claim:work", "claim:composer"),
        ("claim:composer", "claim:city"),
    ]
    assert [step.join_entity_id for step in path.steps] == [
        "entity:composer", "entity:city",
    ]
    # Both exact endpoint selectors survive on both path steps.
    assert [
        (step.source_selector.exact, step.target_selector.exact)
        for step in path.steps
    ] == [("composer", "composer"), ("city", "city")]
    assert receipt.depth_contributions[1].selected_score_contribution > 0


def test_b1_one_hop_cannot_reach_target_and_cannot_claim_h3_pass():
    scores = _scores()
    final, _, receipt = tc.compose_typed_scores(
        "composer composed and born in birthplace",
        scores,
        _graph(),
        _policy(max_hops=1),
    )
    assert final[2].tobytes() == scores[2].tobytes()
    assert receipt.first_reachable_at_depth_2 == 0
    assert receipt.h3_composition_status == "REFUSED"
    assert receipt.h3_refusal_reason == "matched K>=2 run is required"


def test_second_edge_target_shuffle_kills_the_depth_two_target():
    graph = _graph()
    shuffled = tc.target_shuffle_null_control(
        graph, ("a1-birthplace", "a2-decoy"), seed=7,
    )
    assert shuffled.is_null_control
    assert shuffled.topology_sha256 != graph.topology_sha256
    shuffled_birth = next(arc for arc in shuffled.arcs if arc.arc_id == "a1-birthplace")
    assert shuffled_birth.target_claim_id == "claim:wrong_city"

    scores = _scores()
    final, _, receipt = tc.compose_typed_scores(
        "composer composed and born in birthplace", scores, shuffled, _policy(),
    )
    assert final[2].tobytes() == scores[2].tobytes()
    assert 2 not in receipt.k1_ablation.full_over_k1_promoted_targets


def test_role_predicate_shuffle_null_kills_relation_composition():
    graph = _graph()
    shuffled = tc.relation_shuffle_null_control(
        graph, ("a1-birthplace", "a2-decoy"), seed=11,
    )
    assert shuffled.is_null_control
    assert next(
        arc for arc in shuffled.arcs if arc.arc_id == "a1-birthplace"
    ).target_claim_id == "claim:city"
    assert [arc.source_target for arc in shuffled.arcs] == [
        arc.source_target for arc in graph.arcs
    ]
    assert [arc.target_target for arc in shuffled.arcs] == [
        arc.target_target for arc in graph.arcs
    ]
    final, _, receipt = tc.compose_typed_scores(
        "composer composed and born in birthplace",
        _scores(),
        shuffled,
        _policy(),
    )
    assert final[2].tobytes() == _scores()[2].tobytes()
    assert receipt.h3_composition_status == "REFUSED"


def test_relation_mismatch_blocks_second_edge_but_untyped_control_does_not():
    scores = _scores()
    graph = _graph()
    typed, untyped, control = tc.compare_typed_untyped(
        "Who composed the work?", scores, graph, _policy(),
    )
    typed_final, _, typed_receipt = typed
    untyped_final, _, untyped_receipt = untyped

    assert typed_final[1] > scores[1]  # first relation is genuinely matched
    assert typed_final[2].tobytes() == scores[2].tobytes()
    assert typed_receipt.h3_composition_status == "REFUSED"
    assert untyped_final[2] > scores[2]
    assert untyped_receipt.h3_composition_status == "PASS"
    assert control.topology_sha256 == graph.topology_sha256
    assert typed_receipt.topology_sha256 == untyped_receipt.topology_sha256


def test_target_predicate_and_role_cannot_look_ahead_to_score_current_hop():
    arc = _arc(
        "lookahead-trap", 0, 1, "founded", "inventor", "entity:composer",
        target_predicate="born", target_claim_id="claim:composer",
    )
    arc = replace(arc, target_argument_role="birthplace")
    graph = tc.make_typed_graph(_graph().target_ids, (arc,))
    scores = _scores()
    final, _, receipt = tc.compose_typed_scores(
        "Where was the birthplace in which they were born?",
        scores,
        graph,
        _policy(max_hops=1),
    )
    assert final.tobytes() == scores.tobytes()
    assert receipt.reached_targets == 0


def test_role_only_match_cannot_admit_an_unmatched_source_predicate():
    arc = _arc(
        "role-only-trap", 0, 1, "founded", "composer", "entity:composer",
        target_predicate="born", target_claim_id="claim:composer",
    )
    graph = tc.make_typed_graph(_graph().target_ids, (arc,))
    scores = _scores()
    final, _, receipt = tc.compose_typed_scores(
        "Which composer?", scores, graph, _policy(max_hops=1),
    )
    assert final.tobytes() == scores.tobytes()
    assert receipt.reached_targets == 0
    assert receipt.trip_reason == "no_query_compatible_evidence_path"


def test_two_claims_in_one_paragraph_cannot_illegally_switch_claim_identity():
    first = _arc(
        "into-mid-claim-a", 0, 1, "composed", "composer", "entity:composer",
        target_predicate="recorded", target_claim_id="claim:composer:a",
    )
    # Same paragraph ordinal, but this outgoing relation belongs to claim B.
    illegal_second = _arc(
        "out-of-mid-claim-b", 1, 2, "born", "birthplace", "entity:city",
        source_claim_id="claim:composer:b",
        target_predicate="located", target_claim_id="claim:city",
    )
    graph = tc.make_typed_graph(_graph().target_ids, (first, illegal_second))
    scores = _scores()
    final, _, receipt = tc.compose_typed_scores(
        "composer composed and born in birthplace", scores, graph, _policy(),
    )
    assert final[1] > scores[1]
    assert final[2].tobytes() == scores[2].tobytes()
    assert receipt.first_reachable_at_depth_2 == 0
    assert receipt.h3_composition_status == "REFUSED"


def test_no_depth_two_promotion_is_an_explicit_h3_refusal():
    graph = tc.make_typed_graph(
        _graph().target_ids,
        (_arc("only-one-hop", 0, 1, "composed", "composer", "entity:composer"),),
    )
    _, _, receipt = tc.compose_typed_scores(
        "composer composed and born in birthplace", _scores(), graph, _policy(),
    )
    assert receipt.depth_2_promotions == 0
    assert receipt.first_reachable_at_depth_2 == 0
    assert receipt.h3_composition_status == "REFUSED"
    assert receipt.h3_refusal_reason == "no positive depth-2 promotion"


def test_mu_zero_is_bit_identical_and_never_claims_composition():
    scores = np.array([0.0, -0.0, 0.25, -1.0, 2.0], dtype=np.float64)
    final, contribution, receipt = tc.compose_typed_scores(
        "composer composed and born in birthplace",
        scores,
        _graph(),
        _policy(mu=0.0),
    )
    assert final.tobytes() == scores.tobytes()
    assert not contribution.any()
    assert receipt.h3_composition_status == "REFUSED"
    assert receipt.k1_ablation is None


def test_fanout_and_join_hub_gates_fail_closed():
    extra = _arc("seed-fanout", 0, 4, "composed", "composer", "entity:other")
    graph = tc.make_typed_graph(_graph().target_ids, (*_graph().arcs, extra))
    scores = _scores()
    final, _, receipt = tc.compose_typed_scores(
        "composer composed and born in birthplace",
        scores,
        graph,
        _policy(max_fanout=1),
    )
    assert final.tobytes() == scores.tobytes()
    assert receipt.fanout_gate_trips == 1
    assert "fanout_gate" in receipt.trip_reason
    assert receipt.h3_composition_status == "REFUSED"
    assert receipt.h3_refusal_reason == "safety gate trip forced static fallback"

    duplicate_join = replace(
        extra, arc_id="same-join", join_entity_id="entity:composer",
    )
    graph = tc.make_typed_graph(
        _graph().target_ids, (*_graph().arcs, duplicate_join),
    )
    final, _, receipt = tc.compose_typed_scores(
        "composer composed and born in birthplace",
        scores,
        graph,
        _policy(max_join_degree=1),
    )
    assert final.tobytes() == scores.tobytes()
    assert receipt.join_hub_gate_trips >= 1
    assert "join_hub_gate" in receipt.trip_reason
    assert receipt.h3_composition_status == "REFUSED"


def test_join_hub_degree_counts_unique_participating_sources_not_arc_count():
    base = _arc(
        "parallel-0", 0, 1, "composed", "composer", "entity:composer",
        target_predicate="born", target_claim_id="claim:composer",
    )
    parallels = tuple(
        replace(base, arc_id=f"parallel-{index}") for index in range(3)
    )
    graph = tc.make_typed_graph(_graph().target_ids, parallels)
    _, _, receipt = tc.compose_typed_scores(
        "composer composed", _scores(), graph,
        _policy(max_hops=1, max_fanout=4, max_join_degree=2),
    )
    assert receipt.join_hub_gate_trips == 0


def test_graph_and_path_receipts_are_input_order_deterministic():
    graph = _graph()
    reversed_graph = tc.make_typed_graph(graph.target_ids, reversed(graph.arcs))
    assert graph == reversed_graph
    first = tc.compose_typed_scores(
        "composer composed and born in birthplace", _scores(), graph, _policy(),
    )
    second = tc.compose_typed_scores(
        "composer composed and born in birthplace", _scores(), reversed_graph, _policy(),
    )
    np.testing.assert_array_equal(first[0], second[0])
    assert first[2] == second[2]


def test_query_boundary_accepts_raw_text_only_not_evaluator_records():
    with pytest.raises(TypeError, match="raw text"):
        tc.compose_typed_scores(
            {"question": "leak", "answer": "gold", "hop": 2},  # type: ignore[arg-type]
            _scores(),
            _graph(),
            _policy(),
        )


def test_duck_typed_claim_build_adapter_resolves_predicates_roles_and_spans():
    source_predicate = SimpleNamespace(
        source_id="work", role_id="pred:work", role="predicate",
        start=5, end=13, exact="composed",
        source_text_sha256=sha256(b"work").hexdigest(),
    )
    target_predicate = SimpleNamespace(
        source_id="composer", role_id="pred:composer", role="predicate",
        start=5, end=9, exact="born",
        source_text_sha256=sha256(b"composer").hexdigest(),
    )
    source_role = SimpleNamespace(
        source_id="work", role_id="role:composer", role="composer",
        start=20, end=28, exact="composer",
        source_text_sha256=sha256(b"work").hexdigest(),
    )
    target_role = SimpleNamespace(
        source_id="composer", role_id="role:subject", role="subject",
        start=0, end=8, exact="composer",
        source_text_sha256=sha256(b"composer").hexdigest(),
    )
    source_claim = SimpleNamespace(
        claim_id="claim:work", source_id="work",
        subject=source_role, predicate=source_predicate, arguments=(source_role,),
    )
    target_claim = SimpleNamespace(
        claim_id="claim:composer", source_id="composer",
        subject=target_role, predicate=target_predicate, arguments=(target_role,),
    )
    raw_arc = SimpleNamespace(
        arc_id="shared:composer", subject_source_id="work",
        object_source_id="composer", object_role="subject",
        origin="verified_shared_entity", claim_id="claim:work",
        target_claim_id="claim:composer",
        source_evidence_span=source_role,
        target_evidence_span=target_role,
        join_entity_id="entity:composer",
    )
    build = SimpleNamespace(
        paragraph_graph=SimpleNamespace(target_source_ids=("work", "composer")),
        paragraphs=(
            SimpleNamespace(source_id="work", title="Work", text="..."),
            SimpleNamespace(source_id="composer", title="Composer", text="..."),
        ),
        nary_claims=(source_claim, target_claim),
        directed_arcs=(raw_arc,),
        title_anchor_fallback=SimpleNamespace(evidence_spans=()),
    )
    graph = tc.graph_from_claim_build(build)
    assert len(graph.arcs) == 1
    arc = graph.arcs[0]
    assert arc.source_predicate.exact == "composed"
    assert arc.target_predicate.exact == "born"
    assert arc.source_argument_role == "composer"
    assert arc.target_argument_role == "subject"
    assert arc.join_entity_id == "entity:composer"
    assert arc.source_selector.exact == "composer"
    assert arc.target_selector.exact == "composer"
