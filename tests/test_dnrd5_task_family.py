from __future__ import annotations

import copy

import pytest

from _research.dnrd5 import evaluator, task_family as task


SEED = bytes(range(32))


def _response(public: dict[str, object], hypothesis: int) -> dict[str, object]:
    core = task.public_core(public)
    return {
        "schema_version": task.TRAINING_RESPONSE_SCHEMA,
        "block_id": core["block_id"],
        "hypothesis_id": hypothesis,
        "answer_token": core["h0" if hypothesis == 0 else "h1"][core["train_input"]],
    }


def test_study_is_300_domain_separated_blocks_with_no_private_leakage() -> None:
    study = task.generate_study(SEED)
    assert len(study) == task.BLOCK_COUNT
    assert len({bundle["public_task"]["block_id"] for bundle in study}) == task.BLOCK_COUNT
    for bundle in (study[0], study[-1]):
        public = bundle["public_task"]
        task.audit_bundle(public, bundle["evaluator_private"], bundle["probe_private"], bundle["placebo_private"])
        public_bytes = task.canonical_json(public)
        assert bundle["probe_private"]["probe_identity"].encode() not in public_bytes
        assert bundle["evaluator_private"]["private_canary"].encode() not in public_bytes
        assert public["block_id"].startswith("DNRD5-BLOCK-")
    with pytest.raises(task.TaskFamilyError, match="exactly 32"):
        task.generate_block(b"short", 0)
    with pytest.raises(task.TaskFamilyError, match="block_index"):
        task.generate_block(SEED, True)
    duplicated = copy.deepcopy(study[0]["public_task"])
    duplicated["public_core"]["inputs"][1] = duplicated["public_core"]["inputs"][0]
    with pytest.raises(task.TaskFamilyError, match="four distinct"):
        task.public_core(duplicated)


def test_candidates_separate_train_and_hidden_probe_and_response_must_be_consistent() -> None:
    bundle = task.generate_block(SEED, 7)
    public = bundle["public_task"]
    core = task.public_core(public)
    assert core["h0"][core["train_input"]] != core["h1"][core["train_input"]]
    probe_input = bundle["probe_private"]["probe_input"]
    assert probe_input != core["train_input"]
    assert core["h0"][probe_input] != core["h1"][probe_input]
    bad = _response(public, 0)
    bad["answer_token"] = core["h1"][core["train_input"]]
    with pytest.raises(task.TaskFamilyError, match="inconsistent"):
        task.validate_training_response(public, bad)
    forged = copy.deepcopy(public)
    forged["public_core"]["h1"] = dict(forged["public_core"]["h0"])
    with pytest.raises(task.TaskFamilyError, match="differ pointwise"):
        task.public_core(forged)


def test_commitment_swaps_and_private_exposure_are_refused() -> None:
    first, second = task.generate_block(SEED, 1), task.generate_block(SEED, 2)
    swapped = copy.deepcopy(first["public_task"])
    swapped["probe_private_commitment"] = second["public_task"]["probe_private_commitment"]
    with pytest.raises(task.TaskFamilyError, match="commitment mismatch"):
        task.audit_bundle(swapped, first["evaluator_private"], first["probe_private"], first["placebo_private"])
    leaked = copy.deepcopy(first["public_task"])
    leaked["public_core"]["train_input"] = first["probe_private"]["probe_input"]
    with pytest.raises(task.TaskFamilyError):
        task.audit_bundle(leaked, first["evaluator_private"], first["probe_private"], first["placebo_private"])


def test_true_and_placebo_projections_match_shape_and_bind_same_trajectory() -> None:
    cases: dict[bool, tuple[dict[str, object], dict[str, object], dict[str, object]]] = {}
    for bundle in task.generate_study(SEED):
        public = bundle["public_task"]
        sealed = task.seal_training_response(public, _response(public, 0))
        true = evaluator.evaluate_training(public, bundle["evaluator_private"], sealed)
        placebo = evaluator.placebo_proposal_projection(public, bundle["placebo_private"], sealed)
        cases.setdefault(true["feedback_bit"] == placebo["feedback_bit"], (bundle, sealed, true))
    assert set(cases) == {False, True}
    for equal, (bundle, sealed, true) in cases.items():
        public = bundle["public_task"]
        genuine = evaluator.genuine_proposal_projection(true)
        placebo = evaluator.placebo_proposal_projection(public, bundle["placebo_private"], sealed)
        assert set(genuine) == set(placebo)
        assert genuine["trajectory_commitment"] == placebo["trajectory_commitment"] == sealed["trajectory_commitment"]
        assert len(task.canonical_json(genuine)) == len(task.canonical_json(placebo))
        assert (genuine == placebo) is equal


def test_prf_status_is_not_a_conditional_independence_or_mechanism_uniqueness_claim() -> None:
    status = task.task_family_status()
    assert "CONTENT_HASH_ONLY" in status["bundle_audit_status"]
    assert "REQUIRES_CANONICAL_CUSTODY" in status["bundle_audit_status"]
    assert "NOT_CONDITIONAL_INDEPENDENCE_PROOF" in status["theta_placebo_status"]
    assert "NOT_EVIDENCE_OF_UNIQUE" in status["mechanism_uniqueness_status"]
    assert "REQUIRES_LIFECYCLE_CHRONOLOGY_GATE" in status["probe_opening_status"]


def test_probe_offset_uses_frozen_unbiased_rejection_vector() -> None:
    assert [task._uniform_below(SEED, index, "probe-offset", 3) for index in range(12)] == [
        0, 1, 0, 0, 1, 2, 2, 2, 2, 2, 1, 0,
    ]


def test_probe_evaluator_requires_opening_and_refuses_wrong_block() -> None:
    first, second = task.generate_block(SEED, 13), task.generate_block(SEED, 14)
    opening = task.open_probe(first["public_task"], first["probe_private"], first["bundle_audit_receipt"])
    sealed_probe = task.seal_probe_response(first["public_task"], opening, first["probe_private"]["probe_answer"])
    outcome = evaluator.evaluate_probe(first["public_task"], first["probe_private"], sealed_probe)
    assert set(outcome) == {"schema_version", "probe_response_commitment", "score", "receipt_commitment"}
    assert outcome["score"] == 1
    with pytest.raises(task.TaskFamilyError, match="commitment mismatch|another public task"):
        evaluator.evaluate_probe(second["public_task"], second["probe_private"], sealed_probe)
    unsealed = {"answer_token": first["probe_private"]["probe_answer"]}
    with pytest.raises(task.TaskFamilyError):
        evaluator.evaluate_probe(first["public_task"], first["probe_private"], unsealed)
    forged_opening = copy.deepcopy(opening)
    forged_opening["probe_input"] = task.public_core(first["public_task"])["train_input"]
    opening_payload = {key: value for key, value in forged_opening.items() if key != "opening_commitment"}
    forged_opening["opening_commitment"] = task.commitment(opening_payload)
    with pytest.raises(task.TaskFamilyError, match="held-out"):
        task.seal_probe_response(first["public_task"], forged_opening, first["probe_private"]["probe_answer"])


def test_probe_open_requires_cross_private_audit_precondition_and_rejects_local_bad_shape() -> None:
    bundle = task.generate_block(SEED, 18)
    public, probe = bundle["public_task"], copy.deepcopy(bundle["probe_private"])
    with pytest.raises(task.TaskFamilyError, match="bundle_audit"):
        task.open_probe(public, probe, {})
    probe["probe_input"] = task.public_core(public)["train_input"]
    with pytest.raises(task.TaskFamilyError, match="held-out"):
        task.open_probe(public, probe, bundle["bundle_audit_receipt"])


def test_production_custody_split_has_exact_public_keys_and_blind_score() -> None:
    core = task.production_public_core(b"t" * 32, 3)
    evaluator_private = task.production_evaluator_private(b"e" * 32, core)
    challenge = task.production_probe_challenge(b"p" * 32, core)
    hidden = task.production_hidden_answer(evaluator_private, challenge, core)
    placebo = task.production_placebo_private(b"z" * 32, core)
    public = task.assemble_production_public_task(core, task.commitment(evaluator_private), task.commitment(challenge), hidden["commitment"], task.commitment(placebo))
    assert set(public) == {"schema_version", "public_core", "public_core_commitment", "evaluator_private_commitment", "probe_challenge_commitment", "hidden_answer_commitment", "placebo_private_commitment"}
    outcome = evaluator.evaluate_probe_separated(public, challenge, hidden, hidden["probe_answer"])
    assert outcome["score"] == 1 and "theta" not in outcome and "probe_answer" not in outcome
    other = task.production_probe_challenge(b"q" * 32, core)
    with pytest.raises(task.TaskFamilyError, match="challenge"):
        evaluator.evaluate_probe_separated(public, other, hidden, hidden["probe_answer"])
    assert task.production_public_core(b"u" * 32, 3) != core
    assert task.generate_block(SEED, 3)["status"] == task.COMBINED_FIXTURE_STATUS


def test_production_custody_split_refuses_malformed_or_cross_task_private_records() -> None:
    core = task.production_public_core(b"t" * 32, 3)
    evaluator_private = task.production_evaluator_private(b"e" * 32, core)
    challenge = task.production_probe_challenge(b"p" * 32, core)
    hidden = task.production_hidden_answer(evaluator_private, challenge, core)
    placebo = task.production_placebo_private(b"z" * 32, core)
    public = task.assemble_production_public_task(
        core,
        task.commitment(evaluator_private),
        task.commitment(challenge),
        hidden["commitment"],
        task.commitment(placebo),
    )

    bad_evaluator = copy.deepcopy(evaluator_private)
    bad_evaluator["theta"] = 2
    with pytest.raises(task.TaskFamilyError, match="integer 0 or 1"):
        task.production_hidden_answer(bad_evaluator, challenge, core)

    extra_evaluator = copy.deepcopy(evaluator_private)
    extra_evaluator["probe_answer"] = hidden["probe_answer"]
    with pytest.raises(task.TaskFamilyError, match="unexpected or missing fields"):
        task.production_hidden_answer(extra_evaluator, challenge, core)

    training_challenge = copy.deepcopy(challenge)
    training_challenge["probe_input"] = core["train_input"]
    with pytest.raises(task.TaskFamilyError, match="held out"):
        task.production_hidden_answer(evaluator_private, training_challenge, core)

    wrong_schema = copy.deepcopy(challenge)
    wrong_schema["schema_version"] = "hswm-dnrd5-probe-challenge-separated/v2"
    with pytest.raises(task.TaskFamilyError, match="binding mismatch"):
        task.production_hidden_answer(evaluator_private, wrong_schema, core)

    missing_answer = copy.deepcopy(hidden)
    del missing_answer["probe_answer"]
    with pytest.raises(task.TaskFamilyError, match="unexpected or missing fields"):
        evaluator.evaluate_probe_separated(public, challenge, missing_answer, core["outputs"][0])

    forged_answer = copy.deepcopy(hidden)
    forged_answer["probe_answer"] = "nonce-ffffffffffffffff"
    forged_payload = {key: value for key, value in forged_answer.items() if key != "commitment"}
    forged_answer["commitment"] = task.commitment(forged_payload)
    forged_public = copy.deepcopy(public)
    forged_public["hidden_answer_commitment"] = forged_answer["commitment"]
    with pytest.raises(task.TaskFamilyError, match="outside output domain"):
        evaluator.evaluate_probe_separated(
            forged_public, challenge, forged_answer, core["outputs"][0]
        )

    with pytest.raises(task.TaskFamilyError, match="outside public output domain"):
        evaluator.evaluate_probe_separated(
            public, challenge, hidden, "nonce-ffffffffffffffff"
        )

    extra_public = copy.deepcopy(public)
    extra_public["theta"] = evaluator_private["theta"]
    with pytest.raises(task.TaskFamilyError, match="public task shape"):
        evaluator.evaluate_probe_separated(extra_public, challenge, hidden, hidden["probe_answer"])

    other_core = task.production_public_core(b"u" * 32, 4)
    other_evaluator = task.production_evaluator_private(b"v" * 32, other_core)
    other_challenge = task.production_probe_challenge(b"w" * 32, other_core)
    other_hidden = task.production_hidden_answer(other_evaluator, other_challenge, other_core)
    cross_task_public = copy.deepcopy(public)
    cross_task_public["probe_challenge_commitment"] = task.commitment(other_challenge)
    cross_task_public["hidden_answer_commitment"] = other_hidden["commitment"]
    with pytest.raises(task.TaskFamilyError, match="binding mismatch"):
        evaluator.evaluate_probe_separated(
            cross_task_public,
            other_challenge,
            other_hidden,
            other_core["outputs"][0],
        )
