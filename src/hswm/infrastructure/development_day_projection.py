"""Validate and explicitly publish the fixed 2026-09-08 development-day snapshot.

This is a bounded, source-pinned engineering projection.  It does not publish
runtime state, admit learning, or convert the recorded user request into an
efficacy result.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

from hswm.infrastructure.kg_bundle_graph_view import KgBundleGraphView, KgBundleSource
from hswm.infrastructure.kg_bundle_semantics import validate_bundle_semantics
from scripts import upsert_hswm_graph_and_loop_engineering as gateway

ROOT = Path(__file__).resolve().parents[3]
ONTOLOGY_PATH = Path("ontology/identity/hswm_core/HSWM_DEVELOPMENT_DAY_2026-09-08_ONTOLOGY.v1.json")
BUNDLE_UID = "sym:AbstractNode:hswm-development-day-2026-09-08-v1"
SCHEMA_VERSION = "hswm-development-day-ontology-v1"
# Installed only after the reviewed source/document snapshot is committed.
SOURCE_COMMIT = ""
REVIEWED_ARTIFACT_SHA256 = ""
PRIMARY_SOURCE_PATH = "docs/canon/sources/USER_PRIMARY_HSWM_SELF_DEVELOPMENT_AND_DAILY_KG_2026-09-08.txt"
USER_UID = "sym:AbstractNode:hswm-development-day-2026-09-08-user-request"
OWNER = "hswm:development-day:2026-09-08"
GENERIC_SHAPES = ROOT / "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl"
ALLOWED_RELATION_TYPES = frozenset({"HAS_SOURCE", "HAS_CONCEPT", "SPECULATIVE_LINK", "REQUIRES", "PRESERVES", "TESTS", "REFINES"})
REQUIRED_TOP = frozenset({"schema_version", "bundle_uid", "status", "nonclaim", "authority_boundary", "source_accessed_on", "artifact_bindings", "expected_counts", "anchors", "nodes", "relations"})
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


def _safe_path(value: object, root: Path) -> str:
    if not isinstance(value, str) or not value:
        _fail("artifact binding path is invalid")
    path = Path(value)
    if path.is_absolute() or path.as_posix() != value or any(part in {".", ".."} for part in path.parts):
        _fail("artifact binding path is invalid")
    candidate, resolved_root = root / path, root.resolve()
    for current in (candidate, *candidate.parents):
        if current.is_symlink():
            _fail("artifact binding may not traverse a symlink")
        if current == resolved_root:
            break
    return value


def _blob(root: Path, path: str) -> bytes:
    try:
        return subprocess.run(["git", "-C", str(root), "show", f"{SOURCE_COMMIT}:{path}"], check=True, capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"source commit does not contain bound artifact: {path}") from error


def _bindings(rows: object, root: Path) -> dict[str, str]:
    if not isinstance(rows, list) or not rows:
        _fail("artifact_bindings must be non-empty")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            _fail("artifact binding shape")
        path = _safe_path(row.get("path"), root)
        value = row.get("sha256")
        if path in result or not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            _fail("artifact binding identity")
        if sha256(_blob(root, path)).hexdigest() != value:
            _fail(f"source-commit artifact hash drift: {path}")
        result[path] = value
    if PRIMARY_SOURCE_PATH not in result:
        _fail("primary source binding is required")
    return result


def _nodes(rows: object, bindings: Mapping[str, str], root: Path) -> set[str]:
    if not isinstance(rows, list) or not rows:
        _fail("nodes must be non-empty")
    seen: set[str] = set()
    user = None
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("uid"), str) or row["uid"] in seen:
            _fail("node identity")
        if set(row.get("labels", [])) != {"AbstractNode", "Concept"} or not isinstance(row.get("properties"), dict):
            _fail("node shape")
        props = row["properties"]
        if props.get("source_commit") != SOURCE_COMMIT:
            _fail("node source_commit must equal fixed snapshot")
        paths = props.get("source_paths", [])
        if not isinstance(paths, list) or not all(isinstance(path, str) and path in bindings for path in paths):
            _fail("node source_paths must be bound")
        if row["uid"] == USER_UID:
            user = row
            if (props.get("authority_class") != "USER_PRIMARY" or props.get("ontology_authority") != "USER_PRIMARY"
                    or props.get("ontology_authority_class_v1") != "USER_PRIMARY"):
                _fail("user request authority")
            if (props.get("responsibility_owner") != "user:hswm-development-direction"
                    or props.get("role") != "USER_DIRECT_REQUEST"
                    or props.get("standard_graph_role") != "USER_DIRECT_REQUEST"):
                _fail("user request role/owner")
            if props.get("status") != "USER_REQUEST_RECORDED_NOT_EFFICACY" or props.get("source_path") != PRIMARY_SOURCE_PATH:
                _fail("user request status/source")
            expected = _blob(root, PRIMARY_SOURCE_PATH).decode("utf-8").rstrip("\n")
            if props.get("verbatim_text") != expected or props.get("source_sha256") != bindings[PRIMARY_SOURCE_PATH]:
                _fail("user request quote/source binding")
        else:
            if (props.get("authority_class") != "SECONDARY_AI" or props.get("ontology_authority") == "USER_PRIMARY"
                    or props.get("ontology_authority_class_v1") != "SECONDARY_AI"):
                _fail("non-user node authority promotion")
            if props.get("responsibility_owner") != OWNER:
                _fail("secondary node responsibility owner")
        seen.add(row["uid"])
    if BUNDLE_UID not in seen or user is None:
        _fail("bundle root or user request missing")
    return seen


def _relations(rows: object, endpoints: set[str], source_nodes: set[str]) -> None:
    if not isinstance(rows, list):
        _fail("relations must be a list")
    user_source = False
    for row in rows:
        if not isinstance(row, dict) or row.get("type") not in ALLOWED_RELATION_TYPES:
            _fail("relation type outside allowlist")
        if row.get("authority_class") != "SECONDARY_AI" or row.get("from_uid") not in endpoints or row.get("to_uid") not in endpoints:
            _fail("relation authority or endpoint")
        user_source |= row.get("from_uid") == USER_UID and row.get("type") == "HAS_SOURCE" and row.get("to_uid") in source_nodes
    if not user_source:
        _fail("user request must HAS_SOURCE its primary artifact node")


def validate_data(data: dict[str, Any], repo_root: Path = ROOT) -> None:
    if set(data) != REQUIRED_TOP or data.get("schema_version") != SCHEMA_VERSION or data.get("bundle_uid") != BUNDLE_UID:
        _fail("ontology identity/top-level shape")
    if data.get("status") != "ENGINEERING_REFERENCE_SNAPSHOT_NOT_EFFICACY" or not isinstance(data.get("nonclaim"), str) or not isinstance(data.get("authority_boundary"), str) or not isinstance(data.get("source_accessed_on"), str):
        _fail("ontology status/boundary")
    if COMMIT.fullmatch(SOURCE_COMMIT) is None:
        _fail("fixed source commit is not installed")
    bindings = _bindings(data.get("artifact_bindings"), repo_root)
    nodes = _nodes(data.get("nodes"), bindings, repo_root)
    anchors = data.get("anchors")
    if not isinstance(anchors, list) or any(not isinstance(row, dict) or not isinstance(row.get("uid"), str) or not row["uid"] for row in anchors):
        _fail("anchor shape")
    anchor_uids = {row["uid"] for row in anchors}
    if len(anchor_uids) != len(anchors) or nodes & anchor_uids:
        _fail("anchor identity")
    source_nodes = {
        row["uid"] for row in data["nodes"]
        if row["uid"] != USER_UID
        and row["properties"].get("source_path") == PRIMARY_SOURCE_PATH
        and row["properties"].get("source_sha256") == bindings[PRIMARY_SOURCE_PATH]
        and PRIMARY_SOURCE_PATH in row["properties"].get("source_paths", [])
        and (row["properties"].get("role") == "SOURCE_ARTIFACT"
             or row["properties"].get("standard_graph_role") == "SOURCE_ARTIFACT")
    }
    _relations(data.get("relations"), nodes | anchor_uids, source_nodes)
    if data.get("expected_counts") != {"nodes": len(nodes), "anchors": len(anchors), "relations": len(data["relations"])}:
        _fail("expected graph counts drift")
    validate_bundle_semantics(data)
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    KgBundleGraphView.from_bundles(sources=(KgBundleSource("development-day", raw, sha256(raw).hexdigest(), len(raw)),))


def _view(raw: bytes) -> KgBundleGraphView:
    return KgBundleGraphView.from_bundles(
        sources=(KgBundleSource("development-day", raw, sha256(raw).hexdigest(), len(raw)),)
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
    parser.add_argument("--ontology", type=Path, default=ROOT / ONTOLOGY_PATH)
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
    artifact_sha256 = sha256(raw).hexdigest()
    if not args.apply:
        print(json.dumps({"status": "VALIDATED_ONLY_NOT_PUBLISHED", "projection_sha256": artifact_sha256, "new_nodes": len(data["nodes"]), "relations": len(data["relations"])}, sort_keys=True))
        return
    if artifact_sha256 != REVIEWED_ARTIFACT_SHA256:
        raise SystemExit("reviewed artifact SHA pin is not installed or does not match")
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config")
    result = gateway.publish(data, gateway.read_flat_yaml(args.source_config.expanduser()), artifact_sha256)
    print(json.dumps({**result, "status": "APPLIED_OR_VERIFIED_EXACT_PROJECTION", "projection_sha256": artifact_sha256}, sort_keys=True))


if __name__ == "__main__":
    main()
