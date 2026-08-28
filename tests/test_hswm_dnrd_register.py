"""Cross-contract tests for the offline DNRD-4S1 preregistration-B builder."""

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
import _research.dnrd.register as dnrd_register
from _research.dnrd.register import (
    RegistrationInputs,
    RegistrationRefusal,
    build_preregistration,
    main,
    validate_preregistration_value,
    write_preregistration,
)
from _research.dnrd.task_family import canonical_json
from test_hswm_dnrd_execute import _fixture, _git


def _inputs(config: dnrd_execute.ExecutionConfig) -> RegistrationInputs:
    assert config.source_ci_receipt_path is not None
    assert config.bridge_runtime_tree_manifest_path is not None
    assert config.structured_output_qualification_path is not None
    assert config.bridge_runtime_root is not None
    assert config.bridge_state_root is not None
    assert config.node_executable_path is not None
    assert config.python_executable_path is not None
    return RegistrationInputs(
        repo_root=config.repo_root,
        source_manifest_path=config.source_manifest_path,
        source_ci_receipt_path=config.source_ci_receipt_path,
        runtime_manifest_path=config.bridge_runtime_tree_manifest_path,
        qualification_path=config.structured_output_qualification_path,
        model_endpoint=config.model_endpoint,
        bridge_runtime_root=config.bridge_runtime_root,
        bridge_implementation_path=config.bridge_implementation_path,
        bridge_state_root=config.bridge_state_root,
        scorer_implementation_path=config.scorer_implementation_path,
        node_executable_path=config.node_executable_path,
        python_executable_path=config.python_executable_path,
        verifier_helper_path=config.verifier_helper_path,
        verifier_package_lock_path=config.verifier_package_lock_path,
        verifier_runtime_bundle_path=config.verifier_runtime_bundle_path,
        created_at="2026-08-28",
    )


def _source_a_checkout(config: dnrd_execute.ExecutionConfig) -> None:
    _git(config.repo_root, "checkout", "--detach", config.source_a_commit)
    assert _git(config.repo_root, "rev-parse", "HEAD") == config.source_a_commit


def _fixture_production_pins(
    monkeypatch: pytest.MonkeyPatch, inputs: RegistrationInputs
) -> None:
    """The hermetic execute fixture is intentionally not the production runtime."""

    monkeypatch.setattr(
        dnrd_register,
        "OFFICIAL_NODE_EXECUTABLE_SHA256",
        hashlib.sha256(inputs.node_executable_path.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        dnrd_register,
        "OFFICIAL_NODE_VERSION",
        subprocess.run(
            [str(inputs.node_executable_path), "--version"], text=True, capture_output=True, check=True
        ).stdout.strip(),
    )
    monkeypatch.setattr(
        dnrd_register,
        "OFFICIAL_PYTHON_EXECUTABLE_SHA256",
        hashlib.sha256(inputs.python_executable_path.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        dnrd_register,
        "OFFICIAL_PYTHON_VERSION",
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )
    monkeypatch.setattr(
        dnrd_register,
        "OFFICIAL_UNICODE_DATA_VERSION",
        unicodedata.unidata_version,
    )
    monkeypatch.setattr(
        dnrd_register,
        "OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256",
        hashlib.sha256(inputs.verifier_runtime_bundle_path.read_bytes()).hexdigest(),
    )


def _bind_fixture_qualification(inputs: RegistrationInputs) -> str:
    value = json.loads(inputs.qualification_path.read_bytes())
    value["source_files"] = [
        {
            "path": relative,
            "sha256": hashlib.sha256((inputs.repo_root / relative).read_bytes()).hexdigest(),
        }
        for relative in dnrd_execute.QUALIFICATION_SOURCE_PATHS
    ]
    value["python_executable_sha256"] = hashlib.sha256(
        inputs.python_executable_path.read_bytes()
    ).hexdigest()
    value["python_version"] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    value["unicode_data_version"] = unicodedata.unidata_version
    raw = canonical_json(value) + b"\n"
    inputs.qualification_path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_registration_is_canonical_new_file_and_round_trips_executor_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _, _ = _fixture(tmp_path)
    _source_a_checkout(config)
    inputs = _inputs(config)
    qualification_sha = _bind_fixture_qualification(inputs)
    _fixture_production_pins(monkeypatch, inputs)
    assert inputs.verifier_runtime_bundle_path.resolve() == (
        inputs.repo_root / "tools/swm0w_drand/node_modules/drand-client/build/esm/index.mjs"
    )
    assert dnrd_register.OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256 == hashlib.sha256(
        inputs.verifier_runtime_bundle_path.read_bytes()
    ).hexdigest()
    output = config.repo_root / "prereg" / "PREREG_HSWM_DNRD_4S1_2026-08-28.json"
    output.parent.mkdir()

    digest = write_preregistration(inputs=inputs, output=output)
    raw = output.read_bytes()
    assert raw == canonical_json(json.loads(raw))
    assert not raw.endswith(b"\n")
    assert digest == hashlib.sha256(raw).hexdigest()
    assert json.loads(raw)["authority"] == {
        "broad_research_continuation_requested": True,
        "measurement_authorized_by_user_broad_continuation": True,
        "authorization_is_scientific_evidence": False,
        "measurement_requires_external_exact_hash_ratification_receipt": False,
        "measurement_requires_successful_preregistration_b_ci_receipt": True,
        "scientific_judgment_emitted": False,
        "external_governance_required": False,
    }

    # This is deliberately a second implementation's contract check: the
    # execution boundary accepts the builder's exact value without register
    # calling into its preregistration validator.
    config_for_prereg = replace(
        config,
        prereg_path=output.relative_to(config.repo_root).as_posix(),
        prereg_sha256=digest,
        structured_output_qualification_sha256=qualification_sha,
    )
    source_ci, _, _ = dnrd_execute._load_source_ci_receipt(config_for_prereg)
    assert dnrd_execute._validate_preregistration(config_for_prereg, source_ci_receipt=source_ci) == json.loads(raw)

    with pytest.raises(RegistrationRefusal, match="overwrite"):
        write_preregistration(inputs=inputs, output=output)


def test_registration_refuses_noncanonical_external_runtime_file_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _, _ = _fixture(tmp_path)
    _source_a_checkout(config)
    inputs = _inputs(config)
    _bind_fixture_qualification(inputs)
    _fixture_production_pins(monkeypatch, inputs)
    runtime = json.loads(inputs.runtime_manifest_path.read_bytes())
    rows = next(
        package["files"]
        for package in runtime["external_packages"]
        if len(package["files"]) >= 2
    )
    rows.reverse()
    inputs.runtime_manifest_path.write_bytes(canonical_json(runtime))

    with pytest.raises(RegistrationRefusal, match="canonically sorted"):
        build_preregistration(inputs)


def test_registration_refuses_dynamic_pin_or_fixed_contract_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _, _ = _fixture(tmp_path)
    _source_a_checkout(config)
    inputs = _inputs(config)
    _bind_fixture_qualification(inputs)
    monkeypatch.setattr(dnrd_register, "OFFICIAL_NODE_EXECUTABLE_SHA256", "0" * 64)
    with pytest.raises(RegistrationRefusal, match="Node pin"):
        build_preregistration(inputs)
    _fixture_production_pins(monkeypatch, inputs)
    value = build_preregistration(inputs)
    value["authority"]["authorization_is_scientific_evidence"] = True
    with pytest.raises(RegistrationRefusal, match="authority"):
        validate_preregistration_value(value)

    qualification = inputs.qualification_path
    original = qualification.read_bytes()
    qualification.write_bytes(original.replace(inputs.model_endpoint.encode(), b"http://127.0.0.1:1"))
    with pytest.raises(RegistrationRefusal, match="qualification"):
        build_preregistration(inputs)
    qualification.write_bytes(original)

    qualification_value = json.loads(original)
    qualification_value["source_files"].reverse()
    qualification.write_bytes(canonical_json(qualification_value) + b"\n")
    with pytest.raises(RegistrationRefusal, match="source-file order"):
        build_preregistration(inputs)
    qualification.write_bytes(original)

    qualification_value = json.loads(original)
    qualification_value["python_version"] = "0.0.0"
    qualification.write_bytes(canonical_json(qualification_value) + b"\n")
    with pytest.raises(RegistrationRefusal, match="Python/Unicode runtime identities"):
        build_preregistration(inputs)
    qualification.write_bytes(original)

    bad_runtime_root = tmp_path / "other-runtime"
    bad_runtime_root.mkdir()
    with pytest.raises(RegistrationRefusal, match="runtime manifest"):
        build_preregistration(replace(inputs, bridge_runtime_root=bad_runtime_root))

    runtime = json.loads(inputs.runtime_manifest_path.read_bytes())
    runtime["files"][0]["sha256"] = "0" * 64
    inputs.runtime_manifest_path.write_bytes(canonical_json(runtime))
    with pytest.raises(RegistrationRefusal, match="file hash drifted"):
        build_preregistration(inputs)

    # Restore the manifest before isolating the official drand content-address.
    runtime["files"][0]["sha256"] = hashlib.sha256(
        inputs.bridge_implementation_path.read_bytes()
    ).hexdigest()
    inputs.runtime_manifest_path.write_bytes(canonical_json(runtime))
    monkeypatch.setattr(dnrd_register, "OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256", "0" * 64)
    with pytest.raises(RegistrationRefusal, match="official runtime-bundle"):
        build_preregistration(inputs)


def test_registration_binds_qualification_to_captured_source_manifest_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _, _ = _fixture(tmp_path)
    _source_a_checkout(config)
    inputs = _inputs(config)
    _bind_fixture_qualification(inputs)
    _fixture_production_pins(monkeypatch, inputs)
    source_ci = dnrd_register._source_ci

    def mutate_after_source_identity(*args: object, **kwargs: object) -> tuple[dict, str]:
        result = source_ci(*args, **kwargs)
        live_path = inputs.repo_root / "_research/dnrd/live.py"
        live_path.write_bytes(live_path.read_bytes() + b"# after-source-manifest\n")
        qualification = json.loads(inputs.qualification_path.read_bytes())
        for source_file in qualification["source_files"]:
            if source_file["path"] == "_research/dnrd/live.py":
                source_file["sha256"] = hashlib.sha256(live_path.read_bytes()).hexdigest()
                break
        inputs.qualification_path.write_bytes(canonical_json(qualification) + b"\n")
        return result

    monkeypatch.setattr(dnrd_register, "_source_ci", mutate_after_source_identity)

    with pytest.raises(RegistrationRefusal, match="qualification source identities"):
        build_preregistration(inputs)


def test_registration_cli_writes_only_the_requested_new_b_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _, _ = _fixture(tmp_path)
    _source_a_checkout(config)
    inputs = _inputs(config)
    _bind_fixture_qualification(inputs)
    _fixture_production_pins(monkeypatch, inputs)
    output = config.repo_root / "prereg" / "cli.json"
    output.parent.mkdir()
    arguments = [
        "--repo-root", str(inputs.repo_root), "--source-manifest-path", inputs.source_manifest_path,
        "--source-ci-receipt", str(inputs.source_ci_receipt_path), "--runtime-manifest", str(inputs.runtime_manifest_path),
        "--qualification", str(inputs.qualification_path), "--model-endpoint", inputs.model_endpoint,
        "--bridge-runtime-root", str(inputs.bridge_runtime_root), "--bridge-implementation", str(inputs.bridge_implementation_path),
        "--bridge-state-root", str(inputs.bridge_state_root), "--scorer-implementation", str(inputs.scorer_implementation_path),
        "--node-executable", str(inputs.node_executable_path), "--python-executable", str(inputs.python_executable_path),
        "--verifier-helper", str(inputs.verifier_helper_path), "--verifier-package-lock", str(inputs.verifier_package_lock_path),
        "--verifier-runtime-bundle", str(inputs.verifier_runtime_bundle_path), "--created-at", inputs.created_at,
        "--output", str(output),
    ]
    assert main(arguments) == 0
    assert capsys.readouterr().out.strip() == hashlib.sha256(output.read_bytes()).hexdigest()
