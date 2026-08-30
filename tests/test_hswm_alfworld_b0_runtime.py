from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from _research.dnrd5.canonical_json import canonical_bytes
from hswm.experiments import alfworld_b0_runtime as runtime


def test_local_locator_lookup_never_json_decodes_or_retains_valid_unseen_rows(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The final-holdout sentinel may be scanned for split only, never decoded."""
    asset = tmp_path / "asset"
    game = asset / "train" / "g.tw-pddl"
    game.parent.mkdir(parents=True)
    game.write_bytes(b"game")
    selected = {
        "bytes": 4,
        "file_sha256": sha256(b"game").hexdigest(),
        "opaque_uid": "sym:OpaqueAsset:selected",
        "relative_path": "train/g.tw-pddl",
        "relative_path_sha256": sha256(b"train/g.tw-pddl").hexdigest(),
        "split": "train",
        "task_group_uid": "sym:OpaqueAssetGroup:selected",
    }
    sentinel = "VALID_UNSEEN_MUST_NEVER_BE_JSON_DECODED"
    unseen = {
        "bytes": 9,
        "file_sha256": "f" * 64,
        "opaque_uid": sentinel,
        "relative_path": f"valid_unseen/{sentinel}.tw-pddl",
        "relative_path_sha256": sha256(f"valid_unseen/{sentinel}.tw-pddl".encode()).hexdigest(),
        "split": "valid_unseen",
        "task_group_uid": sentinel,
    }
    commitment = {
        "selected_game_counts": {"train": 1, "valid_seen": 0, "valid_unseen": 1},
        "selected_game_bytes_by_split": {"train": 4, "valid_seen": 0, "valid_unseen": 9},
        "selected_task_group_counts": {"train": 1, "valid_seen": 0, "valid_unseen": 1},
        "task_group_overlap_counts": {},
        "selected_game_total": 2,
    }
    locator = {
        "schema_version": "hswm-alfworld-text-clean-pool-local-locator/v1",
        "record_role": "LOCAL_NONREPOSITORY_GAME_LOCATOR_NOT_FOR_REDISTRIBUTION",
        "source_binding": {"repository_commit": "a" * 40, "assets": []},
        "pool_commitment": commitment,
        "records": [selected, unseen],
    }
    locator_raw = (json.dumps(locator, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    manifest = {
        "schema_version": "hswm-alfworld-text-clean-pool/v2",
        "aggregate_commitment": {
            "local_locator_canonical_json_sha256": sha256(canonical_bytes(locator)).hexdigest(),
            "local_locator_rendered_json_sha256": sha256(locator_raw).hexdigest(),
            **commitment,
        },
        "source_binding": {"repository_commit": "a" * 40, "official_release_assets": []},
    }
    manifest_path = tmp_path / "manifest.json"
    locator_path = tmp_path / "locator.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    locator_path.write_bytes(locator_raw)
    original_loads = runtime.json.loads
    decoded_payloads: list[bytes] = []

    def guarded_loads(payload, *args, **kwargs):
        encoded = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        assert sentinel.encode() not in encoded, "valid_unseen sentinel was JSON-decoded"
        decoded_payloads.append(encoded)
        return original_loads(payload, *args, **kwargs)

    monkeypatch.setattr(runtime.json, "loads", guarded_loads)
    _, _, binding, bound_path = runtime.load_local_game_binding(
        pool_manifest=manifest_path,
        local_locator=locator_path,
        asset_root=asset,
        opaque_uid=selected["opaque_uid"],
    )
    assert binding.opaque_uid == selected["opaque_uid"]
    assert bound_path == game
    assert all(sentinel.encode() not in payload for payload in decoded_payloads)


def test_dgx_b0_launcher_strictly_transforms_historical_command_to_controller_proc_fd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    game = tmp_path / "game.tw-pddl"
    game.write_bytes(b"game")

    class Spec:
        bubblewrap = Path(runtime.DGX_BWRAP_PATH)
        game_file = game

        def validate(self) -> None:
            return None

    historical = [
        runtime.DGX_BWRAP_PATH, "--die-with-parent", "--new-session", "--unshare-all",
        "--unshare-net", "--proc", "/proc", "--ro-bind-fd", "3", "/run/hswm/game.tw-pddl",
        "--clearenv", "--", "/python", "-m", "worker",
    ]
    monkeypatch.setattr(runtime, "build_bwrap_command", lambda _spec, *, game_fd: historical)
    command = runtime.build_dgx_b0_bwrap_command(Spec(), sudo=Path(runtime.DGX_SUDO_PATH), verified_game_fd=17)
    assert command[:15] == [
        runtime.DGX_SUDO_PATH, "-n", "--", runtime.DGX_BWRAP_PATH,
        "--die-with-parent", "--new-session", "--unshare-pid", "--unshare-ipc",
        "--unshare-uts", "--unshare-net", "--unshare-cgroup-try", "--cap-drop", "ALL",
        "--cap-add", "CAP_DAC_READ_SEARCH",
    ]
    assert ["--ro-bind", f"/proc/{os.getpid()}/fd/17", "/run/hswm/game.tw-pddl"] == command[17:20]
    assert "--unshare-user" not in command and "--unshare-all" not in command
    assert "--ro-bind-fd" not in command and "--preserve-fds" not in command
    assert runtime.DGX_SANDBOX_PROFILE["game_fd_handoff"] == "NOT_INHERITED_BY_SUDO_OR_WORKER"


@pytest.mark.parametrize("missing", ["--unshare-all", "--unshare-net", "--ro-bind-fd"])
def test_dgx_b0_launcher_rejects_missing_historical_isolation_primitive(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    class Spec:
        bubblewrap = Path(runtime.DGX_BWRAP_PATH)

        def validate(self) -> None:
            return None

    historical = [
        runtime.DGX_BWRAP_PATH, "--die-with-parent", "--new-session", "--unshare-all",
        "--unshare-net", "--ro-bind-fd", "3", "/run/hswm/game.tw-pddl", "--", "/python",
    ]
    index = historical.index(missing)
    del historical[index:index + (3 if missing == "--ro-bind-fd" else 1)]
    monkeypatch.setattr(runtime, "build_bwrap_command", lambda _spec, *, game_fd: historical)
    with pytest.raises(runtime.AlfworldTextRuntimeError, match="primitive count"):
        runtime.build_dgx_b0_bwrap_command(
            Spec(), sudo=Path(runtime.DGX_SUDO_PATH), verified_game_fd=17
        )


def test_pinned_game_fd_remains_open_until_child_waits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    game = tmp_path / "game.tw-pddl"
    game.write_bytes(b"game")
    game_fd = os.open(game, os.O_RDONLY)

    class Child:
        stdin = stdout = stderr = None
        terminal = False

        def poll(self) -> int | None:
            return 0 if self.terminal else None

        def wait(self, timeout: float | None = None) -> int:
            self.terminal = True
            return 0

        def terminate(self) -> None:
            self.terminal = True

        def kill(self) -> None:
            self.terminal = True

    pinned = runtime._PinnedGameProcess(Child(), game_fd)
    assert os.fstat(game_fd).st_size == 4
    assert pinned.poll() is None
    assert os.fstat(game_fd).st_size == 4
    assert pinned.wait(timeout=1) == 0
    with pytest.raises(OSError):
        os.fstat(game_fd)
