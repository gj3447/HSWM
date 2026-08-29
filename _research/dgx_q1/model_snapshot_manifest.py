"""Content-address an exact local Hugging Face model snapshot without network I/O."""

from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256


SCHEMA = "hswm-dgx-q1-model-snapshot-manifest/v1"
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")
_BLOB_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$")
_CHUNK = 8 * 1024 * 1024


class ModelSnapshotManifestRefusal(ValueError):
    """The local snapshot cannot be reduced to the finite declared manifest."""


def _digest_file(path: Path) -> tuple[int, str]:
    digest = sha256()
    length = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(_CHUNK):
                length += len(chunk)
                digest.update(chunk)
    except OSError as error:
        raise ModelSnapshotManifestRefusal("model blob could not be read") from error
    return length, digest.hexdigest()


def _cache_name(repository: str) -> str:
    if _REPOSITORY.fullmatch(repository) is None:
        raise ModelSnapshotManifestRefusal("model repository identity is invalid")
    owner, name = repository.split("/", 1)
    return f"models--{owner}--{name}"


def build_model_snapshot_manifest(
    hub_root: Path,
    *,
    repository: str,
    revision: str,
) -> dict[str, Any]:
    """Hash every snapshot file and bind its content-addressed blob target."""

    if not isinstance(hub_root, Path) or hub_root.is_symlink() or not hub_root.is_dir():
        raise ModelSnapshotManifestRefusal("Hub root must be a real directory")
    if _REVISION.fullmatch(revision) is None:
        raise ModelSnapshotManifestRefusal("revision must be exact lowercase 40-hex")
    try:
        hub = hub_root.resolve(strict=True)
    except OSError as error:
        raise ModelSnapshotManifestRefusal("Hub root is unavailable") from error
    model_root = hub / _cache_name(repository)
    blobs = model_root / "blobs"
    snapshot = model_root / "snapshots" / revision
    try:
        model_resolved = model_root.resolve(strict=True)
        blobs_resolved = blobs.resolve(strict=True)
        snapshot_resolved = snapshot.resolve(strict=True)
    except OSError as error:
        raise ModelSnapshotManifestRefusal("model cache or exact snapshot is absent") from error
    if (
        model_root.is_symlink()
        or blobs.is_symlink()
        or snapshot.is_symlink()
        or not blobs.is_dir()
        or not snapshot.is_dir()
        or not model_resolved.is_relative_to(hub)
        or not blobs_resolved.is_relative_to(model_resolved)
        or not snapshot_resolved.is_relative_to(model_resolved)
    ):
        raise ModelSnapshotManifestRefusal("model cache directory boundary drifted")

    entries: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for candidate in sorted(snapshot.rglob("*"), key=lambda path: path.as_posix()):
        if candidate.is_dir():
            if candidate.is_symlink():
                raise ModelSnapshotManifestRefusal("snapshot directory symlink is forbidden")
            continue
        try:
            relative = PurePosixPath(candidate.relative_to(snapshot).as_posix())
        except ValueError as error:
            raise ModelSnapshotManifestRefusal("snapshot path escaped") from error
        text = relative.as_posix()
        if (
            text in seen_paths
            or text in {"", "."}
            or relative.is_absolute()
            or ".." in relative.parts
            or any(not part or "\x00" in part for part in relative.parts)
        ):
            raise ModelSnapshotManifestRefusal("snapshot relative path is invalid")
        seen_paths.add(text)
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as error:
            raise ModelSnapshotManifestRefusal("snapshot entry is dangling") from error
        if not resolved.is_file() or not resolved.is_relative_to(blobs_resolved):
            raise ModelSnapshotManifestRefusal("snapshot entry does not resolve to model blobs")
        blob_name = resolved.name
        if _BLOB_NAME.fullmatch(blob_name) is None:
            raise ModelSnapshotManifestRefusal("model blob identity is invalid")
        length, digest = _digest_file(resolved)
        entries.append(
            {
                "path": text,
                "blob": blob_name,
                "byte_length": length,
                "sha256": digest,
            }
        )
    if not entries:
        raise ModelSnapshotManifestRefusal("model snapshot is empty")
    total = sum(entry["byte_length"] for entry in entries)
    manifest = {
        "schema_version": SCHEMA,
        "repository": repository,
        "revision": revision,
        "file_count": len(entries),
        "total_byte_length": total,
        "files": entries,
    }
    return {**manifest, "files_sha256": canonical_sha256(entries)}


def _write_exclusive(path: Path, raw: bytes) -> None:
    if not path.parent.is_dir() or path.is_symlink():
        raise ModelSnapshotManifestRefusal("output parent is unavailable")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="hash an exact local HF snapshot")
    parser.add_argument("--hub-root", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output
    if output is None:
        output_root = os.environ.get("HSWM_OUTPUT_ROOT")
        if not output_root:
            return 2
        output = Path(output_root) / "model_snapshot_manifest.json"
    try:
        manifest = build_model_snapshot_manifest(
            args.hub_root,
            repository=args.repository,
            revision=args.revision,
        )
        raw = canonical_bytes(manifest)
        _write_exclusive(output, raw)
    except Exception:
        return 2
    print(
        canonical_bytes(
            {
                "file_count": manifest["file_count"],
                "manifest_sha256": sha256(raw).hexdigest(),
                "status": "MODEL_SNAPSHOT_MANIFESTED",
                "total_byte_length": manifest["total_byte_length"],
            }
        ).decode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
