"""Fail-closed protocol primitives for DNRD5-QCASE024-MI-1.

This is a post-result-selected mechanism-isolation diagnostic.  It is not a
retry of Q1 and cannot authorize a DNRD-5 occurrence, Source A, or an HSWM
causal claim.
"""
from __future__ import annotations

from hashlib import sha256
import re
from typing import Any, Mapping

from _research.dnrd5.canonical_json import CanonicalJsonError, canonical_bytes, parse_canonical
from _research.dgx_q1.live_protocol import SYSTEM_MESSAGE, validate_response_schema

PLAN_SCHEMA = "hswm-dgx-qcase024-mi-plan/v3"
MARKER_SCHEMA = "hswm-dgx-qcase024-mi-start-marker/v3"
NAMESPACE = "DNRD5-QCASE024-MECHANISM-ISOLATION-ONLY/v3"
RUNNER_VERSION = "hswm-dgx-qcase024-mi-runner/v3"
FREEZE_SCHEMA = "hswm-dgx-qcase024-mi-preregistration-freeze/v3"
REGISTRY = {
    "schema_version": "hswm-dgx-qcase024-mi-plan-consumption-registry/v3",
    "path": "/mnt/hswm/evidence/hswm-dnrd5-qcase024-mi-1-usage-v3-consumption-v3",
    "scope": "PINNED_DGX_NODE_LOCAL_DURABLE_PLAN_HASH_REGISTRY",
    "boundary": "NODE_LOCAL_PATH_BINDING_NOT_DISTRIBUTED_GLOBAL_CONSENSUS",
    "terminal": "ONE_DURABLE_BURN_PER_PLAN_HASH_AT_THE_DECLARED_PATH",
}
USAGE_NORMALIZATION = {
    "schema_version": "hswm-dgx-qcase024-mi-usage-normalization/v3",
    "required_integer_fields": ["prompt_tokens", "completion_tokens", "total_tokens"],
    "optional_null_fields": ["prompt_tokens_details"],
    "unknown_fields": "REFUSE",
    "invariant": "PROMPT_TOKENS_PLUS_COMPLETION_TOKENS_EQUALS_TOTAL_TOKENS",
    "boundary": "RAW_PROVIDER_ENVELOPE_RETAINED_WITHOUT_DROPPING_NULL_DETAIL_FIELD",
}
ARMS = ("ASYNC_ENABLED", "ASYNC_DISABLED")
BLOCKS = (
    ("ASYNC_ENABLED", "B01"),
    ("ASYNC_DISABLED", "B01"),
    ("ASYNC_DISABLED", "B02"),
    ("ASYNC_ENABLED", "B02"),
)
NONCLAIMS = (
    "POST_RESULT_SELECTED_QCASE024_DIAGNOSTIC_NOT_CONFIRMATORY_OR_GENERALIZABLE",
    "NOT_A_Q1_RETRY_OR_BATCH_INVARIANCE_QUALIFICATION",
    "NOT_A_DNRD5_300_BLOCK_OCCURRENCE_OR_SOURCE_A_AUTHORIZATION",
    "NOT_CAUSAL_ATTRIBUTION_TO_SCHEDULING_GDN_FP8_OR_PROVIDER_INTERNALS",
    "NOT_PROOF_OF_NO_INTERFERENCE_OR_HSWM_CAUSAL_LEARNING",
    "NOT_PROOF_OF_CONSCIOUSNESS_SELFHOOD_OR_SCALE_INVARIANT_CAUSAL_CLOSURE",
)
IDENTITY_NAMES = (
    "endpoint_sha256", "model_identity_sha256", "runtime_identity_sha256",
    "tls_identity_sha256", "declared_isolation_contract_sha256",
    "model_snapshot_manifest_sha256",
)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_GIT = re.compile(r"^[0-9a-f]{40}$")
_ATTEMPT = re.compile(r"^MI-024-V3-(ASYNC_ENABLED|ASYNC_DISABLED)-B0[12]-R00[1-4]$")
EXPECTED_MATERIAL_SHA256 = {
    "instruction.txt": "8e13131449ba0f31cb7305490dec680f6808006db2e5b50cc8614b172c85b907",
    "model_input.json": "5902dec004e606aaf46b8a5d80c45ab855f275d714d111b2430d86d0e1c1a273",
    "response_schema.json": "a623afd2cace659731c46b336fd4cb75c071e60f425fa583e8995abe7ff83940",
    "rng.bin": "69b1f0ef2be0d6519baa19562928cc6ed3a458e382e48508a4cb47292063bd78",
}
EXPECTED_REQUEST_SHA256 = "fec3b64ce00d750e67a34374fe9d1e5e7fa6232294b8990e0aa4f352bc52fac9"
TERMINALS = (
    "LIVE_COMPLETE_DGX_QCASE024_MECHANISM_DIAGNOSTIC",
    "INCONCLUSIVE_DGX_QCASE024_MI_INCOMPLETE_LIVE_SLOTS",
    "INCONCLUSIVE_DGX_QCASE024_MI_REQUIRED_LOGPROB_OR_ALIGNMENT_UNAVAILABLE",
    "VOID_DGX_QCASE024_MI_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH",
)
PINNED = {"endpoint": "http://127.0.0.1:18080/v1/chat/completions", "model": "qwen3.6-35b-a3b", "repository": "Qwen/Qwen3.6-35B-A3B-FP8", "revision": "95a723d08a9490559dae23d0cff1d9466213d989", "snapshot": "2ece6b46248e818cbf93aa30299300f7dd4c60d9351960ec790cc8b420376e47", "vllm": "0.25.1", "image": "vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089", "image_id": "sha256:30a38a1d74a17365eca400e83ffd885b250e0c8c0d3c5b508afa8c412d2ddf95", "gpu_uuid": "GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5", "gpu_name": "NVIDIA GB10", "driver": "580.126.09", "cc": "12.1"}
EXPECTED_Q1_SELECTION = {"q1_source_commit": "4e3238b472c88c3e51e7849472f46d8f8e368d9d", "q1_result_commit": "a6f13445375f8195a35e025810cc1628c41b5641", "q1_v3_plan_sha256": "b054396e68620c2bcc97a9da9c429edda3182c93d41a573e6eef6fe30c997c22", "q1_live_receipt_sha256": "a10d107463823218ada992945d7b72167669e0948b3019dd680607a530c30978", "q1_evidence_receipt_sha256": "cc53ba6d42ebe52d648fbd777850b9b96c9ae50e7fda99aa5cf7456a6344b51f", "q1_exact_ledger_sha256": "f3cdfff46e1ee4ff0973531296863970f7bc9fa21eff1ea60ddc4da7a6e13f00", "q1_result_projection_sha256": "17649d84046297a0ad5ecaadb5efdcc35d02f8ef58b9784ff8de65048b611d22", "selected_request_sha256": "c24c74241bbf670b3e2c640f3acd18cb449d3172659bde5fcb08262950a53a19", "q1_terminal": "LIVE_FALSIFIED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FROZEN_Q1", "selected_case": "QCASE-024", "selection_status": "POST_RESULT_SELECTED_NOT_CONFIRMATORY", "selection_basis": "ONE_SEMANTIC_ASSISTANT_CONTENT_VARIANT_IN_Q1_V3"}
SERVER_PREFIX = ("--model", "/model-repository/snapshots/95a723d08a9490559dae23d0cff1d9466213d989", "--served-model-name", "qwen3.6-35b-a3b", "--host", "0.0.0.0", "--port", "8000", "--max-num-seqs", "1", "--no-enable-prefix-caching", "--max-model-len", "32768", "--gpu-memory-utilization", "0.500", "--generation-config", "vllm", "--seed", "0", "--enforce-eager", "--language-model-only", "--max-logprobs", "20", "--logprobs-mode", "processed_logprobs")
REQUIRED_ENV = ("HF_HOME=/cache/huggingface", "HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub", "VLLM_CACHE_ROOT=/cache/compile/vllm", "TORCHINDUCTOR_CACHE_DIR=/cache/compile/torchinductor", "TRITON_CACHE_DIR=/cache/compile/triton", "HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1", "VLLM_ENABLE_V1_MULTIPROCESSING=0", "PYTHONHASHSEED=0", "CUBLAS_WORKSPACE_CONFIG=:4096:8")


class MiRefusal(ValueError):
    """The proposed diagnostic drifted outside its frozen boundary."""


def _obj(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise MiRefusal(f"{label} key set drifted")
    return value


def _digest(value: Any, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None or value == "0" * 64:
        raise MiRefusal(f"{label} must be a non-placeholder SHA-256")
    return value


def _canonical(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw:
        raise MiRefusal(f"{label} must be nonempty bytes")
    try:
        value = parse_canonical(raw)
    except (CanonicalJsonError, TypeError) as error:
        raise MiRefusal(f"{label} must be canonical JSON") from error
    if type(value) is not dict:
        raise MiRefusal(f"{label} must be an object")
    return value


def _source(value: Any, label: str) -> dict[str, Any]:
    item = _obj(value, {"commit", "tree", "ci_receipt_sha256", "ci_terminal"}, label)
    if (type(item["commit"]) is not str or _GIT.fullmatch(item["commit"]) is None
            or item["commit"] == "0" * 40 or type(item["tree"]) is not str
            or _GIT.fullmatch(item["tree"]) is None or item["tree"] == "0" * 40
            or item["ci_terminal"] != "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"):
        raise MiRefusal(f"{label} source identity drifted")
    _digest(item["ci_receipt_sha256"], f"{label} CI receipt")
    return item


def build_mi_request(model: str, material: Mapping[str, bytes]) -> bytes:
    """Build the sole QCASE-024 semantic request with diagnostic logprobs."""
    if type(model) is not str or not model or set(material) != {
        "instruction.txt", "model_input.json", "response_schema.json", "rng.bin"
    }:
        raise MiRefusal("MI request model/material binding drifted")
    if {name: sha256(raw).hexdigest() for name, raw in material.items()} != EXPECTED_MATERIAL_SHA256:
        raise MiRefusal("MI material bytes differ from checked-in Q1 v3 QCASE-024")
    try:
        instruction = material["instruction.txt"].decode("utf-8", errors="strict")
        model_input = parse_canonical(material["model_input.json"])
        schema = parse_canonical(material["response_schema.json"])
    except (UnicodeDecodeError, CanonicalJsonError) as error:
        raise MiRefusal("MI material is not UTF-8/canonical JSON") from error
    if (not instruction or type(model_input) is not dict
            or set(model_input) != {"behaviorProjection", "freshProbe"}
            or model_input.get("freshProbe", {}).get("case") != "QCASE-024"
            or type(material["rng.bin"]) is not bytes or len(material["rng.bin"]) != 32):
        raise MiRefusal("MI requires exactly QCASE-024 material")
    validate_response_schema(schema)
    return canonical_bytes({
        "chat_template_kwargs": {"enable_thinking": False},
        "logprobs": True,
        "top_logprobs": 20,
        "max_tokens": 256,
        "messages": [
            {"content": SYSTEM_MESSAGE, "role": "system"},
            {"content": canonical_bytes({
                "contractVersion": "hswm-dgx-q1-live-model-input/v1",
                "callClass": "FRESH_PROBE", "instruction": instruction,
                "input": model_input,
            }).decode("utf-8"), "role": "user"},
        ],
        "model": model, "n": 1,
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "hswm_dgx_q1_live_fresh_probe", "schema": schema, "strict": True,
        }},
        "seed": int.from_bytes(sha256(material["rng.bin"]).digest()[:6], "big"),
        "stream": False, "temperature": 0, "top_p": 1,
    })


def validate_arm_identities(identities: Mapping[str, Mapping[str, bytes]]) -> None:
    if set(identities) != set(ARMS):
        raise MiRefusal("MI requires exactly two named arm identity maps")
    common: dict[str, bytes] | None = None
    async_values: dict[str, bool] = {}
    for arm in ARMS:
        rows = identities[arm]
        if set(rows) != set(IDENTITY_NAMES):
            raise MiRefusal("MI arm identity key set drifted")
        parsed = {name: _canonical(raw, name) for name, raw in rows.items()}
        runtime = parsed["runtime_identity_sha256"]
        endpoint = parsed["endpoint_sha256"]
        model = parsed["model_identity_sha256"]
        snapshot = parsed["model_snapshot_manifest_sha256"]
        tls = parsed["tls_identity_sha256"]
        if (sha256(rows["declared_isolation_contract_sha256"]).hexdigest() != "ac594ec24eb2a096b0053096c8650aeca33aa290d7146bd0793abddcd64e9ba1"
                or {"endpoint": endpoint.get("endpoint"), "model": model.get("model"), "repository": model.get("repository"), "revision": model.get("revision")} != {key: PINNED[key] for key in ("endpoint", "model", "repository", "revision")}
                or sha256(rows["model_snapshot_manifest_sha256"]).hexdigest() != PINNED["snapshot"]
                or set(endpoint) != {"schema_version", "endpoint", "method", "transport"}
                or endpoint.get("schema_version") != "hswm-dgx-q1-endpoint-identity/v1"
                or endpoint.get("method") != "POST" or endpoint.get("transport") != "LOOPBACK_HTTP_NO_TLS"
                or type(endpoint.get("endpoint")) is not str
                or set(model) != {"schema_version", "model", "repository", "revision", "snapshot_manifest_sha256"}
                or model.get("schema_version") != "hswm-dgx-q1-model-identity/v1"
                or type(model.get("model")) is not str or not model["model"]
                or type(model.get("repository")) is not str or not model["repository"]
                or type(model.get("revision")) is not str or _GIT.fullmatch(model["revision"]) is None
                or model.get("snapshot_manifest_sha256") != sha256(rows["model_snapshot_manifest_sha256"]).hexdigest()
                or set(snapshot) != {"schema_version", "repository", "revision", "file_count", "total_byte_length", "files", "files_sha256"}
                or snapshot.get("schema_version") != "hswm-dgx-q1-model-snapshot-manifest/v1"
                or snapshot.get("repository") != model["repository"] or snapshot.get("revision") != model["revision"]
                or type(snapshot.get("file_count")) is not int or snapshot["file_count"] <= 0
                or type(snapshot.get("files")) is not list or len(snapshot["files"]) != snapshot["file_count"]
                or tls != {"schema_version": "hswm-dgx-q1-tls-identity/v1", "endpoint_scheme": "http", "tls": "NOT_APPLICABLE_LOOPBACK_ONLY"}):
            raise MiRefusal("MI endpoint/model/snapshot/TLS identity join drifted")
        runtime_keys = {"schema_version", "container_image", "image_id", "vllm_version", "gpu_uuid", "gpu_name", "gpu_driver_version", "gpu_compute_capability", "endpoint", "served_model", "model_revision", "model_snapshot_manifest_sha256", "max_model_len", "max_num_seqs", "gpu_memory_utilization_milli", "prefix_cache", "enforce_eager", "batch_invariant", "v1_multiprocessing", "model_loading_offline", "generation_config", "engine_seed", "language_model_only", "container_internal_port", "container_network_mode", "container_ipc_mode", "host_publish_ip", "async_scheduling", "server_arguments", "required_environment", "max_logprobs", "logprobs_mode"}
        if (set(runtime) != runtime_keys
                or runtime.get("schema_version") != "hswm-dgx-qcase024-mi-runtime-identity/v3"
                or runtime.get("max_num_seqs") != 1 or runtime.get("prefix_cache") is not False
                or runtime.get("enforce_eager") is not True or runtime.get("batch_invariant") is not False
                or runtime.get("v1_multiprocessing") is not False or runtime.get("engine_seed") != 0
                or runtime.get("max_logprobs") != 20 or runtime.get("logprobs_mode") != "processed_logprobs"
                or type(runtime.get("async_scheduling")) is not bool
                or {"container_image": runtime.get("container_image"), "image_id": runtime.get("image_id"), "vllm_version": runtime.get("vllm_version"), "gpu_uuid": runtime.get("gpu_uuid"), "gpu_name": runtime.get("gpu_name"), "gpu_driver_version": runtime.get("gpu_driver_version"), "gpu_compute_capability": runtime.get("gpu_compute_capability"), "max_model_len": runtime.get("max_model_len"), "gpu_memory_utilization_milli": runtime.get("gpu_memory_utilization_milli")} != {"container_image": PINNED["image"], "image_id": PINNED["image_id"], "vllm_version": PINNED["vllm"], "gpu_uuid": PINNED["gpu_uuid"], "gpu_name": PINNED["gpu_name"], "gpu_driver_version": PINNED["driver"], "gpu_compute_capability": PINNED["cc"], "max_model_len": 32768, "gpu_memory_utilization_milli": 500}
                or type(runtime.get("server_arguments")) is not list
                or type(runtime.get("required_environment")) is not list
                or runtime.get("endpoint") != endpoint["endpoint"]
                or runtime.get("served_model") != model["model"]
                or runtime.get("model_revision") != model["revision"]
                or runtime.get("model_snapshot_manifest_sha256") != sha256(rows["model_snapshot_manifest_sha256"]).hexdigest()):
            raise MiRefusal("MI runtime identity controls drifted")
        required = {"--max-logprobs", "20", "--logprobs-mode", "processed_logprobs"}
        if tuple(runtime["required_environment"]) != REQUIRED_ENV or tuple(runtime["server_arguments"][:-1]) != SERVER_PREFIX or runtime["server_arguments"][-1] not in {"--async-scheduling", "--no-async-scheduling"} or not required <= set(runtime["server_arguments"]):
            raise MiRefusal("MI runtime lacks required processed-logprob argv")
        async_values[arm] = runtime["async_scheduling"]
        for name in ("endpoint_sha256", "model_identity_sha256", "tls_identity_sha256",
                     "declared_isolation_contract_sha256", "model_snapshot_manifest_sha256"):
            if name == "endpoint_sha256" and parsed[name].get("method") != "POST":
                raise MiRefusal("MI endpoint method drifted")
        values = {name: rows[name] for name in IDENTITY_NAMES if name != "runtime_identity_sha256"}
        if common is None:
            common = values
        elif common != values:
            raise MiRefusal("MI arms may differ only in runtime identity")
    if async_values != {"ASYNC_ENABLED": True, "ASYNC_DISABLED": False}:
        raise MiRefusal("MI async arm identity drifted")
    enabled = _canonical(identities["ASYNC_ENABLED"]["runtime_identity_sha256"], "enabled runtime")
    disabled = _canonical(identities["ASYNC_DISABLED"]["runtime_identity_sha256"], "disabled runtime")
    def normalized(runtime: dict[str, Any]) -> dict[str, Any]:
        result = dict(runtime); result["async_scheduling"] = "ARM_CONTROL"; result["server_arguments"] = [
            "ASYNC_CONTROL" if value in {"--async-scheduling", "--no-async-scheduling"} else value
            for value in runtime["server_arguments"]]
        return result
    if (enabled["server_arguments"].count("--async-scheduling") != 1
            or "--no-async-scheduling" in enabled["server_arguments"]
            or disabled["server_arguments"].count("--no-async-scheduling") != 1
            or "--async-scheduling" in disabled["server_arguments"]
            or normalized(enabled) != normalized(disabled)):
        raise MiRefusal("MI arm runtimes may differ only by explicit async argv")


def validate_mi_plan(raw: bytes) -> dict[str, Any]:
    plan = _canonical(raw, "MI plan")
    keys = {"schema_version", "namespace", "source", "runner_version", "material", "request_sha256", "attempt_ids",
            "post_result_selection", "arms", "block_order", "attempts_per_block", "budget", "zero_retry",
            "consumption_registry", "usage_normalization", "verifier", "evidence_root_genesis_sha256", "allowed_terminals", "nonclaims"}
    plan = _obj(plan, keys, "MI plan")
    if (plan["schema_version"] != PLAN_SCHEMA or plan["namespace"] != NAMESPACE
            or plan["runner_version"] != RUNNER_VERSION or plan["attempts_per_block"] != 4
            or plan["budget"] != 16 or plan["zero_retry"] is not True
            or plan["consumption_registry"] != REGISTRY or plan["nonclaims"] != list(NONCLAIMS)
            or plan["allowed_terminals"] != list(TERMINALS)
            or plan["usage_normalization"] != USAGE_NORMALIZATION):
        raise MiRefusal("MI plan static boundary drifted")
    _source(plan["source"], "MI source")
    material = _obj(plan["material"], {"case_id", "instruction_sha256", "model_input_sha256", "response_schema_sha256", "rng_sha256", "max_output_tokens"}, "MI material")
    if material["case_id"] != "QCASE-024" or material["max_output_tokens"] != 256:
        raise MiRefusal("MI material identity drifted")
    for name in set(material) - {"case_id", "max_output_tokens"}:
        _digest(material[name], name)
    if {"instruction.txt": material["instruction_sha256"], "model_input.json": material["model_input_sha256"], "response_schema.json": material["response_schema_sha256"], "rng.bin": material["rng_sha256"]} != EXPECTED_MATERIAL_SHA256:
        raise MiRefusal("MI material provenance is not the exact checked-in Q1 v3 bytes")
    if _digest(plan["request_sha256"], "MI request") != EXPECTED_REQUEST_SHA256:
        raise MiRefusal("MI request is not the exact pinned instrumented QCASE-024 request")
    selection = _obj(plan["post_result_selection"], {"q1_source_commit", "q1_result_commit", "q1_v3_plan_sha256", "q1_live_receipt_sha256", "q1_evidence_receipt_sha256", "q1_exact_ledger_sha256", "q1_result_projection_sha256", "selected_request_sha256", "q1_terminal", "selected_case", "selection_status", "selection_basis"}, "MI selection")
    if (selection != EXPECTED_Q1_SELECTION or selection["selected_case"] != "QCASE-024" or selection["selection_status"] != "POST_RESULT_SELECTED_NOT_CONFIRMATORY"
            or selection["selection_basis"] != "ONE_SEMANTIC_ASSISTANT_CONTENT_VARIANT_IN_Q1_V3"
            or selection["q1_terminal"] != "LIVE_FALSIFIED_EXACT_ASSISTANT_CONTENT_UTF8_ON_FROZEN_Q1"):
        raise MiRefusal("MI post-result selection boundary drifted")
    for name in ("q1_v3_plan_sha256", "q1_live_receipt_sha256", "q1_evidence_receipt_sha256", "q1_exact_ledger_sha256", "q1_result_projection_sha256", "selected_request_sha256"):
        _digest(selection[name], "MI " + name)
    for name in ("q1_source_commit", "q1_result_commit"):
        if type(selection[name]) is not str or _GIT.fullmatch(selection[name]) is None or selection[name] == "0" * 40:
            raise MiRefusal("MI Q1 commit provenance drifted")
    arms = _obj(plan["arms"], set(ARMS), "MI arms")
    for arm, identities in arms.items():
        item = _obj(identities, set(IDENTITY_NAMES), arm)
        for digest in item.values(): _digest(digest, arm)
    if plan["block_order"] != [{"arm": arm, "block_id": block} for arm, block in BLOCKS]:
        raise MiRefusal("MI must use the fixed ABBA fresh-server block order")
    attempts = [f"MI-024-V3-{arm}-{block}-R{rep:03d}" for arm, block in BLOCKS for rep in range(1, 5)]
    if len(attempts) != 16 or plan["attempt_ids"] != attempts or any(_ATTEMPT.fullmatch(item) is None for item in attempts):
        raise MiRefusal("MI attempt domain drifted")
    verifier = _obj(plan["verifier"], {"source", "build_output_sha256"}, "MI verifier")
    _source(verifier["source"], "MI verifier source"); _digest(verifier["build_output_sha256"], "MI verifier build")
    _digest(plan["evidence_root_genesis_sha256"], "MI root genesis")
    return plan


def make_mi_start_marker(plan_raw: bytes) -> bytes:
    plan = validate_mi_plan(plan_raw)
    return canonical_bytes({"schema_version": MARKER_SCHEMA, "namespace": NAMESPACE,
        "plan_sha256": sha256(plan_raw).hexdigest(), "request_sha256": plan["request_sha256"],
        "scheduled_attempts": [f"MI-024-V3-{arm}-{block}-R{rep:03d}" for arm, block in BLOCKS for rep in range(1, 5)],
        "terminal": "ALL_16_SERIALIZED_POSTS_AND_LOGPROB_OBSERVABILITY_BOUND_BEFORE_LIVE_START",
        "nonclaims": list(NONCLAIMS)})


def validate_mi_start_marker(marker_raw: bytes, plan_raw: bytes) -> dict[str, Any]:
    if marker_raw != make_mi_start_marker(plan_raw):
        raise MiRefusal("MI start marker drifted")
    return _canonical(marker_raw, "MI start marker")
