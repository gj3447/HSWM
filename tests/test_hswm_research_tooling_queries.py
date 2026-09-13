from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from hswm.infrastructure import research_tooling_projection as projection
from hswm.infrastructure.kg_bundle_graph_view import KgBundleGraphView, KgBundleSource


ROOT = Path(__file__).resolve().parents[1]


def _view(bundle: dict) -> KgBundleGraphView:
    raw = projection.encode(bundle)
    return KgBundleGraphView.from_bundles(
        sources=(KgBundleSource("research-tooling-query-test", raw, sha256(raw).hexdigest(), len(raw)),),
        profile="v2",
    )


def _rows(view: KgBundleGraphView, filename: str) -> list[dict]:
    result = projection.plain(
        view.query((ROOT / projection.QUERIES / filename).read_text())
    )
    return [{key: value["value"] for key, value in row.items()} for row in result]


@pytest.fixture(scope="module")
def compiled_bundle() -> dict:
    _, bundle = projection.compile_snapshot(ROOT)
    return bundle


def test_research_tooling_query_pack_answers_declared_navigation_questions(
    compiled_bundle: dict,
) -> None:
    view = _view(compiled_bundle)
    q1 = _rows(view, "Q1_candidate_decisions_and_priority.sparql")
    assert len(q1) == 35
    assert {row["qualificationStatus"] for row in q1} == {"PROPOSED_NOT_EXECUTED"}

    q2 = _rows(view, "Q2_existing_reuse_mappings.sparql")
    capability_ids = {row["capabilityId"] for row in q2}
    expected_capability_ids = {
        node["properties"]["source_id"]
        for node in compiled_bundle["nodes"]
        if node["properties"]["standard_graph_role"] == "EXISTING_CAPABILITY"
    }
    assert capability_ids
    assert capability_ids <= expected_capability_ids
    assert all(capability_id.startswith("CAP-") for capability_id in capability_ids)

    q3 = _rows(view, "Q3_experimental_development_specs.sparql")
    assert {row["candidateId"] for row in q3} == {
        "rdf12", "sparql12", "shacl12", "genai-semconv"
    }

    q4 = _rows(view, "Q4_requirement_qualification.sparql")
    assert {row["requirementId"] for row in q4} == {
        "REQ-G0-EXTERNAL", "REQ-D4-CAUSAL-LOOP", "REQ-RU1-PREREGISTRATION",
        "REQ-ICE-LEARNER", "REQ-CONSTRUCTIVE-WITNESS", "REQ-MULTISCALE-EFFECT",
        "REQ-REPRODUCIBLE-PACKAGE", "REQ-RUN-LINEAGE",
    }
    assert {row["qualificationStatus"] for row in q4} == {"PROPOSED_NOT_EXECUTED"}


def test_q6_detects_candidate_whose_source_edges_are_removed(compiled_bundle: dict) -> None:
    mutated = deepcopy(compiled_bundle)
    candidate = next(
        node for node in mutated["nodes"]
        if node["properties"]["standard_graph_role"] == "TOOL_CANDIDATE"
        and node["properties"]["source_id"] == "genai-semconv"
    )
    mutated["relations"] = [
        relation for relation in mutated["relations"]
        if not (relation["from_uid"] == candidate["uid"] and relation["type"] == "HAS_SOURCE")
    ]
    mutated["expected_counts"]["relations"] = len(mutated["relations"])
    rows = _rows(_view(mutated), "Q6_missing_source_assessment_orphan_refs.sparql")
    assert {tuple(sorted(row.items())) for row in rows} == {
        (("issue", "CANDIDATE_WITHOUT_SOURCE"), ("itemId", "genai-semconv"))
    }
