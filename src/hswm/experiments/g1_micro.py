"""Smallest executable outcome-bound HSWM learning slice.

This module is deliberately narrower than a G1 gate.  It runs one opaque-cue
episode through a sealed model trajectory, locally computed evaluator feedback,
one bounded disposition proposal, local one-shot authorization, durable state,
and a fresh behavior call.  It also exposes sham, no-update, removal, and exact
state-restoration observations.

The in-process guard and state are experiment-local.  They are not an Atom v2
Permit, a repository-canonical HSWM admission, or evidence of G1 efficacy.
"""

from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from hswm.experiments.continual_live import (
    ArmBudget,
    ChatBackend,
    ContinualLiveError,
    JSONSchemaContract,
    OpenAIBackendConfig,
    OpenAICompatibleBackend,
    TokenPreflightReceipt,
    _ModelArm,
)
from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256


PROTOCOL = "hswm-g1-micro-exploratory/v1"
STATE_SCHEMA = "hswm-g1-micro-disposition-state/v1"
RECORD_SCHEMA_PREFIX = "hswm-g1-micro-record/"
LOCAL_SCOPE_NONCLAIM = (
    "LOCAL_EXPERIMENTAL_AUTHORIZATION_ONLY;NOT_CANONICAL_ATOM_V2_PERMIT;"
    "NOT_CANONICAL_HSWM_ADMISSION;NOT_G1_GATE_DECISION_OR_EFFICACY"
)
DGX_NETWORK_BOUNDARY = (
    "HOST_INGRESS_LOOPBACK_BOUND;CONTAINER_BRIDGE_EGRESS_NOT_INDEPENDENTLY_BLOCKED"
)
DGX_TRACKED_SOURCE_PATHS = (
    "_research/causal_composition/preregistrations/"
    "g1_micro_exploratory_2026-08-30/protocol.v1.json",
    "src/hswm/experiments/continual_live.py",
    "src/hswm/experiments/g1_micro.py",
    "src/hswm/experiments/g1_micro_dgx.py",
    "src/hswm/selfmod/contracts.py",
)
TERMINALS = frozenset(
    {
        "INCONCLUSIVE_MEASUREMENT_NOT_READY",
        "EXPLORATORY_OBSERVATION_RECORDED_NO_EFFICACY_INFERENCE",
    }
)
OPERATORS = ("ADD_THREE", "MULTIPLY_THREE")
HEX64 = re.compile(r"[0-9a-f]{64}")
DISPOSITION_OWNER = "principal:g1-micro-disposition-owner"
STATE_OWNER = "principal:g1-micro-state-custodian"
PRINCIPALS = {
    "authorizer_uid": "principal:g1-micro-local-authorizer",
    "credit_adjudicator_uid": "principal:g1-micro-credit-adjudicator",
    "executor_uid": "principal:g1-micro-transition-executor",
    "outcome_evaluator_uid": "principal:g1-micro-outcome-evaluator",
    "proposer_uid": "principal:g1-micro-model-proposer",
    "state_custodian_uid": STATE_OWNER,
}


class G1MicroError(RuntimeError):
    """Fail-closed error for the bounded exploratory slice."""


def _digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _source_manifest() -> dict[str, str]:
    experiment_dir = Path(__file__).resolve().parent
    source_root = experiment_dir.parent
    paths = {
        "src/hswm/experiments/continual_live.py": experiment_dir / "continual_live.py",
        "src/hswm/experiments/g1_micro.py": Path(__file__).resolve(),
        "src/hswm/selfmod/contracts.py": source_root / "selfmod/contracts.py",
    }
    return {name: _digest(path.read_bytes()) for name, path in paths.items()}


def _validate_source_manifest(value: object) -> None:
    expected_paths = {
        "src/hswm/experiments/continual_live.py",
        "src/hswm/experiments/g1_micro.py",
        "src/hswm/selfmod/contracts.py",
    }
    if not isinstance(value, Mapping) or set(value) != expected_paths:
        raise G1MicroError("source manifest field set drifted")
    for path, digest in value.items():
        if not isinstance(path, str):
            raise G1MicroError("source manifest path is invalid")
        _require_sha(digest, f"source manifest {path}")


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise G1MicroError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _canonical_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise G1MicroError(f"{label} is not UTF-8 JSON") from error
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise G1MicroError(f"{label} is not one canonical JSON object")
    return value


def make_record(
    kind: str,
    *,
    owner_uid: str,
    payload: Mapping[str, Any],
    refs: Sequence[Mapping[str, str]] = (),
) -> dict[str, Any]:
    """Create one content-addressed, single-owner local research record."""

    if not isinstance(kind, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{1,63}", kind):
        raise G1MicroError("record kind is invalid")
    if not isinstance(owner_uid, str) or not owner_uid:
        raise G1MicroError("record requires exactly one owner uid")
    normalized_refs = sorted(
        (dict(item) for item in refs),
        key=lambda item: (item.get("kind", ""), item.get("sha256", "")),
    )
    for item in normalized_refs:
        if set(item) != {"kind", "sha256"} or not isinstance(item["kind"], str):
            raise G1MicroError("record reference is malformed")
        _require_sha(item["sha256"], "record reference")
    if len({(item["kind"], item["sha256"]) for item in normalized_refs}) != len(
        normalized_refs
    ):
        raise G1MicroError("record references must be unique")
    unsigned = {
        "owner_uid": owner_uid,
        "payload": dict(payload),
        "refs": normalized_refs,
        "schema_version": f"{RECORD_SCHEMA_PREFIX}{kind}/v1",
        "scope_nonclaim": LOCAL_SCOPE_NONCLAIM,
    }
    return {**unsigned, "record_sha256": canonical_sha256(unsigned)}


def validate_record(value: Mapping[str, Any], *, kind: str | None = None) -> None:
    expected = {
        "owner_uid",
        "payload",
        "record_sha256",
        "refs",
        "schema_version",
        "scope_nonclaim",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise G1MicroError("local record field set is invalid")
    schema = value["schema_version"]
    if not isinstance(schema, str) or not schema.startswith(RECORD_SCHEMA_PREFIX):
        raise G1MicroError("local record schema is invalid")
    if kind is not None and schema != f"{RECORD_SCHEMA_PREFIX}{kind}/v1":
        raise G1MicroError(f"expected {kind} record")
    if value["scope_nonclaim"] != LOCAL_SCOPE_NONCLAIM:
        raise G1MicroError("local record exceeded its claim boundary")
    if not isinstance(value["owner_uid"], str) or not value["owner_uid"]:
        raise G1MicroError("local record owner is invalid")
    if not isinstance(value["payload"], Mapping) or not isinstance(value["refs"], list):
        raise G1MicroError("local record payload or references are invalid")
    unsigned = dict(value)
    digest = unsigned.pop("record_sha256")
    if digest != canonical_sha256(unsigned):
        raise G1MicroError("local record digest mismatch")
    rebuilt = make_record(
        schema.removeprefix(RECORD_SCHEMA_PREFIX).removesuffix("/v1"),
        owner_uid=value["owner_uid"],
        payload=value["payload"],
        refs=value["refs"],
    )
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(value):
        raise G1MicroError("local record is not in canonical normalized form")


def _ref(kind: str, record: Mapping[str, Any]) -> dict[str, str]:
    validate_record(record)
    return {"kind": kind, "sha256": str(record["record_sha256"])}


@dataclass(frozen=True, slots=True)
class MicroTask:
    """One opaque cue selecting one of two visible arithmetic operators."""

    study_uid: str
    episode_uid: str
    cue: str
    operand: int
    train_input: int
    fresh_input: int
    hidden_operator: str
    sham_correct: bool

    def __post_init__(self) -> None:
        if any(
            not isinstance(item, str) or not item
            for item in (self.study_uid, self.episode_uid, self.cue)
        ):
            raise G1MicroError("task identities must be non-empty")
        if self.operand != 3 or self.hidden_operator not in OPERATORS:
            raise G1MicroError("micro task permits only the frozen two-operator family")
        if any(
            isinstance(item, bool) or not isinstance(item, int) or not 2 <= item <= 100
            for item in (self.train_input, self.fresh_input)
        ):
            raise G1MicroError("task inputs are outside the bounded domain")
        if self.train_input == self.fresh_input or not isinstance(self.sham_correct, bool):
            raise G1MicroError("task requires distinct inputs and a boolean sham")
        for value in (self.train_input, self.fresh_input):
            if len(set(self.choices(value))) != 2:
                raise G1MicroError("candidate operators collide on a task input")

    def apply(self, value: int, operator: str) -> int:
        if operator == "ADD_THREE":
            return value + self.operand
        if operator == "MULTIPLY_THREE":
            return value * self.operand
        raise G1MicroError("unknown task operator")

    def choice(self, value: int, operator: str) -> str:
        return f"v_{self.apply(value, operator):04d}"

    def choices(self, value: int) -> tuple[str, str]:
        return tuple(sorted(self.choice(value, operator) for operator in OPERATORS))

    def operator_for_choice(self, value: int, choice: str) -> str:
        for operator in OPERATORS:
            if self.choice(value, operator) == choice:
                return operator
        raise G1MicroError("choice does not correspond to an allowed operator")

    def public(self) -> dict[str, Any]:
        return {
            "candidate_operators": list(OPERATORS),
            "cue": self.cue,
            "operand": self.operand,
            "study_uid": self.study_uid,
        }

    def canonical(self) -> dict[str, Any]:
        return {
            **self.public(),
            "episode_uid": self.episode_uid,
            "fresh_input": self.fresh_input,
            "hidden_operator": self.hidden_operator,
            "sham_correct": self.sham_correct,
            "train_input": self.train_input,
        }

    @property
    def commitment_sha256(self) -> str:
        return canonical_sha256(self.canonical())


def task_from_protocol(protocol: Mapping[str, Any]) -> MicroTask:
    if protocol.get("schema_version") != PROTOCOL:
        raise G1MicroError("unsupported G1 micro protocol")
    seed = _require_sha(protocol.get("episode_seed"), "episode seed")
    digest = sha256(f"{seed}:task".encode()).digest()
    hidden = OPERATORS[digest[0] % 2]
    sham = bool(sha256(f"{seed}:sham".encode()).digest()[0] % 2)
    return MicroTask(
        study_uid=str(protocol.get("study_uid", "")),
        episode_uid="episode:" + sha256(f"{seed}:episode".encode()).hexdigest()[:24],
        cue="cue_" + sha256(f"{seed}:cue".encode()).hexdigest()[:16],
        operand=3,
        train_input=7,
        fresh_input=11,
        hidden_operator=hidden,
        sham_correct=sham,
    )


def _validate_protocol(value: Mapping[str, Any]) -> None:
    """Validate the executable preregistration envelope, including API callers."""

    if value.get("schema_version") != PROTOCOL:
        raise G1MicroError("protocol schema mismatch")
    if value.get("scientific_status") != "EXPLORATORY_INTEGRATION_READINESS_NOT_G1_GATE":
        raise G1MicroError("protocol claim boundary drifted")
    if value.get("provider_call_cap") != 8:
        raise G1MicroError("protocol must bind the eight-call ceiling")
    if value.get("arms") != [
        "ACTIVE",
        "OUTCOME_INDEPENDENT_SHAM",
        "NO_UPDATE",
        "REMOVE",
        "RESTORE",
    ]:
        raise G1MicroError("protocol arm set or order drifted")
    if value.get("model_call_sequence") != [
        "pre_outcome_trajectory",
        "active_revision_proposal",
        "outcome_independent_sham_revision_proposal",
        "active_fresh_probe",
        "outcome_independent_sham_fresh_probe",
        "no_update_fresh_probe",
        "removed_state_fresh_probe",
        "restored_state_fresh_probe",
    ]:
        raise G1MicroError("protocol call sequence drifted")
    if value.get("nonclaim") != LOCAL_SCOPE_NONCLAIM:
        raise G1MicroError("protocol local nonclaim drifted")
    if value.get("research_order") != {
        "G0": "NOT_PASSED",
        "G1": "EXPLORATORY_INTEGRATION_READINESS_ONLY",
        "G2_THROUGH_G6": "LOCKED",
    }:
        raise G1MicroError("protocol research order drifted")
    if value.get("permit_policy") != {
        "grant_timing": "AFTER_OUTCOME_CREDIT_AND_EXACT_PROPOSAL_UNDER_PREOUTCOME_POLICY",
        "max_consumptions_per_grant": 1,
        "revision_kind": "OPAQUE_CUE_OPERATOR_DISPOSITION",
        "write_operation": "UPSERT_ONE_DISPOSITION",
        "write_target": "local:g1-micro-state:dispositions",
    }:
        raise G1MicroError("protocol local permit policy drifted")
    task_family = value.get("task_family")
    if not isinstance(task_family, Mapping) or any(
        task_family.get(key) != expected
        for key, expected in {
            "candidate_operators": list(OPERATORS),
            "fresh_input": 11,
            "operand": 3,
            "train_input": 7,
        }.items()
    ):
        raise G1MicroError("protocol task family drifted")
    analysis = value.get("analysis")
    if not isinstance(analysis, Mapping) or analysis.get("terminal_order") != [
        "INCONCLUSIVE_MEASUREMENT_NOT_READY",
        "EXPLORATORY_OBSERVATION_RECORDED_NO_EFFICACY_INFERENCE",
    ]:
        raise G1MicroError("protocol terminal order drifted")
    if (
        value.get("sham_equality_policy")
        != "SHAM_EQUALS_ACTIVE_FEEDBACK_IS_UNINFORMATIVE_NO_CONTROL_CONTRAST"
    ):
        raise G1MicroError("protocol sham-equality interpretation drifted")
    if not isinstance(value.get("study_uid"), str) or not value["study_uid"]:
        raise G1MicroError("protocol study uid is missing")
    _require_sha(value.get("episode_seed"), "episode seed")
    registry = value.get("consumption_registry")
    if (
        not isinstance(registry, Mapping)
        or set(registry) != {"boundary", "path"}
        or registry["boundary"]
        != "DGX_NODE_LOCAL_DURABLE_SINGLE_EXECUTION_NOT_DISTRIBUTED_CONSENSUS"
        or not isinstance(registry["path"], str)
        or not Path(registry["path"]).is_absolute()
        or ".." in Path(registry["path"]).parts
    ):
        raise G1MicroError("protocol consumption registry drifted")
    if value.get("http_post_accounting") != {
        "completion_posts": 8,
        "tokenize_preflight_posts": 8,
        "total_posts": 16,
    }:
        raise G1MicroError("protocol HTTP POST accounting drifted")
    binding = value.get("live_binding")
    if not isinstance(binding, Mapping) or set(binding) != {
        "async_scheduling",
        "container_image",
        "container_image_id",
        "enforce_eager",
        "endpoint_origin",
        "expected_max_model_len",
        "gpu_memory_utilization_milli",
        "gpu_name",
        "gpu_uuid",
        "max_num_seqs",
        "model_repository",
        "model_revision",
        "model_snapshot_manifest_sha256",
        "network_boundary",
        "prefix_cache",
        "served_model",
        "vllm_version",
    }:
        raise G1MicroError("protocol live binding is incomplete")
    if (
        binding["endpoint_origin"] != "http://127.0.0.1:18080"
        or binding["expected_max_model_len"] != 32_768
        or binding["served_model"] != "qwen3.6-35b-a3b"
        or binding["container_image"]
        != "vllm/vllm-openai@sha256:e4f88a835143cd22aee2397a26ec6bb8"
        "0b3a4a6fe0c882bcbc63822904766089"
        or binding["container_image_id"]
        != "sha256:30a38a1d74a17365eca400e83ffd885b250e0c8c0d3c5b508afa8c412d2ddf95"
        or binding["gpu_uuid"] != "GPU-ffed5bca-3452-8e9e-03fb-b2a4d8f40bc5"
        or binding["gpu_name"] != "NVIDIA GB10"
        or binding["gpu_memory_utilization_milli"] != 500
        or binding["max_num_seqs"] != 1
        or binding["prefix_cache"] is not False
        or binding["enforce_eager"] is not True
        or binding["async_scheduling"] is not False
        or binding["model_repository"] != "Qwen/Qwen3.6-35B-A3B-FP8"
        or binding["model_revision"]
        != "95a723d08a9490559dae23d0cff1d9466213d989"
        or binding["model_snapshot_manifest_sha256"]
        != "2ece6b46248e818cbf93aa30299300f7dd4c60d9351960ec790cc8b420376e47"
        or binding["network_boundary"] != DGX_NETWORK_BOUNDARY
        or binding["vllm_version"] != "0.25.1"
    ):
        raise G1MicroError("protocol live binding drifted")
    task_from_protocol(value)


def expected_dgx_server_argv(protocol: Mapping[str, Any]) -> list[str]:
    _validate_protocol(protocol)
    binding = protocol["live_binding"]
    revision = binding["model_revision"]
    return [
        "--model",
        f"/model-repository/snapshots/{revision}",
        "--served-model-name",
        binding["served_model"],
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--max-num-seqs",
        str(binding["max_num_seqs"]),
        "--no-enable-prefix-caching",
        "--max-model-len",
        str(binding["expected_max_model_len"]),
        "--gpu-memory-utilization",
        f"{binding['gpu_memory_utilization_milli'] / 1000:.3f}",
        "--generation-config",
        "vllm",
        "--seed",
        "0",
        "--enforce-eager",
        "--language-model-only",
        "--max-logprobs",
        "20",
        "--logprobs-mode",
        "processed_logprobs",
        "--no-async-scheduling",
    ]


def parse_vllm_success_total(raw: bytes) -> int:
    """Parse the bounded vLLM counters used at both lease boundaries."""

    if not isinstance(raw, bytes) or not raw or len(raw) > 4_000_000:
        raise G1MicroError("vLLM metrics bytes are absent or unbounded")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise G1MicroError("vLLM metrics are not UTF-8") from error
    running: list[Decimal] = []
    successes: list[Decimal] = []
    prefix_hits: list[Decimal] = []
    prefix_queries: list[Decimal] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        metric = parts[0].split("{", 1)[0]
        if metric not in {
            "vllm:num_requests_running",
            "vllm:request_success_total",
            "vllm:prefix_cache_hits",
            "vllm:prefix_cache_hits_total",
            "vllm:prefix_cache_queries",
            "vllm:prefix_cache_queries_total",
            "vllm_prefix_cache_hits",
            "vllm_prefix_cache_hits_total",
            "vllm_prefix_cache_queries",
            "vllm_prefix_cache_queries_total",
        }:
            continue
        try:
            number = Decimal(parts[1])
        except InvalidOperation as error:
            raise G1MicroError("vLLM metric value is invalid") from error
        if not number.is_finite():
            raise G1MicroError("vLLM metric value is non-finite")
        if metric == "vllm:num_requests_running":
            running.append(number)
        elif metric == "vllm:request_success_total":
            successes.append(number)
        elif "prefix_cache_hits" in metric:
            prefix_hits.append(number)
        else:
            prefix_queries.append(number)
    if (
        not running
        or not successes
        or not prefix_hits
        or not prefix_queries
        or any(number != 0 for number in running + prefix_hits + prefix_queries)
    ):
        raise G1MicroError("required vLLM counters are absent, active, or nonzero")
    total = sum(successes, Decimal(0))
    if total < 0 or total != total.to_integral_value():
        raise G1MicroError("vLLM success counter is not a nonnegative integer")
    return int(total)


def validate_dgx_runtime_binding(
    value: Mapping[str, Any],
    *,
    protocol: Mapping[str, Any],
    protocol_sha256: str,
    source_manifest: Mapping[str, str],
) -> None:
    """Validate a measured fresh-container startup record before any model POST."""

    _validate_protocol(protocol)
    _require_sha(protocol_sha256, "runtime protocol")
    _validate_source_manifest(source_manifest)
    validate_record(value, kind="DGXFreshRuntimeBinding")
    payload = value["payload"]
    expected_fields = {
        "async_scheduling",
        "container_inspect_json",
        "container_inspect_sha256",
        "container_id_sha256",
        "container_image",
        "container_image_id",
        "container_start_sha256",
        "endpoint_origin",
        "fresh_cache_directories_empty_before_launch",
        "gpu_name",
        "gpu_observation_sha256",
        "gpu_observation_utf8",
        "gpu_uuid",
        "image_inspect_json",
        "image_inspect_sha256",
        "model_repository",
        "model_revision",
        "model_snapshot_manifest_json",
        "model_snapshot_manifest_sha256",
        "network_boundary",
        "protocol_file_sha256",
        "protocol_sha256",
        "request_success_total_at_start",
        "served_model",
        "server_argv",
        "server_argv_sha256",
        "source_commit",
        "source_manifest",
        "source_tree",
        "startup_metrics_utf8",
        "startup_metrics_sha256",
        "startup_models_json",
        "startup_models_sha256",
        "startup_version_json",
        "startup_version_sha256",
        "terminal",
        "tracked_source_sha256",
        "vllm_version",
    }
    binding = protocol["live_binding"]
    expected_argv = expected_dgx_server_argv(protocol)
    if (
        value["owner_uid"] != "principal:g1-micro-dgx-runtime-custodian"
        or value["refs"] != []
        or set(payload) != expected_fields
        or payload["protocol_sha256"] != protocol_sha256
        or payload["source_manifest"] != dict(source_manifest)
        or payload["container_image"] != binding["container_image"]
        or payload["container_image_id"] != binding["container_image_id"]
        or payload["endpoint_origin"] != binding["endpoint_origin"]
        or payload["gpu_uuid"] != binding["gpu_uuid"]
        or payload["gpu_name"] != binding["gpu_name"]
        or payload["model_repository"] != binding["model_repository"]
        or payload["model_revision"] != binding["model_revision"]
        or payload["model_snapshot_manifest_sha256"]
        != binding["model_snapshot_manifest_sha256"]
        or payload["network_boundary"] != DGX_NETWORK_BOUNDARY
        or payload["served_model"] != binding["served_model"]
        or payload["vllm_version"] != binding["vllm_version"]
        or payload["async_scheduling"] is not binding["async_scheduling"]
        or payload["fresh_cache_directories_empty_before_launch"] is not True
        or payload["request_success_total_at_start"] != 0
        or payload["server_argv"] != expected_argv
        or payload["server_argv_sha256"]
        != _digest("\0".join(expected_argv).encode("utf-8"))
        or payload["terminal"]
        != "FRESH_CONTAINER_STARTUP_ATTESTATION_NOT_NO_INTERFERENCE_PROOF"
        or not isinstance(payload["source_commit"], str)
        or re.fullmatch(r"[0-9a-f]{40}", payload["source_commit"]) is None
        or payload["source_commit"] == "0" * 40
        or not isinstance(payload["source_tree"], str)
        or re.fullmatch(r"[0-9a-f]{40}", payload["source_tree"]) is None
        or payload["source_tree"] == "0" * 40
    ):
        raise G1MicroError("DGX fresh runtime binding drifted")
    for field in (
        "container_inspect_sha256",
        "container_id_sha256",
        "container_start_sha256",
        "gpu_observation_sha256",
        "image_inspect_sha256",
        "model_snapshot_manifest_sha256",
        "protocol_file_sha256",
        "server_argv_sha256",
        "startup_metrics_sha256",
        "startup_models_sha256",
        "startup_version_sha256",
    ):
        _require_sha(payload[field], f"runtime {field}")
    tracked = payload["tracked_source_sha256"]
    if not isinstance(tracked, Mapping) or set(tracked) != set(DGX_TRACKED_SOURCE_PATHS):
        raise G1MicroError("DGX tracked source manifest drifted")
    for path, digest in tracked.items():
        _require_sha(digest, f"tracked source {path}")
    if any(
        tracked[path] != digest for path, digest in source_manifest.items()
    ) or tracked[DGX_TRACKED_SOURCE_PATHS[0]] != payload["protocol_file_sha256"]:
        raise G1MicroError("DGX tracked source differs from execution sources")

    raw_fields = {
        "container_inspect_json": "container_inspect_sha256",
        "gpu_observation_utf8": "gpu_observation_sha256",
        "image_inspect_json": "image_inspect_sha256",
        "model_snapshot_manifest_json": "model_snapshot_manifest_sha256",
        "startup_metrics_utf8": "startup_metrics_sha256",
        "startup_models_json": "startup_models_sha256",
        "startup_version_json": "startup_version_sha256",
    }
    raw: dict[str, bytes] = {}
    for field, digest_field in raw_fields.items():
        text = payload[field]
        if not isinstance(text, str):
            raise G1MicroError(f"runtime {field} is not text")
        encoded = text.encode("utf-8")
        if not encoded or len(encoded) > 4_000_000 or _digest(encoded) != payload[digest_field]:
            raise G1MicroError(f"runtime {field} preimage drifted")
        raw[field] = encoded
    try:
        image = json.loads(raw["image_inspect_json"])
        container = json.loads(raw["container_inspect_json"])
        models = json.loads(raw["startup_models_json"])
        version = json.loads(raw["startup_version_json"])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise G1MicroError("DGX runtime JSON evidence is invalid") from error
    gpu = [item.strip() for item in payload["gpu_observation_utf8"].split(",")]
    snapshot = _canonical_object(
        raw["model_snapshot_manifest_json"], "model snapshot manifest"
    )
    ports: object = None
    if isinstance(container, list) and len(container) == 1 and isinstance(container[0], dict):
        ports = container[0].get("HostConfig", {}).get("PortBindings", {}).get(
            "8000/tcp"
        )
    if (
        not isinstance(image, list)
        or len(image) != 1
        or not isinstance(image[0], dict)
        or image[0].get("Id") != binding["container_image_id"]
        or binding["container_image"] not in image[0].get("RepoDigests", [])
        or gpu != [binding["gpu_uuid"], binding["gpu_name"]]
        or snapshot.get("repository") != binding["model_repository"]
        or snapshot.get("revision") != binding["model_revision"]
        or not isinstance(container, list)
        or len(container) != 1
        or not isinstance(container[0], dict)
        or _digest(str(container[0].get("Id", "")).encode("utf-8"))
        != payload["container_id_sha256"]
        or _digest(str(container[0].get("State", {}).get("StartedAt", "")).encode("utf-8"))
        != payload["container_start_sha256"]
        or container[0].get("Image") != binding["container_image_id"]
        or container[0].get("Config", {}).get("Image") != binding["container_image"]
        or container[0].get("Config", {}).get("Cmd") != expected_argv
        or container[0].get("HostConfig", {}).get("NetworkMode") != "bridge"
        or container[0].get("HostConfig", {}).get("IpcMode") != "private"
        or ports != [{"HostIp": "127.0.0.1", "HostPort": "18080"}]
        or not isinstance(models, dict)
        or [item.get("id") for item in models.get("data", []) if isinstance(item, dict)]
        != [binding["served_model"]]
        or not isinstance(version, dict)
        or version.get("version") != binding["vllm_version"]
        or parse_vllm_success_total(raw["startup_metrics_utf8"]) != 0
    ):
        raise G1MicroError("DGX raw runtime evidence does not match the binding")


def load_protocol(path: str | Path) -> tuple[dict[str, Any], str]:
    raw = Path(path).read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise G1MicroError("protocol is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise G1MicroError("protocol must be one JSON object")
    _validate_protocol(value)
    return value, canonical_sha256(value)


def make_genesis_state() -> dict[str, Any]:
    return {
        "dispositions": [],
        "owner_uid": STATE_OWNER,
        "schema_version": STATE_SCHEMA,
    }


def make_disposition(
    task: MicroTask,
    *,
    operator: str,
    trajectory: Mapping[str, Any],
    feedback: Mapping[str, Any],
    proposal: Mapping[str, Any],
    credit: Mapping[str, Any],
) -> dict[str, Any]:
    if operator not in OPERATORS:
        raise G1MicroError("disposition operator is invalid")
    return make_record(
        "MacroDisposition",
        owner_uid=DISPOSITION_OWNER,
        payload={
            "cue": task.cue,
            "operand": task.operand,
            "operator": operator,
            "revision_kind": "OPAQUE_CUE_OPERATOR_DISPOSITION",
        },
        refs=(
            _ref("trajectory", trajectory),
            _ref("feedback", feedback),
            _ref("proposal", proposal),
            _ref("credit", credit),
        ),
    )


def make_state(dispositions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = sorted((dict(item) for item in dispositions), key=lambda x: x["record_sha256"])
    value = {
        "dispositions": normalized,
        "owner_uid": STATE_OWNER,
        "schema_version": STATE_SCHEMA,
    }
    validate_state(value)
    return value


def validate_state(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "dispositions",
        "owner_uid",
        "schema_version",
    }:
        raise G1MicroError("disposition state field set is invalid")
    if value["schema_version"] != STATE_SCHEMA or value["owner_uid"] != STATE_OWNER:
        raise G1MicroError("disposition state identity or owner drifted")
    dispositions = value["dispositions"]
    if not isinstance(dispositions, list) or len(dispositions) > 1:
        raise G1MicroError("micro state permits at most one disposition")
    for disposition in dispositions:
        validate_record(disposition, kind="MacroDisposition")
        if disposition["owner_uid"] != DISPOSITION_OWNER:
            raise G1MicroError("disposition owner drifted")
        payload = disposition["payload"]
        if set(payload) != {"cue", "operand", "operator", "revision_kind"}:
            raise G1MicroError("disposition payload field set drifted")
        if (
            payload["operator"] not in OPERATORS
            or payload["operand"] != 3
            or payload["revision_kind"] != "OPAQUE_CUE_OPERATOR_DISPOSITION"
        ):
            raise G1MicroError("disposition content exceeds the one-kind contract")


def state_sha256(state: Mapping[str, Any]) -> str:
    validate_state(state)
    return canonical_sha256(state)


def compile_disposition(state: Mapping[str, Any], *, cue: str) -> dict[str, Any]:
    """Compile only the exact cue-matched disposition into the model readset."""

    validate_state(state)
    selected = [item for item in state["dispositions"] if item["payload"]["cue"] == cue]
    if len(selected) > 1:
        raise G1MicroError("compiled disposition has multiple owners for one cue")
    rule = None if not selected else {
        "operand": selected[0]["payload"]["operand"],
        "operator": selected[0]["payload"]["operator"],
    }
    unsigned = {
        "compiler": "hswm-g1-micro-disposition-compiler/v1",
        "cue": cue,
        "readset": [item["record_sha256"] for item in selected],
        "rule": rule,
        "source_state_sha256": state_sha256(state),
    }
    return {**unsigned, "compiled_disposition_sha256": canonical_sha256(unsigned)}


def make_permit_policy(task: MicroTask, protocol_sha256: str) -> dict[str, Any]:
    _require_sha(protocol_sha256, "protocol")
    return make_record(
        "LocalPermitPolicy",
        owner_uid=PRINCIPALS["authorizer_uid"],
        payload={
            "allowed_operation": "UPSERT_ONE_DISPOSITION",
            "allowed_revision_kind": "OPAQUE_CUE_OPERATOR_DISPOSITION",
            "allowed_target_uid": "local:g1-micro-state:dispositions",
            "base_generation": 0,
            "base_state_sha256": state_sha256(make_genesis_state()),
            "episode_uid": task.episode_uid,
            "max_consumptions": 1,
            "principals": dict(PRINCIPALS),
            "protocol_sha256": protocol_sha256,
            "study_uid": task.study_uid,
            "task_commitment_sha256": task.commitment_sha256,
        },
    )


def _validate_permit_policy(
    value: Mapping[str, Any],
    *,
    task: MicroTask | None = None,
    protocol_sha256: str | None = None,
) -> None:
    validate_record(value, kind="LocalPermitPolicy")
    payload = value["payload"]
    if (
        value["owner_uid"] != PRINCIPALS["authorizer_uid"]
        or value["refs"] != []
        or set(payload)
        != {
            "allowed_operation",
            "allowed_revision_kind",
            "allowed_target_uid",
            "base_generation",
            "base_state_sha256",
            "episode_uid",
            "max_consumptions",
            "principals",
            "protocol_sha256",
            "study_uid",
            "task_commitment_sha256",
        }
        or payload["allowed_operation"] != "UPSERT_ONE_DISPOSITION"
        or payload["allowed_revision_kind"] != "OPAQUE_CUE_OPERATOR_DISPOSITION"
        or payload["allowed_target_uid"] != "local:g1-micro-state:dispositions"
        or payload["base_generation"] != 0
        or payload["base_state_sha256"] != state_sha256(make_genesis_state())
        or payload["max_consumptions"] != 1
    ):
        raise G1MicroError("local permit policy is outside the frozen envelope")
    _validate_principals(payload["principals"])
    _require_sha(payload["protocol_sha256"], "permit policy protocol")
    _require_sha(payload["task_commitment_sha256"], "permit policy task commitment")
    if task is not None and (
        payload["episode_uid"] != task.episode_uid
        or payload["study_uid"] != task.study_uid
        or payload["task_commitment_sha256"] != task.commitment_sha256
    ):
        raise G1MicroError("local permit policy task binding drifted")
    if protocol_sha256 is not None and payload["protocol_sha256"] != protocol_sha256:
        raise G1MicroError("local permit policy protocol binding drifted")


def _validate_principals(value: object) -> None:
    if not isinstance(value, Mapping) or dict(value) != PRINCIPALS:
        raise G1MicroError("permit principals differ from the frozen local roles")
    if len(set(value.values())) != len(value):
        raise G1MicroError("local experimental roles must be distinct")


def _write_set(
    *, base_state_sha256: str, disposition_sha256: str, successor_state_sha256: str
) -> list[dict[str, str]]:
    return [
        {
            "base_state_sha256": _require_sha(base_state_sha256, "write base"),
            "disposition_sha256": _require_sha(disposition_sha256, "write disposition"),
            "operation": "UPSERT_ONE_DISPOSITION",
            "successor_state_sha256": _require_sha(successor_state_sha256, "write successor"),
            "target_uid": "local:g1-micro-state:dispositions",
        }
    ]


def make_local_permit(
    *,
    task: MicroTask,
    permit_policy: Mapping[str, Any],
    base_state: Mapping[str, Any],
    base_generation: int,
    trajectory: Mapping[str, Any],
    feedback: Mapping[str, Any],
    proposal: Mapping[str, Any],
    credit: Mapping[str, Any],
    disposition: Mapping[str, Any],
    successor_state: Mapping[str, Any],
) -> dict[str, Any]:
    """Issue an exact post-credit local grant under a pre-outcome policy."""

    _validate_permit_policy(permit_policy, task=task)
    validate_record(trajectory, kind="SealedTrajectory")
    validate_record(feedback)
    validate_record(proposal, kind="RevisionProposal")
    validate_record(credit, kind="CreditDecision")
    validate_record(disposition, kind="MacroDisposition")
    validate_state(base_state)
    validate_state(successor_state)
    if credit["payload"].get("decision") != "CREDIT":
        raise G1MicroError("a local permit cannot be issued without credit")
    if isinstance(base_generation, bool) or base_generation != 0:
        raise G1MicroError("micro learning admission must start at generation zero")
    base_sha = state_sha256(base_state)
    successor_sha = state_sha256(successor_state)
    writes = _write_set(
        base_state_sha256=base_sha,
        disposition_sha256=disposition["record_sha256"],
        successor_state_sha256=successor_sha,
    )
    return make_record(
        "LocalPermitGrant",
        owner_uid=PRINCIPALS["authorizer_uid"],
        payload={
            "authorizer_decision": "GRANT",
            "base_generation": base_generation,
            "base_state_sha256": base_sha,
            "episode_uid": task.episode_uid,
            "permit_nonce": "permit:" + canonical_sha256(
                {
                    "credit": credit["record_sha256"],
                    "episode": task.episode_uid,
                    "proposal": proposal["record_sha256"],
                }
            )[:32],
            "principals": dict(PRINCIPALS),
            "study_uid": task.study_uid,
            "successor_state_sha256": successor_sha,
            "write_set": writes,
            "write_set_sha256": canonical_sha256(writes),
        },
        refs=(
            _ref("permit_policy", permit_policy),
            _ref("trajectory", trajectory),
            _ref("feedback", feedback),
            _ref("proposal", proposal),
            _ref("credit", credit),
            _ref("disposition", disposition),
        ),
    )


def _validate_local_permit(value: Mapping[str, Any]) -> None:
    validate_record(value, kind="LocalPermitGrant")
    payload = value["payload"]
    expected = {
        "authorizer_decision",
        "base_generation",
        "base_state_sha256",
        "episode_uid",
        "permit_nonce",
        "principals",
        "study_uid",
        "successor_state_sha256",
        "write_set",
        "write_set_sha256",
    }
    if set(payload) != expected or payload["authorizer_decision"] != "GRANT":
        raise G1MicroError("local permit payload is invalid")
    _validate_principals(payload["principals"])
    if payload["base_generation"] != 0:
        raise G1MicroError("local permit base generation drifted")
    _require_sha(payload["base_state_sha256"], "permit base state")
    _require_sha(payload["successor_state_sha256"], "permit successor state")
    if not isinstance(payload["write_set"], list) or len(payload["write_set"]) != 1:
        raise G1MicroError("local permit must name one exact write")
    if canonical_sha256(payload["write_set"]) != payload["write_set_sha256"]:
        raise G1MicroError("local permit write-set digest mismatch")
    if {item["kind"] for item in value["refs"]} != {
        "credit",
        "disposition",
        "feedback",
        "permit_policy",
        "proposal",
        "trajectory",
    }:
        raise G1MicroError("local permit reference closure is incomplete")


@dataclass(frozen=True, slots=True)
class ActiveState:
    state: dict[str, Any]
    generation: int

    @property
    def state_sha256(self) -> str:
        return state_sha256(self.state)


class G1MicroStore:
    """Purpose-bounded SQLite CAS with atomic one-shot permit consumption."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        genesis = make_genesis_state()
        raw = canonical_json_bytes(genesis)
        digest = state_sha256(genesis)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS g1_snapshots(
                    state_sha256 TEXT PRIMARY KEY,
                    state_json BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS g1_active(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    state_sha256 TEXT NOT NULL,
                    generation INTEGER NOT NULL CHECK(generation>=0),
                    FOREIGN KEY(state_sha256) REFERENCES g1_snapshots(state_sha256)
                );
                CREATE TABLE IF NOT EXISTS g1_permits(
                    permit_sha256 TEXT PRIMARY KEY,
                    permit_json BLOB NOT NULL,
                    consumption_json BLOB
                );
                CREATE TABLE IF NOT EXISTS g1_admissions(
                    admission_sha256 TEXT PRIMARY KEY,
                    admission_json BLOB NOT NULL,
                    permit_sha256 TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS g1_interventions(
                    generation INTEGER PRIMARY KEY,
                    intervention_sha256 TEXT NOT NULL UNIQUE,
                    intervention_json BLOB NOT NULL
                );
                """
            )
            prior = connection.execute(
                "SELECT state_json FROM g1_snapshots WHERE state_sha256=?", (digest,)
            ).fetchone()
            if prior is None:
                connection.execute("INSERT INTO g1_snapshots VALUES(?,?)", (digest, raw))
            elif bytes(prior["state_json"]) != raw:
                raise G1MicroError("genesis state identity conflict")
            active = connection.execute("SELECT * FROM g1_active WHERE singleton=1").fetchone()
            if active is None:
                connection.execute("INSERT INTO g1_active VALUES(1,?,0)", (digest,))
            self._active_in_tx(connection)

    def _load_state_in_tx(self, connection: sqlite3.Connection, digest: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT state_json FROM g1_snapshots WHERE state_sha256=?", (digest,)
        ).fetchone()
        if row is None:
            raise G1MicroError("state snapshot is missing")
        state = _canonical_object(bytes(row["state_json"]), "stored state")
        if state_sha256(state) != digest:
            raise G1MicroError("stored state digest mismatch")
        return state

    def _active_in_tx(self, connection: sqlite3.Connection) -> ActiveState:
        row = connection.execute("SELECT * FROM g1_active WHERE singleton=1").fetchone()
        if row is None:
            raise G1MicroError("active state pointer is missing")
        return ActiveState(
            state=self._load_state_in_tx(connection, row["state_sha256"]),
            generation=int(row["generation"]),
        )

    def active(self) -> ActiveState:
        with self._connect() as connection:
            return self._active_in_tx(connection)

    def issue_permit(
        self, permit: Mapping[str, Any], *, permit_policy: Mapping[str, Any]
    ) -> None:
        _validate_local_permit(permit)
        _validate_permit_policy(permit_policy)
        policy = permit_policy["payload"]
        payload = permit["payload"]
        refs = {item["kind"]: item["sha256"] for item in permit["refs"]}
        if (
            refs.get("permit_policy") != permit_policy["record_sha256"]
            or payload["study_uid"] != policy["study_uid"]
            or payload["episode_uid"] != policy["episode_uid"]
            or payload["principals"] != policy["principals"]
            or payload["base_generation"] != policy["base_generation"]
            or payload["base_state_sha256"] != policy["base_state_sha256"]
            or payload["write_set"][0]["operation"] != policy["allowed_operation"]
            or payload["write_set"][0]["target_uid"] != policy["allowed_target_uid"]
        ):
            raise G1MicroError("local permit grant exceeds its pre-outcome policy")
        raw = canonical_json_bytes(permit)
        digest = str(permit["record_sha256"])
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT permit_json FROM g1_permits WHERE permit_sha256=?", (digest,)
            ).fetchone()
            if prior is not None:
                connection.rollback()
                raise G1MicroError("local permit nonce or digest was already issued")
            duplicate_nonce = connection.execute(
                "SELECT permit_json FROM g1_permits"
            ).fetchall()
            for row in duplicate_nonce:
                stored = _canonical_object(bytes(row["permit_json"]), "stored permit")
                if stored["payload"]["permit_nonce"] == permit["payload"]["permit_nonce"]:
                    connection.rollback()
                    raise G1MicroError("local permit nonce was already issued")
            connection.execute("INSERT INTO g1_permits VALUES(?,?,NULL)", (digest, raw))
            connection.commit()

    @staticmethod
    def _burn_record(
        permit: Mapping[str, Any], *, terminal: str, admission_sha256: str | None
    ) -> dict[str, Any]:
        return make_record(
            "LocalPermitConsumption",
            owner_uid=STATE_OWNER,
            payload={
                "admission_sha256": admission_sha256,
                "permit_nonce": permit["payload"]["permit_nonce"],
                "terminal": terminal,
            },
            refs=(_ref("permit", permit),),
        )

    def _burn_and_raise(
        self,
        connection: sqlite3.Connection,
        permit: Mapping[str, Any],
        terminal: str,
        message: str,
    ) -> None:
        burn = self._burn_record(permit, terminal=terminal, admission_sha256=None)
        connection.execute(
            "UPDATE g1_permits SET consumption_json=? WHERE permit_sha256=?",
            (canonical_json_bytes(burn), permit["record_sha256"]),
        )
        connection.commit()
        raise G1MicroError(message)

    def admit(
        self,
        *,
        permit: Mapping[str, Any],
        proposal: Mapping[str, Any],
        feedback: Mapping[str, Any],
        credit: Mapping[str, Any],
        successor_state: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Atomically consume the exact grant and advance local active state once."""

        _validate_local_permit(permit)
        validate_record(proposal, kind="RevisionProposal")
        validate_record(feedback)
        validate_record(credit, kind="CreditDecision")
        validate_state(successor_state)
        permit_sha = str(permit["record_sha256"])
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM g1_permits WHERE permit_sha256=?", (permit_sha,)
            ).fetchone()
            if row is None or bytes(row["permit_json"]) != canonical_json_bytes(permit):
                connection.rollback()
                raise G1MicroError("local permit is absent or changed")
            if row["consumption_json"] is not None:
                connection.rollback()
                raise G1MicroError("local permit was already consumed")
            active = self._active_in_tx(connection)
            payload = permit["payload"]
            refs = {item["kind"]: item["sha256"] for item in permit["refs"]}
            checks = {
                "base": (
                    active.generation == payload["base_generation"]
                    and active.state_sha256 == payload["base_state_sha256"]
                ),
                "credit": (
                    credit["payload"].get("decision") == "CREDIT"
                    and refs.get("credit") == credit["record_sha256"]
                ),
                "feedback": refs.get("feedback") == feedback["record_sha256"],
                "proposal": refs.get("proposal") == proposal["record_sha256"],
                "successor": state_sha256(successor_state)
                == payload["successor_state_sha256"],
            }
            failed = next((name for name, passed in checks.items() if not passed), None)
            if failed is not None:
                self._burn_and_raise(
                    connection,
                    permit,
                    f"REFUSED_{failed.upper()}_MISMATCH",
                    f"local admission refused: {failed} mismatch",
                )
            dispositions = successor_state["dispositions"]
            expected_writes = _write_set(
                base_state_sha256=active.state_sha256,
                disposition_sha256=dispositions[0]["record_sha256"],
                successor_state_sha256=state_sha256(successor_state),
            )
            if payload["write_set"] != expected_writes:
                self._burn_and_raise(
                    connection,
                    permit,
                    "REFUSED_WRITE_SET_MISMATCH",
                    "local admission refused: write-set mismatch",
                )
            successor_sha = state_sha256(successor_state)
            successor_raw = canonical_json_bytes(successor_state)
            connection.execute(
                "INSERT OR IGNORE INTO g1_snapshots VALUES(?,?)",
                (successor_sha, successor_raw),
            )
            stored = connection.execute(
                "SELECT state_json FROM g1_snapshots WHERE state_sha256=?", (successor_sha,)
            ).fetchone()
            if stored is None or bytes(stored["state_json"]) != successor_raw:
                self._burn_and_raise(
                    connection,
                    permit,
                    "REFUSED_STATE_IDENTITY_CONFLICT",
                    "local admission refused: successor identity conflict",
                )
            changed = connection.execute(
                "UPDATE g1_active SET state_sha256=?,generation=? "
                "WHERE singleton=1 AND state_sha256=? AND generation=?",
                (successor_sha, active.generation + 1, active.state_sha256, active.generation),
            ).rowcount
            if changed != 1:
                self._burn_and_raise(
                    connection,
                    permit,
                    "REFUSED_STALE_CAS",
                    "local admission lost the active-state CAS",
                )
            admission = make_record(
                "LocalAdmissionReceipt",
                owner_uid=STATE_OWNER,
                payload={
                    "base_generation": active.generation,
                    "base_state_sha256": active.state_sha256,
                    "exact_write_set": expected_writes,
                    "resulting_generation": active.generation + 1,
                    "resulting_state_sha256": successor_sha,
                    "terminal": "ADMITTED_LOCAL_EXPLORATORY",
                },
                refs=(
                    _ref("permit", permit),
                    _ref("proposal", proposal),
                    _ref("feedback", feedback),
                    _ref("credit", credit),
                ),
            )
            burn = self._burn_record(
                permit,
                terminal="ADMITTED_LOCAL_EXPLORATORY",
                admission_sha256=admission["record_sha256"],
            )
            connection.execute(
                "UPDATE g1_permits SET consumption_json=? WHERE permit_sha256=?",
                (canonical_json_bytes(burn), permit_sha),
            )
            connection.execute(
                "INSERT INTO g1_admissions VALUES(?,?,?)",
                (
                    admission["record_sha256"],
                    canonical_json_bytes(admission),
                    permit_sha,
                ),
            )
            connection.commit()
            return {"admission": admission, "consumption": burn}

    def activate_exact(
        self,
        target_state_sha256: str,
        *,
        expected_generation: int,
        operation: str,
        source_admission_sha256: str,
    ) -> dict[str, Any]:
        """Apply a declared evaluator intervention, not a learning admission."""

        if operation not in {"REMOVE_TO_GENESIS", "RESTORE_ACTIVE_SNAPSHOT"}:
            raise G1MicroError("unknown evaluator intervention")
        _require_sha(target_state_sha256, "intervention target")
        _require_sha(source_admission_sha256, "source admission")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            active = self._active_in_tx(connection)
            target = self._load_state_in_tx(connection, target_state_sha256)
            admission_row = connection.execute(
                "SELECT admission_json FROM g1_admissions WHERE admission_sha256=?",
                (source_admission_sha256,),
            ).fetchone()
            if admission_row is None:
                connection.rollback()
                raise G1MicroError("evaluator intervention source admission is absent")
            admission = _canonical_object(
                bytes(admission_row["admission_json"]), "source admission"
            )
            admitted_state_sha = admission["payload"]["resulting_state_sha256"]
            if active.generation != expected_generation:
                connection.rollback()
                raise G1MicroError("evaluator intervention lost the generation CAS")
            if (
                operation == "REMOVE_TO_GENESIS"
                and (
                    active.state_sha256 != admitted_state_sha
                    or target_state_sha256 != state_sha256(make_genesis_state())
                )
            ) or (
                operation == "RESTORE_ACTIVE_SNAPSHOT"
                and (
                    active.state_sha256 != state_sha256(make_genesis_state())
                    or target_state_sha256 != admitted_state_sha
                )
            ):
                connection.rollback()
                raise G1MicroError("evaluator intervention exceeds admission-bound scope")
            if active.state_sha256 == target_state_sha256:
                connection.rollback()
                raise G1MicroError("evaluator intervention target is already active")
            changed = connection.execute(
                "UPDATE g1_active SET state_sha256=?,generation=? "
                "WHERE singleton=1 AND state_sha256=? AND generation=?",
                (
                    target_state_sha256,
                    active.generation + 1,
                    active.state_sha256,
                    active.generation,
                ),
            ).rowcount
            if changed != 1:
                connection.rollback()
                raise G1MicroError("evaluator intervention lost the state CAS")
            receipt = make_record(
                "EvaluatorStateIntervention",
                owner_uid=PRINCIPALS["outcome_evaluator_uid"],
                payload={
                    "authority_class": "DECLARED_EXPERIMENTAL_INTERVENTION_NOT_LEARNING",
                    "base_generation": active.generation,
                    "base_state_sha256": active.state_sha256,
                    "operation": operation,
                    "resulting_generation": active.generation + 1,
                    "resulting_state_sha256": state_sha256(target),
                    "source_admission_sha256": source_admission_sha256,
                },
            )
            connection.execute(
                "INSERT INTO g1_interventions VALUES(?,?,?)",
                (
                    active.generation + 1,
                    receipt["record_sha256"],
                    canonical_json_bytes(receipt),
                ),
            )
            connection.commit()
            return receipt

    def logical_receipts(self) -> dict[str, Any]:
        return _logical_receipts_from_database(self.path)

    def checkpoint(self) -> None:
        with self._connect() as connection:
            row = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if row is None or int(row[0]) != 0:
                raise G1MicroError("state-store WAL checkpoint did not complete")


def _logical_receipts_from_database(path: Path) -> dict[str, Any]:
    """Read the retained store without initializing or mutating it."""

    if not path.is_file() or path.is_symlink():
        raise G1MicroError("state-store artifact is absent or linked")
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        active = connection.execute("SELECT * FROM g1_active WHERE singleton=1").fetchone()
        if active is None:
            raise G1MicroError("retained state-store active pointer is missing")
        snapshot = connection.execute(
            "SELECT state_json FROM g1_snapshots WHERE state_sha256=?",
            (active["state_sha256"],),
        ).fetchone()
        if snapshot is None:
            raise G1MicroError("retained state-store active snapshot is missing")
        active_state = _canonical_object(bytes(snapshot["state_json"]), "retained state")
        if state_sha256(active_state) != active["state_sha256"]:
            raise G1MicroError("retained state-store active snapshot drifted")
        permits = connection.execute(
            "SELECT * FROM g1_permits ORDER BY permit_sha256"
        ).fetchall()
        admissions = connection.execute(
            "SELECT admission_json FROM g1_admissions ORDER BY admission_sha256"
        ).fetchall()
        interventions = connection.execute(
            "SELECT intervention_json FROM g1_interventions ORDER BY generation"
        ).fetchall()
        return {
            "active": {
                "generation": int(active["generation"]),
                "state_sha256": str(active["state_sha256"]),
            },
            "admissions": [
                _canonical_object(bytes(row["admission_json"]), "stored admission")
                for row in admissions
            ],
            "interventions": [
                _canonical_object(bytes(row["intervention_json"]), "stored intervention")
                for row in interventions
            ],
            "permits": [
                {
                    "consumption": (
                        None
                        if row["consumption_json"] is None
                        else _canonical_object(
                            bytes(row["consumption_json"]), "stored consumption"
                        )
                    ),
                    "permit": _canonical_object(bytes(row["permit_json"]), "stored permit"),
                }
                for row in permits
            ],
        }
    except sqlite3.DatabaseError as error:
        raise G1MicroError("retained state-store cannot be read structurally") from error
    finally:
        if connection is not None:
            connection.close()


def _choice_schema(name: str, choices: Sequence[str]) -> JSONSchemaContract:
    return JSONSchemaContract.make(
        name,
        {
            "additionalProperties": False,
            "properties": {"choice": {"enum": list(choices), "type": "string"}},
            "required": ["choice"],
            "type": "object",
        },
    )


def _proposal_schema() -> JSONSchemaContract:
    return JSONSchemaContract.make(
        "g1_micro_revision",
        {
            "additionalProperties": False,
            "properties": {
                "operation": {"enum": list(OPERATORS), "type": "string"},
                "rationale": {"maxLength": 256, "minLength": 1, "type": "string"},
            },
            "required": ["operation", "rationale"],
            "type": "object",
        },
    )


class G1MicroArm(_ModelArm):
    """Thin public specialization of the audited no-retry live call journal."""

    def __init__(
        self,
        *,
        backend: ChatBackend,
        journal_path: Path,
        isolation_id: str,
    ) -> None:
        super().__init__(
            name="g1-micro",
            backend=backend,
            budget=ArmBudget(
                answer_max_output_tokens=64,
                update_max_output_tokens=160,
                max_input_bytes=131_072,
                max_state_bytes=16_384,
                max_cells=1,
                max_memories=1,
            ),
            isolation_id=isolation_id,
            journal_path=journal_path,
        )

    def trajectory(self, task: MicroTask) -> tuple[str, dict[str, Any]]:
        payload = {
            **task.public(),
            "input": task.train_input,
            "output_choices": list(task.choices(task.train_input)),
            "task_contract": (
                "The opaque cue selects exactly one candidate operator. The selection "
                "is not inferable from the cue. Choose one output; no feedback is visible."
            ),
        }
        completion = self._call(
            operation="pre_outcome_trajectory",
            system=(
                "Act as one bounded HSWM function call. Return only the strict JSON "
                "choice. Do not invent cue semantics or request hidden feedback."
            ),
            payload=payload,
            max_output_tokens=self.budget.answer_max_output_tokens,
            response_schema=_choice_schema(
                "g1_micro_trajectory_choice", task.choices(task.train_input)
            ),
        )
        value = json.loads(completion.text)
        return str(value["choice"]), self._call_evidence()

    def propose(
        self,
        task: MicroTask,
        *,
        trajectory_choice: str,
        trajectory_sha256: str,
        feedback_correct: bool,
        feedback_sha256: str,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        payload = {
            **task.public(),
            "feedback": {"choice_was_correct": feedback_correct},
            "feedback_receipt_sha256": feedback_sha256,
            "sealed_trajectory": {
                "choice": trajectory_choice,
                "input": task.train_input,
                "output_choices": list(task.choices(task.train_input)),
                "trajectory_sha256": trajectory_sha256,
            },
            "write_contract": (
                "Propose exactly one cue-bound operator disposition. No topology, "
                "prompt, cache, retrieval, tool, or other state may be revised."
            ),
        }
        completion = self._call(
            operation="propose_revision",
            system=(
                "Infer the cue's operator only from the sealed choice and the supplied "
                "correctness feedback. Return one strict bounded disposition proposal."
            ),
            payload=payload,
            max_output_tokens=self.budget.update_max_output_tokens,
            response_schema=_proposal_schema(),
        )
        value = json.loads(completion.text)
        return {
            "operation": str(value["operation"]),
            "rationale": str(value["rationale"]),
        }, self._call_evidence()

    def probe(
        self,
        task: MicroTask,
        *,
        state: Mapping[str, Any],
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        compiled = compile_disposition(state, cue=task.cue)
        payload = {
            **task.public(),
            "compiled_disposition": compiled,
            "fresh_input": task.fresh_input,
            "output_choices": list(task.choices(task.fresh_input)),
            "task_contract": (
                "Use only the compiled disposition if present. If absent, the opaque "
                "cue itself supplies no information about the selected operator."
            ),
        }
        completion = self._call(
            operation="fresh_behavior_probe",
            system=(
                "Act as one fresh HSWM function call. Read only the supplied compiled "
                "state and return the strict JSON choice."
            ),
            payload=payload,
            max_output_tokens=self.budget.answer_max_output_tokens,
            response_schema=_choice_schema(
                "g1_micro_fresh_choice", task.choices(task.fresh_input)
            ),
        )
        value = json.loads(completion.text)
        return str(value["choice"]), compiled, self._call_evidence()

    def _call_evidence(self) -> dict[str, Any]:
        entry = self.ledger[-1]
        return {
            "call_ledger_entry_sha256": canonical_sha256(entry.canonical()),
            "completion_request_sha256": entry.completion.request_sha256,
            "completion_response_sha256": entry.completion.response_sha256,
            "input_tokens": entry.completion.input_tokens,
            "latency_ms": entry.completion.latency_ms + entry.token_preflight.latency_ms,
            "model": entry.completion.model,
            "output_tokens": entry.completion.output_tokens,
            "token_preflight_receipt_sha256": entry.token_preflight.receipt_sha256,
        }


def _feedback_expected_operator(
    task: MicroTask, *, trajectory_choice: str, correct: bool
) -> str:
    chosen = task.operator_for_choice(task.train_input, trajectory_choice)
    if correct:
        return chosen
    return next(operator for operator in OPERATORS if operator != chosen)


def make_credit(
    *,
    task: MicroTask,
    trajectory: Mapping[str, Any],
    feedback: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    validate_record(trajectory, kind="SealedTrajectory")
    validate_record(feedback)
    validate_record(proposal, kind="RevisionProposal")
    trajectory_choice = trajectory["payload"]["choice"]
    feedback_correct = feedback["payload"]["choice_was_correct"]
    expected = _feedback_expected_operator(
        task,
        trajectory_choice=trajectory_choice,
        correct=feedback_correct,
    )
    proposed = proposal["payload"]["operation"]
    decision = "CREDIT" if proposed == expected else "NO_CREDIT"
    return make_record(
        "CreditDecision",
        owner_uid=PRINCIPALS["credit_adjudicator_uid"],
        payload={
            "credit_rule": "BINARY_FEEDBACK_IDENTIFIES_ONE_OF_TWO_PRECOMMITTED_OPERATORS",
            "decision": decision,
            "expected_operator": expected,
            "proposed_operator": proposed,
        },
        refs=(
            _ref("trajectory", trajectory),
            _ref("feedback", feedback),
            _ref("proposal", proposal),
        ),
    )


def _make_feedback(
    *,
    task: MicroTask,
    trajectory: Mapping[str, Any],
    correct: bool,
    feedback_kind: str,
    commitment: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    refs = [_ref("trajectory", trajectory)]
    if commitment is not None:
        refs.append(_ref("pre_outcome_commitment", commitment))
    return make_record(
        feedback_kind,
        owner_uid=(
            PRINCIPALS["outcome_evaluator_uid"]
            if feedback_kind == "LocalOutcomeObservation"
            else "principal:g1-micro-placebo-custodian"
        ),
        payload={
            "choice_was_correct": correct,
            "episode_uid": task.episode_uid,
            "instrument": "opaque-cue-exact-choice-evaluator/v1",
            "task_commitment_sha256": task.commitment_sha256,
        },
        refs=refs,
    )


def _proposal_record(
    *,
    task: MicroTask,
    response: Mapping[str, str],
    trajectory: Mapping[str, Any],
    feedback: Mapping[str, Any],
    call_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    return make_record(
        "RevisionProposal",
        owner_uid=PRINCIPALS["proposer_uid"],
        payload={
            "call_evidence": dict(call_evidence),
            "cue": task.cue,
            "operation": response["operation"],
            "rationale": response["rationale"],
            "revision_kind": "OPAQUE_CUE_OPERATOR_DISPOSITION",
        },
        refs=(_ref("trajectory", trajectory), _ref("feedback", feedback)),
    )


def _probe_record(
    *,
    branch: str,
    task: MicroTask,
    state: Mapping[str, Any],
    choice: str,
    compiled: Mapping[str, Any],
    call_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    correct_choice = task.choice(task.fresh_input, task.hidden_operator)
    return make_record(
        "FreshBehaviorObservation",
        owner_uid=PRINCIPALS["outcome_evaluator_uid"],
        payload={
            "branch": branch,
            "call_evidence": dict(call_evidence),
            "choice": choice,
            "compiled_disposition": dict(compiled),
            "correct": choice == correct_choice,
            "correct_choice": correct_choice,
            "fresh_input": task.fresh_input,
            "state_sha256": state_sha256(state),
        },
    )


def _admit_branch(
    *,
    store: G1MicroStore,
    task: MicroTask,
    permit_policy: Mapping[str, Any],
    trajectory: Mapping[str, Any],
    feedback: Mapping[str, Any],
    proposal: Mapping[str, Any],
    credit: Mapping[str, Any],
) -> dict[str, Any] | None:
    if credit["payload"]["decision"] != "CREDIT":
        return None
    base = store.active()
    disposition = make_disposition(
        task,
        operator=proposal["payload"]["operation"],
        trajectory=trajectory,
        feedback=feedback,
        proposal=proposal,
        credit=credit,
    )
    successor = make_state([disposition])
    permit = make_local_permit(
        task=task,
        permit_policy=permit_policy,
        base_state=base.state,
        base_generation=base.generation,
        trajectory=trajectory,
        feedback=feedback,
        proposal=proposal,
        credit=credit,
        disposition=disposition,
        successor_state=successor,
    )
    store.issue_permit(permit, permit_policy=permit_policy)
    receipts = store.admit(
        permit=permit,
        proposal=proposal,
        feedback=feedback,
        credit=credit,
        successor_state=successor,
    )
    return {
        "admission": receipts["admission"],
        "consumption": receipts["consumption"],
        "disposition": disposition,
        "permit": permit,
        "successor_state": successor,
    }


def _journal_manifest(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    rows: list[dict[str, Any]] = []
    events: list[str] = []
    completed: dict[int, dict[str, Any]] = {}
    preflights: dict[int, dict[str, Any]] = {}
    for line_number, line in enumerate(raw.splitlines(), start=1):
        value = _canonical_object(line, f"journal line {line_number}")
        rows.append(value)
        event = value.get("event")
        if not isinstance(event, str):
            raise G1MicroError("journal event is missing")
        events.append(event)
        ordinal = value.get("ordinal")
        if event in {"completed", "tokenize_accepted"} and (
            isinstance(ordinal, bool) or not isinstance(ordinal, int)
        ):
            raise G1MicroError("journal call ordinal is invalid")
        if event == "completed":
            if ordinal in completed:
                raise G1MicroError("journal has duplicate completion ordinal")
            completed[ordinal] = value
        elif event == "tokenize_accepted":
            if ordinal in preflights:
                raise G1MicroError("journal has duplicate tokenize ordinal")
            preflights[ordinal] = value
    expected_operations = [
        "pre_outcome_trajectory",
        "propose_revision",
        "propose_revision",
        *("fresh_behavior_probe" for _ in range(5)),
    ]
    if sorted(completed) != list(range(len(completed))) or not set(completed) <= set(
        preflights
    ):
        raise G1MicroError("journal call ordinal coverage drifted")
    success_events = (
        "intent",
        "tokenize_intent",
        "tokenize_raw_response_received",
        "tokenize_accepted",
        "generation_dispatch_intent",
        "raw_response_received",
        "response_received",
        "completed",
    )
    all_rows_accounted = (
        len(rows) == len(completed) * len(success_events)
        and all(
            row.get("event") in success_events and row.get("ordinal") in completed
            for row in rows
        )
    )
    completed_event_sequences_valid = True
    raw_preimages_valid = True
    for ordinal in sorted(completed):
        group = [row for row in rows if row.get("ordinal") == ordinal]
        if tuple(row.get("event") for row in group) != success_events:
            completed_event_sequences_valid = False
            continue
        by_event = {row["event"]: row for row in group}
        if (
            len({row.get("request_id") for row in group}) != 1
            or len({row.get("operation") for row in group}) != 1
        ):
            completed_event_sequences_valid = False
        try:
            intent = by_event["intent"]
            tokenize_intent = by_event["tokenize_intent"]
            tokenize_raw = by_event["tokenize_raw_response_received"]
            tokenize_accepted = by_event["tokenize_accepted"]
            dispatch = by_event["generation_dispatch_intent"]
            raw_response = by_event["raw_response_received"]
            received = by_event["response_received"]
            done = by_event["completed"]
            chat_request = intent["raw_request_json"].encode("utf-8")
            tokenize_request = tokenize_intent["raw_request_json"].encode("utf-8")
            observed_tokenize_request = base64.b64decode(
                tokenize_raw["raw_request_base64"], validate=True
            )
            observed_tokenize_response = base64.b64decode(
                tokenize_raw["raw_response_base64"], validate=True
            )
            observed_chat_request = base64.b64decode(
                raw_response["raw_request_base64"], validate=True
            )
            observed_chat_response = base64.b64decode(
                raw_response["raw_response_base64"], validate=True
            )
            token_receipt = tokenize_accepted["token_preflight"]
            parsed_token_receipt = TokenPreflightReceipt.from_mapping(token_receipt)
            completion = done["completion"]
            if (
                _digest(chat_request) != intent["raw_request_sha256"]
                or _digest(tokenize_request) != tokenize_intent["raw_request_sha256"]
                or observed_tokenize_request != tokenize_request
                or _digest(observed_tokenize_request) != tokenize_raw["raw_request_sha256"]
                or _digest(observed_tokenize_response)
                != tokenize_raw["raw_response_sha256"]
                or len(observed_tokenize_response) != tokenize_raw["response_bytes"]
                or token_receipt["raw_request_json"].encode("utf-8")
                != observed_tokenize_request
                or parsed_token_receipt.canonical() != token_receipt
                or token_receipt["raw_response_json"].encode("utf-8")
                != observed_tokenize_response
                or token_receipt["source_chat_request_sha256"] != _digest(chat_request)
                or dispatch["raw_request_sha256"] != _digest(chat_request)
                or observed_chat_request != chat_request
                or _digest(observed_chat_request) != raw_response["raw_request_sha256"]
                or _digest(observed_chat_response) != raw_response["raw_response_sha256"]
                or len(observed_chat_response) != raw_response["response_bytes"]
                or received["completion"] != completion
                or completion["raw_request_json"].encode("utf-8") != observed_chat_request
                or completion["raw_response_json"].encode("utf-8")
                != observed_chat_response
                or completion["request_sha256"] != _digest(chat_request)
                or completion["response_sha256"] != _digest(observed_chat_response)
            ):
                raw_preimages_valid = False
        except (
            KeyError,
            TypeError,
            ValueError,
            binascii.Error,
            AttributeError,
            ContinualLiveError,
        ):
            raw_preimages_valid = False
    calls: list[dict[str, Any]] = []
    for ordinal in sorted(completed):
        done = completed[ordinal]
        preflight = preflights[ordinal]["token_preflight"]
        completion = done["completion"]
        calls.append(
            {
                "completion_request_sha256": completion["request_sha256"],
                "completion_response_sha256": completion["response_sha256"],
                "operation": done["operation"],
                "ordinal": ordinal,
                "token_preflight_receipt_sha256": preflight["receipt_sha256"],
            }
        )
    failure_events = sorted(
        event
        for event in events
        if event in {"failed", "rejected_response", "tokenize_failed", "tokenize_rejected"}
    )
    return {
        "all_rows_accounted": all_rows_accounted,
        "bytes": len(raw),
        "calls": calls,
        "completion_dispatches": events.count("generation_dispatch_intent"),
        "completed_event_sequences_valid": completed_event_sequences_valid,
        "completed_calls": events.count("completed"),
        "event_count": len(events),
        "events": events,
        "failure_events": failure_events,
        "operation_order_valid": [item["operation"] for item in calls]
        == expected_operations[: len(calls)],
        "path": path.name,
        "raw_preimages_valid": raw_preimages_valid,
        "sha256": _digest(raw),
        "tokenize_posts": events.count("tokenize_intent"),
    }


def _file_manifest(paths: Sequence[Path]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda item: item.name):
        if not path.is_file() or path.is_symlink():
            raise G1MicroError("run artifact is absent or linked")
        raw = path.read_bytes()
        result.append({"bytes": len(raw), "path": path.name, "sha256": _digest(raw)})
    return result


def _descriptive_pattern_observed(probes: Mapping[str, Mapping[str, Any]]) -> bool:
    scores = {name: bool(record["payload"]["correct"]) for name, record in probes.items()}
    return (
        scores == {
            "ACTIVE": True,
            "NO_UPDATE": False,
            "OUTCOME_INDEPENDENT_SHAM": False,
            "REMOVE": False,
            "RESTORE": True,
        }
    )


def _execute_exploratory_slice(
    *,
    backend: ChatBackend,
    protocol: Mapping[str, Any],
    protocol_sha256: str,
    output_dir: str | Path,
    runtime_binding: Mapping[str, Any] | None,
    source_manifest: Mapping[str, str],
) -> dict[str, Any]:
    """Execute the already-claimed eight-call slice with no provider retry."""

    _require_sha(protocol_sha256, "protocol")
    if canonical_sha256(protocol) != protocol_sha256:
        raise G1MicroError("protocol digest differs from the supplied freeze")
    task = task_from_protocol(protocol)
    output = Path(output_dir)
    if output.exists():
        raise G1MicroError("output directory must be fresh")
    output.mkdir(parents=True)
    arm = G1MicroArm(
        backend=backend,
        journal_path=output / "attempt_ledger.jsonl",
        isolation_id=task.episode_uid,
    )
    active_store = G1MicroStore(output / "active.sqlite3")
    sham_store = G1MicroStore(output / "sham.sqlite3")
    genesis = make_genesis_state()
    permit_policy = make_permit_policy(task, protocol_sha256)
    sham_commitment = make_record(
        "PlaceboFeedbackCommitment",
        owner_uid="principal:g1-micro-placebo-custodian",
        payload={
            "choice_was_correct": task.sham_correct,
            "episode_uid": task.episode_uid,
            "formed_before_trajectory": True,
            "task_commitment_sha256": task.commitment_sha256,
        },
    )

    trajectory_choice, trajectory_call = arm.trajectory(task)
    trajectory = make_record(
        "SealedTrajectory",
        owner_uid=PRINCIPALS["executor_uid"],
        payload={
            "call_evidence": trajectory_call,
            "choice": trajectory_choice,
            "episode_uid": task.episode_uid,
            "input": task.train_input,
            "output_choices": list(task.choices(task.train_input)),
            "task_commitment_sha256": task.commitment_sha256,
        },
    )
    actual_correct = trajectory_choice == task.choice(
        task.train_input, task.hidden_operator
    )
    outcome = _make_feedback(
        task=task,
        trajectory=trajectory,
        correct=actual_correct,
        feedback_kind="LocalOutcomeObservation",
    )
    sham_feedback = _make_feedback(
        task=task,
        trajectory=trajectory,
        correct=task.sham_correct,
        feedback_kind="OutcomeIndependentShamFeedback",
        commitment=sham_commitment,
    )

    active_response, active_call = arm.propose(
        task,
        trajectory_choice=trajectory_choice,
        trajectory_sha256=trajectory["record_sha256"],
        feedback_correct=actual_correct,
        feedback_sha256=outcome["record_sha256"],
    )
    sham_response, sham_call = arm.propose(
        task,
        trajectory_choice=trajectory_choice,
        trajectory_sha256=trajectory["record_sha256"],
        feedback_correct=task.sham_correct,
        feedback_sha256=sham_feedback["record_sha256"],
    )
    active_proposal = _proposal_record(
        task=task,
        response=active_response,
        trajectory=trajectory,
        feedback=outcome,
        call_evidence=active_call,
    )
    sham_proposal = _proposal_record(
        task=task,
        response=sham_response,
        trajectory=trajectory,
        feedback=sham_feedback,
        call_evidence=sham_call,
    )
    active_credit = make_credit(
        task=task,
        trajectory=trajectory,
        feedback=outcome,
        proposal=active_proposal,
    )
    sham_credit = make_credit(
        task=task,
        trajectory=trajectory,
        feedback=sham_feedback,
        proposal=sham_proposal,
    )
    active_admission = _admit_branch(
        store=active_store,
        task=task,
        permit_policy=permit_policy,
        trajectory=trajectory,
        feedback=outcome,
        proposal=active_proposal,
        credit=active_credit,
    )
    sham_admission = _admit_branch(
        store=sham_store,
        task=task,
        permit_policy=permit_policy,
        trajectory=trajectory,
        feedback=sham_feedback,
        proposal=sham_proposal,
        credit=sham_credit,
    )
    if active_admission is None or sham_admission is None:
        raise G1MicroError("proposal failed the precommitted credit rule; no probe calls made")

    active_state = active_store.active()
    sham_state = sham_store.active()
    probes: dict[str, dict[str, Any]] = {}
    for branch, state in (
        ("ACTIVE", active_state.state),
        ("OUTCOME_INDEPENDENT_SHAM", sham_state.state),
        ("NO_UPDATE", genesis),
    ):
        choice, compiled, evidence = arm.probe(task, state=state)
        probes[branch] = _probe_record(
            branch=branch,
            task=task,
            state=state,
            choice=choice,
            compiled=compiled,
            call_evidence=evidence,
        )

    active_snapshot_sha = active_state.state_sha256
    source_admission_sha = active_admission["admission"]["record_sha256"]
    remove_receipt = active_store.activate_exact(
        state_sha256(genesis),
        expected_generation=active_state.generation,
        operation="REMOVE_TO_GENESIS",
        source_admission_sha256=source_admission_sha,
    )
    removed = active_store.active()
    choice, compiled, evidence = arm.probe(task, state=removed.state)
    probes["REMOVE"] = _probe_record(
        branch="REMOVE",
        task=task,
        state=removed.state,
        choice=choice,
        compiled=compiled,
        call_evidence=evidence,
    )
    restore_receipt = active_store.activate_exact(
        active_snapshot_sha,
        expected_generation=removed.generation,
        operation="RESTORE_ACTIVE_SNAPSHOT",
        source_admission_sha256=source_admission_sha,
    )
    restored = active_store.active()
    if restored.state_sha256 != active_snapshot_sha:
        raise G1MicroError("restoration did not recover exact active state bytes")
    choice, compiled, evidence = arm.probe(task, state=restored.state)
    probes["RESTORE"] = _probe_record(
        branch="RESTORE",
        task=task,
        state=restored.state,
        choice=choice,
        compiled=compiled,
        call_evidence=evidence,
    )

    active_store.checkpoint()
    sham_store.checkpoint()
    journal = _journal_manifest(output / "attempt_ledger.jsonl")
    if (
        journal["completed_calls"] != 8
        or journal["all_rows_accounted"] is not True
        or journal["tokenize_posts"] != 8
        or journal["completion_dispatches"] != 8
        or journal["completed_event_sequences_valid"] is not True
        or journal["raw_preimages_valid"] is not True
        or journal["failure_events"]
        or journal["operation_order_valid"] is not True
        or len(arm.ledger) != 8
    ):
        raise G1MicroError("live call chronology differs from the frozen call contract")
    terminal = "EXPLORATORY_OBSERVATION_RECORDED_NO_EFFICACY_INFERENCE"
    sham_feedback_contrast = (
        "UNINFORMATIVE_SHAM_EQUALS_ACTIVE_FEEDBACK"
        if task.sham_correct is actual_correct
        else "INFORMATIVE_DIFFERENT_FEEDBACK_SINGLE_CASE_ONLY"
    )
    unsigned = {
        "backend_identity": dict(backend.identity),
        "byte_exact_model_response_required": False,
        "completion_call_count": len(arm.ledger),
        "claim_ceiling": "INSTRUMENT_VALIDATION_ONLY",
        "credit": {"ACTIVE": active_credit, "OUTCOME_INDEPENDENT_SHAM": sham_credit},
        "gate_status": {"G0": "NOT_PASSED", "G1": "NOT_EVALUATED"},
        "descriptive_five_branch_pattern_observed": _descriptive_pattern_observed(probes),
        "evaluator_boundary": "SAME_PROCESS_LOCAL_INSTRUMENT_NOT_INDEPENDENTLY_OWNED",
        "journal": journal,
        "local_admissions": {
            "ACTIVE": active_admission,
            "OUTCOME_INDEPENDENT_SHAM": sham_admission,
        },
        "outcome": outcome,
        "permit_policy": permit_policy,
        "probes": probes,
        "proposals": {
            "ACTIVE": active_proposal,
            "OUTCOME_INDEPENDENT_SHAM": sham_proposal,
        },
        "protocol_canonical_sha256": protocol_sha256,
        "runtime_binding": None if runtime_binding is None else dict(runtime_binding),
        "schema_version": PROTOCOL,
        "scope_nonclaim": LOCAL_SCOPE_NONCLAIM,
        "sham_commitment": sham_commitment,
        "sham_feedback_contrast": sham_feedback_contrast,
        "sham_feedback": sham_feedback,
        "state_interventions": {
            "REMOVE": remove_receipt,
            "RESTORE": restore_receipt,
        },
        "state_store_artifacts": _file_manifest(
            (output / "active.sqlite3", output / "sham.sqlite3")
        ),
        "store_receipts": {
            "ACTIVE": active_store.logical_receipts(),
            "OUTCOME_INDEPENDENT_SHAM": sham_store.logical_receipts(),
        },
        "source_manifest": dict(source_manifest),
        "task_reveal": task.canonical(),
        "terminal": terminal,
        "tokenize_post_count": len(arm.ledger),
        "total_http_post_count": len(arm.ledger) * 2,
        "trajectory": trajectory,
        "verification_scope": "LOCAL_STRUCTURAL_CONSISTENCY_ONLY",
    }
    bundle = {**unsigned, "bundle_sha256": canonical_sha256(unsigned)}
    verify_exploratory_bundle(bundle, base_dir=output)
    _atomic_write(output / "result.json", canonical_json_bytes(bundle))
    return bundle


def _claim_execution(
    *,
    registry_path: Path,
    protocol_sha256: str,
    task: MicroTask,
    output_dir: Path,
    runtime_binding: Mapping[str, Any] | None,
    source_manifest: Mapping[str, str],
) -> dict[str, Any]:
    if not registry_path.is_absolute() or registry_path.is_symlink():
        raise G1MicroError("execution registry must be one absolute non-linked path")
    if not registry_path.parent.is_dir() or registry_path.parent.is_symlink():
        raise G1MicroError("execution registry parent is absent or linked")
    start = make_record(
        "ExecutionStart",
        owner_uid="principal:g1-micro-execution-custodian",
        payload={
            "episode_uid": task.episode_uid,
            "output_dir": str(output_dir),
            "protocol_sha256": protocol_sha256,
            "retry_or_refill_permitted": False,
            "runtime_binding_sha256": (
                None if runtime_binding is None else runtime_binding["record_sha256"]
            ),
            "source_manifest": dict(source_manifest),
            "status": "STARTED_BEFORE_FIRST_HTTP_POST",
            "task_commitment_sha256": task.commitment_sha256,
        },
        refs=(
            ()
            if runtime_binding is None
            else (_ref("runtime_binding", runtime_binding),)
        ),
    )
    _atomic_write(registry_path, canonical_json_bytes(start), create_parent=False)
    return start


def _seal_execution_registry(
    registry_path: Path,
    *,
    start: Mapping[str, Any],
    status: str,
    result_sha256: str | None,
    abort_sha256: str | None,
) -> dict[str, Any]:
    if status not in {"ABORTED_NO_RERUN", "COMPLETED_NO_RERUN"}:
        raise G1MicroError("execution seal status is invalid")
    seal = make_record(
        "ExecutionSeal",
        owner_uid="principal:g1-micro-execution-custodian",
        payload={
            "abort_sha256": abort_sha256,
            "result_sha256": result_sha256,
            "start": dict(start),
            "status": status,
        },
        refs=(_ref("execution_start", start),),
    )
    _replace_canonical(registry_path, canonical_json_bytes(seal))
    return seal


def _run_exploratory_slice_with_backend(
    *,
    backend: ChatBackend,
    protocol: Mapping[str, Any],
    protocol_sha256: str,
    output_dir: str | Path,
    execution_registry_path: str | Path,
    runtime_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Backend-injected producer primitive used only by tests and the live entrypoint."""

    _validate_protocol(protocol)
    if canonical_sha256(protocol) != protocol_sha256:
        raise G1MicroError("protocol digest differs from the supplied freeze")
    task = task_from_protocol(protocol)
    source_manifest = _source_manifest()
    if runtime_binding is not None:
        validate_dgx_runtime_binding(
            runtime_binding,
            protocol=protocol,
            protocol_sha256=protocol_sha256,
            source_manifest=source_manifest,
        )
    output = Path(output_dir)
    registry = Path(execution_registry_path)
    declared_registry = protocol.get("consumption_registry")
    if not isinstance(declared_registry, Mapping) or str(registry) != declared_registry.get(
        "path"
    ):
        raise G1MicroError("execution registry differs from the protocol")
    if output.exists():
        raise G1MicroError("output directory must be fresh")
    start = _claim_execution(
        registry_path=registry,
        protocol_sha256=protocol_sha256,
        task=task,
        output_dir=output,
        runtime_binding=runtime_binding,
        source_manifest=source_manifest,
    )
    try:
        bundle = _execute_exploratory_slice(
            backend=backend,
            protocol=protocol,
            protocol_sha256=protocol_sha256,
            output_dir=output,
            runtime_binding=runtime_binding,
            source_manifest=source_manifest,
        )
    except BaseException as error:
        output.mkdir(parents=True, exist_ok=True)
        journal_path = output / "attempt_ledger.jsonl"
        journal = _journal_manifest(journal_path) if journal_path.is_file() else None
        abort = make_record(
            "ExecutionAbort",
            owner_uid="principal:g1-micro-execution-custodian",
            payload={
                "error_message_sha256": _digest(str(error).encode("utf-8")),
                "error_type": type(error).__name__,
                "journal": journal,
                "retry_or_refill_permitted": False,
                "terminal": "INCONCLUSIVE_MEASUREMENT_NOT_READY",
            },
            refs=(_ref("execution_start", start),),
        )
        abort_path = output / "abort.json"
        if not abort_path.exists():
            _atomic_write(abort_path, canonical_json_bytes(abort))
        _seal_execution_registry(
            registry,
            start=start,
            status="ABORTED_NO_RERUN",
            result_sha256=None,
            abort_sha256=abort["record_sha256"],
        )
        raise
    _seal_execution_registry(
        registry,
        start=start,
        status="COMPLETED_NO_RERUN",
        result_sha256=bundle["bundle_sha256"],
        abort_sha256=None,
    )
    return bundle


def _record_tree(value: object) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        if "record_sha256" in value:
            records.append(value)
        for child in value.values():
            records.extend(_record_tree(child))
    elif isinstance(value, list):
        for child in value:
            records.extend(_record_tree(child))
    return records


def verify_exploratory_bundle(
    bundle: Mapping[str, Any], *, base_dir: str | Path | None = None
) -> dict[str, Any]:
    """Reconstruct the local state and scores without trusting the terminal."""

    expected_fields = {
        "backend_identity",
        "bundle_sha256",
        "byte_exact_model_response_required",
        "completion_call_count",
        "claim_ceiling",
        "credit",
        "descriptive_five_branch_pattern_observed",
        "evaluator_boundary",
        "gate_status",
        "journal",
        "local_admissions",
        "outcome",
        "permit_policy",
        "probes",
        "proposals",
        "protocol_canonical_sha256",
        "runtime_binding",
        "schema_version",
        "scope_nonclaim",
        "sham_commitment",
        "sham_feedback_contrast",
        "sham_feedback",
        "source_manifest",
        "state_interventions",
        "state_store_artifacts",
        "store_receipts",
        "task_reveal",
        "terminal",
        "tokenize_post_count",
        "total_http_post_count",
        "trajectory",
        "verification_scope",
    }
    if not isinstance(bundle, Mapping) or set(bundle) != expected_fields:
        raise G1MicroError("exploratory bundle field set is invalid")
    unsigned = dict(bundle)
    digest = unsigned.pop("bundle_sha256")
    if digest != canonical_sha256(unsigned):
        raise G1MicroError("exploratory bundle digest mismatch")
    _require_sha(bundle["protocol_canonical_sha256"], "bundle protocol")
    _validate_source_manifest(bundle["source_manifest"])
    if bundle["runtime_binding"] is not None:
        validate_record(bundle["runtime_binding"], kind="DGXFreshRuntimeBinding")
    if (
        bundle["schema_version"] != PROTOCOL
        or bundle["scope_nonclaim"] != LOCAL_SCOPE_NONCLAIM
        or bundle["claim_ceiling"] != "INSTRUMENT_VALIDATION_ONLY"
        or bundle["gate_status"] != {"G0": "NOT_PASSED", "G1": "NOT_EVALUATED"}
        or bundle["byte_exact_model_response_required"] is not False
        or bundle["completion_call_count"] != 8
        or bundle["tokenize_post_count"] != 8
        or bundle["total_http_post_count"] != 16
        or bundle["verification_scope"] != "LOCAL_STRUCTURAL_CONSISTENCY_ONLY"
        or bundle["evaluator_boundary"]
        != "SAME_PROCESS_LOCAL_INSTRUMENT_NOT_INDEPENDENTLY_OWNED"
        or bundle["terminal"] not in TERMINALS
    ):
        raise G1MicroError("exploratory bundle claim or execution boundary drifted")
    task = MicroTask(**{
        key: bundle["task_reveal"][key]
        for key in (
            "study_uid",
            "episode_uid",
            "cue",
            "operand",
            "train_input",
            "fresh_input",
            "hidden_operator",
            "sham_correct",
        )
    })
    for record in _record_tree(bundle):
        validate_record(record)
    trajectory = bundle["trajectory"]
    choice = trajectory["payload"]["choice"]
    if choice not in task.choices(task.train_input):
        raise G1MicroError("trajectory choice is outside the task")
    expected_actual = choice == task.choice(task.train_input, task.hidden_operator)
    expected_sham_contrast = (
        "UNINFORMATIVE_SHAM_EQUALS_ACTIVE_FEEDBACK"
        if task.sham_correct is expected_actual
        else "INFORMATIVE_DIFFERENT_FEEDBACK_SINGLE_CASE_ONLY"
    )
    if (
        bundle["outcome"]["payload"]["choice_was_correct"] is not expected_actual
        or bundle["sham_feedback"]["payload"]["choice_was_correct"]
        is not task.sham_correct
        or bundle["sham_commitment"]["payload"]["choice_was_correct"]
        is not task.sham_correct
        or bundle["sham_feedback_contrast"] != expected_sham_contrast
    ):
        raise G1MicroError("outcome or sham feedback cannot be reconstructed")
    _validate_permit_policy(
        bundle["permit_policy"],
        task=task,
        protocol_sha256=bundle["protocol_canonical_sha256"],
    )
    admissions = bundle["local_admissions"]
    for branch, feedback in (
        ("ACTIVE", bundle["outcome"]),
        ("OUTCOME_INDEPENDENT_SHAM", bundle["sham_feedback"]),
    ):
        proposal = bundle["proposals"][branch]
        recomputed_credit = make_credit(
            task=task,
            trajectory=trajectory,
            feedback=feedback,
            proposal=proposal,
        )
        if canonical_json_bytes(recomputed_credit) != canonical_json_bytes(
            bundle["credit"][branch]
        ):
            raise G1MicroError(f"{branch} credit cannot be reconstructed")
        admission = admissions[branch]
        if admission is None or recomputed_credit["payload"]["decision"] != "CREDIT":
            raise G1MicroError("completed bundle requires two credited local admissions")
        successor = admission["successor_state"]
        validate_state(successor)
        disposition = admission["disposition"]
        if successor["dispositions"] != [disposition]:
            raise G1MicroError("admission successor differs from its disposition")
        if disposition["payload"]["operator"] != proposal["payload"]["operation"]:
            raise G1MicroError("admitted disposition differs from the proposal")
        permit = admission["permit"]
        _validate_local_permit(permit)
        permit_payload = permit["payload"]
        permit_refs = {item["kind"]: item["sha256"] for item in permit["refs"]}
        if (
            permit_payload["successor_state_sha256"] != state_sha256(successor)
            or permit_payload["base_state_sha256"] != state_sha256(make_genesis_state())
            or permit_refs.get("permit_policy")
            != bundle["permit_policy"]["record_sha256"]
            or permit_refs.get("trajectory") != trajectory["record_sha256"]
            or permit_refs.get("feedback") != feedback["record_sha256"]
            or permit_refs.get("proposal") != proposal["record_sha256"]
            or permit_refs.get("credit") != recomputed_credit["record_sha256"]
            or permit_refs.get("disposition") != disposition["record_sha256"]
            or admission["admission"]["payload"]["resulting_state_sha256"]
            != state_sha256(successor)
            or admission["consumption"]["payload"]["admission_sha256"]
            != admission["admission"]["record_sha256"]
        ):
            raise G1MicroError("local permit, consumption, and admission do not close")
    probes = bundle["probes"]
    if set(probes) != {
        "ACTIVE",
        "NO_UPDATE",
        "OUTCOME_INDEPENDENT_SHAM",
        "REMOVE",
        "RESTORE",
    }:
        raise G1MicroError("probe branch set is incomplete")
    active_state = admissions["ACTIVE"]["successor_state"]
    sham_state = admissions["OUTCOME_INDEPENDENT_SHAM"]["successor_state"]
    expected_states = {
        "ACTIVE": active_state,
        "NO_UPDATE": make_genesis_state(),
        "OUTCOME_INDEPENDENT_SHAM": sham_state,
        "REMOVE": make_genesis_state(),
        "RESTORE": active_state,
    }
    correct_choice = task.choice(task.fresh_input, task.hidden_operator)
    for branch, probe in probes.items():
        payload = probe["payload"]
        expected_state = expected_states[branch]
        expected_compiled = compile_disposition(expected_state, cue=task.cue)
        if (
            payload["state_sha256"] != state_sha256(expected_state)
            or payload["compiled_disposition"] != expected_compiled
            or payload["correct_choice"] != correct_choice
            or payload["correct"] is not (payload["choice"] == correct_choice)
        ):
            raise G1MicroError(f"{branch} behavior observation cannot be reconstructed")
    remove = bundle["state_interventions"]["REMOVE"]["payload"]
    restore = bundle["state_interventions"]["RESTORE"]["payload"]
    if (
        remove["operation"] != "REMOVE_TO_GENESIS"
        or remove["base_state_sha256"] != state_sha256(active_state)
        or remove["resulting_state_sha256"] != state_sha256(make_genesis_state())
        or restore["operation"] != "RESTORE_ACTIVE_SNAPSHOT"
        or restore["base_state_sha256"] != state_sha256(make_genesis_state())
        or restore["resulting_state_sha256"] != state_sha256(active_state)
    ):
        raise G1MicroError("remove/restore state identities do not reconstruct")
    descriptive_pattern = _descriptive_pattern_observed(probes)
    if bundle["descriptive_five_branch_pattern_observed"] is not descriptive_pattern:
        raise G1MicroError("descriptive branch pattern flag is not reconstructable")
    expected_terminal = "EXPLORATORY_OBSERVATION_RECORDED_NO_EFFICACY_INFERENCE"
    if bundle["terminal"] != expected_terminal:
        raise G1MicroError("exploratory terminal differs from the branch observations")
    journal = bundle["journal"]
    if (
        journal["completed_calls"] != 8
        or journal["all_rows_accounted"] is not True
        or journal["tokenize_posts"] != 8
        or journal["completion_dispatches"] != 8
        or journal["completed_event_sequences_valid"] is not True
        or journal["raw_preimages_valid"] is not True
        or journal["failure_events"]
        or journal["operation_order_valid"] is not True
        or len(journal["calls"]) != 8
    ):
        raise G1MicroError("journal does not satisfy the frozen eight-call chronology")
    evidence = [
        trajectory["payload"]["call_evidence"],
        bundle["proposals"]["ACTIVE"]["payload"]["call_evidence"],
        bundle["proposals"]["OUTCOME_INDEPENDENT_SHAM"]["payload"]["call_evidence"],
        *(probes[name]["payload"]["call_evidence"] for name in (
            "ACTIVE",
            "OUTCOME_INDEPENDENT_SHAM",
            "NO_UPDATE",
            "REMOVE",
            "RESTORE",
        )),
    ]
    for observed, call in zip(evidence, journal["calls"], strict=True):
        if any(
            observed[field] != call[field]
            for field in (
                "completion_request_sha256",
                "completion_response_sha256",
                "token_preflight_receipt_sha256",
            )
        ):
            raise G1MicroError("recorded call evidence differs from the raw journal")
    if base_dir is not None:
        path = Path(base_dir) / journal["path"]
        if not path.is_file() or _digest(path.read_bytes()) != journal["sha256"]:
            raise G1MicroError("attempt journal bytes differ from the bundle")
        if _journal_manifest(path) != journal:
            raise G1MicroError("attempt journal manifest cannot be reconstructed")
        store_paths = [Path(base_dir) / item["path"] for item in bundle["state_store_artifacts"]]
        if _file_manifest(store_paths) != bundle["state_store_artifacts"]:
            raise G1MicroError("state-store artifact manifest cannot be reconstructed")
        stores = {path.name: path for path in store_paths}
        if set(stores) != {"active.sqlite3", "sham.sqlite3"}:
            raise G1MicroError("state-store artifact names drifted")
        retained_receipts = {
            "ACTIVE": _logical_receipts_from_database(stores["active.sqlite3"]),
            "OUTCOME_INDEPENDENT_SHAM": _logical_receipts_from_database(
                stores["sham.sqlite3"]
            ),
        }
        if retained_receipts != bundle["store_receipts"]:
            raise G1MicroError("retained state stores differ from the recorded receipts")
    return {
        "bundle_sha256": digest,
        "exact_state_restore": True,
        "provider_response_byte_stability_required": False,
        "terminal": expected_terminal,
        "verification": "VALID_LOCAL_STRUCTURAL_CONSISTENCY",
    }


def _atomic_write(path: Path, raw: bytes, *, create_parent: bool = True) -> None:
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if path.exists() or temporary.exists():
        raise G1MicroError(f"refusing to overwrite {path}")
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _replace_canonical(path: Path, raw: bytes) -> None:
    if not path.is_file() or path.is_symlink():
        raise G1MicroError("execution registry disappeared or became linked")
    temporary = path.with_name(path.name + ".seal.tmp")
    if temporary.exists():
        raise G1MicroError("execution registry seal temporary already exists")
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def verify_bundle_file(path: str | Path) -> dict[str, Any]:
    bundle_path = Path(path)
    bundle = _canonical_object(bundle_path.read_bytes(), "result bundle")
    return verify_exploratory_bundle(bundle, base_dir=bundle_path.parent)


def verify_frozen_execution_files(
    *,
    bundle_path: str | Path,
    protocol_path: str | Path,
    execution_registry_path: str | Path,
) -> dict[str, Any]:
    """Join local structure to the frozen protocol and durable one-shot seal."""

    result_path = Path(bundle_path)
    registry_path = Path(execution_registry_path)
    if (
        not result_path.is_file()
        or result_path.is_symlink()
        or not registry_path.is_file()
        or registry_path.is_symlink()
    ):
        raise G1MicroError("frozen execution artifacts are absent or linked")
    protocol, protocol_sha256 = load_protocol(protocol_path)
    if str(registry_path) != protocol["consumption_registry"]["path"]:
        raise G1MicroError("verification registry differs from the preregistration")
    bundle = _canonical_object(result_path.read_bytes(), "result bundle")
    local = verify_exploratory_bundle(bundle, base_dir=result_path.parent)
    task = task_from_protocol(protocol)
    if (
        bundle["protocol_canonical_sha256"] != protocol_sha256
        or bundle["task_reveal"] != task.canonical()
    ):
        raise G1MicroError("result does not join to the frozen protocol task")
    seal = _canonical_object(registry_path.read_bytes(), "execution registry seal")
    validate_record(seal, kind="ExecutionSeal")
    if (
        seal["owner_uid"] != "principal:g1-micro-execution-custodian"
        or set(seal["payload"]) != {"abort_sha256", "result_sha256", "start", "status"}
        or seal["payload"]["status"] != "COMPLETED_NO_RERUN"
        or seal["payload"]["abort_sha256"] is not None
        or seal["payload"]["result_sha256"] != bundle["bundle_sha256"]
    ):
        raise G1MicroError("execution registry is not the completed one-shot seal")
    start = seal["payload"]["start"]
    validate_record(start, kind="ExecutionStart")
    start_payload = start["payload"]
    if (
        start["owner_uid"] != "principal:g1-micro-execution-custodian"
        or seal["refs"] != [_ref("execution_start", start)]
        or set(start_payload)
        != {
            "episode_uid",
            "output_dir",
            "protocol_sha256",
            "retry_or_refill_permitted",
            "runtime_binding_sha256",
            "source_manifest",
            "status",
            "task_commitment_sha256",
        }
        or start_payload["episode_uid"] != task.episode_uid
        or start_payload["protocol_sha256"] != protocol_sha256
        or start_payload["task_commitment_sha256"] != task.commitment_sha256
        or start_payload["retry_or_refill_permitted"] is not False
        or start_payload["status"] != "STARTED_BEFORE_FIRST_HTTP_POST"
        or start_payload["source_manifest"] != bundle["source_manifest"]
        or not isinstance(start_payload["output_dir"], str)
        or not Path(start_payload["output_dir"]).is_absolute()
    ):
        raise G1MicroError("execution start does not join protocol, source, and seal")
    runtime_binding = bundle["runtime_binding"]
    if runtime_binding is None:
        raise G1MicroError("frozen live execution lacks a measured DGX runtime binding")
    validate_dgx_runtime_binding(
        runtime_binding,
        protocol=protocol,
        protocol_sha256=protocol_sha256,
        source_manifest=bundle["source_manifest"],
    )
    if (
        start_payload["runtime_binding_sha256"] != runtime_binding["record_sha256"]
        or start["refs"] != [_ref("runtime_binding", runtime_binding)]
        or runtime_binding["payload"]["protocol_file_sha256"]
        != _digest(Path(protocol_path).read_bytes())
    ):
        raise G1MicroError("execution start does not bind the measured DGX runtime")
    identity = bundle["backend_identity"]
    binding = protocol["live_binding"]
    if (
        not isinstance(identity, Mapping)
        or identity.get("adapter") != "openai-compatible-stateless/v1"
        or identity.get("endpoint") != binding["endpoint_origin"]
        or identity.get("model") != binding["served_model"]
        or identity.get("expected_max_model_len") != binding["expected_max_model_len"]
        or identity.get("retry_count") != 0
        or identity.get("token_preflight_transport_trust")
        != "loopback-without-api-key-middleware"
    ):
        raise G1MicroError("result backend differs from the frozen loopback binding")
    return {
        **local,
        "protocol_canonical_sha256": protocol_sha256,
        "registry_sha256": _digest(registry_path.read_bytes()),
        "runtime_image_identity_verified": True,
        "verification": "VALID_LOCAL_PROTOCOL_REGISTRY_BACKEND_BINDING",
    }


def _preflight(
    *,
    protocol_path: Path,
    endpoint: str,
    model: str,
    expected_max_model_len: int,
    output_dir: Path,
    execution_registry_path: Path,
) -> dict[str, Any]:
    protocol, protocol_sha = load_protocol(protocol_path)
    task = task_from_protocol(protocol)
    binding = protocol["live_binding"]
    config = OpenAIBackendConfig(
        endpoint=endpoint,
        model=model,
        expected_max_model_len=expected_max_model_len,
    )
    if urlsplit(config.endpoint).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise G1MicroError("audited G1 micro execution requires a loopback model endpoint")
    if (
        config.endpoint != binding["endpoint_origin"]
        or config.model != binding["served_model"]
        or config.expected_max_model_len != binding["expected_max_model_len"]
    ):
        raise G1MicroError("CLI model endpoint differs from the frozen live binding")
    if output_dir.exists():
        raise G1MicroError("output directory must not exist at preflight")
    output_root_raw = os.environ.get("HSWM_OUTPUT_ROOT")
    if not output_root_raw:
        raise G1MicroError("HSWM_OUTPUT_ROOT must be supplied by the execution wrapper")
    output_root = Path(output_root_raw)
    if (
        not output_root.is_absolute()
        or output_root.is_symlink()
        or not output_root.is_dir()
        or not output_dir.is_absolute()
        or output_root not in output_dir.parents
    ):
        raise G1MicroError("output directory is outside the wrapper-owned output root")
    if (
        str(execution_registry_path) != protocol["consumption_registry"]["path"]
        or execution_registry_path.exists()
        or not execution_registry_path.parent.is_dir()
        or execution_registry_path.parent.is_symlink()
    ):
        raise G1MicroError("durable one-shot execution registry is unavailable")
    return {
        "completion_post_cap": 8,
        "model": config.model,
        "network_calls": 0,
        "output_created": False,
        "preflight": "READY_FOR_EXPLORATORY_LIVE_CALLS",
        "protocol_canonical_sha256": protocol_sha,
        "tokenize_post_cap": 8,
        "total_http_post_cap": 16,
        "scope_nonclaim": LOCAL_SCOPE_NONCLAIM,
        "task_commitment_sha256": task.commitment_sha256,
    }


def run_exploratory_slice(
    *,
    protocol_path: str | Path,
    endpoint: str,
    model: str,
    expected_max_model_len: int,
    output_dir: str | Path,
    execution_registry_path: str | Path,
    runtime_binding_path: str | Path,
) -> dict[str, Any]:
    """Official live entrypoint: preflight, consume once, run, and verify joins."""

    protocol_file = Path(protocol_path)
    output = Path(output_dir)
    registry = Path(execution_registry_path)
    _preflight(
        protocol_path=protocol_file,
        endpoint=endpoint,
        model=model,
        expected_max_model_len=expected_max_model_len,
        output_dir=output,
        execution_registry_path=registry,
    )
    protocol, protocol_sha = load_protocol(protocol_file)
    runtime_binding_file = Path(runtime_binding_path)
    if not runtime_binding_file.is_file() or runtime_binding_file.is_symlink():
        raise G1MicroError("measured DGX runtime binding is absent or linked")
    runtime_binding = _canonical_object(
        runtime_binding_file.read_bytes(), "DGX runtime binding"
    )
    validate_dgx_runtime_binding(
        runtime_binding,
        protocol=protocol,
        protocol_sha256=protocol_sha,
        source_manifest=_source_manifest(),
    )
    backend = OpenAICompatibleBackend(
        OpenAIBackendConfig(
            endpoint=endpoint,
            model=model,
            expected_max_model_len=expected_max_model_len,
        )
    )
    bundle = _run_exploratory_slice_with_backend(
        backend=backend,
        protocol=protocol,
        protocol_sha256=protocol_sha,
        output_dir=output,
        execution_registry_path=registry,
        runtime_binding=runtime_binding,
    )
    verify_frozen_execution_files(
        bundle_path=output / "result.json",
        protocol_path=protocol_file,
        execution_registry_path=registry,
    )
    return bundle


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--expected-max-model-len", type=int, default=32768)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execution-registry", type=Path, required=True)
    parser.add_argument("--runtime-binding", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    preflight = _preflight(
        protocol_path=args.protocol,
        endpoint=args.endpoint,
        model=args.model,
        expected_max_model_len=args.expected_max_model_len,
        output_dir=args.output_dir,
        execution_registry_path=args.execution_registry,
    )
    if args.preflight_only:
        print(canonical_json_bytes(preflight).decode("utf-8"))
        return 0
    if args.runtime_binding is None:
        raise G1MicroError("live execution requires --runtime-binding")
    bundle = run_exploratory_slice(
        protocol_path=args.protocol,
        endpoint=args.endpoint,
        model=args.model,
        expected_max_model_len=args.expected_max_model_len,
        output_dir=args.output_dir,
        execution_registry_path=args.execution_registry,
        runtime_binding_path=args.runtime_binding,
    )
    print(canonical_json_bytes({
        "bundle_sha256": bundle["bundle_sha256"],
        "result_path": str(args.output_dir / "result.json"),
        "terminal": bundle["terminal"],
    }).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
