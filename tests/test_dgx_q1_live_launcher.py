from __future__ import annotations

import json
from hashlib import sha1
from pathlib import Path

import pytest

from _research.dnrd5.canonical_json import parse_canonical
from _research.dgx_q1.live_launcher import LaunchRefused, LiveQ1Lease, LiveQ1Spec
from _research.dgx_q1.live_preregistration import freeze_live_preregistration
from tests.test_dgx_q1_live_preregistration import (
    REVISION,
    SOURCE_COMMIT,
    SOURCE_TREE,
    ci_receipt,
    preregistration_inputs,
)


PUBLICATION_COMMIT = "f" * 40
PUBLICATION_TREE = "9" * 40


def _spec(tmp_path: Path) -> tuple[LiveQ1Spec, dict]:
    repository = tmp_path / "repo"
    repository.mkdir()
    freeze = repository / "_research/dgx_q1/preregistrations/fixture"
    freeze.parent.mkdir(parents=True)
    freeze_live_preregistration(freeze, preregistration_inputs())
    runtime = parse_canonical(
        (freeze / "identities/runtime_identity_sha256.json").read_bytes()
    )
    publication = tmp_path / "publication-ci.json"
    publication.write_bytes(ci_receipt(PUBLICATION_COMMIT, PUBLICATION_TREE, 99))
    hub = tmp_path / "hub"
    model_root = hub / "models--Qwen--Qwen-Test"
    blobs = model_root / "blobs"
    snapshot = model_root / "snapshots" / REVISION
    blobs.mkdir(parents=True)
    snapshot.mkdir(parents=True)
    model_bytes = b"model"
    digest = __import__("hashlib").sha256(model_bytes).hexdigest()
    (blobs / digest).write_bytes(model_bytes)
    (snapshot / "config.json").symlink_to(Path("../../blobs") / digest)
    hf_cache = tmp_path / "hf-cache"
    compile_cache = tmp_path / "compile-cache"
    hf_cache.mkdir()
    compile_cache.mkdir()
    spec = LiveQ1Spec(
        repo_root=repository,
        expected_commit=PUBLICATION_COMMIT,
        expected_tree=PUBLICATION_TREE,
        publication_ci_receipt=publication,
        publication_ci_receipt_sha256=__import__("hashlib").sha256(
            publication.read_bytes()
        ).hexdigest(),
        freeze_root=freeze,
        plan_sha256=__import__("hashlib").sha256(
            (freeze / "plan.json").read_bytes()
        ).hexdigest(),
        lock_path=tmp_path / "q1.lock",
        container_name="hswm-q1-live",
        model_snapshot=snapshot,
        hf_cache=hf_cache,
        compile_cache=compile_cache,
    )
    return spec, runtime


def _observations(spec: LiveQ1Spec, runtime: dict):
    state = {"running": False, "launch": None, "metric_index": 0}
    calls: list[tuple[str, ...]] = []

    def command(argv: tuple[str, ...]) -> bytes:
        calls.append(argv)
        if argv[:4] == ("git", "-C", str(spec.repo_root), "rev-parse"):
            return (PUBLICATION_COMMIT + "\n").encode()
        if argv[:4] == ("git", "-C", str(spec.repo_root), "show"):
            return (PUBLICATION_TREE + "\n").encode()
        if argv[:4] == ("git", "-C", str(spec.repo_root), "status"):
            return b""
        if argv[:4] in {
            ("git", "-C", str(spec.repo_root), "merge-base"),
            ("git", "-C", str(spec.repo_root), "diff"),
        }:
            return b""
        if argv[:4] == ("git", "-C", str(spec.repo_root), "ls-tree"):
            rows = []
            for path in sorted(spec.freeze_root.rglob("*")):
                if not path.is_file():
                    continue
                raw = path.read_bytes()
                oid = sha1(
                    b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
                ).hexdigest()
                relative = path.relative_to(spec.repo_root).as_posix()
                rows.append(f"100644 blob {oid}\t{relative}".encode())
            return b"\0".join(rows) + b"\0"
        if argv[:3] == ("docker", "ps", "-q"):
            return b""
        if argv[:3] == ("docker", "image", "inspect"):
            return (
                runtime["image_id"] + "|" + runtime["container_image"] + "\n"
            ).encode()
        if argv[:2] == ("docker", "run"):
            state["running"] = True
            state["launch"] = argv
            return b"container-id\n"
        if argv[:2] == ("docker", "inspect"):
            launch = state["launch"]
            assert isinstance(launch, tuple)
            image_index = launch.index(runtime["container_image"])
            environment = [
                launch[index + 1]
                for index, value in enumerate(launch)
                if value == "-e"
            ]
            mounts = []
            for index, value in enumerate(launch):
                if value != "--mount":
                    continue
                fields = dict(
                    item.split("=", 1)
                    for item in launch[index + 1].split(",")
                    if "=" in item
                )
                mounts.append(
                    {
                        "Destination": fields["dst"],
                        "Source": fields["src"],
                        "RW": "readonly" not in launch[index + 1],
                    }
                )
            document = [
                {
                    "Id": "container-id",
                    "Image": runtime["image_id"],
                    "Config": {
                        "Image": runtime["container_image"],
                        "Cmd": list(launch[image_index + 1 :]),
                        "Env": environment,
                    },
                    "HostConfig": {
                        "NetworkMode": "bridge",
                        "IpcMode": "private",
                        "RestartPolicy": {"Name": "no"},
                        "DeviceRequests": [{"DeviceIDs": [runtime["gpu_uuid"]]}],
                    },
                    "State": {
                        "Running": True,
                        "Pid": 10,
                        "StartedAt": "2026-08-29T00:00:00Z",
                    },
                    "Mounts": mounts,
                    "NetworkSettings": {"Ports": {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18080"}]}},
                }
            ]
            return json.dumps(document, separators=(",", ":")).encode()
        if argv[:3] == ("docker", "rm", "-f"):
            state["running"] = False
            return b"hswm-q1-live\n"
        if argv[:3] == ("docker", "exec", spec.container_name):
            if "readlink" in argv:
                return b"net:[4026533000]\n"
            return b"  0: 00000000:1F40 00000000:0000 0A\n"
        if argv[0] == "nvidia-smi":
            if argv[1].startswith("--query-gpu="):
                return (
                    f"{runtime['gpu_uuid']}, {runtime['gpu_name']}, "
                    f"{runtime['gpu_driver_version']}, "
                    f"{runtime['gpu_compute_capability']}\n"
                ).encode()
            return (
                f"{runtime['gpu_uuid']}, 123\n".encode()
                if state["running"]
                else b""
            )
        if argv[0] == "ss":
            return (
                b'LISTEN 0 4096 127.0.0.1:18080 0.0.0.0:* users:(("python",pid=123,fd=9))\n'
                if state["running"]
                else b""
            )
        if argv[0] == "ps":
            return b"10 1\n123 10\n"
        if argv[0] == "readlink": return b"net:[1]\n"
        if argv[0] == "cat" and "/net/tcp" in argv[1]: return b"  0: 00000000:1F40 00000000:0000 0A\n"
        if argv[0] == "cat":
            return b"python\0vllm\0" if argv[1].endswith("cmdline") else b"0::/docker/q1\n"
        if argv[0] in {"test", "find"}:
            return b""
        raise AssertionError(argv)

    metric_totals = [0, 0, 1, 1]

    def http_get(url: str) -> bytes:
        if url.endswith("/version"):
            return json.dumps({"version": runtime["vllm_version"]}).encode()
        if url.endswith("/v1/models"):
            return json.dumps({"data": [{"id": runtime["served_model"]}]}).encode()
        assert url.endswith("/metrics")
        index = state["metric_index"]
        state["metric_index"] += 1
        total = metric_totals[index]
        return (
            'vllm:num_requests_running{model_name="q1",engine="0"} 0\n'
            f'vllm:request_success_total{{finished_reason="stop"}} {total}\n'
            'vllm:request_success_total{finished_reason="length"} 0\n'
            'vllm:prefix_cache_hits_total{model_name="q1"} 0\n'
            'vllm:prefix_cache_queries_total{model_name="q1"} 0\n'
        ).encode()

    return command, http_get, calls, state


def test_digest_pinned_lease_attests_actual_boundary_and_removes(tmp_path: Path) -> None:
    spec, runtime = _spec(tmp_path)
    command, http_get, calls, state = _observations(spec, runtime)
    attempt = "DNRD5-Q1L-001-R001"
    with LiveQ1Lease(spec, command, http_get) as lease:
        assert lease.startup_attestation_raw is not None
        assert lease.validated_freeze_files["plan.json"] == (
            spec.freeze_root / "plan.json"
        ).read_bytes()
        assert parse_canonical(lease.attest("PRE", attempt, 0))["phase"] == "PRE"
        assert parse_canonical(lease.attest("POST", attempt, 1))[
            "request_success_total"
        ] == 1
        assert len(
            parse_canonical(lease.attest("FINAL", None, 1))[
                "container_network_namespace_sha256"
            ]
        ) == 64
    assert state["running"] is False
    launch = next(argv for argv in calls if argv[:2] == ("docker", "run"))
    assert launch[launch.index("--network") + 1] == "bridge"
    assert launch[launch.index("--ipc") + 1] == "private"
    assert "VLLM_BATCH_INVARIANT=1" in launch
    assert "VLLM_ENABLE_V1_MULTIPROCESSING=0" in launch
    assert "--no-enable-prefix-caching" in launch
    assert "--language-model-only" in launch
    assert any("dst=/model-repository" in value and "readonly" in value for value in launch)
    assert "/model-repository/snapshots/" + REVISION in launch
    assert all("POST" not in " ".join(argv) for argv in calls)


def test_existing_container_refuses_before_launch(tmp_path: Path) -> None:
    spec, runtime = _spec(tmp_path)
    command, http_get, calls, _ = _observations(spec, runtime)

    def busy(argv: tuple[str, ...]) -> bytes:
        if argv[:3] == ("docker", "ps", "-q"):
            return b"legacy\n"
        return command(argv)

    with pytest.raises(LaunchRefused, match="preexisting"):
        with LiveQ1Lease(spec, busy, http_get):
            pass
    assert not any(argv[:2] == ("docker", "run") for argv in calls)


def test_publication_ci_or_plan_hash_drift_refuses(tmp_path: Path) -> None:
    spec, runtime = _spec(tmp_path)
    command, http_get, _, _ = _observations(spec, runtime)
    bad = LiveQ1Spec(
        **{
            **{name: getattr(spec, name) for name in spec.__dataclass_fields__},
            "plan_sha256": "0" * 64,
        }
    )
    with pytest.raises(LaunchRefused):
        with LiveQ1Lease(bad, command, http_get):
            pass


def test_nonzero_labeled_request_series_cannot_be_hidden(tmp_path: Path) -> None:
    spec, runtime = _spec(tmp_path)
    command, http_get, _, _ = _observations(spec, runtime)

    def hostile(url: str) -> bytes:
        if url.endswith("/metrics"):
                return (
                    b"vllm:num_requests_running 0\n"
                    b'vllm:request_success_total{finished_reason="stop"} 1\n'
                    b'vllm:request_success_total{finished_reason="length"} 0\n'
                    b"vllm:prefix_cache_hits_total 0\n"
                    b"vllm:prefix_cache_queries_total 0\n"
                )
        return http_get(url)

    with pytest.raises(LaunchRefused, match="counter"):
        with LiveQ1Lease(spec, command, hostile):
            pass


def test_ollama_listener_and_nonzero_prefix_metric_refuse(tmp_path: Path) -> None:
    spec, runtime = _spec(tmp_path)
    command, http_get, calls, _ = _observations(spec, runtime)

    def ollama(argv: tuple[str, ...]) -> bytes:
        if argv[0] == "ss" and not any(call[:2] == ("docker", "run") for call in calls):
            return b"LISTEN 0 1 127.0.0.1:11434 0.0.0.0:*\n"
        return command(argv)

    with pytest.raises(LaunchRefused, match="non-allowlisted"):
        with LiveQ1Lease(spec, ollama, http_get):
            pass

    def cached(url: str) -> bytes:
        if url.endswith("/metrics"):
            return b"vllm:num_requests_running 0\nvllm:request_success_total 0\nvllm:prefix_cache_hits_total 1\n"
        return http_get(url)

    with pytest.raises(LaunchRefused, match="prefix-cache"):
        with LiveQ1Lease(spec, command, cached):
            pass

    def missing_prefix(url: str) -> bytes:
        if url.endswith("/metrics"):
            return (
                b"vllm:num_requests_running 0\n"
                b"vllm:request_success_total 0\n"
            )
        return http_get(url)

    with pytest.raises(LaunchRefused, match="prefix-cache"):
        with LiveQ1Lease(spec, command, missing_prefix):
            pass


def test_dgx_listener_allowlist_matches_observed_non_inference_endpoints() -> None:
    observed = "\n".join(
        f"LISTEN 0 4096 {endpoint} 0.0.0.0:*"
        for endpoint in sorted(LiveQ1Lease._ALLOWED_NON_INFERENCE_LISTENERS)
    )
    assert not LiveQ1Lease._unexpected_inference_listener(observed, 18080)
    assert LiveQ1Lease._unexpected_inference_listener(
        observed + "\nLISTEN 0 4096 127.0.0.1:11434 0.0.0.0:*",
        18080,
    )
    assert LiveQ1Lease._unexpected_inference_listener(
        observed + "\nLISTEN 0 4096 0.0.0.0:46135 0.0.0.0:*",
        18080,
    )


def test_missing_container_namespace_listener_refuses(tmp_path: Path) -> None:
    spec, runtime = _spec(tmp_path)
    command, http_get, _, _ = _observations(spec, runtime)

    def missing_internal(argv: tuple[str, ...]) -> bytes:
        if argv[:3] == ("docker", "exec", spec.container_name) and "cat" in argv:
            return b"  sl  local_address rem_address st\n"
        return command(argv)

    with pytest.raises(LaunchRefused, match="listener"):
        with LiveQ1Lease(spec, missing_internal, http_get):
            pass


def test_publication_tree_must_contain_every_exact_freeze_blob(
    tmp_path: Path,
) -> None:
    spec, runtime = _spec(tmp_path)
    command, http_get, _, _ = _observations(spec, runtime)

    def untracked(argv: tuple[str, ...]) -> bytes:
        if argv[:4] == ("git", "-C", str(spec.repo_root), "ls-tree"):
            return b""
        return command(argv)

    with pytest.raises(LaunchRefused, match="publication tree"):
        with LiveQ1Lease(spec, untracked, http_get):
            pass

    def substituted(argv: tuple[str, ...]) -> bytes:
        raw = command(argv)
        if argv[:4] == ("git", "-C", str(spec.repo_root), "ls-tree"):
            return raw.replace(raw.split()[2], b"0" * 40, 1)
        return raw

    with pytest.raises(LaunchRefused, match="exact publication-tree blobs"):
        with LiveQ1Lease(spec, substituted, http_get):
            pass

    def source_drift(argv: tuple[str, ...]) -> bytes:
        if argv[:4] == ("git", "-C", str(spec.repo_root), "diff"):
            raise LaunchRefused("source changed after source CI")
        return command(argv)

    with pytest.raises(LaunchRefused, match="unreadable"):
        with LiveQ1Lease(spec, source_drift, http_get):
            pass


def test_external_freeze_and_listener_appearing_mid_lease_refuse(
    tmp_path: Path,
) -> None:
    spec, runtime = _spec(tmp_path)
    outside = tmp_path / "external-freeze"
    freeze_live_preregistration(outside, preregistration_inputs())
    external = LiveQ1Spec(
        **{
            **{name: getattr(spec, name) for name in spec.__dataclass_fields__},
            "freeze_root": outside,
        }
    )
    command, http_get, _, _ = _observations(external, runtime)
    with pytest.raises(LaunchRefused, match="descendant"):
        with LiveQ1Lease(external, command, http_get):
            pass

    command, http_get, _, _ = _observations(spec, runtime)
    listener_reads = 0

    def late_listener(argv: tuple[str, ...]) -> bytes:
        nonlocal listener_reads
        raw = command(argv)
        if argv[0] == "ss":
            listener_reads += 1
            if listener_reads >= 3:
                raw += b"LISTEN 0 1 127.0.0.1:11434 0.0.0.0:*\n"
        return raw

    attempt = "DNRD5-Q1L-001-R001"
    with LiveQ1Lease(spec, late_listener, http_get) as lease:
        with pytest.raises(LaunchRefused, match="listener"):
            lease.attest("PRE", attempt, 0)
