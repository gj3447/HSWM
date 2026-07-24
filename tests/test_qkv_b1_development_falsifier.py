from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest
from hashlib import sha256

import composition as comp
import qkv_b1_development_falsifier as falsifier
from world_ir import canonical_json


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


# --- v2.4.6 guard-path fixtures (vacuity 0/8: the drift-detection guards were
# never fed drifted inputs; utilities were tested, guards were not) ---

def _segment_file(tmp_path, *, split="development", dataset="ds", qids=("q1", "q2")):
    seg = {"split": split, "dataset": dataset,
           "evaluation_rows": [{"qid": q} for q in qids]}
    p = tmp_path / "segment.json"
    p.write_text(json.dumps(seg), encoding="utf-8")
    return p


def _sidecar_file(tmp_path, *, dataset="ds", rows=(), digest=None):
    rows = list(rows)
    wrapper = {"dataset": dataset, "rows": rows,
               "rows_sha256": digest or sha256(
                   canonical_json(tuple(rows)).encode("utf-8")).hexdigest()}
    p = tmp_path / "sidecar.json"
    p.write_text(json.dumps(wrapper), encoding="utf-8")
    return p


def _rows(*qids):
    return [{"id": q, "relation": "r"} for q in qids]


def test_guard_accepts_valid_segment_and_sidecar(tmp_path):
    """Positive fixture — also kills the NotEq->Eq guard inversions, which turn
    every valid input into a spurious DevelopmentFalsifierError."""
    seg = _segment_file(tmp_path)
    side = _sidecar_file(tmp_path, rows=_rows("q1", "q2"))
    ds = SimpleNamespace(segment_path=str(seg), dataset="ds")
    selected, qids = falsifier._raw_rows_for_segment(ds, side)  # noqa: SLF001
    assert qids == ("q1", "q2")
    assert len(selected) == 2


def test_guard_rejects_segment_split_drift(tmp_path):
    seg = _segment_file(tmp_path, split="test")
    side = _sidecar_file(tmp_path, rows=_rows("q1", "q2"))
    ds = SimpleNamespace(segment_path=str(seg), dataset="ds")
    with pytest.raises(falsifier.DevelopmentFalsifierError, match="identity/split drift"):
        falsifier._raw_rows_for_segment(ds, side)  # noqa: SLF001


def test_guard_rejects_duplicate_qids(tmp_path):
    seg = _segment_file(tmp_path, qids=("q1", "q1"))
    side = _sidecar_file(tmp_path, rows=_rows("q1"))
    ds = SimpleNamespace(segment_path=str(seg), dataset="ds")
    with pytest.raises(falsifier.DevelopmentFalsifierError, match="unique"):
        falsifier._raw_rows_for_segment(ds, side)  # noqa: SLF001


def test_guard_rejects_sidecar_identity_drift(tmp_path):
    seg = _segment_file(tmp_path)
    side = _sidecar_file(tmp_path, dataset="OTHER", rows=_rows("q1", "q2"))
    ds = SimpleNamespace(segment_path=str(seg), dataset="ds")
    with pytest.raises(falsifier.DevelopmentFalsifierError, match="sidecar identity drift"):
        falsifier._raw_rows_for_segment(ds, side)  # noqa: SLF001


def test_guard_rejects_sidecar_digest_mismatch(tmp_path):
    seg = _segment_file(tmp_path)
    side = _sidecar_file(tmp_path, rows=_rows("q1", "q2"), digest="0" * 64)
    ds = SimpleNamespace(segment_path=str(seg), dataset="ds")
    with pytest.raises(falsifier.DevelopmentFalsifierError, match="digest mismatch"):
        falsifier._raw_rows_for_segment(ds, side)  # noqa: SLF001


def test_split_bindings_partition_matches_assignments(tmp_path, monkeypatch):
    """cmp@114/118 (== 'val' / == 'test' inversions): the val/test partition
    must mirror the suite assignments exactly — an inversion silently swaps
    or merges the evaluation halves without raising."""
    seg = _segment_file(tmp_path)
    side = _sidecar_file(tmp_path, rows=_rows("q1", "q2"))
    ds = SimpleNamespace(segment_path=str(seg), dataset="ds",
                         queries=[SimpleNamespace(qid="q1"), SimpleNamespace(qid="q2")])
    stub = SimpleNamespace(
        examples=[SimpleNamespace(qid="q1", occurrence_id="o1"),
                  SimpleNamespace(qid="q2", occurrence_id="o2")],
        assignments=[SimpleNamespace(occurrence_id="o1", split="val", component_id="c1"),
                     SimpleNamespace(occurrence_id="o2", split="test", component_id="c2")],
        suite_id="stub", raw_snapshot_sha256="0" * 64,
    )
    monkeypatch.setattr(falsifier.reval, "build_relation_evaluation_suite",
                        lambda *a, **k: stub)
    val, test, components, _meta = falsifier._split_bindings(ds, side)  # noqa: SLF001
    assert val == (0,)
    assert test == (1,)
    assert components == ("c1", "c2")
