"""Synthetic hypergraph + query generator with TWO honest regimes.

The whole point of an honest falsifier (DB_AND_FALSIFIER_DECISION_2026-07-19.md
§2) is that the harness must be able to say REFUTED / EXCLUDED — not rigged to
confirm. So we generate two deliberately different worlds:

  regime="semantics"  — relevance depends on a HIDDEN linear map A applied to
      embeddings: rel(e,q) ranked by cos(A·pool(e), A·q). Raw cosine (no A) is
      only weakly aligned; frequency/recency are uncorrelated. A *learned*
      bilinear scorer CAN recover A and beat raw cosine — IF the signal is
      learnable from the training queries. It is NOT guaranteed to.

  regime="frequency"  — relevance = the highest-frequency hyperedges, embeddings
      irrelevant. A frequency-only heuristic solves it perfectly, so the
      falsifier's manipulation gate MUST fire and EXCLUDE this dataset as
      uninformative. This regime exists to prove the gate has teeth.

Real datasets (WD50K / JF17K / MuSiQue) are the documented real-run slot in the
falsifier protocol; this synthetic world only proves the harness is sound.

Determinism: every function takes an explicit integer seed. No global RNG.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hypergraph import Hypergraph


@dataclass
class Dataset:
    hg: Hypergraph
    query_emb: np.ndarray          # (Q, d)
    gold: list[np.ndarray]         # length Q; gold[q] = relevant hyperedge indices
    regime: str
    hidden_map: np.ndarray | None  # (d, d) A, for diagnostics only (never given to models)

    @property
    def Q(self) -> int:
        return self.query_emb.shape[0]


def _unit(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.clip(n, 1e-12, None)


def generate(
    regime: str,
    seed: int,
    n_nodes: int = 300,
    n_edges: int = 400,
    n_queries: int = 400,
    dim: int = 24,
    n_topics: int = 12,
    arity_lo: int = 2,
    arity_hi: int = 5,
    gold_per_query: int = 3,
    deviation: float = 1.0,
) -> Dataset:
    """Generate a synthetic Dataset for one regime.

    deviation (semantics regime only): how far the hidden relevance map A is from
    identity. A = (1-dev)*I + dev*R. dev=0 => relevance == raw cosine (cosine
    ceilings, learning has NO headroom); dev=1 => fully rotated (raw cosine weak,
    a learnable non-cosine signal exists). The headroom knob for the diagnostic.
    """
    rng = np.random.default_rng(seed)

    # nodes cluster around latent topic centers (gives embeddings real structure)
    centers = _unit(rng.standard_normal((n_topics, dim)))
    node_topic = rng.integers(0, n_topics, size=n_nodes)
    node_emb = _unit(centers[node_topic] + 0.6 * rng.standard_normal((n_nodes, dim)))

    # hyperedges over random member sets
    members = []
    for _ in range(n_edges):
        k = int(rng.integers(arity_lo, arity_hi + 1))
        members.append(rng.choice(n_nodes, size=k, replace=False))

    # slow-timescale metadata
    edge_freq = rng.integers(1, 50, size=n_edges).astype(np.float64)
    edge_recency = rng.random(n_edges)

    hg = Hypergraph(node_emb=node_emb, members=members,
                    edge_freq=edge_freq, edge_recency=edge_recency)
    pooled = _unit(hg.pooled_emb("mean"))

    query_emb = _unit(rng.standard_normal((n_queries, dim)))
    gold: list[np.ndarray] = []
    hidden_map: np.ndarray | None = None

    if regime == "semantics":
        # hidden map A interpolates identity -> random by `deviation` (headroom knob)
        R = rng.standard_normal((dim, dim))
        R = R / np.linalg.norm(R) * np.linalg.norm(np.eye(dim))  # scale-match to I
        A = (1.0 - deviation) * np.eye(dim) + deviation * R
        hidden_map = A
        qA = _unit(query_emb @ A.T)
        eA = _unit(pooled @ A.T)
        rel = qA @ eA.T  # (Q, M) relevance in the hidden space
        for q in range(n_queries):
            gold.append(np.argsort(-rel[q])[:gold_per_query])
    elif regime == "frequency":
        # relevance = the globally highest-frequency edges, embeddings irrelevant
        top_freq = np.argsort(-edge_freq)[: max(gold_per_query * 4, 12)]
        for q in range(n_queries):
            # each query's gold is a fixed-size slice of the high-frequency set
            gold.append(top_freq[:gold_per_query])
    else:
        raise ValueError(f"unknown regime {regime!r}")

    return Dataset(hg=hg, query_emb=query_emb, gold=gold, regime=regime, hidden_map=hidden_map)


def candidate_pool(ds: Dataset, q: int, pool_size: int, seed: int) -> np.ndarray:
    """Fixed candidate pool for query q (falsifier §2.2 rerank-isolation).

    Union of (a) a lexical-ish signal proxy and (b) the gold, so that every
    query has recallable gold in the pool (pool gold-recall reported by the
    harness). Both learned and heuristic rerank the SAME pool.
    """
    rng = np.random.default_rng(seed * 100003 + q)
    M = ds.hg.M
    # cheap "BM25 union PPR" proxy: random subset + gold guaranteed in-pool
    base = rng.choice(M, size=min(pool_size, M), replace=False)
    pool = np.unique(np.concatenate([base, ds.gold[q]]))
    if pool.size > pool_size:
        # keep gold, trim extras
        goldset = set(ds.gold[q].tolist())
        extras = [e for e in pool.tolist() if e not in goldset]
        keep = list(goldset) + extras[: pool_size - len(goldset)]
        pool = np.array(sorted(keep), dtype=np.int64)
    return pool
