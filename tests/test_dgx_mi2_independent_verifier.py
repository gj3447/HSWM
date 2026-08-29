"""Producer-evidence and adversarial tests for the independent MI-2 reader."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import pytest

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical
from _research.dgx_mi2 import protocol
from _research.dgx_mi2.experiment import make_specs
from _research.dgx_mi2.launcher import Mi2LeaseSpec
from _research.dgx_mi2.preregistration import build_mi2_preregistration, build_verifier_source_manifest
from _research.dgx_mi2.runner import Mi2Observation, Mi2Runner
from _research.dgx_mi2.independent_verifier import COMPLETE, NO_ASSOCIATION, VOID, main, verify
import _research.dgx_mi2.independent_verifier as independent_verifier
from tests.test_dgx_mi2_preregistration import _inputs


PREFIX = b'{\n  "answer": "VISTA",\n  "rationale": "The first cue'
REMAINDER = b' indicates VISTA because the public cue begins with V and the other cue is a different public word in this controlled response."\n}'
CONTENT = (PREFIX + REMAINDER).decode()


def _envelope() -> bytes:
    def row(token: str, data: bytes, *, branch: bool = False) -> dict[str, object]:
        top = [{"token": token, "bytes": list(data), "logprob": "-0.1"}]
        if branch:
            top.append({"token": " explicitly", "bytes": list(b" explicitly"), "logprob": "-1.1"})
        while len(top) < 20:
            index = len(top)
            top.append({"token": f"alt-{index}", "bytes": [index], "logprob": "-2.0"})
        return {"token": token, "bytes": list(data), "logprob": "-0.1", "top_logprobs": top}
    chunks = [PREFIX[index:index + 1] for index in range(19)] + [PREFIX[19:]]
    rows = [row(chunk.decode(), chunk) for chunk in chunks]
    rows.append(row(" indicates", b" indicates", branch=True))
    rows += [row(chr(value), bytes([value])) for value in REMAINDER[len(b" indicates"):]]
    rows.append(row("<|im_end|>", b"<|im_end|>"))
    return json.dumps({"model": "qwen3.6-35b-a3b", "choices": [{"finish_reason": "stop", "message": {"content": CONTENT}, "logprobs": {"content": rows}}], "usage": {"prompt_tokens": 1, "completion_tokens": len(rows), "total_tokens": len(rows) + 1}}, separators=(",", ":")).encode()


class _Lease:
    def __init__(self, spec: Mi2LeaseSpec) -> None:
        self.spec = spec
        self.argv = [*protocol.SERVER_PREFIX, "--async-scheduling" if spec.async_scheduling else "--no-async-scheduling"]
        key = sha256(str(spec.launch_index).encode()).hexdigest()
        self.identity = {"container_id_sha256": key, "container_start_sha256": sha256((key + "s").encode()).hexdigest(), "cgroup_sha256": "3" * 64, "network_namespace_sha256": "4" * 64, "server_argv_sha256": sha256("\0".join(self.argv).encode()).hexdigest()}
    def __enter__(self) -> "_Lease": return self
    def __exit__(self, *_: object) -> None: return None
    def attest(self, phase: str, completed: int) -> bytes:
        return canonical_bytes({"schema_version": "hswm-dgx-mi2-boundary/v1", "pair_id": self.spec.pair_id, "launch_index": self.spec.launch_index, "arm": self.spec.arm, "phase": phase, "completed": completed, "async_scheduling": self.spec.async_scheduling, "server_argv": self.argv, "server_argv_sha256": self.identity["server_argv_sha256"], "server_identity": self.identity, "request_success_total": completed, "raw_metrics_sha256": "6" * 64, "terminal": "FINITE_LAUNCH_BOUNDARY_NOT_NO_INTERFERENCE_PROOF"})
    @property
    def teardown_attestation(self) -> tuple[bytes, bytes]:
        raw = b"GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5, 30, 100.0, 1000, P0\n"
        return canonical_bytes({"schema_version": "hswm-dgx-mi2-launch-crossed-teardown/v1", "pair_id": self.spec.pair_id, "launch_index": self.spec.launch_index, "arm": self.spec.arm, "observed_at_utc": "2026-08-29T00:00:00Z", "gpu_observation": {"sha256": sha256(raw).hexdigest(), "byte_length": len(raw), "validated_projection": {"line_count": 1, "columns_per_line": 5}}, "quiescence": {"docker_containers": 0, "gpu_compute_apps": 0, "target_listener_present": False}, "terminal": "FINITE_TEARDOWN_NOT_NO_INTERFERENCE_PROOF"}), raw


def _evidence(tmp_path: Path, monkeypatch, *, fail_first: bool = False, fail_second: bool = False) -> Path:
    registry = tmp_path / "registry"; registry.mkdir(); monkeypatch.setitem(protocol.REGISTRY, "path", str(registry)); monkeypatch.setattr(independent_verifier, "REGISTRY", dict(protocol.REGISTRY))
    source = Path("_research/dgx_mi2/independent_verifier.py").read_bytes()
    inputs = replace(_inputs(), verifier_build=build_verifier_source_manifest(source, source_path="_research/dgx_mi2/independent_verifier.py"))
    artifacts = build_mi2_preregistration(inputs); plan = parse_canonical(artifacts["plan.json"])
    cache = tmp_path / "cache"; cache.mkdir(); runtime = {}
    for arm in protocol.ARMS:
        item = parse_canonical(artifacts[f"identities/{arm}/runtime_identity_sha256.json"])
        model = parse_canonical(artifacts[f"identities/{arm}/model_identity_sha256.json"])
        runtime[arm] = {"endpoint": item["endpoint"], "image": item["container_image"], "image_id": item["image_id"], "gpu_uuid": item["gpu_uuid"], "served_model": item["served_model"], "model_revision": item["model_revision"], "max_model_len": item["max_model_len"], "gpu_memory_utilization_milli": item["gpu_memory_utilization_milli"], "model_repository": model["repository"], "snapshot_manifest_raw": artifacts[f"identities/{arm}/model_snapshot_manifest_sha256.json"]}
    specs = make_specs(plan_raw=artifacts["plan.json"], arm_runtime=runtime, cache_root=cache / "fresh", lock_path=tmp_path / "lock", model_snapshot=tmp_path / "snapshot")
    root = tmp_path / "evidence"
    gpu = b"GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5, 30, 100.0, 1000, P0\n"
    quiescence = canonical_bytes({"schema_version": "hswm-dgx-mi2-global-quiescence/v1", "gpu_uuid": "GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5", "endpoint": "http://127.0.0.1:18080/v1/chat/completions", "observed_at_utc": "2026-08-29T00:00:00Z", "gpu_observation": {"sha256": sha256(gpu).hexdigest(), "byte_length": len(gpu), "validated_projection": {"line_count": 1, "columns_per_line": 5}}, "quiescence": {"docker_containers": 0, "gpu_compute_apps": 0, "target_listener_present": False}, "terminal": "PRE_BURN_SHARED_DGX_QUIESCENCE_NOT_NO_INTERFERENCE_PROOF"})
    calls = [0]
    def transport(*_: object) -> Mi2Observation:
        calls[0] += 1
        return Mi2Observation(500, b"{}") if fail_first or (fail_second and calls[0] == 2) else Mi2Observation(200, _envelope())
    Mi2Runner(root, freeze_artifacts=artifacts, registry=registry, specs=specs, publication_commit="a" * 40, publication_tree="b" * 40, publication_ci_receipt=artifacts["provenance/source_ci_receipt_sha256.json"], lease_factory=_Lease, transport=transport, prelaunch_quiescence=lambda: (quiescence, gpu)).execute()
    assert parse_canonical((root / "receipt.json").read_bytes())["status"] == ("INCONCLUSIVE_DGX_QCASE024_MI2_INCOMPLETE_LAUNCHES" if fail_first or fail_second else "LIVE_COMPLETE_DGX_QCASE024_MI2_RANDOMIZED_LAUNCH_EXPERIMENT")
    assert plan["budget"] == 48
    return root


def _reseal(root: Path, rows: list[dict[str, object]]) -> None:
    previous = "0" * 64
    for ordinal, row in enumerate(rows, 1):
        row["ordinal"] = ordinal
        row["previous_record_sha256"] = previous
        row.pop("record_sha256", None)
        row["record_sha256"] = canonical_sha256(row)
        previous = row["record_sha256"]
    raw = b"".join(canonical_bytes(row) + b"\n" for row in rows)
    (root / "mi2_ledger.jsonl").write_bytes(raw)
    receipt = parse_canonical((root / "receipt.json").read_bytes())
    receipt["ledger"] = {"sha256": sha256(raw).hexdigest(), "byte_length": len(raw)}
    (root / "receipt.json").write_bytes(canonical_bytes(receipt))


def test_real_producer_evidence_replays_independently(tmp_path: Path, monkeypatch) -> None:
    result = verify(_evidence(tmp_path, monkeypatch), external_registry_root=tmp_path / "registry")
    assert result["terminal"] == COMPLETE
    assert result["family_label"] == NO_ASSOCIATION
    assert result["primary_unit"] == "R001_FRESH_LAUNCH_ONLY"


def test_chain_valid_but_terminal_trace_tamper_is_void(tmp_path: Path, monkeypatch) -> None:
    root = _evidence(tmp_path, monkeypatch); ledger = root / "mi2_ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_bytes().splitlines()]
    terminal = next(row for row in rows if row["record_type"] == "TERMINAL")
    terminal["full_processed_logprob_trace"] = terminal["model_content_utf8"]
    previous = "0" * 64
    for ordinal, row in enumerate(rows, 1):
        row["ordinal"] = ordinal; row["previous_record_sha256"] = previous; row.pop("record_sha256", None)
        row["record_sha256"] = canonical_sha256(row); previous = row["record_sha256"]
    ledger.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in rows))
    assert verify(root, external_registry_root=tmp_path / "registry")["terminal"] == VOID


def test_complete_without_external_burn_registry_is_void(tmp_path: Path, monkeypatch) -> None:
    assert verify(_evidence(tmp_path, monkeypatch))["terminal"] == VOID


def test_cli_passes_the_required_external_burn_registry(tmp_path: Path, monkeypatch) -> None:
    root = _evidence(tmp_path, monkeypatch)
    output = tmp_path / "independent-result.json"
    assert main([
        "--root", str(root),
        "--external-registry-root", str(tmp_path / "registry"),
        "--output", str(output),
    ]) == 0
    result = parse_canonical(output.read_bytes())
    assert result["terminal"] == COMPLETE
    assert result["family_label"] == NO_ASSOCIATION


def test_independent_constants_match_the_registered_contract() -> None:
    assert independent_verifier.RANDOMIZATION == protocol.RANDOMIZATION_CONTRACT
    assert independent_verifier.SERVER_PREFIX == protocol.SERVER_PREFIX
    assert independent_verifier.REQUIRED_ENV == protocol.REQUIRED_ENV


def test_first_pre_boundary_requires_zero_success_baseline(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    argv = [*protocol.SERVER_PREFIX, "--async-scheduling"]
    observed = {
        "container_id_sha256": "1" * 64,
        "container_start_sha256": "2" * 64,
        "cgroup_sha256": "3" * 64,
        "network_namespace_sha256": "4" * 64,
        "server_argv_sha256": sha256("\0".join(argv).encode()).hexdigest(),
    }
    raw = canonical_bytes({
        "schema_version": "hswm-dgx-mi2-boundary/v1",
        "pair_id": "P01",
        "launch_index": 1,
        "arm": "ASYNC_ENABLED",
        "phase": "PRE",
        "completed": 0,
        "async_scheduling": True,
        "server_argv": argv,
        "server_argv_sha256": observed["server_argv_sha256"],
        "server_identity": observed,
        "request_success_total": 7,
        "raw_metrics_sha256": "6" * 64,
        "terminal": "FINITE_LAUNCH_BOUNDARY_NOT_NO_INTERFERENCE_PROOF",
    })
    digest = sha256(raw).hexdigest()
    (content / digest).write_bytes(raw)
    with pytest.raises(ValueError):
        independent_verifier._boundary(
            tmp_path,
            {"sha256": digest, "byte_length": len(raw)},
            {"pair_id": "P01", "launch_index": 1, "arm": "ASYNC_ENABLED"},
            {"async_scheduling": True, "container_name": "hswm-mi2-01", "observed": observed},
            "PRE",
            0,
            argv,
            0,
        )


def test_all_logprob_lexemes_must_be_strings() -> None:
    with pytest.raises(ValueError):
        independent_verifier._decimal(0)


def test_unreferenced_content_blob_is_void(tmp_path: Path, monkeypatch) -> None:
    root = _evidence(tmp_path, monkeypatch)
    (root / "content" / ("f" * 64)).write_bytes(b"unreferenced")
    assert verify(root, external_registry_root=tmp_path / "registry")["terminal"] == VOID


def test_resealed_run_summary_tamper_is_void(tmp_path: Path, monkeypatch) -> None:
    root = _evidence(tmp_path, monkeypatch); ledger = root / "mi2_ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_bytes().splitlines()]
    seal = rows[-1]; seal["launches"][0]["successful_slots"] = 1
    previous = "0" * 64
    for ordinal, row in enumerate(rows, 1):
        row["ordinal"] = ordinal; row["previous_record_sha256"] = previous; row.pop("record_sha256", None)
        row["record_sha256"] = canonical_sha256(row); previous = row["record_sha256"]
    raw = b"".join(canonical_bytes(row) + b"\n" for row in rows); ledger.write_bytes(raw)
    receipt = parse_canonical((root / "receipt.json").read_bytes())
    receipt["ledger"] = {"sha256": sha256(raw).hexdigest(), "byte_length": len(raw)}
    (root / "receipt.json").write_bytes(canonical_bytes(receipt))
    assert verify(root, external_registry_root=tmp_path / "registry")["terminal"] == VOID


def test_structurally_complete_incomplete_prefix_is_inconclusive(tmp_path: Path, monkeypatch) -> None:
    result = verify(_evidence(tmp_path, monkeypatch, fail_first=True))
    assert result["terminal"] == "INCONCLUSIVE_DGX_QCASE024_MI2_INCOMPLETE_LAUNCHES"


def test_resealed_malformed_incomplete_prefix_is_void(tmp_path: Path, monkeypatch) -> None:
    root = _evidence(tmp_path, monkeypatch, fail_first=True); ledger = root / "mi2_ledger.jsonl"
    rows = [json.loads(line) for line in ledger.read_bytes().splitlines()]
    next(row for row in rows if row["record_type"] == "TERMINAL")["unexpected"] = True
    previous = "0" * 64
    for ordinal, row in enumerate(rows, 1):
        row["ordinal"] = ordinal; row["previous_record_sha256"] = previous; row.pop("record_sha256", None)
        row["record_sha256"] = canonical_sha256(row); previous = row["record_sha256"]
    raw=b"".join(canonical_bytes(row)+b"\n" for row in rows); ledger.write_bytes(raw)
    receipt=parse_canonical((root/"receipt.json").read_bytes()); receipt["ledger"]={"sha256":sha256(raw).hexdigest(),"byte_length":len(raw)}; (root/"receipt.json").write_bytes(canonical_bytes(receipt))
    assert verify(root)["terminal"] == VOID


def test_resealed_wrong_partial_attempt_is_void(tmp_path: Path, monkeypatch) -> None:
    root = _evidence(tmp_path, monkeypatch, fail_first=True)
    rows = [json.loads(line) for line in (root / "mi2_ledger.jsonl").read_bytes().splitlines()]
    next(row for row in rows if row["record_type"] == "START")["attempt_id"] = "MI2-P12-D-R002"
    _reseal(root, rows)
    assert verify(root)["terminal"] == VOID


def test_resealed_partial_launch_summary_forgery_is_void(tmp_path: Path, monkeypatch) -> None:
    root = _evidence(tmp_path, monkeypatch, fail_first=True)
    rows = [json.loads(line) for line in (root / "mi2_ledger.jsonl").read_bytes().splitlines()]
    seal = next(row for row in rows if row["record_type"] == "LAUNCH_SEAL")
    seal["successful_slots"] = 1
    rows[-1]["launches"][0]["successful_slots"] = 1
    _reseal(root, rows)
    assert verify(root)["terminal"] == VOID


def test_partial_status_must_match_failure_class(tmp_path: Path, monkeypatch) -> None:
    root = _evidence(tmp_path, monkeypatch, fail_first=True)
    rows = [json.loads(line) for line in (root / "mi2_ledger.jsonl").read_bytes().splitlines()]
    rows[-1]["status"] = "INCONCLUSIVE_DGX_QCASE024_MI2_REQUIRED_CONTENT_OR_TRACE"
    _reseal(root, rows)
    receipt = parse_canonical((root / "receipt.json").read_bytes())
    receipt["status"] = rows[-1]["status"]
    (root / "receipt.json").write_bytes(canonical_bytes(receipt))
    assert verify(root)["terminal"] == VOID


@pytest.mark.parametrize("drop", ["observation", "raw_envelope"])
def test_partial_failure_stage_dependencies_are_exact(tmp_path: Path, monkeypatch, drop: str) -> None:
    root = _evidence(tmp_path, monkeypatch, fail_first=True)
    rows = [json.loads(line) for line in (root / "mi2_ledger.jsonl").read_bytes().splitlines()]
    terminal = next(row for row in rows if row["record_type"] == "TERMINAL")
    terminal[drop] = None
    _reseal(root, rows)
    assert verify(root)["terminal"] == VOID


def test_complete_record_timestamp_must_be_strict_utc_seconds(tmp_path: Path, monkeypatch) -> None:
    root = _evidence(tmp_path, monkeypatch)
    rows = [json.loads(line) for line in (root / "mi2_ledger.jsonl").read_bytes().splitlines()]
    next(row for row in rows if row["record_type"] == "LAUNCH_START")["observed_at_utc"] = "Z"
    _reseal(root, rows)
    assert verify(root, external_registry_root=tmp_path / "registry")["terminal"] == VOID


def test_partial_success_trace_tamper_is_void(tmp_path: Path, monkeypatch) -> None:
    root=_evidence(tmp_path, monkeypatch, fail_second=True); ledger=root/"mi2_ledger.jsonl"
    rows=[json.loads(line) for line in ledger.read_bytes().splitlines()]
    terminal=next(row for row in rows if row["record_type"]=="TERMINAL" and row["outcome"]=="SUCCEEDED")
    terminal["full_processed_logprob_trace"]=terminal["model_content_utf8"]
    previous="0"*64
    for ordinal,row in enumerate(rows,1):
        row["ordinal"]=ordinal; row["previous_record_sha256"]=previous; row.pop("record_sha256",None); row["record_sha256"]=canonical_sha256(row); previous=row["record_sha256"]
    raw=b"".join(canonical_bytes(row)+b"\n" for row in rows); ledger.write_bytes(raw)
    receipt=parse_canonical((root/"receipt.json").read_bytes()); receipt["ledger"]={"sha256":sha256(raw).hexdigest(),"byte_length":len(raw)}; (root/"receipt.json").write_bytes(canonical_bytes(receipt))
    assert verify(root)["terminal"]==VOID
