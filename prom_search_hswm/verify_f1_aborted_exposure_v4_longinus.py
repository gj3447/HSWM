"""Verify the F1 r8 A2 v4 incident receipt and P-A-B pin topology."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from prom_search_hswm.verify_f1_aborted_exposure_v3_longinus import (
    BindingError,
    LINE_RANGE_RE,
    OBJECT_RE,
    PRODUCER_FIELDS,
    PRODUCER_FILE_FIELDS,
    REQUIRED_BINDING_KEYS,
    REQUIRED_LAYERS,
    SHA256_RE,
    _canonical_sha256,
    _changed_paths,
    _commit_blob,
    _definition_start,
    _fail,
    _git,
    _json_bytes,
    _load,
    _parameters,
    _safe_path,
    _signature_sha256,
    _single_parent,
    _strings,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    REPO_ROOT
    / "LONGINUS_HSWM_F1_ABORTED_EXPOSURE_V4_BINDING_2026-07-30.json"
)
SCHEMA = "longinus-hswm-f1-r8-aborted-exposure-v4-binding/v12"
EXPECTED_BINDING_ID = (
    "longinus-hswm-f1-r8-a2-v11-aborted-exposure-v4-v12-20260730"
)
EXPECTED_PRODUCER_COMMIT = "f82bc41ff1615b4f5a9231deca8a90be99ae5b9c"
EXPECTED_PRODUCER_PARENT = "8d23053f730be09852102e5b38437ebee4a4b409"
EXPECTED_PRODUCER_TREE = "543bdeb168a63d8c21bd2d17f271b6d691653e2c"
EXPECTED_ARTIFACT_COMMIT = "86f3b17380585cbab1c861dbbd65418c17074038"
EXPECTED_ARTIFACT_PARENT = EXPECTED_PRODUCER_COMMIT
EXPECTED_ARTIFACT_TREE = "02ac7f6157b8d0e8175aba3c928d41b9c74b72b4"
EXPECTED_PIN_COMMIT = "fb95ac0fd2bde91c4a0b3358c8e46f44cd9b6895"
EXPECTED_PIN_PARENT = EXPECTED_ARTIFACT_COMMIT
EXPECTED_PIN_TREE = "1f308b709ef24b8f55dc197ce6809a2469552be7"
EXPECTED_BINDING_SOURCE_COMMIT = EXPECTED_ARTIFACT_COMMIT
EXPECTED_RECEIPT_PATH = (
    "receipts/hswm_f1_r8_a2_v11_aborted_exposure.v4.json"
)
EXPECTED_RECEIPT_SCHEMA = "hswm-prom9-f1-aborted-attempt-exposure/v4"
EXPECTED_RECEIPT_RAW_SHA256 = (
    "68c6a29082505072acf0ec6166de191b45ea34e1b43acd384c2cf74442292c2f"
)
EXPECTED_RECEIPT_SELF_SHA256 = (
    "2a42ba116cb4d478c4f223ad62f7c29214ebe6f9ca730053d4504cd5ad9d3f23"
)
EXPECTED_RECEIPT_BLOB_OID = "4aae424312e72fead6f093b11d0741638b620e7f"
EXPECTED_RECEIPT_SIZE_BYTES = 1_071_401
EXPECTED_RECEIPT_SCHEMA_LINE = 2_124
EXPECTED_RECEIPT_LINE_COUNT = 16_426
EXPECTED_PRODUCER_ROOT = (
    "b204b6cfcfbf622853b832048dae1f541ec6038a05a6747994c2bcf54441f9b9"
)
EXPECTED_PRODUCER_FILES = 20
EXPECTED_PROFILE_SHA256 = (
    "5c8f245686515c2bc0716eb72e9b49469c9cc3c779ddca5fcaf9b0087abd1386"
)
EXPECTED_GENERATED_AT = "2026-07-30T11:41:25+09:00"
EXPECTED_BASELINE_SCOPE = (
    "HSWM F1 r8 A2 v11 aborted-attempt public v4 receipt, exact "
    "profile-bound producer AST closure, exact P-A-B receipt/pin topology, "
    "and fresh-zero-successor quarantine boundary"
)
EXPECTED_BLOB_AUTHORITY = (
    "Receipt bytes, producer targets, and the pre/post pin source are read "
    "with git cat-file from exact immutable commits; object identities are "
    "independently checked with ls-tree; worktree source is never read."
)
EXPECTED_ANCESTRY_RULE = (
    "The producer is the exact parent of the one-path receipt publication; "
    "that artifact commit is the exact parent of the one-path pin commit; "
    "the pin commit must be an ancestor of HEAD."
)
EXPECTED_PIN_PATH = "prom_search_hswm/prom9_f1_prior_exposure.py"
EXPECTED_PRE_PIN_RAW_SHA256 = (
    "9f0a65df44e4097a3008b1834168ef3d7c745570a8c88d7efb7a02f25a7692e9"
)
EXPECTED_POST_PIN_RAW_SHA256 = (
    "37e63bdb49cc8acc5c30cac08dc45ee208aa9b85b5375f678f5466373747cf40"
)
EXPECTED_PRE_PIN_BLOB_OID = "8b1d54057031f343f521f0901e68d9e722c158f7"
EXPECTED_POST_PIN_BLOB_OID = "9229ac08661d1b041a41841bf32875b77849429f"
EXPECTED_PRE_PIN_SIZE_BYTES = 298_193
EXPECTED_POST_PIN_SIZE_BYTES = 298_263
EXPECTED_PIN_LINE = 132
PIN_BEFORE = b"F1_R8_A2_INCIDENT_RECEIPT_SHA256: str | None = None\n"
PIN_AFTER = (
    b"F1_R8_A2_INCIDENT_RECEIPT_SHA256: str | None = (\n"
    b'    "2a42ba116cb4d478c4f223ad62f7c29214ebe6f9ca730053d4504cd5ad9d3f23"\n'
    b")\n"
)
EXPECTED_COUNTS = {
    "attempt_calls": 27,
    "attempt_events": 157,
    "attempt_states": {"ACCEPTED": 26, "PREPARED": 1},
    "components": 2,
    "item_runs": 8,
    "items": 2,
    "source_entities": 20,
    "spool_absent_calls": 1,
    "spool_calls": 26,
    "spool_complete_calls": 26,
}
EXPECTED_CANARY_COUNTER = {
    "schema_version": "hswm-prom9-f1-canary-post-counter/v1",
    "method": "DT_VLLM_ACCESS_LOG_EXACT_V1",
    "source_provider": "PI/dt.sh",
    "source_job_alias": "hswm-f1-r8-vllm-canary-triton",
    "request_route": "/v1/chat/completions",
    "access_record_pattern_sha256": (
        "55fc21ae6a1109881957fec636caf5e66593185c04ab235fae997b60e97cb738"
    ),
    "job_command": {
        "basename": "cmd.sh",
        "size_bytes": 652,
        "sha256": (
            "95e018951836b4a7fa1730e2c846dfd24171e9c81aca691a838bd16be22cb8dd"
        ),
    },
    "log_snapshot": {
        "basename": "log",
        "size_bytes": 60_031,
        "sha256": (
            "1b4be90649ec3ca9be4a56be551492808c3937d4796a0311147a8dde8dcdc1a1"
        ),
    },
    "origin_commitment_sha256": (
        "5740c8c416ca6bf283aeae82bfadbdc473a5733777a2c04d1ca030dc7f44fd2d"
    ),
    "http_status_counts": {"200": 27},
    "historical_baseline": 1,
    "terminal_total": 27,
    "incident_delta": 26,
    "complete": True,
    "receipt_sha256": (
        "9867e7f5a274c0f5090b450fbf034baa9f5c6e90da29eb35fd7a004c14f4ddf9"
    ),
}
EXPECTED_DISPOSITION = {
    "schema_version": "hswm-prom9-f1-successor-disposition/v1",
    "incident_profile_id": (
        "hswm-f1-r8-a2-v11-development-sigbus-20260730"
    ),
    "forensic_only": True,
    "resume_authorized": False,
    "successor_required": True,
    "legacy_database_mutation_authorized": False,
    "legacy_database_import_authorized": False,
    "accepted_result_import_authorized": False,
}
EXPECTED_TERMINATION = {
    "evidence_status": "OBSERVED_DT_JOB_DIRECTORY",
    "exit_code": 135,
    "signal": "SIGBUS",
    "signal_number": 7,
    "rc_evidence": {
        "basename": "rc",
        "sha256": (
            "35696336da00b304d91bb78c4be84c0e975baa9ee85d1b26d4a0168203c19288"
        ),
        "size_bytes": 4,
    },
}
EXPECTED_INCIDENT = {
    "aborted_attempt_exposure_receipt_sha256": EXPECTED_RECEIPT_SELF_SHA256,
    "counts": EXPECTED_COUNTS,
    "incident_profile_sha256": EXPECTED_PROFILE_SHA256,
    "historical_v8_upstream_model_calls": 1,
    "a2_upstream_model_calls": 26,
    "cumulative_terminal_upstream_model_calls": 27,
    "prospective_a3_upstream_model_calls": 0,
    "confirmatory_upstream_model_calls": 0,
    "scientific_verdicts": 0,
    "canary_counter": EXPECTED_CANARY_COUNTER,
    "successor_disposition": EXPECTED_DISPOSITION,
}
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
        "test_exact_a2_successor_frontier_and_coherent_tamper_refusal"
    ),
    EXPECTED_TARGET_PATHS[3]: (
        "test_historical_v8_spool_schema_is_a_separate_exact_authority"
    ),
    EXPECTED_RECEIPT_PATH: EXPECTED_RECEIPT_SCHEMA,
}
EXPECTED_CONTRACTS = {
    EXPECTED_TARGET_PATHS[0]: "R8_A2_V4_INCIDENT_PRODUCER__UNJUDGED",
    EXPECTED_TARGET_PATHS[1]: "R8_HISTORICAL_V8_SCHEMA_GATE__UNJUDGED",
    EXPECTED_TARGET_PATHS[2]: "R8_A2_V4_SUCCESSOR_FRONTIER_TEST__ENGINEERING_ONLY",
    EXPECTED_TARGET_PATHS[3]: "R8_HISTORICAL_V8_SCHEMA_TEST__ENGINEERING_ONLY",
    EXPECTED_RECEIPT_PATH: "R8_A2_ABORTED_EXPOSURE_V4_ARTIFACT__QUARANTINED",
}
EXPECTED_KG_NODES = {
    EXPECTED_TARGET_PATHS[0]: "LOCAL_PROPOSED_HSWM_F1_R8_A2_V4_INCIDENT_PRODUCER",
    EXPECTED_TARGET_PATHS[1]: (
        "LOCAL_PROPOSED_HSWM_F1_R8_HISTORICAL_V8_SCHEMA_GATE"
    ),
    EXPECTED_TARGET_PATHS[2]: (
        "LOCAL_PROPOSED_HSWM_F1_R8_A2_V4_SUCCESSOR_FRONTIER_TEST"
    ),
    EXPECTED_TARGET_PATHS[3]: (
        "LOCAL_PROPOSED_HSWM_F1_R8_HISTORICAL_V8_SCHEMA_TEST"
    ),
    EXPECTED_RECEIPT_PATH: (
        "LOCAL_PROPOSED_HSWM_F1_R8_A2_ABORTED_EXPOSURE_V4_RECEIPT"
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
    "pin_binding",
    "producer_authority",
    "required_target_paths",
    "bindings",
    "kg",
    "layers",
    "crate_script",
}


def _python_symbol_range(
    blob: bytes, relative: str, expected: Mapping[str, object]
) -> tuple[int, int]:
    if set(expected) != {
        "qualified", "name", "kind", "parameters", "signature_sha256"
    }:
        _fail("LABEL_ROT", f"Python symbol shape drifted for {relative}")
    name = expected.get("name")
    parameters = expected.get("parameters")
    if (
        not isinstance(name, str)
        or expected.get("kind") != "function"
        or not isinstance(parameters, list)
        or not all(isinstance(item, str) for item in parameters)
    ):
        _fail("LABEL_ROT", f"Python symbol label drifted for {relative}")
    try:
        source = blob.decode("utf-8")
        tree = ast.parse(source, filename=relative)
    except (UnicodeError, SyntaxError) as error:
        _fail("SIGNATURE_MISMATCHED", f"cannot parse {relative}: {error}")
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if len(matches) != 1:
        _fail("ORPHANED", f"top-level symbol {name!r} occurs {len(matches)} times")
    node = matches[0]
    if _parameters(node) != parameters:
        _fail("SIGNATURE_MISMATCHED", f"parameters drifted for {relative}:{name}")
    signature = expected.get("signature_sha256")
    if (
        not isinstance(signature, str)
        or SHA256_RE.fullmatch(signature) is None
        or _signature_sha256(source, node) != signature
    ):
        _fail("SIGNATURE_MISMATCHED", f"signature drifted for {relative}:{name}")
    module = relative[:-3].replace("/", ".")
    if expected.get("qualified") != f"{module}.{name}":
        _fail("LABEL_ROT", f"qualified symbol drifted for {relative}:{name}")
    end = getattr(node, "end_lineno", None)
    if not isinstance(end, int):
        _fail("SIGNATURE_MISMATCHED", f"symbol end line absent for {relative}:{name}")
    return _definition_start(node), end


def _receipt_symbol_range(
    blob: bytes, relative: str, expected: Mapping[str, object]
) -> tuple[int, int]:
    if (
        set(expected) != {"qualified", "name", "kind", "parameters"}
        or expected.get("qualified") != f"{relative}#schema_version"
        or expected.get("name") != EXPECTED_RECEIPT_SCHEMA
        or expected.get("kind") != "json_receipt"
        or expected.get("parameters") != []
    ):
        _fail("LABEL_ROT", "v4 JSON receipt symbol label drifted")
    receipt = _json_bytes(blob, "bound v4 exposure receipt")
    unsigned = dict(receipt)
    declared = unsigned.pop("aborted_attempt_exposure_receipt_sha256", None)
    if (
        receipt.get("schema_version") != EXPECTED_RECEIPT_SCHEMA
        or declared != EXPECTED_RECEIPT_SELF_SHA256
        or _canonical_sha256(unsigned) != EXPECTED_RECEIPT_SELF_SHA256
    ):
        _fail("DIVERGENT", "bound v4 JSON receipt self-identity drifted")
    schema_lines = [
        index
        for index, line in enumerate(blob.decode("utf-8").splitlines(), start=1)
        if line == f'  "schema_version": "{EXPECTED_RECEIPT_SCHEMA}",'
    ]
    if schema_lines != [EXPECTED_RECEIPT_SCHEMA_LINE]:
        _fail("SIGNATURE_MISMATCHED", "v4 receipt schema line drifted")
    return EXPECTED_RECEIPT_SCHEMA_LINE, EXPECTED_RECEIPT_SCHEMA_LINE


def _tree_blob(commit: str, relative: str) -> tuple[str, str, bytes]:
    blob = _commit_blob(commit, relative)
    row = _git(
        ["ls-tree", commit, "--", relative],
        label=f"cannot read tree row {relative}",
    ).decode("utf-8", "strict").strip()
    try:
        metadata, observed_path = row.split("\t", 1)
        mode, kind, oid = metadata.split()
    except ValueError:
        _fail("MISSING", f"malformed tree row: {relative}")
    if observed_path != relative or kind != "blob":
        _fail("MISSING", f"tree path is not a blob: {relative}")
    return mode, oid, blob


def _verify_topology(manifest: Mapping[str, object]) -> None:
    git = manifest.get("git")
    expected_git = {
        "remote": "https://github.com/gj3447/HSWM.git",
        "branch": "main",
        "producer_commit": EXPECTED_PRODUCER_COMMIT,
        "producer_parent": EXPECTED_PRODUCER_PARENT,
        "artifact_commit": EXPECTED_ARTIFACT_COMMIT,
        "artifact_parent": EXPECTED_ARTIFACT_PARENT,
        "artifact_tree": EXPECTED_ARTIFACT_TREE,
        "pin_commit": EXPECTED_PIN_COMMIT,
        "pin_parent": EXPECTED_PIN_PARENT,
        "pin_tree": EXPECTED_PIN_TREE,
        "binding_source_commit": EXPECTED_BINDING_SOURCE_COMMIT,
        "blob_authority": EXPECTED_BLOB_AUTHORITY,
        "ancestry_rule": EXPECTED_ANCESTRY_RULE,
    }
    if git != expected_git:
        _fail("LABEL_ROT", "Git authority label drifted")
    if _single_parent(EXPECTED_PRODUCER_COMMIT) != EXPECTED_PRODUCER_PARENT:
        _fail("DIVERGENT", "producer parent drifted")
    if _single_parent(EXPECTED_ARTIFACT_COMMIT) != EXPECTED_ARTIFACT_PARENT:
        _fail("DIVERGENT", "artifact parent drifted")
    if _single_parent(EXPECTED_PIN_COMMIT) != EXPECTED_PIN_PARENT:
        _fail("DIVERGENT", "pin parent drifted")
    for commit, expected_tree, label in (
        (EXPECTED_ARTIFACT_COMMIT, EXPECTED_ARTIFACT_TREE, "artifact"),
        (EXPECTED_PIN_COMMIT, EXPECTED_PIN_TREE, "pin"),
    ):
        observed_tree = _git(
            ["rev-parse", f"{commit}^{{tree}}"],
            label=f"cannot resolve {label} tree",
            classification="DIVERGENT",
        ).decode("ascii", "strict").strip()
        if observed_tree != expected_tree:
            _fail("DIVERGENT", f"{label} tree drifted")
    if _changed_paths(EXPECTED_ARTIFACT_PARENT, EXPECTED_ARTIFACT_COMMIT) != {
        EXPECTED_RECEIPT_PATH
    }:
        _fail("DIVERGENT", "artifact commit is not receipt-only")
    if _changed_paths(EXPECTED_PIN_PARENT, EXPECTED_PIN_COMMIT) != {
        EXPECTED_PIN_PATH
    }:
        _fail("DIVERGENT", "pin commit is not source-pin-only")
    for ancestor, descendant, label in (
        (EXPECTED_PRODUCER_COMMIT, EXPECTED_ARTIFACT_COMMIT, "producer/artifact"),
        (EXPECTED_ARTIFACT_COMMIT, EXPECTED_PIN_COMMIT, "artifact/pin"),
        (EXPECTED_PIN_COMMIT, "HEAD", "pin/HEAD"),
    ):
        _git(
            ["merge-base", "--is-ancestor", ancestor, descendant],
            label=f"{label} ancestry drifted",
            classification="DIVERGENT",
        )


def _verify_pin(manifest: Mapping[str, object]) -> None:
    expected_pin = {
        "path": EXPECTED_PIN_PATH,
        "symbol": "F1_R8_A2_INCIDENT_RECEIPT_SHA256",
        "line": EXPECTED_PIN_LINE,
        "producer_value": None,
        "pinned_value": EXPECTED_RECEIPT_SELF_SHA256,
        "pre_pin_blob_mode": "100644",
        "pre_pin_blob_oid": EXPECTED_PRE_PIN_BLOB_OID,
        "pre_pin_size_bytes": EXPECTED_PRE_PIN_SIZE_BYTES,
        "pre_pin_sha256": EXPECTED_PRE_PIN_RAW_SHA256,
        "pin_blob_mode": "100644",
        "pin_blob_oid": EXPECTED_POST_PIN_BLOB_OID,
        "pin_size_bytes": EXPECTED_POST_PIN_SIZE_BYTES,
        "pin_sha256": EXPECTED_POST_PIN_RAW_SHA256,
        "replacement_policy": "EXACT_UTF8_LITERAL_REPLACEMENT_ONLY",
    }
    if manifest.get("pin_binding") != expected_pin:
        _fail("LABEL_ROT", "pin binding drifted")
    pre_mode, pre_oid, before = _tree_blob(EXPECTED_ARTIFACT_COMMIT, EXPECTED_PIN_PATH)
    post_mode, post_oid, after = _tree_blob(EXPECTED_PIN_COMMIT, EXPECTED_PIN_PATH)
    if (
        pre_mode != "100644"
        or post_mode != "100644"
        or pre_oid != EXPECTED_PRE_PIN_BLOB_OID
        or post_oid != EXPECTED_POST_PIN_BLOB_OID
        or len(before) != EXPECTED_PRE_PIN_SIZE_BYTES
        or len(after) != EXPECTED_POST_PIN_SIZE_BYTES
        or hashlib.sha256(before).hexdigest() != EXPECTED_PRE_PIN_RAW_SHA256
        or hashlib.sha256(after).hexdigest() != EXPECTED_POST_PIN_RAW_SHA256
        or before.count(PIN_BEFORE) != 1
        or PIN_AFTER in before
        or after != before.replace(PIN_BEFORE, PIN_AFTER, 1)
        or before.splitlines()[EXPECTED_PIN_LINE - 1]
        != PIN_BEFORE.rstrip(b"\n")
        or after.splitlines()[EXPECTED_PIN_LINE - 1]
        != PIN_AFTER.splitlines()[0]
    ):
        _fail("DIVERGENT", "pin source is not the exact single replacement")


def _verify_receipt(manifest: Mapping[str, object]) -> dict[str, object]:
    expected_binding = {
        "path": EXPECTED_RECEIPT_PATH,
        "schema_version": EXPECTED_RECEIPT_SCHEMA,
        "schema_line": EXPECTED_RECEIPT_SCHEMA_LINE,
        "size_bytes": EXPECTED_RECEIPT_SIZE_BYTES,
        "raw_sha256": EXPECTED_RECEIPT_RAW_SHA256,
        "self_sha256": EXPECTED_RECEIPT_SELF_SHA256,
        "blob_mode": "100644",
        "blob_oid": EXPECTED_RECEIPT_BLOB_OID,
    }
    if manifest.get("receipt_binding") != expected_binding:
        _fail("LABEL_ROT", "receipt binding drifted")
    mode, oid, raw = _tree_blob(EXPECTED_ARTIFACT_COMMIT, EXPECTED_RECEIPT_PATH)
    if (
        mode != "100644"
        or oid != EXPECTED_RECEIPT_BLOB_OID
        or len(raw) != EXPECTED_RECEIPT_SIZE_BYTES
        or len(raw.splitlines()) != EXPECTED_RECEIPT_LINE_COUNT
        or hashlib.sha256(raw).hexdigest() != EXPECTED_RECEIPT_RAW_SHA256
    ):
        _fail("DIVERGENT", "receipt Git blob bytes drifted")
    receipt = _json_bytes(raw, "v4 exposure receipt")
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
        value.startswith(("/data/", "/Users/", "/home/", "/root/", "file://"))
        for value in public_strings
    ):
        _fail("DIVERGENT", "public receipt leaks private identity material")
    profile = receipt.get("profile_evidence")
    run_identity = receipt.get("run_identity")
    termination = receipt.get("termination")
    capture_policy = receipt.get("capture_policy")
    if (
        receipt.get("status") != "ABORTED_QUARANTINED"
        or receipt.get("complete") is not True
        or receipt.get("counts") != EXPECTED_COUNTS
        or not isinstance(profile, Mapping)
        or profile.get("profile_sha256") != EXPECTED_PROFILE_SHA256
        or _canonical_sha256(profile.get("profile")) != EXPECTED_PROFILE_SHA256
        or profile.get("canary_counter_receipt") != EXPECTED_CANARY_COUNTER
        or receipt.get("successor_disposition") != EXPECTED_DISPOSITION
        or not isinstance(run_identity, Mapping)
        or run_identity.get("incident_profile_id")
        != EXPECTED_DISPOSITION["incident_profile_id"]
        or run_identity.get("run_id") != "f1-2wiki-development-r8-try3-a2"
        or run_identity.get("job_alias")
        != "HSWM_F1_R8_A2_V11_DEVELOPMENT_SIGBUS"
        or run_identity.get("implementation_commit")
        != "5f4aab5f87af2b28bb5e0d1cb7f3b62dc59abf23"
        or run_identity.get("carrier_commit")
        != "5f4aab5f87af2b28bb5e0d1cb7f3b62dc59abf23"
        or run_identity.get("symposium_commit")
        != "54aeaa02f867617756004793e8d4fd6c7b7d9b0e"
        or termination != EXPECTED_TERMINATION
        or not isinstance(capture_policy, Mapping)
        or capture_policy.get("model_calls_invoked") is not False
        or capture_policy.get("gold_inputs_accepted") is not False
        or capture_policy.get("kg_accessed") is not False
    ):
        _fail("LABEL_ROT", "quarantined A2 incident boundary drifted")
    if manifest.get("incident_boundary") != EXPECTED_INCIDENT:
        _fail("LABEL_ROT", "Longinus incident boundary drifted")
    return receipt


def _verify_producer(
    manifest: Mapping[str, object], receipt: Mapping[str, object]
) -> int:
    evidence = receipt.get("evidence_bindings")
    receipt_authority = (
        evidence.get("current_producer_authority")
        if isinstance(evidence, Mapping)
        else None
    )
    manifest_authority = manifest.get("producer_authority")
    if (
        not isinstance(receipt_authority, Mapping)
        or not isinstance(manifest_authority, Mapping)
        or set(receipt_authority) != PRODUCER_FIELDS
        or set(manifest_authority) != PRODUCER_FIELDS
        or receipt_authority != manifest_authority
    ):
        _fail("LABEL_ROT", "producer authority shape or receipt binding drifted")
    expected_scalars = {
        "commit": EXPECTED_PRODUCER_COMMIT,
        "tree": EXPECTED_PRODUCER_TREE,
        "entrypoint": "prom_search_hswm/prom9_f1_prior_exposure.py",
        "closure_policy": "MODULE_SCOPE_LOCAL_AST_LFP_V1",
        "file_count": EXPECTED_PRODUCER_FILES,
        "closure_root_sha256": EXPECTED_PRODUCER_ROOT,
    }
    if any(manifest_authority.get(key) != value for key, value in expected_scalars.items()):
        _fail("LABEL_ROT", "producer scalar authority drifted")
    files = manifest_authority.get("files")
    if not isinstance(files, list) or len(files) != EXPECTED_PRODUCER_FILES:
        _fail("ORPHANED", "producer file inventory is absent")
    ordered_paths: list[str] = []
    seen: set[str] = set()
    for row in files:
        if not isinstance(row, Mapping) or set(row) != PRODUCER_FILE_FIELDS:
            _fail("LABEL_ROT", "producer file row shape drifted")
        relative = row.get("relative_path")
        if not isinstance(relative, str):
            _fail("ORPHANED", "producer path is absent")
        _safe_path(relative)
        if relative in seen:
            _fail("ORPHANED", f"duplicate producer path: {relative}")
        seen.add(relative)
        ordered_paths.append(relative)
        mode, oid, blob = _tree_blob(EXPECTED_PRODUCER_COMMIT, relative)
        if (
            mode != row.get("blob_mode")
            or mode != "100644"
            or oid != row.get("blob_oid")
            or not isinstance(oid, str)
            or OBJECT_RE.fullmatch(oid) is None
            or type(row.get("size_bytes")) is not int
            or len(blob) != row.get("size_bytes")
            or not isinstance(row.get("sha256"), str)
            or SHA256_RE.fullmatch(str(row.get("sha256"))) is None
            or hashlib.sha256(blob).hexdigest() != row.get("sha256")
        ):
            _fail("DIVERGENT", f"producer Git bytes drifted: {relative}")
    if tuple(ordered_paths) != EXPECTED_PRODUCER_PATHS:
        _fail("ORPHANED", "producer path inventory drifted")
    if _canonical_sha256(files) != EXPECTED_PRODUCER_ROOT:
        _fail("DIVERGENT", "producer closure root drifted")
    observed_tree = _git(
        ["rev-parse", f"{EXPECTED_PRODUCER_COMMIT}^{{tree}}"],
        label="cannot resolve producer tree",
        classification="DIVERGENT",
    ).decode("ascii", "strict").strip()
    if observed_tree != EXPECTED_PRODUCER_TREE:
        _fail("DIVERGENT", "producer tree object drifted")
    return len(seen)


def _verify_layers(manifest: Mapping[str, object]) -> int:
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
    nodes: set[str] = set()
    contracts = {"implementation": 0, "test": 0, "artifact": 0}
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
        node = binding.get("kg_node")
        if node != EXPECTED_KG_NODES[relative] or str(node) in nodes:
            _fail("LABEL_ROT", f"local KG identity drifted for {relative}")
        nodes.add(str(node))
        contract = binding.get("contract_binding")
        if contract != EXPECTED_CONTRACTS[relative]:
            _fail("LABEL_ROT", f"contract binding drifted for {relative}")
        if str(contract).endswith("__UNJUDGED"):
            contracts["implementation"] += 1
        elif str(contract).endswith("__ENGINEERING_ONLY"):
            contracts["test"] += 1
        elif str(contract).endswith("__QUARANTINED"):
            contracts["artifact"] += 1
        else:
            _fail("LABEL_ROT", f"contract class drifted for {relative}")
        symbol = binding.get("code_symbol")
        if not isinstance(symbol, Mapping) or symbol.get("name") != EXPECTED_SYMBOLS[relative]:
            _fail("LABEL_ROT", f"code symbol identity drifted for {relative}")
        blob = _commit_blob(EXPECTED_BINDING_SOURCE_COMMIT, relative)
        expected_sha = binding.get("sha256")
        if (
            not isinstance(expected_sha, str)
            or SHA256_RE.fullmatch(expected_sha) is None
            or hashlib.sha256(blob).hexdigest() != expected_sha
        ):
            _fail("DIVERGENT", f"binding Git blob SHA drifted for {relative}")
        start, end = (
            _receipt_symbol_range(blob, relative, symbol)
            if relative == EXPECTED_RECEIPT_PATH
            else _python_symbol_range(blob, relative, symbol)
        )
        match = LINE_RANGE_RE.fullmatch(str(binding.get("line_range")))
        if (
            match is None
            or int(match.group(1)) != start
            or int(match.group(2)) != end
            or line_text != str(start)
        ):
            _fail("DIVERGENT", f"symbol/file line range drifted for {relative}")
        crate = binding.get("crate_script")
        if crate != EXPECTED_CRATES[relative]:
            _fail("LABEL_ROT", f"crate script drifted for {relative}")
        crate_path = str(crate).removeprefix("python -m pytest -q ")
        if not Path(crate_path).name.startswith("test_"):
            _fail("ORPHANED", f"crate target is not a test for {relative}")
        _commit_blob(EXPECTED_BINDING_SOURCE_COMMIT, crate_path)
    if tuple(bound_paths) != EXPECTED_TARGET_PATHS:
        _fail("ORPHANED", "seven-layer reverse scan is incomplete")
    if contracts != {"implementation": 2, "test": 2, "artifact": 1}:
        _fail("LABEL_ROT", "seven-layer contract cardinality drifted")
    return len(bound_paths)


def verify(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, object]:
    manifest = _load(manifest_path)
    if set(manifest) != TOP_LEVEL_KEYS:
        _fail("LABEL_ROT", "manifest top-level shape drifted")
    inadmissible = "EXPLORATORY_ENGINEERING_ONLY__PREREGISTRATION_INADMISSIBLE"
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("binding_id") != EXPECTED_BINDING_ID
        or manifest.get("binding_state") != "PIERCED_LOCAL_NO_KG_WRITE"
        or manifest.get("generated_at") != EXPECTED_GENERATED_AT
        or manifest.get("baseline_scope") != EXPECTED_BASELINE_SCOPE
        or manifest.get("scientific_status") != "UNJUDGED"
        or manifest.get("evidence_class") != inadmissible
        or manifest.get("r7_status") != inadmissible
        or manifest.get("b22_gate") != "LOCKED"
        or type(manifest.get("model_calls")) is not int
        or manifest.get("model_calls") != 26
        or manifest.get("layers") != list(REQUIRED_LAYERS)
    ):
        _fail("LABEL_ROT", "scientific or seven-layer boundary drifted")
    _verify_topology(manifest)
    _verify_pin(manifest)
    receipt = _verify_receipt(manifest)
    producer_files = _verify_producer(manifest, receipt)
    targets = _verify_layers(manifest)
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
        "prom_search_hswm/test_f1_aborted_exposure_v4_longinus.py"
    ):
        _fail("LABEL_ROT", "crate script drifted")
    return {
        "status": "PASS",
        "binding_id": EXPECTED_BINDING_ID,
        "producer_commit": EXPECTED_PRODUCER_COMMIT,
        "artifact_commit": EXPECTED_ARTIFACT_COMMIT,
        "pin_commit": EXPECTED_PIN_COMMIT,
        "receipt_raw_sha256": EXPECTED_RECEIPT_RAW_SHA256,
        "receipt_self_sha256": EXPECTED_RECEIPT_SELF_SHA256,
        "incident_producer_files_checked": producer_files,
        "producer_closure_root_sha256": EXPECTED_PRODUCER_ROOT,
        "longinus_layers": len(REQUIRED_LAYERS),
        "seven_layer_targets_checked": targets,
        "blob_authority": "GIT_COMMIT_ONLY",
        "kg_write_state": kg["write_state"],
        "scientific_status": manifest["scientific_status"],
        "historical_v8_upstream_model_calls": 1,
        "a2_upstream_model_calls": 26,
        "cumulative_terminal_upstream_model_calls": 27,
        "prospective_a3_upstream_model_calls": 0,
        "canary_terminal_total": 27,
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
