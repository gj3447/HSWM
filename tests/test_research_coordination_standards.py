"""Exercise the pinned SHACL 1.0 validator against the actual CLI RDF view."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).parents[1]
CLI = ROOT / "src/hswm/effect-runtime/bin/hswm-research-graph"
FIXTURE = ROOT / "_research/research_coordination/hswm_relation_learning.v1.json"
SHAPES = ROOT / "schemas/HSWM_RESEARCH_COORDINATION_SHACL_1_0.ttl"

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("rdflib") is None or importlib.util.find_spec("pyshacl") is None,
    reason="requires the pinned graph environment (rdflib and pyshacl)",
)


def _export() -> dict[str, object]:
    result = subprocess.run(
        [str(CLI), "export", "--graph", str(FIXTURE)], cwd=ROOT,
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _validate(data: str, data_format: str = "nquads"):
    import rdflib
    from pyshacl import validate

    graph = rdflib.Graph().parse(data=data, format=data_format)
    shapes = rdflib.Graph().parse(SHAPES, format="turtle")
    return graph, validate(graph, shacl_graph=shapes, inference="none", abort_on_first=False)


def test_actual_cli_projection_conforms_to_shacl_and_keeps_candidates_local():
    exported = _export()
    nquads = exported["nquads"]
    assert isinstance(nquads, str)
    graph, report = _validate(nquads)
    conforms, _report_graph, report_text = report
    assert conforms, report_text

    query = """
      PREFIX rc: <https://hswm.invalid/research-coordination/v1/>
      SELECT ?hypothesis ?disposition WHERE {
        ?hypothesis a rc:Hypothesis ; rc:disposition ?disposition .
      }
    """
    rows = list(graph.query(query))
    assert rows
    assert {str(row.disposition) for row in rows} == {"CANDIDATE"}
    roots = list(graph.query("""
      PREFIX rc: <https://hswm.invalid/research-coordination/v1/>
      SELECT ?projection ?source WHERE {
        ?projection a rc:ResearchGraphProjection .
        ?source a rc:SourceGraph .
      }
    """))
    assert len(roots) == 1

    import rdflib
    projection, _source = roots[0]
    source_hash = rdflib.URIRef("https://hswm.invalid/research-coordination/v1/sourceGraphSha256")
    graph.remove((projection, source_hash, None))
    graph.add((projection, source_hash, rdflib.Literal("not-a-sha256")))
    shapes = rdflib.Graph().parse(SHAPES, format="turtle")
    from pyshacl import validate
    assert not validate(graph, shacl_graph=shapes, inference="none", abort_on_first=False)[0]


def test_actual_recorded_start_finish_is_one_prov_activity_with_typed_times(tmp_path):
    snapshot = json.loads(FIXTURE.read_text())
    snapshot["events"] = [
        {"type": "START", "id": "start-1", "taskId": "explore-relation", "actor": "agent-a", "model": "local", "at": "2026-09-09T00:00:00.000Z"},
        {"type": "FINISH", "id": "finish-1", "taskId": "explore-relation", "actor": "agent-a", "at": "2026-09-09T00:01:00.000Z", "disposition": "REFUTED_IN_SCOPE", "summary": "Scoped failure.", "sourceIds": ["constitution"], "usedTokens": 1},
    ]
    path = tmp_path / "recorded.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    result = subprocess.run([str(CLI), "export", "--graph", str(path)], cwd=ROOT, text=True, capture_output=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    graph, report = _validate(json.loads(result.stdout)["nquads"])
    assert report[0], report[2]
    rows = list(graph.query("""
      PREFIX prov: <http://www.w3.org/ns/prov#>
      PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
      SELECT ?activity ?result WHERE {
        ?activity a prov:Activity ; prov:startedAtTime ?start ; prov:endedAtTime ?end .
        ?result prov:wasGeneratedBy ?activity .
        FILTER(datatype(?start) = xsd:dateTime && datatype(?end) = xsd:dateTime)
      }
    """))
    assert len(rows) == 1


def test_shacl_rejects_a_hypothesis_without_required_scope_and_disposition():
    invalid = """
      @prefix rc: <https://hswm.invalid/research-coordination/v1/> .
      <https://example.invalid/h> a rc:Hypothesis .
    """
    _graph, report = _validate(invalid, "turtle")
    conforms, _report_graph, _report_text = report
    assert not conforms
