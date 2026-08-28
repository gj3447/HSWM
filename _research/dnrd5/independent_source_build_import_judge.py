"""Independent, fail-closed judge for DNRD-5 local source/build closure.

This is deliberately a second implementation.  It does not import the
capture module, its constants, the provider gateway, or TypeScript tooling.
It can establish only a structural, local-byte closure: a valid result is not
a Source-A authorization, a provider/model occurrence, an emitted-byte
rebuild, or an independent proof of compiler semantics.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import new as hash_new
from hashlib import sha256
from pathlib import Path, PurePosixPath
import os
import re
import stat
import subprocess
import sys
from typing import Any, Mapping, NoReturn, Sequence

from _research.dnrd5.canonical_json import (
    CanonicalJsonError,
    canonical_bytes,
    canonical_sha256,
    parse_canonical,
)


_HEX_256 = re.compile(r"^[0-9a-f]{64}$")
_OID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_MODES = frozenset(("100644", "100755"))


class IndependentSourceBuildImportJudgeRefusal(ValueError):
    """Typed refusal; this judge never turns a malformed closure into authority."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.terminal = "INDEPENDENT_LOCAL_SOURCE_BUILD_IMPORT_CLOSURE_REFUSED_NO_DISPATCH"
        self.dispatch_authorized = False
        self.dispatch_budget = 0
        self.source_freeze_eligible = False


@dataclass(frozen=True, slots=True)
class IndependentSourceBuildImportJudgeResult:
    """A bounded structural conclusion, deliberately not an occurrence claim."""

    terminal: str
    manifest_sha256: str
    source_commit: str
    physical_repository_verified: bool
    external_toolchains_verified: bool
    python_import_graph_independently_verified: bool
    python_call_summary_independently_verified: bool
    emitted_bytes_independently_verified: bool
    compiler_semantics_independently_verified: bool
    source_a_authorized: bool
    provider_or_model_calls: int


def _refuse(code: str, detail: str) -> NoReturn:
    raise IndependentSourceBuildImportJudgeRefusal(code, detail)


def _object(value: Any, label: str, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        _refuse("SHAPE_INVALID", f"{label} has an unexpected field set")
    return value


def _text(value: Any, label: str, *, nonempty: bool = True) -> str:
    if type(value) is not str or (nonempty and not value):
        _refuse("TYPE_INVALID", f"{label} must be a {'nonempty ' if nonempty else ''}string")
    try:
        value.encode("utf-8", "strict")
    except UnicodeEncodeError:
        _refuse("TYPE_INVALID", f"{label} is not a Unicode scalar string")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _refuse("TYPE_INVALID", f"{label} must be an integer >= {minimum}")
    return value


def _digest(value: Any, label: str) -> str:
    value = _text(value, label)
    if _HEX_256.fullmatch(value) is None:
        _refuse("HASH_INVALID", f"{label} must be lowercase SHA-256")
    return value


def _safe_path(value: Any, label: str, *, allow_root: bool = False) -> str:
    value = _text(value, label)
    if allow_root and value == ".":
        return value
    if "\\" in value or "\x00" in value:
        _refuse("PATH_CLOSURE_INVALID", f"{label} is not POSIX")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        _refuse("PATH_CLOSURE_INVALID", f"{label} escapes its root")
    return path.as_posix()


def _hash_descriptor(value: Any, label: str) -> dict[str, Any]:
    row = _object(value, label, {"byteLength", "sha256"})
    _integer(row["byteLength"], f"{label}.byteLength")
    _digest(row["sha256"], f"{label}.sha256")
    return row


def _file_descriptor(value: Any, label: str) -> dict[str, Any]:
    row = _object(value, label, {"path", "byteLength", "sha256"})
    _safe_path(row["path"], f"{label}.path")
    _integer(row["byteLength"], f"{label}.byteLength")
    _digest(row["sha256"], f"{label}.sha256")
    return row


def _same_descriptor(left: Mapping[str, Any], right: Mapping[str, Any], label: str) -> None:
    if dict(left) != dict(right):
        _refuse("CROSS_REFERENCE_INVALID", f"descriptor differs at {label}")


def _same_bytes(left: Mapping[str, Any], right: Mapping[str, Any], label: str) -> None:
    if (left["byteLength"], left["sha256"]) != (right["byteLength"], right["sha256"]):
        _refuse("CROSS_REFERENCE_INVALID", f"byte descriptor differs at {label}")


def _sorted_unique_descriptors(
    value: Any,
    label: str,
    *, allow_empty: bool = False,
) -> list[dict[str, Any]]:
    if type(value) is not list or (not allow_empty and not value):
        _refuse("DESCRIPTOR_SET_INVALID", f"{label} must be a nonempty list")
    rows = [_file_descriptor(item, f"{label}[{index}]") for index, item in enumerate(value)]
    paths = [row["path"] for row in rows]
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        _refuse("DESCRIPTOR_SET_INVALID", f"{label} paths are not sorted unique")
    return rows


def _oid(value: Any, object_format: str, label: str) -> str:
    value = _text(value, label)
    expected = 40 if object_format == "sha1" else 64
    if len(value) != expected or _OID.fullmatch(value) is None:
        _refuse("GIT_OBJECT_INVALID", f"{label} has the wrong Git object shape")
    return value


def _require_exact_claims(manifest: Mapping[str, Any]) -> None:
    # These literals are the independently frozen wire vocabulary, not imports
    # from the capture implementation.
    if manifest["_tag"] != "Dnrd5LocalSourceBuildImportClosure":
        _refuse("IDENTITY_INVALID", "unexpected closure tag")
    if manifest["contractVersion"] != "hswm-dnrd5-local-source-build-import-closure/v1":
        _refuse("IDENTITY_INVALID", "unexpected closure version")
    if manifest["claimBoundary"] != (
        "LOCAL_GIT_AST_COMPILER_AND_BUILD_IDENTITY_ONLY_NOT_COMPILER_SOUNDNESS_"
        "REMOTE_PROVENANCE_NETWORK_SYSCALL_ABSENCE_SOURCE_A_AUTHORITY_PROVIDER_"
        "OCCURRENCE_LEARNING_OR_SCIENTIFIC_RESULT"
    ):
        _refuse("CLAIM_BOUNDARY_INVALID", "outer claim boundary drifted")
    if manifest["terminal"] != (
        "LOCAL_SOURCE_BUILD_IMPORT_CLOSURE_REDERIVED_"
        "NOT_SOURCE_A_PROVIDER_OCCURRENCE_OR_EFFICACY"
    ):
        _refuse("CLAIM_BOUNDARY_INVALID", "outer terminal drifted")
    if manifest["dispatchAuthorized"] is not False:
        _refuse("CLAIM_BOUNDARY_INVALID", "dispatch must remain false")
    if type(manifest["dispatchBudget"]) is not int or manifest["dispatchBudget"] != 0:
        _refuse("CLAIM_BOUNDARY_INVALID", "dispatch budget must be exact integer zero")
    if manifest["sourceFreezeEligible"] is not False:
        _refuse("CLAIM_BOUNDARY_INVALID", "source freeze eligibility must remain false")
    if type(manifest["providerOrModelCalls"]) is not int or manifest["providerOrModelCalls"] != 0:
        _refuse("CLAIM_BOUNDARY_INVALID", "provider/model call count must be exact integer zero")


def _validate_source(value: Any) -> dict[str, Any]:
    source = _object(
        value,
        "source",
        {
            "gitObjectFormat",
            "commit",
            "tree",
            "commitObject",
            "treeObject",
            "treeObjects",
            "treeObjectsSha256",
            "detachedClean",
            "cleanPolicy",
            "selectedTrackedFiles",
            "selectedTrackedFilesSha256",
        },
    )
    object_format = source["gitObjectFormat"]
    if type(object_format) is not str or object_format not in {"sha1", "sha256"}:
        _refuse("GIT_OBJECT_INVALID", "unsupported Git object format")
    _oid(source["commit"], object_format, "source.commit")
    _oid(source["tree"], object_format, "source.tree")
    _hash_descriptor(source["commitObject"], "source.commitObject")
    _hash_descriptor(source["treeObject"], "source.treeObject")
    if source["detachedClean"] is not True:
        _refuse("GIT_CAPTURE_POLICY_INVALID", "source capture must be detached and clean")
    if source["cleanPolicy"] != (
        "DETACHED_HEAD_EQUALS_REQUESTED_COMMIT_AND_GIT_STATUS_PORCELAIN_V1_"
        "UNTRACKED_ALL_EMPTY_IGNORED_BUILD_INPUTS_CAPTURED_SEPARATELY"
    ):
        _refuse("GIT_CAPTURE_POLICY_INVALID", "clean policy drifted")

    raw_trees = source["treeObjects"]
    if type(raw_trees) is not list or not raw_trees:
        _refuse("GIT_TREE_INVALID", "tree object list is absent")
    trees: list[dict[str, Any]] = []
    for index, item in enumerate(raw_trees):
        row = _object(item, f"source.treeObjects[{index}]", {"path", "gitTreeOid", "byteLength", "sha256"})
        _safe_path(row["path"], f"source.treeObjects[{index}].path", allow_root=True)
        _oid(row["gitTreeOid"], object_format, f"source.treeObjects[{index}].gitTreeOid")
        _integer(row["byteLength"], f"source.treeObjects[{index}].byteLength")
        _digest(row["sha256"], f"source.treeObjects[{index}].sha256")
        trees.append(row)
    tree_paths = [row["path"] for row in trees]
    if tree_paths != sorted(tree_paths) or len(tree_paths) != len(set(tree_paths)):
        _refuse("GIT_TREE_INVALID", "tree object paths are not sorted unique")
    if trees[0]["path"] != "." or trees[0]["gitTreeOid"] != source["tree"]:
        _refuse("GIT_TREE_INVALID", "root tree descriptor does not bind source.tree")
    if source["treeObjectsSha256"] != canonical_sha256(trees):
        _refuse("GIT_TREE_INVALID", "tree object Merkle root drifted")

    raw_selected = source["selectedTrackedFiles"]
    if type(raw_selected) is not list or not raw_selected:
        _refuse("GIT_SELECTION_INVALID", "selected Git file list is absent")
    selected: list[dict[str, Any]] = []
    for index, item in enumerate(raw_selected):
        row = _object(
            item,
            f"source.selectedTrackedFiles[{index}]",
            {"path", "mode", "gitBlobOid", "byteLength", "sha256"},
        )
        path = _safe_path(row["path"], f"source.selectedTrackedFiles[{index}].path")
        if type(row["mode"]) is not str or row["mode"] not in _MODES:
            _refuse("GIT_SELECTION_INVALID", f"selected mode invalid at {path}")
        _oid(row["gitBlobOid"], object_format, f"source.selectedTrackedFiles[{index}].gitBlobOid")
        _integer(row["byteLength"], f"source.selectedTrackedFiles[{index}].byteLength")
        _digest(row["sha256"], f"source.selectedTrackedFiles[{index}].sha256")
        selected.append(row)
    selected_paths = [row["path"] for row in selected]
    if selected_paths != sorted(selected_paths) or len(selected_paths) != len(set(selected_paths)):
        _refuse("GIT_SELECTION_INVALID", "selected Git paths are not sorted unique")
    if any(not _judge_selected_path(path) for path in selected_paths):
        _refuse("GIT_SELECTION_INVALID", "selected Git path is outside the frozen closure policy")
    if source["selectedTrackedFilesSha256"] != canonical_sha256(selected):
        _refuse("GIT_SELECTION_INVALID", "selected Git Merkle root drifted")
    parents = {"."}
    for path in selected_paths:
        current = PurePosixPath(path).parent
        while current.parts:
            parents.add(current.as_posix())
            current = current.parent
    if not parents.issubset(set(tree_paths)):
        _refuse("GIT_TREE_INVALID", "selected path has no declared tree ancestor")
    return source


def _validate_python(value: Any, selected: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    python = _object(
        value,
        "python",
        {
            "namespaceRoots",
            "files",
            "astImportEdges",
            "syntacticCallSites",
            "networkCapableDeferredModules",
            "dynamicImportPolicy",
            "filesSha256",
            "importGraphSha256",
        },
    )
    if python["namespaceRoots"] != ["_research"]:
        _refuse("PYTHON_CLOSURE_INVALID", "unexpected Python namespace root")
    files = _sorted_unique_descriptors(python["files"], "python.files")
    paths = [row["path"] for row in files]
    if any(not path.startswith("_research/dnrd5/") or not path.endswith(".py") for path in paths):
        _refuse("PYTHON_CLOSURE_INVALID", "Python file escaped selected DNRD-5 source")
    selected_python = sorted(
        path for path in selected if path.startswith("_research/dnrd5/") and path.endswith(".py")
    )
    if paths != selected_python:
        _refuse("PYTHON_CLOSURE_INVALID", "AST file set differs from Git-selected Python files")
    for row in files:
        selected_row = selected.get(row["path"])
        if selected_row is None:
            _refuse("PYTHON_CLOSURE_INVALID", f"missing Git row for {row['path']}")
        _same_bytes(row, selected_row, row["path"])
    if python["filesSha256"] != canonical_sha256(files):
        _refuse("PYTHON_CLOSURE_INVALID", "Python file root drifted")
    if python["dynamicImportPolicy"] != "LITERAL_IMPORT_AST_ONLY_DYNAMIC_LOADERS_FORBIDDEN":
        _refuse("PYTHON_CLOSURE_INVALID", "Python dynamic import policy drifted")

    raw_edges = python["astImportEdges"]
    if type(raw_edges) is not list:
        _refuse("PYTHON_CLOSURE_INVALID", "Python import graph is not a list")
    allowed_classes = {"NETWORK_CAPABLE_DEFERRED_DISPATCH", "LOCAL_DNRD5_SOURCE", "PYTHON_STDLIB"}
    edges: list[dict[str, Any]] = []
    for index, item in enumerate(raw_edges):
        row = _object(
            item,
            f"python.astImportEdges[{index}]",
            {"path", "line", "module", "level", "name", "alias", "resolvedPath", "classification"},
        )
        if row["path"] not in set(paths):
            _refuse("PYTHON_CLOSURE_INVALID", "import edge caller is outside Python file set")
        _integer(row["line"], f"python.astImportEdges[{index}].line", minimum=1)
        _text(row["module"], f"python.astImportEdges[{index}].module", nonempty=False)
        _integer(row["level"], f"python.astImportEdges[{index}].level")
        _text(row["name"], f"python.astImportEdges[{index}].name")
        if row["alias"] is not None:
            _text(row["alias"], f"python.astImportEdges[{index}].alias")
        if row["resolvedPath"] is not None:
            _safe_path(row["resolvedPath"], f"python.astImportEdges[{index}].resolvedPath")
            if row["resolvedPath"] not in set(paths):
                _refuse("PYTHON_CLOSURE_INVALID", "local import resolves outside Python file set")
        if type(row["classification"]) is not str or row["classification"] not in allowed_classes:
            _refuse("PYTHON_CLOSURE_INVALID", "unknown Python import classification")
        module_root = row["module"].split(".", 1)[0]
        if module_root in {"http", "socket", "ssl", "urllib"} and row["classification"] != "NETWORK_CAPABLE_DEFERRED_DISPATCH":
            _refuse("PYTHON_CLOSURE_INVALID", "network-capable Python import was hidden")
        if row["classification"] == "NETWORK_CAPABLE_DEFERRED_DISPATCH" and module_root not in {"http", "socket", "ssl", "urllib"}:
            _refuse("PYTHON_CLOSURE_INVALID", "unrecognized network-capable Python import")
        if row["classification"] == "LOCAL_DNRD5_SOURCE" and row["resolvedPath"] is None:
            _refuse("PYTHON_CLOSURE_INVALID", "local Python import lacks a resolved path")
        if row["classification"] != "LOCAL_DNRD5_SOURCE" and row["resolvedPath"] is not None:
            _refuse("PYTHON_CLOSURE_INVALID", "non-local Python import has a local path")
        edges.append(row)
    edge_key = lambda row: (row["path"], row["line"], row["module"], row["name"], row["alias"] or "")
    if edges != sorted(edges, key=edge_key) or len({canonical_bytes(row) for row in edges}) != len(edges):
        _refuse("PYTHON_CLOSURE_INVALID", "Python import graph is not sorted unique")
    if python["importGraphSha256"] != canonical_sha256(edges):
        _refuse("PYTHON_CLOSURE_INVALID", "Python import root drifted")
    network_roots = sorted({row["module"].split(".", 1)[0] for row in edges if row["classification"] == "NETWORK_CAPABLE_DEFERRED_DISPATCH"})
    modules = python["networkCapableDeferredModules"]
    if type(modules) is not list or not all(type(item) is str and item for item in modules) or modules != sorted(set(modules)):
        _refuse("PYTHON_CLOSURE_INVALID", "network-capable module list is not sorted unique")
    if modules != network_roots:
        _refuse("PYTHON_CLOSURE_INVALID", "network-capable classification list drifted")
    calls = _object(python["syntacticCallSites"], "python.syntacticCallSites", {"count", "sha256"})
    _integer(calls["count"], "python.syntacticCallSites.count")
    _digest(calls["sha256"], "python.syntacticCallSites.sha256")
    return python


def _validate_typescript(value: Any, selected: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    typescript = _object(
        value,
        "typescript",
        {
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
        },
    )
    if typescript["contractVersion"] != "hswm-dnrd5-local-source-build-import-closure/v1":
        _refuse("TS_IDENTITY_INVALID", "TypeScript contract version drifted")
    if typescript["claimBoundary"] != (
        "LOCAL_REDERIVATION_ONLY_NO_NETWORK_AUTHORITY_SOURCE_FREEZE_PROVIDER_"
        "OCCURRENCE_OR_SCIENTIFIC_RESULT"
    ) or typescript["terminal"] != "LOCAL_SOURCE_BUILD_IMPORT_CLOSURE_ONLY_NOT_SOURCE_A_PROVIDER_OR_EFFICACY":
        _refuse("TS_IDENTITY_INVALID", "TypeScript claim/terminal drifted")
    if typescript["dispatchAuthorized"] is not False or typescript["sourceFreezeEligible"] is not False:
        _refuse("TS_IDENTITY_INVALID", "TypeScript authority flag drifted")
    if type(typescript["dispatchBudget"]) is not int or typescript["dispatchBudget"] != 0:
        _refuse("TS_IDENTITY_INVALID", "TypeScript budget must be exact integer zero")

    expected_inputs = (
        ".npmrc",
        "package-lock.json",
        "package.json",
        "tsconfig.build.json",
        "tsconfig.dnrd5-source-closure.json",
        "tsconfig.json",
    )
    inputs = _sorted_unique_descriptors(typescript["inputs"], "typescript.inputs")
    if tuple(row["path"] for row in inputs) != expected_inputs:
        _refuse("TS_INPUT_INVALID", "TypeScript input set drifted")
    package_prefix = "src/hswm/effect-runtime/"
    for row in inputs:
        selected_row = selected.get(package_prefix + row["path"])
        if selected_row is None:
            _refuse("TS_INPUT_INVALID", f"Git source omits build input {row['path']}")
        _same_bytes(row, selected_row, row["path"])

    emitted = _object(typescript["emitted"], "typescript.emitted", {"files", "rootSha256"})
    emitted_files = _sorted_unique_descriptors(emitted["files"], "typescript.emitted.files")
    if emitted["rootSha256"] != canonical_sha256(emitted_files):
        _refuse("TS_EMITTED_ROOT_INVALID", "emitted file root drifted")

    compiler = _object(
        typescript["compiler"],
        "typescript.compiler",
        {"effectiveOptions", "nodeExecutable", "nodeVersion", "typescriptFiles", "version"},
    )
    node = _file_descriptor(compiler["nodeExecutable"], "typescript.compiler.nodeExecutable")
    if node["path"] != "external-runtime/node":
        _refuse("TOOLCHAIN_PIN_INVALID", "node executable identity drifted")
    _text(compiler["nodeVersion"], "typescript.compiler.nodeVersion")
    _text(compiler["version"], "typescript.compiler.version")
    compiler_files = _sorted_unique_descriptors(compiler["typescriptFiles"], "typescript.compiler.typescriptFiles")
    if tuple(row["path"] for row in compiler_files) != (
        "node_modules/typescript/lib/tsc.js",
        "node_modules/typescript/lib/typescript.js",
        "node_modules/typescript/package.json",
    ):
        _refuse("TOOLCHAIN_PIN_INVALID", "TypeScript compiler file set drifted")
    options = _object(
        compiler["effectiveOptions"],
        "typescript.compiler.effectiveOptions",
        {
            "allowImportingTsExtensions", "declaration", "declarationMap", "exactOptionalPropertyTypes",
            "module", "moduleResolution", "noEmit", "noEmitOnError", "noUncheckedIndexedAccess",
            "plugins", "rootDir", "sourceMap", "strict", "target", "types",
        },
    )
    wanted_bools = {
        "allowImportingTsExtensions": False,
        "declaration": True,
        "declarationMap": True,
        "exactOptionalPropertyTypes": True,
        "noEmit": False,
        "noEmitOnError": True,
        "noUncheckedIndexedAccess": True,
        "sourceMap": True,
        "strict": True,
    }
    if any(options[key] is not wanted for key, wanted in wanted_bools.items()):
        _refuse("TSCONFIG_POLICY_INVALID", "TypeScript boolean compiler policy drifted")
    if options["plugins"] != [] or options["rootDir"] != "src" or options["types"] != ["node"]:
        _refuse("TSCONFIG_POLICY_INVALID", "TypeScript compiler policy drifted")
    for key, expected in (("module", 199), ("moduleResolution", 99), ("target", 9)):
        _integer(options[key], f"typescript.compiler.effectiveOptions.{key}", minimum=1)
        if options[key] != expected:
            _refuse("TSCONFIG_POLICY_INVALID", f"TypeScript {key} compiler policy drifted")

    external = _sorted_unique_descriptors(typescript["resolvedExternalFiles"], "typescript.resolvedExternalFiles")
    if any(not row["path"].startswith("node_modules/") for row in external):
        _refuse("TS_IMPORT_INVALID", "resolved external path escaped locked package tree")
    external_by_path = {row["path"]: row for row in external}
    raw_sources = typescript["sources"]
    if type(raw_sources) is not list or not raw_sources:
        _refuse("TS_SOURCE_INVALID", "TypeScript source closure is absent")
    sources: list[dict[str, Any]] = []
    source_paths: list[str] = []
    for index, item in enumerate(raw_sources):
        row = _object(item, f"typescript.sources[{index}]", {"path", "byteLength", "sha256", "exportedSymbols", "imports"})
        descriptor = _file_descriptor({key: row[key] for key in ("path", "byteLength", "sha256")}, f"typescript.sources[{index}]")
        if not descriptor["path"].startswith("src/") or not descriptor["path"].endswith(".ts"):
            _refuse("TS_SOURCE_INVALID", "TypeScript source escaped src/*.ts")
        symbols = row["exportedSymbols"]
        if type(symbols) is not list or not all(type(symbol) is str and symbol for symbol in symbols) or symbols != sorted(set(symbols)):
            _refuse("TS_SOURCE_INVALID", "exported symbols are not sorted unique")
        if type(row["imports"]) is not list:
            _refuse("TS_IMPORT_INVALID", "TypeScript imports are not a list")
        selected_row = selected.get(package_prefix + descriptor["path"])
        if selected_row is None:
            _refuse("TS_SOURCE_INVALID", f"Git source omits TypeScript source {descriptor['path']}")
        _same_bytes(descriptor, selected_row, descriptor["path"])
        sources.append(row)
        source_paths.append(descriptor["path"])
    if source_paths != sorted(source_paths) or len(source_paths) != len(set(source_paths)):
        _refuse("TS_SOURCE_INVALID", "TypeScript source paths are not sorted unique")
    source_by_path = {row["path"]: row for row in sources}

    seam_hits: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
    for row in sources:
        imports = row["imports"]
        checked_imports: list[dict[str, Any]] = []
        for index, binding_value in enumerate(imports):
            binding = _object(
                binding_value,
                f"typescript import {row['path']}[{index}]",
                {"kind", "names", "position", "source", "target", "targetKind", "typeOnly"},
            )
            if type(binding["kind"]) is not str or binding["kind"] not in {"static-import", "static-export", "type-import"}:
                _refuse("TS_RUNTIME_LOADER_FORBIDDEN", "non-static module loader entered closure")
            _integer(binding["position"], f"typescript import {row['path']}[{index}].position")
            _text(binding["source"], f"typescript import {row['path']}[{index}].source")
            if type(binding["typeOnly"]) is not bool:
                _refuse("TYPE_INVALID", "TypeScript import typeOnly must be boolean")
            target_kind = binding["targetKind"]
            if type(target_kind) is not str:
                _refuse("TYPE_INVALID", "TypeScript import targetKind must be a string")
            if target_kind == "node-builtin":
                if binding["target"] is not None or not binding["source"].startswith("node:"):
                    _refuse("TS_IMPORT_INVALID", "node builtin target drifted")
            elif target_kind in {"local-source", "locked-package"}:
                target = _file_descriptor(binding["target"], "TypeScript import target")
                prefix = "src/" if target_kind == "local-source" else "node_modules/"
                if not target["path"].startswith(prefix):
                    _refuse("TS_IMPORT_INVALID", "TypeScript target/class mismatch")
                known = source_by_path.get(target["path"]) if target_kind == "local-source" else external_by_path.get(target["path"])
                if known is None:
                    _refuse("TS_IMPORT_INVALID", "TypeScript target is outside resolved closure")
                _same_descriptor(target, {key: known[key] for key in ("path", "byteLength", "sha256")}, target["path"])
            else:
                _refuse("TS_IMPORT_INVALID", "TypeScript target is unclassified")
            names = binding["names"]
            if type(names) is not list:
                _refuse("TS_IMPORT_INVALID", "TypeScript import names are absent")
            checked_names: list[dict[str, Any]] = []
            for name_index, name_value in enumerate(names):
                name = _object(name_value, f"TypeScript import name {row['path']}[{index}][{name_index}]", {"imported", "local", "typeOnly"})
                _text(name["imported"], "TypeScript import name.imported")
                _text(name["local"], "TypeScript import name.local")
                if type(name["typeOnly"]) is not bool:
                    _refuse("TYPE_INVALID", "TypeScript import name.typeOnly must be boolean")
                checked_names.append(name)
                if name["imported"] == "commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal":
                    seam_hits.append((row["path"], binding, name))
            name_keys = [(name["imported"], name["local"]) for name in checked_names]
            if name_keys != sorted(name_keys) or len(name_keys) != len(set(name_keys)):
                _refuse("TS_IMPORT_INVALID", "TypeScript import names are not sorted unique")
            checked_imports.append(binding)
        import_keys = [(binding["position"], binding["kind"]) for binding in checked_imports]
        if import_keys != sorted(import_keys) or len(import_keys) != len(set(import_keys)):
            _refuse("TS_IMPORT_INVALID", "TypeScript imports are not strictly ordered")

    expected_entrypoints = (
        "src/canonical-atom-v2-dnrd5-durable-permit.ts",
        "src/canonical-atom-v2-dnrd5-nine-call.ts",
        "src/canonical-atom-v2-dnrd5-plan-json.ts",
        "src/canonical-atom-v2-dnrd5-randomization.ts",
        "src/canonical-atom-v2-dnrd5-v2-audit-release.ts",
        "src/canonical-atom-v2-dnrd5-v2-lifecycle-adapter.ts",
        "src/canonical-atom-v2-dnrd5-v2-receipt-seal.ts",
        "src/canonical-atom-v2-dnrd5-v2-record-bound-effect.ts",
    )
    entrypoints = typescript["entrypoints"]
    if type(entrypoints) is not list or tuple(entrypoints) != expected_entrypoints:
        _refuse("TS_ENTRYPOINT_INVALID", "TypeScript entrypoints drifted")
    if not set(entrypoints).issubset(source_by_path):
        _refuse("TS_ENTRYPOINT_INVALID", "TypeScript entrypoint not in resolved sources")
    if len(seam_hits) != 1:
        _refuse("TS_SEAM_INVALID", "durable commit seam must have one importer")
    seam_path, seam_binding, seam_name = seam_hits[0]
    if (
        seam_path != "src/canonical-atom-v2-dnrd5-durable-permit.ts"
        or seam_binding["kind"] != "static-import"
        or seam_binding["source"] != "./canonical-atom-v2-durable-runtime.js"
        or seam_binding["targetKind"] != "local-source"
        or seam_binding["typeOnly"] is not False
        or seam_name["local"] != "commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal"
        or seam_name["typeOnly"] is not False
    ):
        _refuse("TS_SEAM_INVALID", "durable commit seam binding drifted")
    target = seam_binding["target"]
    if type(target) is not dict or target.get("path") != "src/canonical-atom-v2-durable-runtime.ts":
        _refuse("TS_SEAM_INVALID", "durable commit seam target drifted")
    runtime = source_by_path.get("src/canonical-atom-v2-durable-runtime.ts")
    if runtime is None:
        _refuse("TS_SEAM_INVALID", "durable runtime source absent")
    _same_descriptor(target, {key: runtime[key] for key in ("path", "byteLength", "sha256")}, "durable commit seam")
    return typescript


def _validate_toolchains(value: Any, typescript: Mapping[str, Any]) -> dict[str, Any]:
    toolchains = _object(value, "toolchains", {"python", "typescriptManifestSha256"})
    python = _object(toolchains["python"], "toolchains.python", {"implementation", "version", "cacheTag", "unicodeVersion", "executable"})
    for key in ("implementation", "version", "cacheTag", "unicodeVersion"):
        _text(python[key], f"toolchains.python.{key}")
    executable = _file_descriptor(python["executable"], "toolchains.python.executable")
    if executable["path"] != "external-runtime/python":
        _refuse("TOOLCHAIN_PIN_INVALID", "Python executable identity drifted")
    expected = sha256(canonical_bytes(typescript)).hexdigest()
    if toolchains["typescriptManifestSha256"] != expected:
        _refuse("TOOLCHAIN_PIN_INVALID", "nested canonical TypeScript byte hash drifted")
    return toolchains


def _validate_evidence(value: Any, selected: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = value
    if type(rows) is not list:
        _refuse("EVIDENCE_PIN_INVALID", "evidence pins are not a list")
    expected = (
        ("source-ci-workflow", ".github/workflows/ci.yml"),
        ("python-source-distribution-policy", "MANIFEST.in"),
        ("pyproject", "pyproject.toml"),
        ("python-lock", "uv.lock"),
        ("scientific-design", "docs/research/HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md"),
        ("exactness-policy", "docs/research/HSWM_DNRD_5_EXACTNESS_POLICY_AMENDMENT_2026-08-28.md"),
        ("node-package", "src/hswm/effect-runtime/package.json"),
        ("node-lock", "src/hswm/effect-runtime/package-lock.json"),
        ("node-policy", "src/hswm/effect-runtime/.npmrc"),
        ("typescript-base-config", "src/hswm/effect-runtime/tsconfig.json"),
        ("typescript-build-config", "src/hswm/effect-runtime/tsconfig.build.json"),
        ("typescript-selected-config", "src/hswm/effect-runtime/tsconfig.dnrd5-source-closure.json"),
        ("typescript-capture", "src/hswm/effect-runtime/scripts/emit-dnrd5-source-closure.mjs"),
        ("actual-byte-manifest", "_research/dnrd5/vectors/actual_byte_corpus_v1/manifest.json"),
        ("v2-schema", "_research/dnrd5/vectors/dnrd5_v2_schema.json"),
        ("lifecycle", "_research/dnrd5/vectors/lifecycle_contract_v1.json"),
        ("alignment", "_research/dnrd5/vectors/lifecycle_atom_alignment_v1.json"),
        ("plan-json-kat", "_research/dnrd5/vectors/plan_json_v1_kat.json"),
    )
    if len(rows) != len(expected):
        _refuse("EVIDENCE_PIN_INVALID", "evidence pin cardinality drifted")
    checked: list[dict[str, Any]] = []
    for index, (row_value, (role, path)) in enumerate(zip(rows, expected, strict=True)):
        row = _object(row_value, f"evidencePins[{index}]", {"role", "path", "mode", "gitBlobOid", "byteLength", "sha256"})
        if row["role"] != role or row["path"] != path:
            _refuse("EVIDENCE_PIN_INVALID", "evidence pin role/path ordering drifted")
        selected_row = selected.get(path)
        selected_projection = (
            {key: selected_row[key] for key in ("path", "mode", "gitBlobOid", "byteLength", "sha256")}
            if selected_row is not None
            else None
        )
        pin_projection = {key: row[key] for key in ("path", "mode", "gitBlobOid", "byteLength", "sha256")}
        if selected_projection is None or pin_projection != selected_projection:
            _refuse("EVIDENCE_PIN_INVALID", f"evidence pin does not equal selected Git record at {path}")
        checked.append(row)
    return checked


def _decode_manifest(raw: bytes) -> dict[str, Any]:
    try:
        manifest = parse_canonical(raw)
    except CanonicalJsonError as error:
        _refuse("CANONICAL_BYTES_INVALID", str(error))
    return _object(
        manifest,
        "manifest",
        {
            "_tag", "contractVersion", "claimBoundary", "dispatchAuthorized", "dispatchBudget",
            "sourceFreezeEligible", "providerOrModelCalls", "source", "toolchains", "python",
            "typescript", "evidencePins", "terminal",
        },
    )


def _git_run(root: Path, arguments: Sequence[str], *, allow_failure: bool = False) -> subprocess.CompletedProcess[bytes]:
    try:
        completed = subprocess.run(
            ["git", "--no-replace-objects", "--no-pager", *arguments],
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        _refuse("PHYSICAL_GIT_UNAVAILABLE", f"local Git could not run: {type(error).__name__}")
    if completed.returncode != 0 and not allow_failure:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "local Git rejected a required identity query")
    return completed


def _git_text(root: Path, *arguments: str) -> str:
    raw = _git_run(root, arguments).stdout
    try:
        value = raw.decode("utf-8", "strict").strip()
    except UnicodeDecodeError:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "Git identity response is not UTF-8")
    if not value:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "Git identity response is empty")
    return value


def _git_object_hash(object_format: str, kind: str, raw: bytes) -> str:
    digest = hash_new(object_format)
    digest.update(f"{kind} {len(raw)}\0".encode("ascii"))
    digest.update(raw)
    return digest.hexdigest()


def _cat_object(root: Path, kind: str, oid: str, object_format: str) -> bytes:
    raw = _git_run(root, ("cat-file", kind, oid)).stdout
    if _git_object_hash(object_format, kind, raw) != oid:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", f"raw {kind} bytes do not match {oid}")
    return raw


def _judge_selected_path(path: str) -> bool:
    # An independently stated selected-set policy.  It is intentionally kept
    # here rather than delegated to the capture implementation.
    critical = {
        ".github/workflows/ci.yml", "MANIFEST.in",
        "pyproject.toml", "uv.lock",
        "docs/research/HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md",
        "docs/research/HSWM_DNRD_5_EXACTNESS_POLICY_AMENDMENT_2026-08-28.md",
        "src/hswm/effect-runtime/package.json",
        "src/hswm/effect-runtime/package-lock.json",
        "src/hswm/effect-runtime/.npmrc",
        "src/hswm/effect-runtime/tsconfig.json",
        "src/hswm/effect-runtime/tsconfig.build.json",
        "src/hswm/effect-runtime/tsconfig.dnrd5-source-closure.json",
        "src/hswm/effect-runtime/scripts/emit-dnrd5-source-closure.mjs",
        "_research/dnrd5/vectors/actual_byte_corpus_v1/manifest.json",
        "_research/dnrd5/vectors/dnrd5_v2_schema.json",
        "_research/dnrd5/vectors/lifecycle_contract_v1.json",
        "_research/dnrd5/vectors/lifecycle_atom_alignment_v1.json",
        "_research/dnrd5/vectors/plan_json_v1_kat.json",
    }
    return (
        path in critical
        or path.startswith("_research/dnrd5/")
        or path.startswith("tests/test_dnrd5_")
        or path.startswith("src/hswm/effect-runtime/src/")
        or path.startswith("src/hswm/effect-runtime/scripts/")
        or path.startswith("src/hswm/effect-runtime/test/")
    )


def _walk_git_tree(root: Path, tree_oid: str, object_format: str, *, prefix: PurePosixPath | None = None, depth: int = 0) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if depth > 256:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "Git tree depth exceeds judge bound")
    current = prefix or PurePosixPath()
    raw = _cat_object(root, "tree", tree_oid, object_format)
    trees = [{"path": current.as_posix() if current.parts else ".", "gitTreeOid": tree_oid, "byteLength": len(raw), "sha256": sha256(raw).hexdigest()}]
    selected: list[dict[str, Any]] = []
    digest_length = 20 if object_format == "sha1" else 32
    cursor = 0
    names: set[bytes] = set()
    while cursor < len(raw):
        space = raw.find(b" ", cursor)
        nul = raw.find(b"\0", space + 1 if space >= 0 else cursor)
        end = nul + 1 + digest_length
        if space <= cursor or nul <= space + 1 or end > len(raw):
            _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "malformed raw Git tree entry")
        raw_mode, raw_name = raw[cursor:space], raw[space + 1:nul]
        if raw_name in names:
            _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "duplicate raw Git tree name")
        names.add(raw_name)
        try:
            mode = raw_mode.decode("ascii", "strict")
            name = raw_name.decode("utf-8", "strict")
        except UnicodeDecodeError:
            _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "raw Git tree name/mode encoding invalid")
        if not name or "/" in name or "\\" in name or name in {".", ".."}:
            _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "unsafe raw Git tree name")
        oid = raw[nul + 1:end].hex()
        _oid(oid, object_format, "raw Git tree child OID")
        child = current / name
        path = _safe_path(child.as_posix(), "raw Git tree path")
        if mode == "40000":
            descendants, child_trees = _walk_git_tree(root, oid, object_format, prefix=child, depth=depth + 1)
            selected.extend(descendants)
            trees.extend(child_trees)
        elif _judge_selected_path(path):
            if mode not in _MODES:
                _refuse("PHYSICAL_GIT_IDENTITY_INVALID", f"selected Git path has unsupported mode: {path}")
            blob = _cat_object(root, "blob", oid, object_format)
            selected.append({"path": path, "mode": mode, "gitBlobOid": oid, "byteLength": len(blob), "sha256": sha256(blob).hexdigest()})
        cursor = end
    return selected, trees


def _regular_bytes(root: Path, relative: str, label: str) -> bytes:
    _safe_path(relative, label)
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    try:
        metadata = candidate.lstat()
        resolved = candidate.resolve(strict=True)
    except OSError:
        _refuse("PHYSICAL_PATH_INVALID", f"missing referenced regular file {label}")
    root_resolved = root.resolve()
    if candidate.is_symlink() or not stat.S_ISREG(metadata.st_mode) or resolved != candidate.absolute() or not resolved.is_relative_to(root_resolved):
        _refuse("PHYSICAL_PATH_INVALID", f"referenced file is not a contained regular file: {label}")
    try:
        return candidate.read_bytes()
    except OSError:
        _refuse("PHYSICAL_PATH_INVALID", f"could not read referenced regular file {label}")


def _verify_physical_descriptor(root: Path, descriptor: Mapping[str, Any], label: str) -> None:
    raw = _regular_bytes(root, descriptor["path"], label)
    if len(raw) != descriptor["byteLength"] or sha256(raw).hexdigest() != descriptor["sha256"]:
        _refuse("PHYSICAL_DESCRIPTOR_DRIFT", f"physical bytes drifted at {label}")


def _verify_external_descriptor(path: Path, descriptor: Mapping[str, Any], label: str) -> None:
    try:
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError:
        _refuse("PHYSICAL_PATH_INVALID", f"external executable missing at {label}")
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or resolved != path.absolute():
        _refuse("PHYSICAL_PATH_INVALID", f"external executable must be a regular non-symlink: {label}")
    raw = path.read_bytes()
    if len(raw) != descriptor["byteLength"] or sha256(raw).hexdigest() != descriptor["sha256"]:
        _refuse("PHYSICAL_DESCRIPTOR_DRIFT", f"external executable bytes drifted at {label}")


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return f"<{type(node).__name__}>"


class _PhysicalCallWitness(ast.NodeVisitor):
    """Independent syntactic witness for the intentionally summary-only field."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.scopes = ["<module>"]
        self.rows: list[dict[str, Any]] = []

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
        if node.id in {"__import__", "eval", "exec", "compile"}:
            _refuse("PHYSICAL_PYTHON_AST_INVALID", f"dynamic loader reference at {self.path}:{node.lineno}")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        name = _call_name(node)
        if name in {
            "builtins.__import__", "builtins.eval", "builtins.exec", "builtins.compile",
            "importlib.import_module", "runpy.run_module", "runpy.run_path",
        } or name.endswith(".import_module"):
            _refuse("PHYSICAL_PYTHON_AST_INVALID", f"dynamic loader reference at {self.path}:{node.lineno}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        callee = _call_name(node.func)
        if callee in {
            "__import__", "eval", "exec", "compile", "builtins.__import__", "builtins.eval",
            "builtins.exec", "builtins.compile", "importlib.import_module", "runpy.run_module", "runpy.run_path",
        } or callee.endswith(".import_module"):
            _refuse("PHYSICAL_PYTHON_AST_INVALID", f"dynamic loader call at {self.path}:{node.lineno}")
        if (
            callee in {"getattr", "builtins.getattr"}
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in {"__import__", "eval", "exec", "compile", "import_module"}
        ):
            _refuse("PHYSICAL_PYTHON_AST_INVALID", f"indirect dynamic loader at {self.path}:{node.lineno}")
        self.rows.append({
            "path": self.path,
            "caller": ".".join(self.scopes),
            "callee": callee,
            "line": node.lineno,
            "column": node.col_offset,
        })
        self.generic_visit(node)


def _physical_local_module(root: Path, module: str) -> str | None:
    try:
        relative = PurePosixPath(*module.split("."))
    except TypeError:
        _refuse("PHYSICAL_PYTHON_AST_INVALID", "local module name is malformed")
    for candidate in (relative.with_suffix(".py"), relative / "__init__.py"):
        candidate_text = candidate.as_posix()
        try:
            (root / candidate_text).lstat()
        except OSError:
            continue
        _regular_bytes(root, candidate_text, f"local module {candidate_text}")
        return candidate_text
    return None


def _verify_physical_python_ast_summary(root: Path, python: Mapping[str, Any]) -> None:
    edges: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for descriptor in python["files"]:
        path = descriptor["path"]
        raw = _regular_bytes(root, path, f"Python AST source {path}")
        try:
            tree = ast.parse(raw, filename=path)
        except (SyntaxError, ValueError, UnicodeDecodeError) as error:
            _refuse("PHYSICAL_PYTHON_AST_INVALID", f"cannot parse {path}: {error}")
        relative = PurePosixPath(path)
        parts = list(relative.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        current_module = ".".join(parts)
        package = current_module.split(".")
        if relative.name != "__init__.py":
            package.pop()
        for node in ast.walk(tree):
            imported: list[tuple[str, int, str, str | None]] = []
            if isinstance(node, ast.Import):
                imported.extend((alias.name, 0, alias.name, alias.asname) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level > len(package):
                    _refuse("PHYSICAL_PYTHON_AST_INVALID", f"relative import escapes package at {path}:{node.lineno}")
                prefix = package[: len(package) - node.level + 1]
                module_parts = node.module.split(".") if node.module else []
                module = ".".join(prefix + module_parts) if node.level else (node.module or "")
                imported.extend((module, node.level, alias.name, alias.asname) for alias in node.names)
            for module, level, name, alias in imported:
                root_name = module.split(".", 1)[0] if module else ""
                if root_name in {"__builtins__", "builtins", "importlib", "runpy"}:
                    _refuse("PHYSICAL_PYTHON_AST_INVALID", f"dynamic import root at {path}:{node.lineno}")
                resolved = _physical_local_module(root, module) if module.startswith("_research.dnrd5") else None
                if module.startswith("_research.dnrd5"):
                    named = _physical_local_module(root, f"{module}.{name}")
                    if named is not None:
                        resolved = named
                    if resolved is None:
                        _refuse("PHYSICAL_PYTHON_AST_INVALID", f"unresolved local import {module} at {path}:{node.lineno}")
                if root_name in {"http", "socket", "ssl", "urllib"}:
                    classification = "NETWORK_CAPABLE_DEFERRED_DISPATCH"
                elif resolved is not None:
                    classification = "LOCAL_DNRD5_SOURCE"
                elif root_name in sys.stdlib_module_names:
                    classification = "PYTHON_STDLIB"
                else:
                    _refuse("PHYSICAL_PYTHON_AST_INVALID", f"unresolved non-stdlib import {module} at {path}:{node.lineno}")
                edges.append({
                    "path": path,
                    "line": node.lineno,
                    "module": module,
                    "level": level,
                    "name": name,
                    "alias": alias,
                    "resolvedPath": resolved,
                    "classification": classification,
                })
        witness = _PhysicalCallWitness(path)
        witness.visit(tree)
        rows.extend(witness.rows)
    edges.sort(key=lambda row: (row["path"], row["line"], row["module"], row["name"], row["alias"] or ""))
    rows.sort(key=lambda row: (row["path"], row["line"], row["column"], row["callee"]))
    if edges != python["astImportEdges"] or python["importGraphSha256"] != canonical_sha256(edges):
        _refuse("PHYSICAL_PYTHON_AST_INVALID", "Python import graph does not rederive from physical bytes")
    summary = python["syntacticCallSites"]
    if summary["count"] != len(rows) or summary["sha256"] != canonical_sha256(rows):
        _refuse("PHYSICAL_PYTHON_AST_INVALID", "Python syntactic-call summary does not rederive from physical bytes")


def _verify_physical_repository(
    repository_root: Path,
    source: Mapping[str, Any],
    python: Mapping[str, Any],
    typescript: Mapping[str, Any],
    toolchains: Mapping[str, Any],
    *,
    node_executable: Path | None,
    python_executable: Path | None,
) -> tuple[bool, bool]:
    supplied = Path(repository_root)
    try:
        root = supplied.resolve(strict=True)
    except OSError:
        _refuse("PHYSICAL_PATH_INVALID", "repository root is unavailable")
    if supplied.is_symlink() or not root.is_dir() or root != supplied.absolute():
        _refuse("PHYSICAL_PATH_INVALID", "repository root must be a direct regular directory")
    top = _git_text(root, "rev-parse", "--show-toplevel")
    try:
        top_path = Path(top).resolve(strict=True)
    except OSError:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "Git top-level is unavailable")
    if top_path != root:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "repository root is not Git top-level")
    symbolic = _git_run(root, ("symbolic-ref", "-q", "HEAD"), allow_failure=True)
    if symbolic.returncode == 0:
        _refuse("PHYSICAL_WORKTREE_NOT_DETACHED", "physical checkout is attached")
    if symbolic.returncode not in {0, 1}:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "could not determine detached HEAD")
    if _git_run(root, ("status", "--porcelain=v1", "-z", "--untracked-files=all")).stdout:
        _refuse("PHYSICAL_WORKTREE_NOT_CLEAN", "physical checkout is dirty")
    object_format = _git_text(root, "rev-parse", "--show-object-format")
    if object_format != source["gitObjectFormat"]:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "Git object format drifted")
    head = _git_text(root, "rev-parse", "--verify", "HEAD^{commit}")
    if head != source["commit"]:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "detached HEAD does not match recorded commit")
    tree = _git_text(root, "rev-parse", "--verify", f"{head}^{{tree}}")
    if tree != source["tree"]:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "HEAD tree does not match recorded tree")
    commit_raw = _cat_object(root, "commit", head, object_format)
    tree_raw = _cat_object(root, "tree", tree, object_format)
    if commit_raw.partition(b"\n")[0] != f"tree {tree}".encode("ascii"):
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "commit does not bind recorded tree")
    if {"byteLength": len(commit_raw), "sha256": sha256(commit_raw).hexdigest()} != source["commitObject"]:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "raw commit descriptor drifted")
    if {"byteLength": len(tree_raw), "sha256": sha256(tree_raw).hexdigest()} != source["treeObject"]:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "raw root-tree descriptor drifted")
    selected, trees = _walk_git_tree(root, tree, object_format)
    selected.sort(key=lambda row: row["path"])
    trees.sort(key=lambda row: row["path"])
    if selected != source["selectedTrackedFiles"] or trees != source["treeObjects"]:
        _refuse("PHYSICAL_GIT_IDENTITY_INVALID", "raw Git selected/tree records drifted")
    for row in selected:
        raw = _regular_bytes(root, row["path"], row["path"])
        if len(raw) != row["byteLength"] or sha256(raw).hexdigest() != row["sha256"]:
            _refuse("PHYSICAL_DESCRIPTOR_DRIFT", f"worktree byte drift at {row['path']}")
    _verify_physical_python_ast_summary(root, python)

    package = root / "src" / "hswm" / "effect-runtime"
    for row in typescript["inputs"]:
        _verify_physical_descriptor(package, row, f"TypeScript input {row['path']}")
    for row in typescript["compiler"]["typescriptFiles"]:
        _verify_physical_descriptor(package, row, f"TypeScript compiler file {row['path']}")
    for row in typescript["resolvedExternalFiles"]:
        _verify_physical_descriptor(package, row, f"resolved external file {row['path']}")
    for row in typescript["sources"]:
        _verify_physical_descriptor(package, row, f"TypeScript source {row['path']}")
        for binding in row["imports"]:
            if binding["target"] is not None:
                _verify_physical_descriptor(package, binding["target"], f"TypeScript import target {binding['target']['path']}")

    external_ok = True
    if node_executable is not None:
        _verify_external_descriptor(Path(node_executable), typescript["compiler"]["nodeExecutable"], "node")
    else:
        external_ok = False
    if python_executable is not None:
        _verify_external_descriptor(Path(python_executable), toolchains["python"]["executable"], "python")
    else:
        external_ok = False
    return True, external_ok


def judge_source_build_import_closure(
    raw: bytes,
    *,
    repository_root: Path | None = None,
    node_executable: Path | None = None,
    python_executable: Path | None = None,
) -> IndependentSourceBuildImportJudgeResult:
    """Judge canonical closure bytes without running Node, providers, or models.

    ``repository_root`` optionally adds raw-Git and regular-worktree-byte
    verification.  It does not execute an npm build or a TypeScript compiler;
    therefore generated emitted bytes and compiler semantic correctness remain
    explicitly unproven even when the physical repository checks succeed.
    """

    manifest = _decode_manifest(raw)
    _require_exact_claims(manifest)
    source = _validate_source(manifest["source"])
    selected = {row["path"]: row for row in source["selectedTrackedFiles"]}
    _validate_python(manifest["python"], selected)
    typescript = _validate_typescript(manifest["typescript"], selected)
    toolchains = _validate_toolchains(manifest["toolchains"], typescript)
    _validate_evidence(manifest["evidencePins"], selected)
    physical = False
    external = False
    if repository_root is not None:
        physical, external = _verify_physical_repository(
            Path(repository_root), source, manifest["python"], typescript, toolchains,
            node_executable=node_executable, python_executable=python_executable,
        )
    return IndependentSourceBuildImportJudgeResult(
        terminal="INDEPENDENT_LOCAL_SOURCE_BUILD_IMPORT_CLOSURE_STRUCTURAL_VALIDATED_NOT_SOURCE_A_PROVIDER_OCCURRENCE_EMITTED_BYTE_REBUILD_OR_COMPILER_SEMANTIC_PROOF",
        manifest_sha256=sha256(raw).hexdigest(),
        source_commit=source["commit"],
        physical_repository_verified=physical,
        external_toolchains_verified=external,
        python_import_graph_independently_verified=physical,
        python_call_summary_independently_verified=physical,
        emitted_bytes_independently_verified=False,
        compiler_semantics_independently_verified=False,
        source_a_authorized=False,
        provider_or_model_calls=0,
    )
