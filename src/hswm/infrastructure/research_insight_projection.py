"""Fail-closed publisher for the fixed 2026-09-06 research-insight projection."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from scripts import upsert_hswm_graph_and_loop_engineering as gateway

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT = Path("ontology/identity/hswm_core/HSWM_RESEARCH_INSIGHTS_2026-09-06.v1.json")
BUNDLE_UID = "sym:AbstractNode:hswm-research-insights-2026-09-06-v1"
EXPECTED_FILE_SHA256 = "b295e2dd367d3510d3016bf06e2197a3675eaf105bbf38372cb676bdd4dc8193"
LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
RELATION = re.compile(r"[A-Z_][A-Z0-9_]*\Z")
UID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]*\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
ROLES = {
    "bundle",
    "source",
    "observation",
    "interpretation",
    "hypothesis",
    "proposed_rule",
    "experiment",
    "status_reading",
}
PROSPECTIVE = {"hypothesis", "proposed_rule", "experiment"}
REQUIRED = {
    "schema_version", "bundle_uid", "status", "authority_boundary", "nonclaim",
    "source_commit", "artifact_bindings", "expected_counts", "anchors", "nodes",
    "relations",
}
BASE = {
    "name", "description", "authority_class", "epistemic_status",
    "record_lifecycle", "sensitivity", "claim_boundary", "semantic_roles",
    "insight_id", "source_paths",
}


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _fail(message: str) -> None:
    raise ValueError(message)


def _safe_path(value: object, root: Path) -> Path:
    if not isinstance(value, str) or not value:
        _fail("artifact binding path is not a normalized repo-relative path")
    relative = Path(value)
    if relative.is_absolute() or relative.as_posix() != value or any(part in {".", ".."} for part in relative.parts):
        _fail("artifact binding path is not a normalized repo-relative path")
    root = root.resolve()
    candidate = root / relative
    for current in (candidate, *candidate.parents):
        if current.is_symlink():
            _fail("artifact binding may not traverse a symlink")
        if current == root:
            break
    path = candidate.resolve()
    if root not in path.parents or not path.is_file() or path.is_symlink():
        _fail("artifact binding path is not a regular repository file")
    return path


def _validate_top(data: dict[str, Any]) -> None:
    if (
        set(data) != REQUIRED
        or data["schema_version"] != "hswm-research-insights/v1"
        or data["bundle_uid"] != BUNDLE_UID
    ):
        _fail("projection identity drift")
    if (
        not isinstance(data["authority_boundary"], str)
        or "SECONDARY_AI" not in data["authority_boundary"]
        or not isinstance(data["status"], str)
        or not data["status"]
        or not isinstance(data["nonclaim"], str)
        or not data["nonclaim"]
        or not isinstance(data["source_commit"], str)
        or not COMMIT.fullmatch(data["source_commit"])
    ):
        _fail("projection authority or source commit drift")


def _validate_bindings(rows: object, root: Path) -> set[str]:
    if not isinstance(rows, list) or not rows:
        _fail("missing artifact bindings")
    bound: set[str] = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"path", "sha256"}
            or not isinstance(row["sha256"], str)
            or not SHA256.fullmatch(row["sha256"])
        ):
            _fail("invalid artifact binding")
        path = _safe_path(row["path"], root)
        if digest(path) != row["sha256"]:
            _fail("artifact binding hash drift")
        if row["path"] in bound:
            _fail("duplicate artifact binding")
        bound.add(row["path"])
    return bound


def _validate_anchor(anchor: object) -> str:
    if not isinstance(anchor, dict) or set(anchor) != {"uid", "name", "required_labels"}:
        _fail("unsafe anchor")
    labels = anchor["required_labels"]
    if (
        not isinstance(anchor["uid"], str)
        or not UID.fullmatch(anchor["uid"])
        or not isinstance(anchor["name"], str)
        or not anchor["name"]
        or not isinstance(labels, list)
        or not labels
        or any(not isinstance(label, str) or not LABEL.fullmatch(label) for label in labels)
    ):
        _fail("unsafe anchor")
    return anchor["uid"]


def _validate_nodes(nodes: list[object], bound: set[str]) -> tuple[list[str], dict[str, str]]:
    uids: list[str] = []
    roles: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict) or set(node) != {"uid", "labels", "properties"}:
            _fail("unsafe node")
        labels = node["labels"]
        if (
            not isinstance(node["uid"], str)
            or not UID.fullmatch(node["uid"])
            or not isinstance(labels, list)
            or not labels
            or len(labels) != len(set(labels))
            or any(not isinstance(label, str) or not LABEL.fullmatch(label) for label in labels)
        ):
            _fail("unsafe node")
        properties = node["properties"]
        if not isinstance(properties, dict) or not BASE <= set(properties):
            _fail("invalid owned-node provenance")
        if any(not isinstance(key, str) or not gateway._neo4j_property(value) for key, value in properties.items()):
            _fail("invalid owned-node provenance")
        role_list = properties["semantic_roles"]
        if (
            properties["authority_class"] != "SECONDARY_AI"
            or properties["record_lifecycle"] != "ACTIVE"
            or properties["sensitivity"] != "non_secret"
            or not isinstance(properties["name"], str)
            or not properties["name"]
            or not isinstance(properties["description"], str)
            or not properties["description"]
            or not isinstance(properties["claim_boundary"], str)
            or not properties["claim_boundary"]
            or not isinstance(role_list, list)
            or len(role_list) != 1
            or role_list[0] not in ROLES
            or not isinstance(properties["source_paths"], list)
        ):
            _fail("invalid owned-node provenance")
        role = role_list[0]
        sources = properties["source_paths"]
        if role != "bundle" and (not sources or not set(sources) <= bound):
            _fail("unbound insight source")
        expected = "PROPOSED_UNTESTED" if role in PROSPECTIVE else "DERIVED_SOURCE_READING"
        if properties["epistemic_status"] != expected:
            _fail("prospective status drift" if role in PROSPECTIVE else "derived status drift")
        uids.append(node["uid"])
        roles[node["uid"]] = role
    return uids, roles


def _validate_relations(relations: list[object], all_uids: set[str], roles: dict[str, str]) -> None:
    tested = {uid: False for uid, role in roles.items() if role == "hypothesis"}
    rule_from = {uid: False for uid, role in roles.items() if role == "proposed_rule"}
    rule_to = {uid: False for uid, role in roles.items() if role == "proposed_rule"}
    seen: set[tuple[object, object, object]] = set()
    for relation in relations:
        if not isinstance(relation, dict):
            _fail("unsafe relation")
        key = (relation.get("from_uid"), relation.get("type"), relation.get("to_uid"))
        if (
            key in seen
            or set(relation) != {"from_uid", "type", "to_uid", "authority_class", "scope", "status"}
            or relation["from_uid"] not in all_uids
            or relation["to_uid"] not in all_uids
            or not isinstance(relation["type"], str)
            or not RELATION.fullmatch(relation["type"])
            or relation["authority_class"] != "SECONDARY_AI"
            or relation["status"] != "PROJECTION_ONLY"
        ):
            _fail("unsafe relation")
        seen.add(key)
        if (
            relation["type"] == "TESTS"
            and roles.get(relation["from_uid"]) == "experiment"
            and roles.get(relation["to_uid"]) == "hypothesis"
        ):
            tested[relation["to_uid"]] = True
        if relation["type"] == "DERIVED_FROM" and relation["from_uid"] in rule_from and roles.get(relation["to_uid"]) in {"observation", "interpretation"}:
            rule_from[relation["from_uid"]] = True
        if relation["type"] == "MOTIVATES" and relation["from_uid"] in rule_to and roles.get(relation["to_uid"]) == "experiment":
            rule_to[relation["from_uid"]] = True
    if not all(tested.values()) or not all(rule_from.values()) or not all(rule_to.values()):
        _fail("required hypothesis/rule links missing")


def validate_data(data: dict[str, Any], repo_root: Path = ROOT) -> None:
    _validate_top(data)
    bound = _validate_bindings(data["artifact_bindings"], repo_root)
    anchors, nodes, relations = data["anchors"], data["nodes"], data["relations"]
    if not all(isinstance(value, list) for value in (anchors, nodes, relations)):
        _fail("graph arrays required")
    if data["expected_counts"] != {"nodes": len(nodes), "anchors": len(anchors), "relations": len(relations)}:
        _fail("count drift")
    anchor_uids = [_validate_anchor(anchor) for anchor in anchors]
    node_uids, roles = _validate_nodes(nodes, bound)
    uids = [*anchor_uids, *node_uids]
    if any(count > 1 for count in Counter(uids).values()):
        _fail("duplicate uid")
    _validate_relations(relations, set(uids), roles)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ontology", type=Path, default=ROOT / DEFAULT_ARTIFACT)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--source-config", type=Path)
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    data = json.loads(arguments.ontology.read_text())
    validate_data(data, arguments.repo_root)
    artifact_sha256 = digest(arguments.ontology)
    if not arguments.apply:
        print(json.dumps({"status": "VALIDATED_ONLY_NOT_PUBLISHED", "projection_sha256": artifact_sha256, "new_nodes": len(data["nodes"]), "relations": len(data["relations"])}, sort_keys=True))
        return
    if artifact_sha256 != EXPECTED_FILE_SHA256:
        raise SystemExit("reviewed artifact SHA pin is not installed")
    if arguments.source_config is None:
        raise SystemExit("--apply requires --source-config")
    published = gateway.publish(data, gateway.read_flat_yaml(arguments.source_config), artifact_sha256)
    print(json.dumps({**published, "status": "APPLIED_OR_VERIFIED_EXACT_PROJECTION", "projection_sha256": artifact_sha256}, sort_keys=True))


if __name__ == "__main__":
    main()
