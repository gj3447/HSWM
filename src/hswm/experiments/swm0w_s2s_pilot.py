"""Public train/dev-only development runner for the SWM-0W-S2S optimizer.

The runner has one fixed roster and no efficacy verdict.  It first executes a
27-cell, ten-update fit-and-replay throughput stage.  A predeclared linear
projection admits the fresh 300-update stage only when its projected
fit-and-replay time is at most 120 minutes.  The second stage reruns every cell
from scratch; no stage-one loss enters selection.
Stage-one cells expose only fixed roster/config/task identity, opaque state and
parameter hashes, and the runner's replay observation; loss, history, and
optimization diagnostics are deliberately absent from throughput artifacts.

Every task is materialized through only ``train`` and ``dev``.  The selected
learning rate for each arm minimizes the exact dyadic tuple
``(mean(L*/L0), max(L*/L0), numeric learning rate)`` across draws 0..2.  The
same positive epoch-zero dev loss must be observed across all arms and rates
within a draw.  A complete deterministic replay is required for every cell.

The canonical execution-bound deterministic receipt is separate from runtime
telemetry.  It binds the numeric environment and therefore does not claim
cross-host byte identity.
Operational failure, replay mismatch, incomplete coverage, baseline drift, or
runtime non-admission produces ``DEVELOPMENT_RUNTIME_VOID`` and no selection.
Offline receipt validation proves strict self-consistency, not authenticated
execution provenance; the public runner separately performs the replay before
it writes a replay-valid cell.
This is development instrumentation only; it cannot establish an efficacy
result or a convergence claim.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import sys
import tempfile
import time
from typing import Any


SCIENTIFIC_STATUS = "DEVELOPMENT_ONLY_UNJUDGED"
TERMINAL_COMPLETE = "DEVELOPMENT_COMPLETE"
TERMINAL_VOID = "DEVELOPMENT_RUNTIME_VOID"
NO_SELECTION = "NO_SELECTION"
NO_EFFICACY_VERDICT = "NO_EFFICACY_VERDICT"

PILOT_VERSION = "hswm-swm0w-s2s-train-dev-pilot/v1"
CONTRACT_VERSION = "hswm-swm0w-s2s-train-dev-pilot-contract/v1"
DETERMINISTIC_RECEIPT_VERSION = (
    "hswm-swm0w-s2s-train-dev-pilot-deterministic-receipt/v1"
)
RUNTIME_TELEMETRY_VERSION = (
    "hswm-swm0w-s2s-train-dev-pilot-runtime-telemetry/v1"
)
CELL_RECEIPT_VERSION = "hswm-swm0w-s2s-train-dev-pilot-cell/v1"
THROUGHPUT_CELL_RECEIPT_VERSION = "hswm-swm0w-s2s-throughput-cell/v1"
SELECTION_VERSION = "hswm-swm0w-s2s-train-dev-pilot-selection/v1"

EXTERNAL_SEED_ASCII = "HSWM-SWM0W-S2S-TRAIN-DEV-PILOT-v1"
EXTERNAL_SEED = hashlib.sha256(EXTERNAL_SEED_ASCII.encode("ascii")).digest()
EXTERNAL_SEED_SHA256_HEX = EXTERNAL_SEED.hex()
TASK_DRAW_INDICES = (0, 1, 2)
EXPECTED_TASK_BATCH_SHA256 = (
    "301b6c6fedd5094487036e0aafe3fbadd239a8593cbb9549132422a148904595"
)
EXPECTED_SEED_COMMITMENT_SHA256 = (
    "0370316c9f9388a5f37ba26c934a5efaed08b828789f392bf702da600cc88dce"
)
EXPECTED_TASK_MANIFEST_SHA256S = (
    "0f926fcc84432a2b47c11405238a325a474539f9cbc69ff160246fa1be1cebe0",
    "eb229a225b8b3410a9ae98b3c960a70aedbacc50406a51b49fa1e11400d3d6bc",
    "2909e23547e2c870d1361156a9130ede96d94b2fa441420619ee049a4093980b",
)
EXPECTED_STRUCTURAL_TARGET_SHA256S = (
    "ef65adf0665e88e7d1dcbef6ad327dca6e25813531a1b622c529730f59073302",
    "6f67d87dc8ad61e6475ff0fcfea377958a809089df5485f0ffe370719bac3c8d",
    "e19a2983cdf7356300cdbefe100cf8bfc5e2d3bdb30ad28cfee087ff7e3ad2cf",
)
EXPECTED_STRUCTURAL_TASK_SHA256S = (
    "4c872262933e3d3dd0a806274ca981a0c5a083535d695d2abee1e9e7c0f41f84",
    "a37f086fed3f8972a15fe2e8a0a8e8ae4caefc5beca3e89c489a4067390f83c0",
    "3a5c0f6af85ef2ffa6859a366782634da06f18061f79660b56adbf7cd40304fc",
)
PUBLIC_ARMS = ("T16", "P_CAP18", "DEEPSETS_870")
PUBLIC_TO_OPERATOR_ARM = {
    "T16": "T16",
    "P_CAP18": "P_CAP18",
    "DEEPSETS_870": "DS870",
}
LEARNING_RATE_LABELS = ("0.001", "0.003", "0.01")
LEARNING_RATE_HEX = {
    label: float(label).hex() for label in LEARNING_RATE_LABELS
}
INITIALIZER_SEED = 0
PATIENCE = 50
MIN_DELTA = 1.0e-9
GRADIENT_CLIP = 5.0
BETA1 = 0.9
BETA2 = 0.999
EPSILON = 1.0e-8
STAGE1_MAX_UPDATES = 10
STAGE2_MAX_UPDATES = 300
STAGE1_NAME = "THROUGHPUT_FIT_AND_REPLAY"
STAGE2_NAME = "FULL_DEVELOPMENT_FIT_AND_REPLAY"
ADMISSION_LIMIT_MINUTES = 120
ADMISSION_LIMIT_NS = ADMISSION_LIMIT_MINUTES * 60 * 1_000_000_000
WORKFLOW_TIMEOUT_MINUTES = 180
WORKFLOW_RUNNER_IMAGE = "ubuntu-24.04"
WORKFLOW_PYTHON_VERSION = "3.11.15"
WORKFLOW_UV_VERSION = "0.12.3"
WORKFLOW_FIXED_ENVIRONMENT = {
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_CORETYPE": "Haswell",
    "OPENBLAS_NUM_THREADS": "1",
    "PYTHONHASHSEED": "0",
}
PROJECTION_MULTIPLIER = STAGE2_MAX_UPDATES // STAGE1_MAX_UPDATES
EXPECTED_CELL_COUNT = (
    len(TASK_DRAW_INDICES) * len(PUBLIC_ARMS) * len(LEARNING_RATE_LABELS)
)


class SWM0WS2SPilotError(RuntimeError):
    """Raised when the fixed development runner must fail closed."""


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise SWM0WS2SPilotError(
                "canonical pilot JSON requires exact string mapping keys"
            )
        return {
            key: _jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: pair[0])
        }
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if value is None or type(value) in (str, int, bool):
        return value
    raise SWM0WS2SPilotError(
        f"canonical pilot JSON rejects value type {type(value)!r}"
    )


def canonical_json(value: Any) -> str:
    """Serialize a float-free receipt tree to one canonical JSON form."""

    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_sha256(value: object, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise SWM0WS2SPilotError(f"{name} must be a lowercase SHA-256")
    return value


def _with_sha256(payload: Mapping[str, Any], field: str) -> dict[str, Any]:
    unsigned = dict(payload)
    if field in unsigned:
        raise SWM0WS2SPilotError(f"duplicate self-hash field: {field}")
    return {**unsigned, field: canonical_sha256(unsigned)}


def _fraction_payload(value: Fraction) -> dict[str, int]:
    return {"denominator": value.denominator, "numerator": value.numerator}


def _parse_fraction_payload(value: object, name: str) -> Fraction:
    payload = _require_exact_keys(
        value, {"denominator", "numerator"}, f"{name} fraction"
    )
    numerator = payload["numerator"]
    denominator = payload["denominator"]
    if (
        type(numerator) is not int
        or type(denominator) is not int
        or denominator <= 0
    ):
        raise SWM0WS2SPilotError(
            f"{name} fraction requires exact integers and positive denominator"
        )
    parsed = Fraction(numerator, denominator)
    if parsed.numerator != numerator or parsed.denominator != denominator:
        raise SWM0WS2SPilotError(f"{name} fraction is not canonical and reduced")
    return parsed


def _finite_loss(value: object, name: str, *, positive: bool = False) -> float:
    if type(value) is not float or not math.isfinite(value) or value < 0.0:
        raise SWM0WS2SPilotError(f"{name} must be an exact finite non-negative float")
    if value == 0.0 and math.copysign(1.0, value) < 0.0:
        raise SWM0WS2SPilotError(f"{name} cannot be negative zero")
    if positive and value <= 0.0:
        raise SWM0WS2SPilotError(f"{name} must be strictly positive")
    return value


def _parse_canonical_float_hex(
    value: object, name: str, *, positive: bool = False
) -> float:
    if type(value) is not str:
        raise SWM0WS2SPilotError(f"{name} must be exact canonical float.hex text")
    try:
        parsed = float.fromhex(value)
    except ValueError as exc:
        raise SWM0WS2SPilotError(
            f"{name} must be exact canonical float.hex text"
        ) from exc
    if parsed.hex() != value:
        raise SWM0WS2SPilotError(f"{name} is not canonical float.hex text")
    return _finite_loss(parsed, name, positive=positive)


def fixed_roster() -> tuple[tuple[int, str, str], ...]:
    """Return the only permitted draw-major, arm-major, rate-major roster."""

    return tuple(
        (draw_index, public_arm, learning_rate_label)
        for draw_index in TASK_DRAW_INDICES
        for public_arm in PUBLIC_ARMS
        for learning_rate_label in LEARNING_RATE_LABELS
    )


def pilot_contract_payload() -> dict[str, Any]:
    """Return the predeclared, result-independent public pilot contract."""

    return {
        "adam": {
            "beta1_hex": BETA1.hex(),
            "beta2_hex": BETA2.hex(),
            "epsilon_hex": EPSILON.hex(),
            "global_gradient_clip_hex": GRADIENT_CLIP.hex(),
        },
        "future_confirmatory_boundary": {
            "fixed_selected_config": {
                "max_updates": STAGE2_MAX_UPDATES,
                "patience": PATIENCE,
            },
            "pilot_seed_and_draw_provenance_are_excluded": True,
            "pilot_external_seed_sha256_hex": EXTERNAL_SEED_SHA256_HEX,
            "pilot_task_draw_indices": list(TASK_DRAW_INDICES),
            "semantic_collisions_from_future_with_replacement_draws": (
                "RETAIN_AND_DISCLOSE_NEVER_FILTER_OR_REROLL"
            ),
            "prior_local_observation_is_timing_only_and_excluded": True,
            "selection_is_not_a_convergence_claim": True,
        },
        "initializer_seed": INITIALIZER_SEED,
        "learning_rates": [
            {
                "binary64_hex": LEARNING_RATE_HEX[label],
                "decimal_label": label,
            }
            for label in LEARNING_RATE_LABELS
        ],
        "min_delta_hex": MIN_DELTA.hex(),
        "ordered_cell_roster": [
            {
                "draw_index": draw_index,
                "learning_rate_decimal": learning_rate_label,
                "public_arm": public_arm,
                "roster_index": roster_index,
            }
            for roster_index, (draw_index, public_arm, learning_rate_label) in enumerate(
                fixed_roster()
            )
        ],
        "operator_arm_mapping": dict(PUBLIC_TO_OPERATOR_ARM),
        "precomputed_task_roster": {
            "batch_sha256": EXPECTED_TASK_BATCH_SHA256,
            "ordered_manifest_sha256s": list(EXPECTED_TASK_MANIFEST_SHA256S),
            "ordered_structural_target_sha256s": list(
                EXPECTED_STRUCTURAL_TARGET_SHA256S
            ),
            "ordered_structural_task_sha256s": list(
                EXPECTED_STRUCTURAL_TASK_SHA256S
            ),
            "seed_commitment_sha256": EXPECTED_SEED_COMMITMENT_SHA256,
        },
        "patience": PATIENCE,
        "projection": {
            "admit_when": "PROJECTED_STAGE2_FIT_AND_REPLAY_NS<=ADMISSION_LIMIT_NS",
            "admission_limit_minutes": ADMISSION_LIMIT_MINUTES,
            "admission_limit_ns": ADMISSION_LIMIT_NS,
            "formula": (
                "PROJECTED_STAGE2_FIT_AND_REPLAY_NS="
                "SUM_STAGE1_FIT_AND_REPLAY_NS*(300/10)"
            ),
            "integer_multiplier": PROJECTION_MULTIPLIER,
            "workflow_timeout_minutes": WORKFLOW_TIMEOUT_MINUTES,
        },
        "public_workflow_numeric_envelope": {
            "accepted_dispatch_policy": (
                "SOLE_FIRST_WORKFLOW_DISPATCH_FOR_EXACT_MAIN_COMMIT"
            ),
            "fixed_environment": dict(WORKFLOW_FIXED_ENVIRONMENT),
            "python_version": WORKFLOW_PYTHON_VERSION,
            "runner_image": WORKFLOW_RUNNER_IMAGE,
            "uv_version": WORKFLOW_UV_VERSION,
            "future_confirmatory_must_reuse_recorded_exact_envelope": True,
        },
        "schema_version": CONTRACT_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "seed_derivation": {
            "algorithm": "SHA256_OF_EXACT_ASCII_THEN_RAW_32_BYTE_DIGEST",
            "ascii": EXTERNAL_SEED_ASCII,
            "external_seed_sha256_hex": EXTERNAL_SEED_SHA256_HEX,
        },
        "selection": {
            "baseline": (
                "L0=EPOCH_ZERO_DEV_LOSS; IDENTICAL_POSITIVE_FLOAT_HEX_ACROSS_"
                "ALL_NINE_FULL_CELLS_WITHIN_EACH_DRAW"
            ),
            "eligible_cells": (
                "ALL_27_FRESH_STAGE2_CELLS_WITH_EXACT_REPLAY; "
                "CAP_LIMITED_REMAINS_ELIGIBLE"
            ),
            "loss_source": "BEST_DEV_LOSS_ONLY",
            "ranking": (
                "PER_ARM_LEXICOGRAPHIC(EXACT_MEAN_Z,EXACT_MAX_Z,NUMERIC_LR); "
                "Z=EXACT_DYADIC(L_STAR)/EXACT_DYADIC(L0)"
            ),
            "stage1_losses_used": False,
            "unused_for_ranking": [
                "best_update",
                "clipped_update_count",
                "runtime",
                "rss",
                "train_loss",
            ],
        },
        "validation_assurance": {
            "offline_parser": "STRICT_SELF_CONSISTENCY_NOT_AUTHENTICATED_EXECUTION",
            "runner": "FIT_THEN_DETERMINISTIC_REPLAY_BEFORE_CELL_EMISSION",
        },
        "splits_materialized": ["train", "dev"],
        "stage1": {
            "cell_count": EXPECTED_CELL_COUNT,
            "max_updates": STAGE1_MAX_UPDATES,
            "purpose": "FIT_AND_REPLAY_RUNTIME_TELEMETRY_ONLY",
        },
        "stage2": {
            "cell_count": EXPECTED_CELL_COUNT,
            "fresh_rerun_of_every_cell": True,
            "max_updates": STAGE2_MAX_UPDATES,
        },
        "task_draw_indices": list(TASK_DRAW_INDICES),
        "verdict": NO_EFFICACY_VERDICT,
    }


PILOT_CONTRACT_SHA256 = canonical_sha256(pilot_contract_payload())


def _first_cpu_field(name: str) -> str | None:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip() == name:
                return value.strip()
    except OSError:
        return None
    return None


def numeric_environment_payload() -> dict[str, Any]:
    """Capture the numeric environment without volatile clocks or memory data."""

    import numpy as np

    configuration = np.__config__.show(mode="dicts")
    build_dependencies = configuration.get("Build Dependencies", {})
    blas = build_dependencies.get("blas", {})
    simd = configuration.get("SIMD Extensions", {})
    thread_names = (
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "OMP_NUM_THREADS",
        "OPENBLAS_CORETYPE",
        "OPENBLAS_NUM_THREADS",
        "PYTHONHASHSEED",
    )
    return {
        "blas": {
            "name": str(blas.get("name", "UNKNOWN")),
            "openblas_configuration": str(
                blas.get("openblas configuration", "UNKNOWN")
            ),
            "version": str(blas.get("version", "UNKNOWN")),
        },
        "byteorder": sys.byteorder,
        "cpu": {
            "flags": _first_cpu_field("flags"),
            "machine": platform.machine(),
            "model_name": _first_cpu_field("model name"),
            "vendor_id": _first_cpu_field("vendor_id"),
        },
        "numpy_version": np.__version__,
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "runner_arch": os.environ.get("RUNNER_ARCH"),
        "runner_os": os.environ.get("RUNNER_OS"),
        "simd": {
            "baseline": list(simd.get("baseline", ())),
            "found": list(simd.get("found", ())),
            "not_found": list(simd.get("not found", ())),
        },
        "source_commit": os.environ.get(
            "HSWM_PILOT_SOURCE_COMMIT", "UNSPECIFIED_DEVELOPMENT_SOURCE"
        ),
        "thread_environment": {
            name: os.environ.get(name) for name in thread_names
        },
    }


def _require_public_workflow_environment(environment: Mapping[str, Any]) -> None:
    """Fail closed when GitHub's observed numeric envelope drifts."""

    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    source_commit = environment.get("source_commit")
    if (
        environment.get("python_version") != WORKFLOW_PYTHON_VERSION
        or environment.get("runner_os") != "Linux"
        or environment.get("runner_arch") != "X64"
        or environment.get("thread_environment") != WORKFLOW_FIXED_ENVIRONMENT
        or type(source_commit) is not str
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
        or source_commit != os.environ.get("GITHUB_SHA")
    ):
        raise SWM0WS2SPilotError("public workflow numeric envelope drifted")


@lru_cache(maxsize=len(TASK_DRAW_INDICES))
def _expected_public_task(draw_index: int) -> object:
    if type(draw_index) is not int or draw_index not in TASK_DRAW_INDICES:
        raise SWM0WS2SPilotError("public task draw index drifted")
    from hswm.experiments.swm0w_s2s_family import generate_task

    return generate_task(external_seed=EXTERNAL_SEED, draw_index=draw_index)


def _task_binding(task: object) -> dict[str, Any]:
    fields = (
        "draw_index",
        "family_certificate_sha256",
        "family_definition_sha256",
        "manifest_sha256",
        "seed_commitment_sha256",
        "structural_target_sha256",
        "structural_task_sha256",
    )
    values = {field: getattr(task, field) for field in fields}
    if type(values["draw_index"]) is not int:
        raise SWM0WS2SPilotError("task draw index is not exact int")
    for field in fields[1:]:
        value = values[field]
        _require_sha256(value, f"task {field}")
    if not hasattr(task, "canonical"):
        raise SWM0WS2SPilotError("task lacks a canonical manifest")
    return {
        **values,
        "task_spec": task.canonical(),
    }


def _opaque_task_binding(task_binding: Mapping[str, Any]) -> dict[str, Any]:
    """Retain task identity without exposing split or target-bearing structure."""

    fields = (
        "draw_index",
        "family_certificate_sha256",
        "family_definition_sha256",
        "manifest_sha256",
        "seed_commitment_sha256",
        "structural_target_sha256",
        "structural_task_sha256",
    )
    if any(field not in task_binding for field in fields):
        raise SWM0WS2SPilotError("opaque task binding is incomplete")
    return {field: task_binding[field] for field in fields}


def _task_batch_sha256(task_bindings: Sequence[Mapping[str, Any]]) -> str:
    if len(task_bindings) != len(TASK_DRAW_INDICES):
        raise SWM0WS2SPilotError("task batch requires all three ordered draws")
    from hswm.experiments.swm0w_s2s_family import TASK_BATCH_VERSION

    def duplicates(field: str) -> list[list[int]]:
        first_seen: dict[str, int] = {}
        result: list[list[int]] = []
        for index, task in enumerate(task_bindings):
            key = task[field]
            if key in first_seen:
                result.append([index, first_seen[key]])
            else:
                first_seen[key] = index
        return result

    return canonical_sha256(
        {
            "duplicate_structural_target_draws": duplicates(
                "structural_target_sha256"
            ),
            "duplicate_structural_task_draws": duplicates(
                "structural_task_sha256"
            ),
            "requested_count": len(task_bindings),
            "schema_version": TASK_BATCH_VERSION,
            "seed_commitment_sha256": task_bindings[0][
                "seed_commitment_sha256"
            ],
            "task_manifest_sha256s": [
                task["manifest_sha256"] for task in task_bindings
            ],
        }
    )


_TRAINING_CONFIG_KEYS = {
    "beta1_hex",
    "beta2_hex",
    "epsilon_hex",
    "gradient_clip_hex",
    "learning_rate_hex",
    "max_updates",
    "min_delta_hex",
    "patience",
    "seed",
}
_STRATUM_RECEIPT_KEYS = {
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
}
_HISTORY_ENTRY_KEYS = {
    "clipped",
    "dev_loss_hex",
    "gradient_norm_hex",
    "improved",
    "parameters_sha256",
    "schema_version",
    "train_loss_hex",
    "update",
}
_OPTIMIZATION_RECEIPT_KEYS = {
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
}


def _parse_training_config(
    value: object, *, max_updates: int, learning_rate_label: str
) -> object:
    config_payload = _require_exact_keys(
        value, _TRAINING_CONFIG_KEYS, "training config"
    )
    from hswm.experiments.swm0w_s2s_training import S2STrainingConfig

    try:
        config = S2STrainingConfig(
            seed=config_payload["seed"],
            max_updates=config_payload["max_updates"],
            learning_rate=_parse_canonical_float_hex(
                config_payload["learning_rate_hex"],
                "training learning rate",
                positive=True,
            ),
            beta1=_parse_canonical_float_hex(
                config_payload["beta1_hex"], "training beta1", positive=True
            ),
            beta2=_parse_canonical_float_hex(
                config_payload["beta2_hex"], "training beta2", positive=True
            ),
            epsilon=_parse_canonical_float_hex(
                config_payload["epsilon_hex"],
                "training epsilon",
                positive=True,
            ),
            gradient_clip=_parse_canonical_float_hex(
                config_payload["gradient_clip_hex"],
                "training gradient clip",
                positive=True,
            ),
            patience=config_payload["patience"],
            min_delta=_parse_canonical_float_hex(
                config_payload["min_delta_hex"], "training min delta"
            ),
        )
    except (TypeError, ValueError) as exc:
        raise SWM0WS2SPilotError("training config is invalid") from exc
    expected = _config_for(max_updates, learning_rate_label)
    if config != expected or canonical_json(config.canonical()) != canonical_json(
        config_payload
    ):
        raise SWM0WS2SPilotError("training config drifted from the fixed cell")
    return config


def _parse_stratum_receipt(value: object) -> object:
    payload = _require_exact_keys(
        value, _STRATUM_RECEIPT_KEYS, "stratum loss receipt"
    )
    from hswm.experiments.swm0w_s2s_training import StratumLossReceipt

    try:
        receipt = StratumLossReceipt(
            role=payload["role"],
            channel=payload["channel"],
            sample_count=payload["sample_count"],
            target_numerator_sum=payload["target_numerator_sum"],
            target_numerator_sum_squares=payload["target_numerator_sum_squares"],
            centered_sum_squares_numerator=payload[
                "centered_sum_squares_numerator"
            ],
            inverse_variance_weight=_parse_canonical_float_hex(
                payload["inverse_variance_weight_hex"],
                "inverse variance weight",
                positive=True,
            ),
            receipt_sha256=payload["receipt_sha256"],
        )
    except (TypeError, ValueError) as exc:
        raise SWM0WS2SPilotError("stratum loss receipt is invalid") from exc
    if canonical_json(receipt.canonical()) != canonical_json(payload):
        raise SWM0WS2SPilotError("stratum loss receipt canonical form drifted")
    return receipt


def _parse_history_entry(value: object) -> object:
    payload = _require_exact_keys(value, _HISTORY_ENTRY_KEYS, "history entry")
    from hswm.experiments.swm0w_s2s_training import OptimizationHistoryEntry

    gradient_hex = payload["gradient_norm_hex"]
    if gradient_hex is not None and type(gradient_hex) is not str:
        raise SWM0WS2SPilotError("history gradient norm hex is malformed")
    try:
        entry = OptimizationHistoryEntry(
            update=payload["update"],
            train_loss=_parse_canonical_float_hex(
                payload["train_loss_hex"], "history train loss"
            ),
            dev_loss=_parse_canonical_float_hex(
                payload["dev_loss_hex"], "history dev loss"
            ),
            gradient_norm=(
                None
                if gradient_hex is None
                else _parse_canonical_float_hex(
                    gradient_hex, "history gradient norm"
                )
            ),
            clipped=payload["clipped"],
            improved=payload["improved"],
            parameters_sha256=payload["parameters_sha256"],
        )
    except (TypeError, ValueError) as exc:
        raise SWM0WS2SPilotError("history entry is invalid") from exc
    if canonical_json(entry.canonical()) != canonical_json(payload):
        raise SWM0WS2SPilotError("history entry canonical form drifted")
    return entry


def _parse_optimization_receipt(
    value: object,
    *,
    draw_index: int,
    public_arm: str,
    learning_rate_label: str,
    max_updates: int,
) -> object:
    payload = _require_exact_keys(
        value, _OPTIMIZATION_RECEIPT_KEYS, "optimization receipt"
    )
    task = _expected_public_task(draw_index)
    if canonical_json(payload["task_spec"]) != canonical_json(task.canonical()):
        raise SWM0WS2SPilotError("optimization receipt task spec drifted")
    config = _parse_training_config(
        payload["config"],
        max_updates=max_updates,
        learning_rate_label=learning_rate_label,
    )
    if type(payload["stratum_loss_receipts"]) is not list:
        raise SWM0WS2SPilotError("optimization strata must be an exact list")
    if type(payload["history"]) is not list:
        raise SWM0WS2SPilotError("optimization history must be an exact list")
    if len(payload["stratum_loss_receipts"]) != 6 or len(payload["history"]) > (
        max_updates + 1
    ):
        raise SWM0WS2SPilotError("optimization receipt collection size drifted")
    strata = tuple(
        _parse_stratum_receipt(item) for item in payload["stratum_loss_receipts"]
    )
    history = tuple(_parse_history_entry(item) for item in payload["history"])
    from hswm.experiments.swm0w_s2s_operator import S2SArm
    from hswm.experiments.swm0w_s2s_training import (
        S2SOptimizationReceipt,
        TerminationReason,
    )

    try:
        arm = S2SArm(payload["arm"])
        termination = TerminationReason(payload["termination_reason"])
        receipt = S2SOptimizationReceipt(
            arm=arm,
            config=config,
            task=task,
            family_definition_sha256=payload["family_definition_sha256"],
            family_certificate_sha256=payload["family_certificate_sha256"],
            structural_target_sha256=payload["structural_target_sha256"],
            structural_task_sha256=payload["structural_task_sha256"],
            task_manifest_sha256=payload["task_manifest_sha256"],
            train_dataset_sha256=payload["train_dataset_sha256"],
            dev_dataset_sha256=payload["dev_dataset_sha256"],
            dataset_schema_sha256=payload["dataset_schema_sha256"],
            train_case_count=payload["train_case_count"],
            dev_case_count=payload["dev_case_count"],
            stratum_loss_receipts=strata,
            loss_definition_sha256=payload["loss_definition_sha256"],
            operator_architecture_receipt_sha256=payload[
                "operator_architecture_receipt_sha256"
            ],
            initial_parameters_sha256=payload["initial_parameters_sha256"],
            best_parameters_sha256=payload["best_parameters_sha256"],
            best_update=payload["best_update"],
            stopped_update=payload["stopped_update"],
            best_train_loss=_parse_canonical_float_hex(
                payload["best_train_loss_hex"], "best train loss"
            ),
            best_dev_loss=_parse_canonical_float_hex(
                payload["best_dev_loss_hex"], "best dev loss"
            ),
            update_count=payload["update_count"],
            clipped_update_count=payload["clipped_update_count"],
            history=history,
            history_entry_count=payload["history_entry_count"],
            history_sha256=payload["history_sha256"],
            termination_reason=termination,
            receipt_sha256=payload["receipt_sha256"],
        )
    except (TypeError, ValueError) as exc:
        raise SWM0WS2SPilotError("optimization receipt is invalid") from exc
    if arm.value != PUBLIC_TO_OPERATOR_ARM[public_arm]:
        raise SWM0WS2SPilotError("optimization receipt arm drifted")
    if canonical_json(receipt.canonical()) != canonical_json(payload):
        raise SWM0WS2SPilotError("optimization receipt canonical form drifted")
    return receipt


def _cell_key(
    roster_index: int,
    draw_index: int,
    public_arm: str,
    learning_rate_label: str,
) -> dict[str, Any]:
    return {
        "draw_index": draw_index,
        "learning_rate_binary64_hex": LEARNING_RATE_HEX[learning_rate_label],
        "learning_rate_decimal": learning_rate_label,
        "operator_arm": PUBLIC_TO_OPERATOR_ARM[public_arm],
        "public_arm": public_arm,
        "roster_index": roster_index,
    }


def _enum_value(value: object) -> str:
    result = getattr(value, "value", value)
    if type(result) is not str:
        raise SWM0WS2SPilotError("enum-like value did not resolve to exact str")
    return result


def _model_common_record(
    model: object,
    *,
    task_binding: Mapping[str, Any],
    cell_key: Mapping[str, Any],
    expected_updates: int,
) -> tuple[dict[str, Any], object]:
    if getattr(model, "fitted", None) is not True:
        raise SWM0WS2SPilotError("fit did not return a fitted model")
    optimization = getattr(model, "optimization", None)
    config = getattr(model, "config", None)
    if optimization is None or config is None:
        raise SWM0WS2SPilotError("fit lacks optimization receipt or config")
    if getattr(config, "max_updates", None) != expected_updates:
        raise SWM0WS2SPilotError("fit config max_updates drifted")
    label = cell_key["learning_rate_decimal"]
    if type(label) is not str:
        raise SWM0WS2SPilotError("cell learning-rate label drifted")
    config_rate = getattr(config, "learning_rate", None)
    if type(config_rate) is not float or config_rate.hex() != float(label).hex():
        raise SWM0WS2SPilotError("decimal learning rate and config binary64 disagree")
    expected_operator_arm = cell_key["operator_arm"]
    if _enum_value(getattr(model, "arm", None)) != expected_operator_arm:
        raise SWM0WS2SPilotError("fit returned the wrong arm")
    stopped_update = getattr(optimization, "stopped_update", None)
    if (
        type(stopped_update) is not int
        or stopped_update < 0
        or stopped_update > expected_updates
    ):
        raise SWM0WS2SPilotError("fit stopped-update boundary drifted")
    receipt_sha256 = getattr(optimization, "receipt_sha256", None)
    parameters_sha256 = getattr(model, "parameters_sha256", None)
    state_sha256 = getattr(model, "state_sha256", None)
    for value, name in (
        (receipt_sha256, "optimization receipt"),
        (parameters_sha256, "parameters"),
        (state_sha256, "model state"),
    ):
        _require_sha256(value, f"{name} SHA")
    _require_sha256(
        getattr(optimization, "initial_parameters_sha256", None),
        "initial parameters SHA",
    )
    record = {
        **dict(cell_key),
        "best_parameters_sha256": parameters_sha256,
        "config": config.canonical(),
        "initial_parameters_sha256": getattr(
            optimization, "initial_parameters_sha256"
        ),
        "model_state_sha256": state_sha256,
        "optimization_receipt_sha256": receipt_sha256,
        "replay_validated": True,
        "schema_version": CELL_RECEIPT_VERSION,
        "stopped_update": stopped_update,
        "task": dict(task_binding),
    }
    return record, optimization


def _parameter_bytes(model: object) -> tuple[tuple[str, str, tuple[int, ...], bytes], ...]:
    parameters = getattr(model, "parameters", None)
    if not isinstance(parameters, Mapping):
        raise SWM0WS2SPilotError("model parameters are not a mapping")
    snapshots = []
    for name in sorted(parameters):
        value = parameters[name]
        dtype = str(getattr(value, "dtype", ""))
        shape = tuple(getattr(value, "shape", ()))
        try:
            payload = value.tobytes(order="C")
        except (AttributeError, TypeError) as exc:
            raise SWM0WS2SPilotError("parameter lacks canonical C-order bytes") from exc
        snapshots.append((str(name), dtype, shape, payload))
    return tuple(snapshots)


def _require_exact_replay(original: object, replayed: object) -> None:
    original_optimization = getattr(original, "optimization", None)
    replayed_optimization = getattr(replayed, "optimization", None)
    if original_optimization is None or replayed_optimization is None:
        raise SWM0WS2SPilotError("replay lacks an optimization receipt")
    if original_optimization.canonical() != replayed_optimization.canonical():
        raise SWM0WS2SPilotError("replay optimization receipt mismatch")
    if getattr(original, "state_sha256", None) != getattr(
        replayed, "state_sha256", None
    ):
        raise SWM0WS2SPilotError("replay model-state mismatch")
    if getattr(original, "parameters_sha256", None) != getattr(
        replayed, "parameters_sha256", None
    ):
        raise SWM0WS2SPilotError("replay parameter SHA mismatch")
    if _parameter_bytes(original) != _parameter_bytes(replayed):
        raise SWM0WS2SPilotError("replay parameter bytes mismatch")


def _throughput_cell_record(
    model: object,
    *,
    task_binding: Mapping[str, Any],
    cell_key: Mapping[str, Any],
) -> dict[str, Any]:
    common, optimization = _model_common_record(
        model,
        task_binding=task_binding,
        cell_key=cell_key,
        expected_updates=STAGE1_MAX_UPDATES,
    )
    if getattr(optimization, "stopped_update", None) != STAGE1_MAX_UPDATES:
        raise SWM0WS2SPilotError("throughput cell did not execute all ten updates")
    if _enum_value(getattr(optimization, "termination_reason", None)) != "MAX_UPDATES":
        raise SWM0WS2SPilotError("throughput cell terminated unexpectedly")
    payload = {
        "config": common["config"],
        "draw_index": common["draw_index"],
        "learning_rate_binary64_hex": common[
            "learning_rate_binary64_hex"
        ],
        "learning_rate_decimal": common["learning_rate_decimal"],
        "model_state_sha256": common["model_state_sha256"],
        "operator_arm": common["operator_arm"],
        "optimization_receipt_sha256": common[
            "optimization_receipt_sha256"
        ],
        "parameters_sha256": common["best_parameters_sha256"],
        "public_arm": common["public_arm"],
        "roster_index": common["roster_index"],
        "runner_replay_observed": True,
        "schema_version": THROUGHPUT_CELL_RECEIPT_VERSION,
        "stage": STAGE1_NAME,
        "task": _opaque_task_binding(task_binding),
        "telemetry_only": True,
    }
    return _with_sha256(payload, "cell_receipt_sha256")


def _full_cell_record(
    model: object,
    *,
    task_binding: Mapping[str, Any],
    cell_key: Mapping[str, Any],
) -> dict[str, Any]:
    common, optimization = _model_common_record(
        model,
        task_binding=task_binding,
        cell_key=cell_key,
        expected_updates=STAGE2_MAX_UPDATES,
    )
    history = getattr(optimization, "history", None)
    if type(history) is not tuple or len(history) == 0:
        raise SWM0WS2SPilotError("full cell lacks epoch-zero history")
    initial_dev_loss = _finite_loss(
        getattr(history[0], "dev_loss", None), "epoch-zero dev loss", positive=True
    )
    best_dev_loss = _finite_loss(
        getattr(optimization, "best_dev_loss", None), "best dev loss"
    )
    best_train_loss = _finite_loss(
        getattr(optimization, "best_train_loss", None), "best train loss"
    )
    termination = _enum_value(getattr(optimization, "termination_reason", None))
    if termination not in {"MAX_UPDATES", "PATIENCE"}:
        raise SWM0WS2SPilotError("full cell termination reason drifted")
    best_update = getattr(optimization, "best_update", None)
    clipped_update_count = getattr(optimization, "clipped_update_count", None)
    if type(best_update) is not int or type(clipped_update_count) is not int:
        raise SWM0WS2SPilotError("full cell integer diagnostics are malformed")
    ratio = Fraction.from_float(best_dev_loss) / Fraction.from_float(initial_dev_loss)
    payload = {
        **common,
        "best_dev_loss_hex": best_dev_loss.hex(),
        "best_train_loss_hex": best_train_loss.hex(),
        "best_update": best_update,
        "budget_status": (
            "CAP_LIMITED"
            if termination == "MAX_UPDATES"
            else "FIXED_PATIENCE_STOP"
        ),
        "clipped_update_count": clipped_update_count,
        "epoch_zero_dev_loss_hex": initial_dev_loss.hex(),
        "fitted": True,
        "learned": getattr(model, "learned", None) is True,
        "optimization_receipt": optimization.canonical(),
        "stage": STAGE2_NAME,
        "termination_reason": termination,
        "z_exact": _fraction_payload(ratio),
    }
    return _with_sha256(payload, "cell_receipt_sha256")


_STAGE1_CELL_KEYS = {
    "cell_receipt_sha256",
    "config",
    "draw_index",
    "learning_rate_binary64_hex",
    "learning_rate_decimal",
    "model_state_sha256",
    "operator_arm",
    "optimization_receipt_sha256",
    "parameters_sha256",
    "public_arm",
    "roster_index",
    "runner_replay_observed",
    "schema_version",
    "stage",
    "task",
    "telemetry_only",
}
_STAGE2_CELL_KEYS = {
    "best_parameters_sha256",
    "cell_receipt_sha256",
    "config",
    "draw_index",
    "initial_parameters_sha256",
    "learning_rate_binary64_hex",
    "learning_rate_decimal",
    "model_state_sha256",
    "operator_arm",
    "optimization_receipt",
    "optimization_receipt_sha256",
    "public_arm",
    "replay_validated",
    "roster_index",
    "schema_version",
    "stage",
    "stopped_update",
    "task",
    "best_dev_loss_hex",
    "best_train_loss_hex",
    "best_update",
    "budget_status",
    "clipped_update_count",
    "epoch_zero_dev_loss_hex",
    "fitted",
    "learned",
    "termination_reason",
    "z_exact",
}


def _expected_model_state_sha256(receipt: object, *, learned: bool) -> str:
    from hswm.experiments import swm0w_s2s_training as training

    return canonical_sha256(
        {
            "arm": receipt.arm.value,
            "fitted": True,
            "learned": learned,
            "optimization_receipt_sha256": receipt.receipt_sha256,
            "parameters_sha256": receipt.best_parameters_sha256,
            "receipt_assurance": training.RECEIPT_ASSURANCE,
            "schema_version": training.TRAINING_VERSION,
            "scientific_status": training.SCIENTIFIC_STATUS,
            "structural_task_sha256": receipt.structural_task_sha256,
        }
    )


def _validate_cell_prefix(
    cells: Sequence[Mapping[str, Any]], *, stage: str
) -> None:
    if stage not in {STAGE1_NAME, STAGE2_NAME}:
        raise SWM0WS2SPilotError("cell stage is not part of the fixed pilot")
    if type(cells) not in (tuple, list) or len(cells) > EXPECTED_CELL_COUNT:
        raise SWM0WS2SPilotError("cell list is not a fixed-roster prefix")
    for roster_index, (cell, expected_key) in enumerate(
        zip(cells, fixed_roster(), strict=False)
    ):
        expected_keys = (
            _STAGE1_CELL_KEYS if stage == STAGE1_NAME else _STAGE2_CELL_KEYS
        )
        _require_exact_keys(cell, expected_keys, "pilot cell")
        draw_index, public_arm, learning_rate_label = expected_key
        if (
            type(cell.get("roster_index")) is not int
            or cell["roster_index"] != roster_index
            or type(cell.get("draw_index")) is not int
            or cell["draw_index"] != draw_index
            or type(cell.get("public_arm")) is not str
            or cell["public_arm"] != public_arm
            or type(cell.get("learning_rate_decimal")) is not str
            or cell["learning_rate_decimal"] != learning_rate_label
            or type(cell.get("operator_arm")) is not str
            or cell["operator_arm"] != PUBLIC_TO_OPERATOR_ARM[public_arm]
            or type(cell.get("learning_rate_binary64_hex")) is not str
            or cell["learning_rate_binary64_hex"]
            != LEARNING_RATE_HEX[learning_rate_label]
            or cell.get("stage") != stage
            or cell.get("schema_version")
            != (
                THROUGHPUT_CELL_RECEIPT_VERSION
                if stage == STAGE1_NAME
                else CELL_RECEIPT_VERSION
            )
        ):
            raise SWM0WS2SPilotError("selector cell roster identity drifted")
        _parse_canonical_float_hex(
            cell.get("learning_rate_binary64_hex"),
            "cell learning rate",
            positive=True,
        )
        if stage == STAGE1_NAME:
            config = _parse_training_config(
                cell["config"],
                max_updates=STAGE1_MAX_UPDATES,
                learning_rate_label=learning_rate_label,
            )
            expected_task_binding = _opaque_task_binding(
                _task_binding(_expected_public_task(draw_index))
            )
            for field in (
                "model_state_sha256",
                "optimization_receipt_sha256",
                "parameters_sha256",
            ):
                _require_sha256(cell[field], f"throughput cell {field}")
            if (
                canonical_json(cell["config"])
                != canonical_json(config.canonical())
                or canonical_json(cell["task"])
                != canonical_json(expected_task_binding)
                or cell.get("runner_replay_observed") is not True
                or cell.get("telemetry_only") is not True
            ):
                raise SWM0WS2SPilotError("throughput cell semantics drifted")
            cell_sha256 = cell.get("cell_receipt_sha256")
            _require_sha256(cell_sha256, "throughput cell receipt SHA")
            unsigned = dict(cell)
            del unsigned["cell_receipt_sha256"]
            if canonical_sha256(unsigned) != cell_sha256:
                raise SWM0WS2SPilotError("throughput cell receipt SHA mismatch")
            continue

        if cell.get("replay_validated") is not True:
            raise SWM0WS2SPilotError("selector requires replay-valid cells only")
        receipt = _parse_optimization_receipt(
            cell["optimization_receipt"],
            draw_index=draw_index,
            public_arm=public_arm,
            learning_rate_label=learning_rate_label,
            max_updates=STAGE2_MAX_UPDATES,
        )
        expected_task_binding = _task_binding(_expected_public_task(draw_index))
        learned = (
            receipt.best_update > 0
            and receipt.best_parameters_sha256
            != receipt.initial_parameters_sha256
        )
        termination = receipt.termination_reason.value
        expected_budget_status = (
            "CAP_LIMITED"
            if termination == "MAX_UPDATES"
            else "FIXED_PATIENCE_STOP"
        )
        if (
            canonical_json(cell["config"])
            != canonical_json(receipt.config.canonical())
            or canonical_json(cell["task"])
            != canonical_json(expected_task_binding)
            or cell["optimization_receipt_sha256"] != receipt.receipt_sha256
            or cell["best_parameters_sha256"]
            != receipt.best_parameters_sha256
            or cell["initial_parameters_sha256"]
            != receipt.initial_parameters_sha256
            or type(cell["stopped_update"]) is not int
            or cell["stopped_update"] != receipt.stopped_update
            or type(cell["fitted"]) is not bool
            or cell["fitted"] is not True
            or type(cell["learned"]) is not bool
            or cell["learned"] is not learned
            or cell["termination_reason"] != termination
            or cell["budget_status"] != expected_budget_status
            or cell["model_state_sha256"]
            != _expected_model_state_sha256(receipt, learned=learned)
        ):
            raise SWM0WS2SPilotError("cell fields drifted from optimization receipt")
        baseline = _parse_canonical_float_hex(
            cell.get("epoch_zero_dev_loss_hex"),
            "cell epoch-zero dev loss",
            positive=True,
        )
        best_dev = _parse_canonical_float_hex(
            cell.get("best_dev_loss_hex"),
            "cell best dev loss",
        )
        if (
            baseline.hex() != receipt.history[0].dev_loss.hex()
            or best_dev.hex() != receipt.best_dev_loss.hex()
            or _parse_canonical_float_hex(
                cell["best_train_loss_hex"], "cell best train loss"
            ).hex()
            != receipt.best_train_loss.hex()
            or type(cell["best_update"]) is not int
            or cell["best_update"] != receipt.best_update
            or type(cell["clipped_update_count"]) is not int
            or cell["clipped_update_count"] != receipt.clipped_update_count
            or _parse_fraction_payload(cell["z_exact"], "cell z")
            != Fraction.from_float(best_dev) / Fraction.from_float(baseline)
        ):
            raise SWM0WS2SPilotError(
                "selector cell loss fields drifted from receipt"
            )
        cell_sha256 = cell.get("cell_receipt_sha256")
        _require_sha256(cell_sha256, "selector cell receipt SHA")
        unsigned = dict(cell)
        del unsigned["cell_receipt_sha256"]
        if canonical_sha256(unsigned) != cell_sha256:
            raise SWM0WS2SPilotError("selector cell receipt SHA mismatch")


def _validate_exact_full_roster(cells: Sequence[Mapping[str, Any]]) -> None:
    if type(cells) not in (tuple, list) or len(cells) != EXPECTED_CELL_COUNT:
        raise SWM0WS2SPilotError("selector requires the exact ordered 27-cell roster")
    _validate_cell_prefix(cells, stage=STAGE2_NAME)


def _select_validated_learning_rates(
    full_cells: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Apply the exact ranking after the strict cell parser has succeeded."""

    by_draw: dict[int, list[Mapping[str, Any]]] = {
        draw_index: [] for draw_index in TASK_DRAW_INDICES
    }
    for cell in full_cells:
        by_draw[cell["draw_index"]].append(cell)
    baseline_hex_by_draw: dict[int, str] = {}
    for draw_index in TASK_DRAW_INDICES:
        baseline_values = {
            cell.get("epoch_zero_dev_loss_hex") for cell in by_draw[draw_index]
        }
        if len(baseline_values) != 1:
            raise SWM0WS2SPilotError("epoch-zero dev loss drifted within a task")
        baseline_hex = next(iter(baseline_values))
        baseline = Fraction.from_float(
            _parse_canonical_float_hex(
                baseline_hex, "epoch-zero dev loss", positive=True
            )
        )
        baseline_hex_by_draw[draw_index] = baseline_hex

    selections = []
    for public_arm in PUBLIC_ARMS:
        candidates = []
        for learning_rate_label in LEARNING_RATE_LABELS:
            cells = tuple(
                cell
                for cell in full_cells
                if cell["public_arm"] == public_arm
                and cell["learning_rate_decimal"] == learning_rate_label
            )
            if tuple(cell["draw_index"] for cell in cells) != TASK_DRAW_INDICES:
                raise SWM0WS2SPilotError("selection candidate lacks all three draws")
            ratios = []
            for cell in cells:
                if cell["learning_rate_binary64_hex"] != float(
                    learning_rate_label
                ).hex():
                    raise SWM0WS2SPilotError(
                        "selection learning-rate label and binary64 drifted"
                    )
                best = Fraction.from_float(
                    _parse_canonical_float_hex(
                        cell["best_dev_loss_hex"], "best dev loss"
                    )
                )
                baseline = Fraction.from_float(
                    _parse_canonical_float_hex(
                        baseline_hex_by_draw[cell["draw_index"]],
                        "epoch-zero dev loss",
                        positive=True,
                    )
                )
                observed_ratio = best / baseline
                if _parse_fraction_payload(
                    cell.get("z_exact"), "selection cell z"
                ) != observed_ratio:
                    raise SWM0WS2SPilotError("cell z receipt drifted")
                ratios.append(observed_ratio)
            mean_ratio = sum(ratios, Fraction(0, 1)) / len(TASK_DRAW_INDICES)
            maximum_ratio = max(ratios)
            numeric_rate = Fraction(learning_rate_label)
            candidates.append(
                (
                    (mean_ratio, maximum_ratio, numeric_rate),
                    {
                        "learning_rate_binary64_hex": LEARNING_RATE_HEX[
                            learning_rate_label
                        ],
                        "learning_rate_decimal": learning_rate_label,
                        "max_z_exact": _fraction_payload(maximum_ratio),
                        "mean_z_exact": _fraction_payload(mean_ratio),
                        "ordered_cell_receipt_sha256s": [
                            cell["cell_receipt_sha256"] for cell in cells
                        ],
                        "ordered_draw_indices": list(TASK_DRAW_INDICES),
                    },
                )
            )
        candidates.sort(key=lambda item: item[0])
        selected_rank, selected = candidates[0]
        candidate_payloads = [
            payload
            for _, payload in sorted(
                candidates, key=lambda item: Fraction(item[1]["learning_rate_decimal"])
            )
        ]
        payload = {
            "candidate_summaries": candidate_payloads,
            "public_arm": public_arm,
            "ranking_key": {
                "max_z_exact": _fraction_payload(selected_rank[1]),
                "mean_z_exact": _fraction_payload(selected_rank[0]),
                "numeric_learning_rate": _fraction_payload(selected_rank[2]),
            },
            "schema_version": SELECTION_VERSION,
            "selected_learning_rate_binary64_hex": selected[
                "learning_rate_binary64_hex"
            ],
            "selected_learning_rate_decimal": selected[
                "learning_rate_decimal"
            ],
            "selection_is_not_a_convergence_claim": True,
        }
        selections.append(_with_sha256(payload, "selection_receipt_sha256"))
    return tuple(selections)


def select_learning_rates(
    full_cells: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Select per arm from all 27 replay-valid stage-two cells, or raise."""

    _validate_exact_full_roster(full_cells)
    return _select_validated_learning_rates(full_cells)


def _deterministic_receipt(
    *,
    environment: Mapping[str, Any] | None,
    task_bindings: Sequence[Mapping[str, Any]],
    stage1_cells: Sequence[Mapping[str, Any]],
    stage2_cells: Sequence[Mapping[str, Any]],
    selections: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    complete = (
        len(stage1_cells) == EXPECTED_CELL_COUNT
        and len(stage2_cells) == EXPECTED_CELL_COUNT
        and len(selections) == len(PUBLIC_ARMS)
    )
    payload = {
        "completion": (
            "COMPLETE_FIXED_DEVELOPMENT_ROSTER"
            if complete
            else "INCOMPLETE_NO_SELECTION"
        ),
        "contract": pilot_contract_payload(),
        "contract_sha256": PILOT_CONTRACT_SHA256,
        "future_confirmatory_exclusion": {
            "exclusion_scope": "EXACT_PILOT_SEED_AND_DRAW_PROVENANCE_ONLY",
            "excluded_external_seed_sha256_hex": EXTERNAL_SEED_SHA256_HEX,
            "excluded_ordered_task_draw_indices": list(TASK_DRAW_INDICES),
            "future_semantic_collision_policy": (
                "RETAIN_AND_DISCLOSE_NEVER_FILTER_OR_REROLL"
            ),
            "recorded_pilot_ordered_task_manifest_sha256s": [
                task["manifest_sha256"] for task in task_bindings
            ],
            "recorded_pilot_ordered_structural_task_sha256s": [
                task["structural_task_sha256"] for task in task_bindings
            ],
            "required": True,
        },
        "execution_bound_numeric_environment": (
            None if environment is None else dict(environment)
        ),
        "execution_bound_numeric_environment_sha256": (
            None if environment is None else canonical_sha256(environment)
        ),
        "ordered_stage1_cell_receipts": list(stage1_cells),
        "ordered_stage2_cell_receipts": list(stage2_cells),
        "ordered_task_bindings": list(task_bindings),
        "schema_version": DETERMINISTIC_RECEIPT_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "selections": list(selections) if complete else [],
        "selection_status": (
            "COMPLETE_DEVELOPMENT_SELECTION" if complete else NO_SELECTION
        ),
        "task_batch_sha256": (
            _task_batch_sha256(task_bindings)
            if len(task_bindings) == len(TASK_DRAW_INDICES)
            else None
        ),
        "verdict": NO_EFFICACY_VERDICT,
    }
    return _with_sha256(payload, "deterministic_receipt_sha256")


def _runtime_report(
    *,
    terminal_status: str,
    reason_code: str,
    task_preparation: Sequence[Mapping[str, Any]],
    cell_runtime: Sequence[Mapping[str, Any]],
    admission: Mapping[str, Any] | None,
    error: BaseException | None = None,
) -> dict[str, Any]:
    payload = {
        "admission": None if admission is None else dict(admission),
        "cell_runtime": list(cell_runtime),
        "error": (
            None
            if error is None
            else {
                "class": type(error).__name__,
                "message": str(error),
            }
        ),
        "reason_code": reason_code,
        "schema_version": RUNTIME_TELEMETRY_VERSION,
        "task_preparation_runtime": list(task_preparation),
        "terminal_status": terminal_status,
        "telemetry_is_nondeterministic": True,
    }
    return _with_sha256(payload, "runtime_telemetry_sha256")


def _artifact(
    deterministic_receipt: Mapping[str, Any], runtime_telemetry: Mapping[str, Any]
) -> dict[str, Any]:
    payload = {
        "deterministic_receipt": dict(deterministic_receipt),
        "runtime_telemetry": dict(runtime_telemetry),
        "schema_version": PILOT_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "terminal_status": runtime_telemetry["terminal_status"],
        "verdict": NO_EFFICACY_VERDICT,
    }
    return _with_sha256(payload, "artifact_sha256")


def initial_void_artifact() -> dict[str, Any]:
    """Return the marker written before any expensive work begins."""

    deterministic = _deterministic_receipt(
        environment=None,
        task_bindings=(),
        stage1_cells=(),
        stage2_cells=(),
        selections=(),
    )
    runtime = _runtime_report(
        terminal_status=TERMINAL_VOID,
        reason_code="RUN_NOT_COMPLETED",
        task_preparation=(),
        cell_runtime=(),
        admission=None,
    )
    return _artifact(deterministic, runtime)


def _peak_rss_kib() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if type(value) not in (int, float) or value < 0:
        raise SWM0WS2SPilotError("peak RSS is unavailable")
    # Linux reports KiB.  The public workflow is frozen to ubuntu-24.04.
    return int(value)


def _runtime_cell(
    *,
    stage: str,
    cell_key: Mapping[str, Any],
    fit_elapsed_ns: int,
    replay_elapsed_ns: int,
    peak_rss_kib: int,
    exit_status: str,
    error: BaseException | None = None,
) -> dict[str, Any]:
    return {
        **dict(cell_key),
        "error_class": None if error is None else type(error).__name__,
        "error_message": None if error is None else str(error),
        "exit_status": exit_status,
        "fit_and_replay_elapsed_ns": fit_elapsed_ns + replay_elapsed_ns,
        "fit_elapsed_ns": fit_elapsed_ns,
        "peak_rss_kib_after": peak_rss_kib,
        "replay_elapsed_ns": replay_elapsed_ns,
        "stage": stage,
    }


def _config_for(max_updates: int, learning_rate_label: str) -> object:
    from hswm.experiments.swm0w_s2s_training import S2STrainingConfig

    return S2STrainingConfig(
        seed=INITIALIZER_SEED,
        max_updates=max_updates,
        learning_rate=float(learning_rate_label),
        beta1=BETA1,
        beta2=BETA2,
        epsilon=EPSILON,
        gradient_clip=GRADIENT_CLIP,
        patience=PATIENCE,
        min_delta=MIN_DELTA,
    )


def run_pilot(
    *,
    task_generator: Callable[..., object] | None = None,
    fitter: Callable[..., object] | None = None,
    replayer: Callable[[object], object] | None = None,
    clock_ns: Callable[[], int] = time.monotonic_ns,
    peak_rss_kib: Callable[[], int] = _peak_rss_kib,
    environment: Mapping[str, Any] | None = None,
    checkpoint: Callable[[Mapping[str, Any]], None] | None = None,
    selector: Callable[
        [Sequence[Mapping[str, Any]]], tuple[dict[str, Any], ...]
    ] = select_learning_rates,
) -> dict[str, Any]:
    """Execute the fixed pilot once and return a canonical artifact tree.

    Dependencies are injectable only to make boundary tests fast.  The public
    CLI exposes no roster, seed, optimizer, split, or threshold override.
    """

    if task_generator is None:
        from hswm.experiments.swm0w_s2s_family import generate_task

        task_generator = generate_task
    if fitter is None or replayer is None:
        from hswm.experiments.swm0w_s2s_training import (
            fit_task_operator,
            replay_optimization,
        )

        fitter = fit_task_operator if fitter is None else fitter
        replayer = replay_optimization if replayer is None else replayer
    from hswm.experiments.swm0w_s2s_operator import S2SArm

    task_bindings: list[dict[str, Any]] = []
    prepared: dict[int, tuple[object, tuple[object, ...], tuple[object, ...]]] = {}
    task_runtime: list[dict[str, Any]] = []
    stage1_cells: list[dict[str, Any]] = []
    stage2_cells: list[dict[str, Any]] = []
    runtime_cells: list[dict[str, Any]] = []
    selections: tuple[dict[str, Any], ...] = ()
    admission: dict[str, Any] | None = None
    environment_was_injected = environment is not None
    observed_environment: Mapping[str, Any] | None = environment

    def build(
        terminal_status: str,
        reason_code: str,
        *,
        error: BaseException | None = None,
    ) -> dict[str, Any]:
        deterministic = _deterministic_receipt(
            environment=observed_environment,
            task_bindings=task_bindings,
            stage1_cells=stage1_cells,
            stage2_cells=stage2_cells,
            selections=selections,
        )
        runtime = _runtime_report(
            terminal_status=terminal_status,
            reason_code=reason_code,
            task_preparation=task_runtime,
            cell_runtime=runtime_cells,
            admission=admission,
            error=error,
        )
        return _artifact(deterministic, runtime)

    def save_progress(reason_code: str) -> None:
        if checkpoint is not None:
            checkpoint(build(TERMINAL_VOID, reason_code))

    try:
        if observed_environment is None:
            observed_environment = numeric_environment_payload()
        canonical_sha256(observed_environment)
        if not environment_was_injected:
            _require_public_workflow_environment(observed_environment)
        save_progress("ENVIRONMENT_BOUND_RUN_IN_PROGRESS")

        for draw_index in TASK_DRAW_INDICES:
            started = clock_ns()
            task = task_generator(
                external_seed=EXTERNAL_SEED,
                draw_index=draw_index,
            )
            if getattr(task, "draw_index", None) != draw_index:
                raise SWM0WS2SPilotError("task generator returned the wrong draw")
            train_cases = tuple(task.iter_cases("train"))
            dev_cases = tuple(task.iter_cases("dev"))
            ended = clock_ns()
            if type(started) is not int or type(ended) is not int or ended < started:
                raise SWM0WS2SPilotError("task preparation clock is non-monotonic")
            binding = _task_binding(task)
            expected_binding = (
                EXPECTED_TASK_MANIFEST_SHA256S[draw_index],
                EXPECTED_STRUCTURAL_TARGET_SHA256S[draw_index],
                EXPECTED_STRUCTURAL_TASK_SHA256S[draw_index],
                EXPECTED_SEED_COMMITMENT_SHA256,
            )
            observed_binding = (
                binding["manifest_sha256"],
                binding["structural_target_sha256"],
                binding["structural_task_sha256"],
                binding["seed_commitment_sha256"],
            )
            if observed_binding != expected_binding:
                raise SWM0WS2SPilotError("public task roster hash drifted")
            task_runtime_record = {
                "draw_index": draw_index,
                "elapsed_ns": ended - started,
                "peak_rss_kib_after": peak_rss_kib(),
            }
            task_bindings.append(binding)
            prepared[draw_index] = (task, train_cases, dev_cases)
            task_runtime.append(task_runtime_record)
            save_progress("TASK_PREPARATION_IN_PROGRESS")

        if _task_batch_sha256(task_bindings) != EXPECTED_TASK_BATCH_SHA256:
            raise SWM0WS2SPilotError("public task batch SHA drifted")

        for stage, max_updates, destination in (
            (STAGE1_NAME, STAGE1_MAX_UPDATES, stage1_cells),
            (STAGE2_NAME, STAGE2_MAX_UPDATES, stage2_cells),
        ):
            if stage == STAGE2_NAME:
                if len(stage1_cells) != EXPECTED_CELL_COUNT:
                    raise SWM0WS2SPilotError("stage one roster is incomplete")
                stage1_total_ns = sum(
                    cell["fit_and_replay_elapsed_ns"]
                    for cell in runtime_cells
                    if cell["stage"] == STAGE1_NAME
                    and cell["exit_status"] == "COMPLETED"
                )
                projected_ns = stage1_total_ns * PROJECTION_MULTIPLIER
                admission = {
                    "admitted": projected_ns <= ADMISSION_LIMIT_NS,
                    "admission_limit_ns": ADMISSION_LIMIT_NS,
                    "integer_projection_multiplier": PROJECTION_MULTIPLIER,
                    "projected_stage2_fit_and_replay_ns": projected_ns,
                    "stage1_fit_and_replay_elapsed_ns_sum": stage1_total_ns,
                }
                if not admission["admitted"]:
                    return build(
                        TERMINAL_VOID,
                        "STAGE2_RUNTIME_ADMISSION_REJECTED",
                    )
                save_progress("RUNTIME_ADMISSION_EVALUATED")

            for roster_index, (
                draw_index,
                public_arm,
                learning_rate_label,
            ) in enumerate(fixed_roster()):
                key = _cell_key(
                    roster_index,
                    draw_index,
                    public_arm,
                    learning_rate_label,
                )
                task, train_cases, dev_cases = prepared[draw_index]
                config = _config_for(max_updates, learning_rate_label)
                arm = S2SArm(PUBLIC_TO_OPERATOR_ARM[public_arm])
                fit_started = clock_ns()
                fit_ended = fit_started
                replay_ended = fit_started
                phase = "FIT"
                try:
                    model = fitter(
                        task,
                        train_cases,
                        dev_cases,
                        arm=arm,
                        config=config,
                    )
                    fit_ended = clock_ns()
                    phase = "REPLAY"
                    replayed = replayer(model)
                    replay_ended = clock_ns()
                    phase = "VERIFY"
                    if any(
                        type(value) is not int
                        for value in (fit_started, fit_ended, replay_ended)
                    ) or not fit_started <= fit_ended <= replay_ended:
                        raise SWM0WS2SPilotError("cell clock is non-monotonic")
                    _require_exact_replay(model, replayed)
                    record = (
                        _throughput_cell_record(
                            model,
                            task_binding=task_bindings[draw_index],
                            cell_key=key,
                        )
                        if stage == STAGE1_NAME
                        else _full_cell_record(
                            model,
                            task_binding=task_bindings[draw_index],
                            cell_key=key,
                        )
                    )
                    runtime_record = _runtime_cell(
                        stage=stage,
                        cell_key=key,
                        fit_elapsed_ns=fit_ended - fit_started,
                        replay_elapsed_ns=replay_ended - fit_ended,
                        peak_rss_kib=peak_rss_kib(),
                        exit_status="COMPLETED",
                    )
                    destination.append(record)
                    runtime_cells.append(runtime_record)
                except Exception as error:
                    failed_at = clock_ns()
                    if phase == "FIT":
                        fit_elapsed = max(0, failed_at - fit_started)
                        replay_elapsed = 0
                    else:
                        fit_elapsed = max(0, fit_ended - fit_started)
                        replay_elapsed = max(0, failed_at - fit_ended)
                    runtime_cells.append(
                        _runtime_cell(
                            stage=stage,
                            cell_key=key,
                            fit_elapsed_ns=fit_elapsed,
                            replay_elapsed_ns=replay_elapsed,
                            peak_rss_kib=peak_rss_kib(),
                            exit_status="ERROR",
                            error=error,
                        )
                    )
                    raise
                save_progress(f"{stage}_IN_PROGRESS")

            if stage == STAGE1_NAME and len(stage1_cells) != EXPECTED_CELL_COUNT:
                raise SWM0WS2SPilotError("stage one did not cover the fixed roster")

        selections = selector(stage2_cells)
        return build(TERMINAL_COMPLETE, "FIXED_DEVELOPMENT_ROSTER_COMPLETE")
    except Exception as error:
        return build(TERMINAL_VOID, "EXECUTION_OR_INTEGRITY_FAILURE", error=error)


def _require_exact_keys(
    value: object, expected: set[str], name: str
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise SWM0WS2SPilotError(f"{name} keys drifted")
    if any(type(key) is not str for key in value):
        raise SWM0WS2SPilotError(f"{name} keys must be exact strings")
    return value


def _require_bound_hash(value: Mapping[str, Any], field: str, name: str) -> None:
    observed = _require_sha256(value.get(field), f"{name} {field}")
    unsigned = dict(value)
    del unsigned[field]
    if canonical_sha256(unsigned) != observed:
        raise SWM0WS2SPilotError(f"{name} self-hash mismatch")


def _validate_task_binding_list(value: object) -> list[dict[str, Any]]:
    if type(value) is not list or len(value) > len(TASK_DRAW_INDICES):
        raise SWM0WS2SPilotError("ordered task bindings are malformed")
    required = {
        "draw_index",
        "family_certificate_sha256",
        "family_definition_sha256",
        "manifest_sha256",
        "seed_commitment_sha256",
        "structural_target_sha256",
        "structural_task_sha256",
        "task_spec",
    }
    for draw_index, binding in enumerate(value):
        _require_exact_keys(binding, required, "task binding")
        if type(binding["draw_index"]) is not int or binding["draw_index"] != draw_index:
            raise SWM0WS2SPilotError("ordered task binding draw drifted")
        for field in required - {"draw_index", "task_spec"}:
            _require_sha256(binding[field], f"task binding {field}")
        if (
            binding["manifest_sha256"]
            != EXPECTED_TASK_MANIFEST_SHA256S[draw_index]
            or binding["structural_target_sha256"]
            != EXPECTED_STRUCTURAL_TARGET_SHA256S[draw_index]
            or binding["structural_task_sha256"]
            != EXPECTED_STRUCTURAL_TASK_SHA256S[draw_index]
            or binding["seed_commitment_sha256"]
            != EXPECTED_SEED_COMMITMENT_SHA256
        ):
            raise SWM0WS2SPilotError("ordered task binding golden drifted")
        if type(binding["task_spec"]) is not dict:
            raise SWM0WS2SPilotError("task binding spec is malformed")
        expected_task = _expected_public_task(draw_index)
        expected_binding = _task_binding(expected_task)
        if canonical_json(binding) != canonical_json(expected_binding):
            raise SWM0WS2SPilotError("task binding differs from regenerated public task")
    return value


def _validate_numeric_environment(value: object) -> dict[str, Any]:
    environment = _require_exact_keys(
        value,
        {
            "blas",
            "byteorder",
            "cpu",
            "numpy_version",
            "platform_release",
            "platform_system",
            "python_implementation",
            "python_version",
            "runner_arch",
            "runner_os",
            "simd",
            "source_commit",
            "thread_environment",
        },
        "numeric environment",
    )
    _require_exact_keys(
        environment["blas"],
        {"name", "openblas_configuration", "version"},
        "numeric environment BLAS",
    )
    _require_exact_keys(
        environment["cpu"],
        {"flags", "machine", "model_name", "vendor_id"},
        "numeric environment CPU",
    )
    _require_exact_keys(
        environment["simd"],
        {"baseline", "found", "not_found"},
        "numeric environment SIMD",
    )
    threads = _require_exact_keys(
        environment["thread_environment"],
        set(WORKFLOW_FIXED_ENVIRONMENT),
        "numeric thread environment",
    )
    if any(value is not None and type(value) is not str for value in threads.values()):
        raise SWM0WS2SPilotError("numeric thread environment value is malformed")
    for field in (
        "byteorder",
        "numpy_version",
        "platform_release",
        "platform_system",
        "python_implementation",
        "python_version",
    ):
        if type(environment[field]) is not str or not environment[field]:
            raise SWM0WS2SPilotError("numeric environment text is malformed")
    for field in ("runner_arch", "runner_os"):
        if environment[field] is not None and type(environment[field]) is not str:
            raise SWM0WS2SPilotError("numeric runner identity is malformed")
    for field in ("flags", "machine", "model_name", "vendor_id"):
        if environment["cpu"][field] is not None and type(
            environment["cpu"][field]
        ) is not str:
            raise SWM0WS2SPilotError("numeric CPU identity is malformed")
    for field in ("name", "openblas_configuration", "version"):
        if type(environment["blas"][field]) is not str:
            raise SWM0WS2SPilotError("numeric BLAS identity is malformed")
    for field in ("baseline", "found", "not_found"):
        values = environment["simd"][field]
        if type(values) is not list or any(type(item) is not str for item in values):
            raise SWM0WS2SPilotError("numeric SIMD identity is malformed")
    source_commit = environment["source_commit"]
    if source_commit != "UNSPECIFIED_DEVELOPMENT_SOURCE" and (
        type(source_commit) is not str
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise SWM0WS2SPilotError("numeric source commit is malformed")
    return environment


def _validate_runtime_cell_prefix(value: object) -> list[dict[str, Any]]:
    if type(value) is not list or len(value) > 2 * EXPECTED_CELL_COUNT:
        raise SWM0WS2SPilotError("runtime cell telemetry is malformed")
    stage_counts = {STAGE1_NAME: 0, STAGE2_NAME: 0}
    entered_stage2 = False
    error_seen = False
    runtime_cell_keys = {
        "draw_index",
        "error_class",
        "error_message",
        "exit_status",
        "fit_and_replay_elapsed_ns",
        "fit_elapsed_ns",
        "learning_rate_binary64_hex",
        "learning_rate_decimal",
        "operator_arm",
        "peak_rss_kib_after",
        "public_arm",
        "replay_elapsed_ns",
        "roster_index",
        "stage",
    }
    for item in value:
        if error_seen:
            raise SWM0WS2SPilotError("runtime continues after a cell error")
        _require_exact_keys(item, runtime_cell_keys, "runtime cell")
        stage = item.get("stage")
        if stage not in stage_counts:
            raise SWM0WS2SPilotError("runtime cell stage drifted")
        if stage == STAGE2_NAME:
            if stage_counts[STAGE1_NAME] != EXPECTED_CELL_COUNT:
                raise SWM0WS2SPilotError("runtime stage two began before stage one ended")
            entered_stage2 = True
        elif entered_stage2:
            raise SWM0WS2SPilotError("runtime stages are out of order")
        roster_index = stage_counts[stage]
        if roster_index >= EXPECTED_CELL_COUNT:
            raise SWM0WS2SPilotError("runtime stage exceeds fixed roster")
        draw, public_arm, learning_rate_label = fixed_roster()[roster_index]
        if (
            type(item.get("roster_index")) is not int
            or item["roster_index"] != roster_index
            or type(item.get("draw_index")) is not int
            or item["draw_index"] != draw
            or item.get("public_arm") != public_arm
            or item.get("operator_arm") != PUBLIC_TO_OPERATOR_ARM[public_arm]
            or item.get("learning_rate_decimal") != learning_rate_label
            or item.get("learning_rate_binary64_hex")
            != LEARNING_RATE_HEX[learning_rate_label]
            or item.get("exit_status") not in {"COMPLETED", "ERROR"}
        ):
            raise SWM0WS2SPilotError("runtime cell roster drifted")
        for field in (
            "fit_elapsed_ns",
            "replay_elapsed_ns",
            "fit_and_replay_elapsed_ns",
            "peak_rss_kib_after",
        ):
            if type(item.get(field)) is not int or item[field] < 0:
                raise SWM0WS2SPilotError("runtime integer telemetry is malformed")
        if item["fit_and_replay_elapsed_ns"] != (
            item["fit_elapsed_ns"] + item["replay_elapsed_ns"]
        ):
            raise SWM0WS2SPilotError("runtime elapsed-time accounting drifted")
        if item["exit_status"] == "COMPLETED":
            if item["error_class"] is not None or item["error_message"] is not None:
                raise SWM0WS2SPilotError("completed runtime cell exposes an error")
        elif (
            type(item["error_class"]) is not str
            or not item["error_class"]
            or type(item["error_message"]) is not str
        ):
            raise SWM0WS2SPilotError("failed runtime cell lacks its exact error")
        stage_counts[stage] += 1
        error_seen = item["exit_status"] == "ERROR"
    return value


def validate_pilot_artifact(value: object) -> dict[str, Any]:
    """Strictly validate one generated pilot artifact and all nested hashes."""

    artifact = _require_exact_keys(
        value,
        {
            "artifact_sha256",
            "deterministic_receipt",
            "runtime_telemetry",
            "schema_version",
            "scientific_status",
            "terminal_status",
            "verdict",
        },
        "pilot artifact",
    )
    if (
        artifact["schema_version"] != PILOT_VERSION
        or artifact["scientific_status"] != SCIENTIFIC_STATUS
        or artifact["verdict"] != NO_EFFICACY_VERDICT
        or artifact["terminal_status"] not in {TERMINAL_COMPLETE, TERMINAL_VOID}
    ):
        raise SWM0WS2SPilotError("pilot artifact identity drifted")
    _require_bound_hash(artifact, "artifact_sha256", "pilot artifact")

    deterministic = _require_exact_keys(
        artifact["deterministic_receipt"],
        {
            "completion",
            "contract",
            "contract_sha256",
            "deterministic_receipt_sha256",
            "execution_bound_numeric_environment",
            "execution_bound_numeric_environment_sha256",
            "future_confirmatory_exclusion",
            "ordered_stage1_cell_receipts",
            "ordered_stage2_cell_receipts",
            "ordered_task_bindings",
            "schema_version",
            "scientific_status",
            "selection_status",
            "selections",
            "task_batch_sha256",
            "verdict",
        },
        "deterministic receipt",
    )
    _require_bound_hash(
        deterministic,
        "deterministic_receipt_sha256",
        "deterministic receipt",
    )
    if (
        deterministic["schema_version"] != DETERMINISTIC_RECEIPT_VERSION
        or deterministic["scientific_status"] != SCIENTIFIC_STATUS
        or deterministic["verdict"] != NO_EFFICACY_VERDICT
        or deterministic["contract_sha256"] != PILOT_CONTRACT_SHA256
        or canonical_json(deterministic["contract"])
        != canonical_json(pilot_contract_payload())
    ):
        raise SWM0WS2SPilotError("deterministic receipt contract drifted")
    environment = deterministic["execution_bound_numeric_environment"]
    environment_sha = deterministic[
        "execution_bound_numeric_environment_sha256"
    ]
    if environment is None:
        if environment_sha is not None:
            raise SWM0WS2SPilotError("absent environment has a hash")
    else:
        _validate_numeric_environment(environment)
        if _require_sha256(
            environment_sha, "numeric environment SHA"
        ) != canonical_sha256(environment):
            raise SWM0WS2SPilotError("numeric environment binding drifted")

    task_bindings = _validate_task_binding_list(
        deterministic["ordered_task_bindings"]
    )
    expected_batch_sha256 = (
        _task_batch_sha256(task_bindings)
        if len(task_bindings) == len(TASK_DRAW_INDICES)
        else None
    )
    if deterministic["task_batch_sha256"] != expected_batch_sha256 or (
        expected_batch_sha256 is not None
        and expected_batch_sha256 != EXPECTED_TASK_BATCH_SHA256
    ):
        raise SWM0WS2SPilotError("deterministic task batch binding drifted")
    stage1 = deterministic["ordered_stage1_cell_receipts"]
    stage2 = deterministic["ordered_stage2_cell_receipts"]
    if type(stage1) is not list or type(stage2) is not list:
        raise SWM0WS2SPilotError("artifact cell receipts must be exact lists")
    _validate_cell_prefix(stage1, stage=STAGE1_NAME)
    _validate_cell_prefix(stage2, stage=STAGE2_NAME)
    if stage2 and len(stage1) != EXPECTED_CELL_COUNT:
        raise SWM0WS2SPilotError("stage two exists before complete stage one")
    if (stage1 or stage2) and len(task_bindings) != len(TASK_DRAW_INDICES):
        raise SWM0WS2SPilotError("cell receipts lack all task bindings")

    expected_exclusion = {
        "exclusion_scope": "EXACT_PILOT_SEED_AND_DRAW_PROVENANCE_ONLY",
        "excluded_external_seed_sha256_hex": EXTERNAL_SEED_SHA256_HEX,
        "excluded_ordered_task_draw_indices": list(TASK_DRAW_INDICES),
        "future_semantic_collision_policy": (
            "RETAIN_AND_DISCLOSE_NEVER_FILTER_OR_REROLL"
        ),
        "recorded_pilot_ordered_task_manifest_sha256s": [
            task["manifest_sha256"] for task in task_bindings
        ],
        "recorded_pilot_ordered_structural_task_sha256s": [
            task["structural_task_sha256"] for task in task_bindings
        ],
        "required": True,
    }
    if canonical_json(deterministic["future_confirmatory_exclusion"]) != canonical_json(
        expected_exclusion
    ):
        raise SWM0WS2SPilotError("future confirmatory exclusion drifted")

    selections = deterministic["selections"]
    complete = (
        len(stage1) == EXPECTED_CELL_COUNT
        and len(stage2) == EXPECTED_CELL_COUNT
        and type(selections) is list
        and len(selections) == len(PUBLIC_ARMS)
    )
    if complete:
        expected_selections = select_learning_rates(stage2)
        if canonical_json(selections) != canonical_json(expected_selections):
            raise SWM0WS2SPilotError("development selections drifted")
        if (
            deterministic["completion"] != "COMPLETE_FIXED_DEVELOPMENT_ROSTER"
            or deterministic["selection_status"]
            != "COMPLETE_DEVELOPMENT_SELECTION"
        ):
            raise SWM0WS2SPilotError("complete receipt status drifted")
    elif (
        selections != []
        or deterministic["completion"] != "INCOMPLETE_NO_SELECTION"
        or deterministic["selection_status"] != NO_SELECTION
    ):
        raise SWM0WS2SPilotError("incomplete receipt exposed a selection")

    runtime = _require_exact_keys(
        artifact["runtime_telemetry"],
        {
            "admission",
            "cell_runtime",
            "error",
            "reason_code",
            "runtime_telemetry_sha256",
            "schema_version",
            "task_preparation_runtime",
            "telemetry_is_nondeterministic",
            "terminal_status",
        },
        "runtime telemetry",
    )
    _require_bound_hash(runtime, "runtime_telemetry_sha256", "runtime telemetry")
    runtime_cells = _validate_runtime_cell_prefix(runtime["cell_runtime"])
    if (
        runtime["schema_version"] != RUNTIME_TELEMETRY_VERSION
        or runtime["telemetry_is_nondeterministic"] is not True
        or runtime["terminal_status"] != artifact["terminal_status"]
        or runtime["reason_code"]
        not in {
            "ENVIRONMENT_BOUND_RUN_IN_PROGRESS",
            "EXECUTION_OR_INTEGRITY_FAILURE",
            "FIXED_DEVELOPMENT_ROSTER_COMPLETE",
            "FULL_DEVELOPMENT_FIT_AND_REPLAY_IN_PROGRESS",
            "RUN_NOT_COMPLETED",
            "RUNTIME_ADMISSION_EVALUATED",
            "STAGE2_RUNTIME_ADMISSION_REJECTED",
            "TASK_PREPARATION_IN_PROGRESS",
            "THROUGHPUT_FIT_AND_REPLAY_IN_PROGRESS",
        }
    ):
        raise SWM0WS2SPilotError("runtime telemetry identity drifted")
    completed_stage1 = sum(
        item["stage"] == STAGE1_NAME and item["exit_status"] == "COMPLETED"
        for item in runtime_cells
    )
    completed_stage2 = sum(
        item["stage"] == STAGE2_NAME and item["exit_status"] == "COMPLETED"
        for item in runtime_cells
    )
    if completed_stage1 != len(stage1) or completed_stage2 != len(stage2):
        raise SWM0WS2SPilotError("runtime and deterministic cell coverage drifted")
    runtime_error = runtime["error"]
    if runtime_error is not None:
        _require_exact_keys(runtime_error, {"class", "message"}, "runtime error")
        if (
            type(runtime_error["class"]) is not str
            or not runtime_error["class"]
            or type(runtime_error["message"]) is not str
        ):
            raise SWM0WS2SPilotError("runtime error is malformed")
    if (runtime_error is not None) != (
        runtime["reason_code"] == "EXECUTION_OR_INTEGRITY_FAILURE"
    ):
        raise SWM0WS2SPilotError("runtime reason and terminal error disagree")
    failed_cells = [
        item for item in runtime_cells if item["exit_status"] == "ERROR"
    ]
    if failed_cells and (
        runtime_error is None
        or runtime_error["class"] != failed_cells[0]["error_class"]
        or runtime_error["message"] != failed_cells[0]["error_message"]
    ):
        raise SWM0WS2SPilotError("runtime cell and terminal errors disagree")
    task_runtime = runtime["task_preparation_runtime"]
    if type(task_runtime) is not list or len(task_runtime) != len(task_bindings):
        raise SWM0WS2SPilotError("task preparation telemetry drifted")
    for draw_index, item in enumerate(task_runtime):
        _require_exact_keys(
            item,
            {"draw_index", "elapsed_ns", "peak_rss_kib_after"},
            "task preparation runtime",
        )
        if (
            type(item.get("draw_index")) is not int
            or item["draw_index"] != draw_index
            or type(item.get("elapsed_ns")) is not int
            or item["elapsed_ns"] < 0
            or type(item.get("peak_rss_kib_after")) is not int
            or item["peak_rss_kib_after"] < 0
        ):
            raise SWM0WS2SPilotError("task preparation telemetry is malformed")
    admission = runtime["admission"]
    if admission is not None:
        expected_admission_keys = {
            "admitted",
            "admission_limit_ns",
            "integer_projection_multiplier",
            "projected_stage2_fit_and_replay_ns",
            "stage1_fit_and_replay_elapsed_ns_sum",
        }
        _require_exact_keys(admission, expected_admission_keys, "runtime admission")
        stage1_elapsed = sum(
            item["fit_and_replay_elapsed_ns"]
            for item in runtime_cells
            if item["stage"] == STAGE1_NAME and item["exit_status"] == "COMPLETED"
        )
        projected = stage1_elapsed * PROJECTION_MULTIPLIER
        if (
            type(admission["admitted"]) is not bool
            or any(
                type(admission[field]) is not int
                for field in expected_admission_keys - {"admitted"}
            )
            or admission["admission_limit_ns"] != ADMISSION_LIMIT_NS
            or admission["integer_projection_multiplier"]
            != PROJECTION_MULTIPLIER
            or admission["stage1_fit_and_replay_elapsed_ns_sum"] != stage1_elapsed
            or admission["projected_stage2_fit_and_replay_ns"] != projected
            or admission["admitted"] != (projected <= ADMISSION_LIMIT_NS)
        ):
            raise SWM0WS2SPilotError("runtime admission calculation drifted")

    task_count = len(task_bindings)
    stage1_count = len(stage1)
    stage2_count = len(stage2)
    if environment is None:
        reachable_prefix = (
            task_count == 0
            and stage1_count == 0
            and stage2_count == 0
            and admission is None
        )
    elif task_count < len(TASK_DRAW_INDICES):
        reachable_prefix = (
            stage1_count == 0 and stage2_count == 0 and admission is None
        )
    elif stage1_count < EXPECTED_CELL_COUNT:
        reachable_prefix = stage2_count == 0 and admission is None
    elif admission is None:
        reachable_prefix = stage2_count == 0
    elif admission["admitted"] is False:
        reachable_prefix = stage2_count == 0
    else:
        reachable_prefix = True
    if not reachable_prefix:
        raise SWM0WS2SPilotError("runtime state is not a reachable pilot prefix")

    reason = runtime["reason_code"]
    if reason == "RUN_NOT_COMPLETED":
        reason_state_valid = (
            artifact["terminal_status"] == TERMINAL_VOID
            and environment is None
            and task_count == 0
            and stage1_count == 0
            and stage2_count == 0
            and admission is None
        )
    elif reason == "ENVIRONMENT_BOUND_RUN_IN_PROGRESS":
        reason_state_valid = (
            artifact["terminal_status"] == TERMINAL_VOID
            and environment is not None
            and task_count == 0
            and stage1_count == 0
            and stage2_count == 0
            and admission is None
        )
    elif reason == "TASK_PREPARATION_IN_PROGRESS":
        reason_state_valid = (
            artifact["terminal_status"] == TERMINAL_VOID
            and environment is not None
            and 1 <= task_count <= len(TASK_DRAW_INDICES)
            and stage1_count == 0
            and stage2_count == 0
            and admission is None
        )
    elif reason == f"{STAGE1_NAME}_IN_PROGRESS":
        reason_state_valid = (
            artifact["terminal_status"] == TERMINAL_VOID
            and environment is not None
            and task_count == len(TASK_DRAW_INDICES)
            and 1 <= stage1_count <= EXPECTED_CELL_COUNT
            and stage2_count == 0
            and admission is None
        )
    elif reason == "RUNTIME_ADMISSION_EVALUATED":
        reason_state_valid = (
            artifact["terminal_status"] == TERMINAL_VOID
            and environment is not None
            and task_count == len(TASK_DRAW_INDICES)
            and stage1_count == EXPECTED_CELL_COUNT
            and stage2_count == 0
            and admission is not None
            and admission["admitted"] is True
        )
    elif reason == f"{STAGE2_NAME}_IN_PROGRESS":
        reason_state_valid = (
            artifact["terminal_status"] == TERMINAL_VOID
            and environment is not None
            and task_count == len(TASK_DRAW_INDICES)
            and stage1_count == EXPECTED_CELL_COUNT
            and 1 <= stage2_count <= EXPECTED_CELL_COUNT
            and admission is not None
            and admission["admitted"] is True
        )
    elif reason == "STAGE2_RUNTIME_ADMISSION_REJECTED":
        reason_state_valid = (
            artifact["terminal_status"] == TERMINAL_VOID
            and environment is not None
            and task_count == len(TASK_DRAW_INDICES)
            and stage1_count == EXPECTED_CELL_COUNT
            and stage2_count == 0
            and admission is not None
            and admission["admitted"] is False
        )
    elif reason == "EXECUTION_OR_INTEGRITY_FAILURE":
        reason_state_valid = (
            artifact["terminal_status"] == TERMINAL_VOID
            and runtime_error is not None
            and (admission is None or admission["admitted"] is True)
        )
    else:
        reason_state_valid = (
            reason == "FIXED_DEVELOPMENT_ROSTER_COMPLETE"
            and artifact["terminal_status"] == TERMINAL_COMPLETE
            and complete
            and admission is not None
            and admission["admitted"] is True
        )
    if not reason_state_valid:
        raise SWM0WS2SPilotError("runtime reason does not match pilot state")

    if artifact["terminal_status"] == TERMINAL_COMPLETE:
        if (
            not complete
            or reason != "FIXED_DEVELOPMENT_ROSTER_COMPLETE"
            or runtime["error"] is not None
            or admission is None
            or admission["admitted"] is not True
            or len(runtime_cells) != 2 * EXPECTED_CELL_COUNT
            or any(item["exit_status"] != "COMPLETED" for item in runtime_cells)
        ):
            raise SWM0WS2SPilotError("complete artifact runtime state drifted")
    elif complete or deterministic["selection_status"] != NO_SELECTION:
        raise SWM0WS2SPilotError("void artifact exposed a complete selection")
    return artifact


def parse_pilot_artifact_bytes(value: bytes) -> dict[str, Any]:
    """Parse canonical newline-terminated JSON and validate every binding."""

    if type(value) is not bytes:
        raise SWM0WS2SPilotError("pilot artifact bytes must be exact bytes")

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise SWM0WS2SPilotError("pilot artifact contains a duplicate key")
            result[key] = item
        return result

    def reject_float(_: str) -> object:
        raise SWM0WS2SPilotError("pilot artifact JSON cannot contain numeric floats")

    try:
        parsed = json.loads(
            value.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_float=reject_float,
            parse_constant=reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SWM0WS2SPilotError("pilot artifact is not canonical JSON") from exc
    if type(parsed) is not dict or value != (
        canonical_json(parsed) + "\n"
    ).encode("utf-8"):
        raise SWM0WS2SPilotError("pilot artifact bytes are not canonical")
    return validate_pilot_artifact(parsed)


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    target = Path(path)
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise SWM0WS2SPilotError("output must be a regular non-symlink path")
    if not target.parent.is_dir():
        raise SWM0WS2SPilotError("output parent directory does not exist")
    payload = (canonical_json(value) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fixed SWM-0W-S2S train/dev-only development pilot. "
            "There are no roster or scientific-threshold overrides."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--initialize-void",
        action="store_true",
        help="write only the pre-run DEVELOPMENT_RUNTIME_VOID marker",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    initial = initial_void_artifact()
    validate_pilot_artifact(initial)
    _atomic_write(args.output, initial)
    if args.initialize_void:
        return 0

    artifact = run_pilot(
        checkpoint=lambda value: _atomic_write(
            args.output, validate_pilot_artifact(value)
        )
    )
    validate_pilot_artifact(artifact)
    _atomic_write(args.output, artifact)
    summary = {
        "artifact_sha256": artifact["artifact_sha256"],
        "deterministic_receipt_sha256": artifact["deterministic_receipt"][
            "deterministic_receipt_sha256"
        ],
        "output": str(args.output),
        "terminal_status": artifact["terminal_status"],
        "verdict": NO_EFFICACY_VERDICT,
    }
    print(canonical_json(summary))
    return 0 if artifact["terminal_status"] == TERMINAL_COMPLETE else 2


__all__ = [
    "ADMISSION_LIMIT_MINUTES",
    "ADMISSION_LIMIT_NS",
    "BETA1",
    "BETA2",
    "EXPECTED_CELL_COUNT",
    "EXPECTED_SEED_COMMITMENT_SHA256",
    "EXPECTED_STRUCTURAL_TARGET_SHA256S",
    "EXPECTED_STRUCTURAL_TASK_SHA256S",
    "EXPECTED_TASK_BATCH_SHA256",
    "EXPECTED_TASK_MANIFEST_SHA256S",
    "EXTERNAL_SEED",
    "EXTERNAL_SEED_ASCII",
    "EXTERNAL_SEED_SHA256_HEX",
    "GRADIENT_CLIP",
    "INITIALIZER_SEED",
    "LEARNING_RATE_HEX",
    "LEARNING_RATE_LABELS",
    "MIN_DELTA",
    "NO_EFFICACY_VERDICT",
    "NO_SELECTION",
    "PATIENCE",
    "PILOT_CONTRACT_SHA256",
    "PUBLIC_ARMS",
    "PUBLIC_TO_OPERATOR_ARM",
    "SCIENTIFIC_STATUS",
    "STAGE1_MAX_UPDATES",
    "STAGE2_MAX_UPDATES",
    "SWM0WS2SPilotError",
    "TASK_DRAW_INDICES",
    "TERMINAL_COMPLETE",
    "TERMINAL_VOID",
    "WORKFLOW_TIMEOUT_MINUTES",
    "canonical_json",
    "canonical_sha256",
    "fixed_roster",
    "initial_void_artifact",
    "main",
    "numeric_environment_payload",
    "parse_pilot_artifact_bytes",
    "pilot_contract_payload",
    "run_pilot",
    "select_learning_rates",
    "validate_pilot_artifact",
]


if __name__ == "__main__":
    raise SystemExit(main())
