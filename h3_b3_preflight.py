"""First-write H3/B3 precompute no-op gate receipt.

The nine tests below are the executable form of preregistration section 3.
Callers cannot supply node ids: this module always executes the frozen mapping
from a fixed repository root with third-party pytest plugin autoload disabled.
Each result binds the exact test-function AST span and captured process output.
The receipt also seals every distinct gate test file in full, so edits to
helpers, imports, fixtures, and other module-level code invalidate the gate
evidence even when the selected test function itself is unchanged.

Longinus ReferenceSite:
``HSWM/H3_B3_COMPOSITION_PREREG_2026-07-20.md`` section 3.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, fields
from hashlib import sha256
import argparse
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterator, Sequence

import h3_artifact_lifecycle as lifecycle
from world_ir import canonical_json, content_id


SCHEMA_VERSION = "hswm-h3-b3-preflight/v4"
REPO_ROOT = Path(__file__).resolve().parent
PYTEST_COMMAND_PREFIX = (
    sys.executable, "-m", "pytest", "-q", "--tb=short",
    "-p", "no:cacheprovider",
)
# Exact match for h3_b3_falsifier.FROZEN_CODE_MODULE_PATHS, duplicated here
# deliberately so this preflight never imports the evaluator that imports it.
# Manifest integration must compare the root of this exact set, not a handpicked
# subset, with lifecycle.authorization_code_root(manifest["code_sha256"]).
FROZEN_IMPLEMENTATION_MODULE_PATHS: tuple[str, ...] = (
    "h3_b3_falsifier.py",
    "h3_arc_adjudicator.py",
    "h3_artifact_lifecycle.py",
    "h3_b3_preflight.py",
    "model_deployment_receipt.py",
    "bge_m3_embed.py",
    "recorded_llm_extractor.py",
    "h3_fresh_manifest.py",
    "h3_b3_prepare.py",
    "claim_builder.py",
    "typed_composition.py",
    "title_anchor_builder.py",
    "composition.py",
    "relation_eval.py",
    "metrics.py",
    "world_ir.py",
)
GATE_NODEIDS: tuple[tuple[int, str, str], ...] = (
    (
        1,
        "non_title_b3_added_adjacency",
        "tests/test_claim_builder.py::"
        "test_shared_exact_claim_roles_create_topology_beyond_title_anchors",
    ),
    (
        2,
        "typed_vs_untyped_score",
        "tests/test_typed_composition.py::"
        "test_relation_mismatch_blocks_second_edge_but_untyped_control_does_not",
    ),
    (
        3,
        "k2_not_k1_depth2",
        "tests/test_h3_b3_end_to_end.py::"
        "test_b3_non_title_two_edge_chain_first_reaches_gold_at_depth_two",
    ),
    (
        4,
        "break_second_edge_kills",
        "tests/test_typed_composition.py::"
        "test_second_edge_target_shuffle_kills_the_depth_two_target",
    ),
    (
        5,
        "mu0_bit_identity",
        "tests/test_typed_composition.py::"
        "test_mu_zero_is_bit_identical_and_never_claims_composition",
    ),
    (
        6,
        "two_selectors_intermediate_receipt",
        "tests/test_typed_composition.py::"
        "test_two_hop_typed_path_beats_matched_k1_and_preserves_full_receipt",
    ),
    (
        7,
        "no_claim_switch",
        "tests/test_typed_composition.py::"
        "test_two_claims_in_one_paragraph_cannot_illegally_switch_claim_identity",
    ),
    (
        8,
        "no_target_predicate_lookahead",
        "tests/test_typed_composition.py::"
        "test_target_predicate_and_role_cannot_look_ahead_to_score_current_hop",
    ),
    (
        9,
        "query_atomic_fanout_hub_trip",
        "tests/test_typed_composition.py::"
        "test_fanout_and_join_hub_gates_fail_closed",
    ),
)
FROZEN_GATE_SOURCE_PATHS: tuple[str, ...] = (
    "tests/test_claim_builder.py",
    "tests/test_typed_composition.py",
    "tests/test_h3_b3_end_to_end.py",
)
FROZEN_GATE_SOURCE_CODE_ROOT_SHA256 = (
    "2218428e2767689ebd538d99aad54031c8dcefdfc2913b43ed5e843f3513ddf5"
)
FROZEN_EXECUTION_SUPPORT_PATHS: tuple[str, ...] = ("pyproject.toml",)
FROZEN_EXECUTION_SOURCE_PATHS: tuple[str, ...] = (
    FROZEN_IMPLEMENTATION_MODULE_PATHS
    + FROZEN_GATE_SOURCE_PATHS
    + FROZEN_EXECUTION_SUPPORT_PATHS
)


class PreflightError(ValueError):
    """The fixed mapping, subprocess evidence, or receipt is invalid."""


class _DuplicateJSONKey(ValueError):
    pass


@dataclass(frozen=True)
class GateResultV1:
    gate: int
    gate_name: str
    nodeid: str
    source_path: str
    source_symbol: str
    source_start_line: int
    source_end_line: int
    ast_span_sha256: str
    gate_source_file_sha256: str
    execution_source_root_sha256: str
    command: tuple[str, ...]
    stdout: str
    stdout_sha256: str
    stderr: str
    stderr_sha256: str
    returncode: int
    result_sha256: str
    passed: bool
    duration_ms: int


@dataclass(frozen=True)
class ImplementationModuleV1:
    path: str
    sha256: str


@dataclass(frozen=True)
class GateSourceFileV1:
    path: str
    sha256: str


@dataclass(frozen=True)
class ExecutionSourceFileV1:
    path: str
    sha256: str


@dataclass(frozen=True)
class PrivateExecutionSnapshotV1:
    root: Path
    files: tuple[ExecutionSourceFileV1, ...]
    root_sha256: str


@dataclass(frozen=True)
class PreflightReceiptV1:
    schema_version: str
    receipt_id: str
    receipt_sha256: str
    cwd: str
    pytest_disable_plugin_autoload: str
    python_executable: str
    gate_mapping_sha256: str
    implementation_modules: tuple[ImplementationModuleV1, ...]
    implementation_code_root_sha256: str
    gate_source_files: tuple[GateSourceFileV1, ...]
    gate_source_code_root_sha256: str
    execution_source_files: tuple[ExecutionSourceFileV1, ...]
    execution_source_root_sha256: str
    gate_count: int
    all_passed: bool
    gates: tuple[GateResultV1, ...]


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise _DuplicateJSONKey(f"duplicate JSON key: {key}")
        value[key] = child
    return value


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def implementation_snapshot() -> tuple[ImplementationModuleV1, ...]:
    """Hash the exact implementation set exercised/authorized by H3."""

    if len(FROZEN_IMPLEMENTATION_MODULE_PATHS) != len(
        set(FROZEN_IMPLEMENTATION_MODULE_PATHS)
    ):
        raise PreflightError("frozen implementation module mapping has duplicates")
    rows: list[ImplementationModuleV1] = []
    repository_root = REPO_ROOT.resolve(strict=True)
    for relative in FROZEN_IMPLEMENTATION_MODULE_PATHS:
        key = Path(relative)
        if (key.is_absolute() or key.as_posix() != relative
                or ".." in key.parts or len(key.parts) != 1):
            raise PreflightError(
                f"implementation module path is not canonical: {relative!r}"
            )
        declared = repository_root / key
        if declared.is_symlink():
            raise PreflightError(
                f"implementation module may not be a symlink: {relative}"
            )
        try:
            resolved = declared.resolve(strict=True)
            resolved.relative_to(repository_root)
        except (OSError, ValueError) as exc:
            raise PreflightError(
                f"implementation module escapes repository: {relative}"
            ) from exc
        if not resolved.is_file():
            raise PreflightError(f"implementation module is missing: {relative}")
        rows.append(ImplementationModuleV1(
            path=relative, sha256=_file_sha256(resolved),
        ))
    return tuple(rows)


def implementation_code_root_sha256(
    modules: Sequence[ImplementationModuleV1] | None = None,
) -> str:
    rows = tuple(modules) if modules is not None else implementation_snapshot()
    if tuple(item.path for item in rows) != FROZEN_IMPLEMENTATION_MODULE_PATHS:
        raise PreflightError("implementation module mapping is not the frozen set")
    mapping = {item.path: item.sha256 for item in rows}
    try:
        return lifecycle.authorization_code_root(mapping)
    except lifecycle.ArtifactLifecycleError as exc:
        raise PreflightError("implementation module hash mapping is invalid") from exc


def gate_source_snapshot() -> tuple[GateSourceFileV1, ...]:
    """Hash every distinct file that supplies one or more frozen gate nodes."""

    mapped_paths = tuple(dict.fromkeys(_node_parts(item[2])[0] for item in GATE_NODEIDS))
    if mapped_paths != FROZEN_GATE_SOURCE_PATHS:
        raise PreflightError("gate source file mapping is not the frozen set")
    repository_root = REPO_ROOT.resolve(strict=True)
    rows: list[GateSourceFileV1] = []
    for relative in FROZEN_GATE_SOURCE_PATHS:
        key = Path(relative)
        if (key.is_absolute() or key.as_posix() != relative
                or ".." in key.parts or len(key.parts) < 2):
            raise PreflightError(
                f"gate source path is not canonical: {relative!r}"
            )
        declared = repository_root / key
        if declared.is_symlink():
            raise PreflightError(f"gate source may not be a symlink: {relative}")
        try:
            resolved = declared.resolve(strict=True)
            resolved.relative_to(repository_root)
        except (OSError, ValueError) as exc:
            raise PreflightError(
                f"gate source escapes repository: {relative}"
            ) from exc
        if not resolved.is_file():
            raise PreflightError(f"gate source is missing: {relative}")
        rows.append(GateSourceFileV1(
            path=relative, sha256=_file_sha256(resolved),
        ))
    return tuple(rows)


def gate_source_code_root_sha256(
    sources: Sequence[GateSourceFileV1] | None = None,
) -> str:
    rows = tuple(sources) if sources is not None else gate_source_snapshot()
    if tuple(item.path for item in rows) != FROZEN_GATE_SOURCE_PATHS:
        raise PreflightError("gate source file mapping is not the frozen set")
    mapping = {item.path: item.sha256 for item in rows}
    try:
        return lifecycle.authorization_code_root(mapping)
    except lifecycle.ArtifactLifecycleError as exc:
        raise PreflightError("gate source file hash mapping is invalid") from exc


def _require_frozen_gate_source_root(
    sources: Sequence[GateSourceFileV1],
) -> str:
    root = gate_source_code_root_sha256(sources)
    if root != FROZEN_GATE_SOURCE_CODE_ROOT_SHA256:
        raise PreflightError("gate source code root differs from frozen root")
    return root


def _declared_source_file(
    root: Path, relative: str, *, label: str,
) -> Path:
    repository_root = root.resolve(strict=True)
    key = Path(relative)
    if (key.is_absolute() or key.as_posix() != relative
            or ".." in key.parts or not key.parts):
        raise PreflightError(f"{label} path is not canonical: {relative!r}")
    declared = repository_root / key
    if declared.is_symlink():
        raise PreflightError(f"{label} may not be a symlink: {relative}")
    try:
        resolved = declared.resolve(strict=True)
        resolved.relative_to(repository_root)
    except (OSError, ValueError) as exc:
        raise PreflightError(f"{label} escapes repository: {relative}") from exc
    if not resolved.is_file():
        raise PreflightError(f"{label} is missing: {relative}")
    return resolved


def execution_source_snapshot(
    root: Path | None = None,
) -> tuple[ExecutionSourceFileV1, ...]:
    """Hash the complete private-tree input used by every gate subprocess."""

    if len(FROZEN_EXECUTION_SOURCE_PATHS) != len(
        set(FROZEN_EXECUTION_SOURCE_PATHS)
    ):
        raise PreflightError("execution source mapping has duplicates")
    source_root = REPO_ROOT if root is None else root
    return tuple(
        ExecutionSourceFileV1(
            path=relative,
            sha256=_file_sha256(_declared_source_file(
                source_root, relative, label="execution source",
            )),
        )
        for relative in FROZEN_EXECUTION_SOURCE_PATHS
    )


def execution_source_root_sha256(
    sources: Sequence[ExecutionSourceFileV1] | None = None,
) -> str:
    rows = tuple(sources) if sources is not None else execution_source_snapshot()
    if tuple(item.path for item in rows) != FROZEN_EXECUTION_SOURCE_PATHS:
        raise PreflightError("execution source mapping is not the frozen set")
    try:
        return lifecycle.authorization_code_root({
            item.path: item.sha256 for item in rows
        })
    except lifecycle.ArtifactLifecycleError as exc:
        raise PreflightError("execution source hash mapping is invalid") from exc


def _set_tree_writable(root: Path) -> None:
    if not root.exists():
        return
    for directory, child_dirs, files in os.walk(root, topdown=False):
        for name in files:
            os.chmod(Path(directory) / name, 0o600)
        for name in child_dirs:
            os.chmod(Path(directory) / name, 0o700)
        os.chmod(directory, 0o700)


@contextmanager
def private_execution_snapshot(
    expected: Sequence[ExecutionSourceFileV1],
) -> Iterator[PrivateExecutionSnapshotV1]:
    """Copy the exact gate inputs to a private, verified, read-only tree."""

    expected_tuple = tuple(expected)
    if tuple(item.path for item in expected_tuple) != FROZEN_EXECUTION_SOURCE_PATHS:
        raise PreflightError("private snapshot input mapping is not frozen")
    with tempfile.TemporaryDirectory(prefix="hswm-h3-preflight-") as raw:
        snapshot_root = (Path(raw).resolve() / "repository")
        snapshot_root.mkdir(mode=0o700)
        try:
            for item in expected_tuple:
                source = _declared_source_file(
                    REPO_ROOT, item.path, label="live execution source",
                )
                if _file_sha256(source) != item.sha256:
                    raise PreflightError(
                        f"live execution source changed before copy: {item.path}"
                    )
                destination = snapshot_root / item.path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                if _file_sha256(destination) != item.sha256:
                    raise PreflightError(
                        f"private execution copy hash mismatch: {item.path}"
                    )
            copied = execution_source_snapshot(snapshot_root)
            if copied != expected_tuple:
                raise PreflightError("private execution snapshot differs from live seal")
            for directory, child_dirs, files in os.walk(
                snapshot_root, topdown=False,
            ):
                for name in files:
                    os.chmod(Path(directory) / name, 0o400)
                for name in child_dirs:
                    os.chmod(Path(directory) / name, 0o500)
                os.chmod(directory, 0o500)
            copied_readonly = execution_source_snapshot(snapshot_root)
            if copied_readonly != expected_tuple:
                raise PreflightError("read-only execution snapshot hash mismatch")
            yield PrivateExecutionSnapshotV1(
                root=snapshot_root,
                files=copied_readonly,
                root_sha256=execution_source_root_sha256(copied_readonly),
            )
        finally:
            _set_tree_writable(snapshot_root)


def gate_mapping_sha256() -> str:
    return _sha256_text(canonical_json(GATE_NODEIDS))


def _node_parts(nodeid: str) -> tuple[str, str]:
    parts = nodeid.split("::")
    if len(parts) != 2 or not parts[0].endswith(".py") or not parts[1]:
        raise PreflightError(f"invalid frozen nodeid {nodeid!r}")
    return parts[0], parts[1]


def _ast_span(
    nodeid: str, *, root: Path | None = None,
) -> tuple[str, str, int, int, str]:
    relative_path, symbol = _node_parts(nodeid)
    repository_root = (REPO_ROOT if root is None else root).resolve(strict=True)
    source_path = (repository_root / relative_path).resolve()
    try:
        source_path.relative_to(repository_root)
    except ValueError as exc:
        raise PreflightError("frozen test path escapes repository root") from exc
    if not source_path.is_file():
        raise PreflightError(f"frozen test source is missing: {relative_path}")
    source = source_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(source_path))
    except SyntaxError as exc:
        raise PreflightError(f"cannot parse frozen test source: {relative_path}") from exc
    matches = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == symbol
    ]
    if len(matches) != 1:
        raise PreflightError(
            f"frozen node {nodeid!r} resolves to {len(matches)} top-level functions"
        )
    node = matches[0]
    segment = ast.get_source_segment(source, node)
    if segment is None or node.end_lineno is None:
        raise PreflightError(f"cannot recover AST source span for {nodeid!r}")
    return (
        relative_path,
        symbol,
        int(node.lineno),
        int(node.end_lineno),
        _sha256_text(segment),
    )


def _result_sha256(
    *, nodeid: str, stdout_sha256: str, stderr_sha256: str,
    returncode: int, passed: bool, gate_source_file_sha256: str,
    execution_source_root_sha256: str,
) -> str:
    return _sha256_text(canonical_json({
        "nodeid": nodeid,
        "gate_source_file_sha256": gate_source_file_sha256,
        "execution_source_root_sha256": execution_source_root_sha256,
        "stdout_sha256": stdout_sha256,
        "stderr_sha256": stderr_sha256,
        "returncode": returncode,
        "passed": passed,
    }))


def _run_gate(
    gate: int,
    gate_name: str,
    nodeid: str,
    *,
    execution_snapshot: PrivateExecutionSnapshotV1,
) -> GateResultV1:
    before = execution_source_snapshot(execution_snapshot.root)
    if (before != execution_snapshot.files
            or execution_source_root_sha256(before)
            != execution_snapshot.root_sha256):
        raise PreflightError(f"gate {gate} private source drift before execution")
    source_path, symbol, start_line, end_line, span_sha = _ast_span(
        nodeid, root=execution_snapshot.root,
    )
    source_hashes = {item.path: item.sha256 for item in before}
    gate_source_file_sha256 = source_hashes[source_path]
    command = (*PYTEST_COMMAND_PREFIX, nodeid)
    environment = os.environ.copy()
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PYTHONHASHSEED"] = "0"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONPATH"] = str(execution_snapshot.root)
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONSTARTUP", None)
    started = time.perf_counter_ns()
    try:
        completed = subprocess.run(
            command,
            cwd=execution_snapshot.root,
            env=environment,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = int(completed.returncode)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr += "\nPRECHECK_TIMEOUT"
        returncode = 124
    after = execution_source_snapshot(execution_snapshot.root)
    if (after != before
            or execution_source_root_sha256(after)
            != execution_snapshot.root_sha256):
        raise PreflightError(f"gate {gate} private source drift during execution")
    duration_ms = max(0, (time.perf_counter_ns() - started) // 1_000_000)
    stdout_sha = _sha256_text(stdout)
    stderr_sha = _sha256_text(stderr)
    passed = returncode == 0
    return GateResultV1(
        gate=gate,
        gate_name=gate_name,
        nodeid=nodeid,
        source_path=source_path,
        source_symbol=symbol,
        source_start_line=start_line,
        source_end_line=end_line,
        ast_span_sha256=span_sha,
        gate_source_file_sha256=gate_source_file_sha256,
        execution_source_root_sha256=execution_snapshot.root_sha256,
        command=command,
        stdout=stdout,
        stdout_sha256=stdout_sha,
        stderr=stderr,
        stderr_sha256=stderr_sha,
        returncode=returncode,
        result_sha256=_result_sha256(
            nodeid=nodeid,
            stdout_sha256=stdout_sha,
            stderr_sha256=stderr_sha,
            returncode=returncode,
            passed=passed,
            gate_source_file_sha256=gate_source_file_sha256,
            execution_source_root_sha256=execution_snapshot.root_sha256,
        ),
        passed=passed,
        duration_ms=int(duration_ms),
    )


def _receipt_payload(
    gates: Sequence[GateResultV1],
    implementation_modules: Sequence[ImplementationModuleV1],
    gate_source_files: Sequence[GateSourceFileV1],
    execution_source_files: Sequence[ExecutionSourceFileV1],
) -> dict[str, Any]:
    gate_tuple = tuple(gates)
    module_tuple = tuple(implementation_modules)
    gate_source_tuple = tuple(gate_source_files)
    execution_source_tuple = tuple(execution_source_files)
    gate_source_root = _require_frozen_gate_source_root(gate_source_tuple)
    execution_root = execution_source_root_sha256(execution_source_tuple)
    execution_hashes = {
        item.path: item.sha256 for item in execution_source_tuple
    }
    for item in (*module_tuple, *gate_source_tuple):
        if execution_hashes.get(item.path) != item.sha256:
            raise PreflightError(
                f"execution source does not bind receipt file: {item.path}"
            )
    if len(gate_tuple) != len(GATE_NODEIDS):
        raise PreflightError("gate result count does not match frozen mapping")
    for result, expected in zip(gate_tuple, GATE_NODEIDS, strict=True):
        source_path, _symbol = _node_parts(expected[2])
        if (result.gate, result.gate_name, result.nodeid) != expected:
            raise PreflightError(
                f"gate {expected[0]} does not match frozen node mapping"
            )
        if result.gate_source_file_sha256 != execution_hashes[source_path]:
            raise PreflightError(
                f"gate {expected[0]} source file does not match execution snapshot"
            )
        if result.execution_source_root_sha256 != execution_root:
            raise PreflightError(
                f"gate {expected[0]} execution source root mismatch"
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "cwd": str(REPO_ROOT),
        "pytest_disable_plugin_autoload": "1",
        "python_executable": sys.executable,
        "gate_mapping_sha256": gate_mapping_sha256(),
        "implementation_modules": module_tuple,
        "implementation_code_root_sha256": implementation_code_root_sha256(
            module_tuple,
        ),
        "gate_source_files": gate_source_tuple,
        "gate_source_code_root_sha256": gate_source_root,
        "execution_source_files": execution_source_tuple,
        "execution_source_root_sha256": execution_root,
        "gate_count": len(gate_tuple),
        "all_passed": all(item.passed for item in gate_tuple),
        "gates": gate_tuple,
    }


def _seal_receipt(
    gates: Sequence[GateResultV1],
    implementation_modules: Sequence[ImplementationModuleV1],
    gate_source_files: Sequence[GateSourceFileV1],
    execution_source_files: Sequence[ExecutionSourceFileV1],
) -> PreflightReceiptV1:
    payload = _receipt_payload(
        gates, implementation_modules, gate_source_files,
        execution_source_files,
    )
    receipt_sha = _sha256_text(canonical_json(payload))
    receipt_id = content_id("h3_b3_preflight_receipt", {
        "receipt_sha256": receipt_sha,
        "gate_mapping_sha256": payload["gate_mapping_sha256"],
        "implementation_code_root_sha256": payload[
            "implementation_code_root_sha256"
        ],
        "gate_source_code_root_sha256": payload[
            "gate_source_code_root_sha256"
        ],
        "execution_source_root_sha256": payload[
            "execution_source_root_sha256"
        ],
    })
    return PreflightReceiptV1(
        schema_version=SCHEMA_VERSION,
        receipt_id=receipt_id,
        receipt_sha256=receipt_sha,
        cwd=payload["cwd"],
        pytest_disable_plugin_autoload=payload["pytest_disable_plugin_autoload"],
        python_executable=payload["python_executable"],
        gate_mapping_sha256=payload["gate_mapping_sha256"],
        implementation_modules=payload["implementation_modules"],
        implementation_code_root_sha256=payload[
            "implementation_code_root_sha256"
        ],
        gate_source_files=payload["gate_source_files"],
        gate_source_code_root_sha256=payload[
            "gate_source_code_root_sha256"
        ],
        execution_source_files=payload["execution_source_files"],
        execution_source_root_sha256=payload[
            "execution_source_root_sha256"
        ],
        gate_count=payload["gate_count"],
        all_passed=payload["all_passed"],
        gates=tuple(gates),
    )


def _write_first(path: Path, receipt: PreflightReceiptV1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (canonical_json(receipt) + "\n").encode("utf-8")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise PreflightError(f"preflight receipt already exists: {path}") from exc
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def run_preflight(output_path: str | Path) -> PreflightReceiptV1:
    """Execute exactly nine frozen nodes and first-write their sealed receipt."""

    output = Path(output_path)
    if output.exists():
        raise PreflightError(f"preflight receipt already exists: {output}")
    implementation_before = implementation_snapshot()
    gate_sources_before = gate_source_snapshot()
    _require_frozen_gate_source_root(gate_sources_before)
    execution_sources_before = execution_source_snapshot()
    with private_execution_snapshot(execution_sources_before) as snapshot:
        gates = tuple(
            _run_gate(*mapping, execution_snapshot=snapshot)
            for mapping in GATE_NODEIDS
        )
        if execution_source_snapshot(snapshot.root) != snapshot.files:
            raise PreflightError("private execution source changed across gates")
    implementation_after = implementation_snapshot()
    gate_sources_after = gate_source_snapshot()
    execution_sources_after = execution_source_snapshot()
    if implementation_after != implementation_before:
        raise PreflightError("implementation code changed while gates were running")
    if gate_sources_after != gate_sources_before:
        raise PreflightError("gate source code changed while gates were running")
    if execution_sources_after != execution_sources_before:
        raise PreflightError("execution source changed while gates were running")
    receipt = _seal_receipt(
        gates, implementation_before, gate_sources_before,
        execution_sources_before,
    )
    _write_first(output, receipt)
    return receipt


def _gate_from_dict(value: Any) -> GateResultV1:
    if not isinstance(value, dict):
        raise PreflightError("gate result must be an object")
    expected = {field.name for field in fields(GateResultV1)}
    if set(value) != expected:
        raise PreflightError("gate result keys do not match the current schema")
    try:
        return GateResultV1(
            gate=value["gate"],
            gate_name=value["gate_name"],
            nodeid=value["nodeid"],
            source_path=value["source_path"],
            source_symbol=value["source_symbol"],
            source_start_line=value["source_start_line"],
            source_end_line=value["source_end_line"],
            ast_span_sha256=value["ast_span_sha256"],
            gate_source_file_sha256=value["gate_source_file_sha256"],
            execution_source_root_sha256=value[
                "execution_source_root_sha256"
            ],
            command=tuple(value["command"]),
            stdout=value["stdout"],
            stdout_sha256=value["stdout_sha256"],
            stderr=value["stderr"],
            stderr_sha256=value["stderr_sha256"],
            returncode=value["returncode"],
            result_sha256=value["result_sha256"],
            passed=value["passed"],
            duration_ms=value["duration_ms"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PreflightError(f"invalid gate result: {exc}") from exc


def _module_from_dict(value: Any) -> ImplementationModuleV1:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise PreflightError("implementation module entry keys mismatch")
    path = value.get("path")
    digest = value.get("sha256")
    if (not isinstance(path, str) or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)):
        raise PreflightError("implementation module entry is invalid")
    return ImplementationModuleV1(path=path, sha256=digest)


def _gate_source_from_dict(value: Any) -> GateSourceFileV1:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise PreflightError("gate source file entry keys mismatch")
    path = value.get("path")
    digest = value.get("sha256")
    if (not isinstance(path, str) or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)):
        raise PreflightError("gate source file entry is invalid")
    return GateSourceFileV1(path=path, sha256=digest)


def _execution_source_from_dict(value: Any) -> ExecutionSourceFileV1:
    if not isinstance(value, dict) or set(value) != {"path", "sha256"}:
        raise PreflightError("execution source file entry keys mismatch")
    path = value.get("path")
    digest = value.get("sha256")
    if (not isinstance(path, str) or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)):
        raise PreflightError("execution source file entry is invalid")
    return ExecutionSourceFileV1(path=path, sha256=digest)


def _validate_gate(
    result: GateResultV1,
    expected: tuple[int, str, str],
    *,
    gate_source_files: Sequence[GateSourceFileV1],
    execution_source_root: str,
) -> None:
    gate, gate_name, nodeid = expected
    if (result.gate, result.gate_name, result.nodeid) != expected:
        raise PreflightError(f"gate {gate} does not match frozen node mapping")
    source_path, symbol, start_line, end_line, span_sha = _ast_span(nodeid)
    if (
        result.source_path != source_path
        or result.source_symbol != symbol
        or result.source_start_line != start_line
        or result.source_end_line != end_line
        or result.ast_span_sha256 != span_sha
    ):
        raise PreflightError(f"gate {gate} source AST span mismatch")
    gate_source_hashes = {item.path: item.sha256 for item in gate_source_files}
    if result.gate_source_file_sha256 != gate_source_hashes[source_path]:
        raise PreflightError(f"gate {gate} source file hash mismatch")
    if result.execution_source_root_sha256 != execution_source_root:
        raise PreflightError(f"gate {gate} execution source root mismatch")
    if result.command != (*PYTEST_COMMAND_PREFIX, nodeid):
        raise PreflightError(f"gate {gate} command is not frozen")
    if not isinstance(result.duration_ms, int) or result.duration_ms < 0:
        raise PreflightError(f"gate {gate} duration is invalid")
    if result.stdout_sha256 != _sha256_text(result.stdout):
        raise PreflightError(f"gate {gate} stdout hash mismatch")
    if result.stderr_sha256 != _sha256_text(result.stderr):
        raise PreflightError(f"gate {gate} stderr hash mismatch")
    expected_result_sha = _result_sha256(
        nodeid=nodeid,
        stdout_sha256=result.stdout_sha256,
        stderr_sha256=result.stderr_sha256,
        returncode=result.returncode,
        passed=result.passed,
        gate_source_file_sha256=result.gate_source_file_sha256,
        execution_source_root_sha256=result.execution_source_root_sha256,
    )
    if result.result_sha256 != expected_result_sha:
        raise PreflightError(f"gate {gate} result hash mismatch")
    if result.returncode != 0 or result.passed is not True:
        raise PreflightError(f"gate {gate} did not pass")


def load_preflight_receipt(path: str | Path) -> PreflightReceiptV1:
    """Load only an exact nine-gate, all-pass, self-hash-valid receipt."""

    source = Path(path)
    raw = source.read_text(encoding="utf-8")
    if not raw.endswith("\n") or raw.count("\n") != 1:
        raise PreflightError("preflight receipt must be one canonical JSON line")
    try:
        value = json.loads(raw[:-1], object_pairs_hook=_strict_object)
    except (_DuplicateJSONKey, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise PreflightError("preflight receipt is invalid JSON") from exc
    if canonical_json(value) + "\n" != raw:
        raise PreflightError("preflight receipt is not canonical JSON")
    expected_keys = {field.name for field in fields(PreflightReceiptV1)}
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise PreflightError("preflight receipt keys do not match v4")
    try:
        gates = tuple(_gate_from_dict(item) for item in value["gates"])
        receipt = PreflightReceiptV1(
            schema_version=value["schema_version"],
            receipt_id=value["receipt_id"],
            receipt_sha256=value["receipt_sha256"],
            cwd=value["cwd"],
            pytest_disable_plugin_autoload=value["pytest_disable_plugin_autoload"],
            python_executable=value["python_executable"],
            gate_mapping_sha256=value["gate_mapping_sha256"],
            implementation_modules=tuple(
                _module_from_dict(item) for item in value["implementation_modules"]
            ),
            implementation_code_root_sha256=value[
                "implementation_code_root_sha256"
            ],
            gate_source_files=tuple(
                _gate_source_from_dict(item) for item in value["gate_source_files"]
            ),
            gate_source_code_root_sha256=value[
                "gate_source_code_root_sha256"
            ],
            execution_source_files=tuple(
                _execution_source_from_dict(item)
                for item in value["execution_source_files"]
            ),
            execution_source_root_sha256=value[
                "execution_source_root_sha256"
            ],
            gate_count=value["gate_count"],
            all_passed=value["all_passed"],
            gates=gates,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PreflightError(f"invalid preflight receipt: {exc}") from exc
    if (
        receipt.schema_version != SCHEMA_VERSION
        or receipt.cwd != str(REPO_ROOT)
        or receipt.pytest_disable_plugin_autoload != "1"
        or receipt.python_executable != sys.executable
        or receipt.gate_mapping_sha256 != gate_mapping_sha256()
        or tuple(item.path for item in receipt.implementation_modules)
        != FROZEN_IMPLEMENTATION_MODULE_PATHS
        or receipt.implementation_code_root_sha256
        != implementation_code_root_sha256(receipt.implementation_modules)
        or tuple(item.path for item in receipt.gate_source_files)
        != FROZEN_GATE_SOURCE_PATHS
        or receipt.gate_source_code_root_sha256
        != gate_source_code_root_sha256(receipt.gate_source_files)
        or receipt.gate_source_code_root_sha256
        != FROZEN_GATE_SOURCE_CODE_ROOT_SHA256
        or tuple(item.path for item in receipt.execution_source_files)
        != FROZEN_EXECUTION_SOURCE_PATHS
        or receipt.execution_source_root_sha256
        != execution_source_root_sha256(receipt.execution_source_files)
        or receipt.gate_count != 9
        or len(receipt.gates) != 9
        or receipt.all_passed is not True
    ):
        raise PreflightError("preflight root policy mismatch")
    current_implementation = implementation_snapshot()
    if receipt.implementation_modules != current_implementation:
        raise PreflightError("preflight implementation code drift")
    current_gate_sources = gate_source_snapshot()
    if receipt.gate_source_files != current_gate_sources:
        raise PreflightError("preflight gate source code drift")
    current_execution_sources = execution_source_snapshot()
    if receipt.execution_source_files != current_execution_sources:
        raise PreflightError("preflight execution source drift")
    for result, expected in zip(receipt.gates, GATE_NODEIDS, strict=True):
        _validate_gate(
            result,
            expected,
            gate_source_files=receipt.gate_source_files,
            execution_source_root=receipt.execution_source_root_sha256,
        )
    payload = _receipt_payload(
        receipt.gates,
        receipt.implementation_modules,
        receipt.gate_source_files,
        receipt.execution_source_files,
    )
    receipt_sha = _sha256_text(canonical_json(payload))
    expected_id = content_id("h3_b3_preflight_receipt", {
        "receipt_sha256": receipt_sha,
        "gate_mapping_sha256": gate_mapping_sha256(),
        "implementation_code_root_sha256": (
            receipt.implementation_code_root_sha256
        ),
        "gate_source_code_root_sha256": receipt.gate_source_code_root_sha256,
        "execution_source_root_sha256": receipt.execution_source_root_sha256,
    })
    if receipt.receipt_sha256 != receipt_sha or receipt.receipt_id != expected_id:
        raise PreflightError("preflight receipt self hash mismatch")
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    receipt = run_preflight(args.output)
    print(canonical_json({
        "receipt_id": receipt.receipt_id,
        "receipt_sha256": receipt.receipt_sha256,
        "all_passed": receipt.all_passed,
        "gate_count": receipt.gate_count,
        "output": str(args.output),
    }))
    return 0 if receipt.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
