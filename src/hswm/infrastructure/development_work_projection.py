"""Validate, export, and explicitly publish one bounded development-work KG snapshot.

This projection records a source-pinned local engineering snapshot.  It is not
canonical HSWM state, a learning admission path, or efficacy evidence.
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
ONTOLOGY_PATH = Path(
    "ontology/identity/hswm_core/HSWM_ADAPTIVE_DEVELOPMENT_WORK_ONTOLOGY.v1.json"
)
BUNDLE_UID = "sym:AbstractNode:hswm-adaptive-development-work-2026-09-08-v1"
SCHEMA_VERSION = "hswm-adaptive-development-work-ontology-v1"
SOURCE_COMMIT = "c59aa4584c4729caf98b0d5bb899602c3718e3c4"
# Reviewed immutable engineering snapshot; changes require a new reviewed pin.
REVIEWED_ARTIFACT_SHA256 = "737324f0a9b64d061d7155c207a62877a122c1818b2a56460b54fe6e7050ca64"
ALLOWED_RELATION_TYPES = frozenset(
    {"HAS_SOURCE", "HAS_CONCEPT", "SPECULATIVE_LINK", "REQUIRES", "PRESERVES", "TESTS", "REFINES"}
)
REQUIRED_TOP = frozenset(
    {
        "schema_version",
        "bundle_uid",
        "status",
        "nonclaim",
        "authority_boundary",
        "source_accessed_on",
        "artifact_bindings",
        "expected_counts",
        "anchors",
        "nodes",
        "relations",
    }
)
GENERIC_SHAPES = ROOT / "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl"
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


def _safe_historical_path(value: object, repo_root: Path) -> str:
    """Accept a normalized repository path without trusting worktree contents."""

    if not isinstance(value, str) or not value:
        _fail("artifact binding path is not normalized repository-relative text")
    relative = Path(value)
    if (
        relative.is_absolute()
        or relative.as_posix() != value
        or any(part in {".", ".."} for part in relative.parts)
    ):
        _fail("artifact binding path is not normalized repository-relative text")
    root = repo_root.resolve()
    candidate = root / relative
    # The bytes come from Git, so a removed current file is acceptable.  A
    # current symlink in this route is still rejected: it must not make a
    # historical binding look like an allowed filesystem traversal.
    for current in (candidate, *candidate.parents):
        if current.is_symlink():
            _fail("artifact binding may not traverse a symlink")
        if current == root:
            break
    return relative.as_posix()


def _git_blob(repo_root: Path, commit: str, relative: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{commit}:{relative}"],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"source commit does not contain bound artifact: {relative}") from error


def _validate_bindings(rows: object, repo_root: Path) -> set[str]:
    if not isinstance(rows, list) or not rows:
        _fail("artifact_bindings must be a non-empty list")
    paths: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            _fail("artifact binding shape is invalid")
        path = _safe_historical_path(row.get("path"), repo_root)
        value = row.get("sha256")
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            _fail("artifact binding SHA-256 is invalid")
        if path in paths:
            _fail("duplicate artifact binding")
        if sha256(_git_blob(repo_root, SOURCE_COMMIT, path)).hexdigest() != value:
            _fail(f"source-commit artifact hash drift: {path}")
        paths.add(path)
    return paths


def _validate_nodes(rows: object, bound_paths: set[str]) -> set[str]:
    if not isinstance(rows, list) or not rows:
        _fail("nodes must be a non-empty list")
    seen: set[str] = set()
    root_count = 0
    for row in rows:
        if not isinstance(row, dict):
            _fail("node must be an object")
        uid = row.get("uid")
        if not isinstance(uid, str) or uid in seen:
            _fail("node UID is invalid or duplicated")
        if set(row.get("labels", [])) != {"AbstractNode", "Concept"}:
            _fail("development-work node labels must be AbstractNode and Concept")
        properties = row.get("properties")
        if not isinstance(properties, dict):
            _fail("node properties must be an object")
        if properties.get("authority_class") != "SECONDARY_AI":
            _fail("development-work nodes must be SECONDARY_AI")
        if properties.get("source_commit") != SOURCE_COMMIT:
            _fail("node source_commit must equal the fixed development snapshot")
        sources = properties.get("source_paths")
        if sources is not None and (
            not isinstance(sources, list)
            or not all(isinstance(path, str) and path in bound_paths for path in sources)
        ):
            _fail("node source_paths must be bound historical artifacts")
        root_count += uid == BUNDLE_UID
        seen.add(uid)
    if root_count != 1:
        _fail("bundle root node must occur exactly once")
    return seen


def _validate_relations(rows: object, endpoints: set[str]) -> None:
    if not isinstance(rows, list):
        _fail("relations must be a list")
    for row in rows:
        if not isinstance(row, dict) or row.get("type") not in ALLOWED_RELATION_TYPES:
            _fail("relation type is outside development-work allowlist")
        if row.get("authority_class") != "SECONDARY_AI":
            _fail("development-work relations must be SECONDARY_AI")
        if row.get("from_uid") not in endpoints or row.get("to_uid") not in endpoints:
            _fail("relation endpoint is not an owned node or declared anchor")


def validate_data(data: dict[str, Any], repo_root: Path = ROOT) -> None:
    """Fail closed on snapshot identity, historical source, or graph drift."""

    if set(data) != REQUIRED_TOP:
        _fail("ontology top-level shape drift")
    if data.get("schema_version") != SCHEMA_VERSION or data.get("bundle_uid") != BUNDLE_UID:
        _fail("ontology identity drift")
    if data.get("status") != "ENGINEERING_REFERENCE_SNAPSHOT_NOT_EFFICACY":
        _fail("development-work status drift")
    if not isinstance(data.get("nonclaim"), str) or not isinstance(data.get("authority_boundary"), str):
        _fail("ontology authority boundary and nonclaim must be text")
    if not isinstance(data.get("source_accessed_on"), str):
        _fail("source_accessed_on must be text")
    if COMMIT.fullmatch(SOURCE_COMMIT) is None:
        _fail("fixed source commit is invalid")
    bound_paths = _validate_bindings(data.get("artifact_bindings"), repo_root)
    nodes = _validate_nodes(data.get("nodes"), bound_paths)
    anchors = data.get("anchors")
    if not isinstance(anchors, list) or any(not isinstance(row, dict) for row in anchors):
        _fail("anchors must be a list of objects")
    if any(not isinstance(row.get("uid"), str) or not row["uid"] for row in anchors):
        _fail("anchor UID is invalid")
    anchor_uids = {row["uid"] for row in anchors}
    if len(anchor_uids) != len(anchors) or nodes & anchor_uids:
        _fail("anchors must have distinct UIDs outside owned nodes")
    _validate_relations(data.get("relations"), nodes | anchor_uids)
    counts = data.get("expected_counts")
    expected = {"nodes": len(nodes), "anchors": len(anchors), "relations": len(data["relations"])}
    if counts != expected:
        _fail("expected graph counts drift")
    validate_bundle_semantics(data)
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    KgBundleGraphView.from_bundles(
        sources=(KgBundleSource("adaptive-development-work", raw, sha256(raw).hexdigest(), len(raw)),)
    )


def _view(raw: bytes) -> KgBundleGraphView:
    return KgBundleGraphView.from_bundles(
        sources=(KgBundleSource("adaptive-development-work", raw, sha256(raw).hexdigest(), len(raw)),)
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
