from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from hswm.infrastructure import fractal_learning_plan_projection as projection
from hswm.infrastructure.kg_bundle_graph_view import KgBundleGraphView, KgBundleSource


PREFIX = """
PREFIX kbrole: <https://hswm.invalid/kg-bundle-rdf/v1/role/>
PREFIX kbr: <https://hswm.invalid/kg-bundle-rdf/v1/rel/>
PREFIX kbp: <https://hswm.invalid/kg-bundle-rdf/v1/prop/>
"""
ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / projection.DEFAULT_ARTIFACT
DOMAIN_SHAPES = ROOT / "schemas/HSWM_HYPERGRAPH_LEARNING_PLAN_SHACL_1_0.ttl"
requires_graph_runtime = pytest.mark.skipif(
    importlib.util.find_spec("rdflib") is None or importlib.util.find_spec("pyshacl") is None,
    reason="the optional graph runtime provides RDFLib and PySHACL",
)


def fixture(root: Path) -> dict:
    source = root / "plan.md"
    source.write_text("hypergraph learning plan\n")
    source_sha = sha256(source.read_bytes()).hexdigest()

    def node(uid: str, role: str, labels: list[str], authority: str = "SECONDARY_AI", **extra: object) -> dict:
        properties = {
            "name": uid,
            "description": "bounded plan record",
            "authority_class": authority,
            "claim_boundary": "NOT_A_SCIENTIFIC_RESULT",
            "standard_graph_role": role,
            "source_paths": ["plan.md"],
            **extra,
        }
        if uid == projection.BUNDLE_UID:
            properties["source_commit"] = "a" * 40
        return {"uid": uid, "labels": labels, "properties": properties}

    nodes = [
        node(projection.BUNDLE_UID, "PLAN_BUNDLE", ["AbstractNode"]),
        node("sym:AbstractNode:assertion", "LEARNING_ASSERTION", ["AbstractNode", "Hyperedge"]),
        node("sym:AbstractNode:concept", "CONCEPT", ["AbstractNode", "Concept"]),
        node("sym:AbstractNode:part-observation", "ROLE_PARTICIPATION", ["AbstractNode", "Participation"], role_name="observes", ordinal=1, revision_scope="cell", membership_status="PROPOSED"),
        node("sym:AbstractNode:part-credit", "ROLE_PARTICIPATION", ["AbstractNode", "Participation"], role_name="credits", ordinal=2, revision_scope="whole", membership_status="PROPOSED"),
    ]
    relations = [
        {"from_uid": "sym:AbstractNode:assertion", "type": "HAS_PARTICIPATION", "to_uid": uid, "authority_class": "SECONDARY_AI", "scope": "PLAN", "status": "PROPOSED"}
        for uid in ("sym:AbstractNode:part-observation", "sym:AbstractNode:part-credit")
    ] + [
        {"from_uid": uid, "type": "TARGET", "to_uid": "sym:AbstractNode:concept", "authority_class": "SECONDARY_AI", "scope": "PLAN", "status": "PROPOSED"}
        for uid in ("sym:AbstractNode:part-observation", "sym:AbstractNode:part-credit")
    ]
    return {
        "schema_version": projection.SCHEMA_VERSION,
        "bundle_uid": projection.BUNDLE_UID,
        "status": "PROPOSED_UNTESTED",
        "nonclaim": "PLAN_ONLY_NOT_LEARNING_OR_EFFICACY_EVIDENCE",
        "artifact_bindings": [{"path": "plan.md", "sha256": source_sha}],
        "expected_counts": {"nodes": len(nodes), "anchors": 0, "relations": len(relations)},
        "anchors": [], "nodes": nodes, "relations": relations,
    }


@requires_graph_runtime
def test_source_bound_bundle_has_standard_role_and_nary_participants(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    projection.validate_data(data, tmp_path)
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    view = KgBundleGraphView.from_bundles(sources=(KgBundleSource("plan", raw, sha256(raw).hexdigest(), len(raw)),))
    query = PREFIX + """
    SELECT ?assertion ?target (COUNT(?participant) AS ?count) {
      ?assertion a kbrole:LEARNING_ASSERTION ; kbr:HAS_PARTICIPATION ?participant .
      ?participant a kbrole:ROLE_PARTICIPATION ; kbp:role_name ?role ; kbr:TARGET ?target .
    } GROUP BY ?assertion ?target
    """
    rows = view.query(query)
    assert len(rows) == 1
    assert rows[0]["count"]["value"] == "2"


@requires_graph_runtime
def test_checked_in_bundle_preserves_role_incidence_and_conforms_to_domain_shape() -> None:
    raw = ARTIFACT.read_bytes()
    projection.validate_data(json.loads(raw), ROOT)
    view = KgBundleGraphView.from_bundles(
        sources=(KgBundleSource("hypergraph-learning-plan", raw, sha256(raw).hexdigest(), len(raw)),)
    )
    report = view.validate_shacl(shapes=DOMAIN_SHAPES.read_bytes())
    assert report["conforms"], report["report_text"]
    query = PREFIX + """
    SELECT ?assertion ?target ?role ?ordinal {
      ?assertion a kbrole:LEARNING_ASSERTION ; kbr:HAS_PARTICIPATION ?p .
      ?p a kbrole:ROLE_PARTICIPATION ; kbp:role_name ?role ; kbp:ordinal ?ordinal ; kbr:TARGET ?target .
    }
    """
    rows = view.query(query)
    assert rows
    assert any(row["role"] is not None and row["ordinal"] is not None for row in rows)


@requires_graph_runtime
def test_domain_shape_rejects_a_participation_without_target() -> None:
    data = json.loads(ARTIFACT.read_text())
    removed = next(row for row in data["relations"] if row["type"] == "TARGET")
    data["relations"].remove(removed)
    data["expected_counts"]["relations"] -= 1
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    view = KgBundleGraphView.from_bundles(
        sources=(KgBundleSource("missing-target", raw, sha256(raw).hexdigest(), len(raw)),)
    )
    report = view.validate_shacl(shapes=DOMAIN_SHAPES.read_bytes())
    assert not report["conforms"]
    assert "TARGET" in report["report_text"]


def test_non_explicit_primary_record_is_rejected(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    data["nodes"][1]["properties"]["authority_class"] = "USER_PRIMARY"
    with pytest.raises(ValueError, match="direct-request"):
        projection.validate_data(data, tmp_path)


def test_apply_with_wrong_sha_refuses_before_live_publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = tmp_path / "plan.json"
    artifact.write_text(json.dumps(fixture(tmp_path)))
    monkeypatch.setattr(projection.gateway, "publish", lambda *_args, **_kwargs: pytest.fail("must not publish"))
    monkeypatch.setattr(sys, "argv", ["projection", "--ontology", str(artifact), "--repo-root", str(tmp_path), "--apply"])
    with pytest.raises(SystemExit, match="SHA pin"):
        projection.main()
