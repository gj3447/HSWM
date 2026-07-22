"""T0 chain-viability gate teeth — synthetic fixtures only (no arm outputs).

The ledger must mirror the traversal kernel's structural admission exactly:
claim continuity, join distinctness, backtrack rejection, fanout/hub bounds,
and must be deterministic and content-addressed.
"""
from __future__ import annotations

from hashlib import sha256

import typed_composition as tc
from chain_viability import enumerate_admissible_chains, ledger_as_json


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


IDS = ("p0", "p1", "p2", "p3", "p4")


def _arc(arc_id, source, target, join, *, source_claim=None, target_claim="set"):
    source_id, target_id = IDS[source], IDS[target]
    target_claim_id = f"claim:{target_id}" if target_claim == "set" else target_claim
    return tc.TypedEvidenceArcV1(
        arc_id=arc_id,
        source_target=source,
        target_target=target,
        source_id=source_id,
        target_id=target_id,
        source_claim_id=source_claim or f"claim:{source_id}",
        target_claim_id=target_claim_id,
        source_predicate=_span(source_id, "predicate", "relates"),
        target_predicate=(
            _span(target_id, "predicate", "relates")
            if target_claim_id is not None else None
        ),
        source_argument_role="object",
        target_argument_role="subject",
        join_entity_id=join,
        source_selector=_span(source_id, "object", target_id, start=20),
        target_selector=_span(target_id, "subject", target_id),
        origin=("verified_shared_entity" if target_claim_id is not None
                else "verified_nary_title"),
    )


def _graph(arcs):
    return tc.make_typed_graph(IDS, tuple(arcs))


def test_legal_chain_is_counted_once():
    # p0 -> p1 (lands claim:p1) -> p2 : continuity + distinct joins + no cycle.
    ledger = enumerate_admissible_chains(_graph([
        _arc("a", 0, 1, "entity:j1"),
        _arc("b", 1, 2, "entity:j2", source_claim="claim:p1"),
    ]))
    assert ledger.admissible_chain_count == 1
    assert ledger.verdict == "T0_PASS"
    chain = ledger.chains[0]
    assert (chain.first_arc_id, chain.second_arc_id) == ("a", "b")
    assert chain.shared_claim_id == "claim:p1"


def test_claim_discontinuity_is_rejected():
    # Second arc leaves p1 from a DIFFERENT claim — paragraph adjacency alone
    # must not count (this is exactly the H3-C0 "paragraph-only simple pair").
    ledger = enumerate_admissible_chains(_graph([
        _arc("a", 0, 1, "entity:j1"),
        _arc("b", 1, 2, "entity:j2", source_claim="claim:other"),
    ]))
    assert ledger.admissible_chain_count == 0
    assert ledger.verdict == "PRECOMPUTE_NOOP_DEPTH2"


def test_backtrack_is_rejected():
    # p0 -> p1 -> p0 : the H3-C0 2Wiki "immediate backtrack" shape.
    ledger = enumerate_admissible_chains(_graph([
        _arc("a", 0, 1, "entity:j1"),
        _arc("b", 1, 0, "entity:j2", source_claim="claim:p1"),
    ]))
    assert ledger.admissible_chain_count == 0


def test_join_reuse_is_rejected():
    ledger = enumerate_admissible_chains(_graph([
        _arc("a", 0, 1, "entity:same"),
        _arc("b", 1, 2, "entity:same", source_claim="claim:p1"),
    ]))
    assert ledger.admissible_chain_count == 0


def test_title_terminal_first_edge_cannot_continue():
    ledger = enumerate_admissible_chains(_graph([
        _arc("a", 0, 1, "entity:j1", target_claim=None),
        _arc("b", 1, 2, "entity:j2", source_claim="claim:p1"),
    ]))
    assert ledger.admissible_chain_count == 0
    assert ledger.nonterminal_arc_count == 1


def test_hub_join_degree_trips():
    arcs = [_arc("a", 0, 1, "entity:hub"),
            _arc("b", 1, 2, "entity:j2", source_claim="claim:p1")]
    # Blow up the hub's incident-source set beyond max_join_degree.
    for i, (s, t) in enumerate(((2, 3), (3, 4), (4, 2), (2, 4), (3, 2))):
        arcs.append(_arc(f"hub{i}", s, t, "entity:hub"))
    policy = tc.TypedCompositionPolicyV1(max_join_degree=2)
    ledger = enumerate_admissible_chains(_graph(arcs), policy)
    assert all(c.first_join_entity_id != "entity:hub" for c in ledger.chains)
    assert ledger.admissible_chain_count == 0


def test_determinism_and_content_address():
    arcs = [
        _arc("a", 0, 1, "entity:j1"),
        _arc("b", 1, 2, "entity:j2", source_claim="claim:p1"),
        _arc("c", 1, 3, "entity:j3", source_claim="claim:p1"),
    ]
    one = enumerate_admissible_chains(_graph(arcs))
    two = enumerate_admissible_chains(_graph(list(reversed(arcs))))
    assert one.admissible_chain_count == two.admissible_chain_count == 2
    assert one.ledger_sha256 == two.ledger_sha256
    assert ledger_as_json(one) == ledger_as_json(two)
    assert [
        (c.first_arc_id, c.second_arc_id) for c in one.chains
    ] == [("a", "b"), ("a", "c")]
