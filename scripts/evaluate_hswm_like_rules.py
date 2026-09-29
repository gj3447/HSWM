"""Validate the local HSWM-like ontology and score submitted rule assessments.

This offline tool reuses the existing RDF/SHACL projection. It neither evaluates
the truth of submitted evidence nor changes canonical state or live KG records.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

from hswm.infrastructure.kg_bundle_graph_view import KgBundleGraphView, KgBundleSource

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "ontology/identity/hswm_core"
BUNDLE = DIRECTORY / "HSWM_LIKE_RULE_ACTIVATION_ONTOLOGY.v1.json"
RUBRIC = DIRECTORY / "HSWM_LIKE_RULE_SCORE.v1.json"
SHAPES = ROOT / "schemas/HSWM_LIKE_RULE_ACTIVATION_SHACL_1_0.ttl"
PREFIX = """
PREFIX kb: <https://hswm.invalid/kg-bundle-rdf/v1/>
PREFIX role: <https://hswm.invalid/kg-bundle-rdf/v1/role/>
PREFIX rel: <https://hswm.invalid/kg-bundle-rdf/v1/rel/>
PREFIX prop: <https://hswm.invalid/kg-bundle-rdf/v1/prop/>
"""
PARTICIPANTS = PREFIX + """
SELECT ?relation_uid ?role ?ordinal ?target_name {
  ?r a role:HYPER_RELATION ; kb:uid ?relation_uid ; rel:HAS_PARTICIPATION ?p .
  ?p prop:role_name ?role ; prop:ordinal ?ordinal ; rel:TARGET ?t .
  ?t prop:name ?target_name .
} ORDER BY ?ordinal
"""
SOURCES = PREFIX + """
SELECT ?map_uid ?source_uid ?digest ?loss {
  ?m a role:MAP_VIEW ; kb:uid ?map_uid ; prop:loss_declaration ?loss ; rel:HAS_BINDING ?b .
  ?b rel:BINDS_SOURCE ?s .
  ?s kb:uid ?source_uid ; prop:source_sha256 ?digest .
}
"""


def read_json(path: Path) -> dict:
    def reject(value: str) -> None:
        raise ValueError(f"Non-finite JSON value: {value}")

    def unique(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(), parse_constant=reject, object_pairs_hook=unique)


def evidence(value: object) -> bool:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError("Evidence must be a list of non-empty references")
    return bool(value)


def score(assessment: dict, rubric: dict) -> dict:
    if assessment.get("profile") != rubric["profile"]:
        raise ValueError("Assessment profile does not match rubric")
    for key in ("subject_uid", "subject_revision", "workload", "evaluator", "assessment_kind"):
        if not isinstance(assessment.get(key), str) or not assessment[key].strip():
            raise ValueError(f"Missing assessment context: {key}")
    axis_ids = {row["id"] for row in rubric["axes"]}
    if set(assessment.get("axes", {})) != axis_ids:
        raise ValueError("Assessment must contain exactly the rubric axes")
    if set(assessment.get("invariants", {})) != set(rubric["invariants"]):
        raise ValueError("Assessment must contain exactly the rubric invariants")
    ratings = {}
    for key, row in assessment["axes"].items():
        if set(row) != {"rating", "evidence"}:
            raise ValueError(f"Invalid rating shape: {key}")
        value = row["rating"]
        has_evidence = evidence(row["evidence"])
        if value is not None and (type(value) is not int or not 0 <= value <= 4):
            raise ValueError(f"Rating outside integer 0..4 or null: {key}")
        if value is not None and not has_evidence:
            raise ValueError(f"Known rating requires evidence: {key}")
        ratings[key] = value
    verdicts = []
    for key, row in assessment["invariants"].items():
        if set(row) != {"holds", "evidence"}:
            raise ValueError(f"Invalid invariant shape: {key}")
        value = row["holds"]
        has_evidence = evidence(row["evidence"])
        if value is not None and type(value) is not bool:
            raise ValueError(f"Invariant must be bool or null: {key}")
        if value is not None and not has_evidence:
            raise ValueError(f"Known invariant requires evidence: {key}")
        verdicts.append(value)
    status = "SCORED_AS_SUBMITTED"
    if any(value is False for value in verdicts):
        status = "INVALID"
    elif None in ratings.values() or None in verdicts or assessment["assessment_kind"] == "TEMPLATE_NOT_MEASURED":
        status = "INCOMPLETE"
    total = None
    if status == "SCORED_AS_SUBMITTED":
        weights = [row["weight"] for row in rubric["axes"]]
        if any(type(w) is not int or w <= 0 for w in weights):
            raise ValueError("Rubric weights must be positive integers")
        total = 100 * sum(row["weight"] * ratings[row["id"]] for row in rubric["axes"]) / (4 * sum(weights))
    return {
        "profile": rubric["profile"], "subject_uid": assessment["subject_uid"],
        "subject_revision": assessment["subject_revision"], "workload": assessment["workload"],
        "assessment_kind": assessment["assessment_kind"], "status": status,
        "ratings": ratings, "assessed_axes": sum(v is not None for v in ratings.values()),
        "score_0_100": total, "evidence_truth_verified": False,
        "claim_boundary": "SUBMITTED_JUDGMENTS_NOT_AUTOMATIC_HSWM_EFFICACY_OR_RATIFICATION",
    }


def validate_bundle(data: dict, repo_root: Path = ROOT) -> KgBundleGraphView:
    raw = json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True).encode()
    view = KgBundleGraphView.from_bundles(sources=(KgBundleSource("hswm-like-rules", raw, sha256(raw).hexdigest(), len(raw)),))
    if data["schema_version"] != "hswm-like-rule-activation/v1":
        raise ValueError("Wrong ontology profile")
    bound = {}
    for binding in data["artifact_bindings"]:
        path = (repo_root / binding["path"]).resolve()
        if not path.is_relative_to(repo_root.resolve()):
            raise ValueError("Source path escapes repository")
        content = path.read_bytes()
        if sha256(content).hexdigest() != binding["sha256"]:
            raise ValueError(f"Source hash drift: {binding['path']}")
        bound[binding["path"]] = content
    nodes = {n["uid"]: n["properties"] for n in data["nodes"]}
    roles = {uid: p["standard_graph_role"] for uid, p in nodes.items()}
    roles.update({a["uid"]: "ANCHOR" for a in data["anchors"]})
    primary = []
    for uid, props in nodes.items():
        path = props["source_path"]
        if path not in bound or sha256(bound[path]).hexdigest() != props["source_sha256"]:
            raise ValueError(f"Node source is not bound: {uid}")
        if props["authority_class"] == "USER_PRIMARY":
            primary.append(uid)
            if roles[uid] != "SOURCE_ARTIFACT" or props.get("exact_user_text") != bound[path].decode().removesuffix("\n"):
                raise ValueError("USER_PRIMARY must preserve the exact source text")
        elif props["authority_class"] != "SECONDARY_AI":
            raise ValueError("Unsupported interpretation authority")
    if len(primary) != 1:
        raise ValueError("This source-bound profile requires exactly one user source")
    definitions = [p for p in nodes.values() if p["standard_graph_role"] == "PREDICATE_DEFINITION"]
    specs = {p["predicate_name"]: p for p in definitions}
    if len(specs) != len(definitions):
        raise ValueError("Duplicate predicate definition")
    outgoing = Counter()
    adjacency = defaultdict(set)
    incoming_parts = Counter()
    for relation in data["relations"]:
        a, name, b = (relation[k] for k in ("from_uid", "type", "to_uid"))
        if name not in specs:
            raise ValueError(f"Undeclared predicate: {name}")
        spec = specs[name]
        if roles[a] not in spec["domain_roles"] or roles[b] not in spec["range_roles"]:
            raise ValueError(f"Predicate domain/range violation: {name}")
        if relation["authority_class"] != "SECONDARY_AI" or relation["status"] != "PROPOSED":
            raise ValueError("Interpretive relationships must remain proposed")
        outgoing[a, name] += 1
        adjacency[a].add(b)
        if name == "HAS_PARTICIPATION":
            incoming_parts[b] += 1
    for uid, role in roles.items():
        for name, spec in specs.items():
            if role in spec["domain_roles"]:
                count = outgoing[uid, name]
                if count < spec["outgoing_min"] or (spec["outgoing_max"] >= 0 and count > spec["outgoing_max"]):
                    raise ValueError(f"Predicate cardinality violation: {uid} {name}")
        if role == "ROLE_PARTICIPATION" and incoming_parts[uid] != 1:
            raise ValueError("Participation must belong to exactly one relation")
    seen, pending = set(), [data["bundle_uid"]]
    while pending:
        uid = pending.pop()
        if uid not in seen:
            seen.add(uid)
            pending.extend(adjacency[uid])
    if seen != set(roles):
        raise ValueError("Unreachable profile node or anchor")
    shape_bytes = (repo_root / "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl").read_bytes() + b"\n" + SHAPES.read_bytes()
    checked = view.validate_shacl(shapes=shape_bytes)
    if not checked["conforms"]:
        raise ValueError(checked["report_text"])
    rows = view.query(PARTICIPANTS)
    observed = {(row["role"]["value"], int(row["ordinal"]["value"]), row["target_name"]["value"]) for row in rows}
    expected = {("task", 0, "deploy"), ("target_scope", 1, "service-a"), ("action", 2, "write"), ("exception", 3, "dry-run"), ("required_rule", 4, "release-rule original with all preconditions")}
    expected_relation = "sym:Concept:hswm-like-20260929-example-joint"
    if observed != expected or len(rows) != 5 or any(row["relation_uid"]["value"] != expected_relation for row in rows):
        raise ValueError("N-ary competency query lost relation, roles, order or targets")
    sources = view.query(SOURCES)
    if len(sources) != 1 or sources[0]["source_uid"]["value"] != primary[0] or sources[0]["digest"]["value"] != nodes[primary[0]]["source_sha256"] or not sources[0]["loss"]["value"]:
        raise ValueError("Map/source competency query lost source or declared loss")
    return view


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Verify bindings, graph contracts, SHACL and competency queries")
    validate.add_argument("--export-dir", type=Path, help="Optional local RDF/PROV export directory")
    assessment = commands.add_parser("score", help="Validate and aggregate submitted evidence ratings")
    assessment.add_argument("assessment", type=Path)
    args = parser.parse_args()
    if args.command == "score":
        print(json.dumps(score(read_json(args.assessment), read_json(RUBRIC)), ensure_ascii=False))
        return
    data = read_json(BUNDLE)
    view = validate_bundle(data)
    if args.export_dir:
        args.export_dir.mkdir(parents=True, exist_ok=True)
        (args.export_dir / "view.nq").write_bytes(view.nquads)
        (args.export_dir / "prov.jsonld").write_bytes(view.prov_o_envelope())
    print(json.dumps({"status": "VALIDATED_LOCAL_PROFILE", "counts": data["expected_counts"], "shacl_conforms": True, "competency_queries": ["nary-roles-and-targets", "map-to-exact-source"], "source_bindings_verified": True, "runtime_efficacy_measured": False}))


if __name__ == "__main__":
    main()
