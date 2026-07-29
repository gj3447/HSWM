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
        "binding_id": "longinus-hswm-f1-r8-deployment-power-v3-20260729",
        "implementation_commit": "b75a2a5bddf0960ae22707d059005cd8393da0c7",
        "bindings_checked": 20,
        "files_checked": 20,
        "implementation_bindings": 10,
        "test_bindings": 10,
        "baseline_changed_paths": 14,
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


@pytest.mark.parametrize(
    "path",
    [
        "prom_search_hswm/f1_target_deployment_probe.py",
        "prom_search_hswm/test_hswm_result_spool_attestation.py",
    ],
)
def test_deployment_attestation_diff_paths_are_reverse_bound(
    tmp_path: Path, path: str
) -> None:
    def mutate(value: dict[str, object]) -> None:
        value["required_target_paths"].remove(path)
        value["bindings"] = [
            binding
            for binding in value["bindings"]
            if not binding["file_line"].startswith(f"{path}:")
        ]
        if path.endswith("test_hswm_result_spool_attestation.py"):
            for binding in value["bindings"]:
                if binding["crate_script"].endswith(path):
                    binding["crate_script"] = (
                        "python -m pytest -q "
                        "prom_search_hswm/test_f1_durable_transport.py"
                    )

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(
        BindingError, match="ORPHANED: implementation baseline diff is not reverse-bound"
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


def test_label_rot_is_classified(tmp_path: Path) -> None:
    changed = _changed_manifest(
        tmp_path, lambda value: value.__setitem__("scientific_status", "CONFIRMED")
    )
    with pytest.raises(BindingError, match="LABEL_ROT: scientific status") as caught:
        verify(changed)
    assert caught.value.classification == "LABEL_ROT"


def test_directory_target_is_missing_not_file_hashed(tmp_path: Path) -> None:
    def mutate(value: dict[str, object]) -> None:
        old = "prom_search_hswm/hswm_result_spool.py"
        index = value["required_target_paths"].index(old)
        value["required_target_paths"][index] = "prom_search_hswm"
        binding = next(
            item
            for item in value["bindings"]
            if item["file_line"].startswith(f"{old}:")
        )
        binding["file_line"] = "prom_search_hswm:199"

    changed = _changed_manifest(tmp_path, mutate)
    with pytest.raises(BindingError, match="MISSING: directory/non-blob") as caught:
        verify(changed)
    assert caught.value.classification == "MISSING"
