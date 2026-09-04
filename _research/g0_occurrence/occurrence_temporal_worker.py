# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "temporalio==1.32.0",
# ]
# ///
"""Retired Python reference adapter for a candidate G0 occurrence.

This module is an orchestration boundary, not a singleton authority.  An
externally verified WORM conditional-create receipt must exist before a
workflow can be started; Temporal's duplicate policy is only a second line of
defence.  It does not create a WORM claim, contact OSF/Sigstore/drand, reveal
materials, evaluate an outcome, or establish any G0 result.

Running this file without ``--serve`` only emits a redacted historical dry-run
plan.  Live ``serve`` and ``start_one_shot`` entrypoints now refuse: the
TypeScript/Effect package subpath ``@hswm/effect-runtime/g0-temporal`` is the
single selected future execution implementation.  Its live external admission
is still fail-closed.  The Python code remains checked
in as a parity oracle and historical reference; it never logs credentials.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from datetime import timedelta
import re
from typing import Any, Mapping, Sequence

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy
from temporalio.worker import Worker

# ``uv run --script`` creates an isolated environment rather than installing
# this repository.  Resolve the checked-out source tree only for that explicit
# script invocation; a normal package import already has ``hswm`` available.
_REPOSITORY_SRC = Path(__file__).resolve().parents[2] / "src"
if _REPOSITORY_SRC.is_dir() and str(_REPOSITORY_SRC) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_SRC))

from hswm.infrastructure.occurrence_workflow import (
    CLAIM_BOUNDARY,
    OccurrencePhase,
    OccurrenceWorkflowStateV1,
    PulseTiming,
    VoidReason,
    advance_occurrence,
    registered_occurrence,
    temporal_one_shot_launch_options,
    void_occurrence,
)


WORKER_SCHEMA = "hswm-g0-occurrence-temporal-worker/v1"
WORKFLOW_NAME = "hswm_g0_occurrence_one_shot_workflow"
ACTIVITY_NAME = "hswm_g0_occurrence_validate_transition"
DEFAULT_TASK_QUEUE = "hswm-g0-occurrence-one-shot"
_DESCRIPTOR_MEDIA_TYPE = "application/vnd.hswm.content-descriptor+json"
RECEIPT_FINALIZATION_GRACE_SECONDS = 60
MAX_PENDING_SIGNALS = 8
MAX_INPUT_JSON_BYTES = 65_536
PYTHON_WORKER_STATUS = "RETIRED_REFERENCE_ONLY_TYPESCRIPT_EXECUTION_SELECTED"
_DESCRIPTOR_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
SIGNAL_AUTHORIZATION_CLAIM_BOUNDARY = (
    "Temporal signal sender authorization is an external namespace, transport, "
    "and deployment policy. This worker receives no sender identity and does "
    "not authenticate or prove authorization of a signal."
)


@dataclass(frozen=True, slots=True)
class ContentDescriptorV1:
    """A typed reference, never material bytes or credentials."""

    name: str
    sha256: str
    media_type: str = _DESCRIPTOR_MEDIA_TYPE

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _DESCRIPTOR_NAME.fullmatch(self.name) is None:
            raise ValueError("descriptor name must be bounded lowercase snake case")
        if not isinstance(self.sha256, str) or len(self.sha256) != 64:
            raise ValueError("descriptor sha256 must be a SHA-256 value")
        if any(char not in "0123456789abcdef" for char in self.sha256):
            raise ValueError("descriptor sha256 must be lowercase hexadecimal")
        if self.media_type != _DESCRIPTOR_MEDIA_TYPE:
            raise ValueError("unsupported descriptor media type")


@dataclass(frozen=True, slots=True)
class PhaseTransitionV1:
    """One pre-built evidence transition; it contains no actor material."""

    next_phase: str
    evidence: ContentDescriptorV1
    timing: str

    def __post_init__(self) -> None:
        if not isinstance(self.next_phase, str) or not isinstance(self.timing, str):
            raise ValueError("transition phase and timing must be strings")
        if not isinstance(self.evidence, ContentDescriptorV1):
            raise ValueError("transition evidence must be a content descriptor")

    def phase(self) -> OccurrencePhase:
        try:
            return OccurrencePhase(self.next_phase)
        except ValueError as exc:
            raise ValueError("transition next_phase is unsupported") from exc

    def pulse_timing(self) -> PulseTiming:
        try:
            return PulseTiming(self.timing)
        except ValueError as exc:
            raise ValueError("transition timing is unsupported") from exc


@dataclass(frozen=True, slots=True)
class OccurrenceWorkflowInputV1:
    """The immutable start input; post-pulse evidence is signal-only."""

    occurrence_uid: str
    worm_claim_receipt: ContentDescriptorV1 | None
    registration_evidence: ContentDescriptorV1
    occurrence_timeout_seconds: int
    schema_version: str = WORKER_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != WORKER_SCHEMA:
            raise ValueError("unsupported Temporal worker schema")
        # Reuse the canonical bounded UID validation and exact workflow ID.
        temporal_one_shot_launch_options(self.occurrence_uid)
        if self.worm_claim_receipt is None:
            raise ValueError("candidate WORM claim receipt descriptor is required")
        if not isinstance(self.worm_claim_receipt, ContentDescriptorV1):
            raise ValueError("WORM receipt must be a content descriptor")
        if not isinstance(self.registration_evidence, ContentDescriptorV1):
            raise ValueError("registration evidence must be a content descriptor")
        if self.worm_claim_receipt.name != "candidate_worm_claim_receipt":
            raise ValueError("WORM receipt descriptor has the wrong role")
        if self.registration_evidence.name != "registration_evidence":
            raise ValueError("registration descriptor has the wrong role")
        if (
            type(self.occurrence_timeout_seconds) is not int
            or not 1 <= self.occurrence_timeout_seconds <= 86_400
        ):
            raise ValueError("occurrence_timeout_seconds must be 1..86400")


@dataclass(frozen=True, slots=True)
class OccurrenceWorkerConfigV1:
    """Non-secret Temporal connection coordinates."""

    address: str
    namespace: str
    task_queue: str
    signal_authorization_binding_sha256: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("address", self.address),
            ("namespace", self.namespace),
            ("task_queue", self.task_queue),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"{field_name} must be a bounded non-empty string")
            if any(char.isspace() for char in value):
                raise ValueError(f"{field_name} must not contain whitespace")
        if (
            not isinstance(self.signal_authorization_binding_sha256, str)
            or re.fullmatch(
                r"[0-9a-f]{64}", self.signal_authorization_binding_sha256
            )
            is None
        ):
            raise ValueError(
                "signal authorization policy must have a content-addressed binding"
            )

    @classmethod
    def from_args_or_environment(
        cls,
        *,
        address: str | None,
        namespace: str | None,
        task_queue: str | None,
        signal_authorization_binding_sha256: str | None,
        environ: Mapping[str, str] | None = None,
    ) -> "OccurrenceWorkerConfigV1":
        values = os.environ if environ is None else environ
        return cls(
            address=address or values.get("HSWM_G0_TEMPORAL_ADDRESS", ""),
            namespace=namespace or values.get("HSWM_G0_TEMPORAL_NAMESPACE", ""),
            task_queue=task_queue or values.get("HSWM_G0_TEMPORAL_TASK_QUEUE", ""),
            signal_authorization_binding_sha256=(
                signal_authorization_binding_sha256
                or values.get(
                    "HSWM_G0_TEMPORAL_SIGNAL_AUTHORIZATION_BINDING", ""
                )
            ),
        )

    def redacted_summary(self) -> dict[str, object]:
        """Expose configuration presence and invariant values, never coordinates."""

        return {
            "address_configured": bool(self.address),
            "namespace_configured": bool(self.namespace),
            "task_queue_configured": bool(self.task_queue),
            "signal_authorization_binding_configured": True,
            "credentials_accepted": False,
        }


def _transition_from_wire(value: object) -> PhaseTransitionV1 | None:
    """Activity boundary validation; no side effect and no retry is permitted."""

    if isinstance(value, PhaseTransitionV1):
        try:
            return PhaseTransitionV1(value.next_phase, value.evidence, value.timing)
        except ValueError:
            return None
    if not isinstance(value, Mapping) or set(value) != {"next_phase", "evidence", "timing"}:
        return None
    next_phase = value["next_phase"]
    timing = value["timing"]
    evidence = value["evidence"]
    if not isinstance(next_phase, str) or not isinstance(timing, str):
        return None
    if not isinstance(evidence, Mapping):
        return None
    try:
        return PhaseTransitionV1(
            next_phase=next_phase,
            evidence=_parse_descriptor(evidence, field="transition evidence"),
            timing=timing,
        )
    except ValueError:
        return None


@activity.defn(name=ACTIVITY_NAME)
async def validate_transition_activity(value: object) -> PhaseTransitionV1 | None:
    return _transition_from_wire(value)


@workflow.defn(name=WORKFLOW_NAME)
class G0OccurrenceOneShotWorkflow:
    """Applies the existing fail-closed state machine to supplied descriptors."""

    def __init__(self) -> None:
        self._pending_transitions: list[object] = []
        self._signal_overflow = False

    @workflow.signal(name="submit_phase_transition")
    def submit_phase_transition(self, transition: object) -> None:
        """Queue one external evidence reference; it is not applied on receipt."""

        if len(self._pending_transitions) >= MAX_PENDING_SIGNALS:
            self._signal_overflow = True
        else:
            self._pending_transitions.append(transition)

    @workflow.run
    async def run(self, input_value: OccurrenceWorkflowInputV1) -> dict[str, object]:
        # Do not trust deserialization alone: refuse malformed/missing WORM input
        # inside the workflow execution as well as at client launch time.
        _validate_input(input_value)
        state = registered_occurrence(
            occurrence_uid=input_value.occurrence_uid,
            registration_evidence_sha256=input_value.registration_evidence.sha256,
        )
        # The externally claimed WORM receipt is both the prerequisite and the
        # exact evidence for REGISTERED -> CLAIMED.  Temporal never claims UID
        # ownership itself.
        state = advance_occurrence(
            state,
            next_phase=OccurrencePhase.CLAIMED,
            evidence_sha256=input_value.worm_claim_receipt.sha256,
            timing=PulseTiming.PRE_PULSE,
        )
        deadline = workflow.now() + timedelta(seconds=input_value.occurrence_timeout_seconds)
        while not state.terminal:
            remaining = deadline - workflow.now()
            if remaining <= timedelta():
                state = _terminal_void(state, VoidReason.LATE)
                break
            try:
                await workflow.wait_condition(
                    lambda: bool(self._pending_transitions), timeout=remaining
                )
            except TimeoutError:
                state = _terminal_void(state, VoidReason.LATE)
                break
            requested_transition = self._pending_transitions.pop(0)
            transition = await workflow.execute_activity(
                validate_transition_activity,
                requested_transition,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            state = (
                apply_transition(state, transition)
                if transition is not None
                else _terminal_void(state, VoidReason.INVALID_EVIDENCE_DESCRIPTOR)
            )
        # A signal already accepted into this workflow task after the nominal
        # final seal is an attempted re-entry, not an ignorable late message.
        if state.phase is OccurrencePhase.SEALED and (
            self._pending_transitions or self._signal_overflow
        ):
            rejected = _rejected_evidence_sha256(self._pending_transitions)
            self._pending_transitions.clear()
            state = _terminal_void(state, VoidReason.TERMINAL_REENTRY, rejected)
        return _state_projection(state)


def _validate_input(input_value: OccurrenceWorkflowInputV1) -> None:
    if not isinstance(input_value, OccurrenceWorkflowInputV1):
        raise ValueError("workflow input must be OccurrenceWorkflowInputV1")
    # Dataclass validation is intentionally repeated for payloads decoded by an
    # external data converter.
    OccurrenceWorkflowInputV1(
        occurrence_uid=input_value.occurrence_uid,
        worm_claim_receipt=input_value.worm_claim_receipt,
        registration_evidence=input_value.registration_evidence,
        occurrence_timeout_seconds=input_value.occurrence_timeout_seconds,
        schema_version=input_value.schema_version,
    )


def apply_transition(
    state: OccurrenceWorkflowStateV1, transition: PhaseTransitionV1
) -> OccurrenceWorkflowStateV1:
    """Apply one payload and convert malformed phase/timing to terminal VOID.

    The canonical state machine owns the VOID reason.  In particular, a bad
    input does not raise an application exception that an orchestration system
    might attempt again.
    """

    try:
        next_phase: object = transition.phase()
        timing: object = transition.pulse_timing()
    except ValueError:
        next_phase = transition.next_phase
        timing = transition.timing
    return advance_occurrence(
        state,
        next_phase=next_phase,  # type: ignore[arg-type]
        evidence_sha256=transition.evidence.sha256,
        timing=timing,  # type: ignore[arg-type]
    )


def _terminal_void(
    state: OccurrenceWorkflowStateV1,
    reason: VoidReason,
    rejected_evidence_sha256: str | None = None,
) -> OccurrenceWorkflowStateV1:
    """Represent an external timeout/malformed payload as a terminal state."""

    return void_occurrence(
        state,
        reason=reason,
        rejected_evidence_sha256=rejected_evidence_sha256,
    )


def _rejected_evidence_sha256(pending: list[object]) -> str | None:
    """Consume the first queued payload's descriptor when it is well-formed."""

    if not pending:
        return None
    transition = _transition_from_wire(pending.pop(0))
    return transition.evidence.sha256 if transition is not None else None


def build_start_options(input_value: OccurrenceWorkflowInputV1) -> dict[str, object]:
    """Build the exact client options; this function never contacts Temporal."""

    _validate_input(input_value)
    canonical = temporal_one_shot_launch_options(input_value.occurrence_uid)
    return {
        "id": canonical.workflow_id,
        "id_reuse_policy": WorkflowIDReusePolicy.REJECT_DUPLICATE,
        "retry_policy": RetryPolicy(maximum_attempts=1),
        "task_queue": None,  # caller must bind the separately validated config
        "execution_timeout": timedelta(
            seconds=input_value.occurrence_timeout_seconds
            + RECEIPT_FINALIZATION_GRACE_SECONDS
        ),
    }


def dry_run_plan(input_value: OccurrenceWorkflowInputV1, config: OccurrenceWorkerConfigV1) -> dict[str, object]:
    """Return a JSON-safe plan without initiating a connection or workflow."""

    options = build_start_options(input_value)
    return {
        "schema_version": WORKER_SCHEMA,
        "python_worker_status": PYTHON_WORKER_STATUS,
        "orchestration_authority": "TYPESCRIPT_TEMPORAL",
        "live_external_admission": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "execution": "DRY_RUN_NO_TEMPORAL_CONNECTION",
        "workflow_name": WORKFLOW_NAME,
        "workflow_id": options["id"],
        "workflow_id_reuse_policy": options["id_reuse_policy"].name,
        "workflow_maximum_attempts": options["retry_policy"].maximum_attempts,
        "activity_maximum_attempts": 1,
        "occurrence_timeout_seconds": input_value.occurrence_timeout_seconds,
        "receipt_finalization_grace_seconds": RECEIPT_FINALIZATION_GRACE_SECONDS,
        "execution_timeout_seconds": int(options["execution_timeout"].total_seconds()),
        "replacement_round_allowed": False,
        "post_start_evidence": "SIGNAL_ONLY_NOT_PRELOADED",
        "publication_eligible": False,
        "signal_authorization": (
            "CONTENT_ADDRESSED_EXTERNAL_POLICY_DECLARED_NOT_VERIFIED_BY_WORKER"
        ),
        "signal_authorization_claim_boundary": SIGNAL_AUTHORIZATION_CLAIM_BOUNDARY,
        "worm_claim_receipt_sha256": input_value.worm_claim_receipt.sha256,
        "config": config.redacted_summary(),
        "g0_status": "NOT_EXECUTED",
    }


async def serve(config: OccurrenceWorkerConfigV1) -> None:
    """Refuse the retired Python worker before any Temporal connection."""

    if PYTHON_WORKER_STATUS.startswith("RETIRED_REFERENCE_ONLY"):
        raise RuntimeError(
            "Python Temporal worker is retired; use the TypeScript Temporal implementation"
        )
    client = await Client.connect(config.address, namespace=config.namespace)
    worker = Worker(
        client,
        task_queue=config.task_queue,
        workflows=[G0OccurrenceOneShotWorkflow],
        activities=[validate_transition_activity],
    )
    await worker.run()


async def start_one_shot(
    client: Client,
    config: OccurrenceWorkerConfigV1,
    input_value: OccurrenceWorkflowInputV1,
) -> Any:
    """Refuse the retired Python start path before inspecting a client."""

    if PYTHON_WORKER_STATUS.startswith("RETIRED_REFERENCE_ONLY"):
        raise RuntimeError(
            "Python Temporal start is retired; use the TypeScript Temporal implementation"
        )
    if not isinstance(client, Client):
        raise TypeError("client must be a Temporal Client")
    options = build_start_options(input_value)
    return await client.start_workflow(
        G0OccurrenceOneShotWorkflow.run,
        input_value,
        id=str(options["id"]),
        task_queue=config.task_queue,
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        retry_policy=RetryPolicy(maximum_attempts=1),
        execution_timeout=options["execution_timeout"],
    )


def _state_projection(state: OccurrenceWorkflowStateV1) -> dict[str, object]:
    return {
        "schema_version": WORKER_SCHEMA,
        "occurrence_uid": state.occurrence_uid,
        "phase": state.phase.value,
        "void_reason": state.void_reason.value if state.void_reason else None,
        "rejected_evidence_sha256": state.rejected_evidence_sha256,
        "evidence_sha256s": list(state.evidence_sha256s),
        "terminal": state.terminal,
        "claim_boundary": CLAIM_BOUNDARY,
        "completion_handshake_required": True,
        "publication_eligible": False,
        "g0_status": "NOT_EVIDENCE_BY_ITSELF",
    }


def _parse_descriptor(value: Mapping[str, object], *, field: str) -> ContentDescriptorV1:
    try:
        if set(value) not in ({"name", "sha256"}, {"name", "sha256", "media_type"}):
            raise ValueError("unsupported descriptor shape")
        name = value["name"]
        sha256 = value["sha256"]
        media_type = value.get("media_type", _DESCRIPTOR_MEDIA_TYPE)
        if not all(isinstance(item, str) for item in (name, sha256, media_type)):
            raise ValueError("descriptor fields must be strings")
        return ContentDescriptorV1(
            name=name, sha256=sha256, media_type=media_type,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field} descriptor") from exc


def input_from_json_path(path: Path) -> OccurrenceWorkflowInputV1:
    """Parse a strict, descriptor-only JSON input file for dry-run use."""

    if not isinstance(path, Path):
        raise ValueError("input JSON path must be a filesystem path")
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("input JSON must be an existing regular file")
    if resolved.stat().st_size > MAX_INPUT_JSON_BYTES:
        raise ValueError("input JSON exceeds byte limit")
    encoded = resolved.read_bytes()
    raw = json.loads(encoded.decode("utf-8"))
    if not isinstance(raw, Mapping) or set(raw) != {
        "occurrence_uid", "worm_claim_receipt", "registration_evidence", "occurrence_timeout_seconds"
    }:
        raise ValueError("input JSON has an unsupported shape")
    worm = raw["worm_claim_receipt"]
    registration = raw["registration_evidence"]
    if not isinstance(worm, Mapping) or not isinstance(registration, Mapping):
        raise ValueError("descriptors must be JSON objects")
    return OccurrenceWorkflowInputV1(
        occurrence_uid=_require_json_string(raw["occurrence_uid"], "occurrence_uid"),
        worm_claim_receipt=_parse_descriptor(worm, field="worm claim receipt"),
        registration_evidence=_parse_descriptor(registration, field="registration evidence"),
        occurrence_timeout_seconds=_require_json_int(
            raw["occurrence_timeout_seconds"], "occurrence_timeout_seconds"
        ),
    )


def _require_json_string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a JSON string")
    return value


def _require_json_int(value: object, field: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{field} must be a JSON integer")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, required=True, help="descriptor-only JSON input"
    )
    parser.add_argument(
        "--address", help="Temporal address (or HSWM_G0_TEMPORAL_ADDRESS)"
    )
    parser.add_argument(
        "--namespace", help="Temporal namespace (or HSWM_G0_TEMPORAL_NAMESPACE)"
    )
    parser.add_argument(
        "--task-queue", help="task queue (or HSWM_G0_TEMPORAL_TASK_QUEUE)"
    )
    parser.add_argument(
        "--signal-authorization-binding-sha256",
        help=(
            "content digest of externally enforced signal authorization policy "
            "(or HSWM_G0_TEMPORAL_SIGNAL_AUTHORIZATION_BINDING)"
        ),
    )
    parser.add_argument(
        "--serve", action="store_true", help="retired Python live path; always refuses"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = OccurrenceWorkerConfigV1.from_args_or_environment(
            address=args.address,
            namespace=args.namespace,
            task_queue=args.task_queue,
            signal_authorization_binding_sha256=(
                args.signal_authorization_binding_sha256
            ),
        )
        input_value = input_from_json_path(args.input)
        if not args.serve:
            print(json.dumps(dry_run_plan(input_value, config), sort_keys=True, indent=2))
            return 0
        asyncio.run(serve(config))
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ACTIVITY_NAME", "ContentDescriptorV1", "DEFAULT_TASK_QUEUE",
    "G0OccurrenceOneShotWorkflow", "OccurrenceWorkerConfigV1",
    "OccurrenceWorkflowInputV1", "PhaseTransitionV1", "WORKER_SCHEMA",
    "WORKFLOW_NAME", "PYTHON_WORKER_STATUS", "SIGNAL_AUTHORIZATION_CLAIM_BOUNDARY", "apply_transition",
    "build_start_options", "dry_run_plan", "input_from_json_path",
    "serve", "start_one_shot", "validate_transition_activity",
]
