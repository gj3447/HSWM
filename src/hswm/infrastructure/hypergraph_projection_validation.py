"""Read-only SHACL 1.0 validation for a bounded HSWM RDF projection.

The report binds the supplied projection manifest, N-Quads dataset and SHACL
shapes by digest.  A successful report only establishes this derived RDF
profile's structural conformance; it does not claim full graph losslessness,
canonical admission, Permit, causal credit, learning, or efficacy.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from hswm.infrastructure.standard_graph_view import StandardGraphView, StandardGraphViewError


def _load_manifest(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("projection JSON is not a readable JSON document") from error
    if not isinstance(value, Mapping):
        raise ValueError("projection JSON must be an object")
    manifest = value.get("manifest", value)
    if not isinstance(manifest, Mapping):
        raise ValueError("projection JSON must contain a manifest object")
    return manifest


def validate_hypergraph_projection(
    *, projection_json: Path, nquads: Path, shapes: Path
) -> Mapping[str, Any]:
    """Validate one source-bound derived projection without any graph writes."""
    manifest = _load_manifest(projection_json)
    dataset = nquads.read_bytes()
    shape_bytes = shapes.read_bytes()
    descriptor = manifest.get("dataset")
    if not isinstance(descriptor, Mapping) or not isinstance(descriptor.get("sha256"), str):
        raise ValueError("projection manifest lacks its dataset SHA-256 binding")
    view = StandardGraphView.from_projection(
        projection_dataset_sha256=descriptor["sha256"], projection_manifest=manifest, nquads=dataset
    )
    validation = view.validate_shacl(shapes=shape_bytes)
    source = manifest.get("source")
    source_digest = source.get("stateSha256") if isinstance(source, Mapping) else None
    if not isinstance(source_digest, str):
        raise ValueError("projection manifest lacks an exact source state digest")
    omissions = manifest.get("rdfDatasetOmits", ())
    if not isinstance(omissions, Sequence) or isinstance(omissions, (str, bytes)):
        raise ValueError("projection manifest lacks an explicit RDF mapping-loss declaration")
    return {
        "contract": "hswm-hypergraph-projection-shacl-validation/v1",
        "conforms": validation["conforms"],
        "datasetSha256": sha256(dataset).hexdigest(),
        "sourceStateSha256": source_digest,
        "shapesSha256": sha256(shape_bytes).hexdigest(),
        "mappingLoss": list(omissions),
        "claimCeiling": "SHACL_1_0_DERIVED_RDF_STRUCTURE_ONLY_NOT_FULL_GRAPH_LOSSLESSNESS_CANONICAL_ADMISSION_PERMIT_CAUSAL_CREDIT_LEARNING_OR_EFFICACY",
        "report": validation["report_text"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projection-json", required=True, type=Path)
    parser.add_argument("--nquads", required=True, type=Path)
    parser.add_argument("--shapes", default=Path("schemas/HSWM_CANONICAL_ATOM_V2_RDF_PROJECTION_SHACL_1_0.ttl"), type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = validate_hypergraph_projection(projection_json=args.projection_json, nquads=args.nquads, shapes=args.shapes)
    except (OSError, ValueError, StandardGraphViewError) as error:
        print(json.dumps({"conforms": False, "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["conforms"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
