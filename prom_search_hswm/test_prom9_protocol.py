from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path

import pytest

from prom_search_hswm import prom9_protocol


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / prom9_protocol.DEFAULT_PROTOCOL


def _protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_checked_in_prom9_protocol_is_valid_and_has_no_external_governance() -> None:
    protocol = prom9_protocol.validate_protocol(_protocol())

    assert protocol["status"] == "DESIGN_LOCKED_NOT_PREREGISTERED"
    assert [stage["id"] for stage in protocol["stages"]] == list(
        prom9_protocol.REQUIRED_STAGE_IDS
    )
    assert [function["id"] for function in protocol["llm_functions"]] == list(
        prom9_protocol.REQUIRED_FUNCTION_IDS
    )
    assert "external" in protocol["execution_model"]["evaluator"].lower()
    assert protocol["external_governance"] == {
        "authority": "NONE",
        "prediction_registration_required": False,
        "result_submission_allowed": False,
    }


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
