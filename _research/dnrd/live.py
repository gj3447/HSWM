"""Narrow live-model boundary for the DNRD diagnostic.

This module is intentionally a transport adapter, not an experiment runner.  It
performs one OpenAI-compatible request per :class:`ModelRequest`, does not
retry, and records what the client can actually observe.  In particular, a
receipt never asserts provider-side cache independence or model determinism.
"""

from __future__ import annotations

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
from .task_family import canonical_json, commitment


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
EVENT_SCHEMA = "hswm-dnrd-live-model-event/v1"
PREFLIGHT_SCHEMA = "hswm-dnrd-live-preflight-receipt/v1"
ASCII_EDGE_WHITESPACE = " \t\r\n"


class LiveBoundaryError(RuntimeError):
    """A dispatched request or a malformed response made the run inconclusive."""


class PreDispatchTransportError(PreDispatchAnswererError):
    """The transport can prove that it sent no HTTP request."""


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

    def _read_bounded(self, stream: Any) -> bytes:
        body = stream.read(self._max_response_bytes + 1)
        if not isinstance(body, bytes) or len(body) > self._max_response_bytes:
            raise LiveBoundaryError("HTTP response exceeds frozen byte limit")
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
                return HttpResponse(status=status, body=self._read_bounded(response))
        except urlerror.HTTPError as error:
            return HttpResponse(status=error.code, body=self._read_bounded(error))
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
    if type(response.status) is not int or not isinstance(response.body, bytes):
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


def _parse_completion(raw: bytes) -> ModelReply:
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
    # Frozen handling is intentionally limited to ASCII edge whitespace.  No
    # case folding, token extraction, JSON repair, or interior-whitespace repair
    # occurs at the live boundary.
    response_token = message["content"].strip(ASCII_EDGE_WHITESPACE)
    if not response_token or any(char.isspace() for char in response_token):
        raise LiveBoundaryError("chat completion must contain one non-whitespace response token")
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
        "RAW_EQUAL_BUDGET",
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
                "chat_config": {**CHAT_CONFIG, "max_tokens": request.max_output_tokens},
                "elapsed_nanoseconds": time.monotonic_ns() - started_ns,
                "provider_cache_independence": "NOT_OBSERVABLE_BY_CLIENT",
                "failure_type": type(error).__name__,
            })
            raise LiveBoundaryError("model request outcome is ambiguous or post-dispatch") from error
        elapsed_ns = time.monotonic_ns() - started_ns
        raw = response.body if isinstance(response, HttpResponse) else b""
        _append(self._event_sink, {
            "schema_version": EVENT_SCHEMA,
            "event": "CHAT_COMPLETION_OBSERVED",
            **call_context,
            "endpoint": f"{self.config.base_url}/v1/chat/completions",
            "model": MODEL_ID,
            "request_sha256": _sha_bytes(body),
            "raw_response_sha256": _sha_bytes(raw),
            "http_status": response.status if isinstance(response, HttpResponse) else None,
            "chat_config": {**CHAT_CONFIG, "max_tokens": request.max_output_tokens},
            "elapsed_nanoseconds": elapsed_ns,
            "provider_cache_independence": "NOT_OBSERVABLE_BY_CLIENT",
        })
        checked = _require_response(response)
        reply = _parse_completion(checked.body)
        _append(self._event_sink, {
            "schema_version": EVENT_SCHEMA,
            "event": "CHAT_COMPLETION_ACCEPTED",
            **call_context,
            "endpoint": f"{self.config.base_url}/v1/chat/completions",
            "model": MODEL_ID,
            "request_sha256": _sha_bytes(body),
            "raw_response_sha256": _sha_bytes(checked.body),
            "raw_response_utf8": checked.body.decode("utf-8", errors="strict"),
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
