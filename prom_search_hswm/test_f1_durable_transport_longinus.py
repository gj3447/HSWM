from __future__ import annotations

import json
from pathlib import Path

import pytest

from prom_search_hswm.verify_f1_durable_transport_longinus import (
    BindingError,
    DEFAULT_MANIFEST,
    verify,
)


def _changed_manifest(tmp_path: Path, mutate) -> Path:
    value = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    mutate(value)
    changed = tmp_path / "binding.json"
    changed.write_text(json.dumps(value), encoding="utf-8")
    return changed


def test_checked_in_f1_r8_binding_is_exact_git_blob_bound() -> None:
    result = verify()
    assert result == {
        "status": "PASS",
        "binding_id": "longinus-hswm-f1-r8-premeasurement-c1-successor-20260729",
        "implementation_commit": "7ebffbb8fb07673f1e7a5d5c284edafd1286878a",
        "bindings_checked": 18,
        "files_checked": 18,
        "implementation_bindings": 9,
        "test_bindings": 9,
        "longinus_layers": 7,
        "classifications": {
            "MISSING": 0,
            "ORPHANED": 0,
            "SIGNATURE_MISMATCHED": 0,
            "DIVERGENT": 0,
            "LABEL_ROT": 0,
        },
        "blob_authority": "GIT_COMMIT_ONLY",
        "kg_write_state": "NOT_AUTHORIZED_NOT_WRITTEN",
        "scientific_status": "UNJUDGED",
        "b22_gate": "LOCKED",
    }


def test_verifier_never_reads_bound_python_from_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.read_text

    def guarded(path: Path, *args, **kwargs):
        if path.suffix == ".py":
            raise AssertionError(f"worktree source read: {path}")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    assert verify()["blob_authority"] == "GIT_COMMIT_ONLY"


def test_divergent_blob_sha_is_classified(tmp_path: Path) -> None:
    changed = _changed_manifest(
        tmp_path, lambda value: value["bindings"][0].__setitem__("sha256", "0" * 64)
    )
    with pytest.raises(BindingError, match="DIVERGENT: Git blob SHA drifted") as caught:
        verify(changed)
    assert caught.value.classification == "DIVERGENT"


def test_reverse_orphan_scan_is_classified(tmp_path: Path) -> None:
    changed = _changed_manifest(tmp_path, lambda value: value["bindings"].pop())
    with pytest.raises(BindingError, match="ORPHANED: target reverse scan mismatch") as caught:
        verify(changed)
    assert caught.value.classification == "ORPHANED"


def test_signature_mismatch_is_classified(tmp_path: Path) -> None:
    def mutate(value: dict[str, object]) -> None:
        value["bindings"][1]["code_symbol"]["parameters"] = ["wrong"]

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(BindingError, match="SIGNATURE_MISMATCHED:.*parameters") as caught:
        verify(changed)
    assert caught.value.classification == "SIGNATURE_MISMATCHED"


def test_label_rot_is_classified(tmp_path: Path) -> None:
    changed = _changed_manifest(
        tmp_path, lambda value: value.__setitem__("scientific_status", "CONFIRMED")
    )
    with pytest.raises(BindingError, match="LABEL_ROT: scientific status") as caught:
        verify(changed)
    assert caught.value.classification == "LABEL_ROT"


def test_directory_target_is_missing_not_file_hashed(tmp_path: Path) -> None:
    def mutate(value: dict[str, object]) -> None:
        old = value["required_target_paths"][0]
        value["required_target_paths"][0] = "prom_search_hswm"
        value["bindings"][0]["file_line"] = "prom_search_hswm:126"
        assert old == "prom_search_hswm/hswm_result_spool.py"

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(BindingError, match="MISSING: directory/non-blob") as caught:
        verify(changed)
    assert caught.value.classification == "MISSING"
