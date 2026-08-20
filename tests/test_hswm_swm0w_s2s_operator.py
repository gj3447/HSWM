from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import itertools
import json
import math

import numpy as np
import pytest

from hswm.experiments import swm0w_s2s_operator as operator
from hswm.experiments import swm0w_s2s_worlds as worlds


SEED = b"swm0w-s2s-operator-focused-public-seed-v1"


@pytest.fixture(scope="module")
def task() -> worlds.TaskSpecV1:
    return worlds.generate_task(external_seed=SEED)


@pytest.fixture(scope="module")
def domain(task: worlds.TaskSpecV1):
    cases = tuple(task.iter_cases())
    presweep = operator.compile_model_worlds(tuple(case.world for case in cases))
    targets = operator.compile_case_target_batch(cases)
    return cases, presweep, targets


def _independent_member_action(array: np.ndarray, swaps: tuple[bool, ...]) -> np.ndarray:
    result = np.asarray(array).copy()
    role_axis = result.ndim - 3
    member_axis = result.ndim - 2
    for role, swap in enumerate(swaps):
        if swap:
            left = [slice(None)] * result.ndim
            right = [slice(None)] * result.ndim
            left[role_axis], left[member_axis] = role, 0
            right[role_axis], right[member_axis] = role, 1
            first = result[tuple(left)].copy()
            result[tuple(left)] = result[tuple(right)]
            result[tuple(right)] = first
    return result


def _independent_role_cycle(array: np.ndarray, cycle: tuple[int, ...]) -> np.ndarray:
    result = np.empty_like(array)
    role_axis = array.ndim - 3
    for source, destination in enumerate(cycle):
        source_index = [slice(None)] * array.ndim
        destination_index = [slice(None)] * array.ndim
        source_index[role_axis] = source
        destination_index[role_axis] = destination
        result[tuple(destination_index)] = array[tuple(source_index)]
    return result


def _independent_inverse_cycle(array: np.ndarray, cycle: tuple[int, ...]) -> np.ndarray:
    result = np.empty_like(array)
    role_axis = array.ndim - 3
    for source, destination in enumerate(cycle):
        source_index = [slice(None)] * array.ndim
        destination_index = [slice(None)] * array.ndim
        source_index[role_axis] = source
        destination_index[role_axis] = destination
        result[tuple(source_index)] = array[tuple(destination_index)]
    return result


def _independent_t_or_p_forward(
    model: operator.S2SOperator, x: np.ndarray
) -> np.ndarray:
    result = np.empty((3, 2, 2), dtype=np.float64)
    phi, psi = model.parameters["phi_w"], model.parameters["psi_w"]
    encoded = np.empty((3, 2, phi.shape[-1]), dtype=np.float64)
    source = np.empty_like(encoded)
    for role, member in itertools.product(range(3), range(2)):
        encoded[role, member] = x[role, member] @ phi[role]
        source[role, member] = x[role, member] @ psi[role]
    for role, member, channel in itertools.product(range(3), range(2), range(2)):
        u = encoded[role, member]
        leaves = []
        for source_role in range(3):
            leaves.append(
                source[role, 1 - member]
                if source_role == role
                else source[source_role, 0] + source[source_role, 1]
            )
        value = float(model.parameters["unary_w"][role, channel] @ u)
        for source_role in range(3):
            value += float(
                model.parameters["pair_w"][role, source_role, channel]
                @ (u * leaves[source_role])
            )
        if model.arm is operator.S2SArm.T16:
            value += float(
                model.parameters["q_w"][role, channel]
                @ (u * leaves[0] * leaves[1] * leaves[2])
            )
        result[role, member, channel] = value + model.parameters["out_b"][
            role, channel
        ]
    return result


def _independent_ds_forward(model: operator.S2SOperator, x: np.ndarray) -> np.ndarray:
    summaries = []
    for role in range(3):
        members = []
        for member in range(2):
            learned = np.tanh(
                x[role, member] @ model.parameters["eta_w"][role]
                + model.parameters["eta_b"][role]
            )
            members.append(np.concatenate((x[role, member], learned)))
        summaries.append(members[0] + members[1])
    result = np.empty((3, 2, 2), dtype=np.float64)
    codes = ((1.0, 0.0), (0.0, 1.0), (-1.0, -1.0))
    for role, member in itertools.product(range(3), range(2)):
        features = np.concatenate((x[role, member], *summaries, codes[role]))
        hidden1 = np.tanh(
            features @ model.parameters["hidden1_w"] + model.parameters["hidden1_b"]
        )
        hidden2 = np.tanh(
            hidden1 @ model.parameters["hidden2_w"] + model.parameters["hidden2_b"]
        )
        result[role, member] = (
            hidden2 @ model.parameters["out_w"] + model.parameters["out_b"]
        )
    return result


def test_exact_parameter_schemas_counts_and_compute_disclosure() -> None:
    expected = {
        operator.S2SArm.T16: {
            "phi_w": (3, 4, 16),
            "psi_w": (3, 4, 16),
            "unary_w": (3, 2, 16),
            "pair_w": (3, 3, 2, 16),
            "q_w": (3, 2, 16),
            "out_b": (3, 2),
        },
        operator.S2SArm.P_CAP18: {
            "phi_w": (3, 4, 18),
            "psi_w": (3, 4, 18),
            "unary_w": (3, 2, 18),
            "pair_w": (3, 3, 2, 18),
            "out_b": (3, 2),
        },
        operator.S2SArm.DS870: {
            "eta_w": (3, 4, 4),
            "eta_b": (3, 4),
            "hidden1_w": (30, 14),
            "hidden1_b": (14,),
            "hidden2_w": (14, 22),
            "hidden2_b": (22,),
            "out_w": (22, 2),
            "out_b": (2,),
        },
    }
    for arm, schema in expected.items():
        assert dict(operator.parameter_shapes(arm)) == schema
        assert sum(math.prod(shape) for shape in schema.values()) == 870
        assert operator.parameter_count(arm) == 870
        receipt = operator.architecture_receipt(arm)
        assert receipt.parameter_count == 870
        assert receipt.receipt_sha256 == operator.canonical_sha256(receipt.unsigned())

    # Independent arithmetic count for the exact implemented (non-reusing) DAG.
    t16 = operator.architecture_receipt(operator.S2SArm.T16).operations
    pcap = operator.architecture_receipt(operator.S2SArm.P_CAP18).operations
    ds = operator.architecture_receipt(operator.S2SArm.DS870).operations
    t16_dense = 2 * 6 * 4 * 16 + 6 * 2 * 16 + 6 * 3 * 2 * 16 + 6 * 2 * 16
    assert (t16.scalar_multiplications, t16.scalar_additions) == (
        t16_dense + 6 * 3 * 16 + 6 * 3 * 16,
        1_584,
    )
    pcap_dense = 2 * 6 * 4 * 18 + 6 * 2 * 18 + 6 * 3 * 2 * 18
    assert (pcap.scalar_multiplications, pcap.scalar_additions) == (
        pcap_dense + 6 * 3 * 18,
        1_566,
    )
    assert (ds.scalar_multiplications, ds.scalar_additions, ds.tanh_evaluations) == (
        6 * 4 * 4 + 6 * (30 * 14 + 14 * 22 + 22 * 2),
        4_752,
        6 * 4 + 6 * 14 + 6 * 22,
    )
    assert ds.scalar_operation_proxy > t16.scalar_operation_proxy
    assert "HIGHER_COMPUTE_THAN_T16" in operator.architecture_receipt(
        operator.S2SArm.DS870
    ).compute_disclosure


def test_compilers_are_exact_finite_model_evaluator_boundaries(task) -> None:
    case = task.case((0, 4, 1, 3, 2, 4))
    model = operator.compile_model_world(case.world)
    targets = operator.compile_case_targets(case)
    assert model.shape == (3, 2, 4)
    assert targets.shape == (3, 2, 2)
    assert model.dtype == targets.dtype == np.float64
    assert not model.flags.writeable and not targets.flags.writeable
    assert model.tolist() == [
        [[1.0, 0.0, 0.0, 0.0], [-1.0, -1.0, -1.0, -1.0]],
        [[0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
        [[0.0, 0.0, 1.0, 0.0], [-1.0, -1.0, -1.0, -1.0]],
    ]
    independently_scaled = np.asarray(case.target_numerators).reshape(3, 2, 2) / 32768.0
    assert np.array_equal(targets, independently_scaled)


def test_constructive_q_witness_is_exact_on_all_15625_worlds(task, domain) -> None:
    cases, presweep, targets = domain
    assert len(cases) == 5**6 == 15_625
    witness = operator.construct_q_witness(task)
    prediction = witness.forward(presweep)
    assert np.array_equal(prediction, targets)
    assert witness.origin is operator.ParameterOrigin.EVALUATOR_ONLY_CONSTRUCTIVE_Q_WITNESS
    assert witness.evaluator_family_sha256 == operator.EVALUATOR_FAMILY_SHA256
    assert not hasattr(witness, "evaluator_task_sha256")
    assert witness.learned is False
    assert operator.SCIENTIFIC_STATUS == "ENGINEERING_CORE_ONLY_UNJUDGED"

    # The evaluator construction has only four active hidden coordinates.
    assert np.count_nonzero(witness.parameters["unary_w"]) == 0
    assert np.count_nonzero(witness.parameters["pair_w"]) == 0
    assert np.count_nonzero(witness.parameters["out_b"]) == 0
    assert np.count_nonzero(witness.parameters["q_w"]) == 12
    assert np.count_nonzero(witness.parameters["phi_w"][:, :, 4:]) == 0
    assert np.count_nonzero(witness.parameters["psi_w"][:, :, 4:]) == 0


@pytest.mark.parametrize("arm", tuple(operator.S2SArm))
def test_all_eight_s2_cubed_actions_are_equivariant_for_every_arm(arm) -> None:
    model = operator.initialize_operator(arm, seed=17)
    sample = (
        (0, 1, 2, 3, 4, 0),
        (4, 3, 2, 1, 0, 4),
        (1, 1, 3, 0, 2, 4),
        (2, 4, 0, 0, 3, 1),
    )
    for values in sample:
        presweep = operator.compile_model_world(worlds.ModelWorldV1(values))
        baseline = model.forward(presweep)
        for action in worlds.ALL_MEMBER_PERMUTATIONS:
            moved = _independent_member_action(presweep, action.swaps)
            expected = _independent_member_action(baseline, action.swaps)
            actual = model.forward(moved)
            np.testing.assert_allclose(actual, expected, rtol=2e-14, atol=2e-14)


@pytest.mark.parametrize("arm", tuple(operator.S2SArm))
def test_vectorized_forward_matches_an_independent_scalar_equation(arm) -> None:
    model = operator.initialize_operator(arm, seed=23)
    x = np.asarray(
        (
            ((0.5, -1.0, 0.25, 2.0), (-0.75, 0.0, 1.5, -0.5)),
            ((1.25, 0.5, -0.5, 0.0), (0.0, -1.5, 0.75, 0.25)),
            ((-0.25, 2.0, 0.5, -1.0), (1.0, -0.5, -0.75, 1.5)),
        ),
        dtype=np.float64,
    )
    expected = (
        _independent_ds_forward(model, x)
        if arm is operator.S2SArm.DS870
        else _independent_t_or_p_forward(model, x)
    )
    np.testing.assert_allclose(model.forward(x), expected, rtol=5e-14, atol=5e-14)


def test_ds_fixed_representation_is_exhaustively_injective_on_recipient_quotient(
    domain,
) -> None:
    cases, presweep, _ = domain
    representation = operator.ds_fixed_recipient_representation(presweep)
    assert representation.shape == (5**6, 3, 2, 18)
    by_signature: dict[tuple[float, ...], tuple[object, ...]] = {}
    by_quotient: dict[tuple[object, ...], tuple[float, ...]] = {}
    for index, case in enumerate(cases):
        values = case.world.raw_values
        role_multisets = tuple(
            tuple(sorted(values[2 * role : 2 * role + 2])) for role in range(3)
        )
        for role in range(3):
            for member in range(2):
                quotient = (
                    role,
                    values[2 * role + member],
                    values[2 * role + 1 - member],
                    role_multisets[(role + 1) % 3],
                    role_multisets[(role + 2) % 3],
                )
                signature = tuple(representation[index, role, member])
                assert by_signature.setdefault(signature, quotient) == quotient
                assert by_quotient.setdefault(quotient, signature) == signature
    assert len(by_signature) == len(by_quotient) == 3 * 25 * 15 * 15


@pytest.mark.parametrize("arm", tuple(operator.S2SArm))
def test_forward_uses_immutable_presweep_and_is_batch_order_independent(arm) -> None:
    model = operator.initialize_operator(arm, seed=29)
    worlds_batch = tuple(
        worlds.ModelWorldV1(values)
        for values in (
            (0, 1, 2, 3, 4, 0),
            (4, 0, 3, 1, 2, 4),
            (2, 2, 1, 4, 0, 3),
            (1, 3, 0, 4, 2, 2),
        )
    )
    presweep = operator.compile_model_worlds(worlds_batch)
    before = presweep.tobytes()
    normal = model.forward(presweep)
    reverse = model.forward(np.ascontiguousarray(presweep[::-1]))[::-1]
    assert presweep.tobytes() == before
    np.testing.assert_allclose(normal, reverse, rtol=2e-14, atol=2e-14)
    individually = np.stack([model.forward(row) for row in presweep])
    np.testing.assert_allclose(normal, individually, rtol=2e-14, atol=2e-14)
    assert not normal.flags.writeable


def test_pcap_has_no_q_and_rejects_q_intervention() -> None:
    model = operator.initialize_operator(operator.S2SArm.P_CAP18, seed=4)
    assert "q_w" not in model.parameters
    assert set(model.parameters) == set(operator.parameter_shapes(model.arm))
    with pytest.raises(operator.SWM0WS2SOperatorError, match="T16"):
        operator.remove_q(model)


def test_q_remove_tamper_and_restore_are_exact(task) -> None:
    world = worlds.ModelWorldV1((0, 1, 2, 3, 4, 0))
    model = operator.construct_q_witness(task)
    before_prediction = model.predict_world(world)
    before_parameter_bytes = {
        name: value.tobytes() for name, value in model.parameters.items()
    }
    ablated, receipt = operator.remove_q(model)
    assert receipt.removed_value_count == 96
    assert receipt.base_state_sha256 == model.state_sha256
    assert receipt.ablated_state_sha256 == ablated.state_sha256
    assert ablated.intervention == "Q_REMOVED"
    assert ablated.parameters["q_w"].tobytes() == np.zeros((3, 2, 16)).tobytes()
    assert np.array_equal(ablated.predict_world(world), np.zeros((3, 2, 2)))

    class TextAlias(str):
        pass

    with pytest.raises(operator.SWM0WS2SOperatorError, match="intervention"):
        replace(ablated, intervention=TextAlias("Q_REMOVED"))

    changed = list(receipt.removed_values_hex)
    changed[0] = (float.fromhex(changed[0]) + 1.0).hex()
    with pytest.raises(operator.SWM0WS2SOperatorError):
        replace(receipt, removed_values_hex=tuple(changed))
    other, _ = operator.remove_q(operator.initialize_operator(operator.S2SArm.T16, seed=99))
    with pytest.raises(operator.SWM0WS2SOperatorError, match="does not bind"):
        operator.restore_q(other, receipt)

    restored = operator.restore_q(ablated, receipt)
    assert restored.state_sha256 == model.state_sha256
    assert restored.parameters_sha256 == model.parameters_sha256
    assert restored.predict_world(world).tobytes() == before_prediction.tobytes()
    assert {
        name: value.tobytes() for name, value in restored.parameters.items()
    } == before_parameter_bytes


def test_within_role_broadcast_and_physical_cycle_mapping_are_exact() -> None:
    predictions = np.arange(12, dtype=np.float64).reshape(3, 2, 2)
    broadcast = operator.within_role_broadcast(predictions)
    expected = predictions.mean(axis=1, keepdims=True)
    expected = np.broadcast_to(expected, predictions.shape)
    assert np.array_equal(broadcast, expected)
    assert all(np.array_equal(broadcast[role, 0], broadcast[role, 1]) for role in range(3))

    presweep = np.arange(24, dtype=np.float64).reshape(3, 2, 4)
    for cycle in worlds.ROLE_CYCLES:
        moved = operator.apply_physical_role_cycle(presweep, cycle)
        assert np.array_equal(moved, _independent_role_cycle(presweep, cycle))
        moved_outputs = _independent_role_cycle(predictions, cycle)
        restored = operator.inverse_map_role_cycle_outputs(moved_outputs, cycle)
        assert np.array_equal(restored, predictions)


def test_both_role_cycle_evaluations_keep_parameters_fixed_and_restore_outputs() -> None:
    model = operator.initialize_operator(operator.S2SArm.T16, seed=31)
    presweep = operator.compile_model_world(worlds.ModelWorldV1((0, 1, 2, 3, 4, 0)))
    state_before = model.state_sha256
    results = operator.evaluate_both_role_cycles(model, presweep)
    assert tuple(cycle for cycle, _ in results) == worlds.ROLE_CYCLES
    for cycle, prediction in results:
        manual = _independent_inverse_cycle(
            model.forward(_independent_role_cycle(presweep, cycle)), cycle
        )
        assert np.array_equal(prediction, manual)
    assert model.state_sha256 == state_before


def test_r2_is_per_role_channel_and_worst_stratum_is_not_hidden() -> None:
    targets = np.arange(48, dtype=np.float64).reshape(4, 3, 2, 2)
    predictions = targets.copy()
    predictions[:, 2, :, 1] += np.asarray(((1.0, -2.0),) * 4)
    score = operator.stratified_r2(predictions, targets)
    assert score.world_count == 4
    for role, channel in itertools.product(range(3), range(2)):
        truth = targets[:, role, :, channel].reshape(-1)
        estimate = predictions[:, role, :, channel].reshape(-1)
        expected = 1.0 - np.sum((truth - estimate) ** 2) / np.sum(
            (truth - truth.mean()) ** 2
        )
        assert score.values[role][channel] == expected
    assert score.worst_role == "r2"
    assert score.worst_channel == "c1"
    assert score.worst_r2 == score.values[2][1] < 1.0
    assert score.receipt_sha256 == operator.canonical_sha256(score.unsigned())
    assert score.predictions_sha256 != score.targets_sha256
    assert score.canonical()["claim_boundary"] == "DIAGNOSTIC_ONLY_NO_EFFICACY_VERDICT"


def test_deterministic_tensor_local_initialization_and_content_hash() -> None:
    first = operator.initialize_operator(operator.S2SArm.T16, seed=73)
    replay = operator.initialize_operator(operator.S2SArm.T16, seed=73)
    other = operator.initialize_operator(operator.S2SArm.T16, seed=74)
    assert first.state_sha256 == replay.state_sha256
    assert first.parameters_sha256 == replay.parameters_sha256
    assert all(
        left.tobytes() == replay.parameters[name].tobytes()
        for name, left in first.parameters.items()
    )
    assert first.parameters_sha256 != other.parameters_sha256

    # Independently replay one tensor's local seed; no preceding draw can affect it.
    shape = (3, 4, 16)
    payload = json.dumps(
        [operator.INITIALIZATION_DOMAIN, 73, "phi_w", list(shape)],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    material = hashlib.sha256(payload.encode()).hexdigest()
    rng = np.random.Generator(np.random.PCG64(int(material[:16], 16)))
    limit = math.sqrt(6.0 / (4 + 16))
    expected = rng.uniform(-limit, limit, size=shape).astype(np.float64)
    assert first.parameters["phi_w"].tobytes() == expected.tobytes()

    with pytest.raises(TypeError):
        first.parameters["phi_w"] = expected
    with pytest.raises(ValueError):
        first.parameters["phi_w"].setflags(write=True)

    forged = {name: value.copy() for name, value in first.parameters.items()}
    forged["phi_w"][0, 0, 0] += 0.125
    with pytest.raises(operator.SWM0WS2SOperatorError, match="claimed origin"):
        replace(first, parameters=forged)


def test_constructive_origin_rejects_arbitrary_finite_parameter_forgery(task) -> None:
    witness = operator.construct_q_witness(task)
    forged = {name: value.copy() for name, value in witness.parameters.items()}
    forged["pair_w"][0, 0, 0, 0] = 0.25
    with pytest.raises(operator.SWM0WS2SOperatorError, match="claimed origin"):
        replace(witness, parameters=forged)


def test_exact_type_dtype_shape_nan_and_receipt_failures(task) -> None:
    model = operator.initialize_operator(operator.S2SArm.T16, seed=1)
    presweep = operator.compile_model_world(worlds.ModelWorldV1((0, 1, 2, 3, 4, 0)))
    for bad in (
        presweep.astype(np.float32),
        presweep.tolist(),
        np.zeros((6, 4), dtype=np.float64),
        np.full((3, 2, 4), np.nan, dtype=np.float64),
    ):
        with pytest.raises(operator.SWM0WS2SOperatorError):
            model.forward(bad)
    with pytest.raises(operator.SWM0WS2SOperatorError):
        operator.initialize_operator(operator.S2SArm.T16, seed=True)
    with pytest.raises(operator.SWM0WS2SOperatorError):
        operator.initialize_operator("UNKNOWN", seed=1)

    parameters = {name: value.copy() for name, value in model.parameters.items()}
    parameters["phi_w"] = parameters["phi_w"].astype(np.float32)
    with pytest.raises(operator.SWM0WS2SOperatorError, match="float64"):
        replace(model, parameters=parameters)
    parameters = {name: value.copy() for name, value in model.parameters.items()}
    parameters["phi_w"][0, 0, 0] = np.nan
    with pytest.raises(operator.SWM0WS2SOperatorError, match="non-finite"):
        replace(model, parameters=parameters)
    parameters = {name: value.copy() for name, value in model.parameters.items()}
    parameters.pop("q_w")
    with pytest.raises(operator.SWM0WS2SOperatorError, match="names"):
        replace(model, parameters=parameters)

    class ForgedWorld(worlds.ModelWorldV1):
        pass

    class ForgedCase(worlds.EvaluatorCaseV1):
        pass

    case = task.case((0, 1, 2, 3, 4, 0))
    with pytest.raises(operator.SWM0WS2SOperatorError, match="exact ModelWorldV1"):
        operator.compile_model_world(ForgedWorld(case.world.raw_values))
    forged_case = ForgedCase(case.world, case.split, case.target_numerators)
    with pytest.raises(operator.SWM0WS2SOperatorError, match="exact EvaluatorCaseV1"):
        operator.compile_case_targets(forged_case)
    with pytest.raises(operator.SWM0WS2SOperatorError):
        replace(operator.architecture_receipt(operator.S2SArm.T16), parameter_count=869)
    with pytest.raises(operator.SWM0WS2SOperatorError):
        replace(operator.architecture_receipt(operator.S2SArm.T16), parameter_count=870.0)
    receipt = operator.architecture_receipt(operator.S2SArm.T16)
    aliased_schema = list(receipt.parameter_schema)
    aliased_schema[0] = (aliased_schema[0][0], (3, 4, 16.0))
    with pytest.raises(operator.SWM0WS2SOperatorError, match="schema drifted"):
        replace(receipt, parameter_schema=tuple(aliased_schema))
    with pytest.raises(FrozenInstanceError):
        operator.architecture_receipt(operator.S2SArm.T16).parameter_count = 869


def test_r2_and_cycle_boundaries_reject_invalid_inputs() -> None:
    values = np.zeros((2, 3, 2, 2), dtype=np.float64)
    with pytest.raises(operator.SWM0WS2SOperatorError, match="positive variance"):
        operator.stratified_r2(values, values)
    with pytest.raises(operator.SWM0WS2SOperatorError, match="match exactly"):
        operator.stratified_r2(
            np.zeros((2, 3, 2, 2), dtype=np.float64),
            np.zeros((3, 3, 2, 2), dtype=np.float64),
        )
    with pytest.raises(operator.SWM0WS2SOperatorError, match="registered"):
        operator.apply_physical_role_cycle(
            np.zeros((3, 2, 4), dtype=np.float64), (0, 1, 2)
        )
    with pytest.raises(operator.SWM0WS2SOperatorError):
        operator.within_role_broadcast(np.zeros((3, 2, 2), dtype=np.float32))
