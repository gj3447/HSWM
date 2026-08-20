from __future__ import annotations

from collections import Counter
import re

import numpy as np
import pytest

from hswm.experiments.swm0_operator import (
    ALL_ARMS,
    ARM_BOUNDARIES,
    COMMON_FEATURE_VOCABULARY,
    DUPLICATE_INFORMATION_CONTROLS,
    ENCODER_PATHS,
    LEARNED_OPERATOR_STATUS,
    MECHANISM_KIND,
    MILESTONE_STATUS,
    STAR_COMPILER_INDEPENDENT,
    BalancedRidgeReadout,
    SWM0Arm,
    SWM0OperatorError,
    cases_from_blocks,
    compile_typed_star,
    encode_world,
    effective_feature_count,
    evaluate_arms,
    estimate_encoder_operations,
    fit_arm,
    semantic_feature_map,
)
from hswm.experiments.swm0_worlds import (
    GROUPING_RELATION,
    ROLE_RELATION,
    HyperedgeV1,
    WorldV1,
    generate_block,
    remove_edge,
    restore_edge,
    rotate_role_gadget,
    shift_grouping_gadget,
)


_TRAIN_SEED = b"swm0-operator-train-seed-v1"
_TEST_SEED = b"swm0-operator-fresh-seed-v1"
_OPAQUE_UID = re.compile(r"(?:n|e|case|block)_[0-9a-f]{24}")


@pytest.fixture(scope="module")
def train_cases():
    blocks = [
        generate_block(
            split="train", block_index=index, seed_preimage=_TRAIN_SEED
        )
        for index in range(3)
    ]
    return cases_from_blocks(blocks)


@pytest.fixture(scope="module")
def test_cases():
    blocks = [
        generate_block(split="test", block_index=index, seed_preimage=_TEST_SEED)
        for index in range(3)
    ]
    return cases_from_blocks(blocks)


def _case(cases, g: int, r: int):
    return next(case for case in cases if case.g == g and case.r == r)


def _reverse_serialisation(world: WorldV1) -> WorldV1:
    edges = tuple(
        HyperedgeV1(
            uid=edge.uid,
            relation_type=edge.relation_type,
            incidences=tuple(reversed(edge.incidences)),
        )
        for edge in reversed(world.edges)
    )
    return WorldV1(nodes=tuple(reversed(world.nodes)), edges=edges)


def test_required_arms_and_one_common_vocabulary():
    assert {arm.value for arm in ALL_ARMS} == {
        "ROLE_NARY_ONE_SWEEP",
        "TYPED_STAR_EQUIV",
        "SCALAR_HYPEREDGE",
        "TYPED_CLIQUE_2SECTION",
        "PAIRWISE_RELATION_SUM",
        "COSINE_OR_FLAT",
        "ROLE_SHUFFLE",
        "GROUPING_SHUFFLE",
        "ID_ORDER_PROBE",
    }
    assert len(COMMON_FEATURE_VOCABULARY) == len(set(COMMON_FEATURE_VOCABULARY))
    assert len(COMMON_FEATURE_VOCABULARY) > 9


def test_claim_boundaries_are_machine_readable_and_narrow():
    assert MECHANISM_KIND == "CONSTRUCTIVE_REPRESENTATION_WITNESS"
    assert MILESTONE_STATUS == "SWM-0R_REPRESENTATION_CONFORMANCE_ONLY"
    assert LEARNED_OPERATOR_STATUS == "SWM-0W_UNIMPLEMENTED_UNJUDGED"
    assert "not learned" in ARM_BOUNDARIES[SWM0Arm.ROLE_NARY_ONE_SWEEP]
    assert "no cosine" in ARM_BOUNDARIES[SWM0Arm.COSINE_OR_FLAT]
    assert "not a sampled shuffle" in ARM_BOUNDARIES[SWM0Arm.ROLE_SHUFFLE]
    assert "not a sampled shuffle" in ARM_BOUNDARIES[SWM0Arm.GROUPING_SHUFFLE]
    assert DUPLICATE_INFORMATION_CONTROLS == (
        (
            SWM0Arm.TYPED_CLIQUE_2SECTION,
            SWM0Arm.PAIRWISE_RELATION_SUM,
        ),
    )


def test_target_and_typed_star_have_exact_feature_parity(test_cases):
    for case in test_cases:
        target_map = semantic_feature_map(
            case.world, SWM0Arm.ROLE_NARY_ONE_SWEEP
        )
        star_map = semantic_feature_map(case.world, SWM0Arm.TYPED_STAR_EQUIV)
        assert target_map == star_map
        assert np.array_equal(
            encode_world(case.world, SWM0Arm.ROLE_NARY_ONE_SWEEP),
            encode_world(case.world, SWM0Arm.TYPED_STAR_EQUIV),
        )
        assert len(target_map) == 1
        assert next(iter(target_map.values())) == pytest.approx(1.0)


def test_typed_star_uses_an_independent_uid_free_compiler(test_cases):
    assert STAR_COMPILER_INDEPENDENT is True
    assert ENCODER_PATHS[SWM0Arm.ROLE_NARY_ONE_SWEEP] != ENCODER_PATHS[
        SWM0Arm.TYPED_STAR_EQUIV
    ]
    stars = compile_typed_star(test_cases[0].world)
    assert len(stars) == 10
    assert not _OPAQUE_UID.search(repr(stars))
    assert {star.relation_type for star in stars} == {
        GROUPING_RELATION,
        ROLE_RELATION,
    }


def test_target_semantic_features_ignore_opaque_identifiers(train_cases, test_cases):
    train_case = _case(train_cases, 2, 1)
    fresh_case = _case(test_cases, 2, 1)
    train_features = semantic_feature_map(
        train_case.world, SWM0Arm.ROLE_NARY_ONE_SWEEP
    )
    fresh_features = semantic_feature_map(
        fresh_case.world, SWM0Arm.ROLE_NARY_ONE_SWEEP
    )
    assert train_features == fresh_features
    assert not any(_OPAQUE_UID.search(key) for key in train_features)
    assert not any(
        isinstance(value, str) and _OPAQUE_UID.search(value)
        for value in train_features.values()
    )
    assert {node.uid for node in train_case.world.nodes}.isdisjoint(
        {node.uid for node in fresh_case.world.nodes}
    )


@pytest.mark.parametrize("arm", list(SWM0Arm))
def test_every_encoder_is_serialisation_order_invariant(test_cases, arm):
    world = test_cases[0].world
    reversed_world = _reverse_serialisation(world)
    assert semantic_feature_map(world, arm) == semantic_feature_map(
        reversed_world, arm
    )
    assert np.array_equal(
        encode_world(world, arm), encode_world(reversed_world, arm)
    )


def test_lossy_information_contracts_hold_exactly(test_cases):
    # Scalar exact grouping is independent of r at fixed g.
    for g in range(3):
        maps = {
            tuple(
                semantic_feature_map(
                    _case(test_cases, g, r).world,
                    SWM0Arm.SCALAR_HYPEREDGE,
                ).items()
            )
            for r in range(3)
        }
        assert len(maps) == 1

    # Typed pairwise projections are independent of g at fixed r.
    for arm in (
        SWM0Arm.TYPED_CLIQUE_2SECTION,
        SWM0Arm.PAIRWISE_RELATION_SUM,
        SWM0Arm.GROUPING_SHUFFLE,
    ):
        for r in range(3):
            maps = {
                tuple(
                    semantic_feature_map(
                        _case(test_cases, g, r).world, arm
                    ).items()
                )
                for g in range(3)
            }
            assert len(maps) == 1

    # The ID probe sees one block-level node multiset, never evaluator labels.
    probe_maps = {
        tuple(
            semantic_feature_map(
                case.world, SWM0Arm.ID_ORDER_PROBE
            ).items()
        )
        for case in test_cases[:9]
    }
    assert len(probe_maps) == 1


def test_balanced_ridge_target_and_star_fit_lookup_on_fresh_ids(
    train_cases, test_cases
):
    target = fit_arm(train_cases, SWM0Arm.ROLE_NARY_ONE_SWEEP)
    star = fit_arm(train_cases, SWM0Arm.TYPED_STAR_EQUIV)
    assert target.score(train_cases) == pytest.approx(1.0)
    assert target.score(test_cases) == pytest.approx(1.0)
    assert star.score(test_cases) == pytest.approx(1.0)
    assert np.array_equal(target.coefficients, star.coefficients)
    assert target.parameter_count == star.parameter_count


def test_every_lossy_control_stays_at_exact_chance(train_cases, test_cases):
    lossy = set(SWM0Arm).difference(
        {SWM0Arm.ROLE_NARY_ONE_SWEEP, SWM0Arm.TYPED_STAR_EQUIV}
    )
    for arm in lossy:
        model = fit_arm(train_cases, arm)
        assert model.score(train_cases) == pytest.approx(1.0 / 3.0)
        assert model.score(test_cases) == pytest.approx(1.0 / 3.0)


def test_all_arms_receive_identical_readout_parameter_budget(
    train_cases, test_cases
):
    evaluations = evaluate_arms(train_cases, test_cases)
    assert len(evaluations) == len(SWM0Arm)
    assert len({result.parameter_count for result in evaluations}) == 1
    assert len({result.effective_feature_count for result in evaluations}) > 1
    assert len({result.encoder_operation_units for result in evaluations}) > 1
    accuracy = {result.arm: result.test_accuracy for result in evaluations}
    assert accuracy[SWM0Arm.ROLE_NARY_ONE_SWEEP] == pytest.approx(1.0)
    assert accuracy[SWM0Arm.TYPED_STAR_EQUIV] == pytest.approx(1.0)
    assert all(re.fullmatch(r"[0-9a-f]{64}", result.state_sha256) for result in evaluations)
    assert all(result.mechanism_kind == MECHANISM_KIND for result in evaluations)
    assert all(result.milestone_status == MILESTONE_STATUS for result in evaluations)


def test_effective_features_and_structural_cost_are_not_compute_parity(test_cases):
    world = test_cases[0].world
    assert effective_feature_count(SWM0Arm.ROLE_NARY_ONE_SWEEP) == 9
    assert effective_feature_count(SWM0Arm.SCALAR_HYPEREDGE) == 3
    target_cost = estimate_encoder_operations(
        world, SWM0Arm.ROLE_NARY_ONE_SWEEP
    )
    star_cost = estimate_encoder_operations(world, SWM0Arm.TYPED_STAR_EQUIV)
    assert target_cost.total_units > 0
    assert star_cost.total_units > target_cost.total_units
    assert target_cost.pair_terms == 0
    assert estimate_encoder_operations(
        world, SWM0Arm.TYPED_CLIQUE_2SECTION
    ).pair_terms > 0


def test_balancing_is_explicit_for_imbalanced_training_cases(train_cases, test_cases):
    target_zero = [case for case in train_cases if case.target == 0]
    imbalanced = tuple(train_cases) + tuple(target_zero) * 4
    model = BalancedRidgeReadout.fit(
        imbalanced, SWM0Arm.ROLE_NARY_ONE_SWEEP
    )
    assert model.class_counts == (
        5 * len(target_zero),
        len([case for case in train_cases if case.target == 1]),
        len([case for case in train_cases if case.target == 2]),
    )
    assert model.score(test_cases) == pytest.approx(1.0)


def test_model_state_digest_is_deterministic_and_arm_bound(train_cases):
    first = fit_arm(train_cases, SWM0Arm.ROLE_NARY_ONE_SWEEP)
    second = fit_arm(train_cases, SWM0Arm.ROLE_NARY_ONE_SWEEP)
    star = fit_arm(train_cases, SWM0Arm.TYPED_STAR_EQUIV)
    assert first.state_sha256 == second.state_sha256
    assert first.state_sha256 != star.state_sha256
    assert not first.coefficients.flags.writeable


def test_counterfactual_group_and_role_rotations_shift_prediction(
    train_cases, test_cases
):
    model = fit_arm(train_cases, SWM0Arm.ROLE_NARY_ONE_SWEEP)
    case = _case(test_cases, 0, 1)
    original = model.predict(case.world)
    assert model.predict(shift_grouping_gadget(case.world, step=1)) == (
        original + 1
    ) % 3
    assert model.predict(rotate_role_gadget(case.world, step=1)) == (
        original + 1
    ) % 3


def test_role_edge_removal_erases_gain_and_exact_restore_recovers_it(
    train_cases, test_cases
):
    model = fit_arm(train_cases, SWM0Arm.ROLE_NARY_ONE_SWEEP)
    removed_predictions: list[int] = []
    targets: list[int] = []
    for case in test_cases:
        role_edge = next(
            edge
            for edge in case.world.edges
            if edge.relation_type == ROLE_RELATION
        )
        removed, receipt = remove_edge(case.world, role_edge.uid)
        assert semantic_feature_map(
            removed, SWM0Arm.ROLE_NARY_ONE_SWEEP
        ) == {}
        removed_predictions.append(model.predict(removed))
        targets.append(case.target)

        restored = restore_edge(removed, receipt)
        assert restored.artifact_sha256 == case.world.artifact_sha256
        assert semantic_feature_map(
            restored, SWM0Arm.ROLE_NARY_ONE_SWEEP
        ) == semantic_feature_map(
            case.world, SWM0Arm.ROLE_NARY_ONE_SWEEP
        )
        assert np.array_equal(model.logits(restored), model.logits(case.world))
        assert model.predict(restored) == case.target

    assert np.mean(np.asarray(removed_predictions) == np.asarray(targets)) == pytest.approx(
        1.0 / 3.0
    )


def test_grouping_edge_removal_changes_mass_and_restore_is_exact(test_cases):
    world = test_cases[0].world
    grouping_edge = next(
        edge for edge in world.edges if edge.relation_type == GROUPING_RELATION
    )
    before = semantic_feature_map(world, SWM0Arm.ROLE_NARY_ONE_SWEEP)
    removed, receipt = remove_edge(world, grouping_edge.uid)
    during = semantic_feature_map(removed, SWM0Arm.ROLE_NARY_ONE_SWEEP)
    assert list(before) == list(during)
    assert next(iter(before.values())) == pytest.approx(1.0)
    assert next(iter(during.values())) == pytest.approx(8.0 / 9.0)
    restored = restore_edge(removed, receipt)
    assert semantic_feature_map(
        restored, SWM0Arm.ROLE_NARY_ONE_SWEEP
    ) == before


def test_readout_rejects_invalid_training_contract(train_cases):
    with pytest.raises(SWM0OperatorError, match="every F_3 class"):
        fit_arm(
            [case for case in train_cases if case.target != 2],
            SWM0Arm.ROLE_NARY_ONE_SWEEP,
        )
    with pytest.raises(SWM0OperatorError, match="positive"):
        fit_arm(train_cases, SWM0Arm.ROLE_NARY_ONE_SWEEP, ridge=0.0)
    with pytest.raises(SWM0OperatorError, match="duplicates"):
        encode_world(
            train_cases[0].world,
            SWM0Arm.ROLE_NARY_ONE_SWEEP,
            vocabulary=("duplicate", "duplicate"),
        )


def test_targets_are_balanced_in_each_fresh_block(test_cases):
    for offset in range(0, len(test_cases), 9):
        assert Counter(case.target for case in test_cases[offset : offset + 9]) == {
            0: 3,
            1: 3,
            2: 3,
        }
