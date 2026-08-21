"""Deterministic numeric-process boundary for the SWM-0W-S2S gate.

This module is intentionally narrower than the confirmatory control plane.  It
does not acquire randomness, inspect Git or GitHub, read clocks or environment
state, choose deadlines, write artifacts, or issue an evidence verdict.  The
TypeScript/Effect shell supplies one already-derived 32-byte seed and the
pilot-adopted numeric protocol configuration.  Python owns the canonical
numeric candidate bytes and nothing outside that numeric boundary.

Confirmation has one irreversible phase boundary: all twenty tasks times all
three arms are fitted and exactly replayed before the first test partition is
materialized.  Adjudication reconstructs archived learned models and reruns
the complete test/integrity/reducer path without calling either optimizer.

Every wire document is ASCII-only canonical UTF-8 JSON followed by exactly one
LF.  Expected failures are typed and CLI failures write no bytes to stdout, so
a failed process cannot be mistaken for a partial ``numeric_candidate.json``.

Scientific status: ``NUMERIC_CANDIDATE_ONLY_UNJUDGED``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import sys
from typing import Any, BinaryIO, Callable, Mapping, Sequence

from hswm.experiments import swm0w_s2s_protocol as candidate_protocol
from hswm.experiments.swm0w_s2s_family import (
    TaskBatchV2,
    TaskSpecV2,
    generate_task_batch,
)
from hswm.experiments.swm0w_s2s_operator import (
    ALL_ARMS,
    S2SArm,
    canonical_json,
    canonical_sha256,
)
from hswm.experiments.swm0w_s2s_training import (
    S2STrainingConfig,
    fit_task_operator,
    replay_optimization,
)


CONFIRM_REQUEST_VERSION = "hswm-swm0w-s2s-numeric-confirm-request/v1"
NUMERIC_CANDIDATE_VERSION = "hswm-swm0w-s2s-numeric-candidate/v1"
NUMERIC_ADJUDICATION_VERSION = "hswm-swm0w-s2s-numeric-adjudication/v1"
NUMERIC_ERROR_VERSION = "hswm-swm0w-s2s-numeric-error/v1"
GOLDEN_VECTOR_VERSION = "hswm-swm0w-s2s-numeric-golden-vector/v1"
SCIENTIFIC_STATUS = "NUMERIC_CANDIDATE_ONLY_UNJUDGED"
NUMERIC_CANDIDATE_STATUS = "NUMERIC_CANDIDATE_COMPLETE_AWAITING_EXTERNAL_ADJUDICATION"
NUMERIC_REPLAY_STATUS = "NUMERIC_REPLAY_VALIDATED_CANDIDATE_ONLY"
CLAIM_BOUNDARY = "NUMERIC_ONLY_NO_EVIDENCE_VERDICT_OR_CHRONOLOGY_CLAIM"
CANONICAL_ENCODING = "ASCII_CANONICAL_UTF8_JSON_PLUS_SINGLE_LF"

TASK_COUNT = candidate_protocol.TASK_COUNT
ARM_COUNT = len(ALL_ARMS)
CELL_COUNT = TASK_COUNT * ARM_COUNT
FIT_EXECUTION_COUNT = CELL_COUNT
REPLAY_EXECUTION_COUNT = CELL_COUNT
OPTIMIZER_EXECUTION_COUNT = FIT_EXECUTION_COUNT + REPLAY_EXECUTION_COUNT
TEST_EVALUATION_COUNT = TASK_COUNT
TEST_WORLD_COUNT_PER_TASK = candidate_protocol.TEST_WORLD_COUNT
DOMAIN_WORLD_COUNT_PER_TASK = candidate_protocol.DOMAIN_WORLD_COUNT
SCORE_VARIANT_COUNT = len(candidate_protocol.ScoreVariant)
TEST_MATERIALIZATION_POLICY = "AFTER_ALL_60_FIT_AND_EXACT_REPLAY_CELLS"
COMPACT_PHRASE_POLICY = "DS_SELECTED_CONFIGURATION_NEVER_BEAT_EPOCH_ZERO"

ADOPTED_PROTOCOL_CONFIG_RECEIPT_SHA256 = (
    "a8f62d3811e42fbf3bc0dc82a52a17f3fa27b4dfa1d43aa9e7ea302a142c40bb"
)
ADOPTED_PROTOCOL_CONFIG_DOCUMENT_SHA256 = (
    "315dad65a8882c4b7c5fb73d295df28b58b0696e25b1b790a342b40ced8d10c4"
)
PILOT_EXCLUDED_SEED_COMMITMENT_SHA256 = (
    "0370316c9f9388a5f37ba26c934a5efaed08b828789f392bf702da600cc88dce"
)

# Public cross-language generator vector.  It is test material, not a
# confirmatory randomness source or chronology claim.
GOLDEN_EXTERNAL_SEED_HEX = (
    "552e51d2ff75cb7c5df5b55a166aba12a277c2813bbdd69bc825286e7c26b6f0"
)
GOLDEN_SEED_COMMITMENT_SHA256 = (
    "8123f630f66f924966af5071c89ce175f7fcc755b0b92b58acc3f445167f73c1"
)
GOLDEN_TASK_BATCH_SHA256 = (
    "2aa00f3696509ee999407ac82dbbdf22d53940dce359019170a88359dbb63ddc"
)
GOLDEN_DRAW0_MANIFEST_SHA256 = (
    "f5bc6533dd422326c3ec33633e2529354b4466d238ae5922a252ef5fed1c928f"
)
GOLDEN_CONFIRM_REQUEST_SELF_SHA256 = (
    "16e4965054165863add0395397cbf3d68d1f3d472b7fc303e40056855368b1d1"
)
GOLDEN_CONFIRM_REQUEST_DOCUMENT_SHA256 = (
    "294eb438fe042238bbe725d0473765f3634eb57876e5cae4807915db66034237"
)
GOLDEN_VECTOR_RECEIPT_SHA256 = (
    "c6f487a192177adf654fada8dca9b8768391fb9f2e39a6b50214db557439618f"
)
GOLDEN_VECTOR_DOCUMENT_SHA256 = (
    "ae30799cc30eb146f69b8884aac1c137ec3fc34e835bcb009351f3889697cf43"
)

_HEX = frozenset("0123456789abcdef")


class NumericOracleErrorCode(str, Enum):
    """Stable expected-failure vocabulary for the process adapter."""

    INVALID_CANONICAL_DOCUMENT = "INVALID_CANONICAL_DOCUMENT"
    INVALID_CONFIRM_REQUEST = "INVALID_CONFIRM_REQUEST"
    NON_ADOPTED_PROTOCOL_CONFIG = "NON_ADOPTED_PROTOCOL_CONFIG"
    TASK_BATCH_GENERATION_FAILED = "TASK_BATCH_GENERATION_FAILED"
    FIT_REPLAY_FAILED = "FIT_REPLAY_FAILED"
    TEST_EVALUATION_FAILED = "TEST_EVALUATION_FAILED"
    CANDIDATE_FINALIZATION_FAILED = "CANDIDATE_FINALIZATION_FAILED"
    INVALID_NUMERIC_CANDIDATE = "INVALID_NUMERIC_CANDIDATE"
    ADJUDICATION_REPLAY_MISMATCH = "ADJUDICATION_REPLAY_MISMATCH"
    INVALID_NUMERIC_ADJUDICATION = "INVALID_NUMERIC_ADJUDICATION"
    INVALID_CLI_INVOCATION = "INVALID_CLI_INVOCATION"
    INTERNAL_NUMERIC_FAILURE = "INTERNAL_NUMERIC_FAILURE"


class SWM0WS2SNumericOracleError(ValueError):
    """A typed, fail-closed numeric-oracle rejection."""

    def __init__(
        self,
        code: NumericOracleErrorCode,
        stage: str,
        detail: str,
    ) -> None:
        if type(code) is not NumericOracleErrorCode:
            raise TypeError("numeric oracle error code requires exact enum")
        if type(stage) is not str or not stage or not stage.isascii():
            raise TypeError("numeric oracle error stage requires nonempty ASCII")
        if type(detail) is not str or not detail:
            raise TypeError("numeric oracle error detail requires nonempty string")
        super().__init__(detail)
        self.code = code
        self.stage = stage


def _fail(
    code: NumericOracleErrorCode,
    stage: str,
    detail: str,
    *,
    cause: BaseException | None = None,
) -> None:
    error = SWM0WS2SNumericOracleError(code, stage, detail)
    if cause is None:
        raise error
    raise error from cause


def _require_exact_json_tree(value: object, name: str) -> None:
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str or not key.isascii():
                _fail(
                    NumericOracleErrorCode.INVALID_CANONICAL_DOCUMENT,
                    "CANONICAL_DECODE",
                    f"{name} requires exact ASCII object keys",
                )
            _require_exact_json_tree(item, f"{name}.{key}")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _require_exact_json_tree(item, f"{name}[{index}]")
        return
    if value is None or type(value) in {int, bool}:
        return
    if type(value) is str and value.isascii():
        return
    _fail(
        NumericOracleErrorCode.INVALID_CANONICAL_DOCUMENT,
        "CANONICAL_DECODE",
        f"{name} contains a forbidden JSON primitive or non-ASCII string",
    )


def canonical_document_bytes(value: Mapping[str, Any]) -> bytes:
    """Encode one exact float-free ASCII JSON document plus one LF."""

    _require_exact_json_tree(value, "canonical document")
    try:
        body = canonical_json(value).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        _fail(
            NumericOracleErrorCode.INVALID_CANONICAL_DOCUMENT,
            "CANONICAL_ENCODE",
            "canonical document encoding failed",
            cause=exc,
        )
    return body + b"\n"


def _parse_canonical_document_bytes(payload: object, name: str) -> dict[str, Any]:
    if type(payload) is not bytes or not payload or not payload.endswith(b"\n"):
        _fail(
            NumericOracleErrorCode.INVALID_CANONICAL_DOCUMENT,
            "CANONICAL_DECODE",
            f"{name} must be exact bytes ending in one LF",
        )
    body = payload[:-1]
    if not body or body.endswith((b"\n", b"\r")) or b"\r" in body:
        _fail(
            NumericOracleErrorCode.INVALID_CANONICAL_DOCUMENT,
            "CANONICAL_DECODE",
            f"{name} has a non-canonical line ending",
        )
    try:
        text = body.decode("ascii")
        value = candidate_protocol.loads_canonical_json(text)
    except (UnicodeDecodeError, candidate_protocol.SWM0WS2SProtocolError) as exc:
        _fail(
            NumericOracleErrorCode.INVALID_CANONICAL_DOCUMENT,
            "CANONICAL_DECODE",
            f"{name} is not exact canonical ASCII JSON",
            cause=exc,
        )
    _require_exact_json_tree(value, name)
    if type(value) is not dict or canonical_document_bytes(value) != payload:
        _fail(
            NumericOracleErrorCode.INVALID_CANONICAL_DOCUMENT,
            "CANONICAL_DECODE",
            f"{name} must be one exact canonical JSON object",
        )
    return value


def _object(
    value: object,
    keys: Sequence[str],
    name: str,
    *,
    code: NumericOracleErrorCode,
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(keys):
        _fail(code, "SCHEMA_VALIDATION", f"{name} keys disagree with exact schema")
    return value


def _string(
    value: object,
    name: str,
    *,
    code: NumericOracleErrorCode,
) -> str:
    if type(value) is not str or not value or not value.isascii():
        _fail(code, "SCHEMA_VALIDATION", f"{name} must be exact nonempty ASCII")
    return value


def _sha256(
    value: object,
    name: str,
    *,
    code: NumericOracleErrorCode,
) -> str:
    text = _string(value, name, code=code)
    if len(text) != 64 or any(character not in _HEX for character in text):
        _fail(code, "SCHEMA_VALIDATION", f"{name} must be lowercase SHA-256")
    return text


def _seed(value: object, *, code: NumericOracleErrorCode) -> bytes:
    text = _string(value, "external seed", code=code)
    if len(text) != 64 or any(character not in _HEX for character in text):
        _fail(code, "SCHEMA_VALIDATION", "external seed must encode exact 32 bytes")
    return bytes.fromhex(text)


def _list(value: object, name: str, length: int, *, code: NumericOracleErrorCode) -> list[Any]:
    if type(value) is not list or len(value) != length:
        _fail(code, "SCHEMA_VALIDATION", f"{name} must contain exactly {length} items")
    return value


def _expected_workload() -> dict[str, Any]:
    return {
        "adjudication_optimizer_refit_allowed": False,
        "arm_order": [arm.value for arm in ALL_ARMS],
        "cell_count": CELL_COUNT,
        "domain_world_count_per_task": DOMAIN_WORLD_COUNT_PER_TASK,
        "draw_indices": list(range(TASK_COUNT)),
        "fit_execution_count": FIT_EXECUTION_COUNT,
        "optimizer_execution_count": OPTIMIZER_EXECUTION_COUNT,
        "replay_execution_count": REPLAY_EXECUTION_COUNT,
        "score_variant_count": SCORE_VARIANT_COUNT,
        "task_count": TASK_COUNT,
        "test_evaluation_count": TEST_EVALUATION_COUNT,
        "test_materialization_policy": TEST_MATERIALIZATION_POLICY,
        "test_world_count_per_task": TEST_WORLD_COUNT_PER_TASK,
    }


def _confirm_request_unsigned(
    external_seed: bytes,
    protocol_config: candidate_protocol.S2SProtocolConfig,
) -> dict[str, Any]:
    return {
        "canonical_encoding": CANONICAL_ENCODING,
        "external_seed_hex": external_seed.hex(),
        "protocol_config": protocol_config.canonical(),
        "protocol_config_receipt_sha256": protocol_config.receipt_sha256,
        "schema_version": CONFIRM_REQUEST_VERSION,
        "workload": _expected_workload(),
    }


def adopted_protocol_config() -> candidate_protocol.S2SProtocolConfig:
    """Reconstruct the exact numeric projection adopted from the public pilot."""

    common = {
        "seed": 0,
        "max_updates": 300,
        "beta1": 0.9,
        "beta2": 0.999,
        "epsilon": 1.0e-8,
        "gradient_clip": 5.0,
        "patience": 50,
        "min_delta": 1.0e-9,
    }
    result = candidate_protocol.build_protocol_config(
        (
            (
                S2SArm.T16,
                S2STrainingConfig(learning_rate=0.003, **common),
            ),
            (
                S2SArm.P_CAP18,
                S2STrainingConfig(learning_rate=0.001, **common),
            ),
            (
                S2SArm.DS870,
                S2STrainingConfig(learning_rate=0.001, **common),
            ),
        ),
        excluded_task_provenance=(
            (PILOT_EXCLUDED_SEED_COMMITMENT_SHA256, (0, 1, 2)),
        ),
    )
    if result.receipt_sha256 != ADOPTED_PROTOCOL_CONFIG_RECEIPT_SHA256:
        _fail(
            NumericOracleErrorCode.INTERNAL_NUMERIC_FAILURE,
            "ADOPTED_CONFIG_RECONSTRUCTION",
            "adopted protocol configuration no longer reconstructs exactly",
        )
    return result


@dataclass(frozen=True, slots=True)
class NumericConfirmRequest:
    external_seed: bytes
    protocol_config: candidate_protocol.S2SProtocolConfig
    request_sha256: str

    def __post_init__(self) -> None:
        if type(self.external_seed) is not bytes or len(self.external_seed) != 32:
            raise TypeError("numeric confirm request requires exact 32-byte seed")
        if type(self.protocol_config) is not candidate_protocol.S2SProtocolConfig:
            raise TypeError("numeric confirm request requires exact protocol config")
        _sha256(
            self.request_sha256,
            "confirm request SHA",
            code=NumericOracleErrorCode.INVALID_CONFIRM_REQUEST,
        )
        if self.request_sha256 != canonical_sha256(self.unsigned()):
            _fail(
                NumericOracleErrorCode.INVALID_CONFIRM_REQUEST,
                "REQUEST_BINDING",
                "confirm request hash mismatch",
            )

    def unsigned(self) -> dict[str, Any]:
        return _confirm_request_unsigned(self.external_seed, self.protocol_config)

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "request_sha256": self.request_sha256}


def build_confirm_request_bytes(
    *, external_seed: bytes, protocol_config: candidate_protocol.S2SProtocolConfig
) -> bytes:
    """Build canonical request bytes without acquiring or interpreting a seed."""

    if type(external_seed) is not bytes or len(external_seed) != 32:
        _fail(
            NumericOracleErrorCode.INVALID_CONFIRM_REQUEST,
            "REQUEST_BUILD",
            "external seed must be exact 32 bytes",
        )
    if type(protocol_config) is not candidate_protocol.S2SProtocolConfig:
        _fail(
            NumericOracleErrorCode.INVALID_CONFIRM_REQUEST,
            "REQUEST_BUILD",
            "protocol config must be exact S2SProtocolConfig",
        )
    unsigned = _confirm_request_unsigned(external_seed, protocol_config)
    return canonical_document_bytes(
        {**unsigned, "request_sha256": canonical_sha256(unsigned)}
    )


def _parse_confirm_request_bytes(
    payload: bytes,
    *,
    required_protocol_config_sha256: str | None,
) -> NumericConfirmRequest:
    code = NumericOracleErrorCode.INVALID_CONFIRM_REQUEST
    data = _parse_canonical_document_bytes(payload, "numeric confirm request")
    data = _object(
        data,
        (
            "canonical_encoding",
            "external_seed_hex",
            "protocol_config",
            "protocol_config_receipt_sha256",
            "request_sha256",
            "schema_version",
            "workload",
        ),
        "numeric confirm request",
        code=code,
    )
    if (
        _string(data["schema_version"], "confirm schema", code=code)
        != CONFIRM_REQUEST_VERSION
        or _string(data["canonical_encoding"], "canonical encoding", code=code)
        != CANONICAL_ENCODING
        or data["workload"] != _expected_workload()
    ):
        _fail(code, "SCHEMA_VALIDATION", "confirm fixed contract drifted")
    try:
        config = candidate_protocol.parse_protocol_config(data["protocol_config"])
    except (TypeError, ValueError, candidate_protocol.SWM0WS2SProtocolError) as exc:
        _fail(code, "SCHEMA_VALIDATION", "protocol config is invalid", cause=exc)
    bound_config_sha = _sha256(
        data["protocol_config_receipt_sha256"],
        "bound protocol config SHA",
        code=code,
    )
    if bound_config_sha != config.receipt_sha256:
        _fail(code, "REQUEST_BINDING", "protocol config binding mismatch")
    if (
        required_protocol_config_sha256 is not None
        and config.receipt_sha256 != required_protocol_config_sha256
    ):
        _fail(
            NumericOracleErrorCode.NON_ADOPTED_PROTOCOL_CONFIG,
            "ADOPTED_CONFIG_POLICY",
            "confirm request does not carry the pilot-adopted configuration",
        )
    result = NumericConfirmRequest(
        external_seed=_seed(data["external_seed_hex"], code=code),
        protocol_config=config,
        request_sha256=_sha256(
            data["request_sha256"], "confirm request SHA", code=code
        ),
    )
    if result.canonical() != data:
        _fail(code, "SCHEMA_VALIDATION", "confirm request is not its exact form")
    return result


def parse_confirm_request_bytes(payload: bytes) -> NumericConfirmRequest:
    """Parse only the exact pilot-adopted production request contract."""

    return _parse_confirm_request_bytes(
        payload,
        required_protocol_config_sha256=ADOPTED_PROTOCOL_CONFIG_RECEIPT_SHA256,
    )


@dataclass(frozen=True, slots=True)
class _ConfirmKernel:
    generate_batch: Callable[..., Any]
    prepare_training_cases: Callable[[Any], tuple[Any, Any]]
    fit: Callable[..., Any]
    replay: Callable[[Any], Any]
    build_replay_receipt: Callable[[Any, Any], Any]
    evaluate: Callable[[Any, tuple[Any, ...], tuple[Any, ...], Any], Any]
    finalize: Callable[..., Any]


@dataclass(frozen=True, slots=True)
class _AdjudicationKernel:
    generate_batch: Callable[..., Any]
    parse_evaluation: Callable[[Mapping[str, Any]], Any]
    parse_final: Callable[[Mapping[str, Any]], Any]
    finalize: Callable[..., Any]


def _prepare_training_cases(task: TaskSpecV2) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    return tuple(task.iter_cases("train")), tuple(task.iter_cases("dev"))


_PRODUCTION_CONFIRM_KERNEL = _ConfirmKernel(
    generate_batch=generate_task_batch,
    prepare_training_cases=_prepare_training_cases,
    fit=fit_task_operator,
    replay=replay_optimization,
    build_replay_receipt=candidate_protocol.build_fit_replay_receipt,
    evaluate=candidate_protocol.evaluate_task,
    finalize=candidate_protocol.finalize_candidate,
)

_PRODUCTION_ADJUDICATION_KERNEL = _AdjudicationKernel(
    generate_batch=generate_task_batch,
    parse_evaluation=candidate_protocol.parse_task_evaluation_receipt,
    parse_final=candidate_protocol.parse_final_candidate_receipt,
    finalize=candidate_protocol.finalize_candidate,
)


@dataclass(frozen=True, slots=True)
class _FittedTask:
    task: Any
    models: tuple[Any, ...]
    replay_receipts: tuple[Any, ...]


def _numeric_projection(final: Any) -> dict[str, Any]:
    return {
        "compact_competitive_phrase_allowed": False,
        "compact_competitive_phrase_policy": COMPACT_PHRASE_POLICY,
        "metric_estimates": {
            name: estimate.canonical() for name, estimate in final.estimates
        },
        "numeric_candidate_outcome": final.outcome.value,
        "numeric_candidate_reason_codes": list(final.reason_codes),
        "numeric_reducer_receipt_sha256": final.receipt_sha256,
        "status": NUMERIC_REPLAY_STATUS,
    }


def _execution_receipt() -> dict[str, Any]:
    return {
        "all_fit_replay_complete_before_test_materialization": True,
        "arm_order": [arm.value for arm in ALL_ARMS],
        "fit_execution_count": FIT_EXECUTION_COUNT,
        "optimizer_execution_count": OPTIMIZER_EXECUTION_COUNT,
        "replay_execution_count": REPLAY_EXECUTION_COUNT,
        "task_count": TASK_COUNT,
        "test_evaluation_count": TEST_EVALUATION_COUNT,
        "test_materialization_after_completed_cell_count": CELL_COUNT,
        "test_materialization_policy": TEST_MATERIALIZATION_POLICY,
    }


def _execute_confirmation(
    request: NumericConfirmRequest,
    kernel: _ConfirmKernel,
) -> dict[str, Any]:
    """Execute the numeric path; test kernels can observe the phase ordering."""

    try:
        batch = kernel.generate_batch(
            external_seed=request.external_seed,
            count=TASK_COUNT,
        )
    except Exception as exc:
        _fail(
            NumericOracleErrorCode.TASK_BATCH_GENERATION_FAILED,
            "TASK_BATCH_GENERATION",
            "fixed task-batch generation failed",
            cause=exc,
        )
    if (
        getattr(batch, "requested_count", None) != TASK_COUNT
        or len(getattr(batch, "tasks", ())) != TASK_COUNT
        or tuple(getattr(task, "draw_index", None) for task in batch.tasks)
        != tuple(range(TASK_COUNT))
    ):
        _fail(
            NumericOracleErrorCode.TASK_BATCH_GENERATION_FAILED,
            "TASK_BATCH_GENERATION",
            "task batch did not retain exact draws 0..19",
        )

    fitted_tasks: list[_FittedTask] = []
    completed_cells = 0
    try:
        for task in batch.tasks:
            train_cases, dev_cases = kernel.prepare_training_cases(task)
            models: list[Any] = []
            replay_receipts: list[Any] = []
            for arm in ALL_ARMS:
                model = kernel.fit(
                    task,
                    train_cases,
                    dev_cases,
                    arm=arm,
                    config=request.protocol_config.config_for(arm),
                )
                replayed = kernel.replay(model)
                replay_receipt = kernel.build_replay_receipt(model, replayed)
                models.append(model)
                replay_receipts.append(replay_receipt)
                completed_cells += 1
            fitted_tasks.append(
                _FittedTask(task, tuple(models), tuple(replay_receipts))
            )
    except Exception as exc:
        _fail(
            NumericOracleErrorCode.FIT_REPLAY_FAILED,
            "FIT_AND_EXACT_REPLAY",
            "a fit/replay cell failed; no numeric candidate was emitted",
            cause=exc,
        )
    if completed_cells != CELL_COUNT or len(fitted_tasks) != TASK_COUNT:
        _fail(
            NumericOracleErrorCode.FIT_REPLAY_FAILED,
            "FIT_AND_EXACT_REPLAY",
            "fit/replay roster ended before all sixty cells completed",
        )

    # This is the sole transition into evaluator-owned test data.  No call to
    # ``evaluate`` is reachable before the exact sixty-cell check above.
    evaluations: list[Any] = []
    try:
        for fitted in fitted_tasks:
            evaluations.append(
                kernel.evaluate(
                    fitted.task,
                    fitted.models,
                    fitted.replay_receipts,
                    request.protocol_config,
                )
            )
    except Exception as exc:
        _fail(
            NumericOracleErrorCode.TEST_EVALUATION_FAILED,
            "COMPLETE_TEST_AND_INTEGRITY_EVALUATION",
            "test/integrity evaluation failed; no numeric candidate was emitted",
            cause=exc,
        )
    if len(evaluations) != TEST_EVALUATION_COUNT:
        _fail(
            NumericOracleErrorCode.TEST_EVALUATION_FAILED,
            "COMPLETE_TEST_AND_INTEGRITY_EVALUATION",
            "test evaluation roster is incomplete",
        )

    try:
        final = kernel.finalize(
            batch,
            tuple(evaluation.metrics for evaluation in evaluations),
            request.protocol_config,
        )
    except Exception as exc:
        _fail(
            NumericOracleErrorCode.CANDIDATE_FINALIZATION_FAILED,
            "CANDIDATE_REDUCER",
            "candidate reducer failed; no numeric candidate was emitted",
            cause=exc,
        )

    unsigned = {
        "canonical_encoding": CANONICAL_ENCODING,
        "candidate_reducer_receipt": final.canonical(),
        "claim_boundary": CLAIM_BOUNDARY,
        "confirm_request_sha256": request.request_sha256,
        "execution_receipt": _execution_receipt(),
        "external_seed_hex": request.external_seed.hex(),
        "numeric_result_projection": _numeric_projection(final),
        "protocol_config": request.protocol_config.canonical(),
        "protocol_config_receipt_sha256": request.protocol_config.receipt_sha256,
        "schema_version": NUMERIC_CANDIDATE_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "status": NUMERIC_CANDIDATE_STATUS,
        "task_batch": candidate_protocol.serialize_task_batch(batch),
        "task_evaluations": [evaluation.canonical() for evaluation in evaluations],
    }
    return {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}


def confirm_numeric_candidate_bytes(payload: bytes) -> bytes:
    """Run the exact adopted confirmation and return all-or-nothing bytes."""

    request = parse_confirm_request_bytes(payload)
    candidate = _execute_confirmation(request, _PRODUCTION_CONFIRM_KERNEL)
    return canonical_document_bytes(candidate)


def _validate_numeric_projection_shape(
    value: object,
    *,
    code: NumericOracleErrorCode,
) -> dict[str, Any]:
    data = _object(
        value,
        (
            "compact_competitive_phrase_allowed",
            "compact_competitive_phrase_policy",
            "metric_estimates",
            "numeric_candidate_outcome",
            "numeric_candidate_reason_codes",
            "numeric_reducer_receipt_sha256",
            "status",
        ),
        "numeric result projection",
        code=code,
    )
    if (
        data["compact_competitive_phrase_allowed"] is not False
        or data["compact_competitive_phrase_policy"] != COMPACT_PHRASE_POLICY
        or data["status"] != NUMERIC_REPLAY_STATUS
    ):
        _fail(
            code,
            "NUMERIC_PROJECTION_SCHEMA",
            "numeric projection fixed claim boundary drifted",
        )
    _sha256(
        data["numeric_reducer_receipt_sha256"],
        "numeric reducer receipt SHA",
        code=code,
    )
    try:
        candidate_protocol.CandidateOutcome(data["numeric_candidate_outcome"])
    except (TypeError, ValueError) as exc:
        _fail(
            code,
            "NUMERIC_PROJECTION_SCHEMA",
            "numeric candidate outcome is unsupported",
            cause=exc,
        )
    reasons = data["numeric_candidate_reason_codes"]
    if (
        type(reasons) is not list
        or not reasons
        or any(type(reason) is not str or not reason or not reason.isascii() for reason in reasons)
    ):
        _fail(
            code,
            "NUMERIC_PROJECTION_SCHEMA",
            "numeric candidate reason codes are malformed",
        )
    estimates = data["metric_estimates"]
    if type(estimates) is not dict or set(estimates) not in (
        frozenset(),
        frozenset(("B", "C", "Q", "R")),
    ):
        _fail(
            code,
            "NUMERIC_PROJECTION_SCHEMA",
            "numeric metric-estimate roster drifted",
        )
    return data


def _parse_candidate_outer(
    payload: bytes,
    *,
    required_protocol_config_sha256: str | None,
) -> tuple[dict[str, Any], bytes, candidate_protocol.S2SProtocolConfig]:
    code = NumericOracleErrorCode.INVALID_NUMERIC_CANDIDATE
    data = _parse_canonical_document_bytes(payload, "numeric candidate")
    data = _object(
        data,
        (
            "canonical_encoding",
            "candidate_reducer_receipt",
            "claim_boundary",
            "confirm_request_sha256",
            "execution_receipt",
            "external_seed_hex",
            "numeric_result_projection",
            "protocol_config",
            "protocol_config_receipt_sha256",
            "receipt_sha256",
            "schema_version",
            "scientific_status",
            "status",
            "task_batch",
            "task_evaluations",
        ),
        "numeric candidate",
        code=code,
    )
    fixed = (
        data["schema_version"] == NUMERIC_CANDIDATE_VERSION
        and data["canonical_encoding"] == CANONICAL_ENCODING
        and data["claim_boundary"] == CLAIM_BOUNDARY
        and data["scientific_status"] == SCIENTIFIC_STATUS
        and data["status"] == NUMERIC_CANDIDATE_STATUS
        and data["execution_receipt"] == _execution_receipt()
    )
    if not fixed:
        _fail(code, "CANDIDATE_SCHEMA", "numeric candidate fixed contract drifted")
    receipt = _sha256(data["receipt_sha256"], "candidate receipt SHA", code=code)
    _sha256(data["confirm_request_sha256"], "confirm request SHA", code=code)
    unsigned = {key: value for key, value in data.items() if key != "receipt_sha256"}
    if receipt != canonical_sha256(unsigned):
        _fail(code, "CANDIDATE_BINDING", "numeric candidate receipt hash mismatch")
    seed = _seed(data["external_seed_hex"], code=code)
    try:
        config = candidate_protocol.parse_protocol_config(data["protocol_config"])
    except Exception as exc:
        _fail(code, "CANDIDATE_SCHEMA", "candidate protocol config is invalid", cause=exc)
    if (
        data["protocol_config_receipt_sha256"] != config.receipt_sha256
        or (
            required_protocol_config_sha256 is not None
            and config.receipt_sha256 != required_protocol_config_sha256
        )
    ):
        _fail(code, "CANDIDATE_BINDING", "candidate protocol config binding drifted")
    expected_request_sha256 = canonical_sha256(
        _confirm_request_unsigned(seed, config)
    )
    if data["confirm_request_sha256"] != expected_request_sha256:
        _fail(
            code,
            "CANDIDATE_BINDING",
            "candidate confirm-request binding drifted",
        )
    _validate_numeric_projection_shape(data["numeric_result_projection"], code=code)
    return data, seed, config


def _adjudicate_numeric_candidate(
    payload: bytes,
    kernel: _AdjudicationKernel,
    *,
    required_protocol_config_sha256: str | None,
) -> dict[str, Any]:
    data, seed, config = _parse_candidate_outer(
        payload,
        required_protocol_config_sha256=required_protocol_config_sha256,
    )
    code = NumericOracleErrorCode.INVALID_NUMERIC_CANDIDATE
    try:
        archived_batch = candidate_protocol.parse_task_batch(data["task_batch"])
        regenerated_batch = kernel.generate_batch(external_seed=seed, count=TASK_COUNT)
    except Exception as exc:
        _fail(code, "TASK_BATCH_REPLAY", "candidate task batch is invalid", cause=exc)
    if (
        candidate_protocol.serialize_task_batch(regenerated_batch)
        != candidate_protocol.serialize_task_batch(archived_batch)
    ):
        _fail(
            NumericOracleErrorCode.ADJUDICATION_REPLAY_MISMATCH,
            "TASK_BATCH_REPLAY",
            "regenerated task batch differs from the archived batch",
        )

    raw_evaluations = _list(
        data["task_evaluations"],
        "candidate task evaluations",
        TASK_COUNT,
        code=code,
    )
    evaluations: list[Any] = []
    try:
        for index, raw in enumerate(raw_evaluations):
            evaluation = kernel.parse_evaluation(raw)
            task = regenerated_batch.tasks[index]
            if (
                evaluation.task != task
                or evaluation.config != config
                or evaluation.metrics.draw_index != index
            ):
                _fail(
                    NumericOracleErrorCode.ADJUDICATION_REPLAY_MISMATCH,
                    "TEST_AND_INTEGRITY_REPLAY",
                    f"task evaluation {index} crosses its regenerated slot",
                )
            evaluations.append(evaluation)
        archived_final = kernel.parse_final(data["candidate_reducer_receipt"])
        recomputed_final = kernel.finalize(
            regenerated_batch,
            tuple(evaluation.metrics for evaluation in evaluations),
            config,
        )
    except SWM0WS2SNumericOracleError:
        raise
    except Exception as exc:
        _fail(
            NumericOracleErrorCode.ADJUDICATION_REPLAY_MISMATCH,
            "TEST_INTEGRITY_AND_REDUCER_REPLAY",
            "candidate test/integrity/reducer replay failed",
            cause=exc,
        )
    if archived_final.canonical() != recomputed_final.canonical():
        _fail(
            NumericOracleErrorCode.ADJUDICATION_REPLAY_MISMATCH,
            "CANDIDATE_REDUCER_REPLAY",
            "recomputed candidate reducer bytes differ from the archive",
        )
    projection = _numeric_projection(recomputed_final)
    if data["numeric_result_projection"] != projection:
        _fail(
            NumericOracleErrorCode.ADJUDICATION_REPLAY_MISMATCH,
            "NUMERIC_PROJECTION_REPLAY",
            "candidate numeric result projection does not recompute",
        )

    replay = {
        "candidate_reducer_canonical_equal": True,
        "candidate_reducer_receipt_sha256": recomputed_final.receipt_sha256,
        "compact_competitive_phrase_allowed": False,
        "compact_competitive_phrase_policy": COMPACT_PHRASE_POLICY,
        "numeric_candidate_outcome": recomputed_final.outcome.value,
        "numeric_candidate_reason_codes": list(recomputed_final.reason_codes),
        "optimizer_refit_performed": False,
        "protocol_config_receipt_sha256": config.receipt_sha256,
        "task_batch_sha256": regenerated_batch.batch_sha256,
        "task_evaluation_receipt_sha256s": [
            evaluation.receipt_sha256 for evaluation in evaluations
        ],
        "test_and_integrity_recomputed_count": len(evaluations),
    }
    unsigned = {
        "candidate_document_sha256": hashlib.sha256(payload).hexdigest(),
        "candidate_receipt_sha256": data["receipt_sha256"],
        "canonical_encoding": CANONICAL_ENCODING,
        "claim_boundary": CLAIM_BOUNDARY,
        "confirm_request_sha256": data["confirm_request_sha256"],
        "numeric_replay": replay,
        "schema_version": NUMERIC_ADJUDICATION_VERSION,
        "scientific_status": SCIENTIFIC_STATUS,
        "status": NUMERIC_REPLAY_STATUS,
    }
    return {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}


def adjudicate_numeric_candidate_bytes(payload: bytes) -> bytes:
    """Replay test/integrity/reducer numerics without either optimizer."""

    result = _adjudicate_numeric_candidate(
        payload,
        _PRODUCTION_ADJUDICATION_KERNEL,
        required_protocol_config_sha256=ADOPTED_PROTOCOL_CONFIG_RECEIPT_SHA256,
    )
    return canonical_document_bytes(result)


def parse_numeric_adjudication_bytes(payload: bytes) -> dict[str, Any]:
    """Strictly validate the small replay projection consumed by TypeScript."""

    code = NumericOracleErrorCode.INVALID_NUMERIC_ADJUDICATION
    data = _parse_canonical_document_bytes(payload, "numeric adjudication")
    data = _object(
        data,
        (
            "candidate_document_sha256",
            "candidate_receipt_sha256",
            "canonical_encoding",
            "claim_boundary",
            "confirm_request_sha256",
            "numeric_replay",
            "receipt_sha256",
            "schema_version",
            "scientific_status",
            "status",
        ),
        "numeric adjudication",
        code=code,
    )
    if (
        data["schema_version"] != NUMERIC_ADJUDICATION_VERSION
        or data["canonical_encoding"] != CANONICAL_ENCODING
        or data["claim_boundary"] != CLAIM_BOUNDARY
        or data["scientific_status"] != SCIENTIFIC_STATUS
        or data["status"] != NUMERIC_REPLAY_STATUS
    ):
        _fail(code, "ADJUDICATION_SCHEMA", "numeric adjudication fixed fields drifted")
    _sha256(data["candidate_document_sha256"], "candidate document SHA", code=code)
    _sha256(data["candidate_receipt_sha256"], "candidate receipt SHA", code=code)
    _sha256(data["confirm_request_sha256"], "confirm request SHA", code=code)
    receipt = _sha256(data["receipt_sha256"], "adjudication receipt SHA", code=code)
    replay = _object(
        data["numeric_replay"],
        (
            "candidate_reducer_canonical_equal",
            "candidate_reducer_receipt_sha256",
            "compact_competitive_phrase_allowed",
            "compact_competitive_phrase_policy",
            "numeric_candidate_outcome",
            "numeric_candidate_reason_codes",
            "optimizer_refit_performed",
            "protocol_config_receipt_sha256",
            "task_batch_sha256",
            "task_evaluation_receipt_sha256s",
            "test_and_integrity_recomputed_count",
        ),
        "numeric replay projection",
        code=code,
    )
    if (
        replay["candidate_reducer_canonical_equal"] is not True
        or replay["compact_competitive_phrase_allowed"] is not False
        or replay["compact_competitive_phrase_policy"] != COMPACT_PHRASE_POLICY
        or replay["optimizer_refit_performed"] is not False
        or replay["test_and_integrity_recomputed_count"] != TASK_COUNT
    ):
        _fail(code, "ADJUDICATION_SCHEMA", "numeric replay fixed fields drifted")
    for field in (
        "candidate_reducer_receipt_sha256",
        "protocol_config_receipt_sha256",
        "task_batch_sha256",
    ):
        _sha256(replay[field], field, code=code)
    if (
        replay["protocol_config_receipt_sha256"]
        != ADOPTED_PROTOCOL_CONFIG_RECEIPT_SHA256
    ):
        _fail(
            code,
            "ADJUDICATION_SCHEMA",
            "numeric replay does not bind the adopted protocol config",
        )
    _list(
        replay["task_evaluation_receipt_sha256s"],
        "evaluation receipt SHAs",
        TASK_COUNT,
        code=code,
    )
    for value in replay["task_evaluation_receipt_sha256s"]:
        _sha256(value, "evaluation receipt SHA", code=code)
    reasons = replay["numeric_candidate_reason_codes"]
    if (
        type(reasons) is not list
        or not reasons
        or any(type(reason) is not str or not reason or not reason.isascii() for reason in reasons)
    ):
        _fail(code, "ADJUDICATION_SCHEMA", "numeric candidate reasons are malformed")
    try:
        candidate_protocol.CandidateOutcome(
            _string(replay["numeric_candidate_outcome"], "numeric outcome", code=code)
        )
    except ValueError as exc:
        _fail(
            code,
            "ADJUDICATION_SCHEMA",
            "numeric candidate outcome is unsupported",
            cause=exc,
        )
    unsigned = {key: value for key, value in data.items() if key != "receipt_sha256"}
    if receipt != canonical_sha256(unsigned):
        _fail(code, "ADJUDICATION_BINDING", "adjudication receipt hash mismatch")
    return data


def golden_vector_document() -> dict[str, Any]:
    """Expose one frozen Python/TypeScript byte and generator integration vector."""

    config = adopted_protocol_config()
    request = build_confirm_request_bytes(
        external_seed=bytes.fromhex(GOLDEN_EXTERNAL_SEED_HEX),
        protocol_config=config,
    )
    config_document_sha256 = hashlib.sha256(
        canonical_document_bytes(config.canonical())
    ).hexdigest()
    request_document_sha256 = hashlib.sha256(request).hexdigest()
    request_value = _parse_canonical_document_bytes(request, "golden request")
    batch = generate_task_batch(
        external_seed=bytes.fromhex(GOLDEN_EXTERNAL_SEED_HEX),
        count=TASK_COUNT,
    )
    if (
        batch.seed_commitment_sha256 != GOLDEN_SEED_COMMITMENT_SHA256
        or batch.batch_sha256 != GOLDEN_TASK_BATCH_SHA256
        or batch.tasks[0].manifest_sha256 != GOLDEN_DRAW0_MANIFEST_SHA256
        or batch.duplicate_structural_target_draws
        or batch.duplicate_structural_task_draws
        or config_document_sha256 != ADOPTED_PROTOCOL_CONFIG_DOCUMENT_SHA256
        or request_document_sha256 != GOLDEN_CONFIRM_REQUEST_DOCUMENT_SHA256
        or request_value["request_sha256"] != GOLDEN_CONFIRM_REQUEST_SELF_SHA256
    ):
        _fail(
            NumericOracleErrorCode.INTERNAL_NUMERIC_FAILURE,
            "GOLDEN_VECTOR_RECONSTRUCTION",
            "frozen seed-to-task generator vector drifted",
        )
    unsigned = {
        "adopted_protocol_config": config.canonical(),
        "adopted_protocol_config_document_sha256": config_document_sha256,
        "canonical_encoding": CANONICAL_ENCODING,
        "confirm_request": request_value,
        "confirm_request_document_sha256": request_document_sha256,
        "draw0_manifest_sha256": GOLDEN_DRAW0_MANIFEST_SHA256,
        "duplicate_structural_target_draws": [],
        "duplicate_structural_task_draws": [],
        "external_seed_hex": GOLDEN_EXTERNAL_SEED_HEX,
        "purpose": "CROSS_LANGUAGE_TEST_VECTOR_NOT_CONFIRMATORY_EVIDENCE",
        "schema_version": GOLDEN_VECTOR_VERSION,
        "seed_commitment_sha256": GOLDEN_SEED_COMMITMENT_SHA256,
        "task_batch_sha256": GOLDEN_TASK_BATCH_SHA256,
    }
    receipt_sha256 = canonical_sha256(unsigned)
    if receipt_sha256 != GOLDEN_VECTOR_RECEIPT_SHA256:
        _fail(
            NumericOracleErrorCode.INTERNAL_NUMERIC_FAILURE,
            "GOLDEN_VECTOR_RECONSTRUCTION",
            "frozen golden-vector receipt drifted",
        )
    return {**unsigned, "receipt_sha256": receipt_sha256}


def golden_vector_bytes() -> bytes:
    result = canonical_document_bytes(golden_vector_document())
    if hashlib.sha256(result).hexdigest() != GOLDEN_VECTOR_DOCUMENT_SHA256:
        _fail(
            NumericOracleErrorCode.INTERNAL_NUMERIC_FAILURE,
            "GOLDEN_VECTOR_RECONSTRUCTION",
            "frozen golden-vector document bytes drifted",
        )
    return result


def _error_bytes(operation: str, error: SWM0WS2SNumericOracleError) -> bytes:
    unsigned = {
        "canonical_encoding": CANONICAL_ENCODING,
        "error_code": error.code.value,
        "operation": operation,
        "schema_version": NUMERIC_ERROR_VERSION,
        "stage": error.stage,
        "status": "NUMERIC_ORACLE_REJECTED_NO_PARTIAL_OUTPUT",
    }
    return canonical_document_bytes(
        {**unsigned, "receipt_sha256": canonical_sha256(unsigned)}
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    stderr: BinaryIO | None = None,
) -> int:
    """Process adapter: ``confirm``, ``adjudicate``, or deterministic ``golden``."""

    arguments = tuple(sys.argv[1:] if argv is None else argv)
    source = sys.stdin.buffer if stdin is None else stdin
    target = sys.stdout.buffer if stdout is None else stdout
    errors = sys.stderr.buffer if stderr is None else stderr
    operation = (
        arguments[0]
        if len(arguments) == 1
        and arguments[0] in {"confirm", "adjudicate", "golden"}
        else "INVALID"
    )
    try:
        if arguments == ("confirm",):
            result = confirm_numeric_candidate_bytes(source.read())
        elif arguments == ("adjudicate",):
            result = adjudicate_numeric_candidate_bytes(source.read())
        elif arguments == ("golden",):
            result = golden_vector_bytes()
        else:
            _fail(
                NumericOracleErrorCode.INVALID_CLI_INVOCATION,
                "CLI",
                "expected exactly one operation: confirm, adjudicate, or golden",
            )
    except SWM0WS2SNumericOracleError as exc:
        errors.write(_error_bytes(operation, exc))
        return 2
    except Exception as exc:  # one adapter conversion; never leak partial stdout
        wrapped = SWM0WS2SNumericOracleError(
            NumericOracleErrorCode.INTERNAL_NUMERIC_FAILURE,
            "PROCESS_ADAPTER",
            "unclassified numeric process failure",
        )
        wrapped.__cause__ = exc
        errors.write(_error_bytes(operation, wrapped))
        return 3
    target.write(result)
    return 0


__all__ = [
    "ADOPTED_PROTOCOL_CONFIG_DOCUMENT_SHA256",
    "ADOPTED_PROTOCOL_CONFIG_RECEIPT_SHA256",
    "CANONICAL_ENCODING",
    "COMPACT_PHRASE_POLICY",
    "CONFIRM_REQUEST_VERSION",
    "GOLDEN_CONFIRM_REQUEST_DOCUMENT_SHA256",
    "GOLDEN_CONFIRM_REQUEST_SELF_SHA256",
    "GOLDEN_DRAW0_MANIFEST_SHA256",
    "GOLDEN_EXTERNAL_SEED_HEX",
    "GOLDEN_SEED_COMMITMENT_SHA256",
    "GOLDEN_TASK_BATCH_SHA256",
    "GOLDEN_VECTOR_DOCUMENT_SHA256",
    "GOLDEN_VECTOR_RECEIPT_SHA256",
    "GOLDEN_VECTOR_VERSION",
    "NUMERIC_ADJUDICATION_VERSION",
    "NUMERIC_CANDIDATE_VERSION",
    "NUMERIC_ERROR_VERSION",
    "NumericConfirmRequest",
    "NumericOracleErrorCode",
    "SCIENTIFIC_STATUS",
    "SWM0WS2SNumericOracleError",
    "adjudicate_numeric_candidate_bytes",
    "adopted_protocol_config",
    "build_confirm_request_bytes",
    "canonical_document_bytes",
    "confirm_numeric_candidate_bytes",
    "golden_vector_bytes",
    "golden_vector_document",
    "main",
    "parse_confirm_request_bytes",
    "parse_numeric_adjudication_bytes",
]


if __name__ == "__main__":
    raise SystemExit(main())
