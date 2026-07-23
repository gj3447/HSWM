"""Pure kernel and narrow runtime shell for an ordered feedback event stream.

The domain core is ``decide``/``evolve``/``fold``.  It performs no I/O and
accepts only environmental facts already captured in event payloads.  The
``FeedbackRuntime`` shell adds first-write-wins request handling through an
injected store; SQLite remains the sole durable writer.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Iterable, Mapping

from feedback_ports import (
    CapabilityAuthority,
    CapabilityContext,
    CapabilityRole,
    EventStorePort,
    JudgmentPort,
    JudgmentReceipt,
    ObservationReceipt,
)


EVENT_SCHEMA_VERSION = "feedback-event/v1"
CUT_SCHEMA_VERSION = "feedback-cut/v1"
REPLAY_SCHEMA_VERSION = "feedback-replay/v1"
COMMIT_POLICY_VERSION = "feedback-commit-policy/v1"
DISPATCH_SCHEMA_VERSION = "feedback-dispatch/v1"
DISPATCH_POLICY_VERSION = "feedback-dispatch-policy/v1"
GENESIS_SHA256 = "0" * 64
VERDICTS = frozenset({"ACCEPT", "REJECT"})


class FeedbackError(ValueError):
    """Base class for fail-closed domain rejection."""


class InvalidTransition(FeedbackError):
    pass


class IntegrityError(FeedbackError):
    pass


class StaleCutError(FeedbackError):
    pass


class IdempotencyConflict(FeedbackError):
    pass


class EventKind(str, Enum):
    ATTACH = "ATTACH"
    PROPOSE = "PROPOSE"
    OBSERVE = "OBSERVE"
    JUDGE = "JUDGE"
    COMMIT = "COMMIT"
    DISPATCH = "DISPATCH"

    def __str__(self) -> str:
        return self.value


KIND_ROLE: dict[EventKind, CapabilityRole] = {
    EventKind.ATTACH: CapabilityRole.PROPOSER,
    EventKind.PROPOSE: CapabilityRole.PROPOSER,
    EventKind.OBSERVE: CapabilityRole.EXECUTOR,
    EventKind.JUDGE: CapabilityRole.JUDGE,
    EventKind.COMMIT: CapabilityRole.COMMITTER,
    EventKind.DISPATCH: CapabilityRole.DISPATCHER,
}

PHASE_KIND: dict[str, EventKind] = {
    "detached": EventKind.ATTACH,
    "attached": EventKind.PROPOSE,
    "proposed": EventKind.OBSERVE,
    "observed": EventKind.JUDGE,
    "judged": EventKind.COMMIT,
    "committed": EventKind.DISPATCH,
}

KIND_PHASE: dict[EventKind, str] = {
    EventKind.ATTACH: "attached",
    EventKind.PROPOSE: "proposed",
    EventKind.OBSERVE: "observed",
    EventKind.JUDGE: "judged",
    EventKind.COMMIT: "committed",
    EventKind.DISPATCH: "dispatched",
}


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise FeedbackError(f"value is not canonical JSON: {error}") from error


def sha256_canonical(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise IntegrityError(f"{field} must be a 64-character SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as error:
        raise IntegrityError(f"{field} must be hexadecimal") from error
    return value


@dataclass(frozen=True)
class EventEnvelope:
    schema_version: str
    stream_id: str
    sequence: int
    request_id: str
    kind: EventKind
    principal_id: str
    input_cut_id: str
    causal_parent_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    payload_sha256: str
    previous_event_sha256: str
    event_sha256: str

    @classmethod
    def build(
        cls,
        *,
        stream_id: str,
        sequence: int,
        request_id: str,
        kind: EventKind,
        principal_id: str,
        input_cut_id: str,
        causal_parent_ids: tuple[str, ...],
        payload: Mapping[str, Any],
        previous_event_sha256: str,
    ) -> "EventEnvelope":
        normalized_payload = json.loads(canonical_json_bytes(dict(payload)).decode("utf-8"))
        base = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "stream_id": stream_id,
            "sequence": sequence,
            "request_id": request_id,
            "kind": str(EventKind(kind)),
            "principal_id": principal_id,
            "input_cut_id": input_cut_id,
            "causal_parent_ids": list(causal_parent_ids),
            "payload": normalized_payload,
            "payload_sha256": sha256_canonical(normalized_payload),
            "previous_event_sha256": previous_event_sha256,
        }
        return cls(
            schema_version=EVENT_SCHEMA_VERSION,
            stream_id=stream_id,
            sequence=sequence,
            request_id=request_id,
            kind=EventKind(kind),
            principal_id=principal_id,
            input_cut_id=input_cut_id,
            causal_parent_ids=tuple(causal_parent_ids),
            payload=normalized_payload,
            payload_sha256=base["payload_sha256"],
            previous_event_sha256=previous_event_sha256,
            event_sha256=sha256_canonical(base),
        )

    def without_event_hash(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "request_id": self.request_id,
            "kind": str(self.kind),
            "principal_id": self.principal_id,
            "input_cut_id": self.input_cut_id,
            "causal_parent_ids": list(self.causal_parent_ids),
            "payload": dict(self.payload),
            "payload_sha256": self.payload_sha256,
            "previous_event_sha256": self.previous_event_sha256,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.without_event_hash(), "event_sha256": self.event_sha256}

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_dict())

    @classmethod
    def from_canonical_bytes(cls, raw: bytes) -> "EventEnvelope":
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise IntegrityError(f"invalid event JSON: {error}") from error
        if canonical_json_bytes(value) != raw:
            raise IntegrityError("stored event bytes are not canonical")
        try:
            event = cls(
                schema_version=value["schema_version"],
                stream_id=value["stream_id"],
                sequence=value["sequence"],
                request_id=value["request_id"],
                kind=EventKind(value["kind"]),
                principal_id=value["principal_id"],
                input_cut_id=value["input_cut_id"],
                causal_parent_ids=tuple(value["causal_parent_ids"]),
                payload=value["payload"],
                payload_sha256=value["payload_sha256"],
                previous_event_sha256=value["previous_event_sha256"],
                event_sha256=value["event_sha256"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise IntegrityError(f"invalid event envelope: {error}") from error
        event.verify_integrity()
        return event

    def verify_integrity(self) -> None:
        if self.schema_version != EVENT_SCHEMA_VERSION:
            raise IntegrityError(f"unsupported event schema {self.schema_version!r}")
        if not self.stream_id or not self.request_id or not self.principal_id or not self.input_cut_id:
            raise IntegrityError("event identity fields must be non-empty")
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence < 0:
            raise IntegrityError("sequence must be a non-negative integer")
        _require_sha256(self.previous_event_sha256, "previous_event_sha256")
        for index, parent in enumerate(self.causal_parent_ids):
            _require_sha256(parent, f"causal_parent_ids[{index}]")
        expected_payload = sha256_canonical(dict(self.payload))
        if not hmac.compare_digest(expected_payload, self.payload_sha256):
            raise IntegrityError("payload digest mismatch")
        expected_event = sha256_canonical(self.without_event_hash())
        if not hmac.compare_digest(expected_event, self.event_sha256):
            raise IntegrityError("event digest mismatch")


@dataclass(frozen=True)
class FeedbackCommand:
    stream_id: str
    request_id: str
    kind: EventKind
    capability: CapabilityContext
    input_cut_id: str
    causal_parent_ids: tuple[str, ...]
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class FeedbackState:
    stream_id: str
    initial_cut_id: str
    phase: str = "detached"
    sequence: int = 0
    previous_event_sha256: str = GENESIS_SHA256
    current_cut_id: str = ""
    final_cut_id: str = ""
    next_dispatch_id: str = ""
    verdict: str = ""
    route: str = ""
    events: tuple[EventEnvelope, ...] = ()
    role_bindings: tuple[tuple[str, str], ...] = ()

    def event(self, kind: EventKind) -> EventEnvelope:
        for event in self.events:
            if event.kind == kind:
                return event
        raise InvalidTransition(f"missing predecessor {kind}")


@dataclass(frozen=True)
class ReplayProjection:
    stream_id: str
    phase: str
    event_count: int
    event_root_sha256: str
    final_cut_id: str
    next_dispatch_id: str
    replay_sha256: str


def initial_state(stream_id: str, initial_cut_id: str) -> FeedbackState:
    if not stream_id or not initial_cut_id:
        raise ValueError("stream_id and initial_cut_id must be non-empty")
    return FeedbackState(
        stream_id=stream_id,
        initial_cut_id=initial_cut_id,
        current_cut_id=initial_cut_id,
    )


def exact_causal_parents(state: FeedbackState, kind: EventKind) -> tuple[str, ...]:
    if kind == EventKind.ATTACH:
        return ()
    if kind == EventKind.PROPOSE:
        return (state.event(EventKind.ATTACH).event_sha256,)
    if kind == EventKind.OBSERVE:
        return (state.event(EventKind.PROPOSE).event_sha256,)
    if kind == EventKind.JUDGE:
        return (
            state.event(EventKind.PROPOSE).event_sha256,
            state.event(EventKind.OBSERVE).event_sha256,
        )
    if kind == EventKind.COMMIT:
        return (state.event(EventKind.JUDGE).event_sha256,)
    if kind == EventKind.DISPATCH:
        return (state.event(EventKind.COMMIT).event_sha256,)
    raise AssertionError(kind)


def derive_final_cut(parent_cut_id: str, judgment_event_sha256: str, verdict: str) -> str:
    return sha256_canonical(
        {
            "schema_version": CUT_SCHEMA_VERSION,
            "parent_cut_id": parent_cut_id,
            "judgment_event_sha256": judgment_event_sha256,
            "verdict": verdict,
            "commit_policy_version": COMMIT_POLICY_VERSION,
        }
    )


def derive_dispatch(
    final_cut_id: str,
    commit_event_sha256: str,
    verdict: str,
    route: str,
) -> str:
    return sha256_canonical(
        {
            "schema_version": DISPATCH_SCHEMA_VERSION,
            "final_cut_id": final_cut_id,
            "commit_event_sha256": commit_event_sha256,
            "verdict": verdict,
            "route": route,
            "dispatch_policy_version": DISPATCH_POLICY_VERSION,
        }
    )


def request_sha256(
    *,
    stream_id: str,
    request_id: str,
    kind: EventKind,
    trusted_principal_id: str,
    input_cut_id: str,
    causal_parent_ids: tuple[str, ...],
    payload_sha256: str,
) -> str:
    return sha256_canonical(
        {
            "schema_version": EVENT_SCHEMA_VERSION,
            "stream_id": stream_id,
            "request_id": request_id,
            "kind": str(kind),
            "trusted_principal_id": trusted_principal_id,
            "input_cut_id": input_cut_id,
            "causal_parent_ids": list(causal_parent_ids),
            "payload_sha256": payload_sha256,
        }
    )


def _require_text(payload: Mapping[str, Any], *fields: str) -> None:
    for field in fields:
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise InvalidTransition(f"payload.{field} must be a non-empty string")


def _validate_payload(state: FeedbackState, event: EventEnvelope) -> None:
    payload = event.payload
    if event.kind == EventKind.ATTACH:
        _require_text(payload, "attachment_id")
    elif event.kind == EventKind.PROPOSE:
        _require_text(payload, "proposal_id", "action")
    elif event.kind == EventKind.OBSERVE:
        _require_text(payload, "receipt_id", "proposal_event_sha256", "adapter_identity")
        if payload["proposal_event_sha256"] != state.event(EventKind.PROPOSE).event_sha256:
            raise InvalidTransition("observation receipt is not bound to the proposal")
        if "observation" not in payload:
            raise InvalidTransition("observation receipt is missing observation")
    elif event.kind == EventKind.JUDGE:
        _require_text(
            payload,
            "judgment_receipt_id",
            "proposal_event_sha256",
            "observation_event_sha256",
            "verdict",
            "adapter_identity",
        )
        if payload["verdict"] not in VERDICTS:
            raise InvalidTransition("verdict must be ACCEPT or REJECT")
        if payload["proposal_event_sha256"] != state.event(EventKind.PROPOSE).event_sha256:
            raise InvalidTransition("judgment is not bound to the proposal")
        if payload["observation_event_sha256"] != state.event(EventKind.OBSERVE).event_sha256:
            raise InvalidTransition("judgment is not bound to the observation")
    elif event.kind == EventKind.COMMIT:
        _require_text(
            payload,
            "judgment_event_sha256",
            "parent_cut_id",
            "verdict",
            "commit_policy_version",
            "final_cut_id",
        )
        judgment = state.event(EventKind.JUDGE)
        expected_cut = derive_final_cut(state.current_cut_id, judgment.event_sha256, state.verdict)
        expected = {
            "judgment_event_sha256": judgment.event_sha256,
            "parent_cut_id": state.current_cut_id,
            "verdict": state.verdict,
            "commit_policy_version": COMMIT_POLICY_VERSION,
            "final_cut_id": expected_cut,
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            raise InvalidTransition("commit payload does not match the judged chain")
    elif event.kind == EventKind.DISPATCH:
        _require_text(
            payload,
            "commit_event_sha256",
            "final_cut_id",
            "verdict",
            "route",
            "dispatch_policy_version",
            "next_dispatch_id",
        )
        commit = state.event(EventKind.COMMIT)
        route = "integrate" if state.verdict == "ACCEPT" else "revise"
        expected_dispatch = derive_dispatch(
            state.final_cut_id, commit.event_sha256, state.verdict, route
        )
        expected = {
            "commit_event_sha256": commit.event_sha256,
            "final_cut_id": state.final_cut_id,
            "verdict": state.verdict,
            "route": route,
            "dispatch_policy_version": DISPATCH_POLICY_VERSION,
            "next_dispatch_id": expected_dispatch,
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            raise InvalidTransition("dispatch payload does not match the committed chain")


def _check_role_binding(state: FeedbackState, event: EventEnvelope) -> tuple[tuple[str, str], ...]:
    role = str(KIND_ROLE[event.kind])
    bindings = dict(state.role_bindings)
    prior_for_role = bindings.get(role)
    if prior_for_role is not None and prior_for_role != event.principal_id:
        raise InvalidTransition(f"stream role {role} is already bound")
    for bound_role, principal in bindings.items():
        if principal == event.principal_id and bound_role != role:
            raise InvalidTransition("one principal cannot hold multiple stream roles in v1")
    bindings[role] = event.principal_id
    if role == str(CapabilityRole.JUDGE):
        proposer = bindings.get(str(CapabilityRole.PROPOSER))
        if proposer == event.principal_id:
            raise InvalidTransition("proposer and judge must be distinct")
    return tuple(sorted(bindings.items()))


def evolve(state: FeedbackState, event: EventEnvelope) -> FeedbackState:
    event.verify_integrity()
    if event.stream_id != state.stream_id:
        raise IntegrityError("event stream mismatch")
    if event.sequence != state.sequence:
        raise IntegrityError(f"sequence mismatch: expected {state.sequence}, got {event.sequence}")
    if event.previous_event_sha256 != state.previous_event_sha256:
        raise IntegrityError("previous event digest mismatch")
    expected_kind = PHASE_KIND.get(state.phase)
    if expected_kind is None or event.kind != expected_kind:
        raise InvalidTransition(f"{event.kind} is forbidden from phase {state.phase}")
    expected_parents = exact_causal_parents(state, event.kind)
    if event.causal_parent_ids != expected_parents:
        raise InvalidTransition("causal parent set/order mismatch")
    expected_cut = state.final_cut_id if event.kind == EventKind.DISPATCH else state.current_cut_id
    if event.input_cut_id != expected_cut:
        raise StaleCutError(f"expected input cut {expected_cut}, got {event.input_cut_id}")
    bindings = _check_role_binding(state, event)
    _validate_payload(state, event)

    next_state = replace(
        state,
        phase=KIND_PHASE[event.kind],
        sequence=state.sequence + 1,
        previous_event_sha256=event.event_sha256,
        events=state.events + (event,),
        role_bindings=bindings,
    )
    if event.kind == EventKind.JUDGE:
        next_state = replace(next_state, verdict=str(event.payload["verdict"]))
    elif event.kind == EventKind.COMMIT:
        next_state = replace(
            next_state,
            current_cut_id=str(event.payload["final_cut_id"]),
            final_cut_id=str(event.payload["final_cut_id"]),
        )
    elif event.kind == EventKind.DISPATCH:
        next_state = replace(
            next_state,
            next_dispatch_id=str(event.payload["next_dispatch_id"]),
            route=str(event.payload["route"]),
        )
    return next_state


def decide(
    state: FeedbackState,
    command: FeedbackCommand,
    authority: CapabilityAuthority,
) -> tuple[EventEnvelope, str]:
    kind = EventKind(command.kind)
    if command.stream_id != state.stream_id:
        raise InvalidTransition("command stream mismatch")
    if not command.request_id:
        raise InvalidTransition("request_id must be non-empty")
    principal_id = authority.verify(
        command.capability, KIND_ROLE[kind], stream_id=command.stream_id
    )
    event = EventEnvelope.build(
        stream_id=command.stream_id,
        sequence=state.sequence,
        request_id=command.request_id,
        kind=kind,
        principal_id=principal_id,
        input_cut_id=command.input_cut_id,
        causal_parent_ids=tuple(command.causal_parent_ids),
        payload=command.payload,
        previous_event_sha256=state.previous_event_sha256,
    )
    # Prove the proposed event is a valid transition before returning it.
    evolve(state, event)
    request_digest = request_sha256(
        stream_id=command.stream_id,
        request_id=command.request_id,
        kind=kind,
        trusted_principal_id=principal_id,
        input_cut_id=command.input_cut_id,
        causal_parent_ids=tuple(command.causal_parent_ids),
        payload_sha256=event.payload_sha256,
    )
    return event, request_digest


def fold(
    events: Iterable[EventEnvelope],
    *,
    stream_id: str,
    initial_cut_id: str,
) -> FeedbackState:
    state = initial_state(stream_id, initial_cut_id)
    for event in events:
        state = evolve(state, event)
    return state


def replay_projection(state: FeedbackState) -> ReplayProjection:
    root = state.previous_event_sha256
    replay = sha256_canonical(
        {
            "schema_version": REPLAY_SCHEMA_VERSION,
            "event_root_sha256": root,
            "phase": state.phase,
            "final_cut_id": state.final_cut_id,
            "next_dispatch_id": state.next_dispatch_id,
        }
    )
    return ReplayProjection(
        stream_id=state.stream_id,
        phase=state.phase,
        event_count=state.sequence,
        event_root_sha256=root,
        final_cut_id=state.final_cut_id,
        next_dispatch_id=state.next_dispatch_id,
        replay_sha256=replay,
    )


class FeedbackRuntime:
    """Thin service shell around the pure kernel and one injected event store."""

    def __init__(
        self,
        *,
        store: EventStorePort,
        authority: CapabilityAuthority,
        stream_id: str,
        initial_cut_id: str,
    ) -> None:
        self.store = store
        self.authority = authority
        self.stream_id = stream_id
        self.initial_cut_id = initial_cut_id

    def state(self) -> FeedbackState:
        return fold(
            self.store.events(self.stream_id),
            stream_id=self.stream_id,
            initial_cut_id=self.initial_cut_id,
        )

    def projection(self) -> ReplayProjection:
        return replay_projection(self.state())

    def command(
        self,
        kind: EventKind,
        *,
        request_id: str,
        capability: CapabilityContext,
        payload: Mapping[str, Any],
        input_cut_id: str | None = None,
        causal_parent_ids: tuple[str, ...] | None = None,
    ) -> FeedbackCommand:
        state = self.state()
        kind = EventKind(kind)
        return FeedbackCommand(
            stream_id=self.stream_id,
            request_id=request_id,
            kind=kind,
            capability=capability,
            input_cut_id=(
                state.final_cut_id if kind == EventKind.DISPATCH else state.current_cut_id
            )
            if input_cut_id is None
            else input_cut_id,
            causal_parent_ids=exact_causal_parents(state, kind)
            if causal_parent_ids is None
            else tuple(causal_parent_ids),
            payload=payload,
        )

    def submit(self, command: FeedbackCommand) -> EventEnvelope:
        kind = EventKind(command.kind)
        principal_id = self.authority.verify(
            command.capability, KIND_ROLE[kind], stream_id=command.stream_id
        )
        payload_sha = sha256_canonical(dict(command.payload))
        command_request_sha = request_sha256(
            stream_id=command.stream_id,
            request_id=command.request_id,
            kind=kind,
            trusted_principal_id=principal_id,
            input_cut_id=command.input_cut_id,
            causal_parent_ids=tuple(command.causal_parent_ids),
            payload_sha256=payload_sha,
        )
        existing = self.store.lookup_request(command.stream_id, command.request_id)
        if existing is not None:
            stored_request_sha, stored_event = existing
            if not hmac.compare_digest(stored_request_sha, command_request_sha):
                raise IdempotencyConflict("same request_id carries different intent")
            return stored_event
        event, computed_request_sha = decide(self.state(), command, self.authority)
        stored, _inserted = self.store.append(event, computed_request_sha)
        return stored

    def commit_command(
        self, *, request_id: str, capability: CapabilityContext
    ) -> FeedbackCommand:
        state = self.state()
        judgment = state.event(EventKind.JUDGE)
        final_cut = derive_final_cut(state.current_cut_id, judgment.event_sha256, state.verdict)
        return self.command(
            EventKind.COMMIT,
            request_id=request_id,
            capability=capability,
            payload={
                "judgment_event_sha256": judgment.event_sha256,
                "parent_cut_id": state.current_cut_id,
                "verdict": state.verdict,
                "commit_policy_version": COMMIT_POLICY_VERSION,
                "final_cut_id": final_cut,
            },
        )

    def dispatch_command(
        self, *, request_id: str, capability: CapabilityContext
    ) -> FeedbackCommand:
        state = self.state()
        commit = state.event(EventKind.COMMIT)
        route = "integrate" if state.verdict == "ACCEPT" else "revise"
        dispatch_id = derive_dispatch(
            state.final_cut_id, commit.event_sha256, state.verdict, route
        )
        return self.command(
            EventKind.DISPATCH,
            request_id=request_id,
            capability=capability,
            payload={
                "commit_event_sha256": commit.event_sha256,
                "final_cut_id": state.final_cut_id,
                "verdict": state.verdict,
                "route": route,
                "dispatch_policy_version": DISPATCH_POLICY_VERSION,
                "next_dispatch_id": dispatch_id,
            },
        )

    def observe_payload(self, receipt: ObservationReceipt) -> Mapping[str, Any]:
        return receipt.as_payload()

    def judgment_payload(self, receipt: JudgmentReceipt) -> Mapping[str, Any]:
        return receipt.as_payload()

    def judge_with_port(
        self,
        port: JudgmentPort,
        *,
        request_id: str,
        capability: CapabilityContext,
    ) -> EventEnvelope:
        state = self.state()
        proposal = state.event(EventKind.PROPOSE)
        observed = state.event(EventKind.OBSERVE)
        receipt = ObservationReceipt(
            receipt_id=str(observed.payload["receipt_id"]),
            proposal_event_sha256=str(observed.payload["proposal_event_sha256"]),
            observation=dict(observed.payload["observation"]),
            adapter_identity=str(observed.payload["adapter_identity"]),
        )
        judgment = port.judge(
            proposal.payload,
            receipt,
            input_cut_id=state.current_cut_id,
            pinned_cut=state.current_cut_id,
            idempotency_key=request_id,
        )
        return self.submit(
            self.command(
                EventKind.JUDGE,
                request_id=request_id,
                capability=capability,
                payload=judgment.as_payload(),
            )
        )
