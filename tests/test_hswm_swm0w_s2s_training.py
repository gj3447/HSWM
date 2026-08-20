from __future__ import annotations

from dataclasses import replace
import math

import numpy as np
import pytest

from hswm.experiments import swm0w_s2s_training as training
from hswm.experiments.swm0w_s2s_family import generate_task
from hswm.experiments.swm0w_s2s_operator import (
    S2SArm,
    S2SOperator,
    forward,
    parameter_shapes,
)


@pytest.fixture(scope="module")
def task():
    return generate_task(external_seed=bytes(range(32)))


@pytest.fixture(scope="module")
def complete_cases(task):
    return tuple(task.iter_cases("train")), tuple(task.iter_cases("dev"))


def _config(**changes):
    return replace(training.S2STrainingConfig(max_updates=0), **changes)


def _random_problem(arm: S2SArm):
    rng = np.random.default_rng(30 + tuple(S2SArm).index(arm))
    parameters = {
        name: rng.normal(scale=0.1, size=shape).astype(np.float64)
        for name, shape in parameter_shapes(arm).items()
    }
    x = rng.normal(size=(2, 3, 2, 4)).astype(np.float64)
    targets = rng.normal(scale=0.2, size=(2, 3, 2, 2)).astype(np.float64)
    weights = np.exp(rng.normal(scale=0.2, size=(3, 2))).astype(np.float64)
    return parameters, x, targets, weights


@pytest.mark.parametrize("arm", tuple(S2SArm))
def test_task_independent_initializer_has_exact_positive_zero_output_heads(arm):
    first = training.initialize_training_operator(arm, seed=17)
    replay = training.initialize_training_operator(arm, seed=17)
    changed = training.initialize_training_operator(arm, seed=18)
    assert first.parameters_sha256 == replay.parameters_sha256
    assert first.parameters_sha256 != changed.parameters_sha256
    assert first.learned is False

    output_names = (
        ("out_w", "out_b")
        if arm is S2SArm.DS870
        else tuple(
            name
            for name in parameter_shapes(arm)
            if name not in {"phi_w", "psi_w"}
        )
    )
    for name in output_names:
        expected = np.zeros(first.parameters[name].shape, dtype=np.float64)
        assert first.parameters[name].tobytes(order="C") == expected.tobytes(order="C")
    x = np.linspace(-1.0, 1.0, 24, dtype=np.float64).reshape(3, 2, 4)
    assert np.array_equal(first.forward(x), np.zeros((3, 2, 2), dtype=np.float64))


def test_initializer_is_structurally_task_independent(task):
    other_task = generate_task(external_seed=bytes(reversed(range(32))))
    assert task.manifest_sha256 != other_task.manifest_sha256
    # No task is an initializer argument; the same arm/seed has one state.
    assert (
        training.initialize_training_operator(S2SArm.T16, seed=4).parameters_sha256
        == training.initialize_training_operator(S2SArm.T16, seed=4).parameters_sha256
    )


@pytest.mark.parametrize("arm", tuple(S2SArm))
def test_training_forward_cache_is_byte_equal_to_operator_forward(arm):
    parameters, x, _, _ = _random_problem(arm)
    predicted, _ = training._forward_with_cache(arm, parameters, x)
    expected = forward(S2SOperator(arm, parameters), x)
    assert predicted.tobytes(order="C") == expected.tobytes(order="C")


@pytest.mark.parametrize("arm", tuple(S2SArm))
def test_all_870_scalar_analytic_gradients_match_central_differences(arm):
    parameters, x, targets, weights = _random_problem(arm)
    _, gradients = training._loss_and_gradients(
        arm, parameters, x, targets, weights
    )
    epsilon = 1.0e-6
    checked = 0
    for name, value in parameters.items():
        for index in np.ndindex(value.shape):
            original = value[index]
            value[index] = original + epsilon
            plus = training._loss_for_parameters(
                arm, parameters, x, targets, weights
            )
            value[index] = original - epsilon
            minus = training._loss_for_parameters(
                arm, parameters, x, targets, weights
            )
            value[index] = original
            numeric = (plus - minus) / (2.0 * epsilon)
            assert math.isclose(
                float(gradients[name][index]), numeric, rel_tol=2.0e-7, abs_tol=2.0e-9
            ), (arm, name, index, gradients[name][index], numeric)
            checked += 1
    assert checked == 870


@pytest.mark.parametrize("arm", tuple(S2SArm))
def test_all_tensor_directional_derivative_matches_analytic_gradient(arm):
    parameters, x, targets, weights = _random_problem(arm)
    _, gradients = training._loss_and_gradients(
        arm, parameters, x, targets, weights
    )
    rng = np.random.default_rng(90 + tuple(S2SArm).index(arm))
    directions = {
        name: rng.normal(size=value.shape).astype(np.float64)
        for name, value in parameters.items()
    }
    norm = math.sqrt(
        sum(float(np.sum(direction * direction)) for direction in directions.values())
    )
    directions = {name: direction / norm for name, direction in directions.items()}
    epsilon = 1.0e-6
    plus = {
        name: value + epsilon * directions[name] for name, value in parameters.items()
    }
    minus = {
        name: value - epsilon * directions[name] for name, value in parameters.items()
    }
    numeric = (
        training._loss_for_parameters(arm, plus, x, targets, weights)
        - training._loss_for_parameters(arm, minus, x, targets, weights)
    ) / (2.0 * epsilon)
    analytic = sum(
        float(np.sum(gradients[name] * directions[name])) for name in parameters
    )
    assert math.isclose(analytic, numeric, rel_tol=2.0e-7, abs_tol=2.0e-9)


def test_psi_gradient_routes_diagonal_source_to_comember_only():
    arm = S2SArm.P_CAP18
    parameters = {
        name: np.zeros(shape, dtype=np.float64)
        for name, shape in parameter_shapes(arm).items()
    }
    parameters["phi_w"][0, 0, 0] = 1.0
    parameters["pair_w"][0, 0, 0, 0] = 1.0
    x = np.zeros((1, 3, 2, 4), dtype=np.float64)
    x[0, 0, 0] = (2.0, 3.0, 5.0, 7.0)
    x[0, 0, 1] = (11.0, 13.0, 17.0, 19.0)
    derivative = np.zeros((1, 3, 2, 2), dtype=np.float64)
    derivative[0, 0, 0, 0] = 1.0
    _, cache = training._forward_with_cache(arm, parameters, x)
    gradients = training._t_or_p_gradients(
        arm, parameters, x, derivative, cache
    )
    expected = np.zeros_like(parameters["psi_w"])
    expected[0, :, 0] = 2.0 * x[0, 0, 1]
    assert np.array_equal(gradients["psi_w"], expected)


def test_ds_summary_gradient_is_broadcast_to_both_source_members():
    arm = S2SArm.DS870
    parameters = {
        name: np.zeros(shape, dtype=np.float64)
        for name, shape in parameter_shapes(arm).items()
    }
    # Decoder field 16 is source-role 1's first learned summary coordinate.
    parameters["hidden1_w"][16, 0] = 1.0
    parameters["hidden2_w"][0, 0] = 1.0
    parameters["out_w"][0, 0] = 1.0
    x = np.zeros((1, 3, 2, 4), dtype=np.float64)
    x[0, 1, 0] = (2.0, 3.0, 5.0, 7.0)
    x[0, 1, 1] = (11.0, 13.0, 17.0, 19.0)
    derivative = np.zeros((1, 3, 2, 2), dtype=np.float64)
    derivative[0, 0, 0, 0] = 1.0
    _, cache = training._forward_with_cache(arm, parameters, x)
    gradients = training._ds_gradients(parameters, x, derivative, cache)
    expected_eta_w = np.zeros_like(parameters["eta_w"])
    expected_eta_w[1, :, 0] = x[0, 1, 0] + x[0, 1, 1]
    expected_eta_b = np.zeros_like(parameters["eta_b"])
    expected_eta_b[1, 0] = 2.0
    assert np.array_equal(gradients["eta_w"], expected_eta_w)
    assert np.array_equal(gradients["eta_b"], expected_eta_b)


def test_complete_train_statistics_are_exact_python_integer_receipts(task, complete_cases):
    train, _ = complete_cases
    receipts = training._build_stratum_loss_receipts(train)
    assert len(receipts) == 6
    for receipt in receipts:
        values = [
            case.target_numerators[2 * receipt.role + member][receipt.channel]
            for case in train
            for member in range(2)
        ]
        assert type(receipt.target_numerator_sum) is int
        assert receipt.sample_count == 12_500
        assert receipt.target_numerator_sum == sum(values)
        assert receipt.target_numerator_sum_squares == sum(value * value for value in values)
        assert receipt.centered_sum_squares_numerator == (
            len(values) * sum(value * value for value in values) - sum(values) ** 2
        )
        assert receipt.receipt_sha256 == training.canonical_sha256(receipt.unsigned())


@pytest.mark.parametrize("arm", tuple(S2SArm))
def test_epoch_zero_is_an_eligible_exact_restore(task, complete_cases, arm):
    train, dev = complete_cases
    model = training.fit_task_operator(
        task, train, dev, arm=arm, config=_config(max_updates=0)
    )
    initial = training.initialize_training_operator(arm, seed=0)
    receipt = model.optimization
    assert receipt.best_update == receipt.stopped_update == receipt.update_count == 0
    assert receipt.history_entry_count == 1
    assert receipt.best_parameters_sha256 == receipt.initial_parameters_sha256
    assert model.parameters_sha256 == initial.parameters_sha256
    assert model.fitted is True
    assert model.learned is False
    assert model.as_unlabeled_operator().learned is False


def test_strict_min_delta_retains_earliest_epoch_and_patience_stops(task, complete_cases):
    train, dev = complete_cases
    model = training.fit_task_operator(
        task,
        train,
        dev,
        arm=S2SArm.T16,
        config=_config(max_updates=5, patience=1, min_delta=1.0e6),
    )
    receipt = model.optimization
    assert receipt.best_update == 0
    assert receipt.stopped_update == 1
    assert receipt.termination_reason is training.TerminationReason.PATIENCE
    assert model.parameters_sha256 == receipt.initial_parameters_sha256
    assert model.learned is False


def test_one_improving_update_crosses_only_the_receipted_learned_boundary(task, complete_cases):
    train, dev = complete_cases
    model = training.fit_task_operator(
        task,
        train,
        dev,
        arm=S2SArm.T16,
        config=_config(max_updates=1, learning_rate=1.0e-4),
    )
    assert model.optimization.best_update == 1
    assert model.parameters_sha256 != model.optimization.initial_parameters_sha256
    assert model.fitted is True
    assert model.learned is True
    assert model.as_unlabeled_operator().learned is False


def test_reordered_complete_tuples_are_bit_deterministic(task, complete_cases):
    train, dev = complete_cases
    config = _config(max_updates=1, learning_rate=1.0e-4)
    canonical = training.fit_task_operator(
        task, train, dev, arm=S2SArm.T16, config=config
    )
    reversed_input = training.fit_task_operator(
        task,
        tuple(reversed(train)),
        tuple(reversed(dev)),
        arm=S2SArm.T16,
        config=config,
    )
    assert canonical.parameters_sha256 == reversed_input.parameters_sha256
    assert canonical.optimization.canonical() == reversed_input.optimization.canonical()
    assert canonical.state_sha256 == reversed_input.state_sha256


def test_complete_split_boundary_rejects_type_missing_duplicate_and_leakage(task, complete_cases):
    train, dev = complete_cases
    config = _config()
    with pytest.raises(training.SWM0WS2STrainingError, match="immutable tuple"):
        training.fit_task_operator(task, list(train), dev, arm=S2SArm.T16, config=config)
    with pytest.raises(training.SWM0WS2STrainingError, match="complete"):
        training.fit_task_operator(task, train[:-1], dev, arm=S2SArm.T16, config=config)
    duplicate = (*train[:-1], train[0])
    with pytest.raises(training.SWM0WS2STrainingError, match="duplicate"):
        training.fit_task_operator(task, duplicate, dev, arm=S2SArm.T16, config=config)
    leaked = (*train[:-1], dev[0])
    with pytest.raises(training.SWM0WS2STrainingError, match="leakage"):
        training.fit_task_operator(task, leaked, dev, arm=S2SArm.T16, config=config)
    with pytest.raises(training.SWM0WS2STrainingError, match="exact EvaluatorCaseV2"):
        training.fit_task_operator(
            task, (*train[:-1], object()), dev, arm=S2SArm.T16, config=config
        )


def test_boundary_rejects_cross_task_and_test_split(task, complete_cases):
    train, dev = complete_cases
    other = generate_task(external_seed=b"z" * 32)
    other_train = tuple(other.iter_cases("train"))
    cross_task = (*train[:-1], other_train[0])
    with pytest.raises(training.SWM0WS2STrainingError, match="different task"):
        training.fit_task_operator(
            task, cross_task, dev, arm=S2SArm.T16, config=_config()
        )
    test_case = next(task.iter_cases("test"))
    leaked_dev = (*dev[:-1], test_case)
    with pytest.raises(training.SWM0WS2STrainingError, match="leakage"):
        training.fit_task_operator(
            task, train, leaked_dev, arm=S2SArm.T16, config=_config()
        )


def test_nonfinite_training_fails_closed(task, complete_cases):
    train, dev = complete_cases
    with pytest.raises(training.SWM0WS2STrainingError, match="non-finite"):
        training.fit_task_operator(
            task,
            train,
            dev,
            arm=S2SArm.T16,
            config=_config(
                max_updates=1,
                learning_rate=float.fromhex("0x1.fffffffffffffp+1023"),
            ),
        )


def test_receipts_bind_task_architecture_data_loss_history_and_best_state(task, complete_cases):
    train, dev = complete_cases
    model = training.fit_task_operator(
        task, train, dev, arm=S2SArm.T16, config=_config()
    )
    receipt = model.optimization
    assert receipt.task is task
    assert receipt.dataset_schema_sha256 == training.DATASET_SCHEMA_SHA256
    assert receipt.train_dataset_sha256 != receipt.dev_dataset_sha256
    assert receipt.loss_definition_sha256 == training._loss_definition_sha256(
        receipt.stratum_loss_receipts
    )
    assert receipt.history_entry_count == 1
    assert receipt.receipt_sha256 == training.canonical_sha256(receipt.unsigned())
    assert not any("test_dataset" in key or "test_loss" in key for key in receipt.unsigned())


def test_receipt_task_and_parameter_tampering_fail_closed(task, complete_cases):
    train, dev = complete_cases
    model = training.fit_task_operator(
        task, train, dev, arm=S2SArm.T16, config=_config()
    )
    receipt = model.optimization
    with pytest.raises(training.SWM0WS2STrainingError, match="best losses"):
        replace(receipt, best_dev_loss=receipt.best_dev_loss + 1.0)

    other = generate_task(external_seed=b"q" * 32)
    with pytest.raises(training.SWM0WS2STrainingError, match="task bindings"):
        replace(receipt, task=other)

    forged_values = {
        name: getattr(receipt, name)
        for name in receipt.__dataclass_fields__
        if name != "receipt_sha256"
    }
    forged_values["initial_parameters_sha256"] = "a" * 64
    forged_hash = training.canonical_sha256(
        training._optimization_unsigned_payload(forged_values)
    )
    with pytest.raises(training.SWM0WS2STrainingError, match="initialization drifted"):
        training.S2SOptimizationReceipt(
            **forged_values, receipt_sha256=forged_hash
        )

    dataset_forgery = {
        name: getattr(receipt, name)
        for name in receipt.__dataclass_fields__
        if name != "receipt_sha256"
    }
    dataset_forgery["train_dataset_sha256"] = "b" * 64
    dataset_forgery_hash = training.canonical_sha256(
        training._optimization_unsigned_payload(dataset_forgery)
    )
    with pytest.raises(training.SWM0WS2STrainingError, match="dataset hashes"):
        training.S2SOptimizationReceipt(
            **dataset_forgery, receipt_sha256=dataset_forgery_hash
        )

    negative_zero_values = {
        name: getattr(receipt, name)
        for name in receipt.__dataclass_fields__
        if name != "receipt_sha256"
    }
    negative_zero_values["best_dev_loss"] = -0.0
    negative_zero_hash = training.canonical_sha256(
        training._optimization_unsigned_payload(negative_zero_values)
    )
    with pytest.raises(training.SWM0WS2STrainingError, match="non-negative"):
        training.S2SOptimizationReceipt(
            **negative_zero_values, receipt_sha256=negative_zero_hash
        )

    parameters = {name: value.copy() for name, value in model.parameters.items()}
    parameters["out_b"][0, 0] = -0.0
    with pytest.raises(training.SWM0WS2STrainingError, match="best-state"):
        training.LearnedS2SOperator(
            arm=model.arm,
            config=model.config,
            parameters=parameters,
            optimization=receipt,
        )


def test_exact_nominal_config_and_arm_boundaries_reject_aliases(task, complete_cases):
    class StringAlias(str):
        pass

    for field, value in (
        ("seed", True),
        ("max_updates", True),
        ("learning_rate", 1),
        ("beta1", np.float64(0.9)),
        ("patience", 1.0),
        ("min_delta", -0.0),
    ):
        with pytest.raises(training.SWM0WS2STrainingError):
            training.S2STrainingConfig(**{field: value})
    train, dev = complete_cases
    with pytest.raises(training.SWM0WS2STrainingError, match="unsupported"):
        training.fit_task_operator(
            task,
            train,
            dev,
            arm=StringAlias("T16"),
            config=_config(),
        )


def test_stratum_receipt_tampering_is_rejected(task, complete_cases):
    train, _ = complete_cases
    receipt = training._build_stratum_loss_receipts(train)[0]
    with pytest.raises(training.SWM0WS2STrainingError, match="exact train statistics"):
        replace(
            receipt,
            inverse_variance_weight=receipt.inverse_variance_weight * 1.0001,
        )
    with pytest.raises(training.SWM0WS2STrainingError, match="inconsistent"):
        replace(
            receipt,
            centered_sum_squares_numerator=receipt.centered_sum_squares_numerator + 1,
        )


def test_full_history_derives_checkpoint_clipping_and_termination(task, complete_cases):
    train, dev = complete_cases
    model = training.fit_task_operator(
        task,
        train,
        dev,
        arm=S2SArm.T16,
        config=_config(max_updates=1, learning_rate=1.0e-4),
    )
    receipt = model.optimization
    assert tuple(entry.update for entry in receipt.history) == (0, 1)
    assert receipt.history[0].parameters_sha256 == receipt.initial_parameters_sha256
    assert receipt.history[1].parameters_sha256 == receipt.best_parameters_sha256
    assert receipt.history_sha256 == training._history_sha256(receipt.history)
    assert receipt.clipped_update_count == sum(
        int(entry.clipped) for entry in receipt.history[1:]
    )
    assert receipt.termination_reason is training.TerminationReason.MAX_UPDATES

    forged_values = {
        name: getattr(receipt, name)
        for name in receipt.__dataclass_fields__
        if name != "receipt_sha256"
    }
    forged_values["termination_reason"] = training.TerminationReason.PATIENCE
    forged_hash = training.canonical_sha256(
        training._optimization_unsigned_payload(forged_values)
    )
    with pytest.raises(training.SWM0WS2STrainingError, match="termination"):
        training.S2SOptimizationReceipt(
            **forged_values, receipt_sha256=forged_hash
        )


def test_learned_wrapper_recomputes_best_losses_from_task_and_state(task, complete_cases):
    train, dev = complete_cases
    model = training.fit_task_operator(
        task, train, dev, arm=S2SArm.T16, config=_config()
    )
    receipt = model.optimization
    original = receipt.history[0]
    forged_entry = replace(
        original,
        train_loss=original.train_loss + 1.0,
        dev_loss=original.dev_loss + 1.0,
    )
    forged_values = {
        name: getattr(receipt, name)
        for name in receipt.__dataclass_fields__
        if name != "receipt_sha256"
    }
    forged_values.update(
        history=(forged_entry,),
        best_train_loss=forged_entry.train_loss,
        best_dev_loss=forged_entry.dev_loss,
        history_sha256=training._history_sha256((forged_entry,)),
    )
    forged_receipt = training.S2SOptimizationReceipt(
        **forged_values,
        receipt_sha256=training.canonical_sha256(
            training._optimization_unsigned_payload(forged_values)
        ),
    )
    with pytest.raises(training.SWM0WS2STrainingError, match="best-state losses"):
        training.LearnedS2SOperator(
            arm=model.arm,
            config=model.config,
            parameters=model.parameters,
            optimization=forged_receipt,
        )


def test_deterministic_replay_verifies_real_trace_and_rejects_forged_provenance(
    task, complete_cases
):
    train, dev = complete_cases
    model = training.fit_task_operator(
        task,
        train,
        dev,
        arm=S2SArm.T16,
        config=_config(max_updates=1, learning_rate=1.0e-4),
    )
    replay = training.replay_optimization(model)
    assert replay.state_sha256 == model.state_sha256
    assert replay.optimization.canonical() == model.optimization.canonical()

    receipt = model.optimization
    changed_entry = replace(
        receipt.history[1], gradient_norm=receipt.history[1].gradient_norm * 0.5
    )
    assert changed_entry.clipped is False
    changed_history = (receipt.history[0], changed_entry)
    forged_values = {
        name: getattr(receipt, name)
        for name in receipt.__dataclass_fields__
        if name != "receipt_sha256"
    }
    forged_values.update(
        history=changed_history,
        history_sha256=training._history_sha256(changed_history),
    )
    forged_receipt = training.S2SOptimizationReceipt(
        **forged_values,
        receipt_sha256=training.canonical_sha256(
            training._optimization_unsigned_payload(forged_values)
        ),
    )
    committed_but_unverified = training.LearnedS2SOperator(
        arm=model.arm,
        config=model.config,
        parameters=model.parameters,
        optimization=forged_receipt,
    )
    with pytest.raises(training.SWM0WS2STrainingError, match="receipt replay mismatch"):
        training.replay_optimization(committed_but_unverified)
