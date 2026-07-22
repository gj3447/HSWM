"""Deterministic weave arm teeth — synthetic fixtures only, no V5 artifacts.

Covers: C1 title-subject continuation, C2 canonical entity (parenthetical
strip + homonym-anchor drop), C3 sibling-subject handoff, reversibility
(strip restores frozen topology bit-exactly), and receipt completeness.
"""
from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace

import typed_composition as tc
from chain_viability import enumerate_admissible_chains
from claim_weave import (
    apply_weave, canonical_title_key, strip_weave,
    weave_c1, weave_c2, weave_c3,
)
from claim_builder import ArgumentRoleV1, NaryClaimV1


def _role(source_id: str, role: str, exact: str, *, start: int = 0,
          kind: str = "entity") -> ArgumentRoleV1:
    return ArgumentRoleV1(
        role_id=f"role:{source_id}:{role}:{start}:{exact}",
        source_id=source_id,
        role_kind=kind,
        role=role,
        start=start,
        end=start + len(exact),
        exact=exact,
        prefix="",
        suffix="",
        source_text_sha256=sha256(f"{source_id}:body".encode()).hexdigest(),
    )


def _claim(claim_id: str, source_id: str, subject: str, predicate: str,
           args: list[tuple[str, str]]) -> NaryClaimV1:
    return NaryClaimV1(
        claim_id=claim_id,
        source_id=source_id,
        subject=_role(source_id, "subject", subject),
        predicate=_role(source_id, "predicate", predicate, start=200, kind="predicate"),
        arguments=tuple(
            _role(source_id, role, exact, start=100 + 40 * i)
            for i, (role, exact) in enumerate(args)
        ),
        observation_ids=("obs:" + claim_id,),
    )


IDS = ("p_film", "p_director", "p_mother", "p_decoy")
TITLES = {
    "p_film": "Polish-Russian War (film)",
    "p_director": "Xawery Zulawski",
    "p_mother": "Malgorzata Braunek",
    "p_decoy": "Unrelated Page",
}

CLAIMS = (
    _claim("c:film", "p_film", "Polish-Russian War", "was directed by",
           [("director", "Xawery Zulawski")]),
    _claim("c:director", "p_director", "Xawery Zulawski", "is the son of",
           [("mother", "Malgorzata Braunek")]),
    _claim("c:director2", "p_decoy", "Xawery Zulawski", "also directed",
           [("work", "Snow White")]),
    _claim("c:mother", "p_mother", "Malgorzata Braunek", "acted in",
           [("work", "The Third Part of the Night")]),
)

BUILD = SimpleNamespace(nary_claims=CLAIMS)


def _title_terminal_arc() -> tc.TypedEvidenceArcV1:
    """Frozen-style terminal: film claim's director argument -> title page."""
    film = CLAIMS[0]
    director_role = film.arguments[0]
    title = TITLES["p_director"]
    return tc.TypedEvidenceArcV1(
        arc_id="frozen:title:film->director",
        source_target=0, target_target=1,
        source_id="p_film", target_id="p_director",
        source_claim_id="c:film", target_claim_id=None,
        source_predicate=tc.SelectorSpanV1(
            source_id="p_film", role_id=film.predicate.role_id,
            role="predicate", text_scope="body",
            start=film.predicate.start, end=film.predicate.end,
            exact=film.predicate.exact,
            source_text_sha256=film.predicate.source_text_sha256),
        target_predicate=None,
        source_argument_role="director", target_argument_role="title",
        join_entity_id="surface:xawery zulawski",
        source_selector=tc.SelectorSpanV1(
            source_id="p_film", role_id=director_role.role_id,
            role="director", text_scope="body",
            start=director_role.start, end=director_role.end,
            exact=director_role.exact,
            source_text_sha256=director_role.source_text_sha256),
        target_selector=tc.SelectorSpanV1(
            source_id="p_director", role_id="title:p_director",
            role="title", text_scope="title",
            start=0, end=len(title), exact=title,
            source_text_sha256=sha256(title.encode()).hexdigest()),
        origin="verified_nary_title",
    )


def _mother_arc() -> tc.TypedEvidenceArcV1:
    """Frozen-style nonterminal: director claim -> mother page claim."""
    director = CLAIMS[1]
    mother_claim = CLAIMS[3]
    role = director.arguments[0]
    return tc.TypedEvidenceArcV1(
        arc_id="frozen:shared:director->mother",
        source_target=1, target_target=2,
        source_id="p_director", target_id="p_mother",
        source_claim_id="c:director", target_claim_id="c:mother",
        source_predicate=tc.SelectorSpanV1(
            source_id="p_director", role_id=director.predicate.role_id,
            role="predicate", text_scope="body",
            start=director.predicate.start, end=director.predicate.end,
            exact=director.predicate.exact,
            source_text_sha256=director.predicate.source_text_sha256),
        target_predicate=tc.SelectorSpanV1(
            source_id="p_mother", role_id=mother_claim.predicate.role_id,
            role="predicate", text_scope="body",
            start=mother_claim.predicate.start, end=mother_claim.predicate.end,
            exact=mother_claim.predicate.exact,
            source_text_sha256=mother_claim.predicate.source_text_sha256),
        source_argument_role="mother", target_argument_role="subject",
        join_entity_id="surface:malgorzata braunek",
        source_selector=tc.SelectorSpanV1(
            source_id="p_director", role_id=role.role_id, role="mother",
            text_scope="body", start=role.start, end=role.end, exact=role.exact,
            source_text_sha256=role.source_text_sha256),
        target_selector=tc.SelectorSpanV1(
            source_id="p_mother", role_id=mother_claim.subject.role_id,
            role="subject", text_scope="body",
            start=mother_claim.subject.start, end=mother_claim.subject.end,
            exact=mother_claim.subject.exact,
            source_text_sha256=mother_claim.subject.source_text_sha256),
        origin="verified_shared_entity",
    )


def _base_graph() -> tc.TypedCompositionGraphV1:
    return tc.make_typed_graph(IDS, (_title_terminal_arc(), _mother_arc()))


def test_frozen_baseline_has_zero_chains():
    # Terminal first edge cannot continue: the H3-C0 failure shape.
    ledger = enumerate_admissible_chains(_base_graph())
    assert ledger.admissible_chain_count == 0
    assert ledger.verdict == "PRECOMPUTE_NOOP_DEPTH2"


def test_c1_title_subject_weave_unlocks_chain():
    base = _base_graph()
    w1 = weave_c1(BUILD, TITLES, base)
    assert len(w1.arcs) == 1
    woven = w1.arcs[0]
    assert woven.origin == "woven_c1_title_subject"
    assert woven.target_claim_id == "c:director"
    ledger = enumerate_admissible_chains(apply_weave(base, [w1]))
    # film --(woven c1)--> director claim --(frozen)--> mother
    assert ledger.admissible_chain_count == 1
    assert ledger.verdict == "T0_PASS"
    assert ledger.chains[0].shared_claim_id == "c:director"


def test_c2_canonical_entity_strips_parenthetical():
    assert canonical_title_key("Polish-Russian War (film)") == "polish-russian war"
    base = _base_graph()
    w2 = weave_c2(BUILD, TITLES, base)
    # director argument "Xawery Zulawski" resolves to anchor p_director and
    # weaves to BOTH claims whose subject is that canonical entity.
    pairs = {(a.source_claim_id, a.target_claim_id) for a in w2.arcs}
    assert ("c:film", "c:director") in pairs
    assert ("c:film", "c:director2") in pairs
    ledger = enumerate_admissible_chains(apply_weave(base, [w2]))
    assert ledger.admissible_chain_count >= 1


def test_c2_homonym_anchor_is_dropped():
    titles = dict(TITLES)
    titles["p_decoy"] = "Xawery Zulawski (footballer)"  # same canonical key
    w2 = weave_c2(BUILD, titles, _base_graph())
    # anchor "xawery zulawski" now maps to two paragraphs -> dropped entirely.
    assert all(a.join_entity_id != "canonical:xawery zulawski" for a in w2.arcs)


def test_c3_sibling_subject_handoff():
    base = _base_graph()
    w3 = weave_c3(BUILD, TITLES, base)
    pairs = {(a.source_claim_id, a.target_claim_id) for a in w3.arcs}
    # The two Zulawski-subject claims hand off to each other across paragraphs.
    assert ("c:director", "c:director2") in pairs
    assert ("c:director2", "c:director") in pairs
    for arc in w3.arcs:
        assert arc.origin == "woven_c3_sibling_subject_handoff"


def test_reversibility_strip_restores_frozen_topology():
    base = _base_graph()
    w1 = weave_c1(BUILD, TITLES, base)
    w2 = weave_c2(BUILD, TITLES, base)
    w3 = weave_c3(BUILD, TITLES, base)
    woven = apply_weave(base, [w1, w2, w3])
    stripped = strip_weave(woven)
    canonical_base = tc.make_typed_graph(
        base.target_ids, tuple(sorted(base.arcs, key=lambda a: a.arc_id)))
    assert stripped.topology_sha256 == canonical_base.topology_sha256
    assert stripped.arcs == canonical_base.arcs


def test_every_woven_arc_has_receipt_with_both_spans():
    base = _base_graph()
    for weave in (weave_c1(BUILD, TITLES, base), weave_c2(BUILD, TITLES, base),
                  weave_c3(BUILD, TITLES, base)):
        assert len(weave.arcs) == len(weave.receipts)
        by_id = {r.arc_id: r for r in weave.receipts}
        for arc in weave.arcs:
            receipt = by_id[arc.arc_id]
            assert receipt.left_exact and receipt.right_exact
            assert receipt.canonical_key
