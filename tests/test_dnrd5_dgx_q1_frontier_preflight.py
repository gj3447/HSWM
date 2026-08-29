"""Pure, no-I/O checks for the finite DGX Q1 control snapshot."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import pytest

from _research.dnrd5.canonical_json import canonical_sha256, parse_canonical
from _research.dnrd5.dgx_q1_frontier_preflight import (
    CONTINUOUS_LEASE,
    DgxQ1PreflightRefusal,
    FULL_PHYSICAL_GPU,
    MATCHED_NONAUTHORIZING,
    NONCLAIM,
    Q1FrontierExpectation,
    REFUSED,
    observe_dgx_q1_frontier_preflight,
)


GPU_NAME = "NVIDIA GB10"
GPU_UUID = "GPU-0123456789abcdef"
IMAGE_ID = "sha256:" + "a" * 64
IMAGE_REFERENCE = "registry.example/hswm/q1@sha256:" + "b" * 64
CGROUP_SHA256 = sha256(b"0::/q1.scope").hexdigest()
PLATFORM = {
    "system_vendor": "MSI",
    "product_name": "MS-C931",
    "product_version": "test-version",
    "os_id": "ubuntu",
    "os_version_id": "24.04",
    "kernel_release": "6.17.0-test",
    "architecture": "aarch64",
    "docker_server_version": "27.5.1",
}


def _expectation() -> Q1FrontierExpectation:
    return Q1FrontierExpectation(
        host_platform_sha256=canonical_sha256(PLATFORM),
        target_gpu_name=GPU_NAME,
        target_gpu_uuid=GPU_UUID,
        target_driver_version="580.126.09",
        target_mig_mode="[N/A]",
        image_id=IMAGE_ID,
        configured_image_reference=IMAGE_REFERENCE,
        vllm_version="0.19.1",
        served_model="qwen-test",
        model_revision="1" * 40,
        model_root="/models/qwen-test",
        endpoint_host="127.0.0.1",
        endpoint_port=8000,
    )


def _engine() -> dict:
    return {
        "cgroup_sha256": CGROUP_SHA256,
        "container_id_sha256": sha256(b"container").hexdigest(),
        "container_started_sha256": sha256(b"start").hexdigest(),
        "repo_digest": IMAGE_REFERENCE,
        "engine": "vllm",
        "vllm_version": "0.19.1",
        "served_model": "qwen-test",
        "model_revision": "1" * 40,
        "model_root": "/models/qwen-test",
        "endpoint_port": 8000,
        "max_num_seqs": 1,
        "prefix_cache": "DISABLED",
        "batch_invariance": "EFFECTIVE_QUALIFIED",
    }


def _facts() -> dict[str, dict]:
    engine = _engine()
    return {
        "host": {
            "hostname_sha256": sha256(b"dgx-test").hexdigest(),
            "platform": PLATFORM,
            "platform_sha256": canonical_sha256(PLATFORM),
        },
        "gpu": {
            "name": GPU_NAME,
            "uuid": GPU_UUID,
            "uuid_sha256": sha256(GPU_UUID.encode()).hexdigest(),
            "driver_version": "580.126.09",
            "mig_mode": "[N/A]",
            "target_cgroup_compute_process_count": 1,
            "foreign_compute_cgroup_sha256s": [],
            "compute_cgroup_set_stable": True,
            "compute_process_tree_bound": True,
        },
        "container": {
            "image_id": IMAGE_ID,
            "configured_image_reference": IMAGE_REFERENCE,
            "repo_digest": IMAGE_REFERENCE,
            "container_id_sha256": engine["container_id_sha256"],
            "container_started_sha256": engine["container_started_sha256"],
            "cgroup_sha256": CGROUP_SHA256,
            "identity_stable": True,
        },
        "lease": {
            "host_owned": True,
            "active": True,
            "lease_owner_sha256": sha256(b"host-scheduler").hexdigest(),
            "lease_id_sha256": sha256(b"lease-1").hexdigest(),
            "target_cgroup_sha256": CGROUP_SHA256,
            "target_gpu_uuid": GPU_UUID,
            "gpu_allocation": FULL_PHYSICAL_GPU,
            "continuous_boundary": CONTINUOUS_LEASE,
        },
        "inference_processes": {
            "process_group_count": 1,
            "process_groups": [engine],
        },
        "listeners": {
            "listeners": [
                {
                    "host": "127.0.0.1",
                    "port": 8000,
                    "owner": "target_vllm_process_group",
                }
            ],
            "stable": True,
        },
        "pre_stats": {
            "running_requests": 0,
            "prefix_cache_hits": 0,
            "prefix_cache_queries": 0,
            "process_identity_bound": True,
        },
        "post_stats": {
            "running_requests": 0,
            "prefix_cache_hits": 0,
            "prefix_cache_queries": 0,
            "process_identity_bound": True,
        },
    }


def _observe(facts: dict[str, dict]):
    return observe_dgx_q1_frontier_preflight(
        _expectation(),
        command_reader=lambda name: facts[name],
        http_reader=lambda name: facts[name],
    )


def _add_foreign_engine(facts: dict[str, dict]) -> None:
    row = deepcopy(_engine())
    row["container_id_sha256"] = sha256(b"foreign-container").hexdigest()
    row["cgroup_sha256"] = sha256(b"0::/foreign.scope").hexdigest()
    facts["inference_processes"]["process_groups"].append(row)
    facts["inference_processes"]["process_group_count"] = 2


def _change_platform(facts: dict[str, dict]) -> None:
    platform = {**facts["host"]["platform"], "product_name": "other"}
    facts["host"]["platform"] = platform
    facts["host"]["platform_sha256"] = canonical_sha256(platform)


def test_exact_snapshot_is_matched_but_never_authorizing_and_is_canonical() -> None:
    receipt = _observe(_facts())
    assert receipt.status == MATCHED_NONAUTHORIZING
    assert receipt.refusal_reasons == ()
    assert receipt.nonclaim == NONCLAIM
    assert receipt.dispatch_authorized is False
    assert receipt.dispatch_budget == 0
    assert receipt.source_freeze_eligible is False
    assert parse_canonical(receipt.canonical_bytes()) == receipt.projection()


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (
            _change_platform,
            "HOST_PLATFORM_IDENTITY_MISMATCH",
        ),
        (
            lambda f: f["gpu"].__setitem__("name", "NVIDIA OTHER"),
            "TARGET_GPU_IDENTITY_MISMATCH",
        ),
        (
            lambda f: f["gpu"].__setitem__("driver_version", "580.127.01"),
            "GPU_DRIVER_VERSION_MISMATCH",
        ),
        (
            lambda f: f["gpu"].__setitem__("mig_mode", "Enabled"),
            "GPU_MIG_MODE_MISMATCH",
        ),
        (
            lambda f: f["gpu"].__setitem__(
                "target_cgroup_compute_process_count", 0
            ),
            "TARGET_CGROUP_GPU_COMPUTE_PROCESS_NOT_OBSERVED",
        ),
        (
            lambda f: f["gpu"].__setitem__("compute_cgroup_set_stable", False),
            "GPU_COMPUTE_CGROUP_SET_CHANGED",
        ),
        (
            lambda f: f["gpu"].__setitem__("compute_process_tree_bound", False),
            "TARGET_GPU_COMPUTE_PROCESS_TREE_UNBOUND",
        ),
        (
            lambda f: f["gpu"].__setitem__(
                "foreign_compute_cgroup_sha256s", [sha256(b"other").hexdigest()]
            ),
            "FOREIGN_GPU_COMPUTE_CGROUP_OBSERVED",
        ),
        (
            lambda f: f["container"].__setitem__(
                "image_id", "sha256:" + "c" * 64
            ),
            "IMAGE_ID_MISMATCH",
        ),
        (
            lambda f: f["container"].__setitem__(
                "configured_image_reference", "repo/model:latest"
            ),
            "CONFIGURED_IMAGE_REFERENCE_NOT_IMMUTABLE",
        ),
        (
            lambda f: f["container"].__setitem__(
                "repo_digest", "registry.example/other@sha256:" + "d" * 64
            ),
            "REPOSITORY_DIGEST_MISMATCH",
        ),
        (
            lambda f: f["container"].__setitem__("identity_stable", False),
            "TARGET_CONTAINER_IDENTITY_CHANGED",
        ),
        (
            lambda f: f["lease"].__setitem__("active", False),
            "HOST_OWNED_LEASE_NOT_ACTIVE",
        ),
        (
            lambda f: f["lease"].__setitem__("host_owned", False),
            "HOST_OWNED_LEASE_NOT_ACTIVE",
        ),
        (
            lambda f: f["lease"].__setitem__("target_gpu_uuid", "other"),
            "LEASE_TARGET_GPU_MISMATCH",
        ),
        (
            lambda f: f["lease"].__setitem__("continuous_boundary", "SNAPSHOT"),
            "LEASE_CONTINUOUS_EXCLUSIVE_BOUNDARY_MISMATCH",
        ),
        (
            lambda f: f["lease"].__setitem__(
                "target_cgroup_sha256", sha256(b"other").hexdigest()
            ),
            "LEASE_TARGET_CGROUP_MISMATCH",
        ),
        (_add_foreign_engine, "INFERENCE_PROCESS_GROUP_COUNT_NOT_ONE"),
        (
            lambda f: f["inference_processes"]["process_groups"][0].__setitem__(
                "cgroup_sha256", sha256(b"other").hexdigest()
            ),
            "TARGET_CONTAINER_PROCESS_IDENTITY_MISMATCH",
        ),
        (
            lambda f: f["inference_processes"]["process_groups"][0].__setitem__(
                "vllm_version", "0.18.9"
            ),
            "VLLM_VERSION_BELOW_0_19",
        ),
        (
            lambda f: f["inference_processes"]["process_groups"][0].__setitem__(
                "served_model", "other"
            ),
            "SERVED_MODEL_MISMATCH",
        ),
        (
            lambda f: f["inference_processes"]["process_groups"][0].__setitem__(
                "model_revision", "other"
            ),
            "MODEL_REVISION_MISMATCH",
        ),
        (
            lambda f: f["inference_processes"]["process_groups"][0].__setitem__(
                "endpoint_port", 8001
            ),
            "ENDPOINT_PORT_MISMATCH",
        ),
        (
            lambda f: f["inference_processes"]["process_groups"][0].__setitem__(
                "max_num_seqs", 2
            ),
            "MAX_NUM_SEQS_NOT_ONE",
        ),
        (
            lambda f: f["inference_processes"]["process_groups"][0].__setitem__(
                "prefix_cache", "ENABLED"
            ),
            "PREFIX_CACHE_NOT_EXPLICITLY_DISABLED",
        ),
        (
            lambda f: f["inference_processes"]["process_groups"][0].__setitem__(
                "batch_invariance", "ENV_DECLARED"
            ),
            "BATCH_INVARIANCE_NOT_EFFECTIVELY_QUALIFIED",
        ),
        (
            lambda f: f["listeners"].__setitem__(
                "listeners",
                [
                    {
                        "host": "0.0.0.0",
                        "port": 8000,
                        "owner": "UNBOUND_PUBLISHED_PORT",
                    }
                ],
            ),
            "LISTENER_NOT_EXACT_LOOPBACK_TARGET",
        ),
        (
            lambda f: f["listeners"].__setitem__("stable", False),
            "TARGET_LISTENER_SET_CHANGED",
        ),
        (
            lambda f: f["pre_stats"].__setitem__(
                "process_identity_bound", False
            ),
            "METRICS_PROCESS_IDENTITY_UNBOUND",
        ),
        (
            lambda f: f["pre_stats"].__setitem__("running_requests", 1),
            "RUNNING_REQUESTS_NONZERO",
        ),
        (
            lambda f: f["post_stats"].__setitem__("prefix_cache_hits", 1),
            "PREFIX_CACHE_COUNTER_NONZERO",
        ),
        (
            lambda f: f["post_stats"].__setitem__("prefix_cache_queries", 1),
            "PREFIX_CACHE_COUNTER_DELTA",
        ),
    ],
)
def test_each_control_violation_refuses(mutate, reason: str) -> None:
    facts = _facts()
    mutate(facts)
    receipt = _observe(facts)
    assert receipt.status == REFUSED
    assert reason in receipt.refusal_reasons


def test_malformed_observation_is_sanitized_and_refused() -> None:
    receipt = observe_dgx_q1_frontier_preflight(
        _expectation(),
        command_reader=lambda _: (_ for _ in ()).throw(OSError("secret-token")),
        http_reader=lambda _: {},
    )
    assert receipt.status == REFUSED
    assert receipt.refusal_reasons == ("OBSERVATION_UNAVAILABLE_OR_MALFORMED",)
    assert b"secret-token" not in receipt.canonical_bytes()


def test_expectation_requires_full_image_digest_and_loopback() -> None:
    invalid = replace(
        _expectation(),
        configured_image_reference="registry.example/q1@sha256:abc",
    )
    with pytest.raises(DgxQ1PreflightRefusal):
        observe_dgx_q1_frontier_preflight(
            invalid,
            command_reader=lambda name: _facts()[name],
            http_reader=lambda name: _facts()[name],
        )
