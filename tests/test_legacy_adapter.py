"""S2 parity teeth: stable EPWC artifact, exact legacy positional projection."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

import legacy_adapter as la
import readouts
import traversal as tv
from tests.test_world_builder import _rows
from weight_field import WeightField
import world_builder as wb
from world_compiler import compile_world
from world_ir import CompilePolicyV1, EvaluationSuiteV1, ObservationBundleV1, SourceBundleV1


def _assert_world_equal(expected: wb.BuiltWorld, actual: wb.BuiltWorld) -> None:
    assert expected.entities == actual.entities
    assert expected.unit_texts == actual.unit_texts
    assert len(expected.hg.members) == len(actual.hg.members)
    assert all(np.array_equal(a, b) for a, b in zip(expected.hg.members, actual.hg.members))
    assert np.array_equal(expected.hg.node_emb, actual.hg.node_emb)
    assert np.array_equal(expected.hg.unit_emb, actual.hg.unit_emb)
    assert np.array_equal(expected.hg.edge_freq, actual.hg.edge_freq)
    assert np.array_equal(expected.hg.edge_recency, actual.hg.edge_recency)
    assert np.array_equal(expected.hg.base_salience, actual.hg.base_salience)
    assert expected.stats == actual.stats
    assert len(expected.queries) == len(actual.queries)
    for left, right in zip(expected.queries, actual.queries):
        assert left.qid == right.qid
        assert left.question == right.question
        assert left.answer == right.answer
        assert left.hop == right.hop
        assert np.array_equal(left.gold, right.gold)


def test_legacy_fixture_exact_world_parity():
    expected = wb.build(_rows())
    compiled = la.compile_legacy_rows(_rows())
    _assert_world_equal(expected, compiled.world)
    assert len(compiled.stable_ids.entity_ids_by_dense) == compiled.world.hg.N
    assert len(compiled.stable_ids.target_ids_by_dense) == compiled.world.hg.M


def test_embed_fn_exactly_two_calls_in_legacy_order():
    calls: list[list[str]] = []

    def embed(texts):
        calls.append(list(texts))
        base = 1000 * len(calls)
        return np.asarray([[base + i, base + i + 0.25, base + i + 0.5]
                           for i in range(len(texts))], dtype=np.float32)

    compiled = la.compile_legacy_rows(_rows(), embed_fn=embed, dim=999)
    assert len(calls) == 2
    assert calls[0] == compiled.world.entities
    assert calls[1] == compiled.world.unit_texts
    assert compiled.world.hg.node_emb.dtype == np.float64
    assert compiled.world.hg.unit_emb.dtype == np.float64
    assert np.array_equal(compiled.world.hg.node_emb[:, 0],
                          np.arange(len(calls[0]), dtype=np.float64) + 1000)
    assert np.array_equal(compiled.world.hg.unit_emb[:, 0],
                          np.arange(len(calls[1]), dtype=np.float64) + 2000)


def test_order_invariant_artifact_but_order_sensitive_legacy_layout():
    forward_rows = _rows()
    reverse_rows = list(reversed(deepcopy(forward_rows)))
    forward = la.compile_legacy_rows(forward_rows)
    reverse = la.compile_legacy_rows(reverse_rows)
    assert forward.artifact.build_id == reverse.artifact.build_id
    assert set(forward.stable_ids.target_ids_by_dense) == set(reverse.stable_ids.target_ids_by_dense)
    assert forward.layout.edge_ids_first_seen != reverse.layout.edge_ids_first_seen
    _assert_world_equal(wb.build(forward_rows), forward.world)
    _assert_world_equal(wb.build(reverse_rows), reverse.world)


def test_evaluation_labels_cannot_change_world_artifact():
    original_rows = _rows()
    changed_rows = deepcopy(original_rows)
    for row in changed_rows:
        row["question"] = "changed question"
        row["answer"] = "changed answer"
        row["hop"] = "9hop"
        for paragraph in row["paragraphs"]:
            paragraph["is_supporting"] = not paragraph.get("is_supporting", False)
    original = la.compile_legacy_rows(original_rows)
    changed = la.compile_legacy_rows(changed_rows)
    assert original.artifact.build_id == changed.artifact.build_id
    assert original.evaluation != changed.evaluation


def test_downstream_field_readout_and_mu_zero_parity():
    old = wb.build(_rows())
    new = la.compile_legacy_rows(_rows()).world
    q = wb.hash_embed(["Who built the castle feared by whom?"], wb.DEFAULT_DIM)[0]
    old_field = WeightField(old.hg)
    new_field = WeightField(new.hg)
    old_field._pooled = old.hg.unit_emb
    new_field._pooled = new.hg.unit_emb
    assert np.array_equal(old_field.value(q), new_field.value(q))
    assert np.array_equal(readouts.retrieve(old_field, q, k=5),
                          readouts.retrieve(new_field, q, k=5))
    old_edges, old_probs = readouts.plan(old_field, q)
    new_edges, new_probs = readouts.plan(new_field, q)
    assert np.array_equal(old_edges, new_edges)
    assert np.array_equal(old_probs, new_probs)
    assert readouts.dispatch(old_field, q) == readouts.dispatch(new_field, q)
    old_ids, old_scores, old_receipt = tv.traverse(old_field, q, k=5, mu=0.0)
    new_ids, new_scores, new_receipt = tv.traverse(new_field, q, k=5, mu=0.0)
    assert np.array_equal(old_ids, new_ids)
    assert np.array_equal(old_scores, new_scores)
    assert old_receipt.abstained == new_receipt.abstained
    assert old_receipt.abstain_reason == new_receipt.abstain_reason


def test_invalid_embedding_fails_closed_instead_of_reproducing_legacy_bug():
    def bad_embed(texts):
        return np.full((len(texts), 3), np.nan)

    with pytest.raises(la.LegacyCompileError) as caught:
        la.compile_legacy_rows(_rows(), embed_fn=bad_embed)
    assert {issue.code for issue in caught.value.rejection.issues} == {la.RejectCode.NONFINITE_VECTOR}


def test_ragged_embedding_is_typed_rejection():
    def ragged_embed(texts):
        return [[1.0, 2.0], [3.0]] if len(texts) > 1 else [[1.0, 2.0]]

    with pytest.raises(la.LegacyCompileError) as caught:
        la.compile_legacy_rows(_rows(), embed_fn=ragged_embed)
    assert {issue.code for issue in caught.value.rejection.issues} == {
        la.RejectCode.EMBEDDING_DIMENSION_MISMATCH,
    }


def test_unknown_gold_target_is_typed_rejection():
    compiled = la.compile_legacy_rows(_rows())
    first = replace(compiled.evaluation.queries[0], gold_target_ids=("hswm:tgt:v1:missing",))
    suite = EvaluationSuiteV1((first,) + compiled.evaluation.queries[1:])
    with pytest.raises(la.LegacyCompileError) as caught:
        la.to_legacy_built_world(compiled.artifact, suite, layout=compiled.layout)
    assert {issue.code for issue in caught.value.rejection.issues} == {la.RejectCode.DANGLING_REFERENCE}


def test_empty_artifact_is_typed_rejection():
    artifact = compile_world(SourceBundleV1(()), ObservationBundleV1(), CompilePolicyV1())
    assert not isinstance(artifact, la.CompileRejectionV1)
    with pytest.raises(la.LegacyCompileError) as caught:
        la.to_legacy_built_world(artifact, EvaluationSuiteV1(()))
    assert {issue.code for issue in caught.value.rejection.issues} == {
        la.RejectCode.SCHEMA_INCOMPATIBLE,
    }
