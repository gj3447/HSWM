"""Fail-closed composition of integrity, evaluation, and workflow evidence.

The completion boundary is deliberately two-step. A valid assessment at the
``DUAL_EVALUATED`` workflow phase produces a non-publishable ``PENDING_EXTERNAL_AUDIT``
receipt. Temporal must then record that exact receipt digest as the final
``SEALED`` transition. Only a second composition over that terminal history
can produce a publication-eligible ``SEALED`` receipt.

Only :func:`verify_external_audit_material` invokes a repository-qualified,
artifact-pinned Cosign verifier.  No function promotes a receipt to outcome
truth, G0, G1, Permit, canonical admission, or learning evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import InitVar, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
import re
import sysconfig
from typing import Any
from uuid import UUID

from hswm.evaluation.occurrence_dual_evaluator import (
    DualEvaluationAssessmentV1,
    DualEvaluationTerminal,
    IndependentJudgmentBV1,
    InspectJudgmentAV1,
    assess_dual_evaluation,
)
from hswm.experiments.swm0w_beacon import canonical_json, canonical_sha256
from hswm.infrastructure.occurrence_attestation import (
    cosign_verify_blob_attestation_artifact_argv,
    verify_with_pinned_binary,
)
from hswm.infrastructure.occurrence_integrity import AssessmentV1, Terminal
from hswm.infrastructure.occurrence_workflow import (
    OccurrencePhase,
    OccurrenceWorkflowStateV1,
)


SCHEMA = "hswm-occurrence-completion/v1"
CLAIM_CEILING = (
    "COMPLETION_HANDSHAKE_AND_QUALIFIED_EXTERNAL_AUDIT_BINDING_ONLY_NOT_"
    "OUTCOME_TRUTH_NOT_G0_NOT_G1_NOT_CANONICAL_LEARNING"
)
PENDING_EXTERNAL_AUDIT_REASON = (
    "candidate evidence is pending external audit verification and Temporal finalization"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_CONSTRUCTION_TOKEN = object()
_AUDIT_VERIFICATION_CONSTRUCTION_TOKEN = object()
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_INSTALLED_DATA_ROOT = (
    Path(sysconfig.get_path("data")) / "share/hswm/g0_occurrence"
)


def _fixed_data_path(filename: str) -> Path:
    repository_path = _REPOSITORY_ROOT / "_research/g0_occurrence" / filename
    return repository_path if repository_path.is_file() else _INSTALLED_DATA_ROOT / filename


_QUALIFICATION_RECORD = _fixed_data_path(
    "HSWM_G0_EXTERNAL_AUDIT_QUALIFICATION.v1.json"
)
_MAX_QUALIFICATION_BYTES = 64 * 1024
_MAX_AUDIT_INPUT_BYTES = 16 * 1024 * 1024
_TOOLCHAIN_CANDIDATES = _fixed_data_path(
    "HSWM_G0_OCCURRENCE_TOOLCHAIN_CANDIDATES.v1.json"
)
TEMPORAL_TERMINAL_RECEIPT_SCHEMA = (
    "hswm-temporal-terminal-execution-audit-receipt/v1"
)
TEMPORAL_HISTORY_EXPORT_SCHEMA = "hswm-temporal-history-export/v1"
TEMPORAL_HISTORY_SOURCE_API = (
    "temporal.api.workflowservice.v1.WorkflowService/GetWorkflowExecutionHistory"
)
TEMPORAL_WORKFLOW_TYPE = "hswm_g0_occurrence_one_shot_workflow"
TEMPORAL_RECEIPT_CLAIM_BOUNDARY = (
    "qualified-auditor assertion over a complete Temporal history export; "
    "not a Temporal-native signature, outcome truth, G0, Permit, canonical "
    "admission, or learning evidence"
)


class OccurrenceCompletionError(ValueError):
    """The completion inputs are malformed or attempt to bypass a boundary."""


class CompletionTerminal(StrEnum):
    BLOCKED = "BLOCKED"
    PENDING_EXTERNAL_AUDIT = "PENDING_EXTERNAL_AUDIT"
    SEALED = "SEALED"
    VOID = "VOID"


@dataclass(frozen=True, slots=True)
class ExternalAuditMaterialV1:
    """Untrusted paths that the trusted completion boundary must verify."""

    audit_manifest: Path
    cosign_bundle: Path
    temporal_terminal_receipt: Path
    temporal_history_export: Path

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, Path)
            for value in (
                self.audit_manifest,
                self.cosign_bundle,
                self.temporal_terminal_receipt,
                self.temporal_history_export,
            )
        ):
            raise OccurrenceCompletionError(
                "external audit material values must be filesystem paths"
            )


@dataclass(frozen=True, slots=True)
class ExternalAuditVerificationV1:
    """Content-addressed record emitted after pinned Cosign verification.

    This record is publication material, not an authorization capability.
    :func:`complete_occurrence` never trusts a caller-supplied instance; it
    reruns verification from :class:`ExternalAuditMaterialV1` inside the
    trusted completion boundary.
    """

    audit_manifest_sha256: str
    audit_bundle_sha256: str
    candidate_receipt_sha256: str
    assessment_sha256: str
    assessment_chain_sha256: str
    dual_assessment_sha256: str
    dual_evidence_sha256: str
    candidate_workflow_sha256: str
    candidate_workflow_evidence_sha256s: tuple[str, ...]
    terminal_workflow_sha256: str
    terminal_workflow_evidence_sha256s: tuple[str, ...]
    temporal_terminal_receipt_sha256: str
    temporal_history_export_sha256: str
    completion_started_at: str
    completion_terminal_at: str
    qualification_sha256: str
    qualification_receipt_sha256: str
    cosign_sha256: str
    cosign_license_sha256: str
    trusted_root_sha256: str
    verification_stdout_sha256: str
    verification_stderr_sha256: str
    auditor_identity: str
    auditor_issuer: str
    verification_sha256: str
    _construction_token: InitVar[object | None] = None

    def __post_init__(self, _construction_token: object | None) -> None:
        for name in (
            "audit_manifest_sha256",
            "audit_bundle_sha256",
            "candidate_receipt_sha256",
            "assessment_sha256",
            "assessment_chain_sha256",
            "dual_assessment_sha256",
            "dual_evidence_sha256",
            "candidate_workflow_sha256",
            "terminal_workflow_sha256",
            "temporal_terminal_receipt_sha256",
            "temporal_history_export_sha256",
            "qualification_sha256",
            "qualification_receipt_sha256",
            "cosign_sha256",
            "cosign_license_sha256",
            "trusted_root_sha256",
            "verification_stdout_sha256",
            "verification_stderr_sha256",
            "verification_sha256",
        ):
            _digest(getattr(self, name), name)
        if type(self.candidate_workflow_evidence_sha256s) is not tuple:
            raise OccurrenceCompletionError("audit workflow evidence chain must be immutable")
        for value in self.candidate_workflow_evidence_sha256s:
            _digest(value, "audit workflow evidence")
        if type(self.terminal_workflow_evidence_sha256s) is not tuple:
            raise OccurrenceCompletionError(
                "audit terminal workflow evidence chain must be immutable"
            )
        for value in self.terminal_workflow_evidence_sha256s:
            _digest(value, "audit terminal workflow evidence")
        if not all(
            isinstance(value, str)
            and value
            and value.strip() == value
            and len(value) <= 1024
            for value in (self.auditor_identity, self.auditor_issuer)
        ):
            raise OccurrenceCompletionError("auditor identity and issuer are required")
        if _time(self.completion_terminal_at, "completion_terminal_at") < _time(
            self.completion_started_at, "completion_started_at"
        ):
            raise OccurrenceCompletionError(
                "completion terminal time precedes completion start"
            )
        if self.verification_sha256 != canonical_sha256(
            self.verification_payload()
        ):
            raise OccurrenceCompletionError(
                "external audit verification digest does not bind its payload"
            )
        if _construction_token is not _AUDIT_VERIFICATION_CONSTRUCTION_TOKEN:
            raise OccurrenceCompletionError(
                "external audit verification records must be emitted by the "
                "qualified verifier"
            )

    def verification_payload(self) -> dict[str, Any]:
        return {
            "assessment_chain_sha256": self.assessment_chain_sha256,
            "assessment_sha256": self.assessment_sha256,
            "audit_bundle_sha256": self.audit_bundle_sha256,
            "audit_manifest_sha256": self.audit_manifest_sha256,
            "auditor_identity": self.auditor_identity,
            "auditor_issuer": self.auditor_issuer,
            "candidate_receipt_sha256": self.candidate_receipt_sha256,
            "candidate_workflow_evidence_sha256s": list(
                self.candidate_workflow_evidence_sha256s
            ),
            "candidate_workflow_sha256": self.candidate_workflow_sha256,
            "completion_started_at": self.completion_started_at,
            "completion_terminal_at": self.completion_terminal_at,
            "terminal_workflow_evidence_sha256s": list(
                self.terminal_workflow_evidence_sha256s
            ),
            "terminal_workflow_sha256": self.terminal_workflow_sha256,
            "temporal_terminal_receipt_sha256": (
                self.temporal_terminal_receipt_sha256
            ),
            "temporal_history_export_sha256": (
                self.temporal_history_export_sha256
            ),
            "cosign_license_sha256": self.cosign_license_sha256,
            "cosign_sha256": self.cosign_sha256,
            "dual_assessment_sha256": self.dual_assessment_sha256,
            "dual_evidence_sha256": self.dual_evidence_sha256,
            "qualification_receipt_sha256": self.qualification_receipt_sha256,
            "qualification_sha256": self.qualification_sha256,
            "schema_version": "hswm-external-audit-verification/v1",
            "trusted_root_sha256": self.trusted_root_sha256,
            "verification_stderr_sha256": self.verification_stderr_sha256,
            "verification_stdout_sha256": self.verification_stdout_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {
            **self.verification_payload(),
            "verification_sha256": self.verification_sha256,
        }

    def publication_artifact(self, *, path: str = "external-audit-verification.json") -> dict[str, Any]:
        payload = canonical_json(self.verification_payload()).encode("utf-8")
        return {
            "path": path,
            "sha256": self.verification_sha256,
            "bytes": len(payload),
            "media_type": "application/json",
            "role": "external-audit-verification",
        }


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise OccurrenceCompletionError(f"{name} must be lowercase SHA-256")
    return value


def _time(value: object, name: str) -> datetime:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or "T" not in value
    ):
        raise OccurrenceCompletionError(f"{name} must be RFC 3339")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise OccurrenceCompletionError(f"{name} must be RFC 3339") from exc
    if parsed.tzinfo is None:
        raise OccurrenceCompletionError(f"{name} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def assessment_digest(value: AssessmentV1) -> str:
    if not isinstance(value, AssessmentV1):
        raise OccurrenceCompletionError("integrity assessment type is invalid")
    return canonical_sha256(value.canonical())


def dual_assessment_digest(value: DualEvaluationAssessmentV1) -> str:
    if not isinstance(value, DualEvaluationAssessmentV1):
        raise OccurrenceCompletionError("dual assessment type is invalid")
    return canonical_sha256(value.canonical())


def workflow_digest(value: OccurrenceWorkflowStateV1) -> str:
    if not isinstance(value, OccurrenceWorkflowStateV1):
        raise OccurrenceCompletionError("workflow type is invalid")
    return canonical_sha256(
        {
            "evidence_sha256s": list(value.evidence_sha256s),
            "occurrence_uid": value.occurrence_uid,
            "phase": value.phase.value,
            "rejected_evidence_sha256": value.rejected_evidence_sha256,
            "schema_version": value.schema_version,
            "void_reason": (
                None if value.void_reason is None else value.void_reason.value
            ),
        }
    )


@dataclass(frozen=True, slots=True)
class OccurrenceCompletionReceiptV1:
    """Content-addressed completion receipt with a self-hash-free payload."""

    occurrence_uid: str
    terminal_status: CompletionTerminal
    reason: str
    started_at: str
    terminal_at: str
    integrity_assessment_sha256: str
    integrity_chain_sha256: str
    workflow_sha256: str
    workflow_evidence_sha256s: tuple[str, ...]
    dual_evaluation_assessment_sha256: str | None
    dual_evaluation_evidence_sha256: str | None
    external_audit_verification_sha256: str | None
    claim_ceiling: str
    receipt_sha256: str
    _construction_token: InitVar[object | None] = None

    def __post_init__(self, _construction_token: object | None) -> None:
        if (
            not isinstance(self.occurrence_uid, str)
            or not self.occurrence_uid
            or not isinstance(self.terminal_status, CompletionTerminal)
            or not isinstance(self.reason, str)
            or not self.reason
            or self.reason.strip() != self.reason
        ):
            raise OccurrenceCompletionError("receipt fields are invalid")
        if _time(self.terminal_at, "terminal_at") < _time(
            self.started_at, "started_at"
        ):
            raise OccurrenceCompletionError("terminal_at precedes started_at")
        for name in (
            "integrity_assessment_sha256",
            "integrity_chain_sha256",
            "workflow_sha256",
            "receipt_sha256",
        ):
            _digest(getattr(self, name), name)
        if type(self.workflow_evidence_sha256s) is not tuple:
            raise OccurrenceCompletionError("workflow evidence chain must be immutable")
        for digest in self.workflow_evidence_sha256s:
            _digest(digest, "workflow evidence")
        for name in (
            "dual_evaluation_assessment_sha256",
            "dual_evaluation_evidence_sha256",
            "external_audit_verification_sha256",
        ):
            value = getattr(self, name)
            if value is not None:
                _digest(value, name)
        if (
            self.terminal_status is CompletionTerminal.SEALED
            and self.external_audit_verification_sha256 is None
        ):
            raise OccurrenceCompletionError(
                "SEALED receipt requires external audit verification"
            )
        if (
            self.terminal_status is not CompletionTerminal.SEALED
            and self.external_audit_verification_sha256 is not None
        ):
            raise OccurrenceCompletionError(
                "non-SEALED receipt cannot claim external audit verification"
            )
        if self.claim_ceiling != CLAIM_CEILING:
            raise OccurrenceCompletionError("receipt claim ceiling is fixed")
        if self.receipt_sha256 != canonical_sha256(self.receipt_payload()):
            raise OccurrenceCompletionError("receipt digest does not bind its payload")
        if _construction_token is not _RECEIPT_CONSTRUCTION_TOKEN:
            raise OccurrenceCompletionError(
                "completion receipts must be constructed by complete_occurrence"
            )

    def receipt_payload(self) -> dict[str, Any]:
        return {
            "claim_ceiling": self.claim_ceiling,
            "dual_evaluation_assessment_sha256": (
                self.dual_evaluation_assessment_sha256
            ),
            "dual_evaluation_evidence_sha256": (
                self.dual_evaluation_evidence_sha256
            ),
            "external_audit_verification_sha256": self.external_audit_verification_sha256,
            "integrity_assessment_sha256": self.integrity_assessment_sha256,
            "integrity_chain_sha256": self.integrity_chain_sha256,
            "occurrence_uid": self.occurrence_uid,
            "reason": self.reason,
            "schema_version": SCHEMA,
            "started_at": self.started_at,
            "terminal_at": self.terminal_at,
            "terminal_status": self.terminal_status.value,
            "workflow_evidence_sha256s": list(self.workflow_evidence_sha256s),
            "workflow_sha256": self.workflow_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.receipt_payload(), "receipt_sha256": self.receipt_sha256}

    def receipt_payload_bytes(self) -> bytes:
        return canonical_json(self.receipt_payload()).encode("utf-8")

    def publication_artifact(
        self, *, path: str = "occurrence-terminal-receipt.payload.json"
    ) -> dict[str, Any]:
        """Describe the exact self-hash-free payload bytes."""

        return {
            "bytes": len(self.receipt_payload_bytes()),
            "media_type": "application/json",
            "path": path,
            "role": "terminal-receipt-payload",
            "sha256": self.receipt_sha256,
        }


def _receipt(
    *,
    status: CompletionTerminal,
    reason: str,
    assessment: AssessmentV1,
    workflow: OccurrenceWorkflowStateV1,
    dual_evaluation: DualEvaluationAssessmentV1 | None,
    external_audit_verification: ExternalAuditVerificationV1 | None = None,
    started_at: str,
    terminal_at: str,
) -> OccurrenceCompletionReceiptV1:
    payload = {
        "claim_ceiling": CLAIM_CEILING,
        "dual_evaluation_assessment_sha256": (
            None
            if dual_evaluation is None
            else dual_assessment_digest(dual_evaluation)
        ),
        "dual_evaluation_evidence_sha256": (
            None if dual_evaluation is None else dual_evaluation.evidence_sha256
        ),
        "external_audit_verification_sha256": (
            None
            if external_audit_verification is None
            else external_audit_verification.verification_sha256
        ),
        "integrity_assessment_sha256": assessment_digest(assessment),
        "integrity_chain_sha256": assessment.chain_digest,
        "occurrence_uid": workflow.occurrence_uid,
        "reason": reason,
        "schema_version": SCHEMA,
        "started_at": started_at,
        "terminal_at": terminal_at,
        "terminal_status": status.value,
        "workflow_evidence_sha256s": list(workflow.evidence_sha256s),
        "workflow_sha256": workflow_digest(workflow),
    }
    return OccurrenceCompletionReceiptV1(
        occurrence_uid=workflow.occurrence_uid,
        terminal_status=status,
        reason=reason,
        started_at=started_at,
        terminal_at=terminal_at,
        integrity_assessment_sha256=payload["integrity_assessment_sha256"],
        integrity_chain_sha256=assessment.chain_digest,
        workflow_sha256=payload["workflow_sha256"],
        workflow_evidence_sha256s=workflow.evidence_sha256s,
        dual_evaluation_assessment_sha256=payload[
            "dual_evaluation_assessment_sha256"
        ],
        dual_evaluation_evidence_sha256=payload[
            "dual_evaluation_evidence_sha256"
        ],
        external_audit_verification_sha256=payload["external_audit_verification_sha256"],
        claim_ceiling=CLAIM_CEILING,
        receipt_sha256=canonical_sha256(payload),
        _construction_token=_RECEIPT_CONSTRUCTION_TOKEN,
    )


_INTEGRITY_VOID_TERMINALS = frozenset(
    {
        Terminal.VOID_BINDING_CHAIN,
        Terminal.VOID_DUPLICATE_OCCURRENCE,
        Terminal.VOID_EVALUATOR_DISAGREEMENT,
        Terminal.VOID_LATE_EVIDENCE,
        Terminal.VOID_RETRY,
        Terminal.VOID_ROLE_SEPARATION,
    }
)
_DUAL_VOID_TERMINALS = frozenset(
    {
        DualEvaluationTerminal.VOID_EVALUATOR_DISAGREEMENT,
        DualEvaluationTerminal.VOID_EVALUATOR_NONINDEPENDENT,
    }
)


def _bounded_bytes(path: Path, name: str, limit: int) -> tuple[Path, bytes]:
    if not isinstance(path, Path):
        raise OccurrenceCompletionError(f"{name} must be a filesystem path")
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise OccurrenceCompletionError(f"{name} must be a regular file")
        if resolved.stat().st_size > limit:
            raise OccurrenceCompletionError(f"{name} exceeds its byte limit")
        return resolved, resolved.read_bytes()
    except OSError as exc:
        raise OccurrenceCompletionError(f"cannot read {name}") from exc


def _strict_json_object(raw: bytes, name: str) -> dict[str, Any]:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OccurrenceCompletionError(f"{name} contains a duplicate key")
            result[key] = value
        return result

    def reject_nonfinite(value: str) -> None:
        raise OccurrenceCompletionError(
            f"{name} contains non-finite JSON number {value}"
        )

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise OccurrenceCompletionError(f"{name} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise OccurrenceCompletionError(f"{name} must be a JSON object")
    return value


def _bounded_text(value: object, name: str, *, maximum: int = 1024) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or len(value) > maximum
        or "\x00" in value
    ):
        raise OccurrenceCompletionError(f"{name} must be bounded non-empty text")
    return value


def _positive_integer(value: object, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise OccurrenceCompletionError(f"{name} must be a positive integer")
    return value


def _event_id(value: object, name: str) -> int:
    if isinstance(value, str) and value.isascii() and value.isdigit():
        value = int(value)
    return _positive_integer(value, name)


@dataclass(frozen=True, slots=True)
class TemporalHistoryExportV1:
    """Canonical auditor export of a complete Temporal history response."""

    namespace: str
    workflow_id: str
    run_id: str
    retrieved_at: str
    server_identity_sha256: str
    signal_authorization_binding_sha256: str
    events: tuple[Mapping[str, Any], ...]

    @classmethod
    def from_bytes(cls, raw: bytes) -> "TemporalHistoryExportV1":
        value = _strict_json_object(raw, "Temporal history export")
        expected = {
            "events",
            "namespace",
            "next_page_token",
            "retrieved_at",
            "run_id",
            "schema_version",
            "server_identity_sha256",
            "signal_authorization_binding_sha256",
            "source_api",
            "workflow_id",
        }
        if set(value) != expected:
            raise OccurrenceCompletionError(
                "Temporal history export schema is invalid"
            )
        if (
            value["schema_version"] != TEMPORAL_HISTORY_EXPORT_SCHEMA
            or value["source_api"] != TEMPORAL_HISTORY_SOURCE_API
            or value["next_page_token"] != ""
        ):
            raise OccurrenceCompletionError(
                "Temporal history export is not a complete supported response"
            )
        if canonical_json(value).encode("utf-8") != raw:
            raise OccurrenceCompletionError(
                "Temporal history export must use canonical JSON bytes"
            )
        events = value["events"]
        if type(events) is not list or not events:
            raise OccurrenceCompletionError(
                "Temporal history export requires a non-empty event list"
            )
        if any(not isinstance(event, Mapping) for event in events):
            raise OccurrenceCompletionError("Temporal history events must be objects")
        try:
            run_id = str(UUID(_bounded_text(value["run_id"], "Temporal run_id")))
        except ValueError as exc:
            raise OccurrenceCompletionError(
                "Temporal run_id must be a canonical UUID"
            ) from exc
        if run_id != value["run_id"]:
            raise OccurrenceCompletionError(
                "Temporal run_id must be a canonical lowercase UUID"
            )
        instance = cls(
            namespace=_bounded_text(value["namespace"], "Temporal namespace"),
            workflow_id=_bounded_text(value["workflow_id"], "Temporal workflow_id"),
            run_id=run_id,
            retrieved_at=_bounded_text(value["retrieved_at"], "history retrieved_at"),
            server_identity_sha256=_digest(
                value["server_identity_sha256"], "Temporal server identity"
            ),
            signal_authorization_binding_sha256=_digest(
                value["signal_authorization_binding_sha256"],
                "Temporal signal authorization binding",
            ),
            events=tuple(events),
        )
        instance.validate_events()
        return instance

    def validate_events(self) -> None:
        ids: list[int] = []
        for index, event in enumerate(self.events):
            if "eventId" not in event or "eventType" not in event or "eventTime" not in event:
                raise OccurrenceCompletionError(
                    f"Temporal history event {index} lacks identity/type/time"
                )
            ids.append(_event_id(event["eventId"], f"Temporal event {index} id"))
            _time(event["eventTime"], f"Temporal event {index} time")
        if ids[0] != 1 or any(right <= left for left, right in zip(ids, ids[1:])):
            raise OccurrenceCompletionError(
                "Temporal history event IDs must start at one and increase"
            )
        first = self.events[0]
        last = self.events[-1]
        if first["eventType"] != "EVENT_TYPE_WORKFLOW_EXECUTION_STARTED":
            raise OccurrenceCompletionError(
                "Temporal history must start with WorkflowExecutionStarted"
            )
        if last["eventType"] != "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED":
            raise OccurrenceCompletionError(
                "Temporal history must end with WorkflowExecutionCompleted"
            )
        started = first.get("workflowExecutionStartedEventAttributes")
        completed = last.get("workflowExecutionCompletedEventAttributes")
        if not isinstance(started, Mapping) or not isinstance(completed, Mapping):
            raise OccurrenceCompletionError(
                "Temporal terminal history lacks start/completion attributes"
            )
        workflow_type = started.get("workflowType")
        if (
            not isinstance(workflow_type, Mapping)
            or workflow_type.get("name") != TEMPORAL_WORKFLOW_TYPE
        ):
            raise OccurrenceCompletionError(
                "Temporal history workflow type does not match the fixed worker"
            )
        if _time(self.retrieved_at, "history retrieved_at") < _time(
            last["eventTime"], "Temporal completion event time"
        ):
            raise OccurrenceCompletionError(
                "Temporal history was retrieved before its completion event"
            )

    @property
    def first_event_id(self) -> int:
        return _event_id(self.events[0]["eventId"], "first Temporal event id")

    @property
    def last_event_id(self) -> int:
        return _event_id(self.events[-1]["eventId"], "last Temporal event id")

    @property
    def started_at(self) -> str:
        return _bounded_text(self.events[0]["eventTime"], "Temporal start time")

    @property
    def completed_at(self) -> str:
        return _bounded_text(self.events[-1]["eventTime"], "Temporal completion time")


@dataclass(frozen=True, slots=True)
class TemporalTerminalAuditReceiptV1:
    """Auditor assertion binding one terminal workflow to its history bytes."""

    occurrence_uid: str
    namespace: str
    workflow_id: str
    run_id: str
    workflow_type: str
    terminal_phase: str
    candidate_receipt_sha256: str
    workflow_sha256: str
    workflow_evidence_sha256s: tuple[str, ...]
    history_export_sha256: str
    history_event_count: int
    history_first_event_id: int
    history_last_event_id: int
    completed_at: str
    workflow_id_reuse_policy: str
    workflow_maximum_attempts: int
    activity_maximum_attempts: int
    replacement_round_allowed: bool
    signal_authorization_binding_sha256: str
    server_identity_sha256: str
    exporter_identity: str

    @classmethod
    def from_bytes(cls, raw: bytes) -> "TemporalTerminalAuditReceiptV1":
        value = _strict_json_object(raw, "Temporal terminal audit receipt")
        fields = {
            "activity_maximum_attempts",
            "candidate_receipt_sha256",
            "claim_boundary",
            "completed_at",
            "exporter_identity",
            "history_event_count",
            "history_export_sha256",
            "history_first_event_id",
            "history_last_event_id",
            "namespace",
            "occurrence_uid",
            "replacement_round_allowed",
            "run_id",
            "schema_version",
            "server_identity_sha256",
            "signal_authorization_binding_sha256",
            "terminal_phase",
            "workflow_evidence_sha256s",
            "workflow_id",
            "workflow_id_reuse_policy",
            "workflow_maximum_attempts",
            "workflow_sha256",
            "workflow_type",
        }
        if set(value) != fields:
            raise OccurrenceCompletionError(
                "Temporal terminal audit receipt schema is invalid"
            )
        if (
            value["schema_version"] != TEMPORAL_TERMINAL_RECEIPT_SCHEMA
            or value["claim_boundary"] != TEMPORAL_RECEIPT_CLAIM_BOUNDARY
        ):
            raise OccurrenceCompletionError(
                "Temporal terminal audit receipt profile is invalid"
            )
        if canonical_json(value).encode("utf-8") != raw:
            raise OccurrenceCompletionError(
                "Temporal terminal audit receipt must use canonical JSON bytes"
            )
        evidence = value["workflow_evidence_sha256s"]
        if type(evidence) is not list or not evidence:
            raise OccurrenceCompletionError(
                "Temporal terminal receipt requires workflow evidence"
            )
        for digest in evidence:
            _digest(digest, "Temporal workflow evidence")
        try:
            run_id = str(UUID(_bounded_text(value["run_id"], "Temporal run_id")))
        except ValueError as exc:
            raise OccurrenceCompletionError(
                "Temporal run_id must be a canonical UUID"
            ) from exc
        if run_id != value["run_id"]:
            raise OccurrenceCompletionError(
                "Temporal run_id must be a canonical lowercase UUID"
            )
        return cls(
            occurrence_uid=_bounded_text(value["occurrence_uid"], "occurrence_uid"),
            namespace=_bounded_text(value["namespace"], "Temporal namespace"),
            workflow_id=_bounded_text(value["workflow_id"], "Temporal workflow_id"),
            run_id=run_id,
            workflow_type=_bounded_text(value["workflow_type"], "workflow type"),
            terminal_phase=_bounded_text(value["terminal_phase"], "terminal phase"),
            candidate_receipt_sha256=_digest(
                value["candidate_receipt_sha256"], "candidate receipt"
            ),
            workflow_sha256=_digest(value["workflow_sha256"], "workflow"),
            workflow_evidence_sha256s=tuple(evidence),
            history_export_sha256=_digest(
                value["history_export_sha256"], "Temporal history export"
            ),
            history_event_count=_positive_integer(
                value["history_event_count"], "Temporal history event count"
            ),
            history_first_event_id=_positive_integer(
                value["history_first_event_id"], "Temporal first event id"
            ),
            history_last_event_id=_positive_integer(
                value["history_last_event_id"], "Temporal last event id"
            ),
            completed_at=_bounded_text(value["completed_at"], "completed_at"),
            workflow_id_reuse_policy=_bounded_text(
                value["workflow_id_reuse_policy"], "workflow reuse policy"
            ),
            workflow_maximum_attempts=_positive_integer(
                value["workflow_maximum_attempts"], "workflow maximum attempts"
            ),
            activity_maximum_attempts=_positive_integer(
                value["activity_maximum_attempts"], "activity maximum attempts"
            ),
            replacement_round_allowed=value["replacement_round_allowed"],
            signal_authorization_binding_sha256=_digest(
                value["signal_authorization_binding_sha256"],
                "Temporal signal authorization binding",
            ),
            server_identity_sha256=_digest(
                value["server_identity_sha256"], "Temporal server identity"
            ),
            exporter_identity=_bounded_text(
                value["exporter_identity"], "Temporal exporter identity"
            ),
        )


def _validate_temporal_terminal_material(
    *,
    receipt_bytes: bytes,
    history_bytes: bytes,
    candidate_receipt: OccurrenceCompletionReceiptV1,
    terminal_workflow: OccurrenceWorkflowStateV1,
    completion_started_at: str,
    completion_terminal_at: str,
) -> tuple[TemporalTerminalAuditReceiptV1, str]:
    history = TemporalHistoryExportV1.from_bytes(history_bytes)
    receipt = TemporalTerminalAuditReceiptV1.from_bytes(receipt_bytes)
    history_sha256 = sha256(history_bytes).hexdigest()
    if receipt.history_export_sha256 != history_sha256:
        raise OccurrenceCompletionError(
            "Temporal terminal receipt does not bind the history export"
        )
    if (
        receipt.occurrence_uid != terminal_workflow.occurrence_uid
        or receipt.workflow_id != f"g0-occurrence/{terminal_workflow.occurrence_uid}"
        or receipt.workflow_type != TEMPORAL_WORKFLOW_TYPE
        or receipt.terminal_phase != OccurrencePhase.SEALED.value
        or receipt.candidate_receipt_sha256 != candidate_receipt.receipt_sha256
        or receipt.workflow_sha256 != workflow_digest(terminal_workflow)
        or receipt.workflow_evidence_sha256s
        != terminal_workflow.evidence_sha256s
        or receipt.workflow_id_reuse_policy != "REJECT_DUPLICATE"
        or receipt.workflow_maximum_attempts != 1
        or receipt.activity_maximum_attempts != 1
        or receipt.replacement_round_allowed is not False
    ):
        raise OccurrenceCompletionError(
            "Temporal terminal receipt does not bind the exact one-shot workflow"
        )
    if (
        receipt.namespace != history.namespace
        or receipt.workflow_id != history.workflow_id
        or receipt.run_id != history.run_id
        or receipt.server_identity_sha256 != history.server_identity_sha256
        or receipt.signal_authorization_binding_sha256
        != history.signal_authorization_binding_sha256
        or receipt.history_event_count != len(history.events)
        or receipt.history_first_event_id != history.first_event_id
        or receipt.history_last_event_id != history.last_event_id
        or _time(receipt.completed_at, "Temporal receipt completed_at")
        != _time(history.completed_at, "Temporal history completed_at")
    ):
        raise OccurrenceCompletionError(
            "Temporal terminal receipt and history export disagree"
        )
    started = _time(completion_started_at, "completion_started_at")
    candidate_at = _time(candidate_receipt.terminal_at, "candidate terminal_at")
    workflow_started = _time(history.started_at, "Temporal history started_at")
    completed = _time(receipt.completed_at, "Temporal receipt completed_at")
    terminal = _time(completion_terminal_at, "completion_terminal_at")
    if not started <= workflow_started <= candidate_at <= completed <= terminal:
        raise OccurrenceCompletionError(
            "Temporal start/candidate/completion chronology is invalid"
        )
    return receipt, history_sha256


def verify_external_audit_material(
    *,
    candidate_receipt: OccurrenceCompletionReceiptV1,
    assessment: AssessmentV1,
    dual_evaluation: DualEvaluationAssessmentV1,
    terminal_workflow: OccurrenceWorkflowStateV1,
    material: ExternalAuditMaterialV1,
    completion_started_at: str,
    completion_terminal_at: str,
) -> ExternalAuditVerificationV1:
    """Run the fixed qualified Cosign verifier and return its bound record.

    The qualification path is repository-fixed.  Its current absent/BLOCKED
    record is a hard refusal; callers cannot select a substitute record.
    """
    if not isinstance(material, ExternalAuditMaterialV1):
        raise OccurrenceCompletionError("exact external audit material is required")
    if (
        not isinstance(candidate_receipt, OccurrenceCompletionReceiptV1)
        or candidate_receipt.terminal_status
        is not CompletionTerminal.PENDING_EXTERNAL_AUDIT
        or candidate_receipt.external_audit_verification_sha256 is not None
    ):
        raise OccurrenceCompletionError(
            "a pending-external-audit candidate receipt is required"
        )
    if not isinstance(assessment, AssessmentV1) or not isinstance(
        dual_evaluation, DualEvaluationAssessmentV1
    ):
        raise OccurrenceCompletionError("exact assessment values are required")
    if (
        not isinstance(terminal_workflow, OccurrenceWorkflowStateV1)
        or terminal_workflow.phase is not OccurrencePhase.SEALED
        or terminal_workflow.occurrence_uid != candidate_receipt.occurrence_uid
        or terminal_workflow.evidence_sha256s
        != (
            *candidate_receipt.workflow_evidence_sha256s,
            candidate_receipt.receipt_sha256,
        )
    ):
        raise OccurrenceCompletionError(
            "external audit requires the exact candidate-bound terminal workflow"
        )
    if (
        candidate_receipt.integrity_assessment_sha256
        != assessment_digest(assessment)
        or candidate_receipt.integrity_chain_sha256 != assessment.chain_digest
        or candidate_receipt.dual_evaluation_assessment_sha256
        != dual_assessment_digest(dual_evaluation)
        or candidate_receipt.dual_evaluation_evidence_sha256
        != dual_evaluation.evidence_sha256
        or candidate_receipt.workflow_evidence_sha256s
        != assessment.workflow_evidence_sha256s
    ):
        raise OccurrenceCompletionError(
            "candidate does not bind the supplied central and dual assessments"
        )

    _, raw = _bounded_bytes(
        _QUALIFICATION_RECORD,
        "external audit qualification record",
        _MAX_QUALIFICATION_BYTES,
    )
    record = _strict_json_object(raw, "external audit qualification record")
    if set(record) != {
        "schema_version",
        "status",
        "toolchain_candidates_sha256",
        "cosign",
        "trusted_root",
        "auditor",
        "qualification_receipt_sha256",
    }:
        raise OccurrenceCompletionError("external audit qualification schema is invalid")
    if (
        record["schema_version"]
        != "hswm-g0-external-audit-qualification/v1"
        or record["status"] != "QUALIFIED"
    ):
        raise OccurrenceCompletionError("external audit verifier is not qualified")
    try:
        toolchain_sha256 = sha256(_TOOLCHAIN_CANDIDATES.read_bytes()).hexdigest()
    except OSError as exc:
        raise OccurrenceCompletionError(
            "toolchain candidates record is unavailable"
        ) from exc
    if (
        record["toolchain_candidates_sha256"] != toolchain_sha256
        or not isinstance(record["qualification_receipt_sha256"], str)
    ):
        raise OccurrenceCompletionError("qualification toolchain or receipt binding is invalid")
    _digest(record["qualification_receipt_sha256"], "qualification receipt sha256")
    if not all(isinstance(record[key], dict) for key in ("cosign", "trusted_root", "auditor")):
        raise OccurrenceCompletionError("external audit qualification schema is invalid")
    cosign, root, auditor = record["cosign"], record["trusted_root"], record["auditor"]
    if (
        set(cosign)
        != {
            "path",
            "sha256",
            "exact_version_output",
            "version",
            "source_commit",
            "license_path",
            "license_sha256",
        }
        or set(root) != {"path", "sha256"}
        or set(auditor) != {"identity", "issuer"}
    ):
        raise OccurrenceCompletionError("external audit qualification fields are invalid")
    if (
        cosign.get("version") != "3.1.3"
        or cosign.get("source_commit")
        != "11926fa5bbbbde47e88fc006b625a17769b743b2"
        or not all(isinstance(cosign[key], str) and cosign[key] for key in cosign)
        or not all(isinstance(root[key], str) and root[key] for key in root)
        or not all(isinstance(auditor[key], str) and auditor[key] for key in auditor)
    ):
        raise OccurrenceCompletionError("external audit qualification values are invalid")
    _digest(cosign["sha256"], "qualified cosign sha256")
    _digest(cosign["license_sha256"], "qualified cosign license sha256")
    _digest(root["sha256"], "qualified trusted root sha256")
    executable = Path(cosign["path"])
    trusted_root = Path(root["path"])
    license_path = Path(cosign["license_path"])
    if not all(path.is_absolute() for path in (executable, trusted_root, license_path)):
        raise OccurrenceCompletionError("qualified artifact paths must be absolute")
    trusted_root, trusted_root_bytes = _bounded_bytes(
        trusted_root, "qualified Sigstore trusted root", _MAX_AUDIT_INPUT_BYTES
    )
    _, license_bytes = _bounded_bytes(
        license_path, "qualified Cosign license", _MAX_AUDIT_INPUT_BYTES
    )
    if sha256(trusted_root_bytes).hexdigest() != root["sha256"]:
        raise OccurrenceCompletionError("qualified trusted root SHA-256 mismatch")
    if sha256(license_bytes).hexdigest() != cosign["license_sha256"]:
        raise OccurrenceCompletionError("qualified Cosign license SHA-256 mismatch")

    attestation_blob, attestation_bytes = _bounded_bytes(
        material.audit_manifest,
        "external audit manifest",
        _MAX_AUDIT_INPUT_BYTES,
    )
    bundle, bundle_bytes = _bounded_bytes(
        material.cosign_bundle,
        "external audit Cosign bundle",
        _MAX_AUDIT_INPUT_BYTES,
    )
    _, temporal_terminal_receipt_bytes = _bounded_bytes(
        material.temporal_terminal_receipt,
        "Temporal terminal execution receipt",
        _MAX_AUDIT_INPUT_BYTES,
    )
    _, temporal_history_export_bytes = _bounded_bytes(
        material.temporal_history_export,
        "Temporal complete history export",
        _MAX_AUDIT_INPUT_BYTES,
    )
    qualification_sha256 = sha256(raw).hexdigest()
    terminal_workflow_sha256 = workflow_digest(terminal_workflow)
    temporal_terminal_receipt_sha256 = sha256(
        temporal_terminal_receipt_bytes
    ).hexdigest()
    _, temporal_history_export_sha256 = _validate_temporal_terminal_material(
        receipt_bytes=temporal_terminal_receipt_bytes,
        history_bytes=temporal_history_export_bytes,
        candidate_receipt=candidate_receipt,
        terminal_workflow=terminal_workflow,
        completion_started_at=completion_started_at,
        completion_terminal_at=completion_terminal_at,
    )
    signed_fields = {
        "assessment_chain_sha256": assessment.chain_digest,
        "assessment_sha256": assessment_digest(assessment),
        "auditor_identity": auditor["identity"],
        "auditor_issuer": auditor["issuer"],
        "candidate_receipt_sha256": candidate_receipt.receipt_sha256,
        "candidate_workflow_evidence_sha256s": list(
            candidate_receipt.workflow_evidence_sha256s
        ),
        "candidate_workflow_sha256": candidate_receipt.workflow_sha256,
        "claim_boundary": CLAIM_CEILING,
        "completion_started_at": completion_started_at,
        "completion_terminal_at": completion_terminal_at,
        "cosign_license_sha256": cosign["license_sha256"],
        "cosign_sha256": cosign["sha256"],
        "dual_assessment_sha256": dual_assessment_digest(dual_evaluation),
        "dual_evidence_sha256": dual_evaluation.evidence_sha256,
        "qualification_receipt_sha256": record[
            "qualification_receipt_sha256"
        ],
        "qualification_sha256": qualification_sha256,
        "schema_version": "hswm-external-completion-audit-manifest/v1",
        "temporal_history_export_sha256": temporal_history_export_sha256,
        "temporal_terminal_receipt_sha256": temporal_terminal_receipt_sha256,
        "terminal_workflow_evidence_sha256s": list(
            terminal_workflow.evidence_sha256s
        ),
        "terminal_workflow_sha256": terminal_workflow_sha256,
        "trusted_root_sha256": root["sha256"],
    }
    expected_attestation_bytes = canonical_json(signed_fields).encode("utf-8")
    if attestation_bytes != expected_attestation_bytes:
        raise OccurrenceCompletionError(
            "signed external audit manifest does not exactly bind the candidate"
        )
    audit_manifest_sha256 = sha256(attestation_bytes).hexdigest()
    audit_bundle_sha256 = sha256(bundle_bytes).hexdigest()
    argv = cosign_verify_blob_attestation_artifact_argv(
        cosign=str(executable.resolve()),
        blob=attestation_blob,
        bundle=bundle,
        trusted_root=trusted_root,
        identity=auditor["identity"],
        issuer=auditor["issuer"],
    )
    result = verify_with_pinned_binary(
        argv=argv,
        executable=executable,
        executable_sha256=cosign["sha256"],
        expected_version_text=cosign["exact_version_output"],
        pinned_inputs={
            attestation_blob: audit_manifest_sha256,
            bundle: audit_bundle_sha256,
            trusted_root: root["sha256"],
        },
    )
    if not result.ran or not result.verified:
        raise OccurrenceCompletionError("qualified external audit verification did not succeed")
    if result.stdout_sha256 is None or result.stderr_sha256 is None:
        raise OccurrenceCompletionError("verifier output digests are absent")
    verification_fields = {
        "assessment_chain_sha256": assessment.chain_digest,
        "assessment_sha256": assessment_digest(assessment),
        "audit_bundle_sha256": audit_bundle_sha256,
        "audit_manifest_sha256": audit_manifest_sha256,
        "auditor_identity": auditor["identity"],
        "auditor_issuer": auditor["issuer"],
        "candidate_receipt_sha256": candidate_receipt.receipt_sha256,
        "candidate_workflow_evidence_sha256s": (
            candidate_receipt.workflow_evidence_sha256s
        ),
        "candidate_workflow_sha256": candidate_receipt.workflow_sha256,
        "completion_started_at": completion_started_at,
        "completion_terminal_at": completion_terminal_at,
        "cosign_license_sha256": cosign["license_sha256"],
        "cosign_sha256": cosign["sha256"],
        "dual_assessment_sha256": dual_assessment_digest(dual_evaluation),
        "dual_evidence_sha256": dual_evaluation.evidence_sha256,
        "qualification_receipt_sha256": record[
            "qualification_receipt_sha256"
        ],
        "qualification_sha256": qualification_sha256,
        "temporal_history_export_sha256": temporal_history_export_sha256,
        "temporal_terminal_receipt_sha256": temporal_terminal_receipt_sha256,
        "terminal_workflow_evidence_sha256s": (
            terminal_workflow.evidence_sha256s
        ),
        "terminal_workflow_sha256": terminal_workflow_sha256,
        "trusted_root_sha256": root["sha256"],
        "verification_stderr_sha256": result.stderr_sha256,
        "verification_stdout_sha256": result.stdout_sha256,
    }
    verification_payload = {
        **verification_fields,
        "candidate_workflow_evidence_sha256s": list(
            candidate_receipt.workflow_evidence_sha256s
        ),
        "terminal_workflow_evidence_sha256s": list(
            terminal_workflow.evidence_sha256s
        ),
        "schema_version": "hswm-external-audit-verification/v1",
    }
    return ExternalAuditVerificationV1(
        **verification_fields,
        verification_sha256=canonical_sha256(verification_payload),
        _construction_token=_AUDIT_VERIFICATION_CONSTRUCTION_TOKEN,
    )


def complete_occurrence(
    *,
    assessment: AssessmentV1,
    workflow: OccurrenceWorkflowStateV1,
    dual_evaluation: DualEvaluationAssessmentV1 | None,
    judgment_a: InspectJudgmentAV1 | None,
    judgment_b: IndependentJudgmentBV1 | None,
    started_at: str,
    terminal_at: str,
    candidate_receipt: OccurrenceCompletionReceiptV1 | None = None,
    external_audit_material: ExternalAuditMaterialV1 | None = None,
    previous_receipt: OccurrenceCompletionReceiptV1 | None = None,
) -> OccurrenceCompletionReceiptV1:
    """Compose one immutable completion receipt, failing closed.

    ``previous_receipt`` provides idempotent terminal replay. A
    ``PENDING_EXTERNAL_AUDIT`` receipt is intentionally not accepted there: it must be
    followed by an exact Temporal ``SEALED`` transition first.
    """

    if not isinstance(assessment, AssessmentV1) or not isinstance(
        workflow, OccurrenceWorkflowStateV1
    ):
        raise OccurrenceCompletionError("exact assessment/workflow values are required")
    if _time(terminal_at, "terminal_at") < _time(started_at, "started_at"):
        raise OccurrenceCompletionError("terminal_at precedes started_at")

    if previous_receipt is not None:
        if (
            not isinstance(previous_receipt, OccurrenceCompletionReceiptV1)
            or previous_receipt.occurrence_uid != workflow.occurrence_uid
        ):
            raise OccurrenceCompletionError("previous terminal receipt mismatch")
        if previous_receipt.terminal_status not in {
            CompletionTerminal.SEALED,
            CompletionTerminal.VOID,
        }:
            raise OccurrenceCompletionError(
                "only final SEALED or VOID receipts are immutable prior receipts"
            )
        recomputed = complete_occurrence(
            assessment=assessment,
            workflow=workflow,
            dual_evaluation=dual_evaluation,
            judgment_a=judgment_a,
            judgment_b=judgment_b,
            started_at=started_at,
            terminal_at=terminal_at,
            candidate_receipt=candidate_receipt,
            external_audit_material=external_audit_material,
            previous_receipt=None,
        )
        if recomputed.canonical() != previous_receipt.canonical():
            raise OccurrenceCompletionError("previous receipt does not match fresh completion inputs")
        return previous_receipt

    actual_dual = assess_dual_evaluation(judgment_a, judgment_b)
    dual_matches = (
        dual_evaluation is not None
        and dual_evaluation.canonical() == actual_dual.canonical()
    )

    if workflow.phase is OccurrencePhase.VOID:
        return _receipt(
            status=CompletionTerminal.VOID,
            reason="one-shot workflow became VOID",
            assessment=assessment,
            workflow=workflow,
            dual_evaluation=dual_evaluation,
            started_at=started_at,
            terminal_at=terminal_at,
        )
    if assessment.terminal in _INTEGRITY_VOID_TERMINALS:
        return _receipt(
            status=CompletionTerminal.VOID,
            reason=f"central integrity: {assessment.terminal.value}",
            assessment=assessment,
            workflow=workflow,
            dual_evaluation=dual_evaluation,
            started_at=started_at,
            terminal_at=terminal_at,
        )
    if (
        dual_evaluation is not None
        and dual_evaluation.terminal in _DUAL_VOID_TERMINALS
    ):
        return _receipt(
            status=CompletionTerminal.VOID,
            reason=f"dual evaluation: {dual_evaluation.terminal.value}",
            assessment=assessment,
            workflow=workflow,
            dual_evaluation=dual_evaluation,
            started_at=started_at,
            terminal_at=terminal_at,
        )

    blocked_reason: str | None = None
    if assessment.terminal is not Terminal.CANDIDATE_REQUIRES_EXTERNAL_AUDIT:
        blocked_reason = "central integrity lacks an external-audit candidate"
    elif workflow.phase not in {
        OccurrencePhase.DUAL_EVALUATED,
        OccurrencePhase.SEALED,
    }:
        blocked_reason = "workflow is not at an exact completion phase"
    elif not assessment.workflow_evidence_sha256s:
        blocked_reason = "central integrity lacks a workflow evidence projection"
    elif (
        workflow.phase is OccurrencePhase.DUAL_EVALUATED
        and workflow.evidence_sha256s != assessment.workflow_evidence_sha256s
    ):
        blocked_reason = "workflow history does not match the central integrity chain"
    elif (
        workflow.phase is OccurrencePhase.SEALED
        and workflow.evidence_sha256s[:-1]
        != assessment.workflow_evidence_sha256s
    ):
        blocked_reason = "terminal workflow prefix does not match central integrity"
    elif (
        not dual_matches
        or dual_evaluation is None
        or dual_evaluation.terminal
        is not DualEvaluationTerminal.SEALED_CANDIDATE_REQUIRES_EXTERNAL_SIGNATURE_AUDIT
    ):
        blocked_reason = (
            "A/B agreement candidate is absent, unverified, or not reproducible"
        )
    elif (
        assessment.dual_evaluation_evidence_sha256
        != dual_evaluation.evidence_sha256
    ):
        blocked_reason = (
            "central integrity bridge does not bind dual-evaluation evidence"
        )
    elif assessment.dual_evaluation_binding_sha256 != dual_evaluation.binding_sha256:
        blocked_reason = "central and dual evaluator normalized bindings do not match"
    elif (
        judgment_a is None
        or judgment_b is None
        or judgment_a.occurrence_uid != workflow.occurrence_uid
        or judgment_b.occurrence_uid != workflow.occurrence_uid
    ):
        blocked_reason = "judgments do not bind the workflow occurrence UID"

    if blocked_reason is not None:
        return _receipt(
            status=CompletionTerminal.BLOCKED,
            reason=blocked_reason,
            assessment=assessment,
            workflow=workflow,
            dual_evaluation=dual_evaluation,
            started_at=started_at,
            terminal_at=terminal_at,
        )

    assert dual_evaluation is not None
    if workflow.phase is OccurrencePhase.DUAL_EVALUATED:
        if candidate_receipt is not None or external_audit_material is not None:
            return _receipt(
                status=CompletionTerminal.BLOCKED,
                reason="finalization input was supplied before candidate issuance",
                assessment=assessment,
                workflow=workflow,
                dual_evaluation=dual_evaluation,
                started_at=started_at,
                terminal_at=terminal_at,
            )
        return _receipt(
            status=CompletionTerminal.PENDING_EXTERNAL_AUDIT,
            reason=PENDING_EXTERNAL_AUDIT_REASON,
            assessment=assessment,
            workflow=workflow,
            dual_evaluation=dual_evaluation,
            started_at=started_at,
            terminal_at=terminal_at,
        )

    if candidate_receipt is None or not isinstance(
        candidate_receipt, OccurrenceCompletionReceiptV1
    ):
        blocked_reason = "Temporal SEALED lacks the pending audit candidate receipt"
    elif (
        candidate_receipt.occurrence_uid != workflow.occurrence_uid
        or candidate_receipt.terminal_status is not CompletionTerminal.PENDING_EXTERNAL_AUDIT
        or candidate_receipt.reason != PENDING_EXTERNAL_AUDIT_REASON
        or candidate_receipt.started_at != started_at
        or candidate_receipt.integrity_assessment_sha256
        != assessment_digest(assessment)
        or candidate_receipt.integrity_chain_sha256 != assessment.chain_digest
        or candidate_receipt.dual_evaluation_assessment_sha256
        != dual_assessment_digest(dual_evaluation)
        or candidate_receipt.dual_evaluation_evidence_sha256
        != dual_evaluation.evidence_sha256
        or workflow.evidence_sha256s
        != (*candidate_receipt.workflow_evidence_sha256s, candidate_receipt.receipt_sha256)
    ):
        blocked_reason = (
            "Temporal SEALED does not exactly extend the pending audit candidate"
        )
    elif _time(candidate_receipt.terminal_at, "candidate terminal_at") > _time(
        terminal_at, "terminal_at"
    ):
        blocked_reason = "Temporal finalization predates the pending audit candidate"

    if blocked_reason is not None:
        return _receipt(
            status=CompletionTerminal.BLOCKED,
            reason=blocked_reason,
            assessment=assessment,
            workflow=workflow,
            dual_evaluation=dual_evaluation,
            started_at=started_at,
            terminal_at=terminal_at,
        )
    if not isinstance(external_audit_material, ExternalAuditMaterialV1):
        return _receipt(
            status=CompletionTerminal.BLOCKED,
            reason="qualified external audit material is absent",
            assessment=assessment,
            workflow=workflow,
            dual_evaluation=dual_evaluation,
            started_at=started_at,
            terminal_at=terminal_at,
        )
    try:
        external_audit_verification = verify_external_audit_material(
            candidate_receipt=candidate_receipt,
            assessment=assessment,
            dual_evaluation=dual_evaluation,
            terminal_workflow=workflow,
            material=external_audit_material,
            completion_started_at=started_at,
            completion_terminal_at=terminal_at,
        )
    except OccurrenceCompletionError:
        return _receipt(
            status=CompletionTerminal.BLOCKED,
            reason=(
                "qualified external audit verification failed or did not bind "
                "the candidate and terminal workflow"
            ),
            assessment=assessment,
            workflow=workflow,
            dual_evaluation=dual_evaluation,
            started_at=started_at,
            terminal_at=terminal_at,
        )
    return _receipt(
        status=CompletionTerminal.SEALED,
        reason=(
            "qualified Cosign verification binds the signed external audit "
            "manifest to the candidate and exact Temporal finalization"
        ),
        assessment=assessment,
        workflow=workflow,
        dual_evaluation=dual_evaluation,
        started_at=started_at,
        terminal_at=terminal_at,
        external_audit_verification=external_audit_verification,
    )


@dataclass(frozen=True, slots=True)
class OccurrenceCompletionReplayV1:
    """All inputs needed to recompute a receipt at a publication boundary.

    This carrier is not an authorization token.  Consumers must call
    :func:`replay_completion` and compare the freshly recomputed canonical
    receipt; a caller-created receipt or carrier has no authority by itself.
    """

    assessment: AssessmentV1
    workflow: OccurrenceWorkflowStateV1
    dual_evaluation: DualEvaluationAssessmentV1 | None
    judgment_a: InspectJudgmentAV1 | None
    judgment_b: IndependentJudgmentBV1 | None
    started_at: str
    terminal_at: str
    candidate_receipt: OccurrenceCompletionReceiptV1 | None = None
    external_audit_material: ExternalAuditMaterialV1 | None = None


def replay_completion(
    replay: OccurrenceCompletionReplayV1,
) -> OccurrenceCompletionReceiptV1:
    """Recompute a receipt without trusting a serialized or in-process claim."""

    if not isinstance(replay, OccurrenceCompletionReplayV1):
        raise OccurrenceCompletionError("exact completion replay inputs are required")
    return complete_occurrence(
        assessment=replay.assessment,
        workflow=replay.workflow,
        dual_evaluation=replay.dual_evaluation,
        judgment_a=replay.judgment_a,
        judgment_b=replay.judgment_b,
        started_at=replay.started_at,
        terminal_at=replay.terminal_at,
        candidate_receipt=replay.candidate_receipt,
        external_audit_material=replay.external_audit_material,
        previous_receipt=None,
    )


def publication_eligible(
    receipt: OccurrenceCompletionReceiptV1,
    *,
    replay: OccurrenceCompletionReplayV1,
) -> bool:
    """Return true only when fresh verification reproduces a SEALED receipt."""

    if not isinstance(receipt, OccurrenceCompletionReceiptV1):
        raise OccurrenceCompletionError("exact completion receipt is required")
    recomputed = replay_completion(replay)
    return (
        recomputed.canonical() == receipt.canonical()
        and recomputed.terminal_status is CompletionTerminal.SEALED
    )


__all__ = [
    "CLAIM_CEILING",
    "PENDING_EXTERNAL_AUDIT_REASON",
    "SCHEMA",
    "CompletionTerminal",
    "ExternalAuditMaterialV1",
    "ExternalAuditVerificationV1",
    "OccurrenceCompletionError",
    "OccurrenceCompletionReplayV1",
    "OccurrenceCompletionReceiptV1",
    "TEMPORAL_HISTORY_EXPORT_SCHEMA",
    "TEMPORAL_HISTORY_SOURCE_API",
    "TEMPORAL_RECEIPT_CLAIM_BOUNDARY",
    "TEMPORAL_TERMINAL_RECEIPT_SCHEMA",
    "TEMPORAL_WORKFLOW_TYPE",
    "TemporalHistoryExportV1",
    "TemporalTerminalAuditReceiptV1",
    "assessment_digest",
    "complete_occurrence",
    "dual_assessment_digest",
    "publication_eligible",
    "replay_completion",
    "verify_external_audit_material",
    "workflow_digest",
]
