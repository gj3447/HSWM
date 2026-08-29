from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from dataclasses import replace

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dgx_mi2 import protocol
from _research.dgx_mi2.experiment import _preflight_services, main, make_specs, run_experiment
import _research.dgx_mi2.experiment as experiment
from _research.dgx_mi2.launcher import Mi2LeaseSpec
from _research.dgx_mi2.runner import COMPLETE, INCOMPLETE, Mi2LogprobUnavailable, Mi2Observation, Mi2Runner, _strict, _trace
from _research.dgx_mi2.protocol import Mi2Refusal
import _research.dgx_mi2.runner as runner_module
from _research.dgx_mi2.preregistration import build_mi2_preregistration, freeze_mi2_preregistration
from tests.test_dgx_mi2_preregistration import _inputs

class Lease:
    seen: list[int] = []
    def __init__(self, spec: Mi2LeaseSpec) -> None: self.spec=spec
    def __enter__(self) -> "Lease": self.seen.append(self.spec.launch_index); return self
    def __exit__(self,*_: object) -> None: pass
    def attest(self,phase: str,completed: int) -> bytes:
        key=sha256(f"{self.spec.launch_index}:{phase}".encode()).hexdigest()
        return canonical_bytes({"server_identity":{"container_id_sha256":key,"container_start_sha256":sha256((key+"s").encode()).hexdigest(),"cgroup_sha256":"3"*64,"network_namespace_sha256":"4"*64,"server_argv_sha256":"5"*64}})
    @property
    def teardown_attestation(self) -> tuple[bytes, bytes]:
        raw=b"GPU-TEST, 30, 100.0, 1000, P0\n"
        return canonical_bytes({"pair_id":self.spec.pair_id,"launch_index":self.spec.launch_index,"arm":self.spec.arm}),raw

def quiescence() -> tuple[bytes, bytes]:
    raw=b"GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5, 30, 100.0, 1000, P0\n"
    return canonical_bytes({"schema_version":"hswm-dgx-mi2-global-quiescence/v1","gpu_uuid":"GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5","endpoint":"http://127.0.0.1:18080/v1/chat/completions","observed_at_utc":"2026-08-29T00:00:00Z","gpu_observation":{"sha256":sha256(raw).hexdigest(),"byte_length":len(raw),"validated_projection":{"line_count":1,"columns_per_line":5}},"quiescence":{"docker_containers":0,"gpu_compute_apps":0,"target_listener_present":False},"terminal":"PRE_BURN_SHARED_DGX_QUIESCENCE_NOT_NO_INTERFERENCE_PROOF"}),raw

def envelope(content: str) -> bytes:
    def row(token: str,data: bytes) -> dict[str,object]:
        tops=[{"token":token,"bytes":list(data),"logprob":"-0.1"}]+[{"token":f"x{i}","bytes":[(data[0]+i)%256],"logprob":"-2.0"} for i in range(1,20)]
        return {"token":token,"bytes":list(data),"logprob":"-0.1","top_logprobs":tops}
    rows=[row(chr(c),bytes([c])) for c in content.encode()]; rows.append(row("<|im_end|>",b"<|im_end|>"))
    return json.dumps({"model":"qwen3.6-35b-a3b","choices":[{"finish_reason":"stop","message":{"content":content},"logprobs":{"content":rows}}],"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}},separators=(",",":")).encode()

def fixture(tmp_path: Path, monkeypatch) -> tuple[dict[str,bytes],dict[int,Mi2LeaseSpec],Path]:
    monkeypatch.setitem(protocol.REGISTRY,"path",str(tmp_path/"registry")); registry=Path(protocol.REGISTRY["path"]); registry.mkdir()
    artifacts=build_mi2_preregistration(_inputs()); plan=parse_canonical(artifacts["plan.json"]); cache=tmp_path/"cache"; cache.mkdir()
    runtime={}
    for arm in protocol.ARMS:
        r=parse_canonical(artifacts[f"identities/{arm}/runtime_identity_sha256.json"]); model=parse_canonical(artifacts[f"identities/{arm}/model_identity_sha256.json"])
        runtime[arm]={"endpoint":r["endpoint"],"image":r["container_image"],"image_id":r["image_id"],"gpu_uuid":r["gpu_uuid"],"served_model":r["served_model"],"model_revision":r["model_revision"],"max_model_len":r["max_model_len"],"gpu_memory_utilization_milli":r["gpu_memory_utilization_milli"],"model_repository":model["repository"],"snapshot_manifest_raw":artifacts[f"identities/{arm}/model_snapshot_manifest_sha256.json"]}
    specs=make_specs(plan_raw=artifacts["plan.json"],arm_runtime=runtime,cache_root=cache/"fresh",lock_path=tmp_path/"lock",model_snapshot=tmp_path/"snapshot")
    return artifacts,specs,registry

def test_runner_uses_real_freezer_plan_and_seals_all_48_slots(tmp_path: Path,monkeypatch) -> None:
    artifacts,specs,registry=fixture(tmp_path,monkeypatch); content='{"answer":"VISTA","rationale":"The public cue begins with V and the second cue describes WATER rather than VISTA exactly."}'
    Lease.seen=[]; runner=Mi2Runner(tmp_path/"evidence",freeze_artifacts=artifacts,registry=registry,specs=specs,publication_commit="a"*40,publication_tree="b"*40,publication_ci_receipt=artifacts["provenance/source_ci_receipt_sha256.json"],lease_factory=Lease,prelaunch_quiescence=quiescence,transport=lambda *_:Mi2Observation(200,envelope(content)))
    runner.execute(); rows=[parse_canonical(x) for x in (tmp_path/"evidence/mi2_ledger.jsonl").read_bytes().splitlines()]
    assert Lease.seen==list(range(1,25)) and sum(x["record_type"]=="START" for x in rows)==48
    assert sum(x["record_type"]=="LAUNCH_SEAL" for x in rows)==24 and rows[-1]["status"]==COMPLETE
    starts=[row for row in rows if row["record_type"]=="LAUNCH_START"]
    assert [(row["absolute_launch_parity"], row["prior_arm"]) for row in starts] == [
        ("ODD" if index % 2 else "EVEN", None if index == 1 else specs[index - 1].arm)
        for index in range(1, 25)
    ]
    assert parse_canonical((tmp_path/"evidence/receipt.json").read_bytes())["successful_slots"]==48

def test_slot_failure_is_inconclusive_and_service_restore_runs(tmp_path: Path,monkeypatch) -> None:
    artifacts,specs,registry=fixture(tmp_path,monkeypatch); calls=[]
    # Direct runner keeps the fixture in-memory; only a post-start response failure is inconclusive.
    runner=Mi2Runner(tmp_path/"evidence2",freeze_artifacts=artifacts,registry=registry,specs=specs,publication_commit="a"*40,publication_tree="b"*40,publication_ci_receipt=artifacts["provenance/source_ci_receipt_sha256.json"],lease_factory=Lease,prelaunch_quiescence=quiescence,transport=lambda *_:Mi2Observation(500,b"{}")); runner.execute()
    assert parse_canonical((tmp_path/"evidence2/receipt.json").read_bytes())["status"]==INCOMPLETE

def test_runner_refuses_injected_lease_identity_drift_before_root_creation(tmp_path: Path, monkeypatch) -> None:
    artifacts, specs, registry = fixture(tmp_path, monkeypatch)
    specs[1] = replace(specs[1], gpu_uuid="GPU-INJECTED-DRIFT")
    with pytest.raises(Exception, match="identity/control"):
        Mi2Runner(tmp_path/"evidence", freeze_artifacts=artifacts, registry=registry, specs=specs,
                  publication_commit="a" * 40, publication_tree="b" * 40,
                  publication_ci_receipt=artifacts["provenance/source_ci_receipt_sha256.json"], lease_factory=Lease,
                  prelaunch_quiescence=quiescence)
    assert not (tmp_path / "evidence").exists()


def test_forged_prelaunch_attestation_refuses_before_plan_burn_or_launch(tmp_path: Path, monkeypatch) -> None:
    artifacts, specs, registry = fixture(tmp_path, monkeypatch)
    Lease.seen = []
    runner = Mi2Runner(tmp_path / "evidence", freeze_artifacts=artifacts, registry=registry, specs=specs,
                       publication_commit="a" * 40, publication_tree="b" * 40,
                       publication_ci_receipt=artifacts["provenance/source_ci_receipt_sha256.json"],
                       lease_factory=Lease, prelaunch_quiescence=lambda: (b"{}", b"not-a-gpu-row"),
                       transport=lambda *_: Mi2Observation(200, b"{}"))
    with pytest.raises(Mi2Refusal, match="global quiescence"):
        runner.execute()
    assert Lease.seen == [] and list(registry.iterdir()) == []


def test_selected_token_logprob_must_equal_selected_top_logprob() -> None:
    content = '{"answer":"VISTA","rationale":"The public cue begins with V and the second cue describes WATER rather than VISTA exactly."}'
    value = json.loads(envelope(content))
    value["choices"][0]["logprobs"]["content"][0]["top_logprobs"][0]["logprob"] = "-0.2"
    with pytest.raises(Mi2LogprobUnavailable):
        _trace(_strict(json.dumps(value, separators=(",", ":")).encode()), content.encode())


def test_logprob_lexemes_must_be_serialized_strings() -> None:
    content = '{"answer":"VISTA","rationale":"The public cue begins with V and the second cue describes WATER rather than VISTA exactly."}'
    value = json.loads(envelope(content))
    value["choices"][0]["logprobs"]["content"][0]["logprob"] = -1
    value["choices"][0]["logprobs"]["content"][0]["top_logprobs"][0]["logprob"] = -1
    with pytest.raises(Mi2LogprobUnavailable):
        _trace(_strict(json.dumps(value, separators=(",", ":")).encode()), content.encode())


def test_partial_container_stop_restores_the_full_pre_stop_snapshot(monkeypatch) -> None:
    identifiers = {"vllm-receiver": "a" * 64, "vllm": "b" * 64}
    running = {name: True for name in identifiers}
    calls: list[tuple[str, ...]] = []
    def docker(*args: str) -> bytes:
        calls.append(args)
        if args[0] == "ps":
            return ("\n".join(name for name in experiment._SHARED_CONTAINERS if running.get(name)) + "\n").encode()
        if args[0] == "inspect":
            name = args[-1]
            return f"{identifiers[name]}\t{str(running[name]).lower()}\tfalse\n".encode()
        if args[0] == "stop":
            name = next(key for key, value in identifiers.items() if value == args[-1])
            running[name] = False
            if name == "vllm":
                raise RuntimeError("stop reported failure after state change")
            return b""
        if args[0] == "start":
            name = next(key for key, value in identifiers.items() if value == args[-1])
            running[name] = True
            return b""
        raise AssertionError(args)
    monkeypatch.setattr(experiment, "_docker", docker)
    stopped: list[tuple[str, str]] = []
    with pytest.raises(RuntimeError, match="state change"):
        experiment._stop_services(stopped)
    assert stopped == [("vllm-receiver", "a" * 64), ("vllm", "b" * 64)]
    assert running == {name: True for name in identifiers}
    assert {args[-1] for args in calls if args[0] == "start"} == set(identifiers.values())


def test_unknown_active_container_refuses_before_any_stop(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    def docker(*args: str) -> bytes:
        calls.append(args)
        if args[0] == "ps":
            return b"unknown-workload\n"
        raise AssertionError(args)
    monkeypatch.setattr(experiment, "_docker", docker)
    with pytest.raises(RuntimeError, match="unknown or ambiguous"):
        experiment._stop_services([])
    assert calls == [("ps", "--format", "{{.Names}}")]


def test_auto_remove_shared_container_refuses_before_any_stop(monkeypatch) -> None:
    identifier = "a" * 64
    calls: list[tuple[str, ...]] = []
    def docker(*args: str) -> bytes:
        calls.append(args)
        if args[0] == "ps":
            return b"vllm\n"
        if args[0] == "inspect":
            return f"{identifier}\ttrue\ttrue\n".encode()
        raise AssertionError(args)
    monkeypatch.setattr(experiment, "_docker", docker)
    with pytest.raises(RuntimeError, match="snapshot drifted"):
        experiment._stop_services([])
    assert not any(args[0] == "stop" for args in calls)


def test_restore_skips_start_for_exact_container_already_running(monkeypatch) -> None:
    identifier = "a" * 64
    calls: list[tuple[str, ...]] = []
    def docker(*args: str) -> bytes:
        calls.append(args)
        if args[0] == "inspect":
            return f"{identifier}\ttrue\tfalse\n".encode()
        raise AssertionError(args)
    monkeypatch.setattr(experiment, "_docker", docker)
    experiment._restore_services([("vllm", identifier)])
    assert not any(args[0] == "start" for args in calls)


def test_postrun_quiescence_failure_keeps_shared_services_stopped(tmp_path: Path, monkeypatch) -> None:
    _, specs, registry = fixture(tmp_path, monkeypatch)
    events: list[str] = []
    class FakeRunner:
        def __init__(self, root: Path, **_: object) -> None: self.root = root
        def execute(self, **_: object) -> None:
            self.root.mkdir()
            (self.root / "receipt.json").write_bytes(canonical_bytes({"status": "SEALED"}))
        def release_exclusive_lock(self) -> None: return None
    monkeypatch.setattr(experiment, "Mi2Runner", FakeRunner)
    def failed_postrun() -> tuple[bytes, bytes]:
        events.append("postrun")
        raise RuntimeError("surviving GPU process")
    with pytest.raises(RuntimeError, match="shared services were left stopped"):
        run_experiment(evidence_root=tmp_path / "evidence", freeze_root=tmp_path / "freeze", registry=registry,
                       specs=specs, publication_commit="a" * 40, publication_tree="b" * 40,
                       publication_ci_receipt=b"unused", stop_shared_services=lambda: events.append("stop"),
                       restore_shared_services=lambda: events.append("restore"), postrun_quiescence=failed_postrun)
    assert events == ["stop", "postrun"]


def test_study_wide_lock_rejects_a_second_runner_before_global_quiescence(tmp_path: Path, monkeypatch) -> None:
    artifacts, specs, registry = fixture(tmp_path, monkeypatch)
    first = Mi2Runner(tmp_path / "evidence-a", freeze_artifacts=artifacts, registry=registry, specs=specs,
                      publication_commit="a" * 40, publication_tree="b" * 40,
                      publication_ci_receipt=artifacts["provenance/source_ci_receipt_sha256.json"],
                      lease_factory=Lease, prelaunch_quiescence=quiescence)
    second = Mi2Runner(tmp_path / "evidence-b", freeze_artifacts=artifacts, registry=registry, specs=specs,
                       publication_commit="a" * 40, publication_tree="b" * 40,
                       publication_ci_receipt=artifacts["provenance/source_ci_receipt_sha256.json"],
                       lease_factory=Lease, prelaunch_quiescence=quiescence)
    first._acquire_exclusive_lock()
    try:
        with pytest.raises(BlockingIOError):
            second._acquire_exclusive_lock()
    finally:
        first.release_exclusive_lock()


def test_seal_io_failure_preserves_burn_and_blocks_any_resume(tmp_path: Path, monkeypatch) -> None:
    artifacts, specs, registry = fixture(tmp_path, monkeypatch)
    original_append = runner_module._append
    def fail_run_seal(root: Path, core: dict[str, object]) -> dict[str, object]:
        if core.get("record_type") == "RUN_SEAL":
            raise OSError("simulated durable-storage failure")
        return original_append(root, core)
    monkeypatch.setattr(runner_module, "_append", fail_run_seal)
    root = tmp_path / "evidence"
    runner = Mi2Runner(root, freeze_artifacts=artifacts, registry=registry, specs=specs,
                       publication_commit="a" * 40, publication_tree="b" * 40,
                       publication_ci_receipt=artifacts["provenance/source_ci_receipt_sha256.json"],
                       lease_factory=Lease, prelaunch_quiescence=quiescence,
                       transport=lambda *_: Mi2Observation(500, b"{}"))
    with pytest.raises(OSError, match="durable-storage"):
        runner.execute()
    assert list(registry.glob("*.consumed")) and (root / "mi2_ledger.jsonl").read_bytes()
    assert not (root / "receipt.json").exists()
    with pytest.raises(Mi2Refusal, match="root/specs"):
        Mi2Runner(root, freeze_artifacts=artifacts, registry=registry, specs=specs,
                  publication_commit="a" * 40, publication_tree="b" * 40,
                  publication_ci_receipt=artifacts["provenance/source_ci_receipt_sha256.json"],
                  lease_factory=Lease, prelaunch_quiescence=quiescence)

def test_cli_preflight_is_read_only(tmp_path: Path, monkeypatch) -> None:
    registry = tmp_path / "registry"; registry.mkdir()
    monkeypatch.setitem(protocol.REGISTRY, "path", str(registry))
    freeze = tmp_path / "freeze"; artifacts = freeze_mi2_preregistration(freeze, _inputs())
    ci = tmp_path / "publication-ci.json"; ci.write_bytes(artifacts["provenance/source_ci_receipt_sha256.json"])
    snapshot = tmp_path / "snapshot"; snapshot.mkdir()
    output_base = tmp_path / "output"; output_base.mkdir()
    cache_base = tmp_path / "cache"; cache_base.mkdir()
    monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(output_base)); monkeypatch.setenv("HSWM_CACHE_ROOT", str(cache_base))
    monkeypatch.setattr("_research.dgx_mi2.experiment._preflight_services", lambda: None)
    monkeypatch.setattr("_research.dgx_mi2.experiment._local_identity_preflight", lambda *args: None)
    assert main(["--freeze-dir", str(freeze), "--registry", str(registry), "--publication-commit", "a" * 40,
                 "--publication-tree", "b" * 40, "--publication-ci-receipt", str(ci), "--model-snapshot", str(snapshot),
                 "--lock-path", str(tmp_path / "lock"), "--preflight-only"]) == 0
    assert not (output_base / "mi2_evidence").exists() and not (cache_base / "mi2-launch-crossed").exists()

def test_known_docker_services_are_a_read_only_preflight_snapshot(monkeypatch) -> None:
    identifier = "a" * 64
    def docker(*args: str) -> bytes:
        if args[0] == "ps":
            return b"vllm\n"
        if args[0] == "inspect":
            return f"{identifier}\ttrue\tfalse\n".encode()
        raise AssertionError(args)
    monkeypatch.setattr(experiment, "_docker", docker)
    _preflight_services()
