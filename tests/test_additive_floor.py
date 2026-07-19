"""D1 — additive-j must satisfy the cosine floor (나생문 C-1 fix verification).

The v0.2 standard demoted I4 (cosine floor) to REFUTED because the M-learning
mechanism undershoots cosine on real data. The additive-j design restores the
floor by construction: W = cosine + λ·ReLU(residual), λ selected on val from a
grid including 0. These tests assert the floor actually holds.
"""
import numpy as np

import synth
from learned_v3_additive import score_additive, train_additive_j
from weight_field import _unit


def test_W_is_pointwise_at_least_cosine_when_lambda_nonneg():
    """W = cosine + λ·ReLU(r) ≥ cosine for every edge (algebraic floor)."""
    ds = synth.generate("semantics", seed=0, deviation=1.0, n_queries=60)
    pooled = _unit(ds.hg.pooled_emb("mean"))
    rng = np.random.default_rng(0)
    M = rng.standard_normal((ds.hg.d, ds.hg.d))
    for q in range(5):
        pool = np.arange(ds.hg.M)
        cos = _unit(pooled[pool]) @ (ds.query_emb[q] / np.linalg.norm(ds.query_emb[q]))
        W = score_additive(pooled[pool], ds.query_emb[q], M, lam=2.0)
        assert (W >= cos - 1e-9).all()          # floor holds pointwise


def test_lambda_zero_recovers_pure_cosine():
    ds = synth.generate("semantics", seed=1, deviation=1.0, n_queries=40)
    pooled = _unit(ds.hg.pooled_emb("mean"))
    M = np.eye(ds.hg.d)
    q = ds.query_emb[0]
    cos = _unit(pooled) @ (q / np.linalg.norm(q))
    W0 = score_additive(pooled, q, M, lam=0.0)
    assert np.allclose(W0, cos)                 # λ=0 => exactly cosine (the fallback)


def test_validation_never_selects_a_floor_breaking_lambda_on_aligned():
    """On cosine-aligned data (dev0), val selection should keep λ=0 (no harm)."""
    ds = synth.generate("semantics", seed=2, deviation=0.0, n_queries=120)
    rng = np.random.default_rng(2)
    perm = rng.permutation(ds.Q)
    train_q = perm[: int(ds.Q * 0.7)]
    _, lam, diag = train_additive_j(ds, train_q, seed=2)
    # λ=0 must be at least tied-best on aligned data (floor preserved)
    by_lam = diag["val_ndcg_by_lambda"]           # keys are float lambdas
    assert by_lam[0.0] >= max(by_lam.values()) - 1e-4
