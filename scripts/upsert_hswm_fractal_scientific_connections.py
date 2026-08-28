#!/usr/bin/env python3
"""Validate and explicitly publish the HSWM fractal scientific-prior projection."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

SCHEMA_VERSION = "hswm-fractal-scientific-connections-ontology/v1"
BUNDLE_UID = "sym:AbstractNode:hswm-fractal-scientific-connections-ontology-2026-08-28"
SYNTHESIS_UID = "sym:AbstractNode:hswm-fractal-scientific-connections-2026-08-28"
REGISTRY_UID = "sym:KG_INFRA:schema-registry-v1-2026-08-03"
NONCLAIM = (
    "LITERATURE_KG_PROJECTION_ONLY_NOT_HSWM_COGNITION_LEARNING_EFFICACY_"
    "CONSCIOUSNESS_OR_SCIENTIFIC_DISCOVERY"
)
EXPECTED_COUNTS = {
    "nodes": 54,
    "anchors": 11,
    "relations": 150,
    "sources": 16,
    "reported_constructs": 18,
    "bridge_hypotheses": 10,
    "null_hypotheses": 8,
}
EXPECTED_NODES_SHA256 = "dd1c11ab36317ebb53f8820da2d92ad0377d58e5f873cc737995f06e9e200eb8"
EXPECTED_ANCHORS_SHA256 = "2ef50de7be8973f917967474443c5f07f36dd07ea2969c1ac9eb75122cd5c6ff"
EXPECTED_RELATIONS_SHA256 = "49bdd9be7c0f5912c9dc89d296d0a1d0866dfd3fde83209eacea9dc7ac978a9c"
SAFE_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SAFE_RELATION = re.compile(r"[A-Z][A-Z0-9_]*")
FCL_UIDS = {
    f"sym:Concept:hswm-fractal-law-{suffix}"
    for suffix in (
        "local-causal-learning",
        "composition-preservation",
        "emergent-coalition",
        "multiscale-credit",
        "topology-morphogenesis",
        "world-self-co-model",
        "diachronic-continuity",
        "hswm-of-hswms",
    )
}


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
        and all(
            item is not None and isinstance(item, (str, bool, int, float))
            for item in value
        )
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
    """Fail closed before a source, schema, ownership, or authority drift can publish."""
    if data.get("schema_version") != SCHEMA_VERSION or data.get("bundle_uid") != BUNDLE_UID:
        raise ValueError("unexpected scientific connection ontology identity")
    if data.get("nonclaim") != NONCLAIM:
        raise ValueError("scientific projection nonclaim drifted")
    if data.get("status") != "SCIENTIFICALLY_CONNECTED_INTEGRATED_CLAIM_UNJUDGED":
        raise ValueError("scientific status drifted")
    if data.get("expected_counts") != EXPECTED_COUNTS:
        raise ValueError("declared scientific projection counts drifted")

    for path_key, sha_key in (
        ("research_path", "research_sha256"),
        ("anchor_projection_path", "anchor_projection_sha256"),
    ):
        path = repo_root / data.get(path_key, "")
        if not path.is_file() or _sha(path) != data.get(sha_key):
            raise ValueError(f"{path_key} hash binding drifted")

    nodes = data.get("nodes")
    anchors = data.get("anchors")
    relations = data.get("relations")
    if not all(type(rows) is list for rows in (nodes, anchors, relations)):
        raise ValueError("nodes, anchors, and relations must be arrays")
    if (len(nodes), len(anchors), len(relations)) != (
        EXPECTED_COUNTS["nodes"],
        EXPECTED_COUNTS["anchors"],
        EXPECTED_COUNTS["relations"],
    ):
        raise ValueError("scientific projection count mismatch")
    if (
        _canonical_sha(nodes),
        _canonical_sha(anchors),
        _canonical_sha(relations),
    ) != (
        EXPECTED_NODES_SHA256,
        EXPECTED_ANCHORS_SHA256,
        EXPECTED_RELATIONS_SHA256,
    ):
        raise ValueError("scientific projection content drifted")
    if any(type(row) is not dict for row in nodes + anchors + relations):
        raise ValueError("projection records must be objects")

    anchor_projection = json.loads(
        (repo_root / data["anchor_projection_path"]).read_text(encoding="utf-8")
    )
    available_anchors = {
        row["uid"]: row["properties"]["name"] for row in anchor_projection["nodes"]
    }
    anchor_uids = [row.get("uid") for row in anchors]
    if any(
        set(row) != {"uid", "name"}
        or not isinstance(row["uid"], str)
        or available_anchors.get(row["uid"]) != row["name"]
        for row in anchors
    ):
        raise ValueError("anchor descriptors are not exact members of the bound projection")

    node_uids = [row.get("uid") for row in nodes]
    duplicate_uids = {
        uid: count
        for uid, count in Counter(node_uids + anchor_uids).items()
        if not isinstance(uid, str) or not uid or count > 1
    }
    if duplicate_uids or set(node_uids) & set(anchor_uids):
        raise ValueError(f"duplicate, invalid, or overlapping UID: {duplicate_uids}")
    if BUNDLE_UID not in node_uids or SYNTHESIS_UID not in node_uids:
        raise ValueError("bundle or synthesis node is absent")

    required_properties = (
        "name",
        "authority_class",
        "canonical_scope",
        "ontology_kind",
        "ontology_plane",
        "epistemic_state",
        "responsibility_owner",
        "claim_boundary",
        "projection_nonclaim",
    )
    for row in nodes:
        if set(row) != {"uid", "labels", "properties"}:
            raise ValueError("node record shape drifted")
        labels, properties = row["labels"], row["properties"]
        if (
            type(labels) is not list
            or not labels
            or len(labels) != len(set(labels))
            or any(not isinstance(label, str) or not SAFE_LABEL.fullmatch(label) for label in labels)
        ):
            raise ValueError("unsafe scientific projection labels")
        if not all(isinstance(properties.get(key), str) and properties[key] for key in required_properties):
            raise ValueError("node lacks authority, owner, epistemic state, or claim boundary")
        if properties["projection_nonclaim"] != NONCLAIM:
            raise ValueError("node nonclaim boundary drifted")
        if any(not isinstance(key, str) or not _neo_scalar_or_list(value) for key, value in properties.items()):
            raise ValueError("node has unsafe Neo4j properties")

    sources = [row for row in nodes if "AcademicPaper" in row["labels"]]
    constructs = [row for row in nodes if "ExternalTheory" in row["labels"]]
    bridges = [row for row in nodes if "BridgeConcept" in row["labels"]]
    nulls = [row for row in nodes if row["uid"].startswith("sym:Hypothesis:hswm-fractal-null-")]
    if tuple(map(len, (sources, constructs, bridges, nulls))) != (
        EXPECTED_COUNTS["sources"],
        EXPECTED_COUNTS["reported_constructs"],
        EXPECTED_COUNTS["bridge_hypotheses"],
        EXPECTED_COUNTS["null_hypotheses"],
    ):
        raise ValueError("scientific atom-family counts drifted")

    source_fields = (
        "title",
        "authors",
        "source_id",
        "source_url",
        "reported_object",
        "reported_dynamics",
        "reported_scope",
        "limitations",
    )
    if any(
        row["properties"]["authority_class"] != "EXTERNAL_PRIMARY_SOURCE_REPORTED"
        or row["properties"]["epistemic_state"] != "LITERATURE_REPORTED"
        or not isinstance(row["properties"].get("publication_year"), int)
        or not row["properties"].get("source_url", "").startswith("https://")
        or not all(isinstance(row["properties"].get(key), str) and row["properties"][key] for key in source_fields)
        for row in sources
    ):
        raise ValueError("primary-source content extraction is incomplete")
    if len({row["properties"]["source_id"] for row in sources}) != len(sources):
        raise ValueError("primary-source identifiers are not unique")
    if any(
        row["properties"]["authority_class"] != "EXTERNAL_PRIMARY_SOURCE_REPORTED"
        or row["properties"]["epistemic_state"] != "LITERATURE_REPORTED"
        or not all(row["properties"].get(key) for key in ("reported_object", "reported_dynamics", "reported_scope", "limitations"))
        for row in constructs
    ):
        raise ValueError("reported scientific constructs are incomplete")
    bridge_fields = (
        "supported_component",
        "hswm_extension",
        "unresolved_delta",
        "testable_prediction",
        "failure_observation",
        "mapped_fcl_ids",
    )
    if any(
        row["properties"]["authority_class"] != "SECONDARY_AI"
        or row["properties"]["epistemic_state"] != "WORKING_HYPOTHESIS"
        or not all(row["properties"].get(key) for key in bridge_fields)
        for row in bridges
    ):
        raise ValueError("HSWM bridge authority or falsifiable content is incomplete")
    if any(
        row["properties"]["epistemic_state"] != "PROPOSED_TEST"
        or not row["properties"].get("target_bridge_uid")
        or not row["properties"].get("rejection_rule")
        for row in nulls
    ):
        raise ValueError("falsification null content is incomplete")

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
            raise ValueError("scientific relation shape or endpoint closure drifted")
        if row["from_uid"] in anchor_uids and row["to_uid"] in anchor_uids:
            raise ValueError("scientific projection may not create anchor-to-anchor edges")
        if row["type"] == "EVIDENCE_FOR":
            raise ValueError("literature mapping may not claim HSWM efficacy evidence")
        relation_keys.append((row["from_uid"], row["type"], row["to_uid"]))
    if len(relation_keys) != len(set(relation_keys)):
        raise ValueError("duplicate scientific relation identity")
    used = {endpoint for row in relations for endpoint in (row["from_uid"], row["to_uid"])}
    if endpoints - used:
        raise ValueError(f"unused scientific projection endpoints: {sorted(endpoints - used)}")

    source_uids = {row["uid"] for row in sources}
    construct_uids = {row["uid"] for row in constructs}
    bridge_uids = {row["uid"] for row in bridges}
    reported_edges = {
        (row["from_uid"], row["to_uid"])
        for row in relations
        if row["type"] == "HAS_CONCEPT"
        and row["authority_class"] == "EXTERNAL_PRIMARY_SOURCE_REPORTED"
    }
    if not all(any(left == uid and right in construct_uids for left, right in reported_edges) for uid in source_uids):
        raise ValueError("every source must own at least one reported construct edge")
    interpretation_edges = [
        row for row in relations
        if row["from_uid"] in construct_uids and row["to_uid"] in bridge_uids
    ]
    if not interpretation_edges or any(
        row["type"] != "THEORETICAL_BASIS_FOR"
        or row["authority_class"] != "SECONDARY_AI"
        or row["status"] != "WORKING_HYPOTHESIS"
        for row in interpretation_edges
    ):
        raise ValueError("literature-to-HSWM bridges must remain SECONDARY_AI hypotheses")
    mapped_fcls = {
        row["to_uid"]
        for row in relations
        if row["from_uid"] in bridge_uids and row["type"] == "SPECULATIVE_LINK"
    }
    if mapped_fcls != FCL_UIDS:
        raise ValueError("the bridge projection must cover all eight FCL laws")
    tested_bridges = {
        row["to_uid"] for row in relations
        if row["from_uid"].startswith("sym:Hypothesis:hswm-fractal-null-")
        and row["type"] == "TESTS"
    }
    if tested_bridges != bridge_uids:
        raise ValueError("every HSWM bridge must have a falsification null")


def _expected_node_properties(data: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "uid": row["uid"],
        **row["properties"],
        "ontology_bundle_uid": data["bundle_uid"],
        "ontology_source_sha256": data["research_sha256"],
        "ontology_anchor_projection_sha256": data["anchor_projection_sha256"],
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
        f"MATCH (a)-[r:{row['type']}]->(b) RETURN properties(r) AS properties",
        from_uid=row["from_uid"],
        to_uid=row["to_uid"],
    ).data()


def _assert_exact_relation(data: Mapping[str, Any], row: Mapping[str, Any], observed: Mapping[str, Any]) -> None:
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
    labels = {label for row in data["nodes"] for label in row["labels"]}
    reltypes = {row["type"] for row in data["relations"]}
    missing_labels = labels - set(registry["labels"] or [])
    missing_reltypes = reltypes - set(registry["relations"] or [])
    if missing_labels or missing_reltypes:
        raise RuntimeError(
            f"unregistered schema tokens: labels={sorted(missing_labels)}, "
            f"relations={sorted(missing_reltypes)}"
        )


def _exact_readback(tx: Any, data: Mapping[str, Any]) -> dict[str, int]:
    expected_nodes = {
        row["uid"]: {"labels": row["labels"], "properties": _expected_node_properties(data, row)}
        for row in data["nodes"]
    }
    observed_nodes = _find_unique_nodes(tx, list(expected_nodes))
    if set(observed_nodes) != set(expected_nodes):
        raise RuntimeError("exact scientific-node readback UID mismatch")
    for uid, expected in expected_nodes.items():
        _assert_exact_node(uid, expected, observed_nodes[uid])
    for relation in data["relations"]:
        observed = _relation_rows(tx, relation)
        if len(observed) != 1:
            raise RuntimeError(
                "exact scientific-relationship readback mismatch: "
                f"{(relation['from_uid'], relation['type'], relation['to_uid'])}"
            )
        _assert_exact_relation(data, relation, observed[0])
    owned_nodes = tx.run(
        "MATCH (n {ontology_bundle_uid:$uid}) RETURN count(n) AS count",
        uid=data["bundle_uid"],
    ).single()["count"]
    owned_relations = tx.run(
        "MATCH ()-[r {ontology_bundle_uid:$uid}]->() RETURN count(r) AS count",
        uid=data["bundle_uid"],
    ).single()["count"]
    if owned_nodes != len(expected_nodes) or owned_relations != len(data["relations"]):
        raise RuntimeError("scientific projection ownership readback drifted")
    return {"readback_nodes": owned_nodes, "readback_relations": owned_relations}


def publish(data: dict[str, Any], config: dict[str, str]) -> dict[str, int]:
    """Create the bounded projection transactionally; anchors are MATCH-only."""
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
                present_anchors = _find_unique_nodes(tx, anchor_uids)
                if set(present_anchors) != set(anchor_uids):
                    raise RuntimeError("required scientific projection anchors are missing")
                names = {row["uid"]: row["name"] for row in data["anchors"]}
                if any(present_anchors[uid]["properties"].get("name") != name for uid, name in names.items()):
                    raise RuntimeError("required scientific projection anchor name drifted")

                new_uids = [row["uid"] for row in data["nodes"]]
                existing = _find_unique_nodes(tx, new_uids)
                if existing and len(existing) != len(new_uids):
                    raise RuntimeError("refusing a partial pre-existing scientific projection")
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

                existing_relations: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
                for row in data["relations"]:
                    key = (row["from_uid"], row["type"], row["to_uid"])
                    found = _relation_rows(tx, row)
                    if len(found) > 1:
                        raise RuntimeError(f"duplicate existing scientific relationship: {key}")
                    if found:
                        _assert_exact_relation(data, row, found[0])
                    existing_relations[key] = found
                if any(existing_relations.values()) and not all(existing_relations.values()):
                    raise RuntimeError("refusing a partial pre-existing scientific relation set")
                created_relations = 0
                if not any(existing_relations.values()):
                    for row in data["relations"]:
                        tx.run(
                            "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
                            f"CREATE (a)-[r:{row['type']}]->(b) SET r=$properties",
                            from_uid=row["from_uid"],
                            to_uid=row["to_uid"],
                            properties=_expected_relation_properties(data, row),
                        ).consume()
                        created_relations += 1
                return {
                    "created_nodes": 0 if existing else len(new_uids),
                    "created_relations": created_relations,
                    "existing_nodes": len(existing),
                    "existing_relations": len(data["relations"]) - created_relations,
                    **_exact_readback(tx, data),
                }

            return session.execute_write(transaction)
    finally:
        driver.close()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ontology",
        type=Path,
        default=root / "ontology/identity/human_universal_body/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_ONTOLOGY.v1.json",
    )
    parser.add_argument("--source-config", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.ontology.read_text(encoding="utf-8"))
    validate_data(data, root)
    if not args.apply:
        print(json.dumps({"new_nodes": len(data["nodes"]), "relations": len(data["relations"]), "status": "VALIDATED_ONLY_NOT_PUBLISHED"}, sort_keys=True))
        return
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config")
    print(json.dumps({**publish(data, read_flat_yaml(args.source_config)), "status": "APPLIED_NEW_NODES_ONLY"}, sort_keys=True))


if __name__ == "__main__":
    main()
