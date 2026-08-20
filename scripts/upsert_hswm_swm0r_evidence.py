#!/usr/bin/env python3
"""Validate and explicitly publish the additive SWM-0R evidence bundle.

The default operation is local and read-only.  Remote mutation requires
``--apply`` and an explicit Neo4j source configuration.  Existing ontology
anchors are read only; this publisher never writes USER_PRIMARY nodes.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "hswm-swm0r-evidence-ontology/v1"
REGISTRY_UID = "sym:KG_INFRA:schema-registry-v1-2026-08-03"
ANCHOR_UID = "sym:ImplementationPlan:hswm-swm0-nary-witness"
BUNDLE_UID = "sym:AbstractNode:hswm-swm0r-evidence-bundle-2026-08-20"

SAFE_LABEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SAFE_RELATION = re.compile(r"[A-Z][A-Z0-9_]*")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
GIT_COMMIT_RE = re.compile(r"[0-9a-f]{40}")

FROZEN_LABELS = frozenset(
    {
        "AbstractNode",
        "Artifact",
        "Evidence",
        "Experiment",
        "ResearchArtifact",
        "Result",
    }
)
FROZEN_RELTYPES = frozenset(
    {
        "BINDS",
        "CONTAINS",
        "DERIVED_FROM",
        "EVIDENCE_FOR",
        "PRODUCED_BY",
        "REQUIRES",
        "TARGETS",
        "VALIDATES",
    }
)

PREREG_PATH = "prereg/PREREG_SWM0R_REPRESENTATION_CONFORMANCE_2026-08-20.json"
RAW_RESULT_PATH = "results/raw/swm0r_representation_conformance_2026-08-20.json"
RESULT_REPORT_PATH = "results/SWM0R_REPRESENTATION_CONFORMANCE_RESULTS_2026-08-20.md"
EVIDENCE_PATH = "evidence/EVIDENCE_SWM0R_REPRESENTATION_CONFORMANCE_2026-08-20.json"
PUBLISHER_PATH = "scripts/upsert_hswm_swm0r_evidence.py"
PUBLISHER_TEST_PATH = "tests/test_hswm_swm0r_ontology.py"
HUB_ONTOLOGY_PATH = (
    "ontology/identity/human_universal_body/"
    "HSWM_HUMAN_UNIVERSAL_BODY_ONTOLOGY.v1.json"
)

RUNTIME_PATHS = (
    "src/hswm/experiments/swm0_operator.py",
    "src/hswm/experiments/swm0_protocol.py",
    "src/hswm/experiments/swm0_worlds.py",
)
VERIFICATION_PATHS = (
    "tests/test_hswm_swm0_operator.py",
    "tests/test_hswm_swm0_protocol.py",
    "tests/test_hswm_swm0_worlds.py",
)
EXPECTED_BINDING_ROLES = {
    **{path: "RUNTIME_SOURCE" for path in RUNTIME_PATHS},
    **{path: "VERIFICATION_SOURCE" for path in VERIFICATION_PATHS},
    PREREG_PATH: "PREREGISTRATION",
    RAW_RESULT_PATH: "RAW_RESULT",
    RESULT_REPORT_PATH: "RESULT_REPORT",
    EVIDENCE_PATH: "EVIDENCE_RECEIPT",
    PUBLISHER_PATH: "KG_PUBLISHER",
    PUBLISHER_TEST_PATH: "KG_PUBLISHER_TEST",
}

SYSTEM_PROPERTY_KEYS = frozenset({"createdAt"})


class SWM0REvidenceError(ValueError):
    """Raised when the bundle, its artifacts, or remote readback is invalid."""


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SWM0REvidenceError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    """Load UTF-8 JSON while rejecting duplicate keys and non-object roots."""

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SWM0REvidenceError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise SWM0REvidenceError(f"JSON artifact must be an object: {path}")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise SWM0REvidenceError(f"{field} must be a lowercase SHA-256")
    return value


def _require_commit(value: Any, field: str) -> str:
    if not isinstance(value, str) or not GIT_COMMIT_RE.fullmatch(value):
        raise SWM0REvidenceError(f"{field} must be a full lowercase Git commit")
    return value


def _resolve_repo_file(repo_root: Path, relative: Any, field: str) -> tuple[str, Path]:
    if not isinstance(relative, str) or not relative:
        raise SWM0REvidenceError(f"{field} must be a non-empty repository path")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or relative != pure.as_posix() or any(
        part in {"", ".", ".."} for part in pure.parts
    ):
        raise SWM0REvidenceError(f"{field} is not a normalized repository path: {relative!r}")
    root = repo_root.resolve()
    candidate = repo_root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SWM0REvidenceError(f"{field} escapes or is missing: {relative}") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise SWM0REvidenceError(f"{field} must be a non-symlink regular file: {relative}")
    return relative, resolved


def _run_git(repo_root: Path, arguments: Sequence[str], *, text: bool = False) -> Any:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            check=True,
            capture_output=True,
            text=text,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SWM0REvidenceError(f"Git binding failed: {' '.join(arguments)}") from exc


def _head_commit(repo_root: Path) -> str:
    return _require_commit(
        _run_git(repo_root, ["rev-parse", "HEAD"], text=True).strip(),
        "HEAD",
    )


def _verify_tracked_head(repo_root: Path, relative: str, expected_sha256: str) -> None:
    _run_git(repo_root, ["ls-files", "--error-unmatch", "--", relative])
    head_bytes = _run_git(repo_root, ["show", f"HEAD:{relative}"])
    if sha256(head_bytes).hexdigest() != expected_sha256:
        raise SWM0REvidenceError(f"working artifact is not byte-identical to HEAD: {relative}")


def _verify_historical_binding(
    repo_root: Path,
    commit: str,
    relative: str,
    expected_sha256: str,
) -> None:
    historical = _run_git(repo_root, ["show", f"{commit}:{relative}"])
    if sha256(historical).hexdigest() != expected_sha256:
        raise SWM0REvidenceError(
            f"historical source hash mismatch at {commit}:{relative}"
        )


def read_flat_yaml(path: Path) -> dict[str, str]:
    """Read the flat Neo4j source config without exposing credentials."""

    config: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        config[key.strip()] = value.strip().strip('"').strip("'")
    required = {"uri", "user", "password", "database"}
    missing = required - config.keys()
    if missing:
        raise SWM0REvidenceError(f"source config is missing keys: {sorted(missing)}")
    return config


def _is_neo4j_property(value: Any) -> bool:
    scalar_types = (str, bool, int, float)
    if value is None:
        return False
    if isinstance(value, scalar_types):
        return True
    if not isinstance(value, list):
        return False
    if not value:
        return True
    first_type = type(value[0])
    return first_type in scalar_types and all(type(item) is first_type for item in value)


def _validate_internal_hashes(raw: dict[str, Any]) -> None:
    if raw.get("schema_version") != "hswm-swm0r-cli-bundle/v1":
        raise SWM0REvidenceError("unexpected SWM-0R raw-result schema")
    unsigned_bundle = dict(raw)
    bundle_digest = _require_sha256(unsigned_bundle.pop("bundle_sha256", None), "bundle_sha256")
    if canonical_sha256(unsigned_bundle) != bundle_digest:
        raise SWM0REvidenceError("raw-result bundle_sha256 mismatch")

    manifest = raw.get("manifest")
    result = raw.get("result")
    if not isinstance(manifest, dict) or not isinstance(result, dict):
        raise SWM0REvidenceError("raw result lacks manifest or result object")
    unsigned_manifest = dict(manifest)
    manifest_digest = _require_sha256(
        unsigned_manifest.pop("manifest_sha256", None), "manifest_sha256"
    )
    if canonical_sha256(unsigned_manifest) != manifest_digest:
        raise SWM0REvidenceError("manifest_sha256 mismatch")

    unsigned_result = dict(result)
    result_digest = _require_sha256(
        unsigned_result.pop("result_sha256", None), "result_sha256"
    )
    if canonical_sha256(unsigned_result) != result_digest:
        raise SWM0REvidenceError("result_sha256 mismatch")

    integrity = result.get("integrity")
    if not isinstance(integrity, dict):
        raise SWM0REvidenceError("result lacks integrity receipt")
    unsigned_integrity = dict(integrity)
    receipt_digest = _require_sha256(
        unsigned_integrity.pop("receipt_sha256", None), "integrity receipt_sha256"
    )
    if canonical_sha256(unsigned_integrity) != receipt_digest:
        raise SWM0REvidenceError("integrity receipt_sha256 mismatch")


def _binding_map(data: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    rows = data.get("artifact_bindings")
    if not isinstance(rows, list):
        raise SWM0REvidenceError("artifact_bindings must be a list")
    result: dict[str, dict[str, str]] = {}
    seen_roles: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SWM0REvidenceError(f"artifact binding {index} must be an object")
        path = row.get("path")
        role = row.get("role")
        digest = _require_sha256(row.get("sha256"), f"artifact binding {index} sha256")
        if not isinstance(path, str) or not isinstance(role, str):
            raise SWM0REvidenceError(f"artifact binding {index} has invalid path or role")
        if path in result or (role, path) in seen_roles:
            raise SWM0REvidenceError(f"duplicate artifact binding: {path}")
        result[path] = {"path": path, "role": role, "sha256": digest}
        seen_roles.add((role, path))
    if {path: row["role"] for path, row in result.items()} != EXPECTED_BINDING_ROLES:
        raise SWM0REvidenceError("artifact binding paths or roles differ from the frozen set")
    canonical_rows = sorted(result.values(), key=lambda row: (row["role"], row["path"]))
    expected_set_sha = _require_sha256(data.get("artifact_set_sha256"), "artifact_set_sha256")
    if canonical_sha256(canonical_rows) != expected_set_sha:
        raise SWM0REvidenceError("artifact_set_sha256 mismatch")
    return result


def _validate_local_anchor(data: Mapping[str, Any], repo_root: Path) -> None:
    anchors = data.get("anchors")
    if not isinstance(anchors, list) or len(anchors) != 1:
        raise SWM0REvidenceError("exactly one read-only SWM-0 anchor is required")
    anchor = anchors[0]
    expected = {
        "uid": ANCHOR_UID,
        "labels": ["Plan", "ImplementationPlan"],
        "properties": {
            "name": "SWM-0 — n-ary non-collapse witness",
            "authority_class": "SECONDARY_AI",
            "implementation_stage": "SWM-0",
        },
        "read_only": True,
    }
    if anchor != expected:
        raise SWM0REvidenceError("read-only SWM-0 anchor contract drift")

    hub = load_json(repo_root / HUB_ONTOLOGY_PATH)
    matches = [row for row in hub.get("nodes", []) if row.get("uid") == ANCHOR_UID]
    if len(matches) != 1:
        raise SWM0REvidenceError("local HUB ontology lacks one unique SWM-0 anchor")
    row = matches[0]
    if row.get("labels") != expected["labels"]:
        raise SWM0REvidenceError("local SWM-0 anchor labels drifted")
    properties = row.get("properties", {})
    for key, value in expected["properties"].items():
        if properties.get(key) != value:
            raise SWM0REvidenceError(f"local SWM-0 anchor property drift: {key}")


def _validate_cross_bindings(
    data: Mapping[str, Any],
    repo_root: Path,
    bindings: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    prereg = load_json(repo_root / PREREG_PATH)
    raw = load_json(repo_root / RAW_RESULT_PATH)
    evidence = load_json(repo_root / EVIDENCE_PATH)
    report_text = (repo_root / RESULT_REPORT_PATH).read_text(encoding="utf-8")
    _validate_internal_hashes(raw)

    if prereg.get("schema") != "hswm-swm0r-preregistration/v1":
        raise SWM0REvidenceError("unexpected preregistration schema")
    if evidence.get("schema") != "hswm-swm0r-evidence/v1":
        raise SWM0REvidenceError("unexpected evidence schema")
    if prereg.get("experiment") != "SWM-0R_REPRESENTATION_CONFORMANCE":
        raise SWM0REvidenceError("preregistration experiment drift")
    if evidence.get("experiment") != prereg["experiment"]:
        raise SWM0REvidenceError("evidence experiment drift")

    runtime_hashes = {path: bindings[path]["sha256"] for path in RUNTIME_PATHS}
    verification_hashes = {
        path: bindings[path]["sha256"] for path in VERIFICATION_PATHS
    }
    if set(prereg.get("source_paths", [])) != set(RUNTIME_PATHS):
        raise SWM0REvidenceError("preregistration runtime source paths drift")
    if prereg.get("source_sha256_at_registration") != runtime_hashes:
        raise SWM0REvidenceError("preregistration runtime source hashes drift")

    manifest = raw["manifest"]
    result = raw["result"]
    prereg_manifest = manifest.get("preregistration")
    if not isinstance(prereg_manifest, dict):
        raise SWM0REvidenceError("manifest lacks preregistration binding")
    source_commit = _require_commit(manifest.get("source_commit"), "source_commit")
    expected_prereg = bindings[PREREG_PATH]
    if prereg_manifest != {
        "commit": source_commit,
        "path": PREREG_PATH,
        "sha256": expected_prereg["sha256"],
    }:
        raise SWM0REvidenceError("manifest preregistration binding drift")
    expected_sources = {**runtime_hashes, PREREG_PATH: expected_prereg["sha256"]}
    if manifest.get("source_sha256") != expected_sources:
        raise SWM0REvidenceError("manifest source_sha256 map drift")

    evidence_bindings = evidence.get("artifact_bindings")
    if not isinstance(evidence_bindings, dict):
        raise SWM0REvidenceError("evidence lacks artifact_bindings")
    unsigned_evidence_bindings = dict(evidence_bindings)
    evidence_set_sha = _require_sha256(
        unsigned_evidence_bindings.pop("binding_set_sha256", None),
        "evidence binding_set_sha256",
    )
    if canonical_sha256(unsigned_evidence_bindings) != evidence_set_sha:
        raise SWM0REvidenceError("evidence binding_set_sha256 mismatch")
    if evidence_bindings.get("preregistration") != {
        "path": PREREG_PATH,
        "sha256": expected_prereg["sha256"],
    }:
        raise SWM0REvidenceError("evidence preregistration binding drift")
    if evidence_bindings.get("raw_result") != {
        "path": RAW_RESULT_PATH,
        "sha256": bindings[RAW_RESULT_PATH]["sha256"],
    }:
        raise SWM0REvidenceError("evidence raw-result binding drift")
    expected_runtime_rows = [
        {"path": path, "sha256": runtime_hashes[path]} for path in RUNTIME_PATHS
    ]
    expected_verification_rows = [
        {"path": path, "sha256": verification_hashes[path]}
        for path in VERIFICATION_PATHS
    ]
    if evidence_bindings.get("runtime_sources") != expected_runtime_rows:
        raise SWM0REvidenceError("evidence runtime-source bindings drift")
    if evidence_bindings.get("verification_sources") != expected_verification_rows:
        raise SWM0REvidenceError("evidence verification-source bindings drift")

    internal = data.get("internal_bindings")
    if not isinstance(internal, dict):
        raise SWM0REvidenceError("internal_bindings must be an object")
    integrity = result.get("integrity", {})
    expected_internal = {
        "evidence_binding_set_sha256": evidence_set_sha,
        "integrity_receipt_sha256": integrity.get("receipt_sha256"),
        "manifest_sha256": manifest.get("manifest_sha256"),
        "protocol_bundle_sha256": raw.get("bundle_sha256"),
        "result_sha256": result.get("result_sha256"),
        "source_commit": source_commit,
    }
    for key, value in expected_internal.items():
        if internal.get(key) != value:
            raise SWM0REvidenceError(f"internal binding drift: {key}")
        if key.endswith("sha256"):
            _require_sha256(value, key)

    evidence_internal = evidence.get("internal_digests")
    if evidence_internal != {
        "bundle_sha256": raw["bundle_sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
        "result_sha256": result["result_sha256"],
    }:
        raise SWM0REvidenceError("evidence internal digests drift")
    chronology = evidence.get("chronology", {})
    if chronology.get("measurement_source_commit") != source_commit or not all(
        chronology.get(key) is True
        for key in (
            "confirmatory_run_after_registration",
            "preregistration_and_sources_committed_before_run",
            "registered_source_and_preregistration_bytes_equal_measurement_HEAD",
        )
    ):
        raise SWM0REvidenceError("evidence chronology is not admissible")

    claim = evidence.get("claim", {})
    verdict = result.get("reduction", {}).get("verdict")
    if (
        verdict != evidence.get("result", {}).get("verdict")
        or result.get("scientific_status") != "UNJUDGED"
        or claim.get("scientific_status") != "UNJUDGED"
        or result.get("learned_operator_claim") is not False
        or claim.get("learned_operator_claim") is not False
        or result.get("next_gate") != "SWM-0W"
        or claim.get("next_gate") != "SWM-0W"
        or claim.get("scope") != "SWM-0R_REPRESENTATION_CONFORMANCE_ONLY"
    ):
        raise SWM0REvidenceError("SWM-0R claim boundary drift")
    if result.get("integrity", {}).get("passed") is not True:
        raise SWM0REvidenceError("raw result integrity did not pass")

    required_report_tokens = (
        "Scientific status: **`UNJUDGED`**",
        source_commit,
        expected_prereg["sha256"],
        bindings[RAW_RESULT_PATH]["sha256"],
        manifest["manifest_sha256"],
        result["result_sha256"],
        "not learned",
    )
    missing_report_tokens = [token for token in required_report_tokens if token not in report_text]
    if missing_report_tokens:
        raise SWM0REvidenceError(
            f"result report lacks bound claim tokens: {missing_report_tokens}"
        )

    for relative, digest in expected_sources.items():
        _verify_historical_binding(repo_root, source_commit, relative, digest)
    parent_commit = _require_commit(
        prereg.get("parent_commit_before_registration"),
        "parent_commit_before_registration",
    )
    actual_parent = _run_git(
        repo_root, ["rev-parse", f"{source_commit}^"], text=True
    ).strip()
    if actual_parent != parent_commit:
        raise SWM0REvidenceError("preregistration parent chronology drift")

    return {
        "evidence_binding_set_sha256": evidence_set_sha,
        "integrity_receipt_sha256": integrity["receipt_sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
        "protocol_bundle_sha256": raw["bundle_sha256"],
        "result_sha256": result["result_sha256"],
        "source_commit": source_commit,
        "verdict": verdict,
    }


def _verify_replay(
    repo_root: Path,
    source_commit: str,
    prereg_sha256: str,
    expected_path: Path,
) -> str:
    """Replay from the historical measurement commit in an isolated sparse clone."""

    command = [
        sys.executable,
        "-m",
        "hswm.experiments.swm0_protocol",
        "--mode",
        "confirmatory",
        "--prereg-path",
        PREREG_PATH,
        "--prereg-sha256",
        prereg_sha256,
    ]
    try:
        with tempfile.TemporaryDirectory(prefix="hswm-swm0r-replay-") as temporary:
            checkout = Path(temporary) / "repository"
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--shared",
                    "--no-checkout",
                    "--quiet",
                    str(repo_root),
                    str(checkout),
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(checkout), "sparse-checkout", "set", "src/hswm", "prereg"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(checkout), "checkout", "--detach", source_commit],
                check=True,
                capture_output=True,
            )
            environment = os.environ.copy()
            python_path = str(checkout / "src")
            if environment.get("PYTHONPATH"):
                python_path = f"{python_path}{os.pathsep}{environment['PYTHONPATH']}"
            environment["PYTHONPATH"] = python_path
            completed = subprocess.run(
                command,
                cwd=checkout,
                env=environment,
                check=True,
                capture_output=True,
            )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SWM0REvidenceError("deterministic SWM-0R replay failed") from exc
    expected = expected_path.read_bytes()
    if completed.stdout != expected:
        raise SWM0REvidenceError("deterministic SWM-0R replay bytes differ")
    return sha256(completed.stdout).hexdigest()


def _authority_scope(authority_class: str) -> str:
    if authority_class == "SECONDARY_AI":
        return "HSWM_SWM0R_ENGINEERING_EVIDENCE_2026_08_20"
    if authority_class == "SYSTEM_DERIVED":
        return "KG_PUBLICATION_DERIVATION"
    raise SWM0REvidenceError(f"forbidden authority class: {authority_class}")


def _expected_node_properties(
    row: Mapping[str, Any], bundle_file_sha256: str
) -> dict[str, Any]:
    logical = row["properties"]
    labels = set(row["labels"])
    authority = logical["authority_class"]
    if authority != "SECONDARY_AI":
        raise SWM0REvidenceError(f"new node is not SECONDARY_AI: {row['uid']}")
    upper_uid = (
        "sym:KG_KNOW:informationentity"
        if labels & {"Artifact", "Evidence", "ResearchArtifact", "Result"}
        else "sym:KG_KNOW:conceptualentity"
    )
    return {
        "uid": row["uid"],
        **logical,
        "ontology_bundle_uid": BUNDLE_UID,
        "ontology_bundle_file_sha256": bundle_file_sha256,
        "ontology_source_sha256": logical["source_sha256"],
        "ontology_kind_v1": logical["ontology_kind"],
        "ontology_plane_v1": logical["ontology_plane"],
        "ontology_domain_v1": logical["ontology_domain"],
        "ontology_upper_uid_v1": upper_uid,
        "ontology_semantic_roles_v1": logical.get("semantic_roles", []),
        "ontology_authority_class_v1": authority,
        "ontology_authority_scope_v1": _authority_scope(authority),
        "ontology_canonical_scope_v1": logical["canonical_scope"],
        "ontology_record_lifecycle_v1": logical["record_lifecycle"],
        "ontology_workflow_state_v1": "NOT_APPLICABLE",
        "ontology_epistemic_state_v1": logical["epistemic_state"],
        "ontology_review_required_v1": logical["review_required"],
    }


def _expected_relation_properties(row: Mapping[str, Any]) -> dict[str, Any]:
    authority = row["authority_class"]
    result = {
        "ontology_bundle_uid": BUNDLE_UID,
        "authority_class": authority,
        "authority": authority,
        "scope": _authority_scope(authority),
        "status": row["status"],
    }
    for key in ("claim_scope", "validation_scope"):
        if key in row:
            result[key] = row[key]
    return result


@dataclass(frozen=True)
class ValidatedBundle:
    data: dict[str, Any]
    ontology_path: Path
    bundle_file_sha256: str
    artifact_set_sha256: str
    artifact_hashes: tuple[tuple[str, str], ...]
    expected_nodes: Mapping[str, tuple[tuple[str, ...], Mapping[str, Any]]]
    expected_relations: tuple[Mapping[str, Any], ...]
    internal: Mapping[str, Any]
    replay_sha256: str
    head_commit: str


def validate_bundle(
    ontology_path: Path,
    repo_root: Path,
    *,
    require_tracked_head: bool = False,
    verify_replay: bool = True,
) -> ValidatedBundle:
    """Validate every local byte, internal digest, authority, and graph row."""

    repo_root = repo_root.resolve()
    ontology_path = ontology_path.resolve()
    try:
        ontology_relative = ontology_path.relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise SWM0REvidenceError("ontology bundle must live inside the repository") from exc
    data = load_json(ontology_path)
    if data.get("schema_version") != SCHEMA_VERSION:
        raise SWM0REvidenceError(f"unsupported schema_version: {data.get('schema_version')!r}")
    if data.get("bundle_uid") != BUNDLE_UID:
        raise SWM0REvidenceError("bundle_uid drift")
    _validate_local_anchor(data, repo_root)

    bindings = _binding_map(data)
    artifact_hashes: list[tuple[str, str]] = []
    for relative, row in sorted(bindings.items()):
        normalized, resolved = _resolve_repo_file(
            repo_root, relative, f"artifact binding {relative}"
        )
        observed = file_sha256(resolved)
        if observed != row["sha256"]:
            raise SWM0REvidenceError(
                f"artifact SHA-256 mismatch: {relative} expected={row['sha256']} actual={observed}"
            )
        artifact_hashes.append((normalized, observed))

    internal = _validate_cross_bindings(data, repo_root, bindings)
    bundle_file_digest = file_sha256(ontology_path)
    head_commit = _head_commit(repo_root)
    if require_tracked_head:
        for relative, digest in artifact_hashes:
            _verify_tracked_head(repo_root, relative, digest)
        _verify_tracked_head(repo_root, ontology_relative, bundle_file_digest)

    nodes = data.get("nodes")
    relations = data.get("relations")
    if not isinstance(nodes, list) or not nodes:
        raise SWM0REvidenceError("nodes must be a non-empty list")
    if not isinstance(relations, list) or not relations:
        raise SWM0REvidenceError("relations must be a non-empty list")
    node_uids = [row.get("uid") for row in nodes]
    anchor_uids = [row["uid"] for row in data["anchors"]]
    duplicates = [
        uid for uid, count in Counter(node_uids + anchor_uids).items() if count > 1
    ]
    if duplicates:
        raise SWM0REvidenceError(f"duplicate node or anchor UIDs: {duplicates}")
    if BUNDLE_UID not in node_uids:
        raise SWM0REvidenceError("bundle_uid must identify a new node")

    labels: set[str] = set()
    expected_nodes: dict[str, tuple[tuple[str, ...], Mapping[str, Any]]] = {}
    for row in nodes:
        if not isinstance(row, dict) or not isinstance(row.get("uid"), str):
            raise SWM0REvidenceError("node rows require string UIDs")
        row_labels = row.get("labels")
        properties = row.get("properties")
        if not isinstance(row_labels, list) or not row_labels:
            raise SWM0REvidenceError(f"node has invalid labels: {row['uid']}")
        if len(set(row_labels)) != len(row_labels):
            raise SWM0REvidenceError(f"node has duplicate labels: {row['uid']}")
        if not isinstance(properties, dict) or not properties.get("name"):
            raise SWM0REvidenceError(f"node has invalid properties: {row['uid']}")
        invalid = [key for key, value in properties.items() if not _is_neo4j_property(value)]
        if invalid:
            raise SWM0REvidenceError(
                f"node has unsupported Neo4j properties {row['uid']}: {sorted(invalid)}"
            )
        labels.update(row_labels)
        expected_nodes[row["uid"]] = (
            tuple(row_labels),
            _expected_node_properties(row, bundle_file_digest),
        )
    unsafe_labels = sorted(label for label in labels if not SAFE_LABEL.fullmatch(label))
    if unsafe_labels or not labels <= FROZEN_LABELS:
        invalid_labels = unsafe_labels or sorted(labels - FROZEN_LABELS)
        raise SWM0REvidenceError(
            f"labels are unsafe or outside frozen registry subset: {invalid_labels}"
        )

    known_uids = set(node_uids + anchor_uids)
    relation_keys: list[tuple[str, str, str]] = []
    relation_types: set[str] = set()
    expected_relations: list[Mapping[str, Any]] = []
    for row in relations:
        if not isinstance(row, dict):
            raise SWM0REvidenceError("relation rows must be objects")
        key = (row.get("from_uid"), row.get("type"), row.get("to_uid"))
        if not all(isinstance(item, str) for item in key):
            raise SWM0REvidenceError("relation endpoints and type must be strings")
        if key[0] not in known_uids or key[2] not in known_uids:
            raise SWM0REvidenceError(f"relation has unknown endpoint: {key}")
        if row.get("authority_class") not in {"SECONDARY_AI", "SYSTEM_DERIVED"}:
            raise SWM0REvidenceError(f"forbidden relation authority: {key}")
        relation_keys.append(key)
        relation_types.add(key[1])
        expected_relations.append(
            {
                "from_uid": key[0],
                "type": key[1],
                "to_uid": key[2],
                "properties": _expected_relation_properties(row),
            }
        )
    duplicate_relations = [
        key for key, count in Counter(relation_keys).items() if count > 1
    ]
    if duplicate_relations:
        raise SWM0REvidenceError(f"duplicate relations: {duplicate_relations}")
    unsafe_relations = sorted(
        relation for relation in relation_types if not SAFE_RELATION.fullmatch(relation)
    )
    if unsafe_relations or not relation_types <= FROZEN_RELTYPES:
        raise SWM0REvidenceError(
            "relations are unsafe or outside frozen registry subset: "
            f"{unsafe_relations or sorted(relation_types - FROZEN_RELTYPES)}"
        )

    replay_sha = (
        _verify_replay(
            repo_root,
            internal["source_commit"],
            bindings[PREREG_PATH]["sha256"],
            repo_root / RAW_RESULT_PATH,
        )
        if verify_replay
        else bindings[RAW_RESULT_PATH]["sha256"]
    )
    if replay_sha != bindings[RAW_RESULT_PATH]["sha256"]:
        raise SWM0REvidenceError("replay SHA-256 differs from bound raw result")

    return ValidatedBundle(
        data=data,
        ontology_path=ontology_path,
        bundle_file_sha256=bundle_file_digest,
        artifact_set_sha256=data["artifact_set_sha256"],
        artifact_hashes=tuple(artifact_hashes),
        expected_nodes=expected_nodes,
        expected_relations=tuple(expected_relations),
        internal=internal,
        replay_sha256=replay_sha,
        head_commit=head_commit,
    )


def _without_system_properties(properties: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in properties.items() if key not in SYSTEM_PROPERTY_KEYS}


def assert_exact_node(
    uid: str,
    expected_labels: Sequence[str],
    expected_properties: Mapping[str, Any],
    observed_labels: Sequence[str],
    observed_properties: Mapping[str, Any],
) -> None:
    """Reject ownership collisions and non-exact idempotent node states."""

    if set(observed_labels) != set(expected_labels):
        raise SWM0REvidenceError(f"node label collision or drift: {uid}")
    cleaned = _without_system_properties(observed_properties)
    if cleaned != dict(expected_properties):
        raise SWM0REvidenceError(f"node property collision or drift: {uid}")


def assert_exact_relation(
    key: tuple[str, str, str],
    expected_properties: Mapping[str, Any],
    observed_properties: Mapping[str, Any],
) -> None:
    """Reject relation hijacking and non-exact idempotent relation states."""

    cleaned = _without_system_properties(observed_properties)
    if cleaned != dict(expected_properties):
        raise SWM0REvidenceError(f"relationship collision or drift: {key}")


def _registry_and_anchor_readback(tx: Any, bundle: ValidatedBundle) -> None:
    registry = tx.run(
        "MATCH (r:SchemaRegistry {uid:$uid}) "
        "RETURN r.allowed_labels AS labels, r.allowed_reltypes AS relations",
        uid=REGISTRY_UID,
    ).single()
    if not registry:
        raise SWM0REvidenceError(f"KG schema registry not found: {REGISTRY_UID}")
    wanted_labels = {
        label for labels, _properties in bundle.expected_nodes.values() for label in labels
    }
    wanted_relations = {row["type"] for row in bundle.expected_relations}
    missing_labels = wanted_labels - set(registry["labels"] or [])
    missing_relations = wanted_relations - set(registry["relations"] or [])
    if missing_labels or missing_relations:
        raise SWM0REvidenceError(
            f"unregistered schema tokens: labels={sorted(missing_labels)}, "
            f"relations={sorted(missing_relations)}"
        )

    rows = tx.run(
        "MATCH (n {uid:$uid}) "
        "RETURN labels(n) AS labels, properties(n) AS properties, elementId(n) AS eid",
        uid=ANCHOR_UID,
    ).data()
    if len(rows) != 1:
        raise SWM0REvidenceError("remote SWM-0 anchor is missing or non-unique")
    row = rows[0]
    properties = row["properties"]
    if (
        set(row["labels"]) != {"Plan", "ImplementationPlan"}
        or properties.get("name") != "SWM-0 — n-ary non-collapse witness"
        or properties.get("ontology_authority_class_v1") != "SECONDARY_AI"
        or properties.get("implementation_stage") != "SWM-0"
    ):
        raise SWM0REvidenceError("remote read-only SWM-0 anchor drift")


def _node_rows(tx: Any, uids: Sequence[str]) -> list[dict[str, Any]]:
    return tx.run(
        "MATCH (n) WHERE n.uid IN $uids "
        "RETURN n.uid AS uid, labels(n) AS labels, properties(n) AS properties, "
        "elementId(n) AS eid",
        uids=list(uids),
    ).data()


def _relation_rows(tx: Any, row: Mapping[str, Any]) -> list[dict[str, Any]]:
    relation_type = row["type"]
    if not SAFE_RELATION.fullmatch(relation_type):
        raise SWM0REvidenceError(f"unsafe relationship type: {relation_type}")
    return tx.run(
        "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
        f"MATCH (a)-[r:{relation_type}]->(b) "
        "RETURN properties(r) AS properties, elementId(r) AS eid",
        from_uid=row["from_uid"],
        to_uid=row["to_uid"],
    ).data()


def _exact_remote_readback(tx: Any, bundle: ValidatedBundle) -> dict[str, int]:
    node_rows = _node_rows(tx, list(bundle.expected_nodes))
    counts = Counter(row["uid"] for row in node_rows)
    if set(counts) != set(bundle.expected_nodes) or any(count != 1 for count in counts.values()):
        raise SWM0REvidenceError(f"exact node readback mismatch: {dict(counts)}")
    for row in node_rows:
        labels, properties = bundle.expected_nodes[row["uid"]]
        assert_exact_node(
            row["uid"], labels, properties, row["labels"], row["properties"]
        )

    relation_count = 0
    for relation in bundle.expected_relations:
        rows = _relation_rows(tx, relation)
        key = (relation["from_uid"], relation["type"], relation["to_uid"])
        if len(rows) != 1:
            raise SWM0REvidenceError(f"exact relationship readback mismatch: {key}")
        assert_exact_relation(key, relation["properties"], rows[0]["properties"])
        relation_count += 1

    owned_nodes = tx.run(
        "MATCH (n {ontology_bundle_uid:$bundle_uid}) RETURN count(n) AS count",
        bundle_uid=BUNDLE_UID,
    ).single()["count"]
    owned_relations = tx.run(
        "MATCH ()-[r {ontology_bundle_uid:$bundle_uid}]->() RETURN count(r) AS count",
        bundle_uid=BUNDLE_UID,
    ).single()["count"]
    if owned_nodes != len(bundle.expected_nodes) or owned_relations != relation_count:
        raise SWM0REvidenceError(
            "bundle ownership count drift: "
            f"nodes={owned_nodes} relations={owned_relations}"
        )
    return {"readback_nodes": owned_nodes, "readback_relations": owned_relations}


def _publish_transaction(tx: Any, bundle: ValidatedBundle) -> dict[str, int]:
    _registry_and_anchor_readback(tx, bundle)
    existing_rows = _node_rows(tx, list(bundle.expected_nodes))
    counts = Counter(row["uid"] for row in existing_rows)
    duplicates = {uid: count for uid, count in counts.items() if count > 1}
    if duplicates:
        raise SWM0REvidenceError(f"duplicate remote KG UIDs: {duplicates}")
    existing = {row["uid"]: row for row in existing_rows}
    for uid, row in existing.items():
        labels, properties = bundle.expected_nodes[uid]
        assert_exact_node(uid, labels, properties, row["labels"], row["properties"])

    relation_existing: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for relation in bundle.expected_relations:
        key = (relation["from_uid"], relation["type"], relation["to_uid"])
        rows = _relation_rows(tx, relation)
        if len(rows) > 1:
            raise SWM0REvidenceError(f"duplicate existing relationship: {key}")
        if rows:
            assert_exact_relation(key, relation["properties"], rows[0]["properties"])
        relation_existing[key] = rows

    created_nodes = 0
    for uid, (labels, properties) in bundle.expected_nodes.items():
        if uid in existing:
            continue
        label_clause = ":".join(labels)
        tx.run(
            f"CREATE (n:{label_clause}) "
            "SET n=$properties, n.createdAt=datetime() RETURN elementId(n) AS eid",
            properties=dict(properties),
        ).single()
        created_nodes += 1

    created_relations = 0
    for relation in bundle.expected_relations:
        key = (relation["from_uid"], relation["type"], relation["to_uid"])
        if relation_existing[key]:
            continue
        tx.run(
            "MATCH (a {uid:$from_uid}), (b {uid:$to_uid}) "
            f"CREATE (a)-[r:{relation['type']}]->(b) "
            "SET r=$properties, r.createdAt=datetime() RETURN elementId(r) AS eid",
            from_uid=relation["from_uid"],
            to_uid=relation["to_uid"],
            properties=dict(relation["properties"]),
        ).single()
        created_relations += 1

    _exact_remote_readback(tx, bundle)
    return {
        "created_nodes": created_nodes,
        "created_relations": created_relations,
        "existing_nodes": len(bundle.expected_nodes) - created_nodes,
        "existing_relations": len(bundle.expected_relations) - created_relations,
    }


def _connect(config: Mapping[str, str]) -> Any:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:  # pragma: no cover
        raise SWM0REvidenceError("remote access requires the optional kg dependency") from exc
    driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))
    driver.verify_connectivity()
    return driver


def publish(bundle: ValidatedBundle, config: Mapping[str, str]) -> dict[str, int]:
    """Create missing owned rows, then read back from a new post-commit session."""

    driver = _connect(config)
    try:
        with driver.session(database=config["database"]) as write_session:
            write_result = write_session.execute_write(_publish_transaction, bundle)
        with driver.session(database=config["database"]) as read_session:
            read_result = read_session.execute_read(_exact_remote_readback, bundle)
        return {**write_result, **read_result}
    finally:
        driver.close()


def readback(bundle: ValidatedBundle, config: Mapping[str, str]) -> dict[str, int]:
    """Perform a registry/anchor check and exact read-only bundle readback."""

    driver = _connect(config)
    try:
        with driver.session(database=config["database"]) as session:
            def operation(tx: Any) -> dict[str, int]:
                _registry_and_anchor_readback(tx, bundle)
                return _exact_remote_readback(tx, bundle)

            return session.execute_read(operation)
    finally:
        driver.close()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ontology",
        type=Path,
        default=repo_root
        / "ontology"
        / "identity"
        / "human_universal_body"
        / "HSWM_SWM0R_EVIDENCE_BUNDLE.v1.json",
    )
    parser.add_argument("--source-config", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--readback-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    require_tracked = args.apply or args.readback_only
    bundle = validate_bundle(
        args.ontology,
        repo_root,
        require_tracked_head=require_tracked,
        verify_replay=True,
    )
    base = {
        "artifact_set_sha256": bundle.artifact_set_sha256,
        "artifacts": len(bundle.artifact_hashes),
        "bundle_file_sha256": bundle.bundle_file_sha256,
        "head_commit": bundle.head_commit,
        "manifest_sha256": bundle.internal["manifest_sha256"],
        "nodes": len(bundle.expected_nodes),
        "relations": len(bundle.expected_relations),
        "replay_sha256": bundle.replay_sha256,
        "result_sha256": bundle.internal["result_sha256"],
        "scientific_status": "UNJUDGED",
        "verdict": bundle.internal["verdict"],
    }
    if not args.apply and not args.readback_only:
        print(json.dumps({**base, "status": "VALIDATED_ONLY"}, sort_keys=True))
        return 0
    if args.source_config is None:
        raise SystemExit("--apply/--readback-only requires --source-config")
    config = read_flat_yaml(args.source_config.expanduser())
    if args.readback_only:
        result = readback(bundle, config)
        status = "EXACT_READBACK_VERIFIED"
    else:
        result = publish(bundle, config)
        status = "APPLIED_AND_POSTCOMMIT_READ_BACK"
    print(json.dumps({**base, **result, "status": status}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ANCHOR_UID",
    "BUNDLE_UID",
    "FROZEN_LABELS",
    "FROZEN_RELTYPES",
    "REGISTRY_UID",
    "SCHEMA_VERSION",
    "SWM0REvidenceError",
    "ValidatedBundle",
    "assert_exact_node",
    "assert_exact_relation",
    "canonical_sha256",
    "file_sha256",
    "load_json",
    "main",
    "readback",
    "validate_bundle",
]
