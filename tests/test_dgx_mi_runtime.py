from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
from dataclasses import replace
import pytest

from _research.dnrd5.canonical_json import canonical_bytes, parse_canonical
from _research.dgx_mi import launcher
from _research.dgx_mi.launcher import MiLease, MiLeaseSpec
from _research.dgx_q1.live_launcher import LaunchRefused
from _research.dgx_mi.experiment import load_checked_in_freeze
from _research.dgx_mi.runner import MiObservation, MiRunner
from tests.test_dgx_mi_preregistration import _inputs
from _research.dgx_mi.preregistration import build_mi_preregistration, freeze_mi_preregistration
from _research.dgx_mi.protocol import BLOCKS


class FakeLease:
    seen: list[tuple[str, str]] = []
    def __init__(self, spec: MiLeaseSpec) -> None: self.spec = spec
    def __enter__(self) -> "FakeLease": self.seen.append((self.spec.arm, self.spec.block_id)); return self
    def __exit__(self, *_: object) -> None: pass
    def attest(self, phase: str, completed: int) -> bytes:
        tag=sha256((self.spec.arm+self.spec.block_id).encode()).hexdigest()
        identity={"container_id_sha256":tag,"container_start_sha256":sha256((tag+"start").encode()).hexdigest(),"cgroup_sha256":"3"*64,"network_namespace_sha256":"4"*64,"server_argv_sha256":"5"*64}
        return canonical_bytes({"phase": phase, "completed": completed, "arm": self.spec.arm, "block": self.spec.block_id, "server_identity":identity})


def _specs(root: Path) -> dict[tuple[str, str], MiLeaseSpec]:
    result = {}
    for n, (arm, block) in enumerate(BLOCKS, 1):
        model = root / f"model-{n}" / "snapshots" / ("a" * 40)
        model.mkdir(parents=True, exist_ok=True)
        hf, compile = root / f"hf-{n}", root / f"compile-{n}"; hf.mkdir(exist_ok=True); compile.mkdir(exist_ok=True)
        result[(arm, block)] = MiLeaseSpec(arm=arm, block_id=block, endpoint="http://127.0.0.1:18080/v1/chat/completions",
            container_name=f"mi-test-{n}", lock_path=root / "lock", model_snapshot=model, hf_cache=hf, compile_cache=compile,
            image="vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089", image_id="sha256:30a38a1d74a17365eca400e83ffd885b250e0c8c0d3c5b508afa8c412d2ddf95", gpu_uuid="GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5", served_model="qwen3.6-35b-a3b",
            model_revision="95a723d08a9490559dae23d0cff1d9466213d989", max_model_len=32768, gpu_memory_utilization_milli=500,
            async_scheduling=arm == "ASYNC_ENABLED", model_repository="Qwen/Qwen3.6-35B-A3B-FP8",
            snapshot_manifest_raw=(Path(__file__).parents[1] / "_research/dgx_q1/preregistrations/hswm-dnrd5-dgx-live-q1-v3-2026-08-29/identities/model_snapshot_manifest_sha256.json").read_bytes())
    return result


def test_checked_in_freeze_loader_returns_validated_closure_for_runner_handoff(
    tmp_path: Path,
) -> None:
    freeze = tmp_path / "freeze"
    artifacts = freeze_mi_preregistration(freeze, _inputs())

    files, plan = load_checked_in_freeze(freeze)

    closure = parse_canonical(artifacts["closure_manifest.json"])
    declared = {row["path"] for row in closure["artifacts"]}
    assert files["closure_manifest.json"] == artifacts["closure_manifest.json"]
    assert set(files) == declared | {"closure_manifest.json"}
    assert plan["budget"] == 16


def test_checked_in_freeze_loader_refuses_undeclared_file_before_handoff(
    tmp_path: Path,
) -> None:
    freeze = tmp_path / "freeze"
    freeze_mi_preregistration(freeze, _inputs())
    (freeze / "undeclared.json").write_bytes(b"{}")

    with pytest.raises(ValueError, match="filesystem closure"):
        load_checked_in_freeze(freeze)


@pytest.mark.parametrize("change", ("namespace", "duplicate"))
def test_checked_in_freeze_loader_refuses_closure_identity_drift_before_handoff(
    tmp_path: Path, change: str,
) -> None:
    freeze = tmp_path / "freeze"
    freeze_mi_preregistration(freeze, _inputs())
    closure_path = freeze / "closure_manifest.json"
    closure = parse_canonical(closure_path.read_bytes())
    if change == "namespace":
        closure["namespace"] = "DNRD5-QCASE024-MECHANISM-ISOLATION-ONLY/v1"
        expected = "closure drifted"
    else:
        closure["artifacts"].append(dict(closure["artifacts"][0]))
        expected = "path duplicated"
    closure_path.write_bytes(canonical_bytes(closure))

    with pytest.raises(ValueError, match=expected):
        load_checked_in_freeze(freeze)


def test_lease_readiness_does_not_retry_identity_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lease = MiLease(_specs(tmp_path)[("ASYNC_ENABLED", "B01")])
    closed = False

    monkeypatch.setattr(lease, "_validate", lambda: None)
    monkeypatch.setattr(lease, "_before", lambda: None)
    monkeypatch.setattr(lease, "_launch", lambda: None)

    def refuse_identity(_: str, __: int) -> bytes:
        raise LaunchRefused("identity drift")

    def close() -> None:
        nonlocal closed
        closed = True
        if lease._lock is not None:
            os.close(lease._lock)
            lease._lock = None

    monkeypatch.setattr(lease, "attest", refuse_identity)
    monkeypatch.setattr(lease, "close", close)
    monkeypatch.setattr(
        launcher.time,
        "sleep",
        lambda _: (_ for _ in ()).throw(AssertionError("identity failure retried")),
    )

    with pytest.raises(LaunchRefused, match="identity drift"):
        lease.__enter__()
    assert closed


def test_runner_burns_once_and_seals_exact_abba_sixteen_slots(tmp_path: Path) -> None:
    artifacts = build_mi_preregistration(_inputs())
    registry = tmp_path / "registry"; registry.mkdir()
    raw = b'{"model":"qwen3.6-35b-a3b","choices":[{"finish_reason":"stop","message":{"content":"{\\"answer\\":\\"VISTA\\",\\"rationale\\":\\"The public cue begins with V, matching VISTA exactly. The other cue describes WATER and is not the selected label.\\"}"},"logprobs":{"content":[{"token":"{","logprob":-0.1,"top_logprobs":[{"token":"{","logprob":-0.1}]}]}}],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}'
    def transport(_: str, __: bytes) -> MiObservation: return MiObservation(200, raw, "application/json", "fake")
    identities = {arm:{name: artifacts[f"identities/{arm}/{name}.json"] for name in ("endpoint_sha256","model_identity_sha256","runtime_identity_sha256","tls_identity_sha256","declared_isolation_contract_sha256","model_snapshot_manifest_sha256")} for arm in ("ASYNC_ENABLED","ASYNC_DISABLED")}
    provenance = {"source_ci_receipt_sha256":artifacts["provenance/source_ci_receipt_sha256.json"],"verifier_ci_receipt_sha256":artifacts["provenance/verifier_ci_receipt_sha256.json"],"verifier_build_output_sha256":artifacts["provenance/verifier_build_output_sha256.json"]}
    FakeLease.seen=[]
    runner=MiRunner(tmp_path / "evidence", plan_raw=artifacts["plan.json"], marker_raw=artifacts["start_marker.json"], closure_raw=artifacts["closure_manifest.json"], genesis_raw=artifacts["root_genesis.json"], material_raw=artifacts["material_provenance.json"], request_raw=artifacts["request.json"], schema_raw=artifacts["materials/QCASE-024/response_schema.json"], identities=identities, provenance=provenance, consumption_root=registry, specs=_specs(tmp_path), publication_commit="a"*40, publication_tree="b"*40, publication_ci_receipt=provenance["source_ci_receipt_sha256"], lease_factory=FakeLease, transport=transport)
    runner.execute()
    rows=[parse_canonical(x) for x in (tmp_path / "evidence/mi_ledger.jsonl").read_bytes().splitlines()]
    assert FakeLease.seen == list(BLOCKS)
    assert sum(row["record_type"] == "START" for row in rows) == 16
    assert sum(row["record_type"] == "TERMINAL" and row["outcome"] == "SUCCEEDED" for row in rows) == 16
    assert [row["record_type"] for row in rows].count("BLOCK_SEAL") == 0
    assert rows[-1]["record_type"] == "RUN_SEAL" and rows[-1]["successful_slots"] == 16
    assert len(rows[-1]["blocks"]) == 4
    assert (registry / (sha256(artifacts["plan.json"]).hexdigest() + ".consumed")).is_file()


def test_direct_runner_rejects_request_or_frozen_spec_drift(tmp_path: Path) -> None:
    from _research.dgx_mi.protocol import MiRefusal
    artifacts=build_mi_preregistration(_inputs()); registry=tmp_path/"registry"; registry.mkdir()
    identities={arm:{name:artifacts[f"identities/{arm}/{name}.json"] for name in ("endpoint_sha256","model_identity_sha256","runtime_identity_sha256","tls_identity_sha256","declared_isolation_contract_sha256","model_snapshot_manifest_sha256")} for arm in ("ASYNC_ENABLED","ASYNC_DISABLED")}
    provenance={"source_ci_receipt_sha256":artifacts["provenance/source_ci_receipt_sha256.json"],"verifier_ci_receipt_sha256":artifacts["provenance/verifier_ci_receipt_sha256.json"],"verifier_build_output_sha256":artifacts["provenance/verifier_build_output_sha256.json"]}
    common=dict(plan_raw=artifacts["plan.json"],marker_raw=artifacts["start_marker.json"],closure_raw=artifacts["closure_manifest.json"],genesis_raw=artifacts["root_genesis.json"],material_raw=artifacts["material_provenance.json"],schema_raw=artifacts["materials/QCASE-024/response_schema.json"],identities=identities,provenance=provenance,consumption_root=registry,specs=_specs(tmp_path),publication_commit="a"*40,publication_tree="b"*40,publication_ci_receipt=provenance["source_ci_receipt_sha256"])
    with pytest.raises(MiRefusal): MiRunner(tmp_path/"bad-request",request_raw=b"{}",**common)
    specs=_specs(tmp_path); changed=specs[("ASYNC_ENABLED","B01")]
    specs[("ASYNC_ENABLED","B01")]=replace(changed,endpoint="http://127.0.0.1:18081/v1/chat/completions")
    with pytest.raises(MiRefusal): MiRunner(tmp_path/"bad-spec",request_raw=artifacts["request.json"],**{**common,"specs":specs})
