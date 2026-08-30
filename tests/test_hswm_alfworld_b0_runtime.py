from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from _research.dnrd5.canonical_json import canonical_bytes
from hswm.experiments import alfworld_b0_runtime as runtime


def test_local_locator_lookup_never_json_decodes_or_retains_valid_unseen_rows(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The final-holdout sentinel may be scanned for split only, never decoded."""
    asset = tmp_path / "asset"
    game = asset / "train" / "g.tw-pddl"
    game.parent.mkdir(parents=True)
    game.write_bytes(b"game")
    selected = {
        "bytes": 4,
        "file_sha256": sha256(b"game").hexdigest(),
        "opaque_uid": "sym:OpaqueAsset:selected",
        "relative_path": "train/g.tw-pddl",
        "relative_path_sha256": sha256(b"train/g.tw-pddl").hexdigest(),
        "split": "train",
        "task_group_uid": "sym:OpaqueAssetGroup:selected",
    }
    sentinel = "VALID_UNSEEN_MUST_NEVER_BE_JSON_DECODED"
    unseen = {
        "bytes": 9,
        "file_sha256": "f" * 64,
        "opaque_uid": sentinel,
        "relative_path": f"valid_unseen/{sentinel}.tw-pddl",
        "relative_path_sha256": sha256(f"valid_unseen/{sentinel}.tw-pddl".encode()).hexdigest(),
        "split": "valid_unseen",
        "task_group_uid": sentinel,
    }
    commitment = {
        "selected_game_counts": {"train": 1, "valid_seen": 0, "valid_unseen": 1},
        "selected_game_bytes_by_split": {"train": 4, "valid_seen": 0, "valid_unseen": 9},
        "selected_task_group_counts": {"train": 1, "valid_seen": 0, "valid_unseen": 1},
        "task_group_overlap_counts": {},
        "selected_game_total": 2,
    }
    locator = {
        "schema_version": "hswm-alfworld-text-clean-pool-local-locator/v1",
        "record_role": "LOCAL_NONREPOSITORY_GAME_LOCATOR_NOT_FOR_REDISTRIBUTION",
        "source_binding": {"repository_commit": "a" * 40, "assets": []},
        "pool_commitment": commitment,
        "records": [selected, unseen],
    }
    locator_raw = (json.dumps(locator, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    manifest = {
        "schema_version": "hswm-alfworld-text-clean-pool/v2",
        "aggregate_commitment": {
            "local_locator_canonical_json_sha256": sha256(canonical_bytes(locator)).hexdigest(),
            "local_locator_rendered_json_sha256": sha256(locator_raw).hexdigest(),
            **commitment,
        },
        "source_binding": {"repository_commit": "a" * 40, "official_release_assets": []},
    }
    manifest_path = tmp_path / "manifest.json"
    locator_path = tmp_path / "locator.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    locator_path.write_bytes(locator_raw)
    original_loads = runtime.json.loads
    decoded_payloads: list[bytes] = []

    def guarded_loads(payload, *args, **kwargs):
        encoded = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        assert sentinel.encode() not in encoded, "valid_unseen sentinel was JSON-decoded"
        decoded_payloads.append(encoded)
        return original_loads(payload, *args, **kwargs)

    monkeypatch.setattr(runtime.json, "loads", guarded_loads)
    _, _, binding, bound_path = runtime.load_local_game_binding(
        pool_manifest=manifest_path,
        local_locator=locator_path,
        asset_root=asset,
        opaque_uid=selected["opaque_uid"],
    )
    assert binding.opaque_uid == selected["opaque_uid"]
    assert bound_path == game
    assert all(sentinel.encode() not in payload for payload in decoded_payloads)
