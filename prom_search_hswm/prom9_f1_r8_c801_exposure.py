#!/usr/bin/env python3
"""Freeze the c800 deployment-loss exposure and authorize fresh c801 cohorts.

This generation is deliberately separate from the historical v4 SIGBUS leaf.
It reads only public source metadata and allowlisted SQLite scalar columns.  It
never reads response bodies, model-response blobs, item-run blobs, or gold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence

from model_deployment_receipt import validate_deployment_receipt
from prom_search_hswm.hswm_typed_ports import (
    canonical_json,
    canonical_sha256,
    output_json_schema,
    output_schema_sha256,
    port_digest,
    validate_port,
)
from prom_search_hswm.prom9_f1_prior_exposure import (
    _ATTEMPT_COLUMNS,
    _CALL_CONTRACTS,
    _CALL_KEYS,
    _DURABLE_CALL_SCHEMA,
    _SPOOL_COLUMNS,
    _SPOOL_ROUTE_PREFIX,
    _open_snapshot_read_only,
    _public_database_snapshot,
    _replay_attempt_event_chain,
    _registry_prompt_authority,
    _snapshot_sqlite_pair,
    _strict_canonical_blob,
    ABORTED_ATTEMPT_STATUS,
    PriorExposureRefusal,
    _source_metadata,
    _verify_call_input_manifest_binding,
    _verify_sqlite_source_pair,
    verified_aborted_attempt_aggregate,
    verify_f1_r8_successor_exposure_set,
    verify_prior_exposure_receipt,
    write_private_once,
)
from prom_search_hswm.prom9_f1_r8_source import (
    EVALUATOR_SEAL_SCHEMA,
    verify_evaluator_seal,
    verify_public_source_receipt,
)
from prom_search_hswm.prom9_f1_r8_environment import (
    R8_COMMIT_BOUND_DEPENDENCY_NAMES,
    R8_DEPENDENCY_NAMES,
    R8_SYMPOSIUM_COMMIT_BOUND_DEPENDENCY_NAMES,
    verify_preimage_bundle,
)


C800_INCIDENT_EXPOSURE_SCHEMA = (
    "hswm-prom9-f1-aborted-attempt-exposure/v5"
)
F1_R8_SUCCESSOR_EXPOSURE_SET_SCHEMA_V2 = (
    "hswm-prom9-f1-successor-exposure-set/v2"
)
C800_RUN_ID = "f1-2wiki-development-r8-c800"
C801_DEVELOPMENT_RUN_ID = "f1-2wiki-development-r8-c801"
C801_SEALED_RUN_ID = "f1-2wiki-sealed-r8-c801"
C800_HSWM_COMMIT = "be82a1248a203cb6bef393558ec2289fb7cd3f04"
C800_SYMPOSIUM_COMMIT = "f4dc9002f0fa1c31c54c9200d2d852d85c942deb"
C800_HSWM_TREE = "29bcd0134812a4fea66c160feb7ab7e3d95612ce"
C800_SYMPOSIUM_TREE = "1d2a997ec1c5ff53813e5f8ec8a75b75c2d12119"
C800_MODEL = "qwen3.6-27b"
C800_MODEL_REVISION = "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"
C800_SPOOL_ENDPOINT = "http://127.0.0.1:8110"
C800_UPSTREAM_ENDPOINT = "http://127.0.0.1:8100/v1/chat/completions"
C800_DEPLOYMENT_RECEIPT_SHA256 = (
    "3dc9004e2e7572829c376a7ee0344cce7a28d4eb88183c9ce2cdfebf7c46f6fe"
)
C800_DEPLOYMENT_RECEIPT_RAW_SHA256 = (
    "e668b31aa582849a4fe7854893460f72a24abac8dd37a90186c3b541c4388a44"
)
C800_JUDGE_CORE_SHA256 = (
    "92384767bfb7e2e7be83cd3320a99d31993a57e5a07e784fad4300248ef6db98"
)
C800_JUDGE_CORE_FILE_SHA256 = (
    "92384767bfb7e2e7be83cd3320a99d31993a57e5a07e784fad4300248ef6db98"
)

# c800 was initialized with the current attempt/spool schema authorities.  The
# historical-v8 spool authority belongs only to the older predecessor capture.
_C800_SCHEMA_AUTHORITIES = {"attempt": "attempt", "spool": "spool"}

# Filled only after the real public receipt has been generated twice from the
# frozen c800 evidence and exact read back.  Production verification fails
# closed while the pin is absent.
C800_INCIDENT_RECEIPT_SHA256: str | None = None

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_ARMS = (
    "typed_hswm_three_function_network",
    "flat_single_llm_three_call_workflow",
    "vector_memory_three_call_workflow",
    "typed_network_role_removed_schema_preserving_null",
    "typed_network_with_role_instructions_shuffled_but_ports_preserved",
)
_EXPECTED_COUNTS = {
    "attempt_calls": 648,
    "attempt_events": 3886,
    "item_runs": 215,
    "spool_calls": 647,
    "attempt_states": {"ACCEPTED": 647, "REJECTED_PROTOCOL": 1},
    "spool_states": {"COMPLETE": 647},
    "accepted_upstream_model_calls": 647,
    "pre_dispatch_rejections": 1,
}
_ARTIFACT_SCHEMAS = {
    "selection_receipt": "hswm-prom9-f1-r8-cohort-selection/v5",
    "manifest": "hswm-prom9-f1-manifest/v3",
    "source_receipt": "hswm-prom9-f1-r8-source-receipt/v3",
    "evaluator_receipt": EVALUATOR_SEAL_SCHEMA,
    "execution_lock": "hswm-prom9-f1-r8-execution-lock/v4",
    "db_genesis_receipt": "hswm-prom9-f1-r8-transport-genesis/v1",
    "environment_dependency_bundle": (
        "hswm-prom9-f1-r8-environment-dependency-bundle/v1"
    ),
    "model_deployment_receipt": "hswm-openai-deployment-attestation/v2",
    "spool_identity_receipt": (
        "hswm-prom9-f1-r8-spool-endpoint-preflight/v2"
    ),
}
_ARTIFACT_SELF_HASHES = {
    "selection_receipt": ("selection_receipt_sha256",),
    "manifest": (),
    "source_receipt": ("source_receipt_sha256",),
    "evaluator_receipt": ("receipt_sha256",),
    "execution_lock": ("lock_sha256",),
    "db_genesis_receipt": ("genesis_sha256",),
    "environment_dependency_bundle": ("bundle_sha256",),
    "model_deployment_receipt": ("receipt_sha256",),
    "spool_identity_receipt": ("preflight_sha256",),
}
_ARTIFACT_SELF_HASH_EXCLUSIONS = {
    "model_deployment_receipt": ("receipt_sha256", "deployment_id"),
}
_ARTIFACT_RAW_SHA256 = {
    "selection_receipt": "f4a0fcf9e4f8be0870b230d03aae37e4a4b547328a8af86e77e6375bb516a793",
    "manifest": "f938c764580a8b79aef8a55a12166af780605148e518f5d4f0f72cd6c1e98881",
    "source_receipt": "c4710cf16c08f1c6a5baec0cfe02823c57c1961ff362d27cee52c0e24a7da8b1",
    "evaluator_receipt": "5a828f45accc6915a73a3bad1831dca933880e641530154b58dda370c81aaa26",
    "execution_lock": "1d866a452f5af3581dd3b9ea03285a3924377d9fc5174eba57b0b163cd3e59f3",
    "db_genesis_receipt": "0774ae58c27e5286edd0559cb78679a5e7481866b97ba0f890c42e87731c5eda",
    "environment_dependency_bundle": (
        "9ad65096b0052597f97209cd92b8d055cc75c66e263127d841ae1a3e2bd22b10"
    ),
    "model_deployment_receipt": C800_DEPLOYMENT_RECEIPT_RAW_SHA256,
    "spool_identity_receipt": "54ea0a4690d7ed75a491736d030e44170cfe1c20e24f3fb252641b8c0d447605",
}
_FROZEN_JSON_RAW_SHA256 = {
    "prior_exposure_receipt": "1b3e4b4d3f89310d40bea5823da77eed3dc80a5c7c8fcfb3116a08295314b1fb",
    "predecessor_successor_exposure_set": (
        "27e904f343d68912e4c7a4f69a624b9b3656bad654d4240d3480fd734fa3b58c"
    ),
    "predecessor_selection_receipt": (
        "47d1cc8095564d1efe2aae5e6c9de1da00c5eb24f7cf0063c9350313b8886c6c"
    ),
}
_EVIDENCE_SHA256 = {
    "job_command": "95e018951836b4a7fa1730e2c846dfd24171e9c81aca691a838bd16be22cb8dd",
    "job_log": "ce5c4fd3e64d2cfb7aebb52d43310a1da4473fb4d01b154de9b8f0ae93628f95",
    "job_rc": "9d9b18720961e9b4689fd763b85e7b6f36160ccd3a8a1c9ddc5103bb0f66c396",
    "systemd_journal": "b542b62eab08d1f16b1e4878700392b2abc77e3a509d5c119687543afaec1630",
    "runner_command": "7c28691ddfaf0815f1239d8f37715247113251472c9f602154c5f5bef89415c0",
    "post_oom_runner_log": "bad3cb89691419026840a1ffec4bb8a67cc28d9d7c5d46695c2bf76b1964842d",
    "post_oom_spool_log": "cd047bef0d23fb8e73487127f5afdd8efb9c40d18d3a9cbc524e62d7cc33d6bf",
}
_DATABASE_MEMBER_SHA256 = {
    "attempt": {
        "main": "0ab48b25cba617ed3a4acca0161813b314c095ef63544bb4af60769eb1012977",
        "wal": "6611a858a372934ea2682fc9394b6adf9d526680e118622b96d76e74c59104d1",
    },
    "spool": {
        "main": "0ab48b25cba617ed3a4acca0161813b314c095ef63544bb4af60769eb1012977",
        "wal": "f032add3acf2798332b35faac128b37cbcc40596bbc538d910190b4dc88f74b7",
    },
}
_C800_ENVIRONMENT_LABELS = {
    "hswm_commit": C800_HSWM_COMMIT,
    "model": C800_MODEL,
    "model_deployment_receipt_sha256": C800_DEPLOYMENT_RECEIPT_SHA256,
    "model_revision": C800_MODEL_REVISION,
    "model_upstream_endpoint": C800_UPSTREAM_ENDPOINT,
    "run_id": C800_RUN_ID,
    "spool_endpoint": C800_SPOOL_ENDPOINT,
    "symposium_commit": C800_SYMPOSIUM_COMMIT,
}
_C800_HSWM_DEPENDENCY_PATHS = {
    "call_receipt": "prom_search_hswm/hswm_call_receipt.py",
    "data_preparer": "prom_search_hswm/prom9_f1_r8_source.py",
    "data_preparer_core": "prom_search_hswm/prom9_prepare_2wiki_f1.py",
    "durable_transport": "prom_search_hswm/hswm_f1_durable_transport.py",
    "environment": "prom_search_hswm/prom9_f1_r8_environment.py",
    "function_network": "prom_search_hswm/hswm_function_network.py",
    "function_network_adapter": "prom_search_hswm/prom_f1_function_network.py",
    "function_registry": "prom_search_hswm/hswm_function_registry.py",
    "lock_builder": "prom_search_hswm/prom9_f1_r8_lock.py",
    "model_deployment_receipt_code": "model_deployment_receipt.py",
    "model_snapshot_attestation_core": "bge_m3_embed.py",
    "power_builder": "prom_search_hswm/prom9_f1_r8_power.py",
    "power_cli": "prom_search_hswm/prom9_f1_r8_power_cli.py",
    "prior_exposure": "prom_search_hswm/prom9_f1_prior_exposure.py",
    "private_output": "prom_search_hswm/prom9_f1_r8_private_output.py",
    "protocol_json": "prom_search_hswm/prom9_semantic_neural_network.v1.json",
    "protocol_loader": "prom_search_hswm/prom9_protocol.py",
    "result_spool": "prom_search_hswm/hswm_result_spool.py",
    "runner": "prom_search_hswm/prom9_f1_r8_runner.py",
    "sqlite_schema_authority": "prom_search_hswm/hswm_f1_sqlite_schema.py",
    "terminal_transport_exporter": "prom_search_hswm/prom9_f1_r8_transport_audit.py",
    "token_envelope": "prom_search_hswm/prom9_f1_envelope.py",
    "token_envelope_derivation": "prom_search_hswm/prom9_f1_r8_envelope.py",
    "token_meter": "prom_search_hswm/hswm_token_meter.py",
    "token_meter_validator": "prom_search_hswm/prom9_validate_token_meter.py",
    "typed_ports": "prom_search_hswm/hswm_typed_ports.py",
}
_C800_SYMPOSIUM_DEPENDENCY_PATHS = {
    "judge_core": "FINDINGS/hswm-f1-r8-try3-2026-07-28/f1_r8_lakatotree_judge_v3.py",
}


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _read_stable_bytes(path: Path, *, max_bytes: int | None = None) -> bytes:
    target = Path(path)
    try:
        before = target.lstat()
    except OSError as error:
        raise PriorExposureRefusal("c800 evidence input is unavailable") from error
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise PriorExposureRefusal("c800 evidence input must be a regular file")
    if max_bytes is not None and before.st_size > max_bytes:
        raise PriorExposureRefusal("c800 evidence input exceeds its public cap")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(target, flags)
        raw = bytearray()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            raw.extend(chunk)
            if max_bytes is not None and len(raw) > max_bytes:
                raise PriorExposureRefusal("c800 evidence input exceeds its public cap")
        after_fd = os.fstat(descriptor)
        after_path = target.lstat()
    except OSError as error:
        raise PriorExposureRefusal("c800 evidence input cannot be read") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    identity = lambda value: (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
    if identity(before) != identity(after_fd) or identity(before) != identity(after_path):
        raise PriorExposureRefusal("c800 evidence input changed while read")
    return bytes(raw)


def _read_json(path: Path, label: str, *, max_bytes: int = 512 * 1024 * 1024) -> dict[str, object]:
    try:
        value = json.loads(_read_stable_bytes(path, max_bytes=max_bytes))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PriorExposureRefusal(f"{label} is not strict JSON") from error
    if not isinstance(value, dict):
        raise PriorExposureRefusal(f"{label} is not a JSON object")
    return value


def _file_binding(path: Path) -> dict[str, object]:
    raw = _read_stable_bytes(path)
    return {
        "basename": Path(path).name,
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _frozen_evidence_binding(path: Path, label: str) -> dict[str, object]:
    binding = _file_binding(path)
    if binding["sha256"] != _EVIDENCE_SHA256[label]:
        raise PriorExposureRefusal(f"c800 {label} evidence identity drifted")
    return binding


def _json_binding(
    path: Path, label: str, expected_schema: str
) -> tuple[dict[str, object], dict[str, object]]:
    raw = _read_stable_bytes(path, max_bytes=512 * 1024 * 1024)
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PriorExposureRefusal(f"{label} is not strict JSON") from error
    if not isinstance(value, dict) or value.get("schema_version") != expected_schema:
        raise PriorExposureRefusal(f"{label} schema drifted")
    declared: dict[str, str] = {}
    for field in _ARTIFACT_SELF_HASHES[label]:
        candidate = value.get(field)
        unsigned = dict(value)
        for excluded in _ARTIFACT_SELF_HASH_EXCLUSIONS.get(label, (field,)):
            unsigned.pop(excluded, None)
        if not _is_sha256(candidate) or canonical_sha256(unsigned) != candidate:
            raise PriorExposureRefusal(f"{label} self-hash verification failed")
        declared[field] = str(candidate)
    return value, {
        "basename": Path(path).name,
        "schema_version": expected_schema,
        "size_bytes": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "canonical_sha256": canonical_sha256(value),
        "declared_hashes": declared,
    }


def _git_authority(root: Path, expected: str, label: str) -> dict[str, str]:
    resolved = Path(root).resolve(strict=True)
    try:
        top = subprocess.run(
            ["git", "-C", str(resolved), "rev-parse", "--show-toplevel"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        commit = subprocess.run(
            ["git", "-C", str(resolved), "rev-parse", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "-C", str(resolved), "rev-parse", "HEAD^{tree}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(resolved), "status", "--porcelain", "--untracked-files=no"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise PriorExposureRefusal(f"{label} Git authority is unavailable") from error
    if (
        Path(top).resolve(strict=True) != resolved
        or commit != expected
        or _GIT_COMMIT.fullmatch(commit) is None
        or _GIT_COMMIT.fullmatch(tree) is None
        or dirty
    ):
        raise PriorExposureRefusal(f"{label} Git authority drifted")
    return {"commit": commit, "tree": tree}


def _git_blob_sha256(
    root: Path,
    commit: str,
    relative: str,
    label: str,
) -> str:
    candidate = PurePosixPath(relative)
    if (
        candidate.is_absolute()
        or not candidate.parts
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise PriorExposureRefusal(f"{label} dependency path drifted")
    try:
        raw = subprocess.run(
            [
                "git",
                "-C",
                str(Path(root).resolve(strict=True)),
                "show",
                f"{commit}:{candidate.as_posix()}",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise PriorExposureRefusal(
            f"{label} dependency is absent from its frozen commit"
        ) from error
    return hashlib.sha256(raw).hexdigest()


def _verify_c800_environment_authority(
    environment: Mapping[str, object],
    *,
    hswm_root: Path,
    symposium_root: Path,
    lock: Mapping[str, object],
    model_deployment_raw_sha256: str,
) -> str:
    compatibility_root = verify_preimage_bundle(environment, verify_live=False)
    environment_receipt = environment.get("environment_receipt")
    dependency_receipt = environment.get("dependency_receipt")
    files = (
        dependency_receipt.get("files")
        if isinstance(dependency_receipt, Mapping)
        else None
    )
    if (
        not isinstance(environment_receipt, Mapping)
        or environment_receipt.get("labels") != _C800_ENVIRONMENT_LABELS
        or not isinstance(dependency_receipt, Mapping)
        or not isinstance(files, Mapping)
        or set(files) != set(R8_DEPENDENCY_NAMES)
        or set(_C800_HSWM_DEPENDENCY_PATHS)
        != set(R8_COMMIT_BOUND_DEPENDENCY_NAMES)
        or set(_C800_SYMPOSIUM_DEPENDENCY_PATHS)
        != set(R8_SYMPOSIUM_COMMIT_BOUND_DEPENDENCY_NAMES)
    ):
        raise PriorExposureRefusal("c800 environment authority drifted")

    authorities = (
        (
            "HSWM",
            hswm_root,
            C800_HSWM_COMMIT,
            "/data/kjra/PROJECT/PI/hswm_f1_r8_c800_20260805/HSWM/",
            _C800_HSWM_DEPENDENCY_PATHS,
        ),
        (
            "SYMPOSIUM",
            symposium_root,
            C800_SYMPOSIUM_COMMIT,
            "/data/kjra/PROJECT/PI/hswm_f1_r8_c800_20260805/SYMPOSIUM/",
            _C800_SYMPOSIUM_DEPENDENCY_PATHS,
        ),
    )
    for label, root, commit, prefix, paths in authorities:
        for name, relative in paths.items():
            entry = files.get(name)
            if (
                not isinstance(entry, Mapping)
                or entry.get("resolved_path") != f"{prefix}{relative}"
                or entry.get("sha256")
                != _git_blob_sha256(root, commit, relative, f"c800 {label}")
            ):
                raise PriorExposureRefusal(
                    f"c800 {label} dependency authority drifted: {name}"
                )

    judge = files.get("judge_core")
    deployment_dependency = files.get("model_deployment_receipt")
    if (
        lock.get("judge_core_sha256") != C800_JUDGE_CORE_SHA256
        or lock.get("judge_core_file_sha256") != C800_JUDGE_CORE_FILE_SHA256
        or not isinstance(judge, Mapping)
        or judge.get("sha256") != C800_JUDGE_CORE_FILE_SHA256
        or not isinstance(deployment_dependency, Mapping)
        or deployment_dependency.get("sha256")
        != C800_DEPLOYMENT_RECEIPT_RAW_SHA256
        or model_deployment_raw_sha256
        != C800_DEPLOYMENT_RECEIPT_RAW_SHA256
        or deployment_dependency.get("sha256") != model_deployment_raw_sha256
    ):
        raise PriorExposureRefusal("c800 frozen dependency binding drifted")
    return compatibility_root


def _producer_authority(root: Path) -> dict[str, object]:
    resolved = Path(root).resolve(strict=True)
    relative = "prom_search_hswm/prom9_f1_r8_c801_exposure.py"
    try:
        top = subprocess.run(
            ["git", "-C", str(resolved), "rev-parse", "--show-toplevel"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        commit = subprocess.run(
            ["git", "-C", str(resolved), "rev-parse", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "-C", str(resolved), "rev-parse", "HEAD^{tree}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            [
                "git", "-C", str(resolved), "status", "--porcelain=v1",
                "--untracked-files=all",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout
        committed = subprocess.run(
            ["git", "-C", str(resolved), "show", f"{commit}:{relative}"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise PriorExposureRefusal("c800 producer Git authority is unavailable") from error
    current = _read_stable_bytes(resolved / relative, max_bytes=2 * 1024 * 1024)
    if (
        Path(top).resolve(strict=True) != resolved
        or _GIT_COMMIT.fullmatch(commit) is None
        or _GIT_COMMIT.fullmatch(tree) is None
        or dirty
        or current != committed
    ):
        raise PriorExposureRefusal("c800 producer Git authority drifted")
    return {
        "commit": commit,
        "tree": tree,
        "entrypoint": relative,
        "entrypoint_size_bytes": len(current),
        "entrypoint_sha256": hashlib.sha256(current).hexdigest(),
    }


def _replay_public_call(
    row: sqlite3.Row,
    *,
    manifest: Mapping[str, object],
    spool_endpoint: str,
    expected_prompts: Mapping[tuple[str, str], str],
) -> dict[str, object]:
    """Replay one call without reading any response or receipt body."""

    physical_call_id = str(row["physical_call_id"])
    intent_raw = bytes(row["intent_bytes"])
    request_raw = bytes(row["request_bytes"])
    if (
        not _is_sha256(physical_call_id)
        or hashlib.sha256(intent_raw).hexdigest() != row["intent_sha256"]
        or hashlib.sha256(request_raw).hexdigest() != row["request_sha256"]
    ):
        raise PriorExposureRefusal("c800 attempt call byte hashes drifted")
    intent = _strict_canonical_blob(intent_raw, "c800 attempt intent")
    request = _strict_canonical_blob(request_raw, "c800 attempt request")
    if (
        set(intent)
        != {
            "schema_version",
            "spool_route",
            "call",
            "request_sha256",
            "output_schema_sha256",
        }
        or intent.get("schema_version") != _DURABLE_CALL_SCHEMA
    ):
        raise PriorExposureRefusal("c800 attempt intent shape drifted")
    call = intent.get("call")
    if not isinstance(call, Mapping) or set(call) != _CALL_KEYS:
        raise PriorExposureRefusal("c800 ModelCallV1 shape drifted")
    string_fields = (
        "physical_call_id",
        "run_id",
        "arm_id",
        "item_id",
        "function_id",
        "model",
        "model_revision",
        "system_prompt",
        "input_type",
        "output_type",
    )
    if any(
        not isinstance(call.get(key), str) or not call.get(key)
        for key in string_fields
    ):
        raise PriorExposureRefusal("c800 ModelCallV1 string identity drifted")
    call_index = call.get("call_index")
    max_output_tokens = call.get("max_output_tokens")
    if (
        type(call_index) is not int
        or call_index not in {1, 2, 3}
        or type(max_output_tokens) is not int
        or max_output_tokens < 1
        or not isinstance(call.get("input_payload"), Mapping)
    ):
        raise PriorExposureRefusal("c800 ModelCallV1 numeric identity drifted")
    function_id, input_type, output_type = _CALL_CONTRACTS[call_index]
    expected_prompt = expected_prompts.get(
        (str(call.get("arm_id")), str(function_id))
    )
    token_envelope = manifest.get("token_envelope")
    output_caps = (
        token_envelope.get("per_call_output_caps")
        if isinstance(token_envelope, Mapping)
        else None
    )
    if (
        (call.get("function_id"), call.get("input_type"), call.get("output_type"))
        != (function_id, input_type, output_type)
        or not isinstance(expected_prompt, str)
        or call.get("system_prompt") != expected_prompt
        or not isinstance(output_caps, Mapping)
        or output_caps.get(str(call_index)) != max_output_tokens
    ):
        raise PriorExposureRefusal("c800 call contract differs from manifest")
    try:
        normalized_input = validate_port(str(input_type), call["input_payload"])
    except Exception as error:
        raise PriorExposureRefusal("c800 call input port validation failed") from error
    if canonical_json(normalized_input) != canonical_json(call["input_payload"]):
        raise PriorExposureRefusal("c800 call input payload is not canonical")
    _verify_call_input_manifest_binding(call, manifest)
    expected_physical = canonical_sha256(
        {
            "run_id": call["run_id"],
            "arm_id": call["arm_id"],
            "item_id": call["item_id"],
            "call_index": call_index,
            "function_id": call["function_id"],
            "registry_prompt_sha256": canonical_sha256(
                {"prompt": call["system_prompt"]}
            ),
            "input_port_sha256": port_digest(str(input_type), normalized_input),
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
        "max_tokens": max_output_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": output_type,
                "strict": True,
                "schema": output_json_schema(str(output_type)),
            },
        },
        "chat_template_kwargs": {"enable_thinking": False},
    }
    route = f"{spool_endpoint.rstrip('/')}{_SPOOL_ROUTE_PREFIX}{physical_call_id}"
    if (
        call["physical_call_id"] != physical_call_id
        or expected_physical != physical_call_id
        or call["run_id"] != C800_RUN_ID
        or call["arm_id"] not in _ARMS
        or call["model"] != manifest.get("model")
        or call["model_revision"] != manifest.get("model_revision")
        or intent.get("spool_route") != route
        or row["endpoint"] != route
        or intent.get("request_sha256") != row["request_sha256"]
        or intent.get("output_schema_sha256")
        != output_schema_sha256(str(output_type))
        or request != expected_request
        or canonical_json(expected_request).encode("utf-8") != request_raw
    ):
        raise PriorExposureRefusal("c800 call intent/request replay drifted")
    digest_fields = (
        "response_sha256",
        "model_response_sha256",
        "call_receipt_sha256",
    )
    if any(
        row[field] is not None and not _is_sha256(row[field])
        for field in digest_fields
    ):
        raise PriorExposureRefusal("c800 call scalar digest drifted")
    return {
        "physical_call_id": physical_call_id,
        "run_id": str(call["run_id"]),
        "arm_id": str(call["arm_id"]),
        "item_id": str(call["item_id"]),
        "call_index": int(call_index),
        "model": str(call["model"]),
        "output_type": str(output_type),
        "status": str(row["status"]),
        "response_status": row["response_status"],
        "terminal_code": row["terminal_code"],
        "intent_sha256": str(row["intent_sha256"]),
        "request_sha256": str(row["request_sha256"]),
        "response_sha256": row["response_sha256"],
        "model_response_sha256": row["model_response_sha256"],
        "call_receipt_sha256": row["call_receipt_sha256"],
        "_request_bytes": request_raw,
    }


def _read_structural_observations(
    attempt_db: Path,
    spool_db: Path,
    *,
    manifest: Mapping[str, object],
    spool_endpoint: str,
    expected_prompts: Mapping[tuple[str, str], str],
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="hswm-f1-c800-snapshot-") as raw_dir:
        snapshot_dir = Path(raw_dir)
        snapshot_dir.chmod(0o700)
        attempt_path, attempt_snapshot = _snapshot_sqlite_pair(
            attempt_db, snapshot_dir, label="attempt"
        )
        spool_path, spool_snapshot = _snapshot_sqlite_pair(
            spool_db, snapshot_dir, label="spool"
        )
        _verify_sqlite_source_pair(attempt_db, attempt_snapshot)
        _verify_sqlite_source_pair(spool_db, spool_snapshot)
        attempt, attempt_database = _open_snapshot_read_only(
            attempt_path,
            expected_columns=_ATTEMPT_COLUMNS,
            authority=_C800_SCHEMA_AUTHORITIES["attempt"],
            label="c800 attempt",
        )
        spool, spool_database = _open_snapshot_read_only(
            spool_path,
            expected_columns=_SPOOL_COLUMNS,
            authority=_C800_SCHEMA_AUTHORITIES["spool"],
            label="c800 spool",
        )
        try:
            call_rows = attempt.execute(
                "SELECT physical_call_id,intent_sha256,intent_bytes,request_sha256,"
                "endpoint,request_bytes,status,response_status,response_sha256,"
                "model_response_sha256,call_receipt_sha256,terminal_code "
                "FROM call_state ORDER BY physical_call_id"
            ).fetchall()
            calls = [
                _replay_public_call(
                    row,
                    manifest=manifest,
                    spool_endpoint=spool_endpoint,
                    expected_prompts=expected_prompts,
                )
                for row in call_rows
            ]
            calls.sort(
                key=lambda row: (
                    str(row["item_id"]),
                    _ARMS.index(str(row["arm_id"])),
                    int(row["call_index"]),
                )
            )
            events = attempt.execute(
                "SELECT sequence,physical_call_id,event_type,event_bytes,"
                "previous_event_sha256,event_sha256 "
                "FROM attempt_events ORDER BY sequence"
            ).fetchall()
            item_runs = [
                {
                    "run_id": str(row[0]),
                    "arm_id": str(row[1]),
                    "item_id": str(row[2]),
                    "run_receipt_sha256": str(row[3]),
                }
                for row in attempt.execute(
                    "SELECT run_id,arm_id,item_id,run_receipt_sha256 "
                    "FROM item_runs ORDER BY item_id,arm_id"
                )
            ]
            spool_rows = [
                {
                    "physical_call_id": str(row[0]),
                    "intent_sha256": str(row[1]),
                    "request_sha256": str(row[2]),
                    "request_bytes": bytes(row[3]),
                    "status": str(row[4]),
                    "response_status": row[5],
                    "response_sha256": row[6],
                    "error_class": row[7],
                }
                for row in spool.execute(
                    "SELECT physical_call_id,intent_sha256,request_sha256,request_bytes,"
                    "status,response_status,response_sha256,error_class "
                    "FROM spool_calls ORDER BY physical_call_id"
                )
            ]
        except sqlite3.DatabaseError as error:
            raise PriorExposureRefusal("c800 structural SQLite read failed") from error
        finally:
            if attempt.in_transaction:
                attempt.execute("ROLLBACK")
            if spool.in_transaction:
                spool.execute("ROLLBACK")
            attempt.close()
            spool.close()
        _verify_sqlite_source_pair(attempt_db, attempt_snapshot)
        _verify_sqlite_source_pair(spool_db, spool_snapshot)
        database_snapshots = {
            "attempt": _public_database_snapshot(
                {**attempt_snapshot, **attempt_database}, kind="attempt"
            ),
            "spool": _public_database_snapshot(
                {**spool_snapshot, **spool_database}, kind="spool"
            ),
        }
    status_counts: dict[str, int] = {}
    for call in calls:
        status_counts[call["status"]] = status_counts.get(call["status"], 0) + 1
    spool_counts: dict[str, int] = {}
    for row in spool_rows:
        spool_counts[row["status"]] = spool_counts.get(row["status"], 0) + 1
    counts = {
        "attempt_calls": len(calls),
        "attempt_events": len(events),
        "item_runs": len(item_runs),
        "spool_calls": len(spool_rows),
        "attempt_states": {key: status_counts[key] for key in sorted(status_counts)},
        "spool_states": {key: spool_counts[key] for key in sorted(spool_counts)},
        "accepted_upstream_model_calls": sum(row["status"] == "ACCEPTED" for row in calls),
        "pre_dispatch_rejections": sum(row["status"] == "REJECTED_PROTOCOL" for row in calls),
    }
    if counts != _EXPECTED_COUNTS:
        raise PriorExposureRefusal("c800 structural counts drifted")

    call_ids = {str(row["physical_call_id"]) for row in calls}
    if len(call_ids) != len(calls) or any(
        row["run_id"] != C800_RUN_ID
        or row["arm_id"] not in _ARMS
        or not 1 <= int(row["call_index"]) <= 3
        or not _is_sha256(row["physical_call_id"])
        or not _is_sha256(row["intent_sha256"])
        or not _is_sha256(row["request_sha256"])
        for row in calls
    ):
        raise PriorExposureRefusal("c800 call identity drifted")
    accepted = [row for row in calls if row["status"] == "ACCEPTED"]
    rejected = [row for row in calls if row["status"] == "REJECTED_PROTOCOL"]
    spool_by_id = {str(row["physical_call_id"]): row for row in spool_rows}
    spool_ids = set(spool_by_id)
    if (
        len(spool_by_id) != len(spool_rows)
        or spool_ids != {str(row["physical_call_id"]) for row in accepted}
        or any(
            row["status"] != "COMPLETE"
            or row["response_status"] != 200
            or not _is_sha256(row["response_sha256"])
            or row["error_class"] is not None
            or hashlib.sha256(row["request_bytes"]).hexdigest()
            != row["request_sha256"]
            for row in spool_rows
        )
        or any(
            row["response_status"] != 200
            or not _is_sha256(row["response_sha256"])
            or row["terminal_code"] is not None
            or spool_by_id[str(row["physical_call_id"])]["intent_sha256"]
            != row["intent_sha256"]
            or spool_by_id[str(row["physical_call_id"])]["request_sha256"]
            != row["request_sha256"]
            or spool_by_id[str(row["physical_call_id"])]["response_sha256"]
            != row["response_sha256"]
            or spool_by_id[str(row["physical_call_id"])]["request_bytes"]
            != row["_request_bytes"]
            or not _is_sha256(row["model_response_sha256"])
            or not _is_sha256(row["call_receipt_sha256"])
            for row in accepted
        )
    ):
        raise PriorExposureRefusal("c800 accepted-call/spool binding drifted")
    rejection = rejected[0]
    if (
        rejection["response_status"] != 400
        or rejection["terminal_code"] != "SPOOL_ATTESTATION_INVALID"
        or not _is_sha256(rejection["response_sha256"])
        or rejection["physical_call_id"] in spool_ids
        or rejection["call_index"] != 3
        or rejection["model_response_sha256"] is not None
        or rejection["call_receipt_sha256"] is not None
    ):
        raise PriorExposureRefusal("c800 pre-dispatch rejection drifted")

    call_states = {
        str(row["physical_call_id"]): str(row["status"])
        for row in calls
    }
    call_bindings = {
        str(row["physical_call_id"]): row
        for row in calls
    }
    event_replay = _replay_attempt_event_chain(events, call_states, call_bindings)
    if event_replay["event_count"] != _EXPECTED_COUNTS["attempt_events"]:
        raise PriorExposureRefusal("c800 event replay count drifted")
    per_call_events: dict[str, list[str]] = {}
    for row in events:
        key = str(row["physical_call_id"])
        per_call_events.setdefault(key, []).append(str(row["event_type"]))
    accepted_chain = [
        "PREPARED", "SENT", "RAW_COMPLETE", "ENVELOPE_VALID",
        "SCHEMA_VALID", "ACCEPTED",
    ]
    if any(
        per_call_events.get(str(row["physical_call_id"])) != accepted_chain
        for row in accepted
    ):
        raise PriorExposureRefusal("c800 accepted event chain drifted")
    rejection_id = str(rejection["physical_call_id"])
    if per_call_events.get(rejection_id) != [
        "PREPARED", "SENT", "RAW_COMPLETE", "REJECTED_PROTOCOL"
    ]:
        raise PriorExposureRefusal("c800 rejection event chain drifted")

    item_run_keys = {(row["item_id"], row["arm_id"]) for row in item_runs}
    if len(item_run_keys) != len(item_runs) or any(
        row["run_id"] != C800_RUN_ID
        or row["arm_id"] not in _ARMS
        or not _is_sha256(row["run_receipt_sha256"])
        for row in item_runs
    ):
        raise PriorExposureRefusal("c800 item-run structure drifted")
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in accepted:
        groups.setdefault((str(row["item_id"]), str(row["arm_id"])), []).append(row)
    for key in item_run_keys:
        group = sorted(groups.get(key, []), key=lambda row: int(row["call_index"]))
        if [row["call_index"] for row in group] != [1, 2, 3]:
            raise PriorExposureRefusal("c800 committed item run lacks three accepted calls")
    frontier_key = (str(rejection["item_id"]), str(rejection["arm_id"]))
    frontier = sorted(groups.get(frontier_key, []), key=lambda row: int(row["call_index"]))
    if (
        frontier_key in item_run_keys
        or [row["call_index"] for row in frontier] != [1, 2]
        or set(groups) != item_run_keys | {frontier_key}
    ):
        raise PriorExposureRefusal("c800 rejected frontier is not pre-dispatch-only")
    per_item_arms: dict[str, set[str]] = {}
    for item_id, arm_id in item_run_keys:
        per_item_arms.setdefault(item_id, set()).add(arm_id)
    if any(arms != set(_ARMS) for arms in per_item_arms.values()):
        raise PriorExposureRefusal("c800 completed item lacks the five-arm schedule")

    return {
        "database_snapshots": database_snapshots,
        "counts": counts,
        "observed_item_ids": sorted(
            {str(row["item_id"]) for row in calls}
            | {str(row["item_id"]) for row in item_runs}
        ),
        "rejection": {
            "physical_call_id": rejection["physical_call_id"],
            "item_id": rejection["item_id"],
            "arm_id": rejection["arm_id"],
            "call_index": rejection["call_index"],
            "response_status": rejection["response_status"],
            "response_sha256": rejection["response_sha256"],
            "terminal_code": rejection["terminal_code"],
            "attempt_state": "REJECTED_PROTOCOL",
            "event_count": len(per_call_events[rejection_id]),
            "spool_row_present": False,
            "model_call_dispatched": False,
        },
    }


def _exposure_aggregate(
    metadata: Mapping[str, Mapping[str, object]], item_ids: Sequence[str]
) -> dict[str, object]:
    items = sorted(set(str(value) for value in item_ids))
    if any(item not in metadata for item in items):
        raise PriorExposureRefusal("c800 exposed item lacks public metadata")
    sources = sorted(
        {
            str(source)
            for item in items
            for source in metadata[item]["source_entity_ids"]
        }
    )
    components = sorted({str(metadata[item]["component_id"]) for item in items})
    return {
        "prior_item_ids": items,
        "prior_source_entity_ids": sources,
        "prior_component_ids": components,
        "item_root_sha256": canonical_sha256(items),
        "source_entity_root_sha256": canonical_sha256(sources),
        "component_root_sha256": canonical_sha256(components),
    }


def _verify_exposure_aggregate(value: object) -> dict[str, object]:
    fields = {
        "prior_item_ids",
        "prior_source_entity_ids",
        "prior_component_ids",
        "item_root_sha256",
        "source_entity_root_sha256",
        "component_root_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise PriorExposureRefusal("c800 exposure aggregate shape drifted")
    for ids_key, root_key in (
        ("prior_item_ids", "item_root_sha256"),
        ("prior_source_entity_ids", "source_entity_root_sha256"),
        ("prior_component_ids", "component_root_sha256"),
    ):
        values = value.get(ids_key)
        if (
            not isinstance(values, list)
            or values != sorted(set(values))
            or any(not isinstance(item, str) or not item for item in values)
            or canonical_sha256(values) != value.get(root_key)
        ):
            raise PriorExposureRefusal("c800 exposure aggregate root drifted")
    return dict(value)


def _verify_file_binding(value: object, label: str) -> Mapping[str, object]:
    if (
        not isinstance(value, Mapping)
        or set(value) != {"basename", "size_bytes", "sha256"}
        or not isinstance(value.get("basename"), str)
        or not value.get("basename")
        or isinstance(value.get("size_bytes"), bool)
        or not isinstance(value.get("size_bytes"), int)
        or int(value["size_bytes"]) < 1
        or not _is_sha256(value.get("sha256"))
    ):
        raise PriorExposureRefusal(f"{label} file binding drifted")
    return value


def _verify_database_snapshot(value: object, label: str) -> None:
    fields = {
        "authority_members", "members", "authority_root_sha256", "integrity",
        "journal_mode", "user_version", "schema_sha256",
        "canonical_schema_sha256",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != fields
        or value.get("authority_members") != ["main", "wal"]
        or value.get("integrity") != "ok"
        or value.get("journal_mode") != "wal"
        or value.get("user_version") != 1
        or not _is_sha256(value.get("schema_sha256"))
        or not _is_sha256(value.get("canonical_schema_sha256"))
    ):
        raise PriorExposureRefusal(f"c800 {label} snapshot authority drifted")
    members = value.get("members")
    if not isinstance(members, Mapping) or set(members) != {"main", "wal"}:
        raise PriorExposureRefusal(f"c800 {label} snapshot members drifted")
    for member_name, member in members.items():
        _verify_file_binding(member, f"c800 {label} {member_name}")
    if canonical_sha256(members) != value.get("authority_root_sha256"):
        raise PriorExposureRefusal(f"c800 {label} snapshot root drifted")


def _verify_c800_incident_unpinned(value: Mapping[str, object]) -> str:
    fields = {
        "schema_version",
        "status",
        "run_identity",
        "runtime_authority",
        "producer_authority",
        "termination",
        "capture_policy",
        "artifact_bindings",
        "database_snapshots",
        "counts",
        "pre_dispatch_rejections",
        "aggregate",
        "successor_disposition",
        "complete",
        "c800_incident_receipt_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise PriorExposureRefusal("c800 incident receipt shape drifted")
    unsigned = dict(value)
    declared = unsigned.pop("c800_incident_receipt_sha256", None)
    if (
        value.get("schema_version") != C800_INCIDENT_EXPOSURE_SCHEMA
        or value.get("status") != ABORTED_ATTEMPT_STATUS
        or value.get("complete") is not True
        or not _is_sha256(declared)
        or canonical_sha256(unsigned) != declared
    ):
        raise PriorExposureRefusal("c800 incident identity drifted")
    if value.get("run_identity") != {
        "run_id": C800_RUN_ID,
        "hswm_commit": C800_HSWM_COMMIT,
        "symposium_commit": C800_SYMPOSIUM_COMMIT,
    }:
        raise PriorExposureRefusal("c800 incident run authority drifted")
    runtime = value.get("runtime_authority")
    if not isinstance(runtime, Mapping) or set(runtime) != {"hswm", "symposium"}:
        raise PriorExposureRefusal("c800 runtime authority is absent")
    for name, expected_commit, expected_tree in (
        ("hswm", C800_HSWM_COMMIT, C800_HSWM_TREE),
        ("symposium", C800_SYMPOSIUM_COMMIT, C800_SYMPOSIUM_TREE),
    ):
        authority = runtime.get(name)
        if (
            not isinstance(authority, Mapping)
            or set(authority) != {"commit", "tree"}
            or authority.get("commit") != expected_commit
            or authority.get("tree") != expected_tree
        ):
            raise PriorExposureRefusal("c800 runtime Git authority drifted")
    producer = value.get("producer_authority")
    if (
        not isinstance(producer, Mapping)
        or set(producer)
        != {
            "commit", "tree", "entrypoint", "entrypoint_size_bytes",
            "entrypoint_sha256",
        }
        or _GIT_COMMIT.fullmatch(str(producer.get("commit"))) is None
        or _GIT_COMMIT.fullmatch(str(producer.get("tree"))) is None
        or producer.get("entrypoint")
        != "prom_search_hswm/prom9_f1_r8_c801_exposure.py"
        or isinstance(producer.get("entrypoint_size_bytes"), bool)
        or not isinstance(producer.get("entrypoint_size_bytes"), int)
        or int(producer["entrypoint_size_bytes"]) < 1
        or not _is_sha256(producer.get("entrypoint_sha256"))
    ):
        raise PriorExposureRefusal("c800 producer authority drifted")
    termination = value.get("termination")
    if (
        not isinstance(termination, Mapping)
        or set(termination)
        != {
            "classification",
            "systemd_unit",
            "systemd_result",
            "wrapper_exit_code",
            "server_pid",
            "deployment_id",
            "deployment_endpoint",
            "job_command",
            "job_log",
            "job_rc",
            "systemd_journal",
            "runner_command",
            "post_oom_runner_log",
            "post_oom_spool_log",
        }
        or termination.get("classification") != "MODEL_DEPLOYMENT_KERNEL_OOM"
        or termination.get("systemd_unit")
        != "dt-hswm-f1-r8-vllm-canary-triton-1025982.scope"
        or termination.get("systemd_result") != "oom-kill"
        or termination.get("wrapper_exit_code") != 143
        or termination.get("server_pid") != 1025995
        or termination.get("deployment_id")
        != (
            "hswm:model_deployment:v2:"
            "3dc9004e2e7572829c376a7ee0344cce7a28d4eb88183c9ce2cdfebf7c46f6fe"
        )
        or termination.get("deployment_endpoint") != "http://127.0.0.1:8100/v1"
    ):
        raise PriorExposureRefusal("c800 deployment-loss evidence drifted")
    for key in set(termination) - {
        "classification", "systemd_unit", "systemd_result", "wrapper_exit_code",
        "server_pid", "deployment_id", "deployment_endpoint",
    }:
        binding = _verify_file_binding(termination.get(key), "c800 termination")
        if binding.get("sha256") != _EVIDENCE_SHA256[key]:
            raise PriorExposureRefusal("c800 termination identity drifted")
    if value.get("capture_policy") != {
        "sqlite_authority_members": ["main", "wal"],
        "sqlite_shm_authoritative": False,
        "sqlite_snapshotted_before_replay": True,
        "response_blob_columns_read": False,
        "item_run_blob_columns_read": False,
        "gold_inputs_accepted": False,
        "model_calls_invoked": False,
        "kg_accessed": False,
        "raw_attempt_states_preserved": True,
        "pre_dispatch_rejection_counts_as_model_call": False,
    }:
        raise PriorExposureRefusal("c800 capture policy drifted")
    if value.get("counts") != _EXPECTED_COUNTS:
        raise PriorExposureRefusal("c800 incident count authority drifted")
    rejections = value.get("pre_dispatch_rejections")
    if not isinstance(rejections, list) or len(rejections) != 1:
        raise PriorExposureRefusal("c800 pre-dispatch rejection inventory drifted")
    rejection = rejections[0]
    rejection_fields = {
        "physical_call_id", "item_id", "arm_id", "call_index",
        "response_status", "response_sha256", "terminal_code",
        "attempt_state", "event_count", "spool_row_present",
        "model_call_dispatched",
    }
    if (
        not isinstance(rejection, Mapping)
        or set(rejection) != rejection_fields
        or not _is_sha256(rejection.get("physical_call_id"))
        or not isinstance(rejection.get("item_id"), str)
        or not rejection.get("item_id")
        or rejection.get("arm_id") not in _ARMS
        or rejection.get("call_index") != 3
        or rejection.get("response_status") != 400
        or not _is_sha256(rejection.get("response_sha256"))
        or rejection.get("terminal_code") != "SPOOL_ATTESTATION_INVALID"
        or rejection.get("attempt_state") != "REJECTED_PROTOCOL"
        or rejection.get("event_count") != 4
        or rejection.get("spool_row_present") is not False
        or rejection.get("model_call_dispatched") is not False
    ):
        raise PriorExposureRefusal("c800 pre-dispatch rejection evidence drifted")
    _verify_exposure_aggregate(value.get("aggregate"))
    disposition = value.get("successor_disposition")
    if disposition != {
        "forensic_only": True,
        "resume_authorized": False,
        "successor_required": True,
        "successor_run_id": C801_DEVELOPMENT_RUN_ID,
        "legacy_database_mutation_authorized": False,
        "legacy_database_import_authorized": False,
        "accepted_result_import_authorized": False,
    }:
        raise PriorExposureRefusal("c800 successor disposition drifted")
    artifacts = value.get("artifact_bindings")
    if not isinstance(artifacts, Mapping) or set(artifacts) != {
        *set(_ARTIFACT_SCHEMAS),
        "prior_exposure_receipt",
        "predecessor_successor_exposure_set",
        "predecessor_selection_receipt",
    }:
        raise PriorExposureRefusal("c800 artifact inventory drifted")
    for name, binding in artifacts.items():
        required = {"basename", "size_bytes", "raw_sha256", "canonical_sha256"}
        if name in _ARTIFACT_SCHEMAS:
            required.update({"schema_version", "declared_hashes"})
        if (
            not isinstance(binding, Mapping)
            or set(binding) != required
            or not isinstance(binding.get("basename"), str)
            or not binding.get("basename")
            or isinstance(binding.get("size_bytes"), bool)
            or not isinstance(binding.get("size_bytes"), int)
            or int(binding["size_bytes"]) < 1
            or any(not _is_sha256(binding.get(key)) for key in ("raw_sha256", "canonical_sha256"))
            or (
                name in _ARTIFACT_SCHEMAS
                and binding.get("schema_version") != _ARTIFACT_SCHEMAS[name]
            )
        ):
            raise PriorExposureRefusal("c800 artifact binding drifted")
        if name in _ARTIFACT_SCHEMAS:
            declared_hashes = binding.get("declared_hashes")
            if (
                not isinstance(declared_hashes, Mapping)
                or set(declared_hashes) != set(_ARTIFACT_SELF_HASHES[name])
                or any(not _is_sha256(item) for item in declared_hashes.values())
            ):
                raise PriorExposureRefusal("c800 artifact self-hash binding drifted")
            if binding.get("raw_sha256") != _ARTIFACT_RAW_SHA256[name]:
                raise PriorExposureRefusal("c800 artifact raw identity drifted")
        elif binding.get("raw_sha256") != _FROZEN_JSON_RAW_SHA256[name]:
            raise PriorExposureRefusal("c800 predecessor artifact identity drifted")
    databases = value.get("database_snapshots")
    if not isinstance(databases, Mapping) or set(databases) != {"attempt", "spool"}:
        raise PriorExposureRefusal("c800 database binding inventory drifted")
    for label in ("attempt", "spool"):
        _verify_database_snapshot(databases[label], label)
        members = databases[label]["members"]
        if {
            member: members[member]["sha256"] for member in ("main", "wal")
        } != _DATABASE_MEMBER_SHA256[label]:
            raise PriorExposureRefusal("c800 database member identity drifted")
    return str(declared)


def verify_c800_incident_exposure(value: Mapping[str, object]) -> str:
    declared = _verify_c800_incident_unpinned(value)
    if not _is_sha256(C800_INCIDENT_RECEIPT_SHA256):
        raise PriorExposureRefusal("c800 incident authority is not pinned")
    if declared != C800_INCIDENT_RECEIPT_SHA256:
        raise PriorExposureRefusal("c800 incident receipt identity drifted")
    return declared


def build_c800_incident_exposure(
    *,
    prior_exposure_receipt: Path,
    predecessor_successor_exposure_set: Path,
    predecessor_selection_receipt: Path,
    artifact_paths: Mapping[str, Path],
    attempt_db: Path,
    spool_db: Path,
    hswm_root: Path,
    symposium_root: Path,
    producer_hswm_root: Path,
    job_command: Path,
    job_log: Path,
    job_rc: Path,
    systemd_journal: Path,
    runner_command: Path,
    post_oom_runner_log: Path,
    post_oom_spool_log: Path,
) -> dict[str, object]:
    if set(artifact_paths) != set(_ARTIFACT_SCHEMAS):
        raise PriorExposureRefusal("c800 artifact path inventory drifted")
    runtime_authority = {
        "hswm": _git_authority(hswm_root, C800_HSWM_COMMIT, "c800 HSWM"),
        "symposium": _git_authority(
            symposium_root, C800_SYMPOSIUM_COMMIT, "c800 SYMPOSIUM"
        ),
    }
    if (
        runtime_authority["hswm"]["tree"] != C800_HSWM_TREE
        or runtime_authority["symposium"]["tree"] != C800_SYMPOSIUM_TREE
    ):
        raise PriorExposureRefusal("c800 runtime Git tree drifted")
    producer_authority = _producer_authority(producer_hswm_root)

    prior = _read_json(prior_exposure_receipt, "prior exposure receipt")
    predecessor_set = _read_json(
        predecessor_successor_exposure_set, "predecessor successor exposure set"
    )
    predecessor_selection = _read_json(
        predecessor_selection_receipt, "predecessor selection receipt"
    )
    prior_sha = verify_prior_exposure_receipt(prior)
    predecessor_set_sha = verify_f1_r8_successor_exposure_set(predecessor_set)

    artifact_values: dict[str, dict[str, object]] = {}
    bindings: dict[str, dict[str, object]] = {}
    for name in sorted(_ARTIFACT_SCHEMAS):
        value, binding = _json_binding(
            Path(artifact_paths[name]), name, _ARTIFACT_SCHEMAS[name]
        )
        if binding["raw_sha256"] != _ARTIFACT_RAW_SHA256[name]:
            raise PriorExposureRefusal(f"c800 {name} raw identity drifted")
        artifact_values[name] = value
        bindings[name] = binding

    # Local import avoids the selection-v5 -> prior-exposure import cycle.
    from prom_search_hswm.prom9_f1_r8_selection_v5 import replay_selection_receipt_v5

    selection = artifact_values["selection_receipt"]
    selection_sha = replay_selection_receipt_v5(
        selection,
        prior_receipt=prior,
        successor_exposure_set=predecessor_set,
        predecessor_selection=predecessor_selection,
    )
    manifest = artifact_values["manifest"]
    source = artifact_values["source_receipt"]
    evaluator = artifact_values["evaluator_receipt"]
    lock = artifact_values["execution_lock"]
    genesis = artifact_values["db_genesis_receipt"]
    environment = artifact_values["environment_dependency_bundle"]
    deployment = artifact_values["model_deployment_receipt"]
    preflight = artifact_values["spool_identity_receipt"]
    source_sha = verify_public_source_receipt(source)
    evaluator_sha = verify_evaluator_seal(evaluator)
    compatibility_root = _verify_c800_environment_authority(
        environment,
        hswm_root=hswm_root,
        symposium_root=symposium_root,
        lock=lock,
        model_deployment_raw_sha256=str(
            bindings["model_deployment_receipt"]["raw_sha256"]
        ),
    )
    deployment_verified = validate_deployment_receipt(
        deployment,
        verify_snapshot=False,
        verify_live_process=False,
    )
    manifest_sha = canonical_sha256(manifest)
    development = selection.get("development")
    if not isinstance(development, Mapping):
        raise PriorExposureRefusal("c800 development cohort is absent")
    selected_item_ids = development.get("item_ids")
    if (
        not isinstance(selected_item_ids, list)
        or selected_item_ids != sorted(set(selected_item_ids))
        or any(not isinstance(value, str) or not value for value in selected_item_ids)
    ):
        raise PriorExposureRefusal("c800 development item identity drifted")
    metadata = _source_metadata(manifest, source)
    cohort_root = canonical_sha256(selected_item_ids)
    environment_receipt = environment.get("environment_receipt")
    dependency_receipt = environment.get("dependency_receipt")
    if not isinstance(environment_receipt, Mapping) or not isinstance(
        dependency_receipt, Mapping
    ):
        raise PriorExposureRefusal("c800 environment subreceipts are absent")
    environment_sha = environment_receipt.get("receipt_sha256")
    dependency_sha = dependency_receipt.get("receipt_sha256")
    server_process = deployment_verified.get("server_process")
    snapshot = deployment_verified.get("snapshot")
    if not isinstance(server_process, Mapping) or not isinstance(snapshot, Mapping):
        raise PriorExposureRefusal("c800 deployment process authority is absent")
    expected_upstream = f"{str(deployment_verified.get('endpoint')).rstrip('/')}/chat/completions"
    if (
        manifest.get("run_id") != C800_RUN_ID
        or manifest.get("mode") != "development"
        or manifest.get("model") != C800_MODEL
        or manifest.get("model_revision") != C800_MODEL_REVISION
        or source.get("dataset") != "framolfese/2WikiMultihopQA"
        or source.get("config") != "default"
        or source.get("split") != "train"
        or source.get("public_selection_receipt_sha256") != selection_sha
        or set(metadata) != set(selected_item_ids)
        or evaluator.get("run_id") != C800_RUN_ID
        or evaluator.get("public_selection_receipt_sha256") != selection_sha
        or evaluator.get("public_source_receipt_sha256") != source_sha
        or evaluator.get("raw_source_sha256") != source.get("raw_source_sha256")
        or evaluator.get("cohort_root_sha256") != cohort_root
        or evaluator.get("answers_inspected_by_operator") is not False
        or lock.get("run_id") != C800_RUN_ID
        or lock.get("mode") != "development"
        or lock.get("purpose") != "DEVELOPMENT_POWER_PILOT"
        or lock.get("selection_receipt_sha256") != selection_sha
        or lock.get("prior_exposure_receipt_sha256") != prior_sha
        or lock.get("aborted_attempt_exposure_receipt_sha256")
        != predecessor_set_sha
        or lock.get("manifest_sha256") != manifest_sha
        or lock.get("public_source_receipt_sha256") != source_sha
        or lock.get("evaluator_receipt_sha256") != evaluator_sha
        or lock.get("cohort_root_sha256") != cohort_root
        or lock.get("gold_source_receipt_sha256")
        != evaluator.get("gold_source_receipt_sha256")
        or lock.get("gold_sha256") != evaluator.get("gold_sha256")
        or lock.get("db_genesis_receipt_sha256") != genesis.get("genesis_sha256")
        or lock.get("environment_dependency_bundle_sha256")
        != environment.get("bundle_sha256")
        or lock.get("environment_dependency_compatibility_root_sha256")
        != compatibility_root
        or lock.get("environment_receipt_sha256") != environment_sha
        or lock.get("dependency_receipt_sha256") != dependency_sha
        or lock.get("deployment_receipt_sha256")
        != deployment_verified.get("receipt_sha256")
        or lock.get("deployment_id") != deployment_verified.get("deployment_id")
        or lock.get("model") != deployment_verified.get("served_model")
        or lock.get("served_model") != deployment_verified.get("served_model")
        or lock.get("model_revision") != snapshot.get("resolved_revision")
        or expected_upstream != C800_UPSTREAM_ENDPOINT
        or lock.get("upstream_endpoint") != expected_upstream
        or lock.get("hswm_commit") != C800_HSWM_COMMIT
        or lock.get("judge_core_sha256") != C800_JUDGE_CORE_SHA256
        or lock.get("judge_core_file_sha256") != C800_JUDGE_CORE_FILE_SHA256
        or genesis.get("run_id") != C800_RUN_ID
        or genesis.get("attempt_integrity") != "ok"
        or genesis.get("spool_integrity") != "ok"
        or str(genesis.get("attempt_journal_mode", "")).casefold() != "wal"
        or str(genesis.get("spool_journal_mode", "")).casefold() != "wal"
        or genesis.get("attempt_audit_connection_synchronous") != "2"
        or genesis.get("spool_audit_connection_synchronous") != "2"
        or genesis.get("attempt_user_version") != 1
        or genesis.get("spool_user_version") != 1
        or any(
            genesis.get(field) != 0
            for field in (
                "call_count",
                "item_run_count",
                "attempt_event_count",
                "spool_call_count",
            )
        )
        or preflight.get("run_id") != C800_RUN_ID
        or preflight.get("execution_lock_sha256") != lock.get("lock_sha256")
        or preflight.get("db_genesis_sha256") != genesis.get("genesis_sha256")
        or preflight.get("upstream_endpoint") != expected_upstream
        or preflight.get("deployment_receipt_sha256")
        != deployment_verified.get("receipt_sha256")
        or preflight.get("deployment_id") != deployment_verified.get("deployment_id")
        or preflight.get("served_model") != deployment_verified.get("served_model")
        or preflight.get("model_revision") != snapshot.get("resolved_revision")
        or not isinstance(preflight.get("endpoint"), str)
        or preflight.get("endpoint") != C800_SPOOL_ENDPOINT
        or not isinstance(lock.get("execution_policy"), Mapping)
        or lock["execution_policy"].get("endpoint") != C800_SPOOL_ENDPOINT
        or preflight.get("endpoint") != lock["execution_policy"].get("endpoint")
    ):
        raise PriorExposureRefusal("c800 artifact graph drifted")
    if (
        server_process.get("pid") != 1025995
        or server_process.get("model_reference") != "Qwen/Qwen3.6-27B"
        or server_process.get("revision_binding") != snapshot.get("resolved_revision")
        or server_process.get("served_alias") != deployment_verified.get("served_model")
        or server_process.get("served_alias_explicit") is not True
    ):
        raise PriorExposureRefusal("c800 deployment process binding drifted")

    expected_prompts = _registry_prompt_authority(environment, manifest, lock)
    expected_prompt_keys = {
        (arm, contract[0])
        for arm in _ARMS
        for contract in _CALL_CONTRACTS.values()
    }
    if set(expected_prompts) != expected_prompt_keys:
        raise PriorExposureRefusal("c800 registry prompt inventory drifted")

    endpoint_identity = preflight.get("endpoint_identity")
    if not isinstance(endpoint_identity, Mapping):
        raise PriorExposureRefusal("c800 spool endpoint identity is absent")
    identity_unsigned = dict(endpoint_identity)
    identity_sha = identity_unsigned.pop("identity_sha256", None)
    audit = endpoint_identity.get("audit")
    if not isinstance(audit, Mapping):
        raise PriorExposureRefusal("c800 spool preflight audit is absent")
    audit_unsigned = dict(audit)
    audit_sha = audit_unsigned.pop("audit_sha256", None)
    empty_root = canonical_sha256([])
    if (
        set(endpoint_identity)
        != {
            "schema_version",
            "normalized_upstream_endpoint",
            "deployment_receipt_sha256",
            "deployment_id",
            "served_model",
            "model_revision",
            "db_identity",
            "audit",
            "identity_sha256",
        }
        or not _is_sha256(identity_sha)
        or canonical_sha256(identity_unsigned) != identity_sha
        or endpoint_identity.get("normalized_upstream_endpoint") != expected_upstream
        or endpoint_identity.get("deployment_receipt_sha256")
        != deployment_verified.get("receipt_sha256")
        or endpoint_identity.get("deployment_id")
        != deployment_verified.get("deployment_id")
        or endpoint_identity.get("served_model")
        != deployment_verified.get("served_model")
        or endpoint_identity.get("model_revision") != snapshot.get("resolved_revision")
        or endpoint_identity.get("db_identity") != genesis.get("spool_db_identity")
        or set(audit)
        != {
            "schema_version",
            "journal_mode",
            "synchronous",
            "call_count",
            "status_counts",
            "completed_root_sha256",
            "audit_sha256",
        }
        or not _is_sha256(audit_sha)
        or canonical_sha256(audit_unsigned) != audit_sha
        or audit.get("schema_version") != "hswm-f1-result-spool/v1"
        or str(audit.get("journal_mode", "")).casefold() != "wal"
        or audit.get("synchronous") != 2
        or audit.get("call_count") != 0
        or audit.get("status_counts") != {}
        or audit.get("completed_root_sha256") != empty_root
    ):
        raise PriorExposureRefusal("c800 spool preflight graph drifted")

    structural = _read_structural_observations(
        attempt_db,
        spool_db,
        manifest=manifest,
        spool_endpoint=C800_SPOOL_ENDPOINT,
        expected_prompts=expected_prompts,
    )
    # Genesis path/device/inode identify the original Dell files and therefore
    # cannot survive an intentional forensic relocation.  Relocated inputs are
    # authorized by the canonical schema plus the pinned main/WAL hashes below.
    for label, schema_key in (
        ("attempt", "attempt_schema_sha256"),
        ("spool", "spool_schema_sha256"),
    ):
        if (
            structural["database_snapshots"][label][
                "canonical_schema_sha256"
            ]
            != genesis.get(schema_key)
        ):
            raise PriorExposureRefusal("c800 database/genesis binding drifted")
        members = structural["database_snapshots"][label].get("members")
        if (
            not isinstance(members, Mapping)
            or {
                member: members[member].get("sha256")
                for member in ("main", "wal")
                if isinstance(members.get(member), Mapping)
            }
            != _DATABASE_MEMBER_SHA256[label]
        ):
            raise PriorExposureRefusal("c800 database member identity drifted")
    exposed_items = list(structural["observed_item_ids"])
    aggregate = _exposure_aggregate(metadata, exposed_items)
    if not set(exposed_items).issubset(set(selected_item_ids)):
        raise PriorExposureRefusal("c800 model exposure is outside the frozen cohort")

    rc_raw = _read_stable_bytes(job_rc, max_bytes=32)
    try:
        rc_value = int(rc_raw.decode("ascii").strip())
    except (UnicodeError, ValueError) as error:
        raise PriorExposureRefusal("c800 job rc is malformed") from error
    job_log_raw = _read_stable_bytes(job_log)
    journal_raw = _read_stable_bytes(systemd_journal, max_bytes=1024 * 1024)
    runner_raw = _read_stable_bytes(runner_command, max_bytes=1024 * 1024)
    runner_refusal_raw = _read_stable_bytes(
        post_oom_runner_log, max_bytes=1024 * 1024
    )
    spool_refusal_raw = _read_stable_bytes(post_oom_spool_log, max_bytes=1024 * 1024)
    job_command_raw = _read_stable_bytes(job_command, max_bytes=1024 * 1024)
    required_job_fragments = (
        b"--model=Qwen/Qwen3.6-27B",
        b"--revision=6a9e13bd6fc8f0983b9b99948120bc37f49c13e9",
        b"--host=127.0.0.1",
        b"--port=8100",
        b"--served-model-name=qwen3.6-27b",
        b"--attention-backend=TRITON_ATTN",
    )
    if (
        rc_value != 143
        or any(fragment not in job_command_raw for fragment in required_job_fragments)
        or b"=== EXIT rc=143" not in job_log_raw
        or b"(APIServer pid=1025995)" not in job_log_raw
        or b"model   Qwen/Qwen3.6-27B" not in job_log_raw
        or b"served_model_name=qwen3.6-27b" not in job_log_raw
        or b"dt-hswm-f1-r8-vllm-canary-triton-1025982.scope" not in journal_raw
        or b"kernel OOM killer killed some processes in this unit" not in journal_raw
        or b"Failed with result 'oom-kill'" not in journal_raw
        or C800_RUN_ID.encode() not in runner_raw
        or b"ROOT=/data/kjra/PROJECT/PI/hswm_f1_r8_c800_20260805" not in runner_raw
        or b"--attempt-db" not in runner_raw
        or b"--spool-db" not in runner_raw
        or b"spool died during startup" not in runner_refusal_raw
        or b"model deployment receipt verification failed" not in spool_refusal_raw
    ):
        raise PriorExposureRefusal("c800 deployment-loss evidence does not corroborate")

    def json_evidence_binding(path: Path, label: str) -> dict[str, object]:
        raw = _read_stable_bytes(path, max_bytes=512 * 1024 * 1024)
        try:
            value = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise PriorExposureRefusal("c800 JSON evidence is malformed") from error
        binding = {
            "basename": Path(path).name,
            "size_bytes": len(raw),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "canonical_sha256": canonical_sha256(value),
        }
        if binding["raw_sha256"] != _FROZEN_JSON_RAW_SHA256[label]:
            raise PriorExposureRefusal(f"c800 {label} identity drifted")
        return binding

    bindings.update(
        {
            "prior_exposure_receipt": json_evidence_binding(
                prior_exposure_receipt,
                "prior_exposure_receipt",
            ),
            "predecessor_successor_exposure_set": json_evidence_binding(
                predecessor_successor_exposure_set,
                "predecessor_successor_exposure_set",
            ),
            "predecessor_selection_receipt": json_evidence_binding(
                predecessor_selection_receipt,
                "predecessor_selection_receipt",
            ),
        }
    )
    unsigned = {
        "schema_version": C800_INCIDENT_EXPOSURE_SCHEMA,
        "status": ABORTED_ATTEMPT_STATUS,
        "run_identity": {
            "run_id": C800_RUN_ID,
            "hswm_commit": C800_HSWM_COMMIT,
            "symposium_commit": C800_SYMPOSIUM_COMMIT,
        },
        "runtime_authority": runtime_authority,
        "producer_authority": producer_authority,
        "termination": {
            "classification": "MODEL_DEPLOYMENT_KERNEL_OOM",
            "systemd_unit": "dt-hswm-f1-r8-vllm-canary-triton-1025982.scope",
            "systemd_result": "oom-kill",
            "wrapper_exit_code": rc_value,
            "server_pid": int(server_process["pid"]),
            "deployment_id": deployment_verified["deployment_id"],
            "deployment_endpoint": deployment_verified["endpoint"],
            "job_command": _frozen_evidence_binding(job_command, "job_command"),
            "job_log": _frozen_evidence_binding(job_log, "job_log"),
            "job_rc": _frozen_evidence_binding(job_rc, "job_rc"),
            "systemd_journal": _frozen_evidence_binding(
                systemd_journal, "systemd_journal"
            ),
            "runner_command": _frozen_evidence_binding(
                runner_command, "runner_command"
            ),
            "post_oom_runner_log": _frozen_evidence_binding(
                post_oom_runner_log, "post_oom_runner_log"
            ),
            "post_oom_spool_log": _frozen_evidence_binding(
                post_oom_spool_log, "post_oom_spool_log"
            ),
        },
        "capture_policy": {
            "sqlite_authority_members": ["main", "wal"],
            "sqlite_shm_authoritative": False,
            "sqlite_snapshotted_before_replay": True,
            "response_blob_columns_read": False,
            "item_run_blob_columns_read": False,
            "gold_inputs_accepted": False,
            "model_calls_invoked": False,
            "kg_accessed": False,
            "raw_attempt_states_preserved": True,
            "pre_dispatch_rejection_counts_as_model_call": False,
        },
        "artifact_bindings": bindings,
        "database_snapshots": structural["database_snapshots"],
        "counts": structural["counts"],
        "pre_dispatch_rejections": [structural["rejection"]],
        "aggregate": aggregate,
        "successor_disposition": {
            "forensic_only": True,
            "resume_authorized": False,
            "successor_required": True,
            "successor_run_id": C801_DEVELOPMENT_RUN_ID,
            "legacy_database_mutation_authorized": False,
            "legacy_database_import_authorized": False,
            "accepted_result_import_authorized": False,
        },
        "complete": True,
    }
    result = {**unsigned, "c800_incident_receipt_sha256": canonical_sha256(unsigned)}
    _verify_c800_incident_unpinned(result)
    return result


def _merged_aggregate(*aggregates: Mapping[str, object]) -> dict[str, object]:
    items: set[str] = set()
    sources: set[str] = set()
    components: set[str] = set()
    for aggregate in aggregates:
        verified = _verify_exposure_aggregate(aggregate)
        items.update(str(value) for value in verified["prior_item_ids"])
        sources.update(str(value) for value in verified["prior_source_entity_ids"])
        components.update(str(value) for value in verified["prior_component_ids"])
    values = {
        "prior_item_ids": sorted(items),
        "prior_source_entity_ids": sorted(sources),
        "prior_component_ids": sorted(components),
    }
    return {
        **values,
        "item_root_sha256": canonical_sha256(values["prior_item_ids"]),
        "source_entity_root_sha256": canonical_sha256(values["prior_source_entity_ids"]),
        "component_root_sha256": canonical_sha256(values["prior_component_ids"]),
    }


def _verify_successor_v2_unpinned(value: Mapping[str, object]) -> str:
    fields = {
        "schema_version",
        "predecessor_exposure_set",
        "predecessor_exposure_set_sha256",
        "c800_incident",
        "c800_incident_sha256",
        "counts",
        "aggregate",
        "successor_disposition",
        "complete",
        "aborted_attempt_exposure_receipt_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise PriorExposureRefusal("c801 successor exposure-set shape drifted")
    unsigned = dict(value)
    declared = unsigned.pop("aborted_attempt_exposure_receipt_sha256", None)
    predecessor = value.get("predecessor_exposure_set")
    incident = value.get("c800_incident")
    if (
        value.get("schema_version") != F1_R8_SUCCESSOR_EXPOSURE_SET_SCHEMA_V2
        or value.get("complete") is not True
        or not _is_sha256(declared)
        or canonical_sha256(unsigned) != declared
        or not isinstance(predecessor, Mapping)
        or not isinstance(incident, Mapping)
    ):
        raise PriorExposureRefusal("c801 successor exposure-set identity drifted")
    predecessor_sha = verify_f1_r8_successor_exposure_set(predecessor)
    incident_sha = _verify_c800_incident_unpinned(incident)
    if (
        value.get("predecessor_exposure_set_sha256") != predecessor_sha
        or value.get("c800_incident_sha256") != incident_sha
    ):
        raise PriorExposureRefusal("c801 successor member binding drifted")
    predecessor_aggregate = verified_aborted_attempt_aggregate(predecessor)
    incident_aggregate = _verify_exposure_aggregate(incident.get("aggregate"))
    expected_aggregate = _merged_aggregate(predecessor_aggregate, incident_aggregate)
    if value.get("aggregate") != expected_aggregate:
        raise PriorExposureRefusal("c801 successor exposure aggregate drifted")
    counts = value.get("counts")
    if counts != {
        "incidents": 3,
        "predecessor_upstream_model_calls": 27,
        "c800_upstream_model_calls": 647,
        "pre_dispatch_rejections": 1,
        "upstream_model_calls": 674,
    }:
        raise PriorExposureRefusal("c801 successor call counts drifted")
    if value.get("successor_disposition") != {
        "historical_v8_quarantined": True,
        "a2_quarantined": True,
        "c800_quarantined": True,
        "resume_authorized": False,
        "successor_required": True,
        "successor_must_start_zero": True,
        "successor_run_id": C801_DEVELOPMENT_RUN_ID,
        "legacy_database_mutation_authorized": False,
        "legacy_database_import_authorized": False,
        "accepted_result_import_authorized": False,
    }:
        raise PriorExposureRefusal("c801 successor disposition drifted")
    return str(declared)


def verify_f1_r8_successor_exposure_set_v2(value: Mapping[str, object]) -> str:
    declared = _verify_successor_v2_unpinned(value)
    incident = value.get("c800_incident")
    assert isinstance(incident, Mapping)
    verify_c800_incident_exposure(incident)
    return declared


def build_f1_r8_successor_exposure_set_v2(
    predecessor_exposure_set: Mapping[str, object],
    c800_incident: Mapping[str, object],
) -> dict[str, object]:
    predecessor_sha = verify_f1_r8_successor_exposure_set(predecessor_exposure_set)
    incident_sha = verify_c800_incident_exposure(c800_incident)
    predecessor_aggregate = verified_aborted_attempt_aggregate(predecessor_exposure_set)
    incident_aggregate = _verify_exposure_aggregate(c800_incident.get("aggregate"))
    unsigned = {
        "schema_version": F1_R8_SUCCESSOR_EXPOSURE_SET_SCHEMA_V2,
        "predecessor_exposure_set": dict(predecessor_exposure_set),
        "predecessor_exposure_set_sha256": predecessor_sha,
        "c800_incident": dict(c800_incident),
        "c800_incident_sha256": incident_sha,
        "counts": {
            "incidents": 3,
            "predecessor_upstream_model_calls": 27,
            "c800_upstream_model_calls": 647,
            "pre_dispatch_rejections": 1,
            "upstream_model_calls": 674,
        },
        "aggregate": _merged_aggregate(predecessor_aggregate, incident_aggregate),
        "successor_disposition": {
            "historical_v8_quarantined": True,
            "a2_quarantined": True,
            "c800_quarantined": True,
            "resume_authorized": False,
            "successor_required": True,
            "successor_must_start_zero": True,
            "successor_run_id": C801_DEVELOPMENT_RUN_ID,
            "legacy_database_mutation_authorized": False,
            "legacy_database_import_authorized": False,
            "accepted_result_import_authorized": False,
        },
        "complete": True,
    }
    result = {
        **unsigned,
        "aborted_attempt_exposure_receipt_sha256": canonical_sha256(unsigned),
    }
    verify_f1_r8_successor_exposure_set_v2(result)
    return result


def verified_c801_exposure_aggregate(value: Mapping[str, object]) -> dict[str, object]:
    verify_f1_r8_successor_exposure_set_v2(value)
    return _verify_exposure_aggregate(value.get("aggregate"))


def merge_c801_exposure_boundaries(
    prior: Mapping[str, object], successor_v2: Mapping[str, object]
) -> dict[str, object]:
    prior_sha = verify_prior_exposure_receipt(prior)
    successor_sha = verify_f1_r8_successor_exposure_set_v2(successor_v2)
    prior_aggregate = prior.get("aggregate")
    if not isinstance(prior_aggregate, Mapping):
        raise PriorExposureRefusal("prior exposure aggregate is absent")
    normalized_prior = {
        "prior_item_ids": list(prior_aggregate.get("prior_item_ids", [])),
        "prior_source_entity_ids": list(
            prior_aggregate.get("prior_source_entity_ids", [])
        ),
        "prior_component_ids": list(prior_aggregate.get("prior_component_ids", [])),
        "item_root_sha256": prior_aggregate.get("item_root_sha256"),
        "source_entity_root_sha256": prior_aggregate.get(
            "source_entity_root_sha256"
        ),
        "component_root_sha256": prior_aggregate.get("component_root_sha256"),
    }
    merged = _merged_aggregate(
        _verify_exposure_aggregate(normalized_prior),
        verified_c801_exposure_aggregate(successor_v2),
    )
    return {
        "prior_exposure_receipt_sha256": prior_sha,
        "aborted_attempt_exposure_receipt_sha256": successor_sha,
        "item_ids": merged["prior_item_ids"],
        "source_entity_ids": merged["prior_source_entity_ids"],
        "component_ids": merged["prior_component_ids"],
        "item_root_sha256": merged["item_root_sha256"],
        "source_entity_root_sha256": merged["source_entity_root_sha256"],
        "component_root_sha256": merged["component_root_sha256"],
    }


def _artifact_arg(value: str) -> tuple[str, Path]:
    name, separator, raw_path = value.partition(":")
    if not separator or name not in _ARTIFACT_SCHEMAS:
        raise argparse.ArgumentTypeError("expected ARTIFACT_NAME:PATH")
    return name, Path(raw_path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    incident = subparsers.add_parser("build-c800-incident")
    incident.add_argument("--prior-exposure-receipt", type=Path, required=True)
    incident.add_argument("--predecessor-successor-exposure-set", type=Path, required=True)
    incident.add_argument("--predecessor-selection-receipt", type=Path, required=True)
    incident.add_argument("--artifact", action="append", type=_artifact_arg, required=True)
    incident.add_argument("--attempt-db", type=Path, required=True)
    incident.add_argument("--spool-db", type=Path, required=True)
    incident.add_argument("--hswm-root", type=Path, required=True)
    incident.add_argument("--symposium-root", type=Path, required=True)
    incident.add_argument("--producer-hswm-root", type=Path, required=True)
    incident.add_argument("--job-command", type=Path, required=True)
    incident.add_argument("--job-log", type=Path, required=True)
    incident.add_argument("--job-rc", type=Path, required=True)
    incident.add_argument("--systemd-journal", type=Path, required=True)
    incident.add_argument("--runner-command", type=Path, required=True)
    incident.add_argument("--post-oom-runner-log", type=Path, required=True)
    incident.add_argument("--post-oom-spool-log", type=Path, required=True)
    incident.add_argument("--output", type=Path, required=True)
    wrapper = subparsers.add_parser("build-successor-v2")
    wrapper.add_argument("--predecessor-successor-exposure-set", type=Path, required=True)
    wrapper.add_argument("--c800-incident", type=Path, required=True)
    wrapper.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build-c800-incident":
            artifacts = dict(args.artifact)
            if len(artifacts) != len(args.artifact):
                raise PriorExposureRefusal("duplicate c800 artifact argument")
            result = build_c800_incident_exposure(
                prior_exposure_receipt=args.prior_exposure_receipt,
                predecessor_successor_exposure_set=(
                    args.predecessor_successor_exposure_set
                ),
                predecessor_selection_receipt=args.predecessor_selection_receipt,
                artifact_paths=artifacts,
                attempt_db=args.attempt_db,
                spool_db=args.spool_db,
                hswm_root=args.hswm_root,
                symposium_root=args.symposium_root,
                producer_hswm_root=args.producer_hswm_root,
                job_command=args.job_command,
                job_log=args.job_log,
                job_rc=args.job_rc,
                systemd_journal=args.systemd_journal,
                runner_command=args.runner_command,
                post_oom_runner_log=args.post_oom_runner_log,
                post_oom_spool_log=args.post_oom_spool_log,
            )
            write_private_once(args.output, result)
            print(
                json.dumps(
                    {
                        "status": "C800_QUARANTINED",
                        "receipt_sha256": result[
                            "c800_incident_receipt_sha256"
                        ],
                    },
                    sort_keys=True,
                )
            )
            return 0
        predecessor = _read_json(
            args.predecessor_successor_exposure_set,
            "predecessor successor exposure set",
        )
        c800 = _read_json(args.c800_incident, "c800 incident")
        result = build_f1_r8_successor_exposure_set_v2(predecessor, c800)
        write_private_once(args.output, result)
        print(
            json.dumps(
                {
                    "status": "C801_SUCCESSOR_REQUIRED",
                    "receipt_sha256": result[
                        "aborted_attempt_exposure_receipt_sha256"
                    ],
                },
                sort_keys=True,
            )
        )
        return 0
    except PriorExposureRefusal as error:
        print(
            json.dumps({"status": "REFUSED", "reason": str(error)}, sort_keys=True),
            file=sys.stderr,
        )
        return 1
    except Exception:
        print(json.dumps({"status": "REFUSED"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
