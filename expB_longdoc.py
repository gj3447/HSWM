"""Experiment B — length vs hop-depth attribution of the additive-j−cosine delta (v2).

Preregistered falsifier for the owner's long-document intuition, crossed
against the SR-lineage competing hypothesis (PROM_PRIOR_ART_TRIBUNAL §6).
v2 after adversarial review wf_a931ba07-21a; scope of every claim below is
MECHANISM SUFFICIENCY in the synth_longdoc aboutness world, not real-doc truth.

  H1 LENGTH  (owner): delta(additive_j − cosine) increases monotonically with
      unit length at hop=0. Tests: paired_trend_p (same queries across strata →
      paired), chapter−sentence gap ≥ MARGIN, and a seed-CLUSTER bootstrap CI
      excluding 0 (review: 5 worlds pooled are not 700 iid queries).
  H2 HOP: at fixed length, delta(additive_j − cosine) falls with hop depth.
      REVIEW RELABEL — the fall is REPRODUCED BY CONSTRUCTION (the simulated
      judge resolves chains only with prob CHAIN_FOLLOW), so H2 here is a
      mechanism DEMONSTRATION, not attribution evidence for SR. The mechanical
      expectation (1−CHAIN_FOLLOW)·delta_h0 is reported next to the observed
      drop so the readback is auditable. Symmetric standards (review): the drop
      must also clear MARGIN and a cluster-bootstrap CI, like H1.

Arm naming (review): the treatment arm is "additive_j" = cosine + λ·judge-bits,
the D1 additive-j *design* instantiated with a SIMULATED judge — it is NOT the
full HSWM weight field (no log-salience term, no learned M). Results transfer
to HSWM only through that design identity.

Attribution ∈ {LENGTH_CONFIRMED, HOP_DEMO_ONLY, BOTH, NEITHER}.
Teeth: regime="null" must return NO_GAIN across BOTH the H1 and H2 (additive_j)
quantities (review: v1 gated only H1). The spread arm's null offset is measured
and reported, not gated (documented known bias).

Pre-registered constants (fixed BEFORE any run; do not renegotiate):
  MARGIN = 0.03, TOL = 0.02, ALPHA = 0.05, SEEDS = (0,1,2,3,4)
  JUDGE_ACC = 0.9, CHAIN_FOLLOW = 0.35 (injected conditional-relevance failure)
  LAMBDA_GRID = (0.0, 0.1, 0.2, 0.4, 0.8)  λ validation-selected, 0 admissible
  Certified λ selection: λ>0 accepted ONLY if its PAIRED validation improvement
      over λ=0 exceeds 2×SE of the paired per-(query,level) diffs (one-sided
      z≈2; safe-policy-improvement pattern, PROM_6 C5 honest-floor in code).
      A fixed margin was tried first and failed: 0.005 < validation SE (~0.025),
      so a null-world seed certified λ=0.8 off pure noise and degraded the test
      split — the winner's curse demonstrated live inside the harness.
  SPREAD_GAMMA = 0.5, SPREAD_STEPS = 3, POOL_SIZE = 40, K = 10
  World premise params (reported with results): n_topics=60, gold_units_per_topic=3.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import metrics
import stats_protocol as sp
import synth_longdoc as sl

MARGIN = 0.03
TOL = 0.02
ALPHA = 0.05
SEEDS = (0, 1, 2, 3, 4)
JUDGE_ACC = 0.9
CHAIN_FOLLOW = 0.35
LAMBDA_GRID = (0.0, 0.1, 0.2, 0.4, 0.8)
SELECT_Z = 2.0   # certified selection: improvement must exceed SELECT_Z × SE(paired val diffs)
SPREAD_GAMMA = 0.5
SPREAD_STEPS = 3
POOL_SIZE = 40
K = 10
HOP_FIXED_LEVEL = "paragraph"
TREND_HOP = 0

ARMS = ("cosine", "additive_j", "spread")


@dataclass
class ExpBVerdict:
    regime: str
    attribution: str   # LENGTH_CONFIRMED / HOP_DEMO_ONLY / BOTH / NEITHER / NO_GAIN / HARNESS_BROKEN
    reason: str
    numbers: dict = field(default_factory=dict)


def _cosine_scores(world: sl.LongDocWorld, level: str, q: int, pool: np.ndarray) -> np.ndarray:
    ue = world.strata[level].unit_emb[pool]
    qe = world.query_emb[q]
    return ue @ (qe / max(np.linalg.norm(qe), 1e-12))


def _judge_bits(world: sl.LongDocWorld, level: str, q: int, pool: np.ndarray,
                rng: np.random.Generator) -> np.ndarray:
    """Simulated pointwise judge: 'is this unit ABOUT the query's target?'

    Reads the EXPOSED owner latent (what an LLM reading the unit would infer).
    Resolves the hop chain only with prob CHAIN_FOLLOW (injected
    conditional-relevance failure — the H2 mechanism); accuracy JUDGE_ACC.
    In the null regime the exposed owner is decoupled from gold, so this
    signal is dead there by construction.
    """
    t0 = int(world.query_topic[q])
    hop = int(world.query_hop[q])
    target = sl._chain_target(t0, hop, world.bridge_next) if (hop == 0 or rng.random() < CHAIN_FOLLOW) else t0
    owner = world.unit_owner[level][pool]
    bits = (owner == target).astype(np.float64)
    flip = rng.random(bits.size) > JUDGE_ACC
    bits[flip] = 1.0 - bits[flip]
    return bits


def _spread_scores(world: sl.LongDocWorld, level: str, q: int, pool: np.ndarray) -> np.ndarray:
    """Deterministic spreading activation over the bridge graph (zero-LLM C4 control)."""
    qe = world.query_emb[q]
    act = np.clip(world.topic_emb @ (qe / max(np.linalg.norm(qe), 1e-12)), 0.0, None)
    T = act.size
    B = np.zeros((T, T))
    B[world.bridge_next, np.arange(T)] = 1.0
    for _ in range(SPREAD_STEPS):
        act = (1.0 - SPREAD_GAMMA) * act + SPREAD_GAMMA * (B @ act)
    members = world.unit_topics[level]
    return np.array([act[members[int(e)]].mean() for e in pool])


def _select_lambda(world: sl.LongDocWorld, val_q: np.ndarray, seed: int) -> float:
    """CERTIFIED λ selection (0 admissible): λ>0 only if its PAIRED validation
    improvement over λ=0 exceeds SELECT_Z × SE of the per-(query,level) diffs
    (safe-policy-improvement pattern). Without certification the selection is a
    winner's-curse channel — demonstrated live by the null world (λ=0.8 chosen
    on validation noise, degraded the test split)."""
    def val_vec(lam: float) -> np.ndarray:
        vals = []
        for q in val_q:
            for level in sl.LENGTH_ORDER:
                pool = sl.candidate_pool(world, level, int(q), POOL_SIZE, seed)
                rng = np.random.default_rng(seed * 613 + int(q) * 7 + 1)
                sc = _cosine_scores(world, level, int(q), pool) + lam * _judge_bits(world, level, int(q), pool, rng)
                vals.append(metrics.ndcg_at_k(sc, world.gold[level][int(q)], pool, k=K, seed=seed))
        return np.array(vals)

    base = val_vec(0.0)
    best_lam, best_mean = 0.0, float(base.mean())
    best_certified = 0.0
    for lam in LAMBDA_GRID[1:]:
        v = val_vec(lam)
        if float(v.mean()) > best_mean:
            best_lam, best_mean = lam, float(v.mean())
            d = v - base
            se = float(d.std(ddof=1)) / max(np.sqrt(d.size), 1.0)
            best_certified = 1.0 if float(d.mean()) >= SELECT_Z * se else 0.0
    return best_lam if best_certified else 0.0


def _eval_world(regime: str, seed: int, val_frac: float = 0.3):
    world = sl.generate(regime, seed=seed)
    rng_split = np.random.default_rng(seed * 271 + 9)
    perm = rng_split.permutation(world.Q)
    n_val = int(world.Q * val_frac)
    val_q, test_q = perm[:n_val], perm[n_val:]

    lam = _select_lambda(world, val_q, seed)

    ndcg = {a: {lv: np.full(world.Q, np.nan) for lv in sl.LENGTH_ORDER} for a in ARMS}
    for q in test_q:
        for level in sl.LENGTH_ORDER:
            pool = sl.candidate_pool(world, level, int(q), POOL_SIZE, seed)
            gold = world.gold[level][int(q)]
            cos = _cosine_scores(world, level, int(q), pool)
            rng_j = np.random.default_rng(seed * 613 + int(q) * 7 + 1)
            scores = {
                "cosine": cos,
                "additive_j": cos + lam * _judge_bits(world, level, int(q), pool, rng_j),
                "spread": _spread_scores(world, level, int(q), pool),
            }
            for a in ARMS:
                ndcg[a][level][int(q)] = metrics.ndcg_at_k(scores[a], gold, pool, k=K, seed=seed)
    return world, ndcg, test_q, lam


def _cluster_ci(per_seed_arrays: list[np.ndarray], n_boot: int = 5000, seed: int = 0,
                level: float = 0.95) -> tuple[float, float, float]:
    """Seed-cluster bootstrap CI of a mean (resample seeds, then queries within).

    Review fix: pooling 5 worlds' queries as iid overstates n. With only 5
    clusters the CI is coarse — that honesty is the point.
    """
    rng = np.random.default_rng((seed * 52361 + 29) % (2**31))
    S = len(per_seed_arrays)
    grand = float(np.concatenate(per_seed_arrays).mean())
    means = np.empty(n_boot)
    for i in range(n_boot):
        picks = rng.integers(0, S, size=S)
        vals = []
        for s in picks:
            arr = per_seed_arrays[s]
            vals.append(arr[rng.integers(0, arr.size, size=arr.size)].mean())
        means[i] = float(np.mean(vals))
    a = (1.0 - level) / 2.0
    lo, hi = np.quantile(means, [a, 1.0 - a])
    return grand, float(lo), float(hi)


def run_expB(regime: str = "aboutness", seeds=SEEDS) -> ExpBVerdict:
    """Full preregistered Experiment B over `seeds`. Returns the attribution verdict."""
    per_seed_trend_slope = []
    trend_rows_by_seed, gap_by_seed = [], []
    hop_deltas = {h: [] for h in (0, 1, 2)}
    hop_deltas_spread = {h: [] for h in (0, 1, 2)}
    lam_per_seed = []

    for seed in seeds:
        world, ndcg, test_q, lam = _eval_world(regime, seed)
        lam_per_seed.append(lam)
        hop = world.query_hop

        q_h0 = np.array([q for q in test_q if hop[int(q)] == TREND_HOP])
        rows = np.stack([
            np.array([ndcg["additive_j"][lv][int(q)] - ndcg["cosine"][lv][int(q)] for lv in sl.LENGTH_ORDER])
            for q in q_h0])
        trend_rows_by_seed.append(rows)
        slope, _ = sp.paired_trend_p(rows, n_perm=200, seed=seed)
        per_seed_trend_slope.append(slope)
        gap_by_seed.append(rows[:, -1] - rows[:, 0])

        for h in (0, 1, 2):
            qs = np.array([q for q in test_q if hop[int(q)] == h])
            hop_deltas[h].append(np.array(
                [ndcg["additive_j"][HOP_FIXED_LEVEL][int(q)] - ndcg["cosine"][HOP_FIXED_LEVEL][int(q)] for q in qs]))
            hop_deltas_spread[h].append(np.array(
                [ndcg["spread"][HOP_FIXED_LEVEL][int(q)] - ndcg["cosine"][HOP_FIXED_LEVEL][int(q)] for q in qs]))

    all_rows = np.concatenate(trend_rows_by_seed)
    trend_slope, trend_p = sp.paired_trend_p(all_rows, n_perm=5000, seed=0)
    gap_mean, gap_lo, gap_hi = _cluster_ci(gap_by_seed, seed=0)
    rise_paragraph = float((all_rows[:, 1] - all_rows[:, 0]).mean())  # hump visibility (review MINOR)

    hd = {h: np.concatenate(hop_deltas[h]) for h in (0, 1, 2)}
    hds = {h: np.concatenate(hop_deltas_spread[h]) for h in (0, 1, 2)}
    hop_drop_by_seed = [hop_deltas[0][i].mean() - hop_deltas[2][i].mean() for i in range(len(seeds))]
    drop_mean, drop_lo, drop_hi = _cluster_ci(
        [hop_deltas[0][i] - float(hop_deltas[2][i].mean()) for i in range(len(seeds))], seed=1)
    hop_drop_hswm = float(hd[0].mean() - hd[2].mean())
    hop_drop_spread = float(hds[0].mean() - hds[2].mean())

    overall = float(all_rows.mean())
    sigma = float(np.concatenate(gap_by_seed).std(ddof=1))
    numbers = {
        "arm_definition": "additive_j = cosine + λ·simulated-judge-bits (D1 design; NOT the full HSWM field)",
        "world_premise": {"n_topics": 60, "gold_units_per_topic": 3, "regime": regime},
        "lambda_per_seed": lam_per_seed,
        "trend_slope": round(trend_slope, 4), "trend_p": round(trend_p, 4),
        "gap_chapter_minus_sentence": round(gap_mean, 4),
        "gap_cluster_ci95": [round(gap_lo, 4), round(gap_hi, 4)],
        "rise_paragraph_minus_sentence": round(rise_paragraph, 4),
        "delta_by_level_h0": {lv: round(float(all_rows[:, i].mean()), 4)
                              for i, lv in enumerate(sl.LENGTH_ORDER)},
        "delta_by_hop_fixed_level": {h: round(float(hd[h].mean()), 4) for h in hd},
        "delta_by_hop_spread_arm": {h: round(float(hds[h].mean()), 4) for h in hds},
        "hop_drop_additive_j": round(hop_drop_hswm, 4),
        "hop_drop_cluster_ci95": [round(drop_lo, 4), round(drop_hi, 4)],
        "hop_drop_expected_mechanical": round((1.0 - CHAIN_FOLLOW) * float(hd[0].mean()), 4),
        "hop_drop_spread": round(hop_drop_spread, 4),
        "spread_null_offset_note": "spread arm carries a measured null bias (see null-run numbers); reported, not gated",
        "seed_slope_report": sp.seed_variance_report(per_seed_trend_slope),
        "seed_hop_drop_report": sp.seed_variance_report(hop_drop_by_seed),
        "required_n_for_MARGIN": sp.required_n(sigma, MARGIN) if sigma > 0 else 1,
        "overall_mean_delta_h0": round(overall, 4),
    }

    # ---- teeth gate (review fix: cover BOTH H1 and H2 additive_j quantities) ----
    if regime == "null":
        h1_ok = abs(overall) < TOL and (trend_p > ALPHA or abs(trend_slope) < 1e-3)
        h2_ok = abs(hop_drop_hswm) < TOL and all(abs(float(hd[h].mean())) < TOL for h in hd)
        numbers["null_spread_measured_bias"] = {h: round(float(hds[h].mean()), 4) for h in hds}
        if h1_ok and h2_ok:
            return ExpBVerdict(regime, "NO_GAIN",
                               "null regime shows no additive_j gain on H1 or H2 paths; harness has teeth "
                               "(spread-arm null bias measured and reported, not gated).", numbers)
        return ExpBVerdict(regime, "HARNESS_BROKEN",
                           f"null regime produced signal (H1_ok={h1_ok}, H2_ok={h2_ok}) — fix before trusting results.",
                           numbers)

    # ---- preregistered attribution (aboutness regime; symmetric standards) ----
    length_confirmed = (trend_p < ALPHA) and (gap_mean >= MARGIN) and (gap_lo > 0)
    hop_demo = (hop_drop_hswm >= MARGIN) and (drop_lo > 0) and (hop_drop_spread <= 0.5 * hop_drop_hswm)

    if length_confirmed and hop_demo:
        att = "BOTH"
        why = ("delta grows with unit length (mechanism-sufficiency for the owner's premise) AND the injected "
               "CHAIN_FOLLOW conditional-relevance failure reproduces the hop collapse (demonstration, not attribution).")
    elif length_confirmed:
        att, why = "LENGTH_CONFIRMED", ("delta grows monotonically with unit length under the aboutness premise; "
                                        "hop-collapse demonstration did not meet thresholds.")
    elif hop_demo:
        att, why = "HOP_DEMO_ONLY", ("monotone length trend NOT established under the aboutness premise; hop collapse "
                                     "REPRODUCED BY CONSTRUCTION (CHAIN_FOLLOW mechanism demo — see "
                                     "hop_drop_expected_mechanical vs observed).")
    else:
        att, why = "NEITHER", "neither the length trend nor the hop-collapse demonstration met preregistered thresholds."
    return ExpBVerdict(regime, att, why, numbers)


if __name__ == "__main__":
    for regime in ("aboutness", "null"):
        v = run_expB(regime)
        print(f"[{regime}] {v.attribution} — {v.reason}")
        for k_, v_ in v.numbers.items():
            print(f"    {k_}: {v_}")
