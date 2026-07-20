"""S3 teeth for immutable, content-addressed field snapshots."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

import field_snapshot as fs
import legacy_adapter as la
import readouts
import traversal
import world_builder as wb
from tests.test_world_builder import _rows
from weight_field import WeightField


def _bundle(rows=None, **kwargs) -> tuple[la.LegacyCompileResult, fs.FieldSnapshotBundleV1]:
    compiled = la.compile_legacy_rows(_rows() if rows is None else rows)
    frozen = fs.freeze_legacy_field_snapshot(
        compiled.artifact, compiled.world, compiled.stable_ids, **kwargs,
    )
    assert isinstance(frozen, fs.FieldSnapshotBundleV1)
    return compiled, frozen


def test_snapshot_hydrates_bit_exact_legacy_field_and_components():
    compiled, bundle = _bundle()
    assert fs.verify_field_snapshot(bundle) == ()
    legacy = WeightField(compiled.world.hg, target_emb=compiled.world.hg.unit_emb)
    hydrated = fs.hydrate_weight_field(bundle)
    for query in compiled.world.queries:
        q = wb.hash_embed([query.question], wb.DEFAULT_DIM)[0]
        expected = legacy.value(q)
        actual = hydrated.value(q)
        components = fs.score_components(bundle, q)
        assert np.array_equal(actual, expected)
        assert np.array_equal(np.asarray(components.final_scores), expected)
        assert np.array_equal(readouts.retrieve(hydrated, q, k=5),
                              readouts.retrieve(legacy, q, k=5))
        expected_edges, expected_probs = readouts.selection_distribution(legacy, q)
        actual_edges, actual_probs = readouts.selection_distribution(hydrated, q)
        assert np.array_equal(actual_edges, expected_edges)
        assert np.array_equal(actual_probs, expected_probs)
        assert readouts.dispatch(hydrated, q) == readouts.dispatch(legacy, q)
        expected_ids, expected_scores, expected_receipt = traversal.traverse(
            legacy, q, k=5, mu=0.0,
        )
        actual_ids, actual_scores, actual_receipt = traversal.traverse(
            hydrated, q, k=5, mu=0.0,
        )
        assert np.array_equal(actual_ids, expected_ids)
        assert np.array_equal(actual_scores, expected_scores)
        assert actual_receipt.abstain_reason == expected_receipt.abstain_reason


def test_snapshot_arrays_are_read_only_and_hydration_does_not_mutate_bundle():
    _, bundle = _bundle()
    before = bundle.snapshot.snapshot_id
    target = fs.thaw_array(bundle.material.target_embeddings)
    salience = fs.thaw_array(bundle.material.base_salience)
    assert not target.flags.writeable
    assert not salience.flags.writeable
    with pytest.raises(ValueError):
        target[0, 0] = 999.0
    with pytest.raises(ValueError):
        salience[0] = 0.5
    field = fs.hydrate_weight_field(bundle)
    field.hg.base_salience = field.hg.base_salience.copy()
    field.hg.base_salience[0] = 0.5
    assert bundle.snapshot.snapshot_id == before
    assert fs.verify_field_snapshot(bundle) == ()


def test_dense_layout_is_bound_even_when_world_build_id_is_same():
    forward_compiled, forward = _bundle()
    reverse_compiled, reverse = _bundle(list(reversed(deepcopy(_rows()))))
    assert forward_compiled.artifact.build_id == reverse_compiled.artifact.build_id
    assert forward.snapshot.target_ids_by_dense != reverse.snapshot.target_ids_by_dense
    assert forward.snapshot.snapshot_id != reverse.snapshot.snapshot_id
    mismatch = fs.freeze_legacy_field_snapshot(
        forward_compiled.artifact, reverse_compiled.world, forward_compiled.stable_ids,
    )
    assert isinstance(mismatch, fs.SnapshotRejectionV1)
    assert fs.SnapshotRejectCode.WORLD_FIELD_MISMATCH in {
        issue.code for issue in mismatch.issues
    }


def test_array_and_artifact_tampering_fail_closed():
    _, bundle = _bundle()
    bad_array = replace(bundle.material.target_embeddings, sha256="0" * 64)
    bad_material = replace(bundle.material, target_embeddings=bad_array)
    bad_bundle = replace(bundle, material=bad_material)
    codes = {issue.code for issue in fs.verify_field_snapshot(bad_bundle)}
    assert fs.SnapshotRejectCode.ARRAY_DIGEST_MISMATCH in codes
    assert fs.SnapshotRejectCode.MATERIAL_DIGEST_MISMATCH in codes
    with pytest.raises(fs.SnapshotHydrationError):
        fs.hydrate_weight_field(bad_bundle)

    bad_artifact = replace(bundle.snapshot.artifact, build_id="hswm:world:v1:tampered")
    bad_snapshot = replace(bundle.snapshot, artifact=bad_artifact)
    artifact_codes = {
        issue.code for issue in fs.verify_field_snapshot(replace(bundle, snapshot=bad_snapshot))
    }
    assert fs.SnapshotRejectCode.ARTIFACT_INVALID in artifact_codes


def test_torn_revision_cut_and_new_revision_are_distinguishable():
    compiled, cut0 = _bundle()
    changed = deepcopy(compiled.world)
    changed.hg.base_salience = changed.hg.base_salience.copy()
    changed.hg.base_salience[0] = 0.5
    cut1 = fs.freeze_legacy_field_snapshot(
        compiled.artifact, changed, compiled.stable_ids,
        revision=1, ledger_id="fixture-ledger", events_root_sha256="1" * 64,
    )
    assert isinstance(cut1, fs.FieldSnapshotBundleV1)
    assert cut1.snapshot.snapshot_id != cut0.snapshot.snapshot_id
    assert cut1.snapshot.revision_cut.cut_id != cut0.snapshot.revision_cut.cut_id

    torn_cut = fs.make_revision_cut(
        cut1.snapshot.target_ids_by_dense,
        np.ones(len(cut1.snapshot.target_ids_by_dense)),
        ledger_id="fixture-ledger", revision=1, events_root_sha256="1" * 64,
    )
    torn = replace(cut1, snapshot=replace(cut1.snapshot, revision_cut=torn_cut))
    codes = {issue.code for issue in fs.verify_field_snapshot(torn)}
    assert fs.SnapshotRejectCode.REVISION_TARGET_MISMATCH in codes
    assert fs.SnapshotRejectCode.SNAPSHOT_ID_MISMATCH in codes


def test_query_and_kernel_parameters_are_validated():
    compiled, bundle = _bundle()
    with pytest.raises(ValueError):
        fs.score_components(bundle, np.zeros(wb.DEFAULT_DIM + 1))
    with pytest.raises(ValueError):
        fs.score_components(bundle, np.full(wb.DEFAULT_DIM, np.nan))
    rejected = fs.freeze_legacy_field_snapshot(
        compiled.artifact, compiled.world, compiled.stable_ids, lam=-0.1,
    )
    assert isinstance(rejected, fs.SnapshotRejectionV1)
    assert {issue.code for issue in rejected.issues} == {
        fs.SnapshotRejectCode.KERNEL_PARAMETER_INVALID,
    }


def test_explicit_target_embedding_seam_matches_legacy_monkeypatch():
    compiled = la.compile_legacy_rows(_rows())
    query = wb.hash_embed([compiled.world.queries[0].question], wb.DEFAULT_DIM)[0]
    old = WeightField(compiled.world.hg)
    old._pooled = compiled.world.hg.unit_emb
    new = WeightField(compiled.world.hg, target_emb=compiled.world.hg.unit_emb)
    assert np.array_equal(old.value(query), new.value(query))


def _rehash_snapshot(snapshot):
    kernel_sha = fs._kernel_sha256(snapshot.kernel)
    parameter_sha = fs._parameter_sha256(snapshot.kernel)
    policy_sha = fs._policy_sha256(snapshot.field_policy, parameter_sha)
    provisional = replace(
        snapshot,
        snapshot_id="",
        kernel_sha256=kernel_sha,
        parameter_sha256=parameter_sha,
        policy_sha256=policy_sha,
    )
    return replace(provisional, snapshot_id=fs._snapshot_id(provisional))


def test_self_consistent_malformed_bilinear_matrix_is_rejected():
    _, bundle = _bundle()
    malformed = fs.freeze_array(np.asarray([1.0, 2.0]), "<f8")
    kernel = replace(
        bundle.snapshot.kernel,
        semantic_mode="bilinear-v1",
        bilinear_matrix=malformed,
    )
    snapshot = _rehash_snapshot(replace(bundle.snapshot, kernel=kernel))
    mutant = replace(bundle, snapshot=snapshot)
    issues = fs.verify_field_snapshot(mutant)
    assert fs.SnapshotRejectCode.KERNEL_PARAMETER_INVALID in {
        issue.code for issue in issues
    }
    with pytest.raises(fs.SnapshotHydrationError):
        fs.hydrate_weight_field(mutant)


def test_self_consistent_unsupported_policy_and_negative_revision_are_rejected():
    _, bundle = _bundle()
    unsupported = replace(
        bundle.snapshot.field_policy,
        tie_policy="unstable-v0",
        score_dtype="float32",
    )
    policy_snapshot = _rehash_snapshot(replace(bundle.snapshot, field_policy=unsupported))
    policy_codes = {
        issue.code for issue in fs.verify_field_snapshot(
            replace(bundle, snapshot=policy_snapshot)
        )
    }
    assert fs.SnapshotRejectCode.KERNEL_PARAMETER_INVALID in policy_codes

    cut = replace(bundle.snapshot.revision_cut, revision=-1, cut_id="")
    cut = replace(cut, cut_id=fs._revision_cut_id(cut))
    provisional = replace(bundle.snapshot, snapshot_id="", revision_cut=cut)
    negative_snapshot = replace(provisional, snapshot_id=fs._snapshot_id(provisional))
    revision_codes = {
        issue.code for issue in fs.verify_field_snapshot(
            replace(bundle, snapshot=negative_snapshot)
        )
    }
    assert fs.SnapshotRejectCode.REVISION_CUT_MISMATCH in revision_codes
