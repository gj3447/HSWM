#!/usr/bin/env python3
"""
hswm_hypergraph 빌더 구조 불변식 테스트 (torch-free — embedding 미주입).
LakatoTree: LakatosTree_PromSearchHSWM_20260721 / P0 doc→hypergraph builder.

부정 오라클 포함(feedback: 주입된 negative oracle) — 잘못 구성하면 실패해야 하는 검사.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hswm_hypergraph import (
    build_hypergraph, default_extractor, load_badiou_findings, Vertex,
)

TOY = [
    {"rf": "T1", "clusters": ["event", "primary"], "text": "Cohen forcing, Hallward void."},
    {"rf": "T2", "clusters": ["event", "secondary"], "text": "Bosteels and Hallward on the event."},
    {"rf": "T3", "clusters": ["ethics"], "text": "No named scholars here, pure claim."},  # dangling entity-wise
]


def test_edge_per_finding():
    hg = build_hypergraph(TOY)
    assert len(hg.edges) == len(TOY), "finding 1개당 하이퍼엣지 1개"
    assert set(hg.edges) == {"T1", "T2", "T3"}


def test_entity_dedup_and_incidence():
    hg = build_hypergraph(TOY)
    # hallward는 T1·T2 양쪽 → 정점 1개, incidence 2개
    hall = hg.vertices["entity:hallward"]
    assert hall.incident_edges == ["T1", "T2"], hall.incident_edges
    # cohen은 T1만
    assert hg.vertices["entity:cohen"].incident_edges == ["T1"]


def test_topic_vertices_and_role_excluded():
    hg = build_hypergraph(TOY)
    assert "topic:event" in hg.vertices
    assert "topic:ethics" in hg.vertices
    # role축(primary/secondary/critique)은 정점화하지 않음
    assert "topic:primary" not in hg.vertices
    assert "topic:secondary" not in hg.vertices


def test_edge_value_is_finding_text():
    hg = build_hypergraph(TOY)
    assert hg.edges["T1"].value == TOY[0]["text"], "edge.value = finding 원문(읽어낼 payload)"


def test_dangling_edge_kept_as_first_class():
    hg = build_hypergraph(TOY)
    # T3: entity 없음. 단 topic:ethics는 묶임 → arity>=1. entity 없는 fact도 E로 존속.
    assert "T3" in hg.edges
    assert hg.edges["T3"].arity >= 1  # topic:ethics 최소
    # entity 전무 finding은 dangling에 안 잡힘(topic이 있으니). entity·topic 다 없으면 dangling.
    only_claim = build_hypergraph([{"rf": "X", "clusters": [], "text": "nothing named."}])
    assert only_claim.dangling_edges() == ["X"]
    assert "X" in only_claim.edges, "정점 0개여도 하이퍼엣지는 1급으로 존속"


def test_union_units_count_and_order():
    hg = build_hypergraph(TOY)
    units = hg.units()
    assert len(units) == len(hg.vertices) + len(hg.edges), "V∪E = |V|+|E|"
    kinds = [k for k, _ in units]
    assert kinds == sorted(kinds, key=lambda k: 0 if k == "V" else 1), "V 먼저, E 나중(결정론)"


def test_determinism():
    a = build_hypergraph(TOY)
    b = build_hypergraph(TOY)
    assert a.units() == b.units()
    assert [a.edges[e].members for e in sorted(a.edges)] == \
           [b.edges[e].members for e in sorted(b.edges)]


def test_duplicate_finding_id_rejected():
    dup = TOY + [{"rf": "T1", "clusters": [], "text": "collision"}]
    try:
        build_hypergraph(dup)
    except ValueError:
        return
    raise AssertionError("중복 finding id는 거부되어야 함")


def test_negative_oracle_broken_incidence_detected():
    """부정 오라클: incidence를 손상시키면 check_incidence가 반드시 잡아야 한다."""
    hg = build_hypergraph(TOY)
    # 엣지 members에 유령 정점 주입 → 비대칭
    hg.edges["T1"].members.append("entity:ghost")
    try:
        hg.check_incidence()
    except AssertionError:
        return
    raise AssertionError("손상된 incidence를 check_incidence가 못 잡음 — 오라클 무효")


def test_embed_injection_populates_both_v_and_e():
    """embed 주입 시 V·E 양쪽 embedding이 채워지고 순서 정합."""
    seen = {}

    def fake_embed(texts):
        # 각 텍스트를 길이-기반 1D 벡터로 (결정론, torch 불필요)
        for i, t in enumerate(texts):
            seen[i] = t
        return [[float(len(t))] for t in texts]

    hg = build_hypergraph(TOY, embed=fake_embed)
    assert all(v.embedding is not None for v in hg.vertices.values())
    assert all(e.embedding is not None for e in hg.edges.values())
    # 첫 정점 임베딩 = 그 embed_text 길이
    v0 = sorted(hg.vertices)[0]
    assert hg.vertices[v0].embedding == [float(len(hg.vertices[v0].embed_text))]


def test_real_badiou_builds():
    findings = load_badiou_findings()
    hg = build_hypergraph(findings)
    assert len(hg.edges) == len(findings) == 24
    hg.check_incidence()
    # 최소 몇몇 핵심 entity 존재
    assert "entity:hallward" in hg.vertices
    # hallward는 다수 finding 언급 → hub
    assert len(hg.vertices["entity:hallward"].incident_edges) >= 5


if __name__ == "__main__":
    fns = [g for n, g in sorted(globals().items()) if n.startswith("test_")]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} PASS")
