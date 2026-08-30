from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.qualify_hswm_alfworld_b0_runtime import (
    CLAIM_CEILING,
    PUBLIC_SCHEMA,
    STATUS,
    QualificationError,
    _canonical_receipt,
    installed_environment,
    public_projection,
    validate_output_paths,
)


def _private_input() -> dict[str, object]:
    return {
        "schema_version": "hswm-alfworld-b0-runtime-dgx-qualification/v1", "status": STATUS,
        "claim_ceiling": CLAIM_CEILING, "protocol": {"path": "x", "file_sha256": "a" * 64, "verified_binding_sha256": "b" * 64},
        "execution": {"commit": "2" * 40, "tree": "3" * 40},
        "source_code_sha256": {"qualification_cli": "c" * 64}, "python": {"version": "3.9.25"},
        "packages": {"key_versions": {"alfworld": "0.5.0"}, "installed_package_count": 1, "installed_package_list_sha256": "d" * 64, "installed_packages": [{"name": "alfworld", "version": "0.5.0"}]},
        "bubblewrap": {"binary_sha256": "e" * 64, "version": "bubblewrap 0.11.0"}, "pool_manifest_sha256": "f" * 64,
        "local_locator_sha256": "0" * 64, "fixed_action": "look", "actor_frame_count": 21, "action_count": 20,
        "terminal": {"done": True, "won": False, "success": False, "score": 0}, "local_receipt_file_sha256": "1" * 64,
    }


def test_public_projection_is_self_hashed_and_has_no_private_fields() -> None:
    public = public_projection(_private_input())
    assert public["schema_version"] == PUBLIC_SCHEMA and public["status"] == STATUS
    assert public["receipt_sha256"] == _canonical_receipt({k: v for k, v in public.items() if k != "receipt_sha256"})["receipt_sha256"]
    rendered = repr(public).lower()
    for forbidden in ("opaque_uid", "relative_path", "observation", "outcome_receipt", "private_binding", "installed_packages"):
        assert forbidden not in rendered


def test_output_placement_refuses_private_repo_and_requires_explicit_external_public(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; (repo / "manifests").mkdir(parents=True)
    external = tmp_path / "external"; external.mkdir()
    with pytest.raises(QualificationError, match="private receipt"):
        validate_output_paths(local_receipt=repo / "secret.json", public_aggregate=repo / "manifests" / "public.json", repository=repo, allow_public_outside_manifests=False)
    with pytest.raises(QualificationError, match="public aggregate"):
        validate_output_paths(local_receipt=external / "secret.json", public_aggregate=external / "public.json", repository=repo, allow_public_outside_manifests=False)
    validate_output_paths(local_receipt=external / "secret.json", public_aggregate=external / "public.json", repository=repo, allow_public_outside_manifests=True)


def test_selected_python_probe_rejects_non_dgx_platform_and_version(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    python = tmp_path / "python"; python.write_text("stub")
    class Result:
        returncode = 0; stderr = b""
        stdout = b'{"machine":"x86_64","packages":[],"version":"3.12.0"}'
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Result())
    with pytest.raises(QualificationError, match="requires Python 3.9.25"):
        installed_environment(python.resolve(), required={})


def test_selected_python_probe_rejects_undeclared_packages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    python = tmp_path / "python"
    python.write_text("stub")

    class Result:
        returncode = 0
        stderr = b""
        stdout = (
            b'{"machine":"aarch64","packages":['
            b'{"name":"alfworld","version":"0.5.0"},'
            b'{"name":"textworld","version":"1.7.0"},'
            b'{"name":"undeclared","version":"1"}],"version":"3.9.25"}'
        )

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Result())
    with pytest.raises(QualificationError, match="undeclared distributions"):
        installed_environment(python.resolve(), required={})


def test_cli_is_directly_executable() -> None:
    repo = Path(__file__).resolve().parents[1]
    completed = subprocess.run([sys.executable, str(repo / "scripts/qualify_hswm_alfworld_b0_runtime.py"), "--help"], cwd=repo.parent, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert "20-action ALFWorld B0 runtime" in completed.stdout


def test_qualification_source_is_fixed_look_local_only_and_uses_b0_streaming_binding() -> None:
    source = (Path(__file__).resolve().parents[1] / "scripts/qualify_hswm_alfworld_b0_runtime.py").read_text(encoding="utf-8")
    assert "from hswm.experiments.alfworld_b0_runtime import load_local_game_binding" in source
    assert "MAX_STEPS = 20" in source
    assert 'FIXED_ACTION = "look"' in source
    assert "http" not in source.lower() and "requests" not in source.lower()
