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
SHAPES = ROOT / "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl"
LEGACY_SHAPES = ROOT / "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0.ttl"
CLOSURE = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v5.json"
CLOSURE_V4 = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v4.json"
CLOSURE_V3 = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v3.json"
CLOSURE_V2 = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v2.json"
CLOSURE_V1 = ROOT / "ontology/identity/hswm_core/HSWM_CLOSURE_PLAN_ONTOLOGY.v1.json"
SESSION_LEDGER = ROOT / "ontology/identity/hswm_core/HSWM_SESSION_LEDGER_2026-09-06.v2.json"
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
    assert b"sym:AbstractNode:hswm-closure-plan-ontology-2026-09-05-v4" in left.nquads
    with pytest.raises(KgBundleGraphViewError, match="immutable"):
        left.claim_ceiling = "x"  # type: ignore[misc]


@pytest.mark.parametrize("path", (CLOSURE, CLOSURE_V4, CLOSURE_V3, CLOSURE_V2, CLOSURE_V1, SESSION_LEDGER, ADAPTIVE, CAUSAL, GRAPH_LOOP, EFFECT_FP))
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
    assert sorted(row["id"]["value"] for row in ratified) == ["D-1", "D-3", "D-4"]
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

    with pytest.raises(ValueError, match="does not assess"):
        KgBundleGraphView.from_bundles(sources=(_synthetic_source("broken", drop_decision_link),))


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


def _cross_bundle_source(
    source_id: str,
    bundle_uid: str,
    node_uid: str,
    labels: list[str],
    *,
    anchors: list[dict] | None = None,
    bindings: list[dict] | None = None,
) -> KgBundleSource:
    bundle = {
        "schema_version": "hswm-test-cross-bundle/v1",
        "bundle_uid": bundle_uid,
        "status": "TEST",
        "nonclaim": "TEST_ONLY",
        "artifact_bindings": bindings or [{"path": f"docs/{source_id}.md", "sha256": "a" * 64}],
        "expected_counts": {"nodes": 1, "anchors": len(anchors or []), "relations": 0},
        "anchors": anchors or [],
        "nodes": [
            {
                "uid": node_uid,
                "labels": labels,
                "properties": {
                    "name": source_id,
                    "description": "test node",
                    "authority_class": "SECONDARY_AI",
                    "claim_boundary": "TEST_ONLY",
                    "projection_nonclaim": "TEST_ONLY",
                },
            }
        ],
        "relations": [],
    }
    raw = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
    return KgBundleSource(source_id, raw, sha256(raw).hexdigest(), len(raw))


def test_v2_rejects_cross_bundle_anchor_label_mismatch_and_v1_remains_explicit_legacy() -> None:
    shared_uid = "sym:Concept:shared-owner"
    owner = _cross_bundle_source(
        "owner",
        "sym:AbstractNode:owner-bundle",
        shared_uid,
        ["Concept"],
    )
    dependent = _cross_bundle_source(
        "dependent",
        "sym:AbstractNode:dependent-bundle",
        "sym:Concept:dependent-node",
        ["Concept"],
        anchors=[{"uid": shared_uid, "name": "shared", "required_labels": ["Concept", "Guardrail"]}],
    )
    with pytest.raises(KgBundleGraphViewError, match="required_labels disagree"):
        KgBundleGraphView.from_bundles(sources=(owner, dependent))

    legacy = KgBundleGraphView.from_bundles(sources=(owner, dependent), profile="v1")
    assert legacy.descriptor["contractVersion"] == "hswm-kg-bundle-rdf-projection/v1"
    assert b"AnchorReference" not in legacy.nquads
    legacy_single = KgBundleGraphView.from_bundles(
        sources=(_synthetic_source(),), profile="v1"
    )
    assert legacy_single.validate_shacl(shapes=LEGACY_SHAPES.read_bytes())["conforms"]


def test_v2_preserves_cross_bundle_anchor_descriptor_and_distinct_binding_occurrences() -> None:
    shared_uid = "sym:Concept:shared-owner"
    owner = _cross_bundle_source(
        "owner",
        "sym:AbstractNode:owner-bundle",
        shared_uid,
        ["Concept", "Guardrail"],
    )
    dependent = _cross_bundle_source(
        "dependent",
        "sym:AbstractNode:dependent-bundle",
        "sym:Concept:dependent-node",
        ["Concept"],
        anchors=[{"uid": shared_uid, "name": "shared", "required_labels": ["Concept", "Guardrail"]}],
        bindings=[
            {"path": "docs/first.md", "sha256": "b" * 64},
            {"path": "docs/second.md", "sha256": "b" * 64},
        ],
    )
    view = KgBundleGraphView.from_bundles(sources=(owner, dependent))
    assert view.validate_shacl(shapes=SHAPES.read_bytes())["conforms"]
    lines = view.nquads.decode().splitlines()
    binding_subjects = {
        line.split()[0]
        for line in lines
        if line.split()[1].endswith("#type>") and line.split()[2].endswith("ArtifactBinding>")
    }
    assert len(binding_subjects) == 3
    assert sum("ArtifactContent>" in line for line in lines) == 2
    repeated_content = f"<urn:sha256:{'b' * 64}>"
    assert sum(
        line.startswith(repeated_content + " ") and "ArtifactContent>" in line for line in lines
    ) == 1
    assert sum("bindsArtifact>" in line for line in lines) == 3
    references = [line for line in lines if "AnchorReference>" in line]
    assert len(references) == 1
    reference = references[0].split()[0]
    descriptor_lines = [line for line in lines if line.startswith(reference + " ")]
    assert any('"Concept"' in line for line in descriptor_lines)
    assert any('"Guardrail"' in line for line in descriptor_lines)


def test_v2_rejects_closure_current_decision_pointer_mutation() -> None:
    data = json.loads(CLOSURE.read_text(encoding="utf-8"))
    claim = next(row for row in data["nodes"] if "current_decision_uid" in row["properties"])
    claim["properties"]["current_decision_uid"] = "sym:Concept:not-an-owned-decision"
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    source = KgBundleSource("closure-mutant", raw, sha256(raw).hexdigest(), len(raw))
    with pytest.raises(ValueError, match="current_decision_uid does not identify"):
        KgBundleGraphView.from_bundles(sources=(source,))


def test_explicit_v1_profile_matches_pinned_pre_v2_compiler_bytes() -> None:
    # Frozen using compiler revision 3aff4b38a2611da84688e451da438a6bb6c0c79d.
    # Keep this oracle independent of the current implementation and usable in
    # an extracted sdist without Git metadata or repository history.
    raw = CLOSURE.read_bytes()
    assert sha256(raw).hexdigest() == (
        "08f45acbfee42750ac2a463db95bd2faa2dd0bbe5b4cf2da262acdcf27757222"
    )
    current = KgBundleGraphView.from_bundles(
        sources=(KgBundleSource("closure", raw, sha256(raw).hexdigest(), len(raw)),),
        profile="v1",
    )
    assert sha256(current.nquads).hexdigest() == (
        "d51484b1674363fcd2c0d50e2d9d1920e60fb899585c057f603ed02c256374de"
    )
