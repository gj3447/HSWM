"""Pure, fail-closed control snapshot for a future DNRD-5 Q1 run.

This module performs no I/O and cannot authorize a provider dispatch. A host
adapter may supply the small observation vocabulary below, but even a fully
matched snapshot is only finite host-observed control evidence. In particular,
it is not a host-owned allocation lease, Source A, a Permit, or evidence of
HSWM causal learning.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from hashlib import sha256
import re
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256


SCHEMA = "hswm-dnrd5-dgx-q1-frontier-preflight/v1"
MATCHED_NONAUTHORIZING = "Q1_HOST_CONTROL_SNAPSHOT_MATCHED_NONAUTHORIZING"
REFUSED = "Q1_ISOLATION_REFUSED"
NONCLAIM = (
    "NOT_DISPATCH_AUTHORIZATION_OR_NO_INTERFERENCE_PROOF_OR_SOURCE_A_PERMIT_"
    "OR_HSWM_CAUSAL_LEARNING"
)
FULL_PHYSICAL_GPU = "EXCLUSIVE_FULL_PHYSICAL_GPU"
CONTINUOUS_LEASE = "HOST_OWNED_LAUNCH_TO_TEARDOWN_LEASE"
ZERO_SHA256 = "0" * 64

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?$"
)
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_REPO_DIGEST = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
_MODEL_REVISION = re.compile(r"^[0-9a-f]{40}$")
_DRIVER_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}$")
_LOOPBACK = frozenset({"127.0.0.1", "::1"})

# Readers receive symbolic facts only. The pure evaluator never sees shell
# text, URLs, request bodies, credentials, or provider response content.
ALLOWLISTED_COMMAND_FACTS = frozenset(
    {"host", "gpu", "container", "lease", "inference_processes", "listeners"}
)
ALLOWLISTED_HTTP_FACTS = frozenset({"pre_stats", "post_stats"})


class DgxQ1PreflightRefusal(ValueError):
    """A declaration or observation is malformed or outside the contract."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Q1FrontierExpectation:
    """Exact values frozen outside the observer, never learned from it."""

    host_platform_sha256: str
    target_gpu_name: str
    target_gpu_uuid: str
    target_driver_version: str
    target_mig_mode: str
    image_id: str
    configured_image_reference: str
    vllm_version: str
    served_model: str
    model_revision: str
    model_root: str
    endpoint_host: str
    endpoint_port: int


@dataclass(frozen=True, slots=True)
class DgxQ1FrontierReceipt:
    status: str
    refusal_reasons: tuple[str, ...]
    observed_identity_sha256: str
    expectation_sha256: str
    observations: Mapping[str, Any]
    nonclaim: str = NONCLAIM
    schema_version: str = SCHEMA
    dispatch_authorized: bool = field(default=False, init=False)
    dispatch_budget: int = field(default=0, init=False)
    source_freeze_eligible: bool = field(default=False, init=False)

    def projection(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "refusal_reasons": list(self.refusal_reasons),
            "observed_identity_sha256": self.observed_identity_sha256,
            "expectation_sha256": self.expectation_sha256,
            "observations": dict(self.observations),
            "nonclaim": self.nonclaim,
            "dispatch_authorized": self.dispatch_authorized,
            "dispatch_budget": self.dispatch_budget,
            "source_freeze_eligible": self.source_freeze_eligible,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self.projection())


def _sha(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise DgxQ1PreflightRefusal(f"{label} must be a lowercase SHA-256")
    return value


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value or len(value.encode("utf-8")) > 4096:
        raise DgxQ1PreflightRefusal(f"{label} must be bounded nonempty text")
    return value


def _version(value: object, label: str) -> tuple[int, int, int]:
    if type(value) is not str or (matched := _VERSION.fullmatch(value)) is None:
        raise DgxQ1PreflightRefusal(f"{label} is not a release version")
    return tuple(int(item or 0) for item in matched.groups())


def _expectation(expectation: Q1FrontierExpectation) -> dict[str, Any]:
    if type(expectation) is not Q1FrontierExpectation:
        raise DgxQ1PreflightRefusal("expectation must be exact Q1FrontierExpectation")
    for name in (
        "target_gpu_name",
        "target_gpu_uuid",
        "target_driver_version",
        "target_mig_mode",
        "served_model",
        "model_revision",
        "model_root",
        "endpoint_host",
    ):
        _text(getattr(expectation, name), name)
    _sha(expectation.host_platform_sha256, "host_platform_sha256")
    if _DRIVER_VERSION.fullmatch(expectation.target_driver_version) is None:
        raise DgxQ1PreflightRefusal("declared GPU driver version is invalid")
    if expectation.endpoint_host not in _LOOPBACK:
        raise DgxQ1PreflightRefusal("declared endpoint must be an exact loopback host")
    if (
        type(expectation.endpoint_port) is not int
        or not 1 <= expectation.endpoint_port <= 65535
    ):
        raise DgxQ1PreflightRefusal("declared endpoint port is invalid")
    if _IMAGE_ID.fullmatch(expectation.image_id) is None:
        raise DgxQ1PreflightRefusal("declared image ID must be immutable sha256")
    if _REPO_DIGEST.fullmatch(expectation.configured_image_reference) is None:
        raise DgxQ1PreflightRefusal(
            "configured image reference must be a full repository digest"
        )
    if _MODEL_REVISION.fullmatch(expectation.model_revision) is None:
        raise DgxQ1PreflightRefusal(
            "declared model revision must be an exact lowercase 40-hex revision"
        )
    _version(expectation.vllm_version, "declared vLLM version")
    return {
        "host_platform_sha256": expectation.host_platform_sha256,
        "target_gpu_name": expectation.target_gpu_name,
        "target_gpu_uuid": expectation.target_gpu_uuid,
        "target_driver_version": expectation.target_driver_version,
        "target_mig_mode": expectation.target_mig_mode,
        "image_id": expectation.image_id,
        "configured_image_reference": expectation.configured_image_reference,
        "vllm_version": expectation.vllm_version,
        "served_model": expectation.served_model,
        "model_revision": expectation.model_revision,
        "model_root": expectation.model_root,
        "endpoint_host": expectation.endpoint_host,
        "endpoint_port": expectation.endpoint_port,
    }


def _fact(reader: Callable[[str], Mapping[str, Any]], name: str) -> Mapping[str, Any]:
    if name not in ALLOWLISTED_COMMAND_FACTS:
        raise DgxQ1PreflightRefusal("command fact is not allowlisted")
    value = reader(name)
    if type(value) is not dict:
        raise DgxQ1PreflightRefusal(f"{name} fact must be a mapping")
    return value


def _http_fact(
    reader: Callable[[str], Mapping[str, Any]], name: str
) -> Mapping[str, Any]:
    if name not in ALLOWLISTED_HTTP_FACTS:
        raise DgxQ1PreflightRefusal("HTTP fact is not allowlisted")
    value = reader(name)
    if type(value) is not dict:
        raise DgxQ1PreflightRefusal(f"{name} HTTP fact must be a mapping")
    return value


def _collect(
    command_reader: Callable[[str], Mapping[str, Any]],
    http_reader: Callable[[str], Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    if not callable(command_reader) or not callable(http_reader):
        raise DgxQ1PreflightRefusal("readers must be callable")
    return {
        name: _fact(command_reader, name)
        for name in sorted(ALLOWLISTED_COMMAND_FACTS)
    } | {
        name: _http_fact(http_reader, name)
        for name in sorted(ALLOWLISTED_HTTP_FACTS)
    }


def _exact_mapping(value: object, keys: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise DgxQ1PreflightRefusal(f"{label} key set drifted")
    return value


def _validate_engine(engine: object) -> Mapping[str, Any]:
    keys = {
        "cgroup_sha256",
        "container_id_sha256",
        "container_started_sha256",
        "repo_digest",
        "engine",
        "vllm_version",
        "served_model",
        "model_revision",
        "model_root",
        "endpoint_port",
        "max_num_seqs",
        "prefix_cache",
        "batch_invariance",
    }
    row = _exact_mapping(engine, keys, "engine group")
    if row["engine"] != "vllm":
        raise DgxQ1PreflightRefusal("engine group is not vLLM")
    for key in ("cgroup_sha256", "container_id_sha256", "container_started_sha256"):
        _sha(row[key], f"engine {key}")
    if (
        type(row["repo_digest"]) is not str
        or _REPO_DIGEST.fullmatch(row["repo_digest"]) is None
    ):
        raise DgxQ1PreflightRefusal("engine repository digest is not immutable")
    _version(row["vllm_version"], "observed vLLM version")
    for key in ("served_model", "model_revision", "model_root"):
        _text(row[key], f"engine {key}")
    if (
        type(row["endpoint_port"]) is not int
        or not 1 <= row["endpoint_port"] <= 65535
    ):
        raise DgxQ1PreflightRefusal("engine endpoint port is invalid")
    if type(row["max_num_seqs"]) is not int or row["max_num_seqs"] < 0:
        raise DgxQ1PreflightRefusal("engine max_num_seqs is invalid")
    if row["prefix_cache"] not in {"ENABLED", "DISABLED", "UNDECLARED"}:
        raise DgxQ1PreflightRefusal("engine prefix-cache declaration drifted")
    if row["batch_invariance"] not in {
        "EFFECTIVE_QUALIFIED",
        "ENV_DECLARED",
        "NOT_DECLARED",
    }:
        raise DgxQ1PreflightRefusal("engine batch-invariance declaration drifted")
    return row


def _validate_observation_shape(
    observed: object,
) -> Mapping[str, Mapping[str, Any]]:
    keys = set(ALLOWLISTED_COMMAND_FACTS | ALLOWLISTED_HTTP_FACTS)
    root = _exact_mapping(observed, keys, "observation")
    host = _exact_mapping(
        root["host"],
        {"hostname_sha256", "platform", "platform_sha256"},
        "host",
    )
    gpu = _exact_mapping(
        root["gpu"],
        {
            "name",
            "uuid",
            "uuid_sha256",
            "driver_version",
            "mig_mode",
            "target_cgroup_compute_process_count",
            "foreign_compute_cgroup_sha256s",
            "compute_cgroup_set_stable",
            "compute_process_tree_bound",
        },
        "gpu",
    )
    container = _exact_mapping(
        root["container"],
        {
            "image_id",
            "configured_image_reference",
            "repo_digest",
            "container_id_sha256",
            "container_started_sha256",
            "cgroup_sha256",
            "identity_stable",
        },
        "container",
    )
    lease = _exact_mapping(
        root["lease"],
        {
            "host_owned",
            "active",
            "lease_owner_sha256",
            "lease_id_sha256",
            "target_cgroup_sha256",
            "target_gpu_uuid",
            "gpu_allocation",
            "continuous_boundary",
        },
        "lease",
    )
    engines = _exact_mapping(
        root["inference_processes"],
        {"process_group_count", "process_groups"},
        "inference_processes",
    )
    listeners = _exact_mapping(
        root["listeners"], {"listeners", "stable"}, "listeners"
    )
    pre = _exact_mapping(
        root["pre_stats"],
        {
            "running_requests",
            "prefix_cache_hits",
            "prefix_cache_queries",
            "process_identity_bound",
        },
        "pre_stats",
    )
    post = _exact_mapping(
        root["post_stats"],
        {
            "running_requests",
            "prefix_cache_hits",
            "prefix_cache_queries",
            "process_identity_bound",
        },
        "post_stats",
    )

    _sha(host["hostname_sha256"], "hostname hash")
    platform = _exact_mapping(
        host["platform"],
        {
            "system_vendor",
            "product_name",
            "product_version",
            "os_id",
            "os_version_id",
            "kernel_release",
            "architecture",
            "docker_server_version",
        },
        "host platform",
    )
    for key, value in platform.items():
        _text(value, f"host platform {key}")
    _sha(host["platform_sha256"], "host platform hash")
    if canonical_sha256(platform) != host["platform_sha256"]:
        raise DgxQ1PreflightRefusal("host platform digest drifted")
    _text(gpu["name"], "GPU name")
    _text(gpu["uuid"], "GPU UUID")
    if (
        type(gpu["driver_version"]) is not str
        or _DRIVER_VERSION.fullmatch(gpu["driver_version"]) is None
    ):
        raise DgxQ1PreflightRefusal("GPU driver version is invalid")
    _text(gpu["mig_mode"], "GPU MIG mode")
    _sha(gpu["uuid_sha256"], "GPU UUID hash")
    if sha256(gpu["uuid"].encode("utf-8")).hexdigest() != gpu["uuid_sha256"]:
        raise DgxQ1PreflightRefusal("GPU UUID digest drifted")
    if (
        type(gpu["target_cgroup_compute_process_count"]) is not int
        or gpu["target_cgroup_compute_process_count"] < 0
    ):
        raise DgxQ1PreflightRefusal(
            "target-cgroup compute-process count is invalid"
        )
    if type(gpu["compute_cgroup_set_stable"]) is not bool:
        raise DgxQ1PreflightRefusal("compute-cgroup stability type drifted")
    if type(gpu["compute_process_tree_bound"]) is not bool:
        raise DgxQ1PreflightRefusal("compute process-tree binding type drifted")
    if type(gpu["foreign_compute_cgroup_sha256s"]) is not list:
        raise DgxQ1PreflightRefusal("foreign compute-cgroup list drifted")
    for digest in gpu["foreign_compute_cgroup_sha256s"]:
        _sha(digest, "foreign compute-cgroup hash")
    if gpu["foreign_compute_cgroup_sha256s"] != sorted(
        set(gpu["foreign_compute_cgroup_sha256s"])
    ):
        raise DgxQ1PreflightRefusal("foreign compute-cgroup list is not canonical")

    if (
        type(container["image_id"]) is not str
        or _IMAGE_ID.fullmatch(container["image_id"]) is None
    ):
        raise DgxQ1PreflightRefusal("container image ID is not immutable")
    _text(container["configured_image_reference"], "configured image reference")
    if (
        type(container["repo_digest"]) is not str
        or _REPO_DIGEST.fullmatch(container["repo_digest"]) is None
    ):
        raise DgxQ1PreflightRefusal("container repository digest is not immutable")
    for key in (
        "container_id_sha256",
        "container_started_sha256",
        "cgroup_sha256",
    ):
        _sha(container[key], f"container {key}")
    if type(container["identity_stable"]) is not bool:
        raise DgxQ1PreflightRefusal("container identity stability type drifted")

    if type(lease["host_owned"]) is not bool or type(lease["active"]) is not bool:
        raise DgxQ1PreflightRefusal("lease booleans drifted")
    for key in (
        "lease_owner_sha256",
        "lease_id_sha256",
        "target_cgroup_sha256",
    ):
        _sha(lease[key], key)
    for key in ("target_gpu_uuid", "gpu_allocation", "continuous_boundary"):
        _text(lease[key], key)

    if (
        type(engines["process_group_count"]) is not int
        or engines["process_group_count"] < 0
    ):
        raise DgxQ1PreflightRefusal("inference process-group count is invalid")
    if type(engines["process_groups"]) is not list:
        raise DgxQ1PreflightRefusal("inference process-group list drifted")
    if engines["process_group_count"] != len(engines["process_groups"]):
        raise DgxQ1PreflightRefusal("inference process-group count drifted")
    for engine in engines["process_groups"]:
        _validate_engine(engine)

    if type(listeners["listeners"]) is not list:
        raise DgxQ1PreflightRefusal("listener list drifted")
    if type(listeners["stable"]) is not bool:
        raise DgxQ1PreflightRefusal("listener stability type drifted")
    listener_order: list[tuple[str, int, str]] = []
    for listener in listeners["listeners"]:
        row = _exact_mapping(listener, {"host", "port", "owner"}, "listener")
        _text(row["host"], "listener host")
        _text(row["owner"], "listener owner")
        if type(row["port"]) is not int or not 1 <= row["port"] <= 65535:
            raise DgxQ1PreflightRefusal("listener port is invalid")
        listener_order.append((row["host"], row["port"], row["owner"]))
    if listener_order != sorted(set(listener_order)):
        raise DgxQ1PreflightRefusal("listener list is not canonical")

    for name, stats in (("pre_stats", pre), ("post_stats", post)):
        if type(stats["process_identity_bound"]) is not bool:
            raise DgxQ1PreflightRefusal(
                f"{name} process identity binding type drifted"
            )
        for key in ("running_requests", "prefix_cache_hits", "prefix_cache_queries"):
            value = stats[key]
            if type(value) is not int or value < 0:
                raise DgxQ1PreflightRefusal(
                    f"{name} counters must be nonnegative integers"
                )
    return root


def _reasons(
    observed: Mapping[str, Mapping[str, Any]], expected: Mapping[str, Any]
) -> tuple[str, ...]:
    reasons: list[str] = []
    gpu = observed["gpu"]
    container = observed["container"]
    lease = observed["lease"]
    engines = observed["inference_processes"]
    listeners = observed["listeners"]

    if observed["host"]["platform_sha256"] != expected["host_platform_sha256"]:
        reasons.append("HOST_PLATFORM_IDENTITY_MISMATCH")
    if (
        gpu["name"] != expected["target_gpu_name"]
        or gpu["uuid"] != expected["target_gpu_uuid"]
    ):
        reasons.append("TARGET_GPU_IDENTITY_MISMATCH")
    if gpu["driver_version"] != expected["target_driver_version"]:
        reasons.append("GPU_DRIVER_VERSION_MISMATCH")
    if gpu["mig_mode"] != expected["target_mig_mode"]:
        reasons.append("GPU_MIG_MODE_MISMATCH")
    if gpu["target_cgroup_compute_process_count"] < 1:
        reasons.append("TARGET_CGROUP_GPU_COMPUTE_PROCESS_NOT_OBSERVED")
    if gpu["compute_cgroup_set_stable"] is not True:
        reasons.append("GPU_COMPUTE_CGROUP_SET_CHANGED")
    if gpu["compute_process_tree_bound"] is not True:
        reasons.append("TARGET_GPU_COMPUTE_PROCESS_TREE_UNBOUND")
    if gpu["foreign_compute_cgroup_sha256s"]:
        reasons.append("FOREIGN_GPU_COMPUTE_CGROUP_OBSERVED")

    if container["image_id"] != expected["image_id"]:
        reasons.append("IMAGE_ID_MISMATCH")
    if container["configured_image_reference"] != expected[
        "configured_image_reference"
    ]:
        reasons.append("CONFIGURED_IMAGE_REFERENCE_MISMATCH")
    if _REPO_DIGEST.fullmatch(container["configured_image_reference"]) is None:
        reasons.append("CONFIGURED_IMAGE_REFERENCE_NOT_IMMUTABLE")
    if container["repo_digest"] != expected["configured_image_reference"]:
        reasons.append("REPOSITORY_DIGEST_MISMATCH")
    if container["identity_stable"] is not True:
        reasons.append("TARGET_CONTAINER_IDENTITY_CHANGED")

    if lease["host_owned"] is not True or lease["active"] is not True:
        reasons.append("HOST_OWNED_LEASE_NOT_ACTIVE")
    if lease["target_gpu_uuid"] != expected["target_gpu_uuid"]:
        reasons.append("LEASE_TARGET_GPU_MISMATCH")
    if (
        lease["gpu_allocation"] != FULL_PHYSICAL_GPU
        or lease["continuous_boundary"] != CONTINUOUS_LEASE
    ):
        reasons.append("LEASE_CONTINUOUS_EXCLUSIVE_BOUNDARY_MISMATCH")
    if lease["target_cgroup_sha256"] != container["cgroup_sha256"]:
        reasons.append("LEASE_TARGET_CGROUP_MISMATCH")

    if engines["process_group_count"] != 1:
        reasons.append("INFERENCE_PROCESS_GROUP_COUNT_NOT_ONE")
    target_groups = [
        row
        for row in engines["process_groups"]
        if row["container_id_sha256"] == container["container_id_sha256"]
    ]
    if len(target_groups) != 1:
        reasons.append("TARGET_INFERENCE_PROCESS_GROUP_NOT_UNIQUE")
    else:
        engine = target_groups[0]
        if (
            engine["cgroup_sha256"] != container["cgroup_sha256"]
            or engine["container_started_sha256"]
            != container["container_started_sha256"]
            or engine["repo_digest"] != container["repo_digest"]
        ):
            reasons.append("TARGET_CONTAINER_PROCESS_IDENTITY_MISMATCH")
        if _version(engine["vllm_version"], "observed vLLM version") < (0, 19, 0):
            reasons.append("VLLM_VERSION_BELOW_0_19")
        if engine["vllm_version"] != expected["vllm_version"]:
            reasons.append("VLLM_DECLARED_VERSION_MISMATCH")
        for key, refusal in (
            ("served_model", "SERVED_MODEL_MISMATCH"),
            ("model_revision", "MODEL_REVISION_MISMATCH"),
            ("model_root", "MODEL_ROOT_MISMATCH"),
            ("endpoint_port", "ENDPOINT_PORT_MISMATCH"),
        ):
            if engine[key] != expected[key]:
                reasons.append(refusal)
        if engine["max_num_seqs"] != 1:
            reasons.append("MAX_NUM_SEQS_NOT_ONE")
        if engine["prefix_cache"] != "DISABLED":
            reasons.append("PREFIX_CACHE_NOT_EXPLICITLY_DISABLED")
        if engine["batch_invariance"] != "EFFECTIVE_QUALIFIED":
            reasons.append("BATCH_INVARIANCE_NOT_EFFECTIVELY_QUALIFIED")

    expected_listener = [
        {
            "host": expected["endpoint_host"],
            "port": expected["endpoint_port"],
            "owner": "target_vllm_process_group",
        }
    ]
    if listeners["listeners"] != expected_listener:
        reasons.append("LISTENER_NOT_EXACT_LOOPBACK_TARGET")
    if listeners["stable"] is not True:
        reasons.append("TARGET_LISTENER_SET_CHANGED")

    pre, post = observed["pre_stats"], observed["post_stats"]
    if (
        pre["process_identity_bound"] is not True
        or post["process_identity_bound"] is not True
    ):
        reasons.append("METRICS_PROCESS_IDENTITY_UNBOUND")
    if pre["running_requests"] != 0 or post["running_requests"] != 0:
        reasons.append("RUNNING_REQUESTS_NONZERO")
    if (
        pre["prefix_cache_hits"] != 0
        or pre["prefix_cache_queries"] != 0
        or post["prefix_cache_hits"] != 0
        or post["prefix_cache_queries"] != 0
    ):
        reasons.append("PREFIX_CACHE_COUNTER_NONZERO")
    if (
        pre["prefix_cache_hits"] != post["prefix_cache_hits"]
        or pre["prefix_cache_queries"] != post["prefix_cache_queries"]
    ):
        reasons.append("PREFIX_CACHE_COUNTER_DELTA")
    return tuple(reasons)


def observe_dgx_q1_frontier_preflight(
    expectation: Q1FrontierExpectation,
    *,
    command_reader: Callable[[str], Mapping[str, Any]],
    http_reader: Callable[[str], Mapping[str, Any]],
) -> DgxQ1FrontierReceipt:
    """Return a finite control receipt that is never dispatch authority."""
    expected = _expectation(expectation)
    try:
        observed = _collect(command_reader, http_reader)
        checked = _validate_observation_shape(observed)
        reasons = _reasons(checked, expected)
    except Exception:
        # External exception text can contain command output or credentials and
        # is intentionally excluded from the durable receipt.
        observed = {"observation": "UNAVAILABLE_OR_MALFORMED"}
        reasons = ("OBSERVATION_UNAVAILABLE_OR_MALFORMED",)
    status = MATCHED_NONAUTHORIZING if not reasons else REFUSED
    return DgxQ1FrontierReceipt(
        status=status,
        refusal_reasons=reasons,
        observed_identity_sha256=canonical_sha256(observed),
        expectation_sha256=canonical_sha256(expected),
        observations=observed,
    )


__all__ = [
    "ALLOWLISTED_COMMAND_FACTS",
    "ALLOWLISTED_HTTP_FACTS",
    "CONTINUOUS_LEASE",
    "DgxQ1FrontierReceipt",
    "DgxQ1PreflightRefusal",
    "FULL_PHYSICAL_GPU",
    "MATCHED_NONAUTHORIZING",
    "NONCLAIM",
    "Q1FrontierExpectation",
    "REFUSED",
    "SCHEMA",
    "ZERO_SHA256",
    "observe_dgx_q1_frontier_preflight",
]
