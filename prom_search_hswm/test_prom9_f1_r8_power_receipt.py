from __future__ import annotations

import copy
from functools import lru_cache
import os
from pathlib import Path
import subprocess

import pytest

from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm.prom9_f1_r8_environment import (
    R8_DEPENDENCY_NAMES,
    build_preimage_bundle,
    r8_dependency_paths,
    r8_environment_labels,
)
from prom_search_hswm.prom9_f1_r8_power import (
    BOOTSTRAP,
    POWER_DEVELOPMENT_SCHEMA,
    POWER_RECEIPT_SCHEMA,
    POWER_SIMULATOR_SCHEMA,
    SELECTED_CLUSTERS,
    TRIALS,
    _load_judge_core,
)
from prom_search_hswm.prom9_f1_r8_power_cli import (
    ENVIRONMENT_HASH_FIELDS,
    PowerCLIRefusal,
    main,
    verify_measured_environment_bundle,
    verify_power_operating_characteristics,
    write_validated_power_receipt,
)


JUDGE_PATH = (
    Path(__file__).resolve().parents[3]
    / "FINDINGS"
    / "hswm-f1-r8-try3-2026-07-28"
    / "f1_r8_lakatotree_judge.py"
)
SENSITIVITY_SCENARIOS = (
    "unequal_cluster",
    "heavy_tail",
    "seed_interaction",
    "carryover",
)


@lru_cache(maxsize=1)
def _actual_judge_power() -> tuple[
    object,
    list[dict[str, object]],
    dict[str, object],
    dict[str, object],
]:
    """Replay the real prospective judge kernel without blessing its old schema."""

    judge = _load_judge_core(JUDGE_PATH)
    contrast_pattern = (-0.001, 0.0, 0.0005, 0.001)
    components: list[dict[str, object]] = []
    for index in range(48):
        source_entity_id = canonical_sha256(
            {"kind": "prospective-power-test-entity", "index": index}
        )
        component_id = canonical_sha256(
            {
                "schema_version": "hswm-source-entity-connected-component/v1",
                "source_entity_ids": [source_entity_id],
            }
        )
        components.append(
            {
                "component_id": component_id,
                "source_entity_ids": [source_entity_id],
                "cluster_size": 2 if index % 4 in {0, 3} else 1,
                "seed_block": index // 4,
                "carryover_block": index % 2,
                "contrasts": {
                    arm: contrast_pattern[index % 4] for arm in judge.CONTROLS
                },
            }
        )
    plan = {
        "schema_version": POWER_SIMULATOR_SCHEMA,
        "trials": TRIALS,
        "master_seed": 20260728,
        "selected_cluster_count": SELECTED_CLUSTERS,
        "selection_method": "complete_seed_block_without_replacement/v1",
        "mde": 0.05,
        "target_power": 0.80,
        "scenarios": list(judge.POWER_SCENARIOS),
    }
    characteristics = judge._recompute_power_characteristics(
        components, plan, bootstrap=BOOTSTRAP
    )
    return judge, components, plan, characteristics


def _environment_hashes(bundle: dict[str, object]) -> dict[str, str]:
    environment = bundle["environment_receipt"]
    dependency = bundle["dependency_receipt"]
    assert isinstance(environment, dict)
    assert isinstance(dependency, dict)
    return {
        "environment_receipt_sha256": str(environment["receipt_sha256"]),
        "dependency_receipt_sha256": str(dependency["receipt_sha256"]),
        "environment_dependency_compatibility_root_sha256": str(
            bundle["compatibility_root_sha256"]
        ),
        "environment_dependency_bundle_sha256": str(bundle["bundle_sha256"]),
    }


def _write_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)
    return path


def _r8_dependency_paths(
    tmp_path: Path,
    *,
    judge_core_path: Path = JUDGE_PATH,
) -> dict[str, Path]:
    tokenizer = tmp_path / "tokenizer"
    paths = r8_dependency_paths(
        protocol_path=_write_text(tmp_path / "protocol.json", '{"version":1}\n'),
        judge_core_path=judge_core_path,
        result_contract_path=_write_text(
            tmp_path / "result-contract.json", '{"schema":"v1"}\n'
        ),
        tokenizer_dir=tokenizer,
        model_catalog_path=_write_text(
            tmp_path / "model-catalog.json", '{"models":[]}\n'
        ),
        model_weight_receipt_path=_write_text(
            tmp_path / "model-weight.json", '{"weights":[]}\n'
        ),
        python_lock_path=_write_text(tmp_path / "python.lock", "pytest==8.0\n"),
    )
    _write_text(tokenizer / "vocab.json", "{}\n")
    _write_text(tokenizer / "merges.txt", "#version: 0.2\n")
    _write_text(tokenizer / "tokenizer_config.json", "{}\n")
    assert set(paths) == set(R8_DEPENDENCY_NAMES)
    return paths


def _head_commit(repo_root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _initialize_test_repository(path: Path) -> str:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.invalid"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "HSWM power test"],
        check=True,
    )
    _write_text(path / "committed-marker.txt", "frozen\n")
    subprocess.run(
        ["git", "-C", str(path), "add", "committed-marker.txt"], check=True
    )
    subprocess.run(
        ["git", "-C", str(path), "commit", "-qm", "freeze test repository"],
        check=True,
    )
    return _head_commit(path)


def _bundle_context(
    dependencies: dict[str, Path],
    *,
    hswm_commit: str,
    symposium_commit: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, str]]:
    labels = r8_environment_labels(
        endpoint="https://inference.invalid/v1",
        model="measured-model",
        model_revision="measured-revision",
        run_id="f1-r8-environment-test",
        hswm_commit=hswm_commit,
        symposium_commit=symposium_commit,
    )
    bundle = build_preimage_bundle(
        dependencies,
        environ=os.environ,
        labels=labels,
    )
    hashes = _environment_hashes(bundle)
    lock: dict[str, object] = {
        **hashes,
        "hswm_commit": hswm_commit,
        "execution_policy": {"endpoint": labels["endpoint"]},
    }
    manifest: dict[str, object] = {
        "model": labels["model"],
        "model_revision": labels["model_revision"],
        "run_id": labels["run_id"],
    }
    return bundle, lock, manifest, hashes


def _allow_pre_c1_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass only pre-C1 HSWM blobs; keep SYMPOSIUM judge binding live."""

    import prom_search_hswm.prom9_f1_r8_environment as environment

    original = environment.verify_repository_dependency_blobs

    def verify_live_commit_only(
        repo_root: Path,
        expected_commit: str,
        _expected_paths: object,
        *,
        required_names: object = environment.R8_COMMIT_BOUND_DEPENDENCY_NAMES,
    ) -> tuple[str, ...]:
        if set(required_names) == set(
            environment.R8_SYMPOSIUM_COMMIT_BOUND_DEPENDENCY_NAMES
        ):
            return original(
                repo_root,
                expected_commit,
                _expected_paths,
                required_names=required_names,
            )
        environment.verify_repository_commit(repo_root, expected_commit)
        return ()

    monkeypatch.setattr(
        environment,
        "verify_repository_dependency_blobs",
        verify_live_commit_only,
    )


def _v3_receipt(
    *,
    components: list[dict[str, object]],
    plan: dict[str, object],
    characteristics: dict[str, object],
    judge_sha256: str,
    environment_hashes: dict[str, str] | None = None,
) -> dict[str, object]:
    evidence = {
        "schema_version": "hswm-prom9-f1-r8-development-evidence/v1",
        "artifact_receipts": dict(
            environment_hashes
            or {field: canonical_sha256(field) for field in ENVIRONMENT_HASH_FIELDS}
        ),
    }
    analysis = {
        "schema_version": POWER_DEVELOPMENT_SCHEMA,
        "development_components": components,
        "simulation_plan": plan,
    }
    unsigned = {
        "schema_version": POWER_RECEIPT_SCHEMA,
        "analysis_input": analysis,
        "development_evidence": evidence,
        "development_evidence_sha256": canonical_sha256(evidence),
        "development_data_sha256": canonical_sha256(components),
        "simulator_sha256": judge_sha256,
        "judge_core_sha256": judge_sha256,
        "inference_unit": "component_cluster_macro",
        "selected_method": "paired_cluster_percentile_bootstrap_v1",
        "minimum_clusters": SELECTED_CLUSTERS,
        "operating_characteristics": characteristics,
    }
    return {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}


def _rehash(receipt: dict[str, object]) -> dict[str, object]:
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256", None)
    return {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}


def test_actual_prospective_judge_semantics_pass_v3_power_gates_but_old_schema_refuses() -> None:
    assert POWER_RECEIPT_SCHEMA == "hswm-prom9-f1-r8-power-operating-characteristic/v3"
    judge, components, plan, characteristics = _actual_judge_power()
    judge_sha = str(judge.judge_core_sha256(JUDGE_PATH))
    receipt = _v3_receipt(
        components=components,
        plan=plan,
        characteristics=characteristics,
        judge_sha256=judge_sha,
    )

    assert verify_power_operating_characteristics(
        receipt,
        judge_core_path=JUDGE_PATH,
    ) == receipt["receipt_sha256"]
    assert characteristics["observed_power_lower_95"] >= 0.80
    assert characteristics["null_false_support_upper_95"] <= 0.05
    assert all(
        characteristics[f"{scenario}_sensitivity_pass"] is True
        for scenario in SENSITIVITY_SCENARIOS
    )

    # The checked-in prospective judge is still v2.  The durable HSWM test must
    # fail closed instead of treating a temporary v1/v2 receipt as acceptable.
    old_lock = {
        "dependency_hashes": {
            "power_operating_characteristic_receipt": receipt["receipt_sha256"]
        },
        "judge_core_sha256": judge_sha,
        "bootstrap": dict(BOOTSTRAP),
    }
    with pytest.raises(judge.JudgeRefusal):
        judge._verify_power_receipt(receipt, lock=old_lock)


def test_power_gate_rejects_a_subthreshold_actual_judge_characteristic() -> None:
    judge, components, plan, characteristics = _actual_judge_power()
    receipt = _v3_receipt(
        components=components,
        plan=plan,
        characteristics=characteristics,
        judge_sha256=str(judge.judge_core_sha256(JUDGE_PATH)),
    )
    failing = copy.deepcopy(receipt)
    assert isinstance(failing["operating_characteristics"], dict)
    failing["operating_characteristics"]["observed_power_lower_95"] = 0.79
    failing = _rehash(failing)

    with pytest.raises(PowerCLIRefusal, match="not independently replayed"):
        verify_power_operating_characteristics(
            failing,
            judge_core_path=JUDGE_PATH,
        )


def test_fabricated_components_and_all_pass_scalars_are_refused_by_judge_replay() -> None:
    judge, components, plan, characteristics = _actual_judge_power()
    fabricated_characteristics = {
        **characteristics,
        "observed_power_at_mde": 1.0,
        "observed_power_lower_95": 1.0,
        "null_false_support_rate": 0.0,
        "null_false_support_upper_95": 0.0,
        "interval_coverage": 1.0,
        "interval_coverage_lower_95": 1.0,
        "expected_interval_width": 0.01,
    }
    for scenario in SENSITIVITY_SCENARIOS:
        fabricated_characteristics[f"{scenario}_support_rate"] = 1.0
        fabricated_characteristics[f"{scenario}_support_lower_95"] = 1.0
        fabricated_characteristics[f"{scenario}_sensitivity_pass"] = True
    receipt = _v3_receipt(
        components=components,
        plan=plan,
        characteristics=fabricated_characteristics,
        judge_sha256=str(judge.judge_core_sha256(JUDGE_PATH)),
    )
    fabricated = copy.deepcopy(receipt)
    fabricated_components = [None] * 48
    assert isinstance(fabricated["analysis_input"], dict)
    fabricated["analysis_input"]["development_components"] = fabricated_components
    fabricated["development_data_sha256"] = canonical_sha256(fabricated_components)
    fabricated = _rehash(fabricated)

    with pytest.raises(PowerCLIRefusal, match="independent power replay failed"):
        verify_power_operating_characteristics(
            fabricated,
            judge_core_path=JUDGE_PATH,
        )


def test_measured_environment_bundle_requires_all_four_execution_lock_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_pre_c1_dependencies(monkeypatch)
    repo_root = Path(__file__).resolve().parents[1]
    symposium_repo_root = Path(__file__).resolve().parents[3]
    expected_paths = _r8_dependency_paths(tmp_path)
    bundle, lock, manifest, expected_hashes = _bundle_context(
        expected_paths,
        hswm_commit=_head_commit(repo_root),
        symposium_commit=_head_commit(symposium_repo_root),
    )

    _, _, observed = verify_measured_environment_bundle(
        bundle,
        execution_lock=lock,
        manifest=manifest,
        expected_paths=expected_paths,
        repo_root=repo_root,
        symposium_repo_root=symposium_repo_root,
    )
    assert observed == expected_hashes

    incomplete_paths = dict(expected_paths)
    incomplete_paths.pop("runner")
    with pytest.raises(PowerCLIRefusal, match="inventory drifted"):
        verify_measured_environment_bundle(
            bundle,
            execution_lock=lock,
            manifest=manifest,
            expected_paths=incomplete_paths,
            repo_root=repo_root,
            symposium_repo_root=symposium_repo_root,
        )

    for field in ENVIRONMENT_HASH_FIELDS:
        drifted = {**lock, field: "f" * 64}
        with pytest.raises(PowerCLIRefusal, match=field):
            verify_measured_environment_bundle(
                bundle,
                execution_lock=drifted,
                manifest=manifest,
                expected_paths=expected_paths,
                repo_root=repo_root,
                symposium_repo_root=symposium_repo_root,
            )


@pytest.mark.parametrize(
    "substituted_name", ["runner", "private_output", "function_network"]
)
def test_measured_environment_bundle_refuses_runtime_semantic_path_substitution(
    tmp_path: Path,
    substituted_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_pre_c1_dependencies(monkeypatch)
    repo_root = Path(__file__).resolve().parents[1]
    symposium_repo_root = Path(__file__).resolve().parents[3]
    expected_paths = _r8_dependency_paths(tmp_path / "expected")
    dummy = _write_text(tmp_path / f"dummy-{substituted_name}.py", "# substitution\n")
    substituted_paths = {**expected_paths, substituted_name: dummy}
    bundle, lock, manifest, _hashes = _bundle_context(
        substituted_paths,
        hswm_commit=_head_commit(repo_root),
        symposium_commit=_head_commit(symposium_repo_root),
    )

    with pytest.raises(PowerCLIRefusal, match="semantics failed"):
        verify_measured_environment_bundle(
            bundle,
            execution_lock=lock,
            manifest=manifest,
            expected_paths=expected_paths,
            repo_root=repo_root,
            symposium_repo_root=symposium_repo_root,
        )


def test_measured_environment_bundle_refuses_live_commit_mismatch(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    symposium_repo_root = Path(__file__).resolve().parents[3]
    expected_paths = _r8_dependency_paths(tmp_path)
    non_live_commit = "0" * 40
    assert non_live_commit != _head_commit(repo_root)
    bundle, lock, manifest, _hashes = _bundle_context(
        expected_paths,
        hswm_commit=non_live_commit,
        symposium_commit=_head_commit(symposium_repo_root),
    )

    with pytest.raises(PowerCLIRefusal, match="semantics failed"):
        verify_measured_environment_bundle(
            bundle,
            execution_lock=lock,
            manifest=manifest,
            expected_paths=expected_paths,
            repo_root=repo_root,
            symposium_repo_root=symposium_repo_root,
        )


def test_measured_environment_bundle_refuses_wrong_symposium_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_pre_c1_dependencies(monkeypatch)
    repo_root = Path(__file__).resolve().parents[1]
    symposium_repo_root = Path(__file__).resolve().parents[3]
    expected_paths = _r8_dependency_paths(tmp_path)
    non_live_symposium_commit = "0" * 40
    assert non_live_symposium_commit != _head_commit(symposium_repo_root)
    bundle, lock, manifest, _hashes = _bundle_context(
        expected_paths,
        hswm_commit=_head_commit(repo_root),
        symposium_commit=non_live_symposium_commit,
    )

    with pytest.raises(PowerCLIRefusal, match="semantics failed"):
        verify_measured_environment_bundle(
            bundle,
            execution_lock=lock,
            manifest=manifest,
            expected_paths=expected_paths,
            repo_root=repo_root,
            symposium_repo_root=symposium_repo_root,
        )


def test_measured_environment_bundle_refuses_uncommitted_judge_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_pre_c1_dependencies(monkeypatch)
    repo_root = Path(__file__).resolve().parents[1]
    symposium_repo_root = tmp_path / "symposium-repo"
    symposium_commit = _initialize_test_repository(symposium_repo_root)
    uncommitted_judge = _write_text(
        symposium_repo_root / "uncommitted-judge.py",
        "# uncommitted judge template\n",
    )
    expected_paths = _r8_dependency_paths(
        tmp_path / "dependencies",
        judge_core_path=uncommitted_judge,
    )
    bundle, lock, manifest, _hashes = _bundle_context(
        expected_paths,
        hswm_commit=_head_commit(repo_root),
        symposium_commit=symposium_commit,
    )

    with pytest.raises(PowerCLIRefusal, match="semantics failed"):
        verify_measured_environment_bundle(
            bundle,
            execution_lock=lock,
            manifest=manifest,
            expected_paths=expected_paths,
            repo_root=repo_root,
            symposium_repo_root=symposium_repo_root,
        )


def test_subthreshold_receipt_is_refused_before_private_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    judge, components, plan, characteristics = _actual_judge_power()
    hashes = {field: canonical_sha256(field) for field in ENVIRONMENT_HASH_FIELDS}
    receipt = _v3_receipt(
        components=components,
        plan=plan,
        characteristics=characteristics,
        judge_sha256=str(judge.judge_core_sha256(JUDGE_PATH)),
        environment_hashes=hashes,
    )
    failing = copy.deepcopy(receipt)
    assert isinstance(failing["operating_characteristics"], dict)
    failing["operating_characteristics"]["null_false_support_upper_95"] = 0.051
    failing = _rehash(failing)
    writes: list[tuple[Path, object]] = []

    import prom_search_hswm.prom9_f1_r8_power_cli as cli

    monkeypatch.setattr(
        cli, "write_private_once", lambda path, value: writes.append((path, value))
    )
    with pytest.raises(PowerCLIRefusal, match="not independently replayed"):
        write_validated_power_receipt(
            Path("must-not-exist.json"),
            failing,
            expected_environment_hashes=hashes,
            judge_core_path=JUDGE_PATH,
        )
    assert writes == []


def test_cli_refusal_does_not_echo_private_error_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import prom_search_hswm.prom9_f1_r8_power_cli as cli

    secret = "PRIVATE-GOLD-ANSWER-MUST-NOT-LEAK"
    monkeypatch.setattr(
        cli,
        "_read",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(secret)),
    )
    paths = [
        "--manifest",
        "m",
        "--execution-lock",
        "l",
        "--public-source-receipt",
        "s",
        "--gold-source-receipt",
        "gs",
        "--selection-receipt",
        "c",
        "--prior-exposure-receipt",
        "p",
        "--suite",
        "u",
        "--evaluator-receipt",
        "e",
        "--gold",
        "g",
        "--db-genesis-receipt",
        "d",
        "--environment-dependency-bundle",
        "b",
        "--symposium-repo-root",
        "symposium",
        "--protocol",
        "protocol",
        "--judge-core",
        "j",
        "--result-contract",
        "result-contract",
        "--tokenizer-dir",
        "tokenizer",
        "--model-catalog",
        "model-catalog",
        "--model-weight-receipt",
        "model-weight",
        "--python-lock",
        "python-lock",
        "--output",
        "o",
    ]

    assert main(paths) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == '{"status": "REFUSED"}'
    assert secret not in captured.err
