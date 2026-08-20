"""Deterministic full-batch training for the unjudged SWM-0W-S2S core.

This module is a deliberately narrow optimizer boundary around the finite V2
task family and the three exact 870-parameter operators.  It consumes complete
``train`` and ``dev`` evaluator tuples, strips them to model-visible tensors,
and never accepts or evaluates ``test`` cases.  Input tuple order is not an
optimization degree of freedom: validated cases are sorted by the canonical
lexicographic six-value world key before hashing or numeric work.

The objective is the mean of six role/channel mean-squared errors, each
multiplied by the inverse population variance measured from *integer train
target numerators*.  The exact Python-integer sums and sums of squares are
bound into :class:`StratumLossReceipt`; those same train-derived weights are
used for dev checkpoint selection.

Initialization is task-independent and separately versioned.  Feature tensors
are seeded by stable per-tensor domains while every output head and output bias
starts as IEEE-754 positive zero.  Optimization is float64, full-batch Adam
with one global gradient clip, epoch/update zero is checkpoint-eligible, dev
improvements are strict by ``min_delta``, ties retain the earliest checkpoint,
and any non-finite state fails closed.

Nothing here is an efficacy verdict, a preregistration, a test-set evaluator,
recurrence, topology learning, or canonical HSWM completion.

Scientific status: ``LEARNED_ENGINEERING_ARTIFACT_UNJUDGED``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from functools import lru_cache
import hashlib
import math
from typing import Any, Mapping

import numpy as np

from hswm.experiments.swm0w_s2s_family import (
    FAMILY_CERTIFICATE_SHA256,
    FAMILY_DEFINITION_SHA256,
    SPLIT_COUNTS,
    TARGET_SCALE_EXPONENT,
    EvaluatorCaseV2,
    TaskSpecV2,
)
from hswm.experiments.swm0w_s2s_operator import (
    ALL_ARMS,
    S2SArm,
    S2SOperator,
    SWM0WS2SOperatorError,
    architecture_receipt,
    canonical_sha256,
    compile_case_target_batch_v2,
    compile_model_world,
    compile_model_worlds,
    forward as operator_forward,
    parameter_shapes,
)
from hswm.experiments.swm0w_s2s_worlds import ModelWorldV1


SCIENTIFIC_STATUS = "LEARNED_ENGINEERING_ARTIFACT_UNJUDGED"
TRAINING_VERSION = "hswm-swm0w-s2s-training/v1"
TRAINING_INITIALIZATION_VERSION = (
    "hswm-swm0w-s2s-task-independent-zero-output-initialization/v1"
)
OPTIMIZER_VERSION = "hswm-swm0w-s2s-full-batch-adam/v1"
STRATUM_LOSS_RECEIPT_VERSION = "hswm-swm0w-s2s-stratum-loss/v1"
LOSS_DEFINITION_VERSION = "hswm-swm0w-s2s-six-stratum-loss/v1"
OPTIMIZATION_RECEIPT_VERSION = "hswm-swm0w-s2s-optimization-receipt/v1"
DATASET_BYTES_VERSION = "hswm-swm0w-s2s-dataset-bytes/v1"
HISTORY_VERSION = "hswm-swm0w-s2s-optimization-history/v1"
HISTORY_ENTRY_VERSION = "hswm-swm0w-s2s-optimization-history-entry/v1"
RECEIPT_ASSURANCE = (
    "SELF_CONSISTENT_COMMITMENT_REQUIRES_DETERMINISTIC_REPLAY"
)

_INITIALIZATION_DOMAIN = b"hswm-swm0w-s2s-training-initialization/v1\x00"
_DATASET_HASH_DOMAIN = b"hswm-swm0w-s2s-dataset-bytes/v1\x00"
_FLOAT64_DTYPE = np.dtype(np.float64)
_ROLE_COUNT = 3
_MEMBER_COUNT = 2
_CHANNEL_COUNT = 2
_STRATUM_COUNT = _ROLE_COUNT * _CHANNEL_COUNT
_TRAIN_CASE_COUNT = SPLIT_COUNTS["train"]
_DEV_CASE_COUNT = SPLIT_COUNTS["dev"]
_TRAIN_STRATUM_SAMPLE_COUNT = _TRAIN_CASE_COUNT * _MEMBER_COUNT
_SHA256_ALPHABET = frozenset("0123456789abcdef")

DATASET_SCHEMA_SHA256 = canonical_sha256(
    {
        "canonical_order": "LEXICOGRAPHIC_RAW_VALUES_ASCENDING",
        "case_bytes": [
            {"dtype": "uint8", "field": "raw_values", "shape": [6]},
            {
                "byte_order": "big",
                "dtype": "int64",
                "field": "target_numerators",
                "shape": [6, 2],
            },
        ],
        "compiled_model_input": {
            "byte_order": "little",
            "dtype": "float64",
            "order": "C",
            "shape": ["N", 3, 2, 4],
        },
        "compiled_target": {
            "byte_order": "little",
            "dtype": "float64",
            "order": "C",
            "shape": ["N", 3, 2, 2],
            "source": "target_numerators/2^19",
        },
        "hash_segment_order": [
            "domain",
            "dataset_schema_sha256",
            "structural_task_sha256",
            "split_length_and_ascii",
            "case_count_uint64_big",
            "lexicographic_case_bytes",
            "compiled_model_input_length_and_bytes",
            "compiled_target_length_and_bytes",
        ],
        "schema_version": DATASET_BYTES_VERSION,
        "task_binding": "structural_task_sha256_raw_32_bytes",
    }
)


class SWM0WS2STrainingError(ValueError):
    """Raised when the deterministic S2S training boundary is violated."""


class TerminationReason(str, Enum):
    MAX_UPDATES = "MAX_UPDATES"
    PATIENCE = "PATIENCE"


def _coerce_arm(arm: S2SArm | str) -> S2SArm:
    if type(arm) is S2SArm:
        return arm
    if type(arm) is not str:
        raise SWM0WS2STrainingError(f"unsupported S2S training arm: {arm!r}")
    try:
        return S2SArm(arm)
    except (TypeError, ValueError) as exc:
        raise SWM0WS2STrainingError(f"unsupported S2S training arm: {arm!r}") from exc


def _require_sha256(value: object, name: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in _SHA256_ALPHABET for character in value)
    ):
        raise SWM0WS2STrainingError(f"{name} must be a lowercase SHA-256")


def _finite_nonnegative(value: object, name: str) -> float:
    if (
        type(value) is not float
        or not math.isfinite(value)
        or value < 0.0
        or (value == 0.0 and math.copysign(1.0, value) < 0.0)
    ):
        raise SWM0WS2STrainingError(f"{name} must be an exact finite non-negative float")
    return value


def _parameter_copy(parameters: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {
        name: np.array(value, dtype=np.float64, order="C", copy=True)
        for name, value in parameters.items()
    }


def _parameter_sha256(arm: S2SArm, parameters: Mapping[str, np.ndarray]) -> str:
    try:
        return S2SOperator(arm, parameters).parameters_sha256
    except SWM0WS2SOperatorError as exc:
        raise SWM0WS2STrainingError("invalid training parameter state") from exc


@dataclass(frozen=True, slots=True)
class S2STrainingConfig:
    """Frozen full-batch Adam configuration; one update equals one epoch."""

    seed: int = 0
    max_updates: int = 200
    learning_rate: float = 0.01
    beta1: float = 0.9
    beta2: float = 0.999
    epsilon: float = 1.0e-8
    gradient_clip: float = 5.0
    patience: int = 25
    min_delta: float = 1.0e-9

    def __post_init__(self) -> None:
        if type(self.seed) is not int or not 0 <= self.seed < 2**64:
            raise SWM0WS2STrainingError("seed must be an exact unsigned 64-bit integer")
        if type(self.max_updates) is not int or self.max_updates < 0:
            raise SWM0WS2STrainingError("max_updates must be a non-negative integer")
        if type(self.patience) is not int or self.patience <= 0:
            raise SWM0WS2STrainingError("patience must be a positive integer")
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
                raise SWM0WS2STrainingError(f"{name} must be an exact finite float")
        if self.learning_rate <= 0.0:
            raise SWM0WS2STrainingError("learning_rate must be positive")
        if not 0.0 < self.beta1 < 1.0 or not 0.0 < self.beta2 < 1.0:
            raise SWM0WS2STrainingError("Adam beta values must lie strictly in (0, 1)")
        if self.epsilon <= 0.0 or self.gradient_clip <= 0.0:
            raise SWM0WS2STrainingError("epsilon and gradient_clip must be positive")
        if self.min_delta < 0.0 or (
            self.min_delta == 0.0 and math.copysign(1.0, self.min_delta) < 0.0
        ):
            raise SWM0WS2STrainingError("min_delta must be non-negative")

    def canonical(self) -> dict[str, Any]:
        return {
            "beta1_hex": self.beta1.hex(),
            "beta2_hex": self.beta2.hex(),
            "epsilon_hex": self.epsilon.hex(),
            "gradient_clip_hex": self.gradient_clip.hex(),
            "learning_rate_hex": self.learning_rate.hex(),
            "max_updates": self.max_updates,
            "min_delta_hex": self.min_delta.hex(),
            "patience": self.patience,
            "seed": self.seed,
        }


@dataclass(frozen=True, slots=True)
class StratumLossReceipt:
    """Exact train-target variance statistics for one role/channel stratum."""

    role: int
    channel: int
    sample_count: int
    target_numerator_sum: int
    target_numerator_sum_squares: int
    centered_sum_squares_numerator: int
    inverse_variance_weight: float
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.role) is not int or not 0 <= self.role < _ROLE_COUNT:
            raise SWM0WS2STrainingError("stratum role must be an exact in-range integer")
        if type(self.channel) is not int or not 0 <= self.channel < _CHANNEL_COUNT:
            raise SWM0WS2STrainingError(
                "stratum channel must be an exact in-range integer"
            )
        if type(self.sample_count) is not int or self.sample_count != _TRAIN_STRATUM_SAMPLE_COUNT:
            raise SWM0WS2STrainingError("stratum must cover the complete train split")
        if type(self.target_numerator_sum) is not int:
            raise SWM0WS2STrainingError("target numerator sum must be an exact integer")
        if (
            type(self.target_numerator_sum_squares) is not int
            or self.target_numerator_sum_squares < 0
        ):
            raise SWM0WS2STrainingError(
                "target numerator sum of squares must be a non-negative integer"
            )
        expected_centered = (
            self.sample_count * self.target_numerator_sum_squares
            - self.target_numerator_sum * self.target_numerator_sum
        )
        if (
            type(self.centered_sum_squares_numerator) is not int
            or self.centered_sum_squares_numerator != expected_centered
            or expected_centered <= 0
        ):
            raise SWM0WS2STrainingError(
                "stratum centered sum-of-squares numerator is inconsistent"
            )
        expected_weight = float(
            Fraction(
                self.sample_count
                * self.sample_count
                * 2 ** (2 * TARGET_SCALE_EXPONENT),
                expected_centered,
            )
        )
        if (
            type(self.inverse_variance_weight) is not float
            or not math.isfinite(self.inverse_variance_weight)
            or self.inverse_variance_weight <= 0.0
            or self.inverse_variance_weight.hex() != expected_weight.hex()
        ):
            raise SWM0WS2STrainingError(
                "inverse variance weight disagrees with exact train statistics"
            )
        _require_sha256(self.receipt_sha256, "stratum receipt SHA")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2STrainingError("stratum receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "centered_sum_squares_numerator": self.centered_sum_squares_numerator,
            "channel": self.channel,
            "inverse_variance_weight_hex": self.inverse_variance_weight.hex(),
            "role": self.role,
            "sample_count": self.sample_count,
            "schema_version": STRATUM_LOSS_RECEIPT_VERSION,
            "target_numerator_sum": self.target_numerator_sum,
            "target_numerator_sum_squares": self.target_numerator_sum_squares,
            "target_scale_exponent": TARGET_SCALE_EXPONENT,
            "variance_definition": (
                "POPULATION_VARIANCE=(N*SUMSQ-SUM^2)/(N^2*2^(2*SCALE_EXPONENT))"
            ),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class OptimizationHistoryEntry:
    """One immutable checkpoint trace entry; update zero has no gradient."""

    update: int
    train_loss: float
    dev_loss: float
    gradient_norm: float | None
    clipped: bool
    improved: bool
    parameters_sha256: str

    def __post_init__(self) -> None:
        if type(self.update) is not int or self.update < 0:
            raise SWM0WS2STrainingError("history update must be non-negative integer")
        _finite_nonnegative(self.train_loss, "history train loss")
        _finite_nonnegative(self.dev_loss, "history dev loss")
        if type(self.clipped) is not bool or type(self.improved) is not bool:
            raise SWM0WS2STrainingError("history flags must be exact bools")
        _require_sha256(self.parameters_sha256, "history parameter SHA")
        if self.update == 0:
            if self.gradient_norm is not None or self.clipped or not self.improved:
                raise SWM0WS2STrainingError(
                    "epoch-zero history must be improved, unclipped, and gradient-free"
                )
        else:
            if self.gradient_norm is None:
                raise SWM0WS2STrainingError(
                    "post-update history requires a global gradient norm"
                )
            _finite_nonnegative(self.gradient_norm, "history gradient norm")

    def canonical(self) -> dict[str, Any]:
        return {
            "clipped": self.clipped,
            "dev_loss_hex": self.dev_loss.hex(),
            "gradient_norm_hex": (
                None if self.gradient_norm is None else self.gradient_norm.hex()
            ),
            "improved": self.improved,
            "parameters_sha256": self.parameters_sha256,
            "schema_version": HISTORY_ENTRY_VERSION,
            "train_loss_hex": self.train_loss.hex(),
            "update": self.update,
        }


def _history_sha256(history: tuple[OptimizationHistoryEntry, ...]) -> str:
    return canonical_sha256(
        {
            "entries": [entry.canonical() for entry in history],
            "schema_version": HISTORY_VERSION,
        }
    )


def _loss_definition_sha256(strata: tuple[StratumLossReceipt, ...]) -> str:
    return canonical_sha256(
        {
            "aggregation": "MEAN_OF_SIX_ROLE_CHANNEL_NORMALIZED_MSE_STRATA",
            "dev_weight_source": "EXACT_COMPLETE_TRAIN_TARGET_NUMERATORS_ONLY",
            "schema_version": LOSS_DEFINITION_VERSION,
            "strata": [receipt.canonical() for receipt in strata],
            "target_scale_exponent": TARGET_SCALE_EXPONENT,
        }
    )


def _optimization_unsigned_payload(values: Mapping[str, Any]) -> dict[str, Any]:
    arm = values["arm"]
    config = values["config"]
    termination = values["termination_reason"]
    strata = values["stratum_loss_receipts"]
    assert type(arm) is S2SArm
    assert type(config) is S2STrainingConfig
    assert type(termination) is TerminationReason
    assert type(strata) is tuple
    return {
        "arm": arm.value,
        "best_dev_loss_hex": values["best_dev_loss"].hex(),
        "best_parameters_sha256": values["best_parameters_sha256"],
        "best_train_loss_hex": values["best_train_loss"].hex(),
        "best_update": values["best_update"],
        "clipped_update_count": values["clipped_update_count"],
        "config": config.canonical(),
        "dataset_bytes_version": DATASET_BYTES_VERSION,
        "dataset_schema_sha256": values["dataset_schema_sha256"],
        "dev_case_count": values["dev_case_count"],
        "dev_dataset_sha256": values["dev_dataset_sha256"],
        "family_certificate_sha256": values["family_certificate_sha256"],
        "family_definition_sha256": values["family_definition_sha256"],
        "history_entry_count": values["history_entry_count"],
        "history": [entry.canonical() for entry in values["history"]],
        "history_sha256": values["history_sha256"],
        "history_version": HISTORY_VERSION,
        "initial_parameters_sha256": values["initial_parameters_sha256"],
        "initialization_version": TRAINING_INITIALIZATION_VERSION,
        "loss_definition_sha256": values["loss_definition_sha256"],
        "optimizer_version": OPTIMIZER_VERSION,
        "operator_architecture_receipt_sha256": values[
            "operator_architecture_receipt_sha256"
        ],
        "schema_version": OPTIMIZATION_RECEIPT_VERSION,
        "receipt_assurance": RECEIPT_ASSURANCE,
        "scientific_status": SCIENTIFIC_STATUS,
        "stopped_update": values["stopped_update"],
        "stratum_loss_receipts": [receipt.canonical() for receipt in strata],
        "structural_target_sha256": values["structural_target_sha256"],
        "structural_task_sha256": values["structural_task_sha256"],
        "task_manifest_sha256": values["task_manifest_sha256"],
        "task_spec": values["task"].canonical(),
        "termination_reason": termination.value,
        "train_case_count": values["train_case_count"],
        "train_dataset_sha256": values["train_dataset_sha256"],
        "training_version": TRAINING_VERSION,
        "update_count": values["update_count"],
    }


@dataclass(frozen=True, slots=True)
class S2SOptimizationReceipt:
    """Content-addressed receipt containing no test cases, targets, or metrics.

    The exact task manifest is evaluator provenance and necessarily names the
    frozen three-way split law; only the train/dev dataset hashes and losses
    are present.
    """

    arm: S2SArm
    config: S2STrainingConfig
    task: TaskSpecV2
    family_definition_sha256: str
    family_certificate_sha256: str
    structural_target_sha256: str
    structural_task_sha256: str
    task_manifest_sha256: str
    train_dataset_sha256: str
    dev_dataset_sha256: str
    dataset_schema_sha256: str
    train_case_count: int
    dev_case_count: int
    stratum_loss_receipts: tuple[StratumLossReceipt, ...]
    loss_definition_sha256: str
    operator_architecture_receipt_sha256: str
    initial_parameters_sha256: str
    best_parameters_sha256: str
    best_update: int
    stopped_update: int
    best_train_loss: float
    best_dev_loss: float
    update_count: int
    clipped_update_count: int
    history: tuple[OptimizationHistoryEntry, ...]
    history_entry_count: int
    history_sha256: str
    termination_reason: TerminationReason
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.arm) is not S2SArm or type(self.config) is not S2STrainingConfig:
            raise SWM0WS2STrainingError(
                "optimization receipt requires exact arm and config types"
            )
        if type(self.task) is not TaskSpecV2:
            raise SWM0WS2STrainingError("optimization receipt requires exact TaskSpecV2")
        for name in (
            "family_definition_sha256",
            "family_certificate_sha256",
            "structural_target_sha256",
            "structural_task_sha256",
            "task_manifest_sha256",
            "train_dataset_sha256",
            "dev_dataset_sha256",
            "dataset_schema_sha256",
            "loss_definition_sha256",
            "operator_architecture_receipt_sha256",
            "initial_parameters_sha256",
            "best_parameters_sha256",
            "history_sha256",
            "receipt_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        if self.family_definition_sha256 != FAMILY_DEFINITION_SHA256:
            raise SWM0WS2STrainingError("optimization receipt family definition drifted")
        if self.family_certificate_sha256 != FAMILY_CERTIFICATE_SHA256:
            raise SWM0WS2STrainingError("optimization receipt family certificate drifted")
        task_bindings = (
            (self.family_definition_sha256, self.task.family_definition_sha256),
            (self.family_certificate_sha256, self.task.family_certificate_sha256),
            (self.structural_target_sha256, self.task.structural_target_sha256),
            (self.structural_task_sha256, self.task.structural_task_sha256),
            (self.task_manifest_sha256, self.task.manifest_sha256),
        )
        if any(receipt_value != task_value for receipt_value, task_value in task_bindings):
            raise SWM0WS2STrainingError("optimization receipt task bindings disagree")
        if self.dataset_schema_sha256 != DATASET_SCHEMA_SHA256:
            raise SWM0WS2STrainingError("optimization receipt dataset schema drifted")
        if (
            self.operator_architecture_receipt_sha256
            != architecture_receipt(self.arm).receipt_sha256
        ):
            raise SWM0WS2STrainingError(
                "optimization receipt operator architecture drifted"
            )
        expected_initial_sha256 = _parameter_sha256(
            self.arm, _training_initial_parameters(self.arm, self.config.seed)
        )
        if self.initial_parameters_sha256 != expected_initial_sha256:
            raise SWM0WS2STrainingError(
                "optimization receipt deterministic initialization drifted"
            )
        # TaskSpecV2 determines both complete allowed datasets and the exact
        # train-only objective.  Recompute them here so an attacker cannot
        # replace semantic claims merely by recomputing the outer receipt hash.
        expected_data = _compiled_task_data(self.task)
        if (
            self.train_dataset_sha256 != expected_data.train_dataset_sha256
            or self.dev_dataset_sha256 != expected_data.dev_dataset_sha256
        ):
            raise SWM0WS2STrainingError(
                "optimization receipt dataset hashes disagree with its task"
            )
        if self.stratum_loss_receipts != expected_data.strata:
            raise SWM0WS2STrainingError(
                "optimization receipt train-only loss strata disagree with its task"
            )
        if type(self.train_case_count) is not int or self.train_case_count != _TRAIN_CASE_COUNT:
            raise SWM0WS2STrainingError("optimization receipt train count is incomplete")
        if type(self.dev_case_count) is not int or self.dev_case_count != _DEV_CASE_COUNT:
            raise SWM0WS2STrainingError("optimization receipt dev count is incomplete")
        if type(self.stratum_loss_receipts) is not tuple or len(self.stratum_loss_receipts) != 6:
            raise SWM0WS2STrainingError("optimization receipt requires six loss strata")
        if any(type(item) is not StratumLossReceipt for item in self.stratum_loss_receipts):
            raise SWM0WS2STrainingError("loss strata require exact receipt types")
        if tuple((item.role, item.channel) for item in self.stratum_loss_receipts) != tuple(
            (role, channel)
            for role in range(_ROLE_COUNT)
            for channel in range(_CHANNEL_COUNT)
        ):
            raise SWM0WS2STrainingError("loss strata are not in canonical role/channel order")
        if self.loss_definition_sha256 != _loss_definition_sha256(
            self.stratum_loss_receipts
        ):
            raise SWM0WS2STrainingError("loss definition hash mismatch")
        if (
            type(self.stopped_update) is not int
            or type(self.update_count) is not int
            or self.update_count < 0
            or self.stopped_update != self.update_count
            or self.update_count > self.config.max_updates
        ):
            raise SWM0WS2STrainingError("optimization update indices are inconsistent")
        if type(self.history) is not tuple or any(
            type(entry) is not OptimizationHistoryEntry for entry in self.history
        ):
            raise SWM0WS2STrainingError("history requires exact immutable entries")
        if (
            type(self.history_entry_count) is not int
            or self.history_entry_count != self.update_count + 1
            or len(self.history) != self.history_entry_count
            or tuple(entry.update for entry in self.history)
            != tuple(range(self.update_count + 1))
        ):
            raise SWM0WS2STrainingError(
                "history must contain epoch zero and every sequential update"
            )
        if self.history_sha256 != _history_sha256(self.history):
            raise SWM0WS2STrainingError("optimization history hash mismatch")
        if self.history[0].parameters_sha256 != self.initial_parameters_sha256:
            raise SWM0WS2STrainingError(
                "epoch-zero history does not bind deterministic initialization"
            )
        _finite_nonnegative(self.best_train_loss, "best_train_loss")
        _finite_nonnegative(self.best_dev_loss, "best_dev_loss")
        if type(self.termination_reason) is not TerminationReason:
            raise SWM0WS2STrainingError("termination reason must be exact")

        running_best = self.history[0]
        stale_updates = 0
        patience_reached_at: int | None = None
        for entry in self.history[1:]:
            assert entry.gradient_norm is not None
            if entry.clipped != (entry.gradient_norm > self.config.gradient_clip):
                raise SWM0WS2STrainingError(
                    "history clipping flag disagrees with the global norm"
                )
            expected_improved = (
                entry.dev_loss < running_best.dev_loss - self.config.min_delta
            )
            if entry.improved is not expected_improved:
                raise SWM0WS2STrainingError(
                    "history improvement flag disagrees with strict min_delta"
                )
            if expected_improved:
                running_best = entry
                stale_updates = 0
            else:
                stale_updates += 1
                if stale_updates >= self.config.patience:
                    patience_reached_at = entry.update
                    if entry.update != self.update_count:
                        raise SWM0WS2STrainingError(
                            "history continues after patience was exhausted"
                        )
        if type(self.clipped_update_count) is not int or self.clipped_update_count != sum(
            int(entry.clipped) for entry in self.history[1:]
        ):
            raise SWM0WS2STrainingError("clipped update count is inconsistent")
        if type(self.best_update) is not int or self.best_update != running_best.update:
            raise SWM0WS2STrainingError("best update disagrees with earliest strict minimum")
        if self.best_train_loss.hex() != running_best.train_loss.hex() or (
            self.best_dev_loss.hex() != running_best.dev_loss.hex()
        ):
            raise SWM0WS2STrainingError("best losses disagree with selected history entry")
        if self.best_parameters_sha256 != running_best.parameters_sha256:
            raise SWM0WS2STrainingError(
                "best parameter state disagrees with selected history entry"
            )
        if (self.best_update == 0) != (
            self.best_parameters_sha256 == self.initial_parameters_sha256
        ):
            raise SWM0WS2STrainingError(
                "epoch-zero selection and best parameter identity disagree"
            )
        expected_termination = (
            TerminationReason.PATIENCE
            if patience_reached_at == self.update_count
            else TerminationReason.MAX_UPDATES
        )
        if self.termination_reason is not expected_termination:
            raise SWM0WS2STrainingError(
                "termination reason disagrees with the complete history"
            )
        if (
            expected_termination is TerminationReason.MAX_UPDATES
            and self.update_count != self.config.max_updates
        ):
            raise SWM0WS2STrainingError("MAX_UPDATES reason disagrees with update count")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2STrainingError("optimization receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return _optimization_unsigned_payload(
            {name: getattr(self, name) for name in self.__dataclass_fields__}
        )

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class LearnedS2SOperator:
    """A fitted wrapper; ``learned`` is true only for a changed best checkpoint."""

    arm: S2SArm
    config: S2STrainingConfig
    parameters: Mapping[str, np.ndarray]
    optimization: S2SOptimizationReceipt

    def __post_init__(self) -> None:
        if type(self.arm) is not S2SArm:
            raise SWM0WS2STrainingError("learned operator arm must be exact S2SArm")
        if type(self.config) is not S2STrainingConfig:
            raise SWM0WS2STrainingError("learned operator config must be exact")
        if type(self.optimization) is not S2SOptimizationReceipt:
            raise SWM0WS2STrainingError("learned operator requires an exact training receipt")
        if self.optimization.arm is not self.arm or self.optimization.config != self.config:
            raise SWM0WS2STrainingError("training receipt does not bind arm/config")
        try:
            base = S2SOperator(self.arm, self.parameters)
        except SWM0WS2SOperatorError as exc:
            raise SWM0WS2STrainingError("learned operator parameters are malformed") from exc
        if base.parameters_sha256 != self.optimization.best_parameters_sha256:
            raise SWM0WS2STrainingError("learned parameters do not match the best-state receipt")
        expected_data = _compiled_task_data(self.optimization.task)
        observed_train_loss = _loss_for_parameters(
            self.arm,
            base.parameters,
            expected_data.train_x,
            expected_data.train_targets,
            expected_data.weights,
        )
        observed_dev_loss = _loss_for_parameters(
            self.arm,
            base.parameters,
            expected_data.dev_x,
            expected_data.dev_targets,
            expected_data.weights,
        )
        if (
            observed_train_loss.hex() != self.optimization.best_train_loss.hex()
            or observed_dev_loss.hex() != self.optimization.best_dev_loss.hex()
        ):
            raise SWM0WS2STrainingError(
                "learned best-state losses disagree with bound task and parameters"
            )
        object.__setattr__(self, "parameters", base.parameters)

    @property
    def learned(self) -> bool:
        return (
            self.optimization.best_update > 0
            and self.optimization.best_parameters_sha256
            != self.optimization.initial_parameters_sha256
        )

    @property
    def fitted(self) -> bool:
        return True

    @property
    def parameter_count(self) -> int:
        return sum(int(value.size) for value in self.parameters.values())

    @property
    def parameters_sha256(self) -> str:
        return self.optimization.best_parameters_sha256

    @property
    def task_binding_sha256(self) -> str:
        return self.optimization.structural_task_sha256

    @property
    def state_sha256(self) -> str:
        return canonical_sha256(
            {
                "arm": self.arm.value,
                "fitted": self.fitted,
                "learned": self.learned,
                "optimization_receipt_sha256": self.optimization.receipt_sha256,
                "parameters_sha256": self.parameters_sha256,
                "receipt_assurance": RECEIPT_ASSURANCE,
                "schema_version": TRAINING_VERSION,
                "scientific_status": SCIENTIFIC_STATUS,
                "structural_task_sha256": self.task_binding_sha256,
            }
        )

    def as_unlabeled_operator(self) -> S2SOperator:
        """Return the numeric core; its base type intentionally says learned=False."""

        return S2SOperator(self.arm, self.parameters)

    def forward(self, presweep: np.ndarray) -> np.ndarray:
        return operator_forward(self.as_unlabeled_operator(), presweep)

    def predict_world(self, world: ModelWorldV1) -> np.ndarray:
        if type(world) is not ModelWorldV1:
            raise SWM0WS2STrainingError("prediction requires exact ModelWorldV1")
        return self.forward(compile_model_world(world))


def _random_feature_tensor(name: str, shape: tuple[int, ...], seed: int) -> np.ndarray:
    descriptor = canonical_sha256(
        {
            "name": name,
            "schema_version": TRAINING_INITIALIZATION_VERSION,
            "seed": seed,
            "shape": list(shape),
        }
    ).encode("ascii")
    digest = hashlib.sha256(_INITIALIZATION_DOMAIN + descriptor).digest()
    rng = np.random.Generator(np.random.PCG64(int.from_bytes(digest[:16], "big")))
    fan_in, fan_out = shape[-2:]
    limit = math.sqrt(6.0 / (fan_in + fan_out))
    return rng.uniform(-limit, limit, size=shape).astype(np.float64)


def _training_initial_parameters(arm: S2SArm, seed: int) -> dict[str, np.ndarray]:
    shapes = parameter_shapes(arm)
    parameters = {
        name: np.zeros(shape, dtype=np.float64) for name, shape in shapes.items()
    }
    random_names = (
        ("eta_w", "hidden1_w", "hidden2_w")
        if arm is S2SArm.DS870
        else ("phi_w", "psi_w")
    )
    for name in random_names:
        parameters[name] = _random_feature_tensor(name, shapes[name], seed)
    return parameters


def initialize_training_operator(
    arm: S2SArm | str, *, seed: int
) -> S2SOperator:
    """Build the versioned task-independent, exact-zero-output initializer."""

    selected = _coerce_arm(arm)
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise SWM0WS2STrainingError("seed must be an exact unsigned 64-bit integer")
    return S2SOperator(selected, _training_initial_parameters(selected, seed))


def _validate_case_tuple(
    task: TaskSpecV2,
    cases: object,
    *,
    split: str,
    expected_count: int,
) -> tuple[EvaluatorCaseV2, ...]:
    if type(cases) is not tuple:
        raise SWM0WS2STrainingError(f"{split} cases must be an exact immutable tuple")
    if len(cases) != expected_count:
        raise SWM0WS2STrainingError(
            f"{split} cases must contain the complete {expected_count}-world split"
        )
    by_world: dict[tuple[int, int, int, int, int, int], EvaluatorCaseV2] = {}
    for case in cases:
        if type(case) is not EvaluatorCaseV2:
            raise SWM0WS2STrainingError(f"{split} cases require exact EvaluatorCaseV2")
        if case.task != task:
            raise SWM0WS2STrainingError(f"{split} case belongs to a different task")
        if case.split != split:
            raise SWM0WS2STrainingError(f"{split} tuple contains {case.split!r} leakage")
        key = case.world.raw_values
        if key in by_world:
            raise SWM0WS2STrainingError(f"{split} tuple contains a duplicate world")
        by_world[key] = case
    # Every accepted case is type-validated by EvaluatorCaseV2 and belongs to
    # this split.  Exact fixed split cardinality plus uniqueness proves
    # completeness; sorting removes caller order as an optimization degree of
    # freedom.
    return tuple(by_world[key] for key in sorted(by_world))


def _validate_training_boundary(
    task: object,
    train_cases: object,
    dev_cases: object,
) -> tuple[TaskSpecV2, tuple[EvaluatorCaseV2, ...], tuple[EvaluatorCaseV2, ...]]:
    if type(task) is not TaskSpecV2:
        raise SWM0WS2STrainingError("training requires an exact TaskSpecV2")
    train = _validate_case_tuple(
        task, train_cases, split="train", expected_count=_TRAIN_CASE_COUNT
    )
    dev = _validate_case_tuple(
        task, dev_cases, split="dev", expected_count=_DEV_CASE_COUNT
    )
    if set(case.world.raw_values for case in train).intersection(
        case.world.raw_values for case in dev
    ):
        raise SWM0WS2STrainingError("train and dev worlds must be disjoint")
    return task, train, dev


def _dataset_sha256(
    task: TaskSpecV2, cases: tuple[EvaluatorCaseV2, ...], split: str
) -> str:
    digest = hashlib.sha256(_DATASET_HASH_DOMAIN)
    digest.update(bytes.fromhex(DATASET_SCHEMA_SHA256))
    digest.update(bytes.fromhex(task.structural_task_sha256))
    split_bytes = split.encode("ascii")
    digest.update(len(split_bytes).to_bytes(1, "big"))
    digest.update(split_bytes)
    digest.update(len(cases).to_bytes(8, "big"))
    for case in cases:
        digest.update(bytes(case.world.raw_values))
        for row in case.target_numerators:
            for value in row:
                digest.update(int(value).to_bytes(8, "big", signed=True))
    # Bind the exact numeric tensors consumed by the optimizer as canonical
    # little-endian float64 C-order bytes in addition to their integer source.
    compiled = (
        compile_model_worlds(tuple(case.world for case in cases)),
        compile_case_target_batch_v2(cases),
    )
    for value in compiled:
        payload = np.asarray(value, dtype="<f8", order="C").tobytes(order="C")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _build_stratum_loss_receipts(
    train_cases: tuple[EvaluatorCaseV2, ...],
) -> tuple[StratumLossReceipt, ...]:
    receipts: list[StratumLossReceipt] = []
    for role in range(_ROLE_COUNT):
        for channel in range(_CHANNEL_COUNT):
            values = tuple(
                int(case.target_numerators[2 * role + member][channel])
                for case in train_cases
                for member in range(_MEMBER_COUNT)
            )
            count = len(values)
            numerator_sum = sum(values, 0)
            numerator_sum_squares = sum((value * value for value in values), 0)
            centered = count * numerator_sum_squares - numerator_sum * numerator_sum
            weight = float(
                Fraction(
                    count * count * 2 ** (2 * TARGET_SCALE_EXPONENT), centered
                )
            )
            unsigned = {
                "centered_sum_squares_numerator": centered,
                "channel": channel,
                "inverse_variance_weight_hex": weight.hex(),
                "role": role,
                "sample_count": count,
                "schema_version": STRATUM_LOSS_RECEIPT_VERSION,
                "target_numerator_sum": numerator_sum,
                "target_numerator_sum_squares": numerator_sum_squares,
                "target_scale_exponent": TARGET_SCALE_EXPONENT,
                "variance_definition": (
                    "POPULATION_VARIANCE=(N*SUMSQ-SUM^2)/(N^2*2^(2*SCALE_EXPONENT))"
                ),
            }
            receipts.append(
                StratumLossReceipt(
                    role=role,
                    channel=channel,
                    sample_count=count,
                    target_numerator_sum=numerator_sum,
                    target_numerator_sum_squares=numerator_sum_squares,
                    centered_sum_squares_numerator=centered,
                    inverse_variance_weight=weight,
                    receipt_sha256=canonical_sha256(unsigned),
                )
            )
    return tuple(receipts)


def _weight_matrix(strata: tuple[StratumLossReceipt, ...]) -> np.ndarray:
    weights = np.empty((_ROLE_COUNT, _CHANNEL_COUNT), dtype=np.float64)
    for receipt in strata:
        weights[receipt.role, receipt.channel] = receipt.inverse_variance_weight
    if not np.isfinite(weights).all() or np.any(weights <= 0.0):
        raise SWM0WS2STrainingError("loss weights must be finite and positive")
    return weights


@dataclass(frozen=True, slots=True)
class _CompiledTaskData:
    train_dataset_sha256: str
    dev_dataset_sha256: str
    strata: tuple[StratumLossReceipt, ...]
    weights: np.ndarray
    train_x: np.ndarray
    train_targets: np.ndarray
    dev_x: np.ndarray
    dev_targets: np.ndarray


@lru_cache(maxsize=32)
def _compiled_task_data(task: TaskSpecV2) -> _CompiledTaskData:
    """Regenerate only complete train/dev data; the test partition is untouched."""

    if type(task) is not TaskSpecV2:
        raise SWM0WS2STrainingError("compiled task data requires exact TaskSpecV2")
    train = tuple(task.iter_cases("train"))
    dev = tuple(task.iter_cases("dev"))
    strata = _build_stratum_loss_receipts(train)
    mutable_weights = _weight_matrix(strata)
    weights = np.frombuffer(
        mutable_weights.tobytes(order="C"), dtype=np.float64
    ).reshape(mutable_weights.shape)
    return _CompiledTaskData(
        train_dataset_sha256=_dataset_sha256(task, train, "train"),
        dev_dataset_sha256=_dataset_sha256(task, dev, "dev"),
        strata=strata,
        weights=weights,
        train_x=compile_model_worlds(tuple(case.world for case in train)),
        train_targets=compile_case_target_batch_v2(train),
        dev_x=compile_model_worlds(tuple(case.world for case in dev)),
        dev_targets=compile_case_target_batch_v2(dev),
    )


def _require_training_arrays(
    x: object, targets: object, weights: object
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if (
        type(x) is not np.ndarray
        or x.dtype != _FLOAT64_DTYPE
        or x.ndim != 4
        or x.shape[1:] != (3, 2, 4)
        or len(x) == 0
        or not np.isfinite(x).all()
    ):
        raise SWM0WS2STrainingError("training input must be finite float64 (N,3,2,4)")
    if (
        type(targets) is not np.ndarray
        or targets.dtype != _FLOAT64_DTYPE
        or targets.shape != (len(x), 3, 2, 2)
        or not np.isfinite(targets).all()
    ):
        raise SWM0WS2STrainingError("training targets must be finite float64 (N,3,2,2)")
    if (
        type(weights) is not np.ndarray
        or weights.dtype != _FLOAT64_DTYPE
        or weights.shape != (3, 2)
        or not np.isfinite(weights).all()
        or np.any(weights <= 0.0)
    ):
        raise SWM0WS2STrainingError("training weights must be positive float64 (3,2)")
    return x, targets, weights


def _t_or_p_forward_cache(
    arm: S2SArm, parameters: Mapping[str, np.ndarray], x: np.ndarray
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    u = np.einsum("nrmd,rdh->nrmh", x, parameters["phi_w"])
    encoded = np.einsum("nrmd,rdh->nrmh", x, parameters["psi_w"])
    role_sums = encoded.sum(axis=2)
    v = np.broadcast_to(
        role_sums[:, None, None, :, :],
        (len(x), _ROLE_COUNT, _MEMBER_COUNT, _ROLE_COUNT, u.shape[-1]),
    ).copy()
    for role in range(_ROLE_COUNT):
        v[:, role, 0, role, :] = encoded[:, role, 1, :]
        v[:, role, 1, role, :] = encoded[:, role, 0, :]
    prediction = np.einsum("nrmh,rch->nrmc", u, parameters["unary_w"])
    pair_features = u[:, :, :, None, :] * v
    prediction += np.einsum(
        "nrmsh,rsch->nrmc", pair_features, parameters["pair_w"]
    )
    cache = {"encoded": encoded, "pair_features": pair_features, "u": u, "v": v}
    if arm is S2SArm.T16:
        q_product = np.prod(v, axis=3)
        q_features = u * q_product
        prediction += np.einsum("nrmh,rch->nrmc", q_features, parameters["q_w"])
        cache["q_features"] = q_features
        cache["q_product"] = q_product
    prediction += parameters["out_b"][None, :, None, :]
    return prediction, cache


def _ds_forward_cache(
    parameters: Mapping[str, np.ndarray], x: np.ndarray
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    eta_pre = (
        np.einsum("nrmd,rdk->nrmk", x, parameters["eta_w"])
        + parameters["eta_b"][None, :, None, :]
    )
    learned_eta = np.tanh(eta_pre)
    eta = np.concatenate((x, learned_eta), axis=-1)
    summaries = eta.sum(axis=2).reshape(len(x), 24)
    summary_fields = np.broadcast_to(
        summaries[:, None, None, :], (len(x), 3, 2, 24)
    )
    role_codes = np.asarray(
        ((1.0, 0.0), (0.0, 1.0), (-1.0, -1.0)), dtype=np.float64
    )
    role_codes = np.broadcast_to(role_codes[None, :, None, :], (len(x), 3, 2, 2))
    decoder = np.concatenate((x, summary_fields, role_codes), axis=-1)
    hidden1 = np.tanh(
        np.einsum("nrmf,fh->nrmh", decoder, parameters["hidden1_w"])
        + parameters["hidden1_b"]
    )
    hidden2 = np.tanh(
        np.einsum("nrmf,fh->nrmh", hidden1, parameters["hidden2_w"])
        + parameters["hidden2_b"]
    )
    prediction = (
        np.einsum("nrmh,hc->nrmc", hidden2, parameters["out_w"])
        + parameters["out_b"]
    )
    return prediction, {
        "decoder": decoder,
        "hidden1": hidden1,
        "hidden2": hidden2,
        "learned_eta": learned_eta,
    }


def _forward_with_cache(
    arm: S2SArm,
    parameters: Mapping[str, np.ndarray],
    x: np.ndarray,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    prediction, cache = (
        _ds_forward_cache(parameters, x)
        if arm is S2SArm.DS870
        else _t_or_p_forward_cache(arm, parameters, x)
    )
    if prediction.shape != (len(x), 3, 2, 2) or not np.isfinite(prediction).all():
        raise SWM0WS2STrainingError("training forward pass produced non-finite output")
    return prediction, cache


def _weighted_loss(
    prediction: np.ndarray, targets: np.ndarray, weights: np.ndarray
) -> float:
    if prediction.shape != targets.shape:
        raise SWM0WS2STrainingError("prediction and target shapes disagree")
    with np.errstate(over="raise", invalid="raise"):
        try:
            residual = prediction - targets
            loss = float(
                np.sum(
                    residual
                    * residual
                    * weights[None, :, None, :],
                    dtype=np.float64,
                )
                / (_STRATUM_COUNT * len(prediction) * _MEMBER_COUNT)
            )
        except FloatingPointError as exc:
            raise SWM0WS2STrainingError("non-finite weighted loss") from exc
    if not math.isfinite(loss) or loss < 0.0:
        raise SWM0WS2STrainingError("weighted loss must be finite and non-negative")
    return loss


def _t_or_p_gradients(
    arm: S2SArm,
    parameters: Mapping[str, np.ndarray],
    x: np.ndarray,
    derivative: np.ndarray,
    cache: Mapping[str, np.ndarray],
) -> dict[str, np.ndarray]:
    u = cache["u"]
    v = cache["v"]
    gradients: dict[str, np.ndarray] = {
        "unary_w": np.einsum("nrmc,nrmh->rch", derivative, u),
        "pair_w": np.einsum(
            "nrmc,nrmsh->rsch", derivative, cache["pair_features"]
        ),
        "out_b": derivative.sum(axis=(0, 2)),
    }
    grad_u = np.einsum("nrmc,rch->nrmh", derivative, parameters["unary_w"])
    grad_u += np.einsum(
        "nrmc,rsch,nrmsh->nrmh", derivative, parameters["pair_w"], v
    )
    grad_v = np.einsum(
        "nrmc,rsch,nrmh->nrmsh", derivative, parameters["pair_w"], u
    )
    if arm is S2SArm.T16:
        gradients["q_w"] = np.einsum(
            "nrmc,nrmh->rch", derivative, cache["q_features"]
        )
        weighted_q = np.einsum("nrmc,rch->nrmh", derivative, parameters["q_w"])
        grad_u += weighted_q * cache["q_product"]
        for source in range(_ROLE_COUNT):
            other_sources = tuple(index for index in range(_ROLE_COUNT) if index != source)
            grad_v[:, :, :, source, :] += (
                weighted_q
                * u
                * v[:, :, :, other_sources[0], :]
                * v[:, :, :, other_sources[1], :]
            )

    grad_encoded = np.zeros_like(cache["encoded"])
    for recipient_role in range(_ROLE_COUNT):
        for member in range(_MEMBER_COUNT):
            for source_role in range(_ROLE_COUNT):
                contribution = grad_v[:, recipient_role, member, source_role, :]
                if source_role == recipient_role:
                    grad_encoded[:, source_role, 1 - member, :] += contribution
                else:
                    grad_encoded[:, source_role, 0, :] += contribution
                    grad_encoded[:, source_role, 1, :] += contribution
    gradients["phi_w"] = np.einsum("nrmd,nrmh->rdh", x, grad_u)
    gradients["psi_w"] = np.einsum("nrmd,nrmh->rdh", x, grad_encoded)
    return gradients


def _ds_gradients(
    parameters: Mapping[str, np.ndarray],
    x: np.ndarray,
    derivative: np.ndarray,
    cache: Mapping[str, np.ndarray],
) -> dict[str, np.ndarray]:
    hidden1 = cache["hidden1"]
    hidden2 = cache["hidden2"]
    gradients: dict[str, np.ndarray] = {
        "out_w": np.einsum("nrmh,nrmc->hc", hidden2, derivative),
        "out_b": derivative.sum(axis=(0, 1, 2)),
    }
    grad_hidden2 = np.einsum("nrmc,hc->nrmh", derivative, parameters["out_w"])
    grad_pre2 = grad_hidden2 * (1.0 - hidden2 * hidden2)
    gradients["hidden2_w"] = np.einsum("nrmf,nrmh->fh", hidden1, grad_pre2)
    gradients["hidden2_b"] = grad_pre2.sum(axis=(0, 1, 2))
    grad_hidden1 = np.einsum(
        "nrmh,fh->nrmf", grad_pre2, parameters["hidden2_w"]
    )
    grad_pre1 = grad_hidden1 * (1.0 - hidden1 * hidden1)
    gradients["hidden1_w"] = np.einsum(
        "nrmf,nrmh->fh", cache["decoder"], grad_pre1
    )
    gradients["hidden1_b"] = grad_pre1.sum(axis=(0, 1, 2))
    grad_decoder = np.einsum(
        "nrmh,fh->nrmf", grad_pre1, parameters["hidden1_w"]
    )
    grad_summary = grad_decoder[:, :, :, 4:28].sum(axis=(1, 2)).reshape(len(x), 3, 8)
    grad_learned_eta = np.broadcast_to(
        grad_summary[:, :, None, 4:8], cache["learned_eta"].shape
    )
    grad_eta_pre = grad_learned_eta * (
        1.0 - cache["learned_eta"] * cache["learned_eta"]
    )
    gradients["eta_w"] = np.einsum("nrmd,nrmk->rdk", x, grad_eta_pre)
    gradients["eta_b"] = grad_eta_pre.sum(axis=(0, 2))
    return gradients


def _loss_and_gradients(
    arm: S2SArm,
    parameters: Mapping[str, np.ndarray],
    x: np.ndarray,
    targets: np.ndarray,
    weights: np.ndarray,
) -> tuple[float, dict[str, np.ndarray]]:
    x, targets, weights = _require_training_arrays(x, targets, weights)
    prediction, cache = _forward_with_cache(arm, parameters, x)
    loss = _weighted_loss(prediction, targets, weights)
    derivative = (
        (prediction - targets)
        * weights[None, :, None, :]
        / (_STRATUM_COUNT * len(x))
    )
    gradients = (
        _ds_gradients(parameters, x, derivative, cache)
        if arm is S2SArm.DS870
        else _t_or_p_gradients(arm, parameters, x, derivative, cache)
    )
    if set(gradients) != set(parameters):
        raise SWM0WS2STrainingError("analytic gradient schema mismatch")
    for name, gradient in gradients.items():
        if (
            type(gradient) is not np.ndarray
            or gradient.dtype != _FLOAT64_DTYPE
            or gradient.shape != parameters[name].shape
            or not np.isfinite(gradient).all()
        ):
            raise SWM0WS2STrainingError(f"non-finite or malformed gradient: {name}")
    return loss, gradients


def _clip_gradients(
    gradients: Mapping[str, np.ndarray], threshold: float
) -> tuple[dict[str, np.ndarray], float, bool]:
    with np.errstate(over="raise", invalid="raise"):
        try:
            squared = math.fsum(
                float(np.dot(value.reshape(-1), value.reshape(-1)))
                for value in gradients.values()
            )
            norm = math.sqrt(squared)
        except (FloatingPointError, OverflowError, ValueError) as exc:
            raise SWM0WS2STrainingError("non-finite global gradient norm") from exc
    if not math.isfinite(norm):
        raise SWM0WS2STrainingError("non-finite global gradient norm")
    clipped = norm > threshold
    scale = threshold / norm if clipped and norm > 0.0 else 1.0
    result = {name: value * scale for name, value in gradients.items()}
    if any(not np.isfinite(value).all() for value in result.values()):
        raise SWM0WS2STrainingError("gradient clipping produced non-finite values")
    return result, norm, clipped


def _loss_for_parameters(
    arm: S2SArm,
    parameters: Mapping[str, np.ndarray],
    x: np.ndarray,
    targets: np.ndarray,
    weights: np.ndarray,
) -> float:
    prediction, _ = _forward_with_cache(arm, parameters, x)
    return _weighted_loss(prediction, targets, weights)


def fit_task_operator(
    task: TaskSpecV2,
    train_cases: tuple[EvaluatorCaseV2, ...],
    dev_cases: tuple[EvaluatorCaseV2, ...],
    *,
    arm: S2SArm | str,
    config: S2STrainingConfig,
) -> LearnedS2SOperator:
    """Fit one arm using complete V2 train/dev tuples and no test observations."""

    if type(config) is not S2STrainingConfig:
        raise SWM0WS2STrainingError("config must be exact S2STrainingConfig")
    selected = _coerce_arm(arm)
    task, train, dev = _validate_training_boundary(task, train_cases, dev_cases)
    data = _compiled_task_data(task)
    train_dataset_sha256 = _dataset_sha256(task, train, "train")
    dev_dataset_sha256 = _dataset_sha256(task, dev, "dev")
    if (
        train_dataset_sha256 != data.train_dataset_sha256
        or dev_dataset_sha256 != data.dev_dataset_sha256
    ):
        raise SWM0WS2STrainingError(
            "validated train/dev bytes disagree with canonical task regeneration"
        )
    train_x = data.train_x
    dev_x = data.dev_x
    train_targets = data.train_targets
    dev_targets = data.dev_targets
    strata = data.strata
    weights = data.weights

    parameters = _training_initial_parameters(selected, config.seed)
    initial_sha256 = _parameter_sha256(selected, parameters)
    moments = {name: np.zeros_like(value) for name, value in parameters.items()}
    variances = {name: np.zeros_like(value) for name, value in parameters.items()}

    best_train_loss = _loss_for_parameters(
        selected, parameters, train_x, train_targets, weights
    )
    best_dev_loss = _loss_for_parameters(
        selected, parameters, dev_x, dev_targets, weights
    )
    best_parameters = _parameter_copy(parameters)
    best_update = 0
    stale_updates = 0
    clipped_updates = 0
    history: list[OptimizationHistoryEntry] = [
        OptimizationHistoryEntry(
            update=0,
            train_loss=best_train_loss,
            dev_loss=best_dev_loss,
            gradient_norm=None,
            clipped=False,
            improved=True,
            parameters_sha256=initial_sha256,
        )
    ]
    termination = TerminationReason.MAX_UPDATES
    update_count = 0

    for update in range(1, config.max_updates + 1):
        _, gradients = _loss_and_gradients(
            selected, parameters, train_x, train_targets, weights
        )
        gradients, gradient_norm, clipped = _clip_gradients(
            gradients, config.gradient_clip
        )
        clipped_updates += int(clipped)
        update_count = update
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            try:
                for name in sorted(parameters):
                    gradient = gradients[name]
                    moments[name] = (
                        config.beta1 * moments[name]
                        + (1.0 - config.beta1) * gradient
                    )
                    variances[name] = (
                        config.beta2 * variances[name]
                        + (1.0 - config.beta2) * gradient * gradient
                    )
                    corrected_moment = moments[name] / (1.0 - config.beta1**update)
                    corrected_variance = variances[name] / (1.0 - config.beta2**update)
                    parameters[name] -= (
                        config.learning_rate
                        * corrected_moment
                        / (np.sqrt(corrected_variance) + config.epsilon)
                    )
            except FloatingPointError as exc:
                raise SWM0WS2STrainingError("Adam produced a non-finite state") from exc
        if any(not np.isfinite(value).all() for value in parameters.values()):
            raise SWM0WS2STrainingError("Adam produced a non-finite parameter")

        train_loss = _loss_for_parameters(
            selected, parameters, train_x, train_targets, weights
        )
        dev_loss = _loss_for_parameters(
            selected, parameters, dev_x, dev_targets, weights
        )
        improved = dev_loss < best_dev_loss - config.min_delta
        history.append(
            OptimizationHistoryEntry(
                update=update,
                train_loss=train_loss,
                dev_loss=dev_loss,
                gradient_norm=gradient_norm,
                clipped=clipped,
                improved=improved,
                parameters_sha256=_parameter_sha256(selected, parameters),
            )
        )
        if improved:
            best_train_loss = train_loss
            best_dev_loss = dev_loss
            best_parameters = _parameter_copy(parameters)
            best_update = update
            stale_updates = 0
        else:
            stale_updates += 1
            if stale_updates >= config.patience:
                termination = TerminationReason.PATIENCE
                break

    best_sha256 = _parameter_sha256(selected, best_parameters)
    loss_definition_sha256 = _loss_definition_sha256(strata)
    frozen_history = tuple(history)
    receipt_values: dict[str, Any] = {
        "arm": selected,
        "config": config,
        "task": task,
        "family_definition_sha256": task.family_definition_sha256,
        "family_certificate_sha256": task.family_certificate_sha256,
        "structural_target_sha256": task.structural_target_sha256,
        "structural_task_sha256": task.structural_task_sha256,
        "task_manifest_sha256": task.manifest_sha256,
        "train_dataset_sha256": train_dataset_sha256,
        "dev_dataset_sha256": dev_dataset_sha256,
        "dataset_schema_sha256": DATASET_SCHEMA_SHA256,
        "train_case_count": len(train),
        "dev_case_count": len(dev),
        "stratum_loss_receipts": strata,
        "loss_definition_sha256": loss_definition_sha256,
        "operator_architecture_receipt_sha256": architecture_receipt(
            selected
        ).receipt_sha256,
        "initial_parameters_sha256": initial_sha256,
        "best_parameters_sha256": best_sha256,
        "best_update": best_update,
        "stopped_update": update_count,
        "best_train_loss": best_train_loss,
        "best_dev_loss": best_dev_loss,
        "update_count": update_count,
        "clipped_update_count": clipped_updates,
        "history": frozen_history,
        "history_entry_count": len(frozen_history),
        "history_sha256": _history_sha256(frozen_history),
        "termination_reason": termination,
    }
    optimization = S2SOptimizationReceipt(
        **receipt_values,
        receipt_sha256=canonical_sha256(
            _optimization_unsigned_payload(receipt_values)
        ),
    )
    return LearnedS2SOperator(
        arm=selected,
        config=config,
        parameters=best_parameters,
        optimization=optimization,
    )


def replay_optimization(model: LearnedS2SOperator) -> LearnedS2SOperator:
    """Deterministically replay and exact-compare one fitted artifact.

    Receipt construction establishes a self-consistent content-addressed
    commitment, not authenticated execution provenance.  This replay is the
    executable verifier for the optimizer trajectory and restored best state.
    It regenerates only the complete train/dev partitions bound by the task.
    """

    if type(model) is not LearnedS2SOperator:
        raise SWM0WS2STrainingError("replay requires exact LearnedS2SOperator")
    task = model.optimization.task
    replay = fit_task_operator(
        task,
        tuple(task.iter_cases("train")),
        tuple(task.iter_cases("dev")),
        arm=model.arm,
        config=model.config,
    )
    if replay.optimization.canonical() != model.optimization.canonical():
        raise SWM0WS2STrainingError("deterministic optimization receipt replay mismatch")
    if set(replay.parameters) != set(model.parameters) or any(
        replay.parameters[name].tobytes(order="C")
        != model.parameters[name].tobytes(order="C")
        for name in replay.parameters
    ):
        raise SWM0WS2STrainingError("deterministic best parameter replay mismatch")
    if replay.state_sha256 != model.state_sha256:
        raise SWM0WS2STrainingError("deterministic learned-state replay mismatch")
    return replay


__all__ = [
    "ALL_ARMS",
    "DATASET_BYTES_VERSION",
    "DATASET_SCHEMA_SHA256",
    "HISTORY_VERSION",
    "HISTORY_ENTRY_VERSION",
    "LOSS_DEFINITION_VERSION",
    "LearnedS2SOperator",
    "OPTIMIZATION_RECEIPT_VERSION",
    "OPTIMIZER_VERSION",
    "OptimizationHistoryEntry",
    "RECEIPT_ASSURANCE",
    "S2SOptimizationReceipt",
    "S2STrainingConfig",
    "SCIENTIFIC_STATUS",
    "STRATUM_LOSS_RECEIPT_VERSION",
    "SWM0WS2STrainingError",
    "StratumLossReceipt",
    "TRAINING_INITIALIZATION_VERSION",
    "TRAINING_VERSION",
    "TerminationReason",
    "fit_task_operator",
    "initialize_training_operator",
    "replay_optimization",
]
