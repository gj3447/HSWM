"""Audited live arms for the nonce-graph continual-learning benchmark.

This module is intentionally narrower than a general agent framework.  It
binds four stateless-chat conditions to :func:`continual.run_prequential`:

``hswm``
    The model authors memories, memory relations, cells, and routing edges in
    an empty-genesis :class:`SQLiteSelfModelStore`.  The committed HSWM
    structure is itself the persistent execution substrate.
``reset``
    The same structured proposal is parsed and checked, then discarded.  The
    active snapshot is exact genesis at every probe.
``no_write``
    The proposal/check call is made without reading prior learned state and is
    discarded.  Its active snapshot is always exact genesis.
``plain``
    The model maintains one bounded linear text value, without graph relations
    or cell topology.

All model calls are one-shot conversations.  There is no retry or hidden chat
history, and update prompts contain only public atomic-relation tokens.  The
module supplies mechanism and audit plumbing; a pilot run is not evidence of a
continual-learning effect.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from hashlib import sha256
import itertools
import json
import os
from pathlib import Path
import re
import socket
import stat
import tempfile
import time
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib import error as urlerror
from urllib import request as urlrequest

from hswm.selfmod.contracts import (
    CellRecord,
    CellTopologyMode,
    MemoryRecord,
    SelfModelPolicy,
    SelfModelSnapshot,
    apply_mutation,
    canonical_json_bytes,
    cell_from_mapping,
    make_mutation,
    make_snapshot,
    make_token,
    memory_from_mapping,
)
from hswm.selfmod.store import SQLiteSelfModelStore

from .continual import (
    ArmAnswer,
    ArmUpdate,
    LearningBatch,
    PROTOCOL,
    PublicLearningToken,
    PublicProbe,
    StreamManifest,
    StreamRun,
    canonical_sha256,
    generate_stream,
    parse_choice,
    run_prequential,
    validate_stream_set,
)


LIVE_PROTOCOL = "hswm-continual-live/v1"
AUTHOR_ID = "agent:continual-memory-author"
CAPABILITY = "nonce_graph_lookup"
GENESIS = make_snapshot()
FROZEN_PILOT_PRECOMMIT_ARTIFACT_SHA256 = (
    "e5f98257a199e70f4e648344f89bd3b59edd6661cbc6dd717b86aaf74fff4324"
)
FROZEN_PILOT_PRECOMMIT_SHA256 = (
    "a7b9a157b12246568663bb34c466d7cf806e8fb899fd99ae3a6d83d67c7f608d"
)


class ContinualLiveError(RuntimeError):
    """A live arm or its audit boundary failed closed."""


def _strict_object(text: str) -> dict[str, Any]:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ContinualLiveError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=no_duplicates)
    except (json.JSONDecodeError, ValueError) as error:
        raise ContinualLiveError(f"model returned invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ContinualLiveError("model response must be one JSON object")
    canonical_json_bytes(value)
    return value


def _digest_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_json_bytes(value) + b"\n"
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _write_bytes_atomic(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@dataclass(frozen=True, slots=True)
class ModelCompletion:
    text: str
    raw_request_json: str
    raw_response_json: str
    request_sha256: str
    response_sha256: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    usage_reported: bool

    def __post_init__(self) -> None:
        if not self.text:
            raise ContinualLiveError("empty model completion")
        for label, raw, digest in (
            ("request", self.raw_request_json, self.request_sha256),
            ("response", self.raw_response_json, self.response_sha256),
        ):
            if not isinstance(raw, str):
                raise ContinualLiveError(f"raw {label} preimage must be text")
            if len(digest) != 64:
                raise ContinualLiveError("model call digest is malformed")
            int(digest, 16)
            if _digest_bytes(raw.encode("utf-8")) != digest:
                raise ContinualLiveError(f"raw {label} preimage digest mismatch")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as error:
                raise ContinualLiveError(
                    f"raw {label} preimage is not valid JSON"
                ) from error
            if label == "response":
                try:
                    returned_text = parsed["choices"][0]["message"]["content"]
                    returned_model = parsed["model"]
                except (KeyError, IndexError, TypeError) as error:
                    raise ContinualLiveError(
                        "raw response lacks the OpenAI completion envelope"
                    ) from error
                if returned_text != self.text or returned_model != self.model:
                    raise ContinualLiveError(
                        "raw response text/model differs from stored completion"
                    )
                usage = parsed.get("usage")
                if self.usage_reported:
                    if not isinstance(usage, Mapping) or (
                        usage.get("prompt_tokens") != self.input_tokens
                        or usage.get("completion_tokens") != self.output_tokens
                    ):
                        raise ContinualLiveError(
                            "raw response usage differs from stored completion"
                        )
                elif usage is not None:
                    raise ContinualLiveError("usage_reported is false but usage exists")
        if min(self.input_tokens, self.output_tokens, self.latency_ms) < 0:
            raise ContinualLiveError("negative model telemetry")

    def canonical(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "latency_ms": self.latency_ms,
            "model": self.model,
            "output_tokens": self.output_tokens,
            "raw_request_json": self.raw_request_json,
            "raw_response_json": self.raw_response_json,
            "request_sha256": self.request_sha256,
            "response_sha256": self.response_sha256,
            "text": self.text,
            "text_sha256": _digest_bytes(self.text.encode("utf-8")),
            "usage_reported": self.usage_reported,
        }


class ChatBackend(Protocol):
    """One stateless chat call; implementations must not retry."""

    @property
    def identity(self) -> Mapping[str, Any]: ...

    def complete(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        max_output_tokens: int,
        request_id: str,
        response_observer: Callable[[bytes, bytes], None],
    ) -> ModelCompletion: ...


@dataclass(frozen=True, slots=True)
class OpenAIBackendConfig:
    endpoint: str
    model: str
    api_key: str | None = None
    timeout_seconds: float = 120.0
    temperature: float = 0.0
    top_p: float = 1.0
    seed: int = 0
    enable_thinking: bool = False
    max_response_bytes: int = 4_000_000

    def __post_init__(self) -> None:
        if not self.endpoint.startswith(("http://", "https://")):
            raise ValueError("endpoint must use HTTP(S)")
        if not self.model:
            raise ValueError("model must be non-empty")
        if self.timeout_seconds <= 0 or self.max_response_bytes <= 0:
            raise ValueError("timeout and response bound must be positive")
        if self.temperature != 0.0:
            raise ValueError("the frozen benchmark requires greedy temperature=0")
        if self.top_p != 1.0 or self.seed != 0:
            raise ValueError("the frozen benchmark requires top_p=1 and seed=0")

    def public_identity(self) -> dict[str, Any]:
        return {
            "adapter": "openai-compatible-stateless/v1",
            "enable_thinking": self.enable_thinking,
            "endpoint": self.endpoint,
            "max_response_bytes": self.max_response_bytes,
            "model": self.model,
            "retry_count": 0,
            "seed": self.seed,
            "temperature": self.temperature,
            "timeout_seconds": self.timeout_seconds,
            "top_p": self.top_p,
        }


class OpenAICompatibleBackend:
    """Small OpenAI-compatible transport with no automatic retry."""

    def __init__(self, config: OpenAIBackendConfig) -> None:
        self.config = config

    @property
    def identity(self) -> Mapping[str, Any]:
        return self.config.public_identity()

    def complete(
        self,
        *,
        messages: Sequence[Mapping[str, str]],
        max_output_tokens: int,
        request_id: str,
        response_observer: Callable[[bytes, bytes], None],
    ) -> ModelCompletion:
        if max_output_tokens <= 0:
            raise ContinualLiveError("max_output_tokens must be positive")
        normalized = [
            {"role": str(item["role"]), "content": str(item["content"])}
            for item in messages
        ]
        if not normalized or any(
            item["role"] not in {"system", "user", "assistant"}
            for item in normalized
        ):
            raise ContinualLiveError("invalid chat messages")
        request_value = {
            "chat_template_kwargs": {
                "enable_thinking": self.config.enable_thinking
            },
            "max_tokens": max_output_tokens,
            "messages": normalized,
            "model": self.config.model,
            "seed": self.config.seed,
            "temperature": 0.0,
            "top_p": self.config.top_p,
        }
        raw_request = canonical_json_bytes(request_value)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Idempotency-Key": request_id,
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = urlrequest.Request(
            self.config.endpoint.rstrip("/") + "/v1/chat/completions",
            data=raw_request,
            headers=headers,
            method="POST",
        )
        started = time.monotonic_ns()
        try:
            with urlrequest.urlopen(
                request, timeout=self.config.timeout_seconds
            ) as response:
                raw_response = response.read(self.config.max_response_bytes + 1)
        except urlerror.HTTPError as error:
            error_raw = error.read(2048)
            response_observer(raw_request, error_raw)
            detail = error_raw.decode("utf-8", errors="replace")
            raise ContinualLiveError(
                f"model HTTP outcome {error.code}; no retry: {detail[:500]}"
            ) from error
        except (urlerror.URLError, TimeoutError, socket.timeout, OSError) as error:
            raise ContinualLiveError(
                f"model call outcome unknown; no retry: {error}"
            ) from error
        latency_ms = (time.monotonic_ns() - started) // 1_000_000
        response_observer(raw_request, raw_response)
        if len(raw_response) > self.config.max_response_bytes:
            raise ContinualLiveError("model response exceeds byte bound")
        try:
            value = json.loads(raw_response.decode("utf-8"))
            text = value["choices"][0]["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise ContinualLiveError(f"invalid chat-completions envelope: {error}") from error
        if not isinstance(text, str) or not text.strip():
            raise ContinualLiveError("model returned empty text")
        usage = value.get("usage")
        usage_reported = isinstance(usage, Mapping)
        try:
            input_tokens = int(usage["prompt_tokens"]) if usage_reported else 0
            output_tokens = int(usage["completion_tokens"]) if usage_reported else 0
        except (KeyError, TypeError, ValueError) as error:
            raise ContinualLiveError("provider usage record is incomplete") from error
        return ModelCompletion(
            text=text,
            raw_request_json=raw_request.decode("utf-8"),
            raw_response_json=raw_response.decode("utf-8"),
            request_sha256=_digest_bytes(raw_request),
            response_sha256=_digest_bytes(raw_response),
            model=str(value.get("model", self.config.model)),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=int(latency_ms),
            usage_reported=usage_reported,
        )


@dataclass(frozen=True, slots=True)
class ArmBudget:
    answer_max_output_tokens: int = 128
    update_max_output_tokens: int = 8192
    max_input_bytes: int = 2_000_000
    max_state_bytes: int = 1_000_000
    max_cells: int = 32
    max_memories: int = 512

    def __post_init__(self) -> None:
        if min(
            self.answer_max_output_tokens,
            self.update_max_output_tokens,
            self.max_input_bytes,
            self.max_state_bytes,
            self.max_cells,
            self.max_memories,
        ) <= 0:
            raise ValueError("all arm budget fields must be positive")

    def canonical(self) -> dict[str, int]:
        return {
            "answer_max_output_tokens": self.answer_max_output_tokens,
            "max_cells": self.max_cells,
            "max_input_bytes": self.max_input_bytes,
            "max_memories": self.max_memories,
            "max_state_bytes": self.max_state_bytes,
            "update_max_output_tokens": self.update_max_output_tokens,
        }


def _proposal_policy(budget: ArmBudget) -> SelfModelPolicy:
    return SelfModelPolicy(
        allowed_capabilities=frozenset({CAPABILITY}),
        max_memories=budget.max_memories,
        max_cells=budget.max_cells,
        max_snapshot_bytes=budget.max_state_bytes,
        max_mutation_bytes=budget.max_input_bytes,
    )


@dataclass(frozen=True, slots=True)
class CallLedgerEntry:
    arm: str
    operation: str
    ordinal: int
    max_output_tokens: int
    backend_identity_json: str
    request_payload_json: str
    request_payload_sha256: str
    system_message: str
    completion: ModelCompletion

    def __post_init__(self) -> None:
        try:
            payload = json.loads(self.request_payload_json)
            backend_identity = json.loads(self.backend_identity_json)
            raw_request = json.loads(self.completion.raw_request_json)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ContinualLiveError("ledger request/config preimage is not JSON") from error
        canonical = canonical_json_bytes(payload)
        if canonical.decode("utf-8") != self.request_payload_json:
            raise ContinualLiveError("ledger request payload is not canonical")
        if _digest_bytes(canonical) != self.request_payload_sha256:
            raise ContinualLiveError("ledger request payload digest mismatch")
        if not self.system_message:
            raise ContinualLiveError("ledger system message is empty")
        if canonical_json_bytes(backend_identity).decode("utf-8") != self.backend_identity_json:
            raise ContinualLiveError("ledger backend identity is not canonical")
        expected_request_fields = {
            "chat_template_kwargs",
            "max_tokens",
            "messages",
            "model",
            "seed",
            "temperature",
            "top_p",
        }
        if not isinstance(raw_request, dict) or set(raw_request) != expected_request_fields:
            raise ContinualLiveError("raw request body field set is not frozen")
        if canonical_json_bytes(raw_request).decode("utf-8") != self.completion.raw_request_json:
            raise ContinualLiveError("raw request body is not canonical")
        if raw_request["messages"] != [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": self.request_payload_json},
        ]:
            raise ContinualLiveError("raw request messages differ from ledger preimage")
        if (
            raw_request["max_tokens"] != self.max_output_tokens
            or raw_request["seed"] != backend_identity.get("seed")
            or raw_request["temperature"] != 0.0
            or raw_request["top_p"] != backend_identity.get("top_p")
            or raw_request["model"] != backend_identity.get("model")
            or raw_request["model"] != self.completion.model
            or raw_request["chat_template_kwargs"]
            != {"enable_thinking": backend_identity.get("enable_thinking", False)}
        ):
            raise ContinualLiveError("raw request parameters differ from frozen config")

    def canonical(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "backend_identity_json": self.backend_identity_json,
            "completion": self.completion.canonical(),
            "max_output_tokens": self.max_output_tokens,
            "operation": self.operation,
            "ordinal": self.ordinal,
            "request_payload_json": self.request_payload_json,
            "request_payload_sha256": self.request_payload_sha256,
            "system_message": self.system_message,
        }


class _ModelArm:
    def __init__(
        self,
        *,
        name: str,
        backend: ChatBackend,
        budget: ArmBudget,
        isolation_id: str,
        journal_path: Path,
    ) -> None:
        if not name or not isolation_id:
            raise ValueError("arm name and isolation id are required")
        self.name = name
        self.backend = backend
        self.budget = budget
        self.isolation_id = isolation_id
        self.journal_path = Path(journal_path)
        if self.journal_path.exists():
            raise ContinualLiveError("arm call journal must be fresh")
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger: list[CallLedgerEntry] = []

    def _journal(self, value: Mapping[str, Any]) -> None:
        raw = canonical_json_bytes(value) + b"\n"
        with self.journal_path.open("ab") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())

    def audit_config(self) -> dict[str, Any]:
        policy = _proposal_policy(self.budget)
        return {
            "backend": dict(self.backend.identity),
            "budget": self.budget.canonical(),
            "proposal_policy": policy.canonical(),
            "proposal_policy_sha256": policy.policy_sha256,
            "protocol": LIVE_PROTOCOL,
        }

    def _call(
        self,
        *,
        operation: str,
        system: str,
        payload: Mapping[str, Any],
        max_output_tokens: int,
    ) -> ModelCompletion:
        payload_raw = canonical_json_bytes(payload)
        messages = (
            {"role": "system", "content": system},
            {"role": "user", "content": payload_raw.decode("utf-8")},
        )
        message_bytes = canonical_json_bytes(messages)
        if len(message_bytes) > self.budget.max_input_bytes:
            raise ContinualLiveError(
                f"{self.name} {operation} input exceeds the common byte envelope"
            )
        ordinal = len(self.ledger)
        request_id = "cl-" + canonical_sha256(
            {
                "arm": self.name,
                "isolation_id": self.isolation_id,
                "operation": operation,
                "ordinal": ordinal,
                "payload_sha256": _digest_bytes(payload_raw),
            }
        )[:32]
        intent = {
            "arm": self.name,
            "backend": dict(self.backend.identity),
            "event": "intent",
            "isolation_id": self.isolation_id,
            "max_output_tokens": max_output_tokens,
            "operation": operation,
            "ordinal": ordinal,
            "request_id": request_id,
            "request_payload_json": payload_raw.decode("utf-8"),
            "request_payload_sha256": _digest_bytes(payload_raw),
            "system_message": system,
        }
        self._journal(intent)
        response_was_received = False
        try:
            def observe_response(raw_request: bytes, raw_response: bytes) -> None:
                nonlocal response_was_received
                self._journal(
                    {
                        "arm": self.name,
                        "event": "raw_response_received",
                        "operation": operation,
                        "ordinal": ordinal,
                        "raw_request_base64": base64.b64encode(raw_request).decode("ascii"),
                        "raw_request_sha256": _digest_bytes(raw_request),
                        "raw_response_base64": base64.b64encode(raw_response).decode("ascii"),
                        "raw_response_sha256": _digest_bytes(raw_response),
                        "request_id": request_id,
                        "response_bytes": len(raw_response),
                    }
                )
                response_was_received = True

            completion = self.backend.complete(
                messages=messages,
                max_output_tokens=max_output_tokens,
                request_id=request_id,
                response_observer=observe_response,
            )
        except BaseException as error:
            self._journal(
                {
                    "arm": self.name,
                    "error": f"{type(error).__name__}: {error}",
                    "event": "failed",
                    "operation": operation,
                    "ordinal": ordinal,
                    "outcome": (
                        "received_invalid" if response_was_received else "unknown"
                    ),
                    "request_id": request_id,
                    "retry_permitted": False,
                }
            )
            raise
        self._journal(
            {
                "arm": self.name,
                "completion": completion.canonical(),
                "event": "response_received",
                "operation": operation,
                "ordinal": ordinal,
                "request_id": request_id,
            }
        )
        try:
            ledger_entry = CallLedgerEntry(
                arm=self.name,
                operation=operation,
                ordinal=ordinal,
                max_output_tokens=max_output_tokens,
                backend_identity_json=canonical_json_bytes(
                    dict(self.backend.identity)
                ).decode("utf-8"),
                request_payload_json=payload_raw.decode("utf-8"),
                request_payload_sha256=_digest_bytes(payload_raw),
                system_message=system,
                completion=completion,
            )
        except BaseException as error:
            self._journal(
                {
                    "arm": self.name,
                    "completion": completion.canonical(),
                    "error": f"{type(error).__name__}: {error}",
                    "event": "rejected_response",
                    "operation": operation,
                    "ordinal": ordinal,
                    "outcome": "received_invalid",
                    "request_id": request_id,
                    "retry_permitted": False,
                }
            )
            raise
        self.ledger.append(ledger_entry)
        self._journal(
            {
                "arm": self.name,
                "completion": completion.canonical(),
                "event": "completed",
                "operation": operation,
                "ordinal": ordinal,
                "request_id": request_id,
            }
        )
        return completion

    def _answer(
        self, probe: PublicProbe, *, state_kind: str, state: Any
    ) -> ArmAnswer:
        completion = self._call(
            operation="answer",
            max_output_tokens=self.budget.answer_max_output_tokens,
            system=(
                "Solve the opaque relation query using only STATE. Follow the "
                "ordered relations from source. Return exactly one JSON object "
                "with the single key choice and one supplied choice value. Do "
                "not write or alter memory."
            ),
            payload={
                "operation": "answer",
                "probe": probe.canonical(),
                "protocol": LIVE_PROTOCOL,
                "state": state,
                "state_kind": state_kind,
            },
        )
        receipt = canonical_sha256(
            {"arm": self.name, "operation": "answer", **completion.canonical()}
        )
        return ArmAnswer(
            response_text=completion.text,
            receipt_sha256=receipt,
            calls=1,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            latency_ms=completion.latency_ms,
        )


def _public_source_tokens(batch: LearningBatch) -> tuple[dict[str, Any], ...]:
    """Create opaque provenance ids without exposing reveal or gold metadata."""

    result: list[dict[str, Any]] = []
    for ordinal, token in enumerate(batch.learning_tokens):
        content = token.canonical()
        token_id = "learn-" + canonical_sha256(
            {
                "content": content,
                "episode_id": batch.episode_id,
                "ordinal": ordinal,
                "phase_nonce": canonical_sha256(
                    {
                        "episode_id": batch.episode_id,
                        "public_batch": [item.canonical() for item in batch.learning_tokens],
                    }
                ),
            }
        )[:24]
        result.append(
            {
                "content": content,
                "suggested_memory_id": "memory-" + canonical_sha256(content)[:24],
                "token_id": token_id,
            }
        )
    return tuple(result)


def _project_snapshot(snapshot: SelfModelSnapshot, budget: ArmBudget) -> dict[str, Any]:
    """Traverse agent-authored cell edges and expose only referenced memories."""

    if not snapshot.cells or snapshot.entry_cell_id is None:
        return {"cells": [], "entry_cell_id": None, "memories": []}
    cells_by_id = {cell.cell_id: cell for cell in snapshot.cells}
    queue = [snapshot.entry_cell_id]
    visited: list[CellRecord] = []
    seen: set[str] = set()
    while queue and len(visited) < budget.max_cells:
        cell_id = queue.pop(0)
        if cell_id in seen:
            continue
        seen.add(cell_id)
        cell = cells_by_id[cell_id]
        visited.append(cell)
        queue.extend(item for item in cell.next_cell_ids if item not in seen)
    memory_ids: list[str] = []
    for cell in visited:
        for memory_id in cell.memory_ids:
            if memory_id not in memory_ids:
                memory_ids.append(memory_id)
    if len(memory_ids) > budget.max_memories:
        raise ContinualLiveError("cell-selected memories exceed common context envelope")
    memories_by_id = {memory.memory_id: memory for memory in snapshot.memories}
    selected = tuple(memories_by_id[memory_id] for memory_id in memory_ids)
    value = {
        "cells": [cell.canonical() for cell in visited],
        "entry_cell_id": snapshot.entry_cell_id,
        "memories": [memory.canonical() for memory in selected],
    }
    if len(canonical_json_bytes(value)) > budget.max_state_bytes:
        raise ContinualLiveError("cell-selected HSWM state exceeds common byte envelope")
    return value


def _parse_structure_proposal(
    text: str,
    *,
    active: SelfModelSnapshot,
    source_tokens: Sequence[Mapping[str, Any]],
    generation: int,
    policy: SelfModelPolicy,
) -> Any:
    value = _strict_object(text)
    expected = {
        "cells",
        "delete_memory_ids",
        "entry_cell_id",
        "rationale",
        "upsert_memories",
    }
    if set(value) != expected:
        raise ContinualLiveError("structured update response field set is invalid")
    if not isinstance(value["rationale"], str) or not value["rationale"].strip():
        raise ContinualLiveError("structured update requires a rationale")
    if not all(isinstance(value[item], list) for item in ("cells", "delete_memory_ids", "upsert_memories")):
        raise ContinualLiveError("structured update list field is invalid")
    memories = tuple(memory_from_mapping(item) for item in value["upsert_memories"])
    cells = tuple(cell_from_mapping(item) for item in value["cells"])
    source_ids = tuple(str(item["token_id"]) for item in source_tokens)
    if not source_ids:
        raise ContinualLiveError("empty learning batch cannot author state")
    if not memories:
        raise ContinualLiveError("agent did not author memory from the public tokens")
    if set(source_ids) != {
        token_id for memory in memories for token_id in memory.source_token_ids
    }:
        raise ContinualLiveError("new memory provenance must cover exactly this public batch")
    if not cells or not isinstance(value["entry_cell_id"], str):
        raise ContinualLiveError("agent did not author a cell topology")
    if any(not isinstance(item, str) or not item for item in value["delete_memory_ids"]):
        raise ContinualLiveError("delete_memory_ids is invalid")
    proposal = make_mutation(
        base_snapshot_id=active.snapshot_id,
        expected_generation=generation,
        author_id=AUTHOR_ID,
        source_token_ids=source_ids,
        upsert_memories=memories,
        delete_memory_ids=tuple(value["delete_memory_ids"]),
        cell_topology_mode=CellTopologyMode.REPLACE,
        cells=cells,
        entry_cell_id=value["entry_cell_id"],
        rationale=value["rationale"],
    )
    # Controls discard the result, but proposal/check must still mean a full
    # contract and policy check rather than merely parsing plausible JSON.
    apply_mutation(active, proposal, policy)
    return proposal


def _structure_update_payload(
    active: SelfModelSnapshot, source_tokens: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "active_hswm": active.canonical(),
        "instruction": (
            "Absorb every public atomic relation by authoring the persistent HSWM "
            "structure itself. Return new or replacement MemoryRecords, explicit "
            "related_memory_ids, and a complete CellRecord routing topology. Cells "
            "must reference every memory needed for later graph traversal. There is "
            "no separate plan document. Preserve useful existing state."
        ),
        "operation": "author_hswm_state",
        "protocol": LIVE_PROTOCOL,
        "public_source_tokens": list(source_tokens),
        "response_contract": {
            "cells": [
                {
                    "capability": CAPABILITY,
                    "cell_id": "agent-chosen id",
                    "executor_agent_id": None,
                    "instruction": "agent-authored retrieval/routing instruction",
                    "memory_ids": ["existing or new memory id"],
                    "next_cell_ids": ["cell id"],
                }
            ],
            "delete_memory_ids": ["obsolete memory id"],
            "entry_cell_id": "one returned cell id",
            "rationale": "non-empty string",
            "upsert_memories": [
                {
                    "content": {
                        "relation": "opaque relation",
                        "source": "opaque source",
                        "target": "opaque target",
                    },
                    "kind": "atomic_relation",
                    "labels": ["agent-authored"],
                    "memory_id": "prefer supplied suggested_memory_id",
                    "related_memory_ids": ["memory id"],
                    "source_token_ids": ["supplied token_id"],
                }
            ],
        },
    }


class StructuredHSWMArm(_ModelArm):
    """Persistent HSWM arm backed by the audited SQLite CAS store."""

    def __init__(
        self,
        *,
        backend: ChatBackend,
        budget: ArmBudget,
        isolation_id: str,
        store_path: Path,
        journal_path: Path | None = None,
        name: str = "hswm",
        commit_updates: bool = True,
        read_history: bool = True,
        reset_after_commit: bool = False,
    ) -> None:
        super().__init__(
            name=name,
            backend=backend,
            budget=budget,
            isolation_id=isolation_id,
            journal_path=journal_path or Path(store_path).with_suffix(".calls.jsonl"),
        )
        self.commit_updates = commit_updates
        self.read_history = read_history
        self.reset_after_commit = reset_after_commit
        if reset_after_commit and not commit_updates:
            raise ValueError("reset_after_commit requires committed proposals")
        self.store_path = Path(store_path)
        self.policy = _proposal_policy(budget)
        self.store = SQLiteSelfModelStore(self.store_path, policy=self.policy)
        active = self.store.active_snapshot()
        if active.generation != 0 or active.snapshot.snapshot_id != GENESIS.snapshot_id:
            raise ContinualLiveError("arm store did not start from exact empty genesis")
        self._source_token_ids: list[str] = []

    def state_canonical_bytes(self) -> bytes:
        # The evaluator reads the durable active snapshot itself; the model never
        # supplies or hashes this value.
        return canonical_json_bytes(self.store.active_snapshot().snapshot.canonical())

    def answer(self, probe: PublicProbe) -> ArmAnswer:
        active = self.store.active_snapshot().snapshot
        if not self.read_history:
            active = GENESIS
        return self._answer(
            probe,
            state_kind="hswm_cells_and_memories",
            state=_project_snapshot(active, self.budget),
        )

    def update(self, batch: LearningBatch) -> ArmUpdate:
        source_tokens = _public_source_tokens(batch)
        active_record = self.store.active_snapshot()
        prompt_snapshot = active_record.snapshot if self.read_history else GENESIS
        completion = self._call(
            operation="update",
            max_output_tokens=self.budget.update_max_output_tokens,
            system=(
                "Return exactly one JSON object matching response_contract. "
                "Author memories, relations, cells, and routing directly in HSWM. "
                "Use only the supplied public source tokens; do not infer a gold answer."
            ),
            payload=_structure_update_payload(prompt_snapshot, source_tokens),
        )
        proposal = _parse_structure_proposal(
            completion.text,
            active=prompt_snapshot,
            source_tokens=source_tokens,
            generation=active_record.generation if self.commit_updates else 0,
            policy=self.policy,
        )
        activation_id: str | None = None
        reset_activation_id: str | None = None
        if self.commit_updates:
            cognitive_tokens = tuple(
                make_token(
                    token_id=str(item["token_id"]),
                    episode_id=batch.episode_id,
                    position=batch.after_step * 1000 + ordinal,
                    role="environment",
                    content=item["content"],
                    provenance={
                        "protocol": LIVE_PROTOCOL,
                        "public_learning_token": True,
                    },
                )
                for ordinal, item in enumerate(source_tokens)
            )
            self.store.append_tokens(cognitive_tokens)
            activation = self.store.commit(proposal)
            activation_id = activation.activation_id
            self._source_token_ids.extend(token.token_id for token in cognitive_tokens)
            if self.reset_after_commit:
                reset = self.store.activate_snapshot(
                    GENESIS.snapshot_id,
                    expected_generation=activation.active_generation,
                    reason="RESET_CONTROL_BEFORE_NEXT_PROBE",
                    author_id="evaluator:reset-control",
                    source_token_ids=(cognitive_tokens[-1].token_id,),
                )
                reset_activation_id = reset.activation_id
        elif self.store.active_snapshot().snapshot.snapshot_id != GENESIS.snapshot_id:
            raise ContinualLiveError(f"control arm {self.name} left genesis")
        if self.reset_after_commit and (
            self.store.active_snapshot().snapshot.snapshot_id != GENESIS.snapshot_id
        ):
            raise ContinualLiveError("reset control failed to reactivate exact genesis")
        receipt = canonical_sha256(
            {
                "activation_id": activation_id,
                "arm": self.name,
                "committed": self.commit_updates,
                "completion": completion.canonical(),
                "proposal_sha256": canonical_sha256(proposal.canonical()),
                "reset_activation_id": reset_activation_id,
            }
        )
        return ArmUpdate(
            receipt_sha256=receipt,
            calls=1,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            latency_ms=completion.latency_ms,
        )

    def checkpoint(self) -> "SnapshotCheckpoint":
        active = self.store.active_snapshot()
        raw = canonical_json_bytes(active.snapshot.canonical())
        return SnapshotCheckpoint(
            snapshot_id=active.snapshot.snapshot_id,
            snapshot_sha256=_digest_bytes(raw),
            generation=active.generation,
        )

    def remove_learned_state(self) -> "StateTransitionReceipt":
        active = self.store.active_snapshot()
        if active.snapshot.snapshot_id == GENESIS.snapshot_id:
            raise ContinualLiveError("cannot remove an already-empty state")
        if not self._source_token_ids:
            raise ContinualLiveError("removal lacks a stored public source token")
        before = _digest_bytes(canonical_json_bytes(active.snapshot.canonical()))
        receipt = self.store.activate_snapshot(
            GENESIS.snapshot_id,
            expected_generation=active.generation,
            reason="CONTINUAL_REMOVAL_PROBE",
            author_id="evaluator:removal-probe",
            source_token_ids=(self._source_token_ids[-1],),
        )
        after_snapshot = self.store.active_snapshot().snapshot
        after = _digest_bytes(canonical_json_bytes(after_snapshot.canonical()))
        if after_snapshot.snapshot_id != GENESIS.snapshot_id:
            raise ContinualLiveError("state removal did not activate exact genesis")
        return StateTransitionReceipt.make(
            operation="remove_to_genesis",
            before_state_sha256=before,
            after_state_sha256=after,
            activation_id=receipt.activation_id,
        )

    def restore_checkpoint(
        self, checkpoint: "SnapshotCheckpoint"
    ) -> "StateTransitionReceipt":
        active = self.store.active_snapshot()
        if active.snapshot.snapshot_id != GENESIS.snapshot_id:
            raise ContinualLiveError("restore requires exact genesis as its base")
        if not self._source_token_ids:
            raise ContinualLiveError("restore lacks a stored public source token")
        before = _digest_bytes(canonical_json_bytes(active.snapshot.canonical()))
        restored = self.store.load_snapshot(checkpoint.snapshot_id)
        restored_raw = canonical_json_bytes(restored.canonical())
        if _digest_bytes(restored_raw) != checkpoint.snapshot_sha256:
            raise ContinualLiveError("checkpoint bytes changed before restore")
        receipt = self.store.activate_snapshot(
            checkpoint.snapshot_id,
            expected_generation=active.generation,
            reason="CONTINUAL_EXACT_RESTORE",
            author_id="evaluator:removal-probe",
            source_token_ids=(self._source_token_ids[-1],),
        )
        after = self.state_canonical_bytes()
        if _digest_bytes(after) != checkpoint.snapshot_sha256:
            raise ContinualLiveError("restored snapshot is not bitwise identical")
        return StateTransitionReceipt.make(
            operation="restore_checkpoint",
            before_state_sha256=before,
            after_state_sha256=_digest_bytes(after),
            activation_id=receipt.activation_id,
        )

    def restart_storage(self) -> None:
        """Drop all live connections and reopen the same durable store."""

        policy = self.store.policy
        self.store.close()
        self.store = SQLiteSelfModelStore(self.store_path, policy=policy)


class ResetArm(StructuredHSWMArm):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            name="reset",
            commit_updates=True,
            read_history=False,
            reset_after_commit=True,
            **kwargs,
        )


class NoWriteArm(StructuredHSWMArm):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(name="no_write", commit_updates=False, read_history=False, **kwargs)


class PlainTextArm(_ModelArm):
    """Bounded, persistent linear-memory control with no structural fields."""

    def __init__(
        self,
        *,
        backend: ChatBackend,
        budget: ArmBudget,
        isolation_id: str,
        state_path: Path,
        journal_path: Path | None = None,
    ) -> None:
        super().__init__(
            name="plain",
            backend=backend,
            budget=budget,
            isolation_id=isolation_id,
            journal_path=journal_path or Path(state_path).with_suffix(".calls.jsonl"),
        )
        self.state_path = Path(state_path)
        if self.state_path.exists():
            raise ContinualLiveError("plain state path must be fresh")
        self._memory = ""
        self._persist()

    def _persist(self) -> None:
        _write_json_atomic(
            self.state_path,
            {"memory": self._memory, "schema": "linear-plain-memory/v1"},
        )

    def state_canonical_bytes(self) -> bytes:
        raw = self.state_path.read_bytes()
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ContinualLiveError("plain state file is corrupt") from error
        canonical = canonical_json_bytes(value)
        if canonical_json_bytes(
            {"memory": self._memory, "schema": "linear-plain-memory/v1"}
        ) != canonical:
            raise ContinualLiveError("plain state file differs from active memory")
        return canonical

    def answer(self, probe: PublicProbe) -> ArmAnswer:
        return self._answer(probe, state_kind="bounded_plain_text", state=self._memory)

    def update(self, batch: LearningBatch) -> ArmUpdate:
        source_tokens = _public_source_tokens(batch)
        completion = self._call(
            operation="update",
            max_output_tokens=self.budget.update_max_output_tokens,
            system=(
                "Maintain one linear plain-text note from the supplied public atomic "
                "relations. Return exactly {\"memory\":\"...\"}. Do not create graph "
                "relations, cells, routes, JSON records inside the string, or infer a gold answer."
            ),
            payload={
                "current_memory": self._memory,
                "operation": "update_plain_memory",
                "protocol": LIVE_PROTOCOL,
                "public_learning_tokens": [item["content"] for item in source_tokens],
                "response_contract": {"memory": "one linear plain-text note"},
            },
        )
        value = _strict_object(completion.text)
        if set(value) != {"memory"} or not isinstance(value["memory"], str):
            raise ContinualLiveError("plain update response field set is invalid")
        if len(value["memory"].encode("utf-8")) > self.budget.max_state_bytes:
            raise ContinualLiveError("plain state exceeds the common byte envelope")
        self._memory = value["memory"]
        self._persist()
        return ArmUpdate(
            receipt_sha256=canonical_sha256(
                {"arm": self.name, "completion": completion.canonical()}
            ),
            calls=1,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            latency_ms=completion.latency_ms,
        )


@dataclass(frozen=True, slots=True)
class SnapshotCheckpoint:
    snapshot_id: str
    snapshot_sha256: str
    generation: int

    def canonical(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "snapshot_id": self.snapshot_id,
            "snapshot_sha256": self.snapshot_sha256,
        }


@dataclass(frozen=True, slots=True)
class StateTransitionReceipt:
    operation: str
    before_state_sha256: str
    after_state_sha256: str
    activation_id: str
    receipt_sha256: str

    @classmethod
    def make(
        cls,
        *,
        operation: str,
        before_state_sha256: str,
        after_state_sha256: str,
        activation_id: str,
    ) -> "StateTransitionReceipt":
        unsigned = {
            "activation_id": activation_id,
            "after_state_sha256": after_state_sha256,
            "before_state_sha256": before_state_sha256,
            "operation": operation,
        }
        return cls(**unsigned, receipt_sha256=canonical_sha256(unsigned))

    def canonical(self) -> dict[str, Any]:
        return {
            "activation_id": self.activation_id,
            "after_state_sha256": self.after_state_sha256,
            "before_state_sha256": self.before_state_sha256,
            "operation": self.operation,
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class RemovalRestoreResult:
    stream_manifest_sha256: str
    primary_run_sha256: str
    primary_final_h_state_sha256: str
    sealed_probe_pack_sha256: str
    active_state_sha256: str
    deleted_state_sha256: str
    restored_state_sha256: str
    active_choices: tuple[str | None, ...]
    deleted_choices: tuple[str | None, ...]
    restored_choices: tuple[str | None, ...]
    active_correct: tuple[bool, ...]
    deleted_correct: tuple[bool, ...]
    restored_correct: tuple[bool, ...]
    active_answer_receipts: tuple[str, ...]
    deleted_answer_receipts: tuple[str, ...]
    restored_answer_receipts: tuple[str, ...]
    active_score: int
    deleted_score: int
    restored_score: int
    remove_receipt: StateTransitionReceipt
    restore_receipt: StateTransitionReceipt
    exact_state_restore: bool
    exact_choice_restore: bool
    state_dependence_observed: bool
    removal_mediation_gate_passed: bool
    result_sha256: str

    def unsigned(self) -> dict[str, Any]:
        return {
            "active_answer_receipts": list(self.active_answer_receipts),
            "active_choices": list(self.active_choices),
            "active_correct": list(self.active_correct),
            "active_score": self.active_score,
            "active_state_sha256": self.active_state_sha256,
            "deleted_answer_receipts": list(self.deleted_answer_receipts),
            "deleted_choices": list(self.deleted_choices),
            "deleted_correct": list(self.deleted_correct),
            "deleted_score": self.deleted_score,
            "deleted_state_sha256": self.deleted_state_sha256,
            "state_dependence_observed": self.state_dependence_observed,
            "exact_choice_restore": self.exact_choice_restore,
            "exact_state_restore": self.exact_state_restore,
            "removal_mediation_gate_passed": self.removal_mediation_gate_passed,
            "primary_final_h_state_sha256": self.primary_final_h_state_sha256,
            "primary_run_sha256": self.primary_run_sha256,
            "remove_receipt": self.remove_receipt.canonical(),
            "restore_receipt": self.restore_receipt.canonical(),
            "restored_answer_receipts": list(self.restored_answer_receipts),
            "restored_choices": list(self.restored_choices),
            "restored_correct": list(self.restored_correct),
            "restored_score": self.restored_score,
            "restored_state_sha256": self.restored_state_sha256,
            "sealed_probe_pack_sha256": self.sealed_probe_pack_sha256,
            "stream_manifest_sha256": self.stream_manifest_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "result_sha256": self.result_sha256}


def run_removal_restore_probes(
    arm: StructuredHSWMArm,
    probes: Sequence[tuple[PublicProbe, str]],
    *,
    primary_run: StreamRun,
) -> RemovalRestoreResult:
    """Run five evaluator-held A/D/B probes around exact durable state removal.

    Gold answers remain in this evaluator function and are never included in an
    arm request.  This hook establishes state mediation only; topology-specific
    causality requires a separate content-preserving structure ablation.
    """

    if len(probes) != 5:
        raise ContinualLiveError("removal/restore requires exactly five sealed probes")

    if primary_run.run_sha256 != canonical_sha256(primary_run.unsigned()):
        raise ContinualLiveError("primary run content hash is invalid")
    h_results = tuple(result for result in primary_run.results if result.arm == "hswm")
    if not h_results:
        raise ContinualLiveError("primary run lacks HSWM results")
    final_h = max(h_results, key=lambda result: result.step)
    primary_final_h_state_sha256 = final_h.post_update_state_sha256
    stream_manifest_sha256 = primary_run.manifest_sha256
    pack_sha256 = sealed_probe_pack_sha256(probes)

    def answer_pack() -> tuple[
        tuple[str | None, ...], tuple[bool, ...], tuple[str, ...]
    ]:
        before = _digest_bytes(arm.state_canonical_bytes())
        choices: list[str | None] = []
        scores: list[bool] = []
        receipts: list[str] = []
        for probe, answer in probes:
            if answer not in probe.choices:
                raise ContinualLiveError("sealed answer is absent from public choices")
            response = arm.answer(probe)
            choice = parse_choice(response.response_text, choices=probe.choices)
            choices.append(choice)
            scores.append(choice == answer)
            receipts.append(response.receipt_sha256)
        after = _digest_bytes(arm.state_canonical_bytes())
        if after != before:
            raise ContinualLiveError("read-only removal probe mutated HSWM state")
        return tuple(choices), tuple(scores), tuple(receipts)

    checkpoint = arm.checkpoint()
    active_state = _digest_bytes(arm.state_canonical_bytes())
    if active_state != primary_final_h_state_sha256:
        raise ContinualLiveError(
            "removal active state differs from the primary HSWM final state"
        )
    active_choices, active_correct, active_receipts = answer_pack()
    remove_receipt = arm.remove_learned_state()
    deleted_state = _digest_bytes(arm.state_canonical_bytes())
    if deleted_state != _digest_bytes(canonical_json_bytes(GENESIS.canonical())):
        raise ContinualLiveError("deleted probe state is not exact genesis")
    deleted_choices, deleted_correct, deleted_receipts = answer_pack()
    arm.restart_storage()
    restore_receipt = arm.restore_checkpoint(checkpoint)
    restored_state = _digest_bytes(arm.state_canonical_bytes())
    restored_choices, restored_correct, restored_receipts = answer_pack()
    exact_state = active_state == restored_state == checkpoint.snapshot_sha256
    exact_choice = active_choices == restored_choices
    if not exact_state or not exact_choice:
        raise ContinualLiveError("A/D/B probe failed exact deterministic restoration")
    active_score = sum(active_correct)
    deleted_score = sum(deleted_correct)
    restored_score = sum(restored_correct)
    state_dependence_observed = (
        active_score > deleted_score and restored_score > deleted_score
    )
    removal_mediation_gate_passed = (
        state_dependence_observed and exact_state and exact_choice
    )
    unsigned = {
        "active_answer_receipts": list(active_receipts),
        "active_choices": list(active_choices),
        "active_correct": list(active_correct),
        "active_score": active_score,
        "active_state_sha256": active_state,
        "deleted_answer_receipts": list(deleted_receipts),
        "deleted_choices": list(deleted_choices),
        "deleted_correct": list(deleted_correct),
        "deleted_score": deleted_score,
        "deleted_state_sha256": deleted_state,
        "state_dependence_observed": state_dependence_observed,
        "exact_choice_restore": exact_choice,
        "exact_state_restore": exact_state,
        "removal_mediation_gate_passed": removal_mediation_gate_passed,
        "primary_final_h_state_sha256": primary_final_h_state_sha256,
        "primary_run_sha256": primary_run.run_sha256,
        "remove_receipt": remove_receipt.canonical(),
        "restore_receipt": restore_receipt.canonical(),
        "restored_answer_receipts": list(restored_receipts),
        "restored_choices": list(restored_choices),
        "restored_correct": list(restored_correct),
        "restored_score": restored_score,
        "restored_state_sha256": restored_state,
        "sealed_probe_pack_sha256": pack_sha256,
        "stream_manifest_sha256": stream_manifest_sha256,
    }
    return RemovalRestoreResult(
        stream_manifest_sha256=stream_manifest_sha256,
        primary_run_sha256=primary_run.run_sha256,
        primary_final_h_state_sha256=primary_final_h_state_sha256,
        sealed_probe_pack_sha256=pack_sha256,
        active_state_sha256=active_state,
        deleted_state_sha256=deleted_state,
        restored_state_sha256=restored_state,
        active_choices=active_choices,
        deleted_choices=deleted_choices,
        restored_choices=restored_choices,
        active_correct=active_correct,
        deleted_correct=deleted_correct,
        restored_correct=restored_correct,
        active_answer_receipts=active_receipts,
        deleted_answer_receipts=deleted_receipts,
        restored_answer_receipts=restored_receipts,
        active_score=active_score,
        deleted_score=deleted_score,
        restored_score=restored_score,
        remove_receipt=remove_receipt,
        restore_receipt=restore_receipt,
        exact_state_restore=exact_state,
        exact_choice_restore=exact_choice,
        state_dependence_observed=state_dependence_observed,
        removal_mediation_gate_passed=removal_mediation_gate_passed,
        result_sha256=canonical_sha256(unsigned),
    )


def make_sealed_probe_pack(
    manifest: StreamManifest, *, count: int = 5
) -> tuple[tuple[PublicProbe, str], ...]:
    """Derive evaluator-held probes unused by the prequential 20-step stream."""

    if count <= 0:
        raise ValueError("sealed probe count must be positive")
    learned = {
        (edge.source, edge.relation): edge.target
        for edge in manifest.edges
        if edge.reveal_step <= manifest.horizon
    }
    entities = sorted(
        {value for edge in manifest.edges for value in (edge.source, edge.target)}
    )
    relations = sorted({edge.relation for edge in manifest.edges})
    used = {(query.source, query.relations) for query in manifest.queries}
    candidates: list[tuple[str, tuple[str, ...], str]] = []
    for source in entities:
        for path in itertools.product(relations, repeat=2):
            relation_path = tuple(path)
            if (source, relation_path) in used:
                continue
            node = source
            for relation in relation_path:
                target = learned.get((node, relation))
                if target is None:
                    break
                node = target
            else:
                candidates.append((source, relation_path, node))
    candidates.sort(
        key=lambda item: canonical_sha256(
            {
                "domain": "sealed-removal-probe",
                "manifest_sha256": manifest.manifest_sha256,
                "relations": list(item[1]),
                "source": item[0],
            }
        )
    )
    if len(candidates) < count:
        raise ContinualLiveError("not enough fully learned unused sealed paths")
    result: list[tuple[PublicProbe, str]] = []
    for index, (source, relation_path, answer) in enumerate(candidates[:count]):
        ranked = sorted(
            (entity for entity in entities if entity != answer),
            key=lambda entity: canonical_sha256(
                {
                    "answer": answer,
                    "domain": "sealed-removal-choice",
                    "entity": entity,
                    "index": index,
                    "manifest_sha256": manifest.manifest_sha256,
                }
            ),
        )
        choices = [answer, *ranked[: manifest.choice_count - 1]]
        choices.sort(
            key=lambda entity: canonical_sha256(
                {
                    "domain": "sealed-removal-order",
                    "entity": entity,
                    "index": index,
                    "manifest_sha256": manifest.manifest_sha256,
                }
            )
        )
        result.append(
            (
                PublicProbe(
                    step=manifest.horizon + index + 1,
                    source=source,
                    relations=relation_path,
                    choices=tuple(choices),
                ),
                answer,
            )
        )
    return tuple(result)


def sealed_probe_pack_sha256(
    probes: Sequence[tuple[PublicProbe, str]],
) -> str:
    return canonical_sha256(
        [
            {"answer": answer, "public_probe": probe.canonical()}
            for probe, answer in probes
        ]
    )


@dataclass(frozen=True, slots=True)
class ParityAudit:
    arm_names: tuple[str, ...]
    primary_call_counts: tuple[int, ...]
    primary_ledger_sha256s: tuple[str, ...]
    primary_operation_sequences: tuple[tuple[str, ...], ...]
    call_parity: bool
    usage_complete: bool
    config_parity: bool
    model_parity: bool
    exact_input_token_parity: bool
    confirmatory: bool
    valid: bool
    audit_sha256: str

    def canonical(self) -> dict[str, Any]:
        return {
            "arm_names": list(self.arm_names),
            "audit_sha256": self.audit_sha256,
            "call_parity": self.call_parity,
            "config_parity": self.config_parity,
            "confirmatory": self.confirmatory,
            "exact_input_token_parity": self.exact_input_token_parity,
            "model_parity": self.model_parity,
            "primary_call_counts": list(self.primary_call_counts),
            "primary_ledger_sha256s": list(self.primary_ledger_sha256s),
            "primary_operation_sequences": [
                list(sequence) for sequence in self.primary_operation_sequences
            ],
            "usage_complete": self.usage_complete,
            "valid": self.valid,
        }


def audit_parity(
    arms: Sequence[_ModelArm], *, confirmatory: bool
) -> ParityAudit:
    if len(arms) != 4:
        raise ContinualLiveError("parity audit requires all four arms")
    arm_names = tuple(arm.name for arm in arms)
    primary_call_counts = tuple(len(arm.ledger) for arm in arms)
    primary_ledger_sha256s = tuple(
        canonical_sha256([entry.canonical() for entry in arm.ledger]) for arm in arms
    )
    primary_operation_sequences = tuple(
        tuple(entry.operation for entry in arm.ledger) for arm in arms
    )
    configs = [canonical_json_bytes(arm.audit_config()) for arm in arms]
    config_parity = len(set(configs)) == 1
    operation_sequences = [
        tuple((entry.operation, entry.max_output_tokens) for entry in arm.ledger)
        for arm in arms
    ]
    call_parity = len(set(operation_sequences)) == 1 and all(
        len(sequence) > 0 for sequence in operation_sequences
    )
    usage_complete = all(
        entry.completion.usage_reported for arm in arms for entry in arm.ledger
    )
    expected_models = {str(arm.backend.identity.get("model", "")) for arm in arms}
    returned_models = {
        entry.completion.model for arm in arms for entry in arm.ledger
    }
    model_parity = (
        len(expected_models) == 1
        and "" not in expected_models
        and returned_models == expected_models
    )
    exact_input = False
    if call_parity:
        exact_input = all(
            len({arm.ledger[index].completion.input_tokens for arm in arms}) == 1
            for index in range(len(arms[0].ledger))
        )
    valid = call_parity and usage_complete and config_parity and model_parity
    if confirmatory:
        valid = valid and exact_input
    unsigned = {
        "arm_names": list(arm_names),
        "call_parity": call_parity,
        "config_parity": config_parity,
        "confirmatory": confirmatory,
        "exact_input_token_parity": exact_input,
        "model_parity": model_parity,
        "primary_call_counts": list(primary_call_counts),
        "primary_ledger_sha256s": list(primary_ledger_sha256s),
        "primary_operation_sequences": [
            list(sequence) for sequence in primary_operation_sequences
        ],
        "usage_complete": usage_complete,
        "valid": valid,
    }
    return ParityAudit(
        arm_names=arm_names,
        primary_call_counts=primary_call_counts,
        primary_ledger_sha256s=primary_ledger_sha256s,
        primary_operation_sequences=primary_operation_sequences,
        call_parity=call_parity,
        usage_complete=usage_complete,
        config_parity=config_parity,
        model_parity=model_parity,
        exact_input_token_parity=exact_input,
        confirmatory=confirmatory,
        valid=valid,
        audit_sha256=canonical_sha256(unsigned),
    )


def scoped_call_ledgers(
    arms: Sequence[_ModelArm],
    audit: ParityAudit,
    *,
    mediation_enabled: bool,
) -> dict[str, Any]:
    """Freeze the four-arm primary prefix apart from H-only mediation calls."""

    if tuple(arm.name for arm in arms) != audit.arm_names:
        raise ContinualLiveError("ledger arms differ from the parity snapshot")
    primary: dict[str, list[dict[str, Any]]] = {}
    mediation: dict[str, list[dict[str, Any]]] = {}
    for index, arm in enumerate(arms):
        prefix_count = audit.primary_call_counts[index]
        prefix = arm.ledger[:prefix_count]
        suffix = arm.ledger[prefix_count:]
        if canonical_sha256([entry.canonical() for entry in prefix]) != (
            audit.primary_ledger_sha256s[index]
        ):
            raise ContinualLiveError("primary call-ledger prefix changed after audit")
        if tuple(entry.operation for entry in prefix) != (
            audit.primary_operation_sequences[index]
        ):
            raise ContinualLiveError("primary operation sequence changed after audit")
        primary[arm.name] = [entry.canonical() for entry in prefix]
        mediation[arm.name] = [entry.canonical() for entry in suffix]
    expected_h_suffix = 15 if mediation_enabled else 0
    if len(mediation["hswm"]) != expected_h_suffix or any(
        mediation[name] for name in ("reset", "no_write", "plain")
    ):
        raise ContinualLiveError("mediation calls contaminated the primary parity scope")
    if any(entry["operation"] != "answer" for entry in mediation["hswm"]):
        raise ContinualLiveError("mediation suffix contains a non-probe call")
    unsigned = {
        "mediation": mediation,
        "mediation_enabled": mediation_enabled,
        "parity_audit_sha256": audit.audit_sha256,
        "primary": primary,
    }
    return {**unsigned, "scoped_ledger_sha256": canonical_sha256(unsigned)}


def build_four_arms(
    *,
    backend_factory: Callable[[], ChatBackend],
    budget: ArmBudget,
    state_dir: Path,
    isolation_prefix: str,
) -> tuple[StructuredHSWMArm, ResetArm, NoWriteArm, PlainTextArm]:
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=False)
    return (
        StructuredHSWMArm(
            backend=backend_factory(),
            budget=budget,
            isolation_id=f"{isolation_prefix}:hswm",
            store_path=state_dir / "hswm" / "state.sqlite3",
            journal_path=state_dir / "hswm" / "calls.jsonl",
        ),
        ResetArm(
            backend=backend_factory(),
            budget=budget,
            isolation_id=f"{isolation_prefix}:reset",
            store_path=state_dir / "reset" / "state.sqlite3",
            journal_path=state_dir / "reset" / "calls.jsonl",
        ),
        NoWriteArm(
            backend=backend_factory(),
            budget=budget,
            isolation_id=f"{isolation_prefix}:no_write",
            store_path=state_dir / "no_write" / "state.sqlite3",
            journal_path=state_dir / "no_write" / "calls.jsonl",
        ),
        PlainTextArm(
            backend=backend_factory(),
            budget=budget,
            isolation_id=f"{isolation_prefix}:plain",
            state_path=state_dir / "plain" / "state.json",
            journal_path=state_dir / "plain" / "calls.jsonl",
        ),
    )


def run_four_arm_stream(
    manifest: StreamManifest,
    *,
    backend_factory: Callable[[], ChatBackend],
    budget: ArmBudget,
    state_dir: Path,
    confirmatory: bool = False,
) -> tuple[StreamRun, ParityAudit, tuple[_ModelArm, ...]]:
    arms = build_four_arms(
        backend_factory=backend_factory,
        budget=budget,
        state_dir=state_dir,
        isolation_prefix=manifest.episode_id,
    )
    run = run_prequential(manifest, arms)
    audit = audit_parity(arms, confirmatory=confirmatory)
    if not audit.valid:
        qualifier = "confirmatory " if confirmatory else ""
        raise ContinualLiveError(f"{qualifier}call/token parity audit failed")
    return run, audit, arms


def _read_secret_seeds(path: Path) -> tuple[bytes, ...]:
    metadata = path.stat()
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ContinualLiveError("seed file permissions must be 0600 or stricter")
    raw = path.read_text(encoding="ascii").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = [line.strip() for line in raw.splitlines() if line.strip()]
    if not isinstance(parsed, list) or not parsed:
        raise ContinualLiveError("seed file must be a JSON list or newline hex list")
    result: list[bytes] = []
    for item in parsed:
        if not isinstance(item, str):
            raise ContinualLiveError("every seed preimage must be hex text")
        try:
            seed = bytes.fromhex(item)
        except ValueError as error:
            raise ContinualLiveError("seed file contains invalid hex") from error
        if len(seed) != 32:
            raise ContinualLiveError("every frozen seed preimage must be exactly 32 bytes")
        result.append(seed)
    return tuple(result)


def _read_commitments(path: Path) -> tuple[str, ...]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContinualLiveError(f"cannot read commitment list: {error}") from error
    if isinstance(value, Mapping):
        value = value.get("commitments")
    if not isinstance(value, list) or not value:
        raise ContinualLiveError("commitments file requires a non-empty JSON list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or len(item) != 64:
            raise ContinualLiveError("commitment must be one SHA-256 hex digest")
        try:
            int(item, 16)
        except ValueError as error:
            raise ContinualLiveError("commitment contains non-hex text") from error
        result.append(item.lower())
    if len(result) != len(set(result)):
        raise ContinualLiveError("seed commitments must be unique")
    return tuple(result)


_PRECOMMIT_FIELDS = {
    "assignment_document",
    "assignment_sha256",
    "commitment_document",
    "commitment_set_sha256",
    "confirmatory_denylist",
    "confirmatory_eligible",
    "engineering_only",
    "frozen_before_pilot_completion_calls",
    "intended_provider",
    "precommit_sha256",
    "preimages_revealed",
    "primary_execution",
    "primary_seed_indices",
    "protocol",
    "reserve_seed_indices",
    "schema",
    "seed_preimage_encoding",
    "supersedes_canonical_artifact_sha256",
    "supersession_reason",
}


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ContinualLiveError(f"{label} must be a SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as error:
        raise ContinualLiveError(f"{label} contains non-hex text") from error
    return value.lower()


def _read_pilot_precommit(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    if _digest_bytes(raw) != FROZEN_PILOT_PRECOMMIT_ARTIFACT_SHA256:
        raise ContinualLiveError("pilot precommit is not the exact frozen v2 artifact")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContinualLiveError(f"invalid pilot precommit JSON: {error}") from error
    if not isinstance(value, dict) or set(value) != _PRECOMMIT_FIELDS:
        raise ContinualLiveError("pilot precommit field set is not frozen v2")
    if canonical_json_bytes(value) != raw:
        raise ContinualLiveError(
            "pilot precommit must be exact canonical JSON with no trailing newline"
        )
    unsigned = {key: item for key, item in value.items() if key != "precommit_sha256"}
    if (
        _require_sha256(value["precommit_sha256"], "precommit_sha256")
        != FROZEN_PILOT_PRECOMMIT_SHA256
        or value["precommit_sha256"] != canonical_sha256(unsigned)
    ):
        raise ContinualLiveError("pilot precommit self-hash mismatch")
    if (
        value["schema"] != "hswm-continual-pilot-precommit/v2"
        or value["protocol"] != PROTOCOL
        or value["engineering_only"] is not True
        or value["confirmatory_eligible"] is not False
        or value["preimages_revealed"] is not False
        or value["frozen_before_pilot_completion_calls"] is not True
        or value["primary_seed_indices"] != [0, 1]
        or value["reserve_seed_indices"] != [2, 3]
        or value["seed_preimage_encoding"]
        != "32 raw bytes; commitment=sha256(raw bytes)"
    ):
        raise ContinualLiveError("pilot precommit authority flags differ from v2")
    commitment_document = value["commitment_document"]
    if not isinstance(commitment_document, dict) or set(commitment_document) != {
        "commitments",
        "protocol",
        "purpose",
        "schema",
    }:
        raise ContinualLiveError("commitment_document field set is invalid")
    commitments = commitment_document["commitments"]
    if (
        commitment_document["schema"]
        != "hswm-continual-pilot-seed-commitments/v1"
        or commitment_document["protocol"] != PROTOCOL
        or commitment_document["purpose"]
        != "engineering-pilot-only-never-confirmatory"
        or not isinstance(commitments, list)
        or len(commitments) != 4
        or len(set(commitments)) != 4
    ):
        raise ContinualLiveError("commitment_document values are invalid")
    for index, commitment in enumerate(commitments):
        _require_sha256(commitment, f"commitment[{index}]")
    if _require_sha256(value["commitment_set_sha256"], "commitment_set_sha256") != canonical_sha256(commitment_document):
        raise ContinualLiveError("commitment document hash mismatch")
    assignment = value["assignment_document"]
    if not isinstance(assignment, dict) or set(assignment) != {
        "primary",
        "protocol",
        "purpose",
        "reserve",
        "reserve_rule",
        "resume_rule",
        "schema",
    }:
        raise ContinualLiveError("assignment_document field set is invalid")
    if (
        assignment["schema"] != "hswm-continual-pilot-seed-assignment/v1"
        or assignment["protocol"] != PROTOCOL
        or assignment["purpose"] != "engineering-pilot-only-never-confirmatory"
        or assignment["primary"] != commitments[:2]
        or assignment["reserve"] != commitments[2:]
        or assignment["reserve_rule"]
        != "mechanical infrastructure invalidity only; never outcome-conditioned"
        or assignment["resume_rule"]
        != "no retry or resume with a revealed preimage"
    ):
        raise ContinualLiveError("assignment_document values are invalid")
    if _require_sha256(value["assignment_sha256"], "assignment_sha256") != canonical_sha256(assignment):
        raise ContinualLiveError("assignment document hash mismatch")
    if value["confirmatory_denylist"] != commitments:
        raise ContinualLiveError("confirmatory denylist must contain all four seeds")
    execution = value["primary_execution"]
    expected_execution = {
        "answer_max_tokens": 128,
        "arms": ["hswm", "reset", "no_write", "plain"],
        "base_endpoint_calls_per_stream": 164,
        "choice_count": 8,
        "delay": 4,
        "endpoint_call_budget_total": 358,
        "endpoint_calls_per_stream": 179,
        "horizon": 20,
        "max_input_bytes": 2_000_000,
        "max_state_bytes": 1_000_000,
        "per_call_timeout_seconds": 120.0,
        "removal_restore": True,
        "removal_restore_extra_calls_per_stream": 15,
        "removal_restore_probes_per_stream": 5,
        "resume_allowed": False,
        "retry_limit": 0,
        "streams": 2,
        "update_max_tokens": 8192,
    }
    if execution != expected_execution:
        raise ContinualLiveError("primary execution differs from frozen pilot v2")
    provider = value["intended_provider"]
    if not isinstance(provider, dict) or set(provider) != {
        "enable_thinking",
        "endpoint",
        "model_revision",
        "model_root",
        "served_model",
        "temperature",
        "vllm_version",
    }:
        raise ContinualLiveError("intended_provider field set is invalid")
    if (
        provider["enable_thinking"] is not False
        or provider["temperature"] != 0.0
        or not isinstance(provider["endpoint"], str)
        or not provider["endpoint"].startswith(("http://", "https://"))
        or not isinstance(provider["served_model"], str)
        or not provider["served_model"]
        or not isinstance(provider["model_root"], str)
        or not provider["model_root"]
        or not re.fullmatch(r"[0-9a-f]{40}", str(provider["model_revision"]))
        or not isinstance(provider["vllm_version"], str)
        or not provider["vllm_version"]
    ):
        raise ContinualLiveError("intended_provider values are invalid")
    _require_sha256(
        value["supersedes_canonical_artifact_sha256"],
        "supersedes_canonical_artifact_sha256",
    )
    if not isinstance(value["supersession_reason"], str) or "8192" not in value["supersession_reason"]:
        raise ContinualLiveError("supersession reason does not bind the 8192-token refreeze")
    return value, raw


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the engineering-only HSWM continual-learning pilot."
    )
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--streams", type=int, default=2)
    parser.add_argument("--seed-file", type=Path, required=True)
    parser.add_argument("--precommit-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--answer-max-tokens", type=int, default=128)
    parser.add_argument("--update-max-tokens", type=int, default=8192)
    parser.add_argument("--max-input-bytes", type=int, default=2_000_000)
    parser.add_argument("--max-state-bytes", type=int, default=1_000_000)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--removal-restore",
        action="store_true",
        help="run five unused sealed probes in active/remove/restart/restore order",
    )
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--container-digest", required=True)
    parser.add_argument("--service-binding", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _cli_parser().parse_args(argv)
    if args.streams != 2:
        raise ContinualLiveError("the frozen engineering pilot requires 2 streams")
    output = args.output_dir
    if output.exists() and any(output.iterdir()):
        raise ContinualLiveError("output directory must be absent or empty; no resume")
    output.mkdir(parents=True, exist_ok=True)
    precommit, precommit_raw = _read_pilot_precommit(args.precommit_file)
    _write_bytes_atomic(output / "frozen_precommit.canonical.json", precommit_raw)
    frozen_seeds = _read_secret_seeds(args.seed_file)
    commitments = tuple(precommit["commitment_document"]["commitments"])
    if len(frozen_seeds) != 4:
        raise ContinualLiveError("pilot requires exactly 4 frozen seed preimages")
    for index, (seed, commitment) in enumerate(zip(frozen_seeds, commitments, strict=True)):
        if _digest_bytes(seed) != commitment:
            raise ContinualLiveError(f"seed commitment mismatch at frozen index {index}")
    seed_indices = tuple(precommit["primary_seed_indices"])
    selected_seeds = tuple(frozen_seeds[index] for index in seed_indices)
    budget = ArmBudget(
        answer_max_output_tokens=args.answer_max_tokens,
        update_max_output_tokens=args.update_max_tokens,
        max_input_bytes=args.max_input_bytes,
        max_state_bytes=args.max_state_bytes,
    )
    backend_config = OpenAIBackendConfig(
        endpoint=args.endpoint,
        model=args.model,
        api_key=os.environ.get(args.api_key_env),
        timeout_seconds=args.timeout,
    )
    execution = precommit["primary_execution"]
    provider = precommit["intended_provider"]
    if (
        args.endpoint.rstrip("/") != str(provider["endpoint"]).rstrip("/")
        or args.model != provider["served_model"]
        or budget.answer_max_output_tokens != execution["answer_max_tokens"]
        or budget.update_max_output_tokens != execution["update_max_tokens"]
        or budget.max_input_bytes != execution["max_input_bytes"]
        or budget.max_state_bytes != execution["max_state_bytes"]
        or args.timeout != execution["per_call_timeout_seconds"]
        or args.removal_restore is not execution["removal_restore"]
    ):
        raise ContinualLiveError("CLI arguments conflict with the durable pilot precommit")
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_revision):
        raise ContinualLiveError("source_revision must be a 40-hex Git revision")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.container_digest):
        raise ContinualLiveError("container_digest must be sha256:<64 hex>")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.service_binding):
        raise ContinualLiveError("service_binding must be sha256:<64 hex>")
    prereg = {
        "backend": backend_config.public_identity(),
        "budget": budget.canonical(),
        "container_digest": args.container_digest,
        "engineering_only": True,
        "mode": "engineering-pilot-only",
        "protocol": LIVE_PROTOCOL,
        "removal_restore_requested": args.removal_restore,
        "ordered_seed_commitments": list(commitments),
        "precommit_artifact_sha256": _digest_bytes(precommit_raw),
        "precommit_sha256": precommit["precommit_sha256"],
        "selected_seed_indices": list(seed_indices),
        "service_binding": args.service_binding,
        "source_revision": args.source_revision,
        "stream_count": args.streams,
    }
    prereg["prereg_sha256"] = canonical_sha256(prereg)
    _write_json_atomic(output / "preregistration.json", prereg)

    status: dict[str, Any] = {
        "completed_streams": 0,
        "error": None,
        "status": "running",
    }
    manifests: list[StreamManifest] = []
    runs: list[StreamRun] = []
    audits: list[ParityAudit] = []
    removal_results: list[RemovalRestoreResult] = []
    ledgers: list[dict[str, Any]] = []
    sealed_packs: list[tuple[tuple[PublicProbe, str], ...]] = []
    try:
        for stream in range(args.streams):
            manifest = generate_stream(
                stream,
                seed_preimage=selected_seeds[stream],
            )
            manifests.append(manifest)
            sealed_packs.append(make_sealed_probe_pack(manifest))
        validation = validate_stream_set(manifests, expected_count=args.streams)
        _write_json_atomic(
            output / "sealed_manifest_commitments.json",
            {
                "manifest_sha256s": [item.manifest_sha256 for item in manifests],
                "sealed_probe_pack_sha256s": [
                    sealed_probe_pack_sha256(item) for item in sealed_packs
                ],
                "validation": validation.canonical(),
            },
        )
        for stream, manifest in enumerate(manifests):
            factory = lambda: OpenAICompatibleBackend(backend_config)
            run, audit, arms = run_four_arm_stream(
                manifest,
                backend_factory=factory,
                budget=budget,
                state_dir=output / "state" / f"stream-{stream:02d}",
                confirmatory=False,
            )
            runs.append(run)
            audits.append(audit)
            if audit.primary_call_counts != (41, 41, 41, 41):
                raise ContinualLiveError(
                    "primary call counts differ from the frozen 164-call budget"
                )
            if args.removal_restore:
                removal_results.append(
                    run_removal_restore_probes(
                        arms[0],
                        sealed_packs[stream],
                        primary_run=run,
                    )
                )
            ledgers.append(
                scoped_call_ledgers(
                    arms, audit, mediation_enabled=args.removal_restore
                )
            )
            status["completed_streams"] = stream + 1
            _write_json_atomic(output / "status.json", status)
        observed_calls = sum(
            len(entries)
            for stream_ledger in ledgers
            for scope in ("primary", "mediation")
            for entries in stream_ledger[scope].values()
        )
        if observed_calls != execution["endpoint_call_budget_total"]:
            raise ContinualLiveError("observed calls differ from frozen total budget")
        status["status"] = "success"
    except BaseException as error:
        status["status"] = "failed"
        status["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        # Seeds are revealed only after all model calling has stopped.  A failed
        # directory is retained and is never resumable.
        reveal = {
            "used_seeds": [
                {"frozen_index": index, "seed_hex": selected_seeds[stream].hex()}
                for stream, index in enumerate(seed_indices)
            ],
            "ordered_seed_commitments": list(commitments),
            "selected_seed_indices": list(seed_indices),
        }
        reveal["reveal_sha256"] = canonical_sha256(reveal)
        _write_json_atomic(output / "seed_reveal.json", reveal)
        post_reveal: dict[str, Any] = {
            "artifact_cardinality_match": False,
            "call_preimage_revalidation_match": False,
            "manifest_regeneration_match": False,
            "programmatic_regrade_match": False,
            "removal_mediation_revalidation_match": False,
            "sealed_probe_regeneration_match": False,
        }
        try:
            regenerated = tuple(
                generate_stream(stream, seed_preimage=selected_seeds[stream])
                for stream in range(args.streams)
            )
            validate_stream_set(regenerated, expected_count=args.streams)
            post_reveal["manifest_regeneration_match"] = (
                [item.manifest_sha256 for item in regenerated]
                == [item.manifest_sha256 for item in manifests]
            )
            regenerated_packs = tuple(make_sealed_probe_pack(item) for item in regenerated)
            post_reveal["sealed_probe_regeneration_match"] = (
                [sealed_probe_pack_sha256(item) for item in regenerated_packs]
                == [sealed_probe_pack_sha256(item) for item in sealed_packs]
            )
            cardinality_ok = (
                len(manifests)
                == len(runs)
                == len(audits)
                == len(ledgers)
                == args.streams
                and (
                    len(removal_results) == args.streams
                    if args.removal_restore
                    else not removal_results
                )
            )
            post_reveal["artifact_cardinality_match"] = cardinality_ok
            regrade_ok = cardinality_ok
            for manifest, run in zip(regenerated, runs, strict=cardinality_ok):
                queries = {query.step: query for query in manifest.queries}
                for result in run.results:
                    query = queries[result.step]
                    reparsed = parse_choice(
                        result.answer.response_text, choices=query.choices
                    )
                    if (
                        reparsed != result.chosen
                        or result.correct != (reparsed == query.answer)
                    ):
                        regrade_ok = False
                        break
            post_reveal["programmatic_regrade_match"] = regrade_ok
            removal_ok = cardinality_ok
            if args.removal_restore and cardinality_ok:
                for manifest, run, pack, result, stream_ledger in zip(
                    regenerated,
                    runs,
                    regenerated_packs,
                    removal_results,
                    ledgers,
                    strict=True,
                ):
                    value = result.canonical()
                    unsigned_result = dict(value)
                    result_sha = unsigned_result.pop("result_sha256")
                    h_results = [item for item in run.results if item.arm == "hswm"]
                    final_h = max(h_results, key=lambda item: item.step)
                    mediation_entries = stream_ledger["mediation"]["hswm"]
                    if (
                        canonical_sha256(unsigned_result) != result_sha
                        or result.stream_manifest_sha256 != manifest.manifest_sha256
                        or result.primary_run_sha256 != run.run_sha256
                        or result.primary_final_h_state_sha256
                        != final_h.post_update_state_sha256
                        or result.sealed_probe_pack_sha256
                        != sealed_probe_pack_sha256(pack)
                        or len(mediation_entries) != 15
                    ):
                        removal_ok = False
                        continue
                    grouped_choices: list[tuple[str | None, ...]] = []
                    grouped_correct: list[tuple[bool, ...]] = []
                    grouped_receipts: list[tuple[str, ...]] = []
                    for offset in (0, 5, 10):
                        choices: list[str | None] = []
                        correct: list[bool] = []
                        receipts: list[str] = []
                        for local, (probe, answer) in enumerate(pack):
                            entry = mediation_entries[offset + local]
                            choice = parse_choice(
                                entry["completion"]["text"], choices=probe.choices
                            )
                            choices.append(choice)
                            correct.append(choice == answer)
                            receipts.append(
                                canonical_sha256(
                                    {
                                        "arm": "hswm",
                                        "operation": "answer",
                                        **entry["completion"],
                                    }
                                )
                            )
                        grouped_choices.append(tuple(choices))
                        grouped_correct.append(tuple(correct))
                        grouped_receipts.append(tuple(receipts))
                    if (
                        tuple(grouped_choices)
                        != (
                            result.active_choices,
                            result.deleted_choices,
                            result.restored_choices,
                        )
                        or tuple(grouped_correct)
                        != (
                            result.active_correct,
                            result.deleted_correct,
                            result.restored_correct,
                        )
                        or tuple(grouped_receipts)
                        != (
                            result.active_answer_receipts,
                            result.deleted_answer_receipts,
                            result.restored_answer_receipts,
                        )
                        or tuple(sum(items) for items in grouped_correct)
                        != (
                            result.active_score,
                            result.deleted_score,
                            result.restored_score,
                        )
                    ):
                        removal_ok = False
            elif not args.removal_restore:
                removal_ok = not removal_results
            post_reveal["removal_mediation_revalidation_match"] = removal_ok
            preimages_ok = True
            for stream_ledger in ledgers:
                for scope in ("primary", "mediation"):
                    for entries in stream_ledger[scope].values():
                        for entry in entries:
                            completion = entry["completion"]
                            try:
                                raw_request_value = json.loads(
                                    completion["raw_request_json"]
                                )
                                raw_response_value = json.loads(
                                    completion["raw_response_json"]
                                )
                                backend_identity = json.loads(
                                    entry["backend_identity_json"]
                                )
                            except (KeyError, TypeError, json.JSONDecodeError):
                                preimages_ok = False
                                continue
                            if (
                                _digest_bytes(
                                    completion["raw_request_json"].encode("utf-8")
                                )
                                != completion["request_sha256"]
                                or _digest_bytes(
                                    completion["raw_response_json"].encode("utf-8")
                                )
                                != completion["response_sha256"]
                                or _digest_bytes(completion["text"].encode("utf-8"))
                                != completion["text_sha256"]
                            ):
                                preimages_ok = False
                                continue
                            try:
                                returned_text = raw_response_value["choices"][0][
                                    "message"
                                ]["content"]
                                returned_model = raw_response_value["model"]
                                usage = raw_response_value["usage"]
                            except (KeyError, IndexError, TypeError):
                                preimages_ok = False
                                continue
                            if (
                                set(raw_request_value)
                                != {
                                    "chat_template_kwargs",
                                    "max_tokens",
                                    "messages",
                                    "model",
                                    "seed",
                                    "temperature",
                                    "top_p",
                                }
                                or raw_request_value["messages"]
                                != [
                                    {
                                        "role": "system",
                                        "content": entry["system_message"],
                                    },
                                    {
                                        "role": "user",
                                        "content": entry["request_payload_json"],
                                    },
                                ]
                                or raw_request_value["max_tokens"]
                                != entry["max_output_tokens"]
                                or raw_request_value["temperature"] != 0.0
                                or raw_request_value["seed"]
                                != backend_identity.get("seed")
                                or raw_request_value["top_p"]
                                != backend_identity.get("top_p")
                                or raw_request_value["model"]
                                != backend_identity.get("model")
                                or raw_request_value["model"] != completion["model"]
                                or raw_request_value["chat_template_kwargs"]
                                != {
                                    "enable_thinking": backend_identity.get(
                                        "enable_thinking", False
                                    )
                                }
                                or returned_text != completion["text"]
                                or returned_model != completion["model"]
                                or usage.get("prompt_tokens")
                                != completion["input_tokens"]
                                or usage.get("completion_tokens")
                                != completion["output_tokens"]
                            ):
                                preimages_ok = False
            post_reveal["call_preimage_revalidation_match"] = preimages_ok
        except BaseException as validation_error:
            post_reveal["error"] = (
                f"{type(validation_error).__name__}: {validation_error}"
            )
        post_reveal["valid"] = all(
            post_reveal[key]
            for key in (
                "manifest_regeneration_match",
                "programmatic_regrade_match",
                "artifact_cardinality_match",
                "removal_mediation_revalidation_match",
                "sealed_probe_regeneration_match",
                "call_preimage_revalidation_match",
            )
        )
        post_reveal["validation_sha256"] = canonical_sha256(post_reveal)
        if status["status"] == "success" and not post_reveal["valid"]:
            status["status"] = "failed"
            status["error"] = "post-reveal regeneration or regrade failed"
        _write_json_atomic(output / "post_reveal_validation.json", post_reveal)
        _write_json_atomic(output / "status.json", status)
        if manifests:
            _write_json_atomic(
                output / "manifests.json",
                {"manifests": [item.canonical() for item in manifests]},
            )
        if runs:
            _write_json_atomic(
                output / "runs.json", {"runs": [item.canonical() for item in runs]}
            )
        if audits:
            _write_json_atomic(
                output / "parity_audits.json",
                {"audits": [item.canonical() for item in audits]},
            )
        if removal_results:
            _write_json_atomic(
                output / "removal_restore.json",
                {"results": [item.canonical() for item in removal_results]},
            )
        if ledgers:
            _write_json_atomic(output / "call_ledgers.json", {"streams": ledgers})
        artifact_hashes = {
            path.relative_to(output).as_posix(): _digest_bytes(path.read_bytes())
            for path in sorted(output.rglob("*"))
            if path.is_file()
            and path.name != "terminal_receipt.json"
            and not path.name.startswith(".tmp")
        }
        terminal = {
            "artifact_sha256s": artifact_hashes,
            "completed_streams": status["completed_streams"],
            "engineering_only": True,
            "error": status["error"],
            "removal_mediation_gate_passed": (
                all(item.removal_mediation_gate_passed for item in removal_results)
                if args.removal_restore and removal_results
                else None
            ),
            "protocol": LIVE_PROTOCOL,
            "status": status["status"],
        }
        terminal["receipt_sha256"] = canonical_sha256(terminal)
        _write_json_atomic(output / "terminal_receipt.json", terminal)
    return 0


__all__ = [
    "ArmBudget",
    "CallLedgerEntry",
    "CAPABILITY",
    "ChatBackend",
    "ContinualLiveError",
    "GENESIS",
    "LIVE_PROTOCOL",
    "ModelCompletion",
    "NoWriteArm",
    "OpenAIBackendConfig",
    "OpenAICompatibleBackend",
    "ParityAudit",
    "PlainTextArm",
    "RemovalRestoreResult",
    "ResetArm",
    "SnapshotCheckpoint",
    "StateTransitionReceipt",
    "StructuredHSWMArm",
    "audit_parity",
    "build_four_arms",
    "main",
    "make_sealed_probe_pack",
    "run_four_arm_stream",
    "run_removal_restore_probes",
    "sealed_probe_pack_sha256",
]


if __name__ == "__main__":
    raise SystemExit(main())
