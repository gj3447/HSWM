"""ooptdd behavior receipt — the cosine floor (HSWM D1), HONEST scope.

⚠️ This receipt's FIRST draft caught a real overclaim: additive-j does NOT guarantee
per-query nDCG ≥ cosine (adding j≥0 non-uniformly RE-RANKS, so an individual query can
drop, min gap ≈ −0.22 on dev1). What additive-j actually guarantees is stated below.

The TRUE floor (asserted here):
  (F1) POINTWISE field floor: W(e|c) = cosine + λ·ReLU(residual) ≥ cosine for EVERY edge
       (because j = λ·ReLU(·) ≥ 0). This is the algebraic guarantee.
  (F2) MEAN-nDCG floor via validation λ-selection: λ is chosen on a val split from a grid
       INCLUDING 0, so the deployed field's val mean-nDCG ≥ cosine by construction; held on
       test empirically (dev1 +0.116, real-KG λ→0 ties cosine).
  (F3) EXACT ZERO-BOOST: where residual ≤ 0, W == cosine EXACTLY (boost-only means
       no-change, not just no-decrease). Kills constant-shift mutants that F1/F2 miss.
  (F4) PREREGISTERED EFFICACY: synthetic dev1 mean-nDCG gain ≥ +0.03
       (LakatoTree prediction-d1-additive-j-frozen-cosine, prediction ii). Kills
       training-path mutants that hide behind the λ=0 safety hatch (gain → 0).
  (F5) VAL-SELECTION MECHANISM (v2.7, grok-4 audit finding): f2_ok trusted
       train_additive_j's selection; F5 re-derives val scores and requires the
       selection to be an honest argmax over a grid containing 0, so the actual
       floor-by-construction (val[λ*] ≥ val[0]) is checked, not assumed. The
       recompute is REPORT-independent (diag numbers are not trusted); it shares
       the _ndcg_for implementation by design (score formulas are locked by
       F1/F3/F6, so a shared ndcg is not an unguarded path).
v2.7.1 (2026-07-24, claude-code audit findings): F5 degenerate-val guard
  (all-zero recompute refused), F5b split re-derivation from (train_q, seed),
  F5 negative oracle widened to all three rejection branches, F6b AST loop-use
  check (the loop must call the canaried helper).
v2.8b (2026-07-24): F7 winner's-curse bound. F2's "held on test" is empirical;
  F7 measures the curse rate (λ* picks val noise → test gap < 0) on 8 fresh
  deterministic splits of THIS structured distribution and locks it ≤ 0.25
  (measured 0.000). Boundary honestly recorded: on structure-free inputs
  (raw random embeddings) selection overfits (4/5 negative) — the claim is
  scoped to structured fields.
  (F6) TRAIN-PATH CANARY (v2.7): the trainer's internal score/gate are the
       shipped _train_score_and_gate — sc == cos + λ·ReLU(resid) and
       gate == λ·(resid>0) exactly. Kills the v21 train-path survivors
       (binop@88.17 sign flip, binop@88.30 mul→add, binop@92.19 dReLU gate).
NOT guaranteed (documented, not asserted): per-query nDCG ≥ cosine; test mean
floor under distribution shift (winner's-curse, 4/5 fresh splits negative —
empirical-on-dev1 only, grok-4 audit + mechanical probes 2026-07-24).

v2.1 mutation audit (2026-07-24, ooptdd/mutate.py, 12 mutants of learned_v3_additive):
  5/12 killed with F1/F2 only → 8/12 after F3+F4 (binop@47 shift killed by F3;
  binop@73/93 training-corruption killed by F4). Documented EQUIVALENT mutants
  (survival is correct behavior, not an oracle gap): binop@36 (softmax
  constant-shift invariance), binop@67 (RNG seed change), cmp@92 (resid>0 vs >=0,
  measure-zero boundary). KNOWN SURVIVOR (non-equivalent, open oracle gap):
  binop@92 — dReLU gate corrupted to (resid>0)+lam still learns enough for F4's
  +0.03 gain; catching it needs a gradient-semantics domain oracle, not floors.
v2.7 (2026-07-24): that oracle is F6 (train score/gate canary on the shipped
  _train_score_and_gate); F5 closes the grok-4 finding (val-selection trusted,
  not checked); score_additive refuses λ<0 (fail-closed domain guard).

ooptdd gates: (1) pre-run locked trace (2) real execution (3) positive readback
(4) source binding (sha) (5) negative oracle (signed-j breaks F1; constant-shift
breaks F3).

Run:  uv run python receipts/receipt_cosine_floor.py   (exit 0 = valid)
"""
from __future__ import annotations

import ast
import hashlib
import sys

import numpy as np

import metrics
import synth
from learned_v3_additive import (LAMBDA_GRID, _ndcg_for, _train_score_and_gate,
                                 score_additive, train_additive_j)
from weight_field import _unit


def _sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]


# v2: locked trace lives at module level so the ooptdd harness can hash it
# statically (AST) before execution — the lock is bound before the run, not after.
LOCK = {
    "F1_pointwise": "W = cosine + lam*ReLU(r) >= cosine for every edge (j>=0)",
    "F2_mean": "lam chosen on val (grid incl 0) => val mean-nDCG >= cosine; held on test",
    "F3_zero_boost_exact": "resid <= 0 => W == cosine exactly (boost-only = no-change)",
    "F4_prereg_efficacy": "synthetic dev1 mean-nDCG gain >= +0.03 (prediction-d1-additive-j-frozen-cosine ii)",
    "F5_val_selection": "selection is honest argmax over a grid containing 0: val[lam*] >= val[0] (grok-audit gap: mechanism was trusted, not checked)",
    "F6_train_canary": "trainer score/gate ARE the locked formulas: sc == cos + lam*ReLU(resid), gate == lam*(resid>0) (kills binop@88/92 train-path survivors)",
    "F7_winners_curse": "test floor는 경험적 보장 — 구조화 필드에서 fresh split curse rate(λ*가 val 노이즈를 골라 test gap<0) 측정값이 선언 상한(0.25) 이하. 구조 없는 입력에선 selection이 overfit 가능(4/5 실측) — claim은 구조화 필드에 한정",
    "not_guaranteed": "per-query nDCG >= cosine (positive j re-ranks; can regress)",
    "negative_oracle": "signed-j (no ReLU, lam>0) breaks F1; constant-shift (lam + ReLU) breaks F3; rigged selection diag breaks F5; over-bound curse rate breaks F7",
}

# v2.2: machine binding from LOCK prose keys to the verdict-gating variables.
# The harness refuses (exit 2) a receipt whose prose has no gating check.
LOCK_CHECKS = {
    "F1_pointwise": "f1_ok",
    "F2_mean": "f2_ok",
    "F3_zero_boost_exact": "f3_ok",
    "F4_prereg_efficacy": "f4_ok",
    "F5_val_selection": "f5_ok",
    "F6_train_canary": ["f6_ok", "f6b_ok"],
    "F7_winners_curse": "f7_ok",
    "negative_oracle": ["neg_breaks", "neg3_breaks", "neg5_breaks", "neg7_breaks"],
}


CURSE_BOUND = 0.25
CURSE_SEEDS = tuple(range(101, 109))


def _f7_within_bound(rate: float, bound: float = CURSE_BOUND) -> bool:
    return rate <= bound


def _f5_selection_consistent(lam_sel: float, diag: dict, recomputed: dict) -> bool:
    """F5 helper — the val-selection mechanism must be an honest argmax over a
    grid containing 0. Checks: 0 in grid; diag bookkeeping matches a
    report-independent recompute (4dp rounding); selected lam ties the recomputed
    max; val[lam*] >= val[0] (the actual floor-by-construction). A degenerate
    recompute (empty val / no gold in pool -> all-zero flat scores) is REFUSED
    (claude-code audit PROBE A: it would pass vacuously)."""
    vals = list(recomputed.values())
    if not vals or all(v == 0.0 for v in vals):
        return False
    claimed = {float(k): float(v) for k, v in diag["val_ndcg_by_lambda"].items()}
    if 0.0 not in claimed:
        return False
    if any(abs(recomputed.get(k, -1.0) - v) > 1e-3 for k, v in claimed.items()):
        return False
    best = max(recomputed.values())
    if recomputed.get(lam_sel, -1.0) < best - 1e-12:
        return False
    return recomputed[lam_sel] >= recomputed[0.0] - 1e-12


def main() -> int:
    print("source-binding:",
          "learned_v3_additive.py", _sha("learned_v3_additive.py"),
          "weight_field.py", _sha("weight_field.py"))
    print("locked-trace F1:", LOCK["F1_pointwise"])

    ds = synth.generate("semantics", seed=0, deviation=1.0, n_queries=200)
    rng = np.random.default_rng(0)
    perm = rng.permutation(ds.Q)
    train_q, test_q = perm[: int(ds.Q * 0.6)], perm[int(ds.Q * 0.6):]
    pooled = _unit(ds.hg.pooled_emb("mean"))
    M, lam, diag = train_additive_j(ds, train_q, seed=0)

    # (F1) POINTWISE floor — over ALL edges, many queries, on a random M too
    worst_pointwise = np.inf
    rngM = np.random.default_rng(1)
    for trial_M in (M, rngM.standard_normal((ds.hg.d, ds.hg.d))):
        for q in list(test_q)[:20]:
            pool = np.arange(ds.hg.M)
            cos = _unit(pooled[pool]) @ (ds.query_emb[int(q)] / np.linalg.norm(ds.query_emb[int(q)]))
            W = score_additive(pooled[pool], ds.query_emb[int(q)], trial_M, lam=max(lam, 1.0))
            worst_pointwise = min(worst_pointwise, float((W - cos).min()))
    f1_ok = worst_pointwise >= -1e-9
    print(f"F1 positive: worst pointwise (W - cosine) = {worst_pointwise:+.2e}  -> {'OK' if f1_ok else 'FAIL'}")

    # (F2) MEAN-nDCG floor on the val-selected lam
    def mean_ndcg(l):
        v = [metrics.ndcg_at_k(score_additive(pooled[synth.candidate_pool(ds, int(q), 60, 0)],
                                               ds.query_emb[int(q)], M, l),
                               ds.gold[int(q)], synth.candidate_pool(ds, int(q), 60, 0), k=10, seed=0)
             for q in test_q]
        return float(np.mean(v))
    mean_cos, mean_add = mean_ndcg(0.0), mean_ndcg(lam)
    f2_ok = mean_add >= mean_cos - 1e-4
    print(f"F2 positive: mean nDCG cosine={mean_cos:.4f} additive(lam={lam})={mean_add:.4f} -> {'OK' if f2_ok else 'FAIL'}")

    # (F3) EXACT ZERO-BOOST — resid <= 0 edges must score EXACTLY cosine
    f3_worst = 0.0
    for q in list(test_q)[:20]:
        pool = np.arange(ds.hg.M)
        peu = _unit(pooled[pool])
        qu = ds.query_emb[int(q)] / np.linalg.norm(ds.query_emb[int(q)])
        cos = peu @ qu
        resid = (peu @ M) @ qu
        W = score_additive(pooled[pool], ds.query_emb[int(q)], M, lam=max(lam, 1.0))
        neg = resid <= 0.0
        if neg.any():
            f3_worst = max(f3_worst, float(np.abs((W - cos)[neg]).max()))
    f3_ok = f3_worst <= 1e-12
    print(f"F3 positive: max |W - cosine| over resid<=0 edges = {f3_worst:.2e} (must be <= 1e-12) -> {'OK' if f3_ok else 'FAIL'}")

    # (F4) PREREGISTERED EFFICACY — dev1 synthetic gain >= +0.03 (prereg prediction ii)
    gain = mean_add - mean_cos
    f4_ok = gain >= 0.03
    print(f"F4 positive: dev1 mean-nDCG gain = {gain:+.4f} (prereg >= +0.03) -> {'OK' if f4_ok else 'FAIL'}")

    # (F5) VAL-SELECTION MECHANISM — grok-audit gap: f2_ok trusted train_additive_j's
    # selection; here the mechanism itself is checked against a recompute that is
    # independent of the trainer's *reported* numbers (report-independent; it shares
    # the _ndcg_for implementation by design — score formulas are locked by F1/F3/F6).
    val_q = [int(q) for q in diag["val_q"]]
    recomputed = {l: _ndcg_for(ds, val_q, pooled, M, l, 0) for l in LAMBDA_GRID}
    # (F5b) split identity (claude-code audit finding b): diag's val_q must match the
    # canonical split re-derived from (train_q, seed) — a swapped split is detected.
    rng_split = np.random.default_rng(0 * 5381 + 3)
    tq = np.array(train_q)
    rng_split.shuffle(tq)
    nval = max(1, int(len(tq) * diag.get("val_frac", 0.3)))
    f5b_ok = val_q == [int(q) for q in tq[:nval]]
    f5_ok = _f5_selection_consistent(lam, diag, recomputed) and f5b_ok
    print(f"F5 positive: lam*={lam} = argmax(val) over grid∋0, val[lam*]={recomputed[lam]:.4f} >= val[0]={recomputed[0.0]:.4f}, split-match={f5b_ok} -> {'OK' if f5_ok else 'FAIL'}")

    # (F6) TRAIN-PATH CANARY — the trainer's internal score/gate ARE the locked
    # formulas (calls the shipped _train_score_and_gate, not a copy). Kills the
    # v21/v2.6 train-path survivors: binop@88.17 (sign flip), binop@88.30 (mul->add),
    # binop@92.19 (dReLU gate (resid>0)+lam).
    rng6 = np.random.default_rng(6)
    d6 = ds.hg.d
    pe6 = _unit(rng6.normal(size=(25, d6)))
    q6 = _unit(rng6.normal(size=(1, d6)))[0]
    M6 = rng6.normal(size=(d6, d6)) / np.sqrt(d6)
    sc6, gate6 = _train_score_and_gate(pe6, q6, M6, 1.5)
    resid6 = (pe6 @ M6) @ q6
    sc6_expect = (pe6 @ q6) + 1.5 * np.maximum(0.0, resid6)
    gate6_expect = 1.5 * (resid6 > 0).astype(float)
    f6_ok = bool(np.allclose(sc6, sc6_expect, atol=1e-12)
                 and np.allclose(gate6, gate6_expect, atol=1e-12))
    print(f"F6 positive: train sc/gate match locked formulas (atol 1e-12, {(resid6 > 0).sum()}/{len(resid6)} resid>0) -> {'OK' if f6_ok else 'FAIL'}")

    # (F6b) LOOP-USE binding (claude-code audit finding e): F6 canaries the helper;
    # the training loop must actually CALL it — an inline corruption that drops the
    # helper call would pass F6 silently, so the call site is AST-checked.
    f6b_ok = False
    for _node in ast.walk(ast.parse(open("learned_v3_additive.py", encoding="utf-8").read())):
        if isinstance(_node, ast.FunctionDef) and _node.name == "train_additive_j":
            f6b_ok = any(isinstance(_s, ast.Call) and isinstance(_s.func, ast.Name)
                         and _s.func.id == "_train_score_and_gate" for _s in ast.walk(_node))
    print(f"F6b positive: train_additive_j calls _train_score_and_gate (AST) -> {'OK' if f6b_ok else 'FAIL'}")

    # (F7) WINNER'S-CURSE BOUND (v2.8b) — the F2 "held on test" claim is empirical;
    # measure how often val-selection picks noise on FRESH deterministic splits of
    # this receipt's own structured distribution. On structure-free inputs selection
    # can overfit (measured 4/5 on raw random embeddings, 2026-07-24) — the claim is
    # scoped to structured fields, and this gate binds that scope to a bound.
    curse_gaps = []
    for s in CURSE_SEEDS:
        ds_s = synth.generate("semantics", seed=s, deviation=1.0, n_queries=200)
        perm_s = np.random.default_rng(s).permutation(ds_s.Q)
        tr_s, te_s = perm_s[: int(ds_s.Q * 0.6)], perm_s[int(ds_s.Q * 0.6):]
        pooled_s = _unit(ds_s.hg.pooled_emb("mean"))
        M_s, lam_s, _ = train_additive_j(ds_s, tr_s, seed=s)

        def _mean_ndcg_s(l, _ds=ds_s, _te=te_s, _M=M_s, _p=pooled_s):
            return float(np.mean([
                metrics.ndcg_at_k(score_additive(_p[synth.candidate_pool(_ds, int(q), 60, 0)],
                                                 _ds.query_emb[int(q)], _M, l),
                                  _ds.gold[int(q)], synth.candidate_pool(_ds, int(q), 60, 0),
                                  k=10, seed=0)
                for q in _te]))
        curse_gaps.append(_mean_ndcg_s(lam_s) - _mean_ndcg_s(0.0))
    curse_rate = sum(1 for g in curse_gaps if g < -1e-4) / len(curse_gaps)
    f7_ok = _f7_within_bound(curse_rate)
    print(f"F7 positive: winner's-curse rate = {curse_rate:.3f} over {len(curse_gaps)} fresh splits "
          f"(gaps {['%+.3f' % g for g in curse_gaps]}) <= bound {CURSE_BOUND} -> {'OK' if f7_ok else 'FAIL'}")

    # documented (NOT a floor): per-query min
    per_q_min = min(
        metrics.ndcg_at_k(score_additive(pooled[synth.candidate_pool(ds, int(q), 60, 0)], ds.query_emb[int(q)], M, lam),
                          ds.gold[int(q)], synth.candidate_pool(ds, int(q), 60, 0), k=10, seed=0)
        - metrics.ndcg_at_k(score_additive(pooled[synth.candidate_pool(ds, int(q), 60, 0)], ds.query_emb[int(q)], M, 0.0),
                            ds.gold[int(q)], synth.candidate_pool(ds, int(q), 60, 0), k=10, seed=0)
        for q in test_q)
    print(f"documented (NOT floor): per-query min nDCG gap = {per_q_min:+.4f} (re-ranking; can be <0)")

    # (5) NEGATIVE ORACLE — signed j (no ReLU) breaches the POINTWISE floor
    def score_signed(pe, q, M, l):
        peu, qu = _unit(pe), q / max(np.linalg.norm(q), 1e-12)
        return (peu @ qu) + l * ((peu @ M) @ qu)   # NO ReLU
    worst_signed = np.inf
    for q in list(test_q)[:20]:
        pool = np.arange(ds.hg.M)
        cos = _unit(pooled[pool]) @ (ds.query_emb[int(q)] / np.linalg.norm(ds.query_emb[int(q)]))
        Ws = score_signed(pooled[pool], ds.query_emb[int(q)], M, 3.0)
        worst_signed = min(worst_signed, float((Ws - cos).min()))
    neg_breaks = worst_signed < 0.0
    print(f"negative-oracle: signed-j worst pointwise (W - cosine) = {worst_signed:+.4f} (must be < 0) -> {'breaks' if neg_breaks else 'FAILED-to-break'}")

    # (5b) NEGATIVE ORACLE for F3 — constant-shift (lam + ReLU) must violate exact zero-boost
    def score_shifted(pe, q, M, l):
        peu, qu = _unit(pe), q / max(np.linalg.norm(q), 1e-12)
        return (peu @ qu) + l + np.maximum(0.0, (peu @ M) @ qu)   # binop@47 mutant shape
    shift_worst = 0.0
    for q in list(test_q)[:20]:
        pool = np.arange(ds.hg.M)
        peu = _unit(pooled[pool])
        qu = ds.query_emb[int(q)] / np.linalg.norm(ds.query_emb[int(q)])
        cos = peu @ qu
        resid = (peu @ M) @ qu
        Wsh = score_shifted(pooled[pool], ds.query_emb[int(q)], M, 1.0)
        neg = resid <= 0.0
        if neg.any():
            shift_worst = max(shift_worst, float(np.abs((Wsh - cos)[neg]).max()))
    neg3_breaks = shift_worst > 1e-12
    print(f"negative-oracle-F3: constant-shift max |W - cosine| on resid<=0 = {shift_worst:.4f} (must be > 1e-12) -> {'breaks' if neg3_breaks else 'FAILED-to-break'}")

    # (5c) NEGATIVE ORACLE for F5 — all three rejection branches must fire
    # (claude-code audit finding d: the single bookkeeping oracle was narrow).
    rigged_book = dict(diag)
    rigged_book["val_ndcg_by_lambda"] = {**diag["val_ndcg_by_lambda"], lam: -1.0}
    neg5a = not _f5_selection_consistent(lam, rigged_book, recomputed)       # bookkeeping lie
    rigged_grid = dict(diag)
    rigged_grid["val_ndcg_by_lambda"] = {k: v for k, v in diag["val_ndcg_by_lambda"].items() if k != 0.0}
    neg5b = not _f5_selection_consistent(lam, rigged_grid, recomputed)       # grid without 0
    neg5c = not _f5_selection_consistent(lam, diag, {**recomputed, 0.0: max(recomputed.values()) + 0.1})  # non-argmax selection
    neg5_breaks = neg5a and neg5b and neg5c
    print(f"negative-oracle-F5: bookkeeping={'rejected' if neg5a else 'PASS?'} grid-no-0={'rejected' if neg5b else 'PASS?'} non-argmax={'rejected' if neg5c else 'PASS?'} -> {'all rejected' if neg5_breaks else 'VACUOUS'}")

    # (5d) NEGATIVE ORACLE for F7 — an over-bound curse rate must be rejected
    neg7_breaks = not _f7_within_bound(CURSE_BOUND + 0.5)
    print(f"negative-oracle-F7: over-bound curse rate ({CURSE_BOUND + 0.5:.2f}) -> {'rejected' if neg7_breaks else 'ACCEPTED (vacuous)'}")

    ok = f1_ok and f2_ok and f3_ok and f4_ok and f5_ok and f6_ok and f6b_ok and f7_ok and neg_breaks and neg3_breaks and neg5_breaks and neg7_breaks
    print("\nRECEIPT:", "VALID ✅" if ok else "INVALID ❌",
          f"| F1={f1_ok} F2={f2_ok} F3={f3_ok} F4={f4_ok} F5={f5_ok} F6={f6_ok} F6b={f6b_ok} F7={f7_ok} negF1={neg_breaks} negF3={neg3_breaks} negF5={neg5_breaks} negF7={neg7_breaks}")
    if not neg_breaks:
        print("  !! negative oracle failed to break F1 -> vacuous", file=sys.stderr)
    if not neg3_breaks:
        print("  !! negative oracle failed to break F3 -> vacuous", file=sys.stderr)
    if not neg5_breaks:
        print("  !! negative oracle failed to reject rigged F5 diag -> vacuous", file=sys.stderr)
    if not neg7_breaks:
        print("  !! negative oracle failed to reject over-bound curse rate -> vacuous", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
