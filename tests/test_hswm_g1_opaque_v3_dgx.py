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


def test_code_pool_selection_takes_the_first_pair_with_equal_public_counts(tmp_path: Path) -> None:
    from tests.test_hswm_g1_opaque_v3 import SEED, _OPAQUE_SUCCESSOR_PROTOCOL

    pool = g1_opaque_v3.v3_code_pool(SEED)
    assert pool == g1_opaque_v3.v3_code_pool(SEED) and len(pool) == 32 and all(len(pairs) == 32 for pairs in pool.values())
    source = json.loads(_OPAQUE_SUCCESSOR_PROTOCOL.read_text(encoding="utf-8"))
    tokenizer_model = {key: source["tokenizer_binding"][key] for key in ("container_image", "container_image_id", "model_repository", "model_revision", "snapshot_manifest_sha256")}
    # Public counts: every pair unequal except candidate index 3 of every episode.
    counts: dict[str, int] = {}
    for pairs in pool.values():
        for index, (code_a, code_b) in enumerate(pairs):
            counts[code_a] = 8
            counts[code_b] = 8 if index == 3 else 9
    protocol, reveal = g1_opaque_v3.generate_v3(
        seed=SEED, study_date="2026-09-15", live_binding=source["live_binding"], tokenizer_model=tokenizer_model,
        consumption_registry_path=str(tmp_path / "once"), token_counts=counts,
    )
    selection = protocol["generation"]["code_selection"]
    assert selection["selected_candidate_index"] == [3] * 32
    assert selection["rule"] == "FIRST_SEED_ORDERED_CANDIDATE_PAIR_WITH_EQUAL_OFFLINE_TOKEN_COUNTS"
    assert selection["pool_sha256"] == canonical_sha256(pool)
    assert all(counts[a] == counts[b] for a, b in (episode["action_codes"] for episode in protocol["episodes"]))
    assert all(episode["action_codes"] == pool[str(episode["ordinal"])][3] for episode in protocol["episodes"])
    assert reveal["reveal_commitment_root"] == protocol["evaluator_reveal_contract"]["reveal_commitment_root"]
    # Without counts the historical index-0 derivation is used, so existing fixtures are unchanged.
    unmeasured, _ = g1_opaque_v3.generate_v3(
        seed=SEED, study_date="2026-09-15", live_binding=source["live_binding"], tokenizer_model=tokenizer_model,
        consumption_registry_path=str(tmp_path / "once"),
    )
    assert unmeasured["generation"]["code_selection"]["selected_candidate_index"] == [0] * 32
    assert all(episode["action_codes"] == pool[str(episode["ordinal"])][0] for episode in unmeasured["episodes"])
    # No equal pair anywhere: refused with the episode named.
    unequal_everywhere = {}
    for pairs in pool.values():
        for code_a, code_b in pairs:
            unequal_everywhere[code_a], unequal_everywhere[code_b] = 7, 8
    with pytest.raises(g1_micro.G1MicroError, match="episode 1 has no candidate pair"):
        g1_opaque_v3.generate_v3(
            seed=SEED, study_date="2026-09-15", live_binding=source["live_binding"], tokenizer_model=tokenizer_model,
            consumption_registry_path=str(tmp_path / "once"), token_counts=unequal_everywhere,
        )


def test_measure_pool_and_publish_after_seal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import threading
    from tests.test_hswm_g1_opaque_v3 import SEED, _OPAQUE_SUCCESSOR_PROTOCOL

    pool = g1_opaque_v3.v3_code_pool(SEED)
    pool_path = tmp_path / "pool.json"
    pool_path.write_bytes(canonical_json_bytes({"schema_version": "hswm-g1-opaque-v3-code-pool/v1", "candidates_per_episode": 32, "pool": pool}))
    snapshot = tmp_path / "hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/95a723d08a9490559dae23d0cff1d9466213d989"
    snapshot.mkdir(parents=True)

    def count_command(argv: tuple[str, ...]) -> bytes:
        assert "--network" in argv and argv[argv.index("--network") + 1] == "none"
        codes = json.loads(argv[-2])["codes"]
        return json.dumps({code: 7 + (int(code[-1], 16) % 2) for code in codes}).encode()

    out = tmp_path / "counts.json"
    assert freeze_tool.main(["measure-pool", "--pool", str(pool_path), "--model-snapshot", str(snapshot), "--live-binding-from", str(_OPAQUE_SUCCESSOR_PROTOCOL), "--out", str(out)], command=count_command) == 0
    report = json.loads(capsys.readouterr().out)
    counts = json.loads(out.read_bytes())
    assert counts["pool_sha256"] == canonical_sha256(pool) and report["codes"] == len(counts["token_counts"]) == 2048
    assert report["pairs_with_equal_counts"] > 0
    # Publisher: waits for a valid seal marker, then copies the reveal atomically.
    protocol, frozen_sha, reveal, reveal_path, _ = _generate(tmp_path)
    protocol_path = _write_protocol(tmp_path, protocol)
    marker_path = tmp_path / "marker.json"
    target = tmp_path / "after-seal.json"
    sealed = {f"episode:{index}": "0" * 64 for index in range(32)}

    def write_marker() -> None:
        marker_path.write_bytes(canonical_json_bytes({"schema_version": "hswm-g1-opaque-v3-seal-marker/v1", "study_uid": protocol["study_uid"], "protocol_canonical_sha256": frozen_sha, "sealed_journals": sealed, "sealed_journals_sha256": canonical_sha256({"sealed_journals": sealed}), "behavior_calls_sealed": 320, "claim_boundary": "test"}))

    threading.Timer(0.3, write_marker).start()
    assert freeze_tool.main(["publish-after-seal", "--marker", str(marker_path), "--reveal", str(reveal_path), "--protocol", str(protocol_path), "--to", str(target), "--timeout-seconds", "10", "--poll-seconds", "0.05"]) == 0
    assert target.read_bytes() == reveal_path.read_bytes()
    assert evaluator_process.load_reveal(target)["protocol_canonical_sha256"] == frozen_sha
    with pytest.raises(SystemExit, match="already exists"):
        freeze_tool.main(["publish-after-seal", "--marker", str(marker_path), "--reveal", str(reveal_path), "--protocol", str(protocol_path), "--to", str(target), "--timeout-seconds", "1"])
