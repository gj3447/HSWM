from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from prom_search_hswm.hswm_function_network import (
    FLAT_ARM,
    REMOVAL_ARM,
    SHUFFLE_ARM,
    VECTOR_ARM,
)
from prom_search_hswm.hswm_typed_ports import canonical_sha256
import prom_search_hswm.prom9_f1_r8_power_cli_v6 as cli
from prom_search_hswm.prom9_f1_r8_power_v6 import (
    BOOTSTRAP_V6,
    DEVELOPMENT_COMPONENTS_V6,
    JUDGE_CAPABILITY_V1,
    MDE_V6,
    POWER_DEVELOPMENT_SCHEMA_V6,
    POWER_EVIDENCE_SCHEMA_V6,
    POWER_RECEIPT_SCHEMA_V6,
    POWER_SCENARIOS_V6,
    POWER_SIMULATION_SEED,
    POWER_SIMULATOR_SCHEMA_V6,
    SELECTED_CLUSTERS_V6,
    TARGET_POWER_V6,
    TRIALS_V6,
    UTILITY_COST_C,
    UTILITY_METRIC,
    PowerRefusal,
    _load_c801_judge_core,
)


JUDGE_FILE_SHA = "a" * 64
JUDGE_CORE_SHA = "b" * 64


def _components() -> list[dict[str, object]]:
    return [
        {
            "component_id": canonical_sha256({"component": index}),
            "item_ids": [f"item-{index}"],
            "source_entity_ids": [canonical_sha256({"source": index})],
            "cluster_size": 1,
            "seed_block": index // 4,
            "carryover_block": index % 2,
            "contrasts": {
                FLAT_ARM: 0.15,
                VECTOR_ARM: 0.15,
                REMOVAL_ARM: 0.15,
                SHUFFLE_ARM: 0.15,
            },
        }
        for index in range(DEVELOPMENT_COMPONENTS_V6)
    ]


def _characteristics() -> dict[str, object]:
    value: dict[str, object] = {
        "trial_count": TRIALS_V6,
        "selected_cluster_count": SELECTED_CLUSTERS_V6,
        "mde": MDE_V6,
        "target_power": TARGET_POWER_V6,
        "observed_power_at_mde": 0.90,
        "observed_power_lower_95": 0.82,
        "null_false_support_rate": 0.01,
        "null_false_support_upper_95": 0.04,
        "interval_coverage": 0.97,
        "interval_coverage_lower_95": 0.95,
        "expected_interval_width": 0.08,
        "effect_0_03_support_rate": 0.25,
        "effect_0_08_support_rate": 0.99,
    }
    for scenario in cli.SENSITIVITY_SCENARIOS:
        value[f"{scenario}_support_rate"] = 0.90
        value[f"{scenario}_support_lower_95"] = 0.82
        value[f"{scenario}_sensitivity_pass"] = True
    return value


def _judge(
    components: list[dict[str, object]],
    characteristics: dict[str, object],
) -> SimpleNamespace:
    return SimpleNamespace(
        __hswm_captured_file_sha256__=JUDGE_FILE_SHA,
        __hswm_captured_core_sha256__=JUDGE_CORE_SHA,
        c801_preflight_contract=lambda: copy.deepcopy(JUDGE_CAPABILITY_V1),
        _derive_power_development_components=(
            lambda *_args, **_kwargs: copy.deepcopy(components)
        ),
        _recompute_power_characteristics=(
            lambda *_args, **_kwargs: copy.deepcopy(characteristics)
        ),
    )


def _receipt() -> tuple[
    dict[str, object], list[dict[str, object]], dict[str, object]
]:
    components = _components()
    characteristics = _characteristics()
    evidence = {
        "schema_version": POWER_EVIDENCE_SCHEMA_V6,
        "manifest": {},
        "execution_lock": {"judge_core_file_sha256": JUDGE_FILE_SHA},
        "public_source_receipt": {},
        "selection_receipt": {},
        "predecessor_selection_receipt": {},
        "gold_source_receipt": {},
        "prior_exposure_receipt": {},
        "aborted_attempt_exposure_receipt": {},
        "suite": {},
        "evaluator_receipt": {},
        "gold": {},
        "db_genesis_receipt": {},
        "environment_dependency_bundle": {
            "dependency_receipt": {
                "files": {"judge_core": {"sha256": JUDGE_FILE_SHA}}
            }
        },
        "artifact_receipts": {},
    }
    plan = {
        "schema_version": POWER_SIMULATOR_SCHEMA_V6,
        "trials": TRIALS_V6,
        "master_seed": POWER_SIMULATION_SEED,
        "selected_cluster_count": SELECTED_CLUSTERS_V6,
        "selection_method": "complete_seed_block_without_replacement/v1",
        "mde": MDE_V6,
        "target_power": TARGET_POWER_V6,
        "scenarios": list(POWER_SCENARIOS_V6),
    }
    unsigned = {
        "schema_version": POWER_RECEIPT_SCHEMA_V6,
        "analysis_input": {
            "schema_version": POWER_DEVELOPMENT_SCHEMA_V6,
            "development_components": components,
            "simulation_plan": plan,
        },
        "development_evidence": evidence,
        "development_evidence_sha256": canonical_sha256(evidence),
        "development_data_sha256": canonical_sha256(components),
        "simulator_sha256": JUDGE_CORE_SHA,
        "judge_core_sha256": JUDGE_CORE_SHA,
        "inference_unit": "component_cluster_macro",
        "selected_method": "paired_cluster_percentile_bootstrap_v1",
        "minimum_clusters": SELECTED_CLUSTERS_V6,
        "operating_characteristics": characteristics,
        "metric": UTILITY_METRIC,
        "utility_cost_c": UTILITY_COST_C,
    }
    return (
        {**unsigned, "receipt_sha256": canonical_sha256(unsigned)},
        components,
        characteristics,
    )


def _resign(receipt: dict[str, object]) -> None:
    evidence = receipt["development_evidence"]
    analysis = receipt["analysis_input"]
    assert isinstance(evidence, dict)
    assert isinstance(analysis, dict)
    receipt["development_evidence_sha256"] = canonical_sha256(evidence)
    receipt["development_data_sha256"] = canonical_sha256(
        analysis["development_components"]
    )
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = canonical_sha256(unsigned)


def test_c801_power_constants_are_single_generation() -> None:
    assert POWER_RECEIPT_SCHEMA_V6.endswith("/v2-utility")
    assert DEVELOPMENT_COMPONENTS_V6 == SELECTED_CLUSTERS_V6 == 800
    assert TRIALS_V6 == 60
    assert MDE_V6 == 0.15
    assert TARGET_POWER_V6 == 0.80
    assert UTILITY_COST_C == 2
    assert BOOTSTRAP_V6["minimum_clusters"] == 800
    assert POWER_SIMULATION_SEED != 20260806


def test_power_gate_accepts_exact_c801_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt, components, characteristics = _receipt()
    monkeypatch.setattr(
        cli,
        "_load_c801_judge_core",
        lambda *_args, **_kwargs: _judge(components, characteristics),
    )
    assert cli.verify_power_operating_characteristics(
        receipt, judge_core_path=Path("judge.py")
    ) == receipt["receipt_sha256"]


@pytest.mark.parametrize(
    ("path", "replacement"),
    (
        (("metric",), "legacy_accuracy"),
        (("utility_cost_c",), 1),
        (("minimum_clusters",), 40),
        (("analysis_input", "simulation_plan", "mde"), 0.05),
        (
            ("analysis_input", "simulation_plan", "selected_cluster_count"),
            40,
        ),
    ),
)
def test_power_gate_refuses_c800_or_nonutility_drift(
    monkeypatch: pytest.MonkeyPatch,
    path: tuple[str, ...],
    replacement: object,
) -> None:
    receipt, components, characteristics = _receipt()
    target: dict[str, object] = receipt
    for key in path[:-1]:
        nested = target[key]
        assert isinstance(nested, dict)
        target = nested
    target[path[-1]] = replacement
    _resign(receipt)
    monkeypatch.setattr(
        cli,
        "_load_c801_judge_core",
        lambda *_args, **_kwargs: _judge(components, characteristics),
    )
    with pytest.raises(cli.PowerCLIRefusal):
        cli.verify_power_operating_characteristics(
            receipt, judge_core_path=Path("judge.py")
        )


def test_rehashed_detached_component_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt, components, characteristics = _receipt()
    analysis = receipt["analysis_input"]
    assert isinstance(analysis, dict)
    stored = analysis["development_components"]
    assert isinstance(stored, list)
    stored[0]["contrasts"][FLAT_ARM] = 0.16
    _resign(receipt)
    monkeypatch.setattr(
        cli,
        "_load_c801_judge_core",
        lambda *_args, **_kwargs: _judge(components, characteristics),
    )
    with pytest.raises(cli.PowerCLIRefusal, match="not rederived"):
        cli.verify_power_operating_characteristics(
            receipt, judge_core_path=Path("judge.py")
        )


def test_stable_judge_loader_executes_only_the_captured_authority(
    tmp_path: Path,
) -> None:
    path = tmp_path / "judge.py"
    source = "\n".join(
        (
            "from pathlib import Path",
            'EXPECTED_MEASUREMENT_LOCK_SHA256 = "__F1_R8_MEASUREMENT_LOCK_SHA256_UNFROZEN__"',
            f"CAPABILITY = {JUDGE_CAPABILITY_V1!r}",
            "def judge_core_sha256(path: Path): return '0' * 64",
            "def c801_preflight_contract(): return dict(CAPABILITY)",
            "def _derive_power_development_components(*args, **kwargs): return []",
            "def _recompute_power_characteristics(*args, **kwargs): return {}",
            "",
        )
    )
    path.write_text(source, encoding="utf-8")
    path.chmod(0o600)
    module = _load_c801_judge_core(path)
    assert module.c801_preflight_contract() == JUDGE_CAPABILITY_V1
    assert module.__hswm_captured_file_sha256__ == hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()
    assert len(module.__hswm_captured_core_sha256__) == 64
    with pytest.raises(PowerRefusal, match="dependency receipt"):
        _load_c801_judge_core(path, expected_file_sha256="f" * 64)


def test_private_reader_refuses_oversize_before_allocation(tmp_path: Path) -> None:
    path = tmp_path / "private.json"
    path.write_bytes(b"12345")
    path.chmod(0o600)
    with pytest.raises(cli.PowerCLIRefusal, match="bounded private regular file"):
        cli._read_private_bytes_bounded(path, "private fixture", 4)


def test_terminal_write_refuses_boundary_drift_before_effect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    receipt, _components_value, _characteristics_value = _receipt()
    evidence = receipt["development_evidence"]
    assert isinstance(evidence, dict)
    evidence["prior_exposure_receipt"] = {"kind": "prior"}
    evidence["aborted_attempt_exposure_receipt"] = {"kind": "successor"}
    evidence["predecessor_selection_receipt"] = {"kind": "predecessor"}
    evidence["selection_receipt"] = {
        "prior_exposure_receipt_sha256": "1" * 64,
        "aborted_attempt_exposure_receipt_sha256": "2" * 64,
        "predecessor_selection_receipt_sha256": "3" * 64,
    }
    evidence["artifact_receipts"] = {
        "prior_exposure_receipt_sha256": "1" * 64,
        "aborted_attempt_exposure_receipt_sha256": "2" * 64,
        "predecessor_selection_receipt_sha256": "3" * 64,
    }
    evidence["execution_lock"] = {
        "prior_exposure_receipt_sha256": "1" * 64,
        "aborted_attempt_exposure_receipt_sha256": "2" * 64,
        "forbidden_prior_item_ids": ["exposed-item"],
        "forbidden_prior_source_entity_ids": ["4" * 64],
        "forbidden_prior_component_ids": ["5" * 64],
    }
    _resign(receipt)
    monkeypatch.setattr(cli, "verify_prior_exposure_receipt", lambda _value: "1" * 64)
    monkeypatch.setattr(
        cli, "verify_f1_r8_successor_exposure_set_v2", lambda _value: "2" * 64
    )
    monkeypatch.setattr(cli, "verify_selection_receipt_v5", lambda _value: "3" * 64)
    monkeypatch.setattr(
        cli,
        "merge_c801_exposure_boundaries",
        lambda *_args: {
            "item_ids": ["exposed-item"],
            "source_entity_ids": ["4" * 64],
            "component_ids": ["5" * 64],
        },
    )
    monkeypatch.setattr(cli, "verify_receipt_environment_hashes", lambda *_args: None)
    monkeypatch.setattr(
        cli, "verify_power_operating_characteristics", lambda *_args, **_kwargs: "ok"
    )
    writes: list[Path] = []
    monkeypatch.setattr(cli, "write_private_once", lambda path, _value: writes.append(path))
    lock = evidence["execution_lock"]
    assert isinstance(lock, dict)
    lock["forbidden_prior_item_ids"] = []
    with pytest.raises(cli.PowerCLIRefusal, match="forbidden exposure union"):
        cli.write_validated_power_receipt(
            tmp_path / "power.json",
            receipt,
            expected_environment_hashes={},
            judge_core_path=tmp_path / "judge.py",
        )
    assert writes == []
