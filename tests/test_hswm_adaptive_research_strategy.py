from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts import build_hswm_adaptive_research_strategy_ontology as builder
from scripts import upsert_hswm_adaptive_research_strategy as publisher


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / builder.ONTOLOGY_PATH


def _data() -> dict:
    return json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))


def _relation_keys(data: dict) -> set[tuple[str, str, str]]:
    return {
        (row["from_uid"], row["type"], row["to_uid"])
        for row in data["relations"]
    }


def test_projection_is_deterministic_source_bound_and_valid() -> None:
    data = _data()

    publisher.validate_data(data, ROOT)

    assert data == builder.build_data()
    assert data["expected_counts"] == publisher.EXPECTED_COUNTS
    assert builder.canonical_sha(data) == publisher.EXPECTED_PROJECTION_SHA256
    assert sha256(ONTOLOGY_PATH.read_bytes()).hexdigest() == publisher.EXPECTED_FILE_SHA256
    assert data["status"] == (
        "TARGET_IDENTITY_FIXED_METHODS_ADAPTIVE_SCIENTIFICALLY_UNJUDGED"
    )


def test_exact_user_source_is_preserved_and_not_promoted_to_evidence() -> None:
    source = ROOT / builder.SOURCE_PATH
    source_digest = "3170c91d233f496185602754b7dd5a10ba2fa6b423e1bc43d77dc0ae996d75cd"
    assert sha256(source.read_bytes()).hexdigest() == source_digest

    data = _data()
    commitment = next(
        row for row in data["nodes"] if row["uid"] == builder.COMMITMENT_UID
    )
    assert commitment["properties"]["authority_class"] == "USER_PRIMARY"
    assert commitment["properties"]["source_sha256"] == source_digest
    assert "not evidence" in commitment["properties"]["claim_boundary"]
    assert all(row["type"] != "EVIDENCE_FOR" for row in data["relations"])


def test_program_preserves_all_fcl_targets_but_not_mechanisms() -> None:
    data = _data()
    relations = _relation_keys(data)
    for fcl_uid in builder.FCL_UIDS.values():
        assert (builder.PROGRAM_UID, "PRESERVES", fcl_uid) in relations

    mechanisms = [
        row
        for row in data["nodes"]
        if "AUXILIARY_HYPOTHESIS_FAMILY"
        in row["properties"]["semantic_roles"]
    ]
    assert len(mechanisms) == 9
    assert all(
        row["properties"]["canonical_scope"]
        == "REVISABLE_AUXILIARY_HYPOTHESIS_FAMILY"
        for row in mechanisms
    )
    assert all(
        row["properties"]["epistemic_state"] == "REPLACEABLE_UNJUDGED"
        for row in mechanisms
    )


def test_red_path_preserves_evidence_and_reenters_through_new_preregistration() -> None:
    data = _data()
    relations = _relation_keys(data)
    state = {
        name: f"sym:Concept:hswm-adaptive-disposition-{name.lower().replace('_', '-')}"
        for name in builder.DISPOSITION_STATES
    }
    assert (state["TESTING"], "NEXT", state["RED_WITHIN_SCOPE"]) in relations
    assert (
        state["RED_WITHIN_SCOPE"],
        "NEXT",
        state["RETIRED_WITH_EVIDENCE_PRESERVED"],
    ) in relations
    assert (
        state["RETIRED_WITH_EVIDENCE_PRESERVED"],
        "NEXT",
        state["REROUTE_PROPOSED"],
    ) in relations
    assert (
        state["REROUTE_PROPOSED"],
        "NEXT",
        state["PREREGISTERED"],
    ) in relations


def test_reroute_requires_falsification_lineage_and_claim_guards() -> None:
    data = _data()
    relations = _relation_keys(data)
    reroute_uid = builder.GUARDRAILS["RG-3"][0]
    for guard_id in ("RG-1", "RG-2", "RG-4", "RG-5", "RG-6"):
        assert (
            reroute_uid,
            "REQUIRES",
            builder.GUARDRAILS[guard_id][0],
        ) in relations


def test_validator_refuses_source_drift_and_efficacy_edge() -> None:
    data = _data()
    data["artifact_bindings"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="artifact binding drifted"):
        publisher.validate_data(data, ROOT)

    data = _data()
    data["relations"][0]["type"] = "EVIDENCE_FOR"
    with pytest.raises(ValueError, match="projection content drifted"):
        publisher.validate_data(data, ROOT)


def test_validator_refuses_partial_target_preservation() -> None:
    data = _data()
    expected = (
        builder.PROGRAM_UID,
        "PRESERVES",
        builder.FCL_UIDS["FCL-8"],
    )
    replacement = copy.deepcopy(data["relations"][0])
    data["relations"] = [
        row
        for row in data["relations"]
        if (row["from_uid"], row["type"], row["to_uid"]) != expected
    ]
    data["relations"].append(replacement)
    with pytest.raises(ValueError, match="projection content drifted"):
        publisher.validate_data(data, ROOT)
