from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "ontology/evidence/HSWM_ICE_LEARNING_REMEDIATION_2026-09-08.v2.json"
CYPHER = ROOT / "ontology/queries/HSWM_ICE_LEARNING_REMEDIATION_2026-09-08.cypher"
SPARQL = ROOT / "ontology/queries/HSWM_ICE_LEARNING_REMEDIATION_2026-09-08.sparql"
ROOT_UID = "sym:AbstractNode:hswm-ice-learning-remediation-2026-09-08-v2"
V1_UID = "sym:AbstractNode:hswm-ice-learning-remediation-2026-09-08-v1"


def _load() -> dict:
    return json.loads(BUNDLE.read_text(encoding="utf-8"))


def _uid(suffix: str) -> str:
    return f"{ROOT_UID}-{suffix}"


def _edges(data: dict) -> set[tuple[str, str, str]]:
    return {(row["from_uid"], row["type"], row["to_uid"]) for row in data["relations"]}


def _require_semantics(data: dict) -> None:
    edges = _edges(data)
    expected_issue_remedy = {
        "i2": "m1", "i3": "m2", "i4": "m3", "i5": "m5",
    }
    for issue, remedy in expected_issue_remedy.items():
        assert (_uid(issue), "REQUIRES", _uid(remedy)) in edges
    assert (_uid("i1"), "REQUIRES", _uid("e1")) in edges
    assert (_uid("i1"), "REQUIRES", _uid("e2")) in edges
    assert (_uid("i5"), "REQUIRES", _uid("e3")) in edges
    assert (_uid("i6"), "REQUIRES", _uid("scope")) in edges
    assert (_uid("i6"), "REQUIRES", _uid("m1")) in edges
    assert (_uid("m4"), "REQUIRES", _uid("e2")) in edges
    assert (_uid("m3"), "REQUIRES", _uid("e1")) in edges
    assert (_uid("m3"), "REQUIRES", _uid("e2")) not in edges
    for index in range(1, 6):
        assert (_uid(f"f{index}"), "TESTS", _uid(f"m{index}")) in edges
        assert (_uid(f"m{index}"), "TESTS", _uid(f"f{index}")) not in edges
    expected_sources = {
        "i1": (1, 2), "i2": (1, 2, 6), "i3": (6,), "i4": (7,),
        "i5": (1, 2), "i6": (7,), "review": (7, 8),
    }
    for item, sources in expected_sources.items():
        for source in sources:
            assert (_uid(item), "HAS_SOURCE", _uid(f"source-{source}")) in edges

    root = next(row for row in data["nodes"] if row["uid"] == ROOT_UID)["properties"]
    assert root["correction_status"] == "INVALID_SEMANTIC_MAPPING_IN_V1_CORRECTED"
    assert root["supersedes_bundle_uid"] == V1_UID
    assert (ROOT_UID, "REFINES", V1_UID) in edges
    correction = next(row for row in data["nodes"] if row["uid"] == _uid("v1-correction"))["properties"]
    assert correction["status"] == "V1_INVALID_SEMANTIC_MAPPING_SUPERSEDED_BY_V2"
    assert ROOT_UID in correction["description"]

    bindings = {row["path"]: row["sha256"] for row in data["artifact_bindings"]}
    correction_path = "docs/operations/artifacts/ice_learning_remediation_2026-09-08/v1_semantic_correction.json"
    assert correction_path in bindings
    assert sha256((ROOT / correction_path).read_bytes()).hexdigest() == bindings[correction_path]
    assert "ontology/evidence/HSWM_ICE_LEARNING_REMEDIATION_2026-09-08.v1.correction.json" not in bindings


def test_checked_in_v2_semantic_edges_and_source_bindings_are_exact() -> None:
    data = _load()
    assert data["bundle_uid"] == ROOT_UID
    _require_semantics(data)


def test_semantic_contract_rejects_reversed_or_stale_recommendation_edges() -> None:
    data = _load()
    bad_issue = deepcopy(data)
    bad_issue["relations"] = [row for row in bad_issue["relations"] if not (
        row["from_uid"] == _uid("i2") and row["type"] == "REQUIRES" and row["to_uid"] == _uid("m1"))]
    bad_issue["relations"].append({"from_uid": _uid("i2"), "to_uid": _uid("m2"), "type": "REQUIRES", "authority_class": "SECONDARY_AI", "scope": "ICE_LEARNING_REMEDIATION_2026_09_08", "status": "MUTATED"})
    with pytest.raises(AssertionError):
        _require_semantics(bad_issue)

    reversed_test = deepcopy(data)
    reversed_test["relations"] = [row for row in reversed_test["relations"] if not (
        row["from_uid"] == _uid("f1") and row["type"] == "TESTS" and row["to_uid"] == _uid("m1"))]
    reversed_test["relations"].append({"from_uid": _uid("m1"), "to_uid": _uid("f1"), "type": "TESTS", "authority_class": "SECONDARY_AI", "scope": "ICE_LEARNING_REMEDIATION_2026_09_08", "status": "MUTATED"})
    with pytest.raises(AssertionError):
        _require_semantics(reversed_test)


def _require_default_query(query: str) -> None:
    assert ROOT_UID in query
    assert V1_UID not in query
    assert "V1_INVALID_SEMANTIC_MAPPING_SUPERSEDED_BY_V2" in query


def test_semantic_contract_rejects_missing_provenance_reference() -> None:
    data = deepcopy(_load())
    data["relations"] = [row for row in data["relations"] if not (
        row["from_uid"] == _uid("i4") and row["type"] == "HAS_SOURCE" and row["to_uid"] == _uid("source-7"))]
    with pytest.raises(AssertionError):
        _require_semantics(data)


def test_default_queries_select_v2_and_do_not_name_v1_as_current_target() -> None:
    for path in (CYPHER, SPARQL):
        _require_default_query(path.read_text(encoding="utf-8"))


def test_default_query_contract_rejects_obsolete_v1_target() -> None:
    obsolete = CYPHER.read_text(encoding="utf-8").replace(ROOT_UID, V1_UID)
    with pytest.raises(AssertionError):
        _require_default_query(obsolete)
