"""Contracts for the HSWM causal-composition research and KG projection."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest

from scripts import build_hswm_causal_composition_research_ontology as builder
from scripts import upsert_hswm_causal_composition_research as publisher


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "_research/causal_composition/project.v1.json"
README = ROOT / "_research/causal_composition/README.md"
ONTOLOGY = ROOT / builder.ONTOLOGY_PATH


def _project() -> dict:
    return json.loads(PROJECT.read_text(encoding="utf-8"))


def _data() -> dict:
    return json.loads(ONTOLOGY.read_text(encoding="utf-8"))


def _nodes(data: dict) -> dict[str, dict]:
    return {row["uid"]: row for row in data["nodes"]}


def _relation_keys(data: dict) -> set[tuple[str, str, str]]:
    return {
        (row["from_uid"], row["type"], row["to_uid"])
        for row in data["relations"]
    }


def test_project_contract_has_ordered_gates_controls_and_unjudged_boundary() -> None:
    project = _project()

    assert project["authority"]["scientific_status"] == "UNJUDGED"
    assert project["authority"]["canonical_scope"] == (
        "RESEARCH_PROGRAM_NOT_HSWM_CANON"
    )
    assert [row["id"] for row in project["gates"]] == [
        "G0",
        "G1",
        "G2A",
        "G2B",
        "G3",
        "G4",
        "G5",
        "G6",
    ]
    assert {row["id"] for row in project["control_families"]} == {
        f"CF-{index:02d}" for index in range(1, 15)
    }
    assert {row["id"] for row in project["confound_axes"]} == {
        "RESOURCE",
        "INFORMATION",
        "DECISION_AUTHORITY",
        "STATE",
        "MEASUREMENT",
        "SCALE",
    }
    assert project["immediate_executable_target"]["gate"] == "G1"
    assert project["immediate_executable_target"]["prerequisite"] == "G0"
    assert "NOT_HSWM_COGNITION" in project["nonclaim"]


def test_gate_dependency_is_parallel_at_credit_and_coalition_then_closes() -> None:
    project = _project()
    gates = {row["id"]: row for row in project["gates"]}

    assert gates["G1"]["prerequisites"] == ["G0"]
    assert gates["G2A"]["prerequisites"] == ["G1"]
    assert gates["G2B"]["prerequisites"] == ["G1"]
    assert gates["G3"]["prerequisites"] == ["G2A", "G2B"]
    assert gates["G4"]["prerequisites"] == ["G3"]
    assert gates["G5"]["prerequisites"] == ["G4"]
    assert gates["G6"]["prerequisites"] == ["G5"]
    assert set(gates["G6"]["mapped_fcl_ids"]) == {
        f"FCL-{index}" for index in range(1, 9)
    }
    for gate in gates.values():
        assert gate["exact_intervention"]
        assert gate["pass_rule"]
        assert gate["fail_rule"]
        assert gate["stop_rule"]
        assert gate["claim_ceiling"]


def test_each_control_is_a_metacognitive_contract_not_a_baseline_name() -> None:
    project = _project()
    for control in project["control_families"]:
        assert control["alternative_explanation"]
        assert control["intervention"]
        assert control["intervention_axes"]
        assert control["matched_axes"]
        assert set(control["intervention_axes"]).isdisjoint(
            control["matched_axes"]
        )
        assert control["preserved_factors"]
        assert control["primary_observables"]
        assert control["failure_inference"]
        assert control["claim_ceiling_if_failed"]
        assert control["mapped_fcl_ids"]
    assert set(project["run_contract"]["required_decisions"]) == {
        "PASS",
        "FAIL",
        "INCONCLUSIVE",
    }
    assert project["run_contract"]["one_primary_intervention_family"] is True
    assert project["run_contract"]["other_applicable_axes_held_fixed"] is True
    assert {
        row["id"] for row in project["run_contract"]["artifact_schemas"]
    } == set(builder.RUN_ARTIFACT_UIDS)
    gates = {row["id"]: row for row in project["gates"]}
    assert gates["G4"]["precursor_claim_ceiling"] == (
        "WORLD_SELF_CONTINUITY_COMPONENT_SIGNAL_ONLY"
    )
    assert gates["G5"]["fallback_claim_ceiling"] == (
        "HIERARCHICAL_COORDINATION_WITHOUT_MACRO_CAUSAL_IDENTIFICATION"
    )
    assert gates["G5"]["primary_estimand"] == "TOTAL_MACRO_INTERVENTION_EFFECT"
    assert gates["G5"]["member_eligibility_contract"][
        "required_independent_gate_passes"
    ] == ["G1", "G2A", "G2B", "G3", "G4"]
    assert gates["G4"]["precursor_contract"]["unlock_authorized"] is False
    extensions = {
        row["id"]: row for row in project["run_contract"]["extension_schemas"]
    }
    assert "final_holdout_identity_sha256" in extensions[
        "CF13SelectionEvidence"
    ]["required_fields"]
    assert "rollback_receipt_uid" in extensions["CF14AuthorityEvidence"][
        "required_fields"
    ]
    assert "primary_total_effect_estimand" in extensions[
        "G5MacroIdentificationEvidence"
    ]["required_fields"]
    arm_classes = {row["id"]: row for row in project["control_arm_classes"]}
    assert arm_classes["PRIVILEGED_INFORMATION_ORACLE_UPPER_BOUND"][
        "eligible_for_causal_ranking"
    ] is False
    assert arm_classes["INFORMATION_MATCHED_PAIRWISE_ENCODING"][
        "eligible_for_causal_ranking"
    ] is True
    boundaries = project["run_contract"]["verification_boundaries"]
    assert boundaries["structural_integrity_not_authorship"]["status"] == (
        "EXTERNAL_PUBLIC_PROMOTION_BLOCKED_PENDING_AUTHENTICATED_RECEIPTS"
    )
    assert boundaries["reviewer_assessment_not_recomputed"]["status"] == (
        "REVIEWER_ISSUED_STRUCTURALLY_BOUND_NOT_AUTOMATICALLY_RECOMPUTED"
    )


def test_readme_preserves_claim_order_and_self_deception_guards() -> None:
    text = README.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    for phrase in (
        "G0 measurement integrity",
        "G1 local causal rung",
        "G2a counterfactual multiscale credit",
        "G2b dynamic n-ary coalition",
        "G3 morphogenesis and recovery",
        "G4 world-self and continuity",
        "G5 two-scale composition",
        "G6 replication and scale stress",
        "removal eliminates",
        "A control definition is never a control run",
        "PASS / FAIL / INCONCLUSIVE",
        "SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED",
        "external or public gate promotion is blocked",
        "does not recompute the scientific conclusion",
    ):
        assert phrase in normalized
    assert text.count("`CF-") >= 14
    assert "No `PASS` may be inferred from test count" in text


def test_deterministic_builder_matches_checked_in_projection() -> None:
    data = _data()

    assert data == builder.build_data()
    assert builder.encoded_data(data) == ONTOLOGY.read_bytes()
    assert sha256(ONTOLOGY.read_bytes()).hexdigest() == publisher.EXPECTED_FILE_SHA256


def test_projection_validates_exact_counts_sources_and_content() -> None:
    data = _data()

    publisher.validate_data(data, ROOT)

    assert data["expected_counts"] == publisher.EXPECTED_COUNTS
    assert len(data["nodes"]) == 99
    assert len(data["anchors"]) == 12
    assert len(data["relations"]) == 394
    assert publisher._canonical_sha(data) == publisher.EXPECTED_PROJECTION_SHA256
    assert {
        row["path"] for row in data["artifact_bindings"]
    } == {path.as_posix() for path in builder.SOURCE_BINDING_PATHS}


def test_projection_unfolds_controls_alternatives_axes_and_claim_ceilings() -> None:
    data = _data()
    nodes = _nodes(data)
    relations = _relation_keys(data)

    for control_id, control_uid in builder.CONTROL_UIDS.items():
        properties = nodes[control_uid]["properties"]
        assert properties["control_id"] == control_id
        assert properties["epistemic_state"] == "PROPOSED_TEST"
        assert (
            control_uid,
            "TARGETS",
            builder.ALT_UIDS[control_id],
        ) in relations
        assert (
            control_uid,
            "HAS_CONCEPT",
            builder.CEILING_UIDS[properties["claim_ceiling_if_failed"]],
        ) in relations
        for axis_id in properties["matched_axis_ids"]:
            assert (
                control_uid,
                "PRESERVES",
                builder.AXIS_UIDS[axis_id],
            ) in relations
    for gate_id, gate_uid in builder.GATE_UIDS.items():
        properties = nodes[gate_uid]["properties"]
        assert properties["gate_id"] == gate_id
        assert (
            gate_uid,
            "HAS_CONCEPT",
            builder.CEILING_UIDS[properties["claim_ceiling"]],
        ) in relations
        for control_id in properties["required_control_ids"]:
            assert (
                gate_uid,
                "REQUIRES",
                builder.CONTROL_UIDS[control_id],
            ) in relations
    assert (
        builder.GATE_UIDS["G4"],
        "HAS_CONCEPT",
        builder.CEILING_UIDS["WORLD_SELF_CONTINUITY_COMPONENT_SIGNAL_ONLY"],
    ) in relations
    assert (
        builder.GATE_UIDS["G5"],
        "HAS_CONCEPT",
        builder.CEILING_UIDS[
            "HIERARCHICAL_COORDINATION_WITHOUT_MACRO_CAUSAL_IDENTIFICATION"
        ],
    ) in relations
    for artifact_id, artifact_uid in builder.RUN_ARTIFACT_UIDS.items():
        properties = nodes[artifact_uid]["properties"]
        assert properties["artifact_kind_id"] == artifact_id
        assert properties["epistemic_state"] == "SCHEMA_DEFINITION"
        assert properties["required_fields"]
        assert (
            builder.PROGRAM_UID,
            "HAS_CONCEPT",
            artifact_uid,
        ) in relations
        assert (
            builder.BENCHMARK_UID,
            "REQUIRES",
            artifact_uid,
        ) in relations
    for extension_id, extension_uid in builder.EXTENSION_UIDS.items():
        properties = nodes[extension_uid]["properties"]
        assert properties["extension_schema_id"] == extension_id
        assert properties["required_fields"]
        assert (
            builder.PROGRAM_UID,
            "HAS_CONCEPT",
            extension_uid,
        ) in relations
    for arm_id, arm_uid in builder.CONTROL_ARM_CLASS_UIDS.items():
        properties = nodes[arm_uid]["properties"]
        assert properties["arm_class_id"] == arm_id
        assert isinstance(properties["eligible_for_causal_ranking"], bool)
        assert (
            builder.PROGRAM_UID,
            "HAS_CONCEPT",
            arm_uid,
        ) in relations
    benchmark = nodes[builder.BENCHMARK_UID]["properties"]
    assert benchmark["structural_integrity_boundary_status"] == (
        "EXTERNAL_PUBLIC_PROMOTION_BLOCKED_PENDING_AUTHENTICATED_RECEIPTS"
    )
    assert benchmark["reviewer_assessment_boundary_status"] == (
        "REVIEWER_ISSUED_STRUCTURALLY_BOUND_NOT_AUTOMATICALLY_RECOMPUTED"
    )
    for ceiling_uid in builder.CEILING_UIDS.values():
        properties = nodes[ceiling_uid]["properties"]
        assert properties["external_public_use_status"] == (
            "EXTERNAL_PUBLIC_PROMOTION_BLOCKED_PENDING_AUTHENTICATED_RECEIPTS"
        )
        assert properties["automatic_promotion_status"] == (
            "REVIEWER_ISSUED_STRUCTURALLY_BOUND_NOT_AUTOMATICALLY_RECOMPUTED"
        )
        assert "structurally valid decision" in properties[
            "description"
        ]


def test_all_eight_fcl_laws_are_preserved_without_efficacy_edges() -> None:
    data = _data()
    relations = _relation_keys(data)
    mapped = {
        to_uid
        for from_uid, relation_type, to_uid in relations
        if from_uid in set(builder.GATE_UIDS.values())
        and relation_type == "SPECULATIVE_LINK"
        and to_uid in set(builder.FCL_UIDS.values())
    }

    assert mapped == set(builder.FCL_UIDS.values())
    assert all(
        (builder.PROGRAM_UID, "PRESERVES", fcl_uid) in relations
        for fcl_uid in builder.FCL_UIDS.values()
    )
    assert not any(row["type"] == "EVIDENCE_FOR" for row in data["relations"])


@pytest.mark.parametrize(
    "mutate",
    (
        lambda data: data["nodes"][0]["properties"].pop("responsibility_owner"),
        lambda data: data["nodes"][5]["properties"].pop("stop_rule"),
        lambda data: data["nodes"][20]["properties"].pop("failure_inference"),
        lambda data: data["relations"].append(deepcopy(data["relations"][0])),
        lambda data: data["relations"][0].__setitem__("to_uid", "missing:uid"),
        lambda data: data["artifact_bindings"][0].__setitem__("sha256", "0" * 64),
    ),
)
def test_validator_refuses_owner_falsifier_relation_and_binding_drift(mutate) -> None:
    data = _data()
    mutate(data)
    with pytest.raises(ValueError):
        publisher.validate_data(data, ROOT)


class _Result:
    def __init__(
        self,
        rows: list[dict] = (),
        single: dict | None = None,
    ) -> None:
        self._rows = rows
        self._single = single

    def data(self) -> list[dict]:
        return self._rows

    def single(self) -> dict | None:
        return self._single


class _Tx:
    def __init__(self, responder) -> None:
        self.responder = responder

    def run(self, query: str, **kwargs: object) -> _Result:
        return self.responder(query, kwargs)


def test_publisher_refuses_duplicate_remote_uid_and_schema_drift() -> None:
    duplicate_tx = _Tx(
        lambda _query, _kwargs: _Result(
            rows=[
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


def test_exact_readback_helpers_reject_property_collisions() -> None:
    data = _data()
    row = data["nodes"][0]
    expected = {
        "labels": row["labels"],
        "properties": publisher._expected_node_properties(data, row),
    }
    observed = deepcopy(expected)
    observed["properties"]["epistemic_state"] = "PROVEN"

    with pytest.raises(RuntimeError, match="node property collision"):
        publisher._assert_exact_node(row["uid"], expected, observed)

    relation = data["relations"][0]
    observed_relation = {
        "properties": publisher._expected_relation_properties(data, relation)
    }
    observed_relation["properties"]["status"] = "EVIDENCE"
    with pytest.raises(RuntimeError, match="relationship property collision"):
        publisher._assert_exact_relation(data, relation, observed_relation)


def test_publisher_has_no_merge_or_anchor_write_path() -> None:
    source = (
        ROOT / "scripts/upsert_hswm_causal_composition_research.py"
    ).read_text(encoding="utf-8")

    assert "MERGE (" not in source
    assert "SET anchor" not in source
    assert "CREATE (n:" in source
    assert "refusing a partial pre-existing" in source


class _PublishResult:
    def __init__(self, rows: list[dict] | None = None, single: dict | None = None) -> None:
        self._rows = rows or []
        self._single = single

    def data(self) -> list[dict]:
        return self._rows

    def single(self) -> dict | None:
        return self._single

    def consume(self) -> None:
        return None


class _PublishTx:
    """Minimal Cypher model for the publisher's bounded transaction contract."""

    _LABELS = re.compile(r"CREATE \(n:([A-Za-z_:]+)\)")
    _RELATION = re.compile(r"CREATE \(a\)-\[r:([A-Z0-9_]+)\]->\(b\)")

    def __init__(self, state: dict, trace: list[str], *, bad_final_count: bool = False) -> None:
        self.state = state
        self.trace = trace
        self.bad_final_count = bad_final_count

    def run(self, query: str, **kwargs: object) -> _PublishResult:
        if "SchemaRegistry" in query:
            return _PublishResult(
                single={
                    "labels": self.state["allowed_labels"],
                    "relations": self.state["allowed_reltypes"],
                }
            )
        if "MATCH (n) WHERE n.uid IN $uids" in query:
            rows = []
            for uid in kwargs["uids"]:  # type: ignore[index]
                node = self.state["nodes"].get(uid)  # type: ignore[index]
                if node is not None:
                    rows.append(
                        {
                            "uid": uid,
                            "labels": list(node["labels"]),
                            "properties": deepcopy(node["properties"]),
                        }
                    )
            return _PublishResult(rows=rows)
        if query.startswith("CREATE (n:"):
            self.trace.append("CREATE_NODE")
            labels = self._LABELS.search(query)
            assert labels is not None
            properties = deepcopy(kwargs["properties"])  # type: ignore[index]
            self.state["nodes"][properties["uid"]] = {
                "labels": labels.group(1).split(":"),
                "properties": properties,
            }
            return _PublishResult()
        if "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) " in query and "RETURN properties(r)" in query:
            key = (kwargs["from_uid"], self._relation_type(query), kwargs["to_uid"])
            return _PublishResult(
                rows=[{"properties": deepcopy(properties)} for properties in self.state["relations"].get(key, [])]
            )
        if "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) " in query and "CREATE (a)-[r:" in query:
            self.trace.append("CREATE_RELATION")
            key = (kwargs["from_uid"], self._relation_type(query), kwargs["to_uid"])
            self.state["relations"].setdefault(key, []).append(deepcopy(kwargs["properties"]))
            return _PublishResult()
        if "MATCH (n {ontology_bundle_uid:$uid}) RETURN count(n) AS count" in query:
            count = sum(
                node["properties"].get("ontology_bundle_uid") == kwargs["uid"]
                for node in self.state["nodes"].values()
            )
            if self.bad_final_count:
                count += 1
            return _PublishResult(single={"count": count})
        if "MATCH ()-[r {ontology_bundle_uid:$uid}]->() RETURN count(r) AS count" in query:
            count = sum(
                properties.get("ontology_bundle_uid") == kwargs["uid"]
                for values in self.state["relations"].values()
                for properties in values
            )
            return _PublishResult(single={"count": count})
        raise AssertionError(f"unexpected Cypher in fake publisher transaction: {query}")

    def _relation_type(self, query: str) -> str:
        match = self._RELATION.search(query)
        if match:
            return match.group(1)
        match = re.search(r"MATCH \(a\)-\[r:([A-Z0-9_]+)\]->\(b\)", query)
        assert match is not None
        return match.group(1)


class _PublishSession:
    def __init__(self, database: dict, trace: list[str], *, bad_final_count: bool) -> None:
        self.database = database
        self.trace = trace
        self.bad_final_count = bad_final_count

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute_write(self, callback):
        working = deepcopy(self.database)
        result = callback(_PublishTx(working, self.trace, bad_final_count=self.bad_final_count))
        self.database.clear()
        self.database.update(working)
        return result


class _PublishDriver:
    def __init__(self, database: dict, trace: list[str], *, bad_final_count: bool) -> None:
        self.database = database
        self.trace = trace
        self.bad_final_count = bad_final_count

    def session(self, *, database: str):
        assert database == "kg"
        return _PublishSession(self.database, self.trace, bad_final_count=self.bad_final_count)

    def close(self) -> None:
        return None


def _fake_live_kg(data: dict) -> dict:
    labels = sorted({label for row in data["nodes"] for label in row["labels"]})
    reltypes = sorted({row["type"] for row in data["relations"]})
    return {
        "allowed_labels": labels,
        "allowed_reltypes": reltypes,
        "nodes": {
            row["uid"]: {"labels": list(row["required_labels"]), "properties": {"name": row["name"]}}
            for row in data["anchors"]
        },
        "relations": {},
    }


def _install_fake_neo4j(monkeypatch: pytest.MonkeyPatch, database: dict, trace: list[str], *, bad_final_count: bool = False) -> None:
    class _GraphDatabase:
        @staticmethod
        def driver(_uri: str, auth: tuple[str, str]) -> _PublishDriver:
            assert auth == ("writer", "secret")
            return _PublishDriver(database, trace, bad_final_count=bad_final_count)

    monkeypatch.setitem(sys.modules, "neo4j", SimpleNamespace(GraphDatabase=_GraphDatabase))


def _owned_counts(database: dict, bundle_uid: str) -> tuple[int, int]:
    return (
        sum(node["properties"].get("ontology_bundle_uid") == bundle_uid for node in database["nodes"].values()),
        sum(
            properties.get("ontology_bundle_uid") == bundle_uid
            for values in database["relations"].values()
            for properties in values
        ),
    )


def test_publish_then_idempotent_republish_has_exact_owned_readback(monkeypatch: pytest.MonkeyPatch) -> None:
    data = _data()
    database, trace = _fake_live_kg(data), []
    _install_fake_neo4j(monkeypatch, database, trace)
    config = {"uri": "bolt://fake", "user": "writer", "password": "secret", "database": "kg"}

    first = publisher.publish(data, config)
    second = publisher.publish(data, config)

    assert first["created_nodes"] == len(data["nodes"])
    assert first["created_relations"] == len(data["relations"])
    assert second["created_nodes"] == second["created_relations"] == 0
    assert second["readback_nodes"] == len(data["nodes"])
    assert second["readback_relations"] == len(data["relations"])
    assert _owned_counts(database, data["bundle_uid"]) == (len(data["nodes"]), len(data["relations"]))
    assert trace.count("CREATE_NODE") == len(data["nodes"])
    assert trace.count("CREATE_RELATION") == len(data["relations"])


@pytest.mark.parametrize("drift", ("missing", "labels"))
def test_publish_rejects_missing_or_drifted_anchor_before_any_write(monkeypatch: pytest.MonkeyPatch, drift: str) -> None:
    data = _data()
    database, trace = _fake_live_kg(data), []
    anchor = data["anchors"][0]
    if drift == "missing":
        del database["nodes"][anchor["uid"]]
        match = "anchors are missing"
    else:
        database["nodes"][anchor["uid"]]["labels"] = []
        match = "anchor label drifted"
    _install_fake_neo4j(monkeypatch, database, trace)

    with pytest.raises(RuntimeError, match=match):
        publisher.publish(data, {"uri": "bolt://fake", "user": "writer", "password": "secret", "database": "kg"})

    assert trace == []
    assert _owned_counts(database, data["bundle_uid"]) == (0, 0)


def test_publish_rejects_partial_owned_nodes_before_any_write(monkeypatch: pytest.MonkeyPatch) -> None:
    data = _data()
    database, trace = _fake_live_kg(data), []
    row = data["nodes"][0]
    database["nodes"][row["uid"]] = {
        "labels": list(row["labels"]),
        "properties": publisher._expected_node_properties(data, row),
    }
    _install_fake_neo4j(monkeypatch, database, trace)

    with pytest.raises(RuntimeError, match="partial pre-existing causal-composition projection"):
        publisher.publish(data, {"uri": "bolt://fake", "user": "writer", "password": "secret", "database": "kg"})

    assert trace == []
    assert _owned_counts(database, data["bundle_uid"]) == (1, 0)


def test_publish_rejects_all_nodes_with_partial_relations_before_any_write(monkeypatch: pytest.MonkeyPatch) -> None:
    data = _data()
    database, trace = _fake_live_kg(data), []
    for row in data["nodes"]:
        database["nodes"][row["uid"]] = {
            "labels": list(row["labels"]),
            "properties": publisher._expected_node_properties(data, row),
        }
    relation = data["relations"][0]
    key = (relation["from_uid"], relation["type"], relation["to_uid"])
    database["relations"][key] = [publisher._expected_relation_properties(data, relation)]
    _install_fake_neo4j(monkeypatch, database, trace)

    with pytest.raises(RuntimeError, match="partial pre-existing causal-composition relation set"):
        publisher.publish(data, {"uri": "bolt://fake", "user": "writer", "password": "secret", "database": "kg"})

    assert trace == []
    assert _owned_counts(database, data["bundle_uid"]) == (len(data["nodes"]), 1)


def test_publish_rolls_back_when_final_owned_count_readback_mismatches(monkeypatch: pytest.MonkeyPatch) -> None:
    data = _data()
    database, trace = _fake_live_kg(data), []
    _install_fake_neo4j(monkeypatch, database, trace, bad_final_count=True)

    with pytest.raises(RuntimeError, match="ownership readback drifted"):
        publisher.publish(data, {"uri": "bolt://fake", "user": "writer", "password": "secret", "database": "kg"})

    assert trace.count("CREATE_NODE") == len(data["nodes"])
    assert trace.count("CREATE_RELATION") == len(data["relations"])
    assert _owned_counts(database, data["bundle_uid"]) == (0, 0)
