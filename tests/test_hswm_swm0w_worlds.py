from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import re

import pytest

from hswm.experiments import swm0w_worlds as worlds


SEED = b"swm0w-f5-structural-world-tests-v1"


@pytest.fixture(scope="module")
def bundle() -> worlds.SWM0WBundleV1:
    return worlds.generate_bundle(seed_preimage=SEED)


def test_f5_cuts_are_exact_and_full_six_tuples_are_disjoint(bundle) -> None:
    train = bundle.for_split("train")
    dev = bundle.for_split("dev")
    test = bundle.for_split("test")
    assert len(train.cases) == 9 * 5**4 == 5625
    assert len(dev.cases) == len(test.cases) == 5**4 == 625
    assert {(case.coefficient_shift, case.operand_shift) for case in train.cases} == {
        (s, t) for s in range(3) for t in range(3)
    }
    assert {(case.coefficient_shift, case.operand_shift) for case in dev.cases} == {(3, 3)}
    assert {(case.coefficient_shift, case.operand_shift) for case in test.cases} == {(4, 4)}

    six = {split.split: {case.six_tuple for case in split.cases} for split in bundle.splits}
    assert six["train"].isdisjoint(six["dev"])
    assert six["train"].isdisjoint(six["test"])
    assert six["dev"].isdisjoint(six["test"])
    for split in bundle.splits:
        for case in split.cases:
            a, b, c = case.coefficients
            d, e, x = case.operands
            assert c == (a + b + case.coefficient_shift) % 5
            assert x == (d + e + case.operand_shift) % 5


def test_model_view_is_only_role_plus_normalized_raw_pair(bundle) -> None:
    forbidden = {
        "case_uid",
        "coefficient_shift",
        "coefficients",
        "incidence_uids",
        "operand_shift",
        "operands",
        "seed_sha256",
        "split",
        "target",
        "target_hex",
        "world_uid",
    }
    uid_pattern = re.compile(r"swm0w_(?:case|world|inc)_[0-9a-f]{24}")
    for split in bundle.splits:
        for case in split.cases:
            payload = case.model_visible()
            assert set(payload) == {"incidences", "schema_version"}
            assert len(payload["incidences"]) == 3
            assert all(set(row) == {"features", "role"} for row in payload["incidences"])
            assert all(len(row["features"]) == 2 for row in payload["incidences"])
            encoded = json.dumps(payload, sort_keys=True)
            assert not forbidden.intersection(payload)
            assert not uid_pattern.search(encoded)
            assert case.case_uid not in encoded
            assert case.world_uid not in encoded
    assert set(worlds.normalize_level(value) for value in range(5)) == {
        -1.0,
        -0.5,
        0.0,
        0.5,
        1.0,
    }


def test_unary_and_every_role_pair_marginal_match_exactly(bundle) -> None:
    unary = dict(bundle.audit.unary_marginal_sha256)
    pair = dict(bundle.audit.pair_marginal_sha256)
    assert len(set(unary.values())) == 1
    assert len(set(pair.values())) == 1
    checks = dict(bundle.audit.checks)
    assert checks["unary_marginals_exactly_matched"]
    assert checks["role_pair_marginals_exactly_matched"]


def test_opaque_identifiers_are_unique_and_split_disjoint(bundle) -> None:
    uid_sets = {}
    for split in bundle.splits:
        identifiers = {
            uid
            for case in split.cases
            for uid in (
                case.case_uid,
                case.world_uid,
                *(uid for _, uid in case.incidence_uids),
            )
        }
        assert len(identifiers) == len(split.cases) * 5
        uid_sets[split.split] = identifiers
    assert uid_sets["train"].isdisjoint(uid_sets["dev"])
    assert uid_sets["train"].isdisjoint(uid_sets["test"])
    assert uid_sets["dev"].isdisjoint(uid_sets["test"])
    assert dict(bundle.audit.opaque_id_counts) == {
        "train": 5625 * 5,
        "dev": 625 * 5,
        "test": 625 * 5,
    }


def test_canonical_world_hash_is_incidence_permutation_invariant(bundle) -> None:
    case = bundle.for_split("test").cases[0]
    reversed_world = worlds.ModelWorldV1(tuple(reversed(case.world.incidences)))
    assert reversed_world.canonical() == case.world.canonical()
    assert reversed_world.semantic_sha256 == case.world.semantic_sha256
    assert reversed_world.feature_matrix() == case.world.feature_matrix()


def test_hidden_tanh_target_has_registered_anova_and_moment_bounds(bundle) -> None:
    audit = bundle.audit
    checks = dict(audit.checks)
    assert audit.passed
    assert all(checks.values())
    assert 0.45 <= audit.triple_variance_fraction <= 0.65
    assert audit.triple_variance_fraction == pytest.approx(0.601406715364511)
    assert all(value > 1.0e-6 for _, value in audit.counterfactual_min_range_by_role)
    assert audit.canonical()["scope"] == {
        "arity": 3,
        "arity_extrapolation_claim": False,
        "incidences_per_role": 1,
        "multi_member_within_role_claim": False,
    }
    for _, (mean, std, second_moment) in audit.split_target_moments:
        assert abs(mean) <= 0.075
        assert 0.32 <= std <= 0.42
        assert 0.10 <= second_moment <= 0.16


def test_replay_is_exact_while_new_seed_changes_only_ids_and_order(bundle) -> None:
    replay = worlds.generate_bundle(seed_preimage=SEED)
    assert replay.canonical() == bundle.canonical()
    other = worlds.generate_bundle(seed_preimage=b"swm0w-f5-other-seed-material-v1")
    assert other.bundle_sha256 != bundle.bundle_sha256
    assert [split.semantic_sha256 for split in other.splits] == [
        split.semantic_sha256 for split in bundle.splits
    ]
    assert {
        case.case_uid for case in other.for_split("test").cases
    }.isdisjoint({case.case_uid for case in bundle.for_split("test").cases})


def test_artifacts_are_frozen_hash_bound_and_export_no_oracle(bundle) -> None:
    case = bundle.for_split("dev").cases[0]
    with pytest.raises(FrozenInstanceError):
        case.target = 0.0
    with pytest.raises(worlds.SWM0WWorldError, match="split_sha256"):
        replace(bundle.for_split("dev"), split_sha256="0" * 64)
    with pytest.raises(worlds.SWM0WWorldError, match="bundle_sha256"):
        replace(bundle, bundle_sha256="0" * 64)
    assert not any("oracle" in name.lower() for name in worlds.__all__)
    assert not any(name.startswith("target_") for name in worlds.__all__)
    assert worlds.cases_from_split(bundle, "train") is bundle.for_split("train").cases


def test_module_has_no_duplicate_literal_dictionary_keys() -> None:
    tree = ast.parse(Path(worlds.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        literal_keys = [
            key.value
            for key in node.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        ]
        assert len(literal_keys) == len(set(literal_keys))


@pytest.mark.parametrize("bad", [-1, 5, True, 1.0])
def test_normalization_rejects_non_f5_values(bad) -> None:
    with pytest.raises(worlds.SWM0WWorldError):
        worlds.normalize_level(bad)
