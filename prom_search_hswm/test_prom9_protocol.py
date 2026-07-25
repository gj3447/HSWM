from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

import hswm_next_research_harness as next_harness
from prom_search_hswm import prom9_protocol


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / prom9_protocol.DEFAULT_PROTOCOL
FIXED_TIME = "2026-07-24T08:00:00+00:00"


def _protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def _status() -> dict:
    return next_harness.build_status(repo_root=REPO_ROOT, recorded_at=FIXED_TIME)


def test_checked_in_prom9_protocol_is_valid_and_keeps_science_external() -> None:
    protocol = prom9_protocol.validate_protocol(_protocol())

    assert protocol["status"] == "DESIGN_LOCKED_NOT_PREREGISTERED"
    assert [stage["id"] for stage in protocol["stages"]] == list(
        prom9_protocol.REQUIRED_STAGE_IDS
    )
    assert [function["id"] for function in protocol["llm_functions"]] == list(
        prom9_protocol.REQUIRED_FUNCTION_IDS
    )
    assert "external" in protocol["execution_model"]["evaluator"].lower()
    assert protocol["lakatotree"]["scientific_prediction_registered_by_this_protocol"] is False
    assert protocol["lakatotree"]["scientific_result_submitted_by_this_protocol"] is False


def test_function_prompts_have_typed_non_overlapping_outputs_and_no_verdict_authority() -> None:
    protocol = prom9_protocol.validate_protocol(_protocol())
    functions = {function["id"]: function for function in protocol["llm_functions"]}

    assert functions["QF_QUERY_COMPILER"]["output_type"] == "QueryPlanV1"
    assert functions["BF_BOND_PROPOSER"]["output_type"] == "BondProposalV1"
    assert functions["AF_ANSWER_SYNTHESIZER"]["output_type"] == "AnswerEnvelopeV1"
    assert "Do not answer the user" in functions["QF_QUERY_COMPILER"]["prompt"]
    assert "Do not answer the query" in functions["BF_BOND_PROPOSER"]["prompt"]
    assert "scientific verdict" in functions["AF_ANSWER_SYNTHESIZER"]["prompt"]
    assert len({function["output_type"] for function in functions.values()}) == 3


def test_protocol_rejects_forward_dependency_role_drift_and_missing_causal_control() -> None:
    forward = deepcopy(_protocol())
    forward["stages"][0]["depends_on"] = ["P2_FROZEN_AGENT_TRANSFER"]
    with pytest.raises(prom9_protocol.Prom9ProtocolError, match="missing/forward"):
        prom9_protocol.validate_protocol(forward)

    role_drift = deepcopy(_protocol())
    role_drift["llm_functions"][1]["id"] = "GENERIC_SECOND_PROMPT"
    with pytest.raises(prom9_protocol.Prom9ProtocolError, match="requires exactly"):
        prom9_protocol.validate_protocol(role_drift)

    no_removal = deepcopy(_protocol())
    no_removal["arm_matrix"]["P1V5"] = [
        arm for arm in no_removal["arm_matrix"]["P1V5"] if "causal_removal" not in arm
    ]
    with pytest.raises(prom9_protocol.Prom9ProtocolError, match="causal removal"):
        prom9_protocol.validate_protocol(no_removal)


def test_current_status_allows_only_f1_repair_preparation() -> None:
    stage_id = "F1_TYPED_FUNCTION_NETWORK"
    packet = prom9_protocol.build_stage_packet(
        protocol=_protocol(),
        protocol_sha256=prom9_protocol.file_sha256(PROTOCOL_PATH),
        status=_status(),
        stage_id=stage_id,
        run_id=f"dev-{stage_id.lower()}",
        recorded_at=FIXED_TIME,
    )

    assert prom9_protocol.verify_stage_packet(packet) == packet["packet_sha256"]
    assert packet["preparation_allowed"] is True
    assert packet["sealed_measurement_allowed"] is False
    assert packet["activation_allowed"] is False
    assert packet["scientific_prediction_registered"] is False
    assert packet["scientific_result_submitted"] is False
    assert len(packet["llm_functions"]) == 3


def test_current_status_refuses_gate0_p1v5_and_p2_before_prerequisites() -> None:
    for stage_id in (
        "G0_REAL_PACKS",
        "P1V5_FAST_TO_SLOW_PLASTICITY",
        "P2_FROZEN_AGENT_TRANSFER",
    ):
        with pytest.raises(prom9_protocol.Prom9ProtocolError, match="is not"):
            prom9_protocol.build_stage_packet(
                protocol=_protocol(),
                protocol_sha256=prom9_protocol.file_sha256(PROTOCOL_PATH),
                status=_status(),
                stage_id=stage_id,
                run_id="must-refuse",
                recorded_at=FIXED_TIME,
            )


def test_stage_packet_requires_the_single_active_gate() -> None:
    status = _status()
    for row in status["gates"]:
        if row["id"] == "B22_GATE0_REAL_PACKS":
            row["state"] = "ACTION_REQUIRED"
            row["missing_dependencies"] = []
    unsigned = dict(status)
    unsigned.pop("status_receipt_sha256")
    status["status_receipt_sha256"] = next_harness.canonical_sha256(unsigned)

    with pytest.raises(prom9_protocol.Prom9ProtocolError, match="single active"):
        prom9_protocol.build_stage_packet(
            protocol=_protocol(),
            protocol_sha256=prom9_protocol.file_sha256(PROTOCOL_PATH),
            status=status,
            stage_id="G0_REAL_PACKS",
            run_id="must-refuse-nonactive",
            recorded_at=FIXED_TIME,
        )


def test_tampered_status_and_stage_packet_fail_closed() -> None:
    status = _status()
    status["gates"][3]["state"] = "SATISFIED"
    with pytest.raises(prom9_protocol.Prom9ProtocolError, match="invalid next-research"):
        prom9_protocol.build_stage_packet(
            protocol=_protocol(),
            protocol_sha256=prom9_protocol.file_sha256(PROTOCOL_PATH),
            status=status,
            stage_id="G0_REAL_PACKS",
            run_id="tampered",
            recorded_at=FIXED_TIME,
        )

    packet = prom9_protocol.build_stage_packet(
        protocol=_protocol(),
        protocol_sha256=prom9_protocol.file_sha256(PROTOCOL_PATH),
        status=_status(),
        stage_id="F1_TYPED_FUNCTION_NETWORK",
        run_id="tampered-packet",
        recorded_at=FIXED_TIME,
    )
    packet["sealed_measurement_allowed"] = True
    with pytest.raises(prom9_protocol.Prom9ProtocolError, match="crossed boundary"):
        prom9_protocol.verify_stage_packet(packet)


def test_write_once_refuses_to_replace_packet(tmp_path: Path) -> None:
    output = tmp_path / "stage.json"
    prom9_protocol._write_once(output, {"ok": True})
    with pytest.raises(prom9_protocol.Prom9ProtocolError, match="refusing to replace"):
        prom9_protocol._write_once(output, {"ok": False})
