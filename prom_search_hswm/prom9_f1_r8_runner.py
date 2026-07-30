#!/usr/bin/env python3
"""Gold-blind HSWM F1 manifest-v3/suite-v4 runner and terminal finalizer.

The runner accepts only a pre-call self-hashed execution lock and never has a
gold option.  It writes a private draft after all item runs are durable.  A
separate finalization step binds an independently exported terminal SQLite
transport package, producing the suite v4 consumed by the preregistered judge.
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
from collections.abc import Mapping, Sequence
from urllib import error as urllib_error
from urllib import request as urllib_request

from prom_search_hswm.hswm_f1_durable_transport import (
    DURABLE_CALL_SCHEMA,
    DurableLedgerIntegrityError,
    DurableSpoolJSONPort,
    SQLiteF1CallLedger,
)
from prom_search_hswm.hswm_call_receipt import (
    CALL_RECEIPT_SCHEMA,
    ModelCallV1,
)
from prom_search_hswm.hswm_function_network import (
    EvidenceCandidateV1,
    F1_ARMS,
    FunctionNetworkItemV1,
    RUN_SCHEMA,
    run_item,
)
from prom_search_hswm.hswm_function_registry import (
    REGISTRY_SCHEMA,
    FunctionRegistryV1,
    build_registry,
    build_registry_from_protocol,
)
from prom_search_hswm.hswm_result_spool import (
    ModelDeploymentBinding,
    SpoolIntegrityError,
    SQLiteResultSpool,
    load_model_deployment_binding,
    normalize_upstream_endpoint,
)
from prom_search_hswm.hswm_token_meter import QwenBpeMeter, TokenMeter
from prom_search_hswm.hswm_result_spool import (
    SPOOL_IDENTITY_ROUTE,
    SPOOL_IDENTITY_SCHEMA,
    SPOOL_SCHEMA,
)
from prom_search_hswm.hswm_typed_ports import (
    canonical_json,
    canonical_sha256,
    output_schema_sha256,
    port_digest,
    validate_port,
)
from prom_search_hswm.prom9_f1_envelope import (
    check_tokenizer_identity,
    enforce_projection,
    envelope_spec,
    validate_token_envelope,
)
from prom_search_hswm.prom9_f1_r8_environment import (
    R8_DEPENDENCY_NAMES,
    load_private_receipt,
    r8_dependency_paths,
    verify_r8_preimage_bundle,
)
from prom_search_hswm.prom9_f1_r8_private_output import (
    canonical_output_path,
    reserve_private_outputs,
)
from prom_search_hswm.prom9_f1_r8_transport_audit import (
    FrozenSQLiteReadOnly,
    RESUME_PREFIX_SCHEMA,
    TransportAuditRefusal,
    exact_schema_readback,
    export_resume_prefix,
    open_frozen_sqlite_read_only,
    private_database_identity,
)
from prom_search_hswm.prom9_f1_prior_exposure import (
    F1_R8_A3_SUCCESSOR_RUN_ID,
    verify_aborted_attempt_exposure_receipt,
    verify_f1_r8_successor_exposure_set,
    verify_forbidden_exposure_union,
)
from prom_search_hswm.prom9_protocol import DEFAULT_PROTOCOL
from prom_search_hswm.prom_f1_function_network import (
    _arm_overrides,
)


MANIFEST_SCHEMA = "hswm-prom9-f1-manifest/v3"
SUITE_DRAFT_SCHEMA = "hswm-prom9-f1-suite-draft/v4"
SUITE_SCHEMA = "hswm-prom9-f1-suite/v4"
EXECUTION_LOCK_SCHEMA = "hswm-prom9-f1-r8-execution-lock/v4"
SEALED_LOCK_SCHEMA = "hswm-prom9-f1-r8-measurement-lock/v6"
SEALED_LOCK_PURPOSE = "CONFIRMATORY_R8_TRY3_MEASUREMENT"
SEALED_EXPERIMENT_TAG = "Q-f1-actual-compute-parity-try3"
SEALED_CLOSES_QUESTION = "Q-f1-actual-compute-parity"
SEALED_RUN_ID = "f1-2wiki-sealed-r8-try3"
DEVELOPMENT_RUN_ID = F1_R8_A3_SUCCESSOR_RUN_ID
HISTORICAL_DERIVATION_DEVELOPMENT_RUN_ID = "f1-2wiki-development-r8-try3-a2"
HISTORICAL_SELECTION_SCHEMA = "hswm-prom9-f1-r8-cohort-selection/v3"
SUCCESSOR_SELECTION_SCHEMA = "hswm-prom9-f1-r8-cohort-selection/v4"
TRANSPORT_SCHEMA = "hswm-f1-durable-call-ledger/v1"
TRANSPORT_BINDINGS_SCHEMA = "hswm-prom9-f1-r8-transport-bindings/v1"
GENESIS_SCHEMA = "hswm-prom9-f1-r8-transport-genesis/v1"
SPOOL_PREFLIGHT_SCHEMA = "hswm-prom9-f1-r8-spool-endpoint-preflight/v2"
PREREGISTRATION_ARTIFACT_SCHEMA = (
    "hswm-prom9-f1-r8-preregistration-artifact/v4"
)
PREREGISTRATION_READBACK_SCHEMA = "hswm-prom9-f1-r8-prereg-readback/v1"
GENERATION_POLICY = {
    "temperature": 0,
    "enable_thinking": False,
    "structured_output_backend": "json_schema",
}
PREDICTED_OUTCOME = {
    "metric": "f1_min_paired_component_cluster_bootstrap_lcb",
    "operator": ">",
    "threshold": 0,
    "claim": "all_four_frozen_control_lcbs_strictly_positive",
}
FALSIFICATION_CONDITION = {
    "metric": "f1_min_paired_component_cluster_bootstrap_lcb",
    "operator": "<=",
    "threshold": 0,
    "trigger": "at_least_one_frozen_control_lcb_nonpositive",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_DEPENDENCY_FILES = R8_DEPENDENCY_NAMES
MANIFEST_PREREGISTRATION_UNFROZEN = "0" * 64
_DEVELOPMENT_LOCK_FIELDS = {
    "schema_version", "purpose", "run_id", "mode", "manifest_sha256",
    "preregistration_artifact_sha256", "selection_receipt_sha256",
    "prior_exposure_receipt_sha256",
    "aborted_attempt_exposure_receipt_sha256",
    "public_source_receipt_sha256",
    "gold_source_receipt_sha256", "gold_sha256", "evaluator_receipt_sha256",
    "db_genesis_receipt_sha256", "environment_receipt_sha256",
    "dependency_receipt_sha256",
    "environment_dependency_compatibility_root_sha256",
    "environment_dependency_bundle_sha256", "hswm_commit",
    "result_contract_sha256", "judge_core_sha256", "judge_core_file_sha256",
    "model", "model_revision", "upstream_endpoint",
    "deployment_receipt_sha256", "deployment_id", "served_model",
    "protocol_sha256",
    "registries_root_sha256", "token_envelope_sha256",
    "token_envelope_derivation_receipt_sha256",
    "generation_policy_sha256", "cohort_root_sha256",
    "candidate_universe_root_sha256", "forbidden_prior_item_ids",
    "forbidden_prior_source_entity_ids", "forbidden_prior_component_ids",
    "execution_policy", "gates", "lock_sha256",
}
_SEALED_LOCK_FIELDS = _DEVELOPMENT_LOCK_FIELDS | {
    "experiment_tag", "closes_question",
}
_EXECUTION_POLICY_FIELDS = {
    "endpoint", "max_workers", "timeout_seconds", "max_delivery_attempts",
    "spool_token_env",
}
_GATE_FIELDS = {
    "expected_items", "expected_arms", "expected_item_runs", "expected_calls",
    "per_call_input_caps", "per_call_output_caps",
    "total_input_tokens_per_run", "total_allowed_output_tokens_per_run",
    "token_spread_max",
}
_GENESIS_FIELDS = {
    "schema_version", "run_id", "attempt_integrity", "spool_integrity",
    "attempt_journal_mode", "attempt_audit_connection_synchronous",
    "spool_journal_mode", "spool_audit_connection_synchronous",
    "attempt_user_version", "spool_user_version", "attempt_schema_sha256",
    "spool_schema_sha256", "attempt_db_identity", "spool_db_identity",
    "call_count", "item_run_count", "attempt_event_count", "spool_call_count",
    "genesis_sha256",
}
_LIVE_ATTEMPT_AUDIT_FIELDS = {
    "schema_version", "journal_mode", "synchronous", "event_chain_tip_sha256",
    "call_count", "status_counts", "accepted_call_root_sha256",
    "spool_binding_root_sha256", "item_run_count", "item_run_root_sha256",
    "audit_sha256",
}
_SPOOL_AUDIT_FIELDS = {
    "schema_version", "journal_mode", "synchronous", "call_count",
    "status_counts", "completed_root_sha256", "audit_sha256",
}
_SPOOL_IDENTITY_FIELDS = {
    "schema_version", "normalized_upstream_endpoint",
    "deployment_receipt_sha256", "deployment_id", "served_model",
    "model_revision", "db_identity", "audit", "identity_sha256",
}
_SPOOL_PREFLIGHT_FIELDS = {
    "schema_version", "run_id", "execution_lock_sha256", "db_genesis_sha256",
    "endpoint", "upstream_endpoint", "deployment_receipt_sha256",
    "deployment_id", "served_model", "model_revision", "endpoint_identity",
    "preflight_sha256",
}
_RESUME_PREFIX_FIELDS = {
    "schema_version", "run_id", "db_genesis_sha256", "attempt_integrity",
    "spool_integrity", "attempt_db_identity", "spool_db_identity",
    "ordered_job_root_sha256", "job_count", "max_workers",
    "frontier_batch", "call_positions", "call_count", "item_run_count",
    "attempt_event_count", "spool_call_count", "event_chain_tip_sha256",
    "attempt_event_root_sha256", "attempt_live_audit", "spool_live_audit",
    "zero_count_genesis", "resume_prefix_sha256",
}
_RESUME_CALL_POSITION_FIELDS = {
    "job_ordinal", "item_id", "arm_id", "call_indices",
    "item_run_committed",
}
_TRANSPORT_BINDING_FIELDS = {
    "schema_version", "run_id", "db_genesis_sha256", "attempt_integrity",
    "spool_integrity", "attempt_journal_mode",
    "attempt_audit_connection_synchronous", "spool_journal_mode",
    "spool_audit_connection_synchronous", "attempt_user_version",
    "spool_user_version", "attempt_schema_sha256", "spool_schema_sha256",
    "attempt_db_identity", "spool_db_identity", "call_count", "item_run_count",
    "attempt_event_count", "spool_call_count", "attempt_status_counts",
    "spool_status_counts", "spool_unknown_count", "identity_conflict_count",
    "event_chain_tip_sha256", "accepted_call_root_sha256",
    "accepted_call_export_root_sha256", "accepted_call_auxiliary_root_sha256",
    "spool_binding_root_sha256", "spool_preimage_root_sha256",
    "item_run_root_sha256", "item_run_preimage_root_sha256",
    "attempt_event_root_sha256", "accepted_calls",
    "accepted_call_auxiliary_preimages", "spool_bindings",
    "spool_call_preimages", "item_run_bindings", "item_run_preimages",
    "attempt_events", "bindings_sha256",
}
_DRAFT_FIELDS = {
    "schema_version", "run_id", "mode", "manifest_sha256", "model",
    "model_revision", "upstream_endpoint", "deployment_receipt_sha256",
    "deployment_id", "served_model", "token_tolerance", "state_capacity_bytes",
    "state_bytes_by_arm", "preregistration_artifact_sha256",
    "preregistration_readback_sha256", "anchored_judge_file_sha256",
    "measurement_lock_sha256", "result_contract_sha256",
    "environment_receipt_sha256", "dependency_receipt_sha256",
    "environment_dependency_compatibility_root_sha256",
    "environment_dependency_bundle_sha256", "hswm_commit",
    "db_genesis_receipt_sha256", "protocol_sha256",
    "registries_root_sha256", "token_envelope_sha256",
    "token_envelope_derivation_receipt_sha256", "cohort_root_sha256",
    "candidate_universe_root_sha256", "generation_policy",
    "generation_policy_sha256", "token_envelope", "envelope_projection",
    "token_parity", "execution_policy", "execution_gates", "max_workers",
    "spool_identity_preflight", "spool_identity_preflight_sha256",
    "registries", "pre_call_transport_audit", "live_transport_audit",
    "item_runs", "gold_opened", "scientific_verdict_emitted",
    "draft_receipt_sha256",
}
_SUITE_FIELDS = (
    _DRAFT_FIELDS
    - {"schema_version", "pre_call_transport_audit", "live_transport_audit", "draft_receipt_sha256"}
    | {"schema_version", "transport_audit", "transport_bindings", "suite_receipt_sha256"}
)
_FUNCTION_IDS = (
    "QF_QUERY_COMPILER", "BF_BOND_PROPOSER", "AF_ANSWER_SYNTHESIZER",
)
_FUNCTION_FIELDS = {
    "function_id", "model", "model_revision", "input_type", "output_type",
    "prompt", "prompt_sha256",
}
_REGISTRY_FIELDS = {
    "schema_version", "protocol_sha256", "functions", "registry_sha256",
}
_CALL_RECEIPT_FIELDS = {
    "schema_version", "physical_call_id", "run_id", "arm_id", "item_id",
    "call_index", "function_id", "model", "model_revision", "prompt_sha256",
    "input_type", "input_port_sha256", "input_payload", "output_type",
    "output_port_sha256", "output_payload", "allowed_output_tokens",
    "input_tokens", "output_tokens", "latency_ms", "cache_status", "retries",
    "receipt_sha256",
}
_ITEM_RUN_FIELDS = {
    "schema_version", "run_id", "arm_id", "item_id", "registry_sha256",
    "candidate_universe_sha256", "calls", "answer", "selected_bond_ids",
    "total_input_tokens", "total_output_tokens", "total_allowed_output_tokens",
    "persistent_state_bytes", "run_receipt_sha256",
}
_PREREGISTRATION_ARTIFACT_FIELDS = {
    "schema_version", "purpose", "experiment_tag", "closes_question", "run_id",
    "mode", "hswm_commit", "model", "model_revision", "metric", "baseline",
    "direction", "noise_band", "credence", "bootstrap", "gates",
    "predicted_outcome", "falsification_condition",
    "manifest_core_sha256", "judge_core_sha256", "result_contract_sha256",
    "measurement_lock_schema_sha256", "result_bundle_builder_sha256",
    "power_operating_characteristic_receipt_sha256",
    "calibration_receipt_sha256", "selection_receipt_sha256",
    "prior_exposure_receipt_sha256",
    "aborted_attempt_exposure_receipt_sha256",
    "public_source_receipt_sha256",
    "gold_source_receipt_sha256", "gold_sha256", "evaluator_receipt_sha256",
    "db_genesis_receipt_sha256", "environment_receipt_sha256",
    "dependency_receipt_sha256",
    "environment_dependency_compatibility_root_sha256",
    "environment_dependency_bundle_sha256", "protocol_sha256",
    "registries_root_sha256", "token_envelope_sha256",
    "token_envelope_derivation_receipt_sha256",
    "generation_policy_sha256", "cohort_root_sha256",
    "candidate_universe_root_sha256", "forbidden_prior_item_ids",
    "forbidden_prior_source_entity_ids", "forbidden_prior_component_ids",
    "preregistration_artifact_sha256",
}
_PREREGISTRATION_READBACK_FIELDS = {
    "schema_version", "purpose", "experiment_tag", "closes_question", "run_id",
    "measurement_lock_sha256", "preregistration_artifact_sha256",
    "external_prediction_receipt_sha256", "external_record_identity",
    "canonical_readback_sha256", "pred_script_sha256",
    "anchored_judge_file_sha256", "judge_core_sha256",
    "result_contract_sha256", "receipt_sha256",
}
_DERIVATION_INPUT_FIELDS = {
    "receipt", "selection_receipt", "historical_manifest",
    "validation_receipt", "projected_outputs_receipt", "source_suite",
    "protocol", "file_sha256s",
}
_DERIVATION_FILE_FIELDS = {
    "selection_receipt", "historical_manifest", "validation_receipt",
    "projected_outputs_receipt", "source_suite", "protocol",
}
_DERIVATION_RECEIPT_FIELDS = {
    "schema_version", "derivation_policy", "selection_receipt_sha256",
    "historical_token_envelope_sha256",
    "historical_input_caps_used_as_floor", "model", "model_revision",
    "protocol_sha256", "registries_root_sha256",
    "token_meter_validation_receipt_sha256", "token_meter",
    "projected_outputs_receipt_sha256", "source_suite_receipt_sha256",
    "development", "confirmatory", "per_call_input_caps",
    "per_call_output_caps", "total_input_tokens_per_run",
    "total_allowed_output_tokens_per_run", "projection_slack_tokens",
    "token_tolerance", "token_envelope_sha256", "gold_inputs_read",
    "model_calls", "receipt_sha256",
}
_DERIVATION_COHORT_FIELDS = {
    "run_id", "items", "components", "minimum_input_caps",
    "projection_sha256", "projected_spread",
}
_EVENT_GENESIS = "0" * 64
_EVENT_TRANSITIONS = {
    "PREPARED": (None,),
    "SENT": ("PREPARED", "DELIVERY_AMBIGUOUS", "SENT"),
    "DELIVERY_AMBIGUOUS": ("SENT",),
    "RAW_COMPLETE": ("SENT",),
    "ENVELOPE_VALID": ("RAW_COMPLETE",),
    "SCHEMA_VALID": ("ENVELOPE_VALID",),
    "ACCEPTED": ("SCHEMA_VALID",),
}


class R8RunnerRefusal(RuntimeError):
    """No model call or suite promotion is authorized."""


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise R8RunnerRefusal(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                R8RunnerRefusal(f"non-finite JSON number in {label}")
            ),
        )
    except R8RunnerRefusal:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise R8RunnerRefusal(f"cannot read {label}: {error}") from error
    if not isinstance(value, dict):
        raise R8RunnerRefusal(f"{label} must be an object")
    return value


def read_stable_bytes(
    path: Path,
    label: str,
    *,
    max_bytes: int = 64 * 1024 * 1024,
) -> tuple[bytes, str]:
    """Capture one bounded regular file and its digest through one stable FD."""

    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 0:
        raise R8RunnerRefusal("stable-read byte bound must be a nonnegative integer")
    target = Path(path)
    try:
        before = target.lstat()
    except OSError as error:
        raise R8RunnerRefusal(f"cannot stat {label}") from error
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise R8RunnerRefusal(f"{label} must be a regular non-symlink file")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags)
    except OSError as error:
        raise R8RunnerRefusal(f"cannot open {label}") from error
    payload = bytearray()
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
        ):
            raise R8RunnerRefusal(f"{label} changed before reading")
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            payload.extend(block)
            if len(payload) > max_bytes:
                raise R8RunnerRefusal(f"{label} exceeds the stable-read byte bound")
        after_fd = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after_path = target.lstat()
    except OSError as error:
        raise R8RunnerRefusal(f"cannot restat {label}") from error
    identity = lambda value: (  # noqa: E731 - compact immutable projection
        value.st_dev, value.st_ino, value.st_mode, value.st_size,
        value.st_mtime_ns, value.st_ctime_ns,
    )
    if (
        identity(before) != identity(after_fd)
        or identity(before) != identity(after_path)
        or len(payload) != before.st_size
    ):
        raise R8RunnerRefusal(f"{label} changed while reading")
    raw = bytes(payload)
    return raw, hashlib.sha256(raw).hexdigest()


def read_stable_json(path: Path, label: str) -> tuple[dict[str, object], str]:
    """Parse one JSON object from the exact bytes captured by ``read_stable_bytes``."""

    raw, digest = read_stable_bytes(path, label)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                R8RunnerRefusal(f"non-finite JSON number in {label}")
            ),
        )
    except R8RunnerRefusal:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise R8RunnerRefusal(f"cannot parse {label}") from error
    if not isinstance(value, dict):
        raise R8RunnerRefusal(f"{label} must be an object")
    return value, digest


def write_private_once(path: Path, value: Mapping[str, object]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    temporary = destination.with_name(f".{destination.name}.partial-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as error:
            raise R8RunnerRefusal(f"refusing to replace output: {destination}") from error
        directory = os.open(str(destination.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise R8RunnerRefusal(f"{label} must be a lowercase SHA-256")
    return value


def _positive(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise R8RunnerRefusal(f"{label} must be a positive integer")
    return value


def _nonnegative(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise R8RunnerRefusal(f"{label} must be a non-negative integer")
    return value


def _self_hash(value: Mapping[str, object], field: str, label: str) -> str:
    unsigned = dict(value)
    declared = unsigned.pop(field, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise R8RunnerRefusal(f"{label} self-hash drifted")
    return declared


def manifest_core_sha256(manifest: Mapping[str, object]) -> str:
    """Hash the final manifest with only its preregistration back-edge unfrozen."""

    if "preregistration_artifact_sha256" not in manifest:
        raise R8RunnerRefusal("manifest preregistration field is absent")
    core = dict(manifest)
    core["preregistration_artifact_sha256"] = MANIFEST_PREREGISTRATION_UNFROZEN
    return canonical_sha256(core)


def _database_identity_value(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "resolved_path", "st_dev", "st_ino",
    }:
        raise R8RunnerRefusal(f"{label} database identity shape drifted")
    path = value.get("resolved_path")
    device = value.get("st_dev")
    inode = value.get("st_ino")
    if (
        not isinstance(path, str)
        or not path
        or isinstance(device, bool)
        or not isinstance(device, int)
        or device < 0
        or isinstance(inode, bool)
        or not isinstance(inode, int)
        or inode < 1
    ):
        raise R8RunnerRefusal(f"{label} database identity values drifted")
    return dict(value)


def _validate_execution_policy_value(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _EXECUTION_POLICY_FIELDS:
        raise R8RunnerRefusal("execution policy fields drifted")
    endpoint = value.get("endpoint")
    max_workers = value.get("max_workers")
    timeout = value.get("timeout_seconds")
    attempts = value.get("max_delivery_attempts")
    token_env = value.get("spool_token_env")
    if (
        not isinstance(endpoint, str)
        or not endpoint.startswith(("http://", "https://"))
        or isinstance(max_workers, bool)
        or not isinstance(max_workers, int)
        or not 1 <= max_workers <= 8
        or isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not float(timeout) > 0
        or isinstance(attempts, bool)
        or not isinstance(attempts, int)
        or attempts < 1
        or not isinstance(token_env, str)
        or not token_env.strip()
    ):
        raise R8RunnerRefusal("execution policy values are invalid")
    return dict(value)


def _validate_deployment_binding(
    execution_lock: Mapping[str, object],
    binding: ModelDeploymentBinding,
) -> None:
    expected = {
        "upstream_endpoint": binding.upstream_endpoint,
        "deployment_receipt_sha256": binding.deployment_receipt_sha256,
        "deployment_id": binding.deployment_id,
        "served_model": binding.served_model,
        "model_revision": binding.model_revision,
    }
    if any(execution_lock.get(key) != value for key, value in expected.items()):
        raise R8RunnerRefusal(
            "live model deployment differs from the frozen execution lock"
        )
    if execution_lock.get("model") != binding.served_model:
        raise R8RunnerRefusal("manifest model differs from the served model")
    try:
        normalize_upstream_endpoint(binding.upstream_endpoint)
    except Exception as error:
        raise R8RunnerRefusal("frozen upstream endpoint is not canonical") from error


def _deployment_binding_from_lock(
    execution_lock: Mapping[str, object],
) -> ModelDeploymentBinding:
    try:
        binding = ModelDeploymentBinding(
            upstream_endpoint=str(execution_lock.get("upstream_endpoint", "")),
            deployment_receipt_sha256=str(
                execution_lock.get("deployment_receipt_sha256", "")
            ),
            deployment_id=str(execution_lock.get("deployment_id", "")),
            served_model=str(execution_lock.get("served_model", "")),
            model_revision=str(execution_lock.get("model_revision", "")),
        )
    except Exception as error:
        raise R8RunnerRefusal("execution-lock deployment binding is invalid") from error
    _validate_deployment_binding(execution_lock, binding)
    return binding


def _validate_prior_list(
    value: object, label: str, *, sha_values: bool
) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise R8RunnerRefusal(f"{label} must be a string array")
    if value != sorted(value) or len(value) != len(set(value)):
        raise R8RunnerRefusal(f"{label} must be sorted and unique")
    if sha_values:
        for item in value:
            _sha(item, label)
    return list(value)


def _validate_lock_gates(
    value: object,
    *,
    item_count: int,
    token_envelope: Mapping[str, object],
    token_tolerance: int,
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _GATE_FIELDS:
        raise R8RunnerRefusal("execution-lock gate shape drifted")
    input_caps = token_envelope.get("per_call_input_caps")
    output_caps = token_envelope.get("per_call_output_caps")
    if not isinstance(input_caps, Mapping) or not isinstance(output_caps, Mapping):
        raise R8RunnerRefusal("token envelope caps are absent")
    expected = {
        "expected_items": item_count,
        "expected_arms": len(F1_ARMS),
        "expected_item_runs": item_count * len(F1_ARMS),
        "expected_calls": item_count * len(F1_ARMS) * len(_FUNCTION_IDS),
        "per_call_input_caps": dict(input_caps),
        "per_call_output_caps": dict(output_caps),
        "total_input_tokens_per_run": sum(int(item) for item in input_caps.values()),
        "total_allowed_output_tokens_per_run": sum(
            int(item) for item in output_caps.values()
        ),
        "token_spread_max": token_tolerance,
    }
    if dict(value) != expected:
        raise R8RunnerRefusal("execution-lock gates differ from the manifest")
    return dict(value)


def _validate_transport_genesis_receipt(
    value: Mapping[str, object],
    *,
    run_id: str,
    expected_sha256: str | None = None,
) -> str:
    if (
        set(value) != _GENESIS_FIELDS
        or value.get("schema_version") != GENESIS_SCHEMA
        or value.get("run_id") != run_id
    ):
        raise R8RunnerRefusal("transport genesis identity or schema drifted")
    declared = _self_hash(value, "genesis_sha256", "transport genesis")
    if expected_sha256 is not None and declared != expected_sha256:
        raise R8RunnerRefusal("transport genesis differs from its frozen binding")
    count_fields = (
        "call_count",
        "item_run_count",
        "attempt_event_count",
        "spool_call_count",
    )
    if (
        value.get("attempt_integrity") != "ok"
        or value.get("spool_integrity") != "ok"
        or not isinstance(value.get("attempt_journal_mode"), str)
        or not isinstance(value.get("spool_journal_mode"), str)
        or str(value.get("attempt_journal_mode")).casefold() != "wal"
        or str(value.get("spool_journal_mode")).casefold() != "wal"
        or value.get("attempt_audit_connection_synchronous") != "2"
        or value.get("spool_audit_connection_synchronous") != "2"
        or type(value.get("attempt_user_version")) is not int
        or type(value.get("spool_user_version")) is not int
        or value.get("attempt_user_version") != 1
        or value.get("spool_user_version") != 1
        or any(
            type(value.get(field)) is not int or value.get(field) != 0
            for field in count_fields
        )
    ):
        raise R8RunnerRefusal(
            "transport genesis is not empty WAL with FULL audit connections"
        )
    _sha(value.get("attempt_schema_sha256"), "genesis attempt schema")
    _sha(value.get("spool_schema_sha256"), "genesis spool schema")
    attempt_identity = _database_identity_value(
        value.get("attempt_db_identity"), "attempt ledger"
    )
    spool_identity = _database_identity_value(
        value.get("spool_db_identity"), "result spool"
    )
    if (
        attempt_identity["st_dev"], attempt_identity["st_ino"]
    ) == (
        spool_identity["st_dev"], spool_identity["st_ino"]
    ):
        raise R8RunnerRefusal("transport genesis aliases one database inode")
    return declared


def _validate_live_attempt_audit(
    value: object,
    *,
    expected_calls: int,
    expected_item_runs: int,
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _LIVE_ATTEMPT_AUDIT_FIELDS:
        raise R8RunnerRefusal("live attempt audit shape drifted")
    _self_hash(value, "audit_sha256", "live attempt audit")
    expected_status = {} if expected_calls == 0 else {"ACCEPTED": expected_calls}
    if (
        value.get("schema_version") != TRANSPORT_SCHEMA
        or str(value.get("journal_mode")).casefold() != "wal"
        or value.get("synchronous") != 2
        or value.get("call_count") != expected_calls
        or value.get("item_run_count") != expected_item_runs
        or value.get("status_counts") != expected_status
    ):
        raise R8RunnerRefusal("live attempt audit durability or counts drifted")
    for field in (
        "event_chain_tip_sha256", "accepted_call_root_sha256",
        "spool_binding_root_sha256", "item_run_root_sha256",
    ):
        _sha(value.get(field), f"live attempt audit {field}")
    if expected_calls == 0 and any(
        value.get(field) != canonical_sha256([])
        for field in (
            "accepted_call_root_sha256", "spool_binding_root_sha256",
            "item_run_root_sha256",
        )
    ):
        raise R8RunnerRefusal("pre-call attempt audit is not empty")
    if expected_calls == 0 and value.get("event_chain_tip_sha256") != _EVENT_GENESIS:
        raise R8RunnerRefusal("pre-call attempt event chain is not at genesis")
    return dict(value)


def _validate_spool_audit(
    value: object, *, expected_calls: int = 0
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _SPOOL_AUDIT_FIELDS:
        raise R8RunnerRefusal("result-spool audit shape drifted")
    _self_hash(value, "audit_sha256", "result-spool audit")
    _nonnegative(expected_calls, "expected result-spool calls")
    expected_status = {} if expected_calls == 0 else {"COMPLETE": expected_calls}
    if (
        value.get("schema_version") != SPOOL_SCHEMA
        or str(value.get("journal_mode")).casefold() != "wal"
        or value.get("synchronous") != 2
        or value.get("call_count") != expected_calls
        or value.get("status_counts") != expected_status
    ):
        raise R8RunnerRefusal("result-spool live audit durability or counts drifted")
    _sha(value.get("completed_root_sha256"), "result-spool completed root")
    if (
        expected_calls == 0
        and value.get("completed_root_sha256") != canonical_sha256([])
    ):
        raise R8RunnerRefusal("result-spool preflight audit is not empty")
    return dict(value)


def _resume_job_values(
    items: Sequence[FunctionNetworkItemV1],
) -> list[tuple[str, str]]:
    return [
        (item.item_id, arm)
        for item in sorted(items, key=lambda value: value.item_id)
        for arm in F1_ARMS
    ]


def _validate_resume_prefix(
    value: object,
    *,
    run_id: str,
    db_genesis_sha256: str,
    ordered_jobs: Sequence[tuple[str, str]],
    max_workers: int,
) -> dict[str, object]:
    if (
        not isinstance(value, Mapping)
        or set(value) != _RESUME_PREFIX_FIELDS
        or value.get("schema_version") != RESUME_PREFIX_SCHEMA
        or value.get("run_id") != run_id
    ):
        raise R8RunnerRefusal("resume prefix schema or run identity drifted")
    _self_hash(value, "resume_prefix_sha256", "resume prefix")
    if value.get("db_genesis_sha256") != db_genesis_sha256:
        raise R8RunnerRefusal("resume prefix differs from frozen DB genesis")
    if value.get("attempt_integrity") != "ok" or value.get("spool_integrity") != "ok":
        raise R8RunnerRefusal("resume prefix database integrity drifted")
    _database_identity_value(value.get("attempt_db_identity"), "attempt ledger")
    _database_identity_value(value.get("spool_db_identity"), "result spool")
    jobs = list(ordered_jobs)
    if not jobs or len(set(jobs)) != len(jobs):
        raise R8RunnerRefusal("canonical resume job universe is invalid")
    job_values = [
        {"item_id": item_id, "arm_id": arm_id}
        for item_id, arm_id in jobs
    ]
    if (
        value.get("job_count") != len(jobs)
        or value.get("ordered_job_root_sha256") != canonical_sha256(job_values)
        or value.get("max_workers") != max_workers
    ):
        raise R8RunnerRefusal(
            "resume prefix job universe or worker width differs from the frozen run"
        )
    call_count = _nonnegative(value.get("call_count"), "resume call count")
    item_run_count = _nonnegative(
        value.get("item_run_count"), "resume item-run count"
    )
    event_count = _nonnegative(
        value.get("attempt_event_count"), "resume event count"
    )
    spool_count = _nonnegative(
        value.get("spool_call_count"), "resume spool count"
    )
    if spool_count != call_count:
        raise R8RunnerRefusal("resume attempt/spool call counts conflict")
    attempt_audit = _validate_live_attempt_audit(
        value.get("attempt_live_audit"),
        expected_calls=call_count,
        expected_item_runs=item_run_count,
    )
    spool_audit = _validate_spool_audit(
        value.get("spool_live_audit"), expected_calls=call_count
    )
    if (
        value.get("event_chain_tip_sha256")
        != attempt_audit["event_chain_tip_sha256"]
    ):
        raise R8RunnerRefusal("resume event tip differs from live attempt audit")
    _sha(value.get("attempt_event_root_sha256"), "resume event root")
    positions = value.get("call_positions")
    if not isinstance(positions, list):
        raise R8RunnerRefusal("resume call positions are absent")
    job_ordinal = {job: ordinal for ordinal, job in enumerate(jobs)}
    seen: set[tuple[str, str]] = set()
    total_calls = 0
    committed_runs = 0
    observed_ordinals: list[int] = []
    for position in positions:
        if not isinstance(position, Mapping) or set(position) != _RESUME_CALL_POSITION_FIELDS:
            raise R8RunnerRefusal("resume call-position shape drifted")
        item_id = position.get("item_id")
        arm_id = position.get("arm_id")
        job = (item_id, arm_id)
        ordinal = position.get("job_ordinal")
        indices = position.get("call_indices")
        committed = position.get("item_run_committed")
        if (
            not isinstance(item_id, str)
            or not isinstance(arm_id, str)
            or job not in job_ordinal
            or job in seen
            or type(ordinal) is not int
            or ordinal != job_ordinal[job]
            or not isinstance(indices, list)
            or any(type(index) is not int for index in indices)
            or indices != list(range(1, len(indices) + 1))
            or not 1 <= len(indices) <= 3
            or not isinstance(committed, bool)
            or (committed and indices != [1, 2, 3])
        ):
            raise R8RunnerRefusal("resume call-position identity drifted")
        seen.add(job)
        observed_ordinals.append(ordinal)
        total_calls += len(indices)
        committed_runs += int(committed)
    frontier = max(observed_ordinals) // max_workers if observed_ordinals else -1
    if observed_ordinals != sorted(observed_ordinals) or value.get("frontier_batch") != frontier:
        raise R8RunnerRefusal("resume scheduler frontier drifted")
    for ordinal in range(max(0, frontier * max_workers)):
        prior = next(
            (
                position
                for position in positions
                if position.get("job_ordinal") == ordinal
            ),
            None,
        )
        if (
            not isinstance(prior, Mapping)
            or prior.get("call_indices") != [1, 2, 3]
            or prior.get("item_run_committed") is not True
        ):
            raise R8RunnerRefusal("resume scheduler batch order drifted")
    if (
        total_calls != call_count
        or committed_runs != item_run_count
        or (call_count > 0 and event_count < call_count * 6)
    ):
        raise R8RunnerRefusal("resume call-position coverage drifted")
    zero = call_count == item_run_count == event_count == spool_count == 0
    if (
        value.get("zero_count_genesis") is not zero
        or (zero and (positions or frontier != -1))
    ):
        raise R8RunnerRefusal("resume zero-count identity drifted")
    del spool_audit
    return dict(value)


def _empty_attempt_audit_from(
    value: Mapping[str, object],
) -> dict[str, object]:
    unsigned = {
        "schema_version": TRANSPORT_SCHEMA,
        "journal_mode": value["journal_mode"],
        "synchronous": value["synchronous"],
        "event_chain_tip_sha256": _EVENT_GENESIS,
        "call_count": 0,
        "status_counts": {},
        "accepted_call_root_sha256": canonical_sha256([]),
        "spool_binding_root_sha256": canonical_sha256([]),
        "item_run_count": 0,
        "item_run_root_sha256": canonical_sha256([]),
    }
    result = {**unsigned, "audit_sha256": canonical_sha256(unsigned)}
    return _validate_live_attempt_audit(
        result, expected_calls=0, expected_item_runs=0
    )


def _spool_preflight_database_identity(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise R8RunnerRefusal("spool identity preflight shape drifted")
    identity = value.get("endpoint_identity")
    if not isinstance(identity, Mapping):
        raise R8RunnerRefusal("result-spool identity shape drifted")
    return _database_identity_value(identity.get("db_identity"), "result spool")


def _validate_resume_database_identity_continuity(
    *,
    genesis: Mapping[str, object],
    resume_prefix: Mapping[str, object],
    spool_identity_preflight: Mapping[str, object] | None = None,
) -> None:
    """Bind every restart authority to the same frozen database pair."""

    for field, label in (
        ("attempt_db_identity", "attempt ledger"),
        ("spool_db_identity", "result spool"),
    ):
        genesis_identity = _database_identity_value(genesis.get(field), label)
        prefix_identity = _database_identity_value(
            resume_prefix.get(field), f"resume {label}"
        )
        if prefix_identity != genesis_identity:
            raise R8RunnerRefusal(
                f"resume {label} identity differs from frozen genesis"
            )
    if (
        spool_identity_preflight is not None
        and _spool_preflight_database_identity(spool_identity_preflight)
        != _database_identity_value(
            genesis.get("spool_db_identity"), "genesis result spool"
        )
    ):
        raise R8RunnerRefusal(
            "spool identity preflight differs from frozen genesis"
        )


def _validate_spool_identity_preflight(
    value: object,
    *,
    run_id: str,
    deployment_binding: ModelDeploymentBinding,
    execution_lock_sha256: str,
    db_genesis_sha256: str,
    endpoint: str,
) -> str:
    if not isinstance(value, Mapping) or set(value) != _SPOOL_PREFLIGHT_FIELDS:
        raise R8RunnerRefusal("spool identity preflight shape drifted")
    declared = _self_hash(value, "preflight_sha256", "spool identity preflight")
    identity = value.get("endpoint_identity")
    if not isinstance(identity, Mapping) or set(identity) != _SPOOL_IDENTITY_FIELDS:
        raise R8RunnerRefusal("result-spool identity shape drifted")
    _self_hash(identity, "identity_sha256", "result-spool identity")
    _spool_preflight_database_identity(value)
    _validate_spool_audit(identity.get("audit"))
    deployment_values = {
        "upstream_endpoint": deployment_binding.upstream_endpoint,
        "deployment_receipt_sha256": (
            deployment_binding.deployment_receipt_sha256
        ),
        "deployment_id": deployment_binding.deployment_id,
        "served_model": deployment_binding.served_model,
        "model_revision": deployment_binding.model_revision,
    }
    identity_values = {
        "upstream_endpoint": identity.get("normalized_upstream_endpoint"),
        "deployment_receipt_sha256": identity.get("deployment_receipt_sha256"),
        "deployment_id": identity.get("deployment_id"),
        "served_model": identity.get("served_model"),
        "model_revision": identity.get("model_revision"),
    }
    if (
        value.get("schema_version") != SPOOL_PREFLIGHT_SCHEMA
        or value.get("run_id") != run_id
        or value.get("execution_lock_sha256") != execution_lock_sha256
        or value.get("db_genesis_sha256") != db_genesis_sha256
        or value.get("endpoint") != endpoint
        or identity.get("schema_version") != SPOOL_IDENTITY_SCHEMA
        or any(value.get(key) != item for key, item in deployment_values.items())
        or identity_values != deployment_values
    ):
        raise R8RunnerRefusal("spool identity preflight differs from frozen execution")
    return declared


def _stable_file_sha256(path: Path, label: str) -> str:
    try:
        _raw, digest = read_stable_bytes(path, label)
    except R8RunnerRefusal:
        raise
    except Exception as error:
        raise R8RunnerRefusal(f"cannot hash {label}") from error
    return digest


def capture_judge_hashes(
    path: Path,
    label: str,
    *,
    expected_measurement_lock_sha256: str | None = None,
) -> tuple[str, str]:
    """Hash and normalize judge authority from one immutable byte capture."""

    raw, full_sha = read_stable_bytes(path, label)
    try:
        source = raw.decode("utf-8")
    except UnicodeError as error:
        raise R8RunnerRefusal(f"cannot read {label} as UTF-8") from error
    marker = "__F1_R8_MEASUREMENT_LOCK_SHA256_UNFROZEN__"
    pattern = re.compile(
        r'^EXPECTED_MEASUREMENT_LOCK_SHA256 = "([0-9a-f]{64}|'
        + re.escape(marker)
        + r')"$',
        re.MULTILINE,
    )
    matches = pattern.findall(source)
    if len(matches) != 1:
        raise R8RunnerRefusal(f"{label} lock-anchor assignment is ambiguous")
    if (
        expected_measurement_lock_sha256 is not None
        and matches != [expected_measurement_lock_sha256]
    ):
        raise R8RunnerRefusal(f"{label} does not carry the exact lock anchor")
    normalized = pattern.sub(
        f'EXPECTED_MEASUREMENT_LOCK_SHA256 = "{marker}"', source
    )
    return full_sha, hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _replay_token_envelope_derivation(
    *,
    derivation_inputs: Mapping[str, object],
    manifest: Mapping[str, object],
    token_meter: TokenMeter,
    protocol_path: Path,
    development_run_id: str,
) -> str:
    # Local import avoids the producer's intentional use of runner item and
    # registry constructors during module initialization.
    from prom_search_hswm.prom9_f1_r8_envelope import (
        verify_token_envelope_derivation,
    )

    return verify_token_envelope_derivation(
        receipt=derivation_inputs["receipt"],
        manifest=manifest,
        selection=derivation_inputs["selection_receipt"],
        historical_manifest=derivation_inputs["historical_manifest"],
        validation_receipt=derivation_inputs["validation_receipt"],
        projected_outputs_receipt=derivation_inputs[
            "projected_outputs_receipt"
        ],
        source_suite=derivation_inputs["source_suite"],
        protocol=derivation_inputs["protocol"],
        meter=token_meter,
        file_sha256s=derivation_inputs["file_sha256s"],
        development_run_id=development_run_id,
    )


def _derivation_development_run_id(
    selection_receipt: Mapping[str, object],
) -> str:
    schema = selection_receipt.get("schema_version")
    if schema == HISTORICAL_SELECTION_SCHEMA:
        return HISTORICAL_DERIVATION_DEVELOPMENT_RUN_ID
    if schema == SUCCESSOR_SELECTION_SCHEMA:
        return DEVELOPMENT_RUN_ID
    raise R8RunnerRefusal("token-envelope derivation selection generation drifted")


def _validate_token_envelope_derivation_gate(
    derivation_inputs: Mapping[str, object],
    *,
    manifest: Mapping[str, object],
    execution_lock: Mapping[str, object],
    token_meter: TokenMeter,
    protocol_path: Path,
    preregistration_artifact: Mapping[str, object] | None,
) -> str:
    if set(derivation_inputs) != _DERIVATION_INPUT_FIELDS:
        raise R8RunnerRefusal("token-envelope derivation input set drifted")
    receipt = derivation_inputs.get("receipt")
    file_sha256s = derivation_inputs.get("file_sha256s")
    if (
        not isinstance(receipt, Mapping)
        or set(receipt) != _DERIVATION_RECEIPT_FIELDS
        or not isinstance(file_sha256s, Mapping)
        or set(file_sha256s) != _DERIVATION_FILE_FIELDS
        or any(
            not isinstance(derivation_inputs.get(name), Mapping)
            for name in _DERIVATION_FILE_FIELDS
        )
    ):
        raise R8RunnerRefusal("token-envelope derivation artifact shape drifted")
    selection_receipt = derivation_inputs["selection_receipt"]
    assert isinstance(selection_receipt, Mapping)
    derivation_development_run_id = _derivation_development_run_id(
        selection_receipt
    )
    for name, digest in file_sha256s.items():
        _sha(digest, f"token-envelope derivation file {name}")
    receipt_sha = _self_hash(
        receipt, "receipt_sha256", "token-envelope derivation receipt"
    )
    if (
        receipt.get("schema_version")
        != "hswm-prom9-f1-r8-token-envelope-derivation/v1"
        or receipt.get("derivation_policy")
        != "tight_common_componentwise_max_of_both_frozen_cohorts/v1"
        or receipt.get("historical_input_caps_used_as_floor") is not False
        or receipt.get("gold_inputs_read") is not False
        or receipt.get("model_calls") != 0
    ):
        raise R8RunnerRefusal("token-envelope derivation policy drifted")
    envelope = manifest.get("token_envelope")
    if not isinstance(envelope, Mapping):
        raise R8RunnerRefusal("manifest token envelope is absent")
    input_caps = envelope.get("per_call_input_caps")
    output_caps = envelope.get("per_call_output_caps")
    if not isinstance(input_caps, Mapping) or not isinstance(output_caps, Mapping):
        raise R8RunnerRefusal("manifest token-envelope caps are absent")
    expected_bindings = {
        "selection_receipt_sha256": execution_lock.get(
            "selection_receipt_sha256"
        ),
        "model": manifest.get("model"),
        "model_revision": manifest.get("model_revision"),
        "protocol_sha256": execution_lock.get("protocol_sha256"),
        "registries_root_sha256": execution_lock.get(
            "registries_root_sha256"
        ),
        "token_envelope_sha256": execution_lock.get("token_envelope_sha256"),
        "per_call_input_caps": dict(input_caps),
        "per_call_output_caps": dict(output_caps),
        "total_input_tokens_per_run": sum(int(value) for value in input_caps.values()),
        "total_allowed_output_tokens_per_run": sum(
            int(value) for value in output_caps.values()
        ),
        "projection_slack_tokens": envelope.get("projection_slack_tokens"),
        "token_tolerance": manifest.get("token_tolerance"),
        "token_meter": token_meter.identity(),
    }
    if any(receipt.get(key) != value for key, value in expected_bindings.items()):
        raise R8RunnerRefusal("token-envelope derivation differs from frozen execution")
    if (
        canonical_sha256(envelope) != receipt.get("token_envelope_sha256")
        or receipt_sha
        != execution_lock.get("token_envelope_derivation_receipt_sha256")
    ):
        raise R8RunnerRefusal("token-envelope derivation lock binding drifted")
    expected_cohorts = {
        "development": (derivation_development_run_id, 55, 48),
        "confirmatory": (SEALED_RUN_ID, 100, 100),
    }
    for cohort, (run_id, items, components) in expected_cohorts.items():
        value = receipt.get(cohort)
        if (
            not isinstance(value, Mapping)
            or set(value) != _DERIVATION_COHORT_FIELDS
            or value.get("run_id") != run_id
            or value.get("items") != items
            or value.get("components") != components
            or not isinstance(value.get("minimum_input_caps"), Mapping)
            or set(value.get("minimum_input_caps", {})) != {"1", "2", "3"}
        ):
            raise R8RunnerRefusal(
                f"token-envelope derivation {cohort} cohort drifted"
            )
        _sha(value.get("projection_sha256"), f"{cohort} derivation projection")
    mode = manifest.get("mode")
    expected_run = DEVELOPMENT_RUN_ID if mode == "development" else SEALED_RUN_ID
    if manifest.get("run_id") != expected_run:
        raise R8RunnerRefusal("manifest run ID differs from the derivation cohort")
    if preregistration_artifact is not None and (
        preregistration_artifact.get(
            "token_envelope_derivation_receipt_sha256"
        )
        != receipt_sha
    ):
        raise R8RunnerRefusal(
            "preregistration artifact differs from the derivation receipt"
        )
    try:
        replayed_sha = _replay_token_envelope_derivation(
            derivation_inputs=derivation_inputs,
            manifest=manifest,
            token_meter=token_meter,
            protocol_path=protocol_path,
            development_run_id=derivation_development_run_id,
        )
    except Exception as error:
        raise R8RunnerRefusal(
            "token-envelope derivation replay failed"
        ) from error
    if replayed_sha != receipt_sha:
        raise R8RunnerRefusal("token-envelope derivation replay SHA drifted")
    return receipt_sha


def _judge_hashes(
    path: Path,
    measurement_lock_sha256: str,
    *,
    label: str = "anchored judge",
) -> tuple[str, str]:
    return capture_judge_hashes(
        path,
        label,
        expected_measurement_lock_sha256=measurement_lock_sha256,
    )


def _validate_environment_dependency_bundle(
    value: object,
    *,
    execution_lock: Mapping[str, object],
    run_id: str,
    model: str,
    model_revision: str,
    spool_endpoint: str,
    deployment_binding: ModelDeploymentBinding,
    dependency_paths: Mapping[str, Path],
    symposium_repo_root: Path,
) -> str:
    if not isinstance(value, Mapping):
        raise R8RunnerRefusal("environment/dependency bundle is absent")
    environment = value.get("environment_receipt")
    dependencies = value.get("dependency_receipt")
    if not isinstance(environment, Mapping) or not isinstance(dependencies, Mapping):
        raise R8RunnerRefusal("environment/dependency receipts are absent")
    bundle_labels = environment.get("labels")
    symposium_commit = (
        bundle_labels.get("symposium_commit")
        if isinstance(bundle_labels, Mapping)
        else None
    )
    if (
        not isinstance(symposium_commit, str)
        or _GIT_COMMIT.fullmatch(symposium_commit) is None
    ):
        raise R8RunnerRefusal(
            "environment symposium_commit is not an exact Git SHA"
        )
    labels = {
        "spool_endpoint": spool_endpoint,
        "model_upstream_endpoint": deployment_binding.upstream_endpoint,
        "model_deployment_receipt_sha256": (
            deployment_binding.deployment_receipt_sha256
        ),
        "hswm_commit": execution_lock.get("hswm_commit"),
        "model": model,
        "model_revision": model_revision,
        "run_id": run_id,
        "symposium_commit": symposium_commit,
    }
    try:
        verified = verify_r8_preimage_bundle(
            value,
            expected_paths=dependency_paths,
            expected_labels=labels,
            repo_root=Path(__file__).resolve().parents[1],
            symposium_repo_root=symposium_repo_root,
            verify_live=True,
        )
    except Exception as error:
        raise R8RunnerRefusal("environment/dependency bundle verification failed") from error
    if environment.get("labels") != labels:
        raise R8RunnerRefusal("environment labels differ from frozen execution")
    hswm_commit = execution_lock.get("hswm_commit")
    if not isinstance(hswm_commit, str) or _GIT_COMMIT.fullmatch(hswm_commit) is None:
        raise R8RunnerRefusal("execution-lock hswm_commit is not an exact Git SHA")
    files = dependencies.get("files")
    expected_names = set(REQUIRED_DEPENDENCY_FILES)
    if not isinstance(files, Mapping) or set(files) != expected_names:
        raise R8RunnerRefusal("dependency semantic-name inventory drifted")
    result_row = files.get("result_contract")
    result_contract_path = dependency_paths.get("result_contract")
    if not isinstance(result_contract_path, Path):
        raise R8RunnerRefusal("result contract semantic path is absent")
    result_sha = _stable_file_sha256(result_contract_path, "result contract")
    if (
        not isinstance(result_row, Mapping)
        or result_row.get("resolved_path")
        != str(Path(result_contract_path).resolve(strict=True))
        or result_row.get("sha256") != result_sha
    ):
        raise R8RunnerRefusal("result contract differs from dependency preimage")
    expected_bindings = {
        "environment_receipt_sha256": verified["environment_receipt_sha256"],
        "dependency_receipt_sha256": verified["dependency_receipt_sha256"],
        "environment_dependency_compatibility_root_sha256": verified[
            "compatibility_root_sha256"
        ],
        "environment_dependency_bundle_sha256": verified["bundle_sha256"],
        "result_contract_sha256": result_sha,
    }
    if any(execution_lock.get(key) != item for key, item in expected_bindings.items()):
        raise R8RunnerRefusal("environment/dependency bundle differs from execution lock")
    return verified["bundle_sha256"]


def _validate_aborted_attempt_exposure_gate(
    value: Mapping[str, object],
    *,
    prior_exposure_receipt: Mapping[str, object],
    execution_lock: Mapping[str, object],
) -> str:
    development_execution = execution_lock.get("schema_version") == EXECUTION_LOCK_SCHEMA
    if (
        development_execution
        and execution_lock.get("run_id") != F1_R8_A3_SUCCESSOR_RUN_ID
    ):
        raise R8RunnerRefusal(
            "development execution requires the fresh a3 successor identity"
        )
    try:
        receipt_sha = (
            verify_f1_r8_successor_exposure_set(value)
            if development_execution
            else verify_aborted_attempt_exposure_receipt(value)
        )
    except Exception as error:
        raise R8RunnerRefusal(
            "aborted-attempt exposure receipt verification failed"
        ) from error
    if receipt_sha != execution_lock.get(
        "aborted_attempt_exposure_receipt_sha256"
    ):
        raise R8RunnerRefusal(
            "aborted-attempt exposure receipt differs from execution lock"
        )
    try:
        verify_forbidden_exposure_union(
            prior_exposure_receipt, value, execution_lock
        )
    except Exception as error:
        raise R8RunnerRefusal(
            "execution-lock forbidden exposure union verification failed"
        ) from error
    return receipt_sha


def _validate_preregistration_gate(
    *,
    mode: str,
    manifest: Mapping[str, object],
    execution_lock: Mapping[str, object],
    preregistration_artifact: Mapping[str, object] | None,
    preregistration_readback: Mapping[str, object] | None,
    anchored_judge_path: Path | None,
    judge_core_path: Path,
    symposium_repo_root: Path,
    result_contract_path: Path,
) -> None:
    if mode == "development":
        if any(
            value is not None
            for value in (
                preregistration_artifact, preregistration_readback,
                anchored_judge_path,
            )
        ):
            raise R8RunnerRefusal("development execution rejects sealed preregistration inputs")
        return
    if (
        not isinstance(preregistration_artifact, Mapping)
        or not isinstance(preregistration_readback, Mapping)
        or anchored_judge_path is None
    ):
        raise R8RunnerRefusal("sealed execution requires the complete preregistration gate")
    try:
        symposium_root = Path(symposium_repo_root).resolve(strict=True)
        committed_judge_core = Path(judge_core_path).resolve(strict=True)
    except OSError as error:
        raise R8RunnerRefusal("sealed judge-core repository path is unavailable") from error
    if (
        not symposium_root.is_dir()
        or not committed_judge_core.is_relative_to(symposium_root)
    ):
        raise R8RunnerRefusal(
            "sealed judge core is outside the declared SYMPOSIUM repository"
        )
    marker = "__F1_R8_MEASUREMENT_LOCK_SHA256_UNFROZEN__"
    judge_core_file_sha, committed_core_sha = _judge_hashes(
        committed_judge_core,
        marker,
        label="judge core",
    )
    if (
        execution_lock.get("judge_core_file_sha256") != judge_core_file_sha
        or execution_lock.get("judge_core_sha256") != committed_core_sha
    ):
        raise R8RunnerRefusal("sealed judge core differs from the execution lock")
    artifact = preregistration_artifact
    if (
        set(artifact) != _PREREGISTRATION_ARTIFACT_FIELDS
        or artifact.get("schema_version") != PREREGISTRATION_ARTIFACT_SCHEMA
        or artifact.get("purpose") != SEALED_LOCK_PURPOSE
        or artifact.get("experiment_tag") != SEALED_EXPERIMENT_TAG
        or artifact.get("closes_question") != SEALED_CLOSES_QUESTION
        or artifact.get("run_id") != SEALED_RUN_ID
        or artifact.get("mode") != "sealed"
    ):
        raise R8RunnerRefusal("sealed preregistration artifact shape drifted")
    if (
        artifact.get("predicted_outcome") != PREDICTED_OUTCOME
        or artifact.get("falsification_condition") != FALSIFICATION_CONDITION
    ):
        raise R8RunnerRefusal(
            "sealed preregistration prediction/falsifier drifted"
        )
    artifact_sha = _self_hash(
        artifact, "preregistration_artifact_sha256", "preregistration artifact"
    )
    if (
        artifact_sha != manifest.get("preregistration_artifact_sha256")
        or artifact_sha != execution_lock.get("preregistration_artifact_sha256")
        or artifact.get("manifest_core_sha256") != manifest_core_sha256(manifest)
    ):
        raise R8RunnerRefusal("preregistration artifact is not manifest/lock-bound")
    for key in _PREREGISTRATION_ARTIFACT_FIELDS & set(execution_lock):
        if key not in {"schema_version", "purpose"} and artifact.get(key) != execution_lock.get(key):
            raise R8RunnerRefusal(f"preregistration artifact differs from lock: {key}")
    for key in _PREREGISTRATION_ARTIFACT_FIELDS:
        if key.endswith("_sha256"):
            _sha(artifact.get(key), f"preregistration {key}")
    _validate_prior_list(
        artifact.get("forbidden_prior_item_ids"),
        "preregistration forbidden item IDs",
        sha_values=False,
    )
    _validate_prior_list(
        artifact.get("forbidden_prior_source_entity_ids"),
        "preregistration forbidden source-entity IDs",
        sha_values=True,
    )
    _validate_prior_list(
        artifact.get("forbidden_prior_component_ids"),
        "preregistration forbidden component IDs",
        sha_values=True,
    )
    _validate_lock_gates(
        artifact.get("gates"),
        item_count=len(manifest.get("items", [])),
        token_envelope=manifest.get("token_envelope", {}),
        token_tolerance=int(manifest.get("token_tolerance", -1)),
    )
    readback = preregistration_readback
    if (
        set(readback) != _PREREGISTRATION_READBACK_FIELDS
        or readback.get("schema_version") != PREREGISTRATION_READBACK_SCHEMA
        or readback.get("purpose") != SEALED_LOCK_PURPOSE
        or readback.get("experiment_tag") != SEALED_EXPERIMENT_TAG
        or readback.get("closes_question") != SEALED_CLOSES_QUESTION
        or readback.get("run_id") != SEALED_RUN_ID
    ):
        raise R8RunnerRefusal("sealed preregistration readback shape drifted")
    _self_hash(readback, "receipt_sha256", "preregistration readback")
    for key in _PREREGISTRATION_READBACK_FIELDS:
        if key.endswith("_sha256"):
            _sha(readback.get(key), f"preregistration readback {key}")
    lock_sha = str(execution_lock.get("lock_sha256"))
    full_judge_sha, core_judge_sha = _judge_hashes(anchored_judge_path, lock_sha)
    result_contract_sha = _stable_file_sha256(result_contract_path, "result contract")
    if (
        readback.get("measurement_lock_sha256") != lock_sha
        or readback.get("preregistration_artifact_sha256") != artifact_sha
        or readback.get("pred_script_sha256") != full_judge_sha
        or readback.get("anchored_judge_file_sha256") != full_judge_sha
        or readback.get("judge_core_sha256") != core_judge_sha
        or artifact.get("judge_core_sha256") != core_judge_sha
        or execution_lock.get("judge_core_sha256") != core_judge_sha
        or core_judge_sha != committed_core_sha
        or readback.get("result_contract_sha256") != result_contract_sha
        or artifact.get("result_contract_sha256") != result_contract_sha
        or execution_lock.get("result_contract_sha256") != result_contract_sha
    ):
        raise R8RunnerRefusal("preregistration judge/result-contract binding drifted")
    external_identity = readback.get("external_record_identity")
    if not (
        isinstance(external_identity, str) and external_identity.strip()
        or isinstance(external_identity, Mapping) and bool(external_identity)
    ):
        raise R8RunnerRefusal("preregistration external record identity is absent")


def _database_identity(path: Path, label: str) -> dict[str, object]:
    try:
        return private_database_identity(path, label)
    except TransportAuditRefusal as error:
        raise R8RunnerRefusal(str(error)) from error


def _read_only_database(path: Path, label: str) -> FrozenSQLiteReadOnly:
    try:
        return open_frozen_sqlite_read_only(path, label)
    except TransportAuditRefusal as error:
        raise R8RunnerRefusal(f"cannot open {label} read-only: {error}") from error


def _database_schema(
    connection: sqlite3.Connection,
    authority: str,
    label: str,
) -> tuple[int, str]:
    try:
        return exact_schema_readback(connection, authority, label)
    except TransportAuditRefusal as error:
        raise R8RunnerRefusal(str(error)) from error


def _private_sqlite_path(path: Path, label: str) -> Path:
    try:
        return canonical_output_path(Path(path))
    except Exception as error:
        raise R8RunnerRefusal(f"{label} parent is not a canonical directory") from error


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(
        path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _seal_private_sqlite_family(path: Path, label: str) -> None:
    target = _private_sqlite_path(path, label)
    for member in (
        target,
        Path(f"{target}-wal"),
        Path(f"{target}-shm"),
        Path(f"{target}-journal"),
    ):
        try:
            before = member.lstat()
        except FileNotFoundError:
            if member == target:
                raise R8RunnerRefusal(f"{label} database is absent")
            continue
        except OSError as error:
            raise R8RunnerRefusal(f"cannot stat {label} SQLite family") from error
        if member == Path(f"{target}-journal"):
            raise R8RunnerRefusal(
                f"{label} rollback journal exists; recovery is not authorized"
            )
        member_label = f"{label} SQLite family member"
        try:
            identity = private_database_identity(member, member_label)
        except TransportAuditRefusal as error:
            raise R8RunnerRefusal(str(error)) from error
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = -1
        try:
            descriptor = os.open(member, flags)
            after = os.fstat(descriptor)
            if (
                (identity["st_dev"], identity["st_ino"])
                != (after.st_dev, after.st_ino)
                or stat.S_IMODE(after.st_mode) != 0o600
                or after.st_uid != os.geteuid()
                or after.st_nlink != 1
            ):
                raise R8RunnerRefusal(f"{label} SQLite family identity drifted")
            os.fsync(descriptor)
            if private_database_identity(member, member_label) != identity:
                raise R8RunnerRefusal(f"{label} SQLite family identity drifted")
        except OSError as error:
            raise R8RunnerRefusal(f"cannot open {label} SQLite family") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    _fsync_parent(target)


def initialize_transport_pair(attempt_db: Path, spool_db: Path) -> None:
    attempt = _private_sqlite_path(attempt_db, "attempt ledger")
    spool = _private_sqlite_path(spool_db, "result spool")
    if attempt == spool:
        raise R8RunnerRefusal("attempt and spool databases must be different files")
    attempt_store: SQLiteF1CallLedger | None = None
    spool_store: SQLiteResultSpool | None = None
    try:
        attempt_store = SQLiteF1CallLedger(attempt)
        spool_store = SQLiteResultSpool(spool)
        if (
            attempt_store.audit().get("call_count") != 0
            or attempt_store.audit().get("item_run_count") != 0
            or spool_store.audit().get("call_count") != 0
        ):
            raise R8RunnerRefusal("new transport pair is not logically empty")
    except (DurableLedgerIntegrityError, SpoolIntegrityError) as error:
        raise R8RunnerRefusal(
            "transport database is already occupied or invalid"
        ) from error
    finally:
        if attempt_store is not None:
            attempt_store.close()
        if spool_store is not None:
            spool_store.close()
    _seal_private_sqlite_family(attempt, "attempt ledger")
    _seal_private_sqlite_family(spool, "result spool")


def verify_fresh_transport_genesis(
    genesis_receipt: Mapping[str, object],
    *,
    execution_lock: Mapping[str, object],
    run_id: str,
    attempt_db: Path,
    spool_db: Path,
    require_live_empty: bool = True,
) -> str:
    if not isinstance(require_live_empty, bool):
        raise R8RunnerRefusal("require_live_empty must be boolean")
    lock_sha = _self_hash(execution_lock, "lock_sha256", "execution lock")
    _sha(lock_sha, "execution lock")
    lock_genesis_sha = execution_lock.get("db_genesis_receipt_sha256")
    _sha(lock_genesis_sha, "execution-lock DB genesis receipt")
    genesis_sha = _validate_transport_genesis_receipt(
        genesis_receipt,
        run_id=run_id,
        expected_sha256=str(lock_genesis_sha),
    )
    observed_identities = {
        "attempt_db_identity": _database_identity(attempt_db, "attempt ledger"),
        "spool_db_identity": _database_identity(spool_db, "result spool"),
    }
    if any(
        genesis_receipt.get(key) != value
        for key, value in observed_identities.items()
    ):
        raise R8RunnerRefusal("transport database identity changed after genesis freeze")
    attempt = _read_only_database(attempt_db, "attempt ledger")
    spool = _read_only_database(spool_db, "result spool")
    try:
        if [str(row[0]) for row in attempt.execute("PRAGMA integrity_check")] != ["ok"]:
            raise R8RunnerRefusal("attempt ledger integrity_check failed")
        if [str(row[0]) for row in spool.execute("PRAGMA integrity_check")] != ["ok"]:
            raise R8RunnerRefusal("result spool integrity_check failed")
        attempt_version, attempt_schema = _database_schema(
            attempt, "attempt", "attempt ledger"
        )
        spool_version, spool_schema = _database_schema(
            spool, "spool", "result spool"
        )
        observed = {
            "attempt_integrity": "ok",
            "spool_integrity": "ok",
            "attempt_user_version": attempt_version,
            "spool_user_version": spool_version,
            "attempt_schema_sha256": attempt_schema,
            "spool_schema_sha256": spool_schema,
            "attempt_journal_mode": str(
                attempt.execute("PRAGMA journal_mode").fetchone()[0]
            ),
            "attempt_audit_connection_synchronous": str(
                attempt.execute("PRAGMA synchronous").fetchone()[0]
            ),
            "spool_journal_mode": str(spool.execute("PRAGMA journal_mode").fetchone()[0]),
            "spool_audit_connection_synchronous": str(
                spool.execute("PRAGMA synchronous").fetchone()[0]
            ),
        }
        if any(genesis_receipt.get(key) != value for key, value in observed.items()):
            raise R8RunnerRefusal(
                "live transport identity or schema no longer equals frozen genesis"
            )
        live_counts = {
            "call_count": int(
                attempt.execute("SELECT COUNT(*) FROM call_state").fetchone()[0]
            ),
            "item_run_count": int(
                attempt.execute("SELECT COUNT(*) FROM item_runs").fetchone()[0]
            ),
            "attempt_event_count": int(
                attempt.execute("SELECT COUNT(*) FROM attempt_events").fetchone()[0]
            ),
            "spool_call_count": int(
                spool.execute("SELECT COUNT(*) FROM spool_calls").fetchone()[0]
            ),
        }
        if require_live_empty and any(
            genesis_receipt.get(key) != value for key, value in live_counts.items()
        ):
            raise R8RunnerRefusal("live transport pair no longer equals frozen genesis")
    finally:
        attempt.close()
        spool.close()
    if any(
        observed_identities[key] != _database_identity(
            attempt_db if key == "attempt_db_identity" else spool_db,
            "attempt ledger" if key == "attempt_db_identity" else "result spool",
        )
        for key in observed_identities
    ):
        raise R8RunnerRefusal("transport identity changed during pre-call genesis audit")
    return genesis_sha


def validate_execution_policy(
    execution_lock: Mapping[str, object],
    *,
    endpoint: str,
    max_workers: int,
    timeout_seconds: float,
    max_delivery_attempts: int,
    spool_token_env: str | None,
) -> None:
    expected = _validate_execution_policy_value(execution_lock.get("execution_policy"))
    observed = {
        "endpoint": endpoint,
        "max_workers": max_workers,
        "timeout_seconds": timeout_seconds,
        "max_delivery_attempts": max_delivery_attempts,
        "spool_token_env": spool_token_env,
    }
    if expected != observed:
        raise R8RunnerRefusal("runtime execution policy differs from the frozen lock")


def _read_spool_endpoint_identity(
    *,
    endpoint: str,
    spool_db: Path,
    deployment_binding: ModelDeploymentBinding,
    spool_token_env: str,
    timeout_seconds: float,
    expected_live_audit: Mapping[str, object],
) -> dict[str, object]:
    token = os.environ.get(spool_token_env)
    if not token:
        raise R8RunnerRefusal("result-spool bearer token is absent")
    request = urllib_request.Request(
        f"{endpoint.rstrip('/')}{SPOOL_IDENTITY_ROUTE}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib_request.urlopen(request, timeout=timeout_seconds) as response:
            if int(response.status) != 200:
                raise R8RunnerRefusal("result-spool identity endpoint refused preflight")
            raw = response.read(128 * 1024 + 1)
    except (OSError, urllib_error.URLError) as error:
        raise R8RunnerRefusal("cannot read result-spool identity endpoint") from error
    if len(raw) > 128 * 1024:
        raise R8RunnerRefusal("result-spool identity response is oversized")
    try:
        identity = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                R8RunnerRefusal("non-finite spool identity value")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise R8RunnerRefusal("result-spool identity is not strict JSON") from error
    if not isinstance(identity, Mapping) or set(identity) != _SPOOL_IDENTITY_FIELDS:
        raise R8RunnerRefusal("result-spool identity shape drifted")
    _self_hash(identity, "identity_sha256", "result-spool identity")
    audit = identity.get("audit")
    expected_calls = _nonnegative(
        expected_live_audit.get("call_count"), "expected result-spool calls"
    )
    _validate_spool_audit(audit, expected_calls=expected_calls)
    _validate_spool_audit(expected_live_audit, expected_calls=expected_calls)
    if audit != expected_live_audit:
        raise R8RunnerRefusal(
            "result-spool endpoint audit differs from the resume prefix"
        )
    if (
        identity.get("schema_version") != SPOOL_IDENTITY_SCHEMA
        or identity.get("db_identity") != _database_identity(spool_db, "result spool")
    ):
        raise R8RunnerRefusal("endpoint service does not own the frozen empty spool DB")
    identity_deployment = {
        "upstream_endpoint": identity.get("normalized_upstream_endpoint"),
        "deployment_receipt_sha256": identity.get("deployment_receipt_sha256"),
        "deployment_id": identity.get("deployment_id"),
        "served_model": identity.get("served_model"),
        "model_revision": identity.get("model_revision"),
    }
    expected_deployment = {
        "upstream_endpoint": deployment_binding.upstream_endpoint,
        "deployment_receipt_sha256": (
            deployment_binding.deployment_receipt_sha256
        ),
        "deployment_id": deployment_binding.deployment_id,
        "served_model": deployment_binding.served_model,
        "model_revision": deployment_binding.model_revision,
    }
    if identity_deployment != expected_deployment:
        raise R8RunnerRefusal(
            "endpoint service deployment differs from the frozen lock"
        )
    return dict(identity)


def verify_spool_endpoint_identity(
    *,
    endpoint: str,
    spool_db: Path,
    deployment_binding: ModelDeploymentBinding,
    spool_token_env: str,
    timeout_seconds: float,
    run_id: str,
    execution_lock_sha256: str,
    db_genesis_sha256: str,
) -> dict[str, object]:
    empty_audit_unsigned = {
        "schema_version": SPOOL_SCHEMA,
        "journal_mode": "wal",
        "synchronous": 2,
        "call_count": 0,
        "status_counts": {},
        "completed_root_sha256": canonical_sha256([]),
    }
    empty_audit = {
        **empty_audit_unsigned,
        "audit_sha256": canonical_sha256(empty_audit_unsigned),
    }
    identity = _read_spool_endpoint_identity(
        endpoint=endpoint,
        spool_db=spool_db,
        deployment_binding=deployment_binding,
        spool_token_env=spool_token_env,
        timeout_seconds=timeout_seconds,
        expected_live_audit=empty_audit,
    )
    expected_deployment = {
        "upstream_endpoint": deployment_binding.upstream_endpoint,
        "deployment_receipt_sha256": (
            deployment_binding.deployment_receipt_sha256
        ),
        "deployment_id": deployment_binding.deployment_id,
        "served_model": deployment_binding.served_model,
        "model_revision": deployment_binding.model_revision,
    }
    unsigned = {
        "schema_version": SPOOL_PREFLIGHT_SCHEMA,
        "run_id": run_id,
        "execution_lock_sha256": execution_lock_sha256,
        "db_genesis_sha256": db_genesis_sha256,
        "endpoint": endpoint,
        **expected_deployment,
        "endpoint_identity": dict(identity),
    }
    result = {**unsigned, "preflight_sha256": canonical_sha256(unsigned)}
    _validate_spool_identity_preflight(
        result,
        run_id=run_id,
        deployment_binding=deployment_binding,
        execution_lock_sha256=execution_lock_sha256,
        db_genesis_sha256=db_genesis_sha256,
        endpoint=endpoint,
    )
    return result


def verify_spool_endpoint_resume_identity(
    *,
    endpoint: str,
    spool_db: Path,
    deployment_binding: ModelDeploymentBinding,
    spool_token_env: str,
    timeout_seconds: float,
    expected_live_audit: Mapping[str, object],
) -> dict[str, object]:
    """Verify the live spool service against a previously exported prefix."""

    return _read_spool_endpoint_identity(
        endpoint=endpoint,
        spool_db=spool_db,
        deployment_binding=deployment_binding,
        spool_token_env=spool_token_env,
        timeout_seconds=timeout_seconds,
        expected_live_audit=expected_live_audit,
    )


def _decoded_bytes(value: object, label: str) -> bytes:
    if not isinstance(value, str):
        raise R8RunnerRefusal(f"{label} is not base64 text")
    try:
        raw = base64.b64decode(value, validate=True)
    except ValueError as error:
        raise R8RunnerRefusal(f"{label} is invalid base64") from error
    return raw


def _strict_json_bytes(raw: bytes, label: str, *, canonical: bool) -> object:
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                R8RunnerRefusal(f"non-finite JSON number in {label}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise R8RunnerRefusal(f"{label} is not strict JSON") from error
    if canonical and canonical_json(value).encode("utf-8") != raw:
        raise R8RunnerRefusal(f"{label} is not canonical JSON")
    return value


def _verify_transport_bindings_against_rows(
    rows: Sequence[Mapping[str, object]],
    bindings: Mapping[str, object],
    *,
    expected_endpoint: str | None = None,
) -> dict[str, object]:
    if (
        set(bindings) != _TRANSPORT_BINDING_FIELDS
        or bindings.get("schema_version") != TRANSPORT_BINDINGS_SCHEMA
    ):
        raise R8RunnerRefusal("transport binding top-level schema drifted")
    _self_hash(bindings, "bindings_sha256", "transport bindings")
    expected_calls: dict[str, str] = {}
    suite_calls_by_id: dict[str, Mapping[str, object]] = {}
    rows_by_identity: dict[tuple[str, str, str, str], Mapping[str, object]] = {}
    expected_items: set[tuple[str, str, str, str]] = set()
    for row in rows:
        receipt_sha = _self_hash(row, "run_receipt_sha256", "item-run receipt")
        item_identity = (
            str(row.get("run_id")), str(row.get("arm_id")),
            str(row.get("item_id")), receipt_sha,
        )
        if item_identity in expected_items:
            raise R8RunnerRefusal("draft repeats an item-run identity")
        expected_items.add(item_identity)
        rows_by_identity[item_identity] = row
        calls = row.get("calls")
        assert isinstance(calls, list)
        for call in calls:
            assert isinstance(call, Mapping)
            physical_id = str(call.get("physical_call_id"))
            call_sha = str(call.get("receipt_sha256"))
            if physical_id in expected_calls:
                raise R8RunnerRefusal("draft repeats a physical call identity")
            expected_calls[physical_id] = call_sha
            suite_calls_by_id[physical_id] = call

    accepted = bindings.get("accepted_calls")
    spool = bindings.get("spool_bindings")
    item_bindings = bindings.get("item_run_bindings")
    if not all(isinstance(value, list) for value in (accepted, spool, item_bindings)):
        raise R8RunnerRefusal("transport binding arrays are absent")
    accepted_by_id: dict[str, Mapping[str, object]] = {}
    accepted_keys = {
        "physical_call_id", "intent_sha256", "request_sha256", "response_sha256",
        "model_response_sha256", "call_receipt_sha256", "response_status",
        "intent_bytes_b64", "request_bytes_b64", "response_body_b64",
        "model_response_bytes_b64",
    }
    for raw in accepted:
        if not isinstance(raw, Mapping) or set(raw) != accepted_keys:
            raise R8RunnerRefusal("accepted-call binding shape drifted")
        physical_id = str(raw.get("physical_call_id"))
        if physical_id in accepted_by_id or physical_id not in expected_calls:
            raise R8RunnerRefusal("accepted-call identity repeats or is foreign")
        preimages: dict[str, bytes] = {}
        for field, payload in (
            ("intent_sha256", "intent_bytes_b64"),
            ("request_sha256", "request_bytes_b64"),
            ("response_sha256", "response_body_b64"),
            ("model_response_sha256", "model_response_bytes_b64"),
        ):
            preimage = _decoded_bytes(raw.get(payload), payload)
            if hashlib.sha256(preimage).hexdigest() != raw.get(field):
                raise R8RunnerRefusal("accepted-call byte preimage drifted")
            preimages[field] = preimage
        if (
            raw.get("call_receipt_sha256") != expected_calls[physical_id]
            or raw.get("response_status") != 200
        ):
            raise R8RunnerRefusal("accepted-call receipt differs from suite draft")
        suite_call = suite_calls_by_id[physical_id]
        intent = _strict_json_bytes(
            preimages["intent_sha256"], "accepted intent", canonical=True
        )
        if not isinstance(intent, Mapping) or set(intent) != {
            "schema_version", "spool_route", "call", "request_sha256",
            "output_schema_sha256",
        } or intent.get("schema_version") != TRANSPORT_SCHEMA:
            raise R8RunnerRefusal("accepted intent schema drifted")
        intent_call = intent.get("call")
        if not isinstance(intent_call, Mapping) or set(intent_call) != {
            "physical_call_id", "run_id", "arm_id", "item_id", "call_index",
            "function_id", "model", "model_revision", "system_prompt",
            "input_type", "input_payload", "output_type", "max_output_tokens",
        }:
            raise R8RunnerRefusal("accepted intent call shape drifted")
        for key in (
            "physical_call_id", "run_id", "arm_id", "item_id", "call_index",
            "function_id", "model", "model_revision", "input_type",
            "input_payload", "output_type",
        ):
            if intent_call.get(key) != suite_call.get(key):
                raise R8RunnerRefusal(f"accepted intent differs from suite call: {key}")
        prompt = intent_call.get("system_prompt")
        if (
            not isinstance(prompt, str)
            or canonical_sha256({"prompt": prompt}) != suite_call.get("prompt_sha256")
            or intent_call.get("max_output_tokens")
            != suite_call.get("allowed_output_tokens")
            or intent.get("request_sha256") != raw.get("request_sha256")
            or not str(intent.get("spool_route", "")).endswith(physical_id)
            or intent.get("output_schema_sha256")
            != output_schema_sha256(str(suite_call.get("output_type")))
        ):
            raise R8RunnerRefusal("accepted intent prompt/request contract drifted")
        try:
            model_call = ModelCallV1(**dict(intent_call))
        except TypeError as error:
            raise R8RunnerRefusal("accepted intent cannot reconstruct the model call") from error
        expected_request = canonical_json(
            DurableSpoolJSONPort._request_body(model_call)
        ).encode("utf-8")
        if preimages["request_sha256"] != expected_request:
            raise R8RunnerRefusal("accepted HTTP request differs from model call")

        model_response = _strict_json_bytes(
            preimages["model_response_sha256"],
            "accepted normalized model response",
            canonical=True,
        )
        if not isinstance(model_response, Mapping) or set(model_response) != {
            "payload", "model", "model_revision", "input_tokens", "output_tokens",
            "latency_ms", "cache_status", "retries",
        }:
            raise R8RunnerRefusal("accepted normalized model response shape drifted")
        response_to_call = {
            "payload": "output_payload", "model": "model",
            "model_revision": "model_revision", "input_tokens": "input_tokens",
            "output_tokens": "output_tokens", "latency_ms": "latency_ms",
            "cache_status": "cache_status", "retries": "retries",
        }
        if any(
            model_response.get(response_key) != suite_call.get(call_key)
            for response_key, call_key in response_to_call.items()
        ):
            raise R8RunnerRefusal("normalized model response differs from suite call")
        validate_port(str(suite_call.get("output_type")), model_response.get("payload"))

        response = _strict_json_bytes(
            preimages["response_sha256"], "accepted raw HTTP response", canonical=False
        )
        if not isinstance(response, Mapping):
            raise R8RunnerRefusal("accepted raw HTTP response is not an object")
        choices = response.get("choices")
        usage = response.get("usage")
        if (
            response.get("model") != suite_call.get("model")
            or not isinstance(choices, list)
            or len(choices) != 1
            or not isinstance(usage, Mapping)
            or not isinstance(choices[0], Mapping)
            or choices[0].get("finish_reason") != "stop"
            or not isinstance(choices[0].get("message"), Mapping)
            or not isinstance(choices[0]["message"].get("content"), str)
        ):
            raise R8RunnerRefusal("accepted raw HTTP response envelope drifted")
        raw_payload = _strict_json_bytes(
            choices[0]["message"]["content"].encode("utf-8"),
            "accepted raw response content",
            canonical=False,
        )
        if (
            raw_payload != model_response.get("payload")
            or usage.get("prompt_tokens") != suite_call.get("input_tokens")
            or usage.get("completion_tokens") != suite_call.get("output_tokens")
        ):
            raise R8RunnerRefusal("raw HTTP response differs from normalized suite output")
        accepted_by_id[physical_id] = raw
    if set(accepted_by_id) != set(expected_calls):
        raise R8RunnerRefusal("accepted-call bindings do not exactly cover the draft")

    spool_by_id: dict[str, Mapping[str, object]] = {}
    spool_keys = {
        "physical_call_id", "intent_sha256", "request_sha256", "response_sha256",
    }
    for raw in spool:
        if not isinstance(raw, Mapping) or set(raw) != spool_keys:
            raise R8RunnerRefusal("spool binding shape drifted")
        physical_id = str(raw.get("physical_call_id"))
        counterpart = accepted_by_id.get(physical_id)
        if physical_id in spool_by_id or counterpart is None or any(
            raw.get(key) != counterpart.get(key)
            for key in ("intent_sha256", "request_sha256", "response_sha256")
        ):
            raise R8RunnerRefusal("spool and accepted-call bindings differ")
        spool_by_id[physical_id] = raw
    if set(spool_by_id) != set(expected_calls):
        raise R8RunnerRefusal("spool bindings do not exactly cover the draft")

    observed_items: set[tuple[str, str, str, str]] = set()
    for raw in item_bindings:
        if not isinstance(raw, Mapping) or set(raw) != {
            "run_id", "arm_id", "item_id", "run_receipt_sha256",
        }:
            raise R8RunnerRefusal("item-run binding shape drifted")
        identity = (
            str(raw.get("run_id")), str(raw.get("arm_id")),
            str(raw.get("item_id")), str(raw.get("run_receipt_sha256")),
        )
        if identity in observed_items:
            raise R8RunnerRefusal("item-run binding repeats")
        observed_items.add(identity)
    if observed_items != expected_items:
        raise R8RunnerRefusal("durable item-run bindings differ from suite rows")

    auxiliary = bindings.get("accepted_call_auxiliary_preimages")
    spool_preimages = bindings.get("spool_call_preimages")
    item_preimages = bindings.get("item_run_preimages")
    events = bindings.get("attempt_events")
    if not all(
        isinstance(value, list)
        for value in (auxiliary, spool_preimages, item_preimages, events)
    ):
        raise R8RunnerRefusal("transport enriched preimage arrays are absent")
    assert isinstance(auxiliary, list)
    assert isinstance(spool_preimages, list)
    assert isinstance(item_preimages, list)
    assert isinstance(events, list)
    if accepted != sorted(accepted, key=lambda item: str(item["physical_call_id"])):
        raise R8RunnerRefusal("accepted-call exports are not canonically sorted")
    if spool != sorted(spool, key=lambda item: str(item["physical_call_id"])):
        raise R8RunnerRefusal("spool bindings are not canonically sorted")
    if item_bindings != sorted(
        item_bindings,
        key=lambda item: (
            str(item["run_id"]), str(item["arm_id"]), str(item["item_id"]),
        ),
    ):
        raise R8RunnerRefusal("item-run bindings are not canonically sorted")

    auxiliary_by_id: dict[str, Mapping[str, object]] = {}
    for raw in auxiliary:
        if not isinstance(raw, Mapping) or set(raw) != {
            "physical_call_id", "endpoint", "response_headers_sha256",
            "response_headers_b64", "call_receipt_bytes_sha256",
            "call_receipt_bytes_b64",
        }:
            raise R8RunnerRefusal("accepted-call auxiliary shape drifted")
        physical_id = str(raw.get("physical_call_id"))
        if physical_id in auxiliary_by_id or physical_id not in suite_calls_by_id:
            raise R8RunnerRefusal("accepted-call auxiliary identity drifted")
        headers = _decoded_bytes(raw.get("response_headers_b64"), "response headers")
        receipt_bytes = _decoded_bytes(
            raw.get("call_receipt_bytes_b64"), "call receipt bytes"
        )
        if (
            hashlib.sha256(headers).hexdigest()
            != raw.get("response_headers_sha256")
            or hashlib.sha256(receipt_bytes).hexdigest()
            != raw.get("call_receipt_bytes_sha256")
        ):
            raise R8RunnerRefusal("accepted-call auxiliary byte hash drifted")
        receipt = _strict_json_bytes(
            receipt_bytes, "accepted call receipt", canonical=True
        )
        if (
            not isinstance(receipt, Mapping)
            or dict(receipt) != dict(suite_calls_by_id[physical_id])
            or _self_hash(receipt, "receipt_sha256", "accepted call receipt")
            != accepted_by_id[physical_id].get("call_receipt_sha256")
        ):
            raise R8RunnerRefusal("accepted call-receipt bytes differ from suite semantics")
        if expected_endpoint is not None and raw.get("endpoint") != (
            f"{expected_endpoint.rstrip('/')}/v1/hswm/calls/{physical_id}"
        ):
            raise R8RunnerRefusal("accepted-call endpoint differs from execution policy")
        auxiliary_by_id[physical_id] = raw
    if set(auxiliary_by_id) != set(expected_calls):
        raise R8RunnerRefusal("accepted-call auxiliaries do not cover the draft")

    spool_preimages_by_id: dict[str, Mapping[str, object]] = {}
    for raw in spool_preimages:
        if not isinstance(raw, Mapping) or set(raw) != {
            "physical_call_id", "intent_sha256", "request_sha256",
            "response_sha256", "status", "response_status", "request_bytes_b64",
            "response_headers_sha256", "response_headers_b64", "response_body_b64",
            "error_class",
        }:
            raise R8RunnerRefusal("spool preimage shape drifted")
        physical_id = str(raw.get("physical_call_id"))
        accepted_row = accepted_by_id.get(physical_id)
        if physical_id in spool_preimages_by_id or accepted_row is None:
            raise R8RunnerRefusal("spool preimage identity drifted")
        request_bytes = _decoded_bytes(raw.get("request_bytes_b64"), "spool request")
        response_headers = _decoded_bytes(
            raw.get("response_headers_b64"), "spool response headers"
        )
        response_body = _decoded_bytes(raw.get("response_body_b64"), "spool response")
        if (
            raw.get("status") != "COMPLETE"
            or raw.get("response_status") != 200
            or raw.get("error_class") is not None
            or any(
                raw.get(key) != accepted_row.get(key)
                for key in (
                    "intent_sha256", "request_sha256", "response_sha256",
                )
            )
            or hashlib.sha256(request_bytes).hexdigest() != raw.get("request_sha256")
            or hashlib.sha256(response_headers).hexdigest()
            != raw.get("response_headers_sha256")
            or hashlib.sha256(response_body).hexdigest() != raw.get("response_sha256")
            or raw.get("request_bytes_b64") != accepted_row.get("request_bytes_b64")
            or raw.get("response_body_b64") != accepted_row.get("response_body_b64")
        ):
            raise R8RunnerRefusal("spool preimage differs from accepted-call bytes")
        spool_preimages_by_id[physical_id] = raw
    if set(spool_preimages_by_id) != set(expected_calls):
        raise R8RunnerRefusal("spool preimages do not cover the draft")

    item_preimages_by_identity: dict[tuple[str, str, str, str], Mapping[str, object]] = {}
    for raw in item_preimages:
        if not isinstance(raw, Mapping) or set(raw) != {
            "run_id", "arm_id", "item_id", "run_receipt_sha256",
            "item_run_bytes_sha256", "item_run_bytes_b64",
        }:
            raise R8RunnerRefusal("item-run preimage shape drifted")
        identity = (
            str(raw.get("run_id")), str(raw.get("arm_id")),
            str(raw.get("item_id")), str(raw.get("run_receipt_sha256")),
        )
        item_bytes = _decoded_bytes(raw.get("item_run_bytes_b64"), "item-run bytes")
        item_value = _strict_json_bytes(item_bytes, "item-run bytes", canonical=True)
        if (
            identity in item_preimages_by_identity
            or identity not in rows_by_identity
            or hashlib.sha256(item_bytes).hexdigest()
            != raw.get("item_run_bytes_sha256")
            or not isinstance(item_value, Mapping)
            or dict(item_value) != dict(rows_by_identity[identity])
            or _self_hash(item_value, "run_receipt_sha256", "item-run preimage")
            != identity[3]
        ):
            raise R8RunnerRefusal("item-run preimage differs from suite row")
        item_preimages_by_identity[identity] = raw
    if set(item_preimages_by_identity) != expected_items:
        raise R8RunnerRefusal("item-run preimages do not cover the suite")

    previous = _EVENT_GENESIS
    event_states: dict[str, str | None] = {}
    for sequence, raw in enumerate(events):
        if not isinstance(raw, Mapping) or set(raw) != {
            "sequence", "physical_call_id", "event_type",
            "previous_event_sha256", "event_sha256", "event_bytes_b64",
        }:
            raise R8RunnerRefusal("attempt-event export shape drifted")
        physical_id = str(raw.get("physical_call_id"))
        event_type = str(raw.get("event_type"))
        event_bytes = _decoded_bytes(raw.get("event_bytes_b64"), "attempt event")
        event_value = _strict_json_bytes(event_bytes, "attempt event", canonical=True)
        allowed = _EVENT_TRANSITIONS.get(event_type)
        if (
            raw.get("sequence") != sequence
            or physical_id not in expected_calls
            or raw.get("previous_event_sha256") != previous
            or hashlib.sha256(event_bytes).hexdigest() != raw.get("event_sha256")
            or not isinstance(event_value, Mapping)
            or set(event_value) != {
                "schema_version", "sequence", "physical_call_id", "event_type",
                "detail", "previous_event_sha256",
            }
            or event_value.get("schema_version") != DURABLE_CALL_SCHEMA
            or event_value.get("sequence") != sequence
            or event_value.get("physical_call_id") != physical_id
            or event_value.get("event_type") != event_type
            or event_value.get("previous_event_sha256") != previous
            or not isinstance(event_value.get("detail"), Mapping)
            or allowed is None
            or event_states.get(physical_id) not in allowed
        ):
            raise R8RunnerRefusal("attempt-event chain semantics drifted")
        event_states[physical_id] = event_type
        previous = str(raw.get("event_sha256"))
    if set(event_states) != set(expected_calls) or any(
        state != "ACCEPTED" for state in event_states.values()
    ):
        raise R8RunnerRefusal("attempt-event tails do not cover accepted calls")

    accepted_minimal = [
        {
            key: raw[key]
            for key in (
                "physical_call_id", "intent_sha256", "request_sha256",
                "response_sha256", "call_receipt_sha256",
            )
        }
        for raw in accepted
    ]
    roots = {
        "accepted_call_root_sha256": canonical_sha256(accepted_minimal),
        "accepted_call_export_root_sha256": canonical_sha256(accepted),
        "accepted_call_auxiliary_root_sha256": canonical_sha256(auxiliary),
        "spool_binding_root_sha256": canonical_sha256(spool),
        "spool_preimage_root_sha256": canonical_sha256(spool_preimages),
        "item_run_root_sha256": canonical_sha256(item_bindings),
        "item_run_preimage_root_sha256": canonical_sha256(item_preimages),
        "attempt_event_root_sha256": canonical_sha256(events),
        "event_chain_tip_sha256": previous,
    }
    if any(bindings.get(key) != value for key, value in roots.items()):
        raise R8RunnerRefusal("transport canonical or enriched root drifted")
    return roots


def _candidate(raw: Mapping[str, object], label: str) -> EvidenceCandidateV1:
    expected = {"bond_id", "evidence_id", "source_entity_id", "content", "observable"}
    if set(raw) != expected or not isinstance(raw.get("observable"), dict):
        raise R8RunnerRefusal(f"{label} candidate schema drifted")
    return EvidenceCandidateV1(
        bond_id=str(raw["bond_id"]),
        evidence_id=str(raw["evidence_id"]),
        source_entity_id=_sha(raw["source_entity_id"], f"{label} source entity"),
        content=str(raw["content"]),
        observable=dict(raw["observable"]),
    )


def _item(raw: Mapping[str, object], label: str) -> FunctionNetworkItemV1:
    expected = {
        "item_id", "query_text", "allowed_evidence_types", "candidates",
        "component_id", "max_evidence_items", "max_input_tokens",
        "max_output_tokens_per_call",
    }
    if set(raw) != expected:
        raise R8RunnerRefusal(f"{label} item schema drifted")
    candidates_raw = raw.get("candidates")
    evidence_types = raw.get("allowed_evidence_types")
    if not isinstance(candidates_raw, list) or not candidates_raw:
        raise R8RunnerRefusal(f"{label} has no candidates")
    if any(not isinstance(value, Mapping) for value in candidates_raw):
        raise R8RunnerRefusal(f"{label} candidate is not an object")
    if not isinstance(evidence_types, list) or not evidence_types or any(
        not isinstance(value, str) or not value for value in evidence_types
    ):
        raise R8RunnerRefusal(f"{label} evidence types drifted")
    return FunctionNetworkItemV1(
        item_id=str(raw["item_id"]),
        query_text=str(raw["query_text"]),
        allowed_evidence_types=tuple(evidence_types),
        candidates=tuple(_candidate(value, label) for value in candidates_raw),
        max_evidence_items=_positive(raw["max_evidence_items"], "max_evidence_items"),
        max_input_tokens=_positive(raw["max_input_tokens"], "max_input_tokens"),
        max_output_tokens_per_call=_positive(
            raw["max_output_tokens_per_call"], "max_output_tokens_per_call"
        ),
        component_id=_sha(raw["component_id"], f"{label} component"),
    )


def _derive_components(
    raw_items: Sequence[Mapping[str, object]],
) -> tuple[dict[str, str], set[str]]:
    parent = {str(item["item_id"]): str(item["item_id"]) for item in raw_items}

    def find(item_id: str) -> str:
        while parent[item_id] != item_id:
            parent[item_id] = parent[parent[item_id]]
            item_id = parent[item_id]
        return item_id

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    owner: dict[str, str] = {}
    entities_by_item: dict[str, set[str]] = {}
    for raw in raw_items:
        item_id = str(raw["item_id"])
        candidates = raw["candidates"]
        assert isinstance(candidates, list)
        entities = {_sha(value["source_entity_id"], "source entity") for value in candidates}
        entities_by_item[item_id] = entities
        for entity in entities:
            union(item_id, owner.setdefault(entity, item_id))
    entities_by_root: dict[str, set[str]] = {}
    for item_id, entities in entities_by_item.items():
        entities_by_root.setdefault(find(item_id), set()).update(entities)
    component_by_root = {
        root: canonical_sha256(
            {
                "schema_version": "hswm-source-entity-connected-component/v1",
                "source_entity_ids": sorted(entities),
            }
        )
        for root, entities in entities_by_root.items()
    }
    by_item = {item_id: component_by_root[find(item_id)] for item_id in parent}
    return by_item, set(owner)


def _registries(
    *,
    protocol_path: Path | None = None,
    protocol: Mapping[str, object] | None = None,
    model: str,
    model_revision: str,
) -> dict[str, FunctionRegistryV1]:
    if protocol is None and protocol_path is None:
        raise R8RunnerRefusal("protocol preimage is absent")
    return {
        arm: (
            build_registry_from_protocol(
                protocol,
                model=model,
                model_revision=model_revision,
                prompt_overrides=_arm_overrides(arm),
            )
            if protocol is not None
            else build_registry(
                Path(protocol_path),
                model=model,
                model_revision=model_revision,
                prompt_overrides=_arm_overrides(arm),
            )
        )
        for arm in F1_ARMS
    }


def build_development_execution_lock(
    manifest: Mapping[str, object],
    *,
    protocol_path: Path,
    protocol: Mapping[str, object] | None = None,
    selection_receipt_sha256: str,
    prior_exposure_receipt_sha256: str,
    aborted_attempt_exposure_receipt_sha256: str,
    public_source_receipt_sha256: str,
    gold_source_receipt_sha256: str,
    gold_sha256: str,
    evaluator_receipt_sha256: str,
    db_genesis_receipt_sha256: str,
    environment_receipt_sha256: str,
    dependency_receipt_sha256: str,
    environment_dependency_compatibility_root_sha256: str,
    environment_dependency_bundle_sha256: str,
    hswm_commit: str,
    result_contract_sha256: str,
    judge_core_sha256: str,
    judge_core_file_sha256: str,
    token_envelope_derivation_receipt_sha256: str,
    deployment_binding: ModelDeploymentBinding,
    forbidden_prior_item_ids: Sequence[str],
    forbidden_prior_source_entity_ids: Sequence[str],
    forbidden_prior_component_ids: Sequence[str],
    execution_policy: Mapping[str, object],
) -> dict[str, object]:
    if manifest.get("schema_version") != MANIFEST_SCHEMA or manifest.get("mode") != "development":
        raise R8RunnerRefusal("development execution lock requires manifest v3/development")
    if manifest.get("preregistration_artifact_sha256") is not None:
        raise R8RunnerRefusal("development execution lock cannot bind preregistration")
    normalized_policy = _validate_execution_policy_value(execution_policy)
    for value, label in (
        (selection_receipt_sha256, "selection receipt"),
        (prior_exposure_receipt_sha256, "prior-exposure receipt"),
        (
            aborted_attempt_exposure_receipt_sha256,
            "aborted-attempt exposure receipt",
        ),
        (public_source_receipt_sha256, "public-source receipt"),
        (gold_source_receipt_sha256, "gold-source receipt"),
        (gold_sha256, "gold"),
        (evaluator_receipt_sha256, "evaluator receipt"),
        (db_genesis_receipt_sha256, "DB genesis receipt"),
        (environment_receipt_sha256, "environment receipt"),
        (dependency_receipt_sha256, "dependency receipt"),
        (
            environment_dependency_compatibility_root_sha256,
            "environment/dependency compatibility root",
        ),
        (environment_dependency_bundle_sha256, "environment/dependency bundle"),
        (result_contract_sha256, "result contract"),
        (judge_core_sha256, "judge core"),
        (judge_core_file_sha256, "judge core file"),
        (
            token_envelope_derivation_receipt_sha256,
            "token-envelope derivation receipt",
        ),
    ):
        _sha(value, label)
    if not isinstance(hswm_commit, str) or _GIT_COMMIT.fullmatch(hswm_commit) is None:
        raise R8RunnerRefusal("hswm_commit must be an exact lowercase Git SHA")
    model = str(manifest.get("model"))
    revision = str(manifest.get("model_revision"))
    if (
        deployment_binding.served_model != model
        or deployment_binding.model_revision != revision
    ):
        raise R8RunnerRefusal(
            "deployment identity differs from the development manifest"
        )
    registries = _registries(
        protocol_path=protocol_path,
        protocol=protocol,
        model=model,
        model_revision=revision,
    )
    raw_items = manifest.get("items")
    if not isinstance(raw_items, list) or not raw_items or any(
        not isinstance(value, Mapping) for value in raw_items
    ):
        raise R8RunnerRefusal("development manifest items are invalid")
    items = [_item(value, f"item {index}") for index, value in enumerate(raw_items)]
    component_by_item, source_entities = _derive_components(raw_items)
    if any(
        value.get("component_id") != component_by_item[str(value["item_id"])]
        for value in raw_items
    ):
        raise R8RunnerRefusal("development manifest component identity drifted")
    item_ids = sorted(item.item_id for item in items)
    cohort_root = canonical_sha256(item_ids)
    candidate_root = canonical_sha256(
        [
            {
                "item_id": item.item_id,
                "candidate_universe_sha256": item.candidate_universe_sha256,
            }
            for item in sorted(items, key=lambda value: value.item_id)
        ]
    )
    envelope = manifest.get("token_envelope")
    if not isinstance(envelope, Mapping):
        raise R8RunnerRefusal("development manifest token envelope is absent")
    input_caps = envelope.get("per_call_input_caps")
    output_caps = envelope.get("per_call_output_caps")
    if not isinstance(input_caps, Mapping) or not isinstance(output_caps, Mapping):
        raise R8RunnerRefusal("development envelope caps are absent")
    protocol_roots = {registry.protocol_sha256 for registry in registries.values()}
    if len(protocol_roots) != 1:
        raise R8RunnerRefusal("development registries disagree on protocol")
    prior_items = _validate_prior_list(
        list(forbidden_prior_item_ids), "forbidden prior item IDs", sha_values=False
    )
    prior_entities = _validate_prior_list(
        list(forbidden_prior_source_entity_ids),
        "forbidden prior source-entity IDs",
        sha_values=True,
    )
    prior_components = _validate_prior_list(
        list(forbidden_prior_component_ids),
        "forbidden prior component IDs",
        sha_values=True,
    )
    if set(item_ids) & set(prior_items) or source_entities & set(prior_entities) or set(component_by_item.values()) & set(prior_components):
        raise R8RunnerRefusal("development manifest overlaps prior exposure")
    unsigned = {
        "schema_version": EXECUTION_LOCK_SCHEMA,
        "purpose": "DEVELOPMENT_POWER_PILOT",
        "run_id": manifest["run_id"],
        "mode": "development",
        "manifest_sha256": canonical_sha256(manifest),
        "preregistration_artifact_sha256": None,
        "selection_receipt_sha256": selection_receipt_sha256,
        "prior_exposure_receipt_sha256": prior_exposure_receipt_sha256,
        "aborted_attempt_exposure_receipt_sha256": (
            aborted_attempt_exposure_receipt_sha256
        ),
        "public_source_receipt_sha256": public_source_receipt_sha256,
        "gold_source_receipt_sha256": gold_source_receipt_sha256,
        "gold_sha256": gold_sha256,
        "evaluator_receipt_sha256": evaluator_receipt_sha256,
        "db_genesis_receipt_sha256": db_genesis_receipt_sha256,
        "environment_receipt_sha256": environment_receipt_sha256,
        "dependency_receipt_sha256": dependency_receipt_sha256,
        "environment_dependency_compatibility_root_sha256": (
            environment_dependency_compatibility_root_sha256
        ),
        "environment_dependency_bundle_sha256": (
            environment_dependency_bundle_sha256
        ),
        "hswm_commit": hswm_commit,
        "result_contract_sha256": result_contract_sha256,
        "judge_core_sha256": judge_core_sha256,
        "judge_core_file_sha256": judge_core_file_sha256,
        "model": model,
        "model_revision": revision,
        "upstream_endpoint": deployment_binding.upstream_endpoint,
        "deployment_receipt_sha256": (
            deployment_binding.deployment_receipt_sha256
        ),
        "deployment_id": deployment_binding.deployment_id,
        "served_model": deployment_binding.served_model,
        "protocol_sha256": next(iter(protocol_roots)),
        "registries_root_sha256": canonical_sha256(
            {arm: registries[arm].registry_sha256 for arm in F1_ARMS}
        ),
        "token_envelope_sha256": canonical_sha256(envelope),
        "token_envelope_derivation_receipt_sha256": (
            token_envelope_derivation_receipt_sha256
        ),
        "generation_policy_sha256": canonical_sha256(GENERATION_POLICY),
        "cohort_root_sha256": cohort_root,
        "candidate_universe_root_sha256": candidate_root,
        "forbidden_prior_item_ids": prior_items,
        "forbidden_prior_source_entity_ids": prior_entities,
        "forbidden_prior_component_ids": prior_components,
        "execution_policy": normalized_policy,
        "gates": {
            "expected_items": len(items),
            "expected_arms": len(F1_ARMS),
            "expected_item_runs": len(items) * len(F1_ARMS),
            "expected_calls": len(items) * len(F1_ARMS) * 3,
            "per_call_input_caps": dict(input_caps),
            "per_call_output_caps": dict(output_caps),
            "total_input_tokens_per_run": sum(int(value) for value in input_caps.values()),
            "total_allowed_output_tokens_per_run": sum(int(value) for value in output_caps.values()),
            "token_spread_max": int(manifest["token_tolerance"]),
        },
    }
    return {**unsigned, "lock_sha256": canonical_sha256(unsigned)}


def validate_manifest_v3(
    manifest: Mapping[str, object],
    *,
    execution_lock: Mapping[str, object],
    token_meter: TokenMeter,
    registries: Mapping[str, FunctionRegistryV1],
) -> tuple[dict[str, object], list[FunctionNetworkItemV1], dict[str, object]]:
    expected = {
        "schema_version", "run_id", "mode", "model", "model_revision",
        "token_tolerance", "state_capacity_bytes", "state_bytes_by_arm",
        "preregistration_artifact_sha256", "generation_policy", "token_envelope",
        "items",
    }
    if set(manifest) != expected or manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise R8RunnerRefusal("unsupported manifest v3 shape")
    lock_sha = _self_hash(execution_lock, "lock_sha256", "execution lock")
    mode = manifest.get("mode")
    if mode == "development":
        if (
            set(execution_lock) != _DEVELOPMENT_LOCK_FIELDS
            or execution_lock.get("schema_version") != EXECUTION_LOCK_SCHEMA
            or execution_lock.get("purpose") != "DEVELOPMENT_POWER_PILOT"
        ):
            raise R8RunnerRefusal("development execution-lock shape drifted")
    elif mode == "sealed":
        if (
            set(execution_lock) != _SEALED_LOCK_FIELDS
            or execution_lock.get("schema_version") != SEALED_LOCK_SCHEMA
            or execution_lock.get("purpose") != SEALED_LOCK_PURPOSE
            or execution_lock.get("experiment_tag") != SEALED_EXPERIMENT_TAG
            or execution_lock.get("closes_question") != SEALED_CLOSES_QUESTION
            or execution_lock.get("run_id") != SEALED_RUN_ID
            or manifest.get("run_id") != SEALED_RUN_ID
        ):
            raise R8RunnerRefusal("unsupported sealed r8/try3 measurement lock")
    else:
        raise R8RunnerRefusal("manifest mode must be development or sealed")
    _validate_execution_policy_value(execution_lock.get("execution_policy"))
    _deployment_binding_from_lock(execution_lock)
    for field in _DEVELOPMENT_LOCK_FIELDS:
        if field.endswith("_sha256") and field != "preregistration_artifact_sha256":
            _sha(execution_lock.get(field), f"execution-lock {field}")
    hswm_commit = execution_lock.get("hswm_commit")
    if not isinstance(hswm_commit, str) or _GIT_COMMIT.fullmatch(hswm_commit) is None:
        raise R8RunnerRefusal("execution-lock hswm_commit is not exact")
    _validate_prior_list(
        execution_lock.get("forbidden_prior_item_ids"),
        "forbidden prior item IDs",
        sha_values=False,
    )
    _validate_prior_list(
        execution_lock.get("forbidden_prior_source_entity_ids"),
        "forbidden prior source-entity IDs",
        sha_values=True,
    )
    _validate_prior_list(
        execution_lock.get("forbidden_prior_component_ids"),
        "forbidden prior component IDs",
        sha_values=True,
    )
    manifest_sha = canonical_sha256(manifest)
    for key in ("run_id", "mode", "model", "model_revision", "preregistration_artifact_sha256"):
        if manifest.get(key) != execution_lock.get(key):
            raise R8RunnerRefusal(f"manifest {key} differs from execution lock")
    if manifest_sha != execution_lock.get("manifest_sha256"):
        raise R8RunnerRefusal("manifest bytes differ from execution lock")
    if mode == "sealed":
        _sha(manifest.get("preregistration_artifact_sha256"), "preregistration artifact")
    elif mode == "development":
        if manifest.get("preregistration_artifact_sha256") is not None:
            raise R8RunnerRefusal("development pilot cannot claim preregistration")
    if manifest.get("generation_policy") != GENERATION_POLICY:
        raise R8RunnerRefusal("generation policy drifted")
    if canonical_sha256(GENERATION_POLICY) != execution_lock.get("generation_policy_sha256"):
        raise R8RunnerRefusal("generation policy is not lock-bound")
    envelope = validate_token_envelope(manifest.get("token_envelope"), arms=F1_ARMS)
    check_tokenizer_identity(envelope["tokenizer"], token_meter)
    if canonical_sha256(envelope) != execution_lock.get("token_envelope_sha256"):
        raise R8RunnerRefusal("token envelope differs from execution lock")
    state_rows = manifest.get("state_bytes_by_arm")
    capacity = manifest.get("state_capacity_bytes")
    if (
        isinstance(capacity, bool)
        or not isinstance(capacity, int)
        or capacity < 0
        or not isinstance(state_rows, dict)
        or set(state_rows) != set(F1_ARMS)
        or any(
            isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= capacity
            for value in state_rows.values()
        )
    ):
        raise R8RunnerRefusal("persistent-state contract drifted")
    raw_items = manifest.get("items")
    gates = execution_lock.get("gates")
    if not isinstance(raw_items, list) or not isinstance(gates, Mapping):
        raise R8RunnerRefusal("manifest items or lock gates are absent")
    tolerance = _nonnegative(manifest.get("token_tolerance"), "token_tolerance")
    _validate_lock_gates(
        gates,
        item_count=len(raw_items),
        token_envelope=envelope,
        token_tolerance=tolerance,
    )
    if any(not isinstance(value, Mapping) for value in raw_items):
        raise R8RunnerRefusal("manifest item is not an object")
    source_input_budget = sum(
        int(value) for value in envelope["per_call_input_caps"].values()
    )
    source_output_budget = max(
        int(value) for value in envelope["per_call_output_caps"].values()
    )
    if any(
        value.get("max_input_tokens") != source_input_budget
        or value.get("max_output_tokens_per_call") != source_output_budget
        for value in raw_items
    ):
        raise R8RunnerRefusal("manifest source budgets differ from the frozen envelope")
    item_ids = [str(value["item_id"]) for value in raw_items]
    if len(set(item_ids)) != len(item_ids):
        raise R8RunnerRefusal("manifest item IDs repeat")
    items = [_item(value, f"item {index}") for index, value in enumerate(raw_items)]
    component_by_item, source_entities = _derive_components(raw_items)
    for value in raw_items:
        if value.get("component_id") != component_by_item[str(value["item_id"])]:
            raise R8RunnerRefusal("manifest component was not source-derived")
    cohort_root = canonical_sha256(sorted(item_ids))
    candidate_root = canonical_sha256(
        [
            {
                "item_id": item.item_id,
                "candidate_universe_sha256": item.candidate_universe_sha256,
            }
            for item in sorted(items, key=lambda value: value.item_id)
        ]
    )
    if (
        cohort_root != execution_lock.get("cohort_root_sha256")
        or candidate_root != execution_lock.get("candidate_universe_root_sha256")
    ):
        raise R8RunnerRefusal("cohort or candidate root differs from execution lock")
    forbidden_items = set(execution_lock.get("forbidden_prior_item_ids", []))
    forbidden_entities = set(execution_lock.get("forbidden_prior_source_entity_ids", []))
    forbidden_components = set(execution_lock.get("forbidden_prior_component_ids", []))
    if (
        set(item_ids) & forbidden_items
        or source_entities & forbidden_entities
        or set(component_by_item.values()) & forbidden_components
    ):
        raise R8RunnerRefusal("manifest overlaps a forbidden prior exposure")
    projection = enforce_projection(
        run_id=str(manifest["run_id"]),
        items=items,
        arms=F1_ARMS,
        registries=registries,
        meter=token_meter,
        envelope=envelope,
        token_tolerance=int(manifest["token_tolerance"]),
    )
    protocol_roots = {registry.protocol_sha256 for registry in registries.values()}
    if len(protocol_roots) != 1 or next(iter(protocol_roots)) != execution_lock.get("protocol_sha256"):
        raise R8RunnerRefusal("protocol differs from execution lock")
    registry_root = canonical_sha256(
        {arm: registries[arm].registry_sha256 for arm in F1_ARMS}
    )
    if registry_root != execution_lock.get("registries_root_sha256"):
        raise R8RunnerRefusal("registry root differs from execution lock")
    normalized = json.loads(json.dumps(manifest, ensure_ascii=False))
    normalized["token_envelope"] = envelope
    return normalized, items, {**projection, "execution_lock_sha256": lock_sha}


def _validate_registry_bundle(
    value: object, *, model: str, model_revision: str
) -> tuple[dict[str, dict[str, Mapping[str, object]]], str, str]:
    if not isinstance(value, Mapping) or set(value) != set(F1_ARMS):
        raise R8RunnerRefusal("suite registries do not exactly cover F1 arms")
    functions_by_arm: dict[str, dict[str, Mapping[str, object]]] = {}
    registry_hashes: dict[str, str] = {}
    protocol_hashes: set[str] = set()
    for arm in F1_ARMS:
        registry = value.get(arm)
        if (
            not isinstance(registry, Mapping)
            or set(registry) != _REGISTRY_FIELDS
            or registry.get("schema_version") != REGISTRY_SCHEMA
        ):
            raise R8RunnerRefusal(f"registry shape drifted for {arm}")
        registry_sha = _self_hash(registry, "registry_sha256", f"registry {arm}")
        protocol_hashes.add(_sha(registry.get("protocol_sha256"), "protocol"))
        raw_functions = registry.get("functions")
        if not isinstance(raw_functions, list) or len(raw_functions) != len(_FUNCTION_IDS):
            raise R8RunnerRefusal(f"registry function count drifted for {arm}")
        indexed: dict[str, Mapping[str, object]] = {}
        for index, raw in enumerate(raw_functions):
            if not isinstance(raw, Mapping) or set(raw) != _FUNCTION_FIELDS:
                raise R8RunnerRefusal(f"registry function shape drifted for {arm}")
            function_id = raw.get("function_id")
            prompt = raw.get("prompt")
            if (
                function_id != _FUNCTION_IDS[index]
                or function_id in indexed
                or raw.get("model") != model
                or raw.get("model_revision") != model_revision
                or not isinstance(prompt, str)
                or not prompt.strip()
                or raw.get("prompt_sha256") != canonical_sha256({"prompt": prompt})
                or not isinstance(raw.get("input_type"), str)
                or not isinstance(raw.get("output_type"), str)
            ):
                raise R8RunnerRefusal(f"registry function semantics drifted for {arm}")
            indexed[str(function_id)] = raw
        functions_by_arm[arm] = indexed
        registry_hashes[arm] = registry_sha
    if len(protocol_hashes) != 1:
        raise R8RunnerRefusal("suite registries disagree on protocol")
    return (
        functions_by_arm,
        next(iter(protocol_hashes)),
        canonical_sha256(registry_hashes),
    )


def _verify_call_receipt_local(
    value: object,
    *,
    run_id: str,
    arm_id: str,
    item_id: str,
    call_index: int,
    function: Mapping[str, object],
    input_cap: int,
    output_cap: int,
) -> str:
    if (
        not isinstance(value, Mapping)
        or set(value) != _CALL_RECEIPT_FIELDS
        or value.get("schema_version") != CALL_RECEIPT_SCHEMA
    ):
        raise R8RunnerRefusal("call receipt shape drifted")
    declared = _self_hash(value, "receipt_sha256", "call receipt")
    if (
        value.get("run_id") != run_id
        or value.get("arm_id") != arm_id
        or value.get("item_id") != item_id
        or value.get("call_index") != call_index
        or value.get("function_id") != function.get("function_id")
        or value.get("model") != function.get("model")
        or value.get("model_revision") != function.get("model_revision")
        or value.get("prompt_sha256") != function.get("prompt_sha256")
        or value.get("input_type") != function.get("input_type")
        or value.get("output_type") != function.get("output_type")
        or value.get("allowed_output_tokens") != output_cap
        or value.get("input_tokens") != input_cap
    ):
        raise R8RunnerRefusal("call receipt differs from registry or token envelope")
    try:
        normalized_input = validate_port(
            str(value.get("input_type")), value.get("input_payload")
        )
        normalized_output = validate_port(
            str(value.get("output_type")), value.get("output_payload")
        )
        input_digest = port_digest(str(value.get("input_type")), normalized_input)
        output_digest = port_digest(str(value.get("output_type")), normalized_output)
    except Exception as error:
        raise R8RunnerRefusal("call receipt typed-port validation failed") from error
    if (
        normalized_input != value.get("input_payload")
        or normalized_output != value.get("output_payload")
        or value.get("input_port_sha256") != input_digest
        or value.get("output_port_sha256") != output_digest
    ):
        raise R8RunnerRefusal("call receipt typed-port digest drifted")
    expected_physical_id = canonical_sha256(
        {
            "run_id": run_id,
            "arm_id": arm_id,
            "item_id": item_id,
            "call_index": call_index,
            "function_id": function["function_id"],
            "registry_prompt_sha256": function["prompt_sha256"],
            "input_port_sha256": input_digest,
        }
    )
    output_tokens = _nonnegative(value.get("output_tokens"), "output tokens")
    if (
        value.get("physical_call_id") != expected_physical_id
        or output_tokens > output_cap
        or value.get("cache_status") not in {"miss", "hit", "provider-unknown"}
    ):
        raise R8RunnerRefusal("call identity or output budget drifted")
    _nonnegative(value.get("latency_ms"), "call latency")
    _nonnegative(value.get("retries"), "call retries")
    return declared


def _verify_item_run_local(
    value: object,
    *,
    run_id: str,
    registry: Mapping[str, object],
    functions: Mapping[str, Mapping[str, object]],
    input_caps: Mapping[str, object],
    output_caps: Mapping[str, object],
    persistent_state_bytes: int,
) -> str:
    if (
        not isinstance(value, Mapping)
        or set(value) != _ITEM_RUN_FIELDS
        or value.get("schema_version") != RUN_SCHEMA
    ):
        raise R8RunnerRefusal("item-run receipt shape drifted")
    declared = _self_hash(value, "run_receipt_sha256", "item-run receipt")
    arm_id = value.get("arm_id")
    item_id = value.get("item_id")
    if (
        value.get("run_id") != run_id
        or not isinstance(arm_id, str)
        or arm_id not in F1_ARMS
        or not isinstance(item_id, str)
        or not item_id
        or value.get("registry_sha256") != registry.get("registry_sha256")
        or value.get("persistent_state_bytes") != persistent_state_bytes
    ):
        raise R8RunnerRefusal("item-run identity or registry binding drifted")
    _sha(value.get("candidate_universe_sha256"), "candidate universe")
    calls = value.get("calls")
    if not isinstance(calls, list) or len(calls) != len(_FUNCTION_IDS):
        raise R8RunnerRefusal("item run does not contain exactly three calls")
    for index, (call, function_id) in enumerate(zip(calls, _FUNCTION_IDS), start=1):
        _verify_call_receipt_local(
            call,
            run_id=run_id,
            arm_id=arm_id,
            item_id=item_id,
            call_index=index,
            function=functions[function_id],
            input_cap=_positive(input_caps.get(str(index)), "input cap"),
            output_cap=_positive(output_caps.get(str(index)), "output cap"),
        )
    try:
        answer = validate_port("AnswerEnvelopeV1", value.get("answer"))
    except Exception as error:
        raise R8RunnerRefusal("item-run answer port is invalid") from error
    if answer != calls[2].get("output_payload"):
        raise R8RunnerRefusal("item-run answer differs from third call output")
    selected = value.get("selected_bond_ids")
    proposal = calls[1].get("output_payload")
    if (
        not isinstance(selected, list)
        or any(not isinstance(item, str) or not item for item in selected)
        or len(selected) != len(set(selected))
        or not isinstance(proposal, Mapping)
    ):
        raise R8RunnerRefusal("item-run selected bonds are malformed")
    expected_selected = (
        [] if proposal.get("abstain") else list(proposal.get("ordered_bond_ids", []))
    )
    if selected != expected_selected:
        raise R8RunnerRefusal("item-run selected bonds differ from BF output")
    totals = {
        "total_input_tokens": sum(int(call["input_tokens"]) for call in calls),
        "total_output_tokens": sum(int(call["output_tokens"]) for call in calls),
        "total_allowed_output_tokens": sum(
            int(call["allowed_output_tokens"]) for call in calls
        ),
    }
    if any(value.get(key) != expected for key, expected in totals.items()):
        raise R8RunnerRefusal("item-run token totals drifted")
    return declared


def _token_parity_local(
    rows: Sequence[Mapping[str, object]],
    *,
    tolerance: int,
    envelope: Mapping[str, object],
) -> dict[str, object]:
    indexed: dict[str, dict[str, Mapping[str, object]]] = {}
    for row in rows:
        item_id, arm_id = str(row["item_id"]), str(row["arm_id"])
        if arm_id in indexed.setdefault(item_id, {}):
            raise R8RunnerRefusal("item/arm row repeats")
        indexed[item_id][arm_id] = row
    items: list[dict[str, object]] = []
    for item_id in sorted(indexed):
        arms = indexed[item_id]
        if set(arms) != set(F1_ARMS):
            raise R8RunnerRefusal("item rows do not exactly cover F1 arms")
        inputs = {arm: int(arms[arm]["total_input_tokens"]) for arm in F1_ARMS}
        outputs = {arm: int(arms[arm]["total_output_tokens"]) for arm in F1_ARMS}
        totals = {arm: inputs[arm] + outputs[arm] for arm in F1_ARMS}
        spread = max(totals.values()) - min(totals.values())
        input_spread = max(inputs.values()) - min(inputs.values())
        items.append(
            {
                "item_id": item_id,
                "input_tokens_by_arm": inputs,
                "output_tokens_by_arm": outputs,
                "total_tokens_by_arm": totals,
                "spread": spread,
                "input_spread": input_spread,
                "within_tolerance": spread <= tolerance,
            }
        )
    return {
        "per_call_input_caps": dict(envelope["per_call_input_caps"]),
        "per_call_output_caps": dict(envelope["per_call_output_caps"]),
        "input_spread_max": max(item["input_spread"] for item in items),
        "spread_max": max(item["spread"] for item in items),
        "all_within_tolerance": all(item["within_tolerance"] for item in items),
        "items": items,
    }


def _validate_projection_record(
    value: object,
    *,
    item_ids: Sequence[str],
    envelope: Mapping[str, object],
) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "projected_total_tokens_by_arm", "projected_spread", "items",
    }:
        raise R8RunnerRefusal("envelope projection shape drifted")
    totals = value.get("projected_total_tokens_by_arm")
    records = value.get("items")
    if (
        not isinstance(totals, Mapping)
        or set(totals) != set(F1_ARMS)
        or not isinstance(records, list)
        or len(records) != len(item_ids)
    ):
        raise R8RunnerRefusal("envelope projection coverage drifted")
    input_total = sum(int(item) for item in envelope["per_call_input_caps"].values())
    projections = envelope["projected_output_tokens_by_arm"]
    expected_totals = {
        arm: input_total + sum(int(item) for item in projections[arm].values())
        for arm in F1_ARMS
    }
    if (
        dict(totals) != expected_totals
        or value.get("projected_spread")
        != max(expected_totals.values()) - min(expected_totals.values())
    ):
        raise R8RunnerRefusal("envelope projected totals drifted")
    seen: set[str] = set()
    input_caps = envelope["per_call_input_caps"]
    for record in records:
        if not isinstance(record, Mapping) or set(record) != {
            "item_id", "projected_upper_bounds",
        }:
            raise R8RunnerRefusal("envelope projection item shape drifted")
        item_id = record.get("item_id")
        bounds = record.get("projected_upper_bounds")
        if (
            not isinstance(item_id, str)
            or item_id in seen
            or item_id not in item_ids
            or not isinstance(bounds, Mapping)
            or set(bounds) != set(F1_ARMS)
        ):
            raise R8RunnerRefusal("envelope projection item identity drifted")
        seen.add(item_id)
        for arm in F1_ARMS:
            triplet = bounds.get(arm)
            if (
                not isinstance(triplet, list)
                or len(triplet) != 3
                or any(
                    isinstance(bound, bool)
                    or not isinstance(bound, int)
                    or bound < 0
                    or bound > int(input_caps[str(index)])
                    for index, bound in enumerate(triplet, start=1)
                )
            ):
                raise R8RunnerRefusal("envelope projection upper bound drifted")
    if seen != set(item_ids):
        raise R8RunnerRefusal("envelope projection does not cover the cohort")


def _verify_execution_structure(
    value: Mapping[str, object],
) -> tuple[list[Mapping[str, object]], dict[str, object], dict[str, object]]:
    run_id, model, model_revision = (
        value.get("run_id"), value.get("model"), value.get("model_revision")
    )
    if any(not isinstance(item, str) or not item for item in (run_id, model, model_revision)):
        raise R8RunnerRefusal("suite execution identity is incomplete")
    mode = value.get("mode")
    if mode not in {"development", "sealed"}:
        raise R8RunnerRefusal("suite execution mode drifted")
    for field in (
        "manifest_sha256", "measurement_lock_sha256", "result_contract_sha256",
        "environment_receipt_sha256", "dependency_receipt_sha256",
        "environment_dependency_compatibility_root_sha256",
        "environment_dependency_bundle_sha256", "db_genesis_receipt_sha256",
        "protocol_sha256", "registries_root_sha256", "token_envelope_sha256",
        "token_envelope_derivation_receipt_sha256",
        "cohort_root_sha256", "candidate_universe_root_sha256",
        "generation_policy_sha256", "spool_identity_preflight_sha256",
    ):
        _sha(value.get(field), f"suite {field}")
    hswm_commit = value.get("hswm_commit")
    if not isinstance(hswm_commit, str) or _GIT_COMMIT.fullmatch(hswm_commit) is None:
        raise R8RunnerRefusal("suite HSWM commit is not exact")
    prereg = value.get("preregistration_artifact_sha256")
    readback_sha = value.get("preregistration_readback_sha256")
    anchored_sha = value.get("anchored_judge_file_sha256")
    if mode == "development":
        if any(item is not None for item in (prereg, readback_sha, anchored_sha)):
            raise R8RunnerRefusal("development suite claims sealed preregistration")
    else:
        for item, label in (
            (prereg, "preregistration artifact"),
            (readback_sha, "preregistration readback"),
            (anchored_sha, "anchored judge"),
        ):
            _sha(item, label)
    if value.get("generation_policy") != GENERATION_POLICY or value.get(
        "generation_policy_sha256"
    ) != canonical_sha256(GENERATION_POLICY):
        raise R8RunnerRefusal("suite generation policy drifted")
    tolerance = _nonnegative(value.get("token_tolerance"), "token tolerance")
    envelope = validate_token_envelope(value.get("token_envelope"), arms=F1_ARMS)
    if canonical_sha256(envelope) != value.get("token_envelope_sha256"):
        raise R8RunnerRefusal("suite token envelope hash drifted")
    capacity = _nonnegative(value.get("state_capacity_bytes"), "state capacity")
    states = value.get("state_bytes_by_arm")
    if (
        not isinstance(states, Mapping)
        or set(states) != set(F1_ARMS)
        or any(
            isinstance(item, bool) or not isinstance(item, int) or not 0 <= item <= capacity
            for item in states.values()
        )
    ):
        raise R8RunnerRefusal("suite persistent-state contract drifted")
    functions, protocol_sha, registry_root = _validate_registry_bundle(
        value.get("registries"), model=model, model_revision=model_revision
    )
    if (
        protocol_sha != value.get("protocol_sha256")
        or registry_root != value.get("registries_root_sha256")
    ):
        raise R8RunnerRefusal("suite registry/protocol roots drifted")
    rows = value.get("item_runs")
    if not isinstance(rows, list) or not rows or any(
        not isinstance(row, Mapping) for row in rows
    ):
        raise R8RunnerRefusal("suite item runs are absent")
    row_mappings = [row for row in rows if isinstance(row, Mapping)]
    item_ids = sorted({str(row.get("item_id")) for row in row_mappings})
    gates = value.get("execution_gates")
    _validate_lock_gates(
        gates,
        item_count=len(item_ids),
        token_envelope=envelope,
        token_tolerance=tolerance,
    )
    assert isinstance(gates, Mapping)
    if len(rows) != gates.get("expected_item_runs"):
        raise R8RunnerRefusal("suite item-run count differs from gates")
    policy = _validate_execution_policy_value(value.get("execution_policy"))
    if value.get("max_workers") != policy.get("max_workers"):
        raise R8RunnerRefusal("suite max_workers differs from execution policy")
    deployment_binding = _deployment_binding_from_lock(value)
    preflight_sha = _validate_spool_identity_preflight(
        value.get("spool_identity_preflight"),
        run_id=str(run_id),
        deployment_binding=deployment_binding,
        execution_lock_sha256=str(value.get("measurement_lock_sha256")),
        db_genesis_sha256=str(value.get("db_genesis_receipt_sha256")),
        endpoint=str(policy.get("endpoint")),
    )
    if preflight_sha != value.get("spool_identity_preflight_sha256"):
        raise R8RunnerRefusal("suite spool preflight digest drifted")
    expected_order = [(item_id, arm) for item_id in item_ids for arm in F1_ARMS]
    observed_order = [
        (str(row.get("item_id")), str(row.get("arm_id"))) for row in row_mappings
    ]
    if observed_order != expected_order:
        raise R8RunnerRefusal("suite item runs are not exact canonical coverage")
    candidate_by_item: dict[str, str] = {}
    registries = value.get("registries")
    assert isinstance(registries, Mapping)
    for row in row_mappings:
        arm = str(row.get("arm_id"))
        item_id = str(row.get("item_id"))
        candidate = str(row.get("candidate_universe_sha256"))
        previous = candidate_by_item.setdefault(item_id, candidate)
        if previous != candidate:
            raise R8RunnerRefusal("candidate universe differs across arms")
        registry = registries[arm]
        assert isinstance(registry, Mapping)
        _verify_item_run_local(
            row,
            run_id=str(run_id),
            registry=registry,
            functions=functions[arm],
            input_caps=envelope["per_call_input_caps"],
            output_caps=envelope["per_call_output_caps"],
            persistent_state_bytes=int(states[arm]),
        )
    cohort_root = canonical_sha256(item_ids)
    candidate_root = canonical_sha256(
        [
            {
                "item_id": item_id,
                "candidate_universe_sha256": candidate_by_item[item_id],
            }
            for item_id in item_ids
        ]
    )
    if (
        value.get("cohort_root_sha256") != cohort_root
        or value.get("candidate_universe_root_sha256") != candidate_root
    ):
        raise R8RunnerRefusal("suite cohort/candidate root drifted")
    expected_parity = _token_parity_local(
        row_mappings, tolerance=tolerance, envelope=envelope
    )
    if value.get("token_parity") != expected_parity:
        raise R8RunnerRefusal("suite token-parity record drifted")
    _validate_projection_record(
        value.get("envelope_projection"), item_ids=item_ids, envelope=envelope
    )
    if value.get("gold_opened") is not False or value.get(
        "scientific_verdict_emitted"
    ) is not False:
        raise R8RunnerRefusal("suite crossed evaluator authority")
    return row_mappings, dict(gates), policy


def run_suite_v3_draft(
    manifest: Mapping[str, object],
    *,
    execution_lock: Mapping[str, object],
    protocol_path: Path,
    model_port,
    token_meter: TokenMeter,
    max_workers: int,
    token_envelope_derivation: Mapping[str, object],
    prior_exposure_receipt: Mapping[str, object],
    aborted_attempt_exposure_receipt: Mapping[str, object],
    environment_dependency_bundle: Mapping[str, object],
    result_contract_path: Path,
    judge_core_path: Path,
    symposium_repo_root: Path,
    tokenizer_dir: Path,
    model_catalog_path: Path,
    model_weight_receipt_path: Path,
    python_lock_path: Path,
    spool_identity_preflight: Mapping[str, object],
    resume_prefix: Mapping[str, object] | None = None,
    offline_complete_resume: bool = False,
    preregistration_artifact: Mapping[str, object] | None = None,
    preregistration_readback: Mapping[str, object] | None = None,
    anchored_judge_path: Path | None = None,
) -> dict[str, object]:
    """Internal executor for inputs captured and validated by the CLI boundary.

    The supported live entrypoint is :func:`main`; direct mapping callers are
    intentionally outside the raw-file provenance authority and are used only
    by deterministic in-process tests with a non-network model port.
    """

    if isinstance(max_workers, bool) or not isinstance(max_workers, int) or not 1 <= max_workers <= 8:
        raise R8RunnerRefusal("max_workers must be in [1,8]")
    ledger_path = getattr(getattr(model_port, "ledger", None), "path", None)
    registries = _registries(
        protocol_path=protocol_path,
        protocol=token_envelope_derivation.get("protocol")
        if isinstance(token_envelope_derivation, Mapping)
        else None,
        model=str(manifest.get("model")),
        model_revision=str(manifest.get("model_revision")),
    )
    normalized, items, projection_record = validate_manifest_v3(
        manifest,
        execution_lock=execution_lock,
        token_meter=token_meter,
        registries=registries,
    )
    execution_lock_sha = str(projection_record.pop("execution_lock_sha256"))
    derivation_sha = _validate_token_envelope_derivation_gate(
        token_envelope_derivation,
        manifest=normalized,
        execution_lock=execution_lock,
        token_meter=token_meter,
        protocol_path=protocol_path,
        preregistration_artifact=preregistration_artifact,
    )
    _validate_aborted_attempt_exposure_gate(
        aborted_attempt_exposure_receipt,
        prior_exposure_receipt=prior_exposure_receipt,
        execution_lock=execution_lock,
    )
    validated_resume_prefix: dict[str, object] | None = None
    if resume_prefix is not None:
        validated_resume_prefix = _validate_resume_prefix(
            resume_prefix,
            run_id=str(normalized["run_id"]),
            db_genesis_sha256=str(
                execution_lock["db_genesis_receipt_sha256"]
            ),
            ordered_jobs=_resume_job_values(items),
            max_workers=max_workers,
        )
    if offline_complete_resume:
        gates = execution_lock.get("gates")
        if (
            validated_resume_prefix is None
            or not isinstance(gates, Mapping)
            or validated_resume_prefix.get("call_count")
            != gates.get("expected_calls")
        ):
            raise R8RunnerRefusal(
                "offline resume requires the exact complete call prefix"
            )
    deployment_binding = load_model_deployment_binding(
        model_weight_receipt_path,
        upstream_endpoint=str(execution_lock.get("upstream_endpoint", "")),
        served_model=str(normalized["model"]),
        model_revision=str(normalized["model_revision"]),
        verify_live_process=not offline_complete_resume,
    )
    _validate_deployment_binding(execution_lock, deployment_binding)
    policy = _validate_execution_policy_value(execution_lock.get("execution_policy"))
    if max_workers != policy.get("max_workers"):
        raise R8RunnerRefusal("direct API max_workers differs from execution lock")
    port_policy = {
        "endpoint": getattr(model_port, "spool_endpoint", None),
        "timeout_seconds": getattr(model_port, "timeout_seconds", None),
        "max_delivery_attempts": getattr(model_port, "max_delivery_attempts", None),
        "spool_token_env": getattr(model_port, "spool_token_env", None),
    }
    expected_port_policy = {
        "endpoint": str(policy["endpoint"]).rstrip("/"),
        "timeout_seconds": policy["timeout_seconds"],
        "max_delivery_attempts": policy["max_delivery_attempts"],
        "spool_token_env": policy["spool_token_env"],
    }
    if port_policy != expected_port_policy:
        raise R8RunnerRefusal("direct model-port policy differs from execution lock")
    dependency_paths = r8_dependency_paths(
        protocol_path=protocol_path,
        judge_core_path=judge_core_path,
        result_contract_path=result_contract_path,
        tokenizer_dir=tokenizer_dir,
        model_catalog_path=model_catalog_path,
        model_weight_receipt_path=model_weight_receipt_path,
        python_lock_path=python_lock_path,
    )
    bundle_sha = _validate_environment_dependency_bundle(
        environment_dependency_bundle,
        execution_lock=execution_lock,
        run_id=str(normalized["run_id"]),
        model=str(normalized["model"]),
        model_revision=str(normalized["model_revision"]),
        spool_endpoint=str(policy["endpoint"]),
        deployment_binding=deployment_binding,
        dependency_paths=dependency_paths,
        symposium_repo_root=symposium_repo_root,
    )
    _validate_preregistration_gate(
        mode=str(normalized["mode"]),
        manifest=normalized,
        execution_lock=execution_lock,
        preregistration_artifact=preregistration_artifact,
        preregistration_readback=preregistration_readback,
        anchored_judge_path=anchored_judge_path,
        judge_core_path=judge_core_path,
        symposium_repo_root=symposium_repo_root,
        result_contract_path=result_contract_path,
    )
    preflight_sha = _validate_spool_identity_preflight(
        spool_identity_preflight,
        run_id=str(normalized["run_id"]),
        deployment_binding=deployment_binding,
        execution_lock_sha256=execution_lock_sha,
        db_genesis_sha256=str(execution_lock["db_genesis_receipt_sha256"]),
        endpoint=str(policy["endpoint"]),
    )
    if ledger_path is not None:
        _seal_private_sqlite_family(Path(ledger_path), "attempt ledger")
    audit = getattr(model_port, "audit", None)
    if not callable(audit):
        raise R8RunnerRefusal("model port does not expose a durable audit")
    jobs = [
        (item, arm)
        for item in sorted(items, key=lambda item: item.item_id)
        for arm in F1_ARMS
    ]
    observed_pre_call_audit = audit()
    if resume_prefix is None:
        pre_call_audit = _validate_live_attempt_audit(
            observed_pre_call_audit, expected_calls=0, expected_item_runs=0
        )
    else:
        assert validated_resume_prefix is not None
        if (
            observed_pre_call_audit
            != validated_resume_prefix["attempt_live_audit"]
        ):
            raise R8RunnerRefusal(
                "live attempt ledger differs from the resume prefix"
            )
        pre_call_audit = _empty_attempt_audit_from(
            validated_resume_prefix["attempt_live_audit"]
        )
    envelope = envelope_spec(normalized["token_envelope"], token_meter)

    def execute(job):
        item, arm = job
        return run_item(
            run_id=str(normalized["run_id"]),
            arm_id=arm,
            item=item,
            registry=registries[arm],
            model_port=model_port,
            envelope=envelope,
            persistent_state_bytes=int(normalized["state_bytes_by_arm"][arm]),
        ).canonical()

    if max_workers == 1:
        rows = [execute(job) for job in jobs]
    else:
        rows = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for offset in range(0, len(jobs), max_workers):
                futures = [executor.submit(execute, job) for job in jobs[offset : offset + max_workers]]
                done, pending = wait(futures, return_when=FIRST_EXCEPTION)
                failure = next(
                    (future.exception() for future in done if future.exception() is not None),
                    None,
                )
                if failure is not None:
                    for future in pending:
                        future.cancel()
                    raise failure
                rows.extend(future.result() for future in futures)
    rows.sort(key=lambda row: (str(row["item_id"]), F1_ARMS.index(str(row["arm_id"]))))
    gates = execution_lock["gates"]
    live_audit = _validate_live_attempt_audit(
        audit(),
        expected_calls=int(gates["expected_calls"]),
        expected_item_runs=int(gates["expected_item_runs"]),
    )
    if ledger_path is not None:
        _seal_private_sqlite_family(Path(ledger_path), "attempt ledger")
    if len(rows) != gates["expected_item_runs"]:
        raise R8RunnerRefusal("terminal durable rows differ from execution lock")
    parity = _token_parity_local(
        rows,
        tolerance=int(normalized["token_tolerance"]),
        envelope=normalized["token_envelope"],
    )
    items_by_id = {item.item_id: item for item in items}
    cohort_root = canonical_sha256(sorted(items_by_id))
    candidate_root = canonical_sha256(
        [
            {"item_id": item_id, "candidate_universe_sha256": items_by_id[item_id].candidate_universe_sha256}
            for item_id in sorted(items_by_id)
        ]
    )
    registry_values = {arm: registries[arm].canonical() for arm in F1_ARMS}
    _, protocol_sha, registry_root = _validate_registry_bundle(
        registry_values,
        model=str(normalized["model"]),
        model_revision=str(normalized["model_revision"]),
    )
    readback_sha = None
    anchored_sha = None
    if preregistration_readback is not None:
        readback_sha = _self_hash(
            preregistration_readback, "receipt_sha256", "preregistration readback"
        )
    if anchored_judge_path is not None:
        anchored_sha = _stable_file_sha256(anchored_judge_path, "anchored judge")
    unsigned = {
        "schema_version": SUITE_DRAFT_SCHEMA,
        "run_id": normalized["run_id"],
        "mode": normalized["mode"],
        "manifest_sha256": canonical_sha256(normalized),
        "model": normalized["model"],
        "model_revision": normalized["model_revision"],
        "upstream_endpoint": deployment_binding.upstream_endpoint,
        "deployment_receipt_sha256": (
            deployment_binding.deployment_receipt_sha256
        ),
        "deployment_id": deployment_binding.deployment_id,
        "served_model": deployment_binding.served_model,
        "token_tolerance": normalized["token_tolerance"],
        "state_capacity_bytes": normalized["state_capacity_bytes"],
        "state_bytes_by_arm": normalized["state_bytes_by_arm"],
        "preregistration_artifact_sha256": normalized["preregistration_artifact_sha256"],
        "preregistration_readback_sha256": readback_sha,
        "anchored_judge_file_sha256": anchored_sha,
        "measurement_lock_sha256": execution_lock_sha,
        "result_contract_sha256": execution_lock["result_contract_sha256"],
        "environment_receipt_sha256": execution_lock[
            "environment_receipt_sha256"
        ],
        "dependency_receipt_sha256": execution_lock["dependency_receipt_sha256"],
        "environment_dependency_compatibility_root_sha256": execution_lock[
            "environment_dependency_compatibility_root_sha256"
        ],
        "environment_dependency_bundle_sha256": bundle_sha,
        "hswm_commit": execution_lock["hswm_commit"],
        "db_genesis_receipt_sha256": execution_lock["db_genesis_receipt_sha256"],
        "protocol_sha256": protocol_sha,
        "registries_root_sha256": registry_root,
        "token_envelope_sha256": canonical_sha256(normalized["token_envelope"]),
        "token_envelope_derivation_receipt_sha256": derivation_sha,
        "cohort_root_sha256": cohort_root,
        "candidate_universe_root_sha256": candidate_root,
        "generation_policy": normalized["generation_policy"],
        "generation_policy_sha256": canonical_sha256(normalized["generation_policy"]),
        "token_envelope": normalized["token_envelope"],
        "envelope_projection": projection_record,
        "token_parity": parity,
        "execution_policy": policy,
        "execution_gates": dict(gates),
        "max_workers": max_workers,
        "spool_identity_preflight": dict(spool_identity_preflight),
        "spool_identity_preflight_sha256": preflight_sha,
        "registries": registry_values,
        "pre_call_transport_audit": pre_call_audit,
        "live_transport_audit": live_audit,
        "item_runs": rows,
        "gold_opened": False,
        "scientific_verdict_emitted": False,
    }
    result = {**unsigned, "draft_receipt_sha256": canonical_sha256(unsigned)}
    if set(result) != _DRAFT_FIELDS:
        raise R8RunnerRefusal("suite draft field set drifted")
    _verify_execution_structure(result)
    return result


def _validate_terminal_transport(
    *,
    rows: Sequence[Mapping[str, object]],
    gates: Mapping[str, object],
    policy: Mapping[str, object],
    bindings: Mapping[str, object],
    audit: object,
) -> dict[str, object]:
    expected_calls = int(gates["expected_calls"])
    expected_runs = int(gates["expected_item_runs"])
    roots = _verify_transport_bindings_against_rows(
        rows, bindings, expected_endpoint=str(policy["endpoint"])
    )
    arrays = {
        "accepted_calls": expected_calls,
        "accepted_call_auxiliary_preimages": expected_calls,
        "spool_bindings": expected_calls,
        "spool_call_preimages": expected_calls,
        "item_run_bindings": expected_runs,
        "item_run_preimages": expected_runs,
        "attempt_events": int(bindings.get("attempt_event_count", -1)),
    }
    if any(
        not isinstance(bindings.get(key), list)
        or len(bindings[key]) != expected
        for key, expected in arrays.items()
    ):
        raise R8RunnerRefusal("terminal transport array coverage drifted")
    if (
        bindings.get("attempt_integrity") != "ok"
        or bindings.get("spool_integrity") != "ok"
        or str(bindings.get("attempt_journal_mode")).casefold() != "wal"
        or str(bindings.get("spool_journal_mode")).casefold() != "wal"
        or str(bindings.get("attempt_audit_connection_synchronous")) != "2"
        or str(bindings.get("spool_audit_connection_synchronous")) != "2"
        or bindings.get("attempt_user_version") != 1
        or bindings.get("spool_user_version") != 1
        or bindings.get("call_count") != expected_calls
        or bindings.get("item_run_count") != expected_runs
        or bindings.get("spool_call_count") != expected_calls
        or bindings.get("attempt_status_counts") != {"ACCEPTED": expected_calls}
        or bindings.get("spool_status_counts") != {"COMPLETE": expected_calls}
        or bindings.get("spool_unknown_count") != 0
        or bindings.get("identity_conflict_count") != 0
        or int(bindings.get("attempt_event_count", -1)) < expected_calls * 6
    ):
        raise R8RunnerRefusal("terminal transport durability or count summary drifted")
    for field in (
        "attempt_schema_sha256", "spool_schema_sha256", "db_genesis_sha256",
    ):
        _sha(bindings.get(field), f"terminal transport {field}")
    attempt_identity = _database_identity_value(
        bindings.get("attempt_db_identity"), "terminal attempt ledger"
    )
    spool_identity = _database_identity_value(
        bindings.get("spool_db_identity"), "terminal result spool"
    )
    if (attempt_identity["st_dev"], attempt_identity["st_ino"]) == (
        spool_identity["st_dev"], spool_identity["st_ino"]
    ):
        raise R8RunnerRefusal("terminal transport databases alias one inode")
    live = _validate_live_attempt_audit(
        audit, expected_calls=expected_calls, expected_item_runs=expected_runs
    )
    expected_live = {
        "journal_mode": bindings["attempt_journal_mode"],
        "synchronous": int(bindings["attempt_audit_connection_synchronous"]),
        "event_chain_tip_sha256": roots["event_chain_tip_sha256"],
        "call_count": expected_calls,
        "status_counts": bindings["attempt_status_counts"],
        "accepted_call_root_sha256": roots["accepted_call_root_sha256"],
        "spool_binding_root_sha256": roots["spool_binding_root_sha256"],
        "item_run_count": expected_runs,
        "item_run_root_sha256": roots["item_run_root_sha256"],
    }
    if any(live.get(key) != expected for key, expected in expected_live.items()):
        raise R8RunnerRefusal("live SQLite audit differs from terminal byte export")
    return roots


def verify_suite_draft_without_gold(value: Mapping[str, object]) -> str:
    if set(value) != _DRAFT_FIELDS or value.get("schema_version") != SUITE_DRAFT_SCHEMA:
        raise R8RunnerRefusal("suite draft schema drifted")
    declared = _self_hash(value, "draft_receipt_sha256", "suite draft")
    rows, gates, policy = _verify_execution_structure(value)
    _validate_live_attempt_audit(
        value.get("pre_call_transport_audit"),
        expected_calls=0,
        expected_item_runs=0,
    )
    live_audit = _validate_live_attempt_audit(
        value.get("live_transport_audit"),
        expected_calls=int(gates["expected_calls"]),
        expected_item_runs=int(gates["expected_item_runs"]),
    )
    item_run_bindings = sorted(
        (
            {
                "run_id": str(row.get("run_id")),
                "arm_id": str(row.get("arm_id")),
                "item_id": str(row.get("item_id")),
                "run_receipt_sha256": str(row.get("run_receipt_sha256")),
            }
            for row in rows
        ),
        key=lambda row: (row["run_id"], row["arm_id"], row["item_id"]),
    )
    if live_audit.get("item_run_root_sha256") != canonical_sha256(
        item_run_bindings
    ):
        raise R8RunnerRefusal(
            "suite draft rows differ from the durable item-run root"
        )
    try:
        binding = ModelDeploymentBinding(
            upstream_endpoint=str(value.get("upstream_endpoint", "")),
            deployment_receipt_sha256=str(
                value.get("deployment_receipt_sha256", "")
            ),
            deployment_id=str(value.get("deployment_id", "")),
            served_model=str(value.get("served_model", "")),
            model_revision=str(value.get("model_revision", "")),
        )
    except Exception as error:
        raise R8RunnerRefusal("suite draft deployment binding drifted") from error
    _validate_spool_identity_preflight(
        value.get("spool_identity_preflight"),
        run_id=str(value["run_id"]),
        deployment_binding=binding,
        execution_lock_sha256=str(value["measurement_lock_sha256"]),
        db_genesis_sha256=str(value["db_genesis_receipt_sha256"]),
        endpoint=str(policy["endpoint"]),
    )
    if len(rows) != int(gates["expected_item_runs"]):
        raise R8RunnerRefusal("suite draft item-run coverage drifted")
    return declared


def _verify_committed_draft_resume(
    draft: Mapping[str, object],
    *,
    resume_prefix: Mapping[str, object],
    spool_identity_preflight: Mapping[str, object],
    expected_authority: Mapping[str, object],
) -> str:
    declared = verify_suite_draft_without_gold(draft)
    gates = draft["execution_gates"]
    assert isinstance(gates, Mapping)
    positions = resume_prefix.get("call_positions")
    if any(draft.get(key) != expected for key, expected in expected_authority.items()):
        raise R8RunnerRefusal(
            "committed suite draft differs from current frozen authority"
        )
    if (
        draft.get("spool_identity_preflight") != spool_identity_preflight
        or draft.get("live_transport_audit")
        != resume_prefix.get("attempt_live_audit")
        or resume_prefix.get("call_count") != gates.get("expected_calls")
        or resume_prefix.get("item_run_count") != gates.get("expected_item_runs")
        or not isinstance(positions, list)
        or len(positions) != gates.get("expected_item_runs")
        or any(
            not isinstance(position, Mapping)
            or position.get("call_indices") != [1, 2, 3]
            or position.get("item_run_committed") is not True
            for position in positions
        )
    ):
        raise R8RunnerRefusal(
            "committed suite draft differs from the full resume prefix"
        )
    return declared


def finalize_suite_v3(
    draft: Mapping[str, object],
    *,
    transport_bindings: Mapping[str, object],
    genesis_receipt: Mapping[str, object],
) -> dict[str, object]:
    verify_suite_draft_without_gold(draft)
    rows, gates, policy = _verify_execution_structure(draft)
    genesis_sha = _validate_transport_genesis_receipt(
        genesis_receipt,
        run_id=str(draft["run_id"]),
        expected_sha256=str(draft["db_genesis_receipt_sha256"]),
    )
    genesis_fields = (
        "attempt_integrity", "spool_integrity", "attempt_journal_mode",
        "attempt_audit_connection_synchronous", "spool_journal_mode",
        "spool_audit_connection_synchronous", "attempt_user_version",
        "spool_user_version", "attempt_schema_sha256", "spool_schema_sha256",
        "attempt_db_identity", "spool_db_identity",
    )
    if (
        transport_bindings.get("run_id") != draft.get("run_id")
        or transport_bindings.get("db_genesis_sha256") != genesis_sha
        or any(
            transport_bindings.get(field) != genesis_receipt.get(field)
            for field in genesis_fields
        )
    ):
        raise R8RunnerRefusal("terminal transport does not continue DB genesis")
    if _spool_preflight_database_identity(
        draft.get("spool_identity_preflight")
    ) != _database_identity_value(
        genesis_receipt.get("spool_db_identity"), "genesis result spool"
    ):
        raise R8RunnerRefusal(
            "spool preflight database identity differs from genesis"
        )
    _validate_terminal_transport(
        rows=rows,
        gates=gates,
        policy=policy,
        bindings=transport_bindings,
        audit=draft.get("live_transport_audit"),
    )
    unsigned = {
        key: value
        for key, value in draft.items()
        if key not in {
            "schema_version", "pre_call_transport_audit", "live_transport_audit",
            "draft_receipt_sha256",
        }
    }
    unsigned = {
        "schema_version": SUITE_SCHEMA,
        **unsigned,
        "transport_audit": dict(draft["live_transport_audit"]),
        "transport_bindings": dict(transport_bindings),
    }
    result = {**unsigned, "suite_receipt_sha256": canonical_sha256(unsigned)}
    if set(result) != _SUITE_FIELDS:
        raise R8RunnerRefusal("suite v3 field set drifted")
    verify_suite_v3_without_gold(result)
    return result


def verify_suite_v3_without_gold(value: Mapping[str, object]) -> str:
    if set(value) != _SUITE_FIELDS or value.get("schema_version") != SUITE_SCHEMA:
        raise R8RunnerRefusal("suite v3 schema drifted")
    declared = _self_hash(value, "suite_receipt_sha256", "suite v3")
    rows, gates, policy = _verify_execution_structure(value)
    bindings = value.get("transport_bindings")
    audit = value.get("transport_audit")
    if not isinstance(bindings, Mapping) or not isinstance(audit, Mapping):
        raise R8RunnerRefusal("suite transport evidence is absent")
    if (
        bindings.get("run_id") != value.get("run_id")
        or bindings.get("db_genesis_sha256")
        != value.get("db_genesis_receipt_sha256")
    ):
        raise R8RunnerRefusal("suite transport identity drifted")
    if _spool_preflight_database_identity(
        value.get("spool_identity_preflight")
    ) != _database_identity_value(
        bindings.get("spool_db_identity"), "terminal result spool"
    ):
        raise R8RunnerRefusal(
            "spool preflight database identity differs from terminal transport"
        )
    _validate_terminal_transport(
        rows=rows,
        gates=gates,
        policy=policy,
        bindings=bindings,
        audit=audit,
    )
    return declared


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--execution-lock", type=Path, required=True)
    run.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    run.add_argument("--endpoint", required=True)
    run.add_argument("--attempt-db", type=Path, required=True)
    run.add_argument("--spool-db", type=Path, required=True)
    run.add_argument("--db-genesis-receipt", type=Path, required=True)
    run.add_argument("--environment-dependency-bundle", type=Path, required=True)
    run.add_argument(
        "--token-envelope-derivation-receipt", type=Path, required=True
    )
    run.add_argument("--selection-receipt", type=Path, required=True)
    run.add_argument("--prior-exposure-receipt", type=Path, required=True)
    run.add_argument(
        "--aborted-attempt-exposure-receipt", type=Path, required=True
    )
    run.add_argument("--historical-manifest", type=Path, required=True)
    run.add_argument("--token-meter-validation-receipt", type=Path, required=True)
    run.add_argument("--projected-outputs-receipt", type=Path, required=True)
    run.add_argument("--token-meter-source-suite", type=Path, required=True)
    run.add_argument("--result-contract", type=Path, required=True)
    run.add_argument("--judge-core", type=Path, required=True)
    run.add_argument("--symposium-repo-root", type=Path, required=True)
    run.add_argument("--model-catalog", type=Path, required=True)
    run.add_argument(
        "--model-deployment-receipt",
        dest="model_weight_receipt",
        type=Path,
        required=True,
    )
    run.add_argument("--python-lock", type=Path, required=True)
    run.add_argument("--preregistration-artifact", type=Path)
    run.add_argument("--preregistration-readback-receipt", type=Path)
    run.add_argument("--anchored-judge", type=Path)
    run.add_argument("--spool-token-env", required=True)
    run.add_argument("--spool-identity-receipt", type=Path, required=True)
    run.add_argument("--reservation-journal", type=Path, required=True)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--timeout-seconds", type=float, default=180.0)
    run.add_argument("--max-workers", type=int, default=1)
    run.add_argument("--max-delivery-attempts", type=int, default=8)
    run.add_argument("--tokenizer-dir", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--draft", type=Path, required=True)
    finalize.add_argument("--transport-bindings", type=Path, required=True)
    finalize.add_argument("--db-genesis-receipt", type=Path, required=True)
    finalize.add_argument("--output", type=Path, required=True)
    finalize.add_argument("--reservation-journal", type=Path, required=True)
    finalize.add_argument("--resume", action="store_true")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--suite", type=Path, required=True)
    initialize = subparsers.add_parser("init-transport")
    initialize.add_argument("--attempt-db", type=Path, required=True)
    initialize.add_argument("--spool-db", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            manifest, _manifest_file_sha = read_stable_json(
                args.manifest, "manifest"
            )
            execution_lock, _execution_lock_file_sha = read_stable_json(
                args.execution_lock, "execution lock"
            )
            environment_bundle = load_private_receipt(
                args.environment_dependency_bundle, verify_live=True
            )
            preregistration_artifact = (
                read_stable_json(
                    args.preregistration_artifact, "preregistration artifact"
                )[0]
                if args.preregistration_artifact is not None
                else None
            )
            preregistration_readback = (
                read_stable_json(
                    args.preregistration_readback_receipt,
                    "preregistration readback",
                )[0]
                if args.preregistration_readback_receipt is not None
                else None
            )
            receipt, _receipt_file_sha = read_stable_json(
                args.token_envelope_derivation_receipt,
                "token-envelope derivation receipt",
            )
            aborted_exposure, _aborted_exposure_file_sha = read_stable_json(
                args.aborted_attempt_exposure_receipt,
                "aborted-attempt exposure receipt",
            )
            prior_exposure, _prior_exposure_file_sha = read_stable_json(
                args.prior_exposure_receipt,
                "prior-exposure receipt",
            )
            derivation_values: dict[str, object] = {"receipt": receipt}
            derivation_file_specs = {
                "selection_receipt": (
                    args.selection_receipt, "public selection receipt"
                ),
                "historical_manifest": (
                    args.historical_manifest, "historical manifest"
                ),
                "validation_receipt": (
                    args.token_meter_validation_receipt,
                    "token-meter validation receipt",
                ),
                "projected_outputs_receipt": (
                    args.projected_outputs_receipt,
                    "projected-output receipt",
                ),
                "source_suite": (
                    args.token_meter_source_suite, "token-meter source suite"
                ),
                "protocol": (args.protocol, "PROM-9 protocol"),
            }
            derivation_file_sha256s: dict[str, str] = {}
            for name, (path, label) in derivation_file_specs.items():
                value, digest = read_stable_json(path, label)
                derivation_values[name] = value
                derivation_file_sha256s[name] = digest
            derivation_values["file_sha256s"] = derivation_file_sha256s
            meter = QwenBpeMeter(
                args.tokenizer_dir / "vocab.json",
                args.tokenizer_dir / "merges.txt",
                args.tokenizer_dir / "tokenizer_config.json",
            )
            registries = _registries(
                protocol_path=args.protocol,
                protocol=derivation_values.get("protocol")
                if isinstance(derivation_values.get("protocol"), Mapping)
                else None,
                model=str(manifest.get("model")),
                model_revision=str(manifest.get("model_revision")),
            )
            normalized, items, projection = validate_manifest_v3(
                manifest,
                execution_lock=execution_lock,
                token_meter=meter,
                registries=registries,
            )
            lock_sha = str(projection["execution_lock_sha256"])
            derivation_sha = _validate_token_envelope_derivation_gate(
                derivation_values,
                manifest=normalized,
                execution_lock=execution_lock,
                token_meter=meter,
                protocol_path=args.protocol,
                preregistration_artifact=preregistration_artifact,
            )
            _validate_aborted_attempt_exposure_gate(
                aborted_exposure,
                prior_exposure_receipt=prior_exposure,
                execution_lock=execution_lock,
            )
            deployment_binding = load_model_deployment_binding(
                args.model_weight_receipt,
                upstream_endpoint=str(
                    execution_lock.get("upstream_endpoint", "")
                ),
                served_model=str(normalized["model"]),
                model_revision=str(normalized["model_revision"]),
                verify_live_process=False,
            )
            _validate_deployment_binding(execution_lock, deployment_binding)
            dependency_paths = r8_dependency_paths(
                protocol_path=args.protocol,
                judge_core_path=args.judge_core,
                result_contract_path=args.result_contract,
                tokenizer_dir=args.tokenizer_dir,
                model_catalog_path=args.model_catalog,
                model_weight_receipt_path=args.model_weight_receipt,
                python_lock_path=args.python_lock,
            )
            bundle_sha = _validate_environment_dependency_bundle(
                environment_bundle,
                execution_lock=execution_lock,
                run_id=str(normalized["run_id"]),
                model=str(normalized["model"]),
                model_revision=str(normalized["model_revision"]),
                spool_endpoint=args.endpoint,
                deployment_binding=deployment_binding,
                dependency_paths=dependency_paths,
                symposium_repo_root=args.symposium_repo_root,
            )
            _validate_preregistration_gate(
                mode=str(normalized["mode"]),
                manifest=normalized,
                execution_lock=execution_lock,
                preregistration_artifact=preregistration_artifact,
                preregistration_readback=preregistration_readback,
                anchored_judge_path=args.anchored_judge,
                judge_core_path=args.judge_core,
                symposium_repo_root=args.symposium_repo_root,
                result_contract_path=args.result_contract,
            )
            validate_execution_policy(
                execution_lock,
                endpoint=args.endpoint,
                max_workers=args.max_workers,
                timeout_seconds=args.timeout_seconds,
                max_delivery_attempts=args.max_delivery_attempts,
                spool_token_env=args.spool_token_env,
            )
            genesis, _genesis_file_sha = read_stable_json(
                args.db_genesis_receipt, "DB genesis receipt"
            )
            forbidden_paths = [
                args.manifest, args.execution_lock, args.protocol, args.attempt_db,
                args.spool_db, args.db_genesis_receipt,
                args.environment_dependency_bundle, args.result_contract,
                args.judge_core, args.model_catalog, args.model_weight_receipt,
                args.python_lock, args.token_envelope_derivation_receipt,
                args.aborted_attempt_exposure_receipt,
                args.prior_exposure_receipt,
                args.selection_receipt, args.historical_manifest,
                args.token_meter_validation_receipt,
                args.projected_outputs_receipt, args.token_meter_source_suite,
                args.tokenizer_dir / "vocab.json",
                args.tokenizer_dir / "merges.txt",
                args.tokenizer_dir / "tokenizer_config.json",
            ]
            forbidden_paths.extend(
                path
                for path in (
                    args.preregistration_artifact,
                    args.preregistration_readback_receipt,
                    args.anchored_judge,
                )
                if path is not None
            )
            reservations = reserve_private_outputs(
                [
                    ("spool_identity_receipt", args.spool_identity_receipt),
                    ("suite_draft", args.output),
                ],
                run_id=str(manifest["run_id"]),
                journal_path=args.reservation_journal,
                resume=args.resume,
                forbidden_paths=forbidden_paths,
            )
            try:
                genesis_sha = verify_fresh_transport_genesis(
                    genesis,
                    execution_lock=execution_lock,
                    run_id=str(normalized["run_id"]),
                    attempt_db=args.attempt_db,
                    spool_db=args.spool_db,
                    require_live_empty=not args.resume,
                )
                ordered_jobs = _resume_job_values(items)
                resume_prefix = _validate_resume_prefix(
                    export_resume_prefix(
                        run_id=str(normalized["run_id"]),
                        genesis_receipt=genesis,
                        attempt_db=args.attempt_db,
                        spool_db=args.spool_db,
                        ordered_jobs=ordered_jobs,
                        max_workers=args.max_workers,
                    ),
                    run_id=str(normalized["run_id"]),
                    db_genesis_sha256=genesis_sha,
                    ordered_jobs=ordered_jobs,
                    max_workers=args.max_workers,
                )
                _validate_resume_database_identity_continuity(
                    genesis=genesis,
                    resume_prefix=resume_prefix,
                )
                gates = execution_lock["gates"]
                assert isinstance(gates, Mapping)
                all_calls_complete = (
                    resume_prefix["call_count"] == gates["expected_calls"]
                )
                reservations.record_resume_audit(resume_prefix)
                endpoint_preflight = reservations[
                    "spool_identity_receipt"
                ].prepared_value()
                committed_draft = reservations["suite_draft"].prepared_value()
                if endpoint_preflight is not None:
                    _validate_spool_identity_preflight(
                        endpoint_preflight,
                        run_id=str(normalized["run_id"]),
                        deployment_binding=deployment_binding,
                        execution_lock_sha256=lock_sha,
                        db_genesis_sha256=genesis_sha,
                        endpoint=args.endpoint,
                    )
                    _validate_resume_database_identity_continuity(
                        genesis=genesis,
                        resume_prefix=resume_prefix,
                        spool_identity_preflight=endpoint_preflight,
                    )
                if committed_draft is not None:
                    if endpoint_preflight is None:
                        raise R8RunnerRefusal(
                            "committed draft lacks a committed spool preflight"
                        )
                    _verify_committed_draft_resume(
                        committed_draft,
                        resume_prefix=resume_prefix,
                        spool_identity_preflight=endpoint_preflight,
                        expected_authority={
                            "run_id": normalized["run_id"],
                            "mode": normalized["mode"],
                            "manifest_sha256": canonical_sha256(normalized),
                            "model": normalized["model"],
                            "model_revision": normalized["model_revision"],
                            "upstream_endpoint": (
                                deployment_binding.upstream_endpoint
                            ),
                            "deployment_receipt_sha256": (
                                deployment_binding.deployment_receipt_sha256
                            ),
                            "deployment_id": deployment_binding.deployment_id,
                            "served_model": deployment_binding.served_model,
                            "token_tolerance": normalized["token_tolerance"],
                            "state_capacity_bytes": normalized[
                                "state_capacity_bytes"
                            ],
                            "state_bytes_by_arm": normalized["state_bytes_by_arm"],
                            "preregistration_artifact_sha256": normalized[
                                "preregistration_artifact_sha256"
                            ],
                            "preregistration_readback_sha256": (
                                _self_hash(
                                    preregistration_readback,
                                    "receipt_sha256",
                                    "preregistration readback",
                                )
                                if preregistration_readback is not None
                                else None
                            ),
                            "anchored_judge_file_sha256": (
                                _stable_file_sha256(
                                    args.anchored_judge, "anchored judge"
                                )
                                if args.anchored_judge is not None
                                else None
                            ),
                            "measurement_lock_sha256": lock_sha,
                            "result_contract_sha256": execution_lock[
                                "result_contract_sha256"
                            ],
                            "environment_receipt_sha256": execution_lock[
                                "environment_receipt_sha256"
                            ],
                            "dependency_receipt_sha256": execution_lock[
                                "dependency_receipt_sha256"
                            ],
                            "environment_dependency_compatibility_root_sha256": (
                                execution_lock[
                                    "environment_dependency_compatibility_root_sha256"
                                ]
                            ),
                            "environment_dependency_bundle_sha256": bundle_sha,
                            "hswm_commit": execution_lock["hswm_commit"],
                            "db_genesis_receipt_sha256": genesis_sha,
                            "protocol_sha256": execution_lock["protocol_sha256"],
                            "registries_root_sha256": execution_lock[
                                "registries_root_sha256"
                            ],
                            "token_envelope_sha256": canonical_sha256(
                                normalized["token_envelope"]
                            ),
                            "token_envelope_derivation_receipt_sha256": (
                                derivation_sha
                            ),
                            "cohort_root_sha256": execution_lock[
                                "cohort_root_sha256"
                            ],
                            "candidate_universe_root_sha256": execution_lock[
                                "candidate_universe_root_sha256"
                            ],
                            "generation_policy": normalized["generation_policy"],
                            "generation_policy_sha256": canonical_sha256(
                                normalized["generation_policy"]
                            ),
                            "token_envelope": normalized["token_envelope"],
                            "execution_policy": execution_lock[
                                "execution_policy"
                            ],
                            "execution_gates": execution_lock["gates"],
                            "max_workers": args.max_workers,
                            "spool_identity_preflight": endpoint_preflight,
                            "spool_identity_preflight_sha256": (
                                endpoint_preflight["preflight_sha256"]
                            ),
                        },
                    )
                    reservations["spool_identity_receipt"].commit(
                        endpoint_preflight
                    )
                    reservations["suite_draft"].commit(committed_draft)
                    result = committed_draft
                else:
                    if not all_calls_complete:
                        live_deployment_binding = load_model_deployment_binding(
                            args.model_weight_receipt,
                            upstream_endpoint=str(
                                execution_lock.get("upstream_endpoint", "")
                            ),
                            served_model=str(normalized["model"]),
                            model_revision=str(normalized["model_revision"]),
                            verify_live_process=True,
                        )
                        _validate_deployment_binding(
                            execution_lock, live_deployment_binding
                        )
                        if live_deployment_binding != deployment_binding:
                            raise R8RunnerRefusal(
                                "live deployment differs from its offline attestation"
                            )
                    created_preflight = endpoint_preflight is None
                    if endpoint_preflight is None:
                        if resume_prefix["call_count"] != 0:
                            raise R8RunnerRefusal(
                                "nonzero resume prefix lacks a committed spool preflight"
                            )
                        endpoint_preflight = verify_spool_endpoint_identity(
                            endpoint=args.endpoint,
                            spool_db=args.spool_db,
                            deployment_binding=deployment_binding,
                            spool_token_env=args.spool_token_env,
                            timeout_seconds=args.timeout_seconds,
                            run_id=str(normalized["run_id"]),
                            execution_lock_sha256=lock_sha,
                            db_genesis_sha256=genesis_sha,
                        )
                        _validate_resume_database_identity_continuity(
                            genesis=genesis,
                            resume_prefix=resume_prefix,
                            spool_identity_preflight=endpoint_preflight,
                        )
                        reservations["spool_identity_receipt"].commit(
                            endpoint_preflight
                        )
                    else:
                        reservations["spool_identity_receipt"].commit(
                            endpoint_preflight
                        )
                    if (
                        args.resume
                        and not created_preflight
                        and not all_calls_complete
                    ):
                        spool_audit = resume_prefix.get("spool_live_audit")
                        if not isinstance(spool_audit, Mapping):
                            raise R8RunnerRefusal(
                                "resume prefix lacks a spool live audit"
                            )
                        live_spool_identity = verify_spool_endpoint_resume_identity(
                            endpoint=args.endpoint,
                            spool_db=args.spool_db,
                            deployment_binding=deployment_binding,
                            spool_token_env=args.spool_token_env,
                            timeout_seconds=args.timeout_seconds,
                            expected_live_audit=spool_audit,
                        )
                        if _database_identity_value(
                            live_spool_identity.get("db_identity"),
                            "live result spool",
                        ) != _database_identity_value(
                            genesis.get("spool_db_identity"),
                            "genesis result spool",
                        ):
                            raise R8RunnerRefusal(
                                "live result spool differs from frozen genesis"
                            )
                    previous_umask = os.umask(0o077)
                    try:
                        def completed_resume_transport(*_args, **_kwargs):
                            raise R8RunnerRefusal(
                                "completed resume attempted forbidden network traffic"
                            )

                        port = DurableSpoolJSONPort(
                            args.endpoint,
                            args.attempt_db,
                            spool_token_env=args.spool_token_env,
                            timeout_seconds=args.timeout_seconds,
                            transport=(
                                completed_resume_transport
                                if all_calls_complete
                                else None
                            ),
                            max_delivery_attempts=args.max_delivery_attempts,
                            require_no_checkpoint_on_close=True,
                        )
                    finally:
                        os.umask(previous_umask)
                    try:
                        _seal_private_sqlite_family(
                            args.attempt_db, "attempt ledger"
                        )
                        result = run_suite_v3_draft(
                            manifest,
                            execution_lock=execution_lock,
                            protocol_path=args.protocol,
                            model_port=port,
                            token_meter=meter,
                            max_workers=args.max_workers,
                            token_envelope_derivation=derivation_values,
                            prior_exposure_receipt=prior_exposure,
                            aborted_attempt_exposure_receipt=aborted_exposure,
                            environment_dependency_bundle=environment_bundle,
                            result_contract_path=args.result_contract,
                            judge_core_path=args.judge_core,
                            symposium_repo_root=args.symposium_repo_root,
                            tokenizer_dir=args.tokenizer_dir,
                            model_catalog_path=args.model_catalog,
                            model_weight_receipt_path=args.model_weight_receipt,
                            python_lock_path=args.python_lock,
                            spool_identity_preflight=endpoint_preflight,
                            resume_prefix=resume_prefix,
                            offline_complete_resume=all_calls_complete,
                            preregistration_artifact=preregistration_artifact,
                            preregistration_readback=preregistration_readback,
                            anchored_judge_path=args.anchored_judge,
                        )
                    finally:
                        port.close()
                    reservations["suite_draft"].commit(result)
            finally:
                reservations.close()
            output = {
                "status": "TERMINAL_DRAFT_NO_GOLD_OPENED",
                "draft_receipt_sha256": result["draft_receipt_sha256"],
                "item_runs": len(result["item_runs"]),
                "calls": result["live_transport_audit"]["call_count"],
            }
        elif args.command == "finalize":
            draft_value = read_json(args.draft, "suite draft")
            bindings_value = read_json(args.transport_bindings, "transport bindings")
            genesis_value = read_json(args.db_genesis_receipt, "DB genesis receipt")
            reservations = reserve_private_outputs(
                [("suite", args.output)],
                run_id=str(draft_value.get("run_id", "")),
                journal_path=args.reservation_journal,
                resume=args.resume,
                forbidden_paths=(
                    args.draft, args.transport_bindings, args.db_genesis_receipt,
                ),
            )
            try:
                result = finalize_suite_v3(
                    draft_value,
                    transport_bindings=bindings_value,
                    genesis_receipt=genesis_value,
                )
                reservations["suite"].commit(result)
            finally:
                reservations.close()
            output = {
                "status": "FINALIZED_NO_GOLD_OPENED",
                "suite_receipt_sha256": result["suite_receipt_sha256"],
                "item_runs": len(result["item_runs"]),
                "calls": result["transport_audit"]["call_count"],
            }
        elif args.command == "verify":
            result = read_json(args.suite, "suite")
            output = {
                "status": "VERIFIED_NO_GOLD_OPENED",
                "suite_receipt_sha256": verify_suite_v3_without_gold(result),
                "item_runs": len(result["item_runs"]),
                "calls": result["transport_audit"]["call_count"],
            }
        else:
            initialize_transport_pair(args.attempt_db, args.spool_db)
            output = {
                "status": "INITIALIZED_EMPTY_WAL_PAIR_NO_MODEL_CALLS",
                "attempt_db_identity": _database_identity(
                    args.attempt_db, "attempt ledger"
                ),
                "spool_db_identity": _database_identity(args.spool_db, "result spool"),
            }
        print(json.dumps(output, sort_keys=True))
        return 0
    except Exception as error:
        print(
            json.dumps({"status": "REFUSED", "reason": str(error)}, sort_keys=True),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEVELOPMENT_RUN_ID",
    "EXECUTION_LOCK_SCHEMA",
    "MANIFEST_SCHEMA",
    "R8RunnerRefusal",
    "SEALED_LOCK_SCHEMA",
    "SEALED_RUN_ID",
    "SUITE_DRAFT_SCHEMA",
    "SUITE_SCHEMA",
    "build_development_execution_lock",
    "capture_judge_hashes",
    "finalize_suite_v3",
    "initialize_transport_pair",
    "manifest_core_sha256",
    "read_stable_bytes",
    "read_stable_json",
    "validate_manifest_v3",
    "validate_execution_policy",
    "verify_fresh_transport_genesis",
    "verify_spool_endpoint_identity",
    "verify_spool_endpoint_resume_identity",
    "verify_suite_draft_without_gold",
    "verify_suite_v3_without_gold",
]
