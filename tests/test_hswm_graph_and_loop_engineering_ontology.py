from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from scripts import build_hswm_graph_and_loop_engineering_ontology as builder


ROOT = Path(__file__).resolve().parents[1]
# v6 was published to the live KG on 2026-09-02 and is retained byte-exactly.
# Engineering commits after that date changed some of the sources it bound.
# Under closure stop rule SR-4 those commits do not re-version this bundle,
# so this test checks the retained published snapshot and names the drift
# instead of re-deriving the projection from live bytes.
V6_FILE_SHA256 = "cd510a10ae4f7d534dfd202dce2f7b49fbdc47c207ce5f46244512d96d48c545"
POST_PUBLICATION_SOURCE_DRIFT = {
    "src/hswm/effect-runtime/package-lock.json",
    "src/hswm/effect-runtime/package.json",
    "src/hswm/effect-runtime/test/public-api.test.ts",
    # v6 bound this test file itself; changing the test to a snapshot check
    # necessarily drifts that self-referential pin.
    "tests/test_hswm_graph_and_loop_engineering_ontology.py",
    # 2026-09-06 Effect functional-boundary refactor (commits d9e5c1a..cf7595a):
    # the same contracts, tests and receipts on PosixFileSystem / Effect
    # services; recorded in HSWM_EFFECT_RUNTIME_FP_BOUNDARY_ONTOLOGY.v1.json.
    "src/hswm/effect-runtime/src/canonical-atom-v2-durable-rdf-projection.ts",
    "src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.ts",
    "src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-engineering.ts",
    "src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-job-process.ts",
    "src/hswm/effect-runtime/src/canonical-atom-v2-graph-loop-research-job.ts",
    "src/hswm/effect-runtime/src/canonical-atom-v2-local-permit-commit.ts",
    "src/hswm/effect-runtime/src/canonical-atom-v2-state-journal-file.ts",
    "src/hswm/effect-runtime/src/canonical-atom-v2-verified-admission-gateway.ts",
    "src/hswm/effect-runtime/test/canonical-atom-v2-graph-loop-research-job.test.ts",
}


def test_graph_and_loop_engineering_projection_is_the_retained_published_snapshot() -> None:
    path = ROOT / builder.ONTOLOGY_PATH
    raw = path.read_bytes()
    assert sha256(raw).hexdigest() == V6_FILE_SHA256
    data = json.loads(raw.decode("utf-8"))
    assert raw == builder.encoded_data(data)
    assert data["schema_version"] == builder.SCHEMA_VERSION
    assert data["bundle_uid"] == builder.BUNDLE_UID

    uids = [row["uid"] for row in data["nodes"]] + [row["uid"] for row in data["anchors"]]
    assert not {uid for uid, count in Counter(uids).items() if count > 1}
    owned = {row["uid"] for row in data["nodes"]}
    for relation in data["relations"]:
        assert relation["from_uid"] in owned
        assert relation["to_uid"] in set(uids)
    assert data["expected_counts"]["nodes"] == len(data["nodes"])
    assert data["expected_counts"]["anchors"] == len(data["anchors"])
    assert data["expected_counts"]["relations"] == len(data["relations"])

    drifted = {
        row["path"]
        for row in data["artifact_bindings"]
        if sha256((ROOT / row["path"]).read_bytes()).hexdigest() != row["sha256"]
    }
    assert drifted <= POST_PUBLICATION_SOURCE_DRIFT, drifted
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
