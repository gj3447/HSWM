from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys

import pytest
pytest.importorskip("temporalio")
from temporalio.common import WorkflowIDReusePolicy


MODULE_PATH = (
    Path(__file__).parents[1]
    / "_research/g0_occurrence/occurrence_temporal_worker.py"
)
SPEC = importlib.util.spec_from_file_location("occurrence_temporal_worker", MODULE_PATH)
assert SPEC and SPEC.loader
worker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = worker
SPEC.loader.exec_module(worker)


def descriptor(name: str, value: int) -> object:
    return worker.ContentDescriptorV1(name=name, sha256=f"{value:064x}")


def input_value() -> object:
    return worker.OccurrenceWorkflowInputV1(
        occurrence_uid="future-outcome-001",
        worm_claim_receipt=descriptor("candidate_worm_claim_receipt", 1),
        registration_evidence=descriptor("registration_evidence", 2),
        occurrence_timeout_seconds=600,
    )


def test_start_options_are_explicitly_one_shot_and_duplicate_rejecting() -> None:
    options = worker.build_start_options(input_value())

    assert options["id"] == "g0-occurrence/future-outcome-001"
    assert options["id_reuse_policy"] is WorkflowIDReusePolicy.REJECT_DUPLICATE
    assert options["retry_policy"].maximum_attempts == 1
    assert options["execution_timeout"].total_seconds() == 660


def test_dry_run_is_redacted_and_never_contacts_temporal() -> None:
    config = worker.OccurrenceWorkerConfigV1(
        address="temporal.internal:7233",
        namespace="g0",
        task_queue="g0-queue",
        signal_authorization_binding_sha256="d" * 64,
    )
    plan = worker.dry_run_plan(input_value(), config)

    assert plan["execution"] == "DRY_RUN_NO_TEMPORAL_CONNECTION"
    assert plan["python_worker_status"] == (
        "RETIRED_REFERENCE_ONLY_TYPESCRIPT_EXECUTION_SELECTED"
    )
    assert plan["orchestration_authority"] == "TYPESCRIPT_TEMPORAL"
    assert plan["live_external_admission"] is False
    assert plan["workflow_id_reuse_policy"] == "REJECT_DUPLICATE"
    assert plan["workflow_maximum_attempts"] == 1
    assert plan["activity_maximum_attempts"] == 1
    assert plan["occurrence_timeout_seconds"] == 600
    assert plan["receipt_finalization_grace_seconds"] == 60
    assert plan["execution_timeout_seconds"] == 660
    assert plan["replacement_round_allowed"] is False
    assert plan["post_start_evidence"] == "SIGNAL_ONLY_NOT_PRELOADED"
    assert plan["publication_eligible"] is False
    assert "temporal.internal" not in str(plan)
    assert plan["signal_authorization"] == (
        "CONTENT_ADDRESSED_EXTERNAL_POLICY_DECLARED_NOT_VERIFIED_BY_WORKER"
    )
    assert "does not authenticate" in plan["signal_authorization_claim_boundary"]
    assert plan["g0_status"] == "NOT_EXECUTED"


def test_retired_python_worker_refuses_serve_and_start() -> None:
    config = worker.OccurrenceWorkerConfigV1(
        address="temporal.internal:7233",
        namespace="g0",
        task_queue="g0-queue",
        signal_authorization_binding_sha256="d" * 64,
    )
    with pytest.raises(RuntimeError, match="TypeScript Temporal implementation"):
        asyncio.run(worker.serve(config))
    with pytest.raises(RuntimeError, match="TypeScript Temporal implementation"):
        asyncio.run(worker.start_one_shot(object(), config, input_value()))


def test_missing_worm_receipt_refuses_before_any_temporal_operation() -> None:
    with pytest.raises(ValueError, match="WORM"):
        worker.OccurrenceWorkflowInputV1(
            occurrence_uid="future-outcome-001",
            worm_claim_receipt=None,
            registration_evidence=descriptor("registration_evidence", 2),
            occurrence_timeout_seconds=600,
        )


def test_config_requires_all_coordinates_and_accepts_no_credentials() -> None:
    with pytest.raises(ValueError, match="address"):
        worker.OccurrenceWorkerConfigV1.from_args_or_environment(
            address=None,
            namespace=None,
            task_queue=None,
            signal_authorization_binding_sha256=None,
            environ={},
        )

    config = worker.OccurrenceWorkerConfigV1.from_args_or_environment(
        address=None,
        namespace=None,
        task_queue=None,
        signal_authorization_binding_sha256=None,
        environ={
            "HSWM_G0_TEMPORAL_ADDRESS": "temporal.example:7233",
            "HSWM_G0_TEMPORAL_NAMESPACE": "g0",
            "HSWM_G0_TEMPORAL_TASK_QUEUE": "occurrence",
            "HSWM_G0_TEMPORAL_SIGNAL_AUTHORIZATION_BINDING": "d" * 64,
            "UNRELATED_SECRET": "must-not-appear",
        },
    )
    assert config.redacted_summary() == {
        "address_configured": True,
        "namespace_configured": True,
        "task_queue_configured": True,
        "signal_authorization_binding_configured": True,
        "credentials_accepted": False,
    }


def test_invalid_transition_payload_is_terminal_void_without_a_retry() -> None:
    transition = worker.PhaseTransitionV1(
        "NOT_A_PHASE", descriptor("invalid", 3), "PRE_PULSE"
    )
    state = worker.registered_occurrence(
        occurrence_uid="future-outcome-001", registration_evidence_sha256=f"{2:064x}"
    )
    result = worker.apply_transition(state, transition)

    assert result.phase.value == "VOID"
    assert result.void_reason.value == "ORDER"


def test_worm_receipt_is_exactly_the_claimed_transition_evidence() -> None:
    value = input_value()
    state = worker.registered_occurrence(
        occurrence_uid=value.occurrence_uid,
        registration_evidence_sha256=value.registration_evidence.sha256,
    )
    claimed = worker.advance_occurrence(
        state,
        next_phase=worker.OccurrencePhase.CLAIMED,
        evidence_sha256=value.worm_claim_receipt.sha256,
        timing=worker.PulseTiming.PRE_PULSE,
    )

    assert claimed.phase.value == "CLAIMED"
    assert claimed.evidence_sha256s[-1] == value.worm_claim_receipt.sha256


def test_start_input_has_no_preloaded_post_pulse_transition_values() -> None:
    assert set(worker.OccurrenceWorkflowInputV1.__dataclass_fields__) == {
        "occurrence_uid",
        "worm_claim_receipt",
        "registration_evidence",
        "occurrence_timeout_seconds",
        "schema_version",
    }


def test_wire_mapping_is_strictly_parsed_without_string_coercion() -> None:
    parsed = worker._transition_from_wire(
        {
            "next_phase": "SCHEDULED",
            "timing": "PRE_PULSE",
            "evidence": {"name": "schedule", "sha256": f"{4:064x}"},
        }
    )
    assert parsed is not None
    assert parsed.evidence.sha256 == f"{4:064x}"

    assert worker._transition_from_wire(
        {
            "next_phase": "SCHEDULED",
            "timing": "PRE_PULSE",
            "evidence": {"name": "schedule", "sha256": 4},
        }
    ) is None


def test_dry_run_input_rejects_oversized_file_before_reading(tmp_path: Path) -> None:
    path = tmp_path / "input.json"
    path.write_bytes(b"x" * (worker.MAX_INPUT_JSON_BYTES + 1))

    with pytest.raises(ValueError, match="exceeds byte limit"):
        worker.input_from_json_path(path)
    assert worker._transition_from_wire(
        {
            "next_phase": "SCHEDULED",
            "timing": "PRE_PULSE",
            "evidence": {"name": "schedule", "sha256": f"{4:064x}", "extra": "x"},
        }
    ) is None


def test_terminal_extra_signal_becomes_void_and_preserves_rejected_digest() -> None:
    sealed = worker.registered_occurrence(
        occurrence_uid="future-outcome-001",
        registration_evidence_sha256=f"{1:064x}",
    )
    steps = (
        (worker.OccurrencePhase.CLAIMED, worker.PulseTiming.PRE_PULSE),
        (worker.OccurrencePhase.SCHEDULED, worker.PulseTiming.PRE_PULSE),
        (worker.OccurrencePhase.PRE_PULSE_SEALED, worker.PulseTiming.PRE_PULSE),
        (worker.OccurrencePhase.PULSE_VERIFIED, worker.PulseTiming.POST_PULSE),
        (worker.OccurrencePhase.REVEALED, worker.PulseTiming.POST_PULSE),
        (worker.OccurrencePhase.DUAL_EVALUATED, worker.PulseTiming.POST_PULSE),
        (worker.OccurrencePhase.SEALED, worker.PulseTiming.POST_PULSE),
    )
    for index, (phase, timing) in enumerate(steps, start=2):
        sealed = worker.advance_occurrence(
            sealed,
            next_phase=phase,
            evidence_sha256=f"{index:064x}",
            timing=timing,
        )
    queued = [
        {
            "next_phase": "SEALED",
            "timing": "POST_PULSE",
            "evidence": {"name": "duplicate", "sha256": f"{5:064x}"},
        }
    ]
    rejected = worker._rejected_evidence_sha256(queued)
    result = worker._terminal_void(
        sealed, worker.VoidReason.TERMINAL_REENTRY, rejected
    )

    assert queued == []
    assert result.phase is worker.OccurrencePhase.VOID
    assert worker._state_projection(result)["rejected_evidence_sha256"] == f"{5:064x}"
    assert worker._state_projection(result)["publication_eligible"] is False
