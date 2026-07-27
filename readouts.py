"""Legacy field readouts and the compatibility supersession write.

The prototype demonstrates that retrieval and a selection distribution can
read the same score vector, and that temporal decay changes both.  This is an
architectural property, not a uniqueness, planning-efficacy, or novelty claim:
T4 arm (e) reproduces the graded pointwise scores from separated metadata.

  (i)   retrieval signal        -> retrieve(): top-k of W(·|c)
  (ii)  selection / dispatch    -> selection_distribution(); dispatch = argmax
  (iii) temporal parameter write -> supersede(): decay slow b(e), never delete

  (iv)  traversal (T1/T2 2026-07-19) -> traverse(): certified damped-restart
        hypergraph walk over the SAME field (traversal.py). Deployment default
        mu=0 = OFF and T5 selected OFF on MuSiQue/2Wiki.
"""
from __future__ import annotations

import numpy as np

from weight_field import WeightField


def retrieve(field: WeightField, query_emb: np.ndarray, k: int = 10,
             edges: np.ndarray | None = None) -> np.ndarray:
    """(i) Retrieval readout: top-k hyperedges by W(·|c). Returns edge ids, best first."""
    if edges is None:
        edges = np.arange(field.hg.M)
    w = field.value(query_emb, edges)
    order = np.argsort(-w, kind="stable")[:k]
    return edges[order]


def selection_distribution(field: WeightField, query_emb: np.ndarray, temp: float = 1.0,
                           edges: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(ii) Softmax selection distribution over W(·|c); not an agent plan."""
    if edges is None:
        edges = np.arange(field.hg.M)
    w = field.value(query_emb, edges)
    z = (w - w.max()) / max(temp, 1e-6)
    p = np.exp(z)
    p /= p.sum()
    return edges, p


def plan(field: WeightField, query_emb: np.ndarray, temp: float = 1.0,
         edges: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Compatibility alias for :func:`selection_distribution`.

    Kept so existing consumers do not break. Downstream task/cost/risk planning
    efficacy has not been measured, so new code should use the precise name.
    """
    return selection_distribution(field, query_emb, temp=temp, edges=edges)


def dispatch(field: WeightField, query_emb: np.ndarray,
             edges: np.ndarray | None = None) -> int:
    """Concrete argmax dispatch over the selection distribution."""
    e, p = selection_distribution(field, query_emb, edges=edges)
    return int(e[int(np.argmax(p))])


def traverse(field: WeightField, query_emb: np.ndarray, k: int = 10,
             mu: float = 0.0, **kw):
    """(iv) Traversal readout: K-hop damped-restart walk reading the SAME field.

    Thin delegation to traversal.traverse (kernel + receipts + trip-wires live
    there). mu=0 (default) or gamma=0 returns the pointwise ranking bit-for-bit
    — traversal is refusable by construction and OFF until certified.
    """
    import traversal as _t
    return _t.traverse(field, query_emb, k=k, mu=mu, **kw)


def supersede(field: WeightField, edge_id: int, decay: float = 0.5) -> None:
    """(iii) Compatibility write: multiplicatively decay slow b(e). NEVER deletes.

    Eilu-va-Eilu: the hyperedge stays in the hypergraph and stays scorable; its
    contribution to W just drops. S3+ replaces this positional in-place write
    with stable-ID event folding and immutable field snapshots.
    """
    if not (0.0 < decay <= 1.0):
        raise ValueError("decay must be in (0, 1]")
    field.hg.base_salience[edge_id] *= decay
