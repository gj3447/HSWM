"""Token-native, agent-authored self-modification runtime for HSWM.

The foundation agent, not this module, writes the durable memory records and
the episode harness.  This runtime owns only the constitutional mechanics:
typed token admission, authority/budget checks, immutable snapshot selection,
execution receipts, and compare-and-swap activation of an agent proposal.

Passing these contracts is engineering evidence that self-modification is
possible.  It is not evidence that the resulting memory is useful or that a
continual-learning curve is positive.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Protocol, Sequence

from hswm.cells.runtime import CellPort, InvokeCellEffect, make_packet

from .contracts import (
    ActiveSnapshot,
    ActivationReceipt,
    CognitiveToken,
    ExecutorAuthority,
    HarnessDocument,
    HarnessMode,
    MemoryRecord,
    MutationProposal,
    SelfModelSnapshot,
    canonical_json_bytes,
    canonical_sha256,
    harness_from_mapping,
    make_mutation,
    make_token,
    memory_from_mapping,
    snapshot_from_mapping,
    token_from_mapping,
)
from .store import SQLiteSelfModelStore


EXECUTION_SCHEMA_VERSION = "hswm-selfmod-execution/v1"
AUTHORING_SCHEMA_VERSION = "hswm-selfmod-authoring/v1"


class SelfModRuntimeError(RuntimeError):
    """The agent response cannot cross the fixed execution boundary."""


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SelfModRuntimeError(f"{name} must be a non-empty string")


def _validate_frozen_request(
    active: ActiveSnapshot, tokens: Sequence[CognitiveToken]
) -> None:
    """Reject caller or agent mutation of a supposedly frozen episode view."""

    try:
        snapshot_from_mapping(active.snapshot.canonical())
        for token in tokens:
            token_from_mapping(token.canonical())
    except ValueError as error:
        raise SelfModRuntimeError("frozen episode state was mutated") from error


def _validate_proposal_scope(
    proposal: MutationProposal,
    *,
    active: ActiveSnapshot,
    tokens: Sequence[CognitiveToken],
    agent_registry: Sequence[ExecutorAuthority] = (),
) -> None:
    if (
        proposal.base_snapshot_id != active.snapshot.snapshot_id
        or proposal.expected_generation != active.generation
    ):
        raise SelfModRuntimeError("proposal does not target the supplied snapshot")
    admitted = {token.token_id for token in tokens}
    if not set(proposal.source_token_ids) <= admitted:
        raise SelfModRuntimeError("proposal cites tokens outside its authoring request")
    for memory in proposal.upsert_memories:
        if not set(memory.source_token_ids) <= set(proposal.source_token_ids):
            raise SelfModRuntimeError(
                "memory provenance exceeds the proposal source scope"
            )
    harness = proposal.harness
    if harness is not None:
        bound_nodes = tuple(
            node for node in harness.nodes if node.executor_agent_id is not None
        )
        if bound_nodes:
            registry = {item.agent_id: item for item in agent_registry}
            if not registry:
                raise SelfModRuntimeError(
                    "an executor-bound harness requires a frozen agent registry"
                )
            for node in bound_nodes:
                authority = registry.get(node.executor_agent_id)
                if authority is None:
                    raise SelfModRuntimeError(
                        "harness executor is outside the authoring registry"
                    )
                if node.capability not in authority.allowed_capabilities:
                    raise SelfModRuntimeError(
                        "harness capability exceeds its executor authority"
                    )


def _string_tuple(
    value: object, label: str, *, unique: bool = True
) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise SelfModRuntimeError(f"{label} must be a list of non-empty strings")
    if unique and len(value) != len(set(value)):
        raise SelfModRuntimeError(f"{label} must not contain duplicates")
    return tuple(value)


def _strict_json_object(text: str) -> dict[str, Any]:
    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SelfModRuntimeError(f"agent JSON repeats key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=reject_duplicate)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SelfModRuntimeError(f"agent returned invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise SelfModRuntimeError("agent response must be one JSON object")
    canonical_json_bytes(value)
    return value


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """One frozen episode view; ``budget`` bounds traversed harness nodes."""

    episode_id: str
    active: ActiveSnapshot
    tokens: tuple[CognitiveToken, ...]
    capabilities: tuple[str, ...]
    budget: int

    def __post_init__(self) -> None:
        _require_text("episode_id", self.episode_id)
        if not self.tokens:
            raise SelfModRuntimeError("an episode requires at least one input token")
        if any(token.episode_id != self.episode_id for token in self.tokens):
            raise SelfModRuntimeError("every input token must belong to the episode")
        if not self.capabilities:
            raise SelfModRuntimeError("capabilities must be non-empty and unique")
        for capability in self.capabilities:
            _require_text("capability", capability)
        if len(self.capabilities) != len(set(self.capabilities)):
            raise SelfModRuntimeError("capabilities must be non-empty and unique")
        object.__setattr__(self, "capabilities", tuple(sorted(self.capabilities)))
        if (
            isinstance(self.budget, bool)
            or not isinstance(self.budget, int)
            or self.budget <= 0
        ):
            raise SelfModRuntimeError("budget must be positive")
        _validate_frozen_request(self.active, self.tokens)


@dataclass(frozen=True, slots=True)
class AuthoringRequest:
    active: ActiveSnapshot
    tokens: tuple[CognitiveToken, ...]
    agent_registry: tuple[ExecutorAuthority, ...] = ()

    def __post_init__(self) -> None:
        if not self.tokens:
            raise SelfModRuntimeError("self-authoring requires at least one token")
        ordered = tuple(sorted(self.agent_registry, key=lambda item: item.agent_id))
        if len(ordered) != len({item.agent_id for item in ordered}):
            raise SelfModRuntimeError("agent registry identities must be unique")
        for authority in ordered:
            if not set(authority.allowed_capabilities) <= set(
                self.active.policy.allowed_capabilities
            ):
                raise SelfModRuntimeError(
                    "agent registry exceeds the active capability policy"
                )
        object.__setattr__(self, "agent_registry", ordered)
        _validate_frozen_request(self.active, self.tokens)


@dataclass(frozen=True, slots=True)
class AgentDecision:
    selected_capability: str
    output: Any
    used_memory_ids: tuple[str, ...] = ()
    followed_node_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text("selected_capability", self.selected_capability)
        canonical_json_bytes(self.output)
        for label, values in (
            ("used_memory_ids", self.used_memory_ids),
            ("followed_node_ids", self.followed_node_ids),
        ):
            if isinstance(values, (str, bytes)):
                raise SelfModRuntimeError(f"{label} must be a sequence")
            if any(not isinstance(value, str) or not value for value in values):
                raise SelfModRuntimeError(f"{label} must contain non-empty strings")
            object.__setattr__(self, label, tuple(values))
        if len(self.used_memory_ids) != len(set(self.used_memory_ids)):
            raise SelfModRuntimeError("used_memory_ids must not contain duplicates")


class SelfModifyingAgent(Protocol):
    """An intelligent agent that executes and rewrites its own HSWM harness."""

    agent_id: str

    def decide(self, request: ExecutionRequest) -> AgentDecision:
        ...

    def author(self, request: AuthoringRequest) -> MutationProposal | None:
        ...


@dataclass(frozen=True, slots=True)
class EpisodeReceipt:
    receipt_id: str
    episode_id: str
    agent_id: str
    used_snapshot_id: str
    used_generation: int
    harness_id: str | None
    input_token_ids: tuple[str, ...]
    input_content_sha256: str
    output_token: CognitiveToken
    selected_capability: str
    used_memory_ids: tuple[str, ...]
    followed_node_ids: tuple[str, ...]
    capability_set_sha256: str
    budget: int
    activation: ActivationReceipt | None
    schema_version: str = EXECUTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field in (
            "receipt_id",
            "episode_id",
            "agent_id",
            "used_snapshot_id",
            "input_content_sha256",
            "selected_capability",
            "capability_set_sha256",
        ):
            _require_text(field, getattr(self, field))
        if self.harness_id is not None:
            _require_text("harness_id", self.harness_id)
        if (
            isinstance(self.used_generation, bool)
            or not isinstance(self.used_generation, int)
            or self.used_generation < 0
        ):
            raise SelfModRuntimeError("used_generation must be non-negative")
        if isinstance(self.budget, bool) or not isinstance(self.budget, int) or self.budget <= 0:
            raise SelfModRuntimeError("budget must be positive")
        if not self.input_token_ids or any(
            not isinstance(token_id, str) or not token_id
            for token_id in self.input_token_ids
        ):
            raise SelfModRuntimeError("receipt input tokens are invalid")
        if self.output_token.episode_id != self.episode_id:
            raise SelfModRuntimeError("receipt output belongs to another episode")
        if self.schema_version != EXECUTION_SCHEMA_VERSION:
            raise SelfModRuntimeError("unsupported execution receipt schema")
        if self.activation is not None and (
            self.activation.base_snapshot_id != self.used_snapshot_id
            or self.activation.base_generation != self.used_generation
        ):
            raise SelfModRuntimeError("receipt activation does not follow its snapshot")
        if canonical_sha256(self.unsigned()) != self.receipt_id:
            raise SelfModRuntimeError("execution receipt digest mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "agent_id": self.agent_id,
            "used_snapshot_id": self.used_snapshot_id,
            "used_generation": self.used_generation,
            "harness_id": self.harness_id,
            "input_token_ids": list(self.input_token_ids),
            "input_content_sha256": self.input_content_sha256,
            "output_token": self.output_token.canonical(),
            "selected_capability": self.selected_capability,
            "used_memory_ids": list(self.used_memory_ids),
            "followed_node_ids": list(self.followed_node_ids),
            "capability_set_sha256": self.capability_set_sha256,
            "budget": self.budget,
            "activation": (
                self.activation.canonical() if self.activation is not None else None
            ),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_id": self.receipt_id}


def _memory_map(snapshot: SelfModelSnapshot) -> dict[str, MemoryRecord]:
    return {memory.memory_id: memory for memory in snapshot.memories}


def _harness_map(harness: HarnessDocument) -> dict[str, Any]:
    return {node.node_id: node for node in harness.nodes}


def validate_agent_decision(
    *,
    request: ExecutionRequest,
    decision: AgentDecision,
    agent_id: str | None = None,
) -> None:
    """Prove that the selected route stayed inside state and authority bounds."""

    allowed = set(request.capabilities)
    policy_allowed = set(request.active.policy.allowed_capabilities)
    if not allowed <= policy_allowed:
        raise SelfModRuntimeError("episode capabilities exceed store authority")
    if decision.selected_capability not in allowed:
        raise SelfModRuntimeError("agent selected an unauthorized capability")

    snapshot = request.active.snapshot
    memories = _memory_map(snapshot)
    if any(memory_id not in memories for memory_id in decision.used_memory_ids):
        raise SelfModRuntimeError("agent claimed a memory absent from the snapshot")

    harness = snapshot.harness
    if harness is None:
        if decision.followed_node_ids:
            raise SelfModRuntimeError("agent claimed harness nodes in an empty harness")
        if request.budget < 1:
            raise SelfModRuntimeError("episode action exceeds its budget")
        return

    nodes = _harness_map(harness)
    followed = decision.followed_node_ids
    if not followed:
        raise SelfModRuntimeError("an active harness requires an explicit node trace")
    if followed[0] != harness.entry_node_id:
        raise SelfModRuntimeError("harness trace must begin at its entry node")
    for node_id in followed:
        if node_id not in nodes:
            raise SelfModRuntimeError("harness trace names an unknown node")
        if nodes[node_id].capability not in allowed:
            raise SelfModRuntimeError(
                "harness trace invokes a capability outside the episode authority"
            )
        executor = nodes[node_id].executor_agent_id
        if executor is not None and executor != agent_id:
            raise SelfModRuntimeError(
                "executor-bound harness nodes require their bound agent; "
                "use MultiAgentHSWM for a multi-agent route"
            )
    if len(followed) > request.budget:
        raise SelfModRuntimeError("harness trace exceeds the episode budget")
    for left, right in zip(followed, followed[1:]):
        if right not in nodes[left].next_node_ids:
            raise SelfModRuntimeError("harness trace crosses an undeclared edge")
    if nodes[followed[-1]].capability != decision.selected_capability:
        raise SelfModRuntimeError(
            "selected capability differs from the final harness node"
        )
    reachable_memory_ids = {
        memory_id
        for node_id in followed
        for memory_id in nodes[node_id].memory_ids
    }
    if not set(decision.used_memory_ids) <= reachable_memory_ids:
        raise SelfModRuntimeError(
            "agent used memory not admitted by the followed harness route"
        )


def _input_content_sha256(tokens: Sequence[CognitiveToken]) -> str:
    return canonical_sha256(
        [
            {
                "position": token.position,
                "role": token.role,
                "content": token.content,
            }
            for token in sorted(tokens, key=lambda item: item.position)
        ]
    )


def _make_episode_receipt(
    *,
    request: ExecutionRequest,
    agent_id: str,
    decision: AgentDecision,
    output_token: CognitiveToken,
    activation: ActivationReceipt | None,
) -> EpisodeReceipt:
    harness = request.active.snapshot.harness
    unsigned = {
        "schema_version": EXECUTION_SCHEMA_VERSION,
        "episode_id": request.episode_id,
        "agent_id": agent_id,
        "used_snapshot_id": request.active.snapshot.snapshot_id,
        "used_generation": request.active.generation,
        "harness_id": harness.harness_id if harness is not None else None,
        "input_token_ids": [token.token_id for token in request.tokens],
        "input_content_sha256": _input_content_sha256(request.tokens),
        "output_token": output_token.canonical(),
        "selected_capability": decision.selected_capability,
        "used_memory_ids": list(decision.used_memory_ids),
        "followed_node_ids": list(decision.followed_node_ids),
        "capability_set_sha256": canonical_sha256(list(request.capabilities)),
        "budget": request.budget,
        "activation": activation.canonical() if activation is not None else None,
    }
    return EpisodeReceipt(
        receipt_id=canonical_sha256(unsigned),
        episode_id=request.episode_id,
        agent_id=agent_id,
        used_snapshot_id=request.active.snapshot.snapshot_id,
        used_generation=request.active.generation,
        harness_id=harness.harness_id if harness is not None else None,
        input_token_ids=tuple(token.token_id for token in request.tokens),
        input_content_sha256=unsigned["input_content_sha256"],
        output_token=output_token,
        selected_capability=decision.selected_capability,
        used_memory_ids=decision.used_memory_ids,
        followed_node_ids=decision.followed_node_ids,
        capability_set_sha256=unsigned["capability_set_sha256"],
        budget=request.budget,
        activation=activation,
    )


class SelfModifyingHSWM:
    """Execute a snapshot, then let the same agent author its successor."""

    def __init__(self, store: SQLiteSelfModelStore) -> None:
        self.store = store

    def absorb(
        self,
        tokens: Sequence[CognitiveToken],
        *,
        agent: SelfModifyingAgent,
        agent_registry: Sequence[ExecutorAuthority] = (),
    ) -> ActivationReceipt | None:
        """Let typed tokens become agent-authored memory without an outcome gate."""

        ordered = tuple(sorted(tokens, key=lambda token: token.position))
        if not ordered:
            raise SelfModRuntimeError("absorb requires at least one token")
        _require_text("agent.agent_id", agent.agent_id)
        self.store.append_tokens(ordered)
        active = self.store.active_snapshot()
        authoring = AuthoringRequest(
            active=active,
            tokens=ordered,
            agent_registry=tuple(agent_registry),
        )
        proposal = agent.author(authoring)
        _validate_frozen_request(active, ordered)
        if proposal is None:
            return None
        if proposal.author_id != agent.agent_id:
            raise SelfModRuntimeError("proposal author differs from executing agent")
        _validate_proposal_scope(
            proposal,
            active=active,
            tokens=ordered,
            agent_registry=authoring.agent_registry,
        )
        return self.store.commit(proposal)

    def run_episode(
        self,
        *,
        episode_id: str,
        tokens: Sequence[CognitiveToken],
        agent: SelfModifyingAgent,
        capabilities: Sequence[str],
        budget: int,
        learn_after: bool = True,
        agent_registry: Sequence[ExecutorAuthority] = (),
    ) -> EpisodeReceipt:
        """Run with a frozen snapshot and optionally commit the agent's rewrite."""

        _require_text("agent.agent_id", agent.agent_id)
        ordered = tuple(sorted(tokens, key=lambda token: token.position))
        active = self.store.active_snapshot()
        request = ExecutionRequest(
            episode_id=episode_id,
            active=active,
            tokens=ordered,
            capabilities=tuple(capabilities),
            budget=budget,
        )
        self.store.append_tokens(ordered)
        decision = agent.decide(request)
        _validate_frozen_request(active, ordered)
        validate_agent_decision(
            request=request,
            decision=decision,
            agent_id=agent.agent_id,
        )

        output_position = max(token.position for token in ordered) + 1
        output_provenance = {
            "protocol": EXECUTION_SCHEMA_VERSION,
            "agent_id": agent.agent_id,
            "used_snapshot_id": active.snapshot.snapshot_id,
            "used_generation": active.generation,
            "selected_capability": decision.selected_capability,
            "used_memory_ids": list(decision.used_memory_ids),
            "followed_node_ids": list(decision.followed_node_ids),
        }
        output_seed = {
            "episode_id": episode_id,
            "position": output_position,
            "content": decision.output,
            "provenance": output_provenance,
        }
        output_token = make_token(
            token_id="agent-" + canonical_sha256(output_seed)[:24],
            episode_id=episode_id,
            position=output_position,
            role="agent",
            content=decision.output,
            provenance=output_provenance,
        )
        self.store.append_tokens((output_token,))

        activation: ActivationReceipt | None = None
        if learn_after:
            authoring_tokens = (*ordered, output_token)
            authoring = AuthoringRequest(
                active=active,
                tokens=authoring_tokens,
                agent_registry=tuple(agent_registry),
            )
            proposal = agent.author(authoring)
            _validate_frozen_request(active, authoring_tokens)
            if proposal is not None:
                if proposal.author_id != agent.agent_id:
                    raise SelfModRuntimeError(
                        "proposal author differs from executing agent"
                    )
                _validate_proposal_scope(
                    proposal,
                    active=active,
                    tokens=authoring_tokens,
                    agent_registry=authoring.agent_registry,
                )
                activation = self.store.commit(proposal)

        return _make_episode_receipt(
            request=request,
            agent_id=agent.agent_id,
            decision=decision,
            output_token=output_token,
            activation=activation,
        )


def _snapshot_prompt_value(snapshot: SelfModelSnapshot) -> dict[str, Any]:
    return snapshot.canonical()


class JsonSelfModifyingAgent:
    """Strict JSON bridge from any ``CellPort`` to the self-modification API.

    The prompts define only the data protocol and fixed authority boundary.  The
    agent authors every memory item, instruction, route, and state deletion.
    """

    def __init__(self, *, agent_id: str, port: CellPort) -> None:
        _require_text("agent_id", agent_id)
        self.agent_id = agent_id
        self.port = port

    def _invoke(
        self,
        *,
        operation: str,
        value: Mapping[str, Any],
        max_response_bytes: int,
    ) -> dict[str, Any]:
        input_bytes = canonical_json_bytes(value)
        activation_id = "selfmod-" + sha256(
            operation.encode("utf-8") + b"\0" + input_bytes
        ).hexdigest()[:24]
        effect = InvokeCellEffect(
            activation_id=activation_id,
            cell_id=self.agent_id,
            input=make_packet(
                packet_id=f"packet-{activation_id}",
                packet_type=f"hswm-selfmod-{operation}-request/v1",
                payload={
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Return exactly one JSON object matching the "
                                "provided response contract. Do not use markdown."
                            ),
                        },
                        {
                            "role": "user",
                            "content": input_bytes.decode("utf-8"),
                        },
                    ]
                },
                provenance={
                    "protocol": AUTHORING_SCHEMA_VERSION,
                    "operation": operation,
                    "agent_id": self.agent_id,
                },
            ),
            expected_output_type=f"hswm-selfmod-{operation}-response/v1",
        )
        packet = self.port.invoke(effect)
        if packet.packet_type != effect.expected_output_type:
            raise SelfModRuntimeError(
                "cell port returned an unexpected response packet type"
            )
        if packet.payload_sha256 != sha256(canonical_json_bytes(packet.payload)).hexdigest():
            raise SelfModRuntimeError("cell port response payload digest mismatch")
        payload = packet.payload
        if not isinstance(payload, Mapping) or not isinstance(payload.get("text"), str):
            raise SelfModRuntimeError("cell port response lacks text")
        response_text = str(payload["text"])
        if len(response_text.encode("utf-8")) > max_response_bytes:
            raise SelfModRuntimeError("cell port response exceeds its byte budget")
        return _strict_json_object(response_text)

    def decide(self, request: ExecutionRequest) -> AgentDecision:
        value = self._invoke(
            operation="execute",
            max_response_bytes=request.active.policy.max_token_bytes,
            value={
                "protocol": EXECUTION_SCHEMA_VERSION,
                "instruction": (
                    "Use the active self-authored memory and harness. Select one "
                    "authorized capability and report the exact harness path."
                ),
                "response_contract": {
                    "selected_capability": "non-empty string",
                    "output": "any JSON value",
                    "used_memory_ids": ["memory id"],
                    "followed_node_ids": ["node id in traversal order"],
                },
                "episode_id": request.episode_id,
                "budget": request.budget,
                "capabilities": list(request.capabilities),
                "snapshot": _snapshot_prompt_value(request.active.snapshot),
                "tokens": [token.canonical() for token in request.tokens],
            },
        )
        required = {
            "selected_capability",
            "output",
            "used_memory_ids",
            "followed_node_ids",
        }
        if set(value) != required:
            raise SelfModRuntimeError("execute response field set is invalid")
        return AgentDecision(
            selected_capability=value["selected_capability"],
            output=value["output"],
            used_memory_ids=_string_tuple(value["used_memory_ids"], "used_memory_ids"),
            followed_node_ids=_string_tuple(
                value["followed_node_ids"], "followed_node_ids", unique=False
            ),
        )

    def author(self, request: AuthoringRequest) -> MutationProposal | None:
        value = self._invoke(
            operation="author",
            max_response_bytes=request.active.policy.max_mutation_bytes,
            value={
                "protocol": AUTHORING_SCHEMA_VERSION,
                "instruction": (
                    "Rewrite your own HSWM memory and future episode harness from "
                    "the supplied tokens. You may add, edit, delete, replace, or "
                    "clear state. Do not copy a hidden rulebook."
                ),
                "response_contract": {
                    "noop": "boolean",
                    "rationale": "non-empty string",
                    "upsert_memories": [
                        {
                            "memory_id": "string",
                            "kind": "string",
                            "content": "any JSON value",
                            "source_token_ids": ["supplied token id"],
                            "related_memory_ids": ["memory id"],
                            "labels": ["string"],
                        }
                    ],
                    "delete_memory_ids": ["memory id"],
                    "harness_mode": "KEEP | REPLACE | CLEAR",
                    "harness": {
                        "purpose": "string",
                        "entry_node_id": "node id",
                        "nodes": [
                            {
                                "node_id": "string",
                                "executor_agent_id": "registered agent id or null",
                                "capability": "authorized capability",
                                "instruction": "agent-authored instruction",
                                "memory_ids": ["memory id"],
                                "next_node_ids": ["node id"],
                            }
                        ],
                    },
                },
                "allowed_capabilities": sorted(
                    request.active.policy.allowed_capabilities
                ),
                "agent_registry": [
                    authority.canonical()
                    for authority in request.agent_registry
                ],
                "snapshot": _snapshot_prompt_value(request.active.snapshot),
                "tokens": [token.canonical() for token in request.tokens],
            },
        )
        required = {
            "noop",
            "rationale",
            "upsert_memories",
            "delete_memory_ids",
            "harness_mode",
            "harness",
        }
        if set(value) != required:
            raise SelfModRuntimeError("author response field set is invalid")
        if not isinstance(value["noop"], bool):
            raise SelfModRuntimeError("noop must be boolean")
        if value["noop"]:
            return None
        _require_text("rationale", value["rationale"])
        if not isinstance(value["upsert_memories"], list):
            raise SelfModRuntimeError("upsert_memories must be a list")
        memories = tuple(
            memory_from_mapping(item) for item in value["upsert_memories"]
        )
        delete_ids = _string_tuple(
            value["delete_memory_ids"], "delete_memory_ids"
        )
        try:
            harness_mode = HarnessMode(value["harness_mode"])
        except (TypeError, ValueError) as error:
            raise SelfModRuntimeError("unknown harness_mode") from error
        harness_value = value["harness"]
        harness: HarnessDocument | None
        if harness_mode is HarnessMode.REPLACE:
            if not isinstance(harness_value, Mapping):
                raise SelfModRuntimeError("REPLACE requires a harness object")
            harness = harness_from_mapping(harness_value)
        else:
            if harness_value is not None:
                raise SelfModRuntimeError("KEEP/CLEAR requires harness=null")
            harness = None
        return make_mutation(
            base_snapshot_id=request.active.snapshot.snapshot_id,
            expected_generation=request.active.generation,
            author_id=self.agent_id,
            source_token_ids=tuple(token.token_id for token in request.tokens),
            upsert_memories=memories,
            delete_memory_ids=delete_ids,
            harness_mode=harness_mode,
            harness=harness,
            rationale=value["rationale"],
        )


__all__ = [
    "AUTHORING_SCHEMA_VERSION",
    "AgentDecision",
    "AuthoringRequest",
    "EXECUTION_SCHEMA_VERSION",
    "EpisodeReceipt",
    "ExecutionRequest",
    "JsonSelfModifyingAgent",
    "SelfModRuntimeError",
    "SelfModifyingAgent",
    "SelfModifyingHSWM",
    "validate_agent_decision",
]
