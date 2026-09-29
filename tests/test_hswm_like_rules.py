"""Source/role corruption and score laundering must be observable failures."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json

import pytest

from scripts import evaluate_hswm_like_rules as rules
from hswm.infrastructure.kg_bundle_graph_view import KgBundleGraphView, KgBundleSource

requires_graph = pytest.mark.skipif(
    importlib.util.find_spec("rdflib") is None or importlib.util.find_spec("pyshacl") is None,
    reason="requires the existing optional graph environment",
)

@pytest.fixture
def rubric():
    return rules.read_json(rules.RUBRIC)


@pytest.fixture
def assessment():
    return rules.read_json(rules.DIRECTORY / "HSWM_LIKE_RULE_ASSESSMENT_TEMPLATE.v1.json")


def filled(assessment):
    result = deepcopy(assessment)
    result["assessment_kind"] = "SYNTHETIC_TEST_NOT_PRODUCTION"
    for row in result["axes"].values():
        row.update(rating=3, evidence=["fixture:representative-case"])
    for row in result["invariants"].values():
        row.update(holds=True, evidence=["fixture:invariant-case"])
    return result


def test_unknown_is_not_a_zero_or_an_unearned_total(assessment, rubric):
    result = rules.score(assessment, rubric)
    assert result["status"] == "INCOMPLETE"
    assert result["score_0_100"] is None
    assert result["assessed_axes"] == 0


def test_submitted_score_retains_evidence_boundary(assessment, rubric):
    result = rules.score(filled(assessment), rubric)
    assert result["score_0_100"] == 75
    assert result["status"] == "SCORED_AS_SUBMITTED"
    assert result["evidence_truth_verified"] is False


def test_violation_cannot_be_averaged_away(assessment, rubric):
    data = filled(assessment)
    data["invariants"]["required_sources_loaded"]["holds"] = False
    result = rules.score(data, rubric)
    assert result["status"] == "INVALID"
    assert result["score_0_100"] is None


def test_one_unknown_prevents_total(assessment, rubric):
    data = filled(assessment)
    data["axes"]["context_activation"]["rating"] = None
    assert rules.score(data, rubric)["score_0_100"] is None


@pytest.mark.parametrize("value", [True, -1, 5, 1.5, "4"])
def test_invalid_rating_rejected(assessment, rubric, value):
    data = filled(assessment)
    data["axes"]["source_fidelity"]["rating"] = value
    with pytest.raises(ValueError, match="Rating"):
        rules.score(data, rubric)


def test_missing_evidence_cannot_claim_observed_zero(assessment, rubric):
    data = filled(assessment)
    data["axes"]["source_fidelity"] = {"rating": 0, "evidence": []}
    with pytest.raises(ValueError, match="requires evidence"):
        rules.score(data, rubric)


@requires_graph
def test_valid_bundle_answers_source_and_role_questions():
    rules.validate_bundle(rules.read_json(rules.BUNDLE))


@requires_graph
def test_source_digest_drift_is_rejected():
    data = rules.read_json(rules.BUNDLE)
    data["artifact_bindings"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Source hash drift"):
        rules.validate_bundle(data)


@requires_graph
def test_ai_interpretation_cannot_be_relabelled_as_primary():
    data = rules.read_json(rules.BUNDLE)
    data["nodes"][0]["properties"].update(authority_class="USER_PRIMARY", ontology_authority_class_v1="USER_PRIMARY")
    with pytest.raises(ValueError, match="exact source text"):
        rules.validate_bundle(data)


@requires_graph
def test_query_detects_changed_role_despite_valid_node_counts():
    data = rules.read_json(rules.BUNDLE)
    part = next(n for n in data["nodes"] if n["properties"].get("role_name") == "exception")
    part["properties"]["role_name"] = "optional_hint"
    with pytest.raises(ValueError, match="competency query"):
        rules.validate_bundle(data)


@requires_graph
def test_domain_range_rejects_navigational_edge_used_as_target():
    data = rules.read_json(rules.BUNDLE)
    edge = next(r for r in data["relations"] if r["type"] == "TARGET")
    edge["to_uid"] = data["bundle_uid"]
    with pytest.raises(ValueError, match="domain/range"):
        rules.validate_bundle(data)


@requires_graph
def test_shacl_rejects_lost_map_source_binding():
    data = rules.read_json(rules.BUNDLE)
    data["relations"] = [r for r in data["relations"] if r["type"] != "BINDS_SOURCE"]
    data["expected_counts"]["relations"] -= 1
    raw = json.dumps(data).encode()
    view = KgBundleGraphView.from_bundles(sources=(KgBundleSource("missing-binding", raw, sha256(raw).hexdigest(), len(raw)),))
    report = view.validate_shacl(shapes=rules.SHAPES.read_bytes())
    assert not report["conforms"]
    assert "BINDS_SOURCE" in report["report_text"]


def test_duplicate_json_keys_are_not_silently_accepted(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"rating": null, "rating": 4}')
    with pytest.raises(ValueError, match="Duplicate"):
        rules.read_json(path)
