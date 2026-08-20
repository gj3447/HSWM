"""Learned fixed-arity third-order scalar compatibility for SWM-0W development.

Only the three model-visible role incidences and their two scalar features enter
the operator.  Labels are consumed by the training/evaluation boundary only.
There is no target oracle, field formula, lookup table, or identifier feature in
this module.

The evaluator boundary accepts the legacy and streamed task envelopes by exact
nominal type, then strips each to an exact ``ModelWorldV1`` before compilation.
Streamed task/source receipts are provenance only and never seed or enter the
numeric path.  V2 initialization separately seeds each named parameter tensor,
making common tensors bit-equal across the nested additive/pair/triple arms.

The target is deliberately narrow: three singleton roles, role-specific learned
``tanh`` encoders, and learned unary, pair-Hadamard, and triple-Hadamard heads.
Its scalar readout is a diagnostic precursor, not canonical HSWM's
recipient-conditioned set-to-set ``W`` or member-specific semantic transport.
It is also not multi-member-within-role DeepSets universality, recurrence,
learned topology, outcome-bound semantic-weight learning, or a novelty claim.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import json
import math
from types import MappingProxyType
from typing import Any, Mapping, Sequence, TypeAlias

import numpy as np

from hswm.experiments.swm0w_worlds import (
    CASE_SCHEMA as LEGACY_CASE_SCHEMA,
    ROLES,
    EvaluatorCaseV1,
    ModelWorldV1,
    RoleInputV1,
    cases_from_split,
)
from hswm.experiments.swm0w_task_family import (
    CASE_SCHEMA as TASK_CASE_SCHEMA,
    TaskEvaluatorCaseV1,
)


OPERATOR_VERSION = "hswm-swm0w-learned-operator/v2"
OPTIMIZER_VERSION = "hswm-manual-adam/v2"
OPTIMIZATION_RECEIPT_VERSION = "hswm-swm0w-optimization-receipt/v2"
EVALUATOR_BINDING_VERSION = "hswm-swm0w-evaluator-binding/v2"
SUITE_COMPARISON_VERSION = "hswm-swm0w-suite-comparison/v2"
HEAD_REMOVAL_RECEIPT_VERSION = "hswm-swm0w-head-removal/v2"
# V2 deliberately replaces the arm-coupled v1 stream: each named tensor is
# seeded independently so nested arms share bit-equal common parameters.
# Receipt/state schema changes must never silently alter either numeric domain.
INITIALIZATION_DOMAIN = "hswm-swm0w-named-parameter-initialization/v2"
TRAINING_ORDER_DOMAIN = "hswm-swm0w-manual-adam-order/v2"
DEFAULT_WIDTH = 16
DEFAULT_ROLE_TRIPLE_PARAMETER_COUNT = 257
PAIR_INDEX = ((0, 1), (0, 2), (1, 2))

EvaluatorEnvelopeV1: TypeAlias = EvaluatorCaseV1 | TaskEvaluatorCaseV1


class SWM0WOperatorError(ValueError):
    """Raised when the learned-operator contract is violated."""


class SWM0WArm(str, Enum):
    ROLE_TRIPLE = "ROLE_TRIPLE"
    TYPED_STAR_TRIPLE = "TYPED_STAR_TRIPLE"
    LOWER_ORDER_PAIR = "LOWER_ORDER_PAIR"
    ADDITIVE = "ADDITIVE"
    ROLELESS = "ROLELESS"
    FLAT_MLP = "FLAT_MLP"
    ROLE_AWARE_DEEPSETS = "ROLE_AWARE_DEEPSETS"


ALL_ARMS = tuple(SWM0WArm)
COMPLETE_CONTROLS = (
    SWM0WArm.FLAT_MLP,
    SWM0WArm.ROLE_AWARE_DEEPSETS,
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if hasattr(value, "canonical"):
        return _jsonable(value.canonical())
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SWM0WOperatorError("canonical JSON requires finite floats")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise SWM0WOperatorError(f"unsupported canonical value: {type(value)!r}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_sha256(value: str, field: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise SWM0WOperatorError(f"{field} must be a lowercase SHA-256")


def _float_array_receipt(value: np.ndarray) -> list[Any]:
    array = np.asarray(value, dtype=np.float64)
    if array.ndim == 0:
        return [float(array).hex()]
    return _jsonable(
        np.vectorize(lambda item: float(item).hex(), otypes=[object])(array)
    )


def _immutable_float64(value: Any) -> np.ndarray:
    """Own immutable bytes so callers cannot re-enable NumPy writes."""

    array = np.ascontiguousarray(value, dtype=np.float64)
    return np.frombuffer(array.tobytes(), dtype=np.float64).reshape(array.shape)


def _coerce_arm(arm: SWM0WArm | str) -> SWM0WArm:
    try:
        return arm if isinstance(arm, SWM0WArm) else SWM0WArm(arm)
    except (TypeError, ValueError) as exc:
        raise SWM0WOperatorError(f"unsupported SWM-0W arm: {arm!r}") from exc


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    width: int = DEFAULT_WIDTH
    seed: int = 0
    epochs: int = 200
    batch_size: int = 256
    learning_rate: float = 0.01
    beta1: float = 0.9
    beta2: float = 0.999
    epsilon: float = 1.0e-8
    gradient_clip: float = 5.0
    patience: int = 25
    min_delta: float = 1.0e-9

    def __post_init__(self) -> None:
        if type(self.width) is not int or self.width <= 0:
            raise SWM0WOperatorError("width must be a positive integer")
        if type(self.seed) is not int or self.seed < 0:
            raise SWM0WOperatorError("seed must be a non-negative integer")
        for name in ("epochs", "batch_size", "patience"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise SWM0WOperatorError(f"{name} must be a positive integer")
        for name in (
            "learning_rate",
            "beta1",
            "beta2",
            "epsilon",
            "gradient_clip",
            "min_delta",
        ):
            value = getattr(self, name)
            if type(value) is not float or not math.isfinite(value):
                raise SWM0WOperatorError(f"{name} must be an exact finite float")
        for name in ("learning_rate", "epsilon", "gradient_clip"):
            if getattr(self, name) <= 0.0:
                raise SWM0WOperatorError(f"{name} must be finite and positive")
        if not 0.0 < self.beta1 < 1.0 or not 0.0 < self.beta2 < 1.0:
            raise SWM0WOperatorError("Adam beta values must lie in (0, 1)")
        if self.min_delta < 0.0:
            raise SWM0WOperatorError("min_delta must be finite and non-negative")

    def canonical(self) -> dict[str, Any]:
        return {
            "batch_size": self.batch_size,
            "beta1": self.beta1,
            "beta2": self.beta2,
            "epochs": self.epochs,
            "epsilon": self.epsilon,
            "gradient_clip": self.gradient_clip,
            "learning_rate": self.learning_rate,
            "min_delta": self.min_delta,
            "patience": self.patience,
            "seed": self.seed,
            "width": self.width,
        }


def _validate_matrix(value: Any) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.float64)
    expected = (len(ROLES), 2)
    if matrix.shape != expected or not np.isfinite(matrix).all():
        raise SWM0WOperatorError(
            f"world feature matrix must be finite with shape {expected!r}"
        )
    return matrix


def native_role_input(world: ModelWorldV1) -> np.ndarray:
    """Use the world's canonical role-ordered public compiler."""

    if type(world) is not ModelWorldV1:
        raise SWM0WOperatorError("operator input must be exact ModelWorldV1")
    result = _validate_matrix(world.feature_matrix()).copy()
    result.setflags(write=False)
    return result


def compile_typed_star_input(world: ModelWorldV1) -> np.ndarray:
    """Independently compile role leaves without calling ``feature_matrix``."""

    if type(world) is not ModelWorldV1:
        raise SWM0WOperatorError("typed-star input must be exact ModelWorldV1")
    by_role: dict[str, tuple[float, float]] = {}
    for incidence in world.incidences:
        if type(incidence) is not RoleInputV1:
            raise SWM0WOperatorError("typed-star incidence must be exact RoleInputV1")
        if incidence.role in by_role:
            raise SWM0WOperatorError("typed-star compiler found a repeated role")
        features = tuple(float(value) for value in incidence.features)
        if len(features) != 2 or not all(math.isfinite(value) for value in features):
            raise SWM0WOperatorError("role incidence requires two finite scalars")
        by_role[incidence.role] = features
    if set(by_role) != set(ROLES):
        raise SWM0WOperatorError("typed-star compiler requires every registered role")
    result = _validate_matrix([by_role[role] for role in ROLES]).copy()
    result.setflags(write=False)
    return result


def assert_typed_star_parity(world: ModelWorldV1) -> str:
    native = native_role_input(world)
    star = compile_typed_star_input(world)
    if not np.array_equal(native, star):
        raise SWM0WOperatorError("native and independently compiled star inputs differ")
    return canonical_sha256(
        {
            "native": _float_array_receipt(native),
            "star": _float_array_receipt(star),
        }
    )


@dataclass(frozen=True, slots=True)
class _EvaluatorViewV1:
    """Validated evaluator boundary; never pass this object into a model."""

    world: ModelWorldV1
    target: float
    split: str
    case_schema: str
    task_uid: str | None
    source_receipt_sha256: str | None

    def __post_init__(self) -> None:
        if type(self.world) is not ModelWorldV1:
            raise SWM0WOperatorError(
                "evaluator world must be exact ModelWorldV1"
            )
        if (
            type(self.target) is not float
            or not math.isfinite(self.target)
            or not -1.0 < self.target < 1.0
        ):
            raise SWM0WOperatorError(
                "evaluator target must be a finite open-interval tanh value"
            )
        if self.case_schema not in {LEGACY_CASE_SCHEMA, TASK_CASE_SCHEMA}:
            raise SWM0WOperatorError("unsupported evaluator case schema")
        task_case = self.case_schema == TASK_CASE_SCHEMA
        if task_case != (self.task_uid is not None):
            raise SWM0WOperatorError(
                "streamed evaluator schema/task identity mismatch"
            )
        if task_case != (self.source_receipt_sha256 is not None):
            raise SWM0WOperatorError(
                "streamed evaluator schema/source receipt mismatch"
            )
        if self.source_receipt_sha256 is not None:
            _require_sha256(
                self.source_receipt_sha256, "source_receipt_sha256"
            )


def _evaluator_view(
    case: EvaluatorEnvelopeV1,
    *,
    expected_split: str | None,
) -> _EvaluatorViewV1:
    if type(case) is EvaluatorCaseV1:
        case_schema = LEGACY_CASE_SCHEMA
        task_uid = None
        source_receipt_sha256 = None
    elif type(case) is TaskEvaluatorCaseV1:
        case_schema = TASK_CASE_SCHEMA
        task_uid = case.task_uid
        source_receipt_sha256 = case.receipt_sha256
    else:
        prefix = "evaluator" if expected_split is None else expected_split
        raise SWM0WOperatorError(
            f"{prefix} input requires only supported evaluator envelopes"
        )
    if expected_split is not None and case.split != expected_split:
        raise SWM0WOperatorError(
            f"{expected_split} input requires only {expected_split} evaluator envelopes"
        )
    return _EvaluatorViewV1(
        world=case.world,
        target=case.target,
        split=case.split,
        case_schema=case_schema,
        task_uid=task_uid,
        source_receipt_sha256=source_receipt_sha256,
    )


def _validated_evaluator_views(
    cases: Sequence[EvaluatorEnvelopeV1],
    *,
    expected_split: str | None,
) -> tuple[_EvaluatorViewV1, ...]:
    if len(cases) == 0:
        name = "evaluator" if expected_split is None else expected_split
        raise SWM0WOperatorError(f"{name} split cannot be empty")
    views = tuple(
        _evaluator_view(case, expected_split=expected_split) for case in cases
    )
    if len({view.case_schema for view in views}) != 1:
        raise SWM0WOperatorError(
            "evaluator input cannot mix evaluator case schemas"
        )
    if len({view.task_uid for view in views}) != 1:
        raise SWM0WOperatorError(
            "evaluator input cannot mix streamed task identities"
        )
    if expected_split is None and len({view.split for view in views}) != 1:
        raise SWM0WOperatorError("evaluation requires exactly one declared split")
    return views


def _source_receipts_sha256(
    views: Sequence[_EvaluatorViewV1],
) -> str | None:
    receipts = tuple(
        view.source_receipt_sha256
        for view in views
        if view.source_receipt_sha256 is not None
    )
    if not receipts:
        return None
    if len(receipts) != len(views):
        raise SWM0WOperatorError("partial evaluator source receipts are forbidden")
    return canonical_sha256(sorted(receipts))


def _evaluator_binding_sha256(
    phases: Mapping[str, Sequence[_EvaluatorViewV1]],
) -> str:
    if not phases or any(len(views) == 0 for views in phases.values()):
        raise SWM0WOperatorError("evaluator binding requires non-empty phases")
    all_views = tuple(view for views in phases.values() for view in views)
    schemas = {view.case_schema for view in all_views}
    task_uids = {view.task_uid for view in all_views}
    if len(schemas) != 1 or len(task_uids) != 1:
        raise SWM0WOperatorError(
            "evaluator phases must share one case schema and task identity"
        )
    return canonical_sha256(
        {
            "case_schema": next(iter(schemas)),
            "phases": {
                name: {
                    "case_count": len(views),
                    "declared_splits": sorted({view.split for view in views}),
                    "source_receipts_sha256": _source_receipts_sha256(views),
                }
                for name, views in sorted(phases.items())
            },
            "schema_version": EVALUATOR_BINDING_VERSION,
            "task_uid": next(iter(task_uids)),
        }
    )


def _typed_star_parity_receipt(
    views: Sequence[_EvaluatorViewV1],
) -> str:
    rows = []
    for view in views:
        rows.append(
            (view.world.semantic_sha256, assert_typed_star_parity(view.world))
        )
    return canonical_sha256(sorted(rows))


@dataclass(frozen=True, slots=True)
class TrainOnlyNormalizer:
    mean: np.ndarray
    scale: np.ndarray
    train_case_count: int

    def __post_init__(self) -> None:
        mean = _immutable_float64(_validate_matrix(self.mean))
        scale = _immutable_float64(_validate_matrix(self.scale))
        if np.any(scale <= 0.0):
            raise SWM0WOperatorError("normalizer scale must be positive")
        if type(self.train_case_count) is not int or self.train_case_count <= 0:
            raise SWM0WOperatorError("normalizer requires positive train_case_count")
        object.__setattr__(self, "mean", mean)
        object.__setattr__(self, "scale", scale)

    @classmethod
    def fit(cls, train: np.ndarray) -> "TrainOnlyNormalizer":
        values = np.asarray(train, dtype=np.float64)
        if values.ndim != 3 or values.shape[1:] != (len(ROLES), 2):
            raise SWM0WOperatorError("normalizer requires [case, role, feature] input")
        mean = values.mean(axis=0)
        scale = values.std(axis=0)
        scale = np.where(scale < 1.0e-12, 1.0, scale)
        return cls(mean=mean, scale=scale, train_case_count=len(values))

    @property
    def state_sha256(self) -> str:
        return canonical_sha256(self.canonical())

    def transform(self, value: np.ndarray) -> np.ndarray:
        values = np.asarray(value, dtype=np.float64)
        if values.shape[-2:] != (len(ROLES), 2):
            raise SWM0WOperatorError("normalizer input has the wrong role-feature shape")
        result = (values - self.mean) / self.scale
        if not np.isfinite(result).all():
            raise SWM0WOperatorError("normalization produced a non-finite value")
        return result

    def canonical(self) -> dict[str, Any]:
        return {
            "mean_hex": _float_array_receipt(self.mean),
            "scale_hex": _float_array_receipt(self.scale),
            "scope": "TRAIN_SPLIT_ONLY_PER_ROLE_PER_FEATURE",
            "train_case_count": self.train_case_count,
        }


def _compiler_for_arm(arm: SWM0WArm):
    return (
        compile_typed_star_input
        if arm is SWM0WArm.TYPED_STAR_TRIPLE
        else native_role_input
    )


def _dataset(
    views: Sequence[_EvaluatorViewV1], arm: SWM0WArm
) -> tuple[np.ndarray, np.ndarray]:
    if not views:
        raise SWM0WOperatorError("a dataset must contain at least one case")
    compiler = _compiler_for_arm(arm)
    inputs: list[np.ndarray] = []
    labels: list[float] = []
    # Optimizer trajectories must depend on semantic examples, not caller order
    # or evaluator-only opaque identities.
    ordered_views = sorted(
        views,
        key=lambda view: (view.world.semantic_sha256, view.target.hex()),
    )
    for view in ordered_views:
        # This is the sole evaluator-to-model crossing: only the exact world is
        # handed to a compiler.  The view, target, split, task, and receipts are
        # never arguments to the compiler, normalizer, or learned forward pass.
        inputs.append(compiler(view.world))
        labels.append(view.target)
    return np.stack(inputs), np.asarray(labels, dtype=np.float64)


def _dataset_sha256(views: Sequence[_EvaluatorViewV1]) -> str:
    rows = sorted(
        (view.world.semantic_sha256, view.target.hex()) for view in views
    )
    return canonical_sha256(rows)


def _validate_training_split_contract(
    train_cases: Sequence[EvaluatorEnvelopeV1],
    dev_cases: Sequence[EvaluatorEnvelopeV1],
) -> tuple[
    tuple[_EvaluatorViewV1, ...],
    tuple[_EvaluatorViewV1, ...],
    str,
]:
    train_views = _validated_evaluator_views(
        train_cases, expected_split="train"
    )
    dev_views = _validated_evaluator_views(dev_cases, expected_split="dev")
    if train_views[0].case_schema != dev_views[0].case_schema:
        raise SWM0WOperatorError(
            "train and dev must use the same evaluator case schema"
        )
    if train_views[0].task_uid != dev_views[0].task_uid:
        raise SWM0WOperatorError(
            "train and dev must use the same streamed task identity"
        )
    train_worlds = {view.world.semantic_sha256 for view in train_views}
    dev_worlds = {view.world.semantic_sha256 for view in dev_views}
    if not train_worlds.isdisjoint(dev_worlds):
        raise SWM0WOperatorError("train and dev semantic worlds must be disjoint")
    return (
        train_views,
        dev_views,
        _evaluator_binding_sha256(
            {"dev": dev_views, "train": train_views}
        ),
    )


def _copy_parameters(parameters: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {
        name: np.asarray(value, dtype=np.float64).copy()
        for name, value in parameters.items()
    }


def _parameter_receipt(parameters: Mapping[str, np.ndarray]) -> dict[str, Any]:
    return {
        name: {
            "shape": list(value.shape),
            "values_hex": _float_array_receipt(value),
        }
        for name, value in sorted(parameters.items())
    }


def _initial_parameters(
    arm: SWM0WArm, width: int, seed: int
) -> dict[str, np.ndarray]:
    if type(seed) is not int or seed < 0:
        raise SWM0WOperatorError(
            "parameter initialization seed must be a non-negative integer"
        )

    def random(
        name: str, shape: tuple[int, ...], fan_in: int
    ) -> np.ndarray:
        seed_material = canonical_sha256(
            [INITIALIZATION_DOMAIN, seed, name, list(shape)]
        )
        rng = np.random.Generator(
            np.random.PCG64(int(seed_material[:16], 16))
        )
        limit = math.sqrt(6.0 / max(1, fan_in + width))
        return rng.uniform(-limit, limit, size=shape).astype(np.float64)

    if arm in {
        SWM0WArm.ROLE_TRIPLE,
        SWM0WArm.TYPED_STAR_TRIPLE,
        SWM0WArm.LOWER_ORDER_PAIR,
        SWM0WArm.ADDITIVE,
    }:
        params = {
            "encoder_w": random("encoder_w", (len(ROLES), 2, width), 2),
            "encoder_b": np.zeros((len(ROLES), width), dtype=np.float64),
            "unary_w": random("unary_w", (len(ROLES), width), width),
            "out_b": np.zeros(1, dtype=np.float64),
        }
        if arm is not SWM0WArm.ADDITIVE:
            params["pair_w"] = random(
                "pair_w", (len(PAIR_INDEX), width), width
            )
        if arm in {SWM0WArm.ROLE_TRIPLE, SWM0WArm.TYPED_STAR_TRIPLE}:
            params["triple_w"] = random("triple_w", (width,), width)
        return params
    if arm is SWM0WArm.ROLELESS:
        return {
            "encoder_w": random("encoder_w", (2, width), 2),
            "encoder_b": np.zeros(width, dtype=np.float64),
            "out_w": random("out_w", (width,), width),
            "out_b": np.zeros(1, dtype=np.float64),
        }
    if arm is SWM0WArm.FLAT_MLP:
        return {
            "hidden1_w": random(
                "hidden1_w", (len(ROLES) * 2, width), len(ROLES) * 2
            ),
            "hidden1_b": np.zeros(width, dtype=np.float64),
            "hidden2_w": random("hidden2_w", (width, width), width),
            "hidden2_b": np.zeros(width, dtype=np.float64),
            "out_w": random("out_w", (width,), width),
            "out_b": np.zeros(1, dtype=np.float64),
        }
    if arm is SWM0WArm.ROLE_AWARE_DEEPSETS:
        return {
            "phi_w": random(
                "phi_w", (2 + len(ROLES), width), 2 + len(ROLES)
            ),
            "phi_b": np.zeros(width, dtype=np.float64),
            "rho_w": random("rho_w", (width, width), width),
            "rho_b": np.zeros(width, dtype=np.float64),
            "out_w": random("out_w", (width,), width),
            "out_b": np.zeros(1, dtype=np.float64),
        }
    raise AssertionError(f"unhandled arm: {arm}")


def _expected_parameter_shapes(
    arm: SWM0WArm, width: int
) -> dict[str, tuple[int, ...]]:
    if arm in {
        SWM0WArm.ROLE_TRIPLE,
        SWM0WArm.TYPED_STAR_TRIPLE,
        SWM0WArm.LOWER_ORDER_PAIR,
        SWM0WArm.ADDITIVE,
    }:
        shapes = {
            "encoder_w": (len(ROLES), 2, width),
            "encoder_b": (len(ROLES), width),
            "unary_w": (len(ROLES), width),
            "out_b": (1,),
        }
        if arm is not SWM0WArm.ADDITIVE:
            shapes["pair_w"] = (len(PAIR_INDEX), width)
        if arm in {SWM0WArm.ROLE_TRIPLE, SWM0WArm.TYPED_STAR_TRIPLE}:
            shapes["triple_w"] = (width,)
        return shapes
    if arm is SWM0WArm.ROLELESS:
        return {
            "encoder_w": (2, width),
            "encoder_b": (width,),
            "out_w": (width,),
            "out_b": (1,),
        }
    if arm is SWM0WArm.FLAT_MLP:
        return {
            "hidden1_w": (len(ROLES) * 2, width),
            "hidden1_b": (width,),
            "hidden2_w": (width, width),
            "hidden2_b": (width,),
            "out_w": (width,),
            "out_b": (1,),
        }
    if arm is SWM0WArm.ROLE_AWARE_DEEPSETS:
        return {
            "phi_w": (2 + len(ROLES), width),
            "phi_b": (width,),
            "rho_w": (width, width),
            "rho_b": (width,),
            "out_w": (width,),
            "out_b": (1,),
        }
    raise AssertionError(f"unhandled arm: {arm}")


def _forward(
    arm: SWM0WArm,
    parameters: Mapping[str, np.ndarray],
    inputs: np.ndarray,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    x = np.asarray(inputs, dtype=np.float64)
    if arm in {
        SWM0WArm.ROLE_TRIPLE,
        SWM0WArm.TYPED_STAR_TRIPLE,
        SWM0WArm.LOWER_ORDER_PAIR,
        SWM0WArm.ADDITIVE,
    }:
        pre = np.einsum("nrf,rfh->nrh", x, parameters["encoder_w"])
        pre = pre + parameters["encoder_b"][None, :, :]
        hidden = np.tanh(pre)
        prediction = np.einsum("nrh,rh->n", hidden, parameters["unary_w"])
        pair_products: list[np.ndarray] = []
        if "pair_w" in parameters:
            for pair_position, (left, right) in enumerate(PAIR_INDEX):
                product = hidden[:, left, :] * hidden[:, right, :]
                pair_products.append(product)
                prediction += product @ parameters["pair_w"][pair_position]
        if "triple_w" in parameters:
            triple = hidden[:, 0, :] * hidden[:, 1, :] * hidden[:, 2, :]
            prediction += triple @ parameters["triple_w"]
        prediction += float(parameters["out_b"][0])
        cache = {
            "hidden": hidden,
            "pair_products": np.stack(pair_products, axis=1)
            if pair_products
            else np.empty((len(x), 0, hidden.shape[-1])),
            "x": x,
        }
        if "triple_w" in parameters:
            cache["triple"] = triple
        return prediction, cache
    if arm is SWM0WArm.ROLELESS:
        hidden = np.tanh(
            np.einsum("nrf,fh->nrh", x, parameters["encoder_w"])
            + parameters["encoder_b"]
        )
        pooled = hidden.mean(axis=1)
        prediction = pooled @ parameters["out_w"] + parameters["out_b"][0]
        return prediction, {"hidden": hidden, "pooled": pooled, "x": x}
    if arm is SWM0WArm.FLAT_MLP:
        flat = x.reshape(len(x), -1)
        hidden1 = np.tanh(flat @ parameters["hidden1_w"] + parameters["hidden1_b"])
        hidden2 = np.tanh(hidden1 @ parameters["hidden2_w"] + parameters["hidden2_b"])
        prediction = hidden2 @ parameters["out_w"] + parameters["out_b"][0]
        return prediction, {"flat": flat, "hidden1": hidden1, "hidden2": hidden2}
    if arm is SWM0WArm.ROLE_AWARE_DEEPSETS:
        one_hot = np.eye(len(ROLES), dtype=np.float64)[None, :, :]
        one_hot = np.broadcast_to(one_hot, (len(x), len(ROLES), len(ROLES)))
        tokens = np.concatenate((x, one_hot), axis=2)
        phi = np.tanh(np.einsum("nrf,fh->nrh", tokens, parameters["phi_w"]) + parameters["phi_b"])
        pooled = phi.sum(axis=1)
        rho = np.tanh(pooled @ parameters["rho_w"] + parameters["rho_b"])
        prediction = rho @ parameters["out_w"] + parameters["out_b"][0]
        return prediction, {"phi": phi, "pooled": pooled, "rho": rho, "tokens": tokens}
    raise AssertionError(f"unhandled arm: {arm}")


def _loss_and_gradients(
    arm: SWM0WArm,
    parameters: Mapping[str, np.ndarray],
    inputs: np.ndarray,
    targets: np.ndarray,
) -> tuple[float, dict[str, np.ndarray]]:
    prediction, cache = _forward(arm, parameters, inputs)
    error = prediction - targets
    loss = float(np.mean(error * error))
    derivative = (2.0 / len(targets)) * error
    gradients: dict[str, np.ndarray] = {}

    if arm in {
        SWM0WArm.ROLE_TRIPLE,
        SWM0WArm.TYPED_STAR_TRIPLE,
        SWM0WArm.LOWER_ORDER_PAIR,
        SWM0WArm.ADDITIVE,
    }:
        hidden = cache["hidden"]
        gradients["out_b"] = np.asarray([derivative.sum()])
        gradients["unary_w"] = np.einsum("n,nrh->rh", derivative, hidden)
        hidden_gradient = derivative[:, None, None] * parameters["unary_w"][None, :, :]
        if "pair_w" in parameters:
            gradients["pair_w"] = np.einsum(
                "n,nph->ph", derivative, cache["pair_products"]
            )
            for pair_position, (left, right) in enumerate(PAIR_INDEX):
                weighted = derivative[:, None] * parameters["pair_w"][pair_position]
                hidden_gradient[:, left, :] += weighted * hidden[:, right, :]
                hidden_gradient[:, right, :] += weighted * hidden[:, left, :]
        if "triple_w" in parameters:
            gradients["triple_w"] = np.einsum("n,nh->h", derivative, cache["triple"])
            weighted = derivative[:, None] * parameters["triple_w"]
            hidden_gradient[:, 0, :] += weighted * hidden[:, 1, :] * hidden[:, 2, :]
            hidden_gradient[:, 1, :] += weighted * hidden[:, 0, :] * hidden[:, 2, :]
            hidden_gradient[:, 2, :] += weighted * hidden[:, 0, :] * hidden[:, 1, :]
        pre_gradient = hidden_gradient * (1.0 - hidden * hidden)
        gradients["encoder_w"] = np.einsum("nrf,nrh->rfh", cache["x"], pre_gradient)
        gradients["encoder_b"] = pre_gradient.sum(axis=0)
        return loss, gradients

    if arm is SWM0WArm.ROLELESS:
        hidden = cache["hidden"]
        gradients["out_b"] = np.asarray([derivative.sum()])
        gradients["out_w"] = cache["pooled"].T @ derivative
        hidden_gradient = (
            derivative[:, None, None]
            * parameters["out_w"][None, None, :]
            / len(ROLES)
        )
        pre_gradient = hidden_gradient * (1.0 - hidden * hidden)
        gradients["encoder_w"] = np.einsum(
            "nrf,nrh->fh", cache["x"], pre_gradient
        )
        gradients["encoder_b"] = pre_gradient.sum(axis=(0, 1))
        return loss, gradients

    if arm is SWM0WArm.FLAT_MLP:
        hidden1 = cache["hidden1"]
        hidden2 = cache["hidden2"]
        gradients["out_b"] = np.asarray([derivative.sum()])
        gradients["out_w"] = hidden2.T @ derivative
        grad_hidden2 = derivative[:, None] * parameters["out_w"]
        grad_pre2 = grad_hidden2 * (1.0 - hidden2 * hidden2)
        gradients["hidden2_w"] = hidden1.T @ grad_pre2
        gradients["hidden2_b"] = grad_pre2.sum(axis=0)
        grad_hidden1 = grad_pre2 @ parameters["hidden2_w"].T
        grad_pre1 = grad_hidden1 * (1.0 - hidden1 * hidden1)
        gradients["hidden1_w"] = cache["flat"].T @ grad_pre1
        gradients["hidden1_b"] = grad_pre1.sum(axis=0)
        return loss, gradients

    if arm is SWM0WArm.ROLE_AWARE_DEEPSETS:
        phi = cache["phi"]
        rho = cache["rho"]
        gradients["out_b"] = np.asarray([derivative.sum()])
        gradients["out_w"] = rho.T @ derivative
        grad_rho = derivative[:, None] * parameters["out_w"]
        grad_pre_rho = grad_rho * (1.0 - rho * rho)
        gradients["rho_w"] = cache["pooled"].T @ grad_pre_rho
        gradients["rho_b"] = grad_pre_rho.sum(axis=0)
        grad_pooled = grad_pre_rho @ parameters["rho_w"].T
        grad_phi = np.broadcast_to(grad_pooled[:, None, :], phi.shape)
        grad_pre_phi = grad_phi * (1.0 - phi * phi)
        gradients["phi_w"] = np.einsum("nrf,nrh->fh", cache["tokens"], grad_pre_phi)
        gradients["phi_b"] = grad_pre_phi.sum(axis=(0, 1))
        return loss, gradients
    raise AssertionError(f"unhandled arm: {arm}")


def _clip_gradients(
    gradients: Mapping[str, np.ndarray], threshold: float
) -> tuple[dict[str, np.ndarray], float, bool]:
    norm = math.sqrt(
        sum(float(np.sum(np.asarray(value) ** 2)) for value in gradients.values())
    )
    if not math.isfinite(norm):
        raise SWM0WOperatorError("non-finite gradient norm")
    clipped = norm > threshold
    scale = threshold / norm if clipped and norm > 0.0 else 1.0
    return (
        {name: np.asarray(value) * scale for name, value in gradients.items()},
        norm,
        clipped,
    )


@dataclass(frozen=True, slots=True)
class OptimizationReceipt:
    arm: SWM0WArm
    config: TrainingConfig
    train_dataset_sha256: str
    dev_dataset_sha256: str
    evaluator_binding_sha256: str
    normalization_sha256: str
    typed_star_input_parity_sha256: str | None
    initial_parameters_sha256: str
    best_epoch: int
    stopped_epoch: int
    best_train_loss: float
    best_dev_loss: float
    update_count: int
    clipped_update_count: int
    history_sha256: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.arm) is not SWM0WArm or type(self.config) is not TrainingConfig:
            raise SWM0WOperatorError(
                "optimization receipt requires exact arm and training config"
            )
        for field in (
            "train_dataset_sha256",
            "dev_dataset_sha256",
            "evaluator_binding_sha256",
            "normalization_sha256",
            "initial_parameters_sha256",
            "history_sha256",
            "receipt_sha256",
        ):
            _require_sha256(getattr(self, field), field)
        if self.typed_star_input_parity_sha256 is not None:
            _require_sha256(
                self.typed_star_input_parity_sha256,
                "typed_star_input_parity_sha256",
            )
        triple_arm = self.arm in {
            SWM0WArm.ROLE_TRIPLE,
            SWM0WArm.TYPED_STAR_TRIPLE,
        }
        if triple_arm != (self.typed_star_input_parity_sha256 is not None):
            raise SWM0WOperatorError(
                "typed-star parity receipt presence disagrees with the arm"
            )
        if (
            type(self.best_epoch) is not int
            or type(self.stopped_epoch) is not int
            or not 0 <= self.best_epoch <= self.stopped_epoch <= self.config.epochs
        ):
            raise SWM0WOperatorError("optimization epochs are inconsistent")
        if self.stopped_epoch == 0:
            raise SWM0WOperatorError("optimization must execute at least one epoch")
        if any(
            not math.isfinite(value) or value < 0.0
            for value in (self.best_train_loss, self.best_dev_loss)
        ):
            raise SWM0WOperatorError(
                "optimization losses must be finite and non-negative"
            )
        if (
            type(self.update_count) is not int
            or type(self.clipped_update_count) is not int
            or self.update_count <= 0
            or not 0 <= self.clipped_update_count <= self.update_count
        ):
            raise SWM0WOperatorError("optimization update counts are inconsistent")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WOperatorError("optimization receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "arm": self.arm.value,
            "best_dev_loss": self.best_dev_loss,
            "best_epoch": self.best_epoch,
            "best_train_loss": self.best_train_loss,
            "clipped_update_count": self.clipped_update_count,
            "config": self.config.canonical(),
            "dev_dataset_sha256": self.dev_dataset_sha256,
            "evaluator_binding_sha256": self.evaluator_binding_sha256,
            "history_sha256": self.history_sha256,
            "initial_parameters_sha256": self.initial_parameters_sha256,
            "initialization_domain": INITIALIZATION_DOMAIN,
            "normalization_sha256": self.normalization_sha256,
            "optimizer": OPTIMIZER_VERSION,
            "schema_version": OPTIMIZATION_RECEIPT_VERSION,
            "stopped_epoch": self.stopped_epoch,
            "train_dataset_sha256": self.train_dataset_sha256,
            "training_order_domain": TRAINING_ORDER_DOMAIN,
            "typed_star_input_parity_sha256": self.typed_star_input_parity_sha256,
            "update_count": self.update_count,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class OperationEstimate:
    arm: SWM0WArm
    parameter_count: int
    matrix_multiply_accumulates: int
    hadamard_multiplications: int
    nonlinearities: int

    @property
    def scalar_operation_proxy(self) -> int:
        return (
            2 * self.matrix_multiply_accumulates
            + self.hadamard_multiplications
            + self.nonlinearities
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "arm": self.arm.value,
            "hadamard_multiplications": self.hadamard_multiplications,
            "matrix_multiply_accumulates": self.matrix_multiply_accumulates,
            "nonlinearities": self.nonlinearities,
            "parameter_count": self.parameter_count,
            "scope": (
                "LEARNED_CORE_PROXY_EXCLUDES_COMPILER_NORMALIZATION_"
                "BIAS_ADDS_AND_POOL_REDUCTIONS_NOT_EQUAL_COMPUTE"
            ),
            "scalar_operation_proxy": self.scalar_operation_proxy,
        }


@dataclass(frozen=True, slots=True)
class InteractionHeadV1:
    """One learned width-vector selected by its canonical participating roles."""

    roles: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            type(self.roles) is not tuple
            or not 1 <= len(self.roles) <= len(ROLES)
            or len(set(self.roles)) != len(self.roles)
            or any(role not in ROLES for role in self.roles)
        ):
            raise SWM0WOperatorError(
                "interaction head requires one to three unique registered roles"
            )
        canonical_roles = tuple(role for role in ROLES if role in self.roles)
        if self.roles != canonical_roles:
            raise SWM0WOperatorError(
                "interaction-head roles must use registered canonical order"
            )

    @property
    def order(self) -> int:
        return len(self.roles)

    def canonical(self) -> dict[str, Any]:
        return {"order": self.order, "roles": list(self.roles)}


def _head_location(head: InteractionHeadV1) -> tuple[str, int | None]:
    if type(head) is not InteractionHeadV1:
        raise SWM0WOperatorError("head selector must be InteractionHeadV1")
    indices = tuple(ROLES.index(role) for role in head.roles)
    if head.order == 1:
        return "unary_w", indices[0]
    if head.order == 2:
        return "pair_w", PAIR_INDEX.index(indices)
    return "triple_w", None


def _head_parameter_view(
    parameters: Mapping[str, np.ndarray], head: InteractionHeadV1
) -> np.ndarray:
    name, row = _head_location(head)
    if name not in parameters:
        raise SWM0WOperatorError(
            f"selected interaction head is unavailable: {head.roles!r}"
        )
    value = parameters[name] if row is None else parameters[name][row]
    if value.ndim != 1:
        raise SWM0WOperatorError("interaction head must select one width-vector")
    return value


@dataclass(frozen=True, slots=True)
class LearnedSWM0WOperator:
    arm: SWM0WArm
    config: TrainingConfig
    normalizer: TrainOnlyNormalizer
    parameters: Mapping[str, np.ndarray]
    optimization: OptimizationReceipt
    intervention: InteractionHeadV1 | None = None

    def __post_init__(self) -> None:
        selected = _coerce_arm(self.arm)
        parameters = {
            name: _immutable_float64(value)
            for name, value in _copy_parameters(self.parameters).items()
        }
        if not parameters or any(not np.isfinite(value).all() for value in parameters.values()):
            raise SWM0WOperatorError("model parameters must be finite and non-empty")
        expected_shapes = _expected_parameter_shapes(selected, self.config.width)
        actual_shapes = {name: value.shape for name, value in parameters.items()}
        if actual_shapes != expected_shapes:
            raise SWM0WOperatorError(
                f"parameter shapes disagree with {selected.value}: {actual_shapes!r}"
            )
        if self.optimization.arm is not selected or self.optimization.config != self.config:
            raise SWM0WOperatorError("optimization receipt does not bind arm/config")
        if self.optimization.normalization_sha256 != self.normalizer.state_sha256:
            raise SWM0WOperatorError("optimization receipt does not bind normalization")
        object.__setattr__(self, "arm", selected)
        object.__setattr__(self, "parameters", MappingProxyType(parameters))
        if self.intervention is not None:
            if type(self.intervention) is not InteractionHeadV1:
                raise SWM0WOperatorError("unsupported frozen intervention")
            removed = _head_parameter_view(parameters, self.intervention)
            if removed.shape != (self.config.width,) or not np.all(removed == 0.0):
                raise SWM0WOperatorError(
                    "removed interaction head must be one exact zero width-vector"
                )

    @property
    def parameter_count(self) -> int:
        return sum(int(value.size) for value in self.parameters.values())

    @property
    def state_sha256(self) -> str:
        return canonical_sha256(
            {
                "arm": self.arm.value,
                "config": self.config.canonical(),
                "intervention": None
                if self.intervention is None
                else {
                    "head": self.intervention.canonical(),
                    "kind": "FROZEN_INTERACTION_HEAD_REMOVAL",
                },
                "normalization_sha256": self.normalizer.state_sha256,
                "optimization_receipt_sha256": self.optimization.receipt_sha256,
                "parameters": _parameter_receipt(self.parameters),
                "schema_version": OPERATOR_VERSION,
            }
        )

    def score(self, world: ModelWorldV1) -> float:
        compiler = _compiler_for_arm(self.arm)
        raw = compiler(world)[None, :, :]
        normalized = self.normalizer.transform(raw)
        prediction, _ = _forward(self.arm, self.parameters, normalized)
        return float(prediction[0])

    def predict(self, world: ModelWorldV1) -> float:
        """Return the learned continuous score; no field decoder is available."""

        return self.score(world)

    def mean_squared_error(
        self, cases: Sequence[EvaluatorEnvelopeV1]
    ) -> float:
        views = _validated_evaluator_views(cases, expected_split=None)
        return self._mean_squared_error_views(views)

    def _mean_squared_error_views(
        self, views: Sequence[_EvaluatorViewV1]
    ) -> float:
        ordered_views = sorted(
            views,
            key=lambda view: (view.world.semantic_sha256, view.target.hex()),
        )
        residuals = np.asarray(
            [self.score(view.world) - view.target for view in ordered_views],
            dtype=np.float64,
        )
        with np.errstate(over="ignore", invalid="ignore"):
            mse = float(np.mean(residuals * residuals))
        if not math.isfinite(mse):
            raise SWM0WOperatorError("mean-squared error must be finite")
        return mse

    def operation_estimate(self) -> OperationEstimate:
        width = self.config.width
        if self.arm in {
            SWM0WArm.ROLE_TRIPLE,
            SWM0WArm.TYPED_STAR_TRIPLE,
            SWM0WArm.LOWER_ORDER_PAIR,
            SWM0WArm.ADDITIVE,
        }:
            pair_count = len(PAIR_INDEX) if "pair_w" in self.parameters else 0
            triple_count = 1 if "triple_w" in self.parameters else 0
            macs = len(ROLES) * 2 * width
            macs += (len(ROLES) + pair_count + triple_count) * width
            hadamards = pair_count * width + 2 * triple_count * width
            nonlinearities = len(ROLES) * width
        elif self.arm is SWM0WArm.ROLELESS:
            macs = len(ROLES) * 2 * width + width
            hadamards = 0
            nonlinearities = len(ROLES) * width
        elif self.arm is SWM0WArm.FLAT_MLP:
            macs = len(ROLES) * 2 * width + width * width + width
            hadamards = 0
            nonlinearities = 2 * width
        else:
            macs = len(ROLES) * (2 + len(ROLES)) * width
            macs += width * width + width
            hadamards = 0
            nonlinearities = (len(ROLES) + 1) * width
        return OperationEstimate(
            arm=self.arm,
            parameter_count=self.parameter_count,
            matrix_multiply_accumulates=macs,
            hadamard_multiplications=hadamards,
            nonlinearities=nonlinearities,
        )


def fit_operator(
    train_cases: Sequence[EvaluatorEnvelopeV1],
    dev_cases: Sequence[EvaluatorEnvelopeV1],
    arm: SWM0WArm | str = SWM0WArm.ROLE_TRIPLE,
    *,
    config: TrainingConfig = TrainingConfig(),
) -> LearnedSWM0WOperator:
    """Fit one arm with manual Adam, global clipping, and dev early stopping."""

    selected = _coerce_arm(arm)
    train_views, dev_views, evaluator_binding_sha256 = (
        _validate_training_split_contract(train_cases, dev_cases)
    )
    parity_sha256 = (
        _typed_star_parity_receipt((*train_views, *dev_views))
        if selected in {SWM0WArm.ROLE_TRIPLE, SWM0WArm.TYPED_STAR_TRIPLE}
        else None
    )
    train_raw, train_targets = _dataset(train_views, selected)
    dev_raw, dev_targets = _dataset(dev_views, selected)
    normalizer = TrainOnlyNormalizer.fit(train_raw)
    train = normalizer.transform(train_raw)
    dev = normalizer.transform(dev_raw)

    parameters = _initial_parameters(selected, config.width, config.seed)
    order_seed_material = canonical_sha256(
        [TRAINING_ORDER_DOMAIN, config.seed]
    )
    rng = np.random.Generator(
        np.random.PCG64(int(order_seed_material[:16], 16))
    )
    parameters["out_b"][0] = float(train_targets.mean())
    initial_sha = canonical_sha256(_parameter_receipt(parameters))
    first_dev_prediction, _ = _forward(selected, parameters, dev)
    best_dev_loss = float(np.mean((first_dev_prediction - dev_targets) ** 2))
    first_train_prediction, _ = _forward(selected, parameters, train)
    best_train_loss = float(np.mean((first_train_prediction - train_targets) ** 2))
    best_parameters = _copy_parameters(parameters)
    best_epoch = 0
    stale_epochs = 0

    moments = {name: np.zeros_like(value) for name, value in parameters.items()}
    variances = {name: np.zeros_like(value) for name, value in parameters.items()}
    update_count = 0
    clipped_count = 0
    history: list[dict[str, Any]] = []
    stopped_epoch = 0
    for epoch in range(1, config.epochs + 1):
        order = rng.permutation(len(train))
        for start in range(0, len(order), config.batch_size):
            indices = order[start : start + config.batch_size]
            _, gradients = _loss_and_gradients(
                selected, parameters, train[indices], train_targets[indices]
            )
            gradients, _, clipped = _clip_gradients(
                gradients, config.gradient_clip
            )
            clipped_count += int(clipped)
            update_count += 1
            for name in sorted(parameters):
                gradient = gradients[name]
                moments[name] = (
                    config.beta1 * moments[name] + (1.0 - config.beta1) * gradient
                )
                variances[name] = (
                    config.beta2 * variances[name]
                    + (1.0 - config.beta2) * gradient * gradient
                )
                corrected_moment = moments[name] / (1.0 - config.beta1**update_count)
                corrected_variance = variances[name] / (
                    1.0 - config.beta2**update_count
                )
                parameters[name] -= config.learning_rate * corrected_moment / (
                    np.sqrt(corrected_variance) + config.epsilon
                )

        train_prediction, _ = _forward(selected, parameters, train)
        dev_prediction, _ = _forward(selected, parameters, dev)
        train_loss = float(np.mean((train_prediction - train_targets) ** 2))
        dev_loss = float(np.mean((dev_prediction - dev_targets) ** 2))
        history.append(
            {"dev_loss_hex": dev_loss.hex(), "epoch": epoch, "train_loss_hex": train_loss.hex()}
        )
        stopped_epoch = epoch
        if dev_loss < best_dev_loss - config.min_delta:
            best_dev_loss = dev_loss
            best_train_loss = train_loss
            best_parameters = _copy_parameters(parameters)
            best_epoch = epoch
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= config.patience:
                break

    receipt_without_hash = {
        "arm": selected.value,
        "best_dev_loss": best_dev_loss,
        "best_epoch": best_epoch,
        "best_train_loss": best_train_loss,
        "clipped_update_count": clipped_count,
        "config": config.canonical(),
        "dev_dataset_sha256": _dataset_sha256(dev_views),
        "evaluator_binding_sha256": evaluator_binding_sha256,
        "history_sha256": canonical_sha256(history),
        "initial_parameters_sha256": initial_sha,
        "initialization_domain": INITIALIZATION_DOMAIN,
        "normalization_sha256": normalizer.state_sha256,
        "optimizer": OPTIMIZER_VERSION,
        "schema_version": OPTIMIZATION_RECEIPT_VERSION,
        "stopped_epoch": stopped_epoch,
        "train_dataset_sha256": _dataset_sha256(train_views),
        "training_order_domain": TRAINING_ORDER_DOMAIN,
        "typed_star_input_parity_sha256": parity_sha256,
        "update_count": update_count,
    }
    optimization = OptimizationReceipt(
        arm=selected,
        config=config,
        train_dataset_sha256=receipt_without_hash["train_dataset_sha256"],
        dev_dataset_sha256=receipt_without_hash["dev_dataset_sha256"],
        evaluator_binding_sha256=evaluator_binding_sha256,
        normalization_sha256=normalizer.state_sha256,
        initial_parameters_sha256=initial_sha,
        typed_star_input_parity_sha256=parity_sha256,
        best_epoch=best_epoch,
        stopped_epoch=stopped_epoch,
        best_train_loss=best_train_loss,
        best_dev_loss=best_dev_loss,
        update_count=update_count,
        clipped_update_count=clipped_count,
        history_sha256=receipt_without_hash["history_sha256"],
        receipt_sha256=canonical_sha256(receipt_without_hash),
    )
    return LearnedSWM0WOperator(
        arm=selected,
        config=config,
        normalizer=normalizer,
        parameters=best_parameters,
        optimization=optimization,
    )


@dataclass(frozen=True, slots=True)
class HeadRemovalReceiptV2:
    base_state_sha256: str
    ablated_state_sha256: str
    arm: SWM0WArm
    head: InteractionHeadV1
    width: int
    removed_values_hex: tuple[str, ...]
    receipt_sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.base_state_sha256, "base_state_sha256")
        _require_sha256(self.ablated_state_sha256, "ablated_state_sha256")
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        if type(self.arm) is not SWM0WArm:
            raise SWM0WOperatorError("head-removal receipt requires a bound arm")
        if type(self.head) is not InteractionHeadV1:
            raise SWM0WOperatorError("head-removal receipt requires a head selector")
        if type(self.width) is not int or self.width <= 0:
            raise SWM0WOperatorError("head-removal width must be positive")
        if (
            type(self.removed_values_hex) is not tuple
            or len(self.removed_values_hex) != self.width
        ):
            raise SWM0WOperatorError(
                "head-removal receipt must contain exactly one width-vector"
            )
        shapes = _expected_parameter_shapes(self.arm, self.width)
        name, _ = _head_location(self.head)
        if name not in shapes:
            raise SWM0WOperatorError(
                "head-removal receipt selects an unavailable interaction head"
            )
        try:
            restored = [
                float.fromhex(value) for value in self.removed_values_hex
            ]
        except (TypeError, ValueError) as exc:
            raise SWM0WOperatorError(
                "head-removal receipt has invalid floats"
            ) from exc
        if not all(math.isfinite(value) for value in restored):
            raise SWM0WOperatorError(
                "head-removal receipt has non-finite floats"
            )
        if any(
            type(encoded) is not str
            or float.fromhex(encoded).hex() != encoded
            for encoded in self.removed_values_hex
        ):
            raise SWM0WOperatorError(
                "head-removal receipt requires canonical finite float hex"
            )
        if self.base_state_sha256 == self.ablated_state_sha256:
            raise SWM0WOperatorError(
                "head-removal intervention must change the state digest"
            )
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WOperatorError("head-removal receipt hash mismatch")

    @property
    def removed_value_count(self) -> int:
        return len(self.removed_values_hex)

    @property
    def triple_head_hex(self) -> tuple[str, ...]:
        """Compatibility view for receipts produced by ``remove_triple_head``."""

        if self.head.roles != ROLES:
            raise SWM0WOperatorError("receipt does not describe the triple head")
        return self.removed_values_hex

    def unsigned(self) -> dict[str, Any]:
        return {
            "ablated_state_sha256": self.ablated_state_sha256,
            "arm": self.arm.value,
            "base_state_sha256": self.base_state_sha256,
            "head": self.head.canonical(),
            "intervention": "FROZEN_INTERACTION_HEAD_REMOVE_RESTORE",
            "removed_values_hex": list(self.removed_values_hex),
            "schema_version": HEAD_REMOVAL_RECEIPT_VERSION,
            "width": self.width,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def remove_interaction_head(
    model: LearnedSWM0WOperator,
    head: InteractionHeadV1,
) -> tuple[LearnedSWM0WOperator, HeadRemovalReceiptV2]:
    if type(model) is not LearnedSWM0WOperator:
        raise SWM0WOperatorError("head removal requires a learned operator")
    if type(head) is not InteractionHeadV1:
        raise SWM0WOperatorError("head removal requires InteractionHeadV1")
    if model.intervention is not None:
        raise SWM0WOperatorError("model already carries a frozen intervention")
    parameters = _copy_parameters(model.parameters)
    selected = _head_parameter_view(parameters, head)
    if selected.shape != (model.config.width,):
        raise SWM0WOperatorError("selected head is not one model-width vector")
    removed = selected.copy()
    selected.fill(0.0)
    ablated = replace(model, parameters=parameters, intervention=head)
    unsigned = {
        "ablated_state_sha256": ablated.state_sha256,
        "arm": model.arm.value,
        "base_state_sha256": model.state_sha256,
        "head": head.canonical(),
        "intervention": "FROZEN_INTERACTION_HEAD_REMOVE_RESTORE",
        "removed_values_hex": [float(value).hex() for value in removed],
        "schema_version": HEAD_REMOVAL_RECEIPT_VERSION,
        "width": model.config.width,
    }
    receipt = HeadRemovalReceiptV2(
        base_state_sha256=model.state_sha256,
        ablated_state_sha256=ablated.state_sha256,
        arm=model.arm,
        head=head,
        width=model.config.width,
        removed_values_hex=tuple(float(value).hex() for value in removed),
        receipt_sha256=canonical_sha256(unsigned),
    )
    return ablated, receipt


def restore_interaction_head(
    model: LearnedSWM0WOperator,
    receipt: HeadRemovalReceiptV2,
) -> LearnedSWM0WOperator:
    if (
        type(model) is not LearnedSWM0WOperator
        or type(receipt) is not HeadRemovalReceiptV2
    ):
        raise SWM0WOperatorError(
            "head restoration requires a learned operator and exact receipt"
        )
    if model.state_sha256 != receipt.ablated_state_sha256:
        raise SWM0WOperatorError("head-removal receipt does not bind this model")
    if (
        model.arm is not receipt.arm
        or model.intervention != receipt.head
        or model.config.width != receipt.width
    ):
        raise SWM0WOperatorError("head restoration arm/intervention mismatch")
    selected = _head_parameter_view(model.parameters, receipt.head)
    if selected.shape != (receipt.width,) or not np.all(selected == 0.0):
        raise SWM0WOperatorError("ablated interaction head is not exactly zero")
    parameters = _copy_parameters(model.parameters)
    destination = _head_parameter_view(parameters, receipt.head)
    destination[:] = np.asarray(
        [float.fromhex(value) for value in receipt.removed_values_hex],
        dtype=np.float64,
    )
    restored = replace(model, parameters=parameters, intervention=None)
    if restored.state_sha256 != receipt.base_state_sha256:
        raise SWM0WOperatorError("interaction-head restoration is not bit exact")
    return restored


TripleHeadRemovalReceipt = HeadRemovalReceiptV2


def remove_triple_head(
    model: LearnedSWM0WOperator,
) -> tuple[LearnedSWM0WOperator, HeadRemovalReceiptV2]:
    return remove_interaction_head(model, InteractionHeadV1(ROLES))


def restore_triple_head(
    model: LearnedSWM0WOperator,
    receipt: HeadRemovalReceiptV2,
) -> LearnedSWM0WOperator:
    if type(receipt) is not HeadRemovalReceiptV2 or receipt.head.roles != ROLES:
        raise SWM0WOperatorError("triple-head restoration requires all roles")
    return restore_interaction_head(model, receipt)


@dataclass(frozen=True, slots=True)
class SuiteComparison:
    mean_squared_error_by_arm: tuple[tuple[str, float], ...]
    model_state_sha256_by_arm: tuple[tuple[str, str], ...]
    evaluation_dataset_sha256: str
    evaluator_binding_sha256: str
    tie_tolerance: float
    target_minus_best_complete_control_mse: float | None
    complete_control_ties_or_wins: bool | None
    novelty_claim_allowed: bool
    interpretation: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        _require_sha256(
            self.evaluation_dataset_sha256, "evaluation_dataset_sha256"
        )
        _require_sha256(
            self.evaluator_binding_sha256, "evaluator_binding_sha256"
        )
        for name, rows in (
            ("mean_squared_error_by_arm", self.mean_squared_error_by_arm),
            ("model_state_sha256_by_arm", self.model_state_sha256_by_arm),
        ):
            if type(rows) is not tuple or any(
                type(row) is not tuple or len(row) != 2 for row in rows
            ):
                raise SWM0WOperatorError(
                    f"{name} must be an immutable tuple of pairs"
                )
        if not self.mean_squared_error_by_arm:
            raise SWM0WOperatorError("comparison requires at least one MSE entry")
        names = [name for name, _ in self.mean_squared_error_by_arm]
        if len(names) != len(set(names)) or any(
            type(name) is not str
            or type(value) is not float
            or not math.isfinite(value)
            or value < 0.0
            for name, value in self.mean_squared_error_by_arm
        ):
            raise SWM0WOperatorError("comparison requires unique finite MSE entries")
        registered_names = {arm.value for arm in SWM0WArm}
        if (
            names != sorted(names)
            or any(name not in registered_names for name in names)
        ):
            raise SWM0WOperatorError(
                "comparison MSE arms must be registered and canonically ordered"
            )
        state_names = [name for name, _ in self.model_state_sha256_by_arm]
        if state_names != names:
            raise SWM0WOperatorError(
                "comparison model-state arms must exactly match MSE arms"
            )
        for name, state_sha256 in self.model_state_sha256_by_arm:
            if type(name) is not str:
                raise SWM0WOperatorError("model-state arm names must be strings")
            _require_sha256(state_sha256, "model_state_sha256")
        if (
            isinstance(self.tie_tolerance, bool)
            or not math.isfinite(self.tie_tolerance)
            or self.tie_tolerance < 0.0
        ):
            raise SWM0WOperatorError(
                "comparison tie_tolerance must be finite and non-negative"
            )
        if self.novelty_claim_allowed is not False:
            raise SWM0WOperatorError("SWM-0W smoke cannot authorize a novelty claim")
        if self.target_minus_best_complete_control_mse is not None and not math.isfinite(
            self.target_minus_best_complete_control_mse
        ):
            raise SWM0WOperatorError("comparison delta must be finite when present")
        errors = dict(self.mean_squared_error_by_arm)
        target = errors.get(SWM0WArm.ROLE_TRIPLE.value)
        complete = [
            errors[arm.value]
            for arm in COMPLETE_CONTROLS
            if arm.value in errors
        ]
        expected_delta = (
            None if target is None or not complete else target - min(complete)
        )
        if self.target_minus_best_complete_control_mse != expected_delta:
            raise SWM0WOperatorError(
                "comparison delta disagrees with registered MSE values"
            )
        expected_tie_or_win = (
            None
            if expected_delta is None
            else expected_delta >= -self.tie_tolerance
        )
        if self.complete_control_ties_or_wins is not expected_tie_or_win:
            raise SWM0WOperatorError(
                "comparison tie decision disagrees with delta/tolerance"
            )
        expected_interpretation = (
            "No novelty claim: a strong information-complete control ties or wins."
            if expected_tie_or_win
            else "No novelty claim from this smoke; a later preregistered comparison is required."
        )
        if self.interpretation != expected_interpretation:
            raise SWM0WOperatorError(
                "comparison interpretation disagrees with its measured branch"
            )
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WOperatorError("suite-comparison receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "evaluation_dataset_sha256": self.evaluation_dataset_sha256,
            "evaluator_binding_sha256": self.evaluator_binding_sha256,
            "mean_squared_error_by_arm": dict(self.mean_squared_error_by_arm),
            "model_state_sha256_by_arm": dict(self.model_state_sha256_by_arm),
            "complete_control_ties_or_wins": self.complete_control_ties_or_wins,
            "interpretation": self.interpretation,
            "novelty_claim_allowed": self.novelty_claim_allowed,
            "schema_version": SUITE_COMPARISON_VERSION,
            "tie_tolerance": self.tie_tolerance,
            "target_minus_best_complete_control_mse": self.target_minus_best_complete_control_mse,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def compare_models(
    models: Mapping[SWM0WArm | str, LearnedSWM0WOperator],
    cases: Sequence[EvaluatorEnvelopeV1],
    *,
    tie_tolerance: float = 1.0e-12,
) -> SuiteComparison:
    if (
        isinstance(tie_tolerance, bool)
        or not math.isfinite(tie_tolerance)
        or tie_tolerance < 0.0
    ):
        raise SWM0WOperatorError("tie_tolerance must be finite and non-negative")
    normalized: dict[SWM0WArm, LearnedSWM0WOperator] = {}
    for arm, model in models.items():
        selected = _coerce_arm(arm)
        if selected in normalized:
            raise SWM0WOperatorError("comparison contains a duplicate arm")
        if type(model) is not LearnedSWM0WOperator or model.arm is not selected:
            raise SWM0WOperatorError("comparison key does not match model arm")
        normalized[selected] = model
    if not normalized:
        raise SWM0WOperatorError("comparison requires at least one model")
    views = _validated_evaluator_views(cases, expected_split=None)
    errors = {
        arm: model._mean_squared_error_views(views)
        for arm, model in normalized.items()
    }
    target = errors.get(SWM0WArm.ROLE_TRIPLE)
    complete = [errors[arm] for arm in COMPLETE_CONTROLS if arm in errors]
    delta = None if target is None or not complete else target - min(complete)
    tie_or_win = None if delta is None else delta >= -tie_tolerance
    interpretation = (
        "No novelty claim: a strong information-complete control ties or wins."
        if tie_or_win
        else "No novelty claim from this smoke; a later preregistered comparison is required."
    )
    unsigned = {
        "evaluation_dataset_sha256": _dataset_sha256(views),
        "evaluator_binding_sha256": _evaluator_binding_sha256(
            {"evaluation": views}
        ),
        "mean_squared_error_by_arm": {
            arm.value: errors[arm] for arm in sorted(errors, key=lambda item: item.value)
        },
        "model_state_sha256_by_arm": {
            arm.value: normalized[arm].state_sha256
            for arm in sorted(normalized, key=lambda item: item.value)
        },
        "complete_control_ties_or_wins": tie_or_win,
        "interpretation": interpretation,
        "novelty_claim_allowed": False,
        "schema_version": SUITE_COMPARISON_VERSION,
        "target_minus_best_complete_control_mse": delta,
        "tie_tolerance": tie_tolerance,
    }
    return SuiteComparison(
        mean_squared_error_by_arm=tuple(
            sorted((arm.value, value) for arm, value in errors.items())
        ),
        model_state_sha256_by_arm=tuple(
            sorted(
                (arm.value, model.state_sha256)
                for arm, model in normalized.items()
            )
        ),
        evaluation_dataset_sha256=unsigned["evaluation_dataset_sha256"],
        evaluator_binding_sha256=unsigned["evaluator_binding_sha256"],
        tie_tolerance=tie_tolerance,
        target_minus_best_complete_control_mse=delta,
        complete_control_ties_or_wins=tie_or_win,
        novelty_claim_allowed=False,
        interpretation=interpretation,
        receipt_sha256=canonical_sha256(unsigned),
    )


__all__ = [
    "ALL_ARMS",
    "COMPLETE_CONTROLS",
    "DEFAULT_ROLE_TRIPLE_PARAMETER_COUNT",
    "DEFAULT_WIDTH",
    "EvaluatorEnvelopeV1",
    "HEAD_REMOVAL_RECEIPT_VERSION",
    "HeadRemovalReceiptV2",
    "INITIALIZATION_DOMAIN",
    "InteractionHeadV1",
    "LearnedSWM0WOperator",
    "OPERATOR_VERSION",
    "OPTIMIZATION_RECEIPT_VERSION",
    "OperationEstimate",
    "OptimizationReceipt",
    "SWM0WArm",
    "SWM0WOperatorError",
    "SuiteComparison",
    "TrainOnlyNormalizer",
    "TrainingConfig",
    "TRAINING_ORDER_DOMAIN",
    "TripleHeadRemovalReceipt",
    "assert_typed_star_parity",
    "canonical_json",
    "canonical_sha256",
    "cases_from_split",
    "compare_models",
    "compile_typed_star_input",
    "fit_operator",
    "native_role_input",
    "remove_interaction_head",
    "remove_triple_head",
    "restore_interaction_head",
    "restore_triple_head",
]
