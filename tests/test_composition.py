import numpy as np

import composition as cp


def _graph():
    return cp.make_graph(
        ("p0", "p1", "p2", "p3"),
        (
            cp.EvidenceArcV1(0, 1, "s0", 3, 8, "Alpha", "alpha"),
            cp.EvidenceArcV1(1, 2, "s1", 5, 9, "Beta", "beta"),
            cp.EvidenceArcV1(3, 2, "s3", 0, 5, "Gamma", "gamma"),
        ),
    )


def test_mu_zero_is_bit_identical_and_never_composes():
    scores = np.array([0.9, 0.2, 0.1, -0.1], dtype=np.float64)
    final, residual, receipt = cp.compose_scores(
        scores, _graph(), cp.CompositionPolicyV1(seed_k=1, hops=2, mu=0.0),
    )
    assert final.tobytes() == scores.tobytes()
    assert not residual.any()
    assert receipt.trip_reason == "mu=0 certified floor"


def test_two_role_paths_compose_and_carry_exact_evidence():
    scores = np.array([0.9, 0.2, 0.1, -0.1], dtype=np.float64)
    final, residual, receipt = cp.compose_scores(
        scores, _graph(),
        cp.CompositionPolicyV1(
            seed_k=1, hops=2, mu=0.2, direction="forward",
            fanout_exponent=0.5,
        ),
    )
    assert receipt.reached_targets == 2
    assert final[2] > scores[2]
    path = next(p for p in receipt.promoted_paths if p.target == 2)
    assert [s.selector_exact for s in path.steps] == ["Alpha", "Beta"]
    assert len(path.steps) == 2


def test_fanout_guard_refuses_unsupported_spread_without_payload_change():
    graph = cp.make_graph(
        ("p0", "p1", "p2"),
        (
            cp.EvidenceArcV1(0, 1, "s", 0, 1, "A", "a"),
            cp.EvidenceArcV1(0, 2, "s", 2, 3, "B", "b"),
        ),
    )
    scores = np.array([0.9, 0.2, 0.1])
    final, residual, receipt = cp.compose_scores(
        scores, graph,
        cp.CompositionPolicyV1(seed_k=1, hops=1, mu=0.2, max_fanout=1),
    )
    assert final.tobytes() == scores.tobytes()
    assert not residual.any()
    assert "fanout guard" in receipt.trip_reason


def test_shuffle_preserves_directed_degree_and_marks_null_control():
    graph = _graph()
    shuffled = cp.degree_preserving_shuffle(graph, seed=7, attempts_per_arc=100)
    before_out = np.bincount([a.source_target for a in graph.arcs], minlength=graph.n_targets)
    after_out = np.bincount([a.source_target for a in shuffled.arcs], minlength=graph.n_targets)
    before_in = np.bincount([a.target_target for a in graph.arcs], minlength=graph.n_targets)
    after_in = np.bincount([a.target_target for a in shuffled.arcs], minlength=graph.n_targets)
    np.testing.assert_array_equal(before_out, after_out)
    np.testing.assert_array_equal(before_in, after_in)
    assert shuffled.is_null_control
    assert shuffled.topology_sha256 != graph.topology_sha256
    assert all(a.selector_exact == "NULL_CONTROL" for a in shuffled.arcs)


def test_graph_and_scores_are_input_order_deterministic():
    graph = _graph()
    reverse = cp.make_graph(graph.target_ids, reversed(graph.arcs))
    assert reverse == graph
    scores = np.array([0.7, 0.4, 0.2, 0.1])
    policy = cp.CompositionPolicyV1(seed_k=2, hops=2, mu=0.1)
    a = cp.compose_scores(scores, graph, policy)
    b = cp.compose_scores(scores, reverse, policy)
    np.testing.assert_array_equal(a[0], b[0])
    assert a[2] == b[2]


def test_equal_score_converging_paths_use_stable_index_tie_break():
    graph = cp.make_graph(
        ("p0", "p1", "p2", "p3"),
        (
            cp.EvidenceArcV1(0, 2, "s0", 0, 1, "A", "a"),
            cp.EvidenceArcV1(1, 2, "s1", 0, 1, "B", "b"),
            cp.EvidenceArcV1(2, 3, "s2", 0, 1, "C", "c"),
        ),
    )
    scores = np.array([0.8, 0.8, 0.1, 0.0])
    _, _, receipt = cp.compose_scores(
        scores, graph,
        cp.CompositionPolicyV1(
            seed_k=2, hops=2, mu=0.1, direction="forward",
        ),
    )
    path = next(item for item in receipt.promoted_paths if item.target == 3)
    assert path.steps[0].source_target == 0
