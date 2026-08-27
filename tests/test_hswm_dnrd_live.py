from __future__ import annotations

import json
import socket
from urllib import error as urlerror

import pytest

from _research.dnrd.live import (
    CHAT_CONFIG,
    MODEL_ID,
    MODEL_MAX_LENGTH,
    MODEL_ROOT,
    VLLM_VERSION,
    LiveBoundaryError,
    HttpResponse,
    OpenAICompatibleDnrdAnswerer,
    OpenAICompatibleDnrdConfig,
    PreDispatchTransportError,
    UrllibHttpTransport,
    preflight_deployment_and_tokenizer,
)
from _research.dnrd.runner import ModelRequest, PreDispatchAnswererError
from _research.dnrd.task_family import commitment


class RecordingTransport:
    def __init__(self, outcomes: list[HttpResponse | Exception]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict] = []

    def request(self, **kwargs: object) -> HttpResponse:
        self.calls.append(dict(kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _completion(*, content: str = "  token-abc  ", model: str = MODEL_ID) -> HttpResponse:
    return HttpResponse(200, json.dumps({
        "model": model,
        "choices": [{"finish_reason": "stop", "message": {"content": content}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 2, "total_tokens": 13, "cached_tokens": 3, "prompt_tokens_details": {"cached_tokens": 3}, "null_telemetry": None},
    }).encode())


def _request() -> ModelRequest:
    return ModelRequest("episode-1", "route-1", "return only a token", 16, 1, "training", None)


def test_answerer_sends_frozen_body_once_and_records_raw_observations() -> None:
    events: list[dict] = []
    transport = RecordingTransport([_completion()])
    answerer = OpenAICompatibleDnrdAnswerer(
        OpenAICompatibleDnrdConfig("http://dgx.local:8000/"), transport, event_sink=events.append
    )
    reply = answerer.answer(_request())
    assert reply.response_token == "token-abc"
    assert (reply.input_tokens, reply.output_tokens) == (11, 2)
    assert reply.server_usage == {"cached_tokens": 3}
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "http://dgx.local:8000/v1/chat/completions"
    body = json.loads(call["body"])
    assert body == {
        "chat_template_kwargs": {"enable_thinking": False},
        "max_tokens": 16,
        "messages": [{"content": "return only a token", "role": "user"}],
        "model": MODEL_ID,
        "n": 1,
        "stream": False,
        "temperature": 0,
        "top_p": 1,
        "logprobs": False,
    }
    assert len(events) == 2
    assert events[0]["event"] == "CHAT_COMPLETION_OBSERVED"
    assert events[0]["provider_cache_independence"] == "NOT_OBSERVABLE_BY_CLIENT"
    assert events[1]["usage"] == {"prompt_tokens": 11, "completion_tokens": 2, "cached_tokens": 3}
    assert events[1]["raw_response_utf8"] == _completion().body.decode()
    assert events[1]["ordinal"] == 1 and events[1]["phase"] == "training"


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"model": "wrong", "choices": [{"finish_reason": "stop", "message": {"content": "token"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}, "model"),
        ({"model": MODEL_ID, "choices": [{"finish_reason": "stop", "message": {"content": "one"}}, {"finish_reason": "stop", "message": {"content": "two"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}, "exactly one"),
        ({"model": MODEL_ID, "choices": [{"finish_reason": "stop", "message": {"content": 3}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}, "textual"),
        ({"model": MODEL_ID, "choices": [{"finish_reason": "stop", "message": {"content": "token"}}], "usage": {"prompt_tokens": True, "completion_tokens": 1, "total_tokens": 2}}, "integer"),
    ],
)
def test_answerer_rejects_malformed_completion_without_repair(payload: dict, message: str) -> None:
    answerer = OpenAICompatibleDnrdAnswerer(
        OpenAICompatibleDnrdConfig("http://endpoint"), RecordingTransport([HttpResponse(200, json.dumps(payload).encode())])
    )
    with pytest.raises(LiveBoundaryError, match=message):
        answerer.answer(_request())


def test_answerer_distinguishes_provable_pre_dispatch_from_ambiguous_failure() -> None:
    pre = OpenAICompatibleDnrdAnswerer(
        OpenAICompatibleDnrdConfig("http://endpoint"), RecordingTransport([PreDispatchTransportError("dns before send")])
    )
    with pytest.raises(PreDispatchAnswererError, match="dns before send"):
        pre.answer(_request())

    events: list[dict] = []
    ambiguous = OpenAICompatibleDnrdAnswerer(
        OpenAICompatibleDnrdConfig("http://endpoint"), RecordingTransport([TimeoutError("unknown")]), event_sink=events.append
    )
    with pytest.raises(LiveBoundaryError, match="ambiguous"):
        ambiguous.answer(_request())
    assert len(events) == 1 and events[0]["event"] == "AMBIGUOUS_OR_POST_DISPATCH_FAILURE"


def test_preflight_makes_only_model_and_tokenize_calls_and_binds_receipt() -> None:
    models = HttpResponse(200, json.dumps({"data": [{"id": MODEL_ID, "root": MODEL_ROOT, "max_model_len": MODEL_MAX_LENGTH}, {"id": "other"}]}).encode())
    version = HttpResponse(200, json.dumps({"version": VLLM_VERSION}).encode())
    tokenizer = HttpResponse(200, json.dumps({"count": 3, "tokens": [1, 2, 3]}).encode())
    transport = RecordingTransport([models, version, tokenizer])
    receipt = preflight_deployment_and_tokenizer(
        OpenAICompatibleDnrdConfig("http://endpoint/"), transport, tokenizer_prompt="frozen probe"
    )
    assert [call["url"] for call in transport.calls] == ["http://endpoint/v1/models", "http://endpoint/version", "http://endpoint/tokenize"]
    assert transport.calls[0]["body"] is None
    assert transport.calls[1]["body"] is None
    assert json.loads(transport.calls[2]["body"]) == {"model": MODEL_ID, "prompt": "frozen probe"}
    unsigned = dict(receipt)
    assert receipt["generation_calls"] == 0
    assert receipt["non_generation_http_calls"] == 3
    assert receipt["preflight_call_order"] == ["GET /v1/models", "GET /version", "POST /tokenize"]
    assert (receipt["model_root"], receipt["model_max_model_len"], receipt["vllm_version"]) == (MODEL_ROOT, MODEL_MAX_LENGTH, VLLM_VERSION)
    assert receipt["chat_config"] == CHAT_CONFIG
    assert receipt["receipt_sha256"] == commitment({key: value for key, value in unsigned.items() if key != "receipt_sha256"})


def test_preflight_refuses_missing_model_and_tokenizer_count() -> None:
    missing = RecordingTransport([HttpResponse(200, b'{"data":[]}')])
    with pytest.raises(LiveBoundaryError, match="does not attest"):
        preflight_deployment_and_tokenizer(OpenAICompatibleDnrdConfig("http://endpoint"), missing, tokenizer_prompt="x")
    malformed = RecordingTransport([
        HttpResponse(200, json.dumps({"data": [{"id": MODEL_ID, "root": MODEL_ROOT, "max_model_len": MODEL_MAX_LENGTH}]}).encode()),
        HttpResponse(200, json.dumps({"version": VLLM_VERSION}).encode()),
        HttpResponse(200, b'{"tokens":[1]}'),
    ])
    with pytest.raises(LiveBoundaryError, match="tokenizer.count"):
        preflight_deployment_and_tokenizer(OpenAICompatibleDnrdConfig("http://endpoint"), malformed, tokenizer_prompt="x")


def test_preflight_refuses_wrong_deployment_root_length_or_vllm_version() -> None:
    wrong_root = RecordingTransport([
        HttpResponse(200, json.dumps({"data": [{"id": MODEL_ID, "root": "other", "max_model_len": MODEL_MAX_LENGTH}]}).encode()),
    ])
    with pytest.raises(LiveBoundaryError, match="root"):
        preflight_deployment_and_tokenizer(OpenAICompatibleDnrdConfig("http://endpoint"), wrong_root, tokenizer_prompt="x")
    wrong_version = RecordingTransport([
        HttpResponse(200, json.dumps({"data": [{"id": MODEL_ID, "root": MODEL_ROOT, "max_model_len": MODEL_MAX_LENGTH}]}).encode()),
        HttpResponse(200, b'{"version":"0.25.0"}'),
    ])
    with pytest.raises(LiveBoundaryError, match="server-version"):
        preflight_deployment_and_tokenizer(OpenAICompatibleDnrdConfig("http://endpoint"), wrong_version, tokenizer_prompt="x")


def test_endpoint_normalizes_v1_and_refuses_query_fragment_or_non_http() -> None:
    assert OpenAICompatibleDnrdConfig("https://endpoint/v1/").base_url == "https://endpoint"
    for endpoint in ("ftp://endpoint", "http://endpoint?x=1", "https://endpoint/#fragment", "https://endpoint/prefix"):
        with pytest.raises(ValueError, match="endpoint"):
            OpenAICompatibleDnrdConfig(endpoint)


def test_answerer_requires_stop_and_exact_usage_arithmetic() -> None:
    unfinished = HttpResponse(200, json.dumps({"model": MODEL_ID, "choices": [{"finish_reason": "length", "message": {"content": "token"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode())
    with pytest.raises(LiveBoundaryError, match="finish"):
        OpenAICompatibleDnrdAnswerer(OpenAICompatibleDnrdConfig("http://endpoint"), RecordingTransport([unfinished])).answer(_request())
    arithmetic = HttpResponse(200, json.dumps({"model": MODEL_ID, "choices": [{"finish_reason": "stop", "message": {"content": "token"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 3}}).encode())
    with pytest.raises(LiveBoundaryError, match="total_tokens"):
        OpenAICompatibleDnrdAnswerer(OpenAICompatibleDnrdConfig("http://endpoint"), RecordingTransport([arithmetic])).answer(_request())


def test_urllib_transport_is_single_shot_and_classifies_only_provable_pre_dispatch() -> None:
    class Response:
        status = 200

        def read(self, _: int) -> bytes:
            return b"{}"

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    class Opener:
        def __init__(self, outcome: object) -> None:
            self.outcome, self.calls = outcome, 0

        def open(self, *_: object, **__: object) -> Response:
            self.calls += 1
            if isinstance(self.outcome, BaseException):
                raise self.outcome
            return self.outcome  # type: ignore[return-value]

    transport = UrllibHttpTransport(max_response_bytes=10)
    opener = Opener(Response())
    transport._opener = opener  # type: ignore[attr-defined]
    assert transport.request(method="GET", url="http://endpoint/v1/models", headers={}, body=None, timeout_seconds=1) == HttpResponse(200, b"{}")
    assert opener.calls == 1

    dns = UrllibHttpTransport()
    dns._opener = Opener(urlerror.URLError(socket.gaierror("no dns")))  # type: ignore[attr-defined]
    with pytest.raises(PreDispatchTransportError, match="DNS/connect"):
        dns.request(method="GET", url="http://endpoint/v1/models", headers={}, body=None, timeout_seconds=1)

    ambiguous = UrllibHttpTransport()
    ambiguous._opener = Opener(urlerror.URLError(TimeoutError("unknown")))  # type: ignore[attr-defined]
    with pytest.raises(LiveBoundaryError, match="ambiguous"):
        ambiguous.request(method="GET", url="http://endpoint/v1/models", headers={}, body=None, timeout_seconds=1)
