"""Verify the seven-layer Longinus binding from an immutable Git commit."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    REPO_ROOT / "LONGINUS_HSWM_F1_ABORTED_EXPOSURE_BINDING_2026-07-30.json"
)
SCHEMA = "longinus-hswm-f1-r8-premeasurement-binding/v9"
EXPECTED_BINDING_ID = "longinus-hswm-f1-r8-aborted-exposure-v9-20260730"
EXPECTED_IMPLEMENTATION_COMMIT = "f117cfdd6b058d1e6db131a19425084d642cdf0c"
EXPECTED_IMPLEMENTATION_PARENT = "6f25ce51cfae5a6d86a4a0bc5c385bd073356094"
EXPECTED_INCIDENT_RECEIPT_SHA256 = (
    "6d3f2f8978a8502c0f01135ad7b998841dbb4bd61462934927f735e3932bad7d"
)
EXPECTED_IMPLEMENTATION_BINDINGS = 6
EXPECTED_TEST_BINDINGS = 8
EXPECTED_ARTIFACT_BINDINGS = 1
REQUIRED_LAYERS = (
    "KG_NODE",
    "CONTRACT_BINDING",
    "CODE_SYMBOL",
    "FILE_LINE",
    "LINE_RANGE",
    "SHA256",
    "CRATE_SCRIPT",
)
REQUIRED_BINDING_KEYS = {
    "kg_node",
    "contract_binding",
    "code_symbol",
    "file_line",
    "line_range",
    "sha256",
    "crate_script",
}
ALLOWED_CONTRACT_BINDINGS = {
    "R8_PREMEASUREMENT_IMPLEMENTATION__UNJUDGED",
    "R8_PREMEASUREMENT_TEST__ENGINEERING_ONLY",
    "R8_ABORTED_EXPOSURE_ARTIFACT__QUARANTINED",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
LINE_RANGE_RE = re.compile(r"^([1-9][0-9]*)-([1-9][0-9]*)$")


class BindingError(ValueError):
    """A classified Longinus binding failure."""

    def __init__(self, classification: str, message: str) -> None:
        self.classification = classification
        super().__init__(f"{classification}: {message}")


def _fail(classification: str, message: str) -> None:
    raise BindingError(classification, message)


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _fail("LABEL_ROT", f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> object:
    _fail("LABEL_ROT", f"non-finite JSON number: {value}")


def _exact_json_equal(actual: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return (
            isinstance(actual, Mapping)
            and set(actual) == set(expected)
            and all(
                _exact_json_equal(actual[key], expected[key])
                for key in expected
            )
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                _exact_json_equal(left, right)
                for left, right in zip(actual, expected, strict=True)
            )
        )
    return type(actual) is type(expected) and actual == expected


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except BindingError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        _fail("MISSING", f"cannot load binding manifest: {error}")
    if not isinstance(value, dict):
        _fail("LABEL_ROT", "binding manifest must be one JSON object")
    return value


def _git(arguments: Sequence[str], *, classification: str, label: str) -> bytes:
    environ = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environ["GIT_NO_REPLACE_OBJECTS"] = "1"
    environ["GIT_LITERAL_PATHSPECS"] = "1"
    completed = subprocess.run(
        ["git", "--no-replace-objects", *arguments],
        cwd=REPO_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environ,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        _fail(classification, f"{label}: {detail or 'git command failed'}")
    return completed.stdout


def _commit_blob(commit: str, relative: str) -> bytes:
    path = Path(relative)
    if not relative or path.is_absolute() or ".." in path.parts:
        _fail("MISSING", f"unsafe source path: {relative!r}")
    object_type = _git(
        ["cat-file", "-t", f"{commit}:{relative}"],
        classification="MISSING",
        label=f"missing Git object {relative}",
    ).decode("ascii", "strict").strip()
    if object_type != "blob":
        _fail("MISSING", f"directory/non-blob binding forbidden: {relative}")
    return _git(
        ["show", f"{commit}:{relative}"],
        classification="MISSING",
        label=f"cannot read Git blob {relative}",
    )


def _parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    result = [item.arg for item in (*node.args.posonlyargs, *node.args.args)]
    if node.args.vararg is not None:
        result.append(f"*{node.args.vararg.arg}")
    result.extend(item.arg for item in node.args.kwonlyargs)
    if node.args.kwarg is not None:
        result.append(f"**{node.args.kwarg.arg}")
    return result


def _symbol_range(
    blob: bytes, path: str, expected: Mapping[str, object]
) -> tuple[int, int]:
    name = expected.get("name")
    kind = expected.get("kind")
    expected_parameters = expected.get("parameters")
    if not isinstance(expected_parameters, list) or not all(
        isinstance(item, str) for item in expected_parameters
    ):
        _fail("LABEL_ROT", f"invalid parameter labels for {path}:{name}")
    if kind == "json_receipt":
        if expected_parameters:
            _fail("LABEL_ROT", f"JSON receipt parameters must be empty for {path}")
        try:
            decoded = blob.decode("utf-8")
            value = json.loads(
                decoded,
                object_pairs_hook=_reject_duplicates,
                parse_constant=_reject_constant,
            )
        except BindingError:
            raise
        except (UnicodeError, json.JSONDecodeError) as error:
            _fail("SIGNATURE_MISMATCHED", f"cannot parse JSON receipt {path}: {error}")
        if not isinstance(value, dict) or value.get("schema_version") != name:
            _fail("SIGNATURE_MISMATCHED", f"JSON receipt schema drifted for {path}")
        if expected.get("qualified") != f"{path}#schema_version":
            _fail("LABEL_ROT", f"qualified JSON symbol rotated for {path}")
        declared = value.get("aborted_attempt_exposure_receipt_sha256")
        unsigned = dict(value)
        unsigned.pop("aborted_attempt_exposure_receipt_sha256", None)
        canonical = json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if (
            declared != EXPECTED_INCIDENT_RECEIPT_SHA256
            or hashlib.sha256(canonical).hexdigest() != declared
        ):
            _fail("DIVERGENT", f"JSON receipt self-hash drifted for {path}")
        schema_lines = [
            index
            for index, line in enumerate(decoded.splitlines(), start=1)
            if '"schema_version"' in line
        ]
        if len(schema_lines) != 1:
            _fail("SIGNATURE_MISMATCHED", f"JSON receipt schema line drifted for {path}")
        return schema_lines[0], schema_lines[0]

    try:
        tree = ast.parse(blob.decode("utf-8"), filename=path)
    except (UnicodeError, SyntaxError) as error:
        _fail("SIGNATURE_MISMATCHED", f"cannot parse {path}: {error}")
    if not isinstance(name, str) or kind not in {"class", "function"}:
        _fail("LABEL_ROT", f"invalid code_symbol label for {path}")
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        _fail("ORPHANED", f"top-level symbol {name!r} occurs {len(matches)} times in {path}")
    node = matches[0]
    actual_kind = "class" if isinstance(node, ast.ClassDef) else "function"
    if actual_kind != kind:
        _fail("SIGNATURE_MISMATCHED", f"{path}:{name} kind {actual_kind} != {kind}")
    actual_parameters = [] if isinstance(node, ast.ClassDef) else _parameters(node)
    if actual_parameters != expected_parameters:
        _fail(
            "SIGNATURE_MISMATCHED",
            f"{path}:{name} parameters {actual_parameters!r} != {expected_parameters!r}",
        )
    module = path[:-3].replace("/", ".") if path.endswith(".py") else path.replace("/", ".")
    if expected.get("qualified") != f"{module}.{name}":
        _fail("LABEL_ROT", f"qualified symbol label rotated for {path}:{name}")
    node_end = getattr(node, "end_lineno", None)
    if not isinstance(node_end, int):
        _fail("SIGNATURE_MISMATCHED", f"symbol end line missing for {path}:{name}")
    return int(node.lineno), node_end


def verify(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, object]:
    manifest = _load(manifest_path)
    if manifest.get("schema") != SCHEMA:
        _fail("LABEL_ROT", f"schema must be {SCHEMA}")
    if manifest.get("binding_id") != EXPECTED_BINDING_ID:
        _fail("LABEL_ROT", "binding identity drifted")
    if manifest.get("binding_state") != "PIERCED_LOCAL_NO_KG_WRITE":
        _fail("LABEL_ROT", "local/no-KG-write boundary drifted")
    if manifest.get("scientific_status") != "UNJUDGED":
        _fail("LABEL_ROT", "scientific status must remain UNJUDGED")
    inadmissible = "EXPLORATORY_ENGINEERING_ONLY__PREREGISTRATION_INADMISSIBLE"
    if manifest.get("evidence_class") != inadmissible or manifest.get("r7_status") != inadmissible:
        _fail("LABEL_ROT", "r7 exploratory/inadmissible boundary drifted")
    incident_boundary = manifest.get("incident_boundary")
    expected_incident_boundary = {
        "aborted_attempt_exposure_receipt_sha256": (
            EXPECTED_INCIDENT_RECEIPT_SHA256
        ),
        "historical_upstream_model_calls": 1,
        "prospective_successor_model_calls": 0,
        "confirmatory_upstream_model_calls": 0,
        "scientific_verdicts": 0,
    }
    if (
        manifest.get("b22_gate") != "LOCKED"
        or type(manifest.get("model_calls")) is not int
        or manifest.get("model_calls") != 1
        or not _exact_json_equal(
            incident_boundary, expected_incident_boundary
        )
    ):
        _fail("LABEL_ROT", "B22/quarantined model-call boundary drifted")
    if manifest.get("layers") != list(REQUIRED_LAYERS):
        _fail("LABEL_ROT", "Longinus seven-layer order drifted")
    kg = manifest.get("kg")
    if not isinstance(kg, dict) or kg.get("write_state") != "NOT_AUTHORIZED_NOT_WRITTEN":
        _fail("LABEL_ROT", "KG write boundary drifted")
    for field in ("provenance_actor", "source_path", "timestamp", "baseline_scope"):
        if not isinstance(kg.get(field), str) or not kg[field]:
            _fail("LABEL_ROT", f"KG provenance field missing: {field}")

    git = manifest.get("git")
    if not isinstance(git, dict):
        _fail("MISSING", "git binding is missing")
    commit = git.get("implementation_commit")
    if not isinstance(commit, str) or COMMIT_RE.fullmatch(commit) is None:
        _fail("MISSING", "implementation commit is missing")
    parent = git.get("implementation_parent")
    if not isinstance(parent, str) or COMMIT_RE.fullmatch(parent) is None:
        _fail("MISSING", "implementation baseline parent is missing")
    if (
        commit != EXPECTED_IMPLEMENTATION_COMMIT
        or parent != EXPECTED_IMPLEMENTATION_PARENT
        or kg.get("baseline_scope") != commit
    ):
        _fail("LABEL_ROT", "implementation commit/baseline identity drifted")
    _git(["cat-file", "-e", f"{commit}^{{commit}}"], classification="MISSING", label="commit missing")
    _git(
        ["cat-file", "-e", f"{parent}^{{commit}}"],
        classification="MISSING",
        label="baseline parent missing",
    )
    _git(
        ["merge-base", "--is-ancestor", parent, commit],
        classification="DIVERGENT",
        label="baseline parent is not an ancestor of implementation commit",
    )
    _git(
        ["merge-base", "--is-ancestor", commit, "HEAD"],
        classification="DIVERGENT",
        label="implementation commit is not an ancestor of HEAD",
    )

    target_paths = manifest.get("required_target_paths")
    if not isinstance(target_paths, list) or not target_paths or not all(
        isinstance(path, str) and path for path in target_paths
    ):
        _fail("MISSING", "required target inventory is missing")
    if len(target_paths) != len(set(target_paths)):
        _fail("ORPHANED", "required target inventory contains duplicates")
    bindings = manifest.get("bindings")
    if not isinstance(bindings, list) or not bindings:
        _fail("MISSING", "bindings are missing")

    seen_paths: set[str] = set()
    seen_nodes: set[str] = set()
    implementation_count = 0
    test_count = 0
    artifact_count = 0
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            _fail("MISSING", f"binding {index} is not an object")
        if set(binding) != REQUIRED_BINDING_KEYS:
            _fail("LABEL_ROT", f"binding {index} does not expose exactly seven layers")
        kg_node = binding.get("kg_node")
        if not isinstance(kg_node, str) or not kg_node.startswith("LOCAL_PROPOSED_"):
            _fail("LABEL_ROT", f"binding {index} invents or omits a local KG identity")
        if kg_node in seen_nodes:
            _fail("ORPHANED", f"duplicate local KG identity: {kg_node}")
        seen_nodes.add(kg_node)
        contract = binding.get("contract_binding")
        if contract not in ALLOWED_CONTRACT_BINDINGS:
            _fail("LABEL_ROT", f"binding {index} contract label rotated")
        implementation_count += contract.endswith("__UNJUDGED")
        test_count += contract.endswith("__ENGINEERING_ONLY")
        artifact_count += contract.endswith("__QUARANTINED")

        file_line = binding.get("file_line")
        if not isinstance(file_line, str) or ":" not in file_line:
            _fail("MISSING", f"binding {index} file_line is missing")
        relative, line_text = file_line.rsplit(":", 1)
        if relative in seen_paths:
            _fail("ORPHANED", f"multiple bindings target one file: {relative}")
        seen_paths.add(relative)
        if relative not in target_paths:
            _fail("ORPHANED", f"binding targets an unregistered path: {relative}")
        blob = _commit_blob(commit, relative)
        expected_sha = binding.get("sha256")
        if not isinstance(expected_sha, str) or SHA256_RE.fullmatch(expected_sha) is None:
            _fail("MISSING", f"invalid SHA-256 label for {relative}")
        actual_sha = hashlib.sha256(blob).hexdigest()
        if actual_sha != expected_sha:
            _fail("DIVERGENT", f"Git blob SHA drifted for {relative}")

        code_symbol = binding.get("code_symbol")
        if not isinstance(code_symbol, dict):
            _fail("MISSING", f"code symbol binding missing for {relative}")
        symbol_start, symbol_end = _symbol_range(blob, relative, code_symbol)
        line_range = binding.get("line_range")
        match = LINE_RANGE_RE.fullmatch(str(line_range))
        if match is None:
            _fail("MISSING", f"line range missing for {relative}")
        start, end = int(match.group(1)), int(match.group(2))
        if start != symbol_start or end != symbol_end or line_text != str(start):
            _fail("DIVERGENT", f"AST/file line range drifted for {relative}")

        crate_script = binding.get("crate_script")
        if not isinstance(crate_script, str) or not crate_script.startswith("python -m pytest -q "):
            _fail("LABEL_ROT", f"unsafe or missing crate script for {relative}")
        test_path = crate_script.removeprefix("python -m pytest -q ")
        if test_path not in target_paths or not Path(test_path).name.startswith("test_"):
            _fail("ORPHANED", f"crate script for {relative} is not bound to a target test")

    missing = set(target_paths) - seen_paths
    extra = seen_paths - set(target_paths)
    if missing or extra:
        _fail("ORPHANED", f"target reverse scan mismatch missing={sorted(missing)} extra={sorted(extra)}")
    changed_paths = {
        path
        for path in _git(
            [
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                parent,
                commit,
            ],
            classification="DIVERGENT",
            label="cannot derive implementation baseline diff",
        )
        .decode("utf-8", "strict")
        .splitlines()
        if path
    }
    unbound_changes = changed_paths - seen_paths
    if unbound_changes:
        _fail(
            "ORPHANED",
            f"implementation baseline diff is not reverse-bound: {sorted(unbound_changes)}",
        )
    if (
        implementation_count != EXPECTED_IMPLEMENTATION_BINDINGS
        or test_count != EXPECTED_TEST_BINDINGS
        or artifact_count != EXPECTED_ARTIFACT_BINDINGS
    ):
        _fail(
            "LABEL_ROT",
            "implementation/test/artifact binding labels are not 6/8/1",
        )

    return {
        "status": "PASS",
        "binding_id": manifest.get("binding_id"),
        "implementation_commit": commit,
        "bindings_checked": len(bindings),
        "files_checked": len(seen_paths),
        "implementation_bindings": implementation_count,
        "test_bindings": test_count,
        "artifact_bindings": artifact_count,
        "baseline_changed_paths": len(changed_paths),
        "longinus_layers": len(REQUIRED_LAYERS),
        "classifications": {
            "MISSING": 0,
            "ORPHANED": 0,
            "SIGNATURE_MISMATCHED": 0,
            "DIVERGENT": 0,
            "LABEL_ROT": 0,
        },
        "blob_authority": "GIT_COMMIT_ONLY",
        "kg_write_state": kg["write_state"],
        "scientific_status": manifest["scientific_status"],
        "b22_gate": manifest["b22_gate"],
        "historical_upstream_model_calls": incident_boundary[
            "historical_upstream_model_calls"
        ],
        "prospective_successor_model_calls": incident_boundary[
            "prospective_successor_model_calls"
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?", default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    try:
        result = verify(args.manifest)
    except BindingError as error:
        print(
            json.dumps(
                {"status": "FAIL", "classification": error.classification, "error": str(error)},
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
