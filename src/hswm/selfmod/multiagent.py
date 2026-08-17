"""Deterministic execution of the persistent HSWM cell topology.

The self-modification contracts persist memories, relations, cells, and their
routing edges as the HSWM itself.  This module projects that frozen structural
state into an ephemeral deterministic execution plan, binds each cell to a
logical agent, invokes the matching ``CellPort``, and carries typed messages
across declared edges.  The plan is execution evidence, never authored or
persisted as part of the HSWM snapshot.

It intentionally does not claim that several calls improve task quality.  It
provides auditable mechanics with which that causal claim can be tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import heapq
import json
from typing import Any, Mapping, Sequence

from hswm.cells.runtime import CellPort, InvokeCellEffect, PacketEnvelope, make_packet

from .contracts import (
    ActiveSnapshot,
    CellRecord,
    CognitiveToken,
    MemoryRecord,
    SelfModelSnapshot,
    canonical_json_bytes,
    canonical_sha256,
    make_token,
    snapshot_from_mapping,
    token_from_mapping,
)
from .multiagent_journal import (
    ExecutionStatus,
    JournalStepStatus,
    SQLiteMultiAgentJournal,
)
from .store import SQLiteSelfModelStore, SelfModelStoreError


MULTIAGENT_EXECUTION_SCHEMA_VERSION = "hswm-multiagent-execution/v2"
MULTIAGENT_MESSAGE_SCHEMA_VERSION = "hswm-multiagent-message/v2"
MULTIAGENT_STEP_SCHEMA_VERSION = "hswm-multiagent-step/v2"
MULTIAGENT_STEP_REQUEST_TYPE = "hswm-multiagent-step-request/v2"
MULTIAGENT_STEP_RESPONSE_TYPE = "hswm-multiagent-step-response/v2"
MULTIAGENT_JSON_REQUEST_TYPE = "hswm-multiagent-json-request/v2"
MULTIAGENT_JSON_RESPONSE_TYPE = "hswm-multiagent-json-response/v2"
MULTIAGENT_JSON_ADAPTER_VERSION = "hswm-multiagent-json-adapter/v2"


class MultiAgentRuntimeError(RuntimeError):
    """Structural HSWM execution crossed a fixed runtime boundary."""


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MultiAgentRuntimeError(f"{label} must be a non-empty string")
    return value


def _strings(
    values: object,
    label: str,
    *,
    unique: bool = True,
    sort: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, Mapping)) or not isinstance(values, Sequence):
        raise MultiAgentRuntimeError(f"{label} must be an array of strings")
    result = tuple(_text(value, label) for value in values)
    if unique and len(result) != len(set(result)):
        raise MultiAgentRuntimeError(f"{label} must not contain duplicates")
    return tuple(sorted(result)) if sort else result


def _fields(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise MultiAgentRuntimeError(f"{label} field set is invalid")


def _json_copy(value: Any) -> Any:
    """Validate and detach caller/adapter-owned JSON values."""

    return json.loads(canonical_json_bytes(value).decode("utf-8"))


def _packet_manifest(packet: PacketEnvelope) -> dict[str, Any]:
    return {
        "packet_id": packet.packet_id,
        "packet_type": packet.packet_type,
        "payload": packet.payload,
        "payload_sha256": packet.payload_sha256,
        "provenance_sha256": packet.provenance_sha256,
    }


def _effect_manifest(effect: InvokeCellEffect) -> dict[str, Any]:
    return {
        "activation_id": effect.activation_id,
        "cell_id": effect.cell_id,
        "input": _packet_manifest(effect.input),
        "expected_output_type": effect.expected_output_type,
    }


def _detached_effect(effect: InvokeCellEffect) -> InvokeCellEffect:
    packet = effect.input
    return InvokeCellEffect(
        activation_id=effect.activation_id,
        cell_id=effect.cell_id,
        input=PacketEnvelope(
            packet_id=packet.packet_id,
            packet_type=packet.packet_type,
            payload=_json_copy(packet.payload),
            payload_sha256=packet.payload_sha256,
            provenance_sha256=packet.provenance_sha256,
        ),
        expected_output_type=effect.expected_output_type,
    )


def _require_unchanged_effect(
    effect: InvokeCellEffect,
    expected_bytes: bytes,
    *,
    label: str,
) -> None:
    try:
        actual = canonical_json_bytes(_effect_manifest(effect))
    except (TypeError, ValueError) as error:
        raise MultiAgentRuntimeError(f"{label} mutated its frozen request") from error
    if actual != expected_bytes:
        raise MultiAgentRuntimeError(f"{label} mutated its frozen request")


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise MultiAgentRuntimeError(f"{label} must be a positive integer")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MultiAgentRuntimeError(f"{label} must be a non-negative integer")
    return value


class TokenVisibility(str, Enum):
    PUBLIC = "PUBLIC"
    DIRECT_ONLY = "DIRECT_ONLY"


@dataclass(frozen=True, slots=True)
class InputScopeManifest:
    token_id: str
    token_sha256: str
    visibility: TokenVisibility
    owner_agent_id: str | None

    def __post_init__(self) -> None:
        _text(self.token_id, "token_id")
        if not _is_sha256(self.token_sha256):
            raise MultiAgentRuntimeError("token_sha256 must be a canonical sha256")
        if not isinstance(self.visibility, TokenVisibility):
            raise MultiAgentRuntimeError("input visibility is invalid")
        if self.visibility is TokenVisibility.PUBLIC:
            if self.owner_agent_id is not None:
                raise MultiAgentRuntimeError("public input cannot have a direct owner")
        else:
            _text(self.owner_agent_id, "owner_agent_id")

    def canonical(self) -> dict[str, Any]:
        return {
            "token_id": self.token_id,
            "token_sha256": self.token_sha256,
            "visibility": self.visibility.value,
            "owner_agent_id": self.owner_agent_id,
        }


@dataclass(frozen=True, slots=True)
class ScopedToken:
    """Direct-input audience for a token.

    ``DIRECT_ONLY`` prevents the raw token from being supplied to other agent
    ports.  It is deliberately not an information-flow secrecy claim: an
    authorized owner may communicate derived output over a cell edge.
    """

    token: CognitiveToken
    visibility: TokenVisibility = TokenVisibility.PUBLIC
    owner_agent_id: str | None = None

    def __post_init__(self) -> None:
        try:
            token = token_from_mapping(_json_copy(self.token.canonical()))
        except ValueError as error:
            raise MultiAgentRuntimeError(f"invalid scoped token: {error}") from error
        object.__setattr__(self, "token", token)
        if not isinstance(self.visibility, TokenVisibility):
            raise MultiAgentRuntimeError("visibility must be PUBLIC or DIRECT_ONLY")
        if self.visibility is TokenVisibility.PUBLIC:
            if self.owner_agent_id is not None:
                raise MultiAgentRuntimeError("a public token cannot have a private owner")
        else:
            _text(self.owner_agent_id, "owner_agent_id")

    def scope_manifest(self) -> InputScopeManifest:
        return InputScopeManifest(
            token_id=self.token.token_id,
            token_sha256=canonical_sha256(self.token.canonical()),
            visibility=self.visibility,
            owner_agent_id=self.owner_agent_id,
        )


@dataclass(frozen=True, slots=True)
class AgentIdentity:
    agent_id: str
    allowed_capabilities: frozenset[str]

    def __post_init__(self) -> None:
        _text(self.agent_id, "agent_id")
        capabilities = frozenset(
            _text(capability, "allowed_capabilities")
            for capability in self.allowed_capabilities
        )
        if not capabilities:
            raise MultiAgentRuntimeError("an agent requires at least one capability")
        object.__setattr__(self, "allowed_capabilities", capabilities)

    def canonical(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "allowed_capabilities": sorted(self.allowed_capabilities),
        }


@dataclass(frozen=True, slots=True)
class AgentDeploymentRecord:
    identity: AgentIdentity
    deployment_id: str
    model_revision_sha256: str

    def __post_init__(self) -> None:
        _text(self.deployment_id, "deployment_id")
        if not _is_sha256(self.model_revision_sha256):
            raise MultiAgentRuntimeError(
                "model_revision_sha256 must be a canonical sha256"
            )

    def canonical(self) -> dict[str, Any]:
        return {
            **self.identity.canonical(),
            "deployment_id": self.deployment_id,
            "model_revision_sha256": self.model_revision_sha256,
        }


@dataclass(frozen=True, slots=True)
class AgentBinding:
    identity: AgentIdentity
    port: CellPort
    deployment_id: str
    model_revision_sha256: str

    def __post_init__(self) -> None:
        self.manifest()

    def manifest(self) -> AgentDeploymentRecord:
        return AgentDeploymentRecord(
            identity=self.identity,
            deployment_id=self.deployment_id,
            model_revision_sha256=self.model_revision_sha256,
        )


@dataclass(frozen=True, slots=True)
class ExecutionBudget:
    step_budget: int
    context_byte_budget: int = 16_777_216
    response_byte_budget: int = 4_194_304
    message_byte_budget: int = 4_194_304

    def __post_init__(self) -> None:
        for field in (
            "step_budget",
            "context_byte_budget",
            "response_byte_budget",
            "message_byte_budget",
        ):
            _positive_int(getattr(self, field), field)

    def canonical(self) -> dict[str, Any]:
        return {
            "step_budget": self.step_budget,
            "context_byte_budget": self.context_byte_budget,
            "response_byte_budget": self.response_byte_budget,
            "message_byte_budget": self.message_byte_budget,
        }


@dataclass(frozen=True, slots=True)
class ExecutionUsage:
    steps: int
    context_bytes: int
    response_bytes: int
    message_bytes: int

    def __post_init__(self) -> None:
        for field in ("steps", "context_bytes", "response_bytes", "message_bytes"):
            _nonnegative_int(getattr(self, field), field)

    def canonical(self) -> dict[str, Any]:
        return {
            "steps": self.steps,
            "context_bytes": self.context_bytes,
            "response_bytes": self.response_bytes,
            "message_bytes": self.message_bytes,
        }


def _strict_output_object(text: str) -> dict[str, Any]:
    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise MultiAgentRuntimeError(
                    "model response contains a duplicate JSON key"
                )
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise MultiAgentRuntimeError(
            f"model response contains non-finite JSON value {value!r}"
        )

    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicate,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise MultiAgentRuntimeError(
            f"model returned invalid JSON without an exact output object: {error}"
        ) from error
    if not isinstance(value, dict) or set(value) != {"output"}:
        raise MultiAgentRuntimeError(
            "model response must be exactly one JSON object with only output"
        )
    canonical_json_bytes(value)
    return value


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


class JsonMultiAgentCellPort:
    """Bridge structured HSWM cell steps through a text ``CellPort``.

    ``OpenAICompatibleCellPort`` consumes chat messages and returns a packet with
    text plus model/usage metadata.  ``MultiAgentHSWM`` instead consumes and
    produces structured JSON packets.  This adapter is the strict seam between
    those contracts; it does not repair markdown or permissively extract JSON.
    """

    def __init__(
        self,
        port: CellPort,
        *,
        max_response_bytes: int = 1_048_576,
    ) -> None:
        if (
            isinstance(max_response_bytes, bool)
            or not isinstance(max_response_bytes, int)
            or max_response_bytes <= 0
        ):
            raise MultiAgentRuntimeError("max_response_bytes must be positive")
        self.port = port
        self.max_response_bytes = max_response_bytes
        self.calls = 0

    def invoke(self, effect: InvokeCellEffect) -> PacketEnvelope:
        if effect.input.packet_type != MULTIAGENT_STEP_REQUEST_TYPE:
            raise MultiAgentRuntimeError(
                "JSON multi-agent adapter received the wrong request packet type"
            )
        if effect.expected_output_type != MULTIAGENT_STEP_RESPONSE_TYPE:
            raise MultiAgentRuntimeError(
                "JSON multi-agent adapter received the wrong response contract"
            )
        try:
            input_digest = canonical_sha256(effect.input.payload)
        except (TypeError, ValueError) as error:
            raise MultiAgentRuntimeError("multi-agent request is not JSON") from error
        if effect.input.payload_sha256 != input_digest:
            raise MultiAgentRuntimeError("multi-agent request payload digest mismatch")
        if not isinstance(effect.input.payload, Mapping):
            raise MultiAgentRuntimeError("multi-agent request payload must be an object")

        canonical_request = canonical_json_bytes(effect.input.payload)
        bridge_seed = {
            "adapter": MULTIAGENT_JSON_ADAPTER_VERSION,
            "outer_activation_id": effect.activation_id,
            "outer_cell_id": effect.cell_id,
            "outer_packet_id": effect.input.packet_id,
            "outer_payload_sha256": effect.input.payload_sha256,
        }
        bridge_activation_id = "multiagent-json-" + canonical_sha256(bridge_seed)[:24]
        bridge_input = make_packet(
            packet_id=f"request:{bridge_activation_id}",
            packet_type=MULTIAGENT_JSON_REQUEST_TYPE,
            payload={
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Execute the frozen HSWM structural cell described by the "
                            "user JSON. Use only its visible tokens, memories, and "
                            "inbound messages. Return exactly one JSON object with "
                            "the single key output. Do not use markdown."
                        ),
                    },
                    {
                        "role": "user",
                        "content": canonical_request.decode("utf-8"),
                    },
                ]
            },
            provenance=bridge_seed,
        )
        bridge_effect = InvokeCellEffect(
            activation_id=bridge_activation_id,
            cell_id=effect.cell_id,
            input=bridge_input,
            expected_output_type=MULTIAGENT_JSON_RESPONSE_TYPE,
        )
        dispatched_effect = _detached_effect(bridge_effect)
        dispatched_effect_bytes = canonical_json_bytes(
            _effect_manifest(dispatched_effect)
        )
        self.calls += 1
        try:
            raw = self.port.invoke(dispatched_effect)
        finally:
            _require_unchanged_effect(
                dispatched_effect,
                dispatched_effect_bytes,
                label="underlying cell port",
            )
        if not isinstance(raw, PacketEnvelope):
            raise MultiAgentRuntimeError("underlying cell port did not return a packet")
        if raw.packet_type != MULTIAGENT_JSON_RESPONSE_TYPE:
            raise MultiAgentRuntimeError(
                "underlying cell port returned the wrong packet type"
            )
        try:
            raw_payload_bytes = canonical_json_bytes(raw.payload)
        except (TypeError, ValueError) as error:
            raise MultiAgentRuntimeError(
                "underlying cell port returned a non-JSON payload"
            ) from error
        if raw.payload_sha256 != canonical_sha256(raw.payload):
            raise MultiAgentRuntimeError(
                "underlying cell port response payload digest mismatch"
            )
        if not _is_sha256(raw.provenance_sha256):
            raise MultiAgentRuntimeError(
                "underlying response provenance is not a canonical sha256"
            )
        if len(raw_payload_bytes) > self.max_response_bytes:
            raise MultiAgentRuntimeError(
                "underlying cell port response exceeds the byte budget"
            )
        payload = raw.payload
        required = {"text", "model", "usage", "response_sha256"}
        if not isinstance(payload, Mapping) or set(payload) != required:
            raise MultiAgentRuntimeError(
                "underlying response does not match the OpenAI adapter payload"
            )
        text = payload["text"]
        if not isinstance(text, str) or not text.strip():
            raise MultiAgentRuntimeError("underlying response text is empty or invalid")
        if len(text.encode("utf-8")) > self.max_response_bytes:
            raise MultiAgentRuntimeError("model JSON response exceeds the byte budget")
        model = payload["model"]
        if not isinstance(model, str) or not model.strip():
            raise MultiAgentRuntimeError("underlying response model is invalid")
        usage = payload["usage"]
        if usage is not None and not isinstance(usage, Mapping):
            raise MultiAgentRuntimeError("underlying response usage is invalid")
        try:
            usage = _json_copy(usage)
        except (TypeError, ValueError) as error:
            raise MultiAgentRuntimeError("underlying response usage is not JSON") from error
        response_sha256 = payload["response_sha256"]
        if not _is_sha256(response_sha256):
            raise MultiAgentRuntimeError(
                "underlying response digest is not a canonical sha256"
            )

        parsed = _strict_output_object(text)
        output = _json_copy(parsed["output"])
        provenance = {
            "adapter": MULTIAGENT_JSON_ADAPTER_VERSION,
            "outer_activation_id": effect.activation_id,
            "outer_cell_id": effect.cell_id,
            "outer_packet_id": effect.input.packet_id,
            "outer_payload_sha256": effect.input.payload_sha256,
            "bridge_request_packet_id": bridge_input.packet_id,
            "bridge_request_payload_sha256": bridge_input.payload_sha256,
            "underlying": {
                "packet_id": raw.packet_id,
                "packet_type": raw.packet_type,
                "payload_sha256": raw.payload_sha256,
                "provenance_sha256": raw.provenance_sha256,
                "model": model,
                "usage": usage,
                "response_sha256": response_sha256,
            },
        }
        output_payload = {"output": output}
        packet_seed = {
            "provenance_sha256": canonical_sha256(provenance),
            "output_payload_sha256": canonical_sha256(output_payload),
        }
        return make_packet(
            packet_id="multiagent-json-" + canonical_sha256(packet_seed)[:24],
            packet_type=effect.expected_output_type,
            payload=output_payload,
            provenance=provenance,
        )


@dataclass(frozen=True, slots=True)
class AgentMessage:
    message_id: str
    episode_id: str
    plan_id: str
    source_cell_id: str
    target_cell_id: str
    sender_agent_id: str
    recipient_agent_id: str
    payload: Any
    payload_sha256: str
    schema_version: str = MULTIAGENT_MESSAGE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field in (
            "message_id",
            "episode_id",
            "plan_id",
            "source_cell_id",
            "target_cell_id",
            "sender_agent_id",
            "recipient_agent_id",
            "payload_sha256",
        ):
            _text(getattr(self, field), field)
        if not _is_sha256(self.message_id) or not _is_sha256(self.plan_id):
            raise MultiAgentRuntimeError(
                "message_id and plan_id must be canonical sha256 values"
            )
        if not _is_sha256(self.payload_sha256):
            raise MultiAgentRuntimeError("payload_sha256 must be a canonical sha256")
        if self.schema_version != MULTIAGENT_MESSAGE_SCHEMA_VERSION:
            raise MultiAgentRuntimeError("unsupported message schema")
        if canonical_sha256(self.payload) != self.payload_sha256:
            raise MultiAgentRuntimeError("message payload digest mismatch")
        if canonical_sha256(self.unsigned()) != self.message_id:
            raise MultiAgentRuntimeError("message identity digest mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "plan_id": self.plan_id,
            "source_cell_id": self.source_cell_id,
            "target_cell_id": self.target_cell_id,
            "sender_agent_id": self.sender_agent_id,
            "recipient_agent_id": self.recipient_agent_id,
            "payload": self.payload,
            "payload_sha256": self.payload_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "message_id": self.message_id}


def _make_message(
    *,
    episode_id: str,
    plan_id: str,
    source_cell_id: str,
    target_cell_id: str,
    sender_agent_id: str,
    recipient_agent_id: str,
    payload: Any,
) -> AgentMessage:
    payload = _json_copy(payload)
    unsigned = {
        "schema_version": MULTIAGENT_MESSAGE_SCHEMA_VERSION,
        "episode_id": episode_id,
        "plan_id": plan_id,
        "source_cell_id": source_cell_id,
        "target_cell_id": target_cell_id,
        "sender_agent_id": sender_agent_id,
        "recipient_agent_id": recipient_agent_id,
        "payload": payload,
        "payload_sha256": canonical_sha256(payload),
    }
    return AgentMessage(message_id=canonical_sha256(unsigned), **unsigned)


@dataclass(frozen=True, slots=True)
class CellStepReceipt:
    receipt_id: str
    sequence: int
    cell_id: str
    agent_id: str
    capability: str
    input_packet_id: str
    input_payload_sha256: str
    output_packet_id: str
    output_payload_sha256: str
    output_provenance_sha256: str
    output: Any
    context_bytes: int
    response_bytes: int
    message_bytes: int
    visible_token_ids: tuple[str, ...]
    used_memory_ids: tuple[str, ...]
    inbound_message_ids: tuple[str, ...]
    outbound_message_ids: tuple[str, ...]
    schema_version: str = MULTIAGENT_STEP_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence <= 0
        ):
            raise MultiAgentRuntimeError("step sequence must be positive")
        for field in (
            "receipt_id",
            "cell_id",
            "agent_id",
            "capability",
            "input_packet_id",
            "input_payload_sha256",
            "output_packet_id",
            "output_payload_sha256",
            "output_provenance_sha256",
        ):
            _text(getattr(self, field), field)
        if not _is_sha256(self.receipt_id):
            raise MultiAgentRuntimeError("receipt_id must be a canonical sha256")
        for field in (
            "input_payload_sha256",
            "output_payload_sha256",
            "output_provenance_sha256",
        ):
            if not _is_sha256(getattr(self, field)):
                raise MultiAgentRuntimeError(
                    f"{field} must be a canonical sha256"
                )
        canonical_json_bytes(self.output)
        if canonical_sha256({"output": self.output}) != self.output_payload_sha256:
            raise MultiAgentRuntimeError("step output differs from its packet digest")
        for field in ("context_bytes", "response_bytes", "message_bytes"):
            _nonnegative_int(getattr(self, field), field)
        if self.context_bytes == 0:
            raise MultiAgentRuntimeError("step context accounting must be non-zero")
        if self.response_bytes != len(
            canonical_json_bytes({"output": self.output})
        ):
            raise MultiAgentRuntimeError("step response byte accounting is invalid")
        for field in (
            "visible_token_ids",
            "used_memory_ids",
            "inbound_message_ids",
            "outbound_message_ids",
        ):
            values = _strings(getattr(self, field), field)
            object.__setattr__(self, field, values)
        if self.schema_version != MULTIAGENT_STEP_SCHEMA_VERSION:
            raise MultiAgentRuntimeError("unsupported step receipt schema")
        if canonical_sha256(self.unsigned()) != self.receipt_id:
            raise MultiAgentRuntimeError("step receipt digest mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "sequence": self.sequence,
            "cell_id": self.cell_id,
            "agent_id": self.agent_id,
            "capability": self.capability,
            "input_packet_id": self.input_packet_id,
            "input_payload_sha256": self.input_payload_sha256,
            "output_packet_id": self.output_packet_id,
            "output_payload_sha256": self.output_payload_sha256,
            "output_provenance_sha256": self.output_provenance_sha256,
            "output": self.output,
            "context_bytes": self.context_bytes,
            "response_bytes": self.response_bytes,
            "message_bytes": self.message_bytes,
            "visible_token_ids": list(self.visible_token_ids),
            "used_memory_ids": list(self.used_memory_ids),
            "inbound_message_ids": list(self.inbound_message_ids),
            "outbound_message_ids": list(self.outbound_message_ids),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_id": self.receipt_id}


def _make_step_receipt(**fields: Any) -> CellStepReceipt:
    unsigned = {"schema_version": MULTIAGENT_STEP_SCHEMA_VERSION, **fields}
    return CellStepReceipt(receipt_id=canonical_sha256(unsigned), **unsigned)


@dataclass(frozen=True, slots=True)
class MultiAgentEpisodeReceipt:
    receipt_id: str
    episode_id: str
    used_snapshot_id: str
    used_generation: int
    plan_id: str
    agent_registry: tuple[AgentDeploymentRecord, ...]
    agent_registry_sha256: str
    input_token_ids: tuple[str, ...]
    input_scopes: tuple[InputScopeManifest, ...]
    input_scope_sha256: str
    route_cell_ids: tuple[str, ...]
    leaf_cell_ids: tuple[str, ...]
    executed_agent_ids: tuple[str, ...]
    step_receipts: tuple[CellStepReceipt, ...]
    messages: tuple[AgentMessage, ...]
    output_token: CognitiveToken
    budget: ExecutionBudget
    usage: ExecutionUsage
    schema_version: str = MULTIAGENT_EXECUTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field in (
            "receipt_id",
            "episode_id",
            "used_snapshot_id",
            "plan_id",
            "agent_registry_sha256",
            "input_scope_sha256",
        ):
            _text(getattr(self, field), field)
        for field in (
            "receipt_id",
            "used_snapshot_id",
            "plan_id",
            "agent_registry_sha256",
            "input_scope_sha256",
        ):
            if not _is_sha256(getattr(self, field)):
                raise MultiAgentRuntimeError(f"{field} must be a canonical sha256")
        for field in (
            "input_token_ids",
            "route_cell_ids",
            "leaf_cell_ids",
            "executed_agent_ids",
        ):
            values = _strings(getattr(self, field), field)
            object.__setattr__(self, field, values)
        if (
            isinstance(self.used_generation, bool)
            or not isinstance(self.used_generation, int)
            or self.used_generation < 0
        ):
            raise MultiAgentRuntimeError("used_generation must be non-negative")
        recomputed_usage = ExecutionUsage(
            steps=len(self.step_receipts),
            context_bytes=sum(step.context_bytes for step in self.step_receipts),
            response_bytes=sum(
                len(canonical_json_bytes({"output": step.output}))
                for step in self.step_receipts
            ),
            message_bytes=sum(
                len(canonical_json_bytes(message.canonical()))
                for message in self.messages
            ),
        )
        if self.usage != recomputed_usage or sum(
            step.response_bytes for step in self.step_receipts
        ) != self.usage.response_bytes or sum(
            step.message_bytes for step in self.step_receipts
        ) != self.usage.message_bytes:
            raise MultiAgentRuntimeError("aggregate budget accounting is invalid")
        if (
            self.usage.steps > self.budget.step_budget
            or self.usage.context_bytes > self.budget.context_byte_budget
            or self.usage.response_bytes > self.budget.response_byte_budget
            or self.usage.message_bytes > self.budget.message_byte_budget
        ):
            raise MultiAgentRuntimeError("execution usage exceeds its aggregate budget")
        if self.schema_version != MULTIAGENT_EXECUTION_SCHEMA_VERSION:
            raise MultiAgentRuntimeError("unsupported multi-agent receipt schema")
        if self.output_token.episode_id != self.episode_id:
            raise MultiAgentRuntimeError("aggregate output belongs to another episode")
        if not self.input_token_ids or not self.route_cell_ids:
            raise MultiAgentRuntimeError("receipt input and route must be non-empty")
        registry_ids = tuple(item.identity.agent_id for item in self.agent_registry)
        if len(registry_ids) != len(set(registry_ids)):
            raise MultiAgentRuntimeError("receipt agent registry contains duplicates")
        if canonical_sha256(
            [item.canonical() for item in self.agent_registry]
        ) != self.agent_registry_sha256:
            raise MultiAgentRuntimeError("receipt agent registry digest mismatch")
        if tuple(scope.token_id for scope in self.input_scopes) != self.input_token_ids:
            raise MultiAgentRuntimeError("receipt input scope order is invalid")
        if canonical_sha256(
            [scope.canonical() for scope in self.input_scopes]
        ) != self.input_scope_sha256:
            raise MultiAgentRuntimeError("receipt input scope digest mismatch")
        try:
            token_from_mapping(self.output_token.canonical())
        except ValueError as error:
            raise MultiAgentRuntimeError(f"invalid aggregate output token: {error}") from error
        if tuple(step.sequence for step in self.step_receipts) != tuple(
            range(1, len(self.step_receipts) + 1)
        ):
            raise MultiAgentRuntimeError("step receipts are not in execution order")
        if tuple(step.cell_id for step in self.step_receipts) != self.route_cell_ids:
            raise MultiAgentRuntimeError("step receipts differ from the frozen route")
        if set(self.leaf_cell_ids) - set(self.route_cell_ids):
            raise MultiAgentRuntimeError("leaf cells must belong to the route")
        actual_agents = tuple(sorted({step.agent_id for step in self.step_receipts}))
        if tuple(sorted(self.executed_agent_ids)) != actual_agents:
            raise MultiAgentRuntimeError("executed agent identity set is invalid")
        registry_by_id = {
            entry.identity.agent_id: entry for entry in self.agent_registry
        }
        if not set(actual_agents) <= set(registry_by_id):
            raise MultiAgentRuntimeError("step names an agent outside the registry")

        message_by_id = {message.message_id: message for message in self.messages}
        if len(message_by_id) != len(self.messages):
            raise MultiAgentRuntimeError("message identities must be unique")
        step_by_cell = {step.cell_id: step for step in self.step_receipts}
        if len(step_by_cell) != len(self.step_receipts):
            raise MultiAgentRuntimeError("route cell identities must be unique")
        inbound_references: list[str] = []
        outbound_references: list[str] = []
        for message in self.messages:
            if canonical_sha256(message.unsigned()) != message.message_id:
                raise MultiAgentRuntimeError("nested message identity mismatch")
            if (
                message.episode_id != self.episode_id
                or message.plan_id != self.plan_id
            ):
                raise MultiAgentRuntimeError("message belongs to another execution")
            source = step_by_cell.get(message.source_cell_id)
            target = step_by_cell.get(message.target_cell_id)
            if source is None or target is None:
                raise MultiAgentRuntimeError("message crosses outside the frozen route")
            if source.sequence >= target.sequence:
                raise MultiAgentRuntimeError("message edge is not forward in the route")
            if (
                source.agent_id != message.sender_agent_id
                or target.agent_id != message.recipient_agent_id
            ):
                raise MultiAgentRuntimeError("message identity differs from cell bindings")
            if (
                message.message_id not in source.outbound_message_ids
                or message.message_id not in target.inbound_message_ids
            ):
                raise MultiAgentRuntimeError("message is missing from a step receipt")
            if canonical_json_bytes(message.payload) != canonical_json_bytes(
                source.output
            ):
                raise MultiAgentRuntimeError("message payload differs from source output")
        for step in self.step_receipts:
            if canonical_sha256(step.unsigned()) != step.receipt_id:
                raise MultiAgentRuntimeError("nested step receipt identity mismatch")
            deployment = registry_by_id[step.agent_id]
            if step.capability not in deployment.identity.allowed_capabilities:
                raise MultiAgentRuntimeError("step exceeds its agent capability scope")
            expected_visible = tuple(
                scope.token_id
                for scope in self.input_scopes
                if scope.visibility is TokenVisibility.PUBLIC
                or scope.owner_agent_id == step.agent_id
            )
            if step.visible_token_ids != expected_visible:
                raise MultiAgentRuntimeError("step violates direct-input visibility")
            inbound_references.extend(step.inbound_message_ids)
            outbound_references.extend(step.outbound_message_ids)
        if self.step_receipts[0].inbound_message_ids or any(
            not step.inbound_message_ids for step in self.step_receipts[1:]
        ):
            raise MultiAgentRuntimeError(
                "receipt route must have one root and connected later steps"
            )
        if (
            len(inbound_references) != len(set(inbound_references))
            or len(outbound_references) != len(set(outbound_references))
            or set(inbound_references) != set(message_by_id)
            or set(outbound_references) != set(message_by_id)
        ):
            raise MultiAgentRuntimeError("step receipts reference an unknown message")
        for step in self.step_receipts:
            expected_message_bytes = sum(
                len(canonical_json_bytes(message_by_id[message_id].canonical()))
                for message_id in step.outbound_message_ids
            )
            if step.message_bytes != expected_message_bytes:
                raise MultiAgentRuntimeError(
                    "step message byte accounting is invalid"
                )
        actual_leaves = tuple(
            step.cell_id for step in self.step_receipts if not step.outbound_message_ids
        )
        if self.leaf_cell_ids != actual_leaves:
            raise MultiAgentRuntimeError("receipt leaf cells differ from message topology")
        predecessor_ids = {
            cell_id: tuple(
                sorted(
                    message.source_cell_id
                    for message in self.messages
                    if message.target_cell_id == cell_id
                )
            )
            for cell_id in self.route_cell_ids
        }
        expected_plan_id = canonical_sha256(
            _execution_plan_preimage(
                snapshot_id=self.used_snapshot_id,
                entry_cell_id=self.route_cell_ids[0],
                route_cell_ids=self.route_cell_ids,
                predecessor_ids=predecessor_ids,
                leaf_cell_ids=self.leaf_cell_ids,
            )
        )
        if self.plan_id != expected_plan_id:
            raise MultiAgentRuntimeError(
                "execution plan identity differs from the receipt topology"
            )
        expected_output = {
            "leaf_outputs": [
                {
                    "cell_id": step.cell_id,
                    "agent_id": step.agent_id,
                    "output": step.output,
                }
                for step in self.step_receipts
                if step.cell_id in self.leaf_cell_ids
            ]
        }
        if canonical_json_bytes(self.output_token.content) != canonical_json_bytes(
            expected_output
        ):
            raise MultiAgentRuntimeError("aggregate output is not linked to leaf outputs")
        expected_output_provenance = {
            "protocol": MULTIAGENT_EXECUTION_SCHEMA_VERSION,
            "snapshot_id": self.used_snapshot_id,
            "generation": self.used_generation,
            "plan_id": self.plan_id,
            "route_cell_ids": list(self.route_cell_ids),
            "executed_agent_ids": sorted(self.executed_agent_ids),
        }
        if self.output_token.provenance_sha256 != canonical_sha256(
            expected_output_provenance
        ):
            raise MultiAgentRuntimeError(
                "aggregate output provenance is not linked to the execution plan"
            )
        if canonical_sha256(self.unsigned()) != self.receipt_id:
            raise MultiAgentRuntimeError("multi-agent episode receipt digest mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "used_snapshot_id": self.used_snapshot_id,
            "used_generation": self.used_generation,
            "plan_id": self.plan_id,
            "agent_registry": [item.canonical() for item in self.agent_registry],
            "agent_registry_sha256": self.agent_registry_sha256,
            "input_token_ids": list(self.input_token_ids),
            "input_scopes": [scope.canonical() for scope in self.input_scopes],
            "input_scope_sha256": self.input_scope_sha256,
            "route_cell_ids": list(self.route_cell_ids),
            "leaf_cell_ids": list(self.leaf_cell_ids),
            "executed_agent_ids": list(self.executed_agent_ids),
            "step_receipts": [step.canonical() for step in self.step_receipts],
            "messages": [message.canonical() for message in self.messages],
            "output_token": self.output_token.canonical(),
            "budget": self.budget.canonical(),
            "usage": self.usage.canonical(),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_id": self.receipt_id}


@dataclass(frozen=True, slots=True)
class _ExecutionPlan:
    plan_id: str
    cell_by_id: Mapping[str, CellRecord]
    route_cell_ids: tuple[str, ...]
    predecessor_ids: Mapping[str, tuple[str, ...]]
    leaf_cell_ids: tuple[str, ...]


def _execution_plan_preimage(
    *,
    snapshot_id: str,
    entry_cell_id: str,
    route_cell_ids: Sequence[str],
    predecessor_ids: Mapping[str, Sequence[str]],
    leaf_cell_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema_version": "hswm-execution-plan/v1",
        "engine": "multiagent-dag/v1",
        "snapshot_id": snapshot_id,
        "entry_cell_id": entry_cell_id,
        "route_cell_ids": list(route_cell_ids),
        "predecessor_cell_ids": [
            {
                "cell_id": cell_id,
                "predecessor_cell_ids": list(predecessor_ids[cell_id]),
            }
            for cell_id in route_cell_ids
        ],
        "leaf_cell_ids": list(leaf_cell_ids),
    }


def _project_execution_plan(snapshot: SelfModelSnapshot) -> _ExecutionPlan:
    if not snapshot.cells or snapshot.entry_cell_id is None:
        raise MultiAgentRuntimeError(
            "multi-agent execution requires an active HSWM cell topology"
        )
    cell_by_id = {cell.cell_id: cell for cell in snapshot.cells}
    reachable: set[str] = set()
    stack = [snapshot.entry_cell_id]
    while stack:
        cell_id = stack.pop()
        if cell_id in reachable:
            continue
        reachable.add(cell_id)
        stack.extend(reversed(cell_by_id[cell_id].next_cell_ids))

    predecessor_sets: dict[str, set[str]] = {cell_id: set() for cell_id in reachable}
    for source_id in reachable:
        for target_id in cell_by_id[source_id].next_cell_ids:
            if target_id in reachable:
                predecessor_sets[target_id].add(source_id)

    indegrees = {
        cell_id: len(predecessors)
        for cell_id, predecessors in predecessor_sets.items()
    }
    ready = [cell_id for cell_id, degree in indegrees.items() if degree == 0]
    heapq.heapify(ready)
    ordered: list[str] = []
    while ready:
        source_id = heapq.heappop(ready)
        ordered.append(source_id)
        for target_id in cell_by_id[source_id].next_cell_ids:
            if target_id not in indegrees:
                continue
            indegrees[target_id] -= 1
            if indegrees[target_id] == 0:
                heapq.heappush(ready, target_id)
    if len(ordered) != len(reachable):
        raise MultiAgentRuntimeError(
            "multi-agent fan-out/fan-in execution requires an acyclic cell topology"
        )
    if not ordered or ordered[0] != snapshot.entry_cell_id:
        raise MultiAgentRuntimeError("the entry cell is not a valid DAG root")
    leaves = tuple(
        cell_id
        for cell_id in ordered
        if not any(target in reachable for target in cell_by_id[cell_id].next_cell_ids)
    )
    predecessor_ids = {
        cell_id: tuple(sorted(predecessors))
        for cell_id, predecessors in predecessor_sets.items()
    }
    plan_preimage = _execution_plan_preimage(
        snapshot_id=snapshot.snapshot_id,
        entry_cell_id=snapshot.entry_cell_id,
        route_cell_ids=ordered,
        predecessor_ids=predecessor_ids,
        leaf_cell_ids=leaves,
    )
    return _ExecutionPlan(
        plan_id=canonical_sha256(plan_preimage),
        cell_by_id=cell_by_id,
        route_cell_ids=tuple(ordered),
        predecessor_ids=predecessor_ids,
        leaf_cell_ids=leaves,
    )


class MultiAgentHSWM:
    """Execute a deterministic projection of frozen structural HSWM state."""

    def __init__(
        self,
        store: SQLiteSelfModelStore,
        *,
        agents: Sequence[AgentBinding],
        journal: SQLiteMultiAgentJournal | None = None,
    ) -> None:
        if not agents:
            raise MultiAgentRuntimeError("at least one agent binding is required")
        bindings: dict[str, AgentBinding] = {}
        for binding in agents:
            agent_id = binding.identity.agent_id
            if agent_id in bindings:
                raise MultiAgentRuntimeError("agent identities must be unique")
            bindings[agent_id] = binding
        self.store = store
        self._bindings = bindings
        self.journal = journal or SQLiteMultiAgentJournal(
            store.path.with_name(store.path.name + ".multiagent.sqlite3")
        )

    def _registry_manifest(self) -> tuple[AgentDeploymentRecord, ...]:
        return tuple(
            self._bindings[agent_id].manifest()
            for agent_id in sorted(self._bindings)
        )

    def _registry_digest(self) -> str:
        return canonical_sha256(
            [item.canonical() for item in self._registry_manifest()]
        )

    def _preflight(
        self,
        *,
        episode_id: str,
        inputs: Sequence[ScopedToken],
        budget: ExecutionBudget,
        pinned_intent: Mapping[str, Any] | None = None,
    ) -> tuple[ActiveSnapshot, tuple[ScopedToken, ...], _ExecutionPlan]:
        _text(episode_id, "episode_id")
        if not isinstance(budget, ExecutionBudget):
            raise MultiAgentRuntimeError("budget must be an ExecutionBudget")
        if not inputs:
            raise MultiAgentRuntimeError("multi-agent execution requires input tokens")

        frozen_inputs: list[ScopedToken] = []
        for scoped in inputs:
            try:
                token = token_from_mapping(_json_copy(scoped.token.canonical()))
            except ValueError as error:
                raise MultiAgentRuntimeError(f"invalid input token: {error}") from error
            frozen_inputs.append(
                ScopedToken(
                    token=token,
                    visibility=scoped.visibility,
                    owner_agent_id=scoped.owner_agent_id,
                )
            )
        frozen_inputs.sort(key=lambda item: (item.token.position, item.token.token_id))
        tokens = tuple(item.token for item in frozen_inputs)
        if any(token.episode_id != episode_id for token in tokens):
            raise MultiAgentRuntimeError("every token must belong to the episode")
        if len({token.token_id for token in tokens}) != len(tokens):
            raise MultiAgentRuntimeError("input token identities must be unique")
        if len({token.position for token in tokens}) != len(tokens):
            raise MultiAgentRuntimeError("input token positions must be unique")
        for scoped in frozen_inputs:
            if (
                scoped.visibility is TokenVisibility.DIRECT_ONLY
                and scoped.owner_agent_id not in self._bindings
            ):
                raise MultiAgentRuntimeError("a direct-only token names an unknown owner")

        if pinned_intent is None:
            loaded = self.store.active_snapshot()
        else:
            snapshot_id = pinned_intent.get("snapshot_id")
            generation = pinned_intent.get("generation")
            _text(snapshot_id, "pinned snapshot_id")
            _nonnegative_int(generation, "pinned generation")
            loaded = ActiveSnapshot(
                snapshot=self.store.load_snapshot(snapshot_id),
                generation=generation,
                policy=self.store.policy,
            )
        try:
            snapshot = snapshot_from_mapping(_json_copy(loaded.snapshot.canonical()))
        except ValueError as error:
            raise MultiAgentRuntimeError(f"active snapshot is invalid: {error}") from error
        active = ActiveSnapshot(
            snapshot=snapshot,
            generation=loaded.generation,
            policy=loaded.policy,
        )
        plan = _project_execution_plan(snapshot)
        if len(plan.route_cell_ids) > budget.step_budget:
            raise MultiAgentRuntimeError(
                "frozen cell route exceeds the aggregate step budget"
            )

        memory_ids = {memory.memory_id for memory in snapshot.memories}
        for cell_id in plan.route_cell_ids:
            cell = plan.cell_by_id[cell_id]
            if cell.executor_agent_id is None:
                raise MultiAgentRuntimeError(
                    f"structural cell {cell_id!r} has no executor binding"
                )
            binding = self._bindings.get(cell.executor_agent_id)
            if binding is None:
                raise MultiAgentRuntimeError(
                    f"structural cell {cell_id!r} names an unknown executor"
                )
            if cell.capability not in active.policy.allowed_capabilities:
                raise MultiAgentRuntimeError(
                    f"structural cell {cell_id!r} exceeds store capability authority"
                )
            if cell.capability not in binding.identity.allowed_capabilities:
                raise MultiAgentRuntimeError(
                    f"structural cell {cell_id!r} is unauthorized for its executor"
                )
            if not set(cell.memory_ids) <= memory_ids:
                raise MultiAgentRuntimeError(
                    f"structural cell {cell_id!r} references missing memory"
                )
        return active, tuple(frozen_inputs), plan

    @staticmethod
    def _validate_frozen_execution(
        *,
        active: ActiveSnapshot,
        inputs: Sequence[ScopedToken],
        input_packet: PacketEnvelope,
        input_packet_bytes: bytes,
    ) -> None:
        try:
            snapshot_from_mapping(_json_copy(active.snapshot.canonical()))
            for scoped in inputs:
                token_from_mapping(_json_copy(scoped.token.canonical()))
            if canonical_json_bytes(_packet_manifest(input_packet)) != input_packet_bytes:
                raise MultiAgentRuntimeError("agent port mutated its request packet")
        except ValueError as error:
            raise MultiAgentRuntimeError("frozen execution state was mutated") from error

    @staticmethod
    def _validate_output_packet(
        output_packet: object,
        *,
        policy_byte_limit: int,
    ) -> PacketEnvelope:
        if not isinstance(output_packet, PacketEnvelope):
            raise MultiAgentRuntimeError("agent port did not return a packet")
        if output_packet.packet_type != MULTIAGENT_STEP_RESPONSE_TYPE:
            raise MultiAgentRuntimeError("agent port returned the wrong packet type")
        if output_packet.payload_sha256 != canonical_sha256(output_packet.payload):
            raise MultiAgentRuntimeError("agent port output payload digest mismatch")
        if not _is_sha256(output_packet.payload_sha256):
            raise MultiAgentRuntimeError(
                "agent port output payload digest is not a canonical sha256"
            )
        if not _is_sha256(output_packet.provenance_sha256):
            raise MultiAgentRuntimeError(
                "agent port output provenance is not a canonical sha256"
            )
        if (
            not isinstance(output_packet.payload, Mapping)
            or set(output_packet.payload) != {"output"}
        ):
            raise MultiAgentRuntimeError(
                "agent port response must contain exactly one output field"
            )
        if len(canonical_json_bytes(output_packet.payload)) > policy_byte_limit:
            raise MultiAgentRuntimeError("agent port response exceeds the byte budget")
        return output_packet

    def run_episode(
        self,
        *,
        episode_id: str,
        inputs: Sequence[ScopedToken],
        budget: ExecutionBudget,
    ) -> MultiAgentEpisodeReceipt:
        """Run or resume the projected cell DAG without repeating an effect."""

        existing = self.journal.execution_record(episode_id=episode_id)
        active, frozen_inputs, plan = self._preflight(
            episode_id=episode_id,
            inputs=inputs,
            budget=budget,
            pinned_intent=existing.intent if existing is not None else None,
        )
        registry = self._registry_manifest()
        scopes = tuple(scoped.scope_manifest() for scoped in frozen_inputs)
        execution_intent = {
            "schema_version": MULTIAGENT_EXECUTION_SCHEMA_VERSION,
            "episode_id": episode_id,
            "snapshot_id": active.snapshot.snapshot_id,
            "generation": active.generation,
            "plan_id": plan.plan_id,
            "agent_registry": [item.canonical() for item in registry],
            "input_scopes": [scope.canonical() for scope in scopes],
            "route_cell_ids": list(plan.route_cell_ids),
            "budget": budget.canonical(),
        }
        execution = self.journal.reserve_execution(
            episode_id=episode_id,
            intent=execution_intent,
        )
        if execution.status is ExecutionStatus.COMPLETED:
            if execution.receipt is None:
                raise MultiAgentRuntimeError("completed journal entry has no receipt")
            return multiagent_receipt_from_mapping(execution.receipt)
        if execution.status is not ExecutionStatus.ACTIVE:
            raise MultiAgentRuntimeError(
                f"execution is {execution.status.value}; reconciliation is required"
            )
        try:
            self.store.append_tokens(tuple(scoped.token for scoped in frozen_inputs))
        except SelfModelStoreError as error:
            reason = f"input token persistence failed permanently: {error}"
            self.journal.fail_execution(episode_id=episode_id, reason=reason)
            raise MultiAgentRuntimeError(reason) from error
        memory_by_id: dict[str, MemoryRecord] = {
            memory.memory_id: memory for memory in active.snapshot.memories
        }
        inbound_by_cell: dict[str, list[AgentMessage]] = {
            cell_id: [] for cell_id in plan.route_cell_ids
        }
        outputs: dict[str, Any] = {}
        messages: list[AgentMessage] = []
        step_receipts: list[CellStepReceipt] = []
        output_packet_ids: set[str] = set()
        context_bytes_used = 0
        response_bytes_used = 0
        message_bytes_used = 0

        for sequence, cell_id in enumerate(plan.route_cell_ids, start=1):
            cell = plan.cell_by_id[cell_id]
            agent_id = cell.executor_agent_id
            if agent_id is None:  # The complete route was checked before side effects.
                raise MultiAgentRuntimeError("frozen cell lost its executor binding")
            binding = self._bindings[agent_id]
            visible = tuple(
                scoped.token
                for scoped in frozen_inputs
                if scoped.visibility is TokenVisibility.PUBLIC
                or scoped.owner_agent_id == agent_id
            )
            inbound = tuple(
                sorted(
                    inbound_by_cell[cell_id],
                    key=lambda message: (
                        message.source_cell_id,
                        message.sender_agent_id,
                        message.message_id,
                    ),
                )
            )
            expected_predecessors = plan.predecessor_ids[cell_id]
            if tuple(message.source_cell_id for message in inbound) != expected_predecessors:
                raise MultiAgentRuntimeError("fan-in is missing a predecessor message")
            request_payload = _json_copy({
                "protocol": MULTIAGENT_EXECUTION_SCHEMA_VERSION,
                "episode_id": episode_id,
                "snapshot_id": active.snapshot.snapshot_id,
                "generation": active.generation,
                "plan_id": plan.plan_id,
                "cell": cell.canonical(),
                "agent": binding.manifest().canonical(),
                "visible_tokens": [token.canonical() for token in visible],
                "memories": [
                    memory_by_id[memory_id].canonical()
                    for memory_id in cell.memory_ids
                ],
                "inbound_messages": [message.canonical() for message in inbound],
            })
            step_context_bytes = len(canonical_json_bytes(request_payload))
            context_bytes_used += step_context_bytes
            if context_bytes_used > budget.context_byte_budget:
                reason = "aggregate context byte budget exceeded"
                self.journal.fail_execution(episode_id=episode_id, reason=reason)
                raise MultiAgentRuntimeError(reason)
            activation_seed = {
                "episode_id": episode_id,
                "snapshot_id": active.snapshot.snapshot_id,
                "plan_id": plan.plan_id,
                "structural_cell_id": cell_id,
                "agent_id": agent_id,
                "deployment": binding.manifest().canonical(),
                "registry_sha256": self._registry_digest(),
                "request_sha256": canonical_sha256(request_payload),
            }
            activation_id = "multiagent-" + canonical_sha256(activation_seed)[:24]
            input_packet = make_packet(
                packet_id=f"request:{activation_id}",
                packet_type=MULTIAGENT_STEP_REQUEST_TYPE,
                payload=request_payload,
                provenance=activation_seed,
            )
            input_packet_bytes = canonical_json_bytes(_packet_manifest(input_packet))
            effect = InvokeCellEffect(
                activation_id=activation_id,
                cell_id=agent_id,
                input=input_packet,
                expected_output_type=MULTIAGENT_STEP_RESPONSE_TYPE,
            )
            step = self.journal.reserve_step(
                episode_id=episode_id,
                sequence=sequence,
                cell_id=cell_id,
                effect=effect,
            )
            freshly_dispatched = False
            if step.status is JournalStepStatus.SUCCEEDED:
                if step.output is None:
                    raise MultiAgentRuntimeError("journal step has no stored output")
                output_packet = step.output
            elif step.status is JournalStepStatus.PENDING:
                claim_token = "claim-" + canonical_sha256(
                    {
                        "episode_id": episode_id,
                        "sequence": sequence,
                        "effect": step.effect_sha256,
                    }
                )[:24]
                self.journal.claim_step(
                    episode_id=episode_id,
                    sequence=sequence,
                    claim_token=claim_token,
                )
                dispatched_effect = _detached_effect(effect)
                dispatched_effect_bytes = canonical_json_bytes(
                    _effect_manifest(dispatched_effect)
                )
                try:
                    try:
                        output_packet = binding.port.invoke(dispatched_effect)
                    finally:
                        _require_unchanged_effect(
                            dispatched_effect,
                            dispatched_effect_bytes,
                            label="agent port",
                        )
                        self._validate_frozen_execution(
                            active=active,
                            inputs=frozen_inputs,
                            input_packet=input_packet,
                            input_packet_bytes=input_packet_bytes,
                        )
                    output_packet = self._validate_output_packet(
                        output_packet,
                        policy_byte_limit=active.policy.max_token_bytes,
                    )
                except BaseException as error:
                    self.journal.mark_step_failure(
                        episode_id=episode_id,
                        sequence=sequence,
                        claim_token=claim_token,
                        reason=f"{type(error).__name__}: {error}",
                        safe_to_retry=bool(getattr(error, "safe_to_retry", False)),
                    )
                    if isinstance(error, MultiAgentRuntimeError):
                        raise
                    raise MultiAgentRuntimeError(
                        f"agent {agent_id!r} failed at cell {cell_id!r}; "
                        "outcome requires reconciliation"
                    ) from error
                self.journal.complete_step(
                    episode_id=episode_id,
                    sequence=sequence,
                    claim_token=claim_token,
                    output=output_packet,
                )
                freshly_dispatched = True
            else:
                raise MultiAgentRuntimeError(
                    f"step {sequence} is {step.status.value}; "
                    "external dispatch is forbidden until reconciliation"
                )
            if not freshly_dispatched:
                output_packet = self._validate_output_packet(
                    output_packet,
                    policy_byte_limit=active.policy.max_token_bytes,
                )
                self._validate_frozen_execution(
                    active=active,
                    inputs=frozen_inputs,
                    input_packet=input_packet,
                    input_packet_bytes=input_packet_bytes,
                )
            if output_packet.packet_id in output_packet_ids:
                reason = "agent ports reused an output packet identity"
                self.journal.fail_execution(episode_id=episode_id, reason=reason)
                raise MultiAgentRuntimeError(reason)
            output_packet_ids.add(output_packet.packet_id)
            step_response_bytes = len(canonical_json_bytes(output_packet.payload))
            response_bytes_used += step_response_bytes
            if response_bytes_used > budget.response_byte_budget:
                reason = "aggregate response byte budget exceeded"
                self.journal.fail_execution(episode_id=episode_id, reason=reason)
                raise MultiAgentRuntimeError(reason)
            output = _json_copy(output_packet.payload["output"])
            outputs[cell_id] = output

            outbound: list[AgentMessage] = []
            step_message_bytes = 0
            for target_cell_id in cell.next_cell_ids:
                if target_cell_id not in inbound_by_cell:
                    continue
                recipient_id = plan.cell_by_id[target_cell_id].executor_agent_id
                if recipient_id is None:
                    raise MultiAgentRuntimeError("target cell lost its executor binding")
                message = _make_message(
                    episode_id=episode_id,
                    plan_id=plan.plan_id,
                    source_cell_id=cell_id,
                    target_cell_id=target_cell_id,
                    sender_agent_id=agent_id,
                    recipient_agent_id=recipient_id,
                    payload=output,
                )
                inbound_by_cell[target_cell_id].append(message)
                messages.append(message)
                outbound.append(message)
                encoded_message_bytes = len(canonical_json_bytes(message.canonical()))
                step_message_bytes += encoded_message_bytes
                message_bytes_used += encoded_message_bytes
            if message_bytes_used > budget.message_byte_budget:
                reason = "aggregate message byte budget exceeded"
                self.journal.fail_execution(episode_id=episode_id, reason=reason)
                raise MultiAgentRuntimeError(reason)

            step_receipts.append(
                _make_step_receipt(
                    sequence=sequence,
                    cell_id=cell_id,
                    agent_id=agent_id,
                    capability=cell.capability,
                    input_packet_id=input_packet.packet_id,
                    input_payload_sha256=input_packet.payload_sha256,
                    output_packet_id=output_packet.packet_id,
                    output_payload_sha256=output_packet.payload_sha256,
                    output_provenance_sha256=output_packet.provenance_sha256,
                    output=output,
                    context_bytes=step_context_bytes,
                    response_bytes=step_response_bytes,
                    message_bytes=step_message_bytes,
                    visible_token_ids=tuple(token.token_id for token in visible),
                    used_memory_ids=cell.memory_ids,
                    inbound_message_ids=tuple(message.message_id for message in inbound),
                    outbound_message_ids=tuple(
                        message.message_id for message in outbound
                    ),
                )
            )

        aggregate_output = {
            "leaf_outputs": [
                {
                    "cell_id": cell_id,
                    "agent_id": plan.cell_by_id[cell_id].executor_agent_id,
                    "output": outputs[cell_id],
                }
                for cell_id in plan.leaf_cell_ids
            ]
        }
        output_position = max(scoped.token.position for scoped in frozen_inputs) + 1
        output_provenance = {
            "protocol": MULTIAGENT_EXECUTION_SCHEMA_VERSION,
            "snapshot_id": active.snapshot.snapshot_id,
            "generation": active.generation,
            "plan_id": plan.plan_id,
            "route_cell_ids": list(plan.route_cell_ids),
            "executed_agent_ids": sorted(
                {
                    plan.cell_by_id[cell_id].executor_agent_id
                    for cell_id in plan.route_cell_ids
                }
            ),
        }
        output_seed = {
            "episode_id": episode_id,
            "position": output_position,
            "content": aggregate_output,
            "provenance": output_provenance,
        }
        output_token = make_token(
            token_id="multiagent-" + canonical_sha256(output_seed)[:24],
            episode_id=episode_id,
            position=output_position,
            role="agent",
            content=aggregate_output,
            provenance=output_provenance,
        )
        if len(canonical_json_bytes(output_token.canonical())) > active.policy.max_token_bytes:
            reason = "aggregate output token exceeds the store byte budget"
            self.journal.fail_execution(episode_id=episode_id, reason=reason)
            raise MultiAgentRuntimeError(reason)
        try:
            self.store.append_tokens((output_token,))
        except SelfModelStoreError as error:
            reason = f"aggregate output persistence failed permanently: {error}"
            self.journal.fail_execution(episode_id=episode_id, reason=reason)
            raise MultiAgentRuntimeError(reason) from error

        usage = ExecutionUsage(
            steps=len(step_receipts),
            context_bytes=context_bytes_used,
            response_bytes=response_bytes_used,
            message_bytes=message_bytes_used,
        )

        unsigned = {
            "schema_version": MULTIAGENT_EXECUTION_SCHEMA_VERSION,
            "episode_id": episode_id,
            "used_snapshot_id": active.snapshot.snapshot_id,
            "used_generation": active.generation,
            "plan_id": plan.plan_id,
            "agent_registry": [item.canonical() for item in registry],
            "agent_registry_sha256": self._registry_digest(),
            "input_token_ids": [scoped.token.token_id for scoped in frozen_inputs],
            "input_scopes": [scope.canonical() for scope in scopes],
            "input_scope_sha256": canonical_sha256(
                [scope.canonical() for scope in scopes]
            ),
            "route_cell_ids": list(plan.route_cell_ids),
            "leaf_cell_ids": list(plan.leaf_cell_ids),
            "executed_agent_ids": sorted(
                {step.agent_id for step in step_receipts}
            ),
            "step_receipts": [step.canonical() for step in step_receipts],
            "messages": [message.canonical() for message in messages],
            "output_token": output_token.canonical(),
            "budget": budget.canonical(),
            "usage": usage.canonical(),
        }
        receipt = MultiAgentEpisodeReceipt(
            receipt_id=canonical_sha256(unsigned),
            episode_id=episode_id,
            used_snapshot_id=active.snapshot.snapshot_id,
            used_generation=active.generation,
            plan_id=plan.plan_id,
            agent_registry=registry,
            agent_registry_sha256=unsigned["agent_registry_sha256"],
            input_token_ids=tuple(unsigned["input_token_ids"]),
            input_scopes=scopes,
            input_scope_sha256=unsigned["input_scope_sha256"],
            route_cell_ids=plan.route_cell_ids,
            leaf_cell_ids=plan.leaf_cell_ids,
            executed_agent_ids=tuple(unsigned["executed_agent_ids"]),
            step_receipts=tuple(step_receipts),
            messages=tuple(messages),
            output_token=output_token,
            budget=budget,
            usage=usage,
        )
        self.journal.complete_execution(
            episode_id=episode_id,
            receipt=receipt.canonical(),
        )
        return receipt


def _message_from_mapping(value: Mapping[str, Any]) -> AgentMessage:
    expected = {
        "schema_version",
        "message_id",
        "episode_id",
        "plan_id",
        "source_cell_id",
        "target_cell_id",
        "sender_agent_id",
        "recipient_agent_id",
        "payload",
        "payload_sha256",
    }
    _fields(value, expected, "message")
    return AgentMessage(**value)


def _step_from_mapping(value: Mapping[str, Any]) -> CellStepReceipt:
    expected = {
        "schema_version",
        "receipt_id",
        "sequence",
        "cell_id",
        "agent_id",
        "capability",
        "input_packet_id",
        "input_payload_sha256",
        "output_packet_id",
        "output_payload_sha256",
        "output_provenance_sha256",
        "output",
        "context_bytes",
        "response_bytes",
        "message_bytes",
        "visible_token_ids",
        "used_memory_ids",
        "inbound_message_ids",
        "outbound_message_ids",
    }
    _fields(value, expected, "step receipt")
    return CellStepReceipt(
        receipt_id=value["receipt_id"],
        sequence=value["sequence"],
        cell_id=value["cell_id"],
        agent_id=value["agent_id"],
        capability=value["capability"],
        input_packet_id=value["input_packet_id"],
        input_payload_sha256=value["input_payload_sha256"],
        output_packet_id=value["output_packet_id"],
        output_payload_sha256=value["output_payload_sha256"],
        output_provenance_sha256=value["output_provenance_sha256"],
        output=_json_copy(value["output"]),
        context_bytes=value["context_bytes"],
        response_bytes=value["response_bytes"],
        message_bytes=value["message_bytes"],
        visible_token_ids=_strings(value["visible_token_ids"], "visible_token_ids"),
        used_memory_ids=_strings(value["used_memory_ids"], "used_memory_ids"),
        inbound_message_ids=_strings(
            value["inbound_message_ids"], "inbound_message_ids"
        ),
        outbound_message_ids=_strings(
            value["outbound_message_ids"], "outbound_message_ids"
        ),
        schema_version=value["schema_version"],
    )


def _deployment_from_mapping(value: Mapping[str, Any]) -> AgentDeploymentRecord:
    expected = {
        "agent_id",
        "allowed_capabilities",
        "deployment_id",
        "model_revision_sha256",
    }
    _fields(value, expected, "agent deployment")
    return AgentDeploymentRecord(
        identity=AgentIdentity(
            agent_id=value["agent_id"],
            allowed_capabilities=frozenset(
                _strings(value["allowed_capabilities"], "allowed_capabilities")
            ),
        ),
        deployment_id=value["deployment_id"],
        model_revision_sha256=value["model_revision_sha256"],
    )


def _scope_from_mapping(value: Mapping[str, Any]) -> InputScopeManifest:
    expected = {"token_id", "token_sha256", "visibility", "owner_agent_id"}
    _fields(value, expected, "input scope")
    try:
        visibility = TokenVisibility(value["visibility"])
    except (TypeError, ValueError) as error:
        raise MultiAgentRuntimeError("input scope visibility is invalid") from error
    return InputScopeManifest(
        token_id=value["token_id"],
        token_sha256=value["token_sha256"],
        visibility=visibility,
        owner_agent_id=value["owner_agent_id"],
    )


def _budget_from_mapping(value: Mapping[str, Any]) -> ExecutionBudget:
    expected = {
        "step_budget",
        "context_byte_budget",
        "response_byte_budget",
        "message_byte_budget",
    }
    _fields(value, expected, "execution budget")
    return ExecutionBudget(**value)


def _usage_from_mapping(value: Mapping[str, Any]) -> ExecutionUsage:
    expected = {"steps", "context_bytes", "response_bytes", "message_bytes"}
    _fields(value, expected, "execution usage")
    return ExecutionUsage(**value)


def multiagent_receipt_from_mapping(
    value: Mapping[str, Any],
) -> MultiAgentEpisodeReceipt:
    """Rehydrate and verify a content-addressed execution receipt."""

    try:
        value = _json_copy(value)
    except (TypeError, ValueError) as error:
        raise MultiAgentRuntimeError("receipt is not canonical JSON data") from error

    expected = {
        "schema_version",
        "receipt_id",
        "episode_id",
        "used_snapshot_id",
        "used_generation",
        "plan_id",
        "agent_registry",
        "agent_registry_sha256",
        "input_token_ids",
        "input_scopes",
        "input_scope_sha256",
        "route_cell_ids",
        "leaf_cell_ids",
        "executed_agent_ids",
        "step_receipts",
        "messages",
        "output_token",
        "budget",
        "usage",
    }
    _fields(value, expected, "multi-agent receipt")
    raw_steps = value["step_receipts"]
    raw_messages = value["messages"]
    raw_registry = value["agent_registry"]
    raw_scopes = value["input_scopes"]
    if any(
        not isinstance(item, list)
        for item in (raw_steps, raw_messages, raw_registry, raw_scopes)
    ):
        raise MultiAgentRuntimeError("receipt nested collections must be arrays")
    if not isinstance(value["output_token"], Mapping):
        raise MultiAgentRuntimeError("receipt output token must be an object")
    try:
        output_token = token_from_mapping(value["output_token"])
    except ValueError as error:
        raise MultiAgentRuntimeError(f"invalid receipt output token: {error}") from error
    return MultiAgentEpisodeReceipt(
        receipt_id=value["receipt_id"],
        episode_id=value["episode_id"],
        used_snapshot_id=value["used_snapshot_id"],
        used_generation=value["used_generation"],
        plan_id=value["plan_id"],
        agent_registry=tuple(
            _deployment_from_mapping(item) for item in raw_registry
        ),
        agent_registry_sha256=value["agent_registry_sha256"],
        input_token_ids=_strings(value["input_token_ids"], "input_token_ids"),
        input_scopes=tuple(_scope_from_mapping(item) for item in raw_scopes),
        input_scope_sha256=value["input_scope_sha256"],
        route_cell_ids=_strings(value["route_cell_ids"], "route_cell_ids"),
        leaf_cell_ids=_strings(value["leaf_cell_ids"], "leaf_cell_ids"),
        executed_agent_ids=_strings(value["executed_agent_ids"], "executed_agent_ids"),
        step_receipts=tuple(_step_from_mapping(item) for item in raw_steps),
        messages=tuple(_message_from_mapping(item) for item in raw_messages),
        output_token=output_token,
        budget=_budget_from_mapping(value["budget"]),
        usage=_usage_from_mapping(value["usage"]),
        schema_version=value["schema_version"],
    )


__all__ = [
    "AgentBinding",
    "AgentDeploymentRecord",
    "AgentIdentity",
    "AgentMessage",
    "ExecutionBudget",
    "ExecutionUsage",
    "InputScopeManifest",
    "JsonMultiAgentCellPort",
    "MULTIAGENT_EXECUTION_SCHEMA_VERSION",
    "MULTIAGENT_JSON_ADAPTER_VERSION",
    "MULTIAGENT_JSON_REQUEST_TYPE",
    "MULTIAGENT_JSON_RESPONSE_TYPE",
    "MULTIAGENT_MESSAGE_SCHEMA_VERSION",
    "MULTIAGENT_STEP_REQUEST_TYPE",
    "MULTIAGENT_STEP_RESPONSE_TYPE",
    "MULTIAGENT_STEP_SCHEMA_VERSION",
    "MultiAgentEpisodeReceipt",
    "MultiAgentHSWM",
    "MultiAgentRuntimeError",
    "CellStepReceipt",
    "ScopedToken",
    "TokenVisibility",
    "multiagent_receipt_from_mapping",
]
