"""Opt-in disposable-Neo4j checks for the bounded common HSWM publisher."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from typing import Any
from uuid import uuid4

import pytest

from hswm.infrastructure import kg_publication_integrity as integrity
from scripts import upsert_hswm_graph_and_loop_engineering as gateway


_ENV = {
    "uri": "HSWM_NEO4J_INTEGRATION_URI",
    "user": "HSWM_NEO4J_INTEGRATION_USERNAME",
    "password": "HSWM_NEO4J_INTEGRATION_PASSWORD",
    "database": "HSWM_NEO4J_INTEGRATION_DATABASE",
}
_missing = [name for name in _ENV.values() if not os.environ.get(name)]
pytestmark = pytest.mark.skipif(
    _missing or os.environ.get("HSWM_NEO4J_DISPOSABLE_TEST") != "1",
    reason=(
        "set HSWM_NEO4J_INTEGRATION_* and HSWM_NEO4J_DISPOSABLE_TEST=1 "
        "for disposable Neo4j publication checks"
    ),
)


def _config() -> dict[str, str]:
    return {key: os.environ[value] for key, value in _ENV.items()}


def _bundle(token: str) -> dict[str, Any]:
    bundle_uid = f"sym:AbstractNode:publication-integrity-{token}"
    first = f"sym:TestPublicationKind:{token}-one"
    second = f"sym:TestPublicationKind:{token}-two"
    return {
        "bundle_uid": bundle_uid,
        "nodes": [
            {
                "uid": first,
                "labels": ["TestPublicationKind"],
                "properties": {"authority_class": "SECONDARY_AI", "name": "first"},
            },
            {
                "uid": second,
                "labels": ["TestPublicationKind"],
                "properties": {"authority_class": "SECONDARY_AI", "name": "second"},
            },
        ],
        "anchors": [
            {
                "uid": integrity.REGISTRY_UID,
                "name": "publication-integrity-registry",
                "required_labels": ["SchemaRegistry"],
            }
        ],
        "relations": [
            {
                "from_uid": first,
                "type": "HAS_CONCEPT",
                "to_uid": second,
                "authority_class": "SECONDARY_AI",
                "scope": "TEST_ONLY",
                "status": "ILLUSTRATIVE",
            }
        ],
    }


@pytest.fixture
def driver() -> Any:
    neo4j = pytest.importorskip("neo4j")
    config = _config()
    opened = neo4j.GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
    registry_token = uuid4().hex
    try:
        with opened.session(database=config["database"]) as session:
            session.run(
                "CREATE CONSTRAINT test_publication_kind_uid IF NOT EXISTS "
                "FOR (n:TestPublicationKind) REQUIRE n.uid IS UNIQUE"
            ).consume()
            session.run(
                "CREATE CONSTRAINT schema_registry_uid IF NOT EXISTS "
                "FOR (n:SchemaRegistry) REQUIRE n.uid IS UNIQUE"
            ).consume()
            session.run(
                "MERGE (r:SchemaRegistry {uid:$uid}) "
                "SET r.name=$name, r.allowed_labels=$labels, r.allowed_reltypes=$relations, "
                "r._hswm_publication_integrity_test_token=$token",
                uid=integrity.REGISTRY_UID,
                name="publication-integrity-registry",
                labels=["TestPublicationKind"],
                relations=["HAS_CONCEPT"],
                token=registry_token,
            ).consume()
        yield opened
    finally:
        with opened.session(database=config["database"]) as session:
            session.run("MATCH (n:TestPublicationKind) DETACH DELETE n").consume()
            session.run(
                "MATCH (r:SchemaRegistry {uid:$uid, _hswm_publication_integrity_test_token:$token}) "
                "DETACH DELETE r",
                uid=integrity.REGISTRY_UID,
                token=registry_token,
            ).consume()
        opened.close()


def test_missing_kind_constraint_refuses_without_creating_nodes(driver: Any) -> None:
    config = _config()
    with driver.session(database=config["database"]) as session:
        session.run("DROP CONSTRAINT test_publication_kind_uid IF EXISTS").consume()
    data = _bundle(uuid4().hex)
    with pytest.raises(integrity.KgPublicationIntegrityError, match="TestPublicationKind"):
        gateway.publish(data, config, "test-digest")
    with driver.session(database=config["database"]) as session:
        count = session.run("MATCH (n {ontology_bundle_uid:$uid}) RETURN count(n) AS count", uid=data["bundle_uid"]).single()["count"]
    assert count == 0


def test_two_publishers_serialize_nodes_and_relationships_and_preserve_registry(driver: Any) -> None:
    config = _config()
    data = _bundle(uuid4().hex)
    with driver.session(database=config["database"]) as session:
        before = dict(session.run("MATCH (r:SchemaRegistry {uid:$uid}) RETURN properties(r) AS properties", uid=integrity.REGISTRY_UID).single()["properties"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _unused: gateway.publish(data, config, "test-digest"), range(2)))

    with driver.session(database=config["database"]) as session:
        after = dict(session.run("MATCH (r:SchemaRegistry {uid:$uid}) RETURN properties(r) AS properties", uid=integrity.REGISTRY_UID).single()["properties"])
        nodes = session.run("MATCH (n {ontology_bundle_uid:$uid}) RETURN count(n) AS count", uid=data["bundle_uid"]).single()["count"]
        relations = session.run("MATCH ()-[r {ontology_bundle_uid:$uid}]->() RETURN count(r) AS count", uid=data["bundle_uid"]).single()["count"]

    assert sorted(result["created_nodes"] for result in results) == [0, 2]
    assert sorted(result["created_relations"] for result in results) == [0, 1]
    assert (nodes, relations) == (2, 1)
    assert after == before


def test_partial_uid_collision_refuses_before_relationship_creation(driver: Any) -> None:
    config = _config()
    data = _bundle(uuid4().hex)
    first = data["nodes"][0]
    with driver.session(database=config["database"]) as session:
        session.run(
            "CREATE (n:TestPublicationKind {uid:$uid, name:'collision'})",
            uid=first["uid"],
        ).consume()
    with pytest.raises(RuntimeError, match="partial pre-existing projection"):
        gateway.publish(data, config, "test-digest")
    with driver.session(database=config["database"]) as session:
        count = session.run("MATCH ()-[r {ontology_bundle_uid:$uid}]->() RETURN count(r) AS count", uid=data["bundle_uid"]).single()["count"]
    assert count == 0
