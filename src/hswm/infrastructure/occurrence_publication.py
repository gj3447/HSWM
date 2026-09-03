"""Deterministic, non-canonical publication projections for terminal occurrences.

RO-Crate and OpenLineage make an already-terminal occurrence easier to archive
and inspect.  They are exported views: neither projection is an HSWM atom,
Permit, outcome owner, evaluator, nor evidence that G0 has passed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

from hswm.experiments.swm0w_beacon import canonical_sha256
from hswm.infrastructure.occurrence_completion import (
    CompletionTerminal,
    OccurrenceCompletionReplayV1,
    OccurrenceCompletionReceiptV1,
    replay_completion,
    verify_external_audit_material,
)


RO_CRATE_SPECIFICATION = "1.3"
OPENLINEAGE_OBSERVED_RELEASE = "1.53.0"
OPENLINEAGE_RUN_EVENT_SCHEMA_URL = (
    "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"
)
HSWM_ARTIFACT_FACET_SCHEMA_URL = (
    "https://raw.githubusercontent.com/gj3447/HSWM/"
    "6108410a90f5caf8b367bb1fce5282c96744d24e/schemas/"
    "hswm_openlineage_artifact_facet.v1.schema.json"
)
HSWM_PUBLICATION_FACET_SCHEMA_URL = (
    "https://raw.githubusercontent.com/gj3447/HSWM/"
    "6108410a90f5caf8b367bb1fce5282c96744d24e/schemas/"
    "hswm_openlineage_occurrence_publication_facet.v1.schema.json"
)
HSWM_PUBLICATION_TERM_BASE = HSWM_PUBLICATION_FACET_SCHEMA_URL + "#"
HSWM_ARTIFACT_SHA256_TERM = HSWM_ARTIFACT_FACET_SCHEMA_URL + "#sha256"
# Full IRI rather than an undeclared compact JSON-LD term. Its value is the
# SHA-256 of the canonical terminal receipt plus normalized artifact scope.
HSWM_PUBLICATION_SCOPE_SHA256_TERM = HSWM_PUBLICATION_TERM_BASE + "scopeSha256"
HSWM_EXTERNAL_AUDIT_SHA256_TERM = (
    HSWM_PUBLICATION_TERM_BASE + "externalAuditVerificationSha256"
)
CLAIM_BOUNDARY = (
    "publication projection only; non-canonical, non-promoting, not an HSWM "
    "atom, Permit, outcome owner, evaluator, causal-credit path, or G0 evidence"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL_STATUSES = frozenset({"SEALED", "VOID"})


class OccurrencePublicationError(ValueError):
    """Raised when an input cannot be safely projected as a terminal occurrence."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise OccurrencePublicationError(f"{field} must be a non-empty trimmed string")
    return value


def _timestamp(value: object, field: str) -> tuple[str, datetime]:
    value = _text(value, field)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise OccurrencePublicationError(
            f"{field} must be an explicit RFC 3339 timestamp"
        ) from exc
    if "T" not in value or parsed.tzinfo is None:
        raise OccurrencePublicationError(f"{field} must be an explicit RFC 3339 timestamp")
    return value, parsed.astimezone(timezone.utc)


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise OccurrencePublicationError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OccurrencePublicationError("artifact descriptor must be a mapping")
    required = {"path", "sha256", "bytes"}
    if set(value) - {"path", "sha256", "bytes", "media_type", "role"} or not required <= set(value):
        raise OccurrencePublicationError("artifact descriptor has unsupported or missing fields")
    path = _text(value["path"], "artifact.path")
    if (
        path.startswith("/") or path.startswith("../") or "/../" in path
        or path in {".", ".."} or "\\" in path or "//" in path
        or any(ord(character) < 0x20 for character in path)
    ):
        raise OccurrencePublicationError("artifact.path must be a relative non-traversing path")
    byte_count = value["bytes"]
    if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
        raise OccurrencePublicationError("artifact.bytes must be a non-negative integer")
    result: dict[str, Any] = {"path": path, "sha256": _digest(value["sha256"], "artifact.sha256"), "bytes": byte_count}
    for field in ("media_type", "role"):
        if field in value:
            result[field] = _text(value[field], f"artifact.{field}")
    return result


def _terminal_receipt(
    value: OccurrenceCompletionReceiptV1,
    replay: OccurrenceCompletionReplayV1,
) -> tuple[dict[str, str | None], tuple[dict[str, Any], ...]]:
    if not isinstance(value, OccurrenceCompletionReceiptV1):
        raise OccurrencePublicationError(
            "terminal receipt must be a guarded completion receipt, not a mapping"
        )
    recomputed = replay_completion(replay)
    if recomputed.canonical() != value.canonical():
        raise OccurrencePublicationError(
            "terminal receipt does not match fresh completion verification"
        )
    status = value.terminal_status.value
    if status not in _TERMINAL_STATUSES:
        raise OccurrencePublicationError("terminal_status must be SEALED or VOID")
    if value.receipt_sha256 != canonical_sha256(value.receipt_payload()):
        raise OccurrencePublicationError("terminal receipt self-digest is invalid")
    audit_sha256 = value.external_audit_verification_sha256
    if status == CompletionTerminal.SEALED.value:
        audit_sha256 = _digest(
            audit_sha256, "external_audit_verification_sha256"
        )
    elif audit_sha256 is not None:
        raise OccurrencePublicationError(
            "VOID receipt must not claim a successful external audit verification"
        )
    started_text, started = _timestamp(value.started_at, "started_at")
    terminal_text, terminal = _timestamp(value.terminal_at, "terminal_at")
    if terminal < started:
        raise OccurrencePublicationError("terminal_at must not precede started_at")
    required_artifacts = [value.publication_artifact()]
    if status == CompletionTerminal.SEALED.value:
        if (
            replay.candidate_receipt is None
            or replay.dual_evaluation is None
            or replay.external_audit_material is None
        ):
            raise OccurrencePublicationError(
                "SEALED publication replay lacks external audit inputs"
            )
        audit = verify_external_audit_material(
            candidate_receipt=replay.candidate_receipt,
            assessment=replay.assessment,
            dual_evaluation=replay.dual_evaluation,
            terminal_workflow=replay.workflow,
            material=replay.external_audit_material,
            completion_started_at=replay.started_at,
            completion_terminal_at=replay.terminal_at,
        )
        if audit.verification_sha256 != audit_sha256:
            raise OccurrencePublicationError(
                "fresh audit verification differs from the terminal receipt"
            )
        required_artifacts.append(audit.publication_artifact())
    receipt = {
        "occurrence_uid": _text(value.occurrence_uid, "occurrence_uid"),
        "terminal_status": status,
        "started_at": started_text,
        "terminal_at": terminal_text,
        "receipt_sha256": _digest(value.receipt_sha256, "receipt_sha256"),
        "external_audit_verification_sha256": audit_sha256,
    }
    return receipt, tuple(required_artifacts)


def _normalized_artifacts(artifacts: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    if isinstance(artifacts, (str, bytes)) or not isinstance(artifacts, Sequence):
        raise OccurrencePublicationError("artifacts must be a sequence of explicit descriptors")
    normalized = tuple(_artifact(item) for item in artifacts)
    if not normalized:
        raise OccurrencePublicationError("artifacts must include the terminal receipt")
    paths = [item["path"] for item in normalized]
    if len(paths) != len(set(paths)):
        raise OccurrencePublicationError("artifact paths must be unique")
    return tuple(sorted(normalized, key=lambda item: item["path"]))


def _require_replayed_artifacts(
    entries: Sequence[Mapping[str, Any]],
    required: Sequence[Mapping[str, Any]],
) -> None:
    """Require one exact byte/media/role descriptor for each replayed record."""

    for expected in required:
        matching = [item for item in entries if item["sha256"] == expected["sha256"]]
        if len(matching) != 1:
            raise OccurrencePublicationError(
                "artifacts must contain each replay-verified record exactly once"
            )
        actual = matching[0]
        if any(
            actual.get(field) != expected[field]
            for field in ("bytes", "media_type", "role")
        ):
            raise OccurrencePublicationError(
                "replay-verified artifact metadata does not match its exact bytes"
            )


def _publication_scope_sha256(receipt: Mapping[str, Any], entries: Sequence[Mapping[str, Any]]) -> str:
    """Digest the explicit receipt/artifact scope, not an implicit directory."""
    scope = {"artifacts": list(entries), "terminalReceipt": dict(receipt)}
    encoded = json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def build_ro_crate_metadata(
    terminal_receipt: OccurrenceCompletionReceiptV1,
    artifacts: Sequence[Mapping[str, Any]],
    *,
    completion_replay: OccurrenceCompletionReplayV1,
) -> dict[str, Any]:
    """Return deterministic RO-Crate 1.3 JSON-LD metadata for a terminal receipt.

    Artifact descriptors are deliberately required even for ``VOID``.  The
    function does not dereference paths or verify bytes: the caller must bind
    those descriptors to an external sealed store before calling it.
    """

    receipt, required_artifacts = _terminal_receipt(
        terminal_receipt, completion_replay
    )
    entries = _normalized_artifacts(artifacts)
    _require_replayed_artifacts(entries, required_artifacts)
    root_id = "./"
    scope_sha256 = _publication_scope_sha256(receipt, entries)
    graph: list[dict[str, Any]] = [
        {
            "@id": root_id,
            "@type": "Dataset",
            "conformsTo": {"@id": "https://w3id.org/ro/crate/1.3"},
            "hasPart": [{"@id": item["path"]} for item in entries],
            HSWM_PUBLICATION_TERM_BASE + "claimBoundary": CLAIM_BOUNDARY,
            HSWM_PUBLICATION_TERM_BASE + "occurrenceUid": receipt["occurrence_uid"],
            HSWM_PUBLICATION_TERM_BASE + "receiptSha256": receipt["receipt_sha256"],
            HSWM_EXTERNAL_AUDIT_SHA256_TERM: receipt[
                "external_audit_verification_sha256"
            ],
            HSWM_PUBLICATION_SCOPE_SHA256_TERM: scope_sha256,
            HSWM_PUBLICATION_TERM_BASE + "terminalStatus": receipt["terminal_status"],
            # The terminal receipt is the release cut for this deterministic
            # projection.  RO-Crate 1.3 requires a root datePublished value.
            "datePublished": receipt["terminal_at"],
            "description": (
                "Terminal HSWM occurrence publication projection; its explicit "
                "receipt and artifact scope is identified by scopeSha256."
            ),
            "license": (
                "No license is granted by this projection; the distributor must "
                "verify and declare the governing license for every artifact "
                "before public release."
            ),
            "name": f"HSWM occurrence publication: {receipt['occurrence_uid']}",
        },
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "about": {"@id": root_id},
            "conformsTo": {"@id": "https://w3id.org/ro/crate/1.3"},
        },
    ]
    for item in entries:
        entity: dict[str, Any] = {
            "@id": item["path"],
            "@type": "File",
            "contentSize": str(item["bytes"]),
            HSWM_ARTIFACT_SHA256_TERM: item["sha256"],
        }
        if "media_type" in item:
            entity["encodingFormat"] = item["media_type"]
        if "role" in item:
            entity[HSWM_ARTIFACT_FACET_SCHEMA_URL + "#artifactRole"] = item["role"]
        graph.append(entity)
    return {
        "@context": "https://w3id.org/ro/crate/1.3/context",
        "@graph": graph,
    }


def build_openlineage_events(
    terminal_receipt: OccurrenceCompletionReceiptV1,
    artifacts: Sequence[Mapping[str, Any]],
    *,
    producer: str,
    completion_replay: OccurrenceCompletionReplayV1,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return deterministic OpenLineage 1.53-compatible START and terminal events."""

    receipt, required_artifacts = _terminal_receipt(
        terminal_receipt, completion_replay
    )
    entries = _normalized_artifacts(artifacts)
    producer = _text(producer, "producer")
    parsed_producer = urlparse(producer)
    if (
        parsed_producer.scheme != "https" or not parsed_producer.hostname
        or parsed_producer.username is not None or parsed_producer.password is not None
        or parsed_producer.query or parsed_producer.fragment
    ):
        raise OccurrencePublicationError("producer must be a credential-free HTTPS URI")
    _require_replayed_artifacts(entries, required_artifacts)
    run_id = str(uuid5(NAMESPACE_URL, f"{receipt['occurrence_uid']}\x00{receipt['receipt_sha256']}"))
    job = {"namespace": "hswm.occurrence.publication", "name": receipt["occurrence_uid"]}
    inputs = [
        {
            "namespace": "hswm.artifact.sha256",
            "name": item["sha256"],
            "facets": {
                "hswmArtifact": {
                    "_producer": producer,
                    "_schemaURL": HSWM_ARTIFACT_FACET_SCHEMA_URL,
                    "bytes": item["bytes"],
                    "path": item["path"],
                    "sha256": item["sha256"],
                }
            },
        }
        for item in entries
    ]
    run_facets = {
        "hswmPublication": {
            "_producer": producer,
            "_schemaURL": HSWM_PUBLICATION_FACET_SCHEMA_URL,
            "claimBoundary": CLAIM_BOUNDARY,
            "externalAuditVerificationSha256": receipt[
                "external_audit_verification_sha256"
            ],
            "receiptSha256": receipt["receipt_sha256"],
            "terminalStatus": receipt["terminal_status"],
        }
    }
    common = {
        "schemaURL": OPENLINEAGE_RUN_EVENT_SCHEMA_URL,
        "producer": producer,
        "job": job,
        "inputs": inputs,
        "outputs": [],
        "run": {"runId": run_id, "facets": run_facets},
    }
    start = {"eventType": "START", "eventTime": receipt["started_at"], **deepcopy(common)}
    terminal = {
        "eventType": "COMPLETE" if receipt["terminal_status"] == "SEALED" else "FAIL",
        "eventTime": receipt["terminal_at"],
        **deepcopy(common),
    }
    return start, terminal


__all__ = [
    "CLAIM_BOUNDARY",
    "HSWM_EXTERNAL_AUDIT_SHA256_TERM",
    "HSWM_ARTIFACT_SHA256_TERM",
    "HSWM_ARTIFACT_FACET_SCHEMA_URL",
    "HSWM_PUBLICATION_FACET_SCHEMA_URL",
    "HSWM_PUBLICATION_SCOPE_SHA256_TERM",
    "OPENLINEAGE_OBSERVED_RELEASE",
    "OPENLINEAGE_RUN_EVENT_SCHEMA_URL",
    "RO_CRATE_SPECIFICATION",
    "OccurrencePublicationError",
    "build_openlineage_events",
    "build_ro_crate_metadata",
]
