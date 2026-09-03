"""Deterministic one-shot G0 occurrence workflow contract.

This is deliberately an adapter-neutral state machine: it does not import a
Temporal SDK, execute a workflow, claim a UID, or write evidence.  An external
WORM conditional-create becomes a singleton boundary only after independent
versioning, policy, retention, and no-delete audit.  The launch options merely
tell an external workflow adapter how it must be configured after a candidate
claim succeeds.

Neither this workflow history nor its terminal state is outcome truth, a
Permit, causal credit, canonical admission, or learning evidence.
"""
from __future__ import annotations

from dataclasses import InitVar, dataclass
from enum import StrEnum
import re
from typing import Mapping


WORKFLOW_SCHEMA = "hswm-g0-occurrence-one-shot-workflow/v1"
LAUNCH_OPTIONS_SCHEMA = "hswm-g0-occurrence-temporal-launch-options/v1"
WORKFLOW_ID_PREFIX = "g0-occurrence/"
CLAIM_BOUNDARY = (
    "WORM conditional create is only a singleton candidate until independent policy/version/no-delete audit; Temporal configuration "
    "is one-shot orchestration only and its SEALED phase is not publication eligibility, outcome truth, Permit, causal credit, "
    "canonical admission, or learning; Temporal signal sender authorization is "
    "an external deployment policy and is neither implemented nor proven by "
    "this adapter-neutral state machine"
)
_UID = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_STATE_CONSTRUCTION_TOKEN = object()


class OccurrencePhase(StrEnum):
    REGISTERED = "REGISTERED"
    CLAIMED = "CLAIMED"
    SCHEDULED = "SCHEDULED"
    PRE_PULSE_SEALED = "PRE_PULSE_SEALED"
    PULSE_VERIFIED = "PULSE_VERIFIED"
    REVEALED = "REVEALED"
    DUAL_EVALUATED = "DUAL_EVALUATED"
    SEALED = "SEALED"
    VOID = "VOID"


class PulseTiming(StrEnum):
    """Externally established relation of an event to the committed pulse."""

    PRE_PULSE = "PRE_PULSE"
    POST_PULSE = "POST_PULSE"


class VoidReason(StrEnum):
    DUPLICATE_OR_RETRY = "DUPLICATE_OR_RETRY"
    LATE = "LATE"
    ORDER = "ORDER"
    INVALID_EVIDENCE_DESCRIPTOR = "INVALID_EVIDENCE_DESCRIPTOR"
    TERMINAL_REENTRY = "TERMINAL_REENTRY"


_NEXT: Mapping[OccurrencePhase, OccurrencePhase] = {
    OccurrencePhase.REGISTERED: OccurrencePhase.CLAIMED,
    OccurrencePhase.CLAIMED: OccurrencePhase.SCHEDULED,
    OccurrencePhase.SCHEDULED: OccurrencePhase.PRE_PULSE_SEALED,
    OccurrencePhase.PRE_PULSE_SEALED: OccurrencePhase.PULSE_VERIFIED,
    OccurrencePhase.PULSE_VERIFIED: OccurrencePhase.REVEALED,
    OccurrencePhase.REVEALED: OccurrencePhase.DUAL_EVALUATED,
    OccurrencePhase.DUAL_EVALUATED: OccurrencePhase.SEALED,
}


@dataclass(frozen=True, slots=True)
class TemporalOneShotLaunchOptionsV1:
    """Exact, SDK-independent projection for a Temporal-like external adapter."""

    occurrence_uid: str
    workflow_id: str
    workflow_id_reuse_policy: str
    workflow_maximum_attempts: int
    activity_maximum_attempts: int
    replacement_round_allowed: bool
    schema_version: str = LAUNCH_OPTIONS_SCHEMA

    def as_external_adapter_options(self) -> dict[str, object]:
        """Return only the exact fields an adapter must preserve."""

        return {
            "activity_retry_policy": {"maximum_attempts": self.activity_maximum_attempts},
            "occurrence_uid": self.occurrence_uid,
            "replacement_round_allowed": self.replacement_round_allowed,
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "workflow_id_reuse_policy": self.workflow_id_reuse_policy,
            "workflow_retry_policy": {"maximum_attempts": self.workflow_maximum_attempts},
        }


def temporal_one_shot_launch_options(
    occurrence_uid: str,
) -> TemporalOneShotLaunchOptionsV1:
    """Project the only permitted external orchestration options for an occurrence."""

    _require_uid(occurrence_uid)
    return TemporalOneShotLaunchOptionsV1(
        occurrence_uid=occurrence_uid,
        workflow_id=f"{WORKFLOW_ID_PREFIX}{occurrence_uid}",
        workflow_id_reuse_policy="REJECT_DUPLICATE",
        workflow_maximum_attempts=1,
        activity_maximum_attempts=1,
        replacement_round_allowed=False,
    )


@dataclass(frozen=True, slots=True)
class OccurrenceWorkflowStateV1:
    """Immutable state; each non-VOID transition is bound to one receipt digest."""

    occurrence_uid: str
    phase: OccurrencePhase
    evidence_sha256s: tuple[str, ...]
    void_reason: VoidReason | None = None
    rejected_evidence_sha256: str | None = None
    schema_version: str = WORKFLOW_SCHEMA
    _construction_token: InitVar[object | None] = None

    def __post_init__(self, _construction_token: object | None) -> None:
        _require_uid(self.occurrence_uid)
        if not isinstance(self.phase, OccurrencePhase):
            raise ValueError("phase must be OccurrencePhase")
        if self.schema_version != WORKFLOW_SCHEMA:
            raise ValueError("unsupported occurrence workflow schema")
        if any(_SHA256.fullmatch(item) is None for item in self.evidence_sha256s):
            raise ValueError("evidence_sha256s must contain lowercase SHA-256 values")
        if self.phase is OccurrencePhase.VOID:
            if not isinstance(self.void_reason, VoidReason):
                raise ValueError("VOID state requires a VoidReason")
            if (
                self.rejected_evidence_sha256 is not None
                and _SHA256.fullmatch(self.rejected_evidence_sha256) is None
            ):
                raise ValueError("rejected evidence must be lowercase SHA-256")
        elif self.void_reason is not None:
            raise ValueError("non-VOID state cannot have a void reason")
        elif self.rejected_evidence_sha256 is not None:
            raise ValueError("non-VOID state cannot have rejected evidence")
        if _construction_token is not _STATE_CONSTRUCTION_TOKEN:
            raise ValueError(
                "workflow states must be constructed by registered_occurrence "
                "or advance_occurrence"
            )

    @property
    def terminal(self) -> bool:
        return self.phase in {OccurrencePhase.SEALED, OccurrencePhase.VOID}


def registered_occurrence(
    *, occurrence_uid: str, registration_evidence_sha256: str
) -> OccurrenceWorkflowStateV1:
    """Begin only after externally registered protocol bytes have been verified."""

    _require_uid(occurrence_uid)
    _require_sha256(registration_evidence_sha256)
    return OccurrenceWorkflowStateV1(
        occurrence_uid=occurrence_uid,
        phase=OccurrencePhase.REGISTERED,
        evidence_sha256s=(registration_evidence_sha256,),
        _construction_token=_STATE_CONSTRUCTION_TOKEN,
    )


def advance_occurrence(
    state: OccurrenceWorkflowStateV1,
    *,
    next_phase: OccurrencePhase,
    evidence_sha256: str,
    timing: PulseTiming,
) -> OccurrenceWorkflowStateV1:
    """Advance exactly once, or fail closed to terminal ``VOID``.

    ``timing`` must originate in the external sealed-event/custodian boundary;
    this pure contract does not treat a caller clock as independent evidence.
    """

    if not isinstance(state, OccurrenceWorkflowStateV1):
        raise TypeError("state must be OccurrenceWorkflowStateV1")
    if not isinstance(next_phase, OccurrencePhase) or not isinstance(timing, PulseTiming):
        return _void(state, VoidReason.ORDER, evidence_sha256)
    if state.terminal:
        if state.phase is OccurrencePhase.VOID:
            return state
        return _void(state, VoidReason.TERMINAL_REENTRY, evidence_sha256)
    if _SHA256.fullmatch(evidence_sha256) is None:
        return _void(state, VoidReason.INVALID_EVIDENCE_DESCRIPTOR)
    if evidence_sha256 in state.evidence_sha256s:
        return _void(state, VoidReason.DUPLICATE_OR_RETRY, evidence_sha256)
    expected = _NEXT[state.phase]
    if next_phase is state.phase:
        return _void(state, VoidReason.DUPLICATE_OR_RETRY, evidence_sha256)
    if next_phase is not expected:
        return _void(state, VoidReason.ORDER, evidence_sha256)
    required_timing = (
        PulseTiming.PRE_PULSE
        if next_phase is OccurrencePhase.PRE_PULSE_SEALED
        else PulseTiming.POST_PULSE
        if next_phase
        in {
            OccurrencePhase.PULSE_VERIFIED,
            OccurrencePhase.REVEALED,
            OccurrencePhase.DUAL_EVALUATED,
            OccurrencePhase.SEALED,
        }
        else PulseTiming.PRE_PULSE
    )
    if timing is not required_timing:
        return _void(state, VoidReason.LATE, evidence_sha256)
    return OccurrenceWorkflowStateV1(
        occurrence_uid=state.occurrence_uid,
        phase=next_phase,
        evidence_sha256s=(*state.evidence_sha256s, evidence_sha256),
        _construction_token=_STATE_CONSTRUCTION_TOKEN,
    )


def void_occurrence(
    state: OccurrenceWorkflowStateV1,
    *,
    reason: VoidReason,
    rejected_evidence_sha256: str | None = None,
) -> OccurrenceWorkflowStateV1:
    """Record an explicit orchestration failure as an immutable VOID state."""

    if not isinstance(state, OccurrenceWorkflowStateV1):
        raise TypeError("state must be OccurrenceWorkflowStateV1")
    if not isinstance(reason, VoidReason):
        raise TypeError("reason must be VoidReason")
    if state.phase is OccurrencePhase.VOID:
        return state
    return _void(state, reason, rejected_evidence_sha256)


def _void(
    state: OccurrenceWorkflowStateV1,
    reason: VoidReason,
    rejected_evidence_sha256: str | None = None,
) -> OccurrenceWorkflowStateV1:
    rejected = (
        rejected_evidence_sha256
        if isinstance(rejected_evidence_sha256, str)
        and _SHA256.fullmatch(rejected_evidence_sha256)
        else None
    )
    return OccurrenceWorkflowStateV1(
        occurrence_uid=state.occurrence_uid,
        phase=OccurrencePhase.VOID,
        evidence_sha256s=state.evidence_sha256s,
        void_reason=reason,
        rejected_evidence_sha256=rejected,
        _construction_token=_STATE_CONSTRUCTION_TOKEN,
    )


def _require_uid(value: str) -> None:
    if not isinstance(value, str) or _UID.fullmatch(value) is None:
        raise ValueError("occurrence_uid must be a bounded stable identifier")


def _require_sha256(value: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError("evidence descriptor must be lowercase SHA-256")


__all__ = [
    "CLAIM_BOUNDARY",
    "LAUNCH_OPTIONS_SCHEMA",
    "OccurrencePhase",
    "OccurrenceWorkflowStateV1",
    "PulseTiming",
    "TemporalOneShotLaunchOptionsV1",
    "VoidReason",
    "WORKFLOW_ID_PREFIX",
    "WORKFLOW_SCHEMA",
    "advance_occurrence",
    "registered_occurrence",
    "temporal_one_shot_launch_options",
    "void_occurrence",
]
