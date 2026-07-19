"""Metrics for the falsifier: fair-tie nDCG@k, answer-EM, paired bootstrap.

Tie fairness (falsifier §2.5): discrete-score heuristics (frequency/RRF) must
not be penalized by an arbitrary tie order, and continuous-score learned models
must not gain unearned ties. We report EXPECTED nDCG under random tie order by
averaging over several seeded tie-shuffles.
"""
from __future__ import annotations

import numpy as np


def _dcg(rels: np.ndarray) -> float:
    discounts = 1.0 / np.log2(np.arange(2, rels.size + 2))
    return float((rels * discounts).sum())


def ndcg_at_k(scores: np.ndarray, gold: np.ndarray, edges: np.ndarray,
              k: int = 10, tie_shuffles: int = 8, seed: int = 0) -> float:
    """Expected nDCG@k of a ranking of `edges` by `scores`, vs binary `gold`.

    scores, edges are aligned arrays over the candidate pool; gold is a set of
    edge ids. Ties broken by averaging over `tie_shuffles` random orders.
    """
    goldset = set(int(g) for g in gold)
    rel = np.array([1.0 if int(e) in goldset else 0.0 for e in edges])
    n_gold_in_pool = int(rel.sum())
    if n_gold_in_pool == 0:
        return 0.0
    idcg = _dcg(np.sort(rel)[::-1][:k])
    rng = np.random.default_rng(seed * 2654435761 % (2**31))
    accs = []
    for _ in range(tie_shuffles):
        jitter = rng.random(scores.shape) * 1e-9
        order = np.argsort(-(scores + jitter), kind="stable")[:k]
        accs.append(_dcg(rel[order]) / idcg if idcg > 0 else 0.0)
    return float(np.mean(accs))


def answer_em(scores: np.ndarray, gold: np.ndarray, edges: np.ndarray,
              tie_shuffles: int = 8, seed: int = 0) -> float:
    """Co-primary downstream proxy: is the top-1 ranked hyperedge gold? (0/1, tie-averaged)."""
    goldset = set(int(g) for g in gold)
    rng = np.random.default_rng((seed * 40503 + 7) % (2**31))
    hits = []
    for _ in range(tie_shuffles):
        jitter = rng.random(scores.shape) * 1e-9
        top1 = edges[int(np.argmax(scores + jitter))]
        hits.append(1.0 if int(top1) in goldset else 0.0)
    return float(np.mean(hits))


def paired_bootstrap_p(a: np.ndarray, b: np.ndarray, n_boot: int = 10000,
                       seed: int = 0) -> float:
    """One-sided p that mean(a) > mean(b) is NOT true, via paired bootstrap of (a-b).

    Returns P(bootstrap mean diff <= 0). Small p => a reliably exceeds b.
    """
    d = np.asarray(a) - np.asarray(b)
    rng = np.random.default_rng((seed * 917 + 3) % (2**31))
    n = d.size
    if n == 0:
        return 1.0
    means = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        means[i] = d[idx].mean()
    return float((means <= 0).mean())
