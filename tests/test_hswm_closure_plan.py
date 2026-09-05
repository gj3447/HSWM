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
    decisions = _nodes_by_role(data, "decision_id")
    assert set(node["properties"]["decision_id"] for node in decisions.values()) == {
        "D-1", "D-2", "D-3", "D-4"
    }
    for node in decisions.values():
        assert node["properties"]["ratification_status"] == "PROPOSED"
        assert node["properties"]["ratification_source_sha256"] == ""
        assert node["properties"]["authority_class"] == "SECONDARY_AI_PROPOSAL_FOR_USER_PRIMARY"
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
    }
    labels = {label for node in data["nodes"] for label in node["labels"]}
    assert labels <= {
        "Concept", "Hypothesis", "Guardrail", "AbstractNode", "ResearchArtifact",
        "SourceDocument", "ResearchProgram",
    }


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
