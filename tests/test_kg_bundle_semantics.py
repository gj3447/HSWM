from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from hswm.infrastructure.kg_bundle_semantics import (
    KgBundleSemanticError,
    validate_bundle_semantics,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "ontology/identity/hswm_core/HSWM_HYPERGRAPH_LEARNING_PLAN_ONTOLOGY.v1.json"
WORKSHOP = ROOT / "ontology/identity/hswm_core/HSWM_WORKSHOP_C1_C3_ONTOLOGY.v1.json"


def _data(path: Path) -> dict:
    return json.loads(path.read_text())


def test_known_source_revision_inventories_and_semantics_conform() -> None:
    validate_bundle_semantics(_data(PLAN))
    validate_bundle_semantics(_data(WORKSHOP))


@pytest.mark.parametrize("replacement", (None, "UNCLASSIFIED"))
def test_known_plan_rejects_role_erasure_or_unclassified_escape(replacement: str | None) -> None:
    data = _data(PLAN)
    assertion = next(
        node for node in data["nodes"]
        if node["properties"]["standard_graph_role"] == "LEARNING_ASSERTION"
    )
    if replacement is None:
        del assertion["properties"]["standard_graph_role"]
    else:
        assertion["properties"]["standard_graph_role"] = replacement
    data["relations"] = [
        row for row in data["relations"]
        if row["from_uid"] != assertion["uid"] or row["type"] != "HAS_PARTICIPATION"
    ]
    with pytest.raises(KgBundleSemanticError, match="(standard_graph_role|UNCLASSIFIED)"):
        validate_bundle_semantics(data)


def test_discovery_authority_cannot_conflict_with_raw_authority() -> None:
    data = _data(PLAN)
    node = data["nodes"][0]
    node["properties"]["ontology_authority_class_v1"] = "USER_PRIMARY"
    with pytest.raises(KgBundleSemanticError, match="conflicts"):
        validate_bundle_semantics(data)


def test_participation_ordinal_is_unique_only_within_each_assertion() -> None:
    data = _data(PLAN)
    participants = [
        node for node in data["nodes"]
        if node["properties"]["standard_graph_role"] == "ROLE_PARTICIPATION"
        and "local-learning-p" in node["uid"]
    ]
    participants[1]["properties"]["ordinal"] = participants[0]["properties"]["ordinal"]
    with pytest.raises(KgBundleSemanticError, match="ordinal must be unique"):
        validate_bundle_semantics(data)


def test_authored_scene_cannot_be_promoted_to_observed_result() -> None:
    data = _data(WORKSHOP)
    scene = next(
        node for node in data["nodes"]
        if node["properties"]["standard_graph_role"] == "AUTHORED_SCENE"
    )
    scene["properties"]["status"] = "OBSERVED_SUCCESS"
    with pytest.raises(KgBundleSemanticError, match="cannot be promoted"):
        validate_bundle_semantics(data)


def _claim_decision_bundle() -> dict:
    return {
        "schema_version": "test-semantic-contract/v1",
        "nodes": [
            {"uid": "sym:Concept:claim", "properties": {
                "standard_graph_role": "CLAIM", "authority_class": "SECONDARY_AI",
                "current_decision_uid": "sym:Concept:decision",
            }},
            {"uid": "sym:Concept:decision", "properties": {
                "standard_graph_role": "DECISION", "authority_class": "SECONDARY_AI",
                "assesses_claim_uid": "sym:Concept:claim",
            }},
        ],
        "relations": [{
            "from_uid": "sym:Concept:claim", "type": "HAS_CONCEPT",
            "to_uid": "sym:Concept:decision",
        }],
    }


def test_current_decision_requires_existing_matching_decision_and_relation() -> None:
    data = _claim_decision_bundle()
    validate_bundle_semantics(data)
    broken = deepcopy(data)
    broken["nodes"][0]["properties"]["current_decision_uid"] = "sym:Concept:missing"
    with pytest.raises(KgBundleSemanticError, match="does not identify"):
        validate_bundle_semantics(broken)
    broken = deepcopy(data)
    broken["relations"] = []
    with pytest.raises(KgBundleSemanticError, match="HAS_CONCEPT"):
        validate_bundle_semantics(broken)
