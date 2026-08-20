#!/usr/bin/env python3
"""Validate and explicitly publish the Human Universal Body ontology bundle."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "hswm-human-universal-body-ontology/v1"
REGISTRY_UID = "sym:KG_INFRA:schema-registry-v1-2026-08-03"
SAFE_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SAFE_RELATION = re.compile(r"[A-Z][A-Z0-9_]*")


def read_flat_yaml(path: Path) -> dict[str, str]:
    """Read the flat Neo4j source config without printing credentials."""
    config: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        config[key.strip()] = value.strip().strip('"').strip("'")
    required = {"uri", "user", "password", "database"}
    missing = required - config.keys()
    if missing:
        raise ValueError(f"source config is missing keys: {sorted(missing)}")
    return config


def require_safe(values: list[str], field: str, pattern: re.Pattern[str]) -> None:
    invalid = sorted({value for value in values if not pattern.fullmatch(value)})
    if invalid:
        raise ValueError(f"unsafe {field}: {invalid}")


def is_neo4j_property(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int, float)):
        return True
    if isinstance(value, list):
        return all(item is not None and isinstance(item, (str, bool, int, float)) for item in value)
    return False


def validate_data(data: dict[str, Any], repo_root: Path) -> None:
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {data.get('schema_version')!r}")
    nodes = data.get("nodes")
    anchors = data.get("anchors")
    relations = data.get("relations")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("nodes must be a non-empty list")
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("anchors must be a non-empty list")
    if not isinstance(relations, list) or not relations:
        raise ValueError("relations must be a non-empty list")

    node_uids = [row["uid"] for row in nodes]
    anchor_uids = [row["uid"] for row in anchors]
    duplicates = [uid for uid, count in Counter(node_uids + anchor_uids).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate node or anchor UIDs: {duplicates}")
    if data["bundle_uid"] not in node_uids:
        raise ValueError("bundle_uid must identify a node in nodes")

    labels: list[str] = []
    for row in nodes:
        if not row.get("labels"):
            raise ValueError(f"node has no labels: {row['uid']}")
        labels.extend(row["labels"])
        properties = row.get("properties")
        if not isinstance(properties, dict) or not properties.get("name"):
            raise ValueError(f"node has invalid properties: {row['uid']}")
        invalid_properties = sorted(key for key, value in properties.items() if not is_neo4j_property(value))
        if invalid_properties:
            raise ValueError(f"unsupported Neo4j properties for {row['uid']}: {invalid_properties}")
    require_safe(labels, "labels", SAFE_LABEL)

    known_uids = set(node_uids + anchor_uids)
    relation_keys: list[tuple[str, str, str]] = []
    relation_types: list[str] = []
    for relation in relations:
        key = (relation["from_uid"], relation["type"], relation["to_uid"])
        relation_keys.append(key)
        relation_types.append(relation["type"])
        if key[0] not in known_uids or key[2] not in known_uids:
            raise ValueError(f"relation has unknown endpoint: {key}")
    duplicate_relations = [key for key, count in Counter(relation_keys).items() if count > 1]
    if duplicate_relations:
        raise ValueError(f"duplicate relations: {duplicate_relations}")
    require_safe(relation_types, "relationship types", SAFE_RELATION)

    source_pairs = (
        ("source_path", "source_sha256"),
        ("philosophy_source_path", "philosophy_source_sha256"),
        ("token_hypergraph_source_path", "token_hypergraph_source_sha256"),
        ("deep_set_hypergraph_source_path", "deep_set_hypergraph_source_sha256"),
    )
    for path_key, hash_key in source_pairs:
        source_path = repo_root / data[path_key]
        if not source_path.is_file():
            raise ValueError(f"{path_key} does not exist: {source_path}")
        source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if source_sha256 != data[hash_key]:
            raise ValueError(
                f"{hash_key} mismatch: payload={data[hash_key]} actual={source_sha256}"
            )


def _find_unique_nodes(tx: Any, uids: list[str]) -> dict[str, str]:
    rows = tx.run(
        "MATCH (n) WHERE n.uid IN $uids RETURN n.uid AS uid, elementId(n) AS eid",
        uids=uids,
    ).data()
    counts = Counter(row["uid"] for row in rows)
    duplicates = {uid: count for uid, count in counts.items() if count > 1}
    if duplicates:
        raise RuntimeError(f"duplicate KG UIDs: {duplicates}")
    return {row["uid"]: row["eid"] for row in rows}


def _publish_transaction(tx: Any, data: dict[str, Any]) -> dict[str, int]:
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

    anchor_uids = [row["uid"] for row in data["anchors"]]
    node_uids = [row["uid"] for row in data["nodes"]]
    existing = _find_unique_nodes(tx, anchor_uids + node_uids)
    missing_anchors = sorted(set(anchor_uids) - existing.keys())
    if missing_anchors:
        raise RuntimeError(f"required KG anchors are missing: {missing_anchors}")

    created = 0
    updated = 0
    element_ids = dict(existing)
    for row in data["nodes"]:
        uid = row["uid"]
        label_clause = ":".join(row["labels"])
        logical = row["properties"]
        authority_class = logical["authority_class"]
        if authority_class == "USER_PRIMARY":
            authority_scope = "USER_UTTERANCE_2026_08_20"
        elif authority_class == "SECONDARY_AI":
            authority_scope = "HSWM_ENGINEERING_FORMALIZATION_2026_08_20"
        else:
            authority_scope = "EXPLICIT_MIXED_BUNDLE_BOUNDARY"
        upper_uid = (
            "sym:KG_KNOW:informationentity"
            if {"SourceDocument", "ResearchArtifact"} & set(row["labels"])
            else "sym:KG_KNOW:conceptualentity"
        )
        properties = {
            **logical,
            "ontology_bundle_uid": data["bundle_uid"],
            "ontology_source_sha256": data["source_sha256"],
            "ontology_kind_v1": logical["ontology_kind"],
            "ontology_plane_v1": logical["ontology_plane"],
            "ontology_domain_v1": logical["ontology_domain"],
            "ontology_upper_uid_v1": upper_uid,
            "ontology_semantic_roles_v1": logical.get("semantic_roles", []),
            "ontology_authority_class_v1": authority_class,
            "ontology_authority_scope_v1": authority_scope,
            "ontology_canonical_scope_v1": logical["canonical_scope"],
            "ontology_record_lifecycle_v1": logical["record_lifecycle"],
            "ontology_workflow_state_v1": "NOT_APPLICABLE",
            "ontology_epistemic_state_v1": logical["epistemic_state"],
            "ontology_review_required_v1": logical["review_required"],
        }
        if uid in existing:
            record = tx.run(
                f"MATCH (n) WHERE elementId(n)=$eid "
                f"SET n:{label_clause}, n += $properties, n.updatedAt=datetime() "
                "RETURN elementId(n) AS eid",
                eid=existing[uid],
                properties=properties,
            ).single()
            updated += 1
        else:
            record = tx.run(
                f"CREATE (n:{label_clause}) "
                "SET n.uid=$uid, n += $properties, n.createdAt=datetime(), n.updatedAt=datetime() "
                "RETURN elementId(n) AS eid",
                uid=uid,
                properties=properties,
            ).single()
            created += 1
        element_ids[uid] = record["eid"]

    for relation in data["relations"]:
        tx.run(
            f"MATCH (a),(b) WHERE elementId(a)=$from_eid AND elementId(b)=$to_eid "
            f"MERGE (a)-[r:{relation['type']}]->(b) "
            "SET r.ontology_bundle_uid=$bundle_uid, r.authority_class=$authority_class, "
            "r.authority=$authority_class, r.scope=$scope, "
            "r.status=$status, r.updatedAt=datetime()",
            from_eid=element_ids[relation["from_uid"]],
            to_eid=element_ids[relation["to_uid"]],
            bundle_uid=data["bundle_uid"],
            authority_class=relation["authority_class"],
            scope=(
                "USER_UTTERANCE_2026_08_20"
                if relation["authority_class"] == "USER_PRIMARY"
                else "HSWM_ENGINEERING_FORMALIZATION_2026_08_20"
            ),
            status=relation["status"],
        ).consume()

    readback = tx.run(
        "MATCH (n) WHERE n.uid IN $uids "
        "RETURN n.uid AS uid, n.name AS name, "
        "n.ontology_authority_class_v1 AS authority_class, "
        "n.ontology_canonical_scope_v1 AS canonical_scope, "
        "n.ontology_kind_v1 AS ontology_kind, "
        "n.ontology_source_sha256 AS source_sha256",
        uids=node_uids,
    ).data()
    if len(readback) != len(node_uids):
        raise RuntimeError(f"node readback mismatch: expected={len(node_uids)} got={len(readback)}")
    expected = {row["uid"]: row for row in data["nodes"]}
    for row in readback:
        wanted = expected[row["uid"]]["properties"]
        if (
            row["name"] != wanted["name"]
            or row["authority_class"] != wanted["authority_class"]
            or row["canonical_scope"] != wanted["canonical_scope"]
            or row["ontology_kind"] != wanted["ontology_kind"]
        ):
            raise RuntimeError(f"node readback property mismatch: {row['uid']}")
        if row["source_sha256"] != data["source_sha256"]:
            raise RuntimeError(f"node readback source hash mismatch: {row['uid']}")

    relation_count = tx.run(
        "MATCH ()-[r]->() WHERE r.ontology_bundle_uid=$bundle_uid RETURN count(r) AS count",
        bundle_uid=data["bundle_uid"],
    ).single()["count"]
    if relation_count != len(data["relations"]):
        raise RuntimeError(
            f"relationship readback mismatch: expected={len(data['relations'])} got={relation_count}"
        )
    return {
        "created_nodes": created,
        "updated_nodes": updated,
        "readback_nodes": len(readback),
        "readback_relations": relation_count,
    }


def publish(data: dict[str, Any], config: dict[str, str]) -> dict[str, int]:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("--apply requires the optional `kg` dependency") from exc

    driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
    driver.verify_connectivity()
    try:
        with driver.session(database=config["database"]) as session:
            return session.execute_write(_publish_transaction, data)
    finally:
        driver.close()


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ontology",
        type=Path,
        default=repo_root
        / "ontology"
        / "identity"
        / "human_universal_body"
        / "HSWM_HUMAN_UNIVERSAL_BODY_ONTOLOGY.v1.json",
    )
    parser.add_argument("--source-config", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="explicitly publish the validated bundle to the configured Neo4j KG",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    data = json.loads(args.ontology.read_text(encoding="utf-8"))
    validate_data(data, repo_root)
    if not args.apply:
        print(json.dumps({
            "anchors": len(data["anchors"]),
            "nodes": len(data["nodes"]),
            "relations": len(data["relations"]),
            "source_sha256": data["source_sha256"],
            "status": "VALIDATED_ONLY",
        }, ensure_ascii=False, sort_keys=True))
        return
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config; KG mutation is never implicit")
    result = publish(data, read_flat_yaml(args.source_config.expanduser()))
    print(json.dumps({**result, "status": "APPLIED_AND_READ_BACK"}, sort_keys=True))


if __name__ == "__main__":
    main()
