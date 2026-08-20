from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import upsert_hswm_swm0r_evidence as publisher


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = (
    ROOT
    / "ontology"
    / "identity"
    / "human_universal_body"
    / "HSWM_SWM0R_EVIDENCE_BUNDLE.v1.json"
)


@pytest.fixture(scope="module")
def validated() -> publisher.ValidatedBundle:
    return publisher.validate_bundle(
        BUNDLE,
        ROOT,
        require_tracked_head=False,
        verify_replay=True,
    )


def test_live_bundle_validates_all_bytes_and_exact_replay(validated) -> None:
    assert len(validated.artifact_hashes) == 12
    assert len(validated.expected_nodes) == 6
    assert len(validated.expected_relations) == 17
    assert validated.replay_sha256 == dict(validated.artifact_hashes)[publisher.RAW_RESULT_PATH]
    assert validated.internal["verdict"] == "PASS"


def test_bundle_uses_one_read_only_secondary_anchor() -> None:
    data = publisher.load_json(BUNDLE)
    assert data["anchors"] == [
        {
            "uid": publisher.ANCHOR_UID,
            "labels": ["Plan", "ImplementationPlan"],
            "properties": {
                "name": "SWM-0 — n-ary non-collapse witness",
                "authority_class": "SECONDARY_AI",
                "implementation_stage": "SWM-0",
            },
            "read_only": True,
        }
    ]
    assert publisher.ANCHOR_UID not in {row["uid"] for row in data["nodes"]}


def test_new_nodes_never_claim_user_primary_authority() -> None:
    data = publisher.load_json(BUNDLE)
    assert {row["properties"]["authority_class"] for row in data["nodes"]} == {
        "SECONDARY_AI"
    }
    assert all(
        row["properties"].get("scientific_status", "UNJUDGED") == "UNJUDGED"
        for row in data["nodes"]
    )
    assert all(
        row["properties"].get("learned_operator_claim", False) is False
        for row in data["nodes"]
    )


def test_only_frozen_registry_tokens_are_used() -> None:
    data = publisher.load_json(BUNDLE)
    labels = {label for row in data["nodes"] for label in row["labels"]}
    relations = {row["type"] for row in data["relations"]}
    assert labels <= publisher.FROZEN_LABELS
    assert relations <= publisher.FROZEN_RELTYPES
    assert relations == {
        "BINDS",
        "CONTAINS",
        "DERIVED_FROM",
        "EVIDENCE_FOR",
        "PRODUCED_BY",
        "REQUIRES",
        "TARGETS",
        "VALIDATES",
    }


def test_artifact_bindings_are_exact_current_file_hashes() -> None:
    data = publisher.load_json(BUNDLE)
    for row in data["artifact_bindings"]:
        assert publisher.file_sha256(ROOT / row["path"]) == row["sha256"]


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema":"a","schema":"b"}', encoding="utf-8")
    with pytest.raises(publisher.SWM0REvidenceError, match="duplicate JSON key"):
        publisher.load_json(path)


def test_binding_set_rejects_digest_or_role_drift() -> None:
    data = publisher.load_json(BUNDLE)
    changed_digest = deepcopy(data)
    changed_digest["artifact_bindings"][0]["sha256"] = "0" * 64
    with pytest.raises(publisher.SWM0REvidenceError, match="artifact_set_sha256"):
        publisher._binding_map(changed_digest)

    changed_role = deepcopy(data)
    changed_role["artifact_bindings"][0]["role"] = "USER_PRIMARY"
    with pytest.raises(publisher.SWM0REvidenceError, match="paths or roles"):
        publisher._binding_map(changed_role)


def test_raw_internal_digest_tamper_is_rejected() -> None:
    raw = publisher.load_json(ROOT / publisher.RAW_RESULT_PATH)
    raw["result"]["scientific_status"] = "ESTABLISHED"
    with pytest.raises(publisher.SWM0REvidenceError, match="(bundle|result)_sha256"):
        publisher._validate_internal_hashes(raw)


def test_repository_path_escape_and_symlink_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(publisher.SWM0REvidenceError, match="normalized repository path"):
        publisher._resolve_repo_file(ROOT, "../outside", "test path")
    target = tmp_path / "target"
    target.write_text("x", encoding="utf-8")
    link = ROOT / "swm0r-ontology-test-link"
    try:
        link.symlink_to(target)
        with pytest.raises(publisher.SWM0REvidenceError, match="escapes or is missing"):
            publisher._resolve_repo_file(ROOT, link.name, "test path")
    finally:
        link.unlink(missing_ok=True)


def test_neo4j_property_validator_rejects_null_and_mixed_arrays() -> None:
    assert publisher._is_neo4j_property(["a", "b"])
    assert publisher._is_neo4j_property([])
    assert not publisher._is_neo4j_property(None)
    assert not publisher._is_neo4j_property(["a", 1])
    assert not publisher._is_neo4j_property({"nested": "map"})


def test_exact_node_idempotence_allows_only_created_at() -> None:
    expected = {"uid": "sym:Artifact:test", "name": "test"}
    publisher.assert_exact_node(
        "sym:Artifact:test",
        ["AbstractNode", "Artifact"],
        expected,
        ["Artifact", "AbstractNode"],
        {**expected, "createdAt": "server timestamp"},
    )
    with pytest.raises(publisher.SWM0REvidenceError, match="property collision"):
        publisher.assert_exact_node(
            "sym:Artifact:test",
            ["AbstractNode", "Artifact"],
            expected,
            ["AbstractNode", "Artifact"],
            {**expected, "foreign": True},
        )


def test_exact_relation_idempotence_rejects_foreign_ownership() -> None:
    key = ("sym:A:a", "BINDS", "sym:B:b")
    expected = {"ontology_bundle_uid": publisher.BUNDLE_UID, "status": "ACTIVE"}
    publisher.assert_exact_relation(
        key, expected, {**expected, "createdAt": "server timestamp"}
    )
    with pytest.raises(publisher.SWM0REvidenceError, match="collision"):
        publisher.assert_exact_relation(
            key,
            expected,
            {**expected, "ontology_bundle_uid": "sym:foreign"},
        )


def test_publisher_contains_no_merge_or_property_overlay_write() -> None:
    source = (ROOT / publisher.PUBLISHER_PATH).read_text(encoding="utf-8")
    assert "MERGE (" not in source
    assert " n +=" not in source
    assert " r +=" not in source
    assert "SET n=$properties" in source
    assert "SET r=$properties" in source


def test_validation_output_is_json_serializable(validated) -> None:
    payload = {
        "artifact_set_sha256": validated.artifact_set_sha256,
        "bundle_file_sha256": validated.bundle_file_sha256,
        "nodes": len(validated.expected_nodes),
        "relations": len(validated.expected_relations),
    }
    assert json.loads(json.dumps(payload)) == payload
