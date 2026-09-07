"""Bounded graph projection for the frontier learning-theory research bundle.

This module only validates, exports, and explicitly publishes the one named
research projection.  It cannot make canonical HSWM writes, admit a relation,
or turn a literature connection into evidence of learning efficacy.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from hswm.infrastructure.kg_bundle_graph_view import KgBundleGraphView, KgBundleSource
from hswm.infrastructure.kg_bundle_semantics import validate_bundle_semantics
from hswm.infrastructure.research_insight_projection import _safe_path
from scripts import upsert_hswm_graph_and_loop_engineering as gateway


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT = Path(
    "ontology/identity/hswm_core/HSWM_FRONTIER_LEARNING_THEORY_ONTOLOGY.v1.json"
)
BUNDLE_UID = "sym:AbstractNode:hswm-frontier-learning-theory-2026-09-07-v1"
SCHEMA_VERSION = "hswm-frontier-learning-theory/v1"
# Replaced only after the checked-in bundle and its bindings have been reviewed.
REVIEWED_ARTIFACT_SHA256 = "47fe62066a03f7b8556e9d3f5b45cc583d75ab6696d515a59088cd37d462159a"
ALLOWED_RELATION_TYPES = frozenset(
    {"HAS_SOURCE", "HAS_CONCEPT", "SPECULATIVE_LINK", "REQUIRES", "PRESERVES", "TESTS"}
)
REQUIRED_TOP = frozenset(
    {
        "schema_version",
        "bundle_uid",
        "status",
        "nonclaim",
        "artifact_bindings",
        "expected_counts",
        "anchors",
        "nodes",
        "relations",
    }
)
OPTIONAL_TOP = frozenset({"authority_boundary", "source_accessed_on"})
GENERIC_SHAPES = ROOT / "schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl"
HISTORICAL_SNAPSHOT = ROOT / "ontology/history/HSWM_FRONTIER_LEARNING_THEORY_SOURCE_SNAPSHOT.v1.json"
HISTORICAL_SNAPSHOT_SCHEMA = "hswm-frontier-learning-theory-source-snapshot/v1"
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


def _strict_json_object(path: Path, label: str) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                _fail(f"{label} has duplicate JSON key: {key}")
            value[key] = item
        return value

    try:
        value = json.loads(path.read_text(), object_pairs_hook=unique)
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} is not JSON") from error
    if not isinstance(value, dict):
        _fail(f"{label} root must be an object")
    return value


def _git_blob(repo_root: Path, commit: str, relative: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{commit}:{relative}"],
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"historical source is unavailable: {commit}:{relative}") from error


def validate_historical_snapshot(
    ontology: Path, snapshot_path: Path = HISTORICAL_SNAPSHOT, repo_root: Path = ROOT
) -> dict[str, Any]:
    """Verify the immutable v1 bytes against explicit Git blobs, not the worktree.

    This is a verification mode for an already-published historical snapshot.
    It has no canonical-write or publication capability.
    """

    snapshot = _strict_json_object(snapshot_path, "historical snapshot")
    required = {"schema_version", "bundle_path", "bundle_sha256", "source_commit", "artifact_bindings"}
    if set(snapshot) != required or snapshot.get("schema_version") != HISTORICAL_SNAPSHOT_SCHEMA:
        _fail("historical snapshot shape or schema drift")
    bundle_path = snapshot.get("bundle_path")
    if not isinstance(bundle_path, str) or _safe_path(bundle_path, repo_root) != ontology.resolve():
        _fail("historical snapshot names a different ontology")
    raw, data = _read_data(ontology)
    raw_sha256 = sha256(raw).hexdigest()
    if raw_sha256 != REVIEWED_ARTIFACT_SHA256:
        _fail("historical ontology differs from reviewed artifact SHA pin")
    if not isinstance(snapshot.get("bundle_sha256"), str) or raw_sha256 != snapshot["bundle_sha256"]:
        _fail("historical ontology raw hash drift")
    commit = snapshot.get("source_commit")
    if not isinstance(commit, str) or COMMIT.fullmatch(commit) is None:
        _fail("historical snapshot commit is invalid")
    try:
        resolved = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", f"{commit}^{{commit}}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("historical snapshot commit is unavailable") from error
    if resolved != commit:
        _fail("historical snapshot commit resolution drift")
    if _git_blob(repo_root, commit, bundle_path) != raw:
        _fail("historical ontology Git blob mismatch")
    bindings = snapshot.get("artifact_bindings")
    if not isinstance(bindings, list) or not bindings:
        _fail("historical snapshot bindings are invalid")
    expected = {(row["path"], row["sha256"]) for row in data.get("artifact_bindings", []) if isinstance(row, dict)}
    observed: set[tuple[str, str]] = set()
    with TemporaryDirectory(prefix="hswm-frontier-historical-") as temporary:
        temporary_root = Path(temporary)
        for row in bindings:
            if not isinstance(row, dict) or set(row) != {"path", "sha256", "source_commit"}:
                _fail("historical snapshot binding shape drift")
            path, binding_sha, binding_commit = row["path"], row["sha256"], row["source_commit"]
            if (not isinstance(path, str) or not isinstance(binding_sha, str) or
                    not isinstance(binding_commit, str) or binding_commit != commit or
                    COMMIT.fullmatch(binding_commit) is None):
                _fail("historical snapshot binding value drift")
            _safe_path(path, repo_root)
            key = (path, binding_sha)
            if key in observed:
                _fail("duplicate historical snapshot binding")
            observed.add(key)
            blob = _git_blob(repo_root, binding_commit, path)
            if sha256(blob).hexdigest() != binding_sha:
                _fail(f"historical source hash drift: {path}")
            target = temporary_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)
        if observed != expected:
            _fail("historical snapshot bindings do not exactly match ontology bindings")
        validate_data(data, temporary_root)
    return {"historical_source_commit": commit, "artifact_bindings": len(observed)}


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
        role = properties.get("standard_graph_role")
        if authority == "SECONDARY_AI":
            continue
        if authority != "USER_PRIMARY" or role != "USER_DIRECT_REQUEST":
            _fail("only explicit USER_PRIMARY direct-request records are allowed")
        sources = properties.get("source_paths")
        if not isinstance(sources, list) or not sources or not set(sources) <= bound_paths:
            _fail("USER_PRIMARY direct-request record must bind its source")


def _validate_relations(rows: object) -> None:
    if not isinstance(rows, list):
        _fail("relations must be a list")
    unknown = {
        row.get("type") if isinstance(row, dict) else type(row).__name__
        for row in rows
        if not isinstance(row, dict) or row.get("type") not in ALLOWED_RELATION_TYPES
    }
    if unknown:
        _fail(f"relation type is outside frontier allowlist: {sorted(unknown, key=str)}")


def validate_data(data: dict[str, Any], repo_root: Path = ROOT) -> None:
    """Fail closed on source, identity, authority, or relation-vocabulary drift."""

    keys = set(data)
    if keys != REQUIRED_TOP | (keys & OPTIONAL_TOP):
        _fail("ontology top-level shape drift")
    if data.get("schema_version") != SCHEMA_VERSION or data.get("bundle_uid") != BUNDLE_UID:
        _fail("ontology identity drift")
    if not isinstance(data.get("status"), str) or not isinstance(data.get("nonclaim"), str):
        _fail("ontology status and nonclaim must be text")
    bound_paths = _validate_bindings(data.get("artifact_bindings"), repo_root)
    _validate_authority(data, bound_paths)
    _validate_relations(data.get("relations"))
    validate_bundle_semantics(data)
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    KgBundleGraphView.from_bundles(
        sources=(KgBundleSource("frontier-learning-theory", raw, sha256(raw).hexdigest(), len(raw)),)
    )


def _view(raw: bytes) -> KgBundleGraphView:
    return KgBundleGraphView.from_bundles(
        sources=(KgBundleSource("frontier-learning-theory", raw, sha256(raw).hexdigest(), len(raw)),)
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
    parser.add_argument("--historical-snapshot", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.historical_snapshot and args.apply:
        raise SystemExit("--historical-snapshot cannot be combined with --apply")
    raw, data = _read_data(args.ontology)
    historical_report: dict[str, Any] | None = None
    if args.historical_snapshot:
        historical_report = validate_historical_snapshot(args.ontology, repo_root=args.repo_root)
    else:
        validate_data(data, args.repo_root)
    view = _view(raw)
    if args.export_dir is not None:
        report = _export(view, args.export_dir, args.additional_shapes)
        if not report["conforms"]:
            raise SystemExit("SHACL validation failed")
    artifact_sha256 = digest(args.ontology)
    if not args.apply:
        status = (
            "HISTORICAL_SNAPSHOT_VALIDATED_NOT_CURRENT_IMPLEMENTATION"
            if args.historical_snapshot else "VALIDATED_ONLY_NOT_PUBLISHED"
        )
        print(json.dumps({"status": status, "projection_sha256": artifact_sha256, "new_nodes": len(data["nodes"]), "relations": len(data["relations"]), **(historical_report or {})}, sort_keys=True))
        return
    if artifact_sha256 != REVIEWED_ARTIFACT_SHA256:
        raise SystemExit("reviewed artifact SHA pin is not installed or does not match")
    if args.source_config is None:
        raise SystemExit("--apply requires --source-config")
    result = gateway.publish(data, gateway.read_flat_yaml(args.source_config), artifact_sha256)
    print(json.dumps({**result, "status": "APPLIED_OR_VERIFIED_EXACT_PROJECTION", "projection_sha256": artifact_sha256}, sort_keys=True))


if __name__ == "__main__":
    main()
