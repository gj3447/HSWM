"""Focused checks for the thin DGX service lifecycle."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

from hswm.experiments import g1_micro
from hswm.experiments import g1_micro_dgx as g1_dgx
from hswm.experiments.g1_micro_dgx import (
    DGXFreshRuntime,
    DGXFreshSpec,
    LaunchRefused,
    make_runtime_binding_record,
    offline_action_code_tokenizer_receipt,
    verify_dgx_execution_receipt,
)
from hswm.selfmod.contracts import canonical_json_bytes


_PROTOCOL = (
    Path(__file__).parents[1]
    / "_research/causal_composition/preregistrations/"
    "g1_micro_exploratory_2026-08-30/protocol.v1.json"
)
_OPAQUE_PROTOCOL = (
    Path(__file__).parents[1]
    / "_research/causal_composition/preregistrations/"
    "g1_opaque_identifiability_pilot_2026-08-30/protocol.v1.json"
)
_SNAPSHOT_MANIFEST = (
    Path(__file__).parents[1]
    / "_research/dgx_mi2/preregistrations/"
    "hswm-dnrd5-qcase024-mi-2-launch-crossed-v1-2026-08-29/"
    "identities/ASYNC_DISABLED/model_snapshot_manifest_sha256.json"
)
_BUNDLE_VERIFIER = Path(__file__).parents[1] / "scripts/verify_hswm_g1_micro_bundle.py"


def test_standalone_bundle_verifier_bootstraps_repository_imports() -> None:
    completed = subprocess.run(
        [sys.executable, str(_BUNDLE_VERIFIER), "--help"],
        cwd=Path(__file__).parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Replay frozen local" in completed.stdout


def _spec(tmp_path: Path) -> DGXFreshSpec:
    output_root = tmp_path / "wrapper"
    output_root.mkdir()
    registry_parent = tmp_path / "durable"
    registry_parent.mkdir()
    snapshot = (
        tmp_path
        / "hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/"
        "95a723d08a9490559dae23d0cff1d9466213d989"
    )
    snapshot.mkdir(parents=True)
    return DGXFreshSpec(
        repo_root=tmp_path,
        protocol_path=tmp_path / "protocol.json",
        output_dir=output_root / "bundle",
        runtime_binding_path=output_root / "runtime.json",
        execution_registry=registry_parent / "once",
        lock_path=tmp_path / "lock",
        container_name="hswm-g1-micro-001",
        model_snapshot=snapshot,
        hf_cache=tmp_path / "hf",
        compile_cache=tmp_path / "compile",
    )


def test_core_server_argv_is_the_only_runner_argv() -> None:
    protocol, _ = g1_micro.load_protocol(_PROTOCOL)
    argv = g1_micro.expected_dgx_server_argv(protocol)

    assert argv[argv.index("--max-num-seqs") + 1] == "1"
    assert "--no-enable-prefix-caching" in argv
    assert "--no-async-scheduling" in argv
    assert protocol["live_binding"]["model_revision"] in " ".join(argv)


def test_runtime_record_uses_core_schema_and_rejects_drift() -> None:
    protocol, protocol_sha = g1_micro.load_protocol(_PROTOCOL)
    binding = protocol["live_binding"]
    source = g1_micro._source_manifest()
    server_argv = g1_micro.expected_dgx_server_argv(protocol)
    container_id = "b" * 64
    started_at = "2026-08-30T00:00:00Z"
    root = Path(__file__).parents[1]
    tracked = {
        path: sha256((root / path).read_bytes()).hexdigest()
        for path in g1_micro.DGX_TRACKED_SOURCE_PATHS
    }
    record = make_runtime_binding_record(
        protocol=protocol,
        protocol_sha256=protocol_sha,
        source_commit="a" * 40,
        source_tree="f" * 40,
        source_manifest=source,
        tracked_source_sha256=tracked,
        protocol_file_sha256=sha256(_PROTOCOL.read_bytes()).hexdigest(),
        container_id_sha256=sha256(container_id.encode()).hexdigest(),
        container_start_sha256=sha256(started_at.encode()).hexdigest(),
        container_inspect_raw=canonical_json_bytes(
            [
                {
                    "Config": {"Cmd": server_argv, "Image": binding["container_image"]},
                    "HostConfig": {
                        "IpcMode": "private",
                        "NetworkMode": "bridge",
                        "PortBindings": {
                            "8000/tcp": [
                                {"HostIp": "127.0.0.1", "HostPort": "18080"}
                            ]
                        },
                    },
                    "Id": container_id,
                    "Image": binding["container_image_id"],
                    "State": {"StartedAt": started_at},
                }
            ]
        ),
        image_inspect_raw=canonical_json_bytes(
            [
                {
                    "Id": binding["container_image_id"],
                    "RepoDigests": [binding["container_image"]],
                }
            ]
        ),
        gpu_observation_raw=f"{binding['gpu_uuid']}, {binding['gpu_name']}\n".encode(),
        snapshot_manifest_raw=_SNAPSHOT_MANIFEST.read_bytes(),
        startup_metrics_raw=(
            b"vllm:num_requests_running 0\n"
            b"vllm:request_success_total 0\n"
            b"vllm:prefix_cache_hits_total 0\n"
            b"vllm:prefix_cache_queries_total 0\n"
        ),
        startup_models_raw=canonical_json_bytes(
            {"data": [{"id": binding["served_model"]}]}
        ),
        startup_version_raw=canonical_json_bytes({"version": binding["vllm_version"]}),
    )
    g1_micro.validate_dgx_runtime_binding(
        record,
        protocol=protocol,
        protocol_sha256=protocol_sha,
        source_manifest=source,
    )
    drifted = deepcopy(record)
    drifted["payload"]["endpoint_origin"] = "http://127.0.0.1:8000"
    unsigned = dict(drifted)
    unsigned.pop("record_sha256")
    drifted["record_sha256"] = g1_micro.canonical_sha256(unsigned)

    with pytest.raises(g1_micro.G1MicroError, match="runtime binding drifted"):
        g1_micro.validate_dgx_runtime_binding(
            drifted,
            protocol=protocol,
            protocol_sha256=protocol_sha,
            source_manifest=source,
        )


def test_final_receipt_joins_eight_requests_and_teardown() -> None:
    protocol, _ = g1_micro.load_protocol(_PROTOCOL)
    binding = protocol["live_binding"]
    container_id = "7" * 64
    started_at = "2026-08-30T00:00:00Z"
    runtime_binding = g1_micro.make_record(
        "DGXFreshRuntimeBinding",
        owner_uid="principal:g1-micro-dgx-runtime-custodian",
        payload={
            "container_id_sha256": sha256(container_id.encode()).hexdigest(),
            "container_start_sha256": sha256(started_at.encode()).hexdigest(),
        },
    )
    bundle = {
        "bundle_sha256": "8" * 64,
        "runtime_binding": runtime_binding,
        "terminal": "EXPLORATORY_OBSERVATION_RECORDED_NO_EFFICACY_INFERENCE",
    }
    container_raw = canonical_json_bytes(
        [
            {
                "Config": {"Cmd": g1_micro.expected_dgx_server_argv(protocol)},
                "Id": container_id,
                "Image": binding["container_image_id"],
                "State": {"StartedAt": started_at},
            }
        ]
    )
    models_raw = canonical_json_bytes({"data": [{"id": binding["served_model"]}]})
    version_raw = canonical_json_bytes({"version": binding["vllm_version"]})

    def receipt(successes: int) -> dict[str, object]:
        metrics = (
            b"vllm:num_requests_running 0\n"
            + f"vllm:request_success_total {successes}\n".encode()
            + b"vllm:prefix_cache_hits_total 0\n"
            + b"vllm:prefix_cache_queries_total 0\n"
        )
        return g1_micro.make_record(
            "DGXRuntimeExecutionReceipt",
            owner_uid="principal:g1-micro-dgx-runtime-custodian",
            payload={
                "bundle_sha256": bundle["bundle_sha256"],
                "completion_posts": 8,
                "final_container_inspect_json": container_raw.decode(),
                "final_container_inspect_sha256": sha256(container_raw).hexdigest(),
                "final_metrics_sha256": sha256(metrics).hexdigest(),
                "final_metrics_utf8": metrics.decode(),
                "final_models_json": models_raw.decode(),
                "final_models_sha256": sha256(models_raw).hexdigest(),
                "final_version_json": version_raw.decode(),
                "final_version_sha256": sha256(version_raw).hexdigest(),
                "network_boundary": g1_micro.DGX_NETWORK_BOUNDARY,
                "runtime_image_identity_verified": True,
                "shared_service_snapshot": [],
                "shared_services_restored_after_quiescence": True,
                "successful_generation_requests": 8,
                "teardown_observation": {
                    "docker_ps_utf8": "",
                    "gpu_compute_utf8": "",
                    "listeners_utf8": "",
                },
                "terminal": bundle["terminal"],
                "tokenize_posts": 8,
            },
            refs=(g1_micro._ref("runtime_binding", runtime_binding),),
        )

    verified = verify_dgx_execution_receipt(
        receipt=receipt(8), bundle=bundle, protocol=protocol
    )
    assert verified["successful_generation_requests"] == 8
    with pytest.raises(LaunchRefused, match="final service evidence"):
        verify_dgx_execution_receipt(
            receipt=receipt(7), bundle=bundle, protocol=protocol
        )


def test_offline_opaque_tokenizer_receipt_requires_equal_lengths_and_order(
    tmp_path: Path,
) -> None:
    protocol, _ = g1_micro.load_protocol(_OPAQUE_PROTOCOL)
    binding = protocol["tokenizer_binding"]
    snapshot = tmp_path / binding["model_revision"]
    snapshot.mkdir()

    def command(argv: tuple[str, ...]) -> bytes:
        payload = json.loads(argv[-2])
        assert payload["episodes"] == [
            {
                "action_codes": episode["action_codes"],
                "episode_uid": episode["episode_uid"],
            }
            for episode in binding["episodes"]
        ]
        rows = [
            {
                "episode_uid": episode["episode_uid"],
                "token_ids": episode["token_ids"],
            }
            for episode in binding["episodes"]
        ]
        return canonical_json_bytes(
            {
                "transformers_version": binding["transformers_version"],
                "tokenizers_version": binding["tokenizers_version"],
                "episodes": rows,
            }
        )

    receipt = offline_action_code_tokenizer_receipt(
        command=command,
        snapshot=snapshot,
        tokenizer_binding=binding,
    )
    expected = {
        "schema_version": "hswm-g1-opaque-offline-tokenizer-receipt/v1",
        "container_image": binding["container_image"],
        "container_image_id": binding["container_image_id"],
        "model_repository": binding["model_repository"],
        "model_revision": binding["model_revision"],
        "snapshot_manifest_sha256": binding["snapshot_manifest_sha256"],
        "encoding": binding["encoding"],
        "transformers_version": binding["transformers_version"],
        "tokenizers_version": binding["tokenizers_version"],
        "episodes": [
            {
                "episode_uid": episode["episode_uid"],
                "action_codes": episode["action_codes"],
                "token_ids": episode["token_ids"],
                "token_counts": episode["token_counts"],
            }
            for episode in binding["episodes"]
        ],
    }
    unsigned = dict(receipt)
    digest = unsigned.pop("receipt_sha256")
    assert unsigned == expected
    assert digest == sha256(canonical_json_bytes(unsigned)).hexdigest()

    def unequal(argv: tuple[str, ...]) -> bytes:
        payload = json.loads(argv[-2])
        return canonical_json_bytes(
            {
                "transformers_version": binding["transformers_version"],
                "tokenizers_version": binding["tokenizers_version"],
                "episodes": [
                    {
                        "episode_uid": item["episode_uid"],
                        "token_ids": [[1], [2, 3]],
                    }
                    for item in payload["episodes"]
                ],
            }
        )

    with pytest.raises(LaunchRefused, match="equal offline token counts"):
        offline_action_code_tokenizer_receipt(
            command=unequal,
            snapshot=snapshot,
            tokenizer_binding=binding,
        )

    def swapped(argv: tuple[str, ...]) -> bytes:
        payload = json.loads(argv[-2])
        rows = [
            {"episode_uid": item["episode_uid"], "token_ids": [[1], [2]]}
            for item in payload["episodes"]
        ]
        rows[0], rows[1] = rows[1], rows[0]
        return canonical_json_bytes(
            {
                "transformers_version": binding["transformers_version"],
                "tokenizers_version": binding["tokenizers_version"],
                "episodes": rows,
            }
        )

    with pytest.raises(LaunchRefused, match="opaque action codes"):
        offline_action_code_tokenizer_receipt(
            command=swapped,
            snapshot=snapshot,
            tokenizer_binding=binding,
        )


def _opaque_tokenizer_receipt_for_test(binding: Mapping[str, Any]) -> dict[str, Any]:
    receipt = {
        "schema_version": "hswm-g1-opaque-offline-tokenizer-receipt/v1",
        **{
            key: deepcopy(binding[key])
            for key in (
                "container_image", "container_image_id", "model_repository",
                "model_revision", "snapshot_manifest_sha256", "encoding",
                "transformers_version", "tokenizers_version", "episodes",
            )
        },
    }
    return {**receipt, "receipt_sha256": sha256(canonical_json_bytes(receipt)).hexdigest()}


def test_offline_tokenizer_uses_pinned_python3_entrypoint(tmp_path: Path) -> None:
    protocol, _ = g1_micro.load_protocol(_OPAQUE_PROTOCOL)
    binding = protocol["tokenizer_binding"]
    snapshot = tmp_path / binding["model_revision"]
    snapshot.mkdir()
    seen: list[tuple[str, ...]] = []

    def command(argv: tuple[str, ...]) -> bytes:
        seen.append(argv)
        return canonical_json_bytes({
            "transformers_version": binding["transformers_version"],
            "tokenizers_version": binding["tokenizers_version"],
            "episodes": [
                {"episode_uid": item["episode_uid"], "token_ids": item["token_ids"]}
                for item in binding["episodes"]
            ],
        })

    offline_action_code_tokenizer_receipt(
        command=command, snapshot=snapshot, tokenizer_binding=binding
    )
    assert seen[0][seen[0].index("--entrypoint") + 1] == "/usr/bin/python3"


def test_opaque_dgx_preflight_emits_validated_tokenizer_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    protocol, protocol_sha = g1_micro.load_protocol(_OPAQUE_PROTOCOL)
    binding = protocol["tokenizer_binding"]
    receipt = _opaque_tokenizer_receipt_for_test(binding)
    events: list[str] = []

    class FakeRuntime:
        def __init__(self, spec: DGXFreshSpec) -> None:
            self.command = lambda argv: b""
            self._protocol = protocol
            self._protocol_sha256 = protocol_sha
            self._source_commit = "a" * 40

        def _validate(self) -> None:
            events.append("validate")

    output_root = tmp_path / "output"; output_root.mkdir()
    cache_root = tmp_path / "cache"; cache_root.mkdir()
    monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("HSWM_CACHE_ROOT", str(cache_root))
    monkeypatch.setattr(g1_dgx, "DGXFreshRuntime", FakeRuntime)
    monkeypatch.setattr(g1_dgx, "offline_action_code_tokenizer_receipt", lambda **_: receipt)

    assert g1_dgx.main([
        "--protocol", str(_OPAQUE_PROTOCOL), "--model-snapshot", str(tmp_path),
        "--lock-path", str(tmp_path / "lock"), "--execution-registry", str(tmp_path / "registry"),
        "--evaluator-reveal", str(tmp_path / "reveal"), "--preflight-only",
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert events == ["validate"]
    assert result["offline_tokenizer_receipt_sha256"] == receipt["receipt_sha256"]
    assert result["ephemeral_offline_tokenizer_containers"] == 1
    assert result["network_calls"] == result["service_mutations"] == 0


def test_opaque_tokenizer_failure_precedes_fresh_runtime_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol, protocol_sha = g1_micro.load_protocol(_OPAQUE_PROTOCOL)
    events: list[str] = []

    class FakeRuntime:
        def __init__(self, spec: DGXFreshSpec) -> None:
            self.command = lambda argv: b""
            self._protocol = protocol
            self._protocol_sha256 = protocol_sha

        def _validate(self) -> None:
            events.append("validate")

        def __enter__(self) -> "FakeRuntime":
            events.append("enter")
            return self

        def __exit__(self, *_: object) -> None:
            events.append("exit")

    monkeypatch.setattr(g1_dgx, "DGXFreshRuntime", FakeRuntime)
    monkeypatch.setattr(
        g1_dgx, "offline_action_code_tokenizer_receipt",
        lambda **_: (_ for _ in ()).throw(LaunchRefused("tokenizer unavailable")),
    )
    with pytest.raises(LaunchRefused, match="tokenizer unavailable"):
        g1_dgx.run_dgx_micro(_spec(tmp_path))
    assert events == ["validate"]


def test_teardown_restores_only_after_mocked_quiescence(tmp_path: Path) -> None:
    restored: list[list[tuple[str, str]]] = []

    def command(argv: tuple[str, ...]) -> bytes:
        if argv[:3] == ("docker", "rm", "-f"):
            return b"hswm-g1-micro-001\n"
        if argv == ("docker", "ps", "-q"):
            return b""
        if argv[0] == "nvidia-smi":
            return b""
        if argv[:2] == ("sudo", "-n"):
            return b""
        raise AssertionError(argv)

    runtime = DGXFreshRuntime(
        _spec(tmp_path),
        command=command,
        stop_services=lambda stopped: stopped,
        restore_services=lambda stopped: restored.append(stopped),
    )
    runtime._started = True
    runtime._stopped = [("vllm", "f" * 64)]
    runtime.close()

    assert restored == [[("vllm", "f" * 64)]]


def test_unsafe_teardown_does_not_restore_services(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    restored: list[list[tuple[str, str]]] = []
    runtime = DGXFreshRuntime(
        _spec(tmp_path),
        command=lambda argv: b"",
        stop_services=lambda stopped: stopped,
        restore_services=lambda stopped: restored.append(stopped),
    )
    runtime._stopped = [("vllm", "f" * 64)]
    monkeypatch.setattr(runtime, "_quiescent", lambda: False)
    monkeypatch.setattr("hswm.experiments.g1_micro_dgx.time.sleep", lambda _: None)
    times = iter((0.0, 61.0))
    monkeypatch.setattr(
        "hswm.experiments.g1_micro_dgx.time.monotonic", lambda: next(times)
    )

    with pytest.raises(LaunchRefused, match="left stopped"):
        runtime.close()

    assert restored == []
