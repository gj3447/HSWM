"""Occam-minimal streamed task core for the fixed-arity SWM-0W gate.

One external byte seed deterministically creates one immutable evaluator task.
The 25 F5 shift pairs form a complete 9/8/8 train/dev/test partition.  Models
see only three singleton role records with raw normalized coefficient/operand
features.  Gold dyadic targets and all identities remain evaluator-side.

The target is a sum of 17 seed-derived, quantized, exactly centered
tanh-affine rank-one terms.  A single shared 17x17 minor of the final integer
mode-0 unfolding is recomputed modulo two primes.  Its nonzero determinants,
together with the 17-term construction, establish mode rank exactly 17 for
this synthetic fixed-arity target.  No NumPy linear algebra is used.

This is task infrastructure, not sealed evidence.  The returned task contains
gold labels and its target tensor.  The label-free iterator retains only model
worlds, and the scorer returns only an aggregate, but this module provides no
process isolation, seed chronology, secrecy, or confirmatory protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Context, Decimal, ROUND_HALF_EVEN
import hashlib
import itertools
import json
import math
import re
from typing import Any, Iterator, Mapping, Sequence

import numpy as np

from hswm.experiments.swm0w_worlds import (
    FIELD_ORDER,
    ROLES,
    SPLITS,
    ModelWorldV1,
    RoleInputV1,
    normalize_level,
)


TASK_VERSION = "hswm-swm0w-streamed-task/v1"
CUT_SCHEMA = "hswm-swm0w-streamed-cut/v1"
RANK_WITNESS_SCHEMA = "hswm-swm0w-final-minor-witness/v1"
TARGET_SCHEMA = "hswm-swm0w-dyadic-target/v1"
CASE_SCHEMA = "hswm-swm0w-streamed-evaluator-case/v1"
SPLIT_SCHEMA = "hswm-swm0w-streamed-split/v1"
TASK_SCHEMA = "hswm-swm0w-streamed-task-artifact/v1"
SCORE_SCHEMA = "hswm-swm0w-streamed-score/v1"

MINIMUM_SEED_BYTES = 32
TARGET_CP_TERMS = 17
REFERENCE_WIDTH = 16
TANH_QUANTIZATION_BITS = 8
TANH_DECIMAL_PRECISION = 80
TARGET_ABS_BOUND = 0.5
MAX_CONSTRUCTION_ATTEMPTS = 32
_CANDIDATE_COLUMNS = 128
_PRIMES = (1_000_000_007, 1_000_000_009)
_SEED_DOMAIN = b"hswm-swm0w-streamed-task-seed/v1"
_TASK_UID_RE = re.compile(r"^swm0wt_[0-9a-f]{24}$")
_CASE_UID_RE = re.compile(r"^swm0wt_case_[0-9a-f]{24}$")
_DECIMAL_CONTEXT = Context(prec=TANH_DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN)
_ROLE_STATES = tuple(itertools.product(range(FIELD_ORDER), repeat=2))
_ALL_SHIFT_PAIRS = frozenset(itertools.product(range(FIELD_ORDER), repeat=2))
_SPLIT_COUNTS = {"train": 9 * FIELD_ORDER**4, "dev": 8 * FIELD_ORDER**4, "test": 8 * FIELD_ORDER**4}


class SWM0WTaskCoreError(ValueError):
    """Raised when a seed, artifact, witness, or score fails closed."""


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SWM0WTaskCoreError("canonical JSON requires finite floats")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if hasattr(value, "canonical"):
        return _jsonable(value.canonical())
    raise SWM0WTaskCoreError(f"unsupported canonical value: {type(value)!r}")


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


def _require_sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SWM0WTaskCoreError(f"{name} must be a lowercase SHA-256")


def _seed_commitment(seed: bytes) -> str:
    if type(seed) is not bytes or len(seed) < MINIMUM_SEED_BYTES:
        raise SWM0WTaskCoreError(
            f"seed must be exact bytes with at least {MINIMUM_SEED_BYTES} bytes"
        )
    return hashlib.sha256(_SEED_DOMAIN + b"\x00" + seed).hexdigest()


def _digest(seed: bytes, domain: str, *coordinates: int) -> bytes:
    suffix = b"".join(int(value).to_bytes(4, "big") for value in coordinates)
    return hashlib.sha256(
        TASK_VERSION.encode("ascii")
        + b"\x00"
        + domain.encode("ascii")
        + b"\x00"
        + seed
        + suffix
    ).digest()


def _integer_array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value, dtype="<i8")
    header = canonical_json(
        {"dtype": "int64-little-endian", "shape": list(array.shape)}
    ).encode("ascii")
    return hashlib.sha256(header + b"\x00" + array.tobytes()).hexdigest()


def _float_array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value, dtype="<f8")
    header = canonical_json(
        {"dtype": "float64-little-endian", "shape": list(array.shape)}
    ).encode("ascii")
    return hashlib.sha256(header + b"\x00" + array.tobytes()).hexdigest()


def _immutable_int64(value: Any) -> np.ndarray:
    array = np.ascontiguousarray(value, dtype="<i8")
    return np.frombuffer(array.tobytes(), dtype="<i8").reshape(array.shape)


def _determinant_mod(matrix: Sequence[Sequence[int]], prime: int) -> int:
    size = len(matrix)
    if size == 0 or any(len(row) != size for row in matrix):
        raise SWM0WTaskCoreError("modular determinant requires a square matrix")
    work = [[int(value) % prime for value in row] for row in matrix]
    determinant = 1
    for column in range(size):
        pivot = next(
            (row for row in range(column, size) if work[row][column]), None
        )
        if pivot is None:
            return 0
        if pivot != column:
            work[column], work[pivot] = work[pivot], work[column]
            determinant = -determinant % prime
        pivot_value = work[column][column]
        determinant = determinant * pivot_value % prime
        inverse = pow(pivot_value, prime - 2, prime)
        for row in range(column + 1, size):
            multiplier = work[row][column] * inverse % prime
            if multiplier:
                work[row][column:] = [
                    (left - multiplier * right) % prime
                    for left, right in zip(
                        work[row][column:], work[column][column:]
                    )
                ]
    return determinant


def _pivot_rows_mod(
    matrix: Sequence[Sequence[int]], prime: int
) -> tuple[int, ...]:
    if not matrix or not matrix[0]:
        return ()
    column_count = len(matrix[0])
    if any(len(row) != column_count for row in matrix):
        raise SWM0WTaskCoreError("modular matrix is ragged")
    work = [[int(value) % prime for value in row] for row in matrix]
    row_ids = list(range(len(work)))
    rank = 0
    for column in range(column_count):
        pivot = next(
            (row for row in range(rank, len(work)) if work[row][column]), None
        )
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        row_ids[rank], row_ids[pivot] = row_ids[pivot], row_ids[rank]
        inverse = pow(work[rank][column], prime - 2, prime)
        work[rank] = [value * inverse % prime for value in work[rank]]
        for row in range(len(work)):
            if row == rank or not work[row][column]:
                continue
            multiplier = work[row][column]
            work[row] = [
                (left - multiplier * right) % prime
                for left, right in zip(work[row], work[rank])
            ]
        rank += 1
        if rank == column_count:
            return tuple(row_ids[:rank])
    return tuple(row_ids[:rank])


@dataclass(frozen=True, slots=True)
class TaskCutV1:
    shift_pair_order: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if (
            type(self.shift_pair_order) is not tuple
            or len(self.shift_pair_order) != FIELD_ORDER**2
            or set(self.shift_pair_order) != _ALL_SHIFT_PAIRS
        ):
            raise SWM0WTaskCoreError("cut must permute all 25 F5 shift pairs")

    def shift_pairs(self, split: str) -> tuple[tuple[int, int], ...]:
        if split == "train":
            return self.shift_pair_order[:9]
        if split == "dev":
            return self.shift_pair_order[9:17]
        if split == "test":
            return self.shift_pair_order[17:]
        raise SWM0WTaskCoreError(f"unsupported split: {split!r}")

    def canonical(self) -> dict[str, Any]:
        return {
            "schema_version": CUT_SCHEMA,
            "shift_pair_order": [list(pair) for pair in self.shift_pair_order],
            "split_cut_counts": {"dev": 8, "test": 8, "train": 9},
        }

    @property
    def cut_sha256(self) -> str:
        return canonical_sha256(self.canonical())


@dataclass(frozen=True, slots=True)
class FinalMinorWitnessV1:
    integer_tensor_sha256: str
    row_indices: tuple[int, ...]
    column_indices: tuple[int, ...]
    determinants: tuple[tuple[int, int], ...]
    receipt_sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.integer_tensor_sha256, "integer_tensor_sha256")
        if (
            len(self.row_indices) != TARGET_CP_TERMS
            or len(set(self.row_indices)) != TARGET_CP_TERMS
            or any(not 0 <= value < FIELD_ORDER**2 for value in self.row_indices)
        ):
            raise SWM0WTaskCoreError("invalid final-minor row indices")
        if (
            len(self.column_indices) != TARGET_CP_TERMS
            or len(set(self.column_indices)) != TARGET_CP_TERMS
            or any(not 0 <= value < FIELD_ORDER**4 for value in self.column_indices)
        ):
            raise SWM0WTaskCoreError("invalid final-minor column indices")
        if tuple(prime for prime, _ in self.determinants) != _PRIMES or any(
            not 0 < determinant < prime
            for prime, determinant in self.determinants
        ):
            raise SWM0WTaskCoreError("invalid final-minor determinants")
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        if self.receipt_sha256 != canonical_sha256(self.unsigned_canonical()):
            raise SWM0WTaskCoreError("final-minor receipt hash mismatch")

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "column_indices": list(self.column_indices),
            "cp_term_upper_bound": TARGET_CP_TERMS,
            "determinants": dict(self.determinants),
            "exact_mode0_rank": TARGET_CP_TERMS,
            "integer_tensor_sha256": self.integer_tensor_sha256,
            "matrix_shape": [FIELD_ORDER**2, FIELD_ORDER**4],
            "proof": "ONE_SHARED_FINAL_INTEGER_TENSOR_MINOR_UNDER_TWO_PRIMES",
            "row_indices": list(self.row_indices),
            "schema_version": RANK_WITNESS_SCHEMA,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned_canonical(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class DyadicTargetV1:
    task_uid: str
    seed_commitment_sha256: str
    cut: TaskCutV1
    construction_attempt: int
    scale_exponent: int
    integer_tensor: np.ndarray = field(repr=False, compare=False)
    integer_tensor_sha256: str = ""
    rank_witness: FinalMinorWitnessV1 | None = None
    receipt_sha256: str = ""

    def __post_init__(self) -> None:
        if not _TASK_UID_RE.fullmatch(self.task_uid):
            raise SWM0WTaskCoreError("invalid task uid")
        _require_sha256(self.seed_commitment_sha256, "seed_commitment_sha256")
        if self.task_uid != f"swm0wt_{self.seed_commitment_sha256[:24]}":
            raise SWM0WTaskCoreError("task uid does not bind its seed commitment")
        if (
            type(self.construction_attempt) is not int
            or not 0 <= self.construction_attempt < MAX_CONSTRUCTION_ATTEMPTS
        ):
            raise SWM0WTaskCoreError("invalid construction attempt")
        if type(self.scale_exponent) is not int or self.scale_exponent <= 0:
            raise SWM0WTaskCoreError("invalid dyadic scale exponent")
        tensor = _immutable_int64(self.integer_tensor)
        if tensor.shape != (FIELD_ORDER**2,) * len(ROLES):
            raise SWM0WTaskCoreError("integer target tensor has wrong shape")
        object.__setattr__(self, "integer_tensor", tensor)
        _require_sha256(self.integer_tensor_sha256, "integer_tensor_sha256")
        if _integer_array_sha256(tensor) != self.integer_tensor_sha256:
            raise SWM0WTaskCoreError("integer target tensor hash mismatch")
        maximum = max(abs(int(value)) for value in tensor.flat)
        if maximum == 0 or maximum >= 2**53:
            raise SWM0WTaskCoreError("integer target magnitude is invalid")
        if math.ldexp(maximum, -self.scale_exponent) > TARGET_ABS_BOUND:
            raise SWM0WTaskCoreError("dyadic target exceeds its bound")
        if not isinstance(self.rank_witness, FinalMinorWitnessV1):
            raise SWM0WTaskCoreError("final-minor witness is required")
        if self.rank_witness.integer_tensor_sha256 != self.integer_tensor_sha256:
            raise SWM0WTaskCoreError("rank witness binds a different tensor")
        unfolding = tensor.reshape(FIELD_ORDER**2, FIELD_ORDER**4)
        minor = [
            [int(unfolding[row, column]) for column in self.rank_witness.column_indices]
            for row in self.rank_witness.row_indices
        ]
        for prime, recorded in self.rank_witness.determinants:
            if _determinant_mod(minor, prime) != recorded:
                raise SWM0WTaskCoreError("final integer-tensor minor does not verify")
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        if self.receipt_sha256 != canonical_sha256(self.unsigned_canonical()):
            raise SWM0WTaskCoreError("dyadic-target receipt hash mismatch")

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "construction": {
                "centered_exactly": True,
                "cp_terms": TARGET_CP_TERMS,
                "decimal_precision": TANH_DECIMAL_PRECISION,
                "factor_quantization_bits": TANH_QUANTIZATION_BITS,
                "role_factors": "SEED_DERIVED_TANH_AFFINE",
            },
            "construction_attempt": self.construction_attempt,
            "cut": self.cut.canonical(),
            "evaluator_only": True,
            "integer_tensor_sha256": self.integer_tensor_sha256,
            "model_visible": False,
            "rank_witness": self.rank_witness.canonical(),
            "scale_exponent": self.scale_exponent,
            "schema_version": TARGET_SCHEMA,
            "scope": {
                "arity": 3,
                "chronology_proven": False,
                "incidences_per_role": 1,
                "process_isolation_enforced": False,
                "sealed_evaluation_boundary": False,
                "secrecy_proven": False,
                "synthetic_target": True,
            },
            "seed_commitment_sha256": self.seed_commitment_sha256,
            "target_abs_bound": TARGET_ABS_BOUND,
            "task_uid": self.task_uid,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned_canonical(), "receipt_sha256": self.receipt_sha256}

    def numerator_at(self, role_values: tuple[tuple[int, int], ...]) -> int:
        indices = tuple(
            coefficient * FIELD_ORDER + operand
            for coefficient, operand in role_values
        )
        return int(self.integer_tensor[indices])


@dataclass(frozen=True, slots=True)
class TaskEvaluatorCaseV1:
    case_uid: str
    task_uid: str
    split: str
    coefficient_shift: int
    operand_shift: int
    role_values: tuple[tuple[int, int], ...]
    target_numerator: int
    target_scale_exponent: int
    target: float
    world: ModelWorldV1
    receipt_sha256: str

    def __post_init__(self) -> None:
        if not _CASE_UID_RE.fullmatch(self.case_uid):
            raise SWM0WTaskCoreError("invalid case uid")
        if not _TASK_UID_RE.fullmatch(self.task_uid):
            raise SWM0WTaskCoreError("invalid case task uid")
        if self.split not in SPLITS:
            raise SWM0WTaskCoreError(f"unsupported split: {self.split!r}")
        if (
            type(self.role_values) is not tuple
            or len(self.role_values) != len(ROLES)
            or any(
                type(pair) is not tuple
                or len(pair) != 2
                or any(type(value) is not int or not 0 <= value < FIELD_ORDER for value in pair)
                for pair in self.role_values
            )
        ):
            raise SWM0WTaskCoreError("role values must be three F5 pairs")
        coefficients = tuple(pair[0] for pair in self.role_values)
        operands = tuple(pair[1] for pair in self.role_values)
        if coefficients[2] != (
            coefficients[0] + coefficients[1] + self.coefficient_shift
        ) % FIELD_ORDER or operands[2] != (
            operands[0] + operands[1] + self.operand_shift
        ) % FIELD_ORDER:
            raise SWM0WTaskCoreError("case values violate their shift cut")
        if (
            type(self.target_numerator) is not int
            or type(self.target_scale_exponent) is not int
            or self.target_scale_exponent <= 0
            or type(self.target) is not float
            or self.target != math.ldexp(
                self.target_numerator, -self.target_scale_exponent
            )
            or abs(self.target) > TARGET_ABS_BOUND
        ):
            raise SWM0WTaskCoreError("case target is not the registered dyadic value")
        expected = tuple(
            (normalize_level(coefficient), normalize_level(operand))
            for coefficient, operand in self.role_values
        )
        if self.world.feature_matrix() != expected:
            raise SWM0WTaskCoreError("model world disagrees with evaluator values")
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        if self.receipt_sha256 != canonical_sha256(self.unsigned_canonical()):
            raise SWM0WTaskCoreError("case receipt hash mismatch")

    @property
    def state_tuple(self) -> tuple[int, ...]:
        return tuple(value for pair in self.role_values for value in pair)

    def model_visible(self) -> dict[str, Any]:
        return self.world.canonical()

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "case_uid": self.case_uid,
            "coefficient_shift": self.coefficient_shift,
            "operand_shift": self.operand_shift,
            "role_values": [list(pair) for pair in self.role_values],
            "schema_version": CASE_SCHEMA,
            "split": self.split,
            "target_numerator": self.target_numerator,
            "target_scale_exponent": self.target_scale_exponent,
            "task_uid": self.task_uid,
            "world": self.world.canonical(),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned_canonical(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class TaskSplitV1:
    task_uid: str
    split: str
    shift_pairs: tuple[tuple[int, int], ...]
    cases: tuple[TaskEvaluatorCaseV1, ...]
    target_integer_sum: int
    target_integer_sum_of_squares: int
    receipt_sha256: str

    def __post_init__(self) -> None:
        if not _TASK_UID_RE.fullmatch(self.task_uid) or self.split not in SPLITS:
            raise SWM0WTaskCoreError("invalid task split identity")
        if len(self.cases) != _SPLIT_COUNTS[self.split]:
            raise SWM0WTaskCoreError("split has the wrong exact case count")
        if any(
            case.task_uid != self.task_uid
            or case.split != self.split
            or (case.coefficient_shift, case.operand_shift) not in self.shift_pairs
            for case in self.cases
        ):
            raise SWM0WTaskCoreError("split contains a mismatched case")
        if len({case.state_tuple for case in self.cases}) != len(self.cases):
            raise SWM0WTaskCoreError("split states are not unique")
        if len({case.case_uid for case in self.cases}) != len(self.cases):
            raise SWM0WTaskCoreError("split case uids are not unique")
        numerators = tuple(case.target_numerator for case in self.cases)
        if self.target_integer_sum != sum(numerators) or (
            self.target_integer_sum_of_squares
            != sum(value * value for value in numerators)
        ):
            raise SWM0WTaskCoreError("split exact target moments do not verify")
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        if self.receipt_sha256 != canonical_sha256(self.unsigned_canonical()):
            raise SWM0WTaskCoreError("split receipt hash mismatch")

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "case_count": len(self.cases),
            "case_receipts_in_evaluation_order": [
                [case.case_uid, case.receipt_sha256] for case in self.cases
            ],
            "schema_version": SPLIT_SCHEMA,
            "shift_pairs": [list(pair) for pair in self.shift_pairs],
            "split": self.split,
            "target_integer_sum": self.target_integer_sum,
            "target_integer_sum_of_squares": self.target_integer_sum_of_squares,
            "task_uid": self.task_uid,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned_canonical(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class StreamedTaskV1:
    target_parameters: DyadicTargetV1
    splits: tuple[TaskSplitV1, ...]
    task_sha256: str

    def __post_init__(self) -> None:
        if tuple(item.split for item in self.splits) != SPLITS:
            raise SWM0WTaskCoreError("task splits must be train/dev/test ordered")
        if any(item.task_uid != self.task_uid for item in self.splits):
            raise SWM0WTaskCoreError("split task uid mismatch")
        if any(
            item.shift_pairs != self.target_parameters.cut.shift_pairs(item.split)
            for item in self.splits
        ):
            raise SWM0WTaskCoreError("split cut does not match target parameters")
        state_sets = {
            item.split: {case.state_tuple for case in item.cases}
            for item in self.splits
        }
        if any(
            not state_sets[left].isdisjoint(state_sets[right])
            for left, right in itertools.combinations(SPLITS, 2)
        ) or len(set().union(*state_sets.values())) != FIELD_ORDER**6:
            raise SWM0WTaskCoreError("task split states are not exactly separated")
        if any(
            case.target_numerator
            != self.target_parameters.numerator_at(case.role_values)
            for item in self.splits
            for case in item.cases
        ):
            raise SWM0WTaskCoreError("case target disagrees with target tensor")
        _require_sha256(self.task_sha256, "task_sha256")
        if self.task_sha256 != canonical_sha256(self.unsigned_canonical()):
            raise SWM0WTaskCoreError("task receipt hash mismatch")

    @property
    def task_uid(self) -> str:
        return self.target_parameters.task_uid

    def for_split(self, split: str) -> TaskSplitV1:
        for item in self.splits:
            if item.split == split:
                return item
        raise SWM0WTaskCoreError(f"unsupported split: {split!r}")

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "schema_version": TASK_SCHEMA,
            "scope": {
                "confirmatory_claim": False,
                "process_isolation_enforced": False,
                "sealed_evaluation_boundary": False,
                "streaming_scope": "ONE_TASK_AT_A_TIME_MEMORY_BOUNDARY",
            },
            "split_receipts": [item.canonical() for item in self.splits],
            "target_parameters": self.target_parameters.canonical(),
            "task_uid": self.task_uid,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned_canonical(), "task_sha256": self.task_sha256}


@dataclass(frozen=True, slots=True)
class TaskScoreV1:
    task_uid: str
    split: str
    split_receipt_sha256: str
    prediction_count: int
    predictions_sha256: str
    mean_squared_error: float
    receipt_sha256: str

    def __post_init__(self) -> None:
        if not _TASK_UID_RE.fullmatch(self.task_uid) or self.split not in SPLITS:
            raise SWM0WTaskCoreError("invalid score identity")
        _require_sha256(self.split_receipt_sha256, "split_receipt_sha256")
        _require_sha256(self.predictions_sha256, "predictions_sha256")
        if type(self.prediction_count) is not int or self.prediction_count <= 0:
            raise SWM0WTaskCoreError("score prediction count must be positive")
        if not math.isfinite(self.mean_squared_error) or self.mean_squared_error < 0:
            raise SWM0WTaskCoreError("score MSE must be finite and nonnegative")
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        if self.receipt_sha256 != canonical_sha256(self.unsigned_canonical()):
            raise SWM0WTaskCoreError("score receipt hash mismatch")

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "aggregate_only": True,
            "mean_squared_error": self.mean_squared_error,
            "prediction_count": self.prediction_count,
            "predictions_sha256": self.predictions_sha256,
            "process_isolation_enforced": False,
            "schema_version": SCORE_SCHEMA,
            "sealed_evaluation_boundary": False,
            "split": self.split,
            "split_receipt_sha256": self.split_receipt_sha256,
            "task_uid": self.task_uid,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned_canonical(), "receipt_sha256": self.receipt_sha256}


def _derive_cut(seed: bytes) -> TaskCutV1:
    ordered = tuple(
        sorted(
            _ALL_SHIFT_PAIRS,
            key=lambda pair: _digest(seed, "cut", pair[0], pair[1]),
        )
    )
    return TaskCutV1(ordered)


def _quantized_tanh(parameter_numerator: int) -> int:
    value = _DECIMAL_CONTEXT.divide(Decimal(parameter_numerator), Decimal(4))
    exponential = _DECIMAL_CONTEXT.exp(_DECIMAL_CONTEXT.multiply(value, Decimal(2)))
    tanh_value = _DECIMAL_CONTEXT.divide(
        _DECIMAL_CONTEXT.subtract(exponential, Decimal(1)),
        _DECIMAL_CONTEXT.add(exponential, Decimal(1)),
    )
    scaled = _DECIMAL_CONTEXT.multiply(
        tanh_value, Decimal(2**TANH_QUANTIZATION_BITS)
    )
    return int(scaled.to_integral_value(rounding=ROUND_HALF_EVEN))


def _candidate_column(
    seed: bytes, attempt: int, role_index: int, candidate_index: int
) -> tuple[int, ...]:
    digest = _digest(seed, "tanh-affine-factor", attempt, role_index, candidate_index)
    parameters = [digest[index] % 17 - 8 for index in range(3)]
    if parameters[0] == parameters[1] == 0:
        parameters[role_index % 2] = 1
    values = tuple(
        _quantized_tanh(
            parameters[0] * (coefficient - 2)
            + parameters[1] * (operand - 2)
            + parameters[2]
        )
        for coefficient, operand in _ROLE_STATES
    )
    total = sum(values)
    centered = tuple(FIELD_ORDER**2 * value - total for value in values)
    if sum(centered) != 0:
        raise SWM0WTaskCoreError("factor centering failed")
    return centered


def _select_role_factors(
    seed: bytes, attempt: int, role_index: int
) -> tuple[tuple[int, ...], ...] | None:
    columns: list[tuple[int, ...]] = []
    for candidate_index in range(_CANDIDATE_COLUMNS):
        candidate = _candidate_column(seed, attempt, role_index, candidate_index)
        if candidate in columns:
            continue
        proposed = (*columns, candidate)
        matrix = [
            [column[row] for column in proposed]
            for row in range(FIELD_ORDER**2)
        ]
        if all(len(_pivot_rows_mod(matrix, prime)) == len(proposed) for prime in _PRIMES):
            columns.append(candidate)
            if len(columns) == TARGET_CP_TERMS:
                return tuple(columns)
    return None


def _build_integer_target(
    seed: bytes,
) -> tuple[np.ndarray, int, tuple[int, ...], tuple[int, ...], tuple[tuple[int, int], ...]]:
    for attempt in range(MAX_CONSTRUCTION_ATTEMPTS):
        factors = tuple(
            _select_role_factors(seed, attempt, role_index)
            for role_index in range(len(ROLES))
        )
        if any(item is None for item in factors):
            continue
        role_factors = tuple(item for item in factors if item is not None)
        weights = tuple(
            1 if _digest(seed, "cp-weight", attempt, term)[0] & 1 else -1
            for term in range(TARGET_CP_TERMS)
        )
        left_matrix = [
            [role_factors[0][term][row] for term in range(TARGET_CP_TERMS)]
            for row in range(FIELD_ORDER**2)
        ]
        right_matrix = [
            [
                role_factors[1][term][middle]
                * role_factors[2][term][right]
                for term in range(TARGET_CP_TERMS)
            ]
            for middle in range(FIELD_ORDER**2)
            for right in range(FIELD_ORDER**2)
        ]
        row_indices = _pivot_rows_mod(left_matrix, _PRIMES[0])
        column_indices = _pivot_rows_mod(right_matrix, _PRIMES[0])
        if len(row_indices) != TARGET_CP_TERMS or len(column_indices) != TARGET_CP_TERMS:
            continue
        tensor = np.empty((FIELD_ORDER**2,) * len(ROLES), dtype=np.int64)
        overflow = False
        for left, middle, right in itertools.product(range(FIELD_ORDER**2), repeat=3):
            value = sum(
                weights[term]
                * role_factors[0][term][left]
                * role_factors[1][term][middle]
                * role_factors[2][term][right]
                for term in range(TARGET_CP_TERMS)
            )
            if abs(value) >= 2**53:
                overflow = True
                break
            tensor[left, middle, right] = value
        if overflow:
            continue
        unfolding = tensor.reshape(FIELD_ORDER**2, FIELD_ORDER**4)
        minor = [
            [int(unfolding[row, column]) for column in column_indices]
            for row in row_indices
        ]
        determinants = tuple(
            (prime, _determinant_mod(minor, prime)) for prime in _PRIMES
        )
        if all(determinant for _, determinant in determinants):
            return tensor, attempt, row_indices, column_indices, determinants
    raise SWM0WTaskCoreError("could not derive a certified rank-17 target")


def _build_target(seed: bytes, cut: TaskCutV1) -> DyadicTargetV1:
    commitment = _seed_commitment(seed)
    task_uid = f"swm0wt_{commitment[:24]}"
    tensor, attempt, rows, columns, determinants = _build_integer_target(seed)
    tensor_sha256 = _integer_array_sha256(tensor)
    witness_unsigned = {
        "column_indices": list(columns),
        "cp_term_upper_bound": TARGET_CP_TERMS,
        "determinants": dict(determinants),
        "exact_mode0_rank": TARGET_CP_TERMS,
        "integer_tensor_sha256": tensor_sha256,
        "matrix_shape": [FIELD_ORDER**2, FIELD_ORDER**4],
        "proof": "ONE_SHARED_FINAL_INTEGER_TENSOR_MINOR_UNDER_TWO_PRIMES",
        "row_indices": list(rows),
        "schema_version": RANK_WITNESS_SCHEMA,
    }
    witness = FinalMinorWitnessV1(
        integer_tensor_sha256=tensor_sha256,
        row_indices=rows,
        column_indices=columns,
        determinants=determinants,
        receipt_sha256=canonical_sha256(witness_unsigned),
    )
    maximum = max(abs(int(value)) for value in tensor.flat)
    scale_exponent = maximum.bit_length() + 1
    target_unsigned = {
        "construction": {
            "centered_exactly": True,
            "cp_terms": TARGET_CP_TERMS,
            "decimal_precision": TANH_DECIMAL_PRECISION,
            "factor_quantization_bits": TANH_QUANTIZATION_BITS,
            "role_factors": "SEED_DERIVED_TANH_AFFINE",
        },
        "construction_attempt": attempt,
        "cut": cut.canonical(),
        "evaluator_only": True,
        "integer_tensor_sha256": tensor_sha256,
        "model_visible": False,
        "rank_witness": witness.canonical(),
        "scale_exponent": scale_exponent,
        "schema_version": TARGET_SCHEMA,
        "scope": {
            "arity": 3,
            "chronology_proven": False,
            "incidences_per_role": 1,
            "process_isolation_enforced": False,
            "sealed_evaluation_boundary": False,
            "secrecy_proven": False,
            "synthetic_target": True,
        },
        "seed_commitment_sha256": commitment,
        "target_abs_bound": TARGET_ABS_BOUND,
        "task_uid": task_uid,
    }
    return DyadicTargetV1(
        task_uid=task_uid,
        seed_commitment_sha256=commitment,
        cut=cut,
        construction_attempt=attempt,
        scale_exponent=scale_exponent,
        integer_tensor=tensor,
        integer_tensor_sha256=tensor_sha256,
        rank_witness=witness,
        receipt_sha256=canonical_sha256(target_unsigned),
    )


def _case_uid(seed: bytes, split: str, role_values: tuple[tuple[int, int], ...]) -> str:
    raw = bytes(value for pair in role_values for value in pair)
    digest = hashlib.sha256(
        TASK_VERSION.encode("ascii") + b"\x00case\x00" + seed + b"\x00" + split.encode("ascii") + raw
    ).hexdigest()
    return f"swm0wt_case_{digest[:24]}"


def _build_case(
    seed: bytes,
    target: DyadicTargetV1,
    split: str,
    shift_pair: tuple[int, int],
    left: tuple[int, int],
    middle: tuple[int, int],
) -> TaskEvaluatorCaseV1:
    coefficient_shift, operand_shift = shift_pair
    right = (
        (left[0] + middle[0] + coefficient_shift) % FIELD_ORDER,
        (left[1] + middle[1] + operand_shift) % FIELD_ORDER,
    )
    role_values = (left, middle, right)
    world = ModelWorldV1(
        tuple(
            RoleInputV1(
                role,
                (normalize_level(values[0]), normalize_level(values[1])),
            )
            for role, values in zip(ROLES, role_values)
        )
    )
    numerator = target.numerator_at(role_values)
    uid = _case_uid(seed, split, role_values)
    unsigned = {
        "case_uid": uid,
        "coefficient_shift": coefficient_shift,
        "operand_shift": operand_shift,
        "role_values": [list(pair) for pair in role_values],
        "schema_version": CASE_SCHEMA,
        "split": split,
        "target_numerator": numerator,
        "target_scale_exponent": target.scale_exponent,
        "task_uid": target.task_uid,
        "world": world.canonical(),
    }
    return TaskEvaluatorCaseV1(
        case_uid=uid,
        task_uid=target.task_uid,
        split=split,
        coefficient_shift=coefficient_shift,
        operand_shift=operand_shift,
        role_values=role_values,
        target_numerator=numerator,
        target_scale_exponent=target.scale_exponent,
        target=math.ldexp(numerator, -target.scale_exponent),
        world=world,
        receipt_sha256=canonical_sha256(unsigned),
    )


def _build_split(seed: bytes, target: DyadicTargetV1, split: str) -> TaskSplitV1:
    shift_pairs = target.cut.shift_pairs(split)
    cases = tuple(
        _build_case(seed, target, split, shift_pair, left, middle)
        for shift_pair in shift_pairs
        for left in _ROLE_STATES
        for middle in _ROLE_STATES
    )
    total = sum(case.target_numerator for case in cases)
    total_squares = sum(case.target_numerator**2 for case in cases)
    unsigned = {
        "case_count": len(cases),
        "case_receipts_in_evaluation_order": [
            [case.case_uid, case.receipt_sha256] for case in cases
        ],
        "schema_version": SPLIT_SCHEMA,
        "shift_pairs": [list(pair) for pair in shift_pairs],
        "split": split,
        "target_integer_sum": total,
        "target_integer_sum_of_squares": total_squares,
        "task_uid": target.task_uid,
    }
    return TaskSplitV1(
        task_uid=target.task_uid,
        split=split,
        shift_pairs=shift_pairs,
        cases=cases,
        target_integer_sum=total,
        target_integer_sum_of_squares=total_squares,
        receipt_sha256=canonical_sha256(unsigned),
    )


def build_task_from_external_seed(seed: bytes) -> StreamedTaskV1:
    """Build one task from exact bytes of length >=32.

    Longer public-randomness values are accepted byte-for-byte.  No chronology
    or secrecy is implied by supplying the bytes here.
    """

    _seed_commitment(seed)
    cut = _derive_cut(seed)
    target = _build_target(seed, cut)
    splits = tuple(_build_split(seed, target, split) for split in SPLITS)
    unsigned = {
        "schema_version": TASK_SCHEMA,
        "scope": {
            "confirmatory_claim": False,
            "process_isolation_enforced": False,
            "sealed_evaluation_boundary": False,
            "streaming_scope": "ONE_TASK_AT_A_TIME_MEMORY_BOUNDARY",
        },
        "split_receipts": [item.canonical() for item in splits],
        "target_parameters": target.canonical(),
        "task_uid": target.task_uid,
    }
    return StreamedTaskV1(
        target_parameters=target,
        splits=splits,
        task_sha256=canonical_sha256(unsigned),
    )


def evaluator_cases_from_split(
    task: StreamedTaskV1, split: str
) -> tuple[TaskEvaluatorCaseV1, ...]:
    """Return evaluator envelopes, including gold labels."""

    if not isinstance(task, StreamedTaskV1):
        raise SWM0WTaskCoreError("case lookup requires a streamed task")
    return task.for_split(split).cases


def model_worlds_from_split(
    task: StreamedTaskV1, split: str
) -> Iterator[ModelWorldV1]:
    """Return an iterator whose retained state contains model worlds only."""

    if not isinstance(task, StreamedTaskV1):
        raise SWM0WTaskCoreError("model-world lookup requires a streamed task")
    worlds = tuple(case.world for case in task.for_split(split).cases)
    return iter(worlds)


def score_task_predictions(
    task: StreamedTaskV1,
    split: str,
    predictions: Sequence[float] | np.ndarray,
) -> TaskScoreV1:
    """Score predictions evaluator-side; this is not a process boundary."""

    if not isinstance(task, StreamedTaskV1):
        raise SWM0WTaskCoreError("scoring requires a streamed task")
    registered = task.for_split(split)
    try:
        values = np.ascontiguousarray(predictions, dtype="<f8")
    except (TypeError, ValueError) as error:
        raise SWM0WTaskCoreError("predictions must be finite scalars") from error
    if values.ndim != 1 or len(values) != len(registered.cases):
        raise SWM0WTaskCoreError("predictions require exact one-dimensional length")
    if not np.isfinite(values).all():
        raise SWM0WTaskCoreError("predictions must be finite scalars")
    try:
        mse = math.fsum(
            (float(prediction) - case.target) ** 2
            for prediction, case in zip(values, registered.cases)
        ) / len(values)
    except OverflowError as error:
        raise SWM0WTaskCoreError("prediction MSE is not finite") from error
    if not math.isfinite(mse):
        raise SWM0WTaskCoreError("prediction MSE is not finite")
    prediction_sha = _float_array_sha256(values)
    unsigned = {
        "aggregate_only": True,
        "mean_squared_error": mse,
        "prediction_count": len(values),
        "predictions_sha256": prediction_sha,
        "process_isolation_enforced": False,
        "schema_version": SCORE_SCHEMA,
        "sealed_evaluation_boundary": False,
        "split": split,
        "split_receipt_sha256": registered.receipt_sha256,
        "task_uid": task.task_uid,
    }
    return TaskScoreV1(
        task_uid=task.task_uid,
        split=split,
        split_receipt_sha256=registered.receipt_sha256,
        prediction_count=len(values),
        predictions_sha256=prediction_sha,
        mean_squared_error=mse,
        receipt_sha256=canonical_sha256(unsigned),
    )


__all__ = [
    "FinalMinorWitnessV1",
    "MINIMUM_SEED_BYTES",
    "REFERENCE_WIDTH",
    "SCORE_SCHEMA",
    "SWM0WTaskCoreError",
    "StreamedTaskV1",
    "TARGET_ABS_BOUND",
    "TARGET_CP_TERMS",
    "TANH_QUANTIZATION_BITS",
    "TASK_VERSION",
    "TaskCutV1",
    "TaskEvaluatorCaseV1",
    "TaskScoreV1",
    "TaskSplitV1",
    "build_task_from_external_seed",
    "canonical_json",
    "canonical_sha256",
    "evaluator_cases_from_split",
    "model_worlds_from_split",
    "score_task_predictions",
]
