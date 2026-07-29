from __future__ import annotations

import copy
from functools import lru_cache
import os
from pathlib import Path
import subprocess

import pytest

from prom_search_hswm.hswm_result_spool import ModelDeploymentBinding
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
    PowerRefusal,
    _load_judge_core,
    _verify_deployment_environment_binding,
)
from prom_search_hswm.prom9_f1_r8_power_cli import (
    ENVIRONMENT_HASH_FIELDS,
    PowerCLIRefusal,
    _verify_model_deployment_receipt,
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
        spool_endpoint="https://spool.invalid",
        model_upstream_endpoint=(
            "https://inference.invalid/v1/chat/completions"
        ),
        model_deployment_receipt_sha256="d" * 64,
        model="measured-model",
        model_revision="f" * 40,
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
        "execution_policy": {"endpoint": labels["spool_endpoint"]},
        "upstream_endpoint": labels["model_upstream_endpoint"],
        "deployment_receipt_sha256": labels[
            "model_deployment_receipt_sha256"
        ],
        "deployment_id": f"hswm:model_deployment:v2:{'d' * 64}",
        "model": labels["model"],
        "served_model": labels["model"],
        "model_revision": labels["model_revision"],
    }
    manifest: dict[str, object] = {
        "model": labels["model"],
        "model_revision": labels["model_revision"],
        "run_id": labels["run_id"],
    }
    return bundle, lock, manifest, hashes


def test_power_builder_requires_exact_eight_label_deployment_binding() -> None:
    labels = r8_environment_labels(
        spool_endpoint="https://spool.invalid",
        model_upstream_endpoint=(
            "https://inference.invalid/v1/chat/completions"
        ),
        model_deployment_receipt_sha256="d" * 64,
        model="measured-model",
        model_revision="f" * 40,
        run_id="run",
        hswm_commit="a" * 40,
        symposium_commit="b" * 40,
    )
    lock = {
        "execution_policy": {"endpoint": labels["spool_endpoint"]},
        "upstream_endpoint": labels["model_upstream_endpoint"],
        "deployment_receipt_sha256": labels[
            "model_deployment_receipt_sha256"
        ],
        "deployment_id": f"hswm:model_deployment:v2:{'d' * 64}",
        "model": labels["model"],
        "served_model": labels["model"],
        "model_revision": labels["model_revision"],
        "hswm_commit": labels["hswm_commit"],
    }
    manifest = {
        "model": labels["model"],
        "model_revision": labels["model_revision"],
        "run_id": labels["run_id"],
    }
    assert _verify_deployment_environment_binding(
        labels, execution_lock=lock, manifest=manifest
    ) == labels

    old = dict(labels)
    old["endpoint"] = old.pop("spool_endpoint")
    with pytest.raises(PowerRefusal, match="deployment semantic"):
        _verify_deployment_environment_binding(
            old, execution_lock=lock, manifest=manifest
        )
    extra = {**labels, "extra": "drift"}
    with pytest.raises(PowerRefusal, match="deployment semantic"):
        _verify_deployment_environment_binding(
            extra, execution_lock=lock, manifest=manifest
        )
    alternate = {**lock, "deployment_receipt_sha256": "e" * 64}
    alternate["deployment_id"] = f"hswm:model_deployment:v2:{'e' * 64}"
    with pytest.raises(PowerRefusal, match="deployment semantic"):
        _verify_deployment_environment_binding(
            labels, execution_lock=alternate, manifest=manifest
        )
    wrong_model = {**lock, "model": "other-model"}
    with pytest.raises(PowerRefusal, match="deployment semantic"):
        _verify_deployment_environment_binding(
            labels, execution_lock=wrong_model, manifest=manifest
        )
    malformed_symposium = {**labels, "symposium_commit": "not-a-commit"}
    with pytest.raises(PowerRefusal, match="deployment semantic"):
        _verify_deployment_environment_binding(
            malformed_symposium, execution_lock=lock, manifest=manifest
        )


def test_power_cli_verifies_official_deployment_receipt_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import prom_search_hswm.prom9_f1_r8_power_cli as cli

    path = _write_text(tmp_path / "deployment.json", "{}\n")
    manifest = {"model": "measured-model", "model_revision": "f" * 40}
    lock = {
        "model": manifest["model"],
        "upstream_endpoint": "https://inference.invalid/v1/chat/completions",
        "deployment_receipt_sha256": "d" * 64,
        "deployment_id": f"hswm:model_deployment:v2:{'d' * 64}",
        "served_model": manifest["model"],
        "model_revision": manifest["model_revision"],
    }
    calls: list[tuple[Path, bool]] = []

    def load_exact(
        raw_path: Path,
        *,
        upstream_endpoint: str,
        served_model: str,
        model_revision: str,
        verify_live_process: bool,
    ) -> ModelDeploymentBinding:
        calls.append((raw_path, verify_live_process))
        return ModelDeploymentBinding(
            upstream_endpoint=upstream_endpoint,
            deployment_receipt_sha256="d" * 64,
            deployment_id=f"hswm:model_deployment:v2:{'d' * 64}",
            served_model=served_model,
            model_revision=model_revision,
        )

    monkeypatch.setattr(cli, "load_model_deployment_binding", load_exact)
    assert _verify_model_deployment_receipt(
        path, execution_lock=lock, manifest=manifest
    )["deployment_receipt_sha256"] == "d" * 64
    assert calls == [(path, False)]

    def load_wrong(*_args: object, **_kwargs: object) -> ModelDeploymentBinding:
        return ModelDeploymentBinding(
            upstream_endpoint=str(lock["upstream_endpoint"]),
            deployment_receipt_sha256="e" * 64,
            deployment_id=f"hswm:model_deployment:v2:{'e' * 64}",
            served_model=str(manifest["model"]),
            model_revision=str(manifest["model_revision"]),
        )

    monkeypatch.setattr(cli, "load_model_deployment_binding", load_wrong)
    with pytest.raises(PowerCLIRefusal, match="frozen execution lock"):
        _verify_model_deployment_receipt(
            path, execution_lock=lock, manifest=manifest
        )


def _allow_pre_c1_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass only pre-C1 HSWM blobs; keep SYMPOSIUM judge binding live."""

    import prom_search_hswm.prom9_f1_r8_environment as environment
    import prom_search_hswm.prom9_f1_r8_power_cli as cli

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

    def verified_deployment(
        _path: Path,
        *,
        upstream_endpoint: str,
        served_model: str,
        model_revision: str,
        verify_live_process: bool,
    ) -> ModelDeploymentBinding:
        assert verify_live_process is False
        return ModelDeploymentBinding(
            upstream_endpoint=upstream_endpoint,
            deployment_receipt_sha256="d" * 64,
            deployment_id=f"hswm:model_deployment:v2:{'d' * 64}",
            served_model=served_model,
            model_revision=model_revision,
        )

    monkeypatch.setattr(cli, "load_model_deployment_binding", verified_deployment)


def _allow_synthetic_components(
    monkeypatch: pytest.MonkeyPatch,
    components: list[dict[str, object]],
) -> None:
    import prom_search_hswm.prom9_f1_r8_power_cli as cli

    monkeypatch.setattr(
        cli,
        "derive_development_components",
        lambda **_kwargs: copy.deepcopy(components),
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
        "manifest": {},
        "execution_lock": {},
        "public_source_receipt": {},
        "selection_receipt": {},
        "gold_source_receipt": {},
        "prior_exposure_receipt": {},
        "suite": {},
        "evaluator_receipt": {},
        "gold": {},
        "db_genesis_receipt": {},
        "environment_dependency_bundle": {},
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


def test_actual_prospective_judge_semantics_pass_v3_power_gates_but_incomplete_judge_evidence_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert POWER_RECEIPT_SCHEMA == "hswm-prom9-f1-r8-power-operating-characteristic/v3"
    judge, components, plan, characteristics = _actual_judge_power()
    judge_sha = str(judge.judge_core_sha256(JUDGE_PATH))
    receipt = _v3_receipt(
        components=components,
        plan=plan,
        characteristics=characteristics,
        judge_sha256=judge_sha,
    )
    _allow_synthetic_components(monkeypatch, components)

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

    # The anchored prospective judge must fail closed on this deliberately
    # incomplete synthetic receipt instead of treating simulator replay alone
    # as sufficient power evidence.
    old_lock = {
        "dependency_hashes": {
            "power_operating_characteristic_receipt": receipt["receipt_sha256"]
        },
        "judge_core_sha256": judge_sha,
        "bootstrap": dict(BOOTSTRAP),
    }
    with pytest.raises(judge.JudgeRefusal):
        judge._verify_power_receipt(
            receipt,
            lock=old_lock,
            prereg={
                "power_operating_characteristic_receipt_sha256": receipt[
                    "receipt_sha256"
                ]
            },
            bootstrap=dict(BOOTSTRAP),
            selection={},
        )


def test_power_gate_rejects_a_subthreshold_actual_judge_characteristic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    judge, components, plan, characteristics = _actual_judge_power()
    receipt = _v3_receipt(
        components=components,
        plan=plan,
        characteristics=characteristics,
        judge_sha256=str(judge.judge_core_sha256(JUDGE_PATH)),
    )
    _allow_synthetic_components(monkeypatch, components)
    failing = copy.deepcopy(receipt)
    assert isinstance(failing["operating_characteristics"], dict)
    failing["operating_characteristics"]["observed_power_lower_95"] = 0.79
    failing = _rehash(failing)

    with pytest.raises(PowerCLIRefusal, match="not independently replayed"):
        verify_power_operating_characteristics(
            failing,
            judge_core_path=JUDGE_PATH,
        )


def test_rehashed_detached_component_contrast_is_refused_by_evidence_rederivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    judge, components, plan, characteristics = _actual_judge_power()
    receipt = _v3_receipt(
        components=components,
        plan=plan,
        characteristics=characteristics,
        judge_sha256=str(judge.judge_core_sha256(JUDGE_PATH)),
    )
    _allow_synthetic_components(monkeypatch, components)
    detached = copy.deepcopy(receipt)
    assert isinstance(detached["analysis_input"], dict)
    detached_components = detached["analysis_input"]["development_components"]
    assert isinstance(detached_components, list)
    assert isinstance(detached_components[0], dict)
    contrasts = detached_components[0]["contrasts"]
    assert isinstance(contrasts, dict)
    arm = next(iter(contrasts))
    contrasts[arm] = float(contrasts[arm]) + 0.125
    detached["development_data_sha256"] = canonical_sha256(detached_components)
    detached = _rehash(detached)

    with pytest.raises(PowerCLIRefusal, match="not rederived from evidence"):
        verify_power_operating_characteristics(
            detached,
            judge_core_path=JUDGE_PATH,
        )


def test_terminal_power_verifier_rejects_incomplete_evidence_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    judge, components, plan, characteristics = _actual_judge_power()
    receipt = _v3_receipt(
        components=components,
        plan=plan,
        characteristics=characteristics,
        judge_sha256=str(judge.judge_core_sha256(JUDGE_PATH)),
    )
    _allow_synthetic_components(monkeypatch, components)
    incomplete = copy.deepcopy(receipt)
    evidence = incomplete["development_evidence"]
    assert isinstance(evidence, dict)
    evidence.pop("manifest")
    incomplete["development_evidence_sha256"] = canonical_sha256(evidence)
    incomplete = _rehash(incomplete)
    with pytest.raises(PowerCLIRefusal, match="development evidence self-hash"):
        verify_power_operating_characteristics(
            incomplete,
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_pre_c1_dependencies(monkeypatch)
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
    _allow_synthetic_components(monkeypatch, components)
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
        "--model-deployment-receipt",
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
