from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json

import pytest

from hswm.evaluation.inspect_outer_runner import INSPECT_AI_REQUIREMENT
from hswm.evaluation.occurrence_dual_evaluator import (
    ExternalSignatureEvidenceV1,
    IndependentJudgmentBV1,
    InspectJudgmentAV1,
    assess_dual_evaluation,
)
from hswm.experiments.swm0w_beacon import canonical_json, canonical_sha256
from hswm.infrastructure.occurrence_completion import (
    CompletionTerminal,
    ExternalAuditMaterialV1,
    OccurrenceCompletionReplayV1,
    OccurrenceCompletionError,
    TEMPORAL_HISTORY_EXPORT_SCHEMA,
    TEMPORAL_HISTORY_SOURCE_API,
    TEMPORAL_RECEIPT_CLAIM_BOUNDARY,
    TEMPORAL_TERMINAL_RECEIPT_SCHEMA,
    TEMPORAL_WORKFLOW_TYPE,
    complete_occurrence,
    publication_eligible,
    verify_external_audit_material,
)
import hswm.infrastructure.occurrence_completion as completion
from hswm.infrastructure.occurrence_integrity import (
    CLAIM_CEILING as INTEGRITY_CLAIM_CEILING,
    AssessmentV1,
    OccurrenceIntegrityError,
    Terminal,
    assess_occurrence,
)
from hswm.infrastructure.occurrence_publication import (
    OccurrencePublicationError,
    build_openlineage_events,
    build_ro_crate_metadata,
)
from hswm.infrastructure.occurrence_workflow import (
    OccurrencePhase,
    OccurrenceWorkflowStateV1,
    PulseTiming,
    advance_occurrence,
    registered_occurrence,
)
from tests.test_occurrence_integrity import (
    assess as integrity_assess,
    values as integrity_values,
)


STARTED_AT = "2026-09-03T00:00:00Z"
CANDIDATE_AT = "2026-09-03T00:01:00Z"
FINAL_AT = "2026-09-03T00:02:00Z"


def blocked_assessment() -> AssessmentV1:
    return assess_occurrence(
        registration=None,
        dsse=None,
        rekor=None,
        rfc3161=None,
        preregistration_binding=None,
        worm=None,
        temporal=None,
        actor_seal=None,
        drand_proof=None,
        custodian_reveal=None,
        evaluator_a=None,
        evaluator_b=None,
        dual_evaluation_bridge=None,
        revision_proposer=None,
        external_audit=None,
    )


def workflow(
    phase: OccurrencePhase = OccurrencePhase.DUAL_EVALUATED,
    *,
    seal_evidence_sha256: str = "8" * 64,
    evidence_sha256s: tuple[str, ...] | None = None,
) -> OccurrenceWorkflowStateV1:
    evidence_sha256s = evidence_sha256s or tuple(
        f"{index:064x}" for index in range(1, 8)
    )
    assert len(evidence_sha256s) == 7
    state = registered_occurrence(
        occurrence_uid="g0-occurrence-1",
        registration_evidence_sha256=evidence_sha256s[0],
    )
    if phase is OccurrencePhase.REGISTERED:
        return state
    steps = (
        (OccurrencePhase.CLAIMED, PulseTiming.PRE_PULSE),
        (OccurrencePhase.SCHEDULED, PulseTiming.PRE_PULSE),
        (OccurrencePhase.PRE_PULSE_SEALED, PulseTiming.PRE_PULSE),
        (OccurrencePhase.PULSE_VERIFIED, PulseTiming.POST_PULSE),
        (OccurrencePhase.REVEALED, PulseTiming.POST_PULSE),
        (OccurrencePhase.DUAL_EVALUATED, PulseTiming.POST_PULSE),
        (OccurrencePhase.SEALED, PulseTiming.POST_PULSE),
    )
    for index, (next_phase, timing) in enumerate(steps, start=1):
        evidence = (
            seal_evidence_sha256
            if next_phase is OccurrencePhase.SEALED
            else evidence_sha256s[index]
        )
        state = advance_occurrence(
            state,
            next_phase=next_phase,
            evidence_sha256=evidence,
            timing=timing,
        )
        if next_phase is phase:
            return state
    raise AssertionError(f"unsupported fixture phase: {phase}")


def bound_workflow(
    assessment: AssessmentV1,
    phase: OccurrencePhase = OccurrencePhase.DUAL_EVALUATED,
    *,
    seal_evidence_sha256: str = "8" * 64,
) -> OccurrenceWorkflowStateV1:
    return workflow(
        phase,
        evidence_sha256s=assessment.workflow_evidence_sha256s,
        seal_evidence_sha256=seal_evidence_sha256,
    )


def void_workflow() -> OccurrenceWorkflowStateV1:
    return advance_occurrence(
        workflow(OccurrencePhase.REGISTERED),
        next_phase=OccurrencePhase.REVEALED,
        evidence_sha256="f" * 64,
        timing=PulseTiming.POST_PULSE,
    )


def integrated_inputs():  # type: ignore[no-untyped-def]
    """Create matching central and independent representations of A/B."""

    *_, central_a, central_b = integrity_values()
    unsigned_a = InspectJudgmentAV1(
        occurrence_uid=central_a.occurrence_uid,
        evaluator=central_a.evaluator,
        inspect_requirement=INSPECT_AI_REQUIREMENT,
        implementation=central_a.implementation,
        task=central_a.task,
        scorer=central_a.scorer,
        config=central_a.config,
        input=central_a.input,
        output=central_a.output,
        canonical_decision_score_sha256=central_a.score_sha256,
        blind_to_arm_identity=True,
        signature=None,
    )
    unsigned_b = IndependentJudgmentBV1(
        occurrence_uid=central_b.occurrence_uid,
        evaluator=central_b.evaluator,
        implementation=central_b.implementation,
        task=central_b.task,
        scorer=central_b.scorer,
        config=central_b.config,
        input=central_b.input,
        output=central_b.output,
        canonical_decision_score_sha256=central_b.score_sha256,
        blind_to_arm_identity=True,
        signature=None,
    )
    judgment_a = replace(
        unsigned_a,
        signature=ExternalSignatureEvidenceV1(
            scheme="dsse",
            authority="verifier-a",
            signed_envelope=central_a.evidence.receipt,
            verification_receipt=central_a.signature_audit,
            signed_payload_sha256=unsigned_a.unsigned_sha256(),
            cryptographically_verified=True,
        ),
    )
    judgment_b = replace(
        unsigned_b,
        signature=ExternalSignatureEvidenceV1(
            scheme="dsse",
            authority="verifier-b",
            signed_envelope=central_b.evidence.receipt,
            verification_receipt=central_b.signature_audit,
            signed_payload_sha256=unsigned_b.unsigned_sha256(),
            cryptographically_verified=True,
        ),
    )
    dual = assess_dual_evaluation(judgment_a, judgment_b)
    central = integrity_assess(
        dual_evaluation_evidence_sha256=dual.evidence_sha256
    )
    assert central.terminal is Terminal.CANDIDATE_REQUIRES_EXTERNAL_AUDIT
    assert central.dual_evaluation_binding_sha256 == dual.binding_sha256
    return central, dual, judgment_a, judgment_b


def compose(
    *,
    assessment: AssessmentV1 | None = None,
    state: OccurrenceWorkflowStateV1 | None = None,
    dual=None,  # type: ignore[no-untyped-def]
    judgment_a=None,  # type: ignore[no-untyped-def]
    judgment_b=None,  # type: ignore[no-untyped-def]
    candidate=None,  # type: ignore[no-untyped-def]
    audit=None,  # type: ignore[no-untyped-def]
    previous=None,  # type: ignore[no-untyped-def]
    terminal_at: str = CANDIDATE_AT,
):
    return complete_occurrence(
        assessment=blocked_assessment() if assessment is None else assessment,
        workflow=workflow() if state is None else state,
        dual_evaluation=(
            assess_dual_evaluation(None, None) if dual is None else dual
        ),
        judgment_a=judgment_a,
        judgment_b=judgment_b,
        candidate_receipt=candidate,
        external_audit_material=audit,
        previous_receipt=previous,
        started_at=STARTED_AT,
        terminal_at=terminal_at,
    )


def replay_inputs(
    *,
    assessment: AssessmentV1 | None = None,
    state: OccurrenceWorkflowStateV1 | None = None,
    dual=None,  # type: ignore[no-untyped-def]
    judgment_a=None,  # type: ignore[no-untyped-def]
    judgment_b=None,  # type: ignore[no-untyped-def]
    candidate=None,  # type: ignore[no-untyped-def]
    audit=None,  # type: ignore[no-untyped-def]
    terminal_at: str = CANDIDATE_AT,
) -> OccurrenceCompletionReplayV1:
    return OccurrenceCompletionReplayV1(
        assessment=blocked_assessment() if assessment is None else assessment,
        workflow=workflow() if state is None else state,
        dual_evaluation=(
            assess_dual_evaluation(None, None) if dual is None else dual
        ),
        judgment_a=judgment_a,
        judgment_b=judgment_b,
        candidate_receipt=candidate,
        external_audit_material=audit,
        started_at=STARTED_AT,
        terminal_at=terminal_at,
    )


def test_missing_evidence_and_workflow_sealed_alone_cannot_publish() -> None:
    receipt = compose()
    assert receipt.terminal_status is CompletionTerminal.BLOCKED
    assert not publication_eligible(receipt, replay=replay_inputs())

    receipt = compose(state=workflow(OccurrencePhase.SEALED))
    assert receipt.terminal_status is CompletionTerminal.BLOCKED
    assert not publication_eligible(
        receipt,
        replay=replay_inputs(state=workflow(OccurrencePhase.SEALED)),
    )


def test_assessment_and_completion_receipts_cannot_be_fabricated() -> None:
    with pytest.raises(OccurrenceIntegrityError, match="assess_occurrence"):
        AssessmentV1(
            Terminal.CANDIDATE_REQUIRES_EXTERNAL_AUDIT,
            INTEGRITY_CLAIM_CEILING,
            "forged",
            "a" * 64,
            "b" * 64,
            "c" * 64,
            "d" * 64,
            ("1" * 64,),
        )

    central, dual, judgment_a, judgment_b = integrated_inputs()
    candidate = compose(
        assessment=central,
        dual=dual,
        judgment_a=judgment_a,
        judgment_b=judgment_b,
    )
    with pytest.raises(OccurrenceCompletionError, match="complete_occurrence"):
        replace(candidate)


def test_same_uid_unrelated_workflow_cannot_reach_pending_state() -> None:
    central, dual, judgment_a, judgment_b = integrated_inputs()
    result = compose(
        assessment=central,
        state=workflow(),
        dual=dual,
        judgment_a=judgment_a,
        judgment_b=judgment_b,
    )
    assert result.terminal_status is CompletionTerminal.BLOCKED
    assert "workflow history" in result.reason


def audit_record(
    monkeypatch, tmp_path, candidate, central, dual, terminal_workflow
):  # type: ignore[no-untyped-def]
    executable = tmp_path / "cosign"; executable.write_bytes(b"x")
    root = tmp_path / "root.json"; root.write_bytes(b"root")
    license_path = tmp_path / "LICENSE"; license_path.write_bytes(b"Apache-2.0")
    blob = tmp_path / "audit-manifest.json"
    bundle = tmp_path / "bundle.json"; bundle.write_bytes(b"bundle")
    history_export = tmp_path / "temporal-history-export.json"
    temporal_receipt = tmp_path / "temporal-terminal.json"
    run_id = "12345678-1234-5678-9234-567812345678"
    server_identity_sha256 = "a" * 64
    signal_authorization_binding_sha256 = "b" * 64
    history_value = {
        "events": [
            {
                "eventId": "1",
                "eventTime": STARTED_AT,
                "eventType": "EVENT_TYPE_WORKFLOW_EXECUTION_STARTED",
                "workflowExecutionStartedEventAttributes": {
                    "workflowType": {"name": TEMPORAL_WORKFLOW_TYPE}
                },
            },
            {
                "eventId": "2",
                "eventTime": FINAL_AT,
                "eventType": "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED",
                "workflowExecutionCompletedEventAttributes": {},
            },
        ],
        "namespace": "g0-test",
        "next_page_token": "",
        "retrieved_at": FINAL_AT,
        "run_id": run_id,
        "schema_version": TEMPORAL_HISTORY_EXPORT_SCHEMA,
        "server_identity_sha256": server_identity_sha256,
        "signal_authorization_binding_sha256": (
            signal_authorization_binding_sha256
        ),
        "source_api": TEMPORAL_HISTORY_SOURCE_API,
        "workflow_id": f"g0-occurrence/{candidate.occurrence_uid}",
    }
    history_export.write_bytes(canonical_json(history_value).encode("utf-8"))
    temporal_receipt_value = {
        "activity_maximum_attempts": 1,
        "candidate_receipt_sha256": candidate.receipt_sha256,
        "claim_boundary": TEMPORAL_RECEIPT_CLAIM_BOUNDARY,
        "completed_at": FINAL_AT,
        "exporter_identity": "independent-temporal-exporter.example.test",
        "history_event_count": 2,
        "history_export_sha256": sha256(history_export.read_bytes()).hexdigest(),
        "history_first_event_id": 1,
        "history_last_event_id": 2,
        "namespace": "g0-test",
        "occurrence_uid": candidate.occurrence_uid,
        "replacement_round_allowed": False,
        "run_id": run_id,
        "schema_version": TEMPORAL_TERMINAL_RECEIPT_SCHEMA,
        "server_identity_sha256": server_identity_sha256,
        "signal_authorization_binding_sha256": (
            signal_authorization_binding_sha256
        ),
        "terminal_phase": "SEALED",
        "workflow_evidence_sha256s": list(
            terminal_workflow.evidence_sha256s
        ),
        "workflow_id": f"g0-occurrence/{candidate.occurrence_uid}",
        "workflow_id_reuse_policy": "REJECT_DUPLICATE",
        "workflow_maximum_attempts": 1,
        "workflow_sha256": completion.workflow_digest(terminal_workflow),
        "workflow_type": TEMPORAL_WORKFLOW_TYPE,
    }
    temporal_receipt.write_bytes(
        canonical_json(temporal_receipt_value).encode("utf-8")
    )
    candidates = tmp_path / "candidates.json"; candidates.write_bytes(b"candidates")
    record = tmp_path / "qualification.json"
    record_value = {
        "schema_version": "hswm-g0-external-audit-qualification/v1",
        "status": "QUALIFIED",
        "toolchain_candidates_sha256": sha256(b"candidates").hexdigest(),
        "cosign": {
            "path": str(executable),
            "sha256": sha256(b"x").hexdigest(),
            "exact_version_output": "cosign version v3.1.3",
            "version": "3.1.3",
            "source_commit": "11926fa5bbbbde47e88fc006b625a17769b743b2",
            "license_path": str(license_path),
            "license_sha256": sha256(b"Apache-2.0").hexdigest(),
        },
        "trusted_root": {
            "path": str(root),
            "sha256": sha256(b"root").hexdigest(),
        },
        "auditor": {
            "identity": "auditor@example.test",
            "issuer": "https://issuer.example.test",
        },
        "qualification_receipt_sha256": "d" * 64,
    }
    record.write_text(json.dumps(record_value), encoding="utf-8")
    signed_fields = {
        "assessment_chain_sha256": central.chain_digest,
        "assessment_sha256": completion.assessment_digest(central),
        "auditor_identity": record_value["auditor"]["identity"],
        "auditor_issuer": record_value["auditor"]["issuer"],
        "candidate_receipt_sha256": candidate.receipt_sha256,
        "candidate_workflow_evidence_sha256s": list(
            candidate.workflow_evidence_sha256s
        ),
        "candidate_workflow_sha256": candidate.workflow_sha256,
        "claim_boundary": completion.CLAIM_CEILING,
        "completion_started_at": STARTED_AT,
        "completion_terminal_at": FINAL_AT,
        "cosign_license_sha256": record_value["cosign"]["license_sha256"],
        "cosign_sha256": record_value["cosign"]["sha256"],
        "dual_assessment_sha256": completion.dual_assessment_digest(dual),
        "dual_evidence_sha256": dual.evidence_sha256,
        "qualification_receipt_sha256": "d" * 64,
        "qualification_sha256": sha256(record.read_bytes()).hexdigest(),
        "schema_version": "hswm-external-completion-audit-manifest/v1",
        "temporal_history_export_sha256": sha256(
            history_export.read_bytes()
        ).hexdigest(),
        "temporal_terminal_receipt_sha256": sha256(
            temporal_receipt.read_bytes()
        ).hexdigest(),
        "terminal_workflow_evidence_sha256s": list(
            terminal_workflow.evidence_sha256s
        ),
        "terminal_workflow_sha256": completion.workflow_digest(
            terminal_workflow
        ),
        "trusted_root_sha256": record_value["trusted_root"]["sha256"],
    }
    blob.write_bytes(canonical_json(signed_fields).encode("utf-8"))
    monkeypatch.setattr(completion, "_QUALIFICATION_RECORD", record)
    monkeypatch.setattr(completion, "_TOOLCHAIN_CANDIDATES", candidates)
    monkeypatch.setattr(
        completion,
        "verify_with_pinned_binary",
        lambda **_: type(
            "R",
            (),
            {
                "ran": True,
                "verified": True,
                "stdout_sha256": "e" * 64,
                "stderr_sha256": "f" * 64,
            },
        )(),
    )
    material = ExternalAuditMaterialV1(
        audit_manifest=blob,
        cosign_bundle=bundle,
        temporal_terminal_receipt=temporal_receipt,
        temporal_history_export=history_export,
    )
    audit = verify_external_audit_material(
        candidate_receipt=candidate,
        assessment=central,
        dual_evaluation=dual,
        terminal_workflow=terminal_workflow,
        material=material,
        completion_started_at=STARTED_AT,
        completion_terminal_at=FINAL_AT,
    )
    return audit, material


def test_exact_two_step_temporal_handshake_is_required_for_sealing(monkeypatch, tmp_path) -> None:
    central, dual, judgment_a, judgment_b = integrated_inputs()
    initial = bound_workflow(central)
    candidate = compose(
        assessment=central,
        state=initial,
        dual=dual,
        judgment_a=judgment_a,
        judgment_b=judgment_b,
    )
    assert candidate.terminal_status is CompletionTerminal.PENDING_EXTERNAL_AUDIT
    candidate_replay = replay_inputs(
        assessment=central,
        state=initial,
        dual=dual,
        judgment_a=judgment_a,
        judgment_b=judgment_b,
    )
    assert not publication_eligible(candidate, replay=candidate_replay)

    sealed_state = advance_occurrence(
        initial,
        next_phase=OccurrencePhase.SEALED,
        evidence_sha256=candidate.receipt_sha256,
        timing=PulseTiming.POST_PULSE,
    )
    without_verified_audit = compose(
        assessment=central,
        state=sealed_state,
        dual=dual,
        judgment_a=judgment_a,
        judgment_b=judgment_b,
        candidate=candidate,
        terminal_at=FINAL_AT,
    )
    assert without_verified_audit.terminal_status is CompletionTerminal.BLOCKED

    absent_material = ExternalAuditMaterialV1(
        audit_manifest=tmp_path / "absent-audit.json",
        cosign_bundle=tmp_path / "absent-bundle.json",
        temporal_terminal_receipt=tmp_path / "absent-temporal.json",
        temporal_history_export=tmp_path / "absent-history.json",
    )
    with pytest.raises(OccurrenceCompletionError, match="not qualified"):
        verify_external_audit_material(
            candidate_receipt=candidate,
            assessment=central,
            dual_evaluation=dual,
            terminal_workflow=sealed_state,
            material=absent_material,
            completion_started_at=STARTED_AT,
            completion_terminal_at=FINAL_AT,
        )
    audit, audit_material = audit_record(
        monkeypatch, tmp_path, candidate, central, dual, sealed_state
    )
    with pytest.raises(OccurrenceCompletionError, match="digest"):
        replace(audit, auditor_identity="forged@example.test")
    final = compose(
        assessment=central,
        state=sealed_state,
        dual=dual,
        judgment_a=judgment_a,
        judgment_b=judgment_b,
        candidate=candidate,
        audit=audit_material,
        terminal_at=FINAL_AT,
    )
    assert final.terminal_status is CompletionTerminal.SEALED
    final_replay = replay_inputs(
        assessment=central,
        state=sealed_state,
        dual=dual,
        judgment_a=judgment_a,
        judgment_b=judgment_b,
        candidate=candidate,
        audit=audit_material,
        terminal_at=FINAL_AT,
    )
    assert publication_eligible(final, replay=final_replay)
    assert final.receipt_sha256 == canonical_sha256(final.receipt_payload())
    assert final.external_audit_verification_sha256 == audit.verification_sha256

    replay = compose(
        assessment=central,
        state=sealed_state,
        dual=dual,
        judgment_a=judgment_a,
        judgment_b=judgment_b,
        candidate=candidate,
        audit=audit_material,
        previous=final,
        terminal_at=FINAL_AT,
    )
    assert replay is final
    with pytest.raises(OccurrenceCompletionError, match="fresh completion inputs"):
        compose(
            assessment=central,
            state=sealed_state,
            dual=dual,
            judgment_a=judgment_a,
            judgment_b=judgment_b,
            candidate=candidate,
            audit=audit_material,
            previous=final,
            terminal_at="2026-09-03T00:03:00Z",
        )

    artifact = final.publication_artifact()
    start, terminal = build_openlineage_events(
            final,
            [artifact, audit.publication_artifact()],
        producer="https://hswm.example/occurrence",
        completion_replay=final_replay,
    )
    assert start["eventType"] == "START"
    assert terminal["eventType"] == "COMPLETE"
    crate = build_ro_crate_metadata(
        final,
        [artifact, audit.publication_artifact()],
        completion_replay=final_replay,
    )
    assert crate["@context"] == "https://w3id.org/ro/crate/1.3/context"

    forged_payload = {
        **final.receipt_payload(),
        "terminal_at": "2026-09-03T00:03:00Z",
    }
    forged = replace(
        final,
        terminal_at=forged_payload["terminal_at"],
        receipt_sha256=canonical_sha256(forged_payload),
        _construction_token=completion._RECEIPT_CONSTRUCTION_TOKEN,
    )
    with pytest.raises(OccurrencePublicationError, match="fresh completion"):
        build_ro_crate_metadata(
            forged,
            [forged.publication_artifact(), audit.publication_artifact()],
            completion_replay=final_replay,
        )

    temporal_receipt_bytes = audit_material.temporal_terminal_receipt.read_bytes()
    audit_material.temporal_terminal_receipt.write_bytes(b"arbitrary plaintext")
    with pytest.raises(OccurrenceCompletionError, match="strict UTF-8 JSON"):
        verify_external_audit_material(
            candidate_receipt=candidate,
            assessment=central,
            dual_evaluation=dual,
            terminal_workflow=sealed_state,
            material=audit_material,
            completion_started_at=STARTED_AT,
            completion_terminal_at=FINAL_AT,
        )
    audit_material.temporal_terminal_receipt.write_bytes(temporal_receipt_bytes)

    history_bytes = audit_material.temporal_history_export.read_bytes()
    invalid_history = json.loads(history_bytes)
    invalid_history["events"][-1]["eventType"] = (
        "EVENT_TYPE_WORKFLOW_EXECUTION_FAILED"
    )
    audit_material.temporal_history_export.write_bytes(
        canonical_json(invalid_history).encode("utf-8")
    )
    with pytest.raises(OccurrenceCompletionError, match="must end"):
        verify_external_audit_material(
            candidate_receipt=candidate,
            assessment=central,
            dual_evaluation=dual,
            terminal_workflow=sealed_state,
            material=audit_material,
            completion_started_at=STARTED_AT,
            completion_terminal_at=FINAL_AT,
        )
    audit_material.temporal_history_export.write_bytes(history_bytes)

    audit_material.audit_manifest.write_bytes(b"{}")
    with pytest.raises(OccurrenceCompletionError, match="does not exactly bind"):
        verify_external_audit_material(
            candidate_receipt=candidate,
            assessment=central,
            dual_evaluation=dual,
            terminal_workflow=sealed_state,
            material=audit_material,
            completion_started_at=STARTED_AT,
            completion_terminal_at=FINAL_AT,
        )


def test_swapped_dual_binding_or_nonexact_temporal_extension_stays_blocked() -> None:
    central, dual, judgment_a, judgment_b = integrated_inputs()
    candidate = compose(
        assessment=central,
        state=bound_workflow(central),
        dual=dual,
        judgment_a=judgment_a,
        judgment_b=judgment_b,
    )
    wrong_seal_state = bound_workflow(
        central,
        OccurrencePhase.SEALED,
        seal_evidence_sha256="f" * 64,
    )
    result = compose(
        assessment=central,
        state=wrong_seal_state,
        dual=dual,
        judgment_a=judgment_a,
        judgment_b=judgment_b,
        candidate=candidate,
        terminal_at=FINAL_AT,
    )
    assert result.terminal_status is CompletionTerminal.BLOCKED

    swapped_a = replace(judgment_a, signature=None)
    swapped_dual = assess_dual_evaluation(swapped_a, judgment_b)
    result = compose(
        assessment=central,
        dual=swapped_dual,
        judgment_a=swapped_a,
        judgment_b=judgment_b,
    )
    assert result.terminal_status is CompletionTerminal.BLOCKED


def test_void_is_immutable_and_projects_as_openlineage_fail() -> None:
    void_state = void_workflow()
    receipt = compose(state=void_state)
    void_replay = replay_inputs(state=void_state)
    assert receipt.terminal_status is CompletionTerminal.VOID
    assert compose(state=void_state, previous=receipt).canonical() == receipt.canonical()
    other = registered_occurrence(
        occurrence_uid="g0-occurrence-1",
        registration_evidence_sha256="2" * 64,
    )
    other = advance_occurrence(
        other,
        next_phase=OccurrencePhase.REVEALED,
        evidence_sha256="e" * 64,
        timing=PulseTiming.POST_PULSE,
    )
    with pytest.raises(OccurrenceCompletionError, match="fresh completion inputs"):
        compose(state=other, previous=receipt)
    _, terminal = build_openlineage_events(
        receipt,
        [receipt.publication_artifact()],
        producer="https://hswm.example/occurrence",
        completion_replay=void_replay,
    )
    assert terminal["eventType"] == "FAIL"


def test_nonterminal_completion_receipts_are_rejected_by_publication() -> None:
    receipt = compose()
    with pytest.raises(OccurrencePublicationError):
        build_ro_crate_metadata(
            receipt,
            [receipt.publication_artifact()],
            completion_replay=replay_inputs(),
        )
