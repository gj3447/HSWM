"""S3 certified readout admission, refusal, and static-floor teeth."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

import certified_readout as cr
import field_snapshot as fs
import legacy_adapter as la
import readouts
import world_builder as wb
from tests.test_world_builder import _rows


def _bundle(*, salience: float = 1.0, lam: float = 0.15) -> tuple[la.LegacyCompileResult, fs.FieldSnapshotBundleV1]:
    compiled = la.compile_legacy_rows(_rows())
    world = deepcopy(compiled.world)
    world.hg.base_salience = world.hg.base_salience.copy()
    world.hg.base_salience[0] = salience
    frozen = fs.freeze_legacy_field_snapshot(
        compiled.artifact,
        world,
        compiled.stable_ids,
        revision=1 if salience != 1.0 else 0,
        ledger_id="fixture-ledger",
        events_root_sha256=("1" * 64 if salience != 1.0 else fs.EMPTY_SHA256),
        lam=lam,
    )
    assert isinstance(frozen, fs.FieldSnapshotBundleV1)
    return compiled, frozen


def _query(compiled, bundle, index=0, **overrides):
    world_query = compiled.world.queries[index]
    vector = wb.hash_embed([world_query.question], wb.DEFAULT_DIM)[0]
    return cr.make_query_embedding(
        world_query.qid,
        world_query.question,
        vector,
        bundle.snapshot.embedding_contract,
        **overrides,
    )


def _admit(bundle, policy, query, *, status=cr.CertificateStatus.CERTIFIED,
           start=0, through=0, current=0):
    certificate = cr.issue_certificate(
        bundle, policy, status=status,
        valid_from_generation=start, valid_through_generation=through,
    )
    request = cr.make_request(bundle, certificate, policy, query)
    context = cr.AdmissionContextV1((certificate.certificate_id,), current)
    return certificate, request, context


@pytest.mark.parametrize("policy", [
    cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=1),
    cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5),
    cr.make_readout_policy(cr.ReadoutKind.SELECTION, top_k=5),
    cr.make_readout_policy(cr.ReadoutKind.DISPATCH, top_k=1),
    cr.make_readout_policy(
        cr.ReadoutKind.TRAVERSAL,
        top_k=5,
        traversal_policy=cr.TraversalPolicyV1(mu=0.0),
    ),
])
def test_valid_certified_payload_is_bit_exact_raw(policy):
    compiled, bundle = _bundle(salience=0.5)
    query = _query(compiled, bundle)
    certificate, request, context = _admit(bundle, policy, query)
    raw = cr.research_probe(bundle, request)
    certified = cr.read_certified(bundle, certificate, request, context)
    assert certified.payload == raw.payload
    assert raw.disposition == cr.ProbeDisposition.NOT_DEPLOYABLE
    assert certified.payload is not None
    assert certified.receipt.refusal_code is None
    assert certified.receipt.kernel_invoked


@pytest.mark.parametrize(("override", "code"), [
    ({"model_revision": "different-revision"}, cr.RefusalCode.MODEL_REVISION_MISMATCH),
    ({"config_sha256": "2" * 64}, cr.RefusalCode.MODEL_CONFIG_MISMATCH),
    ({"producer": "different-producer"}, cr.RefusalCode.MODEL_PRODUCER_MISMATCH),
])
def test_query_embedding_contract_mismatch_refuses(override, code):
    compiled, bundle = _bundle()
    policy = cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5)
    query = _query(compiled, bundle, **override)
    certificate, request, context = _admit(bundle, policy, query)
    result = cr.read_certified(bundle, certificate, request, context)
    assert result.payload is None
    assert result.receipt.refusal_code == code
    assert not result.receipt.kernel_invoked


def test_refusal_occurs_before_scorer_invocation():
    compiled, bundle = _bundle()
    policy = cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5)
    query = _query(compiled, bundle, model_revision="different-revision")
    certificate, request, context = _admit(bundle, policy, query)
    cr._KERNEL_INVOCATION_COUNT = 0
    result = cr.read_certified(bundle, certificate, request, context)
    assert result.payload is None
    assert result.receipt.refusal_code == cr.RefusalCode.MODEL_REVISION_MISMATCH
    assert cr._KERNEL_INVOCATION_COUNT == 0


def test_certificate_expiry_uses_monotonic_generation():
    compiled, bundle = _bundle()
    policy = cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5)
    query = _query(compiled, bundle)
    certificate, request, context = _admit(
        bundle, policy, query, start=5, through=10, current=11,
    )
    result = cr.read_certified(bundle, certificate, request, context)
    assert result.payload is None
    assert result.receipt.refusal_code == cr.RefusalCode.CERTIFICATE_EXPIRED


def test_untrusted_or_tampered_certificate_refuses():
    compiled, bundle = _bundle()
    policy = cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5)
    query = _query(compiled, bundle)
    certificate, request, _ = _admit(bundle, policy, query)
    untrusted = cr.AdmissionContextV1((), 0)
    assert cr.read_certified(bundle, certificate, request, untrusted).receipt.refusal_code == (
        cr.RefusalCode.INVALID_CERTIFICATE
    )
    tampered = replace(certificate, evidence_sha256="f" * 64)
    trusted_old_id = cr.AdmissionContextV1((certificate.certificate_id,), 0)
    assert cr.read_certified(bundle, tampered, request, trusted_old_id).receipt.refusal_code == (
        cr.RefusalCode.INVALID_CERTIFICATE
    )


def test_readout_policy_rotation_refuses():
    compiled, bundle = _bundle()
    retrieve = cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5)
    selection = cr.make_readout_policy(cr.ReadoutKind.SELECTION, top_k=5)
    query = _query(compiled, bundle)
    certificate = cr.issue_certificate(bundle, retrieve)
    request = cr.make_request(bundle, certificate, selection, query)
    context = cr.AdmissionContextV1((certificate.certificate_id,), 0)
    result = cr.read_certified(bundle, certificate, request, context)
    assert result.payload is None
    assert result.receipt.refusal_code == cr.RefusalCode.READOUT_POLICY_MISMATCH


def test_certified_off_traversal_falls_back_to_same_snapshot_static_scores():
    compiled, bundle = _bundle(salience=0.5)
    traversal_policy = cr.make_readout_policy(
        cr.ReadoutKind.TRAVERSAL,
        top_k=5,
        traversal_policy=cr.TraversalPolicyV1(mu=0.4),
    )
    query = _query(compiled, bundle)
    certificate, request, context = _admit(
        bundle, traversal_policy, query, status=cr.CertificateStatus.OFF,
    )
    result = cr.read_certified(bundle, certificate, request, context)
    field = fs.hydrate_weight_field(bundle)
    vector = np.asarray(query.vector, dtype=np.float64)
    expected_ids = readouts.retrieve(field, vector, k=5)
    expected_scores = field.value(vector, expected_ids)
    assert result.payload is not None
    assert result.receipt.action == cr.ReadoutAction.FALLBACK_CURRENT_STATIC
    assert result.payload.target_ordinals == tuple(int(value) for value in expected_ids)
    assert np.array_equal(np.asarray(result.payload.scores), expected_scores)
    assert result.payload.traversal_receipt is not None
    assert result.payload.traversal_receipt.mu == 0.0


def test_off_never_authorizes_a_static_policy():
    compiled, bundle = _bundle()
    policy = cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5)
    query = _query(compiled, bundle)
    certificate, request, context = _admit(
        bundle, policy, query, status=cr.CertificateStatus.OFF,
    )
    result = cr.read_certified(bundle, certificate, request, context)
    assert result.payload is None
    assert result.receipt.refusal_code == cr.RefusalCode.INVALID_CERTIFICATE


def test_installed_traversal_constants_are_policy_bound():
    with pytest.raises(ValueError):
        cr.make_readout_policy(
            cr.ReadoutKind.TRAVERSAL,
            traversal_policy=cr.TraversalPolicyV1(mu=0.1, tau_seed=9.0),
        )


def test_unknown_certificate_status_and_nan_generation_fail_closed():
    compiled, bundle = _bundle()
    policy = cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5)
    query = _query(compiled, bundle)
    certificate = cr.issue_certificate(bundle, policy)
    invented = replace(certificate, status="invented-deployable-status", certificate_id="")
    invented = replace(invented, certificate_id=cr._certificate_id(invented))
    request = cr.make_request(bundle, invented, policy, query)
    context = cr.AdmissionContextV1((invented.certificate_id,), 0)
    result = cr.read_certified(bundle, invented, request, context)
    assert result.payload is None
    assert result.receipt.refusal_code == cr.RefusalCode.INVALID_CERTIFICATE

    normal_request = cr.make_request(bundle, certificate, policy, query)
    nan_context = cr.AdmissionContextV1((certificate.certificate_id,), float("nan"))
    result = cr.read_certified(bundle, certificate, normal_request, nan_context)
    assert result.payload is None
    assert result.receipt.refusal_code == cr.RefusalCode.INVALID_REQUEST
    with pytest.raises(ValueError):
        cr.issue_certificate(bundle, policy, valid_from_generation=0.0)  # type: ignore[arg-type]


def test_malformed_query_is_typed_refusal():
    compiled, bundle = _bundle()
    policy = cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5)
    certificate = cr.issue_certificate(bundle, policy)
    malformed = replace(_query(compiled, bundle), vector=("not-a-number",), dimension=1)
    request = cr.make_request(bundle, certificate, policy, malformed)
    context = cr.AdmissionContextV1((certificate.certificate_id,), 0)
    result = cr.read_certified(bundle, certificate, request, context)
    assert result.payload is None
    assert result.receipt.refusal_code == cr.RefusalCode.INVALID_REQUEST
    assert not result.receipt.kernel_invoked


def test_static_kernel_mutation_invalidates_existing_certificate(monkeypatch):
    import weight_field

    compiled, bundle = _bundle()
    policy = cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5)
    query = _query(compiled, bundle)
    certificate, request, context = _admit(bundle, policy, query)
    original = weight_field.attention_alpha
    monkeypatch.setattr(
        weight_field,
        "attention_alpha",
        lambda pooled_edge_emb, query_emb, M=None: (
            original(pooled_edge_emb, query_emb, M=M) + 0.123
        ),
    )
    result = cr.read_certified(bundle, certificate, request, context)
    assert result.payload is None
    assert result.receipt.refusal_code == cr.RefusalCode.KERNEL_MISMATCH
    assert not result.receipt.kernel_invoked


def test_internal_compute_mutation_invalidates_existing_certificate(monkeypatch):
    compiled, bundle = _bundle()
    policy = cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5)
    query = _query(compiled, bundle)
    certificate, request, context = _admit(bundle, policy, query)
    original = cr._compute_read

    def mutated(*args, **kwargs):
        payload, action = original(*args, **kwargs)
        return replace(
            payload,
            scores=tuple(value + 123.0 for value in payload.scores),
        ), action

    monkeypatch.setattr(cr, "_compute_read", mutated)
    result = cr.read_certified(bundle, certificate, request, context)
    assert result.payload is None
    assert result.receipt.refusal_code == cr.RefusalCode.KERNEL_MISMATCH
    assert not result.receipt.kernel_invoked


def test_mu_positive_apply_receipt_explains_every_payload_score():
    from tests.test_traversal_cert import _corpus_rows

    compiled = la.compile_legacy_rows(_corpus_rows(seed=0, n_chains=8, noise=16))
    bundle = fs.freeze_legacy_field_snapshot(
        compiled.artifact, compiled.world, compiled.stable_ids,
    )
    assert isinstance(bundle, fs.FieldSnapshotBundleV1)
    policy = cr.make_readout_policy(
        cr.ReadoutKind.TRAVERSAL,
        top_k=compiled.world.hg.M,
        traversal_policy=cr.TraversalPolicyV1(mu=0.8),
    )
    query = _query(compiled, bundle)
    certificate, request, context = _admit(bundle, policy, query)
    result = cr.read_certified(bundle, certificate, request, context)
    assert result.payload is not None
    assert result.receipt.action == cr.ReadoutAction.APPLY
    components = np.asarray(result.payload.score_components.final_scores)
    selected = components[np.asarray(result.payload.target_ordinals)]
    assert np.array_equal(np.asarray(result.payload.scores), selected)
    assert np.count_nonzero(result.payload.score_components.traversal_residual) > 0


def test_research_probe_is_structurally_not_deployable():
    compiled, bundle = _bundle()
    policy = cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5)
    query = _query(compiled, bundle)
    certificate = cr.issue_certificate(bundle, policy)
    request = cr.make_request(bundle, certificate, policy, query)
    probe = cr.research_probe(bundle, request)
    assert probe.disposition == cr.ProbeDisposition.NOT_DEPLOYABLE
    assert "UNSAFE RESEARCH PROBE" in probe.warning
    assert not isinstance(probe, cr.CertifiedReadoutResultV1)
