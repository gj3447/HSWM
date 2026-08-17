"""Immutable contracts for an agent-authored, self-modifying HSWM state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence


TOKEN_SCHEMA_VERSION = "hswm-selfmod-token/v1"
SNAPSHOT_SCHEMA_VERSION = "hswm-selfmod-snapshot/v1"
MUTATION_SCHEMA_VERSION = "hswm-selfmod-mutation/v1"
ACTIVATION_SCHEMA_VERSION = "hswm-selfmod-activation/v1"


class SelfModelContractError(ValueError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise SelfModelContractError(f"value is not canonical JSON: {error}") from error


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SelfModelContractError(f"{label} must be a non-empty string")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SelfModelContractError(f"{label} must be a non-negative integer")
    return value


def _texts(
    values: Iterable[object], label: str, *, unique: bool = True, sort: bool = True
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, Mapping)):
        raise SelfModelContractError(f"{label} must be a list/array of strings")
    result = tuple(_text(value, label) for value in values)
    if unique and len(result) != len(set(result)):
        raise SelfModelContractError(f"{label} must not contain duplicates")
    return tuple(sorted(result)) if sort else result


def _field_set(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if not isinstance(value, Mapping):
        raise SelfModelContractError(f"{label} must be an object")
    if set(value) != expected:
        raise SelfModelContractError(f"{label} field set is invalid")


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise SelfModelContractError(f"{label} must be a JSON list/array")
    return value


@dataclass(frozen=True, slots=True)
class CognitiveToken:
    token_id: str
    episode_id: str
    position: int
    role: str
    content: Any
    content_sha256: str
    provenance_sha256: str
    schema_version: str = TOKEN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in (
            "token_id",
            "episode_id",
            "role",
            "content_sha256",
            "provenance_sha256",
        ):
            _text(getattr(self, label), label)
        _nonnegative_int(self.position, "position")
        if self.schema_version != TOKEN_SCHEMA_VERSION:
            raise SelfModelContractError("unsupported token schema")
        if canonical_sha256(self.content) != self.content_sha256:
            raise SelfModelContractError("token content digest mismatch")

    def canonical(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "token_id": self.token_id,
            "episode_id": self.episode_id,
            "position": self.position,
            "role": self.role,
            "content": self.content,
            "content_sha256": self.content_sha256,
            "provenance_sha256": self.provenance_sha256,
        }


def make_token(
    *,
    token_id: str,
    episode_id: str,
    position: int,
    role: str,
    content: Any,
    provenance: Any,
) -> CognitiveToken:
    canonical_json_bytes(content)
    canonical_json_bytes(provenance)
    return CognitiveToken(
        token_id=token_id,
        episode_id=episode_id,
        position=position,
        role=role,
        content=content,
        content_sha256=canonical_sha256(content),
        provenance_sha256=canonical_sha256(provenance),
    )


def token_from_mapping(value: Mapping[str, Any]) -> CognitiveToken:
    _field_set(
        value,
        {
            "schema_version",
            "token_id",
            "episode_id",
            "position",
            "role",
            "content",
            "content_sha256",
            "provenance_sha256",
        },
        "token",
    )
    return CognitiveToken(**value)


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: str
    kind: str
    content: Any
    source_token_ids: tuple[str, ...]
    related_memory_ids: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.memory_id, "memory_id")
        _text(self.kind, "kind")
        canonical_json_bytes(self.content)
        object.__setattr__(
            self,
            "source_token_ids",
            _texts(self.source_token_ids, "source_token_ids"),
        )
        if not self.source_token_ids:
            raise SelfModelContractError("memory requires at least one source token")
        object.__setattr__(
            self,
            "related_memory_ids",
            _texts(self.related_memory_ids, "related_memory_ids"),
        )
        object.__setattr__(self, "labels", _texts(self.labels, "labels"))

    def canonical(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "kind": self.kind,
            "content": self.content,
            "source_token_ids": list(self.source_token_ids),
            "related_memory_ids": list(self.related_memory_ids),
            "labels": list(self.labels),
        }


def memory_from_mapping(value: Mapping[str, Any]) -> MemoryRecord:
    if not isinstance(value, Mapping):
        raise SelfModelContractError("memory must be an object")
    _field_set(
        value,
        {
            "memory_id",
            "kind",
            "content",
            "source_token_ids",
            "related_memory_ids",
            "labels",
        },
        "memory",
    )
    return MemoryRecord(
        memory_id=value["memory_id"],
        kind=value["kind"],
        content=value["content"],
        source_token_ids=tuple(_array(value["source_token_ids"], "source_token_ids")),
        related_memory_ids=tuple(
            _array(value["related_memory_ids"], "related_memory_ids")
        ),
        labels=tuple(_array(value["labels"], "labels")),
    )


@dataclass(frozen=True, slots=True)
class HarnessNode:
    node_id: str
    capability: str
    instruction: str
    memory_ids: tuple[str, ...] = ()
    next_node_ids: tuple[str, ...] = ()
    executor_agent_id: str | None = None

    def __post_init__(self) -> None:
        _text(self.node_id, "node_id")
        _text(self.capability, "capability")
        _text(self.instruction, "instruction")
        if self.executor_agent_id is not None:
            _text(self.executor_agent_id, "executor_agent_id")
        object.__setattr__(
            self, "memory_ids", _texts(self.memory_ids, "memory_ids")
        )
        object.__setattr__(
            self, "next_node_ids", _texts(self.next_node_ids, "next_node_ids")
        )

    def canonical(self) -> dict[str, Any]:
        value = {
            "node_id": self.node_id,
            "capability": self.capability,
            "instruction": self.instruction,
            "memory_ids": list(self.memory_ids),
            "next_node_ids": list(self.next_node_ids),
        }
        # Omit the new field for legacy single-agent nodes so their canonical
        # bytes and content-addressed identities remain exactly stable.
        if self.executor_agent_id is not None:
            value["executor_agent_id"] = self.executor_agent_id
        return value


def _node_from_mapping(value: Mapping[str, Any]) -> HarnessNode:
    if not isinstance(value, Mapping):
        raise SelfModelContractError("harness node must be an object")
    legacy_fields = {
        "node_id",
        "capability",
        "instruction",
        "memory_ids",
        "next_node_ids",
    }
    if set(value) not in (legacy_fields, legacy_fields | {"executor_agent_id"}):
        raise SelfModelContractError("harness node field set is invalid")
    return HarnessNode(
        node_id=value["node_id"],
        capability=value["capability"],
        instruction=value["instruction"],
        memory_ids=tuple(_array(value["memory_ids"], "memory_ids")),
        next_node_ids=tuple(_array(value["next_node_ids"], "next_node_ids")),
        executor_agent_id=value.get("executor_agent_id"),
    )


@dataclass(frozen=True, slots=True)
class HarnessDocument:
    harness_id: str
    purpose: str
    entry_node_id: str
    nodes: tuple[HarnessNode, ...]

    def __post_init__(self) -> None:
        _text(self.harness_id, "harness_id")
        _text(self.purpose, "purpose")
        _text(self.entry_node_id, "entry_node_id")
        if not self.nodes:
            raise SelfModelContractError("harness requires at least one node")
        ordered = tuple(sorted(self.nodes, key=lambda node: node.node_id))
        if len(ordered) != len({node.node_id for node in ordered}):
            raise SelfModelContractError("harness node ids must be unique")
        object.__setattr__(self, "nodes", ordered)
        node_ids = {node.node_id for node in ordered}
        if self.entry_node_id not in node_ids:
            raise SelfModelContractError("harness entry node is missing")
        for node in ordered:
            if not set(node.next_node_ids) <= node_ids:
                raise SelfModelContractError("harness edge targets an unknown node")
        if canonical_sha256(self.unsigned()) != self.harness_id:
            raise SelfModelContractError("harness id digest mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "purpose": self.purpose,
            "entry_node_id": self.entry_node_id,
            "nodes": [node.canonical() for node in self.nodes],
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "harness_id": self.harness_id}


def make_harness(
    *, purpose: str, entry_node_id: str, nodes: Sequence[HarnessNode]
) -> HarnessDocument:
    ordered = tuple(sorted(nodes, key=lambda node: node.node_id))
    unsigned = {
        "purpose": purpose,
        "entry_node_id": entry_node_id,
        "nodes": [node.canonical() for node in ordered],
    }
    return HarnessDocument(
        harness_id=canonical_sha256(unsigned),
        purpose=purpose,
        entry_node_id=entry_node_id,
        nodes=ordered,
    )


def harness_from_mapping(value: Mapping[str, Any]) -> HarnessDocument:
    if not isinstance(value, Mapping):
        raise SelfModelContractError("harness must be an object")
    allowed = {"purpose", "entry_node_id", "nodes", "harness_id"}
    if set(value) not in (allowed, allowed - {"harness_id"}):
        raise SelfModelContractError("harness field set is invalid")
    harness = make_harness(
        purpose=value["purpose"],
        entry_node_id=value["entry_node_id"],
        nodes=tuple(
            _node_from_mapping(node) for node in _array(value["nodes"], "nodes")
        ),
    )
    if "harness_id" in value and value["harness_id"] != harness.harness_id:
        raise SelfModelContractError("stored harness id mismatch")
    return harness


@dataclass(frozen=True, slots=True)
class SelfModelSnapshot:
    snapshot_id: str
    memories: tuple[MemoryRecord, ...] = ()
    harness: HarnessDocument | None = None
    schema_version: str = SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot_id")
        if self.schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise SelfModelContractError("unsupported snapshot schema")
        ordered = tuple(sorted(self.memories, key=lambda item: item.memory_id))
        if len(ordered) != len({memory.memory_id for memory in ordered}):
            raise SelfModelContractError("snapshot memory ids must be unique")
        object.__setattr__(self, "memories", ordered)
        if canonical_sha256(self.unsigned()) != self.snapshot_id:
            raise SelfModelContractError("snapshot id digest mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "memories": [memory.canonical() for memory in self.memories],
            "harness": self.harness.canonical() if self.harness is not None else None,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "snapshot_id": self.snapshot_id}


def make_snapshot(
    memories: Sequence[MemoryRecord] = (),
    harness: HarnessDocument | None = None,
) -> SelfModelSnapshot:
    ordered = tuple(sorted(memories, key=lambda memory: memory.memory_id))
    unsigned = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "memories": [memory.canonical() for memory in ordered],
        "harness": harness.canonical() if harness is not None else None,
    }
    return SelfModelSnapshot(
        snapshot_id=canonical_sha256(unsigned), memories=ordered, harness=harness
    )


def snapshot_from_mapping(value: Mapping[str, Any]) -> SelfModelSnapshot:
    _field_set(
        value,
        {"schema_version", "snapshot_id", "memories", "harness"},
        "snapshot",
    )
    harness_value = value["harness"]
    if harness_value is not None and not isinstance(harness_value, Mapping):
        raise SelfModelContractError("snapshot harness must be an object or null")
    snapshot = make_snapshot(
        memories=tuple(
            memory_from_mapping(item)
            for item in _array(value["memories"], "memories")
        ),
        harness=(
            harness_from_mapping(harness_value)
            if isinstance(harness_value, Mapping)
            else None
        ),
    )
    if value["schema_version"] != SNAPSHOT_SCHEMA_VERSION:
        raise SelfModelContractError("unsupported snapshot schema")
    if value["snapshot_id"] != snapshot.snapshot_id:
        raise SelfModelContractError("stored snapshot id mismatch")
    return snapshot


@dataclass(frozen=True, slots=True)
class SelfModelPolicy:
    allowed_capabilities: frozenset[str]
    max_token_bytes: int = 262_144
    max_memories: int = 512
    max_harness_nodes: int = 128
    max_snapshot_bytes: int = 4_194_304
    max_mutation_bytes: int = 1_048_576

    def __post_init__(self) -> None:
        capabilities = frozenset(
            _text(capability, "allowed_capabilities")
            for capability in self.allowed_capabilities
        )
        if not capabilities:
            raise SelfModelContractError("policy requires an authority set")
        object.__setattr__(self, "allowed_capabilities", capabilities)
        for field in (
            "max_token_bytes",
            "max_memories",
            "max_harness_nodes",
            "max_snapshot_bytes",
            "max_mutation_bytes",
        ):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise SelfModelContractError(f"{field} must be positive")

    def canonical(self) -> dict[str, Any]:
        return {
            "allowed_capabilities": sorted(self.allowed_capabilities),
            "max_token_bytes": self.max_token_bytes,
            "max_memories": self.max_memories,
            "max_harness_nodes": self.max_harness_nodes,
            "max_snapshot_bytes": self.max_snapshot_bytes,
            "max_mutation_bytes": self.max_mutation_bytes,
        }

    @property
    def policy_sha256(self) -> str:
        return canonical_sha256(self.canonical())


@dataclass(frozen=True, slots=True)
class ActiveSnapshot:
    snapshot: SelfModelSnapshot
    generation: int
    policy: SelfModelPolicy

    def __post_init__(self) -> None:
        _nonnegative_int(self.generation, "generation")


class HarnessMode(str, Enum):
    KEEP = "KEEP"
    REPLACE = "REPLACE"
    CLEAR = "CLEAR"


@dataclass(frozen=True, slots=True)
class ExecutorAuthority:
    """Frozen executor identity visible to a self-authoring agent."""

    agent_id: str
    allowed_capabilities: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.agent_id, "agent_id")
        object.__setattr__(
            self,
            "allowed_capabilities",
            _texts(self.allowed_capabilities, "allowed_capabilities"),
        )
        if not self.allowed_capabilities:
            raise SelfModelContractError("executor authority requires capabilities")

    def canonical(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "allowed_capabilities": list(self.allowed_capabilities),
        }


@dataclass(frozen=True, slots=True)
class MutationProposal:
    mutation_id: str
    base_snapshot_id: str
    expected_generation: int
    author_id: str
    source_token_ids: tuple[str, ...]
    upsert_memories: tuple[MemoryRecord, ...]
    delete_memory_ids: tuple[str, ...]
    harness_mode: HarnessMode
    harness: HarnessDocument | None
    rationale: str
    schema_version: str = MUTATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field in ("mutation_id", "base_snapshot_id", "author_id", "rationale"):
            _text(getattr(self, field), field)
        _nonnegative_int(self.expected_generation, "expected_generation")
        if self.schema_version != MUTATION_SCHEMA_VERSION:
            raise SelfModelContractError("unsupported mutation schema")
        object.__setattr__(
            self,
            "source_token_ids",
            _texts(self.source_token_ids, "source_token_ids"),
        )
        if not self.source_token_ids:
            raise SelfModelContractError("mutation requires source tokens")
        ordered = tuple(
            sorted(self.upsert_memories, key=lambda memory: memory.memory_id)
        )
        if len(ordered) != len({memory.memory_id for memory in ordered}):
            raise SelfModelContractError("mutation upsert ids must be unique")
        object.__setattr__(self, "upsert_memories", ordered)
        object.__setattr__(
            self,
            "delete_memory_ids",
            _texts(self.delete_memory_ids, "delete_memory_ids"),
        )
        if {memory.memory_id for memory in ordered} & set(self.delete_memory_ids):
            raise SelfModelContractError("mutation cannot upsert and delete one memory")
        if self.harness_mode is HarnessMode.REPLACE and self.harness is None:
            raise SelfModelContractError("REPLACE requires a harness")
        if self.harness_mode is not HarnessMode.REPLACE and self.harness is not None:
            raise SelfModelContractError("KEEP/CLEAR cannot carry a harness")
        if canonical_sha256(self.unsigned()) != self.mutation_id:
            raise SelfModelContractError("mutation id digest mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "base_snapshot_id": self.base_snapshot_id,
            "expected_generation": self.expected_generation,
            "author_id": self.author_id,
            "source_token_ids": list(self.source_token_ids),
            "upsert_memories": [memory.canonical() for memory in self.upsert_memories],
            "delete_memory_ids": list(self.delete_memory_ids),
            "harness_mode": self.harness_mode.value,
            "harness": self.harness.canonical() if self.harness is not None else None,
            "rationale": self.rationale,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "mutation_id": self.mutation_id}


def make_mutation(
    *,
    base_snapshot_id: str,
    expected_generation: int,
    author_id: str,
    source_token_ids: Sequence[str],
    upsert_memories: Sequence[MemoryRecord] = (),
    delete_memory_ids: Sequence[str] = (),
    harness_mode: HarnessMode = HarnessMode.KEEP,
    harness: HarnessDocument | None = None,
    rationale: str,
) -> MutationProposal:
    source_ids = tuple(sorted(source_token_ids))
    upserts = tuple(sorted(upsert_memories, key=lambda memory: memory.memory_id))
    delete_ids = tuple(sorted(delete_memory_ids))
    unsigned = {
        "schema_version": MUTATION_SCHEMA_VERSION,
        "base_snapshot_id": base_snapshot_id,
        "expected_generation": expected_generation,
        "author_id": author_id,
        "source_token_ids": list(source_ids),
        "upsert_memories": [memory.canonical() for memory in upserts],
        "delete_memory_ids": list(delete_ids),
        "harness_mode": harness_mode.value,
        "harness": harness.canonical() if harness is not None else None,
        "rationale": rationale,
    }
    return MutationProposal(
        mutation_id=canonical_sha256(unsigned),
        base_snapshot_id=base_snapshot_id,
        expected_generation=expected_generation,
        author_id=author_id,
        source_token_ids=source_ids,
        upsert_memories=upserts,
        delete_memory_ids=delete_ids,
        harness_mode=harness_mode,
        harness=harness,
        rationale=rationale,
    )


def mutation_from_mapping(value: Mapping[str, Any]) -> MutationProposal:
    _field_set(
        value,
        {
            "schema_version",
            "mutation_id",
            "base_snapshot_id",
            "expected_generation",
            "author_id",
            "source_token_ids",
            "upsert_memories",
            "delete_memory_ids",
            "harness_mode",
            "harness",
            "rationale",
        },
        "mutation",
    )
    try:
        mode = HarnessMode(value["harness_mode"])
    except (TypeError, ValueError) as error:
        raise SelfModelContractError("unknown harness mode") from error
    harness_value = value["harness"]
    if harness_value is not None and not isinstance(harness_value, Mapping):
        raise SelfModelContractError("mutation harness must be an object or null")
    proposal = make_mutation(
        base_snapshot_id=value["base_snapshot_id"],
        expected_generation=value["expected_generation"],
        author_id=value["author_id"],
        source_token_ids=tuple(
            _array(value["source_token_ids"], "source_token_ids")
        ),
        upsert_memories=tuple(
            memory_from_mapping(item)
            for item in _array(value["upsert_memories"], "upsert_memories")
        ),
        delete_memory_ids=tuple(
            _array(value["delete_memory_ids"], "delete_memory_ids")
        ),
        harness_mode=mode,
        harness=(
            harness_from_mapping(harness_value)
            if isinstance(harness_value, Mapping)
            else None
        ),
        rationale=value["rationale"],
    )
    if value["schema_version"] != MUTATION_SCHEMA_VERSION:
        raise SelfModelContractError("unsupported mutation schema")
    if value["mutation_id"] != proposal.mutation_id:
        raise SelfModelContractError("stored mutation id mismatch")
    return proposal


@dataclass(frozen=True, slots=True)
class ActivationReceipt:
    activation_id: str
    reason: str
    base_snapshot_id: str
    base_generation: int
    active_snapshot_id: str
    active_generation: int
    mutation_id: str | None
    author_id: str
    source_token_ids: tuple[str, ...]
    schema_version: str = ACTIVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field in (
            "activation_id",
            "reason",
            "base_snapshot_id",
            "active_snapshot_id",
            "author_id",
        ):
            _text(getattr(self, field), field)
        _nonnegative_int(self.base_generation, "base_generation")
        _nonnegative_int(self.active_generation, "active_generation")
        if self.active_generation != self.base_generation + 1:
            raise SelfModelContractError("activation generation must advance once")
        if self.schema_version != ACTIVATION_SCHEMA_VERSION:
            raise SelfModelContractError("unsupported activation schema")
        object.__setattr__(
            self,
            "source_token_ids",
            _texts(self.source_token_ids, "source_token_ids"),
        )
        if not self.source_token_ids:
            raise SelfModelContractError("activation requires source tokens")
        if canonical_sha256(self.unsigned()) != self.activation_id:
            raise SelfModelContractError("activation id digest mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "reason": self.reason,
            "base_snapshot_id": self.base_snapshot_id,
            "base_generation": self.base_generation,
            "active_snapshot_id": self.active_snapshot_id,
            "active_generation": self.active_generation,
            "mutation_id": self.mutation_id,
            "author_id": self.author_id,
            "source_token_ids": list(self.source_token_ids),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "activation_id": self.activation_id}


def make_activation_receipt(
    *,
    reason: str,
    base_snapshot_id: str,
    base_generation: int,
    active_snapshot_id: str,
    mutation_id: str | None,
    author_id: str,
    source_token_ids: Sequence[str],
) -> ActivationReceipt:
    source_ids = tuple(sorted(source_token_ids))
    unsigned = {
        "schema_version": ACTIVATION_SCHEMA_VERSION,
        "reason": reason,
        "base_snapshot_id": base_snapshot_id,
        "base_generation": base_generation,
        "active_snapshot_id": active_snapshot_id,
        "active_generation": base_generation + 1,
        "mutation_id": mutation_id,
        "author_id": author_id,
        "source_token_ids": list(source_ids),
    }
    return ActivationReceipt(
        activation_id=canonical_sha256(unsigned),
        reason=reason,
        base_snapshot_id=base_snapshot_id,
        base_generation=base_generation,
        active_snapshot_id=active_snapshot_id,
        active_generation=base_generation + 1,
        mutation_id=mutation_id,
        author_id=author_id,
        source_token_ids=source_ids,
    )


def activation_from_mapping(value: Mapping[str, Any]) -> ActivationReceipt:
    _field_set(
        value,
        {
            "schema_version",
            "activation_id",
            "reason",
            "base_snapshot_id",
            "base_generation",
            "active_snapshot_id",
            "active_generation",
            "mutation_id",
            "author_id",
            "source_token_ids",
        },
        "activation receipt",
    )
    receipt = make_activation_receipt(
        reason=value["reason"],
        base_snapshot_id=value["base_snapshot_id"],
        base_generation=value["base_generation"],
        active_snapshot_id=value["active_snapshot_id"],
        mutation_id=value["mutation_id"],
        author_id=value["author_id"],
        source_token_ids=tuple(
            _array(value["source_token_ids"], "source_token_ids")
        ),
    )
    if value["schema_version"] != ACTIVATION_SCHEMA_VERSION:
        raise SelfModelContractError("unsupported activation schema")
    if value["active_generation"] != receipt.active_generation:
        raise SelfModelContractError("stored activation generation mismatch")
    if value["activation_id"] != receipt.activation_id:
        raise SelfModelContractError("stored activation id mismatch")
    return receipt


def apply_mutation(
    snapshot: SelfModelSnapshot,
    proposal: MutationProposal,
    policy: SelfModelPolicy,
) -> SelfModelSnapshot:
    if proposal.base_snapshot_id != snapshot.snapshot_id:
        raise SelfModelContractError("mutation base snapshot mismatch")
    if len(canonical_json_bytes(proposal.canonical())) > policy.max_mutation_bytes:
        raise SelfModelContractError("mutation exceeds byte budget")

    memories = {memory.memory_id: memory for memory in snapshot.memories}
    for memory_id in proposal.delete_memory_ids:
        memories.pop(memory_id, None)
    for memory in proposal.upsert_memories:
        memories[memory.memory_id] = memory

    if proposal.harness_mode is HarnessMode.KEEP:
        harness = snapshot.harness
    elif proposal.harness_mode is HarnessMode.REPLACE:
        harness = proposal.harness
    else:
        harness = None

    if len(memories) > policy.max_memories:
        raise SelfModelContractError("snapshot exceeds memory-count budget")
    memory_ids = set(memories)
    for memory in memories.values():
        if not set(memory.related_memory_ids) <= memory_ids:
            raise SelfModelContractError("memory relation targets missing state")
    if harness is not None:
        if len(harness.nodes) > policy.max_harness_nodes:
            raise SelfModelContractError("harness exceeds node-count budget")
        for node in harness.nodes:
            if node.capability not in policy.allowed_capabilities:
                raise SelfModelContractError("harness requests unauthorized capability")
            if not set(node.memory_ids) <= memory_ids:
                raise SelfModelContractError("harness references missing memory")

    result = make_snapshot(tuple(memories.values()), harness)
    if len(canonical_json_bytes(result.canonical())) > policy.max_snapshot_bytes:
        raise SelfModelContractError("snapshot exceeds byte budget")
    if result.snapshot_id == snapshot.snapshot_id:
        raise SelfModelContractError("mutation is a no-op")
    return result


__all__ = [
    "ACTIVATION_SCHEMA_VERSION",
    "ActiveSnapshot",
    "ActivationReceipt",
    "CognitiveToken",
    "ExecutorAuthority",
    "HarnessDocument",
    "HarnessMode",
    "HarnessNode",
    "MemoryRecord",
    "MutationProposal",
    "SNAPSHOT_SCHEMA_VERSION",
    "SelfModelContractError",
    "SelfModelPolicy",
    "SelfModelSnapshot",
    "TOKEN_SCHEMA_VERSION",
    "activation_from_mapping",
    "apply_mutation",
    "canonical_json_bytes",
    "canonical_sha256",
    "harness_from_mapping",
    "make_activation_receipt",
    "make_harness",
    "make_mutation",
    "make_snapshot",
    "make_token",
    "memory_from_mapping",
    "mutation_from_mapping",
    "snapshot_from_mapping",
    "token_from_mapping",
]
