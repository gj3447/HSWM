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
from hswm.experiments import swm0w_worlds as worlds


SEED = b"swm0w-learned-operator-tests-v1"
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
        "ROLES",
        "EvaluatorCaseV1",
        "ModelWorldV1",
        "RoleInputV1",
        "cases_from_split",
    }
    assert not any(name.startswith("_") for name in names)
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
    parameters = operator._initial_parameters(arm, 2, rng)
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
    assert "No novelty claim" in comparison.interpretation


def test_frozen_triple_head_remove_restore_is_bit_exact(
    learned_triple, smoke_cases
) -> None:
    _, _, test = smoke_cases
    base_scores = np.asarray([learned_triple.score(case.world) for case in test])
    removed, receipt = operator.remove_triple_head(learned_triple)
    removed_scores = np.asarray([removed.score(case.world) for case in test])
    assert removed.intervention == "TRIPLE_HEAD_REMOVED"
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
        replace(receipt, triple_head_hex=("0x0.0p+0",) * 16)


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
    with pytest.raises(operator.SWM0WOperatorError, match="receipt hash"):
        replace(comparison, interpretation="tampered")


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
