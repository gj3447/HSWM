"""Model-call boundary and replayable receipts for PROM-9 functions."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from collections.abc import Callable, Mapping
from typing import Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from prom_search_hswm.hswm_function_registry import FunctionSpecV1
from prom_search_hswm.hswm_typed_ports import (
    canonical_json,
    canonical_sha256,
    port_digest,
    validate_port,
)


CALL_RECEIPT_SCHEMA = "hswm-prom9-call-receipt/v1"


class FunctionCallError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelCallV1:
    physical_call_id: str
    run_id: str
    arm_id: str
    item_id: str
    call_index: int
    function_id: str
    model: str
    model_revision: str
    system_prompt: str
    input_type: str
    input_payload: dict[str, object]
    output_type: str
    max_output_tokens: int


@dataclass(frozen=True)
class ModelResponseV1:
    payload: dict[str, object]
    model: str
    model_revision: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cache_status: str = "miss"
    retries: int = 0


class ModelPort(Protocol):
    def __call__(self, call: ModelCallV1) -> ModelResponseV1: ...


@dataclass(frozen=True)
class CallReceiptV1:
    physical_call_id: str
    run_id: str
    arm_id: str
    item_id: str
    call_index: int
    function_id: str
    model: str
    model_revision: str
    prompt_sha256: str
    input_type: str
    input_port_sha256: str
    input_payload: dict[str, object]
    output_type: str
    output_port_sha256: str
    output_payload: dict[str, object]
    allowed_output_tokens: int
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cache_status: str
    retries: int
    receipt_sha256: str
    schema_version: str = CALL_RECEIPT_SCHEMA

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "physical_call_id": self.physical_call_id,
            "run_id": self.run_id,
            "arm_id": self.arm_id,
            "item_id": self.item_id,
            "call_index": self.call_index,
            "function_id": self.function_id,
            "model": self.model,
            "model_revision": self.model_revision,
            "prompt_sha256": self.prompt_sha256,
            "input_type": self.input_type,
            "input_port_sha256": self.input_port_sha256,
            "input_payload": self.input_payload,
            "output_type": self.output_type,
            "output_port_sha256": self.output_port_sha256,
            "output_payload": self.output_payload,
            "allowed_output_tokens": self.allowed_output_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": self.latency_ms,
            "cache_status": self.cache_status,
            "retries": self.retries,
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FunctionCallError(f"{label} must be a non-negative integer")
    return value


def invoke_function(
    *,
    run_id: str,
    arm_id: str,
    item_id: str,
    call_index: int,
    function: FunctionSpecV1,
    input_payload: Mapping[str, object],
    max_output_tokens: int,
    model_port: ModelPort,
) -> tuple[dict[str, object], CallReceiptV1]:
    """Validate, execute once, validate again, and mint a self-hashed receipt."""

    if call_index not in {1, 2, 3}:
        raise FunctionCallError("call_index must be 1, 2, or 3")
    if isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int) or max_output_tokens < 1:
        raise FunctionCallError("max_output_tokens must be positive")
    normalized_input = validate_port(function.input_type, input_payload)
    call_identity = {
        "run_id": run_id,
        "arm_id": arm_id,
        "item_id": item_id,
        "call_index": call_index,
        "function_id": function.function_id,
        "registry_prompt_sha256": function.prompt_sha256,
        "input_port_sha256": port_digest(function.input_type, normalized_input),
    }
    call = ModelCallV1(
        physical_call_id=canonical_sha256(call_identity),
        run_id=run_id,
        arm_id=arm_id,
        item_id=item_id,
        call_index=call_index,
        function_id=function.function_id,
        model=function.model,
        model_revision=function.model_revision,
        system_prompt=function.prompt,
        input_type=function.input_type,
        input_payload=normalized_input,
        output_type=function.output_type,
        max_output_tokens=max_output_tokens,
    )
    response = model_port(call)
    if not isinstance(response, ModelResponseV1):
        raise FunctionCallError("model port returned an unsupported response")
    if response.model != function.model or response.model_revision != function.model_revision:
        raise FunctionCallError("model identity drifted at the call boundary")
    normalized_output = validate_port(function.output_type, response.payload)
    input_tokens = _nonnegative_int(response.input_tokens, "input_tokens")
    output_tokens = _nonnegative_int(response.output_tokens, "output_tokens")
    if output_tokens > max_output_tokens:
        raise FunctionCallError("model exceeded the registered output-token cap")
    latency_ms = _nonnegative_int(response.latency_ms, "latency_ms")
    retries = _nonnegative_int(response.retries, "retries")
    if response.cache_status not in {"miss", "hit", "provider-unknown"}:
        raise FunctionCallError("unknown cache status")
    unsigned = {
        "schema_version": CALL_RECEIPT_SCHEMA,
        "physical_call_id": call.physical_call_id,
        "run_id": run_id,
        "arm_id": arm_id,
        "item_id": item_id,
        "call_index": call_index,
        "function_id": function.function_id,
        "model": function.model,
        "model_revision": function.model_revision,
        "prompt_sha256": function.prompt_sha256,
        "input_type": function.input_type,
        "input_port_sha256": port_digest(function.input_type, normalized_input),
        "input_payload": normalized_input,
        "output_type": function.output_type,
        "output_port_sha256": port_digest(function.output_type, normalized_output),
        "output_payload": normalized_output,
        "allowed_output_tokens": max_output_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "cache_status": response.cache_status,
        "retries": retries,
    }
    receipt = CallReceiptV1(
        **{key: value for key, value in unsigned.items() if key != "schema_version"},
        receipt_sha256=canonical_sha256(unsigned),
    )
    return normalized_output, receipt


def verify_call_receipt(value: Mapping[str, object]) -> str:
    data = dict(value)
    if data.get("schema_version") != CALL_RECEIPT_SCHEMA:
        raise FunctionCallError("unsupported call receipt schema")
    declared = data.pop("receipt_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(data) != declared:
        raise FunctionCallError("call receipt self-hash drifted")
    if data.get("input_port_sha256") != port_digest(
        str(data.get("input_type")), data.get("input_payload")
    ):
        raise FunctionCallError("call receipt input port drifted")
    if data.get("output_port_sha256") != port_digest(
        str(data.get("output_type")), data.get("output_payload")
    ):
        raise FunctionCallError("call receipt output port drifted")
    return declared


class OpenAICompatibleJSONPort:
    """Minimal OpenAI-compatible transport used by the Mac mini runner.

    Authentication is read only from the named environment variable.  The key
    is never placed in a request receipt.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        api_key_env: str | None = None,
        timeout_seconds: float = 180.0,
        transport: Callable[[urllib_request.Request, float], bytes] | None = None,
    ) -> None:
        if not endpoint.startswith(("http://", "https://")):
            raise FunctionCallError("endpoint must be HTTP(S)")
        self.endpoint = endpoint
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds
        self._transport = transport or self._urlopen

    @staticmethod
    def _urlopen(request: urllib_request.Request, timeout: float) -> bytes:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            return response.read()

    def __call__(self, call: ModelCallV1) -> ModelResponseV1:
        body = {
            "model": call.model,
            "messages": [
                {"role": "system", "content": call.system_prompt},
                {"role": "user", "content": canonical_json(call.input_payload)},
            ],
            "temperature": 0,
            "top_p": 1,
            "max_tokens": call.max_output_tokens,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key_env:
            api_key = os.environ.get(self.api_key_env)
            if not api_key:
                raise FunctionCallError(f"missing API key environment: {self.api_key_env}")
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib_request.Request(
            self.endpoint,
            data=canonical_json(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.monotonic()
        try:
            raw = self._transport(request, self.timeout_seconds)
            envelope = json.loads(raw)
            content = envelope["choices"][0]["message"]["content"]
            payload = json.loads(content)
            usage = envelope["usage"]
            response_model = envelope["model"]
        except (urllib_error.URLError, TimeoutError, KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise FunctionCallError(f"model transport failed: {type(error).__name__}: {error}") from error
        if not isinstance(payload, dict):
            raise FunctionCallError("model content must be one JSON object")
        if response_model != call.model:
            raise FunctionCallError("served model identity drifted")
        return ModelResponseV1(
            payload=payload,
            model=call.model,
            model_revision=call.model_revision,
            input_tokens=_nonnegative_int(usage.get("prompt_tokens"), "prompt_tokens"),
            output_tokens=_nonnegative_int(usage.get("completion_tokens"), "completion_tokens"),
            latency_ms=max(0, int((time.monotonic() - started) * 1000)),
            cache_status="provider-unknown",
        )


__all__ = [
    "CALL_RECEIPT_SCHEMA",
    "CallReceiptV1",
    "FunctionCallError",
    "ModelCallV1",
    "ModelPort",
    "ModelResponseV1",
    "OpenAICompatibleJSONPort",
    "invoke_function",
    "verify_call_receipt",
]
