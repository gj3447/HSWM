from __future__ import annotations

import pytest

from hswm.infrastructure.occurrence_workflow import (
    OccurrencePhase,
    PulseTiming,
    VoidReason,
    advance_occurrence,
    registered_occurrence,
    temporal_one_shot_launch_options,
    OccurrenceWorkflowStateV1,
)


UID = "study:future-outcome-001"


def digest(index: int) -> str:
    return f"{index:064x}"


def test_external_adapter_options_are_exactly_one_shot() -> None:
    options = temporal_one_shot_launch_options(UID)

    assert options.as_external_adapter_options() == {
        "activity_retry_policy": {"maximum_attempts": 1},
        "occurrence_uid": UID,
        "replacement_round_allowed": False,
        "schema_version": "hswm-g0-occurrence-temporal-launch-options/v1",
        "workflow_id": "g0-occurrence/study:future-outcome-001",
        "workflow_id_reuse_policy": "REJECT_DUPLICATE",
        "workflow_retry_policy": {"maximum_attempts": 1},
    }


def test_happy_path_requires_the_declared_exact_order() -> None:
    state = registered_occurrence(occurrence_uid=UID, registration_evidence_sha256=digest(1))
    steps = (
        (OccurrencePhase.CLAIMED, PulseTiming.PRE_PULSE),
        (OccurrencePhase.SCHEDULED, PulseTiming.PRE_PULSE),
        (OccurrencePhase.PRE_PULSE_SEALED, PulseTiming.PRE_PULSE),
        (OccurrencePhase.PULSE_VERIFIED, PulseTiming.POST_PULSE),
        (OccurrencePhase.REVEALED, PulseTiming.POST_PULSE),
        (OccurrencePhase.DUAL_EVALUATED, PulseTiming.POST_PULSE),
        (OccurrencePhase.SEALED, PulseTiming.POST_PULSE),
    )
    for index, (phase, timing) in enumerate(steps, start=2):
        state = advance_occurrence(
            state, next_phase=phase, evidence_sha256=digest(index), timing=timing
        )

    assert state.phase is OccurrencePhase.SEALED
    assert state.terminal is True
    assert len(state.evidence_sha256s) == 8


def test_workflow_state_cannot_be_fabricated_at_a_terminal_phase() -> None:
    with pytest.raises(ValueError, match="registered_occurrence"):
        OccurrenceWorkflowStateV1(
            UID,
            OccurrencePhase.SEALED,
            (digest(1),),
        )


def test_duplicate_retry_is_terminal_void() -> None:
    state = registered_occurrence(occurrence_uid=UID, registration_evidence_sha256=digest(1))
    claimed = advance_occurrence(
        state,
        next_phase=OccurrencePhase.CLAIMED,
        evidence_sha256=digest(2),
        timing=PulseTiming.PRE_PULSE,
    )

    result = advance_occurrence(
        claimed,
        next_phase=OccurrencePhase.CLAIMED,
        evidence_sha256=digest(3),
        timing=PulseTiming.PRE_PULSE,
    )

    assert result.phase is OccurrencePhase.VOID
    assert result.void_reason is VoidReason.DUPLICATE_OR_RETRY
    assert result.rejected_evidence_sha256 == digest(3)
    assert result.terminal is True


def test_late_pre_pulse_seal_is_terminal_void() -> None:
    state = registered_occurrence(occurrence_uid=UID, registration_evidence_sha256=digest(1))
    for index, phase in enumerate((OccurrencePhase.CLAIMED, OccurrencePhase.SCHEDULED), start=2):
        state = advance_occurrence(
            state, next_phase=phase, evidence_sha256=digest(index), timing=PulseTiming.PRE_PULSE
        )

    result = advance_occurrence(
        state,
        next_phase=OccurrencePhase.PRE_PULSE_SEALED,
        evidence_sha256=digest(4),
        timing=PulseTiming.POST_PULSE,
    )

    assert result.phase is OccurrencePhase.VOID
    assert result.void_reason is VoidReason.LATE
    assert result.rejected_evidence_sha256 == digest(4)


def test_out_of_order_or_reused_evidence_is_terminal_void() -> None:
    state = registered_occurrence(occurrence_uid=UID, registration_evidence_sha256=digest(1))
    out_of_order = advance_occurrence(
        state,
        next_phase=OccurrencePhase.REVEALED,
        evidence_sha256=digest(2),
        timing=PulseTiming.POST_PULSE,
    )
    assert out_of_order.phase is OccurrencePhase.VOID
    assert out_of_order.void_reason is VoidReason.ORDER

    reused = advance_occurrence(
        state,
        next_phase=OccurrencePhase.CLAIMED,
        evidence_sha256=digest(1),
        timing=PulseTiming.PRE_PULSE,
    )
    assert reused.phase is OccurrencePhase.VOID
    assert reused.void_reason is VoidReason.DUPLICATE_OR_RETRY
    assert reused.rejected_evidence_sha256 == digest(1)

    # A later message cannot rewrite the first terminal reason/evidence lineage.
    unchanged = advance_occurrence(
        out_of_order,
        next_phase=OccurrencePhase.CLAIMED,
        evidence_sha256=digest(9),
        timing=PulseTiming.PRE_PULSE,
    )
    assert unchanged is out_of_order


def test_terminal_state_precedes_validation_and_first_void_is_always_immutable() -> None:
    state = registered_occurrence(
        occurrence_uid=UID,
        registration_evidence_sha256=digest(1),
    )
    for index, (phase, timing) in enumerate(
        (
            (OccurrencePhase.CLAIMED, PulseTiming.PRE_PULSE),
            (OccurrencePhase.SCHEDULED, PulseTiming.PRE_PULSE),
            (OccurrencePhase.PRE_PULSE_SEALED, PulseTiming.PRE_PULSE),
            (OccurrencePhase.PULSE_VERIFIED, PulseTiming.POST_PULSE),
            (OccurrencePhase.REVEALED, PulseTiming.POST_PULSE),
            (OccurrencePhase.DUAL_EVALUATED, PulseTiming.POST_PULSE),
            (OccurrencePhase.SEALED, PulseTiming.POST_PULSE),
        ),
        start=2,
    ):
        state = advance_occurrence(
            state,
            next_phase=phase,
            evidence_sha256=digest(index),
            timing=timing,
        )

    reentered = advance_occurrence(
        state,
        next_phase="NOT_A_PHASE",  # type: ignore[arg-type]
        evidence_sha256="not-a-sha256",
        timing="NOT_A_TIMING",  # type: ignore[arg-type]
    )
    assert reentered.phase is OccurrencePhase.VOID
    assert reentered.void_reason is VoidReason.TERMINAL_REENTRY
    assert reentered.rejected_evidence_sha256 is None

    unchanged = advance_occurrence(
        reentered,
        next_phase="NOT_A_PHASE",  # type: ignore[arg-type]
        evidence_sha256=digest(99),
        timing="NOT_A_TIMING",  # type: ignore[arg-type]
    )
    assert unchanged is reentered
