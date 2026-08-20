from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pytest

from hswm.experiments import swm0w_s2s_family as family
from hswm.experiments import swm0w_s2s_worlds as worlds


SEED = b"swm0w-s2s-v2-family-smoke-seed-000000000000"
H = np.asarray(
    (
        (-2, -1, 0, 1, 2),
        (0, 3, -4, -1, 2),
        (7, -7, -6, 5, 1),
        (3, -3, 2, -7, 5),
    ),
    dtype=np.int64,
)


def _reference_gain_table(seed: bytes, draw_index: int) -> tuple[int, ...]:
    material = (
        b"hswm-swm0w-s2s-family-gain-draw/v2\x00"
        + len(seed).to_bytes(8, "big")
        + seed
        + draw_index.to_bytes(8, "big")
    )
    value = int.from_bytes(hashlib.shake_256(material).digest(5), "big") >> 7
    digits = tuple((value >> (3 * shift)) & 7 for shift in reversed(range(11)))
    return (8, *(8 + digit for digit in digits))


def _reference_q(seed: bytes, draw_index: int) -> tuple[int, int, int]:
    material = (
        b"hswm-swm0w-s2s-family-split-q-draw/v2\x00"
        + len(seed).to_bytes(8, "big")
        + seed
        + draw_index.to_bytes(8, "big")
    )
    value = hashlib.shake_256(material).digest(1)[0] >> 4
    return 1, 1 + (value >> 2), 1 + (value & 3)


def _reference_targets(raw: np.ndarray, gains: tuple[int, ...]) -> np.ndarray:
    targets = np.empty((len(raw), 6, 2), dtype=np.int64)
    for role, member, channel in itertools.product(range(3), range(2), range(2)):
        recipient_index = 2 * role + member
        recipient = raw[:, recipient_index]
        comember = raw[:, 2 * role + 1 - member]
        total = np.zeros(len(raw), dtype=np.int64)
        for rank in range(2):
            offset = (role + channel) % 4
            p = H[(offset + rank + 2) % 4]
            t = H[(offset + rank) % 4]
            value = gains[4 * role + 2 * channel + rank] * p[recipient] * t[comember]
            for source in range(3):
                if source != role:
                    source_table = H[((source + channel) % 4 + rank) % 4]
                    value = value * (
                        source_table[raw[:, 2 * source]]
                        + source_table[raw[:, 2 * source + 1]]
                    )
            total += value
        targets[:, recipient_index, channel] = total
    return targets


def _component_basis(raw: np.ndarray) -> np.ndarray:
    """Return the independently constructed 12-coefficient target basis."""

    basis = np.zeros((len(raw), 6, 2, 12), dtype=np.int64)
    for role, member, channel, rank in itertools.product(
        range(3), range(2), range(2), range(2)
    ):
        recipient_index = 2 * role + member
        recipient = raw[:, recipient_index]
        comember = raw[:, 2 * role + 1 - member]
        offset = (role + channel) % 4
        value = (
            H[(offset + rank + 2) % 4][recipient]
            * H[(offset + rank) % 4][comember]
        )
        for source in range(3):
            if source != role:
                table = H[((source + channel) % 4 + rank) % 4]
                value = value * (
                    table[raw[:, 2 * source]]
                    + table[raw[:, 2 * source + 1]]
                )
        coefficient = 4 * role + 2 * channel + rank
        basis[:, recipient_index, channel, coefficient] = value
    return basis


def _gram(values: np.ndarray) -> np.ndarray:
    return values.T @ values


def _bareiss_determinant(matrix: np.ndarray) -> int:
    values = [[int(value) for value in row] for row in matrix.tolist()]
    size = len(values)
    if size == 0:
        return 1
    sign = 1
    previous = 1
    for pivot_index in range(size - 1):
        if values[pivot_index][pivot_index] == 0:
            swap = next(
                (
                    row
                    for row in range(pivot_index + 1, size)
                    if values[row][pivot_index] != 0
                ),
                None,
            )
            if swap is None:
                return 0
            values[pivot_index], values[swap] = values[swap], values[pivot_index]
            sign = -sign
        pivot = values[pivot_index][pivot_index]
        for row in range(pivot_index + 1, size):
            for column in range(pivot_index + 1, size):
                values[row][column] = (
                    values[row][column] * pivot
                    - values[row][pivot_index] * values[pivot_index][column]
                ) // previous
        previous = pivot
    return sign * values[-1][-1]


def _is_exactly_positive_definite(matrix: np.ndarray) -> bool:
    return all(
        _bareiss_determinant(matrix[:order, :order]) > 0
        for order in range(1, len(matrix) + 1)
    )


def _syndrome(raw: np.ndarray, coefficients: tuple[int, int, int]) -> np.ndarray:
    return sum(
        coefficients[role]
        * (raw[:, 2 * role].astype(np.int64) + raw[:, 2 * role + 1])
        for role in range(3)
    ) % 5


def _masks(task: family.TaskSpecV2, raw: np.ndarray) -> dict[str, np.ndarray]:
    syndrome = _syndrome(raw, task.split_coefficients)
    return {
        split: np.isin(syndrome, np.asarray(residues, dtype=np.int64))
        for split, residues in task.split_residues
    }


@pytest.fixture(scope="module")
def task() -> family.TaskSpecV2:
    return family.generate_task(external_seed=SEED, draw_index=0)


@pytest.fixture(scope="module")
def finite_domain(task):
    raw = np.indices((5,) * 6, dtype=np.int8).reshape(6, -1).T
    targets = _reference_targets(raw, task.rank_gains)
    return raw, targets, _masks(task, raw)


def test_definition_is_one_fixed_frame_and_certificate_is_bounded() -> None:
    assert np.array_equal(H @ H.T, np.diag((10, 30, 160, 96)))
    assert family.TARGET_POPULATION_SIZE == 2**33
    assert family.SPLIT_POPULATION_SIZE == 480
    assert family.TARGET_SCALE_EXPONENT == 19
    assert family.ANALYTIC_NUMERATOR_BOUND == 15 * 19_208 == 288_120 < 2**19
    definition = family.family_definition_payload()
    assert definition["sampling_scope"] == (
        "INDEXED_PSEUDORANDOM_WITH_REPLACEMENT_FROM_ONE_FIXED_FEATURE_FRAME"
    )
    assert definition["inference_boundary"] == (
        "TASK_BOOTSTRAP_IS_PROTOCOL_LEVEL_AND_CONDITIONAL_ON_THIS_GENERATOR"
    )
    assert definition["seed_generator"]["duplicate_semantics"]["sampling_action"] == (
        "RETAIN_DRAW_NEVER_SKIP_NEVER_REROLL"
    )
    assert definition["seed_generator"]["allocation_draw"][
        "rejection_byte_budget"
    ] == 4_096
    assert definition["scientific_status"] == "UNJUDGED_TASK_FAMILY_ONLY"
    assert family.canonical_sha256(definition) == family.FAMILY_DEFINITION_SHA256
    assert family.FAMILY_DEFINITION_SHA256 == (
        "9eea937e0a40511b1fd035e048a6ce6ce4c97898a5eafb86176f4d67059a413b"
    )
    certificate = family.family_certificate_payload()
    assert certificate["family_definition_sha256"] == family.FAMILY_DEFINITION_SHA256
    assert family.canonical_sha256(certificate) == family.FAMILY_CERTIFICATE_SHA256
    assert family.FAMILY_CERTIFICATE_SHA256 == (
        "a27049ad345be37007dc3099aafa58f957ee851619f9de55aaac69b3589c2329"
    )
    assert certificate["exact_minima_scope"] == (
        "PRECOMPUTED_EXACT_FAMILY_MATH_AUDIT_CONSTANTS"
    )
    assert Fraction(*family.BROADCAST_DAMAGE_MINIMUM) > Fraction(2, 5)
    for _, numerator, denominator in family.ROLE_CYCLE_DAMAGE_MINIMA:
        assert Fraction(numerator, denominator) > Fraction(4, 5)


def test_runtime_source_has_no_duplicate_string_keys_in_dict_literals() -> None:
    source_path = Path(family.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [
            key.value
            for key in node.keys
            if isinstance(key, ast.Constant) and type(key.value) is str
        ]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            violations.append((node.lineno, duplicates))
    assert violations == []


def test_definition_binds_executable_generator_behavior_vectors() -> None:
    expected = {
        "draws": [
            {
                "allocation_index": 2,
                "draw_index": 0,
                "rank_gains": [8, 10, 14, 13, 15, 12, 13, 8, 12, 13, 15, 12],
                "split_coefficients": [1, 2, 2],
            },
            {
                "allocation_index": 22,
                "draw_index": 1,
                "rank_gains": [8, 10, 14, 9, 13, 8, 11, 10, 9, 14, 15, 8],
                "split_coefficients": [1, 4, 3],
            },
            {
                "allocation_index": 6,
                "draw_index": 2**64 - 1,
                "rank_gains": [8, 15, 13, 9, 11, 11, 14, 13, 9, 8, 10, 10],
                "split_coefficients": [1, 3, 1],
            },
        ],
        "external_seed_hex": (
            "000102030405060708090a0b0c0d0e0f"
            "101112131415161718191a1b1c1d1e1f"
        ),
        "seed_commitment_sha256": (
            "f67ce7e55e476ffd428ce1bfd27a7dc03fe37edb2d2d2655258f34e15e7b52f5"
        ),
    }
    generator = family.family_definition_payload()["seed_generator"]
    assert generator["behavior_vectors"] == expected
    seed = bytes.fromhex(expected["external_seed_hex"])
    assert family._seed_commitment(seed) == expected["seed_commitment_sha256"]
    for vector in expected["draws"]:
        draw_index = vector["draw_index"]
        assert list(family._derive_rank_gains(seed, draw_index)) == vector["rank_gains"]
        assert list(family._derive_split_coefficients(seed, draw_index)) == vector[
            "split_coefficients"
        ]
        assert family._derive_allocation_index(seed, draw_index) == vector[
            "allocation_index"
        ]
        task = family.generate_task(external_seed=seed, draw_index=draw_index)
        assert list(task.rank_gains) == vector["rank_gains"]
        assert list(task.split_coefficients) == vector["split_coefficients"]
        assert task.split_residues == family.SPLIT_ALLOCATIONS[
            vector["allocation_index"]
        ]


@pytest.mark.parametrize(
    "domain_name",
    (
        "_SEED_COMMITMENT_DOMAIN",
        "_GAIN_DRAW_DOMAIN",
        "_SPLIT_Q_DRAW_DOMAIN",
        "_SPLIT_ALLOCATION_DRAW_DOMAIN",
    ),
)
def test_each_literal_domain_mutation_changes_definition_sha(monkeypatch, domain_name) -> None:
    baseline = family.FAMILY_DEFINITION_SHA256
    value = getattr(family, domain_name)
    monkeypatch.setattr(family, domain_name, value + b"mutation")
    assert family.canonical_sha256(family.family_definition_payload()) != baseline


@pytest.mark.parametrize(
    "table_name",
    ("GAIN_ORDER", "SPLIT_COEFFICIENTS", "SPLIT_ALLOCATIONS"),
)
def test_each_ordered_generator_table_mutation_changes_definition_sha(
    monkeypatch, table_name
) -> None:
    baseline = family.FAMILY_DEFINITION_SHA256
    value = getattr(family, table_name)
    monkeypatch.setattr(family, table_name, tuple(reversed(value)))
    assert family.canonical_sha256(family.family_definition_payload()) != baseline


def test_seed_draw_matches_a_separate_reference_and_golden_manifest(task) -> None:
    assert task.rank_gains == _reference_gain_table(SEED, 0)
    assert task.split_coefficients == _reference_q(SEED, 0)
    assert task.rank_gains == (8, 11, 11, 10, 10, 11, 13, 14, 8, 15, 13, 13)
    assert task.split_coefficients == (1, 3, 2)
    assert task.split_residues == (
        ("train", (0, 1)),
        ("dev", (2,)),
        ("test", (3, 4)),
    )
    assert task.structural_target_sha256 == (
        "e6a2a0bb0dd8907800c31a80d62e2ab63979e1455fe7fdb7d68f65981f95c18a"
    )
    assert task.structural_task_sha256 == (
        "ac538c1f3a31512abfe13ad7fb0143863883bde7e99e886a8d493a00b84698d4"
    )
    assert task.manifest_sha256 == (
        "fe7c7dff00accf3c92c83074abfadcf04d0df36540d2621b20c8a6a48c695a39"
    )
    assert family.generate_task(external_seed=SEED, draw_index=0) == task
    assert json.loads(worlds.canonical_json(task.canonical())) == task.canonical()


def test_all_seed_fields_are_domain_separated_and_unbiased_by_construction(task) -> None:
    draws = tuple(family.generate_task(external_seed=SEED, draw_index=i) for i in range(16))
    assert [draw.draw_index for draw in draws] == list(range(16))
    assert all(
        draw.rank_gains == _reference_gain_table(SEED, i)
        for i, draw in enumerate(draws)
    )
    assert all(
        draw.split_coefficients == _reference_q(SEED, i)
        for i, draw in enumerate(draws)
    )
    assert len({draw.rank_gains for draw in draws}) == 16
    assert len({(draw.split_coefficients, draw.split_residues) for draw in draws}) > 1
    assert all(draw.rank_gains[0] == 8 for draw in draws)
    assert all(all(8 <= gain <= 15 for gain in draw.rank_gains[1:]) for draw in draws)


def test_allocation_rejection_consumes_the_next_xof_byte(monkeypatch) -> None:
    class FakeXOF:
        prefix = bytes((255, 240, 29))

        def digest(self, length: int) -> bytes:
            return self.prefix[:length]

    monkeypatch.setattr(family, "_xof", lambda *_: FakeXOF())
    assert family._derive_allocation_index(SEED, 0) == 29


def test_allocation_rejection_budget_fails_closed(monkeypatch) -> None:
    class AllRejectedXOF:
        def digest(self, length: int) -> bytes:
            return bytes((255,)) * length

    monkeypatch.setattr(family, "_xof", lambda *_: AllRejectedXOF())
    with pytest.raises(family.SWM0WS2SFamilyError, match="budget exhausted"):
        family._derive_allocation_index(SEED, 0)


def test_batch_retains_and_records_duplicate_indexed_draws(monkeypatch) -> None:
    monkeypatch.setattr(
        family,
        "_derive_rank_gains",
        lambda _seed, _index: (8,) * 12,
    )
    monkeypatch.setattr(
        family,
        "_derive_split_coefficients",
        lambda _seed, _index: (1, 1, 1),
    )
    monkeypatch.setattr(family, "_derive_allocation_index", lambda _seed, _index: 0)
    batch = family.generate_task_batch(external_seed=SEED, count=4)
    assert len(batch.tasks) == 4
    assert [task.draw_index for task in batch.tasks] == [0, 1, 2, 3]
    assert batch.duplicate_structural_target_draws == ((1, 0), (2, 0), (3, 0))
    assert batch.duplicate_structural_task_draws == ((1, 0), (2, 0), (3, 0))
    assert len({task.manifest_sha256 for task in batch.tasks}) == 4
    assert family.canonical_sha256(batch.batch_payload()) == batch.batch_sha256


def test_structural_hashes_separate_target_split_and_provenance(task) -> None:
    alternate_split = family.SPLIT_ALLOCATIONS[1]
    split_variant = family._build_task(
        seed_commitment_sha256=task.seed_commitment_sha256,
        draw_index=task.draw_index,
        rank_gains=task.rank_gains,
        split_coefficients=task.split_coefficients,
        split_residues=alternate_split,
    )
    assert split_variant.structural_target_sha256 == task.structural_target_sha256
    assert split_variant.structural_task_sha256 != task.structural_task_sha256

    gains = list(task.rank_gains)
    gains[-1] = 8 if gains[-1] != 8 else 9
    target_variant = family._build_task(
        seed_commitment_sha256=task.seed_commitment_sha256,
        draw_index=task.draw_index,
        rank_gains=tuple(gains),
        split_coefficients=task.split_coefficients,
        split_residues=task.split_residues,
    )
    assert target_variant.structural_target_sha256 != task.structural_target_sha256

    provenance_variant = family._build_task(
        seed_commitment_sha256="0" * 64,
        draw_index=1,
        rank_gains=task.rank_gains,
        split_coefficients=task.split_coefficients,
        split_residues=task.split_residues,
    )
    assert provenance_variant.structural_target_sha256 == task.structural_target_sha256
    assert provenance_variant.structural_task_sha256 == task.structural_task_sha256
    assert provenance_variant.manifest_sha256 != task.manifest_sha256


def test_all_480_normalized_split_functions_are_unique_and_balanced() -> None:
    raw = np.indices((5,) * 6, dtype=np.int8).reshape(6, -1).T
    fingerprints = set()
    for coefficients in family.SPLIT_COEFFICIENTS:
        syndrome = _syndrome(raw, coefficients)
        for allocation in family.SPLIT_ALLOCATIONS:
            labels = np.empty(len(raw), dtype=np.uint8)
            for label, (_, residues) in enumerate(allocation):
                labels[np.isin(syndrome, residues)] = label
            fingerprints.add(hashlib.sha256(labels.tobytes()).digest())
            assert np.bincount(labels, minlength=3).tolist() == [6250, 3125, 6250]
    assert len(fingerprints) == 480

    # The completion coordinate has a nonzero coefficient, so every assignment
    # to at most five coordinates has the exact expected number of completions.
    for coefficients in family.SPLIT_COEFFICIENTS:
        syndrome = _syndrome(raw, coefficients)
        for residues in ((0,), (0, 1)):
            selected = raw[np.isin(syndrome, residues)]
            for order in range(1, 6):
                expected = len(residues) * 5 ** (5 - order)
                for coordinates in itertools.combinations(range(6), order):
                    code = np.zeros(len(selected), dtype=np.int64)
                    for coordinate in coordinates:
                        code = 5 * code + selected[:, coordinate]
                    assert np.all(np.bincount(code, minlength=5**order) == expected)


def test_runtime_target_matches_reference_formula_and_bound(task, finite_domain) -> None:
    raw, reference, _ = finite_domain
    sample_indices = tuple(range(0, len(raw), 97))
    runtime = np.asarray(
        [
            task.target(worlds.ModelWorldV1(tuple(int(value) for value in raw[index])))
            for index in sample_indices
        ],
        dtype=np.int64,
    )
    assert np.array_equal(runtime, reference[np.asarray(sample_indices)])
    assert int(np.max(np.abs(reference))) == 61_088
    assert int(np.max(np.abs(reference))) < family.ANALYTIC_NUMERATOR_BOUND
    assert task.gain_mapping() == dict(zip(family.GAIN_ORDER, task.rank_gains, strict=True))
    assert all(
        task.gain(role, channel, rank) == task.rank_gains[4 * role + 2 * channel + rank]
        for role, channel, rank in family.GAIN_ORDER
    )


def test_centering_star_orthogonality_and_exact_rank_two(finite_domain) -> None:
    raw, targets, masks = finite_domain
    for mask in masks.values():
        assert np.array_equal(np.sum(targets[mask], axis=0), np.zeros((6, 2), dtype=np.int64))
        assert np.all(np.sum(targets[mask] ** 2, axis=0) > 0)
        for output, channel in itertools.product(range(6), range(2)):
            vector = targets[:, output, channel]
            for other in range(6):
                if other == output:
                    continue
                contingency = np.zeros((5, 5), dtype=np.int64)
                np.add.at(
                    contingency,
                    (raw[mask, output], raw[mask, other]),
                    vector[mask],
                )
                assert not np.any(contingency)

    for output, channel in itertools.product(range(6), range(2)):
        matrix = np.moveaxis(
            targets[:, output, channel].reshape((5,) * 6), output, 0
        ).reshape(5, -1)
        exact_nonzero_minor = False
        for left, right in itertools.combinations(range(5), 2):
            columns = np.flatnonzero((matrix[left] != 0) | (matrix[right] != 0))
            if columns.size:
                anchor = int(columns[0])
                determinants = (
                    matrix[left, anchor] * matrix[right]
                    - matrix[right, anchor] * matrix[left]
                )
                if np.any(determinants):
                    exact_nonzero_minor = True
                    break
        assert exact_nonzero_minor


def test_target_is_exactly_s2_cubed_equivariant(finite_domain) -> None:
    raw, targets, _ = finite_domain
    weights = np.asarray([5 ** (5 - coordinate) for coordinate in range(6)])
    for swaps in itertools.product((False, True), repeat=3):
        permuted = raw.copy()
        order = list(range(6))
        for role, swap in enumerate(swaps):
            if swap:
                left = 2 * role
                permuted[:, [left, left + 1]] = permuted[:, [left + 1, left]]
                order[left], order[left + 1] = order[left + 1], order[left]
        assert np.array_equal(targets[permuted @ weights], targets[:, order])


def test_universal_intervention_floor_has_exact_integer_pd_certificates() -> None:
    """Prove the conservative floors for every allowed split and real gain vector."""

    raw = np.indices((5,) * 6, dtype=np.int8).reshape(6, -1).T
    basis = _component_basis(raw)
    restored_cycles = {}
    for cycle in family.ROLE_CYCLES:
        permuted = np.empty_like(raw)
        for source, destination in enumerate(cycle):
            permuted[:, 2 * destination : 2 * destination + 2] = raw[
                :, 2 * source : 2 * source + 2
            ]
        cycled = _component_basis(permuted)
        restored = np.empty_like(cycled)
        for source, destination in enumerate(cycle):
            restored[:, 2 * source : 2 * source + 2] = cycled[
                :, 2 * destination : 2 * destination + 2
            ]
        restored_cycles[cycle] = restored

    checked = {"broadcast": 0, family.ROLE_CYCLES[0]: 0, family.ROLE_CYCLES[1]: 0}
    residue_subsets = tuple(
        subset
        for size in (1, 2)
        for subset in itertools.combinations(range(5), size)
    )
    for coefficients in family.SPLIT_COEFFICIENTS:
        syndrome = _syndrome(raw, coefficients)
        blocks = {}
        for residue, role, channel in itertools.product(range(5), range(3), range(2)):
            mask = syndrome == residue
            truth = basis[mask, 2 * role : 2 * role + 2, channel, :]
            blocks[residue, role, channel, "denominator"] = _gram(
                truth.reshape(-1, 12)
            )
            blocks[residue, role, channel, "broadcast"] = _gram(
                truth[:, 0, :] - truth[:, 1, :]
            )
            for cycle in family.ROLE_CYCLES:
                delta = truth - restored_cycles[cycle][
                    mask, 2 * role : 2 * role + 2, channel, :
                ]
                blocks[residue, role, channel, cycle] = _gram(
                    delta.reshape(-1, 12)
                )

        for residues, role, channel in itertools.product(
            residue_subsets, range(3), range(2)
        ):
            denominator = sum(
                (
                    blocks[residue, role, channel, "denominator"]
                    for residue in residues
                ),
                start=np.zeros((12, 12), dtype=np.int64),
            )
            numerators = {
                "broadcast": sum(
                    (
                        blocks[residue, role, channel, "broadcast"]
                        for residue in residues
                    ),
                    start=np.zeros((12, 12), dtype=np.int64),
                ),
                **{
                    cycle: sum(
                        (
                            blocks[residue, role, channel, cycle]
                            for residue in residues
                        ),
                        start=np.zeros((12, 12), dtype=np.int64),
                    )
                    for cycle in family.ROLE_CYCLES
                },
            }
            for intervention, numerator in numerators.items():
                # Broadcast damage is N/(2D), so N/(2D)>2/5 iff
                # 5N-4D>0. Cycle damage is N/D; this same certificate is
                # stronger than its registered 4/5 floor.
                certificate = 5 * numerator - 4 * denominator
                support = sorted(
                    set(np.argwhere(certificate != 0).ravel().tolist())
                )
                reduced = certificate[np.ix_(support, support)]
                assert _is_exactly_positive_definite(reduced)
                checked[intervention] += 1

    assert checked == {
        "broadcast": 1_440,
        family.ROLE_CYCLES[0]: 1_440,
        family.ROLE_CYCLES[1]: 1_440,
    }


def test_representative_intervention_damage_exceeds_certified_floors(task, finite_domain) -> None:
    raw, targets, masks = finite_domain
    broadcast = []
    for mask in masks.values():
        for role, channel in itertools.product(range(3), range(2)):
            truth = targets[mask, 2 * role : 2 * role + 2, channel]
            difference = truth[:, 0] - truth[:, 1]
            broadcast.append(
                Fraction(int(np.sum(difference**2)), 2 * int(np.sum(truth**2)))
            )
    assert min(broadcast) > Fraction(*family.CERTIFIED_BROADCAST_FLOOR)

    for cycle in family.ROLE_CYCLES:
        permuted = np.empty_like(raw)
        for source, destination in enumerate(cycle):
            permuted[:, 2 * destination : 2 * destination + 2] = raw[
                :, 2 * source : 2 * source + 2
            ]
        cycled = _reference_targets(permuted, task.rank_gains)
        restored = np.empty_like(cycled)
        for source, destination in enumerate(cycle):
            restored[:, 2 * source : 2 * source + 2] = cycled[
                :, 2 * destination : 2 * destination + 2
            ]
        damages = []
        for mask in masks.values():
            for role, channel in itertools.product(range(3), range(2)):
                truth = targets[mask, 2 * role : 2 * role + 2, channel]
                prediction = restored[mask, 2 * role : 2 * role + 2, channel]
                damages.append(
                    Fraction(
                        int(np.sum((truth - prediction) ** 2)),
                        int(np.sum(truth**2)),
                    )
                )
        assert min(damages) > Fraction(*family.CERTIFIED_ROLE_CYCLE_FLOOR)


def test_case_boundary_hides_evaluator_fields_and_has_no_case_receipt(task) -> None:
    case = task.case((4, 0, 3, 1, 2, 4))
    payload = case.model_visible()
    assert payload == case.world.model_visible()
    encoded = json.dumps(payload, sort_keys=True)
    assert all(
        field not in encoded
        for field in (
            "gain",
            "split",
            "syndrome",
            "target",
            "seed",
            "structural",
        )
    )
    assert not hasattr(case, "receipt_sha256")
    assert not hasattr(case, "world_uid")
    assert case.target_floats() == tuple(
        tuple(value / 2**19 for value in row) for row in case.target_numerators
    )


def test_frozen_exact_types_and_hashes_reject_forgery(task) -> None:
    with pytest.raises(FrozenInstanceError):
        task.draw_index = 1
    with pytest.raises(family.SWM0WS2SFamilyError, match="rank gains"):
        replace(task, rank_gains=(True, *task.rank_gains[1:]))
    with pytest.raises(family.SWM0WS2SFamilyError, match="split coefficients"):
        replace(task, split_coefficients=(True, 3, 2))
    with pytest.raises(family.SWM0WS2SFamilyError, match="structural target"):
        replace(task, structural_target_sha256="0" * 64)
    with pytest.raises(family.SWM0WS2SFamilyError, match="manifest"):
        replace(task, manifest_sha256="0" * 64)

    class HashSubclass(str):
        pass

    with pytest.raises(family.SWM0WS2SFamilyError, match="family definition SHA"):
        replace(
            task,
            family_definition_sha256=HashSubclass(
                task.family_definition_sha256
            ),
        )
    with pytest.raises(family.SWM0WS2SFamilyError):
        family.generate_task(external_seed=b"short")
    with pytest.raises(family.SWM0WS2SFamilyError):
        family.generate_task(external_seed=SEED, draw_index=True)
    with pytest.raises(family.SWM0WS2SFamilyError):
        family.generate_task_batch(external_seed=SEED, count=True)
    with pytest.raises(family.SWM0WS2SFamilyError):
        family.generate_task_batch(
            external_seed=SEED, count=family.MAX_TASK_BATCH_SIZE + 1
        )
    batch = family.generate_task_batch(external_seed=SEED, count=1)
    with pytest.raises(family.SWM0WS2SFamilyError, match="requested count"):
        replace(batch, requested_count=family.MAX_TASK_BATCH_SIZE + 1)
    with pytest.raises(family.SWM0WS2SFamilyError, match="batch SHA"):
        replace(batch, batch_sha256=HashSubclass(batch.batch_sha256))

    class ForgedWorld(worlds.ModelWorldV1):
        pass

    forged = ForgedWorld((0, 1, 2, 3, 4, 0))
    with pytest.raises(family.SWM0WS2SFamilyError, match="exact ModelWorldV1"):
        task.target(forged)


def test_v1_fixture_and_golden_manifest_remain_unchanged() -> None:
    v1 = worlds.generate_task(
        external_seed=b"swm0w-s2s-focused-tests-external-seed-v1"
    )
    assert type(v1) is worlds.TaskSpecV1
    assert v1.manifest_sha256 == (
        "4ff86e507d30adf181793d3b21b5a772faf29105f82667a8bca361b5f5e4428c"
    )
