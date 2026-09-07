"""Reproduce bounded ontology-projection counterexamples without graph writes.

Run from the repository root with the locked graph runtime. JSON on stdout is
an engineering audit, not scientific evidence or permission to publish mutants.
All mutations are made in memory. No CLI --apply or database client is invoked.
"""

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import subprocess

from hswm.infrastructure import fractal_learning_plan_projection as plan_adapter
from hswm.infrastructure.kg_bundle_graph_view import KgBundleGraphView, KgBundleSource


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / plan_adapter.DEFAULT_ARTIFACT
WORKSHOP = ROOT / "ontology/identity/hswm_core/HSWM_WORKSHOP_C1_C3_ONTOLOGY.v1.json"
GENERIC = ROOT / "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0.ttl"
DOMAIN = ROOT / "schemas/HSWM_HYPERGRAPH_LEARNING_PLAN_SHACL_1_0.ttl"
PREFIX = """
PREFIX kb: <https://hswm.invalid/kg-bundle-rdf/v1/>
PREFIX kbp: <https://hswm.invalid/kg-bundle-rdf/v1/prop/>
PREFIX kbr: <https://hswm.invalid/kg-bundle-rdf/v1/rel/>
PREFIX kbrole: <https://hswm.invalid/kg-bundle-rdf/v1/role/>
"""


def source(data, name):
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return KgBundleSource(name, raw, sha256(raw).hexdigest(), len(raw))


def evaluate(case_id, data, *, plan=False, checks=None):
    item = {"case_id": case_id, "role_counts": dict(sorted(Counter(
        n["properties"].get("standard_graph_role", "ABSENT") for n in data["nodes"]
    ).items()))}
    bound = source(data, case_id)
    view = KgBundleGraphView.from_bundles(sources=(bound,))
    item["mutant_bundle_sha256"] = bound.sha256
    generic = view.validate_shacl(shapes=GENERIC.read_bytes())
    item["generic_shacl_conforms"] = generic["conforms"]
    if not generic["conforms"]:
        item["generic_validation_report"] = generic["report_text"]
    if plan:
        item["generic_plus_domain_shacl_conforms"] = view.validate_shacl(
            shapes=GENERIC.read_bytes() + b"\n" + DOMAIN.read_bytes()
        )["conforms"]
        try:
            plan_adapter.validate_data(data, ROOT)
        except ValueError as exc:
            item["plan_adapter_validation"] = {"accepted": False, "error": str(exc)}
        else:
            item["plan_adapter_validation"] = {"accepted": True}
        # Compare with the exact --apply pin, without invoking --apply.
        item["exact_publication_pin_matches"] = bound.sha256 == plan_adapter.REVIEWED_ARTIFACT_SHA256
    if checks:
        item["semantic_queries"] = {key: view.query(PREFIX + query) for key, query in checks.items()}
    return item


def cross_bundle_anchor():
    def bundle(name, node_uid, anchors):
        return {
            "schema_version": "hswm-adversarial-fixture/v1",
            "bundle_uid": "sym:AbstractNode:audit-" + name,
            "status": "TEST_ONLY", "nonclaim": "TEST_ONLY",
            "artifact_bindings": [{"path": "docs/declared-fixture.md", "sha256": "0" * 64}],
            "expected_counts": {"nodes": 1, "anchors": len(anchors), "relations": 0},
            "anchors": anchors,
            "nodes": [{"uid": node_uid, "labels": ["Concept"], "properties": {
                "name": "fixture", "description": "in-memory fixture",
                "authority_class": "SECONDARY_AI", "claim_boundary": "TEST_ONLY",
                "projection_nonclaim": "TEST_ONLY",
            }}],
            "relations": [],
        }
    uid = "sym:Concept:audit-shared"
    owner = bundle("owner", uid, [])
    dependent = bundle("dependent", "sym:Concept:audit-dependent", [
        {"uid": uid, "name": "fixture", "required_labels": ["Concept", "Guardrail"]}
    ])
    view = KgBundleGraphView.from_bundles(sources=(source(owner, "owner"), source(dependent, "dependent")))
    return {
        "case_id": "cross_bundle_anchor_requirement_lost",
        "owner_labels": ["Concept"], "dependent_required_labels": ["Concept", "Guardrail"],
        "construction_accepted": True,
        "generic_shacl_conforms": view.validate_shacl(shapes=GENERIC.read_bytes())["conforms"],
        "required_guardrail_retained": view.query(PREFIX + """ASK {
          ?n kb:uid "sym:Concept:audit-shared" ; kb:requiredLabel "Guardrail" .
        }"""),
        "owner_has_guardrail": view.query(PREFIX + """ASK {
          ?n kb:uid "sym:Concept:audit-shared" ; kb:label "Guardrail" .
        }"""),
    }


def main():
    plan = json.loads(PLAN.read_bytes())
    workshop = json.loads(WORKSHOP.read_bytes())
    cases = [evaluate("plan_baseline", plan, plan=True), evaluate("workshop_baseline", workshop)]

    mutant = deepcopy(plan)
    relation = next(r for r in mutant["relations"] if r["type"] == "TARGET")
    mutant["relations"].remove(relation)
    mutant["expected_counts"]["relations"] -= 1
    cases.append(evaluate("control_missing_participation_target", mutant, plan=True))

    mutant = deepcopy(plan)
    for node in mutant["nodes"]:
        props = node["properties"]
        if props.get("standard_graph_role") in {"LEARNING_ASSERTION", "ROLE_PARTICIPATION"}:
            props["standard_graph_role"] = "UNCLASSIFIED"
    mutant["relations"] = [r for r in mutant["relations"] if r["type"] not in {"TARGET", "HAS_PARTICIPATION"}]
    mutant["expected_counts"]["relations"] = len(mutant["relations"])
    cases.append(evaluate("domain_target_evasion", mutant, plan=True))

    mutant = deepcopy(plan)
    parts = [n for n in mutant["nodes"] if n["properties"].get("standard_graph_role") == "ROLE_PARTICIPATION"]
    parts[1]["properties"]["ordinal"] = parts[0]["properties"]["ordinal"]
    cases.append(evaluate("duplicate_role_ordinal", mutant, plan=True, checks={
        "no_duplicate_ordinal_per_assertion": """ASK { FILTER NOT EXISTS {
          ?a kbr:HAS_PARTICIPATION ?p, ?q .
          ?p kbp:ordinal ?o . ?q kbp:ordinal ?o . FILTER (?p != ?q)
        } }"""
    }))

    mutant = deepcopy(plan)
    props = next(n["properties"] for n in mutant["nodes"]
                 if n["properties"].get("standard_graph_role") == "LEARNING_ASSERTION")
    props["ontology_authority_class_v1"] = "USER_PRIMARY"
    cases.append(evaluate("conflicting_discovery_authority", mutant, plan=True, checks={
        "raw_and_mapped_authority_agree": """ASK { FILTER NOT EXISTS {
          ?n kbp:authority_class ?a ; kbp:ontology_authority_class_v1 ?b . FILTER (?a != ?b)
        } }"""
    }))

    mutant = deepcopy(plan)
    mutant["artifact_bindings"][0]["sha256"] = "0" * 64
    cases.append(evaluate("control_declared_binding_without_matching_bytes", mutant, plan=True))

    mutant = deepcopy(plan)
    binding = dict(mutant["artifact_bindings"][0])
    binding["path"] = "docs/audit-alias-not-a-real-source.md"
    mutant["artifact_bindings"].append(binding)
    cases.append(evaluate("two_paths_for_one_content_digest", mutant, plan=True))

    mutant = deepcopy(workshop)
    props = next(n["properties"] for n in mutant["nodes"]
                 if n["properties"].get("standard_graph_role") == "AUTHORED_SCENE")
    props["status"] = "OBSERVED_SUCCESS"
    cases.append(evaluate("authored_scene_claims_observation", mutant, checks={
        "authored_scene_is_not_observed_success": """ASK { FILTER NOT EXISTS {
          ?n a kbrole:AUTHORED_SCENE ; kbp:status "OBSERVED_SUCCESS" .
        } }"""
    }))

    closure_path = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v5.json"
    closure = json.loads(closure_path.read_bytes())
    cases.append(evaluate("closure_baseline", closure))
    mutant = deepcopy(closure)
    props = next(n["properties"] for n in mutant["nodes"]
                 if n["properties"].get("standard_graph_role") == "CLAIM")
    props["current_decision_uid"] = "sym:Concept:audit-nonexistent-decision"
    cases.append(evaluate("claim_points_to_missing_current_decision", mutant, checks={
        "current_decision_pointer_matches_linked_decision": """ASK { FILTER NOT EXISTS {
          ?c a kbrole:CLAIM ; kb:uid ?claimUid ; kbp:current_decision_uid ?decisionUid .
          FILTER NOT EXISTS {
            ?c kbr:HAS_CONCEPT ?d .
            ?d a kbrole:DECISION ; kb:uid ?decisionUid ; kbp:assesses_claim_uid ?claimUid .
          }
        } }"""
    }))

    inputs = [PLAN, WORKSHOP, closure_path, GENERIC, DOMAIN,
              ROOT / "src/hswm/infrastructure/kg_bundle_graph_view.py",
              ROOT / "src/hswm/infrastructure/fractal_learning_plan_projection.py",
              ROOT / "_research/graph_standards/runtime/uv.lock", Path(__file__)]
    result = {
        "schema_version": "hswm-philosophy-projection-adversarial-audit/v1",
        "authority_class": "SECONDARY_AI",
        "audit_kind": "ENGINEERING_COUNTEREXAMPLES_NOT_SCIENTIFIC_RESULT",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "scope": {"live_graph_writes": 0, "runtime_implementation_changes": 0,
                  "scientific_gate_changes": 0, "publication_attempts": 0},
        "runtime": {name: version(name) for name in ("rdflib", "pyshacl")},
        "sources": [{"path": str(p.relative_to(ROOT)), "sha256": sha256(p.read_bytes()).hexdigest()} for p in inputs],
        "original_plan_publication_pin_matches": sha256(PLAN.read_bytes()).hexdigest() == plan_adapter.REVIEWED_ARTIFACT_SHA256,
        "interpretation": [
            "All mutants are in-memory copies and are never published.",
            "Shape conformance concerns declared targets and constraints, not empirical truth.",
            "Reserialized baseline also differs from the raw-byte publication pin; byte inequality alone is not a semantic classifier.",
            "Ordinal is role enumeration, not time. Duplicate ordinals demonstrate missing discrimination, not observed causal-order corruption.",
            "The actual plan CLI rejects changed bytes on --apply via its reviewed SHA pin.",
            "Generic declared artifact provenance is not file verification; the plan adapter independently rehashes bindings.",
        ],
        "cases": cases + [cross_bundle_anchor()],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
