#!/usr/bin/env python3
"""B2 cross-field merge 하니스 — synthetic 테스트 (실측 아님).

fixture = 손으로 지은 2Wiki 형 row + 결정론 hash embedder. 실 벤치 데이터·실 임베딩
모델·prereg 어느 것도 건드리지 않는다. 이 테스트가 green이어도 F-B2a/b/c에 대한
증거는 0 — 구조(분할·계층화·seam·recall·evidence shape)만 검증한다.
실행: python -m pytest test_hswm_b2_crossfield.py -q
"""
from __future__ import annotations

import hashlib
import math

import pytest

from prom_b2_crossfield_merge import (
    attach_embeddings, build_field, collect_texts, compose, finding_text, merge,
    paragraphs_from_rows, rank_paragraphs, recall_at, run_experiment,
    seam_arcs_between, stratify, title_parity,
)


def hash_embed(texts: list[str]) -> list[list[float]]:
    """결정론 hash embedder — 동일 텍스트 ⇔ 동일 단위벡터. 의미 없음(구조 테스트 전용)."""
    out = []
    for t in texts:
        digest = hashlib.sha256(t.encode("utf-8")).digest()
        vec = [b - 127.5 for b in digest]
        norm = math.sqrt(sum(x * x for x in vec))
        out.append([x / norm for x in vec])
    return out


def titles_by_parity(n: int = 60) -> tuple[list[str], list[str]]:
    """digit 포함 제목(entity 추출 안 됨)을 짝홀로 분류해 A/B 제목 풀 확보."""
    a, b = [], []
    for i in range(n):
        t = f"T{i}"
        (a if title_parity(t) == "A" else b).append(t)
    return a, b


def mk_row(rid: str, question: str, pairs: list[tuple[str, str]],
           supporting: list[str]) -> dict:
    return {
        "id": rid, "question": question, "answer": "x", "type": "compositional",
        "supporting_facts": {"title": supporting, "sent_id": [0] * len(supporting)},
        "context": {"title": [t for t, _ in pairs],
                    "sentences": [[s] for _, s in pairs]},
    }


TA, TB = titles_by_parity()


@pytest.fixture
def rows():
    # cross row: gold이 A/B 양쪽. 두 gold 문단은 entity "Zorblax" 공유(seam 교량 재료).
    cross = mk_row(
        "r-cross",
        finding_text(TA[0], "Zorblax visited Mereworth."),  # 질의 = gold-A 문단 원문
        [(TA[0], "Zorblax visited Mereworth."),
         (TB[0], "Zorblax founded Blergstad."),
         (TA[1], "Quuxone wrote nothing here."),
         (TB[1], "Quuxtwo sailed elsewhere.")],
        supporting=[TA[0], TB[0]],
    )
    # in-field row: gold 둘 다 A쪽.
    infield = mk_row(
        "r-in",
        finding_text(TA[2], "Frobnak painted Vexampolis."),
        [(TA[2], "Frobnak painted Vexampolis."),
         (TA[3], "Frobnak died in Vexampolis."),
         (TB[2], "Quuxthree hummed a tune.")],
        supporting=[TA[2], TA[3]],
    )
    return [cross, infield]


# (i) 짝홀 분할: 결정론 + disjoint
def test_parity_partition_deterministic_and_disjoint(rows):
    p1 = paragraphs_from_rows(rows)
    p2 = paragraphs_from_rows(rows)
    assert p1 == p2  # 결정론
    a_pids = {pid for pid, r in p1.items() if r["field"] == "A"}
    b_pids = {pid for pid, r in p1.items() if r["field"] == "B"}
    assert a_pids and b_pids and not (a_pids & b_pids)  # disjoint 양쪽 비어있지 않음
    for rec in p1.values():
        assert rec["field"] == title_parity(rec["title"])


# (ii-a) 계층화: gold이 양쪽 field → cross_field
def test_stratification_cross_field(rows):
    klass, gold = stratify(rows[0])
    assert klass == "cross_field" and len(gold) == 2


# (ii-b) 계층화: gold이 한쪽 field → in_field
def test_stratification_in_field(rows):
    klass, gold = stratify(rows[1])
    assert klass == "in_field" and len(gold) == 2


# (iii) seam arc는 다른 field의 동일 정규화 이름 정점 사이에만
def test_seam_arcs_equal_name_cross_field_only(rows):
    pool = paragraphs_from_rows(rows)
    f_a, f_b = build_field(pool, "A"), build_field(pool, "B")
    arcs = seam_arcs_between(f_a, f_b)
    assert arcs, "공유 entity Zorblax가 있으므로 seam이 최소 1개"
    names = set()
    for arc in arcs:
        assert arc.left_vid.startswith("entity:A/")
        assert arc.right_vid.startswith("entity:B/")
        left = arc.left_vid.split("/", 1)[1]
        right = arc.right_vid.split("/", 1)[1]
        assert left == right  # 정규화 이름 동일한 쌍에만
        names.add(left)
    assert "zorblax" in names
    assert "quuxone" not in names and "mereworth" not in names  # 한쪽 전용 entity 제외


# (iv) merged_no_seam(compose)에는 seam arc 0개
def test_merged_no_seam_has_zero_seam_arcs(rows):
    pool = paragraphs_from_rows(rows)
    f_a, f_b = build_field(pool, "A"), build_field(pool, "B")
    assert compose([f_a, f_b]).seam == ()
    assert len(merge(f_a, f_b, new_seam=seam_arcs_between(f_a, f_b)).seam) >= 1


# (v) recall 계산: 손으로 지은 랭킹에서 정확
def test_recall_computation_on_crafted_ranking():
    assert recall_at(["p1", "p2", "p3"], {"p1", "p9"}, 10) == 0.5
    assert recall_at(["p9", "p1"], {"p1", "p9"}, 2) == 1.0
    assert recall_at(["p9", "p1"], {"p1", "p9"}, 1) == 0.5
    assert recall_at(["p2"], {"p1"}, 10) == 0.0
    assert recall_at([], set(), 10) == 0.0


# (vi) evidence dict shape: F-B2a/b/c 키 전부 존재
def test_evidence_shape_has_all_falsifier_keys(rows):
    ev = run_experiment(rows, hash_embed, n_q=None, seed=7, bootstrap_reps=50)
    m = ev["measurement"]
    for fal in ("f_b2a", "f_b2b", "f_b2c"):
        assert "delta" in m[fal] and "bootstrap95" in m[fal]
        assert len(m[fal]["bootstrap95"]) == 2
    assert m["f_b2a"]["check_lower_gt_0"] in (True, False)
    assert m["f_b2b"]["noise_band"] > 0 and "check_no_harm" in m["f_b2b"]
    assert "check_lower_gt_0" in m["f_b2c"]
    for cls in ("cross_field", "in_field"):
        blk = m["per_class"][cls]
        assert blk["n"] >= 1
        for key in ("merged_recall10", "best_single_recall10", "merged_no_seam_recall10"):
            assert key in blk
    for key in ("field_id_a", "field_id_b", "field_id_merged",
                "field_id_merged_no_seam", "n_seam_arcs"):
        assert key in ev["fields"]
    assert len(ev["fields"]["field_id_a"]) == 64
    assert ev["sample"]["seed"] == 7
    # seam ablation arm은 merged와 field_id가 달라야 함 (seam 유무)
    assert ev["fields"]["field_id_merged"] != ev["fields"]["field_id_merged_no_seam"]


# (vii) seam bridge 기전: seam이 있으면 cross-field gold 점수가 정확히 bridge만큼 상승
def test_seam_bridge_lifts_crossfield_gold(rows):
    pool = paragraphs_from_rows(rows)
    f_a, f_b = build_field(pool, "A"), build_field(pool, "B")
    arcs = seam_arcs_between(f_a, f_b)
    f_merged = merge(f_a, f_b, new_seam=arcs)
    f_no_seam = compose([f_a, f_b])
    query = finding_text(TA[0], "Zorblax visited Mereworth.")  # == gold-A 문단 원문
    texts = collect_texts([f_a, f_b, f_merged, f_no_seam], [query])
    table = dict(zip(texts, hash_embed(texts)))
    for f in (f_merged, f_no_seam):
        attach_embeddings(f, table)
    qv = table[query]
    gold_b = next(pid for pid, r in pool.items() if r["title"] == TB[0])
    k = len(pool)
    with_seam = dict(rank_paragraphs(f_merged, qv, top_k=k))
    without = dict(rank_paragraphs(f_no_seam, qv, top_k=k))
    # gold-B는 seam을 통해서만 gold-A(cos=1)의 bridge를 받는다 → 점수 순증
    assert with_seam[gold_b] > without[gold_b] + 0.2
    rank_with = [eid for eid, _ in sorted(with_seam.items(), key=lambda r: (-r[1], r[0]))]
    rank_without = [eid for eid, _ in sorted(without.items(), key=lambda r: (-r[1], r[0]))]
    assert rank_with.index(gold_b) <= rank_without.index(gold_b)
