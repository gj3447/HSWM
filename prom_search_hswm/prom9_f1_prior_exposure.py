#!/usr/bin/env python3
"""Build a private, fail-closed receipt for every prior HSWM F1 exposure.

The four historical Dataset Viewer pages are explicit offline inputs.  Their
opaque bytes remain embedded for audit, while item/source/component identity
is derived only from the allowlisted ``id``, ``question``, ``context``, and
``type`` fields.  Gold and judgment artifacts are inventoried as opaque bytes
and are never JSON-decoded by this module.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence

import bge_m3_embed as _bge_module
import model_deployment_receipt as _deployment_module
import prom_search_hswm.hswm_function_network as _function_network_module
import prom_search_hswm.hswm_function_registry as _registry_module
import prom_search_hswm.hswm_typed_ports as _typed_ports_module
import prom_search_hswm.prom9_prepare_2wiki_f1 as _data_preparer_core_module
import prom_search_hswm.prom9_protocol as _protocol_module
import prom_search_hswm.prom9_f1_r8_source as _source_module
import prom_search_hswm.prom9_f1_r8_environment as _environment_module
import prom_search_hswm.prom_f1_function_network as _network_adapter_module
from prom_search_hswm.hswm_function_registry import build_registry
from prom_search_hswm.hswm_function_network import (
    EvidenceCandidateV1,
    FunctionNetworkError,
    candidate_table_for_arm,
)
from prom_search_hswm.hswm_typed_ports import (
    canonical_json,
    canonical_sha256,
    output_json_schema,
    output_schema_sha256,
    port_digest,
    validate_port,
)
from prom_search_hswm.prom9_f1_r8_source import (
    COMPONENT_SCHEMA,
    SOURCE_ENTITY_SCHEMA,
    source_entity_id,
    verify_public_source_receipt,
)
from prom_search_hswm.prom9_f1_r8_transport_audit import (
    TransportAuditRefusal,
    canonical_schema_sha256,
    exact_schema_readback,
)
from prom_search_hswm.hswm_f1_sqlite_schema import (
    SQLiteAuthorityRefusal,
    database_generation,
)
from prom_search_hswm.prom_f1_function_network import _arm_overrides


SCHEMA = "hswm-prom9-f1-prior-exposure/v1"
ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V2 = (
    "hswm-prom9-f1-aborted-attempt-exposure/v2"
)
ABORTED_ATTEMPT_EXPOSURE_SCHEMA = (
    "hswm-prom9-f1-aborted-attempt-exposure/v3"
)
ABORTED_ATTEMPT_STATUS = "ABORTED_QUARANTINED"
ABORTED_ATTEMPT_PRIVATE_WITNESS_SCHEMA = (
    "hswm-prom9-f1-aborted-attempt-private-witness/v1"
)
_ABORTED_ATTEMPT_V2_CANONICAL_SCHEMA_SHA256 = {
    "attempt": "29f19831499bddea83595ddce2fd97613d03d4b0b498531beeab6f195dc44139",
    "spool": "4e65e2756c820d6d0e36f9e02dbe796ae0e5c0933409aaec86133770543057be",
}
_HISTORICAL_V8_SCHEMA_AUTHORITIES = {
    "attempt": "attempt",
    "spool": "spool_historical_v8",
}
DATASET_SERVER = "https://datasets-server.huggingface.co"
EXPECTED_PAGE_SPECS = ((0, 1), (0, 4), (0, 8), (4, 100))
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROW_KEYS = {
    "id", "question", "answer", "context", "supporting_facts",
    "evidences", "type",
}
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_GENESIS = "0" * 64
_F1_ARMS = (
    "typed_hswm_three_function_network",
    "flat_single_llm_three_call_workflow",
    "vector_memory_three_call_workflow",
    "typed_network_role_removed_schema_preserving_null",
    "typed_network_with_role_instructions_shuffled_but_ports_preserved",
)
_CURRENT_PRODUCER_IMPORT_LFP = (
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
_HISTORICAL_RUNTIME_COMMITS = {
    "hswm_executable": "63a03623d98220800e9921527510d02971b882dc",
    "hswm_carrier": "4da21495ed52d8c85ae112fdf5cf732c14fabaf9",
    "symposium": "09a14b3231b07d94533032efcfdbb24173143ebd",
}
_HISTORICAL_REPLAY_IMPORT_LFP = (
    "hswm_next_research_harness.py",
    "prom_search_hswm/hswm_call_receipt.py",
    "prom_search_hswm/hswm_f1_durable_transport.py",
    "prom_search_hswm/hswm_function_network.py",
    "prom_search_hswm/hswm_function_registry.py",
    "prom_search_hswm/hswm_result_spool.py",
    "prom_search_hswm/hswm_token_meter.py",
    "prom_search_hswm/hswm_typed_ports.py",
    "prom_search_hswm/prom9_f1_envelope.py",
    "prom_search_hswm/prom9_f1_r8_source.py",
    "prom_search_hswm/prom9_prepare_2wiki_f1.py",
    "prom_search_hswm/prom9_protocol.py",
    "prom_search_hswm/prom_f1_function_network.py",
)
_CALL_CONTRACTS = {
    1: ("QF_QUERY_COMPILER", "QueryEnvelopeV1", "QueryPlanV1"),
    2: ("BF_BOND_PROPOSER", "BondScoringEnvelopeV1", "BondProposalV1"),
    3: ("AF_ANSWER_SYNTHESIZER", "AnswerContextV1", "AnswerEnvelopeV1"),
}
_HISTORICAL_SELECTION_SEED = 20260728
_HISTORICAL_DEVELOPMENT_OFFSETS = (104, 204, 304, 404)
_HISTORICAL_CONFIRMATORY_OFFSETS = (
    504, 604, 704, 804, 904, 1004, 1104, 1204, 1304, 1404,
)
_HISTORICAL_DEVELOPMENT_COMPONENTS = 48
_HISTORICAL_SEED_BLOCKS = 12
_HISTORICAL_COMPONENTS_PER_BLOCK = 4
_HISTORICAL_SELECTION_KEY_SCHEMA = "hswm-f1-r8-component-selection/v1"
_HISTORICAL_BLOCK_ASSIGNMENT_SCHEMA = "hswm-f1-r8-power-block-assignment/v1"
_HISTORICAL_DEPENDENCY_NAMES = frozenset(
    {
        "runner", "private_output", "environment", "lock_builder",
        "power_builder", "power_cli", "prior_exposure", "data_preparer_core",
        "function_network_adapter", "protocol_loader",
        "terminal_transport_exporter", "function_network", "durable_transport",
        "result_spool", "call_receipt", "function_registry", "token_meter",
        "typed_ports", "token_envelope", "model_deployment_receipt_code",
        "model_snapshot_attestation_core", "protocol_json", "data_preparer",
        "judge_core", "result_contract", "tokenizer_vocab", "tokenizer_merges",
        "tokenizer_config", "model_catalog", "model_deployment_receipt",
        "python_lock",
    }
)
_LINUX_SIGNAL_NAMES = {
    1: "SIGHUP", 2: "SIGINT", 3: "SIGQUIT", 4: "SIGILL", 5: "SIGTRAP",
    6: "SIGABRT", 7: "SIGBUS", 8: "SIGFPE", 9: "SIGKILL", 10: "SIGUSR1",
    11: "SIGSEGV", 12: "SIGUSR2", 13: "SIGPIPE", 14: "SIGALRM",
    15: "SIGTERM", 16: "SIGSTKFLT", 17: "SIGCHLD", 18: "SIGCONT",
    19: "SIGSTOP", 20: "SIGTSTP", 21: "SIGTTIN", 22: "SIGTTOU",
    23: "SIGURG", 24: "SIGXCPU", 25: "SIGXFSZ", 26: "SIGVTALRM",
    27: "SIGPROF", 28: "SIGWINCH", 29: "SIGIO", 30: "SIGPWR",
    31: "SIGSYS",
}
_DURABLE_CALL_SCHEMA = "hswm-f1-durable-call-ledger/v1"
_SPOOL_ROUTE_PREFIX = "/v1/hswm/calls/"
_CALL_KEYS = {
    "physical_call_id", "run_id", "arm_id", "item_id", "call_index",
    "function_id", "model", "model_revision", "system_prompt", "input_type",
    "input_payload", "output_type", "max_output_tokens",
}
_EVENT_TRANSITIONS = {
    "PREPARED": (None,),
    "SENT": ("PREPARED", "DELIVERY_AMBIGUOUS", "SENT"),
    "DELIVERY_AMBIGUOUS": ("SENT",),
    "RAW_COMPLETE": ("SENT",),
    "ENVELOPE_VALID": ("RAW_COMPLETE",),
    "SCHEMA_VALID": ("ENVELOPE_VALID",),
    "ACCEPTED": ("SCHEMA_VALID",),
    "REJECTED_PROTOCOL": (
        "RAW_COMPLETE", "ENVELOPE_VALID", "SCHEMA_VALID", "SENT",
    ),
    "AMBIGUOUS_ABORT": ("PREPARED", "SENT", "DELIVERY_AMBIGUOUS"),
}
_ATTEMPT_COLUMNS = {
    "call_state": [
        "physical_call_id", "intent_sha256", "intent_bytes", "request_sha256",
        "endpoint", "request_bytes", "status", "response_status",
        "response_headers", "response_body", "response_sha256",
        "model_response", "model_response_sha256", "call_receipt",
        "call_receipt_sha256", "terminal_code",
    ],
    "item_runs": [
        "run_id", "arm_id", "item_id", "run_receipt_sha256", "item_run_bytes",
    ],
    "attempt_events": [
        "sequence", "physical_call_id", "event_type", "event_bytes",
        "previous_event_sha256", "event_sha256",
    ],
}
_SPOOL_COLUMNS = {
    "spool_calls": [
        "physical_call_id", "intent_sha256", "request_sha256", "request_bytes",
        "status", "response_status", "response_headers", "response_body",
        "response_sha256", "error_class",
    ]
}
_PROTECTED_COLUMNS = {
    ("call_state", "response_headers"),
    ("call_state", "response_body"),
    ("call_state", "model_response"),
    ("call_state", "call_receipt"),
    ("item_runs", "item_run_bytes"),
    ("spool_calls", "response_headers"),
    ("spool_calls", "response_body"),
}
_ARTIFACT_SELF_HASH_FIELDS = {
    "selection_receipt": ("selection_receipt_sha256",),
    "manifest": (),
    "source_receipt": ("source_receipt_sha256",),
    "execution_lock": ("lock_sha256",),
    "db_genesis_receipt": ("genesis_sha256",),
    "environment_dependency_bundle": ("bundle_sha256",),
    "model_deployment_receipt": ("receipt_sha256",),
    "spool_identity_receipt": ("preflight_sha256",),
}
_ARTIFACT_SELF_HASH_EXCLUSIONS = {
    "model_deployment_receipt": ("receipt_sha256", "deployment_id"),
}
_INCIDENT_ARTIFACT_SCHEMAS = {
    "selection_receipt": "hswm-prom9-f1-r8-cohort-selection/v2",
    "manifest": "hswm-prom9-f1-manifest/v3",
    "source_receipt": "hswm-prom9-f1-r8-source-receipt/v3",
    "execution_lock": "hswm-prom9-f1-r8-execution-lock/v2",
    "db_genesis_receipt": "hswm-prom9-f1-r8-transport-genesis/v1",
    "environment_dependency_bundle": (
        "hswm-prom9-f1-r8-environment-dependency-bundle/v1"
    ),
    "model_deployment_receipt": "hswm-openai-deployment-attestation/v2",
    "spool_identity_receipt": "hswm-prom9-f1-r8-spool-endpoint-preflight/v2",
}
_INCIDENT_SELECTION_FIELDS = {
    "schema_version", "selection_policy", "prior_exposure_receipt_sha256",
    "development", "confirmatory", "pairwise_disjoint", "source_pages",
    "answers_disclosed_to_stdout", "selection_receipt_sha256",
}
_INCIDENT_LOCK_FIELDS = {
    "schema_version", "purpose", "run_id", "mode", "manifest_sha256",
    "preregistration_artifact_sha256", "selection_receipt_sha256",
    "prior_exposure_receipt_sha256", "public_source_receipt_sha256",
    "gold_source_receipt_sha256", "gold_sha256", "evaluator_receipt_sha256",
    "db_genesis_receipt_sha256", "environment_receipt_sha256",
    "dependency_receipt_sha256",
    "environment_dependency_compatibility_root_sha256",
    "environment_dependency_bundle_sha256", "hswm_commit",
    "result_contract_sha256", "judge_core_sha256", "judge_core_file_sha256",
    "model", "model_revision", "upstream_endpoint",
    "deployment_receipt_sha256", "deployment_id", "served_model",
    "protocol_sha256", "registries_root_sha256", "token_envelope_sha256",
    "generation_policy_sha256", "cohort_root_sha256",
    "candidate_universe_root_sha256", "forbidden_prior_item_ids",
    "forbidden_prior_source_entity_ids", "forbidden_prior_component_ids",
    "execution_policy", "gates", "lock_sha256",
}
_INCIDENT_GENESIS_FIELDS = {
    "schema_version", "run_id", "attempt_integrity", "spool_integrity",
    "attempt_journal_mode", "attempt_audit_connection_synchronous",
    "spool_journal_mode", "spool_audit_connection_synchronous",
    "attempt_user_version", "spool_user_version", "attempt_schema_sha256",
    "spool_schema_sha256", "attempt_db_identity", "spool_db_identity",
    "call_count", "item_run_count", "attempt_event_count", "spool_call_count",
    "genesis_sha256",
}
_INCIDENT_SPOOL_PREFLIGHT_FIELDS = {
    "schema_version", "run_id", "execution_lock_sha256", "db_genesis_sha256",
    "endpoint", "upstream_endpoint", "deployment_receipt_sha256",
    "deployment_id", "served_model", "model_revision", "endpoint_identity",
    "preflight_sha256",
}
_INCIDENT_SPOOL_IDENTITY_FIELDS = {
    "schema_version", "normalized_upstream_endpoint",
    "deployment_receipt_sha256", "deployment_id", "served_model",
    "model_revision", "db_identity", "audit", "identity_sha256",
}
_INCIDENT_SPOOL_AUDIT_FIELDS = {
    "schema_version", "journal_mode", "synchronous", "call_count",
    "status_counts", "completed_root_sha256", "audit_sha256",
}


class PriorExposureRefusal(RuntimeError):
    """The historical exposure boundary is incomplete or mutable."""


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise PriorExposureRefusal("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise PriorExposureRefusal("non-finite JSON number")


def _exact_json_equal(actual: object, expected: object) -> bool:
    """Compare JSON values without Python's bool/int/float equality aliases."""
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
                    for left, right in zip(actual, expected)
                )
        )
    return type(actual) is type(expected) and actual == expected


def _read_private_bytes(path: Path) -> bytes:
    target = Path(path)
    try:
        info = target.lstat()
    except OSError as error:
        raise PriorExposureRefusal("private input is unavailable") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise PriorExposureRefusal("private input must be a regular non-symlink file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise PriorExposureRefusal("private input must not be group/world accessible")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(target, flags)
    except OSError as error:
        raise PriorExposureRefusal("private input cannot be opened") from error
    payload = bytearray()
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != info.st_dev
            or opened.st_ino != info.st_ino
            or stat.S_IMODE(opened.st_mode) & 0o077
        ):
            raise PriorExposureRefusal("private input changed before being read")
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            payload.extend(chunk)
        after_fd = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after_path = target.lstat()
    except OSError as error:
        raise PriorExposureRefusal("private input cannot be restated") from error
    identity = lambda value: (  # noqa: E731 - compact immutable projection
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
    if (
        identity(info) != identity(after_fd)
        or identity(info) != identity(after_path)
        or len(payload) != info.st_size
    ):
        raise PriorExposureRefusal("private input changed while being read")
    return bytes(payload)


def _strict_object(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except PriorExposureRefusal:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PriorExposureRefusal(f"{label} is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise PriorExposureRefusal(f"{label} must be an object")
    return value


def _page_projection(
    page: Mapping[str, object], *, offset: int, length: int
) -> list[dict[str, object]]:
    wrapped_rows = page.get("rows")
    if not isinstance(wrapped_rows, list) or len(wrapped_rows) != length:
        raise PriorExposureRefusal("legacy page length drifted")
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for position, wrapped in enumerate(wrapped_rows):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("row"), dict):
            raise PriorExposureRefusal("legacy page row is malformed")
        row = wrapped["row"]
        if set(row) != _ROW_KEYS:
            raise PriorExposureRefusal("legacy page row schema drifted")
        item_id = row.get("id")
        question = row.get("question")
        question_type = row.get("type")
        context = row.get("context")
        if (
            not isinstance(item_id, str)
            or not item_id
            or item_id in seen
            or not isinstance(question, str)
            or not question
            or not isinstance(question_type, str)
            or not isinstance(context, dict)
            or set(context) != {"title", "sentences"}
        ):
            raise PriorExposureRefusal("legacy page allowlisted identity drifted")
        titles = context.get("title")
        sentence_groups = context.get("sentences")
        if (
            not isinstance(titles, list)
            or not isinstance(sentence_groups, list)
            or not titles
            or len(titles) != len(sentence_groups)
        ):
            raise PriorExposureRefusal("legacy page context arrays drifted")
        entities: list[str] = []
        normalized_context = {"title": [], "sentences": []}
        for title, sentences in zip(titles, sentence_groups):
            if (
                not isinstance(title, str)
                or not title
                or not isinstance(sentences, list)
                or any(not isinstance(sentence, str) for sentence in sentences)
            ):
                raise PriorExposureRefusal("legacy page paragraph drifted")
            normalized_sentences = [str(sentence) for sentence in sentences]
            normalized_context["title"].append(title)
            normalized_context["sentences"].append(normalized_sentences)
            entities.append(source_entity_id(title, normalized_sentences))
        seen.add(item_id)
        result.append(
            {
                "dataset_row_index": offset + position,
                "item_id": item_id,
                "question": question,
                "context": normalized_context,
                "question_type": question_type,
                "question_sha256": canonical_sha256({"question": question}),
                "context_sha256": canonical_sha256({"context": normalized_context}),
                "source_entity_ids": sorted(set(entities)),
                "component_id": None,
            }
        )
    return result


def _assign_components(items: list[dict[str, object]]) -> list[dict[str, object]]:
    parent = {str(item["item_id"]): str(item["item_id"]) for item in items}

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
    for item in items:
        item_id = str(item["item_id"])
        for entity_id in item["source_entity_ids"]:
            prior = owner.setdefault(str(entity_id), item_id)
            union(item_id, prior)
    component_entities: dict[str, set[str]] = {}
    for item in items:
        component_entities.setdefault(find(str(item["item_id"])), set()).update(
            str(value) for value in item["source_entity_ids"]
        )
    component_ids = {
        root: canonical_sha256(
            {
                "schema_version": COMPONENT_SCHEMA,
                "source_entity_ids": sorted(entities),
            }
        )
        for root, entities in component_entities.items()
    }
    components: dict[str, dict[str, object]] = {}
    for item in items:
        item_id = str(item["item_id"])
        component_id = component_ids[find(item_id)]
        item["component_id"] = component_id
        component = components.setdefault(
            component_id,
            {
                "component_id": component_id,
                "item_ids": [],
                "source_entity_ids": sorted(component_entities[find(item_id)]),
            },
        )
        component["item_ids"].append(item_id)
    for component in components.values():
        component["item_ids"].sort()
    return [components[key] for key in sorted(components)]


def _tree_entries(root: Path) -> list[tuple[str, int, int, int, int]]:
    result: list[tuple[str, int, int, int, int]] = []
    for path in sorted(Path(root).rglob("*"), key=lambda value: value.as_posix()):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise PriorExposureRefusal("artifact tree contains a symlink")
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise PriorExposureRefusal("artifact tree contains a special file")
        result.append(
            (relative, info.st_size, stat.S_IMODE(info.st_mode), info.st_mtime_ns, info.st_ino)
        )
    return result


def _hash_file_stable(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
    ):
        raise PriorExposureRefusal("artifact changed while hashing")
    return digest.hexdigest()


def inventory_stable_tree(alias: str, root: Path) -> list[dict[str, object]]:
    if not alias or "/" in alias or "=" in alias:
        raise PriorExposureRefusal("artifact alias is invalid")
    resolved = Path(root).resolve(strict=True)
    if not resolved.is_dir():
        raise PriorExposureRefusal("artifact root must be a directory")
    before = _tree_entries(resolved)
    inventory = [
        {
            "root_alias": alias,
            "path": relative,
            "size_bytes": size,
            "mode": mode,
            "sha256": _hash_file_stable(resolved / relative),
        }
        for relative, size, mode, _mtime, _inode in before
    ]
    after = _tree_entries(resolved)
    if before != after:
        raise PriorExposureRefusal("artifact tree changed while hashing")
    return inventory


def _extract_item_ids(document: Mapping[str, object], kind: str) -> list[str]:
    if kind == "manifest":
        rows = document.get("items")
        key = "item_id"
    elif kind == "suite":
        rows = document.get("item_runs")
        key = "item_id"
    elif kind == "source_receipt":
        rows = document.get("rows")
        key = "item_id"
    else:
        raise PriorExposureRefusal("unsupported identity artifact kind")
    if not isinstance(rows, list) or not rows:
        raise PriorExposureRefusal("identity artifact has no rows")
    values = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get(key), str):
            raise PriorExposureRefusal("identity artifact row drifted")
        values.append(str(row[key]))
    unique = sorted(set(values))
    if kind != "suite" and len(unique) != len(values):
        raise PriorExposureRefusal("identity artifact repeats an item")
    return unique


def _identity_kind(path: Path) -> str | None:
    name = path.name
    if name.startswith("manifest") and name.endswith(".json"):
        return "manifest"
    if name == "suite.json":
        return "suite"
    if "source.receipt" in name and name.endswith(".json"):
        return "source_receipt"
    return None


def _legacy_bindings(
    roots: Mapping[str, Path],
    page_items: Mapping[tuple[int, int], set[str]],
    page_hashes: Mapping[tuple[int, int], str],
    aggregate_items: set[str],
) -> tuple[list[dict[str, object]], dict[str, int], int]:
    bindings: list[dict[str, object]] = []
    counts = {"manifest": 0, "suite": 0, "source_receipt": 0}
    run_dirs: set[tuple[str, str]] = set()
    for alias, root in roots.items():
        resolved = Path(root).resolve(strict=True)
        for directory in sorted(
            (path for path in resolved.rglob("f1-2wiki-*") if path.is_dir()),
            key=lambda value: value.as_posix(),
        ):
            identity_paths = [
                path for path in directory.glob("*.json") if _identity_kind(path)
            ]
            if not identity_paths:
                raise PriorExposureRefusal("F1 run directory lacks an identity artifact")
            run_dirs.add((alias, directory.relative_to(resolved).as_posix()))
            run_sets: list[set[str]] = []
            for path in sorted(identity_paths):
                kind = _identity_kind(path)
                assert kind is not None
                raw = _read_private_bytes(path) if stat.S_IMODE(path.stat().st_mode) & 0o077 == 0 else path.read_bytes()
                document = _strict_object(raw, kind)
                item_ids = _extract_item_ids(document, kind)
                item_set = set(item_ids)
                if not item_set <= aggregate_items:
                    raise PriorExposureRefusal("historical artifact contains an unbound item")
                matches = [spec for spec, values in page_items.items() if values == item_set]
                if len(matches) != 1:
                    raise PriorExposureRefusal("historical artifact does not match one frozen page")
                if kind == "source_receipt":
                    declared = document.get("source_receipt_sha256")
                    unsigned = dict(document)
                    unsigned.pop("source_receipt_sha256", None)
                    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
                        raise PriorExposureRefusal("legacy source receipt self-hash drifted")
                    matched_spec = matches[0]
                    if (
                        document.get("offset") != matched_spec[0]
                        or document.get("length") != matched_spec[1]
                        or document.get("viewer_response_sha256")
                        != page_hashes[matched_spec]
                    ):
                        raise PriorExposureRefusal(
                            "legacy source receipt page binding drifted"
                        )
                counts[kind] += 1
                run_sets.append(item_set)
                bindings.append(
                    {
                        "root_alias": alias,
                        "path": path.relative_to(resolved).as_posix(),
                        "kind": kind,
                        "raw_sha256": hashlib.sha256(raw).hexdigest(),
                        "internal_sha256": document.get("source_receipt_sha256"),
                        "page_id": f"validation-o{matches[0][0]}-n{matches[0][1]}",
                        "item_set_sha256": canonical_sha256(item_ids),
                    }
                )
            if any(values != run_sets[0] for values in run_sets[1:]):
                raise PriorExposureRefusal("identity artifacts disagree within an F1 run")
    return sorted(bindings, key=lambda value: (str(value["root_alias"]), str(value["path"]))), counts, len(run_dirs)


def build_prior_exposure_receipt(
    *,
    page_files: Mapping[tuple[int, int], tuple[Path, str]],
    artifact_roots: Mapping[str, Path],
    dataset: str,
    config: str,
    split: str,
    expected_run_dirs: int,
    expected_legacy_source_receipts: int,
    expected_manifests: int,
    expected_suites: int,
) -> dict[str, object]:
    if set(page_files) != set(EXPECTED_PAGE_SPECS):
        raise PriorExposureRefusal("the exact four legacy pages are required")
    pages: list[dict[str, object]] = []
    projections_by_spec: dict[tuple[int, int], list[dict[str, object]]] = {}
    aggregate_by_index: dict[int, dict[str, object]] = {}
    for offset, length in EXPECTED_PAGE_SPECS:
        path, expected_sha = page_files[(offset, length)]
        if not _SHA256.fullmatch(expected_sha):
            raise PriorExposureRefusal("legacy page expectation is not a SHA-256")
        raw = _read_private_bytes(path)
        page = _strict_object(raw, "legacy Dataset Viewer page")
        canonical_page_sha = canonical_sha256(page)
        if canonical_page_sha != expected_sha:
            raise PriorExposureRefusal("legacy Dataset Viewer page hash drifted")
        projection = _page_projection(page, offset=offset, length=length)
        projections_by_spec[(offset, length)] = projection
        for item in projection:
            index = int(item["dataset_row_index"])
            prior = aggregate_by_index.setdefault(index, item)
            if prior != item:
                raise PriorExposureRefusal("overlapping legacy pages disagree")
        pages.append(
            {
                "page_id": f"validation-o{offset}-n{length}",
                "offset": offset,
                "length": length,
                "raw_bytes_sha256": hashlib.sha256(raw).hexdigest(),
                "canonical_viewer_response_sha256": canonical_page_sha,
                "payload_base64": base64.b64encode(raw).decode("ascii"),
                "whitelisted_projection_sha256": canonical_sha256(projection),
            }
        )
    if sorted(aggregate_by_index) != list(range(104)):
        raise PriorExposureRefusal("legacy page union is not exactly validation rows 0..103")
    items = [aggregate_by_index[index] for index in sorted(aggregate_by_index)]
    if len({str(item["item_id"]) for item in items}) != 104:
        raise PriorExposureRefusal("legacy page union does not contain 104 unique items")
    components = _assign_components(items)
    aggregate_items = {str(item["item_id"]) for item in items}
    page_items = {
        spec: {str(item["item_id"]) for item in projection}
        for spec, projection in projections_by_spec.items()
    }
    roots = {alias: Path(path).resolve(strict=True) for alias, path in artifact_roots.items()}
    inventory = [
        item
        for alias in sorted(roots)
        for item in inventory_stable_tree(alias, roots[alias])
    ]
    bindings, identity_counts, run_dir_count = _legacy_bindings(
        roots,
        page_items,
        {spec: page_files[spec][1] for spec in EXPECTED_PAGE_SPECS},
        aggregate_items,
    )
    if (
        run_dir_count != expected_run_dirs
        or identity_counts["source_receipt"] != expected_legacy_source_receipts
        or identity_counts["manifest"] != expected_manifests
        or identity_counts["suite"] != expected_suites
    ):
        raise PriorExposureRefusal("historical artifact completeness counts drifted")
    item_ids = sorted(aggregate_items)
    source_entities = sorted(
        {str(entity) for item in items for entity in item["source_entity_ids"]}
    )
    component_ids = sorted(str(component["component_id"]) for component in components)
    roots_block = {
        "pages": canonical_sha256(pages),
        "items": canonical_sha256(items),
        "source_entities": canonical_sha256(source_entities),
        "components": canonical_sha256(components),
        "legacy_receipts": canonical_sha256(bindings),
        "artifact_inventory": canonical_sha256(inventory),
    }
    unsigned = {
        "schema_version": SCHEMA,
        "dataset_identity": {
            "dataset": dataset,
            "config": config,
            "split": split,
            "dataset_server": DATASET_SERVER,
        },
        "privacy_policy": {
            "derived_fields": ["id", "question", "context", "type"],
            "opaque_only_fields": ["answer", "supporting_facts", "evidences"],
            "answers_disclosed_to_stdout": False,
            "private_mode": "0600",
        },
        "page_specs": [
            {"offset": offset, "length": length, "expected_sha256": page_files[(offset, length)][1]}
            for offset, length in EXPECTED_PAGE_SPECS
        ],
        "pages": pages,
        "items": items,
        "components": components,
        "legacy_source_receipts": bindings,
        "artifact_roots": [
            {"alias": alias, "resolved_path": str(roots[alias])}
            for alias in sorted(roots)
        ],
        "artifact_inventory": inventory,
        "roots": roots_block,
        "counts": {
            "pages": len(pages),
            "items": len(item_ids),
            "source_entities": len(source_entities),
            "components": len(component_ids),
            "run_directories": run_dir_count,
            "manifests": identity_counts["manifest"],
            "suites": identity_counts["suite"],
            "legacy_source_receipts": identity_counts["source_receipt"],
            "artifact_files": len(inventory),
        },
        "aggregate": {
            "prior_item_ids": item_ids,
            "prior_source_entity_ids": source_entities,
            "prior_component_ids": component_ids,
            "item_root_sha256": canonical_sha256(item_ids),
            "source_entity_root_sha256": canonical_sha256(source_entities),
            "component_root_sha256": canonical_sha256(component_ids),
        },
        "complete": True,
    }
    return {**unsigned, "prior_exposure_receipt_sha256": canonical_sha256(unsigned)}


def verify_prior_exposure_receipt(value: Mapping[str, object]) -> str:
    if value.get("schema_version") != SCHEMA or value.get("complete") is not True:
        raise PriorExposureRefusal("prior-exposure receipt is incomplete")
    unsigned = dict(value)
    declared = unsigned.pop("prior_exposure_receipt_sha256", None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise PriorExposureRefusal("prior-exposure receipt self-hash drifted")
    aggregate = value.get("aggregate")
    if not isinstance(aggregate, dict):
        raise PriorExposureRefusal("prior-exposure aggregate is absent")
    for key, root_key in (
        ("prior_item_ids", "item_root_sha256"),
        ("prior_source_entity_ids", "source_entity_root_sha256"),
        ("prior_component_ids", "component_root_sha256"),
    ):
        values = aggregate.get(key)
        if not isinstance(values, list) or canonical_sha256(values) != aggregate.get(root_key):
            raise PriorExposureRefusal("prior-exposure aggregate root drifted")
    return declared


def _strict_boundary_values(
    aggregate: Mapping[str, object], key: str, label: str
) -> list[str]:
    values = aggregate.get(key)
    if (
        not isinstance(values, list)
        or any(not isinstance(item, str) or not item for item in values)
        or values != sorted(set(values))
    ):
        raise PriorExposureRefusal(f"{label} are not a sorted unique string list")
    return values


def _read_stable_public_bytes(path: Path) -> bytes:
    """Read a regular file through one stable descriptor without a mode claim."""

    target = Path(path)
    try:
        before_path = target.lstat()
    except OSError as error:
        raise PriorExposureRefusal("evidence input is unavailable") from error
    if stat.S_ISLNK(before_path.st_mode) or not stat.S_ISREG(before_path.st_mode):
        raise PriorExposureRefusal("evidence input must be a regular non-symlink file")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags)
    except OSError as error:
        raise PriorExposureRefusal("evidence input cannot be opened") from error
    payload = bytearray()
    try:
        before_fd = os.fstat(descriptor)
        if (before_fd.st_dev, before_fd.st_ino) != (
            before_path.st_dev,
            before_path.st_ino,
        ):
            raise PriorExposureRefusal("evidence input changed before being read")
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            payload.extend(chunk)
        after_fd = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after_path = target.lstat()
    except OSError as error:
        raise PriorExposureRefusal("evidence input cannot be restated") from error

    def identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    if (
        identity(before_path) != identity(before_fd)
        or identity(before_path) != identity(after_fd)
        or identity(before_path) != identity(after_path)
        or len(payload) != before_path.st_size
    ):
        raise PriorExposureRefusal("evidence input changed while being read")
    return bytes(payload)


def _stable_public_file_binding(path: Path) -> dict[str, object]:
    """Stream one stable regular file into only its public size/hash binding."""

    target = Path(path)
    try:
        before_path = target.lstat()
    except OSError as error:
        raise PriorExposureRefusal("evidence input is unavailable") from error
    if stat.S_ISLNK(before_path.st_mode) or not stat.S_ISREG(before_path.st_mode):
        raise PriorExposureRefusal("evidence input must be a regular non-symlink file")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    digest = hashlib.sha256()
    total = 0
    try:
        descriptor = os.open(target, flags)
        before_fd = os.fstat(descriptor)
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
        after_fd = os.fstat(descriptor)
        after_path = target.lstat()
    except OSError as error:
        raise PriorExposureRefusal("evidence input cannot be hashed") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    def identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    if (
        identity(before_path) != identity(before_fd)
        or identity(before_path) != identity(after_fd)
        or identity(before_path) != identity(after_path)
        or total != before_path.st_size
    ):
        raise PriorExposureRefusal("evidence input changed while being hashed")
    return {"size_bytes": total, "sha256": digest.hexdigest()}


def _copy_stable_member(source: Path, destination: Path) -> dict[str, object]:
    source = Path(source)
    destination = Path(destination)
    try:
        before_path = source.lstat()
    except OSError as error:
        raise PriorExposureRefusal("SQLite authority member is unavailable") from error
    if (
        stat.S_ISLNK(before_path.st_mode)
        or not stat.S_ISREG(before_path.st_mode)
        or before_path.st_uid != os.geteuid()
        or before_path.st_nlink != 1
        or stat.S_IMODE(before_path.st_mode) != 0o600
    ):
        raise PriorExposureRefusal(
            "SQLite authority member must be owner-private and unique"
        )
    source_flags = (
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    destination_flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        source_fd = os.open(source, source_flags)
    except OSError as error:
        raise PriorExposureRefusal("SQLite authority member cannot be opened") from error
    try:
        opened_source = os.fstat(source_fd)
        if (opened_source.st_dev, opened_source.st_ino) != (
            before_path.st_dev,
            before_path.st_ino,
        ):
            raise PriorExposureRefusal("SQLite authority member changed before snapshot")
        try:
            destination_fd = os.open(destination, destination_flags, 0o600)
        except OSError as error:
            raise PriorExposureRefusal("SQLite snapshot member already exists") from error
        digest = hashlib.sha256()
        total = 0
        try:
            while True:
                chunk = os.read(source_fd, 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                total += len(chunk)
                pending = memoryview(chunk)
                while pending:
                    written = os.write(destination_fd, pending)
                    if written < 1:
                        raise PriorExposureRefusal("SQLite snapshot write made no progress")
                    pending = pending[written:]
            os.fsync(destination_fd)
            destination_info = os.fstat(destination_fd)
        finally:
            os.close(destination_fd)
        after_source_fd = os.fstat(source_fd)
    finally:
        os.close(source_fd)
    try:
        after_source_path = source.lstat()
        after_destination = destination.lstat()
    except OSError as error:
        raise PriorExposureRefusal("SQLite snapshot member cannot be restated") from error

    def identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    if (
        identity(before_path) != identity(opened_source)
        or identity(before_path) != identity(after_source_fd)
        or identity(before_path) != identity(after_source_path)
        or total != before_path.st_size
        or not stat.S_ISREG(destination_info.st_mode)
        or stat.S_IMODE(destination_info.st_mode) != 0o600
        or (destination_info.st_dev, destination_info.st_ino)
        != (after_destination.st_dev, after_destination.st_ino)
        or destination_info.st_size != total
    ):
        raise PriorExposureRefusal("SQLite authority changed while being snapshotted")
    return {
        "basename": destination.name,
        "size_bytes": total,
        "sha256": digest.hexdigest(),
    }


def _snapshot_sqlite_pair(
    source_main: Path, snapshot_dir: Path, *, label: str
) -> tuple[Path, dict[str, object]]:
    source_main = Path(source_main)
    source_info = source_main.lstat()
    if stat.S_ISLNK(source_info.st_mode) or not stat.S_ISREG(source_info.st_mode):
        raise PriorExposureRefusal("SQLite main identity is not a regular file")
    source_identity = {
        "resolved_path": str(source_main.resolve(strict=True)),
        "st_dev": source_info.st_dev,
        "st_ino": source_info.st_ino,
    }
    source_wal = Path(f"{source_main}-wal")
    destination_main = Path(snapshot_dir) / f"{label}.sqlite3"
    destination_wal = Path(f"{destination_main}-wal")
    main = _copy_stable_member(source_main, destination_main)
    wal = _copy_stable_member(source_wal, destination_wal)
    directory_fd = os.open(snapshot_dir, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    for source, recorded in ((source_main, main), (source_wal, wal)):
        binding = _stable_public_file_binding(source)
        if (
            binding["size_bytes"] != recorded["size_bytes"]
            or binding["sha256"] != recorded["sha256"]
        ):
            raise PriorExposureRefusal("SQLite authority changed after pair snapshot")
    authority = {"main": main, "wal": wal}
    return destination_main, {
        "authority_members": ["main", "wal"],
        "members": authority,
        "authority_root_sha256": canonical_sha256(authority),
        "source_identity": source_identity,
    }


def _verify_sqlite_source_pair(
    source_main: Path, snapshot: Mapping[str, object]
) -> None:
    members = snapshot.get("members")
    identity = snapshot.get("source_identity")
    if not isinstance(members, Mapping) or not isinstance(identity, Mapping):
        raise PriorExposureRefusal("SQLite source snapshot binding is absent")
    main_info = Path(source_main).lstat()
    observed_identity = {
        "resolved_path": str(Path(source_main).resolve(strict=True)),
        "st_dev": main_info.st_dev,
        "st_ino": main_info.st_ino,
    }
    if observed_identity != identity:
        raise PriorExposureRefusal("SQLite source identity changed after capture")
    for suffix, member_name in (("", "main"), ("-wal", "wal")):
        binding = _stable_public_file_binding(Path(f"{source_main}{suffix}"))
        member = members.get(member_name)
        if (
            not isinstance(member, Mapping)
            or binding["size_bytes"] != member.get("size_bytes")
            or binding["sha256"] != member.get("sha256")
        ):
            raise PriorExposureRefusal("SQLite source pair changed after capture")


def _sqlite_authorizer(
    action: int,
    argument_one: str | None,
    argument_two: str | None,
    _database: str | None,
    _trigger: str | None,
) -> int:
    if action == sqlite3.SQLITE_READ and (str(argument_one), str(argument_two)) in (
        _PROTECTED_COLUMNS
    ):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _open_snapshot_read_only(
    path: Path,
    *,
    expected_columns: Mapping[str, list[str]],
    authority: str,
    label: str,
) -> tuple[sqlite3.Connection, dict[str, object]]:
    target = Path(path).resolve(strict=True)
    try:
        connection = sqlite3.connect(
            f"{target.as_uri()}?mode=ro", uri=True, isolation_level=None, timeout=5.0
        )
        connection.row_factory = sqlite3.Row
        connection.set_authorizer(_sqlite_authorizer)
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        integrity = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).casefold()
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        observed_columns = {
            table: [
                str(row[1])
                for row in connection.execute(f"PRAGMA table_info({table})")
            ]
            for table in expected_columns
        }
        exact_version, exact_schema = exact_schema_readback(
            connection, authority, f"{label} snapshot"
        )
    except (sqlite3.Error, TransportAuditRefusal) as error:
        try:
            connection.close()
        except UnboundLocalError:
            pass
        raise PriorExposureRefusal(
            f"{label} snapshot read-only validation refused: {error}"
        ) from error
    if integrity != "ok" or journal_mode != "wal" or user_version != 1:
        connection.close()
        raise PriorExposureRefusal(f"{label} snapshot integrity or WAL identity drifted")
    if (
        tables != set(expected_columns)
        or observed_columns != dict(expected_columns)
        or exact_version != user_version
    ):
        connection.close()
        raise PriorExposureRefusal(f"{label} snapshot schema inventory drifted")
    return connection, {
        "integrity": integrity,
        "journal_mode": journal_mode,
        "user_version": user_version,
        "schema_sha256": canonical_sha256(
            {"user_version": user_version, "tables": observed_columns}
        ),
        "canonical_schema_sha256": exact_schema,
    }


def _strict_canonical_blob(raw: bytes, label: str) -> dict[str, object]:
    value = _strict_object(raw, label)
    if canonical_json(value).encode("utf-8") != raw:
        raise PriorExposureRefusal(f"{label} is not canonical JSON")
    return value


def _artifact_binding(
    name: str, path: Path
) -> tuple[dict[str, object], dict[str, object]]:
    raw = _read_private_bytes(path)
    value = _strict_object(raw, name.replace("_", " "))
    if value.get("schema_version") != _INCIDENT_ARTIFACT_SCHEMAS[name]:
        raise PriorExposureRefusal(f"{name} schema version drifted")
    declared: dict[str, str] = {}
    for field in _ARTIFACT_SELF_HASH_FIELDS[name]:
        candidate = value.get(field)
        if not isinstance(candidate, str) or _SHA256.fullmatch(candidate) is None:
            raise PriorExposureRefusal(f"{name} declared hash drifted")
        unsigned = dict(value)
        for excluded in _ARTIFACT_SELF_HASH_EXCLUSIONS.get(name, (field,)):
            unsigned.pop(excluded, None)
        if canonical_sha256(unsigned) != candidate:
            raise PriorExposureRefusal(f"{name} self-hash verification failed")
        declared[field] = candidate
    return value, {
        "basename": Path(path).name,
        "size_bytes": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "canonical_sha256": canonical_sha256(value),
        "schema_version": value.get("schema_version"),
        "declared_hashes": declared,
    }


def _verify_self_hash_mapping(
    value: object, field: str, label: str
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise PriorExposureRefusal(f"{label} is not an object")
    unsigned = dict(value)
    declared = unsigned.pop(field, None)
    if not _is_sha256(declared) or canonical_sha256(unsigned) != declared:
        raise PriorExposureRefusal(f"{label} self-hash drifted")
    return value


def _verify_database_identity_value(
    value: object, label: str
) -> Mapping[str, object]:
    if (
        not isinstance(value, Mapping)
        or set(value) != {"resolved_path", "st_dev", "st_ino"}
        or not isinstance(value.get("resolved_path"), str)
        or not value.get("resolved_path")
        or any(
            isinstance(value.get(key), bool)
            or not isinstance(value.get(key), int)
            or int(value[key]) < minimum
            for key, minimum in (("st_dev", 0), ("st_ino", 1))
        )
    ):
        raise PriorExposureRefusal(f"{label} database identity drifted")
    return value


def _historical_component_key(component_id: str, purpose: str) -> tuple[str, str]:
    return (
        canonical_sha256(
            {
                "schema_version": _HISTORICAL_SELECTION_KEY_SCHEMA,
                "seed": _HISTORICAL_SELECTION_SEED,
                "purpose": purpose,
                "component_id": component_id,
            }
        ),
        component_id,
    )


def _historical_block_key(component_id: str) -> tuple[str, str]:
    return (
        canonical_sha256(
            {
                "schema_version": _HISTORICAL_BLOCK_ASSIGNMENT_SCHEMA,
                "seed": _HISTORICAL_SELECTION_SEED,
                "component_id": component_id,
            }
        ),
        component_id,
    )


def _historical_redacted_page(
    page: Mapping[str, object], *, purpose: str, offset: int
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rows = page.get("redacted_rows")
    if (
        set(page)
        != {
            "offset", "length", "purpose", "redacted_rows",
            "redacted_rows_sha256", "whitelisted_projection_sha256",
        }
        or page.get("purpose") != purpose
        or page.get("offset") != offset
        or page.get("length") != 100
        or not isinstance(rows, list)
        or len(rows) != 100
        or canonical_sha256(rows) != page.get("redacted_rows_sha256")
    ):
        raise PriorExposureRefusal("historical selection page drifted")
    normalized: list[dict[str, object]] = []
    fake_rows: list[dict[str, object]] = []
    for index, entry in enumerate(rows):
        row = entry.get("row") if isinstance(entry, Mapping) else None
        if (
            not isinstance(entry, Mapping)
            or set(entry) != {"dataset_row_index", "row"}
            or entry.get("dataset_row_index") != offset + index
            or not isinstance(row, Mapping)
            or set(row) != {"id", "question", "context", "type"}
        ):
            raise PriorExposureRefusal("historical selection page allowlist drifted")
        normalized_entry = json.loads(canonical_json(dict(entry)))
        normalized.append(normalized_entry)
        fake_rows.append(
            {
                "row": {
                    **dict(row),
                    "answer": "",
                    "supporting_facts": {"title": [], "sent_id": []},
                    "evidences": [],
                }
            }
        )
    projections = _page_projection({"rows": fake_rows}, offset=offset, length=100)
    if canonical_sha256(projections) != page.get("whitelisted_projection_sha256"):
        raise PriorExposureRefusal("historical selection page projection drifted")
    return projections, normalized


def _historical_selected_block(
    components: Sequence[Mapping[str, object]],
    entries_by_item: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    item_ids = sorted(
        str(item_id)
        for component in components
        for item_id in component["item_ids"]
    )
    try:
        selected_rows = sorted(
            (dict(entries_by_item[item_id]) for item_id in item_ids),
            key=lambda entry: int(entry["dataset_row_index"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise PriorExposureRefusal("historical selected-row preimage drifted") from error
    source_entity_ids = sorted(
        {
            str(source)
            for component in components
            for source in component["source_entity_ids"]
        }
    )
    component_ids = sorted(str(component["component_id"]) for component in components)
    return {
        "item_ids": item_ids,
        "source_entity_ids": source_entity_ids,
        "component_ids": component_ids,
        "selected_rows": selected_rows,
        "selected_rows_sha256": canonical_sha256(selected_rows),
        "item_root_sha256": canonical_sha256(item_ids),
        "source_entity_root_sha256": canonical_sha256(source_entity_ids),
        "component_root_sha256": canonical_sha256(component_ids),
    }


def _verify_historical_selection(
    selection: Mapping[str, object], lock: Mapping[str, object]
) -> list[dict[str, object]]:
    expected_policy = {
        "selection_seed": _HISTORICAL_SELECTION_SEED,
        "development_pool_offsets": list(_HISTORICAL_DEVELOPMENT_OFFSETS),
        "confirmatory_pool_offsets": list(_HISTORICAL_CONFIRMATORY_OFFSETS),
        "page_length": 100,
        "development_components": _HISTORICAL_DEVELOPMENT_COMPONENTS,
        "seed_blocks": _HISTORICAL_SEED_BLOCKS,
        "components_per_seed_block": _HISTORICAL_COMPONENTS_PER_BLOCK,
        "confirmatory_items": 100,
        "confirmatory_component_size": 1,
        "selection_key_schema": _HISTORICAL_SELECTION_KEY_SCHEMA,
        "block_assignment_schema": _HISTORICAL_BLOCK_ASSIGNMENT_SCHEMA,
        "derived_fields": ["id", "question", "context", "type"],
        "answers_used_for_selection": False,
    }
    if (
        not _exact_json_equal(selection.get("selection_policy"), expected_policy)
        or selection.get("prior_exposure_receipt_sha256")
        != lock.get("prior_exposure_receipt_sha256")
    ):
        raise PriorExposureRefusal("historical selection policy/binding drifted")
    pages = selection.get("source_pages")
    expected_pages = [
        ("development", offset) for offset in _HISTORICAL_DEVELOPMENT_OFFSETS
    ] + [
        ("confirmatory_pool", offset)
        for offset in _HISTORICAL_CONFIRMATORY_OFFSETS
    ]
    if not isinstance(pages, list) or len(pages) != len(expected_pages):
        raise PriorExposureRefusal("historical selection page inventory drifted")
    development_rows: list[dict[str, object]] = []
    development_entries: list[dict[str, object]] = []
    confirmatory_rows: list[dict[str, object]] = []
    confirmatory_entries: list[dict[str, object]] = []
    for raw_page, (purpose, offset) in zip(pages, expected_pages):
        if not isinstance(raw_page, Mapping):
            raise PriorExposureRefusal("historical selection page drifted")
        projections, entries = _historical_redacted_page(
            raw_page, purpose=purpose, offset=offset
        )
        if purpose == "development":
            development_rows.extend(projections)
            development_entries.extend(entries)
        else:
            confirmatory_rows.extend(projections)
            confirmatory_entries.extend(entries)
    for label, entries in (
        ("development", development_entries),
        ("confirmatory", confirmatory_entries),
    ):
        identifiers = [str(entry["row"]["id"]) for entry in entries]
        if len(identifiers) != len(set(identifiers)):
            raise PriorExposureRefusal(f"historical {label} pool item IDs repeat")

    prior_items = set(str(item) for item in lock["forbidden_prior_item_ids"])
    prior_sources = set(
        str(source) for source in lock["forbidden_prior_source_entity_ids"]
    )
    development_components = _assign_components(
        [dict(row) for row in development_rows]
    )
    eligible_development = [
        component
        for component in development_components
        if not (set(component["item_ids"]) & prior_items)
        and not (set(component["source_entity_ids"]) & prior_sources)
    ]
    selected_development = sorted(
        eligible_development,
        key=lambda component: _historical_component_key(
            str(component["component_id"]), "development_power"
        ),
    )[:_HISTORICAL_DEVELOPMENT_COMPONENTS]
    if (
        len(selected_development) != _HISTORICAL_DEVELOPMENT_COMPONENTS
        or not any(len(component["item_ids"]) == 1 for component in selected_development)
        or not any(len(component["item_ids"]) > 1 for component in selected_development)
    ):
        raise PriorExposureRefusal("historical development selection drifted")
    block_order = sorted(
        selected_development,
        key=lambda component: _historical_block_key(str(component["component_id"])),
    )
    development_schedule = [
        {
            "component_id": component["component_id"],
            "item_ids": sorted(component["item_ids"]),
            "source_entity_ids": sorted(component["source_entity_ids"]),
            "cluster_size": len(component["item_ids"]),
            "seed_block": rank // _HISTORICAL_COMPONENTS_PER_BLOCK,
            "carryover_block": rank % _HISTORICAL_COMPONENTS_PER_BLOCK,
        }
        for rank, component in enumerate(block_order)
    ]
    development_by_item = {
        str(entry["row"]["id"]): entry for entry in development_entries
    }
    expected_development = {
        **_historical_selected_block(selected_development, development_by_item),
        "component_schedule": development_schedule,
        "selection_root_sha256": canonical_sha256(
            [component["component_id"] for component in selected_development]
        ),
    }

    confirmatory_components = _assign_components(
        [dict(row) for row in confirmatory_rows]
    )
    development_items = set(expected_development["item_ids"])
    development_sources = set(expected_development["source_entity_ids"])
    eligible_confirmatory = [
        component
        for component in confirmatory_components
        if len(component["item_ids"]) == 1
        and not (set(component["item_ids"]) & (prior_items | development_items))
        and not (
            set(component["source_entity_ids"])
            & (prior_sources | development_sources)
        )
    ]
    selected_confirmatory = sorted(
        eligible_confirmatory,
        key=lambda component: _historical_component_key(
            str(component["component_id"]), "confirmatory_r8"
        ),
    )[:100]
    if len(selected_confirmatory) != 100:
        raise PriorExposureRefusal("historical confirmatory selection drifted")
    confirmatory_schedule = [
        {
            "component_id": component["component_id"],
            "item_ids": sorted(component["item_ids"]),
            "source_entity_ids": sorted(component["source_entity_ids"]),
            "cluster_size": 1,
        }
        for component in selected_confirmatory
    ]
    confirmatory_by_item = {
        str(entry["row"]["id"]): entry for entry in confirmatory_entries
    }
    expected_confirmatory = {
        **_historical_selected_block(selected_confirmatory, confirmatory_by_item),
        "component_schedule": confirmatory_schedule,
        "selection_root_sha256": canonical_sha256(
            [component["component_id"] for component in selected_confirmatory]
        ),
    }
    if (
        not _exact_json_equal(selection.get("development"), expected_development)
        or not _exact_json_equal(selection.get("confirmatory"), expected_confirmatory)
    ):
        raise PriorExposureRefusal("historical selection cohorts do not replay")
    return list(expected_development["selected_rows"])


def _verify_incident_artifact_semantics(
    values: Mapping[str, Mapping[str, object]],
    historical_replay: Mapping[str, object] | None = None,
) -> None:
    selection = values["selection_receipt"]
    manifest = values["manifest"]
    source_receipt = values["source_receipt"]
    lock = values["execution_lock"]
    genesis = values["db_genesis_receipt"]
    environment = values["environment_dependency_bundle"]
    deployment = values["model_deployment_receipt"]
    preflight = values["spool_identity_receipt"]
    if (
        set(selection) != _INCIDENT_SELECTION_FIELDS
        or selection.get("answers_disclosed_to_stdout") is not False
        or selection.get("pairwise_disjoint")
        != {"item_ids": True, "source_entity_ids": True, "component_ids": True}
        or not _is_sha256(selection.get("prior_exposure_receipt_sha256"))
        or not isinstance(selection.get("selection_policy"), Mapping)
        or not isinstance(selection.get("source_pages"), list)
        or len(selection["source_pages"]) != 14
    ):
        raise PriorExposureRefusal("historical selection receipt semantics drifted")
    cohort_fields = {
        "component_ids", "component_root_sha256", "component_schedule",
        "item_ids", "item_root_sha256", "selected_rows", "selected_rows_sha256",
        "selection_root_sha256", "source_entity_ids", "source_entity_root_sha256",
    }
    for cohort_name, expected_items in (("development", 55), ("confirmatory", 100)):
        cohort = selection.get(cohort_name)
        if not isinstance(cohort, Mapping) or set(cohort) != cohort_fields:
            raise PriorExposureRefusal("historical selection cohort shape drifted")
        for ids_key, root_key in (
            ("item_ids", "item_root_sha256"),
            ("source_entity_ids", "source_entity_root_sha256"),
            ("component_ids", "component_root_sha256"),
        ):
            ids = cohort.get(ids_key)
            if (
                not isinstance(ids, list)
                or ids != sorted(set(ids))
                or any(not isinstance(item, str) or not item for item in ids)
                or canonical_sha256(ids) != cohort.get(root_key)
            ):
                raise PriorExposureRefusal("historical selection cohort root drifted")
        rows = cohort.get("selected_rows")
        if (
            len(cohort["item_ids"]) != expected_items
            or not isinstance(rows, list)
            or len(rows) != expected_items
            or canonical_sha256(rows) != cohort.get("selected_rows_sha256")
            or not _is_sha256(cohort.get("selection_root_sha256"))
            or not isinstance(cohort.get("component_schedule"), list)
        ):
            raise PriorExposureRefusal("historical selection cohort preimage drifted")
    seen_pages: set[tuple[int, int]] = set()
    for page in selection["source_pages"]:
        if (
            not isinstance(page, Mapping)
            or set(page)
            != {
                "offset", "length", "purpose", "redacted_rows",
                "redacted_rows_sha256", "whitelisted_projection_sha256",
            }
            or isinstance(page.get("offset"), bool)
            or not isinstance(page.get("offset"), int)
            or isinstance(page.get("length"), bool)
            or not isinstance(page.get("length"), int)
            or not isinstance(page.get("purpose"), str)
            or not isinstance(page.get("redacted_rows"), list)
            or canonical_sha256(page["redacted_rows"])
            != page.get("redacted_rows_sha256")
            or not _is_sha256(page.get("whitelisted_projection_sha256"))
        ):
            raise PriorExposureRefusal("historical selection page drifted")
        key = (int(page["offset"]), int(page["length"]))
        if key in seen_pages:
            raise PriorExposureRefusal("historical selection page repeats")
        seen_pages.add(key)
    if (
        set(lock) != _INCIDENT_LOCK_FIELDS
        or lock.get("purpose") != "DEVELOPMENT_POWER_PILOT"
        or lock.get("mode") != "development"
        or not isinstance(lock.get("execution_policy"), Mapping)
        or set(lock["execution_policy"])
        != {"endpoint", "max_delivery_attempts", "max_workers", "spool_token_env", "timeout_seconds"}
        or not isinstance(lock.get("gates"), Mapping)
        or set(lock["gates"])
        != {
            "expected_arms", "expected_calls", "expected_item_runs",
            "expected_items", "per_call_input_caps", "per_call_output_caps",
            "token_spread_max", "total_allowed_output_tokens_per_run",
            "total_input_tokens_per_run",
        }
    ):
        raise PriorExposureRefusal("historical execution lock semantics drifted")
    for field in _INCIDENT_LOCK_FIELDS - {
        "schema_version", "purpose", "run_id", "mode", "model", "model_revision",
        "upstream_endpoint", "deployment_id", "served_model", "hswm_commit",
        "preregistration_artifact_sha256",
        "forbidden_prior_item_ids", "forbidden_prior_source_entity_ids",
        "forbidden_prior_component_ids", "execution_policy", "gates",
    }:
        if not _is_sha256(lock.get(field)):
            raise PriorExposureRefusal("historical execution-lock digest drifted")
    if lock.get("preregistration_artifact_sha256") is not None:
        raise PriorExposureRefusal("historical development lock preregistration drifted")
    if (
        not isinstance(lock.get("model_revision"), str)
        or _GIT_COMMIT.fullmatch(str(lock.get("model_revision"))) is None
    ):
        raise PriorExposureRefusal("historical model revision drifted")
    for field in (
        "forbidden_prior_item_ids", "forbidden_prior_source_entity_ids",
        "forbidden_prior_component_ids",
    ):
        items = lock.get(field)
        if not isinstance(items, list) or items != sorted(set(items)):
            raise PriorExposureRefusal("historical forbidden boundary drifted")
    development_entries = _verify_historical_selection(selection, lock)
    if historical_replay is None:
        try:
            rebuilt = _source_module.build_public_artifacts(
                development_entries,
                public_selection_receipt_sha256=str(
                    selection["selection_receipt_sha256"]
                ),
                dataset=str(source_receipt.get("dataset")),
                config=str(source_receipt.get("config")),
                split=str(source_receipt.get("split")),
                run_id=str(manifest.get("run_id")),
                mode="development",
                model=str(manifest.get("model")),
                model_revision=str(manifest.get("model_revision")),
                token_envelope=manifest.get("token_envelope", {}),
                preregistration_artifact_sha256=None,
            )
        except Exception as error:
            raise PriorExposureRefusal(
                "historical public selection cannot rebuild manifest/source"
            ) from error
    else:
        rebuilt = {
            "manifest": historical_replay.get("manifest"),
            "source_receipt": historical_replay.get("source_receipt"),
        }
    if (
        not _exact_json_equal(rebuilt.get("manifest"), manifest)
        or not _exact_json_equal(rebuilt.get("source_receipt"), source_receipt)
    ):
        raise PriorExposureRefusal(
            "historical public selection does not reproduce manifest/source"
        )
    raw_items = manifest.get("items")
    token_envelope = manifest.get("token_envelope")
    token_tolerance = manifest.get("token_tolerance")
    input_caps = (
        token_envelope.get("per_call_input_caps")
        if isinstance(token_envelope, Mapping)
        else None
    )
    output_caps = (
        token_envelope.get("per_call_output_caps")
        if isinstance(token_envelope, Mapping)
        else None
    )
    if (
        not isinstance(raw_items, list)
        or not raw_items
        or any(
            not isinstance(item, Mapping)
            or not isinstance(item.get("item_id"), str)
            or not item.get("item_id")
            or not isinstance(item.get("candidates"), list)
            or not item.get("candidates")
            for item in raw_items
        )
        or not isinstance(input_caps, Mapping)
        or not isinstance(output_caps, Mapping)
        or isinstance(token_tolerance, bool)
        or not isinstance(token_tolerance, int)
        or token_tolerance < 0
    ):
        raise PriorExposureRefusal("historical manifest gate inputs drifted")
    item_ids = sorted(str(item["item_id"]) for item in raw_items)
    if len(item_ids) != len(set(item_ids)):
        raise PriorExposureRefusal("historical manifest item IDs repeat")
    candidate_root = canonical_sha256(
        [
            {
                "item_id": str(item["item_id"]),
                "candidate_universe_sha256": (
                    _source_module.candidate_universe_sha256(item["candidates"])
                ),
            }
            for item in sorted(raw_items, key=lambda item: str(item["item_id"]))
        ]
    )
    expected_gates = {
        "expected_items": len(raw_items),
        "expected_arms": len(_F1_ARMS),
        "expected_item_runs": len(raw_items) * len(_F1_ARMS),
        "expected_calls": len(raw_items) * len(_F1_ARMS) * len(_CALL_CONTRACTS),
        "per_call_input_caps": dict(input_caps),
        "per_call_output_caps": dict(output_caps),
        "total_input_tokens_per_run": sum(int(value) for value in input_caps.values()),
        "total_allowed_output_tokens_per_run": sum(
            int(value) for value in output_caps.values()
        ),
        "token_spread_max": token_tolerance,
    }
    if (
        not _exact_json_equal(lock.get("gates"), expected_gates)
        or lock.get("token_envelope_sha256") != canonical_sha256(token_envelope)
        or lock.get("generation_policy_sha256")
        != canonical_sha256(_source_module.GENERATION_POLICY)
        or lock.get("cohort_root_sha256") != canonical_sha256(item_ids)
        or lock.get("candidate_universe_root_sha256") != candidate_root
    ):
        raise PriorExposureRefusal("historical execution-lock gates drifted")
    execution_policy = lock.get("execution_policy")
    endpoint = execution_policy.get("endpoint")
    max_workers = execution_policy.get("max_workers")
    timeout_seconds = execution_policy.get("timeout_seconds")
    delivery_attempts = execution_policy.get("max_delivery_attempts")
    spool_token_env = execution_policy.get("spool_token_env")
    if (
        not isinstance(endpoint, str)
        or not endpoint.startswith(("http://", "https://"))
        or isinstance(max_workers, bool)
        or not isinstance(max_workers, int)
        or not 1 <= max_workers <= 8
        or isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not float(timeout_seconds) > 0
        or isinstance(delivery_attempts, bool)
        or not isinstance(delivery_attempts, int)
        or delivery_attempts < 1
        or not isinstance(spool_token_env, str)
        or not spool_token_env.strip()
    ):
        raise PriorExposureRefusal("historical execution policy values drifted")
    if any(
        not _is_sha256(item)
        for field in (
            "forbidden_prior_source_entity_ids",
            "forbidden_prior_component_ids",
        )
        for item in lock[field]
    ):
        raise PriorExposureRefusal("historical forbidden digest boundary drifted")
    if (
        set(genesis) != _INCIDENT_GENESIS_FIELDS
        or genesis.get("run_id") != lock.get("run_id")
        or genesis.get("attempt_integrity") != "ok"
        or genesis.get("spool_integrity") != "ok"
        or str(genesis.get("attempt_journal_mode")).casefold() != "wal"
        or str(genesis.get("spool_journal_mode")).casefold() != "wal"
        or str(genesis.get("attempt_audit_connection_synchronous")) != "2"
        or str(genesis.get("spool_audit_connection_synchronous")) != "2"
        or genesis.get("attempt_user_version") != 1
        or genesis.get("spool_user_version") != 1
        or any(
            genesis.get(field) != 0
            for field in ("call_count", "item_run_count", "attempt_event_count", "spool_call_count")
        )
        or not _is_sha256(genesis.get("attempt_schema_sha256"))
        or not _is_sha256(genesis.get("spool_schema_sha256"))
    ):
        raise PriorExposureRefusal("historical genesis semantics drifted")
    attempt_identity = _verify_database_identity_value(
        genesis.get("attempt_db_identity"), "attempt"
    )
    spool_identity = _verify_database_identity_value(
        genesis.get("spool_db_identity"), "spool"
    )
    if (attempt_identity["st_dev"], attempt_identity["st_ino"]) == (
        spool_identity["st_dev"], spool_identity["st_ino"]
    ):
        raise PriorExposureRefusal("historical genesis database identities alias")
    try:
        compatibility_root = _environment_module.verify_preimage_bundle(
            environment, verify_live=False
        )
        validated_deployment = _deployment_module.validate_deployment_receipt(
            deployment, verify_snapshot=False, verify_live_process=False
        )
    except Exception as error:
        raise PriorExposureRefusal("historical environment/deployment verification failed") from error
    environment_receipt = environment.get("environment_receipt")
    dependency_receipt = environment.get("dependency_receipt")
    environment_labels = (
        environment_receipt.get("labels")
        if isinstance(environment_receipt, Mapping)
        else None
    )
    dependency_files = (
        dependency_receipt.get("files")
        if isinstance(dependency_receipt, Mapping)
        else None
    )
    if (
        not isinstance(environment_labels, Mapping)
        or not isinstance(dependency_files, Mapping)
        or set(dependency_files) != _HISTORICAL_DEPENDENCY_NAMES
    ):
        raise PriorExposureRefusal(
            "historical environment labels/dependency inventory drifted"
        )
    if (
        dependency_files["result_contract"].get("sha256")
        != lock.get("result_contract_sha256")
        or dependency_files["judge_core"].get("sha256")
        != lock.get("judge_core_file_sha256")
    ):
        raise PriorExposureRefusal(
            "historical dependency roles differ from the execution lock"
        )
    try:
        expected_environment_labels = _environment_module.r8_environment_labels(
            spool_endpoint=str(lock["execution_policy"]["endpoint"]),
            model_upstream_endpoint=str(lock.get("upstream_endpoint")),
            model_deployment_receipt_sha256=str(
                deployment.get("receipt_sha256")
            ),
            model=str(lock.get("model")),
            model_revision=str(lock.get("model_revision")),
            run_id=str(lock.get("run_id")),
            hswm_commit=str(lock.get("hswm_commit")),
            symposium_commit=str(environment_labels.get("symposium_commit", "")),
        )
        _environment_module.verify_environment_labels(
            environment_receipt,
            expected_environment_labels,
            verify_live=False,
        )
    except Exception as error:
        raise PriorExposureRefusal("historical environment labels drifted") from error
    deployment_snapshot = validated_deployment.get("snapshot")
    deployment_endpoint = validated_deployment.get("endpoint")
    if (
        compatibility_root != lock.get("environment_dependency_compatibility_root_sha256")
        or environment_receipt.get("receipt_sha256")
        != lock.get("environment_receipt_sha256")
        or environment["dependency_receipt"].get("receipt_sha256")
        != lock.get("dependency_receipt_sha256")
        or deployment.get("receipt_sha256")
        != lock.get("deployment_receipt_sha256")
        or deployment.get("deployment_id") != lock.get("deployment_id")
        or deployment.get("served_model") != lock.get("served_model")
        or lock.get("served_model") != lock.get("model")
        or not isinstance(deployment_snapshot, Mapping)
        or deployment_snapshot.get("resolved_revision")
        != lock.get("model_revision")
        or not isinstance(deployment_endpoint, str)
        or f"{deployment_endpoint.rstrip('/')}/chat/completions"
        != lock.get("upstream_endpoint")
    ):
        raise PriorExposureRefusal(
            "historical environment/deployment lock binding drifted"
        )
    if set(preflight) != _INCIDENT_SPOOL_PREFLIGHT_FIELDS:
        raise PriorExposureRefusal("historical spool preflight shape drifted")
    identity = preflight.get("endpoint_identity")
    if not isinstance(identity, Mapping) or set(identity) != _INCIDENT_SPOOL_IDENTITY_FIELDS:
        raise PriorExposureRefusal("historical spool identity shape drifted")
    if identity.get("schema_version") != "hswm-f1-result-spool-identity/v2":
        raise PriorExposureRefusal("historical spool identity schema drifted")
    _verify_self_hash_mapping(identity, "identity_sha256", "spool identity")
    preflight_database_identity = _verify_database_identity_value(
        identity.get("db_identity"), "spool preflight"
    )
    audit = identity.get("audit")
    if (
        not isinstance(audit, Mapping)
        or set(audit) != _INCIDENT_SPOOL_AUDIT_FIELDS
        or audit.get("schema_version") != "hswm-f1-result-spool/v1"
        or str(audit.get("journal_mode")).casefold() != "wal"
        or audit.get("synchronous") != 2
        or audit.get("call_count") != 0
        or audit.get("status_counts") != {}
        or audit.get("completed_root_sha256") != canonical_sha256([])
    ):
        raise PriorExposureRefusal("historical spool audit drifted")
    _verify_self_hash_mapping(audit, "audit_sha256", "spool audit")
    if (
        preflight.get("run_id") != lock.get("run_id")
        or preflight.get("execution_lock_sha256") != lock.get("lock_sha256")
        or preflight.get("db_genesis_sha256") != genesis.get("genesis_sha256")
        or preflight.get("endpoint") != lock["execution_policy"].get("endpoint")
        or preflight_database_identity != spool_identity
    ):
        raise PriorExposureRefusal("historical spool preflight binding drifted")
    for key in (
        "upstream_endpoint", "deployment_receipt_sha256", "deployment_id",
        "served_model", "model_revision",
    ):
        identity_key = "normalized_upstream_endpoint" if key == "upstream_endpoint" else key
        if preflight.get(key) != lock.get(key) or identity.get(identity_key) != lock.get(key):
            raise PriorExposureRefusal("historical spool deployment binding drifted")


def _git_binding(root: Path, label: str) -> dict[str, str]:
    resolved = Path(root).resolve(strict=True)
    try:
        repository_root = Path(
            str(_git_output(resolved, "rev-parse", "--show-toplevel")).strip()
        ).resolve(strict=True)
        commit = str(_git_output(resolved, "rev-parse", "HEAD")).strip()
        tree = str(_git_output(resolved, "rev-parse", "HEAD^{tree}")).strip()
        status = str(
            _git_output(
                resolved,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
            )
        )
    except (OSError, PriorExposureRefusal) as error:
        raise PriorExposureRefusal(f"{label} Git binding cannot be read") from error
    if repository_root != resolved:
        raise PriorExposureRefusal(f"{label} Git root drifted")
    if _GIT_COMMIT.fullmatch(commit) is None or _GIT_COMMIT.fullmatch(tree) is None:
        raise PriorExposureRefusal(f"{label} Git identity drifted")
    if status:
        raise PriorExposureRefusal(f"{label} Git worktree is not clean")
    return {"commit": commit, "tree": tree}


def _current_producer_root(candidate: Path | None) -> Path:
    executing_root = Path(__file__).resolve(strict=True).parents[1]
    if candidate is None:
        return executing_root
    try:
        supplied_root = Path(candidate).resolve(strict=True)
    except OSError as error:
        raise PriorExposureRefusal("current producer root cannot be resolved") from error
    if supplied_root != executing_root:
        raise PriorExposureRefusal(
            "current producer root differs from the executing module root"
        )
    return supplied_root


def _isolated_git_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return environment


def _git_output(root: Path, *arguments: str, text: bool = True) -> str | bytes:
    completed = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(root), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        env=_isolated_git_environment(),
    )
    if completed.returncode != 0:
        raise PriorExposureRefusal("current producer Git authority cannot be read")
    return completed.stdout


def _module_for_python_path(relative_path: str) -> str:
    if relative_path.endswith("/__init__.py"):
        return relative_path[: -len("/__init__.py")].replace("/", ".")
    return relative_path[:-3].replace("/", ".")


class _ImportTimeVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.imports: list[tuple[str | None, int, tuple[str, ...]]] = []
        self.dynamic_import = False

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append((alias.name, 0, ()))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append(
            (node.module, node.level, tuple(alias.name for alias in node.names))
        )

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        if (
            isinstance(function, ast.Name)
            and function.id == "__import__"
        ) or (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "importlib"
            and function.attr == "import_module"
        ):
            self.dynamic_import = True
        self.generic_visit(node)

    def _visit_definition_expressions(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        if node.returns is not None:
            self.visit(node.returns)
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ):
            if argument.annotation is not None:
                self.visit(argument.annotation)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_definition_expressions(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_definition_expressions(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)


def _resolve_import_module(
    importing_module: str, module: str | None, level: int
) -> str:
    if level == 0:
        return module or ""
    package = importing_module.rsplit(".", 1)[0]
    parts = package.split(".") if package else []
    if level > len(parts) + 1:
        raise PriorExposureRefusal("current producer relative import escapes package")
    prefix = parts[: len(parts) - level + 1]
    if module:
        prefix.extend(module.split("."))
    return ".".join(prefix)


def _discover_current_producer_import_lfp(root: Path) -> tuple[str, ...]:
    raw = _git_output(
        root,
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
        "--",
        "*.py",
        text=False,
    )
    assert isinstance(raw, bytes)
    paths = [item.decode("utf-8") for item in raw.split(b"\0") if item]
    module_to_path: dict[str, str] = {}
    for relative in paths:
        module = _module_for_python_path(relative)
        if module in module_to_path:
            raise PriorExposureRefusal("current producer module mapping repeats")
        module_to_path[module] = relative

    entrypoint = "prom_search_hswm.prom9_f1_prior_exposure"
    pending = [entrypoint]
    discovered: set[str] = set()
    while pending:
        module = pending.pop()
        if module in discovered:
            continue
        relative = module_to_path.get(module)
        if relative is None:
            raise PriorExposureRefusal("current producer entrypoint is absent")
        try:
            tree = ast.parse(
                _read_stable_public_bytes(root / relative), filename=relative
            )
        except (SyntaxError, ValueError) as error:
            raise PriorExposureRefusal(
                "current producer Python source cannot be parsed"
            ) from error
        visitor = _ImportTimeVisitor()
        visitor.visit(tree)
        if visitor.dynamic_import:
            raise PriorExposureRefusal(
                "current producer has an unmodeled import-time dynamic import"
            )
        discovered.add(module)
        for imported, level, names in visitor.imports:
            base = _resolve_import_module(module, imported, level)
            candidates = [base] if base else []
            candidates.extend(
                f"{base}.{name}" if base else name
                for name in names
                if name != "*"
            )
            for candidate in candidates:
                if candidate in module_to_path and candidate not in discovered:
                    pending.append(candidate)
    return tuple(sorted(module_to_path[module] for module in discovered))


def _producer_dependency_paths(root: Path | None = None) -> dict[str, Path]:
    producer_root = (
        Path(root).resolve(strict=True)
        if root is not None
        else Path(__file__).resolve(strict=True).parents[1]
    )
    discovered = _discover_current_producer_import_lfp(producer_root)
    if discovered != _CURRENT_PRODUCER_IMPORT_LFP:
        raise PriorExposureRefusal("current producer import closure drifted")
    return {
        relative: producer_root / relative
        for relative in _CURRENT_PRODUCER_IMPORT_LFP
    }


def _current_producer_authority(root: Path) -> dict[str, object]:
    producer_root = Path(root).resolve(strict=True)
    git_binding = _git_binding(producer_root, "current producer")
    commit = git_binding["commit"]
    files: list[dict[str, object]] = []
    for relative, path in _producer_dependency_paths(producer_root).items():
        raw = _read_stable_public_bytes(path)
        if not raw:
            raise PriorExposureRefusal("current producer file is empty")
        blob = _git_output(
            producer_root, "show", f"{commit}:{relative}", text=False
        )
        assert isinstance(blob, bytes)
        if raw != blob:
            raise PriorExposureRefusal("current producer differs from committed blob")
        tree_row = str(
            _git_output(
                producer_root, "ls-tree", commit, "--", relative, text=True
            )
        ).strip()
        parts = tree_row.split(None, 3)
        if len(parts) != 4 or parts[1] != "blob" or parts[3] != relative:
            raise PriorExposureRefusal("current producer Git blob identity drifted")
        mode, _kind, oid, _path = parts
        if mode not in {"100644", "100755"} or _GIT_COMMIT.fullmatch(oid) is None:
            raise PriorExposureRefusal("current producer Git blob mode drifted")
        files.append(
            {
                "relative_path": relative,
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "blob_mode": mode,
                "blob_oid": oid,
            }
        )
    return {
        "commit": commit,
        "tree": git_binding["tree"],
        "entrypoint": "prom_search_hswm/prom9_f1_prior_exposure.py",
        "closure_policy": "MODULE_SCOPE_LOCAL_AST_LFP_V1",
        "files": files,
        "file_count": len(files),
        "closure_root_sha256": canonical_sha256(files),
    }


_HISTORICAL_REPLAY_CHILD = r'''
import json
import os
import socket
import subprocess
import sys
import urllib.request

def denied(*_args, **_kwargs):
    raise RuntimeError("historical replay external effect denied")

socket.socket = denied
socket.create_connection = denied
subprocess.Popen = denied
subprocess.run = denied
subprocess.call = denied
subprocess.check_call = denied
subprocess.check_output = denied

tree = sys.argv[1]
sys.path.insert(0, tree)
from prom_search_hswm.hswm_function_registry import build_registry
from prom_search_hswm.prom9_f1_r8_source import build_public_artifacts
from prom_search_hswm.prom_f1_function_network import _arm_overrides
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256

payload = json.load(sys.stdin)
protocol_path = os.path.join(tree, "protocol.replay.json")
descriptor = os.open(
    protocol_path,
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
    0o600,
)
raw_protocol = (canonical_json(payload["protocol"]) + "\n").encode("utf-8")
try:
    offset = 0
    while offset < len(raw_protocol):
        written = os.write(descriptor, raw_protocol[offset:])
        if written <= 0:
            raise RuntimeError("historical replay write made no progress")
        offset += written
    os.fsync(descriptor)
finally:
    os.close(descriptor)

rebuilt = build_public_artifacts(
    payload["development_entries"],
    public_selection_receipt_sha256=payload["selection_receipt_sha256"],
    dataset=payload["dataset"],
    config=payload["config"],
    split=payload["split"],
    run_id=payload["run_id"],
    mode="development",
    model=payload["model"],
    model_revision=payload["model_revision"],
    token_envelope=payload["token_envelope"],
    preregistration_artifact_sha256=None,
)
arms = payload["arms"]
registries = {
    arm: build_registry(
        protocol_path,
        model=payload["model"],
        model_revision=payload["model_revision"],
        prompt_overrides=_arm_overrides(arm),
    )
    for arm in arms
}
result = {
    "manifest": rebuilt["manifest"],
    "source_receipt": rebuilt["source_receipt"],
    "protocol_roots": sorted({registry.protocol_sha256 for registry in registries.values()}),
    "registries_root_sha256": canonical_sha256(
        {arm: registries[arm].registry_sha256 for arm in arms}
    ),
    "prompts": [
        {
            "arm_id": arm,
            "function_id": function.function_id,
            "prompt": function.prompt,
        }
        for arm in arms
        for function in registries[arm].functions
    ],
    "python": {
        "implementation": sys.implementation.name,
        "version": ".".join(str(value) for value in sys.version_info[:3]),
    },
}
sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
'''


def _git_commit_binding(
    root: Path, expected_commit: str, label: str
) -> dict[str, str]:
    repository = Path(root).resolve(strict=True)
    if _GIT_COMMIT.fullmatch(expected_commit) is None:
        raise PriorExposureRefusal(f"{label} historical commit drifted")
    object_type = str(
        _git_output(repository, "cat-file", "-t", expected_commit, text=True)
    ).strip()
    tree = str(
        _git_output(
            repository, "rev-parse", f"{expected_commit}^{{tree}}", text=True
        )
    ).strip()
    if object_type != "commit" or _GIT_COMMIT.fullmatch(tree) is None:
        raise PriorExposureRefusal(f"{label} historical Git object drifted")
    return {"commit": expected_commit, "tree": tree}


def _materialize_historical_replay_tree(
    repository: Path, destination: Path
) -> list[dict[str, object]]:
    commit = _HISTORICAL_RUNTIME_COMMITS["hswm_executable"]
    files: list[dict[str, object]] = []
    for relative in _HISTORICAL_REPLAY_IMPORT_LFP:
        raw = _git_output(repository, "show", f"{commit}:{relative}", text=False)
        assert isinstance(raw, bytes)
        if not raw:
            raise PriorExposureRefusal("historical replay blob is empty")
        tree_row = str(
            _git_output(repository, "ls-tree", commit, "--", relative, text=True)
        ).strip()
        parts = tree_row.split(None, 3)
        if len(parts) != 4 or parts[1] != "blob" or parts[3] != relative:
            raise PriorExposureRefusal("historical replay blob identity drifted")
        mode, _kind, oid, _path = parts
        if mode not in {"100644", "100755"} or _GIT_COMMIT.fullmatch(oid) is None:
            raise PriorExposureRefusal("historical replay blob mode drifted")
        target = destination / relative
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.parent.chmod(0o700)
        descriptor = os.open(
            target,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            offset = 0
            while offset < len(raw):
                written = os.write(descriptor, raw[offset:])
                if written <= 0:
                    raise PriorExposureRefusal(
                        "historical replay materialization made no progress"
                    )
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        files.append(
            {
                "relative_path": relative,
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "blob_mode": mode,
                "blob_oid": oid,
            }
        )
    return files


def _historical_runtime_replay(
    *,
    hswm_root: Path,
    carrier_root: Path,
    symposium_root: Path,
    historical_python: Path,
    selection: Mapping[str, object],
    manifest: Mapping[str, object],
    source_receipt: Mapping[str, object],
    lock: Mapping[str, object],
    environment: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    repositories = {
        "hswm_executable": _git_commit_binding(
            hswm_root,
            _HISTORICAL_RUNTIME_COMMITS["hswm_executable"],
            "HSWM executable",
        ),
        "hswm_carrier": _git_commit_binding(
            carrier_root,
            _HISTORICAL_RUNTIME_COMMITS["hswm_carrier"],
            "HSWM carrier",
        ),
        "symposium": _git_commit_binding(
            symposium_root,
            _HISTORICAL_RUNTIME_COMMITS["symposium"],
            "SYMPOSIUM",
        ),
    }
    if lock.get("hswm_commit") != repositories["hswm_executable"]["commit"]:
        raise PriorExposureRefusal("historical HSWM lock commit drifted")
    environment_receipt = environment.get("environment_receipt")
    runtime = (
        environment_receipt.get("runtime")
        if isinstance(environment_receipt, Mapping)
        else None
    )
    python_runtime = runtime.get("python") if isinstance(runtime, Mapping) else None
    executable_receipt = (
        python_runtime.get("executable")
        if isinstance(python_runtime, Mapping)
        else None
    )
    interpreter = Path(historical_python).resolve(strict=True)
    interpreter_raw = _read_stable_public_bytes(interpreter)
    if (
        not isinstance(executable_receipt, Mapping)
        or executable_receipt.get("size_bytes") != len(interpreter_raw)
        or executable_receipt.get("sha256")
        != hashlib.sha256(interpreter_raw).hexdigest()
    ):
        raise PriorExposureRefusal("historical Python interpreter drifted")
    development_entries = _verify_historical_selection(selection, lock)
    dependency = environment.get("dependency_receipt")
    dependency_files = (
        dependency.get("files") if isinstance(dependency, Mapping) else None
    )
    if not isinstance(dependency_files, Mapping):
        raise PriorExposureRefusal("historical dependency files are absent")
    protocol = _strict_object(
        _inline_dependency_bytes(dependency_files, "protocol_json"),
        "historical protocol preimage",
    )
    payload = {
        "development_entries": development_entries,
        "selection_receipt_sha256": selection.get("selection_receipt_sha256"),
        "dataset": source_receipt.get("dataset"),
        "config": source_receipt.get("config"),
        "split": source_receipt.get("split"),
        "run_id": manifest.get("run_id"),
        "model": manifest.get("model"),
        "model_revision": manifest.get("model_revision"),
        "token_envelope": manifest.get("token_envelope"),
        "arms": list(_F1_ARMS),
        "protocol": protocol,
    }
    temporary = tempfile.TemporaryDirectory(prefix="hswm-f1-historical-replay-")
    try:
        tree = Path(temporary.name)
        tree.chmod(0o700)
        replay_files = _materialize_historical_replay_tree(
            Path(hswm_root).resolve(strict=True), tree
        )
        completed = subprocess.run(
            [str(interpreter), "-I", "-S", "-c", _HISTORICAL_REPLAY_CHILD, str(tree)],
            input=canonical_json(payload).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=60,
            cwd=tree,
            env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
            close_fds=True,
        )
        if completed.returncode != 0 or not completed.stdout:
            raise PriorExposureRefusal("historical isolated replay failed")
        try:
            result = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise PriorExposureRefusal(
                "historical isolated replay output drifted"
            ) from error
    except (OSError, subprocess.SubprocessError) as error:
        raise PriorExposureRefusal("historical isolated replay failed") from error
    finally:
        temporary.cleanup()
    if not isinstance(result, Mapping):
        raise PriorExposureRefusal("historical isolated replay result drifted")
    result_python = result.get("python")
    if (
        not isinstance(python_runtime, Mapping)
        or not isinstance(result_python, Mapping)
        or str(result_python.get("implementation", "")).casefold()
        != str(python_runtime.get("implementation", "")).casefold()
        or result_python.get("version") != python_runtime.get("version")
    ):
        raise PriorExposureRefusal("historical Python runtime replay drifted")
    protocol_roots = result.get("protocol_roots")
    if (
        protocol_roots != [lock.get("protocol_sha256")]
        or result.get("registries_root_sha256")
        != lock.get("registries_root_sha256")
    ):
        raise PriorExposureRefusal("historical registry replay differs from lock")
    authority = {
        "repositories": repositories,
        "replay_policy": "COMMIT_BLOBS_PYTHON_ISOLATED_NO_NETWORK_V1",
        "replay_files": replay_files,
        "replay_file_count": len(replay_files),
        "replay_closure_root_sha256": canonical_sha256(replay_files),
        "python_runtime": {
            "implementation": python_runtime.get("implementation"),
            "version": python_runtime.get("version"),
            "executable_size_bytes": len(interpreter_raw),
            "executable_sha256": hashlib.sha256(interpreter_raw).hexdigest(),
        },
        "replay_result_sha256": canonical_sha256(result),
    }
    return dict(result), authority


def _public_database_snapshot(
    value: Mapping[str, object], *, kind: str
) -> dict[str, object]:
    public = dict(value)
    source_identity = public.pop("source_identity", None)
    _verify_database_identity_value(source_identity, f"{kind} source")
    return public


def _private_database_witness(path: Path, label: str) -> dict[str, object]:
    database_path = Path(path)
    try:
        info = database_path.lstat()
        resolved_path = database_path.resolve(strict=True)
        generation = database_generation(database_path, label)
    except (OSError, SQLiteAuthorityRefusal) as error:
        raise PriorExposureRefusal(
            f"{label} private witness cannot be captured"
        ) from error
    if (
        stat.S_ISLNK(info.st_mode)
        or not stat.S_ISREG(info.st_mode)
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_uid != os.geteuid()
        or info.st_nlink != 1
        or not resolved_path.is_absolute()
    ):
        raise PriorExposureRefusal(f"{label} private witness identity drifted")
    main = generation.get("main")
    if (
        not isinstance(main, Mapping)
        or (main.get("st_dev"), main.get("st_ino"))
        != (info.st_dev, info.st_ino)
    ):
        raise PriorExposureRefusal(f"{label} private generation drifted")
    return {
        "resolved_path": str(resolved_path),
        "st_dev": int(info.st_dev),
        "st_ino": int(info.st_ino),
        "mode": oct(stat.S_IMODE(info.st_mode)),
        "uid": int(info.st_uid),
        "nlink": int(info.st_nlink),
        "size_bytes": int(info.st_size),
        "mtime_ns": int(info.st_mtime_ns),
        "ctime_ns": int(info.st_ctime_ns),
        "generation": generation,
    }


def _inline_dependency_bytes(
    files: Mapping[str, object], name: str
) -> bytes:
    value = files.get(name)
    if not isinstance(value, Mapping):
        raise PriorExposureRefusal(f"incident dependency is absent: {name}")
    preimage = value.get("preimage")
    encoded = preimage.get("bytes_b64") if isinstance(preimage, Mapping) else None
    if (
        not isinstance(preimage, Mapping)
        or preimage.get("kind") != "inline-base64"
        or preimage.get("encoding") != "base64"
        or not isinstance(encoded, str)
    ):
        raise PriorExposureRefusal(
            f"incident dependency is not an inline preimage: {name}"
        )
    try:
        raw = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise PriorExposureRefusal(
            f"incident dependency encoding drifted: {name}"
        ) from error
    if (
        isinstance(value.get("size_bytes"), bool)
        or value.get("size_bytes") != len(raw)
        or value.get("sha256") != hashlib.sha256(raw).hexdigest()
    ):
        raise PriorExposureRefusal(
            f"incident dependency bytes drifted: {name}"
        )
    return raw


def _registry_prompt_authority(
    environment: Mapping[str, object],
    manifest: Mapping[str, object],
    lock: Mapping[str, object],
) -> dict[tuple[str, str], str]:
    dependency = environment.get("dependency_receipt")
    files = dependency.get("files") if isinstance(dependency, Mapping) else None
    if not isinstance(files, Mapping):
        raise PriorExposureRefusal("incident dependency files are absent")
    current_modules = {
        "function_registry": Path(str(_registry_module.__file__)),
        "function_network": Path(str(_function_network_module.__file__)),
        "function_network_adapter": Path(str(_network_adapter_module.__file__)),
        "protocol_loader": Path(str(_protocol_module.__file__)),
    }
    for name, path in current_modules.items():
        expected = files.get(name)
        raw = _read_stable_public_bytes(path)
        if (
            not isinstance(expected, Mapping)
            or expected.get("sha256") != hashlib.sha256(raw).hexdigest()
        ):
            raise PriorExposureRefusal(
                f"registry authority implementation drifted: {name}"
            )
    protocol = _strict_object(
        _inline_dependency_bytes(files, "protocol_json"),
        "incident protocol preimage",
    )
    temporary = tempfile.TemporaryDirectory(prefix="hswm-f1-registry-replay-")
    protocol_path = Path(temporary.name) / "protocol.json"
    descriptor = -1
    try:
        descriptor = os.open(
            protocol_path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        payload = (canonical_json(protocol) + "\n").encode("utf-8")
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise PriorExposureRefusal(
                    "incident protocol replay write made no progress"
                )
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        registries = {
            arm: build_registry(
                protocol_path,
                model=str(manifest["model"]),
                model_revision=str(manifest["model_revision"]),
                prompt_overrides=_arm_overrides(arm),
            )
            for arm in _F1_ARMS
        }
    except Exception as error:
        raise PriorExposureRefusal(
            "incident registry authority cannot be rebuilt"
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.cleanup()
    protocol_roots = {registry.protocol_sha256 for registry in registries.values()}
    registry_root = canonical_sha256(
        {arm: registries[arm].registry_sha256 for arm in _F1_ARMS}
    )
    if (
        len(protocol_roots) != 1
        or next(iter(protocol_roots)) != lock.get("protocol_sha256")
        or registry_root != lock.get("registries_root_sha256")
    ):
        raise PriorExposureRefusal("incident registry root differs from lock")
    return {
        (arm, function.function_id): function.prompt
        for arm, registry in registries.items()
        for function in registry.functions
    }


def _source_receipt_metadata(
    source_receipt: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    try:
        verify_public_source_receipt(source_receipt)
    except Exception as error:
        raise PriorExposureRefusal("public source receipt verification failed") from error
    rows = source_receipt.get("rows")
    if not isinstance(rows, list) or not rows:
        raise PriorExposureRefusal("public source rows are absent")
    projected: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise PriorExposureRefusal("public source row is malformed")
        item_id = row.get("item_id")
        row_index = row.get("dataset_row_index")
        question_sha = row.get("question_sha256")
        entities = row.get("source_entity_ids")
        if (
            not isinstance(item_id, str)
            or not item_id
            or isinstance(row_index, bool)
            or not isinstance(row_index, int)
            or not isinstance(question_sha, str)
            or _SHA256.fullmatch(question_sha) is None
            or not isinstance(entities, list)
            or entities != sorted(set(entities))
            or any(not isinstance(value, str) or _SHA256.fullmatch(value) is None for value in entities)
        ):
            raise PriorExposureRefusal("public source identity row drifted")
        projected.append(
            {
                "item_id": item_id,
                "dataset_row_index": row_index,
                "question_sha256": question_sha,
                "source_entity_ids": list(entities),
                "component_id": None,
            }
        )
    if len({str(row["item_id"]) for row in projected}) != len(projected):
        raise PriorExposureRefusal("public source item IDs repeat")
    _assign_components(projected)
    return {str(row["item_id"]): row for row in projected}


def _source_metadata(
    manifest: Mapping[str, object], source_receipt: Mapping[str, object]
) -> dict[str, dict[str, object]]:
    metadata = _source_receipt_metadata(source_receipt)
    manifest_items = manifest.get("items")
    if not isinstance(manifest_items, list) or not manifest_items:
        raise PriorExposureRefusal("manifest items are absent")
    manifest_by_item: dict[str, Mapping[str, object]] = {}
    for raw in manifest_items:
        if not isinstance(raw, Mapping) or not isinstance(raw.get("item_id"), str):
            raise PriorExposureRefusal("manifest item identity drifted")
        item_id = str(raw["item_id"])
        if item_id in manifest_by_item:
            raise PriorExposureRefusal("manifest item IDs repeat")
        manifest_by_item[item_id] = raw
    if set(manifest_by_item) != set(metadata):
        raise PriorExposureRefusal("manifest and public source item sets differ")
    for item_id, raw in manifest_by_item.items():
        candidates = raw.get("candidates")
        if not isinstance(candidates, list):
            raise PriorExposureRefusal("manifest candidates are absent")
        candidate_entities = sorted(
            {
                str(candidate.get("source_entity_id"))
                for candidate in candidates
                if isinstance(candidate, Mapping)
                and isinstance(candidate.get("source_entity_id"), str)
            }
        )
        if (
            candidate_entities != metadata[item_id]["source_entity_ids"]
            or raw.get("component_id") != metadata[item_id]["component_id"]
        ):
            raise PriorExposureRefusal("manifest/source component binding drifted")
    return metadata


def _manifest_item_for_call(
    manifest: Mapping[str, object], item_id: str
) -> Mapping[str, object]:
    items = manifest.get("items")
    matches = [
        item
        for item in items
        if isinstance(item, Mapping) and item.get("item_id") == item_id
    ] if isinstance(items, list) else []
    if len(matches) != 1:
        raise PriorExposureRefusal("attempt item manifest binding drifted")
    return matches[0]


def _candidate_table_for_manifest_item(
    item: Mapping[str, object], arm_id: str
) -> dict[str, object]:
    candidates = item.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise PriorExposureRefusal("attempt item candidate universe drifted")
    canonical_candidates: list[EvidenceCandidateV1] = []
    for candidate in candidates:
        if not isinstance(candidate, Mapping) or set(candidate) != {
            "bond_id",
            "evidence_id",
            "source_entity_id",
            "content",
            "observable",
        }:
            raise PriorExposureRefusal("attempt manifest candidate drifted")
        bond_id = candidate.get("bond_id")
        evidence_id = candidate.get("evidence_id")
        source_entity = candidate.get("source_entity_id")
        content = candidate.get("content")
        observable = candidate.get("observable")
        if (
            not isinstance(bond_id, str)
            or not bond_id
            or not isinstance(evidence_id, str)
            or not evidence_id
            or not isinstance(source_entity, str)
            or _SHA256.fullmatch(source_entity) is None
            or not isinstance(content, str)
            or not content
            or not isinstance(observable, Mapping)
        ):
            raise PriorExposureRefusal("attempt manifest candidate drifted")
        try:
            canonical_candidates.append(
                EvidenceCandidateV1(
                    bond_id=bond_id,
                    evidence_id=evidence_id,
                    source_entity_id=source_entity,
                    content=content,
                    observable=dict(observable),
                )
            )
        except FunctionNetworkError as error:
            raise PriorExposureRefusal(
                "attempt manifest candidate drifted"
            ) from error
    try:
        return candidate_table_for_arm(arm_id, canonical_candidates)
    except FunctionNetworkError as error:
        raise PriorExposureRefusal(
            "attempt candidate table cannot be serialized"
        ) from error


def _verify_call_input_manifest_binding(
    call: Mapping[str, object], manifest: Mapping[str, object]
) -> None:
    item_id = str(call["item_id"])
    arm_id = str(call["arm_id"])
    payload = call["input_payload"]
    assert isinstance(payload, Mapping)
    item = _manifest_item_for_call(manifest, item_id)
    candidates = item.get("candidates")
    assert isinstance(candidates, list)
    expected_request_id = "req-" + canonical_sha256(
        {
            "run_id": call["run_id"],
            "arm_id": arm_id,
            "item_id": item_id,
        }
    )[:8]
    if payload.get("request_id") != expected_request_id:
        raise PriorExposureRefusal("attempt request ID differs from call identity")
    envelope = manifest.get("token_envelope")
    filler = envelope.get("filler") if isinstance(envelope, Mapping) else None
    filler_value = payload.get("parity_filler")
    filler_unit = filler.get("unit") if isinstance(filler, Mapping) else None
    max_filler = (
        filler.get("max_filler_chars") if isinstance(filler, Mapping) else None
    )
    if (
        not isinstance(filler_value, str)
        or not isinstance(filler_unit, str)
        or not filler_unit
        or isinstance(max_filler, bool)
        or not isinstance(max_filler, int)
        or max_filler < 0
        or len(filler_value) > max_filler
        or len(filler_value) % len(filler_unit) != 0
        or filler_value != filler_unit * (len(filler_value) // len(filler_unit))
    ):
        raise PriorExposureRefusal("attempt parity filler differs from envelope")
    call_index = int(call["call_index"])
    if call_index == 1:
        expected_budget = {
            "max_candidates": len(candidates),
            "max_evidence_items": item.get("max_evidence_items"),
            "max_input_tokens": item.get("max_input_tokens"),
            "max_output_tokens": item.get("max_output_tokens_per_call"),
        }
        if (
            payload.get("query_text") != item.get("query_text")
            or payload.get("allowed_evidence_types")
            != item.get("allowed_evidence_types")
            or not _exact_json_equal(payload.get("budget"), expected_budget)
        ):
            raise PriorExposureRefusal("attempt query input differs from manifest")
    elif call_index == 2:
        if (
            not isinstance(payload.get("query_plan"), Mapping)
            or payload["query_plan"].get("request_id") != expected_request_id
            or payload.get("candidate_budget") != item.get("max_evidence_items")
            or not _exact_json_equal(
                payload.get("candidate_table"),
                _candidate_table_for_manifest_item(item, arm_id),
            )
        ):
            raise PriorExposureRefusal(
                "attempt candidate input differs from manifest"
            )
    else:
        candidate_pairs = {
            (candidate.get("evidence_id"), candidate.get("content"))
            for candidate in candidates
            if isinstance(candidate, Mapping)
        }
        selected = payload.get("selected_evidence")
        if (
            payload.get("query_text") != item.get("query_text")
            or not isinstance(payload.get("query_plan"), Mapping)
            or payload["query_plan"].get("request_id") != expected_request_id
            or payload.get("max_answer_tokens")
            != item.get("max_output_tokens_per_call")
            or not isinstance(selected, list)
            or any(
                not isinstance(evidence, Mapping)
                or (evidence.get("evidence_id"), evidence.get("content"))
                not in candidate_pairs
                for evidence in selected
            )
        ):
            raise PriorExposureRefusal("attempt answer input differs from manifest")


def _replay_call_intent_request(
    row: sqlite3.Row,
    *,
    spool_rows: Mapping[str, sqlite3.Row],
    metadata: Mapping[str, Mapping[str, object]],
    manifest: Mapping[str, object],
    spool_endpoint: str,
    expected_prompts: Mapping[tuple[str, str], str],
) -> dict[str, object]:
    physical_call_id = str(row["physical_call_id"])
    intent_raw = bytes(row["intent_bytes"])
    request_raw = bytes(row["request_bytes"])
    if (
        _SHA256.fullmatch(physical_call_id) is None
        or hashlib.sha256(intent_raw).hexdigest() != row["intent_sha256"]
        or hashlib.sha256(request_raw).hexdigest() != row["request_sha256"]
    ):
        raise PriorExposureRefusal("attempt call byte hashes drifted")
    intent = _strict_canonical_blob(intent_raw, "attempt intent")
    request = _strict_canonical_blob(request_raw, "attempt request")
    if set(intent) != {
        "schema_version", "spool_route", "call", "request_sha256",
        "output_schema_sha256",
    } or intent.get("schema_version") != _DURABLE_CALL_SCHEMA:
        raise PriorExposureRefusal("attempt intent shape drifted")
    call = intent.get("call")
    if not isinstance(call, Mapping) or set(call) != _CALL_KEYS:
        raise PriorExposureRefusal("attempt ModelCallV1 shape drifted")
    strings = (
        "physical_call_id", "run_id", "arm_id", "item_id", "function_id",
        "model", "model_revision", "system_prompt", "input_type", "output_type",
    )
    if any(not isinstance(call.get(key), str) or not call.get(key) for key in strings):
        raise PriorExposureRefusal("attempt ModelCallV1 string identity drifted")
    if (
        isinstance(call.get("call_index"), bool)
        or call.get("call_index") not in {1, 2, 3}
        or isinstance(call.get("max_output_tokens"), bool)
        or not isinstance(call.get("max_output_tokens"), int)
        or int(call["max_output_tokens"]) < 1
        or not isinstance(call.get("input_payload"), Mapping)
    ):
        raise PriorExposureRefusal("attempt ModelCallV1 numeric/payload identity drifted")
    call_index = int(call["call_index"])
    contract = _CALL_CONTRACTS[call_index]
    token_envelope = manifest.get("token_envelope")
    output_caps = (
        token_envelope.get("per_call_output_caps")
        if isinstance(token_envelope, Mapping)
        else None
    )
    if (
        (call.get("function_id"), call.get("input_type"), call.get("output_type"))
        != contract
        or not isinstance(output_caps, Mapping)
        or isinstance(output_caps.get(str(call_index)), bool)
        or not isinstance(output_caps.get(str(call_index)), int)
        or call.get("max_output_tokens") != output_caps.get(str(call_index))
    ):
        raise PriorExposureRefusal("attempt call contract differs from manifest")
    try:
        normalized_input = validate_port(
            str(call["input_type"]), call["input_payload"]
        )
    except Exception as error:
        raise PriorExposureRefusal("attempt input port validation failed") from error
    if not _exact_json_equal(call["input_payload"], normalized_input):
        raise PriorExposureRefusal("attempt input payload is not canonical")
    _verify_call_input_manifest_binding(call, manifest)
    expected_physical = canonical_sha256(
        {
            "run_id": call["run_id"],
            "arm_id": call["arm_id"],
            "item_id": call["item_id"],
            "call_index": call["call_index"],
            "function_id": call["function_id"],
            "registry_prompt_sha256": canonical_sha256(
                {"prompt": call["system_prompt"]}
            ),
            "input_port_sha256": port_digest(
                str(call["input_type"]), normalized_input
            ),
        }
    )
    expected_request = {
        "model": call["model"],
        "messages": [
            {"role": "system", "content": call["system_prompt"]},
            {"role": "user", "content": canonical_json(call["input_payload"])},
        ],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": call["max_output_tokens"],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": call["output_type"],
                "strict": True,
                "schema": output_json_schema(str(call["output_type"])),
            },
        },
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if (
        call["physical_call_id"] != physical_call_id
        or expected_physical != physical_call_id
        or intent.get("spool_route") != row["endpoint"]
        or row["endpoint"]
        != f"{spool_endpoint.rstrip('/')}{_SPOOL_ROUTE_PREFIX}{physical_call_id}"
        or intent.get("request_sha256") != row["request_sha256"]
        or intent.get("output_schema_sha256")
        != output_schema_sha256(str(call["output_type"]))
        or request != expected_request
        or canonical_json(expected_request).encode("utf-8") != request_raw
    ):
        raise PriorExposureRefusal("attempt intent/request replay drifted")
    item_id = str(call["item_id"])
    item_metadata = metadata.get(item_id)
    if item_metadata is None:
        raise PriorExposureRefusal("attempt item is absent from public source")
    query_text = call["input_payload"].get("query_text")
    if query_text is not None and (
        not isinstance(query_text, str)
        or canonical_sha256({"question": query_text})
        != item_metadata["question_sha256"]
    ):
        raise PriorExposureRefusal("attempt query differs from public source identity")
    if (
        call["run_id"] != manifest.get("run_id")
        or call["arm_id"] not in _F1_ARMS
        or call["model"] != manifest.get("model")
        or call["model_revision"] != manifest.get("model_revision")
        or call["system_prompt"]
        != expected_prompts.get((str(call["arm_id"]), str(call["function_id"])))
    ):
        raise PriorExposureRefusal("attempt call differs from manifest identity")
    spool = spool_rows.get(physical_call_id)
    spool_state: str | None = None
    spool_response_status: int | None = None
    spool_response_sha256: str | None = None
    if spool is not None:
        spool_request = bytes(spool["request_bytes"])
        if (
            spool["intent_sha256"] != row["intent_sha256"]
            or spool["request_sha256"] != row["request_sha256"]
            or hashlib.sha256(spool_request).hexdigest() != spool["request_sha256"]
            or spool_request != request_raw
        ):
            raise PriorExposureRefusal("attempt/spool request identity drifted")
        spool_state = str(spool["status"])
        spool_response_status = spool["response_status"]
        spool_response_sha256 = spool["response_sha256"]
        if spool_state == "COMPLETE" and (
            not isinstance(spool_response_status, int)
            or not isinstance(spool_response_sha256, str)
            or _SHA256.fullmatch(spool_response_sha256) is None
        ):
            raise PriorExposureRefusal("complete spool row lacks response metadata")
    response_sha = row["response_sha256"]
    model_response_sha = row["model_response_sha256"]
    receipt_sha = row["call_receipt_sha256"]
    for candidate, label in (
        (response_sha, "response"),
        (model_response_sha, "model response"),
        (receipt_sha, "call receipt"),
    ):
        if candidate is not None and (
            not isinstance(candidate, str) or _SHA256.fullmatch(candidate) is None
        ):
            raise PriorExposureRefusal(f"attempt {label} digest drifted")
    if (
        spool_state == "COMPLETE"
        and (row["response_status"] is not None or response_sha is not None)
        and (
            spool_response_status != row["response_status"]
            or spool_response_sha256 != response_sha
        )
    ):
        raise PriorExposureRefusal("attempt/spool response metadata drifted")
    return {
        "physical_call_id": physical_call_id,
        "run_id": str(call["run_id"]),
        "arm_id": str(call["arm_id"]),
        "item_id": item_id,
        "call_index": int(call["call_index"]),
        "function_id": str(call["function_id"]),
        "model": str(call["model"]),
        "model_revision": str(call["model_revision"]),
        "input_type": str(call["input_type"]),
        "output_type": str(call["output_type"]),
        "max_output_tokens": int(call["max_output_tokens"]),
        "dataset_row_index": item_metadata["dataset_row_index"],
        "question_sha256": item_metadata["question_sha256"],
        "source_entity_ids": list(item_metadata["source_entity_ids"]),
        "component_id": item_metadata["component_id"],
        "intent_sha256": str(row["intent_sha256"]),
        "request_sha256": str(row["request_sha256"]),
        "raw_attempt_state": str(row["status"]),
        "response_status": row["response_status"],
        "response_sha256": response_sha,
        "model_response_sha256": model_response_sha,
        "call_receipt_sha256": receipt_sha,
        "terminal_code": row["terminal_code"],
        "spool_snapshot_state": spool_state,
        "spool_response_status": spool_response_status,
        "spool_response_sha256": spool_response_sha256,
        "_query_plan_sha256": (
            canonical_sha256(call["input_payload"]["query_plan"])
            if call_index in {2, 3}
            else None
        ),
    }


def _replay_attempt_event_chain(
    rows: Sequence[sqlite3.Row],
    call_states: Mapping[str, str],
    call_bindings: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    previous = _GENESIS
    per_call_state: dict[str, str] = {}
    per_call_counts: dict[str, int] = {}
    delivery_ordinals: dict[str, int] = {}
    for expected_sequence, row in enumerate(rows):
        raw = bytes(row["event_bytes"])
        value = _strict_canonical_blob(raw, "attempt event")
        physical_call_id = str(row["physical_call_id"])
        event_type = str(row["event_type"])
        if (
            int(row["sequence"]) != expected_sequence
            or row["previous_event_sha256"] != previous
            or hashlib.sha256(raw).hexdigest() != row["event_sha256"]
            or set(value)
            != {
                "schema_version", "sequence", "physical_call_id", "event_type",
                "detail", "previous_event_sha256",
            }
            or value.get("schema_version") != _DURABLE_CALL_SCHEMA
            or type(value.get("sequence")) is not int
            or value.get("sequence") != expected_sequence
            or value.get("physical_call_id") != physical_call_id
            or value.get("event_type") != event_type
            or value.get("previous_event_sha256") != previous
            or physical_call_id not in call_states
            or event_type not in _EVENT_TRANSITIONS
            or per_call_state.get(physical_call_id) not in _EVENT_TRANSITIONS[event_type]
            or not isinstance(value.get("detail"), Mapping)
        ):
            raise PriorExposureRefusal("attempt event chain drifted")
        if event_type == "PREPARED":
            detail = value["detail"]
            if (
                set(detail) != {"intent_sha256", "request_sha256"}
                or detail
                != {
                    "intent_sha256": call_bindings[physical_call_id][
                        "intent_sha256"
                    ],
                    "request_sha256": call_bindings[physical_call_id][
                        "request_sha256"
                    ],
                }
            ):
                raise PriorExposureRefusal("PREPARED event detail drifted")
        elif event_type == "SENT":
            detail = value["detail"]
            ordinal = detail.get("delivery_ordinal")
            if (
                set(detail) != {"delivery_ordinal", "same_inference_identity"}
                or isinstance(ordinal, bool)
                or not isinstance(ordinal, int)
                or ordinal
                != delivery_ordinals.get(physical_call_id, 0) + 1
                or detail.get("same_inference_identity") is not True
            ):
                raise PriorExposureRefusal("SENT event detail drifted")
            delivery_ordinals[physical_call_id] = ordinal
        elif event_type == "DELIVERY_AMBIGUOUS":
            detail = value["detail"]
            if (
                set(detail) != {"delivery_ordinal", "error_class"}
                or type(detail.get("delivery_ordinal")) is not int
                or detail.get("delivery_ordinal")
                != delivery_ordinals.get(physical_call_id)
                or not isinstance(detail.get("error_class"), str)
                or not detail.get("error_class")
            ):
                raise PriorExposureRefusal("ambiguous delivery detail drifted")
        elif event_type == "RAW_COMPLETE":
            detail = value["detail"]
            if (
                set(detail) != {"http_status", "response_sha256", "response_bytes"}
                or detail.get("http_status")
                != call_bindings[physical_call_id]["response_status"]
                or isinstance(detail.get("http_status"), bool)
                or not isinstance(detail.get("http_status"), int)
                or not 100 <= int(detail["http_status"]) <= 599
                or detail.get("response_sha256")
                != call_bindings[physical_call_id]["response_sha256"]
                or not _is_sha256(detail.get("response_sha256"))
                or isinstance(detail.get("response_bytes"), bool)
                or not isinstance(detail.get("response_bytes"), int)
                or int(detail["response_bytes"]) < 0
            ):
                raise PriorExposureRefusal("raw response event detail drifted")
        elif event_type == "ENVELOPE_VALID":
            detail = value["detail"]
            if detail != {
                "finish_reason": "stop",
                "served_model": call_bindings[physical_call_id]["model"],
            }:
                raise PriorExposureRefusal("envelope event detail drifted")
        elif event_type == "SCHEMA_VALID":
            detail = value["detail"]
            output_type = call_bindings[physical_call_id]["output_type"]
            if (
                not _is_sha256(
                    call_bindings[physical_call_id]["model_response_sha256"]
                )
                or detail
                != {
                    "output_type": output_type,
                    "output_schema_sha256": output_schema_sha256(
                        str(output_type)
                    ),
                    "model_response_sha256": call_bindings[physical_call_id][
                        "model_response_sha256"
                    ],
                }
            ):
                raise PriorExposureRefusal("schema event detail drifted")
        elif event_type == "ACCEPTED":
            receipt_sha = call_bindings[physical_call_id]["call_receipt_sha256"]
            if not _is_sha256(receipt_sha) or value["detail"] != {
                "call_receipt_sha256": receipt_sha
            }:
                raise PriorExposureRefusal("accepted event detail drifted")
        elif event_type in {"REJECTED_PROTOCOL", "AMBIGUOUS_ABORT"}:
            code = call_bindings[physical_call_id]["terminal_code"]
            if (
                not isinstance(code, str)
                or not code
                or value["detail"] != {"code": code}
            ):
                raise PriorExposureRefusal("terminal event detail drifted")
        per_call_state[physical_call_id] = event_type
        per_call_counts[physical_call_id] = per_call_counts.get(physical_call_id, 0) + 1
        previous = str(row["event_sha256"])
    if per_call_state != dict(call_states):
        raise PriorExposureRefusal("attempt event terminal states differ from call rows")
    return {
        "event_count": len(rows),
        "event_chain_tip_sha256": previous,
        "per_call_event_counts": {
            key: per_call_counts[key] for key in sorted(per_call_counts)
        },
        "per_call_terminal_states": {
            key: per_call_state[key] for key in sorted(per_call_state)
        },
    }


def _read_attempt_observations(
    connection: sqlite3.Connection,
    *,
    spool_rows: Mapping[str, sqlite3.Row],
    metadata: Mapping[str, Mapping[str, object]],
    manifest: Mapping[str, object],
    spool_endpoint: str,
    expected_prompts: Mapping[tuple[str, str], str],
) -> tuple[list[dict[str, object]], dict[str, object], list[dict[str, object]]]:
    call_rows = connection.execute(
        "SELECT physical_call_id,intent_sha256,intent_bytes,request_sha256,"
        "endpoint,request_bytes,status,response_status,response_sha256,"
        "model_response_sha256,call_receipt_sha256,terminal_code "
        "FROM call_state ORDER BY physical_call_id"
    ).fetchall()
    event_rows = connection.execute(
        "SELECT sequence,physical_call_id,event_type,event_bytes,"
        "previous_event_sha256,event_sha256 FROM attempt_events ORDER BY sequence"
    ).fetchall()
    item_rows = connection.execute(
        "SELECT run_id,arm_id,item_id,run_receipt_sha256 "
        "FROM item_runs ORDER BY run_id,arm_id,item_id"
    ).fetchall()
    if not call_rows:
        raise PriorExposureRefusal("aborted attempt contains no durable calls")
    call_ids = {str(row["physical_call_id"]) for row in call_rows}
    if set(spool_rows) - call_ids:
        raise PriorExposureRefusal("spool snapshot contains a foreign physical call")
    observations = [
        _replay_call_intent_request(
            row,
            spool_rows=spool_rows,
            metadata=metadata,
            manifest=manifest,
            spool_endpoint=spool_endpoint,
            expected_prompts=expected_prompts,
        )
        for row in call_rows
    ]
    observations.sort(
        key=lambda value: (
            str(value["item_id"]),
            _F1_ARMS.index(str(value["arm_id"])),
            int(value["call_index"]),
        )
    )
    call_states = {str(row["physical_call_id"]): str(row["status"]) for row in call_rows}
    call_bindings = {
        str(observation["physical_call_id"]): observation
        for observation in observations
    }
    event_chain = _replay_attempt_event_chain(
        event_rows, call_states, call_bindings
    )
    item_runs: list[dict[str, object]] = []
    for row in item_rows:
        receipt_sha = row["run_receipt_sha256"]
        if (
            not isinstance(receipt_sha, str)
            or _SHA256.fullmatch(receipt_sha) is None
            or str(row["item_id"]) not in metadata
            or str(row["arm_id"]) not in _F1_ARMS
        ):
            raise PriorExposureRefusal("item-run structural identity drifted")
        item_runs.append(
            {
                "run_id": str(row["run_id"]),
                "arm_id": str(row["arm_id"]),
                "item_id": str(row["item_id"]),
                "run_receipt_sha256": receipt_sha,
                "dataset_row_index": metadata[str(row["item_id"])][
                    "dataset_row_index"
                ],
                "question_sha256": metadata[str(row["item_id"])][
                    "question_sha256"
                ],
                "source_entity_ids": list(
                    metadata[str(row["item_id"])] ["source_entity_ids"]
                ),
                "component_id": metadata[str(row["item_id"])]["component_id"],
            }
        )
    item_runs.sort(
        key=lambda value: (
            str(value["item_id"]),
            _F1_ARMS.index(str(value["arm_id"])),
        )
    )
    call_groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for observation in observations:
        key = (str(observation["item_id"]), str(observation["arm_id"]))
        call_groups.setdefault(key, []).append(observation)
    for group in call_groups.values():
        indices = sorted(int(call["call_index"]) for call in group)
        if indices != list(range(1, max(indices) + 1)):
            raise PriorExposureRefusal("aborted attempt call sequence is not a prefix")
        query_plans = {
            str(call["_query_plan_sha256"])
            for call in group
            if call["_query_plan_sha256"] is not None
        }
        if len(query_plans) > 1:
            raise PriorExposureRefusal(
                "aborted attempt query plan changes within an item run"
            )
    for observation in observations:
        observation.pop("_query_plan_sha256", None)
    item_run_keys: set[tuple[str, str]] = set()
    for item_run in item_runs:
        key = (str(item_run["item_id"]), str(item_run["arm_id"]))
        if key in item_run_keys:
            raise PriorExposureRefusal("aborted attempt item-run identity repeats")
        item_run_keys.add(key)
        group = call_groups.get(key, [])
        if (
            [int(call["call_index"]) for call in group] != [1, 2, 3]
            or any(call["raw_attempt_state"] != "ACCEPTED" for call in group)
        ):
            raise PriorExposureRefusal("item run lacks three accepted calls")
    return observations, event_chain, item_runs


def _read_spool_observations(
    connection: sqlite3.Connection,
) -> dict[str, sqlite3.Row]:
    rows = connection.execute(
        "SELECT physical_call_id,intent_sha256,request_sha256,request_bytes,"
        "status,response_status,response_sha256,error_class "
        "FROM spool_calls ORDER BY physical_call_id"
    ).fetchall()
    result: dict[str, sqlite3.Row] = {}
    for row in rows:
        physical_call_id = str(row["physical_call_id"])
        status_value = row["status"]
        response_status = row["response_status"]
        response_sha256 = row["response_sha256"]
        error_class = row["error_class"]
        if (
            physical_call_id in result
            or _SHA256.fullmatch(physical_call_id) is None
            or status_value not in {"DISPATCHING", "COMPLETE", "UNKNOWN"}
        ):
            raise PriorExposureRefusal("spool structural identity drifted")
        if status_value == "COMPLETE" and (
            isinstance(response_status, bool)
            or not isinstance(response_status, int)
            or not 100 <= response_status <= 599
            or not _is_sha256(response_sha256)
            or error_class is not None
        ):
            raise PriorExposureRefusal("complete spool metadata drifted")
        if status_value == "DISPATCHING" and any(
            value is not None
            for value in (response_status, response_sha256, error_class)
        ):
            raise PriorExposureRefusal("dispatching spool metadata drifted")
        if status_value == "UNKNOWN" and (
            response_status is not None
            or response_sha256 is not None
            or not isinstance(error_class, str)
            or not error_class
        ):
            raise PriorExposureRefusal("unknown spool metadata drifted")
        result[physical_call_id] = row
    return result


def build_aborted_attempt_exposure_receipt(
    *,
    attempt_db: Path,
    spool_db: Path,
    selection_receipt: Path,
    manifest: Path,
    source_receipt: Path,
    execution_lock: Path,
    db_genesis_receipt: Path,
    environment_dependency_bundle: Path,
    model_deployment_receipt: Path,
    spool_identity_receipt: Path,
    job_command: Path,
    job_log: Path,
    job_rc: Path,
    hswm_executable_root: Path,
    hswm_carrier_root: Path,
    symposium_root: Path,
    snapshot_dir: Path,
    private_witness_output: Path,
    producer_hswm_root: Path | None = None,
    historical_python: Path | None = None,
) -> dict[str, object]:
    """Derive a quarantine boundary from copied structural evidence only."""

    resolved_producer_root = _current_producer_root(producer_hswm_root)
    job_rc_raw = _read_stable_public_bytes(job_rc)
    try:
        job_rc_value = int(job_rc_raw.decode("ascii").strip())
    except (UnicodeError, ValueError) as error:
        raise PriorExposureRefusal("aborted job exit-code evidence is malformed") from error
    job_paths = [Path(job_command), Path(job_log), Path(job_rc)]
    job_parents = {str(path.resolve(strict=True).parent) for path in job_paths}
    if (
        job_rc_value != 135
        or len(job_parents) != 1
        or [path.name for path in job_paths] != ["cmd.sh", "log", "rc"]
        or not job_paths[0].parent.name.startswith(
            "hswm-f1-r8-v8-development-"
        )
    ):
        raise PriorExposureRefusal("aborted DT job evidence set drifted")
    signal_number = job_rc_value - 128
    signal_name = _LINUX_SIGNAL_NAMES.get(signal_number)
    if signal_name is None:
        raise PriorExposureRefusal("aborted Linux job signal is unknown")
    snapshot_dir = Path(snapshot_dir)
    try:
        snapshot_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    except OSError as error:
        raise PriorExposureRefusal("snapshot directory must be unused") from error
    if stat.S_IMODE(snapshot_dir.stat().st_mode) != 0o700:
        raise PriorExposureRefusal("snapshot directory is not mode 0700")
    parent_fd = os.open(snapshot_dir.parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)

    attempt_snapshot_path, attempt_snapshot = _snapshot_sqlite_pair(
        attempt_db, snapshot_dir, label="attempt"
    )
    spool_snapshot_path, spool_snapshot = _snapshot_sqlite_pair(
        spool_db, snapshot_dir, label="spool"
    )
    _verify_sqlite_source_pair(attempt_db, attempt_snapshot)
    _verify_sqlite_source_pair(spool_db, spool_snapshot)
    artifacts: dict[str, dict[str, object]] = {}
    artifact_values: dict[str, dict[str, object]] = {}
    artifact_paths = {
        "selection_receipt": selection_receipt,
        "manifest": manifest,
        "source_receipt": source_receipt,
        "execution_lock": execution_lock,
        "db_genesis_receipt": db_genesis_receipt,
        "environment_dependency_bundle": environment_dependency_bundle,
        "model_deployment_receipt": model_deployment_receipt,
        "spool_identity_receipt": spool_identity_receipt,
    }
    for name, path in artifact_paths.items():
        value, binding = _artifact_binding(name, Path(path))
        artifact_values[name] = value
        artifacts[name] = binding
    manifest_value = artifact_values["manifest"]
    source_value = artifact_values["source_receipt"]
    historical_replay, historical_authority = _historical_runtime_replay(
        hswm_root=hswm_executable_root,
        carrier_root=hswm_carrier_root,
        symposium_root=symposium_root,
        historical_python=(
            Path(sys.executable) if historical_python is None else historical_python
        ),
        selection=artifact_values["selection_receipt"],
        manifest=manifest_value,
        source_receipt=source_value,
        lock=artifact_values["execution_lock"],
        environment=artifact_values["environment_dependency_bundle"],
    )
    _verify_incident_artifact_semantics(artifact_values, historical_replay)
    metadata = _source_metadata(manifest_value, source_value)
    repositories = historical_authority["repositories"]
    assert isinstance(repositories, Mapping)
    producer_authority = _current_producer_authority(resolved_producer_root)
    lock_value = artifact_values["execution_lock"]
    selection_value = artifact_values["selection_receipt"]
    genesis_value = artifact_values["db_genesis_receipt"]
    environment_value = artifact_values["environment_dependency_bundle"]
    deployment_value = artifact_values["model_deployment_receipt"]
    spool_identity_value = artifact_values["spool_identity_receipt"]
    prompt_rows = historical_replay.get("prompts")
    if not isinstance(prompt_rows, list):
        raise PriorExposureRefusal("historical replay prompts are absent")
    expected_prompts: dict[tuple[str, str], str] = {}
    for prompt_row in prompt_rows:
        if (
            not isinstance(prompt_row, Mapping)
            or set(prompt_row) != {"arm_id", "function_id", "prompt"}
            or prompt_row.get("arm_id") not in _F1_ARMS
            or not isinstance(prompt_row.get("function_id"), str)
            or not prompt_row.get("function_id")
            or not isinstance(prompt_row.get("prompt"), str)
            or not prompt_row.get("prompt")
        ):
            raise PriorExposureRefusal("historical replay prompt drifted")
        key = (str(prompt_row["arm_id"]), str(prompt_row["function_id"]))
        if key in expected_prompts:
            raise PriorExposureRefusal("historical replay prompt repeats")
        expected_prompts[key] = str(prompt_row["prompt"])
    incident_environment_receipt = environment_value.get("environment_receipt")
    incident_environment_labels = (
        incident_environment_receipt.get("labels")
        if isinstance(incident_environment_receipt, Mapping)
        else None
    )
    if (
        lock_value.get("hswm_commit") != repositories["hswm_executable"]["commit"]
        or lock_value.get("manifest_sha256") != canonical_sha256(manifest_value)
        or not isinstance(incident_environment_labels, Mapping)
        or incident_environment_labels.get("symposium_commit")
        != repositories["symposium"]["commit"]
    ):
        raise PriorExposureRefusal(
            "incident lock/repository provenance differs from captured artifacts"
        )
    for key in ("run_id", "mode", "model", "model_revision"):
        if manifest_value.get(key) != lock_value.get(key):
            raise PriorExposureRefusal(f"incident manifest/lock {key} drifted")
    source_declared = source_value.get("source_receipt_sha256")
    if (
        source_declared
        != artifacts["source_receipt"]["declared_hashes"].get(
            "source_receipt_sha256"
        )
    ):
        raise PriorExposureRefusal("incident source receipt self-binding drifted")
    expected_lock_bindings = {
        "selection_receipt_sha256": selection_value.get(
            "selection_receipt_sha256"
        ),
        "public_source_receipt_sha256": source_declared,
        "db_genesis_receipt_sha256": genesis_value.get("genesis_sha256"),
        "environment_dependency_bundle_sha256": environment_value.get(
            "bundle_sha256"
        ),
        "deployment_receipt_sha256": deployment_value.get("receipt_sha256"),
    }
    if any(lock_value.get(key) != expected for key, expected in expected_lock_bindings.items()):
        raise PriorExposureRefusal("incident artifact differs from execution lock")
    incident_dependency_receipt = environment_value.get("dependency_receipt")
    incident_dependency_files = (
        incident_dependency_receipt.get("files")
        if isinstance(incident_dependency_receipt, Mapping)
        else None
    )
    if (
        not isinstance(incident_dependency_files, Mapping)
        or incident_dependency_files["model_deployment_receipt"].get("sha256")
        != artifacts["model_deployment_receipt"]["raw_sha256"]
    ):
        raise PriorExposureRefusal(
            "incident deployment dependency differs from the captured artifact"
        )
    if (
        source_value.get("public_selection_receipt_sha256")
        != selection_value.get("selection_receipt_sha256")
        or manifest_value.get("preregistration_artifact_sha256")
        != lock_value.get("preregistration_artifact_sha256")
    ):
        raise PriorExposureRefusal("incident public source or preregistration binding drifted")
    spool_expected = {
        "run_id": lock_value.get("run_id"),
        "model_revision": lock_value.get("model_revision"),
        "execution_lock_sha256": lock_value.get("lock_sha256"),
        "db_genesis_sha256": genesis_value.get("genesis_sha256"),
        "deployment_receipt_sha256": deployment_value.get("receipt_sha256"),
        "deployment_id": lock_value.get("deployment_id"),
        "served_model": lock_value.get("served_model"),
        "upstream_endpoint": lock_value.get("upstream_endpoint"),
    }
    if any(spool_identity_value.get(key) != expected for key, expected in spool_expected.items()):
        raise PriorExposureRefusal("incident spool identity binding drifted")
    spool_endpoint = spool_identity_value.get("endpoint")
    execution_policy = lock_value.get("execution_policy")
    if (
        not isinstance(spool_endpoint, str)
        or not spool_endpoint
        or not isinstance(execution_policy, Mapping)
        or execution_policy.get("endpoint") != spool_endpoint
    ):
        raise PriorExposureRefusal("incident spool route binding drifted")
    attempt_source_identity = attempt_snapshot["source_identity"]
    spool_source_identity = spool_snapshot["source_identity"]
    endpoint_identity = spool_identity_value.get("endpoint_identity")
    if (
        genesis_value.get("attempt_db_identity") != attempt_source_identity
        or genesis_value.get("spool_db_identity") != spool_source_identity
        or not isinstance(endpoint_identity, Mapping)
        or endpoint_identity.get("db_identity") != spool_source_identity
    ):
        raise PriorExposureRefusal("incident SQLite source identity drifted")

    spool_connection, spool_database = _open_snapshot_read_only(
        spool_snapshot_path,
        expected_columns=_SPOOL_COLUMNS,
        authority=_HISTORICAL_V8_SCHEMA_AUTHORITIES["spool"],
        label="spool",
    )
    try:
        spool_rows = _read_spool_observations(spool_connection)
    finally:
        if spool_connection.in_transaction:
            spool_connection.execute("ROLLBACK")
        spool_connection.close()
    attempt_connection, attempt_database = _open_snapshot_read_only(
        attempt_snapshot_path,
        expected_columns=_ATTEMPT_COLUMNS,
        authority=_HISTORICAL_V8_SCHEMA_AUTHORITIES["attempt"],
        label="attempt",
    )
    try:
        call_observations, event_chain, item_runs = _read_attempt_observations(
            attempt_connection,
            spool_rows=spool_rows,
            metadata=metadata,
            manifest=manifest_value,
            spool_endpoint=spool_endpoint,
            expected_prompts=expected_prompts,
        )
    finally:
        if attempt_connection.in_transaction:
            attempt_connection.execute("ROLLBACK")
        attempt_connection.close()
    if (
        attempt_database.get("schema_sha256")
        != genesis_value.get("attempt_schema_sha256")
        or spool_database.get("schema_sha256")
        != genesis_value.get("spool_schema_sha256")
        or attempt_database.get("journal_mode")
        != genesis_value.get("attempt_journal_mode")
        or spool_database.get("journal_mode")
        != genesis_value.get("spool_journal_mode")
        or attempt_database.get("user_version")
        != genesis_value.get("attempt_user_version")
        or spool_database.get("user_version")
        != genesis_value.get("spool_user_version")
    ):
        raise PriorExposureRefusal("incident SQLite schema differs from genesis")
    for path, snapshot in (
        (attempt_snapshot_path, attempt_snapshot),
        (spool_snapshot_path, spool_snapshot),
    ):
        for suffix, member_name in (("", "main"), ("-wal", "wal")):
            binding = _stable_public_file_binding(Path(f"{path}{suffix}"))
            member = snapshot["members"][member_name]
            if (
                binding["size_bytes"] != member["size_bytes"]
                or binding["sha256"] != member["sha256"]
            ):
                raise PriorExposureRefusal("private SQLite snapshot changed during replay")
    command_raw = _read_stable_public_bytes(job_command)
    log_raw = _read_stable_public_bytes(job_log)
    if not command_raw or not log_raw:
        raise PriorExposureRefusal("job command or log evidence is empty")
    incident_root = str(Path(attempt_db).resolve(strict=True).parent.parent)
    required_command_fragments = (
        incident_root.encode("utf-8"),
        b"prom_search_hswm.prom9_f1_r8_runner",
        b"--attempt-db", b"attempt.sqlite3", b"--spool-db", b"spool.sqlite3",
        b"--manifest", Path(manifest).name.encode("utf-8"),
        b"--execution-lock", Path(execution_lock).name.encode("utf-8"),
    )
    if any(fragment not in command_raw for fragment in required_command_fragments):
        raise PriorExposureRefusal("DT job command is not bound to the incident")
    if b"Bus error" not in log_raw or b"core dumped" not in log_raw:
        raise PriorExposureRefusal("DT job log does not corroborate SIGBUS")
    _verify_sqlite_source_pair(attempt_db, attempt_snapshot)
    _verify_sqlite_source_pair(spool_db, spool_snapshot)
    touched_items = sorted(
        {str(row["item_id"]) for row in call_observations}
        | {str(row["item_id"]) for row in item_runs}
    )
    if any(item not in metadata for item in touched_items):
        raise PriorExposureRefusal("touched item lacks public source metadata")
    touched_sources = sorted(
        {
            str(source)
            for item in touched_items
            for source in metadata[item]["source_entity_ids"]
        }
    )
    touched_components = sorted(
        {str(metadata[item]["component_id"]) for item in touched_items}
    )
    aggregate = {
        "prior_item_ids": touched_items,
        "prior_source_entity_ids": touched_sources,
        "prior_component_ids": touched_components,
        "item_root_sha256": canonical_sha256(touched_items),
        "source_entity_root_sha256": canonical_sha256(touched_sources),
        "component_root_sha256": canonical_sha256(touched_components),
    }
    derived = [
        {
            "claim": "MATCHING_SPOOL_ROW_ABSENT",
            "epistemic_status": "DERIVED_FROM_BOUND_SNAPSHOTS",
            "physical_call_id": str(row["physical_call_id"]),
            "raw_attempt_state": str(row["raw_attempt_state"]),
        }
        for row in call_observations
        if row["spool_snapshot_state"] is None
    ]
    state_counts: dict[str, int] = {}
    for row in call_observations:
        state = str(row["raw_attempt_state"])
        state_counts[state] = state_counts.get(state, 0) + 1
    public_attempt_snapshot = _public_database_snapshot(
        {**attempt_snapshot, **attempt_database}, kind="attempt"
    )
    public_spool_snapshot = _public_database_snapshot(
        {**spool_snapshot, **spool_database}, kind="spool"
    )
    unsigned = {
        "schema_version": ABORTED_ATTEMPT_EXPOSURE_SCHEMA,
        "status": ABORTED_ATTEMPT_STATUS,
        "run_identity": {
            "run_id": manifest_value.get("run_id"),
            "mode": manifest_value.get("mode"),
            "model": manifest_value.get("model"),
            "model_revision": manifest_value.get("model_revision"),
            "job_alias": "HSWM_F1_R8_V8_DEVELOPMENT_SIGBUS",
            "implementation_commit": repositories["hswm_executable"]["commit"],
            "carrier_commit": repositories["hswm_carrier"]["commit"],
            "symposium_commit": repositories["symposium"]["commit"],
        },
        "termination": {
            "evidence_status": "OBSERVED_DT_JOB_DIRECTORY",
            "signal": signal_name,
            "signal_number": signal_number,
            "exit_code": job_rc_value,
            "rc_evidence": {
                "basename": Path(job_rc).name,
                "size_bytes": len(job_rc_raw),
                "sha256": hashlib.sha256(job_rc_raw).hexdigest(),
            },
        },
        "source_binding": {
            "source_receipt_sha256": source_declared,
            "public_source_receipt": source_value,
            "public_manifest": manifest_value,
            "manifest_canonical_sha256": canonical_sha256(manifest_value),
            "all_metadata_root_sha256": canonical_sha256(
                [metadata[item] for item in sorted(metadata)]
            ),
            "touched_metadata_root_sha256": canonical_sha256(
                [metadata[item] for item in touched_items]
            ),
        },
        "capture_policy": {
            "sqlite_authority_members": ["main", "wal"],
            "sqlite_shm_authoritative": False,
            "response_blob_columns_read": False,
            "item_run_blob_columns_read": False,
            "gold_inputs_accepted": False,
            "model_calls_invoked": False,
            "kg_accessed": False,
            "raw_attempt_states_preserved": True,
        },
        "evidence_bindings": {
            "artifacts": artifacts,
            "historical_runtime_authority": {
                **historical_authority,
            },
            "current_producer_authority": producer_authority,
            "job_command": {
                "basename": Path(job_command).name,
                "size_bytes": len(command_raw),
                "sha256": hashlib.sha256(command_raw).hexdigest(),
            },
            "job_log": {
                "basename": Path(job_log).name,
                "size_bytes": len(log_raw),
                "sha256": hashlib.sha256(log_raw).hexdigest(),
            },
        },
        "database_snapshots": {
            "attempt": public_attempt_snapshot,
            "spool": public_spool_snapshot,
        },
        "call_observations": call_observations,
        "item_run_observations": item_runs,
        "event_chain": event_chain,
        "derived_inferences": derived,
        "counts": {
            "attempt_calls": len(call_observations),
            "attempt_events": int(event_chain["event_count"]),
            "item_runs": len(item_runs),
            "spool_calls": len(spool_rows),
            "attempt_states": {key: state_counts[key] for key in sorted(state_counts)},
            "spool_complete_calls": sum(
                row["spool_snapshot_state"] == "COMPLETE" for row in call_observations
            ),
            "spool_absent_calls": sum(
                row["spool_snapshot_state"] is None for row in call_observations
            ),
            "items": len(touched_items),
            "source_entities": len(touched_sources),
            "components": len(touched_components),
        },
        "aggregate": aggregate,
        "complete": True,
    }
    attempt_witness = _private_database_witness(attempt_db, "attempt ledger")
    spool_witness = _private_database_witness(spool_db, "result spool")
    if (
        (attempt_witness["st_dev"], attempt_witness["st_ino"])
        == (spool_witness["st_dev"], spool_witness["st_ino"])
        or attempt_witness["resolved_path"] == spool_witness["resolved_path"]
    ):
        raise PriorExposureRefusal("private database identities alias")
    incident_stage_path = Path(incident_root)
    for database_witness in (attempt_witness, spool_witness):
        database_path = Path(str(database_witness["resolved_path"]))
        try:
            database_path.relative_to(incident_stage_path)
        except ValueError as error:
            raise PriorExposureRefusal(
                "private database is outside the incident stage"
            ) from error
        if database_path == incident_stage_path:
            raise PriorExposureRefusal("private database path is not a file child")
        if database_path.parent.parent != incident_stage_path:
            raise PriorExposureRefusal(
                "private database does not identify the exact incident stage"
            )
    witness_destination = Path(private_witness_output).resolve(strict=False)
    witness_parent = witness_destination.parent
    try:
        parent_info = witness_parent.lstat()
    except OSError as error:
        raise PriorExposureRefusal(
            "private witness parent must already exist"
        ) from error
    if (
        stat.S_ISLNK(parent_info.st_mode)
        or not stat.S_ISDIR(parent_info.st_mode)
        or stat.S_IMODE(parent_info.st_mode) != 0o700
        or parent_info.st_uid != os.geteuid()
    ):
        raise PriorExposureRefusal("private witness parent must be owner-private 0700")
    for repository_root in (
        hswm_executable_root,
        hswm_carrier_root,
        symposium_root,
        resolved_producer_root,
    ):
        resolved_repository = Path(repository_root).resolve(strict=True)
        if os.path.commonpath(
            (str(witness_destination), str(resolved_repository))
        ) == str(resolved_repository):
            raise PriorExposureRefusal("private witness must remain outside Git roots")
    incident_preimage_root = canonical_sha256(unsigned)
    witness_unsigned = {
        "schema_version": ABORTED_ATTEMPT_PRIVATE_WITNESS_SCHEMA,
        "nonce_hex": secrets.token_hex(32),
        "incident_preimage_root_sha256": incident_preimage_root,
        "stage_path": incident_root,
        "databases": {
            "attempt": attempt_witness,
            "spool": spool_witness,
        },
        "db_genesis_receipt": genesis_value,
        "spool_identity_receipt": spool_identity_value,
    }
    witness = {
        **witness_unsigned,
        "private_witness_sha256": canonical_sha256(witness_unsigned),
    }
    write_private_once(witness_destination, witness)
    public_unsigned = {
        **unsigned,
        "assurance": "PRODUCER_ATTESTED",
        "private_witness_commitment": {
            "schema_version": ABORTED_ATTEMPT_PRIVATE_WITNESS_SCHEMA,
            "algorithm": "SHA256_CANONICAL_JSON_V1",
            "incident_preimage_root_sha256": incident_preimage_root,
            "private_witness_sha256": witness["private_witness_sha256"],
        },
    }
    return {
        **public_unsigned,
        "aborted_attempt_exposure_receipt_sha256": canonical_sha256(
            public_unsigned
        ),
    }


def _valid_call_observation_scalars(call: Mapping[str, object]) -> bool:
    text_fields = (
        "run_id", "arm_id", "item_id", "function_id", "model",
        "model_revision", "input_type", "output_type",
    )
    return (
        all(isinstance(call.get(key), str) and bool(call.get(key)) for key in text_fields)
        and not isinstance(call.get("call_index"), bool)
        and call.get("call_index") in {1, 2, 3}
        and not isinstance(call.get("max_output_tokens"), bool)
        and isinstance(call.get("max_output_tokens"), int)
        and int(call["max_output_tokens"]) > 0
        and not isinstance(call.get("dataset_row_index"), bool)
        and isinstance(call.get("dataset_row_index"), int)
        and int(call["dataset_row_index"]) >= 0
    )


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _verify_recorded_file(
    value: object, *, fields: set[str], label: str
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise PriorExposureRefusal(f"aborted-attempt {label} shape drifted")
    if (
        not isinstance(value.get("basename"), str)
        or not value.get("basename")
        or isinstance(value.get("size_bytes"), bool)
        or not isinstance(value.get("size_bytes"), int)
        or int(value["size_bytes"]) < 1
        or not _is_sha256(value.get("sha256"))
    ):
        raise PriorExposureRefusal(f"aborted-attempt {label} identity drifted")
    return value


def _verify_current_producer_authority(value: object) -> Mapping[str, object]:
    fields = {
        "commit", "tree", "entrypoint", "closure_policy", "files",
        "file_count", "closure_root_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise PriorExposureRefusal("current producer authority shape drifted")
    if (
        any(
            not isinstance(value.get(key), str)
            or _GIT_COMMIT.fullmatch(str(value.get(key))) is None
            for key in ("commit", "tree")
        )
        or value.get("entrypoint")
        != "prom_search_hswm/prom9_f1_prior_exposure.py"
        or value.get("closure_policy") != "MODULE_SCOPE_LOCAL_AST_LFP_V1"
    ):
        raise PriorExposureRefusal("current producer authority identity drifted")
    files = value.get("files")
    if (
        not isinstance(files, list)
        or isinstance(value.get("file_count"), bool)
        or value.get("file_count") != len(_CURRENT_PRODUCER_IMPORT_LFP)
        or len(files) != len(_CURRENT_PRODUCER_IMPORT_LFP)
        or value.get("closure_root_sha256") != canonical_sha256(files)
    ):
        raise PriorExposureRefusal("current producer authority root drifted")
    observed_paths: list[str] = []
    for entry in files:
        if (
            not isinstance(entry, Mapping)
            or set(entry)
            != {
                "relative_path", "size_bytes", "sha256", "blob_mode", "blob_oid",
            }
            or not isinstance(entry.get("relative_path"), str)
            or not entry.get("relative_path")
            or isinstance(entry.get("size_bytes"), bool)
            or not isinstance(entry.get("size_bytes"), int)
            or int(entry["size_bytes"]) < 1
            or not _is_sha256(entry.get("sha256"))
            or entry.get("blob_mode") not in {"100644", "100755"}
            or not isinstance(entry.get("blob_oid"), str)
            or _GIT_COMMIT.fullmatch(str(entry.get("blob_oid"))) is None
        ):
            raise PriorExposureRefusal("current producer file binding drifted")
        observed_paths.append(str(entry["relative_path"]))
    if tuple(observed_paths) != _CURRENT_PRODUCER_IMPORT_LFP:
        raise PriorExposureRefusal("current producer import closure drifted")
    return value


def _verify_historical_runtime_authority(value: object) -> Mapping[str, object]:
    fields = {
        "repositories", "replay_policy", "replay_files", "replay_file_count",
        "replay_closure_root_sha256", "python_runtime", "replay_result_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise PriorExposureRefusal("historical runtime authority shape drifted")
    repositories = value.get("repositories")
    if not isinstance(repositories, Mapping) or set(repositories) != set(
        _HISTORICAL_RUNTIME_COMMITS
    ):
        raise PriorExposureRefusal("historical repository inventory drifted")
    for name, expected_commit in _HISTORICAL_RUNTIME_COMMITS.items():
        binding = repositories.get(name)
        if (
            not isinstance(binding, Mapping)
            or set(binding) != {"commit", "tree"}
            or binding.get("commit") != expected_commit
            or not isinstance(binding.get("tree"), str)
            or _GIT_COMMIT.fullmatch(str(binding.get("tree"))) is None
        ):
            raise PriorExposureRefusal("historical repository binding drifted")
    replay_files = value.get("replay_files")
    if (
        value.get("replay_policy")
        != "COMMIT_BLOBS_PYTHON_ISOLATED_NO_NETWORK_V1"
        or not isinstance(replay_files, list)
        or value.get("replay_file_count") != len(_HISTORICAL_REPLAY_IMPORT_LFP)
        or len(replay_files) != len(_HISTORICAL_REPLAY_IMPORT_LFP)
        or value.get("replay_closure_root_sha256")
        != canonical_sha256(replay_files)
        or not _is_sha256(value.get("replay_result_sha256"))
    ):
        raise PriorExposureRefusal("historical replay authority root drifted")
    observed_paths: list[str] = []
    for entry in replay_files:
        if (
            not isinstance(entry, Mapping)
            or set(entry)
            != {
                "relative_path", "size_bytes", "sha256", "blob_mode", "blob_oid",
            }
            or not isinstance(entry.get("relative_path"), str)
            or isinstance(entry.get("size_bytes"), bool)
            or not isinstance(entry.get("size_bytes"), int)
            or int(entry["size_bytes"]) < 1
            or not _is_sha256(entry.get("sha256"))
            or entry.get("blob_mode") not in {"100644", "100755"}
            or not isinstance(entry.get("blob_oid"), str)
            or _GIT_COMMIT.fullmatch(str(entry.get("blob_oid"))) is None
        ):
            raise PriorExposureRefusal("historical replay file binding drifted")
        observed_paths.append(str(entry["relative_path"]))
    if tuple(observed_paths) != _HISTORICAL_REPLAY_IMPORT_LFP:
        raise PriorExposureRefusal("historical replay import closure drifted")
    python_runtime = value.get("python_runtime")
    if (
        not isinstance(python_runtime, Mapping)
        or set(python_runtime)
        != {
            "implementation", "version", "executable_size_bytes",
            "executable_sha256",
        }
        or not isinstance(python_runtime.get("implementation"), str)
        or not python_runtime.get("implementation")
        or not isinstance(python_runtime.get("version"), str)
        or not python_runtime.get("version")
        or isinstance(python_runtime.get("executable_size_bytes"), bool)
        or not isinstance(python_runtime.get("executable_size_bytes"), int)
        or int(python_runtime["executable_size_bytes"]) < 1
        or not _is_sha256(python_runtime.get("executable_sha256"))
    ):
        raise PriorExposureRefusal("historical Python authority drifted")
    return value


def verify_aborted_attempt_exposure_receipt(
    value: Mapping[str, object],
) -> str:
    """Verify a producer-derived quarantine receipt without reading private blobs."""
    receipt_schema = value.get("schema_version") if isinstance(value, Mapping) else None
    expected_top_level = {
        "schema_version",
        "status",
        "run_identity",
        "termination",
        "source_binding",
        "capture_policy",
        "evidence_bindings",
        "database_snapshots",
        "call_observations",
        "item_run_observations",
        "event_chain",
        "derived_inferences",
        "counts",
        "aggregate",
        "complete",
        "aborted_attempt_exposure_receipt_sha256",
    }
    if receipt_schema == ABORTED_ATTEMPT_EXPOSURE_SCHEMA:
        expected_top_level |= {"assurance", "private_witness_commitment"}
    if not isinstance(value, Mapping) or set(value) != expected_top_level:
        raise PriorExposureRefusal("aborted-attempt receipt shape drifted")
    if (
        receipt_schema
        not in {
            ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V2,
            ABORTED_ATTEMPT_EXPOSURE_SCHEMA,
        }
        or value.get("status") != ABORTED_ATTEMPT_STATUS
        or value.get("complete") is not True
    ):
        raise PriorExposureRefusal("aborted-attempt receipt is not quarantined and complete")

    unsigned = dict(value)
    declared = unsigned.pop("aborted_attempt_exposure_receipt_sha256", None)
    try:
        computed = canonical_sha256(unsigned)
    except Exception as error:
        raise PriorExposureRefusal(
            "aborted-attempt receipt is not canonical JSON"
        ) from error
    if (
        not isinstance(declared, str)
        or not _SHA256.fullmatch(declared)
        or computed != declared
    ):
        raise PriorExposureRefusal("aborted-attempt receipt self-hash drifted")
    if receipt_schema == ABORTED_ATTEMPT_EXPOSURE_SCHEMA:
        commitment = value.get("private_witness_commitment")
        if (
            value.get("assurance") != "PRODUCER_ATTESTED"
            or not isinstance(commitment, Mapping)
            or set(commitment)
            != {
                "schema_version", "algorithm",
                "incident_preimage_root_sha256", "private_witness_sha256",
            }
            or commitment.get("schema_version")
            != ABORTED_ATTEMPT_PRIVATE_WITNESS_SCHEMA
            or commitment.get("algorithm") != "SHA256_CANONICAL_JSON_V1"
            or not _is_sha256(commitment.get("incident_preimage_root_sha256"))
            or not _is_sha256(commitment.get("private_witness_sha256"))
        ):
            raise PriorExposureRefusal("private witness commitment drifted")
        public_preimage = dict(unsigned)
        public_preimage.pop("assurance", None)
        public_preimage.pop("private_witness_commitment", None)
        if canonical_sha256(public_preimage) != commitment.get(
            "incident_preimage_root_sha256"
        ):
            raise PriorExposureRefusal("private witness preimage root drifted")
    run_identity = value.get("run_identity")
    termination = value.get("termination")
    source_binding = value.get("source_binding")
    policy = value.get("capture_policy")
    evidence = value.get("evidence_bindings")
    databases = value.get("database_snapshots")
    calls = value.get("call_observations")
    item_runs = value.get("item_run_observations")
    event_chain = value.get("event_chain")
    derived = value.get("derived_inferences")
    counts = value.get("counts")
    aggregate = value.get("aggregate")
    if not isinstance(run_identity, Mapping) or set(run_identity) != {
        "run_id", "mode", "model", "model_revision", "job_alias",
        "implementation_commit",
        "carrier_commit", "symposium_commit",
    }:
        raise PriorExposureRefusal("aborted-attempt run identity shape drifted")
    if any(
        not isinstance(run_identity.get(key), str) or not run_identity.get(key)
        for key in ("run_id", "mode", "model", "model_revision")
    ) or run_identity.get("job_alias") != "HSWM_F1_R8_V8_DEVELOPMENT_SIGBUS" or any(
        not isinstance(run_identity.get(key), str)
        or _GIT_COMMIT.fullmatch(str(run_identity.get(key))) is None
        for key in ("implementation_commit", "carrier_commit", "symposium_commit")
    ):
        raise PriorExposureRefusal("aborted-attempt run identity drifted")
    if (
        not isinstance(termination, Mapping)
        or set(termination)
        != {
            "evidence_status", "signal", "signal_number", "exit_code",
            "rc_evidence",
        }
        or termination.get("evidence_status") != "OBSERVED_DT_JOB_DIRECTORY"
        or isinstance(termination.get("exit_code"), bool)
        or not isinstance(termination.get("exit_code"), int)
        or isinstance(termination.get("signal_number"), bool)
        or not isinstance(termination.get("signal_number"), int)
        or termination.get("signal_number") != 7
        or termination.get("signal") != "SIGBUS"
        or termination.get("exit_code") != 135
        or int(termination["exit_code"])
        != 128 + int(termination["signal_number"])
    ):
        raise PriorExposureRefusal("aborted-attempt termination drifted")
    expected_signal = _LINUX_SIGNAL_NAMES.get(int(termination["signal_number"]))
    if termination.get("signal") != expected_signal:
        raise PriorExposureRefusal("aborted-attempt signal/exit code disagree")
    rc_evidence = termination.get("rc_evidence")
    if (
        not isinstance(rc_evidence, Mapping)
        or set(rc_evidence) != {"basename", "size_bytes", "sha256"}
        or not isinstance(rc_evidence.get("basename"), str)
        or not rc_evidence.get("basename")
        or isinstance(rc_evidence.get("size_bytes"), bool)
        or not isinstance(rc_evidence.get("size_bytes"), int)
        or int(rc_evidence["size_bytes"]) < 1
        or not isinstance(rc_evidence.get("sha256"), str)
        or _SHA256.fullmatch(str(rc_evidence.get("sha256"))) is None
    ):
        raise PriorExposureRefusal("aborted-attempt exit-code evidence drifted")
    expected_policy = {
        "sqlite_authority_members": ["main", "wal"],
        "sqlite_shm_authoritative": False,
        "response_blob_columns_read": False,
        "item_run_blob_columns_read": False,
        "gold_inputs_accepted": False,
        "model_calls_invoked": False,
        "kg_accessed": False,
        "raw_attempt_states_preserved": True,
    }
    if not _exact_json_equal(policy, expected_policy):
        raise PriorExposureRefusal("aborted-attempt capture policy drifted")
    v2_source_fields = {
        "source_receipt_sha256", "public_source_receipt",
        "manifest_canonical_sha256", "touched_metadata_root_sha256",
    }
    v3_source_fields = v2_source_fields | {
        "public_manifest", "all_metadata_root_sha256",
    }
    expected_source_fields = (
        v2_source_fields
        if receipt_schema == ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V2
        else v3_source_fields
    )
    if (
        not isinstance(source_binding, Mapping)
        or set(source_binding) != expected_source_fields
        or any(
            not _is_sha256(source_binding.get(key))
            for key in (
                "source_receipt_sha256", "manifest_canonical_sha256",
                "touched_metadata_root_sha256",
            )
        )
        or (
            receipt_schema == ABORTED_ATTEMPT_EXPOSURE_SCHEMA
            and not _is_sha256(source_binding.get("all_metadata_root_sha256"))
        )
    ):
        raise PriorExposureRefusal("aborted-attempt source binding drifted")
    public_source_receipt = source_binding.get("public_source_receipt")
    try:
        public_source_sha = verify_public_source_receipt(public_source_receipt)
        if receipt_schema == ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V2:
            authoritative_metadata = _source_receipt_metadata(public_source_receipt)
        else:
            public_manifest = source_binding.get("public_manifest")
            if (
                not isinstance(public_manifest, Mapping)
                or canonical_sha256(public_manifest)
                != source_binding.get("manifest_canonical_sha256")
            ):
                raise PriorExposureRefusal("public manifest authority drifted")
            authoritative_metadata = _source_metadata(
                public_manifest, public_source_receipt
            )
            if canonical_sha256(
                [authoritative_metadata[item] for item in sorted(authoritative_metadata)]
            ) != source_binding.get("all_metadata_root_sha256"):
                raise PriorExposureRefusal("global public metadata root drifted")
    except Exception as error:
        raise PriorExposureRefusal(
            "aborted-attempt public source authority drifted"
        ) from error
    if public_source_sha != source_binding.get("source_receipt_sha256"):
        raise PriorExposureRefusal(
            "aborted-attempt public source authority hash drifted"
        )
    v2_evidence_fields = {
        "artifacts", "repositories", "producer_dependencies", "job_command", "job_log",
    }
    v3_evidence_fields = {
        "artifacts", "historical_runtime_authority", "current_producer_authority",
        "job_command", "job_log",
    }
    if not isinstance(evidence, Mapping) or set(evidence) != (
        v2_evidence_fields
        if receipt_schema == ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V2
        else v3_evidence_fields
    ):
        raise PriorExposureRefusal("aborted-attempt evidence inventory drifted")
    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, Mapping) or set(artifacts) != set(
        _ARTIFACT_SELF_HASH_FIELDS
    ):
        raise PriorExposureRefusal("aborted-attempt artifact inventory drifted")
    for name, artifact in artifacts.items():
        if not isinstance(artifact, Mapping) or set(artifact) != {
            "basename", "size_bytes", "raw_sha256", "canonical_sha256",
            "schema_version", "declared_hashes",
        }:
            raise PriorExposureRefusal("aborted-attempt artifact binding shape drifted")
        declared_hashes = artifact.get("declared_hashes")
        if (
            not isinstance(artifact.get("basename"), str)
            or not artifact.get("basename")
            or isinstance(artifact.get("size_bytes"), bool)
            or not isinstance(artifact.get("size_bytes"), int)
            or int(artifact["size_bytes"]) < 1
            or not _is_sha256(artifact.get("raw_sha256"))
                or not _is_sha256(artifact.get("canonical_sha256"))
                or artifact.get("schema_version")
                != _INCIDENT_ARTIFACT_SCHEMAS[str(name)]
            or not isinstance(declared_hashes, Mapping)
            or set(declared_hashes) != set(_ARTIFACT_SELF_HASH_FIELDS[str(name)])
            or any(not _is_sha256(item) for item in declared_hashes.values())
        ):
            raise PriorExposureRefusal("aborted-attempt artifact binding drifted")
    if receipt_schema == ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V2:
        repositories = evidence.get("repositories")
    else:
        historical_runtime = _verify_historical_runtime_authority(
            evidence.get("historical_runtime_authority")
        )
        repositories = historical_runtime.get("repositories")
    if not isinstance(repositories, Mapping) or set(repositories) != {
        "hswm_executable", "hswm_carrier", "symposium",
    }:
        raise PriorExposureRefusal("aborted-attempt repository inventory drifted")
    for repository in repositories.values():
        if (
            not isinstance(repository, Mapping)
            or set(repository) != {"commit", "tree"}
            or any(
                not isinstance(repository.get(key), str)
                or _GIT_COMMIT.fullmatch(str(repository.get(key))) is None
                for key in ("commit", "tree")
            )
        ):
            raise PriorExposureRefusal("aborted-attempt repository binding drifted")
    if (
        run_identity.get("implementation_commit")
        != repositories["hswm_executable"]["commit"]
        or run_identity.get("carrier_commit")
        != repositories["hswm_carrier"]["commit"]
        or run_identity.get("symposium_commit")
        != repositories["symposium"]["commit"]
    ):
        raise PriorExposureRefusal("aborted-attempt repository identity drifted")
    if receipt_schema == ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V2:
        producer_dependencies = evidence.get("producer_dependencies")
        if not isinstance(producer_dependencies, Mapping) or set(
            producer_dependencies
        ) != {
            "prom9_f1_prior_exposure.py", "hswm_function_network.py",
            "hswm_function_registry.py", "hswm_typed_ports.py",
            "prom_f1_function_network.py", "prom9_protocol.py",
            "prom9_prepare_2wiki_f1.py", "prom9_f1_r8_source.py",
            "prom9_f1_r8_environment.py", "model_deployment_receipt.py",
            "bge_m3_embed.py",
        }:
            raise PriorExposureRefusal("aborted-attempt producer inventory drifted")
        for dependency_name, dependency in producer_dependencies.items():
            _verify_recorded_file(
                dependency,
                fields={"basename", "size_bytes", "sha256"},
                label="producer dependency",
            )
            if dependency.get("basename") != dependency_name:
                raise PriorExposureRefusal("producer dependency basename drifted")
    else:
        _verify_current_producer_authority(evidence.get("current_producer_authority"))
    for label in ("job_command", "job_log"):
        _verify_recorded_file(
            evidence.get(label),
            fields={"basename", "size_bytes", "sha256"},
            label=label.replace("_", " "),
        )
    if (
        source_binding.get("source_receipt_sha256")
        != artifacts["source_receipt"]["declared_hashes"].get(
            "source_receipt_sha256"
        )
        or source_binding.get("manifest_canonical_sha256")
        != artifacts["manifest"]["canonical_sha256"]
    ):
        raise PriorExposureRefusal("aborted-attempt source/artifact binding drifted")
    if not isinstance(databases, Mapping) or set(databases) != {"attempt", "spool"}:
        raise PriorExposureRefusal("aborted-attempt database snapshot inventory drifted")
    for database_name, database in databases.items():
        if not isinstance(database, Mapping) or set(database) != {
            "authority_members", "members", "authority_root_sha256", "integrity",
            "journal_mode", "user_version", "schema_sha256",
            "canonical_schema_sha256",
        }:
            raise PriorExposureRefusal("aborted-attempt database snapshot shape drifted")
        members = database.get("members")
        if (
            database.get("authority_members") != ["main", "wal"]
            or not isinstance(members, Mapping)
            or set(members) != {"main", "wal"}
            or database.get("authority_root_sha256") != canonical_sha256(members)
            or database.get("integrity") != "ok"
            or database.get("journal_mode") != "wal"
            or database.get("user_version") != 1
            or not isinstance(database.get("schema_sha256"), str)
            or _SHA256.fullmatch(str(database.get("schema_sha256"))) is None
            or database.get("canonical_schema_sha256")
            != (
                _ABORTED_ATTEMPT_V2_CANONICAL_SCHEMA_SHA256[database_name]
                if receipt_schema == ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V2
                else canonical_schema_sha256(
                    _HISTORICAL_V8_SCHEMA_AUTHORITIES[database_name]
                )
            )
        ):
            raise PriorExposureRefusal("aborted-attempt database snapshot drifted")
        for member in members.values():
            if (
                not isinstance(member, Mapping)
                or set(member) != {"basename", "size_bytes", "sha256"}
                or not isinstance(member.get("basename"), str)
                or "shm" in str(member.get("basename")).casefold()
                or isinstance(member.get("size_bytes"), bool)
                or not isinstance(member.get("size_bytes"), int)
                or int(member["size_bytes"]) < 0
                or not isinstance(member.get("sha256"), str)
                or _SHA256.fullmatch(str(member.get("sha256"))) is None
            ):
                raise PriorExposureRefusal("aborted-attempt SQLite member drifted")
        expected_basenames = {
            "main": f"{database_name}.sqlite3",
            "wal": f"{database_name}.sqlite3-wal",
        }
        if any(
            members[key].get("basename") != expected
            for key, expected in expected_basenames.items()
        ):
            raise PriorExposureRefusal("aborted-attempt SQLite basename drifted")
    if (
        not isinstance(calls, list)
        or not calls
        or not isinstance(item_runs, list)
        or not isinstance(event_chain, Mapping)
        or not isinstance(derived, list)
        or not isinstance(counts, Mapping)
    ):
        raise PriorExposureRefusal("aborted-attempt observation inventory drifted")
    call_fields = {
        "physical_call_id", "run_id", "arm_id", "item_id", "call_index",
        "function_id", "model", "model_revision", "input_type", "output_type",
        "max_output_tokens", "dataset_row_index", "question_sha256",
        "source_entity_ids", "component_id", "intent_sha256", "request_sha256",
        "raw_attempt_state", "response_status", "response_sha256",
        "model_response_sha256", "call_receipt_sha256", "terminal_code",
        "spool_snapshot_state", "spool_response_status", "spool_response_sha256",
    }
    call_ids: set[str] = set()
    call_items: set[str] = set()
    call_sources: set[str] = set()
    call_components: set[str] = set()
    metadata_by_item: dict[str, dict[str, object]] = {}
    call_order: list[tuple[str, int, int]] = []
    state_counts: dict[str, int] = {}
    spool_complete = 0
    spool_absent = 0
    for call in calls:
        if not isinstance(call, Mapping) or set(call) != call_fields:
            raise PriorExposureRefusal("aborted-attempt call observation shape drifted")
        physical = call.get("physical_call_id")
        item_id = call.get("item_id")
        sources = call.get("source_entity_ids")
        component = call.get("component_id")
        state = call.get("raw_attempt_state")
        if (
            not isinstance(physical, str)
            or _SHA256.fullmatch(physical) is None
            or physical in call_ids
            or not isinstance(item_id, str)
            or not item_id
            or call.get("arm_id") not in _F1_ARMS
            or not isinstance(sources, list)
            or sources != sorted(set(sources))
            or any(not isinstance(source, str) or _SHA256.fullmatch(source) is None for source in sources)
            or not isinstance(component, str)
            or _SHA256.fullmatch(component) is None
            or state not in _EVENT_TRANSITIONS
            or state == "SENT_NOT_UPSTREAM"
            or not _valid_call_observation_scalars(call)
            or call.get("run_id") != run_identity.get("run_id")
            or call.get("model") != run_identity.get("model")
            or call.get("model_revision") != run_identity.get("model_revision")
        ):
            raise PriorExposureRefusal("aborted-attempt call observation drifted")
        if any(
            not _is_sha256(call.get(field))
            for field in ("question_sha256", "intent_sha256", "request_sha256")
        ):
            raise PriorExposureRefusal("aborted-attempt required call digest drifted")
        expected_contract = _CALL_CONTRACTS[int(call["call_index"])]
        if (
            call.get("function_id"),
            call.get("input_type"),
            call.get("output_type"),
        ) != expected_contract:
            raise PriorExposureRefusal("aborted-attempt call contract drifted")
        for field in (
            "response_sha256", "model_response_sha256", "call_receipt_sha256",
            "spool_response_sha256",
        ):
            candidate = call.get(field)
            if candidate is not None and (
                not isinstance(candidate, str) or _SHA256.fullmatch(candidate) is None
            ):
                raise PriorExposureRefusal("aborted-attempt call digest drifted")
        response_status = call.get("response_status")
        spool_response_status = call.get("spool_response_status")
        terminal_code = call.get("terminal_code")
        if (
            response_status is not None
            and (
                isinstance(response_status, bool)
                or not isinstance(response_status, int)
                or not 100 <= response_status <= 599
            )
        ) or (
            spool_response_status is not None
            and (
                isinstance(spool_response_status, bool)
                or not isinstance(spool_response_status, int)
                or not 100 <= spool_response_status <= 599
            )
        ) or (
            terminal_code is not None
            and (not isinstance(terminal_code, str) or not terminal_code)
        ):
            raise PriorExposureRefusal("aborted-attempt call terminal metadata drifted")
        spool_state = call.get("spool_snapshot_state")
        if spool_state is None:
            spool_absent += 1
            if spool_response_status is not None or call.get("spool_response_sha256") is not None:
                raise PriorExposureRefusal("absent spool row exposes response metadata")
        elif spool_state == "COMPLETE":
            spool_complete += 1
            if (
                spool_response_status is None
                or not _is_sha256(call.get("spool_response_sha256"))
                or (
                    (response_status is not None or call.get("response_sha256") is not None)
                    and (
                        spool_response_status != response_status
                        or call.get("spool_response_sha256")
                        != call.get("response_sha256")
                    )
                )
            ):
                raise PriorExposureRefusal("aborted-attempt complete spool binding drifted")
        elif spool_state in {"DISPATCHING", "UNKNOWN"}:
            if (
                spool_response_status is not None
                or call.get("spool_response_sha256") is not None
            ):
                raise PriorExposureRefusal(
                    "non-complete spool row exposes response metadata"
                )
        else:
            raise PriorExposureRefusal("aborted-attempt spool state drifted")
        response_sha = call.get("response_sha256")
        model_sha = call.get("model_response_sha256")
        receipt_sha = call.get("call_receipt_sha256")
        response_present = response_status is not None and _is_sha256(response_sha)
        if (response_status is None) != (response_sha is None):
            raise PriorExposureRefusal("attempt response scalar pair drifted")
        response_required = state in {
            "RAW_COMPLETE", "ENVELOPE_VALID", "SCHEMA_VALID", "ACCEPTED",
            "REJECTED_PROTOCOL",
        }
        if response_present != response_required:
            raise PriorExposureRefusal("attempt response presence differs from state")
        if model_sha is not None and not response_present:
            raise PriorExposureRefusal("model response lacks raw response binding")
        if (state == "ACCEPTED") != (receipt_sha is not None):
            raise PriorExposureRefusal("call receipt terminal-state binding drifted")
        if (state in {"REJECTED_PROTOCOL", "AMBIGUOUS_ABORT"}) != (
            terminal_code is not None
        ):
            raise PriorExposureRefusal("terminal code state binding drifted")
        if state in {"SCHEMA_VALID", "ACCEPTED"} and not _is_sha256(model_sha):
            raise PriorExposureRefusal("schema-valid state lacks model response")
        if state in {
            "PREPARED", "SENT", "DELIVERY_AMBIGUOUS", "AMBIGUOUS_ABORT",
            "RAW_COMPLETE", "ENVELOPE_VALID",
        } and model_sha is not None:
            raise PriorExposureRefusal("pre-schema state contains model metadata")
        item_metadata = {
            "item_id": item_id,
            "dataset_row_index": call["dataset_row_index"],
            "question_sha256": call["question_sha256"],
            "source_entity_ids": list(sources),
            "component_id": component,
        }
        if item_id in metadata_by_item and metadata_by_item[item_id] != item_metadata:
            raise PriorExposureRefusal("aborted-attempt item metadata conflicts")
        metadata_by_item[item_id] = item_metadata
        call_order.append(
            (
                item_id,
                _F1_ARMS.index(str(call["arm_id"])),
                int(call["call_index"]),
            )
        )
        call_ids.add(physical)
        call_items.add(item_id)
        call_sources.update(str(source) for source in sources)
        call_components.add(component)
        state_counts[str(state)] = state_counts.get(str(state), 0) + 1
    if call_order != sorted(call_order) or len(set(call_order)) != len(call_order):
        raise PriorExposureRefusal("aborted-attempt call ordering drifted")
    call_groups: dict[tuple[str, str], list[Mapping[str, object]]] = {}
    for call in calls:
        key = (str(call["item_id"]), str(call["arm_id"]))
        call_groups.setdefault(key, []).append(call)
    for group in call_groups.values():
        indices = [int(call["call_index"]) for call in group]
        if indices != list(range(1, max(indices) + 1)):
            raise PriorExposureRefusal("aborted-attempt call sequence is not a prefix")
    item_run_items: set[str] = set()
    item_run_order: list[tuple[str, int]] = []
    item_run_keys: set[tuple[str, str]] = set()
    for item_run in item_runs:
        if not isinstance(item_run, Mapping) or set(item_run) != {
            "run_id", "arm_id", "item_id", "run_receipt_sha256",
            "dataset_row_index", "question_sha256", "source_entity_ids",
            "component_id",
        }:
            raise PriorExposureRefusal("aborted-attempt item-run observation drifted")
        item_run_sources = item_run.get("source_entity_ids")
        if (
            item_run.get("run_id") != run_identity.get("run_id")
            or not isinstance(item_run.get("arm_id"), str)
            or item_run.get("arm_id") not in _F1_ARMS
            or not isinstance(item_run.get("item_id"), str)
            or not item_run.get("item_id")
            or not _is_sha256(item_run.get("run_receipt_sha256"))
            or isinstance(item_run.get("dataset_row_index"), bool)
            or not isinstance(item_run.get("dataset_row_index"), int)
            or int(item_run["dataset_row_index"]) < 0
            or not _is_sha256(item_run.get("question_sha256"))
            or not isinstance(item_run_sources, list)
            or item_run_sources != sorted(set(item_run_sources))
            or any(not _is_sha256(source) for source in item_run_sources)
            or not _is_sha256(item_run.get("component_id"))
        ):
            raise PriorExposureRefusal("aborted-attempt item-run identity drifted")
        item_run_item = str(item_run["item_id"])
        item_run_metadata = {
            "item_id": item_run_item,
            "dataset_row_index": item_run["dataset_row_index"],
            "question_sha256": item_run["question_sha256"],
            "source_entity_ids": list(item_run_sources),
            "component_id": item_run["component_id"],
        }
        if (
            item_run_item in metadata_by_item
            and metadata_by_item[item_run_item] != item_run_metadata
        ):
            raise PriorExposureRefusal("aborted-attempt item-run metadata conflicts")
        metadata_by_item[item_run_item] = item_run_metadata
        item_run_key = (item_run_item, str(item_run["arm_id"]))
        if item_run_key in item_run_keys:
            raise PriorExposureRefusal("aborted-attempt item-run identity repeats")
        item_run_keys.add(item_run_key)
        item_run_calls = call_groups.get(item_run_key, [])
        if (
            [int(call["call_index"]) for call in item_run_calls] != [1, 2, 3]
            or any(call["raw_attempt_state"] != "ACCEPTED" for call in item_run_calls)
        ):
            raise PriorExposureRefusal("item run lacks three accepted calls")
        item_run_items.add(item_run_item)
        call_sources.update(str(source) for source in item_run_sources)
        call_components.add(str(item_run["component_id"]))
        item_run_order.append(
            (
                item_run_item,
                _F1_ARMS.index(str(item_run["arm_id"])),
            )
        )
    if item_run_order != sorted(item_run_order) or len(set(item_run_order)) != len(
        item_run_order
    ):
        raise PriorExposureRefusal("aborted-attempt item-run ordering drifted")
    if any(
        item not in authoritative_metadata
        or metadata_by_item[item] != authoritative_metadata[item]
        for item in metadata_by_item
    ):
        raise PriorExposureRefusal(
            "aborted-attempt metadata differs from public source authority"
        )
    component_by_source: dict[str, str] = {}
    for item_id in sorted(metadata_by_item):
        metadata = metadata_by_item[item_id]
        component_id = str(metadata["component_id"])
        for source_id in metadata["source_entity_ids"]:
            prior_component = component_by_source.setdefault(
                str(source_id), component_id
            )
            if prior_component != component_id:
                raise PriorExposureRefusal(
                    "shared source entity crosses incident components"
                )
    expected_terminal_states = {
        key: next(
            str(call["raw_attempt_state"])
            for call in calls
            if call["physical_call_id"] == key
        )
        for key in sorted(call_ids)
    }
    per_call_event_counts = event_chain.get("per_call_event_counts")
    if (
        set(event_chain)
        != {
            "event_count", "event_chain_tip_sha256", "per_call_event_counts",
            "per_call_terminal_states",
        }
        or isinstance(event_chain.get("event_count"), bool)
        or not isinstance(event_chain.get("event_count"), int)
        or int(event_chain["event_count"]) < len(call_ids)
        or not _is_sha256(event_chain.get("event_chain_tip_sha256"))
        or not isinstance(per_call_event_counts, Mapping)
        or set(per_call_event_counts) != call_ids
        or any(
            isinstance(count, bool) or not isinstance(count, int) or count < 1
            for count in per_call_event_counts.values()
        )
        or sum(int(count) for count in per_call_event_counts.values())
        != event_chain.get("event_count")
        or event_chain.get("per_call_terminal_states") != expected_terminal_states
    ):
        raise PriorExposureRefusal("aborted-attempt event summary drifted")
    expected_count_keys = {
        "attempt_calls", "attempt_events", "item_runs", "spool_calls",
        "attempt_states", "spool_complete_calls", "spool_absent_calls",
        "items", "source_entities", "components",
    }
    numeric_count_keys = expected_count_keys - {"attempt_states"}
    if (
        set(counts) != expected_count_keys
        or any(
            isinstance(counts.get(key), bool)
            or not isinstance(counts.get(key), int)
            or int(counts[key]) < 0
            for key in numeric_count_keys
        )
        or counts.get("attempt_calls") != len(calls)
        or counts.get("attempt_events") != event_chain.get("event_count")
        or counts.get("item_runs") != len(item_runs)
        or counts.get("spool_calls")
        != sum(call.get("spool_snapshot_state") is not None for call in calls)
        or counts.get("attempt_states")
        != {key: state_counts[key] for key in sorted(state_counts)}
        or counts.get("spool_complete_calls") != spool_complete
        or counts.get("spool_absent_calls") != spool_absent
    ):
        raise PriorExposureRefusal("aborted-attempt observation counts drifted")
    calls_by_id = {str(call["physical_call_id"]): call for call in calls}
    inferred_absent: set[str] = set()
    for inference in derived:
        if (
            not isinstance(inference, Mapping)
            or set(inference)
            != {
                "claim", "epistemic_status", "physical_call_id",
                "raw_attempt_state",
            }
            or inference.get("claim") != "MATCHING_SPOOL_ROW_ABSENT"
            or inference.get("epistemic_status")
            != "DERIVED_FROM_BOUND_SNAPSHOTS"
            or inference.get("physical_call_id") not in calls_by_id
            or inference.get("raw_attempt_state")
            != calls_by_id[str(inference.get("physical_call_id"))].get(
                "raw_attempt_state"
            )
        ):
            raise PriorExposureRefusal("aborted-attempt derived inference drifted")
        inferred_absent.add(str(inference["physical_call_id"]))
    expected_absent = {
        str(call["physical_call_id"])
        for call in calls
        if call["spool_snapshot_state"] is None
    }
    if inferred_absent != expected_absent or len(derived) != len(expected_absent):
        raise PriorExposureRefusal("aborted-attempt derived inference drifted")
    if not isinstance(aggregate, Mapping) or set(aggregate) != {
        "prior_item_ids",
        "prior_source_entity_ids",
        "prior_component_ids",
        "item_root_sha256",
        "source_entity_root_sha256",
        "component_root_sha256",
    }:
        raise PriorExposureRefusal("aborted-attempt aggregate shape drifted")
    item_ids = _strict_boundary_values(aggregate, "prior_item_ids", "item ids")
    source_entity_ids = _strict_boundary_values(
        aggregate, "prior_source_entity_ids", "source entity ids"
    )
    component_ids = _strict_boundary_values(
        aggregate, "prior_component_ids", "component ids"
    )
    if (
        set(item_ids) != call_items | item_run_items
        or set(metadata_by_item) != set(item_ids)
        or set(source_entity_ids) != call_sources
        or set(component_ids) != call_components
    ):
        raise PriorExposureRefusal("aborted-attempt aggregate exposure drifted")
    if source_binding.get("touched_metadata_root_sha256") != canonical_sha256(
        [metadata_by_item[item] for item in sorted(metadata_by_item)]
    ):
        raise PriorExposureRefusal("aborted-attempt touched metadata root drifted")
    for values, root_key in (
        (item_ids, "item_root_sha256"),
        (source_entity_ids, "source_entity_root_sha256"),
        (component_ids, "component_root_sha256"),
    ):
        if canonical_sha256(values) != aggregate.get(root_key):
            raise PriorExposureRefusal("aborted-attempt aggregate root drifted")
    if (
        counts["items"] != len(item_ids)
        or counts["source_entities"] != len(source_entity_ids)
        or counts["components"] != len(component_ids)
    ):
        raise PriorExposureRefusal("aborted-attempt aggregate count drifted")
    return declared


def _verify_private_database_generation(
    value: object, label: str
) -> Mapping[str, object]:
    members = {"main", "wal", "shm", "journal"}
    generation_fields = {
        "st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns",
        "sha256",
    }
    if not isinstance(value, Mapping) or set(value) != members:
        raise PriorExposureRefusal(f"{label} generation shape drifted")
    for member in sorted(members):
        observed = value.get(member)
        if observed is None and member != "main":
            continue
        if (
            not isinstance(observed, Mapping)
            or set(observed) != generation_fields
            or any(
                isinstance(observed.get(key), bool)
                or not isinstance(observed.get(key), int)
                or int(observed[key]) < minimum
                for key, minimum in (
                    ("st_dev", 0),
                    ("st_ino", 1),
                    ("st_size", 0),
                    ("st_mtime_ns", 0),
                    ("st_ctime_ns", 0),
                )
            )
            or not _is_sha256(observed.get("sha256"))
        ):
            raise PriorExposureRefusal(
                f"{label} {member} generation drifted"
            )
    return value


def _verify_private_database_witness(
    value: object, label: str
) -> Mapping[str, object]:
    fields = {
        "resolved_path", "st_dev", "st_ino", "mode", "uid", "nlink",
        "size_bytes", "mtime_ns", "ctime_ns", "generation",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise PriorExposureRefusal(f"{label} private witness shape drifted")
    resolved_path = value.get("resolved_path")
    if (
        not isinstance(resolved_path, str)
        or not Path(resolved_path).is_absolute()
        or value.get("mode") != "0o600"
        or value.get("uid") != os.geteuid()
        or value.get("nlink") != 1
        or any(
            isinstance(value.get(key), bool)
            or not isinstance(value.get(key), int)
            or int(value[key]) < minimum
            for key, minimum in (
                ("st_dev", 0),
                ("st_ino", 1),
                ("size_bytes", 0),
                ("mtime_ns", 0),
                ("ctime_ns", 0),
            )
        )
    ):
        raise PriorExposureRefusal(f"{label} private witness identity drifted")
    generation = _verify_private_database_generation(
        value.get("generation"), label
    )
    main = generation.get("main")
    assert isinstance(main, Mapping)
    if any(
        main.get(generation_key) != value.get(witness_key)
        for generation_key, witness_key in (
            ("st_dev", "st_dev"),
            ("st_ino", "st_ino"),
            ("st_size", "size_bytes"),
            ("st_mtime_ns", "mtime_ns"),
            ("st_ctime_ns", "ctime_ns"),
        )
    ):
        raise PriorExposureRefusal(f"{label} main generation identity drifted")
    return value


def verify_aborted_attempt_private_witness(
    public_receipt: Mapping[str, object], witness_path: Path
) -> str:
    """Privileged verification of raw SQLite identities kept outside Git."""

    verify_aborted_attempt_exposure_receipt(public_receipt)
    if public_receipt.get("schema_version") != ABORTED_ATTEMPT_EXPOSURE_SCHEMA:
        raise PriorExposureRefusal("private witness requires a v3 public receipt")
    witness = _strict_object(
        _read_private_bytes(Path(witness_path)), "aborted-attempt private witness"
    )
    witness_fields = {
        "schema_version", "nonce_hex", "incident_preimage_root_sha256",
        "stage_path", "databases", "db_genesis_receipt",
        "spool_identity_receipt", "private_witness_sha256",
    }
    if (
        set(witness) != witness_fields
        or witness.get("schema_version")
        != ABORTED_ATTEMPT_PRIVATE_WITNESS_SCHEMA
        or not isinstance(witness.get("nonce_hex"), str)
        or _SHA256.fullmatch(str(witness.get("nonce_hex"))) is None
    ):
        raise PriorExposureRefusal("private witness shape drifted")
    _verify_self_hash_mapping(
        witness, "private_witness_sha256", "private witness"
    )
    commitment = public_receipt.get("private_witness_commitment")
    assert isinstance(commitment, Mapping)
    if (
        witness.get("incident_preimage_root_sha256")
        != commitment.get("incident_preimage_root_sha256")
        or witness.get("private_witness_sha256")
        != commitment.get("private_witness_sha256")
    ):
        raise PriorExposureRefusal("private witness commitment mismatch")

    stage_text = witness.get("stage_path")
    if not isinstance(stage_text, str) or not Path(stage_text).is_absolute():
        raise PriorExposureRefusal("private witness stage path drifted")
    stage_path = Path(stage_text)
    try:
        stage_info = stage_path.lstat()
        canonical_stage = stage_path.resolve(strict=True)
    except OSError as error:
        raise PriorExposureRefusal("private witness stage is unavailable") from error
    if (
        canonical_stage != stage_path
        or stat.S_ISLNK(stage_info.st_mode)
        or not stat.S_ISDIR(stage_info.st_mode)
        or stat.S_IMODE(stage_info.st_mode) != 0o700
        or stage_info.st_uid != os.geteuid()
    ):
        raise PriorExposureRefusal("private witness stage identity drifted")
    databases = witness.get("databases")
    if not isinstance(databases, Mapping) or set(databases) != {"attempt", "spool"}:
        raise PriorExposureRefusal("private witness database roles drifted")
    attempt = _verify_private_database_witness(
        databases.get("attempt"), "attempt database"
    )
    spool = _verify_private_database_witness(
        databases.get("spool"), "spool database"
    )
    for database in (attempt, spool):
        database_path = Path(str(database["resolved_path"]))
        try:
            canonical_database_path = database_path.resolve(strict=True)
        except OSError as error:
            raise PriorExposureRefusal(
                "private database path is unavailable"
            ) from error
        if canonical_database_path != database_path:
            raise PriorExposureRefusal("private database path is not canonical")
        try:
            database_path.relative_to(stage_path)
        except ValueError as error:
            raise PriorExposureRefusal(
                "private database is outside the incident stage"
            ) from error
        if database_path == stage_path:
            raise PriorExposureRefusal("private database path is not a file child")
        if database_path.parent.parent != stage_path:
            raise PriorExposureRefusal(
                "private database does not identify the exact incident stage"
            )
    if (
        attempt["resolved_path"] == spool["resolved_path"]
        or (attempt["st_dev"], attempt["st_ino"])
        == (spool["st_dev"], spool["st_ino"])
    ):
        raise PriorExposureRefusal("private database identities alias")

    genesis = witness.get("db_genesis_receipt")
    if (
        not isinstance(genesis, Mapping)
        or set(genesis) != _INCIDENT_GENESIS_FIELDS
        or genesis.get("schema_version")
        != _INCIDENT_ARTIFACT_SCHEMAS["db_genesis_receipt"]
    ):
        raise PriorExposureRefusal("private genesis receipt shape drifted")
    _verify_self_hash_mapping(genesis, "genesis_sha256", "private genesis")
    expected_attempt_identity = {
        "resolved_path": attempt["resolved_path"],
        "st_dev": attempt["st_dev"],
        "st_ino": attempt["st_ino"],
    }
    expected_spool_identity = {
        "resolved_path": spool["resolved_path"],
        "st_dev": spool["st_dev"],
        "st_ino": spool["st_ino"],
    }
    if (
        genesis.get("attempt_db_identity") != expected_attempt_identity
        or genesis.get("spool_db_identity") != expected_spool_identity
    ):
        raise PriorExposureRefusal("private genesis database roles drifted")

    preflight = witness.get("spool_identity_receipt")
    if (
        not isinstance(preflight, Mapping)
        or set(preflight) != _INCIDENT_SPOOL_PREFLIGHT_FIELDS
        or preflight.get("schema_version")
        != _INCIDENT_ARTIFACT_SCHEMAS["spool_identity_receipt"]
    ):
        raise PriorExposureRefusal("private spool preflight shape drifted")
    _verify_self_hash_mapping(
        preflight, "preflight_sha256", "private spool preflight"
    )
    endpoint_identity = preflight.get("endpoint_identity")
    if (
        not isinstance(endpoint_identity, Mapping)
        or set(endpoint_identity) != _INCIDENT_SPOOL_IDENTITY_FIELDS
    ):
        raise PriorExposureRefusal("private spool endpoint identity drifted")
    _verify_self_hash_mapping(
        endpoint_identity, "identity_sha256", "private spool endpoint identity"
    )
    audit = endpoint_identity.get("audit")
    if not isinstance(audit, Mapping) or set(audit) != _INCIDENT_SPOOL_AUDIT_FIELDS:
        raise PriorExposureRefusal("private spool audit shape drifted")
    _verify_self_hash_mapping(audit, "audit_sha256", "private spool audit")
    if endpoint_identity.get("db_identity") != expected_spool_identity:
        raise PriorExposureRefusal("private spool preflight role drifted")

    evidence = public_receipt.get("evidence_bindings")
    public_databases = public_receipt.get("database_snapshots")
    run_identity = public_receipt.get("run_identity")
    assert isinstance(evidence, Mapping)
    assert isinstance(public_databases, Mapping)
    assert isinstance(run_identity, Mapping)
    artifacts = evidence.get("artifacts")
    assert isinstance(artifacts, Mapping)
    for artifact_name, preimage, self_hash_field in (
        ("db_genesis_receipt", genesis, "genesis_sha256"),
        ("spool_identity_receipt", preflight, "preflight_sha256"),
    ):
        binding = artifacts.get(artifact_name)
        if not isinstance(binding, Mapping):
            raise PriorExposureRefusal("private artifact binding is absent")
        declared_hashes = binding.get("declared_hashes")
        if (
            not isinstance(declared_hashes, Mapping)
            or canonical_sha256(preimage) != binding.get("canonical_sha256")
            or declared_hashes.get(self_hash_field)
            != preimage.get(self_hash_field)
        ):
            raise PriorExposureRefusal("private artifact preimage binding drifted")

    for role, private_database in (("attempt", attempt), ("spool", spool)):
        public_database = public_databases.get(role)
        if not isinstance(public_database, Mapping):
            raise PriorExposureRefusal("public database role is absent")
        public_members = public_database.get("members")
        private_generation = private_database.get("generation")
        assert isinstance(private_generation, Mapping)
        if not isinstance(public_members, Mapping):
            raise PriorExposureRefusal("public database members are absent")
        for member_name in ("main", "wal"):
            public_member = public_members.get(member_name)
            private_member = private_generation.get(member_name)
            if (
                not isinstance(public_member, Mapping)
                or not isinstance(private_member, Mapping)
                or private_member.get("st_size")
                != public_member.get("size_bytes")
                or private_member.get("sha256") != public_member.get("sha256")
            ):
                raise PriorExposureRefusal(
                    "private database generation differs from public snapshot"
                )
        if (
            genesis.get(f"{role}_schema_sha256")
            != public_database.get("schema_sha256")
            or genesis.get(f"{role}_journal_mode")
            != public_database.get("journal_mode")
            or genesis.get(f"{role}_user_version")
            != public_database.get("user_version")
        ):
            raise PriorExposureRefusal(
                "private genesis differs from public database authority"
            )

    execution_lock_binding = artifacts.get("execution_lock")
    deployment_binding = artifacts.get("model_deployment_receipt")
    assert isinstance(execution_lock_binding, Mapping)
    assert isinstance(deployment_binding, Mapping)
    execution_lock_hashes = execution_lock_binding.get("declared_hashes")
    deployment_hashes = deployment_binding.get("declared_hashes")
    if (
        genesis.get("run_id") != run_identity.get("run_id")
        or preflight.get("run_id") != run_identity.get("run_id")
        or preflight.get("model_revision") != run_identity.get("model_revision")
        or preflight.get("served_model") != run_identity.get("model")
        or preflight.get("db_genesis_sha256") != genesis.get("genesis_sha256")
        or not isinstance(execution_lock_hashes, Mapping)
        or preflight.get("execution_lock_sha256")
        != execution_lock_hashes.get("lock_sha256")
        or not isinstance(deployment_hashes, Mapping)
        or preflight.get("deployment_receipt_sha256")
        != deployment_hashes.get("receipt_sha256")
        or endpoint_identity.get("model_revision")
        != preflight.get("model_revision")
        or endpoint_identity.get("served_model") != preflight.get("served_model")
        or endpoint_identity.get("deployment_id")
        != preflight.get("deployment_id")
        or endpoint_identity.get("deployment_receipt_sha256")
        != preflight.get("deployment_receipt_sha256")
        or endpoint_identity.get("normalized_upstream_endpoint")
        != preflight.get("upstream_endpoint")
    ):
        raise PriorExposureRefusal(
            "private witness differs from public run authority"
        )

    for database, label in ((attempt, "attempt database"), (spool, "spool database")):
        try:
            live_generation = database_generation(
                Path(str(database["resolved_path"])), label
            )
        except SQLiteAuthorityRefusal as error:
            raise PriorExposureRefusal(
                f"{label} live generation cannot be verified"
            ) from error
        if not _exact_json_equal(live_generation, database["generation"]):
            raise PriorExposureRefusal(f"{label} live generation drifted")
    return "RAW_WITNESS_VERIFIED"


def verify_forbidden_exposure_union(
    prior: Mapping[str, object],
    incident: Mapping[str, object],
    execution_lock: Mapping[str, object],
) -> dict[str, object]:
    """Require the lock's forbidden boundary to equal the two receipt union."""

    merged = merge_exposure_boundaries(prior, incident)
    if (
        execution_lock.get("prior_exposure_receipt_sha256")
        != merged["prior_exposure_receipt_sha256"]
        or execution_lock.get("aborted_attempt_exposure_receipt_sha256")
        != merged["aborted_attempt_exposure_receipt_sha256"]
        or execution_lock.get("forbidden_prior_item_ids") != merged["item_ids"]
        or execution_lock.get("forbidden_prior_source_entity_ids")
        != merged["source_entity_ids"]
        or execution_lock.get("forbidden_prior_component_ids")
        != merged["component_ids"]
    ):
        raise PriorExposureRefusal("execution-lock forbidden exposure union drifted")
    return merged


def merge_exposure_boundaries(
    prior: Mapping[str, object], incident: Mapping[str, object]
) -> dict[str, object]:
    """Return the canonical union of historical and aborted-attempt exposure."""
    prior_sha = verify_prior_exposure_receipt(prior)
    incident_sha = verify_aborted_attempt_exposure_receipt(incident)
    prior_aggregate = prior.get("aggregate")
    incident_aggregate = incident.get("aggregate")
    if not isinstance(prior_aggregate, Mapping) or not isinstance(
        incident_aggregate, Mapping
    ):
        raise PriorExposureRefusal("exposure aggregate is absent")

    def merged(key: str, label: str) -> list[str]:
        historical = _strict_boundary_values(prior_aggregate, key, label)
        aborted = _strict_boundary_values(incident_aggregate, key, label)
        return sorted(set(historical).union(aborted))

    item_ids = merged("prior_item_ids", "item ids")
    source_entity_ids = merged("prior_source_entity_ids", "source entity ids")
    component_ids = merged("prior_component_ids", "component ids")
    return {
        "prior_exposure_receipt_sha256": prior_sha,
        "aborted_attempt_exposure_receipt_sha256": incident_sha,
        "item_ids": item_ids,
        "source_entity_ids": source_entity_ids,
        "component_ids": component_ids,
        "item_root_sha256": canonical_sha256(item_ids),
        "source_entity_root_sha256": canonical_sha256(source_entity_ids),
        "component_root_sha256": canonical_sha256(component_ids),
    }


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
            raise PriorExposureRefusal("refusing to replace prior-exposure receipt") from error
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


def _page_arg(value: str) -> tuple[tuple[int, int], tuple[Path, str]]:
    try:
        offset_text, length_text, expected_sha, path_text = value.split(":", 3)
        spec = (int(offset_text), int(length_text))
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError(
            "page must be OFFSET:LENGTH:EXPECTED_SHA256:PATH"
        ) from error
    return spec, (Path(path_text), expected_sha)


def _root_arg(value: str) -> tuple[str, Path]:
    try:
        alias, path = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("artifact root must be ALIAS=PATH") from error
    return alias, Path(path)


def _build_aborted_attempt_main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Replay an aborted F1 attempt from copied SQLite main+WAL evidence."
    )
    parser.add_argument("--attempt-db", type=Path, required=True)
    parser.add_argument("--spool-db", type=Path, required=True)
    parser.add_argument("--selection-receipt", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--execution-lock", type=Path, required=True)
    parser.add_argument("--db-genesis-receipt", type=Path, required=True)
    parser.add_argument("--environment-dependency-bundle", type=Path, required=True)
    parser.add_argument("--model-deployment-receipt", type=Path, required=True)
    parser.add_argument("--spool-identity-receipt", type=Path, required=True)
    parser.add_argument("--job-command", type=Path, required=True)
    parser.add_argument("--job-log", type=Path, required=True)
    parser.add_argument("--job-rc", type=Path, required=True)
    parser.add_argument("--hswm-executable-root", type=Path, required=True)
    parser.add_argument("--producer-hswm-root", type=Path, required=True)
    parser.add_argument("--historical-python", type=Path, required=True)
    parser.add_argument("--hswm-carrier-root", type=Path, required=True)
    parser.add_argument("--symposium-root", type=Path, required=True)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--private-witness-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = build_aborted_attempt_exposure_receipt(
            attempt_db=args.attempt_db,
            spool_db=args.spool_db,
            selection_receipt=args.selection_receipt,
            manifest=args.manifest,
            source_receipt=args.source_receipt,
            execution_lock=args.execution_lock,
            db_genesis_receipt=args.db_genesis_receipt,
            environment_dependency_bundle=args.environment_dependency_bundle,
            model_deployment_receipt=args.model_deployment_receipt,
            spool_identity_receipt=args.spool_identity_receipt,
            job_command=args.job_command,
            job_log=args.job_log,
            job_rc=args.job_rc,
            hswm_executable_root=args.hswm_executable_root,
            producer_hswm_root=args.producer_hswm_root,
            historical_python=args.historical_python,
            hswm_carrier_root=args.hswm_carrier_root,
            symposium_root=args.symposium_root,
            snapshot_dir=args.snapshot_dir,
            private_witness_output=args.private_witness_output,
        )
        verify_aborted_attempt_exposure_receipt(receipt)
        write_private_once(args.output, receipt)
        print(
            json.dumps(
                {
                    "status": "PRODUCER_ATTESTED_STRUCTURAL_REPLAY",
                    "counts": receipt["counts"],
                    "database_roots": {
                        name: value["authority_root_sha256"]
                        for name, value in receipt["database_snapshots"].items()
                    },
                    "aborted_attempt_exposure_receipt_sha256": receipt[
                        "aborted_attempt_exposure_receipt_sha256"
                    ],
                },
                sort_keys=True,
            )
        )
        return 0
    except PriorExposureRefusal as error:
        print(
            json.dumps(
                {"status": "REFUSED", "reason": str(error)}, sort_keys=True
            ),
            file=sys.stderr,
        )
        return 1
    except Exception:
        print(
            json.dumps(
                {"status": "REFUSED", "reason": "INTERNAL_ERROR"},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "build-aborted-attempt":
        return _build_aborted_attempt_main(arguments[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", action="append", type=_page_arg, required=True)
    parser.add_argument("--artifact-root", action="append", type=_root_arg, required=True)
    parser.add_argument("--dataset", default="framolfese/2WikiMultihopQA")
    parser.add_argument("--config", default="default")
    parser.add_argument("--split", default="validation")
    parser.add_argument("--expect-run-dirs", type=int, required=True)
    parser.add_argument("--expect-legacy-source-receipts", type=int, required=True)
    parser.add_argument("--expect-manifests", type=int, required=True)
    parser.add_argument("--expect-suites", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(arguments)
    try:
        pages = dict(args.page)
        roots = dict(args.artifact_root)
        if len(pages) != len(args.page) or len(roots) != len(args.artifact_root):
            raise PriorExposureRefusal("duplicate page or artifact-root argument")
        receipt = build_prior_exposure_receipt(
            page_files=pages,
            artifact_roots=roots,
            dataset=args.dataset,
            config=args.config,
            split=args.split,
            expected_run_dirs=args.expect_run_dirs,
            expected_legacy_source_receipts=args.expect_legacy_source_receipts,
            expected_manifests=args.expect_manifests,
            expected_suites=args.expect_suites,
        )
        verify_prior_exposure_receipt(receipt)
        write_private_once(args.output, receipt)
        print(
            json.dumps(
                {
                    "status": "COMPLETE_NO_ANSWERS_DISCLOSED",
                    **receipt["counts"],
                    "prior_exposure_receipt_sha256": receipt[
                        "prior_exposure_receipt_sha256"
                    ],
                    "roots": receipt["roots"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception:
        print(json.dumps({"status": "REFUSED"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ABORTED_ATTEMPT_EXPOSURE_SCHEMA",
    "ABORTED_ATTEMPT_EXPOSURE_SCHEMA_V2",
    "ABORTED_ATTEMPT_STATUS",
    "EXPECTED_PAGE_SPECS",
    "PriorExposureRefusal",
    "SCHEMA",
    "build_aborted_attempt_exposure_receipt",
    "build_prior_exposure_receipt",
    "inventory_stable_tree",
    "merge_exposure_boundaries",
    "verify_aborted_attempt_exposure_receipt",
    "verify_aborted_attempt_private_witness",
    "verify_forbidden_exposure_union",
    "verify_prior_exposure_receipt",
    "write_private_once",
]
