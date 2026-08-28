"""DNRD-5 future-randomness allocation and call-ledger contract tests."""

from __future__ import annotations

import copy

import pytest

from _research.dnrd5 import randomization


FUTURE_RANDOMNESS = "01" * 32
STUDY_BINDING = "ab" * 32
BLOCK_ID = "DNRD5-BLOCK-0001"


def _plan() -> dict[str, object]:
    return randomization.derive_block_plan(
        future_randomness_hex=FUTURE_RANDOMNESS,
        study_binding_sha256=STUDY_BINDING,
        block_id=BLOCK_ID,
    )


def test_exact_ordered_block_universe_and_total_call_budget() -> None:
    ids = randomization.expected_block_ids()
    assert len(ids) == 300
    assert ids[0] == "DNRD5-BLOCK-0001"
    assert ids[-1] == "DNRD5-BLOCK-0300"
    assert tuple(sorted(ids)) == ids
    assert randomization.CALLS_PER_BLOCK == 9
    assert randomization.TOTAL_CALLS == 2_700


def test_derivation_is_deterministic_domain_separated_and_complete() -> None:
    first = _plan()
    assert first == _plan()
    validated = randomization.validate_block_plan(
        first,
        future_randomness_hex=FUTURE_RANDOMNESS,
        study_binding_sha256=STUDY_BINDING,
    )
    assert validated == first
    public = first["sealed_fork_projection"]
    assignment = first["private_assignment"]
    schedule = first["private_call_schedule"]
    assert isinstance(public, dict) and isinstance(assignment, dict) and isinstance(schedule, list)
    assert set(assignment.values()) == set(randomization.ARMS)
    assert len(schedule) == 9
    assert schedule[0]["call_class"] == "PRE_OUTCOME_TRAJECTORY"
    assert [row["call_class"] for row in schedule].count("REVISION_PROPOSAL") == 4
    assert [row["call_class"] for row in schedule].count("FRESH_PROBE") == 4
    clones = public["forks"]
    for clone in clones:
        assert clone["proposal_seed_sha256"] != clone["probe_seed_sha256"]


def test_clone_material_is_fixed_before_and_independent_of_arm_mapping() -> None:
    clones = randomization.derive_clone_material(
        future_randomness_hex=FUTURE_RANDOMNESS,
        study_binding_sha256=STUDY_BINDING,
        block_id=BLOCK_ID,
    )
    assignment = randomization.derive_arm_assignment(
        future_randomness_hex=FUTURE_RANDOMNESS,
        study_binding_sha256=STUDY_BINDING,
        block_id=BLOCK_ID,
    )
    assert list(assignment) == [clone["fork_id"] for clone in clones]
    assert clones == randomization.derive_clone_material(
        future_randomness_hex=FUTURE_RANDOMNESS,
        study_binding_sha256=STUDY_BINDING,
        block_id=BLOCK_ID,
    )


def test_model_projection_contains_neither_arm_labels_nor_fork_ids() -> None:
    plan = _plan()
    projection = plan["model_visible_randomization_projection"]
    encoded = randomization.canonical_json_bytes(projection)
    for arm in randomization.ARMS:
        assert arm.encode("ascii") not in encoded
    for clone in plan["sealed_fork_projection"]["forks"]:
        assert clone["fork_id"].encode("ascii") not in encoded


def test_study_plan_rederives_all_300_blocks_and_2700_opaque_call_slots() -> None:
    plan = randomization.derive_study_plan(
        future_randomness_hex=FUTURE_RANDOMNESS,
        study_binding_sha256=STUDY_BINDING,
    )
    validated = randomization.validate_study_plan(
        plan,
        future_randomness_hex=FUTURE_RANDOMNESS,
        study_binding_sha256=STUDY_BINDING,
    )
    assert validated == plan
    assert plan["block_count"] == 300
    assert plan["total_call_slots"] == 2700
    assert [block["block_id"] for block in plan["blocks"]] == list(randomization.expected_block_ids())


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda plan: plan["private_call_schedule"].pop(), "exactly nine"),
        (
            lambda plan: plan["private_assignment"].__setitem__(
                list(plan["private_assignment"])[0],
                plan["private_assignment"][list(plan["private_assignment"])[1]],
            ),
            "four-arm permutation|commitment mismatch",
        ),
        (
            lambda plan: plan["assignment_receipt"].__setitem__(
                "assignment_commitment_sha256", "00" * 32
            ),
            "commitment mismatch",
        ),
        (
            lambda plan: plan["model_visible_randomization_projection"].__setitem__("arm", "ACTIVE"),
            "unexpected key set",
        ),
        (
            lambda plan: plan["sealed_fork_projection"]["forks"].reverse(),
            "sealed fork projection|rederive",
        ),
        (
            lambda plan: plan["sealed_fork_projection"]["forks"][0].__setitem__(
                "proposal_seed_sha256", "11" * 32
            ),
            "sealed fork projection|rederive",
        ),
    ],
)
def test_adversarial_plan_mutations_fail_closed(mutation, match: str) -> None:
    plan = copy.deepcopy(_plan())
    mutation(plan)
    with pytest.raises(randomization.RandomizationValidationError, match=match):
        randomization.validate_block_plan(
            plan,
            future_randomness_hex=FUTURE_RANDOMNESS,
            study_binding_sha256=STUDY_BINDING,
        )


def test_self_consistent_rehash_cannot_hide_post_randomness_fork_reordering() -> None:
    plan = copy.deepcopy(_plan())
    plan["sealed_fork_projection"]["forks"].reverse()
    fork_digest = randomization.canonical_json_sha256(plan["sealed_fork_projection"])
    plan["assignment_receipt"]["sealed_fork_projection_sha256"] = fork_digest
    plan["call_schedule_receipt"]["sealed_fork_projection_sha256"] = fork_digest
    with pytest.raises(randomization.RandomizationValidationError, match="rederive"):
        randomization.validate_block_plan(
            plan,
            future_randomness_hex=FUTURE_RANDOMNESS,
            study_binding_sha256=STUDY_BINDING,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("future_randomness_hex", "AA" * 32),
        ("future_randomness_hex", "00"),
        ("study_binding_sha256", "g" * 64),
        ("block_id", "DNRD5-BLOCK-0301"),
    ],
)
def test_invalid_derivation_inputs_are_refused(field: str, value: str) -> None:
    inputs = {
        "future_randomness_hex": FUTURE_RANDOMNESS,
        "study_binding_sha256": STUDY_BINDING,
        "block_id": BLOCK_ID,
    }
    inputs[field] = value
    with pytest.raises(randomization.RandomizationValidationError):
        randomization.derive_block_plan(**inputs)


def test_custody_views_are_copy_isolated_and_model_view_rejects_combined_plan() -> None:
    plan = _plan()
    private = randomization.extract_private_custodian_view(plan)
    assert private["custody_status"] == randomization.COMBINED_CUSTODY_STATUS
    private["private_assignment"].clear()
    assert plan["private_assignment"]
    model = randomization.derive_model_visible_projection(STUDY_BINDING, BLOCK_ID)
    assert randomization.validate_model_visible_projection(model) == model
    assert model["study_binding_sha256"] == STUDY_BINDING
    with pytest.raises(randomization.RandomizationValidationError):
        randomization.validate_model_visible_projection(plan)

    evaluator = randomization.derive_evaluator_visible_projection(
        STUDY_BINDING, BLOCK_ID
    )
    assert randomization.validate_evaluator_visible_projection(evaluator) == evaluator
    for projection in (model, evaluator):
        encoded = randomization.canonical_json_bytes(projection)
        assert b"fork-" not in encoded
        assert b"assignment" not in encoded
        assert all(arm.encode("ascii") not in encoded for arm in randomization.ARMS)


def test_custody_projection_rejects_nested_leakage_and_structural_drift() -> None:
    model = randomization.derive_model_visible_projection(STUDY_BINDING, BLOCK_ID)
    nested_leak = copy.deepcopy(model)
    nested_leak["private"] = {"arm": "ACTIVE", "fork_id": "fork-secret"}
    with pytest.raises(randomization.RandomizationValidationError, match="unexpected key set"):
        randomization.validate_model_visible_projection(nested_leak)

    evaluator = randomization.derive_evaluator_visible_projection(
        STUDY_BINDING, BLOCK_ID
    )
    bad_binding = copy.deepcopy(evaluator)
    bad_binding["study_binding_sha256"] = "not-a-sha"
    with pytest.raises(randomization.RandomizationValidationError, match="SHA-256"):
        randomization.validate_evaluator_visible_projection(bad_binding)

    combined_with_extra = copy.deepcopy(_plan())
    combined_with_extra["public_alias"] = model
    with pytest.raises(randomization.RandomizationValidationError, match="unexpected key set"):
        randomization.extract_private_custodian_view(combined_with_extra)

    other_study = randomization.derive_model_visible_projection("cd" * 32, BLOCK_ID)
    assert other_study != model
