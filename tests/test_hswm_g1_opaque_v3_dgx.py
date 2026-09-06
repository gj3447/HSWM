"""The opaque v3 (G0-local) protocol through the fresh-DGX lease and the freeze tool.

These are structural checks with fake Docker/HTTP commands.  They prove that
the dated v3 preregistration path is accepted, that the v2 launcher lifecycle
is reused unchanged for v3, that the freeze tool measures and freezes without
any POST or registry claim, and that the reveal rebinding keeps the episode
commitments intact.  No model is called and no scientific status changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hswm.experiments import g1_micro, g1_opaque_v3
from hswm.experiments import g1_micro_dgx as g1_dgx
from hswm.experiments import g1_opaque_evaluator_process as evaluator_process
from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256
from scripts import freeze_hswm_g1_opaque_v3 as freeze_tool
from tests.test_hswm_g1_opaque_v3 import _generate


V3_PATH = "_research/causal_composition/preregistrations/g1_opaque_identifiability_v3_2026-09-15/protocol.v1.json"


def _fake_tokenizer_command(token_count: int = 3):
    def command(argv: tuple[str, ...]) -> bytes:
        assert argv[:2] == ("docker", "run") and "--network" in argv and argv[argv.index("--network") + 1] == "none"
        payload = json.loads(argv[-2])
        rows = [
            {"episode_uid": episode["episode_uid"], "token_ids": [[1] * token_count, [2] * token_count]}
            for episode in payload["episodes"]
        ]
        return json.dumps({"transformers_version": "4.57.0", "tokenizers_version": "0.22.0", "episodes": rows}).encode()
    return command


def _write_protocol(tmp_path: Path, protocol: dict[str, Any]) -> Path:
    path = tmp_path / V3_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    return path


def test_dated_v3_path_is_canonical_and_tracks_the_runtime_sources() -> None:
    assert g1_micro.is_dgx_protocol_path(V3_PATH)
    assert not g1_micro.is_dgx_protocol_path(V3_PATH.replace("v3_", "v4_"))
    assert not g1_micro.is_dgx_protocol_path("_research/causal_composition/preregistrations/g1_opaque_identifiability_v3_DRAFT/protocol.v1.json")
    tracked = g1_micro.dgx_tracked_source_paths_for_protocol_path(V3_PATH)
    assert tracked[0] == V3_PATH and tracked[1:] == g1_micro.DGX_TRACKED_SOURCE_PATHS[1:]
    with pytest.raises(g1_micro.G1MicroError):
        g1_micro.dgx_tracked_source_paths_for_protocol_path(V3_PATH.replace("2026-09-15", "DRAFT"))


def test_generic_loader_and_server_argv_accept_the_v3_protocol(tmp_path: Path) -> None:
    protocol, sha, _, _, _ = _generate(tmp_path)
    path = _write_protocol(tmp_path, protocol)
    loaded, loaded_sha = g1_micro.load_protocol(path)
    assert loaded_sha == sha == canonical_sha256(loaded)
    assert g1_micro.expected_completion_posts(loaded) == 320
    assert g1_micro.expected_dgx_server_argv(loaded)[:2] == ["--model", f"/model-repository/snapshots/{loaded['live_binding']['model_revision']}"]
    assert g1_micro.dgx_tracked_source_paths(loaded)[0] == V3_PATH


def test_freeze_tool_measures_offline_then_freezes_and_rebinds_the_reveal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    protocol, draft_sha, reveal, reveal_path, _ = _generate(tmp_path)
    path = _write_protocol(tmp_path, protocol)
    snapshot = tmp_path / "hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots" / protocol["live_binding"]["model_revision"]
    snapshot.mkdir(parents=True)
    assert freeze_tool.main(["measure", "--protocol", str(path), "--model-snapshot", str(snapshot), "--frozen-on", "2026-09-15"], command=_fake_tokenizer_command()) == 0
    report = json.loads(capsys.readouterr().out)
    frozen, frozen_sha = g1_opaque_v3.load_v3_protocol(path)
    assert report["draft_canonical_sha256"] == draft_sha and report["frozen_canonical_sha256"] == frozen_sha != draft_sha
    assert frozen["freeze"]["status"] == "FROZEN" and frozen["tokenizer_binding"]["status"] == "MEASURED"
    assert len(frozen["tokenizer_binding"]["episodes"]) == 32
    assert frozen["evaluator_reveal_contract"] == protocol["evaluator_reveal_contract"]
    assert [item["evaluator_commitment_sha256"] for item in frozen["episodes"]] == [item["evaluator_commitment_sha256"] for item in protocol["episodes"]]
    # A second freeze is refused; unequal token counts are refused before any write.
    with pytest.raises(SystemExit):
        freeze_tool.main(["measure", "--protocol", str(path), "--model-snapshot", str(snapshot), "--frozen-on", "2026-09-15"], command=_fake_tokenizer_command())
    draft_again = _write_protocol(tmp_path / "again", protocol)

    def unequal(argv: tuple[str, ...]) -> bytes:
        payload = json.loads(argv[-2])
        rows = [{"episode_uid": e["episode_uid"], "token_ids": [[1, 1], [2]]} for e in payload["episodes"]]
        return json.dumps({"transformers_version": "x", "tokenizers_version": "y", "episodes": rows}).encode()

    with pytest.raises(g1_dgx.LaunchRefused):
        freeze_tool.main(["measure", "--protocol", str(draft_again), "--model-snapshot", str(snapshot), "--frozen-on", "2026-09-15"], command=unequal)
    assert g1_opaque_v3.load_v3_protocol(draft_again)[0]["freeze"]["status"] == "DRAFT_NOT_FROZEN"
    # The reveal still names the draft digest until the evaluator user rebinds it.
    assert reveal["protocol_canonical_sha256"] == draft_sha
    assert freeze_tool.main(["rebind-reveal", "--reveal", str(reveal_path), "--protocol", str(path)]) == 0
    rebound = evaluator_process.load_reveal(reveal_path)
    assert rebound["protocol_canonical_sha256"] == frozen_sha
    assert rebound["reveal_commitment_root"] == frozen["evaluator_reveal_contract"]["reveal_commitment_root"]
    assert {key: value for key, value in rebound.items() if key != "protocol_canonical_sha256"} == {key: value for key, value in reveal.items() if key != "protocol_canonical_sha256"}
    # The launcher's pre-mutation tokenizer step re-measures and accepts the frozen binding.
    receipt = g1_dgx.offline_action_code_tokenizer_receipt(command=_fake_tokenizer_command(), snapshot=snapshot, tokenizer_binding=frozen["tokenizer_binding"])
    g1_dgx._validate_opaque_tokenizer_receipt(receipt, frozen["tokenizer_binding"])
    with pytest.raises(g1_dgx.LaunchRefused):
        g1_dgx._validate_opaque_tokenizer_receipt(
            g1_dgx.offline_action_code_tokenizer_receipt(command=_fake_tokenizer_command(4), snapshot=snapshot, tokenizer_binding=frozen["tokenizer_binding"]),
            frozen["tokenizer_binding"],
        )


def test_v3_lease_writes_the_binding_before_the_instrument_and_refuses_unmeasured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    protocol, sha, _, _, _ = _generate(tmp_path)
    path = _write_protocol(tmp_path, protocol)
    snapshot = tmp_path / "hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots" / protocol["live_binding"]["model_revision"]
    snapshot.mkdir(parents=True)
    output_root = tmp_path / "wrapper"; output_root.mkdir()
    spec = g1_dgx.DGXFreshSpec(
        repo_root=tmp_path, protocol_path=path, output_dir=output_root / "g1_opaque_v3",
        runtime_binding_path=output_root / "g1_opaque_v3_runtime_binding.json",
        execution_registry=tmp_path / "durable" / "v3-once", lock_path=tmp_path / "lock",
        container_name="hswm-g1-micro-001", model_snapshot=snapshot,
        hf_cache=tmp_path / "hf", compile_cache=tmp_path / "compile",
    )
    events: list[str] = []
    binding_record = {"payload": {"stub": True}, "record_sha256": "0" * 64}

    class FakeRuntime:
        def __init__(self, spec: g1_dgx.DGXFreshSpec, **_: Any) -> None:
            self.command = _fake_tokenizer_command()
            self._protocol, self._protocol_sha256 = g1_opaque_v3.load_v3_protocol(spec.protocol_path)
            self._source_commit = "a" * 40
            self._stopped: list[tuple[str, str]] = []
            self.runtime_binding = binding_record
            self.teardown_observation = None

        def _validate(self) -> None:
            events.append("validate")

        def __enter__(self) -> "FakeRuntime":
            events.append("enter")
            return self

        def __exit__(self, *_: object) -> None:
            events.append("exit")

    monkeypatch.setattr(g1_dgx, "DGXFreshRuntime", FakeRuntime)
    options = g1_dgx.DGXOpaqueV3Options(
        evaluator=evaluator_process.EvaluatorEndpoint(argv_prefix=("python",), reveal_path="/private/reveal", ledger_path="/private/ledger"),
        permit_commit=None, reveal_after_seal=tmp_path / "reveal-after-seal.json",
    )
    # Unmeasured (draft) protocol: refused before the lease is entered.
    with pytest.raises(g1_dgx.LaunchRefused, match="not measured"):
        g1_dgx.run_dgx_v3(spec, options)
    assert events == ["validate"]
    events.clear()
    # Frozen protocol but no Permit process: refused before the lease is entered.
    assert freeze_tool.main(["measure", "--protocol", str(path), "--model-snapshot", str(snapshot), "--frozen-on", "2026-09-15"], command=_fake_tokenizer_command()) == 0
    with pytest.raises(g1_dgx.LaunchRefused, match="Permit commit process"):
        g1_dgx.run_dgx_v3(spec, options)
    assert events == ["validate"]
    events.clear()
    # With a Permit process the lease is entered, the binding is written, then the instrument runs.
    seen: dict[str, Any] = {}

    def fake_live(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        events.append("instrument")
        assert Path(kwargs["runtime_binding_path"]).read_bytes() == canonical_json_bytes(binding_record)
        raise g1_micro.G1MicroError("stop here: the instrument itself is covered by test_hswm_g1_opaque_v3")

    monkeypatch.setattr(g1_opaque_v3, "run_v3_live", fake_live)
    from hswm.experiments import atom_v2_permit_bridge as bridge

    script = tmp_path / "process.js"
    script.write_text("// stand-in for the built Permit commit process; never executed here\n")
    with_permit = g1_dgx.DGXOpaqueV3Options(
        evaluator=options.evaluator, permit_commit=bridge.LocalPermitCommitProcess(runtime="/usr/bin/node", script=str(script)),
        reveal_after_seal=options.reveal_after_seal,
    )
    with pytest.raises(g1_micro.G1MicroError, match="stop here"):
        g1_dgx.run_dgx_v3(spec, with_permit)
    assert events == ["validate", "enter", "instrument", "exit"]
    assert seen["endpoint"] == "http://127.0.0.1:18080" and seen["model"] == protocol["live_binding"]["served_model"]
    assert seen["expected_max_model_len"] == protocol["live_binding"]["expected_max_model_len"]
    assert seen["execution_registry_path"] == spec.execution_registry and seen["reveal_path_after_seal"] == options.reveal_after_seal
