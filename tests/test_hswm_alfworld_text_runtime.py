from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from _research.dnrd5.canonical_json import canonical_bytes
from hswm.experiments import alfworld_text_runtime as runtime
from hswm.experiments import alfworld_text_worker as worker


UID = "alfworld-g0-episode-1"
GAME_SHA = "a" * 64


def test_action_protocol_actor_projection_and_exact_newline_exclude_outcome() -> None:
    line = runtime.action_line(episode_uid=UID, action="look")
    assert worker.parse_action_line(line, episode_uid=UID) == "look"
    actor = worker.actor_projection(episode_uid=UID, observation="kitchen", step_index=0, done=False)
    assert runtime.validate_actor_projection(canonical_bytes(actor) + b"\n", episode_uid=UID) == actor
    for raw in (canonical_bytes(actor), canonical_bytes(actor) + b"\n\n", canonical_bytes(actor) + b"\nextra\n"):
        with pytest.raises(runtime.AlfworldTextRuntimeError, match="exactly one"):
            runtime.validate_actor_projection(raw, episode_uid=UID)
    with pytest.raises(runtime.AlfworldTextRuntimeError, match="field set"):
        runtime.validate_actor_projection(canonical_bytes({**actor, "won": False}) + b"\n", episode_uid=UID)


def test_action_protocol_refuses_extra_multiline_and_oversized_request() -> None:
    with pytest.raises(worker.AlfworldTextWorkerRefusal):
        worker.parse_action_line(b'{"action":"look"}\n', episode_uid=UID)
    with pytest.raises(worker.AlfworldTextWorkerRefusal):
        worker.parse_action_line(runtime.action_line(episode_uid=UID, action="look") + b"{}\n", episode_uid=UID)
    with pytest.raises(runtime.AlfworldTextRuntimeError, match="invalid|exceeds"):
        runtime.action_line(episode_uid=UID, action="x" * worker.MAX_ACTION_BYTES)
    with pytest.raises(runtime.AlfworldTextRuntimeError, match="invalid"):
        runtime.action_line(episode_uid=UID, action="look\nleak")


def test_private_outcome_is_strict_separate_receipt_channel() -> None:
    outcome = worker.build_outcome(episode_uid=UID, action_digests=["1" * 64], observation_digests=["2" * 64, "3" * 64], done=True, won=True, score=1, source_game_sha256=GAME_SHA)
    raw = canonical_bytes(outcome) + b"\n"
    assert runtime.validate_outcome_receipt(raw, episode_uid=UID, source_game_sha256=GAME_SHA, actor_steps=1) == outcome
    with pytest.raises(runtime.AlfworldTextRuntimeError, match="exactly one"):
        runtime.validate_outcome_receipt(raw + b"noise\n", episode_uid=UID, source_game_sha256=GAME_SHA, actor_steps=1)
    tampered = {**outcome, "success": False}
    with pytest.raises(runtime.AlfworldTextRuntimeError, match="success predicate|digest"):
        runtime.validate_outcome_receipt(canonical_bytes(tampered) + b"\n", episode_uid=UID, source_game_sha256=GAME_SHA, actor_steps=1)


def test_game_file_requires_regular_non_symlink_and_exact_hash(tmp_path: Path) -> None:
    game = tmp_path / "game.z8"; game.write_bytes(b"game bytes")
    digest = sha256(game.read_bytes()).hexdigest()
    assert worker.validate_game_file(game, digest) == game
    link = tmp_path / "link.z8"; link.symlink_to(game)
    with pytest.raises(worker.AlfworldTextWorkerRefusal, match="non-symlink"):
        worker.validate_game_file(link, digest)


def _spec(tmp_path: Path) -> runtime.LocalSandboxSpec:
    exe = tmp_path / "bwrap"; exe.write_text("x")
    python_root = tmp_path / "python-root"; (python_root / "bin").mkdir(parents=True)
    python = python_root / "bin" / "python"; python.write_text("x")
    repo = tmp_path / "repo"; repo.mkdir(); (repo / "src").mkdir()
    upstream = tmp_path / "upstream"; upstream.mkdir(); venv = tmp_path / "venv"; venv.mkdir()
    asset = tmp_path / "asset"; game = asset / "train" / "g.tw-pddl"; game.parent.mkdir(parents=True); game.write_bytes(b"game")
    return runtime.LocalSandboxSpec(
        exe, python, python_root, repo, upstream, venv, asset, game, "b" * 64, "c" * 64,
        runtime.LocalGameBinding("sym:OpaqueAsset:test", "train/g.tw-pddl", sha256(b"game").hexdigest(), 4), UID,
    )


def test_bwrap_command_is_011_compatible_isolated_and_fd_bound(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    command = runtime.build_bwrap_command(spec, game_fd=7)
    assert "--preserve-fds" not in command
    assert "--ro-bind-fd" in command and command[command.index("--ro-bind-fd") + 2] == runtime.SANDBOX_GAME_PATH
    assert command[command.index("--outcome-fd") + 1] == "2"
    assert "--unshare-all" in command and "--clearenv" in command
    assert str(spec.asset_root) not in command and str(spec.game_file) not in command
    assert str(spec.python_runtime_root) in command
    assert "--chdir" in command and f"{spec.repository}:{spec.repository / 'src'}" in command
    assert command[command.index("--max-steps") + 1] == "50"


def test_sealed_horizon_is_explicit_and_bounded(tmp_path: Path) -> None:
    spec = replace(_spec(tmp_path), max_steps=20)
    command = runtime.build_bwrap_command(spec, game_fd=7)
    assert command[command.index("--max-steps") + 1] == "20"
    for invalid in (0, 51, True):
        with pytest.raises(runtime.AlfworldTextRuntimeError, match="max_steps"):
            replace(spec, max_steps=invalid).validate()


def test_binding_refuses_path_hash_and_python_closure_drift(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    wrong = spec.asset_root / "wrong"; wrong.write_bytes(b"game")
    bad_path = replace(spec, game_file=wrong)
    with pytest.raises(runtime.AlfworldTextRuntimeError, match="exact pool locator"):
        bad_path.validate()
    bad_python = replace(spec, python_runtime_root=spec.repository)
    with pytest.raises(runtime.AlfworldTextRuntimeError, match="resolve inside"):
        bad_python.validate()
    linked_dir = spec.asset_root / "train"
    spec.game_file.unlink(); linked_dir.rmdir(); (tmp_path / "g.tw-pddl").write_bytes(b"game")
    linked_dir.symlink_to(tmp_path)
    with pytest.raises(runtime.AlfworldTextRuntimeError, match="symlink"):
        spec.validate()


def test_open_verified_game_rehashes_open_fd_before_launch(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    fd = runtime.open_verified_game(spec)
    try:
        assert os.read(fd, 4) == b"game"
    finally:
        os.close(fd)


def test_local_locator_loader_binds_public_commitment_and_exact_uid(tmp_path: Path) -> None:
    asset = tmp_path / "asset"; game = asset / "train" / "g.tw-pddl"; game.parent.mkdir(parents=True); game.write_bytes(b"game")
    record = {"bytes": 4, "file_sha256": sha256(b"game").hexdigest(), "opaque_uid": "sym:OpaqueAsset:one", "relative_path": "train/g.tw-pddl", "relative_path_sha256": sha256(b"train/g.tw-pddl").hexdigest(), "split": "train", "task_group_uid": "sym:OpaqueAssetGroup:one"}
    locator = {"schema_version": "hswm-alfworld-text-clean-pool-local-locator/v1", "record_role": "LOCAL_NONREPOSITORY_GAME_LOCATOR_NOT_FOR_REDISTRIBUTION", "source_binding": {"repository_commit": "a" * 40, "assets": []}, "pool_commitment": {"selected_game_counts": {"train": 1}, "selected_game_bytes_by_split": {"train": 4}, "selected_task_group_counts": {"train": 1}, "task_group_overlap_counts": {}, "selected_game_total": 1}, "records": [record]}
    locator_raw = (json.dumps(locator, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    manifest = {"schema_version": "hswm-alfworld-text-clean-pool/v2", "aggregate_commitment": {"local_locator_canonical_json_sha256": sha256(canonical_bytes(locator)).hexdigest(), "local_locator_rendered_json_sha256": sha256(locator_raw).hexdigest(), **locator["pool_commitment"]}, "source_binding": {"repository_commit": "a" * 40, "official_release_assets": []}}
    manifest_path = tmp_path / "manifest.json"; locator_path = tmp_path / "locator.json"
    manifest_path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()); locator_path.write_bytes(locator_raw)
    pool_sha, locator_sha, binding, path = runtime.load_local_game_binding(pool_manifest=manifest_path, local_locator=locator_path, asset_root=asset, opaque_uid=record["opaque_uid"])
    assert pool_sha == sha256(manifest_path.read_bytes()).hexdigest() and locator_sha == sha256(locator_raw).hexdigest()
    assert binding.file_sha256 == record["file_sha256"] and path == game
    locator["pool_commitment"]["selected_game_total"] = 2
    locator_path.write_text(json.dumps(locator, sort_keys=True), encoding="utf-8")
    with pytest.raises(runtime.AlfworldTextRuntimeError, match="commitment mismatch"):
        runtime.load_local_game_binding(pool_manifest=manifest_path, local_locator=locator_path, asset_root=asset, opaque_uid=record["opaque_uid"])


def test_parent_timeout_and_overlong_protocol_are_surface_errors() -> None:
    read_fd, write_fd = os.pipe()
    try:
        with os.fdopen(read_fd, "rb", closefd=False) as stream:
            with pytest.raises(runtime.AlfworldTextRuntimeError, match="timed out"):
                runtime.read_one_line(stream, timeout_seconds=0.01, label="actor")
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_parent_reader_refuses_partial_and_multiple_frames() -> None:
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b'{"x":1}')
        os.close(write_fd); write_fd = -1
        with os.fdopen(read_fd, "rb", closefd=False) as stream:
            with pytest.raises(runtime.AlfworldTextRuntimeError, match="closed"):
                runtime.read_one_line(stream, timeout_seconds=0.1, label="actor")
    finally:
        os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"{}\n{}\n")
        with os.fdopen(read_fd, "rb", closefd=False) as stream:
            with pytest.raises(runtime.AlfworldTextRuntimeError, match="exactly one"):
                runtime.read_one_line(stream, timeout_seconds=0.1, label="actor")
    finally:
        os.close(read_fd); os.close(write_fd)
