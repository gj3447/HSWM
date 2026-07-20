"""Deterministic S3 comparison: EPWC raw reads versus EPWC + CRE.

This experiment measures tuple-integrity and fail-closed behavior only.  It
does not claim that the current hypergraph or traversal kernel is smarter.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from unittest import mock

import numpy as np

import certified_readout as cr
import field_snapshot as fs
import legacy_adapter as la
import readouts
import traversal
import weight_field
import world_builder as wb
from world_ir import canonical_json


EXPERIMENT_VERSION = "hswm-s3-certified-cut-comparison/v2"
VALID_GOLDEN_SHA256 = "477d77ac75a1031e6fb68c92223b34b9fce958635c86818e69082d9f16f54cad"


def fixture_rows() -> list[dict[str, Any]]:
    paragraphs = {
        "castle": {"idx": 0, "title": "Stormhold Castle",
                   "paragraph_text": "Stormhold Castle was built by Harlan Vex above the northern cliffs. "
                                     "Harlan Vex sealed the gates in winter.",
                   "is_supporting": True},
        "harlan": {"idx": 1, "title": "Harlan Vex",
                   "paragraph_text": "Harlan Vex was a wizard who feared the Ember Dragon. "
                                     "The Ember Dragon haunted his dreams.",
                   "is_supporting": True},
        "dragon": {"idx": 2, "title": "Ember Dragon",
                   "paragraph_text": "The Ember Dragon slept beneath the mountain for a century.",
                   "is_supporting": False},
        "noise1": {"idx": 3, "title": "Willow Market",
                   "paragraph_text": "Willow Market sold river fish and lamp oil every morning.",
                   "is_supporting": False},
        "noise2": {"idx": 4, "title": "Glass Harbor",
                   "paragraph_text": "Glass Harbor traded with Willow Market across the bay.",
                   "is_supporting": False},
    }
    rows: list[dict[str, Any]] = [
        {"id": "2hop__castle_harlan", "hop": "2hop",
         "question": "Who built the castle feared by whom?", "answer": "Ember Dragon",
         "paragraphs": [paragraphs["castle"], paragraphs["harlan"],
                        paragraphs["noise1"], paragraphs["noise2"]]},
        {"id": "3hop1__x_y_z", "question": "Where did the dragon sleep?",
         "answer": "mountain",
         "paragraphs": [dict(paragraphs["dragon"], is_supporting=True),
                        paragraphs["noise1"], dict(paragraphs["harlan"], is_supporting=False)]},
    ]
    for index in range(6):
        rows.append({
            "id": f"2hop__fill{index}", "hop": "2hop",
            "question": f"filler {index}?", "answer": "x",
            "paragraphs": [dict(paragraphs["noise1"], is_supporting=True),
                           paragraphs["noise2"]],
        })
    return rows


def _freeze(
    compiled: la.LegacyCompileResult,
    *,
    decayed_target_id: str,
    lam: float = 0.15,
) -> fs.FieldSnapshotBundleV1:
    world = deepcopy(compiled.world)
    dense = compiled.stable_ids.target_ids_by_dense.index(decayed_target_id)
    world.hg.base_salience = world.hg.base_salience.copy()
    world.hg.base_salience[dense] = 0.5
    bundle = fs.freeze_legacy_field_snapshot(
        compiled.artifact,
        world,
        compiled.stable_ids,
        revision=1,
        ledger_id="s3-fixture-ledger",
        events_root_sha256="1" * 64,
        lam=lam,
    )
    if not isinstance(bundle, fs.FieldSnapshotBundleV1):
        raise AssertionError(bundle)
    return bundle


def _policies() -> tuple[tuple[str, cr.ReadoutPolicyV1], ...]:
    return (
        ("retrieve_k1", cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=1)),
        ("retrieve_k5", cr.make_readout_policy(cr.ReadoutKind.RETRIEVE, top_k=5)),
        ("selection_t1", cr.make_readout_policy(
            cr.ReadoutKind.SELECTION, top_k=5, selection_temperature=1.0,
        )),
        ("dispatch", cr.make_readout_policy(cr.ReadoutKind.DISPATCH, top_k=1)),
        ("traversal_floor", cr.make_readout_policy(
            cr.ReadoutKind.TRAVERSAL,
            top_k=5,
            traversal_policy=cr.TraversalPolicyV1(mu=0.0, gamma=0.5, hops=2, kappa=1),
        )),
    )


def _query(
    compiled: la.LegacyCompileResult,
    bundle: fs.FieldSnapshotBundleV1,
    index: int,
    *,
    model_revision: str | None = None,
    config_sha256: str | None = None,
) -> cr.QueryEmbeddingV1:
    query = compiled.world.queries[index]
    vector = wb.hash_embed([query.question], wb.DEFAULT_DIM)[0]
    return cr.make_query_embedding(
        query.qid,
        query.question,
        vector,
        bundle.snapshot.embedding_contract,
        model_revision=model_revision,
        config_sha256=config_sha256,
    )


def _torn_bundle(bundle: fs.FieldSnapshotBundleV1) -> fs.FieldSnapshotBundleV1:
    cut = fs.make_revision_cut(
        bundle.snapshot.target_ids_by_dense,
        np.ones(len(bundle.snapshot.target_ids_by_dense)),
        ledger_id="s3-fixture-ledger",
        revision=1,
        events_root_sha256="1" * 64,
    )
    return replace(bundle, snapshot=replace(bundle.snapshot, revision_cut=cut))


def _payload_signature(
    payload: cr.ReadoutPayloadV1,
    action: cr.ReadoutAction,
) -> dict[str, Any]:
    return {
        "kind": payload.kind,
        "action": action,
        "target_ordinals": payload.target_ordinals,
        "target_ids": payload.target_ids,
        "scores_sha256": fs.freeze_array(payload.scores, "<f8").sha256,
        "probabilities_sha256": fs.freeze_array(payload.probabilities, "<f8").sha256,
        "dispatch_target_ordinal": payload.dispatch_target_ordinal,
        "dispatch_target_id": payload.dispatch_target_id,
        "traversal_receipt": payload.traversal_receipt,
    }


def _legacy_oracle_signature(
    bundle: fs.FieldSnapshotBundleV1,
    request: cr.ReadoutRequestV1,
) -> dict[str, Any]:
    """Direct legacy oracle, independent of certified_readout._compute_read."""
    policy = request.policy
    query = np.asarray(request.query.vector, dtype=np.float64)
    field = fs.hydrate_weight_field(bundle)
    target_ids = bundle.snapshot.target_ids_by_dense
    probabilities: tuple[float, ...] = ()
    dispatch_ordinal = None
    dispatch_id = None
    receipt = None
    action = cr.ReadoutAction.APPLY
    if policy.kind == cr.ReadoutKind.RETRIEVE:
        ordinals = readouts.retrieve(field, query, k=policy.top_k)
        scores = field.value(query, ordinals)
    elif policy.kind == cr.ReadoutKind.SELECTION:
        edges, probs = readouts.selection_distribution(
            field, query, temp=policy.selection_temperature,
        )
        order = np.argsort(-probs, kind="stable")[:policy.top_k]
        ordinals = edges[order]
        scores = field.value(query, ordinals)
        probabilities = tuple(float(value) for value in probs[order])
    elif policy.kind == cr.ReadoutKind.DISPATCH:
        dispatch_ordinal = readouts.dispatch(field, query)
        ordinals = np.asarray([dispatch_ordinal], dtype=np.int64)
        scores = field.value(query, ordinals)
        edges, probs = readouts.selection_distribution(
            field, query, temp=policy.selection_temperature,
        )
        probabilities = (float(probs[int(np.flatnonzero(edges == dispatch_ordinal)[0])]),)
        dispatch_id = target_ids[dispatch_ordinal]
    else:
        traversal_policy = policy.traversal
        assert traversal_policy is not None
        all_ordinals, all_scores, raw_receipt = readouts.traverse(
            field,
            query,
            k=field.hg.M,
            mu=traversal_policy.mu,
            gamma=traversal_policy.gamma,
            K=traversal_policy.hops,
            kappa=traversal_policy.kappa,
        )
        ordinals = all_ordinals[:policy.top_k]
        scores = all_scores[:policy.top_k]
        receipt = cr._traversal_receipt(raw_receipt)
        if raw_receipt.abstained:
            action = cr.ReadoutAction.FALLBACK_CURRENT_STATIC
    provisional = cr.ReadoutPayloadV1(
        kind=policy.kind,
        target_ordinals=tuple(int(value) for value in ordinals),
        target_ids=tuple(target_ids[int(value)] for value in ordinals),
        scores=tuple(float(value) for value in scores),
        probabilities=probabilities,
        dispatch_target_ordinal=dispatch_ordinal,
        dispatch_target_id=dispatch_id,
        traversal_receipt=receipt,
        score_components=fs.score_components(bundle, query),
        payload_sha256="oracle-not-used",
    )
    return _payload_signature(provisional, action)


def _rehash_snapshot(snapshot: fs.FieldSnapshotV1) -> fs.FieldSnapshotV1:
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


def _unchecked_certificate(
    bundle: fs.FieldSnapshotBundleV1,
    policy: cr.ReadoutPolicyV1,
    *,
    status: Any = cr.CertificateStatus.CERTIFIED,
) -> cr.ReadoutCertificateV1:
    provisional = cr.ReadoutCertificateV1(
        certificate_id="",
        schema_version=cr.CERTIFICATE_SCHEMA_VERSION,
        status=status,
        issuer_id="self-consistent-mutant",
        scope=cr._scope(bundle, policy),
        evidence_sha256=fs.EMPTY_SHA256,
        valid_from_generation=0,
        valid_through_generation=0,
    )
    return replace(provisional, certificate_id=cr._certificate_id(provisional))


def _smart_rows(seed: int = 0, n_chains: int = 8, noise: int = 16) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for index in range(n_chains):
        a, b, c = f"Alpha Keep {index}", f"Bram Vale {index}", f"Cinder Peak {index}"
        pa = {"idx": 0, "title": a,
              "paragraph_text": f"{a} stands north. Lord of {a} rode to {b} each spring. {b} kept the oath.",
              "is_supporting": True}
        pb = {"idx": 1, "title": b,
              "paragraph_text": f"{b} lies east of the river. Scouts of {b} watched {c} burn.",
              "is_supporting": True}
        pc = {"idx": 2, "title": c,
              "paragraph_text": f"{c} is a mountain of ash and old fire.",
              "is_supporting": False}
        noise_p = {"idx": 3, "title": f"Dull Fen {rng.integers(noise)}",
                   "paragraph_text": "Reeds and mud and quiet water lie here for many miles.",
                   "is_supporting": False}
        rows.append({"id": f"2hop__chain{index}", "hop": "2hop",
                     "question": f"Where did the lord of {a} ride each spring?",
                     "answer": b, "paragraphs": [pa, pb, pc, noise_p]})
    return rows


def run_comparison() -> dict[str, Any]:
    rows = fixture_rows()
    compiled = la.compile_legacy_rows(rows)
    decayed_target_id = compiled.stable_ids.target_ids_by_dense[0]
    base = _freeze(compiled, decayed_target_id=decayed_target_id)
    reverse_compiled = la.compile_legacy_rows(list(reversed(deepcopy(rows))))
    reverse = _freeze(reverse_compiled, decayed_target_id=decayed_target_id)
    foreign_rows = deepcopy(rows)
    foreign_rows[0]["paragraphs"][0]["paragraph_text"] += " Foreign revision."
    foreign_compiled = la.compile_legacy_rows(foreign_rows)
    foreign = _freeze(
        foreign_compiled,
        decayed_target_id=foreign_compiled.stable_ids.target_ids_by_dense[0],
    )
    changed_policy = _freeze(compiled, decayed_target_id=decayed_target_id, lam=0.2)
    torn = _torn_bundle(base)
    cut0 = fs.make_revision_cut(
        base.snapshot.target_ids_by_dense,
        np.ones(len(base.snapshot.target_ids_by_dense)),
        ledger_id="s3-fixture-ledger", revision=0, events_root_sha256=fs.EMPTY_SHA256,
    )
    policies = _policies()
    if len(compiled.world.queries) != 8 or len(policies) != 5:
        raise AssertionError("comparison preregistration requires 8 queries and 5 policies")

    certificates = {
        name: cr.issue_certificate(base, policy)
        for name, policy in policies
    }
    valid_attempts = 0
    valid_admitted = 0
    cre_oracle_exact = 0
    probe_oracle_exact = 0
    golden_records = []
    for query_index in range(8):
        query = _query(compiled, base, query_index)
        for name, policy in policies:
            certificate = certificates[name]
            request = cr.make_request(base, certificate, policy, query)
            context = cr.AdmissionContextV1((certificate.certificate_id,), 0)
            oracle = _legacy_oracle_signature(base, request)
            probe = cr.research_probe(base, request)
            certified = cr.read_certified(base, certificate, request, context)
            valid_attempts += 1
            valid_admitted += int(certified.payload is not None)
            probe_oracle_exact += int(
                _payload_signature(probe.payload, probe.observed_action) == oracle
            )
            if certified.payload is not None:
                cre_oracle_exact += int(
                    _payload_signature(certified.payload, certified.receipt.action) == oracle
                )
            golden_records.append((query_index, name, oracle))
    valid_golden_sha256 = sha256(
        canonical_json(tuple(golden_records)).encode("utf-8")
    ).hexdigest()
    golden_matches = valid_golden_sha256 == VALID_GOLDEN_SHA256

    expected = {
        "F1_foreign_world": cr.RefusalCode.WORLD_FIELD_MISMATCH,
        "F2_reversed_dense_layout": cr.RefusalCode.FIELD_SNAPSHOT_MISMATCH,
        "F3_model_revision": cr.RefusalCode.MODEL_REVISION_MISMATCH,
        "F4_model_config": cr.RefusalCode.MODEL_CONFIG_MISMATCH,
        "F5_field_policy": cr.RefusalCode.FIELD_POLICY_MISMATCH,
        "F6_readout_policy": cr.RefusalCode.READOUT_POLICY_MISMATCH,
        "F7_revision_cut": cr.RefusalCode.REVISION_CUT_MISMATCH,
        "F8_torn_revision_fold": cr.RefusalCode.REVISION_FOLD_MISMATCH,
        "F9_untrusted_certificate": cr.RefusalCode.INVALID_CERTIFICATE,
        "F10_expired_certificate": cr.RefusalCode.CERTIFICATE_EXPIRED,
    }
    fault_counts = {
        name: {"attempts": 0, "probe_payloads": 0, "cre_payloads": 0,
               "typed_refusals": 0, "pre_kernel_refusals": 0,
               "observed_zero_kernel_calls": 0,
               "expected_refusal": code.value,
               "observed_refusals": {}}
        for name, code in expected.items()
    }

    for query_index in range(8):
        base_query = _query(compiled, base, query_index)
        revised_query = _query(compiled, base, query_index, model_revision="different-revision")
        config_query = _query(compiled, base, query_index, config_sha256="2" * 64)
        for policy_index, (name, policy) in enumerate(policies):
            certificate = certificates[name]
            normal_request = cr.make_request(base, certificate, policy, base_query)
            normal_context = cr.AdmissionContextV1((certificate.certificate_id,), 0)

            next_name, _ = policies[(policy_index + 1) % len(policies)]
            rotated_certificate = certificates[next_name]
            rotated_request = cr.make_request(base, rotated_certificate, policy, base_query)
            rotated_context = cr.AdmissionContextV1((rotated_certificate.certificate_id,), 0)
            cut_request = cr.make_request(
                base, certificate, policy, base_query,
                expected_revision_cut_id=cut0.cut_id,
            )
            revision_request = cr.make_request(base, certificate, policy, revised_query)
            config_request = cr.make_request(base, certificate, policy, config_query)
            expired_certificate = cr.issue_certificate(
                base, policy, valid_from_generation=5, valid_through_generation=10,
            )
            expired_request = cr.make_request(base, expired_certificate, policy, base_query)

            cases = (
                ("F1_foreign_world", foreign, certificate, normal_request, normal_context),
                ("F2_reversed_dense_layout", reverse, certificate, normal_request, normal_context),
                ("F3_model_revision", base, certificate, revision_request, normal_context),
                ("F4_model_config", base, certificate, config_request, normal_context),
                ("F5_field_policy", changed_policy, certificate, normal_request, normal_context),
                ("F6_readout_policy", base, rotated_certificate, rotated_request, rotated_context),
                ("F7_revision_cut", base, certificate, cut_request, normal_context),
                ("F8_torn_revision_fold", torn, certificate, normal_request, normal_context),
                ("F9_untrusted_certificate", base, certificate, normal_request,
                 cr.AdmissionContextV1((), 0)),
                ("F10_expired_certificate", base, expired_certificate, expired_request,
                 cr.AdmissionContextV1((expired_certificate.certificate_id,), 11)),
            )
            for fault_name, bundle, used_certificate, request, context in cases:
                probe = cr.research_probe(bundle, request)
                cr._KERNEL_INVOCATION_COUNT = 0
                certified = cr.read_certified(
                    bundle, used_certificate, request, context,
                )
                observed_kernel_calls = cr._KERNEL_INVOCATION_COUNT
                counts = fault_counts[fault_name]
                counts["attempts"] += 1
                counts["probe_payloads"] += int(probe.payload is not None)
                counts["cre_payloads"] += int(certified.payload is not None)
                counts["observed_zero_kernel_calls"] += int(observed_kernel_calls == 0)
                observed = certified.receipt.refusal_code
                if observed is not None:
                    counts["typed_refusals"] += 1
                    counts["observed_refusals"][observed.value] = (
                        counts["observed_refusals"].get(observed.value, 0) + 1
                    )
                if certified.payload is None and not certified.receipt.kernel_invoked:
                    counts["pre_kernel_refusals"] += 1

    fault_attempts = sum(value["attempts"] for value in fault_counts.values())
    probe_payloads = sum(value["probe_payloads"] for value in fault_counts.values())
    cre_payloads = sum(value["cre_payloads"] for value in fault_counts.values())
    typed_refusals = sum(value["typed_refusals"] for value in fault_counts.values())
    pre_kernel_refusals = sum(
        value["pre_kernel_refusals"] for value in fault_counts.values()
    )
    expected_codes_exact = all(
        value["observed_refusals"] == {value["expected_refusal"]: value["attempts"]}
        for value in fault_counts.values()
    )

    # Unique adversarial attacks are counted once each, rather than inflated by
    # repeating them across query/policy cells.
    retrieve_policy = policies[1][1]
    retrieve_certificate = certificates["retrieve_k5"]
    representative_query = _query(compiled, base, 0)
    representative_request = cr.make_request(
        base, retrieve_certificate, retrieve_policy, representative_query,
    )
    representative_context = cr.AdmissionContextV1(
        (retrieve_certificate.certificate_id,), 0,
    )
    mutation_traversal_policy = cr.make_readout_policy(
        cr.ReadoutKind.TRAVERSAL,
        top_k=5,
        traversal_policy=cr.TraversalPolicyV1(mu=0.4),
    )
    mutation_traversal_certificate = cr.issue_certificate(
        base, mutation_traversal_policy,
    )
    mutation_traversal_request = cr.make_request(
        base, mutation_traversal_certificate, mutation_traversal_policy,
        representative_query,
    )

    malformed_matrix = fs.freeze_array(np.asarray([1.0, 2.0]), "<f8")
    malformed_kernel = replace(
        base.snapshot.kernel,
        semantic_mode="bilinear-v1",
        bilinear_matrix=malformed_matrix,
    )
    malformed_snapshot = _rehash_snapshot(
        replace(base.snapshot, kernel=malformed_kernel)
    )
    malformed_bundle = replace(base, snapshot=malformed_snapshot)
    malformed_certificate = _unchecked_certificate(malformed_bundle, retrieve_policy)
    malformed_request = cr.make_request(
        malformed_bundle, malformed_certificate, retrieve_policy, representative_query,
    )

    invented_certificate = replace(
        retrieve_certificate,
        certificate_id="",
        status="invented-deployable-status",
    )
    invented_certificate = replace(
        invented_certificate,
        certificate_id=cr._certificate_id(invented_certificate),
    )
    invented_request = cr.make_request(
        base, invented_certificate, retrieve_policy, representative_query,
    )

    malformed_query = replace(
        representative_query,
        vector=("not-a-number",),
        dimension=1,
    )
    malformed_query_request = cr.make_request(
        base, retrieve_certificate, retrieve_policy, malformed_query,
    )

    unsupported_field_policy = replace(
        base.snapshot.field_policy,
        tie_policy="unstable-v0",
        score_dtype="float32",
    )
    unsupported_snapshot = _rehash_snapshot(
        replace(base.snapshot, field_policy=unsupported_field_policy)
    )
    unsupported_bundle = replace(base, snapshot=unsupported_snapshot)
    unsupported_certificate = _unchecked_certificate(unsupported_bundle, retrieve_policy)
    unsupported_request = cr.make_request(
        unsupported_bundle, unsupported_certificate, retrieve_policy, representative_query,
    )

    negative_cut = replace(base.snapshot.revision_cut, revision=-1, cut_id="")
    negative_cut = replace(negative_cut, cut_id=fs._revision_cut_id(negative_cut))
    negative_provisional = replace(
        base.snapshot, snapshot_id="", revision_cut=negative_cut,
    )
    negative_snapshot = replace(
        negative_provisional,
        snapshot_id=fs._snapshot_id(negative_provisional),
    )
    negative_bundle = replace(base, snapshot=negative_snapshot)
    negative_certificate = _unchecked_certificate(negative_bundle, retrieve_policy)
    negative_request = cr.make_request(
        negative_bundle, negative_certificate, retrieve_policy, representative_query,
    )

    adversarial_cases = (
        ("A1_malformed_bilinear", malformed_bundle, malformed_certificate,
         malformed_request,
         cr.AdmissionContextV1((malformed_certificate.certificate_id,), 0),
         cr.RefusalCode.KERNEL_MISMATCH, None),
        ("A2_unknown_certificate_status", base, invented_certificate, invented_request,
         cr.AdmissionContextV1((invented_certificate.certificate_id,), 0),
         cr.RefusalCode.INVALID_CERTIFICATE, None),
        ("A3_nan_generation", base, retrieve_certificate, representative_request,
         cr.AdmissionContextV1((retrieve_certificate.certificate_id,), float("nan")),
         cr.RefusalCode.INVALID_REQUEST, None),
        ("A4_malformed_query", base, retrieve_certificate, malformed_query_request,
         representative_context, cr.RefusalCode.INVALID_REQUEST, None),
        ("A5_unsupported_field_policy", unsupported_bundle, unsupported_certificate,
         unsupported_request,
         cr.AdmissionContextV1((unsupported_certificate.certificate_id,), 0),
         cr.RefusalCode.SNAPSHOT_BROKEN, None),
        ("A6_negative_revision", negative_bundle, negative_certificate, negative_request,
         cr.AdmissionContextV1((negative_certificate.certificate_id,), 0),
         cr.RefusalCode.REVISION_CUT_MISMATCH, None),
        ("A7_static_kernel_mutation", base, retrieve_certificate, representative_request,
         representative_context, cr.RefusalCode.KERNEL_MISMATCH, "static"),
        ("A8_traversal_kernel_mutation", base, mutation_traversal_certificate,
         mutation_traversal_request,
         cr.AdmissionContextV1((mutation_traversal_certificate.certificate_id,), 0),
         cr.RefusalCode.KERNEL_MISMATCH, "traversal"),
        ("A9_internal_compute_mutation", base, retrieve_certificate,
         representative_request, representative_context,
         cr.RefusalCode.KERNEL_MISMATCH, "internal"),
    )
    attacks: dict[str, Any] = {}
    original_attention = weight_field.attention_alpha
    original_traverse = traversal.traverse
    original_compute = cr._compute_read
    for name, bundle, certificate, request, context, expected_code, mutation in adversarial_cases:
        if mutation == "static":
            mutation_context = mock.patch.object(
                weight_field,
                "attention_alpha",
                lambda pooled_edge_emb, query_emb, M=None: (
                    original_attention(pooled_edge_emb, query_emb, M=M) + 0.123
                ),
            )
        elif mutation == "traversal":
            mutation_context = mock.patch.object(
                traversal,
                "traverse",
                lambda *args, **kwargs: original_traverse(*args, **kwargs),
            )
        elif mutation == "internal":
            def mutated_compute(*args, **kwargs):
                payload, action = original_compute(*args, **kwargs)
                return replace(
                    payload,
                    scores=tuple(value + 123.0 for value in payload.scores),
                ), action

            mutation_context = mock.patch.object(
                cr, "_compute_read", mutated_compute,
            )
        else:
            mutation_context = mock.patch.object(
                weight_field, "attention_alpha", weight_field.attention_alpha,
            )
        with mutation_context:
            cr._KERNEL_INVOCATION_COUNT = 0
            result = cr.read_certified(bundle, certificate, request, context)
            observed_kernel_calls = cr._KERNEL_INVOCATION_COUNT
        attacks[name] = {
            "expected_refusal": expected_code.value,
            "observed_refusal": (
                None if result.receipt.refusal_code is None
                else result.receipt.refusal_code.value
            ),
            "payload": result.payload is not None,
            "kernel_calls": observed_kernel_calls,
        }

    traversal_policy = cr.make_readout_policy(
        cr.ReadoutKind.TRAVERSAL,
        top_k=5,
        traversal_policy=cr.TraversalPolicyV1(mu=0.4),
    )
    trip_certificate = cr.issue_certificate(base, traversal_policy)
    trip_request = cr.make_request(
        base, trip_certificate, traversal_policy, representative_query,
    )
    trip_result = cr.read_certified(
        base, trip_certificate, trip_request,
        cr.AdmissionContextV1((trip_certificate.certificate_id,), 0),
    )
    off_certificate = cr.issue_certificate(
        base, traversal_policy, status=cr.CertificateStatus.OFF,
    )
    off_request = cr.make_request(
        base, off_certificate, traversal_policy, representative_query,
    )
    off_result = cr.read_certified(
        base, off_certificate, off_request,
        cr.AdmissionContextV1((off_certificate.certificate_id,), 0),
    )

    smart_compiled = la.compile_legacy_rows(_smart_rows())
    smart_bundle = fs.freeze_legacy_field_snapshot(
        smart_compiled.artifact, smart_compiled.world, smart_compiled.stable_ids,
    )
    if not isinstance(smart_bundle, fs.FieldSnapshotBundleV1):
        raise AssertionError(smart_bundle)
    apply_policy = cr.make_readout_policy(
        cr.ReadoutKind.TRAVERSAL,
        top_k=smart_compiled.world.hg.M,
        traversal_policy=cr.TraversalPolicyV1(mu=0.8),
    )
    apply_query = _query(smart_compiled, smart_bundle, 0)
    apply_certificate = cr.issue_certificate(smart_bundle, apply_policy)
    apply_request = cr.make_request(
        smart_bundle, apply_certificate, apply_policy, apply_query,
    )
    apply_result = cr.read_certified(
        smart_bundle, apply_certificate, apply_request,
        cr.AdmissionContextV1((apply_certificate.certificate_id,), 0),
    )
    assert apply_result.payload is not None
    apply_components = np.asarray(apply_result.payload.score_components.final_scores)
    apply_selected = apply_components[np.asarray(apply_result.payload.target_ordinals)]
    smart_controls = {
        "mu_positive_apply": {
            "action": apply_result.receipt.action.value,
            "payload_component_bit_exact": bool(np.array_equal(
                np.asarray(apply_result.payload.scores), apply_selected,
            )),
            "nonzero_traversal_residuals": int(np.count_nonzero(
                apply_result.payload.score_components.traversal_residual,
            )),
        },
        "query_trip_fallback": {
            "action": trip_result.receipt.action.value,
            "reason": trip_result.payload.traversal_receipt.abstain_reason,
        },
        "certificate_off_fallback": {
            "action": off_result.receipt.action.value,
            "executed_mu": off_result.payload.traversal_receipt.mu,
        },
    }

    adversarial_passed = all(
        value["observed_refusal"] == value["expected_refusal"]
        and value["payload"] is False
        and value["kernel_calls"] == 0
        for value in attacks.values()
    )
    smart_controls_passed = (
        smart_controls["mu_positive_apply"]["action"] == cr.ReadoutAction.APPLY.value
        and smart_controls["mu_positive_apply"]["payload_component_bit_exact"]
        and smart_controls["mu_positive_apply"]["nonzero_traversal_residuals"] > 0
        and smart_controls["query_trip_fallback"]["action"]
            == cr.ReadoutAction.FALLBACK_CURRENT_STATIC.value
        and smart_controls["certificate_off_fallback"]["action"]
            == cr.ReadoutAction.FALLBACK_CURRENT_STATIC.value
        and smart_controls["certificate_off_fallback"]["executed_mu"] == 0.0
    )
    passed = (
        valid_attempts == 40
        and valid_admitted == 40
        and cre_oracle_exact == 40
        and probe_oracle_exact == 40
        and golden_matches
        and fault_attempts == 400
        and probe_payloads == 400
        and cre_payloads == 0
        and typed_refusals == 400
        and pre_kernel_refusals == 400
        and sum(value["observed_zero_kernel_calls"] for value in fault_counts.values()) == 400
        and expected_codes_exact
        and adversarial_passed
        and smart_controls_passed
    )
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "claim_scope": "local scope-check conformance and pre-kernel refusal",
        "non_claim": "does not measure smart-hypergraph retrieval or reasoning efficacy",
        "fixture": {"queries": 8, "targets": 5, "policies": 5,
                    "scope_fault_classes": 10, "unique_adversarial_attacks": len(attacks)},
        "valid_controls": {
            "attempts": valid_attempts,
            "probe_oracle_bit_exact": probe_oracle_exact,
            "cre_admitted": valid_admitted,
            "cre_oracle_bit_exact": cre_oracle_exact,
            "false_refusals": valid_attempts - valid_admitted,
            "golden_sha256": valid_golden_sha256,
            "golden_matches": golden_matches,
        },
        "scope_fault_conformance": {
            "attempts": fault_attempts,
            "unbound_not_deployable_probe_payloads": probe_payloads,
            "cre_payloads": cre_payloads,
            "cre_typed_refusals": typed_refusals,
            "cre_pre_kernel_refusals": pre_kernel_refusals,
            "observed_zero_kernel_calls": sum(
                value["observed_zero_kernel_calls"] for value in fault_counts.values()
            ),
            "expected_codes_exact": expected_codes_exact,
        },
        "scope_faults": fault_counts,
        "unique_adversarial_attacks": attacks,
        "smart_traversal_safety_controls": smart_controls,
        "verdict": "PASS" if passed else "FAIL",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = run_comparison()
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.out is not None:
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if result["verdict"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
