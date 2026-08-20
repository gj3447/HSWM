"""Structurally disjoint F5 worlds for the learned SWM-0W gate.

The model-visible object is deliberately tiny: three role-bearing records, each
containing only ``[normalized coefficient, normalized operand]``.  Evaluator
labels, split cuts, discrete field values, seeds, and opaque identities live in
separate envelopes and must never be passed to an operator.

For a cut ``(s, t)``, coefficient and operand triples are drawn from::

    C_s = {(a, b, a + b + s mod 5)}
    X_t = {(d, e, d + e + t mod 5)}

Train uses every ``(s, t)`` in ``{0, 1, 2}^2``; dev and test use ``(3, 3)``
and ``(4, 4)``.  The full six-tuples are therefore disjoint, while every
role-conditioned unary and pair marginal is exactly identical.  This module
contains no recurrence, LLM, or public target/oracle function.  Each of the
three roles has exactly one incidence: this is a fixed-arity third-order test,
not evidence for multi-member within-role Deep Sets universality or arity
extrapolation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import itertools
import json
import math
import re
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np


FIELD_ORDER = 5
ROLES = ("r0", "r1", "r2")
SPLITS = ("train", "dev", "test")
SPLIT_SHIFT_PAIRS: Mapping[str, tuple[tuple[int, int], ...]] = {
    "train": tuple(itertools.product(range(3), repeat=2)),
    "dev": ((3, 3),),
    "test": ((4, 4),),
}

PROTOCOL_VERSION = "hswm-swm0w-worlds/v1"
MODEL_WORLD_SCHEMA = "hswm-swm0w-model-world/v1"
CASE_SCHEMA = "hswm-swm0w-evaluator-case/v1"
SPLIT_SCHEMA = "hswm-swm0w-split/v1"
AUDIT_SCHEMA = "hswm-swm0w-generator-audit/v1"
BUNDLE_SCHEMA = "hswm-swm0w-bundle/v1"

_NORMALIZED_LEVELS = tuple((value - 2) / 2.0 for value in range(FIELD_ORDER))
_UID_RE = re.compile(r"^swm0w_(?:case|world|inc)_[0-9a-f]{24}$")
_FORBIDDEN_MODEL_KEYS = frozenset(
    {
        "case_uid",
        "coefficient_shift",
        "coefficients",
        "incidence_uid",
        "incidence_uids",
        "label",
        "operand_shift",
        "operands",
        "seed",
        "seed_sha256",
        "split",
        "target",
        "target_hex",
        "world_uid",
        "y",
    }
)


class SWM0WWorldError(ValueError):
    """Raised when an SWM-0W world or audit violates its frozen contract."""


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
            raise SWM0WWorldError("canonical JSON cannot contain non-finite floats")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if hasattr(value, "canonical"):
        return _jsonable(value.canonical())
    raise SWM0WWorldError(f"unsupported canonical value: {type(value)!r}")


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


def _require_sha256(value: str, field: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SWM0WWorldError(f"{field} must be a lowercase SHA-256")


def _require_uid(value: str) -> None:
    if not isinstance(value, str) or not _UID_RE.fullmatch(value):
        raise SWM0WWorldError(f"invalid opaque SWM-0W uid: {value!r}")


def normalize_level(value: int) -> float:
    """Map an F5 value bijectively to ``[-1, -.5, 0, .5, 1]``."""

    if type(value) is not int or not 0 <= value < FIELD_ORDER:
        raise SWM0WWorldError("F5 levels must be integers in [0, 4]")
    return _NORMALIZED_LEVELS[value]


@dataclass(frozen=True, slots=True)
class RoleInputV1:
    """One model-visible incidence: role plus exactly two raw scalars."""

    role: str
    features: tuple[float, float]

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise SWM0WWorldError(f"unsupported role: {self.role!r}")
        if not isinstance(self.features, tuple) or len(self.features) != 2:
            raise SWM0WWorldError("role features must be an immutable pair")
        if any(type(value) is not float or value not in _NORMALIZED_LEVELS for value in self.features):
            raise SWM0WWorldError("role features must be normalized F5 floats")

    @property
    def coefficient(self) -> float:
        return self.features[0]

    @property
    def operand(self) -> float:
        return self.features[1]

    def canonical(self) -> dict[str, Any]:
        return {"features": list(self.features), "role": self.role}


@dataclass(frozen=True, slots=True)
class ModelWorldV1:
    """The complete model input; it contains no identity or evaluator field."""

    incidences: tuple[RoleInputV1, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.incidences, tuple) or len(self.incidences) != len(ROLES):
            raise SWM0WWorldError("a model world requires exactly three incidences")
        if {record.role for record in self.incidences} != set(ROLES):
            raise SWM0WWorldError("a model world requires each registered role once")

    def canonical(self) -> dict[str, Any]:
        return {
            "incidences": [
                record.canonical()
                for record in sorted(self.incidences, key=lambda item: item.role)
            ],
            "schema_version": MODEL_WORLD_SCHEMA,
        }

    @property
    def semantic_sha256(self) -> str:
        return canonical_sha256(self.canonical())

    def feature_matrix(self) -> tuple[tuple[float, float], ...]:
        """Return raw features in the registered role order."""

        by_role = {record.role: record.features for record in self.incidences}
        return tuple(by_role[role] for role in ROLES)


@dataclass(frozen=True, slots=True)
class EvaluatorCaseV1:
    """Evaluator-only envelope.  Models must receive ``world`` and nothing else."""

    case_uid: str
    world_uid: str
    incidence_uids: tuple[tuple[str, str], ...]
    split: str
    coefficient_shift: int
    operand_shift: int
    coefficients: tuple[int, int, int]
    operands: tuple[int, int, int]
    target: float
    world: ModelWorldV1

    def __post_init__(self) -> None:
        _require_uid(self.case_uid)
        _require_uid(self.world_uid)
        if self.case_uid == self.world_uid:
            raise SWM0WWorldError("case and world identities must be distinct")
        if self.split not in SPLITS:
            raise SWM0WWorldError(f"unsupported split: {self.split!r}")
        if (self.coefficient_shift, self.operand_shift) not in SPLIT_SHIFT_PAIRS[self.split]:
            raise SWM0WWorldError("case shifts do not belong to its registered split")
        for triple_name, triple in (
            ("coefficients", self.coefficients),
            ("operands", self.operands),
        ):
            if (
                not isinstance(triple, tuple)
                or len(triple) != len(ROLES)
                or any(type(value) is not int or not 0 <= value < FIELD_ORDER for value in triple)
            ):
                raise SWM0WWorldError(f"{triple_name} must be an immutable F5 triple")
        if self.coefficients[2] != (
            self.coefficients[0] + self.coefficients[1] + self.coefficient_shift
        ) % FIELD_ORDER:
            raise SWM0WWorldError("coefficient triple violates C_s")
        if self.operands[2] != (
            self.operands[0] + self.operands[1] + self.operand_shift
        ) % FIELD_ORDER:
            raise SWM0WWorldError("operand triple violates X_t")
        if not isinstance(self.target, float) or not math.isfinite(self.target) or not -1.0 < self.target < 1.0:
            raise SWM0WWorldError("target must be a finite open-interval tanh value")
        if (
            not isinstance(self.incidence_uids, tuple)
            or {role for role, _ in self.incidence_uids} != set(ROLES)
            or len(self.incidence_uids) != len(ROLES)
        ):
            raise SWM0WWorldError("evaluator incidence identities must cover every role")
        identities = [self.case_uid, self.world_uid]
        for role, uid in self.incidence_uids:
            if role not in ROLES:
                raise SWM0WWorldError("incidence identity has an unknown role")
            _require_uid(uid)
            identities.append(uid)
        if len(set(identities)) != len(identities):
            raise SWM0WWorldError("evaluator identities must be distinct")
        expected = tuple(
            (normalize_level(self.coefficients[index]), normalize_level(self.operands[index]))
            for index in range(len(ROLES))
        )
        if self.world.feature_matrix() != expected:
            raise SWM0WWorldError("model features disagree with evaluator F5 values")

    @property
    def six_tuple(self) -> tuple[int, int, int, int, int, int]:
        return (*self.coefficients, *self.operands)

    def model_visible(self) -> dict[str, Any]:
        return self.world.canonical()

    def canonical(self) -> dict[str, Any]:
        return {
            "case_uid": self.case_uid,
            "coefficient_shift": self.coefficient_shift,
            "coefficients": list(self.coefficients),
            "incidence_uids": [
                {"role": role, "uid": uid}
                for role, uid in sorted(self.incidence_uids)
            ],
            "operand_shift": self.operand_shift,
            "operands": list(self.operands),
            "schema_version": CASE_SCHEMA,
            "split": self.split,
            "target_hex": self.target.hex(),
            "world": self.world.canonical(),
            "world_uid": self.world_uid,
        }

    @property
    def artifact_sha256(self) -> str:
        return canonical_sha256(self.canonical())


@dataclass(frozen=True, slots=True)
class WorldSplitV1:
    split: str
    seed_sha256: str
    cases: tuple[EvaluatorCaseV1, ...]
    split_sha256: str

    def __post_init__(self) -> None:
        if self.split not in SPLITS:
            raise SWM0WWorldError(f"unsupported split: {self.split!r}")
        _require_sha256(self.seed_sha256, "seed_sha256")
        _require_sha256(self.split_sha256, "split_sha256")
        expected_count = len(SPLIT_SHIFT_PAIRS[self.split]) * FIELD_ORDER**4
        if not isinstance(self.cases, tuple) or len(self.cases) != expected_count:
            raise SWM0WWorldError(
                f"{self.split} requires exactly {expected_count} evaluator cases"
            )
        if any(case.split != self.split for case in self.cases):
            raise SWM0WWorldError("split contains a case from another split")
        if len({case.six_tuple for case in self.cases}) != len(self.cases):
            raise SWM0WWorldError("full six-tuples must be unique within a split")
        if self.split_sha256 != canonical_sha256(self.unsigned_canonical()):
            raise SWM0WWorldError("split_sha256 does not authenticate the split")

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "cases": [case.canonical() for case in sorted(self.cases, key=lambda item: item.case_uid)],
            "schema_version": SPLIT_SCHEMA,
            "seed_sha256": self.seed_sha256,
            "split": self.split,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned_canonical(), "split_sha256": self.split_sha256}

    @property
    def semantic_sha256(self) -> str:
        rows = [
            {
                "six_tuple": list(case.six_tuple),
                "target_hex": case.target.hex(),
                "world": case.world.canonical(),
            }
            for case in sorted(self.cases, key=lambda item: item.six_tuple)
        ]
        return canonical_sha256(rows)


@dataclass(frozen=True, slots=True)
class GeneratorAuditV1:
    passed: bool
    checks: tuple[tuple[str, bool], ...]
    unary_marginal_sha256: tuple[tuple[str, str], ...]
    pair_marginal_sha256: tuple[tuple[str, str], ...]
    full_tuple_counts: tuple[tuple[str, int], ...]
    opaque_id_counts: tuple[tuple[str, int], ...]
    anova_variances: tuple[tuple[str, float], ...]
    triple_variance_fraction: float
    counterfactual_min_range_by_role: tuple[tuple[str, float], ...]
    split_target_moments: tuple[tuple[str, tuple[float, float, float]], ...]
    receipt_sha256: str

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "anova_variances": dict(self.anova_variances),
            "checks": dict(self.checks),
            "counterfactual_min_range_by_role": dict(self.counterfactual_min_range_by_role),
            "full_tuple_counts": dict(self.full_tuple_counts),
            "opaque_id_counts": dict(self.opaque_id_counts),
            "pair_marginal_sha256": dict(self.pair_marginal_sha256),
            "passed": self.passed,
            "schema_version": AUDIT_SCHEMA,
            "scope": {
                "arity": 3,
                "incidences_per_role": 1,
                "multi_member_within_role_claim": False,
                "arity_extrapolation_claim": False,
            },
            "split_target_moments": {
                split: {"mean": values[0], "second_moment": values[2], "std": values[1]}
                for split, values in self.split_target_moments
            },
            "triple_variance_fraction": self.triple_variance_fraction,
            "unary_marginal_sha256": dict(self.unary_marginal_sha256),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned_canonical(), "receipt_sha256": self.receipt_sha256}

    def __post_init__(self) -> None:
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        if self.passed != all(passed for _, passed in self.checks):
            raise SWM0WWorldError("audit passed flag disagrees with its checks")
        if self.receipt_sha256 != canonical_sha256(self.unsigned_canonical()):
            raise SWM0WWorldError("receipt_sha256 does not authenticate the audit")


@dataclass(frozen=True, slots=True)
class SWM0WBundleV1:
    splits: tuple[WorldSplitV1, ...]
    audit: GeneratorAuditV1
    bundle_sha256: str

    def __post_init__(self) -> None:
        if tuple(split.split for split in self.splits) != SPLITS:
            raise SWM0WWorldError("bundle splits must be ordered train/dev/test")
        if not self.audit.passed:
            raise SWM0WWorldError("generator audit failed closed")
        _require_sha256(self.bundle_sha256, "bundle_sha256")
        if self.bundle_sha256 != canonical_sha256(self.unsigned_canonical()):
            raise SWM0WWorldError("bundle_sha256 does not authenticate the bundle")

    def for_split(self, split: str) -> WorldSplitV1:
        for item in self.splits:
            if item.split == split:
                return item
        raise SWM0WWorldError(f"unsupported split: {split!r}")

    def unsigned_canonical(self) -> dict[str, Any]:
        return {
            "audit": self.audit.canonical(),
            "schema_version": BUNDLE_SCHEMA,
            "splits": [split.canonical() for split in self.splits],
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned_canonical(), "bundle_sha256": self.bundle_sha256}


def _opaque_uid(
    prefix: str,
    seed_preimage: bytes,
    split: str,
    six_tuple: Sequence[int],
    domain: str,
) -> str:
    payload = b"\x00".join(
        (
            PROTOCOL_VERSION.encode("ascii"),
            seed_preimage,
            split.encode("ascii"),
            bytes(six_tuple),
            domain.encode("ascii"),
        )
    )
    return f"swm0w_{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def _probability_digest(cases: Sequence[EvaluatorCaseV1], arity: int) -> str:
    counter: Counter[str] = Counter()
    for case in cases:
        by_role = {record.role: record.features for record in case.world.incidences}
        for selected_roles in itertools.combinations(ROLES, arity):
            key = canonical_json(
                {
                    "roles": list(selected_roles),
                    "values": [list(by_role[role]) for role in selected_roles],
                }
            )
            counter[key] += 1
    total = len(cases)
    signature = [
        {
            "event": json.loads(key),
            "probability": [
                Fraction(count, total).numerator,
                Fraction(count, total).denominator,
            ],
        }
        for key, count in sorted(counter.items())
    ]
    return canonical_sha256(signature)


def _model_payload_is_clean(world: ModelWorldV1) -> bool:
    payload = world.canonical()

    def walk(value: Any) -> bool:
        if isinstance(value, Mapping):
            if _FORBIDDEN_MODEL_KEYS.intersection(value):
                return False
            return all(walk(item) for item in value.values())
        if isinstance(value, list):
            return all(walk(item) for item in value)
        return not (isinstance(value, str) and _UID_RE.fullmatch(value))

    return (
        walk(payload)
        and set(payload) == {"incidences", "schema_version"}
        and all(set(row) == {"features", "role"} for row in payload["incidences"])
    )


def _target_diagnostics(
    evaluate: Callable[[tuple[int, int, int], tuple[int, int, int]], float],
    splits: Sequence[WorldSplitV1],
) -> tuple[
    tuple[tuple[str, float], ...],
    float,
    tuple[tuple[str, float], ...],
    tuple[tuple[str, tuple[float, float, float]], ...],
]:
    role_records = tuple(itertools.product(range(FIELD_ORDER), repeat=2))
    values = np.empty((25, 25, 25), dtype=np.float64)
    for left_index, left in enumerate(role_records):
        for middle_index, middle in enumerate(role_records):
            for right_index, right in enumerate(role_records):
                values[left_index, middle_index, right_index] = evaluate(
                    (left[0], middle[0], right[0]),
                    (left[1], middle[1], right[1]),
                )

    grand = float(values.mean())
    unary = (
        values.mean(axis=(1, 2)) - grand,
        values.mean(axis=(0, 2)) - grand,
        values.mean(axis=(0, 1)) - grand,
    )
    pair01 = values.mean(axis=2) - grand - unary[0][:, None] - unary[1][None, :]
    pair02 = values.mean(axis=1) - grand - unary[0][:, None] - unary[2][None, :]
    pair12 = values.mean(axis=0) - grand - unary[1][:, None] - unary[2][None, :]
    triple = (
        values
        - grand
        - unary[0][:, None, None]
        - unary[1][None, :, None]
        - unary[2][None, None, :]
        - pair01[:, :, None]
        - pair02[:, None, :]
        - pair12[None, :, :]
    )
    unary_variance = float(sum(np.mean(component**2) for component in unary))
    pair_variance = float(
        np.mean(pair01**2) + np.mean(pair02**2) + np.mean(pair12**2)
    )
    triple_variance = float(np.mean(triple**2))
    total_variance = float(np.var(values))
    anova = (
        ("pair", pair_variance),
        ("total", total_variance),
        ("triple", triple_variance),
        ("unary", unary_variance),
    )
    fraction = triple_variance / total_variance
    counterfactual_ranges = tuple(
        (role, float(np.ptp(values, axis=index).min()))
        for index, role in enumerate(ROLES)
    )
    moments = tuple(
        (
            split.split,
            (
                float(np.mean([case.target for case in split.cases])),
                float(np.std([case.target for case in split.cases])),
                float(np.mean([case.target**2 for case in split.cases])),
            ),
        )
        for split in splits
    )
    return anova, fraction, counterfactual_ranges, moments


def _build_audit(
    splits: Sequence[WorldSplitV1],
    evaluate: Callable[[tuple[int, int, int], tuple[int, int, int]], float],
) -> GeneratorAuditV1:
    full_sets = {
        split.split: {case.six_tuple for case in split.cases} for split in splits
    }
    uid_sets = {
        split.split: {
            uid
            for case in split.cases
            for uid in (
                case.case_uid,
                case.world_uid,
                *(uid for _, uid in case.incidence_uids),
            )
        }
        for split in splits
    }
    unary = tuple(
        (split.split, _probability_digest(split.cases, 1)) for split in splits
    )
    pair = tuple(
        (split.split, _probability_digest(split.cases, 2)) for split in splits
    )
    anova, triple_fraction, counterfactual_ranges, moments = _target_diagnostics(
        evaluate, splits
    )
    moment_values = dict(moments)
    standard_deviations = [values[1] for values in moment_values.values()]
    second_moments = [values[2] for values in moment_values.values()]
    pairwise_split_names = tuple(itertools.combinations(SPLITS, 2))
    checks = (
        (
            "full_six_tuples_split_disjoint",
            all(full_sets[left].isdisjoint(full_sets[right]) for left, right in pairwise_split_names),
        ),
        (
            "opaque_ids_split_disjoint",
            all(uid_sets[left].isdisjoint(uid_sets[right]) for left, right in pairwise_split_names),
        ),
        (
            "opaque_ids_globally_unique",
            sum(len(values) for values in uid_sets.values())
            == len(set().union(*uid_sets.values())),
        ),
        ("unary_marginals_exactly_matched", len({digest for _, digest in unary}) == 1),
        ("role_pair_marginals_exactly_matched", len({digest for _, digest in pair}) == 1),
        (
            "model_payload_evaluator_fields_absent",
            all(_model_payload_is_clean(case.world) for split in splits for case in split.cases),
        ),
        (
            "model_semantics_split_disjoint",
            all(
                {case.world.semantic_sha256 for case in next(item for item in splits if item.split == left).cases}.isdisjoint(
                    {case.world.semantic_sha256 for case in next(item for item in splits if item.split == right).cases}
                )
                for left, right in pairwise_split_names
            ),
        ),
        ("tanh_anova_orthogonal", abs(dict(anova)["total"] - sum(dict(anova)[name] for name in ("unary", "pair", "triple"))) < 1.0e-12),
        ("triple_variance_45_to_65_percent", 0.45 <= triple_fraction <= 0.65),
        ("every_role_counterfactually_matters", all(value > 1.0e-6 for _, value in counterfactual_ranges)),
        ("split_target_mean_bounded", all(abs(values[0]) <= 0.075 for values in moment_values.values())),
        ("split_target_std_bounded", all(0.32 <= value <= 0.42 for value in standard_deviations)),
        ("split_target_std_drift_bounded", max(standard_deviations) - min(standard_deviations) <= 0.03),
        ("split_target_second_moment_drift_bounded", max(second_moments) - min(second_moments) <= 0.01),
    )
    unsigned = {
        "anova_variances": dict(anova),
        "checks": dict(checks),
        "counterfactual_min_range_by_role": dict(counterfactual_ranges),
        "full_tuple_counts": {split: len(values) for split, values in full_sets.items()},
        "opaque_id_counts": {split: len(values) for split, values in uid_sets.items()},
        "pair_marginal_sha256": dict(pair),
        "passed": all(passed for _, passed in checks),
        "schema_version": AUDIT_SCHEMA,
        "scope": {
            "arity": 3,
            "incidences_per_role": 1,
            "multi_member_within_role_claim": False,
            "arity_extrapolation_claim": False,
        },
        "split_target_moments": {
            split: {"mean": values[0], "second_moment": values[2], "std": values[1]}
            for split, values in moments
        },
        "triple_variance_fraction": triple_fraction,
        "unary_marginal_sha256": dict(unary),
    }
    return GeneratorAuditV1(
        passed=all(passed for _, passed in checks),
        checks=checks,
        unary_marginal_sha256=unary,
        pair_marginal_sha256=pair,
        full_tuple_counts=tuple((split, len(full_sets[split])) for split in SPLITS),
        opaque_id_counts=tuple((split, len(uid_sets[split])) for split in SPLITS),
        anova_variances=anova,
        triple_variance_fraction=triple_fraction,
        counterfactual_min_range_by_role=counterfactual_ranges,
        split_target_moments=moments,
        receipt_sha256=canonical_sha256(unsigned),
    )


def generate_bundle(*, seed_preimage: bytes) -> SWM0WBundleV1:
    """Generate the complete train/dev/test cut and its fail-closed audit.

    The evaluator below is local to this function: no importable target function
    or coefficient table is exposed to an operator.  This is an API separation,
    not cryptographic secrecy; labels remain available on evaluator envelopes.
    """

    if not isinstance(seed_preimage, bytes) or len(seed_preimage) < 16:
        raise SWM0WWorldError("seed_preimage must contain at least 128 bits")

    def evaluate_hidden(
        coefficients: tuple[int, int, int], operands: tuple[int, int, int]
    ) -> float:
        c = tuple(normalize_level(value) for value in coefficients)
        x = tuple(normalize_level(value) for value in operands)
        local = (
            0.65 * c[0] + 0.35 * x[0] + 0.25 * c[0] * x[0],
            0.55 * c[1] - 0.45 * x[1] + 0.20 * c[1] * x[1],
            -0.40 * c[2] + 0.60 * x[2] - 0.15 * c[2] * x[2],
        )
        unary = 0.30 * (
            0.83 * local[0] + 1.07 * local[1] + 1.31 * local[2]
        )
        pair = 0.20 * (
            0.91 * local[0] * local[1]
            + 1.17 * local[0] * local[2]
            + 0.73 * local[1] * local[2]
        )
        triple = 3.00 * local[0] * local[1] * local[2]
        return math.tanh(unary + pair + triple)

    seed_sha256 = hashlib.sha256(seed_preimage).hexdigest()
    built_splits: list[WorldSplitV1] = []
    incidence_orders = tuple(itertools.permutations(range(len(ROLES))))
    for split in SPLITS:
        cases: list[EvaluatorCaseV1] = []
        for coefficient_shift, operand_shift in SPLIT_SHIFT_PAIRS[split]:
            for a, b, d, e in itertools.product(range(FIELD_ORDER), repeat=4):
                coefficients = (a, b, (a + b + coefficient_shift) % FIELD_ORDER)
                operands = (d, e, (d + e + operand_shift) % FIELD_ORDER)
                six_tuple = (*coefficients, *operands)
                case_uid = _opaque_uid("case", seed_preimage, split, six_tuple, "case")
                world_uid = _opaque_uid("world", seed_preimage, split, six_tuple, "world")
                records = tuple(
                    RoleInputV1(
                        role=role,
                        features=(normalize_level(coefficients[index]), normalize_level(operands[index])),
                    )
                    for index, role in enumerate(ROLES)
                )
                order_digest = hashlib.sha256(
                    (case_uid + "|incidence-order").encode("ascii")
                ).digest()
                order = incidence_orders[int.from_bytes(order_digest[:2], "big") % len(incidence_orders)]
                world = ModelWorldV1(tuple(records[index] for index in order))
                incidence_uids = tuple(
                    (
                        role,
                        _opaque_uid("inc", seed_preimage, split, six_tuple, f"incidence:{role}"),
                    )
                    for role in ROLES
                )
                cases.append(
                    EvaluatorCaseV1(
                        case_uid=case_uid,
                        world_uid=world_uid,
                        incidence_uids=incidence_uids,
                        split=split,
                        coefficient_shift=coefficient_shift,
                        operand_shift=operand_shift,
                        coefficients=coefficients,
                        operands=operands,
                        target=evaluate_hidden(coefficients, operands),
                        world=world,
                    )
                )
        cases.sort(
            key=lambda case: hashlib.sha256(
                seed_preimage + split.encode("ascii") + case.case_uid.encode("ascii")
            ).digest()
        )
        unsigned = {
            "cases": [case.canonical() for case in sorted(cases, key=lambda item: item.case_uid)],
            "schema_version": SPLIT_SCHEMA,
            "seed_sha256": seed_sha256,
            "split": split,
        }
        built_splits.append(
            WorldSplitV1(
                split=split,
                seed_sha256=seed_sha256,
                cases=tuple(cases),
                split_sha256=canonical_sha256(unsigned),
            )
        )

    splits = tuple(built_splits)
    audit = _build_audit(splits, evaluate_hidden)
    if not audit.passed:
        failures = [name for name, passed in audit.checks if not passed]
        raise SWM0WWorldError(f"SWM-0W generator audit failed: {failures}")
    unsigned_bundle = {
        "audit": audit.canonical(),
        "schema_version": BUNDLE_SCHEMA,
        "splits": [split.canonical() for split in splits],
    }
    return SWM0WBundleV1(
        splits=splits,
        audit=audit,
        bundle_sha256=canonical_sha256(unsigned_bundle),
    )


def cases_from_split(
    bundle: SWM0WBundleV1, split: str
) -> tuple[EvaluatorCaseV1, ...]:
    """Return evaluator envelopes; callers must pass only ``case.world`` to models."""

    return bundle.for_split(split).cases


__all__ = [
    "AUDIT_SCHEMA",
    "BUNDLE_SCHEMA",
    "CASE_SCHEMA",
    "FIELD_ORDER",
    "MODEL_WORLD_SCHEMA",
    "PROTOCOL_VERSION",
    "ROLES",
    "SPLITS",
    "SPLIT_SCHEMA",
    "SPLIT_SHIFT_PAIRS",
    "EvaluatorCaseV1",
    "GeneratorAuditV1",
    "ModelWorldV1",
    "RoleInputV1",
    "SWM0WBundleV1",
    "SWM0WWorldError",
    "WorldSplitV1",
    "canonical_json",
    "canonical_sha256",
    "cases_from_split",
    "generate_bundle",
    "normalize_level",
]
