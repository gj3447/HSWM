"""Exact finite worlds for the unjudged SWM-0W set-to-set bridge.

The fixture is deliberately small: one three-role hyperedge, two unordered
members per role, one immutable sweep, and a two-channel target.  The external
seed binds task identity only.  It does not select targets: v1 uses one fixed
factor frame whose symmetry, orthogonality, scale, and intervention floors can
be checked exhaustively before any learning experiment.

For recipient ``(r,m)`` and channel ``c`` the integer target is

``sum_k P[r,c,k](a[r,m]) * T[r,c,k](a[r,1-m])``
``      * product_(s != r) sum_n T[s,c,k](a[s,n])``.

Each expanded term has four active input coordinates.  This is a set-factorized
rank-two family, not a six-way CP claim.  Split membership is computable from
the six public values and is intentionally non-secret.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import itertools
import json
import re
from typing import Any, Iterator, Mapping, Sequence

import numpy as np


FIELD_ORDER = 5
ROLES = ("r0", "r1", "r2")
CHANNELS = ("c0", "c1")
MEMBERS_PER_ROLE = 2
RECIPIENTS = tuple((role, member) for role in ROLES for member in range(2))
TARGET_RANK = 2
T16_HIDDEN_WIDTH = 16
T16_ACTIVE_DIMENSIONS = 4
TARGET_SCALE_EXPONENT = 15
ANALYTIC_NUMERATOR_BOUND = 19_208
OBSERVED_MAX_ABS_TARGET = 5_560
SCIENTIFIC_STATUS = "UNJUDGED_INTEGRITY_ONLY"

SPLITS = ("train", "dev", "test")
FIXED_SPLIT_RESIDUES = (
    ("train", (0, 1)),
    ("dev", (2,)),
    ("test", (3, 4)),
)
SPLIT_RESIDUES: Mapping[str, tuple[int, ...]] = dict(FIXED_SPLIT_RESIDUES)
SPLIT_COUNTS: Mapping[str, int] = {
    split: len(residues) * FIELD_ORDER**5
    for split, residues in FIXED_SPLIT_RESIDUES
}

# Algebraically safe centered, mutually orthogonal frame.  Rows are h_0..h_3.
FACTOR_FRAME = (
    (-2, -1, 0, 1, 2),
    (0, 3, -4, -1, 2),
    (7, -7, -6, 5, 1),
    (3, -3, 2, -7, 5),
)
FACTOR_GRAM_DIAGONAL = (10, 30, 160, 96)

# Exact minima over all split/role/channel strata under the fixed frame.
BROADCAST_DAMAGE_FLOOR = (5_187_851, 10_706_138)
ROLE_CYCLES = ((1, 2, 0), (2, 0, 1))
ROLE_CYCLE_DAMAGE_FLOORS = (
    ((1, 2, 0), 21_660_571, 18_632_331),
    # The reverse-cycle minimum is slightly below the earlier proposed floor;
    # exhaustive exact arithmetic corrected it.
    ((2, 0, 1), 85_553, 73_855),
)

PROTOCOL_VERSION = "hswm-swm0w-s2s-task/v1"
MODEL_WORLD_SCHEMA = "hswm-swm0w-s2s-model-world/v1"
MINIMUM_SEED_BYTES = 32
_SEED_DOMAIN = b"hswm-swm0w-s2s-external-seed/v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ANALYTIC_FAMILY = (
    ("family", "RECIPIENT_CONDITIONED_SET_FACTORIZED_RANK_2"),
    ("expanded_active_coordinate_order", 4),
    ("t16_hidden_width", T16_HIDDEN_WIDTH),
    ("t16_exact_active_dimensions", T16_ACTIVE_DIMENSIONS),
    ("target_scale_exponent", TARGET_SCALE_EXPONENT),
    ("analytic_numerator_bound", ANALYTIC_NUMERATOR_BOUND),
    ("seed_effect", "IDENTITY_BINDING_ONLY_FIXED_FRAME_NO_TARGET_DIVERSITY"),
    ("split_information", "INFERABLE_FROM_ALL_SIX_RAW_VALUES_NON_SECRET"),
    ("scientific_status", SCIENTIFIC_STATUS),
)


class SWM0WS2SWorldError(ValueError):
    """Raised when a finite-world boundary is malformed."""


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if value is None or type(value) in (str, int, bool):
        return value
    raise SWM0WS2SWorldError(f"unsupported manifest value: {type(value)!r}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _exact_tree_equal(left: object, right: object) -> bool:
    """Compare frozen manifest trees without Python's bool/int aliasing."""

    if type(left) is not type(right):
        return False
    if type(left) is tuple:
        return len(left) == len(right) and all(
            _exact_tree_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return bool(left == right)


def centered_contrasts(value: int) -> tuple[int, int, int, int]:
    """Return ``1[a=q]-1[a=4]`` for q=0..3."""

    if type(value) is not int or not 0 <= value < FIELD_ORDER:
        raise SWM0WS2SWorldError("a centered contrast requires an exact Z5 integer")
    return tuple(int(value == q) - int(value == 4) for q in range(4))


def _require_raw_values(values: object) -> None:
    if (
        type(values) is not tuple
        or len(values) != 6
        or any(type(value) is not int or not 0 <= value < 5 for value in values)
    ):
        raise SWM0WS2SWorldError("raw values must be an immutable exact Z5 six-tuple")


def _require_targets(values: object) -> None:
    if (
        type(values) is not tuple
        or len(values) != 6
        or any(
            type(row) is not tuple
            or len(row) != 2
            or any(type(value) is not int for value in row)
            for row in values
        )
    ):
        raise SWM0WS2SWorldError("targets must be six immutable integer 2-vectors")


@dataclass(frozen=True, slots=True)
class ModelWorldV1:
    """The complete model-visible state in role/member enumeration order."""

    raw_values: tuple[int, int, int, int, int, int]

    def __post_init__(self) -> None:
        _require_raw_values(self.raw_values)

    @property
    def syndrome(self) -> int:
        return sum(self.raw_values) % FIELD_ORDER

    def model_visible(self) -> dict[str, Any]:
        return {
            "roles": [
                {
                    "role": role,
                    "members": [
                        {
                            "raw": self.raw_values[2 * r + member],
                            "centered_contrasts": list(
                                centered_contrasts(self.raw_values[2 * r + member])
                            ),
                        }
                        for member in range(2)
                    ],
                }
                for r, role in enumerate(ROLES)
            ],
            "schema_version": MODEL_WORLD_SCHEMA,
        }


@dataclass(frozen=True, slots=True)
class MemberPermutationV1:
    """One element of S2^3 acting on member enumeration and outputs."""

    swaps: tuple[bool, bool, bool]

    def __post_init__(self) -> None:
        if (
            type(self.swaps) is not tuple
            or len(self.swaps) != 3
            or any(type(value) is not bool for value in self.swaps)
        ):
            raise SWM0WS2SWorldError("member permutation requires three exact bools")

    def apply_world(self, world: ModelWorldV1) -> ModelWorldV1:
        if type(world) is not ModelWorldV1:
            raise SWM0WS2SWorldError("member permutation requires exact ModelWorldV1")
        values = list(world.raw_values)
        for role, swap in enumerate(self.swaps):
            if swap:
                left = 2 * role
                values[left], values[left + 1] = values[left + 1], values[left]
        return ModelWorldV1(tuple(values))

    def apply_targets(
        self, targets: tuple[tuple[int, int], ...]
    ) -> tuple[tuple[int, int], ...]:
        _require_targets(targets)
        rows = list(targets)
        for role, swap in enumerate(self.swaps):
            if swap:
                left = 2 * role
                rows[left], rows[left + 1] = rows[left + 1], rows[left]
        return tuple(rows)

    apply_outputs = apply_targets

    def inverse(self) -> MemberPermutationV1:
        return self


ALL_MEMBER_PERMUTATIONS = tuple(
    MemberPermutationV1(swaps) for swaps in itertools.product((False, True), repeat=3)
)


def _fixed_factor_tables() -> tuple[tuple[str, tuple[int, ...]], ...]:
    rows: list[tuple[str, tuple[int, ...]]] = []
    for kind in ("P", "T"):
        for role in range(3):
            for channel in range(2):
                offset = (role + channel) % 4
                for rank in range(2):
                    frame_index = (offset + rank + (2 if kind == "P" else 0)) % 4
                    rows.append(
                        (f"{kind}:r{role}:c{channel}:k{rank}", FACTOR_FRAME[frame_index])
                    )
    return tuple(rows)


FIXED_FACTOR_TABLES = _fixed_factor_tables()


def _split_for_syndrome(syndrome: int) -> str:
    for split, residues in FIXED_SPLIT_RESIDUES:
        if syndrome in residues:
            return split
    raise AssertionError("fixed residues must partition Z5")


@dataclass(frozen=True, slots=True)
class EvaluatorCaseV1:
    """Minimal evaluator envelope; only ``world`` is model-visible."""

    world: ModelWorldV1
    split: str
    target_numerators: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if type(self.world) is not ModelWorldV1:
            raise SWM0WS2SWorldError("case requires exact ModelWorldV1")
        if type(self.split) is not str or self.split != _split_for_syndrome(
            self.world.syndrome
        ):
            raise SWM0WS2SWorldError("case split disagrees with its public world")
        _require_targets(self.target_numerators)
        expected_targets = _target_from_values(
            self.world.raw_values, dict(FIXED_FACTOR_TABLES)
        )
        if self.target_numerators != expected_targets:
            raise SWM0WS2SWorldError("case targets disagree with the fixed task")
        if (
            max(abs(value) for row in self.target_numerators for value in row)
            > ANALYTIC_NUMERATOR_BOUND
        ):
            raise SWM0WS2SWorldError("target exceeds the analytic bound")

    def model_visible(self) -> dict[str, Any]:
        return self.world.model_visible()

    def target_floats(self) -> tuple[tuple[float, float], ...]:
        scale = float(2**TARGET_SCALE_EXPONENT)
        return tuple(tuple(value / scale for value in row) for row in self.target_numerators)


def _task_payload(
    seed_commitment_sha256: str,
    split_residues: tuple[tuple[str, tuple[int, ...]], ...],
    factor_tables: tuple[tuple[str, tuple[int, ...]], ...],
    analytic_family: tuple[tuple[str, str | int], ...],
) -> dict[str, Any]:
    return {
        "analytic_family": dict(analytic_family),
        "factor_tables": [
            {"key": key, "values": list(values)} for key, values in factor_tables
        ],
        "protocol_version": PROTOCOL_VERSION,
        "seed_commitment_sha256": seed_commitment_sha256,
        "split_residues": {split: list(residues) for split, residues in split_residues},
    }


@dataclass(frozen=True, slots=True)
class TaskSpecV1:
    """One portable task manifest plus streamed finite evaluator cases."""

    seed_commitment_sha256: str
    split_residues: tuple[tuple[str, tuple[int, ...]], ...]
    factor_tables: tuple[tuple[str, tuple[int, ...]], ...]
    analytic_family: tuple[tuple[str, str | int], ...]
    manifest_sha256: str

    def __post_init__(self) -> None:
        if type(self.seed_commitment_sha256) is not str or not _SHA256_RE.fullmatch(
            self.seed_commitment_sha256
        ):
            raise SWM0WS2SWorldError("invalid seed commitment")
        if not _exact_tree_equal(self.split_residues, FIXED_SPLIT_RESIDUES):
            raise SWM0WS2SWorldError("task must use the fixed split mapping")
        if not _exact_tree_equal(self.factor_tables, FIXED_FACTOR_TABLES):
            raise SWM0WS2SWorldError("task must use the proven fixed factor frame")
        if not _exact_tree_equal(self.analytic_family, ANALYTIC_FAMILY):
            raise SWM0WS2SWorldError("task analytic family drifted")
        if (
            type(self.manifest_sha256) is not str
            or self.manifest_sha256 != canonical_sha256(self.manifest_payload())
        ):
            raise SWM0WS2SWorldError("task manifest SHA does not match")

    def manifest_payload(self) -> dict[str, Any]:
        return _task_payload(
            self.seed_commitment_sha256,
            self.split_residues,
            self.factor_tables,
            self.analytic_family,
        )

    def canonical(self) -> dict[str, Any]:
        return {**self.manifest_payload(), "manifest_sha256": self.manifest_sha256}

    def factor_mapping(self) -> dict[str, tuple[int, ...]]:
        return dict(self.factor_tables)

    def target(self, world: ModelWorldV1) -> tuple[tuple[int, int], ...]:
        if type(world) is not ModelWorldV1:
            raise SWM0WS2SWorldError("target requires exact ModelWorldV1")
        return _target_from_values(world.raw_values, self.factor_mapping())

    def case(self, raw_values: tuple[int, int, int, int, int, int]) -> EvaluatorCaseV1:
        world = ModelWorldV1(raw_values)
        return EvaluatorCaseV1(world, _split_for_syndrome(world.syndrome), self.target(world))

    def iter_cases(self, split: str | None = None) -> Iterator[EvaluatorCaseV1]:
        if split is not None and split not in SPLITS:
            raise SWM0WS2SWorldError(f"unsupported split: {split!r}")
        factors = self.factor_mapping()
        for values in itertools.product(range(5), repeat=6):
            world = ModelWorldV1(values)
            world_split = _split_for_syndrome(world.syndrome)
            if split is None or split == world_split:
                yield EvaluatorCaseV1(
                    world,
                    world_split,
                    _target_from_values(values, factors),
                )


def _target_from_values(
    raw_values: Sequence[int], factors: Mapping[str, tuple[int, ...]]
) -> tuple[tuple[int, int], ...]:
    outputs: list[tuple[int, int]] = []
    for role in range(3):
        for member in range(2):
            recipient = raw_values[2 * role + member]
            comember = raw_values[2 * role + 1 - member]
            channels: list[int] = []
            for channel in range(2):
                total = 0
                for rank in range(2):
                    value = (
                        factors[f"P:r{role}:c{channel}:k{rank}"][recipient]
                        * factors[f"T:r{role}:c{channel}:k{rank}"][comember]
                    )
                    for source in range(3):
                        if source != role:
                            table = factors[f"T:r{source}:c{channel}:k{rank}"]
                            value *= table[raw_values[2 * source]] + table[
                                raw_values[2 * source + 1]
                            ]
                    total += value
                channels.append(total)
            outputs.append(tuple(channels))
    return tuple(outputs)


def _all_targets(raw: np.ndarray) -> np.ndarray:
    factors = dict(FIXED_FACTOR_TABLES)
    targets = np.empty((len(raw), 6, 2), dtype=np.int64)
    for index, values in enumerate(raw):
        targets[index] = _target_from_values(tuple(int(v) for v in values), factors)
    return targets


def _damage_fraction(prediction: np.ndarray, truth: np.ndarray) -> tuple[int, int]:
    from fractions import Fraction

    fraction = Fraction(
        int(np.sum((truth - prediction) ** 2, dtype=np.int64)),
        int(np.sum(truth**2, dtype=np.int64)),
    )
    return fraction.numerator, fraction.denominator


@lru_cache(maxsize=1)
def _fixed_integrity_summary() -> dict[str, Any]:
    """Generate the internal exact audit summary; it is not a research verdict."""

    raw = np.indices((5,) * 6, dtype=np.int8).reshape(6, -1).T
    targets = _all_targets(raw)
    syndrome = np.sum(raw, axis=1, dtype=np.int64) % 5
    masks = {
        split: np.isin(syndrome, np.asarray(residues, dtype=np.int64))
        for split, residues in FIXED_SPLIT_RESIDUES
    }
    frame = np.asarray(FACTOR_FRAME, dtype=np.int64)
    if not np.array_equal(
        frame @ frame.T, np.diag(np.asarray(FACTOR_GRAM_DIAGONAL, dtype=np.int64))
    ):
        raise SWM0WS2SWorldError("fixed factor Gram matrix drifted")

    for split, residues in FIXED_SPLIT_RESIDUES:
        selected = raw[masks[split]]
        if len(selected) != SPLIT_COUNTS[split]:
            raise SWM0WS2SWorldError("split cardinality drifted")
        for order in range(1, 6):
            expected = len(residues) * 5 ** (5 - order)
            for coordinates in itertools.combinations(range(6), order):
                code = np.zeros(len(selected), dtype=np.int64)
                for coordinate in coordinates:
                    code = 5 * code + selected[:, coordinate]
                if not np.all(np.bincount(code, minlength=5**order) == expected):
                    raise SWM0WS2SWorldError("normalized marginal audit failed")

    if any(np.any(np.sum(targets[mask], axis=0) != 0) for mask in masks.values()):
        raise SWM0WS2SWorldError("target centering audit failed")
    if int(np.max(np.abs(targets))) != OBSERVED_MAX_ABS_TARGET:
        raise SWM0WS2SWorldError("observed target scale drifted")

    for output in range(6):
        for channel in range(2):
            tensor = targets[:, output, channel].reshape((5,) * 6)
            matrix = np.moveaxis(tensor, output, 0).reshape(5, -1)
            rank_two = False
            for left, right in itertools.combinations(range(5), 2):
                nonzero = np.flatnonzero((matrix[left] != 0) | (matrix[right] != 0))
                if nonzero.size:
                    column = int(nonzero[0])
                    determinants = (
                        matrix[left, column] * matrix[right]
                        - matrix[right, column] * matrix[left]
                    )
                    rank_two |= bool(np.any(determinants))
            if not rank_two:
                raise SWM0WS2SWorldError("rank-two audit failed")

    flat_weights = np.asarray([5 ** (5 - coordinate) for coordinate in range(6)])
    for action in ALL_MEMBER_PERMUTATIONS:
        permuted = raw.copy()
        order = list(range(6))
        for role, swap in enumerate(action.swaps):
            if swap:
                left = 2 * role
                permuted[:, [left, left + 1]] = permuted[:, [left + 1, left]]
                order[left], order[left + 1] = order[left + 1], order[left]
        indices = permuted.astype(np.int64) @ flat_weights
        if not np.array_equal(targets[indices], targets[:, order]):
            raise SWM0WS2SWorldError("S2^3 equivariance audit failed")

    unrestricted_counterexample = False
    for mask in masks.values():
        for output in range(6):
            for channel in range(2):
                vector = targets[:, output, channel]
                for other in range(6):
                    if other == output:
                        continue
                    table = np.zeros((5, 5), dtype=np.int64)
                    np.add.at(table, (raw[mask, output], raw[mask, other]), vector[mask])
                    if np.any(table):
                        raise SWM0WS2SWorldError("recipient-star orthogonality failed")
                for left, right in itertools.combinations(
                    (coordinate for coordinate in range(6) if coordinate != output), 2
                ):
                    table = np.zeros((5, 5), dtype=np.int64)
                    np.add.at(table, (raw[mask, left], raw[mask, right]), vector[mask])
                    unrestricted_counterexample |= bool(np.any(table))

    broadcast_min: tuple[int, int] | None = None
    for mask in masks.values():
        for role in range(3):
            for channel in range(2):
                truth = targets[mask, 2 * role : 2 * role + 2, channel]
                difference = truth[:, 0] - truth[:, 1]
                from fractions import Fraction

                exact = Fraction(
                    int(np.sum(difference**2, dtype=np.int64)),
                    2 * int(np.sum(truth**2, dtype=np.int64)),
                )
                fraction = (exact.numerator, exact.denominator)
                if (
                    broadcast_min is None
                    or fraction[0] * broadcast_min[1] < broadcast_min[0] * fraction[1]
                ):
                    broadcast_min = fraction

    cycle_minima = []
    for cycle in ROLE_CYCLES:
        permuted = np.empty_like(raw)
        for source, destination in enumerate(cycle):
            permuted[:, 2 * destination : 2 * destination + 2] = raw[
                :, 2 * source : 2 * source + 2
            ]
        cycled = _all_targets(permuted)
        restored = np.empty_like(cycled)
        for source, destination in enumerate(cycle):
            restored[:, 2 * source : 2 * source + 2] = cycled[
                :, 2 * destination : 2 * destination + 2
            ]
        minimum: tuple[int, int] | None = None
        for mask in masks.values():
            for role in range(3):
                for channel in range(2):
                    fraction = _damage_fraction(
                        restored[mask, 2 * role : 2 * role + 2, channel],
                        targets[mask, 2 * role : 2 * role + 2, channel],
                    )
                    if (
                        minimum is None
                        or fraction[0] * minimum[1] < minimum[0] * fraction[1]
                    ):
                        minimum = fraction
        cycle_minima.append((cycle, *minimum))

    summary = {
        "broadcast_damage_floor": broadcast_min,
        "role_cycle_damage_floors": tuple(cycle_minima),
        "max_abs_target": int(np.max(np.abs(targets))),
        "unrestricted_pair_counterexample_found": unrestricted_counterexample,
        "scientific_status": SCIENTIFIC_STATUS,
    }
    if broadcast_min != BROADCAST_DAMAGE_FLOOR:
        raise SWM0WS2SWorldError("broadcast floor drifted")
    if tuple(cycle_minima) != ROLE_CYCLE_DAMAGE_FLOORS:
        raise SWM0WS2SWorldError("role-cycle floor drifted")
    if not unrestricted_counterexample:
        raise SWM0WS2SWorldError("expected unrestricted-pair counterexample was absent")
    return summary


def generate_task(*, external_seed: bytes) -> TaskSpecV1:
    """Return the fixed-frame task bound to caller-supplied future randomness."""

    if type(external_seed) is not bytes or len(external_seed) < MINIMUM_SEED_BYTES:
        raise SWM0WS2SWorldError(
            f"external seed must be exact bytes with at least {MINIMUM_SEED_BYTES} bytes"
        )
    commitment = hashlib.sha256(_SEED_DOMAIN + b"\x00" + external_seed).hexdigest()
    payload = _task_payload(
        commitment, FIXED_SPLIT_RESIDUES, FIXED_FACTOR_TABLES, ANALYTIC_FAMILY
    )
    task = TaskSpecV1(
        commitment,
        FIXED_SPLIT_RESIDUES,
        FIXED_FACTOR_TABLES,
        ANALYTIC_FAMILY,
        canonical_sha256(payload),
    )
    _fixed_integrity_summary()
    return task


# Temporary source compatibility while callers migrate to the smaller task API.
generate_fixture = generate_task


__all__ = [
    "ALL_MEMBER_PERMUTATIONS",
    "ANALYTIC_FAMILY",
    "ANALYTIC_NUMERATOR_BOUND",
    "BROADCAST_DAMAGE_FLOOR",
    "CHANNELS",
    "EvaluatorCaseV1",
    "FACTOR_FRAME",
    "FACTOR_GRAM_DIAGONAL",
    "FIELD_ORDER",
    "FIXED_FACTOR_TABLES",
    "MEMBERS_PER_ROLE",
    "MemberPermutationV1",
    "ModelWorldV1",
    "OBSERVED_MAX_ABS_TARGET",
    "RECIPIENTS",
    "ROLES",
    "ROLE_CYCLES",
    "ROLE_CYCLE_DAMAGE_FLOORS",
    "SCIENTIFIC_STATUS",
    "SPLITS",
    "SPLIT_COUNTS",
    "SPLIT_RESIDUES",
    "SWM0WS2SWorldError",
    "T16_ACTIVE_DIMENSIONS",
    "T16_HIDDEN_WIDTH",
    "TARGET_RANK",
    "TARGET_SCALE_EXPONENT",
    "TaskSpecV1",
    "canonical_json",
    "canonical_sha256",
    "centered_contrasts",
    "generate_fixture",
    "generate_task",
]
