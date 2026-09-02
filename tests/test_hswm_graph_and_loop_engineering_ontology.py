from __future__ import annotations

import json
from pathlib import Path

from scripts import build_hswm_graph_and_loop_engineering_ontology as builder
from scripts import upsert_hswm_graph_and_loop_engineering as publisher


ROOT = Path(__file__).resolve().parents[1]


def test_graph_and_loop_engineering_projection_is_deterministic_and_current() -> None:
    data = builder.build_data()

    builder.validate_data(data)
    publisher.validate_data(data)

    path = ROOT / builder.ONTOLOGY_PATH
    assert path.read_bytes() == builder.encoded_data(data)
    assert json.loads(path.read_text(encoding="utf-8")) == data
    assert data["expected_counts"]["external_source_records"] == len(
        builder.EXTERNAL_SOURCES
    )
    assert data["expected_counts"]["gates"] == len(builder.GATES)
    assert data["expected_counts"]["proof_claims"] == len(builder.PROOF_STATUSES)
    assert data["expected_counts"]["proof_decisions"] == len(
        builder.PROOF_STATUSES
    )
    assert data["expected_counts"]["qualification_runs"] == len(
        builder.QUALIFICATION_RUNS
    )

    claims = {
        node["properties"]["proof_status_id"]: node
        for node in data["nodes"]
        if node["properties"].get("standard_graph_role") == "CLAIM"
    }
    decisions = {
        node["properties"]["proof_status_id"]: node
        for node in data["nodes"]
        if node["properties"].get("standard_graph_role") == "DECISION"
    }
    expected_status_ids = {f"PS-{index}" for index in range(1, 7)}
    assert set(claims) == expected_status_ids
    assert set(decisions) == expected_status_ids
    assert decisions["PS-1"]["properties"]["summary_bucket"] == "FORMAL_MODEL_PROVED"
    assert (
        decisions["PS-2"]["properties"]["summary_bucket"]
        == "LOCAL_ENGINEERING_SUPPORTED"
    )
    assert (
        decisions["PS-4"]["properties"]["summary_bucket"]
        == "LOCAL_ENGINEERING_SUPPORTED"
    )
    assert {
        decisions[status_id]["properties"]["summary_bucket"]
        for status_id in ("PS-3", "PS-5", "PS-6")
    } == {"CORE_UNPROVED"}

    relations = data["relations"]
    nodes_by_uid = {node["uid"]: node for node in data["nodes"]}
    for item in builder.PROOF_STATUSES:
        status_id = item["status_id"]
        claim_uid = builder._proof_claim_uid(item["slug"])
        decision_uid = builder._proof_decision_uid(item["slug"])
        claim = claims[status_id]
        decision = decisions[status_id]
        assert claim["uid"] == claim_uid
        assert decision["uid"] == decision_uid
        assert claim["properties"]["current_decision_uid"] == decision_uid
        assert decision["properties"]["assesses_claim_uid"] == claim_uid

        current_decision_edges = [
            relation
            for relation in relations
            if relation["from_uid"] == claim_uid
            and relation["type"] == "HAS_CONCEPT"
            and relation["scope"] == "CURRENT_STATUS_DECISION"
        ]
        assert [relation["to_uid"] for relation in current_decision_edges] == [
            decision_uid
        ]

        evidence_edges = {
            relation["to_uid"]
            for relation in relations
            if relation["from_uid"] == claim_uid
            and relation["type"] == "HAS_SOURCE"
            and relation["scope"] == "CLAIM_EVIDENCE_SOURCE"
        }
        expected_evidence = {
            builder._local_source_uid(path) for path in item["sources"]
        }
        assert evidence_edges == expected_evidence
        assert set(claim["properties"]["evidence_source_uids"]) == expected_evidence
        assert {
            nodes_by_uid[uid]["properties"]["standard_graph_role"]
            for uid in evidence_edges
        } == {"EVIDENCE_ARTIFACT"}

        gap_edges = {
            relation["to_uid"]
            for relation in relations
            if relation["from_uid"] == claim_uid
            and relation["type"] == "TARGETS"
            and relation["scope"] == "OPEN_CLAIM_GAP"
        }
        expected_gaps = (
            set() if item["gap"] is None else {builder._gap_uid(item["gap"])}
        )
        assert gap_edges == expected_gaps
        assert claim["properties"]["open_gap_uid"] == (
            "" if item["gap"] is None else builder._gap_uid(item["gap"])
        )

    qualification_nodes = {
        node["properties"]["qualification_run_id"]: node
        for node in data["nodes"]
        if node["properties"].get("standard_graph_role") == "QUALIFICATION_RUN"
    }
    assert set(qualification_nodes) == {"QR-1", "QR-2", "QR-3"}
    for item in builder.QUALIFICATION_RUNS:
        run_uid = builder._qualification_run_uid(item["slug"])
        assert qualification_nodes[item["run_id"]]["uid"] == run_uid
        run_sources = {
            relation["to_uid"]
            for relation in relations
            if relation["from_uid"] == run_uid
            and relation["type"] == "HAS_SOURCE"
            and relation["scope"] == "QUALIFICATION_INPUT_SNAPSHOT"
        }
        assert run_sources == {
            builder._local_source_uid(path) for path in item["sources"]
        }
        tested = {
            relation["to_uid"]
            for relation in relations
            if relation["from_uid"] == run_uid
            and relation["type"] == "TESTS"
            and relation["scope"] == "LOCAL_REPRODUCIBILITY_QUALIFICATION"
        }
        assert tested == (
            {builder._proof_claim_uid(slug) for slug in item["qualified_claims"]}
            or {builder.BUNDLE_UID}
        )
