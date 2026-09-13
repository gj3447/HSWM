from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from hswm.infrastructure import research_tooling_projection as projection


ROOT = Path(__file__).resolve().parents[1]


def _prepared_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    directory = tmp_path / "inputs"
    directory.mkdir()
    original = ROOT / projection.INPUT
    for name in projection.FILES[:3]:
        (directory / name).write_bytes((original / name).read_bytes())
    findings = [json.loads((directory / name).read_text()) for name in projection.FILES[1:3]]
    (directory / projection.FILES[3]).write_text(json.dumps({"authority": "SECONDARY_AI", "as_of": "2026-09-13", "sources": [], "candidates": []}))
    candidates = [row for finding in findings for row in finding["candidates"]]
    assessments = [
        {"candidate_id": row["id"], "decision": "PROPOSED_EVALUATION", "requirement_ids": [],
         "existing_capability_ids": [], "reason": "Source-bound test assessment.",
         "adoption_evidence_class": "SOURCE_REPORTED", "qualification": {
             "id": "Q-" + row["id"], "title": "Qualification", "priority": "P1",
             "acceptance": "Review evidence.", "trigger": "Before use.", "status": "PROPOSED_NOT_EXECUTED"}}
        for row in candidates
    ]
    (directory / projection.FILES[4]).write_text(json.dumps({"authority": "SECONDARY_AI", "as_of": "2026-09-13", "source_commit": projection.CUT, "conceptual_delta": "Test projection.", "assessments": assessments}))
    for relative in (projection.QUERIES, Path("src/hswm/infrastructure/research_tooling_projection.py"),
                     Path("src/hswm/infrastructure/kg_bundle_graph_view.py"),
                     Path("schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl")):
        source, target = ROOT / relative, tmp_path / relative
        if source.is_dir(): shutil.copytree(source, target)
        else: target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(source.read_bytes())
    real_blob = projection.blob
    monkeypatch.setattr(projection, "INPUT", Path("inputs"))
    monkeypatch.setattr(projection, "blob", lambda path, root=ROOT: real_blob(path, ROOT))
    return {"directory": directory, "assessments": assessments}


def test_compiled_projection_is_source_scoped_and_has_public_secondary_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = _prepared_inputs(tmp_path, monkeypatch)
    _, bundle = projection.compile_snapshot(tmp_path)
    roles = {node["properties"]["standard_graph_role"] for node in bundle["nodes"]}
    assert {"RESEARCH_TOOLING_ROOT", "EXISTING_CAPABILITY", "RESEARCH_REQUIREMENT", "RESEARCH_SOURCE",
            "TOOL_CANDIDATE", "ADOPTION_EVIDENCE", "INTEGRATED_ASSESSMENT", "QUALIFICATION",
            "FIXED_GIT_SOURCE_DESCRIPTOR"} <= roles
    candidates = [node for node in bundle["nodes"] if node["properties"]["standard_graph_role"] == "TOOL_CANDIDATE"]
    assert len(candidates) == len(prepared["assessments"])
    for node in bundle["nodes"]:
        props = node["properties"]
        assert (props["ontology_sensitivity_v1"], props["ontology_record_lifecycle_v1"], props["ontology_epistemic_state_v1"]) == ("NORMAL", "ACTIVE", "PENDING")
        assert props["authority_class"] == "SECONDARY_AI" and props["ontology_canonical_scope_v1"] == "AI_ANALYSIS_NOT_USER_RATIFIED"


def test_candidate_missing_official_source_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = _prepared_inputs(tmp_path, monkeypatch)
    path = prepared["directory"] / projection.FILES[1]
    finding = json.loads(path.read_text()); finding["candidates"][0]["source_ids"].append("not-a-source")
    path.write_text(json.dumps(finding))
    with pytest.raises(ValueError, match="missing official source"):
        projection.compile_snapshot(tmp_path)


def test_assessment_dangling_requirement_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = _prepared_inputs(tmp_path, monkeypatch)
    path = prepared["directory"] / projection.FILES[4]
    assessment = json.loads(path.read_text()); assessment["assessments"][0]["requirement_ids"] = ["REQ-MISSING"]
    path.write_text(json.dumps(assessment))
    with pytest.raises(ValueError, match="dangling requirement"):
        projection.compile_snapshot(tmp_path)


def test_draft_analysis_cannot_be_reclassified_as_adoption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = _prepared_inputs(tmp_path, monkeypatch)
    path = prepared["directory"] / projection.FILES[4]
    assessment = json.loads(path.read_text()); assessment["assessments"][0]["decision"] = "ADOPTED"
    path.write_text(json.dumps(assessment))
    with pytest.raises(ValueError, match="cannot be promoted"):
        projection.compile_snapshot(tmp_path)


def test_broken_curation_pointer_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _prepared_inputs(tmp_path, monkeypatch)
    _, bundle = projection.compile_snapshot(tmp_path)
    bundle["nodes"][0]["properties"]["curation_source_pointer"] = "/no/such/input"
    with pytest.raises(ValueError, match="invalid curation pointer"):
        projection.validate_curation_pointers(bundle["nodes"], tmp_path)


def test_experimental_spec_cannot_be_misclassified_as_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = _prepared_inputs(tmp_path, monkeypatch)
    path = prepared["directory"] / projection.FILES[1]
    finding = json.loads(path.read_text())
    finding["candidates"][0]["release_lane"] = "EXPERIMENTAL"
    path.write_text(json.dumps(finding))
    with pytest.raises(ValueError, match="experimental lane"):
        projection.compile_snapshot(tmp_path)


def test_research_catalog_cannot_complete_unexecuted_qualification(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = _prepared_inputs(tmp_path, monkeypatch)
    path = prepared["directory"] / projection.FILES[4]
    assessment = json.loads(path.read_text())
    assessment["assessments"][0]["qualification"]["status"] = "PASSED"
    path.write_text(json.dumps(assessment))
    with pytest.raises(ValueError, match="cannot mark qualification executed"):
        projection.compile_snapshot(tmp_path)
