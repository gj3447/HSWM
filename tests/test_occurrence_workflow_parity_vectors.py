from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hswm.infrastructure.occurrence_workflow import (
    OccurrencePhase,
    PulseTiming,
    advance_occurrence,
    registered_occurrence,
)


VECTORS_PATH = (
    Path(__file__).parents[1]
    / "_research/g0_occurrence/HSWM_G0_WORKFLOW_PARITY_VECTORS.v1.json"
)


def _known_or_raw(enum_type: type, value: str) -> Any:
    try:
        return enum_type(value)
    except ValueError:
        return value


def test_python_workflow_matches_cross_language_parity_vectors() -> None:
    vectors = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))

    assert vectors["schema_version"] == (
        "hswm-g0-occurrence-workflow-parity-vectors/v1"
    )
    assert vectors["status"] == (
        "CROSS_LANGUAGE_ENGINEERING_FIXTURE_ONLY_NOT_EXECUTED_NOT_G0"
    )
    assert vectors["parity_scope"] == (
        "TRANSITION_RESULT_PARITY_ONLY_NOT_WIRE_SCHEMA_NOT_TIMEOUT_LOOP_"
        "NOT_SIGNAL_QUEUE_NOT_COMPLETION_HANDSHAKE"
    )
    assert vectors["occurrence_timeout_seconds"] == 600
    assert len(vectors["cases"]) == 11

    for case in vectors["cases"]:
        state = registered_occurrence(
            occurrence_uid=vectors["occurrence_uid"],
            registration_evidence_sha256=case["registration_evidence_sha256"],
        )
        for transition in case["transitions"]:
            state = advance_occurrence(
                state,
                next_phase=_known_or_raw(
                    OccurrencePhase, transition["next_phase"]
                ),
                evidence_sha256=transition["evidence_sha256"],
                timing=_known_or_raw(PulseTiming, transition["timing"]),
            )

        expected = case["expected"]
        assert state.phase.value == expected["phase"], case["case_id"]
        assert list(state.evidence_sha256s) == expected["evidence_sha256s"], case[
            "case_id"
        ]
        assert (
            None if state.void_reason is None else state.void_reason.value
        ) == expected["void_reason"], case["case_id"]
        assert state.rejected_evidence_sha256 == expected[
            "rejected_evidence_sha256"
        ], case["case_id"]
        assert state.terminal is expected["terminal"], case["case_id"]
