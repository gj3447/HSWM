"""Learned fixed-arity third-order scalar compatibility for SWM-0W development.

Only the three model-visible role incidences and their two scalar features enter
the operator.  Labels are consumed by the training/evaluation boundary only.
There is no target oracle, field formula, lookup table, or identifier feature in
this module.

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
from typing import Any, Mapping, Sequence

import numpy as np

from hswm.experiments.swm0w_worlds import (
    ROLES,
    EvaluatorCaseV1,
    ModelWorldV1,
    RoleInputV1,
    cases_from_split,
)


OPERATOR_VERSION = "hswm-swm0w-learned-operator/v1"
OPTIMIZER_VERSION = "hswm-manual-adam/v1"
DEFAULT_WIDTH = 16
DEFAULT_ROLE_TRIPLE_PARAMETER_COUNT = 257
PAIR_INDEX = ((0, 1), (0, 2), (1, 2))


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
        finite_positive = (
            "learning_rate",
            "epsilon",
            "gradient_clip",
        )
        for name in finite_positive:
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise SWM0WOperatorError(f"{name} must be finite and positive")
        if not 0.0 < self.beta1 < 1.0 or not 0.0 < self.beta2 < 1.0:
            raise SWM0WOperatorError("Adam beta values must lie in (0, 1)")
        if not math.isfinite(self.min_delta) or self.min_delta < 0.0:
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

    if not isinstance(world, ModelWorldV1):
        raise SWM0WOperatorError("operator input must be ModelWorldV1")
    result = _validate_matrix(world.feature_matrix()).copy()
    result.setflags(write=False)
    return result


def compile_typed_star_input(world: ModelWorldV1) -> np.ndarray:
    """Independently compile role leaves without calling ``feature_matrix``."""

    if not isinstance(world, ModelWorldV1):
        raise SWM0WOperatorError("typed-star input must be ModelWorldV1")
    by_role: dict[str, tuple[float, float]] = {}
    for incidence in world.incidences:
        if not isinstance(incidence, RoleInputV1):
            raise SWM0WOperatorError("typed-star incidence must be RoleInputV1")
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


def _typed_star_parity_receipt(
    cases: Sequence[EvaluatorCaseV1],
) -> str:
    rows = []
    for case in cases:
        if not isinstance(case, EvaluatorCaseV1):
            raise SWM0WOperatorError("parity audit requires EvaluatorCaseV1")
        rows.append(
            (case.world.semantic_sha256, assert_typed_star_parity(case.world))
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
    cases: Sequence[EvaluatorCaseV1], arm: SWM0WArm
) -> tuple[np.ndarray, np.ndarray]:
    if not cases:
        raise SWM0WOperatorError("a dataset must contain at least one case")
    compiler = _compiler_for_arm(arm)
    inputs: list[np.ndarray] = []
    labels: list[float] = []
    # Optimizer trajectories must depend on semantic examples, not caller order
    # or evaluator-only opaque identities.
    ordered_cases = sorted(
        cases,
        key=lambda case: (case.world.semantic_sha256, case.target.hex())
        if isinstance(case, EvaluatorCaseV1)
        else ("", ""),
    )
    for case in ordered_cases:
        if not isinstance(case, EvaluatorCaseV1):
            raise SWM0WOperatorError("label plumbing requires EvaluatorCaseV1")
        inputs.append(compiler(case.world))
        if (
            type(case.target) is not float
            or not math.isfinite(case.target)
            or not -1.0 < case.target < 1.0
        ):
            raise SWM0WOperatorError(
                "evaluator target must be a finite open-interval tanh value"
            )
        labels.append(float(case.target))
    return np.stack(inputs), np.asarray(labels, dtype=np.float64)


def _dataset_sha256(cases: Sequence[EvaluatorCaseV1]) -> str:
    rows = sorted(
        (case.world.semantic_sha256, case.target.hex()) for case in cases
    )
    return canonical_sha256(rows)


def _validate_training_split_contract(
    train_cases: Sequence[EvaluatorCaseV1],
    dev_cases: Sequence[EvaluatorCaseV1],
) -> None:
    for cases, expected in ((train_cases, "train"), (dev_cases, "dev")):
        if not cases:
            raise SWM0WOperatorError(f"{expected} split cannot be empty")
        if any(
            not isinstance(case, EvaluatorCaseV1) or case.split != expected
            for case in cases
        ):
            raise SWM0WOperatorError(
                f"{expected} input requires only {expected} evaluator envelopes"
            )
    train_worlds = {case.world.semantic_sha256 for case in train_cases}
    dev_worlds = {case.world.semantic_sha256 for case in dev_cases}
    if not train_worlds.isdisjoint(dev_worlds):
        raise SWM0WOperatorError("train and dev semantic worlds must be disjoint")


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
    arm: SWM0WArm, width: int, rng: np.random.Generator
) -> dict[str, np.ndarray]:
    def random(shape: tuple[int, ...], fan_in: int) -> np.ndarray:
        limit = math.sqrt(6.0 / max(1, fan_in + width))
        return rng.uniform(-limit, limit, size=shape).astype(np.float64)

    if arm in {
        SWM0WArm.ROLE_TRIPLE,
        SWM0WArm.TYPED_STAR_TRIPLE,
        SWM0WArm.LOWER_ORDER_PAIR,
        SWM0WArm.ADDITIVE,
    }:
        params = {
            "encoder_w": random((len(ROLES), 2, width), 2),
            "encoder_b": np.zeros((len(ROLES), width), dtype=np.float64),
            "unary_w": random((len(ROLES), width), width),
            "out_b": np.zeros(1, dtype=np.float64),
        }
        if arm is not SWM0WArm.ADDITIVE:
            params["pair_w"] = random((len(PAIR_INDEX), width), width)
        if arm in {SWM0WArm.ROLE_TRIPLE, SWM0WArm.TYPED_STAR_TRIPLE}:
            params["triple_w"] = random((width,), width)
        return params
    if arm is SWM0WArm.ROLELESS:
        return {
            "encoder_w": random((2, width), 2),
            "encoder_b": np.zeros(width, dtype=np.float64),
            "out_w": random((width,), width),
            "out_b": np.zeros(1, dtype=np.float64),
        }
    if arm is SWM0WArm.FLAT_MLP:
        return {
            "hidden1_w": random((len(ROLES) * 2, width), len(ROLES) * 2),
            "hidden1_b": np.zeros(width, dtype=np.float64),
            "hidden2_w": random((width, width), width),
            "hidden2_b": np.zeros(width, dtype=np.float64),
            "out_w": random((width,), width),
            "out_b": np.zeros(1, dtype=np.float64),
        }
    if arm is SWM0WArm.ROLE_AWARE_DEEPSETS:
        return {
            "phi_w": random((2 + len(ROLES), width), 2 + len(ROLES)),
            "phi_b": np.zeros(width, dtype=np.float64),
            "rho_w": random((width, width), width),
            "rho_b": np.zeros(width, dtype=np.float64),
            "out_w": random((width,), width),
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
        for field in (
            "train_dataset_sha256",
            "dev_dataset_sha256",
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
            "history_sha256": self.history_sha256,
            "initial_parameters_sha256": self.initial_parameters_sha256,
            "normalization_sha256": self.normalization_sha256,
            "optimizer": OPTIMIZER_VERSION,
            "stopped_epoch": self.stopped_epoch,
            "train_dataset_sha256": self.train_dataset_sha256,
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
class LearnedSWM0WOperator:
    arm: SWM0WArm
    config: TrainingConfig
    normalizer: TrainOnlyNormalizer
    parameters: Mapping[str, np.ndarray]
    optimization: OptimizationReceipt
    intervention: str = "NONE"

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
        if self.intervention not in {"NONE", "TRIPLE_HEAD_REMOVED"}:
            raise SWM0WOperatorError("unsupported frozen intervention")
        if self.intervention == "TRIPLE_HEAD_REMOVED" and (
            "triple_w" not in parameters
            or not np.all(parameters["triple_w"] == 0.0)
        ):
            raise SWM0WOperatorError("removed triple head must be exactly zero")

    @property
    def parameter_count(self) -> int:
        return sum(int(value.size) for value in self.parameters.values())

    @property
    def state_sha256(self) -> str:
        return canonical_sha256(
            {
                "arm": self.arm.value,
                "config": self.config.canonical(),
                "intervention": self.intervention,
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

    def mean_squared_error(self, cases: Sequence[EvaluatorCaseV1]) -> float:
        if not cases:
            raise SWM0WOperatorError("mean-squared error requires evaluator cases")
        residuals = np.asarray(
            [self.score(case.world) - case.target for case in cases],
            dtype=np.float64,
        )
        return float(np.mean(residuals * residuals))

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
    train_cases: Sequence[EvaluatorCaseV1],
    dev_cases: Sequence[EvaluatorCaseV1],
    arm: SWM0WArm | str = SWM0WArm.ROLE_TRIPLE,
    *,
    config: TrainingConfig = TrainingConfig(),
) -> LearnedSWM0WOperator:
    """Fit one arm with manual Adam, global clipping, and dev early stopping."""

    selected = _coerce_arm(arm)
    _validate_training_split_contract(train_cases, dev_cases)
    parity_sha256 = (
        _typed_star_parity_receipt((*train_cases, *dev_cases))
        if selected in {SWM0WArm.ROLE_TRIPLE, SWM0WArm.TYPED_STAR_TRIPLE}
        else None
    )
    train_raw, train_targets = _dataset(train_cases, selected)
    dev_raw, dev_targets = _dataset(dev_cases, selected)
    normalizer = TrainOnlyNormalizer.fit(train_raw)
    train = normalizer.transform(train_raw)
    dev = normalizer.transform(dev_raw)

    initialization_family = (
        SWM0WArm.ROLE_TRIPLE
        if selected is SWM0WArm.TYPED_STAR_TRIPLE
        else selected
    )
    seed_material = canonical_sha256(
        [config.seed, initialization_family.value, OPERATOR_VERSION]
    )
    rng = np.random.Generator(np.random.PCG64(int(seed_material[:16], 16)))
    parameters = _initial_parameters(selected, config.width, rng)
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
        "dev_dataset_sha256": _dataset_sha256(dev_cases),
        "history_sha256": canonical_sha256(history),
        "initial_parameters_sha256": initial_sha,
        "normalization_sha256": normalizer.state_sha256,
        "optimizer": OPTIMIZER_VERSION,
        "stopped_epoch": stopped_epoch,
        "train_dataset_sha256": _dataset_sha256(train_cases),
        "typed_star_input_parity_sha256": parity_sha256,
        "update_count": update_count,
    }
    optimization = OptimizationReceipt(
        arm=selected,
        config=config,
        train_dataset_sha256=receipt_without_hash["train_dataset_sha256"],
        dev_dataset_sha256=receipt_without_hash["dev_dataset_sha256"],
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
class TripleHeadRemovalReceipt:
    base_state_sha256: str
    ablated_state_sha256: str
    arm: SWM0WArm
    triple_head_hex: tuple[str, ...]
    receipt_sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.base_state_sha256, "base_state_sha256")
        _require_sha256(self.ablated_state_sha256, "ablated_state_sha256")
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        if self.arm not in {
            SWM0WArm.ROLE_TRIPLE,
            SWM0WArm.TYPED_STAR_TRIPLE,
        }:
            raise SWM0WOperatorError("triple-head receipt has a non-triple arm")
        if not self.triple_head_hex:
            raise SWM0WOperatorError("triple-head receipt cannot be empty")
        try:
            restored = [float.fromhex(value) for value in self.triple_head_hex]
        except (TypeError, ValueError) as exc:
            raise SWM0WOperatorError("triple-head receipt has invalid floats") from exc
        if not all(math.isfinite(value) for value in restored):
            raise SWM0WOperatorError("triple-head receipt has non-finite floats")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WOperatorError("triple-head receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "ablated_state_sha256": self.ablated_state_sha256,
            "arm": self.arm.value,
            "base_state_sha256": self.base_state_sha256,
            "intervention": "FROZEN_TRIPLE_HEAD_REMOVE_RESTORE",
            "triple_head_hex": list(self.triple_head_hex),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def remove_triple_head(
    model: LearnedSWM0WOperator,
) -> tuple[LearnedSWM0WOperator, TripleHeadRemovalReceipt]:
    if model.arm not in {SWM0WArm.ROLE_TRIPLE, SWM0WArm.TYPED_STAR_TRIPLE}:
        raise SWM0WOperatorError("triple-head removal requires a full triple arm")
    if model.intervention != "NONE":
        raise SWM0WOperatorError("model already carries a frozen intervention")
    parameters = _copy_parameters(model.parameters)
    triple = parameters["triple_w"].copy()
    parameters["triple_w"].fill(0.0)
    ablated = replace(
        model, parameters=parameters, intervention="TRIPLE_HEAD_REMOVED"
    )
    unsigned = {
        "ablated_state_sha256": ablated.state_sha256,
        "arm": model.arm.value,
        "base_state_sha256": model.state_sha256,
        "intervention": "FROZEN_TRIPLE_HEAD_REMOVE_RESTORE",
        "triple_head_hex": [float(value).hex() for value in triple],
    }
    receipt = TripleHeadRemovalReceipt(
        base_state_sha256=model.state_sha256,
        ablated_state_sha256=ablated.state_sha256,
        arm=model.arm,
        triple_head_hex=tuple(float(value).hex() for value in triple),
        receipt_sha256=canonical_sha256(unsigned),
    )
    return ablated, receipt


def restore_triple_head(
    model: LearnedSWM0WOperator,
    receipt: TripleHeadRemovalReceipt,
) -> LearnedSWM0WOperator:
    if model.state_sha256 != receipt.ablated_state_sha256:
        raise SWM0WOperatorError("triple-head receipt does not bind this model")
    if model.arm is not receipt.arm or model.intervention != "TRIPLE_HEAD_REMOVED":
        raise SWM0WOperatorError("triple-head restoration arm/intervention mismatch")
    if not np.all(model.parameters["triple_w"] == 0.0):
        raise SWM0WOperatorError("ablated model triple head is not exactly zero")
    parameters = _copy_parameters(model.parameters)
    parameters["triple_w"] = np.asarray(
        [float.fromhex(value) for value in receipt.triple_head_hex], dtype=np.float64
    )
    restored = replace(model, parameters=parameters, intervention="NONE")
    if restored.state_sha256 != receipt.base_state_sha256:
        raise SWM0WOperatorError("triple-head restoration is not bit exact")
    return restored


@dataclass(frozen=True, slots=True)
class SuiteComparison:
    mean_squared_error_by_arm: tuple[tuple[str, float], ...]
    target_minus_best_complete_control_mse: float | None
    complete_control_ties_or_wins: bool | None
    novelty_claim_allowed: bool
    interpretation: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        names = [name for name, _ in self.mean_squared_error_by_arm]
        if len(names) != len(set(names)) or any(
            not math.isfinite(value) or value < 0.0
            for _, value in self.mean_squared_error_by_arm
        ):
            raise SWM0WOperatorError("comparison requires unique finite MSE entries")
        if self.novelty_claim_allowed is not False:
            raise SWM0WOperatorError("SWM-0W smoke cannot authorize a novelty claim")
        if self.target_minus_best_complete_control_mse is not None and not math.isfinite(
            self.target_minus_best_complete_control_mse
        ):
            raise SWM0WOperatorError("comparison delta must be finite when present")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WOperatorError("suite-comparison receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "mean_squared_error_by_arm": dict(self.mean_squared_error_by_arm),
            "complete_control_ties_or_wins": self.complete_control_ties_or_wins,
            "interpretation": self.interpretation,
            "novelty_claim_allowed": self.novelty_claim_allowed,
            "target_minus_best_complete_control_mse": self.target_minus_best_complete_control_mse,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def compare_models(
    models: Mapping[SWM0WArm | str, LearnedSWM0WOperator],
    cases: Sequence[EvaluatorCaseV1],
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
        if not isinstance(model, LearnedSWM0WOperator) or model.arm is not selected:
            raise SWM0WOperatorError("comparison key does not match model arm")
        normalized[selected] = model
    if not normalized:
        raise SWM0WOperatorError("comparison requires at least one model")
    errors = {
        arm: model.mean_squared_error(cases) for arm, model in normalized.items()
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
        "mean_squared_error_by_arm": {
            arm.value: errors[arm] for arm in sorted(errors, key=lambda item: item.value)
        },
        "complete_control_ties_or_wins": tie_or_win,
        "interpretation": interpretation,
        "novelty_claim_allowed": False,
        "target_minus_best_complete_control_mse": delta,
    }
    return SuiteComparison(
        mean_squared_error_by_arm=tuple(
            sorted((arm.value, value) for arm, value in errors.items())
        ),
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
    "LearnedSWM0WOperator",
    "OPERATOR_VERSION",
    "OperationEstimate",
    "OptimizationReceipt",
    "SWM0WArm",
    "SWM0WOperatorError",
    "SuiteComparison",
    "TrainOnlyNormalizer",
    "TrainingConfig",
    "TripleHeadRemovalReceipt",
    "assert_typed_star_parity",
    "canonical_json",
    "canonical_sha256",
    "cases_from_split",
    "compare_models",
    "compile_typed_star_input",
    "fit_operator",
    "native_role_input",
    "remove_triple_head",
    "restore_triple_head",
]
