"""Frozen protocol primitives for the DGX DNRD-5 live Q1 qualification.

Live Q1 tests only client-observed, exact assistant-content repeatability for
one pinned model/runtime pair. It is not a DNRD-5 occurrence, Source A, an
HSWM learning result, or evidence of provider-internal determinism.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any

from _research.dnrd5.canonical_json import (
    CanonicalJsonError,
    canonical_bytes,
    parse_canonical,
)


PLAN_SCHEMA = "hswm-dgx-q1-live-response-exactness/v1"
MARKER_SCHEMA = "hswm-dgx-q1-live-start-marker/v1"
NAMESPACE = "DNRD5-Q1-LIVE-QUALIFICATION-ONLY/v1"
RUNNER_VERSION = "hswm-dgx-q1-live-runner/v1"
BOUNDARY_SCHEMA = "hswm-dgx-q1-live-boundary-attestation/v1"
CONSUMPTION_REGISTRY_SCHEMA = "hswm-dgx-q1-plan-consumption-registry/v1"
CONSUMPTION_REGISTRY_PATH = (
    "/mnt/hswm/evidence/hswm-dnrd5-q1-live-consumption-v1"
)
CONSUMPTION_REGISTRY = {
    "schema_version": CONSUMPTION_REGISTRY_SCHEMA,
    "path": CONSUMPTION_REGISTRY_PATH,
    "scope": "PINNED_DGX_NODE_LOCAL_DURABLE_PLAN_HASH_REGISTRY",
    "boundary": "NODE_LOCAL_PATH_BINDING_NOT_DISTRIBUTED_GLOBAL_CONSENSUS",
    "terminal": "ONE_DURABLE_BURN_PER_PLAN_HASH_AT_THE_DECLARED_PATH",
}
REPRODUCED = "LIVE_REPRODUCED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FROZEN_Q1"
FALSIFIED = "LIVE_FALSIFIED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FROZEN_Q1"
INCONCLUSIVE = "INCONCLUSIVE_LIVE_Q1_EVIDENCE"
VOID = "VOID_LIVE_Q1_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH"
TERMINALS = (REPRODUCED, FALSIFIED, INCONCLUSIVE, VOID)
NONCLAIMS = (
    "NOT_A_DNRD5_300_BLOCK_OCCURRENCE_CALL_OR_PILOT_EFFECT_DATA",
    "NOT_SOURCE_A_AUTHORIZATION_OR_SOURCE_A_FREEZE",
    "NOT_PROOF_OF_PROVIDER_INTERNAL_CACHE_SCHEDULING_OR_GLOBAL_DETERMINISM",
    "NOT_PROOF_OF_NO_INTERFERENCE_OR_HSWM_CAUSAL_LEARNING",
    "NOT_PROOF_OF_CONSCIOUSNESS_SELFHOOD_OR_SCALE_INVARIANT_CAUSAL_CLOSURE",
)
CALL_CLASSES = (
    "PRE_OUTCOME_TRAJECTORY",
    "REVISION_PROPOSAL",
    "FRESH_PROBE",
)
SYSTEM_MESSAGE = (
    "Act only as the bounded DNRD-5 token-native model function. Read the "
    "declared public synthetic input, follow its instruction, and return "
    "exactly one object satisfying the supplied strict JSON schema."
)

_SHA = re.compile(r"^[0-9a-f]{64}$")
_GIT = re.compile(r"^[0-9a-f]{40}$")
_CASE = re.compile(r"^QCASE-[0-9]{3}$")
_ATTEMPT = re.compile(r"^DNRD5-Q1L-([0-9]{3})-R(00[1-4])$")


class LiveQ1Refusal(ValueError):
    """The proposed plan, material, response, or marker is outside live Q1."""


@dataclass(frozen=True, slots=True)
class LiveQ1CaseMaterial:
    case_id: str
    instruction_bytes: bytes
    model_input_bytes: bytes
    response_schema_bytes: bytes
    rng_bytes: bytes
    max_output_tokens: int


def _object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise LiveQ1Refusal(f"{label} key set drifted")
    return value


def _digest(value: Any, label: str) -> str:
    if (
        type(value) is not str
        or _SHA.fullmatch(value) is None
        or value == "0" * 64
    ):
        raise LiveQ1Refusal(f"{label} must be a non-placeholder SHA-256")
    return value


def _source(value: Any, label: str) -> dict[str, Any]:
    source = _object(
        value,
        {"commit", "tree", "ci_receipt_sha256", "ci_terminal"},
        label,
    )
    if (
        type(source["commit"]) is not str
        or _GIT.fullmatch(source["commit"]) is None
        or source["commit"] == "0" * 40
        or type(source["tree"]) is not str
        or _GIT.fullmatch(source["tree"]) is None
        or source["tree"] == "0" * 40
    ):
        raise LiveQ1Refusal(f"{label} Git identity drifted")
    _digest(source["ci_receipt_sha256"], f"{label} CI receipt")
    if source["ci_terminal"] != "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD":
        raise LiveQ1Refusal(f"{label} CI terminal drifted")
    return source


def strict_json(raw: bytes) -> Any:
    """Parse ordinary bounded UTF-8 JSON, rejecting duplicates/non-finites."""

    if type(raw) is not bytes or len(raw) > 1_048_576:
        raise LiveQ1Refusal("ordinary JSON bytes are unbounded")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise LiveQ1Refusal("duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise LiveQ1Refusal(f"forbidden JSON constant {value}")

    try:
        return json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise LiveQ1Refusal("not strict ordinary UTF-8 JSON") from error


def validate_response_schema(
    schema: Any,
    value: Any | None = None,
    *,
    instance: bool = False,
) -> None:
    """Validate the closed JSON-schema subset used by the public Q corpus."""

    if type(schema) is not dict or schema.get("type") not in {
        "object",
        "array",
        "string",
        "integer",
        "boolean",
        "null",
    }:
        raise LiveQ1Refusal("response schema is unsupported or tautological")
    kind = schema["type"]
    if kind == "object":
        required = schema.get("required")
        if (
            set(schema) != {"type", "properties", "required", "additionalProperties"}
            or type(schema.get("properties")) is not dict
            or not schema["properties"]
            or type(required) is not list
            or len(required) != len(set(required))
            or set(required) != set(schema["properties"])
            or schema.get("additionalProperties") is not False
        ):
            raise LiveQ1Refusal("response object schema drifted")
        for child in schema["properties"].values():
            validate_response_schema(child)
    elif kind == "array":
        if (
            not {"type", "items"} <= set(schema)
            or not set(schema) <= {"type", "items", "minItems", "maxItems"}
            or type(schema.get("items")) is not dict
            or type(schema.get("minItems", 0)) is not int
            or type(schema.get("maxItems", 65_536)) is not int
            or schema.get("minItems", 0) < 0
            or schema.get("maxItems", 65_536) < schema.get("minItems", 0)
        ):
            raise LiveQ1Refusal("response array schema drifted")
        validate_response_schema(schema["items"])
    elif kind == "string":
        if (
            not {"type"} <= set(schema)
            or not set(schema) <= {"type", "minLength", "maxLength", "pattern"}
            or type(schema.get("minLength", 0)) is not int
            or type(schema.get("maxLength", 65_536)) is not int
            or schema.get("minLength", 0) < 0
            or schema.get("maxLength", 65_536) < schema.get("minLength", 0)
            or ("pattern" in schema and type(schema["pattern"]) is not str)
        ):
            raise LiveQ1Refusal("response string schema drifted")
        try:
            re.compile(schema.get("pattern", ""))
        except re.error as error:
            raise LiveQ1Refusal("response string pattern drifted") from error
    elif kind == "integer":
        if (
            not {"type"} <= set(schema)
            or not set(schema) <= {"type", "minimum", "maximum"}
            or type(schema.get("minimum", -(2**53 - 1))) is not int
            or type(schema.get("maximum", 2**53 - 1)) is not int
            or schema.get("minimum", -(2**53 - 1))
            > schema.get("maximum", 2**53 - 1)
        ):
            raise LiveQ1Refusal("response integer schema drifted")
    elif set(schema) != {"type"}:
        raise LiveQ1Refusal("response scalar schema drifted")

    if not instance:
        return
    if kind == "object":
        properties = schema["properties"]
        if type(value) is not dict or set(value) != set(properties):
            raise LiveQ1Refusal("response object instance drifted")
        for key, child in properties.items():
            validate_response_schema(child, value[key], instance=True)
    elif kind == "array":
        if (
            type(value) is not list
            or not schema.get("minItems", 0)
            <= len(value)
            <= schema.get("maxItems", 65_536)
        ):
            raise LiveQ1Refusal("response array instance drifted")
        for item in value:
            validate_response_schema(schema["items"], item, instance=True)
    elif kind == "string":
        if (
            type(value) is not str
            or not schema.get("minLength", 0)
            <= len(value)
            <= schema.get("maxLength", 65_536)
            or ("pattern" in schema and re.fullmatch(schema["pattern"], value) is None)
        ):
            raise LiveQ1Refusal("response string instance drifted")
    elif kind == "integer":
        if (
            type(value) is not int
            or not schema.get("minimum", -(2**53 - 1))
            <= value
            <= schema.get("maximum", 2**53 - 1)
        ):
            raise LiveQ1Refusal("response integer instance drifted")
    elif kind == "boolean" and type(value) is not bool:
        raise LiveQ1Refusal("response boolean instance drifted")
    elif kind == "null" and value is not None:
        raise LiveQ1Refusal("response null instance drifted")


def derive_live_q1_order(attempts: Sequence[str], seed: bytes) -> list[str]:
    """Frozen domain-separated SHA-256 Fisher--Yates permutation."""

    if (
        type(seed) is not bytes
        or len(seed) != 32
        or type(attempts) not in {tuple, list}
        or len(attempts) != 96
        or len(set(attempts)) != 96
        or any(type(item) is not str or _ATTEMPT.fullmatch(item) is None for item in attempts)
    ):
        raise LiveQ1Refusal("live Q1 call-order domain drifted")
    ordered = list(attempts)
    for counter, index in enumerate(range(len(ordered) - 1, 0, -1)):
        digest = sha256(
            b"HSWM-DGX-Q1-LIVE-CALL-ORDER-V1\0"
            + seed
            + counter.to_bytes(8, "big")
        ).digest()
        swap = int.from_bytes(digest[:8], "big") % (index + 1)
        ordered[index], ordered[swap] = ordered[swap], ordered[index]
    return ordered


def build_live_q1_request(
    model: str,
    call_class: str,
    material: LiveQ1CaseMaterial,
) -> bytes:
    """Construct one exact OpenAI-compatible request from frozen raw material."""

    if (
        type(model) is not str
        or not model
        or len(model) > 160
        or type(material) is not LiveQ1CaseMaterial
        or _CASE.fullmatch(material.case_id) is None
        or call_class not in CALL_CLASSES
        or material.max_output_tokens not in {64, 128, 256}
        or not material.rng_bytes
    ):
        raise LiveQ1Refusal("request identity or bound drifted")
    try:
        instruction = material.instruction_bytes.decode("utf-8", errors="strict")
        model_input = parse_canonical(material.model_input_bytes)
        response_schema = parse_canonical(material.response_schema_bytes)
    except (UnicodeDecodeError, CanonicalJsonError) as error:
        raise LiveQ1Refusal("request material is not exact UTF-8/canonical JSON") from error
    needed = {
        "PRE_OUTCOME_TRAJECTORY": {"publicTask", "behaviorProjection"},
        "REVISION_PROPOSAL": {
            "sealedTrajectory",
            "assignedFeedback",
            "revisionRequest",
        },
        "FRESH_PROBE": {"behaviorProjection", "freshProbe"},
    }[call_class]
    if not instruction or type(model_input) is not dict or set(model_input) != needed:
        raise LiveQ1Refusal("request material semantic shape drifted")
    validate_response_schema(response_schema)
    seed = int.from_bytes(sha256(material.rng_bytes).digest()[:6], "big")
    return canonical_bytes(
        {
            "chat_template_kwargs": {"enable_thinking": False},
            "logprobs": False,
            "max_tokens": material.max_output_tokens,
            "messages": [
                {"content": SYSTEM_MESSAGE, "role": "system"},
                {
                    "content": canonical_bytes(
                        {
                            "contractVersion": "hswm-dgx-q1-live-model-input/v1",
                            "callClass": call_class,
                            "instruction": instruction,
                            "input": model_input,
                        }
                    ).decode("utf-8"),
                    "role": "user",
                },
            ],
            "model": model,
            "n": 1,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "hswm_dgx_q1_live_" + call_class.lower(),
                    "schema": response_schema,
                    "strict": True,
                },
            },
            "seed": seed,
            "stream": False,
            "temperature": 0,
            "top_p": 1,
        }
    )


def validate_live_q1_plan(raw: bytes) -> dict[str, Any]:
    try:
        plan = parse_canonical(raw)
    except (CanonicalJsonError, TypeError) as error:
        raise LiveQ1Refusal("live Q1 plan is not canonical JSON") from error
    keys = {
        "schema_version",
        "namespace",
        "source",
        "runner_version",
        "corpus_manifest_sha256",
        "corpus",
        "replicates",
        "call_order",
        "call_order_algorithm",
        "call_order_seed_hex",
        "call_order_seed_sha256",
        "budget",
        "zero_retry",
        "consumption_registry",
        "identities",
        "verifier",
        "evidence_root_genesis_sha256",
        "comparator",
        "allowed_terminals",
        "nonclaims",
    }
    plan = _object(plan, keys, "live Q1 plan")
    if plan["schema_version"] != PLAN_SCHEMA or plan["namespace"] != NAMESPACE:
        raise LiveQ1Refusal("live Q1 schema/namespace drifted")
    _source(plan["source"], "source")
    if plan["runner_version"] != RUNNER_VERSION:
        raise LiveQ1Refusal("runner version drifted")
    _digest(plan["corpus_manifest_sha256"], "corpus manifest")
    corpus = plan["corpus"]
    if type(corpus) is not list or len(corpus) != 24:
        raise LiveQ1Refusal("live Q1 requires exactly 24 cases")
    case_keys = {
        "case_id",
        "call_class",
        "request_sha256",
        "instruction_sha256",
        "model_input_sha256",
        "response_schema_sha256",
        "rng_sha256",
        "max_output_tokens",
    }
    ids: list[str] = []
    classes: Counter[str] = Counter()
    for case in corpus:
        case = _object(case, case_keys, "live Q1 case")
        if (
            type(case["case_id"]) is not str
            or _CASE.fullmatch(case["case_id"]) is None
            or case["call_class"] not in CALL_CLASSES
            or type(case["max_output_tokens"]) is not int
            or case["max_output_tokens"] not in {64, 128, 256}
        ):
            raise LiveQ1Refusal("case identity/class/token drifted")
        for name in case_keys - {"case_id", "call_class", "max_output_tokens"}:
            _digest(case[name], name)
        ids.append(case["case_id"])
        classes[case["call_class"]] += 1
    if len(set(ids)) != 24 or classes != Counter({name: 8 for name in CALL_CLASSES}):
        raise LiveQ1Refusal("case uniqueness or balanced class coverage drifted")
    if plan["replicates"] != 4 or plan["budget"] != 96 or plan["zero_retry"] is not True:
        raise LiveQ1Refusal("live Q1 must be 24 x 4 with zero retries")
    if plan["consumption_registry"] != CONSUMPTION_REGISTRY:
        raise LiveQ1Refusal("single-use consumption registry drifted")
    if (
        plan["call_order_algorithm"] != "FROZEN_SHA256_FISHER_YATES_V1"
        or type(plan["call_order_seed_hex"]) is not str
        or _SHA.fullmatch(plan["call_order_seed_hex"]) is None
    ):
        raise LiveQ1Refusal("call-order algorithm or seed drifted")
    seed = bytes.fromhex(plan["call_order_seed_hex"])
    _digest(plan["call_order_seed_sha256"], "call-order seed")
    attempts = [
        f"DNRD5-Q1L-{case_id[-3:]}-R{replicate:03d}"
        for case_id in ids
        for replicate in range(1, 5)
    ]
    if (
        sha256(seed).hexdigest() != plan["call_order_seed_sha256"]
        or plan["call_order"] != derive_live_q1_order(attempts, seed)
    ):
        raise LiveQ1Refusal("call order is not independently derived")
    identity_keys = {
        "endpoint_sha256",
        "model_identity_sha256",
        "runtime_identity_sha256",
        "tls_identity_sha256",
        "declared_isolation_contract_sha256",
        "model_snapshot_manifest_sha256",
    }
    identities = _object(plan["identities"], identity_keys, "identities")
    for name, digest in identities.items():
        _digest(digest, name)
    verifier = _object(plan["verifier"], {"source", "build_output_sha256"}, "verifier")
    _source(verifier["source"], "verifier source")
    _digest(verifier["build_output_sha256"], "verifier build")
    _digest(plan["evidence_root_genesis_sha256"], "evidence root genesis")
    if (
        plan["comparator"]
        != "EXACT_ASSISTANT_CONTENT_UTF8_WITH_CANONICAL_STRUCTURED_DIAGNOSTIC"
        or plan["allowed_terminals"] != list(TERMINALS)
        or plan["nonclaims"] != list(NONCLAIMS)
    ):
        raise LiveQ1Refusal("comparator, terminal, or nonclaim boundary drifted")
    return plan


def make_live_q1_start_marker(plan_raw: bytes) -> bytes:
    plan = validate_live_q1_plan(plan_raw)
    return canonical_bytes(
        {
            "schema_version": MARKER_SCHEMA,
            "namespace": NAMESPACE,
            "q1_sha256": sha256(plan_raw).hexdigest(),
            "request_sha256s": [row["request_sha256"] for row in plan["corpus"]],
            "terminal": "PLAN_AND_ALL_24_REQUEST_HASHES_BOUND_BEFORE_ANY_LIVE_START",
            "nonclaims": list(NONCLAIMS),
        }
    )


def validate_live_q1_start_marker(marker_raw: bytes, plan_raw: bytes) -> dict[str, Any]:
    expected = make_live_q1_start_marker(plan_raw)
    if marker_raw != expected:
        raise LiveQ1Refusal("live Q1 start marker drifted")
    return parse_canonical(marker_raw)


def validate_boundary_attestation(
    raw: bytes,
    plan_raw: bytes,
    *,
    phase: str,
    attempt_id: str | None,
    completed_attempts: int,
) -> dict[str, Any]:
    """Validate a typed, per-boundary observation from the exclusive lease."""

    plan = validate_live_q1_plan(plan_raw)
    try:
        receipt = parse_canonical(raw)
    except (CanonicalJsonError, TypeError) as error:
        raise LiveQ1Refusal("boundary attestation is not canonical JSON") from error
    keys = {
        "schema_version",
        "namespace",
        "q1_sha256",
        "phase",
        "attempt_id",
        "completed_attempts",
        "endpoint_sha256",
        "model_identity_sha256",
        "runtime_identity_sha256",
        "model_snapshot_manifest_sha256",
        "container_id_sha256",
        "image_id",
        "configured_image",
        "container_start_sha256",
        "cgroup_sha256",
        "argv_sha256",
        "gpu_uuid",
        "gpu_compute_pids",
        "host_listener_present",
        "container_init_pid",
        "container_network_namespace_sha256",
        "container_tcp_tables_sha256",
        "internal_listener_port",
        "host_listener_inventory_sha256",
        "unexpected_listener_count",
        "requests_running",
        "request_success_total",
        "prefix_cache_hits",
        "prefix_cache_queries",
        "raw_metrics_sha256",
        "boundary",
        "nonclaim",
    }
    receipt = _object(receipt, keys, "boundary attestation")
    if (
        receipt["schema_version"] != BOUNDARY_SCHEMA
        or receipt["namespace"] != NAMESPACE
        or receipt["q1_sha256"] != sha256(plan_raw).hexdigest()
        or receipt["phase"] != phase
        or receipt["attempt_id"] != attempt_id
        or type(completed_attempts) is not int
        or not 0 <= completed_attempts <= 96
        or receipt["completed_attempts"] != completed_attempts
        or receipt["endpoint_sha256"] != plan["identities"]["endpoint_sha256"]
        or receipt["model_identity_sha256"]
        != plan["identities"]["model_identity_sha256"]
        or receipt["runtime_identity_sha256"]
        != plan["identities"]["runtime_identity_sha256"]
        or receipt["model_snapshot_manifest_sha256"]
        != plan["identities"]["model_snapshot_manifest_sha256"]
        or receipt["boundary"]
        != "FINITE_OBSERVED_CONTROLS_NOT_NO_INTERFERENCE_PROOF"
        or receipt["nonclaim"]
        != "NOT_DISPATCH_AUTHORIZATION_OR_SOURCE_A_PERMIT_OR_NO_INTERFERENCE_PROOF"
    ):
        raise LiveQ1Refusal("boundary attestation plan/context drifted")
    for name in (
        "container_id_sha256",
        "container_start_sha256",
        "cgroup_sha256",
        "argv_sha256",
        "container_network_namespace_sha256",
        "container_tcp_tables_sha256",
        "host_listener_inventory_sha256",
        "raw_metrics_sha256",
    ):
        _digest(receipt[name], name)
    if (
        phase not in {"STARTUP", "PRE", "POST", "FINAL"}
        or (phase in {"PRE", "POST"}) != (attempt_id is not None)
        or (attempt_id is not None and _ATTEMPT.fullmatch(attempt_id) is None)
        or type(receipt["image_id"]) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", receipt["image_id"]) is None
        or type(receipt["configured_image"]) is not str
        or not receipt["configured_image"]
        or type(receipt["gpu_uuid"]) is not str
        or re.fullmatch(r"GPU-[0-9a-f-]{8,80}", receipt["gpu_uuid"]) is None
    ):
        raise LiveQ1Refusal("boundary attestation identity drifted")
    for name in ("gpu_compute_pids",):
        values = receipt[name]
        if (
            type(values) is not list
            or not values
            or len(values) != len(set(values))
            or any(type(pid) is not int or pid <= 0 for pid in values)
            or values != sorted(values)
        ):
            raise LiveQ1Refusal("boundary process set drifted")
    if (
        type(receipt["requests_running"]) is not int
        or receipt["requests_running"] != 0
        or type(receipt["request_success_total"]) is not int
        or receipt["request_success_total"] != completed_attempts
        or receipt["host_listener_present"] is not True
        or type(receipt["container_init_pid"]) is not int
        or receipt["container_init_pid"] <= 0
        or receipt["internal_listener_port"] != 8000
        or type(receipt["unexpected_listener_count"]) is not int
        or receipt["unexpected_listener_count"] != 0
        or type(receipt["prefix_cache_hits"]) is not int
        or receipt["prefix_cache_hits"] != 0
        or type(receipt["prefix_cache_queries"]) is not int
        or receipt["prefix_cache_queries"] != 0
    ):
        raise LiveQ1Refusal("boundary request counters drifted")
    return receipt


def validate_live_envelope(
    raw: bytes,
    status: int,
    expected_model: str,
    response_schema_raw: bytes,
) -> tuple[bytes, bytes]:
    """Return exact content bytes and a canonical diagnostic projection."""

    if type(status) is not int or status != 200:
        raise LiveQ1Refusal("provider status is not 200")
    envelope = strict_json(raw)
    try:
        schema = parse_canonical(response_schema_raw)
    except CanonicalJsonError as error:
        raise LiveQ1Refusal("response schema bytes drifted") from error
    if type(envelope) is not dict or envelope.get("model") != expected_model:
        raise LiveQ1Refusal("provider model identity drifted")
    choices = envelope.get("choices")
    usage = envelope.get("usage")
    if (
        type(choices) is not list
        or len(choices) != 1
        or type(choices[0]) is not dict
        or choices[0].get("finish_reason") != "stop"
        or type(choices[0].get("message")) is not dict
        or type(choices[0]["message"].get("content")) is not str
    ):
        raise LiveQ1Refusal("provider choice, finish, or content drifted")
    if (
        type(usage) is not dict
        or any(
            type(usage.get(name)) is not int or usage[name] < 0
            for name in ("prompt_tokens", "completion_tokens", "total_tokens")
        )
        or usage["prompt_tokens"] + usage["completion_tokens"] != usage["total_tokens"]
    ):
        raise LiveQ1Refusal("provider usage accounting drifted")
    content = choices[0]["message"]["content"].encode("utf-8", errors="strict")
    parsed = strict_json(content)
    validate_response_schema(schema, parsed, instance=True)
    return content, canonical_bytes(parsed)


def bind_case_material(
    case: Mapping[str, Any],
    material: LiveQ1CaseMaterial,
    model: str,
) -> bytes:
    """Reconstruct and verify every raw-material and request binding."""

    if type(case) is not dict or material.case_id != case.get("case_id"):
        raise LiveQ1Refusal("case/material identity drifted")
    expected = {
        "instruction_sha256": sha256(material.instruction_bytes).hexdigest(),
        "model_input_sha256": sha256(material.model_input_bytes).hexdigest(),
        "response_schema_sha256": sha256(material.response_schema_bytes).hexdigest(),
        "rng_sha256": sha256(material.rng_bytes).hexdigest(),
    }
    if any(case.get(name) != digest for name, digest in expected.items()):
        raise LiveQ1Refusal("raw case material binding drifted")
    request = build_live_q1_request(model, case["call_class"], material)
    if (
        case.get("max_output_tokens") != material.max_output_tokens
        or case.get("request_sha256") != sha256(request).hexdigest()
    ):
        raise LiveQ1Refusal("constructed request binding drifted")
    return request


__all__ = [
    "BOUNDARY_SCHEMA",
    "CALL_CLASSES",
    "CONSUMPTION_REGISTRY",
    "CONSUMPTION_REGISTRY_PATH",
    "CONSUMPTION_REGISTRY_SCHEMA",
    "FALSIFIED",
    "INCONCLUSIVE",
    "LiveQ1CaseMaterial",
    "LiveQ1Refusal",
    "MARKER_SCHEMA",
    "NAMESPACE",
    "NONCLAIMS",
    "PLAN_SCHEMA",
    "REPRODUCED",
    "RUNNER_VERSION",
    "TERMINALS",
    "VOID",
    "bind_case_material",
    "build_live_q1_request",
    "derive_live_q1_order",
    "make_live_q1_start_marker",
    "strict_json",
    "validate_live_envelope",
    "validate_boundary_attestation",
    "validate_live_q1_plan",
    "validate_live_q1_start_marker",
    "validate_response_schema",
]
