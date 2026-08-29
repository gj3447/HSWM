"""Local, no-call DNRD-5 source/build/import closure.

This instrument derives identities from Git objects, Python ASTs, the locked
TypeScript compiler's own resolution table, and a fresh controlled build.  It
does not issue a Source-A decision, authorize dispatch, call a provider/model,
or establish occurrence or efficacy.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from hashlib import new as new_hash
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat as stat_module
import subprocess
import sys
import tempfile
import unicodedata
from typing import Any, Mapping, Sequence

from _research.dnrd5.canonical_json import (
    CanonicalJsonError,
    canonical_bytes,
    canonical_sha256,
    parse_canonical,
)


CONTRACT_VERSION = "hswm-dnrd5-local-source-build-import-closure/v1"
TYPESCRIPT_CONTRACT_VERSION = CONTRACT_VERSION
TERMINAL = (
    "LOCAL_SOURCE_BUILD_IMPORT_CLOSURE_REDERIVED_"
    "NOT_SOURCE_A_PROVIDER_OCCURRENCE_OR_EFFICACY"
)
TYPESCRIPT_TERMINAL = (
    "LOCAL_SOURCE_BUILD_IMPORT_CLOSURE_ONLY_NOT_SOURCE_A_PROVIDER_OR_EFFICACY"
)
TYPESCRIPT_CLAIM_BOUNDARY = (
    "LOCAL_REDERIVATION_ONLY_NO_NETWORK_AUTHORITY_SOURCE_FREEZE_PROVIDER_"
    "OCCURRENCE_OR_SCIENTIFIC_RESULT"
)
REFUSAL_TERMINAL = "LOCAL_SOURCE_BUILD_IMPORT_CLOSURE_REFUSED_NO_DISPATCH"
CLAIM_BOUNDARY = (
    "LOCAL_GIT_AST_COMPILER_AND_BUILD_IDENTITY_ONLY_NOT_COMPILER_SOUNDNESS_"
    "REMOTE_PROVENANCE_NETWORK_SYSCALL_ABSENCE_SOURCE_A_AUTHORITY_PROVIDER_"
    "OCCURRENCE_LEARNING_OR_SCIENTIFIC_RESULT"
)
PACKAGE_ROOT = PurePosixPath("src/hswm/effect-runtime")
NODE_CAPTURE = PACKAGE_ROOT / "scripts/emit-dnrd5-source-closure.mjs"
TYPESCRIPT_ENTRYPOINTS = tuple(
    sorted(
        (
            "src/canonical-atom-v2-dnrd5-durable-permit.ts",
            "src/canonical-atom-v2-dnrd5-nine-call.ts",
            "src/canonical-atom-v2-dnrd5-plan-json.ts",
            "src/canonical-atom-v2-dnrd5-randomization.ts",
            "src/canonical-atom-v2-dnrd5-v2-audit-release.ts",
            "src/canonical-atom-v2-dnrd5-v2-exact-w0-restore-projection.ts",
            "src/canonical-atom-v2-dnrd5-v2-lifecycle-adapter.ts",
            "src/canonical-atom-v2-dnrd5-v2-receipt-seal.ts",
            "src/canonical-atom-v2-dnrd5-v2-record-bound-effect.ts",
        )
    )
)
TYPESCRIPT_INPUT_PATHS = tuple(
    sorted(
        (
            ".npmrc",
            "package-lock.json",
            "package.json",
            "tsconfig.build.json",
            "tsconfig.dnrd5-source-closure.json",
            "tsconfig.json",
        )
    )
)
TYPESCRIPT_COMPILER_PATHS = tuple(
    sorted(
        (
            "node_modules/typescript/lib/tsc.js",
            "node_modules/typescript/lib/typescript.js",
            "node_modules/typescript/package.json",
        )
    )
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_OID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_ALLOWED_MODES = {"100644", "100755"}
_DYNAMIC_CALLS = {
    "__import__",
    "builtins.__import__",
    "eval",
    "builtins.eval",
    "exec",
    "builtins.exec",
    "compile",
    "builtins.compile",
    "importlib.import_module",
    "runpy.run_module",
    "runpy.run_path",
}
_FORBIDDEN_IMPORT_ROOTS = {"__builtins__", "builtins", "importlib", "runpy"}
_NETWORK_CAPABLE_ROOTS = {"http", "socket", "ssl", "urllib"}
_CRITICAL_ARTIFACTS: tuple[tuple[str, PurePosixPath], ...] = (
    ("source-ci-workflow", PurePosixPath(".github/workflows/ci.yml")),
    ("python-source-distribution-policy", PurePosixPath("MANIFEST.in")),
    ("pyproject", PurePosixPath("pyproject.toml")),
    ("python-lock", PurePosixPath("uv.lock")),
    (
        "scientific-design",
        PurePosixPath(
            "docs/research/HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md"
        ),
    ),
    (
        "exactness-policy",
        PurePosixPath(
            "docs/research/HSWM_DNRD_5_EXACTNESS_POLICY_AMENDMENT_2026-08-28.md"
        ),
    ),
    ("node-package", PACKAGE_ROOT / "package.json"),
    ("node-lock", PACKAGE_ROOT / "package-lock.json"),
    ("node-policy", PACKAGE_ROOT / ".npmrc"),
    ("typescript-base-config", PACKAGE_ROOT / "tsconfig.json"),
    ("typescript-build-config", PACKAGE_ROOT / "tsconfig.build.json"),
    (
        "typescript-selected-config",
        PACKAGE_ROOT / "tsconfig.dnrd5-source-closure.json",
    ),
    ("typescript-capture", NODE_CAPTURE),
    (
        "actual-byte-manifest",
        PurePosixPath(
            "_research/dnrd5/vectors/actual_byte_corpus_v1/manifest.json"
        ),
    ),
    (
        "v2-schema",
        PurePosixPath("_research/dnrd5/vectors/dnrd5_v2_schema.json"),
    ),
    (
        "lifecycle",
        PurePosixPath("_research/dnrd5/vectors/lifecycle_contract_v1.json"),
    ),
    (
        "alignment",
        PurePosixPath(
            "_research/dnrd5/vectors/lifecycle_atom_alignment_v1.json"
        ),
    ),
    (
        "plan-json-kat",
        PurePosixPath("_research/dnrd5/vectors/plan_json_v1_kat.json"),
    ),
)


class SourceBuildImportClosureRefusal(ValueError):
    """Typed fail-closed local qualification refusal."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.terminal = REFUSAL_TERMINAL
        self.dispatch_authorized = False
        self.dispatch_budget = 0
        self.source_freeze_eligible = False


@dataclass(frozen=True, slots=True)
class CapturedSourceBuildImportClosure:
    manifest: Mapping[str, Any]
    raw: bytes
    descriptor: Mapping[str, Any]


def _refuse(code: str, detail: str) -> None:
    raise SourceBuildImportClosureRefusal(code, detail)


def _run(
    arguments: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
    timeout: int = 300,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            list(arguments),
            cwd=cwd,
            env=dict(environment) if environment is not None else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        _refuse("LOCAL_TOOL_EXECUTION_FAILED", f"{arguments[0]} did not complete")
    if result.returncode != 0 and not allow_failure:
        detail = result.stderr.decode("utf-8", errors="replace")[:2_000]
        _refuse(
            "LOCAL_TOOL_EXECUTION_FAILED",
            f"{arguments[0]} exited {result.returncode}: {detail}",
        )
    return result


def _git(root: Path, *arguments: str, allow_failure: bool = False) -> bytes:
    return _run(
        ("git", "--no-replace-objects", "--no-pager", *arguments),
        cwd=root,
        allow_failure=allow_failure,
    ).stdout


def _text(raw: bytes, label: str) -> str:
    try:
        value = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        _refuse("GIT_IDENTITY_INVALID", f"{label} is not UTF-8")
    return value


def _safe_relative_path(value: str, label: str) -> PurePosixPath:
    if type(value) is not str or not value or "\\" in value:
        _refuse("PATH_CLOSURE_INVALID", f"{label} is not a POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        _refuse("PATH_CLOSURE_INVALID", f"{label} escaped the closure root")
    return path


def _git_object_oid(object_format: str, kind: str, raw: bytes) -> str:
    digest = new_hash(object_format)
    digest.update(f"{kind} {len(raw)}\0".encode("ascii"))
    digest.update(raw)
    return digest.hexdigest()


def _valid_git_oid(value: str, object_format: str) -> bool:
    expected_length = 40 if object_format == "sha1" else 64
    return len(value) == expected_length and _GIT_OID.fullmatch(value) is not None


def _walk_raw_git_tree(
    root: Path,
    tree_oid: str,
    object_format: str,
    *,
    prefix: PurePosixPath | None = None,
    depth: int = 0,
    raw_cache: Mapping[str, bytes] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if depth > 256:
        _refuse("GIT_IDENTITY_INVALID", "Git tree nesting exceeds closure limit")
    current_prefix = prefix or PurePosixPath()
    cached = raw_cache.get(tree_oid) if raw_cache is not None else None
    raw = cached if cached is not None else _git(root, "cat-file", "tree", tree_oid)
    if _git_object_oid(object_format, "tree", raw) != tree_oid:
        _refuse("GIT_IDENTITY_INVALID", "raw subtree bytes do not match tree OID")
    tree_records = [
        {
            "path": current_prefix.as_posix() if current_prefix.parts else ".",
            "gitTreeOid": tree_oid,
            "byteLength": len(raw),
            "sha256": sha256(raw).hexdigest(),
        }
    ]
    selected: list[dict[str, Any]] = []
    digest_length = 20 if object_format == "sha1" else 32
    cursor = 0
    names: set[bytes] = set()
    while cursor < len(raw):
        space = raw.find(b" ", cursor)
        nul = raw.find(b"\0", space + 1 if space >= 0 else cursor)
        oid_end = nul + 1 + digest_length
        if space <= cursor or nul <= space + 1 or oid_end > len(raw):
            _refuse("GIT_IDENTITY_INVALID", "raw Git tree record is malformed")
        raw_mode = raw[cursor:space]
        raw_name = raw[space + 1 : nul]
        if raw_name in names:
            _refuse("GIT_IDENTITY_INVALID", "raw Git tree has a duplicate name")
        names.add(raw_name)
        try:
            mode = raw_mode.decode("ascii", errors="strict")
            name = raw_name.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            _refuse("GIT_IDENTITY_INVALID", "raw Git tree metadata is not UTF-8/ASCII")
        if not name or "/" in name or name in {".", ".."} or "\\" in name:
            _refuse("PATH_CLOSURE_INVALID", "raw Git tree name is unsafe")
        child_oid = raw[nul + 1 : oid_end].hex()
        if not _valid_git_oid(child_oid, object_format):
            _refuse("GIT_IDENTITY_INVALID", "raw Git tree child OID is malformed")
        child_path = current_prefix / name
        path_text = _safe_relative_path(
            child_path.as_posix(), "raw Git tree path"
        ).as_posix()
        if mode == "40000":
            child_selected, child_trees = _walk_raw_git_tree(
                root,
                child_oid,
                object_format,
                prefix=child_path,
                depth=depth + 1,
                raw_cache=raw_cache,
            )
            selected.extend(child_selected)
            tree_records.extend(child_trees)
        elif _selected_path(PurePosixPath(path_text)):
            if mode not in _ALLOWED_MODES:
                _refuse(
                    "SOURCE_BLOB_DRIFT",
                    f"unsupported selected Git entry {path_text}",
                )
            blob = _git(root, "cat-file", "blob", child_oid)
            if _git_object_oid(object_format, "blob", blob) != child_oid:
                _refuse(
                    "SOURCE_BLOB_DRIFT",
                    f"raw blob bytes do not match OID at {path_text}",
                )
            selected.append(
                {
                    "path": path_text,
                    "mode": mode,
                    "gitBlobOid": child_oid,
                    "byteLength": len(blob),
                    "sha256": sha256(blob).hexdigest(),
                }
            )
        cursor = oid_end
    return selected, tree_records


def _descriptor(path: Path, stable_path: str) -> dict[str, Any]:
    try:
        metadata = path.lstat()
    except OSError:
        _refuse("SOURCE_BLOB_DRIFT", f"missing required file {stable_path}")
    if not stat_module.S_ISREG(metadata.st_mode) or path.is_symlink():
        _refuse("SOURCE_BLOB_DRIFT", f"{stable_path} is not a regular file")
    try:
        raw = path.read_bytes()
    except OSError:
        _refuse("SOURCE_BLOB_DRIFT", f"could not read required file {stable_path}")
    return {
        "path": stable_path,
        "byteLength": len(raw),
        "sha256": sha256(raw).hexdigest(),
    }


def _descriptor_within(root: Path, path: Path, stable_path: str) -> dict[str, Any]:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        _refuse("SOURCE_BLOB_DRIFT", f"missing required file {stable_path}")
    absolute = path.absolute()
    resolved_root = root.resolve()
    if resolved != absolute or not resolved.is_relative_to(resolved_root):
        _refuse(
            "SOURCE_BLOB_DRIFT",
            f"required file path traverses a symlink or escapes root: {stable_path}",
        )
    return _descriptor(path, stable_path)


def _selected_path(path: PurePosixPath) -> bool:
    text = path.as_posix()
    return (
        text in {item.as_posix() for _, item in _CRITICAL_ARTIFACTS}
        or text.startswith("_research/dnrd5/")
        or text.startswith("tests/test_dnrd5_")
        or text.startswith(f"{PACKAGE_ROOT.as_posix()}/src/")
        or text.startswith(f"{PACKAGE_ROOT.as_posix()}/scripts/")
        or text.startswith(f"{PACKAGE_ROOT.as_posix()}/test/")
    )


def collect_git_source(
    repo_root: Path,
    commit: str = "HEAD",
    *,
    require_detached_clean: bool = True,
) -> dict[str, Any]:
    """Rehash the selected closure directly from raw Git blob objects."""

    root = repo_root.resolve()
    top = _text(_git(root, "rev-parse", "--show-toplevel"), "Git top-level").strip()
    if Path(top).resolve() != root:
        _refuse("GIT_IDENTITY_INVALID", "repo_root is not the Git top-level")
    if require_detached_clean:
        symbolic = _run(
            ("git", "symbolic-ref", "-q", "HEAD"),
            cwd=root,
            allow_failure=True,
        )
        if symbolic.returncode == 0:
            _refuse("WORKTREE_NOT_DETACHED_CLEAN", "capture checkout is attached")
        status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        if status:
            _refuse("WORKTREE_NOT_DETACHED_CLEAN", "capture checkout is dirty")

    oid = _text(
        _git(
            root,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{commit}^{{commit}}",
        ),
        "commit OID",
    ).strip()
    tree = _text(
        _git(root, "rev-parse", "--verify", f"{oid}^{{tree}}"),
        "tree OID",
    ).strip()
    object_format = _text(
        _git(root, "rev-parse", "--show-object-format"), "object format"
    ).strip()
    if object_format not in {"sha1", "sha256"}:
        _refuse("GIT_IDENTITY_INVALID", "unsupported Git object format")
    if not _valid_git_oid(oid, object_format) or not _valid_git_oid(
        tree, object_format
    ):
        _refuse("GIT_IDENTITY_INVALID", "commit or tree OID is malformed")
    if require_detached_clean:
        head_oid = _text(
            _git(root, "rev-parse", "--verify", "HEAD^{commit}"),
            "detached HEAD OID",
        ).strip()
        if head_oid != oid:
            _refuse(
                "WORKTREE_NOT_DETACHED_CLEAN",
                "requested commit is not the detached checkout HEAD",
            )
    commit_bytes = _git(root, "cat-file", "commit", oid)
    tree_bytes = _git(root, "cat-file", "tree", tree)
    if _git_object_oid(object_format, "commit", commit_bytes) != oid:
        _refuse("GIT_IDENTITY_INVALID", "raw commit bytes do not match commit OID")
    if _git_object_oid(object_format, "tree", tree_bytes) != tree:
        _refuse("GIT_IDENTITY_INVALID", "raw tree bytes do not match tree OID")
    if commit_bytes.partition(b"\n")[0] != f"tree {tree}".encode("ascii"):
        _refuse("GIT_IDENTITY_INVALID", "raw commit/tree binding is inconsistent")

    selected, tree_objects = _walk_raw_git_tree(
        root,
        tree,
        object_format,
        raw_cache={tree: tree_bytes},
    )
    selected.sort(key=lambda item: item["path"])
    tree_objects.sort(key=lambda item: item["path"])
    paths = [item["path"] for item in selected]
    if len(paths) != len(set(paths)):
        _refuse("SOURCE_BLOB_DRIFT", "raw Git tree selected duplicate paths")
    tree_paths = [item["path"] for item in tree_objects]
    if len(tree_paths) != len(set(tree_paths)):
        _refuse("GIT_IDENTITY_INVALID", "raw Git tree closure has duplicate paths")
    if not selected:
        _refuse("SOURCE_BLOB_DRIFT", "selected source closure is empty")
    return {
        "gitObjectFormat": object_format,
        "commit": oid,
        "tree": tree,
        "commitObject": {
            "byteLength": len(commit_bytes),
            "sha256": sha256(commit_bytes).hexdigest(),
        },
        "treeObject": {
            "byteLength": len(tree_bytes),
            "sha256": sha256(tree_bytes).hexdigest(),
        },
        "treeObjects": tree_objects,
        "treeObjectsSha256": canonical_sha256(tree_objects),
        "detachedClean": require_detached_clean,
        "cleanPolicy": (
            "DETACHED_HEAD_EQUALS_REQUESTED_COMMIT_AND_GIT_STATUS_PORCELAIN_V1_"
            "UNTRACKED_ALL_EMPTY_IGNORED_BUILD_INPUTS_CAPTURED_SEPARATELY"
        ),
        "selectedTrackedFiles": selected,
        "selectedTrackedFilesSha256": canonical_sha256(selected),
    }


def _module_name(path: PurePosixPath) -> str:
    parts = list(path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_local_module(root: Path, module: str) -> str | None:
    relative = PurePosixPath(*module.split("."))
    for candidate in (relative.with_suffix(".py"), relative / "__init__.py"):
        path = root / candidate
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            continue
        if (
            path.is_file()
            and not path.is_symlink()
            and resolved == path.absolute()
            and resolved.is_relative_to(root)
        ):
            return candidate.as_posix()
    return None


def _callee_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _callee_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return f"<{type(node).__name__}>"


class _CallCollector(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.scopes: list[str] = ["<module>"]
        self.calls: list[dict[str, Any]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scopes.append(node.name)
        self.generic_visit(node)
        self.scopes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scopes.append(node.name)
        self.generic_visit(node)
        self.scopes.pop()

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in {"__builtins__", "__import__", "eval", "exec", "compile"}:
            _refuse(
                "PYTHON_DYNAMIC_IMPORT_FORBIDDEN",
                f"{self.path}:{node.lineno} references dynamic loader {node.id}",
            )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        callee = _callee_name(node)
        if callee in _DYNAMIC_CALLS or callee.endswith(".import_module"):
            _refuse(
                "PYTHON_DYNAMIC_IMPORT_FORBIDDEN",
                f"{self.path}:{node.lineno} references dynamic loader {callee}",
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        callee = _callee_name(node.func)
        if callee in _DYNAMIC_CALLS or callee.endswith(".import_module"):
            _refuse(
                "PYTHON_DYNAMIC_IMPORT_FORBIDDEN",
                f"{self.path}:{node.lineno} uses {callee}",
            )
        if (
            callee in {"getattr", "builtins.getattr"}
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value
            in {"__import__", "eval", "exec", "compile", "import_module"}
        ):
            _refuse(
                "PYTHON_DYNAMIC_IMPORT_FORBIDDEN",
                f"{self.path}:{node.lineno} obtains a dynamic loader indirectly",
            )
        self.calls.append(
            {
                "path": self.path,
                "caller": ".".join(self.scopes),
                "callee": callee,
                "line": node.lineno,
                "column": node.col_offset,
            }
        )
        self.generic_visit(node)


def resolve_python_ast_closure(repo_root: Path) -> dict[str, Any]:
    """Parse exact local DNRD-5 Python files without importing them."""

    root = repo_root.resolve()
    base = root / "_research" / "dnrd5"
    try:
        base_resolved = base.resolve(strict=True)
    except OSError:
        _refuse("PYTHON_IMPORT_CLOSURE_INVALID", "DNRD-5 Python source root is absent")
    if (
        not base.is_dir()
        or base.is_symlink()
        or base_resolved != base.absolute()
        or not base_resolved.is_relative_to(root)
    ):
        _refuse("PYTHON_IMPORT_CLOSURE_INVALID", "DNRD-5 Python source root is absent")
    paths = sorted(
        path
        for path in base.rglob("*.py")
        if path.is_file()
        and not path.is_symlink()
        and path.resolve(strict=True) == path.absolute()
        and path.resolve(strict=True).is_relative_to(root)
    )
    if not paths:
        _refuse("PYTHON_IMPORT_CLOSURE_INVALID", "DNRD-5 Python source set is empty")
    files: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    network_modules: set[str] = set()

    for path in paths:
        relative = PurePosixPath(path.relative_to(root).as_posix())
        file_descriptor = _descriptor_within(root, path, relative.as_posix())
        raw = path.read_bytes()
        try:
            tree = ast.parse(raw, filename=relative.as_posix())
        except (SyntaxError, ValueError) as error:
            _refuse(
                "PYTHON_IMPORT_CLOSURE_INVALID",
                f"{relative.as_posix()} is not parseable Python: {error}",
            )
        files.append(
            {
                "path": relative.as_posix(),
                "byteLength": file_descriptor["byteLength"],
                "sha256": file_descriptor["sha256"],
            }
        )
        current_module = _module_name(relative)
        current_package = current_module.split(".")
        if path.name != "__init__.py":
            current_package.pop()

        for node in ast.walk(tree):
            imports: list[tuple[str, int, str, str | None]] = []
            if isinstance(node, ast.Import):
                imports.extend(
                    (alias.name, 0, alias.name, alias.asname) for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                if node.level > len(current_package):
                    _refuse(
                        "PYTHON_IMPORT_CLOSURE_INVALID",
                        f"{relative.as_posix()} relative import escapes its package",
                    )
                prefix = current_package[: len(current_package) - node.level + 1]
                module_parts = node.module.split(".") if node.module else []
                module = ".".join(prefix + module_parts) if node.level else (node.module or "")
                imports.extend(
                    (module, node.level, alias.name, alias.asname)
                    for alias in node.names
                )
            for module, level, name, alias in imports:
                root_name = module.split(".", 1)[0] if module else ""
                if root_name in _FORBIDDEN_IMPORT_ROOTS:
                    _refuse(
                        "PYTHON_DYNAMIC_IMPORT_FORBIDDEN",
                        f"{relative.as_posix()} imports {root_name}",
                    )
                resolved = (
                    _resolve_local_module(root, module)
                    if module.startswith("_research.dnrd5")
                    else None
                )
                if module.startswith("_research.dnrd5"):
                    submodule = _resolve_local_module(root, f"{module}.{name}")
                    if submodule is not None:
                        resolved = submodule
                if module.startswith("_research.dnrd5") and resolved is None:
                    _refuse(
                        "PYTHON_IMPORT_CLOSURE_INVALID",
                        f"{relative.as_posix()} cannot resolve {module}",
                    )
                if root_name in _NETWORK_CAPABLE_ROOTS:
                    classification = "NETWORK_CAPABLE_DEFERRED_DISPATCH"
                    network_modules.add(root_name)
                elif resolved is not None:
                    classification = "LOCAL_DNRD5_SOURCE"
                elif root_name in sys.stdlib_module_names:
                    classification = "PYTHON_STDLIB"
                else:
                    _refuse(
                        "PYTHON_IMPORT_CLOSURE_INVALID",
                        f"{relative.as_posix()} has unresolved non-stdlib import {module}",
                    )
                edges.append(
                    {
                        "path": relative.as_posix(),
                        "line": node.lineno,
                        "module": module,
                        "level": level,
                        "name": name,
                        "alias": alias,
                        "resolvedPath": resolved,
                        "classification": classification,
                    }
                )
        collector = _CallCollector(relative.as_posix())
        collector.visit(tree)
        calls.extend(collector.calls)

    edges.sort(
        key=lambda item: (
            item["path"],
            item["line"],
            item["module"],
            item["name"],
            item["alias"] or "",
        )
    )
    calls.sort(
        key=lambda item: (
            item["path"], item["line"], item["column"], item["callee"]
        )
    )
    return {
        "namespaceRoots": ["_research"],
        "files": files,
        "astImportEdges": edges,
        "syntacticCallSites": {
            "count": len(calls),
            "sha256": canonical_sha256(calls),
        },
        "networkCapableDeferredModules": sorted(network_modules),
        "dynamicImportPolicy": "LITERAL_IMPORT_AST_ONLY_DYNAMIC_LOADERS_FORBIDDEN",
        "filesSha256": canonical_sha256(files),
        "importGraphSha256": canonical_sha256(edges),
    }


def _node_descriptor(value: Any, label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != {"path", "byteLength", "sha256"}:
        _refuse("TS_RESOLUTION_INVALID", f"{label} descriptor shape drifted")
    _safe_relative_path(value["path"], f"{label}.path")
    if type(value["byteLength"]) is not int or value["byteLength"] < 0:
        _refuse("TS_RESOLUTION_INVALID", f"{label}.byteLength is invalid")
    if type(value["sha256"]) is not str or _SHA256.fullmatch(value["sha256"]) is None:
        _refuse("TS_RESOLUTION_INVALID", f"{label}.sha256 is invalid")
    return value


def _unique_descriptors(values: Any, label: str) -> list[Mapping[str, Any]]:
    if type(values) is not list:
        _refuse("TS_RESOLUTION_INVALID", f"{label} must be a list")
    checked = [_node_descriptor(value, f"{label}[{index}]") for index, value in enumerate(values)]
    paths = [value["path"] for value in checked]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        _refuse("TS_RESOLUTION_INVALID", f"{label} paths are not sorted unique")
    return checked


def validate_typescript_closure(raw: bytes) -> Mapping[str, Any]:
    """Validate exact Node capture bytes and recompute graph/build invariants."""

    try:
        value = parse_canonical(raw)
    except CanonicalJsonError as error:
        _refuse("TS_RESOLUTION_INVALID", f"Node closure is not canonical: {error}")
    expected_keys = {
        "contractVersion",
        "claimBoundary",
        "dispatchAuthorized",
        "dispatchBudget",
        "sourceFreezeEligible",
        "compiler",
        "entrypoints",
        "inputs",
        "emitted",
        "resolvedExternalFiles",
        "sources",
        "terminal",
    }
    if type(value) is not dict or set(value) != expected_keys:
        _refuse("TS_RESOLUTION_INVALID", "Node closure root shape drifted")
    if (
        value["contractVersion"] != TYPESCRIPT_CONTRACT_VERSION
        or value["terminal"] != TYPESCRIPT_TERMINAL
        or value["dispatchAuthorized"] is not False
        or type(value["dispatchBudget"]) is not int
        or value["dispatchBudget"] != 0
        or value["sourceFreezeEligible"] is not False
    ):
        _refuse("TS_RESOLUTION_INVALID", "Node closure claim boundary drifted")
    if value["claimBoundary"] != TYPESCRIPT_CLAIM_BOUNDARY:
        _refuse("TS_RESOLUTION_INVALID", "Node claim boundary drifted")

    inputs = _unique_descriptors(value["inputs"], "inputs")
    if tuple(item["path"] for item in inputs) != TYPESCRIPT_INPUT_PATHS:
        _refuse("TS_RESOLUTION_INVALID", "Node build input set drifted")
    external_files = _unique_descriptors(
        value["resolvedExternalFiles"], "resolvedExternalFiles"
    )
    if not external_files or any(
        not item["path"].startswith("node_modules/") for item in external_files
    ):
        _refuse("TS_RESOLUTION_INVALID", "resolved external file escaped node_modules")
    emitted = value["emitted"]
    if type(emitted) is not dict or set(emitted) != {"files", "rootSha256"}:
        _refuse("BUILD_TREE_INVALID", "emitted tree shape drifted")
    emitted_files = _unique_descriptors(emitted["files"], "emitted.files")
    if not emitted_files or emitted["rootSha256"] != canonical_sha256(emitted["files"]):
        _refuse("BUILD_TREE_INVALID", "emitted tree root mismatch")

    compiler = value["compiler"]
    if type(compiler) is not dict or set(compiler) != {
        "effectiveOptions",
        "nodeExecutable",
        "nodeVersion",
        "typescriptFiles",
        "version",
    }:
        _refuse("TOOLCHAIN_PIN_INVALID", "compiler closure shape drifted")
    _node_descriptor(compiler["nodeExecutable"], "compiler.nodeExecutable")
    compiler_files = _unique_descriptors(
        compiler["typescriptFiles"], "compiler.typescriptFiles"
    )
    if tuple(item["path"] for item in compiler_files) != TYPESCRIPT_COMPILER_PATHS:
        _refuse("TOOLCHAIN_PIN_INVALID", "TypeScript compiler file set drifted")
    if not all(type(compiler[key]) is str and compiler[key] for key in ("nodeVersion", "version")):
        _refuse("TOOLCHAIN_PIN_INVALID", "compiler version pin is absent")
    options = compiler["effectiveOptions"]
    expected_option_keys = {
        "allowImportingTsExtensions",
        "declaration",
        "declarationMap",
        "exactOptionalPropertyTypes",
        "module",
        "moduleResolution",
        "noEmit",
        "noEmitOnError",
        "noUncheckedIndexedAccess",
        "plugins",
        "rootDir",
        "sourceMap",
        "strict",
        "target",
        "types",
    }
    if type(options) is not dict or set(options) != expected_option_keys:
        _refuse("TSCONFIG_POLICY_INVALID", "effective compiler options are absent")
    required_options = {
        "allowImportingTsExtensions": False,
        "declaration": True,
        "declarationMap": True,
        "exactOptionalPropertyTypes": True,
        "noEmit": False,
        "noEmitOnError": True,
        "noUncheckedIndexedAccess": True,
        "plugins": [],
        "rootDir": "src",
        "sourceMap": True,
        "strict": True,
        "types": ["node"],
    }
    if any(options.get(key) != expected for key, expected in required_options.items()):
        _refuse("TSCONFIG_POLICY_INVALID", "effective compiler policy drifted")
    if (
        options.get("module") != 199
        or options.get("moduleResolution") != 99
        or options.get("target") != 9
    ):
        _refuse("TSCONFIG_POLICY_INVALID", "effective compiler target is absent")

    sources = value["sources"]
    if type(sources) is not list or not sources:
        _refuse("TS_RESOLUTION_INVALID", "TypeScript source closure is empty")
    source_paths: list[str] = []
    seam_hits: dict[str, list[tuple[str, Mapping[str, Any], Mapping[str, Any]]]] = {
        "commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal": [],
        "recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal": [],
    }
    allowed_kinds = {"static-import", "static-export", "type-import"}
    for index, source in enumerate(sources):
        if type(source) is not dict or set(source) != {
            "path",
            "byteLength",
            "sha256",
            "exportedSymbols",
            "imports",
        }:
            _refuse("TS_RESOLUTION_INVALID", f"sources[{index}] shape drifted")
        _node_descriptor(
            {key: source[key] for key in ("path", "byteLength", "sha256")},
            f"sources[{index}]",
        )
        source_paths.append(source["path"])
        if not source["path"].startswith("src/") or not source["path"].endswith(
            ".ts"
        ):
            _refuse("TS_RESOLUTION_INVALID", "source path escaped TypeScript src")
        symbols = source["exportedSymbols"]
        if (
            type(symbols) is not list
            or not all(type(symbol) is str and symbol for symbol in symbols)
            or symbols != sorted(set(symbols))
        ):
            _refuse("TS_RESOLUTION_INVALID", "exported symbols are not sorted unique")
        if type(source["imports"]) is not list:
            _refuse("TS_RESOLUTION_INVALID", "source imports are not a list")
        for binding in source["imports"]:
            if type(binding) is not dict or set(binding) != {
                "kind",
                "names",
                "position",
                "source",
                "target",
                "targetKind",
                "typeOnly",
            }:
                _refuse("TS_RESOLUTION_INVALID", "import binding shape drifted")
            if (
                type(binding["kind"]) is not str
                or type(binding["position"]) is not int
                or binding["position"] < 0
                or type(binding["source"]) is not str
                or not binding["source"]
                or type(binding["targetKind"]) is not str
                or type(binding["typeOnly"]) is not bool
            ):
                _refuse("TS_RESOLUTION_INVALID", "import binding fields drifted")
            if binding["kind"] not in allowed_kinds:
                _refuse("TS_RUNTIME_LOADER_FORBIDDEN", "runtime loader entered the selected graph")
            if binding["targetKind"] == "node-builtin":
                if binding["target"] is not None or not binding["source"].startswith("node:"):
                    _refuse("TS_RESOLUTION_INVALID", "node builtin binding drifted")
            elif binding["targetKind"] in {"local-source", "locked-package"}:
                _node_descriptor(binding["target"], "import target")
                target_path = binding["target"]["path"]
                expected_prefix = (
                    "src/"
                    if binding["targetKind"] == "local-source"
                    else "node_modules/"
                )
                if not target_path.startswith(expected_prefix):
                    _refuse("TS_RESOLUTION_INVALID", "import target path/class drifted")
            else:
                _refuse("TS_RESOLUTION_INVALID", "import target is unclassified")
            if type(binding["names"]) is not list:
                _refuse("TS_RESOLUTION_INVALID", "import names are absent")
            for name in binding["names"]:
                if (
                    type(name) is not dict
                    or set(name) != {"imported", "local", "typeOnly"}
                    or type(name["imported"]) is not str
                    or not name["imported"]
                    or type(name["local"]) is not str
                    or not name["local"]
                    or type(name["typeOnly"]) is not bool
                ):
                    _refuse("TS_RESOLUTION_INVALID", "import name shape drifted")
            if binding["names"] != sorted(
                binding["names"],
                key=lambda name: (name["imported"], name["local"]),
            ):
                _refuse("TS_RESOLUTION_INVALID", "import names are not sorted")
            if binding["kind"] == "type-import" and binding["typeOnly"] is not True:
                _refuse("TS_RESOLUTION_INVALID", "type import lost its type-only flag")
            for name in binding["names"]:
                if (
                    type(name) is dict
                    and name.get("imported") in seam_hits
                ):
                    seam_hits[name["imported"]].append(
                        (source["path"], binding, name)
                    )
    if source_paths != sorted(source_paths) or len(source_paths) != len(set(source_paths)):
        _refuse("TS_RESOLUTION_INVALID", "TypeScript source paths are not sorted unique")
    entrypoints = value["entrypoints"]
    if (
        type(entrypoints) is not list
        or not all(type(entrypoint) is str and entrypoint for entrypoint in entrypoints)
        or entrypoints != sorted(set(entrypoints))
    ):
        _refuse("TS_RESOLUTION_INVALID", "TypeScript entrypoints are not sorted unique")
    if tuple(entrypoints) != TYPESCRIPT_ENTRYPOINTS:
        _refuse("TS_RESOLUTION_INVALID", "TypeScript entrypoint set drifted")
    if not set(entrypoints).issubset(source_paths):
        _refuse("TS_RESOLUTION_INVALID", "entrypoint escaped the resolved source graph")
    for symbol, hits in seam_hits.items():
        if len(hits) != 1:
            _refuse(
                "TS_DISPATCH_SEAM_INVALID",
                f"durable dispatcher seam importer set drifted for {symbol}",
            )
        path, binding, name = hits[0]
        target = binding["target"]
        if (
            path != "src/canonical-atom-v2-dnrd5-durable-permit.ts"
            or binding["kind"] != "static-import"
            or binding["source"] != "./canonical-atom-v2-durable-runtime.js"
            or binding["targetKind"] != "local-source"
            or binding["typeOnly"] is not False
            or name["local"] != symbol
            or name["typeOnly"] is not False
            or type(target) is not dict
            or target.get("path") != "src/canonical-atom-v2-durable-runtime.ts"
        ):
            _refuse(
                "TS_DISPATCH_SEAM_INVALID",
                f"durable dispatcher seam binding drifted for {symbol}",
            )
    return value


def _verify_selected_worktree_bytes(root: Path, source: Mapping[str, Any]) -> None:
    for record in source["selectedTrackedFiles"]:
        current = _descriptor_within(
            root, root / record["path"], record["path"]
        )
        if (
            current["byteLength"] != record["byteLength"]
            or current["sha256"] != record["sha256"]
        ):
            _refuse("SOURCE_BLOB_DRIFT", f"worktree byte drift at {record['path']}")


def _same_descriptor(
    expected: Mapping[str, Any], actual: Mapping[str, Any], label: str
) -> None:
    if dict(expected) != dict(actual):
        _refuse("SOURCE_BLOB_DRIFT", f"physical descriptor drift at {label}")


def _verify_typescript_physical_inputs(
    root: Path,
    typescript: Mapping[str, Any],
    node_executable: Path,
) -> None:
    package = root / PACKAGE_ROOT
    _same_descriptor(
        typescript["compiler"]["nodeExecutable"],
        _descriptor(node_executable, "external-runtime/node"),
        "external-runtime/node",
    )
    descriptor_groups = (
        typescript["inputs"],
        typescript["compiler"]["typescriptFiles"],
        typescript["resolvedExternalFiles"],
        typescript["sources"],
    )
    for group in descriptor_groups:
        for expected in group:
            path = expected["path"]
            actual = _descriptor_within(package, package / path, path)
            _same_descriptor(
                {key: expected[key] for key in ("path", "byteLength", "sha256")},
                actual,
                path,
            )
    for source in typescript["sources"]:
        for binding in source["imports"]:
            target = binding["target"]
            if target is None:
                continue
            path = target["path"]
            actual = _descriptor_within(package, package / path, path)
            _same_descriptor(target, actual, f"import target {path}")


def _resolve_node_executable(environment: Mapping[str, str] | None) -> Path:
    search_path = environment.get("PATH") if environment is not None else None
    candidate = shutil.which("node", path=search_path)
    if candidate is None:
        _refuse("LOCAL_TOOL_EXECUTION_FAILED", "node executable is unavailable")
    executable = Path(candidate).resolve()
    _descriptor(executable, "external-runtime/node")
    return executable


def capture_local_source_build_import_closure(
    repo_root: Path,
    *,
    commit: str = "HEAD",
    require_detached_clean: bool = True,
    environment: Mapping[str, str] | None = None,
) -> CapturedSourceBuildImportClosure:
    """Join independently rederived local evidence into one bounded manifest."""

    root = repo_root.resolve()
    source = collect_git_source(
        root, commit, require_detached_clean=require_detached_clean
    )
    _verify_selected_worktree_bytes(root, source)
    python = resolve_python_ast_closure(root)
    selected_python_paths = sorted(
        item["path"]
        for item in source["selectedTrackedFiles"]
        if item["path"].startswith("_research/dnrd5/")
        and item["path"].endswith(".py")
    )
    ast_python_paths = [item["path"] for item in python["files"]]
    if selected_python_paths != ast_python_paths:
        _refuse(
            "PYTHON_IMPORT_CLOSURE_INVALID",
            "Git-selected and AST-parsed DNRD-5 Python source sets differ",
        )
    node_executable = _resolve_node_executable(environment)
    node = _run(
        (
            str(node_executable),
            str(NODE_CAPTURE.relative_to(PACKAGE_ROOT)),
        ),
        cwd=root / PACKAGE_ROOT,
        environment=environment,
        timeout=300,
    )
    typescript_raw = node.stdout
    if len(typescript_raw) > 2_000_000:
        _refuse("TS_RESOLUTION_INVALID", "Node closure exceeds local size ceiling")
    typescript = validate_typescript_closure(typescript_raw)
    _verify_typescript_physical_inputs(root, typescript, node_executable)
    _verify_selected_worktree_bytes(root, source)
    if require_detached_clean and _git(
        root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    ):
        _refuse("WORKTREE_NOT_DETACHED_CLEAN", "capture changed the checkout")
    selected_by_path = {
        item["path"]: item for item in source["selectedTrackedFiles"]
    }
    evidence_pins: list[dict[str, Any]] = []
    for role, path in _CRITICAL_ARTIFACTS:
        record = selected_by_path.get(path.as_posix())
        if record is None:
            _refuse("EVIDENCE_PIN_INVALID", f"missing selected artifact {path}")
        evidence_pins.append(
            {
                "role": role,
                "path": record["path"],
                "mode": record["mode"],
                "gitBlobOid": record["gitBlobOid"],
                "byteLength": record["byteLength"],
                "sha256": record["sha256"],
            }
        )
    for record in typescript["sources"]:
        path = (PACKAGE_ROOT / record["path"]).as_posix()
        selected = selected_by_path.get(path)
        if selected is None or (
            selected["byteLength"], selected["sha256"]
        ) != (record["byteLength"], record["sha256"]):
            _refuse("SOURCE_BLOB_DRIFT", f"TypeScript source/Git mismatch at {path}")

    executable = _descriptor(
        Path(sys.executable).resolve(), "external-runtime/python"
    )
    manifest: dict[str, Any] = {
        "_tag": "Dnrd5LocalSourceBuildImportClosure",
        "contractVersion": CONTRACT_VERSION,
        "claimBoundary": CLAIM_BOUNDARY,
        "dispatchAuthorized": False,
        "dispatchBudget": 0,
        "sourceFreezeEligible": False,
        "providerOrModelCalls": 0,
        "source": source,
        "toolchains": {
            "python": {
                "implementation": platform.python_implementation(),
                "version": platform.python_version(),
                "cacheTag": sys.implementation.cache_tag,
                "unicodeVersion": unicodedata.unidata_version,
                "executable": executable,
            },
            "typescriptManifestSha256": sha256(typescript_raw).hexdigest(),
        },
        "python": python,
        "typescript": typescript,
        "evidencePins": evidence_pins,
        "terminal": TERMINAL,
    }
    raw = canonical_bytes(manifest)
    descriptor = {
        "mediaType": "application/vnd.hswm.dnrd5-local-source-build-import-closure-v1+json",
        "byteLength": len(raw),
        "sha256": sha256(raw).hexdigest(),
    }
    return CapturedSourceBuildImportClosure(manifest, raw, descriptor)


def capture_detached_offline(
    repo_root: Path, commit: str = "HEAD"
) -> CapturedSourceBuildImportClosure:
    """Build from a local detached clone with npm forced to offline mode."""

    source_root = repo_root.resolve()
    oid = _text(
        _git(
            source_root,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{commit}^{{commit}}",
        ),
        "commit OID",
    ).strip()
    with tempfile.TemporaryDirectory(prefix="hswm-dnrd5-source-closure-") as temporary:
        snapshot = Path(temporary) / "repository"
        _run(
            (
                "git",
                "clone",
                "--shared",
                "--no-checkout",
                "--quiet",
                str(source_root),
                str(snapshot),
            ),
            cwd=Path(temporary),
        )
        _run(("git", "checkout", "--detach", "--quiet", oid), cwd=snapshot)
        package = snapshot / PACKAGE_ROOT
        environment = {
            "PATH": os.environ.get("PATH", os.defpath),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TZ": "UTC",
            "npm_config_cache": str((Path.home() / ".npm").resolve()),
            "npm_config_userconfig": str((package / ".npmrc").resolve()),
            "npm_config_offline": "true",
            "npm_config_ignore_scripts": "true",
            "npm_config_audit": "false",
            "npm_config_fund": "false",
            "npm_config_update_notifier": "false",
            "HTTP_PROXY": "",
            "HTTPS_PROXY": "",
            "ALL_PROXY": "",
            "NO_PROXY": "*",
        }
        _run(
            (
                "npm",
                "ci",
                "--offline",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
            ),
            cwd=package,
            environment=environment,
            timeout=600,
        )
        return capture_local_source_build_import_closure(
            snapshot,
            commit=oid,
            require_detached_clean=True,
            environment=environment,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="derive local DNRD-5 source/build/import closure without dispatch"
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--commit", default="HEAD")
    arguments = parser.parse_args(argv)
    try:
        captured = capture_detached_offline(arguments.repo, arguments.commit)
    except SourceBuildImportClosureRefusal as error:
        sys.stderr.buffer.write(
            canonical_bytes(
                {
                    "error": {
                        "code": error.code,
                        "detail": error.detail,
                        "terminal": error.terminal,
                        "dispatchAuthorized": False,
                        "dispatchBudget": 0,
                    }
                }
            )
        )
        return 1
    sys.stdout.buffer.write(captured.raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
