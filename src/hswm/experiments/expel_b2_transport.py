"""One-shot OpenAI-compatible transport for the prospective B2 text baseline.

The transport is deliberately an external lesson-baseline adapter.  It neither
executes ALFWorld, chooses tasks, admits HSWM state, nor interprets a result.
Every POST is reserved before transport so failed and preflight-only requests
remain observable to the enclosing prospective runner.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from threading import Lock
import time
from typing import Any, Callable, Mapping, Sequence

from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256

from .alfworld_b0_actor import (
    B0_ACTION_MAX_BYTES,
    B0_ACTION_MAX_HISTORY_STEPS,
    B0_ACTION_MAX_OUTPUT_TOKENS,
    B0_ACTION_MAX_REQUEST_BYTES,
    _action_schema,
    _bounded_identifier,
    _bounded_observation,
    _strict_object,
)
from .continual_live import (
    ContinualLiveError,
    JSONSchemaContract,
    ModelCompletion,
    OpenAICompatibleBackend,
    STRUCTURED_OUTPUT_MODE,
    TOKEN_PREFLIGHT_MODE,
    TokenPreflightReceipt,
    _prepare_chat_request,
    _prepare_tokenize_request,
)
from .expel_b2_text_lesson import (
    ARM_ID,
    CLAIM_BOUNDARY,
    MAX_LESSON_UTF8_BYTES,
    REFLECTION_PROMPT_UTF8,
    build_action_messages,
    normalize_rule,
)


TRANSPORT_SCHEMA = "hswm-expel-b2-transport/v1"
ACTION_RECEIPT_SCHEMA = "hswm-expel-b2-action-receipt/v1"
REFLECTION_RECEIPT_SCHEMA = "hswm-expel-b2-reflection-receipt/v1"
# Every phase has the same combined occurrence budget: 240 action posts plus
# at most eight reflection posts.  A failed/preflight-only post consumes its
# arm allocation and cannot be shifted between kinds.
MAX_ACTION_POSTS = 240
MAX_REFLECTION_POSTS = 8
REFLECTION_MAX_OUTPUT_TOKENS = 128
MAX_SEALED_TRAJECTORY_BYTES = 64 * 1024
MAX_REQUEST_TIMEOUT_SECONDS = 120.0


class ExpelB2TransportError(ContinualLiveError):
    """The prospective B2 transport contract failed closed."""


def _sha(value: bytes) -> str:
    return sha256(value).hexdigest()


def _reflection_schema() -> JSONSchemaContract:
    return JSONSchemaContract.make(
        "hswm_expel_b2_reflection",
        {
            "additionalProperties": False,
            "properties": {"rule": {"maxLength": 512, "minLength": 1, "type": "string"}},
            "required": ["rule"],
            "type": "object",
        },
    )


def _strict_json(raw: str, *, label: str) -> dict[str, Any]:
    try:
        return _strict_object(raw)
    except ContinualLiveError as error:
        raise ExpelB2TransportError(f"{label} response is not one strict JSON object") from error


def _require_digest(label: str, value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ExpelB2TransportError(f"{label} must be a lowercase SHA-256")
    return value


def _require_deadline(deadline: float | None) -> None:
    if deadline is not None and (isinstance(deadline, bool) or not isinstance(deadline, (int, float)) or not math.isfinite(deadline)):
        raise ExpelB2TransportError("deadline must be finite monotonic time")


def _validate_history(history: Sequence[Mapping[str, str]], *, step_index: int) -> None:
    if isinstance(step_index, bool) or not isinstance(step_index, int) or not 0 <= step_index < B0_ACTION_MAX_HISTORY_STEPS:
        raise ExpelB2TransportError("step index exceeds the ALFWorld action horizon")
    if not isinstance(history, (tuple, list)) or len(history) != step_index:
        raise ExpelB2TransportError("history must contain exactly one prior pair per step")
    for index, item in enumerate(history):
        if not isinstance(item, Mapping) or set(item) != {"observation", "action"}:
            raise ExpelB2TransportError("history entries must be exact observation/action pairs")
        _bounded_observation(f"history observation {index}", item["observation"])
        action = item["action"]
        if (not isinstance(action, str) or not 1 <= len(action.encode("utf-8")) <= B0_ACTION_MAX_BYTES
                or "\n" in action or "\r" in action or any(not 0x20 <= ord(char) <= 0x7E for char in action)):
            raise ExpelB2TransportError("history action is not one bounded printable ASCII line")


@dataclass(frozen=True, slots=True)
class RequestEvent:
    operation: str
    phase: str
    index: int
    request_sha256: str
    response_sha256: str | None
    http_status: int | None
    response_complete: bool | None
    input_tokens: int | None
    output_tokens: int | None
    usage_reported: bool | None
    outcome: str

    def canonical(self) -> dict[str, Any]:
        return {
            "operation": self.operation, "phase": self.phase, "index": self.index,
            "request_sha256": self.request_sha256, "response_sha256": self.response_sha256,
            "http_status": self.http_status, "response_complete": self.response_complete,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "usage_reported": self.usage_reported,
            "outcome": self.outcome,
        }


class ExpelB2RequestGate:
    """Reserve action/reflection tokenizer and completion requests independently."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counts = {(operation, phase): 0 for operation in ("action", "reflection") for phase in ("tokenize", "completion")}
        self._sealed = False

    def reserve(self, *, operation: str, phase: str) -> int:
        if operation not in {"action", "reflection"} or phase not in {"tokenize", "completion"}:
            raise ExpelB2TransportError("unknown B2 request operation or phase")
        cap = MAX_ACTION_POSTS if operation == "action" else MAX_REFLECTION_POSTS
        with self._lock:
            if self._sealed:
                raise ExpelB2TransportError("B2 request gate is sealed")
            key = (operation, phase)
            if self._counts[key] >= cap:
                raise ExpelB2TransportError(f"B2 {operation} {phase} cap exhausted")
            self._counts[key] += 1
            return self._counts[key]

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {f"{operation}_{phase}": self._counts[(operation, phase)] for operation in ("action", "reflection") for phase in ("tokenize", "completion")}

    def seal(self) -> dict[str, int]:
        with self._lock:
            self._sealed = True
            return {f"{operation}_{phase}": self._counts[(operation, phase)] for operation in ("action", "reflection") for phase in ("tokenize", "completion")}


@dataclass(frozen=True, slots=True)
class B2ActionReceipt:
    action: str
    episode_uid: str
    step_index: int
    lesson_sha256: str
    token_preflight: TokenPreflightReceipt
    completion: ModelCompletion
    action_tokenize_index: int
    action_completion_index: int
    receipt_sha256: str

    def unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": ACTION_RECEIPT_SCHEMA, "arm_id": ARM_ID,
            "claim_boundary": CLAIM_BOUNDARY, "action": self.action,
            "action_sha256": _sha(self.action.encode("ascii")), "episode_uid": self.episode_uid,
            "step_index": self.step_index, "lesson_sha256": self.lesson_sha256,
            "response_schema_sha256": _action_schema().schema_sha256,
            "token_preflight_receipt_sha256": self.token_preflight.receipt_sha256,
            "token_preflight_input_tokens": self.token_preflight.count,
            "input_tokens": self.completion.input_tokens, "output_tokens": self.completion.output_tokens,
            "usage_reported": self.completion.usage_reported, "model": self.completion.model,
            "completion_request_sha256": self.completion.request_sha256,
            "completion_response_sha256": self.completion.response_sha256,
            "action_tokenize_index": self.action_tokenize_index,
            "action_completion_index": self.action_completion_index,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class B2ReflectionReceipt:
    episode_uid: str
    terminal_seal_sha256: str
    trajectory_sha256: str
    rule_utf8: str
    token_preflight: TokenPreflightReceipt
    completion: ModelCompletion
    reflection_tokenize_index: int
    reflection_completion_index: int
    receipt_sha256: str

    def unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": REFLECTION_RECEIPT_SCHEMA, "arm_id": ARM_ID,
            "claim_boundary": CLAIM_BOUNDARY, "episode_uid": self.episode_uid,
            "terminal_seal_sha256": self.terminal_seal_sha256, "trajectory_sha256": self.trajectory_sha256,
            "rule_utf8": self.rule_utf8, "rule_sha256": _sha(self.rule_utf8.encode("ascii")),
            "response_schema_sha256": _reflection_schema().schema_sha256,
            "token_preflight_receipt_sha256": self.token_preflight.receipt_sha256,
            "token_preflight_input_tokens": self.token_preflight.count,
            "input_tokens": self.completion.input_tokens, "output_tokens": self.completion.output_tokens,
            "usage_reported": self.completion.usage_reported, "model": self.completion.model,
            "completion_request_sha256": self.completion.request_sha256,
            "completion_response_sha256": self.completion.response_sha256,
            "reflection_tokenize_index": self.reflection_tokenize_index,
            "reflection_completion_index": self.reflection_completion_index,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


class ExpelB2Transport:
    """No-retry B2 model transport; caller owns environment and lesson admission."""

    def __init__(
        self,
        backend: OpenAICompatibleBackend,
        *,
        gate: ExpelB2RequestGate | None = None,
        event_sink: Callable[[RequestEvent], None] | None = None,
    ) -> None:
        identity = backend.identity
        if (identity.get("enable_thinking") is not False or identity.get("temperature") != 0.0
                or identity.get("top_p") != 1.0 or identity.get("seed") != 0
                or identity.get("token_preflight_mode") != TOKEN_PREFLIGHT_MODE
                or identity.get("response_format_mode") != STRUCTURED_OUTPUT_MODE
                or not isinstance(identity.get("model"), str) or not identity["model"]
                or isinstance(identity.get("timeout_seconds"), bool)
                or not isinstance(identity.get("timeout_seconds"), (int, float))
                or not math.isfinite(identity["timeout_seconds"])
                or not 0 < identity["timeout_seconds"] <= MAX_REQUEST_TIMEOUT_SECONDS):
            raise ExpelB2TransportError("backend does not meet the frozen B2 transport contract")
        self._backend = backend
        self._gate = gate or ExpelB2RequestGate()
        self._events: list[RequestEvent] = []
        self._event_sink = event_sink

    @property
    def events(self) -> tuple[RequestEvent, ...]:
        return tuple(self._events)

    @property
    def request_counts(self) -> dict[str, int]:
        return self._gate.counts()

    def seal(self) -> dict[str, int]:
        return self._gate.seal()

    def _before_post(self, deadline: float | None, monotonic: Callable[[], float]) -> None:
        if deadline is not None:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise ExpelB2TransportError("occurrence wall-time ceiling reached before POST")
            if remaining < self._backend.identity["timeout_seconds"]:
                raise ExpelB2TransportError("remaining occurrence wall time cannot cover the frozen request timeout")

    def _record_event(self, event: RequestEvent, *, replace_index: int | None = None) -> int:
        """Persist an event synchronously; reservation delivery precedes every POST.

        The sink belongs to the occurrence runner.  It may durably append the
        canonical event before this method returns.  A sink failure therefore
        prevents the associated network call.
        """
        if replace_index is None:
            self._events.append(event)
            index = len(self._events) - 1
        else:
            self._events[replace_index] = event
            index = replace_index
        if self._event_sink is not None:
            self._event_sink(event)
        return index

    def _tokenize(self, *, operation: str, raw_chat: bytes, request_id: str, max_output_tokens: int, deadline: float | None, monotonic: Callable[[], float]) -> tuple[int, TokenPreflightReceipt]:
        raw_tokenize = _prepare_tokenize_request(backend_identity=self._backend.identity, raw_chat_request=raw_chat)
        self._before_post(deadline, monotonic)
        index = self._gate.reserve(operation=operation, phase="tokenize")
        event_index = self._record_event(
            RequestEvent(operation, "tokenize", index, _sha(raw_tokenize), None, None, None, None, None, None, "ISSUED_UNKNOWN")
        )

        observations = 0

        def observe(request: bytes, response: bytes, status: int | None, complete: bool) -> None:
            nonlocal observations
            observations += 1
            if request != raw_tokenize:
                raise ExpelB2TransportError("tokenize observer saw another request")
            self._record_event(
                RequestEvent(operation, "tokenize", index, _sha(request), _sha(response), status, complete, None, None, None, "OBSERVED"),
                replace_index=event_index,
            )

        try:
            receipt = self._backend.tokenize(raw_request=raw_tokenize, source_chat_request_sha256=_sha(raw_chat), max_output_tokens=max_output_tokens, request_id=request_id, response_observer=observe)
        except Exception:
            if self._events[event_index].outcome == "ISSUED_UNKNOWN":
                prior = self._events[event_index]
                self._record_event(RequestEvent(
                    prior.operation, prior.phase, prior.index, prior.request_sha256,
                    prior.response_sha256, prior.http_status, prior.response_complete,
                    prior.input_tokens, prior.output_tokens, prior.usage_reported, "FAILED",
                ), replace_index=event_index)
            raise
        expected_context = self._backend.identity.get("expected_max_model_len")
        if (observations != 1 or receipt.model != self._backend.identity["model"]
                or receipt.source_chat_request_sha256 != _sha(raw_chat)
                or receipt.max_output_tokens != max_output_tokens
                or receipt.max_model_len != expected_context
                or receipt.count + max_output_tokens > receipt.max_model_len):
            raise ExpelB2TransportError("token preflight does not bind this request")
        prior = self._events[event_index]
        self._record_event(RequestEvent(
            prior.operation, prior.phase, prior.index, prior.request_sha256,
            prior.response_sha256, prior.http_status, prior.response_complete,
            receipt.count, 0, False, prior.outcome,
        ), replace_index=event_index)
        return index, receipt

    def _complete(self, *, operation: str, raw_chat: bytes, request_id: str, deadline: float | None, monotonic: Callable[[], float]) -> tuple[int, ModelCompletion]:
        self._before_post(deadline, monotonic)
        index = self._gate.reserve(operation=operation, phase="completion")
        event_index = self._record_event(
            RequestEvent(operation, "completion", index, _sha(raw_chat), None, None, None, None, None, None, "ISSUED_UNKNOWN")
        )

        observations = 0

        def observe(request: bytes, response: bytes) -> None:
            nonlocal observations
            observations += 1
            if request != raw_chat:
                raise ExpelB2TransportError("completion observer saw another request")
            self._record_event(
                RequestEvent(operation, "completion", index, _sha(request), _sha(response), None, True, None, None, None, "OBSERVED"),
                replace_index=event_index,
            )

        try:
            completion = self._backend.complete(raw_request=raw_chat, request_id=request_id, response_observer=observe)
        except Exception:
            if self._events[event_index].outcome == "ISSUED_UNKNOWN":
                prior = self._events[event_index]
                self._record_event(RequestEvent(
                    prior.operation, prior.phase, prior.index, prior.request_sha256,
                    prior.response_sha256, prior.http_status, prior.response_complete,
                    prior.input_tokens, prior.output_tokens, prior.usage_reported, "FAILED",
                ), replace_index=event_index)
            raise
        if observations != 1 or completion.model != self._backend.identity["model"]:
            raise ExpelB2TransportError("completion model does not match backend identity")
        prior = self._events[event_index]
        self._record_event(RequestEvent(
            prior.operation, prior.phase, prior.index, prior.request_sha256,
            prior.response_sha256, prior.http_status, prior.response_complete,
            (completion.input_tokens if completion.usage_reported else None),
            (completion.output_tokens if completion.usage_reported else None),
            completion.usage_reported, prior.outcome,
        ), replace_index=event_index)
        return index, completion

    def act(self, *, lesson_utf8: str, episode_uid: str, step_index: int, history: Sequence[Mapping[str, str]], observation: str, deadline: float | None = None, monotonic: Callable[[], float] = time.monotonic) -> B2ActionReceipt:
        _require_deadline(deadline)
        if not isinstance(lesson_utf8, str) or len(lesson_utf8.encode("utf-8")) > MAX_LESSON_UTF8_BYTES:
            raise ExpelB2TransportError("lesson exceeds the frozen B2 byte cap")
        _bounded_identifier("episode_uid", episode_uid)
        _bounded_observation("observation", observation)
        _validate_history(history, step_index=step_index)
        messages = build_action_messages(lesson_utf8=lesson_utf8, episode_uid=episode_uid, step_index=step_index, history=history, observation=observation)
        schema = _action_schema()
        raw = _prepare_chat_request(backend_identity=self._backend.identity, messages=messages, max_output_tokens=B0_ACTION_MAX_OUTPUT_TOKENS, response_schema=schema)
        if len(raw) > B0_ACTION_MAX_REQUEST_BYTES:
            raise ExpelB2TransportError("action request exceeds the frozen B0 input byte cap")
        request_id = f"hswm-b2-action-{_sha(raw)[:32]}"
        tokenize_index, preflight = self._tokenize(operation="action", raw_chat=raw, request_id=request_id, max_output_tokens=B0_ACTION_MAX_OUTPUT_TOKENS, deadline=deadline, monotonic=monotonic)
        completion_index, completion = self._complete(operation="action", raw_chat=raw, request_id=request_id, deadline=deadline, monotonic=monotonic)
        value = _strict_json(completion.text, label="action")
        try:
            schema.validate_instance(value)
        except ContinualLiveError as error:
            raise ExpelB2TransportError("action response violates strict schema") from error
        action = value["action"]
        if not isinstance(action, str) or not action or "\n" in action or "\r" in action or any(not 0x20 <= ord(char) <= 0x7E for char in action):
            raise ExpelB2TransportError("action must be one printable ASCII line")
        unsigned = B2ActionReceipt(action, episode_uid, step_index, _sha(lesson_utf8.encode()), preflight, completion, tokenize_index, completion_index, "").unsigned()
        return B2ActionReceipt(action, episode_uid, step_index, _sha(lesson_utf8.encode()), preflight, completion, tokenize_index, completion_index, canonical_sha256(unsigned))

    def reflect_success(self, *, sealed_success: Mapping[str, object], deadline: float | None = None, monotonic: Callable[[], float] = time.monotonic) -> B2ReflectionReceipt:
        _require_deadline(deadline)
        required = {"episode_uid", "terminal_seal_sha256", "trajectory_sha256", "visible_trajectory_utf8"}
        if set(sealed_success) != required:
            raise ExpelB2TransportError("sealed-success payload fields drifted")
        episode_uid = sealed_success["episode_uid"]
        if not isinstance(episode_uid, str):
            raise ExpelB2TransportError("sealed-success episode UID is invalid")
        _bounded_identifier("episode_uid", episode_uid)
        terminal = _require_digest("terminal_seal_sha256", sealed_success["terminal_seal_sha256"])
        trajectory = _require_digest("trajectory_sha256", sealed_success["trajectory_sha256"])
        visible = sealed_success["visible_trajectory_utf8"]
        if not isinstance(visible, str) or len(visible.encode("utf-8")) > MAX_SEALED_TRAJECTORY_BYTES:
            raise ExpelB2TransportError("sealed-success visible trajectory is invalid")
        if _sha(visible.encode("utf-8")) != trajectory:
            raise ExpelB2TransportError("sealed-success trajectory digest does not bind visible trajectory")
        payload = canonical_json_bytes({"episode_uid": episode_uid, "terminal_seal_sha256": terminal, "trajectory_sha256": trajectory, "visible_trajectory_utf8": visible}).decode()
        schema = _reflection_schema()
        raw = _prepare_chat_request(backend_identity=self._backend.identity, messages=({"role": "system", "content": REFLECTION_PROMPT_UTF8}, {"role": "user", "content": payload}), max_output_tokens=REFLECTION_MAX_OUTPUT_TOKENS, response_schema=schema)
        request_id = f"hswm-b2-reflection-{_sha(raw)[:32]}"
        tokenize_index, preflight = self._tokenize(operation="reflection", raw_chat=raw, request_id=request_id, max_output_tokens=REFLECTION_MAX_OUTPUT_TOKENS, deadline=deadline, monotonic=monotonic)
        completion_index, completion = self._complete(operation="reflection", raw_chat=raw, request_id=request_id, deadline=deadline, monotonic=monotonic)
        value = _strict_json(completion.text, label="reflection")
        try:
            schema.validate_instance(value)
            rule = normalize_rule(value["rule"])
        except (ContinualLiveError, ValueError) as error:
            raise ExpelB2TransportError("reflection response violates strict schema") from error
        unsigned = B2ReflectionReceipt(episode_uid, terminal, trajectory, rule, preflight, completion, tokenize_index, completion_index, "").unsigned()
        return B2ReflectionReceipt(episode_uid, terminal, trajectory, rule, preflight, completion, tokenize_index, completion_index, canonical_sha256(unsigned))
