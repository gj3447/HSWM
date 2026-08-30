from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.qualify_hswm_alfworld_text_runtime import (
    CLAIM_CEILING,
    PUBLIC_SCHEMA,
    STATUS,
    QualificationError,
    _canonical_receipt,
    _canonical_distribution_name,
    public_projection,
    validate_output_paths,
)


def test_distribution_names_use_installer_canonicalization() -> None:
    assert _canonical_distribution_name("fast_downward_textworld") == "fast-downward-textworld"
    assert _canonical_distribution_name("Fast.Downward--TextWorld") == "fast-downward-textworld"


def _local_input() -> dict[str, object]:
    return {
        "schema_version": "hswm-alfworld-text-runtime-qualification/v1",
        "status": STATUS,
        "claim_ceiling": CLAIM_CEILING,
        "pool_manifest_sha256": "a" * 64,
        "local_locator_sha256": "b" * 64,
        "source_code_sha256": {"qualification_cli": "c" * 64, "runtime": "d" * 64, "worker": "e" * 64},
        "python": {"executable_sha256": "f" * 64, "version": "3.9.25"},
        "packages": {"key_versions": {"alfworld": "0.5.0"}, "installed_package_count": 1,
                     "installed_package_list_sha256": "1" * 64, "installed_packages": [{"name": "alfworld", "version": "0.5.0"}]},
        "bubblewrap": {"binary_sha256": "2" * 64, "version": "bubblewrap 0.11.0"},
        "protocol": {"fixed_action": "look", "actor_frame_count": 51, "action_count": 50},
        "terminal": {"done": True, "won": False, "success": False, "score": 0},
        "local_receipt_sha256": "3" * 64,
    }


def test_public_projection_is_canonical_digest_bound_and_has_no_game_or_content_fields() -> None:
    value = public_projection(_local_input())
    assert value["schema_version"] == PUBLIC_SCHEMA
    assert value["receipt_sha256"] == _canonical_receipt({key: item for key, item in value.items() if key != "receipt_sha256"})["receipt_sha256"]
    flattened = " ".join(_keys(value)).lower()
    for forbidden in ("uid", "path", "observation", "game", "outcome"):
        assert forbidden not in flattened
    assert "installed_packages" not in value["packages"]
    assert value["local_receipt_sha256"] == "3" * 64


def test_public_projection_refuses_private_or_missing_local_contract_fields() -> None:
    value = _local_input()
    value["private_binding"] = {"game_opaque_uid": "secret"}
    with pytest.raises(QualificationError, match="field set"):
        public_projection(value)
    value = _local_input()
    del value["terminal"]
    with pytest.raises(QualificationError, match="field set"):
        public_projection(value)


def test_output_path_policy_refuses_repository_private_receipt_and_unapproved_public_location(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; (repo / "manifests").mkdir(parents=True)
    outside = tmp_path / "external"; outside.mkdir()
    with pytest.raises(QualificationError, match="outside the repository"):
        validate_output_paths(local_receipt=repo / "private.json", public_aggregate=repo / "manifests" / "public.json", repository=repo, allow_public_outside_manifests=False)
    with pytest.raises(QualificationError, match="under repository/manifests"):
        validate_output_paths(local_receipt=outside / "private.json", public_aggregate=repo / "elsewhere.json", repository=repo, allow_public_outside_manifests=False)
    validate_output_paths(local_receipt=outside / "private.json", public_aggregate=repo / "elsewhere.json", repository=repo, allow_public_outside_manifests=True)


def test_qualification_cli_is_directly_executable_by_path() -> None:
    repository = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(repository / "scripts/qualify_hswm_alfworld_text_runtime.py"), "--help"],
        cwd=repository.parent,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Run one sealed ALFWorld" in completed.stdout


def test_checked_public_qualification_projection_if_present() -> None:
    repository = Path(__file__).resolve().parents[1]
    path = repository / "manifests/HSWM_ALFWORLD_TEXT_RUNTIME_QUALIFICATION_2026-08-30.json"
    if not path.exists():
        pytest.skip("qualification projection is generated only after the real sealed smoke")
    value = json.loads(path.read_text(encoding="utf-8"))
    unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
    assert value["receipt_sha256"] == _canonical_receipt(unsigned)["receipt_sha256"]
    assert value["schema_version"] == PUBLIC_SCHEMA
    assert value["status"] == STATUS
    assert value["claim_ceiling"] == CLAIM_CEILING
    assert value["pool_manifest_sha256"] == _sha256(
        repository / "manifests/HSWM_ALFWORLD_TEXT_CLEAN_POOL_2026-08-30.json"
    )
    assert value["source_code_sha256"] == {
        "qualification_cli": _sha256(repository / "scripts/qualify_hswm_alfworld_text_runtime.py"),
        "runtime": _sha256(repository / "src/hswm/experiments/alfworld_text_runtime.py"),
        "worker": _sha256(repository / "src/hswm/experiments/alfworld_text_worker.py"),
    }
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":")).lower()
    for forbidden in ("game_opaque_uid", "game_relative_path", "observation", "outcome_receipt", "private_binding"):
        assert forbidden not in serialized
    assert len(value["local_locator_sha256"]) == 64
    assert len(value["local_receipt_sha256"]) == 64


def _keys(value: object) -> list[str]:
    if isinstance(value, dict):
        return [str(key) for key in value] + [child for item in value.values() for child in _keys(item)]
    if isinstance(value, list):
        return [child for item in value for child in _keys(item)]
    return []


def _sha256(path: Path) -> str:
    from hashlib import sha256

    return sha256(path.read_bytes()).hexdigest()
