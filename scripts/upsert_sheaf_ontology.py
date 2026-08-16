#!/usr/bin/env python3
"""Validate the HSWM sheaf ontology and optionally run its legacy KG loader.

Validation is the default. Direct KG mutation requires an explicit ``--apply``
and source config because the active HSWM path uses the bounded external
ontology adapter, not raw Cypher writes.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from typing import Any

REGISTRY_UID = "sym:KG_INFRA:schema-registry-v1-2026-08-03"
SAFE_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SAFE_RELATION = re.compile(r"[A-Z][A-Z0-9_]*")


def read_flat_yaml(path: Path) -> dict[str, str]:
    """Read the intentionally flat Neo4j source config without exposing secrets."""
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


def require_safe_tokens(tokens: list[str], field: str, pattern: re.Pattern[str]) -> None:
    invalid = sorted({token for token in tokens if not pattern.fullmatch(token)})
    if invalid:
        raise ValueError(f"unsafe {field}: {invalid}")


def schema_tokens(data: dict[str, Any]) -> tuple[set[str], set[str]]:
    binding = data["kg_schema_binding"]
    labels = {
        *binding["bundle_labels"],
        *binding["concept_labels"],
        binding["module_extra_label"],
        *binding["source_labels"],
        *binding["mapping_labels"],
    }
    relations = {
        *binding["bundle_relations"].values(),
        binding["mapping_target_relation"],
        binding["source_support_relation"],
        binding["mapping_source_relation"],
    }
    aliases = binding["relationship_type_aliases"]
    relations.update(aliases.get(row["type"], row["type"]) for row in data["concept_relations"])
    require_safe_tokens(sorted(labels), "labels", SAFE_LABEL)
    require_safe_tokens(sorted(relations), "relationship types", SAFE_RELATION)
    return labels, relations


def validate_data(data: dict[str, Any]) -> None:
    if data["schema_version"] != "hswm-sheaf-ontology/v1":
        raise ValueError("unsupported ontology schema")
    groups = [data["concepts"], data["sources"], data["hswm_mappings"]]
    all_uids = [data["bundle_uid"], *[row["uid"] for group in groups for row in group]]
    duplicates = [uid for uid, count in Counter(all_uids).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate ontology UIDs: {duplicates}")
    concept_uids = {row["uid"] for row in data["concepts"]}
    source_uids = {row["uid"] for row in data["sources"]}
    for relation in data["concept_relations"]:
        if relation["from_uid"] not in concept_uids or relation["to_uid"] not in concept_uids:
            raise ValueError(f"concept relation has an unknown endpoint: {relation}")
    for link in data["source_concept_links"]:
        if link["source_uid"] not in source_uids or not set(link["concept_uids"]) <= concept_uids:
            raise ValueError(f"source link has an unknown endpoint: {link}")
    for mapping in data["hswm_mappings"]:
        if mapping["sheaf_concept_uid"] not in concept_uids:
            raise ValueError(f"mapping has an unknown target: {mapping['uid']}")
    schema_tokens(data)


def cypher_labels(labels: list[str]) -> str:
    require_safe_tokens(labels, "labels", SAFE_LABEL)
    return ":".join(labels)


def load_ontology(data: dict[str, Any], config: dict[str, str]) -> dict[str, int]:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:  # pragma: no cover - exercised only with --apply
        raise RuntimeError("--apply requires the optional `kg` dependency") from exc

    binding = data["kg_schema_binding"]
    wanted_labels, wanted_relations = schema_tokens(data)
    all_uids = [
        data["bundle_uid"],
        *[row["uid"] for row in data["concepts"]],
        *[row["uid"] for row in data["sources"]],
        *[row["uid"] for row in data["hswm_mappings"]],
    ]
    driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
    driver.verify_connectivity()
    try:
        with driver.session(database=config["database"]) as session:
            registry = session.run(
                "MATCH (r:SchemaRegistry {uid:$uid}) "
                "RETURN r.allowed_labels AS labels, r.allowed_reltypes AS relations",
                uid=REGISTRY_UID,
            ).single()
            if not registry:
                raise RuntimeError(f"KG schema registry not found: {REGISTRY_UID}")
            missing_labels = wanted_labels - set(registry["labels"] or [])
            missing_relations = wanted_relations - set(registry["relations"] or [])
            if missing_labels or missing_relations:
                raise RuntimeError(
                    f"unregistered KG schema tokens: labels={sorted(missing_labels)}, "
                    f"relations={sorted(missing_relations)}"
                )
            found = session.run(
                "MATCH (n) WHERE n.uid IN $uids RETURN n.uid AS uid, elementId(n) AS eid",
                uids=all_uids,
            ).data()
            counts = Counter(row["uid"] for row in found)
            duplicates = {uid: count for uid, count in counts.items() if count > 1}
            if duplicates:
                raise RuntimeError(f"duplicate KG UIDs before upsert: {duplicates}")
            existing = {row["uid"]: row["eid"] for row in found}
            result = session.execute_write(_upsert_transaction, data, binding, existing)
        return result
    finally:
        driver.close()


def _upsert_transaction(tx: Any, data: dict[str, Any], binding: dict[str, Any], existing: dict[str, str]) -> dict[str, int]:
    eids = dict(existing)

    def upsert_rows(rows: list[dict[str, Any]], labels: list[str], properties: list[str]) -> None:
        label_clause = cypher_labels(labels)
        old = [{**row, "eid": existing[row["uid"]]} for row in rows if row["uid"] in existing]
        new = [row for row in rows if row["uid"] not in existing]
        assignments = ", ".join(f"n.{key}=row.{key}" for key in properties)
        if old:
            query = (
                f"UNWIND $rows AS row MATCH (n) WHERE elementId(n)=row.eid "
                f"SET n:{label_clause}, {assignments}, n.updatedAt=datetime() "
                "RETURN n.uid AS uid, elementId(n) AS eid"
            )
            for record in tx.run(query, rows=old):
                eids[record["uid"]] = record["eid"]
        if new:
            create_properties = ", ".join(["uid:row.uid", *[f"{key}:row.{key}" for key in properties]])
            query = (
                f"UNWIND $rows AS row CREATE (n:{label_clause} {{{create_properties}, "
                "createdAt:datetime(), updatedAt:datetime()}) "
                "RETURN n.uid AS uid, elementId(n) AS eid"
            )
            for record in tx.run(query, rows=new):
                eids[record["uid"]] = record["eid"]

    bundle = [{
        "uid": data["bundle_uid"],
        "name": "HSWM Sheaf Research Ontology 2026-08-15",
        "schema_version": data["schema_version"],
        "status": data["status"],
        "created_at": data["created_at"],
        "authority_boundary": data["authority_boundary"],
        "implementation_order": data["implementation_order"],
        "nonclaims": data["nonclaims"],
    }]
    upsert_rows(bundle, binding["bundle_labels"], [
        "name", "schema_version", "status", "created_at", "authority_boundary",
        "implementation_order", "nonclaims",
    ])
    concepts = [{
        **row,
        "sheaf_research_kind_v1": row["kind"],
        "sheaf_research_definition_v1": row["definition"],
        "sheaf_research_bundle_uid_v1": data["bundle_uid"],
    } for row in data["concepts"]]
    upsert_rows(concepts, binding["concept_labels"], [
        "name", "sheaf_research_kind_v1", "sheaf_research_definition_v1",
        "sheaf_research_bundle_uid_v1",
    ])
    source_rows = [{
        **row,
        "name": row["title"],
        "arxiv_id": row.get("arxiv_id"),
        "supports_topics": row["supports"],
        "sheaf_research_bundle_uid_v1": data["bundle_uid"],
    } for row in data["sources"]]
    upsert_rows(source_rows, binding["source_labels"], [
        "name", "title", "authors", "year", "url", "arxiv_id", "publication_status",
        "supports_topics", "sheaf_research_bundle_uid_v1",
    ])
    mapping_rows = [{
        **row,
        "authority": "NONCANONICAL_RESEARCH_MAPPING",
        "sheaf_research_bundle_uid_v1": data["bundle_uid"],
    } for row in data["hswm_mappings"]]
    upsert_rows(mapping_rows, binding["mapping_labels"], [
        "name", "hswm_component", "sheaf_concept_uid", "correspondence", "status",
        "caveat", "authority", "sheaf_research_bundle_uid_v1",
    ])

    module_eid = eids[data["module_uid"]]
    tx.run(
        f"MATCH (m) WHERE elementId(m)=$eid SET m:{binding['module_extra_label']}",
        eid=module_eid,
    ).consume()

    def merge_edges(rows: list[dict[str, str]], rel_type: str) -> None:
        require_safe_tokens([rel_type], "relationship types", SAFE_RELATION)
        tx.run(
            f"UNWIND $rows AS row MATCH (a),(b) "
            "WHERE elementId(a)=row.from_eid AND elementId(b)=row.to_eid "
            f"MERGE (a)-[r:{rel_type}]->(b) SET r.ontology_bundle_uid=$bundle_uid",
            rows=rows,
            bundle_uid=data["bundle_uid"],
        ).consume()

    bundle_eid = eids[data["bundle_uid"]]
    bundle_relations = binding["bundle_relations"]
    merge_edges([{"from_eid": bundle_eid, "to_eid": eids[row["uid"]]} for row in data["concepts"]], bundle_relations["concept"])
    merge_edges([{"from_eid": bundle_eid, "to_eid": module_eid}], bundle_relations["module"])
    merge_edges([{"from_eid": module_eid, "to_eid": eids[row["uid"]]} for row in data["concepts"] if row["uid"] != data["module_uid"]], bundle_relations["concept"])
    merge_edges([{"from_eid": bundle_eid, "to_eid": eids[row["uid"]]} for row in data["sources"]], bundle_relations["source"])
    merge_edges([{"from_eid": bundle_eid, "to_eid": eids[row["uid"]]} for row in data["hswm_mappings"]], bundle_relations["mapping"])
    merge_edges([
        {"from_eid": eids[row["uid"]], "to_eid": eids[row["sheaf_concept_uid"]]}
        for row in data["hswm_mappings"]
    ], binding["mapping_target_relation"])

    aliases = binding["relationship_type_aliases"]
    by_type: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in data["concept_relations"]:
        kg_type = aliases.get(row["type"], row["type"])
        by_type[kg_type].append({"from_eid": eids[row["from_uid"]], "to_eid": eids[row["to_uid"]]})
    for relation_type, rows in by_type.items():
        merge_edges(rows, relation_type)

    support_rows = [
        {"from_eid": eids[link["source_uid"]], "to_eid": eids[concept_uid]}
        for link in data["source_concept_links"] for concept_uid in link["concept_uids"]
    ]
    merge_edges(support_rows, binding["source_support_relation"])
    sources_by_concept: dict[str, list[str]] = defaultdict(list)
    for link in data["source_concept_links"]:
        for concept_uid in link["concept_uids"]:
            sources_by_concept[concept_uid].append(link["source_uid"])
    mapping_support_rows = [
        {"from_eid": eids[mapping["uid"]], "to_eid": eids[source_uid]}
        for mapping in data["hswm_mappings"]
        for source_uid in sources_by_concept[mapping["sheaf_concept_uid"]]
    ]
    merge_edges(mapping_support_rows, binding["mapping_source_relation"])
    return {
        "concepts": len(data["concepts"]),
        "sources": len(data["sources"]),
        "mappings": len(data["hswm_mappings"]),
        "concept_relations": len(data["concept_relations"]),
        "source_concept_links": len(support_rows),
        "mapping_source_links": len(mapping_support_rows),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ontology",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "ontology"
        / "field"
        / "sheaf"
        / "HSWM_SHEAF_ONTOLOGY.v1.json",
    )
    parser.add_argument("--source-config", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="explicitly use the legacy direct Neo4j writer",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="compatibility alias; validation is already the default",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = json.loads(args.ontology.read_text(encoding="utf-8"))
    validate_data(data)
    if not args.apply:
        print(json.dumps({
            "concepts": len(data["concepts"]),
            "sources": len(data["sources"]),
            "mappings": len(data["hswm_mappings"]),
            "concept_relations": len(data["concept_relations"]),
        }, sort_keys=True))
        return
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config; direct KG write is never implicit")
    result = load_ontology(data, read_flat_yaml(args.source_config))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
