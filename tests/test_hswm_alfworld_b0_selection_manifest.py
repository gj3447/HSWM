"""Immutable public-projection checks for the committed ALFWorld B0 selection."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from _research.dnrd5.canonical_json import canonical_bytes


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPOSITORY_ROOT / "manifests/HSWM_ALFWORLD_B0_SELECTION_2026-08-30.json"
FILE_SHA256 = "20bd5b3991871a45505983c2d2cca8cb97b5a1f4a1b9994c55f8808de1603b9e"
PRIVATE_RECEIPT_FILE_SHA256 = "fbfa41028af96bd6d77ca3d7f19b3fb438ccee10f70f13ede9a6257b61062f94"
PROTOCOL_SHA256 = "5beea2a1ff11fa33f71f3b9c4caa02b46315cef68593c6dbcd096d67cb183132"
POOL_SHA256 = "68a7772f78091e6b4c0eddfde016e319be2222ce7ccb5cc1e0fd085ca0936815"
LOCATOR_SHA256 = "cfa8f4bd7357de4be5507e56c3a04d9cac789ff5bfd58786be8c3ec6c4f9e85c"
SELECTOR_SOURCE_SHA256 = "0d4d785a42dba33cfe3a4902513345a81dc8dc8125f813973b91acd5b76f2988"
SELECTION_DIGEST_SHA256 = "4da3f7d09eb62dce4b4b61ca2e5f119de8d50a22e82756c6e75389b18c9267e8"


def _manifest() -> tuple[bytes, dict[str, object]]:
    raw = MANIFEST.read_bytes()
    value = json.loads(raw)
    assert isinstance(value, dict)
    return raw, value


def _all_keys(value: object) -> list[str]:
    if isinstance(value, dict):
        return [str(key) for key in value] + [
            child for item in value.values() for child in _all_keys(item)
        ]
    if isinstance(value, list):
        return [child for item in value for child in _all_keys(item)]
    return []


def test_public_selection_manifest_is_exact_canonical_and_self_receipted() -> None:
    raw, value = _manifest()
    assert raw.endswith(b"\n") and raw.count(b"\n") == 1
    assert sha256(raw).hexdigest() == FILE_SHA256
    assert canonical_bytes(value) + b"\n" == raw
    unsigned = {key: item for key, item in value.items() if key != "public_projection_sha256"}
    assert value["public_projection_sha256"] == sha256(canonical_bytes(unsigned)).hexdigest()
    assert value["private_receipt_sha256"] == PRIVATE_RECEIPT_FILE_SHA256


def test_public_selection_manifest_binds_inputs_and_fixed_allocation() -> None:
    _raw, value = _manifest()
    assert value["schema_version"] == "hswm-alfworld-b0-selection/v1"
    assert value["record_role"] == "AGGREGATE_PROSPECTIVE_B0_SELECTION_COMMITMENT_NOT_A_RESULT"
    assert value["status"] == "PROSPECTIVE_SELECTION_ONLY_G0_NOT_RUN"
    assert value["protocol"] == {
        "uid": "sym:ExploratoryStudy:hswm-alfworld-b0-calibration-2026-08-30",
        "version": "v1",
        "protocol_file_sha256": PROTOCOL_SHA256,
    }
    assert value["selector_source_sha256"] == SELECTOR_SOURCE_SHA256
    assert value["input_commitments"] == {
        "pool_manifest_rendered_json_sha256": POOL_SHA256,
        "local_locator_rendered_json_sha256": LOCATOR_SHA256,
    }
    assert value["selection"] == {
        "algorithm": "hswm-alfworld-b0-selection/v1",
        "game_rank_domain": "HSWM_ALFWORLD_B0_GAME/v1",
        "group_rank_domain": "HSWM_ALFWORLD_B0_GROUP/v1",
        "without_replacement": True,
        "selected_group_counts": {"train": 8, "valid_seen": 4},
        "valid_unseen_record_detail_access": "NONE_BEYOND_AGGREGATE_AND_SPLIT_COUNT",
        "valid_unseen_selected_group_count": 0,
        "selection_digest_sha256": SELECTION_DIGEST_SHA256,
    }


def test_public_selection_manifest_has_no_private_identity_path_or_outcome_data() -> None:
    raw, value = _manifest()
    rendered = raw.decode("utf-8", "strict").lower()
    keys = {key.lower() for key in _all_keys(value)}
    forbidden_keys = {
        "opaque_uid",
        "task_group_uid",
        "relative_path",
        "path",
        "selected",
        "episode_uid",
        "observation",
        "trajectory",
        "action",
        "outcome",
        "outcome_receipt",
        "score",
        "won",
        "result",
    }
    assert not (keys & forbidden_keys)
    for token in forbidden_keys:
        assert f'"{token}":' not in rendered
    assert "valid_unseen" not in rendered or value["selection"][
        "valid_unseen_record_detail_access"
    ] == "NONE_BEYOND_AGGREGATE_AND_SPLIT_COUNT"
