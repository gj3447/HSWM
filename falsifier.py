"""Prereg falsifier harness — learned hyperedge weight vs STRONG heuristics.

Faithful (minimal) implementation of DB_AND_FALSIFIER_DECISION_2026-07-19.md §2.
The point is that this harness can return REFUTED / EXCLUDED, not just SUPPORTED.

Pre-registered constants (fixed BEFORE any run; do not renegotiate after seeing
results):
  MARGIN = 0.03   learned must beat best_heuristic / null-head / param-free by this
  TOL    = 0.01   manipulation-gate tolerance
  CEIL   = 0.85   headroom gate: best_heuristic must be below this (room to win)
  ALPHA  = 0.0167 paired-bootstrap significance (Bonferroni-ish)

Documented simplifications vs the full protocol (honesty; §2.10 "미해결"):
- Manipulation gate here checks only NON-semantic lone signals (frequency,
  recency) against best_heuristic; the full protocol also certifies raw-cosine
  ~ random, which this synthetic minimal version does not (raw cosine is kept as
  a legitimate semantic baseline). Real-data run must add that certification.
- Downstream "answer" is a top-1-gold proxy, not a real reader EM/F1.
- Seeds regenerate the whole world (replication across synthetic worlds).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import metrics
import synth
import weight_field as wf
from learned import train_bilinear
from weight_field import WeightField

MARGIN = 0.03
TOL = 0.01
CEIL = 0.85
ALPHA = 0.0167
POOL_SIZE = 60
K = 10


@dataclass
class Verdict:
    regime: str
    label: str                       # SUPPORTED / REFUTED / INCONCLUSIVE / EXCLUDED
    reason: str
    numbers: dict = field(default_factory=dict)


def _score_pool(scorer_name: str, hg, query, pool, M_real, M_null):
    """Return per-edge scores over `pool` for the named scorer."""
    if scorer_name == "learned":
        return WeightField(hg, M=M_real).value(query, pool)
    if scorer_name == "null":
        return WeightField(hg, M=M_null).value(query, pool)
    if scorer_name == "cosine":
        return WeightField(hg, M=None).value(query, pool)  # param-free control (#8)
    return wf.HEURISTICS[scorer_name](hg, query, pool)


SCORERS = ["learned", "null", "cosine", "frequency", "recency", "rrf"]
HEURISTIC_SET = ["cosine", "frequency", "recency", "rrf"]


def _eval_seed(regime: str, seed: int, train_frac: float = 0.6):
    ds = synth.generate(regime, seed=seed)
    rng = np.random.default_rng(seed * 131 + 5)
    perm = rng.permutation(ds.Q)
    n_train = int(ds.Q * train_frac)
    train_q, test_q = perm[:n_train], perm[n_train:]

    M_real = train_bilinear(ds, train_q, pool_size=POOL_SIZE, seed=seed, shuffle_labels=False)
    M_null = train_bilinear(ds, train_q, pool_size=POOL_SIZE, seed=seed, shuffle_labels=True)

    # per-query metrics on the test split
    per_q_ndcg = {s: [] for s in SCORERS}
    per_q_em = {s: [] for s in SCORERS}
    gold_recall = []
    for q in test_q:
        pool = synth.candidate_pool(ds, int(q), POOL_SIZE, seed)
        gold_in_pool = np.intersect1d(ds.gold[int(q)], pool)
        gold_recall.append(gold_in_pool.size / max(ds.gold[int(q)].size, 1))
        for s in SCORERS:
            sc = _score_pool(s, ds.hg, ds.query_emb[int(q)], pool, M_real, M_null)
            per_q_ndcg[s].append(metrics.ndcg_at_k(sc, ds.gold[int(q)], pool, k=K, seed=seed))
            per_q_em[s].append(metrics.answer_em(sc, ds.gold[int(q)], pool, seed=seed))
    out = {
        "ndcg": {s: np.array(per_q_ndcg[s]) for s in SCORERS},
        "em": {s: np.array(per_q_em[s]) for s in SCORERS},
        "gold_recall": float(np.mean(gold_recall)),
    }
    return out


def run_falsifier(regime: str, seeds=(0, 1, 2, 3, 4)) -> Verdict:
    """Run the full prereg falsifier for one regime. Returns a Verdict."""
    seed_results = [_eval_seed(regime, s) for s in seeds]

    # per-seed means
    def seed_mean(res, scorer, metric="ndcg"):
        return float(res[metric][scorer].mean())

    # best heuristic per seed (by test-mean nDCG)
    best_heur_name_per_seed = []
    for res in seed_results:
        means = {h: seed_mean(res, h) for h in HEURISTIC_SET}
        best_heur_name_per_seed.append(max(means, key=means.get))

    learned_seed_means = [seed_mean(r, "learned") for r in seed_results]
    bestheur_seed_means = [seed_mean(r, best_heur_name_per_seed[i]) for i, r in enumerate(seed_results)]
    null_seed_means = [seed_mean(r, "null") for r in seed_results]
    cos_seed_means = [seed_mean(r, "cosine") for r in seed_results]
    freq_seed_means = [seed_mean(r, "frequency") for r in seed_results]
    rec_seed_means = [seed_mean(r, "recency") for r in seed_results]

    m_learned = float(np.mean(learned_seed_means))
    m_bestheur = float(np.mean(bestheur_seed_means))
    m_null = float(np.mean(null_seed_means))
    m_cos = float(np.mean(cos_seed_means))

    numbers = {
        "mean_learned_ndcg": round(m_learned, 4),
        "mean_best_heuristic_ndcg": round(m_bestheur, 4),
        "mean_null_head_ndcg": round(m_null, 4),
        "mean_cosine_ndcg": round(m_cos, 4),
        "mean_frequency_ndcg": round(float(np.mean(freq_seed_means)), 4),
        "mean_recency_ndcg": round(float(np.mean(rec_seed_means)), 4),
        "best_heuristic_per_seed": best_heur_name_per_seed,
        "gold_recall": round(float(np.mean([r["gold_recall"] for r in seed_results])), 3),
        "worst_seed_learned": round(min(learned_seed_means), 4),
        "worst_seed_best_heuristic": round(min(bestheur_seed_means), 4),
    }

    # ---- Gate 1: manipulation (non-semantic lone signal ~ best heuristic) ----
    lone = max(float(np.mean(freq_seed_means)), float(np.mean(rec_seed_means)))
    if lone >= m_bestheur - TOL:
        return Verdict(regime, "EXCLUDED",
                       f"manipulable: lone non-semantic signal ({lone:.3f}) >= best_heuristic-{TOL} "
                       f"({m_bestheur - TOL:.3f}); dataset shortcut-solvable, uninformative.",
                       numbers)

    # ---- Gate 2: headroom / ceiling ----
    if m_bestheur >= CEIL:
        return Verdict(regime, "EXCLUDED",
                       f"ceiling: best_heuristic {m_bestheur:.3f} >= {CEIL}; no room to demonstrate a win.",
                       numbers)

    # ---- co-primary answer gate ----
    m_em_learned = float(np.mean([seed_mean(r, "learned", "em") for r in seed_results]))
    m_em_bestheur = float(np.mean([seed_mean(r, best_heur_name_per_seed[i], "em")
                                   for i, r in enumerate(seed_results)]))
    numbers["mean_learned_em"] = round(m_em_learned, 4)
    numbers["mean_best_heuristic_em"] = round(m_em_bestheur, 4)

    # ---- significance: pooled per-query diff learned - best_heur ----
    diffs = []
    for i, r in enumerate(seed_results):
        diffs.append(r["ndcg"]["learned"] - r["ndcg"][best_heur_name_per_seed[i]])
    diffs = np.concatenate(diffs)
    # one-sided p that mean(learned - best_heuristic) > 0 is NOT true
    p = metrics.paired_bootstrap_p(diffs, np.zeros_like(diffs), seed=0)
    numbers["paired_bootstrap_p"] = round(p, 4)
    numbers["mean_ndcg_gain"] = round(float(diffs.mean()), 4)

    # ---- decision rule (§2.7) ----
    beats_heur = m_learned >= m_bestheur + MARGIN
    beats_null = m_learned >= m_null + MARGIN
    beats_cos = m_learned >= m_cos + MARGIN
    worst_ok = min(learned_seed_means) >= min(bestheur_seed_means)
    sig_ok = p < ALPHA
    answer_ok = m_em_learned >= m_em_bestheur

    numbers.update({
        "beats_heuristic_by_margin": beats_heur, "beats_null_head": beats_null,
        "beats_param_free_cosine": beats_cos, "worst_seed_ok": worst_ok,
        "significant": sig_ok, "answer_not_regressed": answer_ok,
    })

    if beats_heur and beats_null and beats_cos and worst_ok and sig_ok and answer_ok:
        return Verdict(regime, "SUPPORTED",
                       "learned field beats best_heuristic, null-head, and param-free cosine by "
                       f">={MARGIN} on all seeds, significant (p={p:.4f}), no answer regression.",
                       numbers)

    if (m_learned < m_bestheur - TOL) or (not beats_null) or (not beats_cos) or (not answer_ok):
        return Verdict(regime, "REFUTED",
                       "learned field failed a hard control: "
                       + ("loses to best_heuristic; " if m_learned < m_bestheur - TOL else "")
                       + ("null-head caught up; " if not beats_null else "")
                       + ("param-free cosine caught up; " if not beats_cos else "")
                       + ("answer-EM regressed; " if not answer_ok else ""),
                       numbers)

    return Verdict(regime, "INCONCLUSIVE",
                   "mean gain present but not all pre-registered clauses met "
                   f"(margin={beats_heur}, worst_seed={worst_ok}, sig={sig_ok}).",
                   numbers)
