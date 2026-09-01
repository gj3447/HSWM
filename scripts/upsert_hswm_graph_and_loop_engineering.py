#!/usr/bin/env python3
"""Validate and explicitly publish the graph-and-loop engineering projection."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from scripts import build_hswm_graph_and_loop_engineering_ontology as builder


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / builder.ONTOLOGY_PATH
REGISTRY_UID = "sym:KG_INFRA:schema-registry-v1-2026-08-03"
SAFE_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
SAFE_RELATION = re.compile(r"[A-Z_][A-Z0-9_]*\Z")


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def read_flat_yaml(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if ":" in raw and not raw.lstrip().startswith("#"):
            key, value = raw.split(":", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    if {"uri", "user", "password", "database"} - values.keys():
        raise ValueError("source config is incomplete")
    return values


def _neo4j_property(value: Any) -> bool:
    return isinstance(value, (str, bool, int, float)) or (
        isinstance(value, list)
        and all(isinstance(item, (str, bool, int, float)) for item in value)
    )


def validate_data(data: dict[str, Any], repo_root: Path = ROOT) -> None:
    """Reject source, graph, schema, or claim-boundary drift before publication."""

    builder.validate_data(data)
    if data != builder.build_data():
        raise ValueError("projection is not the deterministic build")

    nodes = data["nodes"]
    anchors = data["anchors"]
    relations = data["relations"]
    for row in anchors:
        if (
            set(row) != {"uid", "name", "required_labels"}
            or not isinstance(row["uid"], str)
            or not row["uid"]
            or not isinstance(row["name"], str)
            or not row["name"]
            or not isinstance(row["required_labels"], list)
            or not row["required_labels"]
            or any(
                not isinstance(label, str) or not SAFE_LABEL.fullmatch(label)
                for label in row["required_labels"]
            )
        ):
            raise ValueError("unsafe anchor descriptor")
    uids = [row["uid"] for row in nodes] + [row["uid"] for row in anchors]
    duplicate_uids = {uid: count for uid, count in Counter(uids).items() if count > 1}
    if duplicate_uids:
        raise ValueError(f"duplicate uid: {duplicate_uids}")
    all_uids = set(uids)
    for row in nodes:
        if (
            not isinstance(row["labels"], list)
            or not row["labels"]
            or len(row["labels"]) != len(set(row["labels"]))
            or any(not SAFE_LABEL.fullmatch(label) for label in row["labels"])
            or any(
                not isinstance(key, str) or not _neo4j_property(value)
                for key, value in row["properties"].items()
            )
        ):
            raise ValueError(f"unsafe node record: {row['uid']}")
    seen_relations: set[tuple[str, str, str]] = set()
    for row in relations:
        key = (row["from_uid"], row["type"], row["to_uid"])
        if (
            key in seen_relations
            or row["from_uid"] not in all_uids
            or row["to_uid"] not in all_uids
            or not SAFE_RELATION.fullmatch(row["type"])
        ):
            raise ValueError(f"unsafe or duplicate relation: {key}")
        seen_relations.add(key)


def _node_properties(
    data: Mapping[str, Any], row: Mapping[str, Any], projection_sha256: str
) -> dict[str, Any]:
    return {
        "uid": row["uid"],
        **row["properties"],
        "ontology_bundle_uid": data["bundle_uid"],
        "ontology_projection_sha256": projection_sha256,
    }


def _relation_properties(
    data: Mapping[str, Any], row: Mapping[str, Any], projection_sha256: str
) -> dict[str, Any]:
    return {
        "ontology_bundle_uid": data["bundle_uid"],
        "ontology_projection_sha256": projection_sha256,
        "authority_class": row["authority_class"],
        "scope": row["scope"],
        "status": row["status"],
    }


def _find_unique_nodes(tx: Any, uids: list[str]) -> dict[str, dict[str, Any]]:
    rows = tx.run(
        "MATCH (n) WHERE n.uid IN $uids "
        "RETURN n.uid AS uid, labels(n) AS labels, properties(n) AS properties",
        uids=uids,
    ).data()
    duplicates = {
        uid: count for uid, count in Counter(row["uid"] for row in rows).items() if count > 1
    }
    if duplicates:
        raise RuntimeError(f"duplicate remote KG UIDs: {duplicates}")
    return {row["uid"]: row for row in rows}


def _relation_rows(tx: Any, row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return tx.run(
        "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
        f"MATCH (a)-[r:{row['type']}]->(b) RETURN properties(r) AS properties",
        from_uid=row["from_uid"],
        to_uid=row["to_uid"],
    ).data()


def _assert_registry(tx: Any, data: Mapping[str, Any]) -> None:
    row = tx.run(
        "MATCH (r:SchemaRegistry {uid:$uid}) "
        "RETURN r.allowed_labels AS labels, r.allowed_reltypes AS relations",
        uid=REGISTRY_UID,
    ).single()
    if row is None:
        raise RuntimeError(f"KG schema registry not found: {REGISTRY_UID}")
    expected_labels = {label for node in data["nodes"] for label in node["labels"]}
    expected_types = {relation["type"] for relation in data["relations"]}
    missing_labels = expected_labels - set(row["labels"] or ())
    missing_types = expected_types - set(row["relations"] or ())
    if missing_labels or missing_types:
        raise RuntimeError(
            "unregistered schema tokens: "
            f"labels={sorted(missing_labels)}, relations={sorted(missing_types)}"
        )


def _assert_anchors(tx: Any, data: Mapping[str, Any]) -> None:
    anchors = {row["uid"]: row for row in data["anchors"]}
    observed = _find_unique_nodes(tx, list(anchors))
    if set(observed) != set(anchors):
        raise RuntimeError("required remote anchors are missing")
    for uid, expected in anchors.items():
        actual = observed[uid]
        if actual["properties"].get("name") != expected["name"]:
            raise RuntimeError(
                f"anchor name drifted: {uid}; expected={expected['name']!r}, "
                f"observed={actual['properties'].get('name')!r}"
            )
        if not set(expected["required_labels"]) <= set(actual["labels"]):
            raise RuntimeError(f"anchor labels drifted: {uid}")


def _assert_exact_node(
    observed: Mapping[str, Any],
    expected_row: Mapping[str, Any],
    data: Mapping[str, Any],
    projection_sha256: str,
) -> None:
    if set(observed["labels"]) != set(expected_row["labels"]):
        raise RuntimeError(f"node label collision: {expected_row['uid']}")
    if observed["properties"] != _node_properties(data, expected_row, projection_sha256):
        raise RuntimeError(f"node property collision: {expected_row['uid']}")


def _assert_exact_relation(
    observed: Mapping[str, Any],
    expected_row: Mapping[str, Any],
    data: Mapping[str, Any],
    projection_sha256: str,
) -> None:
    if observed["properties"] != _relation_properties(
        data, expected_row, projection_sha256
    ):
        key = (
            expected_row["from_uid"],
            expected_row["type"],
            expected_row["to_uid"],
        )
        raise RuntimeError(f"relationship property collision: {key}")


def _readback(
    tx: Any, data: Mapping[str, Any], projection_sha256: str
) -> dict[str, int]:
    nodes_by_uid = {row["uid"]: row for row in data["nodes"]}
    observed_nodes = _find_unique_nodes(tx, list(nodes_by_uid))
    if set(observed_nodes) != set(nodes_by_uid):
        raise RuntimeError("remote node readback UID mismatch")
    for uid, row in nodes_by_uid.items():
        _assert_exact_node(observed_nodes[uid], row, data, projection_sha256)
    for row in data["relations"]:
        observed_relations = _relation_rows(tx, row)
        if len(observed_relations) != 1:
            key = (row["from_uid"], row["type"], row["to_uid"])
            raise RuntimeError(f"remote relation readback mismatch: {key}")
        _assert_exact_relation(observed_relations[0], row, data, projection_sha256)
    node_count = tx.run(
        "MATCH (n {ontology_bundle_uid:$uid}) RETURN count(n) AS count",
        uid=data["bundle_uid"],
    ).single()["count"]
    relation_count = tx.run(
        "MATCH ()-[r {ontology_bundle_uid:$uid}]->() RETURN count(r) AS count",
        uid=data["bundle_uid"],
    ).single()["count"]
    if node_count != len(nodes_by_uid) or relation_count != len(data["relations"]):
        raise RuntimeError("remote ownership count mismatch")
    return {"readback_nodes": node_count, "readback_relations": relation_count}


def publish(
    data: dict[str, Any], config: dict[str, str], projection_sha256: str
) -> dict[str, int]:
    """Create all bundle-owned nodes and relations in one fail-closed transaction."""

    try:
        from neo4j import GraphDatabase
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("--apply requires the optional kg dependency") from error

    driver = GraphDatabase.driver(
        config["uri"], auth=(config["user"], config["password"])
    )
    try:
        with driver.session(database=config["database"]) as session:

            def transaction(tx: Any) -> dict[str, int]:
                _assert_registry(tx, data)
                _assert_anchors(tx, data)

                existing_nodes = _find_unique_nodes(
                    tx, [row["uid"] for row in data["nodes"]]
                )
                if existing_nodes and len(existing_nodes) != len(data["nodes"]):
                    raise RuntimeError("refusing a partial pre-existing projection")
                if existing_nodes:
                    expected = {row["uid"]: row for row in data["nodes"]}
                    for uid, observed in existing_nodes.items():
                        _assert_exact_node(
                            observed, expected[uid], data, projection_sha256
                        )
                else:
                    for row in data["nodes"]:
                        labels = ":".join(row["labels"])
                        tx.run(
                            f"CREATE (n:{labels}) SET n=$properties",
                            properties=_node_properties(data, row, projection_sha256),
                        ).consume()

                existing_relations: list[bool] = []
                for row in data["relations"]:
                    found = _relation_rows(tx, row)
                    if len(found) > 1:
                        raise RuntimeError("duplicate remote relation")
                    if found:
                        _assert_exact_relation(found[0], row, data, projection_sha256)
                    existing_relations.append(bool(found))
                if any(existing_relations) and not all(existing_relations):
                    raise RuntimeError("refusing a partial pre-existing relation set")
                if not any(existing_relations):
                    for row in data["relations"]:
                        tx.run(
                            "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
                            f"CREATE (a)-[r:{row['type']}]->(b) SET r=$properties",
                            from_uid=row["from_uid"],
                            to_uid=row["to_uid"],
                            properties=_relation_properties(
                                data, row, projection_sha256
                            ),
                        ).consume()

                readback = _readback(tx, data, projection_sha256)
                return {
                    "created_nodes": 0 if existing_nodes else len(data["nodes"]),
                    "created_relations": 0
                    if any(existing_relations)
                    else len(data["relations"]),
                    "existing_nodes": len(existing_nodes),
                    "existing_relations": len(data["relations"])
                    if any(existing_relations)
                    else 0,
                    **readback,
                }

            return session.execute_write(transaction)
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology", type=Path, default=ONTOLOGY_PATH)
    parser.add_argument("--source-config", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.ontology.read_text(encoding="utf-8"))
    validate_data(data)
    projection_sha256 = _file_sha(args.ontology)
    if not args.apply:
        print(
            json.dumps(
                {
                    "new_nodes": len(data["nodes"]),
                    "relations": len(data["relations"]),
                    "projection_sha256": projection_sha256,
                    "status": "VALIDATED_ONLY_NOT_PUBLISHED",
                },
                sort_keys=True,
            )
        )
        return
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config")
    result = publish(data, read_flat_yaml(args.source_config), projection_sha256)
    print(
        json.dumps(
            {
                **result,
                "projection_sha256": projection_sha256,
                "status": "APPLIED_OR_VERIFIED_EXACT_PROJECTION",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
