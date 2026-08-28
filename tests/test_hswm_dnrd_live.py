from __future__ import annotations

import base64
import hashlib
import json
import socket
from urllib import error as urlerror

import pytest

from _research.dnrd.live import (
    CHAT_CONFIG,
    EVENT_SCHEMA,
    MAX_ANSWERER_RESPONSE_BYTES,
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
from _research.dnrd.runner import MAX_OUTPUT_TOKENS, ModelRequest, PreDispatchAnswererError
from _research.dnrd.task_family import commitment


VALID_RESPONSE_TOKEN = "token-aaaaaaaaaaaaaaaaaaaa"
OTHER_VALID_RESPONSE_TOKEN = "token-bbbbbbbbbbbbbbbbbbbb"
CANDIDATE_RESPONSE_TOKENS = (VALID_RESPONSE_TOKEN, OTHER_VALID_RESPONSE_TOKEN)
VALID_STRUCTURED_CONTENT = json.dumps({"response_token": VALID_RESPONSE_TOKEN})


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


def _completion(*, content: str | None = None, model: str = MODEL_ID) -> HttpResponse:
    if content is None:
        content = json.dumps({"response_token": VALID_RESPONSE_TOKEN})
    return HttpResponse(200, json.dumps({
        "model": model,
        "choices": [{"finish_reason": "stop", "message": {"content": content}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 2, "total_tokens": 13, "cached_tokens": 3, "prompt_tokens_details": {"cached_tokens": 3}, "null_telemetry": None},
    }).encode())


def _request() -> ModelRequest:
    return ModelRequest(
        "episode-1", "route-1", "return only a token", MAX_OUTPUT_TOKENS,
        1, "training", None, CANDIDATE_RESPONSE_TOKENS,
    )


def test_answerer_sends_frozen_body_once_and_records_raw_observations() -> None:
    events: list[dict] = []
    transport = RecordingTransport([_completion()])
    answerer = OpenAICompatibleDnrdAnswerer(
        OpenAICompatibleDnrdConfig("http://dgx.local:8000/"), transport, event_sink=events.append
    )
    reply = answerer.answer(_request())
    assert reply.response_token == VALID_RESPONSE_TOKEN
    assert (reply.input_tokens, reply.output_tokens) == (11, 2)
    assert reply.server_usage == {"cached_tokens": 3}
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "http://dgx.local:8000/v1/chat/completions"
    body = json.loads(call["body"])
    assert body == {
        "chat_template_kwargs": {"enable_thinking": False},
        "max_tokens": MAX_OUTPUT_TOKENS,
        "messages": [{"content": "return only a token", "role": "user"}],
        "model": MODEL_ID,
        "n": 1,
        "stream": False,
        "temperature": 0,
        "top_p": 1,
        "logprobs": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "hswm_dnrd_response_token",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"response_token": {
                        "type": "string", "enum": list(CANDIDATE_RESPONSE_TOKENS),
                        "pattern": "^token-[0-9a-f]{20}$", "minLength": 26, "maxLength": 26,
                    }},
                    "required": ["response_token"],
                    "additionalProperties": False,
                },
            },
        },
    }
    assert len(events) == 2
    assert events[0]["event"] == "CHAT_COMPLETION_OBSERVED"
    assert events[0]["provider_cache_independence"] == "NOT_OBSERVABLE_BY_CLIENT"
    assert events[1]["usage"] == {"prompt_tokens": 11, "completion_tokens": 2, "cached_tokens": 3}
    assert events[1]["raw_response_utf8"] == _completion().body.decode()
    assert events[1]["chat_config"] == {
        **CHAT_CONFIG,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "response_format": body["response_format"],
        "response_format_schema_sha256": commitment(body["response_format"]["json_schema"]["schema"]),
    }
    assert events[1]["ordinal"] == 1 and events[1]["phase"] == "training"


def test_answerer_accepts_pretty_semantic_response_without_reformatting_raw_body() -> None:
    content = '{\n  "response_token" : "' + VALID_RESPONSE_TOKEN + '"\n}'
    events: list[dict] = []
    reply = OpenAICompatibleDnrdAnswerer(
        OpenAICompatibleDnrdConfig("http://endpoint"),
        RecordingTransport([_completion(content=content)]), event_sink=events.append,
    ).answer(_request())
    assert reply.response_token == VALID_RESPONSE_TOKEN
    assert json.loads(events[-1]["raw_response_utf8"])["choices"][0]["message"]["content"] == content
    assert hashlib.sha256(events[-1]["raw_response_utf8"].encode()).hexdigest() == events[-1]["raw_response_sha256"]


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"model": "wrong", "choices": [{"finish_reason": "stop", "message": {"content": VALID_STRUCTURED_CONTENT}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}, "model"),
        ({"model": MODEL_ID, "choices": [{"finish_reason": "stop", "message": {"content": "one"}}, {"finish_reason": "stop", "message": {"content": "two"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}, "exactly one"),
        ({"model": MODEL_ID, "choices": [{"finish_reason": "stop", "message": {"content": 3}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}, "textual"),
        ({"model": MODEL_ID, "choices": [{"finish_reason": "stop", "message": {"content": VALID_STRUCTURED_CONTENT}}], "usage": {"prompt_tokens": True, "completion_tokens": 1, "total_tokens": 2}}, "integer"),
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
    events: list[dict] = []
    with pytest.raises(LiveBoundaryError, match="finish"):
        OpenAICompatibleDnrdAnswerer(
            OpenAICompatibleDnrdConfig("http://endpoint"), RecordingTransport([unfinished]), event_sink=events.append
        ).answer(_request())
    assert [event["event"] for event in events] == ["CHAT_COMPLETION_OBSERVED", "CHAT_COMPLETION_REJECTED"]
    rejected = events[1]
    assert rejected["failure_stage_code"] == "FINISH_REASON_NOT_STOP"
    assert rejected["failure_message_sha256"] == hashlib.sha256(
        b"chat completion choice must finish with exact reason 'stop'"
    ).hexdigest()
    assert rejected["failure_message"] == "chat completion choice must finish with exact reason 'stop'"
    assert rejected["raw_response_encoding"] == "base64"
    assert rejected["raw_response_bytes"] == len(unfinished.body)
    assert base64.b64decode(rejected["raw_response_base64"], validate=True) == unfinished.body
    assert rejected["raw_response_sha256"] == hashlib.sha256(unfinished.body).hexdigest()
    assert "authorization" not in rejected and "api_key" not in rejected
    arithmetic = HttpResponse(200, json.dumps({"model": MODEL_ID, "choices": [{"finish_reason": "stop", "message": {"content": VALID_STRUCTURED_CONTENT}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 3}}).encode())
    with pytest.raises(LiveBoundaryError, match="total_tokens"):
        OpenAICompatibleDnrdAnswerer(OpenAICompatibleDnrdConfig("http://endpoint"), RecordingTransport([arithmetic])).answer(_request())


def test_answerer_retains_non_utf8_rejection_as_exact_base64() -> None:
    raw = b"\xffnot-json"
    events: list[dict] = []
    with pytest.raises(LiveBoundaryError, match="UTF-8"):
        OpenAICompatibleDnrdAnswerer(
            OpenAICompatibleDnrdConfig("http://endpoint"), RecordingTransport([HttpResponse(200, raw)]), event_sink=events.append
        ).answer(_request())
    rejected = events[-1]
    assert rejected["event"] == "CHAT_COMPLETION_REJECTED"
    assert rejected["failure_stage_code"] == "CHAT_COMPLETION_NOT_UTF8_JSON"
    assert base64.b64decode(rejected["raw_response_base64"], validate=True) == raw


def test_answerer_rejects_noncanonical_dnrd4_response_token_at_live_boundary() -> None:
    events: list[dict] = []
    with pytest.raises(LiveBoundaryError, match="exact DNRD-4 form"):
        OpenAICompatibleDnrdAnswerer(
            OpenAICompatibleDnrdConfig("http://endpoint"),
            RecordingTransport([_completion(content=json.dumps({"response_token": "token-short"}))]),
            event_sink=events.append,
        ).answer(_request())
    assert [event["event"] for event in events] == [
        "CHAT_COMPLETION_OBSERVED",
        "CHAT_COMPLETION_REJECTED",
    ]
    assert events[-1]["failure_stage_code"] == "RESPONSE_TOKEN_FORM_INVALID"


@pytest.mark.parametrize(
    ("content", "stage_code"),
    [
        ("not-json", "STRUCTURED_RESPONSE_NOT_STRICT_JSON"),
        ('{"response_token":"' + VALID_RESPONSE_TOKEN + '","response_token":"' + OTHER_VALID_RESPONSE_TOKEN + '"}', "STRUCTURED_RESPONSE_NOT_STRICT_JSON"),
        (json.dumps({"token": VALID_RESPONSE_TOKEN}), "STRUCTURED_RESPONSE_KEYSET_INVALID"),
        (json.dumps({"response_token": VALID_RESPONSE_TOKEN, "extra": "x"}), "STRUCTURED_RESPONSE_KEYSET_INVALID"),
        (json.dumps({"response_token": "token-cccccccccccccccccccc"}), "RESPONSE_TOKEN_NOT_REQUEST_CANDIDATE"),
    ],
)
def test_answerer_refuses_wrong_structured_json_key_or_candidate_token(content: str, stage_code: str) -> None:
    events: list[dict] = []
    with pytest.raises(LiveBoundaryError):
        OpenAICompatibleDnrdAnswerer(
            OpenAICompatibleDnrdConfig("http://endpoint"),
            RecordingTransport([_completion(content=content)]),
            event_sink=events.append,
        ).answer(_request())
    assert [event["event"] for event in events] == ["CHAT_COMPLETION_OBSERVED", "CHAT_COMPLETION_REJECTED"]
    assert events[-1]["failure_stage_code"] == stage_code


def test_answerer_retains_non_2xx_body_for_exact_replay() -> None:
    raw = b'{"error":"overloaded"}'
    events: list[dict] = []
    with pytest.raises(LiveBoundaryError, match="HTTP response status 503"):
        OpenAICompatibleDnrdAnswerer(
            OpenAICompatibleDnrdConfig("http://endpoint"), RecordingTransport([HttpResponse(503, raw)]), event_sink=events.append
        ).answer(_request())
    assert [event["event"] for event in events] == ["CHAT_COMPLETION_OBSERVED", "CHAT_COMPLETION_REJECTED"]
    rejected = events[-1]
    assert rejected["failure_stage_code"] == "HTTP_STATUS_NOT_2XX"
    assert rejected["failure_message"] == "HTTP response status 503"
    assert base64.b64decode(rejected["raw_response_base64"], validate=True) == raw


@pytest.mark.parametrize(
    ("usage", "stage_code"),
    [
        ({"prompt_tokens": True, "completion_tokens": 1, "total_tokens": 2}, "USAGE_PROMPT_TOKENS_INVALID"),
        ({"prompt_tokens": 1, "completion_tokens": -1, "total_tokens": 0}, "USAGE_COMPLETION_TOKENS_INVALID"),
        ({"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": "2"}, "USAGE_TOTAL_TOKENS_INVALID"),
    ],
)
def test_answerer_assigns_exhaustive_usage_rejection_codes(usage: dict, stage_code: str) -> None:
    raw = json.dumps({
        "model": MODEL_ID,
        "choices": [{"finish_reason": "stop", "message": {"content": VALID_STRUCTURED_CONTENT}}],
        "usage": usage,
    }).encode()
    events: list[dict] = []
    with pytest.raises(LiveBoundaryError):
        OpenAICompatibleDnrdAnswerer(
            OpenAICompatibleDnrdConfig("http://endpoint"), RecordingTransport([HttpResponse(200, raw)]), event_sink=events.append
        ).answer(_request())
    assert [event["event"] for event in events] == ["CHAT_COMPLETION_OBSERVED", "CHAT_COMPLETION_REJECTED"]
    assert events[-1]["failure_stage_code"] == stage_code
    assert events[-1]["failure_message_sha256"] == hashlib.sha256(events[-1]["failure_message"].encode()).hexdigest()


def test_answerer_rejects_non_http_transport_without_fake_empty_response() -> None:
    events: list[dict] = []
    transport = RecordingTransport([])
    transport.outcomes.append(object())  # type: ignore[arg-type]
    with pytest.raises(LiveBoundaryError, match="exact HTTP observation"):
        OpenAICompatibleDnrdAnswerer(
            OpenAICompatibleDnrdConfig("http://endpoint", api_key="must-not-appear"), transport, event_sink=events.append
        ).answer(_request())
    assert [event["event"] for event in events] == ["TRANSPORT_RESPONSE_REJECTED"]
    rejected = events[0]
    assert rejected["schema_version"] == EVENT_SCHEMA
    assert rejected["failure_stage_code"] == "TRANSPORT_RESPONSE_NOT_EXACT_HTTP_RESPONSE"
    assert not any(key.startswith("raw_response") for key in rejected)
    assert "headers" not in rejected and "api_key" not in rejected and "must-not-appear" not in json.dumps(rejected)


def test_answerer_distinguishes_an_actual_empty_http_body_from_invalid_transport_shape() -> None:
    events: list[dict] = []
    with pytest.raises(LiveBoundaryError, match="UTF-8 JSON"):
        OpenAICompatibleDnrdAnswerer(
            OpenAICompatibleDnrdConfig("http://endpoint"), RecordingTransport([HttpResponse(200, b"")]), event_sink=events.append
        ).answer(_request())
    assert [event["event"] for event in events] == ["CHAT_COMPLETION_OBSERVED", "CHAT_COMPLETION_REJECTED"]
    rejected = events[-1]
    assert rejected["raw_response_bytes"] == 0
    assert rejected["raw_response_base64"] == ""


def test_answerer_enforces_own_response_cap_without_serializing_oversized_body() -> None:
    raw = b"x" * (MAX_ANSWERER_RESPONSE_BYTES + 9)
    events: list[dict] = []
    with pytest.raises(LiveBoundaryError, match="1 MiB"):
        OpenAICompatibleDnrdAnswerer(
            OpenAICompatibleDnrdConfig("http://endpoint"), RecordingTransport([HttpResponse(200, raw)]), event_sink=events.append
        ).answer(_request())
    assert [event["event"] for event in events] == ["CHAT_COMPLETION_REJECTED"]
    rejected = events[0]
    assert rejected["failure_stage_code"] == "RESPONSE_BODY_EXCEEDS_1_MIB"
    prefix = raw[:MAX_ANSWERER_RESPONSE_BYTES + 1]
    assert rejected["retained_response_prefix_encoding"] == "base64"
    assert base64.b64decode(rejected["retained_response_prefix_base64"], validate=True) == prefix
    assert rejected["retained_response_prefix_sha256"] == hashlib.sha256(prefix).hexdigest()
    assert rejected["retained_response_prefix_bytes"] == MAX_ANSWERER_RESPONSE_BYTES + 1
    assert rejected["response_body_bytes_lower_bound"] == MAX_ANSWERER_RESPONSE_BYTES + 1
    assert not any(key.startswith("raw_response_") for key in rejected)


def test_production_urllib_oversize_retains_exact_prefix_instead_of_ambiguous_failure() -> None:
    raw = b"z" * (MAX_ANSWERER_RESPONSE_BYTES + 23)

    class Response:
        status = 200

        def read(self, limit: int) -> bytes:
            assert limit == MAX_ANSWERER_RESPONSE_BYTES + 1
            return raw[:limit]

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    class Opener:
        calls = 0

        def open(self, *_: object, **__: object) -> Response:
            self.calls += 1
            return Response()

    transport = UrllibHttpTransport()
    opener = Opener()
    transport._opener = opener  # type: ignore[attr-defined]
    events: list[dict] = []
    with pytest.raises(LiveBoundaryError, match="1 MiB"):
        OpenAICompatibleDnrdAnswerer(
            OpenAICompatibleDnrdConfig("http://endpoint", api_key="must-not-appear"), transport, event_sink=events.append
        ).answer(_request())
    assert opener.calls == 1
    assert [event["event"] for event in events] == ["CHAT_COMPLETION_REJECTED"]
    rejected = events[0]
    prefix = raw[:MAX_ANSWERER_RESPONSE_BYTES + 1]
    assert base64.b64decode(rejected["retained_response_prefix_base64"], validate=True) == prefix
    assert rejected["retained_response_prefix_sha256"] == hashlib.sha256(prefix).hexdigest()
    assert rejected["retained_response_prefix_bytes"] == MAX_ANSWERER_RESPONSE_BYTES + 1
    assert rejected["response_body_bytes_lower_bound"] == MAX_ANSWERER_RESPONSE_BYTES + 1
    assert rejected["http_status"] == 200
    assert "must-not-appear" not in json.dumps(rejected)


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
