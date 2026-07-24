from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

import hswm_next_research_harness as harness


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = "2026-07-24T05:00:00+00:00"


def _plan() -> dict:
    return json.loads((REPO_ROOT / harness.DEFAULT_PLAN).read_text(encoding="utf-8"))


def _by_id(status: dict) -> dict[str, dict]:
    return {row["id"]: row for row in status["gates"]}


def test_current_repository_opens_only_gate0_and_f1() -> None:
    status = harness.build_status(repo_root=REPO_ROOT, recorded_at=FIXED_TIME)
    gates = _by_id(status)

    assert harness.verify_status(status) == status["status_receipt_sha256"]
    assert gates["P1V4_L0_POLICY_ACTUATION_L2"]["state"] == "SATISFIED"
    assert gates["B21_ROUTER_ONLY_FALSIFICATION"]["state"] == "SATISFIED"
    assert gates["B22_BOND_WEIGHT_GROUNDWORK"]["state"] == "SATISFIED"
    assert gates["B22_GATE0_REAL_PACKS"]["state"] == "ACTION_REQUIRED"
    assert gates["P1V5_THREE_FACTOR_BOND_PLASTICITY"]["state"] == "BLOCKED"
    assert gates["F1_MULTI_LLM_FUNCTION_NETWORK"]["state"] == "READY"
    assert [item["id"] for item in status["next_actions"]] == [
        "B22_GATE0_REAL_PACKS",
        "F1_MULTI_LLM_FUNCTION_NETWORK",
    ]
    assert status["scientific_prediction_registered"] is False
    assert status["scientific_verdict_emitted"] is False


def test_p1v4_self_asserted_or_tampered_result_is_refused(tmp_path: Path) -> None:
    source = REPO_ROOT / "receipts/p1v4_policy_lakatotree_result_seed5_r2_20260724.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    value["measurement"]["typed_improvement_count_vs_no_memory"] = 5
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(harness.NextResearchHarnessError, match="self-hash drifted"):
        harness._validate_p1v4_l2_result(tampered)


def test_plan_rejects_forward_dependency_and_duplicate_gate() -> None:
    plan = _plan()
    broken = deepcopy(plan)
    broken["gates"][0]["depends_on"] = ["P4_HOMEOSTASIS_SLEEP_AND_SCALE"]
    with pytest.raises(harness.NextResearchHarnessError, match="missing/forward"):
        harness._validate_plan(broken)

    duplicated = deepcopy(plan)
    duplicated["gates"][1]["id"] = duplicated["gates"][0]["id"]
    with pytest.raises(harness.NextResearchHarnessError, match="duplicate gate"):
        harness._validate_plan(duplicated)


def test_lakatotree_packet_is_draft_and_cannot_submit_science() -> None:
    status = harness.build_status(repo_root=REPO_ROOT, recorded_at=FIXED_TIME)
    packet = harness.build_lakatotree_packet(
        status=status,
        plan=_plan(),
        result_path="/opt/lakatotree/.runtime/research-current/HSWM/receipts/status.json",
    )

    assert packet["tree"] == "LakatosTree_HSWM_20260719"
    assert packet["node_state_expected"] == "DRAFT"
    assert packet["scientific_prediction_registered"] is False
    assert packet["scientific_result_submitted"] is False
    assert "prediction" not in packet
    assert "submit_result" not in packet
    unsigned = dict(packet)
    declared = unsigned.pop("packet_sha256")
    assert declared == harness.canonical_sha256(unsigned)


def test_write_once_refuses_receipt_replacement(tmp_path: Path) -> None:
    path = tmp_path / "receipt.json"
    harness._write_once(path, {"ok": True})
    with pytest.raises(harness.NextResearchHarnessError, match="refusing to replace"):
        harness._write_once(path, {"ok": False})


def test_explicit_invalid_gate0_receipt_fails_closed(tmp_path: Path) -> None:
    invalid = tmp_path / "gate0.json"
    invalid.write_text("{}\n", encoding="utf-8")

    with pytest.raises(harness.NextResearchHarnessError, match="Gate-0 acceptance is invalid"):
        harness.build_status(
            repo_root=REPO_ROOT,
            gate0_acceptance=invalid,
            recorded_at=FIXED_TIME,
        )
