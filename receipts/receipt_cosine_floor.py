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
NOT guaranteed (documented, not asserted): per-query nDCG ≥ cosine.

v2.1 mutation audit (2026-07-24, ooptdd/mutate.py, 12 mutants of learned_v3_additive):
  5/12 killed with F1/F2 only → 8/12 after F3+F4 (binop@47 shift killed by F3;
  binop@73/93 training-corruption killed by F4). Documented EQUIVALENT mutants
  (survival is correct behavior, not an oracle gap): binop@36 (softmax
  constant-shift invariance), binop@67 (RNG seed change), cmp@92 (resid>0 vs >=0,
  measure-zero boundary). KNOWN SURVIVOR (non-equivalent, open oracle gap):
  binop@92 — dReLU gate corrupted to (resid>0)+lam still learns enough for F4's
  +0.03 gain; catching it needs a gradient-semantics domain oracle, not floors.

ooptdd gates: (1) pre-run locked trace (2) real execution (3) positive readback
(4) source binding (sha) (5) negative oracle (signed-j breaks F1; constant-shift
breaks F3).

Run:  uv run python receipts/receipt_cosine_floor.py   (exit 0 = valid)
"""
from __future__ import annotations

import hashlib
import sys

import numpy as np

import metrics
import synth
from learned_v3_additive import score_additive, train_additive_j
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
    "not_guaranteed": "per-query nDCG >= cosine (positive j re-ranks; can regress)",
    "negative_oracle": "signed-j (no ReLU, lam>0) breaks F1; constant-shift (lam + ReLU) breaks F3",
}


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
    M, lam, _ = train_additive_j(ds, train_q, seed=0)

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

    ok = f1_ok and f2_ok and f3_ok and f4_ok and neg_breaks and neg3_breaks
    print("\nRECEIPT:", "VALID ✅" if ok else "INVALID ❌",
          f"| F1={f1_ok} F2={f2_ok} F3={f3_ok} F4={f4_ok} negF1={neg_breaks} negF3={neg3_breaks}")
    if not neg_breaks:
        print("  !! negative oracle failed to break F1 -> vacuous", file=sys.stderr)
    if not neg3_breaks:
        print("  !! negative oracle failed to break F3 -> vacuous", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
