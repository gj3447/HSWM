"""Deterministic, offline preregistration-B construction for DNRD-4.

This module turns already frozen Source-A evidence into the *one* new B-path
payload.  It neither makes a commit nor opens a network connection, starts a
model, creates mutable experiment roots, or writes an execution configuration.
The resulting bytes are canonical JSON with no terminal newline: Git's blob
identity is deliberately left to the subsequent, one-path B commit.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import unicodedata
from typing import Any, Mapping, Sequence

from . import execute as _execute

from .execute import (
    MAX_OUTPUT_TOKENS,
    MODEL_ID,
    OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256,
    OFFICIAL_NODE_EXECUTABLE_SHA256,
    OFFICIAL_NODE_VERSION,
    OFFICIAL_PYTHON_EXECUTABLE_SHA256,
    OFFICIAL_PYTHON_VERSION,
    OFFICIAL_UNICODE_DATA_VERSION,
    PREREGISTRATION_B_CI_RECEIPT_SCHEMA,
    PREREG_CLAIM_BOUNDARY,
    PREREG_SCHEMA,
    QUALIFICATION_SOURCE_PATHS,
    RUNTIME_TREE_MANIFEST_SCHEMA,
    SCORER_ARGUMENT_CONTRACT,
    SOURCE_CI_RECEIPT_SCHEMA,
    SOURCE_MANIFEST_SCHEMA,
    STRUCTURED_OUTPUT_QUALIFICATION_RECORD_ROLE,
    STRUCTURED_OUTPUT_QUALIFICATION_SCHEMA,
    TOKENIZER_PREFLIGHT_PROMPT,
    VLLM_VERSION,
    _pinned_subprocess_environment,
)
from .task_family import canonical_json, commitment


class RegistrationRefusal(ValueError):
    """A supplied Source-A pin cannot safely form the DNRD-4 B artifact."""


_HEX = frozenset("0123456789abcdef")
_DATE = "%Y-%m-%d"


@dataclass(frozen=True, slots=True)
class RegistrationInputs:
    """All dynamic pins that become part of the immutable B preregistration."""

    repo_root: Path
    source_manifest_path: str
    source_ci_receipt_path: Path
    runtime_manifest_path: Path
    qualification_path: Path
    model_endpoint: str
    bridge_runtime_root: Path
    bridge_implementation_path: Path
    bridge_state_root: Path
    scorer_implementation_path: Path
    node_executable_path: Path
    python_executable_path: Path
    verifier_helper_path: Path
    verifier_package_lock_path: Path
    verifier_runtime_bundle_path: Path
    created_at: str


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _plain_file(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise RegistrationRefusal(f"{label} is absent") from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise RegistrationRefusal(f"{label} must be a plain regular file")


def _plain_directory(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise RegistrationRefusal(f"{label} is absent") from error
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise RegistrationRefusal(f"{label} must be a plain directory")


def _file_sha(path: Path, label: str) -> str:
    _plain_file(path, label)
    return _sha(path.read_bytes())


def _hex(value: object, label: str, *, length: int = 64) -> str:
    if type(value) is not str or len(value) != length or any(char not in _HEX for char in value):
        raise RegistrationRefusal(f"{label} must be lowercase {length}-hex")
    return value


def _relative(value: object, label: str) -> str:
    if type(value) is not str or not value or value.startswith("/"):
        raise RegistrationRefusal(f"{label} must be a nonempty relative path")
    path = Path(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise RegistrationRefusal(f"{label} escapes its root")
    return path.as_posix()


def _object(raw: bytes, label: str, *, canonical: bool) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise RegistrationRefusal(f"{label} is not UTF-8") from error

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in pairs:
            if key in output:
                raise RegistrationRefusal(f"{label} repeats JSON key {key!r}")
            output[key] = value
        return output

    def no_constant(value: str) -> None:
        raise RegistrationRefusal(f"{label} contains forbidden JSON constant {value!r}")

    try:
        value = json.loads(text, object_pairs_hook=no_duplicates, parse_constant=no_constant)
    except (json.JSONDecodeError, RegistrationRefusal) as error:
        if isinstance(error, RegistrationRefusal):
            raise
        raise RegistrationRefusal(f"{label} is not JSON") from error
    if type(value) is not dict:
        raise RegistrationRefusal(f"{label} must be a JSON object")
    if canonical and canonical_json(value) != raw:
        raise RegistrationRefusal(f"{label} must have exact canonical JSON bytes and no LF")
    return value


def _keys(value: object, expected: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise RegistrationRefusal(f"{label} key set drifted")
    return value


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode:
        raise RegistrationRefusal(f"git {' '.join(args)} failed")
    try:
        return completed.stdout.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError as error:
        raise RegistrationRefusal("Git returned a non-ASCII identity") from error


def _date(value: str) -> None:
    try:
        datetime.strptime(value, _DATE)
    except ValueError as error:
        raise RegistrationRefusal("created_at must be YYYY-MM-DD") from error


def _utc(value: object, label: str) -> int:
    if type(value) is not str:
        raise RegistrationRefusal(f"{label} must be UTC RFC3339")
    try:
        return int(datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())
    except ValueError as error:
        raise RegistrationRefusal(f"{label} must be UTC RFC3339 seconds") from error


def _source_identity(inputs: RegistrationInputs) -> tuple[str, str, int, str, list[dict[str, str]]]:
    root = inputs.repo_root.resolve()
    _plain_directory(root, "Source-A checkout")
    if _git(root, "status", "--porcelain"):
        raise RegistrationRefusal("Source-A checkout must be clean")
    if subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=root).returncode == 0:
        raise RegistrationRefusal("Source-A checkout must be detached")
    commit = _hex(_git(root, "rev-parse", "HEAD"), "Source-A commit", length=40)
    tree = _hex(_git(root, "rev-parse", "HEAD^{tree}"), "Source-A tree", length=40)
    try:
        committed_at = int(_git(root, "show", "-s", "--format=%ct", "HEAD"))
    except ValueError as error:
        raise RegistrationRefusal("Source-A commit time is malformed") from error
    if committed_at < 0:
        raise RegistrationRefusal("Source-A commit time is malformed")
    relative = _relative(inputs.source_manifest_path, "source manifest path")
    manifest_path = root / relative
    raw = manifest_path.read_bytes()
    manifest = _object(raw, "source manifest", canonical=True)
    data = _keys(manifest, {"schema_version", "experiment_id", "source_commit_tree_bound_externally", "files"}, "source manifest")
    if (data["schema_version"] != SOURCE_MANIFEST_SCHEMA or data["experiment_id"] != "HSWM-DNRD-4" or
            data["source_commit_tree_bound_externally"] != "SOURCE_COMMIT_TREE_BOUND_EXTERNALLY_NO_SELF_CYCLE"):
        raise RegistrationRefusal("source manifest identity drifted")
    rows = data["files"]
    if type(rows) is not list or not rows:
        raise RegistrationRefusal("source manifest must contain files")
    prior = ""
    source_rows: list[dict[str, str]] = []
    for ordinal, row in enumerate(rows):
        entry = _keys(row, {"path", "sha256"}, f"source manifest.files[{ordinal}]")
        path, digest = _relative(entry["path"], "source manifest path"), _hex(entry["sha256"], "source manifest SHA-256")
        if path <= prior or _file_sha(root / path, f"source member {path}") != digest:
            raise RegistrationRefusal("source manifest order or source member hash drifted")
        prior = path
        source_rows.append({"path": path, "sha256": digest})
    return commit, tree, committed_at, _sha(raw), source_rows


def _source_ci(
    path: Path, *, commit: str, tree: str, source_committed_at: int
) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    receipt = _object(raw, "source CI receipt", canonical=True)
    data = _keys(receipt, {"schema_version", "provider", "run_id", "head_sha", "conclusion", "raw_response_sha256", "raw_response_utf8", "discovery_query", "critical_projection", "raw_list_response_sha256", "raw_list_response_utf8", "receipt_sha256"}, "source CI receipt")
    unsigned = {key: value for key, value in data.items() if key != "receipt_sha256"}
    if (data["schema_version"] != SOURCE_CI_RECEIPT_SCHEMA or data["provider"] != "GITHUB_ACTIONS" or
            type(data["run_id"]) is not int or data["run_id"] <= 0 or data["head_sha"] != commit or
            data["conclusion"] != "success" or data["receipt_sha256"] != commitment(unsigned)):
        raise RegistrationRefusal("source CI receipt identity/self-hash drifted")
    _hex(data["raw_response_sha256"], "source CI raw response SHA-256")
    if type(data["raw_response_utf8"]) is not str or _sha(data["raw_response_utf8"].encode()) != data["raw_response_sha256"]:
        raise RegistrationRefusal("source CI raw response digest drifted")
    try:
        _execute._validate_ci_v2_evidence(data, label="source CI receipt")
    except _execute.ExecutionRefusal as error:
        raise RegistrationRefusal(str(error)) from error
    api = _object(data["raw_response_utf8"].encode(), "source CI raw response", canonical=False)
    head = api.get("head_commit")
    if (api.get("id") != data["run_id"] or api.get("head_sha") != commit or api.get("status") != "completed" or
            api.get("conclusion") != "success" or type(head) is not dict or head.get("id") != commit or head.get("tree_id") != tree):
        raise RegistrationRefusal("source CI raw response does not attest Source-A")
    if _utc(api.get("updated_at"), "source CI raw response.updated_at") < source_committed_at:
        raise RegistrationRefusal("source CI completed before the frozen Source-A commit")
    return dict(data), _sha(raw)


def _runtime_manifest(
    path: Path,
    *,
    commit: str,
    tree: str,
    manifest_path: str,
    manifest_sha: str,
    source_rows: list[dict[str, str]],
    node_sha: str,
    node_version: str,
    runtime_root: Path,
    bridge_implementation: Path,
) -> str:
    raw = path.read_bytes()
    value = _object(raw, "runtime manifest", canonical=True)
    data = _keys(value, {"schema_version", "root_path", "entrypoint", "files", "external_packages", "build_provenance"}, "runtime manifest")
    provenance = _keys(data["build_provenance"], {"source_a_commit", "source_a_tree", "source_manifest_path", "source_manifest_sha256", "node_executable_sha256", "node_version", "dependency_materialization_command", "compilation_command", "claim_boundary", "source_inputs", "package_roots", "typescript"}, "runtime manifest provenance")
    if (data["schema_version"] != RUNTIME_TREE_MANIFEST_SCHEMA or data["root_path"] != str(runtime_root) or
            not isinstance(data["entrypoint"], str) or provenance["source_a_commit"] != commit or
            provenance["source_a_tree"] != tree or provenance["source_manifest_path"] != manifest_path or
            provenance["source_manifest_sha256"] != manifest_sha or provenance["node_executable_sha256"] != node_sha or
            provenance["node_version"] != node_version or provenance["source_inputs"] != source_rows):
        raise RegistrationRefusal("runtime manifest does not bind the supplied Source-A and Node pins")
    _plain_directory(runtime_root, "bridge runtime root")
    entrypoint = _relative(data["entrypoint"], "runtime manifest entrypoint")
    try:
        bridge_relative = bridge_implementation.resolve().relative_to(runtime_root.resolve()).as_posix()
    except ValueError as error:
        raise RegistrationRefusal("bridge implementation must reside under the runtime root") from error
    if entrypoint != bridge_relative:
        raise RegistrationRefusal("runtime manifest entrypoint differs from the CLI bridge implementation")
    entries = data["files"]
    if type(entries) is not list:
        raise RegistrationRefusal("runtime manifest files must be a list")
    matching = [
        _keys(row, {"path", "sha256", "bytes"}, "runtime manifest file")
        for row in entries
        if type(row) is dict and row.get("path") == entrypoint
    ]
    if len(matching) != 1:
        raise RegistrationRefusal("runtime manifest must contain exactly one bridge entrypoint row")
    entry = matching[0]
    if type(entry["bytes"]) is not int or entry["bytes"] < 0 or _hex(entry["sha256"], "runtime bridge entrypoint SHA-256") != _file_sha(bridge_implementation, "bridge implementation") or bridge_implementation.stat().st_size != entry["bytes"]:
        raise RegistrationRefusal("runtime manifest bridge entrypoint bytes/hash drifted")
    return _sha(raw)


def _qualification(
    path: Path,
    *,
    endpoint: str,
    source_rows: list[dict[str, str]],
) -> str:
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise RegistrationRefusal("qualification must be one canonical JSON object followed by LF")
    value = _object(raw[:-1], "qualification", canonical=True)
    required = {"schema_version", "domain", "event_schema", "experiment_occurrence", "future_seed_material_used", "record_role", "raw_full_stdout_record_persisted", "retry_count", "max_output_tokens", "model_endpoint", "served_model_id", "vllm_version", "provider_cache_independence", "calls", "started_at_unix_ns", "ended_at_unix_ns", "source_files", "python_executable_sha256", "python_version", "unicode_data_version"}
    data = _keys(value, required, "qualification")
    if (data["schema_version"] != STRUCTURED_OUTPUT_QUALIFICATION_SCHEMA or data["domain"] != "HSWM-DNRD4-STRUCTURED-OUTPUT-QUALIFICATION-v1" or
            data["event_schema"] != "hswm-dnrd-live-model-event/v3" or data["experiment_occurrence"] is not False or
            data["future_seed_material_used"] is not False or data["record_role"] != STRUCTURED_OUTPUT_QUALIFICATION_RECORD_ROLE or
            data["raw_full_stdout_record_persisted"] is not False or data["retry_count"] != 0 or
            data["max_output_tokens"] != MAX_OUTPUT_TOKENS or data["model_endpoint"] != endpoint or
            data["served_model_id"] != MODEL_ID or data["vllm_version"] != VLLM_VERSION):
        raise RegistrationRefusal("qualification does not bind the DNRD-4 non-scientific contract")
    source_hashes = {row["path"]: row["sha256"] for row in source_rows}
    source_files = data["source_files"]
    if type(source_files) is not list or len(source_files) != len(QUALIFICATION_SOURCE_PATHS):
        raise RegistrationRefusal("qualification source-file closure drifted")
    for index, expected_path in enumerate(QUALIFICATION_SOURCE_PATHS):
        source_file = _keys(
            source_files[index],
            {"path", "sha256"},
            f"qualification.source_files[{index}]",
        )
        if source_file["path"] != expected_path:
            raise RegistrationRefusal("qualification source-file order drifted")
        _hex(source_file["sha256"], f"qualification.source_files[{index}].sha256")
        if source_file["sha256"] != source_hashes.get(expected_path):
            raise RegistrationRefusal("qualification source identities do not bind Source-A")
    _hex(data["python_executable_sha256"], "qualification Python executable SHA-256")
    if (
        data["python_executable_sha256"] != OFFICIAL_PYTHON_EXECUTABLE_SHA256
        or data["python_version"] != OFFICIAL_PYTHON_VERSION
        or data["unicode_data_version"] != OFFICIAL_UNICODE_DATA_VERSION
    ):
        raise RegistrationRefusal(
            "qualification Python/Unicode runtime identities do not bind the frozen runtime"
        )
    return _sha(raw)


def _version(path: Path, argument: str, label: str) -> str:
    _plain_file(path, label)
    try:
        completed = subprocess.run([str(path), argument], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=60, env=_pinned_subprocess_environment())
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RegistrationRefusal(f"{label} cannot report a version") from error
    if completed.returncode:
        raise RegistrationRefusal(f"{label} cannot report a version")
    value = completed.stdout.decode("ascii", errors="strict").strip()
    if not value:
        raise RegistrationRefusal(f"{label} returned an empty version")
    return value


def build_preregistration(inputs: RegistrationInputs) -> dict[str, Any]:
    """Return, but do not write, the exact canonical DNRD-4 B payload."""

    _date(inputs.created_at)
    if not inputs.model_endpoint.startswith(("http://", "https://")):
        raise RegistrationRefusal("model endpoint must be an absolute HTTP(S) URL")
    commit, tree, source_committed_at, source_manifest_sha, source_rows = _source_identity(inputs)
    ci, ci_sha = _source_ci(
        inputs.source_ci_receipt_path,
        commit=commit,
        tree=tree,
        source_committed_at=source_committed_at,
    )
    node = inputs.node_executable_path.resolve()
    python = inputs.python_executable_path.resolve()
    node_sha, node_version = _file_sha(node, "Node executable"), _version(node, "--version", "Node executable")
    python_sha, python_banner = _file_sha(python, "Python executable"), _version(python, "--version", "Python executable")
    if (
        node_sha != OFFICIAL_NODE_EXECUTABLE_SHA256
        or node_version != OFFICIAL_NODE_VERSION
    ):
        raise RegistrationRefusal("Node pin is not the frozen DNRD production runtime")
    if (
        python.resolve() != Path(sys.executable).resolve()
        or python_sha != OFFICIAL_PYTHON_EXECUTABLE_SHA256
        or python_banner != f"Python {OFFICIAL_PYTHON_VERSION}"
        or f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}" != OFFICIAL_PYTHON_VERSION
        or unicodedata.unidata_version != OFFICIAL_UNICODE_DATA_VERSION
    ):
        raise RegistrationRefusal("Python/Unicode pin is not the frozen DNRD production runtime")
    for path, label in ((inputs.bridge_runtime_root, "bridge runtime root"), (inputs.bridge_implementation_path, "bridge implementation"), (inputs.scorer_implementation_path, "scorer implementation"), (inputs.verifier_helper_path, "verifier helper"), (inputs.verifier_package_lock_path, "verifier package lock"), (inputs.verifier_runtime_bundle_path, "verifier runtime bundle")):
        if not path.is_absolute():
            raise RegistrationRefusal(f"{label} must be absolute")
    runtime_root = inputs.bridge_runtime_root.resolve()
    bridge_implementation = inputs.bridge_implementation_path.resolve()
    runtime_sha = _runtime_manifest(inputs.runtime_manifest_path, commit=commit, tree=tree, manifest_path=_relative(inputs.source_manifest_path, "source manifest path"), manifest_sha=source_manifest_sha, source_rows=source_rows, node_sha=node_sha, node_version=node_version, runtime_root=runtime_root, bridge_implementation=bridge_implementation)
    qualification_sha = _qualification(
        inputs.qualification_path,
        endpoint=inputs.model_endpoint,
        source_rows=source_rows,
    )
    expected_scorer = inputs.repo_root.resolve() / "_research/dnrd/scorer.py"
    expected_helper = inputs.repo_root.resolve() / "_research/dnrd/verify-beacon.mjs"
    expected_lock = inputs.repo_root.resolve() / "tools/swm0w_drand/package-lock.json"
    expected_bundle = inputs.repo_root.resolve() / "tools/swm0w_drand/node_modules/drand-client/build/esm/index.mjs"
    if (
        inputs.scorer_implementation_path.resolve() != expected_scorer
        or inputs.verifier_helper_path.resolve() != expected_helper
        or inputs.verifier_package_lock_path.resolve() != expected_lock
        or inputs.verifier_runtime_bundle_path.resolve() != expected_bundle
        or _file_sha(inputs.verifier_runtime_bundle_path, "verifier runtime bundle")
        != OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256
    ):
        raise RegistrationRefusal("drand/scorer topology or official runtime-bundle pin drifted")
    scorer_sha = _file_sha(inputs.scorer_implementation_path, "scorer implementation")
    bridge_state = inputs.bridge_state_root.resolve()
    if not bridge_state.is_absolute():
        raise RegistrationRefusal("planned bridge state root must be absolute")
    bridge_config = {"root_path": str(bridge_state), "frozen_scorer_source_sha256": scorer_sha}
    value = {
        "schema_version": PREREG_SCHEMA, "experiment_id": "HSWM-DNRD-4", "protocol_version": "v4", "created_at": inputs.created_at,
        "status": "FROZEN_AWAITING_SUCCESSFUL_PREREGISTRATION_B_CI_AND_FUTURE_PULSE",
        "authority": {"broad_research_continuation_requested": True, "measurement_authorized_by_user_broad_continuation": True, "authorization_is_scientific_evidence": False, "measurement_requires_external_exact_hash_ratification_receipt": False, "measurement_requires_successful_preregistration_b_ci_receipt": True, "scientific_judgment_emitted": False, "external_governance_required": False},
        "canonical_role": PREREG_CLAIM_BOUNDARY["canonical_role"], "predecessor_bindings": PREREG_CLAIM_BOUNDARY["predecessor_bindings"], "forbidden_rescues": PREREG_CLAIM_BOUNDARY["forbidden_rescues"], "scientific_question": PREREG_CLAIM_BOUNDARY["scientific_question"], "hypotheses": PREREG_CLAIM_BOUNDARY["hypotheses"],
        "testbed": {"family": "REPEATED_CONTEXT_TABULAR_ROUTING_MECHANICS_V2", "relationship_to_prior_p1": PREREG_CLAIM_BOUNDARY["testbed_claims"]["relationship_to_prior_p1"], "development_streams": 4, "training_calls_per_stream_maximum": 8, "paired_heldout_probes_per_stream": 8, "evaluation_arms": 3, "evaluation_calls": 96, "shared_learning_or_compiler_calls_maximum": 32, "client_dispatched_generation_request_ceiling": 128, "analysis_unit": PREREG_CLAIM_BOUNDARY["testbed_claims"]["analysis_unit"], "model": {"served_model_id": MODEL_ID, "substitution_allowed": False, "temperature": 0, "thinking": False, "max_output_tokens": MAX_OUTPUT_TOKENS, "deployment_readback_required": True, "exact_weight_revision_attested": False, "exact_weight_identity_claimed": False}, "freshness": PREREG_CLAIM_BOUNDARY["testbed_claims"]["freshness"]},
        "learning_boundary": PREREG_CLAIM_BOUNDARY["learning_boundary"], "arms": PREREG_CLAIM_BOUNDARY["arms"], "interventions": PREREG_CLAIM_BOUNDARY["interventions"],
        "parity_and_leakage": {"same_served_model_id_and_chat_endpoint": True, "equal_client_dispatched_and_logical_requests": True, "equal_generation_limits_input_token_parity_not_claimed": True, "equal_candidate_evidence_universe": True, "all_active_payloads_within_byte_ceiling": True, "active_state_byte_ceiling": 16_384, "full_fixed_rule_replay_numeric_payload_bytes_equal": True, "full_deranged_numeric_payload_byte_count_equal": True, "arm_labels_hidden_from_model": True, "fresh_process_recovery_observed": True, "distinct_arm_mount_ids": True, "evaluation_read_only_wrt_routing_observed": True, "pre_dispatch_readout_bound_before_model_response": True, "scorer_outcome_response_independent": True, "cache_hits_required": 0, "private_route_binding_open_only_after_response_seal": True, "compiler_input_audit": PREREG_CLAIM_BOUNDARY["parity_claims"]["compiler_input_audit"], "canary": PREREG_CLAIM_BOUNDARY["parity_claims"]["canary"]},
        "diagnostic_readouts": PREREG_CLAIM_BOUNDARY["diagnostic_readouts"], "void_conditions": PREREG_CLAIM_BOUNDARY["void_conditions"], "single_attempt_policy": PREREG_CLAIM_BOUNDARY["single_attempt_policy"], "required_before_measurement": PREREG_CLAIM_BOUNDARY["required_before_measurement"], "result_promotion": PREREG_CLAIM_BOUNDARY["result_promotion"], "measurement_gate": PREREG_CLAIM_BOUNDARY["measurement_gate"],
        "preregistration_b_ci_gate": {"receipt_schema": PREREGISTRATION_B_CI_RECEIPT_SCHEMA, "provider": "GITHUB_ACTIONS", "status": "completed", "conclusion": "success", "minimum_lead_seconds": 900, "selection_rule": "EXACT_UNFILTERED_PUSH_MAIN_HEAD_SHA_WORKFLOW_LIST_TOTAL_COUNT_ONE_FIRST_ATTEMPT"},
        "source_a_ci": {"receipt_sha256": ci_sha, "run_id": ci["run_id"], "head_sha": commit, "conclusion": "success"},
        "runtime_bindings": {"model_endpoint": inputs.model_endpoint, "bridge_implementation_sha256": _file_sha(bridge_implementation, "bridge implementation"), "bridge_runtime_tree_manifest_sha256": runtime_sha, "bridge_config_sha256": commitment(bridge_config), "scorer_implementation_sha256": scorer_sha, "node_executable_sha256": node_sha, "node_version": node_version, "python_executable_sha256": python_sha, "python_version": OFFICIAL_PYTHON_VERSION, "unicode_data_version": OFFICIAL_UNICODE_DATA_VERSION, "verifier_helper_sha256": _file_sha(inputs.verifier_helper_path, "verifier helper"), "verifier_package_lock_sha256": _file_sha(inputs.verifier_package_lock_path, "verifier package lock"), "verifier_runtime_bundle_sha256": OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256, "structured_output_qualification_sha256": qualification_sha, "subprocess_environment": _pinned_subprocess_environment()},
    }
    # The builder's last operation is a local contract check; callers never
    # receive a conveniently shaped but invalid B payload.
    validate_preregistration_value(value)
    return value


def validate_preregistration_value(value: Mapping[str, Any]) -> None:
    """Independently enforce the complete fixed-key/v4 preregistration shape."""

    expected = {"schema_version", "experiment_id", "protocol_version", "created_at", "status", "authority", "canonical_role", "predecessor_bindings", "forbidden_rescues", "scientific_question", "hypotheses", "testbed", "learning_boundary", "arms", "interventions", "parity_and_leakage", "diagnostic_readouts", "void_conditions", "single_attempt_policy", "required_before_measurement", "result_promotion", "measurement_gate", "preregistration_b_ci_gate", "source_a_ci", "runtime_bindings"}
    data = _keys(value, expected, "preregistration")
    if data["schema_version"] != PREREG_SCHEMA or data["experiment_id"] != "HSWM-DNRD-4" or data["protocol_version"] != "v4" or data["status"] != "FROZEN_AWAITING_SUCCESSFUL_PREREGISTRATION_B_CI_AND_FUTURE_PULSE":
        raise RegistrationRefusal("preregistration identity/status drifted")
    _date(data["created_at"])
    authority = _keys(data["authority"], {"broad_research_continuation_requested", "measurement_authorized_by_user_broad_continuation", "authorization_is_scientific_evidence", "measurement_requires_external_exact_hash_ratification_receipt", "measurement_requires_successful_preregistration_b_ci_receipt", "scientific_judgment_emitted", "external_governance_required"}, "preregistration.authority")
    if authority != {"broad_research_continuation_requested": True, "measurement_authorized_by_user_broad_continuation": True, "authorization_is_scientific_evidence": False, "measurement_requires_external_exact_hash_ratification_receipt": False, "measurement_requires_successful_preregistration_b_ci_receipt": True, "scientific_judgment_emitted": False, "external_governance_required": False}:
        raise RegistrationRefusal("preregistration authority drifted")
    gate = _keys(data["preregistration_b_ci_gate"], {"receipt_schema", "provider", "status", "conclusion", "minimum_lead_seconds", "selection_rule"}, "preregistration B CI gate")
    if gate != {"receipt_schema": PREREGISTRATION_B_CI_RECEIPT_SCHEMA, "provider": "GITHUB_ACTIONS", "status": "completed", "conclusion": "success", "minimum_lead_seconds": 900, "selection_rule": "EXACT_UNFILTERED_PUSH_MAIN_HEAD_SHA_WORKFLOW_LIST_TOTAL_COUNT_ONE_FIRST_ATTEMPT"}:
        raise RegistrationRefusal("preregistration B CI gate drifted")
    ci = _keys(data["source_a_ci"], {"receipt_sha256", "run_id", "head_sha", "conclusion"}, "source A CI")
    if type(ci["run_id"]) is not int or ci["run_id"] <= 0 or ci["conclusion"] != "success":
        raise RegistrationRefusal("source A CI contract drifted")
    _hex(ci["receipt_sha256"], "source A CI receipt SHA-256"); _hex(ci["head_sha"], "source A CI head", length=40)
    runtime = _keys(data["runtime_bindings"], {"model_endpoint", "bridge_implementation_sha256", "bridge_runtime_tree_manifest_sha256", "bridge_config_sha256", "scorer_implementation_sha256", "node_executable_sha256", "node_version", "python_executable_sha256", "python_version", "unicode_data_version", "verifier_helper_sha256", "verifier_package_lock_sha256", "verifier_runtime_bundle_sha256", "structured_output_qualification_sha256", "subprocess_environment"}, "runtime bindings")
    for key in ("bridge_implementation_sha256", "bridge_runtime_tree_manifest_sha256", "bridge_config_sha256", "scorer_implementation_sha256", "node_executable_sha256", "python_executable_sha256", "verifier_helper_sha256", "verifier_package_lock_sha256", "verifier_runtime_bundle_sha256", "structured_output_qualification_sha256"):
        _hex(runtime[key], f"runtime.{key}")
    if not isinstance(runtime["model_endpoint"], str) or not runtime["model_endpoint"].startswith(("http://", "https://")) or runtime["subprocess_environment"] != _pinned_subprocess_environment():
        raise RegistrationRefusal("runtime binding contract drifted")
    testbed, model = _keys(data["testbed"], {"family", "relationship_to_prior_p1", "development_streams", "training_calls_per_stream_maximum", "paired_heldout_probes_per_stream", "evaluation_arms", "evaluation_calls", "shared_learning_or_compiler_calls_maximum", "client_dispatched_generation_request_ceiling", "analysis_unit", "model", "freshness"}, "testbed"), None
    model = _keys(testbed["model"], {"served_model_id", "substitution_allowed", "temperature", "thinking", "max_output_tokens", "deployment_readback_required", "exact_weight_revision_attested", "exact_weight_identity_claimed"}, "testbed model")
    if (testbed["family"] != "REPEATED_CONTEXT_TABULAR_ROUTING_MECHANICS_V2" or testbed["development_streams"] != 4 or testbed["training_calls_per_stream_maximum"] != 8 or testbed["paired_heldout_probes_per_stream"] != 8 or testbed["evaluation_arms"] != 3 or testbed["evaluation_calls"] != 96 or testbed["shared_learning_or_compiler_calls_maximum"] != 32 or testbed["client_dispatched_generation_request_ceiling"] != 128 or model != {"served_model_id": MODEL_ID, "substitution_allowed": False, "temperature": 0, "thinking": False, "max_output_tokens": MAX_OUTPUT_TOKENS, "deployment_readback_required": True, "exact_weight_revision_attested": False, "exact_weight_identity_claimed": False}):
        raise RegistrationRefusal("testbed/model contract drifted")
    parity = _keys(data["parity_and_leakage"], {"same_served_model_id_and_chat_endpoint", "equal_client_dispatched_and_logical_requests", "equal_generation_limits_input_token_parity_not_claimed", "equal_candidate_evidence_universe", "all_active_payloads_within_byte_ceiling", "active_state_byte_ceiling", "full_fixed_rule_replay_numeric_payload_bytes_equal", "full_deranged_numeric_payload_byte_count_equal", "arm_labels_hidden_from_model", "fresh_process_recovery_observed", "distinct_arm_mount_ids", "evaluation_read_only_wrt_routing_observed", "pre_dispatch_readout_bound_before_model_response", "scorer_outcome_response_independent", "cache_hits_required", "private_route_binding_open_only_after_response_seal", "compiler_input_audit", "canary"}, "parity")
    required_true = {key for key in parity if key not in {"active_state_byte_ceiling", "cache_hits_required", "compiler_input_audit", "canary"}}
    if any(parity[key] is not True for key in required_true) or parity["active_state_byte_ceiling"] != 16_384 or parity["cache_hits_required"] != 0:
        raise RegistrationRefusal("parity contract drifted")
    boundary = {"canonical_role": data["canonical_role"], "predecessor_bindings": data["predecessor_bindings"], "forbidden_rescues": data["forbidden_rescues"], "scientific_question": data["scientific_question"], "hypotheses": data["hypotheses"], "testbed_claims": {key: testbed[key] for key in ("relationship_to_prior_p1", "analysis_unit", "freshness")}, "learning_boundary": data["learning_boundary"], "arms": dict(data["arms"]), "interventions": data["interventions"], "parity_claims": {key: parity[key] for key in ("compiler_input_audit", "canary")}, "diagnostic_readouts": data["diagnostic_readouts"], "void_conditions": data["void_conditions"], "single_attempt_policy": data["single_attempt_policy"], "required_before_measurement": data["required_before_measurement"], "result_promotion": data["result_promotion"], "measurement_gate": data["measurement_gate"]}
    if boundary != PREREG_CLAIM_BOUNDARY:
        raise RegistrationRefusal("scientific claim boundary drifted")


def write_preregistration(*, inputs: RegistrationInputs, output: Path) -> str:
    """Write canonical no-LF bytes once; output must be the planned new B path."""

    try:
        relative = output.resolve().relative_to(inputs.repo_root.resolve())
    except ValueError as error:
        raise RegistrationRefusal("preregistration output must reside in the Source-A checkout") from error
    _relative(relative.as_posix(), "preregistration output path")
    if output.exists() or output.is_symlink():
        raise RegistrationRefusal("refusing to overwrite preregistration output")
    _plain_directory(output.parent, "preregistration output parent")
    raw = canonical_json(build_preregistration(inputs))
    output.write_bytes(raw)
    return _sha(raw)


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m _research.dnrd.register", description="Offline deterministic DNRD-4 preregistration-B builder; no network, model, config, or commit.")
    for name in ("repo-root", "source-ci-receipt", "runtime-manifest", "qualification", "bridge-runtime-root", "bridge-implementation", "bridge-state-root", "scorer-implementation", "node-executable", "python-executable", "verifier-helper", "verifier-package-lock", "verifier-runtime-bundle", "output"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--source-manifest-path", required=True)
    parser.add_argument("--model-endpoint", required=True)
    parser.add_argument("--created-at", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        inputs = RegistrationInputs(repo_root=_path(args.repo_root), source_manifest_path=args.source_manifest_path, source_ci_receipt_path=_path(args.source_ci_receipt), runtime_manifest_path=_path(args.runtime_manifest), qualification_path=_path(args.qualification), model_endpoint=args.model_endpoint, bridge_runtime_root=_path(args.bridge_runtime_root), bridge_implementation_path=_path(args.bridge_implementation), bridge_state_root=_path(args.bridge_state_root), scorer_implementation_path=_path(args.scorer_implementation), node_executable_path=_path(args.node_executable), python_executable_path=_path(args.python_executable), verifier_helper_path=_path(args.verifier_helper), verifier_package_lock_path=_path(args.verifier_package_lock), verifier_runtime_bundle_path=_path(args.verifier_runtime_bundle), created_at=args.created_at)
        digest = write_preregistration(inputs=inputs, output=_path(args.output))
    except (OSError, RegistrationRefusal, subprocess.SubprocessError) as error:
        print(f"DNRD-4 registration refused: {error}", file=sys.stderr)
        return 2
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
