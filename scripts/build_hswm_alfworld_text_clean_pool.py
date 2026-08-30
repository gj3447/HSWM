#!/usr/bin/env python3
"""Build an aggregate-only ALFWorld text clean-pool commitment.

The checked-in manifest has no game locator, task name, trial identifier, or
per-game digest.  The detailed locator is deliberately written outside the
repository to support local execution without publishing asset identifiers.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Iterable
from zipfile import BadZipFile, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = Path("/mnt/bulk/cache/hswm/alfworld/aaba6870f86c5be6a08a491f32a50b906227bc3e/data")
DEFAULT_OUTPUT = ROOT / "manifests/HSWM_ALFWORLD_TEXT_CLEAN_POOL_2026-08-30.json"
DEFAULT_LOCATOR_OUTPUT = DEFAULT_DATA_ROOT.parent / "locators/HSWM_ALFWORLD_TEXT_CLEAN_POOL_2026-08-30.locator.v1.json"
SPLITS = ("train", "valid_seen", "valid_unseen")
TASK_PREFIX = "pick_clean_then_place_in_recep-"
REPOSITORY_COMMIT = "aaba6870f86c5be6a08a491f32a50b906227bc3e"
SOURCE_AUDIT_PATH = "_research/causal_composition/priors/alfworld_text_g1_candidate_v1/source_audit.v1.json"
SOURCE_AUDIT_SHA256 = "626daca514906eacefe258fca1694b3186b6d2fde68b88a08554ea7f9318e0c5"
LOCAL_AUTH_PATH = "_research/causal_composition/priors/alfworld_text_g1_candidate_v1/local_use_authorization.v1.json"
LOCAL_AUTH_SHA256 = "48c1b5c82ff8c6c5b454f5e0a32beb9546fd46db4b891c804397ca036d71f3a8"
SOURCE_ASSET_SPECS = (
    {"name": "json_2.1.1_json.zip", "bytes": 72018818, "sha256": "25171f16e20ad7b048c47275c45b0babf3aa1cbab29cec97387922350a9844bc", "use": "REQUIRED_METADATA_PROVENANCE"},
    {"name": "json_2.1.1_pddl.zip", "bytes": 34881784, "sha256": "913942ebed06659ea0da2f8122512d98bc6add30d84961ca803132d8fbcad585", "use": "UNUSED_NOT_REQUIRED_FOR_TEXT_POOL"},
    {"name": "json_2.1.3_tw-pddl.zip", "bytes": 36507267, "sha256": "5df77ea759f2211a4106082839ddbbb790f1ba4e7d097ed732cf453f72aa36cf", "use": "REQUIRED_SELECTED_GAME_PROVENANCE"},
)


def _sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _is_regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _is_regular_directory(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink()


def _trial_id_digest(ids: Iterable[str]) -> str:
    return _sha256_bytes("".join(f"{item}\n" for item in sorted(ids)).encode())


def _parse_solvable_game(path: Path) -> bool:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return type(value) is dict and value.get("solvable") is True


def _task_dirs(split_root: Path) -> list[Path]:
    return sorted(path for path in split_root.glob(f"{TASK_PREFIX}*") if _is_regular_directory(path))


def _trial_dirs(task_dir: Path) -> list[Path]:
    return sorted(path for path in task_dir.iterdir() if _is_regular_directory(path))


def _assert_nonrepository_locator(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return resolved
    raise ValueError(f"local locator target must be outside repository: {resolved}")


def _safe_zip_index(path: Path) -> dict[str, ZipInfo]:
    if not _is_regular_file(path):
        raise ValueError(f"missing regular archive: {path}")
    try:
        with ZipFile(path) as archive:
            index: dict[str, ZipInfo] = {}
            for info in archive.infolist():
                member, pure, mode = info.filename, PurePosixPath(info.filename), info.external_attr >> 16
                unsafe = "\\" in member or pure.is_absolute() or ".." in pure.parts
                special = stat.S_ISLNK(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode) or stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode)
                if unsafe or special:
                    raise ValueError(f"unsafe zip member in {path.name}: {member!r}")
                if not info.is_dir():
                    if member in index:
                        raise ValueError(f"duplicate zip member in {path.name}: {member!r}")
                    index[member] = info
    except BadZipFile as error:
        raise ValueError(f"invalid zip archive: {path}") from error
    return index


def _verify_required_archives(archive_root: Path, specs: Iterable[dict[str, Any]]) -> tuple[dict[str, ZipInfo], dict[str, ZipInfo], list[dict[str, Any]]]:
    indices: dict[str, dict[str, ZipInfo]] = {}
    public: list[dict[str, Any]] = []
    for spec in specs:
        entry = dict(spec)
        if str(spec["use"]).startswith("REQUIRED"):
            path = archive_root / str(spec["name"])
            if not _is_regular_file(path) or path.stat().st_size != spec["bytes"]:
                raise ValueError(f"archive byte-size mismatch: {path}")
            if _sha256_bytes(path.read_bytes()) != spec["sha256"]:
                raise ValueError(f"archive SHA-256 mismatch: {path}")
            indices[str(spec["name"])] = _safe_zip_index(path)
            entry["verified"] = True
        else:
            entry["verified"] = False
        public.append(entry)
    return indices["json_2.1.1_json.zip"], indices["json_2.1.3_tw-pddl.zip"], public


def _rule_commitment() -> str:
    return _sha256_bytes(_canonical_bytes({"task_prefix": TASK_PREFIX, "excluded_casefold_substrings": ["movable", "sliced"], "requires_regular_game": True, "requires_json_object_solvable_true": True, "included_splits": list(SPLITS), "task_group_definition": "SHA256_OF_TASK_DIRECTORY_NAME_WITHOUT_SPLIT_OR_TRIAL"}))


def _verify_repository_bindings() -> None:
    """Fail closed before publishing stale audit or authorization bindings."""
    for relative_path, expected, label in (
        (SOURCE_AUDIT_PATH, SOURCE_AUDIT_SHA256, "source audit"),
        (LOCAL_AUTH_PATH, LOCAL_AUTH_SHA256, "local authorization"),
    ):
        path = ROOT / relative_path
        if not _is_regular_file(path) or _sha256_bytes(path.read_bytes()) != expected:
            raise ValueError(f"{label} SHA-256 binding drifted: {path}")


def _metadata_trials_from_archive(index: dict[str, ZipInfo]) -> list[tuple[str, str, str]]:
    """Derive the candidate universe from the verified metadata archive only."""
    trials: list[tuple[str, str, str]] = []
    for member in index:
        parts = PurePosixPath(member).parts
        if len(parts) < 3 or parts[0] != "json_2.1.1" or parts[1] not in SPLITS:
            continue
        if not parts[2].startswith(TASK_PREFIX):
            continue
        if parts[-1] != "traj_data.json":
            continue
        if len(parts) != 5 or not parts[3]:
            raise ValueError(f"unexpected candidate metadata member shape: {member!r}")
        trials.append((parts[1], parts[2], parts[3]))
    return sorted(trials)


def build_inventory(data_root: Path, *, archive_root: Path | None = None, asset_specs: Iterable[dict[str, Any]] = SOURCE_ASSET_SPECS) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return public aggregate commitment and private detailed local locator."""
    _verify_repository_bindings()
    data_root = data_root.resolve()
    archive_root = (archive_root or data_root.parent / "assets").resolve()
    json_archive, tw_archive, public_assets = _verify_required_archives(archive_root, asset_specs)
    json_root, records = data_root / "json_2.1.1", []
    metadata_audit: dict[str, dict[str, Any]] = {}
    archive_trials = _metadata_trials_from_archive(json_archive)
    with ZipFile(archive_root / "json_2.1.1_json.zip") as metadata_zip, ZipFile(archive_root / "json_2.1.3_tw-pddl.zip") as tw_zip:
        for split in SPLITS:
            split_root = json_root / split
            if not _is_regular_directory(split_root):
                raise ValueError(f"missing regular split directory: {split_root}")
            metadata_ids, missing_ids = [], []
            for archived_split, task_name, trial_name in archive_trials:
                if archived_split != split:
                    continue
                trial_id = f"{split}/{task_name}/{trial_name}"
                trial_dir = json_root / trial_id
                trajectory = trial_dir / "traj_data.json"
                metadata_member = f"json_2.1.1/{trial_id}/traj_data.json"
                if not _is_regular_file(trajectory) or metadata_zip.read(metadata_member) != trajectory.read_bytes():
                    raise ValueError(f"extracted metadata does not match archive: {trajectory}")
                metadata_ids.append(trial_id)
                game = trial_dir / "game.tw-pddl"
                game_member = f"json_2.1.1/{trial_id}/game.tw-pddl"
                game_in_archive = game_member in tw_archive
                if not game_in_archive:
                    if _is_regular_file(game):
                        raise ValueError(f"extracted game absent from archive: {game}")
                    missing_ids.append(trial_id)
                    continue
                if not _is_regular_file(game) or tw_zip.read(game_member) != game.read_bytes():
                    raise ValueError(f"extracted game does not match archive: {game}")
                if "movable" in task_name.lower() or "sliced" in task_name.lower() or not _parse_solvable_game(game):
                    continue
                relative_path = game.relative_to(json_root).as_posix()
                relative_path_sha256 = _sha256_bytes(relative_path.encode())
                # Group identity intentionally excludes the official split so a
                # repeated task configuration cannot straddle calibration and
                # holdout merely under a different split label.
                task_group_sha256 = _sha256_bytes(task_name.encode())
                records.append({"opaque_uid": f"sym:OpaqueAsset:alfworld-game-{relative_path_sha256}", "relative_path": relative_path, "relative_path_sha256": relative_path_sha256, "file_sha256": _sha256_bytes(game.read_bytes()), "bytes": game.stat().st_size, "split": split, "task_group_uid": f"sym:OpaqueAssetGroup:alfworld-task-{task_group_sha256}"})
            metadata_audit[split] = {"trial_directories_with_traj_data": len(metadata_ids), "missing_game_trial_id_count": len(missing_ids), "missing_game_trial_ids_sha256": _trial_id_digest(missing_ids)}
    records.sort(key=lambda item: (item["split"], item["relative_path"]))
    counts = {split: sum(item["split"] == split for item in records) for split in SPLITS}
    byte_counts = {split: sum(item["bytes"] for item in records if item["split"] == split) for split in SPLITS}
    group_sets = {
        split: {item["task_group_uid"] for item in records if item["split"] == split}
        for split in SPLITS
    }
    group_counts = {split: len(groups) for split, groups in group_sets.items()}
    group_overlap_counts = {
        f"{left}__{right}": len(group_sets[left] & group_sets[right])
        for index, left in enumerate(SPLITS)
        for right in SPLITS[index + 1:]
    }
    locator = {"schema_version": "hswm-alfworld-text-clean-pool-local-locator/v1", "record_role": "LOCAL_NONREPOSITORY_GAME_LOCATOR_NOT_FOR_REDISTRIBUTION", "source_binding": {"repository_commit": REPOSITORY_COMMIT, "assets": public_assets}, "pool_commitment": {"selected_game_counts": counts, "selected_game_bytes_by_split": byte_counts, "selected_task_group_counts": group_counts, "task_group_overlap_counts": group_overlap_counts, "selected_game_total": len(records)}, "records": records}
    manifest = {
        "schema_version": "hswm-alfworld-text-clean-pool/v2",
        "record_role": "AGGREGATE_OPAQUE_LOCAL_TASK_POOL_COMMITMENT_NOT_A_SPLIT_OR_RESULT",
        "status": "LOCAL_RESEARCH_ASSET_INVENTORY_ONLY",
        "source_binding": {"repository_commit": REPOSITORY_COMMIT, "data_root_layout": "json_2.1.1", "source_audit": {"path": SOURCE_AUDIT_PATH, "sha256": SOURCE_AUDIT_SHA256}, "local_use_authorization": {"path": LOCAL_AUTH_PATH, "sha256": LOCAL_AUTH_SHA256}, "official_release_assets": public_assets},
        "selection": {"environment_mode": "ALFWORLD_TEXT_ONLY", "included_splits": list(SPLITS), "selection_algorithm": "hswm-alfworld-text-clean-pool/v2", "selection_rule_sha256": _rule_commitment(), "task_group_definition": "SHA256_OF_TASK_DIRECTORY_NAME_WITHOUT_SPLIT_OR_TRIAL", "selected_game_bytes_crosschecked_against_tw_archive": True, "selected_metadata_crosschecked_against_json_archive": True},
        "aggregate_commitment": {"local_locator_canonical_json_sha256": _sha256_bytes(_canonical_bytes(locator)), "local_locator_rendered_json_sha256": _sha256_bytes((json.dumps(locator, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()), "selected_game_counts": counts, "selected_game_bytes_by_split": byte_counts, "selected_task_group_counts": group_counts, "task_group_overlap_counts": group_overlap_counts, "selected_game_total": len(records)},
        "metadata_trial_audit": metadata_audit,
        "no_claim": ["This aggregate commitment contains no game locator, semantic task name, trial identifier, per-game digest, game content, PDDL, trajectory, or annotation.", "The detailed local locator is deliberately non-repository and is not authorized for redistribution.", "It assigns no training, calibration, validation, final-holdout, or other experimental split.", "It is not an ALFWorld execution, G0 result, G1 result, comparator result, or HSWM efficacy claim."],
    }
    return manifest, locator


def build_manifest(data_root: Path, **kwargs: Any) -> dict[str, Any]:
    return build_inventory(data_root, **kwargs)[0]


def _render(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--archive-root", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--locator-output", type=Path, default=DEFAULT_LOCATOR_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    locator_output = _assert_nonrepository_locator(args.locator_output)
    manifest, locator = build_inventory(args.data_root, archive_root=args.archive_root)
    rendered_manifest, rendered_locator = _render(manifest), _render(locator)
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != rendered_manifest:
            raise SystemExit(f"manifest drift: {args.output}")
        if not locator_output.is_file() or locator_output.read_text(encoding="utf-8") != rendered_locator:
            raise SystemExit(f"local locator drift: {locator_output}")
        print(f"MATCH {args.output}\nMATCH {locator_output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    locator_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered_manifest, encoding="utf-8")
    locator_output.write_text(rendered_locator, encoding="utf-8")
    print(f"WROTE {args.output}\nWROTE {locator_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
