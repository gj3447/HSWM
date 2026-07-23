from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.v1.json"
E1_CONTRACT = HERE / "e1_contract.v1.json"
sys.path.insert(0, str(HERE))

import budget_ledger as ledger  # noqa: E402
import experimental_harness as harness  # noqa: E402


def _source(index: int) -> str:
    return hashlib.sha256(f"source-{index}".encode()).hexdigest()


def _inventories(
    arm_id: str,
    *,
    parameters: int = 7,
    serialized_bytes: int = 64,
    shared_artifact_sha256: str = "c" * 64,
) -> tuple[dict, dict]:
    required_shared_entries = [
        {
            "state_id": state_id,
            "allocation_id": f"{arm_id}:{state_id}-allocation",
            "role": role,
            "byte_length": 32,
            "learned": False,
            "mutable": False,
            "learned_block_id": None,
            "shared_artifact_sha256": shared_artifact_sha256,
        }
        for state_id, role in ledger.REQUIRED_SHARED_IMMUTABLE_COMPONENT_REGISTRY
    ]
    parameter_inventory = {
        "schema": ledger.PARAMETER_INVENTORY_SCHEMA,
        "arm_id": arm_id,
        "registered_learned_block_ids": ["primary-block"],
        "blocks": [
            {
                "learned_block_id": "primary-block",
                "allocation_id": "parameter-allocation",
                "role": "registered_score_block",
                "trainable_parameters": parameters,
            }
        ],
    }
    state_inventory = {
        "schema": ledger.STATE_INVENTORY_SCHEMA,
        "arm_id": arm_id,
        "entries": [
            {
                "state_id": "weights",
                "allocation_id": "serialized-weights",
                "role": "learned_weights",
                "byte_length": serialized_bytes,
                "learned": True,
                "mutable": True,
                "learned_block_id": "primary-block",
            },
            *required_shared_entries,
        ],
    }
    return parameter_inventory, state_inventory


def _state_entry(state_inventory: dict, state_id: str) -> dict:
    return next(
        entry
        for entry in state_inventory["entries"]
        if entry["state_id"] == state_id
    )


def _arm_artifacts(
    arm_id: str,
    *,
    training_examples: int = 4,
    wall_seconds: int = 10,
    parameters: int = 7,
    serialized_bytes: int = 64,
    seed_sha256: str = "a" * 64,
    shared_artifact_sha256: str = "c" * 64,
    update_packets: int = 1,
    dispatch_count: int = 3,
    evaluation_cadence: int = 1,
) -> dict:
    values = {
        "optimizer_steps": 2,
        "training_examples": training_examples,
        "embedding_calls": 3,
        "offline_model_calls": 1,
        "online_model_calls": 1,
        "input_tokens": 40,
        "output_tokens": 20,
        "candidate_edge_scores": 12,
        "revision_events_consumed": 5,
        "update_packets": update_packets,
        "dispatch_count": dispatch_count,
        "evaluation_cadence": evaluation_cadence,
        "scorer_flops": 80,
        "judge_calls": 1,
        "wall_seconds": wall_seconds,
        "peak_bytes": 90,
        "monetary_cost": 2,
    }
    usage = [
        ledger.make_usage_event(
            usage_event_id=f"usage-{index:02d}",
            arm_id=arm_id,
            task_id="independent_selection_action",
            split_id="development",
            dimension=dimension,
            amount=amount,
            source_event_sha256=_source(index),
        )
        for index, (dimension, amount) in enumerate(values.items())
    ]
    usage.append(
        ledger.make_seed_event(
            usage_event_id="usage-seed",
            arm_id=arm_id,
            task_id="independent_selection_action",
            split_id="development",
            seed_id="world-seed",
            seed_sha256=seed_sha256,
            source_event_sha256=_source(99),
        )
    )
    parameters, states = _inventories(
        arm_id,
        parameters=parameters,
        serialized_bytes=serialized_bytes,
        shared_artifact_sha256=shared_artifact_sha256,
    )
    return {
        "usage_events": usage,
        "parameter_inventory": parameters,
        "serialized_state_inventory": states,
    }


def _compare(one: dict, separate: dict, **kwargs) -> dict:
    return ledger.compare_budget_parity(
        arm_artifacts={"one_field": one, "separate_heads": separate},
        compared_arms=["one_field", "separate_heads"],
        **kwargs,
    )


def test_exact_dimensions_match_manifest_v1_and_projection_is_artifact_derived() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert tuple(manifest["budget_contract"]["exact_dimensions"]) == (
        ledger.LEGACY_V1_EXACT_DIMENSIONS
    )
    assert tuple(manifest["budget_contract"]["capped_dimensions"]) == ledger.CAPPED_DIMENSIONS

    result = _compare(_arm_artifacts("one_field"), _arm_artifacts("separate_heads"))
    assert result["equal_measured_budget"] is True
    assert result["engineering_budget_valid"] is True
    assert result["self_report_authoritative"] is False
    assert result["scientific_verdict"] is None
    scope = result["projections"]["one_field"]["scopes"][0]
    assert scope["exact"]["unique_trainable_parameters"] == 7
    assert scope["exact"]["serialized_mutable_bytes"] == 64
    assert scope["artifact_guards"] == {
        "serialized_learned_state_bytes": 64,
        "scorer_flops": 80,
        "judge_calls": 1,
        "replay_bytes": scope["artifact_guards"]["replay_bytes"],
    }
    assert scope["seed_manifest"] == [
        {"seed_id": "world-seed", "seed_sha256": "a" * 64}
    ]


def test_exact_budget_mismatch_cannot_be_overridden_by_forged_self_report() -> None:
    result = _compare(
        _arm_artifacts("one_field", training_examples=4),
        _arm_artifacts("separate_heads", training_examples=5),
        self_report={"equal_budget": True, "winner": "one_field"},
    )
    assert result["equal_measured_budget"] is False
    assert result["engineering_budget_valid"] is False
    assert "BUDGET_INVALID_EXACT_DIMENSION" in {
        mismatch["code"] for mismatch in result["mismatches"]
    }
    assert "SELF_REPORT_IGNORED" in {
        warning["code"] for warning in result["warnings"]
    }
    assert result["scientific_verdict"] is None


@pytest.mark.parametrize(
    ("dimension", "one_kwargs", "separate_kwargs"),
    [
        ("serialized_mutable_bytes", {"serialized_bytes": 64}, {"serialized_bytes": 65}),
        ("update_packets", {"update_packets": 1}, {"update_packets": 2}),
        ("dispatch_count", {"dispatch_count": 3}, {"dispatch_count": 4}),
        ("evaluation_cadence", {"evaluation_cadence": 1}, {"evaluation_cadence": 2}),
    ],
)
def test_each_e1_exact_extension_has_budget_invalid_teeth(
    dimension: str, one_kwargs: dict, separate_kwargs: dict
) -> None:
    result = _compare(
        _arm_artifacts("one_field", **one_kwargs),
        _arm_artifacts("separate_heads", **separate_kwargs),
    )
    assert result["equal_measured_budget"] is False
    assert any(
        mismatch["code"] == "BUDGET_INVALID_EXACT_DIMENSION"
        and mismatch.get("dimension") == dimension
        for mismatch in result["mismatches"]
    )


def test_forged_equal_budget_field_inside_raw_event_is_rejected() -> None:
    artifacts = _arm_artifacts("one_field")
    artifacts["usage_events"][0]["equal_budget"] = True
    with pytest.raises(ledger.BudgetViolation) as caught:
        ledger.derive_budget_projection(arm_id="one_field", **artifacts)
    assert caught.value.code == "FORGED_SELF_REPORT_FIELD"


def test_hidden_head_and_duplicate_allocations_are_detected() -> None:
    parameters, states = _inventories("one_field")
    states["entries"].append(
        {
            "state_id": "shadow-router",
            "allocation_id": "shadow-router-allocation",
            "role": "task_router",
            "byte_length": 16,
            "learned": True,
            "mutable": True,
            "learned_block_id": None,
        }
    )
    with pytest.raises(ledger.BudgetViolation) as caught:
        ledger.inspect_inventories(
            arm_id="one_field",
            parameter_inventory=parameters,
            serialized_state_inventory=states,
        )
    assert caught.value.code == "HIDDEN_HEAD_DETECTED"

    parameters, states = _inventories("one_field")
    parameters["registered_learned_block_ids"].append("second-block")
    parameters["blocks"].append(
        {
            "learned_block_id": "second-block",
            "allocation_id": "parameter-allocation",
            "role": "revision_head",
            "trainable_parameters": 1,
        }
    )
    with pytest.raises(ledger.BudgetViolation) as caught:
        ledger.inspect_inventories(
            arm_id="one_field",
            parameter_inventory=parameters,
            serialized_state_inventory=states,
        )
    assert caught.value.code == "DUPLICATE_ALLOCATION"


def test_capped_resource_non_equality_is_reported_not_forced_equal() -> None:
    result = _compare(
        _arm_artifacts("one_field", wall_seconds=10),
        _arm_artifacts("separate_heads", wall_seconds=12),
        numeric_caps={"wall_seconds": 20, "peak_bytes": 100, "monetary_cost": 3},
    )
    assert result["equal_measured_budget"] is True
    assert result["engineering_budget_valid"] is True
    assert result["capped_resources"]["exactly_equal"] is False
    assert result["capped_resources"]["equality_required"] is False
    assert "CAPPED_RESOURCE_NON_EQUAL_REPORTED" in {
        warning["code"] for warning in result["warnings"]
    }


def test_seed_and_serialized_state_are_artifact_parity_guards() -> None:
    seed_mismatch = _compare(
        _arm_artifacts("one_field", seed_sha256="a" * 64),
        _arm_artifacts("separate_heads", seed_sha256="b" * 64),
    )
    assert "BUDGET_INVALID_SEED_BINDING" in {
        mismatch["code"] for mismatch in seed_mismatch["mismatches"]
    }

    state_mismatch = _compare(
        _arm_artifacts("one_field", serialized_bytes=64),
        _arm_artifacts("separate_heads", serialized_bytes=65),
    )
    assert "BUDGET_INVALID_ARTIFACT_GUARD" in {
        mismatch["code"] for mismatch in state_mismatch["mismatches"]
    }


def test_shared_immutable_state_compares_semantics_and_hash_not_allocation_namespace() -> None:
    matched = _compare(
        _arm_artifacts("one_field", shared_artifact_sha256="c" * 64),
        _arm_artifacts("separate_heads", shared_artifact_sha256="c" * 64),
    )
    assert matched["engineering_budget_valid"] is True
    one_binding = matched["projections"]["one_field"]["inventory"][
        "shared_immutable_state_bindings"
    ][0]
    separate_binding = matched["projections"]["separate_heads"]["inventory"][
        "shared_immutable_state_bindings"
    ][0]
    assert one_binding == separate_binding
    assert "allocation_id" not in one_binding

    mismatched = _compare(
        _arm_artifacts("one_field", shared_artifact_sha256="c" * 64),
        _arm_artifacts("separate_heads", shared_artifact_sha256="d" * 64),
    )
    assert mismatched["engineering_budget_valid"] is False
    assert "BUDGET_INVALID_SHARED_ARTIFACT" in {
        mismatch["code"] for mismatch in mismatched["mismatches"]
    }


def test_hash_shared_state_must_really_be_immutable() -> None:
    parameters, states = _inventories("one_field")
    _state_entry(states, "task_adapter")["mutable"] = True
    with pytest.raises(ledger.BudgetViolation) as caught:
        ledger.inspect_inventories(
            arm_id="one_field",
            parameter_inventory=parameters,
            serialized_state_inventory=states,
        )
    assert caught.value.code == "REQUIRED_SHARED_COMPONENT_STATE_INVALID"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing", "REQUIRED_SHARED_COMPONENT_MISSING"),
        ("renamed", "UNREGISTERED_SHARED_ARTIFACT"),
        ("role_spoof", "REQUIRED_SHARED_COMPONENT_ROLE_MISMATCH"),
        ("hash_omitted", "REQUIRED_SHARED_COMPONENT_HASH_MISSING"),
    ],
)
def test_required_shared_registry_fails_closed(
    mutation: str, expected_code: str
) -> None:
    parameters, states = _inventories("one_field")
    target = _state_entry(states, "task_adapter")
    if mutation == "missing":
        states["entries"].remove(target)
    elif mutation == "renamed":
        target["state_id"] = "common_component_task_adapter"
    elif mutation == "role_spoof":
        target["role"] = "common_component_task_adapter"
    else:
        target.pop("shared_artifact_sha256")

    with pytest.raises(ledger.BudgetViolation) as caught:
        ledger.inspect_inventories(
            arm_id="one_field",
            parameter_inventory=parameters,
            serialized_state_inventory=states,
        )
    assert caught.value.code == expected_code


def test_empty_shared_binding_marker_bypass_and_unregistered_sharing_are_rejected() -> None:
    parameters, states = _inventories("one_field")
    for index, (state_id, _role) in enumerate(
        ledger.REQUIRED_SHARED_IMMUTABLE_COMPONENT_REGISTRY
    ):
        target = _state_entry(states, state_id)
        target["state_id"] = f"common_component_{index}"
        target["role"] = f"common_component_role_{index}"
        target.pop("shared_artifact_sha256")
    with pytest.raises(ledger.BudgetViolation) as caught:
        ledger.inspect_inventories(
            arm_id="one_field",
            parameter_inventory=parameters,
            serialized_state_inventory=states,
        )
    assert caught.value.code == "REQUIRED_SHARED_COMPONENT_MISSING"

    parameters, states = _inventories("one_field")
    states["entries"].append(
        {
            "state_id": "arm_local_cache",
            "allocation_id": "arm-local-cache-allocation",
            "role": "immutable_arm_local_cache",
            "byte_length": 8,
            "learned": False,
            "mutable": False,
            "learned_block_id": None,
            "shared_artifact_sha256": "f" * 64,
        }
    )
    with pytest.raises(ledger.BudgetViolation) as caught:
        ledger.inspect_inventories(
            arm_id="one_field",
            parameter_inventory=parameters,
            serialized_state_inventory=states,
        )
    assert caught.value.code == "UNREGISTERED_SHARED_ARTIFACT"


def test_arm_local_immutable_state_is_allowed_without_claiming_shared() -> None:
    parameters, states = _inventories("one_field")
    states["entries"].append(
        {
            "state_id": "arm_local_decoder_cache",
            "allocation_id": "arm-local-decoder-cache-allocation",
            "role": "immutable_arm_local_decoder_cache",
            "byte_length": 8,
            "learned": False,
            "mutable": False,
            "learned_block_id": None,
        }
    )
    report = ledger.inspect_inventories(
        arm_id="one_field",
        parameter_inventory=parameters,
        serialized_state_inventory=states,
    )
    assert [
        binding["state_id"]
        for binding in report["shared_immutable_state_bindings"]
    ] == [
        state_id
        for state_id, _role in ledger.REQUIRED_SHARED_IMMUTABLE_COMPONENT_REGISTRY
    ]


def test_padding_usage_is_rejected() -> None:
    artifacts = _arm_artifacts("one_field")
    artifacts["usage_events"][0]["padding"] = True
    with pytest.raises(ledger.BudgetViolation) as caught:
        ledger.derive_budget_projection(arm_id="one_field", **artifacts)
    assert caught.value.code == "PADDING_EVENT_FORBIDDEN"


def test_equal_missing_dimensions_do_not_turn_into_false_zero_parity() -> None:
    artifacts = _arm_artifacts("one_field")
    artifacts["usage_events"] = [
        event
        for event in artifacts["usage_events"]
        if event["dimension"] != "dispatch_count"
    ]
    with pytest.raises(ledger.BudgetViolation) as caught:
        ledger.derive_budget_projection(arm_id="one_field", **artifacts)
    assert caught.value.code == "BUDGET_DIMENSION_MISSING"

    artifacts = _arm_artifacts("one_field")
    artifacts["usage_events"] = [
        event for event in artifacts["usage_events"] if event["dimension"] != "seed_binding"
    ]
    with pytest.raises(ledger.BudgetViolation) as caught:
        ledger.derive_budget_projection(arm_id="one_field", **artifacts)
    assert caught.value.code == "BUDGET_DIMENSION_MISSING"


def test_budget_events_are_bound_to_verified_harness_event_hashes() -> None:
    run = harness.ExperimentHarness(
        {"cut": "frozen"}, ["one_field"], experiment_id="e1-integration"
    ).arm("one_field")
    required_usage_dimensions = (
        set(ledger.E1_EXACT_DIMENSIONS)
        | set(ledger.ARTIFACT_PARITY_GUARDS)
    ) - {
        "unique_trainable_parameters",
        "serialized_mutable_bytes",
        "serialized_learned_state_bytes",
        "replay_bytes",
    }
    committed = []
    for index, dimension in enumerate(sorted(required_usage_dimensions)):
        usage = ledger.make_usage_event(
            usage_event_id=f"step-{index}",
            arm_id="one_field",
            task_id="selection",
            split_id="dev",
            dimension=dimension,
            amount=1 if dimension == "optimizer_steps" else 0,
        )
        committed.append(
            run.append_event(
                request_id=f"budget-{index}",
                event_type="budget",
                payload={"usage": usage},
            )
        )
    seed_usage = ledger.make_seed_event(
        usage_event_id="step-seed",
        arm_id="one_field",
        task_id="selection",
        split_id="dev",
        seed_id="world-seed",
        seed_sha256="a" * 64,
    )
    committed.append(
        run.append_event(
            request_id="budget-seed",
            event_type="budget",
            payload={"usage": seed_usage},
        )
    )
    run.replay()
    extracted = ledger.extract_usage_events(run.events)
    assert extracted[0]["source_event_sha256"] == committed[0]["event_sha256"]

    parameters, states = _inventories("one_field")
    projection = ledger.derive_budget_projection(
        arm_id="one_field",
        usage_events=extracted,
        parameter_inventory=parameters,
        serialized_state_inventory=states,
    )
    assert projection["scopes"][0]["exact"]["optimizer_steps"] == 1

    forged = copy.deepcopy(run.events)
    forged[0]["payload"]["usage"]["amount"] = 9
    with pytest.raises(ledger.BudgetViolation) as caught:
        ledger.extract_usage_events(forged)
    assert caught.value.code == "SOURCE_EVENT_HASH_MISMATCH"


def _receipt_fixture(*, separate_training_examples: int = 4):
    experiment = harness.ExperimentHarness(
        {"cut_id": "frozen-cut", "weights": {"edge": 1}, "history": []},
        harness.CANONICAL_ARM_IDS,
        experiment_id="e1-receipt",
        run_names={
            "one_field": "receipt-one-field",
            "separate_heads": "receipt-separate-heads",
            "hard_versioned_revision_comparator": "receipt-hard-versioned",
            "unversioned_negative_control": "receipt-unversioned-control",
        },
    )
    inventory_artifacts = {}
    # C/D are intentionally structurally and numerically different controls.
    # Their projections remain source-complete and guarded, but only A/B are an
    # exact-equality cohort.
    for arm_id, training_examples, parameters, serialized_bytes in (
        ("one_field", 4, 7, 64),
        ("separate_heads", separate_training_examples, 7, 64),
        ("hard_versioned_revision_comparator", 2, 0, 0),
        ("unversioned_negative_control", 9, 3, 16),
    ):
        run = experiment.arm(arm_id)
        run.append_event(
            request_id="input",
            event_type="input",
            payload={"task_id": "independent_selection_action", "split_id": "development"},
        )
        run.append_event(
            request_id="score",
            event_type="score",
            payload={
                "task_id": "independent_selection_action",
                "split_id": "development",
                "scores": [0, 1],
            },
        )
        next_state = run.state
        next_state["weights"]["edge"] = 2
        next_state["history"].append("update")
        run.append_event(
            request_id="update",
            event_type="update",
            payload={"task_id": "independent_selection_action", "split_id": "development"},
            state_after=next_state,
        )
        run.append_event(
            request_id="evaluation",
            event_type="evaluation",
            payload={"task_id": "independent_selection_action", "split_id": "development"},
        )
        artifacts = _arm_artifacts(
            arm_id,
            training_examples=training_examples,
            wall_seconds=10,
            parameters=parameters,
            serialized_bytes=serialized_bytes,
            update_packets=1,
            evaluation_cadence=1,
        )
        for index, raw_usage in enumerate(artifacts["usage_events"]):
            usage = copy.deepcopy(raw_usage)
            usage.pop("source_event_sha256")
            run.append_event(
                request_id=f"budget-{index}",
                event_type="budget",
                payload={"usage": usage},
            )
        inventory_artifacts[arm_id] = {
            "parameter_inventory": artifacts["parameter_inventory"],
            "serialized_state_inventory": artifacts["serialized_state_inventory"],
        }
    return experiment, inventory_artifacts


def _receipt_hash(receipt: dict) -> str:
    unsigned = copy.deepcopy(receipt)
    unsigned.pop("receipt_sha256", None)
    return harness.canonical_sha256(unsigned)


def test_engineering_receipt_joins_verified_replay_budget_inventory_and_code() -> None:
    experiment, inventories = _receipt_fixture()
    receipt = harness.build_engineering_receipt(
        experiment=experiment,
        required_arms=harness.CANONICAL_ARM_IDS,
        arm_inventories=inventories,
        evaluator_sha256="e" * 64,
        analysis_code_sha256="d" * 64,
        numeric_caps={"wall_seconds": 20, "peak_bytes": 100, "monetary_cost": 3},
    )
    assert receipt["pass_code"] == harness.EXPERIMENT_HARNESS_PASS
    assert receipt["authority"] == "ENGINEERING_ONLY"
    assert receipt["scientific_verdict"] is None
    assert receipt["budget"]["engineering_budget_valid"] is True
    assert receipt["required_arms"] == list(harness.CANONICAL_ARM_IDS)
    assert list(receipt["arm_replays"]) == list(harness.CANONICAL_ARM_IDS)
    assert receipt["arm_roles"] == [
        {"arm_id": arm_id, "role_id": harness.ARM_ROLE_IDS[arm_id]}
        for arm_id in harness.CANONICAL_ARM_IDS
    ]
    required_shared_registry = [
        {"state_id": state_id, "role": role}
        for state_id, role in ledger.REQUIRED_SHARED_IMMUTABLE_COMPONENT_REGISTRY
    ]
    registry_binding = receipt["shared_immutable_component_registry"]
    assert registry_binding["required_components"] == required_shared_registry
    assert registry_binding["registry_sha256"] == harness.canonical_sha256(
        required_shared_registry
    )
    assert registry_binding["verified_on_arms"] == list(harness.CANONICAL_ARM_IDS)
    assert registry_binding["allocation_id_cross_arm_authoritative"] is False
    assert registry_binding["complete"] is True
    assert receipt["budget"]["exact_parity_cohort"] == list(
        harness.EXACT_PARITY_COHORT
    )
    assert receipt["budget"]["control_arm_policy"] == {
        "policy_code": harness.CONTROL_BUDGET_POLICY_CODE,
        "arms": list(harness.CONTROL_ARM_IDS),
        "exact_equality_exempt": True,
        "required_guards": [
            "canonical_participation_and_role_binding",
            "complete_source_backed_projection",
            "inventory_validation",
            "numeric_caps",
            "shared_immutable_state_identity",
            "replay_counter_consistency",
        ],
    }
    for arm in receipt["arm_replays"].values():
        assert arm["event_count"] > 0
        assert len(arm["event_root_sha256"]) == 64
        assert len(arm["replay_sha256"]) == 64
        assert len(arm["usage_events_sha256"]) == 64
        assert len(arm["parameter_inventory_sha256"]) == 64
        assert len(arm["serialized_state_inventory_sha256"]) == 64
        assert arm[
            "required_shared_immutable_component_registry_sha256"
        ] == registry_binding["registry_sha256"]
        assert len(arm["event_topology_sha256"]) == 64
        assert arm["event_topology"]["scopes"][0]["update_packets"] == 1
        assert arm["event_topology"]["scopes"][0]["evaluation_cadence"] == 1

    reversed_receipt = harness.build_engineering_receipt(
        experiment=experiment,
        required_arms=list(reversed(harness.CANONICAL_ARM_IDS)),
        arm_inventories=inventories,
        evaluator_sha256="e" * 64,
        analysis_code_sha256="d" * 64,
        numeric_caps={"wall_seconds": 20, "peak_bytes": 100, "monetary_cost": 3},
    )
    assert reversed_receipt == receipt

    verified = harness.verify_engineering_receipt(
        receipt=receipt,
        experiment=experiment,
        required_arms=list(reversed(harness.CANONICAL_ARM_IDS)),
        arm_inventories=inventories,
        evaluator_sha256="e" * 64,
        analysis_code_sha256="d" * 64,
        numeric_caps={"wall_seconds": 20, "peak_bytes": 100, "monetary_cost": 3},
    )
    assert verified == receipt


@pytest.mark.parametrize(
    "required_arms",
    [
        harness.CANONICAL_ARM_IDS[:-1],
        (*harness.CANONICAL_ARM_IDS[:-1], "renamed_control"),
        (*harness.CANONICAL_ARM_IDS, "extra_arm"),
    ],
)
def test_receipt_rejects_missing_renamed_or_extra_required_arm_ids(
    required_arms,
) -> None:
    experiment, inventories = _receipt_fixture()
    with pytest.raises(harness.HarnessViolation) as caught:
        harness.build_engineering_receipt(
            experiment=experiment,
            required_arms=required_arms,
            arm_inventories=inventories,
            evaluator_sha256="e" * 64,
            analysis_code_sha256="d" * 64,
        )
    assert caught.value.code == "RECEIPT_ARM_SET_INVALID"


@pytest.mark.parametrize("extra_event_type", ["update", "evaluation"])
def test_receipt_rejects_replay_topology_not_backed_by_usage_counter(
    extra_event_type: str,
) -> None:
    experiment, inventories = _receipt_fixture()
    run = experiment.arm("one_field")
    kwargs = {
        "request_id": f"extra-noop-{extra_event_type}",
        "event_type": extra_event_type,
        "payload": {
            "task_id": "independent_selection_action",
            "split_id": "development",
        },
    }
    if extra_event_type == "update":
        kwargs["state_after"] = run.state
    run.append_event(**kwargs)

    with pytest.raises(harness.HarnessViolation) as caught:
        harness.build_engineering_receipt(
            experiment=experiment,
            required_arms=harness.CANONICAL_ARM_IDS,
            arm_inventories=inventories,
            evaluator_sha256="e" * 64,
            analysis_code_sha256="d" * 64,
        )
    assert caught.value.code == "BUDGET_EVENT_TOPOLOGY_MISMATCH"


def test_receipt_compares_shared_immutable_state_across_all_four_arms() -> None:
    experiment, inventories = _receipt_fixture()
    _state_entry(
        inventories["hard_versioned_revision_comparator"][
            "serialized_state_inventory"
        ],
        "shared_decoder",
    )["shared_artifact_sha256"] = "d" * 64
    with pytest.raises(harness.HarnessViolation) as caught:
        harness.build_engineering_receipt(
            experiment=experiment,
            required_arms=harness.CANONICAL_ARM_IDS,
            arm_inventories=inventories,
            evaluator_sha256="e" * 64,
            analysis_code_sha256="d" * 64,
        )
    assert caught.value.code == "BUDGET_INVALID"
    assert "BUDGET_INVALID_SHARED_ARTIFACT" in str(caught.value)


def test_receipt_rejects_empty_shared_binding_marker_bypass() -> None:
    experiment, inventories = _receipt_fixture()
    states = inventories["unversioned_negative_control"][
        "serialized_state_inventory"
    ]
    for index, (state_id, _role) in enumerate(
        ledger.REQUIRED_SHARED_IMMUTABLE_COMPONENT_REGISTRY
    ):
        target = _state_entry(states, state_id)
        target["state_id"] = f"common_component_{index}"
        target["role"] = f"common_component_role_{index}"
        target.pop("shared_artifact_sha256")
    with pytest.raises(harness.HarnessViolation) as caught:
        harness.build_engineering_receipt(
            experiment=experiment,
            required_arms=harness.CANONICAL_ARM_IDS,
            arm_inventories=inventories,
            evaluator_sha256="e" * 64,
            analysis_code_sha256="d" * 64,
        )
    assert caught.value.code == "REQUIRED_SHARED_COMPONENT_MISSING"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda receipt: receipt["arm_replays"]["one_field"].update(
            {"replay_sha256": "0" * 64}
        ),
        lambda receipt: receipt["budget"].update({"parity_sha256": "0" * 64}),
        lambda receipt: receipt["arm_replays"]["one_field"]["event_topology"][
            "scopes"
        ][0].update({"update_packets": 2}),
        lambda receipt: receipt["code_bindings"].update(
            {"analysis_code_sha256": "0" * 64}
        ),
        lambda receipt: receipt["arm_replays"].pop("separate_heads"),
    ],
)
def test_altered_receipt_facts_cannot_reverify(mutation) -> None:
    experiment, inventories = _receipt_fixture()
    receipt = harness.build_engineering_receipt(
        experiment=experiment,
        required_arms=harness.CANONICAL_ARM_IDS,
        arm_inventories=inventories,
        evaluator_sha256="e" * 64,
        analysis_code_sha256="d" * 64,
    )
    mutation(receipt)
    receipt["receipt_sha256"] = _receipt_hash(receipt)
    with pytest.raises(harness.HarnessViolation) as caught:
        harness.verify_engineering_receipt(
            receipt=receipt,
            experiment=experiment,
            required_arms=harness.CANONICAL_ARM_IDS,
            arm_inventories=inventories,
            evaluator_sha256="e" * 64,
            analysis_code_sha256="d" * 64,
        )
    assert caught.value.code == "RECEIPT_EVIDENCE_MISMATCH"


def test_receipt_refuses_missing_arm_direct_usage_and_invalid_budget() -> None:
    experiment, inventories = _receipt_fixture()
    missing = {"one_field": inventories["one_field"]}
    with pytest.raises(harness.HarnessViolation) as caught:
        harness.build_engineering_receipt(
            experiment=experiment,
            required_arms=harness.CANONICAL_ARM_IDS,
            arm_inventories=missing,
            evaluator_sha256="e" * 64,
            analysis_code_sha256="d" * 64,
        )
    assert caught.value.code == "RECEIPT_ARM_MISSING"

    direct = copy.deepcopy(inventories)
    direct["one_field"]["usage_events"] = _arm_artifacts("one_field")["usage_events"]
    with pytest.raises(harness.HarnessViolation) as caught:
        harness.build_engineering_receipt(
            experiment=experiment,
            required_arms=harness.CANONICAL_ARM_IDS,
            arm_inventories=direct,
            evaluator_sha256="e" * 64,
            analysis_code_sha256="d" * 64,
        )
    assert caught.value.code == "DIRECT_USAGE_ARTIFACT_FORBIDDEN"

    unequal_experiment, unequal_inventories = _receipt_fixture(
        separate_training_examples=5
    )
    with pytest.raises(harness.HarnessViolation) as caught:
        harness.build_engineering_receipt(
            experiment=unequal_experiment,
            required_arms=harness.CANONICAL_ARM_IDS,
            arm_inventories=unequal_inventories,
            evaluator_sha256="e" * 64,
            analysis_code_sha256="d" * 64,
        )
    assert caught.value.code == "BUDGET_INVALID"


def test_e1_contract_is_engineering_only_and_exposes_future_falsifiers() -> None:
    contract = json.loads(E1_CONTRACT.read_text(encoding="utf-8"))
    assert contract["exit_boundary"]["pass_code"] == "EXPERIMENT_HARNESS_PASS"
    assert contract["exit_boundary"]["authority"] == "ENGINEERING_ONLY"
    assert contract["exit_boundary"]["scientific_verdict"] is None
    assert contract["prohibitions"]["efficacy_run"] is True
    assert contract["budget_authority"]["legacy_v1_exact_dimensions"] == list(
        ledger.LEGACY_V1_EXACT_DIMENSIONS
    )
    assert contract["budget_authority"]["e1_exact_dimensions"] == list(
        ledger.E1_EXACT_DIMENSIONS
    )
    assert contract["arm_registry"]["receipt_requires_exact_id_set"] == list(
        harness.CANONICAL_ARM_IDS
    )
    assert contract["budget_authority"]["exact_parity_cohort"] == list(
        harness.EXACT_PARITY_COHORT
    )
    assert contract["budget_authority"]["control_arm_policy"][
        "policy_code"
    ] == harness.CONTROL_BUDGET_POLICY_CODE
    assert contract["budget_authority"]["replay_derivable_counter_scope"] == list(
        harness.REPLAY_DERIVED_USAGE_COUNTERS
    )
    required_shared_registry = [
        {"state_id": state_id, "role": role}
        for state_id, role in ledger.REQUIRED_SHARED_IMMUTABLE_COMPONENT_REGISTRY
    ]
    assert contract["inventory_contract"][
        "required_shared_immutable_component_registry"
    ] == required_shared_registry
    assert contract["inventory_contract"][
        "required_shared_registry_frozen_for_receipt_schema"
    ] is True
    assert {
        "REQUIRED_SHARED_COMPONENT_MISSING",
        "REQUIRED_SHARED_COMPONENT_ROLE_MISMATCH",
        "REQUIRED_SHARED_COMPONENT_HASH_MISSING",
        "UNREGISTERED_SHARED_ARTIFACT",
    }.issubset(contract["mismatch_codes"])
    assert "RAW_USAGE_ONLY_NOT_REPLAY_DERIVABLE" in contract["budget_authority"][
        "counter_sources"
    ]["dispatch_count"]
    assert [arm["id"] for arm in contract["minimum_arm_roles"]] == list(
        harness.CANONICAL_ARM_IDS
    )
    assert {arm["role"] for arm in contract["minimum_arm_roles"]} == {
        "A_ONE_FIELD",
        "B_SHARED_SUBSTRATE_SEPARATE_HEADS",
        "C_HARD_REVISION_THEN_SCORING",
        "D_UNVERSIONED_SHARED_NEGATIVE_CONTROL",
    }
    future = contract["future_scientific_join_inputs"]
    assert future["status"] == "EXPOSED_NOT_EVALUATED"
    assert future["high_conflict_regime"] is True
    assert future["per_task_noninferiority"] is None
    assert future["stale_leakage_ceiling"] is None
    assert any("content bindings" in item for item in contract["limitations"])
