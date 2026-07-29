from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from prom_search_hswm.verify_f1_durable_transport_longinus import (
    BindingError,
    DEFAULT_MANIFEST,
    _definition_start,
    _signature_sha256,
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
        "binding_id": "longinus-hswm-f1-r8-durable-resume-v10-20260730",
        "baseline_ancestor": "a18a7e233da6b968c382a88c9ed9e9bf962b7576",
        "implementation_commit": "624cab85f794ee4b64bb8616ae172c1bf2e9c985",
        "implementation_actual_parent": "1dbdce8f403e91355161b47a246e336bd5d43872",
        "artifact_commit": "d5a918da4fc691d4e47a320e23fc6ba5c42065db",
        "artifact_commit_parent": "624cab85f794ee4b64bb8616ae172c1bf2e9c985",
        "binding_source_commit": "d5a918da4fc691d4e47a320e23fc6ba5c42065db",
        "bindings_checked": 17,
        "files_checked": 17,
        "implementation_bindings": 8,
        "test_bindings": 8,
        "artifact_bindings": 1,
        "implementation_changed_paths": 15,
        "artifact_changed_paths": 1,
        "binding_source_changed_paths": 16,
        "unchanged_relevant_paths": 1,
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
        "historical_upstream_model_calls": 1,
        "prospective_successor_model_calls": 0,
    }


def test_verifier_never_reads_bound_python_from_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
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


@pytest.mark.parametrize(
    "path",
    [
        "prom_search_hswm/hswm_f1_durable_transport.py",
        "prom_search_hswm/test_prom9_f1_r8_runner.py",
    ],
)
def test_git_preimage_diff_paths_are_reverse_bound(
    tmp_path: Path, path: str
) -> None:
    def mutate(value: dict[str, object]) -> None:
        value["required_target_paths"].remove(path)
        value["bindings"] = [
            binding
            for binding in value["bindings"]
            if not binding["file_line"].startswith(f"{path}:")
        ]
        if Path(path).name.startswith("test_"):
            for binding in value["bindings"]:
                if binding["crate_script"].endswith(path):
                    binding["crate_script"] = (
                        "python -m pytest -q "
                        "prom_search_hswm/test_prom9_f1_prior_exposure.py"
                    )

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(
        BindingError, match="ORPHANED: implementation/artifact diff is not reverse-bound"
    ) as caught:
        verify(changed)
    assert caught.value.classification == "ORPHANED"


def test_signature_mismatch_is_classified(tmp_path: Path) -> None:
    def mutate(value: dict[str, object]) -> None:
        value["bindings"][1]["code_symbol"]["parameters"] = ["wrong"]

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(BindingError, match="SIGNATURE_MISMATCHED:.*parameters") as caught:
        verify(changed)
    assert caught.value.classification == "SIGNATURE_MISMATCHED"


def test_signature_sha_mismatch_is_classified(tmp_path: Path) -> None:
    def mutate(value: dict[str, object]) -> None:
        value["bindings"][0]["code_symbol"]["signature_sha256"] = "0" * 64

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(
        BindingError, match="SIGNATURE_MISMATCHED:.*canonical signature drifted"
    ) as caught:
        verify(changed)
    assert caught.value.classification == "SIGNATURE_MISMATCHED"


def test_contract_role_swap_cannot_preserve_only_global_counts(tmp_path: Path) -> None:
    def mutate(value: dict[str, object]) -> None:
        implementation = value["bindings"][0]
        artifact = value["bindings"][-1]
        implementation["contract_binding"], artifact["contract_binding"] = (
            artifact["contract_binding"],
            implementation["contract_binding"],
        )

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(
        BindingError, match="LABEL_ROT:.*contract roles"
    ) as caught:
        verify(changed)
    assert caught.value.classification == "LABEL_ROT"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("def target(value):\n    pass\n", "def target(value: int):\n    pass\n"),
        ("def target(value=1):\n    pass\n", "def target(value=2):\n    pass\n"),
        ("def target(value, /):\n    pass\n", "def target(value):\n    pass\n"),
        ("def target(*, value):\n    pass\n", "def target(value):\n    pass\n"),
        ("def target(value):\n    pass\n", "def target(value) -> None:\n    pass\n"),
        ("def target(value):\n    pass\n", "async def target(value):\n    pass\n"),
    ],
)
def test_signature_hash_covers_kinds_defaults_and_annotations(
    left: str, right: str
) -> None:
    left_node = ast.parse(left).body[0]
    right_node = ast.parse(right).body[0]
    assert isinstance(left_node, (ast.FunctionDef, ast.AsyncFunctionDef))
    assert isinstance(right_node, (ast.FunctionDef, ast.AsyncFunctionDef))
    assert _signature_sha256(left, left_node) != _signature_sha256(right, right_node)


def test_definition_start_includes_all_decorators() -> None:
    source = "@first\n@second(value=1)\ndef target():\n    pass\n"
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.FunctionDef)
    assert _definition_start(node) == 1


def test_json_incident_receipt_schema_symbol_is_bound(tmp_path: Path) -> None:
    def mutate(value: dict[str, object]) -> None:
        binding = next(
            item
            for item in value["bindings"]
            if item["code_symbol"]["kind"] == "json_receipt"
        )
        binding["code_symbol"]["name"] = "hswm-prom9-f1-aborted-attempt-exposure/v0"

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(
        BindingError, match="SIGNATURE_MISMATCHED: JSON receipt schema drifted"
    ) as caught:
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
        old = "prom_search_hswm/prom9_f1_r8_transport_audit.py"
        index = value["required_target_paths"].index(old)
        value["required_target_paths"][index] = "prom_search_hswm"
        binding = next(
            item
            for item in value["bindings"]
            if item["file_line"].startswith(f"{old}:")
        )
        binding["file_line"] = "prom_search_hswm:1250"

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(BindingError, match="MISSING: directory/non-blob") as caught:
        verify(changed)
    assert caught.value.classification == "MISSING"
