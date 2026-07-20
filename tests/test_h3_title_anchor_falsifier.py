import numpy as np

import h3_title_anchor_falsifier as h3


def test_cluster_bootstrap_uses_components_and_detects_positive_delta():
    result = h3.cluster_bootstrap(
        np.array([0.1, 0.2, 0.3, 0.4]),
        ("a", "a", "b", "c"), n_boot=2000, seed=7, n_permutations=10000,
    )
    assert result["n_queries"] == 4
    assert result["n_components"] == 3
    assert result["mean_delta"] == 0.25
    assert result["ci95"][0] > 0
    assert result["p_cluster_signflip_one_sided"] < 0.2


def test_query_metrics_requires_all_supports_for_asr10():
    scores = np.arange(20, dtype=np.float64)
    all_in = h3.query_metrics(scores, np.array([19, 18]))
    one_out = h3.query_metrics(scores, np.array([19, 0]))
    assert all_in["asr10"] == 1.0
    assert one_out["asr10"] == 0.0
    assert one_out["support_recall10"] == 0.5


def test_rrf_is_rank_only_and_shape_preserving():
    cosine = np.array([[0.9, 0.1, 0.2], [0.0, 0.5, 0.4]])
    bm25 = np.array([[1.0, 3.0, 2.0], [4.0, 1.0, 2.0]])
    out = h3.rrf_scores(cosine, bm25)
    assert out.shape == cosine.shape
    assert np.isfinite(out).all()
    transformed = h3.rrf_scores(cosine * 100.0 + 7.0, np.exp(bm25))
    np.testing.assert_array_equal(out, transformed)


def test_paired_gate_refuses_zero_and_accepts_stable_positive_effect():
    assert not h3._paired_gate(np.zeros(20))["passes"]
    assert h3._paired_gate(np.full(20, 0.03))["passes"]


def test_bh_qvalues_are_monotone_and_keyed():
    q = h3._bh_qvalues([("a", 0.001), ("b", 0.02), ("c", 0.2), ("d", 0.8)])
    assert set(q) == {"a", "b", "c", "d"}
    assert q["a"] <= q["b"] <= q["c"] <= q["d"]
    assert q["a"] == 0.004
