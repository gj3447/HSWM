"""Trusted ports and capability contexts for the generic feedback runtime.

The runtime never grants authority from an event payload or an ``actor`` string.
Callers receive an opaque, HMAC-bound :class:`CapabilityContext` from a trusted
``CapabilityAuthority`` and inject it into a command.  Capabilities are runtime
context; they are deliberately not serialized into the authoritative event log.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol, runtime_checkable


class CapabilityRole(str, Enum):
    PROPOSER = "proposer"
    EXECUTOR = "executor"
    JUDGE = "judge"
    COMMITTER = "committer"
    DISPATCHER = "dispatcher"

    def __str__(self) -> str:
        return self.value


def _capability_message(
    authority_id: str,
    stream_id: str,
    principal_id: str,
    role: CapabilityRole,
) -> bytes:
    return json.dumps(
        {
            "authority_id": authority_id,
            "stream_id": stream_id,
            "principal_id": principal_id,
            "role": str(role),
            "schema_version": "feedback-capability/v1",
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class CapabilityContext:
    """Opaque authority proof presented out-of-band with a command."""

    authority_id: str
    stream_id: str
    principal_id: str
    role: CapabilityRole
    signature: str


class CapabilityError(PermissionError):
    """A capability is absent, forged, or does not grant the requested role."""


class CapabilityAuthority:
    """Mint and verify HMAC-bound capabilities from an injected runtime secret."""

    def __init__(self, *, authority_id: str, secret: bytes) -> None:
        if not authority_id:
            raise ValueError("authority_id must be non-empty")
        if not isinstance(secret, bytes) or len(secret) < 16:
            raise ValueError("capability secret must contain at least 16 bytes")
        self.authority_id = authority_id
        self._secret = secret

    def mint(
        self,
        *,
        stream_id: str,
        principal_id: str,
        role: CapabilityRole,
    ) -> CapabilityContext:
        if not stream_id or not principal_id:
            raise ValueError("stream_id and principal_id must be non-empty")
        role = CapabilityRole(role)
        signature = hmac.new(
            self._secret,
            _capability_message(self.authority_id, stream_id, principal_id, role),
            hashlib.sha256,
        ).hexdigest()
        return CapabilityContext(self.authority_id, stream_id, principal_id, role, signature)

    def verify(
        self,
        context: CapabilityContext,
        required_role: CapabilityRole,
        *,
        stream_id: str,
    ) -> str:
        if not isinstance(context, CapabilityContext):
            raise CapabilityError("trusted CapabilityContext required")
        required_role = CapabilityRole(required_role)
        if (
            context.authority_id != self.authority_id
            or context.stream_id != stream_id
            or context.role != required_role
        ):
            raise CapabilityError(f"capability does not grant {required_role}")
        expected = hmac.new(
            self._secret,
            _capability_message(
                context.authority_id,
                context.stream_id,
                context.principal_id,
                context.role,
            ),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, context.signature):
            raise CapabilityError("forged capability signature")
        return context.principal_id


@dataclass(frozen=True)
class ObservationReceipt:
    receipt_id: str
    proposal_event_sha256: str
    observation: Mapping[str, Any]
    adapter_identity: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "proposal_event_sha256": self.proposal_event_sha256,
            "observation": dict(self.observation),
            "adapter_identity": self.adapter_identity,
        }


@dataclass(frozen=True)
class JudgmentReceipt:
    receipt_id: str
    proposal_event_sha256: str
    observation_event_sha256: str
    verdict: str
    adapter_identity: str
    evidence: Mapping[str, Any]

    def as_payload(self) -> dict[str, Any]:
        return {
            "judgment_receipt_id": self.receipt_id,
            "proposal_event_sha256": self.proposal_event_sha256,
            "observation_event_sha256": self.observation_event_sha256,
            "verdict": self.verdict,
            "adapter_identity": self.adapter_identity,
            "evidence": dict(self.evidence),
        }


@runtime_checkable
class ExecutorPort(Protocol):
    adapter_identity: str

    def execute(
        self,
        proposal: Mapping[str, Any],
        *,
        pinned_cut: str,
        idempotency_key: str,
    ) -> ObservationReceipt: ...


@runtime_checkable
class JudgmentPort(Protocol):
    """Generic operational evaluator; deliberately not a scientific judge."""

    adapter_identity: str

    def judge(
        self,
        proposal: Mapping[str, Any],
        observation: ObservationReceipt,
        *,
        input_cut_id: str,
        pinned_cut: str,
        idempotency_key: str,
    ) -> JudgmentReceipt: ...


@runtime_checkable
class CommitterPort(Protocol):
    adapter_identity: str

    def authorize_commit(self, judgment: JudgmentReceipt) -> Mapping[str, Any]: ...


@runtime_checkable
class DispatcherPort(Protocol):
    adapter_identity: str

    def authorize_dispatch(self, committed_cut_id: str, route: str) -> Mapping[str, Any]: ...


@runtime_checkable
class EventStorePort(Protocol):
    def lookup_request(self, stream_id: str, request_id: str) -> tuple[str, Any] | None: ...

    def events(self, stream_id: str) -> list[Any]: ...

    def append(self, event: Any, request_sha256: str) -> tuple[Any, bool]: ...
