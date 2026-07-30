"""Verify the F1 r8 v3 incident producer from immutable Git blobs."""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    REPO_ROOT
    / "LONGINUS_HSWM_F1_ABORTED_EXPOSURE_V3_BINDING_2026-07-30.json"
)
SCHEMA = "longinus-hswm-f1-r8-aborted-exposure-v3-binding/v12"
EXPECTED_BINDING_ID = "longinus-hswm-f1-r8-aborted-exposure-v3-v12-20260730"
EXPECTED_PRODUCER_COMMIT = "5de77e9a0701139b1875ed017b691c8ea9e11650"
EXPECTED_PRODUCER_PARENT = "5dc6b7f3e46bf563fd31ebafa164eb269fa9f798"
EXPECTED_PRODUCER_TREE = "84dccad8c542466a8dd46ab4e60d1b3ea7e98fe2"
EXPECTED_ARTIFACT_COMMIT = "21a1b0da9f462a57746d7a6d170616f47ded329c"
EXPECTED_ARTIFACT_PARENT = EXPECTED_PRODUCER_COMMIT
EXPECTED_BINDING_SOURCE_COMMIT = EXPECTED_ARTIFACT_COMMIT
EXPECTED_RECEIPT_PATH = "receipts/hswm_f1_r8_v8_aborted_exposure.v3.json"
EXPECTED_RECEIPT_SCHEMA = "hswm-prom9-f1-aborted-attempt-exposure/v3"
EXPECTED_RECEIPT_RAW_SHA256 = (
    "8e87c09c90651d56cd2cc7e246488fec2f34c664ed5be2e8a72d93b4f2af5d88"
)
EXPECTED_RECEIPT_SELF_SHA256 = (
    "0b59515be42ad3f86c03a6c7a0664be3e275ea6a349267653608c238b12b12d8"
)
EXPECTED_RECEIPT_BLOB_OID = "bd3a9a480ac0a82a995edde0c40d89af505e14cb"
EXPECTED_PRODUCER_ROOT = (
    "be67419b266f8c5ef8bec701fd91457ad188595467e78e14ce50a4ea16392842"
)
EXPECTED_PRODUCER_FILES = 20
EXPECTED_BASELINE_SCOPE = (
    "HSWM F1 r8 v8 aborted-attempt public v3 receipt, exact current producer "
    "AST closure, historical-v8 SQLite schema gate, and zero-successor-call "
    "quarantine boundary"
)
EXPECTED_GENERATED_AT = "2026-07-30T08:55:00+09:00"
EXPECTED_BLOB_AUTHORITY = (
    "Receipt bytes and all producer/binding target bytes are read with git "
    "cat-file from exact immutable commits; receipt and producer object "
    "identities are independently checked with ls-tree; worktree source is "
    "never read."
)
EXPECTED_ANCESTRY_RULE = (
    "The producer commit is the exact parent of the one-path artifact "
    "publication commit, and the artifact commit must be an ancestor of HEAD."
)
EXPECTED_PRODUCER_PATHS = (
    "bge_m3_embed.py",
    "hswm_next_research_harness.py",
    "model_deployment_receipt.py",
    "prom_search_hswm/hswm_call_receipt.py",
    "prom_search_hswm/hswm_f1_durable_transport.py",
    "prom_search_hswm/hswm_f1_sqlite_schema.py",
    "prom_search_hswm/hswm_function_network.py",
    "prom_search_hswm/hswm_function_registry.py",
    "prom_search_hswm/hswm_result_spool.py",
    "prom_search_hswm/hswm_token_meter.py",
    "prom_search_hswm/hswm_typed_ports.py",
    "prom_search_hswm/prom9_f1_envelope.py",
    "prom_search_hswm/prom9_f1_prior_exposure.py",
    "prom_search_hswm/prom9_f1_r8_environment.py",
    "prom_search_hswm/prom9_f1_r8_private_output.py",
    "prom_search_hswm/prom9_f1_r8_source.py",
    "prom_search_hswm/prom9_f1_r8_transport_audit.py",
    "prom_search_hswm/prom9_prepare_2wiki_f1.py",
    "prom_search_hswm/prom9_protocol.py",
    "prom_search_hswm/prom_f1_function_network.py",
)
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
EXPECTED_TARGET_PATHS = (
    "prom_search_hswm/prom9_f1_prior_exposure.py",
    "prom_search_hswm/hswm_f1_sqlite_schema.py",
    "prom_search_hswm/test_prom9_f1_prior_exposure.py",
    "prom_search_hswm/test_hswm_f1_sqlite_schema.py",
    EXPECTED_RECEIPT_PATH,
)
EXPECTED_SYMBOLS = {
    EXPECTED_TARGET_PATHS[0]: "build_aborted_attempt_exposure_receipt",
    EXPECTED_TARGET_PATHS[1]: "exact_schema_readback",
    EXPECTED_TARGET_PATHS[2]: (
        "test_aborted_attempt_public_identity_and_producer_inventory_are_closed"
    ),
    EXPECTED_TARGET_PATHS[3]: (
        "test_historical_v8_spool_schema_is_a_separate_exact_authority"
    ),
    EXPECTED_RECEIPT_PATH: EXPECTED_RECEIPT_SCHEMA,
}
EXPECTED_CONTRACTS = {
    EXPECTED_TARGET_PATHS[0]: "R8_V3_INCIDENT_PRODUCER__UNJUDGED",
    EXPECTED_TARGET_PATHS[1]: "R8_HISTORICAL_V8_SCHEMA_GATE__UNJUDGED",
    EXPECTED_TARGET_PATHS[2]: "R8_V3_INCIDENT_PRODUCER_TEST__ENGINEERING_ONLY",
    EXPECTED_TARGET_PATHS[3]: "R8_HISTORICAL_V8_SCHEMA_TEST__ENGINEERING_ONLY",
    EXPECTED_RECEIPT_PATH: "R8_ABORTED_EXPOSURE_V3_ARTIFACT__QUARANTINED",
}
EXPECTED_KG_NODES = {
    EXPECTED_TARGET_PATHS[0]: "LOCAL_PROPOSED_HSWM_F1_R8_V3_INCIDENT_PRODUCER",
    EXPECTED_TARGET_PATHS[1]: (
        "LOCAL_PROPOSED_HSWM_F1_R8_HISTORICAL_V8_SCHEMA_GATE"
    ),
    EXPECTED_TARGET_PATHS[2]: (
        "LOCAL_PROPOSED_HSWM_F1_R8_V3_INCIDENT_PRODUCER_TEST"
    ),
    EXPECTED_TARGET_PATHS[3]: (
        "LOCAL_PROPOSED_HSWM_F1_R8_HISTORICAL_V8_SCHEMA_TEST"
    ),
    EXPECTED_RECEIPT_PATH: (
        "LOCAL_PROPOSED_HSWM_F1_R8_ABORTED_EXPOSURE_V3_RECEIPT"
    ),
}
EXPECTED_CRATES = {
    EXPECTED_TARGET_PATHS[0]: (
        "python -m pytest -q prom_search_hswm/test_prom9_f1_prior_exposure.py"
    ),
    EXPECTED_TARGET_PATHS[1]: (
        "python -m pytest -q prom_search_hswm/test_hswm_f1_sqlite_schema.py"
    ),
    EXPECTED_TARGET_PATHS[2]: (
        "python -m pytest -q prom_search_hswm/test_prom9_f1_prior_exposure.py"
    ),
    EXPECTED_TARGET_PATHS[3]: (
        "python -m pytest -q prom_search_hswm/test_hswm_f1_sqlite_schema.py"
    ),
    EXPECTED_RECEIPT_PATH: (
        "python -m pytest -q prom_search_hswm/test_prom9_f1_prior_exposure.py"
    ),
}
TOP_LEVEL_KEYS = {
    "schema",
    "binding_id",
    "binding_state",
    "generated_at",
    "baseline_scope",
    "scientific_status",
    "evidence_class",
    "r7_status",
    "b22_gate",
    "model_calls",
    "incident_boundary",
    "git",
    "receipt_binding",
    "producer_authority",
    "required_target_paths",
    "bindings",
    "kg",
    "layers",
    "crate_script",
}
PRODUCER_FIELDS = {
    "commit",
    "tree",
    "entrypoint",
    "closure_policy",
    "files",
    "file_count",
    "closure_root_sha256",
}
PRODUCER_FILE_FIELDS = {
    "relative_path",
    "size_bytes",
    "sha256",
    "blob_mode",
    "blob_oid",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OBJECT_RE = re.compile(r"^[0-9a-f]{40}$")
LINE_RANGE_RE = re.compile(r"^([1-9][0-9]*)-([1-9][0-9]*)$")


class BindingError(ValueError):
    """A classified Longinus v12 binding failure."""

    def __init__(self, classification: str, message: str) -> None:
        self.classification = classification
        super().__init__(f"{classification}: {message}")


def _fail(classification: str, message: str) -> None:
    raise BindingError(classification, message)


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in items:
        if key in value:
            _fail("LABEL_ROT", f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _constant(value: str) -> object:
    _fail("LABEL_ROT", f"non-finite JSON value: {value}")


def _json_bytes(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except BindingError:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        _fail("SIGNATURE_MISMATCHED", f"cannot parse {label}: {error}")
    if not isinstance(value, dict):
        _fail("SIGNATURE_MISMATCHED", f"{label} must be one JSON object")
    return value


def _load(path: Path) -> dict[str, object]:
    try:
        return _json_bytes(path.read_bytes(), "Longinus manifest")
    except OSError as error:
        _fail("MISSING", f"cannot read Longinus manifest: {error}")


def _canonical_sha256(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    result = [item.arg for item in (*node.args.posonlyargs, *node.args.args)]
    if node.args.vararg is not None:
        result.append(f"*{node.args.vararg.arg}")
    result.extend(item.arg for item in node.args.kwonlyargs)
    if node.args.kwarg is not None:
        result.append(f"**{node.args.kwarg.arg}")
    return result


def _source_segment(source: str, node: ast.AST, *, label: str) -> str:
    segment = ast.get_source_segment(source, node)
    if not isinstance(segment, str) or not segment:
        _fail("SIGNATURE_MISMATCHED", f"cannot recover {label} source")
    return segment


def _argument_descriptor(
    source: str, argument: ast.arg, *, default: ast.expr | None = None
) -> dict[str, object]:
    return {
        "name": argument.arg,
        "annotation": (
            None
            if argument.annotation is None
            else _source_segment(source, argument.annotation, label="annotation")
        ),
        "type_comment": getattr(argument, "type_comment", None),
        "default": (
            None
            if default is None
            else _source_segment(source, default, label="default")
        ),
    }


def _signature_descriptor(
    source: str, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
) -> dict[str, object]:
    type_params = [
        _source_segment(source, item, label="type parameter")
        for item in getattr(node, "type_params", ())
    ]
    decorators = [
        _source_segment(source, item, label="decorator")
        for item in node.decorator_list
    ]
    if isinstance(node, ast.ClassDef):
        return {
            "kind": "class",
            "bases": [
                _source_segment(source, item, label="class base")
                for item in node.bases
            ],
            "keywords": [
                {
                    "name": item.arg,
                    "value": _source_segment(
                        source, item.value, label="class keyword"
                    ),
                }
                for item in node.keywords
            ],
            "decorators": decorators,
            "type_params": type_params,
        }

    positional = [*node.args.posonlyargs, *node.args.args]
    positional_defaults: list[ast.expr | None] = [None] * (
        len(positional) - len(node.args.defaults)
    ) + list(node.args.defaults)
    posonly_count = len(node.args.posonlyargs)
    positional_descriptors = [
        _argument_descriptor(source, item, default=default)
        for item, default in zip(positional, positional_defaults)
    ]
    return {
        "kind": (
            "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
        ),
        "positional_only": positional_descriptors[:posonly_count],
        "positional_or_keyword": positional_descriptors[posonly_count:],
        "vararg": (
            None
            if node.args.vararg is None
            else _argument_descriptor(source, node.args.vararg)
        ),
        "keyword_only": [
            _argument_descriptor(source, item, default=default)
            for item, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
        ],
        "kwarg": (
            None
            if node.args.kwarg is None
            else _argument_descriptor(source, node.args.kwarg)
        ),
        "returns": (
            None
            if node.returns is None
            else _source_segment(source, node.returns, label="return annotation")
        ),
        "type_comment": node.type_comment,
        "decorators": decorators,
        "type_params": type_params,
    }


def _signature_sha256(
    source: str, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
) -> str:
    return _canonical_sha256(_signature_descriptor(source, node))


def _definition_start(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    return min(
        [int(node.lineno), *(int(item.lineno) for item in node.decorator_list)]
    )


def _symbol_range(
    blob: bytes, relative: str, expected: Mapping[str, object]
) -> tuple[int, int]:
    name = expected.get("name")
    kind = expected.get("kind")
    parameters = expected.get("parameters")
    if not isinstance(parameters, list) or not all(
        isinstance(item, str) for item in parameters
    ):
        _fail("LABEL_ROT", f"invalid parameter labels for {relative}:{name}")
    if kind == "json_receipt":
        if set(expected) != {"qualified", "name", "kind", "parameters"}:
            _fail("LABEL_ROT", "JSON receipt symbol shape drifted")
        if parameters or name != EXPECTED_RECEIPT_SCHEMA:
            _fail("LABEL_ROT", "JSON receipt symbol label drifted")
        if expected.get("qualified") != f"{relative}#schema_version":
            _fail("LABEL_ROT", "qualified JSON receipt symbol drifted")
        receipt = _json_bytes(blob, "bound v3 exposure receipt")
        declared = receipt.get("aborted_attempt_exposure_receipt_sha256")
        unsigned = dict(receipt)
        unsigned.pop("aborted_attempt_exposure_receipt_sha256", None)
        if (
            receipt.get("schema_version") != EXPECTED_RECEIPT_SCHEMA
            or declared != EXPECTED_RECEIPT_SELF_SHA256
            or _canonical_sha256(unsigned) != EXPECTED_RECEIPT_SELF_SHA256
        ):
            _fail("DIVERGENT", "bound JSON receipt self-identity drifted")
        try:
            lines = blob.decode("utf-8").splitlines()
        except UnicodeError as error:
            _fail("SIGNATURE_MISMATCHED", f"cannot decode {relative}: {error}")
        schema_lines = [
            index
            for index, line in enumerate(lines, start=1)
            if line == f'  "schema_version": "{EXPECTED_RECEIPT_SCHEMA}",'
        ]
        if schema_lines != [584]:
            _fail("SIGNATURE_MISMATCHED", "v3 receipt schema line drifted")
        return 584, 584

    if set(expected) != {
        "qualified", "name", "kind", "parameters", "signature_sha256"
    }:
        _fail("LABEL_ROT", f"Python symbol shape drifted for {relative}")
    try:
        source = blob.decode("utf-8")
        tree = ast.parse(source, filename=relative)
    except (UnicodeError, SyntaxError) as error:
        _fail("SIGNATURE_MISMATCHED", f"cannot parse {relative}: {error}")
    if not isinstance(name, str) or kind not in {"class", "function"}:
        _fail("LABEL_ROT", f"invalid code symbol label for {relative}")
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        _fail("ORPHANED", f"top-level symbol {name!r} occurs {len(matches)} times")
    node = matches[0]
    actual_kind = "class" if isinstance(node, ast.ClassDef) else "function"
    if actual_kind != kind:
        _fail("SIGNATURE_MISMATCHED", f"symbol kind drifted for {relative}:{name}")
    actual_parameters = [] if isinstance(node, ast.ClassDef) else _parameters(node)
    if actual_parameters != parameters:
        _fail("SIGNATURE_MISMATCHED", f"symbol parameters drifted for {relative}:{name}")
    signature = expected.get("signature_sha256")
    if (
        not isinstance(signature, str)
        or SHA256_RE.fullmatch(signature) is None
        or _signature_sha256(source, node) != signature
    ):
        _fail("SIGNATURE_MISMATCHED", f"symbol signature drifted for {relative}:{name}")
    module = relative[:-3].replace("/", ".")
    if expected.get("qualified") != f"{module}.{name}":
        _fail("LABEL_ROT", f"qualified symbol drifted for {relative}:{name}")
    end = getattr(node, "end_lineno", None)
    if not isinstance(end, int):
        _fail("SIGNATURE_MISMATCHED", f"symbol end line absent for {relative}:{name}")
    return _definition_start(node), end


def _git(
    arguments: Sequence[str], *, label: str, classification: str = "MISSING"
) -> bytes:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    environment["GIT_LITERAL_PATHSPECS"] = "1"
    completed = subprocess.run(
        ["git", "--no-replace-objects", *arguments],
        cwd=REPO_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        _fail(classification, f"{label}: {detail or 'git command failed'}")
    return completed.stdout


def _safe_path(relative: str) -> None:
    candidate = Path(relative)
    if not relative or candidate.is_absolute() or ".." in candidate.parts:
        _fail("ORPHANED", f"unsafe producer path: {relative!r}")


def _commit_blob(commit: str, relative: str) -> bytes:
    _safe_path(relative)
    kind = _git(
        ["cat-file", "-t", f"{commit}:{relative}"],
        label=f"missing Git object {relative}",
    ).decode("ascii", "strict").strip()
    if kind != "blob":
        _fail("MISSING", f"producer path is not a blob: {relative}")
    return _git(
        ["cat-file", "-p", f"{commit}:{relative}"],
        label=f"cannot read {relative}",
    )


def _single_parent(commit: str) -> str:
    fields = _git(
        ["rev-list", "--parents", "-n", "1", commit],
        label=f"cannot resolve parent of {commit}",
        classification="DIVERGENT",
    ).decode("ascii", "strict").split()
    if len(fields) != 2 or fields[0] != commit:
        _fail("DIVERGENT", f"commit is not single-parent: {commit}")
    return fields[1]


def _changed_paths(left: str, right: str) -> set[str]:
    return {
        item
        for item in _git(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", left, right],
            label="cannot derive artifact diff",
            classification="DIVERGENT",
        ).decode("utf-8", "strict").splitlines()
        if item
    }


def _strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def verify(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, object]:
    manifest = _load(manifest_path)
    if set(manifest) != TOP_LEVEL_KEYS:
        _fail("LABEL_ROT", "manifest top-level shape drifted")
    if manifest.get("schema") != SCHEMA:
        _fail("LABEL_ROT", f"schema must be {SCHEMA}")
    if manifest.get("binding_id") != EXPECTED_BINDING_ID:
        _fail("LABEL_ROT", "binding identity drifted")
    inadmissible = "EXPLORATORY_ENGINEERING_ONLY__PREREGISTRATION_INADMISSIBLE"
    if (
        manifest.get("binding_state") != "PIERCED_LOCAL_NO_KG_WRITE"
        or manifest.get("generated_at") != EXPECTED_GENERATED_AT
        or manifest.get("baseline_scope") != EXPECTED_BASELINE_SCOPE
        or manifest.get("scientific_status") != "UNJUDGED"
        or manifest.get("evidence_class") != inadmissible
        or manifest.get("r7_status") != inadmissible
        or manifest.get("b22_gate") != "LOCKED"
        or type(manifest.get("model_calls")) is not int
        or manifest.get("model_calls") != 1
        or manifest.get("layers") != list(REQUIRED_LAYERS)
    ):
        _fail("LABEL_ROT", "scientific or seven-layer boundary drifted")

    git = manifest.get("git")
    if not isinstance(git, Mapping) or set(git) != {
        "remote", "branch", "producer_commit", "producer_parent",
        "artifact_commit", "artifact_parent", "binding_source_commit",
        "blob_authority", "ancestry_rule",
    }:
        _fail("LABEL_ROT", "Git authority shape drifted")
    if (
        git.get("remote") != "https://github.com/gj3447/HSWM.git"
        or git.get("branch") != "main"
        or git.get("producer_commit") != EXPECTED_PRODUCER_COMMIT
        or git.get("producer_parent") != EXPECTED_PRODUCER_PARENT
        or git.get("artifact_commit") != EXPECTED_ARTIFACT_COMMIT
        or git.get("artifact_parent") != EXPECTED_ARTIFACT_PARENT
        or git.get("binding_source_commit") != EXPECTED_BINDING_SOURCE_COMMIT
        or git.get("blob_authority") != EXPECTED_BLOB_AUTHORITY
        or git.get("ancestry_rule") != EXPECTED_ANCESTRY_RULE
    ):
        _fail("LABEL_ROT", "Git authority label drifted")
    if _single_parent(EXPECTED_PRODUCER_COMMIT) != EXPECTED_PRODUCER_PARENT:
        _fail("DIVERGENT", "producer parent drifted")
    if _single_parent(EXPECTED_ARTIFACT_COMMIT) != EXPECTED_ARTIFACT_PARENT:
        _fail("DIVERGENT", "artifact parent drifted")
    _git(
        ["merge-base", "--is-ancestor", EXPECTED_PRODUCER_COMMIT, EXPECTED_ARTIFACT_COMMIT],
        label="producer is not an ancestor of artifact",
        classification="DIVERGENT",
    )
    _git(
        ["merge-base", "--is-ancestor", EXPECTED_ARTIFACT_COMMIT, "HEAD"],
        label="artifact is not an ancestor of HEAD",
        classification="DIVERGENT",
    )
    if _changed_paths(EXPECTED_ARTIFACT_PARENT, EXPECTED_ARTIFACT_COMMIT) != {
        EXPECTED_RECEIPT_PATH
    }:
        _fail("DIVERGENT", "artifact commit is not the one-path receipt publication")

    receipt_binding = manifest.get("receipt_binding")
    expected_receipt_binding = {
        "path": EXPECTED_RECEIPT_PATH,
        "schema_version": EXPECTED_RECEIPT_SCHEMA,
        "schema_line": 584,
        "size_bytes": 998645,
        "raw_sha256": EXPECTED_RECEIPT_RAW_SHA256,
        "self_sha256": EXPECTED_RECEIPT_SELF_SHA256,
        "blob_mode": "100644",
        "blob_oid": EXPECTED_RECEIPT_BLOB_OID,
    }
    if receipt_binding != expected_receipt_binding:
        _fail("LABEL_ROT", "receipt binding drifted")
    receipt_raw = _commit_blob(EXPECTED_ARTIFACT_COMMIT, EXPECTED_RECEIPT_PATH)
    receipt_tree_row = _git(
        ["ls-tree", EXPECTED_ARTIFACT_COMMIT, "--", EXPECTED_RECEIPT_PATH],
        label="cannot read receipt tree row",
    ).decode("utf-8", "strict").strip()
    try:
        receipt_metadata, receipt_path = receipt_tree_row.split("\t", 1)
        receipt_mode, receipt_kind, receipt_oid = receipt_metadata.split()
    except ValueError:
        _fail("MISSING", "malformed receipt tree row")
    if (
        receipt_path != EXPECTED_RECEIPT_PATH
        or receipt_kind != "blob"
        or receipt_mode != expected_receipt_binding["blob_mode"]
        or receipt_oid != expected_receipt_binding["blob_oid"]
        or len(receipt_raw) != expected_receipt_binding["size_bytes"]
        or hashlib.sha256(receipt_raw).hexdigest() != EXPECTED_RECEIPT_RAW_SHA256
    ):
        _fail("DIVERGENT", "receipt Git blob bytes drifted")
    receipt = _json_bytes(receipt_raw, "v3 exposure receipt")
    unsigned = dict(receipt)
    declared = unsigned.pop("aborted_attempt_exposure_receipt_sha256", None)
    if (
        receipt.get("schema_version") != EXPECTED_RECEIPT_SCHEMA
        or declared != EXPECTED_RECEIPT_SELF_SHA256
        or _canonical_sha256(unsigned) != EXPECTED_RECEIPT_SELF_SHA256
    ):
        _fail("DIVERGENT", "receipt canonical self-binding drifted")

    forbidden = {
        "stage_path", "capture_host", "resolved_path", "source_identity",
        "nonce_hex", "st_dev", "st_ino",
    }
    public_strings = tuple(_strings(receipt))
    if forbidden.intersection(public_strings) or any(
        value.startswith("/") for value in public_strings
    ):
        _fail("DIVERGENT", "public receipt leaks private identity material")

    incident = manifest.get("incident_boundary")
    expected_counts = {
        "attempt_calls": 2,
        "attempt_events": 8,
        "attempt_states": {"ACCEPTED": 1, "SENT": 1},
        "components": 1,
        "item_runs": 0,
        "items": 1,
        "source_entities": 10,
        "spool_absent_calls": 1,
        "spool_calls": 1,
        "spool_complete_calls": 1,
    }
    expected_incident = {
        "aborted_attempt_exposure_receipt_sha256": EXPECTED_RECEIPT_SELF_SHA256,
        "counts": expected_counts,
        "historical_upstream_model_calls": 1,
        "prospective_successor_model_calls": 0,
        "confirmatory_upstream_model_calls": 0,
        "scientific_verdicts": 0,
    }
    if incident != expected_incident or receipt.get("counts") != expected_counts:
        _fail("LABEL_ROT", "quarantined incident boundary drifted")

    receipt_authority = receipt.get("evidence_bindings")
    receipt_authority = (
        receipt_authority.get("current_producer_authority")
        if isinstance(receipt_authority, Mapping)
        else None
    )
    manifest_authority = manifest.get("producer_authority")
    if (
        not isinstance(receipt_authority, Mapping)
        or not isinstance(manifest_authority, Mapping)
        or set(receipt_authority) != PRODUCER_FIELDS
        or set(manifest_authority) != PRODUCER_FIELDS
    ):
        _fail("LABEL_ROT", "producer authority shape drifted")
    for field, expected in (
        ("commit", EXPECTED_PRODUCER_COMMIT),
        ("tree", EXPECTED_PRODUCER_TREE),
        ("entrypoint", "prom_search_hswm/prom9_f1_prior_exposure.py"),
        ("closure_policy", "MODULE_SCOPE_LOCAL_AST_LFP_V1"),
        ("file_count", EXPECTED_PRODUCER_FILES),
        ("closure_root_sha256", EXPECTED_PRODUCER_ROOT),
    ):
        if receipt_authority.get(field) != expected or manifest_authority.get(field) != expected:
            _fail("LABEL_ROT", f"producer {field} drifted")
    receipt_files = receipt_authority.get("files")
    manifest_files = manifest_authority.get("files")
    if not isinstance(receipt_files, list) or not isinstance(manifest_files, list):
        _fail("ORPHANED", "producer file inventory is absent")
    if (
        len(receipt_files) != EXPECTED_PRODUCER_FILES
        or len(manifest_files) != EXPECTED_PRODUCER_FILES
    ):
        _fail("ORPHANED", "producer file count drifted")
    seen: set[str] = set()
    ordered_paths: list[str] = []
    for receipt_file, manifest_file in zip(receipt_files, manifest_files):
        if (
            not isinstance(receipt_file, Mapping)
            or not isinstance(manifest_file, Mapping)
            or set(receipt_file) != PRODUCER_FILE_FIELDS
            or set(manifest_file) != PRODUCER_FILE_FIELDS
        ):
            _fail("LABEL_ROT", "producer file row shape drifted")
        relative = manifest_file.get("relative_path")
        if not isinstance(relative, str):
            _fail("ORPHANED", "producer path is absent")
        _safe_path(relative)
        if relative in seen:
            _fail("ORPHANED", f"duplicate producer path: {relative}")
        seen.add(relative)
        ordered_paths.append(relative)
        if receipt_file.get("relative_path") != relative:
            _fail("ORPHANED", "producer path substitution drifted")
        for field in ("size_bytes", "sha256", "blob_mode", "blob_oid"):
            if receipt_file.get(field) != manifest_file.get(field):
                _fail("DIVERGENT", f"producer {field} differs from receipt")
        if (
            manifest_file.get("blob_mode") != "100644"
            or not isinstance(manifest_file.get("blob_oid"), str)
            or OBJECT_RE.fullmatch(str(manifest_file["blob_oid"])) is None
        ):
            _fail("LABEL_ROT", f"producer Git label is invalid: {relative}")
        blob = _commit_blob(EXPECTED_PRODUCER_COMMIT, relative)
        tree_row = _git(
            ["ls-tree", EXPECTED_PRODUCER_COMMIT, "--", relative],
            label=f"cannot read producer tree row {relative}",
        ).decode("utf-8", "strict").strip()
        try:
            metadata, observed_path = tree_row.split("\t", 1)
            mode, kind, oid = metadata.split()
        except ValueError:
            _fail("MISSING", f"malformed producer tree row: {relative}")
        if observed_path != relative or kind != "blob":
            _fail("MISSING", f"producer tree path drifted: {relative}")
        if mode != manifest_file.get("blob_mode") or oid != manifest_file.get("blob_oid"):
            _fail("DIVERGENT", f"producer Git identity drifted: {relative}")
        if (
            type(manifest_file.get("size_bytes")) is not int
            or int(manifest_file["size_bytes"]) < 1
            or len(blob) != manifest_file["size_bytes"]
            or not isinstance(manifest_file.get("sha256"), str)
            or SHA256_RE.fullmatch(str(manifest_file["sha256"])) is None
            or hashlib.sha256(blob).hexdigest() != manifest_file["sha256"]
        ):
            _fail("DIVERGENT", f"producer bytes drifted: {relative}")
    if len(receipt_files) != len(manifest_files) or receipt_files != manifest_files:
        _fail("ORPHANED", "producer ordered file inventory drifted")
    if tuple(ordered_paths) != EXPECTED_PRODUCER_PATHS:
        _fail("ORPHANED", "producer path inventory drifted")
    if _canonical_sha256(manifest_files) != EXPECTED_PRODUCER_ROOT:
        _fail("DIVERGENT", "producer closure root drifted")
    observed_tree = _git(
        ["rev-parse", f"{EXPECTED_PRODUCER_COMMIT}^{{tree}}"],
        label="cannot resolve producer tree",
        classification="DIVERGENT",
    ).decode("ascii", "strict").strip()
    if observed_tree != EXPECTED_PRODUCER_TREE:
        _fail("DIVERGENT", "producer tree object drifted")

    target_paths = manifest.get("required_target_paths")
    if (
        not isinstance(target_paths, list)
        or tuple(target_paths) != EXPECTED_TARGET_PATHS
        or len(target_paths) != len(set(target_paths))
    ):
        _fail("ORPHANED", "seven-layer target inventory drifted")
    bindings = manifest.get("bindings")
    if not isinstance(bindings, list) or len(bindings) != len(EXPECTED_TARGET_PATHS):
        _fail("ORPHANED", "seven-layer binding inventory drifted")
    bound_paths: list[str] = []
    bound_nodes: set[str] = set()
    contract_counts = {"implementation": 0, "test": 0, "artifact": 0}
    for index, binding in enumerate(bindings):
        if not isinstance(binding, Mapping) or set(binding) != REQUIRED_BINDING_KEYS:
            _fail("LABEL_ROT", f"binding {index} does not expose seven layers")
        file_line = binding.get("file_line")
        if not isinstance(file_line, str) or ":" not in file_line:
            _fail("MISSING", f"binding {index} file_line is absent")
        relative, line_text = file_line.rsplit(":", 1)
        expected_relative = EXPECTED_TARGET_PATHS[index]
        if relative != expected_relative:
            _fail("ORPHANED", f"binding {index} target path drifted")
        bound_paths.append(relative)
        kg_node = binding.get("kg_node")
        if kg_node != EXPECTED_KG_NODES[relative]:
            _fail("LABEL_ROT", f"local KG identity drifted for {relative}")
        if str(kg_node) in bound_nodes:
            _fail("ORPHANED", f"duplicate local KG identity: {kg_node}")
        bound_nodes.add(str(kg_node))
        contract = binding.get("contract_binding")
        if contract != EXPECTED_CONTRACTS[relative]:
            _fail("LABEL_ROT", f"contract binding drifted for {relative}")
        if str(contract).endswith("__UNJUDGED"):
            contract_counts["implementation"] += 1
        elif str(contract).endswith("__ENGINEERING_ONLY"):
            contract_counts["test"] += 1
        elif str(contract).endswith("__QUARANTINED"):
            contract_counts["artifact"] += 1
        else:
            _fail("LABEL_ROT", f"contract class drifted for {relative}")
        code_symbol = binding.get("code_symbol")
        if (
            not isinstance(code_symbol, Mapping)
            or code_symbol.get("name") != EXPECTED_SYMBOLS[relative]
        ):
            _fail("LABEL_ROT", f"code symbol identity drifted for {relative}")
        blob = _commit_blob(EXPECTED_BINDING_SOURCE_COMMIT, relative)
        expected_sha = binding.get("sha256")
        if (
            not isinstance(expected_sha, str)
            or SHA256_RE.fullmatch(expected_sha) is None
            or hashlib.sha256(blob).hexdigest() != expected_sha
        ):
            _fail("DIVERGENT", f"binding Git blob SHA drifted for {relative}")
        symbol_start, symbol_end = _symbol_range(blob, relative, code_symbol)
        range_match = LINE_RANGE_RE.fullmatch(str(binding.get("line_range")))
        if range_match is None:
            _fail("MISSING", f"line range is absent for {relative}")
        start, end = int(range_match.group(1)), int(range_match.group(2))
        if start != symbol_start or end != symbol_end or line_text != str(start):
            _fail("DIVERGENT", f"symbol/file line range drifted for {relative}")
        crate_script = binding.get("crate_script")
        if crate_script != EXPECTED_CRATES[relative]:
            _fail("LABEL_ROT", f"crate script drifted for {relative}")
        crate_path = str(crate_script).removeprefix("python -m pytest -q ")
        if not Path(crate_path).name.startswith("test_"):
            _fail("ORPHANED", f"crate target is not a test for {relative}")
        _commit_blob(EXPECTED_BINDING_SOURCE_COMMIT, crate_path)
    if tuple(bound_paths) != EXPECTED_TARGET_PATHS:
        _fail("ORPHANED", "seven-layer reverse scan is incomplete")
    if contract_counts != {"implementation": 2, "test": 2, "artifact": 1}:
        _fail("LABEL_ROT", "seven-layer contract cardinality drifted")

    kg = manifest.get("kg")
    expected_kg = {
        "write_state": "NOT_AUTHORIZED_NOT_WRITTEN",
        "anchor_status": "LOCAL_PROPOSED_REFERENCE_IDENTITY",
        "provenance_actor": "Codex",
        "source_path": DEFAULT_MANIFEST.name,
        "timestamp": EXPECTED_GENERATED_AT,
    }
    if kg != expected_kg:
        _fail("LABEL_ROT", "KG local-only boundary drifted")
    if manifest.get("crate_script") != (
        "python -m pytest -q "
        "prom_search_hswm/test_f1_aborted_exposure_v3_longinus.py"
    ):
        _fail("LABEL_ROT", "crate script drifted")
    return {
        "status": "PASS",
        "binding_id": EXPECTED_BINDING_ID,
        "producer_commit": EXPECTED_PRODUCER_COMMIT,
        "artifact_commit": EXPECTED_ARTIFACT_COMMIT,
        "receipt_raw_sha256": EXPECTED_RECEIPT_RAW_SHA256,
        "receipt_self_sha256": EXPECTED_RECEIPT_SELF_SHA256,
        "incident_producer_files_checked": len(seen),
        "producer_closure_root_sha256": EXPECTED_PRODUCER_ROOT,
        "longinus_layers": len(REQUIRED_LAYERS),
        "seven_layer_targets_checked": len(bound_paths),
        "blob_authority": "GIT_COMMIT_ONLY",
        "kg_write_state": kg["write_state"],
        "scientific_status": manifest["scientific_status"],
        "historical_upstream_model_calls": incident[
            "historical_upstream_model_calls"
        ],
        "prospective_successor_model_calls": incident[
            "prospective_successor_model_calls"
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?", default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    try:
        result = verify(args.manifest)
    except BindingError as error:
        print(json.dumps({"status": "FAIL", "reason": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
