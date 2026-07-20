from __future__ import annotations

import numpy as np

import composition as comp
import qkv_b1_development_falsifier as falsifier


def test_policy_grid_matches_frozen_experiment_surface() -> None:
    assert len(falsifier.POLICY_GRID) == 24
    assert {item.seed_k for item in falsifier.POLICY_GRID} == {3, 10}
    assert {item.temperature for item in falsifier.POLICY_GRID} == {0.05, 0.1, 0.2}
    assert {item.gamma for item in falsifier.POLICY_GRID} == {0.1, 0.25, 0.5, 1.0}
    assert {item.hops for item in falsifier.POLICY_GRID} == {2}


def test_component_bootstrap_is_deterministic_and_not_query_iid() -> None:
    delta = np.asarray([1.0, 1.0, -1.0, 0.5], dtype=np.float64)
    components = ("shared", "shared", "solo-a", "solo-b")

    first = falsifier._cluster_bootstrap(  # noqa: SLF001
        delta, components, seed=7, n_bootstrap=1000,
    )
    second = falsifier._cluster_bootstrap(  # noqa: SLF001
        delta, components, seed=7, n_bootstrap=1000,
    )

    assert first == second
    assert first["n_components"] == 3
    assert first["mean_delta"] == 0.375
    assert first["n_bootstrap"] == 1000


def test_multigraph_value_shuffle_preserves_exact_in_and_out_degrees() -> None:
    graph = comp.make_graph(
        ("a", "b", "c", "d"),
        (
            comp.EvidenceArcV1(0, 1, "r0", 0, 1, "x", "x"),
            comp.EvidenceArcV1(0, 1, "r1", 0, 1, "y", "y"),
            comp.EvidenceArcV1(1, 2, "r2", 0, 1, "z", "z"),
            comp.EvidenceArcV1(2, 3, "r3", 0, 1, "w", "w"),
            comp.EvidenceArcV1(3, 0, "r4", 0, 1, "q", "q"),
        ),
    )
    shuffled = falsifier._degree_preserving_value_shuffle(  # noqa: SLF001
        graph, 7,
    )

    assert shuffled.is_null_control
    assert len(shuffled.arcs) == len(graph.arcs)
    assert sorted(item.source_target for item in shuffled.arcs) == sorted(
        item.source_target for item in graph.arcs
    )
    assert sorted(item.target_target for item in shuffled.arcs) == sorted(
        item.target_target for item in graph.arcs
    )
    assert all(item.source_target != item.target_target for item in shuffled.arcs)
    assert falsifier._edge_multiset(shuffled) != falsifier._edge_multiset(graph)  # noqa: SLF001
