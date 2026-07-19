"""The 4-fold identification: retrieval = plan = supersession, one field.

PROM_16_FULL_LANDSCAPE_2026.md §"두 SOTA 극과 미개척 triple": the *unclaimed*
contribution is not any single mechanism but the IDENTIFICATION — one learnable
hyperedge weight field simultaneously being:

  (i)   retrieval signal        -> retrieve(): top-k of W(·|c)
  (ii)  agent plan / dispatch   -> plan(): the distribution W(·|c); dispatch = argmax
  (iii) non-destructive supersede -> supersede(): decay slow b(e), never delete

All three call the SAME WeightField.value — that shared call IS the 4-fold
identification (the 4th fold, provenance/binding-first, lives in the substrate
= Longinus incidence, and is out of scope for this minimal prototype).

  (iv)  traversal (T1/T2 2026-07-19) -> traverse(): certified damped-restart
        hypergraph walk over the SAME field (traversal.py). Deployment default
        mu=0 = OFF; one write gives three effects — FOUR where traversal is
        certified (unconditional "four effects" would be an overclaim,
        PROM_TRAVERSAL_DESIGN §3).

Honesty note: identifying three roles in one field is an ARCHITECTURAL claim,
not proof it is *better* (falsifier axis A tests whether the learned field even
beats heuristics). This module only demonstrates the identification is
structurally coherent and runnable.
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


def plan(field: WeightField, query_emb: np.ndarray, temp: float = 1.0,
         edges: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(ii) Plan readout: the softmax distribution over W(·|c). dispatch = argmax.

    Returns (edges, probs). The distribution IS the plan (계획 = attention 분포);
    a single dispatch is argmax/sample from it, so 계획 ⊋ 출격 holds by construction.
    """
    if edges is None:
        edges = np.arange(field.hg.M)
    w = field.value(query_emb, edges)
    z = (w - w.max()) / max(temp, 1e-6)
    p = np.exp(z)
    p /= p.sum()
    return edges, p


def dispatch(field: WeightField, query_emb: np.ndarray,
             edges: np.ndarray | None = None) -> int:
    """The concrete realization of the plan: argmax over the same field."""
    e, p = plan(field, query_emb, edges=edges)
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
    """(iii) Supersession readout: multiplicatively decay slow b(e). NEVER deletes.

    Eilu-va-Eilu: the hyperedge stays in the hypergraph and stays scorable; its
    contribution to W just drops. This is the same field the other two readouts
    use, so a superseded fact automatically sinks in retrieval AND in the plan
    distribution — one write, three effects (the identification at work).
    """
    if not (0.0 < decay <= 1.0):
        raise ValueError("decay must be in (0, 1]")
    field.hg.base_salience[edge_id] *= decay
