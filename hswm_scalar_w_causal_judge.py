"""Frozen pure judge for the HSWM scalar-W causal-shadow preregistration.

This module performs no model calls and has no KG or HSWM_LOCAL_RECORD write path.  It
interprets a content-addressed metric artifact using only the thresholds frozen
in the preregistration.  The judge is intentionally incapable of promoting the
result to operator-valued semantic W.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping


JUDGE_SCHEMA_VERSION = "hswm-scalar-w-causal-judgment/v1"
METRIC_SCHEMA_VERSION = "hswm-semantic-weight-metrics/v1"
REQUIRED_EFFECTS = {
    "transfer_gain",
    "embedding_delta",
    "hyper_only_delta",
    "full_over_embedding_delta",
    "full_over_hypergraph_delta",
    "learned_gain",
    "w_ablation_delta",
    "w_shuffle_delta",
    "w_uniform_delta",
    "w_random_update_delta",
    "context_operator_delta",
    "restoration_gap",
    "restoration_over_removed",
}

EXPECTED_EFFECT_ARMS = {
    "transfer_gain": ("W_FULL_LEARNED", "NO_SHARED_STATE"),
    "embedding_delta": ("EMBEDDING_ONLY", "NO_SHARED_STATE"),
    "hyper_only_delta": ("HYPERGRAPH_ONLY", "NO_SHARED_STATE"),
    "full_over_embedding_delta": ("W_FULL_LEARNED", "EMBEDDING_ONLY"),
    "full_over_hypergraph_delta": ("W_FULL_LEARNED", "HYPERGRAPH_ONLY"),
    "learned_gain": ("W_FULL_LEARNED", None),
    "w_ablation_delta": ("W_FULL_LEARNED", "W_REMOVED_BASE"),
    "w_shuffle_delta": ("W_FULL_LEARNED", "W_SHUFFLED_WITHIN_STRATUM"),
    "w_uniform_delta": ("W_FULL_LEARNED", "W_UNIFORM_L1_MATCHED"),
    "w_random_update_delta": ("W_FULL_LEARNED", "W_RANDOM_UPDATE_MATCHED"),
    "context_operator_delta": (
        "W_FULL_LEARNED",
        "STRONG_CONTEXT_VECTOR_EQUAL_INFO",
    ),
    "restoration_gap": ("W_FULL_LEARNED", "W_RESTORED_EXACT"),
    "restoration_over_removed": ("W_RESTORED_EXACT", "W_REMOVED_BASE"),
}
BASELINE_ALLOWLIST = {
    "FROZEN_NO_WRITE",
    "STRONG_CONTEXT_VECTOR_EQUAL_INFO",
    "W_UNIFORM_L1_MATCHED",
}
ROUTE_COMPARATORS = {
    "W_REMOVED_BASE",
    "W_SHUFFLED_WITHIN_STRATUM",
    "STRONG_CONTEXT_VECTOR_EQUAL_INFO",
}
REQUIRED_METRIC_FIELDS = {
    "schema_version",
    "experiment_id",
    "scope",
    "observation_suite_sha256",
    "strongest_baseline_arm",
    "bootstrap",
    "effects",
    "erasure_fraction",
    "restoration_recovery_fraction",
    "route_jsd_normalized",
    "route_case_count",
    "route_divergence_cases",
    "retention_loss",
    "negative_transfer_rate",
    "seed_direction",
    "scientific_judgment_emitted",
}
REQUIRED_EFFECT_FIELDS = {
    "left_arm",
    "right_arm",
    "mean",
    "lcb95",
    "ucb95",
    "direction",
    "noise_band",
    "clusters",
}
BOOTSTRAP_LOCK = {
    "unit": "component_cluster",
    "samples": 10_000,
    "seed": 20260726,
    "interval": "paired_percentile_95",
}
_HEX = frozenset("0123456789abcdef")


class ScalarWJudgeError(ValueError):
    """The metric artifact is incomplete, drifted, or not judgeable."""


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ScalarWJudgeError(f"metric artifact is not canonical JSON: {error}") from error


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ScalarWJudgeError(f"{field} must be an object")
    return value


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScalarWJudgeError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ScalarWJudgeError(f"{field} must be finite")
    return number


def _effect(effects: Mapping[str, Any], effect_id: str) -> Mapping[str, Any]:
    effect = _mapping(effects.get(effect_id), f"effects.{effect_id}")
    if set(effect) != REQUIRED_EFFECT_FIELDS:
        raise ScalarWJudgeError(f"effects.{effect_id} field set drift")
    if effect.get("noise_band") != [-0.02, 0.02]:
        raise ScalarWJudgeError(f"effects.{effect_id}.noise_band drift")
    mean = _number(effect.get("mean"), f"effects.{effect_id}.mean")
    lcb = _number(effect.get("lcb95"), f"effects.{effect_id}.lcb95")
    ucb = _number(effect.get("ucb95"), f"effects.{effect_id}.ucb95")
    if not -1.0 <= lcb <= mean <= ucb <= 1.0:
        raise ScalarWJudgeError(f"effects.{effect_id} interval is outside [-1,1]")
    expected_direction = "positive" if mean > 0.0 else "negative" if mean < 0.0 else "zero"
    if effect.get("direction") != expected_direction:
        raise ScalarWJudgeError(f"effects.{effect_id}.direction is inconsistent")
    clusters = effect.get("clusters")
    if not isinstance(clusters, int) or isinstance(clusters, bool) or clusters <= 0:
        raise ScalarWJudgeError(f"effects.{effect_id}.clusters must be a positive integer")
    return effect


def judge_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the frozen scalar-W gates and emit a narrow independent judgment."""

    if set(metrics) != REQUIRED_METRIC_FIELDS:
        raise ScalarWJudgeError("metric field set drift")
    if metrics.get("schema_version") != METRIC_SCHEMA_VERSION:
        raise ScalarWJudgeError("unsupported metric schema")
    if metrics.get("experiment_id") != "HSWM-SWCM-1":
        raise ScalarWJudgeError("experiment id drift")
    if metrics.get("scope") != "scalar_slow_efficacy_v1":
        raise ScalarWJudgeError("judge scope is not scalar_slow_efficacy_v1")
    if metrics.get("scientific_judgment_emitted") is not False:
        raise ScalarWJudgeError("producer metric artifact already contains a judgment")
    suite_sha = metrics.get("observation_suite_sha256")
    if (
        not isinstance(suite_sha, str)
        or len(suite_sha) != 64
        or any(character not in _HEX for character in suite_sha)
    ):
        raise ScalarWJudgeError("observation suite SHA drift")
    baseline_arm = metrics.get("strongest_baseline_arm")
    if baseline_arm not in BASELINE_ALLOWLIST:
        raise ScalarWJudgeError("strongest baseline arm drift")
    bootstrap = _mapping(metrics.get("bootstrap"), "bootstrap")
    if dict(bootstrap) != BOOTSTRAP_LOCK:
        raise ScalarWJudgeError("bootstrap lock drift")

    effects = _mapping(metrics.get("effects"), "effects")
    if set(effects) != REQUIRED_EFFECTS:
        raise ScalarWJudgeError("effect set drift")
    checked = {effect_id: _effect(effects, effect_id) for effect_id in sorted(effects)}
    cluster_counts = {effect["clusters"] for effect in checked.values()}
    if len(cluster_counts) != 1:
        raise ScalarWJudgeError("effect cluster counts drift")
    for effect_id, (expected_left, expected_right) in EXPECTED_EFFECT_ARMS.items():
        effect = checked[effect_id]
        right = baseline_arm if expected_right is None else expected_right
        if effect.get("left_arm") != expected_left or effect.get("right_arm") != right:
            raise ScalarWJudgeError(f"effects.{effect_id} arm identity drift")
    transfer = checked["transfer_gain"]
    embedding_control = checked["full_over_embedding_delta"]
    hypergraph_control = checked["full_over_hypergraph_delta"]
    learned = checked["learned_gain"]
    ablation = checked["w_ablation_delta"]
    shuffle = checked["w_shuffle_delta"]
    uniform = checked["w_uniform_delta"]
    random_update = checked["w_random_update_delta"]
    context = checked["context_operator_delta"]
    restoration = checked["restoration_gap"]
    for direct_id, component_id in (
        ("full_over_embedding_delta", "embedding_delta"),
        ("full_over_hypergraph_delta", "hyper_only_delta"),
    ):
        expected_direct_mean = _number(
            transfer["mean"], "transfer_gain.mean"
        ) - _number(checked[component_id]["mean"], f"{component_id}.mean")
        if not math.isclose(
            _number(checked[direct_id]["mean"], f"{direct_id}.mean"),
            expected_direct_mean,
            abs_tol=1e-12,
        ):
            raise ScalarWJudgeError(
                f"{direct_id} contradicts transfer/component effect algebra"
            )
    if not math.isclose(
        _number(ablation["mean"], "ablation.mean"),
        _number(restoration["mean"], "restoration.mean")
        + _number(
            checked["restoration_over_removed"]["mean"],
            "restoration_over_removed.mean",
        ),
        abs_tol=1e-12,
    ):
        raise ScalarWJudgeError("restoration effect means violate the mediation identity")
    baseline_effect_id = {
        "STRONG_CONTEXT_VECTOR_EQUAL_INFO": "context_operator_delta",
        "W_UNIFORM_L1_MATCHED": "w_uniform_delta",
    }.get(baseline_arm)
    if baseline_effect_id is not None and not math.isclose(
        _number(learned["mean"], "learned.mean"),
        _number(checked[baseline_effect_id]["mean"], f"{baseline_effect_id}.mean"),
        abs_tol=1e-12,
    ):
        raise ScalarWJudgeError("learned gain contradicts the selected baseline effect")

    erasure = _mapping(metrics.get("erasure_fraction"), "erasure_fraction")
    expected_erasure = {
        "w_ablation_delta",
        "w_shuffle_delta",
        "w_random_update_delta",
    }
    if set(erasure) != expected_erasure:
        raise ScalarWJudgeError("erasure-fraction set drift")
    if any(erasure[key] is None for key in expected_erasure):
        raise ScalarWJudgeError("erasure fraction undefined because learned gain is non-positive")
    learned_mean = _number(learned["mean"], "learned.mean")
    if learned_mean <= 0.0:
        raise ScalarWJudgeError("learned gain must be positive before mediation ratios")
    for effect_id in expected_erasure:
        expected_fraction = _number(
            checked[effect_id]["mean"], f"effects.{effect_id}.mean"
        ) / learned_mean
        observed_fraction = _number(erasure[effect_id], f"erasure.{effect_id}")
        if not math.isclose(observed_fraction, expected_fraction, abs_tol=1e-12):
            raise ScalarWJudgeError(f"erasure.{effect_id} is inconsistent with effects")

    recovery = _number(
        metrics.get("restoration_recovery_fraction"),
        "restoration_recovery_fraction",
    )
    ablation_mean = _number(ablation["mean"], "ablation.mean")
    if ablation_mean <= 0.0:
        raise ScalarWJudgeError("restoration denominator must be positive")
    expected_recovery = _number(
        checked["restoration_over_removed"]["mean"],
        "restoration_over_removed.mean",
    ) / ablation_mean
    if not math.isclose(recovery, expected_recovery, abs_tol=1e-12):
        raise ScalarWJudgeError("restoration recovery is inconsistent with effects")

    seed_direction = _mapping(metrics.get("seed_direction"), "seed_direction")
    if set(seed_direction) != {"per_seed_gain", "positive_count", "seed_count"}:
        raise ScalarWJudgeError("seed-direction field set drift")
    seed_count = seed_direction.get("seed_count")
    positive_count = seed_direction.get("positive_count")
    if (
        not isinstance(seed_count, int)
        or isinstance(seed_count, bool)
        or not isinstance(positive_count, int)
        or isinstance(positive_count, bool)
    ):
        raise ScalarWJudgeError("seed-direction counts must be integers")
    per_seed = _mapping(seed_direction.get("per_seed_gain"), "seed_direction.per_seed_gain")
    normalized_seed_gains: dict[str, float] = {}
    for seed_id, value in per_seed.items():
        if not isinstance(seed_id, str):
            raise ScalarWJudgeError("seed ids must be canonical non-negative decimal strings")
        try:
            parsed_seed_id = int(seed_id)
        except ValueError as error:
            raise ScalarWJudgeError(
                "seed ids must be canonical non-negative decimal strings"
            ) from error
        if parsed_seed_id < 0 or seed_id != str(parsed_seed_id):
            raise ScalarWJudgeError("seed ids must be canonical non-negative decimal strings")
        gain = _number(value, f"seed_direction.per_seed_gain.{seed_id}")
        if not -1.0 <= gain <= 1.0:
            raise ScalarWJudgeError("per-seed gain must be in [-1,1]")
        normalized_seed_gains[seed_id] = gain
    if seed_count != len(normalized_seed_gains) or positive_count != sum(
        value > 0.0 for value in normalized_seed_gains.values()
    ):
        raise ScalarWJudgeError("seed-direction counts are inconsistent with per-seed gains")
    if seed_count != 5:
        raise ScalarWJudgeError("seed-direction requires exactly five independent seeds")
    if not math.isclose(
        sum(normalized_seed_gains.values()) / seed_count,
        learned_mean,
        abs_tol=1e-12,
    ):
        raise ScalarWJudgeError("per-seed gains do not average to learned gain")

    route_jsd = _mapping(metrics.get("route_jsd_normalized"), "route_jsd_normalized")
    if set(route_jsd) != ROUTE_COMPARATORS:
        raise ScalarWJudgeError("route JSD comparator set drift")
    for comparator, value in route_jsd.items():
        jsd = _number(value, f"route_jsd_normalized.{comparator}")
        if not 0.0 <= jsd <= 1.0:
            raise ScalarWJudgeError(f"route JSD out of range for {comparator}")
    route_divergence_cases = metrics.get("route_divergence_cases")
    if not isinstance(route_divergence_cases, int) or isinstance(
        route_divergence_cases, bool
    ) or route_divergence_cases < 0:
        raise ScalarWJudgeError("route_divergence_cases must be a non-negative integer")
    route_case_count = metrics.get("route_case_count")
    if not isinstance(route_case_count, int) or isinstance(
        route_case_count, bool
    ) or route_case_count <= 0:
        raise ScalarWJudgeError("route_case_count must be a positive integer")
    if route_divergence_cases > route_case_count:
        raise ScalarWJudgeError("route divergence count exceeds route case count")
    cluster_count = next(iter(cluster_counts))
    if route_case_count < cluster_count * seed_count or route_case_count % seed_count:
        raise ScalarWJudgeError("route case count is inconsistent with clusters and seeds")
    intervention_jsd = max(
        _number(route_jsd["W_REMOVED_BASE"], "route_jsd_normalized.W_REMOVED_BASE"),
        _number(
            route_jsd["W_SHUFFLED_WITHIN_STRATUM"],
            "route_jsd_normalized.W_SHUFFLED_WITHIN_STRATUM",
        ),
    )
    if route_divergence_cases > 0 and intervention_jsd <= 1e-12:
        raise ScalarWJudgeError("positive route divergence count contradicts zero intervention JSD")
    if route_divergence_cases == 0 and intervention_jsd > 1e-12:
        raise ScalarWJudgeError("zero route divergence count contradicts positive intervention JSD")

    retention_loss = _number(metrics.get("retention_loss"), "retention_loss")
    if not -1.0 <= retention_loss <= 1.0:
        raise ScalarWJudgeError("retention_loss must be in [-1,1]")
    negative_transfer_rate = _number(
        metrics.get("negative_transfer_rate"), "negative_transfer_rate"
    )
    if not 0.0 <= negative_transfer_rate <= 1.0:
        raise ScalarWJudgeError("negative_transfer_rate must be in [0,1]")
    harmful_cluster_count = negative_transfer_rate * cluster_count
    if not math.isclose(
        harmful_cluster_count, round(harmful_cluster_count), abs_tol=1e-12
    ):
        raise ScalarWJudgeError(
            "negative_transfer_rate is not quantized by the fresh cluster count"
        )

    gates = {
        "transfer_gain_lcb_positive": _number(
            transfer["lcb95"], "transfer_gain.lcb95"
        )
        > 0.0,
        "full_over_embedding_lcb_positive": _number(
            embedding_control["lcb95"], "full_over_embedding_delta.lcb95"
        )
        > 0.0,
        "full_over_hypergraph_lcb_positive": _number(
            hypergraph_control["lcb95"], "full_over_hypergraph_delta.lcb95"
        )
        > 0.0,
        "learned_gain_mean_at_least_0_05": _number(learned["mean"], "learned.mean") >= 0.05,
        "learned_gain_lcb_positive": _number(learned["lcb95"], "learned.lcb95") > 0.0,
        "removal_lcb_positive": _number(ablation["lcb95"], "ablation.lcb95") > 0.0,
        "shuffle_lcb_positive": _number(shuffle["lcb95"], "shuffle.lcb95") > 0.0,
        "uniform_lcb_positive": _number(uniform["lcb95"], "uniform.lcb95") > 0.0,
        "random_update_lcb_positive": _number(random_update["lcb95"], "random.lcb95") > 0.0,
        "context_delta_mean_at_least_0_03": _number(context["mean"], "context.mean") >= 0.03,
        "context_delta_lcb_positive": _number(context["lcb95"], "context.lcb95") > 0.0,
        "removal_erasure_at_least_0_70": _number(
            erasure["w_ablation_delta"], "erasure.w_ablation_delta"
        )
        >= 0.70,
        "shuffle_erasure_at_least_0_70": _number(
            erasure["w_shuffle_delta"], "erasure.w_shuffle_delta"
        )
        >= 0.70,
        "random_erasure_at_least_0_70": _number(
            erasure["w_random_update_delta"], "erasure.w_random_update_delta"
        )
        >= 0.70,
        "restoration_recovery_at_least_0_90": recovery >= 0.90,
        "restoration_interval_inside_rope": _number(
            restoration["lcb95"], "restoration.lcb95"
        )
        >= -0.02
        and _number(restoration["ucb95"], "restoration.ucb95") <= 0.02,
        "retention_loss_at_most_0_03": retention_loss <= 0.03,
        "negative_transfer_rate_at_most_0_10": negative_transfer_rate <= 0.10,
        "route_divergence_cases_at_least_1": route_divergence_cases >= 1,
        "seed_direction_at_least_4_of_5": positive_count >= 4,
    }
    supported = all(gates.values())
    input_sha = canonical_sha256(metrics)
    return {
        "schema_version": JUDGE_SCHEMA_VERSION,
        "judgment_id": canonical_sha256(
            {
                "judge": JUDGE_SCHEMA_VERSION,
                "metric_sha256": input_sha,
            }
        ),
        "metric_sha256": input_sha,
        "experiment_id": metrics["experiment_id"],
        "scope": "scalar_slow_efficacy_v1",
        "decision": (
            "SUPPORTED_SCALAR_CAUSAL_SHADOW_NARROW"
            if supported
            else "REJECTED_OR_NARROW"
        ),
        "gates": gates,
        "failed_gates": sorted(gate for gate, passed in gates.items() if not passed),
        "operator_w_claim_allowed": False,
        "scientific_judgment_emitted": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
        judgment = judge_metrics(_mapping(metrics, "metrics"))
    except (OSError, json.JSONDecodeError, ScalarWJudgeError) as error:
        print(json.dumps({"status": "INVALID", "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(judgment, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "JUDGE_SCHEMA_VERSION",
    "ScalarWJudgeError",
    "judge_metrics",
]
