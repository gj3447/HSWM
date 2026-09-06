from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from hswm.infrastructure.kg_bundle_graph_view import (
    CLAIM_CEILING,
    NONCLAIM,
    KgBundleGraphView,
    KgBundleGraphViewError,
    KgBundleSource,
)


ROOT = Path(__file__).parents[1]
SHAPES = ROOT / "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0.ttl"
CLOSURE = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v3.json"
CLOSURE_V2 = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v2.json"
CLOSURE_V1 = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v1.json"
ADAPTIVE = ROOT / "ontology/identity/hswm_core/HSWM_ADAPTIVE_RESEARCH_STRATEGY_ONTOLOGY.v1.json"
GRAPH_LOOP = ROOT / "ontology/identity/hswm_core/HSWM_GRAPH_AND_LOOP_ENGINEERING_ONTOLOGY.v6.json"
CAUSAL = ROOT / "ontology/identity/hswm_core/HSWM_CAUSAL_COMPOSITION_RESEARCH_ONTOLOGY.v1.json"
EFFECT_FP = ROOT / "ontology/identity/hswm_core/HSWM_EFFECT_RUNTIME_FP_BOUNDARY_ONTOLOGY.v1.json"
PREFIXES = """
PREFIX kb: <https://hswm.invalid/kg-bundle-rdf/v1/>
PREFIX kbp: <https://hswm.invalid/kg-bundle-rdf/v1/prop/>
PREFIX kbr: <https://hswm.invalid/kg-bundle-rdf/v1/rel/>
PREFIX kbrole: <https://hswm.invalid/kg-bundle-rdf/v1/role/>
PREFIX prov: <http://www.w3.org/ns/prov#>
"""


def _source(path: Path, source_id: str) -> KgBundleSource:
    raw = path.read_bytes()
    return KgBundleSource(source_id, raw, sha256(raw).hexdigest(), len(raw))


def _synthetic(mutate=None) -> bytes:
    bundle = {
        "schema_version": "hswm-test-bundle/v1",
        "bundle_uid": "sym:AbstractNode:test-bundle",
        "status": "TEST",
        "nonclaim": "TEST_ONLY",
        "artifact_bindings": [{"path": "docs/example.md", "sha256": "0" * 64}],
        "expected_counts": {"nodes": 3, "anchors": 1, "relations": 3},
        "anchors": [{"uid": "sym:Concept:hswm", "name": "HSWM", "required_labels": ["Concept"]}],
        "nodes": [
            {
                "uid": "sym:Concept:test-claim",
                "labels": ["Concept"],
                "properties": {
                    "name": "claim",
                    "description": "d",
                    "authority_class": "SECONDARY_AI",
                    "claim_boundary": "b",
                    "projection_nonclaim": "TEST_ONLY",
                    "standard_graph_role": "CLAIM",
                    "current_decision_uid": "sym:Concept:test-decision",
                },
            },
            {
                "uid": "sym:Concept:test-decision",
                "labels": ["Concept", "Guardrail"],
                "properties": {
                    "name": "decision",
                    "description": "d",
                    "authority_class": "SECONDARY_AI",
                    "claim_boundary": "b",
                    "projection_nonclaim": "TEST_ONLY",
                    "standard_graph_role": "DECISION",
                    "assesses_claim_uid": "sym:Concept:test-claim",
                    "evidence_disposition": "NOT_EVALUATED",
                    "claim_ceiling": "TEST",
                    "review_required": True,
                    "weights": [1, 2.5],
                },
            },
            {
                "uid": "sym:AbstractNode:test-source",
                "labels": ["AbstractNode", "SourceDocument"],
                "properties": {
                    "name": "source",
                    "description": "d",
                    "authority_class": "SECONDARY_AI",
                    "claim_boundary": "b",
                    "projection_nonclaim": "TEST_ONLY",
                    "standard_graph_role": "EVIDENCE_ARTIFACT",
                    "source_path": "docs/example.md",
                    "source_sha256": "0" * 64,
                },
            },
        ],
        "relations": [
            {"from_uid": "sym:Concept:test-claim", "type": "HAS_SOURCE", "to_uid": "sym:AbstractNode:test-source", "authority_class": "SYSTEM_DERIVED", "scope": "S", "status": "BOUND"},
            {"from_uid": "sym:Concept:test-claim", "type": "HAS_CONCEPT", "to_uid": "sym:Concept:test-decision", "authority_class": "SECONDARY_AI", "scope": "S", "status": "ACTIVE"},
            {"from_uid": "sym:Concept:test-decision", "type": "CONSTRAINS", "to_uid": "sym:Concept:test-claim", "authority_class": "SECONDARY_AI", "scope": "S", "status": "ACTIVE"},
        ],
    }
    if mutate is not None:
        mutate(bundle)
    return json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()


def _synthetic_source(source_id: str = "synthetic", mutate=None) -> KgBundleSource:
    raw = _synthetic(mutate)
    return KgBundleSource(source_id, raw, sha256(raw).hexdigest(), len(raw))


def test_closure_bundle_view_is_deterministic_blank_node_free_and_bound() -> None:
    left = KgBundleGraphView.from_bundles(sources=(_source(CLOSURE, "closure"),))
    right = KgBundleGraphView.from_bundles(sources=(_source(CLOSURE, "closure"),))
    assert left.nquads == right.nquads
    assert b"_:" not in left.nquads
    assert left.descriptor["dataset"]["sha256"] == sha256(left.nquads).hexdigest()
    bundle = json.loads(CLOSURE.read_text(encoding="utf-8"))
    assert left.descriptor["nodeCount"] == len(bundle["nodes"])
    assert left.descriptor["relationCount"] == len(bundle["relations"])
    assert left.descriptor["nonclaim"] == NONCLAIM
    assert left.claim_ceiling == CLAIM_CEILING
    assert b"sym:AbstractNode:hswm-closure-plan-ontology-2026-09-05-v3" in left.nquads
    with pytest.raises(KgBundleGraphViewError, match="immutable"):
        left.claim_ceiling = "x"  # type: ignore[misc]


@pytest.mark.parametrize("path", (CLOSURE, CLOSURE_V2, CLOSURE_V1, ADAPTIVE, CAUSAL, GRAPH_LOOP, EFFECT_FP))
def test_checked_in_bundles_conform_to_the_shared_shacl_shape(path: Path) -> None:
    view = KgBundleGraphView.from_bundles(sources=(_source(path, path.stem.lower()),))
    report = view.validate_shacl(shapes=SHAPES.read_bytes())
    assert report["conforms"], report["report_text"]


def test_closure_plan_sparql_invariants_hold() -> None:
    view = KgBundleGraphView.from_bundles(sources=(_source(CLOSURE, "closure"),))
    every_claim_has_a_matching_decision = PREFIXES + """
    ASK { FILTER NOT EXISTS {
      ?claim a kbrole:CLAIM ; kb:uid ?uid .
      FILTER NOT EXISTS {
        ?claim kbr:HAS_CONCEPT ?decision .
        ?decision a kbrole:DECISION ; kbp:assesses_claim_uid ?uid .
      }
    } }
    """
    assert view.query(every_claim_has_a_matching_decision) is True
    every_user_step_depends_on_a_user_decision = PREFIXES + """
    ASK { FILTER NOT EXISTS {
      ?step a kbrole:CLOSURE_STEP ; kbp:needs_user true .
      FILTER NOT EXISTS { ?step kbr:DEPENDS_ON ?decision . ?decision a kbrole:USER_PRIMARY_DECISION . }
    } }
    """
    assert view.query(every_user_step_depends_on_a_user_decision) is True
    every_ratified_decision_is_bound_to_the_user_source = PREFIXES + """
    ASK { FILTER NOT EXISTS {
      ?d a kbrole:USER_PRIMARY_DECISION ; kbp:ratification_status "RATIFIED" ; kbp:ratification_source_sha256 ?sha .
      FILTER NOT EXISTS { ?d kbr:HAS_SOURCE ?src . ?src kbp:source_sha256 ?sha ; kb:label "UserCanonicalUtterance" . }
    } }
    """
    assert view.query(every_ratified_decision_is_bound_to_the_user_source) is True
    ratified = view.query(PREFIXES + """
    SELECT ?id WHERE { ?d a kbrole:USER_PRIMARY_DECISION ; kbp:ratification_status "RATIFIED" ; kbp:decision_id ?id . }
    """)
    assert sorted(row["id"]["value"] for row in ratified) == ["D-1", "D-4"]
    proposed_has_no_source = PREFIXES + """
    ASK { FILTER NOT EXISTS { ?d a kbrole:USER_PRIMARY_DECISION ; kbp:ratification_status "PROPOSED" ; kbr:HAS_SOURCE ?s . } }
    """
    assert view.query(proposed_has_no_source) is True
    every_gap_is_closed_by_a_step = PREFIXES + """
    ASK { FILTER NOT EXISTS {
      ?gap a kbrole:GAP .
      FILTER NOT EXISTS { ?step a kbrole:CLOSURE_STEP ; kbr:CLOSES ?gap . }
    } }
    """
    assert view.query(every_gap_is_closed_by_a_step) is True
    refuted_findings_block_nothing = PREFIXES + """
    ASK { FILTER NOT EXISTS {
      ?f a kbrole:CLAIM ; kbp:verification_status "REFUTED" .
      { ?f kbr:BLOCKS ?g } UNION { ?f kbr:ASSESSES ?g }
    } }
    """
    assert view.query(refuted_findings_block_nothing) is True
    rows = view.query(PREFIXES + """
    SELECT ?order ?runBy WHERE { ?s a kbrole:CLOSURE_STEP ; kbp:step_order ?order ; kbp:run_by ?runBy . }
    """)
    assert len(rows) == 6
    assert sorted(int(row["order"]["value"]) for row in rows) == [1, 2, 3, 4, 5, 6]
    anchors = view.query(PREFIXES + "SELECT ?uid WHERE { ?a a kb:Anchor ; kb:uid ?uid . }")
    assert {row["uid"]["value"] for row in anchors} >= {
        "sym:Hypothesis:hswm-meta-g0-measurement-integrity",
        "sym:Hypothesis:hswm-meta-g1-local-causal-rung",
    }


def test_prov_envelope_and_multi_bundle_projection() -> None:
    view = KgBundleGraphView.from_bundles(
        sources=(_source(ADAPTIVE, "adaptive"), _source(CLOSURE, "closure"), _source(CLOSURE_V1, "closure-v1"))
    )
    envelope = json.loads(view.prov_o_envelope())
    assert envelope["@graph"][1]["prov:wasDerivedFrom"] == [
        {"@id": f"urn:sha256:{item['sha256']}"} for item in view.descriptor["sources"]
    ]
    assert view.descriptor["sources"][0]["id"] == "adaptive"
    derived = view.query(PREFIXES + """
    ASK { ?p a kb:Projection ; prov:wasDerivedFrom ?b1 , ?b2 . ?b1 a kb:Bundle . ?b2 a kb:Bundle . FILTER(?b1 != ?b2) }
    """)
    assert derived is True


def test_synthetic_bundle_round_trip_and_shacl_violation_detection() -> None:
    view = KgBundleGraphView.from_bundles(sources=(_synthetic_source(),))
    assert view.validate_shacl(shapes=SHAPES.read_bytes())["conforms"]
    assert b'"2.5"^^<http://www.w3.org/2001/XMLSchema#double>' in view.nquads
    assert b'"true"^^<http://www.w3.org/2001/XMLSchema#boolean>' in view.nquads

    def drop_decision_link(bundle: dict) -> None:
        del bundle["nodes"][1]["properties"]["assesses_claim_uid"]

    broken = KgBundleGraphView.from_bundles(sources=(_synthetic_source("broken", drop_decision_link),))
    report = broken.validate_shacl(shapes=SHAPES.read_bytes())
    assert not report["conforms"]
    assert "assesses_claim_uid" in report["report_text"]


def test_source_and_query_boundaries_fail_closed() -> None:
    good = _synthetic_source()
    with pytest.raises(KgBundleGraphViewError, match="SHA-256 differs"):
        KgBundleSource("mutated", good.raw_bytes + b" ", good.sha256, good.byte_length + 1)
    with pytest.raises(KgBundleGraphViewError, match="byte length differs"):
        KgBundleSource("short", good.raw_bytes, good.sha256, good.byte_length - 1)

    def dangling(bundle: dict) -> None:
        bundle["relations"][0]["to_uid"] = "sym:Concept:missing"

    with pytest.raises(KgBundleGraphViewError, match="neither owned nor anchored"):
        _synthetic_source("dangling", dangling)

    def nested(bundle: dict) -> None:
        bundle["nodes"][0]["properties"]["nested"] = {"a": 1}

    with pytest.raises(KgBundleGraphViewError, match="non-scalar"):
        _synthetic_source("nested", nested)

    def secret(bundle: dict) -> None:
        bundle["nodes"][0]["properties"]["password"] = "x"

    with pytest.raises(KgBundleGraphViewError, match="forbidden property key"):
        _synthetic_source("secret", secret)

    def bad_count(bundle: dict) -> None:
        bundle["expected_counts"]["nodes"] = 5

    with pytest.raises(KgBundleGraphViewError, match="expected_counts.nodes"):
        _synthetic_source("count", bad_count)
    raw = b'{"schema_version":"x","schema_version":"x"}'
    with pytest.raises(KgBundleGraphViewError, match="duplicate JSON key"):
        KgBundleSource("duplicate", raw, sha256(raw).hexdigest(), len(raw))
    view = KgBundleGraphView.from_bundles(sources=(good,))
    with pytest.raises(KgBundleGraphViewError, match="only SELECT and ASK"):
        view.query("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")
    with pytest.raises(KgBundleGraphViewError, match="forbidden"):
        view.query("SELECT * WHERE { SERVICE <http://example.invalid/sparql> { ?s ?p ?o } }")
    with pytest.raises(KgBundleGraphViewError, match="unique"):
        KgBundleGraphView.from_bundles(sources=(good, good))
