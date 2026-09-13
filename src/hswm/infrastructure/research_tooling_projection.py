"""Deterministic, read-only projection of HSWM research-tooling findings."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any
from collections.abc import Mapping

from hswm.infrastructure.kg_bundle_graph_view import KgBundleGraphView, KgBundleSource

ROOT = Path(__file__).resolve().parents[3]
CUT = "c57f39a8c33bb86d19cfcaa40b880b944707e53d"
UID = "sym:AbstractNode:hswm-scientific-research-tooling-2026-09-13"
INPUT = Path("_research/graph_standards/research_tooling_2026-09-13")
FILES = ("repository-gap-inventory.json", "reproducibility-findings.json", "evaluation-formal-findings.json", "graph-standards-findings.json", "integrated-assessment.json")
BUNDLE = Path("ontology/research_tooling/HSWM_SCIENTIFIC_RESEARCH_TOOLING_2026-09-13.v1.json")
ARTIFACTS = Path("docs/research/artifacts/hswm_research_tooling_2026-09-13")
QUERIES = Path("ontology/queries/hswm_research_tooling_2026-09-13")
NONCLAIM = "TOOLING_PROJECTION_NOT_HSWM_COGNITION_NOT_CAUSAL_EFFICACY"
OWNER = "hswm:research-tooling:2026-09-13"
DISCOVERY = "sym:AbstractNode:hswm-knowledge-map-discovery-2026-09-13"


def encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def plain(value: Any) -> Any:
    if isinstance(value, Mapping): return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [plain(v) for v in value]
    return value


def blob(path: str, root: Path = ROOT) -> bytes:
    return subprocess.run(["git", "-C", str(root), "show", f"{CUT}:{path}"], check=True, capture_output=True).stdout


def uid(kind: str, source: str, identifier: str) -> str:
    return f"sym:AbstractNode:hswm-research-tooling-{kind}-{sha256((source + ':' + identifier).encode()).hexdigest()[:20]}"


def local_path(url: str) -> str | None:
    marker = "https://github.com/gj3447/HSWM/blob/main/"
    return url.removeprefix(marker) if url.startswith(marker) else None


def resolve_pointer(value: Any, pointer: str) -> Any:
    if not pointer.startswith("/"): raise ValueError("curation pointer is not a JSON pointer")
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def validate_curation_pointers(nodes: list[dict], root: Path) -> None:
    for node in nodes:
        props = node["properties"]
        try:
            selected = resolve_pointer(json.loads((root / props["curation_source_path"]).read_bytes()), props["curation_source_pointer"])
            if "source_id" in props and (not isinstance(selected, dict) or selected.get("id") != props["source_id"]):
                raise ValueError("pointer does not resolve its declared source ID")
            if props["standard_graph_role"] == "INTEGRATED_ASSESSMENT" and selected.get("candidate_id") != props["candidate_id"]:
                raise ValueError("pointer does not resolve its assessment")
            if props["standard_graph_role"] == "CAPABILITY_EVIDENCE" and selected.get("statement") != props.get("statement"):
                raise ValueError("pointer does not resolve its evidence statement")
        except (KeyError, IndexError, ValueError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid curation pointer: {node['uid']}") from error


def safe_props(row: dict[str, Any]) -> dict[str, Any]:
    reserved = {"name", "description", "status", "authority_class", "standard_graph_role", "responsibility_owner", "claim_boundary", "domain", "kind", "plane", "semantic_roles"}
    return {("source_" + k if k in reserved else k): v for k, v in row.items() if isinstance(v, (str, int, float, bool)) or (isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) for x in v))}


def compile_snapshot(root: Path = ROOT) -> tuple[dict, dict]:
    data = {name: json.loads((root / INPUT / name).read_bytes()) for name in FILES}
    inventory = data[FILES[0]]
    if inventory.get("source_commit") != CUT:
        raise ValueError("inventory source cut mismatch")
    for name in FILES[1:4]:
        finding = data[name]
        if finding.get("authority") != "SECONDARY_AI" or (finding.get("as_of") or finding.get("accessed_on")) != "2026-09-13":
            raise ValueError("findings authority/date mismatch")
    integrated = data[FILES[4]]
    if integrated.get("authority") != "SECONDARY_AI" or integrated.get("as_of") != "2026-09-13" or integrated.get("source_commit") != CUT:
        raise ValueError("integrated assessment authority/date/source mismatch")
    capabilities, requirements = inventory["existing_capabilities"], inventory["requirements"]
    sources: list[tuple[str, dict[str, Any]]] = []
    candidates: list[tuple[str, dict[str, Any]]] = []
    for name in FILES[1:4]:
        sources.extend((name, row) for row in data[name]["sources"])
        candidates.extend((name, row) for row in data[name]["candidates"])
        if len({row["id"] for row in data[name]["sources"]}) != len(data[name]["sources"]):
            raise ValueError("duplicate scoped source ID")
    assessments = data[FILES[4]]["assessments"]
    cap_index = {row["id"]: i for i, row in enumerate(capabilities)}; req_index = {row["id"]: i for i, row in enumerate(requirements)}
    source_index = {(name, row["id"]): i for name in FILES[1:4] for i, row in enumerate(data[name]["sources"])}
    candidate_index = {(name, row["id"]): i for name in FILES[1:4] for i, row in enumerate(data[name]["candidates"])}
    assessment_index = {row["candidate_id"]: i for i, row in enumerate(assessments)}
    candidate_keys = {(name, row["id"]) for name, row in candidates}
    by_id = {row["id"]: (name, row) for name, row in candidates}
    if len(by_id) != len(candidates) or {a["candidate_id"] for a in assessments} != set(by_id) or len(assessments) != len(by_id):
        raise ValueError("assessment must occur exactly once per candidate")
    cap_ids, req_ids = {r["id"] for r in capabilities}, {r["id"] for r in requirements}
    if len(cap_ids) != len(capabilities) or len(req_ids) != len(requirements):
        raise ValueError("duplicate capability or requirement identity")
    for req in requirements:
        if not set(req["existing_capability_ids"]) <= cap_ids:
            raise ValueError("requirement refers to missing capability")
    for assessment in assessments:
        if not set(assessment["requirement_ids"]) <= req_ids or not set(assessment["existing_capability_ids"]) <= cap_ids:
            raise ValueError("assessment has dangling requirement or capability")
        if assessment["decision"] in {"ADOPTED", "CURRENT", "IMPLEMENTED"}:
            raise ValueError("draft analysis cannot be promoted as adoption decision")
        if assessment["qualification"]["status"] != "PROPOSED_NOT_EXECUTED":
            raise ValueError("tooling research cannot mark qualification executed")
        candidate = by_id[assessment["candidate_id"]][1]
        if candidate.get("release_lane") == "EXPERIMENTAL" and assessment["decision"] != "WATCH_EXPERIMENTAL":
            raise ValueError("experimental specification must remain in experimental lane")
    source_ids_by_file = {name: {row["id"] for file, row in sources if file == name} for name in FILES[1:4]}
    for filename, candidate in candidates:
        if not candidate["source_ids"] or not set(candidate["source_ids"]) <= source_ids_by_file[filename]:
            raise ValueError("candidate refers to missing official source")
        if not set(candidate.get("version_source_ids", [])) <= set(candidate["source_ids"]):
            raise ValueError("candidate version source is not a candidate source")
    for cap in capabilities:
        for evidence in cap.get("evidence", []):
            actual = sha256(blob(evidence["path"].split("#", 1)[0], root)).hexdigest()
            if actual != evidence["sha256"]:
                raise ValueError("inventory evidence hash differs from fixed Git source")

    nodes: list[dict] = []; relations: dict[tuple[str, str, str], dict] = {}; anchors: dict[str, dict] = {}
    def node(value: str, name: str, role: str, **props: Any) -> None:
        required = {"name": name, "description": name, "standard_graph_role": role, "authority_class": "SECONDARY_AI", "ontology_authority_class_v1": "SECONDARY_AI", "responsibility_owner": OWNER, "status": "SOURCE_BOUND_RESEARCH_TOOLING", "claim_boundary": NONCLAIM, "projection_nonclaim": NONCLAIM, "ontology_sensitivity_v1": "NORMAL", "ontology_record_lifecycle_v1": "ACTIVE", "ontology_epistemic_state_v1": "PENDING", "ontology_review_required_v1": True, "ontology_canonical_scope_v1": "AI_ANALYSIS_NOT_USER_RATIFIED", "ontology_domain_v1": "AI", "ontology_kind_v1": "CONCEPT", "ontology_plane_v1": "RESEARCH_PROJECTION", "ontology_semantic_roles_v1": [role], "curation_source_path": str(INPUT), "curation_source_pointer": "/", **props}
        nodes.append({"uid": value, "labels": ["Concept", "AbstractNode"], "properties": required})
    def edge(a: str, typ: str, b: str, scope: str = "SOURCE_BOUND_RESEARCH_TOOLING") -> None:
        relations[(a, typ, b)] = {"from_uid": a, "type": typ, "to_uid": b, "authority_class": "SECONDARY_AI", "scope": scope, "status": "PROJECTION_ONLY"}
    def anchor(value: str, name: str, labels: list[str]) -> None:
        anchors[value] = {"uid": value, "name": name, "required_labels": labels}

    anchor("sym:Concept:hswm", "HSWM", ["Concept"]); anchor(DISCOVERY, "HSWM 전체 지식 지도 — 문서·표준 그래프 질의 진입점", ["Concept", "AbstractNode"])
    node(UID, "HSWM 과학 연구 도구·최신 표준 — 근거·요구사항·검증 과제", "RESEARCH_TOOLING_ROOT", source_commit=CUT, curation_source_path=str(INPUT / FILES[4]), curation_source_pointer="/conceptual_delta")
    edge(UID, "REFERS_TO", "sym:Concept:hswm"); edge(UID, "REFERS_TO", DISCOVERY)
    descriptor_nodes = {}
    for cap in capabilities:
        for evidence_i, evidence in enumerate(cap.get("evidence", [])):
            path = evidence["path"].split("#", 1)[0]
            if path not in descriptor_nodes:
                value = uid("fixed-git-source", "fixed", path); raw = blob(path, root); descriptor_nodes[path] = value
                node(value, "Fixed Git source: " + path, "FIXED_GIT_SOURCE_DESCRIPTOR", source_path=path, source_commit=CUT, source_sha256=sha256(raw).hexdigest(), source_byte_length=len(raw), curation_source_path=str(INPUT / FILES[0]), curation_source_pointer=f"/existing_capabilities/{cap_index[cap['id']]}/evidence/{evidence_i}")
                edge(UID, "HAS_SOURCE", value)
    for req in requirements:
        for reference in req.get("source_paths", []):
            path = reference.split("#", 1)[0]
            if path not in descriptor_nodes:
                value = uid("fixed-git-source", "fixed", path); raw = blob(path, root); descriptor_nodes[path] = value
                node(value, "Fixed Git source: " + path, "FIXED_GIT_SOURCE_DESCRIPTOR", source_path=path, source_commit=CUT, source_sha256=sha256(raw).hexdigest(), source_byte_length=len(raw), curation_source_path=str(INPUT / FILES[0]), curation_source_pointer=f"/requirements/{req_index[req['id']]}/source_paths")
                edge(UID, "HAS_SOURCE", value)
    for filename, row in sources:
        path = local_path(row["url"])
        if path and path not in descriptor_nodes:
            value = uid("fixed-git-source", "fixed", path); raw = blob(path, root); descriptor_nodes[path] = value
            node(value, "Fixed Git source: " + path, "FIXED_GIT_SOURCE_DESCRIPTOR", source_path=path, source_commit=CUT, source_sha256=sha256(raw).hexdigest(), source_byte_length=len(raw), curation_source_path=str(INPUT / filename), curation_source_pointer=f"/sources/{source_index[(filename, row['id'])]}")
            edge(UID, "HAS_SOURCE", value)
    cap_nodes = {}
    for row in capabilities:
        value = uid("capability", FILES[0], row["id"]); cap_nodes[row["id"]] = value; node(value, row["capability"], "EXISTING_CAPABILITY", source_id=row["id"], **safe_props(row), curation_source_path=str(INPUT / FILES[0]), curation_source_pointer=f"/existing_capabilities/{cap_index[row['id']]}"); edge(UID, "HAS_CONCEPT", value)
        for evidence_i, evidence in enumerate(row.get("evidence", [])):
            path = evidence["path"].split("#", 1)[0]; eid = uid("capability-evidence", FILES[0], row["id"] + ":" + evidence["path"])
            node(eid, "Evidence: " + row["id"], "CAPABILITY_EVIDENCE", **safe_props(evidence), curation_source_path=str(INPUT / FILES[0]), curation_source_pointer=f"/existing_capabilities/{cap_index[row['id']]}/evidence/{evidence_i}")
            edge(value, "HAS_SOURCE", eid); edge(eid, "HAS_SOURCE", descriptor_nodes[path])
    req_nodes = {}
    for row in requirements:
        value = uid("requirement", FILES[0], row["id"]); req_nodes[row["id"]] = value; node(value, row["need"], "RESEARCH_REQUIREMENT", source_id=row["id"], **safe_props(row), curation_source_path=str(INPUT / FILES[0]), curation_source_pointer=f"/requirements/{req_index[row['id']]}"); edge(UID, "HAS_CONCEPT", value)
        for cap in row["existing_capability_ids"]: edge(value, "REQUIRES", cap_nodes[cap])
        for reference in row.get("source_paths", []): edge(value, "HAS_SOURCE", descriptor_nodes[reference.split("#", 1)[0]])
    source_nodes = {}; candidate_nodes = {}
    for filename, row in sources:
        path = local_path(row["url"]); scope = "LOCAL_FIXED_GIT" if path else "EXTERNAL_WEB_OBSERVATION_ONLY"
        value = uid("research-source", filename, row["id"]); source_nodes[(filename, row["id"])] = value; node(value, row["title"], "RESEARCH_SOURCE", source_file=filename, source_id=row["id"], source_scope=scope, source_cut=CUT if path else "NOT_ARCHIVED_REMOTE_WEBPAGE", **safe_props(row), curation_source_path=str(INPUT / filename), curation_source_pointer=f"/sources/{source_index[(filename, row['id'])]}"); edge(UID, "HAS_SOURCE", value)
        if path: edge(value, "HAS_SOURCE", descriptor_nodes[path])
    for filename, row in candidates:
        value = uid("candidate", filename, row["id"]); candidate_nodes[row["id"]] = value; node(value, row["name"], "TOOL_CANDIDATE", source_file=filename, source_id=row["id"], **safe_props(row), curation_source_path=str(INPUT / filename), curation_source_pointer=f"/candidates/{candidate_index[(filename, row['id'])]}"); edge(UID, "HAS_CONCEPT", value)
        for sid in row["source_ids"]: edge(value, "HAS_SOURCE", source_nodes[(filename, sid)])
        evidence = uid("adoption-evidence", filename, row["id"]); node(evidence, "Adoption evidence: " + row["name"], "ADOPTION_EVIDENCE", statement=row["adoption_evidence"], evidence_class=next(a["adoption_evidence_class"] for a in assessments if a["candidate_id"] == row["id"]), candidate_id=row["id"], curation_source_path=str(INPUT / filename), curation_source_pointer=f"/candidates/{candidate_index[(filename, row['id'])]}" + "/adoption_evidence"); edge(value, "HAS_CONCEPT", evidence)
        for sid in row["source_ids"]: edge(evidence, "HAS_SOURCE", source_nodes[(filename, sid)])
    for row in assessments:
        candidate = candidate_nodes[row["candidate_id"]]; value = uid("assessment", FILES[4], row["candidate_id"]); node(value, "Assessment: " + row["candidate_id"], "INTEGRATED_ASSESSMENT", **safe_props(row), curation_source_path=str(INPUT / FILES[4]), curation_source_pointer=f"/assessments/{assessment_index[row['candidate_id']]}"); edge(UID, "HAS_CONCEPT", value); edge(value, "REFERS_TO", candidate)
        for rid in row["requirement_ids"]: edge(value, "REQUIRES", req_nodes[rid])
        for cid in row["existing_capability_ids"]: edge(value, "PRESERVES", cap_nodes[cid])
        q = row["qualification"]; qid = uid("qualification", FILES[4], q["id"]); node(qid, q["title"], "QUALIFICATION", **safe_props(q), curation_source_path=str(INPUT / FILES[4]), curation_source_pointer=f"/assessments/{assessment_index[row['candidate_id']]}" + "/qualification"); edge(value, "HAS_CONCEPT", qid)
    validate_curation_pointers(nodes, root)
    if len({n["uid"] for n in nodes}) != len(nodes): raise ValueError("duplicate projected identity")
    inputs = [{"path": str(INPUT / name), "sha256": sha256((root / INPUT / name).read_bytes()).hexdigest()} for name in FILES]
    support = [Path(__file__).relative_to(ROOT), Path("src/hswm/infrastructure/kg_bundle_graph_view.py"), Path("schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl"), *sorted(p.relative_to(root) for p in (root / QUERIES).iterdir())]
    source_records = []
    for filename, row in sorted(sources, key=lambda item: (item[0], item[1]["id"])):
        path = local_path(row["url"])
        source_records.append({"source_file": filename, "source_id": row["id"], "title": row["title"], "url": row["url"], "organization": row.get("organization"), "accessed_on": row.get("accessed_on"), "source_date": row.get("source_date"), "kind": row.get("kind"), "finding": row.get("finding"), "source_scope": "LOCAL_FIXED_GIT" if path else "EXTERNAL_WEB_OBSERVATION_ONLY", "source_cut": CUT if path else "NOT_ARCHIVED_REMOTE_WEBPAGE", "fixed_git_descriptor_uid": descriptor_nodes.get(path) if path else None})
    fixed_records = [{"source_path": path, "source_commit": CUT, "sha256": sha256(blob(path, root)).hexdigest(), "descriptor_uid": value} for path, value in sorted(descriptor_nodes.items())]
    catalog = {"schema_version": "hswm-research-tooling-source-catalog/v1", "source_commit": CUT, "inputs": inputs + [{"path": str(p), "sha256": sha256((root / p).read_bytes()).hexdigest()} for p in support], "candidate_count": len(candidates), "assessment_count": len(assessments), "research_sources": source_records, "fixed_git_source_descriptors": fixed_records, "research_source_counts": {"external_web_observation_only": sum(local_path(row["url"]) is None for _, row in sources), "local_fixed_git": sum(local_path(row["url"]) is not None for _, row in sources)}, "observation_boundary": "Remote web pages are recorded as dated observations in findings inputs; their page bytes are not archived or content-hashed by this projection."}
    bundle = {"schema_version": "hswm-scientific-research-tooling/v1", "bundle_uid": UID, "status": "SOURCE_BOUND_RESEARCH_TOOLING_NOT_EFFICACY", "nonclaim": NONCLAIM, "authority_boundary": "SECONDARY_AI source-bound research tooling curation; not an adoption, efficacy, or HSWM cognition claim.", "source_accessed_on": "2026-09-13", "artifact_bindings": [{"path": str(ARTIFACTS / "source-catalog.json"), "sha256": sha256(encode(catalog)).hexdigest()}, {"path": "ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_DISCOVERY_2026-09-13.v1.json", "sha256": "f97838782144ba09d290a2e4ce9fc71868fbff0bee8e8aab6bfba9f81eecb589"}], "expected_counts": {"nodes": len(nodes), "anchors": len(anchors), "relations": len(relations)}, "anchors": [anchors[k] for k in sorted(anchors)], "nodes": sorted(nodes, key=lambda x: x["uid"]), "relations": [relations[k] for k in sorted(relations)]}
    return catalog, bundle


def build(*, check: bool = False, root: Path = ROOT) -> dict:
    catalog, bundle = compile_snapshot(root); raw = encode(bundle)
    view = KgBundleGraphView.from_bundles(sources=(KgBundleSource("hswm-research-tooling-2026-09-13", raw, sha256(raw).hexdigest(), len(raw)),), profile="v2")
    shacl = dict(view.validate_shacl(shapes=(root / "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl").read_bytes()))
    if not shacl["conforms"]: raise ValueError(shacl["report_text"])
    query_files = list((root / QUERIES).iterdir())
    stems = {p.stem for p in query_files if p.suffix == ".sparql"}
    if len(stems) != 6 or {p.stem for p in query_files if p.suffix == ".cypher"} != stems: raise ValueError("paired query inventory mismatch")
    results = {p.name: plain(view.query(p.read_text())) for p in sorted((root / QUERIES).glob("*.sparql"))}
    candidate_ids = {n["properties"]["id"] for n in bundle["nodes"] if n["properties"]["standard_graph_role"] == "TOOL_CANDIDATE"}
    experimental_ids = {n["properties"]["candidate_id"] for n in bundle["nodes"] if n["properties"].get("decision") == "WATCH_EXPERIMENTAL"}
    for query, expected in (("Q1_candidate_decisions_and_priority.sparql", candidate_ids), ("Q3_experimental_development_specs.sparql", experimental_ids)):
        rows = results[query]
        if len(rows) != len(expected) or {r["candidateId"]["value"] for r in rows} != expected:
            raise ValueError("query candidate coverage differs from declared input")
    if results["Q6_missing_source_assessment_orphan_refs.sparql"]: raise ValueError("query found missing source or orphan reference")
    validation = {"schema_version": "hswm-research-tooling-validation/v1", "source_commit": CUT, "bundle_sha256": sha256(raw).hexdigest(), "counts": bundle["expected_counts"], "shacl": shacl, "query_row_counts": {k: len(v) for k, v in results.items()}, "claim_boundary": NONCLAIM}
    index = ["# HSWM research-tooling source appendix — 2026-09-13", "", f"Fixed Git source cut: `{CUT}`. Remote webpages below are dated input observations; this projection does not archive or hash their page bytes.", "", "| Scoped ID | Title | URL | Organization | Date | Kind | Source scope | Finding |", "|---|---|---|---|---|---|---|---|"]
    for row in catalog["research_sources"]:
        url = row["url"] if row["source_scope"] == "EXTERNAL_WEB_OBSERVATION_ONLY" else f"https://github.com/gj3447/HSWM/blob/{CUT}/{local_path(row['url'])}"
        compact = lambda v: str(v or "").replace("|", "\\|").replace("\n", " ")
        index.append("| " + compact(row["source_file"] + ":" + row["source_id"]) + " | " + compact(row["title"]) + f" | [{compact(row['url'])}]({url}) | " + " | ".join(compact(row[k]) for k in ("organization", "source_date", "kind", "source_scope", "finding")) + " |")
    artifacts = {BUNDLE: raw, ARTIFACTS / "source-catalog.json": encode(catalog), ARTIFACTS / "research-tooling.nq": view.nquads, ARTIFACTS / "descriptor.json": encode(plain(view.descriptor)), ARTIFACTS / "provenance.jsonld": view.prov_o_envelope(), ARTIFACTS / "query-results.json": encode(results), ARTIFACTS / "validation.json": encode(validation), ARTIFACTS / "source-index.md": ("\n".join(index) + "\n").encode()}
    for path, content in artifacts.items():
        target = root / path
        if check:
            if not target.is_file() or target.read_bytes() != content: raise ValueError(f"derived artifact drift: {path}")
        else: target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true")
    print(json.dumps(build(check=parser.parse_args().check), ensure_ascii=False, sort_keys=True))
