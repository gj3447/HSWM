"""QKV-R1 ordered-routing teeth: K2 necessity, refusal, and receipts."""
from __future__ import annotations

from dataclasses import replace

import qkv_routing as qkv


def _record(
    record_id: str,
    source: str,
    predicate: str,
    target: str,
) -> qkv.EvidenceKVV1:
    value = f"Entity {target}"
    source_text = f"Entity {source} {predicate} {value}."
    target_text = f"{value} is the subject of record {target}."
    return qkv.EvidenceKVV1(
        record_id=record_id,
        source_frontier=source,
        predicate=predicate,
        target_frontier=target,
        source_selector=qkv.bind_exact_selector(source, source_text, value),
        target_selector=qkv.bind_exact_selector(target, target_text, value),
    )


def _records() -> tuple[qkv.EvidenceKVV1, ...]:
    # Same key multiset, different order:
    #   A --alpha--> B --beta--> D
    #   A --beta-->  C --alpha--> E
    return (
        _record("a-alpha-b", "A", "alpha relation", "B"),
        _record("a-beta-c", "A", "beta relation", "C"),
        _record("b-beta-d", "B", "beta relation", "D"),
        _record("c-alpha-e", "C", "alpha relation", "E"),
    )


def _graph() -> qkv.QKVGraphV1:
    return qkv.make_qkv_graph(_records())


def test_ordered_relation_pair_routes_to_distinct_k2_values_and_k1_cannot():
    graph = _graph()
    alpha_beta = qkv.QueryProgramV1(
        initial_frontier="A",
        relations=("alpha relation", "beta relation"),
    )
    beta_alpha = qkv.QueryProgramV1(
        initial_frontier="A",
        relations=("beta relation", "alpha relation"),
    )

    ab_full = qkv.route_full(graph, alpha_beta)
    ba_full = qkv.route_full(graph, beta_alpha)
    ab_k1 = qkv.route_k1(graph, alpha_beta)
    ba_k1 = qkv.route_k1(graph, beta_alpha)

    assert ab_full.status == ba_full.status == "PASS"
    assert (ab_full.final_frontier, ba_full.final_frontier) == ("D", "E")
    assert ab_full.completed_steps == ba_full.completed_steps == 2
    assert ab_k1.status == ba_k1.status == "PARTIAL"
    assert (ab_k1.final_frontier, ba_k1.final_frontier) == ("B", "C")
    assert {ab_k1.final_frontier, ba_k1.final_frontier}.isdisjoint({"D", "E"})


def test_value_becomes_next_query_frontier_with_a_digest_chained_receipt():
    receipt = qkv.route_full(
        _graph(),
        qkv.QueryProgramV1("A", ("alpha relation", "beta relation")),
    )
    first, second = receipt.steps

    assert first.value.target_frontier == first.q_after.frontier == "B"
    assert first.q_after == second.q_before
    assert first.q_after_sha256 == second.q_before_sha256
    assert first.q_after.relation == "beta relation"
    assert second.value.target_frontier == second.q_after.frontier == "D"
    assert second.q_after.relation is None
    assert first.value.source_selector.exact == "Entity B"
    assert first.value.target_selector.exact == "Entity B"
    assert second.value.source_selector.exact == "Entity D"
    assert second.value.target_selector.exact == "Entity D"


def test_unseen_second_relation_refuses_atomically_without_partial_route():
    receipt = qkv.route_full(
        _graph(),
        qkv.QueryProgramV1("A", ("alpha relation", "unseen relation")),
    )

    assert receipt.status == "REFUSED"
    assert receipt.refusal_code == "NO_KEY_MATCH"
    assert receipt.refusal_depth == 2
    assert receipt.final_frontier == receipt.initial_frontier == "A"
    assert receipt.completed_steps == 0
    assert receipt.steps == ()


def test_ambiguous_second_key_refuses_atomically_instead_of_tie_breaking():
    records = (*_records(), _record("b-beta-x", "B", "beta relation", "X"))
    graph = qkv.make_qkv_graph(records)
    receipt = qkv.route_full(
        graph,
        qkv.QueryProgramV1("A", ("alpha relation", "beta relation")),
    )

    assert receipt.status == "REFUSED"
    assert receipt.refusal_code == "AMBIGUOUS_KEY_MATCH"
    assert receipt.refusal_depth == 2
    assert receipt.final_frontier == "A"
    assert receipt.completed_steps == 0
    assert receipt.steps == ()


def test_record_input_order_and_repeated_runs_are_bit_deterministic():
    forward = qkv.make_qkv_graph(_records())
    reverse = qkv.make_qkv_graph(tuple(reversed(_records())))
    program = qkv.QueryProgramV1(
        "A", ("alpha relation", "beta relation"),
    )

    assert forward == reverse
    first = qkv.route_full(forward, program)
    again = qkv.route_full(forward, program)
    reordered = qkv.route_full(reverse, program)
    assert first == again == reordered
    assert first.receipt_id == again.receipt_id == reordered.receipt_id
    assert first.route_sha256 == again.route_sha256 == reordered.route_sha256


def test_graph_hash_drift_is_rejected_before_routing():
    graph = _graph()
    forged = replace(graph, graph_sha256="0" * 64)
    program = qkv.QueryProgramV1("A", ("alpha relation",))

    try:
        qkv.route_full(forged, program)
    except qkv.QKVIntegrityError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("forged graph hash was accepted")
