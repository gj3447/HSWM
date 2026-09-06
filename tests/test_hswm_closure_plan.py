from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts import build_hswm_closure_plan_ontology as builder
from scripts import upsert_hswm_closure_plan as publisher


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / builder.ONTOLOGY_PATH


def _data() -> dict:
    return json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))


def _nodes_by_role(data: dict, key: str) -> dict[str, dict]:
    return {
        node["uid"]: node
        for node in data["nodes"]
        if node["properties"].get(key)
    }


def _relation_keys(data: dict) -> set[tuple[str, str, str]]:
    return {(row["from_uid"], row["type"], row["to_uid"]) for row in data["relations"]}


def test_projection_is_deterministic_source_bound_and_valid() -> None:
    data = _data()
    publisher.validate_data(data, ROOT)
    assert data == builder.build_data()
    assert ONTOLOGY_PATH.read_bytes() == builder.encoded_data(data)
    assert data["expected_counts"] == publisher.EXPECTED_COUNTS
    assert builder.canonical_sha(data) == publisher.EXPECTED_PROJECTION_SHA256
    assert sha256(ONTOLOGY_PATH.read_bytes()).hexdigest() == publisher.EXPECTED_FILE_SHA256
    assert data["status"] == builder.STATUS
    assert data["nonclaim"] == builder.NONCLAIM
    for row in data["artifact_bindings"]:
        assert sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]


def test_findings_match_the_bound_audit_json() -> None:
    data = _data()
    findings = json.loads((ROOT / builder.FINDINGS_PATH).read_text(encoding="utf-8"))["findings"]
    claims = {
        node["properties"]["finding_key"]: node
        for node in data["nodes"]
        if node["properties"].get("standard_graph_role") == "CLAIM"
    }
    decisions = {
        node["properties"]["finding_key"]: node
        for node in data["nodes"]
        if node["properties"].get("standard_graph_role") == "DECISION"
    }
    assert list(claims) == [item["key"] for item in findings]
    assert set(decisions) == set(claims)
    assert Counter(item["status"] for item in findings) == Counter(
        {"CONFIRMED": 11, "CONTESTED": 2, "REFUTED": 1}
    )
    relation_keys = _relation_keys(data)
    for item in findings:
        claim = claims[item["key"]]
        decision = decisions[item["key"]]
        assert claim["properties"]["verification_status"] == item["status"]
        assert claim["properties"]["current_decision_uid"] == decision["uid"]
        assert decision["properties"]["assesses_claim_uid"] == claim["uid"]
        assert len(decision["properties"]["refuter_votes"]) == 2
        assert (claim["uid"], "HAS_SOURCE", builder.FINDINGS_UID) in relation_keys
        assert (claim["uid"], "HAS_CONCEPT", decision["uid"]) in relation_keys
        assert (decision["uid"], "CONSTRAINS", claim["uid"]) in relation_keys
        assert (builder.AUDIT_RUN_UID, "TESTS", claim["uid"]) in relation_keys
        assert claim["properties"]["severity_revised"] == min(
            (vote["revised_severity"] for vote in item["votes"]),
            key=lambda value: builder.SEVERITY_ORDER[value],
        )
    refuted = claims["bridge-theorems-satisfied-by-trivial-interpretation"]
    assert decisions["bridge-theorems-satisfied-by-trivial-interpretation"]["properties"][
        "evidence_disposition"
    ] == "RED"
    assert not any(
        key[0] == refuted["uid"] and key[1] in {"BLOCKS", "ASSESSES"} for key in relation_keys
    )
    assert (
        claims["g0-requires-nine-independent-roles-with-no-plan"]["uid"],
        "BLOCKS",
        builder.G0_UID,
    ) in relation_keys


def test_plan_nodes_carry_dates_stop_rules_and_pending_ratification() -> None:
    data = _data()
    steps = _nodes_by_role(data, "step_id")
    assert len(steps) == 6
    orders = sorted(node["properties"]["step_order"] for node in steps.values())
    assert orders == [1, 2, 3, 4, 5, 6]
    relation_keys = _relation_keys(data)
    for node in steps.values():
        props = node["properties"]
        assert props["run_by"] >= "2026-09-08"
        assert props["stop_rule"]
        assert props["verification_commands"]
        assert props["step_kind"] in {"RULE_RELAXATION", "TECHNICAL_WORK", "RESOURCE"}
        if props["needs_user"]:
            assert any(
                key[0] == node["uid"] and key[1] == "DEPENDS_ON" for key in relation_keys
            )
    for before, after in builder.STEP_PRECEDENCE:
        assert (builder.step_uid(before), "PRECEDES", builder.step_uid(after)) in relation_keys
    decisions = {
        node["properties"]["decision_id"]: node for node in _nodes_by_role(data, "decision_id").values()
    }
    assert set(decisions) == {"D-1", "D-2", "D-3", "D-4"}
    for decision_id, node in decisions.items():
        props = node["properties"]
        if decision_id in builder.RATIFIED_DECISIONS:
            source_path = builder.RATIFICATION_SOURCE_BY_DECISION[decision_id]
            source_uid = builder.DELEGATED_SOURCE_UID if source_path == builder.DELEGATED_RATIFICATION_SOURCE_PATH else builder.RATIFICATION_SOURCE_UID
            assert props["ratification_status"] == "RATIFIED"
            assert props["ratification_source_sha256"] == sha256((ROOT / source_path).read_bytes()).hexdigest()
            assert props["ratification_mode"] == builder.RATIFICATION_MODE_BY_DECISION[decision_id]
            assert props["authority_class"] == "USER_PRIMARY"
            assert (node["uid"], "HAS_SOURCE", source_uid) in relation_keys
        else:
            assert props["ratification_status"] == "PROPOSED"
            assert props["ratification_source_sha256"] == ""
            assert props["authority_class"] == "SECONDARY_AI_PROPOSAL_FOR_USER_PRIMARY"
    assert builder.RATIFIED_DECISIONS == ("D-1", "D-3", "D-4")
    assert decisions["D-3"]["properties"]["ratification_mode"].startswith("DELEGATED_CHOICE")
    assert decisions["D-2"]["properties"]["ratification_status"] == "PROPOSED"
    assert (builder.BUNDLE_UID, "SUPERSEDES_AS_FOLLOWUP", builder.PREDECESSOR_BUNDLE_UID) in relation_keys
    assert (builder.PROGRAM_UID, "SUPERSEDES_AS_FOLLOWUP", builder.PREDECESSOR_PROGRAM_UID) in relation_keys
    cap = [node for node in data["nodes"] if node["properties"].get("plan_graph_role") == "BURDEN_CAP"]
    assert len(cap) == 1
    assert cap[0]["properties"]["window_commits"] == 100
    assert cap[0]["properties"]["min_core_share"] == 0.5
    assert cap[0]["properties"]["window_start_commit"] == builder.AUDITED_COMMIT


def test_anchors_are_match_only_and_registered_shapes_hold() -> None:
    data = _data()
    owned = {node["uid"] for node in data["nodes"]}
    anchor_uids = {row["uid"] for row in data["anchors"]}
    assert not owned & anchor_uids
    for row in data["relations"]:
        assert row["from_uid"] in owned
        assert row["to_uid"] in owned | anchor_uids
    subgates = _nodes_by_role(data, "subgate_id")
    assert {node["properties"]["claim_ceiling"] for node in subgates.values()} == {
        "MEASUREMENT_READY_SINGLE_OWNER",
        "DEFERRED_PUBLICATION_GATE",
    }
    relation_keys = _relation_keys(data)
    assert (builder.subgate_uid("G0-LOCAL"), "NARROWS", builder.G0_UID) in relation_keys
    assert (builder.subgate_uid("G0-EXTERNAL"), "DEFERS", builder.G0_UID) in relation_keys
    assert (builder.BUNDLE_UID, "DOES_NOT_ENFORCE", builder.HSWM_UID) in relation_keys
    assert (builder.PROGRAM_UID, "PRESERVES", builder.CAUSAL_PROGRAM_UID) in relation_keys
    types = {row["type"] for row in data["relations"]}
    assert types <= {
        "HAS_CONCEPT", "HAS_SOURCE", "CONSTRAINS", "TARGETS", "TESTS", "PRESERVES",
        "DOES_NOT_ENFORCE", "ASSESSES", "ADDRESSES", "PRECEDES", "BLOCKS", "DEPENDS_ON",
        "MITIGATES", "PROPOSES", "NARROWS", "DEFERS", "AUDITS", "CLOSES",
        "SUPERSEDES_AS_FOLLOWUP",
    }
    labels = {label for node in data["nodes"] for label in node["labels"]}
    assert labels <= {
        "Concept", "Hypothesis", "Guardrail", "AbstractNode", "ResearchArtifact",
        "SourceDocument", "ResearchProgram", "UserCanonicalUtterance",
    }


def test_ratification_v2_snapshot_is_retained_unchanged() -> None:
    v2 = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v2.json"
    assert sha256(v2.read_bytes()).hexdigest() == "0aa237bdea8d71ca7b89a6e66a93f7ba6e97951128ab9b8c7f8947340e95f357"
    data = json.loads(v2.read_text(encoding="utf-8"))
    assert data["bundle_uid"] == "sym:AbstractNode:hswm-closure-plan-ontology-2026-09-05-v2"
    assert all(
        node["properties"]["closure_status"] != "COMPLETED"
        for node in data["nodes"]
        if node["properties"].get("plan_graph_role") == "CLOSURE_STEP"
    )


def test_v3_event_snapshot_is_retained_unchanged() -> None:
    v3 = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v3.json"
    assert sha256(v3.read_bytes()).hexdigest() == "546b9e429e02992a952f6e8535d65c7f832f925b7bf8ace26b490b70f9dab7c2"
    data = json.loads(v3.read_text(encoding="utf-8"))
    assert data["bundle_uid"] == "sym:AbstractNode:hswm-closure-plan-ontology-2026-09-05-v3"


def test_v4_event_snapshot_is_retained_unchanged() -> None:
    v4 = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v4.json"
    assert sha256(v4.read_bytes()).hexdigest() == "d0e4ade085a9d8b0da6a691320220e9793b968ddb6811c52908d52f64200351e"
    data = json.loads(v4.read_text(encoding="utf-8"))
    assert data["bundle_uid"] == builder.PREDECESSOR_BUNDLE_UID
    assert "V1_DONE_STATE_REACHED" not in data["status"]


def test_v5_event_records_the_done_state_as_a_segment_not_reached() -> None:
    data = _data()
    assert builder.DONE_STATE_JUDGMENT["done_state_status"] == "SEGMENT_OBSERVED_BY_V5_RECEIPT_NOT_REACHED"
    assert "V1_DONE_STATE_SEGMENT_OBSERVED_BY_V5_NOT_REACHED" in data["status"]
    done = [node for node in data["nodes"] if node["uid"] == builder.DONE_STATE_UID]
    assert len(done) == 1
    props = done[0]["properties"]
    assert props["done_state_status"] == "SEGMENT_OBSERVED_BY_V5_RECEIPT_NOT_REACHED"
    assert props["ceiling_observed"] != props["ceiling_required"]
    assert any("canonical revision" in item for item in props["criteria_not_satisfied"])
    assert any("held-out" in item for item in props["criteria_not_satisfied"])
    towards_done = [rel for rel in data["relations"] if rel["to_uid"] == builder.DONE_STATE_UID]
    assert towards_done, "the done-state must stay connected"
    for rel in towards_done:
        assert "REACHED_AS" not in json.dumps(rel) and "REACHED_AT" not in json.dumps(rel), rel
    narrowing = [rel for rel in towards_done if rel["from_uid"] == builder.V5_RECEIPT_UID]
    assert len(narrowing) == 1 and narrowing[0]["type"] == "NARROWS"
    steps = {node["properties"]["step_id"]: node["properties"] for node in _nodes_by_role(data, "step_id").values()}
    assert steps["S-5"]["progress_status"] == "PARTIAL_B0_RECOVERED_INCONCLUSIVE_B2_DRAFT_ONLY"
    assert steps["S-5"]["closure_status"] == "PLANNED"
    assert steps["S-6"]["progress_status"] == "DELIVERABLE_A_DONE_DELIVERABLE_B_BLOCKED_ON_USER_WORDS"
    assert steps["S-6"]["progress_blocker"] == "USER_WORDS_ON_SECOND_PARTY"
    assert steps["S-1"]["progress_blocker"] == "USER_WORDS_ON_D2"
    assert "progress_status" not in steps["S-3"]


def test_receipts_mark_s2_s3_s4_complete_without_promotion() -> None:
    data = _data()
    steps = {node["properties"]["step_id"]: node for node in _nodes_by_role(data, "step_id").values()}
    for step_id in ("S-2", "S-3", "S-4"):
        assert steps[step_id]["properties"]["closure_status"] == "COMPLETED", step_id
    assert steps["S-3"]["properties"]["completion_outcome"] == "RUN_COMPLETE_PREREGISTERED_RULE_NOT_MET"
    assert steps["S-4"]["properties"]["completion_outcome"].startswith("D3_RATIFIED_OPTION_A")
    assert all(steps[s]["properties"]["closure_status"] != "COMPLETED" for s in ("S-5",))
    receipts = {node["uid"]: node["properties"] for node in data["nodes"] if node["properties"].get("standard_graph_role") == "QUALIFICATION_RUN" and "closure_step_id" in node["properties"]}
    assert set(receipts) == {builder.V3_RECEIPT_UID, builder.V4_RECEIPT_UID, builder.V5_RECEIPT_UID}
    assert receipts[builder.V3_RECEIPT_UID]["qualification_status"] == "V3_COMPLETE_NO_SEPARATION_NO_EFFICACY_INFERENCE"
    assert receipts[builder.V4_RECEIPT_UID]["qualification_status"] == "V3_COMPLETE_NO_SEPARATION_NO_EFFICACY_INFERENCE"
    assert receipts[builder.V5_RECEIPT_UID]["qualification_status"] == "V3_COMPLETE_G0_LOCAL_IDENTIFIABILITY_OBSERVED_NO_EFFICACY_INFERENCE"
    assert receipts[builder.V5_RECEIPT_UID]["claim_ceiling"] == "MEASUREMENT_READY_SINGLE_OWNER_UNDER_DECLARED_OPAQUE_TASK"
    assert receipts[builder.V5_RECEIPT_UID]["failing_rule_clause"] == "NONE"
    keys = _relation_keys(data)
    for uid in receipts:
        assert (uid, "TESTS", builder.subgate_uid("G0-LOCAL")) in keys
        assert (uid, "PRESERVES", builder.G0_UID) in keys
        assert (uid, "DEPENDS_ON", builder.EFFECT_FP_BUNDLE_UID) in keys
    assert (builder.V5_RECEIPT_UID, "SUPERSEDES_AS_FOLLOWUP", builder.V4_RECEIPT_UID) in keys
    assert "G0_NOT_PASSED_G1_LOCKED" in data["status"] and "SEGMENT_OBSERVED_BY_V5_NOT_REACHED" in data["status"] and "D1_D3_D4_USER_RATIFIED" in data["status"]
    cap = [node for node in data["nodes"] if node["properties"].get("plan_graph_role") == "BURDEN_CAP"][0]
    assert cap["properties"]["reading_core_share"] < cap["properties"]["min_core_share"]


def test_pre_ratification_v1_snapshot_is_retained_unchanged() -> None:
    v1 = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v1.json"
    assert sha256(v1.read_bytes()).hexdigest() == (
        "23def6168a277aa9f1758cbc6fefc4e713388044507e47dd98d4189e987f9e13"
    )
    data = json.loads(v1.read_text(encoding="utf-8"))
    assert data["bundle_uid"] == "sym:AbstractNode:hswm-closure-plan-ontology-2026-09-05"
    assert all(
        node["properties"]["ratification_status"] == "PROPOSED"
        for node in data["nodes"]
        if node["properties"].get("plan_graph_role") == "USER_PRIMARY_DECISION"
    )


def test_drift_is_rejected() -> None:
    data = _data()
    mutated = json.loads(json.dumps(data))
    mutated["nodes"][0]["properties"]["name"] = "drifted"
    with pytest.raises(ValueError, match="deterministic build"):
        publisher.validate_data(mutated, ROOT)
    mutated = json.loads(json.dumps(data))
    mutated["artifact_bindings"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        publisher.validate_data(mutated, ROOT)
