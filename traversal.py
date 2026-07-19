"""Field traversal operator — the (iv) readout of the SAME weight field (T1).

Spec: SYMPOSIUM HSWM/PROM_TRAVERSAL_DESIGN_2026-07-19.md (v2, 3-critic SOUND_W_ADJ).
Certified damped-restart hypergraph walk on the star/bipartite expansion:

    seed s = topm softmax(W(·|c)/τ)                       (plan() 분포의 절단)
    hop:   n = Σ_e (a·b^κ) → nodes / deg   ;   ã = Σ_v n → edges / arity ; L1 renorm
    a_{k+1} = (1−γ)·s + γ·prune_topm(ã)                   (restart = skip term)
    W_trav  = W + μ·R,  R = 1[Δ>0]·ReLU(z_S(Δ)),  S = support(a_K)∪support(s)

Honesty invariants built in (do not weaken):
- μ=0 OR γ=0 ⇒ EARLY RETURN, bit-identical to the pointwise readout.
- The transition operator uses SLOW field components only (COO structure, deg,
  arity, b) — query enters via seed and restart only. supersede() invalidates
  nothing: b is a separate vector read at hop time (O(0) invalidation).
- per-hop L1 renorm + truncation make the operator mildly NONLINEAR: only the
  RELATIVE b differences matter; corpus-wide uniform supersession is a no-op
  by construction (spec §2.4). Contraction log is DIAGNOSTIC ONLY.
- Path receipts are GREEDY-argmax chains, not true max-contribution paths.
- MU_GRID below is PROVISIONAL until the T3/T5 recalibration lock; under the
  support-restricted z-norm R is O(1) by construction so the grid is
  scale-appropriate (verified in tests), but certification (μ selection with
  SELECT_Z_ADJ) is T3 — this module never self-certifies.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dfield

import numpy as np

from weight_field import WeightField

# ---- prereg constants (spec §2.2; fixed before any run) ----
GAMMA = 0.5              # walk mass; hard cap ≤0.5 ⇒ worst-case amplification 2γ/(1−γ) ≤ 2×
K_DEFAULT = 2            # hop cap (K=3 needs canon-amendment + hop-3 certification)
TAU_SEED = 1.0           # seed softmax temperature (BP contraction regime τ≥1)
SEED_M = 64              # seed truncation
PRUNE_M = 1024           # per-hop frontier keep (compute guard, NOT semantics)
MU_GRID = (0.0, 0.1, 0.2, 0.4, 0.8)   # provisional until T3/T5 lock; 0 admissible
SELECT_Z_ADJ = 2.5       # μ certification gate (multiplicity-corrected; used in T3, not here)
ENTROPY_BLOWUP = float(np.log(4.0))   # H(a_K) − H(a_0) beyond this ⇒ abstain
NEFF_MIN = 1.5           # min 1-hop parent-contribution n_eff over top-k ⇒ abstain
KEPT_MASS_ABSTAIN = 0.95  # real-world abstain threshold (synthetic worlds hard-assert ≥0.99)


@dataclass
class TraversalIndex:
    """Query-independent COO structure (bake-time; rebuilt only on incidence change)."""
    edge_idx: np.ndarray     # (nnz,) hyperedge id per incidence entry
    node_idx: np.ndarray     # (nnz,) node id per incidence entry
    deg_node: np.ndarray     # (N,) node hyperedge-degree, clipped ≥1 (0-degree NaN guard)
    arity: np.ndarray        # (M,)
    M: int
    N: int


def build_index(hg) -> TraversalIndex:
    """COO from hg.members directly — NEVER via hg.incidence() (dense M×N)."""
    arity = np.array([m.size for m in hg.members], dtype=np.int64)
    edge_idx = np.repeat(np.arange(hg.M), arity)
    node_idx = np.concatenate(hg.members) if hg.M else np.empty(0, dtype=np.int64)
    deg_node = np.maximum(np.bincount(node_idx, minlength=hg.N), 1)
    return TraversalIndex(edge_idx=edge_idx, node_idx=node_idx,
                          deg_node=deg_node.astype(np.float64),
                          arity=arity.astype(np.float64), M=hg.M, N=hg.N)


@dataclass
class TraversalReceipt:
    seed_edges: np.ndarray
    mu: float
    gamma: float
    K: int
    kappa: int
    kept_mass: list = dfield(default_factory=list)     # per-hop surviving mass after prune
    paths: list = dfield(default_factory=list)         # greedy (edge, via_node, parent_edge, contrib) per hop
    n_eff: float = float("inf")                        # 1-hop parent-contribution approx (min over top-k)
    contraction_log: list = dfield(default_factory=list)  # ‖a_{k+1}−a_k‖₁ — DIAGNOSTIC ONLY
    abstained: bool = False
    abstain_reason: str | None = None


def _softmax_topm(w: np.ndarray, m: int) -> np.ndarray:
    z = np.exp((w - w.max()) / TAU_SEED)
    if z.size > m:
        cut = np.partition(z, -m)[-m]
        z = np.where(z >= cut, z, 0.0)
    s = z / max(z.sum(), 1e-12)
    return s


def _prune_topm(a: np.ndarray, m: int, rc: TraversalReceipt) -> np.ndarray:
    total = float(a.sum())
    if np.count_nonzero(a) <= m or total <= 0:
        rc.kept_mass.append(1.0)
        return a
    cut = np.partition(a, -m)[-m]
    kept = np.where(a >= cut, a, 0.0)
    rc.kept_mass.append(float(kept.sum()) / total)
    return kept


def _entropy(p: np.ndarray) -> float:
    nz = p[p > 0]
    if nz.size == 0:
        return 0.0
    q = nz / nz.sum()
    return float(-(q * np.log(q)).sum())


def _greedy_paths(rc: TraversalReceipt, idx: TraversalIndex, w_in: np.ndarray,
                  n_vec: np.ndarray, a_new: np.ndarray, step: int, top: int = 8) -> None:
    """Greedy-argmax chain receipt (documented approximation, spec §3).

    parent_edge(v) = argmax-contribution edge into node v — via ascending-sort
    last-write-wins on the COO arrays (deterministic).
    """
    order = np.argsort(w_in, kind="stable")
    parent_edge = np.full(idx.N, -1, dtype=np.int64)
    parent_edge[idx.node_idx[order]] = idx.edge_idx[order]
    top_edges = np.argsort(-a_new, kind="stable")[:top]
    for e in top_edges:
        if a_new[e] <= 0:
            continue
        mem = idx.node_idx[idx.edge_idx == e]
        if mem.size == 0:
            continue
        via = int(mem[int(np.argmax(n_vec[mem]))])
        rc.paths.append((step, int(e), via, int(parent_edge[via]), float(a_new[e])))


def _pointwise(W: np.ndarray, k: int, rc: TraversalReceipt, reason: str):
    rc.abstained = True
    rc.abstain_reason = reason
    order = np.argsort(-W, kind="stable")[:k]
    return order, W[order], rc


def traverse(field: WeightField, query_emb: np.ndarray, k: int = 10,
             mu: float = 0.0, K: int = K_DEFAULT, kappa: int = 1,
             gamma: float = GAMMA, index: TraversalIndex | None = None):
    """(iv) traversal readout of the SAME field. Returns (edge_ids, scores, receipt).

    mu=0 OR gamma=0 ⇒ bit-identical to the pointwise readout (early return —
    the structural floor guarantee, spec §2.5). Deployment default is mu=0:
    traversal is OFF until certified per-corpus (T3/T5).
    """
    if gamma > 0.5:
        raise ValueError("gamma hard cap 0.5 (amplification bound 2γ/(1−γ) ≤ 2×)")
    hg = field.hg
    W = field.value(query_emb)
    rc = TraversalReceipt(seed_edges=np.empty(0, dtype=np.int64), mu=mu,
                          gamma=gamma, K=K, kappa=kappa)
    if mu == 0.0 or gamma == 0.0:
        return _pointwise(W, k, rc, f"certified floor (mu={mu}, gamma={gamma})")

    idx = index if index is not None else build_index(hg)
    s = _softmax_topm(W, SEED_M)
    rc.seed_edges = np.flatnonzero(s)
    g = hg.base_salience ** kappa            # supersession conductance (vector OUTSIDE the COO)

    a = s.copy()
    n_vec = np.zeros(idx.N)
    for step in range(K):
        w_in = (a * g)[idx.edge_idx]
        n_vec = np.bincount(idx.node_idx, weights=w_in, minlength=idx.N) / idx.deg_node
        at = np.bincount(idx.edge_idx, weights=n_vec[idx.node_idx], minlength=idx.M) / idx.arity
        at = at / max(at.sum(), 1e-12)
        a_new = (1.0 - gamma) * s + gamma * _prune_topm(at, PRUNE_M, rc)
        _greedy_paths(rc, idx, w_in, n_vec, a_new, step)
        rc.contraction_log.append(float(np.abs(a_new - a).sum()))
        a = a_new

    # ---- query-time trip-wires (fixed constants; abstain-only failure mode) ----
    if _entropy(a) - _entropy(s) > ENTROPY_BLOWUP:
        return _pointwise(W, k, rc, "entropy blowup (oversmoothing onset)")
    if rc.kept_mass and min(rc.kept_mass) < KEPT_MASS_ABSTAIN:
        return _pointwise(W, k, rc, f"kept_mass {min(rc.kept_mass):.3f} < {KEPT_MASS_ABSTAIN}")
    top_pre = np.argsort(-a, kind="stable")[:k]
    neffs = []
    for e in top_pre:
        mem = idx.node_idx[idx.edge_idx == e]
        c = n_vec[mem]
        c = c[c > 0]
        if c.size:
            neffs.append(float(c.sum() ** 2 / (c ** 2).sum()))
    rc.n_eff = min(neffs) if neffs else 0.0
    if rc.n_eff < NEFF_MIN:
        return _pointwise(W, k, rc, f"n_eff {rc.n_eff:.2f} < {NEFF_MIN} (single uncorroborated chain)")

    # ---- final combine (support-restricted z + raw-positive mask, spec §2.5) ----
    S = np.flatnonzero((a != 0) | (s != 0))
    d = a[S] - s[S]
    R = np.zeros_like(W)
    std = float(d.std(ddof=0))
    if std > 0:
        R[S] = (d > 0) * np.maximum((d - d.mean()) / std, 0.0)
    W_trav = W + mu * R
    order = np.argsort(-W_trav, kind="stable")[:k]
    return order, W_trav[order], rc
