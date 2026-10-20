#!/usr/bin/env python3
"""Check the receipt's local PROV view with the existing RDF/SHACL/SPARQL stack."""
import hashlib
import json
from pathlib import Path
import sys

from pyshacl import validate
from rdflib import Graph, Namespace, RDF

SHAPES = """
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<urn:hswm:finite-guard:result-shape> a sh:NodeShape ;
  sh:targetSubjectsOf prov:value ;
  sh:class prov:Entity ;
  sh:property [ sh:path prov:value ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path prov:wasGeneratedBy ; sh:minCount 1 ; sh:maxCount 1 ; sh:class prov:Activity ] ;
  sh:property [ sh:path prov:wasDerivedFrom ; sh:minCount 1 ; sh:class prov:Entity ] .
<urn:hswm:finite-guard:activity-shape> a sh:NodeShape ;
  sh:targetClass prov:Activity ;
  sh:property [ sh:path prov:used ; sh:minCount 1 ; sh:class prov:Entity ] ;
  sh:property [ sh:path prov:wasAssociatedWith ; sh:minCount 1 ; sh:maxCount 1 ; sh:class prov:Agent ] .
"""

def check(path: Path):
    raw = path.read_bytes()
    assert path.name == hashlib.sha256(raw).hexdigest() + ".json", "Receipt address mismatch"
    receipt = json.loads(raw)
    assert receipt["schema_version"] == "hswm-research-receipt/v1"
    assert receipt["actor"] == "agent(codex)" and receipt["authority_class"] == "SECONDARY_AI"
    graph = Graph().parse(data=json.dumps(receipt["graph"]), format="json-ld")
    shapes = Graph().parse(data=SHAPES, format="turtle")
    conforms, _, report = validate(graph, shacl_graph=shapes, inference="none")
    assert conforms, report
    rows = list(graph.query("""
      PREFIX prov: <http://www.w3.org/ns/prov#>
      SELECT ?result ?activity ?value WHERE {
        ?result a prov:Entity ; prov:wasGeneratedBy ?activity ; prov:value ?value .
        ?activity a prov:Activity .
      }
    """))
    assert len(rows) == 1 and json.loads(str(rows[0].value)) == receipt["observations"], "Wrong measured result"
    prov = Namespace("http://www.w3.org/ns/prov#")
    # Exercise the shape's actual referential type check, not just triple count.
    graph.remove((rows[0].activity, RDF.type, prov.Activity))
    assert not validate(graph, shacl_graph=shapes, inference="none")[0], "Missing activity accepted"
    return {"status": "LOCAL_PROV_VIEW_VERIFIED", "measuredResult": str(rows[0].result),
            "missingActivityRejected": True, "claim": "Local receipt shapes and result query, not full PROV qualification"}

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: .venv/bin/python _research/finite_guard_live_v1/check_graph.py RECEIPT.json")
    print(json.dumps(check(Path(sys.argv[1])), indent=2))
