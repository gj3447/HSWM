"""One-sweep set-to-set operator core for the unjudged SWM-0W-S2S bridge.

This module implements only the finite numeric engineering object specified by
``HSWM_SWM0W_S2S_GATE_2026-08-20.md``: one role-bearing hyperedge, three roles,
two members per role, and one simultaneous ``V -> E -> V`` sweep.  It contains
no optimizer, checkpoint selection, efficacy verdict, recurrence, LLM cell,
causal update, or topology mutation.

``T16`` is the proposed recipient-conditioned transport.  ``P_CAP18`` removes
its four-way Q head at the same exact 870-parameter budget.  ``DS870`` is an
information-complete equivariant DeepSets control at that same parameter
budget, but its operation receipt explicitly records its higher compute.

The public Q witness is evaluator-only constructive instrumentation.  It uses
the fixed target factors to prove that the T16 equation can express the frozen
finite family; it is not learned and cannot establish efficacy.

Scientific status: ``ENGINEERING_CORE_ONLY / UNJUDGED``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import itertools
import json
import math
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np

from hswm.experiments.swm0w_s2s_worlds import (
    CHANNELS,
    FIXED_FACTOR_TABLES,
    ROLE_CYCLES,
    ROLES,
    TARGET_SCALE_EXPONENT,
    EvaluatorCaseV1,
    ModelWorldV1,
    TaskSpecV1,
    centered_contrasts,
)


SCIENTIFIC_STATUS = "ENGINEERING_CORE_ONLY_UNJUDGED"
OPERATOR_VERSION = "hswm-swm0w-s2s-operator/v1"
ARCHITECTURE_RECEIPT_VERSION = "hswm-swm0w-s2s-architecture-receipt/v1"
Q_REMOVAL_RECEIPT_VERSION = "hswm-swm0w-s2s-q-removal/v1"
R2_RECEIPT_VERSION = "hswm-swm0w-s2s-stratified-r2/v1"
INITIALIZATION_DOMAIN = "hswm-swm0w-s2s-tensor-local-initialization/v1"
PARAMETER_HASH_DOMAIN = b"hswm-swm0w-s2s-parameters/v1\x00"

ROLE_COUNT = 3
MEMBER_COUNT = 2
INPUT_WIDTH = 4
OUTPUT_WIDTH = 2
T16_WIDTH = 16
P_CAP18_WIDTH = 18
DS_ETA_WIDTH = 4
DS_HIDDEN1_WIDTH = 14
DS_HIDDEN2_WIDTH = 22
ROLE_CODES = np.frombuffer(
    np.asarray(((1.0, 0.0), (0.0, 1.0), (-1.0, -1.0)), dtype=np.float64).tobytes(),
    dtype=np.float64,
).reshape(3, 2)


class SWM0WS2SOperatorError(ValueError):
    """Raised when the one-sweep operator boundary is malformed."""


class S2SArm(str, Enum):
    T16 = "T16"
    P_CAP18 = "P_CAP18"
    DS870 = "DS870"


class ParameterOrigin(str, Enum):
    EXTERNAL_UNTRAINED = "EXTERNAL_UNTRAINED"
    DETERMINISTIC_INITIALIZATION = "DETERMINISTIC_INITIALIZATION"
    EVALUATOR_ONLY_CONSTRUCTIVE_Q_WITNESS = (
        "EVALUATOR_ONLY_CONSTRUCTIVE_Q_WITNESS"
    )


ALL_ARMS = tuple(S2SArm)


_PARAMETER_SCHEMAS: Mapping[S2SArm, tuple[tuple[str, tuple[int, ...]], ...]] = {
    S2SArm.T16: (
        ("phi_w", (3, 4, 16)),
        ("psi_w", (3, 4, 16)),
        ("unary_w", (3, 2, 16)),
        ("pair_w", (3, 3, 2, 16)),
        ("q_w", (3, 2, 16)),
        ("out_b", (3, 2)),
    ),
    S2SArm.P_CAP18: (
        ("phi_w", (3, 4, 18)),
        ("psi_w", (3, 4, 18)),
        ("unary_w", (3, 2, 18)),
        ("pair_w", (3, 3, 2, 18)),
        ("out_b", (3, 2)),
    ),
    S2SArm.DS870: (
        ("eta_w", (3, 4, 4)),
        ("eta_b", (3, 4)),
        ("hidden1_w", (30, 14)),
        ("hidden1_b", (14,)),
        ("hidden2_w", (14, 22)),
        ("hidden2_b", (22,)),
        ("out_w", (22, 2)),
        ("out_b", (2,)),
    ),
}


def _coerce_arm(arm: S2SArm | str) -> S2SArm:
    try:
        return arm if type(arm) is S2SArm else S2SArm(arm)
    except (TypeError, ValueError) as exc:
        raise SWM0WS2SOperatorError(f"unsupported S2S arm: {arm!r}") from exc


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SWM0WS2SOperatorError("canonical JSON requires finite floats")
        return value
    if value is None or type(value) in (str, int, bool):
        return value
    raise SWM0WS2SOperatorError(f"unsupported canonical value: {type(value)!r}")


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
    """Compare immutable receipt trees without numeric or subclass aliases."""

    if type(left) is not type(right):
        return False
    if type(left) is tuple:
        return len(left) == len(right) and all(
            _exact_tree_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return bool(left == right)


def _require_sha256(value: object, name: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise SWM0WS2SOperatorError(f"{name} must be a lowercase SHA-256")


def _immutable_float64(value: np.ndarray) -> np.ndarray:
    """Return a C-order float64 array ultimately backed by immutable bytes."""

    if type(value) is not np.ndarray or value.dtype != np.dtype(np.float64):
        raise SWM0WS2SOperatorError("numeric tensors must be exact float64 ndarrays")
    contiguous = np.ascontiguousarray(value)
    frozen = np.frombuffer(contiguous.tobytes(order="C"), dtype=np.float64)
    return frozen.reshape(contiguous.shape)


def _snapshot_tensor(
    value: object,
    *,
    trailing_shape: tuple[int, ...],
    name: str,
) -> tuple[np.ndarray, bool]:
    if type(value) is not np.ndarray or value.dtype != np.dtype(np.float64):
        raise SWM0WS2SOperatorError(f"{name} must be an exact float64 ndarray")
    if value.shape == trailing_shape:
        single = True
    elif value.ndim == len(trailing_shape) + 1 and value.shape[1:] == trailing_shape:
        single = False
        if value.shape[0] == 0:
            raise SWM0WS2SOperatorError(f"{name} batch must be non-empty")
    else:
        raise SWM0WS2SOperatorError(
            f"{name} must have shape {trailing_shape!r} or (N, {trailing_shape!r})"
        )
    if not np.isfinite(value).all():
        raise SWM0WS2SOperatorError(f"{name} must contain only finite values")
    snapshot = _immutable_float64(value)
    return (snapshot[None, ...] if single else snapshot), single


def _finish_batch(value: np.ndarray, single: bool) -> np.ndarray:
    selected = value[0] if single else value
    return _immutable_float64(np.asarray(selected, dtype=np.float64))


def parameter_shapes(arm: S2SArm | str) -> Mapping[str, tuple[int, ...]]:
    selected = _coerce_arm(arm)
    return MappingProxyType(dict(_PARAMETER_SCHEMAS[selected]))


def parameter_count(arm: S2SArm | str) -> int:
    return sum(math.prod(shape) for shape in parameter_shapes(arm).values())


@dataclass(frozen=True, slots=True)
class OperationEstimate:
    """Exact algebraic census for one world and all six recipient outputs."""

    scalar_multiplications: int
    scalar_additions: int
    tanh_evaluations: int

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 0
            for value in (
                self.scalar_multiplications,
                self.scalar_additions,
                self.tanh_evaluations,
            )
        ):
            raise SWM0WS2SOperatorError("operation counts must be non-negative integers")

    @property
    def scalar_operation_proxy(self) -> int:
        return (
            self.scalar_multiplications
            + self.scalar_additions
            + self.tanh_evaluations
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "scope": (
                "EXACT_ALGEBRAIC_DAG_ONE_WORLD_SIX_RECIPIENTS_"
                "INCLUDES_BIAS_HEAD_AND_SET_SUM_ADDS_EXCLUDES_INDEXING"
            ),
            "scalar_additions": self.scalar_additions,
            "scalar_multiplications": self.scalar_multiplications,
            "scalar_operation_proxy": self.scalar_operation_proxy,
            "tanh_evaluations": self.tanh_evaluations,
        }


def _operation_estimate(arm: S2SArm) -> OperationEstimate:
    if arm is S2SArm.T16:
        # This implementation recomputes u*prod(v) for Q after forming pairs.
        return OperationEstimate(2_304, 1_584, 0)
    if arm is S2SArm.P_CAP18:
        return OperationEstimate(2_052, 1_566, 0)
    return OperationEstimate(4_728, 4_752, 240)


@dataclass(frozen=True, slots=True)
class ArchitectureReceipt:
    arm: S2SArm
    parameter_schema: tuple[tuple[str, tuple[int, ...]], ...]
    parameter_count: int
    operations: OperationEstimate
    compute_disclosure: str
    scientific_status: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.arm) is not S2SArm:
            raise SWM0WS2SOperatorError("architecture receipt requires an exact arm")
        if not _exact_tree_equal(
            self.parameter_schema, _PARAMETER_SCHEMAS[self.arm]
        ):
            raise SWM0WS2SOperatorError("architecture parameter schema drifted")
        if type(self.parameter_count) is not int or self.parameter_count != 870:
            raise SWM0WS2SOperatorError("every S2S arm must contain exactly 870 parameters")
        if (
            type(self.operations) is not OperationEstimate
            or self.operations != _operation_estimate(self.arm)
        ):
            raise SWM0WS2SOperatorError("architecture operation census drifted")
        expected_disclosure = {
            S2SArm.T16: "REFERENCE_COMPUTE_NOT_AN_EQUAL_COMPUTE_CLAIM",
            S2SArm.P_CAP18: "LOWER_PROXY_THAN_T16_MATCHED_PARAMETERS_ONLY",
            S2SArm.DS870: "HIGHER_COMPUTE_THAN_T16_MATCHED_PARAMETERS_ONLY",
        }[self.arm]
        if (
            type(self.compute_disclosure) is not str
            or self.compute_disclosure != expected_disclosure
        ):
            raise SWM0WS2SOperatorError("architecture compute disclosure drifted")
        if (
            type(self.scientific_status) is not str
            or self.scientific_status != SCIENTIFIC_STATUS
        ):
            raise SWM0WS2SOperatorError("architecture scientific status drifted")
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SOperatorError("architecture receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "arm": self.arm.value,
            "compute_disclosure": self.compute_disclosure,
            "operations": self.operations.canonical(),
            "parameter_count": self.parameter_count,
            "parameter_schema": [
                {"name": name, "shape": list(shape)}
                for name, shape in self.parameter_schema
            ],
            "schema_version": ARCHITECTURE_RECEIPT_VERSION,
            "scientific_status": self.scientific_status,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def architecture_receipt(arm: S2SArm | str) -> ArchitectureReceipt:
    selected = _coerce_arm(arm)
    disclosure = {
        S2SArm.T16: "REFERENCE_COMPUTE_NOT_AN_EQUAL_COMPUTE_CLAIM",
        S2SArm.P_CAP18: "LOWER_PROXY_THAN_T16_MATCHED_PARAMETERS_ONLY",
        S2SArm.DS870: "HIGHER_COMPUTE_THAN_T16_MATCHED_PARAMETERS_ONLY",
    }[selected]
    unsigned = {
        "arm": selected.value,
        "compute_disclosure": disclosure,
        "operations": _operation_estimate(selected).canonical(),
        "parameter_count": parameter_count(selected),
        "parameter_schema": [
            {"name": name, "shape": list(shape)}
            for name, shape in _PARAMETER_SCHEMAS[selected]
        ],
        "schema_version": ARCHITECTURE_RECEIPT_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
    }
    return ArchitectureReceipt(
        arm=selected,
        parameter_schema=_PARAMETER_SCHEMAS[selected],
        parameter_count=parameter_count(selected),
        operations=_operation_estimate(selected),
        compute_disclosure=disclosure,
        scientific_status=SCIENTIFIC_STATUS,
        receipt_sha256=canonical_sha256(unsigned),
    )


def _freeze_parameters(
    arm: S2SArm, parameters: Mapping[str, np.ndarray]
) -> Mapping[str, np.ndarray]:
    if not isinstance(parameters, Mapping):
        raise SWM0WS2SOperatorError("parameters must be a named mapping")
    expected = dict(_PARAMETER_SCHEMAS[arm])
    if set(parameters) != set(expected) or any(type(name) is not str for name in parameters):
        raise SWM0WS2SOperatorError("parameter names disagree with the exact arm schema")
    frozen: dict[str, np.ndarray] = {}
    for name, shape in _PARAMETER_SCHEMAS[arm]:
        value = parameters[name]
        if type(value) is not np.ndarray or value.dtype != np.dtype(np.float64):
            raise SWM0WS2SOperatorError(
                f"parameter {name!r} must be an exact float64 ndarray"
            )
        if value.shape != shape:
            raise SWM0WS2SOperatorError(
                f"parameter {name!r} must have exact shape {shape!r}"
            )
        if not np.isfinite(value).all():
            raise SWM0WS2SOperatorError(f"parameter {name!r} contains non-finite values")
        frozen[name] = _immutable_float64(value)
    return MappingProxyType(frozen)


def _tensor_sha256(value: np.ndarray) -> str:
    canonical = np.asarray(value, dtype="<f8", order="C")
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def _bound_tensor_sha256(value: np.ndarray) -> str:
    return canonical_sha256(
        {
            "bytes_sha256": _tensor_sha256(value),
            "dtype": "float64-le",
            "shape": list(value.shape),
        }
    )


def _parameter_sha256(parameters: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256(PARAMETER_HASH_DOMAIN)
    for name in sorted(parameters):
        value = parameters[name]
        descriptor = canonical_json(
            {"dtype": "float64-le", "name": name, "shape": list(value.shape)}
        ).encode("utf-8")
        digest.update(len(descriptor).to_bytes(8, "big"))
        digest.update(descriptor)
        canonical = np.asarray(value, dtype="<f8", order="C").tobytes(order="C")
        digest.update(len(canonical).to_bytes(8, "big"))
        digest.update(canonical)
    return digest.hexdigest()


EVALUATOR_FAMILY_SHA256 = canonical_sha256(
    {
        "factor_tables": [
            {"key": key, "values": list(values)}
            for key, values in FIXED_FACTOR_TABLES
        ],
        "family": "FIXED_V1_SET_FACTORIZED_RANK_2",
        "scope": "STRUCTURAL_FORMULA_BINDING_NOT_SEED_PROVENANCE",
        "target_scale_exponent": TARGET_SCALE_EXPONENT,
    }
)


@dataclass(frozen=True, slots=True)
class S2SOperator:
    arm: S2SArm
    parameters: Mapping[str, np.ndarray]
    origin: ParameterOrigin = ParameterOrigin.EXTERNAL_UNTRAINED
    initialization_seed: int | None = None
    intervention: str | None = None

    def __post_init__(self) -> None:
        if type(self.arm) is not S2SArm:
            raise SWM0WS2SOperatorError("operator arm must be an exact S2SArm")
        if type(self.origin) is not ParameterOrigin:
            raise SWM0WS2SOperatorError("operator origin must be exact ParameterOrigin")
        if self.origin is ParameterOrigin.DETERMINISTIC_INITIALIZATION:
            if type(self.initialization_seed) is not int or self.initialization_seed < 0:
                raise SWM0WS2SOperatorError("deterministic origin requires a non-negative seed")
        elif self.origin is ParameterOrigin.EVALUATOR_ONLY_CONSTRUCTIVE_Q_WITNESS:
            if self.arm is not S2SArm.T16 or self.initialization_seed is not None:
                raise SWM0WS2SOperatorError("constructive witness must be unseeded T16")
        elif self.initialization_seed is not None:
            raise SWM0WS2SOperatorError("external parameters may not claim an initialization seed")
        if self.intervention is not None and (
            type(self.intervention) is not str or self.intervention != "Q_REMOVED"
        ):
            raise SWM0WS2SOperatorError("unsupported frozen intervention")
        if self.intervention == "Q_REMOVED" and self.arm is not S2SArm.T16:
            raise SWM0WS2SOperatorError("only T16 has a removable Q head")
        frozen = _freeze_parameters(self.arm, self.parameters)
        if self.intervention == "Q_REMOVED":
            zeros = np.zeros((3, 2, 16), dtype=np.float64)
            if frozen["q_w"].tobytes(order="C") != zeros.tobytes(order="C"):
                raise SWM0WS2SOperatorError("removed Q head must be positive-zero bytes")
        if self.origin is not ParameterOrigin.EXTERNAL_UNTRAINED:
            expected = _origin_parameters(self.arm, self.origin, self.initialization_seed)
            for name, expected_value in expected.items():
                bound_value = (
                    np.zeros_like(expected_value)
                    if self.intervention == "Q_REMOVED" and name == "q_w"
                    else expected_value
                )
                if frozen[name].tobytes(order="C") != bound_value.tobytes(order="C"):
                    raise SWM0WS2SOperatorError(
                        f"parameter {name!r} contradicts its claimed origin"
                    )
        object.__setattr__(self, "parameters", frozen)

    @property
    def learned(self) -> bool:
        """No constructor in this module can assert learned status."""

        return False

    @property
    def parameter_count(self) -> int:
        return sum(int(value.size) for value in self.parameters.values())

    @property
    def parameters_sha256(self) -> str:
        return _parameter_sha256(self.parameters)

    @property
    def evaluator_family_sha256(self) -> str | None:
        """Bind the fixed formula, never an authenticated external seed/task."""

        return (
            EVALUATOR_FAMILY_SHA256
            if self.origin is ParameterOrigin.EVALUATOR_ONLY_CONSTRUCTIVE_Q_WITNESS
            else None
        )

    @property
    def state_sha256(self) -> str:
        return canonical_sha256(
            {
                "architecture_receipt_sha256": architecture_receipt(self.arm).receipt_sha256,
                "arm": self.arm.value,
                "evaluator_family_sha256": self.evaluator_family_sha256,
                "initialization_seed": self.initialization_seed,
                "intervention": self.intervention,
                "learned": False,
                "origin": self.origin.value,
                "parameters_sha256": self.parameters_sha256,
                "schema_version": OPERATOR_VERSION,
                "scientific_status": SCIENTIFIC_STATUS,
            }
        )

    def forward(self, presweep: np.ndarray) -> np.ndarray:
        return forward(self, presweep)

    def predict_world(self, world: ModelWorldV1) -> np.ndarray:
        return self.forward(compile_model_world(world))

    def operation_receipt(self) -> ArchitectureReceipt:
        return architecture_receipt(self.arm)


def _initial_tensor(
    name: str,
    shape: tuple[int, ...],
    *,
    seed: int,
) -> np.ndarray:
    if name.endswith("_b"):
        return np.zeros(shape, dtype=np.float64)
    material = canonical_sha256([INITIALIZATION_DOMAIN, seed, name, list(shape)])
    rng = np.random.Generator(np.random.PCG64(int(material[:16], 16)))
    if name in {"phi_w", "psi_w", "eta_w"}:
        fan_in, fan_out = shape[-2:]
    elif name in {"hidden1_w", "hidden2_w", "out_w"}:
        fan_in, fan_out = shape[-2:]
    else:
        fan_in, fan_out = shape[-1], OUTPUT_WIDTH
    limit = math.sqrt(6.0 / (fan_in + fan_out))
    return rng.uniform(-limit, limit, size=shape).astype(np.float64)


def _fixed_q_witness_parameters() -> dict[str, np.ndarray]:
    factors = dict(FIXED_FACTOR_TABLES)
    parameters = {
        name: np.zeros(shape, dtype=np.float64)
        for name, shape in _PARAMETER_SCHEMAS[S2SArm.T16]
    }
    scale = float(2**-TARGET_SCALE_EXPONENT)
    for role, channel, rank in itertools.product(range(3), range(2), range(2)):
        active = 2 * channel + rank
        p_table = factors[f"P:r{role}:c{channel}:k{rank}"]
        t_table = factors[f"T:r{role}:c{channel}:k{rank}"]
        parameters["phi_w"][role, :, active] = p_table[:4]
        parameters["psi_w"][role, :, active] = t_table[:4]
        parameters["q_w"][role, channel, active] = scale
    return parameters


def _origin_parameters(
    arm: S2SArm, origin: ParameterOrigin, seed: int | None
) -> dict[str, np.ndarray]:
    if origin is ParameterOrigin.DETERMINISTIC_INITIALIZATION:
        assert seed is not None
        return {
            name: _initial_tensor(name, shape, seed=seed)
            for name, shape in _PARAMETER_SCHEMAS[arm]
        }
    if origin is ParameterOrigin.EVALUATOR_ONLY_CONSTRUCTIVE_Q_WITNESS:
        return _fixed_q_witness_parameters()
    raise AssertionError("external parameters have no claimed deterministic origin")


def initialize_operator(arm: S2SArm | str, *, seed: int) -> S2SOperator:
    selected = _coerce_arm(arm)
    if type(seed) is not int or seed < 0:
        raise SWM0WS2SOperatorError("initialization seed must be a non-negative integer")
    parameters = _origin_parameters(
        selected, ParameterOrigin.DETERMINISTIC_INITIALIZATION, seed
    )
    return S2SOperator(
        selected,
        parameters,
        origin=ParameterOrigin.DETERMINISTIC_INITIALIZATION,
        initialization_seed=seed,
    )


def compile_model_world(world: ModelWorldV1) -> np.ndarray:
    if type(world) is not ModelWorldV1:
        raise SWM0WS2SOperatorError("compiler requires exact ModelWorldV1")
    values = np.asarray(
        [centered_contrasts(value) for value in world.raw_values],
        dtype=np.float64,
    ).reshape(ROLE_COUNT, MEMBER_COUNT, INPUT_WIDTH)
    return _immutable_float64(values)


def compile_model_worlds(worlds: Sequence[ModelWorldV1]) -> np.ndarray:
    if type(worlds) is not tuple or not worlds:
        raise SWM0WS2SOperatorError("world batch must be a non-empty immutable tuple")
    if any(type(world) is not ModelWorldV1 for world in worlds):
        raise SWM0WS2SOperatorError("world batch requires exact ModelWorldV1 entries")
    return _immutable_float64(
        np.stack([compile_model_world(world) for world in worlds], axis=0)
    )


def compile_case_targets(case: EvaluatorCaseV1) -> np.ndarray:
    if type(case) is not EvaluatorCaseV1:
        raise SWM0WS2SOperatorError("target compiler requires exact EvaluatorCaseV1")
    values = np.asarray(case.target_numerators, dtype=np.float64).reshape(3, 2, 2)
    values /= float(2**TARGET_SCALE_EXPONENT)
    return _immutable_float64(values)


def compile_case_target_batch(cases: Sequence[EvaluatorCaseV1]) -> np.ndarray:
    if type(cases) is not tuple or not cases:
        raise SWM0WS2SOperatorError("case batch must be a non-empty immutable tuple")
    if any(type(case) is not EvaluatorCaseV1 for case in cases):
        raise SWM0WS2SOperatorError("case batch requires exact EvaluatorCaseV1 entries")
    return _immutable_float64(
        np.stack([compile_case_targets(case) for case in cases], axis=0)
    )


def _t_or_p_forward(
    model: S2SOperator, x: np.ndarray
) -> np.ndarray:
    parameters = model.parameters
    u = np.einsum("nrmd,rdh->nrmh", x, parameters["phi_w"])
    encoded_sources = np.einsum("nrmd,rdh->nrmh", x, parameters["psi_w"])
    role_sums = encoded_sources.sum(axis=2)

    # v[n, recipient_role, recipient_member, source_role, hidden] is assembled
    # exclusively from the immutable presweep.  The diagonal uses the unique
    # co-member; off-diagonals use the complete source-role set.
    v = np.broadcast_to(
        role_sums[:, None, None, :, :],
        (len(x), ROLE_COUNT, MEMBER_COUNT, ROLE_COUNT, u.shape[-1]),
    ).copy()
    for role in range(ROLE_COUNT):
        v[:, role, 0, role, :] = encoded_sources[:, role, 1, :]
        v[:, role, 1, role, :] = encoded_sources[:, role, 0, :]

    prediction = np.einsum("nrmh,rch->nrmc", u, parameters["unary_w"])
    pair_features = u[:, :, :, None, :] * v
    prediction += np.einsum("nrmsh,rsch->nrmc", pair_features, parameters["pair_w"])
    if model.arm is S2SArm.T16:
        q_features = u * np.prod(v, axis=3)
        prediction += np.einsum("nrmh,rch->nrmc", q_features, parameters["q_w"])
    prediction += parameters["out_b"][None, :, None, :]
    return prediction


def _ds_decoder_inputs(model: S2SOperator, x: np.ndarray) -> np.ndarray:
    learned = np.tanh(
        np.einsum("nrmd,rdk->nrmk", x, model.parameters["eta_w"])
        + model.parameters["eta_b"][None, :, None, :]
    )
    eta = np.concatenate((x, learned), axis=-1)
    summaries = eta.sum(axis=2).reshape(len(x), 24)
    summary_fields = np.broadcast_to(
        summaries[:, None, None, :], (len(x), 3, 2, 24)
    )
    role_codes = np.broadcast_to(ROLE_CODES[None, :, None, :], (len(x), 3, 2, 2))
    return np.concatenate((x, summary_fields, role_codes), axis=-1)


def _ds_forward(model: S2SOperator, x: np.ndarray) -> np.ndarray:
    decoder_input = _ds_decoder_inputs(model, x)
    hidden1 = np.tanh(
        np.einsum("nrmf,fh->nrmh", decoder_input, model.parameters["hidden1_w"])
        + model.parameters["hidden1_b"]
    )
    hidden2 = np.tanh(
        np.einsum("nrmf,fh->nrmh", hidden1, model.parameters["hidden2_w"])
        + model.parameters["hidden2_b"]
    )
    return (
        np.einsum("nrmh,hc->nrmc", hidden2, model.parameters["out_w"])
        + model.parameters["out_b"]
    )


def forward(model: S2SOperator, presweep: np.ndarray) -> np.ndarray:
    if type(model) is not S2SOperator:
        raise SWM0WS2SOperatorError("forward requires exact S2SOperator")
    x, single = _snapshot_tensor(
        presweep, trailing_shape=(3, 2, 4), name="presweep"
    )
    prediction = (
        _ds_forward(model, x)
        if model.arm is S2SArm.DS870
        else _t_or_p_forward(model, x)
    )
    if prediction.shape != (len(x), 3, 2, 2) or not np.isfinite(prediction).all():
        raise SWM0WS2SOperatorError("forward produced an invalid postsweep tensor")
    return _finish_batch(prediction, single)


def ds_fixed_recipient_representation(presweep: np.ndarray) -> np.ndarray:
    """Return the fixed 18-vector embedded in every DS870 decoder input.

    ``[recipient contrast; three role-wise fixed contrast sums; role code]`` is
    injective on the recipient-marked ``S2^3`` quotient for two Z5 members per
    role.  The learned four-vector half of each role summary can add features
    but cannot erase this fixed representation.
    """

    x, single = _snapshot_tensor(
        presweep, trailing_shape=(3, 2, 4), name="presweep"
    )
    summaries = x.sum(axis=2).reshape(len(x), 12)
    summary_fields = np.broadcast_to(
        summaries[:, None, None, :], (len(x), 3, 2, 12)
    )
    role_codes = np.broadcast_to(ROLE_CODES[None, :, None, :], (len(x), 3, 2, 2))
    representation = np.concatenate((x, summary_fields, role_codes), axis=-1)
    return _finish_batch(representation, single)


def construct_q_witness(task: TaskSpecV1) -> S2SOperator:
    """Construct the evaluator-only, nonlearned exact Q witness for fixed v1."""

    if type(task) is not TaskSpecV1:
        raise SWM0WS2SOperatorError("Q witness requires exact TaskSpecV1")
    parameters = _fixed_q_witness_parameters()
    return S2SOperator(
        S2SArm.T16,
        parameters,
        origin=ParameterOrigin.EVALUATOR_ONLY_CONSTRUCTIVE_Q_WITNESS,
    )


@dataclass(frozen=True, slots=True)
class QRemovalReceipt:
    base_state_sha256: str
    ablated_state_sha256: str
    removed_values_hex: tuple[str, ...]
    removed_bytes_sha256: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "base_state_sha256",
            "ablated_state_sha256",
            "removed_bytes_sha256",
            "receipt_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        if type(self.removed_values_hex) is not tuple or len(self.removed_values_hex) != 96:
            raise SWM0WS2SOperatorError("Q receipt must contain exactly 96 values")
        try:
            values = np.asarray(
                [float.fromhex(value) for value in self.removed_values_hex],
                dtype=np.float64,
            )
        except (TypeError, ValueError) as exc:
            raise SWM0WS2SOperatorError("Q receipt contains an invalid float") from exc
        if any(
            type(encoded) is not str or float.fromhex(encoded).hex() != encoded
            for encoded in self.removed_values_hex
        ) or not np.isfinite(values).all():
            raise SWM0WS2SOperatorError("Q receipt requires canonical finite float hex")
        if _tensor_sha256(values.reshape(3, 2, 16)) != self.removed_bytes_sha256:
            raise SWM0WS2SOperatorError("Q receipt byte digest mismatch")
        if self.base_state_sha256 == self.ablated_state_sha256:
            raise SWM0WS2SOperatorError("Q removal must change the bound state")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SOperatorError("Q removal receipt hash mismatch")

    @property
    def removed_value_count(self) -> int:
        return len(self.removed_values_hex)

    def unsigned(self) -> dict[str, Any]:
        return {
            "ablated_state_sha256": self.ablated_state_sha256,
            "base_state_sha256": self.base_state_sha256,
            "intervention": "FROZEN_Q_REMOVE_EXACT_RESTORE",
            "removed_bytes_sha256": self.removed_bytes_sha256,
            "removed_values_hex": list(self.removed_values_hex),
            "schema_version": Q_REMOVAL_RECEIPT_VERSION,
            "value_count": 96,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def remove_q(model: S2SOperator) -> tuple[S2SOperator, QRemovalReceipt]:
    if type(model) is not S2SOperator or model.arm is not S2SArm.T16:
        raise SWM0WS2SOperatorError("Q removal requires exact T16 operator")
    if model.intervention is not None:
        raise SWM0WS2SOperatorError("operator already carries an intervention")
    removed = model.parameters["q_w"]
    parameters = {name: value.copy() for name, value in model.parameters.items()}
    parameters["q_w"] = np.zeros((3, 2, 16), dtype=np.float64)
    ablated = replace(model, parameters=parameters, intervention="Q_REMOVED")
    values_hex = tuple(float(value).hex() for value in removed.reshape(-1))
    unsigned = {
        "ablated_state_sha256": ablated.state_sha256,
        "base_state_sha256": model.state_sha256,
        "intervention": "FROZEN_Q_REMOVE_EXACT_RESTORE",
        "removed_bytes_sha256": _tensor_sha256(removed),
        "removed_values_hex": list(values_hex),
        "schema_version": Q_REMOVAL_RECEIPT_VERSION,
        "value_count": 96,
    }
    return ablated, QRemovalReceipt(
        base_state_sha256=model.state_sha256,
        ablated_state_sha256=ablated.state_sha256,
        removed_values_hex=values_hex,
        removed_bytes_sha256=_tensor_sha256(removed),
        receipt_sha256=canonical_sha256(unsigned),
    )


def restore_q(model: S2SOperator, receipt: QRemovalReceipt) -> S2SOperator:
    if type(model) is not S2SOperator or type(receipt) is not QRemovalReceipt:
        raise SWM0WS2SOperatorError("Q restoration requires exact model and receipt")
    if (
        model.arm is not S2SArm.T16
        or model.intervention != "Q_REMOVED"
        or model.state_sha256 != receipt.ablated_state_sha256
    ):
        raise SWM0WS2SOperatorError("Q receipt does not bind this ablated model")
    zeros = np.zeros((3, 2, 16), dtype=np.float64)
    if model.parameters["q_w"].tobytes(order="C") != zeros.tobytes(order="C"):
        raise SWM0WS2SOperatorError("ablated Q head is not exact positive-zero bytes")
    restored_q = np.asarray(
        [float.fromhex(value) for value in receipt.removed_values_hex],
        dtype=np.float64,
    ).reshape(3, 2, 16)
    if _tensor_sha256(restored_q) != receipt.removed_bytes_sha256:
        raise SWM0WS2SOperatorError("restored Q bytes disagree with receipt")
    parameters = {name: value.copy() for name, value in model.parameters.items()}
    parameters["q_w"] = restored_q
    restored = replace(model, parameters=parameters, intervention=None)
    if restored.state_sha256 != receipt.base_state_sha256:
        raise SWM0WS2SOperatorError("Q restoration is not byte exact")
    return restored


def within_role_broadcast(predictions: np.ndarray) -> np.ndarray:
    values, single = _snapshot_tensor(
        predictions, trailing_shape=(3, 2, 2), name="predictions"
    )
    pooled = 0.5 * values[:, :, :1, :] + 0.5 * values[:, :, 1:, :]
    broadcast = np.broadcast_to(pooled, values.shape).copy()
    if not np.isfinite(broadcast).all():
        raise SWM0WS2SOperatorError("broadcast produced non-finite values")
    return _finish_batch(broadcast, single)


def _require_role_cycle(cycle: object) -> tuple[int, int, int]:
    if (
        type(cycle) is not tuple
        or len(cycle) != 3
        or any(type(value) is not int for value in cycle)
        or tuple(sorted(cycle)) != (0, 1, 2)
        or cycle not in ROLE_CYCLES
    ):
        raise SWM0WS2SOperatorError("cycle must be one of the two registered role cycles")
    return cycle


def apply_physical_role_cycle(
    presweep: np.ndarray, cycle: tuple[int, int, int]
) -> np.ndarray:
    selected = _require_role_cycle(cycle)
    values, single = _snapshot_tensor(
        presweep, trailing_shape=(3, 2, 4), name="presweep"
    )
    moved = np.empty_like(values)
    for source, destination in enumerate(selected):
        moved[:, destination, :, :] = values[:, source, :, :]
    return _finish_batch(moved, single)


def inverse_map_role_cycle_outputs(
    predictions: np.ndarray, cycle: tuple[int, int, int]
) -> np.ndarray:
    selected = _require_role_cycle(cycle)
    values, single = _snapshot_tensor(
        predictions, trailing_shape=(3, 2, 2), name="predictions"
    )
    restored = np.empty_like(values)
    for source, destination in enumerate(selected):
        restored[:, source, :, :] = values[:, destination, :, :]
    return _finish_batch(restored, single)


def evaluate_both_role_cycles(
    model: S2SOperator, presweep: np.ndarray
) -> tuple[tuple[tuple[int, int, int], np.ndarray], ...]:
    if type(model) is not S2SOperator:
        raise SWM0WS2SOperatorError("role-cycle evaluation requires exact S2SOperator")
    return tuple(
        (
            cycle,
            inverse_map_role_cycle_outputs(
                model.forward(apply_physical_role_cycle(presweep, cycle)), cycle
            ),
        )
        for cycle in ROLE_CYCLES
    )


@dataclass(frozen=True, slots=True)
class StratifiedR2:
    values: tuple[tuple[float, float], ...]
    worst_role: str
    worst_channel: str
    worst_r2: float
    world_count: int
    predictions_sha256: str
    targets_sha256: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.values) is not tuple
            or len(self.values) != 3
            or any(type(row) is not tuple or len(row) != 2 for row in self.values)
            or any(
                type(value) is not float or not math.isfinite(value)
                for row in self.values
                for value in row
            )
        ):
            raise SWM0WS2SOperatorError("R2 values must be a finite immutable 3x2 matrix")
        if type(self.world_count) is not int or self.world_count <= 0:
            raise SWM0WS2SOperatorError("R2 world count must be positive")
        if type(self.worst_role) is not str or type(self.worst_channel) is not str:
            raise SWM0WS2SOperatorError("R2 worst-stratum labels must be exact strings")
        if type(self.worst_r2) is not float or not math.isfinite(self.worst_r2):
            raise SWM0WS2SOperatorError("R2 worst value must be an exact finite float")
        _require_sha256(self.predictions_sha256, "predictions_sha256")
        _require_sha256(self.targets_sha256, "targets_sha256")
        flat = [
            (self.values[role][channel], role, channel)
            for role in range(3)
            for channel in range(2)
        ]
        value, role, channel = min(flat, key=lambda item: (item[0], item[1], item[2]))
        if (
            self.worst_role != ROLES[role]
            or self.worst_channel != CHANNELS[channel]
            or self.worst_r2 != value
        ):
            raise SWM0WS2SOperatorError("R2 worst-stratum fields disagree")
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SOperatorError("R2 receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "claim_boundary": "DIAGNOSTIC_ONLY_NO_EFFICACY_VERDICT",
            "r2_by_role_channel": {
                ROLES[role]: {
                    CHANNELS[channel]: self.values[role][channel]
                    for channel in range(2)
                }
                for role in range(3)
            },
            "predictions_sha256": self.predictions_sha256,
            "schema_version": R2_RECEIPT_VERSION,
            "scientific_status": SCIENTIFIC_STATUS,
            "targets_sha256": self.targets_sha256,
            "worst_channel": self.worst_channel,
            "worst_r2": self.worst_r2,
            "worst_role": self.worst_role,
            "world_count": self.world_count,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def stratified_r2(predictions: np.ndarray, targets: np.ndarray) -> StratifiedR2:
    predicted, predicted_single = _snapshot_tensor(
        predictions, trailing_shape=(3, 2, 2), name="predictions"
    )
    truth, truth_single = _snapshot_tensor(
        targets, trailing_shape=(3, 2, 2), name="targets"
    )
    if predicted_single != truth_single or predicted.shape != truth.shape:
        raise SWM0WS2SOperatorError("prediction and target batches must match exactly")
    values: list[tuple[float, float]] = []
    for role in range(3):
        row = []
        for channel in range(2):
            observed = truth[:, role, :, channel].reshape(-1)
            estimate = predicted[:, role, :, channel].reshape(-1)
            centered = observed - observed.mean()
            denominator = float(np.dot(centered, centered))
            if not math.isfinite(denominator) or denominator <= 0.0:
                raise SWM0WS2SOperatorError("every role/channel target must have positive variance")
            residual = observed - estimate
            numerator = float(np.dot(residual, residual))
            score = float(1.0 - numerator / denominator)
            if not math.isfinite(score):
                raise SWM0WS2SOperatorError("R2 must be finite")
            row.append(score)
        values.append(tuple(row))
    immutable_values = tuple(values)
    flat = [
        (immutable_values[role][channel], role, channel)
        for role in range(3)
        for channel in range(2)
    ]
    worst, worst_role, worst_channel = min(
        flat, key=lambda item: (item[0], item[1], item[2])
    )
    unsigned = {
        "claim_boundary": "DIAGNOSTIC_ONLY_NO_EFFICACY_VERDICT",
        "r2_by_role_channel": {
            ROLES[role]: {
                CHANNELS[channel]: immutable_values[role][channel]
                for channel in range(2)
            }
            for role in range(3)
        },
        "predictions_sha256": _bound_tensor_sha256(predicted),
        "schema_version": R2_RECEIPT_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "targets_sha256": _bound_tensor_sha256(truth),
        "worst_channel": CHANNELS[worst_channel],
        "worst_r2": worst,
        "worst_role": ROLES[worst_role],
        "world_count": len(predicted),
    }
    return StratifiedR2(
        values=immutable_values,
        worst_role=ROLES[worst_role],
        worst_channel=CHANNELS[worst_channel],
        worst_r2=worst,
        world_count=len(predicted),
        predictions_sha256=unsigned["predictions_sha256"],
        targets_sha256=unsigned["targets_sha256"],
        receipt_sha256=canonical_sha256(unsigned),
    )


__all__ = [
    "ALL_ARMS",
    "ARCHITECTURE_RECEIPT_VERSION",
    "ArchitectureReceipt",
    "EVALUATOR_FAMILY_SHA256",
    "INITIALIZATION_DOMAIN",
    "OPERATOR_VERSION",
    "OperationEstimate",
    "ParameterOrigin",
    "QRemovalReceipt",
    "ROLE_CODES",
    "S2SArm",
    "SCIENTIFIC_STATUS",
    "SWM0WS2SOperatorError",
    "S2SOperator",
    "StratifiedR2",
    "apply_physical_role_cycle",
    "architecture_receipt",
    "canonical_json",
    "canonical_sha256",
    "compile_case_target_batch",
    "compile_case_targets",
    "compile_model_world",
    "compile_model_worlds",
    "construct_q_witness",
    "ds_fixed_recipient_representation",
    "evaluate_both_role_cycles",
    "forward",
    "initialize_operator",
    "inverse_map_role_cycle_outputs",
    "parameter_count",
    "parameter_shapes",
    "remove_q",
    "restore_q",
    "stratified_r2",
    "within_role_broadcast",
]
