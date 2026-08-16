from __future__ import annotations

import json
from urllib import error as urlerror

import pytest

from hswm.cells.openai import (
    FixtureCellPort,
    ModelProtocolError,
    OpenAICompatibleCellPort,
    OpenAICompatibleConfig,
    UnknownModelOutcome,
)
from hswm.cells.runtime import InvokeCellEffect, make_packet


def effect(payload=None):
    return InvokeCellEffect(
        activation_id="activation-1",
        cell_id="cell-a",
        input=make_packet(
            packet_id="input-1",
            packet_type="question/v1",
            payload=payload if payload is not None else {"prompt": "Return four"},
            provenance={"source": "adapter-test"},
        ),
        expected_output_type="answer/v1",
    )


class FakeResponse:
    def __init__(self, value):
        self.raw = json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, limit):
        return self.raw[:limit]


def test_openai_compatible_adapter_builds_typed_packet(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "model": "fixture-model",
                "choices": [{"message": {"content": "4"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1},
            }
        )

    monkeypatch.setattr("hswm.cells.openai.urlrequest.urlopen", fake_urlopen)
    port = OpenAICompatibleCellPort(
        OpenAICompatibleConfig(
            base_url="http://model.invalid",
            model="fixture-model",
            api_key="secret-not-persisted",
            timeout_seconds=3,
        )
    )
    output = port.invoke(effect())
    assert port.calls == 1
    assert output.packet_type == "answer/v1"
    assert output.payload["text"] == "4"
    assert output.payload["model"] == "fixture-model"
    assert captured["timeout"] == 3
    assert captured["request"].get_header("X-idempotency-key") == "activation-1"
    body = json.loads(captured["request"].data.decode("utf-8"))
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert "secret-not-persisted" not in json.dumps(output.payload)


def test_transport_failure_is_unknown_not_safe_retry(monkeypatch) -> None:
    def fail(request, timeout):
        raise urlerror.URLError("connection reset")

    monkeypatch.setattr("hswm.cells.openai.urlrequest.urlopen", fail)
    port = OpenAICompatibleCellPort(
        OpenAICompatibleConfig(base_url="http://model.invalid", model="m")
    )
    with pytest.raises(UnknownModelOutcome):
        port.invoke(effect())


def test_invalid_input_never_reaches_transport(monkeypatch) -> None:
    called = False

    def fake_urlopen(request, timeout):
        nonlocal called
        called = True
        return FakeResponse({})

    monkeypatch.setattr("hswm.cells.openai.urlrequest.urlopen", fake_urlopen)
    port = OpenAICompatibleCellPort(
        OpenAICompatibleConfig(base_url="http://model.invalid", model="m")
    )
    with pytest.raises(ModelProtocolError, match="requires messages or prompt"):
        port.invoke(effect({"not_prompt": 1}))
    assert port.calls == 0
    assert called is False


def test_malformed_response_is_protocol_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "hswm.cells.openai.urlrequest.urlopen",
        lambda request, timeout: FakeResponse({"choices": []}),
    )
    port = OpenAICompatibleCellPort(
        OpenAICompatibleConfig(base_url="http://model.invalid", model="m")
    )
    with pytest.raises(ModelProtocolError, match="invalid chat-completions"):
        port.invoke(effect())


def test_fixture_port_is_deterministic() -> None:
    left = FixtureCellPort(response_text="4").invoke(effect())
    right = FixtureCellPort(response_text="4").invoke(effect())
    assert left == right
