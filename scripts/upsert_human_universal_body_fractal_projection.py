#!/usr/bin/env python3
"""Validate and explicitly publish the non-overwriting fractal KG projection."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

SCHEMA_VERSION = "hswm-human-universal-body-fractal-projection/v1"
BUNDLE_UID = "sym:AbstractNode:hswm-human-universal-body-fractal-projection-2026-08-28"
REGISTRY_UID = "sym:KG_INFRA:schema-registry-v1-2026-08-03"
NONCLAIM = "KG_PROJECTION_ONLY_NOT_HSWM_COGNITION_OR_LEARNING_NOT_SCIENTIFIC_EVIDENCE"
FRACTAL_UID = "sym:Concept:hswm-fractal-cognitive-composition"
EXPECTED_NEW_NODE_COUNT = 14
EXPECTED_RELATION_COUNT = 47
EXPECTED_DERIVATION_SOURCE_COMMIT = "a410db4f53ffb90a253af45df502805cc6b9b175"
EXPECTED_NODES_SHA256 = "cdffa06b2b58256d75310761daa85a340a4d02068884cb5a8fd646a35b172a00"
EXPECTED_ANCHORS_SHA256 = "7c0c8739ceb678b33e5e37684b29dcbeb2e3f5e1181e8e5035578d0de1e06588"
EXPECTED_RELATIONS_SHA256 = "3fdca26836630936e98c6b3a4e8d9c59dace1d4d9a2491afcd2c00e3fcfdb611"
SAFE_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SAFE_RELATION = re.compile(r"[A-Z][A-Z0-9_]*")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _neo_scalar_or_list(value: Any) -> bool:
    return value is None or isinstance(value, (str, bool, int, float)) or (
        isinstance(value, list)
        and all(item is not None and isinstance(item, (str, bool, int, float)) for item in value)
    )


def read_flat_yaml(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if ":" in raw and not raw.lstrip().startswith("#"):
            key, value = raw.split(":", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    if {"uri", "user", "password", "database"} - values.keys():
        raise ValueError("source config is incomplete")
    return values


def validate_data(data: dict[str, Any], repo_root: Path) -> None:
    if data.get("schema_version") != SCHEMA_VERSION or data.get("bundle_uid") != BUNDLE_UID:
        raise ValueError("unexpected fractal projection identity")
    if data.get("nonclaim") != NONCLAIM:
        raise ValueError("fractal projection nonclaim drifted")
    if data.get("derivation_source_commit") != EXPECTED_DERIVATION_SOURCE_COMMIT:
        raise ValueError("fractal projection derivation commit drifted")
    base = repo_root / data.get("historical_base_path", "")
    if not base.is_file() or _sha(base) != data.get("historical_base_sha256"):
        raise ValueError("historical v1 base binding drifted")
    historical = json.loads(base.read_text(encoding="utf-8"))
    historical_uids = {row["uid"] for row in historical["nodes"]} | {
        row["uid"] for row in historical["anchors"]
    }
    nodes, anchors, relations = data.get("nodes"), data.get("anchors"), data.get("relations")
    if type(nodes) is not list or len(nodes) != EXPECTED_NEW_NODE_COUNT:
        raise ValueError("fractal projection must contain exactly fourteen new nodes")
    if type(anchors) is not list or not anchors or type(relations) is not list or not relations:
        raise ValueError("fractal projection anchors and relations are required")
    observed_content_hashes = (
        _canonical_sha(nodes),
        _canonical_sha(anchors),
        _canonical_sha(relations),
    )
    if observed_content_hashes != (
        EXPECTED_NODES_SHA256,
        EXPECTED_ANCHORS_SHA256,
        EXPECTED_RELATIONS_SHA256,
    ):
        raise ValueError("fractal projection scientific content drifted")
    if any(type(row) is not dict for row in nodes + anchors + relations):
        raise ValueError("projection records must be objects")
    source_pairs = (("source_path", "source_sha256"), ("canon_path", "canon_sha256"))
    for path_key, sha_key in source_pairs:
        path = repo_root / data.get(path_key, "")
        if not path.is_file() or _sha(path) != data.get(sha_key):
            raise ValueError(f"{path_key} hash binding drifted")
    node_uids = [row.get("uid") for row in nodes]
    anchor_uids = [row.get("uid") for row in anchors]
    duplicate_uids = {
        uid: count
        for uid, count in Counter(node_uids + anchor_uids).items()
        if not isinstance(uid, str) or not uid or count > 1
    }
    if duplicate_uids:
        raise ValueError(f"duplicate or invalid projection UID: {duplicate_uids}")
    if set(node_uids) & set(anchor_uids) or set(node_uids) & historical_uids or BUNDLE_UID not in node_uids:
        raise ValueError("new-node or anchor UID closure drifted")
    if FRACTAL_UID not in node_uids:
        raise ValueError("fractal core concept is absent")
    if any(set(row) != {"uid", "name"} or not isinstance(row["name"], str) or not row["name"] for row in anchors):
        raise ValueError("projection anchors must have exact uid/name descriptors")
    for row in nodes:
        labels, properties = row.get("labels"), row.get("properties")
        if set(row) != {"uid", "labels", "properties"} or type(labels) is not list or not labels or len(labels) != len(set(labels)) or any(not isinstance(label, str) or not SAFE_LABEL.fullmatch(label) for label in labels):
            raise ValueError("unsafe projection node labels")
        required_properties = ("name", "authority_class", "canonical_scope", "ontology_kind", "ontology_plane", "epistemic_state", "responsibility_owner", "claim_boundary", "projection_nonclaim")
        if type(properties) is not dict or "nonclaim" in properties or not all(isinstance(properties.get(key), str) and properties[key] for key in required_properties):
            raise ValueError("projection node lacks authority, owner, or claim boundary")
        if properties["projection_nonclaim"] != NONCLAIM:
            raise ValueError("projection node nonclaim boundary drifted")
        if any(not isinstance(key, str) or not _neo_scalar_or_list(value) for key, value in properties.items()):
            raise ValueError("projection node has unsafe Neo4j properties")
    if len(relations) != EXPECTED_RELATION_COUNT:
        raise ValueError("fractal projection must contain the exact forty-seven relations")
    endpoints = set(node_uids + anchor_uids)
    if any(
        set(row) != {"from_uid", "type", "to_uid", "authority_class", "scope", "status"}
        or type(row.get("type")) is not str
        or not SAFE_RELATION.fullmatch(row["type"])
        or row.get("from_uid") not in endpoints
        or row.get("to_uid") not in endpoints
        for row in relations
    ):
        raise ValueError("projection relation endpoint closure drifted")
    if any(row.get("from_uid") in anchor_uids and row.get("to_uid") in anchor_uids for row in relations):
        raise ValueError("projection must not create anchor-to-anchor edges")
    keys = [(row["from_uid"], row["type"], row["to_uid"]) for row in relations]
    if len(keys) != len(set(keys)) or any(not isinstance(row.get(key), str) or not row[key] for row in relations for key in ("authority_class", "scope", "status")):
        raise ValueError("projection relation identity or authority drifted")
    used = {endpoint for row in relations for endpoint in (row["from_uid"], row["to_uid"])}
    unused_anchors = set(anchor_uids) - used
    unused_nodes = set(node_uids) - used
    if unused_anchors or unused_nodes:
        raise ValueError(
            "projection endpoint closure has unused records: "
            f"anchors={sorted(unused_anchors)} nodes={sorted(unused_nodes)}"
        )


def _expected_node_properties(data: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "uid": row["uid"],
        **row["properties"],
        "ontology_bundle_uid": data["bundle_uid"],
        "ontology_source_sha256": data["source_sha256"],
    }


def _expected_relation_properties(data: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ontology_bundle_uid": data["bundle_uid"],
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
    counts = Counter(row["uid"] for row in rows)
    duplicates = {uid: count for uid, count in counts.items() if count > 1}
    if duplicates:
        raise RuntimeError(f"duplicate remote KG UIDs: {duplicates}")
    return {row["uid"]: row for row in rows}


def _assert_exact_node(uid: str, expected: Mapping[str, Any], observed: Mapping[str, Any]) -> None:
    if set(observed["labels"]) != set(expected["labels"]):
        raise RuntimeError(f"node label collision or drift: {uid}")
    if observed["properties"] != expected["properties"]:
        raise RuntimeError(f"node property collision or drift: {uid}")


def _relation_rows(tx: Any, row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return tx.run(
        "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
        f"MATCH (a)-[r:{row['type']}]->(b) "
        "RETURN properties(r) AS properties",
        from_uid=row["from_uid"],
        to_uid=row["to_uid"],
    ).data()


def _assert_exact_relation(
    data: Mapping[str, Any], row: Mapping[str, Any], observed: Mapping[str, Any]
) -> None:
    if observed["properties"] != _expected_relation_properties(data, row):
        key = (row["from_uid"], row["type"], row["to_uid"])
        raise RuntimeError(f"relationship property collision or drift: {key}")


def _registry_readback(tx: Any, data: Mapping[str, Any]) -> None:
    registry = tx.run(
        "MATCH (r:SchemaRegistry {uid:$uid}) "
        "RETURN r.allowed_labels AS labels, r.allowed_reltypes AS relations",
        uid=REGISTRY_UID,
    ).single()
    if not registry:
        raise RuntimeError(f"KG schema registry not found: {REGISTRY_UID}")
    wanted_labels = {label for row in data["nodes"] for label in row["labels"]}
    wanted_relations = {row["type"] for row in data["relations"]}
    missing_labels = wanted_labels - set(registry["labels"] or [])
    missing_relations = wanted_relations - set(registry["relations"] or [])
    if missing_labels or missing_relations:
        raise RuntimeError(
            f"unregistered schema tokens: labels={sorted(missing_labels)}, "
            f"relations={sorted(missing_relations)}"
        )


def _exact_readback(tx: Any, data: Mapping[str, Any]) -> dict[str, int]:
    expected_nodes = {
        row["uid"]: {"labels": row["labels"], "properties": _expected_node_properties(data, row)}
        for row in data["nodes"]
    }
    rows = _find_unique_nodes(tx, list(expected_nodes))
    if set(rows) != set(expected_nodes):
        raise RuntimeError("exact new-node readback UID mismatch")
    for uid, expected in expected_nodes.items():
        _assert_exact_node(uid, expected, rows[uid])
    relation_count = 0
    for relation in data["relations"]:
        rows = _relation_rows(tx, relation)
        if len(rows) != 1:
            key = (relation["from_uid"], relation["type"], relation["to_uid"])
            raise RuntimeError(f"exact relationship readback mismatch: {key}")
        _assert_exact_relation(data, relation, rows[0])
        relation_count += 1
    owned_nodes = tx.run(
        "MATCH (n {ontology_bundle_uid:$bundle_uid}) RETURN count(n) AS count",
        bundle_uid=data["bundle_uid"],
    ).single()["count"]
    owned_relations = tx.run(
        "MATCH ()-[r {ontology_bundle_uid:$bundle_uid}]->() RETURN count(r) AS count",
        bundle_uid=data["bundle_uid"],
    ).single()["count"]
    if owned_nodes != len(expected_nodes) or owned_relations != relation_count:
        raise RuntimeError("projection ownership readback count drifted")
    return {"readback_nodes": owned_nodes, "readback_relations": owned_relations}


def publish(data: dict[str, Any], config: dict[str, str]) -> dict[str, int]:
    """Create only absent projection nodes/relations; anchors remain MATCH-only."""
    try:
        from neo4j import GraphDatabase
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("--apply requires the optional kg dependency") from error
    driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
    try:
        with driver.session(database=config["database"]) as session:
            def transaction(tx: Any) -> dict[str, int]:
                _registry_readback(tx, data)
                anchors = [row["uid"] for row in data["anchors"]]
                new_uids = [row["uid"] for row in data["nodes"]]
                # Anchors are queried only; no CREATE, SET, MERGE, or labels are ever
                # applied to them by this projection publisher.
                present = _find_unique_nodes(tx, anchors)
                if set(present) != set(anchors):
                    raise RuntimeError("required projection anchors are missing or non-unique")
                anchor_names = {row["uid"]: row["name"] for row in data["anchors"]}
                if any(present[uid]["properties"].get("name") != name for uid, name in anchor_names.items()):
                    raise RuntimeError("required projection anchor name drifted")
                existing = _find_unique_nodes(tx, new_uids)
                if existing and len(existing) != len(new_uids):
                    raise RuntimeError("refusing a partial pre-existing projection")
                if existing:
                    expected = {row["uid"]: row for row in data["nodes"]}
                    for uid, observed in existing.items():
                        row = expected[uid]
                        _assert_exact_node(
                            uid,
                            {"labels": row["labels"], "properties": _expected_node_properties(data, row)},
                            observed,
                        )
                else:
                    for row in data["nodes"]:
                        labels = ":".join(row["labels"])
                        tx.run(
                            f"CREATE (n:{labels}) SET n=$properties",
                            properties=_expected_node_properties(data, row),
                        ).consume()
                relation_existing: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
                for row in data["relations"]:
                    key = (row["from_uid"], row["type"], row["to_uid"])
                    found = _relation_rows(tx, row)
                    if len(found) > 1:
                        raise RuntimeError(f"duplicate existing relationship: {key}")
                    if found:
                        _assert_exact_relation(data, row, found[0])
                    relation_existing[key] = found
                if relation_existing and any(relation_existing.values()) and not all(relation_existing.values()):
                    raise RuntimeError("refusing a partial pre-existing projection relation set")
                created_relations = 0
                if not any(relation_existing.values()):
                    for row in data["relations"]:
                        tx.run(
                            "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
                            f"CREATE (a)-[r:{row['type']}]->(b) SET r=$properties",
                            from_uid=row["from_uid"],
                            to_uid=row["to_uid"],
                            properties=_expected_relation_properties(data, row),
                        ).consume()
                        created_relations += 1
                readback = _exact_readback(tx, data)
                return {
                    "created_nodes": 0 if existing else len(new_uids),
                    "created_relations": created_relations,
                    "existing_nodes": len(existing),
                    "existing_relations": len(data["relations"]) - created_relations,
                    **readback,
                }
            return session.execute_write(transaction)
    finally:
        driver.close()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--projection", type=Path, default=root / "ontology/identity/human_universal_body/HSWM_HUMAN_UNIVERSAL_BODY_FRACTAL_PROJECTION.v1.json")
    parser.add_argument("--source-config", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.projection.read_text(encoding="utf-8"))
    validate_data(data, root)
    if not args.apply:
        print(json.dumps({"new_nodes": len(data["nodes"]), "status": "VALIDATED_ONLY_NOT_PUBLISHED"}, sort_keys=True))
        return
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config")
    print(json.dumps({**publish(data, read_flat_yaml(args.source_config)), "status": "APPLIED_NEW_NODES_ONLY"}, sort_keys=True))


if __name__ == "__main__":
    main()
