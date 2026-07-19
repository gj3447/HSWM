"""The weight field W(e | c) — the heart of 재배맨 v3.

Formalization (SEMANTIC_WEIGHT_HARNESS_v3.md §3, PROM_16 §SYMPOSIUM 위치):

    W(e | c) = phi( alpha(e, c; theta) , b(e) )
               └ fast, contextual ┘   └ slow salience ┘

- alpha(e,c;theta): incidence-masked attention of hyperedge e under context c,
  computed as a bilinear score pooled(e)^T · M · q (theta = M). Raw cosine is
  the M = I special case (the parameter-free control). This is the FAST
  component read by 재배맨 as the plan.
- b(e): slow, context-free base salience. Occam (오캄) decays it for superseded
  facts (supersession = down-weight, never delete). This is the SLOW component.
- phi: combination. Default phi = alpha + lambda * log(b) (additive, so a
  down-weighted stale edge is pushed down without being removed).

Heuristic scorers (cosine / frequency / recency / RRF) are alternative fields
used as the falsifier's STRONG baselines. The whole architecture is the same
"one field, many readouts" shape — the readouts (readouts.py) prove the 4-fold
identification: retrieval, plan, supersession all read THIS field.
"""
from __future__ import annotations

import numpy as np

from hypergraph import Hypergraph


def _unit(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.clip(n, 1e-12, None)


def attention_alpha(
    pooled_edge_emb: np.ndarray,   # (K, d) for K candidate edges
    query_emb: np.ndarray,          # (d,)
    M: np.ndarray | None = None,    # (d, d) learned bilinear map; None => raw cosine
) -> np.ndarray:
    """Fast contextual attention alpha(e, c). Higher = more relevant.

    Bilinear form on unit-normalized inputs: score = pooled_e^T · M · q. This is
    exactly the score learned.py trains M for (consistent train/eval). M=None =>
    raw cosine pooled_e^T q (the parameter-free representation-parity control #8).
    """
    pe = _unit(pooled_edge_emb)                       # (K, d)
    q = query_emb / max(np.linalg.norm(query_emb), 1e-12)
    if M is None:
        return pe @ q
    return (pe @ M) @ q                                # (K,) bilinear pe^T M q


def combine(alpha: np.ndarray, base_salience: np.ndarray, lam: float = 0.15) -> np.ndarray:
    """phi(alpha, b) = alpha + lam*log(b). Down-weighted b pushes W down, never removes."""
    return alpha + lam * np.log(np.clip(base_salience, 1e-6, None))


# ---- heuristic scorers (STRONG baselines; falsifier §2.3) ----

def cosine_scorer(hg: Hypergraph, query_emb: np.ndarray, edges: np.ndarray,
                  pooled: np.ndarray | None = None) -> np.ndarray:
    if pooled is None:
        pooled = hg.pooled_emb("mean")
    return attention_alpha(pooled[edges], query_emb, M=None)


def frequency_scorer(hg: Hypergraph, query_emb: np.ndarray, edges: np.ndarray,
                     pooled: np.ndarray | None = None) -> np.ndarray:
    return hg.edge_freq[edges].astype(np.float64)


def recency_scorer(hg: Hypergraph, query_emb: np.ndarray, edges: np.ndarray,
                   pooled: np.ndarray | None = None) -> np.ndarray:
    return hg.edge_recency[edges].astype(np.float64)


def _ranks(scores: np.ndarray) -> np.ndarray:
    """Descending ranks (1 = best), ties get averaged position via argsort of argsort."""
    order = np.argsort(-scores, kind="stable")
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(scores) + 1, dtype=np.float64)
    return ranks


def rrf_scorer(hg: Hypergraph, query_emb: np.ndarray, edges: np.ndarray,
               pooled: np.ndarray | None = None, k: float = 60.0) -> np.ndarray:
    """Reciprocal Rank Fusion of cosine + frequency + recency (strong hybrid)."""
    cs = cosine_scorer(hg, query_emb, edges, pooled)
    fs = frequency_scorer(hg, query_emb, edges, pooled)
    rs = recency_scorer(hg, query_emb, edges, pooled)
    return 1.0 / (k + _ranks(cs)) + 1.0 / (k + _ranks(fs)) + 1.0 / (k + _ranks(rs))


HEURISTICS = {
    "cosine": cosine_scorer,
    "frequency": frequency_scorer,
    "recency": recency_scorer,
    "rrf": rrf_scorer,
}


class WeightField:
    """The unified learnable weight field. ONE field; readouts.py reads it three ways.

    theta = M (bilinear map, learned by learned.py). base_salience = slow b(e).
    """

    def __init__(self, hg: Hypergraph, M: np.ndarray | None = None, lam: float = 0.15):
        self.hg = hg
        self.M = M
        self.lam = lam
        self._pooled = hg.pooled_emb("mean")

    def value(self, query_emb: np.ndarray, edges: np.ndarray | None = None) -> np.ndarray:
        """W(e | c) for the given context over the given candidate edges (default: all)."""
        if edges is None:
            edges = np.arange(self.hg.M)
        alpha = attention_alpha(self._pooled[edges], query_emb, M=self.M)
        return combine(alpha, self.hg.base_salience[edges], self.lam)
