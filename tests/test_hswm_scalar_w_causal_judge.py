from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from hswm_scalar_w_causal_judge import (
    EXPECTED_EFFECT_ARMS,
    REQUIRED_EFFECTS,
    ScalarWJudgeError,
    judge_metrics,
)


ROOT = Path(__file__).resolve().parents[1]


def effect(mean: float, lcb: float, ucb: float) -> dict[str, object]:
    return {
        "left_arm": "left",
        "right_arm": "right",
        "mean": mean,
        "lcb95": lcb,
        "ucb95": ucb,
        "direction": "positive" if mean > 0 else "zero",
        "noise_band": [-0.02, 0.02],
        "clusters": 2,
    }


def passing_metrics() -> dict[str, object]:
    effects = {name: effect(0.10, 0.05, 0.15) for name in REQUIRED_EFFECTS}
    effects["transfer_gain"] = effect(0.40, 0.30, 0.50)
    effects["embedding_delta"] = effect(0.10, 0.05, 0.15)
    effects["hyper_only_delta"] = effect(0.12, 0.06, 0.18)
    effects["full_over_embedding_delta"] = effect(0.30, 0.20, 0.40)
    effects["full_over_hypergraph_delta"] = effect(0.28, 0.18, 0.38)
    effects["learned_gain"] = effect(0.30, 0.20, 0.40)
    effects["w_ablation_delta"] = effect(0.25, 0.15, 0.35)
    effects["w_shuffle_delta"] = effect(0.24, 0.14, 0.34)
    effects["w_random_update_delta"] = effect(0.23, 0.13, 0.33)
    effects["context_operator_delta"] = effect(0.30, 0.20, 0.40)
    effects["restoration_gap"] = effect(0.0, -0.01, 0.01)
    effects["restoration_over_removed"] = effect(0.25, 0.15, 0.35)
    baseline = "STRONG_CONTEXT_VECTOR_EQUAL_INFO"
    for effect_id, (left_arm, right_arm) in EXPECTED_EFFECT_ARMS.items():
        effects[effect_id]["left_arm"] = left_arm
        effects[effect_id]["right_arm"] = baseline if right_arm is None else right_arm
    return {
        "schema_version": "hswm-semantic-weight-metrics/v1",
        "experiment_id": "HSWM-SWCM-1",
        "scope": "scalar_slow_efficacy_v1",
        "observation_suite_sha256": "0" * 64,
        "strongest_baseline_arm": baseline,
        "bootstrap": {
            "unit": "component_cluster",
            "samples": 10000,
            "seed": 20260726,
            "interval": "paired_percentile_95",
        },
        "effects": effects,
        "erasure_fraction": {
            "w_ablation_delta": 0.25 / 0.30,
            "w_shuffle_delta": 0.24 / 0.30,
            "w_random_update_delta": 0.23 / 0.30,
        },
        "restoration_recovery_fraction": 1.0,
        "route_jsd_normalized": {
            "W_REMOVED_BASE": 0.2,
            "W_SHUFFLED_WITHIN_STRATUM": 0.15,
            "STRONG_CONTEXT_VECTOR_EQUAL_INFO": 0.1,
        },
        "route_case_count": 10,
        "route_divergence_cases": 10,
        "retention_loss": 0.01,
        "negative_transfer_rate": 0.0,
        "seed_direction": {
            "per_seed_gain": {str(seed): 0.30 for seed in range(1, 6)},
            "positive_count": 5,
            "seed_count": 5,
        },
        "scientific_judgment_emitted": False,
    }


def test_pure_judge_accepts_only_narrow_scalar_claim() -> None:
    judgment = judge_metrics(passing_metrics())
    assert judgment["decision"] == "SUPPORTED_SCALAR_CAUSAL_SHADOW_NARROW"
    assert judgment["operator_w_claim_allowed"] is False
    assert judgment["failed_gates"] == []


def test_pure_judge_rejects_failed_mediation_without_compensation() -> None:
    metrics = passing_metrics()
    metrics["effects"]["w_shuffle_delta"] = effect(0.207, 0.10, 0.30)
    metrics["effects"]["w_shuffle_delta"]["left_arm"] = "W_FULL_LEARNED"
    metrics["effects"]["w_shuffle_delta"]["right_arm"] = (
        "W_SHUFFLED_WITHIN_STRATUM"
    )
    metrics["erasure_fraction"]["w_shuffle_delta"] = 0.69
    judgment = judge_metrics(metrics)
    assert judgment["decision"] == "REJECTED_OR_NARROW"
    assert "shuffle_erasure_at_least_0_70" in judgment["failed_gates"]


@pytest.mark.parametrize(
    ("effect_id", "gate_id"),
    [
        ("transfer_gain", "transfer_gain_lcb_positive"),
        ("full_over_embedding_delta", "full_over_embedding_lcb_positive"),
        ("full_over_hypergraph_delta", "full_over_hypergraph_lcb_positive"),
        ("w_uniform_delta", "uniform_lcb_positive"),
    ],
)
def test_pure_judge_rejects_each_non_w_control_compensation(
    effect_id: str, gate_id: str
) -> None:
    metrics = passing_metrics()
    metrics["effects"][effect_id]["lcb95"] = -0.01
    judgment = judge_metrics(metrics)
    assert judgment["decision"] == "REJECTED_OR_NARROW"
    assert gate_id in judgment["failed_gates"]


def test_pure_judge_rejects_embedding_matching_full_without_compensation() -> None:
    metrics = passing_metrics()
    metrics["effects"]["embedding_delta"] = effect(0.40, 0.30, 0.50)
    metrics["effects"]["embedding_delta"]["left_arm"] = "EMBEDDING_ONLY"
    metrics["effects"]["embedding_delta"]["right_arm"] = "NO_SHARED_STATE"
    metrics["effects"]["full_over_embedding_delta"] = effect(0.0, -0.01, 0.01)
    metrics["effects"]["full_over_embedding_delta"]["left_arm"] = "W_FULL_LEARNED"
    metrics["effects"]["full_over_embedding_delta"]["right_arm"] = "EMBEDDING_ONLY"
    judgment = judge_metrics(metrics)
    assert judgment["decision"] == "REJECTED_OR_NARROW"
    assert "full_over_embedding_lcb_positive" in judgment["failed_gates"]


def test_pure_judge_rejects_producer_judgment_and_noise_band_drift() -> None:
    judged = passing_metrics()
    judged["scientific_judgment_emitted"] = True
    with pytest.raises(ScalarWJudgeError, match="already contains"):
        judge_metrics(judged)

    drifted = passing_metrics()
    drifted["effects"]["learned_gain"]["noise_band"] = [-0.05, 0.05]
    with pytest.raises(ScalarWJudgeError, match="noise_band drift"):
        judge_metrics(drifted)


def test_pure_judge_requires_exact_effect_set_and_10000_bootstraps() -> None:
    missing = passing_metrics()
    del missing["effects"]["hyper_only_delta"]
    with pytest.raises(ScalarWJudgeError, match="effect set"):
        judge_metrics(missing)

    weak = passing_metrics()
    weak["bootstrap"]["samples"] = 9999
    with pytest.raises(ScalarWJudgeError, match="bootstrap lock"):
        judge_metrics(weak)


def test_pure_judge_rejects_experiment_and_effect_arm_identity_drift() -> None:
    wrong_experiment = passing_metrics()
    wrong_experiment["experiment_id"] = "HSWM-SWCM-FORGED"
    with pytest.raises(ScalarWJudgeError, match="experiment id drift"):
        judge_metrics(wrong_experiment)

    wrong_arm = passing_metrics()
    wrong_arm["effects"]["w_ablation_delta"]["right_arm"] = (
        "W_SHUFFLED_WITHIN_STRATUM"
    )
    with pytest.raises(ScalarWJudgeError, match="arm identity drift"):
        judge_metrics(wrong_arm)


def test_pure_judge_recomputes_seed_direction_counts() -> None:
    inconsistent = passing_metrics()
    inconsistent["seed_direction"]["positive_count"] = 4
    with pytest.raises(ScalarWJudgeError, match="counts are inconsistent"):
        judge_metrics(inconsistent)

    too_many = passing_metrics()
    too_many["seed_direction"]["per_seed_gain"]["6"] = 0.30
    too_many["seed_direction"]["positive_count"] = 6
    too_many["seed_direction"]["seed_count"] = 6
    with pytest.raises(ScalarWJudgeError, match="exactly five"):
        judge_metrics(too_many)

    noncanonical = passing_metrics()
    noncanonical["seed_direction"]["per_seed_gain"] = {
        seed_id: 0.30 for seed_id in ("a", "b", "c", "d", "e")
    }
    with pytest.raises(ScalarWJudgeError, match="canonical non-negative"):
        judge_metrics(noncanonical)

    out_of_range = passing_metrics()
    out_of_range["seed_direction"]["per_seed_gain"]["1"] = 2.0
    with pytest.raises(ScalarWJudgeError, match=r"gain must be in \[-1,1\]"):
        judge_metrics(out_of_range)

    inconsistent_mean = passing_metrics()
    inconsistent_mean["seed_direction"]["per_seed_gain"] = {
        str(seed): 0.20 for seed in range(1, 6)
    }
    with pytest.raises(ScalarWJudgeError, match="do not average"):
        judge_metrics(inconsistent_mean)


def test_pure_judge_requires_complete_bounded_route_evidence() -> None:
    missing_jsd = passing_metrics()
    del missing_jsd["route_jsd_normalized"]
    with pytest.raises(ScalarWJudgeError, match="metric field set drift"):
        judge_metrics(missing_jsd)

    boolean_count = passing_metrics()
    boolean_count["route_divergence_cases"] = True
    with pytest.raises(ScalarWJudgeError, match="non-negative integer"):
        judge_metrics(boolean_count)

    out_of_range = passing_metrics()
    out_of_range["route_jsd_normalized"]["W_REMOVED_BASE"] = 1.01
    with pytest.raises(ScalarWJudgeError, match="route JSD out of range"):
        judge_metrics(out_of_range)

    contradictory = passing_metrics()
    contradictory["route_jsd_normalized"] = {
        comparator: 0.0 for comparator in contradictory["route_jsd_normalized"]
    }
    with pytest.raises(ScalarWJudgeError, match="contradicts zero"):
        judge_metrics(contradictory)

    converse = passing_metrics()
    converse["route_divergence_cases"] = 0
    with pytest.raises(ScalarWJudgeError, match="contradicts positive"):
        judge_metrics(converse)

    impossible_count = passing_metrics()
    impossible_count["route_divergence_cases"] = 11
    with pytest.raises(ScalarWJudgeError, match="exceeds route case count"):
        judge_metrics(impossible_count)


def test_pure_judge_recomputes_erasure_and_restoration_ratios() -> None:
    forged_erasure = passing_metrics()
    forged_erasure["erasure_fraction"]["w_ablation_delta"] = 0.99
    with pytest.raises(ScalarWJudgeError, match="inconsistent with effects"):
        judge_metrics(forged_erasure)

    forged_recovery = passing_metrics()
    forged_recovery["restoration_recovery_fraction"] = 0.99
    with pytest.raises(ScalarWJudgeError, match="recovery is inconsistent"):
        judge_metrics(forged_recovery)

    broken_identity = passing_metrics()
    broken_identity["effects"]["restoration_over_removed"]["mean"] = 0.24
    with pytest.raises(ScalarWJudgeError, match="mediation identity"):
        judge_metrics(broken_identity)

    baseline_mismatch = passing_metrics()
    baseline_mismatch["effects"]["context_operator_delta"]["mean"] = 0.29
    with pytest.raises(ScalarWJudgeError, match="selected baseline"):
        judge_metrics(baseline_mismatch)


def test_pure_judge_requires_exact_bootstrap_and_metric_shape() -> None:
    for field in ("seed", "interval"):
        missing = passing_metrics()
        del missing["bootstrap"][field]
        with pytest.raises(ScalarWJudgeError, match="bootstrap lock drift"):
            judge_metrics(missing)

    extra = passing_metrics()
    extra["unregistered_metric"] = 1
    with pytest.raises(ScalarWJudgeError, match="metric field set drift"):
        judge_metrics(extra)


def test_pure_judge_rejects_impossible_rate_and_effect_ranges() -> None:
    negative_rate = passing_metrics()
    negative_rate["negative_transfer_rate"] = -0.01
    with pytest.raises(ScalarWJudgeError, match=r"must be in \[0,1\]"):
        judge_metrics(negative_rate)

    unquantized_rate = passing_metrics()
    unquantized_rate["negative_transfer_rate"] = 0.05
    with pytest.raises(ScalarWJudgeError, match="not quantized"):
        judge_metrics(unquantized_rate)

    impossible_effect = passing_metrics()
    impossible_effect["effects"]["transfer_gain"]["ucb95"] = 1.1
    with pytest.raises(ScalarWJudgeError, match=r"outside \[-1,1\]"):
        judge_metrics(impossible_effect)


def test_judge_cli_replays_a_frozen_metric_file(tmp_path: Path) -> None:
    metric_path = tmp_path / "metrics.json"
    metric_path.write_text(json.dumps(passing_metrics()), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "hswm_scalar_w_causal_judge.py",
            "--metrics",
            str(metric_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["decision"] == (
        "SUPPORTED_SCALAR_CAUSAL_SHADOW_NARROW"
    )
