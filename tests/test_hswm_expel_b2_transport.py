from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Callable, Mapping

import pytest

from hswm.experiments.continual_live import (
    ModelCompletion,
    STRUCTURED_OUTPUT_MODE,
    TOKEN_PREFLIGHT_MODE,
    TokenPreflightReceipt,
)
from hswm.experiments.expel_b2_text_lesson import render_lesson
from hswm.experiments.expel_b2_transport import (
    MAX_ACTION_POSTS, MAX_REFLECTION_POSTS,
    B2ActionReceipt,
    ExpelB2RequestGate,
    ExpelB2Transport,
    ExpelB2TransportError,
)
from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256


class ScriptedBackend:
    def __init__(self, *, action: str = '{"action":"look"}', reflection: str = '{"rule":"Inspect before acting."}') -> None:
        self.action = action
        self.reflection = reflection
        self.calls: list[tuple[str, bytes]] = []
        self.fail_tokenize = False
        self.fail_complete = False
        self.usage_reported = True
        self.reject_multiple_system_messages = False

    @property
    def identity(self) -> Mapping[str, Any]:
        return {
            "enable_thinking": False, "expected_max_model_len": 4096,
            "model": "test-model", "response_format_mode": STRUCTURED_OUTPUT_MODE,
            "seed": 0, "temperature": 0.0, "token_preflight_mode": TOKEN_PREFLIGHT_MODE,
            "top_p": 1.0, "timeout_seconds": 120.0,
        }

    def tokenize(self, *, raw_request: bytes, source_chat_request_sha256: str, max_output_tokens: int, request_id: str, response_observer: Callable[[bytes, bytes, int | None, bool], None]) -> TokenPreflightReceipt:
        self.calls.append(("tokenize", raw_request))
        messages = json.loads(raw_request)["messages"]
        if self.reject_multiple_system_messages and sum(item["role"] == "system" for item in messages) > 1:
            raise RuntimeError("System message must be at the beginning.")
        if self.fail_tokenize:
            raise RuntimeError("tokenize transport failed")
        response = canonical_json_bytes({"count": 11, "max_model_len": 4096, "token_strs": None, "tokens": list(range(11))})
        response_observer(raw_request, response, 200, True)
        return TokenPreflightReceipt.make(raw_request=raw_request, raw_response=response, source_chat_request_sha256=source_chat_request_sha256, max_output_tokens=max_output_tokens, http_status=200, latency_ms=4, raw_response_complete=True)

    def complete(self, *, raw_request: bytes, request_id: str, response_observer: Callable[[bytes, bytes], None]) -> ModelCompletion:
        self.calls.append(("complete", raw_request))
        if self.fail_complete:
            raise RuntimeError("completion transport failed")
        schema_name = json.loads(raw_request)["response_format"]["json_schema"]["name"]
        text = self.reflection if schema_name == "hswm_expel_b2_reflection" else self.action
        envelope: dict[str, object] = {"choices": [{"finish_reason": "stop", "message": {"content": text}}], "model": "test-model"}
        if self.usage_reported:
            envelope["usage"] = {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14}
        response = canonical_json_bytes(envelope)
        response_observer(raw_request, response)
        return ModelCompletion(text=text, raw_request_json=raw_request.decode(), raw_response_json=response.decode(), request_sha256=sha256(raw_request).hexdigest(), response_sha256=sha256(response).hexdigest(), model="test-model", input_tokens=11 if self.usage_reported else 0, output_tokens=3 if self.usage_reported else 0, latency_ms=7, usage_reported=self.usage_reported)


def _sealed_success() -> dict[str, object]:
    visible = "look\nYou see an apple.\ntake apple"
    return {
        "episode_uid": "train:001",
        "terminal_seal_sha256": "a" * 64,
        "trajectory_sha256": sha256(visible.encode()).hexdigest(),
        "visible_trajectory_utf8": visible,
    }


def test_action_uses_frozen_lesson_and_returns_hashed_usage_receipt() -> None:
    backend = ScriptedBackend()
    receipt = ExpelB2Transport(backend).act(
        lesson_utf8=render_lesson(()), episode_uid="heldout:001", step_index=0,
        history=[], observation="You are in a kitchen.",
    )
    assert isinstance(receipt, B2ActionReceipt)
    assert receipt.action == "look"
    assert receipt.completion.input_tokens == 11 and receipt.completion.output_tokens == 3
    assert receipt.receipt_sha256 == canonical_sha256(receipt.unsigned())
    chat = json.loads(backend.calls[1][1])
    assert [item["role"] for item in chat["messages"]] == ["system", "user"]
    assert chat["messages"][0]["content"].endswith("\n\n" + render_lesson(()))


def test_action_template_accepts_exactly_one_leading_system_message_without_losing_posts() -> None:
    backend = ScriptedBackend(); backend.reject_multiple_system_messages = True
    transport = ExpelB2Transport(backend)
    receipt = transport.act(lesson_utf8=render_lesson(()), episode_uid="heldout:001", step_index=0, history=[], observation="room")
    assert receipt.action == "look"
    assert transport.request_counts == {"action_tokenize": 1, "action_completion": 1, "reflection_tokenize": 0, "reflection_completion": 0}


def test_reflection_uses_only_supplied_sealed_success_payload_and_strict_rule_schema() -> None:
    backend = ScriptedBackend()
    receipt = ExpelB2Transport(backend).reflect_success(sealed_success=_sealed_success())
    assert receipt.rule_utf8 == "Inspect before acting."
    assert receipt.receipt_sha256 == canonical_sha256(receipt.unsigned())
    user = json.loads(json.loads(backend.calls[1][1])["messages"][1]["content"])
    assert user == _sealed_success()


@pytest.mark.parametrize("action,reflection", [
    ('{"action":"look","extra":1}', '{"rule":"Good."}'),
    ('{"action":"look"}', '{"rule":"one\\ntwo"}'),
])
def test_invalid_strict_json_reserves_both_posts_before_failing(action: str, reflection: str) -> None:
    transport = ExpelB2Transport(ScriptedBackend(action=action, reflection=reflection))
    if action != '{"action":"look"}':
        with pytest.raises(ExpelB2TransportError, match="strict schema"):
            transport.act(lesson_utf8=render_lesson(()), episode_uid="heldout:001", step_index=0, history=[], observation="room")
        assert transport.request_counts == {"action_tokenize": 1, "action_completion": 1, "reflection_tokenize": 0, "reflection_completion": 0}
    else:
        with pytest.raises(ExpelB2TransportError, match="strict schema"):
            transport.reflect_success(sealed_success=_sealed_success())
        assert transport.request_counts == {"action_tokenize": 0, "action_completion": 0, "reflection_tokenize": 1, "reflection_completion": 1}


def test_transport_failure_is_preserved_after_pre_network_reservation() -> None:
    backend = ScriptedBackend(); backend.fail_tokenize = True
    transport = ExpelB2Transport(backend)
    with pytest.raises(RuntimeError, match="tokenize transport failed"):
        transport.act(lesson_utf8=render_lesson(()), episode_uid="heldout:001", step_index=0, history=[], observation="room")
    assert transport.request_counts == {"action_tokenize": 1, "action_completion": 0, "reflection_tokenize": 0, "reflection_completion": 0}
    assert transport.events[0].outcome == "FAILED" and transport.events[0].response_sha256 is None


def test_event_sink_receives_reserved_request_hash_before_network_failure() -> None:
    backend = ScriptedBackend(); backend.fail_tokenize = True
    persisted = []
    transport = ExpelB2Transport(backend, event_sink=persisted.append)
    with pytest.raises(RuntimeError, match="tokenize transport failed"):
        transport.act(lesson_utf8=render_lesson(()), episode_uid="heldout:001", step_index=0, history=[], observation="room")
    assert [event.outcome for event in persisted] == ["ISSUED_UNKNOWN", "FAILED"]
    assert persisted[0].request_sha256 == persisted[1].request_sha256
    assert persisted[0].request_sha256 == transport.events[0].request_sha256


def test_completion_failure_is_reserved_and_does_not_allow_refill() -> None:
    backend = ScriptedBackend(); backend.fail_complete = True
    transport = ExpelB2Transport(backend)
    with pytest.raises(RuntimeError, match="completion transport failed"):
        transport.reflect_success(sealed_success=_sealed_success())
    assert transport.request_counts == {"action_tokenize": 0, "action_completion": 0, "reflection_tokenize": 1, "reflection_completion": 1}
    assert [event.outcome for event in transport.events] == ["OBSERVED", "FAILED"]


def test_observable_usage_survives_invalid_model_json() -> None:
    transport = ExpelB2Transport(ScriptedBackend(action='{"action":"look","unexpected":1}'))
    with pytest.raises(ExpelB2TransportError, match="strict schema"):
        transport.act(lesson_utf8=render_lesson(()), episode_uid="heldout:001", step_index=0, history=[], observation="room")
    completion = transport.events[-1]
    assert completion.outcome == "OBSERVED"
    assert (completion.input_tokens, completion.output_tokens, completion.usage_reported) == (11, 3, True)


def test_missing_provider_usage_stays_unknown_in_the_request_event() -> None:
    backend = ScriptedBackend(); backend.usage_reported = False
    transport = ExpelB2Transport(backend)
    transport.act(lesson_utf8=render_lesson(()), episode_uid="heldout:001", step_index=0,
                  history=[], observation="room")
    completion = transport.events[-1]
    assert (completion.input_tokens, completion.output_tokens, completion.usage_reported) == (None, None, False)


def test_each_phase_allows_240_action_plus_8_reflection_posts_and_then_seals() -> None:
    gate = ExpelB2RequestGate()
    for _ in range(MAX_ACTION_POSTS):
        gate.reserve(operation="action", phase="tokenize")
    for index in range(MAX_REFLECTION_POSTS):
        assert gate.reserve(operation="reflection", phase="tokenize") == index + 1
    with pytest.raises(ExpelB2TransportError, match="cap exhausted"):
        gate.reserve(operation="action", phase="tokenize")
    with pytest.raises(ExpelB2TransportError, match="cap exhausted"):
        gate.reserve(operation="reflection", phase="tokenize")
    assert gate.seal()["action_tokenize"] == 240
    with pytest.raises(ExpelB2TransportError, match="sealed"):
        gate.reserve(operation="reflection", phase="completion")


def test_deadline_prevents_a_post_without_reserving_it() -> None:
    transport = ExpelB2Transport(ScriptedBackend())
    with pytest.raises(ExpelB2TransportError, match="wall-time"):
        transport.act(lesson_utf8=render_lesson(()), episode_uid="heldout:001", step_index=0, history=[], observation="room", deadline=1.0, monotonic=lambda: 1.0)
    assert transport.request_counts == {"action_tokenize": 0, "action_completion": 0, "reflection_tokenize": 0, "reflection_completion": 0}


def test_remaining_wall_time_must_cover_the_backend_request_timeout() -> None:
    transport = ExpelB2Transport(ScriptedBackend())
    with pytest.raises(ExpelB2TransportError, match="cannot cover"):
        transport.act(lesson_utf8=render_lesson(()), episode_uid="heldout:001", step_index=0,
                      history=[], observation="room", deadline=100.0, monotonic=lambda: 1.0)
    assert not transport.events


def test_action_reuses_the_b0_episode_local_history_contract_before_post() -> None:
    transport = ExpelB2Transport(ScriptedBackend())
    with pytest.raises(ExpelB2TransportError, match="exact observation/action"):
        transport.act(
            lesson_utf8=render_lesson(()), episode_uid="heldout:001", step_index=1,
            history=[{"observation": "room", "action": "look", "outcome": "win"}], observation="room",
        )
    assert not transport.events


def test_reflection_rejects_visible_trajectory_with_nonmatching_seal_digest_before_post() -> None:
    sealed = _sealed_success()
    sealed["trajectory_sha256"] = "b" * 64
    transport = ExpelB2Transport(ScriptedBackend())
    with pytest.raises(ExpelB2TransportError, match="trajectory digest"):
        transport.reflect_success(sealed_success=sealed)
    assert not transport.events
