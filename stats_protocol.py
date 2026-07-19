"""Statistical protocol for prereg claims — Experiment C of PROM_6 (SYMPOSIUM).

Implements the IR-stats mandated toolkit (Smucker/Allan/Carterette CIKM 2007;
Sakai topic-set-size 2016; Card et al. EMNLP 2020; Benjamini-Hochberg 1995):

  paired_permutation_p   primary test — sign-flip randomization on per-query diffs
  bootstrap_ci           95% CI of the mean per-query gain (the real deliverable)
  required_n             power analysis: n ≈ 8·(σ_Δ/minD)² for 80% power @ α=.05
  bh_adjust              Benjamini-Hochberg across K datasets/strata
  paired_trend_p         per-query monotone-trend test across ordered strata
                         (Experiment B's length axis: is the HSWM−cosine delta
                         increasing in unit length?)
  seed_variance_report   per-seed mean ± std; flags gain ≲ seed noise

Design rules baked in (do not weaken):
- paired > unpaired: all tests condition on query. No Wilcoxon/sign tests
  (Smucker et al.: discontinue).
- The point estimate is never reported without its CI (bootstrap over queries).
- λ/config selection and metric reporting must use disjoint splits; these
  functions only *test*, they do not select.
"""
from __future__ import annotations

import numpy as np


def paired_permutation_p(diffs: np.ndarray, n_perm: int = 10000, seed: int = 0,
                         alternative: str = "greater") -> float:
    """Sign-flip randomization test on per-query paired differences.

    H0: the paired difference distribution is symmetric around 0.
    alternative: "greater" (mean diff > 0), "less", or "two-sided".
    Exact-style Monte Carlo with add-one smoothing (never returns 0).
    """
    d = np.asarray(diffs, dtype=np.float64)
    n = d.size
    if n == 0:
        return 1.0
    obs = d.mean()
    rng = np.random.default_rng((seed * 7919 + 11) % (2**31))
    signs = rng.integers(0, 2, size=(n_perm, n)) * 2 - 1
    perm_means = (signs * d).mean(axis=1)
    if alternative == "greater":
        hits = int((perm_means >= obs).sum())
    elif alternative == "less":
        hits = int((perm_means <= obs).sum())
    elif alternative == "two-sided":
        hits = int((np.abs(perm_means) >= abs(obs)).sum())
    else:
        raise ValueError(f"unknown alternative {alternative!r}")
    return float((hits + 1) / (n_perm + 1))


def bootstrap_ci(diffs: np.ndarray, n_boot: int = 10000, seed: int = 0,
                 level: float = 0.95) -> tuple[float, float, float]:
    """(mean, lo, hi) percentile bootstrap CI over queries of the mean gain.

    A gain claim is credible only if lo > 0 (CI excludes zero).
    """
    d = np.asarray(diffs, dtype=np.float64)
    n = d.size
    if n == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng((seed * 104729 + 13) % (2**31))
    idx = rng.integers(0, n, size=(n_boot, n))
    means = d[idx].mean(axis=1)
    a = (1.0 - level) / 2.0
    lo, hi = np.quantile(means, [a, 1.0 - a])
    return float(d.mean()), float(lo), float(hi)


def required_n(sigma_delta: float, min_detectable: float) -> int:
    """Paired-sample size for ~80% power at two-sided α=0.05.

    Normal-approx rule n ≈ (z_{α/2}+z_{β})²·(σ_Δ/minD)² ≈ 7.85·(σ_Δ/minD)².
    Estimate σ_Δ from a pilot's per-query diffs — never assume it.
    """
    if min_detectable <= 0:
        raise ValueError("min_detectable must be > 0")
    if sigma_delta <= 0:
        return 1
    return int(np.ceil(7.85 * (sigma_delta / min_detectable) ** 2))


def bh_adjust(pvals: list[float] | np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (monotone, capped at 1)."""
    p = np.asarray(pvals, dtype=np.float64)
    m = p.size
    order = np.argsort(p)
    adj = np.empty(m)
    running = 1.0
    for rank_from_last in range(m - 1, -1, -1):
        i = order[rank_from_last]
        running = min(running, p[i] * m / (rank_from_last + 1))
        adj[i] = running
    return adj


def paired_trend_p(per_query_by_stratum: np.ndarray, n_perm: int = 10000,
                   seed: int = 0) -> tuple[float, float]:
    """Monotone-increase test for a per-query metric across ORDERED strata.

    per_query_by_stratum: (n_queries, n_strata) — e.g. the HSWM−cosine delta of
    the SAME query evaluated at each unit-length stratum (paired by design).

    Statistic: mean per-query least-squares slope over stratum index.
    Null: within each query, stratum labels are exchangeable (per-query
    permutation of the row). Returns (mean_slope, one-sided p for slope > 0).
    """
    X = np.asarray(per_query_by_stratum, dtype=np.float64)
    if X.ndim != 2 or X.shape[1] < 2:
        raise ValueError("need (n_queries, n_strata>=2)")
    n_q, n_s = X.shape
    t = np.arange(n_s, dtype=np.float64)
    tc = t - t.mean()
    denom = float((tc**2).sum())

    def mean_slope(mat: np.ndarray) -> float:
        return float(((mat - mat.mean(axis=1, keepdims=True)) @ tc / denom).mean())

    obs = mean_slope(X)
    rng = np.random.default_rng((seed * 6151 + 17) % (2**31))
    hits = 0
    for _ in range(n_perm):
        perm = np.array([row[rng.permutation(n_s)] for row in X])
        if mean_slope(perm) >= obs:
            hits += 1
    return obs, float((hits + 1) / (n_perm + 1))


def seed_variance_report(per_seed_means: list[float] | np.ndarray) -> dict:
    """mean ± std across seeds; flags a gain smaller than the seed noise floor."""
    m = np.asarray(per_seed_means, dtype=np.float64)
    return {
        "per_seed": [round(float(v), 4) for v in m],
        "mean": round(float(m.mean()), 4),
        "std": round(float(m.std(ddof=1)), 4) if m.size > 1 else 0.0,
        "n_seeds": int(m.size),
    }
