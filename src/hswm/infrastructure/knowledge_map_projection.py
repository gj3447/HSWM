"""Rebuild the fixed HSWM knowledge navigation snapshot; no live write path.

Uses the existing KG bundle RDF/SHACL/PROV compiler. Historical source bytes
come from a fixed Git cut, never from a dirty working tree. This is metadata
tooling, not a new runtime, cognition, authority, or scientific adjudicator.
"""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from hswm.infrastructure.kg_bundle_graph_view import KgBundleGraphView, KgBundleSource

ROOT = Path(__file__).resolve().parents[3]
CUT = "5cb22703cf42128dd204966087594ad8561a554d"
UID = "sym:AbstractNode:hswm-knowledge-map-2026-09-13"
INPUT_DIR = Path("ontology/knowledge_map")
TOPICS = INPUT_DIR / "HSWM_KNOWLEDGE_MAP_TOPICS_2026-09-13.v1.json"
COVERAGE = INPUT_DIR / "HSWM_KNOWLEDGE_MAP_COVERAGE_2026-09-13.v1.json"
BUNDLE = INPUT_DIR / "HSWM_KNOWLEDGE_MAP_2026-09-13.v1.json"
ARTIFACTS = Path("docs/operations/artifacts/hswm_knowledge_map_2026-09-13")
QUERIES = Path("ontology/queries/hswm_knowledge_map_2026-09-13")
QUERY_STEMS = {"Q1_topic_states", "Q2_current_entrypoints", "Q3_coverage_obligations",
               "Q4_source_status_ambiguities", "Q5_formal_vs_efficacy", "Q6_unresolved_source_bundle_uids"}
NONCLAIM = "SOURCE_BOUND_NAVIGATION_NOT_NEW_DESIGN_NOT_CANONICAL_STATE_NOT_LEARNING_NOT_EFFICACY"


def encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def blob(path: str, root: Path = ROOT) -> bytes:
    return subprocess.run(["git", "-C", str(root), "show", f"{CUT}:{path}"],
                          check=True, capture_output=True).stdout


def base_path(path: str) -> str:
    return path.split("#", 1)[0]


def source_uid(path: str) -> str:
    return UID + "-source-" + sha256(path.encode()).hexdigest()[:16]


def pointer(data: Any, value: str) -> Any:
    for key in value.lstrip("/").split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        data = data[int(key)] if isinstance(data, list) else data[key]
    return data


def compile_snapshot(root: Path = ROOT) -> tuple[dict, dict]:
    topics = json.loads((root / TOPICS).read_bytes())
    coverage = json.loads((root / COVERAGE).read_bytes())
    live_path = ARTIFACTS / "live-resolution.json"
    live = json.loads((root / live_path).read_bytes())
    if live["source_commit"] != CUT:
        raise ValueError("live resolution source cut mismatch")
    observations = {r["uid"]: r for r in live["records"]}
    if len(observations) != len(live["records"]):
        raise ValueError("duplicate live observation")
    for uid, observation in observations.items():
        matches = observation["matches"]
        if not isinstance(matches, list) or observation["resolution"] not in {"RESOLVED_UNIQUE", "NOT_FOUND"}:
            raise ValueError("ambiguous or invalid live identity")
        if observation["resolution"] == "NOT_FOUND":
            if matches:
                raise ValueError("NOT_FOUND has live matches")
        elif len(matches) != 1 or matches[0].get("uid") != uid:
            raise ValueError("RESOLVED_UNIQUE requires exactly one identical UID")
    for data in (topics, coverage):
        if data["authority"] != "SECONDARY_AI" or data["as_of"] != "2026-09-13":
            raise ValueError("curation authority/date mismatch")
    topic_ids = [t["id"] for t in topics["topics"]]
    expected_obligations = {f"FCL-{i}" for i in range(1, 9)} | {f"CR-{i}" for i in range(8)}
    actual_obligations = [o["id"] for o in coverage["obligations"]]
    if len(set(topic_ids)) != len(topic_ids) or set(actual_obligations) != expected_obligations or len(actual_obligations) != 16:
        raise ValueError("topic identity or FCL/CR coverage mismatch")
    tracked = set(subprocess.check_output(["git", "-C", str(root), "ls-tree", "-r", "--name-only", CUT]).decode().splitlines())
    ontology_paths = {p for p in tracked if p.startswith("ontology/") and "HSWM" in p and p.endswith(".json")}
    doc_paths = {p for p in tracked if p.startswith("docs/") and "HSWM" in p and p.endswith(".md")}
    entrypoints = {base_path(e["path"]) for t in topics["topics"] for e in t["entrypoints"]}
    paths = ontology_paths | doc_paths | entrypoints | {"README.md", "INDEX.md", "F1_R8_RESULTS_LOG.md", "ontology/identity/hswm_core/README.md"}
    for o in coverage["obligations"]:
        paths.update(base_path(p) for p in [o["source_path"], *o["existing_design_paths"], *o["evidence_paths"]])
    overrides = {r["path"]: r for r in topics["historical_overrides"]}
    for h in overrides.values():
        paths.update([h["path"], *h["successor_paths"]])
    paths.update(c["source_path"] for c in coverage["cross_links"])
    if paths - tracked:
        raise ValueError(f"source paths absent from fixed cut: {sorted(paths - tracked)}")
    raw = {p: blob(p, root) for p in sorted(paths)}
    parsed = {p: json.loads(b) for p, b in raw.items() if p.endswith(".json")}
    for topic in topics["topics"]:
        source_text = "\n".join(raw[base_path(e["path"])].decode() for e in topic["entrypoints"])
        for existing_uid in topic["existing_uids"]:
            if re.search(r"(?<![\w:.-])" + re.escape(existing_uid) + r"(?![\w:.-])", source_text) is None:
                raise ValueError(f"topic UID absent from its fixed-cut entrypoints: {existing_uid}")
    # The source catalog binds curation bytes outside ontology/; these are
    # metadata inputs, not node-owning ontology bundles or anchor-revision pins.
    input_paths = [TOPICS, COVERAGE, live_path, Path(__file__).relative_to(ROOT),
                   Path("src/hswm/infrastructure/kg_bundle_graph_view.py"),
                   Path("schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl")]
    query_paths = [p for p in sorted((root / QUERIES).iterdir()) if p.suffix in {".sparql", ".cypher"}]
    if {p.name for p in query_paths} != {stem + suffix for stem in QUERY_STEMS for suffix in (".sparql", ".cypher")}:
        raise ValueError("paired query inventory mismatch")
    input_paths.extend(p.relative_to(root) for p in query_paths)
    inputs = [{"path": str(p), "sha256": sha256((root / p).read_bytes()).hexdigest()} for p in input_paths]
    records = []
    for p, b in raw.items():
        data = parsed.get(p, {})
        bundle_uid = data.get("bundle_uid")
        observation = observations.get(bundle_uid, {})
        nav = "CURRENT_ENTRYPOINT" if p in entrypoints else "CATALOGUED_SNAPSHOT"
        if p in overrides:
            nav = "RETIRED_TARGET_FORMAT" if "CORE_RESPONSIBILITY" in p else "HISTORICAL_REFERENCE"
        rec = {"path": p, "sha256": sha256(b).hexdigest(), "byte_length": len(b), "source_commit": CUT,
               "source_bundle_uid": bundle_uid, "raw_source_status": str(data.get("status", "NOT_DECLARED")),
               "source_format": "NODE_BUNDLE" if isinstance(data.get("nodes"), list) else ("STRUCTURED_JSON" if p.endswith(".json") else "DOCUMENT"),
               "navigation_status": nav, "live_resolution": observation.get("resolution", "NOT_CHECKED")}
        if p in overrides:
            rec["navigation_reason"] = overrides[p]["reason"]
        records.append(rec)
    catalog = {"schema_version": "hswm-knowledge-map-source-catalog/v1", "authority": "SECONDARY_AI", "source_commit": CUT,
               "scope": {"ontology_rule": "tracked ontology/**/*.json containing HSWM in path", "ontology_count": len(ontology_paths),
                         "document_rule": "tracked docs/**/*.md containing HSWM in path", "document_count": len(doc_paths),
                         "additional_sources": "explicit curated entrypoints, coverage references, history successors and repository entrypoints",
                         "excluded": ["uncommitted work", "private runtime state and credentials", "external KG payloads", "transitive source payload expansion"],
                         "boundary": "Complete inventory for declared path classes; not exhaustive semantic indexing of every repository byte."},
               "curation_inputs": inputs, "sources": records}
    nodes: list[dict] = []
    relations: dict[tuple, dict] = {}
    anchors: dict[str, dict] = {}

    def node(uid: str, name: str, role: str, **props: Any) -> None:
        nodes.append({"uid": uid, "labels": ["Concept", "AbstractNode"], "properties": {
            "name": name, "description": name, "standard_graph_role": role, "authority_class": "SECONDARY_AI",
            "ontology_authority_class_v1": "SECONDARY_AI", "responsibility_owner": "hswm:knowledge-map:2026-09-13",
            "status": "SOURCE_BOUND_NAVIGATION", "claim_boundary": NONCLAIM, "projection_nonclaim": NONCLAIM,
            "source_commit": CUT, **props}})

    def edge(a: str, kind: str, b: str, scope: str = "SOURCE_BOUND_NAVIGATION_ONLY") -> None:
        relations[(a, kind, b)] = {"from_uid": a, "type": kind, "to_uid": b, "authority_class": "SECONDARY_AI",
                                  "scope": scope, "status": "PROJECTION_ONLY"}

    def reference(owner: str, original_uid: str) -> None:
        observation = observations.get(original_uid, {})
        if observation.get("resolution") == "RESOLVED_UNIQUE":
            match = observation["matches"][0]
            anchors[original_uid] = {"uid": original_uid, "name": match["name"], "required_labels": sorted(match["labels"])}
            edge(owner, "REFERS_TO", original_uid, "LIVE_IDENTITY_REFERENCE_ONLY_NOT_SOURCE_REVISION_EQUIVALENCE")

    node(UID, "HSWM 전체 지식 지도 — 기존 설계·구현·증명·실험·남은 의무", "KNOWLEDGE_MAP",
         topic_count=len(topic_ids), obligation_count=16, source_count=len(records),
         conceptual_delta="Connect existing artifacts and distinguish four evidence axes; no new HSWM target or success criterion.")
    reference(UID, "sym:Concept:hswm")
    catalog_uid = UID + "-catalog"
    node(catalog_uid, "Declared-scope complete source catalog", "SOURCE_CATALOG")
    edge(UID, "HAS_CONCEPT", catalog_uid)
    for rec in records:
        p = rec["path"]
        props = {k: v for k, v in rec.items() if k not in {"path", "sha256", "byte_length"} and v is not None}
        node(source_uid(p), Path(p).name, "SOURCE_SNAPSHOT", source_path=p, source_sha256=rec["sha256"],
             source_byte_length=rec["byte_length"], **props)
        edge(catalog_uid, "HAS_SOURCE", source_uid(p))
        if rec["source_bundle_uid"]:
            reference(source_uid(p), rec["source_bundle_uid"])
    for t in topics["topics"]:
        tuid = UID + "-topic-" + t["id"]
        node(tuid, t["title"], "KNOWLEDGE_MAP_TOPIC", **{k: v for k, v in t.items() if k not in {"id", "title", "entrypoints"}},
             curation_source_path=str(TOPICS), curation_source_pointer="/topics/" + str(topics["topics"].index(t)))
        edge(UID, "HAS_CONCEPT", tuid)
        for e in t["entrypoints"]:
            edge(tuid, "HAS_SOURCE", source_uid(base_path(e["path"])), "CURATED_ENTRYPOINT: " + e["role"])
        for existing in t["existing_uids"]:
            reference(tuid, existing)
    for o in coverage["obligations"]:
        original = pointer(parsed[o["source_path"]], o["source_pointer"])
        if o["existing_uid"] and original.get("uid") != o["existing_uid"]:
            raise ValueError("obligation source pointer UID mismatch")
        if o["id"].startswith("CR-") and original.get("id") != o["id"]:
            raise ValueError("constructive obligation source pointer mismatch")
        ouid = UID + "-obligation-" + o["id"].lower()
        node(ouid, o["id"] + ": " + o["title"], "COVERAGE_OBLIGATION", obligation_id=o["id"],
             **{k: v for k, v in o.items() if k not in {"id", "title"} and v is not None},
             curation_source_path=str(COVERAGE), engineering_status="SEE_BOUND_IMPLEMENTATION_AND_EVIDENCE_SOURCES")
        edge(UID, "HAS_CONCEPT", ouid)
        for p in [o["source_path"], *o["existing_design_paths"], *o["evidence_paths"]]:
            edge(ouid, "HAS_SOURCE", source_uid(base_path(p)))
        if o["existing_uid"]:
            reference(ouid, o["existing_uid"])
        for fcl in o["mapped_fcl_ids"]:
            if o["id"] != fcl:
                edge(ouid, "REQUIRES", UID + "-obligation-" + fcl.lower(), "CURATED_CR_TO_FCL_COVERAGE_NOT_PROOF")
    for p, h in overrides.items():
        for successor in h["successor_paths"]:
            edge(source_uid(successor), "PRESERVES", source_uid(p), "HISTORICAL_REFERENCE_NOT_AUTOMATIC_SUCCESS_OR_EFFICACY")
    for i, link in enumerate(coverage["cross_links"]):
        original = pointer(parsed[link["source_path"]], link["source_pointer"])
        if (original["from_uid"], original["type"], original["to_uid"]) != (link["from_path"], link["type"], link["to_path"]):
            raise ValueError("existing cross-link source mismatch")
        luid = UID + "-existing-link-" + str(i + 1)
        node(luid, "Existing " + link["type"] + " relation " + str(i + 1), "EXISTING_RELATION_REFERENCE",
             original_from_uid=link["from_path"], original_to_uid=link["to_path"], original_relation_type=link["type"],
             source_path=link["source_path"], source_pointer=link["source_pointer"],
             description=link["reason"], original_relation_status=str(original.get("status", "NOT_DECLARED")))
        edge(UID, "HAS_CONCEPT", luid)
        edge(luid, "HAS_SOURCE", source_uid(link["source_path"]))
        reference(luid, link["from_path"])
        reference(luid, link["to_path"])
    if len({n["uid"] for n in nodes}) != len(nodes):
        raise ValueError("duplicate projected identity")
    # Only bind catalog here: it transitively pins metadata inputs and Git blobs.
    # Non-node JSON never pretends to own an existing anchor revision.
    bundle = {"schema_version": "hswm-knowledge-map-ontology/v1", "bundle_uid": UID, "status": "SOURCE_BOUND_NAVIGATION_NOT_EFFICACY",
              "nonclaim": NONCLAIM, "authority_boundary": "SECONDARY_AI curation; originals retain their authority; live anchors are identity-only references.",
              "source_accessed_on": "2026-09-13", "artifact_bindings": [{"path": str(ARTIFACTS / "source-catalog.json"), "sha256": sha256(encode(catalog)).hexdigest()}],
              "expected_counts": {"nodes": len(nodes), "anchors": len(anchors), "relations": len(relations)},
              "anchors": [anchors[u] for u in sorted(anchors)], "nodes": sorted(nodes, key=lambda n: n["uid"]),
              "relations": [relations[k] for k in sorted(relations)]}
    return catalog, bundle


def build(*, check: bool = False, root: Path = ROOT) -> dict:
    catalog, bundle = compile_snapshot(root)
    bundle_bytes = encode(bundle)
    view = KgBundleGraphView.from_bundles(sources=(KgBundleSource(
        source_id="hswm-knowledge-map-2026-09-13", raw_bytes=bundle_bytes,
        sha256=sha256(bundle_bytes).hexdigest(), byte_length=len(bundle_bytes)),), profile="v2")
    shacl = plain(view.validate_shacl(shapes=(root / "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl").read_bytes()))
    if not shacl["conforms"]:
        raise ValueError(shacl["report_text"])
    results = {p.name: plain(view.query(p.read_text())) for p in sorted((root / QUERIES).glob("*.sparql"))}
    # SPARQL GROUP_CONCAT does not promise member order. These three cells
    # represent sets of delimiter-free FCL IDs/IRIs; normalize only those sets.
    for row in results["Q3_coverage_obligations.sparql"]:
        for field in ("mappedFcls", "requiredFclObligations", "requiredFcls"):
            row[field]["value"] = "|".join(sorted(set(row[field]["value"].split("|"))))
    counts = {k: len(v) for k, v in results.items()}
    if len(results) != 6 or counts["Q1_topic_states.sparql"] != 13:
        raise ValueError("query coverage mismatch")
    q3 = results["Q3_coverage_obligations.sparql"]
    if len(q3) != 16 or any(r["obligation"] is None for r in q3) or len({r["requiredObligationId"]["value"] for r in q3}) != 16:
        raise ValueError("query found missing coverage obligation")
    validation = {"schema_version": "hswm-knowledge-map-validation/v1", "source_commit": CUT,
                  "bundle_sha256": sha256(bundle_bytes).hexdigest(), "counts": bundle["expected_counts"],
                  "source_count": len(catalog["sources"]), "scope": catalog["scope"], "shacl": shacl,
                  "query_row_counts": counts, "navigation_counts": dict(Counter(s["navigation_status"] for s in catalog["sources"])),
                  "query_serialization": "Q3 GROUP_CONCAT set cells sorted lexically; row order uses existing RDF view canonical sorting",
                  "claim_boundary": NONCLAIM}
    index = ["# HSWM 원문 목록 — 2026-09-13", "", f"고정 Git source cut: `{CUT}`. 아래 링크는 이 commit의 원문을 가리킵니다.", "",
             "전체 목록의 범위는 source-catalog.json에 명시합니다. CURRENT_ENTRYPOINT는 읽기 진입점이며 효능 판정이 아닙니다.", "",
             "| 원문 | 탐색 상태 | 원문 형식 |", "|---|---|---|"]
    for source in catalog["sources"]:
        path = source["path"]
        index.append(f"| [{path}](https://github.com/gj3447/HSWM/blob/{CUT}/{path}) | {source['navigation_status']} | {source['source_format']} |")
    artifacts = {BUNDLE: bundle_bytes, ARTIFACTS / "source-catalog.json": encode(catalog),
                 ARTIFACTS / "knowledge-map.nq": view.nquads, ARTIFACTS / "descriptor.json": encode(plain(view.descriptor)),
                 ARTIFACTS / "provenance.jsonld": view.prov_o_envelope(), ARTIFACTS / "query-results.json": encode(results),
                 ARTIFACTS / "validation.json": encode(validation), ARTIFACTS / "source-index.md": ("\n".join(index) + "\n").encode()}
    for path, content in artifacts.items():
        target = root / path
        if check:
            if not target.is_file() or target.read_bytes() != content:
                raise ValueError(f"derived artifact drift: {path}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    return validation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify existing bytes without writing")
    args = parser.parse_args()
    print(json.dumps(build(check=args.check), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
