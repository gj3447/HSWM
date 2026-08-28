"""Deterministic, offline preparation artifacts for a DNRD-4 occurrence.

This operator utility deliberately stops before all scientific work: it neither
contacts GitHub nor a model, runs npm/TypeScript, creates a preregistration, or
creates an execution configuration.  It only converts already-present bytes
into the strict artifacts consumed by :mod:`_research.dnrd.execute`.

Typical use is intentionally split across Source-A and preregistration-B:

``source-manifest`` may be run while preparing the Source-A commit.  In
contrast, ``runtime-manifest`` requires an already-built, detached, clean
Source-A checkout and writes its artifact *outside* that checkout.  Receipt
commands turn a previously downloaded GitHub Actions run JSON body into an
attested local projection; downloading that body is explicitly out of scope.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any, Mapping, Sequence

from .execute import (
    CORE_SOURCE_FILES,
    OFFICIAL_NODE_EXECUTABLE_SHA256,
    OFFICIAL_NODE_VERSION,
    PREREGISTRATION_B_CI_RECEIPT_SCHEMA,
    RUNTIME_TREE_MANIFEST_SCHEMA,
    SOURCE_CI_RECEIPT_SCHEMA,
    SOURCE_MANIFEST_SCHEMA,
)
from .task_family import canonical_json, commitment


class PreparationRefusal(ValueError):
    """The supplied local bytes cannot form a DNRD-4 preparation artifact."""


_HEX = frozenset("0123456789abcdef")
_RUNTIME_RELATIVE = Path("src/hswm/effect-runtime")
_COMPILED_RELATIVE = Path("dist-dnrd")
_ENTRYPOINT_RELATIVE = _COMPILED_RELATIVE / "canonical-atom-v2-routing-diagnostic-process.js"
_PACKAGE_ROOTS = ("@types/node", "effect", "typescript")
_EXPECTED_COMPILED_FILE_COUNT = 56
_EXPECTED_EXTERNAL_PACKAGE_NAMES = frozenset(
    {
        "@standard-schema/spec",
        "@types/node",
        "effect",
        "fast-check",
        "pure-rand",
        "typescript",
        "undici-types",
    }
)
_EXPECTED_EXTERNAL_FILE_COUNT = 3_994


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha_file(path: Path) -> str:
    _plain_file(path, str(path))
    return _sha(path.read_bytes())


def _plain_file(path: Path, label: str) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError as error:
        raise PreparationRefusal(f"{label} is absent") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise PreparationRefusal(f"{label} must be a plain regular file")


def _plain_directory(path: Path, label: str) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError as error:
        raise PreparationRefusal(f"{label} is absent") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise PreparationRefusal(f"{label} must be a plain directory")


def _relative(value: str, label: str) -> str:
    if not value or value.startswith("/"):
        raise PreparationRefusal(f"{label} must be a nonempty relative path")
    path = Path(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise PreparationRefusal(f"{label} escapes its root")
    return path.as_posix()


def _hex(value: object, label: str, *, length: int = 64) -> str:
    if type(value) is not str or len(value) != length or any(char not in _HEX for char in value):
        raise PreparationRefusal(f"{label} must be lowercase {length}-hex")
    return value


def _object_from_utf8(raw: bytes, label: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PreparationRefusal(f"{label} is not UTF-8") from error

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PreparationRefusal(f"{label} repeats JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise PreparationRefusal(f"{label} contains forbidden JSON constant {value!r}")

    try:
        value = json.loads(text, object_pairs_hook=no_duplicates, parse_constant=reject_constant)
    except (json.JSONDecodeError, PreparationRefusal) as error:
        if isinstance(error, PreparationRefusal):
            raise
        raise PreparationRefusal(f"{label} is not JSON") from error
    if type(value) is not dict:
        raise PreparationRefusal(f"{label} must be a JSON object")
    return value


def _canonical_object(raw: bytes, label: str) -> dict[str, Any]:
    value = _object_from_utf8(raw, label)
    if canonical_json(value) != raw:
        raise PreparationRefusal(f"{label} must use exact canonical JSON bytes")
    return value


def _exact_keys(value: object, expected: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise PreparationRefusal(f"{label} key set drifted")
    return value


def _write_new(path: Path, value: Mapping[str, Any]) -> str:
    if path.exists() or path.is_symlink():
        raise PreparationRefusal(f"refusing to overwrite {path}")
    parent = path.parent
    _plain_directory(parent, f"output parent {parent}")
    raw = canonical_json(value)
    path.write_bytes(raw)
    return _sha(raw)


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise PreparationRefusal(f"git {' '.join(args)} failed: {detail}")
    try:
        return completed.stdout.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError as error:
        raise PreparationRefusal(f"git {' '.join(args)} returned non-ASCII identity") from error


def _require_clean_detached_checkout(repo_root: Path) -> tuple[str, str]:
    _plain_directory(repo_root, "repository root")
    if _git(repo_root, "status", "--porcelain"):
        raise PreparationRefusal("runtime/receipt checkout must be clean")
    branch = subprocess.run(
        ["git", "symbolic-ref", "-q", "HEAD"], cwd=repo_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if branch.returncode == 0:
        raise PreparationRefusal("runtime/receipt checkout must be detached at its exact commit")
    commit = _hex(_git(repo_root, "rev-parse", "HEAD"), "checkout HEAD", length=40)
    tree = _hex(_git(repo_root, "rev-parse", "HEAD^{tree}"), "checkout tree", length=40)
    return commit, tree


def _source_manifest_value(repo_root: Path) -> dict[str, Any]:
    _plain_directory(repo_root, "repository root")
    files: list[dict[str, str]] = []
    for relative in sorted(CORE_SOURCE_FILES):
        target = repo_root / relative
        _plain_file(target, f"source member {relative}")
        files.append({"path": relative, "sha256": _sha_file(target)})
    return {
        "schema_version": SOURCE_MANIFEST_SCHEMA,
        "experiment_id": "HSWM-DNRD-4",
        "source_commit_tree_bound_externally": "SOURCE_COMMIT_TREE_BOUND_EXTERNALLY_NO_SELF_CYCLE",
        "files": files,
    }


def generate_source_manifest(*, repo_root: Path, output: Path) -> str:
    """Write the exact ``CORE_SOURCE_FILES`` manifest; never overwrite output."""

    return _write_new(output, _source_manifest_value(repo_root))


def _load_source_manifest(repo_root: Path, source_manifest_path: str) -> tuple[dict[str, Any], str]:
    relative = _relative(source_manifest_path, "source manifest path")
    target = repo_root / relative
    _plain_file(target, "source manifest")
    raw = target.read_bytes()
    value = _canonical_object(raw, "source manifest")
    manifest = _exact_keys(
        value,
        {"schema_version", "experiment_id", "source_commit_tree_bound_externally", "files"},
        "source manifest",
    )
    if (
        manifest["schema_version"] != SOURCE_MANIFEST_SCHEMA
        or manifest["experiment_id"] != "HSWM-DNRD-4"
        or manifest["source_commit_tree_bound_externally"]
        != "SOURCE_COMMIT_TREE_BOUND_EXTERNALLY_NO_SELF_CYCLE"
    ):
        raise PreparationRefusal("source manifest identity drifted")
    rows = manifest["files"]
    if type(rows) is not list:
        raise PreparationRefusal("source manifest files must be a list")
    seen: set[str] = set()
    ordered: list[str] = []
    for index, row in enumerate(rows):
        item = _exact_keys(row, {"path", "sha256"}, f"source manifest.files[{index}]")
        path = _relative(item["path"], f"source manifest.files[{index}].path")
        digest = _hex(item["sha256"], f"source manifest.files[{index}].sha256")
        if path in seen:
            raise PreparationRefusal("source manifest repeats a source member")
        member = repo_root / path
        if _sha_file(member) != digest:
            raise PreparationRefusal(f"source manifest hash drifted: {path}")
        seen.add(path)
        ordered.append(path)
    if ordered != sorted(ordered) or seen != CORE_SOURCE_FILES:
        raise PreparationRefusal("source manifest is not the exact DNRD-4 source closure")
    return dict(manifest), _sha(raw)


def _regular_files(root: Path, relative_root: str) -> list[dict[str, Any]]:
    directory = root / relative_root
    _plain_directory(directory, f"runtime directory {relative_root}")
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("*")):
        info = path.lstat()
        rel = path.relative_to(root).as_posix()
        if stat.S_ISLNK(info.st_mode):
            raise PreparationRefusal(f"runtime closure contains a symlink: {rel}")
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise PreparationRefusal(f"runtime closure contains a non-regular entry: {rel}")
        rows.append({"path": rel, "sha256": _sha_file(path), "bytes": info.st_size})
    if not rows:
        raise PreparationRefusal(f"runtime closure is empty: {relative_root}")
    return rows


def _package_entrypoint(package_root: Path, package: Mapping[str, Any]) -> Path:
    """Resolve a package's import-oriented root entrypoint without Node I/O."""

    def choose(value: object) -> str | None:
        if isinstance(value, str):
            return value
        if type(value) is list:
            for item in value:
                selected = choose(item)
                if selected is not None:
                    return selected
            return None
        if type(value) is dict:
            for key in ("import", "default", "require", "node", "types"):
                if key in value:
                    selected = choose(value[key])
                    if selected is not None:
                        return selected
        return None

    target: str | None = None
    exports = package.get("exports")
    if type(exports) is dict and "." in exports:
        target = choose(exports["."])
    elif exports is not None:
        target = choose(exports)
    if target is None:
        for key in ("module", "main", "types", "typings"):
            candidate = package.get(key)
            if isinstance(candidate, str) and candidate:
                target = candidate
                break
    if target is None:
        for fallback in ("index.js", "index.mjs", "index.cjs", "index.d.ts"):
            if (package_root / fallback).is_file():
                target = fallback
                break
    if target is None or target.startswith("/"):
        raise PreparationRefusal("external package has no local resolved entrypoint")
    candidate = package_root / target.removeprefix("./")
    try:
        candidate.relative_to(package_root)
    except ValueError as error:
        raise PreparationRefusal("external package entrypoint escapes its package") from error
    _plain_file(candidate, "external package resolved entrypoint")
    return candidate


def _external_package_closure(runtime_root: Path) -> list[dict[str, Any]]:
    pending = list(_PACKAGE_ROOTS)
    selected: set[str] = set()
    packages: dict[str, dict[str, Any]] = {}
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        root_relative = f"node_modules/{name}"
        root = runtime_root / root_relative
        _plain_directory(root, f"external package {name}")
        package_json = root / "package.json"
        _plain_file(package_json, f"external package {name} package.json")
        package = _object_from_utf8(package_json.read_bytes(), f"external package {name} package.json")
        if package.get("name") != name or not isinstance(package.get("version"), str) or not package["version"]:
            raise PreparationRefusal(f"external package identity drifted: {name}")
        dependencies = package.get("dependencies", {})
        if type(dependencies) is not dict or any(type(key) is not str or not key for key in dependencies):
            raise PreparationRefusal(f"external package dependencies malformed: {name}")
        selected.add(name)
        pending.extend(sorted(dependencies))
        entrypoint = _package_entrypoint(root, package)
        files = _regular_files(runtime_root, root_relative)
        package_json_relative = f"{root_relative}/package.json"
        packages[name] = {
            "name": name,
            "version": package["version"],
            "package_root": root_relative,
            "package_json_path": package_json_relative,
            "package_json_sha256": _sha_file(package_json),
            "resolved_entrypoint_path": entrypoint.relative_to(runtime_root).as_posix(),
            "resolved_entrypoint_sha256": _sha_file(entrypoint),
            "files": files,
        }
    return [packages[name] for name in sorted(packages)]


def generate_runtime_manifest(
    *, repo_root: Path, source_manifest_path: str, node_executable: Path, output: Path
) -> str:
    """Hash the already-materialized Source-A DNRD runtime closure.

    This does not run ``npm ci`` or ``tsc``.  It refuses anything except the
    fixed effect-runtime location in a clean detached checkout so it cannot be
    accidentally used as a build command on mutable source.
    """

    repo_root = repo_root.resolve()
    source_commit, source_tree = _require_clean_detached_checkout(repo_root)
    if output.resolve().is_relative_to(repo_root):
        raise PreparationRefusal("runtime manifest output must be outside the clean Source-A checkout")
    _, source_manifest_sha = _load_source_manifest(repo_root, source_manifest_path)
    runtime_root = repo_root / _RUNTIME_RELATIVE
    _plain_directory(runtime_root, "effect runtime root")
    compiled = _regular_files(runtime_root, _COMPILED_RELATIVE.as_posix())
    if len(compiled) != _EXPECTED_COMPILED_FILE_COUNT:
        raise PreparationRefusal(
            f"DNRD-4 requires exactly {_EXPECTED_COMPILED_FILE_COUNT} compiled dist-dnrd files, got {len(compiled)}"
        )
    entrypoint = runtime_root / _ENTRYPOINT_RELATIVE
    _plain_file(entrypoint, "DNRD runtime bridge entrypoint")
    node_executable = node_executable.resolve()
    _plain_file(node_executable, "pinned Node executable")
    version = subprocess.run(
        [str(node_executable), "--version"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if version.returncode != 0:
        raise PreparationRefusal("pinned Node executable cannot report its version")
    node_version = version.stdout.decode("ascii", errors="strict").strip()
    if not node_version.startswith("v"):
        raise PreparationRefusal("pinned Node executable returned a malformed version")
    if (
        _sha_file(node_executable) != OFFICIAL_NODE_EXECUTABLE_SHA256
        or node_version != OFFICIAL_NODE_VERSION
    ):
        raise PreparationRefusal("Node executable is not the frozen DNRD production runtime")
    packages = _external_package_closure(runtime_root)
    if (
        {package["name"] for package in packages}
        != _EXPECTED_EXTERNAL_PACKAGE_NAMES
        or sum(len(package["files"]) for package in packages)
        != _EXPECTED_EXTERNAL_FILE_COUNT
    ):
        raise PreparationRefusal(
            "DNRD-4 requires the exact seven-package, 3,994-file external runtime closure"
        )
    source_manifest, _ = _load_source_manifest(repo_root, source_manifest_path)
    compiler_paths = {
        "package_json_path": "node_modules/typescript/package.json",
        "bin_tsc_path": "node_modules/typescript/bin/tsc",
        "lib_tsc_path": "node_modules/typescript/lib/tsc.js",
        "lib_typescript_path": "node_modules/typescript/lib/typescript.js",
    }
    # Spell the keys explicitly: the schema is a frozen interface, not a
    # convenience mapping whose accidental rename could silently alter it.
    typescript = {
        **compiler_paths,
        "package_json_sha256": _sha_file(runtime_root / compiler_paths["package_json_path"]),
        "bin_tsc_sha256": _sha_file(runtime_root / compiler_paths["bin_tsc_path"]),
        "lib_tsc_sha256": _sha_file(runtime_root / compiler_paths["lib_tsc_path"]),
        "lib_typescript_sha256": _sha_file(runtime_root / compiler_paths["lib_typescript_path"]),
    }
    value = {
        "schema_version": RUNTIME_TREE_MANIFEST_SCHEMA,
        "root_path": str(runtime_root),
        "entrypoint": _ENTRYPOINT_RELATIVE.as_posix(),
        "files": compiled,
        "external_packages": packages,
        "build_provenance": {
            "source_a_commit": source_commit,
            "source_a_tree": source_tree,
            "source_manifest_path": _relative(source_manifest_path, "source manifest path"),
            "source_manifest_sha256": source_manifest_sha,
            "node_executable_sha256": _sha_file(node_executable),
            "node_version": node_version,
            "dependency_materialization_command": ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
            "compilation_command": ["{PINNED_NODE_EXECUTABLE}", "node_modules/typescript/lib/tsc.js", "-p", "tsconfig.dnrd.json"],
            "claim_boundary": "SOURCE_SELECTED_PACKAGE_AND_COMPILER_BYTES_PINNED_BUILD_NOT_INDEPENDENTLY_REEXECUTED",
            "source_inputs": source_manifest["files"],
            "package_roots": list(_PACKAGE_ROOTS),
            "typescript": typescript,
        },
    }
    return _write_new(output, value)


def _completed_unix(value: object, label: str) -> int:
    if type(value) is not str:
        raise PreparationRefusal(f"{label} must be an exact UTC RFC3339 timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise PreparationRefusal(f"{label} must be exact UTC RFC3339 seconds") from error
    return int(parsed.timestamp())


_CI_WORKFLOW_PATH = ".github/workflows/ci.yml"
_CI_REPOSITORY = "gj3447/HSWM"


def _discovery_query(head_sha: str) -> dict[str, object]:
    return {
        "request_path": f"/repos/{_CI_REPOSITORY}/actions/workflows/ci.yml/runs?event=push&branch=main&head_sha={head_sha}&per_page=100&page=1",
        "workflow_path": _CI_WORKFLOW_PATH, "event": "push", "branch": "main",
        "head_sha": head_sha, "per_page": 100, "page": 1,
    }


def _ci_projection(api: Mapping[str, Any], label: str) -> dict[str, Any]:
    """The complete run identity used to prevent CI/run selection after the fact."""
    head = api.get("head_commit")
    repository, head_repository = api.get("repository"), api.get("head_repository")
    if not isinstance(head, dict) or not isinstance(repository, dict) or not isinstance(head_repository, dict):
        raise PreparationRefusal(f"{label} has no complete GitHub run/repository projection")
    fields = ("id", "workflow_id", "run_number", "name", "path", "event", "head_branch", "head_sha", "run_attempt", "status", "conclusion", "created_at", "run_started_at", "updated_at", "pull_requests")
    value = {key: api.get(key) for key in fields}
    value["head_commit"] = {"id": head.get("id"), "tree_id": head.get("tree_id")}
    value["repository"] = {"id": repository.get("id"), "full_name": repository.get("full_name")}
    value["head_repository"] = {"id": head_repository.get("id"), "full_name": head_repository.get("full_name")}
    if (type(value["id"]) is not int or value["id"] <= 0 or type(value["workflow_id"]) is not int or value["workflow_id"] <= 0
            or type(value["run_number"]) is not int or value["run_number"] <= 0 or value["name"] != "CI"
            or value["path"] != _CI_WORKFLOW_PATH or value["event"] != "push" or value["head_branch"] != "main"
            or value["run_attempt"] != 1 or value["status"] != "completed" or value["conclusion"] != "success"
            or value["pull_requests"] != [] or value["repository"] != value["head_repository"]
            or value["repository"].get("full_name") != _CI_REPOSITORY or type(value["repository"].get("id")) is not int or value["repository"]["id"] <= 0):
        raise PreparationRefusal(f"{label} is not the unique first-attempt main push CI run")
    head_sha = _hex(value["head_sha"], f"{label}.head_sha", length=40)
    if value["head_commit"].get("id") != head_sha:
        raise PreparationRefusal(f"{label} head commit SHA drifted")
    _hex(value["head_commit"].get("tree_id"), f"{label}.head_commit.tree_id", length=40)
    created = _completed_unix(value["created_at"], f"{label}.created_at")
    started = _completed_unix(value["run_started_at"], f"{label}.run_started_at")
    updated = _completed_unix(value["updated_at"], f"{label}.updated_at")
    if not created <= started <= updated:
        raise PreparationRefusal(f"{label} timestamps are not ordered")
    return value


def _github_completed_success(raw: bytes, raw_list: bytes, *, expected_head: str) -> tuple[dict[str, Any], dict[str, Any], str, str, int]:
    api = _object_from_utf8(raw, "raw GitHub Actions response")
    projection = _ci_projection(api, "raw GitHub Actions response")
    head_sha = _hex(projection["head_sha"], "raw GitHub Actions head_sha", length=40)
    if head_sha != expected_head:
        raise PreparationRefusal("raw GitHub Actions response head differs from requested exact commit")
    listing = _object_from_utf8(raw_list, "raw GitHub Actions workflow-runs list response")
    rows = listing.get("workflow_runs")
    if listing.get("total_count") != 1 or type(rows) is not list or len(rows) != 1 or type(rows[0]) is not dict:
        raise PreparationRefusal("workflow-runs list must prove exactly one qualifying run")
    listed_projection = _ci_projection(rows[0], "raw GitHub Actions workflow-runs list row")
    if listed_projection != projection:
        raise PreparationRefusal("workflow-runs list row differs from selected raw run")
    tree = _hex(projection["head_commit"]["tree_id"], "raw GitHub Actions head_commit.tree_id", length=40)
    completed = _completed_unix(projection["updated_at"], "raw GitHub Actions updated_at")
    return api, projection, head_sha, tree, completed


def _raw_response_bytes(path: Path) -> bytes:
    """Read exact GitHub bytes from a plain file or standard input.

    ``-`` lets an operator pipe ``gh api`` directly into this offline
    projector.  The preparer still performs no network operation itself and
    avoids a mutable, unaddressed intermediate response file.
    """

    if path == Path("-"):
        return sys.stdin.buffer.read()
    _plain_file(path, "raw GitHub Actions response")
    return path.read_bytes()


def generate_source_ci_receipt(
    *, raw_response: Path, raw_list_response: Path, output: Path, source_a_commit: str, source_a_tree: str
) -> str:
    """Create the v2 source-A CI receipt from saved run and list API bodies."""

    if raw_response == raw_list_response == Path("-"):
        raise PreparationRefusal("run and workflow-runs list cannot both consume stdin")
    raw, raw_list = _raw_response_bytes(raw_response), _raw_response_bytes(raw_list_response)
    api, projection, head_sha, tree, _ = _github_completed_success(raw, raw_list, expected_head=_hex(source_a_commit, "source A commit", length=40))
    if head_sha != _hex(source_a_commit, "source A commit", length=40) or tree != _hex(source_a_tree, "source A tree", length=40):
        raise PreparationRefusal("raw GitHub Actions response does not bind the supplied Source-A commit/tree")
    unsigned = {
        "schema_version": SOURCE_CI_RECEIPT_SCHEMA,
        "provider": "GITHUB_ACTIONS",
        "run_id": api["id"],
        "head_sha": head_sha,
        "conclusion": "success",
        "raw_response_sha256": _sha(raw),
        "raw_response_utf8": raw.decode("utf-8", errors="strict"),
        "discovery_query": _discovery_query(head_sha),
        "critical_projection": projection,
        "raw_list_response_sha256": _sha(raw_list),
        "raw_list_response_utf8": raw_list.decode("utf-8", errors="strict"),
    }
    return _write_new(output, {**unsigned, "receipt_sha256": commitment(unsigned)})


def generate_preregistration_b_ci_receipt(
    *, repo_root: Path, preregistration_path: str, raw_response: Path, raw_list_response: Path, output: Path
) -> str:
    """Create the v2 B receipt from local B plus saved run and list API bodies."""

    repo_root = repo_root.resolve()
    commit, tree = _require_clean_detached_checkout(repo_root)
    relative = _relative(preregistration_path, "preregistration path")
    prereg = repo_root / relative
    _plain_file(prereg, "preregistration")
    if raw_response == raw_list_response == Path("-"):
        raise PreparationRefusal("run and workflow-runs list cannot both consume stdin")
    raw, raw_list = _raw_response_bytes(raw_response), _raw_response_bytes(raw_list_response)
    api, projection, head_sha, api_tree, completed = _github_completed_success(raw, raw_list, expected_head=commit)
    if head_sha != commit or api_tree != tree:
        raise PreparationRefusal("raw GitHub Actions response does not bind this detached preregistration-B checkout")
    blob = _hex(_git(repo_root, "rev-parse", f"HEAD:{relative}"), "preregistration Git blob", length=40)
    unsigned = {
        "schema_version": PREREGISTRATION_B_CI_RECEIPT_SCHEMA,
        "provider": "GITHUB_ACTIONS",
        "run_id": api["id"],
        "head_sha": commit,
        "head_tree_oid": tree,
        "preregistration_path": relative,
        "preregistration_sha256": _sha(prereg.read_bytes()),
        "preregistration_git_blob_oid": blob,
        "status": "completed",
        "conclusion": "success",
        "completed_at_utc": api["updated_at"],
        "completed_at_unix": completed,
        "raw_response_sha256": _sha(raw),
        "raw_response_utf8": raw.decode("utf-8", errors="strict"),
        "discovery_query": _discovery_query(commit),
        "critical_projection": projection,
        "raw_list_response_sha256": _sha(raw_list),
        "raw_list_response_utf8": raw_list.decode("utf-8", errors="strict"),
    }
    return _write_new(output, {**unsigned, "receipt_sha256": commitment(unsigned)})


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m _research.dnrd.prepare",
        description="Offline deterministic DNRD-4 Source-A/B preparation artifacts; never contacts a model or network.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    source = commands.add_parser("source-manifest", help="write the canonical CORE_SOURCE_FILES manifest")
    source.add_argument("--repo-root", required=True)
    source.add_argument("--output", required=True)
    runtime = commands.add_parser("runtime-manifest", help="hash an already npm-ci/tsc-built exact-A runtime")
    runtime.add_argument("--repo-root", required=True)
    runtime.add_argument("--source-manifest-path", required=True)
    runtime.add_argument("--node-executable", required=True)
    runtime.add_argument("--output", required=True)
    a_receipt = commands.add_parser("source-ci-receipt", help="attest saved raw Source-A GitHub Actions JSON")
    a_receipt.add_argument(
        "--raw-response", required=True,
        help="saved raw Actions response path, or - for exact stdin bytes",
    )
    a_receipt.add_argument("--raw-list-response", required=True, help="saved exact workflow-runs list JSON, or - for stdin")
    a_receipt.add_argument("--source-a-commit", required=True)
    a_receipt.add_argument("--source-a-tree", required=True)
    a_receipt.add_argument("--output", required=True)
    b_receipt = commands.add_parser("preregistration-b-ci-receipt", help="attest saved raw preregistration-B Actions JSON")
    b_receipt.add_argument("--repo-root", required=True)
    b_receipt.add_argument("--preregistration-path", required=True)
    b_receipt.add_argument(
        "--raw-response", required=True,
        help="saved raw Actions response path, or - for exact stdin bytes",
    )
    b_receipt.add_argument("--raw-list-response", required=True, help="saved exact workflow-runs list JSON, or - for stdin")
    b_receipt.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "source-manifest":
            digest = generate_source_manifest(repo_root=_path(args.repo_root), output=_path(args.output))
        elif args.command == "runtime-manifest":
            digest = generate_runtime_manifest(
                repo_root=_path(args.repo_root), source_manifest_path=args.source_manifest_path,
                node_executable=_path(args.node_executable), output=_path(args.output),
            )
        elif args.command == "source-ci-receipt":
            digest = generate_source_ci_receipt(
                raw_response=(Path("-") if args.raw_response == "-" else _path(args.raw_response)),
                raw_list_response=(Path("-") if args.raw_list_response == "-" else _path(args.raw_list_response)),
                output=_path(args.output),
                source_a_commit=args.source_a_commit, source_a_tree=args.source_a_tree,
            )
        else:
            digest = generate_preregistration_b_ci_receipt(
                repo_root=_path(args.repo_root), preregistration_path=args.preregistration_path,
                raw_response=(Path("-") if args.raw_response == "-" else _path(args.raw_response)),
                raw_list_response=(Path("-") if args.raw_list_response == "-" else _path(args.raw_list_response)),
                output=_path(args.output),
            )
    except (OSError, PreparationRefusal, subprocess.SubprocessError) as error:
        print(f"DNRD-4 preparation refused: {error}", file=sys.stderr)
        return 2
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
