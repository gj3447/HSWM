from hashlib import sha256
import json
from pathlib import Path
from dataclasses import replace

import pytest

from _research.dnrd5.canonical_json import canonical_bytes
from hswm.experiments.expel_b2_selection import (
    B0_UID, ExpelB2SelectionError, select_prospective_b2, verify_private_selection,
    write_selection_receipts, main,
)
from hswm.experiments import expel_b2_protocol, expel_b2_selection


def _fixtures(tmp_path: Path) -> tuple[Path, Path, str, str]:
    rows = []
    for split, groups, repeats in (("train", 9, 2), ("valid_seen", 5, 2), ("valid_unseen", 3, 1)):
        for group in range(groups):
            for repeat in range(repeats):
                # valid_unseen decoys are deliberately invalid JSON if decoded as a record.
                if split == "valid_unseen":
                    rows.append('{"split":"valid_unseen","opaque_uid":"DO_NOT_DECODE", BAD}')
                else:
                    uid = f"{split}:{group}:{repeat}"
                    rows.append(json.dumps({"bytes": 1, "file_sha256": "a" * 64, "opaque_uid": uid, "relative_path": uid, "relative_path_sha256": sha256(uid.encode()).hexdigest(), "split": split, "task_group_uid": f"group:{split}:{group}"}, sort_keys=True))
    locator = ("{\"schema_version\":\"hswm-alfworld-text-clean-pool-local-locator/v1\",\"records\":[" + ",".join(rows) + "]}").encode()
    locator_path = tmp_path / "locator.json"; locator_path.write_bytes(locator)
    counts = {"train": 18, "valid_seen": 10, "valid_unseen": 3}
    groups = {"train": 9, "valid_seen": 5, "valid_unseen": 3}
    manifest = {"schema_version": "hswm-alfworld-text-clean-pool/v2", "aggregate_commitment": {"local_locator_rendered_json_sha256": sha256(locator).hexdigest(), "selected_game_counts": counts, "selected_task_group_counts": groups}}
    pool_path = tmp_path / "pool.json"; pool_path.write_bytes(json.dumps(manifest, sort_keys=True).encode())
    return pool_path, locator_path, sha256(pool_path.read_bytes()).hexdigest(), sha256(locator).hexdigest()


def _select(tmp_path: Path):
    pool, locator, pool_sha, locator_sha = _fixtures(tmp_path)
    return select_prospective_b2(pool_manifest=pool.absolute(), local_locator=locator.absolute(), occurrence_uid="sym:Occurrence:hswm-expel-b2-2026-09-06-a", protocol_uid="sym:ExploratoryStudy:hswm-expel-b2-2026-09-06", protocol_version="v1", protocol_sha256="b" * 64, expected_pool_manifest_sha256=pool_sha, expected_local_locator_sha256=locator_sha), pool_sha, locator_sha


def test_streams_invalid_valid_unseen_without_decoding_and_selects_groups_deterministically(tmp_path: Path) -> None:
    first, _, _ = _select(tmp_path)
    second, _, _ = _select(tmp_path)
    assert first == second
    assert len(first.train) == 8 and len({x.task_group_uid for x in first.train}) == 8
    assert len(first.valid_seen) == 4 and len({x.task_group_uid for x in first.valid_seen}) == 4
    public = first.public_projection(private_receipt_sha256="c" * 64)
    assert b"DO_NOT_DECODE" not in canonical_bytes(public)
    assert b"group:" not in canonical_bytes(public)
    assert public["selection_identity_sha256"]


def test_source_pins_and_b0_identity_are_mandatory(tmp_path: Path) -> None:
    selection, pool_sha, locator_sha = _select(tmp_path)
    with pytest.raises(ExpelB2SelectionError, match="B0"):
        select_prospective_b2(pool_manifest=tmp_path / "pool.json", local_locator=tmp_path / "locator.json", occurrence_uid="occ", protocol_uid=B0_UID, protocol_version="v1", protocol_sha256="b" * 64, expected_pool_manifest_sha256=pool_sha, expected_local_locator_sha256=locator_sha)
    with pytest.raises(ExpelB2SelectionError, match="source-pinned"):
        select_prospective_b2(pool_manifest=tmp_path / "pool.json", local_locator=tmp_path / "locator.json", occurrence_uid="occ", protocol_uid="b2", protocol_version="v1", protocol_sha256="b" * 64, expected_pool_manifest_sha256="d" * 64, expected_local_locator_sha256=locator_sha)
    assert selection.pool_manifest_sha256 == pool_sha


def test_private_verification_and_redacted_receipts(tmp_path: Path) -> None:
    selection, pool_sha, locator_sha = _select(tmp_path)
    repo = tmp_path / "repo"; (repo / "manifests").mkdir(parents=True)
    private, public = tmp_path / "private.json", repo / "manifests" / "b2.json"
    write_selection_receipts(selection=selection, private_output=private, public_output=public, repository_root=repo)
    rows = verify_private_selection(private, occurrence_uid=selection.occurrence_uid, protocol_uid=selection.protocol_uid, protocol_version="v1", protocol_sha256="b" * 64, expected_pool_manifest_sha256=pool_sha, expected_local_locator_sha256=locator_sha)
    assert len(rows) == 12
    assert b"group:" in private.read_bytes() and b"group:" not in public.read_bytes()
    value = json.loads(public.read_bytes())
    assert value["selection_identity"]["occurrence_uid"] == selection.occurrence_uid
    with pytest.raises(ExpelB2SelectionError, match="identity mismatch"):
        verify_private_selection(private, occurrence_uid="another", protocol_uid=selection.protocol_uid, protocol_version="v1", protocol_sha256="b" * 64, expected_pool_manifest_sha256=pool_sha, expected_local_locator_sha256=locator_sha)


def test_verify_inputs_reselects_and_rejects_private_receipt_drift(tmp_path: Path) -> None:
    selection, _, _ = _select(tmp_path)
    selection.verify_inputs(pool_manifest=tmp_path / "pool.json", local_locator=tmp_path / "locator.json")
    forged = replace(selection, selection_digest="d" * 64)
    with pytest.raises(ExpelB2SelectionError, match="private receipt identity or digest drifted"):
        forged.verify_inputs(pool_manifest=tmp_path / "pool.json", local_locator=tmp_path / "locator.json")


def test_cli_rejects_unfrozen_protocol_before_selector_or_locator_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = tmp_path / "protocol.json"; protocol.write_text("{}")
    called = False
    def reject(_path: Path):
        raise expel_b2_protocol.B2ProtocolError("B2 protocol is not the exact frozen source-bound contract")
    def selector(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("selector must not run for an unfrozen protocol")
    monkeypatch.setattr(expel_b2_protocol, "verify_protocol", reject)
    monkeypatch.setattr(expel_b2_selection, "select_prospective_b2", selector)
    monkeypatch.setenv("HSWM_OUTPUT_ROOT", str(tmp_path))
    monkeypatch.setenv("HSWM_CACHE_ROOT", str(tmp_path))
    with pytest.raises(expel_b2_protocol.B2ProtocolError, match="not the exact frozen"):
        main(["--protocol", str(protocol), "--pool", str(tmp_path / "pool"), "--locator", str(tmp_path / "locator")])
    assert called is False
