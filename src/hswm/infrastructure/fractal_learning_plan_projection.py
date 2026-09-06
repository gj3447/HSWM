"""Bounded standard-graph projection for the hypergraph learning-plan bundle.

This is an interoperability and publication boundary.  It does not execute a
rewrite, revise canonical state, or establish that the proposed mechanism
learns, predicts, or has efficacy.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from hswm.infrastructure.kg_bundle_graph_view import KgBundleGraphView, KgBundleSource
from hswm.infrastructure.research_insight_projection import _safe_path
from scripts import upsert_hswm_graph_and_loop_engineering as gateway


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT = Path(
    "ontology/identity/hswm_core/HSWM_HYPERGRAPH_LEARNING_PLAN_ONTOLOGY.v1.json"
)
BUNDLE_UID = "sym:AbstractNode:hswm-hypergraph-learning-plan-2026-09-06-v1"
SCHEMA_VERSION = "hswm-hypergraph-learning-plan/v1"
REVIEWED_ARTIFACT_SHA256 = "c59ef55784059b111b1c73f140d6530144aec4d75220dd1cffd4295ff3e34356"
REQUIRED_TOP = frozenset(
    {
        "schema_version", "bundle_uid", "status", "nonclaim", "artifact_bindings",
        "expected_counts", "anchors", "nodes", "relations",
    }
)
OPTIONAL_TOP = frozenset({"authority_boundary", "source_accessed_on"})
GENERIC_SHAPES = ROOT / "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0.ttl"
COMMIT = re.compile(r"[0-9a-f]{40}\Z")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _fail(message: str) -> None:
    raise ValueError(message)


def _read_data(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("ontology is not JSON") from error
    if not isinstance(data, dict):
        _fail("ontology root must be an object")
    return raw, data


def _validate_bindings(rows: object, repo_root: Path) -> set[str]:
    if not isinstance(rows, list) or not rows:
        _fail("artifact_bindings must be a non-empty list")
    paths: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            _fail("artifact binding shape is invalid")
        path = _safe_path(row.get("path"), repo_root)
        value = row.get("sha256")
        if not isinstance(value, str) or len(value) != 64 or digest(path) != value:
            _fail("artifact binding hash drift")
        if row["path"] in paths:
            _fail("duplicate artifact binding")
        paths.add(row["path"])
    return paths


def _validate_authority(data: Mapping[str, Any], bound_paths: set[str]) -> None:
    bundle_nodes = [row for row in data["nodes"] if row.get("uid") == BUNDLE_UID]
    if len(bundle_nodes) != 1:
        _fail("bundle node must occur exactly once")
    properties = bundle_nodes[0].get("properties")
    if (
        not isinstance(properties, dict)
        or not isinstance(properties.get("source_commit"), str)
        or COMMIT.fullmatch(properties["source_commit"]) is None
    ):
        _fail("bundle node must carry source_commit")
    for row in data["nodes"]:
        properties = row.get("properties")
        if not isinstance(properties, dict):
            _fail("node properties must be an object")
        authority = properties.get("authority_class")
        if authority == "SECONDARY_AI":
            continue
        if authority != "USER_PRIMARY" or properties.get("standard_graph_role") != "USER_DIRECT_REQUEST":
            _fail("only explicit USER_PRIMARY direct-request records are allowed")
        sources = properties.get("source_paths")
        if not isinstance(sources, list) or not sources or not set(sources) <= bound_paths:
            _fail("USER_PRIMARY direct-request record must bind its source")


def validate_data(data: dict[str, Any], repo_root: Path = ROOT) -> None:
    keys = set(data)
    if keys != REQUIRED_TOP | (keys & OPTIONAL_TOP):
        _fail("ontology top-level shape drift")
    if data.get("schema_version") != SCHEMA_VERSION or data.get("bundle_uid") != BUNDLE_UID:
        _fail("ontology identity drift")
    if not isinstance(data.get("status"), str) or not isinstance(data.get("nonclaim"), str):
        _fail("ontology status and nonclaim must be text")
    bound_paths = _validate_bindings(data.get("artifact_bindings"), repo_root)
    _validate_authority(data, bound_paths)
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    KgBundleGraphView.from_bundles(
        sources=(KgBundleSource("hypergraph-learning-plan", raw, sha256(raw).hexdigest(), len(raw)),)
    )


def _view(raw: bytes) -> KgBundleGraphView:
    return KgBundleGraphView.from_bundles(
        sources=(KgBundleSource("hypergraph-learning-plan", raw, sha256(raw).hexdigest(), len(raw)),)
    )


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _export(view: KgBundleGraphView, directory: Path, additional_shapes: Path | None) -> Mapping[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    shapes = GENERIC_SHAPES.read_bytes()
    if additional_shapes is not None:
        shapes += b"\n" + additional_shapes.read_bytes()
    validation = dict(view.validate_shacl(shapes=shapes))
    manifest = _plain(view.descriptor)
    manifest["shacl"] = {"sha256": sha256(shapes).hexdigest(), "conforms": validation["conforms"]}
    (directory / "view.nq").write_bytes(view.nquads)
    (directory / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    (directory / "prov.jsonld").write_bytes(view.prov_o_envelope() + b"\n")
    (directory / "validation.json").write_text(json.dumps(validation, sort_keys=True) + "\n")
    return validation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ontology", type=Path, default=ROOT / DEFAULT_ARTIFACT)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--export-dir", type=Path)
    parser.add_argument("--additional-shapes", type=Path)
    parser.add_argument("--source-config", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raw, data = _read_data(args.ontology)
    validate_data(data, args.repo_root)
    view = _view(raw)
    if args.export_dir is not None:
        report = _export(view, args.export_dir, args.additional_shapes)
        if not report["conforms"]:
            raise SystemExit("SHACL validation failed")
    artifact_sha256 = digest(args.ontology)
    if not args.apply:
        print(json.dumps({"status": "VALIDATED_ONLY_NOT_PUBLISHED", "projection_sha256": artifact_sha256, "new_nodes": len(data["nodes"]), "relations": len(data["relations"])}, sort_keys=True))
        return
    if artifact_sha256 != REVIEWED_ARTIFACT_SHA256:
        raise SystemExit("reviewed artifact SHA pin is not installed or does not match")
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config")
    result = gateway.publish(data, gateway.read_flat_yaml(args.source_config), artifact_sha256)
    print(json.dumps({**result, "status": "APPLIED_OR_VERIFIED_EXACT_PROJECTION", "projection_sha256": artifact_sha256}, sort_keys=True))


if __name__ == "__main__":
    main()
