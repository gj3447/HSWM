"""One-shot, stateless B0 action calls for the ALFWorld text calibration.

This is deliberately not an agent loop.  It neither retains prior observations
nor reads or writes a memory, lesson, retrieval, or environment state.  The
caller supplies the bounded visible transcript of one current episode and
receives one strictly validated action together with a compact audit receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from threading import Lock
from typing import Any, Mapping

from hswm.selfmod.contracts import canonical_json_bytes

from .continual_live import (
    ContinualLiveError,
    JSONSchemaContract,
    OpenAIBackendConfig,
    OpenAICompatibleBackend,
    STRUCTURED_OUTPUT_MODE,
    TOKEN_PREFLIGHT_MODE,
    _prepare_chat_request,
    _prepare_tokenize_request,
    canonical_sha256,
)


B0_ACTION_PROTOCOL = "hswm-alfworld-b0-action/v1"
B0_ACTION_RECEIPT_SCHEMA = "hswm-alfworld-b0-action-receipt/v1"
B0_ACTION_MAX_OUTPUT_TOKENS = 64
B0_ACTION_MAX_BYTES = 512
B0_ACTION_MAX_INPUT_BYTES = 128 * 1024
B0_ACTION_MAX_REQUEST_BYTES = 256 * 1024
B0_ACTION_MAX_HISTORY_STEPS = 20
B0_ACTION_MAX_OBSERVATION_BYTES = 32 * 1024
B0_MAX_TOKENIZE_CALLS = 240
B0_MAX_COMPLETION_CALLS = 240

# This instruction is intentionally constant.  The episode-specific material
# belongs exclusively in the one canonical user object below.
B0_ACTION_SYSTEM_MESSAGE = (
    "You control one ALFWorld text game. Using only the current episode transcript and current observation, return exactly one JSON object whose action value is the next literal environment command. Do not output reasoning, commentary, multiple commands, tools, memories, lessons, outcomes, admissible-command lists, or state changes."
)


class ALFWorldB0ActorError(ContinualLiveError):
    """The isolated B0 action contract failed closed."""


class B0RequestGate:
    """Consume each permitted HTTP POST before transport, including failures."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._tokenize_calls = 0
        self._completion_calls = 0
        self._sealed = False

    def reserve(self, kind: str) -> int:
        with self._lock:
            if self._sealed:
                raise ALFWorldB0ActorError("B0 request gate is sealed")
            if kind == "tokenize":
                if self._tokenize_calls >= B0_MAX_TOKENIZE_CALLS:
                    raise ALFWorldB0ActorError("B0 tokenize request cap exhausted")
                self._tokenize_calls += 1
                return self._tokenize_calls
            if kind == "completion":
                if self._completion_calls >= B0_MAX_COMPLETION_CALLS:
                    raise ALFWorldB0ActorError("B0 completion request cap exhausted")
                self._completion_calls += 1
                return self._completion_calls
            raise ALFWorldB0ActorError("unknown B0 request kind")

    def counts(self) -> tuple[int, int]:
        with self._lock:
            return self._tokenize_calls, self._completion_calls

    def seal(self) -> tuple[int, int]:
        with self._lock:
            self._sealed = True
            return self._tokenize_calls, self._completion_calls


def _digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def _strict_object(raw: str) -> dict[str, Any]:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ALFWorldB0ActorError("action response has a duplicate JSON key")
            value[key] = item
        return value

    try:
        value = json.loads(raw, object_pairs_hook=no_duplicates)
    except json.JSONDecodeError as error:
        raise ALFWorldB0ActorError("action response is not JSON") from error
    if not isinstance(value, dict):
        raise ALFWorldB0ActorError("action response must be one JSON object")
    return value


def _bounded_identifier(label: str, value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,256}", value):
        raise ALFWorldB0ActorError(f"{label} is not a bounded opaque identifier")


def _bounded_observation(label: str, value: str) -> None:
    if (
        not isinstance(value, str)
        or len(value.encode("utf-8")) > B0_ACTION_MAX_OBSERVATION_BYTES
        or "\r" in value
        or any(not (char == "\n" or 0x20 <= ord(char) <= 0x7E) for char in value)
    ):
        raise ALFWorldB0ActorError(
            f"{label} must be bounded printable ASCII text with optional LF"
        )


def _action_schema() -> JSONSchemaContract:
    return JSONSchemaContract.make(
        "alfworld_b0_action",
        {
            "additionalProperties": False,
            "properties": {
                "action": {"maxLength": B0_ACTION_MAX_BYTES, "minLength": 1, "type": "string"}
            },
            "required": ["action"],
            "type": "object",
        },
    )


@dataclass(frozen=True, slots=True)
class B0ActionBudget:
    """Bounds for a single request; the actor has no cross-call state."""

    max_input_bytes: int = B0_ACTION_MAX_REQUEST_BYTES

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_input_bytes, bool)
            or not isinstance(self.max_input_bytes, int)
            or not 1 <= self.max_input_bytes <= B0_ACTION_MAX_REQUEST_BYTES
        ):
            raise ValueError("max_input_bytes must be a bounded positive integer")


@dataclass(frozen=True, slots=True)
class B0ActionReceipt:
    """Compact evidence only; it intentionally contains no observation/history."""

    action: str
    action_sha256: str
    completion_latency_ms: int
    completion_call_index: int
    completion_request_sha256: str
    completion_response_sha256: str
    episode_uid: str
    input_tokens: int
    model: str
    output_tokens: int
    protocol: str
    receipt_sha256: str
    response_schema_sha256: str
    schema: str
    step_index: int
    completion_call_count: int
    tokenize_call_count: int
    tokenize_call_index: int
    token_preflight_token_count: int
    token_preflight_latency_ms: int
    token_preflight_receipt_sha256: str
    token_preflight_request_sha256: str
    token_preflight_response_sha256: str
    usage_reported: bool

    def unsigned(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "action_sha256": self.action_sha256,
            "completion_latency_ms": self.completion_latency_ms,
            "completion_call_index": self.completion_call_index,
            "completion_request_sha256": self.completion_request_sha256,
            "completion_response_sha256": self.completion_response_sha256,
            "episode_uid": self.episode_uid,
            "input_tokens": self.input_tokens,
            "model": self.model,
            "output_tokens": self.output_tokens,
            "protocol": self.protocol,
            "response_schema_sha256": self.response_schema_sha256,
            "schema": self.schema,
            "step_index": self.step_index,
            "completion_call_count": self.completion_call_count,
            "tokenize_call_count": self.tokenize_call_count,
            "tokenize_call_index": self.tokenize_call_index,
            "token_preflight_token_count": self.token_preflight_token_count,
            "token_preflight_latency_ms": self.token_preflight_latency_ms,
            "token_preflight_receipt_sha256": self.token_preflight_receipt_sha256,
            "token_preflight_request_sha256": self.token_preflight_request_sha256,
            "token_preflight_response_sha256": self.token_preflight_response_sha256,
            "usage_reported": self.usage_reported,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


class ALFWorldB0Actor:
    """A stateless, single-action OpenAI-compatible caller."""

    def __init__(
        self,
        backend: OpenAICompatibleBackend,
        *,
        budget: B0ActionBudget | None = None,
        request_gate: B0RequestGate | None = None,
    ) -> None:
        self._backend = backend
        self._budget = budget or B0ActionBudget()
        self._request_gate = request_gate or B0RequestGate()
        identity = backend.identity
        if (
            identity.get("enable_thinking") is not False
            or identity.get("temperature") != 0.0
            or identity.get("top_p") != 1.0
            or identity.get("seed") != 0
            or identity.get("token_preflight_mode") != TOKEN_PREFLIGHT_MODE
            or identity.get("response_format_mode") != STRUCTURED_OUTPUT_MODE
            or not isinstance(identity.get("model"), str)
            or not identity["model"]
        ):
            raise ALFWorldB0ActorError("backend does not meet the frozen B0 contract")

    @classmethod
    def from_config(
        cls,
        config: OpenAIBackendConfig,
        *,
        budget: B0ActionBudget | None = None,
        request_gate: B0RequestGate | None = None,
    ) -> "ALFWorldB0Actor":
        """Bind this actor to the repository's no-retry transport."""

        return cls(
            OpenAICompatibleBackend(config),
            budget=budget,
            request_gate=request_gate,
        )

    @property
    def request_counts(self) -> tuple[int, int]:
        """Return issued tokenize/completion POST counts for occurrence sealing."""

        return self._request_gate.counts()

    def seal(self) -> tuple[int, int]:
        """Forbid any later POST and return the final issued-call counts."""

        return self._request_gate.seal()

    @property
    def response_schema(self) -> JSONSchemaContract:
        return _action_schema()

    def act(
        self,
        *,
        episode_uid: str,
        step_index: int,
        history: tuple[Mapping[str, str], ...] | list[Mapping[str, str]],
        observation: str,
    ) -> B0ActionReceipt:
        _bounded_identifier("episode_uid", episode_uid)
        if (
            isinstance(step_index, bool)
            or not isinstance(step_index, int)
            or not 0 <= step_index < B0_ACTION_MAX_HISTORY_STEPS
        ):
            raise ALFWorldB0ActorError("step_index must identify one of the 20 permitted actions")
        _bounded_observation("observation", observation)
        if not isinstance(history, (tuple, list)) or len(history) != step_index:
            raise ALFWorldB0ActorError("history must contain exactly one prior pair per step")
        if len(history) > B0_ACTION_MAX_HISTORY_STEPS:
            raise ALFWorldB0ActorError("history exceeds the B0 within-episode bound")
        normalized_history: list[dict[str, str]] = []
        for index, item in enumerate(history):
            if not isinstance(item, Mapping) or set(item) != {"observation", "action"}:
                raise ALFWorldB0ActorError("history entries must be exact observation/action pairs")
            prior_observation = item["observation"]
            prior_action = item["action"]
            _bounded_observation(f"history observation {index}", prior_observation)
            if not isinstance(prior_action, str):
                raise ALFWorldB0ActorError("history actions must be text")
            if (
                not 1 <= len(prior_action.encode("utf-8")) <= B0_ACTION_MAX_BYTES
                or any(not 0x20 <= ord(char) <= 0x7E for char in prior_action)
            ):
                raise ALFWorldB0ActorError(f"history action {index} is not bounded printable ASCII")
            normalized_history.append({"observation": prior_observation, "action": prior_action})

        user_content = canonical_json_bytes(
            {
                "episode_uid": episode_uid,
                "history": normalized_history,
                "observation": observation,
                "protocol": B0_ACTION_PROTOCOL,
                "step_index": step_index,
            }
        ).decode("utf-8")
        if len(user_content.encode("utf-8")) > B0_ACTION_MAX_INPUT_BYTES:
            raise ALFWorldB0ActorError("B0 canonical payload exceeds its byte bound")
        messages = (
            {"role": "system", "content": B0_ACTION_SYSTEM_MESSAGE},
            {"role": "user", "content": user_content},
        )
        schema = self.response_schema
        raw_request = _prepare_chat_request(
            backend_identity=self._backend.identity,
            messages=messages,
            max_output_tokens=B0_ACTION_MAX_OUTPUT_TOKENS,
            response_schema=schema,
        )
        if len(raw_request) > self._budget.max_input_bytes:
            raise ALFWorldB0ActorError("B0 action request exceeds input byte budget")
        request_sha256 = _digest(raw_request)
        request_id = f"alfworld-b0-{request_sha256[:32]}"
        raw_tokenize = _prepare_tokenize_request(
            backend_identity=self._backend.identity, raw_chat_request=raw_request
        )
        token_observations = 0

        def observe_tokenize(request: bytes, response: bytes, status: int | None, complete: bool) -> None:
            nonlocal token_observations
            token_observations += 1
            if request != raw_tokenize:
                raise ALFWorldB0ActorError("tokenize observer saw a different request")
            del response, status, complete

        tokenize_call_index = self._request_gate.reserve("tokenize")
        preflight = self._backend.tokenize(
            raw_request=raw_tokenize,
            source_chat_request_sha256=request_sha256,
            max_output_tokens=B0_ACTION_MAX_OUTPUT_TOKENS,
            request_id=request_id,
            response_observer=observe_tokenize,
        )
        identity = self._backend.identity
        expected_context = identity.get("expected_max_model_len")
        if (
            token_observations != 1
            or preflight.model != identity["model"]
            or preflight.source_chat_request_sha256 != request_sha256
            or preflight.max_output_tokens != B0_ACTION_MAX_OUTPUT_TOKENS
            or preflight.max_model_len != expected_context
            or preflight.count + B0_ACTION_MAX_OUTPUT_TOKENS > preflight.max_model_len
        ):
            raise ALFWorldB0ActorError("token preflight does not bound this B0 action")

        completion_observations = 0

        def observe_completion(request: bytes, response: bytes) -> None:
            nonlocal completion_observations
            completion_observations += 1
            if request != raw_request:
                raise ALFWorldB0ActorError("completion observer saw a different request")
            del response

        completion_call_index = self._request_gate.reserve("completion")
        completion = self._backend.complete(
            raw_request=raw_request,
            request_id=request_id,
            response_observer=observe_completion,
        )
        if completion_observations != 1 or completion.model != identity["model"]:
            raise ALFWorldB0ActorError("completion model does not match the backend identity")
        value = _strict_object(completion.text)
        try:
            schema.validate_instance(value)
            action = value["action"]
        except ContinualLiveError as error:
            raise ALFWorldB0ActorError("action response violates the strict schema") from error
        if (
            not isinstance(action, str)
            or not 1 <= len(action.encode("utf-8")) <= B0_ACTION_MAX_BYTES
            or any(not 0x20 <= ord(char) <= 0x7E for char in action)
            or "\r" in action
            or "\n" in action
        ):
            raise ALFWorldB0ActorError("action must be printable ASCII without line breaks")
        unsigned = {
            "action": action,
            "action_sha256": _digest(action.encode("ascii")),
            "completion_call_index": completion_call_index,
            "completion_latency_ms": completion.latency_ms,
            "completion_request_sha256": completion.request_sha256,
            "completion_response_sha256": completion.response_sha256,
            "episode_uid": episode_uid,
            "input_tokens": completion.input_tokens,
            "model": completion.model,
            "output_tokens": completion.output_tokens,
            "protocol": B0_ACTION_PROTOCOL,
            "response_schema_sha256": schema.schema_sha256,
            "schema": B0_ACTION_RECEIPT_SCHEMA,
            "step_index": step_index,
            "completion_call_count": 1,
            "tokenize_call_count": 1,
            "tokenize_call_index": tokenize_call_index,
            "token_preflight_token_count": preflight.count,
            "token_preflight_latency_ms": preflight.latency_ms,
            "token_preflight_receipt_sha256": preflight.receipt_sha256,
            "token_preflight_request_sha256": preflight.request_sha256,
            "token_preflight_response_sha256": preflight.response_sha256,
            "usage_reported": completion.usage_reported,
        }
        return B0ActionReceipt(
            **unsigned,
            receipt_sha256=canonical_sha256(unsigned),
        )
