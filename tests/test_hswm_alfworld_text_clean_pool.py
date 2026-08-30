"""Contract tests for the aggregate-only local ALFWorld clean-task pool."""

from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts/build_hswm_alfworld_text_clean_pool.py"
MANIFEST_PATH = ROOT / "manifests/HSWM_ALFWORLD_TEXT_CLEAN_POOL_2026-08-30.json"
_SPEC = importlib.util.spec_from_file_location("alfworld_clean_pool_builder", BUILDER_PATH)
assert _SPEC and _SPEC.loader
builder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(builder)


def _spec(name: str, payload: bytes, use: str) -> dict[str, object]:
    return {"name": name, "bytes": len(payload), "sha256": sha256(payload).hexdigest(), "use": use}


def _fixture(tmp_path: Path, game_bytes: bytes = b'{"solvable": true}') -> tuple[Path, tuple[dict[str, object], ...]]:
    data_root = tmp_path / "data"
    trial = data_root / "json_2.1.1/train/pick_clean_then_place_in_recep-Cup-None-Sink-1/trial-a"
    trial.mkdir(parents=True)
    (trial / "traj_data.json").write_bytes(b"{}")
    (trial / "game.tw-pddl").write_bytes(game_bytes)
    for split in ("valid_seen", "valid_unseen"):
        (data_root / "json_2.1.1" / split).mkdir(parents=True)
    assets = tmp_path / "assets"
    assets.mkdir()
    metadata, games = assets / "json_2.1.1_json.zip", assets / "json_2.1.3_tw-pddl.zip"
    with ZipFile(metadata, "w", ZIP_DEFLATED) as archive:
        archive.writestr("json_2.1.1/train/pick_clean_then_place_in_recep-Cup-None-Sink-1/trial-a/traj_data.json", b"{}")
    with ZipFile(games, "w", ZIP_DEFLATED) as archive:
        archive.writestr("json_2.1.1/train/pick_clean_then_place_in_recep-Cup-None-Sink-1/trial-a/game.tw-pddl", game_bytes)
    return data_root, (_spec(metadata.name, metadata.read_bytes(), "REQUIRED_METADATA_PROVENANCE"), _spec("unused.zip", b"unused", "UNUSED_NOT_REQUIRED_FOR_TEXT_POOL"), _spec(games.name, games.read_bytes(), "REQUIRED_SELECTED_GAME_PROVENANCE"))


def test_public_commitment_has_no_locator_or_game_digest(tmp_path: Path) -> None:
    data_root, specs = _fixture(tmp_path)
    manifest, locator = builder.build_inventory(data_root, archive_root=tmp_path / "assets", asset_specs=specs)
    assert manifest["aggregate_commitment"]["selected_game_counts"] == {"train": 1, "valid_seen": 0, "valid_unseen": 0}
    assert manifest["aggregate_commitment"]["selected_task_group_counts"] == {
        "train": 1,
        "valid_seen": 0,
        "valid_unseen": 0,
    }
    text = json.dumps(manifest)
    assert "trial-a" not in text and "Cup-None-Sink" not in text
    assert "file_sha256" not in text and "relative_path" not in text
    assert locator["records"][0]["relative_path"].endswith("trial-a/game.tw-pddl")
    assert locator["records"][0]["file_sha256"] == sha256(b'{"solvable": true}').hexdigest()


def test_builder_rejects_extracted_game_tamper(tmp_path: Path) -> None:
    data_root, specs = _fixture(tmp_path)
    next((data_root / "json_2.1.1/train").glob("**/game.tw-pddl")).write_bytes(b'{"solvable": true, "tampered": true}')
    with pytest.raises(ValueError, match="extracted game does not match archive"):
        builder.build_inventory(data_root, archive_root=tmp_path / "assets", asset_specs=specs)


def test_builder_rejects_extracted_selected_game_tampered_to_unsolvable(tmp_path: Path) -> None:
    data_root, specs = _fixture(tmp_path)
    next((data_root / "json_2.1.1/train").glob("**/game.tw-pddl")).write_bytes(b'{"solvable": false}')
    with pytest.raises(ValueError, match="extracted game does not match archive"):
        builder.build_inventory(data_root, archive_root=tmp_path / "assets", asset_specs=specs)


def test_builder_rejects_missing_extracted_archive_member(tmp_path: Path) -> None:
    data_root, specs = _fixture(tmp_path)
    next((data_root / "json_2.1.1/train").glob("**/traj_data.json")).unlink()
    with pytest.raises(ValueError, match="extracted metadata does not match archive"):
        builder.build_inventory(data_root, archive_root=tmp_path / "assets", asset_specs=specs)


def test_builder_rejects_unsafe_archive_member(tmp_path: Path) -> None:
    data_root, specs = _fixture(tmp_path)
    archive = tmp_path / "assets/json_2.1.1_json.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as value:
        value.writestr("../escape", b"x")
    changed = dict(specs[0], bytes=archive.stat().st_size, sha256=sha256(archive.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="unsafe zip member"):
        builder.build_inventory(data_root, archive_root=tmp_path / "assets", asset_specs=(changed, specs[1], specs[2]))


def test_locator_target_inside_repository_is_refused() -> None:
    with pytest.raises(ValueError, match="outside repository"):
        builder._assert_nonrepository_locator(ROOT / "manifests/private.locator.json")


def test_builder_fails_closed_when_checked_source_binding_drifts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root, specs = _fixture(tmp_path)
    monkeypatch.setattr(builder, "SOURCE_AUDIT_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="source audit SHA-256 binding drifted"):
        builder.build_inventory(
            data_root,
            archive_root=tmp_path / "assets",
            asset_specs=specs,
        )


def test_checked_manifest_counts_and_no_asset_locators() -> None:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert value["schema_version"] == "hswm-alfworld-text-clean-pool/v2"
    assert value["aggregate_commitment"]["selected_game_counts"] == {"train": 650, "valid_seen": 27, "valid_unseen": 31}
    assert value["aggregate_commitment"]["selected_game_total"] == 708
    assert value["aggregate_commitment"]["selected_task_group_counts"] == {
        "train": 268,
        "valid_seen": 27,
        "valid_unseen": 11,
    }
    assert value["aggregate_commitment"]["task_group_overlap_counts"] == {
        "train__valid_seen": 25,
        "train__valid_unseen": 0,
        "valid_seen__valid_unseen": 0,
    }
    assert value["selection"]["task_group_definition"] == (
        "SHA256_OF_TASK_DIRECTORY_NAME_WITHOUT_SPLIT_OR_TRIAL"
    )
    assert {split: (audit["trial_directories_with_traj_data"], audit["missing_game_trial_id_count"]) for split, audit in value["metadata_trial_audit"].items()} == {"train": (858, 208), "valid_seen": (37, 10), "valid_unseen": (36, 5)}
    text = json.dumps(value)
    for forbidden in ("usable_games", "relative_path", "file_sha256", "trial_T", "pick_clean_then_place"):
        assert forbidden not in text
    pddl = value["source_binding"]["official_release_assets"][1]
    assert pddl["use"] == "UNUSED_NOT_REQUIRED_FOR_TEXT_POOL" and pddl["verified"] is False
