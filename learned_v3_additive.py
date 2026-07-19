"""D1 — additive-j on FROZEN cosine (나생문 C-1/C-2 fix option (a)).

Fixes the v0.2 refuted 'cosine floor': instead of learning M *inside* α (which
reshapes cosine everywhere and undershoots it), freeze α = raw cosine and add a
SIGN-CONSTRAINED residual:

    W(e|c) = cosine(pool(e), c)  +  λ_j · ReLU( pool(e)ᵀ M q )
             └ frozen, α ────────┘    └ j ≥ 0 (boost-only) ────┘

- j ≥ 0 by ReLU, so W ≥ cosine POINTWISE (the algebraic floor holds by construction).
- The RETRIEVAL floor (never worse than cosine on nDCG) is guaranteed operationally
  by selecting λ_j on a validation split from a grid that INCLUDES 0 — if the
  learned residual does not help val-nDCG, λ_j = 0 collapses to pure cosine.
- Negative signals (refute/모순/supersede) are NOT j's job here — they route to b
  (unchanged). j only boosts.

The residual M is trained by the judgment loop (judge-supplied labels; here the
simulated oracle = ds.gold), exactly as llm_judgment_loop but on the additive score.

Pre-registered on LakatoTree: prediction-d1-additive-j-frozen-cosine.
Prediction: (i) floor holds (test nDCG ≥ cosine − ε), (ii) synthetic dev1 gain ≥ 0.03.
Risk: j≥0 can only boost gold, cannot suppress high-cosine non-gold → may under-recover.
"""
from __future__ import annotations

import numpy as np

import metrics
import synth
from weight_field import _unit

LAMBDA_GRID = [0.0, 0.5, 1.0, 2.0, 4.0, 8.0]


def _softmax(s):
    z = s - s.max()
    e = np.exp(z)
    return e / e.sum()


def score_additive(pe_pool, q, M, lam):
    """W = cosine + λ·ReLU(peᵀ M q). pe_pool (K,d), q (d,)."""
    peu = _unit(pe_pool)
    qu = q / max(np.linalg.norm(q), 1e-12)
    cos = peu @ qu
    resid = (peu @ M) @ qu
    return cos + lam * np.maximum(0.0, resid)


def _ndcg_for(ds, qs, pooled, M, lam, seed):
    vals = []
    for q in qs:
        pool = synth.candidate_pool(ds, int(q), 60, seed)
        sc = score_additive(pooled[pool], ds.query_emb[int(q)], M, lam)
        vals.append(metrics.ndcg_at_k(sc, ds.gold[int(q)], pool, k=10, seed=seed))
    return float(np.mean(vals)) if len(vals) else 0.0


def train_additive_j(ds, train_q, seed=0, epochs=120, lr=0.4, lam_train=1.0,
                     rounds_topk=15, val_frac=0.3):
    """Train residual M via judgment loop on the additive score; select λ_j on val.

    Returns (M, lambda_j, diag). lambda_j is chosen from LAMBDA_GRID by val nDCG
    (0 included → never worse than cosine on val).
    """
    d = ds.hg.d
    rng = np.random.default_rng(seed * 5381 + 3)
    pooled = _unit(ds.hg.pooled_emb("mean"))
    train_q = np.array(train_q)
    rng.shuffle(train_q)
    nval = max(1, int(len(train_q) * val_frac))
    val_q, tr_q = train_q[:nval], train_q[nval:]
    M = 0.01 * rng.standard_normal((d, d))

    items = []
    for q in tr_q:
        pool = synth.candidate_pool(ds, int(q), 60, seed)
        gold = np.intersect1d(ds.gold[int(q)], pool)
        if gold.size:
            items.append((int(q), pool, np.searchsorted(pool, gold)))

    for _ in range(epochs):
        grad = np.zeros((d, d))
        for q, pool, goldpos in items:
            peu = pooled[pool]
            qu = ds.query_emb[q] / max(np.linalg.norm(ds.query_emb[q]), 1e-12)
            resid = (peu @ M) @ qu
            sc = (peu @ qu) + lam_train * np.maximum(0.0, resid)   # W = cosine + λ·ReLU(residual)
            p = _softmax(sc)
            y = np.zeros_like(p)
            y[goldpos] = 1.0 / goldpos.size
            gate = (resid > 0).astype(float) * lam_train        # dReLU
            coeff = (p - y) * gate
            grad += np.outer(peu.T @ coeff, qu)
        if items:
            M = M - lr * (grad / len(items))

    # select lambda_j on val (grid incl 0 => floor)
    val_scores = {lam: _ndcg_for(ds, val_q, pooled, M, lam, seed) for lam in LAMBDA_GRID}
    best_lam = max(val_scores, key=val_scores.get)
    return M, best_lam, {"val_ndcg_by_lambda": {k: round(v, 4) for k, v in val_scores.items()}}


def run_d1_synthetic(devs=(0.0, 1.0), seeds=(0, 1, 2)):
    out = {}
    for dev in devs:
        cos_list, add_list, floor_ok = [], [], []
        for seed in seeds:
            ds = synth.generate("semantics", seed=seed, deviation=dev, n_queries=300)
            rng = np.random.default_rng(seed * 17 + 2)
            perm = rng.permutation(ds.Q)
            ntr = int(ds.Q * 0.6)
            train_q, test_q = perm[:ntr], perm[ntr:]
            pooled = _unit(ds.hg.pooled_emb("mean"))
            M, lam, _ = train_additive_j(ds, train_q, seed=seed)
            cos = _ndcg_for(ds, test_q, pooled, M, 0.0, seed)   # lam=0 => pure cosine
            add = _ndcg_for(ds, test_q, pooled, M, lam, seed)
            cos_list.append(cos)
            add_list.append(add)
            floor_ok.append(add >= cos - 1e-4)
        out[f"dev={dev}"] = {
            "cosine_ndcg": round(float(np.mean(cos_list)), 4),
            "additive_j_ndcg": round(float(np.mean(add_list)), 4),
            "gain": round(float(np.mean(add_list) - np.mean(cos_list)), 4),
            "floor_ok_all_seeds": all(floor_ok),
        }
    return out


def run_d1_realkg(seeds=(0, 1, 2)):
    from neo4j_loader import load_members
    from real_run import build_loo_dataset
    node_emb, members = load_members()
    cos_list, add_list, floor_ok, lams = [], [], [], []
    for seed in seeds:
        ds, train_q, test_q = build_loo_dataset(node_emb, members, seed)
        pooled = _unit(ds.hg.pooled_emb("mean"))
        M, lam, _ = train_additive_j(ds, train_q, seed=seed)
        cos = _ndcg_for(ds, test_q, pooled, M, 0.0, seed)
        add = _ndcg_for(ds, test_q, pooled, M, lam, seed)
        cos_list.append(cos); add_list.append(add); lams.append(lam)
        floor_ok.append(add >= cos - 1e-4)
    return {"cosine_ndcg": round(float(np.mean(cos_list)), 4),
            "additive_j_ndcg": round(float(np.mean(add_list)), 4),
            "gain": round(float(np.mean(add_list) - np.mean(cos_list)), 4),
            "floor_ok_all_seeds": all(floor_ok),
            "selected_lambdas": lams}


if __name__ == "__main__":
    import json
    print("=== D1 additive-j — SYNTHETIC (floor + dev1 efficacy) ===")
    print(json.dumps(run_d1_synthetic(), indent=2))
    print("\n=== D1 additive-j — REAL KG (floor must hold, λ→0 expected) ===")
    print(json.dumps(run_d1_realkg(), indent=2, ensure_ascii=False))
