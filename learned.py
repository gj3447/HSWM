"""Trainable bilinear hyperedge scorer (the LEARNED weight in falsifier axis A).

score(e, q) = pooled(e)^T · M · q   (M in R^{d x d}, learned)

Trained by multi-positive InfoNCE over each training query's candidate pool,
full-batch gradient descent in numpy (no torch — minimal prototype). M=I-like
recovers raw cosine; a good M recovers the hidden semantic transform.

The two CONTROLS that make the falsifier honest live here too:
- null-head (`shuffle_labels=True`): same capacity, trained on SHUFFLED gold.
  If the real head cannot beat this, its "win" was free-parameter overfit, not
  signal -> falsifier REFUTES (DB_AND_FALSIFIER_DECISION §2.4).
- the parameter-free control (raw cosine) lives in weight_field (M=None).

Gradient (multi-positive InfoNCE, gold set G, pool C):
  s_c = pe_c^T M q ;  p = softmax(s)
  loss = -(1/|G|) sum_{g in G} log p_g
  dloss/dM = sum_c (p_c - y_c) * outer(pe_c, q),  y_c = 1/|G| if c in G else 0
"""
from __future__ import annotations

import numpy as np

from synth import Dataset, candidate_pool
from weight_field import _unit


def _softmax(x: np.ndarray) -> np.ndarray:
    z = x - x.max()
    e = np.exp(z)
    return e / e.sum()


def train_bilinear(
    ds: Dataset,
    train_q: np.ndarray,
    pool_size: int = 60,
    seed: int = 0,
    epochs: int = 150,
    lr: float = 0.5,
    l2: float = 1e-3,
    shuffle_labels: bool = False,
) -> np.ndarray:
    """Learn M (d x d). Returns the trained bilinear map.

    shuffle_labels=True builds the capacity-matched NULL head: gold sets are
    permuted across the training queries, destroying the query<->gold signal
    while keeping identical capacity and training budget.
    """
    d = ds.hg.d
    rng = np.random.default_rng(seed * 7919 + 11)
    M = np.eye(d) + 0.01 * rng.standard_normal((d, d))  # start near cosine
    pooled = _unit(ds.hg.pooled_emb("mean"))
    q_all = _unit(ds.query_emb)

    # precompute pools + gold (optionally shuffled) for training queries
    items = []
    gold_lists = [ds.gold[q] for q in train_q]
    if shuffle_labels:
        perm = rng.permutation(len(train_q))
        gold_lists = [ds.gold[train_q[p]] for p in perm]
    for i, q in enumerate(train_q):
        pool = candidate_pool(ds, int(q), pool_size, seed)
        gold = np.intersect1d(gold_lists[i], pool)
        if gold.size == 0:
            continue  # no positive in pool; skip (reported via pool gold-recall elsewhere)
        items.append((int(q), pool, gold))

    for _ in range(epochs):
        grad = np.zeros((d, d))
        loss = 0.0
        for q, pool, gold in items:
            pe = pooled[pool]              # (K, d)
            qq = q_all[q]                  # (d,)
            s = (pe @ M) @ qq             # (K,)
            p = _softmax(s)
            y = np.zeros_like(p)
            goldpos = np.searchsorted(pool, gold)
            y[goldpos] = 1.0 / gold.size
            loss += -np.log(np.clip(p[goldpos].sum(), 1e-12, None))
            # grad = sum_c (p_c - y_c) outer(pe_c, q) = outer( pe^T coeff , q )
            coeff = (p - y)               # (K,)
            grad += np.outer(pe.T @ coeff, qq)   # (d, d)
        n = max(len(items), 1)
        grad = grad / n + l2 * M
        M = M - lr * grad
    return M
