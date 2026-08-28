"""Single-shot, byte-observing provider gateway for DNRD-5.

The gateway, rather than its caller, constructs the exact provider request
from separately supplied semantic inputs.  It durably records a START record
before dispatch, performs one no-redirect HTTP request, persists exact request
and response bytes in a content-addressed store, and then appends one terminal
record.  A started call identifier is never reusable.

This closes the client-side request/response substitution gap.  It does not
attest provider internals, kernel/process isolation, provider cache behavior,
model determinism, or a scientific occurrence.  Those remain separately
measured source-freeze gates.
"""

from __future__ import annotations

import errno
import fcntl
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import socket
import tempfile
import time
from typing import Any, Mapping, Protocol, Sequence
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from _research.dnrd5.canonical_json import (
    MAX_SAFE_INTEGER,
    CanonicalJsonError,
    canonical_bytes,
    canonical_sha256,
    parse_canonical,
)


GATEWAY_VERSION = "hswm-dnrd5-provider-gateway/v1"
REQUEST_PROJECTION_VERSION = "hswm-dnrd5-provider-request-projection/v1"
MODEL_INPUT_ENVELOPE_VERSION = "hswm-dnrd5-model-input-envelope/v1"
RECEIPT_VERSION = "hswm-dnrd5-provider-transport-receipt/v1"
LEDGER_RECORD_VERSION = "hswm-dnrd5-provider-attempt-ledger-record/v1"
RECEIPT_MEDIA_TYPE = (
    "application/vnd.hswm.dnrd5-provider-transport-receipt-v1+json"
)
REQUEST_PROJECTION_MEDIA_TYPE = (
    "application/vnd.hswm.dnrd5-provider-request-projection-v1+json"
)
MODEL_INPUT_MEDIA_TYPE = (
    "application/vnd.hswm.dnrd5-model-input-v1+json"
)
RESPONSE_SCHEMA_MEDIA_TYPE = "application/schema+json"
JSON_MEDIA_TYPE = "application/json"
TEXT_MEDIA_TYPE = "text/plain;charset=utf-8"
BINARY_MEDIA_TYPE = "application/octet-stream"
MAX_REQUEST_BYTES = 1_048_576
MAX_RESPONSE_BYTES = 1_048_576
MAX_OUTPUT_TOKENS = 4_096
SYSTEM_MESSAGE = (
    "Act only as the bounded DNRD-5 token-native model function. Read the "
    "declared input, follow its instruction, and return exactly one object "
    "satisfying the supplied strict JSON schema."
)
BOUNDARY_STATUS = (
    "CLIENT_OBSERVED_EXACT_APPLICATION_BYTES_NOT_PROVIDER_INTERNAL_OS_CACHE_"
    "DETERMINISM_OR_SCIENTIFIC_ATTESTATION"
)
ZERO_SHA256 = "0" * 64
CALL_CLASSES = (
    "PRE_OUTCOME_TRAJECTORY",
    "REVISION_PROPOSAL",
    "FRESH_PROBE",
)

_BLOCK_ID = re.compile(
    r"^DNRD5-BLOCK-(?:000[1-9]|00[1-9][0-9]|0[12][0-9]{2}|0300)$"
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}$")
_RESPONSE_SCHEMA_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_FORBIDDEN_MODEL_INPUT_KEYS = {
    "arm",
    "armlabel",
    "cloneid",
    "evaluatorprivate",
    "evaluatordiagnostics",
    "forkid",
    "genuineoutcome",
    "hiddenanswer",
    "placebopreimage",
    "probeanswer",
    "theta",
}


class ProviderGatewayRefusal(ValueError):
    """Input, evidence, or durable ledger bytes violate the frozen boundary."""


class ProviderGatewayExecutionError(RuntimeError):
    """One consumed call ended without an accepted provider response."""

    def __init__(self, failure_code: str, detail: str) -> None:
        super().__init__(detail)
        self.failure_code = failure_code


@dataclass(frozen=True, slots=True)
class ContentDescriptor:
    media_type: str
    byte_length: int
    sha256: str

    def projection(self) -> dict[str, Any]:
        return {
            "mediaType": self.media_type,
            "byteLength": self.byte_length,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class Dnrd5ProviderConfig:
    endpoint: str
    expected_model: str
    api_key: str | None = None
    timeout_milliseconds: int = 120_000
    max_response_bytes: int = MAX_RESPONSE_BYTES

    def __post_init__(self) -> None:
        _validate_endpoint(self.endpoint)
        if _MODEL_ID.fullmatch(self.expected_model) is None:
            raise ProviderGatewayRefusal("expected_model is not a canonical model identifier")
        if self.api_key is not None and (
            type(self.api_key) is not str or not self.api_key
        ):
            raise ProviderGatewayRefusal("api_key must be nonempty text or None")
        if (
            type(self.timeout_milliseconds) is not int
            or not 1 <= self.timeout_milliseconds <= 86_400_000
        ):
            raise ProviderGatewayRefusal(
                "timeout_milliseconds must be an integer in [1, 86400000]"
            )
        if self.max_response_bytes != MAX_RESPONSE_BYTES:
            raise ProviderGatewayRefusal(
                "DNRD-5 accepted responses use the frozen one-MiB byte cap"
            )


@dataclass(frozen=True, slots=True)
class Dnrd5ProviderCall:
    block_id: str
    call_id: str
    call_class: str
    session_id: str
    worker_id: str
    private_binding_sha256: str
    request_nonce: str
    rng_bytes: bytes
    model_identity_bytes: bytes
    runtime_identity_bytes: bytes
    isolation_bytes: bytes
    instruction_bytes: bytes
    model_input_bytes: bytes
    response_schema_bytes: bytes
    max_output_tokens: int


@dataclass(frozen=True, slots=True)
class HttpObservation:
    status: int
    body: bytes
    response_content_type: str | None
    provider_request_id: str | None


class SingleShotHttpTransport(Protocol):
    def request(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_milliseconds: int,
    ) -> HttpObservation: ...


@dataclass(frozen=True, slots=True)
class Dnrd5ProviderCallResult:
    receipt: Mapping[str, Any]
    receipt_bytes: bytes
    request_projection_bytes: bytes
    request_bytes: bytes
    response_bytes: bytes


@dataclass(frozen=True, slots=True)
class Dnrd5CompletedBlockGatewaySummary:
    block_id: str
    generation_call_count: int
    trajectory_call_count: int
    revision_call_count: int
    probe_call_count: int
    first_start_ordinal: int
    last_terminal_ordinal: int
    receipt_sha256s: tuple[str, ...]
    terminal: str


class _NoRedirect(urlrequest.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Any,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


class UrllibSingleShotTransport:
    """Exactly one urllib open with redirects and environment proxies disabled."""

    def __init__(self, *, max_response_bytes: int = MAX_RESPONSE_BYTES) -> None:
        if max_response_bytes != MAX_RESPONSE_BYTES:
            raise ProviderGatewayRefusal("transport response cap drifted")
        self._max_response_bytes = max_response_bytes
        self._opener = urlrequest.build_opener(
            urlrequest.ProxyHandler({}), _NoRedirect()
        )

    @staticmethod
    def _headers(headers: Any) -> tuple[str | None, str | None]:
        content_type = headers.get("Content-Type")
        request_id = headers.get("X-Request-Id")
        for value, label in (
            (content_type, "response content type"),
            (request_id, "provider request id"),
        ):
            if value is not None and (
                type(value) is not str
                or not value
                or len(value.encode("utf-8", errors="strict")) > 1_024
            ):
                raise ProviderGatewayExecutionError(
                    "RESPONSE_HEADER_INVALID", f"{label} is not bounded text"
                )
        return content_type, request_id

    def _read(self, stream: Any) -> bytes:
        body = stream.read(self._max_response_bytes + 1)
        if type(body) is not bytes:
            raise ProviderGatewayExecutionError(
                "TRANSPORT_OBSERVATION_INVALID", "HTTP body is not exact bytes"
            )
        if len(body) > self._max_response_bytes:
            raise ProviderGatewayExecutionError(
                "RESPONSE_TOO_LARGE", "provider response exceeds one MiB"
            )
        return body

    def request(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_milliseconds: int,
    ) -> HttpObservation:
        try:
            request = urlrequest.Request(
                url, data=body, headers=dict(headers), method="POST"
            )
        except (TypeError, ValueError) as error:
            raise ProviderGatewayExecutionError(
                "PRE_DISPATCH_CONFIGURATION_INVALID",
                "urllib rejected the request before dispatch",
            ) from error
        try:
            with self._opener.open(
                request, timeout=timeout_milliseconds / 1_000
            ) as response:
                status = getattr(response, "status", None)
                if type(status) is not int:
                    raise ProviderGatewayExecutionError(
                        "TRANSPORT_OBSERVATION_INVALID",
                        "HTTP status is not an integer",
                    )
                content_type, request_id = self._headers(response.headers)
                return HttpObservation(
                    status=status,
                    body=self._read(response),
                    response_content_type=content_type,
                    provider_request_id=request_id,
                )
        except urlerror.HTTPError as error:
            content_type, request_id = self._headers(error.headers)
            return HttpObservation(
                status=error.code,
                body=self._read(error),
                response_content_type=content_type,
                provider_request_id=request_id,
            )
        except ProviderGatewayExecutionError:
            raise
        except urlerror.URLError as error:
            reason = error.reason
            pre_dispatch = isinstance(
                reason, (ValueError, socket.gaierror, ConnectionRefusedError)
            ) or (
                isinstance(reason, OSError)
                and reason.errno
                in {
                    errno.ECONNREFUSED,
                    errno.ENETUNREACH,
                    errno.EHOSTUNREACH,
                    errno.ENETDOWN,
                }
            )
            code = (
                "PRE_DISPATCH_CONNECT_FAILURE"
                if pre_dispatch
                else "AMBIGUOUS_TRANSPORT_OUTCOME"
            )
            raise ProviderGatewayExecutionError(
                code, "provider request did not produce an exact HTTP observation"
            ) from error
        except (TimeoutError, socket.timeout, OSError) as error:
            raise ProviderGatewayExecutionError(
                "AMBIGUOUS_TRANSPORT_OUTCOME",
                "provider request outcome is ambiguous",
            ) from error


def _validate_endpoint(endpoint: object) -> str:
    if type(endpoint) is not str or not endpoint:
        raise ProviderGatewayRefusal("endpoint must be nonempty text")
    try:
        parsed = urlparse.urlsplit(endpoint)
        port = parsed.port
    except ValueError as error:
        raise ProviderGatewayRefusal("endpoint port is invalid") from error
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != "/v1/chat/completions"
        or (port is not None and not 0 < port < 65_536)
    ):
        raise ProviderGatewayRefusal(
            "endpoint must be an exact http(s) /v1/chat/completions URL without authority secrets, query, or fragment"
        )
    return endpoint


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise ProviderGatewayRefusal(f"{label} is not a canonical identifier")
    return value


def _hash(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ProviderGatewayRefusal(f"{label} must be lowercase SHA-256")
    return value


def _exact_mapping(
    value: object, keys: set[str], label: str
) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ProviderGatewayRefusal(f"{label} key set drifted")
    return value


def _descriptor(media_type: str, raw: bytes) -> ContentDescriptor:
    if type(raw) is not bytes:
        raise ProviderGatewayRefusal("content must be exact bytes")
    return ContentDescriptor(media_type, len(raw), sha256(raw).hexdigest())


def _descriptor_from_projection(
    value: object, label: str
) -> ContentDescriptor:
    record = _exact_mapping(
        value, {"mediaType", "byteLength", "sha256"}, label
    )
    media_type = record["mediaType"]
    byte_length = record["byteLength"]
    digest = record["sha256"]
    if (
        type(media_type) is not str
        or not media_type
        or len(media_type) > 256
        or type(byte_length) is not int
        or not 0 <= byte_length <= MAX_SAFE_INTEGER
    ):
        raise ProviderGatewayRefusal(f"{label} descriptor fields are invalid")
    return ContentDescriptor(media_type, byte_length, _hash(digest, label))


def _same_descriptor(
    descriptor: ContentDescriptor, media_type: str, raw: bytes
) -> bool:
    return descriptor == _descriptor(media_type, raw)


def _strict_json(raw: bytes, label: str) -> Any:
    def unique(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ProviderGatewayRefusal(f"duplicate key in {label}")
            result[key] = item
        return result

    def reject_constant(value: str) -> None:
        raise ProviderGatewayRefusal(f"non-finite constant {value!r} in {label}")

    try:
        return json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderGatewayRefusal(f"{label} is not strict UTF-8 JSON") from error


def _validate_call(call: Dnrd5ProviderCall) -> None:
    if type(call) is not Dnrd5ProviderCall:
        raise ProviderGatewayRefusal("call must be an exact Dnrd5ProviderCall")
    if _BLOCK_ID.fullmatch(call.block_id) is None:
        raise ProviderGatewayRefusal("block_id is outside DNRD-5's 300 blocks")
    for value, label in (
        (call.call_id, "call_id"),
        (call.session_id, "session_id"),
        (call.worker_id, "worker_id"),
    ):
        _identifier(value, label)
    if call.call_class not in CALL_CLASSES:
        raise ProviderGatewayRefusal("call_class is not a frozen DNRD-5 class")
    _hash(call.private_binding_sha256, "private_binding_sha256")
    _hash(call.request_nonce, "request_nonce")
    byte_fields = (
        call.rng_bytes,
        call.model_identity_bytes,
        call.runtime_identity_bytes,
        call.isolation_bytes,
        call.instruction_bytes,
        call.model_input_bytes,
        call.response_schema_bytes,
    )
    if any(type(value) is not bytes for value in byte_fields):
        raise ProviderGatewayRefusal("all call content must be exact bytes")
    if not call.rng_bytes:
        raise ProviderGatewayRefusal("rng_bytes cannot be empty")
    for value, label in (
        (call.model_identity_bytes, "model identity"),
        (call.runtime_identity_bytes, "runtime identity"),
        (call.isolation_bytes, "isolation"),
        (call.model_input_bytes, "model input"),
        (call.response_schema_bytes, "response schema"),
    ):
        try:
            parsed = parse_canonical(value)
        except CanonicalJsonError as error:
            raise ProviderGatewayRefusal(
                f"{label} must be exact canonical-json/v1 bytes"
            ) from error
        if type(parsed) is not dict:
            raise ProviderGatewayRefusal(f"{label} must be a canonical object")
    try:
        instruction = call.instruction_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ProviderGatewayRefusal("instruction must be UTF-8 text") from error
    if not instruction or len(call.instruction_bytes) > 65_536:
        raise ProviderGatewayRefusal("instruction text is empty or oversized")
    if (
        type(call.max_output_tokens) is not int
        or not 1 <= call.max_output_tokens <= MAX_OUTPUT_TOKENS
    ):
        raise ProviderGatewayRefusal(
            "max_output_tokens is outside the frozen bounded range"
        )
    model_input = parse_canonical(call.model_input_bytes)
    _validate_model_input(call.call_class, model_input)
    visible_bytes = call.model_input_bytes + b"\0" + call.instruction_bytes
    for hidden, label in (
        (call.block_id.encode(), "block identity"),
        (call.call_id.encode(), "call identity"),
        (call.session_id.encode(), "session identity"),
        (call.worker_id.encode(), "worker identity"),
        (call.private_binding_sha256.encode(), "private binding"),
        (call.request_nonce.encode(), "request nonce"),
    ):
        if hidden in visible_bytes:
            raise ProviderGatewayRefusal(f"model-visible input leaks {label}")
    upper_visible = visible_bytes.upper()
    if any(label.encode() in upper_visible for label in (
        "ACTIVE",
        "OUTCOME_INDEPENDENT_SHAM",
        "DELAYED_NO_CREDIT",
        "EXACT_W0_ROLLBACK",
    )):
        raise ProviderGatewayRefusal("model-visible input leaks a canonical arm label")


def _normalized_key(value: str) -> str:
    return value.casefold().replace("_", "").replace("-", "")


def _walk_model_input(value: Any, *, depth: int = 0) -> None:
    if depth > 64:
        raise ProviderGatewayRefusal("model input nesting exceeds the gateway bound")
    if type(value) is dict:
        for key, item in value.items():
            if _normalized_key(key) in _FORBIDDEN_MODEL_INPUT_KEYS:
                raise ProviderGatewayRefusal(
                    f"model input carries forbidden hidden key {key!r}"
                )
            _walk_model_input(item, depth=depth + 1)
    elif type(value) is list:
        for item in value:
            _walk_model_input(item, depth=depth + 1)


def _validate_model_input(call_class: str, value: Any) -> None:
    keys_by_class = {
        "PRE_OUTCOME_TRAJECTORY": {"publicTask", "behaviorProjection"},
        "REVISION_PROPOSAL": {
            "sealedTrajectory",
            "assignedFeedback",
            "revisionRequest",
        },
        "FRESH_PROBE": {"behaviorProjection", "freshProbe"},
    }
    expected = keys_by_class[call_class]
    record = _exact_mapping(value, expected, "call-class model input")
    if any(type(record[key]) is not dict for key in expected):
        raise ProviderGatewayRefusal(
            "each call-class model input role must be a canonical object"
        )
    _walk_model_input(record)


def _seed(rng_bytes: bytes) -> int:
    return int.from_bytes(sha256(rng_bytes).digest()[:6], "big")


def _response_schema_name(call_class: str) -> str:
    return "hswm_dnrd5_" + call_class.lower()


def build_provider_request(
    call: Dnrd5ProviderCall, config: Dnrd5ProviderConfig
) -> tuple[bytes, bytes]:
    """Construct the evidence projection and exact provider body internally."""
    _validate_call(call)
    model_input = parse_canonical(call.model_input_bytes)
    response_schema = parse_canonical(call.response_schema_bytes)
    instruction = call.instruction_bytes.decode("utf-8", errors="strict")
    schema_name = _response_schema_name(call.call_class)
    if _RESPONSE_SCHEMA_NAME.fullmatch(schema_name) is None:
        raise ProviderGatewayRefusal("derived response schema name is invalid")
    if (
        response_schema.get("type") != "object"
        or response_schema.get("additionalProperties") is not False
        or type(response_schema.get("properties")) is not dict
        or type(response_schema.get("required")) is not list
    ):
        raise ProviderGatewayRefusal(
            "response schema must be a closed required object schema"
        )
    input_envelope = {
        "contractVersion": MODEL_INPUT_ENVELOPE_VERSION,
        "callClass": call.call_class,
        "instruction": instruction,
        "input": model_input,
    }
    user_content = canonical_bytes(input_envelope).decode("utf-8")
    seed = _seed(call.rng_bytes)
    request = {
        "chat_template_kwargs": {"enable_thinking": False},
        "logprobs": False,
        "max_tokens": call.max_output_tokens,
        "messages": [
            {"content": SYSTEM_MESSAGE, "role": "system"},
            {"content": user_content, "role": "user"},
        ],
        "model": config.expected_model,
        "n": 1,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": response_schema,
                "strict": True,
            },
        },
        "seed": seed,
        "stream": False,
        "temperature": 0,
        "top_p": 1,
    }
    request_bytes = canonical_bytes(request)
    if len(request_bytes) > MAX_REQUEST_BYTES:
        raise ProviderGatewayRefusal("provider request exceeds one MiB")
    projection = {
        "contractVersion": REQUEST_PROJECTION_VERSION,
        "callClass": call.call_class,
        "rng": _descriptor(BINARY_MEDIA_TYPE, call.rng_bytes).projection(),
        "modelIdentity": _descriptor(
            JSON_MEDIA_TYPE, call.model_identity_bytes
        ).projection(),
        "runtimeIdentity": _descriptor(
            JSON_MEDIA_TYPE, call.runtime_identity_bytes
        ).projection(),
        "isolation": _descriptor(
            JSON_MEDIA_TYPE, call.isolation_bytes
        ).projection(),
        "instruction": _descriptor(
            TEXT_MEDIA_TYPE, call.instruction_bytes
        ).projection(),
        "modelInput": _descriptor(
            MODEL_INPUT_MEDIA_TYPE, call.model_input_bytes
        ).projection(),
        "responseSchema": _descriptor(
            RESPONSE_SCHEMA_MEDIA_TYPE, call.response_schema_bytes
        ).projection(),
        "expectedModel": config.expected_model,
        "maxOutputTokens": call.max_output_tokens,
        "derivedSeed": seed,
        "providerRequest": _descriptor(
            JSON_MEDIA_TYPE, request_bytes
        ).projection(),
        "status": "GATEWAY_CONSTRUCTED_REQUEST_NOT_CALLER_SUPPLIED",
    }
    return canonical_bytes(projection), request_bytes


def _same_json_value(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def _validate_json_schema(schema: Any, *, path: str = "$", depth: int = 0) -> None:
    if depth > 32 or type(schema) is not dict:
        raise ProviderGatewayRefusal(f"response schema {path} is not a bounded object")
    schema_type = schema.get("type")
    common = {"type", "enum", "const"}
    allowed_by_type = {
        "object": common | {"properties", "required", "additionalProperties"},
        "array": common | {"items", "minItems", "maxItems"},
        "string": common | {"pattern", "minLength", "maxLength"},
        "integer": common | {"minimum", "maximum"},
        "boolean": common,
        "null": common,
    }
    if schema_type not in allowed_by_type or not set(schema) <= allowed_by_type[schema_type]:
        raise ProviderGatewayRefusal(
            f"response schema {path} uses an unsupported type or keyword"
        )
    if "enum" in schema:
        enum = schema["enum"]
        if type(enum) is not list or not enum or any(
            any(_same_json_value(item, prior) for prior in enum[:index])
            for index, item in enumerate(enum)
        ):
            raise ProviderGatewayRefusal(f"response schema {path} enum is invalid")
    if schema_type == "object":
        properties = schema.get("properties")
        required = schema.get("required")
        if (
            type(properties) is not dict
            or type(required) is not list
            or any(type(key) is not str or not key for key in properties)
            or any(type(key) is not str for key in required)
            or len(required) != len(set(required))
            or set(required) != set(properties)
            or schema.get("additionalProperties") is not False
        ):
            raise ProviderGatewayRefusal(
                f"response schema {path} must require every declared property and forbid extras"
            )
        for key, child in properties.items():
            _validate_json_schema(child, path=f"{path}.{key}", depth=depth + 1)
    elif schema_type == "array":
        minimum = schema.get("minItems", 0)
        maximum = schema.get("maxItems", MAX_SAFE_INTEGER)
        if (
            "items" not in schema
            or type(minimum) is not int
            or type(maximum) is not int
            or not 0 <= minimum <= maximum <= 10_000
        ):
            raise ProviderGatewayRefusal(f"response schema {path} array bounds are invalid")
        _validate_json_schema(schema["items"], path=f"{path}[]", depth=depth + 1)
    elif schema_type == "string":
        minimum = schema.get("minLength", 0)
        maximum = schema.get("maxLength", 65_536)
        if (
            type(minimum) is not int
            or type(maximum) is not int
            or not 0 <= minimum <= maximum <= 65_536
        ):
            raise ProviderGatewayRefusal(f"response schema {path} string bounds are invalid")
        if "pattern" in schema:
            pattern = schema["pattern"]
            if type(pattern) is not str or len(pattern) > 4_096:
                raise ProviderGatewayRefusal(f"response schema {path} pattern is invalid")
            try:
                re.compile(pattern, re.ASCII)
            except re.error as error:
                raise ProviderGatewayRefusal(
                    f"response schema {path} pattern does not compile"
                ) from error
    elif schema_type == "integer":
        minimum = schema.get("minimum", -MAX_SAFE_INTEGER)
        maximum = schema.get("maximum", MAX_SAFE_INTEGER)
        if (
            type(minimum) is not int
            or type(maximum) is not int
            or not -MAX_SAFE_INTEGER <= minimum <= maximum <= MAX_SAFE_INTEGER
        ):
            raise ProviderGatewayRefusal(f"response schema {path} integer bounds are invalid")


def _validate_json_instance(instance: Any, schema: Mapping[str, Any], *, path: str = "$") -> None:
    if "const" in schema and not _same_json_value(instance, schema["const"]):
        raise ProviderGatewayExecutionError(
            "MODEL_CONTENT_SCHEMA_INVALID", f"model content {path} violates const"
        )
    if "enum" in schema and not any(
        _same_json_value(instance, item) for item in schema["enum"]
    ):
        raise ProviderGatewayExecutionError(
            "MODEL_CONTENT_SCHEMA_INVALID", f"model content {path} violates enum"
        )
    schema_type = schema["type"]
    if schema_type == "object":
        if type(instance) is not dict or set(instance) != set(schema["properties"]):
            raise ProviderGatewayExecutionError(
                "MODEL_CONTENT_SCHEMA_INVALID", f"model content {path} object shape drifted"
            )
        for key, child in schema["properties"].items():
            _validate_json_instance(instance[key], child, path=f"{path}.{key}")
    elif schema_type == "array":
        if type(instance) is not list or not schema.get("minItems", 0) <= len(instance) <= schema.get("maxItems", 10_000):
            raise ProviderGatewayExecutionError(
                "MODEL_CONTENT_SCHEMA_INVALID", f"model content {path} array shape drifted"
            )
        for index, item in enumerate(instance):
            _validate_json_instance(item, schema["items"], path=f"{path}[{index}]")
    elif schema_type == "string":
        if type(instance) is not str or not schema.get("minLength", 0) <= len(instance) <= schema.get("maxLength", 65_536):
            raise ProviderGatewayExecutionError(
                "MODEL_CONTENT_SCHEMA_INVALID", f"model content {path} string shape drifted"
            )
        if "pattern" in schema and re.fullmatch(schema["pattern"], instance, re.ASCII) is None:
            raise ProviderGatewayExecutionError(
                "MODEL_CONTENT_SCHEMA_INVALID", f"model content {path} pattern drifted"
            )
    elif schema_type == "integer":
        if type(instance) is not int or not schema.get("minimum", -MAX_SAFE_INTEGER) <= instance <= schema.get("maximum", MAX_SAFE_INTEGER):
            raise ProviderGatewayExecutionError(
                "MODEL_CONTENT_SCHEMA_INVALID", f"model content {path} integer drifted"
            )
    elif schema_type == "boolean":
        if type(instance) is not bool:
            raise ProviderGatewayExecutionError(
                "MODEL_CONTENT_SCHEMA_INVALID", f"model content {path} is not boolean"
            )
    elif schema_type == "null" and instance is not None:
        raise ProviderGatewayExecutionError(
            "MODEL_CONTENT_SCHEMA_INVALID", f"model content {path} is not null"
        )


def _validate_response(
    raw: bytes,
    status: int,
    expected_model: str,
    response_schema_bytes: bytes,
) -> None:
    if status != 200:
        raise ProviderGatewayExecutionError(
            "HTTP_STATUS_NOT_200", "provider response status is not exactly 200"
        )
    try:
        value = _strict_json(raw, "provider response")
    except ProviderGatewayRefusal as error:
        raise ProviderGatewayExecutionError(
            "RESPONSE_NOT_STRICT_JSON",
            "provider response is not strict UTF-8 JSON",
        ) from error
    if type(value) is not dict:
        raise ProviderGatewayExecutionError(
            "RESPONSE_NOT_OBJECT", "provider response must be an object"
        )
    if value.get("model") != expected_model:
        raise ProviderGatewayExecutionError(
            "MODEL_IDENTITY_MISMATCH", "provider response model identity drifted"
        )
    choices = value.get("choices")
    if type(choices) is not list or len(choices) != 1 or type(choices[0]) is not dict:
        raise ProviderGatewayExecutionError(
            "CHOICE_CARDINALITY_INVALID", "provider must return exactly one choice"
        )
    choice = choices[0]
    message = choice.get("message")
    if (
        choice.get("finish_reason") != "stop"
        or type(message) is not dict
        or type(message.get("content")) is not str
        or not message["content"]
    ):
        raise ProviderGatewayExecutionError(
            "CHOICE_TERMINAL_INVALID", "provider choice is not one stopped text response"
        )
    try:
        structured = _strict_json(
            message["content"].encode("utf-8"), "model content"
        )
    except ProviderGatewayRefusal as error:
        raise ProviderGatewayExecutionError(
            "MODEL_CONTENT_NOT_STRICT_JSON",
            "model content is not strict UTF-8 JSON",
        ) from error
    if type(structured) is not dict:
        raise ProviderGatewayExecutionError(
            "MODEL_CONTENT_NOT_OBJECT", "model content must be one strict JSON object"
        )
    try:
        response_schema = parse_canonical(response_schema_bytes)
        _validate_json_schema(response_schema)
    except (CanonicalJsonError, ProviderGatewayRefusal) as error:
        raise ProviderGatewayExecutionError(
            "RESPONSE_SCHEMA_INVALID", "bound response schema is invalid"
        ) from error
    _validate_json_instance(structured, response_schema)
    usage = value.get("usage")
    if type(usage) is not dict:
        raise ProviderGatewayExecutionError(
            "USAGE_INVALID", "provider response usage must be an object"
        )
    counts: list[int] = []
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        count = usage.get(key)
        if type(count) is not int or count < 0:
            raise ProviderGatewayExecutionError(
                "USAGE_INVALID", f"usage.{key} must be a nonnegative integer"
            )
        counts.append(count)
    if counts[0] + counts[1] != counts[2]:
        raise ProviderGatewayExecutionError(
            "USAGE_INVALID", "provider usage arithmetic drifted"
        )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def initialize_provider_evidence_root(root: Path) -> None:
    """Create one new evidence root; existing roots are never overwritten."""
    if not isinstance(root, Path) or root.exists() or not root.parent.is_dir():
        raise ProviderGatewayRefusal(
            "evidence root must be a new child of an existing directory"
        )
    root.mkdir(mode=0o700)
    (root / "content").mkdir(mode=0o700)
    ledger = root / "attempts.jsonl"
    fd = os.open(ledger, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_directory(root)
    _fsync_directory(root.parent)


def _content_path(root: Path, digest: str) -> Path:
    return root / "content" / digest


def _persist_content(root: Path, raw: bytes) -> None:
    digest = sha256(raw).hexdigest()
    destination = _content_path(root, digest)
    if destination.exists():
        if destination.read_bytes() != raw:
            raise ProviderGatewayRefusal("content-addressed path collision")
        return
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="xb",
            dir=root / "content",
            prefix=".dnrd5-content-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, destination)
        except FileExistsError:
            if destination.read_bytes() != raw:
                raise ProviderGatewayRefusal("content-addressed path collision")
        _fsync_directory(root / "content")
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def _record(core: Mapping[str, Any]) -> dict[str, Any]:
    return {**core, "recordSha256": canonical_sha256(core)}


def _parse_ledger(raw: bytes) -> list[dict[str, Any]]:
    if not raw:
        return []
    if not raw.endswith(b"\n") or b"\n\n" in raw:
        raise ProviderGatewayRefusal("attempt ledger framing is invalid")
    records: list[dict[str, Any]] = []
    previous = ZERO_SHA256
    start_keys = {
        "schemaVersion",
        "recordType",
        "ordinal",
        "previousRecordSha256",
        "blockId",
        "callId",
        "callClass",
        "sessionId",
        "workerId",
        "privateBindingSha256",
        "requestNonce",
        "requestProjection",
        "request",
        "startedAtUnixMs",
        "retry",
        "terminal",
        "recordSha256",
    }
    terminal_keys = {
        "schemaVersion",
        "recordType",
        "ordinal",
        "previousRecordSha256",
        "blockId",
        "callId",
        "callClass",
        "startRecordSha256",
        "outcome",
        "receipt",
        "observedResponse",
        "failureCode",
        "finishedAtUnixMs",
        "retryAllowed",
        "terminal",
        "recordSha256",
    }
    for ordinal, line in enumerate(raw[:-1].split(b"\n"), start=1):
        try:
            value = parse_canonical(line)
        except CanonicalJsonError as error:
            raise ProviderGatewayRefusal(
                "attempt ledger contains noncanonical record bytes"
            ) from error
        if type(value) is not dict:
            raise ProviderGatewayRefusal("attempt ledger record is not an object")
        record_type = value.get("recordType")
        expected_keys = start_keys if record_type == "START" else terminal_keys
        if set(value) != expected_keys:
            raise ProviderGatewayRefusal("attempt ledger record key set drifted")
        if (
            value.get("schemaVersion") != LEDGER_RECORD_VERSION
            or value.get("ordinal") != ordinal
            or value.get("previousRecordSha256") != previous
            or record_type not in {"START", "TERMINAL"}
            or _BLOCK_ID.fullmatch(value.get("blockId") or "") is None
            or value.get("callClass") not in CALL_CLASSES
        ):
            raise ProviderGatewayRefusal("attempt ledger chronology drifted")
        _identifier(value.get("callId"), "ledger callId")
        _hash(value.get("previousRecordSha256"), "ledger predecessor")
        if record_type == "START":
            _identifier(value.get("sessionId"), "ledger sessionId")
            _identifier(value.get("workerId"), "ledger workerId")
            _hash(value.get("privateBindingSha256"), "ledger private binding")
            _hash(value.get("requestNonce"), "ledger request nonce")
            _descriptor_from_projection(
                value.get("requestProjection"), "ledger request projection"
            )
            _descriptor_from_projection(value.get("request"), "ledger request")
            if (
                type(value.get("startedAtUnixMs")) is not int
                or not 0 <= value["startedAtUnixMs"] <= MAX_SAFE_INTEGER
                or value.get("retry") != "NONE"
                or value.get("terminal")
                != "DURABLY_VISIBLE_BEFORE_SINGLE_DISPATCH"
            ):
                raise ProviderGatewayRefusal("attempt start contract drifted")
        else:
            _hash(value.get("startRecordSha256"), "ledger start binding")
            if (
                type(value.get("finishedAtUnixMs")) is not int
                or not 0 <= value["finishedAtUnixMs"] <= MAX_SAFE_INTEGER
                or value.get("retryAllowed") is not False
                or value.get("terminal")
                != "CALL_ID_CONSUMED_NO_RETRY_RESUME_OR_REPLACEMENT"
            ):
                raise ProviderGatewayRefusal("attempt terminal contract drifted")
            outcome = value.get("outcome")
            if outcome == "SUCCEEDED":
                receipt_descriptor = _descriptor_from_projection(
                    value.get("receipt"), "ledger receipt"
                )
                response_descriptor = _descriptor_from_projection(
                    value.get("observedResponse"), "ledger observed response"
                )
                if (
                    receipt_descriptor.media_type != RECEIPT_MEDIA_TYPE
                    or response_descriptor.media_type != JSON_MEDIA_TYPE
                    or value.get("failureCode") is not None
                ):
                    raise ProviderGatewayRefusal(
                        "successful terminal evidence closure drifted"
                    )
            elif outcome == "FAILED":
                failure_code = value.get("failureCode")
                if (
                    value.get("receipt") is not None
                    or type(failure_code) is not str
                    or re.fullmatch(r"^[A-Z][A-Z0-9_]{0,127}$", failure_code)
                    is None
                ):
                    raise ProviderGatewayRefusal(
                        "failed terminal evidence closure drifted"
                    )
                if value.get("observedResponse") is not None:
                    observed = _descriptor_from_projection(
                        value["observedResponse"], "ledger failed response"
                    )
                    if observed.media_type != JSON_MEDIA_TYPE:
                        raise ProviderGatewayRefusal(
                            "failed observed response media type drifted"
                        )
            else:
                raise ProviderGatewayRefusal("attempt terminal outcome drifted")
        supplied = value.get("recordSha256")
        core = {key: item for key, item in value.items() if key != "recordSha256"}
        if supplied != canonical_sha256(core):
            raise ProviderGatewayRefusal("attempt ledger record self-hash drifted")
        previous = supplied
        records.append(value)
    starts: dict[str, dict[str, Any]] = {}
    terminals: set[str] = set()
    for record in records:
        call_id = _identifier(record.get("callId"), "ledger callId")
        if record["recordType"] == "START":
            if call_id in starts:
                raise ProviderGatewayRefusal("attempt ledger duplicates a call start")
            starts[call_id] = record
        else:
            if call_id not in starts or call_id in terminals:
                raise ProviderGatewayRefusal("attempt ledger terminal lacks one prior start")
            if record.get("startRecordSha256") != starts[call_id]["recordSha256"]:
                raise ProviderGatewayRefusal("attempt terminal binds the wrong start")
            terminals.add(call_id)
    return records


def read_provider_attempt_ledger(root: Path) -> tuple[dict[str, Any], ...]:
    ledger = root / "attempts.jsonl"
    if not ledger.is_file():
        raise ProviderGatewayRefusal("provider attempt ledger is missing")
    return tuple(_parse_ledger(ledger.read_bytes()))


def _unterminated_starts(
    records: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    terminal_call_ids = {
        record["callId"]
        for record in records
        if record.get("recordType") == "TERMINAL"
    }
    return tuple(
        record
        for record in records
        if record.get("recordType") == "START"
        and record["callId"] not in terminal_call_ids
    )


def validate_provider_attempt_ledger_closed(root: Path) -> None:
    """Refuse any root containing a consumed call without a terminal record.

    An unterminated START may mean that dispatch occurred.  It is therefore
    never recovered by retrying, resuming, or appending later calls.  This is a
    client-side fail-closed occurrence rule, not provider-side exactly-once.
    """
    if _unterminated_starts(read_provider_attempt_ledger(root)):
        raise ProviderGatewayRefusal(
            "provider evidence root contains an unterminated consumed call; "
            "the occurrence is irrecoverably incomplete"
        )


def _load_content_descriptor(
    root: Path,
    projection: object,
    *,
    expected_media_type: str,
    label: str,
) -> bytes:
    descriptor = _descriptor_from_projection(projection, label)
    if descriptor.media_type != expected_media_type:
        raise ProviderGatewayRefusal(f"{label} media type drifted")
    path = _content_path(root, descriptor.sha256)
    if not path.is_file():
        raise ProviderGatewayRefusal(f"{label} content is missing")
    raw = path.read_bytes()
    if not _same_descriptor(descriptor, expected_media_type, raw):
        raise ProviderGatewayRefusal(f"{label} content descriptor drifted")
    return raw


def validate_completed_block_gateway_evidence(
    root: Path, block_id: str
) -> Dnrd5CompletedBlockGatewaySummary:
    """Close one actual block's nine durable START/terminal/receipt chains."""
    if _BLOCK_ID.fullmatch(block_id) is None:
        raise ProviderGatewayRefusal("completed block identity is invalid")
    records = read_provider_attempt_ledger(root)
    starts = [
        record
        for record in records
        if record["blockId"] == block_id and record["recordType"] == "START"
    ]
    terminals = [
        record
        for record in records
        if record["blockId"] == block_id and record["recordType"] == "TERMINAL"
    ]
    if len(starts) != 9 or len(terminals) != 9:
        raise ProviderGatewayRefusal(
            "completed block requires exactly nine starts and nine terminals"
        )
    expected_classes = [
        "PRE_OUTCOME_TRAJECTORY",
        *(["REVISION_PROPOSAL"] * 4),
        *(["FRESH_PROBE"] * 4),
    ]
    if [record["callClass"] for record in starts] != expected_classes:
        raise ProviderGatewayRefusal("completed block call grammar drifted")
    for key in ("callId", "sessionId", "workerId", "privateBindingSha256"):
        if len({record[key] for record in starts}) != 9:
            raise ProviderGatewayRefusal(
                f"completed block {key} values must be globally unique"
            )
    if len({record["requestNonce"] for record in starts}) != 9:
        raise ProviderGatewayRefusal(
            "completed block request nonces must be globally unique"
        )
    terminal_by_start = {
        record["startRecordSha256"]: record for record in terminals
    }
    if len(terminal_by_start) != 9:
        raise ProviderGatewayRefusal("completed block terminal bindings repeat")
    receipt_digests: list[str] = []
    rng_digests: set[str] = set()
    for start in starts:
        terminal = terminal_by_start.get(start["recordSha256"])
        if terminal is None or terminal["outcome"] != "SUCCEEDED":
            raise ProviderGatewayRefusal(
                "completed block contains missing or unsuccessful call terminal"
            )
        receipt_bytes = _load_content_descriptor(
            root,
            terminal["receipt"],
            expected_media_type=RECEIPT_MEDIA_TYPE,
            label="block provider receipt",
        )
        receipt = parse_canonical(receipt_bytes)
        if type(receipt) is not dict:
            raise ProviderGatewayRefusal("block provider receipt is not an object")
        media_types = {
            "requestProjection": REQUEST_PROJECTION_MEDIA_TYPE,
            "request": JSON_MEDIA_TYPE,
            "response": JSON_MEDIA_TYPE,
            "rng": BINARY_MEDIA_TYPE,
            "modelIdentity": JSON_MEDIA_TYPE,
            "runtimeIdentity": JSON_MEDIA_TYPE,
            "isolation": JSON_MEDIA_TYPE,
            "instruction": TEXT_MEDIA_TYPE,
            "modelInput": MODEL_INPUT_MEDIA_TYPE,
            "responseSchema": RESPONSE_SCHEMA_MEDIA_TYPE,
        }
        content = {
            role: _load_content_descriptor(
                root,
                receipt.get(role),
                expected_media_type=media_type,
                label=f"block receipt {role}",
            )
            for role, media_type in media_types.items()
        }
        checked = validate_provider_receipt(receipt_bytes, content)
        if (
            checked["blockId"] != block_id
            or checked["callId"] != start["callId"]
            or checked["callClass"] != start["callClass"]
            or checked["sessionId"] != start["sessionId"]
            or checked["workerId"] != start["workerId"]
            or checked["privateBindingSha256"]
            != start["privateBindingSha256"]
            or checked["attemptStartRecordSha256"]
            != start["recordSha256"]
            or checked["attemptOrdinal"] != start["ordinal"]
            or checked["requestProjection"] != start["requestProjection"]
            or checked["request"] != start["request"]
            or terminal["observedResponse"] != checked["response"]
        ):
            raise ProviderGatewayRefusal(
                "block receipt does not close its exact durable attempt"
            )
        rng_digest = checked["rng"]["sha256"]
        if rng_digest in rng_digests:
            raise ProviderGatewayRefusal(
                "completed block RNG descriptors must be globally unique"
            )
        rng_digests.add(rng_digest)
        receipt_digests.append(checked["receiptSha256"])
    return Dnrd5CompletedBlockGatewaySummary(
        block_id=block_id,
        generation_call_count=9,
        trajectory_call_count=1,
        revision_call_count=4,
        probe_call_count=4,
        first_start_ordinal=starts[0]["ordinal"],
        last_terminal_ordinal=max(record["ordinal"] for record in terminals),
        receipt_sha256s=tuple(receipt_digests),
        terminal=(
            "NINE_CLIENT_OBSERVED_CALLS_CLOSED_NOT_PROVIDER_INTERNAL_OS_CACHE_"
            "DETERMINISM_OR_SCIENTIFIC_ATTESTATION"
        ),
    )


def _append_ledger_record(
    root: Path,
    build: Any,
) -> dict[str, Any]:
    ledger = root / "attempts.jsonl"
    fd = os.open(ledger, os.O_RDWR | os.O_APPEND)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.lseek(fd, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 65_536)
            if not chunk:
                break
            chunks.append(chunk)
        records = _parse_ledger(b"".join(chunks))
        record = build(records)
        encoded = canonical_bytes(record) + b"\n"
        written = 0
        while written < len(encoded):
            amount = os.write(fd, encoded[written:])
            if amount <= 0:
                raise OSError("short attempt-ledger append")
            written += amount
        os.fsync(fd)
        return record
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _append_start(
    root: Path,
    call: Dnrd5ProviderCall,
    request_projection: ContentDescriptor,
    request: ContentDescriptor,
    started_at_unix_ms: int,
) -> dict[str, Any]:
    def build(records: list[dict[str, Any]]) -> dict[str, Any]:
        if _unterminated_starts(records):
            raise ProviderGatewayRefusal(
                "provider evidence root contains an unterminated consumed call; "
                "no later call may be dispatched"
            )
        if any(record.get("callId") == call.call_id for record in records):
            raise ProviderGatewayRefusal(
                "call_id was already consumed; retry, resume, and replacement are forbidden"
            )
        if any(
            record.get("recordType") == "START"
            and record.get("requestNonce") == call.request_nonce
            for record in records
        ):
            raise ProviderGatewayRefusal("request_nonce was already consumed")
        core = {
            "schemaVersion": LEDGER_RECORD_VERSION,
            "recordType": "START",
            "ordinal": len(records) + 1,
            "previousRecordSha256": (
                records[-1]["recordSha256"] if records else ZERO_SHA256
            ),
            "blockId": call.block_id,
            "callId": call.call_id,
            "callClass": call.call_class,
            "sessionId": call.session_id,
            "workerId": call.worker_id,
            "privateBindingSha256": call.private_binding_sha256,
            "requestNonce": call.request_nonce,
            "requestProjection": request_projection.projection(),
            "request": request.projection(),
            "startedAtUnixMs": started_at_unix_ms,
            "retry": "NONE",
            "terminal": "DURABLY_VISIBLE_BEFORE_SINGLE_DISPATCH",
        }
        return _record(core)

    return _append_ledger_record(root, build)


def _append_terminal(
    root: Path,
    call: Dnrd5ProviderCall,
    start: Mapping[str, Any],
    *,
    outcome: str,
    receipt: ContentDescriptor | None,
    observed_response: ContentDescriptor | None,
    failure_code: str | None,
    finished_at_unix_ms: int,
) -> dict[str, Any]:
    def build(records: list[dict[str, Any]]) -> dict[str, Any]:
        matching = [
            record for record in records if record.get("callId") == call.call_id
        ]
        if len(matching) != 1 or matching[0].get("recordType") != "START":
            raise ProviderGatewayRefusal(
                "call terminal requires exactly one unterminated start"
            )
        core = {
            "schemaVersion": LEDGER_RECORD_VERSION,
            "recordType": "TERMINAL",
            "ordinal": len(records) + 1,
            "previousRecordSha256": records[-1]["recordSha256"],
            "blockId": call.block_id,
            "callId": call.call_id,
            "callClass": call.call_class,
            "startRecordSha256": start["recordSha256"],
            "outcome": outcome,
            "receipt": None if receipt is None else receipt.projection(),
            "observedResponse": (
                None if observed_response is None else observed_response.projection()
            ),
            "failureCode": failure_code,
            "finishedAtUnixMs": finished_at_unix_ms,
            "retryAllowed": False,
            "terminal": "CALL_ID_CONSUMED_NO_RETRY_RESUME_OR_REPLACEMENT",
        }
        return _record(core)

    return _append_ledger_record(root, build)


def _request_headers(
    config: Dnrd5ProviderConfig, request_nonce: str
) -> tuple[dict[str, str], dict[str, Any]]:
    headers = {
        "Accept": "application/json",
        "Cache-Control": "no-store",
        "Content-Type": "application/json",
        "X-HSWM-DNRD5-Request-Nonce": request_nonce,
    }
    authorization = "ABSENT"
    if config.api_key is not None:
        headers["Authorization"] = f"Bearer {config.api_key}"
        authorization = "PRESENT_REDACTED"
    projection = {
        "accept": "application/json",
        "cacheControl": "no-store",
        "contentType": "application/json",
        "requestNonce": request_nonce,
        "authorization": authorization,
    }
    return headers, projection


def _receipt(
    *,
    call: Dnrd5ProviderCall,
    config: Dnrd5ProviderConfig,
    start: Mapping[str, Any],
    request_projection: ContentDescriptor,
    request: ContentDescriptor,
    response: ContentDescriptor,
    header_projection: Mapping[str, Any],
    observation: HttpObservation,
    started_at_unix_ms: int,
    finished_at_unix_ms: int,
    elapsed_monotonic_ms: int,
) -> dict[str, Any]:
    core = {
        "schemaVersion": RECEIPT_VERSION,
        "gatewayVersion": GATEWAY_VERSION,
        "blockId": call.block_id,
        "callId": call.call_id,
        "callClass": call.call_class,
        "sessionId": call.session_id,
        "workerId": call.worker_id,
        "privateBindingSha256": call.private_binding_sha256,
        "attemptOrdinal": start["ordinal"],
        "attemptStartRecordSha256": start["recordSha256"],
        "endpoint": config.endpoint,
        "method": "POST",
        "requestHeaders": dict(header_projection),
        "requestProjection": request_projection.projection(),
        "request": request.projection(),
        "response": response.projection(),
        "rng": _descriptor(BINARY_MEDIA_TYPE, call.rng_bytes).projection(),
        "modelIdentity": _descriptor(
            JSON_MEDIA_TYPE, call.model_identity_bytes
        ).projection(),
        "runtimeIdentity": _descriptor(
            JSON_MEDIA_TYPE, call.runtime_identity_bytes
        ).projection(),
        "isolation": _descriptor(
            JSON_MEDIA_TYPE, call.isolation_bytes
        ).projection(),
        "instruction": _descriptor(
            TEXT_MEDIA_TYPE, call.instruction_bytes
        ).projection(),
        "modelInput": _descriptor(
            MODEL_INPUT_MEDIA_TYPE, call.model_input_bytes
        ).projection(),
        "responseSchema": _descriptor(
            RESPONSE_SCHEMA_MEDIA_TYPE, call.response_schema_bytes
        ).projection(),
        "expectedModel": config.expected_model,
        "httpStatus": observation.status,
        "responseContentType": observation.response_content_type,
        "providerRequestId": observation.provider_request_id,
        "startedAtUnixMs": started_at_unix_ms,
        "finishedAtUnixMs": finished_at_unix_ms,
        "elapsedMonotonicMs": elapsed_monotonic_ms,
        "timeoutMilliseconds": config.timeout_milliseconds,
        "transportImplementation": "PYTHON_URLLIB_SINGLE_OPEN_NO_REDIRECT_NO_ENV_PROXY",
        "retry": "NONE",
        "redirect": "DISABLED",
        "clientCacheSubstitution": "DISABLED",
        "providerCacheIndependence": "NOT_OBSERVABLE_BY_CLIENT",
        "osProcessIsolation": "BOUND_DESCRIPTOR_NOT_PROVEN_BY_GATEWAY",
        "boundaryStatus": BOUNDARY_STATUS,
    }
    return {**core, "receiptSha256": canonical_sha256(core)}


def _content_for_receipt(
    call: Dnrd5ProviderCall,
    request_projection_bytes: bytes,
    request_bytes: bytes,
    response_bytes: bytes,
) -> dict[str, bytes]:
    return {
        "requestProjection": request_projection_bytes,
        "request": request_bytes,
        "response": response_bytes,
        "rng": call.rng_bytes,
        "modelIdentity": call.model_identity_bytes,
        "runtimeIdentity": call.runtime_identity_bytes,
        "isolation": call.isolation_bytes,
        "instruction": call.instruction_bytes,
        "modelInput": call.model_input_bytes,
        "responseSchema": call.response_schema_bytes,
    }


def validate_provider_receipt(
    receipt_bytes: bytes,
    content: Mapping[str, bytes],
) -> dict[str, Any]:
    """Independently revalidate one accepted receipt and every bound byte string."""
    try:
        receipt = parse_canonical(receipt_bytes)
    except CanonicalJsonError as error:
        raise ProviderGatewayRefusal(
            "provider receipt is not exact canonical-json/v1"
        ) from error
    expected_keys = {
        "schemaVersion",
        "gatewayVersion",
        "blockId",
        "callId",
        "callClass",
        "sessionId",
        "workerId",
        "privateBindingSha256",
        "attemptOrdinal",
        "attemptStartRecordSha256",
        "endpoint",
        "method",
        "requestHeaders",
        "requestProjection",
        "request",
        "response",
        "rng",
        "modelIdentity",
        "runtimeIdentity",
        "isolation",
        "instruction",
        "modelInput",
        "responseSchema",
        "expectedModel",
        "httpStatus",
        "responseContentType",
        "providerRequestId",
        "startedAtUnixMs",
        "finishedAtUnixMs",
        "elapsedMonotonicMs",
        "timeoutMilliseconds",
        "transportImplementation",
        "retry",
        "redirect",
        "clientCacheSubstitution",
        "providerCacheIndependence",
        "osProcessIsolation",
        "boundaryStatus",
        "receiptSha256",
    }
    record = _exact_mapping(receipt, expected_keys, "provider receipt")
    if (
        record["schemaVersion"] != RECEIPT_VERSION
        or record["gatewayVersion"] != GATEWAY_VERSION
        or _BLOCK_ID.fullmatch(record["blockId"] or "") is None
        or record["callClass"] not in CALL_CLASSES
        or record["method"] != "POST"
        or record["httpStatus"] != 200
        or record["transportImplementation"]
        != "PYTHON_URLLIB_SINGLE_OPEN_NO_REDIRECT_NO_ENV_PROXY"
        or record["retry"] != "NONE"
        or record["redirect"] != "DISABLED"
        or record["clientCacheSubstitution"] != "DISABLED"
        or record["providerCacheIndependence"] != "NOT_OBSERVABLE_BY_CLIENT"
        or record["osProcessIsolation"] != "BOUND_DESCRIPTOR_NOT_PROVEN_BY_GATEWAY"
        or record["boundaryStatus"] != BOUNDARY_STATUS
    ):
        raise ProviderGatewayRefusal("provider receipt frozen constants drifted")
    for key in ("callId", "sessionId", "workerId"):
        _identifier(record[key], f"receipt {key}")
    for key in ("privateBindingSha256", "attemptStartRecordSha256"):
        _hash(record[key], f"receipt {key}")
    _validate_endpoint(record["endpoint"])
    if _MODEL_ID.fullmatch(record["expectedModel"] or "") is None:
        raise ProviderGatewayRefusal("receipt expected model is invalid")
    response_content_type = record["responseContentType"]
    if (
        type(response_content_type) is not str
        or response_content_type.split(";", 1)[0].strip().casefold()
        != "application/json"
        or len(response_content_type.encode("utf-8", errors="strict")) > 1_024
    ):
        raise ProviderGatewayRefusal("receipt response content type is invalid")
    provider_request_id = record["providerRequestId"]
    if provider_request_id is not None and (
        type(provider_request_id) is not str
        or not provider_request_id
        or len(provider_request_id.encode("utf-8", errors="strict")) > 1_024
    ):
        raise ProviderGatewayRefusal("receipt provider request id is invalid")
    for key in (
        "attemptOrdinal",
        "startedAtUnixMs",
        "finishedAtUnixMs",
        "elapsedMonotonicMs",
        "timeoutMilliseconds",
    ):
        value = record[key]
        if type(value) is not int or not 0 <= value <= MAX_SAFE_INTEGER:
            raise ProviderGatewayRefusal(f"receipt {key} is not a safe integer")
    if (
        record["attemptOrdinal"] < 1
        or record["startedAtUnixMs"] > record["finishedAtUnixMs"]
        or record["timeoutMilliseconds"] < 1
    ):
        raise ProviderGatewayRefusal("provider receipt chronology is invalid")
    headers = _exact_mapping(
        record["requestHeaders"],
        {"accept", "cacheControl", "contentType", "requestNonce", "authorization"},
        "request header projection",
    )
    if (
        headers["accept"] != "application/json"
        or headers["cacheControl"] != "no-store"
        or headers["contentType"] != "application/json"
        or _SHA256.fullmatch(headers["requestNonce"] or "") is None
        or headers["authorization"] not in {"ABSENT", "PRESENT_REDACTED"}
    ):
        raise ProviderGatewayRefusal("request header projection drifted")
    expected_content_keys = {
        "requestProjection",
        "request",
        "response",
        "rng",
        "modelIdentity",
        "runtimeIdentity",
        "isolation",
        "instruction",
        "modelInput",
        "responseSchema",
    }
    if type(content) is not dict or set(content) != expected_content_keys:
        raise ProviderGatewayRefusal("receipt content map key set drifted")
    media_types = {
        "requestProjection": REQUEST_PROJECTION_MEDIA_TYPE,
        "request": JSON_MEDIA_TYPE,
        "response": JSON_MEDIA_TYPE,
        "rng": BINARY_MEDIA_TYPE,
        "modelIdentity": JSON_MEDIA_TYPE,
        "runtimeIdentity": JSON_MEDIA_TYPE,
        "isolation": JSON_MEDIA_TYPE,
        "instruction": TEXT_MEDIA_TYPE,
        "modelInput": MODEL_INPUT_MEDIA_TYPE,
        "responseSchema": RESPONSE_SCHEMA_MEDIA_TYPE,
    }
    for role, media_type in media_types.items():
        raw = content[role]
        if type(raw) is not bytes:
            raise ProviderGatewayRefusal(f"receipt content {role} is not bytes")
        descriptor = _descriptor_from_projection(record[role], f"receipt {role}")
        if not _same_descriptor(descriptor, media_type, raw):
            raise ProviderGatewayRefusal(f"receipt {role} descriptor mismatch")
    projection = parse_canonical(content["requestProjection"])
    projection_record = _exact_mapping(
        projection,
        {
            "contractVersion",
            "callClass",
            "rng",
            "modelIdentity",
            "runtimeIdentity",
            "isolation",
            "instruction",
            "modelInput",
            "responseSchema",
            "expectedModel",
            "maxOutputTokens",
            "derivedSeed",
            "providerRequest",
            "status",
        },
        "request projection",
    )
    if (
        projection_record["contractVersion"] != REQUEST_PROJECTION_VERSION
        or projection_record["callClass"] != record["callClass"]
        or projection_record["expectedModel"] != record["expectedModel"]
        or projection_record["status"]
        != "GATEWAY_CONSTRUCTED_REQUEST_NOT_CALLER_SUPPLIED"
    ):
        raise ProviderGatewayRefusal("request projection identity drifted")
    if (
        type(projection_record["maxOutputTokens"]) is not int
        or not 1 <= projection_record["maxOutputTokens"] <= MAX_OUTPUT_TOKENS
        or type(projection_record["derivedSeed"]) is not int
        or projection_record["derivedSeed"] != _seed(content["rng"])
    ):
        raise ProviderGatewayRefusal("request projection RNG controls drifted")
    for role in (
        "rng",
        "modelIdentity",
        "runtimeIdentity",
        "isolation",
        "instruction",
        "modelInput",
        "responseSchema",
    ):
        if projection_record[role] != record[role]:
            raise ProviderGatewayRefusal(
                f"request projection {role} does not bind the receipt"
            )
    if projection_record["providerRequest"] != record["request"]:
        raise ProviderGatewayRefusal("request projection does not bind provider bytes")
    reconstructed_call = Dnrd5ProviderCall(
        block_id=record["blockId"],
        call_id=record["callId"],
        call_class=record["callClass"],
        session_id=record["sessionId"],
        worker_id=record["workerId"],
        private_binding_sha256=record["privateBindingSha256"],
        request_nonce=headers["requestNonce"],
        rng_bytes=content["rng"],
        model_identity_bytes=content["modelIdentity"],
        runtime_identity_bytes=content["runtimeIdentity"],
        isolation_bytes=content["isolation"],
        instruction_bytes=content["instruction"],
        model_input_bytes=content["modelInput"],
        response_schema_bytes=content["responseSchema"],
        max_output_tokens=projection_record["maxOutputTokens"],
    )
    reconstructed_config = Dnrd5ProviderConfig(
        endpoint=record["endpoint"],
        expected_model=record["expectedModel"],
        api_key=None,
        timeout_milliseconds=record["timeoutMilliseconds"],
    )
    expected_projection, expected_request = build_provider_request(
        reconstructed_call, reconstructed_config
    )
    if (
        expected_projection != content["requestProjection"]
        or expected_request != content["request"]
    ):
        raise ProviderGatewayRefusal(
            "provider request is not the exact gateway reconstruction"
        )
    request = parse_canonical(content["request"])
    if (
        type(request) is not dict
        or request.get("model") != record["expectedModel"]
        or request.get("seed") != projection_record["derivedSeed"]
        or request.get("max_tokens") != projection_record["maxOutputTokens"]
        or request.get("n") != 1
        or request.get("stream") is not False
        or request.get("temperature") != 0
        or request.get("top_p") != 1
        or request.get("logprobs") is not False
    ):
        raise ProviderGatewayRefusal("provider request generation controls drifted")
    _validate_response(
        content["response"],
        200,
        record["expectedModel"],
        content["responseSchema"],
    )
    core = {key: item for key, item in record.items() if key != "receiptSha256"}
    if record["receiptSha256"] != canonical_sha256(core):
        raise ProviderGatewayRefusal("provider receipt self-hash drifted")
    return dict(record)


class Dnrd5ProviderGateway:
    """Durable single-shot gateway over one new or recovered evidence root."""

    def __init__(self, root: Path, config: Dnrd5ProviderConfig) -> None:
        if (
            not isinstance(root, Path)
            or not root.is_dir()
            or not (root / "content").is_dir()
            or not (root / "attempts.jsonl").is_file()
        ):
            raise ProviderGatewayRefusal("provider evidence root is not initialized")
        validate_provider_attempt_ledger_closed(root)
        self._root = root
        self._config = config

    @classmethod
    def create(
        cls, root: Path, config: Dnrd5ProviderConfig
    ) -> "Dnrd5ProviderGateway":
        initialize_provider_evidence_root(root)
        return cls(root, config)

    def execute(self, call: Dnrd5ProviderCall) -> Dnrd5ProviderCallResult:
        """Consume exactly one call ID and either return accepted bytes or fail terminally."""
        _validate_call(call)
        request_projection_bytes, request_bytes = build_provider_request(
            call, self._config
        )
        request_projection = _descriptor(
            REQUEST_PROJECTION_MEDIA_TYPE, request_projection_bytes
        )
        request = _descriptor(JSON_MEDIA_TYPE, request_bytes)
        for raw in (
            call.rng_bytes,
            call.model_identity_bytes,
            call.runtime_identity_bytes,
            call.isolation_bytes,
            call.instruction_bytes,
            call.model_input_bytes,
            call.response_schema_bytes,
            request_projection_bytes,
            request_bytes,
        ):
            _persist_content(self._root, raw)
        started_at_unix_ms = time.time_ns() // 1_000_000
        start = _append_start(
            self._root,
            call,
            request_projection,
            request,
            started_at_unix_ms,
        )
        headers, header_projection = _request_headers(
            self._config, call.request_nonce
        )
        started_monotonic_ns = time.monotonic_ns()
        observation: HttpObservation | None = None
        try:
            transport = UrllibSingleShotTransport(
                max_response_bytes=self._config.max_response_bytes
            )
            observation = transport.request(
                url=self._config.endpoint,
                headers=headers,
                body=request_bytes,
                timeout_milliseconds=self._config.timeout_milliseconds,
            )
            if type(observation) is not HttpObservation:
                raise ProviderGatewayExecutionError(
                    "TRANSPORT_OBSERVATION_INVALID",
                    "transport returned an undeclared observation type",
                )
            _persist_content(self._root, observation.body)
            response = _descriptor(JSON_MEDIA_TYPE, observation.body)
            _validate_response(
                observation.body,
                observation.status,
                self._config.expected_model,
                call.response_schema_bytes,
            )
            elapsed_ms = max(
                0, (time.monotonic_ns() - started_monotonic_ns) // 1_000_000
            )
            finished_at_unix_ms = max(
                started_at_unix_ms, time.time_ns() // 1_000_000
            )
            receipt = _receipt(
                call=call,
                config=self._config,
                start=start,
                request_projection=request_projection,
                request=request,
                response=response,
                header_projection=header_projection,
                observation=observation,
                started_at_unix_ms=started_at_unix_ms,
                finished_at_unix_ms=finished_at_unix_ms,
                elapsed_monotonic_ms=elapsed_ms,
            )
            receipt_bytes = canonical_bytes(receipt)
            receipt_descriptor = _descriptor(RECEIPT_MEDIA_TYPE, receipt_bytes)
            _persist_content(self._root, receipt_bytes)
            content = _content_for_receipt(
                call, request_projection_bytes, request_bytes, observation.body
            )
            validate_provider_receipt(receipt_bytes, content)
            _append_terminal(
                self._root,
                call,
                start,
                outcome="SUCCEEDED",
                receipt=receipt_descriptor,
                observed_response=response,
                failure_code=None,
                finished_at_unix_ms=finished_at_unix_ms,
            )
            return Dnrd5ProviderCallResult(
                receipt=dict(receipt),
                receipt_bytes=receipt_bytes,
                request_projection_bytes=request_projection_bytes,
                request_bytes=request_bytes,
                response_bytes=observation.body,
            )
        except ProviderGatewayExecutionError as error:
            finished_at_unix_ms = max(
                started_at_unix_ms, time.time_ns() // 1_000_000
            )
            observed = (
                None
                if observation is None
                else _descriptor(JSON_MEDIA_TYPE, observation.body)
            )
            _append_terminal(
                self._root,
                call,
                start,
                outcome="FAILED",
                receipt=None,
                observed_response=observed,
                failure_code=error.failure_code,
                finished_at_unix_ms=finished_at_unix_ms,
            )
            raise


__all__ = [
    "BOUNDARY_STATUS",
    "CALL_CLASSES",
    "Dnrd5ProviderCall",
    "Dnrd5ProviderCallResult",
    "Dnrd5CompletedBlockGatewaySummary",
    "Dnrd5ProviderConfig",
    "Dnrd5ProviderGateway",
    "GATEWAY_VERSION",
    "ProviderGatewayExecutionError",
    "ProviderGatewayRefusal",
    "RECEIPT_VERSION",
    "build_provider_request",
    "initialize_provider_evidence_root",
    "read_provider_attempt_ledger",
    "validate_provider_attempt_ledger_closed",
    "validate_provider_receipt",
    "validate_completed_block_gateway_evidence",
]
