from __future__ import annotations

from uuid import UUID

import pytest

from hswm.evaluation.occurrence_dual_evaluator import assess_dual_evaluation
from hswm.infrastructure import occurrence_publication as publication
from hswm.infrastructure.occurrence_completion import (
    CompletionTerminal,
    OccurrenceCompletionReplayV1,
    complete_occurrence,
)
from hswm.infrastructure.occurrence_integrity import assess_occurrence
from hswm.infrastructure.occurrence_workflow import (
    OccurrencePhase,
    PulseTiming,
    advance_occurrence,
    registered_occurrence,
)


def _blocked_assessment():  # type: ignore[no-untyped-def]
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


def _void_fixture():  # type: ignore[no-untyped-def]
    state = registered_occurrence(
        occurrence_uid="g0-occurrence-void-001",
        registration_evidence_sha256="1" * 64,
    )
    state = advance_occurrence(
        state,
        next_phase=OccurrencePhase.REVEALED,
        evidence_sha256="2" * 64,
        timing=PulseTiming.POST_PULSE,
    )
    assessment = _blocked_assessment()
    dual = assess_dual_evaluation(None, None)
    receipt = complete_occurrence(
        assessment=assessment,
        workflow=state,
        dual_evaluation=dual,
        judgment_a=None,
        judgment_b=None,
        started_at="2026-09-03T00:00:00Z",
        terminal_at="2026-09-03T00:00:03Z",
    )
    assert receipt.terminal_status is CompletionTerminal.VOID
    replay = OccurrenceCompletionReplayV1(
        assessment=assessment,
        workflow=state,
        dual_evaluation=dual,
        judgment_a=None,
        judgment_b=None,
        started_at="2026-09-03T00:00:00Z",
        terminal_at="2026-09-03T00:00:03Z",
    )
    return receipt, replay


def _artifacts(receipt):  # type: ignore[no-untyped-def]
    return [
        receipt.publication_artifact(path="receipts/terminal.json"),
        {
            "path": "raw/actions.json",
            "sha256": "b" * 64,
            "bytes": 12,
            "role": "pre-pulse-action-seal",
        },
        {
            "path": "receipts/custodian.json",
            "sha256": "c" * 64,
            "bytes": 34,
            "media_type": "application/json",
        },
    ]


def test_ro_crate_is_deterministic_non_promoting_and_keeps_void_artifacts() -> None:
    receipt, replay = _void_fixture()
    artifacts = _artifacts(receipt)
    metadata = publication.build_ro_crate_metadata(
        receipt,
        list(reversed(artifacts)),
        completion_replay=replay,
    )

    root = metadata["@graph"][0]
    assert metadata["@context"] == "https://w3id.org/ro/crate/1.3/context"
    assert root[publication.HSWM_PUBLICATION_FACET_SCHEMA_URL + "#terminalStatus"] == "VOID"
    assert root[publication.HSWM_EXTERNAL_AUDIT_SHA256_TERM] is None
    assert root[publication.HSWM_PUBLICATION_FACET_SCHEMA_URL + "#claimBoundary"] == publication.CLAIM_BOUNDARY
    assert root["description"].startswith("Terminal HSWM occurrence")
    assert root["datePublished"] == receipt.terminal_at
    assert root["license"].startswith("No license is granted")
    assert len(root[publication.HSWM_PUBLICATION_SCOPE_SHA256_TERM]) == 64
    assert [entry["@id"] for entry in root["hasPart"]] == [
        "raw/actions.json", "receipts/custodian.json", "receipts/terminal.json"
    ]
    assert metadata == publication.build_ro_crate_metadata(
        receipt, artifacts, completion_replay=replay
    )
    terminal_entity = next(
        entry for entry in metadata["@graph"] if entry.get("@id") == "receipts/terminal.json"
    )
    assert terminal_entity[publication.HSWM_ARTIFACT_SHA256_TERM] == receipt.receipt_sha256
    assert terminal_entity["contentSize"] == str(
        receipt.publication_artifact()["bytes"]
    )
    assert "sha256" not in terminal_entity


def test_openlineage_start_and_void_fail_are_stable() -> None:
    receipt, replay = _void_fixture()
    artifacts = _artifacts(receipt)
    start, terminal = publication.build_openlineage_events(
        receipt,
        artifacts,
        producer="https://hswm.example/exporter/1",
        completion_replay=replay,
    )

    assert start["eventType"] == "START"
    assert terminal["eventType"] == "FAIL"
    assert start["schemaURL"] == publication.OPENLINEAGE_RUN_EVENT_SCHEMA_URL
    assert terminal["schemaURL"] == publication.OPENLINEAGE_RUN_EVENT_SCHEMA_URL
    assert str(UUID(start["run"]["runId"])) == start["run"]["runId"]
    assert start["run"]["runId"] == terminal["run"]["runId"]
    facet = terminal["run"]["facets"]["hswmPublication"]
    assert facet["_schemaURL"] == publication.HSWM_PUBLICATION_FACET_SCHEMA_URL
    assert facet["terminalStatus"] == "VOID"
    assert facet["externalAuditVerificationSha256"] is None
    assert facet["claimBoundary"] == publication.CLAIM_BOUNDARY
    assert len(terminal["inputs"]) == len(artifacts)


def test_forged_terminal_receipt_mapping_is_rejected() -> None:
    _, replay = _void_fixture()
    forged = {
        "occurrence_uid": "g0-occurrence/forged",
        "terminal_status": "SEALED",
        "started_at": "2026-09-03T00:00:00Z",
        "terminal_at": "2026-09-03T00:00:03Z",
        "receipt_sha256": "a" * 64,
    }
    with pytest.raises(publication.OccurrencePublicationError, match="guarded"):
        publication.build_ro_crate_metadata(  # type: ignore[arg-type]
            forged,
            [{"path": "terminal.json", "sha256": "a" * 64, "bytes": 1}],
            completion_replay=replay,
        )


def test_artifacts_must_be_explicit_unique_and_include_receipt() -> None:
    receipt, replay = _void_fixture()
    artifacts = _artifacts(receipt)
    duplicate = [*artifacts, {**artifacts[0], "sha256": "d" * 64}]
    with pytest.raises(publication.OccurrencePublicationError, match="unique"):
        publication.build_ro_crate_metadata(
            receipt, duplicate, completion_replay=replay
        )
    with pytest.raises(publication.OccurrencePublicationError, match="non-traversing"):
        publication.build_ro_crate_metadata(
            receipt,
            [{"path": "../raw", "sha256": receipt.receipt_sha256, "bytes": 1}],
            completion_replay=replay,
        )
    without_receipt = [
        item for item in artifacts if item["sha256"] != receipt.receipt_sha256
    ]
    with pytest.raises(publication.OccurrencePublicationError, match="record"):
        publication.build_ro_crate_metadata(
            receipt, without_receipt, completion_replay=replay
        )


@pytest.mark.parametrize(
    "producer",
    [
        "relative-producer",
        "https://hswm.example/exporter?token=secret",
        "https://hswm.example/exporter#fragment",
    ],
)
def test_openlineage_producer_must_be_credential_free_https(producer: str) -> None:
    receipt, replay = _void_fixture()
    with pytest.raises(publication.OccurrencePublicationError, match="HTTPS URI"):
        publication.build_openlineage_events(
            receipt,
            _artifacts(receipt),
            producer=producer,
            completion_replay=replay,
        )
