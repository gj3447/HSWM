"""Tests for the offline post-B DNRD-4S1 execution-config builder."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unicodedata

import pytest

import _research.dnrd.execute as dnrd_execute
from _research.dnrd.configure import (
    ConfigurationInputs,
    ConfigurationRefusal,
    configure_execution,
)
from _research.dnrd.task_family import canonical_json
from test_hswm_dnrd_execute import _fixture, _git


def _b_checkout(config: dnrd_execute.ExecutionConfig) -> None:
    _git(config.repo_root, "checkout", "--detach", config.prereg_b_commit)
    assert _git(config.repo_root, "rev-parse", "HEAD") == config.prereg_b_commit


def _fixture_production_pins(
    monkeypatch: pytest.MonkeyPatch, config: dnrd_execute.ExecutionConfig
) -> None:
    assert config.node_executable_path is not None
    assert config.python_executable_path is not None
    monkeypatch.setattr(
        dnrd_execute, "OFFICIAL_NODE_EXECUTABLE_SHA256",
        hashlib.sha256(config.node_executable_path.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        dnrd_execute, "OFFICIAL_NODE_VERSION",
        subprocess.run([str(config.node_executable_path), "--version"], text=True, capture_output=True, check=True).stdout.strip(),
    )
    monkeypatch.setattr(
        dnrd_execute, "OFFICIAL_PYTHON_EXECUTABLE_SHA256",
        hashlib.sha256(config.python_executable_path.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        dnrd_execute, "OFFICIAL_PYTHON_VERSION",
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )
    monkeypatch.setattr(dnrd_execute, "OFFICIAL_UNICODE_DATA_VERSION", unicodedata.unidata_version)
    monkeypatch.setattr(
        dnrd_execute, "OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256",
        hashlib.sha256(config.verifier_runtime_bundle_path.read_bytes()).hexdigest(),
    )


def _inputs(tmp_path: Path, config: dnrd_execute.ExecutionConfig) -> ConfigurationInputs:
    assert config.source_ci_receipt_path is not None
    assert config.preregistration_ci_receipt_path is not None
    assert config.structured_output_qualification_path is not None
    assert config.bridge_runtime_tree_manifest_path is not None
    assert config.node_executable_path is not None
    assert config.python_executable_path is not None
    assert config.bridge_state_root is not None
    assert config.attempt_registry_root is not None
    config.bridge_state_root.rmdir()
    config.attempt_registry_root.rmdir()
    config_parent = tmp_path / "published-config"
    config_parent.mkdir(mode=0o700)
    return ConfigurationInputs(
        repo_root=config.repo_root,
        preregistration_path=config.prereg_path,
        source_manifest_path=config.source_manifest_path,
        source_ci_receipt_path=config.source_ci_receipt_path,
        preregistration_ci_receipt_path=config.preregistration_ci_receipt_path,
        qualification_path=config.structured_output_qualification_path,
        runtime_manifest_path=config.bridge_runtime_tree_manifest_path,
        bridge_state_root=config.bridge_state_root,
        attempt_registry_root=config.attempt_registry_root,
        output_root=tmp_path / "future-evidence",
        config_output_path=config_parent / "dnrd4s1-config.json",
        node_executable_path=config.node_executable_path,
        python_executable_path=config.python_executable_path,
    )


def test_configure_builds_new_owner_only_config_and_passes_static_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, _, _ = _fixture(tmp_path)
    _b_checkout(fixture)
    _fixture_production_pins(monkeypatch, fixture)
    inputs = _inputs(tmp_path, fixture)

    digest = configure_execution(inputs)
    raw = inputs.config_output_path.read_bytes()
    assert raw == canonical_json(json.loads(raw))
    assert not raw.endswith(b"\n")
    assert digest == hashlib.sha256(raw).hexdigest()
    assert inputs.config_output_path.stat().st_mode & 0o777 == 0o400
    assert inputs.bridge_state_root.stat().st_mode & 0o777 == 0o700
    assert inputs.attempt_registry_root.stat().st_mode & 0o777 == 0o700
    assert not list(inputs.bridge_state_root.iterdir())
    assert not list(inputs.attempt_registry_root.iterdir())
    assert not inputs.output_root.exists()

    loaded = dnrd_execute._config_from_json(inputs.config_output_path)
    assert loaded.prereg_b_commit == fixture.prereg_b_commit
    assert loaded.source_a_commit == fixture.source_a_commit
    assert loaded.bridge_state_root == inputs.bridge_state_root
    dnrd_execute._verify_static_pins(loaded, require_official_runtime_identity=True)


def test_configure_refuses_existing_mutable_or_output_paths_without_creating_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, _, _ = _fixture(tmp_path)
    _b_checkout(fixture)
    _fixture_production_pins(monkeypatch, fixture)
    inputs = _inputs(tmp_path, fixture)
    inputs.output_root.mkdir()

    with pytest.raises(ConfigurationRefusal, match="evidence output root must be new"):
        configure_execution(inputs)
    assert not inputs.config_output_path.exists()
    assert not inputs.bridge_state_root.exists()
    assert not inputs.attempt_registry_root.exists()


def test_configure_refuses_registry_not_b_pinned_state_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, _, _ = _fixture(tmp_path)
    _b_checkout(fixture)
    _fixture_production_pins(monkeypatch, fixture)
    inputs = _inputs(tmp_path, fixture)
    wrong = tmp_path / "other-registry"
    with pytest.raises(ConfigurationRefusal, match="bridge-state parent/attempt-registry"):
        configure_execution(replace(inputs, attempt_registry_root=wrong))
    assert not inputs.config_output_path.exists()
    assert not inputs.bridge_state_root.exists()
    assert not wrong.exists()


def test_configure_removes_its_new_config_and_roots_if_round_trip_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, _, _ = _fixture(tmp_path)
    _b_checkout(fixture)
    _fixture_production_pins(monkeypatch, fixture)
    inputs = _inputs(tmp_path, fixture)

    def fail_round_trip(_: Path) -> dnrd_execute.ExecutionConfig:
        raise dnrd_execute.ExecutionRefusal("injected config-loader failure")

    monkeypatch.setattr(dnrd_execute, "_config_from_json", fail_round_trip)
    with pytest.raises(ConfigurationRefusal, match="injected config-loader failure"):
        configure_execution(inputs)
    assert not inputs.config_output_path.exists()
    assert not inputs.bridge_state_root.exists()
    assert not inputs.attempt_registry_root.exists()
