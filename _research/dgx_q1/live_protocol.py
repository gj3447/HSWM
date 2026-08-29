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
import ipaddress
import json
import re
from typing import Any
from urllib.parse import urlsplit

from _research.dnrd5.canonical_json import (
    CanonicalJsonError,
    canonical_bytes,
    canonical_sha256,
    parse_canonical,
)


PLAN_SCHEMA = "hswm-dgx-q1-live-response-exactness/v1"
MARKER_SCHEMA = "hswm-dgx-q1-live-start-marker/v1"
NAMESPACE = "DNRD5-Q1-LIVE-QUALIFICATION-ONLY/v1"
RUNNER_VERSION = "hswm-dgx-q1-live-runner/v3"
BOUNDARY_SCHEMA = "hswm-dgx-q1-live-boundary-attestation/v3"
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
    "NOT_A_BATCH_INVARIANCE_QUALIFICATION",
    "NOT_MODEL_SUPPORT_BEYOND_THE_OBSERVED_SERIALIZED_CONFIGURATION",
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
_LISTENER_ENDPOINT = re.compile(
    r"^(?:(?P<ipv4>[0-9.]+)(?:%(?P<ipv4_zone>[A-Za-z0-9_.-]+))?"
    r"|\[(?P<ipv6>[0-9A-Fa-f:.]+)(?:%(?P<ipv6_zone>[A-Za-z0-9_.-]+))?\])"
    r":(?P<port>[0-9]{1,5})$"
)
_DECLARED_ISOLATION_STATIC = {
    "batch_invariant": False,
    "boundary": "FINITE_DECLARED_SERIALIZED_CONTROL_CONTRACT_WITHOUT_BATCH_INVARIANCE",
    "dedicated_gpu": True,
    "dedicated_node": True,
    "dedicated_process": True,
    "max_num_seqs": 1,
    "network_scope": "LOOPBACK_INGRESS_ONLY_OUTBOUND_NOT_ATTESTED",
    "other_inference_processes": 0,
    "prefix_cache": False,
    "v1_multiprocessing": False,
}
_DYNAMIC_KERNEL_RPC_POLICY = {
    "schema_version": "hswm-dgx-q1-dynamic-kernel-rpc-listener-policy/v1",
    "program": 100021,
    "service": "nlockmgr",
    "owner": "superuser",
    "versions": [1, 3, 4],
    "netids": ["tcp", "tcp6", "udp", "udp6"],
    "tcp_wildcard_hosts": ["0.0.0.0", "[::]"],
    "nlm_tcpport": 0,
    "nlm_udpport": 0,
    "required_tcp_listener_count": 2,
    "observation": "RPCINFO_LOCAL_REGISTRATION_JOINED_TO_PRIVILEGED_HOST_TCP_LISTENER_ROWS",
}
_DYNAMIC_REGISTRATION_KEYS = {
    "program", "version", "netid", "address", "service", "owner"
}
_RPC_IPV4_ADDRESS = re.compile(r"^0\.0\.0\.0\.([0-9]{1,3})\.([0-9]{1,3})$")
_RPC_IPV6_ADDRESS = re.compile(r"^::\.([0-9]{1,3})\.([0-9]{1,3})$")


class LiveQ1Refusal(ValueError):
    """The proposed plan, material, response, or marker is outside live Q1."""


def loopback_q1_target(endpoint: str) -> str:
    """Return the exact host listener target for the fixed Q1 HTTP endpoint."""

    if type(endpoint) is not str or len(endpoint) > 512:
        raise LiveQ1Refusal("endpoint is not bounded text")
    parsed = urlsplit(endpoint)
    try:
        port = parsed.port
    except ValueError as error:
        raise LiveQ1Refusal("live Q1 endpoint port drifted") from error
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port is None
        or not 1 <= port <= 65_535
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != "/v1/chat/completions"
        or parsed.query
        or parsed.fragment
        or endpoint != f"http://127.0.0.1:{port}/v1/chat/completions"
    ):
        raise LiveQ1Refusal("live Q1 requires the exact loopback HTTP chat path")
    return f"127.0.0.1:{port}"


def _listener_endpoint(value: Any) -> str:
    if type(value) is not str or not value or any(char.isspace() for char in value):
        raise LiveQ1Refusal("host listener endpoint is not nonempty whitespace-free text")
    match = _LISTENER_ENDPOINT.fullmatch(value)
    if match is None:
        raise LiveQ1Refusal("host listener endpoint grammar drifted")
    try:
        if match["ipv4"] is not None:
            ipaddress.IPv4Address(match["ipv4"])
        else:
            ipaddress.IPv6Address(match["ipv6"])
        port = int(match["port"])
    except ValueError as error:
        raise LiveQ1Refusal("host listener endpoint address/port drifted") from error
    if not 1 <= port <= 65_535:
        raise LiveQ1Refusal("host listener endpoint port drifted")
    return value


def listener_inventory_sha256(endpoints: Sequence[str]) -> str:
    """Hash the exact sorted listener inventory representation used by Q1."""

    if type(endpoints) not in {list, tuple}:
        raise LiveQ1Refusal("listener inventory must be an ordered endpoint sequence")
    values = tuple(_listener_endpoint(value) for value in endpoints)
    if not values or len(values) != len(set(values)):
        raise LiveQ1Refusal("listener inventory is not nonempty unique endpoints")
    return sha256("\n".join(sorted(values)).encode()).hexdigest()


def validate_host_tcp_listener_rows(value: Any) -> tuple[str, ...]:
    """Validate self-contained normalized ``ss -ltnpH`` TCP listener rows."""

    if type(value) is not list or not value or len(value) > 256:
        raise LiveQ1Refusal("host TCP listener rows are not bounded nonempty list")
    rows: list[str] = []
    endpoints: set[str] = set()
    for row in value:
        try:
            byte_length = len(row.encode("utf-8", errors="strict")) if type(row) is str else 0
        except UnicodeEncodeError as error:
            raise LiveQ1Refusal("host TCP listener row is not UTF-8 text") from error
        if (
            type(row) is not str
            or not 1 <= byte_length <= 16_384
            or any(ord(char) < 32 or ord(char) == 127 for char in row)
        ):
            raise LiveQ1Refusal("host TCP listener row text drifted")
        fields = row.split()
        if len(fields) < 5 or fields[0] != "LISTEN":
            raise LiveQ1Refusal("host TCP listener row shape/state drifted")
        endpoint = _listener_endpoint(fields[3])
        if endpoint in endpoints:
            raise LiveQ1Refusal("host TCP listener endpoint multiplicity drifted")
        endpoints.add(endpoint)
        rows.append(row)
    if rows != sorted(set(rows)):
        raise LiveQ1Refusal("host TCP listener rows are not sorted unique")
    return tuple(rows)


def _rpc_port(address: Any, netid: str) -> int:
    if type(address) is not str:
        raise LiveQ1Refusal("dynamic kernel RPC address drifted")
    match = (
        _RPC_IPV4_ADDRESS.fullmatch(address)
        if netid in {"tcp", "udp"}
        else _RPC_IPV6_ADDRESS.fullmatch(address)
    )
    if match is None:
        raise LiveQ1Refusal("dynamic kernel RPC wildcard address drifted")
    high, low = (int(value) for value in match.groups())
    if high > 255 or low > 255:
        raise LiveQ1Refusal("dynamic kernel RPC address byte drifted")
    port = high * 256 + low
    if port < 1024:
        raise LiveQ1Refusal("dynamic kernel RPC port is not dynamic/unprivileged")
    return port


def validate_dynamic_kernel_rpc_registrations(value: Any) -> tuple[dict[str, Any], ...]:
    """Validate the complete local rpcinfo registration cross-product for nlockmgr."""

    if type(value) is not list or len(value) != 12:
        raise LiveQ1Refusal("dynamic kernel RPC registrations must be exactly 12 rows")
    rows: list[dict[str, Any]] = []
    addresses: dict[str, str] = {}
    combinations: set[tuple[int, str]] = set()
    for row in value:
        row = _object(row, _DYNAMIC_REGISTRATION_KEYS, "dynamic kernel RPC registration")
        if (
            type(row["program"]) is not int
            or type(row["version"]) is not int
            or type(row["netid"]) is not str
            or type(row["service"]) is not str
            or type(row["owner"]) is not str
            or row["program"] != _DYNAMIC_KERNEL_RPC_POLICY["program"]
            or row["version"] not in _DYNAMIC_KERNEL_RPC_POLICY["versions"]
            or row["netid"] not in _DYNAMIC_KERNEL_RPC_POLICY["netids"]
            or row["service"] != _DYNAMIC_KERNEL_RPC_POLICY["service"]
            or row["owner"] != _DYNAMIC_KERNEL_RPC_POLICY["owner"]
        ):
            raise LiveQ1Refusal("dynamic kernel RPC registration identity drifted")
        _rpc_port(row["address"], row["netid"])
        netid = row["netid"]
        if netid in addresses and addresses[netid] != row["address"]:
            raise LiveQ1Refusal("dynamic kernel RPC netid address is not stable")
        addresses[netid] = row["address"]
        combinations.add((row["version"], netid))
        rows.append(row)
    expected = {
        (version, netid)
        for version in _DYNAMIC_KERNEL_RPC_POLICY["versions"]
        for netid in _DYNAMIC_KERNEL_RPC_POLICY["netids"]
    }
    if (
        combinations != expected
        or len(combinations) != len(rows)
        or rows != sorted(rows, key=canonical_bytes)
    ):
        raise LiveQ1Refusal("dynamic kernel RPC registration cross-product/order drifted")
    return tuple(rows)


def dynamic_kernel_rpc_tcp_listeners(value: Any) -> tuple[str, ...]:
    """Derive the one IPv4 and one IPv6 nlockmgr TCP listener from rpcinfo."""

    rows = validate_dynamic_kernel_rpc_registrations(value)
    addresses = {row["netid"]: row["address"] for row in rows}
    ipv4_port = _rpc_port(addresses["tcp"], "tcp")
    ipv6_port = _rpc_port(addresses["tcp6"], "tcp6")
    listeners = (f"0.0.0.0:{ipv4_port}", f"[::]:{ipv6_port}")
    return tuple(sorted(listeners))


def validate_declared_isolation_contract(raw: bytes, *, target: str) -> dict[str, Any]:
    """Validate the frozen listener baseline and the non-listener Q1 controls."""

    _listener_endpoint(target)
    try:
        declared = parse_canonical(raw)
    except (CanonicalJsonError, TypeError) as error:
        raise LiveQ1Refusal("declared isolation identity is not canonical JSON") from error
    keys = set(_DECLARED_ISOLATION_STATIC) | {
        "schema_version",
        "host_listener_allowlist",
        "host_listener_allowlist_sha256",
        "host_listener_policy",
        "dynamic_kernel_rpc_listener_policy",
    }
    declared = _object(declared, keys, "declared isolation identity")
    if (
        declared["schema_version"] != "hswm-dgx-q1-declared-isolation/v3"
        or any(declared[name] != value for name, value in _DECLARED_ISOLATION_STATIC.items())
        or declared["host_listener_policy"]
        != "EXACT_FROZEN_STATIC_PLUS_RPCBOUND_DYNAMIC_NLOCKMGR_PLUS_ONE_Q1_TARGET"
        or type(declared["host_listener_allowlist"]) is not list
        or type(declared["host_listener_allowlist_sha256"]) is not str
        or declared["dynamic_kernel_rpc_listener_policy"] != _DYNAMIC_KERNEL_RPC_POLICY
    ):
        raise LiveQ1Refusal("declared isolation identity drifted")
    allowlist = declared["host_listener_allowlist"]
    if (
        not allowlist
        or any(_listener_endpoint(value) != value for value in allowlist)
        or allowlist != sorted(set(allowlist))
        or target in allowlist
        or "127.0.0.1:11434" in allowlist
        or declared["host_listener_allowlist_sha256"] != listener_inventory_sha256(allowlist)
    ):
        raise LiveQ1Refusal("declared isolation listener baseline drifted")
    return declared


# Identity is the historical name used by launch-side callers.  Keep one
# implementation so freezer, runner, and launcher accept identical bytes.
validate_declared_isolation_identity = validate_declared_isolation_contract


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
    declared_isolation_raw: bytes,
    target: str,
    startup_dynamic_kernel_rpc_registrations: Sequence[Mapping[str, Any]] | None = None,
    startup_dynamic_kernel_rpc_tcp_listeners: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Validate a typed, per-boundary observation from the exclusive lease."""

    plan = validate_live_q1_plan(plan_raw)
    declared = validate_declared_isolation_contract(
        declared_isolation_raw, target=target
    )
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
        "host_tcp_listener_rows",
        "host_tcp_listener_rows_sha256",
        "dynamic_kernel_rpc_registrations",
        "dynamic_kernel_rpc_registrations_sha256",
        "dynamic_kernel_rpc_tcp_listeners",
        "nlm_tcpport",
        "nlm_udpport",
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
        "host_tcp_listener_rows_sha256",
        "raw_metrics_sha256",
    ):
        _digest(receipt[name], name)
    registrations = validate_dynamic_kernel_rpc_registrations(
        receipt["dynamic_kernel_rpc_registrations"]
    )
    listeners = dynamic_kernel_rpc_tcp_listeners(
        receipt["dynamic_kernel_rpc_registrations"]
    )
    if (
        receipt["dynamic_kernel_rpc_registrations_sha256"]
        != canonical_sha256(list(registrations))
        or type(receipt["dynamic_kernel_rpc_tcp_listeners"]) is not list
        or tuple(receipt["dynamic_kernel_rpc_tcp_listeners"]) != listeners
        or type(receipt["nlm_tcpport"]) is not int
        or type(receipt["nlm_udpport"]) is not int
        or receipt["nlm_tcpport"] != 0
        or receipt["nlm_udpport"] != 0
    ):
        raise LiveQ1Refusal("dynamic kernel RPC boundary binding drifted")
    static = declared["host_listener_allowlist"]
    inventory = tuple(sorted((*static, *listeners, target)))
    rows = validate_host_tcp_listener_rows(receipt["host_tcp_listener_rows"])
    row_endpoints = tuple(row.split()[3] for row in rows)
    if (
        receipt["host_tcp_listener_rows_sha256"] != canonical_sha256(list(rows))
        or set(row_endpoints) != set(inventory)
        or len(row_endpoints) != len(inventory)
        or len(inventory) != len(set(inventory))
        or "127.0.0.1:11434" in listeners
        or target in listeners
        or any(listener in static for listener in listeners)
        or any(
            "users:" in row or "pid=" in row
            for row, endpoint in zip(rows, row_endpoints, strict=True)
            if endpoint in listeners
        )
        or receipt["host_listener_inventory_sha256"]
        != listener_inventory_sha256(inventory)
    ):
        raise LiveQ1Refusal("host listener inventory binding drifted")
    if phase == "STARTUP":
        if (
            startup_dynamic_kernel_rpc_registrations is not None
            or startup_dynamic_kernel_rpc_tcp_listeners is not None
        ):
            raise LiveQ1Refusal("startup dynamic kernel RPC baseline drifted")
    elif (
        startup_dynamic_kernel_rpc_registrations is None
        or startup_dynamic_kernel_rpc_tcp_listeners is None
        or tuple(startup_dynamic_kernel_rpc_registrations) != registrations
        or tuple(startup_dynamic_kernel_rpc_tcp_listeners) != listeners
    ):
        raise LiveQ1Refusal("dynamic kernel RPC values changed after startup")
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
    "dynamic_kernel_rpc_tcp_listeners",
    "listener_inventory_sha256",
    "validate_host_tcp_listener_rows",
    "make_live_q1_start_marker",
    "loopback_q1_target",
    "strict_json",
    "validate_live_envelope",
    "validate_boundary_attestation",
    "validate_declared_isolation_contract",
    "validate_declared_isolation_identity",
    "validate_dynamic_kernel_rpc_registrations",
    "validate_live_q1_plan",
    "validate_live_q1_start_marker",
    "validate_response_schema",
]
