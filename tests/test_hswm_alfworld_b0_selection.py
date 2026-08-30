from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from _research.dnrd5.canonical_json import canonical_bytes
from hswm.experiments.alfworld_b0_selection import (
    AlfworldB0SelectionError,
    select_prospective_b0,
    write_selection_receipts,
)


def _write_pool(tmp_path: Path) -> tuple[Path, Path]:
    records = []
    for split, groups, repeats in (("train", 9, 2), ("valid_seen", 5, 2), ("valid_unseen", 3, 1)):
        for group in range(groups):
            for repeat in range(repeats):
                name = f"{split}/{group}/{repeat}"
                records.append({"bytes": 1, "file_sha256": "a" * 64, "opaque_uid": f"opaque:{name}", "relative_path": name, "relative_path_sha256": sha256(name.encode()).hexdigest(), "split": split, "task_group_uid": f"group:{split}:{group}"})
    locator = {"schema_version": "hswm-alfworld-text-clean-pool-local-locator/v1", "records": records}
    locator_path = tmp_path / "locator.json"
    locator_path.write_text(json.dumps(locator, sort_keys=True), encoding="utf-8")
    counts = {split: sum(record["split"] == split for record in records) for split in ("train", "valid_seen", "valid_unseen")}
    groups = {split: len({record["task_group_uid"] for record in records if record["split"] == split}) for split in counts}
    manifest = {"schema_version": "hswm-alfworld-text-clean-pool/v2", "aggregate_commitment": {"local_locator_rendered_json_sha256": sha256(locator_path.read_bytes()).hexdigest(), "selected_game_counts": counts, "selected_task_group_counts": groups}}
    pool_path = tmp_path / "pool.json"
    pool_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return pool_path, locator_path


def test_selects_stably_one_game_per_group_without_unseen_identifiers(tmp_path: Path) -> None:
    pool, locator = _write_pool(tmp_path)
    first = select_prospective_b0(pool_manifest=pool, local_locator=locator, protocol_uid="protocol:test", protocol_version="v1", protocol_sha256="b" * 64)
    second = select_prospective_b0(pool_manifest=pool, local_locator=locator, protocol_uid="protocol:test", protocol_version="v1", protocol_sha256="b" * 64)
    assert first == second
    assert len(first.train) == 8 and len({row.task_group_uid for row in first.train}) == 8
    assert len(first.valid_seen) == 4 and len({row.task_group_uid for row in first.valid_seen}) == 4
    public = first.public_projection()
    rendered = canonical_bytes(public)
    assert b"opaque:" not in rendered and b"group:" not in rendered
    assert public["status"] == "PROSPECTIVE_SELECTION_ONLY_G0_NOT_RUN"


def test_rejects_locator_commitment_drift(tmp_path: Path) -> None:
    pool, locator = _write_pool(tmp_path)
    locator.write_bytes(locator.read_bytes() + b" ")
    with pytest.raises(AlfworldB0SelectionError, match="commitment"):
        select_prospective_b0(pool_manifest=pool, local_locator=locator, protocol_uid="protocol:test", protocol_version="v1", protocol_sha256="b" * 64)


def test_private_receipt_stays_outside_repository_and_public_is_aggregate_only(tmp_path: Path) -> None:
    pool, locator = _write_pool(tmp_path)
    selection = select_prospective_b0(pool_manifest=pool, local_locator=locator, protocol_uid="protocol:test", protocol_version="v1", protocol_sha256="b" * 64)
    repo = tmp_path / "repo"
    (repo / "manifests").mkdir(parents=True)
    public = repo / "manifests" / "public.json"
    private = tmp_path / "private.json"
    write_selection_receipts(selection=selection, private_output=private, public_output=public, repository_root=repo)
    assert private.exists() and public.exists()
    assert b"opaque:" in private.read_bytes()
    assert b"opaque:" not in public.read_bytes()
    with pytest.raises(AlfworldB0SelectionError, match="not already exist"):
        write_selection_receipts(selection=selection, private_output=private, public_output=public, repository_root=repo)
    with pytest.raises(AlfworldB0SelectionError, match="outside repository"):
        write_selection_receipts(selection=selection, private_output=repo / "private.json", public_output=repo / "manifests" / "other.json", repository_root=repo)
    with pytest.raises(AlfworldB0SelectionError, match="repository/manifests"):
        write_selection_receipts(selection=selection, private_output=tmp_path / "another-private.json", public_output=repo / "other.json", repository_root=repo)
