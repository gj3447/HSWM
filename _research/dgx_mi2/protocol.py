"""Fail-closed primitives for the MI-2 launch-crossed diagnostic.

MI-2 is a post-result-selected, finite diagnostic.  It has no authority to
qualify Source A, create a DNRD-5 causal occurrence, or establish an HSWM
learning, efficacy, FCL, consciousness, or scale-closure claim.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import itertools
import re
from typing import Any, Mapping, Sequence

from _research.dnrd5.canonical_json import CanonicalJsonError, canonical_bytes, parse_canonical


PLAN_SCHEMA = "hswm-dgx-qcase024-mi2-launch-crossed-plan/v1"
MARKER_SCHEMA = "hswm-dgx-qcase024-mi2-launch-crossed-start-marker/v1"
FREEZE_SCHEMA = "hswm-dgx-qcase024-mi2-launch-crossed-preregistration-freeze/v1"
SEED_SCHEMA = "hswm-dgx-qcase024-mi2-launch-crossed-csprng-raw-draw/v2"
GENESIS_SCHEMA = "hswm-dgx-qcase024-mi2-launch-crossed-evidence-root-genesis/v1"
NAMESPACE = "DNRD5-QCASE024-MI-2-LAUNCH-CROSSED-ONLY/v1"
RUNNER_VERSION = "hswm-dgx-qcase024-mi2-launch-crossed-runner/v1"
INSTRUMENT_ID = "DNRD5-QCASE024-MI-2-LAUNCH-CROSSED-V1"
ARMS = ("ASYNC_ENABLED", "ASYNC_DISABLED")
PAIR_COUNT = 12
LAUNCHES_PER_PAIR = 2
REPLICATES_PER_LAUNCH = 2
FRESH_LAUNCHES = PAIR_COUNT * LAUNCHES_PER_PAIR
PRIMARY_POSTS = FRESH_LAUNCHES
TOTAL_POSTS = FRESH_LAUNCHES * REPLICATES_PER_LAUNCH
ALPHA = "0.05"
ENDPOINT_ALPHA = "0.025"
SCHEDULE_DOMAIN = "HSWM-DNRD5-MI2-LAUNCH-CROSSED-SCHEDULE/v1"
SCHEDULES_PER_HALF = 20
SCHEDULE_COUNT = SCHEDULES_PER_HALF * SCHEDULES_PER_HALF
SCHEDULE_SELECTION_LIMIT = ((1 << 256) // SCHEDULE_COUNT) * SCHEDULE_COUNT
SCHEDULE_SELECTION_METHOD = "RAW_CSPRNG_256_BIT_INTEGER_REJECTION_SAMPLING_400_THEN_EXPLICIT_ED_DE_LEXICOGRAPHIC_SCHEDULE"
REGISTRY = {
    "schema_version": "hswm-dgx-qcase024-mi2-launch-crossed-consumption-registry/v1",
    "path": "/mnt/hswm/evidence/hswm-dnrd5-qcase024-mi-2-launch-crossed-v1-consumption-v1",
    "scope": "PINNED_DGX_NODE_LOCAL_DURABLE_PLAN_HASH_REGISTRY",
    "boundary": "NODE_LOCAL_PATH_BINDING_NOT_DISTRIBUTED_GLOBAL_CONSENSUS",
    "terminal": "ONE_DURABLE_BURN_PER_PLAN_HASH_AT_THE_DECLARED_PATH",
}
TERMINALS = (
    "LIVE_COMPLETE_DGX_QCASE024_MI2_RANDOMIZED_LAUNCH_EXPERIMENT",
    "INCONCLUSIVE_DGX_QCASE024_MI2_INCOMPLETE_LAUNCHES",
    "INCONCLUSIVE_DGX_QCASE024_MI2_REQUIRED_CONTENT_OR_TRACE",
    "VOID_DGX_QCASE024_MI2_PROTOCOL_LEDGER_HASH_ORDER_OR_BOUNDARY_BREACH",
)
NONCLAIMS = (
    "POST_RESULT_SELECTED_CASE_FINITE_RANDOMIZED_CONTRAST_ONLY_NOT_GENERALIZABLE",
    "NOT_A_Q1_RETRY_OR_BATCH_INVARIANCE_QUALIFICATION",
    "NOT_A_DNRD5_300_BLOCK_OCCURRENCE_OR_SOURCE_A_AUTHORIZATION",
    "NOT_MECHANISTIC_ATTRIBUTION_TO_PROVIDER_INTERNAL_SCHEDULER_GDN_FP8_KERNEL_OR_LAUNCH_TIME",
    "NOT_PROOF_OF_NO_INTERFERENCE_OR_HSWM_CAUSAL_LEARNING",
    "NOT_PROOF_OF_CONSCIOUSNESS_SELFHOOD_OR_SCALE_INVARIANT_CAUSAL_CLOSURE",
)
IDENTITY_NAMES = (
    "endpoint_sha256", "model_identity_sha256", "runtime_identity_sha256",
    "tls_identity_sha256", "declared_isolation_contract_sha256",
    "model_snapshot_manifest_sha256",
)
EXPECTED_MATERIAL_SHA256 = {
    "instruction.txt": "8e13131449ba0f31cb7305490dec680f6808006db2e5b50cc8614b172c85b907",
    "model_input.json": "5902dec004e606aaf46b8a5d80c45ab855f275d714d111b2430d86d0e1c1a273",
    "response_schema.json": "a623afd2cace659731c46b336fd4cb75c071e60f425fa583e8995abe7ff83940",
    "rng.bin": "69b1f0ef2be0d6519baa19562928cc6ed3a458e382e48508a4cb47292063bd78",
}
EXPECTED_REQUEST_SHA256 = "fec3b64ce00d750e67a34374fe9d1e5e7fa6232294b8990e0aa4f352bc52fac9"
EXPECTED_MI1_SELECTION = {
    "mi1_result_commit": "4891e8560f54983461b1904e7c5f8bb9fcc4cdfe",
    "mi1_result_tree": "c400df84f67a24805af964473c644a293ea02297",
    "mi1_result_ci_receipt_sha256": "f2e84493a1d3f6a5794483c4ecc9de9e81fec938ff53eb5b8978d60d535d304a",
    "mi1_evidence_sha256": "82807014e3b6bbffaa675e4c79f7c25b60a94a2afc5e2bbe7dc45bb896b34681",
    "mi1_result_projection_sha256": "8bd6a537812344a1036e2c4206cd8129ed2294c1b40cca724c8bee4729c7ec43",
    "mi1_ledger_sha256": "838f338946af641f69e0e234eafbe8589be9c783dbc12870e1d110128c8a160b",
    "mi1_terminal": "LIVE_COMPLETE_DGX_QCASE024_MECHANISM_DIAGNOSTIC",
    "mi1_observation_pattern": "BOTH_ARMS_VARIATION",
    "selection_status": "POST_RESULT_SELECTED_CASE_FINITE_RANDOMIZED_CONTRAST_ONLY_NOT_GENERALIZABLE",
}
FULL_TRACE_SCHEMA = "hswm-dgx-mi2-full-processed-logprob-trace/v1"
FIXED_BRANCH_ROW = 20
FIXED_BRANCH_PREFIX_LENGTH = 52
FIXED_BRANCH_PREFIX_SHA256 = "073d99db9361985aa3706af40d268a21bd9bb68fd608dd00a2b51ff3857b3bdf"
FIXED_BRANCH_CANDIDATES = {
    "indicates": {
        "token": " indicates",
        "sha256": "55fde3431b756dfca90d8b612bb85fd7d7a282438be28c060af78d5081c0470e",
    },
    "explicitly": {
        "token": " explicitly",
        "sha256": "d6a745a584f5f0b57eddf076426e31a457cf068a78b2caa9d0cc3778f354d697",
    },
}
RANDOMIZATION_CONTRACT = {
    "family_alpha": ALPHA,
    "endpoint_alpha": ENDPOINT_ALPHA,
    "multiplicity": "BONFERRONI_TWO_REGISTERED_ENDPOINTS",
    "endpoints": [
        {"endpoint": "CONTENT_TV", "statistic": "T_content=1/2*sum_c|N_E,c-N_D,c|", "primary_replicate": "R001"},
        {"endpoint": "FIXED_BRANCH_MARGIN", "statistic": "T_margin=abs(sum_E M_i-sum_D M_i)", "primary_replicate": "R001", "completion_row_zero_based": FIXED_BRANCH_ROW, "prefix_length": FIXED_BRANCH_PREFIX_LENGTH, "prefix_sha256": FIXED_BRANCH_PREFIX_SHA256, "candidates": FIXED_BRANCH_CANDIDATES},
    ],
    "schedule_domain_count": SCHEDULE_COUNT,
    "schedule_selection_method": SCHEDULE_SELECTION_METHOD,
    "raw_draw_acceptance": "RAW_256_BIT_CSPRNG_INTEGER_LT_FLOOR_2POW256_DIV_400_TIMES_400_THEN_MOD_400",
    "upper_tail": "COUNT_T_GE_OBSERVED_OVER_ALL_400_SCHEDULES",
    "minimum_attainable_inclusive_tail": "2/400=0.005_DUE_TO_GLOBAL_ARM_COMPLEMENT_SYMMETRY",
    "unit": "FRESH_LAUNCH_PRIMARY_R001",
    "trace_unavailable": "INCONCLUSIVE_REQUIRED_TRACE_ENDPOINT_UNAVAILABLE_NO_POST_HOC_FALLBACK",
    "hash_binding_boundary": "SHA256_ARTIFACT_BINDING_PROVES_RECORDED_RAW_DRAW_AND_SELECTION_CONSISTENCY_NOT_ENTROPY_OR_MANIPULATION",
}
PINNED = {
    "endpoint": "http://127.0.0.1:18080/v1/chat/completions", "model": "qwen3.6-35b-a3b",
    "repository": "Qwen/Qwen3.6-35B-A3B-FP8", "revision": "95a723d08a9490559dae23d0cff1d9466213d989",
    "snapshot": "2ece6b46248e818cbf93aa30299300f7dd4c60d9351960ec790cc8b420376e47",
    "vllm": "0.25.1", "image": "vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089",
    "image_id": "sha256:30a38a1d74a17365eca400e83ffd885b250e0c8c0d3c5b508afa8c412d2ddf95",
    "gpu_uuid": "GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5", "gpu_name": "NVIDIA GB10",
    "driver": "580.126.09", "cc": "12.1",
}
SERVER_PREFIX = (
    "--model", "/model-repository/snapshots/95a723d08a9490559dae23d0cff1d9466213d989",
    "--served-model-name", "qwen3.6-35b-a3b", "--host", "0.0.0.0", "--port", "8000",
    "--max-num-seqs", "1", "--no-enable-prefix-caching", "--max-model-len", "32768",
    "--gpu-memory-utilization", "0.500", "--generation-config", "vllm", "--seed", "0",
    "--enforce-eager", "--language-model-only", "--max-logprobs", "20", "--logprobs-mode",
    "processed_logprobs",
)
REQUIRED_ENV = (
    "HF_HOME=/cache/huggingface", "HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub",
    "VLLM_CACHE_ROOT=/cache/compile/vllm", "TORCHINDUCTOR_CACHE_DIR=/cache/compile/torchinductor",
    "TRITON_CACHE_DIR=/cache/compile/triton", "HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1",
    "VLLM_ENABLE_V1_MULTIPROCESSING=0", "PYTHONHASHSEED=0", "CUBLAS_WORKSPACE_CONFIG=:4096:8",
)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_GIT = re.compile(r"^[0-9a-f]{40}$")
_PAIR = re.compile(r"^P(?:0[1-9]|1[0-2])$")
_ATTEMPT = re.compile(r"^MI2-P(?:0[1-9]|1[0-2])-(?:E|D)-R00[12]$")


class Mi2Refusal(ValueError):
    """The proposed launch-crossed study drifted outside its frozen boundary."""


class Mi2RequiredTraceUnavailable(Mi2Refusal):
    """The preregistered FIXED_BRANCH_MARGIN endpoint cannot be evaluated."""


def _canonical(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw:
        raise Mi2Refusal(f"{label} must be nonempty bytes")
    try:
        value = parse_canonical(raw)
    except (CanonicalJsonError, TypeError) as error:
        raise Mi2Refusal(f"{label} must be canonical JSON") from error
    if type(value) is not dict:
        raise Mi2Refusal(f"{label} must be an object")
    return value


def _object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise Mi2Refusal(f"{label} key set drifted")
    return value


def _digest(value: Any, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None or value == "0" * 64:
        raise Mi2Refusal(f"{label} must be a non-placeholder SHA-256")
    return value


def pair_id(index: int) -> str:
    if type(index) is not int or not 1 <= index <= PAIR_COUNT:
        raise Mi2Refusal("MI-2 pair index drifted")
    return f"P{index:02d}"


def all_balanced_schedules() -> tuple[tuple[str, ...], ...]:
    """Return all 400 allowed schedules in explicit lexicographic ED/DE order."""
    half: list[tuple[str, ...]] = []
    for choices in itertools.combinations(range(6), 3):
        selected = set(choices)
        half.append(tuple("ED" if index in selected else "DE" for index in range(6)))
    # ``ED`` precedes ``DE`` here by the study's explicit alphabet, not Python
    # string ordering; this is the schedule selector's public lexicographic rule.
    half.sort(key=lambda row: tuple(0 if item == "ED" else 1 for item in row))
    schedules = tuple(left + right for left in half for right in half)
    if len(schedules) != SCHEDULE_COUNT or len(set(schedules)) != SCHEDULE_COUNT:
        raise AssertionError("MI-2 schedule enumeration defect")
    return schedules


ALL_SCHEDULES = all_balanced_schedules()


def validate_schedule(schedule: Sequence[str]) -> tuple[str, ...]:
    if type(schedule) not in {list, tuple} or len(schedule) != PAIR_COUNT:
        raise Mi2Refusal("MI-2 requires twelve adjacent matched pairs")
    result = tuple(schedule)
    if any(type(item) is not str or item not in {"ED", "DE"} for item in result):
        raise Mi2Refusal("MI-2 pair orientation drifted")
    if result.count("ED") != 6 or result.count("DE") != 6:
        raise Mi2Refusal("MI-2 requires exactly six ED and six DE pairs")
    if result[:6].count("ED") != 3 or result[6:].count("ED") != 3:
        raise Mi2Refusal("MI-2 requires three ED pairs in each temporal half")
    if result not in ALL_SCHEDULES:
        raise Mi2Refusal("MI-2 schedule is outside the closed 400-schedule domain")
    return result


def make_seed_material(seed: bytes) -> bytes:
    if type(seed) is not bytes or len(seed) != 32:
        raise Mi2Refusal("MI-2 CSPRNG raw draw must be exactly 32 bytes")
    return canonical_bytes({
        "schema_version": SEED_SCHEMA,
        "raw_draw_hex": seed.hex(),
        "selection_domain": SCHEDULE_DOMAIN,
        "terminal": "RAW_CSPRNG_256_BIT_DRAW_REVEALED_BEFORE_SCHEDULE_SELECTION",
    })


def parse_seed_material(raw: bytes) -> bytes:
    value = _object(_canonical(raw, "MI-2 seed material"),
                    {"schema_version", "raw_draw_hex", "selection_domain", "terminal"},
                    "MI-2 seed material")
    if (value["schema_version"] != SEED_SCHEMA or value["selection_domain"] != SCHEDULE_DOMAIN
            or value["terminal"] != "RAW_CSPRNG_256_BIT_DRAW_REVEALED_BEFORE_SCHEDULE_SELECTION"
            or type(value["raw_draw_hex"]) is not str):
        raise Mi2Refusal("MI-2 seed material schema drifted")
    try:
        seed = bytes.fromhex(value["raw_draw_hex"])
    except ValueError as error:
        raise Mi2Refusal("MI-2 seed material hex drifted") from error
    if len(seed) != 32 or value["raw_draw_hex"] != seed.hex():
        raise Mi2Refusal("MI-2 seed material length/canonical hex drifted")
    return seed


def select_schedule(seed_material_raw: bytes) -> tuple[int, tuple[str, ...]]:
    raw_draw = parse_seed_material(seed_material_raw)
    value = int.from_bytes(raw_draw, "big")
    if value >= SCHEDULE_SELECTION_LIMIT:
        raise Mi2Refusal("MI-2 recorded raw CSPRNG draw is in the rejected tail")
    index = value % SCHEDULE_COUNT
    return index, ALL_SCHEDULES[index]


def block_order(schedule: Sequence[str]) -> list[dict[str, Any]]:
    orientations = validate_schedule(schedule)
    rows: list[dict[str, Any]] = []
    for index, orientation in enumerate(orientations, 1):
        for position, short_arm in enumerate(orientation, 1):
            absolute_index = len(rows) + 1
            arm = "ASYNC_ENABLED" if short_arm == "E" else "ASYNC_DISABLED"
            rows.append({
                "pair_id": pair_id(index),
                "pair_orientation": orientation,
                "launch_position": position,
                "absolute_launch_index": absolute_index,
                "absolute_launch_parity": "ODD" if absolute_index % 2 else "EVEN",
                "prior_arm": None if not rows else rows[-1]["arm"],
                "arm": arm,
                "arm_code": short_arm,
            })
    if len(rows) != FRESH_LAUNCHES:
        raise AssertionError("MI-2 launch construction defect")
    return rows


def attempt_ids(schedule: Sequence[str]) -> list[str]:
    return [
        f"MI2-{row['pair_id']}-{row['arm_code']}-R{replicate:03d}"
        for row in block_order(schedule)
        for replicate in range(1, REPLICATES_PER_LAUNCH + 1)
    ]


def _source(value: Any, label: str) -> dict[str, Any]:
    item = _object(value, {"commit", "tree", "ci_receipt_sha256", "ci_terminal"}, label)
    if (type(item["commit"]) is not str or _GIT.fullmatch(item["commit"]) is None
            or type(item["tree"]) is not str or _GIT.fullmatch(item["tree"]) is None
            or item["commit"] == "0" * 40 or item["tree"] == "0" * 40
            or item["ci_terminal"] != "FIRST_ATTEMPT_SUCCESSFUL_CI_BUILD"):
        raise Mi2Refusal(f"{label} source identity drifted")
    _digest(item["ci_receipt_sha256"], f"{label} CI receipt")
    return item


def validate_arm_identities(identities: Mapping[str, Mapping[str, bytes]]) -> None:
    if set(identities) != set(ARMS):
        raise Mi2Refusal("MI-2 requires exactly the two async arms")
    common: dict[str, bytes] | None = None
    flags: dict[str, bool] = {}
    runtimes: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        row = identities[arm]
        if set(row) != set(IDENTITY_NAMES):
            raise Mi2Refusal("MI-2 identity key set drifted")
        parsed = {name: _canonical(raw, f"MI-2 {name}") for name, raw in row.items()}
        runtime, endpoint = parsed["runtime_identity_sha256"], parsed["endpoint_sha256"]
        model, snapshot, tls = (parsed["model_identity_sha256"], parsed["model_snapshot_manifest_sha256"],
                                 parsed["tls_identity_sha256"])
        if (sha256(row["declared_isolation_contract_sha256"]).hexdigest() != "ac594ec24eb2a096b0053096c8650aeca33aa290d7146bd0793abddcd64e9ba1"
                or {"endpoint": endpoint.get("endpoint"), "model": model.get("model"), "repository": model.get("repository"), "revision": model.get("revision")} != {key: PINNED[key] for key in ("endpoint", "model", "repository", "revision")}
                or sha256(row["model_snapshot_manifest_sha256"]).hexdigest() != PINNED["snapshot"]
                or set(endpoint) != {"schema_version", "endpoint", "method", "transport"}
                or endpoint.get("schema_version") != "hswm-dgx-q1-endpoint-identity/v1" or endpoint.get("method") != "POST"
                or endpoint.get("transport") != "LOOPBACK_HTTP_NO_TLS"
                or set(model) != {"schema_version", "model", "repository", "revision", "snapshot_manifest_sha256"}
                or model.get("schema_version") != "hswm-dgx-q1-model-identity/v1"
                or model.get("snapshot_manifest_sha256") != sha256(row["model_snapshot_manifest_sha256"]).hexdigest()
                or set(snapshot) != {"schema_version", "repository", "revision", "file_count", "total_byte_length", "files", "files_sha256"}
                or snapshot.get("schema_version") != "hswm-dgx-q1-model-snapshot-manifest/v1"
                or snapshot.get("repository") != model["repository"] or snapshot.get("revision") != model["revision"]
                or type(snapshot.get("file_count")) is not int or snapshot["file_count"] <= 0
                or type(snapshot.get("files")) is not list or len(snapshot["files"]) != snapshot["file_count"]
                or tls != {"schema_version": "hswm-dgx-q1-tls-identity/v1", "endpoint_scheme": "http", "tls": "NOT_APPLICABLE_LOOPBACK_ONLY"}):
            raise Mi2Refusal("MI-2 endpoint/model/snapshot/TLS identity drifted")
        runtime_keys = {
            "schema_version", "container_image", "image_id", "vllm_version", "gpu_uuid", "gpu_name",
            "gpu_driver_version", "gpu_compute_capability", "endpoint", "served_model", "model_revision",
            "model_snapshot_manifest_sha256", "max_model_len", "max_num_seqs", "gpu_memory_utilization_milli",
            "prefix_cache", "enforce_eager", "batch_invariant", "v1_multiprocessing", "model_loading_offline",
            "generation_config", "engine_seed", "language_model_only", "container_internal_port",
            "container_network_mode", "container_ipc_mode", "host_publish_ip", "async_scheduling",
            "server_arguments", "required_environment", "max_logprobs", "logprobs_mode",
        }
        fixed_runtime = {
            "container_image": PINNED["image"], "image_id": PINNED["image_id"], "vllm_version": PINNED["vllm"],
            "gpu_uuid": PINNED["gpu_uuid"], "gpu_name": PINNED["gpu_name"], "gpu_driver_version": PINNED["driver"],
            "gpu_compute_capability": PINNED["cc"], "endpoint": PINNED["endpoint"], "served_model": PINNED["model"],
            "model_revision": PINNED["revision"], "model_snapshot_manifest_sha256": PINNED["snapshot"],
            "max_model_len": 32768, "max_num_seqs": 1, "gpu_memory_utilization_milli": 500,
        }
        if (set(runtime) != runtime_keys or runtime.get("schema_version") != "hswm-dgx-qcase024-mi-runtime-identity/v4"
                or runtime.get("prefix_cache") is not False or runtime.get("enforce_eager") is not True
                or runtime.get("batch_invariant") is not False or runtime.get("v1_multiprocessing") is not False
                or runtime.get("model_loading_offline") is not True or runtime.get("generation_config") != "vllm"
                or runtime.get("engine_seed") != 0 or runtime.get("language_model_only") is not True
                or runtime.get("container_internal_port") != 8000 or runtime.get("container_network_mode") != "bridge"
                or runtime.get("container_ipc_mode") != "private" or runtime.get("host_publish_ip") != "127.0.0.1"
                or runtime.get("max_logprobs") != 20 or runtime.get("logprobs_mode") != "processed_logprobs"
                or {key: runtime.get(key) for key in fixed_runtime} != fixed_runtime
                or tuple(runtime.get("required_environment", ())) != REQUIRED_ENV
                or type(runtime.get("async_scheduling")) is not bool
                or type(runtime.get("server_arguments")) is not list
                or tuple(runtime["server_arguments"][:-1]) != SERVER_PREFIX
                or runtime["server_arguments"][-1] not in {"--async-scheduling", "--no-async-scheduling"}):
            raise Mi2Refusal("MI-2 pinned runtime identity drifted")
        flags[arm] = runtime["async_scheduling"]
        runtimes[arm] = runtime
        other = {name: row[name] for name in IDENTITY_NAMES if name != "runtime_identity_sha256"}
        if common is None:
            common = other
        elif common != other:
            raise Mi2Refusal("MI-2 arms may differ only in runtime identity")
        for raw in row.values():
            _digest(sha256(raw).hexdigest(), "MI-2 identity bytes")
    if flags != {"ASYNC_ENABLED": True, "ASYNC_DISABLED": False}:
        raise Mi2Refusal("MI-2 async flag pairing drifted")
    def normalized(runtime: dict[str, Any]) -> dict[str, Any]:
        result = dict(runtime)
        result["async_scheduling"] = "ARM_CONTROL"
        result["server_arguments"] = [
            "ASYNC_CONTROL" if value in {"--async-scheduling", "--no-async-scheduling"} else value
            for value in runtime["server_arguments"]
        ]
        return result
    enabled, disabled = runtimes["ASYNC_ENABLED"], runtimes["ASYNC_DISABLED"]
    if (enabled["server_arguments"].count("--async-scheduling") != 1
            or "--no-async-scheduling" in enabled["server_arguments"]
            or disabled["server_arguments"].count("--no-async-scheduling") != 1
            or "--async-scheduling" in disabled["server_arguments"]
            or normalized(enabled) != normalized(disabled)):
        raise Mi2Refusal("MI-2 arm runtimes may differ only in explicit async argv")


def _content_digest(value: Any, label: str) -> str:
    return _digest(value, label)


def content_tv_statistic(primary_content_by_pair: Mapping[str, Sequence[str]], schedule: Sequence[str]) -> int:
    """Compute T_content = 1/2 * sum_c |N_E,c - N_D,c| on R001 values only."""
    orientations = validate_schedule(schedule)
    if set(primary_content_by_pair) != {pair_id(index) for index in range(1, PAIR_COUNT + 1)}:
        raise Mi2Refusal("MI-2 primary content pair domain drifted")
    enabled: Counter[str] = Counter()
    disabled: Counter[str] = Counter()
    for index, orientation in enumerate(orientations, 1):
        values = primary_content_by_pair[pair_id(index)]
        if type(values) not in {list, tuple} or len(values) != 2:
            raise Mi2Refusal("MI-2 primary pair requires two launch content SHA-256 values")
        first, second = (_content_digest(value, "MI-2 primary content") for value in values)
        if orientation == "ED":
            enabled[first] += 1; disabled[second] += 1
        else:
            disabled[first] += 1; enabled[second] += 1
    distance = sum(abs(enabled[key] - disabled[key]) for key in set(enabled) | set(disabled))
    if distance % 2:
        raise Mi2Refusal("MI-2 primary arm count distance must be even")
    return distance // 2


# Backwards-compatible short name for the primary endpoint's pure statistic.
statistic = content_tv_statistic


def _finite_decimal(value: Any, label: str) -> Decimal:
    if type(value) is bool or type(value) not in {str, int, Decimal}:
        raise Mi2RequiredTraceUnavailable(f"MI-2 {label} decimal representation drifted")
    try:
        decimal = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise Mi2RequiredTraceUnavailable(f"MI-2 {label} decimal parse drifted") from error
    if not decimal.is_finite():
        raise Mi2RequiredTraceUnavailable(f"MI-2 {label} is nonfinite")
    return decimal


def extract_fixed_branch_margin(trace_raw: bytes) -> Decimal:
    """Extract the registered row-20 candidate margin from one R001 trace.

    The prefix, row, token identities, byte strings, and log-probability
    representations are all required.  This deliberately raises an endpoint
    unavailability exception rather than silently falling back to content TV.
    """
    try:
        trace = _canonical(trace_raw, "MI-2 full processed trace")
        if set(trace) != {"schema_version", "rows"} or trace["schema_version"] != FULL_TRACE_SCHEMA:
            raise ValueError
        rows = trace["rows"]
        if type(rows) is not list or len(rows) <= FIXED_BRANCH_ROW:
            raise ValueError
        prefix = bytearray()
        for row in rows[:FIXED_BRANCH_ROW]:
            if type(row) is not dict or type(row.get("bytes")) is not list:
                raise ValueError
            if any(type(item) is not int or not 0 <= item <= 255 for item in row["bytes"]):
                raise ValueError
            prefix.extend(row["bytes"])
        if len(prefix) != FIXED_BRANCH_PREFIX_LENGTH or sha256(bytes(prefix)).hexdigest() != FIXED_BRANCH_PREFIX_SHA256:
            raise ValueError
        row = rows[FIXED_BRANCH_ROW]
        if type(row) is not dict or set(row) != {"token", "bytes", "logprob", "top_logprobs"}:
            raise ValueError
        candidates = row["top_logprobs"]
        if type(candidates) is not list:
            raise ValueError
        values: dict[str, Decimal] = {}
        identities: set[tuple[str, bytes]] = set()
        for candidate in candidates:
            if type(candidate) is not dict or set(candidate) != {"token", "bytes", "logprob"}:
                raise ValueError
            token, raw_bytes = candidate["token"], candidate["bytes"]
            if (type(token) is not str or type(raw_bytes) is not list
                    or type(candidate["logprob"]) is not str
                    or any(type(item) is not int or not 0 <= item <= 255 for item in raw_bytes)):
                raise ValueError
            identity = (token, bytes(raw_bytes))
            if identity in identities:
                raise ValueError
            identities.add(identity)
            for name, contract in FIXED_BRANCH_CANDIDATES.items():
                expected = contract["token"].encode("utf-8")
                if (token == contract["token"] and identity[1] == expected
                        and sha256(identity[1]).hexdigest() == contract["sha256"]):
                    if name in values:
                        raise ValueError
                    values[name] = _finite_decimal(candidate["logprob"], f"{name} candidate logprob")
        if set(values) != set(FIXED_BRANCH_CANDIDATES):
            raise ValueError
        return values["indicates"] - values["explicitly"]
    except Mi2RequiredTraceUnavailable:
        raise
    except Exception as error:
        raise Mi2RequiredTraceUnavailable("MI-2 fixed branch trace alignment/candidate contract unavailable") from error


def margin_statistic(primary_margin_by_pair: Mapping[str, Sequence[Decimal]], schedule: Sequence[str]) -> Decimal:
    orientations = validate_schedule(schedule)
    if set(primary_margin_by_pair) != {pair_id(index) for index in range(1, PAIR_COUNT + 1)}:
        raise Mi2RequiredTraceUnavailable("MI-2 margin pair domain drifted")
    enabled, disabled = Decimal(0), Decimal(0)
    for index, orientation in enumerate(orientations, 1):
        values = primary_margin_by_pair[pair_id(index)]
        if type(values) not in {list, tuple} or len(values) != 2:
            raise Mi2RequiredTraceUnavailable("MI-2 margin pair requires two R001 values")
        first, second = (_finite_decimal(value, "primary margin") for value in values)
        if orientation == "ED":
            enabled += first; disabled += second
        else:
            disabled += first; enabled += second
    return abs(enabled - disabled)


def exact_upper_tail_randomization(primary_content_by_pair: Mapping[str, Sequence[str]],
                                   observed_schedule: Sequence[str]) -> dict[str, Any]:
    observed = validate_schedule(observed_schedule)
    observed_t = content_tv_statistic(primary_content_by_pair, observed)
    distribution = [content_tv_statistic(primary_content_by_pair, candidate) for candidate in ALL_SCHEDULES]
    numerator = sum(value >= observed_t for value in distribution)
    return {
        "schema_version": "hswm-dgx-qcase024-mi2-launch-crossed-randomization/v1", "endpoint": "CONTENT_TV",
        "statistic": "T_content=1/2*sum_c|N_E,c-N_D,c|",
        "observed_t": observed_t,
        "upper_tail_numerator": numerator,
        "denominator": SCHEDULE_COUNT,
        "p_value": f"{numerator}/{SCHEDULE_COUNT}",
        "alpha": ENDPOINT_ALPHA,
        "reject_at_alpha": numerator * 1000 <= 25 * SCHEDULE_COUNT,
        "schedule_domain_count": SCHEDULE_COUNT,
        "interpretation": "FINITE_EXACT_RANDOMIZATION_ENDPOINT_NOT_MECHANISTIC_ATTRIBUTION",
    }


def exact_margin_upper_tail_randomization(primary_margin_by_pair: Mapping[str, Sequence[Decimal]],
                                          observed_schedule: Sequence[str]) -> dict[str, Any]:
    observed = validate_schedule(observed_schedule)
    observed_t = margin_statistic(primary_margin_by_pair, observed)
    distribution = [margin_statistic(primary_margin_by_pair, candidate) for candidate in ALL_SCHEDULES]
    numerator = sum(value >= observed_t for value in distribution)
    return {
        "schema_version": "hswm-dgx-qcase024-mi2-launch-crossed-randomization/v1", "endpoint": "FIXED_BRANCH_MARGIN",
        "statistic": "T_margin=abs(sum_E M_i-sum_D M_i)", "observed_t": str(observed_t),
        "upper_tail_numerator": numerator, "denominator": SCHEDULE_COUNT,
        "p_value": f"{numerator}/{SCHEDULE_COUNT}", "alpha": ENDPOINT_ALPHA,
        "reject_at_alpha": numerator * 1000 <= 25 * SCHEDULE_COUNT,
        "schedule_domain_count": SCHEDULE_COUNT,
        "interpretation": "FINITE_EXACT_RANDOMIZATION_ENDPOINT_NOT_MECHANISTIC_ATTRIBUTION",
    }


def endpoint_family_randomization(primary_content_by_pair: Mapping[str, Sequence[str]],
                                  primary_margin_by_pair: Mapping[str, Sequence[Decimal]],
                                  observed_schedule: Sequence[str]) -> dict[str, Any]:
    content = exact_upper_tail_randomization(primary_content_by_pair, observed_schedule)
    margin = exact_margin_upper_tail_randomization(primary_margin_by_pair, observed_schedule)
    positive = content["reject_at_alpha"] or margin["reject_at_alpha"]
    return {
        "schema_version": "hswm-dgx-qcase024-mi2-launch-crossed-endpoint-family/v1",
        "family_alpha": ALPHA, "endpoint_alpha": ENDPOINT_ALPHA,
        "multiplicity": "BONFERRONI_TWO_REGISTERED_ENDPOINTS",
        "endpoints": [content, margin],
        "family_label": (
            "FINITE_RANDOMIZED_ARM_ASSOCIATION_DETECTED"
            if positive else "FINITE_RANDOMIZED_NO_ARM_ASSOCIATION_DETECTED"
        ),
        "missing_fixed_branch_margin": "INCONCLUSIVE_REQUIRED_TRACE_ENDPOINT_UNAVAILABLE_NO_POST_HOC_FALLBACK",
    }


def validate_mi2_plan(raw: bytes, *, seed_material_raw: bytes | None = None) -> dict[str, Any]:
    keys = {
        "schema_version", "namespace", "instrument_id", "source", "runner_version", "material",
        "request_sha256", "post_result_selection", "arms", "schedule_selection", "block_order",
        "attempt_ids", "replicates_per_launch", "fresh_launches", "primary_posts", "budget",
        "zero_retry", "no_refill_resume_or_early_stop", "consumption_registry", "randomization",
        "verifier", "evidence_root_genesis_sha256", "allowed_terminals", "nonclaims",
    }
    plan = _object(_canonical(raw, "MI-2 plan"), keys, "MI-2 plan")
    if (plan["schema_version"] != PLAN_SCHEMA or plan["namespace"] != NAMESPACE
            or plan["instrument_id"] != INSTRUMENT_ID or plan["runner_version"] != RUNNER_VERSION
            or plan["replicates_per_launch"] != REPLICATES_PER_LAUNCH
            or plan["fresh_launches"] != FRESH_LAUNCHES or plan["primary_posts"] != PRIMARY_POSTS
            or plan["budget"] != TOTAL_POSTS or plan["zero_retry"] is not True
            or plan["no_refill_resume_or_early_stop"] is not True
            or plan["consumption_registry"] != REGISTRY or plan["allowed_terminals"] != list(TERMINALS)
            or plan["nonclaims"] != list(NONCLAIMS)):
        raise Mi2Refusal("MI-2 plan static boundary drifted")
    _source(plan["source"], "MI-2 source")
    verifier = _object(plan["verifier"], {"source", "build_output_sha256"}, "MI-2 verifier")
    _source(verifier["source"], "MI-2 verifier source")
    _digest(verifier["build_output_sha256"], "MI-2 verifier build")
    material = _object(plan["material"], {"case_id", "instruction_sha256", "model_input_sha256", "response_schema_sha256", "rng_sha256", "max_output_tokens"}, "MI-2 material")
    expected_material = {
        "instruction.txt": material["instruction_sha256"], "model_input.json": material["model_input_sha256"],
        "response_schema.json": material["response_schema_sha256"], "rng.bin": material["rng_sha256"],
    }
    if material["case_id"] != "QCASE-024" or material["max_output_tokens"] != 256 or expected_material != EXPECTED_MATERIAL_SHA256:
        raise Mi2Refusal("MI-2 material is not the frozen QCASE-024 material")
    if _digest(plan["request_sha256"], "MI-2 request") != EXPECTED_REQUEST_SHA256:
        raise Mi2Refusal("MI-2 request is not the frozen instrumented QCASE-024 request")
    selection = _object(plan["post_result_selection"], set(EXPECTED_MI1_SELECTION), "MI-2 selection")
    if selection != EXPECTED_MI1_SELECTION:
        raise Mi2Refusal("MI-2 selection boundary drifted")
    for name in ("mi1_result_ci_receipt_sha256", "mi1_evidence_sha256", "mi1_result_projection_sha256", "mi1_ledger_sha256"):
        _digest(selection[name], "MI-2 " + name)
    for name in ("mi1_result_commit", "mi1_result_tree"):
        if type(selection[name]) is not str or _GIT.fullmatch(selection[name]) is None:
            raise Mi2Refusal("MI-2 result Git provenance drifted")
    arms = _object(plan["arms"], set(ARMS), "MI-2 arms")
    for identities in arms.values():
        _object(identities, set(IDENTITY_NAMES), "MI-2 arm identity digests")
        for digest in identities.values(): _digest(digest, "MI-2 arm identity digest")
    schedule_selection = _object(plan["schedule_selection"], {"method", "seed_material_sha256", "schedule_index", "schedule", "schedule_domain_count"}, "MI-2 schedule selection")
    schedule = validate_schedule(schedule_selection["schedule"])
    if (schedule_selection["method"] != SCHEDULE_SELECTION_METHOD
            or _digest(schedule_selection["seed_material_sha256"], "MI-2 seed material") is None
            or type(schedule_selection["schedule_index"]) is not int or not 0 <= schedule_selection["schedule_index"] < SCHEDULE_COUNT
            or schedule_selection["schedule_domain_count"] != SCHEDULE_COUNT
            or ALL_SCHEDULES[schedule_selection["schedule_index"]] != schedule):
        raise Mi2Refusal("MI-2 schedule selection drifted")
    expected_order = block_order(schedule)
    if plan["block_order"] != expected_order or plan["attempt_ids"] != attempt_ids(schedule):
        raise Mi2Refusal("MI-2 launch/attempt order drifted")
    if len(plan["attempt_ids"]) != TOTAL_POSTS or any(_ATTEMPT.fullmatch(item) is None for item in plan["attempt_ids"]):
        raise Mi2Refusal("MI-2 attempt domain drifted")
    if plan["randomization"] != RANDOMIZATION_CONTRACT:
        raise Mi2Refusal("MI-2 randomization contract drifted")
    _digest(plan["evidence_root_genesis_sha256"], "MI-2 root genesis")
    if seed_material_raw is not None:
        if sha256(seed_material_raw).hexdigest() != schedule_selection["seed_material_sha256"]:
            raise Mi2Refusal("MI-2 seed material plan binding drifted")
        index, selected = select_schedule(seed_material_raw)
        if index != schedule_selection["schedule_index"] or selected != schedule:
            raise Mi2Refusal("MI-2 CSPRNG schedule rederivation drifted")
    return plan


def make_mi2_start_marker(plan_raw: bytes, seed_material_raw: bytes) -> bytes:
    plan = validate_mi2_plan(plan_raw, seed_material_raw=seed_material_raw)
    return canonical_bytes({
        "schema_version": MARKER_SCHEMA, "namespace": NAMESPACE,
        "plan_sha256": sha256(plan_raw).hexdigest(), "request_sha256": plan["request_sha256"],
        "seed_material_sha256": sha256(seed_material_raw).hexdigest(),
        "scheduled_attempts": plan["attempt_ids"],
        "terminal": "ALL_48_SERIALIZED_POSTS_AND_PRIMARY_RANDOMIZATION_BOUND_BEFORE_LIVE_START",
        "nonclaims": list(NONCLAIMS),
    })


def validate_mi2_start_marker(marker_raw: bytes, plan_raw: bytes, seed_material_raw: bytes) -> dict[str, Any]:
    if marker_raw != make_mi2_start_marker(plan_raw, seed_material_raw):
        raise Mi2Refusal("MI-2 start marker drifted")
    return _canonical(marker_raw, "MI-2 start marker")
