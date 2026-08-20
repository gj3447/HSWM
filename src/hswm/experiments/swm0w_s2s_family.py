"""Seed-varying finite task family for the unjudged SWM-0W-S2S bridge.

This module is additive to :mod:`swm0w_s2s_worlds`.  The v1 fixed fixture and
its historical hashes remain unchanged.  V2 keeps the same fixed orthogonal
feature frame while future public randomness draws rank coefficients and a
held-out split.  One future seed drives domain-separated, indexed
pseudorandom draws *with replacement*.  Duplicate structural targets or
complete tasks are recorded by ``TaskBatchV2`` and are never silently skipped
or rerolled.  This is a deterministic generator conditional on its seed and
hash/XOF assumption, not an information-theoretic source of independent bits.

The family therefore supplies distinct coefficient/split laws over one fixed
feature frame.  It is not evidence for independent mechanisms, independent
feature families, or non-isomorphism under arbitrary relabelings.  Any task
bootstrap remains a protocol-level procedure conditional on this generator;
this module neither performs it nor turns indexed draws into mechanism-level
replicates.

Scientific status: ``UNJUDGED_TASK_FAMILY_ONLY``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import itertools
from typing import Any, Iterator, Mapping, Sequence

from hswm.experiments.swm0w_s2s_worlds import (
    CHANNELS,
    FACTOR_FRAME,
    FACTOR_GRAM_DIAGONAL,
    FIELD_ORDER,
    FIXED_FACTOR_TABLES,
    MINIMUM_SEED_BYTES,
    ModelWorldV1,
    ROLES,
    SWM0WS2SWorldError,
    canonical_sha256,
)


SCIENTIFIC_STATUS = "UNJUDGED_TASK_FAMILY_ONLY"
FAMILY_DEFINITION_VERSION = "hswm-swm0w-s2s-family-definition/v2"
FAMILY_CERTIFICATE_VERSION = "hswm-swm0w-s2s-family-certificate/v2"
STRUCTURAL_TARGET_VERSION = "hswm-swm0w-s2s-structural-target/v2"
STRUCTURAL_TASK_VERSION = "hswm-swm0w-s2s-structural-task/v2"
TASK_MANIFEST_VERSION = "hswm-swm0w-s2s-task/v2"
TASK_BATCH_VERSION = "hswm-swm0w-s2s-task-batch/v2"
TARGET_RANK = 2
TARGET_SCALE_EXPONENT = 19
ANALYTIC_NUMERATOR_BOUND = 288_120
GAIN_LEVELS = tuple(range(8, 16))
REFERENCE_GAIN = 8
GAIN_ORDER = tuple(
    (role, channel, rank)
    for role in range(3)
    for channel in range(2)
    for rank in range(2)
)
TARGET_POPULATION_SIZE = 8**11
MAX_TASK_BATCH_SIZE = 4_096
MAX_ALLOCATION_REJECTION_BYTES = 4_096

SPLITS = ("train", "dev", "test")
SPLIT_COEFFICIENTS = tuple(
    (1, q1, q2) for q1 in range(1, FIELD_ORDER) for q2 in range(1, FIELD_ORDER)
)


def _split_allocations() -> tuple[tuple[tuple[str, tuple[int, ...]], ...], ...]:
    allocations = []
    for dev in range(FIELD_ORDER):
        remaining = tuple(value for value in range(FIELD_ORDER) if value != dev)
        for train in itertools.combinations(remaining, 2):
            test = tuple(value for value in remaining if value not in train)
            allocations.append(
                (("train", tuple(train)), ("dev", (dev,)), ("test", test))
            )
    return tuple(allocations)


SPLIT_ALLOCATIONS = _split_allocations()
SPLIT_POPULATION_SIZE = len(SPLIT_COEFFICIENTS) * len(SPLIT_ALLOCATIONS)
SPLIT_COUNTS: Mapping[str, int] = {
    "train": 2 * FIELD_ORDER**5,
    "dev": FIELD_ORDER**5,
    "test": 2 * FIELD_ORDER**5,
}

BROADCAST_DAMAGE_MINIMUM = (2_027_528, 4_509_001)
ROLE_CYCLES = ((1, 2, 0), (2, 0, 1))
ROLE_CYCLE_DAMAGE_MINIMA = (
    ((1, 2, 0), 420_960_389, 416_884_981),
    ((2, 0, 1), 17_109_007, 16_617_375),
)
CERTIFIED_BROADCAST_FLOOR = (2, 5)
CERTIFIED_ROLE_CYCLE_FLOOR = (4, 5)

_SEED_COMMITMENT_DOMAIN = b"hswm-swm0w-s2s-family-external-seed/v2\x00"
_GAIN_DRAW_DOMAIN = b"hswm-swm0w-s2s-family-gain-draw/v2\x00"
_SPLIT_Q_DRAW_DOMAIN = b"hswm-swm0w-s2s-family-split-q-draw/v2\x00"
_SPLIT_ALLOCATION_DRAW_DOMAIN = (
    b"hswm-swm0w-s2s-family-split-allocation-draw/v2\x00"
)
_GENERATOR_VECTOR_SEED = bytes(range(32))
_GENERATOR_VECTOR_DRAW_INDICES = (0, 1, 2**64 - 1)
_SHA256_ALPHABET = frozenset("0123456789abcdef")


class SWM0WS2SFamilyError(SWM0WS2SWorldError):
    """Raised when a V2 task-family boundary is malformed."""


def _exact_tree_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is tuple:
        return len(left) == len(right) and all(
            _exact_tree_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return bool(left == right)


def _require_sha256(value: object, name: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in _SHA256_ALPHABET for character in value)
    ):
        raise SWM0WS2SFamilyError(f"{name} must be a lowercase SHA-256")


def _require_seed(external_seed: object) -> bytes:
    if type(external_seed) is not bytes or len(external_seed) < MINIMUM_SEED_BYTES:
        raise SWM0WS2SFamilyError(
            f"external seed must be exact bytes with at least {MINIMUM_SEED_BYTES} bytes"
        )
    return external_seed


def _require_draw_index(draw_index: object) -> int:
    if type(draw_index) is not int or not 0 <= draw_index < 2**64:
        raise SWM0WS2SFamilyError("draw index must be an exact unsigned 64-bit integer")
    return draw_index


def _draw_material(domain: bytes, external_seed: bytes, draw_index: int) -> bytes:
    return (
        domain
        + len(external_seed).to_bytes(8, "big")
        + external_seed
        + draw_index.to_bytes(8, "big")
    )


def _xof(domain: bytes, external_seed: bytes, draw_index: int) -> Any:
    return hashlib.shake_256(_draw_material(domain, external_seed, draw_index))


def _seed_commitment(external_seed: bytes) -> str:
    return hashlib.sha256(
        _SEED_COMMITMENT_DOMAIN
        + len(external_seed).to_bytes(8, "big")
        + external_seed
    ).hexdigest()


def _derive_rank_gains(external_seed: bytes, draw_index: int) -> tuple[int, ...]:
    # Five bytes contain forty unbiased XOF bits.  Taking the first thirty-three
    # gives one exactly uniform integer in [0, 2**33), hence eleven base-8 digits.
    value = (
        int.from_bytes(
            _xof(_GAIN_DRAW_DOMAIN, external_seed, draw_index).digest(5), "big"
        )
        >> 7
    )
    digits = tuple((value >> (3 * shift)) & 0b111 for shift in reversed(range(11)))
    return (REFERENCE_GAIN, *(REFERENCE_GAIN + digit for digit in digits))


def _derive_split_coefficients(
    external_seed: bytes, draw_index: int
) -> tuple[int, int, int]:
    value = _xof(_SPLIT_Q_DRAW_DOMAIN, external_seed, draw_index).digest(1)[0] >> 4
    return (1, 1 + (value >> 2), 1 + (value & 0b11))


def _derive_allocation_index(external_seed: bytes, draw_index: int) -> int:
    # Rejecting 240..255 makes byte % 30 exactly uniform. hashlib's SHAKE digest
    # is a repeatable prefix, so requesting n+1 bytes exposes the next XOF byte.
    stream = _xof(_SPLIT_ALLOCATION_DRAW_DOMAIN, external_seed, draw_index)
    for offset in range(MAX_ALLOCATION_REJECTION_BYTES):
        candidate = stream.digest(offset + 1)[offset]
        if candidate < 240:
            return candidate % len(SPLIT_ALLOCATIONS)
    raise SWM0WS2SFamilyError("allocation XOF rejection budget exhausted")


def _generator_behavior_vectors() -> dict[str, Any]:
    """Return fixed public vectors computed through the executable derivations."""

    seed = _GENERATOR_VECTOR_SEED
    return {
        "draws": [
            {
                "allocation_index": _derive_allocation_index(seed, draw_index),
                "draw_index": draw_index,
                "rank_gains": list(_derive_rank_gains(seed, draw_index)),
                "split_coefficients": list(
                    _derive_split_coefficients(seed, draw_index)
                ),
            }
            for draw_index in _GENERATOR_VECTOR_DRAW_INDICES
        ],
        "external_seed_hex": seed.hex(),
        "seed_commitment_sha256": _seed_commitment(seed),
    }


def family_definition_payload() -> dict[str, Any]:
    return {
        "analytic_numerator_bound": ANALYTIC_NUMERATOR_BOUND,
        "base_factor_tables": [
            {"key": key, "values": list(values)} for key, values in FIXED_FACTOR_TABLES
        ],
        "factor_frame": [list(row) for row in FACTOR_FRAME],
        "factor_gram_diagonal": list(FACTOR_GRAM_DIAGONAL),
        "gain_domain": {
            "gain_order": [list(index) for index in GAIN_ORDER],
            "reference_gain": REFERENCE_GAIN,
            "reference_gain_index": 0,
            "remaining_gain_levels": list(GAIN_LEVELS),
            "target_population_size": TARGET_POPULATION_SIZE,
        },
        "inference_boundary": (
            "TASK_BOOTSTRAP_IS_PROTOCOL_LEVEL_AND_CONDITIONAL_ON_THIS_GENERATOR"
        ),
        "sampling_scope": (
            "INDEXED_PSEUDORANDOM_WITH_REPLACEMENT_FROM_ONE_FIXED_FEATURE_FRAME"
        ),
        "schema_version": FAMILY_DEFINITION_VERSION,
        "seed_generator": {
            "allocation_draw": {
                "accepted_byte_range": [0, 239],
                "domain_hex": _SPLIT_ALLOCATION_DRAW_DOMAIN.hex(),
                "mapping": "ACCEPTED_BYTE_MOD_30",
                "rejection_byte_budget": MAX_ALLOCATION_REJECTION_BYTES,
                "rejected_byte_range": [240, 255],
                "xof": "SHAKE256",
            },
            "behavior_vectors": _generator_behavior_vectors(),
            "duplicate_semantics": {
                "comparison_keys": [
                    "structural_target_sha256",
                    "structural_task_sha256",
                ],
                "record": "(LATER_DRAW_INDEX,FIRST_EARLIER_EQUAL_DRAW_INDEX)",
                "sampling_action": "RETAIN_DRAW_NEVER_SKIP_NEVER_REROLL",
            },
            "gain_draw": {
                "domain_hex": _GAIN_DRAW_DOMAIN.hex(),
                "mapping": "FIRST_33_OF_40_XOF_BITS_AS_ELEVEN_MSB_FIRST_BASE8_DIGITS",
                "xof": "SHAKE256",
            },
            "indexed_draw_preimage_framing": [
                "LITERAL_DOMAIN_BYTES",
                "UINT64_BE_EXTERNAL_SEED_LENGTH",
                "EXTERNAL_SEED_BYTES",
                "UINT64_BE_DRAW_INDEX",
            ],
            "maximum_batch_size": MAX_TASK_BATCH_SIZE,
            "minimum_external_seed_bytes": MINIMUM_SEED_BYTES,
            "seed_commitment": {
                "domain_hex": _SEED_COMMITMENT_DOMAIN.hex(),
                "hash": "SHA256",
                "preimage_framing": [
                    "LITERAL_DOMAIN_BYTES",
                    "UINT64_BE_EXTERNAL_SEED_LENGTH",
                    "EXTERNAL_SEED_BYTES",
                ],
            },
            "split_allocation_table_ordered": [
                [[split, list(residues)] for split, residues in allocation]
                for allocation in SPLIT_ALLOCATIONS
            ],
            "split_coefficient_draw": {
                "domain_hex": _SPLIT_Q_DRAW_DOMAIN.hex(),
                "mapping": "FIRST_4_XOF_BITS_AS_TWO_MSB_FIRST_BASE4_DIGITS_PLUS_ONE",
                "xof": "SHAKE256",
            },
            "split_coefficient_table_ordered": [
                list(coefficients) for coefficients in SPLIT_COEFFICIENTS
            ],
            "with_replacement": True,
        },
        "scientific_status": SCIENTIFIC_STATUS,
        "split_domain": {
            "allocation_count": len(SPLIT_ALLOCATIONS),
            "coefficient_count": len(SPLIT_COEFFICIENTS),
            "coefficient_rule": "q=(1,q1,q2), q1,q2 in F5\\{0}",
            "population_size": SPLIT_POPULATION_SIZE,
            "residue_cardinalities": {"dev": 1, "test": 2, "train": 2},
        },
        "symmetry": "WITHIN_ROLE_MEMBER_GROUP_S2_CUBED",
        "target_formula": "RECIPIENT_CONDITIONED_SET_FACTORIZED_RANK_2_WITH_GAIN_ON_P",
        "target_rank": TARGET_RANK,
        "target_scale_exponent": TARGET_SCALE_EXPONENT,
    }


FAMILY_DEFINITION_SHA256 = canonical_sha256(family_definition_payload())


def family_certificate_payload() -> dict[str, Any]:
    return {
        "analytic_numerator_bound": ANALYTIC_NUMERATOR_BOUND,
        "broadcast_damage_minimum": {
            "denominator": BROADCAST_DAMAGE_MINIMUM[1],
            "numerator": BROADCAST_DAMAGE_MINIMUM[0],
        },
        "certified_broadcast_floor": {
            "denominator": CERTIFIED_BROADCAST_FLOOR[1],
            "numerator": CERTIFIED_BROADCAST_FLOOR[0],
        },
        "certified_role_cycle_floor": {
            "denominator": CERTIFIED_ROLE_CYCLE_FLOOR[1],
            "numerator": CERTIFIED_ROLE_CYCLE_FLOOR[0],
        },
        "checks": [
            "CENTERING",
            "EXACT_RANK_2",
            "S2_CUBED_EQUIVARIANCE",
            "RECIPIENT_STAR_ORTHOGONALITY",
            "ONE_TO_FIVE_COORDINATE_SPLIT_BALANCE",
            "BROADCAST_AND_BOTH_ROLE_CYCLE_DAMAGE",
        ],
        "exact_minima_scope": "PRECOMPUTED_EXACT_FAMILY_MATH_AUDIT_CONSTANTS",
        "family_definition_sha256": FAMILY_DEFINITION_SHA256,
        "role_cycle_damage_minima": [
            {
                "cycle": list(cycle),
                "denominator": denominator,
                "numerator": numerator,
            }
            for cycle, numerator, denominator in ROLE_CYCLE_DAMAGE_MINIMA
        ],
        "schema_version": FAMILY_CERTIFICATE_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "universal_floor_proof": (
            "EXACT_INTEGER_SYLVESTER_5N_MINUS_4D_POSITIVE_DEFINITE"
        ),
    }


FAMILY_CERTIFICATE_SHA256 = canonical_sha256(family_certificate_payload())


def _gain_entries(rank_gains: Sequence[int]) -> list[dict[str, Any]]:
    return [
        {
            "channel": CHANNELS[channel],
            "gain": rank_gains[index],
            "rank": rank,
            "role": ROLES[role],
        }
        for index, (role, channel, rank) in enumerate(GAIN_ORDER)
    ]


def _structural_target_payload(rank_gains: Sequence[int]) -> dict[str, Any]:
    return {
        "family_definition_sha256": FAMILY_DEFINITION_SHA256,
        "rank_gains": _gain_entries(rank_gains),
        "schema_version": STRUCTURAL_TARGET_VERSION,
    }


def _split_payload(
    coefficients: Sequence[int],
    residues: Sequence[tuple[str, Sequence[int]]],
) -> dict[str, Any]:
    return {
        "coefficients": list(coefficients),
        "residues": {split: list(values) for split, values in residues},
    }


def _structural_task_payload(
    structural_target_sha256: str,
    coefficients: Sequence[int],
    residues: Sequence[tuple[str, Sequence[int]]],
) -> dict[str, Any]:
    return {
        "schema_version": STRUCTURAL_TASK_VERSION,
        "split": _split_payload(coefficients, residues),
        "structural_target_sha256": structural_target_sha256,
    }


def _manifest_payload(
    *,
    seed_commitment_sha256: str,
    draw_index: int,
    rank_gains: Sequence[int],
    split_coefficients: Sequence[int],
    split_residues: Sequence[tuple[str, Sequence[int]]],
    structural_target_sha256: str,
    structural_task_sha256: str,
) -> dict[str, Any]:
    return {
        "draw_index": draw_index,
        "family_certificate_sha256": FAMILY_CERTIFICATE_SHA256,
        "family_definition_sha256": FAMILY_DEFINITION_SHA256,
        "rank_gains": _gain_entries(rank_gains),
        "schema_version": TASK_MANIFEST_VERSION,
        "seed_commitment_sha256": seed_commitment_sha256,
        "split": _split_payload(split_coefficients, split_residues),
        "structural_target_sha256": structural_target_sha256,
        "structural_task_sha256": structural_task_sha256,
    }


def _require_rank_gains(rank_gains: object) -> None:
    if (
        type(rank_gains) is not tuple
        or len(rank_gains) != len(GAIN_ORDER)
        or any(type(gain) is not int for gain in rank_gains)
        or rank_gains[0] != REFERENCE_GAIN
        or any(gain not in GAIN_LEVELS for gain in rank_gains[1:])
    ):
        raise SWM0WS2SFamilyError(
            "rank gains require fixed leading 8 and eleven exact integers in 8..15"
        )


def _require_split(
    coefficients: object, residues: object
) -> None:
    if (
        type(coefficients) is not tuple
        or len(coefficients) != 3
        or any(type(value) is not int for value in coefficients)
        or coefficients not in SPLIT_COEFFICIENTS
    ):
        raise SWM0WS2SFamilyError("split coefficients must be one normalized family member")
    if type(residues) is not tuple or not any(
        _exact_tree_equal(residues, allocation) for allocation in SPLIT_ALLOCATIONS
    ):
        raise SWM0WS2SFamilyError("split residues must be one canonical labeled allocation")


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
        raise SWM0WS2SFamilyError("targets must be six immutable integer 2-vectors")


def _syndrome(
    raw_values: Sequence[int], coefficients: Sequence[int]
) -> int:
    return sum(
        coefficients[role] * (raw_values[2 * role] + raw_values[2 * role + 1])
        for role in range(3)
    ) % FIELD_ORDER


def _split_for_values(
    raw_values: Sequence[int],
    coefficients: Sequence[int],
    residues: Sequence[tuple[str, Sequence[int]]],
) -> str:
    syndrome = _syndrome(raw_values, coefficients)
    for split, split_residues in residues:
        if syndrome in split_residues:
            return split
    raise AssertionError("canonical split residues must partition F5")


def _target_from_values(
    raw_values: Sequence[int], rank_gains: Sequence[int]
) -> tuple[tuple[int, int], ...]:
    factors = dict(FIXED_FACTOR_TABLES)
    outputs = []
    for role in range(3):
        for member in range(2):
            recipient = raw_values[2 * role + member]
            comember = raw_values[2 * role + 1 - member]
            channels = []
            for channel in range(2):
                total = 0
                for rank in range(2):
                    gain = rank_gains[4 * role + 2 * channel + rank]
                    value = (
                        gain
                        * factors[f"P:r{role}:c{channel}:k{rank}"][recipient]
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


@dataclass(frozen=True, slots=True)
class TaskSpecV2:
    """One indexed pseudorandom task draw from the fixed-frame V2 family."""

    seed_commitment_sha256: str
    draw_index: int
    rank_gains: tuple[int, ...]
    split_coefficients: tuple[int, int, int]
    split_residues: tuple[tuple[str, tuple[int, ...]], ...]
    family_definition_sha256: str
    family_certificate_sha256: str
    structural_target_sha256: str
    structural_task_sha256: str
    manifest_sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.seed_commitment_sha256, "seed commitment")
        _require_draw_index(self.draw_index)
        _require_rank_gains(self.rank_gains)
        _require_split(self.split_coefficients, self.split_residues)
        _require_sha256(self.family_definition_sha256, "family definition SHA")
        _require_sha256(self.family_certificate_sha256, "family certificate SHA")
        _require_sha256(self.structural_target_sha256, "structural target SHA")
        _require_sha256(self.structural_task_sha256, "structural task SHA")
        _require_sha256(self.manifest_sha256, "task manifest SHA")
        if self.family_definition_sha256 != FAMILY_DEFINITION_SHA256:
            raise SWM0WS2SFamilyError("task family definition SHA drifted")
        if self.family_certificate_sha256 != FAMILY_CERTIFICATE_SHA256:
            raise SWM0WS2SFamilyError("task family certificate SHA drifted")
        expected_target = canonical_sha256(_structural_target_payload(self.rank_gains))
        if self.structural_target_sha256 != expected_target:
            raise SWM0WS2SFamilyError("structural target SHA does not match")
        expected_task = canonical_sha256(
            _structural_task_payload(
                expected_target, self.split_coefficients, self.split_residues
            )
        )
        if self.structural_task_sha256 != expected_task:
            raise SWM0WS2SFamilyError("structural task SHA does not match")
        expected_manifest = canonical_sha256(self.manifest_payload())
        if self.manifest_sha256 != expected_manifest:
            raise SWM0WS2SFamilyError("task manifest SHA does not match")

    def manifest_payload(self) -> dict[str, Any]:
        return _manifest_payload(
            seed_commitment_sha256=self.seed_commitment_sha256,
            draw_index=self.draw_index,
            rank_gains=self.rank_gains,
            split_coefficients=self.split_coefficients,
            split_residues=self.split_residues,
            structural_target_sha256=self.structural_target_sha256,
            structural_task_sha256=self.structural_task_sha256,
        )

    def canonical(self) -> dict[str, Any]:
        return {**self.manifest_payload(), "manifest_sha256": self.manifest_sha256}

    def gain_mapping(self) -> dict[tuple[int, int, int], int]:
        return dict(zip(GAIN_ORDER, self.rank_gains, strict=True))

    def gain(self, role: int, channel: int, rank: int) -> int:
        if (
            type(role) is not int
            or type(channel) is not int
            or type(rank) is not int
            or not 0 <= role < 3
            or not 0 <= channel < 2
            or not 0 <= rank < 2
        ):
            raise SWM0WS2SFamilyError("gain index must be exact in-range integers")
        return self.rank_gains[4 * role + 2 * channel + rank]

    def split_for_world(self, world: ModelWorldV1) -> str:
        if type(world) is not ModelWorldV1:
            raise SWM0WS2SFamilyError("split requires exact ModelWorldV1")
        return _split_for_values(
            world.raw_values, self.split_coefficients, self.split_residues
        )

    def target(self, world: ModelWorldV1) -> tuple[tuple[int, int], ...]:
        if type(world) is not ModelWorldV1:
            raise SWM0WS2SFamilyError("target requires exact ModelWorldV1")
        return _target_from_values(world.raw_values, self.rank_gains)

    def case(self, raw_values: tuple[int, int, int, int, int, int]) -> EvaluatorCaseV2:
        world = ModelWorldV1(raw_values)
        return EvaluatorCaseV2(
            self,
            world,
            self.split_for_world(world),
            self.target(world),
        )

    def iter_cases(self, split: str | None = None) -> Iterator[EvaluatorCaseV2]:
        if split is not None and split not in SPLITS:
            raise SWM0WS2SFamilyError(f"unsupported split: {split!r}")
        for values in itertools.product(range(FIELD_ORDER), repeat=6):
            world = ModelWorldV1(values)
            world_split = self.split_for_world(world)
            if split is None or split == world_split:
                yield EvaluatorCaseV2(
                    self,
                    world,
                    world_split,
                    self.target(world),
                )


@dataclass(frozen=True, slots=True)
class EvaluatorCaseV2:
    """Evaluator-owned task/world envelope; only ``world`` is model-visible."""

    task: TaskSpecV2
    world: ModelWorldV1
    split: str
    target_numerators: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if type(self.task) is not TaskSpecV2:
            raise SWM0WS2SFamilyError("case requires exact TaskSpecV2")
        if type(self.world) is not ModelWorldV1:
            raise SWM0WS2SFamilyError("case requires exact ModelWorldV1")
        if type(self.split) is not str or self.split != self.task.split_for_world(
            self.world
        ):
            raise SWM0WS2SFamilyError("case split disagrees with its task and public world")
        _require_targets(self.target_numerators)
        if self.target_numerators != self.task.target(self.world):
            raise SWM0WS2SFamilyError("case targets disagree with its structural task")
        if (
            max(abs(value) for row in self.target_numerators for value in row)
            > ANALYTIC_NUMERATOR_BOUND
        ):
            raise SWM0WS2SFamilyError("case target exceeds the analytic bound")

    def model_visible(self) -> dict[str, Any]:
        return self.world.model_visible()

    def target_floats(self) -> tuple[tuple[float, float], ...]:
        scale = float(2**TARGET_SCALE_EXPONENT)
        return tuple(tuple(value / scale for value in row) for row in self.target_numerators)


def _duplicate_pairs(
    tasks: Sequence[TaskSpecV2], attribute: str
) -> tuple[tuple[int, int], ...]:
    first_seen: dict[str, int] = {}
    duplicates = []
    for index, task in enumerate(tasks):
        key = getattr(task, attribute)
        if key in first_seen:
            duplicates.append((index, first_seen[key]))
        else:
            first_seen[key] = index
    return tuple(duplicates)


def _batch_payload(
    seed_commitment_sha256: str,
    requested_count: int,
    tasks: Sequence[TaskSpecV2],
    duplicate_target_draws: Sequence[tuple[int, int]],
    duplicate_task_draws: Sequence[tuple[int, int]],
) -> dict[str, Any]:
    return {
        "duplicate_structural_target_draws": [list(pair) for pair in duplicate_target_draws],
        "duplicate_structural_task_draws": [list(pair) for pair in duplicate_task_draws],
        "requested_count": requested_count,
        "schema_version": TASK_BATCH_VERSION,
        "seed_commitment_sha256": seed_commitment_sha256,
        "task_manifest_sha256s": [task.manifest_sha256 for task in tasks],
    }


@dataclass(frozen=True, slots=True)
class TaskBatchV2:
    """Indexed draws including duplicates; bootstrap policy lives elsewhere."""

    seed_commitment_sha256: str
    requested_count: int
    tasks: tuple[TaskSpecV2, ...]
    duplicate_structural_target_draws: tuple[tuple[int, int], ...]
    duplicate_structural_task_draws: tuple[tuple[int, int], ...]
    batch_sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.seed_commitment_sha256, "batch seed commitment")
        _require_sha256(self.batch_sha256, "batch SHA")
        if (
            type(self.requested_count) is not int
            or not 0 < self.requested_count <= MAX_TASK_BATCH_SIZE
        ):
            raise SWM0WS2SFamilyError(
                f"requested count must be an exact integer in 1..{MAX_TASK_BATCH_SIZE}"
            )
        if type(self.tasks) is not tuple or len(self.tasks) != self.requested_count:
            raise SWM0WS2SFamilyError("batch must retain exactly every requested draw")
        if any(type(task) is not TaskSpecV2 for task in self.tasks):
            raise SWM0WS2SFamilyError("batch tasks must be exact TaskSpecV2 entries")
        if any(
            task.seed_commitment_sha256 != self.seed_commitment_sha256
            or task.draw_index != index
            for index, task in enumerate(self.tasks)
        ):
            raise SWM0WS2SFamilyError(
                "batch tasks must preserve their indexed pseudorandom draws"
            )
        expected_targets = _duplicate_pairs(self.tasks, "structural_target_sha256")
        expected_tasks = _duplicate_pairs(self.tasks, "structural_task_sha256")
        if not _exact_tree_equal(
            self.duplicate_structural_target_draws, expected_targets
        ):
            raise SWM0WS2SFamilyError("duplicate structural-target record is incomplete")
        if not _exact_tree_equal(self.duplicate_structural_task_draws, expected_tasks):
            raise SWM0WS2SFamilyError("duplicate structural-task record is incomplete")
        expected_hash = canonical_sha256(self.batch_payload())
        if self.batch_sha256 != expected_hash:
            raise SWM0WS2SFamilyError("batch SHA does not match")

    def batch_payload(self) -> dict[str, Any]:
        return _batch_payload(
            self.seed_commitment_sha256,
            self.requested_count,
            self.tasks,
            self.duplicate_structural_target_draws,
            self.duplicate_structural_task_draws,
        )

    def canonical(self) -> dict[str, Any]:
        return {**self.batch_payload(), "batch_sha256": self.batch_sha256}


def _build_task(
    *,
    seed_commitment_sha256: str,
    draw_index: int,
    rank_gains: tuple[int, ...],
    split_coefficients: tuple[int, int, int],
    split_residues: tuple[tuple[str, tuple[int, ...]], ...],
) -> TaskSpecV2:
    structural_target = canonical_sha256(_structural_target_payload(rank_gains))
    structural_task = canonical_sha256(
        _structural_task_payload(
            structural_target, split_coefficients, split_residues
        )
    )
    payload = _manifest_payload(
        seed_commitment_sha256=seed_commitment_sha256,
        draw_index=draw_index,
        rank_gains=rank_gains,
        split_coefficients=split_coefficients,
        split_residues=split_residues,
        structural_target_sha256=structural_target,
        structural_task_sha256=structural_task,
    )
    return TaskSpecV2(
        seed_commitment_sha256,
        draw_index,
        rank_gains,
        split_coefficients,
        split_residues,
        FAMILY_DEFINITION_SHA256,
        FAMILY_CERTIFICATE_SHA256,
        structural_target,
        structural_task,
        canonical_sha256(payload),
    )


def generate_task(*, external_seed: bytes, draw_index: int = 0) -> TaskSpecV2:
    """Generate one indexed pseudorandom draw without inspecting its target."""

    seed = _require_seed(external_seed)
    index = _require_draw_index(draw_index)
    return _build_task(
        seed_commitment_sha256=_seed_commitment(seed),
        draw_index=index,
        rank_gains=_derive_rank_gains(seed, index),
        split_coefficients=_derive_split_coefficients(seed, index),
        split_residues=SPLIT_ALLOCATIONS[_derive_allocation_index(seed, index)],
    )


def generate_task_batch(*, external_seed: bytes, count: int) -> TaskBatchV2:
    """Generate indexed draws with replacement and retain every duplicate."""

    seed = _require_seed(external_seed)
    if type(count) is not int or not 0 < count <= MAX_TASK_BATCH_SIZE:
        raise SWM0WS2SFamilyError(
            f"count must be a positive exact integer at most {MAX_TASK_BATCH_SIZE}"
        )
    commitment = _seed_commitment(seed)
    tasks = tuple(generate_task(external_seed=seed, draw_index=index) for index in range(count))
    duplicate_targets = _duplicate_pairs(tasks, "structural_target_sha256")
    duplicate_tasks = _duplicate_pairs(tasks, "structural_task_sha256")
    payload = _batch_payload(
        commitment, count, tasks, duplicate_targets, duplicate_tasks
    )
    return TaskBatchV2(
        commitment,
        count,
        tasks,
        duplicate_targets,
        duplicate_tasks,
        canonical_sha256(payload),
    )


__all__ = [
    "ANALYTIC_NUMERATOR_BOUND",
    "BROADCAST_DAMAGE_MINIMUM",
    "CERTIFIED_BROADCAST_FLOOR",
    "CERTIFIED_ROLE_CYCLE_FLOOR",
    "EvaluatorCaseV2",
    "FAMILY_CERTIFICATE_SHA256",
    "FAMILY_DEFINITION_SHA256",
    "GAIN_LEVELS",
    "GAIN_ORDER",
    "MAX_ALLOCATION_REJECTION_BYTES",
    "MAX_TASK_BATCH_SIZE",
    "REFERENCE_GAIN",
    "ROLE_CYCLES",
    "ROLE_CYCLE_DAMAGE_MINIMA",
    "SCIENTIFIC_STATUS",
    "SPLIT_ALLOCATIONS",
    "SPLIT_COEFFICIENTS",
    "SPLIT_COUNTS",
    "SPLIT_POPULATION_SIZE",
    "SWM0WS2SFamilyError",
    "TARGET_POPULATION_SIZE",
    "TARGET_RANK",
    "TARGET_SCALE_EXPONENT",
    "TaskBatchV2",
    "TaskSpecV2",
    "family_certificate_payload",
    "family_definition_payload",
    "generate_task",
    "generate_task_batch",
]
