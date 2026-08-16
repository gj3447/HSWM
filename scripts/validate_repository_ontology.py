#!/usr/bin/env python3
"""Validate the small, read-only repository layout contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "HSWM_REPOSITORY_ONTOLOGY.v1.json"
ROOT_BASELINE_V1_COMMIT = "33556a55530bdc0912154abc8c19897f89b0dcda"
IGNORED_FALLBACK_PARTS = {
    ".git",
    ".hypothesis",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "hswm.egg-info",
}
IGNORED_FALLBACK_ROOT_FILES = {"PKG-INFO", "setup.cfg"}

# Direct script execution from a source checkout should work without an editable
# install. Normal package imports still take the ordinary installed path.
try:
    from hswm.infrastructure import legacy_replay
except ModuleNotFoundError:  # pragma: no cover - exercised by direct operators
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from hswm.infrastructure import legacy_replay


class OntologyError(ValueError):
    """The repository layout contract is inconsistent or out of date."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise OntologyError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OntologyError(f"cannot read JSON document: {path}") from exc
    if not isinstance(value, dict):
        raise OntologyError(f"JSON document must be an object: {path}")
    return value


def _resolve_from_repo(relative: str) -> Path:
    return REPO_ROOT / relative


def _safe_repository_file(relative: Any, *, label: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise OntologyError(f"invalid {label} path")
    logical = Path(relative)
    if (
        logical.is_absolute()
        or ".." in logical.parts
        or logical.as_posix() != relative
    ):
        raise OntologyError(f"invalid {label} path: {relative!r}")
    root = REPO_ROOT.resolve()
    candidate = REPO_ROOT / logical
    if candidate.is_symlink() or not candidate.is_file():
        raise OntologyError(f"{label} is not a regular file: {relative}")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise OntologyError(f"cannot resolve {label}: {relative}") from exc
    if not resolved.is_relative_to(root):
        raise OntologyError(f"{label} escapes the repository: {relative}")
    return candidate


def validate_graph(data: dict[str, Any]) -> None:
    """Validate the curated concept graph, not every physical repository path."""

    if data.get("schema_version") != "hswm-repository-ontology/v1":
        raise OntologyError("unsupported repository ontology schema")

    concepts = data.get("concepts", [])
    concept_uids = [row.get("uid") for row in concepts]
    if len(concept_uids) != len(set(concept_uids)) or None in concept_uids:
        raise OntologyError("concept UIDs must be present and unique")
    concept_set = set(concept_uids)
    if data.get("root_uid") in concept_set:
        raise OntologyError("root_uid must identify the repository, not a concept")
    for concept in concepts:
        directory = _resolve_from_repo(concept["directory"])
        if not directory.is_dir() or not (directory / "README.md").is_file():
            raise OntologyError(
                f"concept directory lacks README: {concept['directory']}"
            )

    for relation in data.get("relations", []):
        if relation.get("from") not in concept_set or relation.get("to") not in concept_set:
            raise OntologyError(f"relation has unknown endpoint: {relation}")
        if not relation.get("type"):
            raise OntologyError(f"relation has no type: {relation}")

    mount_ids: set[str] = set()
    for mount in data.get("mounts", []):
        mount_id = mount.get("id")
        if not mount_id or mount_id in mount_ids:
            raise OntologyError(f"mount id missing or duplicated: {mount_id!r}")
        mount_ids.add(mount_id)
        if not set(mount.get("concepts", [])) <= concept_set:
            raise OntologyError(f"mount has unknown concept: {mount_id}")
        if not mount.get("patterns") and not mount.get("root_patterns"):
            raise OntologyError(f"mount has no patterns: {mount_id}")

    public = data.get("public_root_surface", [])
    if len(public) != len(set(public)) or any("/" in path for path in public):
        raise OntologyError("public_root_surface must contain unique root paths")


def _filesystem_repository_paths() -> tuple[list[str], bool]:
    paths: list[str] = []
    for path in REPO_ROOT.rglob("*"):
        relative = path.relative_to(REPO_ROOT)
        if any(part in IGNORED_FALLBACK_PARTS for part in relative.parts):
            continue
        if len(relative.parts) == 1 and relative.name in IGNORED_FALLBACK_ROOT_FILES:
            continue
        if path.is_file() or path.is_symlink():
            paths.append(relative.as_posix())
    return sorted(set(paths)), False


def repository_paths() -> tuple[list[str], bool]:
    """Return current repository files and whether Git supplied the list."""

    local_git_metadata = (REPO_ROOT / ".git").exists() or (
        REPO_ROOT / ".git"
    ).is_symlink()
    try:
        top_level = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        if local_git_metadata:
            raise OntologyError("Git checkout metadata cannot be read") from exc
        return _filesystem_repository_paths()
    if Path(top_level.stdout.strip()).resolve() != REPO_ROOT.resolve():
        if local_git_metadata:
            raise OntologyError("Git checkout resolves to the wrong repository root")
        return _filesystem_repository_paths()

    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        if local_git_metadata:
            raise OntologyError("Git checkout index cannot be read") from exc
        return _filesystem_repository_paths()

    paths = []
    for relative in proc.stdout.decode("utf-8").split("\0"):
        if not relative:
            continue
        path = REPO_ROOT / relative
        if path.exists() or path.is_symlink():
            paths.append(Path(relative).as_posix())
    return sorted(set(paths)), True


def _migration_entries() -> tuple[legacy_replay.MigrationEntry, ...]:
    try:
        return legacy_replay.load_migration_entries(REPO_ROOT)
    except legacy_replay.LegacyReplayError as exc:
        raise OntologyError(str(exc)) from exc


def _baseline_payload(data: dict[str, Any]) -> dict[str, Any]:
    relative = data.get("root_compatibility_baseline")
    if not isinstance(relative, str) or not relative:
        raise OntologyError("root_compatibility_baseline must name one file")
    payload = _read_json(
        _safe_repository_file(relative, label="root compatibility baseline")
    )
    if payload.get("$schema") != (
        "../../schemas/hswm_root_compatibility_baseline.v1.schema.json"
    ):
        raise OntologyError("root compatibility baseline names the wrong schema")
    if payload.get("schema_version") != "hswm-root-compatibility-baseline/v1":
        raise OntologyError("unsupported root compatibility baseline schema")
    if payload.get("status") != "FROZEN_BASELINE":
        raise OntologyError("root compatibility baseline is not frozen")
    source_commit = payload.get("source_commit")
    if source_commit != ROOT_BASELINE_V1_COMMIT:
        raise OntologyError("root compatibility baseline v1 commit changed")
    source_public = payload.get("source_public_paths")
    if (
        not isinstance(source_public, list)
        or not source_public
        or any(
            not isinstance(path, str)
            or not path
            or "/" in path
            or "\\" in path
            for path in source_public
        )
        or len(source_public) != len(set(source_public))
    ):
        raise OntologyError(
            "root compatibility baseline source public paths are invalid"
        )
    return payload


def load_legacy(
    data: dict[str, Any],
    entries: Sequence[legacy_replay.MigrationEntry] | None = None,
) -> tuple[dict[str, Any], set[str]]:
    """Derive active root exceptions from one frozen baseline minus migrations."""

    payload = _baseline_payload(data)
    rows = payload.get("paths")
    if not isinstance(rows, list):
        raise OntologyError("root compatibility baseline paths are missing")

    listed: list[str] = []
    for path in rows:
        if (
            not isinstance(path, str)
            or not path
            or "/" in path
            or "\\" in path
        ):
            raise OntologyError("invalid root compatibility baseline path")
        listed.append(path)
    if len(listed) != len(set(listed)):
        raise OntologyError("root compatibility baseline paths must be unique")
    if set(listed) & set(payload["source_public_paths"]):
        raise OntologyError("baseline public and compatibility paths overlap")

    selected = tuple(entries) if entries is not None else _migration_entries()
    migrated = {entry.old_path for entry in selected}
    active = set(listed) - migrated
    if active & set(data["public_root_surface"]):
        raise OntologyError("public and legacy root surfaces overlap")
    return payload, active


def _git_root_files(commit: str) -> set[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-tree", "-z", commit],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise OntologyError(f"cannot inspect root compatibility commit {commit}") from exc
    files: set[str] = set()
    for record in proc.stdout.decode("utf-8").split("\0"):
        if not record:
            continue
        metadata, name = record.split("\t", 1)
        _mode, object_type, _object_id = metadata.split(" ", 2)
        if object_type == "blob":
            files.add(name)
    return files


def _git_blob(commit: str, relative: str) -> bytes:
    logical = Path(relative)
    if (
        not relative
        or "\\" in relative
        or logical.is_absolute()
        or ".." in logical.parts
        or logical.as_posix() != relative
    ):
        raise OntologyError(f"invalid frozen repository path: {relative!r}")
    try:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show", f"{commit}:{relative}"],
            check=True,
            capture_output=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise OntologyError(f"cannot read frozen repository path: {relative}") from exc


def _git_json(commit: str, relative: str) -> dict[str, Any]:
    try:
        value = json.loads(
            _git_blob(commit, relative).decode("utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OntologyError(f"invalid frozen JSON document: {relative}") from exc
    if not isinstance(value, dict):
        raise OntologyError(f"frozen JSON document must be an object: {relative}")
    return value


def _registry_paths(data: dict[str, Any], key: str) -> tuple[str, ...]:
    value = data.get(key)
    if isinstance(value, str) and value:
        paths = (value,)
    elif (
        isinstance(value, list)
        and value
        and all(isinstance(path, str) and path for path in value)
    ):
        paths = tuple(value)
    else:
        raise OntologyError(f"repository ontology has invalid {key}")
    if len(paths) != len(set(paths)):
        raise OntologyError(f"repository ontology repeats a manifest in {key}")
    return paths


def _validate_frozen_registry(data: dict[str, Any], commit: str) -> None:
    """Existing replay manifests are immutable; future manifests are additive."""

    frozen_ontology = _git_json(
        commit, "ontology/HSWM_REPOSITORY_ONTOLOGY.v1.json"
    )
    for key in ("python_root_migrations", "asset_root_migrations"):
        frozen = set(_registry_paths(frozen_ontology, key))
        current = set(_registry_paths(data, key))
        missing = frozen - current
        if missing:
            raise OntologyError(
                f"migration registry dropped frozen manifests: {sorted(missing)}"
            )
        for relative in sorted(frozen):
            current_path = _safe_repository_file(
                relative, label="frozen migration manifest"
            )
            if current_path.read_bytes() != _git_blob(commit, relative):
                raise OntologyError(
                    f"frozen migration manifest changed: {relative}"
                )


def _validate_frozen_baseline(data: dict[str, Any], payload: dict[str, Any]) -> None:
    commit = payload["source_commit"]
    try:
        ancestry = subprocess.run(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "merge-base",
                "--is-ancestor",
                commit,
                "HEAD",
            ],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise OntologyError("Git executable is unavailable") from exc
    if ancestry.returncode != 0:
        raise OntologyError("root compatibility baseline is not reachable from HEAD")

    frozen_public = payload["source_public_paths"]
    frozen_ontology = _git_json(
        commit, "ontology/HSWM_REPOSITORY_ONTOLOGY.v1.json"
    )
    frozen_ontology_public = frozen_ontology.get("public_root_surface")
    if (
        not isinstance(frozen_ontology_public, list)
        or any(not isinstance(path, str) for path in frozen_ontology_public)
        or set(frozen_ontology_public) != set(frozen_public)
    ):
        raise OntologyError(
            "baseline source public paths differ from the frozen ontology"
        )
    if set(data["public_root_surface"]) != set(frozen_public):
        raise OntologyError(
            "current public root surface differs from the frozen ontology"
        )
    observed = _git_root_files(commit)
    declared = set(payload["paths"]) | set(frozen_public)
    if observed != declared:
        raise OntologyError(
            "root compatibility baseline drift: "
            f"missing={sorted(observed - declared)}, "
            f"extra={sorted(declared - observed)}"
        )
    _validate_frozen_registry(data, commit)


def _validate_active_baseline_bytes(
    payload: dict[str, Any], active_legacy: set[str]
) -> None:
    commit = payload["source_commit"]
    for relative in sorted(active_legacy):
        current = _safe_repository_file(relative, label="frozen root path")
        expected = hashlib.sha256(_git_blob(commit, relative)).hexdigest()
        observed = hashlib.sha256(current.read_bytes()).hexdigest()
        if observed != expected:
            raise OntologyError(f"frozen root path changed: {relative}")


def _validate_migrations(
    entries: Sequence[legacy_replay.MigrationEntry],
    active_legacy: set[str],
    *,
    verify_git_source: bool,
) -> tuple[int, int]:
    for entry in entries:
        old = _resolve_from_repo(entry.old_path)
        if entry.old_path in active_legacy or old.exists() or old.is_symlink():
            raise OntologyError(f"migrated path still occupies root: {entry.old_path}")
        canonical = _resolve_from_repo(entry.canonical_path)
        if canonical.is_symlink() or not canonical.is_file():
            raise OntologyError(f"canonical path is missing: {entry.canonical_path}")

    if verify_git_source:
        try:
            verified = legacy_replay.verify_migrations(REPO_ROOT)
        except legacy_replay.LegacyReplayError as exc:
            raise OntologyError(str(exc)) from exc
        if verified.get("count") != len(entries):
            raise OntologyError("legacy replay verification count mismatch")

    python_count = sum(entry.old_path.endswith(".py") for entry in entries)
    return python_count, len(entries) - python_count


def validate_root_surface(
    paths: Iterable[str],
    data: dict[str, Any],
    legacy: set[str],
    *,
    allow_missing: bool = False,
) -> None:
    public = set(data["public_root_surface"])
    roots = {path for path in paths if "/" not in path}
    allowed = public | legacy
    unexpected = roots - allowed
    missing = allowed - roots
    if unexpected or (missing and not allow_missing):
        raise OntologyError(
            "root surface drift: "
            f"unexpected={sorted(unexpected)}, "
            f"missing={sorted(missing) if not allow_missing else []}"
        )
    for relative in roots:
        _safe_repository_file(relative, label="active root path")


def validate_checkout(data: dict[str, Any]) -> dict[str, int | bool]:
    paths, from_git = repository_paths()
    entries = _migration_entries()
    baseline, legacy = load_legacy(data, entries)
    python_count, asset_count = _validate_migrations(
        entries,
        legacy,
        verify_git_source=from_git,
    )
    validate_root_surface(paths, data, legacy, allow_missing=not from_git)
    if from_git:
        _validate_frozen_baseline(data, baseline)
        _validate_active_baseline_bytes(baseline, legacy)

    return {
        "paths": len(paths),
        "legacy_root_paths": len(legacy),
        "concepts": len(data["concepts"]),
        "python_root_migrations": python_count,
        "asset_root_migrations": asset_count,
        "from_git": from_git,
    }


def main() -> int:
    data = _read_json(ONTOLOGY_PATH)
    validate_graph(data)
    result = validate_checkout(data)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
