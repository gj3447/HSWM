"""Read-only, parallel anchor-revision checks for modern KG bundle inputs.

This is a publication preflight helper.  It never alters an anchor contract or
publishes anything.  A source bundle can bind an anchor revision only when its
own artifact bindings name an ontology JSON which owns that anchor.  Other
anchors are reported as explicitly unpinned, rather than being mistaken for a
full revision pin.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


def _fail(message: str) -> None:
    raise ValueError(message)


def _safe_bound_file(repo_root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        _fail("artifact binding path must be non-empty text")
    candidate = (repo_root / relative).resolve()
    root = repo_root.resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        _fail("anchor revision binding path is not a regular repository file")
    return candidate


def _raw_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _bound_ontology_candidates(data: Mapping[str, Any], repo_root: Path) -> list[tuple[Path, str]]:
    bindings = data.get("artifact_bindings")
    if bindings is None:
        return []
    if not isinstance(bindings, list):
        _fail("artifact_bindings must be a list when present")
    candidates: list[tuple[Path, str]] = []
    for row in bindings:
        if not isinstance(row, Mapping) or set(row) != {"path", "sha256"}:
            _fail("artifact binding shape is invalid")
        relative, declared_sha = row["path"], row["sha256"]
        if not isinstance(declared_sha, str) or len(declared_sha) != 64:
            _fail("artifact binding sha256 is invalid")
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            _fail("anchor revision binding path is not a regular repository file")
        # Only ontology JSON can establish node ownership.  Do not make old
        # source code or ordinary documents part of an anchor revision check.
        if not relative.startswith("ontology/") or not relative.endswith(".json"):
            continue
        path = _safe_bound_file(repo_root, relative)
        candidates.append((path, declared_sha))
    return candidates


def _load_owner(path: Path) -> tuple[dict[str, Any], set[str]]:
    try:
        payload = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"bound ontology is not JSON: {path}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("bundle_uid"), str):
        _fail(f"bound ontology has no bundle_uid: {path}")
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        _fail(f"bound ontology has no nodes: {path}")
    owned = {
        row["uid"] for row in nodes
        if isinstance(row, Mapping) and isinstance(row.get("uid"), str)
    }
    return payload, owned


def build_bound_anchor_revisions(
    data: Mapping[str, Any], repo_root: Path
) -> dict[str, dict[str, str]]:
    """Describe what this source revision can prove about each anchor.

    Modern candidates carry the raw JSON digest which the generic publisher
    writes as ``ontology_projection_sha256``.  Legacy candidates are checked
    only by their declared bundle identity because their dedicated publisher
    uses a different property contract.
    """

    anchors = data.get("anchors")
    if not isinstance(anchors, list):
        _fail("anchors must be a list")
    anchor_uids = []
    for anchor in anchors:
        if not isinstance(anchor, Mapping) or not isinstance(anchor.get("uid"), str):
            _fail("anchor uid is invalid")
        anchor_uids.append(anchor["uid"])
    if len(anchor_uids) != len(set(anchor_uids)):
        _fail("duplicate anchor uid")

    owners: dict[str, list[tuple[dict[str, Any], str, Path]]] = {uid: [] for uid in anchor_uids}
    for path, declared_sha in _bound_ontology_candidates(data, repo_root):
        raw_sha = _raw_sha(path)
        payload, node_uids = _load_owner(path)
        matched = set(anchor_uids) & node_uids
        # A historical source may bind another JSON for context.  It is not an
        # anchor revision dependency unless it owns one of this bundle's
        # anchors, so its hash drift must not block this preflight.
        if not matched:
            continue
        if raw_sha != declared_sha:
            _fail(f"anchor revision binding hash drift: {path.relative_to(repo_root.resolve())}")
        for uid in matched:
            owners[uid].append((payload, raw_sha, path))

    result: dict[str, dict[str, str]] = {}
    for uid in anchor_uids:
        matches = owners[uid]
        if not matches:
            result[uid] = {"pin_status": "UNPINNED_NO_BOUND_OWNER"}
            continue
        if len(matches) != 1:
            _fail(f"anchor has multiple bound ontology owners: {uid}")
        payload, raw_sha, path = matches[0]
        if "artifact_bindings" in payload:
            result[uid] = {
                "pin_status": "PINNED_MODERN_RAW_BUNDLE_DIGEST",
                "path": path.relative_to(repo_root.resolve()).as_posix(),
                "ontology_bundle_uid": payload["bundle_uid"],
                "ontology_projection_sha256": raw_sha,
            }
        else:
            result[uid] = {
                "pin_status": "PINNED_LEGACY_IDENTITY_ONLY",
                "path": path.relative_to(repo_root.resolve()).as_posix(),
                "ontology_bundle_uid": payload["bundle_uid"],
            }
    return result


def validate_bound_anchor_revisions(
    tx: Any, data: Mapping[str, Any], repo_root: Path
) -> dict[str, Any]:
    """Fail closed on a stale or wrongly owned *pinned* live anchor.

    Unpinned anchors remain visible in the report.  They are not silently
    treated as revision-bound, and this function does not infer a missing
    source file or a historical publisher digest.
    """

    revisions = build_bound_anchor_revisions(data, repo_root)
    checked = 0
    unpinned: list[str] = []
    legacy: list[str] = []
    for uid, expected in revisions.items():
        status = expected["pin_status"]
        if status == "UNPINNED_NO_BOUND_OWNER":
            unpinned.append(uid)
            continue
        rows = tx.run(
            "MATCH (n {uid:$uid}) RETURN n.uid AS uid, properties(n) AS properties",
            uid=uid,
        ).data()
        if len(rows) != 1:
            raise RuntimeError(f"anchor revision remote UID mismatch: {uid}")
        properties = rows[0].get("properties")
        if not isinstance(properties, Mapping):
            raise RuntimeError(f"anchor revision remote properties are invalid: {uid}")
        if properties.get("ontology_bundle_uid") != expected["ontology_bundle_uid"]:
            raise RuntimeError(f"anchor revision bundle drift: {uid}")
        if status == "PINNED_MODERN_RAW_BUNDLE_DIGEST":
            if properties.get("ontology_projection_sha256") != expected["ontology_projection_sha256"]:
                raise RuntimeError(f"anchor revision projection digest drift: {uid}")
        else:
            legacy.append(uid)
        checked += 1
    return {
        "checked_pinned_anchors": checked,
        "legacy_identity_only_anchors": tuple(legacy),
        "unpinned_anchors": tuple(unpinned),
        "anchor_revisions": revisions,
    }
