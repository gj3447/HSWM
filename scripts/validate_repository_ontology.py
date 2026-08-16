#!/usr/bin/env python3
"""Validate the ontology-first repository projection and its path catalog."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = REPO_ROOT / "ontology" / "HSWM_REPOSITORY_ONTOLOGY.v1.json"
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


class OntologyError(ValueError):
    """The repository ontology is internally inconsistent or out of date."""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _resolve_from_repo(relative: str) -> Path:
    return REPO_ROOT / relative


def validate_graph(data: dict[str, Any]) -> None:
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
            raise OntologyError(f"concept directory lacks README: {concept['directory']}")

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

    analogy = data.get("learning_analogy", {})
    mapping = analogy.get("mapping", {})
    required_mapping = {
        "training_data",
        "parameters",
        "optimizer_signal",
        "forward_pass",
        "validation",
    }
    if set(mapping) != required_mapping or not analogy.get("necessary_condition"):
        raise OntologyError("learning analogy is incomplete")


def repository_paths() -> tuple[list[str], bool]:
    """Return repository-relative files and whether the list came from Git."""
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
    except (FileNotFoundError, subprocess.CalledProcessError):
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

    candidates = proc.stdout.decode("utf-8").split("\0")
    paths = []
    for relative in candidates:
        if not relative:
            continue
        path = REPO_ROOT / relative
        # The index can still name an unstaged deletion. It is not part of the
        # working repository projection that will be committed.
        if path.exists() or path.is_symlink():
            paths.append(Path(relative).as_posix())
    return sorted(set(paths)), True


def _matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern)


def concepts_for_path(
    path: str,
    data: dict[str, Any],
    legacy_paths: set[str],
) -> list[str]:
    concepts: set[str] = set()
    for mount in data["mounts"]:
        ordinary_match = any(
            _matches(path, pattern) for pattern in mount.get("patterns", [])
        )
        root_match = "/" not in path and any(
            _matches(path, pattern) for pattern in mount.get("root_patterns", [])
        )
        if ordinary_match or root_match:
            concepts.update(mount["concepts"])
    if path in legacy_paths:
        concepts.add("hswm:repo:history")
    return sorted(concepts)


def _kind(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".json": "json",
        ".md": "markdown",
        ".py": "python",
        ".sh": "shell",
        ".txt": "text",
        ".log": "log",
        ".toml": "toml",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".png": "image",
    }.get(suffix, "other")


def _storage_role(path: str, public: set[str], legacy: set[str]) -> str:
    if path in public:
        return "PUBLIC_ROOT"
    if path in legacy:
        return "LEGACY_PATH_BOUND_ROOT"
    return "CANONICAL_DIRECTORY"


def _legacy_payload(data: dict[str, Any], paths: Iterable[str]) -> dict[str, Any]:
    public = set(data["public_root_surface"])
    roots = sorted(path for path in paths if "/" not in path and path not in public)
    reason_by_kind = {
        "python": "legacy-flat-module: imports, packaging, sibling lookup, or historical SHA may bind this path",
        "markdown": "legacy research record: incoming links or historical SHA may bind this path",
        "json": "legacy artifact: a writer, reader, manifest, or receipt may bind this path",
        "text": "preserved source text or user-canon preimage",
        "log": "historical run output",
        "shell": "legacy root command with possible cwd-relative behavior",
    }
    return {
        "$schema": "../../schemas/hswm_legacy_root_paths.v1.schema.json",
        "schema_version": "hswm-legacy-root-paths/v1",
        "status": "FROZEN_COMPATIBILITY_SURFACE",
        "policy": "No new path may be added here without an explicit migration audit.",
        "count": len(roots),
        "paths": [
            {
                "path": path,
                "kind": _kind(path),
                "reason": reason_by_kind.get(_kind(path), "legacy root compatibility path"),
            }
            for path in roots
        ],
    }


def load_legacy(data: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    payload = _read_json(_resolve_from_repo(data["legacy_root_inventory"]))
    if payload.get("schema_version") != "hswm-legacy-root-paths/v1":
        raise OntologyError("unsupported legacy-root inventory schema")
    listed = [row.get("path") for row in payload.get("paths", [])]
    if len(listed) != len(set(listed)) or None in listed:
        raise OntologyError("legacy root paths must be present and unique")
    if payload.get("count") != len(listed) or any("/" in path for path in listed):
        raise OntologyError("legacy root count/path shape mismatch")
    if set(listed) & set(data["public_root_surface"]):
        raise OntologyError("public and legacy root surfaces overlap")
    return payload, set(listed)


def validate_python_root_migrations(
    data: dict[str, Any],
    legacy: set[str],
    *,
    verify_git_source: bool,
) -> int:
    """Validate explicit root-to-package moves without rewriting old evidence.

    A source checkout can also prove the old bytes against the pinned commit.
    Source distributions lack Git objects, so they still enforce the structural
    half of the contract: old root absent, canonical path present, and no stale
    legacy-root exception.
    """

    relative = data.get("python_root_migrations")
    if not isinstance(relative, str) or not relative:
        raise OntologyError("python_root_migrations must name a manifest")
    payload = _read_json(_resolve_from_repo(relative))
    if payload.get("schema_version") != "hswm-python-root-migrations/v1":
        raise OntologyError("unsupported Python root migration schema")
    if payload.get("status") != "SOURCE_PINNED_PATH_MIGRATION":
        raise OntologyError("unsupported Python root migration status")

    source_commit = payload.get("source_commit")
    if (
        not isinstance(source_commit, str)
        or len(source_commit) != 40
        or any(ch not in "0123456789abcdef" for ch in source_commit)
    ):
        raise OntologyError("Python migration source_commit must be a full Git SHA")

    rows = payload.get("migrations", [])
    if not isinstance(rows, list) or not rows:
        raise OntologyError("Python migration manifest must contain migrations")
    old_paths: set[str] = set()
    canonical_paths: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise OntologyError("Python migration row must be an object")
        old_path = row.get("old_path")
        canonical_path = row.get("canonical_path")
        source_sha256 = row.get("source_sha256")
        if (
            not isinstance(old_path, str)
            or "/" in old_path
            or not old_path.endswith(".py")
        ):
            raise OntologyError(f"invalid migrated root path: {old_path!r}")
        if (
            not isinstance(canonical_path, str)
            or not canonical_path.startswith("src/hswm/")
            or not canonical_path.endswith(".py")
        ):
            raise OntologyError(f"invalid canonical Python path: {canonical_path!r}")
        if (
            not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in source_sha256)
        ):
            raise OntologyError(f"invalid source digest for {old_path}")
        if old_path in old_paths or canonical_path in canonical_paths:
            raise OntologyError("duplicated Python migration path")
        old_paths.add(old_path)
        canonical_paths.add(canonical_path)
        if old_path in legacy or _resolve_from_repo(old_path).exists():
            raise OntologyError(f"migrated Python path still occupies root: {old_path}")
        if not _resolve_from_repo(canonical_path).is_file():
            raise OntologyError(f"canonical Python path is missing: {canonical_path}")

        if verify_git_source:
            try:
                source = subprocess.run(
                    ["git", "-C", str(REPO_ROOT), "show", f"{source_commit}:{old_path}"],
                    check=True,
                    capture_output=True,
                ).stdout
            except (FileNotFoundError, subprocess.CalledProcessError) as exc:
                raise OntologyError(
                    f"cannot resolve migrated source {source_commit}:{old_path}"
                ) from exc
            if hashlib.sha256(source).hexdigest() != source_sha256:
                raise OntologyError(f"migrated source digest mismatch: {old_path}")
    return len(rows)


def build_catalog(
    data: dict[str, Any],
    paths: Iterable[str],
    legacy: set[str],
) -> dict[str, Any]:
    public = set(data["public_root_surface"])
    entries = []
    for path in sorted(paths):
        concepts = concepts_for_path(path, data, legacy)
        if not concepts:
            raise OntologyError(f"unclassified repository path: {path}")
        entries.append(
            {
                "path": path,
                "kind": _kind(path),
                "storage_role": _storage_role(path, public, legacy),
                "concepts": concepts,
            }
        )
    counts: dict[str, int] = {}
    for concept in (row["uid"] for row in data["concepts"]):
        counts[concept] = sum(concept in entry["concepts"] for entry in entries)
    return {
        "$schema": "../schemas/hswm_path_catalog.v1.schema.json",
        "schema_version": "hswm-path-catalog/v1",
        "ontology": "ontology/HSWM_REPOSITORY_ONTOLOGY.v1.json",
        "entry_count": len(entries),
        "concept_counts": counts,
        "entries": entries,
    }


def validate_root_surface(
    paths: Iterable[str],
    data: dict[str, Any],
    legacy: set[str],
) -> None:
    public = set(data["public_root_surface"])
    roots = {path for path in paths if "/" not in path}
    if roots != public | legacy:
        raise OntologyError(
            "root surface drift: "
            f"unexpected={sorted(roots - public - legacy)}, "
            f"missing={sorted((public | legacy) - roots)}"
        )


def validate_checkout(data: dict[str, Any]) -> dict[str, int | bool]:
    paths, from_git = repository_paths()
    _, legacy = load_legacy(data)
    migration_count = validate_python_root_migrations(
        data, legacy, verify_git_source=from_git
    )
    if from_git:
        validate_root_surface(paths, data, legacy)

    expected = build_catalog(data, paths, legacy)
    catalog = _read_json(_resolve_from_repo(data["path_catalog"]))
    if catalog.get("schema_version") != "hswm-path-catalog/v1":
        raise OntologyError("unsupported path catalog schema")
    catalog_paths = [row.get("path") for row in catalog.get("entries", [])]
    if len(catalog_paths) != len(set(catalog_paths)) or None in catalog_paths:
        raise OntologyError("catalog paths must be present and unique")
    if catalog.get("entry_count") != len(catalog_paths):
        raise OntologyError("catalog entry_count mismatch")

    expected_by_path = {row["path"]: row for row in expected["entries"]}
    catalog_by_path = {row["path"]: row for row in catalog["entries"]}
    compared_paths = set(expected_by_path)
    if from_git and compared_paths != set(catalog_by_path):
        raise OntologyError(
            "path catalog drift: "
            f"missing={sorted(compared_paths - set(catalog_by_path))[:10]}, "
            f"stale={sorted(set(catalog_by_path) - compared_paths)[:10]}"
        )
    if not from_git:
        compared_paths &= set(catalog_by_path)
    for path in sorted(compared_paths):
        if expected_by_path[path] != catalog_by_path[path]:
            raise OntologyError(f"catalog classification drift: {path}")

    return {
        "paths": len(paths),
        "legacy_root_paths": len(legacy),
        "concepts": len(data["concepts"]),
        "python_root_migrations": migration_count,
        "from_git": from_git,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--initialize-legacy-root",
        action="store_true",
        help="write the initial frozen legacy-root inventory",
    )
    parser.add_argument(
        "--write-path-catalog",
        action="store_true",
        help="regenerate the derived path-to-concept catalog",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = _read_json(ONTOLOGY_PATH)
    validate_graph(data)
    paths, _ = repository_paths()

    if args.initialize_legacy_root:
        _write_json(
            _resolve_from_repo(data["legacy_root_inventory"]),
            _legacy_payload(data, paths),
        )
        paths, _ = repository_paths()
    _, legacy = load_legacy(data)
    if args.write_path_catalog:
        catalog_relative = data["path_catalog"]
        if catalog_relative not in paths:
            paths = sorted([*paths, catalog_relative])
        _write_json(
            _resolve_from_repo(catalog_relative),
            build_catalog(data, paths, legacy),
        )

    result = validate_checkout(data)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
