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


# --- v2.4.4 oracle strengthening (vacuity 0/8: judge-bit corruption and spread
# damping/clip mutants passed because tests pinned structure, not behavior) ---

def test_judge_bits_binary_and_track_owner(monkeypatch):
    """Kills cmp@99 (owner==target inversion), binop@101 (1-bits -> 1+bits),
    cmp@97 Eq->NotEq (hop!=0 forces chain resolution when CHAIN_FOLLOW=0).
    Boundary twins (cmp@97.74 Lt->LtE, cmp@100 Gt->GtE) are measure-zero
    equivalents and are expected to survive by design."""
    import expB_longdoc as eb
    monkeypatch.setattr(eb, "CHAIN_FOLLOW", 0.0)   # deterministic: target is always t0
    w = sl.generate("aboutness", seed=2)
    rng = np.random.default_rng(0)
    pool = np.arange(60)
    rates = []
    for q in range(w.Q):
        t0 = int(w.query_topic[q])
        owner = w.unit_owner["chapter"][pool]
        bits = eb._judge_bits(w, "chapter", q, pool, rng)
        assert set(np.unique(bits)) <= {0.0, 1.0}, "judge bits must stay binary"
        rates.append(float((bits == (owner == t0).astype(float)).mean()))
    rate = float(np.mean(rates))
    assert abs(rate - eb.JUDGE_ACC) < 0.05, f"judge agreement {rate} != JUDGE_ACC {eb.JUDGE_ACC}"


def test_judge_never_resolves_chain_when_follow_rate_zero(monkeypatch):
    """cmp@97.62 (hop==0 -> hop!=0): with CHAIN_FOLLOW=0 the judge must NEVER
    resolve the chain for hop>0 queries. Counts actual _chain_target calls."""
    import expB_longdoc as eb
    w = sl.generate("aboutness", seed=2)
    monkeypatch.setattr(eb, "CHAIN_FOLLOW", 0.0)
    calls = []
    orig = sl._chain_target
    monkeypatch.setattr(sl, "_chain_target",
                        lambda *a: (calls.append(a), orig(*a))[1])
    rng = np.random.default_rng(0)
    pool = np.arange(20)
    hop_qs = [q for q in range(w.Q) if int(w.query_hop[q]) > 0]
    assert hop_qs, "fixture must contain hop>0 queries"
    for q in hop_qs[:5]:
        eb._judge_bits(w, "chapter", q, pool, rng)
    assert calls == [], "chain resolved despite CHAIN_FOLLOW=0 (injected hop!=0 branch)"


def test_spread_scores_nonneg_and_bounded():
    """Kills clip@108 (negative activations leak), binop@113 Add->Sub
    ((1-γ) -> (1+γ) amplification) and Mult->Add ((1-γ)*act -> (1-γ)+act).
    The sentence level (arity 1) exposes amplification that member-mean
    dilution hides at coarser levels."""
    import expB_longdoc as eb
    w = sl.generate("aboutness", seed=4)
    pool = np.arange(60)
    for level in ("sentence", "chapter"):
        for q in range(0, w.Q, 5):
            s = eb._spread_scores(w, level, q, pool)
            assert np.isfinite(s).all()
            assert (s >= -1e-12).all(), f"{level}: spread scores must stay nonnegative"
            assert (s <= 1.0 + 1e-9).all(), f"{level}: damped spread must stay <= 1"
