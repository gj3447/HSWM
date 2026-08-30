from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Callable, Mapping

import pytest

from hswm.experiments.alfworld_b0_actor import (
    ALFWorldB0Actor,
    ALFWorldB0ActorError,
    B0_ACTION_MAX_OUTPUT_TOKENS,
    B0_ACTION_PROTOCOL,
    B0ActionBudget,
)
from hswm.experiments.continual_live import (
    ModelCompletion,
    TOKEN_PREFLIGHT_MODE,
    TokenPreflightReceipt,
    STRUCTURED_OUTPUT_MODE,
)
from hswm.selfmod.contracts import canonical_json_bytes


class ScriptedBackend:
    def __init__(self, text: str = '{"action":"look"}', *, model: str = "test-model") -> None:
        self.text = text
        self.model = model
        self.returned_model = model
        self.calls: list[tuple[str, bytes]] = []

    @property
    def identity(self) -> Mapping[str, Any]:
        return {
            "enable_thinking": False,
            "expected_max_model_len": 1024,
            "model": self.model,
            "response_format_mode": STRUCTURED_OUTPUT_MODE,
            "seed": 0,
            "temperature": 0.0,
            "token_preflight_mode": TOKEN_PREFLIGHT_MODE,
            "top_p": 1.0,
        }

    def tokenize(self, *, raw_request: bytes, source_chat_request_sha256: str, max_output_tokens: int, request_id: str, response_observer: Callable[[bytes, bytes, int | None, bool], None]) -> TokenPreflightReceipt:
        self.calls.append(("tokenize", raw_request))
        response = canonical_json_bytes({"count": 11, "max_model_len": 1024, "token_strs": None, "tokens": list(range(11))})
        response_observer(raw_request, response, 200, True)
        return TokenPreflightReceipt.make(raw_request=raw_request, raw_response=response, source_chat_request_sha256=source_chat_request_sha256, max_output_tokens=max_output_tokens, http_status=200, latency_ms=3, raw_response_complete=True)

    def complete(self, *, raw_request: bytes, request_id: str, response_observer: Callable[[bytes, bytes], None]) -> ModelCompletion:
        self.calls.append(("complete", raw_request))
        response = canonical_json_bytes({"choices": [{"finish_reason": "stop", "message": {"content": self.text}}], "model": self.returned_model, "usage": {"completion_tokens": 2, "prompt_tokens": 11, "total_tokens": 13}})
        response_observer(raw_request, response)
        return ModelCompletion(text=self.text, raw_request_json=raw_request.decode(), raw_response_json=response.decode(), request_sha256=sha256(raw_request).hexdigest(), response_sha256=sha256(response).hexdigest(), model=self.returned_model, input_tokens=11, output_tokens=2, latency_ms=7, usage_reported=True)


def test_one_shot_action_is_canonical_and_has_no_observation_in_receipt() -> None:
    backend = ScriptedBackend()
    actor = ALFWorldB0Actor(backend)
    receipt = actor.act(episode_uid="episode:one", step_index=0, history=[], observation="You are in a kitchen.")
    assert receipt.action == "look"
    assert receipt.protocol == B0_ACTION_PROTOCOL
    assert receipt.completion_call_count == 1
    assert receipt.completion_call_index == 1
    assert receipt.tokenize_call_count == 1
    assert receipt.tokenize_call_index == 1
    assert receipt.token_preflight_token_count == 11
    assert receipt.receipt_sha256 == sha256(canonical_json_bytes(receipt.unsigned())).hexdigest()
    assert "observation" not in receipt.canonical()
    assert "history" not in receipt.canonical()
    assert len(backend.calls) == 2
    chat = json.loads(backend.calls[1][1])
    assert chat["max_tokens"] == B0_ACTION_MAX_OUTPUT_TOKENS
    assert chat["messages"][0]["role"] == "system"
    assert json.loads(chat["messages"][1]["content"]) == {"episode_uid": "episode:one", "history": [], "observation": "You are in a kitchen.", "protocol": B0_ACTION_PROTOCOL, "step_index": 0}
    actor.act(episode_uid="episode:two", step_index=0, history=[], observation="A new room.")
    assert actor.request_counts == (2, 2)
    second = json.loads(backend.calls[-1][1])
    assert json.loads(second["messages"][1]["content"])["history"] == []


def test_explicit_within_episode_history_is_included_without_actor_persistence() -> None:
    backend = ScriptedBackend()
    ALFWorldB0Actor(backend).act(
        episode_uid="episode:one",
        step_index=1,
        history=[{"observation": "You are in a kitchen.", "action": "look"}],
        observation="You see an apple.",
    )
    payload = json.loads(json.loads(backend.calls[-1][1])["messages"][1]["content"])
    assert payload["history"] == [{"action": "look", "observation": "You are in a kitchen."}]


def test_history_is_only_ordered_prior_pairs() -> None:
    with pytest.raises(ALFWorldB0ActorError, match="exact observation/action"):
        ALFWorldB0Actor(ScriptedBackend()).act(
            episode_uid="episode:one",
            step_index=1,
            history=[{"observation": "room", "action": "look", "outcome": "won"}],
            observation="room",
        )
    with pytest.raises(ALFWorldB0ActorError, match="exactly one prior pair"):
        ALFWorldB0Actor(ScriptedBackend()).act(
            episode_uid="episode:one", step_index=1, history=[], observation="room"
        )


@pytest.mark.parametrize("text", [
    '{"action":"look","extra":1}',
    '{"action":"look\\n"}',
    '{"action":"é"}',
    '{"action":""}',
])
def test_rejects_non_exact_or_non_ascii_actions(text: str) -> None:
    with pytest.raises(ALFWorldB0ActorError):
        ALFWorldB0Actor(ScriptedBackend(text)).act(episode_uid="episode:one", step_index=0, history=[], observation="room")


def test_accepts_json_whitespace_without_requiring_provider_byte_exactness() -> None:
    receipt = ALFWorldB0Actor(ScriptedBackend('  {"action" : "look"}\n')).act(
        episode_uid="episode:one", step_index=0, history=[], observation="room"
    )
    assert receipt.action == "look"
    assert receipt.canonical()["action"] == "look"


def test_rejects_request_over_budget_before_network_call() -> None:
    backend = ScriptedBackend()
    with pytest.raises(ALFWorldB0ActorError, match="byte budget"):
        ALFWorldB0Actor(backend, budget=B0ActionBudget(max_input_bytes=1)).act(episode_uid="episode:one", step_index=0, history=[], observation="room")
    assert backend.calls == []


def test_refuses_action_21_before_any_network_call() -> None:
    backend = ScriptedBackend()
    history = [{"observation": "room", "action": "look"}] * 20
    with pytest.raises(ALFWorldB0ActorError, match="20 permitted actions"):
        ALFWorldB0Actor(backend).act(
            episode_uid="episode:one",
            step_index=20,
            history=history,
            observation="room",
        )
    assert backend.calls == []


def test_sealed_gate_and_pretransport_caps_fail_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hswm.experiments import alfworld_b0_actor as module

    monkeypatch.setattr(module, "B0_MAX_TOKENIZE_CALLS", 1)
    backend = ScriptedBackend()
    actor = ALFWorldB0Actor(backend)
    actor.act(episode_uid="episode:one", step_index=0, history=[], observation="room")
    with pytest.raises(ALFWorldB0ActorError, match="cap exhausted"):
        actor.act(episode_uid="episode:two", step_index=0, history=[], observation="room")
    assert [kind for kind, _ in backend.calls] == ["tokenize", "complete"]
    assert actor.seal() == (1, 1)
    with pytest.raises(ALFWorldB0ActorError, match="sealed"):
        actor.act(episode_uid="episode:three", step_index=0, history=[], observation="room")


def test_rejects_completion_model_drift() -> None:
    backend = ScriptedBackend()
    backend.returned_model = "other"
    with pytest.raises(ALFWorldB0ActorError, match="completion model"):
        ALFWorldB0Actor(backend).act(episode_uid="episode:one", step_index=0, history=[], observation="room")
