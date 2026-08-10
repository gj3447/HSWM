#!/usr/bin/env python3
"""
hswm_null_battery B0 테스트 — 결정론 + 대조군 불변식 + 감사 판정.
seed-rf-hswm4-null-battery-confound-audit-20260725. 벤치 주장 없음 — 순수 null/audit만.
실행: python -m pytest test_hswm_null_battery.py -q
"""
from __future__ import annotations

import pytest

from hswm_null_battery import (
    canary_detected, degree_preserving_shuffle, degree_sequence,
    deranged_placebo_store, disjoint_audit, headroom_band_ok,
    make_canary, random_edit_plan, run_verdict,
)


# --- headroom band ---

def test_headroom_band_accepts_mid_range():
    assert headroom_band_ok(0.5)
    assert headroom_band_ok(0.3) and headroom_band_ok(0.7)


def test_headroom_band_rejects_saturation_and_floor():
    assert not headroom_band_ok(5 / 6)   # p1v2형 포화
    assert not headroom_band_ok(0.1)     # 바닥


# --- placebo store ---

def test_placebo_preserves_schema_and_replaces_content():
    store = {"l1": "alpha lesson", "l2": "beta lesson", "l3": "gamma lesson"}
    pool = [f"unrelated domain content {i}" for i in range(10)]
    p = deranged_placebo_store(store, pool, seed="s1")
    assert sorted(p) == sorted(store)                    # 동일 id 집합
    assert len(p) == len(store)                          # 동일 크기
    assert all(v.startswith("unrelated") for v in p.values())  # 내용 무관 풀
    assert not any(p[k] == store[k] for k in store)      # 내용 전부 교체


def test_placebo_deterministic_and_fail_closed():
    store = {"a": "x", "b": "y"}
    pool = ["p1", "p2", "p3"]
    assert deranged_placebo_store(store, pool, "s") == deranged_placebo_store(store, pool, "s")
    with pytest.raises(ValueError):
        deranged_placebo_store(store, ["only-one"], "s")  # 풀 부족 fail-closed


# --- random edit plan ---

def test_random_edit_plan_same_size_and_deterministic():
    ids = [f"l{i}" for i in range(20)]
    p1 = random_edit_plan(ids, n_insert=2, n_delete=3, n_reweight=4, seed="e1")
    p2 = random_edit_plan(ids, n_insert=2, n_delete=3, n_reweight=4, seed="e1")
    assert p1 == p2                                     # 결정론
    assert p1.size() == 9
    assert len(p1.deletes) == 3 and len(p1.reweights) == 4 and len(p1.inserts) == 2
    assert all(0.5 <= m <= 1.5 for _, m in p1.reweights)
    assert not set(p1.deletes) & {t for t, _ in p1.reweights}  # 타깃 비중복


def test_random_edit_plan_fail_closed_on_overshoot():
    with pytest.raises(ValueError):
        random_edit_plan(["a", "b"], 0, 2, 1, "s")


# --- degree-preserving shuffle ---

def test_shuffle_preserves_degree_sequence_and_edge_sizes():
    edges = [["a", "b"], ["b", "c"], ["a", "c", "d"], ["d", "e"]]
    sh = degree_preserving_shuffle(edges, seed="t4")
    assert len(sh) == len(edges)
    assert sorted(len(e) for e in sh) == sorted(len(e) for e in edges)      # 엣지 크기
    assert sorted(degree_sequence(sh).values()) == sorted(degree_sequence(edges).values())  # degree seq
    # 재라벨이므로 노드 수 보존
    assert len({v for e in sh for v in e}) == len({v for e in edges for v in e})


def test_shuffle_deterministic():
    edges = [["a", "b"], ["b", "c"]]
    assert degree_preserving_shuffle(edges, "s") == degree_preserving_shuffle(edges, "s")


# --- canary ---

def test_canary_roundtrip_and_uniqueness():
    c = make_canary("lesson-42", "seed-7")
    assert canary_detected(f"answer mentions {c} verbatim", c)
    assert not canary_detected("ordinary answer", c)
    assert make_canary("lesson-42", "seed-8") != c      # 시드 분리
    assert make_canary("lesson-42", "seed-7") == c      # 결정론


# --- disjoint audit ---

def test_disjoint_audit_catches_exact_and_near_dup():
    train = ["what is the capital of france", "unique training query"]
    ev = ["what is the capital of france", "what is the capital of france?"]  # exact + near
    r = disjoint_audit(train, ev, near_dup_threshold=0.6)
    assert r["verdict"] == "VOID"
    assert "what is the capital of france" in r["exact_overlaps"]
    assert r["leakage"] >= 2


def test_disjoint_audit_clean_when_disjoint():
    r = disjoint_audit(["alpha beta gamma"], ["delta epsilon zeta"])
    assert r["verdict"] == "CLEAN" and r["leakage"] == 0


# --- run verdict ---

def test_run_verdict_fail_closed():
    assert run_verdict()["valid"]
    assert not run_verdict(freeze_hash_changed=True)["valid"]
    assert not run_verdict(leakage=2)["valid"]
    v = run_verdict(judge_sha_changed=True, replay_failed=True)
    assert not v["valid"] and len(v["voids"]) == 2
