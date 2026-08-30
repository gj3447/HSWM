#!/usr/bin/env python3
"""Validate and explicitly publish the adaptive-research KG projection."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from scripts import build_hswm_adaptive_research_strategy_ontology as builder


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / builder.ONTOLOGY_PATH
REGISTRY_UID = "sym:KG_INFRA:schema-registry-v1-2026-08-03"
EXPECTED_COUNTS = {
    "nodes": 35,
    "anchors": 16,
    "relations": 170,
    "target_invariants": 5,
    "mechanism_families": 9,
    "disposition_states": 8,
    "guardrails": 6,
    "source_records": 4,
}
EXPECTED_PROJECTION_SHA256 = (
    "a9e8e313bd848b10d0e73f2c0fef95ffcff68ccc341a209487625e9b78f83317"
)
EXPECTED_NODES_SHA256 = (
    "6bb7bd8a83492c929ef41da4fc88cafcf5717cc1df68446bf79caa3365feec91"
)
EXPECTED_ANCHORS_SHA256 = (
    "cf0a52f56dff7ff43c91c24a377981fccb04fbc81fc1da985c65299a44e93c41"
)
EXPECTED_RELATIONS_SHA256 = (
    "0934b506e0e9017ee8d39e851f3b0c83a9be4d21fcb35edea820df994030cfa1"
)
EXPECTED_FILE_SHA256 = (
    "b44c13a76724f545c492a36b5a32cf02339f6fa89846aae5ec218de14d1e6cbb"
)
PREDECESSOR_FILE_SHA256 = (
    "c566d78c4babbac14138ccf17cafd4022bfdf4f39566238ec348a61e5e733627"
)
PREDECESSOR_SNAPSHOT = {
    "nodes": 34,
    "node_sha256": "9e05f787578cb54a22fca6576fa1218dc89a363c9918bb4b7f0d85ec71f3c3b6",
    "relations": 161,
    "relation_sha256": "048afaf36196c4d7baad591a656584a4dc1ad0f7eef06bb0c75202f8f505760e",
}
MIGRATION_NEW_NODE_UIDS = {
    builder.CONSTITUTION_UID,
}
SAFE_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SAFE_RELATION = re.compile(r"[A-Z][A-Z0-9_]*")
TOP_LEVEL_KEYS = {
    "schema_version",
    "bundle_uid",
    "status",
    "nonclaim",
    "authority_boundary",
    "artifact_bindings",
    "expected_counts",
    "anchors",
    "nodes",
    "relations",
}


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _neo4j_property(value: Any) -> bool:
    return isinstance(value, (str, bool, int, float)) or (
        isinstance(value, list)
        and all(isinstance(item, (str, bool, int, float)) for item in value)
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


def _binding_map(data: Mapping[str, Any], repo_root: Path) -> dict[str, str]:
    rows = data.get("artifact_bindings")
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or set(row) != {"path", "sha256"}
        for row in rows
    ):
        raise ValueError("artifact bindings have an invalid shape")
    expected_paths = {path.as_posix() for path in builder.SOURCE_BINDING_PATHS}
    observed_paths = [row["path"] for row in rows]
    if len(observed_paths) != len(set(observed_paths)) or set(observed_paths) != expected_paths:
        raise ValueError("artifact binding paths drifted")
    root = repo_root.resolve()
    result: dict[str, str] = {}
    for row in rows:
        logical = Path(row["path"])
        if logical.is_absolute() or ".." in logical.parts or logical.as_posix() != row["path"]:
            raise ValueError("artifact binding path is not normalized")
        path = repo_root / logical
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"artifact binding is not a regular file: {logical}")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError(f"artifact binding escapes repository: {logical}")
        observed_sha = _file_sha(path)
        if row["sha256"] != observed_sha:
            raise ValueError(f"artifact binding drifted: {logical}")
        result[row["path"]] = observed_sha
    return result


def validate_data(data: dict[str, Any], repo_root: Path = ROOT) -> None:
    """Fail closed on source, authority, graph, or claim-boundary drift."""

    if set(data) != TOP_LEVEL_KEYS:
        raise ValueError("adaptive-research ontology top-level shape drifted")
    if data.get("schema_version") != builder.SCHEMA_VERSION:
        raise ValueError("adaptive-research schema identity drifted")
    if data.get("bundle_uid") != builder.BUNDLE_UID:
        raise ValueError("adaptive-research bundle identity drifted")
    if data.get("status") != builder.STATUS or data.get("nonclaim") != builder.NONCLAIM:
        raise ValueError("adaptive-research status or nonclaim drifted")
    if data.get("expected_counts") != EXPECTED_COUNTS:
        raise ValueError("adaptive-research declared counts drifted")
    _binding_map(data, repo_root)
    if (
        builder.canonical_sha(data),
        builder.canonical_sha(data.get("nodes")),
        builder.canonical_sha(data.get("anchors")),
        builder.canonical_sha(data.get("relations")),
    ) != (
        EXPECTED_PROJECTION_SHA256,
        EXPECTED_NODES_SHA256,
        EXPECTED_ANCHORS_SHA256,
        EXPECTED_RELATIONS_SHA256,
    ):
        raise ValueError("adaptive-research projection content drifted")
    if data != builder.build_data():
        raise ValueError("adaptive-research projection is not the deterministic build")

    nodes = data["nodes"]
    anchors = data["anchors"]
    relations = data["relations"]
    if not all(isinstance(rows, list) for rows in (nodes, anchors, relations)):
        raise ValueError("nodes, anchors, and relations must be arrays")
    if (len(nodes), len(anchors), len(relations)) != (
        EXPECTED_COUNTS["nodes"],
        EXPECTED_COUNTS["anchors"],
        EXPECTED_COUNTS["relations"],
    ):
        raise ValueError("adaptive-research graph count mismatch")
    if any(not isinstance(row, dict) for row in nodes + anchors + relations):
        raise ValueError("adaptive-research graph records must be objects")

    anchor_uids = [row.get("uid") for row in anchors]
    for row in anchors:
        if (
            set(row) != {"uid", "name", "required_labels"}
            or not isinstance(row["uid"], str)
            or not row["uid"]
            or not isinstance(row["name"], str)
            or not row["name"]
            or not isinstance(row["required_labels"], list)
            or not row["required_labels"]
            or any(not SAFE_LABEL.fullmatch(label) for label in row["required_labels"])
        ):
            raise ValueError("anchor descriptors are unsafe")

    required_properties = {
        "name",
        "description",
        "authority_class",
        "canonical_scope",
        "ontology_kind",
        "ontology_plane",
        "epistemic_state",
        "responsibility_owner",
        "claim_boundary",
        "projection_nonclaim",
        "ontology_domain",
        "record_lifecycle",
        "review_required",
        "semantic_roles",
    }
    node_uids = [row.get("uid") for row in nodes]
    duplicates = {
        uid: count
        for uid, count in Counter(node_uids + anchor_uids).items()
        if not isinstance(uid, str) or not uid or count > 1
    }
    if duplicates or set(node_uids) & set(anchor_uids):
        raise ValueError(f"duplicate or overlapping ontology UID: {duplicates}")
    for row in nodes:
        if set(row) != {"uid", "labels", "properties"}:
            raise ValueError("node record shape drifted")
        labels = row["labels"]
        properties = row["properties"]
        if (
            not isinstance(labels, list)
            or not labels
            or len(labels) != len(set(labels))
            or any(not isinstance(label, str) or not SAFE_LABEL.fullmatch(label) for label in labels)
        ):
            raise ValueError("node labels are unsafe")
        if not required_properties <= set(properties):
            raise ValueError("node lacks authority, owner, or claim boundary")
        if properties["projection_nonclaim"] != builder.NONCLAIM or properties["review_required"] is not True:
            raise ValueError("node nonclaim or review boundary drifted")
        if any(not isinstance(key, str) or not _neo4j_property(value) for key, value in properties.items()):
            raise ValueError(f"node has unsafe Neo4j properties: {row['uid']}")

    by_uid = {row["uid"]: row for row in nodes}
    commitment = by_uid.get(builder.COMMITMENT_UID)
    if not commitment or commitment["properties"]["authority_class"] != "USER_PRIMARY":
        raise ValueError("USER_PRIMARY commitment authority drifted")
    mechanisms = [
        row for row in nodes
        if "AUXILIARY_HYPOTHESIS_FAMILY" in row["properties"]["semantic_roles"]
    ]
    dispositions = [
        row for row in nodes
        if "MECHANISM_DISPOSITION" in row["properties"]["semantic_roles"]
    ]
    guardrails = [
        row for row in nodes
        if "REROUTE_GUARDRAIL" in row["properties"]["semantic_roles"]
    ]
    sources = [row for row in nodes if "SourceDocument" in row["labels"]]
    invariants = [
        row for row in nodes if "TARGET_INVARIANT" in row["properties"]["semantic_roles"]
    ]
    if (
        len(invariants),
        len(mechanisms),
        len(dispositions),
        len(guardrails),
        len(sources),
    ) != (
        EXPECTED_COUNTS["target_invariants"],
        EXPECTED_COUNTS["mechanism_families"],
        EXPECTED_COUNTS["disposition_states"],
        EXPECTED_COUNTS["guardrails"],
        EXPECTED_COUNTS["source_records"],
    ):
        raise ValueError("adaptive-research atom-family counts drifted")
    if any(row["properties"]["epistemic_state"] != "REPLACEABLE_UNJUDGED" for row in mechanisms):
        raise ValueError("auxiliary mechanism scientific state overclaims")
    if any(row["properties"]["epistemic_state"] != "STATE_DEFINITION" for row in dispositions):
        raise ValueError("disposition definition was mistaken for an observation")
    if {
        row["properties"].get("source_path")
        for row in sources
    } != {path.as_posix() for path in builder.SOURCE_RECORD_PATHS}:
        raise ValueError("source-record provenance is incomplete")

    endpoints = set(node_uids + anchor_uids)
    relation_keys: list[tuple[str, str, str]] = []
    for row in relations:
        if (
            set(row) != {"from_uid", "type", "to_uid", "authority_class", "scope", "status"}
            or not isinstance(row.get("type"), str)
            or not SAFE_RELATION.fullmatch(row["type"])
            or row.get("from_uid") not in endpoints
            or row.get("to_uid") not in endpoints
            or any(not isinstance(row.get(key), str) or not row[key] for key in ("authority_class", "scope", "status"))
        ):
            raise ValueError("relation shape, token, or endpoint closure drifted")
        if row["from_uid"] in anchor_uids and row["to_uid"] in anchor_uids:
            raise ValueError("projection may not create anchor-to-anchor relations")
        if row["type"] == "EVIDENCE_FOR":
            raise ValueError("strategy projection may not claim HSWM efficacy evidence")
        relation_keys.append((row["from_uid"], row["type"], row["to_uid"]))
    if len(relation_keys) != len(set(relation_keys)):
        raise ValueError("duplicate adaptive-research relation identity")
    used = {endpoint for row in relations for endpoint in (row["from_uid"], row["to_uid"])}
    if endpoints - used:
        raise ValueError(f"unused ontology endpoints: {sorted(endpoints - used)}")

    relation_set = set(relation_keys)
    expected_fcl_preservation = {
        (builder.PROGRAM_UID, "PRESERVES", uid) for uid in builder.FCL_UIDS.values()
    }
    if not expected_fcl_preservation <= relation_set:
        raise ValueError("adaptive program does not preserve every FCL target obligation")
    commitment_preserves = {
        to_uid
        for from_uid, relation_type, to_uid in relation_set
        if from_uid == builder.COMMITMENT_UID and relation_type == "PRESERVES"
    }
    if commitment_preserves != {builder.TARGET_INVARIANTS["TI-1"]["uid"]}:
        raise ValueError("adaptive USER_PRIMARY source was extended beyond TI-1")
    for invariant in builder.TARGET_INVARIANTS.values():
        invariant_uid = invariant["uid"]
        expected_sources = set(invariant["source_uids"])
        observed_sources = {
            to_uid
            for from_uid, relation_type, to_uid in relation_set
            if from_uid == invariant_uid and relation_type == "HAS_SOURCE"
        }
        if observed_sources != expected_sources:
            raise ValueError("target invariant canonical provenance drifted")
        if by_uid[invariant_uid]["properties"].get("canonical_source_uids") != invariant["source_uids"]:
            raise ValueError("target invariant source-property provenance drifted")
    required_fcl_sources = {
        builder.FRACTAL_SCIENTIFIC_CONNECTIONS_UID,
        builder.FRACTAL_SCIENTIFIC_CONNECTIONS_ONTOLOGY_UID,
    }
    observed_fcl_sources = {
        to_uid
        for from_uid, relation_type, to_uid in relation_set
        if from_uid == builder.PROGRAM_UID
        and relation_type == "HAS_SOURCE"
        and to_uid in required_fcl_sources
    }
    if observed_fcl_sources != required_fcl_sources:
        raise ValueError("FCL scientific-connection provenance is incomplete")
    if (
        builder.BUNDLE_UID,
        "DOES_NOT_ENFORCE",
        "sym:Concept:hswm",
    ) not in relation_set:
        raise ValueError("projection non-evidence boundary is absent")
    for mechanism in mechanisms:
        uid = mechanism["uid"]
        if (
            uid,
            "REALIZES",
            builder.TARGET_INVARIANTS["TI-1"]["uid"],
        ) not in relation_set or (
            builder.GUARDRAILS["RG-1"][0],
            "TESTS",
            uid,
        ) not in relation_set:
            raise ValueError("replaceable mechanism lacks target or falsification binding")
    required_reroute_edges = {
        (builder.GUARDRAILS["RG-3"][0], "REQUIRES", builder.GUARDRAILS[guard_id][0])
        for guard_id in ("RG-1", "RG-2", "RG-4", "RG-5", "RG-6")
    }
    if not required_reroute_edges <= relation_set:
        raise ValueError("reroute transaction weakened a required guardrail")


def _source_sha(data: Mapping[str, Any]) -> str:
    bindings = {row["path"]: row["sha256"] for row in data["artifact_bindings"]}
    return bindings[builder.SOURCE_PATH.as_posix()]


def _expected_node_properties(data: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "uid": row["uid"],
        **row["properties"],
        "ontology_bundle_uid": data["bundle_uid"],
        "ontology_projection_sha256": EXPECTED_FILE_SHA256,
        "ontology_user_source_sha256": _source_sha(data),
    }


def _expected_relation_properties(data: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ontology_bundle_uid": data["bundle_uid"],
        "ontology_projection_sha256": EXPECTED_FILE_SHA256,
        "authority_class": row["authority_class"],
        "scope": row["scope"],
        "status": row["status"],
    }


def _snapshot_digest(rows: list[dict[str, Any]], *, relation: bool) -> str:
    if relation:
        ordered = sorted(
            rows,
            key=lambda row: (row["from_uid"], row["type"], row["to_uid"]),
        )
    else:
        ordered = sorted(rows, key=lambda row: row["uid"])
    return builder.canonical_sha(ordered)


def _snapshot_descriptor(
    nodes: list[dict[str, Any]], relations: list[dict[str, Any]]
) -> dict[str, int | str]:
    normalized_nodes = [
        {
            "uid": row["uid"],
            "labels": sorted(row["labels"]),
            "properties": row["properties"],
        }
        for row in nodes
    ]
    normalized_relations = [
        {
            "from_uid": row["from_uid"],
            "type": row["type"],
            "to_uid": row["to_uid"],
            "properties": row["properties"],
        }
        for row in relations
    ]
    return {
        "nodes": len(normalized_nodes),
        "node_sha256": _snapshot_digest(normalized_nodes, relation=False),
        "relations": len(normalized_relations),
        "relation_sha256": _snapshot_digest(normalized_relations, relation=True),
    }


def _expected_snapshot(data: Mapping[str, Any]) -> dict[str, int | str]:
    nodes = [
        {
            "uid": row["uid"],
            "labels": row["labels"],
            "properties": _expected_node_properties(data, row),
        }
        for row in data["nodes"]
    ]
    relations = [
        {
            "from_uid": row["from_uid"],
            "type": row["type"],
            "to_uid": row["to_uid"],
            "properties": _expected_relation_properties(data, row),
        }
        for row in data["relations"]
    ]
    return _snapshot_descriptor(nodes, relations)


def classify_owned_snapshot(snapshot: Mapping[str, int | str], data: Mapping[str, Any]) -> str:
    """Return the only safe owned-bundle state; reject partial or unknown data."""

    if dict(snapshot) == PREDECESSOR_SNAPSHOT:
        return "EXACT_PREDECESSOR"
    if dict(snapshot) == _expected_snapshot(data):
        return "EXACT_CURRENT"
    raise RuntimeError("adaptive-research bundle is partial, mixed, or unknown")


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
        f"MATCH (a)-[r:{row['type']}]->(b) RETURN properties(r) AS properties",
        from_uid=row["from_uid"],
        to_uid=row["to_uid"],
    ).data()


def _owned_bundle_rows(tx: Any, bundle_uid: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = tx.run(
        "MATCH (n {ontology_bundle_uid:$bundle_uid}) "
        "RETURN n.uid AS uid, labels(n) AS labels, properties(n) AS properties",
        bundle_uid=bundle_uid,
    ).data()
    relations = tx.run(
        "MATCH (a)-[r {ontology_bundle_uid:$bundle_uid}]->(b) "
        "RETURN a.uid AS from_uid, type(r) AS type, b.uid AS to_uid, "
        "properties(r) AS properties",
        bundle_uid=bundle_uid,
    ).data()
    return nodes, relations


def _create_node(tx: Any, properties: Mapping[str, Any], labels: list[str]) -> None:
    tx.run(
        f"CREATE (n:{':'.join(labels)}) SET n=$properties",
        properties=dict(properties),
    ).consume()


def _migrate_exact_predecessor(
    tx: Any,
    data: Mapping[str, Any],
    predecessor_nodes: list[dict[str, Any]],
    predecessor_relations: list[dict[str, Any]],
) -> dict[str, int]:
    """Migrate the sole known predecessor inside the caller's transaction."""

    current_by_uid = {row["uid"]: row for row in data["nodes"]}
    predecessor_by_uid = {row["uid"]: row for row in predecessor_nodes}
    predecessor_uids = {row["uid"] for row in predecessor_nodes}
    retained_uids = set(current_by_uid) - MIGRATION_NEW_NODE_UIDS
    if predecessor_uids != retained_uids:
        raise RuntimeError("known predecessor node set is not the declared migration input")
    if any(set(row["labels"]) != set(current_by_uid[row["uid"]]["labels"]) for row in predecessor_nodes):
        raise RuntimeError("known predecessor labels are incompatible with current projection")
    observed_retained = _find_unique_nodes(tx, sorted(retained_uids))
    if set(observed_retained) != retained_uids:
        raise RuntimeError("retained predecessor UID set has an external collision")
    for uid in sorted(retained_uids):
        _assert_exact_node(
            uid,
            {
                "labels": predecessor_by_uid[uid]["labels"],
                "properties": predecessor_by_uid[uid]["properties"],
            },
            observed_retained[uid],
        )
    if _find_unique_nodes(tx, sorted(MIGRATION_NEW_NODE_UIDS)):
        raise RuntimeError("new adaptive-research source UID already exists externally")

    current_relations = {
        (row["from_uid"], row["type"], row["to_uid"]): row
        for row in data["relations"]
    }
    predecessor_keys = {
        (row["from_uid"], row["type"], row["to_uid"])
        for row in predecessor_relations
    }
    predecessor_by_key = {
        (row["from_uid"], row["type"], row["to_uid"]): row
        for row in predecessor_relations
    }
    removed_keys = predecessor_keys - set(current_relations)
    expected_removed = {
        (builder.COMMITMENT_UID, "PRESERVES", builder.TARGET_INVARIANTS[key]["uid"])
        for key in ("TI-2", "TI-3", "TI-4", "TI-5")
    }
    if removed_keys != expected_removed:
        raise RuntimeError("known predecessor does not have exactly the four retired USER_PRIMARY edges")
    retained_keys = predecessor_keys & set(current_relations)
    new_keys = set(current_relations) - predecessor_keys
    for key in retained_keys:
        rows = _relation_rows(tx, current_relations[key])
        if (
            len(rows) != 1
            or rows[0]["properties"] != predecessor_by_key[key]["properties"]
        ):
            raise RuntimeError(f"retained relation has an external collision: {key}")
    for key in new_keys:
        if _relation_rows(tx, current_relations[key]):
            raise RuntimeError(f"new relation collides with an external relation: {key}")

    old_removed_properties = {
        "ontology_bundle_uid": data["bundle_uid"],
        "ontology_projection_sha256": PREDECESSOR_FILE_SHA256,
        "authority_class": "USER_PRIMARY",
        "scope": "TARGET_DIRECTION",
        "status": "USER_RATIFIED",
    }
    for key in removed_keys:
        rows = _relation_rows(tx, predecessor_by_key[key])
        if len(rows) != 1 or rows[0]["properties"] != old_removed_properties:
            raise RuntimeError(f"retired relation has an external collision: {key}")

    for from_uid, _relation_type, to_uid in sorted(removed_keys):
        deleted = tx.run(
            "MATCH (a {uid:$from_uid})-[r:PRESERVES]->(b {uid:$to_uid}) "
            "WHERE properties(r) = $properties DELETE r RETURN 1 AS deleted",
            from_uid=from_uid,
            to_uid=to_uid,
            properties=old_removed_properties,
        ).data()
        if len(deleted) != 1 or deleted[0].get("deleted") != 1:
            raise RuntimeError("retired predecessor relation was not exact and unique")

    for uid in sorted(retained_uids):
        count = tx.run(
            "MATCH (n {uid:$uid}) SET n=$properties RETURN count(n) AS count",
            uid=uid,
            properties=_expected_node_properties(data, current_by_uid[uid]),
        ).single()["count"]
        if count != 1:
            raise RuntimeError(f"retained predecessor node is not unique: {uid}")
    for uid in sorted(MIGRATION_NEW_NODE_UIDS):
        row = current_by_uid[uid]
        _create_node(tx, _expected_node_properties(data, row), row["labels"])

    for key in sorted(retained_keys):
        row = current_relations[key]
        count = tx.run(
            "MATCH (a {uid:$from_uid})-[r]->(b {uid:$to_uid}) "
            f"WHERE type(r) = '{row['type']}' SET r=$properties RETURN count(r) AS count",
            from_uid=row["from_uid"],
            to_uid=row["to_uid"],
            properties=_expected_relation_properties(data, row),
        ).single()["count"]
        if count != 1:
            raise RuntimeError(f"retained relation is not unique: {key}")
    for key in sorted(new_keys):
        row = current_relations[key]
        tx.run(
            "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
            f"CREATE (a)-[r:{row['type']}]->(b) SET r=$properties",
            from_uid=row["from_uid"],
            to_uid=row["to_uid"],
            properties=_expected_relation_properties(data, row),
        ).consume()
    return {
        "migrated_nodes": len(retained_uids),
        "created_nodes": len(MIGRATION_NEW_NODE_UIDS),
        "deleted_relations": len(removed_keys),
        "updated_relations": len(retained_keys),
        "created_relations": len(new_keys),
    }


def _registry_readback(tx: Any, data: Mapping[str, Any]) -> None:
    registry = tx.run(
        "MATCH (r:SchemaRegistry {uid:$uid}) "
        "RETURN r.allowed_labels AS labels, r.allowed_reltypes AS relations",
        uid=REGISTRY_UID,
    ).single()
    if not registry:
        raise RuntimeError(f"KG schema registry not found: {REGISTRY_UID}")
    missing_labels = {
        label for row in data["nodes"] for label in row["labels"]
    } - set(registry["labels"] or [])
    missing_relations = {row["type"] for row in data["relations"]} - set(
        registry["relations"] or []
    )
    if missing_labels or missing_relations:
        raise RuntimeError(
            f"unregistered schema tokens: labels={sorted(missing_labels)}, "
            f"relations={sorted(missing_relations)}"
        )


def _exact_readback(tx: Any, data: Mapping[str, Any]) -> dict[str, int]:
    expected_nodes = {
        row["uid"]: {
            "labels": row["labels"],
            "properties": _expected_node_properties(data, row),
        }
        for row in data["nodes"]
    }
    observed_nodes = _find_unique_nodes(tx, list(expected_nodes))
    if set(observed_nodes) != set(expected_nodes):
        raise RuntimeError("exact adaptive-research node readback UID mismatch")
    for uid, expected in expected_nodes.items():
        _assert_exact_node(uid, expected, observed_nodes[uid])
    for relation in data["relations"]:
        rows = _relation_rows(tx, relation)
        if len(rows) != 1 or rows[0]["properties"] != _expected_relation_properties(data, relation):
            raise RuntimeError(
                "exact adaptive-research relation readback mismatch: "
                f"{(relation['from_uid'], relation['type'], relation['to_uid'])}"
            )
    owned_nodes = tx.run(
        "MATCH (n {ontology_bundle_uid:$uid}) RETURN count(n) AS count",
        uid=data["bundle_uid"],
    ).single()["count"]
    owned_relations = tx.run(
        "MATCH ()-[r {ontology_bundle_uid:$uid}]->() RETURN count(r) AS count",
        uid=data["bundle_uid"],
    ).single()["count"]
    if owned_nodes != len(expected_nodes) or owned_relations != len(data["relations"]):
        raise RuntimeError("adaptive-research projection ownership readback drifted")
    return {"readback_nodes": owned_nodes, "readback_relations": owned_relations}


def publish(data: dict[str, Any], config: dict[str, str]) -> dict[str, int]:
    """Create the projection transactionally; external anchors are MATCH-only."""

    try:
        from neo4j import GraphDatabase
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("--apply requires the optional kg dependency") from error
    driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
    try:
        with driver.session(database=config["database"]) as session:

            def transaction(tx: Any) -> dict[str, int]:
                _registry_readback(tx, data)
                anchor_uids = [row["uid"] for row in data["anchors"]]
                present = _find_unique_nodes(tx, anchor_uids)
                if set(present) != set(anchor_uids):
                    missing = sorted(set(anchor_uids) - set(present))
                    raise RuntimeError(f"required adaptive-research anchors are missing: {missing}")
                for row in data["anchors"]:
                    observed = present[row["uid"]]
                    if observed["properties"].get("name") != row["name"]:
                        raise RuntimeError(f"anchor name drifted: {row['uid']}")
                    if not set(row["required_labels"]) <= set(observed["labels"]):
                        raise RuntimeError(f"anchor label drifted: {row['uid']}")

                owned_nodes, owned_relations = _owned_bundle_rows(tx, data["bundle_uid"])
                if owned_nodes or owned_relations:
                    state = classify_owned_snapshot(
                        _snapshot_descriptor(owned_nodes, owned_relations), data
                    )
                    if state == "EXACT_CURRENT":
                        return {
                            "created_nodes": 0,
                            "created_relations": 0,
                            "existing_nodes": len(owned_nodes),
                            "existing_relations": len(owned_relations),
                            **_exact_readback(tx, data),
                        }
                    migration = _migrate_exact_predecessor(
                        tx, data, owned_nodes, owned_relations
                    )
                    return {**migration, **_exact_readback(tx, data)}

                new_uids = [row["uid"] for row in data["nodes"]]
                if _find_unique_nodes(tx, new_uids):
                    raise RuntimeError("new adaptive-research projection UID already exists externally")
                for row in data["nodes"]:
                    _create_node(tx, _expected_node_properties(data, row), row["labels"])
                for row in data["relations"]:
                    if _relation_rows(tx, row):
                        raise RuntimeError("new adaptive-research relation collides externally")
                    tx.run(
                        "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
                        f"CREATE (a)-[r:{row['type']}]->(b) SET r=$properties",
                        from_uid=row["from_uid"],
                        to_uid=row["to_uid"],
                        properties=_expected_relation_properties(data, row),
                    ).consume()
                return {
                    "created_nodes": len(new_uids),
                    "created_relations": len(data["relations"]),
                    "existing_nodes": 0,
                    "existing_relations": 0,
                    **_exact_readback(tx, data),
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
    validate_data(data, ROOT)
    if _file_sha(args.ontology) != EXPECTED_FILE_SHA256:
        raise SystemExit("adaptive-research ontology file bytes drifted")
    if not args.apply:
        print(
            json.dumps(
                {
                    "new_nodes": len(data["nodes"]),
                    "relations": len(data["relations"]),
                    "projection_sha256": EXPECTED_FILE_SHA256,
                    "status": "VALIDATED_ONLY_NOT_PUBLISHED",
                },
                sort_keys=True,
            )
        )
        return
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config")
    result = publish(data, read_flat_yaml(args.source_config))
    print(
        json.dumps(
            {
                **result,
                "projection_sha256": EXPECTED_FILE_SHA256,
                "status": "APPLIED_OR_VERIFIED_EXACT_PROJECTION",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
