"""Focused tests for the ALFWorld B0 DGX service boundary."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from hswm.experiments import alfworld_b0_dgx as dgx
from hswm.selfmod.contracts import canonical_json_bytes


def test_frozen_service_configuration_is_b0_specific_and_bounded() -> None:
    argv = dgx.expected_server_argv()
    assert "--max-num-seqs" in argv and argv[argv.index("--max-num-seqs") + 1] == "1"
    assert "--no-enable-prefix-caching" in argv and "--no-async-scheduling" in argv
    assert "--enforce-eager" in argv and "--language-model-only" in argv
    assert dgx.MAX_REQUESTS == dgx.MAX_TOKENIZE_REQUESTS + dgx.MAX_COMPLETION_REQUESTS == 480
    assert "EGRESS_NOT_INDEPENDENTLY_CLAIMED" in dgx.NETWORK_BOUNDARY


def test_metrics_require_idle_cache_free_and_integral_success_total() -> None:
    raw = (b"vllm:num_requests_running 0\n"
           b"vllm:request_success_total{finished_reason=\"stop\"} 4\n"
           b"vllm:prefix_cache_hits_total 0\n"
           b"vllm:prefix_cache_queries_total 0\n")
    assert dgx.parse_success_total(raw) == 4
    with pytest.raises(dgx.LaunchRefused, match="absent, active, or nonzero"):
        dgx.parse_success_total(raw.replace(b"hits_total 0", b"hits_total 1"))


def _spec(tmp_path: Path) -> dgx.B0DgxLeaseSpec:
    repo = tmp_path / "repo"; repo.mkdir()
    protocol = repo / "_research/protocol.json"; protocol.parent.mkdir()
    protocol.write_text(json.dumps({"schema_version": dgx.PROTOCOL_SCHEMA, "model_runtime": dgx.MODEL_RUNTIME}))
    snapshot = tmp_path / "hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots" / dgx.MODEL_REVISION
    snapshot.mkdir(parents=True)
    return dgx.B0DgxLeaseSpec(repo_root=repo, protocol_path=protocol,
        protocol_sha256=sha256(protocol.read_bytes()).hexdigest(), declared_source_paths=(protocol,),
        lock_path=tmp_path / "locks/b0.lock", container_name="hswm-alfworld-b0-test-01",
        model_snapshot=snapshot, hf_cache=tmp_path / "cache/hf", compile_cache=tmp_path / "cache/compile")


def test_lease_validates_then_attests_and_restores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _spec(tmp_path); spec.lock_path.parent.mkdir(); spec.hf_cache.parent.mkdir(); events: list[str] = []
    manifest_raw = canonical_json_bytes({"fixture": True})
    monkeypatch.setattr(dgx, "SNAPSHOT_MANIFEST_SHA256", sha256(manifest_raw).hexdigest())
    monkeypatch.setattr(dgx, "build_model_snapshot_manifest", lambda *_args, **_kwargs: {"fixture": True})
    state = {"started": False}
    inspect = lambda: json.dumps([{"Id": "a" * 64, "Image": dgx.IMAGE_ID,
        "Config": {"Image": dgx.IMAGE, "Cmd": list(dgx.expected_server_argv()), "Env": ["HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1", "VLLM_ENABLE_V1_MULTIPROCESSING=0", "HF_HOME=/cache/huggingface", "HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub", "VLLM_CACHE_ROOT=/cache/compile/vllm", "TORCHINDUCTOR_CACHE_DIR=/cache/compile/torchinductor", "TRITON_CACHE_DIR=/cache/compile/triton", "PYTHONHASHSEED=0", "CUBLAS_WORKSPACE_CONFIG=:4096:8"]},
        "HostConfig": {"NetworkMode": "bridge", "IpcMode": "private", "PortBindings": {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18080"}]}}, "State": {"StartedAt": "now"}}]).encode()
    def command(argv: tuple[str, ...]) -> bytes:
        if argv[:4] == ("git", "-C", str(spec.repo_root), "status"): return b""
        if argv[:4] == ("git", "-C", str(spec.repo_root), "rev-parse"): return b"a" * 40 + b"\n"
        if argv[:4] == ("git", "-C", str(spec.repo_root), "show"): return spec.protocol_path.read_bytes()
        if argv[:3] == ("docker", "image", "inspect"): return json.dumps([{ "Id": dgx.IMAGE_ID, "RepoDigests": [dgx.IMAGE]}]).encode()
        if argv[:2] == ("nvidia-smi", "--query-gpu=uuid,name"): return f"{dgx.GPU_UUID}, {dgx.GPU_NAME}\n".encode()
        if argv[:2] == ("docker", "ps"): return (b"a\n" if state["started"] else b"")
        if argv[:2] == ("nvidia-smi", "--query-compute-apps=gpu_uuid,pid"): return b"gpu, 1\n" if state["started"] else b""
        if argv[:2] == ("sudo", "-n"): return b""
        if argv[:3] == ("docker", "run", "-d"): state["started"] = True; return b"a" * 64 + b"\n"
        if argv[:2] == ("docker", "inspect"): return inspect()
        if argv[:3] == ("docker", "rm", "-f"): state["started"] = False; return b"a\n"
        raise AssertionError(argv)
    metrics = b"vllm:num_requests_running 0\nvllm:request_success_total 0\nvllm:prefix_cache_hits_total 0\nvllm:prefix_cache_queries_total 0\n"
    def get(url: str) -> bytes:
        if url.endswith("/v1/models"): return b'{"data":[{"id":"qwen3.6-35b-a3b"}]}'
        if url.endswith("/version"): return b'{"version":"0.25.1"}'
        if url.endswith("/metrics"): return metrics
        raise AssertionError(url)
    lease = dgx.B0DgxLease(spec, command=command, http_get=get,
                            stop_services=lambda stopped: events.append("stop") or [("vllm", "b" * 64)],
                            restore_services=lambda stopped: events.append("restore"))
    with lease:
        assert lease.startup is not None
        assert lease.attest(0, 0)["metrics"] == metrics
        with pytest.raises(dgx.LaunchRefused, match="request count"):
            lease.attest(241, 240)
    assert lease.final is not None and lease.final["metrics"] == metrics
    assert events == ["stop", "restore"]


def test_protocol_endpoint_or_runtime_drift_refuses_before_service_stop(
        tmp_path: Path) -> None:
    spec = _spec(tmp_path); spec.lock_path.parent.mkdir(); spec.hf_cache.parent.mkdir()
    stopped: list[bool] = []
    drifted = {"schema_version": dgx.PROTOCOL_SCHEMA, "model_runtime": {**dgx.MODEL_RUNTIME, "endpoint_origin": "http://127.0.0.1:18081"}}
    spec.protocol_path.write_text(json.dumps(drifted))
    drifted_spec = dgx.B0DgxLeaseSpec(
        repo_root=spec.repo_root, protocol_path=spec.protocol_path,
        protocol_sha256=sha256(spec.protocol_path.read_bytes()).hexdigest(),
        declared_source_paths=spec.declared_source_paths, lock_path=spec.lock_path,
        container_name=spec.container_name, model_snapshot=spec.model_snapshot,
        hf_cache=spec.hf_cache, compile_cache=spec.compile_cache,
        endpoint="http://127.0.0.1:18081")
    def command(argv: tuple[str, ...]) -> bytes:
        if argv[:4] == ("git", "-C", str(spec.repo_root), "status"): return b""
        if argv[:4] == ("git", "-C", str(spec.repo_root), "rev-parse"): return b"a" * 40 + b"\n"
        if argv[:4] == ("git", "-C", str(spec.repo_root), "show"): return spec.protocol_path.read_bytes()
        raise AssertionError(argv)
    with pytest.raises(dgx.LaunchRefused, match="protocol runtime identity"):
        with dgx.B0DgxLease(drifted_spec, command=command,
                             stop_services=lambda _: stopped.append(True) or []):
            pass
    assert stopped == []
    assert dgx.B0DgxLeaseSpec.__dataclass_fields__["endpoint"].default == "http://127.0.0.1:18080"


def test_final_attest_failure_still_removes_and_restores(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _spec(tmp_path); spec.lock_path.parent.mkdir(); spec.hf_cache.parent.mkdir()
    manifest_raw = canonical_json_bytes({"fixture": True})
    monkeypatch.setattr(dgx, "SNAPSHOT_MANIFEST_SHA256", sha256(manifest_raw).hexdigest())
    monkeypatch.setattr(dgx, "build_model_snapshot_manifest", lambda *_args, **_kwargs: {"fixture": True})
    events: list[str] = []; state = {"started": False, "final": False}
    inspect = json.dumps([{"Id": "a" * 64, "Image": dgx.IMAGE_ID,
        "Config": {"Image": dgx.IMAGE, "Cmd": list(dgx.expected_server_argv()), "Env": ["HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1", "VLLM_ENABLE_V1_MULTIPROCESSING=0", "HF_HOME=/cache/huggingface", "HUGGINGFACE_HUB_CACHE=/cache/huggingface/hub", "VLLM_CACHE_ROOT=/cache/compile/vllm", "TORCHINDUCTOR_CACHE_DIR=/cache/compile/torchinductor", "TRITON_CACHE_DIR=/cache/compile/triton", "PYTHONHASHSEED=0", "CUBLAS_WORKSPACE_CONFIG=:4096:8"]},
        "HostConfig": {"NetworkMode": "bridge", "IpcMode": "private", "PortBindings": {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18080"}]}}, "State": {"StartedAt": "now"}}]).encode()
    def command(argv: tuple[str, ...]) -> bytes:
        if argv[:4] == ("git", "-C", str(spec.repo_root), "status"): return b""
        if argv[:4] == ("git", "-C", str(spec.repo_root), "rev-parse"): return b"a" * 40 + b"\n"
        if argv[:4] == ("git", "-C", str(spec.repo_root), "show"): return spec.protocol_path.read_bytes()
        if argv[:3] == ("docker", "image", "inspect"): return json.dumps([{ "Id": dgx.IMAGE_ID, "RepoDigests": [dgx.IMAGE]}]).encode()
        if argv[:2] == ("nvidia-smi", "--query-gpu=uuid,name"): return f"{dgx.GPU_UUID}, {dgx.GPU_NAME}\n".encode()
        if argv[:3] == ("docker", "ps", "-aq"): return b""
        if argv[:2] == ("docker", "ps"): return b"a\n" if state["started"] else b""
        if argv[:2] == ("nvidia-smi", "--query-compute-apps=gpu_uuid,pid"): return b"gpu, 1\n" if state["started"] else b""
        if argv[:2] == ("sudo", "-n"): return b""
        if argv[:3] == ("docker", "run", "-d"): state["started"] = True; return b"a" * 64 + b"\n"
        if argv[:2] == ("docker", "inspect"): return inspect
        if argv[:3] == ("docker", "rm", "-f"): events.append("rm"); state["started"] = False; return b"a\n"
        raise AssertionError(argv)
    metrics_zero = b"vllm:num_requests_running 0\nvllm:request_success_total 0\nvllm:prefix_cache_hits_total 0\nvllm:prefix_cache_queries_total 0\n"
    metrics_one = metrics_zero.replace(b"request_success_total 0", b"request_success_total 1")
    def get(url: str) -> bytes:
        if url.endswith("/v1/models"): return b'{"data":[{"id":"qwen3.6-35b-a3b"}]}'
        if url.endswith("/version"): return b'{"version":"0.25.1"}'
        if url.endswith("/metrics"): return metrics_one if state["final"] else metrics_zero
        raise AssertionError(url)
    lease = dgx.B0DgxLease(spec, command=command, http_get=get,
                            stop_services=lambda _: events.append("stop") or [("vllm", "b" * 64)],
                            restore_services=lambda _: events.append("restore"))
    with pytest.raises(dgx.LaunchRefused, match="service attestation drifted"):
        with lease:
            state["final"] = True
    # __exit__ propagates the original final-attest error only after cleanup.
    assert events == ["stop", "rm", "restore"]
    assert state["started"] is False


def test_stale_container_name_refuses_before_shared_service_stop(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _spec(tmp_path); spec.lock_path.parent.mkdir(); spec.hf_cache.parent.mkdir()
    stopped: list[bool] = []
    manifest_raw = canonical_json_bytes({"fixture": True})
    monkeypatch.setattr(dgx, "SNAPSHOT_MANIFEST_SHA256", sha256(manifest_raw).hexdigest())
    monkeypatch.setattr(dgx, "build_model_snapshot_manifest", lambda *_args, **_kwargs: {"fixture": True})
    def command(argv: tuple[str, ...]) -> bytes:
        if argv[:4] == ("git", "-C", str(spec.repo_root), "status"): return b""
        if argv[:4] == ("git", "-C", str(spec.repo_root), "rev-parse"): return b"a" * 40 + b"\n"
        if argv[:4] == ("git", "-C", str(spec.repo_root), "show"): return spec.protocol_path.read_bytes()
        if argv[:3] == ("docker", "image", "inspect"): return json.dumps([{ "Id": dgx.IMAGE_ID, "RepoDigests": [dgx.IMAGE]}]).encode()
        if argv[:2] == ("nvidia-smi", "--query-gpu=uuid,name"): return f"{dgx.GPU_UUID}, {dgx.GPU_NAME}\n".encode()
        if argv[:3] == ("docker", "ps", "-aq"): return b"stale\n"
        raise AssertionError(argv)
    with pytest.raises(dgx.LaunchRefused, match="container name is not fresh"):
        with dgx.B0DgxLease(spec, command=command,
                             stop_services=lambda _: stopped.append(True) or []):
            pass
    assert stopped == []


def test_snapshot_mount_path_must_be_the_hashed_canonical_snapshot(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _spec(tmp_path); spec.lock_path.parent.mkdir(); spec.hf_cache.parent.mkdir()
    wrong_snapshot = tmp_path / "elsewhere/snapshots" / dgx.MODEL_REVISION
    wrong_snapshot.mkdir(parents=True)
    wrong = dgx.B0DgxLeaseSpec(
        repo_root=spec.repo_root, protocol_path=spec.protocol_path,
        protocol_sha256=spec.protocol_sha256, declared_source_paths=spec.declared_source_paths,
        lock_path=spec.lock_path, container_name=spec.container_name,
        model_snapshot=wrong_snapshot, hf_cache=spec.hf_cache,
        compile_cache=spec.compile_cache)
    manifest_raw = canonical_json_bytes({"fixture": True})
    monkeypatch.setattr(dgx, "SNAPSHOT_MANIFEST_SHA256", sha256(manifest_raw).hexdigest())
    monkeypatch.setattr(dgx, "build_model_snapshot_manifest", lambda *_args, **_kwargs: {"fixture": True})
    def command(argv: tuple[str, ...]) -> bytes:
        if argv[:4] == ("git", "-C", str(spec.repo_root), "status"): return b""
        if argv[:4] == ("git", "-C", str(spec.repo_root), "rev-parse"): return b"a" * 40 + b"\n"
        if argv[:4] == ("git", "-C", str(spec.repo_root), "show"): return spec.protocol_path.read_bytes()
        if argv[:3] == ("docker", "image", "inspect"): return json.dumps([{ "Id": dgx.IMAGE_ID, "RepoDigests": [dgx.IMAGE]}]).encode()
        if argv[:2] == ("nvidia-smi", "--query-gpu=uuid,name"): return f"{dgx.GPU_UUID}, {dgx.GPU_NAME}\n".encode()
        raise AssertionError(argv)
    with pytest.raises(dgx.LaunchRefused, match="model snapshot drifted"):
        dgx.B0DgxLease(wrong, command=command)._validate()
