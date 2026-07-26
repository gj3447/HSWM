"""Pure event-sourced runtime kernel for one HSWM cell activation.

This module mirrors ``formal/HSWMRuntime.lean``.  It owns admission, replay,
budget accounting, activation correlation, and effect descriptions.  Model
execution stays behind ``CellPort`` and therefore cannot occur inside the
decision or evolution functions.

Passing this module's tests is engineering evidence only.  It does not judge
HSWM's learning, transfer, topology, consolidation, or larger-AI hypotheses.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, ClassVar, Mapping, Protocol, TypeAlias


SCHEMA_VERSION = "hswm-cellular-runtime/v1"


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def canonical_json_bytes(value: Any) -> bytes:
    """Encode JSON data deterministically or fail before it crosses the kernel."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class PacketEnvelope:
    packet_id: str
    packet_type: str
    payload: Any
    payload_sha256: str
    provenance_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "packet_id",
            "packet_type",
            "payload_sha256",
            "provenance_sha256",
        ):
            _require_text(name, getattr(self, name))


def make_packet(
    *,
    packet_id: str,
    packet_type: str,
    payload: Any,
    provenance: Any,
) -> PacketEnvelope:
    """Build a packet whose payload and provenance digests are reproducible."""

    return PacketEnvelope(
        packet_id=packet_id,
        packet_type=packet_type,
        payload=payload,
        payload_sha256=sha256(canonical_json_bytes(payload)).hexdigest(),
        provenance_sha256=sha256(canonical_json_bytes(provenance)).hexdigest(),
    )


@dataclass(frozen=True, slots=True)
class CellContract:
    cell_id: str
    input_type: str
    output_type: str

    def __post_init__(self) -> None:
        for name in ("cell_id", "input_type", "output_type"):
            _require_text(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class PendingActivation:
    activation_id: str
    cell_id: str
    input_packet_id: str
    input_payload_sha256: str
    expected_output_type: str


@dataclass(frozen=True, slots=True)
class CompletedActivation:
    activation_id: str
    cell_id: str
    output_packet_id: str
    output_payload_sha256: str


@dataclass(frozen=True, slots=True)
class KernelState:
    remaining_budget: int
    version: int = 0
    pending: tuple[PendingActivation, ...] = ()
    completed: tuple[CompletedActivation, ...] = ()

    def __post_init__(self) -> None:
        if self.remaining_budget < 0:
            raise ValueError("remaining_budget must be non-negative")
        if self.version < 0:
            raise ValueError("version must be non-negative")

    def find_pending(self, activation_id: str) -> PendingActivation | None:
        return next(
            (item for item in self.pending if item.activation_id == activation_id),
            None,
        )

    def has_activation(self, activation_id: str) -> bool:
        return any(item.activation_id == activation_id for item in self.pending) or any(
            item.activation_id == activation_id for item in self.completed
        )


@dataclass(frozen=True, slots=True)
class RequestCellStep:
    expected_version: int
    activation_id: str
    cell_id: str
    input: PacketEnvelope

    def __post_init__(self) -> None:
        if self.expected_version < 0:
            raise ValueError("expected_version must be non-negative")
        _require_text("activation_id", self.activation_id)
        _require_text("cell_id", self.cell_id)


@dataclass(frozen=True, slots=True)
class RecordCellOutput:
    expected_version: int
    activation_id: str
    output: PacketEnvelope

    def __post_init__(self) -> None:
        if self.expected_version < 0:
            raise ValueError("expected_version must be non-negative")
        _require_text("activation_id", self.activation_id)


Command: TypeAlias = RequestCellStep | RecordCellOutput


@dataclass(frozen=True, slots=True)
class CellStepRequested:
    schema_version: ClassVar[str] = SCHEMA_VERSION
    sequence: int
    activation_id: str
    cell_id: str
    input: PacketEnvelope
    expected_output_type: str


@dataclass(frozen=True, slots=True)
class CellStepCompleted:
    schema_version: ClassVar[str] = SCHEMA_VERSION
    sequence: int
    activation_id: str
    cell_id: str
    output: PacketEnvelope


Event: TypeAlias = CellStepRequested | CellStepCompleted


@dataclass(frozen=True, slots=True)
class InvokeCellEffect:
    schema_version: ClassVar[str] = SCHEMA_VERSION
    activation_id: str
    cell_id: str
    input: PacketEnvelope
    expected_output_type: str


Effect: TypeAlias = InvokeCellEffect


class RejectionReason(str, Enum):
    STALE_VERSION = "stale_version"
    BUDGET_EXHAUSTED = "budget_exhausted"
    DUPLICATE_ACTIVATION = "duplicate_activation"
    UNKNOWN_CELL = "unknown_cell"
    INPUT_TYPE_MISMATCH = "input_type_mismatch"
    UNKNOWN_ACTIVATION = "unknown_activation"
    OUTPUT_TYPE_MISMATCH = "output_type_mismatch"


@dataclass(frozen=True, slots=True)
class Accepted:
    events: tuple[Event, ...]


@dataclass(frozen=True, slots=True)
class Rejected:
    reason: RejectionReason
    detail: str


Decision: TypeAlias = Accepted | Rejected


class KernelInvariantError(RuntimeError):
    """Raised only when invalid events bypass ``decide`` and enter replay."""


def decide(
    registry: Mapping[str, CellContract],
    state: KernelState,
    command: Command,
) -> Decision:
    """Pure command admission.  No adapter is reachable from this function."""

    if command.expected_version != state.version:
        return Rejected(
            RejectionReason.STALE_VERSION,
            f"expected version {command.expected_version}, current {state.version}",
        )

    if isinstance(command, RequestCellStep):
        if state.remaining_budget == 0:
            return Rejected(
                RejectionReason.BUDGET_EXHAUSTED,
                "a cell step requires one remaining budget unit",
            )
        if state.has_activation(command.activation_id):
            return Rejected(
                RejectionReason.DUPLICATE_ACTIVATION,
                f"activation {command.activation_id!r} already exists",
            )
        contract = registry.get(command.cell_id)
        if contract is None:
            return Rejected(
                RejectionReason.UNKNOWN_CELL,
                f"cell {command.cell_id!r} has no registered contract",
            )
        if command.input.packet_type != contract.input_type:
            return Rejected(
                RejectionReason.INPUT_TYPE_MISMATCH,
                f"expected {contract.input_type!r}, got {command.input.packet_type!r}",
            )
        return Accepted(
            (
                CellStepRequested(
                    sequence=state.version + 1,
                    activation_id=command.activation_id,
                    cell_id=command.cell_id,
                    input=command.input,
                    expected_output_type=contract.output_type,
                ),
            )
        )

    pending = state.find_pending(command.activation_id)
    if pending is None:
        return Rejected(
            RejectionReason.UNKNOWN_ACTIVATION,
            f"activation {command.activation_id!r} is not pending",
        )
    if command.output.packet_type != pending.expected_output_type:
        return Rejected(
            RejectionReason.OUTPUT_TYPE_MISMATCH,
            f"expected {pending.expected_output_type!r}, got {command.output.packet_type!r}",
        )
    return Accepted(
        (
            CellStepCompleted(
                sequence=state.version + 1,
                activation_id=command.activation_id,
                cell_id=pending.cell_id,
                output=command.output,
            ),
        )
    )


def evolve(state: KernelState, event: Event) -> KernelState:
    """Pure state transition for one already-authorized event."""

    if event.sequence != state.version + 1:
        raise KernelInvariantError(
            f"event sequence {event.sequence} does not follow state version {state.version}"
        )

    if isinstance(event, CellStepRequested):
        if state.remaining_budget == 0:
            raise KernelInvariantError("requested event cannot consume zero budget")
        if state.has_activation(event.activation_id):
            raise KernelInvariantError("requested event reuses an activation id")
        pending = PendingActivation(
            activation_id=event.activation_id,
            cell_id=event.cell_id,
            input_packet_id=event.input.packet_id,
            input_payload_sha256=event.input.payload_sha256,
            expected_output_type=event.expected_output_type,
        )
        return KernelState(
            version=event.sequence,
            remaining_budget=state.remaining_budget - 1,
            pending=(pending, *state.pending),
            completed=state.completed,
        )

    pending = state.find_pending(event.activation_id)
    if pending is None:
        raise KernelInvariantError("completed event has no pending activation")
    completed = CompletedActivation(
        activation_id=event.activation_id,
        cell_id=event.cell_id,
        output_packet_id=event.output.packet_id,
        output_payload_sha256=event.output.payload_sha256,
    )
    return KernelState(
        version=event.sequence,
        remaining_budget=state.remaining_budget,
        pending=tuple(
            item for item in state.pending if item.activation_id != event.activation_id
        ),
        completed=(completed, *state.completed),
    )


def effects(event: Event) -> tuple[Effect, ...]:
    """Describe external work only after the corresponding event is committed."""

    if isinstance(event, CellStepRequested):
        return (
            InvokeCellEffect(
                activation_id=event.activation_id,
                cell_id=event.cell_id,
                input=event.input,
                expected_output_type=event.expected_output_type,
            ),
        )
    return ()


def replay(initial: KernelState, history: tuple[Event, ...]) -> KernelState:
    """Rebuild state deterministically from an ordered finite history."""

    state = initial
    for event in history:
        state = evolve(state, event)
    return state


def evolve_accepted(state: KernelState, decision: Decision) -> KernelState:
    if isinstance(decision, Rejected):
        raise KernelInvariantError(
            f"cannot evolve a rejected decision: {decision.reason.value}"
        )
    return replay(state, decision.events)


class CellPort(Protocol):
    """Effect adapter boundary; implementations may invoke an LLM or a stub."""

    def invoke(self, effect: InvokeCellEffect) -> PacketEnvelope:
        ...


def execute_cell_effect(
    *,
    state: KernelState,
    effect: InvokeCellEffect,
    registry: Mapping[str, CellContract],
    port: CellPort,
) -> tuple[KernelState, CellStepCompleted]:
    """Run one adapter effect and feed its output back through the pure kernel."""

    pending = state.find_pending(effect.activation_id)
    if pending is None or pending.cell_id != effect.cell_id:
        raise KernelInvariantError("effect does not name a pending activation")
    output = port.invoke(effect)
    decision = decide(
        registry,
        state,
        RecordCellOutput(
            expected_version=state.version,
            activation_id=effect.activation_id,
            output=output,
        ),
    )
    if isinstance(decision, Rejected):
        raise KernelInvariantError(
            f"cell adapter output rejected: {decision.reason.value}: {decision.detail}"
        )
    if len(decision.events) != 1 or not isinstance(
        decision.events[0], CellStepCompleted
    ):
        raise KernelInvariantError("completion decision violated the v1 event contract")
    completion = decision.events[0]
    return evolve(state, completion), completion


def state_projection(state: KernelState) -> dict[str, Any]:
    """Canonical, payload-free state projection for receipts and replay checks."""

    return {
        "schema_version": SCHEMA_VERSION,
        "version": state.version,
        "remaining_budget": state.remaining_budget,
        "pending": [
            {
                "activation_id": item.activation_id,
                "cell_id": item.cell_id,
                "input_packet_id": item.input_packet_id,
                "input_payload_sha256": item.input_payload_sha256,
                "expected_output_type": item.expected_output_type,
            }
            for item in state.pending
        ],
        "completed": [
            {
                "activation_id": item.activation_id,
                "cell_id": item.cell_id,
                "output_packet_id": item.output_packet_id,
                "output_payload_sha256": item.output_payload_sha256,
            }
            for item in state.completed
        ],
    }


def state_digest(state: KernelState) -> str:
    return sha256(canonical_json_bytes(state_projection(state))).hexdigest()


__all__ = [
    "Accepted",
    "CellContract",
    "CellPort",
    "CellStepCompleted",
    "CellStepRequested",
    "CompletedActivation",
    "Decision",
    "Effect",
    "Event",
    "InvokeCellEffect",
    "KernelInvariantError",
    "KernelState",
    "PacketEnvelope",
    "PendingActivation",
    "RecordCellOutput",
    "Rejected",
    "RejectionReason",
    "RequestCellStep",
    "SCHEMA_VERSION",
    "canonical_json_bytes",
    "decide",
    "effects",
    "evolve",
    "evolve_accepted",
    "execute_cell_effect",
    "make_packet",
    "replay",
    "state_digest",
    "state_projection",
]
