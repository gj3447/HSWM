"""Unit tests for prom9_f1_r8_power_v2 — utility power receipt + simulator.

Synthetic fixtures extend the metric-v2 harness with the block metadata the
simulator needs (12 equal seed blocks of 4, integer carryover blocks) and a
self-hashed selection receipt.  Two cohorts are exercised:

* a degenerate all-abstain cohort (every contrast exactly 0): the null must
  never support while every injected effect scenario must support
  deterministically;
* the metric-v2 outcome pattern (mixed correct/wrong/abstain): exact
  Fraction contrasts, full receipt build + verify, refusal on tampering.

The real-suite smoke runs against the frozen t2 development cohort when it
exists on disk (Dell) and is skipped elsewhere; it also proves the v2
simulator is byte-identical to the frozen v1 judge on the same float
components.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import stat
from fractions import Fraction
from pathlib import Path

import pytest

from prom_search_hswm.hswm_function_network import (
    FLAT_ARM,
    REMOVAL_ARM,
    SHUFFLE_ARM,
    TYPED_ARM,
    VECTOR_ARM,
)
from prom_search_hswm.hswm_typed_ports import canonical_sha256
from prom_search_hswm import prom9_f1_metric_v2 as m2
from prom_search_hswm.prom9_f1_metric_v2 import MetricV2Refusal
from prom_search_hswm import prom9_f1_r8_power_v2 as p2
from prom_search_hswm.prom9_f1_r8_power_v2 import PowerV2Refusal

ARMS = (TYPED_ARM, FLAT_ARM, VECTOR_ARM, REMOVAL_ARM, SHUFFLE_ARM)
CONTROLS = (FLAT_ARM, VECTOR_ARM, REMOVAL_ARM, SHUFFLE_ARM)
RUN_ID = "power-v2-test-run"
N_ITEMS = 48

# metric-v2 outcome pattern (same expectations as test_prom9_f1_metric_v2):
#   typed   correct i<24, wrong 24<=i<28
#   flat    correct i<16, wrong 16<=i<24
#   vector  correct i<20, wrong 20<=i<23
#   removal abstain everywhere
#   shuffle correct i<18, wrong 18<=i<21
_PATTERN = {
    TYPED_ARM: (24, 28),
    FLAT_ARM: (16, 24),
    VECTOR_ARM: (20, 23),
    REMOVAL_ARM: (0, 0),
    SHUFFLE_ARM: (18, 21),
}


def _item_id(index: int) -> str:
    return f"item-{index:02d}"


def _entity_id(index: int) -> str:
    return f"entity-{index:02d}"


def _component_id(index: int) -> str:
    return canonical_sha256(
        {
            "schema_version": "hswm-source-entity-connected-component/v1",
            "source_entity_ids": [_entity_id(index)],
        }
    )


def _pattern_answer(arm: str, index: int) -> dict:
    correct_until, wrong_until = _PATTERN[arm]
    if index < correct_until:
        return {"abstain": False, "answer": f"  ANSWER-{_item_id(index).split('-')[1]}\n"}
    if index < wrong_until:
        return {"abstain": False, "answer": f"fabricated-{index}"}
    return {"abstain": True, "answer": ""}


def _abstain_answer(arm: str, index: int) -> dict:
    return {"abstain": True, "answer": ""}


def _accepted_answer(index: int) -> str:
    return f"answer-{_item_id(index).split('-')[1]}"


def _build_fixture(answer_fn=_pattern_answer) -> dict:
    manifest = {
        "schema_version": "hswm-prom9-f1-manifest/v3",
        "mode": "development",
        "run_id": RUN_ID,
        "items": [
            {
                "item_id": _item_id(i),
                "component_id": _component_id(i),
                "candidates": [{"source_entity_id": _entity_id(i)}],
            }
            for i in range(N_ITEMS)
        ],
    }
    item_runs = [
        {
            "item_id": _item_id(i),
            "arm_id": arm,
            "answer": answer_fn(arm, i),
        }
        for i in range(N_ITEMS)
        for arm in ARMS
    ]
    suite = {
        "schema_version": "hswm-prom9-f1-suite/v4",
        "mode": "development",
        "run_id": RUN_ID,
        "manifest_sha256": canonical_sha256(manifest),
        "item_runs": item_runs,
    }
    suite["suite_receipt_sha256"] = canonical_sha256(suite)
    gold = {
        "schema_version": "hswm-prom9-f1-gold/v2",
        "run_id": RUN_ID,
        "items": [
            {"item_id": _item_id(i), "accepted_answers": [_accepted_answer(i)]}
            for i in range(N_ITEMS)
        ],
    }
    selection = {
        "schema_version": "hswm-prom9-f1-r8-cohort-selection/v4",
        "development": {
            "item_ids": [_item_id(i) for i in range(N_ITEMS)],
            "component_schedule": [
                {
                    "component_id": _component_id(i),
                    "item_ids": [_item_id(i)],
                    "source_entity_ids": [_entity_id(i)],
                    "cluster_size": 1,
                    "seed_block": i // 4,
                    "carryover_block": i % 4,
                }
                for i in range(N_ITEMS)
            ],
        },
    }
    selection["selection_receipt_sha256"] = canonical_sha256(selection)
    return {
        "suite": suite,
        "gold": gold,
        "manifest": manifest,
        "selection": selection,
    }


def _build(fixture: dict) -> dict:
    return p2.build_power_v2_receipt(
        suite=fixture["suite"],
        gold=fixture["gold"],
        manifest=fixture["manifest"],
        selection=fixture["selection"],
    )


@pytest.fixture(scope="module")
def degenerate_receipt() -> dict:
    return _build(_build_fixture(_abstain_answer))


@pytest.fixture(scope="module")
def pattern_fixture() -> dict:
    return _build_fixture()


@pytest.fixture(scope="module")
def pattern_receipt(pattern_fixture) -> dict:
    return _build(pattern_fixture)


# ---------------------------------------------------------------------------
# degenerate cohort: null never supports, every injected effect supports
# ---------------------------------------------------------------------------


def test_degenerate_null_never_supports(degenerate_receipt):
    characteristics = degenerate_receipt["operating_characteristics"]
    assert characteristics["null_false_support_rate"] == 0.0


def test_degenerate_injected_effect_supports(degenerate_receipt):
    characteristics = degenerate_receipt["operating_characteristics"]
    assert characteristics["observed_power_at_mde"] == 1.0
    assert characteristics["effect_0_03_support_rate"] == 1.0
    assert characteristics["effect_0_08_support_rate"] == 1.0
    assert characteristics["interval_coverage"] == 1.0
    assert characteristics["expected_interval_width"] == 0.0
    for scenario in p2.SENSITIVITY_SCENARIOS:
        assert characteristics[f"{scenario}_support_rate"] == 1.0
        assert characteristics[f"{scenario}_sensitivity_pass"] is True


def test_degenerate_receipt_verifies(degenerate_receipt):
    declared = p2.verify_power_v2_operating_characteristics(degenerate_receipt)
    assert declared == degenerate_receipt["receipt_sha256"]
    assert degenerate_receipt["metric"] == p2.UTILITY_METRIC
    assert degenerate_receipt["utility_cost_c"] == 2


def test_degenerate_components_exact_zero(degenerate_receipt):
    components = degenerate_receipt["analysis_input"]["development_components"]
    assert len(components) == 48
    assert all(
        contrast == "0"
        for component in components
        for contrast in component["contrasts"].values()
    )
    seed_blocks = {}
    for component in components:
        seed_blocks[component["seed_block"]] = (
            seed_blocks.get(component["seed_block"], 0) + 1
        )
    assert len(seed_blocks) == 12 and set(seed_blocks.values()) == {4}


# ---------------------------------------------------------------------------
# metric-v2 pattern cohort: exact Fraction contrasts
# ---------------------------------------------------------------------------


def test_pattern_components_exact_fractions(pattern_receipt):
    components = {
        component["component_id"]: component
        for component in pattern_receipt["analysis_input"]["development_components"]
    }
    assert len(components) == 48
    # per-component single-item paired utility contrasts at c=2:
    #   typed−flat    : 3 on 16<=i<24, -2 on 24<=i<28, else 0
    #   typed−removal : 1 on i<24, -2 on 24<=i<28, else 0
    for i in range(N_ITEMS):
        contrasts = components[_component_id(i)]["contrasts"]
        assert set(contrasts) == set(CONTROLS)
        assert contrasts[FLAT_ARM] == str(
            Fraction(3 if 16 <= i < 24 else (-2 if 24 <= i < 28 else 0))
        )
        expected_removal = 1 if i < 24 else (-2 if i < 28 else 0)
        assert contrasts[REMOVAL_ARM] == str(Fraction(expected_removal))
        assert contrasts[SHUFFLE_ARM] == str(
            Fraction(3 if 18 <= i < 21 else (1 if 21 <= i < 24 else (-2 if 24 <= i < 28 else 0)))
        )
        assert contrasts[VECTOR_ARM] == str(
            Fraction(3 if 20 <= i < 23 else (1 if i == 23 else (-2 if 24 <= i < 28 else 0)))
        )


def test_pattern_metric_summary_exact(pattern_receipt):
    summary = pattern_receipt["analysis_input"]["utility_metric"]
    assert summary["name"] == p2.UTILITY_METRIC
    assert summary["cost_c"] == 2
    assert summary["per_arm_utility"] == {
        TYPED_ARM: "1/3",
        FLAT_ARM: "0",
        VECTOR_ARM: "7/24",
        REMOVAL_ARM: "0",
        SHUFFLE_ARM: "1/4",
    }
    assert summary["paired_contrasts"] == {
        FLAT_ARM: "1/3",
        VECTOR_ARM: "1/24",
        REMOVAL_ARM: "1/3",
        SHUFFLE_ARM: "1/12",
    }
    assert summary["min_contrast"] == "1/24"
    assert summary["coverage_v1_contrasts"] == {
        FLAT_ARM: "1/6",
        VECTOR_ARM: "1/12",
        REMOVAL_ARM: "1/2",
        SHUFFLE_ARM: "1/8",
    }


def test_pattern_receipt_builds_and_verifies(pattern_receipt):
    declared = p2.verify_power_v2_operating_characteristics(pattern_receipt)
    assert declared == pattern_receipt["receipt_sha256"]
    characteristics = pattern_receipt["operating_characteristics"]
    assert characteristics["null_false_support_rate"] == 0.0
    assert 0.0 <= characteristics["observed_power_at_mde"] <= 1.0
    assert characteristics["interval_coverage"] >= 0.95


def test_receipt_self_hash_detects_tamper(pattern_receipt):
    tampered = copy.deepcopy(pattern_receipt)
    tampered["operating_characteristics"]["null_false_support_rate"] = 0.5
    with pytest.raises(PowerV2Refusal):
        p2.verify_power_v2_operating_characteristics(tampered)


def test_receipt_component_tamper_detected(pattern_receipt):
    tampered = copy.deepcopy(pattern_receipt)
    tampered["analysis_input"]["development_components"][0]["contrasts"][
        FLAT_ARM
    ] = "99"
    with pytest.raises(PowerV2Refusal):
        p2.verify_power_v2_operating_characteristics(tampered)


# ---------------------------------------------------------------------------
# refusal discipline
# ---------------------------------------------------------------------------


def test_tampered_suite_refused():
    fixture = _build_fixture()
    fixture["suite"]["item_runs"][0]["answer"]["answer"] = "fabricated"
    with pytest.raises(MetricV2Refusal):
        _build(fixture)


def test_tampered_gold_refused():
    fixture = _build_fixture()
    fixture["gold"]["items"] = fixture["gold"]["items"][1:]
    with pytest.raises(MetricV2Refusal):
        _build(fixture)


def test_unequal_seed_blocks_refused():
    fixture = _build_fixture()
    row = fixture["selection"]["development"]["component_schedule"][0]
    row["seed_block"] = 7  # now block 7 has 5 components and block 0 has 3
    selection = fixture["selection"]
    selection["selection_receipt_sha256"] = canonical_sha256(
        {k: v for k, v in selection.items() if k != "selection_receipt_sha256"}
    )
    with pytest.raises(PowerV2Refusal):
        _build(fixture)


def test_missing_block_metadata_refused():
    fixture = _build_fixture()
    row = fixture["selection"]["development"]["component_schedule"][0]
    del row["seed_block"]
    selection = fixture["selection"]
    selection["selection_receipt_sha256"] = canonical_sha256(
        {k: v for k, v in selection.items() if k != "selection_receipt_sha256"}
    )
    with pytest.raises(PowerV2Refusal):
        _build(fixture)


def test_selection_self_hash_drift_refused():
    fixture = _build_fixture()
    fixture["selection"]["selection_receipt_sha256"] = "0" * 64
    with pytest.raises(PowerV2Refusal):
        _build(fixture)


def test_output_first_write_wins(tmp_path, degenerate_receipt):
    target = tmp_path / "receipt.json"
    p2._write_output_once(target, degenerate_receipt)
    first_bytes = target.read_bytes()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    with pytest.raises(Exception) as error:
        p2._write_output_once(target, degenerate_receipt)
    assert type(error.value).__name__.endswith("Refusal")
    assert target.read_bytes() == first_bytes


def test_cli_roundtrip(tmp_path):
    fixture = _build_fixture(_abstain_answer)
    paths = {}
    for name in ("suite", "gold", "manifest", "selection"):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(fixture[name]), encoding="utf-8")
        paths[name] = path
    output = tmp_path / "power-v2.json"
    argv = [
        "--suite", str(paths["suite"]),
        "--gold", str(paths["gold"]),
        "--selection", str(paths["selection"]),
        "--manifest", str(paths["manifest"]),
        "--output", str(output),
    ]
    assert p2.main(argv) == 0
    assert output.exists()
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == p2.POWER_V2_RECEIPT_SCHEMA
    assert receipt["operating_characteristics"]["null_false_support_rate"] == 0.0
    # first-write-wins: a second run must refuse to replace the receipt
    assert p2.main(argv) == 1
    assert json.loads(output.read_text(encoding="utf-8")) == receipt


def test_cli_manifest_default_is_suite_sibling(tmp_path):
    fixture = _build_fixture(_abstain_answer)
    for name, filename in (
        ("suite", "suite.v4.json"),
        ("gold", "gold.v2.json"),
        ("manifest", "manifest.v3.json"),
        ("selection", "selection.v4.json"),
    ):
        (tmp_path / filename).write_text(
            json.dumps(fixture[name]), encoding="utf-8"
        )
    output = tmp_path / "power-v2.json"
    assert (
        p2.main(
            [
                "--suite", str(tmp_path / "suite.v4.json"),
                "--gold", str(tmp_path / "gold.v2.json"),
                "--selection", str(tmp_path / "selection.v4.json"),
                "--output", str(output),
            ]
        )
        == 0
    )


# ---------------------------------------------------------------------------
# real frozen t2 development cohort (Dell only)
# ---------------------------------------------------------------------------

_REAL_ROOT = Path("/data/kjra/PROJECT/PI/hswm_f1_r8_a3_20260803")
_REAL_SELECTION = _REAL_ROOT / "common" / "selection.v4.json"
_REAL_T2 = _REAL_ROOT / "development-a3-t2"
_JUDGE_RELATIVE_PATH = Path(
    "FINDINGS/hswm-f1-r8-try3-2026-07-28/f1_r8_lakatotree_judge.py"
)


def _resolve_judge_path() -> Path | None:
    repo_root = Path(__file__).resolve().parents[1]
    candidates = (
        repo_root.parents[1],
        repo_root.parent / "SYMPOSIUM",
        repo_root.parent / "symposium",
    )
    matches = {
        candidate.resolve()
        for candidate in candidates
        if (candidate.resolve() / _JUDGE_RELATIVE_PATH).is_file()
    }
    if len(matches) != 1:
        return None
    return next(iter(matches)) / _JUDGE_RELATIVE_PATH


def _load_judge_module(path: Path):
    spec = importlib.util.spec_from_file_location("hswm_f1_r8_frozen_judge_v2_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(
    not os.path.exists(_REAL_SELECTION) or not os.path.exists(_REAL_T2 / "suite.v4.json"),
    reason="real frozen a3 t2 suite is absent (non-Dell host)",
)
def test_real_t2_receipt_builds_and_verifies():
    evidence = m2.load_development_evidence(
        suite_path=_REAL_T2 / "suite.v4.json",
        gold_path=_REAL_T2 / "gold.v2.json",
        manifest_path=_REAL_T2 / "manifest.v3.json",
        selection_path=_REAL_SELECTION,
    )
    components = p2.utility_development_components(evidence)
    assert len(components) == 48
    receipt = _build(
        {
            "suite": m2.load_suite(_REAL_T2 / "suite.v4.json"),
            "gold": m2.load_gold(_REAL_T2 / "gold.v2.json"),
            "manifest": m2.load_manifest(_REAL_T2 / "manifest.v3.json"),
            "selection": m2.load_selection(_REAL_SELECTION),
        }
    )
    declared = p2.verify_power_v2_operating_characteristics(receipt)
    assert declared == receipt["receipt_sha256"]
    characteristics = receipt["operating_characteristics"]
    # v2 development invariants on the real cohort
    assert characteristics["null_false_support_rate"] == 0.0
    assert characteristics["interval_coverage"] >= 0.95
    assert 0.0 <= characteristics["observed_power_at_mde"] <= 1.0
    # the t2 utility contrasts are pinned by the metric golden test
    summary = receipt["analysis_input"]["utility_metric"]
    assert summary["min_contrast"] == "1/6"
    assert summary["per_arm_utility"][TYPED_ARM] == "8/27"
    assert summary["paired_contrasts"][SHUFFLE_ARM] == "1/6"


@pytest.mark.skipif(
    not os.path.exists(_REAL_SELECTION) or not os.path.exists(_REAL_T2 / "suite.v4.json"),
    reason="real frozen a3 t2 suite is absent (non-Dell host)",
)
def test_simulator_parity_with_frozen_v1_judge():
    judge_path = _resolve_judge_path()
    if judge_path is None:
        pytest.skip("frozen v1 judge is not resolvable from this checkout")
    judge = _load_judge_module(judge_path)
    evidence = m2.load_development_evidence(
        suite_path=_REAL_T2 / "suite.v4.json",
        gold_path=_REAL_T2 / "gold.v2.json",
        manifest_path=_REAL_T2 / "manifest.v3.json",
        selection_path=_REAL_SELECTION,
    )
    v2_components = p2.utility_development_components(evidence)
    plan = {
        "schema_version": p2.POWER_V2_SIMULATOR_SCHEMA,
        "trials": p2.TRIALS,
        "master_seed": p2.SELECTION_SEED,
        "selected_cluster_count": p2.SELECTED_CLUSTERS,
        "selection_method": "complete_seed_block_without_replacement/v1",
        "mde": 0.05,
        "target_power": 0.80,
        "scenarios": list(p2.POWER_V2_SCENARIOS),
    }
    v2_result = p2._recompute_utility_power_characteristics(
        v2_components, plan, bootstrap=p2.UTILITY_BOOTSTRAP
    )
    # the same components as v1-style float contrasts, replayed by the frozen
    # v1 judge with the v1 plan/bootstrap: the structure is identical, so the
    # operating characteristics must be byte-identical.
    float_components = [
        {
            **component,
            "contrasts": {
                arm: float(Fraction(value))
                for arm, value in component["contrasts"].items()
            },
        }
        for component in v2_components
    ]
    v1_plan = {
        "schema_version": "hswm-prom9-f1-r8-power-simulator-spec/v1",
        "trials": p2.TRIALS,
        "master_seed": p2.SELECTION_SEED,
        "selected_cluster_count": p2.SELECTED_CLUSTERS,
        "selection_method": "complete_seed_block_without_replacement/v1",
        "mde": 0.05,
        "target_power": 0.80,
        "scenarios": list(p2.POWER_V2_SCENARIOS),
    }
    v1_bootstrap = {
        "reps": 10000,
        "seed": 20260724,
        "lower_index": 249,
        "upper_index": 9749,
        "paired": True,
        "unit": "component_cluster_macro",
        "method": "paired_cluster_percentile_bootstrap_v1",
        "minimum_clusters": 40,
        "metric": "min_of_four_paired_cluster_bootstrap_lcbs",
    }
    v1_result = judge._recompute_power_characteristics(
        float_components, v1_plan, bootstrap=v1_bootstrap
    )
    assert v1_result == v2_result
