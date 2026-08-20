"""Fail-closed diagnostic and confirmatory protocol for the SWM-0W scalar gate.

The protocol intentionally has a small scientific surface:

* one task is built, fitted, evaluated, reduced to a receipt, then released;
* the model receives label-free ``ModelWorldV1`` objects at test time;
* all nine registered arms share one task-UID-derived optimizer seed;
* the T16 model undergoes all seven equal-width head removals and exact restores;
* twenty task receipts are reduced with one shared, frozen task bootstrap.

This module is evaluation machinery, not evidence.  It emits diagnostic or
candidate outcomes only.  The separate final-bundle authority must revalidate
chronology, source, seeds, tasks, and reduction before mapping a candidate to
PASS, KILL, or INCONCLUSIVE.  This module never makes that mapping.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

import numpy as np

from hswm.experiments.swm0w_operator import (
    InteractionHeadV1,
    LearnedSWM0WOperator,
    SWM0WArm,
    TrainingConfig,
    assert_typed_star_parity,
    canonical_json,
    canonical_sha256,
    fit_operator,
    remove_interaction_head,
    restore_interaction_head,
)
from hswm.experiments.swm0w_task_family import (
    MINIMUM_SEED_BYTES,
    StreamedTaskV1,
    build_task_from_external_seed,
    evaluator_cases_from_split,
    model_worlds_from_split,
    score_task_predictions,
)
from hswm.experiments.swm0w_worlds import ModelWorldV1, ROLES, RoleInputV1, SPLITS


PROTOCOL_VERSION = "hswm-swm0w-protocol/v2"
TASK_RECEIPT_SCHEMA = "hswm-swm0w-protocol-task-receipt/v2"
FINAL_RECEIPT_SCHEMA = "hswm-swm0w-protocol-final-receipt/v2"
ADMISSION_RECEIPT_SCHEMA = "hswm-swm0w-external-admission/v1"
ARM_RESULT_SCHEMA = "hswm-swm0w-protocol-arm-result/v1"
HEAD_RESULT_SCHEMA = "hswm-swm0w-protocol-head-result/v1"
EXACT_VARIANCE_SCHEMA = "hswm-swm0w-exact-test-variance/v1"
ORDERED_TASK_SEEDS_SCHEMA = "hswm-swm0w-ordered-task-seeds/v1"
OPTIMIZER_SEED_DOMAIN = b"hswm-swm0w-optimizer-seed/v1"
OPTIMIZER_SEED_RULE = (
    "UINT64_BE_SHA256(ASCII('hswm-swm0w-optimizer-seed/v1')+NUL+TASK_UID)[:8]"
)
ROLE_CYCLE_RULE = "R0_GETS_R1_R1_GETS_R2_R2_GETS_R0"
TASK_COUNT = 20
TEST_CASE_COUNT = 5_000
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20_260_820
BOOTSTRAP_QUANTILES = (0.05, 0.95)
_TASK_UID_RE = re.compile(r"^swm0wt_([0-9a-f]{24})$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_EXPERIMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class SWM0WProtocolError(ValueError):
    """Raised when protocol inputs or content-addressed artifacts drift."""


class RunMode(str, Enum):
    DIAGNOSTIC = "DIAGNOSTIC"
    CONFIRMATORY = "CONFIRMATORY"


class ProtocolOutcome(str, Enum):
    CANDIDATE_PASS_AWAITING_BUNDLE = "CANDIDATE_PASS_AWAITING_BUNDLE"
    CANDIDATE_KILL_AWAITING_BUNDLE = "CANDIDATE_KILL_AWAITING_BUNDLE"
    CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE = (
        "CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE"
    )
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    VOID = "VOID"


def _require_sha256(value: str, field: str) -> None:
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise SWM0WProtocolError(f"{field} must be a lowercase SHA-256")


def _finite(value: float, field: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise SWM0WProtocolError(f"{field} must be an exact finite float")
    return value


def _float_hex(value: float, field: str) -> str:
    return _finite(value, field).hex()


def _same_float(left: float, right: float) -> bool:
    return type(left) is float and type(right) is float and left.hex() == right.hex()


def _require_exact_json_tree(value: Any, field: str) -> None:
    """Reject Python aliases that JSON decoding itself cannot produce.

    In particular, ``bool`` is an ``int`` subclass and string enums are
    ``str`` subclasses.  Equality-based contract checks must not silently
    normalize either into a different canonical receipt.
    """

    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                raise SWM0WProtocolError(f"{field} JSON object keys must be exact strings")
            _require_exact_json_tree(item, f"{field}.{key}")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _require_exact_json_tree(item, f"{field}[{index}]")
        return
    if value is None or type(value) in {str, int, bool}:
        return
    if type(value) is float and math.isfinite(value):
        return
    raise SWM0WProtocolError(f"{field} contains a non-JSON or aliased primitive")


def _coerce_mode(value: RunMode | str) -> RunMode:
    try:
        return value if type(value) is RunMode else RunMode(value)
    except (TypeError, ValueError) as exc:
        raise SWM0WProtocolError(f"unsupported run mode: {value!r}") from exc


@dataclass(frozen=True, slots=True)
class ArmSpec:
    spec_id: str
    arm: SWM0WArm
    width: int
    family: str

    def __post_init__(self) -> None:
        if type(self.spec_id) is not str or not re.fullmatch(
            r"(?:[TPARFD]16|P17-cap|A21-cap|R64-cap)", self.spec_id
        ):
            raise SWM0WProtocolError("invalid arm-spec id")
        if type(self.arm) is not SWM0WArm:
            raise SWM0WProtocolError("arm spec requires an exact SWM0WArm")
        if type(self.width) is not int or self.width <= 0:
            raise SWM0WProtocolError("arm-spec width must be positive")
        if type(self.family) is not str or self.family not in {
            "TARGET", "LOWER_ORDER", "COMPLETE", "CAPACITY"
        }:
            raise SWM0WProtocolError("invalid arm-spec family")

    def canonical(self) -> dict[str, Any]:
        return {
            "arm": self.arm.value,
            "family": self.family,
            "spec_id": self.spec_id,
            "width": self.width,
        }


ARM_SPECS = (
    ArmSpec("T16", SWM0WArm.ROLE_TRIPLE, 16, "TARGET"),
    ArmSpec("P16", SWM0WArm.LOWER_ORDER_PAIR, 16, "LOWER_ORDER"),
    ArmSpec("A16", SWM0WArm.ADDITIVE, 16, "LOWER_ORDER"),
    ArmSpec("R16", SWM0WArm.ROLELESS, 16, "LOWER_ORDER"),
    ArmSpec("F16", SWM0WArm.FLAT_MLP, 16, "COMPLETE"),
    ArmSpec("D16", SWM0WArm.ROLE_AWARE_DEEPSETS, 16, "COMPLETE"),
    ArmSpec("P17-cap", SWM0WArm.LOWER_ORDER_PAIR, 17, "CAPACITY"),
    ArmSpec("A21-cap", SWM0WArm.ADDITIVE, 21, "CAPACITY"),
    ArmSpec("R64-cap", SWM0WArm.ROLELESS, 64, "CAPACITY"),
)
_SPECS_BY_ID = {spec.spec_id: spec for spec in ARM_SPECS}
if len(_SPECS_BY_ID) != 9:
    raise RuntimeError("SWM-0W protocol arm registry is not exactly nine unique specs")


HEAD_SPECS = (
    InteractionHeadV1((ROLES[0],)),
    InteractionHeadV1((ROLES[1],)),
    InteractionHeadV1((ROLES[2],)),
    InteractionHeadV1((ROLES[0], ROLES[1])),
    InteractionHeadV1((ROLES[0], ROLES[2])),
    InteractionHeadV1((ROLES[1], ROLES[2])),
    InteractionHeadV1(ROLES),
)


@dataclass(frozen=True, slots=True)
class OptimizerTemplate:
    epochs: int = 300
    batch_size: int = 256
    learning_rate: float = 0.01
    beta1: float = 0.9
    beta2: float = 0.999
    epsilon: float = 1.0e-8
    gradient_clip: float = 5.0
    patience: int = 25
    min_delta: float = 1.0e-9

    def __post_init__(self) -> None:
        if any(
            type(getattr(self, name)) is not int
            for name in ("epochs", "batch_size", "patience")
        ):
            raise SWM0WProtocolError("optimizer counts must be exact integers")
        if any(
            type(getattr(self, name)) is not float
            for name in (
                "learning_rate",
                "beta1",
                "beta2",
                "epsilon",
                "gradient_clip",
                "min_delta",
            )
        ):
            raise SWM0WProtocolError("optimizer numeric settings must be exact floats")
        # Reuse the operator's public validator without assigning scientific
        # meaning to the dummy width/seed.
        TrainingConfig(
            width=1,
            seed=0,
            epochs=self.epochs,
            batch_size=self.batch_size,
            learning_rate=self.learning_rate,
            beta1=self.beta1,
            beta2=self.beta2,
            epsilon=self.epsilon,
            gradient_clip=self.gradient_clip,
            patience=self.patience,
            min_delta=self.min_delta,
        )

    def config(self, spec: ArmSpec, task_uid: str) -> TrainingConfig:
        return TrainingConfig(
            width=spec.width,
            seed=optimizer_seed_from_task_uid(task_uid),
            epochs=self.epochs,
            batch_size=self.batch_size,
            learning_rate=self.learning_rate,
            beta1=self.beta1,
            beta2=self.beta2,
            epsilon=self.epsilon,
            gradient_clip=self.gradient_clip,
            patience=self.patience,
            min_delta=self.min_delta,
        )

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
        }


CONFIRMATORY_OPTIMIZER = OptimizerTemplate()


@dataclass(frozen=True, slots=True)
class Thresholds:
    q: float = 0.80
    l: float = 0.10
    c: float = -0.02
    h: float = 0.10
    s: float = 0.0
    r: float = 0.10
    k_phrase: float = 0.10

    def __post_init__(self) -> None:
        for field in ("q", "l", "c", "h", "s", "r", "k_phrase"):
            _finite(getattr(self, field), field)

    def canonical(self) -> dict[str, str]:
        return {name: getattr(self, name).hex() for name in ("q", "l", "c", "h", "s", "r", "k_phrase")}


# Proposed values live in one replaceable object until an external
# preregistration binds them.  A caller may pass another validated Thresholds
# object to diagnostic reduction; the final receipt always content-binds it.
CONFIRMATORY_THRESHOLDS = Thresholds()


@dataclass(frozen=True, slots=True)
class ConfirmatoryAdmissionV1:
    """Structural link to external operational checks, not authentication.

    A self-hash proves internal consistency only.  It does not prove GitHub
    chronology or make a scientific verdict admissible.  The final-bundle
    authority must independently revalidate every referenced artifact.
    """

    experiment_id: str
    registration_core_sha256: str
    protocol_contract_sha256: str
    commitment_sha256: str
    preregistration_sha256: str
    prereg_file_sha256: str
    source_commit_a: str
    registration_commit_b: str
    workflow_sha256: str
    github_chronology_receipt_sha256: str
    future_round: int
    task_seed_binding_sha256: str
    admission_status: str
    validated: bool
    receipt_sha256: str

    def __post_init__(self) -> None:
        for field in (
            "registration_core_sha256",
            "protocol_contract_sha256",
            "commitment_sha256",
            "preregistration_sha256",
            "prereg_file_sha256",
            "workflow_sha256",
            "github_chronology_receipt_sha256",
            "task_seed_binding_sha256",
            "receipt_sha256",
        ):
            _require_sha256(getattr(self, field), field)
        if type(self.experiment_id) is not str or not _EXPERIMENT_ID_RE.fullmatch(
            self.experiment_id
        ):
            raise SWM0WProtocolError("invalid admission experiment id")
        for field in ("source_commit_a", "registration_commit_b"):
            if type(getattr(self, field)) is not str or not _GIT_SHA1_RE.fullmatch(
                getattr(self, field)
            ):
                raise SWM0WProtocolError(f"{field} must be lowercase Git SHA-1")
        if self.source_commit_a == self.registration_commit_b:
            raise SWM0WProtocolError("registration must be a distinct later commit")
        if type(self.future_round) is not int or self.future_round < 1:
            raise SWM0WProtocolError("external admission future round must be positive")
        if (
            type(self.admission_status) is not str
            or self.admission_status != "GITHUB_OPERATIONAL_CHRONOLOGY_OBSERVED"
        ):
            raise SWM0WProtocolError("external admission status drift")
        if self.validated is not True:
            raise SWM0WProtocolError("external admission must be explicitly validated")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WProtocolError("external admission receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "admission_status": self.admission_status,
            "commitment_sha256": self.commitment_sha256,
            "experiment_id": self.experiment_id,
            "future_round": self.future_round,
            "github_chronology_receipt_sha256": self.github_chronology_receipt_sha256,
            "preregistration_sha256": self.preregistration_sha256,
            "prereg_file_sha256": self.prereg_file_sha256,
            "registration_commit_b": self.registration_commit_b,
            "registration_core_sha256": self.registration_core_sha256,
            "protocol_contract_sha256": self.protocol_contract_sha256,
            "schema_version": ADMISSION_RECEIPT_SCHEMA,
            "source_commit_a": self.source_commit_a,
            "task_seed_binding_sha256": self.task_seed_binding_sha256,
            "validated": self.validated,
            "workflow_sha256": self.workflow_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def validate_admission_receipt(value: Mapping[str, Any]) -> ConfirmatoryAdmissionV1:
    """Parse the exact public output of the external chronology validator."""

    if not isinstance(value, Mapping):
        raise SWM0WProtocolError("external admission must be a mapping")
    _require_exact_json_tree(value, "external_admission")
    expected = {
        "admission_status",
        "commitment_sha256",
        "experiment_id",
        "future_round",
        "github_chronology_receipt_sha256",
        "preregistration_sha256",
        "prereg_file_sha256",
        "protocol_contract_sha256",
        "receipt_sha256",
        "registration_commit_b",
        "registration_core_sha256",
        "schema_version",
        "source_commit_a",
        "task_seed_binding_sha256",
        "validated",
        "workflow_sha256",
    }
    if set(value) != expected:
        raise SWM0WProtocolError("external admission field set drift")
    if value["schema_version"] != ADMISSION_RECEIPT_SCHEMA:
        raise SWM0WProtocolError("external admission schema drift")
    result = ConfirmatoryAdmissionV1(
        experiment_id=value["experiment_id"],
        registration_core_sha256=value["registration_core_sha256"],
        protocol_contract_sha256=value["protocol_contract_sha256"],
        commitment_sha256=value["commitment_sha256"],
        preregistration_sha256=value["preregistration_sha256"],
        prereg_file_sha256=value["prereg_file_sha256"],
        source_commit_a=value["source_commit_a"],
        registration_commit_b=value["registration_commit_b"],
        workflow_sha256=value["workflow_sha256"],
        github_chronology_receipt_sha256=value[
            "github_chronology_receipt_sha256"
        ],
        future_round=value["future_round"],
        task_seed_binding_sha256=value["task_seed_binding_sha256"],
        admission_status=value["admission_status"],
        validated=value["validated"],
        receipt_sha256=value["receipt_sha256"],
    )
    if canonical_json(value) != canonical_json(result.canonical()):
        raise SWM0WProtocolError(
            "external admission is not exact canonical JSON representation"
        )
    return result


@dataclass(frozen=True, slots=True)
class ExactTestVariance:
    case_count: int
    target_integer_sum: int
    target_integer_sum_of_squares: int
    target_scale_exponent: int

    def __post_init__(self) -> None:
        for name in (
            "case_count",
            "target_integer_sum",
            "target_integer_sum_of_squares",
            "target_scale_exponent",
        ):
            if type(getattr(self, name)) is not int:
                raise SWM0WProtocolError("exact variance components must be integers")
        if self.case_count <= 1 or self.target_scale_exponent <= 0:
            raise SWM0WProtocolError("exact test variance requires a nontrivial test split")
        if self.centered_numerator <= 0:
            raise SWM0WProtocolError("exact test variance must be positive")

    @property
    def centered_numerator(self) -> int:
        return (
            self.case_count * self.target_integer_sum_of_squares
            - self.target_integer_sum * self.target_integer_sum
        )

    @property
    def population_variance(self) -> float:
        value = math.ldexp(
            self.centered_numerator / (self.case_count * self.case_count),
            -2 * self.target_scale_exponent,
        )
        if not math.isfinite(value) or value <= 0.0:
            raise SWM0WProtocolError("exact variance cannot be represented as a positive float")
        return value

    def canonical(self) -> dict[str, Any]:
        return {
            "case_count": self.case_count,
            "centered_numerator": self.centered_numerator,
            "population_variance_hex": self.population_variance.hex(),
            "rational_denominator_before_dyadic_scale": self.case_count**2,
            "schema_version": EXACT_VARIANCE_SCHEMA,
            "target_integer_sum": self.target_integer_sum,
            "target_integer_sum_of_squares": self.target_integer_sum_of_squares,
            "target_scale_exponent": self.target_scale_exponent,
        }


def exact_test_variance(task: StreamedTaskV1) -> ExactTestVariance:
    if type(task) is not StreamedTaskV1:
        raise SWM0WProtocolError("exact variance requires an exact StreamedTaskV1")
    split = task.for_split("test")
    return ExactTestVariance(
        case_count=len(split.cases),
        target_integer_sum=split.target_integer_sum,
        target_integer_sum_of_squares=split.target_integer_sum_of_squares,
        target_scale_exponent=task.target_parameters.scale_exponent,
    )


def optimizer_seed_from_task_uid(task_uid: str) -> int:
    match = _TASK_UID_RE.fullmatch(task_uid) if type(task_uid) is str else None
    if match is None:
        raise SWM0WProtocolError("optimizer seed requires an exact task uid")
    digest = hashlib.sha256(
        OPTIMIZER_SEED_DOMAIN + b"\x00" + task_uid.encode("ascii")
    ).digest()
    return int.from_bytes(digest[:8], "big")


def _ordered_task_seed_hash_binding_sha256(seed_hashes: Sequence[str]) -> str:
    if len(seed_hashes) != TASK_COUNT:
        raise SWM0WProtocolError("ordered seed binding requires exactly 20 seeds")
    for index, digest in enumerate(seed_hashes):
        _require_sha256(digest, f"task_seed_sha256[{index}]")
    if len(set(seed_hashes)) != TASK_COUNT:
        raise SWM0WProtocolError("ordered seed binding requires unique seeds")
    return canonical_sha256(
        {
            "ordered_seed_sha256": [
                {"index": index, "seed_sha256": digest}
                for index, digest in enumerate(seed_hashes)
            ],
            "schema_version": ORDERED_TASK_SEEDS_SCHEMA,
            "task_count": TASK_COUNT,
        }
    )


def ordered_task_seed_binding_sha256(seeds: Sequence[bytes]) -> str:
    """Bind the exact ordered twenty 32-byte seeds used by the protocol."""

    if len(seeds) != TASK_COUNT or any(
        type(seed) is not bytes or len(seed) != 32 for seed in seeds
    ):
        raise SWM0WProtocolError(
            "ordered seed binding requires exactly 20 exact 32-byte seeds"
        )
    if len(set(seeds)) != TASK_COUNT:
        raise SWM0WProtocolError("ordered seed binding requires unique seeds")
    return _ordered_task_seed_hash_binding_sha256(
        tuple(hashlib.sha256(seed).hexdigest() for seed in seeds)
    )


def r_squared_from_mse(mse: float, variance: ExactTestVariance) -> float:
    _finite(mse, "mean_squared_error")
    if mse < 0.0 or type(variance) is not ExactTestVariance:
        raise SWM0WProtocolError("R-squared requires nonnegative MSE and exact variance")
    result = 1.0 - mse / variance.population_variance
    if not math.isfinite(result):
        raise SWM0WProtocolError("R-squared is not finite")
    return float(result)


@dataclass(frozen=True, slots=True)
class ArmResult:
    spec_id: str
    optimizer_seed: int
    training_config_sha256: str
    model_state_sha256: str
    optimization_receipt_sha256: str
    score_receipt_sha256: str
    predictions_sha256: str
    mean_squared_error: float
    test_r2: float

    def __post_init__(self) -> None:
        if type(self.spec_id) is not str or self.spec_id not in _SPECS_BY_ID:
            raise SWM0WProtocolError("arm result uses an unregistered spec")
        if type(self.optimizer_seed) is not int or self.optimizer_seed < 0:
            raise SWM0WProtocolError("arm optimizer seed must be nonnegative")
        for field in (
            "training_config_sha256",
            "model_state_sha256",
            "optimization_receipt_sha256",
            "score_receipt_sha256",
            "predictions_sha256",
        ):
            _require_sha256(getattr(self, field), field)
        _finite(self.mean_squared_error, "mean_squared_error")
        _finite(self.test_r2, "test_r2")
        if self.mean_squared_error < 0.0:
            raise SWM0WProtocolError("arm MSE must be nonnegative")

    def canonical(self) -> dict[str, Any]:
        return {
            "mean_squared_error_hex": self.mean_squared_error.hex(),
            "model_state_sha256": self.model_state_sha256,
            "optimization_receipt_sha256": self.optimization_receipt_sha256,
            "optimizer_seed": self.optimizer_seed,
            "predictions_sha256": self.predictions_sha256,
            "schema_version": ARM_RESULT_SCHEMA,
            "score_receipt_sha256": self.score_receipt_sha256,
            "spec_id": self.spec_id,
            "test_r2_hex": self.test_r2.hex(),
            "training_config_sha256": self.training_config_sha256,
        }


@dataclass(frozen=True, slots=True)
class HeadResult:
    head: InteractionHeadV1
    removal_receipt_sha256: str
    ablated_state_sha256: str
    restored_state_sha256: str
    restored_score_receipt_sha256: str
    restored_predictions_sha256: str
    score_receipt_sha256: str
    predictions_sha256: str
    ablated_mse: float
    ablated_r2: float
    damage: float

    def __post_init__(self) -> None:
        if type(self.head) is not InteractionHeadV1:
            raise SWM0WProtocolError("head result requires an exact selector")
        for field in (
            "removal_receipt_sha256",
            "ablated_state_sha256",
            "restored_state_sha256",
            "restored_score_receipt_sha256",
            "restored_predictions_sha256",
            "score_receipt_sha256",
            "predictions_sha256",
        ):
            _require_sha256(getattr(self, field), field)
        for field in ("ablated_mse", "ablated_r2", "damage"):
            _finite(getattr(self, field), field)

    def canonical(self) -> dict[str, Any]:
        return {
            "ablated_mse_hex": self.ablated_mse.hex(),
            "ablated_r2_hex": self.ablated_r2.hex(),
            "ablated_state_sha256": self.ablated_state_sha256,
            "damage_hex": self.damage.hex(),
            "head": self.head.canonical(),
            "predictions_sha256": self.predictions_sha256,
            "removal_receipt_sha256": self.removal_receipt_sha256,
            "restored_state_sha256": self.restored_state_sha256,
            "restored_score_receipt_sha256": self.restored_score_receipt_sha256,
            "restored_predictions_sha256": self.restored_predictions_sha256,
            "schema_version": HEAD_RESULT_SCHEMA,
            "score_receipt_sha256": self.score_receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class MetricVector:
    q: float
    l: float
    c: float
    h: float
    s: float
    r: float
    k: float

    def __post_init__(self) -> None:
        for name in "qlchsrk":
            _finite(getattr(self, name), name)

    def canonical(self) -> dict[str, str]:
        return {name.upper(): getattr(self, name).hex() for name in "qlchsrk"}


@dataclass(frozen=True, slots=True)
class TaskReceipt:
    task_index: int
    task_uid: str
    task_sha256: str
    task_seed_sha256: str
    optimizer_template: OptimizerTemplate
    optimizer_template_sha256: str
    exact_variance: ExactTestVariance
    arm_results: tuple[ArmResult, ...]
    native_star_world_count: int
    native_star_parity_sha256: str
    role_cycle_score_receipt_sha256: str
    role_cycle_predictions_sha256: str
    role_cycle_mse: float
    role_cycle_r2: float
    head_results: tuple[HeadResult, ...]
    metrics: MetricVector
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.task_index) is not int or self.task_index < 0:
            raise SWM0WProtocolError("task index must be nonnegative")
        if type(self.task_uid) is not str or _TASK_UID_RE.fullmatch(self.task_uid) is None:
            raise SWM0WProtocolError("invalid task receipt uid")
        for field in (
            "task_sha256",
            "task_seed_sha256",
            "optimizer_template_sha256",
            "native_star_parity_sha256",
            "role_cycle_score_receipt_sha256",
            "role_cycle_predictions_sha256",
            "receipt_sha256",
        ):
            _require_sha256(getattr(self, field), field)
        if type(self.optimizer_template) is not OptimizerTemplate:
            raise SWM0WProtocolError(
                "task receipt requires exact optimizer template"
            )
        if (
            OptimizerTemplate(**self.optimizer_template.canonical())
            != self.optimizer_template
            or self.optimizer_template_sha256
            != canonical_sha256(self.optimizer_template.canonical())
        ):
            raise SWM0WProtocolError("task optimizer template does not verify")
        if type(self.exact_variance) is not ExactTestVariance:
            raise SWM0WProtocolError("task receipt requires exact test variance")
        if self.exact_variance.case_count != TEST_CASE_COUNT:
            raise SWM0WProtocolError(
                "task receipt exact variance must cover exactly 5,000 test cases"
            )
        if (
            type(self.arm_results) is not tuple
            or any(type(row) is not ArmResult for row in self.arm_results)
            or tuple(row.spec_id for row in self.arm_results)
            != tuple(spec.spec_id for spec in ARM_SPECS)
        ):
            raise SWM0WProtocolError("task receipt must contain all nine arms in order")
        expected_seed = optimizer_seed_from_task_uid(self.task_uid)
        if any(row.optimizer_seed != expected_seed for row in self.arm_results):
            raise SWM0WProtocolError("arm optimizer seed is not the exact task-UID seed")
        for spec, row in zip(ARM_SPECS, self.arm_results):
            expected_config_sha = canonical_sha256(
                self.optimizer_template.config(spec, self.task_uid).canonical()
            )
            if row.training_config_sha256 != expected_config_sha:
                raise SWM0WProtocolError(
                    "arm training config does not match task optimizer/spec"
                )
        if type(self.native_star_world_count) is not int or self.native_star_world_count != 15_625:
            raise SWM0WProtocolError("native/star parity must cover all 15,625 worlds")
        if (
            type(self.head_results) is not tuple
            or any(type(row) is not HeadResult for row in self.head_results)
            or tuple(row.head for row in self.head_results) != HEAD_SPECS
        ):
            raise SWM0WProtocolError("task receipt must contain all seven heads in order")
        if len({row.ablated_state_sha256 for row in self.head_results}) != len(
            HEAD_SPECS
        ):
            raise SWM0WProtocolError(
                "distinct head removals require unique ablated model states"
            )
        if type(self.metrics) is not MetricVector:
            raise SWM0WProtocolError("task receipt metrics must be exact MetricVector")
        results = {row.spec_id: row for row in self.arm_results}
        for row in self.arm_results:
            expected_r2 = r_squared_from_mse(row.mean_squared_error, self.exact_variance)
            if not _same_float(row.test_r2, expected_r2):
                raise SWM0WProtocolError("arm R-squared disagrees with exact variance")
        _finite(self.role_cycle_mse, "role_cycle_mse")
        _finite(self.role_cycle_r2, "role_cycle_r2")
        if not _same_float(
            self.role_cycle_r2,
            r_squared_from_mse(self.role_cycle_mse, self.exact_variance),
        ):
            raise SWM0WProtocolError("role-cycle R-squared disagrees with exact variance")
        base_r2 = results["T16"].test_r2
        for row in self.head_results:
            if any(type(role) is not str for role in row.head.roles):
                raise SWM0WProtocolError("head roles must be exact strings")
            if row.restored_state_sha256 != results["T16"].model_state_sha256:
                raise SWM0WProtocolError("head restoration is not bit-exact")
            if row.ablated_state_sha256 == results["T16"].model_state_sha256:
                raise SWM0WProtocolError("head removal did not change model state")
            if (
                row.restored_score_receipt_sha256 != results["T16"].score_receipt_sha256
                or row.restored_predictions_sha256 != results["T16"].predictions_sha256
            ):
                raise SWM0WProtocolError(
                    "head restoration predictions are not bit-exact"
                )
            if row.predictions_sha256 == results["T16"].predictions_sha256 and (
                row.score_receipt_sha256 != results["T16"].score_receipt_sha256
                or not _same_float(row.ablated_mse, results["T16"].mean_squared_error)
                or not _same_float(row.ablated_r2, base_r2)
                or not _same_float(row.damage, 0.0)
            ):
                raise SWM0WProtocolError(
                    "unchanged head predictions require unchanged score and zero damage"
                )
            if not _same_float(
                row.ablated_r2,
                r_squared_from_mse(row.ablated_mse, self.exact_variance),
            ) or not _same_float(row.damage, base_r2 - row.ablated_r2):
                raise SWM0WProtocolError("head damage does not recompute")
        score_rows = [
            (
                row.predictions_sha256,
                row.score_receipt_sha256,
                row.mean_squared_error,
                row.test_r2,
            )
            for row in self.arm_results
        ]
        score_rows.append(
            (
                self.role_cycle_predictions_sha256,
                self.role_cycle_score_receipt_sha256,
                self.role_cycle_mse,
                self.role_cycle_r2,
            )
        )
        score_rows.extend(
            (
                row.predictions_sha256,
                row.score_receipt_sha256,
                row.ablated_mse,
                row.ablated_r2,
            )
            for row in self.head_results
        )
        by_predictions: dict[str, tuple[str, str, str]] = {}
        by_score: dict[str, tuple[str, str, str]] = {}
        for predictions_sha, score_sha, mse, r2 in score_rows:
            prediction_claim = (score_sha, mse.hex(), r2.hex())
            score_claim = (predictions_sha, mse.hex(), r2.hex())
            if predictions_sha in by_predictions and (
                by_predictions[predictions_sha] != prediction_claim
            ):
                raise SWM0WProtocolError(
                    "equal prediction receipts require equal scores and metrics"
                )
            if score_sha in by_score and by_score[score_sha] != score_claim:
                raise SWM0WProtocolError(
                    "equal score receipts require equal predictions and metrics"
                )
            by_predictions[predictions_sha] = prediction_claim
            by_score[score_sha] = score_claim
        expected_metrics = metric_vector_from_measurements(
            results, self.role_cycle_r2, self.head_results
        )
        if self.metrics.canonical() != expected_metrics.canonical():
            raise SWM0WProtocolError("task metrics do not recompute from measurements")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WProtocolError("task protocol receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "arm_results": [row.canonical() for row in self.arm_results],
            "exact_test_variance": self.exact_variance.canonical(),
            "head_results": [row.canonical() for row in self.head_results],
            "metrics": self.metrics.canonical(),
            "native_star_parity": {
                "exact": True,
                "receipt_sha256": self.native_star_parity_sha256,
                "world_count": self.native_star_world_count,
            },
            "optimizer_template_sha256": self.optimizer_template_sha256,
            "optimizer_template": self.optimizer_template.canonical(),
            "role_cycle": {
                "mean_squared_error_hex": self.role_cycle_mse.hex(),
                "predictions_sha256": self.role_cycle_predictions_sha256,
                "r2_hex": self.role_cycle_r2.hex(),
                "rule": ROLE_CYCLE_RULE,
                "score_receipt_sha256": self.role_cycle_score_receipt_sha256,
            },
            "schema_version": TASK_RECEIPT_SCHEMA,
            "task_index": self.task_index,
            "task_sha256": self.task_sha256,
            "task_seed_sha256": self.task_seed_sha256,
            "task_uid": self.task_uid,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def metric_vector_from_measurements(
    results: Mapping[str, ArmResult],
    role_cycle_r2: float,
    heads: Sequence[HeadResult],
) -> MetricVector:
    if set(results) != set(_SPECS_BY_ID):
        raise SWM0WProtocolError("metric reduction requires exactly nine arms")
    if tuple(row.head for row in heads) != HEAD_SPECS:
        raise SWM0WProtocolError("metric reduction requires exactly seven ordered heads")
    q = results["T16"].test_r2
    lower = max(results[name].test_r2 for name in ("P16", "A16", "R16"))
    complete = max(results[name].test_r2 for name in ("F16", "D16"))
    capacity = max(results[name].test_r2 for name in ("P17-cap", "A21-cap", "R64-cap"))
    triple_damage = heads[-1].damage
    return MetricVector(
        q=q,
        l=q - lower,
        c=q - complete,
        h=triple_damage,
        s=triple_damage - max(row.damage for row in heads[:-1]),
        r=q - role_cycle_r2,
        k=q - capacity,
    )


def _score_model_label_free(
    model: LearnedSWM0WOperator,
    task: StreamedTaskV1,
    *,
    role_cycle: bool = False,
) -> tuple[Any, tuple[float, ...]]:
    if type(model) is not LearnedSWM0WOperator or type(task) is not StreamedTaskV1:
        raise SWM0WProtocolError("prediction requires exact model and task artifacts")
    predictions: list[float] = []
    for world in model_worlds_from_split(task, "test"):
        visible = cycle_role_inputs(world) if role_cycle else world
        # Only ModelWorldV1 crosses this boundary.  The task/evaluator envelope
        # remains owned by score_task_predictions below.
        prediction = model.predict(visible)
        if not math.isfinite(prediction):
            raise SWM0WProtocolError("model emitted a non-finite test prediction")
        predictions.append(float(prediction))
    values = tuple(predictions)
    return score_task_predictions(task, "test", values), values


def cycle_role_inputs(world: ModelWorldV1) -> ModelWorldV1:
    """Apply the frozen non-identity role cycle without any evaluator fields."""

    if type(world) is not ModelWorldV1:
        raise SWM0WProtocolError("role cycle requires an exact ModelWorldV1")
    values = world.feature_matrix()
    cycled = (values[1], values[2], values[0])
    return ModelWorldV1(
        tuple(RoleInputV1(role=role, features=features) for role, features in zip(ROLES, cycled))
    )


def _parity_receipt(task: StreamedTaskV1) -> tuple[int, str]:
    rows: list[tuple[str, str, str]] = []
    for split in SPLITS:
        for world in model_worlds_from_split(task, split):
            rows.append((split, world.semantic_sha256, assert_typed_star_parity(world)))
    if len(rows) != 15_625:
        raise SWM0WProtocolError("native/star parity coverage drift")
    return len(rows), canonical_sha256(rows)


def _arm_result(
    spec: ArmSpec,
    model: LearnedSWM0WOperator,
    score: Any,
    variance: ExactTestVariance,
) -> ArmResult:
    expected_config = model.config
    if model.arm is not spec.arm or model.config.width != spec.width:
        raise SWM0WProtocolError("fitted model does not match its registered arm spec")
    return ArmResult(
        spec_id=spec.spec_id,
        optimizer_seed=model.config.seed,
        training_config_sha256=canonical_sha256(expected_config.canonical()),
        model_state_sha256=model.state_sha256,
        optimization_receipt_sha256=model.optimization.receipt_sha256,
        score_receipt_sha256=score.receipt_sha256,
        predictions_sha256=score.predictions_sha256,
        mean_squared_error=float(score.mean_squared_error),
        test_r2=r_squared_from_mse(float(score.mean_squared_error), variance),
    )


def execute_task(
    seed: bytes,
    task_index: int,
    *,
    mode: RunMode | str = RunMode.DIAGNOSTIC,
    optimizer: OptimizerTemplate = CONFIRMATORY_OPTIMIZER,
) -> TaskReceipt:
    """Execute one streamed task; no randomness fetch or scientific claim occurs."""

    selected_mode = _coerce_mode(mode)
    if type(seed) is not bytes or len(seed) < MINIMUM_SEED_BYTES:
        raise SWM0WProtocolError("task seed must be exact bytes of at least 32 bytes")
    if type(task_index) is not int or task_index < 0:
        raise SWM0WProtocolError("task index must be nonnegative")
    if type(optimizer) is not OptimizerTemplate:
        raise SWM0WProtocolError("optimizer must be an exact OptimizerTemplate")
    if OptimizerTemplate(**optimizer.canonical()) != optimizer:
        raise SWM0WProtocolError("optimizer changed after validation")
    if selected_mode is RunMode.CONFIRMATORY and optimizer != CONFIRMATORY_OPTIMIZER:
        raise SWM0WProtocolError("confirmatory execution requires the frozen default optimizer")
    if selected_mode is RunMode.CONFIRMATORY and len(seed) != 32:
        raise SWM0WProtocolError("confirmatory task seeds must be exactly 32 bytes")

    task = build_task_from_external_seed(seed)
    variance = exact_test_variance(task)
    train = evaluator_cases_from_split(task, "train")
    dev = evaluator_cases_from_split(task, "dev")
    models: dict[str, LearnedSWM0WOperator] = {}
    arm_rows: list[ArmResult] = []
    for spec in ARM_SPECS:
        config = optimizer.config(spec, task.task_uid)
        model = fit_operator(train, dev, spec.arm, config=config)
        score, _ = _score_model_label_free(model, task)
        models[spec.spec_id] = model
        arm_rows.append(_arm_result(spec, model, score, variance))

    target_model = models["T16"]
    cycle_score, _ = _score_model_label_free(target_model, task, role_cycle=True)
    base_r2 = arm_rows[0].test_r2
    head_rows: list[HeadResult] = []
    for head in HEAD_SPECS:
        ablated, removal = remove_interaction_head(target_model, head)
        score, _ = _score_model_label_free(ablated, task)
        ablated_r2 = r_squared_from_mse(float(score.mean_squared_error), variance)
        restored = restore_interaction_head(ablated, removal)
        if restored.state_sha256 != target_model.state_sha256:
            raise SWM0WProtocolError("interaction head did not restore bit-exactly")
        restored_score, _ = _score_model_label_free(restored, task)
        if (
            restored_score.predictions_sha256 != arm_rows[0].predictions_sha256
            or restored_score.receipt_sha256 != arm_rows[0].score_receipt_sha256
        ):
            raise SWM0WProtocolError(
                "interaction head did not restore predictions bit-exactly"
            )
        head_rows.append(
            HeadResult(
                head=head,
                removal_receipt_sha256=removal.receipt_sha256,
                ablated_state_sha256=ablated.state_sha256,
                restored_state_sha256=restored.state_sha256,
                restored_score_receipt_sha256=restored_score.receipt_sha256,
                restored_predictions_sha256=restored_score.predictions_sha256,
                score_receipt_sha256=score.receipt_sha256,
                predictions_sha256=score.predictions_sha256,
                ablated_mse=float(score.mean_squared_error),
                ablated_r2=ablated_r2,
                damage=base_r2 - ablated_r2,
            )
        )
    parity_count, parity_sha = _parity_receipt(task)
    metrics = metric_vector_from_measurements(
        {row.spec_id: row for row in arm_rows},
        r_squared_from_mse(float(cycle_score.mean_squared_error), variance),
        head_rows,
    )
    unsigned = {
        "arm_results": [row.canonical() for row in arm_rows],
        "exact_test_variance": variance.canonical(),
        "head_results": [row.canonical() for row in head_rows],
        "metrics": metrics.canonical(),
        "native_star_parity": {
            "exact": True,
            "receipt_sha256": parity_sha,
            "world_count": parity_count,
        },
        "optimizer_template_sha256": canonical_sha256(optimizer.canonical()),
        "optimizer_template": optimizer.canonical(),
        "role_cycle": {
            "mean_squared_error_hex": float(cycle_score.mean_squared_error).hex(),
            "predictions_sha256": cycle_score.predictions_sha256,
            "r2_hex": r_squared_from_mse(float(cycle_score.mean_squared_error), variance).hex(),
            "rule": ROLE_CYCLE_RULE,
            "score_receipt_sha256": cycle_score.receipt_sha256,
        },
        "schema_version": TASK_RECEIPT_SCHEMA,
        "task_index": task_index,
        "task_sha256": task.task_sha256,
        "task_seed_sha256": hashlib.sha256(seed).hexdigest(),
        "task_uid": task.task_uid,
    }
    return TaskReceipt(
        task_index=task_index,
        task_uid=task.task_uid,
        task_sha256=task.task_sha256,
        task_seed_sha256=hashlib.sha256(seed).hexdigest(),
        optimizer_template=optimizer,
        optimizer_template_sha256=canonical_sha256(optimizer.canonical()),
        exact_variance=variance,
        arm_results=tuple(arm_rows),
        native_star_world_count=parity_count,
        native_star_parity_sha256=parity_sha,
        role_cycle_score_receipt_sha256=cycle_score.receipt_sha256,
        role_cycle_predictions_sha256=cycle_score.predictions_sha256,
        role_cycle_mse=float(cycle_score.mean_squared_error),
        role_cycle_r2=r_squared_from_mse(float(cycle_score.mean_squared_error), variance),
        head_results=tuple(head_rows),
        metrics=metrics,
        receipt_sha256=canonical_sha256(unsigned),
    )


@dataclass(frozen=True, slots=True)
class MetricEstimate:
    point: float
    lower: float | None
    upper: float | None

    def __post_init__(self) -> None:
        _finite(self.point, "estimate point")
        if (self.lower is None) != (self.upper is None):
            raise SWM0WProtocolError("estimate interval must be wholly present or absent")
        if self.lower is not None:
            _finite(self.lower, "estimate lower")
            _finite(self.upper, "estimate upper")
            if self.lower > self.upper:
                raise SWM0WProtocolError("estimate interval is reversed")

    def canonical(self) -> dict[str, str | None]:
        return {
            "lower_hex": None if self.lower is None else self.lower.hex(),
            "point_hex": self.point.hex(),
            "upper_hex": None if self.upper is None else self.upper.hex(),
        }


def shared_task_bootstrap_indices() -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    result = rng.integers(
        0, TASK_COUNT, size=(BOOTSTRAP_RESAMPLES, TASK_COUNT), dtype=np.int64
    )
    result.setflags(write=False)
    return result


def _bootstrap_sha256(indices: np.ndarray) -> str:
    array = np.ascontiguousarray(indices, dtype="<i8")
    header = canonical_json({"dtype": "int64-little-endian", "shape": list(array.shape)})
    return hashlib.sha256(header.encode("ascii") + b"\x00" + array.tobytes()).hexdigest()


def summarize_metrics(tasks: Sequence[TaskReceipt]) -> tuple[tuple[str, MetricEstimate], ...]:
    if len(tasks) == 0:
        raise SWM0WProtocolError("metric summary requires at least one task")
    fields = "qlchsrk"
    arrays = {
        field: np.asarray([getattr(task.metrics, field) for task in tasks], dtype=np.float64)
        for field in fields
    }
    if any(not np.isfinite(values).all() for values in arrays.values()):
        raise SWM0WProtocolError("task metrics must be finite")
    if len(tasks) != TASK_COUNT:
        return tuple(
            (field.upper(), MetricEstimate(float(values.mean()), None, None))
            for field, values in arrays.items()
        )
    indices = shared_task_bootstrap_indices()
    rows: list[tuple[str, MetricEstimate]] = []
    for field, values in arrays.items():
        replicates = values[indices].mean(axis=1)
        lower, upper = np.quantile(
            replicates, BOOTSTRAP_QUANTILES, method="linear"
        )
        rows.append(
            (
                field.upper(),
                MetricEstimate(float(values.mean()), float(lower), float(upper)),
            )
        )
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class FinalReceipt:
    mode: RunMode
    outcome: ProtocolOutcome
    reason_codes: tuple[str, ...]
    admission: ConfirmatoryAdmissionV1 | None
    task_receipt_sha256: tuple[str, ...]
    ordered_task_seed_binding_sha256: str | None
    optimizer_template_sha256: str
    thresholds: Thresholds
    metric_estimates: tuple[tuple[str, MetricEstimate], ...]
    bootstrap_indices_sha256: str | None
    capacity_independent_phrase_candidate: bool
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.mode) is not RunMode or type(self.outcome) is not ProtocolOutcome:
            raise SWM0WProtocolError("final receipt requires exact mode and outcome")
        if type(self.reason_codes) is not tuple or not self.reason_codes or any(
            not isinstance(value, str) or not value for value in self.reason_codes
        ):
            raise SWM0WProtocolError("final receipt requires reason codes")
        if self.admission is not None and type(self.admission) is not ConfirmatoryAdmissionV1:
            raise SWM0WProtocolError("final admission must be an exact typed receipt")
        if self.admission is not None and (
            self.admission.receipt_sha256
            != canonical_sha256(self.admission.unsigned())
        ):
            raise SWM0WProtocolError("final admission changed after validation")
        if type(self.task_receipt_sha256) is not tuple:
            raise SWM0WProtocolError("final task receipt hashes must be an exact tuple")
        for value in self.task_receipt_sha256:
            _require_sha256(value, "task_receipt_sha256")
        if self.ordered_task_seed_binding_sha256 is not None:
            _require_sha256(
                self.ordered_task_seed_binding_sha256,
                "ordered_task_seed_binding_sha256",
            )
        _require_sha256(self.optimizer_template_sha256, "optimizer_template_sha256")
        if type(self.thresholds) is not Thresholds:
            raise SWM0WProtocolError("final receipt requires exact thresholds")
        if (
            type(self.metric_estimates) is not tuple
            or any(
                type(row) is not tuple
                or len(row) != 2
                or type(row[0]) is not str
                or type(row[1]) is not MetricEstimate
                for row in self.metric_estimates
            )
            or tuple(name for name, _ in self.metric_estimates) != tuple("QLCHSRK")
        ):
            raise SWM0WProtocolError("final receipt metric order drift")
        if len(self.task_receipt_sha256) == TASK_COUNT:
            _require_sha256(self.bootstrap_indices_sha256, "bootstrap_indices_sha256")
        elif self.bootstrap_indices_sha256 is not None:
            raise SWM0WProtocolError("partial diagnostics cannot claim frozen bootstrap")
        if type(self.capacity_independent_phrase_candidate) is not bool:
            raise SWM0WProtocolError("capacity phrase candidate must be exact bool")
        if self.capacity_independent_phrase_candidate and self.outcome is not ProtocolOutcome.CANDIDATE_PASS_AWAITING_BUNDLE:
            raise SWM0WProtocolError("capacity phrase candidate requires candidate PASS")
        if self.outcome is ProtocolOutcome.CANDIDATE_PASS_AWAITING_BUNDLE and self.admission is None:
            raise SWM0WProtocolError("candidate PASS requires typed operational admission")
        if self.outcome is not ProtocolOutcome.VOID and self.admission is not None and (
            self.ordered_task_seed_binding_sha256 is None
            or self.admission.task_seed_binding_sha256
            != self.ordered_task_seed_binding_sha256
        ):
            raise SWM0WProtocolError("final admission/task-seed binding mismatch")
        if self.mode is RunMode.DIAGNOSTIC and (
            self.outcome
            not in {ProtocolOutcome.DIAGNOSTIC_ONLY, ProtocolOutcome.VOID}
        ):
            raise SWM0WProtocolError("diagnostic final receipt cannot emit a candidate")
        if self.mode is RunMode.CONFIRMATORY and self.outcome is not ProtocolOutcome.VOID:
            if (
                len(self.task_receipt_sha256) != TASK_COUNT
                or self.admission is None
                or self.thresholds != CONFIRMATORY_THRESHOLDS
                or self.optimizer_template_sha256
                != canonical_sha256(CONFIRMATORY_OPTIMIZER.canonical())
                or self.admission.protocol_contract_sha256
                != canonical_sha256(protocol_contract())
            ):
                raise SWM0WProtocolError(
                    "non-VOID confirmatory receipt violates the frozen contract"
                )
            expected_outcome, expected_reasons, expected_phrase = _reduce(
                self.mode,
                dict(self.metric_estimates),
                task_count=len(self.task_receipt_sha256),
                exact_optimizer=True,
                exact_thresholds=True,
                admission_valid=True,
                integrity_errors=(),
                thresholds=self.thresholds,
            )
            if (
                self.outcome is not expected_outcome
                or self.reason_codes != expected_reasons
                or self.capacity_independent_phrase_candidate is not expected_phrase
            ):
                raise SWM0WProtocolError("final candidate outcome does not recompute")
        _require_sha256(self.receipt_sha256, "receipt_sha256")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WProtocolError("final protocol receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "external_admission": None if self.admission is None else self.admission.canonical(),
            "arm_specs": [spec.canonical() for spec in ARM_SPECS],
            "bootstrap": {
                "generator": "numpy.random.PCG64",
                "indices_sha256": self.bootstrap_indices_sha256,
                "quantile_method": "linear",
                "quantiles": list(BOOTSTRAP_QUANTILES),
                "resamples": BOOTSTRAP_RESAMPLES,
                "seed": BOOTSTRAP_SEED,
                "shared_across_metrics": True,
                "unit": "TASK",
            },
            "capacity_independent_phrase_candidate": self.capacity_independent_phrase_candidate,
            "metric_estimates": {name: estimate.canonical() for name, estimate in self.metric_estimates},
            "mode": self.mode.value,
            "optimizer_seed_rule": OPTIMIZER_SEED_RULE,
            "optimizer_template_sha256": self.optimizer_template_sha256,
            "protocol_version": PROTOCOL_VERSION,
            "reason_codes": list(self.reason_codes),
            "schema_version": FINAL_RECEIPT_SCHEMA,
            "task_receipt_sha256_in_seed_order": list(self.task_receipt_sha256),
            "ordered_task_seed_binding_sha256": self.ordered_task_seed_binding_sha256,
            "thresholds": self.thresholds.canonical(),
            "outcome": self.outcome.value,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def _reduce(
    mode: RunMode,
    estimates: Mapping[str, MetricEstimate],
    *,
    task_count: int,
    exact_optimizer: bool,
    exact_thresholds: bool,
    admission_valid: bool,
    integrity_errors: Sequence[str],
    thresholds: Thresholds,
) -> tuple[ProtocolOutcome, tuple[str, ...], bool]:
    void_reasons = list(integrity_errors)
    if mode is RunMode.CONFIRMATORY:
        if task_count != TASK_COUNT:
            void_reasons.append("CONFIRMATORY_TASK_COUNT_DRIFT")
        if not exact_optimizer:
            void_reasons.append("CONFIRMATORY_OPTIMIZER_DRIFT")
        if not exact_thresholds:
            void_reasons.append("CONFIRMATORY_THRESHOLD_DRIFT")
        if not admission_valid:
            void_reasons.append("MISSING_OR_MISMATCHED_OPERATIONAL_ADMISSION")
    if void_reasons:
        return ProtocolOutcome.VOID, tuple(dict.fromkeys(void_reasons)), False
    if mode is RunMode.DIAGNOSTIC:
        return ProtocolOutcome.DIAGNOSTIC_ONLY, ("DIAGNOSTIC_ONLY",), False
    required = {
        "Q": thresholds.q,
        "L": thresholds.l,
        "C": thresholds.c,
        "H": thresholds.h,
        "S": thresholds.s,
        "R": thresholds.r,
    }
    if any(estimates[name].lower is None for name in required):
        return ProtocolOutcome.VOID, ("MISSING_CONFIRMATORY_INTERVALS",), False
    passes = {
        name: estimates[name].lower >= threshold
        if name != "S"
        else estimates[name].lower > threshold
        for name, threshold in required.items()
    }
    if all(passes.values()):
        phrase = estimates["K"].lower is not None and estimates["K"].lower >= thresholds.k_phrase
        return (
            ProtocolOutcome.CANDIDATE_PASS_AWAITING_BUNDLE,
            ("CANDIDATE_ALL_ESSENTIAL_GATES_PASS",),
            phrase,
        )
    killed = [
        f"{name}_UCB_BELOW_GATE"
        for name, threshold in required.items()
        if estimates[name].upper is not None
        and (
            estimates[name].upper < threshold
            if name != "S"
            else estimates[name].upper <= threshold
        )
    ]
    if killed:
        return ProtocolOutcome.CANDIDATE_KILL_AWAITING_BUNDLE, tuple(killed), False
    return (
        ProtocolOutcome.CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE,
        ("CANDIDATE_ESSENTIAL_INTERVAL_CROSSES_GATE",),
        False,
    )


def finalize_protocol(
    tasks: Sequence[TaskReceipt],
    *,
    mode: RunMode | str = RunMode.DIAGNOSTIC,
    optimizer: OptimizerTemplate = CONFIRMATORY_OPTIMIZER,
    admission: ConfirmatoryAdmissionV1 | None = None,
    integrity_errors: Sequence[str] = (),
    thresholds: Thresholds = CONFIRMATORY_THRESHOLDS,
) -> FinalReceipt:
    selected_mode = _coerce_mode(mode)
    if type(optimizer) is not OptimizerTemplate:
        raise SWM0WProtocolError("optimizer must be an exact OptimizerTemplate")
    if OptimizerTemplate(**optimizer.canonical()) != optimizer:
        raise SWM0WProtocolError("optimizer changed after validation")
    if type(thresholds) is not Thresholds:
        raise SWM0WProtocolError("thresholds must be an exact Thresholds")
    if Thresholds(**{name: getattr(thresholds, name) for name in ("q", "l", "c", "h", "s", "r", "k_phrase")}) != thresholds:
        raise SWM0WProtocolError("thresholds changed after validation")
    if admission is not None and type(admission) is not ConfirmatoryAdmissionV1:
        raise SWM0WProtocolError("admission must be an exact ConfirmatoryAdmissionV1")
    if admission is not None and validate_admission_receipt(admission.canonical()) != admission:
        raise SWM0WProtocolError("admission does not survive strict readback")
    task_rows = tuple(tasks)
    if not task_rows or any(type(task) is not TaskReceipt for task in task_rows):
        raise SWM0WProtocolError("finalization requires exact nonempty task receipts")
    for task in task_rows:
        if task.receipt_sha256 != canonical_sha256(task.unsigned()):
            raise SWM0WProtocolError("task receipt changed after construction")
        if validate_task_receipt(task.canonical()) != task:
            raise SWM0WProtocolError("task receipt does not survive strict readback")
    tasks = task_rows
    if tuple(task.task_index for task in tasks) != tuple(range(len(tasks))):
        raise SWM0WProtocolError("task receipts must retain exact seed order")
    if len({task.task_uid for task in tasks}) != len(tasks):
        raise SWM0WProtocolError("task receipt identities must be unique")
    template_sha = canonical_sha256(optimizer.canonical())
    if any(
        task.optimizer_template != optimizer
        or task.optimizer_template_sha256 != template_sha
        for task in tasks
    ):
        raise SWM0WProtocolError("task receipt optimizer template mismatch")
    if type(integrity_errors) is not tuple or any(
        type(value) is not str or not value for value in integrity_errors
    ):
        raise SWM0WProtocolError(
            "integrity errors must be an exact tuple of nonempty strings"
        )
    expected_contract_sha = canonical_sha256(
        protocol_contract(optimizer=optimizer, thresholds=thresholds)
    )
    admission_contract_valid = (
        admission is not None
        and admission.protocol_contract_sha256 == expected_contract_sha
    )
    ordered_seed_binding = (
        _ordered_task_seed_hash_binding_sha256(
            tuple(task.task_seed_sha256 for task in tasks)
        )
        if len(tasks) == TASK_COUNT
        else None
    )
    admission_seed_valid = (
        admission is not None
        and ordered_seed_binding is not None
        and admission.task_seed_binding_sha256 == ordered_seed_binding
    )
    admission_valid = admission_contract_valid and admission_seed_valid
    effective_integrity_errors = tuple(integrity_errors)
    if admission is not None and not admission_contract_valid:
        effective_integrity_errors += ("ADMISSION_PROTOCOL_CONTRACT_MISMATCH",)
    if admission is not None and not admission_seed_valid:
        effective_integrity_errors += ("ADMISSION_ORDERED_SEED_BINDING_MISMATCH",)
    estimates = summarize_metrics(tasks)
    estimates_by_name = dict(estimates)
    outcome, reasons, phrase = _reduce(
        selected_mode,
        estimates_by_name,
        task_count=len(tasks),
        exact_optimizer=optimizer == CONFIRMATORY_OPTIMIZER,
        exact_thresholds=thresholds == CONFIRMATORY_THRESHOLDS,
        admission_valid=admission_valid,
        integrity_errors=effective_integrity_errors,
        thresholds=thresholds,
    )
    bootstrap_sha = (
        _bootstrap_sha256(shared_task_bootstrap_indices())
        if len(tasks) == TASK_COUNT
        else None
    )
    unsigned = {
        "external_admission": None if admission is None else admission.canonical(),
        "arm_specs": [spec.canonical() for spec in ARM_SPECS],
        "bootstrap": {
            "generator": "numpy.random.PCG64",
            "indices_sha256": bootstrap_sha,
            "quantile_method": "linear",
            "quantiles": list(BOOTSTRAP_QUANTILES),
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "shared_across_metrics": True,
            "unit": "TASK",
        },
        "capacity_independent_phrase_candidate": phrase,
        "metric_estimates": {name: estimate.canonical() for name, estimate in estimates},
        "mode": selected_mode.value,
        "optimizer_seed_rule": OPTIMIZER_SEED_RULE,
        "ordered_task_seed_binding_sha256": ordered_seed_binding,
        "optimizer_template_sha256": template_sha,
        "protocol_version": PROTOCOL_VERSION,
        "reason_codes": list(reasons),
        "schema_version": FINAL_RECEIPT_SCHEMA,
        "task_receipt_sha256_in_seed_order": [task.receipt_sha256 for task in tasks],
        "thresholds": thresholds.canonical(),
        "outcome": outcome.value,
    }
    return FinalReceipt(
        mode=selected_mode,
        outcome=outcome,
        reason_codes=reasons,
        admission=admission,
        task_receipt_sha256=tuple(task.receipt_sha256 for task in tasks),
        ordered_task_seed_binding_sha256=ordered_seed_binding,
        optimizer_template_sha256=template_sha,
        thresholds=thresholds,
        metric_estimates=estimates,
        bootstrap_indices_sha256=bootstrap_sha,
        capacity_independent_phrase_candidate=phrase,
        receipt_sha256=canonical_sha256(unsigned),
    )


def _canonical_float_from_hex(value: Any, field: str) -> float:
    if type(value) is not str:
        raise SWM0WProtocolError(f"{field} must be canonical float hex")
    try:
        parsed = float.fromhex(value)
    except ValueError as exc:
        raise SWM0WProtocolError(f"{field} must be canonical float hex") from exc
    if not math.isfinite(parsed) or parsed.hex() != value:
        raise SWM0WProtocolError(f"{field} must be canonical finite float hex")
    return parsed


def validate_task_receipt(value: Mapping[str, Any]) -> TaskReceipt:
    """Strictly parse a task receipt and recompute every derived metric."""

    if not isinstance(value, Mapping):
        raise SWM0WProtocolError("task receipt must be a mapping")
    _require_exact_json_tree(value, "task_receipt")
    expected_fields = {
        "arm_results",
        "exact_test_variance",
        "head_results",
        "metrics",
        "native_star_parity",
        "optimizer_template",
        "optimizer_template_sha256",
        "receipt_sha256",
        "role_cycle",
        "schema_version",
        "task_index",
        "task_seed_sha256",
        "task_sha256",
        "task_uid",
    }
    if set(value) != expected_fields or value["schema_version"] != TASK_RECEIPT_SCHEMA:
        raise SWM0WProtocolError("task receipt field/schema drift")
    raw_optimizer = value["optimizer_template"]
    optimizer_fields = {
        "batch_size",
        "beta1",
        "beta2",
        "epochs",
        "epsilon",
        "gradient_clip",
        "learning_rate",
        "min_delta",
        "patience",
    }
    if not isinstance(raw_optimizer, Mapping) or set(raw_optimizer) != optimizer_fields:
        raise SWM0WProtocolError("task optimizer template field drift")
    optimizer = OptimizerTemplate(**dict(raw_optimizer))
    if canonical_json(raw_optimizer) != canonical_json(optimizer.canonical()):
        raise SWM0WProtocolError("task optimizer template representation drift")
    raw_variance = value["exact_test_variance"]
    if not isinstance(raw_variance, Mapping):
        raise SWM0WProtocolError("exact test variance must be a mapping")
    variance = ExactTestVariance(
        case_count=raw_variance.get("case_count"),
        target_integer_sum=raw_variance.get("target_integer_sum"),
        target_integer_sum_of_squares=raw_variance.get(
            "target_integer_sum_of_squares"
        ),
        target_scale_exponent=raw_variance.get("target_scale_exponent"),
    )
    if raw_variance != variance.canonical():
        raise SWM0WProtocolError("exact test variance derived fields drift")
    raw_arms = value["arm_results"]
    if not isinstance(raw_arms, list) or len(raw_arms) != len(ARM_SPECS):
        raise SWM0WProtocolError("task arm result count drift")
    arm_rows: list[ArmResult] = []
    arm_fields = {
        "mean_squared_error_hex",
        "model_state_sha256",
        "optimization_receipt_sha256",
        "optimizer_seed",
        "predictions_sha256",
        "schema_version",
        "score_receipt_sha256",
        "spec_id",
        "test_r2_hex",
        "training_config_sha256",
    }
    for raw in raw_arms:
        if (
            not isinstance(raw, Mapping)
            or set(raw) != arm_fields
            or raw["schema_version"] != ARM_RESULT_SCHEMA
        ):
            raise SWM0WProtocolError("task arm result field/schema drift")
        arm_rows.append(
            ArmResult(
                spec_id=raw["spec_id"],
                optimizer_seed=raw["optimizer_seed"],
                training_config_sha256=raw["training_config_sha256"],
                model_state_sha256=raw["model_state_sha256"],
                optimization_receipt_sha256=raw[
                    "optimization_receipt_sha256"
                ],
                score_receipt_sha256=raw["score_receipt_sha256"],
                predictions_sha256=raw["predictions_sha256"],
                mean_squared_error=_canonical_float_from_hex(
                    raw["mean_squared_error_hex"], "arm mean_squared_error"
                ),
                test_r2=_canonical_float_from_hex(raw["test_r2_hex"], "arm r2"),
            )
        )
    raw_heads = value["head_results"]
    if not isinstance(raw_heads, list) or len(raw_heads) != len(HEAD_SPECS):
        raise SWM0WProtocolError("task head result count drift")
    head_fields = {
        "ablated_mse_hex",
        "ablated_r2_hex",
        "ablated_state_sha256",
        "damage_hex",
        "head",
        "predictions_sha256",
        "removal_receipt_sha256",
        "restored_predictions_sha256",
        "restored_score_receipt_sha256",
        "restored_state_sha256",
        "schema_version",
        "score_receipt_sha256",
    }
    head_rows: list[HeadResult] = []
    for raw in raw_heads:
        if (
            not isinstance(raw, Mapping)
            or set(raw) != head_fields
            or raw["schema_version"] != HEAD_RESULT_SCHEMA
        ):
            raise SWM0WProtocolError("task head result field/schema drift")
        selector = raw["head"]
        if (
            not isinstance(selector, Mapping)
            or set(selector) != {"order", "roles"}
            or type(selector["order"]) is not int
            or type(selector["roles"]) is not list
            or any(type(role) is not str for role in selector["roles"])
            or selector["order"] != len(selector["roles"])
        ):
            raise SWM0WProtocolError("task head selector drift")
        head_rows.append(
            HeadResult(
                head=InteractionHeadV1(tuple(selector["roles"])),
                removal_receipt_sha256=raw["removal_receipt_sha256"],
                ablated_state_sha256=raw["ablated_state_sha256"],
                restored_state_sha256=raw["restored_state_sha256"],
                restored_score_receipt_sha256=raw[
                    "restored_score_receipt_sha256"
                ],
                restored_predictions_sha256=raw[
                    "restored_predictions_sha256"
                ],
                score_receipt_sha256=raw["score_receipt_sha256"],
                predictions_sha256=raw["predictions_sha256"],
                ablated_mse=_canonical_float_from_hex(
                    raw["ablated_mse_hex"], "head ablated_mse"
                ),
                ablated_r2=_canonical_float_from_hex(
                    raw["ablated_r2_hex"], "head ablated_r2"
                ),
                damage=_canonical_float_from_hex(raw["damage_hex"], "head damage"),
            )
        )
    raw_metrics = value["metrics"]
    if not isinstance(raw_metrics, Mapping) or set(raw_metrics) != set("QLCHSRK"):
        raise SWM0WProtocolError("task metric field set drift")
    metrics = MetricVector(
        **{
            name.lower(): _canonical_float_from_hex(raw_metrics[name], name)
            for name in "QLCHSRK"
        }
    )
    parity = value["native_star_parity"]
    if (
        not isinstance(parity, Mapping)
        or set(parity) != {"exact", "receipt_sha256", "world_count"}
        or parity["exact"] is not True
    ):
        raise SWM0WProtocolError("native/star parity receipt drift")
    role_cycle = value["role_cycle"]
    if (
        not isinstance(role_cycle, Mapping)
        or set(role_cycle)
        != {
            "mean_squared_error_hex",
            "predictions_sha256",
            "r2_hex",
            "rule",
            "score_receipt_sha256",
        }
        or role_cycle["rule"] != ROLE_CYCLE_RULE
    ):
        raise SWM0WProtocolError("role-cycle receipt drift")
    result = TaskReceipt(
        task_index=value["task_index"],
        task_uid=value["task_uid"],
        task_sha256=value["task_sha256"],
        task_seed_sha256=value["task_seed_sha256"],
        optimizer_template=optimizer,
        optimizer_template_sha256=value["optimizer_template_sha256"],
        exact_variance=variance,
        arm_results=tuple(arm_rows),
        native_star_world_count=parity["world_count"],
        native_star_parity_sha256=parity["receipt_sha256"],
        role_cycle_score_receipt_sha256=role_cycle[
            "score_receipt_sha256"
        ],
        role_cycle_predictions_sha256=role_cycle["predictions_sha256"],
        role_cycle_mse=_canonical_float_from_hex(
            role_cycle["mean_squared_error_hex"], "role-cycle mse"
        ),
        role_cycle_r2=_canonical_float_from_hex(
            role_cycle["r2_hex"], "role-cycle r2"
        ),
        head_results=tuple(head_rows),
        metrics=metrics,
        receipt_sha256=value["receipt_sha256"],
    )
    if canonical_json(value) != canonical_json(result.canonical()):
        raise SWM0WProtocolError(
            "task receipt is not exact canonical JSON representation"
        )
    return result


def validate_final_receipt(value: Mapping[str, Any]) -> FinalReceipt:
    """Strictly parse and recompute a persisted final protocol receipt."""

    if not isinstance(value, Mapping):
        raise SWM0WProtocolError("final receipt must be a mapping")
    _require_exact_json_tree(value, "final_receipt")
    expected_fields = {
        "arm_specs",
        "bootstrap",
        "capacity_independent_phrase_candidate",
        "external_admission",
        "metric_estimates",
        "mode",
        "optimizer_seed_rule",
        "optimizer_template_sha256",
        "ordered_task_seed_binding_sha256",
        "protocol_version",
        "reason_codes",
        "receipt_sha256",
        "schema_version",
        "task_receipt_sha256_in_seed_order",
        "thresholds",
        "outcome",
    }
    if set(value) != expected_fields:
        raise SWM0WProtocolError("final receipt field set drift")
    if (
        value["schema_version"] != FINAL_RECEIPT_SCHEMA
        or value["protocol_version"] != PROTOCOL_VERSION
        or value["optimizer_seed_rule"] != OPTIMIZER_SEED_RULE
        or value["arm_specs"] != [spec.canonical() for spec in ARM_SPECS]
    ):
        raise SWM0WProtocolError("final receipt frozen contract drift")
    task_hashes = value["task_receipt_sha256_in_seed_order"]
    if not isinstance(task_hashes, list):
        raise SWM0WProtocolError("final task receipts must be an ordered list")
    task_hash_tuple = tuple(task_hashes)
    for digest in task_hash_tuple:
        _require_sha256(digest, "task_receipt_sha256")
    binding = value["ordered_task_seed_binding_sha256"]
    if binding is not None:
        _require_sha256(binding, "ordered_task_seed_binding_sha256")
    bootstrap = value["bootstrap"]
    if (
        not isinstance(bootstrap, Mapping)
        or type(bootstrap.get("generator")) is not str
        or (
            bootstrap.get("indices_sha256") is not None
            and type(bootstrap.get("indices_sha256")) is not str
        )
        or type(bootstrap.get("quantile_method")) is not str
        or type(bootstrap.get("quantiles")) is not list
        or any(type(item) is not float for item in bootstrap.get("quantiles", ()))
        or type(bootstrap.get("resamples")) is not int
        or type(bootstrap.get("seed")) is not int
        or type(bootstrap.get("shared_across_metrics")) is not bool
        or type(bootstrap.get("unit")) is not str
    ):
        raise SWM0WProtocolError("final bootstrap primitive type drift")
    expected_bootstrap = {
        "generator": "numpy.random.PCG64",
        "indices_sha256": (
            _bootstrap_sha256(shared_task_bootstrap_indices())
            if len(task_hash_tuple) == TASK_COUNT
            else None
        ),
        "quantile_method": "linear",
        "quantiles": list(BOOTSTRAP_QUANTILES),
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
        "shared_across_metrics": True,
        "unit": "TASK",
    }
    if bootstrap != expected_bootstrap:
        raise SWM0WProtocolError("final bootstrap contract drift")
    raw_thresholds = value["thresholds"]
    if not isinstance(raw_thresholds, Mapping) or set(raw_thresholds) != {
        "q", "l", "c", "h", "s", "r", "k_phrase"
    }:
        raise SWM0WProtocolError("final threshold field set drift")
    thresholds = Thresholds(
        **{
            name: _canonical_float_from_hex(raw_thresholds[name], f"threshold.{name}")
            for name in ("q", "l", "c", "h", "s", "r", "k_phrase")
        }
    )
    raw_estimates = value["metric_estimates"]
    if not isinstance(raw_estimates, Mapping) or set(raw_estimates) != set("QLCHSRK"):
        raise SWM0WProtocolError("final metric field/order drift")
    estimates: list[tuple[str, MetricEstimate]] = []
    for name in "QLCHSRK":
        row = raw_estimates[name]
        if not isinstance(row, Mapping) or set(row) != {
            "lower_hex", "point_hex", "upper_hex"
        }:
            raise SWM0WProtocolError("final metric estimate field drift")
        lower = (
            None
            if row["lower_hex"] is None
            else _canonical_float_from_hex(row["lower_hex"], f"{name}.lower")
        )
        upper = (
            None
            if row["upper_hex"] is None
            else _canonical_float_from_hex(row["upper_hex"], f"{name}.upper")
        )
        estimates.append(
            (
                name,
                MetricEstimate(
                    _canonical_float_from_hex(row["point_hex"], f"{name}.point"),
                    lower,
                    upper,
                ),
            )
        )
    raw_admission = value["external_admission"]
    admission = (
        None
        if raw_admission is None
        else validate_admission_receipt(raw_admission)
    )
    if type(value["capacity_independent_phrase_candidate"]) is not bool:
        raise SWM0WProtocolError("capacity phrase flag must be exact bool")
    if not isinstance(value["reason_codes"], list):
        raise SWM0WProtocolError("final reason codes must be a list")
    _require_sha256(value["optimizer_template_sha256"], "optimizer_template_sha256")
    _require_sha256(value["receipt_sha256"], "receipt_sha256")
    result = FinalReceipt(
        mode=_coerce_mode(value["mode"]),
        outcome=ProtocolOutcome(value["outcome"]),
        reason_codes=tuple(value["reason_codes"]),
        admission=admission,
        task_receipt_sha256=task_hash_tuple,
        ordered_task_seed_binding_sha256=binding,
        optimizer_template_sha256=value["optimizer_template_sha256"],
        thresholds=thresholds,
        metric_estimates=tuple(estimates),
        bootstrap_indices_sha256=bootstrap["indices_sha256"],
        capacity_independent_phrase_candidate=value[
            "capacity_independent_phrase_candidate"
        ],
        receipt_sha256=value["receipt_sha256"],
    )
    if canonical_json(value) != canonical_json(result.canonical()):
        raise SWM0WProtocolError(
            "final receipt is not exact canonical JSON representation"
        )
    return result


def run_protocol(
    task_seeds: Sequence[bytes],
    *,
    mode: RunMode | str = RunMode.DIAGNOSTIC,
    optimizer: OptimizerTemplate = CONFIRMATORY_OPTIMIZER,
    admission: ConfirmatoryAdmissionV1 | None = None,
    integrity_errors: Sequence[str] = (),
    thresholds: Thresholds = CONFIRMATORY_THRESHOLDS,
) -> FinalReceipt:
    """Stream task seeds through execution; at most one task/model suite is live."""

    selected_mode = _coerce_mode(mode)
    task_seeds = tuple(task_seeds)
    if type(optimizer) is not OptimizerTemplate or OptimizerTemplate(
        **optimizer.canonical()
    ) != optimizer:
        raise SWM0WProtocolError("run optimizer is not an intact exact template")
    if type(thresholds) is not Thresholds or Thresholds(
        **{
            name: getattr(thresholds, name)
            for name in ("q", "l", "c", "h", "s", "r", "k_phrase")
        }
    ) != thresholds:
        raise SWM0WProtocolError("run thresholds are not an intact exact contract")
    if type(integrity_errors) is not tuple or any(
        type(value) is not str or not value for value in integrity_errors
    ):
        raise SWM0WProtocolError(
            "run integrity errors must be an exact tuple of nonempty strings"
        )
    if not task_seeds:
        raise SWM0WProtocolError("protocol requires at least one task seed")
    if selected_mode is RunMode.CONFIRMATORY and len(task_seeds) != TASK_COUNT:
        # Return VOID without burning compute on a contract-drifted suite.
        raise SWM0WProtocolError("confirmatory execution requires exactly 20 task seeds")
    if len({seed for seed in task_seeds if type(seed) is bytes}) != len(task_seeds):
        raise SWM0WProtocolError("task seeds must be exact unique bytes")
    if selected_mode is RunMode.CONFIRMATORY:
        if optimizer != CONFIRMATORY_OPTIMIZER:
            raise SWM0WProtocolError(
                "confirmatory preflight requires the frozen optimizer"
            )
        if thresholds != CONFIRMATORY_THRESHOLDS:
            raise SWM0WProtocolError(
                "confirmatory preflight requires the frozen thresholds"
            )
        if type(admission) is not ConfirmatoryAdmissionV1:
            raise SWM0WProtocolError(
                "confirmatory preflight requires typed external admission"
            )
        if validate_admission_receipt(admission.canonical()) != admission:
            raise SWM0WProtocolError(
                "confirmatory admission fails strict preflight readback"
            )
        seed_binding = ordered_task_seed_binding_sha256(task_seeds)
        if admission.task_seed_binding_sha256 != seed_binding:
            raise SWM0WProtocolError(
                "confirmatory admission binds different ordered task seeds"
            )
        expected_contract = canonical_sha256(protocol_contract())
        if admission.protocol_contract_sha256 != expected_contract:
            raise SWM0WProtocolError(
                "confirmatory admission binds a different protocol contract"
            )
    receipts: list[TaskReceipt] = []
    for index, seed in enumerate(task_seeds):
        receipts.append(
            execute_task(seed, index, mode=selected_mode, optimizer=optimizer)
        )
    return finalize_protocol(
        receipts,
        mode=selected_mode,
        optimizer=optimizer,
        admission=admission,
        integrity_errors=integrity_errors,
        thresholds=thresholds,
    )


def protocol_contract(
    *,
    optimizer: OptimizerTemplate = CONFIRMATORY_OPTIMIZER,
    thresholds: Thresholds = CONFIRMATORY_THRESHOLDS,
) -> dict[str, Any]:
    """Return the frozen, non-result contract for preregistration tooling."""

    if type(optimizer) is not OptimizerTemplate or OptimizerTemplate(
        **optimizer.canonical()
    ) != optimizer:
        raise SWM0WProtocolError("contract optimizer is not intact")
    if type(thresholds) is not Thresholds or Thresholds(
        **{
            name: getattr(thresholds, name)
            for name in ("q", "l", "c", "h", "s", "r", "k_phrase")
        }
    ) != thresholds:
        raise SWM0WProtocolError("contract thresholds are not intact")

    indices = shared_task_bootstrap_indices()
    return {
        "arm_specs": [spec.canonical() for spec in ARM_SPECS],
        "bootstrap": {
            "generator": "numpy.random.PCG64",
            "indices_sha256": _bootstrap_sha256(indices),
            "quantile_method": "linear",
            "quantiles": list(BOOTSTRAP_QUANTILES),
            "resamples": BOOTSTRAP_RESAMPLES,
            "sample_shape": list(indices.shape),
            "seed": BOOTSTRAP_SEED,
            "shared_across_metrics": True,
            "unit": "TASK",
        },
        "confirmatory_optimizer": optimizer.canonical(),
        "head_removals": [head.canonical() for head in HEAD_SPECS],
        "metrics": {
            "C": "R2(T16)-max(R2(F16),R2(D16))",
            "H": "R2(T16)-R2(T16_WITH_TRIPLE_HEAD_REMOVED)",
            "K": "R2(T16)-max(R2(P17-cap),R2(A21-cap),R2(R64-cap))",
            "L": "R2(T16)-max(R2(P16),R2(A16),R2(R16))",
            "Q": "R2(T16)",
            "R": "R2(T16)-R2(T16_WITH_FIXED_ROLE_CYCLE)",
            "S": "H-max(THREE_UNARY_AND_THREE_PAIR_HEAD_DAMAGES)",
        },
        "optimizer_seed_rule": OPTIMIZER_SEED_RULE,
        "ordered_task_seed_binding": {
            "schema_version": ORDERED_TASK_SEEDS_SCHEMA,
            "seed_representation": "SHA256_EXACT_32_BYTE_SEED",
        },
        "protocol_version": PROTOCOL_VERSION,
        "role_cycle_rule": ROLE_CYCLE_RULE,
        "scope": {
            "canonical_set_to_set_w_claim": False,
            "external_admission_is_structural_not_authenticating": True,
            "final_bundle_revalidation_required_for_scientific_verdict": True,
            "standalone_authoritative_verdict": False,
            "standalone_outcomes": [item.value for item in ProtocolOutcome],
            "scalar_fixed_three_singleton_role_precursor_only": True,
            "streaming": "ONE_TASK_AT_A_TIME",
        },
        "task_count": TASK_COUNT,
        "test_case_count": TEST_CASE_COUNT,
        "thresholds": thresholds.canonical(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("contract", help="print the frozen non-result contract")
    run = subcommands.add_parser("run-diagnostic", help="run explicit diagnostic seeds")
    run.add_argument("--task-seed-hex", action="append", required=True)
    run.add_argument("--epochs", type=int, default=300)
    run.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args(argv)
    if args.command == "contract":
        print(canonical_json(protocol_contract()))
        return 0
    try:
        seeds = tuple(bytes.fromhex(value) for value in args.task_seed_hex)
    except ValueError as exc:
        parser.error(f"invalid task seed hex: {exc}")
    optimizer = OptimizerTemplate(
        epochs=args.epochs,
        batch_size=args.batch_size,
        patience=min(25, args.epochs),
    )
    result = run_protocol(seeds, mode=RunMode.DIAGNOSTIC, optimizer=optimizer)
    print(canonical_json(result.canonical()))
    return 0


__all__ = [
    "ARM_SPECS",
    "ADMISSION_RECEIPT_SCHEMA",
    "BOOTSTRAP_QUANTILES",
    "BOOTSTRAP_RESAMPLES",
    "BOOTSTRAP_SEED",
    "CONFIRMATORY_OPTIMIZER",
    "CONFIRMATORY_THRESHOLDS",
    "HEAD_SPECS",
    "PROTOCOL_VERSION",
    "ROLE_CYCLE_RULE",
    "TASK_COUNT",
    "TEST_CASE_COUNT",
    "ArmResult",
    "ArmSpec",
    "ConfirmatoryAdmissionV1",
    "ExactTestVariance",
    "FinalReceipt",
    "HeadResult",
    "MetricEstimate",
    "MetricVector",
    "OptimizerTemplate",
    "RunMode",
    "SWM0WProtocolError",
    "TaskReceipt",
    "Thresholds",
    "ProtocolOutcome",
    "cycle_role_inputs",
    "exact_test_variance",
    "execute_task",
    "finalize_protocol",
    "main",
    "metric_vector_from_measurements",
    "optimizer_seed_from_task_uid",
    "ordered_task_seed_binding_sha256",
    "protocol_contract",
    "r_squared_from_mse",
    "run_protocol",
    "shared_task_bootstrap_indices",
    "summarize_metrics",
    "validate_admission_receipt",
    "validate_final_receipt",
    "validate_task_receipt",
]


if __name__ == "__main__":
    raise SystemExit(main())
