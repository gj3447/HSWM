from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import itertools
import json

import numpy as np
import pytest

from hswm.experiments import swm0w_s2s_worlds as worlds


SEED = b"swm0w-s2s-focused-tests-external-seed-v1"
H = (
    (-2, -1, 0, 1, 2),
    (0, 3, -4, -1, 2),
    (7, -7, -6, 5, 1),
    (3, -3, 2, -7, 5),
)
RESIDUES = {"train": (0, 1), "dev": (2,), "test": (3, 4)}


def _factor(kind: str, role: int, channel: int, rank: int) -> tuple[int, ...]:
    offset = (role + channel) % 4
    return H[(offset + rank + (2 if kind == "P" else 0)) % 4]


def _doc_q_only_target(values: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    outputs = []
    for role in range(3):
        for member in range(2):
            hidden = [0] * 16
            recipient = values[2 * role + member]
            comember = values[2 * role + 1 - member]
            for channel in range(2):
                for rank in range(2):
                    value = (
                        _factor("P", role, channel, rank)[recipient]
                        * _factor("T", role, channel, rank)[comember]
                    )
                    for source in range(3):
                        if source != role:
                            table = _factor("T", source, channel, rank)
                            value *= table[values[2 * source]] + table[values[2 * source + 1]]
                    hidden[2 * channel + rank] = value
            outputs.append((sum(hidden[0:2]), sum(hidden[2:4])))
            assert hidden[4:] == [0] * 12
    return tuple(outputs)


@pytest.fixture(scope="module")
def task() -> worlds.TaskSpecV1:
    return worlds.generate_task(external_seed=SEED)


@pytest.fixture(scope="module")
def domain(task):
    cases = tuple(task.iter_cases())
    raw = np.asarray([case.world.raw_values for case in cases], dtype=np.int64)
    targets = np.asarray([case.target_numerators for case in cases], dtype=np.int64)
    syndrome = np.sum(raw, axis=1) % 5
    masks = {split: np.isin(syndrome, residues) for split, residues in RESIDUES.items()}
    return cases, raw, targets, masks


def test_centered_contrasts_are_the_exact_public_basis() -> None:
    rows = tuple(worlds.centered_contrasts(value) for value in range(5))
    assert rows == (
        (1, 0, 0, 0),
        (0, 1, 0, 0),
        (0, 0, 1, 0),
        (0, 0, 0, 1),
        (-1, -1, -1, -1),
    )
    assert np.sum(np.asarray(rows), axis=0).tolist() == [0, 0, 0, 0]
    for bad in (-1, 5, True, 1.0, "1"):
        with pytest.raises(worlds.SWM0WS2SWorldError):
            worlds.centered_contrasts(bad)


def test_fixed_frame_and_tables_reconstruct_the_stated_algebra(task) -> None:
    frame = np.asarray(H, dtype=np.int64)
    assert np.array_equal(frame @ frame.T, np.diag((10, 30, 160, 96)))
    assert worlds.FACTOR_FRAME == H
    factors = task.factor_mapping()
    assert len(factors) == 24
    for kind, role, channel, rank in itertools.product(("P", "T"), range(3), range(2), range(2)):
        assert factors[f"{kind}:r{role}:c{channel}:k{rank}"] == _factor(
            kind, role, channel, rank
        )
    assert all(sum(table) == 0 for table in H)
    assert worlds.ANALYTIC_NUMERATOR_BOUND == 19_208 < 2**15
    assert dict(task.analytic_family)["seed_effect"].endswith("NO_TARGET_DIVERSITY")


def test_every_world_matches_doc_formula_and_exact_q_only_t16(task, domain) -> None:
    cases, _, targets, _ = domain
    independently_built = np.empty_like(targets)
    for index, case in enumerate(cases):
        independently_built[index] = _doc_q_only_target(case.world.raw_values)
    assert np.array_equal(targets, independently_built)
    assert worlds.T16_HIDDEN_WIDTH == 16
    assert worlds.T16_ACTIVE_DIMENSIONS == 4
    assert int(np.max(np.abs(targets))) == 5_560


def test_split_is_complete_fixed_and_explicitly_inferable(task, domain) -> None:
    cases, raw, _, masks = domain
    assert len(cases) == 5**6
    assert {split: int(np.count_nonzero(mask)) for split, mask in masks.items()} == {
        "train": 6_250,
        "dev": 3_125,
        "test": 6_250,
    }
    for case in cases:
        inferred = next(
            split
            for split, residues in RESIDUES.items()
            if sum(case.world.raw_values) % 5 in residues
        )
        assert case.split == inferred
        assert len(case.target_numerators) == 6
        assert all(len(row) == 2 for row in case.target_numerators)
    assert len({tuple(row) for row in raw}) == 5**6
    assert dict(task.analytic_family)["split_information"].endswith("NON_SECRET")


def test_model_envelope_excludes_evaluator_fields_but_not_raw_values(task) -> None:
    case = task.case((4, 0, 3, 1, 2, 4))
    payload = case.model_visible()
    assert set(payload) == {"roles", "schema_version"}
    assert [row["role"] for row in payload["roles"]] == list(worlds.ROLES)
    assert all(set(row) == {"members", "role"} for row in payload["roles"])
    assert all(
        set(member) == {"centered_contrasts", "raw"}
        for row in payload["roles"]
        for member in row["members"]
    )
    encoded = json.dumps(payload, sort_keys=True)
    assert all(
        field not in encoded
        for field in ("split", "syndrome", "target", "seed", "factor")
    )
    recovered = tuple(member["raw"] for row in payload["roles"] for member in row["members"])
    assert sum(recovered) % 5 == case.world.syndrome


def test_all_one_to_five_coordinate_marginals_are_uniform(domain) -> None:
    _, raw, _, masks = domain
    for split, residues in RESIDUES.items():
        selected = raw[masks[split]]
        for order in range(1, 6):
            expected = len(residues) * 5 ** (5 - order)
            for coordinates in itertools.combinations(range(6), order):
                code = np.zeros(len(selected), dtype=np.int64)
                for coordinate in coordinates:
                    code = 5 * code + selected[:, coordinate]
                assert np.all(np.bincount(code, minlength=5**order) == expected)


def test_centering_star_contingencies_and_rank_are_recomputed(domain) -> None:
    _, raw, targets, masks = domain
    for mask in masks.values():
        assert np.array_equal(np.sum(targets[mask], axis=0), np.zeros((6, 2), dtype=np.int64))
        assert np.all(np.sum(targets[mask] ** 2, axis=0) > 0)
        for output in range(6):
            for channel in range(2):
                vector = targets[:, output, channel]
                for other in range(6):
                    if other == output:
                        continue
                    table = np.zeros((5, 5), dtype=np.int64)
                    np.add.at(table, (raw[mask, output], raw[mask, other]), vector[mask])
                    assert not np.any(table)
    for output, channel in itertools.product(range(6), range(2)):
        tensor = targets[:, output, channel].reshape((5,) * 6)
        matrix = np.moveaxis(tensor, output, 0).reshape(5, -1)
        witness = False
        for left, right in itertools.combinations(range(5), 2):
            nonzero = np.flatnonzero((matrix[left] != 0) | (matrix[right] != 0))
            if nonzero.size:
                column = int(nonzero[0])
                determinants = (
                    matrix[left, column] * matrix[right]
                    - matrix[right, column] * matrix[left]
                )
                if np.any(determinants):
                    witness = True
                    break
        assert witness  # formula already supplies rank <=2; this exact minor gives >=2


def test_unrestricted_pair_span_has_an_independent_counterexample(domain) -> None:
    _, raw, targets, masks = domain
    witness = None
    for split, mask in masks.items():
        for output, channel in itertools.product(range(6), range(2)):
            for left, right in itertools.combinations(
                (coordinate for coordinate in range(6) if coordinate != output), 2
            ):
                table = np.zeros((5, 5), dtype=np.int64)
                np.add.at(
                    table,
                    (raw[mask, left], raw[mask, right]),
                    targets[mask, output, channel],
                )
                nonzero = np.argwhere(table != 0)
                if nonzero.size:
                    levels = tuple(int(value) for value in nonzero[0])
                    witness = (split, output, channel, left, right, levels, int(table[levels]))
                    break
            if witness:
                break
        if witness:
            break
    assert witness is not None
    assert witness[1] not in witness[3:5]
    assert witness[-1] != 0


def test_all_eight_member_permutations_are_exactly_equivariant(domain) -> None:
    _, raw, targets, _ = domain
    weights = np.asarray([5 ** (5 - coordinate) for coordinate in range(6)])
    assert len(worlds.ALL_MEMBER_PERMUTATIONS) == 8
    for action in worlds.ALL_MEMBER_PERMUTATIONS:
        permuted = raw.copy()
        output_order = list(range(6))
        for role, swap in enumerate(action.swaps):
            if swap:
                left = 2 * role
                permuted[:, [left, left + 1]] = permuted[:, [left + 1, left]]
                output_order[left], output_order[left + 1] = output_order[left + 1], output_order[left]
        indices = permuted @ weights
        assert np.array_equal(targets[indices], targets[:, output_order])


def test_exact_broadcast_and_both_role_cycle_floors(domain) -> None:
    _, raw, targets, masks = domain
    broadcast = []
    for mask in masks.values():
        for role, channel in itertools.product(range(3), range(2)):
            truth = targets[mask, 2 * role : 2 * role + 2, channel]
            difference = truth[:, 0] - truth[:, 1]
            broadcast.append(
                Fraction(int(np.sum(difference**2)), 2 * int(np.sum(truth**2)))
            )
    assert min(broadcast) == Fraction(5_187_851, 10_706_138)

    minima = []
    for cycle in ((1, 2, 0), (2, 0, 1)):
        permuted = np.empty_like(raw)
        for source, destination in enumerate(cycle):
            permuted[:, 2 * destination : 2 * destination + 2] = raw[:, 2 * source : 2 * source + 2]
        cycled = np.asarray([_doc_q_only_target(tuple(row)) for row in permuted])
        restored = np.empty_like(cycled)
        for source, destination in enumerate(cycle):
            restored[:, 2 * source : 2 * source + 2] = cycled[:, 2 * destination : 2 * destination + 2]
        damage = []
        for mask in masks.values():
            for role, channel in itertools.product(range(3), range(2)):
                truth = targets[mask, 2 * role : 2 * role + 2, channel]
                prediction = restored[mask, 2 * role : 2 * role + 2, channel]
                damage.append(
                    Fraction(int(np.sum((truth - prediction) ** 2)), int(np.sum(truth**2)))
                )
        minima.append((cycle, min(damage)))
    assert minima == [
        ((1, 2, 0), Fraction(21_660_571, 18_632_331)),
        ((2, 0, 1), Fraction(85_553, 73_855)),
    ]


def test_manifest_is_portable_and_seed_only_changes_identity(task) -> None:
    replay = worlds.generate_fixture(external_seed=SEED)
    assert replay == task
    assert task.manifest_sha256 == "4ff86e507d30adf181793d3b21b5a772faf29105f82667a8bca361b5f5e4428c"
    assert worlds.canonical_sha256(task.manifest_payload()) == task.manifest_sha256
    assert json.loads(worlds.canonical_json(task.canonical())) == task.canonical()
    other = worlds.generate_task(external_seed=b"swm0w-s2s-second-external-seed-material-v1")
    assert other.seed_commitment_sha256 != task.seed_commitment_sha256
    assert other.manifest_sha256 != task.manifest_sha256
    assert other.factor_tables == task.factor_tables
    assert other.case((0, 1, 2, 3, 4, 0)).target_numerators == task.case(
        (0, 1, 2, 3, 4, 0)
    ).target_numerators


def test_frozen_exact_types_and_single_manifest_hash_reject_forgery(task) -> None:
    case = task.case((0, 1, 2, 3, 4, 0))
    with pytest.raises(FrozenInstanceError):
        case.split = "test"
    for bad in ((0, 1, 2, 3, 4, True), [0, 1, 2, 3, 4, 0]):
        with pytest.raises(worlds.SWM0WS2SWorldError):
            worlds.ModelWorldV1(bad)
    with pytest.raises(worlds.SWM0WS2SWorldError):
        worlds.MemberPermutationV1((False, 0, True))
    with pytest.raises(worlds.SWM0WS2SWorldError):
        replace(case, split="test")
    forged_targets = tuple((0, 0) for _ in range(6))
    with pytest.raises(worlds.SWM0WS2SWorldError, match="fixed task"):
        replace(case, target_numerators=forged_targets)
    with pytest.raises(worlds.SWM0WS2SWorldError, match="manifest"):
        replace(task, manifest_sha256="0" * 64)
    forged_split = (("train", (0, True)), ("dev", (2,)), ("test", (3, 4)))
    forged_payload = task.manifest_payload()
    forged_payload["split_residues"] = {
        "train": [0, True],
        "dev": [2],
        "test": [3, 4],
    }
    with pytest.raises(worlds.SWM0WS2SWorldError, match="fixed split"):
        replace(
            task,
            split_residues=forged_split,
            manifest_sha256=worlds.canonical_sha256(forged_payload),
        )
    with pytest.raises(worlds.SWM0WS2SWorldError):
        worlds.generate_task(external_seed=b"too-short")

    class ForgedWorld(worlds.ModelWorldV1):
        pass

    forged = ForgedWorld((0, 1, 2, 3, 4, 0))
    with pytest.raises(worlds.SWM0WS2SWorldError, match="exact ModelWorldV1"):
        task.target(forged)
    with pytest.raises(worlds.SWM0WS2SWorldError, match="exact ModelWorldV1"):
        worlds.ALL_MEMBER_PERMUTATIONS[0].apply_world(forged)


def test_status_remains_integrity_only_unjudged(task) -> None:
    assert worlds.SCIENTIFIC_STATUS == "UNJUDGED_INTEGRITY_ONLY"
    assert dict(task.analytic_family)["scientific_status"] == worlds.SCIENTIFIC_STATUS
    assert not hasattr(task, "audit")
    assert not hasattr(task.case((0, 0, 0, 0, 0, 0)), "receipt_sha256")
