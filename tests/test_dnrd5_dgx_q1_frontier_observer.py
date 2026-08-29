"""Injected-reader tests for the read-only DGX observation adapter."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from _research.dnrd5 import dgx_q1_frontier_observer as observer_module
from _research.dnrd5.canonical_json import canonical_sha256
from _research.dnrd5.dgx_q1_frontier_observer import observe_frontier
from _research.dnrd5.dgx_q1_frontier_preflight import (
    DgxQ1FrontierReceipt,
    Q1FrontierExpectation,
    REFUSED,
)


GPU_NAME = "NVIDIA GB10"
GPU_UUID = "GPU-test"
IMAGE_ID = "sha256:" + "d" * 64
IMAGE_REFERENCE = "vllm/vllm-openai@sha256:" + "e" * 64
TARGET_ID = "a" * 64
RECEIVER_ID = "b" * 64
OTHER_ID = "c" * 64
PLATFORM = {
    "system_vendor": "MSI",
    "product_name": "MS-C931",
    "product_version": "5.36_0ACUM024",
    "os_id": "ubuntu",
    "os_version_id": "24.04",
    "kernel_release": "6.17.0-1008-nvidia",
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
        vllm_version="0.25.1",
        served_model="qwen3.6-35b-a3b",
        model_revision="95a723d08a9490559dae23d0cff1d9466213d989",
        model_root="Qwen/Qwen3.6-35B-A3B-FP8",
        endpoint_host="127.0.0.1",
        endpoint_port=8000,
    )


def _inspect(
    container_id: str,
    configured_image: str,
    pid: int,
    started: str,
    port: int,
    hosts: tuple[str, ...],
) -> bytes:
    bindings = ",".join(
        f'{{"HostIp":"{host}","HostPort":"{port}"}}' for host in hosts
    )
    return (
        f"{container_id}|{IMAGE_ID}|{configured_image}|{pid}|{started}|"
        f'{{"8000/tcp":[{bindings}]}}\n'
    ).encode()


def _current_command_log() -> tuple[
    Callable[[str, str | None], bytes], list[tuple[str, str | None]]
]:
    calls: list[tuple[str, str | None]] = []

    def command(fact: str, argument: str | None) -> bytes:
        calls.append((fact, argument))
        if fact == "docker_ps":
            return b"target\nreceiver\nother\n"
        if fact == "docker_inspect":
            if argument in {"target", TARGET_ID}:
                return _inspect(
                    TARGET_ID,
                    "vllm/vllm-openai:latest",
                    100,
                    "2026-08-17T06:03:08Z",
                    8000,
                    ("0.0.0.0", "::"),
                )
            if argument in {"receiver", RECEIVER_ID}:
                return _inspect(
                    RECEIVER_ID,
                    "vllm/vllm-openai:latest",
                    101,
                    "2026-08-17T06:08:14Z",
                    8001,
                    ("0.0.0.0", "::"),
                )
            return _inspect(
                OTHER_ID,
                "local/comfy:latest",
                102,
                "2026-08-18T00:00:00Z",
                8188,
                ("0.0.0.0", "::"),
            )
        if fact == "docker_repo_digests":
            return (IMAGE_REFERENCE + "\n").encode()
        if fact == "docker_batch_invariant":
            return b""
        if fact == "cmdline":
            if argument == "100":
                return (
                    b"/usr/bin/python3\0/usr/local/bin/vllm\0serve\0"
                    b"--model=Qwen/Qwen3.6-35B-A3B-FP8\0"
                    b"--served-model-name\0qwen3.6-35b-a3b\0"
                    b"--port=8000\0--max-num-seqs=6\0"
                    b"--enable-prefix-caching\0"
                )
            if argument == "101":
                return (
                    b"/usr/bin/python3\0/usr/local/bin/vllm\0serve\0"
                    b"--model=Qwen/Qwen3-4B\0"
                    b"--served-model-name=qwen3-4b-real\0"
                    b"--port=8000\0--max-num-seqs=4\0"
                )
            return b"python3\0main.py\0"
        if fact == "gpu":
            return f"{GPU_NAME}, {GPU_UUID}, 580.126.09, [N/A]\n".encode()
        if fact == "compute_pids":
            return b"200\n201\n202\n"
        if fact == "cgroup":
            cgroups = {
                "100": "target.scope",
                "101": "receiver.scope",
                "102": "other.scope",
                "200": "target.scope",
                "201": "receiver.scope",
                "202": "other.scope",
            }
            return f"0::/system.slice/{cgroups[argument]}\n".encode()
        if fact == "listeners":
            return (
                b"LISTEN 0 4096 0.0.0.0:8000 0.0.0.0:*\n"
                b"LISTEN 0 4096 [::]:8000 [::]:*\n"
                b"LISTEN 0 4096 0.0.0.0:8001 0.0.0.0:*\n"
            )
        if fact == "host":
            return b"dgx-test\n"
        platform_outputs = {
            "dmi_vendor": b"MSI\n",
            "dmi_product": b"MS-C931\n",
            "dmi_version": b"5.36_0ACUM024\n",
            "os_release": b'ID=ubuntu\nVERSION_ID="24.04"\n',
            "kernel": b"6.17.0-1008-nvidia\n",
            "architecture": b"aarch64\n",
            "docker_version": b"27.5.1\n",
        }
        if fact in platform_outputs:
            return platform_outputs[fact]
        raise AssertionError(f"unexpected command fact: {fact}")

    return command, calls


def _current_http_log() -> tuple[Callable[[str], bytes], list[str]]:
    calls: list[str] = []

    def http(url: str) -> bytes:
        calls.append(url)
        if url.endswith("/version"):
            return b'{"version":"0.25.1"}'
        if url.endswith("/v1/models"):
            if ":8000/" in url:
                return (
                    b'{"data":[{"id":"qwen3.6-35b-a3b",'
                    b'"root":"Qwen/Qwen3.6-35B-A3B-FP8"}]}'
                )
            return (
                b'{"data":[{"id":"qwen3-4b-real",'
                b'"root":"Qwen/Qwen3-4B"}]}'
            )
        return (
            b'vllm:num_requests_running{engine="0",model_name="qwen"} 0.0\n'
            b'vllm:prefix_cache_queries_total{engine="0"} 351609.0\n'
            b'vllm:prefix_cache_hits_total{engine="0"} 29568.0\n'
        )

    return http, calls


def test_current_like_dgx_snapshot_preserves_specific_fail_closed_reasons() -> None:
    command, command_calls = _current_command_log()
    http, http_calls = _current_http_log()
    receipt = observe_frontier(
        _expectation(), command_reader=command, http_reader=http
    )
    assert receipt.status == REFUSED
    expected_reasons = {
        "FOREIGN_GPU_COMPUTE_CGROUP_OBSERVED",
        "TARGET_GPU_COMPUTE_PROCESS_TREE_UNBOUND",
        "CONFIGURED_IMAGE_REFERENCE_MISMATCH",
        "CONFIGURED_IMAGE_REFERENCE_NOT_IMMUTABLE",
        "HOST_OWNED_LEASE_NOT_ACTIVE",
        "MODEL_REVISION_MISMATCH",
        "INFERENCE_PROCESS_GROUP_COUNT_NOT_ONE",
        "MAX_NUM_SEQS_NOT_ONE",
        "PREFIX_CACHE_NOT_EXPLICITLY_DISABLED",
        "BATCH_INVARIANCE_NOT_EFFECTIVELY_QUALIFIED",
        "LISTENER_NOT_EXACT_LOOPBACK_TARGET",
        "METRICS_PROCESS_IDENTITY_UNBOUND",
        "PREFIX_CACHE_COUNTER_NONZERO",
    }
    assert expected_reasons <= set(receipt.refusal_reasons)
    assert "OBSERVATION_UNAVAILABLE_OR_MALFORMED" not in receipt.refusal_reasons
    assert all(name in {
        "docker_ps",
        "docker_inspect",
        "docker_repo_digests",
        "docker_batch_invariant",
        "gpu",
        "compute_pids",
        "cgroup",
        "cmdline",
        "listeners",
        "host",
        "dmi_vendor",
        "dmi_product",
        "dmi_version",
        "os_release",
        "kernel",
        "architecture",
        "docker_version",
    } for name, _ in command_calls)
    assert all(
        url.startswith("http://127.0.0.1:")
        and url.rsplit("/", 1)[-1] in {"version", "models", "metrics"}
        for url in http_calls
    )
    raw = receipt.canonical_bytes()
    assert TARGET_ID.encode() not in raw
    assert b"target.scope" not in raw


def test_digest_pinned_single_process_controls_still_refuse_without_host_lease() -> None:
    command, _ = _current_command_log()

    def isolated_command(fact: str, argument: str | None) -> bytes:
        if fact == "docker_ps":
            return b"target\n"
        if fact == "docker_inspect":
            return _inspect(
                TARGET_ID,
                IMAGE_REFERENCE,
                100,
                "2026-08-29T00:00:00Z",
                8000,
                ("127.0.0.1",),
            )
        if fact == "docker_batch_invariant":
            return b"1"
        if fact == "cmdline":
            return (
                b"/usr/bin/python3\0/usr/local/bin/vllm\0serve\0"
                b"--model=Qwen/Qwen3.6-35B-A3B-FP8\0"
                b"--served-model-name=qwen3.6-35b-a3b\0"
                b"--revision=95a723d08a9490559dae23d0cff1d9466213d989\0"
                b"--port=8000\0--max-num-seqs=1\0"
                b"--no-enable-prefix-caching\0"
            )
        if fact == "compute_pids":
            return b"200\n"
        if fact == "listeners":
            return b"LISTEN 0 4096 127.0.0.1:8000 0.0.0.0:*\n"
        return command(fact, argument)

    def zero_http(url: str) -> bytes:
        if url.endswith("/version"):
            return b'{"version":"0.25.1"}'
        if url.endswith("/v1/models"):
            return (
                b'{"data":[{"id":"qwen3.6-35b-a3b",'
                b'"root":"Qwen/Qwen3.6-35B-A3B-FP8"}]}'
            )
        return (
            b"vllm:num_requests_running 0\n"
            b"vllm:prefix_cache_queries_total 0\n"
            b"vllm:prefix_cache_hits_total 0\n"
        )

    receipt = observe_frontier(
        _expectation(), command_reader=isolated_command, http_reader=zero_http
    )
    assert receipt.status == REFUSED
    assert "HOST_OWNED_LEASE_NOT_ACTIVE" in receipt.refusal_reasons
    assert "TARGET_GPU_COMPUTE_PROCESS_TREE_UNBOUND" in receipt.refusal_reasons
    assert "BATCH_INVARIANCE_NOT_EFFECTIVELY_QUALIFIED" in receipt.refusal_reasons
    assert "LISTENER_NOT_EXACT_LOOPBACK_TARGET" in receipt.refusal_reasons
    assert "METRICS_PROCESS_IDENTITY_UNBOUND" in receipt.refusal_reasons
    for reason in (
        "INFERENCE_PROCESS_GROUP_COUNT_NOT_ONE",
        "MODEL_REVISION_MISMATCH",
        "MAX_NUM_SEQS_NOT_ONE",
        "PREFIX_CACHE_NOT_EXPLICITLY_DISABLED",
        "PREFIX_CACHE_COUNTER_NONZERO",
    ):
        assert reason not in receipt.refusal_reasons


def test_adapter_failure_is_a_sanitized_refusal() -> None:
    receipt = observe_frontier(
        _expectation(),
        command_reader=lambda *_: (_ for _ in ()).throw(
            RuntimeError("secret-token")
        ),
        http_reader=lambda _: b"",
    )
    assert receipt.status == REFUSED
    assert receipt.refusal_reasons == ("OBSERVATION_UNAVAILABLE_OR_MALFORMED",)
    assert b"secret-token" not in receipt.canonical_bytes()


def test_cli_defaults_to_hswm_run_output_and_never_overwrites(
    tmp_path: Path, monkeypatch
) -> None:
    receipt = DgxQ1FrontierReceipt(
        status=REFUSED,
        refusal_reasons=("TEST_REFUSAL",),
        observed_identity_sha256="0" * 64,
        expectation_sha256="1" * 64,
        observations={"test": "bounded"},
    )
    monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.setattr(observer_module, "observe_frontier", lambda *a, **k: receipt)
    argv = [
        "--host-platform-sha256",
        canonical_sha256(PLATFORM),
        "--target-gpu-name",
        GPU_NAME,
        "--target-gpu-uuid",
        GPU_UUID,
        "--target-driver-version",
        "580.126.09",
        "--target-mig-mode",
        "[N/A]",
        "--image-id",
        IMAGE_ID,
        "--configured-image-reference",
        IMAGE_REFERENCE,
        "--vllm-version",
        "0.25.1",
        "--served-model",
        "qwen3.6-35b-a3b",
        "--model-revision",
        "95a723d08a9490559dae23d0cff1d9466213d989",
        "--model-root",
        "Qwen/Qwen3.6-35B-A3B-FP8",
        "--endpoint-host",
        "127.0.0.1",
        "--endpoint-port",
        "8000",
    ]
    output = tmp_path / "dgx_q1_frontier_snapshot.json"
    assert observer_module.main(argv) == 0
    assert output.read_bytes() == receipt.canonical_bytes()
    assert observer_module.main(argv) == 2
    assert output.read_bytes() == receipt.canonical_bytes()
