"""Verify the local Longinus binding for the F1 durable transport slice."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "LONGINUS_HSWM_F1_DURABLE_TRANSPORT_BINDING_2026-07-27.json"
SCHEMA = "longinus-hswm-f1-durable-transport-binding/v1"
REQUIRED_LAYERS = {
    "KG_NODE",
    "CONTRACT_BINDING",
    "CODE_SYMBOL",
    "FILE_LINE",
    "LINE_RANGE",
    "SHA256",
    "CRATE_SCRIPT",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
LINE_RANGE_RE = re.compile(r"^(0|[1-9][0-9]*)-(0|[1-9][0-9]*)$")


class BindingError(ValueError):
    """The checked-in binding is incomplete, unsafe, or byte-drifted."""


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise BindingError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BindingError(f"cannot load binding manifest: {error}") from error
    if not isinstance(value, dict):
        raise BindingError("binding manifest must be one JSON object")
    return value


def _safe_file(relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise BindingError("binding source_path must be a non-empty string")
    candidate_path = Path(relative)
    if candidate_path.is_absolute() or ".." in candidate_path.parts:
        raise BindingError(f"unsafe binding source path: {relative}")
    root = REPO_ROOT.resolve()
    candidate = (root / candidate_path).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise BindingError(f"binding source is missing or escapes repository: {relative}")
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, object]:
    manifest = _load(manifest_path)
    if manifest.get("schema") != SCHEMA:
        raise BindingError(f"schema must be {SCHEMA}")
    if manifest.get("binding_state") != "PIERCED_LOCAL_NO_KG_WRITE":
        raise BindingError("binding_state must preserve the local/no-KG-write boundary")
    if set(manifest.get("layers", [])) != REQUIRED_LAYERS:
        raise BindingError("Longinus seven-layer inventory drifted")
    kg = manifest.get("kg")
    if not isinstance(kg, dict) or kg.get("write_state") != "NOT_AUTHORIZED_NOT_WRITTEN":
        raise BindingError("KG write boundary drifted")
    git = manifest.get("git")
    if not isinstance(git, dict) or not GIT_COMMIT_RE.fullmatch(
        str(git.get("implementation_commit", ""))
    ):
        raise BindingError("implementation commit binding is missing")
    bindings = manifest.get("bindings")
    if not isinstance(bindings, list) or not bindings:
        raise BindingError("bindings must be a non-empty array")

    seen_ids: set[str] = set()
    files: set[str] = set()
    roles: set[str] = set()
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            raise BindingError(f"binding {index} must be an object")
        source_id = binding.get("sourceId")
        if not isinstance(source_id, str) or not source_id or source_id in seen_ids:
            raise BindingError(f"binding {index} sourceId is missing or duplicated")
        seen_ids.add(source_id)
        relative = binding.get("source_path")
        path = _safe_file(relative)
        expected_sha = binding.get("sha256")
        if not isinstance(expected_sha, str) or SHA256_RE.fullmatch(expected_sha) is None:
            raise BindingError(f"binding {source_id} has invalid SHA-256")
        if binding.get("sha256_baseline") != expected_sha or _sha256(path) != expected_sha:
            raise BindingError(f"binding {source_id} source bytes drifted")
        match = LINE_RANGE_RE.fullmatch(str(binding.get("line_range", "")))
        if match is None:
            raise BindingError(f"binding {source_id} line range is invalid")
        start, end = (int(match.group(1)), int(match.group(2)))
        lines = path.read_text(encoding="utf-8").splitlines()
        if start < 1 or end < start or end > len(lines):
            raise BindingError(f"binding {source_id} line range escapes source")
        token = binding.get("symbol_token")
        if not isinstance(token, str) or not token or token not in "\n".join(lines[start - 1 : end]):
            raise BindingError(f"binding {source_id} symbol token is absent from range")
        if binding.get("sourcePath") != f"{relative}:{start}":
            raise BindingError(f"binding {source_id} sourcePath drifted")
        role = binding.get("layer")
        if not isinstance(role, str) or not role:
            raise BindingError(f"binding {source_id} role is missing")
        roles.add(role)
        files.add(str(relative))

    required_roles = {
        "L1_CONTRACT",
        "L2_PROTOCOL",
        "L3_STORE",
        "L4_INTEGRATION",
        "L5_TEST",
        "L6_RECEIPT",
        "L7_VERIFIER",
    }
    if not required_roles.issubset(roles):
        raise BindingError("artifact-role coverage is incomplete")
    return {
        "status": "PASS",
        "binding_id": manifest.get("binding_id"),
        "bindings_checked": len(bindings),
        "files_checked": len(files),
        "longinus_layers": len(REQUIRED_LAYERS),
        "artifact_roles": sorted(roles),
        "kg_write_state": kg["write_state"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?", default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        result = verify(args.manifest)
    except BindingError as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
