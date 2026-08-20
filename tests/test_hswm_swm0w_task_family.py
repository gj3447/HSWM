from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from hswm.experiments import swm0w_task_family as core
from hswm.experiments import swm0w_worlds as worlds


SEED = b"swm0w-occam-streamed-task-test-seed-" + b"A" * 40


@pytest.fixture(scope="module")
def task() -> core.StreamedTaskV1:
    return core.build_task_from_external_seed(SEED)


def test_public_core_is_single_task_only_and_seed_fails_closed(task) -> None:
    assert task.task_uid.startswith("swm0wt_")
    assert not hasattr(core, "build_task_family_from_external_seeds")
    assert not hasattr(core, "reveal_task_family")
    assert not hasattr(core, "TaskCommitmentRegistryV1")
    with pytest.raises(core.SWM0WTaskCoreError, match="exact bytes"):
        core.build_task_from_external_seed(bytearray(SEED))
    with pytest.raises(core.SWM0WTaskCoreError, match="at least 32"):
        core.build_task_from_external_seed(b"short")
    exact_beacon_seed = bytes(range(32))
    exact_task = core.build_task_from_external_seed(exact_beacon_seed)
    assert exact_task.target_parameters.seed_commitment_sha256 == core._seed_commitment(
        exact_beacon_seed
    )
    assert len(SEED) > 32  # Longer values are intentionally accepted byte-for-byte.


def test_cut_is_complete_9_8_8_and_splits_are_exactly_separated(task) -> None:
    cut = task.target_parameters.cut
    assert [len(cut.shift_pairs(split)) for split in worlds.SPLITS] == [9, 8, 8]
    assert set(cut.shift_pair_order) == set(itertools.product(range(5), repeat=2))
    assert len(set(cut.shift_pair_order)) == 25
    states = {}
    uids = []
    for split, expected in (("train", 5625), ("dev", 5000), ("test", 5000)):
        artifact = task.for_split(split)
        assert len(artifact.cases) == expected
        states[split] = {case.state_tuple for case in artifact.cases}
        uids.extend(case.case_uid for case in artifact.cases)
        assert artifact.target_integer_sum == sum(
            case.target_numerator for case in artifact.cases
        )
        assert artifact.target_integer_sum_of_squares == sum(
            case.target_numerator**2 for case in artifact.cases
        )
    for left, right in itertools.combinations(worlds.SPLITS, 2):
        assert states[left].isdisjoint(states[right])
    assert len(set().union(*states.values())) == 5**6
    assert len(uids) == len(set(uids)) == 5**6


def test_final_integer_tensor_minor_proves_exact_mode_rank_17(task) -> None:
    parameters = task.target_parameters
    tensor = parameters.integer_tensor
    witness = parameters.rank_witness
    assert witness is not None
    assert tensor.shape == (25, 25, 25)
    assert tensor.flags.writeable is False
    assert core._integer_array_sha256(tensor) == parameters.integer_tensor_sha256
    assert witness.integer_tensor_sha256 == parameters.integer_tensor_sha256
    unfolding = tensor.reshape(25, 625)
    minor = [
        [int(unfolding[row, column]) for column in witness.column_indices]
        for row in witness.row_indices
    ]
    assert len(minor) == len(minor[0]) == core.TARGET_CP_TERMS == 17
    for prime, recorded in witness.determinants:
        assert core._determinant_mod(minor, prime) == recorded != 0
    assert witness.canonical()["exact_mode0_rank"] == 17
    assert witness.canonical()["cp_term_upper_bound"] == 17
    assert np.all(tensor.sum(axis=0) == 0)
    assert np.all(tensor.sum(axis=1) == 0)
    assert np.all(tensor.sum(axis=2) == 0)


def test_targets_are_exact_bounded_dyadics_and_evaluator_only(task) -> None:
    parameters = task.target_parameters
    maximum = max(abs(int(value)) for value in parameters.integer_tensor.flat)
    assert 0 < math.ldexp(maximum, -parameters.scale_exponent) <= 0.5
    scope = parameters.canonical()["scope"]
    assert scope == {
        "arity": 3,
        "chronology_proven": False,
        "incidences_per_role": 1,
        "process_isolation_enforced": False,
        "sealed_evaluation_boundary": False,
        "secrecy_proven": False,
        "synthetic_target": True,
    }
    assert parameters.canonical()["evaluator_only"] is True
    assert parameters.canonical()["model_visible"] is False
    for split in task.splits:
        for case in split.cases:
            assert case.target == math.ldexp(
                case.target_numerator, -case.target_scale_exponent
            )
            assert abs(case.target) <= core.TARGET_ABS_BOUND
            assert case.target_numerator == parameters.numerator_at(case.role_values)


def test_model_boundary_contains_only_role_and_two_raw_features(task) -> None:
    forbidden = {"case_uid", "label", "seed", "split", "target", "task_uid", "uid"}
    for split in worlds.SPLITS:
        iterator = core.model_worlds_from_split(task, split)
        retained = iterator.__reduce__()[1][0]
        assert retained and all(isinstance(item, worlds.ModelWorldV1) for item in retained)
        assert not any(isinstance(item, core.TaskEvaluatorCaseV1) for item in retained)
        for world in iterator:
            payload = world.canonical()
            assert set(payload) == {"incidences", "schema_version"}
            assert all(set(row) == {"features", "role"} for row in payload["incidences"])
            assert not forbidden.intersection(payload)
            assert all(len(row["features"]) == 2 for row in payload["incidences"])
    evaluator_case = core.evaluator_cases_from_split(task, "dev")[0]
    assert evaluator_case.target_numerator
    assert "target" not in json.dumps(evaluator_case.model_visible(), sort_keys=True)


def test_receipts_are_deterministic_frozen_and_fail_closed(task) -> None:
    assert task.task_sha256 == core.canonical_sha256(task.unsigned_canonical())
    assert task.target_parameters.receipt_sha256 == core.canonical_sha256(
        task.target_parameters.unsigned_canonical()
    )
    for split in task.splits:
        assert split.receipt_sha256 == core.canonical_sha256(split.unsigned_canonical())
        assert all(
            case.receipt_sha256 == core.canonical_sha256(case.unsigned_canonical())
            for case in split.cases
        )
    with pytest.raises(FrozenInstanceError):
        task.task_sha256 = "0" * 64
    with pytest.raises(ValueError):
        task.target_parameters.integer_tensor.setflags(write=True)
    with pytest.raises(core.SWM0WTaskCoreError, match="task receipt"):
        replace(task, task_sha256="0" * 64)
    with pytest.raises(core.SWM0WTaskCoreError, match="exact target moments"):
        replace(task.for_split("dev"), target_integer_sum=0)
    witness = task.target_parameters.rank_witness
    assert witness is not None
    with pytest.raises(core.SWM0WTaskCoreError, match="final-minor receipt"):
        replace(witness, receipt_sha256="0" * 64)
    changed = tuple(
        (prime, determinant + 1 if determinant + 1 < prime else 1)
        for prime, determinant in witness.determinants
    )
    unsigned = witness.unsigned_canonical()
    unsigned["determinants"] = dict(changed)
    forged_witness = core.FinalMinorWitnessV1(
        integer_tensor_sha256=witness.integer_tensor_sha256,
        row_indices=witness.row_indices,
        column_indices=witness.column_indices,
        determinants=changed,
        receipt_sha256=core.canonical_sha256(unsigned),
    )
    with pytest.raises(core.SWM0WTaskCoreError, match="minor does not verify"):
        replace(task.target_parameters, rank_witness=forged_witness)


def test_evaluator_score_is_deterministic_aggregate_not_a_seal(task) -> None:
    cases = task.for_split("test").cases
    predictions = np.asarray([case.target for case in cases], dtype=np.float64)
    score = core.score_task_predictions(task, "test", predictions)
    replay = core.score_task_predictions(task, "test", predictions.copy())
    assert score.mean_squared_error == 0.0
    assert score.canonical() == replay.canonical()
    assert score.prediction_count == 5000
    assert score.canonical()["aggregate_only"] is True
    assert score.canonical()["process_isolation_enforced"] is False
    assert score.canonical()["sealed_evaluation_boundary"] is False
    with pytest.raises(core.SWM0WTaskCoreError, match="exact one-dimensional"):
        core.score_task_predictions(task, "test", predictions[:-1])
    predictions[0] = np.nan
    with pytest.raises(core.SWM0WTaskCoreError, match="finite"):
        core.score_task_predictions(task, "test", predictions)
    with pytest.raises(core.SWM0WTaskCoreError, match="score receipt"):
        replace(score, receipt_sha256="0" * 64)


def test_artifact_hashes_ignore_openblas_cpu_dispatch() -> None:
    script = (
        "import json;"
        "from hswm.experiments.swm0w_task_family import build_task_from_external_seed as b;"
        f"t=b(bytes.fromhex('{SEED.hex()}'));"
        "print(json.dumps([t.task_sha256,t.target_parameters.integer_tensor_sha256,"
        "t.target_parameters.rank_witness.receipt_sha256]))"
    )
    outputs = []
    for core_type in ("Haswell", "SkylakeX"):
        environment = os.environ.copy()
        environment["OPENBLAS_CORETYPE"] = core_type
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        outputs.append(json.loads(completed.stdout.strip().splitlines()[-1]))
    assert outputs[0] == outputs[1]


def test_source_is_occam_bounded_and_has_no_numpy_linalg() -> None:
    source_path = Path(core.__file__)
    source = source_path.read_text(encoding="utf-8")
    test_source = Path(__file__).read_text(encoding="utf-8")
    assert len(source.splitlines()) < 1200
    assert len(test_source.splitlines()) < 300
    assert "np.linalg" not in source
    assert "numpy.linalg" not in source
    assert "SVD" not in source
    assert "bootstrap" not in source.lower()
