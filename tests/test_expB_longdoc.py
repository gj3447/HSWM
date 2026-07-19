"""Experiment B harness must have TEETH and honest paired structure (v2).

Review wf_a931ba07-21a fixes locked in by test:
- null regime NO_GAIN must cover BOTH H1 and H2 additive_j quantities;
- candidate_pool must be process-deterministic (no hash());
- gold base rate must be CONSTANT across length strata (the v1 saturation
  artifact must be structurally impossible);
- dilution must still be real (the length axis is live, not neutralized).
"""
import numpy as np

import synth_longdoc as sl
from expB_longdoc import TOL, ExpBVerdict, run_expB


def test_world_gold_constant_base_rate_and_paired_across_strata():
    w = sl.generate("aboutness", seed=0)
    for level in sl.LENGTH_ORDER:
        assert len(w.gold[level]) == w.Q                      # same query set per stratum
        sizes = {g.size for g in w.gold[level]}
        assert sizes == {3}, f"{level}: gold sizes {sizes} != {{3}} (base-rate must not scale with length)"
    for q in (0, 1, 5):
        pool = sl.candidate_pool(w, "chapter", q, 40, seed=0)
        assert np.intersect1d(pool, w.gold["chapter"][q]).size == w.gold["chapter"][q].size


def test_designed_units_have_exact_arity_and_owner_membership():
    w = sl.generate("aboutness", seed=3)
    for level in sl.LENGTH_ORDER:
        k = sl.LENGTH_LEVELS[level]
        owners = w.unit_owner[level]
        for j in np.flatnonzero(owners >= 0)[:50]:
            mem = w.unit_topics[level][int(j)]
            assert mem.size == k, f"{level} unit {j}: arity {mem.size} != {k}"
            assert owners[j] in mem, "owner topic must be a member of its designed unit"


def test_candidate_pool_is_deterministic():
    w = sl.generate("aboutness", seed=1)
    a = sl.candidate_pool(w, "section", 7, 40, seed=5)
    b = sl.candidate_pool(w, "section", 7, 40, seed=5)
    assert np.array_equal(a, b)


def test_embedding_dilution_grows_with_length():
    """cosine(query, gold-unit embedding) must fall as units lengthen — the axis is live."""
    w = sl.generate("aboutness", seed=1)
    sims = {}
    for level in sl.LENGTH_ORDER:
        hg = w.strata[level]
        vals = []
        for q in range(0, w.Q, 7):
            if int(w.query_hop[q]) != 0:
                continue
            g = w.gold[level][q]
            qe = w.query_emb[q]
            vals.append(float((hg.unit_emb[g] @ qe).mean()))
        sims[level] = float(np.mean(vals))
    assert sims["sentence"] > sims["chapter"], sims


def test_null_regime_has_teeth_on_both_pathways():
    v = run_expB("null", seeds=(0, 1))
    assert isinstance(v, ExpBVerdict)
    assert v.attribution == "NO_GAIN", (v.attribution, v.reason, v.numbers)
    # numeric teeth (review: gate must cover the H2 quantities the verdict rests on)
    assert abs(v.numbers["hop_drop_additive_j"]) < TOL
    for h, d in v.numbers["delta_by_hop_fixed_level"].items():
        assert abs(d) < TOL, (h, d)
    assert "null_spread_measured_bias" in v.numbers  # measured, reported, not gated


def test_aboutness_regime_returns_genuine_attribution():
    v = run_expB("aboutness", seeds=(0, 1))
    assert v.attribution in {"LENGTH_CONFIRMED", "HOP_DEMO_ONLY", "BOTH", "NEITHER"}
    for key in ("arm_definition", "world_premise", "trend_slope", "trend_p",
                "gap_chapter_minus_sentence", "gap_cluster_ci95",
                "rise_paragraph_minus_sentence", "delta_by_level_h0",
                "delta_by_hop_fixed_level", "delta_by_hop_spread_arm",
                "hop_drop_additive_j", "hop_drop_cluster_ci95",
                "hop_drop_expected_mechanical", "hop_drop_spread",
                "seed_slope_report", "seed_hop_drop_report",
                "required_n_for_MARGIN", "lambda_per_seed"):
        assert key in v.numbers, key
    for lam in v.numbers["lambda_per_seed"]:
        assert lam in (0.0, 0.1, 0.2, 0.4, 0.8)  # cosine floor: 0 admissible
