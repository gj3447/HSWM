from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256
from _research.dnrd5.source_build_import_closure import (
    CONTRACT_VERSION,
    TYPESCRIPT_CLAIM_BOUNDARY,
    TYPESCRIPT_ENTRYPOINTS,
    TYPESCRIPT_TERMINAL,
    SourceBuildImportClosureRefusal,
    collect_git_source,
    resolve_python_ast_closure,
    validate_typescript_closure,
)


def _descriptor(path: str, byte: str) -> dict[str, object]:
    return {"path": path, "byteLength": 1, "sha256": byte * 64}


_DURABLE_INTERNAL_SEAMS = (
    "commitCanonicalAtomV2DurableFromDnrd5DispatcherInternal",
    "recoverCanonicalAtomV2DurableFromDnrd5DispatcherInternal",
)


def _binding(*, seam: bool = False) -> dict[str, object]:
    return {
        "kind": "static-import",
        "names": (
            [
                {"imported": name, "local": name, "typeOnly": False}
                for name in _DURABLE_INTERNAL_SEAMS
            ]
            if seam
            else [{"imported": "Effect", "local": "Effect", "typeOnly": False}]
        ),
        "position": 0,
        "source": "./canonical-atom-v2-durable-runtime.js",
        "target": _descriptor("src/canonical-atom-v2-durable-runtime.ts", "8"),
        "targetKind": "local-source",
        "typeOnly": False,
    }


def _typescript_fixture() -> dict[str, object]:
    emitted = [_descriptor("entry.js", "1")]
    sources = [
        {
            **_descriptor(path, "a"),
            "exportedSymbols": ["entry"],
            "imports": [
                _binding(seam=True)
            ]
            if path == "src/canonical-atom-v2-dnrd5-durable-permit.ts"
            else [],
        }
        for path in TYPESCRIPT_ENTRYPOINTS
    ]
    sources.append(
        {
            **_descriptor("src/canonical-atom-v2-durable-runtime.ts", "b"),
            "exportedSymbols": ["CanonicalAtomV2DurableRuntime"],
            "imports": [],
        }
    )
    return {
        "contractVersion": CONTRACT_VERSION,
        "claimBoundary": TYPESCRIPT_CLAIM_BOUNDARY,
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
            "nodeExecutable": _descriptor("external-runtime/node", "2"),
            "nodeVersion": "v24.13.0",
            "typescriptFiles": [
                _descriptor("node_modules/typescript/lib/tsc.js", "3"),
                _descriptor("node_modules/typescript/lib/typescript.js", "4"),
                _descriptor("node_modules/typescript/package.json", "5"),
            ],
            "version": "5.9.3",
        },
        "entrypoints": list(TYPESCRIPT_ENTRYPOINTS),
        "inputs": [
            _descriptor(".npmrc", "6"),
            _descriptor("package-lock.json", "7"),
            _descriptor("package.json", "8"),
            _descriptor("tsconfig.build.json", "9"),
            _descriptor("tsconfig.dnrd5-source-closure.json", "c"),
            _descriptor("tsconfig.json", "d"),
        ],
        "emitted": {
            "files": emitted,
            "rootSha256": canonical_sha256(emitted),
        },
        "resolvedExternalFiles": [
            _descriptor("node_modules/effect/dist/dts/index.d.ts", "9")
        ],
        "sources": sources,
        "terminal": TYPESCRIPT_TERMINAL,
    }


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _git_text(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=root, stdin=subprocess.DEVNULL, text=True
    ).strip()


def test_python_ast_graph_is_deterministic_and_exposes_network_capability(
    tmp_path: Path,
) -> None:
    package = tmp_path / "_research" / "dnrd5"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    nested = package / "nested"
    nested.mkdir()
    (nested / "__init__.py").write_text("", encoding="utf-8")
    (nested / "subject.py").write_text("VALUE = 2\n", encoding="utf-8")
    (package / "subject.py").write_text(
        "import json\nimport socket\nfrom . import helper\n\ndef f():\n    return json.dumps(helper.VALUE)\n",
        encoding="utf-8",
    )

    first = resolve_python_ast_closure(tmp_path)
    second = resolve_python_ast_closure(tmp_path)
    assert first == second
    assert "_research/dnrd5/nested/subject.py" in {
        item["path"] for item in first["files"]
    }
    assert first["networkCapableDeferredModules"] == ["socket"]
    helper = next(
        edge for edge in first["astImportEdges"] if edge["name"] == "helper"
    )
    assert helper["resolvedPath"] == "_research/dnrd5/helper.py"


def test_python_dynamic_loading_and_relative_escape_fail_closed(
    tmp_path: Path,
) -> None:
    package = tmp_path / "_research" / "dnrd5"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    subject = package / "subject.py"
    subject.write_text("eval('1 + 1')\n", encoding="utf-8")
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        resolve_python_ast_closure(tmp_path)
    assert caught.value.code == "PYTHON_DYNAMIC_IMPORT_FORBIDDEN"

    subject.write_text(
        "from builtins import __import__ as loader\nloader('os')\n",
        encoding="utf-8",
    )
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        resolve_python_ast_closure(tmp_path)
    assert caught.value.code == "PYTHON_DYNAMIC_IMPORT_FORBIDDEN"

    subject.write_text("loader = eval\nloader('1 + 1')\n", encoding="utf-8")
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        resolve_python_ast_closure(tmp_path)
    assert caught.value.code == "PYTHON_DYNAMIC_IMPORT_FORBIDDEN"

    subject.write_text(
        "import builtins\nloader = builtins.eval\nloader('1 + 1')\n",
        encoding="utf-8",
    )
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        resolve_python_ast_closure(tmp_path)
    assert caught.value.code == "PYTHON_DYNAMIC_IMPORT_FORBIDDEN"

    subject.write_text("from ...outside import value\n", encoding="utf-8")
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        resolve_python_ast_closure(tmp_path)
    assert caught.value.code == "PYTHON_IMPORT_CLOSURE_INVALID"


def test_typescript_closure_recomputes_build_root_and_dispatch_seam() -> None:
    fixture = _typescript_fixture()
    assert validate_typescript_closure(canonical_bytes(fixture))["dispatchBudget"] == 0

    root_drift = deepcopy(fixture)
    root_drift["emitted"]["rootSha256"] = "f" * 64
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        validate_typescript_closure(canonical_bytes(root_drift))
    assert caught.value.code == "BUILD_TREE_INVALID"

    loader = deepcopy(fixture)
    loader["sources"][0]["imports"][0]["kind"] = "runtime-dynamic-import"
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        validate_typescript_closure(canonical_bytes(loader))
    assert caught.value.code == "TS_RUNTIME_LOADER_FORBIDDEN"

    missing = deepcopy(fixture)
    missing["sources"][0]["imports"][0]["names"].pop()
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        validate_typescript_closure(canonical_bytes(missing))
    assert caught.value.code == "TS_DISPATCH_SEAM_INVALID"

    renamed = deepcopy(fixture)
    renamed["sources"][0]["imports"][0]["names"][0]["local"] = "renamed"
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        validate_typescript_closure(canonical_bytes(renamed))
    assert caught.value.code == "TS_DISPATCH_SEAM_INVALID"

    additional = deepcopy(fixture)
    additional["sources"][1]["imports"].append(_binding(seam=True))
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        validate_typescript_closure(canonical_bytes(additional))
    assert caught.value.code == "TS_DISPATCH_SEAM_INVALID"


def test_typescript_closure_requires_exact_canonical_bytes() -> None:
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        validate_typescript_closure(b" " + canonical_bytes(_typescript_fixture()))
    assert caught.value.code == "TS_RESOLUTION_INVALID"


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda fixture: fixture["sources"][0].update(
                {"exportedSymbols": [{"not": "a string"}]}
            ),
            "TS_RESOLUTION_INVALID",
        ),
        (
            lambda fixture: fixture.update({"entrypoints": [1]}),
            "TS_RESOLUTION_INVALID",
        ),
        (
            lambda fixture: fixture["sources"][0]["imports"][0].update(
                {"position": False}
            ),
            "TS_RESOLUTION_INVALID",
        ),
        (
            lambda fixture: fixture["sources"][0]["imports"][0].update(
                {"names": [{"imported": 1, "local": "x", "typeOnly": False}]}
            ),
            "TS_RESOLUTION_INVALID",
        ),
        (
            lambda fixture: fixture["inputs"][0].update({"path": 7}),
            "PATH_CLOSURE_INVALID",
        ),
        (
            lambda fixture: fixture.update({"dispatchBudget": False}),
            "TS_RESOLUTION_INVALID",
        ),
        (
            lambda fixture: fixture.update(
                {"claimBoundary": "SOURCE_A_PROVIDER_OCCURRENCE_AUTHORIZED"}
            ),
            "TS_RESOLUTION_INVALID",
        ),
    ],
)
def test_typescript_closure_refuses_hostile_field_types(mutate, code: str) -> None:
    fixture = _typescript_fixture()
    mutate(fixture)
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        validate_typescript_closure(canonical_bytes(fixture))
    assert caught.value.code == code


def test_git_capture_reads_blobs_and_requires_detached_clean_checkout(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source = root / "_research" / "dnrd5"
    source.mkdir(parents=True)
    (source / "sample.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "test")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "fixture")
    original = _git_text(root, "rev-parse", "HEAD")
    _git(root, "checkout", "--detach", "-q")

    captured = collect_git_source(root)
    assert captured["detachedClean"] is True
    assert captured["commit"] == original
    assert captured["commitObject"]["byteLength"] > 0
    assert len(captured["commitObject"]["sha256"]) == 64
    assert captured["treeObject"]["byteLength"] > 0
    assert len(captured["treeObject"]["sha256"]) == 64
    assert len(captured["selectedTrackedFiles"]) == 1
    assert captured["selectedTrackedFiles"][0]["path"] == (
        "_research/dnrd5/sample.py"
    )

    _git(root, "commit", "--allow-empty", "-qm", "alternate")
    alternate = _git_text(root, "rev-parse", "HEAD")
    _git(root, "checkout", "--detach", "-q", original)
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        collect_git_source(root, alternate)
    assert caught.value.code == "WORKTREE_NOT_DETACHED_CLEAN"

    (source / "sample.py").write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(SourceBuildImportClosureRefusal) as caught:
        collect_git_source(root)
    assert caught.value.code == "WORKTREE_NOT_DETACHED_CLEAN"


def test_git_capture_ignores_replacement_refs(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source = root / "_research" / "dnrd5"
    source.mkdir(parents=True)
    (source / "sample.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "test")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "original")
    original = _git_text(root, "rev-parse", "HEAD")
    (source / "sample.py").write_text("VALUE = 2\n", encoding="utf-8")
    _git(root, "commit", "-qam", "replacement")
    replacement = _git_text(root, "rev-parse", "HEAD")
    _git(root, "checkout", "--detach", "-q", original)
    _git(root, "replace", original, replacement)

    captured = collect_git_source(root)
    assert captured["commit"] == original
    record = captured["selectedTrackedFiles"][0]
    assert record["sha256"] == __import__("hashlib").sha256(b"VALUE = 1\n").hexdigest()
