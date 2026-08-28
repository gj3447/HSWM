"""Narrow live-model boundary for the DNRD diagnostic.

This module is intentionally a transport adapter, not an experiment runner.  It
performs one OpenAI-compatible request per :class:`ModelRequest`, does not
retry, and records what the client can actually observe.  In particular, a
receipt never asserts provider-side cache independence or model determinism.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import errno
import socket
import time
from typing import Any, Callable, Mapping, Protocol
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from .runner import MAX_OUTPUT_TOKENS, ModelReply, ModelRequest, PreDispatchAnswererError, model_request_commitment
from .task_family import canonical_json, commitment, is_response_token


MODEL_ID = "qwen3.6-35b-a3b"
MODEL_ROOT = "Qwen/Qwen3.6-35B-A3B-FP8"
MODEL_MAX_LENGTH = 32_768
VLLM_VERSION = "0.25.1"
CHAT_CONFIG = {
    "chat_template_kwargs": {"enable_thinking": False},
    "logprobs": False,
    "n": 1,
    "stream": False,
    "temperature": 0,
    "top_p": 1,
}
EVENT_SCHEMA = "hswm-dnrd-live-model-event/v3"
PREFLIGHT_SCHEMA = "hswm-dnrd-live-preflight-receipt/v1"
REJECTED_RAW_ENCODING = "base64"
MAX_ANSWERER_RESPONSE_BYTES = 1_048_576

# These codes identify the frozen boundary check without making forensic
# consumers parse an exception's human-readable text. They deliberately do
# not name any request header or authentication material.
_RESPONSE_FAILURE_STAGE_CODES = {
    "HTTP response status": "HTTP_STATUS_NOT_2XX",
    "chat completion is not UTF-8 JSON": "CHAT_COMPLETION_NOT_UTF8_JSON",
    "chat completion must be a JSON object": "CHAT_COMPLETION_NOT_OBJECT",
    "chat completion model does not match frozen DNRD model": "MODEL_ID_MISMATCH",
    "chat completion must contain exactly one object choice": "CHOICE_CARDINALITY",
    "chat completion choice must finish with exact reason 'stop'": "FINISH_REASON_NOT_STOP",
    "chat completion choice must contain textual message.content": "MESSAGE_CONTENT_NOT_TEXT",
    "chat completion structured response is not strict JSON": "STRUCTURED_RESPONSE_NOT_STRICT_JSON",
    "chat completion structured response must be an object with exactly response_token": "STRUCTURED_RESPONSE_KEYSET_INVALID",
    "chat completion structured response_token violates exact DNRD-4 form": "RESPONSE_TOKEN_FORM_INVALID",
    "chat completion structured response_token is not one of the request candidates": "RESPONSE_TOKEN_NOT_REQUEST_CANDIDATE",
    "chat completion must contain object usage": "USAGE_NOT_OBJECT",
    "usage.prompt_tokens must be a nonnegative integer": "USAGE_PROMPT_TOKENS_INVALID",
    "usage.completion_tokens must be a nonnegative integer": "USAGE_COMPLETION_TOKENS_INVALID",
    "usage.total_tokens must be a nonnegative integer": "USAGE_TOTAL_TOKENS_INVALID",
    "usage.total_tokens must equal prompt_tokens + completion_tokens": "USAGE_ARITHMETIC_MISMATCH",
}


class LiveBoundaryError(RuntimeError):
    """A dispatched request or a malformed response made the run inconclusive."""


class PreDispatchTransportError(PreDispatchAnswererError):
    """The transport can prove that it sent no HTTP request."""


class _ObservedResponseBodyLimitError(LiveBoundaryError):
    """A single HTTP exchange supplied the fixed retained oversize prefix."""

    def __init__(self, *, http_status: int, retained_prefix: bytes) -> None:
        super().__init__("chat completion response exceeds frozen 1 MiB byte limit")
        self.http_status = http_status
        self.retained_prefix = retained_prefix


@dataclass(frozen=True)
class HttpResponse:
    """The complete, raw observation of one HTTP response."""

    status: int
    body: bytes


class HttpTransport(Protocol):
    """Injectable, single-shot transport.  It must not perform retries itself."""

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HttpResponse: ...


class _NoRedirect(urlrequest.HTTPRedirectHandler):
    """Convert every redirect into its first observed HTTP response."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


class UrllibHttpTransport:
    """One bounded urllib request with redirects disabled and no retry policy.

    ``OpenerDirector.open`` is the urllib primitive needed to install a local
    no-redirect policy without mutating urllib's process-global opener.  Each
    call invokes it exactly once.
    """

    def __init__(self, *, max_response_bytes: int = 1_048_576) -> None:
        if type(max_response_bytes) is not int or max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be a positive integer")
        self._max_response_bytes = max_response_bytes
        self._opener = urlrequest.build_opener(_NoRedirect())

    def _read_bounded(self, stream: Any, *, http_status: object) -> bytes:
        body = stream.read(self._max_response_bytes + 1)
        if not isinstance(body, bytes):
            raise LiveBoundaryError("HTTP response exceeds frozen byte limit")
        if len(body) > self._max_response_bytes:
            if type(http_status) is not int:
                raise LiveBoundaryError("HTTP response exceeds frozen byte limit")
            raise _ObservedResponseBodyLimitError(
                http_status=http_status,
                retained_prefix=body,
            )
        return body

    @staticmethod
    def _provably_pre_dispatch(error: BaseException) -> bool:
        if isinstance(error, (ValueError, socket.gaierror, ConnectionRefusedError)):
            return True
        if isinstance(error, OSError) and error.errno in {
            errno.ECONNREFUSED,
            errno.ENETUNREACH,
            errno.EHOSTUNREACH,
            errno.ENETDOWN,
        }:
            return True
        return False

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_seconds: float,
    ) -> HttpResponse:
        if method not in {"GET", "POST"} or type(timeout_seconds) not in (int, float) or timeout_seconds <= 0:
            raise PreDispatchTransportError("invalid pre-dispatch HTTP request configuration")
        if body is not None and not isinstance(body, bytes):
            raise PreDispatchTransportError("HTTP body must be bytes or None")
        try:
            request = urlrequest.Request(url, data=body, headers=dict(headers), method=method)
        except (TypeError, ValueError) as error:
            raise PreDispatchTransportError("urllib rejected HTTP request before dispatch") from error
        try:
            # This is deliberately the sole network attempt.  The local opener
            # returns 30x as HTTPError rather than following it.
            with self._opener.open(request, timeout=float(timeout_seconds)) as response:
                status = getattr(response, "status", None)
                return HttpResponse(status=status, body=self._read_bounded(response, http_status=status))
        except urlerror.HTTPError as error:
            return HttpResponse(status=error.code, body=self._read_bounded(error, http_status=error.code))
        except urlerror.URLError as error:
            if self._provably_pre_dispatch(error.reason):
                raise PreDispatchTransportError("DNS/connect failure before HTTP dispatch") from error
            raise LiveBoundaryError("urllib request outcome is ambiguous") from error
        except (ValueError, OSError) as error:
            if self._provably_pre_dispatch(error):
                raise PreDispatchTransportError("urllib failed before HTTP dispatch") from error
            raise LiveBoundaryError("urllib request outcome is ambiguous") from error


EventSink = Callable[[Mapping[str, Any]], None]


@dataclass(frozen=True)
class OpenAICompatibleDnrdConfig:
    """Frozen generation identity, with only endpoint/auth/timeout operational."""

    endpoint: str
    api_key: str | None = None
    timeout_seconds: float = 120.0
    model: str = MODEL_ID

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, str) or not self.endpoint.rstrip("/"):
            raise ValueError("endpoint must be a nonempty URL prefix")
        try:
            parsed = urlparse.urlsplit(self.endpoint)
            port = parsed.port
        except ValueError as error:
            raise ValueError("endpoint must have a valid port") from error
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") not in {"", "/v1"}
            or port is not None and not (0 < port < 65536)
        ):
            raise ValueError("endpoint must be an http(s) base URL with no query/fragment")
        if self.model != MODEL_ID:
            raise ValueError(f"DNRD is frozen to model {MODEL_ID!r}")
        if type(self.timeout_seconds) not in (int, float) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    @property
    def base_url(self) -> str:
        parsed = urlparse.urlsplit(self.endpoint)
        # Accept a common OpenAI base URL ending in /v1, but normalize it before
        # the frozen /v1/* paths below so requests can never become /v1/v1/*.
        return f"{parsed.scheme}://{parsed.netloc}"


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return canonical_json(value)


def _headers(config: OpenAICompatibleDnrdConfig) -> dict[str, str]:
    result = {"Accept": "application/json", "Content-Type": "application/json"}
    if config.api_key is not None:
        result["Authorization"] = f"Bearer {config.api_key}"
    return result


def _request_identity_bytes(method: str, url: str, body: bytes | None) -> bytes:
    """Public, secret-free request preimage used in a deployment receipt."""

    return _json_bytes({
        "body_sha256": _sha_bytes(body or b""),
        "content_type": "application/json",
        "method": method,
        "url": url,
    })


def _require_response(response: HttpResponse) -> HttpResponse:
    if type(response) is not HttpResponse or type(response.status) is not int or not isinstance(response.body, bytes):
        raise LiveBoundaryError("transport did not return an exact HTTP observation")
    if response.status < 200 or response.status >= 300:
        raise LiveBoundaryError(f"HTTP response status {response.status}")
    return response


def _decode_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LiveBoundaryError(f"{label} is not UTF-8 JSON") from error
    if type(value) is not dict:
        raise LiveBoundaryError(f"{label} must be a JSON object")
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise LiveBoundaryError(f"{label} must be a nonnegative integer")
    return value


def _candidate_response_tokens(request: ModelRequest) -> tuple[str, str]:
    """Read DNRD-4's per-episode, two-token output contract.

    The runner owns construction and commitment of this field.  The transport
    independently validates it before any dispatch, so a malformed request
    cannot weaken the schema sent to a provider.
    """
    candidates = getattr(request, "candidate_response_tokens", None)
    if type(candidates) is not tuple or len(candidates) != 2:
        raise PreDispatchAnswererError("DNRD-4 request must carry exactly two candidate response tokens")
    first, second = candidates
    if (
        not is_response_token(first)
        or not is_response_token(second)
        or first >= second
    ):
        raise PreDispatchAnswererError(
            "DNRD-4 request candidate response tokens must be distinct canonical response tokens in sorted order"
        )
    return first, second


def _response_format(candidates: tuple[str, str]) -> dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "response_token": {
                "type": "string",
                "enum": list(candidates),
                "pattern": r"^token-[0-9a-f]{20}$",
                "minLength": 26,
                "maxLength": 26,
            },
        },
        "required": ["response_token"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "hswm_dnrd_response_token",
            "strict": True,
            "schema": schema,
        },
    }


def _chat_config(request: ModelRequest) -> dict[str, Any]:
    response_format = _response_format(_candidate_response_tokens(request))
    return {
        **CHAT_CONFIG,
        "max_tokens": request.max_output_tokens,
        "response_format": response_format,
        "response_format_schema_sha256": commitment(response_format["json_schema"]["schema"]),
    }


def _strict_structured_response(content: str, candidates: tuple[str, str]) -> str:
    def no_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate object key")
            result[key] = value
        return result

    try:
        value = json.loads(
            content,
            object_pairs_hook=no_duplicate_object_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("non-finite number")),
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise LiveBoundaryError("chat completion structured response is not strict JSON") from error
    if type(value) is not dict or set(value) != {"response_token"}:
        raise LiveBoundaryError("chat completion structured response must be an object with exactly response_token")
    response_token = value["response_token"]
    if not is_response_token(response_token):
        raise LiveBoundaryError("chat completion structured response_token violates exact DNRD-4 form")
    if response_token not in candidates:
        raise LiveBoundaryError("chat completion structured response_token is not one of the request candidates")
    return response_token


def _parse_completion(raw: bytes, candidates: tuple[str, str]) -> ModelReply:
    value = _decode_object(raw, "chat completion")
    if value.get("model") != MODEL_ID:
        raise LiveBoundaryError("chat completion model does not match frozen DNRD model")
    choices = value.get("choices")
    if type(choices) is not list or len(choices) != 1 or type(choices[0]) is not dict:
        raise LiveBoundaryError("chat completion must contain exactly one object choice")
    if choices[0].get("finish_reason") != "stop":
        raise LiveBoundaryError("chat completion choice must finish with exact reason 'stop'")
    message = choices[0].get("message")
    if type(message) is not dict or type(message.get("content")) is not str:
        raise LiveBoundaryError("chat completion choice must contain textual message.content")
    response_token = _strict_structured_response(message["content"], candidates)
    usage = value.get("usage")
    if type(usage) is not dict:
        raise LiveBoundaryError("chat completion must contain object usage")
    input_tokens = _integer(usage.get("prompt_tokens"), "usage.prompt_tokens")
    output_tokens = _integer(usage.get("completion_tokens"), "usage.completion_tokens")
    total_tokens = _integer(usage.get("total_tokens"), "usage.total_tokens")
    if total_tokens != input_tokens + output_tokens:
        raise LiveBoundaryError("usage.total_tokens must equal prompt_tokens + completion_tokens")
    return ModelReply(
        response_token=response_token,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        client_cache_hit=False,
        server_usage={
            key: _integer(item, f"usage.{key}")
            for key, item in usage.items()
            if key not in {"prompt_tokens", "completion_tokens", "total_tokens"}
            and type(item) is int
        },
    )


def _failure_stage_code(error: LiveBoundaryError) -> str:
    """Return a stable, non-secret label for one observed-response refusal."""
    message = str(error)
    for prefix, code in _RESPONSE_FAILURE_STAGE_CODES.items():
        if message.startswith(prefix):
            return code
    # All _require_response and _parse_completion failure messages are covered
    # above.  Keep a fixed final label should a future boundary check be added
    # without a corresponding schema code; never encode exception internals.
    return "UNMAPPED_FROZEN_RESPONSE_CONTRACT_REJECTED"


def _rejected_completion_event(
    *,
    call_context: Mapping[str, Any],
    endpoint: str,
    request_body: bytes,
    raw_response: bytes,
    response: object,
    elapsed_nanoseconds: int,
    chat_config: Mapping[str, Any],
    error: LiveBoundaryError,
) -> dict[str, Any]:
    """Retain the exact bounded response body after a parser/HTTP refusal.

    The production urllib transport already enforces its 1 MiB response cap.
    This event serializes only the response body, never request headers or the
    environment-supplied API key.
    """
    return {
        "schema_version": EVENT_SCHEMA,
        "event": "CHAT_COMPLETION_REJECTED",
        **call_context,
        "endpoint": endpoint,
        "model": MODEL_ID,
        "request_sha256": _sha_bytes(request_body),
        "raw_response_sha256": _sha_bytes(raw_response),
        "raw_response_encoding": REJECTED_RAW_ENCODING,
        "raw_response_base64": base64.b64encode(raw_response).decode("ascii"),
        "raw_response_bytes": len(raw_response),
        "http_status": response.status if isinstance(response, HttpResponse) else None,
        "chat_config": dict(chat_config),
        "elapsed_nanoseconds": elapsed_nanoseconds,
        "provider_cache_independence": "NOT_OBSERVABLE_BY_CLIENT",
        "failure_stage_code": _failure_stage_code(error),
        "failure_message": str(error),
        "failure_message_sha256": _sha_bytes(str(error).encode("utf-8")),
    }


def _transport_response_rejected_event(
    *,
    call_context: Mapping[str, Any],
    endpoint: str,
    request_body: bytes,
    elapsed_nanoseconds: int,
    chat_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Describe a malformed transport return without inventing response bytes."""
    failure_message = "transport did not return an exact HTTP observation"
    return {
        "schema_version": EVENT_SCHEMA,
        "event": "TRANSPORT_RESPONSE_REJECTED",
        **call_context,
        "endpoint": endpoint,
        "model": MODEL_ID,
        "request_sha256": _sha_bytes(request_body),
        "chat_config": dict(chat_config),
        "elapsed_nanoseconds": elapsed_nanoseconds,
        "provider_cache_independence": "NOT_OBSERVABLE_BY_CLIENT",
        "failure_stage_code": "TRANSPORT_RESPONSE_NOT_EXACT_HTTP_RESPONSE",
        "failure_message": failure_message,
        "failure_message_sha256": _sha_bytes(failure_message.encode("utf-8")),
    }


def _oversize_response_rejected_event(
    *,
    call_context: Mapping[str, Any],
    endpoint: str,
    request_body: bytes,
    retained_prefix: bytes,
    http_status: int,
    elapsed_nanoseconds: int,
    chat_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Retain only the exact fixed prefix that proves an oversized response.

    The prefix establishes a lower bound, not the full response's byte length
    or digest.  Request headers and credentials never enter this event.
    """
    failure_message = "chat completion response exceeds frozen 1 MiB byte limit"
    if len(retained_prefix) != MAX_ANSWERER_RESPONSE_BYTES + 1:
        raise RuntimeError("oversize response prefix must be exactly 1 MiB + 1 byte")
    return {
        "schema_version": EVENT_SCHEMA,
        "event": "CHAT_COMPLETION_REJECTED",
        **call_context,
        "endpoint": endpoint,
        "model": MODEL_ID,
        "request_sha256": _sha_bytes(request_body),
        "retained_response_prefix_encoding": REJECTED_RAW_ENCODING,
        "retained_response_prefix_base64": base64.b64encode(retained_prefix).decode("ascii"),
        "retained_response_prefix_sha256": _sha_bytes(retained_prefix),
        "retained_response_prefix_bytes": len(retained_prefix),
        "response_body_bytes_lower_bound": len(retained_prefix),
        "http_status": http_status,
        "chat_config": dict(chat_config),
        "elapsed_nanoseconds": elapsed_nanoseconds,
        "provider_cache_independence": "NOT_OBSERVABLE_BY_CLIENT",
        "failure_stage_code": "RESPONSE_BODY_EXCEEDS_1_MIB",
        "failure_message": failure_message,
        "failure_message_sha256": _sha_bytes(failure_message.encode("utf-8")),
    }


def _append(sink: EventSink | None, event: Mapping[str, Any]) -> None:
    if sink is not None:
        # A fresh immutable mapping prevents a sink from altering later records.
        sink(dict(event))


def _call_context(request: ModelRequest) -> dict[str, Any]:
    """Public runner identity that never enters the provider prompt/body."""
    if type(request.ordinal) is not int or request.ordinal < 1:
        raise PreDispatchAnswererError("DNRD request ordinal must be a positive integer")
    if request.phase not in {"training", "heldout"}:
        raise PreDispatchAnswererError("DNRD request phase is invalid")
    if request.phase == "training" and request.arm is not None:
        raise PreDispatchAnswererError("training request must not carry an arm")
    if request.phase == "heldout" and request.arm not in {
        "FULL",
        "NO_MEMORY_ROLLBACK",
        "BINDING_DERANGED_NUMERIC_PLACEBO",
    }:
        raise PreDispatchAnswererError("heldout request arm is invalid")
    return {
        "ordinal": request.ordinal,
        "phase": request.phase,
        "arm": request.arm,
        "dnrd_request_sha256": model_request_commitment(request),
    }


class OpenAICompatibleDnrdAnswerer:
    """A one-request/no-retry :class:`~_research.dnrd.runner.Answerer`."""

    def __init__(
        self,
        config: OpenAICompatibleDnrdConfig,
        transport: HttpTransport,
        *,
        event_sink: EventSink | None = None,
    ) -> None:
        self.config = config
        self._transport = transport
        self._event_sink = event_sink

    def answer(self, request: ModelRequest) -> ModelReply:
        if request.max_output_tokens != MAX_OUTPUT_TOKENS:
            raise PreDispatchAnswererError("DNRD request max_output_tokens must equal the frozen limit")
        if not isinstance(request.prompt, str) or not request.prompt:
            raise PreDispatchAnswererError("DNRD request prompt must be nonempty text")
        chat_config = _chat_config(request)
        candidates = _candidate_response_tokens(request)
        call_context = _call_context(request)
        body = _json_bytes({
            "chat_template_kwargs": CHAT_CONFIG["chat_template_kwargs"],
            "max_tokens": request.max_output_tokens,
            "messages": [{"content": request.prompt, "role": "user"}],
            "model": MODEL_ID,
            "n": CHAT_CONFIG["n"],
            "stream": CHAT_CONFIG["stream"],
            "temperature": CHAT_CONFIG["temperature"],
            "top_p": CHAT_CONFIG["top_p"],
            "logprobs": CHAT_CONFIG["logprobs"],
            "response_format": chat_config["response_format"],
        })
        started_ns = time.monotonic_ns()
        try:
            response = self._transport.request(
                method="POST",
                url=f"{self.config.base_url}/v1/chat/completions",
                headers=_headers(self.config),
                body=body,
                timeout_seconds=float(self.config.timeout_seconds),
            )
        except PreDispatchTransportError:
            raise
        except _ObservedResponseBodyLimitError as error:
            elapsed_ns = time.monotonic_ns() - started_ns
            endpoint = f"{self.config.base_url}/v1/chat/completions"
            _append(self._event_sink, _oversize_response_rejected_event(
                call_context=call_context,
                endpoint=endpoint,
                request_body=body,
                retained_prefix=error.retained_prefix,
                http_status=error.http_status,
                elapsed_nanoseconds=elapsed_ns,
                chat_config=chat_config,
            ))
            raise LiveBoundaryError("chat completion response exceeds frozen 1 MiB byte limit") from error
        except Exception as error:
            # The transport did not prove no bytes left the process.  The runner
            # must conservatively treat this as a post-first-call interruption.
            _append(self._event_sink, {
                "schema_version": EVENT_SCHEMA,
                "event": "AMBIGUOUS_OR_POST_DISPATCH_FAILURE",
                **call_context,
                "endpoint": f"{self.config.base_url}/v1/chat/completions",
                "model": MODEL_ID,
                "request_sha256": _sha_bytes(body),
                "chat_config": chat_config,
                "elapsed_nanoseconds": time.monotonic_ns() - started_ns,
                "provider_cache_independence": "NOT_OBSERVABLE_BY_CLIENT",
                "failure_type": type(error).__name__,
            })
            raise LiveBoundaryError("model request outcome is ambiguous or post-dispatch") from error
        elapsed_ns = time.monotonic_ns() - started_ns
        endpoint = f"{self.config.base_url}/v1/chat/completions"
        if type(response) is not HttpResponse:
            _append(self._event_sink, _transport_response_rejected_event(
                call_context=call_context,
                endpoint=endpoint,
                request_body=body,
                elapsed_nanoseconds=elapsed_ns,
                chat_config=chat_config,
            ))
            raise LiveBoundaryError("transport did not return an exact HTTP observation")
        if type(response.status) is not int or type(response.body) is not bytes:
            _append(self._event_sink, _transport_response_rejected_event(
                call_context=call_context,
                endpoint=endpoint,
                request_body=body,
                elapsed_nanoseconds=elapsed_ns,
                chat_config=chat_config,
            ))
            raise LiveBoundaryError("transport did not return an exact HTTP observation")
        raw = response.body
        if len(raw) > MAX_ANSWERER_RESPONSE_BYTES:
            retained_prefix = raw[:MAX_ANSWERER_RESPONSE_BYTES + 1]
            _append(self._event_sink, _oversize_response_rejected_event(
                call_context=call_context,
                endpoint=endpoint,
                request_body=body,
                retained_prefix=retained_prefix,
                http_status=response.status,
                elapsed_nanoseconds=elapsed_ns,
                chat_config=chat_config,
            ))
            raise LiveBoundaryError("chat completion response exceeds frozen 1 MiB byte limit")
        _append(self._event_sink, {
            "schema_version": EVENT_SCHEMA,
            "event": "CHAT_COMPLETION_OBSERVED",
            **call_context,
            "endpoint": endpoint,
            "model": MODEL_ID,
            "request_sha256": _sha_bytes(body),
            "raw_response_sha256": _sha_bytes(raw),
            "http_status": response.status if isinstance(response, HttpResponse) else None,
            "chat_config": chat_config,
            "elapsed_nanoseconds": elapsed_ns,
            "provider_cache_independence": "NOT_OBSERVABLE_BY_CLIENT",
        })
        try:
            checked = _require_response(response)
            reply = _parse_completion(checked.body, candidates)
        except LiveBoundaryError as error:
            _append(self._event_sink, _rejected_completion_event(
                call_context=call_context,
                endpoint=endpoint,
                request_body=body,
                raw_response=raw,
                response=response,
                elapsed_nanoseconds=elapsed_ns,
                chat_config=chat_config,
                error=error,
            ))
            raise
        _append(self._event_sink, {
            "schema_version": EVENT_SCHEMA,
            "event": "CHAT_COMPLETION_ACCEPTED",
            **call_context,
            "endpoint": endpoint,
            "model": MODEL_ID,
            "request_sha256": _sha_bytes(body),
            "raw_response_sha256": _sha_bytes(checked.body),
            "raw_response_utf8": checked.body.decode("utf-8", errors="strict"),
            "chat_config": chat_config,
            "dnrd_response_sha256": commitment({
                "response_token": reply.response_token,
                "input_tokens": reply.input_tokens,
                "output_tokens": reply.output_tokens,
                "client_cache_hit": reply.client_cache_hit,
                "server_usage": dict(reply.server_usage or {}),
            }),
            "usage": {"prompt_tokens": reply.input_tokens, "completion_tokens": reply.output_tokens, **dict(reply.server_usage or {})},
            "elapsed_nanoseconds": elapsed_ns,
            "provider_cache_independence": "NOT_OBSERVABLE_BY_CLIENT",
        })
        return reply


def preflight_deployment_and_tokenizer(
    config: OpenAICompatibleDnrdConfig,
    transport: HttpTransport,
    *,
    tokenizer_prompt: str,
) -> dict[str, Any]:
    """Observe exact model identity and one non-generation tokenizer response.

    The caller must preregister this as non-generation network activity.  This
    function makes exactly three transport calls (``/v1/models``, ``/version``,
    then ``/tokenize``) and deliberately does not call a chat-completions
    endpoint.
    """

    if not isinstance(tokenizer_prompt, str) or not tokenizer_prompt:
        raise PreDispatchAnswererError("tokenizer preflight prompt must be nonempty text")
    headers = _headers(config)
    models_url = f"{config.base_url}/v1/models"
    version_url = f"{config.base_url}/version"
    tokenize_url = f"{config.base_url}/tokenize"
    try:
        models = _require_response(transport.request(
            method="GET", url=models_url, headers=headers,
            body=None, timeout_seconds=float(config.timeout_seconds),
        ))
    except PreDispatchTransportError:
        raise
    except Exception as error:
        raise LiveBoundaryError("model-list preflight outcome is ambiguous or rejected") from error
    model_payload = _decode_object(models.body, "model-list response")
    data = model_payload.get("data")
    matching = [item for item in data if type(item) is dict and item.get("id") == MODEL_ID] if type(data) is list else []
    if len(matching) != 1:
        raise LiveBoundaryError("model-list response does not attest frozen DNRD model")
    model_entry = matching[0]
    if model_entry.get("root") != MODEL_ROOT:
        raise LiveBoundaryError("model-list root does not match frozen DNRD deployment")
    if _integer(model_entry.get("max_model_len"), "model-list max_model_len") != MODEL_MAX_LENGTH:
        raise LiveBoundaryError("model-list max_model_len does not match frozen DNRD deployment")
    try:
        version = _require_response(transport.request(
            method="GET", url=version_url, headers=headers,
            body=None, timeout_seconds=float(config.timeout_seconds),
        ))
    except PreDispatchTransportError:
        raise
    except Exception as error:
        raise LiveBoundaryError("server-version preflight outcome is ambiguous or rejected") from error
    version_payload = _decode_object(version.body, "server-version response")
    if version_payload.get("version") != VLLM_VERSION:
        raise LiveBoundaryError("server-version does not match frozen vLLM deployment")
    tokenize_body = _json_bytes({"model": MODEL_ID, "prompt": tokenizer_prompt})
    try:
        tokenized = _require_response(transport.request(
            method="POST", url=tokenize_url, headers=headers,
            body=tokenize_body, timeout_seconds=float(config.timeout_seconds),
        ))
    except PreDispatchTransportError:
        raise
    except Exception as error:
        raise LiveBoundaryError("tokenizer preflight outcome is ambiguous or rejected") from error
    tokenizer_payload = _decode_object(tokenized.body, "tokenizer response")
    token_count = _integer(tokenizer_payload.get("count"), "tokenizer.count")
    if "tokens" in tokenizer_payload:
        if type(tokenizer_payload["tokens"]) is not list or len(tokenizer_payload["tokens"]) != token_count:
            raise LiveBoundaryError("tokenizer tokens/count mismatch")
    unsigned = {
        "schema_version": PREFLIGHT_SCHEMA,
        "endpoint": config.base_url,
        "model": MODEL_ID,
        "model_root": MODEL_ROOT,
        "model_max_model_len": MODEL_MAX_LENGTH,
        "vllm_version": VLLM_VERSION,
        "chat_config": CHAT_CONFIG,
        "model_list_request_sha256": _sha_bytes(_request_identity_bytes("GET", models_url, None)),
        "model_list_response_sha256": _sha_bytes(models.body),
        # These are the exact response bodies already decoded as public JSON
        # above.  They intentionally exclude request headers (and therefore
        # any Authorization secret), but let a later bundle verifier reparse
        # the deployment rather than trust a caller-provided summary.
        "model_list_response_utf8": models.body.decode("utf-8", errors="strict"),
        "version_request_sha256": _sha_bytes(_request_identity_bytes("GET", version_url, None)),
        "version_response_sha256": _sha_bytes(version.body),
        "version_response_utf8": version.body.decode("utf-8", errors="strict"),
        "tokenizer_request_sha256": _sha_bytes(_request_identity_bytes("POST", tokenize_url, tokenize_body)),
        "tokenizer_response_sha256": _sha_bytes(tokenized.body),
        "tokenizer_response_utf8": tokenized.body.decode("utf-8", errors="strict"),
        "tokenizer_count": token_count,
        "provider_cache_independence": "NOT_OBSERVABLE_BY_CLIENT",
        "generation_calls": 0,
        "non_generation_http_calls": 3,
        "preflight_call_order": ["GET /v1/models", "GET /version", "POST /tokenize"],
    }
    return {**unsigned, "receipt_sha256": commitment(unsigned)}
