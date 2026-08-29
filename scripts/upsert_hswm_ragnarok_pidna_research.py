#!/usr/bin/env python3
"""Validate and explicitly publish the bounded Ragnarok/PIDNA research KG projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "hswm-ragnarok-pidna-research-ontology/v1"
BUNDLE_UID = "sym:AbstractNode:hswm-ragnarok-pidna-research-ontology-2026-08-29"
REGISTRY_UID = "sym:KG_INFRA:schema-registry-v1-2026-08-03"
STATUS = "RESEARCH_PROJECTS_INITIALIZED_INTEGRATED_CLAIMS_UNJUDGED"
NONCLAIM = (
    "RESEARCH_KG_PROJECTION_ONLY_NOT_HSWM_COGNITION_LEARNING_ASCENT_"
    "EFFICACY_OR_SCIENTIFIC_DISCOVERY"
)
EXPECTED_COUNTS = {
    "nodes": 31,
    "anchors": 10,
    "relations": 78,
    "projects": 2,
    "hypotheses": 9,
    "source_records": 9,
}
EXPECTED_PROJECTION_SHA256 = (
    "ee7cb716f27ff12be31f8950ce6f35f3dd1a5aade9a6b8ddfc852c514fddf23c"
)
PREVIOUS_PROJECTION_SHA256 = (
    "e39de54f591c8f5b3b98984ff5f922964733f3cb4a298713dc9aea2945019302"
)
EXPECTED_PROJECT_UIDS = {
    "sym:ResearchProgram:hswm-ragnarok-research-2026-08-29",
    "sym:ResearchProgram:hswm-pidna-research-2026-08-29",
}
EXPECTED_FCL_SCOPE = {
    "mapped": ["FCL-1", "FCL-2", "FCL-3", "FCL-4", "FCL-5", "FCL-7", "FCL-8"],
    "out_of_scope": ["FCL-6"],
}
PIDNA_CONCEPT_UID = "sym:Concept:pidna-pure-intelligence-dna"
UPGRADE_ADDED_RELATION_KEYS = frozenset(
    {
        (
            "sym:Concept:pidna-functional-scale-recurrence",
            "SPECULATIVE_LINK",
            "sym:Concept:hswm-fractal-law-emergent-coalition",
        ),
        (
            "sym:Concept:pidna-functional-scale-recurrence",
            "SPECULATIVE_LINK",
            "sym:Concept:hswm-fractal-law-topology-morphogenesis",
        ),
        (
            "sym:Concept:pidna-functional-scale-recurrence",
            "SPECULATIVE_LINK",
            "sym:Concept:hswm-fractal-law-diachronic-continuity",
        ),
        (
            "sym:Hypothesis:ragnarok-causal-ownership",
            "SPECULATIVE_LINK",
            "sym:Concept:hswm-fractal-law-local-causal-learning",
        ),
        *(
            (
                "sym:Hypothesis:ragnarok-scale-closure",
                "SPECULATIVE_LINK",
                f"sym:Concept:hswm-fractal-law-{suffix}",
            )
            for suffix in (
                "composition-preservation",
                "emergent-coalition",
                "multiscale-credit",
                "topology-morphogenesis",
                "diachronic-continuity",
            )
        ),
    }
)
EXPECTED_HISTORICAL_DIGESTS = {
    "lakatotree/TOUCH_THE_SKY.md": (
        "b5b621e4fa528b502dd31a45c5894000aac082a525b335cc97f3cba3ef3b4745"
    ),
    "lakatotree/docs/PIDNA.md": (
        "d2c982e8a8db1ebba463224c7ca1c4e5e01f87a8b8ebb7b66ccb0bc09590e162"
    ),
    "lakatotree/formal/Pidna.lean": (
        "ff15396aee69b0327c252bb11bb59170a470f4744ad00ac146ea3ea9f77284dd"
    ),
}
SAFE_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SAFE_RELATION = re.compile(r"[A-Z][A-Z0-9_]*")
SHA256 = re.compile(r"[0-9a-f]{64}")


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
    return (
        value is None
        or isinstance(value, (str, bool, int, float))
        or (
            isinstance(value, list)
            and all(
                item is not None and isinstance(item, (str, bool, int, float))
                for item in value
            )
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
    """Fail closed before an authority, source, graph, or claim-boundary drift."""
    expected_top = {
        "schema_version",
        "bundle_uid",
        "status",
        "nonclaim",
        "artifact_bindings",
        "historical_source_digests",
        "expected_counts",
        "anchors",
        "nodes",
        "relations",
    }
    if set(data) != expected_top:
        raise ValueError("unexpected research ontology top-level shape")
    if data["schema_version"] != SCHEMA_VERSION or data["bundle_uid"] != BUNDLE_UID:
        raise ValueError("unexpected research ontology identity")
    if data["status"] != STATUS or data["nonclaim"] != NONCLAIM:
        raise ValueError("research status or nonclaim boundary drifted")
    if data["expected_counts"] != EXPECTED_COUNTS:
        raise ValueError("declared research ontology counts drifted")

    bindings = data["artifact_bindings"]
    if type(bindings) is not list or len(bindings) != 4:
        raise ValueError("exactly four project artifact bindings are required")
    bound_paths: set[str] = set()
    for row in bindings:
        if set(row) != {"path", "sha256"} or not SHA256.fullmatch(
            row.get("sha256", "")
        ):
            raise ValueError("invalid project artifact binding")
        path = repo_root / row["path"]
        if (
            row["path"] in bound_paths
            or not path.is_file()
            or _sha(path) != row["sha256"]
        ):
            raise ValueError(f"project artifact binding drifted: {row['path']}")
        bound_paths.add(row["path"])
    expected_paths = {
        "_research/ragnarok/README.md",
        "_research/ragnarok/project.v1.json",
        "_research/pidna/README.md",
        "_research/pidna/project.v1.json",
    }
    if bound_paths != expected_paths:
        raise ValueError("project artifact binding set drifted")

    historical = data["historical_source_digests"]
    if type(historical) is not list or len(historical) != 3:
        raise ValueError("historical source digest set drifted")
    observed_historical: dict[str, str] = {}
    for row in historical:
        if (
            set(row) != {"path_identity", "sha256", "availability"}
            or row.get("availability")
            != "LOCAL_RETIRED_ARCHIVE_READ_ONLY_NOT_REPOSITORY_DEPENDENCY"
            or not SHA256.fullmatch(row.get("sha256", ""))
        ):
            raise ValueError(
                "historical source record is unsafe or overclaims availability"
            )
        if row["path_identity"] in observed_historical:
            raise ValueError("duplicate historical source path identity")
        observed_historical[row["path_identity"]] = row["sha256"]
    if observed_historical != EXPECTED_HISTORICAL_DIGESTS:
        raise ValueError("historical PIDNA source digests drifted")

    project_manifests = [
        json.loads(
            (repo_root / "_research/ragnarok/project.v1.json").read_text(
                encoding="utf-8"
            )
        ),
        json.loads(
            (repo_root / "_research/pidna/project.v1.json").read_text(encoding="utf-8")
        ),
    ]
    if {row["kg"]["project_uid"] for row in project_manifests} != EXPECTED_PROJECT_UIDS:
        raise ValueError("project manifest KG identities drifted")
    if any(
        row["authority"]["scientific_status"] != "UNJUDGED" for row in project_manifests
    ):
        raise ValueError("project manifest scientific status overclaims")
    if any(
        row.get("fcl_scope", {}).get("mapped") != EXPECTED_FCL_SCOPE["mapped"]
        or row.get("fcl_scope", {}).get("out_of_scope")
        != EXPECTED_FCL_SCOPE["out_of_scope"]
        or not row.get("fcl_scope", {}).get("boundary")
        for row in project_manifests
    ):
        raise ValueError("project manifest FCL scope drifted")
    if any(
        row["kg"]["ontology_path"]
        != str(
            Path("ontology/identity/hswm_core")
            / "HSWM_RAGNAROK_PIDNA_RESEARCH_ONTOLOGY.v1.json"
        )
        for row in project_manifests
    ):
        raise ValueError("project manifest ontology path drifted")

    anchors, nodes, relations = data["anchors"], data["nodes"], data["relations"]
    if not all(type(rows) is list for rows in (anchors, nodes, relations)):
        raise ValueError("anchors, nodes, and relations must be arrays")
    if (len(nodes), len(anchors), len(relations)) != (
        EXPECTED_COUNTS["nodes"],
        EXPECTED_COUNTS["anchors"],
        EXPECTED_COUNTS["relations"],
    ):
        raise ValueError("research ontology count mismatch")
    if any(type(row) is not dict for row in anchors + nodes + relations):
        raise ValueError("research ontology records must be objects")

    anchor_uids: list[str] = []
    for row in anchors:
        if set(row) != {"uid", "name", "required_labels"} or not all(
            isinstance(row.get(key), str) and row[key] for key in ("uid", "name")
        ):
            raise ValueError("invalid anchor descriptor")
        if (
            type(row["required_labels"]) is not list
            or not row["required_labels"]
            or len(row["required_labels"]) != len(set(row["required_labels"]))
            or any(
                not isinstance(label, str) or not SAFE_LABEL.fullmatch(label)
                for label in row["required_labels"]
            )
        ):
            raise ValueError("invalid anchor label contract")
        anchor_uids.append(row["uid"])
    if len(anchor_uids) != len(set(anchor_uids)):
        raise ValueError("duplicate research ontology anchor")

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
    node_uids: list[str] = []
    for row in nodes:
        if set(row) != {"uid", "labels", "properties"}:
            raise ValueError("node record shape drifted")
        uid, labels, properties = row["uid"], row["labels"], row["properties"]
        if not isinstance(uid, str) or not uid:
            raise ValueError("invalid node UID")
        if (
            type(labels) is not list
            or not labels
            or len(labels) != len(set(labels))
            or any(
                not isinstance(label, str) or not SAFE_LABEL.fullmatch(label)
                for label in labels
            )
        ):
            raise ValueError("unsafe node labels")
        if type(properties) is not dict or required_properties - properties.keys():
            raise ValueError(
                "node lacks required authority, status, or boundary properties"
            )
        if properties["projection_nonclaim"] != NONCLAIM:
            raise ValueError("node nonclaim boundary drifted")
        if properties["review_required"] is not True:
            raise ValueError("research projection nodes must remain review-required")
        if any(
            not isinstance(key, str) or not _neo_scalar_or_list(value)
            for key, value in properties.items()
        ):
            raise ValueError("node has unsafe Neo4j properties")
        if any(
            not properties.get(key) for key in required_properties - {"review_required"}
        ):
            raise ValueError("node has an empty required property")
        node_uids.append(uid)
    duplicates = {
        uid: count
        for uid, count in Counter(node_uids + anchor_uids).items()
        if count > 1
    }
    if duplicates or set(node_uids) & set(anchor_uids):
        raise ValueError(f"duplicate or overlapping UIDs: {duplicates}")
    if BUNDLE_UID not in node_uids:
        raise ValueError("bundle node is absent")

    projects = [row for row in nodes if "ResearchProgram" in row["labels"]]
    hypotheses = [row for row in nodes if "Hypothesis" in row["labels"]]
    sources = [row for row in nodes if "SourceDocument" in row["labels"]]
    if (len(projects), len(hypotheses), len(sources)) != (
        EXPECTED_COUNTS["projects"],
        EXPECTED_COUNTS["hypotheses"],
        EXPECTED_COUNTS["source_records"],
    ):
        raise ValueError("project, hypothesis, or source family count drifted")
    if {row["uid"] for row in projects} != EXPECTED_PROJECT_UIDS:
        raise ValueError("research program identities drifted")
    if any(
        row["properties"]["epistemic_state"] != "WORKING_HYPOTHESIS"
        for row in hypotheses
    ):
        raise ValueError("hypothesis scientific state overclaims")

    endpoints = set(node_uids + anchor_uids)
    relation_keys: list[tuple[str, str, str]] = []
    for row in relations:
        if (
            set(row)
            != {"from_uid", "type", "to_uid", "authority_class", "scope", "status"}
            or not isinstance(row.get("type"), str)
            or not SAFE_RELATION.fullmatch(row["type"])
            or row.get("from_uid") not in endpoints
            or row.get("to_uid") not in endpoints
            or any(
                not isinstance(row.get(key), str) or not row[key]
                for key in ("authority_class", "scope", "status")
            )
        ):
            raise ValueError("relation shape or endpoint closure drifted")
        if row["from_uid"] in anchor_uids and row["to_uid"] in anchor_uids:
            raise ValueError("projection may not create anchor-to-anchor relations")
        if row["type"] == "EVIDENCE_FOR":
            raise ValueError("research projection may not claim HSWM efficacy evidence")
        relation_keys.append((row["from_uid"], row["type"], row["to_uid"]))
    if len(relation_keys) != len(set(relation_keys)):
        raise ValueError("duplicate research relationship identity")
    used = {
        endpoint for row in relations for endpoint in (row["from_uid"], row["to_uid"])
    }
    if endpoints - used:
        raise ValueError(f"unused projection endpoint: {sorted(endpoints - used)}")

    hypothesis_uids = {row["uid"] for row in hypotheses}
    hypothesis_owner_counts = Counter(
        row["to_uid"]
        for row in relations
        if row["type"] == "HAS_CONCEPT"
        and row["from_uid"] in EXPECTED_PROJECT_UIDS
        and row["to_uid"] in hypothesis_uids
    )
    if set(hypothesis_owner_counts) != hypothesis_uids or any(
        count != 1 for count in hypothesis_owner_counts.values()
    ):
        raise ValueError("every hypothesis must belong to exactly one research project")
    tested_hypotheses = {
        row["from_uid"]
        for row in relations
        if row["type"] in {"TESTS", "SPECULATIVE_LINK"}
        and row["from_uid"] in hypothesis_uids
    }
    if tested_hypotheses != hypothesis_uids:
        raise ValueError("every hypothesis must have a typed falsification target")

    historical_source_uids = {
        "sym:SourceDocument:lakatotree-touch-the-sky-historical",
        "sym:SourceDocument:lakatotree-pidna-historical",
    }
    source_concept_edges = {
        (row["from_uid"], row["to_uid"])
        for row in relations
        if row["type"] == "HAS_CONCEPT"
    }
    if not all(
        (uid, PIDNA_CONCEPT_UID) in source_concept_edges
        for uid in historical_source_uids
    ):
        raise ValueError("historical definition sources are not bound to PIDNA")
    anti_ragnarok_uid = "sym:Hypothesis:pidna-anti-ragnarok-verification"
    anti_targets = {
        row["to_uid"] for row in relations if row["from_uid"] == anti_ragnarok_uid
    }
    if anti_targets != {
        "sym:Concept:ragnarok-diagnostic-vector",
        "sym:DomainEvent:lx3_ragnarok",
    }:
        raise ValueError("PIDNA anti-Ragnarok coupling drifted")
    if _projection_digest(data) != EXPECTED_PROJECTION_SHA256:
        raise ValueError("research projection content digest drifted")


def _projection_digest(data: Mapping[str, Any]) -> str:
    return _canonical_sha(
        {
            "artifact_bindings": data["artifact_bindings"],
            "historical_source_digests": data["historical_source_digests"],
            "anchors": data["anchors"],
            "nodes": data["nodes"],
            "relations": data["relations"],
        }
    )


def _expected_node_properties(
    data: Mapping[str, Any], row: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "uid": row["uid"],
        **row["properties"],
        "ontology_bundle_uid": data["bundle_uid"],
        "ontology_projection_sha256": _projection_digest(data),
    }


def _expected_relation_properties(
    data: Mapping[str, Any], row: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "ontology_bundle_uid": data["bundle_uid"],
        "authority_class": row["authority_class"],
        "scope": row["scope"],
        "status": row["status"],
    }


def _relation_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return row["from_uid"], row["type"], row["to_uid"]


def _previous_node_contract(
    data: Mapping[str, Any], row: Mapping[str, Any]
) -> dict[str, Any]:
    properties = _expected_node_properties(data, row)
    properties["ontology_projection_sha256"] = PREVIOUS_PROJECTION_SHA256
    if row["uid"] == BUNDLE_UID:
        properties.pop("projection_revision")
        properties.pop("supersedes_projection_sha256")
    labels = list(row["labels"])
    if row["uid"] == PIDNA_CONCEPT_UID:
        labels = ["Concept", "CanonicalDefinition"]
    return {"labels": labels, "properties": properties}


def _previous_relations(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    previous = [
        row
        for row in data["relations"]
        if _relation_key(row) not in UPGRADE_ADDED_RELATION_KEYS
    ]
    if len(previous) != 69:
        raise RuntimeError("exact previous relationship contract drifted")
    return previous


def _publication_status(result: Mapping[str, int]) -> str:
    if result.get("upgraded_nodes", 0):
        return "UPGRADED_EXACT_PREVIOUS_PROJECTION"
    if result.get("created_nodes", 0):
        return "APPLIED_NEW_PROJECTION"
    return "VERIFIED_EXISTING_PROJECTION"


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


def _assert_exact_node(
    uid: str, expected: Mapping[str, Any], observed: Mapping[str, Any]
) -> None:
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
        row["uid"]: {
            "labels": row["labels"],
            "properties": _expected_node_properties(data, row),
        }
        for row in data["nodes"]
    }
    observed_nodes = _find_unique_nodes(tx, list(expected_nodes))
    if set(observed_nodes) != set(expected_nodes):
        raise RuntimeError("exact research-node readback UID mismatch")
    for uid, expected in expected_nodes.items():
        _assert_exact_node(uid, expected, observed_nodes[uid])
    for relation in data["relations"]:
        observed = _relation_rows(tx, relation)
        if len(observed) != 1:
            raise RuntimeError(
                "exact research-relationship readback mismatch: "
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
        raise RuntimeError("research projection ownership readback drifted")
    return {"readback_nodes": owned_nodes, "readback_relations": owned_relations}


def _assert_exact_previous_projection(
    tx: Any,
    data: Mapping[str, Any],
    observed_nodes: Mapping[str, Mapping[str, Any]],
) -> None:
    for row in data["nodes"]:
        _assert_exact_node(
            row["uid"],
            _previous_node_contract(data, row),
            observed_nodes[row["uid"]],
        )
    owned_nodes = tx.run(
        "MATCH (n {ontology_bundle_uid:$uid}) RETURN count(n) AS count",
        uid=data["bundle_uid"],
    ).single()["count"]
    if owned_nodes != len(data["nodes"]):
        raise RuntimeError("exact previous node ownership count drifted")

    for relation in _previous_relations(data):
        observed = _relation_rows(tx, relation)
        if len(observed) != 1:
            raise RuntimeError(
                "exact previous relationship readback mismatch: "
                f"{_relation_key(relation)}"
            )
        _assert_exact_relation(data, relation, observed[0])
    for relation in data["relations"]:
        if _relation_key(relation) in UPGRADE_ADDED_RELATION_KEYS and _relation_rows(
            tx, relation
        ):
            raise RuntimeError(
                "refusing a partial previous-projection upgrade: "
                f"{_relation_key(relation)}"
            )
    owned_relations = tx.run(
        "MATCH ()-[r {ontology_bundle_uid:$uid}]->() RETURN count(r) AS count",
        uid=data["bundle_uid"],
    ).single()["count"]
    if owned_relations != len(_previous_relations(data)):
        raise RuntimeError("exact previous relationship ownership count drifted")


def _upgrade_exact_previous_projection(tx: Any, data: Mapping[str, Any]) -> int:
    for row in data["nodes"]:
        updated = tx.run(
            "MATCH (n {uid:$uid, ontology_bundle_uid:$bundle_uid, "
            "ontology_projection_sha256:$previous_sha256}) "
            "SET n=$properties RETURN count(n) AS count",
            uid=row["uid"],
            bundle_uid=data["bundle_uid"],
            previous_sha256=PREVIOUS_PROJECTION_SHA256,
            properties=_expected_node_properties(data, row),
        ).single()["count"]
        if updated != 1:
            raise RuntimeError(
                f"exact previous node changed during upgrade: {row['uid']}"
            )
    tx.run(
        "MATCH (n {uid:$uid}) REMOVE n:CanonicalDefinition SET n:BridgeConcept",
        uid=PIDNA_CONCEPT_UID,
    ).consume()

    created = 0
    for row in data["relations"]:
        if _relation_key(row) not in UPGRADE_ADDED_RELATION_KEYS:
            continue
        tx.run(
            "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
            f"CREATE (a)-[r:{row['type']}]->(b) SET r=$properties",
            from_uid=row["from_uid"],
            to_uid=row["to_uid"],
            properties=_expected_relation_properties(data, row),
        ).consume()
        created += 1
    if created != len(UPGRADE_ADDED_RELATION_KEYS):
        raise RuntimeError("exact previous relationship upgrade count drifted")
    return created


def publish(
    data: dict[str, Any],
    config: dict[str, str],
    *,
    upgrade_exact_previous: bool = False,
) -> dict[str, int]:
    """Create, verify, or exactly upgrade the projection; anchors remain MATCH-only."""
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
                _registry_readback(tx, data)
                anchor_uids = [row["uid"] for row in data["anchors"]]
                present_anchors = _find_unique_nodes(tx, anchor_uids)
                if set(present_anchors) != set(anchor_uids):
                    missing = sorted(set(anchor_uids) - set(present_anchors))
                    raise RuntimeError(
                        f"required research anchors are missing: {missing}"
                    )
                for anchor in data["anchors"]:
                    observed = present_anchors[anchor["uid"]]
                    if observed["properties"].get("name") != anchor["name"]:
                        raise RuntimeError("required research anchor name drifted")
                    if not set(anchor["required_labels"]).issubset(observed["labels"]):
                        raise RuntimeError("required research anchor labels drifted")

                new_uids = [row["uid"] for row in data["nodes"]]
                existing = _find_unique_nodes(tx, new_uids)
                if existing and len(existing) != len(new_uids):
                    raise RuntimeError(
                        "refusing a partial pre-existing research projection"
                    )
                upgraded_nodes = 0
                if existing:
                    expected = {row["uid"]: row for row in data["nodes"]}
                    try:
                        for uid, observed in existing.items():
                            row = expected[uid]
                            _assert_exact_node(
                                uid,
                                {
                                    "labels": row["labels"],
                                    "properties": _expected_node_properties(data, row),
                                },
                                observed,
                            )
                    except RuntimeError:
                        if not upgrade_exact_previous:
                            raise
                        _assert_exact_previous_projection(tx, data, existing)
                        upgraded_nodes = len(existing)
                else:
                    for row in data["nodes"]:
                        labels = ":".join(row["labels"])
                        tx.run(
                            f"CREATE (n:{labels}) SET n=$properties",
                            properties=_expected_node_properties(data, row),
                        ).consume()

                if upgraded_nodes:
                    created_relations = _upgrade_exact_previous_projection(tx, data)
                    existing_relation_count = len(_previous_relations(data))
                else:
                    existing_relations: dict[
                        tuple[str, str, str], list[dict[str, Any]]
                    ] = {}
                    for row in data["relations"]:
                        key = _relation_key(row)
                        found = _relation_rows(tx, row)
                        if len(found) > 1:
                            raise RuntimeError(
                                f"duplicate existing research relationship: {key}"
                            )
                        if found:
                            _assert_exact_relation(data, row, found[0])
                        existing_relations[key] = found
                    if any(existing_relations.values()) and not all(
                        existing_relations.values()
                    ):
                        raise RuntimeError(
                            "refusing a partial pre-existing research relation set"
                        )
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
                    existing_relation_count = len(data["relations"]) - created_relations
                return {
                    "created_nodes": 0 if existing else len(new_uids),
                    "upgraded_nodes": upgraded_nodes,
                    "created_relations": created_relations,
                    "existing_nodes": len(existing),
                    "existing_relations": existing_relation_count,
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
        default=root
        / "ontology/identity/hswm_core/HSWM_RAGNAROK_PIDNA_RESEARCH_ONTOLOGY.v1.json",
    )
    parser.add_argument("--source-config", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--upgrade-exact-previous",
        action="store_true",
        help=(
            "allow the one pinned e39de54f... projection to advance in place; "
            "any node, relationship, owner, label, or digest drift aborts first"
        ),
    )
    args = parser.parse_args()
    data = json.loads(args.ontology.read_text(encoding="utf-8"))
    validate_data(data, root)
    if not args.apply:
        if args.upgrade_exact_previous:
            raise SystemExit("--upgrade-exact-previous requires --apply")
        print(
            json.dumps(
                {
                    "new_nodes": len(data["nodes"]),
                    "relations": len(data["relations"]),
                    "projection_sha256": _projection_digest(data),
                    "status": "VALIDATED_ONLY_NOT_PUBLISHED",
                },
                sort_keys=True,
            )
        )
        return
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config")
    result = publish(
        data,
        read_flat_yaml(args.source_config.expanduser()),
        upgrade_exact_previous=args.upgrade_exact_previous,
    )
    print(json.dumps({**result, "status": _publication_status(result)}, sort_keys=True))


if __name__ == "__main__":
    main()
