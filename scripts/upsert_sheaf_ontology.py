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

from hswm.infrastructure import kg_legacy_projection

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
    if data["module_uid"] not in concept_uids:
        raise ValueError("module_uid must identify a declared concept")
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


def _projection(data: dict[str, Any]) -> dict[str, Any]:
    validate_data(data)
    binding = data["kg_schema_binding"]
    nodes: list[dict[str, Any]] = []
    relations: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add_nodes(rows: list[dict[str, Any]], labels: list[str], properties: list[str]) -> None:
        for row in rows:
            node_labels = list(labels)
            if row["uid"] == data["module_uid"]:
                node_labels.append(binding["module_extra_label"])
            nodes.append({"uid": row["uid"], "labels": node_labels,
                          "properties": {key: row.get(key) for key in properties}})

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
    add_nodes(bundle, binding["bundle_labels"], [
        "name", "schema_version", "status", "created_at", "authority_boundary",
        "implementation_order", "nonclaims",
    ])
    concepts = [{
        **row,
        "sheaf_research_kind_v1": row["kind"],
        "sheaf_research_definition_v1": row["definition"],
        "sheaf_research_bundle_uid_v1": data["bundle_uid"],
    } for row in data["concepts"]]
    add_nodes(concepts, binding["concept_labels"], [
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
    add_nodes(source_rows, binding["source_labels"], [
        "name", "title", "authors", "year", "url", "arxiv_id", "publication_status",
        "supports_topics", "sheaf_research_bundle_uid_v1",
    ])
    mapping_rows = [{
        **row,
        "authority": "NONCANONICAL_RESEARCH_MAPPING",
        "sheaf_research_bundle_uid_v1": data["bundle_uid"],
    } for row in data["hswm_mappings"]]
    add_nodes(mapping_rows, binding["mapping_labels"], [
        "name", "hswm_component", "sheaf_concept_uid", "correspondence", "status",
        "caveat", "authority", "sheaf_research_bundle_uid_v1",
    ])

    def add_edge(source: str, kind: str, target: str) -> None:
        # The historical MERGE projection coalesces aliases onto one pair edge.
        key = (source, kind, target)
        relations[key] = {"from_uid": source, "type": kind, "to_uid": target,
                          "properties": {"ontology_bundle_uid": data["bundle_uid"]}}

    bundle_uid = data["bundle_uid"]
    module_uid = data["module_uid"]
    for group, role in (("concepts", "concept"), ("sources", "source"), ("hswm_mappings", "mapping")):
        for row in data[group]:
            add_edge(bundle_uid, binding["bundle_relations"][role], row["uid"])
    add_edge(bundle_uid, binding["bundle_relations"]["module"], module_uid)
    for row in data["concepts"]:
        if row["uid"] != module_uid:
            add_edge(module_uid, binding["bundle_relations"]["concept"], row["uid"])
    for row in data["hswm_mappings"]:
        add_edge(row["uid"], binding["mapping_target_relation"], row["sheaf_concept_uid"])
    aliases = binding["relationship_type_aliases"]
    for row in data["concept_relations"]:
        add_edge(row["from_uid"], aliases.get(row["type"], row["type"]), row["to_uid"])
    sources_by_concept: dict[str, list[str]] = defaultdict(list)
    for link in data["source_concept_links"]:
        for uid in link["concept_uids"]:
            add_edge(link["source_uid"], binding["source_support_relation"], uid)
            sources_by_concept[uid].append(link["source_uid"])
    for mapping in data["hswm_mappings"]:
        for uid in sources_by_concept[mapping["sheaf_concept_uid"]]:
            add_edge(mapping["uid"], binding["mapping_source_relation"], uid)
    projection = {"bundle_uid": bundle_uid, "nodes": nodes, "relations": list(relations.values())}
    kg_legacy_projection.validate_projection(projection)
    return projection


def load_ontology(data: dict[str, Any], config: dict[str, str]) -> dict[str, int]:
    projection = _projection(data)
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("--apply requires the optional `kg` dependency") from exc
    driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
    try:
        with driver.session(database=config["database"]) as session:
            result = session.execute_write(kg_legacy_projection.publish_projection, projection)
        sources_by_concept: dict[str, list[str]] = defaultdict(list)
        for link in data["source_concept_links"]:
            for uid in link["concept_uids"]:
                sources_by_concept[uid].append(link["source_uid"])
        return {**result, "concepts": len(data["concepts"]), "sources": len(data["sources"]),
                "mappings": len(data["hswm_mappings"]), "concept_relations": len(data["concept_relations"]),
                "source_concept_links": sum(len(link["concept_uids"]) for link in data["source_concept_links"]),
                "mapping_source_links": sum(len(sources_by_concept[m["sheaf_concept_uid"]]) for m in data["hswm_mappings"])}
    finally:
        driver.close()


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
    _projection(data)
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
