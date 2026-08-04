#!/usr/bin/env python3
"""F1 r8 power v2 — selective-utility development power operating characteristics.

The v1 development power receipt (``prom9_f1_r8_power.build_power_receipt``)
scores arms by binary coverage and asks whether the frozen 40-of-48
component-cluster design resolves a 0.05 minimum paired contrast.  Metric v2
(``prom9_f1_metric_v2``) replaces binary coverage with the selective utility
``U = 1·correct − c·wrong`` (abstain = 0), which is blind neither to
abstention nor to fabrication.  This module builds the v2 development power
receipt: the same component partition, the same simulation STRUCTURE (60
trials, master seed 20260728, complete-seed-block selection of 40 clusters,
the same nine scenarios, the same paired cluster percentile bootstrap with
10000 reps at seed 20260724), but scored on the exact utility contrasts.

Everything is deterministic and stdlib-only.  Contrast identity is never
silently accepted: the analysis input is derived exclusively from
``prom9_f1_metric_v2.verify_development_identity`` (suite self-hash, manifest
hash binding, five-arm coverage, gold identity, source-derived component
partition), plus the block metadata the simulator needs (twelve equal seed
blocks of four components, integer seed/carryover blocks, the same component
identity/partition discipline the v1 builder enforces).  Any drift raises
:class:`PowerV2Refusal` (or :class:`MetricV2Refusal` from the identity
layer).

Receipt schema ``hswm-prom9-f1-r8-power-operating-characteristic/v2-utility``:

    schema_version                the v2-utility receipt schema string
    analysis_input                object with keys
                                  {schema_version:
                                   "hswm-prom9-f1-r8-power-v2-development-data/v1",
                                   development_components,
                                   simulation_plan,
                                   utility_metric}
      development_components      48 rows {component_id, item_ids,
                                  source_entity_ids, cluster_size, seed_block,
                                  carryover_block, contrasts}; contrasts maps
                                  each of the 4 control arms to the EXACT
                                  paired typed−control utility contrast as a
                                  Fraction string ("p/q", integers as "p")
      simulation_plan             {schema_version:
                                   "hswm-prom9-f1-r8-power-v2-simulator-spec/v1",
                                   trials: 60, master_seed: 20260728,
                                   selected_cluster_count: 40,
                                   selection_method:
                                   "complete_seed_block_without_replacement/v1",
                                   mde: 0.05, target_power: 0.80,
                                   scenarios: [null, effect_0_03, mde,
                                   effect_0_08, coverage, unequal_cluster,
                                   heavy_tail, seed_interaction, carryover]}
      utility_metric              {name, cost_c, per_arm_utility,
                                  paired_contrasts, min_contrast,
                                  coverage_v1_contrasts}; every metric value
                                  an exact Fraction string, coverage_v1 the
                                  blind binary-coverage baseline on the same
                                  partition
    development_evidence          {schema_version:
                                   "hswm-prom9-f1-r8-power-v2-development-evidence/v1",
                                   run_id, suite, gold, manifest, selection,
                                   artifact_receipts:
                                   {suite_receipt_sha256, manifest_sha256,
                                   gold_sha256, selection_receipt_sha256,
                                   selection_sha256}}
    development_evidence_sha256   canonical_sha256(development_evidence)
    development_data_sha256       canonical_sha256(development_components)
    simulator_sha256              SHA-256 of this module's file bytes
    metric                        "utility_c2_min_paired_component_cluster_bootstrap_lcb"
                                  (frozen receipt field)
    utility_cost_c                2 (frozen receipt field)
    inference_unit                "component_cluster_macro"
    selected_method               "paired_cluster_percentile_bootstrap_v1"
    minimum_clusters              40
    operating_characteristics     the v1 key set: trial_count,
                                  selected_cluster_count, mde, target_power,
                                  observed_power_at_mde,
                                  observed_power_lower_95,
                                  null_false_support_rate,
                                  null_false_support_upper_95,
                                  interval_coverage,
                                  interval_coverage_lower_95,
                                  expected_interval_width,
                                  effect_0_03_support_rate,
                                  effect_0_08_support_rate, and for each
                                  sensitivity scenario the triple
                                  (support_rate, support_lower_95,
                                  sensitivity_pass)
    receipt_sha256                canonical_sha256 over every field above

Verification (:func:`verify_power_v2_operating_characteristics`) re-derives
the components from the embedded evidence through the metric-v2 identity
layer, replays the simulation exactly, and enforces the v2 development gates:

* the null scenario false-support rate is exactly 0 (the utility metric must
  never support under the null),
* interval coverage of the true minimum effect is at least 0.95,
* every Wilson lower/upper bound is coherent and inside [0, 1],
* mde 0.05 and target power 0.80 are frozen design constants.

Unlike the v1 publication gate (``prom9_f1_r8_power_cli``), this is a
DEVELOPMENT receipt: observed power at mde, the effect support rates, the
expected interval width, and the four sensitivity outcomes are REPORTED, not
gated.  The point of the v2 analysis is to measure how the selective-utility
metric's operating characteristics differ from the coverage metric's before
any confirmatory design is frozen.  (On the t2 development cohort the utility
contrasts have per-component sd ≈ 0.7, so a 0.05 mde is not resolvable at 40
clusters; the receipt says so rather than smoothing it over.)

CLI::

    python -m prom_search_hswm.prom9_f1_r8_power_v2 \
        --suite SUITE --gold GOLD --selection SELECTION \
        [--manifest MANIFEST] --output OUTPUT

The manifest defaults to ``manifest.v3.json`` next to the suite.  The output
is first-write-wins 0600 (``write_private_once`` when the prior-exposure
stack is importable, else an identical vendored atomic link).  Like the v1
CLI, stderr only ever says ``REFUSED``: suite and gold carry answers, and an
exception message could too.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import sys
from collections.abc import Mapping, Sequence
from fractions import Fraction

from prom_search_hswm.hswm_function_network import (
    FLAT_ARM,
    REMOVAL_ARM,
    SHUFFLE_ARM,
    TYPED_ARM,
    VECTOR_ARM,
)
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm import prom9_f1_metric_v2 as metric_v2
from prom_search_hswm.prom9_f1_metric_v2 import MetricV2Refusal

POWER_V2_RECEIPT_SCHEMA = (
    "hswm-prom9-f1-r8-power-operating-characteristic/v2-utility"
)
POWER_V2_DEVELOPMENT_SCHEMA = "hswm-prom9-f1-r8-power-v2-development-data/v1"
POWER_V2_EVIDENCE_SCHEMA = "hswm-prom9-f1-r8-power-v2-development-evidence/v1"
POWER_V2_SIMULATOR_SCHEMA = "hswm-prom9-f1-r8-power-v2-simulator-spec/v1"

UTILITY_METRIC = "utility_c2_min_paired_component_cluster_bootstrap_lcb"
UTILITY_COST_C = 2
SELECTION_SEED = 20260728
SELECTED_CLUSTERS = 40
TRIALS = 60
SEED_BLOCKS = 12
COMPONENTS_PER_BLOCK = 4
UTILITY_BOOTSTRAP = {
    "reps": 10000,
    "seed": 20260724,
    "lower_index": 249,
    "upper_index": 9749,
    "paired": True,
    "unit": "component_cluster_macro",
    "method": "paired_cluster_percentile_bootstrap_v1",
    "minimum_clusters": SELECTED_CLUSTERS,
    "metric": UTILITY_METRIC,
}
POWER_V2_SCENARIOS = (
    "null", "effect_0_03", "mde", "effect_0_08", "coverage",
    "unequal_cluster", "heavy_tail", "seed_interaction", "carryover",
)
SENSITIVITY_SCENARIOS = (
    "unequal_cluster",
    "heavy_tail",
    "seed_interaction",
    "carryover",
)
CONTROLS = (FLAT_ARM, VECTOR_ARM, REMOVAL_ARM, SHUFFLE_ARM)
ALL_ARMS = (TYPED_ARM, *CONTROLS)
OPERATING_CHARACTERISTIC_KEYS = frozenset(
    {
        "trial_count",
        "selected_cluster_count",
        "mde",
        "target_power",
        "observed_power_at_mde",
        "observed_power_lower_95",
        "null_false_support_rate",
        "null_false_support_upper_95",
        "interval_coverage",
        "interval_coverage_lower_95",
        "expected_interval_width",
        "effect_0_03_support_rate",
        "effect_0_08_support_rate",
        *(
            f"{scenario}_{suffix}"
            for scenario in SENSITIVITY_SCENARIOS
            for suffix in ("support_rate", "support_lower_95", "sensitivity_pass")
        ),
    }
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_POWER_V2_REPLAY_CACHE: dict[str, dict[str, object]] = {}
_BOOTSTRAP_COUNT_CACHE: dict[tuple[int, int, int], tuple[tuple[int, ...], ...]] = {}


class PowerV2Refusal(RuntimeError):
    """The v2 development evidence or power receipt is inadmissible."""


def _fraction(value: object, label: str) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise PowerV2Refusal(f"{label} is not an exact rational")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise PowerV2Refusal(f"{label} is not an exact rational") from error


def _contrast_float(component: Mapping[str, object], arm: str) -> float:
    contrasts = component.get("contrasts")
    if not isinstance(contrasts, Mapping) or set(contrasts) != set(CONTROLS):
        raise PowerV2Refusal("development utility contrasts drifted")
    return float(_fraction(contrasts[arm], "development utility contrast"))


def utility_development_components(
    evidence: metric_v2.DevelopmentEvidence, c: int = UTILITY_COST_C
) -> list[dict[str, object]]:
    """v2 analysis input: exact per-component paired utility contrasts.

    ``evidence`` is the fully cross-verified metric-v2 development cohort, so
    the component identity/partition discipline of the v1 builder (suite
    self-hash, manifest binding, five-arm coverage, gold identity,
    source-derived component ids, exact partition coverage) has already been
    enforced.  What remains is the block metadata the simulator needs and the
    metric-v2 contrast derivation itself; any drift refuses.
    """
    if not isinstance(c, int) or isinstance(c, bool) or c < 1:
        raise PowerV2Refusal("utility cost c must be a positive integer")
    per_component = metric_v2.per_component_contrasts(evidence, c)
    components: list[dict[str, object]] = []
    seed_blocks: dict[int, int] = {}
    for row in evidence.schedule:
        component_id = str(row.get("component_id"))
        seed_block = row.get("seed_block")
        carryover_block = row.get("carryover_block")
        cluster_size = row.get("cluster_size")
        item_ids = row.get("item_ids")
        source_entities = row.get("source_entity_ids")
        if (
            not isinstance(seed_block, int)
            or isinstance(seed_block, bool)
            or not isinstance(carryover_block, int)
            or isinstance(carryover_block, bool)
            or not isinstance(cluster_size, int)
            or isinstance(cluster_size, bool)
            or cluster_size < 1
            or not isinstance(item_ids, list)
            or len(item_ids) != cluster_size
            or not isinstance(source_entities, list)
            or not source_entities
        ):
            raise PowerV2Refusal("development component block metadata drifted")
        contrasts = per_component[component_id]
        if set(contrasts) != set(CONTROLS):
            raise PowerV2Refusal("development utility contrasts drifted")
        components.append(
            {
                "component_id": component_id,
                "item_ids": sorted(str(value) for value in item_ids),
                "source_entity_ids": sorted(str(value) for value in source_entities),
                "cluster_size": cluster_size,
                "seed_block": seed_block,
                "carryover_block": carryover_block,
                "contrasts": {
                    arm: str(contrasts[arm]) for arm in CONTROLS
                },
            }
        )
        seed_blocks[seed_block] = seed_blocks.get(seed_block, 0) + 1
    if (
        len(components) != metric_v2.DEVELOPMENT_COMPONENTS
        or len(seed_blocks) != SEED_BLOCKS
        or set(seed_blocks.values()) != {COMPONENTS_PER_BLOCK}
    ):
        raise PowerV2Refusal(
            "development components do not form twelve equal seed blocks"
        )
    return components


def _wilson_one_sided(successes: int, trials: int) -> tuple[float, float]:
    """One-sided 95% Wilson lower/upper bounds (identical to the v1 judge)."""

    if not 0 <= successes <= trials or trials < 1:
        raise PowerV2Refusal("invalid binomial operating-characteristic count")
    z = 1.6448536269514722
    rate = successes / float(trials)
    denominator = 1.0 + (z * z) / trials
    center = (rate + (z * z) / (2.0 * trials)) / denominator
    margin = (
        z
        * math.sqrt(
            (rate * (1.0 - rate) / trials)
            + (z * z) / (4.0 * trials * trials)
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _paired_bootstrap_intervals(
    differences: Mapping[str, Sequence[float]],
    *,
    reps: int,
    seed: int,
    lower_index: int,
    upper_index: int,
) -> dict[str, dict[str, float]]:
    """Paired cluster percentile bootstrap (v1 structure, utility scores)."""

    if set(differences) != set(CONTROLS):
        raise PowerV2Refusal("bootstrap contrasts drifted")
    lengths = {len(values) for values in differences.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) < 2:
        raise PowerV2Refusal(
            "bootstrap requires a common nontrivial component-cluster cut"
        )
    sample_size = next(iter(lengths))
    if not 0 <= lower_index < upper_index < reps:
        raise PowerV2Refusal("bootstrap interval indices drifted")
    cache_key = (sample_size, reps, seed)
    count_vectors = _BOOTSTRAP_COUNT_CACHE.get(cache_key)
    if count_vectors is None:
        generator = random.Random(seed)
        generated: list[tuple[int, ...]] = []
        for _ in range(reps):
            counts = [0] * sample_size
            for _ in range(sample_size):
                counts[generator.randrange(sample_size)] += 1
            generated.append(tuple(counts))
        count_vectors = tuple(generated)
        _BOOTSTRAP_COUNT_CACHE[cache_key] = count_vectors

    result: dict[str, dict[str, float]] = {}
    arms_by_vector: dict[tuple[float, ...], list[str]] = {}
    for arm in CONTROLS:
        vector = tuple(float(value) for value in differences[arm])
        arms_by_vector.setdefault(vector, []).append(arm)
    for vector, arms in arms_by_vector.items():
        if len(set(vector)) == 1:
            interval = {"lower": vector[0], "upper": vector[0]}
        else:
            samples = [
                sum(count * value for count, value in zip(counts, vector))
                / float(sample_size)
                for counts in count_vectors
            ]
            samples.sort()
            interval = {
                "lower": float(samples[lower_index]),
                "upper": float(samples[upper_index]),
            }
        for arm in arms:
            result[arm] = dict(interval)
    return result


def _primary_lcb_covers_min_effect(
    intervals: Mapping[str, Mapping[str, float]], *, true_min_effect: float
) -> bool:
    """Coverage for M=min marginal LCBs against D=min true effects (v1 rule)."""

    if set(intervals) != set(CONTROLS):
        raise PowerV2Refusal("primary LCB coverage contrasts drifted")
    lower_bounds: list[float] = []
    for arm in CONTROLS:
        interval = intervals[arm]
        if set(interval) != {"lower", "upper"}:
            raise PowerV2Refusal("primary LCB coverage interval shape drifted")
        lower = float(interval["lower"])
        upper = float(interval["upper"])
        if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
            raise PowerV2Refusal("primary LCB coverage interval drifted")
        lower_bounds.append(lower)
    if not math.isfinite(float(true_min_effect)):
        raise PowerV2Refusal("primary LCB true minimum effect drifted")
    return min(lower_bounds) <= float(true_min_effect)


def _recompute_utility_power_characteristics(
    components: Sequence[Mapping[str, object]],
    plan: Mapping[str, object],
    *,
    bootstrap: Mapping[str, object],
) -> dict[str, object]:
    """Replay the v1 simulator STRUCTURE on the utility contrast distribution.

    Trial selection (master-seed-derived per-scenario/trial seeds, complete
    seed blocks without replacement), residual centering, scenario effect
    injection and residual transforms, paired bootstrap intervals, the
    min-of-four-LCB support rule, the min-effect coverage rule, and the
    one-sided Wilson bounds are all identical to the v1 judge; only the
    scoring metric (selective utility instead of binary coverage) differs.
    Memoization changes only runtime, never the receipt.
    """

    replay_key = canonical_sha256(
        {
            "components": list(components),
            "plan": dict(plan),
            "bootstrap": dict(bootstrap),
        }
    )
    cached_replay = _POWER_V2_REPLAY_CACHE.get(replay_key)
    if cached_replay is not None:
        return dict(cached_replay)
    if list(plan.get("scenarios", [])) != list(POWER_V2_SCENARIOS):
        raise PowerV2Refusal("power v2 simulation scenarios drifted")
    selected_count = int(plan["selected_cluster_count"])
    trial_count = int(plan["trials"])
    master_seed = int(plan["master_seed"])
    mde = float(plan["mde"])
    target_power = float(plan["target_power"])
    means = {
        arm: sum(_contrast_float(component, arm) for component in components)
        / float(len(components))
        for arm in CONTROLS
    }
    mean_cluster_size = sum(
        int(component["cluster_size"]) for component in components
    ) / float(len(components))
    mean_seed_block = sum(
        int(component["seed_block"]) for component in components
    ) / float(len(components))
    mean_carryover_block = sum(
        int(component["carryover_block"]) for component in components
    ) / float(len(components))
    effects = {
        "null": 0.0,
        "effect_0_03": 0.03,
        "mde": mde,
        "effect_0_08": 0.08,
        "coverage": mde,
        "unequal_cluster": mde,
        "heavy_tail": mde,
        "seed_interaction": mde,
        "carryover": mde,
    }
    seed_blocks: dict[int, list[Mapping[str, object]]] = {}
    for component in components:
        seed_blocks.setdefault(int(component["seed_block"]), []).append(component)
    block_sizes = {len(block) for block in seed_blocks.values()}
    if (
        plan.get("selection_method")
        != "complete_seed_block_without_replacement/v1"
        or len(block_sizes) != 1
    ):
        raise PowerV2Refusal("power simulation requires equal complete seed blocks")
    block_size = next(iter(block_sizes))
    if selected_count % block_size or selected_count > len(components):
        raise PowerV2Refusal(
            "power selected cluster count cannot form complete seed blocks"
        )
    selected_block_count = selected_count // block_size
    if selected_block_count > len(seed_blocks):
        raise PowerV2Refusal("power development data has too few complete seed blocks")
    trials: dict[str, list[dict[str, object]]] = {
        scenario: [] for scenario in POWER_V2_SCENARIOS
    }
    interval_cache: dict[str, dict[str, dict[str, float]]] = {}
    for scenario in POWER_V2_SCENARIOS:
        for trial_index in range(trial_count):
            selection_seed = int(
                canonical_sha256(
                    {
                        "master_seed": master_seed,
                        "scenario": scenario,
                        "trial_index": trial_index,
                        "stage": "development-component-selection",
                    }
                )[:16],
                16,
            )
            selection_rng = random.Random(selection_seed)
            chosen_blocks = selection_rng.sample(
                sorted(seed_blocks), selected_block_count
            )
            sampled = sorted(
                (
                    component
                    for block_id in chosen_blocks
                    for component in seed_blocks[block_id]
                ),
                key=lambda component: str(component["component_id"]),
            )
            differences: dict[str, list[float]] = {arm: [] for arm in CONTROLS}
            for component in sampled:
                for arm in CONTROLS:
                    residual = _contrast_float(component, arm) - means[arm]
                    if scenario == "unequal_cluster":
                        residual *= math.sqrt(
                            mean_cluster_size / float(component["cluster_size"])
                        )
                    elif scenario == "heavy_tail":
                        residual *= 3.0
                    elif scenario == "seed_interaction":
                        residual += (float(component["seed_block"]) - mean_seed_block) * 0.002
                    elif scenario == "carryover":
                        residual += (
                            float(component["carryover_block"]) - mean_carryover_block
                        ) * 0.002
                    differences[arm].append(effects[scenario] + residual)
            interval_key = canonical_json(differences)
            intervals = interval_cache.get(interval_key)
            if intervals is None:
                intervals = _paired_bootstrap_intervals(
                    differences,
                    reps=int(bootstrap["reps"]),
                    seed=int(bootstrap["seed"]),
                    lower_index=int(bootstrap["lower_index"]),
                    upper_index=int(bootstrap["upper_index"]),
                )
                interval_cache[interval_key] = intervals
            support = min(interval["lower"] for interval in intervals.values()) > 0.0
            # The registered scalar is the minimum of four marginal lower
            # bounds; its coverage event is M <= D_true (see the v1 judge).
            covered = _primary_lcb_covers_min_effect(
                intervals, true_min_effect=effects[scenario]
            )
            width = sum(
                interval["upper"] - interval["lower"] for interval in intervals.values()
            ) / float(len(CONTROLS))
            trials[scenario].append(
                {
                    "support": support,
                    "covered": covered,
                    "interval_width": width,
                }
            )

    def count(scenario: str, field: str) -> int:
        return sum(bool(row[field]) for row in trials[scenario])

    def rate(scenario: str, field: str) -> float:
        return count(scenario, field) / float(trial_count)

    def mean_width(scenario: str) -> float:
        return sum(float(row["interval_width"]) for row in trials[scenario]) / float(
            trial_count
        )

    power_successes = count("mde", "support")
    null_successes = count("null", "support")
    coverage_successes = count("coverage", "covered")
    power_lower, _ = _wilson_one_sided(power_successes, trial_count)
    _, null_upper = _wilson_one_sided(null_successes, trial_count)
    coverage_lower, _ = _wilson_one_sided(coverage_successes, trial_count)
    result: dict[str, object] = {
        "trial_count": trial_count,
        "selected_cluster_count": selected_count,
        "mde": mde,
        "target_power": target_power,
        "observed_power_at_mde": rate("mde", "support"),
        "observed_power_lower_95": power_lower,
        "null_false_support_rate": rate("null", "support"),
        "null_false_support_upper_95": null_upper,
        "interval_coverage": rate("coverage", "covered"),
        "interval_coverage_lower_95": coverage_lower,
        "expected_interval_width": mean_width("coverage"),
        "effect_0_03_support_rate": rate("effect_0_03", "support"),
        "effect_0_08_support_rate": rate("effect_0_08", "support"),
    }
    for scenario in SENSITIVITY_SCENARIOS:
        successes = count(scenario, "support")
        lower, _ = _wilson_one_sided(successes, trial_count)
        result[f"{scenario}_support_rate"] = successes / float(trial_count)
        result[f"{scenario}_support_lower_95"] = lower
        result[f"{scenario}_sensitivity_pass"] = lower >= target_power
    _POWER_V2_REPLAY_CACHE[replay_key] = dict(result)
    return result


def _selection_self_hash(selection: Mapping[str, object]) -> str:
    unsigned = dict(selection)
    declared = unsigned.pop("selection_receipt_sha256", None)
    if not isinstance(declared, str) or _SHA256.fullmatch(declared) is None:
        raise PowerV2Refusal("cohort selection self-hash is absent or malformed")
    if canonical_sha256(unsigned) != declared:
        raise PowerV2Refusal("cohort selection self-hash drifted")
    return declared


def _simulator_sha256() -> str:
    return hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()


def _utility_metric_summary(
    evidence: metric_v2.DevelopmentEvidence,
) -> dict[str, object]:
    paired = metric_v2.paired_contrasts(evidence, UTILITY_COST_C)
    return {
        "name": UTILITY_METRIC,
        "cost_c": UTILITY_COST_C,
        "per_arm_utility": {
            arm: str(value)
            for arm, value in metric_v2.per_arm_utility(
                evidence, UTILITY_COST_C
            ).items()
        },
        "paired_contrasts": {arm: str(value) for arm, value in paired.items()},
        "min_contrast": str(min(paired.values())),
        "coverage_v1_contrasts": {
            arm: str(value)
            for arm, value in metric_v2.coverage_v1_contrasts(evidence).items()
        },
    }


def build_power_v2_receipt(
    *,
    suite: Mapping[str, object],
    gold: Mapping[str, object],
    manifest: Mapping[str, object],
    selection: Mapping[str, object],
) -> dict[str, object]:
    """Build the v2 (selective-utility) development power receipt.

    The four artifacts are cross-verified through the metric-v2 identity
    layer before any contrast is computed; the simulation is then replayed
    deterministically from the exact per-component utility contrasts.
    """

    evidence = metric_v2.verify_development_identity(
        suite=suite, gold=gold, manifest=manifest, selection=selection
    )
    selection_sha = _selection_self_hash(selection)
    components = utility_development_components(evidence, UTILITY_COST_C)
    plan = {
        "schema_version": POWER_V2_SIMULATOR_SCHEMA,
        "trials": TRIALS,
        "master_seed": SELECTION_SEED,
        "selected_cluster_count": SELECTED_CLUSTERS,
        "selection_method": "complete_seed_block_without_replacement/v1",
        "mde": 0.05,
        "target_power": 0.80,
        "scenarios": list(POWER_V2_SCENARIOS),
    }
    analysis = {
        "schema_version": POWER_V2_DEVELOPMENT_SCHEMA,
        "development_components": components,
        "simulation_plan": plan,
        "utility_metric": _utility_metric_summary(evidence),
    }
    evidence_block = {
        "schema_version": POWER_V2_EVIDENCE_SCHEMA,
        "run_id": evidence.run_id,
        "suite": dict(suite),
        "gold": dict(gold),
        "manifest": dict(manifest),
        "selection": dict(selection),
        "artifact_receipts": {
            "suite_receipt_sha256": evidence.suite_sha256,
            "manifest_sha256": evidence.manifest_sha256,
            "gold_sha256": evidence.gold_sha256,
            "selection_receipt_sha256": selection_sha,
            "selection_sha256": canonical_sha256(selection),
        },
    }
    characteristics = _recompute_utility_power_characteristics(
        components, plan, bootstrap=UTILITY_BOOTSTRAP
    )
    unsigned = {
        "schema_version": POWER_V2_RECEIPT_SCHEMA,
        "analysis_input": analysis,
        "development_evidence": evidence_block,
        "development_evidence_sha256": canonical_sha256(evidence_block),
        "development_data_sha256": canonical_sha256(components),
        "simulator_sha256": _simulator_sha256(),
        "metric": UTILITY_METRIC,
        "utility_cost_c": UTILITY_COST_C,
        "inference_unit": "component_cluster_macro",
        "selected_method": "paired_cluster_percentile_bootstrap_v1",
        "minimum_clusters": SELECTED_CLUSTERS,
        "operating_characteristics": characteristics,
    }
    return {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise PowerV2Refusal(f"{label} is absent or malformed")
    return value


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PowerV2Refusal(f"{label} is not an exact SHA-256 digest")
    return value


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PowerV2Refusal(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise PowerV2Refusal(f"{label} is not finite")
    return result


def _exact_integer(value: object, expected: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value != expected:
        raise PowerV2Refusal(f"{label} drifted from the frozen design")
    return value


def verify_power_v2_operating_characteristics(
    receipt: Mapping[str, object],
) -> str:
    """Replay and gate a v2 development power receipt before publication.

    Every numeric claim is recomputed from the embedded evidence; the
    simulation is replayed exactly; the only scientific gates are the v2
    development invariants (null false-support exactly 0, interval coverage
    at least 0.95).  Returns the declared receipt_sha256 on success.
    """

    expected_receipt_keys = {
        "schema_version",
        "analysis_input",
        "development_evidence",
        "development_evidence_sha256",
        "development_data_sha256",
        "simulator_sha256",
        "metric",
        "utility_cost_c",
        "inference_unit",
        "selected_method",
        "minimum_clusters",
        "operating_characteristics",
        "receipt_sha256",
    }
    if set(receipt) != expected_receipt_keys:
        raise PowerV2Refusal("power v2 receipt shape drifted")
    if receipt.get("schema_version") != POWER_V2_RECEIPT_SCHEMA:
        raise PowerV2Refusal("power v2 receipt schema drifted")
    unsigned = dict(receipt)
    declared = _sha256(unsigned.pop("receipt_sha256", None), "power v2 receipt")
    if canonical_sha256(unsigned) != declared:
        raise PowerV2Refusal("power v2 receipt self-hash drifted")
    for field in (
        "development_evidence_sha256",
        "development_data_sha256",
        "simulator_sha256",
    ):
        _sha256(receipt.get(field), f"power v2 receipt {field}")
    if receipt.get("simulator_sha256") != _simulator_sha256():
        raise PowerV2Refusal("power v2 receipt targets a different simulator")
    if (
        receipt.get("metric") != UTILITY_METRIC
        or receipt.get("utility_cost_c") != UTILITY_COST_C
    ):
        raise PowerV2Refusal("power v2 metric identity drifted")
    if (
        receipt.get("inference_unit") != "component_cluster_macro"
        or receipt.get("selected_method")
        != "paired_cluster_percentile_bootstrap_v1"
    ):
        raise PowerV2Refusal("power v2 reducer contract drifted")
    _exact_integer(receipt.get("minimum_clusters"), SELECTED_CLUSTERS, "minimum clusters")

    evidence_block = _mapping(
        receipt.get("development_evidence"), "development evidence"
    )
    expected_evidence_keys = {
        "schema_version",
        "run_id",
        "suite",
        "gold",
        "manifest",
        "selection",
        "artifact_receipts",
    }
    if (
        set(evidence_block) != expected_evidence_keys
        or evidence_block.get("schema_version") != POWER_V2_EVIDENCE_SCHEMA
        or canonical_sha256(evidence_block)
        != receipt.get("development_evidence_sha256")
    ):
        raise PowerV2Refusal("development v2 evidence self-hash drifted")
    suite = _mapping(evidence_block.get("suite"), "development suite")
    gold = _mapping(evidence_block.get("gold"), "development gold")
    manifest = _mapping(evidence_block.get("manifest"), "development manifest")
    selection = _mapping(evidence_block.get("selection"), "cohort selection")
    try:
        rederived_evidence = metric_v2.verify_development_identity(
            suite=suite, gold=gold, manifest=manifest, selection=selection
        )
        selection_sha = _selection_self_hash(selection)
    except (MetricV2Refusal, PowerV2Refusal) as error:
        raise PowerV2Refusal(
            "development v2 evidence failed exact re-verification"
        ) from error
    artifacts = _mapping(
        evidence_block.get("artifact_receipts"), "artifact receipts"
    )
    if set(artifacts) != {
        "suite_receipt_sha256",
        "manifest_sha256",
        "gold_sha256",
        "selection_receipt_sha256",
        "selection_sha256",
    }:
        raise PowerV2Refusal("artifact receipt inventory drifted")
    if (
        evidence_block.get("run_id") != rederived_evidence.run_id
        or artifacts.get("suite_receipt_sha256") != rederived_evidence.suite_sha256
        or artifacts.get("manifest_sha256") != rederived_evidence.manifest_sha256
        or artifacts.get("gold_sha256") != rederived_evidence.gold_sha256
        or artifacts.get("selection_receipt_sha256") != selection_sha
        or artifacts.get("selection_sha256") != canonical_sha256(selection)
    ):
        raise PowerV2Refusal("development v2 artifact binding drifted")

    analysis = _mapping(receipt.get("analysis_input"), "power v2 analysis input")
    if set(analysis) != {
        "schema_version",
        "development_components",
        "simulation_plan",
        "utility_metric",
    } or analysis.get("schema_version") != POWER_V2_DEVELOPMENT_SCHEMA:
        raise PowerV2Refusal("power v2 analysis-input contract drifted")
    components = analysis.get("development_components")
    if not isinstance(components, list) or len(components) != (
        metric_v2.DEVELOPMENT_COMPONENTS
    ):
        raise PowerV2Refusal("power v2 development-component count drifted")
    if canonical_sha256(components) != receipt.get("development_data_sha256"):
        raise PowerV2Refusal("power v2 development-data preimage drifted")
    rederived_components = utility_development_components(
        rederived_evidence, UTILITY_COST_C
    )
    if canonical_json(components) != canonical_json(rederived_components):
        raise PowerV2Refusal(
            "development v2 components were not rederived from evidence"
        )
    summary = _mapping(analysis.get("utility_metric"), "utility metric summary")
    if summary != _utility_metric_summary(rederived_evidence):
        raise PowerV2Refusal("utility metric summary was not rederived")

    plan = _mapping(analysis.get("simulation_plan"), "power v2 simulation plan")
    if set(plan) != {
        "schema_version",
        "trials",
        "master_seed",
        "selected_cluster_count",
        "selection_method",
        "mde",
        "target_power",
        "scenarios",
    }:
        raise PowerV2Refusal("power v2 simulation-plan shape drifted")
    if (
        plan.get("schema_version") != POWER_V2_SIMULATOR_SCHEMA
        or plan.get("master_seed") != SELECTION_SEED
        or plan.get("selection_method")
        != "complete_seed_block_without_replacement/v1"
        or plan.get("scenarios") != list(POWER_V2_SCENARIOS)
    ):
        raise PowerV2Refusal("power v2 simulation-plan contract drifted")
    _exact_integer(plan.get("trials"), TRIALS, "power v2 simulation trial count")
    _exact_integer(
        plan.get("selected_cluster_count"),
        SELECTED_CLUSTERS,
        "power v2 selected cluster count",
    )
    if _finite(plan.get("mde"), "power v2 MDE") != 0.05 or _finite(
        plan.get("target_power"), "power v2 target power"
    ) != 0.80:
        raise PowerV2Refusal("power v2 MDE or target drifted from the frozen design")

    raw_characteristics = _mapping(
        receipt.get("operating_characteristics"),
        "power v2 operating characteristics",
    )
    if set(raw_characteristics) != OPERATING_CHARACTERISTIC_KEYS:
        raise PowerV2Refusal("power v2 operating-characteristic shape drifted")
    _exact_integer(
        raw_characteristics.get("trial_count"), TRIALS, "observed trial count"
    )
    _exact_integer(
        raw_characteristics.get("selected_cluster_count"),
        SELECTED_CLUSTERS,
        "observed selected cluster count",
    )
    recomputed = _recompute_utility_power_characteristics(
        components,
        plan,
        bootstrap=UTILITY_BOOTSTRAP,
    )
    if dict(raw_characteristics) != dict(recomputed):
        raise PowerV2Refusal(
            "power v2 operating characteristics were not replayed"
        )
    numeric: dict[str, float] = {}
    for key, raw in raw_characteristics.items():
        if key in {"trial_count", "selected_cluster_count"} or key.endswith(
            "_sensitivity_pass"
        ):
            continue
        numeric[key] = _finite(raw, f"operating characteristic {key}")
    for key, value in numeric.items():
        if (
            key.endswith("_rate")
            or key.endswith("_lower_95")
            or key.endswith("_upper_95")
            or key in {"observed_power_at_mde", "interval_coverage", "target_power"}
        ) and not 0.0 <= value <= 1.0:
            raise PowerV2Refusal(f"operating characteristic {key} is outside [0,1]")
    if _finite(
        raw_characteristics.get("expected_interval_width"),
        "expected interval width",
    ) < 0.0:
        raise PowerV2Refusal("expected interval width is negative")

    if numeric["mde"] != 0.05 or numeric["target_power"] != 0.80:
        raise PowerV2Refusal("reported power v2 MDE or target drifted")
    # One-sided Wilson bounds at 0/60 or 60/60 successes can land float dust
    # (≈1e-18) outside the estimate; the v1 publication gate never observed
    # this because its frozen thresholds required nonzero power.  Bound
    # coherence is therefore checked at a 1e-12 tolerance — far below any
    # scientifically meaningful discrepancy.
    _BOUND_TOLERANCE = 1e-12
    if (
        numeric["observed_power_lower_95"]
        > numeric["observed_power_at_mde"] + _BOUND_TOLERANCE
    ):
        raise PowerV2Refusal("power lower confidence bound exceeds its estimate")
    if (
        numeric["null_false_support_rate"]
        > numeric["null_false_support_upper_95"] + _BOUND_TOLERANCE
    ):
        raise PowerV2Refusal("null upper confidence bound is incoherent")
    if (
        numeric["interval_coverage_lower_95"]
        > numeric["interval_coverage"] + _BOUND_TOLERANCE
    ):
        raise PowerV2Refusal("coverage lower confidence bound exceeds its estimate")
    target = numeric["target_power"]
    for scenario in SENSITIVITY_SCENARIOS:
        rate = numeric[f"{scenario}_support_rate"]
        lower = numeric[f"{scenario}_support_lower_95"]
        if lower > rate + _BOUND_TOLERANCE:
            raise PowerV2Refusal(
                f"{scenario} sensitivity confidence bound is incoherent"
            )
        if raw_characteristics.get(f"{scenario}_sensitivity_pass") is not (
            lower >= target
        ):
            raise PowerV2Refusal(f"{scenario} sensitivity verdict drifted")

    # v2 development gates: the metric must never support under the null and
    # the interval must cover the true minimum effect.  Power at mde, effect
    # support rates, width, and the sensitivity outcomes are development
    # measurements and are reported, not gated.
    if numeric["null_false_support_rate"] != 0.0:
        raise PowerV2Refusal("utility metric falsely supports under the null")
    if numeric["interval_coverage"] < 0.95:
        raise PowerV2Refusal("utility interval coverage is below 0.95")
    return declared


def _write_output_once(path: Path, value: Mapping[str, object]) -> None:
    """First-write-wins 0600 publication (write_private_once pattern)."""

    try:
        from prom_search_hswm.prom9_f1_prior_exposure import write_private_once
    except Exception:  # stdlib-only host: use the identical vendored pattern
        write_private_once = None
    if write_private_once is not None:
        write_private_once(Path(path), value)
        return
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    temporary = destination.with_name(f".{destination.name}.partial-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as error:
            raise PowerV2Refusal(
                "refusing to replace an existing power v2 receipt"
            ) from error
        directory = os.open(str(destination.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="development manifest (default: manifest.v3.json next to the suite)",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest_path = (
            args.manifest
            if args.manifest is not None
            else args.suite.with_name("manifest.v3.json")
        )
        suite = metric_v2.load_suite(args.suite)
        gold = metric_v2.load_gold(args.gold)
        manifest = metric_v2.load_manifest(manifest_path)
        selection = metric_v2.load_selection(args.selection)
        receipt = build_power_v2_receipt(
            suite=suite, gold=gold, manifest=manifest, selection=selection
        )
        verify_power_v2_operating_characteristics(receipt)
        _write_output_once(args.output, receipt)
    except Exception:
        # Never echo an exception: it could include answer-bearing preimages.
        print(json.dumps({"status": "REFUSED"}), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "TERMINAL_DEVELOPMENT_POWER_V2_RECEIPT",
                "receipt_sha256": receipt["receipt_sha256"],
                "development_components": len(
                    receipt["analysis_input"]["development_components"]
                ),
                "metric": receipt["metric"],
                "utility_cost_c": receipt["utility_cost_c"],
                "minimum_clusters": receipt["minimum_clusters"],
                "operating_characteristics": receipt["operating_characteristics"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CONTROLS",
    "OPERATING_CHARACTERISTIC_KEYS",
    "POWER_V2_DEVELOPMENT_SCHEMA",
    "POWER_V2_EVIDENCE_SCHEMA",
    "POWER_V2_RECEIPT_SCHEMA",
    "POWER_V2_SCENARIOS",
    "POWER_V2_SIMULATOR_SCHEMA",
    "SELECTED_CLUSTERS",
    "SELECTION_SEED",
    "SENSITIVITY_SCENARIOS",
    "TRIALS",
    "UTILITY_BOOTSTRAP",
    "UTILITY_COST_C",
    "UTILITY_METRIC",
    "MetricV2Refusal",
    "PowerV2Refusal",
    "build_power_v2_receipt",
    "main",
    "utility_development_components",
    "verify_power_v2_operating_characteristics",
]
