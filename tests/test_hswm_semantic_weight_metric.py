from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from hswm_semantic_weight_metric import (
    CONTEXT_VECTOR,
    FROZEN,
    METRIC_SCHEMA_VERSION,
    REQUIRED_ARMS,
    SemanticWeightMetricError,
    W_FULL,
    W_RANDOM,
    W_REMOVED,
    W_RESTORED,
    W_SHUFFLED,
    W_UNIFORM,
    evaluate_observations,
    observation_from_mapping,
    validate_observation_suite,
)
from hswm_scalar_w_causal_judge import judge_metrics
from hswm_w_ablation import (
    WAblationError,
    build_w_ablation_bundle,
    verify_w_ablation_bundle,
)
from hswm_weight_snapshot import (
    SlowWeightV1,
    WeightDeltaV1,
    apply_candidate,
    canonical_sha256,
    make_initial_snapshot,
    make_weight_candidate,
)
from scripts.validate_hswm_semantic_weight_metric_contract import (
    CONTRACT_PATH,
    PREREG_PATH,
    MetricContractValidationError,
    validate_contract,
    validate_preregistration,
    validate_with_injected_negative,
)


ROOT = Path(__file__).resolve().parents[1]


def digest(label: str) -> str:
    return canonical_sha256(label)


def snapshot_pair():
    base = make_initial_snapshot(
        (
            SlowWeightV1("edge:a", -1.0),
            SlowWeightV1("edge:b", -1.2),
            SlowWeightV1("edge:c", -1.4),
            SlowWeightV1("edge:d", -1.6),
        ),
        topology_sha256=digest("topology"),
        provenance_root_sha256=digest("base-provenance"),
    )
    after = {"edge:a": -0.8, "edge:b": -1.3, "edge:c": -1.3, "edge:d": -1.8}
    candidate = make_weight_candidate(
        base,
        (
            WeightDeltaV1(
                edge_id=edge_id,
                before_log_salience=base.weight_map()[edge_id],
                after_log_salience=value,
                eligibility_tag_sha256=digest(f"eligibility:{edge_id}"),
            )
            for edge_id, value in after.items()
        ),
        learning_policy_sha256=digest("policy"),
        provenance_root_sha256=digest("candidate-provenance"),
    )
    return base, apply_candidate(base, candidate)


def test_w_ablation_preserves_delta_multiset_and_restores_exactly() -> None:
    base, full = snapshot_pair()
    bundle = build_w_ablation_bundle(
        base,
        full,
        strata_by_edge={edge_id: "same-type-role-degree" for edge_id in base.weight_map()},
        seed=7,
    )
    verify_w_ablation_bundle(bundle)
    assert bundle.removed is base
    assert bundle.restored is full
    assert bundle.shuffled.snapshot_id not in {base.snapshot_id, full.snapshot_id}
    full_deltas = sorted(
        full.weight_map()[edge_id] - base.weight_map()[edge_id]
        for edge_id in base.weight_map()
    )
    shuffled_deltas = sorted(
        bundle.shuffled.weight_map()[edge_id] - base.weight_map()[edge_id]
        for edge_id in base.weight_map()
    )
    assert shuffled_deltas == pytest.approx(full_deltas)


def test_w_ablation_rejects_single_changed_edge_stratum() -> None:
    base, full = snapshot_pair()
    strata = {edge_id: "shared" for edge_id in base.weight_map()}
    strata["edge:a"] = "singleton"
    with pytest.raises(WAblationError, match="at least two edges"):
        build_w_ablation_bundle(base, full, strata_by_edge=strata, seed=1)


UTILITY = {
    "NO_SHARED_STATE": 0.40,
    "EMBEDDING_ONLY": 0.45,
    "HYPERGRAPH_ONLY": 0.46,
    FROZEN: 0.50,
    CONTEXT_VECTOR: 0.60,
    W_UNIFORM: 0.52,
    W_RANDOM: 0.48,
    W_FULL: 0.90,
    W_REMOVED: 0.50,
    W_SHUFFLED: 0.55,
    W_RESTORED: 0.90,
}


ROUTES = {
    "base": {"edge:a": 0.5, "edge:b": 0.5},
    "full": {"edge:a": 0.8, "edge:b": 0.2},
    "shuffle": {"edge:a": 0.4, "edge:b": 0.6},
    "uniform": {"edge:a": 0.55, "edge:b": 0.45},
    "random": {"edge:a": 0.45, "edge:b": 0.55},
}


def arm_snapshot(arm: str) -> str:
    if arm in {W_FULL, W_RESTORED}:
        return digest("snapshot:full")
    if arm == W_SHUFFLED:
        return digest("snapshot:shuffle")
    if arm == W_UNIFORM:
        return digest("snapshot:uniform")
    if arm == W_RANDOM:
        return digest("snapshot:random")
    return digest("snapshot:base")


def arm_route(arm: str) -> dict[str, float]:
    if arm in {W_FULL, W_RESTORED}:
        return ROUTES["full"]
    if arm == W_SHUFFLED:
        return ROUTES["shuffle"]
    if arm == W_UNIFORM:
        return ROUTES["uniform"]
    if arm == W_RANDOM:
        return ROUTES["random"]
    return ROUTES["base"]


def observation_mapping(
    *,
    item_id: str,
    cluster_id: str,
    cohort: str,
    seed: int,
    sequence_id: str,
    arm: str,
    position: int,
) -> dict[str, object]:
    route = arm_route(arm)
    utility = UTILITY[arm]
    if cohort == "retention":
        utility = 0.80 if arm in {W_FULL, W_RESTORED} else 0.81
    return {
        "schema_version": METRIC_SCHEMA_VERSION,
        "experiment_id": "fixture-scalar-w",
        "item_id": item_id,
        "cluster_id": cluster_id,
        "cohort": cohort,
        "seed": seed,
        "arm_id": arm,
        "sequence_id": sequence_id,
        "arm_order_position": position,
        "utility": utility,
        "model_sha256": digest("model"),
        "task_sha256": digest(f"task:{item_id}"),
        "topology_sha256": digest("topology"),
        "embedding_sha256": digest("embedding"),
        "relation_schema_sha256": digest("relations"),
        "candidate_universe_sha256": digest(f"candidates:{item_id}"),
        "raw_information_union_sha256": digest(f"raw-info:{item_id}"),
        "compute_envelope_sha256": digest("compute-envelope"),
        "treatment_payload_sha256": digest(f"payload:{arm}"),
        "weight_snapshot_sha256": arm_snapshot(arm),
        "pre_llm_logits_sha256": digest(
            "logits:full" if arm in {W_FULL, W_RESTORED} else f"logits:{arm}"
        ),
        "pre_llm_rank_sha256": digest(
            "rank:full" if arm in {W_FULL, W_RESTORED} else f"rank:{arm}"
        ),
        "route_digest": canonical_sha256(route),
        "physical_call_cap": 3,
        "logical_call_cap": 3,
        "input_token_cap": 4096,
        "output_token_cap": 512,
        "state_budget_bytes": 16384,
        "eligibility_seal_index": 1,
        "outcome_observe_index": 2,
        "answer_seal_index": 3,
        "gold_reveal_index": 4,
        "cache_hits": 0,
        "route_probabilities": route,
    }


def suite_mappings() -> list[dict[str, object]]:
    rows = []
    for cohort in ("fresh", "retention"):
        for cluster_index in range(2):
            item_id = f"{cohort}:item:{cluster_index}"
            sequence_id = (
                "FULL_REMOVE_SHUFFLE_RESTORE"
                if cluster_index == 0
                else "FULL_SHUFFLE_REMOVE_RESTORE"
            )
            positions = {arm: index for index, arm in enumerate(REQUIRED_ARMS)}
            if sequence_id == "FULL_SHUFFLE_REMOVE_RESTORE":
                positions[W_REMOVED], positions[W_SHUFFLED] = (
                    positions[W_SHUFFLED],
                    positions[W_REMOVED],
                )
            for seed in range(1, 6):
                for arm in REQUIRED_ARMS:
                    rows.append(
                        observation_mapping(
                            item_id=item_id,
                            cluster_id=f"{cohort}:cluster:{cluster_index}",
                            cohort=cohort,
                            seed=seed,
                            sequence_id=sequence_id,
                            arm=arm,
                            position=positions[arm],
                        )
                    )
    return rows


def test_metric_suite_validates_and_reduces_without_verdict() -> None:
    rows = [observation_from_mapping(row) for row in suite_mappings()]
    validated = validate_observation_suite(rows)
    result = evaluate_observations(
        validated,
        strongest_baseline_arm=CONTEXT_VECTOR,
        bootstrap_samples=1000,
        seed=11,
    )
    assert result["scientific_judgment_emitted"] is False
    assert result["effects"]["learned_gain"]["mean"] == pytest.approx(0.30)
    assert result["erasure_fraction"]["w_ablation_delta"] == pytest.approx(4 / 3)
    assert result["restoration_recovery_fraction"] == pytest.approx(1.0)
    assert result["retention_loss"] == pytest.approx(0.01)
    assert result["negative_transfer_rate"] == 0.0
    assert result["seed_direction"]["positive_count"] == 5
    assert result["route_case_count"] == 10
    assert result["route_divergence_cases"] == 10
    assert result["route_jsd_normalized"][W_REMOVED] > 0.0


def test_metric_reducer_output_replays_through_the_frozen_judge() -> None:
    mappings = suite_mappings()
    for mapping in mappings:
        mapping["experiment_id"] = "HSWM-SWCM-1"
    rows = [observation_from_mapping(row) for row in mappings]
    metrics = evaluate_observations(
        validate_observation_suite(rows),
        strongest_baseline_arm=CONTEXT_VECTOR,
        bootstrap_samples=10_000,
        seed=20260726,
    )
    judgment = judge_metrics(metrics)
    assert judgment["decision"] == "SUPPORTED_SCALAR_CAUSAL_SHADOW_NARROW"
    assert judgment["operator_w_claim_allowed"] is False


def test_metric_suite_rejects_compute_parity_drift() -> None:
    mappings = suite_mappings()
    mappings[0]["input_token_cap"] = 4095
    rows = [observation_from_mapping(row) for row in mappings]
    with pytest.raises(SemanticWeightMetricError, match="parity"):
        validate_observation_suite(rows)


def test_metric_suite_rejects_gold_before_answer_seal() -> None:
    mapping = suite_mappings()[0]
    mapping["gold_reveal_index"] = mapping["answer_seal_index"]
    with pytest.raises(SemanticWeightMetricError, match="before gold"):
        observation_from_mapping(mapping)


def test_metric_suite_rejects_failed_restore() -> None:
    mappings = suite_mappings()
    target = next(row for row in mappings if row["arm_id"] == W_RESTORED)
    target["weight_snapshot_sha256"] = digest("not-full")
    rows = [observation_from_mapping(row) for row in mappings]
    with pytest.raises(SemanticWeightMetricError, match="bit-identical"):
        validate_observation_suite(rows)


def test_metric_suite_requires_both_intervention_sequences() -> None:
    mappings = suite_mappings()
    group = [
        row
        for row in mappings
        if row["item_id"] == "fresh:item:0" and row["seed"] == 1
    ]
    removed = next(row for row in group if row["arm_id"] == W_REMOVED)
    displaced = next(row for row in group if row["arm_order_position"] == 6)
    removed["arm_order_position"], displaced["arm_order_position"] = (
        displaced["arm_order_position"],
        removed["arm_order_position"],
    )
    rows = [observation_from_mapping(row) for row in mappings]
    with pytest.raises(SemanticWeightMetricError, match="frozen FULL"):
        validate_observation_suite(rows)


def test_metric_suite_rejects_mixed_sequence_ids_and_insufficient_seeds() -> None:
    mappings = suite_mappings()
    mappings[0]["sequence_id"] = "forged-sequence"
    rows = [observation_from_mapping(row) for row in mappings]
    with pytest.raises(SemanticWeightMetricError, match="mixes intervention"):
        validate_observation_suite(rows)

    one_seed = [row for row in suite_mappings() if row["seed"] == 1]
    rows = [observation_from_mapping(row) for row in one_seed]
    with pytest.raises(SemanticWeightMetricError, match="five independent"):
        validate_observation_suite(rows)

    six_seeds = suite_mappings()
    extra_seed = [deepcopy(row) for row in six_seeds if row["seed"] == 1]
    for row in extra_seed:
        row["seed"] = 6
    rows = [observation_from_mapping(row) for row in six_seeds + extra_seed]
    with pytest.raises(SemanticWeightMetricError, match="exactly five"):
        validate_observation_suite(rows)


def test_metric_suite_requires_balanced_sequences_and_exact_numeric_restore() -> None:
    one_sequence = [
        row
        for row in suite_mappings()
        if row["sequence_id"] == "FULL_REMOVE_SHUFFLE_RESTORE"
    ]
    rows = [observation_from_mapping(row) for row in one_sequence]
    with pytest.raises(SemanticWeightMetricError, match="balance both"):
        validate_observation_suite(rows)

    mappings = suite_mappings()
    restored = next(row for row in mappings if row["arm_id"] == W_RESTORED)
    restored["pre_llm_logits_sha256"] = digest("forged-restored-logits")
    rows = [observation_from_mapping(row) for row in mappings]
    with pytest.raises(SemanticWeightMetricError, match="logits differ"):
        validate_observation_suite(rows)


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_real_contract_and_preregistration_validate_fail_closed() -> None:
    contract = load_contract()
    contract_receipt = validate_contract(contract, repo_root=ROOT)
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    prereg_receipt = validate_preregistration(prereg, contract_path=CONTRACT_PATH)
    assert contract_receipt["scientific_status"] == "UNJUDGED"
    assert prereg_receipt["measurement_authorized"] is False
    assert validate_with_injected_negative(contract, repo_root=ROOT) is True


def test_contract_rejects_missing_arm_and_hash_drift() -> None:
    contract = load_contract()
    missing = deepcopy(contract)
    missing["required_arms"].pop()
    with pytest.raises(MetricContractValidationError, match="minItems"):
        validate_contract(missing, repo_root=ROOT)

    drifted = deepcopy(contract)
    drifted["runtime_artifacts"][0]["sha256"] = "0" * 64
    with pytest.raises(MetricContractValidationError, match="SHA drift"):
        validate_contract(drifted, repo_root=ROOT)


def test_contract_rejects_scientific_promotion() -> None:
    contract = load_contract()
    promoted = deepcopy(contract)
    promoted["status"] = "SCIENTIFICALLY_VALIDATED"
    with pytest.raises(MetricContractValidationError, match="schema const"):
        validate_contract(promoted, repo_root=ROOT)


def test_contract_and_preregistration_require_explicit_bootstrap_lock() -> None:
    contract = load_contract()
    del contract["statistics"]["bootstrap_seed"]
    with pytest.raises(MetricContractValidationError, match="misses bound schema fields"):
        validate_contract(contract, repo_root=ROOT)

    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    del prereg["statistics"]["bootstrap_interval"]
    with pytest.raises(MetricContractValidationError, match="fields must be exact"):
        validate_preregistration(prereg, contract_path=CONTRACT_PATH)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("formulae", "misses bound schema fields"),
        ("intervention_invariants", "minItems"),
        ("created_at", "ISO date"),
    ],
)
def test_bound_json_schema_rejects_structural_holes(field: str, message: str) -> None:
    contract = load_contract()
    if field == "formulae":
        contract[field] = {}
    elif field == "intervention_invariants":
        contract[field] = []
    else:
        contract[field] = "not-a-date"
    with pytest.raises(MetricContractValidationError, match=message):
        validate_contract(contract, repo_root=ROOT)


@pytest.mark.parametrize(
    "field",
    ["hypothesis", "kill_conditions", "required_before_lock", "judge_binding"],
)
def test_preregistration_rejects_missing_required_sections(field: str) -> None:
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    del prereg[field]
    with pytest.raises(MetricContractValidationError, match="fields must be exact"):
        validate_preregistration(prereg, contract_path=CONTRACT_PATH)


def test_preregistration_rejects_judge_and_server_identity_drift() -> None:
    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    prereg["judge_binding"]["sha256"] = "0" * 64
    with pytest.raises(MetricContractValidationError, match="judge SHA drift"):
        validate_preregistration(prereg, contract_path=CONTRACT_PATH)

    prereg = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    prereg["server_registration"]["state"] = "REGISTERED"
    with pytest.raises(MetricContractValidationError, match="server preregistration"):
        validate_preregistration(prereg, contract_path=CONTRACT_PATH)
