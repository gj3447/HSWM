"""ooptdd behavior receipt — the cosine floor (HSWM D1), HONEST scope.

⚠️ This receipt's FIRST draft caught a real overclaim: additive-j does NOT guarantee
per-query nDCG ≥ cosine (adding j≥0 non-uniformly RE-RANKS, so an individual query can
drop, min gap ≈ −0.22 on dev1). What additive-j actually guarantees is stated below.

The TRUE floor (both asserted here):
  (F1) POINTWISE field floor: W(e|c) = cosine + λ·ReLU(residual) ≥ cosine for EVERY edge
       (because j = λ·ReLU(·) ≥ 0). This is the algebraic guarantee.
  (F2) MEAN-nDCG floor via validation λ-selection: λ is chosen on a val split from a grid
       INCLUDING 0, so the deployed field's val mean-nDCG ≥ cosine by construction; held on
       test empirically (dev1 +0.116, real-KG λ→0 ties cosine).
NOT guaranteed (documented, not asserted): per-query nDCG ≥ cosine.

ooptdd gates: (1) pre-run locked trace (2) real execution (3) positive readback
(4) source binding (sha) (5) negative oracle (signed-j breaks F1 pointwise floor).

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


def main() -> int:
    print("source-binding:",
          "learned_v3_additive.py", _sha("learned_v3_additive.py"),
          "weight_field.py", _sha("weight_field.py"))
    LOCK = {
        "F1_pointwise": "W = cosine + lam*ReLU(r) >= cosine for every edge (j>=0)",
        "F2_mean": "lam chosen on val (grid incl 0) => val mean-nDCG >= cosine; held on test",
        "not_guaranteed": "per-query nDCG >= cosine (positive j re-ranks; can regress)",
        "negative_oracle": "signed-j (no ReLU, lam>0) CAN yield W < cosine => F1 breached",
    }
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

    ok = f1_ok and f2_ok and neg_breaks
    print("\nRECEIPT:", "VALID ✅" if ok else "INVALID ❌",
          f"| F1_pointwise={f1_ok} F2_mean={f2_ok} negative_oracle_breaks={neg_breaks}")
    if not neg_breaks:
        print("  !! negative oracle failed to break F1 -> vacuous", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
