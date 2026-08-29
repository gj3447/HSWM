from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = (
    ROOT / "ontology/identity/hswm_core/HSWM_RAGNAROK_PIDNA_RESEARCH_ONTOLOGY.v1.json"
)
SCRIPT_PATH = ROOT / "scripts/upsert_hswm_ragnarok_pidna_research.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "ragnarok_pidna_publisher", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _data() -> dict:
    return json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))


def test_projection_and_bound_projects_validate() -> None:
    module = _load_module()
    data = _data()

    module.validate_data(data, ROOT)

    assert data["status"] == "RESEARCH_PROJECTS_INITIALIZED_INTEGRATED_CLAIMS_UNJUDGED"
    assert data["expected_counts"] == {
        "nodes": 31,
        "anchors": 10,
        "relations": 78,
        "projects": 2,
        "hypotheses": 9,
        "source_records": 9,
    }
    assert module._projection_digest(data) == module.EXPECTED_PROJECTION_SHA256


def test_project_manifests_keep_science_unjudged_and_experiments_falsifiable() -> None:
    expected = {
        "ragnarok": ({"RAG-H1", "RAG-H2", "RAG-H3", "RAG-H4"}, 4),
        "pidna": ({"PID-H1", "PID-H2", "PID-H3", "PID-H4", "PID-H5"}, 5),
    }
    for name, (hypothesis_ids, experiment_count) in expected.items():
        manifest = json.loads(
            (ROOT / f"_research/{name}/project.v1.json").read_text(encoding="utf-8")
        )
        assert manifest["authority"]["scientific_status"] == "UNJUDGED"
        assert {row["id"] for row in manifest["hypotheses"]} == hypothesis_ids
        assert len(manifest["experiments"]) == experiment_count
        assert all(row["reject_when"] for row in manifest["hypotheses"])
        assert all(row["claim_ceiling"] for row in manifest["experiments"])
        assert manifest["fcl_scope"]["mapped"] == [
            "FCL-1",
            "FCL-2",
            "FCL-3",
            "FCL-4",
            "FCL-5",
            "FCL-7",
            "FCL-8",
        ]
        assert manifest["fcl_scope"]["out_of_scope"] == ["FCL-6"]


def test_historical_pidna_sources_remain_read_only_non_dependencies() -> None:
    module = _load_module()
    data = _data()
    assert {
        row["path_identity"]: row["sha256"] for row in data["historical_source_digests"]
    } == module.EXPECTED_HISTORICAL_DIGESTS
    assert all(
        row["availability"]
        == "LOCAL_RETIRED_ARCHIVE_READ_ONLY_NOT_REPOSITORY_DEPENDENCY"
        for row in data["historical_source_digests"]
    )
    pidna_readme = (ROOT / "_research/pidna/README.md").read_text(encoding="utf-8")
    assert "not copied back into this repository" in pidna_readme
    assert "deleted governance services" in pidna_readme


def test_validator_rejects_bound_artifact_drift() -> None:
    module = _load_module()
    data = _data()
    data["artifact_bindings"][0]["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="artifact binding drifted"):
        module.validate_data(data, ROOT)


def test_validator_rejects_hypothesis_overclaim_and_efficacy_edge() -> None:
    module = _load_module()
    data = _data()
    hypothesis = next(row for row in data["nodes"] if "Hypothesis" in row["labels"])
    hypothesis["properties"]["epistemic_state"] = "PROVEN"

    with pytest.raises(
        ValueError,
        match="Hypothesis scientific state overclaims|hypothesis scientific state overclaims",
    ):
        module.validate_data(data, ROOT)

    data = _data()
    data["relations"][0]["type"] = "EVIDENCE_FOR"
    with pytest.raises(ValueError, match="may not claim HSWM efficacy evidence"):
        module.validate_data(data, ROOT)


def test_validator_rejects_pidna_ragnarok_coupling_drift() -> None:
    module = _load_module()
    data = _data()
    data["relations"] = [
        row
        for row in data["relations"]
        if not (
            row["from_uid"] == "sym:Hypothesis:pidna-anti-ragnarok-verification"
            and row["to_uid"] == "sym:DomainEvent:lx3_ragnarok"
        )
    ]
    data["relations"].append(copy.deepcopy(data["relations"][0]))
    replacement = data["relations"][-1]
    replacement.update(
        {
            "from_uid": "sym:Hypothesis:pidna-anti-ragnarok-verification",
            "type": "SPECULATIVE_LINK",
            "to_uid": "sym:Concept:hswm",
            "authority_class": "SECONDARY_AI",
            "scope": "RAGNAROK_COUPLING",
            "status": "WORKING_HYPOTHESIS",
        }
    )

    with pytest.raises(ValueError, match="anti-Ragnarok coupling drifted"):
        module.validate_data(data, ROOT)


def test_validator_pins_non_hypothesis_claim_contract() -> None:
    module = _load_module()
    data = _data()
    source = next(
        row
        for row in data["nodes"]
        if row["uid"] == "sym:SourceDocument:sculley-hidden-technical-debt-2015"
    )
    source["properties"]["claim_boundary"] = "This proves HSWM efficacy."
    source["properties"]["authority_class"] = "CANONICAL"

    with pytest.raises(ValueError, match="projection content digest drifted"):
        module.validate_data(data, ROOT)


def test_validator_requires_exactly_one_project_owner_per_hypothesis() -> None:
    module = _load_module()
    data = _data()
    replacement = next(
        row
        for row in data["relations"]
        if row["from_uid"] == data["bundle_uid"]
        and row["to_uid"] == "sym:Concept:pidna-pure-intelligence-dna"
    )
    replacement.update(
        {
            "from_uid": "sym:ResearchProgram:hswm-ragnarok-research-2026-08-29",
            "type": "HAS_CONCEPT",
            "to_uid": "sym:Hypothesis:pidna-paired-cycle-advantage",
            "authority_class": "SECONDARY_AI",
            "scope": "RESEARCH_PROGRAM",
            "status": "PROPOSED",
        }
    )

    with pytest.raises(ValueError, match="exactly one research project"):
        module.validate_data(data, ROOT)


def test_exact_previous_upgrade_contract_is_narrow_and_auditable() -> None:
    module = _load_module()
    data = _data()
    previous = module._previous_relations(data)
    current_keys = {module._relation_key(row) for row in data["relations"]}
    previous_keys = {module._relation_key(row) for row in previous}

    assert len(previous) == 69
    assert current_keys - previous_keys == module.UPGRADE_ADDED_RELATION_KEYS
    pidna = next(row for row in data["nodes"] if row["uid"] == module.PIDNA_CONCEPT_UID)
    assert pidna["labels"] == ["Concept", "BridgeConcept"]
    assert module._previous_node_contract(data, pidna)["labels"] == [
        "Concept",
        "CanonicalDefinition",
    ]
    assert module._publication_status({"upgraded_nodes": 31}) == (
        "UPGRADED_EXACT_PREVIOUS_PROJECTION"
    )
    assert module._publication_status({"created_nodes": 31}) == "APPLIED_NEW_PROJECTION"
    assert module._publication_status({"created_nodes": 0}) == (
        "VERIFIED_EXISTING_PROJECTION"
    )
