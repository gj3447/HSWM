from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import inspect
import itertools
import math
from pathlib import Path

import numpy as np
import pytest

from hswm.experiments import swm0w_operator as operator
from hswm.experiments import swm0w_task_family as task_core
from hswm.experiments import swm0w_worlds as worlds


SEED = b"swm0w-learned-operator-tests-v1"
TASK_SEED = b"swm0w-operator-task-adapter-tests-v1-" + b"T" * 40
SMOKE_CONFIG = operator.TrainingConfig(
    width=16,
    seed=7,
    epochs=10,
    batch_size=64,
    patience=4,
)


@pytest.fixture(scope="module")
def bundle() -> worlds.SWM0WBundleV1:
    return worlds.generate_bundle(seed_preimage=SEED)


@pytest.fixture(scope="module")
def smoke_cases(bundle):
    return (
        worlds.cases_from_split(bundle, "train")[:384],
        worlds.cases_from_split(bundle, "dev")[:160],
        worlds.cases_from_split(bundle, "test")[:160],
    )


@pytest.fixture(scope="module")
def learned_triple(smoke_cases) -> operator.LearnedSWM0WOperator:
    train, dev, _ = smoke_cases
    return operator.fit_operator(train, dev, config=SMOKE_CONFIG)


@pytest.fixture(scope="module")
def streamed_task() -> task_core.StreamedTaskV1:
    return task_core.build_task_from_external_seed(TASK_SEED)


@pytest.fixture(scope="module")
def streamed_cases(streamed_task):
    return (
        task_core.evaluator_cases_from_split(streamed_task, "train")[:96],
        task_core.evaluator_cases_from_split(streamed_task, "dev")[:48],
        task_core.evaluator_cases_from_split(streamed_task, "test")[:48],
    )


def _uid(prefix: str, index: int, domain: str) -> str:
    digest = hashlib.sha256(f"{index}:{domain}".encode("ascii")).hexdigest()[:24]
    return f"swm0w_{prefix}_{digest}"


def _reidentify(
    cases: tuple[worlds.EvaluatorCaseV1, ...],
) -> tuple[worlds.EvaluatorCaseV1, ...]:
    result = []
    for index, case in enumerate(cases):
        result.append(
            replace(
                case,
                case_uid=_uid("case", index, "case"),
                world_uid=_uid("world", index, "world"),
                incidence_uids=tuple(
                    (role, _uid("inc", index, f"incidence:{role}"))
                    for role in worlds.ROLES
                ),
            )
        )
    return tuple(reversed(result))


def _reidentify_streamed_cases(cases):
    result = []
    for index, case in enumerate(cases):
        digest = hashlib.sha256(
            f"{case.split}:{index}:streamed-case".encode("ascii")
        ).hexdigest()[:24]
        unsigned = case.unsigned_canonical()
        unsigned["case_uid"] = f"swm0wt_case_{digest}"
        result.append(
            replace(
                case,
                case_uid=unsigned["case_uid"],
                receipt_sha256=task_core.canonical_sha256(unsigned),
            )
        )
    return tuple(reversed(result))


def _permute_worlds(
    cases: tuple[worlds.EvaluatorCaseV1, ...],
) -> tuple[worlds.EvaluatorCaseV1, ...]:
    permutations = tuple(itertools.permutations(range(len(worlds.ROLES))))
    return tuple(
        replace(
            case,
            world=worlds.ModelWorldV1(
                tuple(case.world.incidences[index] for index in permutations[position % 6])
            ),
        )
        for position, case in enumerate(cases)
    )


def test_native_and_independently_compiled_typed_star_inputs_match(bundle) -> None:
    for split in bundle.splits:
        for case in split.cases:
            native = operator.native_role_input(case.world)
            star = operator.compile_typed_star_input(case.world)
            assert np.array_equal(native, star)
            assert native.dtype == star.dtype == np.float64
            assert not native.flags.writeable
            assert not star.flags.writeable

    world = bundle.for_split("test").cases[0].world
    reversed_world = worlds.ModelWorldV1(tuple(reversed(world.incidences)))
    assert np.array_equal(
        operator.compile_typed_star_input(reversed_world),
        operator.native_role_input(world),
    )
    assert len(operator.assert_typed_star_parity(reversed_world)) == 64


def test_operator_imports_only_public_model_api_and_has_no_modulo_or_oracle() -> None:
    source = Path(operator.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    world_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "hswm.experiments.swm0w_worlds"
    ]
    assert len(world_imports) == 1
    names = {alias.name for alias in world_imports[0].names}
    assert names == {
        "CASE_SCHEMA",
        "ROLES",
        "EvaluatorCaseV1",
        "ModelWorldV1",
        "RoleInputV1",
        "cases_from_split",
    }
    assert not any(name.startswith("_") for name in names)
    task_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "hswm.experiments.swm0w_task_family"
    ]
    assert len(task_imports) == 1
    task_names = {alias.name for alias in task_imports[0].names}
    assert task_names == {"CASE_SCHEMA", "TaskEvaluatorCaseV1"}
    assert not any(name.startswith("_") for name in task_names)
    assert not any(isinstance(node, ast.Mod) for node in ast.walk(tree))
    for forbidden in ("evaluate_hidden", "constructive_target", "target_table"):
        assert forbidden not in source
    assert tuple(inspect.signature(operator.LearnedSWM0WOperator.score).parameters) == (
        "self",
        "world",
    )


@pytest.mark.parametrize("arm", tuple(operator.SWM0WArm))
def test_manual_gradients_match_central_differences(arm) -> None:
    rng = np.random.Generator(np.random.PCG64(9137))
    parameters = operator._initial_parameters(arm, 2, 9137)
    inputs = rng.normal(0.0, 0.35, size=(4, len(worlds.ROLES), 2))
    targets = rng.uniform(-0.7, 0.7, size=4)
    _, cache = operator._forward(arm, parameters, inputs)
    if arm in {operator.SWM0WArm.LOWER_ORDER_PAIR, operator.SWM0WArm.ADDITIVE}:
        assert "triple" not in cache
    _, gradients = operator._loss_and_gradients(arm, parameters, inputs, targets)
    epsilon = 1.0e-6
    for name, value in parameters.items():
        numerical = np.empty_like(value)
        for index in np.ndindex(value.shape):
            original = float(value[index])
            value[index] = original + epsilon
            plus, _ = operator._forward(arm, parameters, inputs)
            plus_loss = float(np.mean((plus - targets) ** 2))
            value[index] = original - epsilon
            minus, _ = operator._forward(arm, parameters, inputs)
            minus_loss = float(np.mean((minus - targets) ** 2))
            value[index] = original
            numerical[index] = (plus_loss - minus_loss) / (2.0 * epsilon)
        assert np.allclose(gradients[name], numerical, rtol=2.0e-5, atol=2.0e-7)


def test_named_initialization_is_nested_arm_matched_and_schema_independent(
    monkeypatch,
) -> None:
    arms = (
        operator.SWM0WArm.ADDITIVE,
        operator.SWM0WArm.LOWER_ORDER_PAIR,
        operator.SWM0WArm.ROLE_TRIPLE,
        operator.SWM0WArm.TYPED_STAR_TRIPLE,
    )
    initialized = {
        arm: operator._initial_parameters(arm, 5, 23) for arm in arms
    }
    for name in ("encoder_w", "encoder_b", "unary_w", "out_b"):
        assert all(
            np.array_equal(initialized[arms[0]][name], initialized[arm][name])
            for arm in arms[1:]
        )
    assert np.array_equal(
        initialized[operator.SWM0WArm.LOWER_ORDER_PAIR]["pair_w"],
        initialized[operator.SWM0WArm.ROLE_TRIPLE]["pair_w"],
    )
    assert all(
        np.array_equal(
            initialized[operator.SWM0WArm.ROLE_TRIPLE][name],
            initialized[operator.SWM0WArm.TYPED_STAR_TRIPLE][name],
        )
        for name in initialized[operator.SWM0WArm.ROLE_TRIPLE]
    )

    baseline = operator._initial_parameters(
        operator.SWM0WArm.ROLE_TRIPLE, 5, 23
    )
    monkeypatch.setattr(operator, "OPERATOR_VERSION", "metadata-only-test/v999")
    replay = operator._initial_parameters(
        operator.SWM0WArm.ROLE_TRIPLE, 5, 23
    )
    assert all(np.array_equal(baseline[name], replay[name]) for name in baseline)


def test_small_learning_smoke_is_continuous_deterministic_and_receipted(
    learned_triple, smoke_cases
) -> None:
    train, dev, _ = smoke_cases
    model = learned_triple
    assert model.arm is operator.SWM0WArm.ROLE_TRIPLE
    assert model.parameter_count == operator.DEFAULT_ROLE_TRIPLE_PARAMETER_COUNT == 257
    assert model.config.width == 16
    assert 0 < model.optimization.best_epoch <= model.optimization.stopped_epoch <= 10
    assert model.optimization.typed_star_input_parity_sha256 is not None
    assert model.optimization.receipt_sha256 == operator.canonical_sha256(
        model.optimization.unsigned()
    )
    assert model.optimization.unsigned()["schema_version"] == (
        operator.OPTIMIZATION_RECEIPT_VERSION
    )
    assert model.optimization.unsigned()["initialization_domain"] == (
        operator.INITIALIZATION_DOMAIN
    )
    assert model.optimization.unsigned()["training_order_domain"] == (
        operator.TRAINING_ORDER_DOMAIN
    )
    assert len(model.optimization.evaluator_binding_sha256) == 64
    baseline = float(
        np.mean(
            (
                np.asarray([case.target for case in dev])
                - np.mean([case.target for case in train])
            )
            ** 2
        )
    )
    assert math.isfinite(model.mean_squared_error(dev))
    assert model.mean_squared_error(dev) < baseline
    score = model.score(dev[0].world)
    assert model.predict(dev[0].world) == score
    assert isinstance(score, float)
    with pytest.raises(operator.SWM0WOperatorError, match="ModelWorldV1"):
        model.score(dev[0])


def test_normalization_uses_train_features_only(learned_triple, smoke_cases) -> None:
    train, _, _ = smoke_cases
    ordered = sorted(
        train, key=lambda case: (case.world.semantic_sha256, case.target.hex())
    )
    raw = np.stack([case.world.feature_matrix() for case in ordered]).astype(np.float64)
    expected_scale = raw.std(axis=0)
    expected_scale = np.where(expected_scale < 1.0e-12, 1.0, expected_scale)
    assert np.array_equal(learned_triple.normalizer.mean, raw.mean(axis=0))
    assert np.array_equal(learned_triple.normalizer.scale, expected_scale)
    assert learned_triple.normalizer.train_case_count == len(train)
    assert learned_triple.optimization.normalization_sha256 == (
        learned_triple.normalizer.state_sha256
    )


def test_case_order_and_evaluator_uids_cannot_change_training(
    learned_triple, smoke_cases
) -> None:
    train, dev, _ = smoke_cases
    replay = operator.fit_operator(
        _reidentify(train),
        _reidentify(dev),
        config=SMOKE_CONFIG,
    )
    assert replay.state_sha256 == learned_triple.state_sha256
    assert replay.optimization.receipt_sha256 == (
        learned_triple.optimization.receipt_sha256
    )
    for name in learned_triple.parameters:
        assert np.array_equal(replay.parameters[name], learned_triple.parameters[name])


def test_all_incidence_permutations_preserve_scores_and_training(
    learned_triple, smoke_cases
) -> None:
    train, dev, test = smoke_cases
    case = test[0]
    scores = {
        learned_triple.score(
            worlds.ModelWorldV1(tuple(case.world.incidences[index] for index in order))
        )
        for order in itertools.permutations(range(len(worlds.ROLES)))
    }
    assert scores == {learned_triple.score(case.world)}

    replay = operator.fit_operator(
        _permute_worlds(train),
        _permute_worlds(dev),
        config=SMOKE_CONFIG,
    )
    assert replay.state_sha256 == learned_triple.state_sha256


def test_typed_star_and_native_training_have_exact_parameter_parity(smoke_cases) -> None:
    train, dev, _ = smoke_cases
    config = operator.TrainingConfig(
        width=4, seed=11, epochs=2, batch_size=64, patience=2
    )
    native = operator.fit_operator(
        train[:128], dev[:64], operator.SWM0WArm.ROLE_TRIPLE, config=config
    )
    star = operator.fit_operator(
        train[:128], dev[:64], operator.SWM0WArm.TYPED_STAR_TRIPLE, config=config
    )
    assert native.optimization.initial_parameters_sha256 == (
        star.optimization.initial_parameters_sha256
    )
    assert native.optimization.history_sha256 == star.optimization.history_sha256
    assert native.optimization.typed_star_input_parity_sha256 == (
        star.optimization.typed_star_input_parity_sha256
    )
    for name in native.parameters:
        assert np.array_equal(native.parameters[name], star.parameters[name])
    assert [native.score(case.world) for case in dev[:32]] == [
        star.score(case.world) for case in dev[:32]
    ]


def test_all_controls_train_and_report_honest_non_equal_compute_counts(
    smoke_cases,
) -> None:
    train, dev, test = smoke_cases
    config = operator.TrainingConfig(
        width=4, seed=3, epochs=1, batch_size=96, patience=1
    )
    models = {
        arm: operator.fit_operator(train[:96], dev[:48], arm, config=config)
        for arm in operator.SWM0WArm
    }
    assert {arm: model.parameter_count for arm, model in models.items()} == {
        operator.SWM0WArm.ROLE_TRIPLE: 65,
        operator.SWM0WArm.TYPED_STAR_TRIPLE: 65,
        operator.SWM0WArm.LOWER_ORDER_PAIR: 61,
        operator.SWM0WArm.ADDITIVE: 49,
        operator.SWM0WArm.ROLELESS: 17,
        operator.SWM0WArm.FLAT_MLP: 53,
        operator.SWM0WArm.ROLE_AWARE_DEEPSETS: 49,
    }
    for model in models.values():
        estimate = model.operation_estimate()
        assert estimate.parameter_count == model.parameter_count
        assert estimate.scalar_operation_proxy > 0
        assert estimate.canonical()["scope"] == (
            "LEARNED_CORE_PROXY_EXCLUDES_COMPILER_NORMALIZATION_"
            "BIAS_ADDS_AND_POOL_REDUCTIONS_NOT_EQUAL_COMPUTE"
        )
    assert models[operator.SWM0WArm.ROLE_TRIPLE].operation_estimate().hadamard_multiplications == 20
    assert models[operator.SWM0WArm.ADDITIVE].operation_estimate().hadamard_multiplications == 0

    comparison = operator.compare_models(
        {
            arm: models[arm]
            for arm in (
                operator.SWM0WArm.ROLE_TRIPLE,
                operator.SWM0WArm.FLAT_MLP,
                operator.SWM0WArm.ROLE_AWARE_DEEPSETS,
            )
        },
        test[:48],
    )
    assert not comparison.novelty_claim_allowed
    assert set(dict(comparison.mean_squared_error_by_arm)) == {
        "ROLE_TRIPLE",
        "FLAT_MLP",
        "ROLE_AWARE_DEEPSETS",
    }
    assert comparison.receipt_sha256 == operator.canonical_sha256(
        comparison.unsigned()
    )
    assert set(dict(comparison.model_state_sha256_by_arm)) == {
        "ROLE_TRIPLE",
        "FLAT_MLP",
        "ROLE_AWARE_DEEPSETS",
    }
    assert len(comparison.evaluation_dataset_sha256) == 64
    assert len(comparison.evaluator_binding_sha256) == 64
    assert comparison.tie_tolerance == 1.0e-12
    assert "No novelty claim" in comparison.interpretation


def test_frozen_triple_head_remove_restore_is_bit_exact(
    learned_triple, smoke_cases
) -> None:
    _, _, test = smoke_cases
    base_scores = np.asarray([learned_triple.score(case.world) for case in test])
    removed, receipt = operator.remove_triple_head(learned_triple)
    removed_scores = np.asarray([removed.score(case.world) for case in test])
    assert removed.intervention == operator.InteractionHeadV1(worlds.ROLES)
    assert removed.state_sha256 != learned_triple.state_sha256
    assert np.all(removed.parameters["triple_w"] == 0.0)
    assert not np.array_equal(base_scores, removed_scores)
    assert receipt.receipt_sha256 == operator.canonical_sha256(receipt.unsigned())
    with pytest.raises(TypeError):
        removed.parameters["triple_w"] = np.ones(16)
    with pytest.raises(ValueError):
        removed.parameters["triple_w"][0] = 1.0
    with pytest.raises(ValueError):
        removed.parameters["triple_w"].setflags(write=True)
    with pytest.raises(ValueError):
        removed.normalizer.mean.setflags(write=True)

    restored = operator.restore_triple_head(removed, receipt)
    assert restored.state_sha256 == learned_triple.state_sha256
    assert np.array_equal(
        base_scores,
        np.asarray([restored.score(case.world) for case in test]),
    )
    with pytest.raises(operator.SWM0WOperatorError, match="receipt hash"):
        replace(receipt, removed_values_hex=("0x0.0p+0",) * 16)


@pytest.mark.parametrize(
    "roles",
    (
        ("r0",),
        ("r1",),
        ("r2",),
        ("r0", "r1"),
        ("r0", "r2"),
        ("r1", "r2"),
        ("r0", "r1", "r2"),
    ),
)
def test_generic_head_removal_is_one_equal_width_slice_and_restores_exactly(
    learned_triple, roles
) -> None:
    head = operator.InteractionHeadV1(roles)
    expected = {
        name: np.asarray(value).copy()
        for name, value in learned_triple.parameters.items()
    }
    parameter_name, row = operator._head_location(head)
    selected = expected[parameter_name] if row is None else expected[parameter_name][row]
    selected.fill(0.0)

    removed, receipt = operator.remove_interaction_head(learned_triple, head)
    assert removed.intervention == head
    assert removed.parameter_count == learned_triple.parameter_count
    assert removed.operation_estimate() == learned_triple.operation_estimate()
    assert receipt.head == head
    assert receipt.width == learned_triple.config.width
    assert receipt.removed_value_count == learned_triple.config.width
    assert all(
        np.array_equal(expected[name], removed.parameters[name])
        for name in expected
    )
    restored = operator.restore_interaction_head(removed, receipt)
    assert restored.state_sha256 == learned_triple.state_sha256
    assert all(
        np.array_equal(
            restored.parameters[name], learned_triple.parameters[name]
        )
        for name in learned_triple.parameters
    )


def test_head_selectors_and_receipts_fail_closed(
    learned_triple, smoke_cases
) -> None:
    for roles in ((), ("r0", "r0"), ("r1", "r0"), ("bad",)):
        with pytest.raises(operator.SWM0WOperatorError):
            operator.InteractionHeadV1(roles)

    removed, receipt = operator.remove_interaction_head(
        learned_triple, operator.InteractionHeadV1(("r0",))
    )
    with pytest.raises(operator.SWM0WOperatorError, match="already"):
        operator.remove_interaction_head(
            removed, operator.InteractionHeadV1(("r1",))
        )
    other_removed, _ = operator.remove_interaction_head(
        learned_triple, operator.InteractionHeadV1(("r1",))
    )
    with pytest.raises(operator.SWM0WOperatorError, match="does not bind"):
        operator.restore_interaction_head(other_removed, receipt)
    with pytest.raises(operator.SWM0WOperatorError, match="width-vector"):
        replace(receipt, removed_values_hex=list(receipt.removed_values_hex))
    with pytest.raises(operator.SWM0WOperatorError, match="canonical"):
        replace(
            receipt,
            removed_values_hex=("0x0p+0",) * receipt.width,
            receipt_sha256=operator.canonical_sha256(
                {
                    **receipt.unsigned(),
                    "removed_values_hex": ["0x0p+0"] * receipt.width,
                }
            ),
        )
    with pytest.raises(operator.SWM0WOperatorError, match="all roles"):
        operator.restore_triple_head(removed, receipt)

    train, dev, _ = smoke_cases
    additive = operator.fit_operator(
        train[:16],
        dev[:8],
        operator.SWM0WArm.ADDITIVE,
        config=operator.TrainingConfig(
            width=2, seed=4, epochs=1, batch_size=8, patience=1
        ),
    )
    with pytest.raises(operator.SWM0WOperatorError, match="unavailable"):
        operator.remove_interaction_head(
            additive, operator.InteractionHeadV1(("r0", "r1"))
        )

    class HostileOperator(operator.LearnedSWM0WOperator):
        @property
        def state_sha256(self):
            return "0" * 64

    hostile = HostileOperator(
        arm=learned_triple.arm,
        config=learned_triple.config,
        normalizer=learned_triple.normalizer,
        parameters=learned_triple.parameters,
        optimization=learned_triple.optimization,
    )
    with pytest.raises(operator.SWM0WOperatorError, match="learned operator"):
        operator.remove_interaction_head(
            hostile, operator.InteractionHeadV1(("r0",))
        )
    hostile_removed = HostileOperator(
        arm=removed.arm,
        config=removed.config,
        normalizer=removed.normalizer,
        parameters=removed.parameters,
        optimization=removed.optimization,
        intervention=removed.intervention,
    )
    with pytest.raises(operator.SWM0WOperatorError, match="exact receipt"):
        operator.restore_interaction_head(hostile_removed, receipt)
    with pytest.raises(operator.SWM0WOperatorError, match="does not match"):
        operator.compare_models(
            {operator.SWM0WArm.ROLE_TRIPLE: hostile}, smoke_cases[2][:2]
        )


def test_streamed_task_envelopes_train_evaluate_and_never_enter_model(
    streamed_cases, monkeypatch
) -> None:
    train, dev, test = streamed_cases
    seen_worlds = []
    original_compiler = operator.native_role_input

    def guarded_compiler(world):
        result = original_compiler(world)
        assert type(world) is worlds.ModelWorldV1
        seen_worlds.append(world)
        return result

    monkeypatch.setattr(operator, "native_role_input", guarded_compiler)
    config = operator.TrainingConfig(
        width=3, seed=29, epochs=2, batch_size=32, patience=2
    )
    model = operator.fit_operator(train, dev, config=config)
    assert seen_worlds
    assert all(type(world) is worlds.ModelWorldV1 for world in seen_worlds)
    assert math.isfinite(model.mean_squared_error(test))
    with pytest.raises(operator.SWM0WOperatorError, match="ModelWorldV1"):
        model.score(test[0])

    comparison = operator.compare_models(
        {operator.SWM0WArm.ROLE_TRIPLE: model}, test
    )
    reversed_test = tuple(reversed(test))
    assert model.mean_squared_error(test) == model.mean_squared_error(
        reversed_test
    )
    assert comparison.receipt_sha256 == operator.compare_models(
        {operator.SWM0WArm.ROLE_TRIPLE: model}, reversed_test
    ).receipt_sha256
    assert dict(comparison.model_state_sha256_by_arm) == {
        "ROLE_TRIPLE": model.state_sha256
    }
    assert comparison.evaluator_binding_sha256 != (
        model.optimization.evaluator_binding_sha256
    )
    replay = operator.fit_operator(
        tuple(reversed(train)), tuple(reversed(dev)), config=config
    )
    assert replay.state_sha256 == model.state_sha256
    assert replay.optimization.receipt_sha256 == (
        model.optimization.receipt_sha256
    )
    reidentified = operator.fit_operator(
        _reidentify_streamed_cases(train),
        _reidentify_streamed_cases(dev),
        config=config,
    )
    assert all(
        np.array_equal(model.parameters[name], reidentified.parameters[name])
        for name in model.parameters
    )
    assert reidentified.optimization.evaluator_binding_sha256 != (
        model.optimization.evaluator_binding_sha256
    )
    assert reidentified.state_sha256 != model.state_sha256


def test_evaluator_adapter_rejects_ducks_subclasses_mixing_and_task_mismatch(
    learned_triple, smoke_cases, streamed_cases
) -> None:
    legacy_train, legacy_dev, _ = smoke_cases
    task_train, task_dev, task_test = streamed_cases
    tiny = operator.TrainingConfig(
        width=2, seed=2, epochs=1, batch_size=8, patience=1
    )

    with pytest.raises(operator.SWM0WOperatorError, match="mix"):
        operator.fit_operator(
            (legacy_train[0], task_train[0]), task_dev[:2], config=tiny
        )
    with pytest.raises(operator.SWM0WOperatorError, match="same evaluator"):
        operator.fit_operator(legacy_train[:2], task_dev[:2], config=tiny)

    changed_unsigned = task_dev[0].unsigned_canonical()
    changed_unsigned["task_uid"] = "swm0wt_" + "a" * 24
    changed_task = replace(
        task_dev[0],
        task_uid=changed_unsigned["task_uid"],
        receipt_sha256=task_core.canonical_sha256(changed_unsigned),
    )
    with pytest.raises(operator.SWM0WOperatorError, match="same streamed task"):
        operator.fit_operator(task_train[:2], (changed_task,), config=tiny)

    class DuckEvaluator:
        split = "test"
        target = float("nan")
        world = task_test[0].world

    with pytest.raises(operator.SWM0WOperatorError, match="supported evaluator"):
        learned_triple.mean_squared_error((DuckEvaluator(),))

    class LeakyWorld(worlds.ModelWorldV1):
        def feature_matrix(self):
            return super().feature_matrix()

    leaky_world = LeakyWorld(task_test[0].world.incidences)
    with pytest.raises(operator.SWM0WOperatorError, match="exact ModelWorldV1"):
        learned_triple.score(leaky_world)
    leaky_case = replace(task_test[0], world=leaky_world)
    with pytest.raises(operator.SWM0WOperatorError, match="exact ModelWorldV1"):
        learned_triple.mean_squared_error((leaky_case,))


def test_split_contract_and_comparison_labels_fail_closed(
    learned_triple, smoke_cases
) -> None:
    train, dev, _ = smoke_cases
    tiny = operator.TrainingConfig(
        width=2, seed=1, epochs=1, batch_size=16, patience=1
    )
    with pytest.raises(operator.SWM0WOperatorError, match="train input"):
        operator.fit_operator(dev[:16], dev[16:32], config=tiny)
    with pytest.raises(operator.SWM0WOperatorError, match="dev input"):
        operator.fit_operator(train[:16], train[16:32], config=tiny)

    flat = operator.fit_operator(
        train[:32], dev[:16], operator.SWM0WArm.FLAT_MLP, config=tiny
    )
    with pytest.raises(operator.SWM0WOperatorError, match="does not match"):
        operator.compare_models(
            {operator.SWM0WArm.ROLE_TRIPLE: flat}, dev[:8]
        )
    comparison = operator.compare_models(
        {operator.SWM0WArm.ROLE_TRIPLE: learned_triple}, dev[:8]
    )
    with pytest.raises(operator.SWM0WOperatorError, match="interpretation disagrees"):
        replace(comparison, interpretation="tampered")
    with pytest.raises(operator.SWM0WOperatorError, match="at least one"):
        replace(
            comparison,
            mean_squared_error_by_arm=(),
            model_state_sha256_by_arm=(),
        )
    with pytest.raises(operator.SWM0WOperatorError, match="finite MSE"):
        replace(
            comparison,
            mean_squared_error_by_arm=(("ROLE_TRIPLE", False),),
        )


def test_scope_and_default_budget_are_explicit_and_bounded() -> None:
    assert "fixed-arity third-order" in (operator.__doc__ or "")
    assert "diagnostic precursor" in (operator.__doc__ or "")
    assert "not canonical HSWM's" in (operator.__doc__ or "")
    assert "not multi-member-within-role DeepSets universality" in (
        operator.__doc__ or ""
    )
    config = operator.TrainingConfig()
    assert config.width == 16
    assert config.epochs == 200
    assert config.patience == 25
    with pytest.raises(operator.SWM0WOperatorError):
        operator.TrainingConfig(width=0)
    with pytest.raises(operator.SWM0WOperatorError):
        operator.TrainingConfig(epochs=0)
