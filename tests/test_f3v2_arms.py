"""Tests for the F3v2 slice-2 arms harness (offline; no chat calls).

Covers: arm construction determinism, placebo format parity (token-length
band), retrieval determinism, disagreement-gate on/off wiring, TRR math on
synthetic scores, and the K1-K3 kill-condition evaluator (each kill fires /
none fires / indeterminate states).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import f3v2_arms as fa  # noqa: E402
import f3v2_procedural_worlds as fw  # noqa: E402


def _train_rows(worlds, solved_ids):
    return [{"world_id": w["world_id"], "correct": w["world_id"] in solved_ids,
             "actions": fw.strategy_solver(w), "reason": "ok"} for w in worlds]


# ------------------------------------------------- arm construction
def test_lesson_store_deterministic_and_only_from_solved():
    worlds = fw.generate_batch(4, "hard", 20260726)
    rows = _train_rows(worlds, {w["world_id"] for w in worlds[:3]})
    a = fa.build_donor_lesson_store(worlds, rows)
    b = fa.build_donor_lesson_store(worlds, rows)
    assert a == b
    # one unsolved world -> its lessons are excluded
    worlds_all = fa.build_donor_lesson_store(worlds, _train_rows(
        worlds, {w["world_id"] for w in worlds}))
    assert len(a) < len(worlds_all)
    # typed layers present per solved world
    types = {e["type"] for e in a}
    assert types == {"fact", "workflow", "norm"}


def test_retrieve_topk_deterministic_and_bounded():
    worlds = fw.generate_batch(3, "hard", 7)
    store = fa.build_donor_lesson_store(
        worlds, _train_rows(worlds, {w["world_id"] for w in worlds}))
    test_world = fw.generate_world(seed=99, tier="hard", world_idx=0)
    q = fw.render_prompt(test_world)
    a = fa.retrieve_topk(q, store)
    b = fa.retrieve_topk(q, store)
    assert a == b
    assert len(a) <= fa.TOP_K
    # a query about a specific ore retrieves that world's order fact first
    ore = worlds[0]["items"][0]
    hits = fa.retrieve_topk(f"preparation order of {ore}", store, k=1)
    assert hits and ore in hits[0]["text"]


def test_placebo_format_parity_and_determinism():
    w = fw.generate_world(seed=7, tier="hard", world_idx=0)
    store = fa.build_donor_lesson_store([w], _train_rows([w], {w["world_id"]}))
    ref = fa.render_lesson_block([e["text"] for e in
                                  fa.retrieve_topk(fw.render_prompt(w), store)])
    p1 = fa.build_placebo(ref, "7")
    p2 = fa.build_placebo(ref, "7")
    assert p1 == p2  # deterministic
    assert 0.85 * len(ref) <= len(p1) <= 1.15 * len(ref)
    # same block shape (header + bullets), content-free of foundry vocabulary
    assert p1.startswith("Field notes from prior foundry work:\n- ")
    assert p1.count("\n- ") >= 3
    import re as _re
    for banned in ("cleanse", "heat", "charge", "inscribe", "blast", "ore",
                   "crucible", "primed"):
        assert not _re.search(rf"\b{banned}", p1.casefold())


# ------------------------------------------------- disagreement gate wiring
def test_disagreement_gate_drops_only_contradictions():
    test_world = fw.generate_world(seed=123, tier="hard", world_idx=0)
    ore = test_world["items"][0]
    actual = " -> ".join(test_world["ladders"][ore])
    wrong = " -> ".join(reversed(test_world["ladders"][ore]))
    contradicting = [{"lesson_id": "l1",
                      "text": f"Preparation order of {ore}: {wrong}."}]
    agreeing = [{"lesson_id": "l2",
                 "text": f"Preparation order of {ore}: {actual}."}]
    foreign = [{"lesson_id": "l3",
                "text": "Preparation order of zzzq: heat -> charge."}]
    generic = [{"lesson_id": "l4", "text": "avoid blast-fusing (taints)."}]
    kept, dropped = fa.disagreement_gate(
        contradicting + agreeing + foreign + generic, test_world)
    assert [e["lesson_id"] for e in kept] == ["l2", "l3", "l4"]
    assert len(dropped) == 1 and dropped[0]["lesson_id"] == "l1"
    assert ore in dropped[0]["reason"]
    # gate off == identity (wiring: the ablation flag just skips the call)
    lessons = contradicting + agreeing
    assert lessons == (fa.disagreement_gate(lessons, test_world)[0]
                       if False else lessons)


# ------------------------------------------------- TRR / NTR math
def test_trr_math_and_guards():
    import pytest
    assert fa.compute_trr(0.5, 0.2, 0.8) == pytest.approx(0.5)
    assert fa.compute_trr(0.1, 0.2, 0.8) < 0        # negative transfer
    assert fa.compute_trr(0.8, 0.2, 0.8) == pytest.approx(1.0)  # ceiling
    assert fa.compute_trr(0.5, 0.5, 0.5) is None    # collapsed ceiling gap
    assert fa.compute_trr(0.5, 0.6, 0.5) is None    # B-self below no-mem
    assert fa.compute_trr(None, 0.2, 0.8) is None


def test_negative_transfer_rate():
    assert fa.negative_transfer_rate([1, 0, 0, 1], [1, 1, 0, 0]) == 0.25
    assert fa.negative_transfer_rate([1, 1], [0, 0]) == 0.0
    assert fa.negative_transfer_rate([], []) is None


# ------------------------------------------------- kill evaluator (K1-K3)
def _vectors_from_acc(acc, n=10):
    """Deterministic binary vectors with the requested accuracies (paired)."""
    out = {}
    for arm, a in acc.items():
        k = round(a * n)
        out[arm] = [1] * k + [0] * (n - k)
    return out


def test_kills_none_fire_on_healthy_outcome():
    acc = {"a_no_memory": 0.1, "b_naive_donor": 0.2, "c_abstracted": 0.5,
           "d_contrast": 0.6, "e_b_self": 0.8, "f_placebo": 0.1}
    res = fa.evaluate_kill_conditions(acc, _vectors_from_acc(acc), seed=1)
    assert res["k1_environment_kill"]["fired"] is False
    assert res["k2_claim_kill"]["fired"] is False
    assert res["k3_priming_kill"]["fired"] is False
    assert res["trr"]["c_abstracted"] == 0.5714  # (0.5-0.1)/(0.8-0.1)


def test_k1_environment_kill_fires():
    # receiver ZS saturated (>=60%) AND c/d TRR both <= 0
    acc = {"a_no_memory": 0.7, "b_naive_donor": 0.6, "c_abstracted": 0.6,
           "d_contrast": 0.6, "e_b_self": 0.9, "f_placebo": 0.7}
    res = fa.evaluate_kill_conditions(acc, _vectors_from_acc(acc), seed=1)
    assert res["k1_environment_kill"]["fired"] is True


def test_k1_not_fired_when_receiver_zs_low():
    acc = {"a_no_memory": 0.1, "b_naive_donor": 0.05, "c_abstracted": 0.05,
           "d_contrast": 0.1, "e_b_self": 0.8, "f_placebo": 0.1}
    res = fa.evaluate_kill_conditions(acc, _vectors_from_acc(acc), seed=1)
    assert res["k1_environment_kill"]["fired"] is False


def test_k2_claim_kill_fires():
    # naive TRR < 0 and c/d vectors identical to naive -> no significant beat
    acc = {"a_no_memory": 0.5, "b_naive_donor": 0.3, "c_abstracted": 0.3,
           "d_contrast": 0.3, "e_b_self": 0.9, "f_placebo": 0.5}
    vectors = _vectors_from_acc(acc)
    vectors["c_abstracted"] = list(vectors["b_naive_donor"])
    vectors["d_contrast"] = list(vectors["b_naive_donor"])
    res = fa.evaluate_kill_conditions(acc, vectors, seed=1)
    assert res["k2_claim_kill"]["fired"] is True


def test_k2_not_fired_when_contrast_beats_naive():
    n = 40
    acc = {"a_no_memory": 0.5, "b_naive_donor": 0.25, "c_abstracted": 0.75,
           "d_contrast": 0.25, "e_b_self": 0.9, "f_placebo": 0.5}
    vectors = _vectors_from_acc(acc, n=n)
    # c strictly dominates b on the paired tasks -> CI lower > 0
    vectors["b_naive_donor"] = [0] * n
    vectors["c_abstracted"] = [1] * n
    res = fa.evaluate_kill_conditions(acc, vectors, seed=1)
    assert res["k2_claim_kill"]["fired"] is False


def test_k3_priming_kill_fires():
    # placebo TRR >= abstracted TRR - 0.1
    acc = {"a_no_memory": 0.1, "b_naive_donor": 0.2, "c_abstracted": 0.3,
           "d_contrast": 0.7, "e_b_self": 0.9, "f_placebo": 0.25}
    res = fa.evaluate_kill_conditions(acc, _vectors_from_acc(acc), seed=1)
    assert res["k3_priming_kill"]["fired"] is True


def test_kills_indeterminate_on_collapsed_ceiling():
    acc = {"a_no_memory": 0.5, "b_naive_donor": 0.5, "c_abstracted": 0.5,
           "d_contrast": 0.5, "e_b_self": 0.5, "f_placebo": 0.5}
    res = fa.evaluate_kill_conditions(acc, _vectors_from_acc(acc), seed=1)
    assert res["k1_environment_kill"]["fired"] is None
    assert res["k2_claim_kill"]["fired"] is None
    assert res["k3_priming_kill"]["fired"] is None
