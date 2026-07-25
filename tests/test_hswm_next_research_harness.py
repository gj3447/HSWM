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


def _rehash_judgment(value: dict) -> dict:
    unsigned = dict(value)
    unsigned.pop("judgment_sha256", None)
    value["judgment_sha256"] = harness.canonical_sha256(unsigned)
    return value


def test_current_repository_exposes_only_f1_parity_repair() -> None:
    status = harness.build_status(repo_root=REPO_ROOT, recorded_at=FIXED_TIME)
    gates = _by_id(status)

    assert harness.verify_status(status) == status["status_receipt_sha256"]
    assert gates["P1V4_L0_POLICY_ACTUATION_L2"]["state"] == "SATISFIED"
    assert gates["B21_ROUTER_ONLY_FALSIFICATION"]["state"] == "SATISFIED"
    assert gates["B22_BOND_WEIGHT_GROUNDWORK"]["state"] == "SATISFIED"
    assert gates["F1_MULTI_LLM_FUNCTION_NETWORK"]["state"] == "ACTION_REQUIRED"
    assert gates["F1_MULTI_LLM_FUNCTION_NETWORK"]["evidence"]["gates"]["equal_budget"] is False
    assert gates["B22_GATE0_REAL_PACKS"]["state"] == "BLOCKED"
    assert gates["P1V5_THREE_FACTOR_BOND_PLASTICITY"]["state"] == "BLOCKED"
    assert gates["P2_AGENT_A_TO_FROZEN_B_TRANSFER"]["state"] == "BLOCKED"
    assert gates["P3_SINGLE_TYPED_TOPOLOGY_OPERATION"]["state"] == "BLOCKED"
    assert status["active_gate"]["id"] == "F1_MULTI_LLM_FUNCTION_NETWORK"
    assert [item["id"] for item in status["next_actions"]] == [
        "F1_MULTI_LLM_FUNCTION_NETWORK"
    ]
    assert status["sequence_locked"] is True
    assert status["scientific_prediction_registered"] is False
    assert status["scientific_verdict_emitted"] is False


def test_f1_classifier_requires_sealed_conjunction_and_n100() -> None:
    path = REPO_ROOT / "_research/prom9_runs/f1-2wiki-dev-r4/judgment.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["mode"] = "sealed"
    value["verdict"] = "F1_SUPPORTED_NARROW"
    value["parity_failures"] = []
    for key in value["gates"]:
        value["gates"][key] = True
    for metric in value["metrics"].values():
        metric["n"] = 100
    state, evidence = harness._classify_f1_judgment(_rehash_judgment(value))

    assert state == "SATISFIED"
    assert evidence["sample_gate"] is True
    assert evidence["disposition"] == "F1_SUPPORTED_NARROW_REVALIDATED"

    for metric in value["metrics"].values():
        metric["n"] = 99
    state, evidence = harness._classify_f1_judgment(_rehash_judgment(value))
    assert state == "ACTION_REQUIRED"
    assert evidence["disposition"] == "F1_SEALED_SAMPLE_TOO_SMALL"


def test_f1_tamper_is_refused() -> None:
    path = REPO_ROOT / "_research/prom9_runs/f1-2wiki-dev-r4/judgment.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["gates"]["equal_budget"] = True
    with pytest.raises(harness.NextResearchHarnessError, match="self-hash drifted"):
        harness._classify_f1_judgment(value)


def test_out_of_order_gate_evidence_is_refused(tmp_path: Path) -> None:
    dummy = tmp_path / "not-open-yet.json"
    with pytest.raises(harness.NextResearchHarnessError, match="out-of-order"):
        harness.build_status(
            repo_root=REPO_ROOT,
            p1v5_packet=dummy,
            recorded_at=FIXED_TIME,
        )


def test_sequence_unlocks_one_gate_at_a_time(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dummy = tmp_path / "evidence.json"
    dummy.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        harness,
        "_validate_f1_evidence",
        lambda **_: ("SATISFIED", {"disposition": "test-f1-supported"}),
    )
    monkeypatch.setattr(
        harness,
        "_validate_gate0_acceptance",
        lambda _: {"disposition": "test-gate0-accepted"},
    )

    weight_frontier = harness.build_status(
        repo_root=REPO_ROOT,
        gate0_acceptance=dummy,
        recorded_at=FIXED_TIME,
    )
    assert weight_frontier["active_gate"]["id"] == "P1V5_THREE_FACTOR_BOND_PLASTICITY"

    monkeypatch.setattr(
        harness,
        "_validate_p1v5_packet",
        lambda _: ("SATISFIED", {"disposition": "test-p1v5-supported"}),
    )
    transfer_frontier = harness.build_status(
        repo_root=REPO_ROOT,
        gate0_acceptance=dummy,
        p1v5_packet=dummy,
        recorded_at=FIXED_TIME,
    )
    assert transfer_frontier["active_gate"]["id"] == "P2_AGENT_A_TO_FROZEN_B_TRANSFER"

    monkeypatch.setattr(
        harness,
        "_validate_p2_packet",
        lambda _: ("SATISFIED", {"disposition": "test-p2-supported"}),
    )
    topology_frontier = harness.build_status(
        repo_root=REPO_ROOT,
        gate0_acceptance=dummy,
        p1v5_packet=dummy,
        p2_packet=dummy,
        recorded_at=FIXED_TIME,
    )
    assert topology_frontier["active_gate"]["id"] == "P3_SINGLE_TYPED_TOPOLOGY_OPERATION"


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


def test_explicit_invalid_gate0_receipt_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        harness,
        "_validate_f1_evidence",
        lambda **_: ("SATISFIED", {"disposition": "test-f1-supported"}),
    )
    invalid = tmp_path / "gate0.json"
    invalid.write_text("{}\n", encoding="utf-8")

    with pytest.raises(harness.NextResearchHarnessError, match="Gate-0 acceptance is invalid"):
        harness.build_status(
            repo_root=REPO_ROOT,
            gate0_acceptance=invalid,
            recorded_at=FIXED_TIME,
        )
