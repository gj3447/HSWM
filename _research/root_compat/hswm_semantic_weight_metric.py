"""Pure observation validator and metric reducer for HSWM semantic-W tests.

The reducer emits measurements, confidence intervals, and intervention
diagnostics.  It intentionally emits no PASS/FAIL or scientific verdict.  A
separate preregistered judge must interpret these observations after the run.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable, Mapping, Sequence

from hswm_weight_snapshot import canonical_sha256


METRIC_SCHEMA_VERSION = "hswm-semantic-weight-observation/v1"
EVALUATION_SCHEMA_VERSION = "hswm-semantic-weight-metrics/v1"

W_FULL = "W_FULL_LEARNED"
W_REMOVED = "W_REMOVED_BASE"
W_SHUFFLED = "W_SHUFFLED_WITHIN_STRATUM"
W_RESTORED = "W_RESTORED_EXACT"
W_UNIFORM = "W_UNIFORM_L1_MATCHED"
W_RANDOM = "W_RANDOM_UPDATE_MATCHED"
FROZEN = "FROZEN_NO_WRITE"
CONTEXT_VECTOR = "STRONG_CONTEXT_VECTOR_EQUAL_INFO"
NO_SHARED = "NO_SHARED_STATE"
EMBEDDING_ONLY = "EMBEDDING_ONLY"
HYPERGRAPH_ONLY = "HYPERGRAPH_ONLY"

REQUIRED_ARMS = (
    NO_SHARED,
    EMBEDDING_ONLY,
    HYPERGRAPH_ONLY,
    FROZEN,
    CONTEXT_VECTOR,
    W_UNIFORM,
    W_RANDOM,
    W_FULL,
    W_REMOVED,
    W_SHUFFLED,
    W_RESTORED,
)

PARITY_FIELDS = (
    "model_sha256",
    "task_sha256",
    "topology_sha256",
    "embedding_sha256",
    "relation_schema_sha256",
    "candidate_universe_sha256",
    "raw_information_union_sha256",
    "compute_envelope_sha256",
    "physical_call_cap",
    "logical_call_cap",
    "input_token_cap",
    "output_token_cap",
    "state_budget_bytes",
)

SHA_FIELDS = (
    "model_sha256",
    "task_sha256",
    "topology_sha256",
    "embedding_sha256",
    "relation_schema_sha256",
    "candidate_universe_sha256",
    "raw_information_union_sha256",
    "compute_envelope_sha256",
    "treatment_payload_sha256",
    "weight_snapshot_sha256",
    "pre_llm_logits_sha256",
    "pre_llm_rank_sha256",
    "route_digest",
)

OBSERVATION_FIELDS = {
    "schema_version",
    "experiment_id",
    "item_id",
    "cluster_id",
    "cohort",
    "seed",
    "arm_id",
    "sequence_id",
    "arm_order_position",
    "utility",
    *SHA_FIELDS,
    "physical_call_cap",
    "logical_call_cap",
    "input_token_cap",
    "output_token_cap",
    "state_budget_bytes",
    "eligibility_seal_index",
    "outcome_observe_index",
    "answer_seal_index",
    "gold_reveal_index",
    "cache_hits",
    "route_probabilities",
}

_HEX = frozenset("0123456789abcdef")


class SemanticWeightMetricError(ValueError):
    """An observation suite violates a metric or isolation contract."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise SemanticWeightMetricError(f"{field} must be non-empty text")
    return value


def _sha(value: object, field: str) -> str:
    text = _text(value, field)
    if len(text) != 64 or any(character not in _HEX for character in text):
        raise SemanticWeightMetricError(f"{field} must be a lowercase SHA-256")
    return text


def _nonnegative_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SemanticWeightMetricError(f"{field} must be a non-negative integer")
    return value


def _probabilities(value: object) -> tuple[tuple[str, float], ...]:
    if not isinstance(value, Mapping) or not value:
        raise SemanticWeightMetricError("route_probabilities must be a non-empty object")
    normalized: list[tuple[str, float]] = []
    for edge_id, raw_probability in value.items():
        edge = _text(edge_id, "route_probabilities edge id")
        if isinstance(raw_probability, bool) or not isinstance(raw_probability, (int, float)):
            raise SemanticWeightMetricError(f"route probability for {edge} must be numeric")
        probability = float(raw_probability)
        if not math.isfinite(probability) or probability < 0.0 or probability > 1.0:
            raise SemanticWeightMetricError(f"invalid route probability for {edge}")
        normalized.append((edge, probability))
    normalized.sort()
    if not math.isclose(sum(probability for _, probability in normalized), 1.0, abs_tol=1e-9):
        raise SemanticWeightMetricError("route probabilities must sum to one")
    return tuple(normalized)


@dataclass(frozen=True)
class SemanticWeightObservationV1:
    schema_version: str
    experiment_id: str
    item_id: str
    cluster_id: str
    cohort: str
    seed: int
    arm_id: str
    sequence_id: str
    arm_order_position: int
    utility: float
    model_sha256: str
    task_sha256: str
    topology_sha256: str
    embedding_sha256: str
    relation_schema_sha256: str
    candidate_universe_sha256: str
    raw_information_union_sha256: str
    compute_envelope_sha256: str
    treatment_payload_sha256: str
    weight_snapshot_sha256: str
    pre_llm_logits_sha256: str
    pre_llm_rank_sha256: str
    route_digest: str
    physical_call_cap: int
    logical_call_cap: int
    input_token_cap: int
    output_token_cap: int
    state_budget_bytes: int
    eligibility_seal_index: int
    outcome_observe_index: int
    answer_seal_index: int
    gold_reveal_index: int
    cache_hits: int
    route_probabilities: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        if self.schema_version != METRIC_SCHEMA_VERSION:
            raise SemanticWeightMetricError("unsupported observation schema")
        for field in ("experiment_id", "item_id", "cluster_id", "arm_id", "sequence_id"):
            _text(getattr(self, field), field)
        if self.cohort not in {"fresh", "retention"}:
            raise SemanticWeightMetricError("cohort must be fresh or retention")
        _nonnegative_int(self.seed, "seed")
        _nonnegative_int(self.arm_order_position, "arm_order_position")
        if self.arm_id not in REQUIRED_ARMS:
            raise SemanticWeightMetricError(f"unknown arm_id {self.arm_id!r}")
        if isinstance(self.utility, bool) or not isinstance(self.utility, (int, float)):
            raise SemanticWeightMetricError("utility must be numeric")
        utility = float(self.utility)
        if not math.isfinite(utility) or not 0.0 <= utility <= 1.0:
            raise SemanticWeightMetricError("utility must be finite and in [0, 1]")
        object.__setattr__(self, "utility", utility)
        for field in SHA_FIELDS:
            _sha(getattr(self, field), field)
        for field in (
            "physical_call_cap",
            "logical_call_cap",
            "input_token_cap",
            "output_token_cap",
            "state_budget_bytes",
            "eligibility_seal_index",
            "outcome_observe_index",
            "answer_seal_index",
            "gold_reveal_index",
            "cache_hits",
        ):
            _nonnegative_int(getattr(self, field), field)
        if self.physical_call_cap == 0 or self.logical_call_cap == 0:
            raise SemanticWeightMetricError("call caps must be positive")
        if self.eligibility_seal_index >= self.outcome_observe_index:
            raise SemanticWeightMetricError("eligibility must be sealed before outcome")
        if self.answer_seal_index >= self.gold_reveal_index:
            raise SemanticWeightMetricError("answer must be sealed before gold reveal")
        if self.cache_hits != 0:
            raise SemanticWeightMetricError("sealed metric requires cache_hits=0")
        probabilities = _probabilities(dict(self.route_probabilities))
        if self.route_digest != canonical_sha256(dict(probabilities)):
            raise SemanticWeightMetricError(
                "route_digest does not match canonical route probabilities"
            )
        object.__setattr__(self, "route_probabilities", probabilities)

    def canonical(self) -> dict[str, object]:
        return {
            field: (
                dict(self.route_probabilities)
                if field == "route_probabilities"
                else getattr(self, field)
            )
            for field in sorted(OBSERVATION_FIELDS)
        }


def observation_from_mapping(value: Mapping[str, object]) -> SemanticWeightObservationV1:
    keys = set(value)
    if keys != OBSERVATION_FIELDS:
        missing = sorted(OBSERVATION_FIELDS - keys)
        extra = sorted(keys - OBSERVATION_FIELDS)
        raise SemanticWeightMetricError(
            f"observation fields must be exact; missing={missing} extra={extra}"
        )
    return SemanticWeightObservationV1(
        **{**value, "route_probabilities": _probabilities(value["route_probabilities"])}  # type: ignore[arg-type]
    )


def _parity_signature(row: SemanticWeightObservationV1) -> tuple[object, ...]:
    return tuple(getattr(row, field) for field in PARITY_FIELDS)


def validate_observation_suite(
    observations: Iterable[SemanticWeightObservationV1],
) -> tuple[SemanticWeightObservationV1, ...]:
    rows = tuple(observations)
    if not rows:
        raise SemanticWeightMetricError("observation suite must not be empty")
    if len({row.experiment_id for row in rows}) != 1:
        raise SemanticWeightMetricError("suite mixes experiment ids")

    grouped: dict[tuple[str, int, str], list[SemanticWeightObservationV1]] = {}
    for row in rows:
        grouped.setdefault((row.item_id, row.seed, row.cohort), []).append(row)
    required = set(REQUIRED_ARMS)
    for key, group in grouped.items():
        arms = [row.arm_id for row in group]
        if len(arms) != len(set(arms)) or set(arms) != required:
            raise SemanticWeightMetricError(
                f"{key} must contain each required arm exactly once"
            )
        if len({_parity_signature(row) for row in group}) != 1:
            raise SemanticWeightMetricError(f"{key} violates equal-compute or equal-input parity")
        if len({row.cluster_id for row in group}) != 1:
            raise SemanticWeightMetricError(f"{key} crosses cluster ids")
        if len({row.sequence_id for row in group}) != 1:
            raise SemanticWeightMetricError(f"{key} mixes intervention sequence ids")
        if {row.arm_order_position for row in group} != set(range(len(REQUIRED_ARMS))):
            raise SemanticWeightMetricError(f"{key} arm order is not a full counterbalance permutation")
        candidate_sets = {
            tuple(edge_id for edge_id, _ in row.route_probabilities) for row in group
        }
        if len(candidate_sets) != 1:
            raise SemanticWeightMetricError(f"{key} route candidate support drift")

        by_arm = {row.arm_id: row for row in group}
        full = by_arm[W_FULL]
        restored = by_arm[W_RESTORED]
        removed = by_arm[W_REMOVED]
        frozen = by_arm[FROZEN]
        sequence_id = full.sequence_id
        positions = {
            arm: by_arm[arm].arm_order_position
            for arm in (W_FULL, W_REMOVED, W_SHUFFLED, W_RESTORED)
        }
        valid_order = (
            sequence_id == "FULL_REMOVE_SHUFFLE_RESTORE"
            and positions[W_FULL]
            < positions[W_REMOVED]
            < positions[W_SHUFFLED]
            < positions[W_RESTORED]
        ) or (
            sequence_id == "FULL_SHUFFLE_REMOVE_RESTORE"
            and positions[W_FULL]
            < positions[W_SHUFFLED]
            < positions[W_REMOVED]
            < positions[W_RESTORED]
        )
        if not valid_order:
            raise SemanticWeightMetricError(
                f"{key} does not match either frozen FULL-intervention-RESTORED sequence"
            )
        if restored.weight_snapshot_sha256 != full.weight_snapshot_sha256:
            raise SemanticWeightMetricError(f"{key} restored W is not bit-identical to full W")
        if restored.route_digest != full.route_digest:
            raise SemanticWeightMetricError(f"{key} restored route digest differs from full")
        if restored.pre_llm_logits_sha256 != full.pre_llm_logits_sha256:
            raise SemanticWeightMetricError(f"{key} restored pre-LLM logits differ from full")
        if restored.pre_llm_rank_sha256 != full.pre_llm_rank_sha256:
            raise SemanticWeightMetricError(f"{key} restored pre-LLM rank differs from full")
        if removed.weight_snapshot_sha256 != frozen.weight_snapshot_sha256:
            raise SemanticWeightMetricError(f"{key} removed W is not the frozen base W")
        for arm in (NO_SHARED, EMBEDDING_ONLY, HYPERGRAPH_ONLY, CONTEXT_VECTOR):
            if by_arm[arm].weight_snapshot_sha256 != frozen.weight_snapshot_sha256:
                raise SemanticWeightMetricError(f"{key} {arm} mounted non-base W")
        for arm in (W_SHUFFLED, W_UNIFORM, W_RANDOM):
            snapshot = by_arm[arm].weight_snapshot_sha256
            if snapshot in {full.weight_snapshot_sha256, frozen.weight_snapshot_sha256}:
                raise SemanticWeightMetricError(f"{key} {arm} failed to intervene on W")
    cohorts = {row.cohort for row in rows}
    if cohorts != {"fresh", "retention"}:
        raise SemanticWeightMetricError("suite requires both fresh and retention cohorts")
    seeds_by_cohort = {
        cohort: {row.seed for row in rows if row.cohort == cohort} for cohort in cohorts
    }
    if any(len(seeds) != 5 for seeds in seeds_by_cohort.values()):
        raise SemanticWeightMetricError("each cohort requires exactly five independent seeds")
    if seeds_by_cohort["fresh"] != seeds_by_cohort["retention"]:
        raise SemanticWeightMetricError("fresh and retention cohorts must use identical seeds")
    for cohort in cohorts:
        sequence_counts: dict[str, int] = {}
        for key, group in grouped.items():
            if key[2] == cohort:
                sequence_id = group[0].sequence_id
                sequence_counts[sequence_id] = sequence_counts.get(sequence_id, 0) + 1
        if set(sequence_counts) != {
            "FULL_REMOVE_SHUFFLE_RESTORE",
            "FULL_SHUFFLE_REMOVE_RESTORE",
        } or len(set(sequence_counts.values())) != 1:
            raise SemanticWeightMetricError(
                f"{cohort} cohort must balance both frozen intervention sequences"
            )
    return tuple(sorted(rows, key=lambda row: (row.cohort, row.cluster_id, row.item_id, row.seed, row.arm_id)))


def _quantile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise SemanticWeightMetricError("cannot take a quantile of an empty sample")
    position = (len(sorted_values) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def _paired_cluster_effect(
    cluster_values: Mapping[str, Mapping[str, float]],
    left_arm: str,
    right_arm: str,
    *,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, object]:
    cluster_ids = sorted(cluster_values)
    differences = [
        cluster_values[cluster_id][left_arm] - cluster_values[cluster_id][right_arm]
        for cluster_id in cluster_ids
    ]
    mean = sum(differences) / len(differences)
    rng = random.Random(seed)
    boot = []
    for _ in range(bootstrap_samples):
        sample = [differences[rng.randrange(len(differences))] for _ in differences]
        boot.append(sum(sample) / len(sample))
    boot.sort()
    lcb = _quantile(boot, 0.025)
    ucb = _quantile(boot, 0.975)
    direction = "positive" if mean > 0 else "negative" if mean < 0 else "zero"
    return {
        "left_arm": left_arm,
        "right_arm": right_arm,
        "mean": mean,
        "lcb95": lcb,
        "ucb95": ucb,
        "direction": direction,
        "noise_band": [-0.02, 0.02],
        "clusters": len(differences),
    }


def _jsd(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    if set(left) != set(right):
        raise SemanticWeightMetricError("JSD inputs have different candidate support")
    total = 0.0
    for edge_id in sorted(left):
        p = left[edge_id]
        q = right[edge_id]
        midpoint = (p + q) / 2.0
        if p > 0.0:
            total += 0.5 * p * math.log(p / midpoint)
        if q > 0.0:
            total += 0.5 * q * math.log(q / midpoint)
    return total / math.log(2.0)


def _cluster_arm_means(
    rows: Sequence[SemanticWeightObservationV1], cohort: str
) -> dict[str, dict[str, float]]:
    buckets: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        if row.cohort == cohort:
            buckets.setdefault((row.cluster_id, row.arm_id), []).append(row.utility)
    clusters = sorted({cluster_id for cluster_id, _ in buckets})
    if not clusters:
        return {}
    result: dict[str, dict[str, float]] = {}
    for cluster_id in clusters:
        result[cluster_id] = {}
        for arm in REQUIRED_ARMS:
            values = buckets.get((cluster_id, arm))
            if not values:
                raise SemanticWeightMetricError(f"cluster {cluster_id} lacks arm {arm}")
            result[cluster_id][arm] = sum(values) / len(values)
    return result


def evaluate_observations(
    observations: Iterable[SemanticWeightObservationV1],
    *,
    strongest_baseline_arm: str,
    bootstrap_samples: int = 10_000,
    seed: int = 20260726,
) -> dict[str, object]:
    """Reduce frozen observations without deciding whether gates passed."""

    if strongest_baseline_arm not in {FROZEN, CONTEXT_VECTOR, W_UNIFORM}:
        raise SemanticWeightMetricError("strongest baseline was not dev-selected from the allowlist")
    if bootstrap_samples < 1000:
        raise SemanticWeightMetricError("bootstrap_samples must be at least 1000")
    rows = validate_observation_suite(observations)
    fresh = _cluster_arm_means(rows, "fresh")
    if not fresh:
        raise SemanticWeightMetricError("fresh cohort is required")

    comparisons = {
        "transfer_gain": (W_FULL, NO_SHARED),
        "embedding_delta": (EMBEDDING_ONLY, NO_SHARED),
        "hyper_only_delta": (HYPERGRAPH_ONLY, NO_SHARED),
        "full_over_embedding_delta": (W_FULL, EMBEDDING_ONLY),
        "full_over_hypergraph_delta": (W_FULL, HYPERGRAPH_ONLY),
        "learned_gain": (W_FULL, strongest_baseline_arm),
        "w_ablation_delta": (W_FULL, W_REMOVED),
        "w_shuffle_delta": (W_FULL, W_SHUFFLED),
        "w_uniform_delta": (W_FULL, W_UNIFORM),
        "w_random_update_delta": (W_FULL, W_RANDOM),
        "context_operator_delta": (W_FULL, CONTEXT_VECTOR),
        "restoration_gap": (W_FULL, W_RESTORED),
        "restoration_over_removed": (W_RESTORED, W_REMOVED),
    }
    effects = {
        metric_id: _paired_cluster_effect(
            fresh,
            left,
            right,
            bootstrap_samples=bootstrap_samples,
            seed=seed + index,
        )
        for index, (metric_id, (left, right)) in enumerate(comparisons.items())
    }
    learned_gain = float(effects["learned_gain"]["mean"])
    erasure: dict[str, float | None] = {}
    for metric_id in ("w_ablation_delta", "w_shuffle_delta", "w_random_update_delta"):
        erasure[metric_id] = (
            float(effects[metric_id]["mean"]) / learned_gain
            if learned_gain > 0.0
            else None
        )
    removed_gain = float(effects["w_ablation_delta"]["mean"])
    recovery = (
        float(effects["restoration_over_removed"]["mean"]) / removed_gain
        if removed_gain > 0.0
        else None
    )

    route_jsd: dict[str, float] = {}
    route_divergence_cases = 0
    route_case_count = 0
    for comparator in (W_REMOVED, W_SHUFFLED, CONTEXT_VECTOR):
        values = []
        by_key = {
            (row.item_id, row.seed, row.cohort, row.arm_id): row for row in rows
        }
        for row in rows:
            if row.cohort != "fresh" or row.arm_id != W_FULL:
                continue
            other = by_key[(row.item_id, row.seed, row.cohort, comparator)]
            values.append(_jsd(dict(row.route_probabilities), dict(other.route_probabilities)))
        route_jsd[comparator] = sum(values) / len(values)
    by_key = {(row.item_id, row.seed, row.cohort, row.arm_id): row for row in rows}
    for row in rows:
        if row.cohort != "fresh" or row.arm_id != W_FULL:
            continue
        route_case_count += 1
        removed = by_key[(row.item_id, row.seed, row.cohort, W_REMOVED)]
        shuffled = by_key[(row.item_id, row.seed, row.cohort, W_SHUFFLED)]
        if max(
            _jsd(dict(row.route_probabilities), dict(removed.route_probabilities)),
            _jsd(dict(row.route_probabilities), dict(shuffled.route_probabilities)),
        ) > 1e-12:
            route_divergence_cases += 1

    retention = _cluster_arm_means(rows, "retention")
    baseline_mean = sum(
        values[strongest_baseline_arm] for values in retention.values()
    ) / len(retention)
    full_mean = sum(values[W_FULL] for values in retention.values()) / len(retention)
    retention_loss = baseline_mean - full_mean
    negative_transfer_rate = sum(
        values[W_FULL] < values[strongest_baseline_arm] for values in fresh.values()
    ) / len(fresh)
    seed_cluster_values: dict[tuple[int, str, str], list[float]] = {}
    for row in rows:
        if row.cohort == "fresh" and row.arm_id in {W_FULL, strongest_baseline_arm}:
            seed_cluster_values.setdefault(
                (row.seed, row.cluster_id, row.arm_id), []
            ).append(row.utility)
    per_seed_gain: dict[str, float] = {}
    for seed_id in sorted({key[0] for key in seed_cluster_values}):
        cluster_differences = []
        for cluster_id in sorted(
            {key[1] for key in seed_cluster_values if key[0] == seed_id}
        ):
            full_values = seed_cluster_values[(seed_id, cluster_id, W_FULL)]
            baseline_values = seed_cluster_values[
                (seed_id, cluster_id, strongest_baseline_arm)
            ]
            cluster_differences.append(
                sum(full_values) / len(full_values)
                - sum(baseline_values) / len(baseline_values)
            )
        per_seed_gain[str(seed_id)] = sum(cluster_differences) / len(
            cluster_differences
        )
    seed_direction = {
        "per_seed_gain": per_seed_gain,
        "positive_count": sum(value > 0.0 for value in per_seed_gain.values()),
        "seed_count": len(per_seed_gain),
    }

    canonical_rows = [row.canonical() for row in rows]
    return {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "experiment_id": rows[0].experiment_id,
        "scope": "scalar_slow_efficacy_v1",
        "observation_suite_sha256": canonical_sha256(canonical_rows),
        "strongest_baseline_arm": strongest_baseline_arm,
        "bootstrap": {
            "unit": "component_cluster",
            "samples": bootstrap_samples,
            "seed": seed,
            "interval": "paired_percentile_95",
        },
        "effects": effects,
        "erasure_fraction": erasure,
        "restoration_recovery_fraction": recovery,
        "route_jsd_normalized": route_jsd,
        "route_case_count": route_case_count,
        "route_divergence_cases": route_divergence_cases,
        "retention_loss": retention_loss,
        "negative_transfer_rate": negative_transfer_rate,
        "seed_direction": seed_direction,
        "scientific_judgment_emitted": False,
    }


__all__ = [
    "CONTEXT_VECTOR",
    "EMBEDDING_ONLY",
    "EVALUATION_SCHEMA_VERSION",
    "FROZEN",
    "HYPERGRAPH_ONLY",
    "METRIC_SCHEMA_VERSION",
    "NO_SHARED",
    "PARITY_FIELDS",
    "REQUIRED_ARMS",
    "SemanticWeightMetricError",
    "SemanticWeightObservationV1",
    "W_FULL",
    "W_RANDOM",
    "W_REMOVED",
    "W_RESTORED",
    "W_SHUFFLED",
    "W_UNIFORM",
    "evaluate_observations",
    "observation_from_mapping",
    "validate_observation_suite",
]
