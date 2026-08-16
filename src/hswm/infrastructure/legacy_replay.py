"""Materialize exact legacy root paths in an isolated detached Git checkout.

The active repository ontology names the migration manifests.  Those manifests
remain the single source of truth for ``old_path -> source_commit/source_sha256``;
this module does not maintain a second path map.  A replay workspace is always
a new standalone clone outside the live repository, so restoring an old root
path never writes it back into the active checkout.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence


LIST_SCHEMA_VERSION = "hswm-legacy-replay-list/v1"
VERIFY_SCHEMA_VERSION = "hswm-legacy-replay-verification/v1"
RECEIPT_SCHEMA_VERSION = "hswm-legacy-replay-workspace-receipt/v1"
RECEIPT_NAME = "hswm-legacy-replay.json"
ONTOLOGY_RELATIVE_PATH = Path("ontology/HSWM_REPOSITORY_ONTOLOGY.v1.json")
_REPOSITORY_MARKERS = (Path("pyproject.toml"), ONTOLOGY_RELATIVE_PATH)
_COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_OLD_PATH_RE = re.compile(r"[^/\\]+\.py\Z")


class LegacyReplayError(RuntimeError):
    """The requested replay cannot be proven or safely materialized."""


class _DuplicateJSONKey(ValueError):
    pass


@dataclass(frozen=True)
class MigrationEntry:
    old_path: str
    canonical_path: str
    source_commit: str
    source_sha256: str
    migration_manifest: str
    destination_kind: str | None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_json_file(path: Path, *, label: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _DuplicateJSONKey(f"duplicate key {key!r}")
            result[key] = value
        return result

    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, _DuplicateJSONKey) as exc:
        raise LegacyReplayError(f"cannot load strict JSON for {label}: {path}") from exc
    if not isinstance(value, dict):
        raise LegacyReplayError(f"{label} must be a JSON object: {path}")
    return value


def discover_repository_root(anchor: str | Path = __file__) -> Path:
    """Find an HSWM source checkout from a file or directory anchor."""

    try:
        resolved = Path(anchor).resolve(strict=True)
    except OSError as exc:
        raise LegacyReplayError(f"repository anchor does not exist: {anchor}") from exc
    start = resolved.parent if resolved.is_file() else resolved
    for candidate in (start, *start.parents):
        if all((candidate / marker).is_file() for marker in _REPOSITORY_MARKERS):
            return candidate
    raise LegacyReplayError(f"cannot discover HSWM repository root from {resolved}")


def _safe_repository_file(repo_root: Path, relative: Any, *, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise LegacyReplayError(f"{label} must be a non-empty repository-relative path")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
        raise LegacyReplayError(f"{label} is not a canonical repository-relative path")
    root = repo_root.resolve(strict=True)
    candidate = root / path
    if candidate.is_symlink():
        raise LegacyReplayError(f"{label} may not be a symlink: {relative}")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise LegacyReplayError(f"{label} is missing or escapes the repository: {relative}") from exc
    if not resolved.is_file():
        raise LegacyReplayError(f"{label} must be a regular file: {relative}")
    return resolved


def _git(
    repo: Path,
    *args: str,
    check: bool = True,
    text: bool = False,
) -> subprocess.CompletedProcess[Any]:
    environment = os.environ.copy()
    environment.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    })
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=check,
            capture_output=True,
            text=text,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise LegacyReplayError("Git executable is unavailable") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr if isinstance(exc.stderr, str) else (
            exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        )
        detail = stderr.strip().splitlines()[-1] if stderr.strip() else "Git command failed"
        raise LegacyReplayError(detail) from exc


def _require_git_checkout(repo_root: Path) -> Path:
    root = repo_root.resolve(strict=True)
    top = _git(root, "rev-parse", "--show-toplevel", text=True).stdout.strip()
    if Path(top).resolve() != root:
        raise LegacyReplayError(f"repository root is nested in another Git checkout: {root}")
    return root


def load_migration_entries(repo_root: str | Path) -> tuple[MigrationEntry, ...]:
    """Load the ontology-selected migration rows with no parallel path registry."""

    root = Path(repo_root).resolve(strict=True)
    ontology_path = _safe_repository_file(
        root, ONTOLOGY_RELATIVE_PATH.as_posix(), label="repository ontology",
    )
    ontology = _strict_json_file(ontology_path, label="repository ontology")
    manifest_value = ontology.get("python_root_migrations")
    if isinstance(manifest_value, str):
        manifest_paths = [manifest_value]
    elif (
        isinstance(manifest_value, list)
        and manifest_value
        and all(isinstance(item, str) for item in manifest_value)
    ):
        manifest_paths = list(manifest_value)
    else:
        raise LegacyReplayError("repository ontology has no Python migration manifests")
    if len(manifest_paths) != len(set(manifest_paths)):
        raise LegacyReplayError("repository ontology repeats a migration manifest")

    entries: list[MigrationEntry] = []
    seen_old_paths: set[str] = set()
    for relative in manifest_paths:
        manifest_path = _safe_repository_file(root, relative, label="migration manifest")
        manifest = _strict_json_file(manifest_path, label="migration manifest")
        source_commit = manifest.get("source_commit")
        if not isinstance(source_commit, str) or not _COMMIT_RE.fullmatch(source_commit):
            raise LegacyReplayError(f"invalid source_commit in {relative}")
        rows = manifest.get("migrations")
        if not isinstance(rows, list) or not rows:
            raise LegacyReplayError(f"migration manifest has no rows: {relative}")
        for row in rows:
            if not isinstance(row, Mapping):
                raise LegacyReplayError(f"migration row must be an object: {relative}")
            old_path = row.get("old_path")
            canonical_path = row.get("canonical_path")
            source_sha256 = row.get("source_sha256")
            destination_kind = row.get("destination_kind")
            if not isinstance(old_path, str) or not _OLD_PATH_RE.fullmatch(old_path):
                raise LegacyReplayError(f"invalid old_path in {relative}: {old_path!r}")
            if old_path in seen_old_paths:
                raise LegacyReplayError(f"duplicate migrated old_path: {old_path}")
            if (
                not isinstance(canonical_path, str)
                or Path(canonical_path).is_absolute()
                or ".." in Path(canonical_path).parts
                or Path(canonical_path).as_posix() != canonical_path
                or not canonical_path.endswith(".py")
            ):
                raise LegacyReplayError(
                    f"invalid canonical_path in {relative}: {canonical_path!r}"
                )
            if not isinstance(source_sha256, str) or not _SHA256_RE.fullmatch(source_sha256):
                raise LegacyReplayError(f"invalid source_sha256 for {old_path}")
            if destination_kind is not None and not isinstance(destination_kind, str):
                raise LegacyReplayError(f"invalid destination_kind for {old_path}")
            seen_old_paths.add(old_path)
            entries.append(MigrationEntry(
                old_path=old_path,
                canonical_path=canonical_path,
                source_commit=source_commit,
                source_sha256=source_sha256,
                migration_manifest=relative,
                destination_kind=destination_kind,
            ))
    return tuple(sorted(entries, key=lambda item: item.old_path))


def _entry_index(repo_root: Path) -> dict[str, MigrationEntry]:
    return {entry.old_path: entry for entry in load_migration_entries(repo_root)}


def list_migrations(repo_root: str | Path) -> dict[str, Any]:
    entries = load_migration_entries(repo_root)
    return {
        "schema_version": LIST_SCHEMA_VERSION,
        "count": len(entries),
        "entries": [asdict(entry) for entry in entries],
    }


def _verify_entry(root: Path, entry: MigrationEntry) -> dict[str, Any]:
    commit = _git(root, "rev-parse", "--verify", f"{entry.source_commit}^{{commit}}", text=True)
    resolved_commit = commit.stdout.strip()
    if resolved_commit != entry.source_commit:
        raise LegacyReplayError(
            f"source commit did not resolve exactly for {entry.old_path}: {resolved_commit}"
        )
    ancestry = _git(
        root, "merge-base", "--is-ancestor", entry.source_commit, "HEAD", check=False,
    )
    if ancestry.returncode != 0:
        raise LegacyReplayError(
            f"source commit is not reachable from HEAD for {entry.old_path}"
        )
    blob = _git(root, "show", f"{entry.source_commit}:{entry.old_path}").stdout
    observed = _sha256_bytes(blob)
    if observed != entry.source_sha256:
        raise LegacyReplayError(
            f"source blob SHA-256 mismatch for {entry.old_path}: {observed}"
        )
    tree = _git(root, "rev-parse", f"{entry.source_commit}^{{tree}}", text=True).stdout.strip()
    return {
        **asdict(entry),
        "observed_source_sha256": observed,
        "source_tree": tree,
        "verified": True,
    }


def verify_migrations(
    repo_root: str | Path,
    old_path: str | None = None,
) -> dict[str, Any]:
    """Prove commit ancestry and exact Git blob bytes for one or all rows."""

    root = _require_git_checkout(Path(repo_root))
    entries = _entry_index(root)
    if old_path is None:
        selected = tuple(entries[name] for name in sorted(entries))
    else:
        try:
            selected = (entries[old_path],)
        except KeyError as exc:
            raise LegacyReplayError(f"unknown migrated old_path: {old_path}") from exc
    verified = [_verify_entry(root, entry) for entry in selected]
    return {
        "schema_version": VERIFY_SCHEMA_VERSION,
        "repository_head": _git(root, "rev-parse", "HEAD", text=True).stdout.strip(),
        "count": len(verified),
        "entries": verified,
    }


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def _validate_destination(repo_root: Path, destination: str | Path) -> Path:
    raw = Path(destination)
    if ".." in raw.parts:
        raise LegacyReplayError("destination may not contain '..'")
    absolute = raw if raw.is_absolute() else Path.cwd() / raw
    parent = absolute.parent
    try:
        resolved_parent = parent.resolve(strict=True)
    except OSError as exc:
        raise LegacyReplayError("destination parent must already exist") from exc
    if not resolved_parent.is_dir():
        raise LegacyReplayError("destination parent must be a directory")
    resolved = resolved_parent / absolute.name
    root = repo_root.resolve(strict=True)
    if _paths_overlap(root, resolved):
        raise LegacyReplayError("destination may not equal, contain, or be inside repository")
    if os.path.lexists(absolute):
        raise LegacyReplayError("destination must not exist")
    return resolved


def _clone_without_hardlinks(source: Path, destination: Path) -> None:
    environment = os.environ.copy()
    environment.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    })
    try:
        subprocess.run(
            [
                "git", "-c", "core.hooksPath=/dev/null", "clone",
                "--no-hardlinks", "--no-checkout", "--", str(source), str(destination),
            ],
            check=True,
            capture_output=True,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise LegacyReplayError("Git executable is unavailable") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        detail = stderr.strip().splitlines()[-1] if stderr.strip() else "Git clone failed"
        raise LegacyReplayError(detail) from exc


def _atomic_receipt(path: Path, payload: dict[str, Any]) -> None:
    encoded = (_canonical_json(payload) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def materialize_workspace(
    repo_root: str | Path,
    old_path: str,
    destination: str | Path,
) -> dict[str, Any]:
    """Create and attest a full detached standalone clone for ``old_path``."""

    root = _require_git_checkout(Path(repo_root))
    entries = _entry_index(root)
    try:
        requested = entries[old_path]
    except KeyError as exc:
        raise LegacyReplayError(f"unknown migrated old_path: {old_path}") from exc
    same_commit = tuple(
        entry for entry in entries.values()
        if entry.source_commit == requested.source_commit
    )
    verified_before = [_verify_entry(root, entry) for entry in same_commit]
    target = _validate_destination(root, destination)

    _clone_without_hardlinks(root, target)
    _git(
        target, "-c", "core.hooksPath=/dev/null", "checkout", "--detach",
        requested.source_commit,
    )
    checkout_head = _git(target, "rev-parse", "HEAD", text=True).stdout.strip()
    if checkout_head != requested.source_commit:
        raise LegacyReplayError("materialized checkout HEAD differs from source commit")
    symbolic = _git(target, "symbolic-ref", "-q", "HEAD", check=False, text=True)
    if symbolic.returncode == 0:
        raise LegacyReplayError("materialized checkout is not detached")
    if symbolic.returncode not in {0, 1}:
        raise LegacyReplayError("cannot determine whether materialized HEAD is detached")
    alternates = target / ".git/objects/info/alternates"
    if alternates.exists() or alternates.is_symlink():
        raise LegacyReplayError("materialized clone is not object-standalone")

    checkout_sources: list[dict[str, Any]] = []
    for entry in same_commit:
        candidate = target / entry.old_path
        if candidate.is_symlink() or not candidate.is_file():
            raise LegacyReplayError(f"materialized source is missing or unsafe: {entry.old_path}")
        observed = _sha256_file(candidate)
        if observed != entry.source_sha256:
            raise LegacyReplayError(
                f"checkout file SHA-256 mismatch for {entry.old_path}: {observed}"
            )
        checkout_sources.append({
            "old_path": entry.old_path,
            "source_sha256": entry.source_sha256,
            "checkout_sha256": observed,
            "migration_manifest": entry.migration_manifest,
        })
    status = _git(target, "status", "--porcelain=v1", "--untracked-files=all", text=True)
    if status.stdout:
        raise LegacyReplayError("materialized checkout is not clean")

    tree = _git(root, "rev-parse", f"{requested.source_commit}^{{tree}}", text=True).stdout.strip()
    receipt: dict[str, Any] = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "status": "VERIFIED",
        "workspace_kind": "detached-standalone-clone",
        "requested_old_path": old_path,
        "source_repository": str(root),
        "source_repository_head": _git(root, "rev-parse", "HEAD", text=True).stdout.strip(),
        "source_commit": requested.source_commit,
        "source_tree": tree,
        "git_metadata": True,
        "detached_head": True,
        "clean_checkout": True,
        "objects_standalone": True,
        "verified_sources": sorted(checkout_sources, key=lambda item: item["old_path"]),
        "pre_materialization_verification_count": len(verified_before),
        "receipt_sha256": "",
    }
    receipt["receipt_sha256"] = _sha256_bytes(
        _canonical_json(receipt).encode("utf-8")
    )
    receipt_path = target / ".git" / RECEIPT_NAME
    _atomic_receipt(receipt_path, receipt)

    final_status = _git(
        target, "status", "--porcelain=v1", "--untracked-files=all", text=True,
    )
    if final_status.stdout:
        raise LegacyReplayError("receipt publication dirtied the replay checkout")
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="HSWM source checkout (default: discover from this module)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="list ontology-selected migrated root paths")
    verify = subparsers.add_parser("verify", help="verify commit ancestry and source blobs")
    verify.add_argument("old_path", nargs="?", help="verify one old path; omit for all")
    materialize = subparsers.add_parser(
        "materialize", help="create a detached standalone replay checkout",
    )
    materialize.add_argument("old_path")
    materialize.add_argument("destination", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        root = (
            discover_repository_root(args.repo)
            if args.repo is not None
            else discover_repository_root()
        )
        if args.command == "list":
            result = list_migrations(root)
        elif args.command == "verify":
            result = verify_migrations(root, args.old_path)
        else:
            result = materialize_workspace(root, args.old_path, args.destination)
    except LegacyReplayError as exc:
        print(f"legacy replay refused: {exc}", file=sys.stderr)
        return 2
    print(_canonical_json(result))
    return 0


__all__ = [
    "LegacyReplayError",
    "MigrationEntry",
    "RECEIPT_NAME",
    "discover_repository_root",
    "list_migrations",
    "load_migration_entries",
    "main",
    "materialize_workspace",
    "verify_migrations",
]


if __name__ == "__main__":
    raise SystemExit(main())
