"""stats_protocol must detect real effects, stay calm under null, and match hand math."""
import numpy as np

import stats_protocol as sp


def test_permutation_detects_real_effect_and_holds_under_null():
    rng = np.random.default_rng(0)
    effect = rng.normal(0.05, 0.1, size=200)      # true mean 0.05
    null = rng.normal(0.0, 0.1, size=200)
    assert sp.paired_permutation_p(effect) < 0.01
    assert sp.paired_permutation_p(null) > 0.05


def test_permutation_never_returns_zero_and_handles_empty():
    assert sp.paired_permutation_p(np.array([1.0] * 5)) > 0.0
    assert sp.paired_permutation_p(np.array([])) == 1.0


def test_bootstrap_ci_excludes_zero_only_for_real_gain():
    rng = np.random.default_rng(1)
    m, lo, hi = sp.bootstrap_ci(rng.normal(0.05, 0.1, size=300))
    assert lo > 0.0 and lo < m < hi
    m2, lo2, hi2 = sp.bootstrap_ci(rng.normal(0.0, 0.1, size=300))
    assert lo2 < 0.0 < hi2


def test_required_n_matches_hand_calculation():
    # n = ceil(7.85 * (0.2/0.04)^2) = ceil(196.25) = 197
    assert sp.required_n(0.2, 0.04) == 197
    assert sp.required_n(0.1, 0.03) == int(np.ceil(7.85 * (0.1 / 0.03) ** 2))
    assert sp.required_n(0.0, 0.03) == 1


def test_bh_adjust_known_example():
    # classic: p=(.01,.02,.03,.04) m=4 -> adj=(.04,.04,.04,.04)
    adj = sp.bh_adjust([0.01, 0.02, 0.03, 0.04])
    assert np.allclose(adj, [0.04, 0.04, 0.04, 0.04])
    adj2 = sp.bh_adjust([0.001, 0.5])
    assert adj2[0] == 0.002 and adj2[1] == 0.5


def test_paired_trend_detects_monotone_increase_not_flat():
    rng = np.random.default_rng(2)
    n_q = 120
    increasing = np.linspace(0.0, 0.12, 4)[None, :] + rng.normal(0, 0.05, size=(n_q, 4))
    slope, p = sp.paired_trend_p(increasing, n_perm=2000, seed=0)
    assert slope > 0 and p < 0.01
    flat = rng.normal(0, 0.05, size=(n_q, 4))
    _, p_flat = sp.paired_trend_p(flat, n_perm=2000, seed=0)
    assert p_flat > 0.05


def test_seed_variance_report_shape():
    rep = sp.seed_variance_report([0.1, 0.12, 0.09])
    assert rep["n_seeds"] == 3 and rep["std"] > 0
