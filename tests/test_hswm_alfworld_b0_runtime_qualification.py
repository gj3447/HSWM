from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.qualify_hswm_alfworld_b0_runtime import (
    CLAIM_CEILING,
    CONTRACT_SCHEMA,
    PUBLIC_SCHEMA,
    STATUS,
    QualificationError,
    _canonical_receipt,
    _read_contract,
    canonical_bytes,
    installed_environment,
    public_projection,
    validate_output_paths,
)
from hswm.experiments.alfworld_b0_runtime import dgx_sandbox_contract


def _private_input() -> dict[str, object]:
    return {
        "schema_version": "hswm-alfworld-b0-runtime-dgx-qualification/v1", "status": STATUS,
        "claim_ceiling": CLAIM_CEILING, "qualification_contract": {"path": "x", "file_sha256": "a" * 64},
        "execution": {"commit": "2" * 40, "tree": "3" * 40},
        "source_code_sha256": {"qualification_cli": "c" * 64}, "python": {"version": "3.9.25"},
        "packages": {"key_versions": {"alfworld": "0.5.0"}, "installed_package_count": 1, "installed_package_list_sha256": "d" * 64, "installed_packages": [{"name": "alfworld", "version": "0.5.0"}]},
        "sandbox": dgx_sandbox_contract(), "pool_manifest_sha256": "f" * 64,
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


def test_public_projection_refuses_private_text_smuggled_through_terminal() -> None:
    private = _private_input()
    terminal = private["terminal"]
    assert isinstance(terminal, dict)
    terminal["score"] = "opaque_uid:private-game"
    with pytest.raises(QualificationError, match="cannot safely project"):
        public_projection(private)


def test_checked_contract_is_canonical_immutable_and_pre_b0() -> None:
    repository = Path(__file__).resolve().parents[1]
    path = repository / "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/runtime_qualification_contract.v1.json"
    contract, binding = _read_contract(path, repository)
    assert contract["schema_version"] == CONTRACT_SCHEMA
    assert binding == sha256(path.read_bytes()).hexdigest()
    assert contract["boundary"] == {
        "no_b0_selection": True,
        "no_model_or_network_request": True,
        "no_learning_or_revision": True,
        "no_hswm_efficacy_claim": True,
        "valid_unseen_record_access": "SPLIT_TOKEN_ONLY_NO_UID_OR_PATH_DECODE_OR_RETENTION",
    }
    assert contract["registration_status"] == "PROSPECTIVE_BEFORE_ANY_B0_SELECTION_MODEL_OR_OUTCOME_CALL_AFTER_ENGINEERING_RESET_DIAGNOSTICS"
    assert contract["amendment_chronology"][0]["superseded_contract_file_sha256"] == "a3c3b55a980f97b5be67d0bc9bf0750b1e7e83cfd73f5a057980b641ed537b05"
    profile = contract["runtime_profile"]
    assert isinstance(profile, dict)
    alfworld = profile["alfworld"]
    assert isinstance(alfworld, dict)
    assert alfworld["extracted_tree_member_manifest_sha256"] == "6c956159bbedeb82f9c44a08196d78633a50f1cbd98db8036ad92c45e262048e"


def test_checked_dgx_public_qualification_is_q_bound_canonical_and_aggregate_only() -> None:
    repository = Path(__file__).resolve().parents[1]
    manifest_path = repository / "manifests/HSWM_ALFWORLD_TEXT_RUNTIME_DGX_QUALIFICATION_2026-08-30.json"
    contract_path = repository / "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/runtime_qualification_contract.v1.json"
    raw = manifest_path.read_bytes()
    value = json.loads(raw)
    assert raw == canonical_bytes(value) + b"\n"
    assert sha256(raw).hexdigest() == "a641218babb759159714f02fd539cf508997991f9469731788353941fb98595d"
    unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
    assert value["receipt_sha256"] == sha256(canonical_bytes(unsigned)).hexdigest()
    assert value["qualification_contract"] == {
        "file_sha256": sha256(contract_path.read_bytes()).hexdigest()
    }
    assert value["schema_version"] == PUBLIC_SCHEMA
    assert value["status"] == STATUS
    assert value["claim_ceiling"] == CLAIM_CEILING
    assert value["fixed_action"] == "look"
    assert value["actor_frame_count"] == 21 and value["action_count"] == 20
    assert value["terminal"] == {"done": True, "score": 0, "success": False, "won": False}
    assert value["sandbox"] == dgx_sandbox_contract()
    assert value["execution"] == {
        "commit": "e666dad4fc15584b158d3ebfc46a5b2977dd8e9f",
        "tree": "dc7317491d11d37e728edc4b80a85fe126af8277",
    }
    contract = json.loads(contract_path.read_bytes())
    sources = contract["execution_sources"]
    assert set(value["source_code_sha256"]) == set(sources)
    for name, relative in sources.items():
        committed = subprocess.run(
            ["git", "-C", str(repository), "show", f"{value['execution']['commit']}:{relative}"],
            check=True,
            capture_output=True,
        ).stdout
        assert value["source_code_sha256"][name] == sha256(committed).hexdigest()
    rendered = raw.decode("utf-8").lower()
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


def test_selected_python_probe_isolated_from_controller_python_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    python = tmp_path / "venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("stub")
    observed: dict[str, object] = {}

    class Result:
        returncode = 0
        stderr = b""
        stdout = (
            b'{"machine":"aarch64","packages":['
            b'{"name":"alfworld","version":"0.5.0"},'
            b'{"name":"textworld","version":"1.7.0"}],"version":"3.9.25"}'
        )

    def fake_run(*args: object, **kwargs: object) -> Result:
        observed.update(kwargs)
        return Result()

    monkeypatch.setenv("PYTHONPATH", "/controller/repository:/controller/repository/src")
    monkeypatch.setattr(subprocess, "run", fake_run)
    packages, _versions = installed_environment(python.resolve(), required={})
    environment = observed["env"]
    assert isinstance(environment, dict)
    assert "PYTHONPATH" not in environment and "PYTHONHOME" not in environment
    assert environment["PYTHONNOUSERSITE"] == "1"
    assert observed["cwd"] == python.parent
    assert len(packages) == 2


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
    assert "from hswm.experiments.alfworld_b0_runtime import (" in source
    assert "load_local_game_binding," in source
    assert "MAX_STEPS = 20" in source
    assert 'FIXED_ACTION = "look"' in source
    assert "import requests" not in source.lower()
    assert "urllib.request" not in source.lower()
    assert "verify_protocol" not in source
    assert "alfworld-source-archive" in source and "textworld" in source
