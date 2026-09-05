from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from hswm.infrastructure.hypergraph_projection_validation import validate_hypergraph_projection


ROOT = Path(__file__).resolve().parents[1]
SHAPES = ROOT / "schemas" / "HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_SHACL_1_0.ttl"
VOCAB = "https://hswm.invalid/canonical-atom-v2/rdf/v1/vocab/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
XSD = "http://www.w3.org/2001/XMLSchema#"


def _dataset(*, state_sha: str = "0" * 64) -> bytes:
    subject, graph = "https://example.test/dataset", "https://example.test/graph"
    values = [
        (RDF, f"<{VOCAB}Dataset>"),
        (f"{VOCAB}stateSha256", f'"{state_sha}"'),
        (f"{VOCAB}stateRevision", f'"1"^^<{XSD}nonNegativeInteger>'),
        (f"{VOCAB}schemaVersion", '"schema:v2"'),
        (f"{VOCAB}schemaContentSha256", f'"{"1" * 64}"'),
        (f"{VOCAB}journalLineageId", '"journal:main"'),
        (f"{VOCAB}tailSha256", f'"{"2" * 64}"'),
        (f"{VOCAB}rdfProfile", '"RDF_1_1_N_QUADS_BLANK_NODE_FREE_DETERMINISTIC_PROFILE"'),
        (f"{VOCAB}mapping", '"ROLE_PRESERVING_REIFIED_TYPED_REFERENCE"'),
        (f"{VOCAB}writeBack", '"FORBIDDEN"'),
        (f"{VOCAB}nonclaim", '"RDF_PROJECTION_ONLY_NOT_CANONICAL_HSWM_STATE_COGNITION_LEARNING_PERMISSION_OR_EFFICACY"'),
        (f"{VOCAB}compilerContractVersion", '"hswm-canonical-atom-v2-rdf-projection/v1"'),
        (f"{VOCAB}compilerContractSha256", f'"{"3" * 64}"'),
    ]
    return "".join(f"<{subject}> <{predicate}> {obj} <{graph}> .\n" for predicate, obj in values).encode()


def _manifest(dataset: bytes) -> dict[str, object]:
    return {
        "_tag": "CanonicalAtomV2RdfProjectionManifest",
        "contractVersion": "hswm-canonical-atom-v2-rdf-projection/v1",
        "rdfProfile": "RDF_1_1_N_QUADS_BLANK_NODE_FREE_DETERMINISTIC_PROFILE",
        "mapping": "ROLE_PRESERVING_REIFIED_TYPED_REFERENCE",
        "dataset": {"mediaType": "application/n-quads", "byteLength": len(dataset), "sha256": sha256(dataset).hexdigest()},
        "writeBack": "FORBIDDEN",
        "nonclaim": "RDF_PROJECTION_ONLY_NOT_CANONICAL_HSWM_STATE_COGNITION_LEARNING_PERMISSION_OR_EFFICACY",
        "invalidatedBy": ["SCHEMA_CONTENT_BINDING_CHANGED", "STATE_DIGEST_CHANGED", "TAIL_DESCRIPTOR_OR_BYTES_CHANGED", "COMPILER_PROFILE_CHANGED"],
        "rdfDatasetOmits": ["RAW_CONTENT_PAYLOAD_BYTES", "FULL_JOURNAL_CHAIN"],
        "source": {"stateSha256": "0" * 64},
    }


def test_validation_binds_shapes_dataset_and_source_digest(tmp_path: Path) -> None:
    dataset = _dataset()
    nquads, projection = tmp_path / "projection.nq", tmp_path / "projection.json"
    nquads.write_bytes(dataset)
    projection.write_text(json.dumps({"manifest": _manifest(dataset)}), encoding="utf-8")
    report = validate_hypergraph_projection(projection_json=projection, nquads=nquads, shapes=SHAPES)
    assert report["conforms"] is True
    assert report["datasetSha256"] == sha256(dataset).hexdigest()
    assert report["sourceStateSha256"] == "0" * 64
    assert report["shapesSha256"] == sha256(SHAPES.read_bytes()).hexdigest()
    assert "FULL_GRAPH_LOSSLESSNESS" in report["claimCeiling"]


def test_validation_returns_nonconformance_for_an_invalid_shacl_projection(tmp_path: Path) -> None:
    dataset = _dataset(state_sha="not-a-sha")
    nquads, projection = tmp_path / "projection.nq", tmp_path / "projection.json"
    nquads.write_bytes(dataset)
    projection.write_text(json.dumps({"manifest": _manifest(dataset)}), encoding="utf-8")
    report = validate_hypergraph_projection(projection_json=projection, nquads=nquads, shapes=SHAPES)
    assert report["conforms"] is False


def test_cli_exits_nonzero_and_returns_the_shacl_report_for_invalid_projection(tmp_path: Path) -> None:
    dataset = _dataset(state_sha="not-a-sha")
    nquads, projection = tmp_path / "projection.nq", tmp_path / "projection.json"
    nquads.write_bytes(dataset)
    projection.write_text(json.dumps({"manifest": _manifest(dataset)}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "hswm.infrastructure.hypergraph_projection_validation", "--projection-json", str(projection), "--nquads", str(nquads), "--shapes", str(SHAPES)],
        cwd=ROOT, check=False, capture_output=True, text=True,
    )
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["conforms"] is False
    assert report["shapesSha256"] == sha256(SHAPES.read_bytes()).hexdigest()
