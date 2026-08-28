from __future__ import annotations

from copy import deepcopy
from hashlib import sha1, sha256
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256
from _research.dnrd5.independent_source_build_import_judge import (
    IndependentSourceBuildImportJudgeRefusal,
    judge_source_build_import_closure,
)


_PACKAGE = "src/hswm/effect-runtime"
_ENTRYPOINTS = (
    "src/canonical-atom-v2-dnrd5-durable-permit.ts",
    "src/canonical-atom-v2-dnrd5-nine-call.ts",
    "src/canonical-atom-v2-dnrd5-plan-json.ts",
    "src/canonical-atom-v2-dnrd5-randomization.ts",
    "src/canonical-atom-v2-dnrd5-v2-audit-release.ts",
    "src/canonical-atom-v2-dnrd5-v2-lifecycle-adapter.ts",
    "src/canonical-atom-v2-dnrd5-v2-receipt-seal.ts",
    "src/canonical-atom-v2-dnrd5-v2-record-bound-effect.ts",
)
_PIN_PATHS = (
    ("source-ci-workflow", ".github/workflows/ci.yml"),
    ("python-source-distribution-policy", "MANIFEST.in"),
    ("pyproject", "pyproject.toml"),
    ("python-lock", "uv.lock"),
    ("scientific-design", "docs/research/HSWM_DNRD_5_CAUSAL_MACROPLASTICITY_DESIGN_2026-08-28.md"),
    ("exactness-policy", "docs/research/HSWM_DNRD_5_EXACTNESS_POLICY_AMENDMENT_2026-08-28.md"),
    ("node-package", f"{_PACKAGE}/package.json"),
    ("node-lock", f"{_PACKAGE}/package-lock.json"),
    ("node-policy", f"{_PACKAGE}/.npmrc"),
    ("typescript-base-config", f"{_PACKAGE}/tsconfig.json"),
    ("typescript-build-config", f"{_PACKAGE}/tsconfig.build.json"),
    ("typescript-selected-config", f"{_PACKAGE}/tsconfig.dnrd5-source-closure.json"),
    ("typescript-capture", f"{_PACKAGE}/scripts/emit-dnrd5-source-closure.mjs"),
    ("actual-byte-manifest", "_research/dnrd5/vectors/actual_byte_corpus_v1/manifest.json"),
    ("v2-schema", "_research/dnrd5/vectors/dnrd5_v2_schema.json"),
    ("lifecycle", "_research/dnrd5/vectors/lifecycle_contract_v1.json"),
    ("alignment", "_research/dnrd5/vectors/lifecycle_atom_alignment_v1.json"),
    ("plan-json-kat", "_research/dnrd5/vectors/plan_json_v1_kat.json"),
)


def _hex(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _git_oid(label: str) -> str:
    return sha1(label.encode("utf-8")).hexdigest()


def _descriptor(path: str, label: str | None = None) -> dict[str, object]:
    return {"path": path, "byteLength": 1, "sha256": _hex(label or path)}


def _parents(paths: list[str], root_oid: str) -> list[dict[str, object]]:
    directories = {"."}
    for path in paths:
        parent = PurePosixPath(path).parent
        while parent.parts:
            directories.add(parent.as_posix())
            parent = parent.parent
    return [
        {
            "path": path,
            "gitTreeOid": root_oid if path == "." else _git_oid(f"tree:{path}"),
            "byteLength": 1,
            "sha256": _hex(f"tree-bytes:{path}"),
        }
        for path in sorted(directories)
    ]


def _structural_manifest() -> dict[str, Any]:
    input_paths = (
        ".npmrc",
        "package-lock.json",
        "package.json",
        "tsconfig.build.json",
        "tsconfig.dnrd5-source-closure.json",
        "tsconfig.json",
    )
    runtime_path = "src/canonical-atom-v2-durable-runtime.ts"
    selected_paths = sorted(
        {path for _, path in _PIN_PATHS}
        | {"_research/dnrd5/example.py"}
        | {f"{_PACKAGE}/{path}" for path in (*_ENTRYPOINTS, runtime_path)}
    )
    selected = [
        {
            "path": path,
            "mode": "100644",
            "gitBlobOid": _git_oid(f"blob:{path}"),
            "byteLength": 1,
            "sha256": _hex(f"selected:{path}"),
        }
        for path in selected_paths
    ]
    by_path = {item["path"]: item for item in selected}
    root_oid = _git_oid("source-tree")
    trees = _parents(selected_paths, root_oid)

    def git_descriptor(path: str) -> dict[str, object]:
        item = by_path[path]
        return {key: item[key] for key in ("path", "byteLength", "sha256")}

    def package_descriptor(path: str) -> dict[str, object]:
        item = git_descriptor(f"{_PACKAGE}/{path}")
        return {**item, "path": path}

    source_paths = [*_ENTRYPOINTS, runtime_path]
    sources = []
    for path in source_paths:
        imports: list[dict[str, object]] = []
        if path == _ENTRYPOINTS[0]:
            imports.append(
                {
                    "kind": "static-import",
                    "names": [
                        {
                            "imported": "commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal",
                            "local": "commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal",
                            "typeOnly": False,
                        }
                    ],
                    "position": 1,
                    "source": "./canonical-atom-v2-durable-runtime.js",
                    "target": package_descriptor(runtime_path),
                    "targetKind": "local-source",
                    "typeOnly": False,
                }
            )
        sources.append(
            {
                **package_descriptor(path),
                "exportedSymbols": ["fixture"],
                "imports": imports,
            }
        )
    sources.sort(key=lambda item: item["path"])
    inputs = [package_descriptor(path) for path in input_paths]
    external = [_descriptor("node_modules/effect/dist/dts/index.d.ts", "external-effect")]
    compiler_files = [
        _descriptor("node_modules/typescript/lib/tsc.js", "tsc"),
        _descriptor("node_modules/typescript/lib/typescript.js", "typescript"),
        _descriptor("node_modules/typescript/package.json", "typescript-package"),
    ]
    emitted_files = [_descriptor("entry.js", "emitted-entry")]
    typescript: dict[str, Any] = {
        "contractVersion": "hswm-dnrd5-local-source-build-import-closure/v1",
        "claimBoundary": "LOCAL_REDERIVATION_ONLY_NO_NETWORK_AUTHORITY_SOURCE_FREEZE_PROVIDER_OCCURRENCE_OR_SCIENTIFIC_RESULT",
        "dispatchAuthorized": False,
        "dispatchBudget": 0,
        "sourceFreezeEligible": False,
        "compiler": {
            "effectiveOptions": {
                "allowImportingTsExtensions": False,
                "declaration": True,
                "declarationMap": True,
                "exactOptionalPropertyTypes": True,
                "module": 199,
                "moduleResolution": 99,
                "noEmit": False,
                "noEmitOnError": True,
                "noUncheckedIndexedAccess": True,
                "plugins": [],
                "rootDir": "src",
                "sourceMap": True,
                "strict": True,
                "target": 9,
                "types": ["node"],
            },
            "nodeExecutable": _descriptor("external-runtime/node", "node"),
            "nodeVersion": "v24.13.0",
            "typescriptFiles": compiler_files,
            "version": "5.9.3",
        },
        "entrypoints": list(_ENTRYPOINTS),
        "inputs": inputs,
        "emitted": {"files": emitted_files, "rootSha256": canonical_sha256(emitted_files)},
        "resolvedExternalFiles": external,
        "sources": sources,
        "terminal": "LOCAL_SOURCE_BUILD_IMPORT_CLOSURE_ONLY_NOT_SOURCE_A_PROVIDER_OR_EFFICACY",
    }
    python_files = [git_descriptor("_research/dnrd5/example.py")]
    manifest: dict[str, Any] = {
        "_tag": "Dnrd5LocalSourceBuildImportClosure",
        "contractVersion": "hswm-dnrd5-local-source-build-import-closure/v1",
        "claimBoundary": "LOCAL_GIT_AST_COMPILER_AND_BUILD_IDENTITY_ONLY_NOT_COMPILER_SOUNDNESS_REMOTE_PROVENANCE_NETWORK_SYSCALL_ABSENCE_SOURCE_A_AUTHORITY_PROVIDER_OCCURRENCE_LEARNING_OR_SCIENTIFIC_RESULT",
        "dispatchAuthorized": False,
        "dispatchBudget": 0,
        "sourceFreezeEligible": False,
        "providerOrModelCalls": 0,
        "source": {
            "gitObjectFormat": "sha1",
            "commit": _git_oid("source-commit"),
            "tree": root_oid,
            "commitObject": {"byteLength": 1, "sha256": _hex("commit")},
            "treeObject": {"byteLength": 1, "sha256": _hex("tree")},
            "treeObjects": trees,
            "treeObjectsSha256": canonical_sha256(trees),
            "detachedClean": True,
            "cleanPolicy": "DETACHED_HEAD_EQUALS_REQUESTED_COMMIT_AND_GIT_STATUS_PORCELAIN_V1_UNTRACKED_ALL_EMPTY_IGNORED_BUILD_INPUTS_CAPTURED_SEPARATELY",
            "selectedTrackedFiles": selected,
            "selectedTrackedFilesSha256": canonical_sha256(selected),
        },
        "toolchains": {
            "python": {
                "implementation": "CPython",
                "version": "3.12.0",
                "cacheTag": "cpython-312",
                "unicodeVersion": "15.0.0",
                "executable": _descriptor("external-runtime/python", "python"),
            },
            "typescriptManifestSha256": sha256(canonical_bytes(typescript)).hexdigest(),
        },
        "python": {
            "namespaceRoots": ["_research"],
            "files": python_files,
            "astImportEdges": [],
            "syntacticCallSites": {"count": 0, "sha256": canonical_sha256([])},
            "networkCapableDeferredModules": [],
            "dynamicImportPolicy": "LITERAL_IMPORT_AST_ONLY_DYNAMIC_LOADERS_FORBIDDEN",
            "filesSha256": canonical_sha256(python_files),
            "importGraphSha256": canonical_sha256([]),
        },
        "typescript": typescript,
        "evidencePins": [
            {"role": role, **by_path[path]} for role, path in _PIN_PATHS
        ],
        "terminal": "LOCAL_SOURCE_BUILD_IMPORT_CLOSURE_REDERIVED_NOT_SOURCE_A_PROVIDER_OCCURRENCE_OR_EFFICACY",
    }
    return manifest


def _raw(manifest: dict[str, Any]) -> bytes:
    return canonical_bytes(manifest)


def test_structural_baseline_is_local_only_and_never_authority() -> None:
    result = judge_source_build_import_closure(_raw(_structural_manifest()))
    assert result.physical_repository_verified is False
    assert result.source_a_authorized is False
    assert result.provider_or_model_calls == 0
    assert result.emitted_bytes_independently_verified is False
    assert result.compiler_semantics_independently_verified is False


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: value.update({"dispatchAuthorized": True}), "CLAIM_BOUNDARY_INVALID"),
        (lambda value: value.update({"dispatchBudget": True}), "CLAIM_BOUNDARY_INVALID"),
        (lambda value: value["source"].update({"selectedTrackedFilesSha256": "0" * 64}), "GIT_SELECTION_INVALID"),
        (lambda value: value["source"]["selectedTrackedFiles"][0].update({"path": []}), "TYPE_INVALID"),
        (lambda value: value["source"].update({"gitObjectFormat": []}), "GIT_OBJECT_INVALID"),
        (
            lambda value: value["typescript"]["compiler"]["effectiveOptions"].update({"module": 1}),
            "TSCONFIG_POLICY_INVALID",
        ),
        (
            lambda value: value["typescript"]["sources"][0]["imports"][0].update({"kind": "runtime-dynamic-import"}),
            "TS_RUNTIME_LOADER_FORBIDDEN",
        ),
        (
            lambda value: value["typescript"]["sources"][0]["imports"][0].update({"source": "./different-runtime.js"}),
            "TS_SEAM_INVALID",
        ),
    ],
)
def test_mutations_reach_independent_specific_refusals(mutate, code: str) -> None:
    manifest = _structural_manifest()
    mutate(manifest)
    with pytest.raises(IndependentSourceBuildImportJudgeRefusal) as caught:
        judge_source_build_import_closure(_raw(manifest))
    assert caught.value.code == code


def _git(root: Path, *arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=root, stdin=subprocess.DEVNULL)


def _raw_tree_records(root: Path, oid: str, *, prefix: PurePosixPath | None = None) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    current = prefix or PurePosixPath()
    raw = _git(root, "cat-file", "tree", oid)
    trees = [{"path": current.as_posix() if current.parts else ".", "gitTreeOid": oid, "byteLength": len(raw), "sha256": sha256(raw).hexdigest()}]
    selected: list[dict[str, object]] = []
    cursor = 0
    while cursor < len(raw):
        space = raw.index(b" ", cursor)
        nul = raw.index(b"\0", space + 1)
        mode = raw[cursor:space].decode("ascii")
        name = raw[space + 1:nul].decode("utf-8")
        child_oid = raw[nul + 1:nul + 21].hex()
        path = (current / name).as_posix()
        if mode == "40000":
            child_selected, child_trees = _raw_tree_records(root, child_oid, prefix=current / name)
            selected.extend(child_selected)
            trees.extend(child_trees)
        elif (
            path.startswith("_research/dnrd5/")
            or path.startswith("src/hswm/effect-runtime/src/")
            or path.startswith("src/hswm/effect-runtime/scripts/")
            or path in {item[1] for item in _PIN_PATHS}
        ):
            blob = _git(root, "cat-file", "blob", child_oid)
            selected.append({"path": path, "mode": mode, "gitBlobOid": child_oid, "byteLength": len(blob), "sha256": sha256(blob).hexdigest()})
        cursor = nul + 21
    return selected, trees


def _write(root: Path, path: str, contents: bytes) -> None:
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(contents)


def _physical_manifest(root: Path) -> dict[str, Any]:
    manifest = _structural_manifest()
    selected_paths = [row["path"] for row in manifest["source"]["selectedTrackedFiles"]]
    for path in selected_paths:
        contents = b"VALUE = 1\n" if path == "_research/dnrd5/example.py" else f"fixture:{path}\n".encode()
        _write(root, path, contents)
    _write(root, ".gitignore", b"node_modules/\n")
    package = root / _PACKAGE
    for path in (
        "node_modules/typescript/lib/tsc.js",
        "node_modules/typescript/lib/typescript.js",
        "node_modules/typescript/package.json",
        "node_modules/effect/dist/dts/index.d.ts",
    ):
        _write(package, path, f"fixture:{path}\n".encode())
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "fixture"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
    subprocess.run(["git", "checkout", "--detach", "-q"], cwd=root, check=True)

    commit = _git(root, "rev-parse", "HEAD").decode().strip()
    tree = _git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    commit_bytes = _git(root, "cat-file", "commit", commit)
    tree_bytes = _git(root, "cat-file", "tree", tree)
    selected, trees = _raw_tree_records(root, tree)
    selected.sort(key=lambda item: item["path"])
    trees.sort(key=lambda item: item["path"])
    manifest["source"] = {
        "gitObjectFormat": "sha1",
        "commit": commit,
        "tree": tree,
        "commitObject": {"byteLength": len(commit_bytes), "sha256": sha256(commit_bytes).hexdigest()},
        "treeObject": {"byteLength": len(tree_bytes), "sha256": sha256(tree_bytes).hexdigest()},
        "treeObjects": trees,
        "treeObjectsSha256": canonical_sha256(trees),
        "detachedClean": True,
        "cleanPolicy": "DETACHED_HEAD_EQUALS_REQUESTED_COMMIT_AND_GIT_STATUS_PORCELAIN_V1_UNTRACKED_ALL_EMPTY_IGNORED_BUILD_INPUTS_CAPTURED_SEPARATELY",
        "selectedTrackedFiles": selected,
        "selectedTrackedFilesSha256": canonical_sha256(selected),
    }
    by_path = {row["path"]: row for row in selected}

    def current_descriptor(path: str) -> dict[str, object]:
        raw = (root / path).read_bytes()
        return {"path": path, "byteLength": len(raw), "sha256": sha256(raw).hexdigest()}

    python_descriptor = current_descriptor("_research/dnrd5/example.py")
    manifest["python"]["files"] = [python_descriptor]
    manifest["python"]["filesSha256"] = canonical_sha256([python_descriptor])
    package_descriptor = lambda path: current_descriptor(f"{_PACKAGE}/{path}") | {"path": path}
    typescript = manifest["typescript"]
    typescript["inputs"] = [
        package_descriptor(path)
        for path in (".npmrc", "package-lock.json", "package.json", "tsconfig.build.json", "tsconfig.dnrd5-source-closure.json", "tsconfig.json")
    ]
    typescript["compiler"]["typescriptFiles"] = [
        package_descriptor(path)
        for path in ("node_modules/typescript/lib/tsc.js", "node_modules/typescript/lib/typescript.js", "node_modules/typescript/package.json")
    ]
    typescript["resolvedExternalFiles"] = [package_descriptor("node_modules/effect/dist/dts/index.d.ts")]
    for source in typescript["sources"]:
        descriptor = package_descriptor(source["path"])
        source.update(descriptor)
        for binding in source["imports"]:
            if binding["target"] is not None:
                binding["target"] = package_descriptor(binding["target"]["path"])
    manifest["toolchains"]["typescriptManifestSha256"] = sha256(canonical_bytes(typescript)).hexdigest()
    manifest["evidencePins"] = [
        {"role": role, **by_path[path]} for role, path in _PIN_PATHS
    ]
    return manifest


def test_physical_repository_rehashes_ignored_build_input_and_detects_drift(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    manifest = _physical_manifest(root)
    result = judge_source_build_import_closure(_raw(manifest), repository_root=root)
    assert result.physical_repository_verified is True
    assert result.external_toolchains_verified is False
    assert result.python_import_graph_independently_verified is True
    assert result.python_call_summary_independently_verified is True

    false_import_graph = deepcopy(manifest)
    false_import_graph["python"]["astImportEdges"] = [
        {
            "path": "_research/dnrd5/example.py",
            "line": 1,
            "module": "json",
            "level": 0,
            "name": "loads",
            "alias": None,
            "resolvedPath": None,
            "classification": "PYTHON_STDLIB",
        }
    ]
    false_import_graph["python"]["importGraphSha256"] = canonical_sha256(false_import_graph["python"]["astImportEdges"])
    with pytest.raises(IndependentSourceBuildImportJudgeRefusal) as caught:
        judge_source_build_import_closure(_raw(false_import_graph), repository_root=root)
    assert caught.value.code == "PHYSICAL_PYTHON_AST_INVALID"

    false_call_summary = deepcopy(manifest)
    false_call_summary["python"]["syntacticCallSites"]["sha256"] = "0" * 64
    with pytest.raises(IndependentSourceBuildImportJudgeRefusal) as caught:
        judge_source_build_import_closure(_raw(false_call_summary), repository_root=root)
    assert caught.value.code == "PHYSICAL_PYTHON_AST_INVALID"

    external = root / _PACKAGE / "node_modules/effect/dist/dts/index.d.ts"
    external.write_bytes(b"ignored build input drift\n")
    with pytest.raises(IndependentSourceBuildImportJudgeRefusal) as caught:
        judge_source_build_import_closure(_raw(manifest), repository_root=root)
    assert caught.value.code == "PHYSICAL_DESCRIPTOR_DRIFT"
