from __future__ import annotations

from copy import deepcopy

import pytest

from hswm.infrastructure import kg_publication_integrity as integrity


def _data() -> dict[str, object]:
    return {
        "bundle_uid": "sym:AbstractNode:test-publication-bundle",
        "nodes": [
            {
                "uid": "sym:TestKind:one",
                "labels": ["TestKind"],
                "properties": {"authority_class": "SECONDARY_AI"},
            },
            {
                "uid": "sym:TestKind:two",
                "labels": ["TestKind", "Auxiliary"],
                "properties": {"authority_class": "SECONDARY_AI"},
            },
        ],
        "relations": [],
    }


def _constraint(kind: str) -> dict[str, object]:
    return {
        "name": f"{kind.lower()}_uid",
        "type": "UNIQUENESS",
        "entityType": "NODE",
        "labelsOrTypes": [kind],
        "properties": ["uid"],
    }


class _Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def data(self) -> list[dict[str, object]]:
        return self._rows

    def single(self) -> dict[str, object] | None:
        return self._rows[0] if self._rows else None


class _Tx:
    def __init__(self, constraints: list[dict[str, object]]) -> None:
        self.constraints = constraints
        self.registry = {"uid": integrity.REGISTRY_UID, "name": "registry"}
        self.queries: list[str] = []

    def run(self, query: str, **_params: object) -> _Result:
        self.queries.append(query)
        if query.startswith("SHOW CONSTRAINTS"):
            return _Result(self.constraints)
        if "__hswm_publication_transaction_lock" in query:
            return _Result([{"uid": integrity.REGISTRY_UID, "properties": dict(self.registry)}])
        raise AssertionError(query)


def test_uid_kind_label_is_required_for_every_owned_node() -> None:
    data = _data()
    assert integrity.validate_uid_kind_labels(data) == {"TestKind"}

    broken = deepcopy(data)
    broken["nodes"][0]["labels"] = ["Other"]  # type: ignore[index]
    with pytest.raises(integrity.KgPublicationIntegrityError, match="kind label"):
        integrity.validate_uid_kind_labels(broken)

    malformed = deepcopy(data)
    malformed["nodes"][0]["uid"] = "sym:TestKind:"  # type: ignore[index]
    with pytest.raises(integrity.KgPublicationIntegrityError, match="UID kind"):
        integrity.validate_uid_kind_labels(malformed)

    overridden = deepcopy(data)
    overridden["nodes"][0]["properties"]["uid"] = "sym:TestKind:other"  # type: ignore[index]
    with pytest.raises(integrity.KgPublicationIntegrityError, match="cannot override"):
        integrity.validate_uid_kind_labels(overridden)


def test_direct_publication_preflight_keeps_semantic_validation_in_the_gateway_path() -> None:
    broken = _data()
    broken["nodes"][0]["properties"]["current_decision_uid"] = "missing"  # type: ignore[index]
    with pytest.raises(integrity.KgPublicationIntegrityError, match="current_decision_uid"):
        integrity.validate_bundle_for_publication(broken)


def test_missing_kind_constraint_refuses_before_publication() -> None:
    transaction = _Tx([])
    with pytest.raises(integrity.KgPublicationIntegrityError, match="TestKind"):
        integrity.assert_uid_kind_constraints(transaction, _data())
    assert transaction.queries == [
        "SHOW CONSTRAINTS YIELD name, type, entityType, labelsOrTypes, properties "
        "RETURN name, type, entityType, labelsOrTypes, properties"
    ]


def test_exact_uid_uniqueness_constraint_is_accepted() -> None:
    transaction = _Tx([_constraint("TestKind"), _constraint("SchemaRegistry")])
    assert integrity.assert_uid_kind_constraints(transaction, _data()) == {"TestKind"}


def test_modern_neo4j_node_property_uniqueness_constraint_is_accepted() -> None:
    kind_constraint = _constraint("TestKind")
    kind_constraint["type"] = "NODE_PROPERTY_UNIQUENESS"
    registry_constraint = _constraint("SchemaRegistry")
    registry_constraint["type"] = "NODE_PROPERTY_UNIQUENESS"
    transaction = _Tx([kind_constraint, registry_constraint])
    assert integrity.assert_uid_kind_constraints(transaction, _data()) == {"TestKind"}


def test_registry_uid_constraint_is_required_alongside_owned_kind_constraints() -> None:
    transaction = _Tx([_constraint("TestKind")])
    with pytest.raises(integrity.KgPublicationIntegrityError, match="SchemaRegistry"):
        integrity.assert_uid_kind_constraints(transaction, _data())


def test_non_uid_or_non_unique_constraint_does_not_satisfy_identity_preflight() -> None:
    wrong_property = _constraint("TestKind")
    wrong_property["properties"] = ["name"]
    wrong_type = _constraint("TestKind")
    wrong_type["type"] = "NODE_KEY"
    transaction = _Tx([wrong_property, wrong_type, _constraint("SchemaRegistry")])
    with pytest.raises(integrity.KgPublicationIntegrityError, match="missing required"):
        integrity.assert_uid_kind_constraints(transaction, _data())


def test_registry_serialization_keeps_final_properties_identical() -> None:
    transaction = _Tx([])
    before = dict(transaction.registry)
    integrity.serialize_on_schema_registry(transaction)
    assert transaction.registry == before
    assert "SET r.__hswm_publication_transaction_lock" in transaction.queries[0]
    assert "REMOVE r.__hswm_publication_transaction_lock" in transaction.queries[0]
