"""Candidate-only protocol core for the unjudged SWM-0W-S2S gate.

The module deliberately stops short of future-randomness acquisition,
chronology, preregistration, and an authoritative scientific verdict.  It
strictly serializes already-fitted artifacts, requires an explicit
fit/replay-equality receipt, evaluates the finite V2 test partition without
feeding evaluator fields to a model, and reduces exactly twenty indexed task
draws to a *candidate* outcome.

The task family samples with replacement from one fixed feature frame.  The
shared task bootstrap is therefore a conditional stability calculation under
that frozen generator, not evidence for independent mechanisms or feature
families.

Scientific status: ``CANDIDATE_PROTOCOL_ENGINEERING_ONLY_UNJUDGED``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import itertools
import json
import math
from typing import Any, Mapping, Sequence

import numpy as np

from hswm.experiments.swm0w_s2s_family import (
    FAMILY_CERTIFICATE_SHA256,
    FAMILY_DEFINITION_SHA256,
    GAIN_ORDER,
    SPLIT_COUNTS,
    SPLITS,
    TARGET_SCALE_EXPONENT,
    EvaluatorCaseV2,
    TaskBatchV2,
    TaskSpecV2,
)
from hswm.experiments.swm0w_s2s_operator import (
    ALL_ARMS,
    Q_REMOVAL_RECEIPT_VERSION,
    ROLE_CYCLES,
    QRemovalReceipt,
    S2SArm,
    S2SOperator,
    architecture_receipt,
    canonical_json,
    canonical_sha256,
    compile_case_target_batch_v2,
    compile_model_worlds,
    evaluate_both_role_cycles,
    parameter_shapes,
    remove_q,
    restore_q,
    stratified_r2,
    within_role_broadcast,
)
from hswm.experiments.swm0w_s2s_training import (
    DATASET_BYTES_VERSION,
    DATASET_SCHEMA_SHA256,
    HISTORY_ENTRY_VERSION,
    HISTORY_VERSION,
    LOSS_DEFINITION_VERSION,
    OPTIMIZATION_RECEIPT_VERSION,
    OPTIMIZER_VERSION,
    RECEIPT_ASSURANCE,
    SCIENTIFIC_STATUS as TRAINING_SCIENTIFIC_STATUS,
    STRATUM_LOSS_RECEIPT_VERSION,
    TRAINING_INITIALIZATION_VERSION,
    TRAINING_VERSION,
    LearnedS2SOperator,
    OptimizationHistoryEntry,
    S2SOptimizationReceipt,
    S2STrainingConfig,
    StratumLossReceipt,
    TerminationReason,
)
from hswm.experiments.swm0w_s2s_worlds import (
    ALL_MEMBER_PERMUTATIONS,
    CHANNELS,
    FIELD_ORDER,
    ROLES,
)


SCIENTIFIC_STATUS = "CANDIDATE_PROTOCOL_ENGINEERING_ONLY_UNJUDGED"
PROTOCOL_VERSION = "hswm-swm0w-s2s-candidate-protocol/v1"
PROTOCOL_CONFIG_VERSION = "hswm-swm0w-s2s-protocol-config/v1"
TASK_BATCH_ARCHIVE_VERSION = "hswm-swm0w-s2s-task-batch-archive/v1"
PARAMETER_TENSOR_VERSION = "hswm-swm0w-s2s-parameter-tensor/v1"
LEARNED_ARCHIVE_VERSION = "hswm-swm0w-s2s-learned-archive/v1"
FIT_REPLAY_VERSION = "hswm-swm0w-s2s-fit-replay/v1"
LEARNED_Q_INTERVENTION_VERSION = "hswm-swm0w-s2s-learned-q-intervention/v1"
SCORE_RECEIPT_VERSION = "hswm-swm0w-s2s-six-stratum-score/v1"
INTEGRITY_RECEIPT_VERSION = "hswm-swm0w-s2s-integrity/v1"
TASK_METRIC_VERSION = "hswm-swm0w-s2s-task-metrics/v1"
TASK_EVALUATION_VERSION = "hswm-swm0w-s2s-task-evaluation/v1"
FINAL_RECEIPT_VERSION = "hswm-swm0w-s2s-candidate-final/v1"

TASK_COUNT = 20
TEST_WORLD_COUNT = SPLIT_COUNTS["test"]
DOMAIN_WORLD_COUNT = FIELD_ORDER**6
STRATUM_SAMPLE_COUNT = TEST_WORLD_COUNT * 2
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20_260_820
BOOTSTRAP_QUANTILES = (0.05, 0.95)
PAIR_NULL_EPSILON = 2.0**-32
DEFAULT_SYMMETRY_ATOL = 2.0e-14
DEFAULT_SYMMETRY_RTOL = 2.0e-14
_SHA256_ALPHABET = frozenset("0123456789abcdef")


class SWM0WS2SProtocolError(ValueError):
    """Raised when a candidate protocol or canonical artifact drifts."""


class CandidateOutcome(str, Enum):
    CANDIDATE_PASS_AWAITING_BUNDLE = "CANDIDATE_PASS_AWAITING_BUNDLE"
    CANDIDATE_KILL_AWAITING_BUNDLE = "CANDIDATE_KILL_AWAITING_BUNDLE"
    CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE = (
        "CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE"
    )
    VOID = "VOID"


class ScoreVariant(str, Enum):
    T16_BASE = "T16_BASE"
    P_CAP18_BASE = "P_CAP18_BASE"
    DS870_BASE = "DS870_BASE"
    T16_Q_REMOVED = "T16_Q_REMOVED"
    T16_RESTORED = "T16_RESTORED"
    T16_BROADCAST = "T16_BROADCAST"
    T16_CYCLE_120 = "T16_CYCLE_120"
    T16_CYCLE_201 = "T16_CYCLE_201"


_VARIANT_ARM = {
    ScoreVariant.T16_BASE: S2SArm.T16,
    ScoreVariant.P_CAP18_BASE: S2SArm.P_CAP18,
    ScoreVariant.DS870_BASE: S2SArm.DS870,
    ScoreVariant.T16_Q_REMOVED: S2SArm.T16,
    ScoreVariant.T16_RESTORED: S2SArm.T16,
    ScoreVariant.T16_BROADCAST: S2SArm.T16,
    ScoreVariant.T16_CYCLE_120: S2SArm.T16,
    ScoreVariant.T16_CYCLE_201: S2SArm.T16,
}


def loads_canonical_json(payload: str) -> Any:
    """Decode exact canonical JSON while rejecting duplicate object keys."""

    if type(payload) is not str:
        raise SWM0WS2SProtocolError("canonical JSON payload must be an exact string")

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SWM0WS2SProtocolError(f"duplicate canonical JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise SWM0WS2SProtocolError(f"non-finite JSON constant is forbidden: {value}")

    try:
        result = json.loads(
            payload,
            object_pairs_hook=object_pairs,
            parse_constant=invalid_constant,
        )
    except (json.JSONDecodeError, TypeError) as exc:
        raise SWM0WS2SProtocolError("canonical JSON decoding failed") from exc
    _require_exact_json(result, "canonical JSON")
    if canonical_json(result) != payload:
        raise SWM0WS2SProtocolError("JSON payload is not the exact canonical encoding")
    return result


def _require_exact_json(value: object, name: str) -> None:
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise SWM0WS2SProtocolError(f"{name} keys must be exact strings")
            _require_exact_json(item, f"{name}.{key}")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _require_exact_json(item, f"{name}[{index}]")
        return
    if value is None or type(value) in {str, int, bool}:
        return
    raise SWM0WS2SProtocolError(
        f"{name} contains a non-JSON primitive or Python subclass alias"
    )


def _object(value: object, keys: Sequence[str], name: str) -> dict[str, Any]:
    _require_exact_json(value, name)
    if type(value) is not dict or set(value) != set(keys):
        raise SWM0WS2SProtocolError(f"{name} keys disagree with the exact schema")
    return value


def _list(value: object, name: str, *, length: int | None = None) -> list[Any]:
    if type(value) is not list or (length is not None and len(value) != length):
        expected = "an exact list" if length is None else f"an exact {length}-item list"
        raise SWM0WS2SProtocolError(f"{name} must be {expected}")
    return value


def _string(value: object, name: str) -> str:
    if type(value) is not str:
        raise SWM0WS2SProtocolError(f"{name} must be an exact string")
    return value


def _integer(
    value: object, name: str, *, minimum: int | None = None, maximum: int | None = None
) -> int:
    if type(value) is not int:
        raise SWM0WS2SProtocolError(f"{name} must be an exact integer")
    if minimum is not None and value < minimum:
        raise SWM0WS2SProtocolError(f"{name} is below its minimum")
    if maximum is not None and value > maximum:
        raise SWM0WS2SProtocolError(f"{name} exceeds its maximum")
    return value


def _boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise SWM0WS2SProtocolError(f"{name} must be an exact bool")
    return value


def _sha256(value: object, name: str) -> str:
    text = _string(value, name)
    if len(text) != 64 or any(character not in _SHA256_ALPHABET for character in text):
        raise SWM0WS2SProtocolError(f"{name} must be a lowercase SHA-256")
    return text


def _float_hex(
    value: object,
    name: str,
    *,
    nonnegative: bool = False,
    positive: bool = False,
    allow_negative_zero: bool = False,
) -> float:
    text = _string(value, name)
    try:
        result = float.fromhex(text)
    except ValueError as exc:
        raise SWM0WS2SProtocolError(f"{name} must be canonical float hex") from exc
    if not math.isfinite(result) or result.hex() != text:
        raise SWM0WS2SProtocolError(f"{name} must be canonical finite float hex")
    if (
        not allow_negative_zero
        and result == 0.0
        and math.copysign(1.0, result) < 0.0
    ):
        raise SWM0WS2SProtocolError(f"{name} may not encode negative zero")
    if nonnegative and result < 0.0:
        raise SWM0WS2SProtocolError(f"{name} must be non-negative")
    if positive and result <= 0.0:
        raise SWM0WS2SProtocolError(f"{name} must be positive")
    return result


def _finite(value: object, name: str, *, nonnegative: bool = False) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise SWM0WS2SProtocolError(f"{name} must be an exact finite float")
    if value == 0.0 and math.copysign(1.0, value) < 0.0:
        raise SWM0WS2SProtocolError(f"{name} may not be negative zero")
    if nonnegative and value < 0.0:
        raise SWM0WS2SProtocolError(f"{name} must be non-negative")
    return value


def _clean_float(value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise SWM0WS2SProtocolError("numeric reduction produced a non-finite value")
    return 0.0 if result == 0.0 else result


def _same_canonical(actual: Mapping[str, Any], expected: Mapping[str, Any], name: str) -> None:
    if canonical_json(actual) != canonical_json(expected):
        raise SWM0WS2SProtocolError(f"{name} is not its exact canonical representation")


def _enum(enum_type: type[Enum], value: object, name: str) -> Any:
    text = _string(value, name)
    try:
        result = enum_type(text)
    except ValueError as exc:
        raise SWM0WS2SProtocolError(f"{name} is unsupported") from exc
    if type(result) is not enum_type:
        raise SWM0WS2SProtocolError(f"{name} enum type drifted")
    return result


def parse_task_spec_v2(value: Mapping[str, Any]) -> TaskSpecV2:
    data = _object(
        value,
        (
            "draw_index",
            "family_certificate_sha256",
            "family_definition_sha256",
            "manifest_sha256",
            "rank_gains",
            "schema_version",
            "seed_commitment_sha256",
            "split",
            "structural_target_sha256",
            "structural_task_sha256",
        ),
        "TaskSpecV2",
    )
    if _string(data["schema_version"], "task schema") != "hswm-swm0w-s2s-task/v2":
        raise SWM0WS2SProtocolError("unsupported TaskSpecV2 schema")
    gain_rows = _list(data["rank_gains"], "rank gains", length=len(GAIN_ORDER))
    gains: list[int] = []
    for expected_index, row in zip(GAIN_ORDER, gain_rows, strict=True):
        entry = _object(row, ("channel", "gain", "rank", "role"), "rank gain")
        role, channel, rank = expected_index
        if (
            _string(entry["role"], "gain role") != ROLES[role]
            or _string(entry["channel"], "gain channel") != CHANNELS[channel]
            or _integer(entry["rank"], "gain rank") != rank
        ):
            raise SWM0WS2SProtocolError("rank gains are not in canonical typed order")
        gains.append(_integer(entry["gain"], "gain"))
    split = _object(data["split"], ("coefficients", "residues"), "task split")
    coefficients = tuple(
        _integer(item, "split coefficient")
        for item in _list(split["coefficients"], "split coefficients", length=3)
    )
    residue_map = _object(split["residues"], SPLITS, "split residues")
    residues = tuple(
        (
            name,
            tuple(
                _integer(item, f"{name} residue")
                for item in _list(residue_map[name], f"{name} residues")
            ),
        )
        for name in SPLITS
    )
    try:
        result = TaskSpecV2(
            seed_commitment_sha256=_sha256(
                data["seed_commitment_sha256"], "seed commitment"
            ),
            draw_index=_integer(data["draw_index"], "draw index", minimum=0),
            rank_gains=tuple(gains),
            split_coefficients=coefficients,
            split_residues=residues,
            family_definition_sha256=_sha256(
                data["family_definition_sha256"], "family definition SHA"
            ),
            family_certificate_sha256=_sha256(
                data["family_certificate_sha256"], "family certificate SHA"
            ),
            structural_target_sha256=_sha256(
                data["structural_target_sha256"], "structural target SHA"
            ),
            structural_task_sha256=_sha256(
                data["structural_task_sha256"], "structural task SHA"
            ),
            manifest_sha256=_sha256(data["manifest_sha256"], "task manifest SHA"),
        )
    except ValueError as exc:
        raise SWM0WS2SProtocolError("TaskSpecV2 validation failed") from exc
    _same_canonical(data, result.canonical(), "TaskSpecV2")
    return result


def serialize_task_batch(batch: TaskBatchV2) -> dict[str, Any]:
    if type(batch) is not TaskBatchV2:
        raise SWM0WS2SProtocolError("task-batch serialization requires exact TaskBatchV2")
    unsigned = {
        "batch": batch.canonical(),
        "schema_version": TASK_BATCH_ARCHIVE_VERSION,
        "tasks": [task.canonical() for task in batch.tasks],
    }
    return {**unsigned, "archive_sha256": canonical_sha256(unsigned)}


def parse_task_batch(value: Mapping[str, Any]) -> TaskBatchV2:
    data = _object(
        value,
        ("archive_sha256", "batch", "schema_version", "tasks"),
        "TaskBatchV2 archive",
    )
    if _string(data["schema_version"], "batch archive schema") != TASK_BATCH_ARCHIVE_VERSION:
        raise SWM0WS2SProtocolError("unsupported task-batch archive schema")
    tasks = tuple(
        parse_task_spec_v2(item)
        for item in _list(data["tasks"], "task-batch tasks")
    )
    raw = _object(
        data["batch"],
        (
            "batch_sha256",
            "duplicate_structural_target_draws",
            "duplicate_structural_task_draws",
            "requested_count",
            "schema_version",
            "seed_commitment_sha256",
            "task_manifest_sha256s",
        ),
        "TaskBatchV2",
    )
    if _string(raw["schema_version"], "batch schema") != "hswm-swm0w-s2s-task-batch/v2":
        raise SWM0WS2SProtocolError("unsupported TaskBatchV2 schema")

    def pairs(field: str) -> tuple[tuple[int, int], ...]:
        return tuple(
            tuple(_integer(item, field, minimum=0) for item in _list(row, field, length=2))
            for row in _list(raw[field], field)
        )

    manifests = tuple(
        _sha256(item, "task manifest SHA")
        for item in _list(raw["task_manifest_sha256s"], "task manifest SHAs")
    )
    if manifests != tuple(task.manifest_sha256 for task in tasks):
        raise SWM0WS2SProtocolError("task-batch manifest order drifted")
    try:
        result = TaskBatchV2(
            seed_commitment_sha256=_sha256(
                raw["seed_commitment_sha256"], "batch seed commitment"
            ),
            requested_count=_integer(raw["requested_count"], "requested count", minimum=1),
            tasks=tasks,
            duplicate_structural_target_draws=pairs(
                "duplicate_structural_target_draws"
            ),
            duplicate_structural_task_draws=pairs("duplicate_structural_task_draws"),
            batch_sha256=_sha256(raw["batch_sha256"], "batch SHA"),
        )
    except ValueError as exc:
        raise SWM0WS2SProtocolError("TaskBatchV2 validation failed") from exc
    unsigned = {key: data[key] for key in ("batch", "schema_version", "tasks")}
    if _sha256(data["archive_sha256"], "batch archive SHA") != canonical_sha256(unsigned):
        raise SWM0WS2SProtocolError("task-batch archive hash mismatch")
    _same_canonical(data, serialize_task_batch(result), "TaskBatchV2 archive")
    return result


def parse_training_config(value: Mapping[str, Any]) -> S2STrainingConfig:
    data = _object(
        value,
        (
            "beta1_hex",
            "beta2_hex",
            "epsilon_hex",
            "gradient_clip_hex",
            "learning_rate_hex",
            "max_updates",
            "min_delta_hex",
            "patience",
            "seed",
        ),
        "training config",
    )
    try:
        result = S2STrainingConfig(
            seed=_integer(data["seed"], "config seed", minimum=0),
            max_updates=_integer(data["max_updates"], "max updates", minimum=0),
            learning_rate=_float_hex(
                data["learning_rate_hex"], "learning rate", positive=True
            ),
            beta1=_float_hex(data["beta1_hex"], "beta1", positive=True),
            beta2=_float_hex(data["beta2_hex"], "beta2", positive=True),
            epsilon=_float_hex(data["epsilon_hex"], "epsilon", positive=True),
            gradient_clip=_float_hex(
                data["gradient_clip_hex"], "gradient clip", positive=True
            ),
            patience=_integer(data["patience"], "patience", minimum=1),
            min_delta=_float_hex(
                data["min_delta_hex"], "min delta", nonnegative=True
            ),
        )
    except ValueError as exc:
        raise SWM0WS2SProtocolError("training-config validation failed") from exc
    _same_canonical(data, result.canonical(), "training config")
    return result


def _parse_stratum_loss(value: Mapping[str, Any]) -> StratumLossReceipt:
    data = _object(
        value,
        (
            "centered_sum_squares_numerator",
            "channel",
            "inverse_variance_weight_hex",
            "receipt_sha256",
            "role",
            "sample_count",
            "schema_version",
            "target_numerator_sum",
            "target_numerator_sum_squares",
            "target_scale_exponent",
            "variance_definition",
        ),
        "stratum loss receipt",
    )
    if (
        _string(data["schema_version"], "stratum schema")
        != STRATUM_LOSS_RECEIPT_VERSION
        or _integer(data["target_scale_exponent"], "target scale")
        != TARGET_SCALE_EXPONENT
        or _string(data["variance_definition"], "variance definition")
        != "POPULATION_VARIANCE=(N*SUMSQ-SUM^2)/(N^2*2^(2*SCALE_EXPONENT))"
    ):
        raise SWM0WS2SProtocolError("stratum fixed contract drifted")
    try:
        result = StratumLossReceipt(
            role=_integer(data["role"], "stratum role"),
            channel=_integer(data["channel"], "stratum channel"),
            sample_count=_integer(data["sample_count"], "stratum sample count"),
            target_numerator_sum=_integer(
                data["target_numerator_sum"], "target numerator sum"
            ),
            target_numerator_sum_squares=_integer(
                data["target_numerator_sum_squares"], "target numerator sum squares"
            ),
            centered_sum_squares_numerator=_integer(
                data["centered_sum_squares_numerator"], "centered sum squares"
            ),
            inverse_variance_weight=_float_hex(
                data["inverse_variance_weight_hex"],
                "inverse variance weight",
                positive=True,
            ),
            receipt_sha256=_sha256(data["receipt_sha256"], "stratum receipt SHA"),
        )
    except ValueError as exc:
        raise SWM0WS2SProtocolError("stratum-loss validation failed") from exc
    _same_canonical(data, result.canonical(), "stratum loss receipt")
    return result


def _parse_history_entry(value: Mapping[str, Any]) -> OptimizationHistoryEntry:
    data = _object(
        value,
        (
            "clipped",
            "dev_loss_hex",
            "gradient_norm_hex",
            "improved",
            "parameters_sha256",
            "schema_version",
            "train_loss_hex",
            "update",
        ),
        "optimization history entry",
    )
    if _string(data["schema_version"], "history-entry schema") != HISTORY_ENTRY_VERSION:
        raise SWM0WS2SProtocolError("history-entry schema drifted")
    gradient = (
        None
        if data["gradient_norm_hex"] is None
        else _float_hex(
            data["gradient_norm_hex"], "gradient norm", nonnegative=True
        )
    )
    try:
        result = OptimizationHistoryEntry(
            update=_integer(data["update"], "history update", minimum=0),
            train_loss=_float_hex(data["train_loss_hex"], "train loss", nonnegative=True),
            dev_loss=_float_hex(data["dev_loss_hex"], "dev loss", nonnegative=True),
            gradient_norm=gradient,
            clipped=_boolean(data["clipped"], "history clipped"),
            improved=_boolean(data["improved"], "history improved"),
            parameters_sha256=_sha256(
                data["parameters_sha256"], "history parameters SHA"
            ),
        )
    except ValueError as exc:
        raise SWM0WS2SProtocolError("history-entry validation failed") from exc
    _same_canonical(data, result.canonical(), "optimization history entry")
    return result


def parse_optimization_receipt(value: Mapping[str, Any]) -> S2SOptimizationReceipt:
    keys = (
        "arm",
        "best_dev_loss_hex",
        "best_parameters_sha256",
        "best_train_loss_hex",
        "best_update",
        "clipped_update_count",
        "config",
        "dataset_bytes_version",
        "dataset_schema_sha256",
        "dev_case_count",
        "dev_dataset_sha256",
        "family_certificate_sha256",
        "family_definition_sha256",
        "history",
        "history_entry_count",
        "history_sha256",
        "history_version",
        "initial_parameters_sha256",
        "initialization_version",
        "loss_definition_sha256",
        "operator_architecture_receipt_sha256",
        "optimizer_version",
        "receipt_assurance",
        "receipt_sha256",
        "schema_version",
        "scientific_status",
        "stopped_update",
        "stratum_loss_receipts",
        "structural_target_sha256",
        "structural_task_sha256",
        "task_manifest_sha256",
        "task_spec",
        "termination_reason",
        "train_case_count",
        "train_dataset_sha256",
        "training_version",
        "update_count",
    )
    data = _object(value, keys, "optimization receipt")
    fixed = {
        "dataset_bytes_version": DATASET_BYTES_VERSION,
        "history_version": HISTORY_VERSION,
        "initialization_version": TRAINING_INITIALIZATION_VERSION,
        "optimizer_version": OPTIMIZER_VERSION,
        "receipt_assurance": RECEIPT_ASSURANCE,
        "schema_version": OPTIMIZATION_RECEIPT_VERSION,
        "scientific_status": TRAINING_SCIENTIFIC_STATUS,
        "training_version": TRAINING_VERSION,
    }
    if any(_string(data[name], name) != expected for name, expected in fixed.items()):
        raise SWM0WS2SProtocolError("optimization fixed contract drifted")
    task = parse_task_spec_v2(data["task_spec"])
    config = parse_training_config(data["config"])
    strata = tuple(
        _parse_stratum_loss(item)
        for item in _list(data["stratum_loss_receipts"], "stratum receipts", length=6)
    )
    history = tuple(
        _parse_history_entry(item)
        for item in _list(data["history"], "optimization history")
    )
    try:
        result = S2SOptimizationReceipt(
            arm=_enum(S2SArm, data["arm"], "optimization arm"),
            config=config,
            task=task,
            family_definition_sha256=_sha256(
                data["family_definition_sha256"], "family definition SHA"
            ),
            family_certificate_sha256=_sha256(
                data["family_certificate_sha256"], "family certificate SHA"
            ),
            structural_target_sha256=_sha256(
                data["structural_target_sha256"], "structural target SHA"
            ),
            structural_task_sha256=_sha256(
                data["structural_task_sha256"], "structural task SHA"
            ),
            task_manifest_sha256=_sha256(
                data["task_manifest_sha256"], "task manifest SHA"
            ),
            train_dataset_sha256=_sha256(
                data["train_dataset_sha256"], "train dataset SHA"
            ),
            dev_dataset_sha256=_sha256(
                data["dev_dataset_sha256"], "dev dataset SHA"
            ),
            dataset_schema_sha256=_sha256(
                data["dataset_schema_sha256"], "dataset schema SHA"
            ),
            train_case_count=_integer(data["train_case_count"], "train case count"),
            dev_case_count=_integer(data["dev_case_count"], "dev case count"),
            stratum_loss_receipts=strata,
            loss_definition_sha256=_sha256(
                data["loss_definition_sha256"], "loss definition SHA"
            ),
            operator_architecture_receipt_sha256=_sha256(
                data["operator_architecture_receipt_sha256"],
                "architecture receipt SHA",
            ),
            initial_parameters_sha256=_sha256(
                data["initial_parameters_sha256"], "initial parameters SHA"
            ),
            best_parameters_sha256=_sha256(
                data["best_parameters_sha256"], "best parameters SHA"
            ),
            best_update=_integer(data["best_update"], "best update", minimum=0),
            stopped_update=_integer(data["stopped_update"], "stopped update", minimum=0),
            best_train_loss=_float_hex(
                data["best_train_loss_hex"], "best train loss", nonnegative=True
            ),
            best_dev_loss=_float_hex(
                data["best_dev_loss_hex"], "best dev loss", nonnegative=True
            ),
            update_count=_integer(data["update_count"], "update count", minimum=0),
            clipped_update_count=_integer(
                data["clipped_update_count"], "clipped update count", minimum=0
            ),
            history=history,
            history_entry_count=_integer(
                data["history_entry_count"], "history entry count", minimum=1
            ),
            history_sha256=_sha256(data["history_sha256"], "history SHA"),
            termination_reason=_enum(
                TerminationReason, data["termination_reason"], "termination reason"
            ),
            receipt_sha256=_sha256(data["receipt_sha256"], "optimization receipt SHA"),
        )
    except ValueError as exc:
        raise SWM0WS2SProtocolError("optimization-receipt validation failed") from exc
    _same_canonical(data, result.canonical(), "optimization receipt")
    return result


@dataclass(frozen=True, slots=True)
class Thresholds:
    q: float = 0.80
    b: float = 0.10
    r: float = 0.10
    c_phrase: float = -0.02

    def __post_init__(self) -> None:
        for name in ("q", "b", "r", "c_phrase"):
            _finite(getattr(self, name), f"threshold {name}")

    def canonical(self) -> dict[str, str]:
        return {
            "b_hex": self.b.hex(),
            "c_phrase_hex": self.c_phrase.hex(),
            "q_hex": self.q.hex(),
            "r_hex": self.r.hex(),
        }


@dataclass(frozen=True, slots=True)
class S2SProtocolConfig:
    """Pilot-independent contract; every per-arm config is caller supplied."""

    arm_configs: tuple[tuple[S2SArm, S2STrainingConfig], ...]
    excluded_task_provenance: tuple[tuple[str, tuple[int, ...]], ...]
    thresholds: Thresholds
    pair_null_epsilon: float
    symmetry_atol: float
    symmetry_rtol: float
    receipt_sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.arm_configs) is not tuple
            or len(self.arm_configs) != len(ALL_ARMS)
            or any(
                type(row) is not tuple
                or len(row) != 2
                or type(row[0]) is not S2SArm
                or type(row[1]) is not S2STrainingConfig
                for row in self.arm_configs
            )
            or tuple(arm for arm, _ in self.arm_configs) != ALL_ARMS
        ):
            raise SWM0WS2SProtocolError(
                "protocol config requires all three exact arms in canonical order"
            )
        if type(self.thresholds) is not Thresholds:
            raise SWM0WS2SProtocolError("protocol thresholds require exact Thresholds")
        if (
            type(self.excluded_task_provenance) is not tuple
            or any(
                type(row) is not tuple
                or len(row) != 2
                or type(row[0]) is not str
                or type(row[1]) is not tuple
                or not row[1]
                or any(type(index) is not int or index < 0 for index in row[1])
                or row[1] != tuple(sorted(set(row[1])))
                for row in self.excluded_task_provenance
            )
            or tuple(row[0] for row in self.excluded_task_provenance)
            != tuple(sorted({row[0] for row in self.excluded_task_provenance}))
        ):
            raise SWM0WS2SProtocolError("excluded task provenance is not canonical")
        for seed_sha, _ in self.excluded_task_provenance:
            _sha256(seed_sha, "excluded seed commitment SHA")
        _finite(self.pair_null_epsilon, "pair-null epsilon", nonnegative=True)
        _finite(self.symmetry_atol, "symmetry atol", nonnegative=True)
        _finite(self.symmetry_rtol, "symmetry rtol", nonnegative=True)
        _sha256(self.receipt_sha256, "protocol-config receipt SHA")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SProtocolError("protocol-config receipt hash mismatch")

    def config_for(self, arm: S2SArm) -> S2STrainingConfig:
        if type(arm) is not S2SArm:
            raise SWM0WS2SProtocolError("config lookup requires exact S2SArm")
        return dict(self.arm_configs)[arm]

    def unsigned(self) -> dict[str, Any]:
        return {
            "arm_configs": [
                {"arm": arm.value, "config": config.canonical()}
                for arm, config in self.arm_configs
            ],
            "excluded_task_provenance": [
                {
                    "draw_indices": list(draw_indices),
                    "seed_commitment_sha256": seed_sha,
                }
                for seed_sha, draw_indices in self.excluded_task_provenance
            ],
            "bootstrap": {
                "generator": "numpy.random.PCG64",
                "quantile_method": "linear",
                "quantiles": [value.hex() for value in BOOTSTRAP_QUANTILES],
                "resamples": BOOTSTRAP_RESAMPLES,
                "seed": BOOTSTRAP_SEED,
                "shared_across_metrics": True,
                "unit": "INDEXED_TASK_DRAW_CONDITIONAL_ON_FIXED_FRAME_GENERATOR",
            },
            "pair_null_epsilon_hex": self.pair_null_epsilon.hex(),
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": PROTOCOL_CONFIG_VERSION,
            "scientific_status": SCIENTIFIC_STATUS,
            "structural_collision_policy": (
                "RETAIN_AND_DISCLOSE_WITH_OBSERVED_MULTIPLICITY"
            ),
            "symmetry_atol_hex": self.symmetry_atol.hex(),
            "symmetry_rtol_hex": self.symmetry_rtol.hex(),
            "task_count": TASK_COUNT,
            "thresholds": self.thresholds.canonical(),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def _protocol_config_unsigned(
    arm_configs: tuple[tuple[S2SArm, S2STrainingConfig], ...],
    excluded_task_provenance: tuple[tuple[str, tuple[int, ...]], ...],
    thresholds: Thresholds,
    pair_null_epsilon: float,
    symmetry_atol: float,
    symmetry_rtol: float,
) -> dict[str, Any]:
    """Build through a temporary non-validating view to avoid mutable defaults."""

    return {
        "arm_configs": [
            {"arm": arm.value, "config": config.canonical()}
            for arm, config in arm_configs
        ],
        "excluded_task_provenance": [
            {
                "draw_indices": list(draw_indices),
                "seed_commitment_sha256": seed_sha,
            }
            for seed_sha, draw_indices in excluded_task_provenance
        ],
        "bootstrap": {
            "generator": "numpy.random.PCG64",
            "quantile_method": "linear",
            "quantiles": [value.hex() for value in BOOTSTRAP_QUANTILES],
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "shared_across_metrics": True,
            "unit": "INDEXED_TASK_DRAW_CONDITIONAL_ON_FIXED_FRAME_GENERATOR",
        },
        "pair_null_epsilon_hex": pair_null_epsilon.hex(),
        "protocol_version": PROTOCOL_VERSION,
        "schema_version": PROTOCOL_CONFIG_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "structural_collision_policy": (
            "RETAIN_AND_DISCLOSE_WITH_OBSERVED_MULTIPLICITY"
        ),
        "symmetry_atol_hex": symmetry_atol.hex(),
        "symmetry_rtol_hex": symmetry_rtol.hex(),
        "task_count": TASK_COUNT,
        "thresholds": thresholds.canonical(),
    }


def build_protocol_config(
    arm_configs: tuple[tuple[S2SArm, S2STrainingConfig], ...],
    *,
    excluded_task_provenance: tuple[tuple[str, tuple[int, ...]], ...],
    thresholds: Thresholds = Thresholds(),
    pair_null_epsilon: float = PAIR_NULL_EPSILON,
    symmetry_atol: float = DEFAULT_SYMMETRY_ATOL,
    symmetry_rtol: float = DEFAULT_SYMMETRY_RTOL,
) -> S2SProtocolConfig:
    if (
        type(arm_configs) is not tuple
        or type(excluded_task_provenance) is not tuple
        or type(thresholds) is not Thresholds
        or type(pair_null_epsilon) is not float
        or type(symmetry_atol) is not float
        or type(symmetry_rtol) is not float
    ):
        raise SWM0WS2SProtocolError("protocol config inputs require exact types")
    unsigned = _protocol_config_unsigned(
        arm_configs,
        excluded_task_provenance,
        thresholds,
        pair_null_epsilon,
        symmetry_atol,
        symmetry_rtol,
    )
    return S2SProtocolConfig(
        arm_configs=arm_configs,
        excluded_task_provenance=excluded_task_provenance,
        thresholds=thresholds,
        pair_null_epsilon=pair_null_epsilon,
        symmetry_atol=symmetry_atol,
        symmetry_rtol=symmetry_rtol,
        receipt_sha256=canonical_sha256(unsigned),
    )


def parse_protocol_config(value: Mapping[str, Any]) -> S2SProtocolConfig:
    data = _object(
        value,
        (
            "arm_configs",
            "bootstrap",
            "excluded_task_provenance",
            "pair_null_epsilon_hex",
            "protocol_version",
            "receipt_sha256",
            "schema_version",
            "scientific_status",
            "structural_collision_policy",
            "symmetry_atol_hex",
            "symmetry_rtol_hex",
            "task_count",
            "thresholds",
        ),
        "protocol config",
    )
    if (
        _string(data["schema_version"], "config schema") != PROTOCOL_CONFIG_VERSION
        or _string(data["protocol_version"], "protocol version") != PROTOCOL_VERSION
        or _string(data["scientific_status"], "scientific status") != SCIENTIFIC_STATUS
        or _integer(data["task_count"], "task count") != TASK_COUNT
        or _string(data["structural_collision_policy"], "collision policy")
        != "RETAIN_AND_DISCLOSE_WITH_OBSERVED_MULTIPLICITY"
    ):
        raise SWM0WS2SProtocolError("protocol-config fixed fields drifted")
    bootstrap = _object(
        data["bootstrap"],
        (
            "generator",
            "quantile_method",
            "quantiles",
            "resamples",
            "seed",
            "shared_across_metrics",
            "unit",
        ),
        "bootstrap contract",
    )
    expected_bootstrap = _protocol_config_unsigned(
        tuple(), tuple(), Thresholds(), 0.0, 0.0, 0.0
    )["bootstrap"]
    if bootstrap != expected_bootstrap:
        raise SWM0WS2SProtocolError("bootstrap contract drifted")
    threshold_data = _object(
        data["thresholds"],
        ("b_hex", "c_phrase_hex", "q_hex", "r_hex"),
        "thresholds",
    )
    thresholds = Thresholds(
        q=_float_hex(threshold_data["q_hex"], "Q threshold"),
        b=_float_hex(threshold_data["b_hex"], "B threshold"),
        r=_float_hex(threshold_data["r_hex"], "R threshold"),
        c_phrase=_float_hex(threshold_data["c_phrase_hex"], "C phrase threshold"),
    )
    rows = _list(data["arm_configs"], "arm configs", length=len(ALL_ARMS))
    arm_configs = tuple(
        (
            _enum(
                S2SArm,
                _object(row, ("arm", "config"), "arm config")["arm"],
                "config arm",
            ),
            parse_training_config(row["config"]),
        )
        for row in rows
    )
    excluded_provenance = tuple(
        (
            _sha256(
                _object(
                    row,
                    ("draw_indices", "seed_commitment_sha256"),
                    "excluded provenance",
                )["seed_commitment_sha256"],
                "excluded seed commitment SHA",
            ),
            tuple(
                _integer(index, "excluded draw index", minimum=0)
                for index in _list(row["draw_indices"], "excluded draw indices")
            ),
        )
        for row in _list(
            data["excluded_task_provenance"], "excluded task provenance"
        )
    )
    result = build_protocol_config(
        arm_configs,
        excluded_task_provenance=excluded_provenance,
        thresholds=thresholds,
        pair_null_epsilon=_float_hex(
            data["pair_null_epsilon_hex"], "pair-null epsilon", nonnegative=True
        ),
        symmetry_atol=_float_hex(
            data["symmetry_atol_hex"], "symmetry atol", nonnegative=True
        ),
        symmetry_rtol=_float_hex(
            data["symmetry_rtol_hex"], "symmetry rtol", nonnegative=True
        ),
    )
    if result.receipt_sha256 != _sha256(data["receipt_sha256"], "config receipt SHA"):
        raise SWM0WS2SProtocolError("protocol-config receipt hash mismatch")
    _same_canonical(data, result.canonical(), "protocol config")
    return result


@dataclass(frozen=True, slots=True)
class ParameterTensor:
    name: str
    shape: tuple[int, ...]
    values_hex: tuple[str, ...]
    bytes_sha256: str

    def __post_init__(self) -> None:
        if type(self.name) is not str or not self.name:
            raise SWM0WS2SProtocolError("parameter tensor name must be exact nonempty string")
        if (
            type(self.shape) is not tuple
            or not self.shape
            or any(type(value) is not int or value <= 0 for value in self.shape)
        ):
            raise SWM0WS2SProtocolError("parameter tensor shape is invalid")
        if type(self.values_hex) is not tuple or len(self.values_hex) != math.prod(self.shape):
            raise SWM0WS2SProtocolError("parameter tensor value count disagrees with shape")
        values = np.asarray(
            [
                _float_hex(
                    value,
                    f"parameter {self.name}",
                    allow_negative_zero=True,
                )
                for value in self.values_hex
            ],
            dtype="<f8",
        ).reshape(self.shape)
        _sha256(self.bytes_sha256, "parameter tensor bytes SHA")
        if hashlib.sha256(values.tobytes(order="C")).hexdigest() != self.bytes_sha256:
            raise SWM0WS2SProtocolError("parameter tensor bytes hash mismatch")

    def array(self) -> np.ndarray:
        return np.asarray(
            [float.fromhex(value) for value in self.values_hex], dtype=np.float64
        ).reshape(self.shape)

    def canonical(self) -> dict[str, Any]:
        return {
            "bytes_sha256": self.bytes_sha256,
            "dtype": "float64-little-endian",
            "name": self.name,
            "schema_version": PARAMETER_TENSOR_VERSION,
            "shape": list(self.shape),
            "values_hex": list(self.values_hex),
        }


@dataclass(frozen=True, slots=True)
class LearnedModelArchive:
    arm: S2SArm
    optimization: S2SOptimizationReceipt
    tensors: tuple[ParameterTensor, ...]
    fitted: bool
    learned: bool
    parameter_count: int
    parameters_sha256: str
    learned_state_sha256: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.arm) is not S2SArm or type(self.optimization) is not S2SOptimizationReceipt:
            raise SWM0WS2SProtocolError("learned archive requires exact arm/optimization")
        if self.optimization.arm is not self.arm:
            raise SWM0WS2SProtocolError("learned archive arm crosses its optimization")
        schema = tuple(parameter_shapes(self.arm).items())
        if (
            type(self.tensors) is not tuple
            or any(type(tensor) is not ParameterTensor for tensor in self.tensors)
            or tuple((tensor.name, tensor.shape) for tensor in self.tensors) != schema
        ):
            raise SWM0WS2SProtocolError("learned archive tensor schema drifted")
        if (
            type(self.fitted) is not bool
            or self.fitted is not True
            or type(self.learned) is not bool
        ):
            raise SWM0WS2SProtocolError("learned archive status flags must be exact")
        if type(self.parameter_count) is not int or self.parameter_count != 870:
            raise SWM0WS2SProtocolError("learned archive parameter count must be 870")
        for name in ("parameters_sha256", "learned_state_sha256", "receipt_sha256"):
            _sha256(getattr(self, name), name)
        model = self.model()
        if (
            model.fitted is not self.fitted
            or model.learned is not self.learned
            or model.parameter_count != self.parameter_count
            or model.parameters_sha256 != self.parameters_sha256
            or model.state_sha256 != self.learned_state_sha256
        ):
            raise SWM0WS2SProtocolError("learned archive model bindings disagree")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SProtocolError("learned archive receipt hash mismatch")

    def parameters(self) -> dict[str, np.ndarray]:
        return {tensor.name: tensor.array() for tensor in self.tensors}

    def model(self) -> LearnedS2SOperator:
        try:
            return LearnedS2SOperator(
                arm=self.arm,
                config=self.optimization.config,
                parameters=self.parameters(),
                optimization=self.optimization,
            )
        except ValueError as exc:
            raise SWM0WS2SProtocolError("learned archive reconstruction failed") from exc

    def unsigned(self) -> dict[str, Any]:
        return {
            "arm": self.arm.value,
            "fitted": self.fitted,
            "learned": self.learned,
            "learned_state_sha256": self.learned_state_sha256,
            "optimization_receipt": self.optimization.canonical(),
            "parameter_count": self.parameter_count,
            "parameters_sha256": self.parameters_sha256,
            "schema_version": LEARNED_ARCHIVE_VERSION,
            "scientific_status": SCIENTIFIC_STATUS,
            "tensors": [tensor.canonical() for tensor in self.tensors],
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def archive_learned_model(model: LearnedS2SOperator) -> LearnedModelArchive:
    if type(model) is not LearnedS2SOperator:
        raise SWM0WS2SProtocolError("archive requires exact LearnedS2SOperator")
    tensors = tuple(
        ParameterTensor(
            name=name,
            shape=shape,
            values_hex=tuple(float(value).hex() for value in model.parameters[name].reshape(-1)),
            bytes_sha256=hashlib.sha256(
                np.asarray(model.parameters[name], dtype="<f8", order="C").tobytes(order="C")
            ).hexdigest(),
        )
        for name, shape in parameter_shapes(model.arm).items()
    )
    unsigned = {
        "arm": model.arm.value,
        "fitted": True,
        "learned": model.learned,
        "learned_state_sha256": model.state_sha256,
        "optimization_receipt": model.optimization.canonical(),
        "parameter_count": model.parameter_count,
        "parameters_sha256": model.parameters_sha256,
        "schema_version": LEARNED_ARCHIVE_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "tensors": [tensor.canonical() for tensor in tensors],
    }
    return LearnedModelArchive(
        arm=model.arm,
        optimization=model.optimization,
        tensors=tensors,
        fitted=True,
        learned=model.learned,
        parameter_count=model.parameter_count,
        parameters_sha256=model.parameters_sha256,
        learned_state_sha256=model.state_sha256,
        receipt_sha256=canonical_sha256(unsigned),
    )


def _parse_parameter_tensor(value: Mapping[str, Any]) -> ParameterTensor:
    data = _object(
        value,
        ("bytes_sha256", "dtype", "name", "schema_version", "shape", "values_hex"),
        "parameter tensor",
    )
    if (
        _string(data["schema_version"], "parameter tensor schema")
        != PARAMETER_TENSOR_VERSION
        or _string(data["dtype"], "parameter dtype") != "float64-little-endian"
    ):
        raise SWM0WS2SProtocolError("parameter tensor fixed contract drifted")
    result = ParameterTensor(
        name=_string(data["name"], "parameter name"),
        shape=tuple(
            _integer(item, "parameter dimension", minimum=1)
            for item in _list(data["shape"], "parameter shape")
        ),
        values_hex=tuple(
            _string(item, "parameter value hex")
            for item in _list(data["values_hex"], "parameter values")
        ),
        bytes_sha256=_sha256(data["bytes_sha256"], "parameter bytes SHA"),
    )
    _same_canonical(data, result.canonical(), "parameter tensor")
    return result


def parse_learned_model_archive(value: Mapping[str, Any]) -> LearnedModelArchive:
    data = _object(
        value,
        (
            "arm",
            "fitted",
            "learned",
            "learned_state_sha256",
            "optimization_receipt",
            "parameter_count",
            "parameters_sha256",
            "receipt_sha256",
            "schema_version",
            "scientific_status",
            "tensors",
        ),
        "learned model archive",
    )
    if (
        _string(data["schema_version"], "learned archive schema") != LEARNED_ARCHIVE_VERSION
        or _string(data["scientific_status"], "learned archive status")
        != SCIENTIFIC_STATUS
    ):
        raise SWM0WS2SProtocolError("learned archive fixed contract drifted")
    result = LearnedModelArchive(
        arm=_enum(S2SArm, data["arm"], "learned archive arm"),
        optimization=parse_optimization_receipt(data["optimization_receipt"]),
        tensors=tuple(
            _parse_parameter_tensor(item)
            for item in _list(data["tensors"], "learned archive tensors")
        ),
        fitted=_boolean(data["fitted"], "fitted flag"),
        learned=_boolean(data["learned"], "learned flag"),
        parameter_count=_integer(data["parameter_count"], "parameter count"),
        parameters_sha256=_sha256(data["parameters_sha256"], "parameters SHA"),
        learned_state_sha256=_sha256(
            data["learned_state_sha256"], "learned state SHA"
        ),
        receipt_sha256=_sha256(data["receipt_sha256"], "learned archive receipt SHA"),
    )
    _same_canonical(data, result.canonical(), "learned model archive")
    return result


@dataclass(frozen=True, slots=True)
class FitReplayReceipt:
    arm: S2SArm
    task_manifest_sha256: str
    original_learned_state_sha256: str
    replay_learned_state_sha256: str
    original_optimization_receipt_sha256: str
    replay_optimization_receipt_sha256: str
    original_history_sha256: str
    replay_history_sha256: str
    original_parameters_sha256: str
    replay_parameters_sha256: str
    parameter_bytes_equal: bool
    optimization_canonical_equal: bool
    state_equal: bool
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.arm) is not S2SArm or any(
            type(value) is not bool
            for value in (
                self.parameter_bytes_equal,
                self.optimization_canonical_equal,
                self.state_equal,
            )
        ):
            raise SWM0WS2SProtocolError("fit replay requires exact arm/bools")
        for name in (
            "task_manifest_sha256",
            "original_learned_state_sha256",
            "replay_learned_state_sha256",
            "original_optimization_receipt_sha256",
            "replay_optimization_receipt_sha256",
            "original_history_sha256",
            "replay_history_sha256",
            "original_parameters_sha256",
            "replay_parameters_sha256",
            "receipt_sha256",
        ):
            _sha256(getattr(self, name), name)
        if (
            not self.parameter_bytes_equal
            or not self.optimization_canonical_equal
            or not self.state_equal
            or self.original_learned_state_sha256 != self.replay_learned_state_sha256
            or self.original_optimization_receipt_sha256
            != self.replay_optimization_receipt_sha256
            or self.original_history_sha256 != self.replay_history_sha256
            or self.original_parameters_sha256 != self.replay_parameters_sha256
        ):
            raise SWM0WS2SProtocolError("fit replay is not exact")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SProtocolError("fit-replay receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "arm": self.arm.value,
            "optimization_canonical_equal": self.optimization_canonical_equal,
            "original_history_sha256": self.original_history_sha256,
            "original_learned_state_sha256": self.original_learned_state_sha256,
            "original_optimization_receipt_sha256": (
                self.original_optimization_receipt_sha256
            ),
            "original_parameters_sha256": self.original_parameters_sha256,
            "parameter_bytes_equal": self.parameter_bytes_equal,
            "replay_history_sha256": self.replay_history_sha256,
            "replay_learned_state_sha256": self.replay_learned_state_sha256,
            "replay_optimization_receipt_sha256": (
                self.replay_optimization_receipt_sha256
            ),
            "replay_parameters_sha256": self.replay_parameters_sha256,
            "schema_version": FIT_REPLAY_VERSION,
            "state_equal": self.state_equal,
            "task_manifest_sha256": self.task_manifest_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def build_fit_replay_receipt(
    original: LearnedS2SOperator, replay: LearnedS2SOperator
) -> FitReplayReceipt:
    if type(original) is not LearnedS2SOperator or type(replay) is not LearnedS2SOperator:
        raise SWM0WS2SProtocolError("fit replay requires exact learned models")
    exact_bytes = (
        original.arm is replay.arm
        and tuple(original.parameters) == tuple(replay.parameters)
        and all(
            original.parameters[name].tobytes(order="C")
            == replay.parameters[name].tobytes(order="C")
            for name in original.parameters
        )
    )
    optimization_equal = original.optimization.canonical() == replay.optimization.canonical()
    state_equal = original.state_sha256 == replay.state_sha256
    values = {
        "arm": original.arm,
        "task_manifest_sha256": original.optimization.task_manifest_sha256,
        "original_learned_state_sha256": original.state_sha256,
        "replay_learned_state_sha256": replay.state_sha256,
        "original_optimization_receipt_sha256": original.optimization.receipt_sha256,
        "replay_optimization_receipt_sha256": replay.optimization.receipt_sha256,
        "original_history_sha256": original.optimization.history_sha256,
        "replay_history_sha256": replay.optimization.history_sha256,
        "original_parameters_sha256": original.parameters_sha256,
        "replay_parameters_sha256": replay.parameters_sha256,
        "parameter_bytes_equal": exact_bytes,
        "optimization_canonical_equal": optimization_equal,
        "state_equal": state_equal,
    }
    unsigned = {
        "arm": original.arm.value,
        "optimization_canonical_equal": optimization_equal,
        "original_history_sha256": original.optimization.history_sha256,
        "original_learned_state_sha256": original.state_sha256,
        "original_optimization_receipt_sha256": original.optimization.receipt_sha256,
        "original_parameters_sha256": original.parameters_sha256,
        "parameter_bytes_equal": exact_bytes,
        "replay_history_sha256": replay.optimization.history_sha256,
        "replay_learned_state_sha256": replay.state_sha256,
        "replay_optimization_receipt_sha256": replay.optimization.receipt_sha256,
        "replay_parameters_sha256": replay.parameters_sha256,
        "schema_version": FIT_REPLAY_VERSION,
        "state_equal": state_equal,
        "task_manifest_sha256": original.optimization.task_manifest_sha256,
    }
    return FitReplayReceipt(**values, receipt_sha256=canonical_sha256(unsigned))


def parse_fit_replay_receipt(value: Mapping[str, Any]) -> FitReplayReceipt:
    data = _object(
        value,
        (
            "arm",
            "optimization_canonical_equal",
            "original_history_sha256",
            "original_learned_state_sha256",
            "original_optimization_receipt_sha256",
            "original_parameters_sha256",
            "parameter_bytes_equal",
            "receipt_sha256",
            "replay_history_sha256",
            "replay_learned_state_sha256",
            "replay_optimization_receipt_sha256",
            "replay_parameters_sha256",
            "schema_version",
            "state_equal",
            "task_manifest_sha256",
        ),
        "fit-replay receipt",
    )
    if _string(data["schema_version"], "fit-replay schema") != FIT_REPLAY_VERSION:
        raise SWM0WS2SProtocolError("fit-replay schema drifted")
    result = FitReplayReceipt(
        arm=_enum(S2SArm, data["arm"], "fit-replay arm"),
        task_manifest_sha256=_sha256(data["task_manifest_sha256"], "task manifest SHA"),
        original_learned_state_sha256=_sha256(
            data["original_learned_state_sha256"], "original learned state SHA"
        ),
        replay_learned_state_sha256=_sha256(
            data["replay_learned_state_sha256"], "replay learned state SHA"
        ),
        original_optimization_receipt_sha256=_sha256(
            data["original_optimization_receipt_sha256"],
            "original optimization receipt SHA",
        ),
        replay_optimization_receipt_sha256=_sha256(
            data["replay_optimization_receipt_sha256"],
            "replay optimization receipt SHA",
        ),
        original_history_sha256=_sha256(
            data["original_history_sha256"], "original history SHA"
        ),
        replay_history_sha256=_sha256(
            data["replay_history_sha256"], "replay history SHA"
        ),
        original_parameters_sha256=_sha256(
            data["original_parameters_sha256"], "original parameters SHA"
        ),
        replay_parameters_sha256=_sha256(
            data["replay_parameters_sha256"], "replay parameters SHA"
        ),
        parameter_bytes_equal=_boolean(
            data["parameter_bytes_equal"], "parameter bytes equal"
        ),
        optimization_canonical_equal=_boolean(
            data["optimization_canonical_equal"], "optimization canonical equal"
        ),
        state_equal=_boolean(
            data["state_equal"], "state equal"
        ),
        receipt_sha256=_sha256(data["receipt_sha256"], "fit-replay receipt SHA"),
    )
    _same_canonical(data, result.canonical(), "fit-replay receipt")
    return result


def _parse_q_removal(value: Mapping[str, Any]) -> QRemovalReceipt:
    data = _object(
        value,
        (
            "ablated_state_sha256",
            "base_state_sha256",
            "intervention",
            "receipt_sha256",
            "removed_bytes_sha256",
            "removed_values_hex",
            "schema_version",
            "value_count",
        ),
        "Q removal receipt",
    )
    if (
        _string(data["schema_version"], "Q-removal schema") != Q_REMOVAL_RECEIPT_VERSION
        or _string(data["intervention"], "Q intervention")
        != "FROZEN_Q_REMOVE_EXACT_RESTORE"
        or _integer(data["value_count"], "Q value count") != 96
    ):
        raise SWM0WS2SProtocolError("Q-removal fixed contract drifted")
    result = QRemovalReceipt(
        base_state_sha256=_sha256(data["base_state_sha256"], "base core state SHA"),
        ablated_state_sha256=_sha256(
            data["ablated_state_sha256"], "ablated core state SHA"
        ),
        removed_values_hex=tuple(
            _string(item, "removed Q value")
            for item in _list(data["removed_values_hex"], "removed Q values", length=96)
        ),
        removed_bytes_sha256=_sha256(
            data["removed_bytes_sha256"], "removed Q bytes SHA"
        ),
        receipt_sha256=_sha256(data["receipt_sha256"], "Q-removal receipt SHA"),
    )
    # Signed zero is not an alias in a byte-exact restoration receipt.
    for index, encoded in enumerate(result.removed_values_hex):
        _float_hex(
            encoded,
            f"removed Q value {index}",
            allow_negative_zero=True,
        )
    _same_canonical(data, result.canonical(), "Q removal receipt")
    return result


@dataclass(frozen=True, slots=True)
class LearnedQInterventionReceipt:
    task_manifest_sha256: str
    learned_state_sha256: str
    optimization_receipt_sha256: str
    learned_parameters_sha256: str
    base_core_state_sha256: str
    removal: QRemovalReceipt
    restored_core_state_sha256: str
    restored_learned_state_sha256: str
    restored_parameters_sha256: str
    exact_restored_parameter_bytes: bool
    exact_restored_learned_state: bool
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.removal) is not QRemovalReceipt or type(
            self.exact_restored_parameter_bytes
        ) is not bool or type(self.exact_restored_learned_state) is not bool:
            raise SWM0WS2SProtocolError("learned Q receipt requires exact receipt/bool")
        for name in (
            "task_manifest_sha256",
            "learned_state_sha256",
            "optimization_receipt_sha256",
            "learned_parameters_sha256",
            "base_core_state_sha256",
            "restored_core_state_sha256",
            "restored_learned_state_sha256",
            "restored_parameters_sha256",
            "receipt_sha256",
        ):
            _sha256(getattr(self, name), name)
        if (
            not self.exact_restored_parameter_bytes
            or not self.exact_restored_learned_state
            or self.base_core_state_sha256 != self.removal.base_state_sha256
            or self.restored_core_state_sha256 != self.base_core_state_sha256
            or self.restored_parameters_sha256 != self.learned_parameters_sha256
            or self.restored_learned_state_sha256 != self.learned_state_sha256
        ):
            raise SWM0WS2SProtocolError("learned Q restoration is not exact")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SProtocolError("learned Q intervention hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "base_core_state_sha256": self.base_core_state_sha256,
            "exact_restored_parameter_bytes": self.exact_restored_parameter_bytes,
            "exact_restored_learned_state": self.exact_restored_learned_state,
            "learned_parameters_sha256": self.learned_parameters_sha256,
            "learned_state_sha256": self.learned_state_sha256,
            "optimization_receipt_sha256": self.optimization_receipt_sha256,
            "removal": self.removal.canonical(),
            "restored_core_state_sha256": self.restored_core_state_sha256,
            "restored_learned_state_sha256": self.restored_learned_state_sha256,
            "restored_parameters_sha256": self.restored_parameters_sha256,
            "schema_version": LEARNED_Q_INTERVENTION_VERSION,
            "task_manifest_sha256": self.task_manifest_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def remove_learned_q(
    model: LearnedS2SOperator,
) -> tuple[S2SOperator, LearnedQInterventionReceipt]:
    if type(model) is not LearnedS2SOperator or model.arm is not S2SArm.T16:
        raise SWM0WS2SProtocolError("learned Q removal requires exact learned T16")
    core = model.as_unlabeled_operator()
    ablated, removal = remove_q(core)
    restored = restore_q(ablated, removal)
    restored_learned = LearnedS2SOperator(
        arm=model.arm,
        config=model.config,
        parameters=restored.parameters,
        optimization=model.optimization,
    )
    exact = tuple(core.parameters) == tuple(restored.parameters) and all(
        core.parameters[name].tobytes(order="C")
        == restored.parameters[name].tobytes(order="C")
        for name in core.parameters
    )
    unsigned = {
        "base_core_state_sha256": core.state_sha256,
        "exact_restored_parameter_bytes": exact,
        "exact_restored_learned_state": restored_learned.state_sha256 == model.state_sha256,
        "learned_parameters_sha256": model.parameters_sha256,
        "learned_state_sha256": model.state_sha256,
        "optimization_receipt_sha256": model.optimization.receipt_sha256,
        "removal": removal.canonical(),
        "restored_core_state_sha256": restored.state_sha256,
        "restored_learned_state_sha256": restored_learned.state_sha256,
        "restored_parameters_sha256": restored.parameters_sha256,
        "schema_version": LEARNED_Q_INTERVENTION_VERSION,
        "task_manifest_sha256": model.optimization.task_manifest_sha256,
    }
    receipt = LearnedQInterventionReceipt(
        task_manifest_sha256=model.optimization.task_manifest_sha256,
        learned_state_sha256=model.state_sha256,
        optimization_receipt_sha256=model.optimization.receipt_sha256,
        learned_parameters_sha256=model.parameters_sha256,
        base_core_state_sha256=core.state_sha256,
        removal=removal,
        restored_core_state_sha256=restored.state_sha256,
        restored_learned_state_sha256=restored_learned.state_sha256,
        restored_parameters_sha256=restored.parameters_sha256,
        exact_restored_parameter_bytes=exact,
        exact_restored_learned_state=restored_learned.state_sha256 == model.state_sha256,
        receipt_sha256=canonical_sha256(unsigned),
    )
    return ablated, receipt


def restore_learned_q(
    model: LearnedS2SOperator,
    ablated: S2SOperator,
    receipt: LearnedQInterventionReceipt,
) -> LearnedS2SOperator:
    if (
        type(model) is not LearnedS2SOperator
        or type(ablated) is not S2SOperator
        or type(receipt) is not LearnedQInterventionReceipt
        or model.arm is not S2SArm.T16
        or model.state_sha256 != receipt.learned_state_sha256
        or model.optimization.receipt_sha256 != receipt.optimization_receipt_sha256
        or model.optimization.task_manifest_sha256 != receipt.task_manifest_sha256
        or ablated.state_sha256 != receipt.removal.ablated_state_sha256
    ):
        raise SWM0WS2SProtocolError("learned Q receipt crosses model/task/intervention")
    restored = restore_q(ablated, receipt.removal)
    if (
        restored.state_sha256 != receipt.restored_core_state_sha256
        or restored.parameters_sha256 != receipt.restored_parameters_sha256
        or any(
            restored.parameters[name].tobytes(order="C")
            != model.parameters[name].tobytes(order="C")
            for name in restored.parameters
        )
    ):
        raise SWM0WS2SProtocolError("learned Q restoration replay mismatch")
    try:
        restored_learned = LearnedS2SOperator(
            arm=model.arm,
            config=model.config,
            parameters=restored.parameters,
            optimization=model.optimization,
        )
    except ValueError as exc:
        raise SWM0WS2SProtocolError("restored learned wrapper reconstruction failed") from exc
    if restored_learned.state_sha256 != receipt.restored_learned_state_sha256:
        raise SWM0WS2SProtocolError("restored learned-state binding mismatch")
    return restored_learned


def parse_learned_q_intervention(
    value: Mapping[str, Any]
) -> LearnedQInterventionReceipt:
    data = _object(
        value,
        (
            "base_core_state_sha256",
            "exact_restored_parameter_bytes",
            "exact_restored_learned_state",
            "learned_parameters_sha256",
            "learned_state_sha256",
            "optimization_receipt_sha256",
            "receipt_sha256",
            "removal",
            "restored_core_state_sha256",
            "restored_learned_state_sha256",
            "restored_parameters_sha256",
            "schema_version",
            "task_manifest_sha256",
        ),
        "learned Q intervention",
    )
    if (
        _string(data["schema_version"], "learned Q schema")
        != LEARNED_Q_INTERVENTION_VERSION
    ):
        raise SWM0WS2SProtocolError("learned Q schema drifted")
    result = LearnedQInterventionReceipt(
        task_manifest_sha256=_sha256(data["task_manifest_sha256"], "task manifest SHA"),
        learned_state_sha256=_sha256(data["learned_state_sha256"], "learned state SHA"),
        optimization_receipt_sha256=_sha256(
            data["optimization_receipt_sha256"], "optimization receipt SHA"
        ),
        learned_parameters_sha256=_sha256(
            data["learned_parameters_sha256"], "learned parameters SHA"
        ),
        base_core_state_sha256=_sha256(
            data["base_core_state_sha256"], "base core state SHA"
        ),
        removal=_parse_q_removal(data["removal"]),
        restored_core_state_sha256=_sha256(
            data["restored_core_state_sha256"], "restored core state SHA"
        ),
        restored_learned_state_sha256=_sha256(
            data["restored_learned_state_sha256"], "restored learned state SHA"
        ),
        restored_parameters_sha256=_sha256(
            data["restored_parameters_sha256"], "restored parameters SHA"
        ),
        exact_restored_parameter_bytes=_boolean(
            data["exact_restored_parameter_bytes"], "exact restored bytes"
        ),
        exact_restored_learned_state=_boolean(
            data["exact_restored_learned_state"], "exact restored learned state"
        ),
        receipt_sha256=_sha256(data["receipt_sha256"], "learned Q receipt SHA"),
    )
    _same_canonical(data, result.canonical(), "learned Q intervention")
    return result


def _bound_tensor_sha256(value: np.ndarray) -> str:
    array = np.asarray(value, dtype="<f8", order="C")
    return canonical_sha256(
        {
            "bytes_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest(),
            "dtype": "float64-little-endian",
            "shape": list(array.shape),
        }
    )


def _complete_test_data(
    task: TaskSpecV2,
) -> tuple[tuple[EvaluatorCaseV2, ...], np.ndarray, np.ndarray, np.ndarray, str]:
    if type(task) is not TaskSpecV2:
        raise SWM0WS2SProtocolError("test evaluation requires exact TaskSpecV2")
    cases = tuple(task.iter_cases("test"))
    if (
        len(cases) != TEST_WORLD_COUNT
        or any(type(case) is not EvaluatorCaseV2 or case.task != task for case in cases)
        or tuple(case.world.raw_values for case in cases)
        != tuple(sorted(case.world.raw_values for case in cases))
        or len({case.world.raw_values for case in cases}) != TEST_WORLD_COUNT
    ):
        raise SWM0WS2SProtocolError("test tuple is incomplete, duplicated, or reordered")
    worlds = tuple(case.world for case in cases)
    x = compile_model_worlds(worlds)
    target_numerators = np.asarray(
        [case.target_numerators for case in cases], dtype=np.int64
    ).reshape(TEST_WORLD_COUNT, 3, 2, 2)
    targets = compile_case_target_batch_v2(cases)
    raw = np.asarray([world.raw_values for world in worlds], dtype=np.uint8)
    digest = hashlib.sha256(b"hswm-swm0w-s2s-test-dataset/v1\x00")
    digest.update(bytes.fromhex(task.structural_task_sha256))
    digest.update(raw.tobytes(order="C"))
    digest.update(np.asarray(target_numerators, dtype=">i8").tobytes(order="C"))
    return cases, x, targets, target_numerators, digest.hexdigest()


@dataclass(frozen=True, slots=True)
class StratumScore:
    role: int
    channel: int
    sample_count: int
    target_numerator_sum: int
    target_numerator_sum_squares: int
    centered_sum_squares_numerator: int
    squared_error: float
    r2: float

    def __post_init__(self) -> None:
        if type(self.role) is not int or not 0 <= self.role < 3:
            raise SWM0WS2SProtocolError("score role must be exact in-range integer")
        if type(self.channel) is not int or not 0 <= self.channel < 2:
            raise SWM0WS2SProtocolError("score channel must be exact in-range integer")
        if type(self.sample_count) is not int or self.sample_count != STRATUM_SAMPLE_COUNT:
            raise SWM0WS2SProtocolError("score must cover exactly 12,500 stratum samples")
        if type(self.target_numerator_sum) is not int:
            raise SWM0WS2SProtocolError("score target sum must be exact integer")
        if (
            type(self.target_numerator_sum_squares) is not int
            or self.target_numerator_sum_squares < 0
        ):
            raise SWM0WS2SProtocolError("score target sum squares must be non-negative")
        expected_centered = (
            self.sample_count * self.target_numerator_sum_squares
            - self.target_numerator_sum * self.target_numerator_sum
        )
        if (
            type(self.centered_sum_squares_numerator) is not int
            or self.centered_sum_squares_numerator != expected_centered
            or expected_centered <= 0
        ):
            raise SWM0WS2SProtocolError("score target variance is invalid")
        _finite(self.squared_error, "score squared error", nonnegative=True)
        _finite(self.r2, "score R2")
        denominator = float(
            expected_centered
            / (self.sample_count * 2 ** (2 * TARGET_SCALE_EXPONENT))
        )
        expected_r2 = _clean_float(1.0 - self.squared_error / denominator)
        if self.r2.hex() != expected_r2.hex():
            raise SWM0WS2SProtocolError("score R2 disagrees with exact target variance")

    def canonical(self) -> dict[str, Any]:
        return {
            "centered_sum_squares_numerator": self.centered_sum_squares_numerator,
            "channel": self.channel,
            "r2_hex": self.r2.hex(),
            "role": self.role,
            "sample_count": self.sample_count,
            "squared_error_hex": self.squared_error.hex(),
            "target_numerator_sum": self.target_numerator_sum,
            "target_numerator_sum_squares": self.target_numerator_sum_squares,
        }


@dataclass(frozen=True, slots=True)
class SixStratumScore:
    variant: ScoreVariant
    arm: S2SArm
    task_manifest_sha256: str
    structural_task_sha256: str
    learned_state_sha256: str
    evaluated_state_sha256: str
    source_receipt_sha256: str
    source_prediction_tensor_sha256: str | None
    test_dataset_sha256: str
    world_count: int
    prediction_tensor_sha256: str
    target_tensor_sha256: str
    strata: tuple[StratumScore, ...]
    worst_role: int
    worst_channel: int
    worst_r2: float
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.variant) is not ScoreVariant or type(self.arm) is not S2SArm:
            raise SWM0WS2SProtocolError("score requires exact variant/arm")
        if _VARIANT_ARM[self.variant] is not self.arm:
            raise SWM0WS2SProtocolError("score variant crosses architecture arm")
        for name in (
            "task_manifest_sha256",
            "structural_task_sha256",
            "learned_state_sha256",
            "evaluated_state_sha256",
            "source_receipt_sha256",
            "test_dataset_sha256",
            "prediction_tensor_sha256",
            "target_tensor_sha256",
            "receipt_sha256",
        ):
            _sha256(getattr(self, name), name)
        if self.source_prediction_tensor_sha256 is not None:
            _sha256(
                self.source_prediction_tensor_sha256,
                "source prediction tensor SHA",
            )
        if (self.variant is ScoreVariant.T16_BROADCAST) != (
            self.source_prediction_tensor_sha256 is not None
        ):
            raise SWM0WS2SProtocolError(
                "only broadcast scores require a source prediction binding"
            )
        if type(self.world_count) is not int or self.world_count != TEST_WORLD_COUNT:
            raise SWM0WS2SProtocolError("score must cover the complete test world set")
        expected_order = tuple((role, channel) for role in range(3) for channel in range(2))
        if (
            type(self.strata) is not tuple
            or any(type(row) is not StratumScore for row in self.strata)
            or tuple((row.role, row.channel) for row in self.strata) != expected_order
        ):
            raise SWM0WS2SProtocolError("score strata are incomplete or reordered")
        if type(self.worst_role) is not int or type(self.worst_channel) is not int:
            raise SWM0WS2SProtocolError("worst score indices must be exact integers")
        _finite(self.worst_r2, "worst R2")
        worst = min(
            (row.r2, row.role, row.channel) for row in self.strata
        )
        if (
            self.worst_r2.hex() != worst[0].hex()
            or self.worst_role != worst[1]
            or self.worst_channel != worst[2]
        ):
            raise SWM0WS2SProtocolError("score worst stratum disagrees")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SProtocolError("score receipt hash mismatch")

    @property
    def r2_matrix(self) -> tuple[tuple[float, float], ...]:
        return tuple(
            tuple(self.strata[2 * role + channel].r2 for channel in range(2))
            for role in range(3)
        )

    def unsigned(self) -> dict[str, Any]:
        return {
            "arm": self.arm.value,
            "evaluated_state_sha256": self.evaluated_state_sha256,
            "learned_state_sha256": self.learned_state_sha256,
            "prediction_tensor_sha256": self.prediction_tensor_sha256,
            "reduction_order": "LEXICOGRAPHIC_WORLD_THEN_MEMBER_NUMPY_DOT_FLOAT64",
            "schema_version": SCORE_RECEIPT_VERSION,
            "scientific_status": SCIENTIFIC_STATUS,
            "source_prediction_tensor_sha256": self.source_prediction_tensor_sha256,
            "source_receipt_sha256": self.source_receipt_sha256,
            "strata": [row.canonical() for row in self.strata],
            "structural_task_sha256": self.structural_task_sha256,
            "target_scale_exponent": TARGET_SCALE_EXPONENT,
            "target_tensor_sha256": self.target_tensor_sha256,
            "task_manifest_sha256": self.task_manifest_sha256,
            "test_dataset_sha256": self.test_dataset_sha256,
            "variant": self.variant.value,
            "world_count": self.world_count,
            "worst_channel": self.worst_channel,
            "worst_r2_hex": self.worst_r2.hex(),
            "worst_role": self.worst_role,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def score_complete_test_predictions(
    task: TaskSpecV2,
    model: LearnedS2SOperator,
    *,
    evaluated_state_sha256: str,
    source_receipt_sha256: str,
    source_prediction_tensor_sha256: str | None = None,
    variant: ScoreVariant,
    predictions: np.ndarray,
) -> SixStratumScore:
    if (
        type(task) is not TaskSpecV2
        or type(model) is not LearnedS2SOperator
        or type(variant) is not ScoreVariant
        or model.optimization.task != task
        or model.arm is not _VARIANT_ARM[variant]
    ):
        raise SWM0WS2SProtocolError("score crosses task/model/variant boundary")
    _sha256(evaluated_state_sha256, "evaluated state SHA")
    _sha256(source_receipt_sha256, "score source receipt SHA")
    if source_prediction_tensor_sha256 is not None:
        _sha256(source_prediction_tensor_sha256, "source prediction tensor SHA")
    if (variant is ScoreVariant.T16_BROADCAST) != (
        source_prediction_tensor_sha256 is not None
    ):
        raise SWM0WS2SProtocolError("broadcast source binding is missing or misplaced")
    if (
        type(predictions) is not np.ndarray
        or predictions.dtype != np.dtype(np.float64)
        or predictions.shape != (TEST_WORLD_COUNT, 3, 2, 2)
        or not np.isfinite(predictions).all()
    ):
        raise SWM0WS2SProtocolError("score predictions must be complete finite float64")
    _, _, targets, target_numerators, dataset_sha = _complete_test_data(task)
    diagnostic = stratified_r2(predictions, targets)
    rows: list[StratumScore] = []
    for role in range(3):
        for channel in range(2):
            numerator_values = target_numerators[:, role, :, channel].reshape(-1)
            observed = targets[:, role, :, channel].reshape(-1)
            estimated = predictions[:, role, :, channel].reshape(-1)
            residual = observed - estimated
            squared_error = _clean_float(float(np.dot(residual, residual)))
            target_sum = int(sum(int(value) for value in numerator_values))
            target_sum_squares = int(
                sum(int(value) * int(value) for value in numerator_values)
            )
            centered = (
                STRATUM_SAMPLE_COUNT * target_sum_squares - target_sum * target_sum
            )
            denominator = float(
                centered
                / (STRATUM_SAMPLE_COUNT * 2 ** (2 * TARGET_SCALE_EXPONENT))
            )
            r2 = _clean_float(1.0 - squared_error / denominator)
            rows.append(
                StratumScore(
                    role=role,
                    channel=channel,
                    sample_count=STRATUM_SAMPLE_COUNT,
                    target_numerator_sum=target_sum,
                    target_numerator_sum_squares=target_sum_squares,
                    centered_sum_squares_numerator=centered,
                    squared_error=squared_error,
                    r2=r2,
                )
            )
    strata = tuple(rows)
    diagnostic_values = tuple(
        tuple(row.r2 for row in strata[2 * role : 2 * role + 2])
        for role in range(3)
    )
    if diagnostic_values != diagnostic.values:
        raise SWM0WS2SProtocolError("confirmatory and diagnostic R2 kernels disagree")
    worst_r2, worst_role, worst_channel = min(
        (row.r2, row.role, row.channel) for row in strata
    )
    unsigned = {
        "arm": model.arm.value,
        "evaluated_state_sha256": evaluated_state_sha256,
        "learned_state_sha256": model.state_sha256,
        "prediction_tensor_sha256": _bound_tensor_sha256(predictions),
        "reduction_order": "LEXICOGRAPHIC_WORLD_THEN_MEMBER_NUMPY_DOT_FLOAT64",
        "schema_version": SCORE_RECEIPT_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "source_prediction_tensor_sha256": source_prediction_tensor_sha256,
        "source_receipt_sha256": source_receipt_sha256,
        "strata": [row.canonical() for row in strata],
        "structural_task_sha256": task.structural_task_sha256,
        "target_scale_exponent": TARGET_SCALE_EXPONENT,
        "target_tensor_sha256": _bound_tensor_sha256(targets),
        "task_manifest_sha256": task.manifest_sha256,
        "test_dataset_sha256": dataset_sha,
        "variant": variant.value,
        "world_count": TEST_WORLD_COUNT,
        "worst_channel": worst_channel,
        "worst_r2_hex": worst_r2.hex(),
        "worst_role": worst_role,
    }
    return SixStratumScore(
        variant=variant,
        arm=model.arm,
        task_manifest_sha256=task.manifest_sha256,
        structural_task_sha256=task.structural_task_sha256,
        learned_state_sha256=model.state_sha256,
        evaluated_state_sha256=evaluated_state_sha256,
        source_receipt_sha256=source_receipt_sha256,
        source_prediction_tensor_sha256=source_prediction_tensor_sha256,
        test_dataset_sha256=dataset_sha,
        world_count=TEST_WORLD_COUNT,
        prediction_tensor_sha256=unsigned["prediction_tensor_sha256"],
        target_tensor_sha256=unsigned["target_tensor_sha256"],
        strata=strata,
        worst_role=worst_role,
        worst_channel=worst_channel,
        worst_r2=worst_r2,
        receipt_sha256=canonical_sha256(unsigned),
    )


def _parse_stratum_score(value: Mapping[str, Any]) -> StratumScore:
    data = _object(
        value,
        (
            "centered_sum_squares_numerator",
            "channel",
            "r2_hex",
            "role",
            "sample_count",
            "squared_error_hex",
            "target_numerator_sum",
            "target_numerator_sum_squares",
        ),
        "stratum score",
    )
    result = StratumScore(
        role=_integer(data["role"], "score role"),
        channel=_integer(data["channel"], "score channel"),
        sample_count=_integer(data["sample_count"], "score sample count"),
        target_numerator_sum=_integer(data["target_numerator_sum"], "target sum"),
        target_numerator_sum_squares=_integer(
            data["target_numerator_sum_squares"], "target sum squares"
        ),
        centered_sum_squares_numerator=_integer(
            data["centered_sum_squares_numerator"], "centered sum squares"
        ),
        squared_error=_float_hex(
            data["squared_error_hex"], "squared error", nonnegative=True
        ),
        r2=_float_hex(data["r2_hex"], "stratum R2"),
    )
    _same_canonical(data, result.canonical(), "stratum score")
    return result


def parse_six_stratum_score(value: Mapping[str, Any]) -> SixStratumScore:
    data = _object(
        value,
        (
            "arm",
            "evaluated_state_sha256",
            "learned_state_sha256",
            "prediction_tensor_sha256",
            "receipt_sha256",
            "reduction_order",
            "schema_version",
            "scientific_status",
            "source_prediction_tensor_sha256",
            "source_receipt_sha256",
            "strata",
            "structural_task_sha256",
            "target_scale_exponent",
            "target_tensor_sha256",
            "task_manifest_sha256",
            "test_dataset_sha256",
            "variant",
            "world_count",
            "worst_channel",
            "worst_r2_hex",
            "worst_role",
        ),
        "six-stratum score",
    )
    if (
        _string(data["schema_version"], "score schema") != SCORE_RECEIPT_VERSION
        or _string(data["scientific_status"], "score status") != SCIENTIFIC_STATUS
        or _string(data["reduction_order"], "score reduction order")
        != "LEXICOGRAPHIC_WORLD_THEN_MEMBER_NUMPY_DOT_FLOAT64"
        or _integer(data["target_scale_exponent"], "target scale")
        != TARGET_SCALE_EXPONENT
    ):
        raise SWM0WS2SProtocolError("score fixed contract drifted")
    result = SixStratumScore(
        variant=_enum(ScoreVariant, data["variant"], "score variant"),
        arm=_enum(S2SArm, data["arm"], "score arm"),
        task_manifest_sha256=_sha256(data["task_manifest_sha256"], "task manifest SHA"),
        structural_task_sha256=_sha256(
            data["structural_task_sha256"], "structural task SHA"
        ),
        learned_state_sha256=_sha256(data["learned_state_sha256"], "learned state SHA"),
        evaluated_state_sha256=_sha256(
            data["evaluated_state_sha256"], "evaluated state SHA"
        ),
        source_receipt_sha256=_sha256(
            data["source_receipt_sha256"], "score source receipt SHA"
        ),
        source_prediction_tensor_sha256=(
            None
            if data["source_prediction_tensor_sha256"] is None
            else _sha256(
                data["source_prediction_tensor_sha256"],
                "source prediction tensor SHA",
            )
        ),
        test_dataset_sha256=_sha256(data["test_dataset_sha256"], "test dataset SHA"),
        world_count=_integer(data["world_count"], "score world count"),
        prediction_tensor_sha256=_sha256(
            data["prediction_tensor_sha256"], "prediction tensor SHA"
        ),
        target_tensor_sha256=_sha256(data["target_tensor_sha256"], "target tensor SHA"),
        strata=tuple(
            _parse_stratum_score(item)
            for item in _list(data["strata"], "score strata", length=6)
        ),
        worst_role=_integer(data["worst_role"], "worst role"),
        worst_channel=_integer(data["worst_channel"], "worst channel"),
        worst_r2=_float_hex(data["worst_r2_hex"], "worst R2"),
        receipt_sha256=_sha256(data["receipt_sha256"], "score receipt SHA"),
    )
    _same_canonical(data, result.canonical(), "six-stratum score")
    return result


@dataclass(frozen=True, slots=True)
class ModelSymmetryResult:
    arm: S2SArm
    learned_state_sha256: str
    action_count: int
    world_count: int
    max_abs_error: float
    within_tolerance: bool

    def __post_init__(self) -> None:
        if type(self.arm) is not S2SArm:
            raise SWM0WS2SProtocolError("symmetry row requires exact arm")
        _sha256(self.learned_state_sha256, "symmetry learned state SHA")
        if type(self.action_count) is not int or self.action_count != 8:
            raise SWM0WS2SProtocolError("symmetry must cover all eight S2^3 actions")
        if type(self.world_count) is not int or self.world_count != DOMAIN_WORLD_COUNT:
            raise SWM0WS2SProtocolError("symmetry must cover the complete finite domain")
        _finite(self.max_abs_error, "symmetry max error", nonnegative=True)
        if type(self.within_tolerance) is not bool:
            raise SWM0WS2SProtocolError("symmetry tolerance flag must be exact bool")

    def canonical(self) -> dict[str, Any]:
        return {
            "action_count": self.action_count,
            "arm": self.arm.value,
            "learned_state_sha256": self.learned_state_sha256,
            "max_abs_error_hex": self.max_abs_error.hex(),
            "within_tolerance": self.within_tolerance,
            "world_count": self.world_count,
        }


@dataclass(frozen=True, slots=True)
class IntegrityReceipt:
    task_manifest_sha256: str
    structural_task_sha256: str
    family_definition_sha256: str
    family_certificate_sha256: str
    domain_world_count: int
    split_counts: tuple[tuple[str, int], ...]
    structural_audit_sha256: str
    model_symmetry: tuple[ModelSymmetryResult, ...]
    symmetry_atol: float
    symmetry_rtol: float
    pair_null_epsilon: float
    pcap_max_r2: float
    q_removed_max_r2: float
    restore_parameter_bytes_equal: bool
    restore_prediction_bytes_equal: bool
    errors: tuple[str, ...]
    valid: bool
    receipt_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "task_manifest_sha256",
            "structural_task_sha256",
            "family_definition_sha256",
            "family_certificate_sha256",
            "structural_audit_sha256",
            "receipt_sha256",
        ):
            _sha256(getattr(self, name), name)
        if (
            self.family_definition_sha256 != FAMILY_DEFINITION_SHA256
            or self.family_certificate_sha256 != FAMILY_CERTIFICATE_SHA256
            or type(self.domain_world_count) is not int
            or self.domain_world_count != DOMAIN_WORLD_COUNT
            or type(self.split_counts) is not tuple
            or self.split_counts != tuple((name, SPLIT_COUNTS[name]) for name in SPLITS)
        ):
            raise SWM0WS2SProtocolError("integrity finite-family binding drifted")
        if (
            type(self.model_symmetry) is not tuple
            or tuple(row.arm for row in self.model_symmetry) != ALL_ARMS
            or any(type(row) is not ModelSymmetryResult for row in self.model_symmetry)
        ):
            raise SWM0WS2SProtocolError("integrity symmetry roster drifted")
        for name in (
            "symmetry_atol",
            "symmetry_rtol",
            "pair_null_epsilon",
        ):
            _finite(getattr(self, name), name, nonnegative=True)
        _finite(self.pcap_max_r2, "P_CAP18 max R2")
        _finite(self.q_removed_max_r2, "Q-removed max R2")
        if (
            type(self.restore_parameter_bytes_equal) is not bool
            or type(self.restore_prediction_bytes_equal) is not bool
            or type(self.valid) is not bool
            or type(self.errors) is not tuple
            or any(type(reason) is not str or not reason for reason in self.errors)
            or self.errors != tuple(dict.fromkeys(self.errors))
        ):
            raise SWM0WS2SProtocolError("integrity flags/errors require exact types")
        expected_valid = (
            not self.errors
            and all(row.within_tolerance for row in self.model_symmetry)
            and self.pcap_max_r2 <= self.pair_null_epsilon
            and self.q_removed_max_r2 <= self.pair_null_epsilon
            and self.restore_parameter_bytes_equal
            and self.restore_prediction_bytes_equal
        )
        if self.valid is not expected_valid:
            raise SWM0WS2SProtocolError("integrity validity does not recompute")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SProtocolError("integrity receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "domain_world_count": self.domain_world_count,
            "errors": list(self.errors),
            "family_certificate_sha256": self.family_certificate_sha256,
            "family_definition_sha256": self.family_definition_sha256,
            "model_symmetry": [row.canonical() for row in self.model_symmetry],
            "pair_null_epsilon_hex": self.pair_null_epsilon.hex(),
            "pcap_max_r2_hex": self.pcap_max_r2.hex(),
            "q_removed_max_r2_hex": self.q_removed_max_r2.hex(),
            "restore_parameter_bytes_equal": self.restore_parameter_bytes_equal,
            "restore_prediction_bytes_equal": self.restore_prediction_bytes_equal,
            "schema_version": INTEGRITY_RECEIPT_VERSION,
            "scientific_status": SCIENTIFIC_STATUS,
            "split_counts": [
                {"count": count, "split": split} for split, count in self.split_counts
            ],
            "structural_audit_sha256": self.structural_audit_sha256,
            "structural_task_sha256": self.structural_task_sha256,
            "symmetry_atol_hex": self.symmetry_atol.hex(),
            "symmetry_rtol_hex": self.symmetry_rtol.hex(),
            "task_manifest_sha256": self.task_manifest_sha256,
            "valid": self.valid,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def _member_action(array: np.ndarray, swaps: tuple[bool, bool, bool]) -> np.ndarray:
    moved = np.array(array, copy=True)
    for role, swap in enumerate(swaps):
        if swap:
            moved[:, role, [0, 1], :] = moved[:, role, [1, 0], :]
    return moved


def _structural_audit(task: TaskSpecV2) -> tuple[str, tuple[str, ...], np.ndarray]:
    cases = tuple(task.iter_cases())
    errors: list[str] = []
    if len(cases) != DOMAIN_WORLD_COUNT:
        errors.append("DOMAIN_WORLD_COUNT_DRIFT")
    raw = np.asarray([case.world.raw_values for case in cases], dtype=np.int64)
    targets = np.asarray(
        [case.target_numerators for case in cases], dtype=np.int64
    ).reshape(DOMAIN_WORLD_COUNT, 6, 2)
    split_labels = tuple(case.split for case in cases)
    masks = {
        split: np.asarray([label == split for label in split_labels], dtype=bool)
        for split in SPLITS
    }
    split_summary: list[dict[str, Any]] = []
    for split in SPLITS:
        selected = raw[masks[split]]
        if len(selected) != SPLIT_COUNTS[split]:
            errors.append(f"{split.upper()}_COUNT_DRIFT")
        marginal_hashes = []
        for order in range(1, 6):
            expected = len(selected) // (FIELD_ORDER**order)
            for coordinates in itertools.combinations(range(6), order):
                code = np.zeros(len(selected), dtype=np.int64)
                for coordinate in coordinates:
                    code = FIELD_ORDER * code + selected[:, coordinate]
                histogram = np.bincount(code, minlength=FIELD_ORDER**order)
                if not np.all(histogram == expected):
                    errors.append("NORMALIZED_MARGINAL_DRIFT")
                marginal_hashes.append(
                    hashlib.sha256(np.asarray(histogram, dtype=">i8").tobytes()).hexdigest()
                )
        selected_targets = targets[masks[split]]
        sums = np.sum(selected_targets, axis=0, dtype=np.int64)
        sum_squares = np.sum(selected_targets * selected_targets, axis=0, dtype=np.int64)
        if np.any(sums != 0):
            errors.append("TARGET_CENTERING_DRIFT")
        if np.any(sum_squares <= 0):
            errors.append("TARGET_VARIANCE_DRIFT")
        for output in range(6):
            for channel in range(2):
                vector = selected_targets[:, output, channel]
                for other in range(6):
                    if other == output:
                        continue
                    table = np.zeros((FIELD_ORDER, FIELD_ORDER), dtype=np.int64)
                    np.add.at(
                        table,
                        (selected[:, output], selected[:, other]),
                        vector,
                    )
                    if np.any(table):
                        errors.append("RECIPIENT_STAR_ORTHOGONALITY_DRIFT")
        split_summary.append(
            {
                "count": len(selected),
                "marginal_histogram_sha256": canonical_sha256(marginal_hashes),
                "split": split,
                "target_sum_sha256": hashlib.sha256(
                    np.asarray(sums, dtype=">i8").tobytes()
                ).hexdigest(),
                "target_sum_squares_sha256": hashlib.sha256(
                    np.asarray(sum_squares, dtype=">i8").tobytes()
                ).hexdigest(),
            }
        )

    # Exact rank-two witness for every recipient/channel flattening.
    for output in range(6):
        for channel in range(2):
            tensor = targets[:, output, channel].reshape((FIELD_ORDER,) * 6)
            matrix = np.moveaxis(tensor, output, 0).reshape(FIELD_ORDER, -1)
            rank_two = False
            for left, right in itertools.combinations(range(FIELD_ORDER), 2):
                nonzero = np.flatnonzero((matrix[left] != 0) | (matrix[right] != 0))
                if nonzero.size:
                    column = int(nonzero[0])
                    determinants = (
                        matrix[left, column] * matrix[right]
                        - matrix[right, column] * matrix[left]
                    )
                    rank_two |= bool(np.any(determinants))
            if not rank_two:
                errors.append("TARGET_RANK_TWO_DRIFT")

    weights = np.asarray(
        [FIELD_ORDER ** (5 - coordinate) for coordinate in range(6)],
        dtype=np.int64,
    )
    for action in ALL_MEMBER_PERMUTATIONS:
        permuted = raw.copy()
        output_order = list(range(6))
        for role, swap in enumerate(action.swaps):
            if swap:
                left = 2 * role
                permuted[:, [left, left + 1]] = permuted[:, [left + 1, left]]
                output_order[left], output_order[left + 1] = (
                    output_order[left + 1],
                    output_order[left],
                )
        indices = permuted @ weights
        if not np.array_equal(targets[indices], targets[:, output_order]):
            errors.append("TARGET_S2_CUBED_DRIFT")

    summary = {
        "domain_world_count": len(cases),
        "family_certificate_sha256": task.family_certificate_sha256,
        "family_definition_sha256": task.family_definition_sha256,
        "rank_two_output_count": 12,
        "split_summary": split_summary,
        "structural_task_sha256": task.structural_task_sha256,
        "target_s2_cubed_action_count": 8,
    }
    return canonical_sha256(summary), tuple(dict.fromkeys(errors)), raw


def build_integrity_receipt(
    task: TaskSpecV2,
    models: tuple[LearnedS2SOperator, ...],
    config: S2SProtocolConfig,
    *,
    pcap_score: SixStratumScore,
    q_removed_score: SixStratumScore,
    base_score: SixStratumScore,
    restored_score: SixStratumScore,
    restore_parameter_bytes_equal: bool,
) -> IntegrityReceipt:
    if (
        type(task) is not TaskSpecV2
        or type(models) is not tuple
        or tuple(model.arm for model in models) != ALL_ARMS
        or any(type(model) is not LearnedS2SOperator for model in models)
        or type(config) is not S2SProtocolConfig
    ):
        raise SWM0WS2SProtocolError("integrity audit requires exact task/model roster/config")
    errors: list[str] = []
    for arm, model in zip(ALL_ARMS, models, strict=True):
        if (
            model.optimization.task != task
            or model.config != config.config_for(arm)
            or model.parameter_count != 870
            or architecture_receipt(arm).parameter_count != 870
        ):
            errors.append(f"{arm.value}_MODEL_BINDING_DRIFT")
    structural_sha, structural_errors, raw = _structural_audit(task)
    errors.extend(structural_errors)
    worlds = tuple(task.case(tuple(int(value) for value in row)).world for row in raw)
    x = compile_model_worlds(worlds)
    symmetry_rows: list[ModelSymmetryResult] = []
    for model in models:
        baseline = model.forward(x)
        max_abs = 0.0
        within_tolerance = True
        for action in ALL_MEMBER_PERMUTATIONS:
            moved = _member_action(x, action.swaps)
            expected = _member_action(baseline, action.swaps)
            actual = model.forward(moved)
            difference = np.abs(actual - expected)
            max_abs = max(max_abs, float(np.max(difference)))
            action_within = bool(np.all(
                difference
                <= config.symmetry_atol + config.symmetry_rtol * np.abs(expected)
            ))
            within_tolerance &= action_within
            if not action_within:
                errors.append(f"{model.arm.value}_S2_CUBED_TOLERANCE_EXCEEDED")
        symmetry_rows.append(
            ModelSymmetryResult(
                arm=model.arm,
                learned_state_sha256=model.state_sha256,
                action_count=8,
                world_count=DOMAIN_WORLD_COUNT,
                max_abs_error=_clean_float(max_abs),
                within_tolerance=within_tolerance,
            )
        )
    score_roster = (pcap_score, q_removed_score, base_score, restored_score)
    if any(score.task_manifest_sha256 != task.manifest_sha256 for score in score_roster):
        errors.append("CROSS_TASK_SCORE")
    if pcap_score.variant is not ScoreVariant.P_CAP18_BASE:
        errors.append("PCAP_SCORE_VARIANT_DRIFT")
    if q_removed_score.variant is not ScoreVariant.T16_Q_REMOVED:
        errors.append("Q_REMOVED_SCORE_VARIANT_DRIFT")
    if base_score.variant is not ScoreVariant.T16_BASE:
        errors.append("T16_BASE_SCORE_VARIANT_DRIFT")
    if restored_score.variant is not ScoreVariant.T16_RESTORED:
        errors.append("T16_RESTORED_SCORE_VARIANT_DRIFT")
    pcap_max = _clean_float(max(row.r2 for row in pcap_score.strata))
    q_max = _clean_float(max(row.r2 for row in q_removed_score.strata))
    if pcap_max > config.pair_null_epsilon:
        errors.append("PCAP_NULL_R2_EXCEEDS_EPSILON")
    if q_max > config.pair_null_epsilon:
        errors.append("Q_REMOVED_NULL_R2_EXCEEDS_EPSILON")
    prediction_equal = (
        base_score.prediction_tensor_sha256 == restored_score.prediction_tensor_sha256
        and base_score.strata == restored_score.strata
    )
    if not restore_parameter_bytes_equal:
        errors.append("Q_RESTORE_PARAMETER_BYTES_DRIFT")
    if not prediction_equal:
        errors.append("Q_RESTORE_PREDICTION_BYTES_DRIFT")
    errors_tuple = tuple(dict.fromkeys(errors))
    valid = not errors_tuple
    values = {
        "task_manifest_sha256": task.manifest_sha256,
        "structural_task_sha256": task.structural_task_sha256,
        "family_definition_sha256": task.family_definition_sha256,
        "family_certificate_sha256": task.family_certificate_sha256,
        "domain_world_count": DOMAIN_WORLD_COUNT,
        "split_counts": tuple((name, SPLIT_COUNTS[name]) for name in SPLITS),
        "structural_audit_sha256": structural_sha,
        "model_symmetry": tuple(symmetry_rows),
        "symmetry_atol": config.symmetry_atol,
        "symmetry_rtol": config.symmetry_rtol,
        "pair_null_epsilon": config.pair_null_epsilon,
        "pcap_max_r2": pcap_max,
        "q_removed_max_r2": q_max,
        "restore_parameter_bytes_equal": restore_parameter_bytes_equal,
        "restore_prediction_bytes_equal": prediction_equal,
        "errors": errors_tuple,
        "valid": valid,
    }
    unsigned = {
        "domain_world_count": DOMAIN_WORLD_COUNT,
        "errors": list(errors_tuple),
        "family_certificate_sha256": task.family_certificate_sha256,
        "family_definition_sha256": task.family_definition_sha256,
        "model_symmetry": [row.canonical() for row in symmetry_rows],
        "pair_null_epsilon_hex": config.pair_null_epsilon.hex(),
        "pcap_max_r2_hex": pcap_max.hex(),
        "q_removed_max_r2_hex": q_max.hex(),
        "restore_parameter_bytes_equal": restore_parameter_bytes_equal,
        "restore_prediction_bytes_equal": prediction_equal,
        "schema_version": INTEGRITY_RECEIPT_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "split_counts": [
            {"count": SPLIT_COUNTS[name], "split": name} for name in SPLITS
        ],
        "structural_audit_sha256": structural_sha,
        "structural_task_sha256": task.structural_task_sha256,
        "symmetry_atol_hex": config.symmetry_atol.hex(),
        "symmetry_rtol_hex": config.symmetry_rtol.hex(),
        "task_manifest_sha256": task.manifest_sha256,
        "valid": valid,
    }
    return IntegrityReceipt(**values, receipt_sha256=canonical_sha256(unsigned))


def _parse_symmetry_row(value: Mapping[str, Any]) -> ModelSymmetryResult:
    data = _object(
        value,
        (
            "action_count",
            "arm",
            "learned_state_sha256",
            "max_abs_error_hex",
            "within_tolerance",
            "world_count",
        ),
        "model symmetry result",
    )
    result = ModelSymmetryResult(
        arm=_enum(S2SArm, data["arm"], "symmetry arm"),
        learned_state_sha256=_sha256(
            data["learned_state_sha256"], "symmetry learned state SHA"
        ),
        action_count=_integer(data["action_count"], "symmetry action count"),
        world_count=_integer(data["world_count"], "symmetry world count"),
        max_abs_error=_float_hex(
            data["max_abs_error_hex"], "symmetry max error", nonnegative=True
        ),
        within_tolerance=_boolean(
            data["within_tolerance"], "symmetry within tolerance"
        ),
    )
    _same_canonical(data, result.canonical(), "model symmetry result")
    return result


def parse_integrity_receipt(value: Mapping[str, Any]) -> IntegrityReceipt:
    data = _object(
        value,
        (
            "domain_world_count",
            "errors",
            "family_certificate_sha256",
            "family_definition_sha256",
            "model_symmetry",
            "pair_null_epsilon_hex",
            "pcap_max_r2_hex",
            "q_removed_max_r2_hex",
            "receipt_sha256",
            "restore_parameter_bytes_equal",
            "restore_prediction_bytes_equal",
            "schema_version",
            "scientific_status",
            "split_counts",
            "structural_audit_sha256",
            "structural_task_sha256",
            "symmetry_atol_hex",
            "symmetry_rtol_hex",
            "task_manifest_sha256",
            "valid",
        ),
        "integrity receipt",
    )
    if (
        _string(data["schema_version"], "integrity schema") != INTEGRITY_RECEIPT_VERSION
        or _string(data["scientific_status"], "integrity status") != SCIENTIFIC_STATUS
    ):
        raise SWM0WS2SProtocolError("integrity fixed contract drifted")
    split_counts = tuple(
        (
            _string(_object(row, ("count", "split"), "split count")["split"], "split"),
            _integer(row["count"], "split count"),
        )
        for row in _list(data["split_counts"], "split counts", length=3)
    )
    result = IntegrityReceipt(
        task_manifest_sha256=_sha256(data["task_manifest_sha256"], "task manifest SHA"),
        structural_task_sha256=_sha256(
            data["structural_task_sha256"], "structural task SHA"
        ),
        family_definition_sha256=_sha256(
            data["family_definition_sha256"], "family definition SHA"
        ),
        family_certificate_sha256=_sha256(
            data["family_certificate_sha256"], "family certificate SHA"
        ),
        domain_world_count=_integer(data["domain_world_count"], "domain world count"),
        split_counts=split_counts,
        structural_audit_sha256=_sha256(
            data["structural_audit_sha256"], "structural audit SHA"
        ),
        model_symmetry=tuple(
            _parse_symmetry_row(item)
            for item in _list(data["model_symmetry"], "model symmetry", length=3)
        ),
        symmetry_atol=_float_hex(
            data["symmetry_atol_hex"], "symmetry atol", nonnegative=True
        ),
        symmetry_rtol=_float_hex(
            data["symmetry_rtol_hex"], "symmetry rtol", nonnegative=True
        ),
        pair_null_epsilon=_float_hex(
            data["pair_null_epsilon_hex"], "pair-null epsilon", nonnegative=True
        ),
        pcap_max_r2=_float_hex(data["pcap_max_r2_hex"], "P_CAP18 max R2"),
        q_removed_max_r2=_float_hex(
            data["q_removed_max_r2_hex"], "Q-removed max R2"
        ),
        restore_parameter_bytes_equal=_boolean(
            data["restore_parameter_bytes_equal"], "restore parameter equality"
        ),
        restore_prediction_bytes_equal=_boolean(
            data["restore_prediction_bytes_equal"], "restore prediction equality"
        ),
        errors=tuple(
            _string(item, "integrity error")
            for item in _list(data["errors"], "integrity errors")
        ),
        valid=_boolean(data["valid"], "integrity validity"),
        receipt_sha256=_sha256(data["receipt_sha256"], "integrity receipt SHA"),
    )
    _same_canonical(data, result.canonical(), "integrity receipt")
    return result


@dataclass(frozen=True, slots=True)
class TaskMetricReceipt:
    draw_index: int
    task_manifest_sha256: str
    structural_task_sha256: str
    protocol_config_sha256: str
    model_archive_sha256s: tuple[str, ...]
    fit_replay_sha256s: tuple[str, ...]
    score_receipt_sha256s: tuple[str, ...]
    learned_q_receipt_sha256: str
    integrity_receipt_sha256: str
    integrity_valid: bool
    q: float
    b: float
    r: float
    c: float
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.draw_index) is not int or self.draw_index < 0:
            raise SWM0WS2SProtocolError("task metric draw index must be exact")
        for name in (
            "task_manifest_sha256",
            "structural_task_sha256",
            "protocol_config_sha256",
            "learned_q_receipt_sha256",
            "integrity_receipt_sha256",
            "receipt_sha256",
        ):
            _sha256(getattr(self, name), name)
        if (
            type(self.model_archive_sha256s) is not tuple
            or len(self.model_archive_sha256s) != len(ALL_ARMS)
            or type(self.fit_replay_sha256s) is not tuple
            or len(self.fit_replay_sha256s) != len(ALL_ARMS)
            or type(self.score_receipt_sha256s) is not tuple
            or len(self.score_receipt_sha256s) != len(ScoreVariant)
        ):
            raise SWM0WS2SProtocolError("task metric artifact roster is incomplete")
        for index, digest in enumerate(
            self.model_archive_sha256s
            + self.fit_replay_sha256s
            + self.score_receipt_sha256s
        ):
            _sha256(digest, f"task metric artifact SHA {index}")
        if type(self.integrity_valid) is not bool:
            raise SWM0WS2SProtocolError("task metric integrity flag must be exact bool")
        for name in ("q", "b", "r", "c"):
            _finite(getattr(self, name), f"task metric {name}")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SProtocolError("task metric receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "b_hex": self.b.hex(),
            "c_hex": self.c.hex(),
            "draw_index": self.draw_index,
            "fit_replay_sha256s": list(self.fit_replay_sha256s),
            "integrity_receipt_sha256": self.integrity_receipt_sha256,
            "integrity_valid": self.integrity_valid,
            "learned_q_receipt_sha256": self.learned_q_receipt_sha256,
            "model_archive_sha256s": list(self.model_archive_sha256s),
            "q_hex": self.q.hex(),
            "r_hex": self.r.hex(),
            "protocol_config_sha256": self.protocol_config_sha256,
            "schema_version": TASK_METRIC_VERSION,
            "score_receipt_sha256s": list(self.score_receipt_sha256s),
            "structural_task_sha256": self.structural_task_sha256,
            "task_manifest_sha256": self.task_manifest_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def _metric_values(scores: tuple[SixStratumScore, ...]) -> tuple[float, float, float, float]:
    if (
        type(scores) is not tuple
        or len(scores) != len(ScoreVariant)
        or tuple(score.variant for score in scores) != tuple(ScoreVariant)
        or any(type(score) is not SixStratumScore for score in scores)
    ):
        raise SWM0WS2SProtocolError("task metrics require all score variants in order")
    by_variant = {score.variant: score for score in scores}
    base = by_variant[ScoreVariant.T16_BASE].strata
    broadcast = by_variant[ScoreVariant.T16_BROADCAST].strata
    cycles = (
        by_variant[ScoreVariant.T16_CYCLE_120].strata,
        by_variant[ScoreVariant.T16_CYCLE_201].strata,
    )
    q_value = _clean_float(min(row.r2 for row in base))
    b_value = _clean_float(
        min(left.r2 - right.r2 for left, right in zip(base, broadcast, strict=True))
    )
    r_value = _clean_float(
        min(
            left.r2 - right.r2
            for cycle in cycles
            for left, right in zip(base, cycle, strict=True)
        )
    )
    c_value = _clean_float(
        min(row.r2 for row in base)
        - min(row.r2 for row in by_variant[ScoreVariant.DS870_BASE].strata)
    )
    return q_value, b_value, r_value, c_value


def build_task_metric_receipt(
    task: TaskSpecV2,
    config: S2SProtocolConfig,
    archives: tuple[LearnedModelArchive, ...],
    replays: tuple[FitReplayReceipt, ...],
    scores: tuple[SixStratumScore, ...],
    learned_q: LearnedQInterventionReceipt,
    integrity: IntegrityReceipt,
) -> TaskMetricReceipt:
    if (
        type(task) is not TaskSpecV2
        or type(config) is not S2SProtocolConfig
        or type(archives) is not tuple
        or type(replays) is not tuple
        or tuple(archive.arm for archive in archives) != ALL_ARMS
        or tuple(replay.arm for replay in replays) != ALL_ARMS
        or any(type(archive) is not LearnedModelArchive for archive in archives)
        or any(type(replay) is not FitReplayReceipt for replay in replays)
        or type(learned_q) is not LearnedQInterventionReceipt
        or type(integrity) is not IntegrityReceipt
    ):
        raise SWM0WS2SProtocolError("task metric artifact types/roster drifted")
    q_value, b_value, r_value, c_value = _metric_values(scores)
    values = {
        "draw_index": task.draw_index,
        "task_manifest_sha256": task.manifest_sha256,
        "structural_task_sha256": task.structural_task_sha256,
        "protocol_config_sha256": config.receipt_sha256,
        "model_archive_sha256s": tuple(item.receipt_sha256 for item in archives),
        "fit_replay_sha256s": tuple(item.receipt_sha256 for item in replays),
        "score_receipt_sha256s": tuple(item.receipt_sha256 for item in scores),
        "learned_q_receipt_sha256": learned_q.receipt_sha256,
        "integrity_receipt_sha256": integrity.receipt_sha256,
        "integrity_valid": integrity.valid,
        "q": q_value,
        "b": b_value,
        "r": r_value,
        "c": c_value,
    }
    unsigned = {
        "b_hex": b_value.hex(),
        "c_hex": c_value.hex(),
        "draw_index": task.draw_index,
        "fit_replay_sha256s": list(values["fit_replay_sha256s"]),
        "integrity_receipt_sha256": integrity.receipt_sha256,
        "integrity_valid": integrity.valid,
        "learned_q_receipt_sha256": learned_q.receipt_sha256,
        "model_archive_sha256s": list(values["model_archive_sha256s"]),
        "q_hex": q_value.hex(),
        "r_hex": r_value.hex(),
        "protocol_config_sha256": config.receipt_sha256,
        "schema_version": TASK_METRIC_VERSION,
        "score_receipt_sha256s": list(values["score_receipt_sha256s"]),
        "structural_task_sha256": task.structural_task_sha256,
        "task_manifest_sha256": task.manifest_sha256,
    }
    return TaskMetricReceipt(
        **values,
        receipt_sha256=canonical_sha256(unsigned),
    )


def parse_task_metric_receipt(value: Mapping[str, Any]) -> TaskMetricReceipt:
    data = _object(
        value,
        (
            "b_hex",
            "c_hex",
            "draw_index",
            "fit_replay_sha256s",
            "integrity_receipt_sha256",
            "integrity_valid",
            "learned_q_receipt_sha256",
            "model_archive_sha256s",
            "q_hex",
            "r_hex",
            "protocol_config_sha256",
            "receipt_sha256",
            "schema_version",
            "score_receipt_sha256s",
            "structural_task_sha256",
            "task_manifest_sha256",
        ),
        "task metric receipt",
    )
    if _string(data["schema_version"], "task metric schema") != TASK_METRIC_VERSION:
        raise SWM0WS2SProtocolError("task metric schema drifted")
    result = TaskMetricReceipt(
        draw_index=_integer(data["draw_index"], "metric draw index", minimum=0),
        task_manifest_sha256=_sha256(data["task_manifest_sha256"], "task manifest SHA"),
        structural_task_sha256=_sha256(
            data["structural_task_sha256"], "structural task SHA"
        ),
        protocol_config_sha256=_sha256(
            data["protocol_config_sha256"], "protocol config SHA"
        ),
        model_archive_sha256s=tuple(
            _sha256(item, "model archive SHA")
            for item in _list(data["model_archive_sha256s"], "model archive SHAs", length=3)
        ),
        fit_replay_sha256s=tuple(
            _sha256(item, "fit replay SHA")
            for item in _list(data["fit_replay_sha256s"], "fit replay SHAs", length=3)
        ),
        score_receipt_sha256s=tuple(
            _sha256(item, "score receipt SHA")
            for item in _list(
                data["score_receipt_sha256s"], "score receipt SHAs", length=8
            )
        ),
        learned_q_receipt_sha256=_sha256(
            data["learned_q_receipt_sha256"], "learned Q receipt SHA"
        ),
        integrity_receipt_sha256=_sha256(
            data["integrity_receipt_sha256"], "integrity receipt SHA"
        ),
        integrity_valid=_boolean(data["integrity_valid"], "integrity valid"),
        q=_float_hex(data["q_hex"], "task Q"),
        b=_float_hex(data["b_hex"], "task B"),
        r=_float_hex(data["r_hex"], "task R"),
        c=_float_hex(data["c_hex"], "task C"),
        receipt_sha256=_sha256(data["receipt_sha256"], "task metric receipt SHA"),
    )
    _same_canonical(data, result.canonical(), "task metric receipt")
    return result


@dataclass(frozen=True, slots=True)
class TaskEvaluationReceipt:
    task: TaskSpecV2
    config: S2SProtocolConfig
    archives: tuple[LearnedModelArchive, ...]
    replays: tuple[FitReplayReceipt, ...]
    learned_q: LearnedQInterventionReceipt
    scores: tuple[SixStratumScore, ...]
    integrity: IntegrityReceipt
    metrics: TaskMetricReceipt
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.task) is not TaskSpecV2:
            raise SWM0WS2SProtocolError("task evaluation requires exact task")
        if type(self.config) is not S2SProtocolConfig:
            raise SWM0WS2SProtocolError("task evaluation requires exact protocol config")
        _sha256(self.receipt_sha256, "task evaluation receipt SHA")
        if (
            type(self.archives) is not tuple
            or tuple(item.arm for item in self.archives) != ALL_ARMS
            or any(type(item) is not LearnedModelArchive for item in self.archives)
            or type(self.replays) is not tuple
            or tuple(item.arm for item in self.replays) != ALL_ARMS
            or any(type(item) is not FitReplayReceipt for item in self.replays)
            or type(self.learned_q) is not LearnedQInterventionReceipt
            or type(self.scores) is not tuple
            or tuple(item.variant for item in self.scores) != tuple(ScoreVariant)
            or any(type(item) is not SixStratumScore for item in self.scores)
            or type(self.integrity) is not IntegrityReceipt
            or type(self.metrics) is not TaskMetricReceipt
        ):
            raise SWM0WS2SProtocolError("task evaluation artifact roster drifted")
        task = self.task
        for arm, archive, replay in zip(
            ALL_ARMS, self.archives, self.replays, strict=True
        ):
            optimization = archive.optimization
            if (
                optimization.task != task
                or optimization.config != self.config.config_for(arm)
                or replay.task_manifest_sha256 != task.manifest_sha256
                or replay.original_learned_state_sha256 != archive.learned_state_sha256
                or replay.original_optimization_receipt_sha256
                != optimization.receipt_sha256
                or replay.original_history_sha256 != optimization.history_sha256
                or replay.original_parameters_sha256 != archive.parameters_sha256
            ):
                raise SWM0WS2SProtocolError("task evaluation fit artifact crosses slot")
        t_archive, p_archive, d_archive = self.archives
        if (
            self.learned_q.task_manifest_sha256 != task.manifest_sha256
            or self.learned_q.learned_state_sha256 != t_archive.learned_state_sha256
            or self.learned_q.optimization_receipt_sha256
            != t_archive.optimization.receipt_sha256
            or self.learned_q.learned_parameters_sha256
            != t_archive.parameters_sha256
            or self.integrity.task_manifest_sha256 != task.manifest_sha256
            or self.integrity.structural_task_sha256 != task.structural_task_sha256
        ):
            raise SWM0WS2SProtocolError("task evaluation intervention/integrity crosses task")
        if (
            tuple(row.learned_state_sha256 for row in self.integrity.model_symmetry)
            != tuple(archive.learned_state_sha256 for archive in self.archives)
            or self.integrity.symmetry_atol.hex() != self.config.symmetry_atol.hex()
            or self.integrity.symmetry_rtol.hex() != self.config.symmetry_rtol.hex()
            or self.integrity.pair_null_epsilon.hex()
            != self.config.pair_null_epsilon.hex()
        ):
            raise SWM0WS2SProtocolError("task integrity crosses model/config")
        archives_by_arm = {item.arm: item for item in self.archives}
        base_states = {
            item.arm: item.model().as_unlabeled_operator().state_sha256
            for item in self.archives
        }
        if (
            self.learned_q.base_core_state_sha256 != base_states[S2SArm.T16]
            or self.learned_q.removal.base_state_sha256 != base_states[S2SArm.T16]
            or self.learned_q.restored_core_state_sha256 != base_states[S2SArm.T16]
        ):
            raise SWM0WS2SProtocolError("task evaluation Q core binding drifted")
        score_map = {item.variant: item for item in self.scores}
        for score in self.scores:
            archive = archives_by_arm[score.arm]
            if (
                score.task_manifest_sha256 != task.manifest_sha256
                or score.structural_task_sha256 != task.structural_task_sha256
                or score.learned_state_sha256 != archive.learned_state_sha256
            ):
                raise SWM0WS2SProtocolError("task evaluation score crosses task/model")
            if score.variant in {
                ScoreVariant.T16_Q_REMOVED,
                ScoreVariant.T16_RESTORED,
                ScoreVariant.T16_CYCLE_120,
                ScoreVariant.T16_CYCLE_201,
            }:
                expected_source = self.learned_q.receipt_sha256
            else:
                expected_source = archive.receipt_sha256
            if score.source_receipt_sha256 != expected_source:
                raise SWM0WS2SProtocolError("task evaluation score source crosses artifact")
        expected_states = {
            ScoreVariant.T16_BASE: base_states[S2SArm.T16],
            ScoreVariant.P_CAP18_BASE: base_states[S2SArm.P_CAP18],
            ScoreVariant.DS870_BASE: base_states[S2SArm.DS870],
            ScoreVariant.T16_Q_REMOVED: self.learned_q.removal.ablated_state_sha256,
            ScoreVariant.T16_RESTORED: self.learned_q.restored_core_state_sha256,
            ScoreVariant.T16_BROADCAST: base_states[S2SArm.T16],
            ScoreVariant.T16_CYCLE_120: self.learned_q.restored_core_state_sha256,
            ScoreVariant.T16_CYCLE_201: self.learned_q.restored_core_state_sha256,
        }
        if any(
            score.evaluated_state_sha256 != expected_states[score.variant]
            for score in self.scores
        ):
            raise SWM0WS2SProtocolError("task evaluation score state binding drifted")
        base = score_map[ScoreVariant.T16_BASE]
        pcap = score_map[ScoreVariant.P_CAP18_BASE]
        q_removed = score_map[ScoreVariant.T16_Q_REMOVED]
        broadcast = score_map[ScoreVariant.T16_BROADCAST]
        restored = score_map[ScoreVariant.T16_RESTORED]
        if broadcast.source_prediction_tensor_sha256 != base.prediction_tensor_sha256:
            raise SWM0WS2SProtocolError("broadcast did not consume stored T16 baseline")
        if (
            restored.prediction_tensor_sha256 != base.prediction_tensor_sha256
            or restored.strata != base.strata
        ):
            raise SWM0WS2SProtocolError("restored score differs from T16 baseline")
        if (
            self.integrity.pcap_max_r2.hex()
            != max(row.r2 for row in pcap.strata).hex()
            or self.integrity.q_removed_max_r2.hex()
            != max(row.r2 for row in q_removed.strata).hex()
            or self.integrity.restore_parameter_bytes_equal
            is not self.learned_q.exact_restored_parameter_bytes
            or not self.integrity.restore_prediction_bytes_equal
        ):
            raise SWM0WS2SProtocolError("task integrity does not derive from bound scores")
        if len({score.test_dataset_sha256 for score in self.scores}) != 1 or len(
            {score.target_tensor_sha256 for score in self.scores}
        ) != 1:
            raise SWM0WS2SProtocolError("task evaluation scores cross test data")
        expected_metric_links = (
            tuple(item.receipt_sha256 for item in self.archives),
            tuple(item.receipt_sha256 for item in self.replays),
            tuple(item.receipt_sha256 for item in self.scores),
        )
        if (
            self.metrics.draw_index != task.draw_index
            or self.metrics.task_manifest_sha256 != task.manifest_sha256
            or self.metrics.structural_task_sha256 != task.structural_task_sha256
            or self.metrics.protocol_config_sha256 != self.config.receipt_sha256
            or self.metrics.model_archive_sha256s != expected_metric_links[0]
            or self.metrics.fit_replay_sha256s != expected_metric_links[1]
            or self.metrics.score_receipt_sha256s != expected_metric_links[2]
            or self.metrics.learned_q_receipt_sha256 != self.learned_q.receipt_sha256
            or self.metrics.integrity_receipt_sha256 != self.integrity.receipt_sha256
            or self.metrics.integrity_valid is not self.integrity.valid
            or tuple(value.hex() for value in _metric_values(self.scores))
            != tuple(
                value.hex()
                for value in (self.metrics.q, self.metrics.b, self.metrics.r, self.metrics.c)
            )
        ):
            raise SWM0WS2SProtocolError("task metric receipt does not derive from scores")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SProtocolError("task evaluation receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "archives": [item.canonical() for item in self.archives],
            "fit_replays": [item.canonical() for item in self.replays],
            "integrity": self.integrity.canonical(),
            "learned_q_intervention": self.learned_q.canonical(),
            "metrics": self.metrics.canonical(),
            "protocol_config": self.config.canonical(),
            "schema_version": TASK_EVALUATION_VERSION,
            "scores": [item.canonical() for item in self.scores],
            "scientific_status": SCIENTIFIC_STATUS,
            "task_spec": self.task.canonical(),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def _make_task_evaluation(
    task: TaskSpecV2,
    config: S2SProtocolConfig,
    archives: tuple[LearnedModelArchive, ...],
    replays: tuple[FitReplayReceipt, ...],
    learned_q: LearnedQInterventionReceipt,
    scores: tuple[SixStratumScore, ...],
    integrity: IntegrityReceipt,
) -> TaskEvaluationReceipt:
    metrics = build_task_metric_receipt(
        task, config, archives, replays, scores, learned_q, integrity
    )
    values = {
        "task": task,
        "config": config,
        "archives": archives,
        "replays": replays,
        "learned_q": learned_q,
        "scores": scores,
        "integrity": integrity,
        "metrics": metrics,
    }
    unsigned = {
        "archives": [item.canonical() for item in archives],
        "fit_replays": [item.canonical() for item in replays],
        "integrity": integrity.canonical(),
        "learned_q_intervention": learned_q.canonical(),
        "metrics": metrics.canonical(),
        "protocol_config": config.canonical(),
        "schema_version": TASK_EVALUATION_VERSION,
        "scores": [item.canonical() for item in scores],
        "scientific_status": SCIENTIFIC_STATUS,
        "task_spec": task.canonical(),
    }
    return TaskEvaluationReceipt(**values, receipt_sha256=canonical_sha256(unsigned))


def _recompute_task_evaluation_components(
    task: TaskSpecV2,
    models: tuple[LearnedS2SOperator, ...],
    config: S2SProtocolConfig,
) -> tuple[
    tuple[LearnedModelArchive, ...],
    LearnedQInterventionReceipt,
    tuple[SixStratumScore, ...],
    IntegrityReceipt,
]:
    """Reconstruct every deterministic, model-derived evaluation component."""

    if (
        type(task) is not TaskSpecV2
        or type(models) is not tuple
        or len(models) != len(ALL_ARMS)
        or any(type(model) is not LearnedS2SOperator for model in models)
        or tuple(model.arm for model in models) != ALL_ARMS
        or type(config) is not S2SProtocolConfig
        or any(
            model.optimization.task != task
            or model.config != config.config_for(arm)
            for arm, model in zip(ALL_ARMS, models, strict=True)
        )
    ):
        raise SWM0WS2SProtocolError(
            "evaluation reconstruction requires exact task/model/config bindings"
        )

    _, x, _, _, _ = _complete_test_data(task)
    t_model, p_model, d_model = models
    archives = tuple(archive_learned_model(model) for model in models)
    t_base = t_model.forward(x)
    p_base = p_model.forward(x)
    d_base = d_model.forward(x)
    t_core = t_model.as_unlabeled_operator()
    p_core = p_model.as_unlabeled_operator()
    d_core = d_model.as_unlabeled_operator()

    ablated, learned_q = remove_learned_q(t_model)
    q_removed_predictions = ablated.forward(x)
    restored_learned = restore_learned_q(t_model, ablated, learned_q)
    restored = restored_learned.as_unlabeled_operator()
    restored_predictions = restored_learned.forward(x)
    parameter_bytes_equal = (
        restored_learned.state_sha256 == t_model.state_sha256
        and tuple(restored.parameters) == tuple(t_model.parameters)
        and all(
            restored.parameters[name].tobytes(order="C")
            == t_model.parameters[name].tobytes(order="C")
            for name in restored.parameters
        )
    )
    if not parameter_bytes_equal:
        raise SWM0WS2SProtocolError("Q restoration changed learned parameter bytes")
    broadcast_predictions = within_role_broadcast(t_base)
    cycle_rows = evaluate_both_role_cycles(restored, x)
    if tuple(row[0] for row in cycle_rows) != ROLE_CYCLES:
        raise SWM0WS2SProtocolError("registered role-cycle order drifted")

    base_prediction_sha = _bound_tensor_sha256(t_base)
    variants = (
        (
            t_model,
            t_core.state_sha256,
            archives[0].receipt_sha256,
            None,
            ScoreVariant.T16_BASE,
            t_base,
        ),
        (
            p_model,
            p_core.state_sha256,
            archives[1].receipt_sha256,
            None,
            ScoreVariant.P_CAP18_BASE,
            p_base,
        ),
        (
            d_model,
            d_core.state_sha256,
            archives[2].receipt_sha256,
            None,
            ScoreVariant.DS870_BASE,
            d_base,
        ),
        (
            t_model,
            ablated.state_sha256,
            learned_q.receipt_sha256,
            None,
            ScoreVariant.T16_Q_REMOVED,
            q_removed_predictions,
        ),
        (
            t_model,
            restored.state_sha256,
            learned_q.receipt_sha256,
            None,
            ScoreVariant.T16_RESTORED,
            restored_predictions,
        ),
        (
            t_model,
            t_core.state_sha256,
            archives[0].receipt_sha256,
            base_prediction_sha,
            ScoreVariant.T16_BROADCAST,
            broadcast_predictions,
        ),
        (
            t_model,
            restored.state_sha256,
            learned_q.receipt_sha256,
            None,
            ScoreVariant.T16_CYCLE_120,
            cycle_rows[0][1],
        ),
        (
            t_model,
            restored.state_sha256,
            learned_q.receipt_sha256,
            None,
            ScoreVariant.T16_CYCLE_201,
            cycle_rows[1][1],
        ),
    )
    scores = tuple(
        score_complete_test_predictions(
            task,
            model,
            evaluated_state_sha256=state_sha,
            source_receipt_sha256=source_sha,
            source_prediction_tensor_sha256=source_prediction_sha,
            variant=variant,
            predictions=predictions,
        )
        for (
            model,
            state_sha,
            source_sha,
            source_prediction_sha,
            variant,
            predictions,
        ) in variants
    )
    by_variant = {score.variant: score for score in scores}
    integrity = build_integrity_receipt(
        task,
        models,
        config,
        pcap_score=by_variant[ScoreVariant.P_CAP18_BASE],
        q_removed_score=by_variant[ScoreVariant.T16_Q_REMOVED],
        base_score=by_variant[ScoreVariant.T16_BASE],
        restored_score=by_variant[ScoreVariant.T16_RESTORED],
        restore_parameter_bytes_equal=parameter_bytes_equal,
    )
    return archives, learned_q, scores, integrity


def _verify_task_evaluation_semantics(receipt: TaskEvaluationReceipt) -> None:
    """Authenticate claimed measurements by replaying the finite evaluation."""

    models = tuple(archive.model() for archive in receipt.archives)
    expected_archives, expected_q, expected_scores, expected_integrity = (
        _recompute_task_evaluation_components(receipt.task, models, receipt.config)
    )
    comparisons = (
        (
            [item.canonical() for item in receipt.archives],
            [item.canonical() for item in expected_archives],
            "model archives",
        ),
        (receipt.learned_q.canonical(), expected_q.canonical(), "learned Q replay"),
        (
            [item.canonical() for item in receipt.scores],
            [item.canonical() for item in expected_scores],
            "complete test scores",
        ),
        (
            receipt.integrity.canonical(),
            expected_integrity.canonical(),
            "integrity audit",
        ),
    )
    for actual, expected, name in comparisons:
        if canonical_json(actual) != canonical_json(expected):
            raise SWM0WS2SProtocolError(
                f"task evaluation {name} failed deterministic reconstruction"
            )


def parse_task_evaluation_receipt(value: Mapping[str, Any]) -> TaskEvaluationReceipt:
    data = _object(
        value,
        (
            "archives",
            "fit_replays",
            "integrity",
            "learned_q_intervention",
            "metrics",
            "protocol_config",
            "receipt_sha256",
            "schema_version",
            "scores",
            "scientific_status",
            "task_spec",
        ),
        "task evaluation receipt",
    )
    if (
        _string(data["schema_version"], "task evaluation schema")
        != TASK_EVALUATION_VERSION
        or _string(data["scientific_status"], "task evaluation status")
        != SCIENTIFIC_STATUS
    ):
        raise SWM0WS2SProtocolError("task evaluation fixed contract drifted")
    result = TaskEvaluationReceipt(
        task=parse_task_spec_v2(data["task_spec"]),
        config=parse_protocol_config(data["protocol_config"]),
        archives=tuple(
            parse_learned_model_archive(item)
            for item in _list(data["archives"], "archives", length=3)
        ),
        replays=tuple(
            parse_fit_replay_receipt(item)
            for item in _list(data["fit_replays"], "fit replays", length=3)
        ),
        learned_q=parse_learned_q_intervention(data["learned_q_intervention"]),
        scores=tuple(
            parse_six_stratum_score(item)
            for item in _list(data["scores"], "scores", length=8)
        ),
        integrity=parse_integrity_receipt(data["integrity"]),
        metrics=parse_task_metric_receipt(data["metrics"]),
        receipt_sha256=_sha256(
            data["receipt_sha256"], "task evaluation receipt SHA"
        ),
    )
    _same_canonical(data, result.canonical(), "task evaluation receipt")
    _verify_task_evaluation_semantics(result)
    return result


def evaluate_task(
    task: TaskSpecV2,
    models: tuple[LearnedS2SOperator, ...],
    replays: tuple[FitReplayReceipt, ...],
    config: S2SProtocolConfig,
) -> TaskEvaluationReceipt:
    """Evaluate one already-fitted task without training or seed acquisition."""

    if (
        type(task) is not TaskSpecV2
        or type(models) is not tuple
        or len(models) != len(ALL_ARMS)
        or any(type(model) is not LearnedS2SOperator for model in models)
        or tuple(model.arm for model in models) != ALL_ARMS
        or type(replays) is not tuple
        or len(replays) != len(ALL_ARMS)
        or any(type(replay) is not FitReplayReceipt for replay in replays)
        or tuple(replay.arm for replay in replays) != ALL_ARMS
        or type(config) is not S2SProtocolConfig
    ):
        raise SWM0WS2SProtocolError("task evaluation requires exact fixed rosters")
    for arm, model, replay in zip(ALL_ARMS, models, replays, strict=True):
        if (
            model.optimization.task != task
            or model.config != config.config_for(arm)
            or replay.task_manifest_sha256 != task.manifest_sha256
            or replay.original_learned_state_sha256 != model.state_sha256
            or replay.original_optimization_receipt_sha256
            != model.optimization.receipt_sha256
            or replay.original_history_sha256 != model.optimization.history_sha256
            or replay.original_parameters_sha256 != model.parameters_sha256
        ):
            raise SWM0WS2SProtocolError("fit/replay marker crosses task/model/config")

    archives, learned_q, scores, integrity = _recompute_task_evaluation_components(
        task, models, config
    )
    return _make_task_evaluation(
        task, config, archives, replays, learned_q, scores, integrity
    )


@dataclass(frozen=True, slots=True)
class MetricEstimate:
    point: float
    lower: float
    upper: float

    def __post_init__(self) -> None:
        for name in ("point", "lower", "upper"):
            _finite(getattr(self, name), f"metric estimate {name}")
        if self.lower > self.upper:
            raise SWM0WS2SProtocolError("metric estimate interval is reversed")

    def canonical(self) -> dict[str, str]:
        return {
            "lower_hex": self.lower.hex(),
            "point_hex": self.point.hex(),
            "upper_hex": self.upper.hex(),
        }


def shared_task_bootstrap_indices() -> np.ndarray:
    """One frozen positional task bootstrap shared by Q, B, R, and C."""

    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    result = rng.integers(
        0, TASK_COUNT, size=(BOOTSTRAP_RESAMPLES, TASK_COUNT), dtype=np.int64
    )
    result.setflags(write=False)
    return result


def _bootstrap_sha256(indices: np.ndarray) -> str:
    array = np.ascontiguousarray(indices, dtype="<i8")
    header = canonical_json(
        {"dtype": "int64-little-endian", "shape": list(array.shape)}
    )
    return hashlib.sha256(header.encode("ascii") + b"\x00" + array.tobytes()).hexdigest()


def _summarize_task_metrics(
    metrics: tuple[TaskMetricReceipt, ...],
) -> tuple[tuple[str, MetricEstimate], ...]:
    if (
        type(metrics) is not tuple
        or len(metrics) != TASK_COUNT
        or any(type(item) is not TaskMetricReceipt for item in metrics)
    ):
        raise SWM0WS2SProtocolError("bootstrap requires exactly twenty task metrics")
    indices = shared_task_bootstrap_indices()
    rows: list[tuple[str, MetricEstimate]] = []
    for name, attribute in (("Q", "q"), ("B", "b"), ("R", "r"), ("C", "c")):
        values = np.asarray(
            [getattr(item, attribute) for item in metrics],
            dtype=np.float64,
        )
        if not np.isfinite(values).all():
            raise SWM0WS2SProtocolError("task metric array is non-finite")
        sampled = values[indices]
        replicates = np.fromiter(
            (
                math.fsum(float(value) for value in row) / TASK_COUNT
                for row in sampled
            ),
            dtype=np.float64,
            count=BOOTSTRAP_RESAMPLES,
        )
        lower, upper = np.quantile(
            replicates, BOOTSTRAP_QUANTILES, method="linear"
        )
        rows.append(
            (
                name,
                MetricEstimate(
                    point=_clean_float(
                        math.fsum(float(value) for value in values) / TASK_COUNT
                    ),
                    lower=_clean_float(float(lower)),
                    upper=_clean_float(float(upper)),
                ),
            )
        )
    return tuple(rows)


def _candidate_reduction(
    batch: TaskBatchV2,
    metrics: tuple[TaskMetricReceipt, ...],
    config: S2SProtocolConfig,
    integrity_errors: tuple[str, ...],
) -> tuple[
    CandidateOutcome,
    tuple[str, ...],
    tuple[tuple[str, MetricEstimate], ...],
    str | None,
    bool,
]:
    errors = list(integrity_errors)
    if batch.requested_count != TASK_COUNT:
        errors.append("TASK_BATCH_COUNT_DRIFT")
    excluded = {
        (seed_sha, draw_index)
        for seed_sha, draw_indices in config.excluded_task_provenance
        for draw_index in draw_indices
    }
    if any(
        (task.seed_commitment_sha256, task.draw_index) in excluded
        for task in batch.tasks
    ):
        errors.append("EXCLUDED_TASK_PROVENANCE_REUSED")
    if len(metrics) != TASK_COUNT:
        errors.append("TASK_METRIC_COUNT_DRIFT")
    if len(metrics) == TASK_COUNT and batch.requested_count == TASK_COUNT:
        for index, (task, metric) in enumerate(
            zip(batch.tasks, metrics, strict=True)
        ):
            if (
                metric.task_manifest_sha256 != task.manifest_sha256
                or metric.structural_task_sha256 != task.structural_task_sha256
                or metric.draw_index != index
            ):
                errors.append(f"TASK_{index:02d}_ORDER_OR_MANIFEST_DRIFT")
            if metric.protocol_config_sha256 != config.receipt_sha256:
                errors.append(f"TASK_{index:02d}_PROTOCOL_CONFIG_DRIFT")
            if not metric.integrity_valid:
                errors.append(f"TASK_{index:02d}_INTEGRITY_INVALID")
    if errors:
        return CandidateOutcome.VOID, tuple(dict.fromkeys(errors)), tuple(), None, False

    estimates = _summarize_task_metrics(metrics)
    by_name = dict(estimates)
    thresholds = {
        "Q": config.thresholds.q,
        "B": config.thresholds.b,
        "R": config.thresholds.r,
    }
    if all(by_name[name].lower >= threshold for name, threshold in thresholds.items()):
        phrase = by_name["C"].lower >= config.thresholds.c_phrase
        return (
            CandidateOutcome.CANDIDATE_PASS_AWAITING_BUNDLE,
            ("CANDIDATE_Q_B_R_LCBS_MEET_GATES",),
            estimates,
            _bootstrap_sha256(shared_task_bootstrap_indices()),
            phrase,
        )
    kills = tuple(
        f"{name}_UCB_BELOW_GATE"
        for name, threshold in thresholds.items()
        if by_name[name].upper < threshold
    )
    if kills:
        outcome = CandidateOutcome.CANDIDATE_KILL_AWAITING_BUNDLE
        reasons = kills
    else:
        outcome = CandidateOutcome.CANDIDATE_INCONCLUSIVE_AWAITING_BUNDLE
        reasons = ("CANDIDATE_ESSENTIAL_INTERVAL_CROSSES_GATE",)
    return (
        outcome,
        reasons,
        estimates,
        _bootstrap_sha256(shared_task_bootstrap_indices()),
        False,
    )


@dataclass(frozen=True, slots=True)
class FinalCandidateReceipt:
    task_batch: TaskBatchV2
    config: S2SProtocolConfig
    task_metrics: tuple[TaskMetricReceipt, ...]
    integrity_errors: tuple[str, ...]
    outcome: CandidateOutcome
    reason_codes: tuple[str, ...]
    estimates: tuple[tuple[str, MetricEstimate], ...]
    bootstrap_indices_sha256: str | None
    compact_competitive_phrase_candidate: bool
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.task_batch) is not TaskBatchV2 or type(self.config) is not S2SProtocolConfig:
            raise SWM0WS2SProtocolError("final candidate requires exact batch/config")
        if type(self.task_metrics) is not tuple or any(
            type(item) is not TaskMetricReceipt for item in self.task_metrics
        ):
            raise SWM0WS2SProtocolError("final candidate metrics require exact tuple")
        if type(self.integrity_errors) is not tuple or any(
            type(item) is not str or not item for item in self.integrity_errors
        ):
            raise SWM0WS2SProtocolError("final candidate integrity errors are malformed")
        if type(self.outcome) is not CandidateOutcome:
            raise SWM0WS2SProtocolError("final candidate outcome requires exact enum")
        if type(self.reason_codes) is not tuple or not self.reason_codes or any(
            type(item) is not str or not item for item in self.reason_codes
        ):
            raise SWM0WS2SProtocolError("final candidate reason codes are malformed")
        if type(self.estimates) is not tuple or any(
            type(row) is not tuple
            or len(row) != 2
            or type(row[0]) is not str
            or type(row[1]) is not MetricEstimate
            for row in self.estimates
        ):
            raise SWM0WS2SProtocolError("final metric estimates are malformed")
        if self.estimates and tuple(name for name, _ in self.estimates) != (
            "Q",
            "B",
            "R",
            "C",
        ):
            raise SWM0WS2SProtocolError("final metric order drifted")
        if self.bootstrap_indices_sha256 is not None:
            _sha256(self.bootstrap_indices_sha256, "bootstrap indices SHA")
        if type(self.compact_competitive_phrase_candidate) is not bool:
            raise SWM0WS2SProtocolError("final optional phrase flag must be exact bool")
        expected = _candidate_reduction(
            self.task_batch, self.task_metrics, self.config, self.integrity_errors
        )
        if (
            self.outcome is not expected[0]
            or self.reason_codes != expected[1]
            or self.estimates != expected[2]
            or self.bootstrap_indices_sha256 != expected[3]
            or self.compact_competitive_phrase_candidate is not expected[4]
        ):
            raise SWM0WS2SProtocolError("final candidate result does not recompute")
        if self.outcome is CandidateOutcome.VOID and (
            self.estimates or self.bootstrap_indices_sha256 is not None
        ):
            raise SWM0WS2SProtocolError("VOID may not summarize partial task rows")
        if (
            self.compact_competitive_phrase_candidate
            and self.outcome is not CandidateOutcome.CANDIDATE_PASS_AWAITING_BUNDLE
        ):
            raise SWM0WS2SProtocolError("optional phrase requires candidate PASS")
        _sha256(self.receipt_sha256, "final candidate receipt SHA")
        if self.receipt_sha256 != canonical_sha256(self.unsigned()):
            raise SWM0WS2SProtocolError("final candidate receipt hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "bootstrap": {
                "generator": "numpy.random.PCG64",
                "indices_sha256": self.bootstrap_indices_sha256,
                "quantile_method": "linear",
                "quantiles": [value.hex() for value in BOOTSTRAP_QUANTILES],
                "resamples": BOOTSTRAP_RESAMPLES,
                "seed": BOOTSTRAP_SEED,
                "shared_across_metrics": True,
                "unit": "INDEXED_TASK_DRAW_CONDITIONAL_ON_FIXED_FRAME_GENERATOR",
            },
            "claim_boundary": "CANDIDATE_ONLY_EXTERNAL_ADJUDICATION_REQUIRED",
            "compact_competitive_phrase_candidate": (
                self.compact_competitive_phrase_candidate
            ),
            "integrity_errors": list(self.integrity_errors),
            "metric_estimates": {
                name: estimate.canonical() for name, estimate in self.estimates
            },
            "outcome": self.outcome.value,
            "protocol_config": self.config.canonical(),
            "protocol_version": PROTOCOL_VERSION,
            "reason_codes": list(self.reason_codes),
            "schema_version": FINAL_RECEIPT_VERSION,
            "scientific_status": SCIENTIFIC_STATUS,
            "task_batch": serialize_task_batch(self.task_batch),
            "task_metrics": [item.canonical() for item in self.task_metrics],
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


def finalize_candidate(
    task_batch: TaskBatchV2,
    task_metrics: tuple[TaskMetricReceipt, ...],
    config: S2SProtocolConfig,
    *,
    integrity_errors: tuple[str, ...] = (),
) -> FinalCandidateReceipt:
    if (
        type(task_batch) is not TaskBatchV2
        or type(task_metrics) is not tuple
        or any(type(item) is not TaskMetricReceipt for item in task_metrics)
        or type(config) is not S2SProtocolConfig
        or type(integrity_errors) is not tuple
        or any(type(item) is not str or not item for item in integrity_errors)
    ):
        raise SWM0WS2SProtocolError("candidate finalization inputs require exact types")
    outcome, reasons, estimates, bootstrap_sha, phrase = _candidate_reduction(
        task_batch, task_metrics, config, integrity_errors
    )
    values = {
        "task_batch": task_batch,
        "config": config,
        "task_metrics": task_metrics,
        "integrity_errors": integrity_errors,
        "outcome": outcome,
        "reason_codes": reasons,
        "estimates": estimates,
        "bootstrap_indices_sha256": bootstrap_sha,
        "compact_competitive_phrase_candidate": phrase,
    }
    unsigned = {
        "bootstrap": {
            "generator": "numpy.random.PCG64",
            "indices_sha256": bootstrap_sha,
            "quantile_method": "linear",
            "quantiles": [value.hex() for value in BOOTSTRAP_QUANTILES],
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "shared_across_metrics": True,
            "unit": "INDEXED_TASK_DRAW_CONDITIONAL_ON_FIXED_FRAME_GENERATOR",
        },
        "claim_boundary": "CANDIDATE_ONLY_EXTERNAL_ADJUDICATION_REQUIRED",
        "compact_competitive_phrase_candidate": phrase,
        "integrity_errors": list(integrity_errors),
        "metric_estimates": {name: row.canonical() for name, row in estimates},
        "outcome": outcome.value,
        "protocol_config": config.canonical(),
        "protocol_version": PROTOCOL_VERSION,
        "reason_codes": list(reasons),
        "schema_version": FINAL_RECEIPT_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "task_batch": serialize_task_batch(task_batch),
        "task_metrics": [item.canonical() for item in task_metrics],
    }
    return FinalCandidateReceipt(
        **values, receipt_sha256=canonical_sha256(unsigned)
    )


def _parse_metric_estimate(value: Mapping[str, Any], name: str) -> MetricEstimate:
    data = _object(
        value, ("lower_hex", "point_hex", "upper_hex"), f"{name} estimate"
    )
    result = MetricEstimate(
        point=_float_hex(data["point_hex"], f"{name} point"),
        lower=_float_hex(data["lower_hex"], f"{name} lower"),
        upper=_float_hex(data["upper_hex"], f"{name} upper"),
    )
    _same_canonical(data, result.canonical(), f"{name} estimate")
    return result


def parse_final_candidate_receipt(value: Mapping[str, Any]) -> FinalCandidateReceipt:
    data = _object(
        value,
        (
            "bootstrap",
            "claim_boundary",
            "compact_competitive_phrase_candidate",
            "integrity_errors",
            "metric_estimates",
            "outcome",
            "protocol_config",
            "protocol_version",
            "reason_codes",
            "receipt_sha256",
            "schema_version",
            "scientific_status",
            "task_batch",
            "task_metrics",
        ),
        "final candidate receipt",
    )
    if (
        _string(data["schema_version"], "final schema") != FINAL_RECEIPT_VERSION
        or _string(data["protocol_version"], "protocol version") != PROTOCOL_VERSION
        or _string(data["scientific_status"], "final status") != SCIENTIFIC_STATUS
        or _string(data["claim_boundary"], "claim boundary")
        != "CANDIDATE_ONLY_EXTERNAL_ADJUDICATION_REQUIRED"
    ):
        raise SWM0WS2SProtocolError("final candidate fixed contract drifted")
    bootstrap = _object(
        data["bootstrap"],
        (
            "generator",
            "indices_sha256",
            "quantile_method",
            "quantiles",
            "resamples",
            "seed",
            "shared_across_metrics",
            "unit",
        ),
        "final bootstrap",
    )
    expected_bootstrap = {
        "generator": "numpy.random.PCG64",
        "indices_sha256": bootstrap["indices_sha256"],
        "quantile_method": "linear",
        "quantiles": [value.hex() for value in BOOTSTRAP_QUANTILES],
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
        "shared_across_metrics": True,
        "unit": "INDEXED_TASK_DRAW_CONDITIONAL_ON_FIXED_FRAME_GENERATOR",
    }
    if bootstrap != expected_bootstrap:
        raise SWM0WS2SProtocolError("final bootstrap fixed contract drifted")
    bootstrap_sha = (
        None
        if bootstrap["indices_sha256"] is None
        else _sha256(bootstrap["indices_sha256"], "bootstrap indices SHA")
    )
    raw_estimates = _object(
        data["metric_estimates"],
        () if not data["metric_estimates"] else ("B", "C", "Q", "R"),
        "metric estimates",
    )
    estimates = tuple(
        (name, _parse_metric_estimate(raw_estimates[name], name))
        for name in ("Q", "B", "R", "C")
        if name in raw_estimates
    )
    result = FinalCandidateReceipt(
        task_batch=parse_task_batch(data["task_batch"]),
        config=parse_protocol_config(data["protocol_config"]),
        task_metrics=tuple(
            parse_task_metric_receipt(item)
            for item in _list(data["task_metrics"], "task metrics")
        ),
        integrity_errors=tuple(
            _string(item, "final integrity error")
            for item in _list(data["integrity_errors"], "final integrity errors")
        ),
        outcome=_enum(CandidateOutcome, data["outcome"], "candidate outcome"),
        reason_codes=tuple(
            _string(item, "candidate reason")
            for item in _list(data["reason_codes"], "candidate reasons")
        ),
        estimates=estimates,
        bootstrap_indices_sha256=bootstrap_sha,
        compact_competitive_phrase_candidate=_boolean(
            data["compact_competitive_phrase_candidate"], "optional phrase flag"
        ),
        receipt_sha256=_sha256(data["receipt_sha256"], "final receipt SHA"),
    )
    _same_canonical(data, result.canonical(), "final candidate receipt")
    return result


__all__ = [
    "BOOTSTRAP_QUANTILES",
    "BOOTSTRAP_RESAMPLES",
    "BOOTSTRAP_SEED",
    "CandidateOutcome",
    "FinalCandidateReceipt",
    "FitReplayReceipt",
    "IntegrityReceipt",
    "LearnedModelArchive",
    "LearnedQInterventionReceipt",
    "MetricEstimate",
    "PAIR_NULL_EPSILON",
    "PROTOCOL_VERSION",
    "S2SProtocolConfig",
    "SCIENTIFIC_STATUS",
    "SWM0WS2SProtocolError",
    "ScoreVariant",
    "SixStratumScore",
    "StratumScore",
    "TASK_COUNT",
    "TEST_WORLD_COUNT",
    "TaskEvaluationReceipt",
    "TaskMetricReceipt",
    "Thresholds",
    "archive_learned_model",
    "build_fit_replay_receipt",
    "build_integrity_receipt",
    "build_protocol_config",
    "build_task_metric_receipt",
    "evaluate_task",
    "finalize_candidate",
    "loads_canonical_json",
    "parse_final_candidate_receipt",
    "parse_fit_replay_receipt",
    "parse_integrity_receipt",
    "parse_learned_model_archive",
    "parse_learned_q_intervention",
    "parse_optimization_receipt",
    "parse_protocol_config",
    "parse_six_stratum_score",
    "parse_task_batch",
    "parse_task_evaluation_receipt",
    "parse_task_metric_receipt",
    "parse_task_spec_v2",
    "parse_training_config",
    "remove_learned_q",
    "restore_learned_q",
    "score_complete_test_predictions",
    "serialize_task_batch",
    "shared_task_bootstrap_indices",
]
