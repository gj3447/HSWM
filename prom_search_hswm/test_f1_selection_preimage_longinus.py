from __future__ import annotations

import json
from pathlib import Path

import pytest

from prom_search_hswm.verify_f1_selection_preimage_longinus import (
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


def test_checked_in_selection_preimage_binding_is_exact_git_blob_bound() -> None:
    assert verify() == {
        "status": "PASS",
        "binding_id": "longinus-hswm-f1-r8-selection-preimage-v11-20260730",
        "baseline_ancestor": "7af2ad71777aca268497a13fd30d127abfd7e855",
        "implementation_commit": "c0c5cef13262a19b0e6669cd2fd85c36320c5cee",
        "implementation_actual_parent": "8bdb7eeb401acc9dd2a34036cc209485698ca03f",
        "binding_source_commit": "c0c5cef13262a19b0e6669cd2fd85c36320c5cee",
        "incident_artifact_source_commit": (
            "d5a918da4fc691d4e47a320e23fc6ba5c42065db"
        ),
        "incident_artifact_source_parent": (
            "624cab85f794ee4b64bb8616ae172c1bf2e9c985"
        ),
        "bindings_checked": 4,
        "files_checked": 4,
        "implementation_bindings": 2,
        "test_bindings": 1,
        "artifact_bindings": 1,
        "implementation_changed_paths": 2,
        "unchanged_relevant_paths": 2,
        "longinus_layers": 7,
        "classifications": {
            "MISSING": 0,
            "ORPHANED": 0,
            "SIGNATURE_MISMATCHED": 0,
            "DIVERGENT": 0,
            "LABEL_ROT": 0,
        },
        "blob_authority": "GIT_COMMIT_ONLY",
        "predecessor_binding_id": (
            "longinus-hswm-f1-r8-durable-resume-v10-20260730"
        ),
        "selection_receipt_sha256": (
            "e2d36903dafb6b5e1387c9969ce9fb60cbd315c24f1d51e30618579291d9d6b8"
        ),
        "incident_receipt_sha256": (
            "f97634c0c4185b9bdbe983d6fe5fffc672e6c625923f027a780433acfc714afd"
        ),
        "kg_write_state": "NOT_AUTHORIZED_NOT_WRITTEN",
        "scientific_status": "UNJUDGED",
        "b22_gate": "LOCKED",
        "historical_upstream_model_calls": 1,
        "prospective_successor_model_calls": 0,
    }


def test_verifier_never_reads_bound_python_from_worktree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.read_text

    def guarded(path: Path, *args, **kwargs):
        if path.suffix == ".py":
            raise AssertionError(f"worktree source read: {path}")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    assert verify()["blob_authority"] == "GIT_COMMIT_ONLY"


def test_verifier_ignores_ambient_git_control_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "forged-git-dir"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "forged-work-tree"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "forged-index"))
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(tmp_path / "forged-objects"))
    assert verify()["status"] == "PASS"


def test_active_selection_boundary_mutation_is_label_rot(tmp_path: Path) -> None:
    changed = _changed_manifest(
        tmp_path,
        lambda value: value["selection_boundary"].__setitem__(
            "selection_file_sha256", "0" * 64
        ),
    )
    with pytest.raises(BindingError, match="LABEL_ROT: active selection boundary"):
        verify(changed)


def test_superseded_boundary_cannot_be_erased(tmp_path: Path) -> None:
    changed = _changed_manifest(
        tmp_path,
        lambda value: value["superseded_interim"].__setitem__(
            "incident_v1_self_sha256", "0" * 64
        ),
    )
    with pytest.raises(BindingError, match="LABEL_ROT: superseded interim"):
        verify(changed)


def test_changed_path_reverse_orphan_is_classified(tmp_path: Path) -> None:
    changed = _changed_manifest(
        tmp_path, lambda value: value["bindings"].pop(0)
    )
    with pytest.raises(BindingError, match="ORPHANED: binding inventory"):
        verify(changed)


def test_bound_blob_divergence_is_classified(tmp_path: Path) -> None:
    changed = _changed_manifest(
        tmp_path,
        lambda value: value["bindings"][0].__setitem__("sha256", "0" * 64),
    )
    with pytest.raises(BindingError, match="DIVERGENT: Git blob SHA drifted"):
        verify(changed)


def test_symbol_signature_mismatch_is_classified(tmp_path: Path) -> None:
    changed = _changed_manifest(
        tmp_path,
        lambda value: value["bindings"][0]["code_symbol"].__setitem__(
            "signature_sha256", "0" * 64
        ),
    )
    with pytest.raises(BindingError, match="SIGNATURE_MISMATCHED"):
        verify(changed)


def test_unchanged_provenance_inventory_cannot_rotate(tmp_path: Path) -> None:
    changed = _changed_manifest(
        tmp_path,
        lambda value: value["change_inventory"].__setitem__(
            "unchanged_relevant_paths", []
        ),
    )
    with pytest.raises(BindingError, match="LABEL_ROT: change inventory"):
        verify(changed)


@pytest.mark.parametrize(
    ("field", "value"),
    (("scientific_status", "PROGRESSIVE"), ("model_calls", 0)),
)
def test_scientific_and_model_call_labels_remain_locked(
    tmp_path: Path, field: str, value: object
) -> None:
    changed = _changed_manifest(
        tmp_path, lambda manifest: manifest.__setitem__(field, value)
    )
    with pytest.raises(BindingError, match="LABEL_ROT"):
        verify(changed)


def test_artifact_source_coordinate_cannot_rotate(tmp_path: Path) -> None:
    changed = _changed_manifest(
        tmp_path,
        lambda value: value["git"].__setitem__(
            "incident_artifact_source_commit",
            "624cab85f794ee4b64bb8616ae172c1bf2e9c985",
        ),
    )
    with pytest.raises(BindingError, match="LABEL_ROT: git coordinate drifted"):
        verify(changed)
