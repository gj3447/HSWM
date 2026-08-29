from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from _research.dgx_q1.model_snapshot_manifest import (
    ModelSnapshotManifestRefusal,
    build_model_snapshot_manifest,
    main,
)
from _research.dnrd5.canonical_json import parse_canonical


REPOSITORY = "Example/Exact-Model"
REVISION = "a" * 40


def _snapshot(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    model = hub / "models--Example--Exact-Model"
    blobs = model / "blobs"
    snapshot = model / "snapshots" / REVISION
    blobs.mkdir(parents=True)
    snapshot.mkdir(parents=True)
    first = b"weight-bytes"
    second = b'{"model_type":"test"}'
    (blobs / sha256(first).hexdigest()).write_bytes(first)
    (blobs / sha256(second).hexdigest()).write_bytes(second)
    (snapshot / "weights.bin").symlink_to(
        Path("../../blobs") / sha256(first).hexdigest()
    )
    (snapshot / "config.json").symlink_to(
        Path("../../blobs") / sha256(second).hexdigest()
    )
    return hub


def test_manifest_binds_exact_paths_blobs_and_bytes(tmp_path: Path) -> None:
    manifest = build_model_snapshot_manifest(
        _snapshot(tmp_path), repository=REPOSITORY, revision=REVISION
    )
    assert manifest["file_count"] == 2
    assert manifest["total_byte_length"] == len(b"weight-bytes") + len(
        b'{"model_type":"test"}'
    )
    assert [row["path"] for row in manifest["files"]] == [
        "config.json",
        "weights.bin",
    ]
    assert all(len(row["sha256"]) == 64 for row in manifest["files"])
    assert len(manifest["files_sha256"]) == 64


def test_snapshot_symlink_may_not_escape_blob_store(tmp_path: Path) -> None:
    hub = _snapshot(tmp_path)
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    snapshot = hub / "models--Example--Exact-Model" / "snapshots" / REVISION
    (snapshot / "escape").symlink_to(outside)
    with pytest.raises(ModelSnapshotManifestRefusal, match="model blobs"):
        build_model_snapshot_manifest(
            hub, repository=REPOSITORY, revision=REVISION
        )


@pytest.mark.parametrize(
    ("repository", "revision"),
    [("missing-slash", REVISION), (REPOSITORY, "A" * 40), (REPOSITORY, "0")],
)
def test_identity_must_be_exact(
    tmp_path: Path, repository: str, revision: str
) -> None:
    hub = _snapshot(tmp_path)
    with pytest.raises(ModelSnapshotManifestRefusal):
        build_model_snapshot_manifest(hub, repository=repository, revision=revision)


def test_cli_writes_once_below_hswm_output_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hub = _snapshot(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(output))
    argv = [
        "--hub-root",
        str(hub),
        "--repository",
        REPOSITORY,
        "--revision",
        REVISION,
    ]
    assert main(argv) == 0
    raw = (output / "model_snapshot_manifest.json").read_bytes()
    assert parse_canonical(raw)["revision"] == REVISION
    assert main(argv) == 2
