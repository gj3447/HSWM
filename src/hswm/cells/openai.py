"""Explicit OpenAI-compatible and deterministic fixture ports for HSWM cells."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import socket
from typing import Any, Mapping
from urllib import error as urlerror
from urllib import request as urlrequest

from .runtime import (
    InvokeCellEffect,
    PacketEnvelope,
    canonical_json_bytes,
    make_packet,
)


class CellAdapterError(RuntimeError):
    safe_to_retry = False


class SafeBeforeSendError(CellAdapterError):
    """The adapter proves that no request bytes were sent."""

    safe_to_retry = True


class UnknownModelOutcome(CellAdapterError):
    """The endpoint may have received or executed the request."""


class ModelProtocolError(CellAdapterError):
    """A response arrived but did not satisfy the adapter contract."""


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout_seconds: float = 60.0
    max_tokens: int = 256
    temperature: float = 0.0
    enable_thinking: bool = False
    max_response_bytes: int = 2_000_000

    def __post_init__(self) -> None:
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must use http or https")
        if not self.model:
            raise ValueError("model must be non-empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_tokens <= 0 or self.max_response_bytes <= 0:
            raise ValueError("max_tokens and max_response_bytes must be positive")
        if self.temperature < 0:
            raise ValueError("temperature must be non-negative")


class OpenAICompatibleCellPort:
    def __init__(self, config: OpenAICompatibleConfig) -> None:
        self.config = config
        self.calls = 0

    def _messages(self, payload: Any) -> list[dict[str, str]]:
        if isinstance(payload, Mapping) and isinstance(payload.get("messages"), list):
            messages = payload["messages"]
            if not messages or any(
                not isinstance(item, Mapping)
                or item.get("role") not in {"system", "user", "assistant"}
                or not isinstance(item.get("content"), str)
                for item in messages
            ):
                raise ModelProtocolError("payload messages are invalid")
            return [
                {"role": str(item["role"]), "content": str(item["content"])}
                for item in messages
            ]
        if isinstance(payload, Mapping) and isinstance(payload.get("prompt"), str):
            return [{"role": "user", "content": payload["prompt"]}]
        if isinstance(payload, str):
            return [{"role": "user", "content": payload}]
        raise ModelProtocolError("input payload requires messages or prompt")

    def invoke(self, effect: InvokeCellEffect) -> PacketEnvelope:
        messages = self._messages(effect.input.payload)
        request_value = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "chat_template_kwargs": {
                "enable_thinking": self.config.enable_thinking
            },
        }
        request_bytes = canonical_json_bytes(request_value)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Idempotency-Key": effect.activation_id,
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        endpoint = self.config.base_url.rstrip("/") + "/v1/chat/completions"
        http_request = urlrequest.Request(
            endpoint,
            data=request_bytes,
            headers=headers,
            method="POST",
        )
        self.calls += 1
        try:
            with urlrequest.urlopen(
                http_request, timeout=self.config.timeout_seconds
            ) as response:
                raw = response.read(self.config.max_response_bytes + 1)
        except urlerror.HTTPError as error:
            body = error.read(2048).decode("utf-8", errors="replace")
            raise UnknownModelOutcome(
                f"HTTP {error.code} from model endpoint: {body[:500]}"
            ) from error
        except (urlerror.URLError, TimeoutError, socket.timeout, OSError) as error:
            raise UnknownModelOutcome(f"model transport outcome unknown: {error}") from error
        if len(raw) > self.config.max_response_bytes:
            raise ModelProtocolError("model response exceeds configured byte limit")
        try:
            response_value = json.loads(raw.decode("utf-8"))
            choice = response_value["choices"][0]
            text = choice["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise ModelProtocolError(f"invalid chat-completions response: {error}") from error
        if not isinstance(text, str) or not text.strip():
            raise ModelProtocolError("model returned empty non-text content")
        response_sha = sha256(raw).hexdigest()
        return make_packet(
            packet_id=f"packet-{effect.activation_id}-{response_sha[:16]}",
            packet_type=effect.expected_output_type,
            payload={
                "text": text,
                "model": response_value.get("model", self.config.model),
                "usage": response_value.get("usage"),
                "response_sha256": response_sha,
            },
            provenance={
                "adapter": "openai-compatible/v1",
                "activation_id": effect.activation_id,
                "cell_id": effect.cell_id,
                "request_sha256": sha256(request_bytes).hexdigest(),
                "response_sha256": response_sha,
            },
        )


class FixtureCellPort:
    """Deterministic adapter used for contract and crash-window tests."""

    def __init__(self, *, response_text: str = "fixture-ok") -> None:
        if not response_text:
            raise ValueError("response_text must be non-empty")
        self.response_text = response_text
        self.calls = 0

    def invoke(self, effect: InvokeCellEffect) -> PacketEnvelope:
        self.calls += 1
        input_sha = sha256(canonical_json_bytes(effect.input.payload)).hexdigest()
        return make_packet(
            packet_id=f"fixture-{effect.activation_id}-{input_sha[:12]}",
            packet_type=effect.expected_output_type,
            payload={
                "text": self.response_text,
                "input_sha256": input_sha,
                "cell_id": effect.cell_id,
            },
            provenance={
                "adapter": "fixture/v1",
                "activation_id": effect.activation_id,
                "input_sha256": input_sha,
            },
        )


__all__ = [
    "CellAdapterError",
    "FixtureCellPort",
    "ModelProtocolError",
    "OpenAICompatibleCellPort",
    "OpenAICompatibleConfig",
    "SafeBeforeSendError",
    "UnknownModelOutcome",
]
