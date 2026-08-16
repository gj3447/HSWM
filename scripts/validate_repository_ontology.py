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

    manifest_paths = python_migration_manifest_paths(data)
    old_paths: set[str] = set()
    canonical_paths: set[str] = set()
    migration_count = 0
    destination_prefixes = {
        "canonical-package": "src/hswm/",
        "research-source": "_research/",
        "maintenance-script": "scripts/",
        "test": "tests/",
    }
    for relative in manifest_paths:
        payload = _read_json(_resolve_from_repo(relative))
        schema_version = payload.get("schema_version")
        if schema_version not in {
            "hswm-python-root-migrations/v1",
            "hswm-python-root-migrations/v2",
        }:
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
            if not isinstance(canonical_path, str) or not canonical_path.endswith(".py"):
                raise OntologyError(f"invalid canonical Python path: {canonical_path!r}")
            if schema_version == "hswm-python-root-migrations/v1":
                if not canonical_path.startswith("src/hswm/"):
                    raise OntologyError(
                        f"v1 migration must target src/hswm: {canonical_path!r}"
                    )
            else:
                destination_kind = row.get("destination_kind")
                prefix = destination_prefixes.get(destination_kind)
                if prefix is None or not canonical_path.startswith(prefix):
                    raise OntologyError(
                        "migration destination kind/path mismatch: "
                        f"{destination_kind!r} -> {canonical_path!r}"
                    )
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
            migration_count += 1
            if old_path in legacy or _resolve_from_repo(old_path).exists():
                raise OntologyError(f"migrated Python path still occupies root: {old_path}")
            if not _resolve_from_repo(canonical_path).is_file():
                raise OntologyError(f"canonical Python path is missing: {canonical_path}")

            if verify_git_source:
                try:
                    source = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(REPO_ROOT),
                            "show",
                            f"{source_commit}:{old_path}",
                        ],
                        check=True,
                        capture_output=True,
                    ).stdout
                except (FileNotFoundError, subprocess.CalledProcessError) as exc:
                    raise OntologyError(
                        f"cannot resolve migrated source {source_commit}:{old_path}"
                    ) from exc
                if hashlib.sha256(source).hexdigest() != source_sha256:
                    raise OntologyError(f"migrated source digest mismatch: {old_path}")
    return migration_count


def python_migration_manifest_paths(data: dict[str, Any]) -> list[str]:
    """Return unique migration manifests while accepting the original scalar form."""

    value = data.get("python_root_migrations")
    if isinstance(value, str) and value:
        return [value]
    if (
        isinstance(value, list)
        and value
        and all(isinstance(item, str) and item for item in value)
        and len(value) == len(set(value))
    ):
        return value
    raise OntologyError("python_root_migrations must name one or more manifests")


def migration_old_paths(data: dict[str, Any]) -> set[str]:
    old_paths: set[str] = set()
    for relative in python_migration_manifest_paths(data):
        payload = _read_json(_resolve_from_repo(relative))
        for row in payload.get("migrations", []):
            old_path = row.get("old_path") if isinstance(row, dict) else None
            if isinstance(old_path, str):
                old_paths.add(old_path)
    return old_paths


def validate_python_root_classification(
    data: dict[str, Any], paths: Iterable[str]
) -> dict[str, int]:
    """Require an exact, disjoint explanation for every remaining root module."""

    relative = data.get("python_root_classification")
    if not isinstance(relative, str) or not relative:
        raise OntologyError("python_root_classification must name a manifest")
    payload = _read_json(_resolve_from_repo(relative))
    if payload.get("schema_version") != "hswm-python-root-classification/v1":
        raise OntologyError("unsupported Python root classification schema")
    if payload.get("status") != "ACTIVE_MIGRATION_RATCHET":
        raise OntologyError("unsupported Python root classification status")

    class_names = {"SHA_LOCKED", "REPLAY_HISTORY_LOCKED", "REVIEW_REQUIRED"}
    classes = payload.get("classes")
    counts = payload.get("counts")
    if not isinstance(classes, dict) or set(classes) != class_names:
        raise OntologyError("Python root classification classes are incomplete")
    if not isinstance(counts, dict):
        raise OntologyError("Python root classification counts are missing")

    classified: set[str] = set()
    for class_name in sorted(class_names):
        members = classes.get(class_name)
        if (
            not isinstance(members, list)
            or any(
                not isinstance(path, str)
                or "/" in path
                or not path.endswith(".py")
                for path in members
            )
            or len(members) != len(set(members))
        ):
            raise OntologyError(f"invalid Python root class: {class_name}")
        overlap = classified & set(members)
        if overlap:
            raise OntologyError(f"Python root classes overlap: {sorted(overlap)}")
        classified.update(members)
        if counts.get(class_name) != len(members):
            raise OntologyError(f"Python root class count mismatch: {class_name}")

    root_python = {
        path for path in paths if "/" not in path and path.endswith(".py")
    }
    if classified != root_python:
        raise OntologyError(
            "Python root classification drift: "
            f"missing={sorted(root_python - classified)}, "
            f"stale={sorted(classified - root_python)}"
        )
    observed = payload.get("observed_root_python_count")
    if observed != len(root_python) or counts.get("partition_total") != len(root_python):
        raise OntologyError("Python root partition total mismatch")

    applied = payload.get("applied_migration_manifests")
    known_manifests = set(python_migration_manifest_paths(data))
    if (
        not isinstance(applied, list)
        or not applied
        or len(applied) != len(set(applied))
        or not set(applied) <= known_manifests
    ):
        raise OntologyError("classification names unknown migration manifests")
    applied_count = 0
    for manifest in applied:
        migration_payload = _read_json(_resolve_from_repo(manifest))
        migrations = migration_payload.get("migrations")
        if not isinstance(migrations, list):
            raise OntologyError("classification migration manifest has no rows")
        applied_count += len(migrations)
    baseline_count = payload.get("baseline_root_python_count")
    if not isinstance(baseline_count, int) or baseline_count - applied_count != observed:
        raise OntologyError("Python root migration ratchet arithmetic mismatch")

    return {class_name: len(classes[class_name]) for class_name in class_names}


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
    root_classes = validate_python_root_classification(data, paths)
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
        "root_python_sha_locked": root_classes["SHA_LOCKED"],
        "root_python_replay_locked": root_classes["REPLAY_HISTORY_LOCKED"],
        "root_python_review_required": root_classes["REVIEW_REQUIRED"],
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
    parser.add_argument(
        "--prune-migrated-root",
        action="store_true",
        help="remove manifest-pinned migrations from the frozen root inventory",
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
    if args.prune_migrated_root:
        legacy_path = _resolve_from_repo(data["legacy_root_inventory"])
        payload = _read_json(legacy_path)
        migrated = migration_old_paths(data)
        payload["paths"] = [
            row for row in payload.get("paths", []) if row.get("path") not in migrated
        ]
        payload["count"] = len(payload["paths"])
        _write_json(legacy_path, payload)
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
