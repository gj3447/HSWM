"""Contract tests for the source-expanded HSWM fractal scientific ontology."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import upsert_hswm_fractal_scientific_connections as publisher


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = (
    ROOT
    / "ontology/identity/human_universal_body/"
    "HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_ONTOLOGY.v1.json"
)
RESEARCH = ROOT / "docs/research/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md"


def _data() -> dict[str, object]:
    return json.loads(ONTOLOGY.read_text(encoding="utf-8"))


def _nodes(data: dict[str, object]) -> dict[str, dict[str, object]]:
    return {row["uid"]: row for row in data["nodes"]}


def _relation_keys(data: dict[str, object]) -> set[tuple[str, str, str, str, str]]:
    return {
        (
            row["from_uid"],
            row["type"],
            row["to_uid"],
            row["authority_class"],
            row["status"],
        )
        for row in data["relations"]
    }


def test_scientific_projection_validates_exact_content_and_bound_sources() -> None:
    data = _data()
    publisher.validate_data(data, ROOT)
    assert data["expected_counts"] == publisher.EXPECTED_COUNTS
    assert hashlib.sha256(RESEARCH.read_bytes()).hexdigest() == data["research_sha256"]
    anchor = ROOT / data["anchor_projection_path"]
    assert hashlib.sha256(anchor.read_bytes()).hexdigest() == data["anchor_projection_sha256"]
    assert data["status"] == "SCIENTIFICALLY_CONNECTED_INTEGRATED_CLAIM_UNJUDGED"
    assert "NOT_HSWM_COGNITION" in data["nonclaim"]


def test_sixteen_primary_sources_expand_content_instead_of_storing_urls_only() -> None:
    data = _data()
    sources = [row for row in data["nodes"] if "AcademicPaper" in row["labels"]]
    assert len(sources) == 16
    assert len({row["properties"]["source_url"] for row in sources}) == 16
    for row in sources:
        properties = row["properties"]
        assert properties["authority_class"] == "EXTERNAL_PRIMARY_SOURCE_REPORTED"
        assert properties["epistemic_state"] == "LITERATURE_REPORTED"
        assert properties["canonical_scope"] == "EXTERNAL_LITERATURE_NOT_HSWM_CANON"
        assert all(
            isinstance(properties.get(key), str) and len(properties[key]) >= 20
            for key in (
                "reported_object",
                "reported_dynamics",
                "reported_scope",
                "limitations",
                "claim_boundary",
            )
        )


def test_reported_constructs_and_hswm_bridges_have_different_authority() -> None:
    data = _data()
    nodes = _nodes(data)
    constructs = {
        uid for uid, row in nodes.items() if "ExternalTheory" in row["labels"]
    }
    bridges = {uid for uid, row in nodes.items() if "BridgeConcept" in row["labels"]}
    assert len(constructs) == 18
    assert len(bridges) == 10
    for uid in constructs:
        assert nodes[uid]["properties"]["authority_class"] == "EXTERNAL_PRIMARY_SOURCE_REPORTED"
        assert nodes[uid]["properties"]["epistemic_state"] == "LITERATURE_REPORTED"
    for uid in bridges:
        properties = nodes[uid]["properties"]
        assert properties["authority_class"] == "SECONDARY_AI"
        assert properties["epistemic_state"] == "WORKING_HYPOTHESIS"
        assert all(
            properties.get(key)
            for key in (
                "supported_component",
                "hswm_extension",
                "unresolved_delta",
                "testable_prediction",
                "failure_observation",
                "mapped_fcl_ids",
            )
        )
    interpretation = [
        row
        for row in data["relations"]
        if row["from_uid"] in constructs and row["to_uid"] in bridges
    ]
    assert interpretation
    assert all(
        row["type"] == "THEORETICAL_BASIS_FOR"
        and row["authority_class"] == "SECONDARY_AI"
        and row["status"] == "WORKING_HYPOTHESIS"
        for row in interpretation
    )


def test_core_scientific_paths_are_explicit_atoms_and_typed_relations() -> None:
    rows = _relation_keys(_data())
    reported = "EXTERNAL_PRIMARY_SOURCE_REPORTED"
    working = "SECONDARY_AI"
    assert (
        "sym:AcademicPaper:mcmillen-levin-collective-intelligence-2024",
        "HAS_CONCEPT",
        "sym:Concept:scientific-prior-multiscale-competency-architecture",
        reported,
        "REPORTED",
    ) in rows
    assert (
        "sym:Concept:scientific-prior-multiscale-competency-architecture",
        "THEORETICAL_BASIS_FOR",
        "sym:Concept:hswm-scientific-bridge-functional-cognitive-scale-closure",
        working,
        "WORKING_HYPOTHESIS",
    ) in rows
    assert (
        "sym:Concept:hswm-scientific-bridge-functional-cognitive-scale-closure",
        "SPECULATIVE_LINK",
        "sym:Concept:hswm-fractal-law-composition-preservation",
        working,
        "WORKING_HYPOTHESIS",
    ) in rows
    assert (
        "sym:Concept:scientific-prior-operadic-wiring-self-similarity",
        "THEORETICAL_BASIS_FOR",
        "sym:Concept:hswm-scientific-bridge-same-type-operational-composition",
        working,
        "WORKING_HYPOTHESIS",
    ) in rows
    assert (
        "sym:Concept:scientific-prior-intervention-effective-causal-emergence",
        "THEORETICAL_BASIS_FOR",
        "sym:Concept:hswm-scientific-bridge-macro-causal-individuation",
        working,
        "WORKING_HYPOTHESIS",
    ) in rows
    assert (
        "sym:Concept:scientific-prior-nested-markov-blanket-formation",
        "THEORETICAL_BASIS_FOR",
        "sym:Concept:hswm-scientific-bridge-joint-world-self-boundary-model",
        working,
        "WORKING_HYPOTHESIS",
    ) in rows


def test_all_eight_laws_are_covered_and_every_bridge_has_a_null() -> None:
    data = _data()
    nodes = _nodes(data)
    bridges = {uid for uid, row in nodes.items() if "BridgeConcept" in row["labels"]}
    mapped = {
        row["to_uid"]
        for row in data["relations"]
        if row["from_uid"] in bridges and row["type"] == "SPECULATIVE_LINK"
    }
    tested = {
        row["to_uid"]
        for row in data["relations"]
        if row["from_uid"].startswith("sym:Hypothesis:hswm-fractal-null-")
        and row["type"] == "TESTS"
    }
    assert mapped == publisher.FCL_UIDS
    assert tested == bridges
    assert not any(row["type"] == "EVIDENCE_FOR" for row in data["relations"])


def test_research_document_states_three_closures_and_non_equivalences() -> None:
    text = RESEARCH.read_text(encoding="utf-8")
    for phrase in (
        "기능적 다중규모 폐쇄",
        "형식적 합성 폐쇄",
        "인과적 거시 폐쇄",
        "GNW의 뇌 의식 이론을 HSWM 의식 주장으로 옮기지 않는다",
        "Markov blanket은 관측된 conditional independence",
        "과거 task 성능 보존은 주체성이나 학습 계보의 연속성이 아니다",
        "SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED",
    ):
        assert phrase in text
    assert text.count("https://") >= 16


@pytest.mark.parametrize(
    "mutate",
    (
        lambda data: data["nodes"][0]["properties"].pop("responsibility_owner"),
        lambda data: data["nodes"][2]["properties"].pop("reported_dynamics"),
        lambda data: data["nodes"][-1]["properties"].pop("rejection_rule"),
        lambda data: data["relations"].append(deepcopy(data["relations"][0])),
        lambda data: data["relations"][0].__setitem__("to_uid", "missing:uid"),
        lambda data: data.__setitem__("research_sha256", "0" * 64),
    ),
)
def test_validator_refuses_source_owner_content_relation_and_hash_drift(mutate) -> None:
    data = _data()
    mutate(data)
    with pytest.raises(ValueError):
        publisher.validate_data(data, ROOT)


class _Result:
    def __init__(
        self,
        rows: list[dict[str, object]] = (),
        single: dict[str, object] | None = None,
    ) -> None:
        self._rows = rows
        self._single = single

    def data(self) -> list[dict[str, object]]:
        return self._rows

    def single(self) -> dict[str, object] | None:
        return self._single


class _Tx:
    def __init__(self, responder) -> None:
        self.responder = responder

    def run(self, query: str, **kwargs: object) -> _Result:
        return self.responder(query, kwargs)


def test_publisher_refuses_duplicate_uid_schema_and_property_collision() -> None:
    duplicate_tx = _Tx(
        lambda _query, _kwargs: _Result(
            [
                {"uid": "duplicate", "labels": [], "properties": {}},
                {"uid": "duplicate", "labels": [], "properties": {}},
            ]
        )
    )
    with pytest.raises(RuntimeError, match="duplicate remote KG UIDs"):
        publisher._find_unique_nodes(duplicate_tx, ["duplicate"])

    registry_tx = _Tx(
        lambda _query, _kwargs: _Result(
            single={"labels": ["Concept"], "relations": ["HAS_SOURCE"]}
        )
    )
    with pytest.raises(RuntimeError, match="unregistered schema tokens"):
        publisher._registry_readback(registry_tx, _data())

    data = _data()
    row = data["nodes"][0]
    expected = {
        "labels": row["labels"],
        "properties": publisher._expected_node_properties(data, row),
    }
    observed = deepcopy(expected)
    observed["properties"]["responsibility_owner"] = "wrong_owner"
    with pytest.raises(RuntimeError, match="node property collision"):
        publisher._assert_exact_node(row["uid"], expected, observed)
