from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib
import json

import pytest

from hswm.experiments import swm0w_s2s_numeric_oracle as oracle
from hswm.experiments import swm0w_s2s_protocol as candidate_protocol
from hswm.experiments.swm0w_s2s_family import generate_task_batch
from hswm.experiments.swm0w_s2s_operator import ALL_ARMS, canonical_sha256
from hswm.experiments.swm0w_s2s_training import S2STrainingConfig


@pytest.fixture(scope="module")
def adopted_config():
    return oracle.adopted_protocol_config()


@pytest.fixture(scope="module")
def golden_request(adopted_config):
    return oracle.build_confirm_request_bytes(
        external_seed=bytes.fromhex(oracle.GOLDEN_EXTERNAL_SEED_HEX),
        protocol_config=adopted_config,
    )


def _rehash_document(value: dict[str, object], field: str = "receipt_sha256") -> bytes:
    unsigned = {key: item for key, item in value.items() if key != field}
    value[field] = canonical_sha256(unsigned)
    return oracle.canonical_document_bytes(value)


def test_adopted_config_and_cross_language_golden_bytes_are_frozen(
    adopted_config, golden_request
):
    assert adopted_config.receipt_sha256 == (
        "a8f62d3811e42fbf3bc0dc82a52a17f3fa27b4dfa1d43aa9e7ea302a142c40bb"
    )
    assert hashlib.sha256(
        oracle.canonical_document_bytes(adopted_config.canonical())
    ).hexdigest() == (
        "315dad65a8882c4b7c5fb73d295df28b58b0696e25b1b790a342b40ced8d10c4"
    )
    assert hashlib.sha256(golden_request).hexdigest() == (
        "294eb438fe042238bbe725d0473765f3634eb57876e5cae4807915db66034237"
    )
    assert len(golden_request) == 2861
    assert golden_request.endswith(b"\n") and not golden_request.endswith(b"\n\n")
    parsed = oracle.parse_confirm_request_bytes(golden_request)
    assert parsed.external_seed.hex() == oracle.GOLDEN_EXTERNAL_SEED_HEX
    assert parsed.protocol_config == adopted_config
    assert parsed.request_sha256 == (
        "16e4965054165863add0395397cbf3d68d1f3d472b7fc303e40056855368b1d1"
    )


def test_seed_to_twenty_draw_batch_golden_vector_is_exact_and_retains_draws():
    batch = generate_task_batch(
        external_seed=bytes.fromhex(oracle.GOLDEN_EXTERNAL_SEED_HEX),
        count=oracle.TASK_COUNT,
    )
    assert batch.seed_commitment_sha256 == oracle.GOLDEN_SEED_COMMITMENT_SHA256
    assert batch.batch_sha256 == oracle.GOLDEN_TASK_BATCH_SHA256
    assert batch.tasks[0].manifest_sha256 == oracle.GOLDEN_DRAW0_MANIFEST_SHA256
    assert tuple(task.draw_index for task in batch.tasks) == tuple(range(20))
    assert batch.duplicate_structural_target_draws == ()
    assert batch.duplicate_structural_task_draws == ()


def test_golden_document_is_self_bound_and_cli_byte_identical():
    value = oracle.golden_vector_document()
    payload = oracle.golden_vector_bytes()
    assert value["purpose"] == "CROSS_LANGUAGE_TEST_VECTOR_NOT_CONFIRMATORY_EVIDENCE"
    assert value["confirm_request_document_sha256"] == (
        "294eb438fe042238bbe725d0473765f3634eb57876e5cae4807915db66034237"
    )
    assert value["receipt_sha256"] == (
        "c6f487a192177adf654fada8dca9b8768391fb9f2e39a6b50214db557439618f"
    )
    assert hashlib.sha256(payload).hexdigest() == (
        "ae30799cc30eb146f69b8884aac1c137ec3fc34e835bcb009351f3889697cf43"
    )
    stdin, stdout, stderr = BytesIO(), BytesIO(), BytesIO()
    assert oracle.main(("golden",), stdin=stdin, stdout=stdout, stderr=stderr) == 0
    assert stdout.getvalue() == payload
    assert stderr.getvalue() == b""


@pytest.mark.parametrize(
    "mutate",
    (
        lambda value: value[:-1],
        lambda value: value + b"\n",
        lambda value: b" " + value,
        lambda value: value.replace(b'"schema_version"', b'"extra":0,"schema_version"'),
        lambda value: value.replace(b'"task_count":20', b'"task_count":true'),
    ),
)
def test_confirm_request_rejects_noncanonical_excess_and_fixed_field_drift(
    golden_request, mutate
):
    with pytest.raises(oracle.SWM0WS2SNumericOracleError):
        oracle.parse_confirm_request_bytes(mutate(golden_request))


def test_canonical_decoder_rejects_duplicate_keys_and_non_ascii():
    with pytest.raises(oracle.SWM0WS2SNumericOracleError) as duplicate:
        oracle.parse_confirm_request_bytes(b'{"a":1,"a":1}\n')
    assert duplicate.value.code is oracle.NumericOracleErrorCode.INVALID_CANONICAL_DOCUMENT
    with pytest.raises(oracle.SWM0WS2SNumericOracleError) as non_ascii:
        oracle.parse_confirm_request_bytes('{"a":"é"}\n'.encode())
    assert non_ascii.value.code is oracle.NumericOracleErrorCode.INVALID_CANONICAL_DOCUMENT


def test_production_parser_rejects_max_update_zero_but_private_test_hook_can_parse():
    config = candidate_protocol.build_protocol_config(
        tuple(
            (
                arm,
                S2STrainingConfig(
                    seed=0,
                    max_updates=0,
                    learning_rate=0.001,
                    patience=1,
                ),
            )
            for arm in ALL_ARMS
        ),
        excluded_task_provenance=(
            (oracle.PILOT_EXCLUDED_SEED_COMMITMENT_SHA256, (0, 1, 2)),
        ),
    )
    payload = oracle.build_confirm_request_bytes(
        external_seed=bytes.fromhex(oracle.GOLDEN_EXTERNAL_SEED_HEX),
        protocol_config=config,
    )
    with pytest.raises(oracle.SWM0WS2SNumericOracleError) as rejected:
        oracle.parse_confirm_request_bytes(payload)
    assert rejected.value.code is oracle.NumericOracleErrorCode.NON_ADOPTED_PROTOCOL_CONFIG
    parsed = oracle._parse_confirm_request_bytes(
        payload, required_protocol_config_sha256=None
    )
    assert parsed.protocol_config == config
    assert all(row.max_updates == 0 for _, row in config.arm_configs)


@dataclass(frozen=True, slots=True)
class _FakeModel:
    task: object
    arm: object


@dataclass(frozen=True, slots=True)
class _FakeReplay:
    draw_index: int
    arm: str


@dataclass(frozen=True, slots=True)
class _FakeMetric:
    draw_index: int

    def canonical(self) -> dict[str, object]:
        return {"draw_index": self.draw_index, "schema_version": "test-metric/v1"}


@dataclass(frozen=True, slots=True)
class _FakeEvaluation:
    task: object
    config: object
    metrics: _FakeMetric
    receipt_sha256: str

    @classmethod
    def issue(cls, task, config):
        unsigned = {
            "metrics": {"draw_index": task.draw_index, "schema_version": "test-metric/v1"},
            "protocol_config_receipt_sha256": config.receipt_sha256,
            "schema_version": "test-evaluation/v1",
            "task_spec": task.canonical(),
        }
        return cls(task, config, _FakeMetric(task.draw_index), canonical_sha256(unsigned))

    def canonical(self) -> dict[str, object]:
        unsigned = {
            "metrics": self.metrics.canonical(),
            "protocol_config_receipt_sha256": self.config.receipt_sha256,
            "schema_version": "test-evaluation/v1",
            "task_spec": self.task.canonical(),
        }
        return {**unsigned, "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class _FakeFinal:
    outcome: object
    reason_codes: tuple[str, ...]
    estimates: tuple[object, ...]
    receipt_sha256: str

    @classmethod
    def issue(cls, metrics):
        unsigned = {
            "draw_indices": [metric.draw_index for metric in metrics],
            "outcome": candidate_protocol.CandidateOutcome.VOID.value,
            "reason_codes": ["SYNTHETIC_TEST_KERNEL"],
            "schema_version": "test-final/v1",
        }
        return cls(
            candidate_protocol.CandidateOutcome.VOID,
            ("SYNTHETIC_TEST_KERNEL",),
            (),
            canonical_sha256(unsigned),
        )

    def canonical(self) -> dict[str, object]:
        # The test reducer always covers draws 0..19.
        unsigned = {
            "draw_indices": list(range(oracle.TASK_COUNT)),
            "outcome": self.outcome.value,
            "reason_codes": list(self.reason_codes),
            "schema_version": "test-final/v1",
        }
        return {**unsigned, "receipt_sha256": self.receipt_sha256}


def _fake_finalizer(_batch, metrics, _config):
    assert tuple(metric.draw_index for metric in metrics) == tuple(range(20))
    return _FakeFinal.issue(metrics)


def _fake_confirm_candidate(golden_request):
    events: list[tuple[str, int, str | None]] = []
    completed: set[tuple[int, str]] = set()

    def prepare(task):
        events.append(("prepare_train_dev", task.draw_index, None))
        return (), ()

    def fit(task, train, dev, *, arm, config):
        assert train == () and dev == ()
        assert config == oracle.adopted_protocol_config().config_for(arm)
        events.append(("fit", task.draw_index, arm.value))
        return _FakeModel(task, arm)

    def replay(model):
        events.append(("replay", model.task.draw_index, model.arm.value))
        completed.add((model.task.draw_index, model.arm.value))
        return model

    def build_replay(model, replayed):
        assert model == replayed
        return _FakeReplay(model.task.draw_index, model.arm.value)

    def evaluate(task, models, replays, config):
        assert len(completed) == oracle.CELL_COUNT
        assert len(models) == len(replays) == 3
        assert tuple(model.arm for model in models) == ALL_ARMS
        assert config == oracle.adopted_protocol_config()
        events.append(("evaluate_test", task.draw_index, None))
        return _FakeEvaluation.issue(task, config)

    kernel = oracle._ConfirmKernel(
        generate_batch=generate_task_batch,
        prepare_training_cases=prepare,
        fit=fit,
        replay=replay,
        build_replay_receipt=build_replay,
        evaluate=evaluate,
        finalize=_fake_finalizer,
    )
    request = oracle.parse_confirm_request_bytes(golden_request)
    value = oracle._execute_confirmation(request, kernel)
    return oracle.canonical_document_bytes(value), events


def test_all_sixty_fit_replays_finish_before_first_test_materialization(golden_request):
    payload, events = _fake_confirm_candidate(golden_request)
    first_test = next(index for index, row in enumerate(events) if row[0] == "evaluate_test")
    pre_test = events[:first_test]
    assert sum(row[0] == "fit" for row in pre_test) == 60
    assert sum(row[0] == "replay" for row in pre_test) == 60
    assert not any(row[0] == "evaluate_test" for row in pre_test)
    assert sum(row[0] == "evaluate_test" for row in events) == 20
    value = json.loads(payload)
    assert value["execution_receipt"] == oracle._execution_receipt()
    assert value["numeric_result_projection"]["compact_competitive_phrase_allowed"] is False
    assert value["numeric_result_projection"]["status"] == oracle.NUMERIC_REPLAY_STATUS
    assert value["claim_boundary"] == oracle.CLAIM_BOUNDARY
    assert "verdict" not in value
    assert oracle._PRODUCTION_CONFIRM_KERNEL.generate_batch is generate_task_batch
    assert oracle._PRODUCTION_CONFIRM_KERNEL.fit is oracle.fit_task_operator
    assert oracle._PRODUCTION_CONFIRM_KERNEL.replay is oracle.replay_optimization
    assert oracle._PRODUCTION_CONFIRM_KERNEL.evaluate is candidate_protocol.evaluate_task
    assert oracle._PRODUCTION_CONFIRM_KERNEL.finalize is candidate_protocol.finalize_candidate


def test_public_confirm_wrapper_executes_the_optimizer_bearing_path_once(
    golden_request, monkeypatch
):
    calls: list[tuple[object, object]] = []

    def execute(request, kernel):
        calls.append((request, kernel))
        return {"schema_version": "synthetic-single-call/v1"}

    monkeypatch.setattr(oracle, "_execute_confirmation", execute)
    assert oracle.confirm_numeric_candidate_bytes(golden_request) == (
        b'{"schema_version":"synthetic-single-call/v1"}\n'
    )
    assert len(calls) == 1
    assert calls[0][0] == oracle.parse_confirm_request_bytes(golden_request)
    assert calls[0][1] is oracle._PRODUCTION_CONFIRM_KERNEL


def _fake_adjudication_kernel(config, events):
    def parse_evaluation(raw):
        task = candidate_protocol.parse_task_spec_v2(raw["task_spec"])
        expected = _FakeEvaluation.issue(task, config)
        if raw != expected.canonical():
            raise ValueError("fake evaluation drifted")
        events.append(("recompute_test_integrity", task.draw_index))
        return expected

    def parse_final(raw):
        expected = _FakeFinal.issue(tuple(_FakeMetric(index) for index in range(20)))
        if raw != expected.canonical():
            raise ValueError("fake final drifted")
        return expected

    return oracle._AdjudicationKernel(
        generate_batch=generate_task_batch,
        parse_evaluation=parse_evaluation,
        parse_final=parse_final,
        finalize=_fake_finalizer,
    )


def test_adjudication_regenerates_all_numeric_rows_without_optimizer_refit(
    adopted_config, golden_request, monkeypatch
):
    candidate, _ = _fake_confirm_candidate(golden_request)
    monkeypatch.setattr(
        oracle,
        "fit_task_operator",
        lambda *args, **kwargs: pytest.fail("adjudication called fit optimizer"),
    )
    monkeypatch.setattr(
        oracle,
        "replay_optimization",
        lambda *args, **kwargs: pytest.fail("adjudication called replay optimizer"),
    )
    events: list[tuple[str, int]] = []
    value = oracle._adjudicate_numeric_candidate(
        candidate,
        _fake_adjudication_kernel(adopted_config, events),
        required_protocol_config_sha256=oracle.ADOPTED_PROTOCOL_CONFIG_RECEIPT_SHA256,
    )
    payload = oracle.canonical_document_bytes(value)
    parsed = oracle.parse_numeric_adjudication_bytes(payload)
    assert events == [("recompute_test_integrity", index) for index in range(20)]
    assert parsed["numeric_replay"]["optimizer_refit_performed"] is False
    assert parsed["numeric_replay"]["test_and_integrity_recomputed_count"] == 20
    assert parsed["numeric_replay"]["compact_competitive_phrase_allowed"] is False
    assert parsed["status"] == oracle.NUMERIC_REPLAY_STATUS
    assert "verdict" not in parsed
    assert set(oracle._AdjudicationKernel.__dataclass_fields__) == {
        "generate_batch",
        "parse_evaluation",
        "parse_final",
        "finalize",
    }
    assert oracle._PRODUCTION_ADJUDICATION_KERNEL.generate_batch is generate_task_batch
    assert oracle._PRODUCTION_ADJUDICATION_KERNEL.parse_evaluation is (
        candidate_protocol.parse_task_evaluation_receipt
    )
    assert oracle._PRODUCTION_ADJUDICATION_KERNEL.parse_final is (
        candidate_protocol.parse_final_candidate_receipt
    )
    assert oracle._PRODUCTION_ADJUDICATION_KERNEL.finalize is (
        candidate_protocol.finalize_candidate
    )


def test_adjudication_rejects_projection_and_batch_tamper(adopted_config, golden_request):
    candidate, _ = _fake_confirm_candidate(golden_request)
    base = json.loads(candidate)

    request_binding = json.loads(candidate)
    request_binding["confirm_request_sha256"] = "0" * 64
    request_binding_payload = _rehash_document(request_binding)
    with pytest.raises(oracle.SWM0WS2SNumericOracleError) as request_error:
        oracle._adjudicate_numeric_candidate(
            request_binding_payload,
            _fake_adjudication_kernel(adopted_config, []),
            required_protocol_config_sha256=oracle.ADOPTED_PROTOCOL_CONFIG_RECEIPT_SHA256,
        )
    assert request_error.value.code is (
        oracle.NumericOracleErrorCode.INVALID_NUMERIC_CANDIDATE
    )

    projection = json.loads(candidate)
    projection["numeric_result_projection"]["compact_competitive_phrase_allowed"] = True
    projection_payload = _rehash_document(projection)
    with pytest.raises(oracle.SWM0WS2SNumericOracleError) as phrase:
        oracle._adjudicate_numeric_candidate(
            projection_payload,
            _fake_adjudication_kernel(adopted_config, []),
            required_protocol_config_sha256=oracle.ADOPTED_PROTOCOL_CONFIG_RECEIPT_SHA256,
        )
    assert phrase.value.code is oracle.NumericOracleErrorCode.INVALID_NUMERIC_CANDIDATE

    base["task_batch"]["batch"]["batch_sha256"] = "0" * 64
    batch_payload = _rehash_document(base)
    with pytest.raises(oracle.SWM0WS2SNumericOracleError):
        oracle._adjudicate_numeric_candidate(
            batch_payload,
            _fake_adjudication_kernel(adopted_config, []),
            required_protocol_config_sha256=oracle.ADOPTED_PROTOCOL_CONFIG_RECEIPT_SHA256,
        )


def test_cli_failure_has_empty_stdout_and_typed_canonical_stderr():
    stdin, stdout, stderr = BytesIO(b"{}\n"), BytesIO(), BytesIO()
    assert oracle.main(("confirm",), stdin=stdin, stdout=stdout, stderr=stderr) == 2
    assert stdout.getvalue() == b""
    error = json.loads(stderr.getvalue())
    assert stderr.getvalue().endswith(b"\n")
    assert error["schema_version"] == oracle.NUMERIC_ERROR_VERSION
    assert error["status"] == "NUMERIC_ORACLE_REJECTED_NO_PARTIAL_OUTPUT"
    assert error["operation"] == "confirm"
    assert error["error_code"] in {
        oracle.NumericOracleErrorCode.INVALID_CONFIRM_REQUEST.value,
        oracle.NumericOracleErrorCode.INVALID_CANONICAL_DOCUMENT.value,
    }
    assert "candidate" not in error

    stdin, stdout, stderr = BytesIO(), BytesIO(), BytesIO()
    assert oracle.main(("é",), stdin=stdin, stdout=stdout, stderr=stderr) == 2
    assert stdout.getvalue() == b""
    invalid = json.loads(stderr.getvalue())
    assert invalid["operation"] == "INVALID"
    assert invalid["error_code"] == (
        oracle.NumericOracleErrorCode.INVALID_CLI_INVOCATION.value
    )


def test_numeric_module_has_no_external_control_plane_imports_or_clock_reads():
    with open(oracle.__file__, encoding="utf-8") as handle:
        source = handle.read()
    forbidden = (
        "import os",
        "import resource",
        "import subprocess",
        "import time",
        "import requests",
        "import urllib",
        "import github",
        "import drand",
        "Path(",
    )
    assert not any(token in source for token in forbidden)
    assert "getenv(" not in source
    assert "getrusage(" not in source
    assert "fit_task_operator" not in set(oracle._AdjudicationKernel.__dataclass_fields__)
