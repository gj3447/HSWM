#!/usr/bin/env python3
"""
B0 field 대수 법칙 테스트 (L1–L4 + fail-closed + CRDT dedup).
DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md §3.4. 벤치 주장 없음 — 순수 대수만.
실행: python -m pytest test_hswm_field_algebra.py -q
"""
from __future__ import annotations

import pytest

from hswm_hypergraph import build_hypergraph
from hswm_field_algebra import (
    Field, SeamArc, compose, field_id, merge, merge_all, reassemble, split,
)

LEX = ["lacan", "zizek", "badiou", "cohen", "hallward"]


def mk_field(findings, sources, ledger=(), seam=()):
    hg = build_hypergraph(findings, extractor=lambda t: {e for e in LEX if e in t.lower()})
    prov = {eid: tuple(sorted(sources[eid])) for eid in hg.edges}
    return Field(hg=hg, provenance=prov, ledger=frozenset(ledger), seam=tuple(seam))


@pytest.fixture
def fields():
    a = mk_field(
        [{"rf": "a1", "text": "lacan on the real", "clusters": ["psycho"]},
         {"rf": "sh", "text": "cohen forcing shared", "clusters": ["set"]}],
        {"a1": {"srcA"}, "sh": {"srcA", "srcB"}},
        ledger={"ev-a1"},
    )
    b = mk_field(
        [{"rf": "b1", "text": "zizek reads hallward", "clusters": ["politics"]},
         {"rf": "sh", "text": "cohen forcing shared", "clusters": ["set"]}],
        {"b1": {"srcB"}, "sh": {"srcA", "srcB"}},
        ledger={"ev-b1"},
    )
    c = mk_field(
        [{"rf": "c1", "text": "badiou event axiom", "clusters": ["ontology"]}],
        {"c1": {"srcC"}},
    )
    return a, b, c


def test_L1_merge_commutative(fields):
    a, b, _ = fields
    assert field_id(merge(a, b)) == field_id(merge(b, a))


def test_L2_merge_associative(fields):
    a, b, c = fields
    assert field_id(merge(merge(a, b), c)) == field_id(merge(a, merge(b, c)))


def test_L3_merge_idempotent(fields):
    a, _, _ = fields
    assert field_id(merge(a, a)) == field_id(a)


def test_L4_split_merge_roundtrip(fields):
    a, b, _ = fields
    arc = SeamArc(arc_id="s1", left_vid="entity:lacan", right_vid="entity:zizek",
                  evidence="test canonical pair", event_id="ev-s1")
    whole = merge(a, b, new_seam=(arc,))
    parts, crossing = split(whole, part_of=lambda s: "A" if s == "srcA" else "B")
    # 다중소스 엣지 sh는 양쪽 파트에 같은 eid로 복제
    assert "sh" in parts["A"].hg.edges and "sh" in parts["B"].hg.edges
    # lacan(A)–zizek(B) arc는 파트를 가로지름 → 벗겨짐
    assert [x.arc_id for x in crossing] == ["s1"]
    rebuilt = reassemble(parts, crossing)
    assert field_id(rebuilt) == field_id(whole)  # 비트동일 왕복


def test_L3_crdt_dedup_no_square_corruption(fields):
    """재merge가 ledger·provenance를 제곱 누적시키지 않음 (S1 제곱부패 교훈)."""
    a, b, _ = fields
    once = merge(a, b)
    twice = merge(once, b)
    assert field_id(twice) == field_id(once)
    assert twice.ledger == frozenset({"ev-a1", "ev-b1"})


def test_fail_closed_same_eid_different_payload(fields):
    a, _, _ = fields
    rogue = mk_field(
        [{"rf": "sh", "text": "DIFFERENT payload", "clusters": ["set"]}],
        {"sh": {"srcZ"}},
    )
    with pytest.raises(ValueError, match="엣지 충돌"):
        merge(a, rogue)


def test_fail_closed_vertex_kind_conflict():
    x = mk_field([{"rf": "x1", "text": "lacan", "clusters": ["k"]}], {"x1": {"s1"}})
    y_hg = build_hypergraph(
        [{"rf": "y1", "text": "no entity here", "clusters": ["lacan"]}],
        extractor=lambda t: set())  # 'lacan'이 topic 정점으로 등장 → kind 충돌 아님(vid 다름)
    y = Field(hg=y_hg, provenance={"y1": ("s2",)}, ledger=frozenset(), seam=())
    merged = merge(x, y)  # entity:lacan vs topic:lacan — vid가 달라 공존 (정상)
    assert "entity:lacan" in merged.hg.vertices and "topic:lacan" in merged.hg.vertices


def test_seam_arc_requires_existing_vertices(fields):
    a, _, _ = fields
    ghost = SeamArc(arc_id="g", left_vid="entity:ghost", right_vid="entity:lacan",
                    evidence="", event_id="ev-g")
    with pytest.raises(ValueError, match="미존재 정점"):
        merge(a, a, new_seam=(ghost,))


def test_compose_is_single_call(fields):
    """R4: 적용 = 함수 하나. compose 결과는 merge_all과 동일."""
    a, b, c = fields
    assert field_id(compose([a, b, c])) == field_id(merge_all([a, b, c]))


def test_provenance_required():
    hg = build_hypergraph([{"rf": "p1", "text": "cohen", "clusters": []}],
                          extractor=lambda t: {"cohen"})
    with pytest.raises(ValueError, match="provenance 없는 엣지"):
        Field(hg=hg, provenance={}, ledger=frozenset(), seam=())
