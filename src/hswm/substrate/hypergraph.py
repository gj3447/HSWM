"""Hypergraph data structure for the semantic weight mapper prototype.

재배맨 v3 (KG: 재배맨-v3-semantic-weight-mapper, verdict-jaebaeman-v3-longinus-based-substrate-2026-07-19).

A Hypergraph here mirrors the Neo4j-reified shape (the DB decision =
`decision-jaebaeman-v3-db-neo4j-stay-2026-07-19`): each n-ary fact is a
*hyperedge* over a set of member (argument) nodes. Nodes carry embeddings
(Neo4j native VECTOR); hyperedges carry incidence + slow-timescale metadata
(frequency / recency / base salience b) used by the weight field.

This module is intentionally storage-agnostic: a synthetic generator
(`synth.py`) or a Neo4j loader can both produce this shape. Only the
*support* (which nodes each hyperedge binds) is structural — everything
else (weights) is computed on-demand by `weight_field.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Hypergraph:
    """Reified hypergraph over N nodes and M hyperedges.

    Attributes
    ----------
    node_emb : (N, d) float array
        Per-node semantic embedding (the Longinus-bound substrate; a
        hyperedge weight is only ever computed over *bound* members).
    members : list[np.ndarray]
        length M; members[j] = int indices of nodes bound by hyperedge j.
        This incidence is the *support* of the weight field — attention is
        masked to it (weight = 0 off the hypergraph). This is the formal
        content of "마구 연결 금지" (Constrain axis).
    edge_freq : (M,) float
        Slow-timescale usage count (heuristic salience input).
    edge_recency : (M,) float
        Slow-timescale last-touch (0..1 normalized; higher = more recent).
    base_salience : (M,) float
        b(e): the slow, context-free component of the weight field. Occam
        (오캄) decays this for superseded facts — supersession = down-weight,
        never delete (Eilu-va-Eilu). Distinct from the fast attention alpha
        that 재배맨 reads as the plan.
    """

    node_emb: np.ndarray
    members: list[np.ndarray]
    edge_freq: np.ndarray
    edge_recency: np.ndarray
    base_salience: np.ndarray = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.node_emb = np.asarray(self.node_emb, dtype=np.float64)
        self.members = [np.asarray(m, dtype=np.int64) for m in self.members]
        self.edge_freq = np.asarray(self.edge_freq, dtype=np.float64)
        self.edge_recency = np.asarray(self.edge_recency, dtype=np.float64)
        if self.base_salience is None:
            self.base_salience = np.ones(self.M, dtype=np.float64)
        self.base_salience = np.asarray(self.base_salience, dtype=np.float64)
        self._validate()

    def _validate(self) -> None:
        n = self.node_emb.shape[0]
        for j, mem in enumerate(self.members):
            if mem.size == 0:
                raise ValueError(f"hyperedge {j} has empty member set (arity 0 forbidden)")
            if mem.min() < 0 or mem.max() >= n:
                raise ValueError(f"hyperedge {j} references node outside [0,{n})")
        for name in ("edge_freq", "edge_recency", "base_salience"):
            arr = getattr(self, name)
            if arr.shape[0] != self.M:
                raise ValueError(f"{name} length {arr.shape[0]} != M={self.M}")

    @property
    def N(self) -> int:
        return self.node_emb.shape[0]

    @property
    def M(self) -> int:
        return len(self.members)

    @property
    def d(self) -> int:
        return self.node_emb.shape[1]

    def incidence(self) -> np.ndarray:
        """(M, N) boolean incidence matrix H[j,i] = node i in hyperedge j."""
        H = np.zeros((self.M, self.N), dtype=bool)
        for j, mem in enumerate(self.members):
            H[j, mem] = True
        return H

    def pooled_emb(self, pool: str = "mean") -> np.ndarray:
        """(M, d) hyperedge embedding = permutation-invariant pool of members.

        Mean-pool (DeepSets baseline) is the standard for retrieval — see
        PROM_16 §부록 (HyperGraphRAG serialize-and-embed / DeepSets pooling).
        The *learned* attention head (learned.py) is the trainable alternative;
        this mean-pool is the parameter-free representation-parity control (#8).
        """
        out = np.zeros((self.M, self.d), dtype=np.float64)
        for j, mem in enumerate(self.members):
            vecs = self.node_emb[mem]
            if pool == "mean":
                out[j] = vecs.mean(axis=0)
            elif pool == "sum":
                out[j] = vecs.sum(axis=0)
            elif pool == "max":
                out[j] = vecs.max(axis=0)
            else:
                raise ValueError(f"unknown pool {pool!r}")
        return out
