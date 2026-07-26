#!/usr/bin/env python3
"""Fail-closed validator for the machine-readable HSWM research ledger.

The validator intentionally uses only the Python standard library.  The JSON
Schema is the interchange contract; this module enforces the safety and
scientific-promotion rules that JSON Schema alone cannot express.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "hswm-research-ledger/v1"
ALLOWED_STATES = {
    "planned",
    "running",
    "engineering_validated",
    "exploratory_supported",
    "exploratory_refuted",
    "partial",
    "progressive",
    "canonical",
    "abandoned",
}
PROMOTED_STATES = {"progressive", "canonical"}
REF_LIST_FIELDS = (
    "prereg_refs",
    "source_refs",
    "evidence_refs",
    "judge_refs",
    "lakato_refs",
)
REF_KINDS = {
    "preregistration",
    "source",
    "evidence_receipt",
    "judge_receipt",
    "lakatotree_readback",
}
AVAILABILITY = {"present", "remote", "external_unverified"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
URI_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


class LedgerValidationError(ValueError):
    """Raised when a ledger cannot safely be treated as authoritative."""


def _fail(message: str) -> None:
    raise LedgerValidationError(message)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} must be an object")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"{field} must be an array")
    return value


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")
    return value


def _identifier(value: Any, field: str) -> str:
    text = _nonempty_string(value, field)
    if not IDENTIFIER_RE.fullmatch(text):
        _fail(f"{field} is not a safe identifier: {text!r}")
    return text


def _require_fields(obj: Mapping[str, Any], fields: Iterable[str], context: str) -> None:
    missing = [field for field in fields if field not in obj]
    if missing:
        _fail(f"{context} missing required fields: {', '.join(missing)}")


def _unique_ids(items: list[Any], id_field: str, context: str) -> None:
    identifiers: list[str] = []
    for index, raw in enumerate(items):
        item = _mapping(raw, f"{context}[{index}]")
        identifiers.append(_identifier(item.get(id_field), f"{context}[{index}].{id_field}"))
    duplicates = sorted(
        identifier for identifier, count in Counter(identifiers).items() if count > 1
    )
    if duplicates:
        _fail(f"duplicate {id_field} values in {context}: {duplicates}")


def _safe_relative_path(raw: Any, field: str) -> str:
    text = _nonempty_string(raw, field)
    if URI_RE.match(text):
        _fail(f"{field} must be a repository-relative path, not a URI: {text!r}")
    path = PurePosixPath(text)
    if path.is_absolute() or text.startswith(("~", "\\")):
        _fail(f"unsafe absolute active root in {field}: {text!r}")
    if any(part in {"..", ""} for part in path.parts):
        _fail(f"unsafe traversal in {field}: {text!r}")
    return text


def _artifact_path_kind(raw: str, field: str) -> str:
    if URI_RE.match(raw):
        return "uri"
    path = PurePosixPath(raw)
    if path.is_absolute() or raw.startswith(("~", "\\")):
        _fail(f"unsafe absolute artifact path in {field}: {raw!r}")
    if any(part in {"..", ""} for part in path.parts):
        _fail(f"unsafe traversal in artifact path {field}: {raw!r}")
    return "relative"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_artifact_ref(
    raw: Any,
    *,
    context: str,
    repo_root: Path,
    verify_files: bool,
) -> None:
    ref = _mapping(raw, context)
    _require_fields(
        ref,
        (
            "artifact_id",
            "kind",
            "path",
            "sha256",
            "availability",
            "claim_boundary",
        ),
        context,
    )
    _identifier(ref["artifact_id"], f"{context}.artifact_id")
    kind = _nonempty_string(ref["kind"], f"{context}.kind")
    if kind not in REF_KINDS:
        _fail(f"{context}.kind has unknown value: {kind!r}")
    availability = _nonempty_string(ref["availability"], f"{context}.availability")
    if availability not in AVAILABILITY:
        _fail(f"{context}.availability has unknown value: {availability!r}")
    expected_hash = _nonempty_string(ref["sha256"], f"{context}.sha256")
    if not SHA256_RE.fullmatch(expected_hash):
        _fail(f"{context}.sha256 must be a lowercase SHA-256 digest")
    _nonempty_string(ref["claim_boundary"], f"{context}.claim_boundary")

    raw_path = _nonempty_string(ref["path"], f"{context}.path")
    path_kind = _artifact_path_kind(raw_path, f"{context}.path")
    if availability == "present" and path_kind != "relative":
        _fail(f"{context} claims present but does not use a repository-relative path")
    if path_kind == "relative" and availability != "present":
        _fail(f"{context} is repository-relative but is not marked present")
    if not verify_files or availability != "present":
        return

    path = repo_root / raw_path
    if not path.is_file():
        _fail(f"{context} claims a missing local artifact: {raw_path}")
    actual_hash = _sha256(path)
    if actual_hash != expected_hash:
        _fail(
            f"{context} SHA-256 drift: expected={expected_hash} actual={actual_hash} "
            f"path={raw_path}"
        )


def _validate_tree_topology(ledger: Mapping[str, Any]) -> None:
    active = _mapping(ledger.get("active_tree"), "active_tree")
    _require_fields(
        active,
        ("tree_id", "status", "authority_uri", "host_role", "claim_boundary"),
        "active_tree",
    )
    _identifier(active["tree_id"], "active_tree.tree_id")
    predecessors = _list(ledger.get("predecessor_trees"), "predecessor_trees")

    all_trees = [active, *[_mapping(item, "predecessor_trees[]") for item in predecessors]]
    active_count = sum(tree.get("status") == "ACTIVE" for tree in all_trees)
    if active_count != 1:
        _fail(f"exactly one ACTIVE research tree is required; found {active_count}")
    if active.get("status") != "ACTIVE":
        _fail("active_tree.status must be ACTIVE")
    if active.get("host_role") != "ADJUDICATION_AND_RECORD":
        _fail("active_tree.host_role must be ADJUDICATION_AND_RECORD")
    _nonempty_string(active["authority_uri"], "active_tree.authority_uri")
    _nonempty_string(active["claim_boundary"], "active_tree.claim_boundary")

    for index, predecessor in enumerate(predecessors):
        tree = _mapping(predecessor, f"predecessor_trees[{index}]")
        _require_fields(
            tree,
            ("tree_id", "status", "relation", "mutation_policy", "notes"),
            f"predecessor_trees[{index}]",
        )
        if tree.get("status") != "PREDECESSOR":
            _fail(f"predecessor_trees[{index}].status must be PREDECESSOR")
        if tree.get("relation") != "LINEAGE_ONLY":
            _fail(f"predecessor_trees[{index}].relation must be LINEAGE_ONLY")
        if tree.get("mutation_policy") != "PRESERVE_NO_FORCE_MERGE":
            _fail(
                f"predecessor_trees[{index}].mutation_policy must preserve lineage"
            )
    _unique_ids(all_trees, "tree_id", "research trees")


def _validate_authority(ledger: Mapping[str, Any]) -> None:
    authority = _mapping(ledger.get("programme_authority"), "programme_authority")
    _require_fields(
        authority,
        (
            "programme_id",
            "status",
            "code_repository",
            "default_branch",
            "active_roots",
            "claim_policy",
        ),
        "programme_authority",
    )
    _identifier(authority["programme_id"], "programme_authority.programme_id")
    if authority.get("status") != "ACTIVE":
        _fail("programme_authority.status must be ACTIVE")
    _nonempty_string(authority["code_repository"], "programme_authority.code_repository")
    _nonempty_string(authority["default_branch"], "programme_authority.default_branch")
    _nonempty_string(authority["claim_policy"], "programme_authority.claim_policy")
    roots = _list(authority["active_roots"], "programme_authority.active_roots")
    if not roots:
        _fail("programme_authority.active_roots must not be empty")
    _unique_ids(roots, "root_id", "programme_authority.active_roots")
    for index, raw in enumerate(roots):
        root = _mapping(raw, f"programme_authority.active_roots[{index}]")
        _require_fields(root, ("root_id", "path", "role"), f"active_roots[{index}]")
        _safe_relative_path(root["path"], f"programme_authority.active_roots[{index}].path")
        if root.get("role") not in {"CODE_AUTHORITY", "LEDGER_AUTHORITY"}:
            _fail(f"programme_authority.active_roots[{index}].role is unknown")


def _validate_source_roles(ledger: Mapping[str, Any]) -> None:
    roles = _list(ledger.get("source_roles"), "source_roles")
    if not roles:
        _fail("source_roles must not be empty")
    _unique_ids(roles, "source_id", "source_roles")
    required = {"CODE_AUTHORITY", "ADJUDICATION_RECORD", "COMPUTE_RUNTIME"}
    observed: set[str] = set()
    for index, raw in enumerate(roles):
        role = _mapping(raw, f"source_roles[{index}]")
        _require_fields(
            role,
            ("source_id", "role", "uri", "authority", "write_policy", "notes"),
            f"source_roles[{index}]",
        )
        observed.add(_nonempty_string(role["role"], f"source_roles[{index}].role"))
        for field in ("uri", "authority", "write_policy", "notes"):
            _nonempty_string(role[field], f"source_roles[{index}].{field}")
    missing = sorted(required - observed)
    if missing:
        _fail(f"source_roles missing required roles: {missing}")


def _validate_promotion_gate(ledger: Mapping[str, Any]) -> None:
    gate = _mapping(ledger.get("promotion_gate"), "promotion_gate")
    _require_fields(
        gate,
        (
            "gate_id",
            "fail_closed",
            "required_for_states",
            "ordered_requirements",
            "prohibitions",
        ),
        "promotion_gate",
    )
    _identifier(gate["gate_id"], "promotion_gate.gate_id")
    if gate.get("fail_closed") is not True:
        _fail("promotion_gate.fail_closed must be true")
    required_for = set(_list(gate["required_for_states"], "promotion_gate.required_for_states"))
    if required_for != PROMOTED_STATES:
        _fail("promotion_gate.required_for_states must be progressive and canonical")
    requirements = _list(gate["ordered_requirements"], "promotion_gate.ordered_requirements")
    if len(requirements) < 6 or not all(isinstance(item, str) and item for item in requirements):
        _fail("promotion_gate.ordered_requirements must contain at least six steps")
    prohibitions = _list(gate["prohibitions"], "promotion_gate.prohibitions")
    if not prohibitions:
        _fail("promotion_gate.prohibitions must not be empty")


def _validate_hypotheses(
    ledger: Mapping[str, Any], *, repo_root: Path, verify_files: bool
) -> tuple[int, int]:
    hypotheses = _list(ledger.get("hypotheses"), "hypotheses")
    if not hypotheses:
        _fail("hypotheses must not be empty")
    _unique_ids(hypotheses, "hypothesis_id", "hypotheses")

    artifact_ids: list[str] = []
    artifact_count = 0
    for index, raw in enumerate(hypotheses):
        hypothesis = _mapping(raw, f"hypotheses[{index}]")
        context = f"hypotheses[{index}]"
        _require_fields(
            hypothesis,
            (
                "hypothesis_id",
                "title",
                "state",
                "claim_scope",
                *REF_LIST_FIELDS,
                "git",
                "runtime",
                "supersedes",
                "next_falsifier",
                "caveats",
            ),
            context,
        )
        state = _nonempty_string(hypothesis["state"], f"{context}.state")
        if state not in ALLOWED_STATES:
            _fail(f"{context}.state has unknown value: {state!r}")
        _nonempty_string(hypothesis["title"], f"{context}.title")
        _nonempty_string(hypothesis["claim_scope"], f"{context}.claim_scope")

        refs_by_field: dict[str, list[Any]] = {}
        for field in REF_LIST_FIELDS:
            refs = _list(hypothesis[field], f"{context}.{field}")
            refs_by_field[field] = refs
            for ref_index, ref in enumerate(refs):
                ref_context = f"{context}.{field}[{ref_index}]"
                _validate_artifact_ref(
                    ref,
                    context=ref_context,
                    repo_root=repo_root,
                    verify_files=verify_files,
                )
                artifact = _mapping(ref, ref_context)
                artifact_ids.append(str(artifact["artifact_id"]))
                artifact_count += 1

        if state in PROMOTED_STATES:
            judge_refs = refs_by_field["judge_refs"]
            lakato_refs = refs_by_field["lakato_refs"]
            if not judge_refs:
                _fail(
                    f"{context} claims {state} without independent judge evidence"
                )
            if not lakato_refs:
                _fail(f"{context} claims {state} without LakatoTree readback evidence")
            if any(_mapping(ref, "judge_ref").get("kind") != "judge_receipt" for ref in judge_refs):
                _fail(f"{context}.judge_refs must contain judge_receipt artifacts")
            if any(
                _mapping(ref, "lakato_ref").get("kind") != "lakatotree_readback"
                for ref in lakato_refs
            ):
                _fail(f"{context}.lakato_refs must contain lakatotree_readback artifacts")

        git = _mapping(hypothesis["git"], f"{context}.git")
        _require_fields(
            git,
            ("repository", "branch", "ledger_base_commit", "notes"),
            f"{context}.git",
        )
        commit = _nonempty_string(git["ledger_base_commit"], f"{context}.git.ledger_base_commit")
        if not GIT_SHA_RE.fullmatch(commit):
            _fail(f"{context}.git.ledger_base_commit must be a full Git SHA-1")
        if "runtime_commit" in git and not GIT_SHA_RE.fullmatch(
            _nonempty_string(git["runtime_commit"], f"{context}.git.runtime_commit")
        ):
            _fail(f"{context}.git.runtime_commit must be a full Git SHA-1")

        runtime = _mapping(hypothesis["runtime"], f"{context}.runtime")
        _require_fields(
            runtime,
            ("execution_host", "control_plane", "status", "observed_at", "notes"),
            f"{context}.runtime",
        )
        for field in ("execution_host", "control_plane", "status", "observed_at", "notes"):
            _nonempty_string(runtime[field], f"{context}.runtime.{field}")

        supersedes = _list(hypothesis["supersedes"], f"{context}.supersedes")
        for superseded_index, superseded in enumerate(supersedes):
            _identifier(superseded, f"{context}.supersedes[{superseded_index}]")
        if len(supersedes) != len(set(supersedes)):
            _fail(f"{context}.supersedes contains duplicate IDs")

        falsifier = _mapping(hypothesis["next_falsifier"], f"{context}.next_falsifier")
        _require_fields(
            falsifier,
            ("falsifier_id", "test", "kill_condition", "dependency_ids"),
            f"{context}.next_falsifier",
        )
        _identifier(falsifier["falsifier_id"], f"{context}.next_falsifier.falsifier_id")
        _nonempty_string(falsifier["test"], f"{context}.next_falsifier.test")
        _nonempty_string(
            falsifier["kill_condition"], f"{context}.next_falsifier.kill_condition"
        )
        dependencies = _list(
            falsifier["dependency_ids"], f"{context}.next_falsifier.dependency_ids"
        )
        for dependency_index, dependency in enumerate(dependencies):
            _identifier(
                dependency,
                f"{context}.next_falsifier.dependency_ids[{dependency_index}]",
            )
        caveats = _list(hypothesis["caveats"], f"{context}.caveats")
        if not caveats or not all(isinstance(caveat, str) and caveat for caveat in caveats):
            _fail(f"{context}.caveats must contain at least one non-empty caveat")

    duplicate_artifacts = sorted(
        artifact_id
        for artifact_id, count in Counter(artifact_ids).items()
        if count > 1
    )
    if duplicate_artifacts:
        _fail(f"duplicate artifact_id values: {duplicate_artifacts}")
    return len(hypotheses), artifact_count


def validate_ledger(
    ledger: Any,
    *,
    ledger_path: Path,
    verify_files: bool = True,
) -> dict[str, Any]:
    """Validate a parsed ledger and return a deterministic receipt.

    ``ledger_path`` anchors all repository-relative artifact paths.  The v1
    layout requires the ledger at ``<repo>/research/<name>.json``.
    """

    root = _mapping(ledger, "ledger")
    _require_fields(
        root,
        (
            "schema_version",
            "ledger_id",
            "generated_at",
            "programme_authority",
            "active_tree",
            "predecessor_trees",
            "source_roles",
            "promotion_gate",
            "hypotheses",
        ),
        "ledger",
    )
    if root.get("schema_version") != SCHEMA_VERSION:
        _fail(f"unsupported schema_version: {root.get('schema_version')!r}")
    ledger_id = _identifier(root.get("ledger_id"), "ledger.ledger_id")
    _nonempty_string(root.get("generated_at"), "ledger.generated_at")

    resolved_ledger_path = Path(ledger_path).resolve()
    if resolved_ledger_path.parent.name != "research":
        _fail("ledger_path must be located directly under the repository research directory")
    repo_root = resolved_ledger_path.parent.parent

    _validate_authority(root)
    _validate_tree_topology(root)
    _validate_source_roles(root)
    _validate_promotion_gate(root)
    hypothesis_count, artifact_count = _validate_hypotheses(
        root, repo_root=repo_root, verify_files=verify_files
    )

    return {
        "schema": "hswm-research-ledger-validation/v1",
        "status": "PASS",
        "ledger_id": ledger_id,
        "active_tree": root["active_tree"]["tree_id"],
        "hypotheses_checked": hypothesis_count,
        "artifacts_checked": artifact_count,
        "local_hashes_verified": verify_files,
        "scientific_promotion_rule": "progressive/canonical require judge and LakatoTree readback receipts",
    }


def load_and_validate(path: Path, *, verify_files: bool = True) -> dict[str, Any]:
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise LedgerValidationError(f"ledger file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise LedgerValidationError(f"invalid ledger JSON: {error}") from error
    return validate_ledger(ledger, ledger_path=path, verify_files=verify_files)


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "ledger",
        nargs="?",
        type=Path,
        default=repo_root / "research/HSWM_RESEARCH_LEDGER.v1.json",
    )
    parser.add_argument(
        "--no-file-check",
        action="store_true",
        help="validate structure only; do not verify present artifact bytes",
    )
    args = parser.parse_args(argv)
    try:
        receipt = load_and_validate(args.ledger, verify_files=not args.no_file_check)
    except LedgerValidationError as error:
        print(
            json.dumps(
                {
                    "schema": "hswm-research-ledger-validation/v1",
                    "status": "FAIL",
                    "error": str(error),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
