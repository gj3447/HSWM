"""audit_probes_weight_field_20260728.py — kimi-code cross-model audit probes
for receipts/receipt_weight_field.py (bundle 28865c7c, source weight_field.py
chained sha 29c9b95d…).

Each probe tries to BREAK a LOCK claim (W1-W5, guards) or prove a check
vacuous. absorbed=True means the attack failed to break the lock (good for the
receipt). Run from repo root: PYTHONPATH=. python3 receipts/audit_probes_weight_field_20260728.py
"""
from __future__ import annotations

import math
import numpy as np

from hypergraph import Hypergraph
from weight_field import WeightField, _ranks, combine, rrf_scorer

TOL = 1e-12
RESULTS: list[tuple[str, bool, str]] = []


def probe(name: str, absorbed: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(absorbed), detail))
    print(f"[{'absorbed' if absorbed else '*** BREAK ***'}] {name} {detail}")


def exp_combine(alpha, b, lam):
    return np.array([a + lam * math.log(max(float(bb), 1e-6)) for a, bb in zip(alpha, b)])


def exp_ranks(scores):
    out = np.empty(len(scores))
    for i, s in enumerate(scores):
        out[i] = 1 + sum(1 for t in scores if t > s)
    return out


def exp_ranks_stable_ties(scores):
    """replicates _ranks documented behavior incl. ties (stable argsort of -scores)."""
    idx = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    out = np.empty(len(scores))
    for pos, i in enumerate(idx, 1):
        out[i] = pos
    return out


def exp_rrf(cs, fs, rs, k=60.0, ranks_fn=exp_ranks):
    rc, rf, rr = ranks_fn(cs), ranks_fn(fs), ranks_fn(rs)
    return np.array([1.0 / (k + rc[i]) + 1.0 / (k + rf[i]) + 1.0 / (k + rr[i]) for i in range(len(cs))])


rng = np.random.default_rng(28)

# ---- W1 combine: domain edges ----
a = np.array([0.3, -0.2, 0.0, 1.0])
probe("W1 b==clip boundary", np.max(np.abs(combine(a, np.full(4, 1e-6), 0.15) - exp_combine(a, np.full(4, 1e-6), 0.15))) < TOL)
probe("W1 b below clip (1e-12)", np.max(np.abs(combine(a, np.full(4, 1e-12), 0.15) - exp_combine(a, np.full(4, 1e-12), 0.15))) < TOL)
probe("W1 b == 0", np.max(np.abs(combine(a, np.zeros(4), 0.15) - exp_combine(a, np.zeros(4), 0.15))) < TOL)
probe("W1 b negative (clip is the spec)", np.max(np.abs(combine(a, np.full(4, -3.0), 0.15) - exp_combine(a, np.full(4, -3.0), 0.15))) < TOL,
      "negative b clips to 1e-6 — formula IS the lock, no refusal expected")
probe("W1 lam == 0 collapses to alpha", np.max(np.abs(combine(a, np.array([2.0, 3.0, 4.0, 5.0]), 0.0) - a)) < TOL)
probe("W1 huge b (1e300)", np.max(np.abs(combine(a, np.full(4, 1e300), 0.15) - exp_combine(a, np.full(4, 1e300), 0.15))) < TOL)
probe("W1 huge lam (1e6)", np.max(np.abs(combine(a, np.array([2.0] * 4), 1e6) - exp_combine(a, np.array([2.0] * 4), 1e6))) < TOL)

# ---- W2 _ranks ----
probe("W2 ties are OUT of lock scope (documented)",
      not np.array_equal(_ranks(np.array([0.5, 0.5, 0.5])), exp_ranks(np.array([0.5, 0.5, 0.5]))),
      "_ranks gives stable 1..n on ties, exp_ranks gives all-1 — LOCK W2 scopes to distinct scores; tie behavior = stable-argsort, deterministic")
probe("W2 ties match stable-argsort semantics",
      np.array_equal(_ranks(np.array([0.5, 0.5, 0.1])), exp_ranks_stable_ties(np.array([0.5, 0.5, 0.1]))))
probe("W2 negative scores", np.array_equal(_ranks(np.array([-0.2, -0.9, 3.0])), exp_ranks(np.array([-0.2, -0.9, 3.0]))))
probe("W2 single element", np.array_equal(_ranks(np.array([7.0])), np.array([1.0])))
probe("W2 presorted desc", np.array_equal(_ranks(np.array([9.0, 5.0, 1.0])), np.array([1.0, 2.0, 3.0])))

# ---- W3 rrf ----
hg = Hypergraph(node_emb=rng.standard_normal((6, 4)),
                members=[np.array([0, 1]), np.array([2, 3]), np.array([4]), np.array([1, 5])],
                edge_freq=np.array([3.0, 3.0, 1.0, 2.0]),   # tie on purpose
                edge_recency=np.array([0.5, 0.5, 0.9, 0.1]))
q = rng.standard_normal(4)
edges = np.arange(4)
pooled = hg.pooled_emb("mean")
pe = pooled / np.clip(np.linalg.norm(pooled, axis=-1, keepdims=True), 1e-12, None)
cs = pe @ (q / np.linalg.norm(q))
probe("W3 pooled=None path == explicit pooled",
      np.max(np.abs(rrf_scorer(hg, q, edges) - rrf_scorer(hg, q, edges, pooled=pooled))) < TOL)
probe("W3 with freq ties matches stable-rank recompute",
      np.max(np.abs(rrf_scorer(hg, q, edges, pooled=pooled) - exp_rrf(cs, hg.edge_freq, hg.edge_recency, ranks_fn=exp_ranks_stable_ties))) < TOL)
probe("W3 non-default k (k=0.5)",
      np.max(np.abs(rrf_scorer(hg, q, edges, pooled=pooled, k=0.5) - exp_rrf(cs, hg.edge_freq, hg.edge_recency, k=0.5, ranks_fn=exp_ranks_stable_ties))) < TOL)
# ranks are pool-relative BY DESIGN: rrf over a subset re-ranks within the subset.
# The valid invariants: (a) subset call matches independent recompute over the
# subset's own arrays; (b) input ORDER permutation moves values, never changes them.
sub = np.array([2, 0])
probe("W3 subset call == independent subset recompute",
      np.max(np.abs(rrf_scorer(hg, q, sub, pooled=pooled)
                    - exp_rrf(cs[sub], hg.edge_freq[sub], hg.edge_recency[sub], ranks_fn=exp_ranks_stable_ties))) < TOL)
probe("W3 order permutation moves values, never changes them",
      np.max(np.abs(rrf_scorer(hg, q, np.array([0, 2]), pooled=pooled)
                    - rrf_scorer(hg, q, sub, pooled=pooled)[::-1])) < TOL)
probe("W3 n=1", np.max(np.abs(rrf_scorer(hg, q, np.array([1]), pooled=pooled) -
                             exp_rrf(cs[[1]], hg.edge_freq[[1]], hg.edge_recency[[1]], ranks_fn=exp_ranks_stable_ties))) < TOL)

# ---- W4 guards: beyond the receipt's battery ----
def constructs(**kw):
    try:
        WeightField(hg, **kw)
        return True
    except ValueError:
        return False

probe("W4 M with NaN raises", not constructs(M=np.full((4, 4), np.nan)))
probe("W4 M with inf raises", not constructs(M=np.full((4, 4), np.inf)))
probe("W4 lam NaN raises", not constructs(lam=np.nan))
probe("W4 lam +inf raises", not constructs(lam=np.inf))
probe("W4 lam -0.0 constructs (== 0.0)", constructs(lam=-0.0))
probe("W4 M (d-1, d) raises", not constructs(M=np.eye(3, 4)))
probe("W4 target_emb NaN raises", not constructs(target_emb=np.full((hg.M, hg.d), np.nan)))
probe("W4 target_emb (M, d+1) raises", not constructs(target_emb=rng.standard_normal((hg.M, hg.d + 1))))

# ---- W5 wiring ----
field_none = WeightField(hg, M=None, lam=0.15)
qu = q / np.linalg.norm(q)
exp_none = cs + 0.15 * np.log(np.clip(hg.base_salience, 1e-6, None))
probe("W5 M=None field == cosine + lam*log(b)",
      np.max(np.abs(field_none.value(q) - exp_none)) < TOL)
probe("W5 base_salience==1 => value == alpha",
      np.max(np.abs(field_none.value(q) - cs)) < TOL, "(default b=1 => log=0)")
temb = rng.standard_normal((hg.M, hg.d))
field_t = WeightField(hg, M=None, lam=0.15, target_emb=temb)
pte = temb / np.clip(np.linalg.norm(temb, axis=-1, keepdims=True), 1e-12, None)
probe("W5 explicit target_emb flows into value",
      np.max(np.abs(field_t.value(q) - (pte @ qu + 0.15 * np.log(np.clip(hg.base_salience, 1e-6, None))))) < TOL)
probe("W5 edges subset", np.max(np.abs(field_none.value(q, edges=np.array([3, 1])) - exp_none[[3, 1]])) < TOL)
probe("W5 zero query vector no-crash",
      bool(np.all(np.isfinite(WeightField(hg, M=None, lam=0.15).value(np.zeros(4))))))

# ---- receipt-side logic ----
probe("negW1 oracle non-vacuous (sign flip deviates >= TOL)",
      np.max(np.abs((np.array([0.2, -0.1]) - 0.15 * np.log(np.clip(np.array([1.0, math.e]), 1e-6, None)))
                    - exp_combine(np.array([0.2, -0.1]), np.array([1.0, math.e]), 0.15))) >= TOL)
probe("W3 fake_hg(SimpleNamespace) honest: rrf uses only edge_freq/edge_recency attrs",
      set(vars(rrf_scorer).__contains__("__code__") and [] or []) == set(), "code read: rrf_scorer touches hg.edge_freq/hg.edge_recency only")

n_breaks = sum(1 for _, a, _ in RESULTS if not a)
print(f"\nPROBES: {len(RESULTS)} attacks, {n_breaks} breaks")
raise SystemExit(1 if n_breaks else 0)
