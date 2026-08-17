"""Audited live arms for the nonce-graph continual-learning benchmark.

This module is intentionally narrower than a general agent framework.  It
binds four stateless-chat conditions to :func:`continual.run_prequential`:

``hswm``
    The adapter materializes fixed public-token content and provenance while
    the model authors memory relations, cells, and routing edges in an
    empty-genesis :class:`SQLiteSelfModelStore`.  The committed HSWM structure
    is itself the persistent execution substrate.
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
import gc
from hashlib import sha256
import itertools
import json
import os
from pathlib import Path
import re
import sqlite3
import socket
import stat
import tarfile
import tempfile
import time
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib import error as urlerror
from urllib import request as urlrequest

from hswm.selfmod.contracts import (
    CellRecord,
    CellTopologyMode,
    MemoryRecord,
    MutationProposal,
    SelfModelPolicy,
    SelfModelSnapshot,
    apply_mutation,
    canonical_json_bytes,
    make_mutation,
    make_snapshot,
    make_token,
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
COMPACT_PATCH_SCHEMA = "hswm-compact-structure-patch/v3"
INDEXED_AUTHORING_VIEW_SCHEMA = "hswm-indexed-authoring-view/v1"
MUTATION_EXPRESSIVITY = "compact-adapter-subset"
PUBLIC_SCHEMA_GATE_FIXTURE_DOMAIN = "hswm-public-schema-gate/v3"
PUBLIC_SCHEMA_GATE_PROTOCOL = "hswm-public-schema-gate/v4"
PUBLIC_SCHEMA_GATE_EPISODE = "public-schema-gate-never-evaluation"
PUBLIC_SCHEMA_GATE_CONTEXT_WINDOW_TOKENS = 32_768
PUBLIC_SCHEMA_GATE_OUTPUT_TOKEN_CEILING = 6144
PUBLIC_SCHEMA_GATE_MAX_UPDATE_INPUT_TOKENS = (
    PUBLIC_SCHEMA_GATE_CONTEXT_WINDOW_TOKENS
    - PUBLIC_SCHEMA_GATE_OUTPUT_TOKEN_CEILING
)
STRUCTURED_OUTPUT_MODE = "openai-response-format-json-schema/v1"
MAX_AUTHORED_CELLS = 16
MAX_CELL_MEMORY_REFERENCES = 64
MAX_CELL_EDGES = 8
MAX_RELATED_MEMORY_IDS = 8
MAX_CELL_ID_CHARS = 64
MAX_CELL_INSTRUCTION_CHARS = 256
MAX_RATIONALE_CHARS = 512
MAX_PLAIN_MEMORY_CHARS = 16_384
MAX_RESPONSE_SCHEMA_BYTES = 131_072
MAX_RAW_REQUEST_BYTES = 2_000_000
MAX_COMPLETION_TEXT_BYTES = 1_000_000
GENESIS = make_snapshot()
FROZEN_PILOT_PRECOMMIT_ARTIFACT_SHA256 = (
    "e5f98257a199e70f4e648344f89bd3b59edd6661cbc6dd717b86aaf74fff4324"
)
FROZEN_PILOT_PRECOMMIT_SHA256 = (
    "a7b9a157b12246568663bb34c466d7cf806e8fb899fd99ae3a6d83d67c7f608d"
)
FROZEN_RECOVERY_PRECOMMIT_ARTIFACT_SHA256 = (
    "5cbcac7399d48ad3436fb382781572e5daefbf1cb0b55473cf33af7171eafc86"
)
FROZEN_RECOVERY_PRECOMMIT_SHA256 = (
    "4aeb7d82a6624e2e47496b5ea66354e95d8cf81e7c501e6961c70070938e8c1e"
)
FAILED_SERVICE_BEFORE_ARTIFACT_SHA256 = (
    "6ebb35cc8b8cd8f04c1a9541fa708131cfd95890ed6b93e25f4cb0c6d0e6d90f"
)
FAILED_SERVICE_AFTER_ARTIFACT_SHA256 = (
    "24e6f31de6a42dfd82ecccc19e68dbe52ea5cf9d80185bf351349138ee7724ab"
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
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=".tmp-", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _write_bytes_atomic(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=".tmp-", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _checkpoint_sqlite_artifacts(root: Path) -> tuple[str, ...]:
    """Seal every runner-owned SQLite database into one persistent main file."""

    root = Path(root)
    # sqlite3 context managers commit/rollback but do not close their connection.
    # The store uses short-lived per-operation connections, so collect any finished
    # connection cycles before requiring an exclusive WAL-mode transition.
    gc.collect()
    finalized: list[str] = []
    for path in sorted(root.rglob("*.sqlite3")):
        if not path.is_file() or path.is_symlink():
            raise ContinualLiveError("SQLite artifact path is not a regular file")
        connection = sqlite3.connect(path, timeout=10.0, isolation_level=None)
        try:
            connection.execute("PRAGMA busy_timeout=10000")
            journal_mode = str(
                connection.execute("PRAGMA journal_mode").fetchone()[0]
            ).lower()
            if journal_mode == "wal":
                checkpoint = connection.execute(
                    "PRAGMA wal_checkpoint(TRUNCATE)"
                ).fetchone()
                if checkpoint is None or int(checkpoint[0]) != 0:
                    raise ContinualLiveError(
                        "SQLite WAL checkpoint was busy before artifact hashing"
                    )
                journal_mode = str(
                    connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
                ).lower()
            if journal_mode != "delete":
                raise ContinualLiveError(
                    "SQLite artifact did not enter sealed DELETE journal mode"
                )
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise ContinualLiveError("SQLite artifact failed quick_check")
        finally:
            connection.close()
        finalized.append(path.relative_to(root).as_posix())
    gc.collect()
    dangling = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name.endswith(("-wal", "-shm", "-journal"))
    )
    if dangling:
        raise ContinualLiveError(
            "SQLite sidecar remains after final checkpoint: " + ", ".join(dangling)
        )
    return tuple(finalized)


def _final_artifact_sha256s(root: Path) -> dict[str, str]:
    """Hash the exact persistent regular-file tree except its terminal receipt."""

    root = Path(root)
    terminal = root / "terminal_receipt.json"
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ContinualLiveError("artifact tree cannot contain symbolic links")
        if not path.is_file():
            continue
        if path == terminal:
            continue
        if path.name.startswith(".tmp-"):
            raise ContinualLiveError("artifact tree contains an unfinished atomic write")
        if path.name.endswith(("-wal", "-shm", "-journal")):
            raise ContinualLiveError("artifact tree contains an unsealed SQLite sidecar")
        result[path.relative_to(root).as_posix()] = _digest_bytes(path.read_bytes())
    return result


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
        if len(self.text.encode("utf-8")) > MAX_COMPLETION_TEXT_BYTES:
            raise ContinualLiveError("model completion text exceeds its hard byte bound")
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
                    choices = parsed["choices"]
                    if not isinstance(choices, list) or len(choices) != 1:
                        raise TypeError("response must contain exactly one choice")
                    message = choices[0]["message"]
                    if not isinstance(message, Mapping):
                        raise TypeError("response message is not an object")
                    returned_text = message["content"]
                    returned_model = parsed["model"]
                except (KeyError, IndexError, TypeError) as error:
                    raise ContinualLiveError(
                        "raw response lacks the OpenAI completion envelope"
                    ) from error
                if (
                    message.get("reasoning_content") not in (None, "")
                    or message.get("reasoning") not in (None, "")
                    or message.get("refusal") not in (None, "")
                    or message.get("tool_calls") not in (None, [])
                    or message.get("function_call") is not None
                ):
                    raise ContinualLiveError(
                        "raw response used a non-content side channel"
                    )
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
            "text_bytes": len(self.text.encode("utf-8")),
            "text_sha256": _digest_bytes(self.text.encode("utf-8")),
            "usage_reported": self.usage_reported,
        }


_SUPPORTED_JSON_SCHEMA_KEYS = frozenset(
    {
        "additionalProperties",
        "const",
        "enum",
        "items",
        "maxItems",
        "maximum",
        "maxLength",
        "minItems",
        "minimum",
        "minLength",
        "properties",
        "required",
        "type",
    }
)


def _validate_bounded_json_schema(node: object, *, path: str = "$") -> None:
    if not isinstance(node, Mapping):
        raise ContinualLiveError(f"response schema node {path} must be an object")
    unsupported = set(node) - _SUPPORTED_JSON_SCHEMA_KEYS
    if unsupported:
        raise ContinualLiveError(
            f"response schema uses unsupported keywords at {path}: {sorted(unsupported)}"
        )
    node_type = node.get("type")
    if node_type not in {"array", "integer", "null", "object", "string"}:
        raise ContinualLiveError(f"response schema type at {path} is unsupported")
    if "enum" in node:
        enum = node["enum"]
        if not isinstance(enum, list) or not enum:
            raise ContinualLiveError(f"response schema enum at {path} is invalid")
        encoded = [canonical_json_bytes(item) for item in enum]
        if len(encoded) != len(set(encoded)):
            raise ContinualLiveError(f"response schema enum at {path} is duplicated")
    if node_type == "object":
        properties = node.get("properties")
        required = node.get("required")
        if (
            not isinstance(properties, Mapping)
            or not properties
            or node.get("additionalProperties") is not False
            or not isinstance(required, list)
            or any(not isinstance(item, str) for item in required)
            or set(required) != set(properties)
            or len(required) != len(set(required))
        ):
            raise ContinualLiveError(
                f"response schema object at {path} is not exact and fully required"
            )
        for name, child in properties.items():
            if not isinstance(name, str) or not name:
                raise ContinualLiveError(f"response schema property at {path} is invalid")
            _validate_bounded_json_schema(child, path=f"{path}.properties.{name}")
    elif node_type == "array":
        maximum = node.get("maxItems")
        minimum = node.get("minItems", 0)
        if (
            isinstance(maximum, bool)
            or not isinstance(maximum, int)
            or isinstance(minimum, bool)
            or not isinstance(minimum, int)
            or minimum < 0
            or maximum < minimum
            or "items" not in node
        ):
            raise ContinualLiveError(f"response schema array at {path} is unbounded")
        _validate_bounded_json_schema(node["items"], path=f"{path}.items")
    elif node_type == "string" and "enum" not in node and "const" not in node:
        maximum = node.get("maxLength")
        minimum = node.get("minLength", 0)
        if (
            isinstance(maximum, bool)
            or not isinstance(maximum, int)
            or isinstance(minimum, bool)
            or not isinstance(minimum, int)
            or minimum < 0
            or maximum < minimum
        ):
            raise ContinualLiveError(f"response schema string at {path} is unbounded")
    elif node_type == "integer":
        minimum = node.get("minimum")
        maximum = node.get("maximum")
        if (
            isinstance(minimum, bool)
            or not isinstance(minimum, int)
            or isinstance(maximum, bool)
            or not isinstance(maximum, int)
            or maximum < minimum
        ):
            raise ContinualLiveError(f"response schema integer at {path} is unbounded")


def _validate_json_schema_instance(
    value: object, schema: Mapping[str, Any], *, path: str = "$"
) -> None:
    if "const" in schema and value != schema["const"]:
        raise ContinualLiveError(f"model response violates schema const at {path}")
    if "enum" in schema and value not in schema["enum"]:
        raise ContinualLiveError(f"model response violates schema enum at {path}")
    node_type = schema["type"]
    if node_type == "object":
        if not isinstance(value, dict) or set(value) != set(schema["required"]):
            raise ContinualLiveError(f"model response violates object schema at {path}")
        for name, child in schema["properties"].items():
            _validate_json_schema_instance(value[name], child, path=f"{path}.{name}")
    elif node_type == "array":
        if not isinstance(value, list) or not (
            schema.get("minItems", 0) <= len(value) <= schema["maxItems"]
        ):
            raise ContinualLiveError(f"model response violates array bound at {path}")
        for index, item in enumerate(value):
            _validate_json_schema_instance(
                item, schema["items"], path=f"{path}[{index}]"
            )
    elif node_type == "string":
        if not isinstance(value, str) or not (
            schema.get("minLength", 0)
            <= len(value)
            <= schema.get("maxLength", len(value))
        ):
            raise ContinualLiveError(f"model response violates string bound at {path}")
    elif node_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int) or not (
            schema["minimum"] <= value <= schema["maximum"]
        ):
            raise ContinualLiveError(f"model response violates integer bound at {path}")
    elif node_type == "null" and value is not None:
        raise ContinualLiveError(f"model response violates null schema at {path}")


@dataclass(frozen=True, slots=True)
class JSONSchemaContract:
    """Canonical OpenAI ``response_format`` JSON Schema identity."""

    name: str
    schema_json: str
    schema_sha256: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.name):
            raise ContinualLiveError("response schema name is invalid")
        try:
            schema = json.loads(self.schema_json)
        except json.JSONDecodeError as error:
            raise ContinualLiveError("response schema preimage is not JSON") from error
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ContinualLiveError("response schema must describe one JSON object")
        canonical = canonical_json_bytes(schema)
        if len(canonical) > MAX_RESPONSE_SCHEMA_BYTES:
            raise ContinualLiveError("response schema exceeds its byte bound")
        if canonical.decode("utf-8") != self.schema_json:
            raise ContinualLiveError("response schema preimage is not canonical")
        if _digest_bytes(canonical) != self.schema_sha256:
            raise ContinualLiveError("response schema digest mismatch")
        _validate_bounded_json_schema(schema)

    @classmethod
    def make(cls, name: str, schema: Mapping[str, Any]) -> "JSONSchemaContract":
        raw = canonical_json_bytes(schema)
        return cls(
            name=name,
            schema_json=raw.decode("utf-8"),
            schema_sha256=_digest_bytes(raw),
        )

    def schema(self) -> dict[str, Any]:
        value = json.loads(self.schema_json)
        if not isinstance(value, dict):  # guarded by __post_init__
            raise AssertionError("validated schema changed type")
        return value

    def response_format(self) -> dict[str, Any]:
        return {
            "json_schema": {
                "name": self.name,
                "schema": self.schema(),
                "strict": True,
            },
            "type": "json_schema",
        }

    def validate_instance(self, value: object) -> None:
        _validate_json_schema_instance(value, self.schema())

    def canonical(self) -> dict[str, str]:
        return {
            "name": self.name,
            "schema_json": self.schema_json,
            "schema_sha256": self.schema_sha256,
        }


def _prepare_chat_request(
    *,
    backend_identity: Mapping[str, Any],
    messages: Sequence[Mapping[str, str]],
    max_output_tokens: int,
    response_schema: JSONSchemaContract,
) -> bytes:
    if max_output_tokens <= 0:
        raise ContinualLiveError("max_output_tokens must be positive")
    if backend_identity.get("response_format_mode") != STRUCTURED_OUTPUT_MODE:
        raise ContinualLiveError("backend does not bind strict JSON Schema requests")
    if backend_identity.get("enable_thinking") is not False:
        raise ContinualLiveError("backend must explicitly disable thinking")
    normalized = [
        {"role": str(item["role"]), "content": str(item["content"])}
        for item in messages
    ]
    if not normalized or any(
        item["role"] not in {"system", "user", "assistant"}
        for item in normalized
    ):
        raise ContinualLiveError("invalid chat messages")
    model = backend_identity.get("model")
    if not isinstance(model, str) or not model:
        raise ContinualLiveError("backend identity lacks a model")
    request_value = {
        "chat_template_kwargs": {
            "enable_thinking": False
        },
        "max_tokens": max_output_tokens,
        "messages": normalized,
        "model": model,
        "response_format": response_schema.response_format(),
        "seed": backend_identity.get("seed"),
        "temperature": 0.0,
        "top_p": backend_identity.get("top_p"),
    }
    raw = canonical_json_bytes(request_value)
    if len(raw) > MAX_RAW_REQUEST_BYTES:
        raise ContinualLiveError("prepared chat request exceeds its hard byte bound")
    return raw


class ChatBackend(Protocol):
    """One stateless chat call; implementations must not retry."""

    @property
    def identity(self) -> Mapping[str, Any]: ...

    def complete(
        self,
        *,
        raw_request: bytes,
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
        if self.enable_thinking is not False:
            raise ValueError("the frozen benchmark requires enable_thinking=false")
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
            "response_format_mode": STRUCTURED_OUTPUT_MODE,
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
        raw_request: bytes,
        request_id: str,
        response_observer: Callable[[bytes, bytes], None],
    ) -> ModelCompletion:
        if len(raw_request) > MAX_RAW_REQUEST_BYTES:
            raise ContinualLiveError("prepared chat request exceeds its hard byte bound")
        try:
            request_value = json.loads(raw_request)
            response_format = request_value["response_format"]
            json_schema = response_format["json_schema"]
            contract = JSONSchemaContract.make(
                json_schema["name"], json_schema["schema"]
            )
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise ContinualLiveError("prepared chat request is invalid") from error
        if (
            canonical_json_bytes(request_value) != raw_request
            or set(request_value)
            != {
                "chat_template_kwargs",
                "max_tokens",
                "messages",
                "model",
                "response_format",
                "seed",
                "temperature",
                "top_p",
            }
            or response_format != contract.response_format()
            or request_value["model"] != self.config.model
            or request_value["seed"] != self.config.seed
            or request_value["temperature"] != 0.0
            or request_value["top_p"] != self.config.top_p
            or request_value["chat_template_kwargs"]
            != {"enable_thinking": self.config.enable_thinking}
            or isinstance(request_value["max_tokens"], bool)
            or not isinstance(request_value["max_tokens"], int)
            or request_value["max_tokens"] <= 0
        ):
            raise ContinualLiveError("prepared chat request differs from backend config")
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


def _strict_json_object(properties: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "additionalProperties": False,
        "properties": dict(properties),
        "required": list(properties),
        "type": "object",
    }


def _string_schema(*, max_length: int, min_length: int = 1) -> dict[str, Any]:
    return {
        "maxLength": max_length,
        "minLength": min_length,
        "type": "string",
    }


def _index_item_schema(count: int) -> dict[str, Any]:
    if count <= 0:
        raise ContinualLiveError("response schema requires a non-empty public batch")
    return {"maximum": count - 1, "minimum": 0, "type": "integer"}


def _compact_patch_response_schema(
    active: SelfModelSnapshot,
    source_tokens: Sequence[Mapping[str, Any]],
    policy: SelfModelPolicy,
) -> JSONSchemaContract:
    source_count = len(source_tokens)
    if source_count <= 0:
        raise ContinualLiveError("compact response schema requires public tokens")
    active_count = len(active.memories)
    new_index_items = _index_item_schema(source_count)
    cell_index_items = {
        "maximum": min(policy.max_cells, MAX_AUTHORED_CELLS) - 1,
        "minimum": 0,
        "type": "integer",
    }
    existing_relation_index_items = (
        _index_item_schema(active_count)
        if active_count
        else {"maximum": 0, "minimum": 0, "type": "integer"}
    )
    cell_edge_array = {
        "items": cell_index_items,
        "maxItems": MAX_CELL_EDGES,
        "type": "array",
    }
    cell = _strict_json_object(
        {
            "capability": {"const": CAPABILITY, "type": "string"},
            "cell_id": _string_schema(max_length=MAX_CELL_ID_CHARS),
            "executor_agent_id": {"type": "null"},
            "instruction": _string_schema(
                max_length=MAX_CELL_INSTRUCTION_CHARS
            ),
            "next_cell_indices": cell_edge_array,
        }
    )
    memory_relation = _strict_json_object(
        {
            "related_existing_memory_indices": {
                "items": existing_relation_index_items,
                "maxItems": min(active_count, MAX_RELATED_MEMORY_IDS),
                "type": "array",
            },
            "related_other_new_token_indices": {
                "items": new_index_items,
                "maxItems": min(max(source_count - 1, 0), MAX_RELATED_MEMORY_IDS),
                "type": "array",
            },
        }
    )
    schema = _strict_json_object(
        {
            "cells": {
                "items": cell,
                "maxItems": min(policy.max_cells, MAX_AUTHORED_CELLS),
                "minItems": 1,
                "type": "array",
            },
            "entry_cell_index": cell_index_items,
            "existing_memory_cell_indices": {
                "items": {
                    "maximum": cell_index_items["maximum"],
                    "minimum": -1,
                    "type": "integer",
                },
                "maxItems": active_count,
                "minItems": active_count,
                "type": "array",
            },
            "new_memory_cell_indices": {
                "items": cell_index_items,
                "maxItems": source_count,
                "minItems": source_count,
                "type": "array",
            },
            "new_memory_relations": {
                "items": memory_relation,
                "maxItems": source_count,
                "minItems": source_count,
                "type": "array",
            },
            "rationale": _string_schema(max_length=MAX_RATIONALE_CHARS),
        }
    )
    return JSONSchemaContract.make("hswm_compact_patch_v3", schema)


def _plain_memory_response_schema() -> JSONSchemaContract:
    return JSONSchemaContract.make(
        "hswm_plain_memory_v1",
        _strict_json_object(
            {
                "memory": _string_schema(
                    max_length=MAX_PLAIN_MEMORY_CHARS,
                    min_length=0,
                )
            }
        ),
    )


def _choice_response_schema(choices: Sequence[str]) -> JSONSchemaContract:
    frozen = tuple(choices)
    if not frozen or len(frozen) != len(set(frozen)) or any(
        not isinstance(item, str) or not item for item in frozen
    ):
        raise ContinualLiveError("choice response schema requires unique choices")
    return JSONSchemaContract.make(
        "hswm_choice_v1",
        _strict_json_object(
            {"choice": {"enum": list(frozen), "type": "string"}}
        ),
    )


@dataclass(frozen=True, slots=True)
class CallLedgerEntry:
    arm: str
    completion_text_bytes: int
    operation: str
    ordinal: int
    max_output_tokens: int
    messages_bytes: int
    backend_identity_json: str
    raw_request_bytes: int
    request_payload_json: str
    request_payload_bytes: int
    request_payload_sha256: str
    response_schema_bytes: int
    response_schema_json: str
    response_schema_name: str
    response_schema_sha256: str
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
        expected_messages = canonical_json_bytes(
            [
                {"role": "system", "content": self.system_message},
                {"role": "user", "content": self.request_payload_json},
            ]
        )
        if (
            self.request_payload_bytes != len(canonical)
            or self.messages_bytes != len(expected_messages)
            or self.response_schema_bytes
            != len(self.response_schema_json.encode("utf-8"))
            or self.raw_request_bytes
            != len(self.completion.raw_request_json.encode("utf-8"))
            or self.completion_text_bytes
            != len(self.completion.text.encode("utf-8"))
        ):
            raise ContinualLiveError("ledger byte counts differ from their preimages")
        if not self.system_message:
            raise ContinualLiveError("ledger system message is empty")
        if not self.completion.usage_reported:
            raise ContinualLiveError("live model call requires provider token usage")
        if self.completion.output_tokens > self.max_output_tokens:
            raise ContinualLiveError("provider output usage exceeds the request budget")
        if canonical_json_bytes(backend_identity).decode("utf-8") != self.backend_identity_json:
            raise ContinualLiveError("ledger backend identity is not canonical")
        response_schema = JSONSchemaContract(
            name=self.response_schema_name,
            schema_json=self.response_schema_json,
            schema_sha256=self.response_schema_sha256,
        )
        expected_request_fields = {
            "chat_template_kwargs",
            "max_tokens",
            "messages",
            "model",
            "response_format",
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
            or raw_request["response_format"] != response_schema.response_format()
            or backend_identity.get("response_format_mode")
            != STRUCTURED_OUTPUT_MODE
            or raw_request["chat_template_kwargs"]
            != {"enable_thinking": backend_identity.get("enable_thinking", False)}
        ):
            raise ContinualLiveError("raw request parameters differ from frozen config")

    def canonical(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "backend_identity_json": self.backend_identity_json,
            "completion": self.completion.canonical(),
            "completion_text_bytes": self.completion_text_bytes,
            "max_output_tokens": self.max_output_tokens,
            "messages_bytes": self.messages_bytes,
            "operation": self.operation,
            "ordinal": self.ordinal,
            "raw_request_bytes": self.raw_request_bytes,
            "request_payload_json": self.request_payload_json,
            "request_payload_bytes": self.request_payload_bytes,
            "request_payload_sha256": self.request_payload_sha256,
            "response_schema_bytes": self.response_schema_bytes,
            "response_schema_json": self.response_schema_json,
            "response_schema_name": self.response_schema_name,
            "response_schema_sha256": self.response_schema_sha256,
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
        completion_validator: Callable[[CallLedgerEntry], object] | None = None,
    ) -> None:
        if not name or not isolation_id:
            raise ValueError("arm name and isolation id are required")
        self.name = name
        self.backend = backend
        self.budget = budget
        self.isolation_id = isolation_id
        self.journal_path = Path(journal_path)
        self.completion_validator = completion_validator
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
            "indexed_authoring_view_schema": INDEXED_AUTHORING_VIEW_SCHEMA,
            "mutation_expressivity": MUTATION_EXPRESSIVITY,
            "proposal_policy": policy.canonical(),
            "proposal_policy_sha256": policy.policy_sha256,
            "protocol": LIVE_PROTOCOL,
            "structured_output_mode": STRUCTURED_OUTPUT_MODE,
        }

    def _call(
        self,
        *,
        operation: str,
        system: str,
        payload: Mapping[str, Any],
        max_output_tokens: int,
        response_schema: JSONSchemaContract,
    ) -> ModelCompletion:
        payload_raw = canonical_json_bytes(payload)
        messages = (
            {"role": "system", "content": system},
            {"role": "user", "content": payload_raw.decode("utf-8")},
        )
        messages_raw = canonical_json_bytes(messages)
        backend_identity = dict(self.backend.identity)
        raw_request = _prepare_chat_request(
            backend_identity=backend_identity,
            messages=messages,
            max_output_tokens=max_output_tokens,
            response_schema=response_schema,
        )
        if len(raw_request) > self.budget.max_input_bytes:
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
                "raw_request_sha256": _digest_bytes(raw_request),
                "response_schema_sha256": response_schema.schema_sha256,
            }
        )[:32]
        intent = {
            "arm": self.name,
            "backend": backend_identity,
            "event": "intent",
            "isolation_id": self.isolation_id,
            "max_output_tokens": max_output_tokens,
            "messages_bytes": len(messages_raw),
            "operation": operation,
            "ordinal": ordinal,
            "raw_request_bytes": len(raw_request),
            "raw_request_json": raw_request.decode("utf-8"),
            "raw_request_sha256": _digest_bytes(raw_request),
            "request_id": request_id,
            "request_payload_bytes": len(payload_raw),
            "request_payload_json": payload_raw.decode("utf-8"),
            "request_payload_sha256": _digest_bytes(payload_raw),
            "response_schema_bytes": len(response_schema.schema_json.encode("utf-8")),
            "response_schema_json": response_schema.schema_json,
            "response_schema_name": response_schema.name,
            "response_schema_sha256": response_schema.schema_sha256,
            "system_message": system,
        }
        self._journal(intent)
        response_was_received = False
        observer_calls = 0
        observed_response: bytes | None = None
        try:
            def observe_response(observed_request: bytes, raw_response: bytes) -> None:
                nonlocal observer_calls, observed_response, response_was_received
                observer_calls += 1
                observed_response = raw_response
                prepared_request_match = observed_request == raw_request
                self._journal(
                    {
                        "arm": self.name,
                        "event": "raw_response_received",
                        "operation": operation,
                        "ordinal": ordinal,
                        "prepared_request_match": prepared_request_match,
                        "raw_request_base64": base64.b64encode(observed_request).decode("ascii"),
                        "raw_request_sha256": _digest_bytes(observed_request),
                        "raw_response_base64": base64.b64encode(raw_response).decode("ascii"),
                        "raw_response_sha256": _digest_bytes(raw_response),
                        "request_id": request_id,
                        "response_schema_sha256": response_schema.schema_sha256,
                        "response_bytes": len(raw_response),
                    }
                )
                response_was_received = True
                if not prepared_request_match:
                    raise ContinualLiveError(
                        "backend observed request differs from prepared preimage"
                    )

            completion = self.backend.complete(
                raw_request=raw_request,
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
                    "response_schema_sha256": response_schema.schema_sha256,
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
                "response_schema_sha256": response_schema.schema_sha256,
            }
        )
        try:
            if observer_calls != 1:
                raise ContinualLiveError(
                    "backend must report exactly one raw response observation"
                )
            if observed_response != completion.raw_response_json.encode("utf-8"):
                raise ContinualLiveError(
                    "observed raw response differs from returned completion"
                )
            ledger_entry = CallLedgerEntry(
                arm=self.name,
                completion_text_bytes=len(completion.text.encode("utf-8")),
                operation=operation,
                ordinal=ordinal,
                max_output_tokens=max_output_tokens,
                messages_bytes=len(messages_raw),
                backend_identity_json=canonical_json_bytes(backend_identity).decode(
                    "utf-8"
                ),
                raw_request_bytes=len(raw_request),
                request_payload_json=payload_raw.decode("utf-8"),
                request_payload_bytes=len(payload_raw),
                request_payload_sha256=_digest_bytes(payload_raw),
                response_schema_bytes=len(response_schema.schema_json.encode("utf-8")),
                response_schema_json=response_schema.schema_json,
                response_schema_name=response_schema.name,
                response_schema_sha256=response_schema.schema_sha256,
                system_message=system,
                completion=completion,
            )
            response_schema.validate_instance(_strict_object(completion.text))
            if self.completion_validator is not None:
                # Gate-specific acceptance happens before an update response can
                # be parsed, committed, or followed by another provider call.
                self.completion_validator(ledger_entry)
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
                    "response_schema_sha256": response_schema.schema_sha256,
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
                "response_schema_sha256": response_schema.schema_sha256,
            }
        )
        return completion

    def _answer(
        self, probe: PublicProbe, *, state_kind: str, state: Any
    ) -> ArmAnswer:
        response_schema = _choice_response_schema(probe.choices)
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
            response_schema=response_schema,
        )
        response_schema.validate_instance(_strict_object(completion.text))
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


def _projection_indices(
    value: object,
    *,
    label: str,
    upper_bound: int,
) -> tuple[int, ...]:
    """Validate index references without sorting, deduplicating, or repairing."""

    if not isinstance(value, list):
        raise ContinualLiveError(f"{label} must be an index array")
    result = tuple(value)
    if any(
        isinstance(item, bool)
        or not isinstance(item, int)
        or item < 0
        or item >= upper_bound
        for item in result
    ):
        raise ContinualLiveError(f"{label} contains a bool, negative, or unknown index")
    return result


def _expand_indexed_authoring_projection(
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    """Expand the lossless indexed view without invoking sorting constructors."""

    fields = {
        "active_generation",
        "cells",
        "entry_cell_index",
        "memories",
        "projection_sha256",
        "schema",
        "schema_version",
        "snapshot_id",
        "source_snapshot_sha256",
    }
    if not isinstance(projection, Mapping) or set(projection) != fields:
        raise ContinualLiveError("indexed authoring projection field set is invalid")
    body = {
        key: value for key, value in projection.items() if key != "projection_sha256"
    }
    if (
        projection["schema"] != INDEXED_AUTHORING_VIEW_SCHEMA
        or not isinstance(projection["active_generation"], int)
        or isinstance(projection["active_generation"], bool)
        or projection["active_generation"] < 0
        or not isinstance(projection["snapshot_id"], str)
        or not isinstance(projection["schema_version"], str)
        or not isinstance(projection["source_snapshot_sha256"], str)
        or not isinstance(projection["projection_sha256"], str)
        or projection["projection_sha256"] != canonical_sha256(body)
    ):
        raise ContinualLiveError("indexed authoring projection identity is invalid")
    memories = projection["memories"]
    cells = projection["cells"]
    if not isinstance(memories, list) or not isinstance(cells, list):
        raise ContinualLiveError("indexed authoring projection arrays are invalid")

    memory_fields = {
        "content",
        "kind",
        "labels",
        "memory_id",
        "related_memory_indices",
        "source_token_ids",
    }
    memory_ids: list[str] = []
    for item in memories:
        if not isinstance(item, Mapping) or set(item) != memory_fields:
            raise ContinualLiveError("indexed projection memory field set is invalid")
        if (
            not isinstance(item["memory_id"], str)
            or not isinstance(item["kind"], str)
            or not isinstance(item["source_token_ids"], list)
            or not isinstance(item["labels"], list)
        ):
            raise ContinualLiveError("indexed projection memory metadata is invalid")
        memory_ids.append(item["memory_id"])
    if len(memory_ids) != len(set(memory_ids)):
        raise ContinualLiveError("indexed projection memory ids are not unique")

    cell_fields = {
        "capability",
        "cell_id",
        "executor_agent_id",
        "instruction",
        "memory_indices",
        "next_cell_indices",
    }
    cell_ids: list[str] = []
    for item in cells:
        if not isinstance(item, Mapping) or set(item) != cell_fields:
            raise ContinualLiveError("indexed projection cell field set is invalid")
        if (
            not isinstance(item["cell_id"], str)
            or not isinstance(item["capability"], str)
            or not isinstance(item["instruction"], str)
            or item["executor_agent_id"] is not None
            and not isinstance(item["executor_agent_id"], str)
        ):
            raise ContinualLiveError("indexed projection cell metadata is invalid")
        cell_ids.append(item["cell_id"])
    if len(cell_ids) != len(set(cell_ids)):
        raise ContinualLiveError("indexed projection cell ids are not unique")

    expanded_memories = []
    for index, item in enumerate(memories):
        related_indices = _projection_indices(
            item["related_memory_indices"],
            label=f"projection memories[{index}].related_memory_indices",
            upper_bound=len(memory_ids),
        )
        expanded_memories.append(
            {
                "content": item["content"],
                "kind": item["kind"],
                "labels": list(item["labels"]),
                "memory_id": item["memory_id"],
                "related_memory_ids": [memory_ids[item] for item in related_indices],
                "source_token_ids": list(item["source_token_ids"]),
            }
        )
    expanded_cells = []
    for index, item in enumerate(cells):
        memory_indices = _projection_indices(
            item["memory_indices"],
            label=f"projection cells[{index}].memory_indices",
            upper_bound=len(memory_ids),
        )
        next_cell_indices = _projection_indices(
            item["next_cell_indices"],
            label=f"projection cells[{index}].next_cell_indices",
            upper_bound=len(cell_ids),
        )
        expanded_cells.append(
            {
                "capability": item["capability"],
                "cell_id": item["cell_id"],
                "executor_agent_id": item["executor_agent_id"],
                "instruction": item["instruction"],
                "memory_ids": [memory_ids[item] for item in memory_indices],
                "next_cell_ids": [cell_ids[item] for item in next_cell_indices],
            }
        )
    entry = projection["entry_cell_index"]
    if cell_ids:
        entry_indices = _projection_indices(
            [entry],
            label="projection entry_cell_index",
            upper_bound=len(cell_ids),
        )
        entry_cell_id: str | None = cell_ids[entry_indices[0]]
    elif entry is None:
        entry_cell_id = None
    else:
        raise ContinualLiveError("empty projection must have a null entry cell")
    expanded = {
        "cells": expanded_cells,
        "entry_cell_id": entry_cell_id,
        "memories": expanded_memories,
        "schema_version": projection["schema_version"],
        "snapshot_id": projection["snapshot_id"],
    }
    if _digest_bytes(canonical_json_bytes(expanded)) != projection[
        "source_snapshot_sha256"
    ]:
        raise ContinualLiveError(
            "indexed projection source snapshot digest does not match expansion"
        )
    return expanded


def _indexed_authoring_projection(
    active: SelfModelSnapshot,
    *,
    generation: int,
) -> dict[str, Any]:
    """Create a deterministic lossless view whose long references are indices."""

    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
        raise ContinualLiveError("active generation must be a non-negative integer")
    active_raw = canonical_json_bytes(active.canonical())
    memory_ids = tuple(memory.memory_id for memory in active.memories)
    cell_ids = tuple(cell.cell_id for cell in active.cells)
    if len(memory_ids) != len(set(memory_ids)) or len(cell_ids) != len(set(cell_ids)):
        raise ContinualLiveError("active HSWM ids are not unique")
    memory_index = {memory_id: index for index, memory_id in enumerate(memory_ids)}
    cell_index = {cell_id: index for index, cell_id in enumerate(cell_ids)}

    def lookup_many(
        values: Sequence[str], indexes: Mapping[str, int], label: str
    ) -> list[int]:
        try:
            return [indexes[value] for value in values]
        except KeyError as error:
            raise ContinualLiveError(
                f"active HSWM {label} targets missing state"
            ) from error

    if active.entry_cell_id is None:
        entry_cell_index: int | None = None
    else:
        try:
            entry_cell_index = cell_index[active.entry_cell_id]
        except KeyError as error:  # guarded by SelfModelSnapshot, retained fail-closed
            raise ContinualLiveError("active HSWM entry cell is missing") from error
    body = {
        "active_generation": generation,
        "cells": [
            {
                "capability": cell.capability,
                "cell_id": cell.cell_id,
                "executor_agent_id": cell.executor_agent_id,
                "instruction": cell.instruction,
                "memory_indices": lookup_many(
                    cell.memory_ids, memory_index, "cell memory reference"
                ),
                "next_cell_indices": lookup_many(
                    cell.next_cell_ids, cell_index, "cell edge"
                ),
            }
            for cell in active.cells
        ],
        "entry_cell_index": entry_cell_index,
        "memories": [
            {
                "content": memory.content,
                "kind": memory.kind,
                "labels": list(memory.labels),
                "memory_id": memory.memory_id,
                "related_memory_indices": lookup_many(
                    memory.related_memory_ids, memory_index, "memory relation"
                ),
                "source_token_ids": list(memory.source_token_ids),
            }
            for memory in active.memories
        ],
        "schema": INDEXED_AUTHORING_VIEW_SCHEMA,
        "schema_version": active.schema_version,
        "snapshot_id": active.snapshot_id,
        "source_snapshot_sha256": _digest_bytes(active_raw),
    }
    projection = {**body, "projection_sha256": canonical_sha256(body)}
    expanded = _expand_indexed_authoring_projection(projection)
    if canonical_json_bytes(expanded) != active_raw:
        raise ContinualLiveError(
            "indexed authoring projection does not losslessly expand to active HSWM"
        )
    return projection


def _validate_indexed_authoring_projection(
    projection: Mapping[str, Any],
    *,
    active: SelfModelSnapshot,
    generation: int,
) -> None:
    """Bind an untrusted persisted view to one exact active snapshot/generation."""

    expanded = _expand_indexed_authoring_projection(projection)
    if canonical_json_bytes(expanded) != canonical_json_bytes(active.canonical()):
        raise ContinualLiveError("indexed projection expands to a different HSWM state")
    expected = _indexed_authoring_projection(active, generation=generation)
    if canonical_json_bytes(projection) != canonical_json_bytes(expected):
        raise ContinualLiveError("indexed projection is not the deterministic active view")


def _validate_compact_adapter_active_subset(active: SelfModelSnapshot) -> None:
    """Reject active structures the scalar assignment-vector patch cannot express."""

    if not active.cells:
        if active.entry_cell_id is not None or active.memories:
            raise ContinualLiveError(
                "compact adapter requires cells for every active memory"
            )
        return
    if active.entry_cell_id is None:
        raise ContinualLiveError("compact adapter active cells require an entry cell")
    cells_by_id = {cell.cell_id: cell for cell in active.cells}
    if len(cells_by_id) != len(active.cells):
        raise ContinualLiveError("compact adapter active cell ids are not unique")
    reachable: set[str] = set()
    queue = [active.entry_cell_id]
    while queue:
        cell_id = queue.pop(0)
        if cell_id in reachable:
            continue
        if cell_id not in cells_by_id:
            raise ContinualLiveError("compact adapter active edge targets missing cell")
        reachable.add(cell_id)
        queue.extend(cells_by_id[cell_id].next_cell_ids)
    if reachable != set(cells_by_id):
        raise ContinualLiveError("compact adapter requires every active cell reachable")
    memory_ids = {memory.memory_id for memory in active.memories}
    reference_counts = {memory_id: 0 for memory_id in memory_ids}
    for cell in active.cells:
        if cell.capability != CAPABILITY:
            raise ContinualLiveError("compact adapter active cell capability is unsupported")
        if cell.executor_agent_id is not None:
            raise ContinualLiveError("compact adapter cannot preserve delegated executors")
        for memory_id in cell.memory_ids:
            if memory_id not in reference_counts:
                raise ContinualLiveError(
                    "compact adapter active cell references missing memory"
                )
            reference_counts[memory_id] += 1
    if any(count != 1 for count in reference_counts.values()):
        raise ContinualLiveError(
            "compact adapter requires every active memory in exactly one reachable cell"
        )


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
) -> MutationProposal:
    value = _strict_object(text)
    if set(value) != {
        "cells",
        "entry_cell_index",
        "existing_memory_cell_indices",
        "new_memory_cell_indices",
        "new_memory_relations",
        "rationale",
    }:
        raise ContinualLiveError("compact structured update field set is invalid")
    if not all(
        isinstance(value[item], list)
        for item in (
            "cells",
            "existing_memory_cell_indices",
            "new_memory_cell_indices",
            "new_memory_relations",
        )
    ):
        raise ContinualLiveError("compact structured update list field is invalid")
    _compact_patch_response_schema(active, source_tokens, policy).validate_instance(
        value
    )
    if (
        not isinstance(value["rationale"], str)
        or not value["rationale"].strip()
        or len(value["rationale"]) > MAX_RATIONALE_CHARS
    ):
        raise ContinualLiveError("structured update requires a rationale")
    cell_count = len(value["cells"])
    if not 1 <= cell_count <= min(policy.max_cells, MAX_AUTHORED_CELLS):
        raise ContinualLiveError("compact patch exceeds the authored cell bound")
    source_ids = tuple(str(item["token_id"]) for item in source_tokens)
    if not source_ids or len(source_ids) != len(set(source_ids)):
        raise ContinualLiveError("public source token ids must be non-empty and unique")
    active_memories = tuple(active.memories)
    active_ids = tuple(memory.memory_id for memory in active_memories)
    new_ids = tuple(str(item["suggested_memory_id"]) for item in source_tokens)
    if len(new_ids) != len(set(new_ids)) or set(new_ids) & set(active_ids):
        raise ContinualLiveError("new deterministic memory ids collide with HSWM state")

    def index_list(
        items: object,
        label: str,
        *,
        upper_bound: int,
    ) -> tuple[int, ...]:
        if not isinstance(items, list) or any(
            isinstance(item, bool) or not isinstance(item, int) for item in items
        ):
            raise ContinualLiveError(f"{label} must contain integer indexes")
        indexes = tuple(items)
        if len(indexes) != len(set(indexes)) or any(
            item < 0 or item >= upper_bound for item in indexes
        ):
            raise ContinualLiveError(f"{label} contains duplicate or unknown indexes")
        return indexes

    cell_fields = {
        "capability",
        "cell_id",
        "executor_agent_id",
        "instruction",
        "next_cell_indices",
    }
    cell_specs: list[tuple[str, str, tuple[int, ...]]] = []
    for item in value["cells"]:
        if not isinstance(item, Mapping) or set(item) != cell_fields:
            raise ContinualLiveError("compact cell field set is invalid")
        if (
            not isinstance(item["cell_id"], str)
            or not item["cell_id"]
            or len(item["cell_id"]) > MAX_CELL_ID_CHARS
            or item["capability"] != CAPABILITY
            or not isinstance(item["instruction"], str)
            or not item["instruction"]
            or len(item["instruction"]) > MAX_CELL_INSTRUCTION_CHARS
        ):
            raise ContinualLiveError("compact cell text or capability is invalid")
        if item["executor_agent_id"] is not None:
            raise ContinualLiveError("compact cells cannot delegate hidden execution")
        next_cell_indices = index_list(
            item["next_cell_indices"],
            "cell next_cell_indices",
            upper_bound=cell_count,
        )
        if len(next_cell_indices) > MAX_CELL_EDGES:
            raise ContinualLiveError("compact cell edge list exceeds its bound")
        cell_specs.append(
            (item["cell_id"], item["instruction"], next_cell_indices)
        )
    cell_ids = tuple(item[0] for item in cell_specs)
    if len(cell_ids) != len(set(cell_ids)):
        raise ContinualLiveError("compact cell ids must be unique")
    entry_cell_index = value["entry_cell_index"]
    if (
        isinstance(entry_cell_index, bool)
        or not isinstance(entry_cell_index, int)
        or entry_cell_index < 0
        or entry_cell_index >= cell_count
    ):
        raise ContinualLiveError("entry_cell_index cites an unknown cell")

    def assignment_vector(
        items: object,
        label: str,
        *,
        expected_length: int,
        allow_delete: bool,
    ) -> tuple[int, ...]:
        if (
            not isinstance(items, list)
            or len(items) != expected_length
            or any(isinstance(item, bool) or not isinstance(item, int) for item in items)
        ):
            raise ContinualLiveError(f"{label} must have its exact aligned length")
        assignments = tuple(items)
        minimum = -1 if allow_delete else 0
        if any(item < minimum or item >= cell_count for item in assignments):
            raise ContinualLiveError(f"{label} cites an unknown cell")
        return assignments

    existing_assignments = assignment_vector(
        value["existing_memory_cell_indices"],
        "existing_memory_cell_indices",
        expected_length=len(active_memories),
        allow_delete=True,
    )
    new_assignments = assignment_vector(
        value["new_memory_cell_indices"],
        "new_memory_cell_indices",
        expected_length=len(source_tokens),
        allow_delete=False,
    )
    for cell_index in range(cell_count):
        existing_assigned_count = sum(
            assignment == cell_index for assignment in existing_assignments
        )
        new_assigned_count = sum(
            assignment == cell_index for assignment in new_assignments
        )
        if (
            existing_assigned_count + new_assigned_count
            > MAX_CELL_MEMORY_REFERENCES
        ):
            raise ContinualLiveError("compact cell exceeds the memory assignment bound")

    delete_ids = tuple(
        active_ids[index]
        for index, assignment in enumerate(existing_assignments)
        if assignment == -1
    )
    deleted_ids = set(delete_ids)
    for index, memory in enumerate(active_memories):
        if existing_assignments[index] != -1 and (
            set(memory.related_memory_ids) & deleted_ids
        ):
            raise ContinualLiveError(
                "cannot delete an existing memory still referenced by surviving state"
            )

    relation_fields = {
        "related_existing_memory_indices",
        "related_other_new_token_indices",
    }
    if len(value["new_memory_relations"]) != len(source_tokens):
        raise ContinualLiveError(
            "new_memory_relations must have one ordered item per public token"
        )
    parsed_relations: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    for source_index, item in enumerate(value["new_memory_relations"]):
        if not isinstance(item, Mapping) or set(item) != relation_fields:
            raise ContinualLiveError("new_memory_relations item field set is invalid")
        related_existing = index_list(
            item["related_existing_memory_indices"],
            "related_existing_memory_indices",
            upper_bound=len(active_memories),
        )
        related_other_new = index_list(
            item["related_other_new_token_indices"],
            "related_other_new_token_indices",
            upper_bound=len(source_tokens),
        )
        if (
            len(related_existing) > MAX_RELATED_MEMORY_IDS
            or len(related_other_new) > MAX_RELATED_MEMORY_IDS
        ):
            raise ContinualLiveError("new memory relation exceeds the bounded degree")
        if source_index in related_other_new:
            raise ContinualLiveError(
                "related_other_new_token_indices cannot contain its source array index"
            )
        source_content = source_tokens[source_index]["content"]
        if not isinstance(source_content, Mapping):
            raise ContinualLiveError("public relation content is not an object")
        source_target = source_content.get("target")
        for existing_index in related_existing:
            if existing_assignments[existing_index] == -1:
                raise ContinualLiveError("new relation targets a deleted existing memory")
            target_content = active_memories[existing_index].content
            if (
                not isinstance(target_content, Mapping)
                or source_target != target_content.get("source")
            ):
                raise ContinualLiveError(
                    "new-to-existing relation is not content-composable"
                )
        for target_index in related_other_new:
            target_content = source_tokens[target_index]["content"]
            if (
                not isinstance(target_content, Mapping)
                or source_target != target_content.get("source")
            ):
                raise ContinualLiveError(
                    "new-to-new relation is not content-composable"
                )
        parsed_relations.append((related_existing, related_other_new))

    memories = tuple(
        MemoryRecord(
            memory_id=new_ids[source_index],
            kind="atomic_relation",
            content=source_token["content"],
            source_token_ids=(source_ids[source_index],),
            related_memory_ids=(
                tuple(active_ids[index] for index in parsed_relations[source_index][0])
                + tuple(new_ids[index] for index in parsed_relations[source_index][1])
            ),
            labels=("agent-organized",),
        )
        for source_index, source_token in enumerate(source_tokens)
    )
    cells = tuple(
        CellRecord(
            cell_id=cell_ids[cell_index],
            capability=CAPABILITY,
            instruction=cell_specs[cell_index][1],
            memory_ids=(
                tuple(
                    active_ids[index]
                    for index, assignment in enumerate(existing_assignments)
                    if assignment == cell_index
                )
                + tuple(
                    new_ids[index]
                    for index, assignment in enumerate(new_assignments)
                    if assignment == cell_index
                )
            ),
            next_cell_ids=tuple(
                cell_ids[index] for index in cell_specs[cell_index][2]
            ),
            executor_agent_id=None,
        )
        for cell_index in range(cell_count)
    )

    reachable: set[int] = set()
    queue = [entry_cell_index]
    while queue:
        cell_index = queue.pop(0)
        if cell_index in reachable:
            continue
        reachable.add(cell_index)
        queue.extend(cell_specs[cell_index][2])
    if reachable != set(range(cell_count)):
        raise ContinualLiveError("every compact cell must be reachable from entry")

    proposal = make_mutation(
        base_snapshot_id=active.snapshot_id,
        expected_generation=generation,
        author_id=AUTHOR_ID,
        source_token_ids=source_ids,
        upsert_memories=memories,
        delete_memory_ids=tuple(delete_ids),
        cell_topology_mode=CellTopologyMode.REPLACE,
        cells=cells,
        entry_cell_id=cell_ids[entry_cell_index],
        rationale=value["rationale"],
    )
    # H/R/N all run the same materialization, contract, and policy check.
    apply_mutation(active, proposal, policy)
    return proposal


def _structure_update_payload(
    active: SelfModelSnapshot,
    source_tokens: Sequence[Mapping[str, Any]],
    *,
    generation: int,
) -> dict[str, Any]:
    indexed_view = _indexed_authoring_projection(active, generation=generation)
    _validate_indexed_authoring_projection(
        indexed_view,
        active=active,
        generation=generation,
    )
    return {
        "compact_patch_schema": COMPACT_PATCH_SCHEMA,
        "current_hswm_indexed_read_only": indexed_view,
        "instruction": (
            "Author only the compact HSWM organization patch. The adapter copies each "
            "public token's fixed content, id, and provenance into a MemoryRecord; you "
            "must author every memory relation and the complete reachable cell routing "
            "topology. The cells array order defines cell indices; entry_cell_index and "
            "next_cell_indices refer only to that returned array. The exact-length "
            "existing_memory_cell_indices vector aligns with the canonical "
            "current_hswm_indexed_read_only.memories order: -1 deletes that memory and "
            "every "
            "other value is its chosen cell index. The exact-length "
            "new_memory_cell_indices vector aligns with public_source_tokens order and "
            "never permits -1. The new_memory_relations item at array position i has "
            "public_source_tokens[i] as its SOURCE. related_existing_memory_indices "
            "targets the canonical existing-memory order; "
            "related_other_new_token_indices targets distinct OTHER public tokens and "
            "must never contain i. Use [] where no target is justified. A directed "
            "composition is valid only when source.content.target equals target.content."
            "source. Batches may be shuffled: never infer relations from index, "
            "adjacency, or order. Do not reproduce HSWM, MemoryRecord, or token JSON as "
            "a substitute for vectors; a bounded cell instruction may name public "
            "identifiers needed for routing. The indexed read-only view is a lossless "
            "projection of HSWM itself, not a separate plan or harness document."
        ),
        "index_alignment": {
            "cell_indices": "returned cells array order",
            "existing_memory_count": len(active.memories),
            "existing_memory_indices": (
                "current_hswm_indexed_read_only.memories canonical active order"
            ),
            "new_memory_count": len(source_tokens),
            "new_memory_indices": "public_source_tokens array order",
            "relation_source": "new_memory_relations array position",
        },
        "output_bounds": {
            "cell_id_max_chars": MAX_CELL_ID_CHARS,
            "cell_instruction_max_chars": MAX_CELL_INSTRUCTION_CHARS,
            "cells_max": MAX_AUTHORED_CELLS,
            "memory_assignments_max_per_cell": MAX_CELL_MEMORY_REFERENCES,
            "memory_relations_max_per_kind": MAX_RELATED_MEMORY_IDS,
            "new_memory_relation_semantics": (
                "relation array position is source; related_other_new_token_indices "
                "are distinct other new targets and related_existing_memory_indices "
                "are surviving existing targets; content.target-to-content.source "
                "composition only; self-reference forbidden; [] means no target"
            ),
            "next_cells_max_per_cell": MAX_CELL_EDGES,
            "rationale_max_chars": MAX_RATIONALE_CHARS,
            "single_cell_assignment_per_memory": True,
        },
        "mutation_expressivity": MUTATION_EXPRESSIVITY,
        "operation": "author_hswm_compact_patch",
        "protocol": LIVE_PROTOCOL,
        "public_source_tokens": [
            {**dict(item), "token_index": index}
            for index, item in enumerate(source_tokens)
        ],
        "response_contract": {
            "cells_item_fields": [
                "capability",
                "cell_id",
                "executor_agent_id",
                "instruction",
                "next_cell_indices",
            ],
            "existing_memory_cell_indices": {
                "exact_length": len(active.memories),
                "item_domain": "-1 or a valid returned-cell index",
                "source_order": "current_hswm_indexed_read_only.memories",
            },
            "new_memory_cell_indices": {
                "exact_length": len(source_tokens),
                "item_domain": "a valid returned-cell index; -1 forbidden",
                "source_order": "public_source_tokens",
            },
            "new_memory_relations": {
                "exact_length": len(source_tokens),
                "source_order": "public_source_tokens",
            },
            "top_level_fields": [
                "cells",
                "entry_cell_index",
                "existing_memory_cell_indices",
                "new_memory_cell_indices",
                "new_memory_relations",
                "rationale",
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
        completion_validator: Callable[[CallLedgerEntry], object] | None = None,
        proposal_validator: Callable[
            [MutationProposal, Sequence[Mapping[str, Any]], SelfModelSnapshot], object
        ]
        | None = None,
    ) -> None:
        super().__init__(
            name=name,
            backend=backend,
            budget=budget,
            isolation_id=isolation_id,
            journal_path=journal_path or Path(store_path).with_suffix(".calls.jsonl"),
            completion_validator=completion_validator,
        )
        self.commit_updates = commit_updates
        self.read_history = read_history
        self.reset_after_commit = reset_after_commit
        self.proposal_validator = proposal_validator
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
        _validate_compact_adapter_active_subset(prompt_snapshot)
        completion = self._call(
            operation="update",
            max_output_tokens=self.budget.update_max_output_tokens,
            system=(
                "Return exactly the six-key JSON object described by response_contract. "
                "Author "
                "cells, assignment vectors, relations, and routing directly in HSWM. "
                "The cells array defines the only valid cell indices. Entry and next "
                "indices must cite returned cells. existing_memory_cell_indices aligns "
                "with canonical existing-memory order and alone may use -1 to delete; "
                "new_memory_cell_indices aligns with public-token order and never uses "
                "-1. Both vectors must have their exact requested lengths, with no "
                "omission or default. new_memory_relations array position i makes public "
                "token i the SOURCE; its other-new targets must not contain i. Relations "
                "are content-composable only, never inferred from shuffled index/order. "
                "The read-only active HSWM uses canonical memory and cell indices while "
                "preserving content, provenance, relations, assignments, and topology. "
                "Do not return IDs where indices are required, memory/token JSON, a "
                "separate plan, or prose outside the six fields. Short cell instructions "
                "may name public routing identifiers. Use only public tokens; never "
                "infer a gold answer."
            ),
            payload=_structure_update_payload(
                prompt_snapshot,
                source_tokens,
                generation=active_record.generation,
            ),
            response_schema=_compact_patch_response_schema(
                prompt_snapshot,
                source_tokens,
                self.policy,
            ),
        )
        proposal = _parse_structure_proposal(
            completion.text,
            active=prompt_snapshot,
            source_tokens=source_tokens,
            generation=active_record.generation if self.commit_updates else 0,
            policy=self.policy,
        )
        if self.proposal_validator is not None:
            self.proposal_validator(proposal, source_tokens, prompt_snapshot)
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
        completion_validator: Callable[[CallLedgerEntry], object] | None = None,
    ) -> None:
        super().__init__(
            name="plain",
            backend=backend,
            budget=budget,
            isolation_id=isolation_id,
            journal_path=journal_path or Path(state_path).with_suffix(".calls.jsonl"),
            completion_validator=completion_validator,
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
            response_schema=_plain_memory_response_schema(),
        )
        value = _strict_object(completion.text)
        _plain_memory_response_schema().validate_instance(value)
        if set(value) != {"memory"} or not isinstance(value["memory"], str):
            raise ContinualLiveError("plain update response field set is invalid")
        if len(value["memory"]) > MAX_PLAIN_MEMORY_CHARS:
            raise ContinualLiveError("plain state exceeds the structured-output bound")
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


def _public_gate_nonce(domain: str, index: int, *, prefix: str) -> str:
    raw = (
        f"{PUBLIC_SCHEMA_GATE_FIXTURE_DOMAIN}|public-denylisted|{domain}|{index}"
    ).encode("ascii")
    return f"{prefix}_{sha256(raw).hexdigest()[:12]}"


def _public_gate_tokens(start: int, count: int) -> tuple[PublicLearningToken, ...]:
    return tuple(
        PublicLearningToken(
            source=_public_gate_nonce("node", index, prefix="n"),
            relation=_public_gate_nonce("relation", index % 7, prefix="r"),
            target=_public_gate_nonce("node", index + 1, prefix="n"),
        )
        for index in range(start, start + count)
    )


def _public_gate_incremental_tokens() -> tuple[PublicLearningToken, ...]:
    """Exercise new-to-new and canonical-index new-to-existing relations."""

    tokens = list(_public_gate_tokens(140, 4))
    tokens[1] = PublicLearningToken(
        source=_public_gate_nonce("node", 141, prefix="n"),
        relation=_public_gate_nonce("relation", 1, prefix="r"),
        target=_public_gate_nonce("node", 100, prefix="n"),
    )
    return tuple(tokens)


def public_schema_gate_fixture() -> dict[str, Any]:
    """Return the fixed public fixture, which is never eligible for evaluation."""

    warmup = _public_gate_tokens(0, 64)
    synthetic_extension = _public_gate_tokens(64, 76)
    incremental = _public_gate_incremental_tokens()
    probe = PublicProbe(
        step=1,
        source=_public_gate_nonce("node", 0, prefix="n"),
        relations=(_public_gate_nonce("relation", 0, prefix="r"),),
        choices=(
            _public_gate_nonce("decoy", 1, prefix="n"),
            _public_gate_nonce("node", 1, prefix="n"),
            _public_gate_nonce("decoy", 2, prefix="n"),
            _public_gate_nonce("decoy", 3, prefix="n"),
        ),
    )
    value = {
        "compact_patch_schema": COMPACT_PATCH_SCHEMA,
        "denylisted_from_evaluation": True,
        "episode_id": PUBLIC_SCHEMA_GATE_EPISODE,
        "incremental_tokens": [item.canonical() for item in incremental],
        "probe": probe.canonical(),
        "probe_answer": _public_gate_nonce("node", 1, prefix="n"),
        "protocol": PUBLIC_SCHEMA_GATE_FIXTURE_DOMAIN,
        "synthetic_extension_tokens": [
            item.canonical() for item in synthetic_extension
        ],
        "warmup_tokens": [item.canonical() for item in warmup],
    }
    return {**value, "fixture_sha256": canonical_sha256(value)}


def _validate_public_gate_agent_relations(
    proposal: MutationProposal,
    source_tokens: Sequence[Mapping[str, Any]],
    active: SelfModelSnapshot,
) -> dict[str, Any]:
    """Require the public fixture's content-derived directed memory graph.

    This is a pre-commit schema-gate predicate, not a repair step.  The model
    must author the edges itself; a missing, extra, reversed, or self edge
    rejects the proposal while the durable store remains at its prior state.
    """

    if proposal.delete_memory_ids:
        raise ContinualLiveError(
            "public gate compact patch cannot delete existing fixture memories"
        )
    expected_memory_ids = {
        str(item["suggested_memory_id"]) for item in source_tokens
    }
    memories = {memory.memory_id: memory for memory in proposal.upsert_memories}
    if set(memories) != expected_memory_ids:
        raise ContinualLiveError(
            "public gate relation check lacks the exact deterministic memories"
        )
    expected_new_edges = sorted(
        {
            (
                str(source["suggested_memory_id"]),
                str(target["suggested_memory_id"]),
            )
            for source_index, source in enumerate(source_tokens)
            for target_index, target in enumerate(source_tokens)
            if source_index != target_index
            and source["content"].get("target")
            == target["content"].get("source")
        }
    )
    expected_existing_edges = sorted(
        {
            (str(source["suggested_memory_id"]), target.memory_id)
            for source in source_tokens
            for target in active.memories
            if source["content"].get("target") == target.content.get("source")
        }
    )
    expected_edges = sorted(expected_new_edges + expected_existing_edges)
    observed_edges = sorted(
        (memory.memory_id, related_memory_id)
        for memory in proposal.upsert_memories
        for related_memory_id in memory.related_memory_ids
    )
    expected_values = [
        {"source_memory_id": source, "target_memory_id": target}
        for source, target in expected_edges
    ]
    observed_values = [
        {"source_memory_id": source, "target_memory_id": target}
        for source, target in observed_edges
    ]
    if observed_edges != expected_edges:
        raise ContinualLiveError(
            "public gate agent-authored relations differ from the exact "
            "content-derived directed composition graph"
        )
    new_ids = set(expected_memory_ids)
    active_ids = {memory.memory_id for memory in active.memories}
    observed_new_edges = sorted(edge for edge in observed_edges if edge[1] in new_ids)
    observed_existing_edges = sorted(
        edge for edge in observed_edges if edge[1] in active_ids
    )
    if len(observed_new_edges) + len(observed_existing_edges) != len(observed_edges):
        raise ContinualLiveError("public gate relation targets unknown memory state")

    def relation_values(edges: Sequence[tuple[str, str]]) -> list[dict[str, str]]:
        return [
            {"source_memory_id": source, "target_memory_id": target}
            for source, target in edges
        ]

    return {
        "author": AUTHOR_ID,
        "exact_match": True,
        "expected_existing_relation_count": len(expected_existing_edges),
        "expected_existing_relations_sha256": canonical_sha256(
            relation_values(expected_existing_edges)
        ),
        "expected_new_relation_count": len(expected_new_edges),
        "expected_new_relations_sha256": canonical_sha256(
            relation_values(expected_new_edges)
        ),
        "expected_relation_count": len(expected_edges),
        "expected_relations_sha256": canonical_sha256(expected_values),
        "observed_existing_relation_count": len(observed_existing_edges),
        "observed_existing_relations_sha256": canonical_sha256(
            relation_values(observed_existing_edges)
        ),
        "observed_new_relation_count": len(observed_new_edges),
        "observed_new_relations_sha256": canonical_sha256(
            relation_values(observed_new_edges)
        ),
        "observed_relation_count": len(observed_edges),
        "observed_relations_sha256": canonical_sha256(observed_values),
        "source_token_count": len(source_tokens),
    }


def _install_public_gate_extension(
    arm: StructuredHSWMArm,
    tokens: Sequence[PublicLearningToken],
) -> dict[str, Any]:
    """Grow a public dry-run state to 140 memories without another model call."""

    batch = LearningBatch(
        episode_id=PUBLIC_SCHEMA_GATE_EPISODE,
        after_step=1,
        chosen=None,
        correct=False,
        learning_tokens=tuple(tokens),
    )
    source_tokens = _public_source_tokens(batch)
    active = arm.store.active_snapshot()
    if len(active.snapshot.memories) != 64 or not active.snapshot.cells:
        raise ContinualLiveError("public gate extension requires the committed 64-state")
    new_ids = tuple(str(item["suggested_memory_id"]) for item in source_tokens)
    if set(new_ids) & {memory.memory_id for memory in active.snapshot.memories}:
        raise ContinualLiveError("public gate extension memory id collision")
    memories = tuple(
        MemoryRecord(
            memory_id=new_ids[index],
            kind="atomic_relation",
            content=item["content"],
            source_token_ids=(str(item["token_id"]),),
            related_memory_ids=(new_ids[index + 1],)
            if index + 1 < len(new_ids)
            else (),
            labels=("public-gate-fixture",),
        )
        for index, item in enumerate(source_tokens)
    )
    cells = tuple(
        CellRecord(
            cell_id=cell.cell_id,
            capability=cell.capability,
            instruction=cell.instruction,
            memory_ids=cell.memory_ids
            + (new_ids if cell.cell_id == active.snapshot.entry_cell_id else ()),
            next_cell_ids=cell.next_cell_ids,
            executor_agent_id=cell.executor_agent_id,
        )
        for cell in active.snapshot.cells
    )
    cognitive_tokens = tuple(
        make_token(
            token_id=str(item["token_id"]),
            episode_id=PUBLIC_SCHEMA_GATE_EPISODE,
            position=100_000 + index,
            role="environment",
            content=item["content"],
            provenance={
                "denylisted_from_evaluation": True,
                "protocol": PUBLIC_SCHEMA_GATE_PROTOCOL,
            },
        )
        for index, item in enumerate(source_tokens)
    )
    proposal = make_mutation(
        base_snapshot_id=active.snapshot.snapshot_id,
        expected_generation=active.generation,
        author_id="evaluator:public-schema-gate-fixture",
        source_token_ids=tuple(token.token_id for token in cognitive_tokens),
        upsert_memories=memories,
        cell_topology_mode=CellTopologyMode.REPLACE,
        cells=cells,
        entry_cell_id=active.snapshot.entry_cell_id,
        rationale="PUBLIC_SCHEMA_GATE_SYNTHETIC_WORST_STATE_ONLY",
    )
    arm.store.append_tokens(cognitive_tokens)
    receipt = arm.store.commit(proposal)
    arm._source_token_ids.extend(token.token_id for token in cognitive_tokens)
    after = arm.store.active_snapshot().snapshot
    if len(after.memories) != 140:
        raise ContinualLiveError("public gate extension did not create 140 memories")
    return {
        "activation_id": receipt.activation_id,
        "after_state_sha256": _digest_bytes(canonical_json_bytes(after.canonical())),
        "before_state_sha256": _digest_bytes(
            canonical_json_bytes(active.snapshot.canonical())
        ),
        "evaluator_authored_memory_count": len(memories),
        "evaluator_authored_relation_count": sum(
            len(memory.related_memory_ids) for memory in memories
        ),
        "memory_count": len(after.memories),
        "mutation_sha256": canonical_sha256(proposal.canonical()),
        "relation_author": "evaluator:public-schema-gate-fixture",
    }


def _public_gate_call_summary(entry: CallLedgerEntry) -> dict[str, Any]:
    try:
        raw_response = json.loads(entry.completion.raw_response_json)
        finish_reason = raw_response["choices"][0]["finish_reason"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
        raise ContinualLiveError("public gate response lacks finish_reason") from error
    if finish_reason != "stop":
        raise ContinualLiveError(
            f"public gate model call did not stop cleanly: {finish_reason!r}"
        )
    if not entry.completion.usage_reported:
        raise ContinualLiveError("public gate requires provider token usage")
    if (
        entry.operation == "update"
        and entry.completion.output_tokens > PUBLIC_SCHEMA_GATE_OUTPUT_TOKEN_CEILING
    ):
        raise ContinualLiveError("public gate update lacks frozen output headroom")
    if (
        entry.operation == "update"
        and entry.completion.input_tokens > PUBLIC_SCHEMA_GATE_MAX_UPDATE_INPUT_TOKENS
    ):
        raise ContinualLiveError("public gate update exceeds frozen input-token ceiling")
    return {
        "arm": entry.arm,
        "finish_reason": finish_reason,
        "input_tokens": entry.completion.input_tokens,
        "operation": entry.operation,
        "ordinal": entry.ordinal,
        "output_tokens": entry.completion.output_tokens,
        "request_sha256": entry.completion.request_sha256,
        "response_sha256": entry.completion.response_sha256,
    }


def _authoring_projection_binding(
    entry: CallLedgerEntry,
    *,
    store: SQLiteSelfModelStore,
) -> dict[str, Any]:
    if entry.operation != "update":
        raise ContinualLiveError("authoring projection binding requires an update call")
    try:
        payload = json.loads(entry.request_payload_json)
        projection = payload["current_hswm_indexed_read_only"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ContinualLiveError("update ledger lacks indexed authoring projection") from error
    if not isinstance(projection, Mapping):
        raise ContinualLiveError("indexed authoring projection is not an object")
    if payload.get("mutation_expressivity") != MUTATION_EXPRESSIVITY:
        raise ContinualLiveError("update ledger lacks compact adapter scope binding")
    generation = projection["active_generation"]
    snapshot_id = projection["snapshot_id"]
    historical = store.load_snapshot(snapshot_id)
    if generation == 0:
        if snapshot_id != GENESIS.snapshot_id:
            raise ContinualLiveError("generation-zero projection is not exact genesis")
    else:
        matches = [
            receipt
            for receipt in store.activation_history()
            if receipt.active_generation == generation
            and receipt.active_snapshot_id == snapshot_id
        ]
        if len(matches) != 1:
            raise ContinualLiveError(
                "projection source is not one exact historical active state"
            )
    _validate_indexed_authoring_projection(
        projection,
        active=historical,
        generation=generation,
    )
    return {
        "active_generation": generation,
        "mutation_expressivity": payload.get("mutation_expressivity"),
        "projection_schema": projection["schema"],
        "projection_sha256": projection["projection_sha256"],
        "request_sha256": entry.completion.request_sha256,
        "snapshot_id": snapshot_id,
        "source_snapshot_sha256": projection["source_snapshot_sha256"],
    }


def run_public_schema_gate(
    *,
    backend_factory: Callable[[], ChatBackend],
    state_dir: Path,
) -> dict[str, Any]:
    """Run exactly four public, non-evaluation calls through the v4 adapter."""

    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=False)
    budget = ArmBudget(
        answer_max_output_tokens=128,
        update_max_output_tokens=PUBLIC_SCHEMA_GATE_OUTPUT_TOKEN_CEILING,
        max_input_bytes=2_000_000,
        max_state_bytes=1_000_000,
    )
    accepted_model: list[str] = []
    agent_relation_checks: list[dict[str, Any]] = []

    def accept_gate_completion(entry: CallLedgerEntry) -> None:
        _public_gate_call_summary(entry)
        if accepted_model and entry.completion.model != accepted_model[0]:
            raise ContinualLiveError("public gate returned model identity drift")
        if not accepted_model:
            accepted_model.append(entry.completion.model)

    def accept_gate_proposal(
        proposal: MutationProposal,
        source_tokens: Sequence[Mapping[str, Any]],
        active: SelfModelSnapshot,
    ) -> None:
        agent_relation_checks.append(
            _validate_public_gate_agent_relations(proposal, source_tokens, active)
        )

    structured = StructuredHSWMArm(
        backend=backend_factory(),
        budget=budget,
        isolation_id="public-schema-gate:structured",
        store_path=state_dir / "structured" / "state.sqlite3",
        journal_path=state_dir / "structured" / "calls.jsonl",
        completion_validator=accept_gate_completion,
        proposal_validator=accept_gate_proposal,
    )
    plain = PlainTextArm(
        backend=backend_factory(),
        budget=budget,
        isolation_id="public-schema-gate:plain",
        state_path=state_dir / "plain" / "state.json",
        journal_path=state_dir / "plain" / "calls.jsonl",
        completion_validator=accept_gate_completion,
    )
    fixture = public_schema_gate_fixture()
    warmup_tokens = _public_gate_tokens(0, 64)
    incremental_tokens = _public_gate_incremental_tokens()
    warmup = LearningBatch(
        episode_id=PUBLIC_SCHEMA_GATE_EPISODE,
        after_step=0,
        chosen=None,
        correct=False,
        learning_tokens=warmup_tokens,
    )
    incremental = LearningBatch(
        episode_id=PUBLIC_SCHEMA_GATE_EPISODE,
        after_step=2,
        chosen=None,
        correct=False,
        learning_tokens=incremental_tokens,
    )
    try:
        genesis_sha256 = _digest_bytes(structured.state_canonical_bytes())
        warmup_update = structured.update(warmup)
        after_warmup = structured.store.active_snapshot().snapshot
        if len(after_warmup.memories) != 64:
            raise ContinualLiveError("public gate warmup did not materialize 64 memories")
        extension = _install_public_gate_extension(
            structured, _public_gate_tokens(64, 76)
        )
        incremental_update = structured.update(incremental)
        after_incremental = structured.store.active_snapshot().snapshot
        if len(after_incremental.memories) != 144:
            raise ContinualLiveError(
                "public gate incremental patch did not materialize 144 memories"
            )
        if (
            len(agent_relation_checks) != 2
            or [item["source_token_count"] for item in agent_relation_checks]
            != [64, 4]
            or [item["expected_relation_count"] for item in agent_relation_checks]
            != [63, 3]
        ):
            raise ContinualLiveError(
                "public gate did not verify both exact agent-authored relation chains"
            )
        plain_update = plain.update(warmup)
        before_probe_sha256 = _digest_bytes(structured.state_canonical_bytes())
        probe = PublicProbe(
            step=1,
            source=_public_gate_nonce("node", 0, prefix="n"),
            relations=(_public_gate_nonce("relation", 0, prefix="r"),),
            choices=(
                _public_gate_nonce("decoy", 1, prefix="n"),
                _public_gate_nonce("node", 1, prefix="n"),
                _public_gate_nonce("decoy", 2, prefix="n"),
                _public_gate_nonce("decoy", 3, prefix="n"),
            ),
        )
        answer = structured.answer(probe)
        chosen = parse_choice(answer.response_text, choices=probe.choices)
        after_probe_sha256 = _digest_bytes(structured.state_canonical_bytes())
        if chosen != fixture["probe_answer"]:
            raise ContinualLiveError("public gate read-only probe was incorrect")
        if before_probe_sha256 != after_probe_sha256:
            raise ContinualLiveError("public gate probe mutated HSWM state")
        if len(structured.ledger) != 3 or len(plain.ledger) != 1:
            raise ContinualLiveError("public gate must make exactly four model calls")
        call_entries = (
            structured.ledger[0],
            structured.ledger[1],
            plain.ledger[0],
            structured.ledger[2],
        )
        call_summaries = tuple(_public_gate_call_summary(item) for item in call_entries)
        projection_bindings = [
            _authoring_projection_binding(
                structured.ledger[index],
                store=structured.store,
            )
            for index in (0, 1)
        ]
        if len({item.completion.model for item in call_entries}) != 1:
            raise ContinualLiveError("public gate returned model identity drift")
        result = {
            "adapter_schema": COMPACT_PATCH_SCHEMA,
            "agent_relation_checks": agent_relation_checks,
            "authoring_projection_bindings": projection_bindings,
            "after_incremental_state_sha256": _digest_bytes(
                canonical_json_bytes(after_incremental.canonical())
            ),
            "after_probe_state_sha256": after_probe_sha256,
            "after_warmup_state_sha256": _digest_bytes(
                canonical_json_bytes(after_warmup.canonical())
            ),
            "before_probe_state_sha256": before_probe_sha256,
            "calls": list(call_summaries),
            "calls_observed": len(call_summaries),
            "denylisted_from_evaluation": True,
            "extension": extension,
            "final_cell_count": len(after_incremental.cells),
            "final_memory_count": len(after_incremental.memories),
            "fixture_sha256": fixture["fixture_sha256"],
            "genesis_state_sha256": genesis_sha256,
            "indexed_authoring_view_schema": INDEXED_AUTHORING_VIEW_SCHEMA,
            "input_token_ceiling": PUBLIC_SCHEMA_GATE_MAX_UPDATE_INPUT_TOKENS,
            "incremental_update_receipt_sha256": incremental_update.receipt_sha256,
            "mutation_expressivity": MUTATION_EXPRESSIVITY,
            "output_token_ceiling": PUBLIC_SCHEMA_GATE_OUTPUT_TOKEN_CEILING,
            "plain_update_receipt_sha256": plain_update.receipt_sha256,
            "probe_answer_receipt_sha256": answer.receipt_sha256,
            "probe_choice": chosen,
            "probe_mechanism_attribution": "not-attested-by-this-public-gate",
            "protocol": PUBLIC_SCHEMA_GATE_PROTOCOL,
            "provider_structured_output_backend_attested": False,
            "provider_context_window_tokens": (
                PUBLIC_SCHEMA_GATE_CONTEXT_WINDOW_TOKENS
            ),
            "semantic_acceptance": "local-strict-parser-after-provider-json-schema",
            "valid": True,
            "warmup_update_receipt_sha256": warmup_update.receipt_sha256,
        }
        return {**result, "result_sha256": canonical_sha256(result)}
    finally:
        structured.store.close()


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

_RECOVERY_PRECOMMIT_FIELDS = {
    "assignment_document",
    "assignment_sha256",
    "commitment_document",
    "commitment_set_sha256",
    "confirmatory_denylist",
    "confirmatory_eligible",
    "engineering_only",
    "failed_primary_binding",
    "frozen_before_recovery_completion_calls",
    "intended_provider",
    "precommit_sha256",
    "primary_preimages_revealed",
    "primary_seed_commitment_denylist",
    "primary_seed_indices_prohibited",
    "protocol",
    "recovery_execution",
    "reserve_preimages_revealed",
    "schema",
    "seed_preimage_encoding",
    "selected_seed_indices",
    "supersedes_canonical_artifact_sha256",
    "supersession_reason",
}

_FAILED_PRIMARY_BINDING_FIELDS = {
    "artifacts_tar_sha256",
    "completed_model_responses",
    "completed_streams",
    "endpoint_calls_observed",
    "failed_call_journal_sha256",
    "failed_run_id",
    "failed_source_revision",
    "failure_class",
    "frozen_v2_precommit_artifact_sha256",
    "outer_receipt_sha256",
    "output_terminal_file_sha256",
    "post_reveal_file_sha256",
    "post_reveal_validation_sha256",
    "preregistration_file_sha256",
    "preregistration_sha256",
    "retry_permitted",
    "score_artifacts_written",
    "seed_reveal_file_sha256",
    "service_identity_sha256",
    "status_file_sha256",
    "terminal_receipt_sha256",
    "usable_model_responses",
    "wrapper_terminal_file_sha256",
}


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ContinualLiveError(f"{label} must be a SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as error:
        raise ContinualLiveError(f"{label} contains non-hex text") from error
    return value.lower()


def _validate_recovery_precommit(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContinualLiveError(f"invalid recovery precommit JSON: {error}") from error
    if not isinstance(value, dict) or set(value) != _RECOVERY_PRECOMMIT_FIELDS:
        raise ContinualLiveError("recovery precommit field set is not frozen v3")
    if canonical_json_bytes(value) != raw:
        raise ContinualLiveError(
            "recovery precommit must be exact canonical JSON with no trailing newline"
        )
    unsigned = {key: item for key, item in value.items() if key != "precommit_sha256"}
    if (
        _require_sha256(value["precommit_sha256"], "precommit_sha256")
        != FROZEN_RECOVERY_PRECOMMIT_SHA256
        or value["precommit_sha256"] != canonical_sha256(unsigned)
    ):
        raise ContinualLiveError("recovery precommit self-hash mismatch")
    if (
        value["schema"] != "hswm-continual-pilot-recovery-precommit/v3"
        or value["protocol"] != PROTOCOL
        or value["engineering_only"] is not True
        or value["confirmatory_eligible"] is not False
        or value["frozen_before_recovery_completion_calls"] is not True
        or value["primary_preimages_revealed"] is not True
        or value["reserve_preimages_revealed"] is not False
        or value["primary_seed_indices_prohibited"] != [0, 1]
        or value["selected_seed_indices"] != [2, 3]
        or value["seed_preimage_encoding"]
        != "32 raw bytes; commitment=sha256(raw bytes)"
    ):
        raise ContinualLiveError(
            "recovery authority must prohibit primary indices and select reserve [2, 3]"
        )
    commitment_document = value["commitment_document"]
    if not isinstance(commitment_document, dict) or set(commitment_document) != {
        "commitments",
        "protocol",
        "purpose",
        "schema",
    }:
        raise ContinualLiveError("recovery commitment_document is invalid")
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
        raise ContinualLiveError("recovery commitment_document values are invalid")
    for index, commitment in enumerate(commitments):
        _require_sha256(commitment, f"commitment[{index}]")
    if (
        _require_sha256(value["commitment_set_sha256"], "commitment_set_sha256")
        != canonical_sha256(commitment_document)
    ):
        raise ContinualLiveError("recovery commitment document hash mismatch")
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
        raise ContinualLiveError("recovery assignment_document is invalid")
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
        raise ContinualLiveError("recovery assignment_document values are invalid")
    if (
        _require_sha256(value["assignment_sha256"], "assignment_sha256")
        != canonical_sha256(assignment)
        or value["confirmatory_denylist"] != commitments
        or value["primary_seed_commitment_denylist"] != commitments[:2]
    ):
        raise ContinualLiveError("recovery assignment or denylist mismatch")
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
        "per_call_timeout_seconds": 600.0,
        "removal_restore": True,
        "removal_restore_extra_calls_per_stream": 15,
        "removal_restore_probes_per_stream": 5,
        "resume_allowed": False,
        "retry_limit": 0,
        "streams": 2,
        "update_max_tokens": 8192,
    }
    if value["recovery_execution"] != expected_execution:
        raise ContinualLiveError("recovery execution differs from frozen v3")
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
        raise ContinualLiveError("recovery intended_provider field set is invalid")
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
        raise ContinualLiveError("recovery intended_provider values are invalid")
    binding = value["failed_primary_binding"]
    if not isinstance(binding, dict) or set(binding) != _FAILED_PRIMARY_BINDING_FIELDS:
        raise ContinualLiveError("failed primary binding field set is invalid")
    for key in binding:
        if key.endswith("_sha256"):
            _require_sha256(binding[key], f"failed_primary_binding.{key}")
    if (
        binding["completed_model_responses"] != 0
        or binding["completed_streams"] != 0
        or binding["endpoint_calls_observed"] != 1
        or binding["failure_class"] != "mechanical_timeout_before_response"
        or binding["retry_permitted"] is not False
        or binding["score_artifacts_written"] is not False
        or binding["usable_model_responses"] != 0
        or binding["frozen_v2_precommit_artifact_sha256"]
        != FROZEN_PILOT_PRECOMMIT_ARTIFACT_SHA256
        or not isinstance(binding["failed_run_id"], str)
        or not binding["failed_run_id"]
        or not re.fullmatch(r"[0-9a-f]{40}", str(binding["failed_source_revision"]))
    ):
        raise ContinualLiveError("failed primary binding does not prove no-score timeout")
    if (
        value["supersedes_canonical_artifact_sha256"]
        != FROZEN_PILOT_PRECOMMIT_ARTIFACT_SHA256
        or "timed out" not in value["supersession_reason"]
        or "120 to 600" not in value["supersession_reason"]
    ):
        raise ContinualLiveError("recovery supersession does not bind the consumed v2")
    return value


def _read_pilot_precommit(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    artifact_sha256 = _digest_bytes(raw)
    if artifact_sha256 == FROZEN_RECOVERY_PRECOMMIT_ARTIFACT_SHA256:
        return _validate_recovery_precommit(raw), raw
    if artifact_sha256 != FROZEN_PILOT_PRECOMMIT_ARTIFACT_SHA256:
        raise ContinualLiveError(
            "precommit is neither the exact frozen v2 nor reserve-recovery v3 artifact"
        )
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


def _sha256_file(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise ContinualLiveError(f"cannot read bound artifact {path}: {error}") from error
    return digest.hexdigest()


def _json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContinualLiveError(f"{label} is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ContinualLiveError(f"{label} must be one JSON object")
    return value


def _tar_regular_members(archive: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    result: dict[str, tarfile.TarInfo] = {}
    for member in archive.getmembers():
        if member.name.startswith("/") or ".." in Path(member.name).parts:
            raise ContinualLiveError("failed-run tar contains an unsafe member path")
        if member.issym() or member.islnk():
            raise ContinualLiveError("failed-run tar must not contain links")
        if not member.isfile():
            continue
        if member.name in result:
            raise ContinualLiveError("failed-run tar contains duplicate file members")
        result[member.name] = member
    if not result or len(result) > 512:
        raise ContinualLiveError("failed-run tar file cardinality is invalid")
    return result


def _tar_member_bytes(
    archive: tarfile.TarFile,
    members: Mapping[str, tarfile.TarInfo],
    name: str,
    *,
    max_bytes: int = 16_000_000,
) -> bytes:
    member = members.get(name)
    if member is None:
        raise ContinualLiveError(f"failed-run tar is missing {name}")
    if member.size > max_bytes:
        raise ContinualLiveError(f"failed-run tar member {name} exceeds its byte bound")
    handle = archive.extractfile(member)
    if handle is None:
        raise ContinualLiveError(f"failed-run tar member {name} is unreadable")
    raw = handle.read(max_bytes + 1)
    if len(raw) != member.size or len(raw) > max_bytes:
        raise ContinualLiveError(f"failed-run tar member {name} is truncated or oversized")
    return raw


def _tar_member_sha256(
    archive: tarfile.TarFile, member: tarfile.TarInfo
) -> str:
    handle = archive.extractfile(member)
    if handle is None:
        raise ContinualLiveError(f"failed-run tar member {member.name} is unreadable")
    digest = sha256()
    observed = 0
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        observed += len(chunk)
        digest.update(chunk)
    if observed != member.size:
        raise ContinualLiveError(f"failed-run tar member {member.name} is truncated")
    return digest.hexdigest()


def _validate_failed_primary_artifacts(
    artifacts_tar: Path,
    outer_receipt_path: Path,
    *,
    precommit: Mapping[str, Any],
) -> dict[str, Any]:
    """Prove that reserve activation follows the exact no-score r2 timeout."""

    binding = precommit["failed_primary_binding"]
    tar_sha256 = _sha256_file(artifacts_tar)
    receipt_raw = outer_receipt_path.read_bytes()
    receipt_sha256 = _digest_bytes(receipt_raw)
    if tar_sha256 != binding["artifacts_tar_sha256"]:
        raise ContinualLiveError("failed-run artifacts.tar differs from frozen v3")
    if receipt_sha256 != binding["outer_receipt_sha256"]:
        raise ContinualLiveError("failed-run outer receipt differs from frozen v3")
    outer_receipt = _json_bytes(receipt_raw, "failed-run outer receipt")
    if set(outer_receipt) != {
        "artifact",
        "command_sha256",
        "durable_tier",
        "execution_tier",
        "exit_code",
        "finished_at",
        "run_id",
        "schema",
        "source_commit",
        "source_root",
        "started_at",
        "status",
    }:
        raise ContinualLiveError("failed-run outer receipt field set is invalid")
    artifact = outer_receipt["artifact"]
    if (
        outer_receipt["schema"] != "bhgman-hswm-run/v1"
        or outer_receipt["run_id"] != binding["failed_run_id"]
        or outer_receipt["source_commit"] != binding["failed_source_revision"]
        or outer_receipt["status"] != "failed"
        or outer_receipt["exit_code"] != 1
        or outer_receipt["execution_tier"] != "dgx-nvme"
        or outer_receipt["durable_tier"] != "data01-4tb-nfs"
        or not isinstance(artifact, dict)
        or artifact
        != {
            "bytes": artifacts_tar.stat().st_size,
            "name": "artifacts.tar",
            "sha256": tar_sha256,
        }
    ):
        raise ContinualLiveError("failed-run outer receipt does not bind the r2 artifact")

    pilot_prefix = "outputs/pilot/"
    required = {
        "journal": pilot_prefix + "state/stream-00/hswm/calls.jsonl",
        "post_reveal": pilot_prefix + "post_reveal_validation.json",
        "precommit": pilot_prefix + "frozen_precommit.canonical.json",
        "prereg": pilot_prefix + "preregistration.json",
        "seed_reveal": pilot_prefix + "seed_reveal.json",
        "status": pilot_prefix + "status.json",
        "terminal": pilot_prefix + "terminal_receipt.json",
        "service_before": "outputs/ops/service.before.canonical.json",
        "service_after": "outputs/ops/service.after.canonical.json",
        "wrapper": "outputs/ops/wrapper_terminal.canonical.json",
    }
    try:
        archive_context = tarfile.open(artifacts_tar, mode="r:*")
    except (OSError, tarfile.TarError) as error:
        raise ContinualLiveError(f"failed-run artifact is not a readable tar: {error}") from error
    with archive_context as archive:
        members = _tar_regular_members(archive)
        raw = {
            key: _tar_member_bytes(archive, members, name)
            for key, name in required.items()
        }
        expected_member_hashes = {
            "journal": binding["failed_call_journal_sha256"],
            "post_reveal": binding["post_reveal_file_sha256"],
            "precommit": binding["frozen_v2_precommit_artifact_sha256"],
            "prereg": binding["preregistration_file_sha256"],
            "seed_reveal": binding["seed_reveal_file_sha256"],
            "status": binding["status_file_sha256"],
            "terminal": binding["output_terminal_file_sha256"],
            "service_before": FAILED_SERVICE_BEFORE_ARTIFACT_SHA256,
            "service_after": FAILED_SERVICE_AFTER_ARTIFACT_SHA256,
            "wrapper": binding["wrapper_terminal_file_sha256"],
        }
        for key, expected in expected_member_hashes.items():
            if _digest_bytes(raw[key]) != expected:
                raise ContinualLiveError(
                    f"failed-run tar member {required[key]} differs from frozen evidence"
                )

        terminal = _json_bytes(raw["terminal"], "failed-run terminal receipt")
        terminal_unsigned = {
            key: item for key, item in terminal.items() if key != "receipt_sha256"
        }
        if (
            terminal.get("receipt_sha256") != canonical_sha256(terminal_unsigned)
            or terminal.get("receipt_sha256") != binding["terminal_receipt_sha256"]
            or terminal.get("status") != "failed"
            or terminal.get("completed_streams") != 0
            or terminal.get("removal_mediation_gate_passed") is not None
        ):
            raise ContinualLiveError("failed-run terminal does not prove zero completion")
        artifact_hashes = terminal.get("artifact_sha256s")
        if not isinstance(artifact_hashes, dict):
            raise ContinualLiveError("failed-run terminal lacks its artifact hash map")
        actual_pilot_hashes = {
            name.removeprefix(pilot_prefix): _tar_member_sha256(archive, member)
            for name, member in members.items()
            if name.startswith(pilot_prefix)
            and name != required["terminal"]
        }
        if actual_pilot_hashes != artifact_hashes:
            raise ContinualLiveError("failed-run terminal artifact map is not exact")

        status = _json_bytes(raw["status"], "failed-run status")
        if (
            set(status) != {"completed_streams", "error", "status"}
            or status["status"] != "failed"
            or status["completed_streams"] != 0
            or status["error"] != terminal.get("error")
        ):
            raise ContinualLiveError("failed-run status differs from terminal receipt")
        journal_lines = [line for line in raw["journal"].splitlines() if line]
        if len(journal_lines) != 2:
            raise ContinualLiveError("failed-run journal is not exactly intent+failed")
        events = [
            _json_bytes(line, f"failed-run journal event {index}")
            for index, line in enumerate(journal_lines)
        ]
        intent, failed = events
        if (
            intent.get("event") != "intent"
            or failed.get("event") != "failed"
            or intent.get("arm") != failed.get("arm")
            or intent.get("arm") != "hswm"
            or intent.get("operation") != failed.get("operation")
            or intent.get("operation") != "update"
            or intent.get("ordinal") != failed.get("ordinal")
            or intent.get("ordinal") != 0
            or intent.get("request_id") != failed.get("request_id")
            or intent.get("max_output_tokens") != 8192
            or intent.get("backend", {}).get("timeout_seconds") != 120.0
            or failed.get("outcome") != "unknown"
            or failed.get("retry_permitted") is not False
            or "timed out" not in str(failed.get("error", "")).lower()
            or any("completion" in event for event in events)
        ):
            raise ContinualLiveError("failed-run journal is not a first-call timeout")
        journal_names = sorted(
            name for name in members if name.startswith(pilot_prefix) and name.endswith("calls.jsonl")
        )
        if journal_names != [required["journal"]]:
            raise ContinualLiveError("failed-run contains calls beyond the first HSWM intent")

        forbidden_score_files = {
            pilot_prefix + name
            for name in (
                "call_ledgers.json",
                "parity_audits.json",
                "removal_restore.json",
                "runs.json",
            )
        }
        if forbidden_score_files & set(members):
            raise ContinualLiveError("failed-run contains score or completed-call artifacts")
        post_reveal = _json_bytes(raw["post_reveal"], "failed-run post-reveal")
        post_reveal_unsigned = {
            key: item for key, item in post_reveal.items()
            if key != "validation_sha256"
        }
        if (
            post_reveal.get("validation_sha256")
            != binding["post_reveal_validation_sha256"]
            or post_reveal.get("validation_sha256")
            != canonical_sha256(post_reveal_unsigned)
            or post_reveal.get("valid") is not False
        ):
            raise ContinualLiveError("failed-run post-reveal record is not invalid/no-score")
        prior_precommit = _json_bytes(raw["precommit"], "failed-run v2 precommit")
        if prior_precommit.get("schema") != "hswm-continual-pilot-precommit/v2":
            raise ContinualLiveError("failed-run does not contain the consumed v2 authority")
        prereg = _json_bytes(raw["prereg"], "failed-run preregistration")
        prereg_unsigned = {
            key: item for key, item in prereg.items() if key != "prereg_sha256"
        }
        if (
            prereg.get("prereg_sha256") != canonical_sha256(prereg_unsigned)
            or prereg.get("prereg_sha256") != binding["preregistration_sha256"]
            or prereg.get("selected_seed_indices") != [0, 1]
            or prereg.get("precommit_artifact_sha256")
            != binding["frozen_v2_precommit_artifact_sha256"]
        ):
            raise ContinualLiveError("failed-run preregistration is not consumed primary v2")
        seed_reveal = _json_bytes(raw["seed_reveal"], "failed-run seed reveal")
        reveal_unsigned = {
            key: item for key, item in seed_reveal.items() if key != "reveal_sha256"
        }
        commitments = list(precommit["commitment_document"]["commitments"])
        used = seed_reveal.get("used_seeds")
        if (
            seed_reveal.get("reveal_sha256") != canonical_sha256(reveal_unsigned)
            or seed_reveal.get("selected_seed_indices") != [0, 1]
            or seed_reveal.get("ordered_seed_commitments") != commitments
            or not isinstance(used, list)
            or len(used) != 2
        ):
            raise ContinualLiveError("failed-run seed reveal does not consume primary only")
        for index, item in enumerate(used):
            if (
                not isinstance(item, dict)
                or item.get("frozen_index") != index
                or not isinstance(item.get("seed_hex"), str)
            ):
                raise ContinualLiveError("failed-run primary seed reveal is malformed")
            try:
                seed = bytes.fromhex(item["seed_hex"])
            except ValueError as error:
                raise ContinualLiveError("failed-run primary seed reveal is malformed") from error
            if len(seed) != 32 or _digest_bytes(seed) != commitments[index]:
                raise ContinualLiveError("failed-run primary seed reveal mismatches commitment")

        service_before = _json_bytes(raw["service_before"], "service before")
        service_after = _json_bytes(raw["service_after"], "service after")
        for phase, service in (("before", service_before), ("after", service_after)):
            if (
                set(service) != {"identity", "identity_sha256", "phase"}
                or service["phase"] != phase
                or service["identity_sha256"]
                != canonical_sha256(service["identity"])
                or service["identity_sha256"] != binding["service_identity_sha256"]
            ):
                raise ContinualLiveError(f"failed-run service {phase} binding is invalid")
        if service_before["identity"] != service_after["identity"]:
            raise ContinualLiveError("failed-run service identity changed during timeout")
        wrapper = _json_bytes(raw["wrapper"], "failed-run wrapper terminal")
        if (
            set(wrapper)
            != {
                "after_capture_exit_code",
                "after_identity_sha256",
                "before_identity_sha256",
                "identity_unchanged",
                "pilot_exit_code",
                "schema",
            }
            or wrapper["schema"] != "hswm-continual-live-ops-wrapper/v1"
            or wrapper["before_identity_sha256"]
            != binding["service_identity_sha256"]
            or wrapper["after_identity_sha256"]
            != binding["service_identity_sha256"]
            or wrapper["identity_unchanged"] is not True
            or wrapper["pilot_exit_code"] != 1
            or wrapper["after_capture_exit_code"] != 0
        ):
            raise ContinualLiveError("failed-run wrapper terminal is invalid")

    return {
        "artifacts_tar_sha256": tar_sha256,
        "completed_model_responses": 0,
        "completed_streams": 0,
        "failed_call_journal_sha256": binding["failed_call_journal_sha256"],
        "failed_primary_binding_sha256": canonical_sha256(binding),
        "failure_class": "mechanical_timeout_before_response",
        "no_score_proof": True,
        "outer_receipt_sha256": receipt_sha256,
        "primary_seed_indices_consumed": [0, 1],
        "reserve_seed_indices_authorized": [2, 3],
        "service_identity_sha256": binding["service_identity_sha256"],
        "terminal_receipt_sha256": binding["terminal_receipt_sha256"],
        "wrapper": wrapper,
    }


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the engineering-only HSWM continual-learning pilot."
    )
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--streams", type=int, default=2)
    parser.add_argument("--seed-file", type=Path, required=True)
    parser.add_argument("--precommit-file", type=Path, required=True)
    parser.add_argument("--failed-run-artifacts-tar", type=Path)
    parser.add_argument("--failed-run-receipt", type=Path)
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
    if precommit["schema"] in {
        "hswm-continual-pilot-precommit/v2",
        "hswm-continual-pilot-recovery-precommit/v3",
    }:
        raise ContinualLiveError(
            "v2 and v3 execution authorities are consumed; all four old seed "
            "commitments are permanently prohibited"
        )
    if args.failed_run_artifacts_tar is None or args.failed_run_receipt is None:
        raise ContinualLiveError(
            "reserve recovery requires the exact failed-run tar and outer receipt"
        )
    frozen_seeds = _read_secret_seeds(args.seed_file)
    commitments = tuple(precommit["commitment_document"]["commitments"])
    if len(frozen_seeds) != 4:
        raise ContinualLiveError("pilot requires exactly 4 frozen seed preimages")
    for index, (seed, commitment) in enumerate(zip(frozen_seeds, commitments, strict=True)):
        if _digest_bytes(seed) != commitment:
            raise ContinualLiveError(f"seed commitment mismatch at frozen index {index}")
    seed_indices = tuple(precommit["selected_seed_indices"])
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
    execution = precommit["recovery_execution"]
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
    failed_primary_validation = _validate_failed_primary_artifacts(
        args.failed_run_artifacts_tar,
        args.failed_run_receipt,
        precommit=precommit,
    )
    _write_bytes_atomic(output / "frozen_precommit.canonical.json", precommit_raw)
    _write_json_atomic(
        output / "failed_primary_validation.json", failed_primary_validation
    )
    prereg = {
        "backend": backend_config.public_identity(),
        "budget": budget.canonical(),
        "container_digest": args.container_digest,
        "engineering_only": True,
        "failed_primary_binding_sha256": failed_primary_validation[
            "failed_primary_binding_sha256"
        ],
        "mode": "engineering-pilot-reserve-recovery-only",
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
                                response_schema = JSONSchemaContract(
                                    name=entry["response_schema_name"],
                                    schema_json=entry["response_schema_json"],
                                    schema_sha256=entry["response_schema_sha256"],
                                )
                                response_schema.validate_instance(
                                    _strict_object(completion["text"])
                                )
                            except (
                                KeyError,
                                TypeError,
                                json.JSONDecodeError,
                                ContinualLiveError,
                            ):
                                preimages_ok = False
                                continue
                            if (
                                _digest_bytes(
                                    completion["raw_request_json"].encode("utf-8")
                                )
                                != completion["request_sha256"]
                                or canonical_json_bytes(raw_request_value).decode(
                                    "utf-8"
                                )
                                != completion["raw_request_json"]
                                or _digest_bytes(
                                    completion["raw_response_json"].encode("utf-8")
                                )
                                != completion["response_sha256"]
                                or _digest_bytes(completion["text"].encode("utf-8"))
                                != completion["text_sha256"]
                                or len(completion["text"].encode("utf-8"))
                                != completion["text_bytes"]
                                or len(completion["text"].encode("utf-8"))
                                != entry["completion_text_bytes"]
                                or len(completion["raw_request_json"].encode("utf-8"))
                                != entry["raw_request_bytes"]
                                or len(entry["request_payload_json"].encode("utf-8"))
                                != entry["request_payload_bytes"]
                                or len(entry["response_schema_json"].encode("utf-8"))
                                != entry["response_schema_bytes"]
                                or len(
                                    canonical_json_bytes(
                                        [
                                            {
                                                "role": "system",
                                                "content": entry["system_message"],
                                            },
                                            {
                                                "role": "user",
                                                "content": entry[
                                                    "request_payload_json"
                                                ],
                                            },
                                        ]
                                    )
                                )
                                != entry["messages_bytes"]
                            ):
                                preimages_ok = False
                                continue
                            try:
                                choices = raw_response_value["choices"]
                                if not isinstance(choices, list) or len(choices) != 1:
                                    raise TypeError("response choice count changed")
                                returned_message = choices[0]["message"]
                                returned_text = returned_message["content"]
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
                                    "response_format",
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
                                or raw_request_value["response_format"]
                                != response_schema.response_format()
                                or backend_identity.get("response_format_mode")
                                != STRUCTURED_OUTPUT_MODE
                                or raw_request_value["chat_template_kwargs"]
                                != {
                                    "enable_thinking": backend_identity.get(
                                        "enable_thinking", False
                                    )
                                }
                                or returned_text != completion["text"]
                                or returned_model != completion["model"]
                                or returned_message.get("reasoning_content")
                                not in (None, "")
                                or returned_message.get("reasoning") not in (None, "")
                                or returned_message.get("refusal") not in (None, "")
                                or returned_message.get("tool_calls") not in (None, [])
                                or returned_message.get("function_call") is not None
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
        checkpointed_sqlite_artifacts = _checkpoint_sqlite_artifacts(output)
        artifact_hashes = _final_artifact_sha256s(output)
        terminal = {
            "artifact_sha256s": artifact_hashes,
            "checkpointed_sqlite_artifacts": list(
                checkpointed_sqlite_artifacts
            ),
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


def _schema_gate_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the four-call public HSWM compact-schema gate. This command has "
            "no seed or evaluation path."
        )
    )
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--container-digest", required=True)
    parser.add_argument("--service-binding", required=True)
    return parser


def schema_gate_main(argv: Sequence[str] | None = None) -> int:
    """CLI for the public gate; deliberately cannot accept or derive seed material."""

    args = _schema_gate_cli_parser().parse_args(argv)
    if args.timeout != 600.0:
        raise ContinualLiveError("public schema gate timeout is frozen at 600 seconds")
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_revision):
        raise ContinualLiveError("source_revision must be a 40-hex Git revision")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.container_digest):
        raise ContinualLiveError("container_digest must be sha256:<64 hex>")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", args.service_binding):
        raise ContinualLiveError("service_binding must be sha256:<64 hex>")
    output = args.output_dir
    if output.exists() and any(output.iterdir()):
        raise ContinualLiveError("schema gate output must be absent or empty; no resume")
    output.mkdir(parents=True, exist_ok=True)
    backend_config = OpenAIBackendConfig(
        endpoint=args.endpoint,
        model=args.model,
        api_key=os.environ.get(args.api_key_env),
        timeout_seconds=args.timeout,
    )
    fixture = public_schema_gate_fixture()
    _write_json_atomic(output / "public_fixture.json", fixture)
    prereg = {
        "adapter_schema": COMPACT_PATCH_SCHEMA,
        "answer_max_tokens": 128,
        "backend": backend_config.public_identity(),
        "call_budget": 4,
        "container_digest": args.container_digest,
        "denylisted_from_evaluation": True,
        "fixture_sha256": fixture["fixture_sha256"],
        "indexed_authoring_view_schema": INDEXED_AUTHORING_VIEW_SCHEMA,
        "max_input_bytes": 2_000_000,
        "max_state_bytes": 1_000_000,
        "max_update_input_tokens": PUBLIC_SCHEMA_GATE_MAX_UPDATE_INPUT_TOKENS,
        "mutation_expressivity": MUTATION_EXPRESSIVITY,
        "no_precommit_or_seed_path": True,
        "output_token_ceiling": PUBLIC_SCHEMA_GATE_OUTPUT_TOKEN_CEILING,
        "protocol": PUBLIC_SCHEMA_GATE_PROTOCOL,
        "provider_context_window_tokens": PUBLIC_SCHEMA_GATE_CONTEXT_WINDOW_TOKENS,
        "retry_limit": 0,
        "service_binding": args.service_binding,
        "source_revision": args.source_revision,
        "structured_output_backend": "provider-auto-not-attested",
        "structured_output_mode": STRUCTURED_OUTPUT_MODE,
        "update_max_tokens": PUBLIC_SCHEMA_GATE_OUTPUT_TOKEN_CEILING,
    }
    prereg["prereg_sha256"] = canonical_sha256(prereg)
    _write_json_atomic(output / "gate_preregistration.json", prereg)
    status: dict[str, Any] = {"error": None, "status": "running"}
    try:
        result = run_public_schema_gate(
            backend_factory=lambda: OpenAICompatibleBackend(backend_config),
            state_dir=output / "state",
        )
        _write_json_atomic(output / "gate_result.json", result)
        status["status"] = "success"
    except BaseException as error:
        status["status"] = "failed"
        status["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        _write_json_atomic(output / "status.json", status)
        checkpointed_sqlite_artifacts = _checkpoint_sqlite_artifacts(output)
        artifact_hashes = _final_artifact_sha256s(output)
        terminal = {
            "artifact_sha256s": artifact_hashes,
            "calls_expected": 4,
            "checkpointed_sqlite_artifacts": list(
                checkpointed_sqlite_artifacts
            ),
            "denylisted_from_evaluation": True,
            "error": status["error"],
            "no_precommit_or_seed_path": True,
            "protocol": PUBLIC_SCHEMA_GATE_PROTOCOL,
            "schema_gate_passed": status["status"] == "success",
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
    "COMPACT_PATCH_SCHEMA",
    "ContinualLiveError",
    "GENESIS",
    "JSONSchemaContract",
    "LIVE_PROTOCOL",
    "ModelCompletion",
    "NoWriteArm",
    "OpenAIBackendConfig",
    "OpenAICompatibleBackend",
    "ParityAudit",
    "PlainTextArm",
    "PUBLIC_SCHEMA_GATE_PROTOCOL",
    "RemovalRestoreResult",
    "ResetArm",
    "SnapshotCheckpoint",
    "StateTransitionReceipt",
    "StructuredHSWMArm",
    "STRUCTURED_OUTPUT_MODE",
    "audit_parity",
    "build_four_arms",
    "main",
    "make_sealed_probe_pack",
    "public_schema_gate_fixture",
    "run_four_arm_stream",
    "run_public_schema_gate",
    "run_removal_restore_probes",
    "sealed_probe_pack_sha256",
    "schema_gate_main",
]


if __name__ == "__main__":
    raise SystemExit(main())
