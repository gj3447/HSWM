#!/usr/bin/env python3
"""Pure, strict adjudicator for the DNRD-4S1 diagnostic candidate.

This file intentionally imports only the Python standard library.  It judges
the candidate artifact, never a live runtime: a passing judgment is an
engineering-integrity diagnostic only, not an efficacy, Permit, or learning
verdict.
"""

from __future__ import annotations

from datetime import datetime, timezone
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
import sys
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit
from uuid import UUID


CANDIDATE_SCHEMA = "hswm-dnrd-candidate/v3"
INCONCLUSIVE_SCHEMA = "hswm-dnrd-inconclusive-occurrence/v2"
JUDGMENT_SCHEMA = "hswm-dnrd-judgment/v3"
EXPERIMENT_ID = "HSWM-DNRD-4S1"
PROTOCOL_VERSION = "v4s1"
SEED_DOMAIN = "HSWM-DNRD-4S1-FUTURE-SEED-V1"
STRUCTURED_OUTPUT_QUALIFICATION_SCHEMA = "hswm-dnrd4s1-structured-output-qualification-summary/v1"
STRUCTURED_OUTPUT_QUALIFICATION_DOMAIN = "HSWM-DNRD4S1-STRUCTURED-OUTPUT-QUALIFICATION-v1"


def _validate_ci_v2_receipt(receipt: Mapping[str, Any], label: str) -> None:
    """Recheck the raw GitHub run/list anti-selection proof without network access."""
    query = receipt["discovery_query"]
    head_sha = receipt["head_sha"]
    expected = {"request_path": f"/repos/gj3447/HSWM/actions/workflows/ci.yml/runs?event=push&branch=main&head_sha={head_sha}&per_page=100&page=1", "workflow_path": ".github/workflows/ci.yml", "event": "push", "branch": "main", "head_sha": head_sha, "per_page": 100, "page": 1}
    if query != expected:
        raise BundleRefusal(f"{label} discovery query drifted")
    raw_list = _string(receipt["raw_list_response_utf8"], f"{label}.raw_list_response_utf8")
    if _sha_bytes(raw_list.encode()) != _sha(receipt["raw_list_response_sha256"], f"{label}.raw_list_response_sha256"):
        raise BundleRefusal(f"{label} raw workflow-runs list digest mismatch")
    listed = _parse_json_bytes(raw_list.encode(), f"{label} raw workflow-runs list", canonical=False)
    raw = _parse_json_bytes(_string(receipt["raw_response_utf8"], f"{label}.raw_response_utf8").encode(), f"{label} raw response", canonical=False)
    rows = listed.get("workflow_runs") if type(listed) is dict else None
    if type(raw) is not dict or type(listed) is not dict or listed.get("total_count") != 1:
        raise BundleRefusal(f"{label} workflow-runs list is malformed")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise BundleRefusal(f"{label} workflow-runs list does not prove one run")
    fields = ("id", "workflow_id", "run_number", "name", "path", "event", "head_branch", "head_sha", "run_attempt", "status", "conclusion", "created_at", "run_started_at", "updated_at", "pull_requests")
    if any(raw.get(k) != rows[0].get(k) for k in (*fields, "head_commit", "repository", "head_repository")):
        raise BundleRefusal(f"{label} raw response does not attest selected/listed critical projection")
    def projection(value: Mapping[str, Any]) -> dict[str, Any]:
        head, repo, hrepo = value["head_commit"], value["repository"], value["head_repository"]
        return {**{key: value.get(key) for key in fields}, "head_commit": {"id": head.get("id"), "tree_id": head.get("tree_id")}, "repository": {"id": repo.get("id"), "full_name": repo.get("full_name")}, "head_repository": {"id": hrepo.get("id"), "full_name": hrepo.get("full_name")}}
    if receipt["critical_projection"] != projection(raw) or projection(rows[0]) != projection(raw):
        raise BundleRefusal(f"{label} retained critical projection mismatch")
    if (raw.get("id") != receipt["run_id"] or type(raw.get("workflow_id")) is not int or raw.get("workflow_id") <= 0 or type(raw.get("run_number")) is not int or raw.get("run_number") <= 0 or raw.get("name") != "CI" or raw.get("path") != ".github/workflows/ci.yml" or raw.get("event") != "push" or raw.get("head_branch") != "main" or raw.get("head_sha") != head_sha or raw.get("run_attempt") != 1 or raw.get("status") != "completed" or raw.get("conclusion") != "success" or raw.get("pull_requests") != []):
        raise BundleRefusal(f"{label} is not an eligible first-attempt CI run")
    head, repo, hrepo = raw.get("head_commit"), raw.get("repository"), raw.get("head_repository")
    if not isinstance(head, dict) or not isinstance(repo, dict) or not isinstance(hrepo, dict) or head.get("id") != head_sha or repo != hrepo or repo.get("full_name") != "gj3447/HSWM" or type(repo.get("id")) is not int or repo["id"] <= 0:
        raise BundleRefusal(f"{label} GitHub head/repository binding drifted")
    if not (_strict_utc_unix(raw.get("created_at"), f"{label}.created_at") <= _strict_utc_unix(raw.get("run_started_at"), f"{label}.run_started_at") <= _strict_utc_unix(raw.get("updated_at"), f"{label}.updated_at")):
        raise BundleRefusal(f"{label} timestamps not ordered")
ARMS = (
    "FULL",
    "NO_MEMORY_ROLLBACK",
    "BINDING_DERANGED_NUMERIC_PLACEBO",
)
MOUNT_ROLES = {
    "FULL": "FULL_TRAINABLE",
    "NO_MEMORY_ROLLBACK": "W0_ROLLBACK",
    "BINDING_DERANGED_NUMERIC_PLACEBO": "DERANGED_CONTROL",
}
# RAW_EQUAL_BUDGET is retained only as the fixed-rule replay gate's durable
# mount label.  It is deliberately excluded from the scientific arm set.
CLOSURE_ARMS = (*ARMS, "RAW_EQUAL_BUDGET")
CLOSURE_MOUNT_ROLES = {**MOUNT_ROLES, "RAW_EQUAL_BUDGET": "RAW_CONTROL"}
HEX64 = frozenset("0123456789abcdef")
RUNNER_EVENT_SCHEMA = "hswm-dnrd-runner-event/v2"
LIVE_EVENT_SCHEMA = "hswm-dnrd-live-model-event/v3"
QUALIFICATION_SOURCE_PATHS = (
    "_research/dnrd/live.py",
    "_research/dnrd/qualify.py",
    "_research/dnrd/runner.py",
    "_research/dnrd/task_family.py",
)
PUBLIC_MANIFEST_SCHEMA = "hswm-dnrd-public-manifest/v2"
PULSE_BINDING_SCHEMA = "hswm-dnrd4s1-pulse-binding/v1"
RUNTIME_RECEIPT_SCHEMA = "hswm-dnrd-runtime-receipt/v3"
EXECUTION_CLOSURE_ISOLATION_CLAIM = (
    "OWNER_READ_EXECUTE_ONLY_COPIED_CLOSURES_PER_INVOCATION_ENTRYPOINT_REHASHED_"
    "SAME_UID_ADVERSARIAL_IMMUTABILITY_NOT_PROVEN"
)
RUNTIME_TREE_MANIFEST_SCHEMA = "hswm-dnrd-bridge-runtime-tree-manifest/v4"
RUNTIME_CLOSURE_MAX_FILES = 8_192
RUNTIME_CLOSURE_MAX_TOTAL_BYTES = 67_108_864
VERIFIER_TIMEOUT_SECONDS = 60
VERIFIER_ARGUMENT_CONTRACT = (
    "online", "--expected-round", "{FIRST_ELIGIBLE_ROUND}"
)
VERIFIER_RUNTIME_BUNDLE_EVIDENCE_PATH = "verifier_runtime_bundle.mjs"
VERIFIER_RUNTIME_BUNDLE_MAX_BYTES = 1_048_576
OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256 = (
    "c5f6eff0d5692efd8f2e19953a49713d17554739016f9d0f3235380aab9ea904"
)
OFFICIAL_NODE_EXECUTABLE_SHA256 = (
    "53fb205ae78805130177e24bcb459a69a1518c8d98f8965f31d85aae7ea840fc"
)
OFFICIAL_NODE_VERSION = "v24.13.0"
OFFICIAL_PYTHON_EXECUTABLE_SHA256 = (
    "021044895e95be79dc2f110367607e684119afbc8ce75f6f0eec94844e0acec7"
)
OFFICIAL_PYTHON_VERSION = "3.12.13"
OFFICIAL_UNICODE_DATA_VERSION = "15.0.0"
VERIFIER_RUNTIME_BUNDLE_DEPENDENCY_POLICY = (
    "EXACT_OFFICIAL_DRAND_CLIENT_1_4_2_ESM_BYTES_NO_ORDINARY_STATIC_DYNAMIC_ESM_IMPORTS"
)
PRODUCTION_EXECUTION_ADAPTER_BOUNDARY = (
    "PRODUCTION_HASH_BOUND_ADAPTERS_NO_INJECTED_IO"
)
SCORER_ISOLATED_LAUNCH_CODE = (
    "import runpy,sys;sys.path.insert(0,'.');"
    "runpy.run_module('_research.dnrd.scorer',run_name='__main__')"
)
SCORER_ARGUMENT_CONTRACT = ("-I", "-S", "-c", SCORER_ISOLATED_LAUNCH_CODE)
PINNED_SUBPROCESS_ENVIRONMENT = {
    "PYTHONNOUSERSITE": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONUTF8": "1",
    "TZ": "UTC",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": "/usr/bin:/bin",
}
_ORDINARY_ESM_DEPENDENCY_PATTERNS = (
    re.compile(r"(?m)^[ \t]*import(?:[ \t\r\n({*\"']|$)"),
    re.compile(r"\bimport[ \t\r\n]*\("),
    re.compile(
        r"(?ms)^[ \t]*export[ \t\r\n]+(?:\*|\{).{0,4096}?\bfrom"
        r"[ \t\r\n]*[\"']"
    ),
)
RUNTIME_DEPENDENCY_MATERIALIZATION_COMMAND = (
    "npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"
)
RUNTIME_COMPILATION_COMMAND = (
    "{PINNED_NODE_EXECUTABLE}", "node_modules/typescript/lib/tsc.js", "-p",
    "tsconfig.dnrd.json",
)
RUNTIME_BUILD_CLAIM_BOUNDARY = (
    "SOURCE_SELECTED_PACKAGE_AND_COMPILER_BYTES_PINNED_BUILD_NOT_INDEPENDENTLY_REEXECUTED"
)
RUNTIME_PACKAGE_ROOTS = ("@types/node", "effect", "typescript")
RUNTIME_SOURCE_PACKAGE_JSON = "src/hswm/effect-runtime/package.json"
RUNTIME_SOURCE_PACKAGE_LOCK = "src/hswm/effect-runtime/package-lock.json"
RUNTIME_SOURCE_TSCONFIG = "src/hswm/effect-runtime/tsconfig.dnrd.json"
SCORER_ROLE_SEPARATION = "DECLARED_ROLE_SEPARATION_NOT_PROVEN"
TRACE_STATUS = "SEALED_PRE_OUTCOME_LOCAL_EXPERIMENTAL_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
PROVIDER_CACHE_UNOBSERVABLE = "NOT_OBSERVABLE_BY_CLIENT"
MAX_OUTPUT_TOKENS = 64
TOKENIZER_PREFLIGHT_PROMPT = '{"response_token":"token-ffffffffffffffffffff"}'
TRAINING_CANARY_PREFIX = "dnrd-training-provenance:"
PREREGISTRATION_SCHEMA = "hswm-durable-numeric-routing-diagnostic-preregistration/v4"
PREREG_CLAIM_BOUNDARY_SHA256 = (
    "e3b28ffd6ca4102ad522bbe84db5c2621f91650584088165071969b62f2f362d"
)
QUICKNET_CHAIN = {
    "beacon_id": "quicknet",
    "genesis_time": 1_692_803_367,
    "group_hash": "f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e",
    "hash": "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971",
    "period": 3,
    "public_key": (
        "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8"
        "c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5"
        "ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a"
    ),
    "scheme_id": "bls-unchained-g1-rfc9380",
}
# Kept independent of execute.py: the adjudicator must not import the program
# whose source closure it verifies.
FROZEN_DNRD_SOURCE_CLOSURE = frozenset(
    {
        "_research/dnrd/__init__.py",
        "_research/dnrd/prepare.py",
        "_research/dnrd/qualify.py",
        "_research/dnrd/register.py",
        "_research/dnrd/configure.py",
        "_research/dnrd/task_family.py",
        "_research/dnrd/scorer.py",
        "_research/dnrd/seed.py",
        "_research/dnrd/runner.py",
        "_research/dnrd/live.py",
        "_research/dnrd/execute.py",
        "_research/dnrd/judge.py",
        "tests/test_hswm_dnrd_execute.py",
        "tests/test_hswm_dnrd_configure.py",
        "tests/test_hswm_dnrd_judge.py",
        "tests/test_hswm_dnrd_integration.py",
        "tests/test_hswm_dnrd_live.py",
        "tests/test_hswm_dnrd_prepare.py",
        "tests/test_hswm_dnrd_qualify.py",
        "tests/test_hswm_dnrd_register.py",
        "tests/test_hswm_dnrd_runner.py",
        "tests/test_hswm_dnrd_seed.py",
        "tests/test_hswm_dnrd_task_scorer.py",
        "src/hswm/effect-runtime/src/canonical-atom-v2-routing-diagnostic.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-routing-diagnostic-file.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-routing-diagnostic-process.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-content-bound.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-content-file.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-content-runtime.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-content.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-domain.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-json.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-schema.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-state-journal-file.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-state-journal-store.ts",
        "src/hswm/effect-runtime/src/canonical-atom-v2-state-journal.ts",
        "src/hswm/effect-runtime/test/canonical-atom-v2-routing-diagnostic.test.ts",
        "src/hswm/effect-runtime/test/canonical-atom-v2-routing-diagnostic-file.test.ts",
        "src/hswm/effect-runtime/test/canonical-atom-v2-routing-diagnostic-process.test.ts",
        "src/hswm/effect-runtime/.npmrc",
        "src/hswm/effect-runtime/package.json",
        "src/hswm/effect-runtime/package-lock.json",
        "src/hswm/effect-runtime/tsconfig.json",
        "src/hswm/effect-runtime/tsconfig.build.json",
        "src/hswm/effect-runtime/tsconfig.dnrd.json",
        ".github/workflows/ci.yml",
        "pyproject.toml",
        "uv.lock",
        "MANIFEST.in",
        "tools/swm0w_drand/.npmrc",
        "tools/swm0w_drand/package.json",
        "tools/swm0w_drand/package-lock.json",
        "tools/swm0w_drand/fixtures/quicknet-round-1000.json",
        "_research/dnrd/verify-beacon.mjs",
        "docs/research/HSWM_DNRD_4_SUCCESSOR_SCIENTIFIC_BOUNDARY_2026-08-28.md",
        "docs/research/HSWM_DNRD_4S1_SUCCESSOR_SCIENTIFIC_BOUNDARY_2026-08-28.md",
    }
)

# Raw V2 mount-closure constants.  These duplicate the deliberately small
# TypeScript file-adapter wire contract so that the bundle adjudicator never
# imports or executes the runtime it is evaluating.
MOUNT_CLOSURE_SCHEMA = "hswm-dnrd-bridge-mount-closure/v1"
MOUNT_CLOSURE_LAYOUT = "hswm-dnrd-ts-file-adapter-mount-closure/v1"
MOUNT_CLOSURE_PLAN_SCHEMA = "hswm-dnrd-bridge-mount-closure-plan/v2"
PROCESS_ROOT_CONFIG_SCHEMA = "hswm-dnrd-routing-diagnostic-process-root-config/v1"
STREAM_RESERVATION_SCHEMA = "hswm-dnrd-routing-diagnostic-stream-reservation/v1"
CONTROL_RESERVATION_SCHEMA = "hswm-dnrd-routing-diagnostic-control-reservation/v1"
PROCESS_MOUNT_SCHEMA = "hswm-dnrd-routing-diagnostic-process-mount/v1"
V2_JSON_SCHEMA = "hswm-canonical-json/v1"
V2_SCHEMA_VERSION = "hswm:dnrd:v1"
V2_LINEAGE = "lineage:dnrd:local-experimental"
V2_ACTOR = "actor:dnrd:local-experimental"
V2_AUTHORIZATION = "authorization:dnrd:local-experimental"
V2_SCOPE = "scope:dnrd:local-experimental"
V2_ROUTING_OWNER = "owner:dnrd:routing"
V2_JOURNAL_CONTRACT = "hswm-canonical-atom-v2-state-journal/v1"
V2_JOURNAL_MEDIA_TYPE = "application/vnd.hswm.canonical-atom-v2-state-journal+json"
V2_SCHEMA_MEDIA_TYPE = "application/vnd.hswm.canonical-schema-v2+json"
V2_ATOM_ENVELOPE_MEDIA_TYPE = "application/vnd.hswm.canonical-atom-v2+json"
V2_DNRD_CONTENT_MEDIA_TYPE = "application/vnd.hswm.dnrd+json"
V2_PROVENANCE_MEDIA_TYPE = "application/vnd.hswm.dnrd.local-transition-provenance+json"
V2_CONTENT_MAX_BYTES = 16_777_216
V2_JSON_MAX_BYTES = 1_048_576
V2_JOURNAL_MAX_BYTES = 1_048_576
MOUNT_CLOSURE_MAX_FILE_BYTES = 1_048_576
MOUNT_CLOSURE_MAX_FILES = 4_096
MOUNT_CLOSURE_MAX_TOTAL_BYTES = 16_777_216
V2_SAFE_INTEGER = 9_007_199_254_740_991
V2_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
V2_MOUNT_ID = re.compile(
    r"^dnrd-mount-v1-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
V2_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
RESPONSE_TOKEN_RE = re.compile(r"^token-[0-9a-f]{20}$", re.ASCII)

# The candidate is only a projection.  A GO terminal is available solely from
# ``judge_bundle`` after all of these names have been re-derived from retained
# bytes.  Keeping this list here makes candidate schema drift fail closed.
CANDIDATE_BINDING_KEYS = frozenset(
    {
        "source_manifest_sha256",
        "preregistration_sha256",
        "preregistration_ci_receipt_sha256",
        "pulse_receipt_sha256",
        "split_manifest_sha256",
        "model_deployment_sha256",
        "scorer_sha256",
        "runtime_receipt_sha256",
        "event_ledger_sha256",
        "model_event_ledger_sha256",
        "bridge_state_evidence_sha256",
        "git_chronology_evidence_sha256",
        "bridge_mount_closure_sha256",
    }
)

BUNDLE_COMMON_REQUIRED_FILES = frozenset(
    {
        "runner_events.jsonl",
        "model_events.jsonl",
        "public_manifest.json",
        "deployment_receipt.json",
        "pulse_binding.json",
        "pulse_verifier_receipt.json",
        "source_manifest.json",
        "preregistration.json",
        "source_ci_receipt.json",
        "preregistration_ci_receipt.json",
        "structured_output_qualification.json",
        "runtime_receipt.json",
        "attempt_lock_receipt.json",
        "terminal-intent.json",
        "config_readback.json",
        "git_chronology_evidence.json",
        "private/private_manifest.json",
        "bridge_runtime_tree_manifest.json",
        VERIFIER_RUNTIME_BUNDLE_EVIDENCE_PATH,
        "bundle_index.json",
    }
)
BUNDLE_CANDIDATE_REQUIRED_FILES = frozenset(
    {
        *BUNDLE_COMMON_REQUIRED_FILES,
        "candidate.json",
        "bridge_state_evidence.json",
        "bridge_mount_closure.json",
    }
)


class JudgeRefusal(ValueError):
    """The artifact is malformed, non-independent, or violates the protocol."""


class DiagnosticFailure(JudgeRefusal):
    """A structurally valid candidate reached a predeclared non-GO terminal."""

    def __init__(self, terminal: str, message: str) -> None:
        super().__init__(message)
        self.terminal = terminal


def _keys(value: object, expected: set[str], where: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise JudgeRefusal(f"{where} must be an object")
    actual = set(value)
    if actual != expected:
        raise JudgeRefusal(
            f"{where} key set mismatch: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    return value


def _string(value: object, where: str) -> str:
    if type(value) is not str or not value:
        raise JudgeRefusal(f"{where} must be a nonempty string")
    return value


def _sha(value: object, where: str) -> str:
    result = _string(value, where)
    if len(result) != 64 or any(char not in HEX64 for char in result):
        raise JudgeRefusal(f"{where} must be a lowercase SHA-256 hex digest")
    return result


def _hex_of_length(value: object, where: str, length: int) -> str:
    result = _string(value, where)
    if len(result) != length or any(char not in HEX64 for char in result):
        raise BundleRefusal(f"{where} must be a lowercase {length}-hex value")
    return result


def _process_instance_id(value: object, where: str) -> str:
    """Accept the raw canonical UUID emitted by the one-operation TS process."""
    result = _string(value, where)
    try:
        parsed = UUID(result)
    except (AttributeError, ValueError) as error:
        raise BundleRefusal(f"{where} must be a canonical lowercase UUID") from error
    if str(parsed) != result:
        raise BundleRefusal(f"{where} must be a canonical lowercase UUID")
    return result


def _integer(value: object, where: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise JudgeRefusal(f"{where} must be an integer >= {minimum}")
    return value


def _boolean(value: object, where: str) -> bool:
    if type(value) is not bool:
        raise JudgeRefusal(f"{where} must be boolean")
    return value


def _forbid_candidate_terminal(value: object, where: str = "candidate") -> None:
    if type(value) is dict:
        for key, child in value.items():
            if key in {"verdict", "terminal"}:
                raise JudgeRefusal(f"{where}.{key} is forbidden in a measurement candidate")
            _forbid_candidate_terminal(child, f"{where}.{key}")
    elif type(value) is list:
        for index, child in enumerate(value):
            _forbid_candidate_terminal(child, f"{where}[{index}]")


def _state(value: object, where: str, *, owner_required: bool) -> dict[str, str | bool]:
    expected = {"state_sha256", "revision_id", "lineage_id", "immutable"}
    if owner_required:
        expected.add("owner_id")
    data = _keys(value, expected, where)
    result: dict[str, str | bool] = {
        "state_sha256": _sha(data["state_sha256"], f"{where}.state_sha256"),
        "revision_id": _string(data["revision_id"], f"{where}.revision_id"),
        "lineage_id": _string(data["lineage_id"], f"{where}.lineage_id"),
        "immutable": _boolean(data["immutable"], f"{where}.immutable"),
    }
    if result["immutable"] is not True:
        raise DiagnosticFailure("VOID_PROTOCOL", f"{where}.immutable must be true")
    if owner_required:
        result["owner_id"] = _string(data["owner_id"], f"{where}.owner_id")
    return result


def _route_only(value: object, where: str) -> tuple[str, str]:
    data = _keys(value, {"selected_route_id", "route_digest_sha256"}, where)
    return (
        _string(data["selected_route_id"], f"{where}.selected_route_id"),
        _sha(data["route_digest_sha256"], f"{where}.route_digest_sha256"),
    )


def _arm_observation(value: object, where: str) -> tuple[str, str, int]:
    data = _keys(value, {"selected_route_id", "route_digest_sha256", "route_reward_micros"}, where)
    return (
        _string(data["selected_route_id"], f"{where}.selected_route_id"),
        _sha(data["route_digest_sha256"], f"{where}.route_digest_sha256"),
        _reward(data["route_reward_micros"], f"{where}.route_reward_micros"),
    )


def _reward(value: object, where: str) -> int:
    result = _integer(value, where, minimum=-1_000_000)
    if result not in {-1_000_000, 0, 1_000_000}:
        raise JudgeRefusal(f"{where} must be one of -1000000, 0, 1000000")
    return result


def _validate_bindings(value: object) -> None:
    data = _keys(
        value,
        set(CANDIDATE_BINDING_KEYS),
        "bindings",
    )
    for key, item in data.items():
        _sha(item, f"bindings.{key}")


def _validate_chronology(value: object) -> None:
    data = _keys(
        value,
        {
            "source_commit",
            "preregistration_commit",
            "source_tree_oid",
            "preregistration_tree_oid",
            "source_frozen_at_unix",
            "preregistration_committed_at_unix",
            "preregistration_ci_completed_at_unix",
            "pulse_round",
            "pulse_chain_hash",
            "pulse_at_unix",
        },
        "chronology",
    )
    for key in (
        "source_commit",
        "preregistration_commit",
        "source_tree_oid",
        "preregistration_tree_oid",
    ):
        digest = _string(data[key], f"chronology.{key}")
        if len(digest) != 40 or any(char not in HEX64 for char in digest):
            raise JudgeRefusal(f"chronology.{key} must be a lowercase 40-hex Git OID")
    source_at = _integer(data["source_frozen_at_unix"], "chronology.source_frozen_at_unix", minimum=1)
    preregistered_at = _integer(
        data["preregistration_committed_at_unix"],
        "chronology.preregistration_committed_at_unix",
        minimum=1,
    )
    ci_completed_at = _integer(
        data["preregistration_ci_completed_at_unix"],
        "chronology.preregistration_ci_completed_at_unix",
        minimum=1,
    )
    pulse_at = _integer(data["pulse_at_unix"], "chronology.pulse_at_unix", minimum=1)
    _integer(data["pulse_round"], "chronology.pulse_round", minimum=1)
    _sha(data["pulse_chain_hash"], "chronology.pulse_chain_hash")
    if preregistered_at < source_at or preregistered_at > ci_completed_at:
        raise DiagnosticFailure(
            "VOID_PROTOCOL",
            "preregistration commit must fall after source freeze and no later than B-CI completion",
        )
    if pulse_at < max(source_at, ci_completed_at) + 900:
        raise DiagnosticFailure(
            "VOID_PROTOCOL",
            "future pulse must be at least 900 seconds after freeze and B-CI completion",
        )


def _validate_overlap(value: object) -> None:
    data = _keys(
        value,
        {
            "normalizer_sha256",
            "training_heldout_exact_overlap",
            "training_heldout_normalized_overlap",
            "prior_item_overlap",
            "leak_detected",
            "watermark_detected",
        },
        "overlap",
    )
    _sha(data["normalizer_sha256"], "overlap.normalizer_sha256")
    for key in (
        "training_heldout_exact_overlap",
        "training_heldout_normalized_overlap",
        "prior_item_overlap",
    ):
        if _integer(data[key], f"overlap.{key}") != 0:
            raise DiagnosticFailure("VOID_PROTOCOL", f"overlap.{key} must be zero")
    if _boolean(data["leak_detected"], "overlap.leak_detected"):
        raise DiagnosticFailure("VOID_PROTOCOL", "overlap.leak_detected must be false")
    if _boolean(data["watermark_detected"], "overlap.watermark_detected"):
        raise DiagnosticFailure("VOID_PROTOCOL", "overlap.watermark_detected must be false")


def _validate_parity(value: object) -> None:
    expected = {
        "same_served_model_id_and_chat_endpoint",
        "equal_client_dispatched_and_logical_requests",
        "equal_generation_limits_input_token_parity_not_claimed",
        "equal_candidate_evidence_universe",
        "all_active_payloads_within_byte_ceiling",
        "full_fixed_rule_replay_numeric_payload_bytes_equal",
        "full_deranged_numeric_payload_byte_count_equal",
        "arm_labels_hidden_from_model",
        "pre_dispatch_readout_bound_before_model_response",
        "scorer_outcome_response_independent",
        "fresh_process_recovery_observed",
        "distinct_arm_mount_ids",
        "evaluation_read_only_wrt_routing_observed",
    }
    data = _keys(value, expected, "parity")
    for key in expected:
        if _boolean(data[key], f"parity.{key}") is not True:
            raise DiagnosticFailure("VOID_PROTOCOL", f"parity.{key} must be true")


def _validate_call_ledger(value: object) -> None:
    data = _keys(
        value,
        {
            "common_training_model_calls",
            "evaluation_model_calls",
            "client_dispatched_generation_requests",
            "logical_model_calls",
            "route_only_model_calls",
            "scorer_model_calls",
            "retries",
            "client_cache_hits",
            "post_first_call_operational_failure",
        },
        "call_ledger",
    )
    operational_failure = _boolean(
        data["post_first_call_operational_failure"],
        "call_ledger.post_first_call_operational_failure",
    )
    training = _integer(data["common_training_model_calls"], "call_ledger.common_training_model_calls")
    evaluation = _integer(data["evaluation_model_calls"], "call_ledger.evaluation_model_calls")
    dispatched = _integer(
        data["client_dispatched_generation_requests"],
        "call_ledger.client_dispatched_generation_requests",
    )
    logical = _integer(data["logical_model_calls"], "call_ledger.logical_model_calls")
    # This counts only the runner's own cache.  Provider prefix-cache behavior
    # is neither observable here nor a claim of this diagnostic.
    for key in ("route_only_model_calls", "scorer_model_calls", "retries", "client_cache_hits"):
        if _integer(data[key], f"call_ledger.{key}") != 0:
            raise DiagnosticFailure("VOID_PROTOCOL", f"call_ledger.{key} must equal 0")
    if operational_failure:
        raise DiagnosticFailure(
            "VOID_PROTOCOL",
            "completed candidate cannot report an operational failure; use the separate inconclusive occurrence",
        )
    expected = (32, 96, 128, 128)
    if (training, evaluation, dispatched, logical) != expected:
        raise DiagnosticFailure(
            "VOID_PROTOCOL",
            "completed call ledger must retain 32 training + 96 evaluation = "
            "128 client-dispatched generation requests",
        )


def _validate_stream(value: object, index: int) -> tuple[dict[str, object], bool]:
    where = f"streams[{index}]"
    data = _keys(
        value,
        {
            "stream_id",
            "w0",
            "w1",
            "clean_process_recovery",
            "fixed_rule_replay",
            "local_v2_linkage",
            "derangement",
            "w0_replay_mismatch_probe_ids",
            "probes",
        },
        where,
    )
    stream_id = _string(data["stream_id"], f"{where}.stream_id")
    w0 = _state(data["w0"], f"{where}.w0", owner_required=False)
    w1 = _state(data["w1"], f"{where}.w1", owner_required=True)
    if w0["state_sha256"] == w1["state_sha256"]:
        raise DiagnosticFailure(
            "VOID_PROTOCOL",
            f"{where} W0 and FULL must be distinct immutable mount observations",
        )
    if w0["lineage_id"] != w1["lineage_id"]:
        raise DiagnosticFailure("VOID_PROTOCOL", f"{where} W0/FULL lineage mismatch")

    recovery = _keys(
        data["clean_process_recovery"],
        {"recovered", "journal_sha256", "recovered_state_sha256", "fresh_process", "process_instance_id"},
        f"{where}.clean_process_recovery",
    )
    if _boolean(recovery["recovered"], f"{where}.clean_process_recovery.recovered") is not True:
        raise DiagnosticFailure("DIAGNOSTIC_NO_GO", f"{where} did not recover a durable journal")
    if _boolean(recovery["fresh_process"], f"{where}.clean_process_recovery.fresh_process") is not True:
        raise DiagnosticFailure("DIAGNOSTIC_NO_GO", f"{where} used in-memory continuation rather than clean restart")
    _sha(recovery["journal_sha256"], f"{where}.clean_process_recovery.journal_sha256")
    _process_instance_id(recovery["process_instance_id"], f"{where}.clean_process_recovery.process_instance_id")
    if _sha(recovery["recovered_state_sha256"], f"{where}.clean_process_recovery.recovered_state_sha256") != w1["state_sha256"]:
        raise DiagnosticFailure(
            "DIAGNOSTIC_NO_GO",
            f"{where} clean process did not recover the retained FULL mount",
        )

    local = _keys(
        data["local_v2_linkage"],
        {
            "experimental_schema_id",
            "owner_id",
            "outcome_ledger_sha256",
            "credit_ledger_sha256",
            "local_structural_receipt_sha256",
            "transition_evidence_sha256",
            "local_only",
            "schema_owner_matches",
            "outcome_present",
            "reference_grant_matched_not_canonical_permit",
        },
        f"{where}.local_v2_linkage",
    )
    if _string(local["experimental_schema_id"], f"{where}.local_v2_linkage.experimental_schema_id") != "hswm:dnrd:v1":
        raise DiagnosticFailure("VOID_PROTOCOL", f"{where} must use the experimental local V2 schema")
    if _string(local["owner_id"], f"{where}.local_v2_linkage.owner_id") != w1["owner_id"]:
        raise DiagnosticFailure("VOID_PROTOCOL", f"{where} owner does not match retained FULL mount owner")
    for key in (
        "outcome_ledger_sha256",
        "credit_ledger_sha256",
        "local_structural_receipt_sha256",
        "transition_evidence_sha256",
    ):
        _sha(local[key], f"{where}.local_v2_linkage.{key}")
    for key in (
        "local_only",
        "schema_owner_matches",
        "outcome_present",
        "reference_grant_matched_not_canonical_permit",
    ):
        if _boolean(local[key], f"{where}.local_v2_linkage.{key}") is not True:
            raise DiagnosticFailure("VOID_PROTOCOL", f"{where}.local_v2_linkage.{key} must be true")

    derangement = _keys(
        data["derangement"],
        {
            "algorithm",
            "seed_sha256",
            "fixed_point_count",
            "preserves_update_multiset",
            "preserves_precision",
            "preserves_l1_l2_norms",
            "preserves_routing_payload_byte_count",
            "routing_payload_content_differs",
        },
        f"{where}.derangement",
    )
    if _string(derangement["algorithm"], f"{where}.derangement.algorithm") != "within-stratum-no-fixed-point/v1":
        raise DiagnosticFailure("VOID_PROTOCOL", f"{where} derangement algorithm mismatch")
    _sha(derangement["seed_sha256"], f"{where}.derangement.seed_sha256")
    if _integer(derangement["fixed_point_count"], f"{where}.derangement.fixed_point_count") != 0:
        raise DiagnosticFailure("VOID_PROTOCOL", f"{where} derangement has a fixed point")
    for key in (
        "preserves_update_multiset",
        "preserves_precision",
        "preserves_l1_l2_norms",
        "preserves_routing_payload_byte_count",
        "routing_payload_content_differs",
    ):
        if _boolean(derangement[key], f"{where}.derangement.{key}") is not True:
            raise DiagnosticFailure("VOID_PROTOCOL", f"{where}.derangement.{key} must be true")

    diffs = data["w0_replay_mismatch_probe_ids"]
    if type(diffs) is not list or diffs:
        raise DiagnosticFailure("DIAGNOSTIC_NO_GO", f"{where}.w0_replay_mismatch_probe_ids must be an empty list")
    probes = data["probes"]
    if type(probes) is not list or len(probes) != 8:
        raise JudgeRefusal(f"{where}.probes must contain exactly eight probes")
    seen_probe_ids: set[str] = set()
    positive_counts = {arm: 0 for arm in ARMS}
    full_w0_differences = 0
    full_deranged_differences = 0
    for probe_index, probe in enumerate(probes):
        probe_where = f"{where}.probes[{probe_index}]"
        entry = _keys(
            probe,
            {"probe_id", "arms", "rollback", "restore"},
            probe_where,
        )
        probe_id = _string(entry["probe_id"], f"{probe_where}.probe_id")
        if probe_id in seen_probe_ids:
            raise JudgeRefusal(f"{where} repeats probe_id {probe_id!r}")
        seen_probe_ids.add(probe_id)
        arms = _keys(entry["arms"], set(ARMS), f"{probe_where}.arms")
        observations = {
            arm: _arm_observation(arms[arm], f"{probe_where}.arms.{arm}") for arm in ARMS
        }
        w0_route, w0_digest, _ = observations["NO_MEMORY_ROLLBACK"]
        full_route, full_digest, _ = observations["FULL"]
        deranged_route, deranged_digest, _ = observations["BINDING_DERANGED_NUMERIC_PLACEBO"]
        full_w0_differences += int(full_route != w0_route)
        full_deranged_differences += int(full_route != deranged_route)
        rollback = _route_only(entry["rollback"], f"{probe_where}.rollback")
        restore = _route_only(entry["restore"], f"{probe_where}.restore")
        if rollback != (w0_route, w0_digest):
            raise DiagnosticFailure(
                "DIAGNOSTIC_NO_GO",
                f"{probe_where} W0-mount route observation does not match the retained W0 baseline",
            )
        if restore != (full_route, full_digest):
            raise DiagnosticFailure(
                "DIAGNOSTIC_NO_GO",
                f"{probe_where} FULL-mount route observation does not match the retained FULL baseline",
            )
        for arm, (_, _, reward) in observations.items():
            positive_counts[arm] += int(reward > 0)
    summary = {
        "stream_id": stream_id,
        "positive_route_reward_counts": positive_counts,
        "full_vs_w0_selected_route_differences": full_w0_differences,
        "full_vs_deranged_selected_route_differences": full_deranged_differences,
    }
    passes = (
        positive_counts["FULL"] == 8
        and positive_counts["NO_MEMORY_ROLLBACK"] == 4
        and positive_counts["BINDING_DERANGED_NUMERIC_PLACEBO"] <= 4
        and full_w0_differences == 4
        and full_deranged_differences >= 4
    )
    return summary, passes


def _judgment(
    candidate: Mapping[str, Any],
    *,
    terminal: str,
    stream_route_checks: list[dict[str, object]] | None = None,
    utility_report: list[dict[str, object]] | None = None,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    canonical = json.dumps(candidate, sort_keys=True, separators=(",", ":"), allow_nan=False)
    result: dict[str, Any] = {
        "schema_version": JUDGMENT_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "candidate_sha256": sha256(canonical.encode("utf-8")).hexdigest(),
        "authority": "STRUCTURAL_CANDIDATE_ONLY_NOT_EVIDENCE_BUNDLE_VERIFIED",
        "terminal": terminal,
        "scientific_status": "UNJUDGED",
        "efficacy_claim": "NOT_EVALUATED",
        "canonical_permit": "NOT_ESTABLISHED",
        "learning_claim": "NOT_ESTABLISHED",
        "claim_boundary": (
            "Finite engineering-conformance diagnostic only, not scientific effect evidence; "
            "response-independent route-reward counts are reported without an efficacy, Permit, "
            "or learning claim. Model responses are format/liveness observations and need not "
            "match selected-route evidence. Scorer role separation is declared only as "
            "DECLARED_ROLE_SEPARATION_NOT_PROVEN; no stronger scorer-role property is established. "
            "Model-serving identity/determinism is not proven."
        ),
        "stream_route_checks": stream_route_checks or [],
    }
    if failure_reason is not None:
        result["failure_reason"] = failure_reason
    return result


def judge(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Non-authoritative structural helper for an already-loaded candidate.

    This is useful for checking the predeclared terminal logic in isolation,
    but it intentionally cannot establish that the candidate describes a real
    occurrence.  Call :func:`judge_bundle` for the authoritative path.
    """

    _forbid_candidate_terminal(candidate)
    data = _keys(
        candidate,
        {
            "schema_version",
            "experiment_id",
            "bindings",
            "chronology",
            "overlap",
            "parity",
            "call_ledger",
            "streams",
        },
        "candidate",
    )
    if _string(data["schema_version"], "candidate.schema_version") != CANDIDATE_SCHEMA:
        raise JudgeRefusal(f"candidate.schema_version must be {CANDIDATE_SCHEMA!r}")
    if _string(data["experiment_id"], "candidate.experiment_id") != EXPERIMENT_ID:
        raise JudgeRefusal(f"candidate.experiment_id must be {EXPERIMENT_ID!r}")
    try:
        _validate_bindings(data["bindings"])
        _validate_chronology(data["chronology"])
        _validate_overlap(data["overlap"])
        _validate_parity(data["parity"])
        _validate_call_ledger(data["call_ledger"])
        streams = data["streams"]
        if type(streams) is not list or len(streams) != 4:
            raise JudgeRefusal("candidate.streams must contain exactly four streams")
        summaries: list[dict[str, object]] = []
        actuation_passes: list[bool] = []
        stream_ids: set[str] = set()
        for index, stream in enumerate(streams):
            summary, actuation_passed = _validate_stream(stream, index)
            stream_id = str(summary["stream_id"])
            if stream_id in stream_ids:
                raise JudgeRefusal(f"candidate repeats stream_id {stream_id!r}")
            stream_ids.add(stream_id)
            summaries.append(summary)
            actuation_passes.append(actuation_passed)
    except DiagnosticFailure as failure:
        return _judgment(candidate, terminal=failure.terminal, failure_reason=str(failure))

    if all(actuation_passes):
        terminal = "DIAGNOSTIC_INTEGRITY_GO_NO_UTILITY_CLAIM"
    else:
        terminal = "DIAGNOSTIC_NO_GO"
    return _judgment(
        candidate,
        terminal=terminal,
        stream_route_checks=[
            {
                "stream_id": item["stream_id"],
                "positive_route_reward_counts": item["positive_route_reward_counts"],
                "full_vs_w0_selected_route_differences": item["full_vs_w0_selected_route_differences"],
                "full_vs_deranged_selected_route_differences": item["full_vs_deranged_selected_route_differences"],
            }
            for item in summaries
        ],
    )


def _load_json(path: Path) -> Mapping[str, Any]:
    def reject_constant(value: str) -> None:
        raise JudgeRefusal(f"non-finite JSON constant {value!r} is forbidden")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if type(value) is not dict:
        raise JudgeRefusal("candidate JSON root must be an object")
    return value


# ---------------------------------------------------------------------------
# Authoritative evidence-bundle verification
# ---------------------------------------------------------------------------
#
# The functions below intentionally duplicate the small frozen DNRD wire
# contracts instead of importing ``runner``, ``task_family``, ``live``, or the
# TypeScript bridge.  The adjudicator must remain a separately runnable,
# stdlib-only consumer of evidence rather than a second caller of the system it
# is assessing.


class BundleRefusal(JudgeRefusal):
    """The retained evidence bundle cannot support an authoritative result."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise BundleRefusal("value cannot be represented as finite canonical JSON") from error


def _sha_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _bundle_plain_file(root: Path, relative: str, *, allow_empty: bool = False) -> Path:
    if (
        type(relative) is not str
        or not relative
        or relative.startswith("/")
        or any(part in {"", ".", ".."} for part in Path(relative).parts)
    ):
        raise BundleRefusal(f"bundle artifact path is not a safe relative path: {relative!r}")
    path = root / relative
    try:
        info = path.lstat()
    except FileNotFoundError as error:
        raise BundleRefusal(f"bundle is missing required artifact {relative!r}") from error
    if not path.is_relative_to(root) or path.is_symlink() or not path.is_file():
        raise BundleRefusal(f"bundle artifact {relative!r} must be a plain regular file")
    if info.st_size < 1 and not allow_empty:
        raise BundleRefusal(f"bundle artifact {relative!r} is empty")
    return path


def _parse_json_bytes(data: bytes, label: str, *, canonical: bool) -> Any:
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise BundleRefusal(f"{label} is not UTF-8") from error

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise BundleRefusal(f"{label} repeats JSON key {key!r}")
            result[key] = item
        return result

    def no_nonfinite(value: str) -> None:
        raise BundleRefusal(f"{label} contains non-finite JSON token {value!r}")

    try:
        value = json.loads(text, object_pairs_hook=no_duplicates, parse_constant=no_nonfinite)
    except (json.JSONDecodeError, BundleRefusal) as error:
        if isinstance(error, BundleRefusal):
            raise
        raise BundleRefusal(f"{label} is not JSON") from error
    if canonical and _canonical_bytes(value) != data:
        raise BundleRefusal(f"{label} must be exact canonical JSON bytes")
    return value


def _bundle_object(root: Path, relative: str, *, canonical: bool = True) -> tuple[dict[str, Any], bytes]:
    raw = _bundle_plain_file(root, relative).read_bytes()
    value = _parse_json_bytes(raw, relative, canonical=canonical)
    if type(value) is not dict:
        raise BundleRefusal(f"{relative} root must be an object")
    return value, raw


def _bundle_jsonl(root: Path, relative: str, *, allow_empty: bool = False) -> tuple[list[dict[str, Any]], bytes]:
    raw = _bundle_plain_file(root, relative, allow_empty=allow_empty).read_bytes()
    if allow_empty and raw == b"":
        return [], raw
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise BundleRefusal(f"{relative} must be canonical JSONL with exactly one terminal LF")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(raw[:-1].split(b"\n")):
        if not line:
            raise BundleRefusal(f"{relative} contains an empty JSONL record")
        item = _parse_json_bytes(line, f"{relative}[{index}]", canonical=True)
        if type(item) is not dict:
            raise BundleRefusal(f"{relative}[{index}] must be an object")
        rows.append(item)
    if not rows:
        raise BundleRefusal(f"{relative} contains no events")
    return rows, raw


def _structured_output_qualification(
    raw: bytes,
    *,
    config: Mapping[str, Any],
    public: Mapping[str, Any],
    private: Mapping[str, Any],
    source: Mapping[str, Any],
    preregistration: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Verify the non-scientific structured-output qualification byte-for-byte."""
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise BundleRefusal("structured-output qualification must be one canonical JSON object followed by exactly one LF")
    value = _parse_json_bytes(raw[:-1], "structured-output qualification", canonical=True)
    required = {
        "schema_version", "domain", "event_schema", "experiment_occurrence",
        "future_seed_material_used", "record_role", "raw_full_stdout_record_persisted",
        "retry_count", "max_output_tokens", "model_endpoint", "served_model_id",
        "vllm_version", "provider_cache_independence", "calls", "started_at_unix_ns",
        "ended_at_unix_ns", "source_files", "python_executable_sha256",
        "python_version", "unicode_data_version",
    }
    data = _check_exact_keys(value, required, "structured-output qualification")
    if (
        data["schema_version"] != STRUCTURED_OUTPUT_QUALIFICATION_SCHEMA
        or data["domain"] != STRUCTURED_OUTPUT_QUALIFICATION_DOMAIN
        or data["event_schema"] != LIVE_EVENT_SCHEMA
        or data["experiment_occurrence"] is not False
        or data["future_seed_material_used"] is not False
        or data["record_role"] != (
            "CONTENT_ADDRESSED_OPERATOR_SUMMARY_OF_DISJOINT_NONSCIENTIFIC_LIVE_"
            "QUALIFICATION_NOT_SCIENTIFIC_EVIDENCE"
        )
        or data["raw_full_stdout_record_persisted"] is not False
        or type(data["retry_count"]) is not int
        or data["retry_count"] != 0
        or type(data["max_output_tokens"]) is not int
        or data["max_output_tokens"] != MAX_OUTPUT_TOKENS
        or data["model_endpoint"] != config["model_endpoint"]
        or data["served_model_id"] != "qwen3.6-35b-a3b"
        or data["vllm_version"] != "0.25.1"
        or data["provider_cache_independence"] != PROVIDER_CACHE_UNOBSERVABLE
        or type(data["calls"]) is not list or len(data["calls"]) != 3
    ):
        raise BundleRefusal("structured-output qualification violates its non-scientific frozen contract")
    if (
        type(data["started_at_unix_ns"]) is not int
        or type(data["ended_at_unix_ns"]) is not int
        or data["started_at_unix_ns"] <= 0
        or data["ended_at_unix_ns"] <= data["started_at_unix_ns"]
    ):
        raise BundleRefusal("structured-output qualification time interval is invalid")
    source_rows = source.get("files")
    if type(source_rows) is not list:
        raise BundleRefusal("source manifest files are unavailable to qualification validation")
    source_hashes = {
        row.get("path"): row.get("sha256")
        for row in source_rows
        if type(row) is dict
    }
    source_files = data["source_files"]
    if type(source_files) is not list or len(source_files) != len(QUALIFICATION_SOURCE_PATHS):
        raise BundleRefusal("structured-output qualification source-file closure drifted")
    for index, expected_path in enumerate(QUALIFICATION_SOURCE_PATHS):
        source_file = _check_exact_keys(
            source_files[index],
            {"path", "sha256"},
            f"structured-output qualification.source_files[{index}]",
        )
        if source_file["path"] != expected_path:
            raise BundleRefusal("structured-output qualification source-file order drifted")
        _sha(
            source_file["sha256"],
            f"structured-output qualification.source_files[{index}].sha256",
        )
        if source_file["sha256"] != source_hashes.get(expected_path):
            raise BundleRefusal(
                "structured-output qualification source identities do not match Source A"
            )
    _sha(
        data["python_executable_sha256"],
        "structured-output qualification.python_executable_sha256",
    )
    runtime = preregistration.get("runtime_bindings")
    if type(runtime) is not dict:
        raise BundleRefusal(
            "preregistration runtime bindings are unavailable to qualification validation"
        )
    if (
        data["python_executable_sha256"] != config.get("python_executable_sha256")
        or data["python_executable_sha256"]
        != runtime.get("python_executable_sha256")
        or data["python_executable_sha256"] != OFFICIAL_PYTHON_EXECUTABLE_SHA256
        or data["python_version"] != config.get("python_version")
        or data["python_version"] != runtime.get("python_version")
        or data["python_version"] != OFFICIAL_PYTHON_VERSION
        or data["unicode_data_version"] != config.get("unicode_data_version")
        or data["unicode_data_version"] != runtime.get("unicode_data_version")
        or data["unicode_data_version"] != OFFICIAL_UNICODE_DATA_VERSION
    ):
        raise BundleRefusal(
            "structured-output qualification Python/Unicode runtime identities do not match frozen runtime"
        )
    tokens: set[str] = set()
    requested_candidate_indices: set[int] = set()
    call_keys = {"candidate_response_tokens", "completion_tokens", "dnrd_request_sha256", "dnrd_response_sha256", "finish_reason", "http_request_sha256", "http_status", "ordinal", "prompt_tokens", "raw_response_sha256", "requested_token", "response_format_schema_sha256", "returned_token"}
    for ordinal, raw_call in enumerate(data["calls"], start=1):
        call = _check_exact_keys(raw_call, call_keys, f"structured-output qualification.calls[{ordinal - 1}]")
        candidates = _candidate_response_tokens(call["candidate_response_tokens"], f"structured-output qualification.calls[{ordinal - 1}].candidate_response_tokens")
        if (
            type(call["ordinal"]) is not int or call["ordinal"] != ordinal
            or type(call["http_status"]) is not int or call["http_status"] != 200
            or call["finish_reason"] != "stop"
            or call["requested_token"] not in candidates
            or call["returned_token"] != call["requested_token"]
            or type(call["prompt_tokens"]) is not int or call["prompt_tokens"] < 0
            or type(call["completion_tokens"]) is not int
            or not 0 < call["completion_tokens"] <= MAX_OUTPUT_TOKENS
        ):
            raise BundleRefusal("structured-output qualification call does not retain the fixed successful contract")
        for field in ("dnrd_request_sha256", "dnrd_response_sha256", "http_request_sha256", "raw_response_sha256", "response_format_schema_sha256"):
            _sha(call[field], f"structured-output qualification.calls[{ordinal - 1}].{field}")
        expected_schema = {
            "type": "object",
            "properties": {
                "response_token": {
                    "type": "string",
                    "enum": list(candidates),
                    "pattern": r"^token-[0-9a-f]{20}$",
                    "minLength": 26,
                    "maxLength": 26,
                }
            },
            "required": ["response_token"],
            "additionalProperties": False,
        }
        if call["response_format_schema_sha256"] != _canonical_hash(expected_schema):
            raise BundleRefusal("structured-output qualification response schema digest drifted")
        requested_candidate_indices.add(candidates.index(call["requested_token"]))
        tokens.update(candidates)
    if len(tokens) != 6:
        raise BundleRefusal("structured-output qualification must retain exactly six distinct candidate tokens")
    if requested_candidate_indices != {0, 1}:
        raise BundleRefusal("structured-output qualification must exercise both candidate enum positions")
    fixture_bytes = _canonical_bytes({"public": public, "private": private})
    if any(token.encode("ascii") in fixture_bytes for token in tokens):
        raise BundleRefusal("future-seeded public/private fixture overlaps structured-output qualification candidate tokens")
    return data


def _bundle_sha_receipt(value: Mapping[str, Any], label: str) -> str:
    if "receipt_sha256" not in value:
        raise BundleRefusal(f"{label} has no receipt_sha256")
    digest = _sha(value["receipt_sha256"], f"{label}.receipt_sha256")
    unsigned = dict(value)
    del unsigned["receipt_sha256"]
    if digest != _sha_bytes(_canonical_bytes(unsigned)):
        raise BundleRefusal(f"{label} receipt self-hash mismatch")
    return digest


def _check_exact_keys(value: object, keys: Iterable[str], label: str) -> Mapping[str, Any]:
    return _keys(value, set(keys), label)


def _strict_identifier(value: object, label: str) -> str:
    result = _string(value, label)
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:/-")
    if result[0] not in set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") or any(
        character not in allowed for character in result
    ):
        raise BundleRefusal(f"{label} is not a frozen DNRD identifier")
    return result


def _canonical_hash(value: object) -> str:
    return _sha_bytes(_canonical_bytes(value))


def _frozen_date(value: object, label: str) -> str:
    """Accept one calendar-valid ISO date with no free-form metadata suffix."""
    result = _string(value, label)
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", result) is None:
        raise BundleRefusal(f"{label} must be an exact ISO-8601 date (YYYY-MM-DD)")
    try:
        datetime.strptime(result, "%Y-%m-%d")
    except ValueError as error:
        raise BundleRefusal(f"{label} must be a valid calendar date") from error
    return result


def _strict_utc_unix(value: object, label: str) -> int:
    """Parse the sole accepted GitHub UTC timestamp form without local-time drift."""
    result = _string(value, label)
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", result) is None:
        raise BundleRefusal(f"{label} must be exact UTC RFC3339 seconds")
    try:
        return int(datetime.strptime(result, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())
    except ValueError as error:
        raise BundleRefusal(f"{label} must be a valid UTC RFC3339 timestamp") from error


def _validate_preregistration_claim_boundary(prereg: Mapping[str, Any]) -> None:
    """Reject any preregistration that broadens the mechanics-only claim."""
    _frozen_date(prereg.get("created_at"), "preregistration.created_at")
    testbed = _check_exact_keys(
        prereg.get("testbed"),
        {
            "family", "relationship_to_prior_p1", "development_streams",
            "training_calls_per_stream_maximum", "paired_heldout_probes_per_stream",
            "evaluation_arms", "evaluation_calls",
            "shared_learning_or_compiler_calls_maximum",
            "client_dispatched_generation_request_ceiling", "analysis_unit", "model",
            "freshness",
        },
        "preregistration.testbed",
    )
    model = _check_exact_keys(
        testbed["model"],
        {
            "served_model_id", "substitution_allowed", "temperature", "thinking",
            "max_output_tokens", "deployment_readback_required",
            "exact_weight_revision_attested", "exact_weight_identity_claimed",
        },
        "preregistration.testbed.model",
    )
    if (
        testbed["family"] != "REPEATED_CONTEXT_TABULAR_ROUTING_MECHANICS_V2"
        or testbed["development_streams"] != 4
        or testbed["training_calls_per_stream_maximum"] != 8
        or testbed["paired_heldout_probes_per_stream"] != 8
        or testbed["evaluation_arms"] != 3
        or testbed["evaluation_calls"] != 96
        or testbed["shared_learning_or_compiler_calls_maximum"] != 32
        or testbed["client_dispatched_generation_request_ceiling"] != 128
        or model["served_model_id"] != "qwen3.6-35b-a3b"
        or model["substitution_allowed"] is not False
        or model["temperature"] != 0
        or model["thinking"] is not False
        or model["max_output_tokens"] != MAX_OUTPUT_TOKENS
        or model["deployment_readback_required"] is not True
        or model["exact_weight_revision_attested"] is not False
        or model["exact_weight_identity_claimed"] is not False
    ):
        raise BundleRefusal(
            "preregistration testbed/model differs from the frozen repeated-context diagnostic"
        )
    arms = _check_exact_keys(
        prereg.get("arms"),
        set(ARMS),
        "preregistration.arms",
    )
    parity = _check_exact_keys(
        prereg.get("parity_and_leakage"),
        {
            "same_served_model_id_and_chat_endpoint",
            "equal_client_dispatched_and_logical_requests",
            "equal_generation_limits_input_token_parity_not_claimed",
            "equal_candidate_evidence_universe", "all_active_payloads_within_byte_ceiling",
            "active_state_byte_ceiling", "full_fixed_rule_replay_numeric_payload_bytes_equal",
            "full_deranged_numeric_payload_byte_count_equal", "arm_labels_hidden_from_model",
            "fresh_process_recovery_observed", "distinct_arm_mount_ids",
            "evaluation_read_only_wrt_routing_observed", "cache_hits_required",
            "private_route_binding_open_only_after_response_seal", "pre_dispatch_readout_bound_before_model_response",
            "scorer_outcome_response_independent", "compiler_input_audit", "canary",
        },
        "preregistration.parity_and_leakage",
    )
    required_true = {
        "same_served_model_id_and_chat_endpoint",
        "equal_client_dispatched_and_logical_requests",
        "equal_generation_limits_input_token_parity_not_claimed",
        "equal_candidate_evidence_universe",
        "all_active_payloads_within_byte_ceiling",
        "full_fixed_rule_replay_numeric_payload_bytes_equal",
        "full_deranged_numeric_payload_byte_count_equal",
        "arm_labels_hidden_from_model",
        "fresh_process_recovery_observed",
        "distinct_arm_mount_ids",
        "evaluation_read_only_wrt_routing_observed",
        "private_route_binding_open_only_after_response_seal",
        "pre_dispatch_readout_bound_before_model_response",
        "scorer_outcome_response_independent",
    }
    if (
        any(parity[key] is not True for key in required_true)
        or parity["active_state_byte_ceiling"] != 16_384
        or parity["cache_hits_required"] != 0
    ):
        raise BundleRefusal("preregistration parity boundary is not the frozen diagnostic contract")
    claim_boundary = {
        "canonical_role": prereg["canonical_role"],
        "predecessor_bindings": prereg["predecessor_bindings"],
        "forbidden_rescues": prereg["forbidden_rescues"],
        "scientific_question": prereg["scientific_question"],
        "hypotheses": prereg["hypotheses"],
        "testbed_claims": {
            key: testbed[key]
            for key in ("relationship_to_prior_p1", "analysis_unit", "freshness")
        },
        "learning_boundary": prereg["learning_boundary"],
        "arms": dict(arms),
        "interventions": prereg["interventions"],
        "parity_claims": {
            key: parity[key] for key in ("compiler_input_audit", "canary")
        },
        "diagnostic_readouts": prereg["diagnostic_readouts"],
        "void_conditions": prereg["void_conditions"],
        "single_attempt_policy": prereg["single_attempt_policy"],
        "required_before_measurement": prereg["required_before_measurement"],
        "result_promotion": prereg["result_promotion"],
        "measurement_gate": prereg["measurement_gate"],
    }
    if _canonical_hash(claim_boundary) != PREREG_CLAIM_BOUNDARY_SHA256:
        raise BundleRefusal(
            "preregistration claim boundary differs from the frozen engineering-conformance contract"
        )


def _validate_source_and_preregistration(
    *,
    source: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    source_ci: Mapping[str, Any],
    preregistration_ci: Mapping[str, Any],
    candidate: Mapping[str, Any],
    source_bytes: bytes,
    preregistration_bytes: bytes,
    preregistration_ci_bytes: bytes,
) -> None:
    bindings = candidate["bindings"]
    if bindings["source_manifest_sha256"] != _sha_bytes(source_bytes):
        raise BundleRefusal("candidate source manifest binding does not match retained bytes")
    if bindings["preregistration_sha256"] != _sha_bytes(preregistration_bytes):
        raise BundleRefusal("candidate preregistration binding does not match retained bytes")

    source_data = _check_exact_keys(
        source,
        {"schema_version", "experiment_id", "source_commit_tree_bound_externally", "files"},
        "source manifest",
    )
    if (
        source_data["schema_version"] != "hswm-dnrd-source-freeze-manifest/v1"
        or source_data["experiment_id"] != EXPERIMENT_ID
        or source_data["source_commit_tree_bound_externally"]
        != "SOURCE_COMMIT_TREE_BOUND_EXTERNALLY_NO_SELF_CYCLE"
    ):
        raise BundleRefusal("source manifest identity is not the frozen DNRD source manifest")
    files = source_data["files"]
    if type(files) is not list or not files:
        raise BundleRefusal("source manifest must retain a nonempty source closure")
    previous = ""
    source_hashes: dict[str, str] = {}
    for index, row in enumerate(files):
        item = _check_exact_keys(row, {"path", "sha256"}, f"source manifest.files[{index}]")
        path = _string(item["path"], f"source manifest.files[{index}].path")
        if path <= previous or path.startswith("/") or ".." in Path(path).parts:
            raise BundleRefusal("source manifest paths must be unique sorted relative paths")
        previous = path
        _sha(item["sha256"], f"source manifest.files[{index}].sha256")
        source_hashes[path] = str(item["sha256"])
    if set(source_hashes) != FROZEN_DNRD_SOURCE_CLOSURE:
        raise BundleRefusal("source manifest is not the exact frozen DNRD source closure")
    if source_hashes["_research/dnrd/scorer.py"] != bindings["scorer_sha256"]:
        raise BundleRefusal("candidate scorer identity does not match frozen scorer source closure")

    prereg = _check_exact_keys(
        preregistration,
        {
            "schema_version", "experiment_id", "protocol_version", "created_at", "status",
            "authority", "canonical_role", "predecessor_bindings", "forbidden_rescues",
            "scientific_question", "hypotheses", "testbed", "learning_boundary", "arms",
            "interventions", "parity_and_leakage", "diagnostic_readouts", "void_conditions",
            "single_attempt_policy", "required_before_measurement", "result_promotion",
            "measurement_gate", "preregistration_b_ci_gate", "source_a_ci", "runtime_bindings",
        },
        "preregistration",
    )
    if (
        prereg["schema_version"] != PREREGISTRATION_SCHEMA
        or prereg["experiment_id"] != EXPERIMENT_ID
        or prereg["protocol_version"] != PROTOCOL_VERSION
        or prereg["status"]
        != "FROZEN_AWAITING_SUCCESSFUL_PREREGISTRATION_B_CI_AND_FUTURE_PULSE"
    ):
        raise BundleRefusal("preregistration is not the frozen DNRD-4S1 B-CI chronology contract")
    authority = _check_exact_keys(
        prereg["authority"],
        {
            "broad_research_continuation_requested",
            "measurement_authorized_by_user_broad_continuation",
            "authorization_is_scientific_evidence",
            "measurement_requires_external_exact_hash_ratification_receipt",
            "measurement_requires_successful_preregistration_b_ci_receipt",
            "scientific_judgment_emitted",
            "external_governance_required",
        },
        "preregistration.authority",
    )
    if (
        authority["broad_research_continuation_requested"] is not True
        or authority["measurement_authorized_by_user_broad_continuation"] is not True
        or authority["authorization_is_scientific_evidence"] is not False
        or authority["measurement_requires_external_exact_hash_ratification_receipt"] is not False
        or authority["measurement_requires_successful_preregistration_b_ci_receipt"] is not True
        or authority["scientific_judgment_emitted"] is not False
        or authority["external_governance_required"] is not False
    ):
        raise BundleRefusal("preregistration authority does not preserve B-CI chronology gating")
    _validate_preregistration_claim_boundary(prereg)
    preregistration_b_ci_gate = _check_exact_keys(
        prereg["preregistration_b_ci_gate"],
        {"receipt_schema", "provider", "status", "conclusion", "minimum_lead_seconds", "selection_rule"},
        "preregistration.preregistration_b_ci_gate",
    )
    if (
        preregistration_b_ci_gate["receipt_schema"]
        != "hswm-dnrd-preregistration-b-ci-receipt/v2"
        or preregistration_b_ci_gate["provider"] != "GITHUB_ACTIONS"
        or preregistration_b_ci_gate["status"] != "completed"
        or preregistration_b_ci_gate["conclusion"] != "success"
        or type(preregistration_b_ci_gate["minimum_lead_seconds"]) is not int
        or preregistration_b_ci_gate["minimum_lead_seconds"] != 900
        or preregistration_b_ci_gate["selection_rule"] != "EXACT_UNFILTERED_PUSH_MAIN_HEAD_SHA_WORKFLOW_LIST_TOTAL_COUNT_ONE_FIRST_ATTEMPT"
    ):
        raise BundleRefusal("preregistration does not freeze the B-CI receipt chronology gate")

    ci = _check_exact_keys(
        source_ci,
        {
            "schema_version", "provider", "run_id", "head_sha", "conclusion",
            "raw_response_sha256", "raw_response_utf8", "discovery_query", "critical_projection", "raw_list_response_sha256", "raw_list_response_utf8", "receipt_sha256",
        },
        "source CI receipt",
    )
    if ci["schema_version"] != "hswm-dnrd-source-ci-receipt/v2":
        raise BundleRefusal("source CI receipt schema mismatch")
    _bundle_sha_receipt(ci, "source CI receipt")
    _validate_ci_v2_receipt(ci, "source CI receipt")
    if (
        ci["provider"] != "GITHUB_ACTIONS"
        or type(ci["run_id"]) is not int
        or ci["run_id"] <= 0
        or ci["conclusion"] != "success"
    ):
        raise BundleRefusal("source CI receipt is not a successful GitHub Actions occurrence")
    _git_oid(ci["head_sha"], "source CI receipt.head_sha")
    raw_ci = _string(ci["raw_response_utf8"], "source CI receipt.raw_response_utf8")
    if _sha_bytes(raw_ci.encode("utf-8")) != _sha(ci["raw_response_sha256"], "source CI receipt.raw_response_sha256"):
        raise BundleRefusal("source CI raw response digest mismatch")
    # The retained provider body is evidence in its received form, not an
    # emitter-owned canonical document.  It still has to be strict JSON with
    # no duplicate/non-finite ambiguity before its attested fields are used.
    ci_api = _parse_json_bytes(raw_ci.encode("utf-8"), "source CI raw response", canonical=False)
    source_head_commit = ci_api.get("head_commit") if type(ci_api) is dict else None
    source_ci_completed_at = (
        _strict_utc_unix(ci_api.get("updated_at"), "source CI raw response.updated_at")
        if type(ci_api) is dict
        else None
    )
    if (
        type(ci_api) is not dict
        or ci_api.get("id") != ci["run_id"]
        or ci_api.get("head_sha") != ci["head_sha"]
        or ci_api.get("status") != "completed"
        or ci_api.get("conclusion") != ci["conclusion"]
        or type(source_head_commit) is not dict
        or source_head_commit.get("id") != ci["head_sha"]
        or source_head_commit.get("tree_id") != candidate["chronology"]["source_tree_oid"]
        or candidate["chronology"]["source_frozen_at_unix"]
        > source_ci_completed_at
        or candidate["chronology"]["preregistration_committed_at_unix"]
        < source_ci_completed_at
    ):
        raise BundleRefusal(
            "source CI raw response does not attest completed source-A tree/freeze/precedence"
        )

    preregistration_ci_data = _check_exact_keys(
        preregistration_ci,
        {
            "schema_version", "provider", "run_id", "head_sha", "head_tree_oid",
            "preregistration_path", "preregistration_git_blob_oid", "preregistration_sha256",
            "status", "conclusion", "completed_at_utc", "completed_at_unix",
            "raw_response_sha256", "raw_response_utf8", "discovery_query", "critical_projection", "raw_list_response_sha256", "raw_list_response_utf8", "receipt_sha256",
        },
        "preregistration B CI receipt",
    )
    if preregistration_ci_data["schema_version"] != "hswm-dnrd-preregistration-b-ci-receipt/v2":
        raise BundleRefusal("preregistration B CI receipt schema mismatch")
    _bundle_sha_receipt(preregistration_ci_data, "preregistration B CI receipt")
    _validate_ci_v2_receipt(preregistration_ci_data, "preregistration B CI receipt")
    if (
        preregistration_ci_data["provider"] != "GITHUB_ACTIONS"
        or type(preregistration_ci_data["run_id"]) is not int
        or preregistration_ci_data["run_id"] <= 0
        or preregistration_ci_data["status"] != "completed"
        or preregistration_ci_data["conclusion"] != "success"
        or preregistration_ci_data["preregistration_sha256"]
        != bindings["preregistration_sha256"]
        or _sha_bytes(preregistration_ci_bytes)
        != bindings["preregistration_ci_receipt_sha256"]
    ):
        raise BundleRefusal("preregistration B CI receipt does not bind the candidate/status contract")
    for key in ("head_sha", "head_tree_oid", "preregistration_git_blob_oid"):
        _git_oid(preregistration_ci_data[key], f"preregistration B CI receipt.{key}")
    _string(
        preregistration_ci_data["preregistration_path"],
        "preregistration B CI receipt.preregistration_path",
    )
    raw_preregistration_ci = _string(
        preregistration_ci_data["raw_response_utf8"],
        "preregistration B CI receipt.raw_response_utf8",
    )
    if _sha_bytes(raw_preregistration_ci.encode("utf-8")) != _sha(
        preregistration_ci_data["raw_response_sha256"],
        "preregistration B CI receipt.raw_response_sha256",
    ):
        raise BundleRefusal("preregistration B CI raw response digest mismatch")
    completed_at_unix = _integer(
        preregistration_ci_data["completed_at_unix"],
        "preregistration B CI receipt.completed_at_unix",
        minimum=1,
    )
    completed_at_utc = _strict_utc_unix(
        preregistration_ci_data["completed_at_utc"],
        "preregistration B CI receipt.completed_at_utc",
    )
    if completed_at_utc != completed_at_unix:
        raise BundleRefusal("preregistration B CI receipt UTC completion time drifted")
    raw_api = _parse_json_bytes(
        raw_preregistration_ci.encode("utf-8"),
        "preregistration B CI raw response",
        canonical=False,
    )
    head_commit = raw_api.get("head_commit") if type(raw_api) is dict else None
    if (
        type(raw_api) is not dict
        or raw_api.get("id") != preregistration_ci_data["run_id"]
        or raw_api.get("head_sha") != preregistration_ci_data["head_sha"]
        or raw_api.get("status") != "completed"
        or raw_api.get("conclusion") != "success"
        or raw_api.get("updated_at") != preregistration_ci_data["completed_at_utc"]
        or type(head_commit) is not dict
        or head_commit.get("id") != preregistration_ci_data["head_sha"]
        or head_commit.get("tree_id") != preregistration_ci_data["head_tree_oid"]
    ):
        raise BundleRefusal(
            "preregistration B CI raw response does not attest frozen run/head/tree/completion"
        )

    prereg_ci = _check_exact_keys(
        prereg["source_a_ci"],
        {"receipt_sha256", "run_id", "head_sha", "conclusion"},
        "preregistration.source_a_ci",
    )
    if prereg_ci["receipt_sha256"] != _sha_bytes(_canonical_bytes(source_ci)):
        raise BundleRefusal("preregistration does not bind retained source-CI receipt bytes")
    if (
        prereg_ci.get("run_id") != ci["run_id"]
        or prereg_ci.get("head_sha") != ci["head_sha"]
        or ci["head_sha"] != candidate["chronology"]["source_commit"]
        or prereg_ci.get("conclusion") != "success"
    ):
        raise BundleRefusal("preregistration source-CI identity mismatch")


def _validate_execution_closure_modes(closure: Path, label: str) -> None:
    """Verify the retained owner-read/execute-only seal, including directories."""
    try:
        root_info = closure.lstat()
    except FileNotFoundError as error:
        raise BundleRefusal(f"{label} directory is absent") from error
    if (
        stat.S_ISLNK(root_info.st_mode)
        or not stat.S_ISDIR(root_info.st_mode)
        or stat.S_IMODE(root_info.st_mode) != 0o500
    ):
        raise BundleRefusal(f"{label} root must be a plain 0500 directory")
    for path in closure.rglob("*"):
        info = path.lstat()
        relative = path.relative_to(closure).as_posix()
        if stat.S_ISLNK(info.st_mode):
            raise BundleRefusal(f"{label} contains a symbolic link: {relative}")
        if stat.S_ISDIR(info.st_mode):
            if stat.S_IMODE(info.st_mode) != 0o500:
                raise BundleRefusal(f"{label} directory is not sealed 0500: {relative}")
        elif stat.S_ISREG(info.st_mode):
            if stat.S_IMODE(info.st_mode) != 0o400:
                raise BundleRefusal(f"{label} file is not sealed 0400: {relative}")
        else:
            raise BundleRefusal(f"{label} contains a nonregular path: {relative}")


def _validate_source_closure(root: Path, source: Mapping[str, Any]) -> None:
    """Rehash the copied source-A closure, rather than trusting its manifest."""
    closure = root / "source_closure"
    _validate_execution_closure_modes(closure, "source closure")
    files = source["files"]
    expected: set[str] = set()
    for index, row in enumerate(files):
        path = _string(row["path"], f"source closure manifest.files[{index}].path")
        expected.add(path)
        target = _bundle_plain_file(root, f"source_closure/{path}")
        if _sha_bytes(target.read_bytes()) != row["sha256"]:
            raise BundleRefusal(f"source closure copy does not match source manifest: {path}")
    actual = {
        path.relative_to(closure).as_posix()
        for path in closure.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    if actual != expected:
        raise BundleRefusal("source closure contains files absent from, or missing from, source manifest")


def _runtime_relative_path(value: object, label: str) -> str:
    """Validate the same narrow relative-path domain as the runtime exporter."""
    path = _string(value, label)
    if path.startswith("/") or any(part in {"", ".", ".."} for part in Path(path).parts):
        raise BundleRefusal(f"{label} is not a safe runtime-relative path")
    return path


def _runtime_closure_files(root: Path) -> dict[str, bytes]:
    """Read the copied runtime tree while refusing links and special files.

    ``bundle_index`` normally establishes this boundary first, but the runtime
    validator deliberately repeats the filesystem walk.  That lets this
    narrowly-scoped verifier be used directly in a unit/adversarial audit and
    means a symlinked deep package member cannot evade package-closure checks.
    """
    closure = root / "bridge_runtime_closure"
    _validate_execution_closure_modes(closure, "bridge runtime closure")
    result: dict[str, bytes] = {}

    def visit(directory: Path) -> None:
        for child in directory.iterdir():
            child_info = child.lstat()
            relative = child.relative_to(closure).as_posix()
            if child.is_symlink():
                raise BundleRefusal(f"bridge runtime closure contains a symbolic link: {relative}")
            if stat.S_ISDIR(child_info.st_mode):
                visit(child)
            elif stat.S_ISREG(child_info.st_mode):
                # npm package closures can contain intentional zero-byte
                # marker modules.  Their admissibility is decided below only
                # by the complete manifest's exact path, byte count and hash.
                result[relative] = child.read_bytes()
            else:
                raise BundleRefusal(f"bridge runtime closure contains a nonregular path: {relative}")

    visit(closure)
    if not result:
        raise BundleRefusal("bridge runtime closure has no copied bytes")
    return result


def _runtime_manifest_rows(
    rows: object,
    *,
    label: str,
    closure_files: Mapping[str, bytes] | None = None,
    required_prefix: str | None = None,
    require_bytes: bool = True,
) -> dict[str, str]:
    """Parse sorted `{path,sha256}` rows and optionally rehash copied bytes."""
    if type(rows) is not list or not rows:
        raise BundleRefusal(f"{label} must be a nonempty file list")
    result: dict[str, str] = {}
    previous = ""
    for index, raw in enumerate(rows):
        row = _check_exact_keys(raw, {"path", "sha256", "bytes"} if require_bytes else {"path", "sha256"}, f"{label}[{index}]")
        path = _runtime_relative_path(row["path"], f"{label}[{index}].path")
        digest = _sha(row["sha256"], f"{label}[{index}].sha256")
        if require_bytes and (type(row["bytes"]) is not int or row["bytes"] < 0):
            raise BundleRefusal(f"{label}[{index}].bytes must be a nonnegative integer")
        if path <= previous or path in result:
            raise BundleRefusal(f"{label} must be strictly sorted and duplicate-free")
        if required_prefix is not None and not path.startswith(f"{required_prefix}/"):
            raise BundleRefusal(f"{label} escapes its declared package root")
        if closure_files is not None:
            body = closure_files.get(path)
            if body is None or (require_bytes and len(body) != row["bytes"]) or _sha_bytes(body) != digest:
                raise BundleRefusal(f"{label} copy hash mismatch: {path}")
        result[path] = digest
        previous = path
    return result


def _runtime_package_metadata(raw: bytes, label: str) -> tuple[str, str, set[str]]:
    """Strictly parse retained package metadata without requiring canonical npm JSON."""
    value = _parse_json_bytes(raw, label, canonical=False)
    if type(value) is not dict:
        raise BundleRefusal(f"{label} must be a JSON object")
    name = _string(value.get("name"), f"{label}.name")
    version = _string(value.get("version"), f"{label}.version")
    dependencies = value.get("dependencies", {})
    if type(dependencies) is not dict or any(type(key) is not str or not key for key in dependencies):
        raise BundleRefusal(f"{label}.dependencies is malformed")
    return name, version, set(dependencies)


def _runtime_source_dependency_specs(
    raw: bytes, label: str
) -> tuple[dict[str, str], dict[str, str]]:
    """Read exact top-level dependency declarations from retained source A."""
    value = _parse_json_bytes(raw, label, canonical=False)
    if type(value) is not dict:
        raise BundleRefusal(f"{label} must be a JSON object")

    def parse(field: str) -> dict[str, str]:
        dependencies = value.get(field, {})
        if type(dependencies) is not dict:
            raise BundleRefusal(f"{label}.{field} is malformed")
        result: dict[str, str] = {}
        for name, version in dependencies.items():
            if type(name) is not str or not name or type(version) is not str or not version:
                raise BundleRefusal(f"{label}.{field} has a malformed dependency specification")
            result[name] = version
        return result

    return parse("dependencies"), parse("devDependencies")


def _runtime_source_lock_packages(raw: bytes, label: str) -> Mapping[str, Any]:
    """Retain only the package-lock v3 projection needed for exact row pins."""
    value = _parse_json_bytes(raw, label, canonical=False)
    if type(value) is not dict or value.get("lockfileVersion") != 3:
        raise BundleRefusal(f"{label} is not a supported npm package-lock v3 object")
    packages = value.get("packages")
    if type(packages) is not dict:
        raise BundleRefusal(f"{label}.packages is malformed")
    return packages


def _runtime_recursive_package_closure(
    roots: Sequence[str], package_dependencies: Mapping[str, set[str]]
) -> set[str]:
    """Compute the exact selected package closure using copied package metadata."""
    closure: set[str] = set()
    pending = list(reversed(tuple(roots)))
    while pending:
        name = pending.pop()
        if name in closure:
            continue
        dependencies = package_dependencies.get(name)
        if dependencies is None:
            raise BundleRefusal(
                "bridge runtime external package closure omits a required root or transitive dependency"
            )
        closure.add(name)
        pending.extend(sorted(dependencies, reverse=True))
    return closure


def _validate_runtime_closure(
    root: Path,
    runtime: Mapping[str, Any],
    *,
    source: Mapping[str, Any],
    candidate: Mapping[str, Any],
    chronology: Mapping[str, Any],
) -> None:
    """Reverify the v3 compiled/runtime dependency closure from retained bytes.

    The source-selected package/lock/config inputs, pinned Node executable,
    exact compiler bytes, and recursive selected package closure are
    evidence-bound here.  This is deliberately an input/closure audit, not an
    independent build re-execution or a claim that compiled behavior was
    reproduced by this stdlib adjudicator.
    """
    manifest, raw = _bundle_object(root, "bridge_runtime_tree_manifest.json")
    if runtime.get("bridge_runtime_tree_manifest_sha256") != _sha_bytes(raw):
        raise BundleRefusal("runtime receipt does not bind copied bridge runtime-tree manifest bytes")
    data = _check_exact_keys(
        manifest,
        {"schema_version", "root_path", "entrypoint", "files", "external_packages", "build_provenance"},
        "bridge runtime tree manifest",
    )
    if data["schema_version"] != RUNTIME_TREE_MANIFEST_SCHEMA:
        raise BundleRefusal("bridge runtime tree manifest schema mismatch")
    if (
        _string(data["root_path"], "bridge runtime tree manifest.root_path")
        != runtime.get("bridge_runtime_root")
    ):
        raise BundleRefusal("bridge runtime tree root does not bind the runtime receipt")

    closure_files = _runtime_closure_files(root)
    compiled = _runtime_manifest_rows(
        data["files"], label="bridge runtime tree files", closure_files=closure_files
    )
    entrypoint = _runtime_relative_path(data["entrypoint"], "bridge runtime tree manifest.entrypoint")
    if entrypoint not in compiled or compiled[entrypoint] != runtime.get("bridge_implementation_sha256"):
        raise BundleRefusal("runtime receipt bridge implementation is not the copied runtime-tree entrypoint")

    packages = data["external_packages"]
    if type(packages) is not list or len(packages) > RUNTIME_CLOSURE_MAX_FILES:
        raise BundleRefusal("bridge runtime external package pinset is malformed")
    package_names: set[str] = set()
    package_roots: set[str] = set()
    package_files: dict[str, str] = {}
    package_by_name: dict[str, Mapping[str, Any]] = {}
    package_dependencies: dict[str, set[str]] = {}
    previous_name = ""
    for index, raw_package in enumerate(packages):
        package = _check_exact_keys(
            raw_package,
            {
                "name", "version", "package_root", "package_json_path", "package_json_sha256",
                "resolved_entrypoint_path", "resolved_entrypoint_sha256", "files",
            },
            f"bridge runtime external_packages[{index}]",
        )
        name = _string(package["name"], f"bridge runtime external_packages[{index}].name")
        version = _string(package["version"], f"bridge runtime external_packages[{index}].version")
        package_root = _runtime_relative_path(
            package["package_root"], f"bridge runtime external_packages[{index}].package_root"
        )
        package_json_path = _runtime_relative_path(
            package["package_json_path"], f"bridge runtime external_packages[{index}].package_json_path"
        )
        entrypoint_path = _runtime_relative_path(
            package["resolved_entrypoint_path"],
            f"bridge runtime external_packages[{index}].resolved_entrypoint_path",
        )
        package_json_sha = _sha(
            package["package_json_sha256"], f"bridge runtime external_packages[{index}].package_json_sha256"
        )
        entrypoint_sha = _sha(
            package["resolved_entrypoint_sha256"],
            f"bridge runtime external_packages[{index}].resolved_entrypoint_sha256"
        )
        if (
            name <= previous_name
            or name in package_names
            or package_root in package_roots
            or package_root != f"node_modules/{name}"
            or package_json_path != f"{package_root}/package.json"
            or not entrypoint_path.startswith(f"{package_root}/")
        ):
            raise BundleRefusal("bridge runtime external package identity/order is not exact and safe")
        rows = _runtime_manifest_rows(
            package["files"],
            label=f"bridge runtime external package {name} files",
            closure_files=closure_files,
            required_prefix=package_root,
        )
        actual_under_root = {
            path for path in closure_files if path.startswith(f"{package_root}/")
        }
        if (
            set(rows) != actual_under_root
            or package_json_path not in rows
            or rows[package_json_path] != package_json_sha
            or entrypoint_path not in rows
            or rows[entrypoint_path] != entrypoint_sha
            or set(rows) & set(compiled)
            or set(rows) & set(package_files)
        ):
            raise BundleRefusal("bridge runtime external package file closure is not exact")
        package_body = closure_files[package_json_path]
        discovered_name, discovered_version, dependencies = _runtime_package_metadata(
            package_body, f"bridge runtime external package {name} package.json"
        )
        if discovered_name != name or discovered_version != version:
            raise BundleRefusal("bridge runtime external package metadata does not match copied package.json bytes")
        package_names.add(name)
        package_roots.add(package_root)
        package_files.update(rows)
        package_by_name[name] = package
        package_dependencies[name] = dependencies
        previous_name = name
    expected_package_names = _runtime_recursive_package_closure(
        RUNTIME_PACKAGE_ROOTS, package_dependencies
    )
    if package_names != expected_package_names:
        raise BundleRefusal(
            "bridge runtime external package names do not equal the exact recursive selected dependency closure"
        )

    expected_files = set(compiled) | set(package_files)
    if set(closure_files) != expected_files:
        raise BundleRefusal("runtime closure contains files absent from, or missing from, its complete tree manifest")
    if (
        len(expected_files) > RUNTIME_CLOSURE_MAX_FILES
        or sum(len(body) for body in closure_files.values()) > RUNTIME_CLOSURE_MAX_TOTAL_BYTES
    ):
        raise BundleRefusal("bridge runtime closure exceeds the frozen 8192-file/64-MiB bounds")

    provenance = _check_exact_keys(
        data["build_provenance"],
        {
            "source_a_commit", "source_a_tree", "source_manifest_path", "source_manifest_sha256",
            "node_executable_sha256", "node_version", "dependency_materialization_command",
            "compilation_command", "claim_boundary", "source_inputs", "package_roots", "typescript",
        },
        "bridge runtime build provenance",
    )
    chronology_source = _check_exact_keys(
        chronology.get("source"),
        {
            "commit_oid", "commit_raw_utf8", "tree_oid", "commit_time_unix",
            "source_manifest_path", "source_manifest_blob_sha256", "file_blobs",
        },
        "git chronology source for runtime provenance",
    )
    if (
        provenance["source_a_commit"] != candidate["chronology"]["source_commit"]
        or provenance["source_a_tree"] != candidate["chronology"]["source_tree_oid"]
        or provenance["source_manifest_path"] != chronology_source["source_manifest_path"]
        or provenance["source_manifest_sha256"] != candidate["bindings"]["source_manifest_sha256"]
        or provenance["node_executable_sha256"] != runtime.get("node_executable_sha256")
        or provenance["node_version"] != runtime.get("node_version")
        or provenance["dependency_materialization_command"]
        != list(RUNTIME_DEPENDENCY_MATERIALIZATION_COMMAND)
        or provenance["compilation_command"] != list(RUNTIME_COMPILATION_COMMAND)
        or provenance["claim_boundary"] != RUNTIME_BUILD_CLAIM_BOUNDARY
        or provenance["package_roots"] != list(RUNTIME_PACKAGE_ROOTS)
    ):
        raise BundleRefusal(
            "bridge runtime build provenance does not bind source-A, Node, selected packages, and the fixed v3 recipe"
        )
    _git_oid(provenance["source_a_commit"], "bridge runtime build provenance.source_a_commit")
    _git_oid(provenance["source_a_tree"], "bridge runtime build provenance.source_a_tree")
    _runtime_relative_path(provenance["source_manifest_path"], "bridge runtime build provenance.source_manifest_path")
    _sha(provenance["source_manifest_sha256"], "bridge runtime build provenance.source_manifest_sha256")
    _sha(provenance["node_executable_sha256"], "bridge runtime build provenance.node_executable_sha256")
    _string(provenance["node_version"], "bridge runtime build provenance.node_version")

    _string(
        provenance["claim_boundary"], "bridge runtime build provenance.claim_boundary"
    )
    source_inputs = _runtime_manifest_rows(
        provenance["source_inputs"], label="bridge runtime build source inputs", require_bytes=False
    )
    source_rows = _runtime_manifest_rows(source["files"], label="retained source manifest inputs", require_bytes=False)
    if source_inputs != source_rows:
        raise BundleRefusal("bridge runtime build source inputs do not exactly reproduce the source-A manifest")
    for path, digest in source_inputs.items():
        source_body = _bundle_plain_file(root, f"source_closure/{path}").read_bytes()
        if _sha_bytes(source_body) != digest:
            raise BundleRefusal("bridge runtime build input does not match copied source-A closure bytes")
    required_inputs = {
        RUNTIME_SOURCE_PACKAGE_JSON,
        RUNTIME_SOURCE_PACKAGE_LOCK,
        "src/hswm/effect-runtime/tsconfig.json",
        "src/hswm/effect-runtime/tsconfig.build.json",
        RUNTIME_SOURCE_TSCONFIG,
        "src/hswm/effect-runtime/.npmrc",
    }
    if not required_inputs.issubset(source_inputs):
        raise BundleRefusal("bridge runtime build provenance lacks required package/lock/compiler source inputs")

    source_dependencies, source_dev_dependencies = _runtime_source_dependency_specs(
        _bundle_plain_file(root, f"source_closure/{RUNTIME_SOURCE_PACKAGE_JSON}").read_bytes(),
        "retained source-A effect-runtime package.json",
    )
    source_lock_packages = _runtime_source_lock_packages(
        _bundle_plain_file(root, f"source_closure/{RUNTIME_SOURCE_PACKAGE_LOCK}").read_bytes(),
        "retained source-A effect-runtime package-lock.json",
    )
    for name, package in package_by_name.items():
        lock_entry = source_lock_packages.get(f"node_modules/{name}")
        if type(lock_entry) is not dict or lock_entry.get("version") != package["version"]:
            raise BundleRefusal(
                "bridge runtime external package name/version does not match source-A package-lock pin"
            )
    expected_root_versions = {
        "effect": source_dependencies.get("effect"),
        "typescript": source_dev_dependencies.get("typescript"),
        "@types/node": source_dev_dependencies.get("@types/node"),
    }
    if any(
        type(version) is not str
        or package_by_name.get(name) is None
        or package_by_name[name]["version"] != version
        for name, version in expected_root_versions.items()
    ):
        raise BundleRefusal(
            "bridge runtime package root version does not exactly match source-A dependencies/devDependencies"
        )
    compiler = _check_exact_keys(
        provenance["typescript"],
        {
            "package_json_path", "package_json_sha256", "bin_tsc_path", "bin_tsc_sha256",
            "lib_tsc_path", "lib_tsc_sha256", "lib_typescript_path", "lib_typescript_sha256",
        },
        "bridge runtime TypeScript compiler pin",
    )
    compiler_pairs = (
        ("package_json_path", "package_json_sha256"),
        ("bin_tsc_path", "bin_tsc_sha256"),
        ("lib_tsc_path", "lib_tsc_sha256"),
        ("lib_typescript_path", "lib_typescript_sha256"),
    )
    compiler_paths: list[str] = []
    typescript = package_by_name.get("typescript")
    if typescript is None or typescript["package_root"] != "node_modules/typescript":
        raise BundleRefusal("bridge runtime build provenance lacks the pinned TypeScript package closure")
    for path_key, sha_key in compiler_pairs:
        path = _runtime_relative_path(compiler[path_key], f"bridge runtime TypeScript compiler.{path_key}")
        digest = _sha(compiler[sha_key], f"bridge runtime TypeScript compiler.{sha_key}")
        if (
            not path.startswith("node_modules/typescript/")
            or package_files.get(path) != digest
        ):
            raise BundleRefusal("bridge runtime TypeScript compiler bytes are absent from its copied package closure")
        compiler_paths.append(path)
    if (
        len(set(compiler_paths)) != len(compiler_paths)
        or compiler["package_json_path"] != typescript["package_json_path"]
        or compiler["lib_tsc_path"] != RUNTIME_COMPILATION_COMMAND[1]
    ):
        raise BundleRefusal("bridge runtime TypeScript compiler pin does not identify four exact compiler files")

    # Re-run the same conservative static-import closure check used by the
    # executor against retained compiled bytes.  Dynamic loading remains
    # runtime-trusted, but omitted ordinary JS siblings or package identities
    # cannot silently shrink this independently auditable closure.
    import_pattern = re.compile(r"(?:\bfrom\s*|\bimport\s*\()\s*[\"']([^\"']+)[\"']")
    for relative in sorted(compiled):
        if not relative.endswith(".js"):
            continue
        try:
            text = closure_files[relative].decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise BundleRefusal(f"compiled runtime JavaScript is not UTF-8: {relative}") from error
        for target in import_pattern.findall(text):
            if target.startswith("."):
                normalized = (Path(relative).parent / target).as_posix()
                if not normalized.endswith(".js"):
                    normalized += ".js"
                if normalized not in compiled:
                    raise BundleRefusal("runtime-tree closure omits a static relative JavaScript import")
            elif not target.startswith(("node:", "#")) and target not in package_names:
                raise BundleRefusal("runtime-tree closure omits a static external package identity")


def _validate_preregistration_runtime_binding(
    preregistration: Mapping[str, Any],
    runtime: Mapping[str, Any],
    config: Mapping[str, Any],
) -> None:
    binding = _check_exact_keys(
        preregistration.get("runtime_bindings"),
        {
            "model_endpoint", "bridge_implementation_sha256", "bridge_runtime_tree_manifest_sha256",
            "bridge_config_sha256", "scorer_implementation_sha256", "node_executable_sha256",
            "node_version", "python_executable_sha256", "python_version", "unicode_data_version",
            "verifier_helper_sha256", "verifier_package_lock_sha256", "verifier_runtime_bundle_sha256",
            "structured_output_qualification_sha256",
            "subprocess_environment",
        },
        "preregistration.runtime_bindings",
    )
    runtime_keys = (
        "bridge_implementation_sha256", "bridge_runtime_tree_manifest_sha256",
        "scorer_implementation_sha256", "node_executable_sha256", "node_version",
        "python_executable_sha256", "python_version", "unicode_data_version",
    )
    config_keys = (
        "model_endpoint", "verifier_helper_sha256", "verifier_package_lock_sha256",
        "verifier_runtime_bundle_sha256", "structured_output_qualification_sha256",
    )
    for key in runtime_keys:
        if binding[key] != runtime.get(key):
            raise BundleRefusal(
                f"preregistration runtime binding differs from retained runtime receipt: {key}"
            )
    for key in config_keys:
        if binding[key] != config.get(key):
            raise BundleRefusal(
                f"preregistration runtime binding differs from execution config readback: {key}"
            )
    if binding["bridge_config_sha256"] != _canonical_hash(runtime.get("bridge_config")):
        raise BundleRefusal("preregistration bridge config binding differs from runtime receipt")
    if (
        binding["subprocess_environment"] != PINNED_SUBPROCESS_ENVIRONMENT
        or runtime.get("subprocess_environment") != PINNED_SUBPROCESS_ENVIRONMENT
    ):
        raise BundleRefusal("preregistration subprocess environment differs from runtime receipt")
    if (
        binding["verifier_runtime_bundle_sha256"]
        != OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256
        or binding["node_executable_sha256"] != OFFICIAL_NODE_EXECUTABLE_SHA256
        or binding["node_version"] != OFFICIAL_NODE_VERSION
        or binding["python_executable_sha256"]
        != OFFICIAL_PYTHON_EXECUTABLE_SHA256
        or binding["python_version"] != OFFICIAL_PYTHON_VERSION
        or binding["unicode_data_version"] != OFFICIAL_UNICODE_DATA_VERSION
    ):
        raise BundleRefusal(
            "preregistration runtime identities differ from Source-A protocol constants"
        )


def _validate_verifier_source_binding(
    source: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    config: Mapping[str, Any],
) -> None:
    """Join retained Source-A verifier bytes to config and preregistration pins."""
    rows = source.get("files")
    if type(rows) is not list:
        raise BundleRefusal("source manifest verifier binding has no file rows")
    hashes: dict[str, str] = {}
    for index, raw in enumerate(rows):
        row = _check_exact_keys(
            raw, {"path", "sha256"}, f"source manifest verifier row[{index}]"
        )
        path = _string(row["path"], f"source manifest verifier row[{index}].path")
        if path in hashes:
            raise BundleRefusal("source manifest verifier binding repeats a path")
        hashes[path] = _sha(
            row["sha256"], f"source manifest verifier row[{index}].sha256"
        )
    binding = preregistration.get("runtime_bindings")
    if type(binding) is not dict:
        raise BundleRefusal("preregistration verifier source binding is absent")
    expected = {
        "_research/dnrd/verify-beacon.mjs": "verifier_helper_sha256",
        "tools/swm0w_drand/package-lock.json": "verifier_package_lock_sha256",
    }
    for path, field in expected.items():
        source_sha = hashes.get(path)
        if (
            source_sha is None
            or source_sha != config.get(field)
            or source_sha != binding.get(field)
        ):
            raise BundleRefusal(
                f"retained Source-A bytes do not bind preregistered {field}"
            )


def _preregistration_active_state_byte_ceiling(preregistration: Mapping[str, Any]) -> int:
    parity = _check_exact_keys(
        preregistration.get("parity_and_leakage"),
        {
            "same_served_model_id_and_chat_endpoint", "equal_client_dispatched_and_logical_requests",
            "equal_generation_limits_input_token_parity_not_claimed", "equal_candidate_evidence_universe",
            "all_active_payloads_within_byte_ceiling", "active_state_byte_ceiling",
            "full_fixed_rule_replay_numeric_payload_bytes_equal", "full_deranged_numeric_payload_byte_count_equal",
            "arm_labels_hidden_from_model", "fresh_process_recovery_observed", "distinct_arm_mount_ids",
            "evaluation_read_only_wrt_routing_observed", "cache_hits_required",
            "private_route_binding_open_only_after_response_seal", "pre_dispatch_readout_bound_before_model_response",
            "scorer_outcome_response_independent", "compiler_input_audit", "canary",
        },
        "preregistration.parity_and_leakage",
    )
    required_true = {
        "same_served_model_id_and_chat_endpoint", "equal_client_dispatched_and_logical_requests",
        "equal_generation_limits_input_token_parity_not_claimed", "equal_candidate_evidence_universe",
        "all_active_payloads_within_byte_ceiling", "full_fixed_rule_replay_numeric_payload_bytes_equal",
        "full_deranged_numeric_payload_byte_count_equal", "arm_labels_hidden_from_model",
        "fresh_process_recovery_observed", "distinct_arm_mount_ids",
        "evaluation_read_only_wrt_routing_observed", "private_route_binding_open_only_after_response_seal",
        "pre_dispatch_readout_bound_before_model_response", "scorer_outcome_response_independent",
    }
    if any(parity[key] is not True for key in required_true) or parity["cache_hits_required"] != 0:
        raise BundleRefusal("preregistration does not freeze the required observable parity boundaries")
    return _integer(
        parity["active_state_byte_ceiling"],
        "preregistration.parity_and_leakage.active_state_byte_ceiling", minimum=1,
    )


def _validate_source_closure_overlap(
    root: Path, source: Mapping[str, Any], public: Mapping[str, Any], candidate: Mapping[str, Any]
) -> None:
    strings: set[str] = set()
    for stream in public["streams"]:
        for episode in stream["training"] + stream["heldout"]:
            strings.update((episode["episode_id"], episode["entity"], episode["surface_template"], episode["prompt"]))
            strings.update(episode["aliases"])
            for evidence in episode["route_evidence"]:
                strings.update((evidence["evidence_text"], evidence["response_token"], evidence["route_id"]))
    needles = [value.encode("utf-8") for value in strings if len(value) >= 16]
    for row in source["files"]:
        path = _string(row["path"], "source closure overlap path")
        if any(needle in _bundle_plain_file(root, f"source_closure/{path}").read_bytes() for needle in needles):
            raise BundleRefusal("generated high-entropy public item occurs in retained source-A closure")
    if candidate["overlap"]["prior_item_overlap"] != 0:
        raise BundleRefusal("candidate prior-item overlap does not match closure rescan")


# ---------------------------------------------------------------------------
# Raw V2 bridge-mount closure replay
# ---------------------------------------------------------------------------


def _v2_text_key(value: str) -> bytes:
    """The TS canonical encoder orders object keys by UTF-16 code units."""
    try:
        return value.encode("utf-16-be", errors="strict")
    except UnicodeEncodeError as error:
        raise BundleRefusal("V2 canonical JSON has a lone surrogate key") from error


def _v2_quote(value: object, label: str) -> str:
    text = _string(value, label)
    pieces: list[str] = ['"']
    for character in text:
        code = ord(character)
        if 0xD800 <= code <= 0xDFFF:
            raise BundleRefusal(f"{label} contains a lone Unicode surrogate")
        if character == '"':
            pieces.append(r'\"')
        elif character == "\\":
            pieces.append(r"\\")
        elif character == "\b":
            pieces.append(r"\b")
        elif character == "\f":
            pieces.append(r"\f")
        elif character == "\n":
            pieces.append(r"\n")
        elif character == "\r":
            pieces.append(r"\r")
        elif character == "\t":
            pieces.append(r"\t")
        elif code < 0x20:
            pieces.append(f"\\u{code:04x}")
        else:
            pieces.append(character)
    pieces.append('"')
    return "".join(pieces)


def _v2_canonical_bytes(value: object, label: str = "V2 value") -> bytes:
    """Implement the bounded TS ``canonicalJsonBytes`` contract in stdlib.

    JSON's default Python spelling is not quite this contract: V2 keeps UTF-8
    characters literal, accepts only safe integers, and orders keys by JS
    UTF-16 text order.  The raw durability objects are all checked through
    this encoder before their hashes are used.
    """

    nodes = 0

    def encode(item: object, depth: int, where: str) -> str:
        nonlocal nodes
        if depth > 128:
            raise BundleRefusal(f"{where} exceeds V2 canonical JSON depth")
        nodes += 1
        if nodes > 100_000:
            raise BundleRefusal(f"{where} exceeds V2 canonical JSON node bound")
        if item is None:
            return "null"
        if type(item) is bool:
            return "true" if item else "false"
        if type(item) is int:
            if abs(item) > V2_SAFE_INTEGER:
                raise BundleRefusal(f"{where} is outside V2 safe-integer range")
            return str(item)
        if type(item) is str:
            return _v2_quote(item, where)
        if type(item) is list:
            return "[" + ",".join(
                encode(child, depth + 1, f"{where}[{index}]")
                for index, child in enumerate(item)
            ) + "]"
        if type(item) is dict:
            for key in item:
                if type(key) is not str:
                    raise BundleRefusal(f"{where} has a non-string V2 object key")
                _v2_quote(key, f"{where} object key")
            return "{" + ",".join(
                _v2_quote(key, f"{where} object key")
                + ":"
                + encode(item[key], depth + 1, f"{where}.{key}")
                for key in sorted(item, key=_v2_text_key)
            ) + "}"
        raise BundleRefusal(f"{where} is not representable by V2 canonical JSON")

    try:
        raw = encode(value, 0, label).encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise BundleRefusal(f"{label} is not strict UTF-8 canonical JSON") from error
    if len(raw) > V2_JSON_MAX_BYTES:
        raise BundleRefusal(f"{label} exceeds V2 canonical JSON byte bound")
    return raw


def _v2_object_bytes(data: bytes, label: str) -> Mapping[str, Any]:
    if not data or len(data) > V2_JSON_MAX_BYTES:
        raise BundleRefusal(f"{label} violates the V2 1 MiB JSON bound")
    value = _parse_json_bytes(data, label, canonical=False)
    if type(value) is not dict:
        raise BundleRefusal(f"{label} must be a V2 JSON object")
    if _v2_canonical_bytes(value, label) != data:
        raise BundleRefusal(f"{label} is not exact V2 canonical JSON bytes")
    return value


def _v2_identifier(value: object, label: str) -> str:
    result = _string(value, label)
    if not V2_IDENTIFIER.fullmatch(result):
        raise BundleRefusal(f"{label} is not a V2 identifier")
    return result


def _v2_integer(value: object, label: str, *, minimum: int | None = None, maximum: int | None = None) -> int:
    if type(value) is not int or abs(value) > V2_SAFE_INTEGER:
        raise BundleRefusal(f"{label} must be a V2 safe integer")
    if minimum is not None and value < minimum:
        raise BundleRefusal(f"{label} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise BundleRefusal(f"{label} must be <= {maximum}")
    return value


def _v2_descriptor(
    value: object,
    label: str,
    *,
    media_type: str | None = None,
    minimum_bytes: int = 0,
    maximum_bytes: int = V2_CONTENT_MAX_BYTES,
) -> Mapping[str, Any]:
    data = _check_exact_keys(value, {"mediaType", "byteLength", "sha256"}, label)
    raw_media = _string(data["mediaType"], f"{label}.mediaType")
    if "/" not in raw_media or len(raw_media) > 255:
        raise BundleRefusal(f"{label}.mediaType is not a V2 media type")
    if media_type is not None and raw_media != media_type:
        raise BundleRefusal(f"{label}.mediaType does not match the frozen media domain")
    _v2_integer(data["byteLength"], f"{label}.byteLength", minimum=minimum_bytes, maximum=maximum_bytes)
    _sha(data["sha256"], f"{label}.sha256")
    return data


def _v2_key(value: object, label: str) -> Mapping[str, Any]:
    data = _check_exact_keys(value, {"schemaVersion", "lineageId", "atomUid", "revisionId"}, label)
    _v2_identifier(data["schemaVersion"], f"{label}.schemaVersion")
    _v2_identifier(data["lineageId"], f"{label}.lineageId")
    _v2_identifier(data["atomUid"], f"{label}.atomUid")
    _v2_integer(data["revisionId"], f"{label}.revisionId", minimum=0)
    return data


def _v2_key_id(value: Mapping[str, Any]) -> str:
    return f"{value['schemaVersion']}|{value['lineageId']}|{value['atomUid']}|{value['revisionId']}"


def _v2_key_sort(value: Mapping[str, Any]) -> tuple[bytes, bytes, bytes, int]:
    return (
        _v2_text_key(str(value["schemaVersion"])),
        _v2_text_key(str(value["lineageId"])),
        _v2_text_key(str(value["atomUid"])),
        int(value["revisionId"]),
    )


def _v2_same_key(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> bool:
    if left is None or right is None:
        return left is right
    return _v2_key_id(left) == _v2_key_id(right)


def _v2_sorted_keys(values: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(values, key=_v2_key_sort)


def _v2_sha(value: object, label: str) -> str:
    return _sha(value, label)


def _v2_hash_object(value: object, label: str) -> str:
    return _sha_bytes(_v2_canonical_bytes(value, label))


def _v2_slot_name(lineage: str, schema_sha256: str, revision: int) -> str:
    raw = f"hswm-canonical-atom-v2-state-journal-slot/v1\0{lineage}\0{schema_sha256}\0{revision}"
    return _sha_bytes(raw.encode("utf-8"))


def _v2_expected_dnrd_schema() -> dict[str, Any]:
    """Exact schema object constructed by ``makeDnrdCanonicalSchemaV2``."""
    return {
        "_tag": "HSWMCanonicalSchemaV2",
        "contractVersion": "hswm-canonical-schema-contract/v2",
        "schemaVersion": V2_SCHEMA_VERSION,
        "scientificStatus": "UNJUDGED",
        "bootstrapTrustStatement": (
            "DNRD is local experimental structural validity only; it is not canonical Permit, "
            "admission, learning, or scientific efficacy."
        ),
        "owners": [
            {"address": "owner:dnrd:trajectory", "obligation": "Own local experimental trajectory records."},
            {"address": "owner:dnrd:outcome", "obligation": "Own local experimental declared-role-separated outcome records."},
            {"address": "owner:dnrd:credit", "obligation": "Own local experimental frozen credit records."},
            {"address": V2_ROUTING_OWNER, "obligation": "Own local experimental routing disposition revisions."},
        ],
        "kinds": [
            {
                "kind": "dnrd:trajectory", "form": "ENTITY", "revisionPolicy": "SINGLETON",
                "allowedOwners": ["owner:dnrd:trajectory"], "minimumArity": 0, "referenceContracts": [],
            },
            {
                "kind": "dnrd:outcome", "form": "RELATION", "revisionPolicy": "SINGLETON",
                "allowedOwners": ["owner:dnrd:outcome"], "minimumArity": 1,
                "referenceContracts": [{"referenceType": "dnrd:reference", "roles": [{"role": "trajectory", "targetKinds": ["dnrd:trajectory"], "minimum": 1, "maximum": 1}]}],
            },
            {
                "kind": "dnrd:credit", "form": "RELATION", "revisionPolicy": "SINGLETON",
                "allowedOwners": ["owner:dnrd:credit"], "minimumArity": 2,
                "referenceContracts": [{"referenceType": "dnrd:reference", "roles": [
                    {"role": "trajectory", "targetKinds": ["dnrd:trajectory"], "minimum": 1, "maximum": 1},
                    {"role": "outcome", "targetKinds": ["dnrd:outcome"], "minimum": 1, "maximum": 1},
                ]}],
            },
            {
                "kind": "dnrd:routing-disposition", "form": "ENTITY", "revisionPolicy": "LINEAR",
                "allowedOwners": [V2_ROUTING_OWNER], "minimumArity": 0,
                "referenceContracts": [
                    {"referenceType": "dnrd:reference", "roles": [{"role": "credit", "targetKinds": ["dnrd:credit"], "minimum": 0, "maximum": 1}]},
                    {"referenceType": "hswm:reference:supersedes", "roles": [{"role": "hswm:role:predecessor", "targetKinds": ["dnrd:routing-disposition"], "minimum": 0, "maximum": 1}]},
                ],
            },
        ],
    }


def _v2_expected_schema_descriptor() -> tuple[Mapping[str, Any], bytes]:
    raw = _v2_canonical_bytes(_v2_expected_dnrd_schema(), "frozen DNRD V2 schema")
    return (
        {
            "mediaType": V2_SCHEMA_MEDIA_TYPE,
            "byteLength": len(raw),
            "sha256": _sha_bytes(raw),
        },
        raw,
    )


def _closure_safe_path(value: object, label: str) -> str:
    path = _string(value, label)
    if (
        path.startswith("/")
        or any(part in {"", ".", ".."} for part in Path(path).parts)
        or "\\" in path
    ):
        raise BundleRefusal(f"{label} is not a safe closure-relative path")
    return path


def _closure_files(
    root: Path, manifest: Mapping[str, Any]
) -> dict[str, bytes]:
    """Rehash the retained immutable V2 file tree and reject unlisted bytes."""
    rows = manifest["files"]
    if type(rows) is not list or not rows:
        raise BundleRefusal("bridge mount closure must retain a nonempty file manifest")
    if len(rows) > MOUNT_CLOSURE_MAX_FILES:
        raise BundleRefusal("bridge mount closure exceeds the frozen 4096-file bound")
    listed: dict[str, bytes] = {}
    previous = ""
    total_bytes = 0
    for index, raw_row in enumerate(rows):
        row = _check_exact_keys(raw_row, {"path", "sha256", "bytes", "mode"}, f"bridge mount closure.files[{index}]")
        relative = _closure_safe_path(row["path"], f"bridge mount closure.files[{index}].path")
        if relative <= previous:
            raise BundleRefusal("bridge mount closure file paths must be strictly sorted")
        previous = relative
        expected_hash = _sha(row["sha256"], f"bridge mount closure.files[{index}].sha256")
        expected_bytes = _v2_integer(
            row["bytes"], f"bridge mount closure.files[{index}].bytes", minimum=1,
            maximum=MOUNT_CLOSURE_MAX_FILE_BYTES,
        )
        total_bytes += expected_bytes
        if total_bytes > MOUNT_CLOSURE_MAX_TOTAL_BYTES:
            raise BundleRefusal("bridge mount closure exceeds the frozen 16-MiB total-byte bound")
        if row["mode"] != 0o400:
            raise BundleRefusal("bridge mount closure file manifest must retain immutable 0400 mode")
        target = root / "bridge_mount_closure" / relative
        try:
            info = target.lstat()
        except FileNotFoundError as error:
            raise BundleRefusal(f"bridge mount closure is missing listed file {relative!r}") from error
        if target.is_symlink() or not target.is_file() or stat.S_IMODE(info.st_mode) != 0o400:
            raise BundleRefusal(f"bridge mount closure file {relative!r} is not an immutable plain 0400 file")
        raw = target.read_bytes()
        if len(raw) != expected_bytes or _sha_bytes(raw) != expected_hash:
            raise BundleRefusal(f"bridge mount closure listed hash/size mismatch: {relative}")
        listed[relative] = raw

    closure = root / "bridge_mount_closure"
    try:
        root_info = closure.lstat()
    except FileNotFoundError as error:
        raise BundleRefusal("bridge mount closure directory is absent") from error
    if closure.is_symlink() or not closure.is_dir() or stat.S_IMODE(root_info.st_mode) != 0o700:
        raise BundleRefusal("bridge mount closure root must be a private plain 0700 directory")
    actual: set[str] = set()
    for item in closure.rglob("*"):
        relative = item.relative_to(closure).as_posix()
        info = item.lstat()
        if item.is_symlink():
            raise BundleRefusal(f"bridge mount closure contains a symbolic link: {relative}")
        if item.is_dir():
            if stat.S_IMODE(info.st_mode) != 0o700:
                raise BundleRefusal(f"bridge mount closure directory is not private 0700: {relative}")
        elif item.is_file():
            if stat.S_IMODE(info.st_mode) != 0o400:
                raise BundleRefusal(f"bridge mount closure file is not immutable 0400: {relative}")
            actual.add(relative)
        else:
            raise BundleRefusal(f"bridge mount closure contains a nonregular path: {relative}")
    if actual != set(listed):
        raise BundleRefusal(
            "bridge mount closure files differ from manifest: "
            f"missing={sorted(actual - set(listed))}, excess={sorted(set(listed) - actual)}"
        )
    return listed


def _closure_file(files: Mapping[str, bytes], relative: str, label: str) -> bytes:
    raw = files.get(relative)
    if raw is None:
        raise BundleRefusal(f"{label} is absent from bridge mount closure")
    return raw


def _closure_v2_object(files: Mapping[str, bytes], relative: str, label: str) -> Mapping[str, Any]:
    return _v2_object_bytes(_closure_file(files, relative, label), label)


def _closure_state_evidence_map(
    state_evidence: Mapping[str, Any], public: Mapping[str, Any]
) -> dict[tuple[str, str], Mapping[str, Any]]:
    top = _check_exact_keys(state_evidence, {"schema_version", "streams"}, "bridge state evidence for closure")
    if top["schema_version"] != "hswm-dnrd-bridge-state-evidence/v2" or type(top["streams"]) is not list:
        raise BundleRefusal("bridge state evidence does not have the frozen closure-bindable schema")
    public_ids = {str(stream["stream_id"]) for stream in public["streams"]}
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for stream_index, raw_stream in enumerate(top["streams"]):
        stream = _check_exact_keys(raw_stream, {"stream_id", "pre_evaluation", "post_evaluation", "fixed_rule_replay"}, f"bridge state closure streams[{stream_index}]")
        stream_id = _string(stream["stream_id"], f"bridge state closure streams[{stream_index}].stream_id")
        if stream_id not in public_ids:
            raise BundleRefusal("bridge state closure evidence names an unknown public stream")
        for timing in ("pre_evaluation", "post_evaluation"):
            snapshot = _check_exact_keys(
                stream[timing], {"arms", "fresh_recovery"}, f"bridge state closure {stream_id}.{timing}"
            )
            arms = _check_exact_keys(snapshot["arms"], set(ARMS), f"bridge state closure {stream_id}.{timing}.arms")
            recovery = _check_exact_keys(
                snapshot["fresh_recovery"], set(ARMS), f"bridge state closure {stream_id}.{timing}.fresh_recovery"
            )
            for arm in ARMS:
                entry = _check_exact_keys(
                    arms[arm],
                    {
                        "mount_id", "mount_role", "state_sha256", "routing_payload_utf8",
                        "routing_payload_sha256", "routing_payload_bytes", "score_projection_utf8",
                        "score_projection_sha256", "score_projection_bytes",
                    },
                    f"bridge state closure {stream_id}.{timing}.{arm}",
                )
                mount_id = _string(entry["mount_id"], f"bridge state closure {stream_id}.{timing}.{arm}.mount_id")
                if not V2_MOUNT_ID.fullmatch(mount_id) or entry["mount_role"] != MOUNT_ROLES[arm]:
                    raise BundleRefusal("bridge state closure evidence does not retain the raw expected mount role")
                payload_hash = _sha(
                    entry["routing_payload_sha256"], f"bridge state closure {stream_id}.{timing}.{arm}.routing_payload_sha256"
                )
                if entry["state_sha256"] != payload_hash:
                    raise BundleRefusal("bridge state closure evidence state hash does not equal durable routing payload hash")
                rec = _check_exact_keys(
                    recovery[arm], {"recovered", "fresh_process", "journal_sha256", "process_instance_id"},
                    f"bridge state closure {stream_id}.{timing}.{arm}.fresh_recovery",
                )
                if rec["recovered"] is not True or rec["fresh_process"] is not True:
                    raise BundleRefusal("bridge state closure has no fresh durable recovery observation")
                _sha(rec["journal_sha256"], f"bridge state closure {stream_id}.{timing}.{arm}.journal_sha256")
                _process_instance_id(rec["process_instance_id"], f"bridge state closure {stream_id}.{timing}.{arm}.process_instance_id")
                key = (stream_id, arm)
                previous = result.get(key)
                if timing == "pre_evaluation":
                    if previous is not None:
                        raise BundleRefusal("bridge state closure repeats a stream/arm evidence entry")
                    result[key] = {"pre": entry, "pre_recovery": rec}
                else:
                    if previous is None:
                        raise BundleRefusal("bridge state closure post-evaluation evidence lacks a pre-evaluation entry")
                    result[key] = {**previous, "post": entry, "post_recovery": rec}
        replay = _check_exact_keys(
            stream["fixed_rule_replay"], {"state", "fresh_recovery", "post_evaluation"},
            f"bridge state closure {stream_id}.fixed_rule_replay",
        )
        replay_post = _check_exact_keys(
            replay["post_evaluation"], {"state", "fresh_recovery"},
            f"bridge state closure {stream_id}.fixed_rule_replay.post_evaluation",
        )
        for timing, entry_value, recovery_value in (
            ("pre", replay["state"], replay["fresh_recovery"]),
            ("post", replay_post["state"], replay_post["fresh_recovery"]),
        ):
            entry = _check_exact_keys(entry_value, set(arms["FULL"]), f"bridge state closure {stream_id}.fixed_rule_replay.{timing}")
            rec = _check_exact_keys(recovery_value, {"recovered", "fresh_process", "journal_sha256", "process_instance_id"}, f"bridge state closure {stream_id}.fixed_rule_replay.{timing}.fresh_recovery")
            if entry["mount_role"] != "RAW_CONTROL" or rec["recovered"] is not True or rec["fresh_process"] is not True:
                raise BundleRefusal("fixed-rule replay closure evidence is not a fresh RAW_CONTROL recovery")
            key = (stream_id, "RAW_EQUAL_BUDGET")
            if timing == "pre":
                result[key] = {"pre": entry, "pre_recovery": rec}
            else:
                result[key] = {**result[key], "post": entry, "post_recovery": rec}
    expected = {(stream_id, arm) for stream_id in public_ids for arm in CLOSURE_ARMS}
    if set(result) != expected or any("post" not in item for item in result.values()):
        raise BundleRefusal("bridge state closure evidence does not cover exact public stream/arm support")
    return result


def _closure_plan_from_mounts(
    mounts: Sequence[Mapping[str, Any]], bridge_state_sha256: str
) -> dict[str, Any]:
    by_stream: dict[str, dict[str, dict[str, Any]]] = {}
    for mount in mounts:
        stream_id = str(mount["stream_id"])
        arm = str(mount["arm"])
        by_stream.setdefault(stream_id, {})[arm] = {
            "mount_id": mount["mount_id"],
            "mount_role": mount["mount_role"],
            "pre_evaluation_journal_sha256": mount["pre_evaluation_journal_sha256"],
            "post_evaluation_journal_sha256": mount["post_evaluation_journal_sha256"],
            "pre_evaluation_routing_payload_sha256": mount["pre_evaluation_routing_payload_sha256"],
            "post_evaluation_routing_payload_sha256": mount["post_evaluation_routing_payload_sha256"],
        }
    return {
        "schema_version": MOUNT_CLOSURE_PLAN_SCHEMA,
        "bridge_state_evidence_sha256": bridge_state_sha256,
        "streams": [
            {
                "stream_id": stream_id,
                "arms": {arm: by_stream[stream_id][arm] for arm in ARMS},
                "fixed_rule_replay": by_stream[stream_id]["RAW_EQUAL_BUDGET"],
            }
            for stream_id in sorted(by_stream)
        ],
    }


def _closure_expected_stream_support(stream: Mapping[str, Any]) -> dict[str, Any]:
    stream_id = _string(stream["stream_id"], "public stream ID for closure")
    route_ids = sorted((_string(route, "public route ID for closure") for route in stream["route_ids"]), key=_v2_text_key)
    stratum = f"stratum:{_sha_bytes(stream_id.encode('utf-8'))}"
    contexts = [
        {
            "context_key": context,
            "context_sha256": _sha_bytes(context.encode("utf-8")),
            "stratum": stratum,
        }
        for context in stream["context_keys"]
    ]
    contexts.sort(key=lambda item: (str(item["stratum"]), str(item["context_sha256"])))
    expected_derangement: dict[str, str] = {}
    by_stratum: dict[str, list[Mapping[str, Any]]] = {}
    for context in contexts:
        by_stratum.setdefault(str(context["stratum"]), []).append(context)
    for _, group in sorted(by_stratum.items(), key=lambda item: _v2_text_key(item[0])):
        if len(group) < 2:
            raise BundleRefusal("public closure stream cannot derive a fixed-point-free DNRD derangement")
        for index, receiver in enumerate(group):
            expected_derangement[str(receiver["context_key"])] = str(group[(index + 1) % len(group)]["context_key"])
    episodes: list[dict[str, Any]] = []
    training: list[dict[str, Any]] = []
    for phase in ("training", "heldout"):
        for episode in stream[phase]:
            row = {
                "episode_id": episode["episode_id"],
                "context_key": episode["context_key"],
                "phase": phase,
                "forced_route_id": episode["forced_route_id"] if phase == "training" else None,
            }
            episodes.append(row)
            if phase == "training":
                training.append(
                    {
                        "episode_id": episode["episode_id"],
                        "context_key": episode["context_key"],
                        "selected_route_id": episode["forced_route_id"],
                    }
                )
    return {
        "route_ids": route_ids,
        "contexts": contexts,
        "matched_derangement": expected_derangement,
        "episodes": episodes,
        "training": training,
    }


def _closure_registry(
    files: Mapping[str, bytes],
    *,
    mount: Mapping[str, Any],
    stream: Mapping[str, Any],
    scorer_sha256: str,
) -> Mapping[str, Any]:
    mount_id = str(mount["mount_id"])
    data = _closure_v2_object(files, f"registry/{mount_id}.json", f"bridge mount registry {mount_id}")
    expected_keys = {
        "schema_version", "mount_id", "mount_role", "source_mount_id", "source_state_sha256",
        "frozen_scorer_source_sha256", "stream_id", "route_ids", "contexts", "matched_derangement",
        "episodes", "training",
    }
    row = _check_exact_keys(data, expected_keys, f"bridge mount registry {mount_id}")
    if (
        row["schema_version"] != PROCESS_MOUNT_SCHEMA
        or row["mount_id"] != mount_id
        or row["mount_role"] != mount["mount_role"]
        or row["stream_id"] != mount["stream_id"]
        or row["frozen_scorer_source_sha256"] != scorer_sha256
    ):
        raise BundleRefusal("bridge mount registry identity is not bound to mount/source-scoring evidence")
    support = _closure_expected_stream_support(stream)
    if row["route_ids"] != support["route_ids"] or row["matched_derangement"] != support["matched_derangement"]:
        raise BundleRefusal("bridge mount registry route/derangement support differs from exact public stream")
    if row["episodes"] != support["episodes"] or row["training"] != support["training"]:
        raise BundleRefusal("bridge mount registry episode/training support differs from exact public stream")
    if row["contexts"] != support["contexts"]:
        raise BundleRefusal("bridge mount registry context bindings differ from exact public stream")
    # Structural checks above compare to public support; retain strict raw V2
    # primitive checks too so a type-coercive JSON projection cannot pass.
    if not V2_MOUNT_ID.fullmatch(_string(row["mount_id"], f"bridge mount registry {mount_id}.mount_id")):
        raise BundleRefusal("bridge mount registry mount ID is malformed")
    _sha(row["frozen_scorer_source_sha256"], f"bridge mount registry {mount_id}.frozen_scorer_source_sha256")
    for index, context in enumerate(row["contexts"]):
        item = _check_exact_keys(context, {"context_key", "context_sha256", "stratum"}, f"bridge mount registry {mount_id}.contexts[{index}]")
        _string(item["context_key"], f"bridge mount registry {mount_id}.contexts[{index}].context_key")
        _sha(item["context_sha256"], f"bridge mount registry {mount_id}.contexts[{index}].context_sha256")
        _v2_identifier(item["stratum"], f"bridge mount registry {mount_id}.contexts[{index}].stratum")
    return row


def _validate_closure_layout(
    files: Mapping[str, bytes], mounts: Sequence[Mapping[str, Any]]
) -> None:
    mount_ids = {str(mount["mount_id"]) for mount in mounts}
    static = {"root-config.json"}
    for mount in mounts:
        stream_id = str(mount["stream_id"])
        static.add(f"registry/{mount['mount_id']}.json")
        static.add(f"streams/{stream_id}.json")
        if mount["arm"] == "RAW_EQUAL_BUDGET":
            static.add(f"controls/{stream_id}-RAW_EQUAL_BUDGET.json")
        elif mount["arm"] == "BINDING_DERANGED_NUMERIC_PLACEBO":
            static.add(f"controls/{stream_id}-BINDING_DERANGED_NUMERIC_PLACEBO.json")
    for stream_index in range(4):
        stream_id = f"stream-{stream_index}"
        static.add(f"streams/{stream_id}.json")
        static.add(f"controls/{stream_id}-RAW_EQUAL_BUDGET.json")
        static.add(f"controls/{stream_id}-BINDING_DERANGED_NUMERIC_PLACEBO.json")
    if not static.issubset(files):
        raise BundleRefusal("bridge mount closure omits root/reservation/registry bytes")
    for path in files:
        if path in static:
            continue
        parts = Path(path).parts
        if len(parts) != 4 or parts[0] != "mounts" or parts[1] not in mount_ids:
            raise BundleRefusal(f"bridge mount closure has an unrecognized raw path: {path}")
        if parts[2] not in {"schema-bindings", "objects", "journal-objects", "journal-slots"}:
            raise BundleRefusal(f"bridge mount closure has an unrecognized raw storage domain: {path}")
        if not re.fullmatch(r"[0-9a-f]{64}", parts[3]):
            raise BundleRefusal(f"bridge mount closure content-addressed filename is malformed: {path}")
    for mount_id in mount_ids:
        prefix = f"mounts/{mount_id}/"
        if not any(path.startswith(prefix + "schema-bindings/") for path in files):
            raise BundleRefusal("bridge mount closure omits schema binding bytes")
        if not any(path.startswith(prefix + "objects/") for path in files):
            raise BundleRefusal("bridge mount closure omits content objects")
        if not any(path.startswith(prefix + "journal-objects/") for path in files):
            raise BundleRefusal("bridge mount closure omits journal objects")
        if not any(path.startswith(prefix + "journal-slots/") for path in files):
            raise BundleRefusal("bridge mount closure omits journal slots")


def _validate_closure_reservations(
    files: Mapping[str, bytes], public: Mapping[str, Any], scorer_sha256: str,
    mounts: Sequence[Mapping[str, Any]], registries: Mapping[str, Mapping[str, Any]],
) -> None:
    root_config = _closure_v2_object(files, "root-config.json", "bridge mount root config")
    root = _check_exact_keys(root_config, {"schema_version", "frozen_scorer_source_sha256"}, "bridge mount root config")
    if root["schema_version"] != PROCESS_ROOT_CONFIG_SCHEMA or root["frozen_scorer_source_sha256"] != scorer_sha256:
        raise BundleRefusal("bridge mount root config differs from frozen scorer source")
    streams = {str(stream["stream_id"]): stream for stream in public["streams"]}
    for stream_id, stream in streams.items():
        reservation = _closure_v2_object(files, f"streams/{stream_id}.json", f"bridge stream reservation {stream_id}")
        row = _check_exact_keys(reservation, {"schema_version", "stream_id", "public_stream_sha256"}, f"bridge stream reservation {stream_id}")
        if (
            row["schema_version"] != STREAM_RESERVATION_SCHEMA
            or row["stream_id"] != stream_id
            or row["public_stream_sha256"] != _v2_hash_object(stream, f"public stream reservation input {stream_id}")
        ):
            raise BundleRefusal("bridge stream reservation is not exact public stream evidence")
    by_stream_arm = {(str(mount["stream_id"]), str(mount["arm"])): mount for mount in mounts}
    for stream_id in streams:
        raw_mount = by_stream_arm[(stream_id, "RAW_EQUAL_BUDGET")]
        deranged_mount = by_stream_arm[(stream_id, "BINDING_DERANGED_NUMERIC_PLACEBO")]
        for arm, mount in (("RAW_EQUAL_BUDGET", raw_mount), ("BINDING_DERANGED_NUMERIC_PLACEBO", deranged_mount)):
            reservation = _closure_v2_object(files, f"controls/{stream_id}-{arm}.json", f"bridge control reservation {stream_id}/{arm}")
            row = _check_exact_keys(
                reservation,
                {"schema_version", "stream_id", "arm", "source_mount_id", "source_state_sha256", "target_payload_sha256"},
                f"bridge control reservation {stream_id}/{arm}",
            )
            registry = registries[str(mount["mount_id"])]
            if (
                row["schema_version"] != CONTROL_RESERVATION_SCHEMA
                or row["stream_id"] != stream_id
                or row["arm"] != arm
                or row["source_mount_id"] != registry["source_mount_id"]
                or row["source_state_sha256"] != registry["source_state_sha256"]
                or row["target_payload_sha256"] != mount["pre_evaluation_routing_payload_sha256"]
            ):
                raise BundleRefusal("bridge control reservation does not bind exact source/target routing state")
            _sha(row["target_payload_sha256"], f"bridge control reservation {stream_id}/{arm}.target_payload_sha256")


def _closure_object_store(files: Mapping[str, bytes], mount_id: str) -> dict[str, bytes]:
    prefix = f"mounts/{mount_id}/objects/"
    objects: dict[str, bytes] = {}
    for path, raw in files.items():
        if not path.startswith(prefix):
            continue
        digest = path.removeprefix(prefix)
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or _sha_bytes(raw) != digest:
            raise BundleRefusal(f"bridge mount {mount_id} content object filename/hash mismatch")
        objects[digest] = raw
    if not objects:
        raise BundleRefusal(f"bridge mount {mount_id} has no raw V2 content objects")
    return objects


def _v2_object_for_descriptor(
    objects: Mapping[str, bytes], descriptor: Mapping[str, Any], label: str, used: set[str]
) -> Mapping[str, Any]:
    digest = _sha(descriptor["sha256"], f"{label}.sha256")
    raw = objects.get(digest)
    if raw is None:
        raise BundleRefusal(f"{label} has no exact retained content object")
    if len(raw) != descriptor["byteLength"] or _sha_bytes(raw) != digest:
        raise BundleRefusal(f"{label} raw content object does not match its descriptor")
    used.add(digest)
    return _v2_object_bytes(raw, label)


def _v2_reference(value: object, label: str) -> Mapping[str, Any]:
    data = _check_exact_keys(value, {"referenceType", "role", "target"}, label)
    _v2_identifier(data["referenceType"], f"{label}.referenceType")
    _v2_identifier(data["role"], f"{label}.role")
    _v2_key(data["target"], f"{label}.target")
    return data


def _v2_atom(value: object, label: str) -> Mapping[str, Any]:
    atom = _check_exact_keys(
        value,
        {"_tag", "contractVersion", "key", "kind", "responsibilityOwner", "content", "provenance", "lifecycle", "references"},
        label,
    )
    key = _v2_key(atom["key"], f"{label}.key")
    if key["schemaVersion"] != V2_SCHEMA_VERSION or key["lineageId"] != V2_LINEAGE:
        raise BundleRefusal(f"{label} escapes the frozen DNRD schema/lineage")
    kind = _v2_identifier(atom["kind"], f"{label}.kind")
    owners = {
        "dnrd:trajectory": "owner:dnrd:trajectory",
        "dnrd:outcome": "owner:dnrd:outcome",
        "dnrd:credit": "owner:dnrd:credit",
        "dnrd:routing-disposition": V2_ROUTING_OWNER,
    }
    if atom["_tag"] != "CanonicalAtomV2" or atom["contractVersion"] != "hswm-canonical-atom/v2" or kind not in owners:
        raise BundleRefusal(f"{label} is not a frozen DNRD V2 atom")
    if atom["responsibilityOwner"] != owners[kind] or atom["lifecycle"] != "ADMITTED":
        raise BundleRefusal(f"{label} has an invalid schema-relative responsibility owner/lifecycle")
    _v2_descriptor(atom["content"], f"{label}.content", media_type=V2_DNRD_CONTENT_MEDIA_TYPE, minimum_bytes=1)
    provenance = _check_exact_keys(atom["provenance"], {"mode", "evidenceSha256", "sourceRef"}, f"{label}.provenance")
    if provenance["mode"] not in {"BOOTSTRAP", "OBSERVATION", "DERIVATION"}:
        raise BundleRefusal(f"{label}.provenance.mode is not a supported DNRD V2 mode")
    _sha(provenance["evidenceSha256"], f"{label}.provenance.evidenceSha256")
    if provenance["sourceRef"] is not None:
        _v2_key(provenance["sourceRef"], f"{label}.provenance.sourceRef")
    references = atom["references"]
    if type(references) is not list or len(references) > 256:
        raise BundleRefusal(f"{label}.references is not a bounded V2 reference list")
    seen: set[str] = set()
    for index, reference in enumerate(references):
        parsed = _v2_reference(reference, f"{label}.references[{index}]")
        identity = f"{parsed['referenceType']}|{parsed['role']}|{_v2_key_id(parsed['target'])}"
        if identity in seen:
            raise BundleRefusal(f"{label} repeats a typed V2 reference")
        seen.add(identity)
    return atom


def _v2_routing_payload(
    value: object, registry: Mapping[str, Any], label: str
) -> Mapping[str, Any]:
    payload = _check_exact_keys(value, {"schemaVersion", "contexts", "structuralStatus"}, label)
    if (
        payload["schemaVersion"] != "hswm-dnrd-routing-payload/v1"
        or payload["structuralStatus"]
        != "LOCAL_EXPERIMENTAL_ROUTING_PAYLOAD_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
        or type(payload["contexts"]) is not list
        or len(payload["contexts"]) != len(registry["contexts"])
    ):
        raise BundleRefusal(f"{label} is not a frozen DNRD routing payload")
    routes = registry["route_ids"]
    for index, (raw_context, expected_context) in enumerate(zip(payload["contexts"], registry["contexts"], strict=True)):
        context = _check_exact_keys(raw_context, {"contextSha256", "stratum", "routes"}, f"{label}.contexts[{index}]")
        if context["contextSha256"] != expected_context["context_sha256"] or context["stratum"] != expected_context["stratum"]:
            raise BundleRefusal(f"{label} context support/order differs from frozen registry")
        _sha(context["contextSha256"], f"{label}.contexts[{index}].contextSha256")
        _v2_identifier(context["stratum"], f"{label}.contexts[{index}].stratum")
        if type(context["routes"]) is not list or len(context["routes"]) != len(routes):
            raise BundleRefusal(f"{label} route support is malformed")
        for route_index, (raw_route, expected_route) in enumerate(zip(context["routes"], routes, strict=True)):
            route = _check_exact_keys(raw_route, {"routeId", "scoreMicros"}, f"{label}.contexts[{index}].routes[{route_index}]")
            if route["routeId"] != expected_route:
                raise BundleRefusal(f"{label} route order/support differs from frozen registry")
            _v2_identifier(route["routeId"], f"{label}.contexts[{index}].routes[{route_index}].routeId")
            _v2_integer(route["scoreMicros"], f"{label}.contexts[{index}].routes[{route_index}].scoreMicros", minimum=-100_000, maximum=100_000)
    return payload


def _v2_trace(value: object, label: str) -> Mapping[str, Any]:
    trace = _check_exact_keys(
        value,
        {
            "schemaVersion", "traceId", "episodeId", "routingPayloadSha256", "contextSha256", "stratum",
            "routeId", "preOutcomeScoreMicros", "requestSha256", "responseSha256", "status",
        },
        label,
    )
    if (
        trace["schemaVersion"] != "hswm-dnrd-eligibility-trace/v1"
        or trace["status"] != TRACE_STATUS
    ):
        raise BundleRefusal(f"{label} identity/status is not a frozen DNRD eligibility trace")
    for key in ("traceId", "routingPayloadSha256", "contextSha256", "requestSha256", "responseSha256"):
        _sha(trace[key], f"{label}.{key}")
    for key in ("episodeId", "stratum", "routeId"):
        _v2_identifier(trace[key], f"{label}.{key}")
    _v2_integer(trace["preOutcomeScoreMicros"], f"{label}.preOutcomeScoreMicros", minimum=-100_000, maximum=100_000)
    unsigned = {key: item for key, item in trace.items() if key != "traceId"}
    if trace["traceId"] != _v2_hash_object(unsigned, f"{label} unsigned trace"):
        raise BundleRefusal(f"{label}.traceId does not bind exact raw trace fields")
    return trace


def _v2_outcome(value: object, label: str, scorer_sha256: str) -> Mapping[str, Any]:
    outcome = _check_exact_keys(
        value,
        {
            "schemaVersion", "outcomeId", "traceId", "producerAddress", "scorerAddress", "scorerProvenanceAddress",
            "scorerSourceSha256", "outcomeScoreMicros", "scorerObservationSha256", "independence", "status",
        },
        label,
    )
    if (
        outcome["schemaVersion"] != "hswm-dnrd-outcome-observation/v1"
        or outcome["producerAddress"] != "principal:dnrd-producer"
        or outcome["scorerAddress"] != "principal:dnrd-scorer"
        or outcome["scorerProvenanceAddress"] != "repo:_research/dnrd/scorer.py"
        or outcome["scorerSourceSha256"] != scorer_sha256
        or outcome["independence"] != "DECLARED_ROLE_SEPARATION_NOT_INDEPENDENTLY_PROVEN"
        or outcome["status"] != "LOCAL_EXPERIMENTAL_OUTCOME_NOT_EXTERNAL_TRUTH_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
    ):
        raise BundleRefusal(f"{label} does not retain frozen local scorer/outcome provenance")
    for key in ("outcomeId", "traceId", "scorerSourceSha256", "scorerObservationSha256"):
        _sha(outcome[key], f"{label}.{key}")
    if outcome["outcomeScoreMicros"] not in {-1_000_000, 0, 1_000_000}:
        raise BundleRefusal(f"{label}.outcomeScoreMicros violates frozen reward support")
    unsigned = {key: item for key, item in outcome.items() if key != "outcomeId"}
    if outcome["outcomeId"] != _v2_hash_object(unsigned, f"{label} unsigned outcome"):
        raise BundleRefusal(f"{label}.outcomeId does not bind exact raw outcome fields")
    return outcome


def _v2_credit(value: object, label: str) -> Mapping[str, Any]:
    credit = _check_exact_keys(
        value,
        {
            "schemaVersion", "outcomeId", "traceId", "beforePayloadSha256", "afterPayloadSha256",
            "deltaMicros", "updatedRouteCount", "consumedOutcomeIds", "status",
        },
        label,
    )
    if (
        credit["schemaVersion"] != "hswm-dnrd-credit-receipt/v1"
        or credit["status"] != "LOCAL_EXPERIMENTAL_STRUCTURAL_CREDIT_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
        or credit["updatedRouteCount"] != 1
        or type(credit["consumedOutcomeIds"]) is not list
    ):
        raise BundleRefusal(f"{label} is not a frozen one-route DNRD credit receipt")
    for key in ("outcomeId", "traceId", "beforePayloadSha256", "afterPayloadSha256"):
        _sha(credit[key], f"{label}.{key}")
    _v2_integer(credit["deltaMicros"], f"{label}.deltaMicros", minimum=-100_000, maximum=100_000)
    previous = ""
    for index, outcome_id in enumerate(credit["consumedOutcomeIds"]):
        digest = _sha(outcome_id, f"{label}.consumedOutcomeIds[{index}]")
        if digest <= previous:
            raise BundleRefusal(f"{label}.consumedOutcomeIds must be strict sorted unique SHA-256 IDs")
        previous = digest
    return credit


def _v2_atom_payload(
    atom: Mapping[str, Any], objects: Mapping[str, bytes], label: str, used: set[str]
) -> Mapping[str, Any]:
    descriptor = _v2_descriptor(atom["content"], f"{label}.content", media_type=V2_DNRD_CONTENT_MEDIA_TYPE, minimum_bytes=1)
    return _v2_object_for_descriptor(objects, descriptor, f"{label}.content", used)


def _v2_journal_descriptor(value: object, label: str) -> Mapping[str, Any]:
    return _v2_descriptor(
        value, label, media_type=V2_JOURNAL_MEDIA_TYPE, minimum_bytes=1, maximum_bytes=V2_JOURNAL_MAX_BYTES
    )


def _v2_instant(value: object, label: str) -> str:
    instant = _string(value, label)
    if not V2_INSTANT.fullmatch(instant):
        raise BundleRefusal(f"{label} is not a canonical UTC millisecond instant")
    try:
        parsed = datetime.strptime(instant, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as error:
        raise BundleRefusal(f"{label} is not a real UTC instant") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" != instant:
        raise BundleRefusal(f"{label} is not a canonical UTC millisecond instant")
    return instant


def _v2_reference_record(reference_type: str, role: str, target: Mapping[str, Any]) -> dict[str, Any]:
    return {"referenceType": reference_type, "role": role, "target": dict(target)}


def _v2_provenance(
    atom: Mapping[str, Any], *, mode: str, evidence_sha256: str, source: Mapping[str, Any] | None, label: str
) -> None:
    expected = {"mode": mode, "evidenceSha256": evidence_sha256, "sourceRef": None if source is None else dict(source)}
    if atom["provenance"] != expected:
        raise BundleRefusal(f"{label} provenance does not retain the exact DNRD causal source")


def _v2_expected_credit_update(
    *,
    payload: Mapping[str, Any],
    trace: Mapping[str, Any],
    outcome: Mapping[str, Any],
    consumed_outcome_ids: Sequence[str],
    label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    before_hash = _v2_hash_object(payload, f"{label} prior routing payload")
    if trace["routingPayloadSha256"] != before_hash or outcome["traceId"] != trace["traceId"]:
        raise BundleRefusal(f"{label} outcome/trace does not bind the current raw routing payload")
    expected_context: Mapping[str, Any] | None = None
    for context in payload["contexts"]:
        if context["contextSha256"] == trace["contextSha256"] and context["stratum"] == trace["stratum"]:
            expected_context = context
            break
    if expected_context is None:
        raise BundleRefusal(f"{label} trace names an absent raw routing context")
    current_score: int | None = None
    for route in expected_context["routes"]:
        if route["routeId"] == trace["routeId"]:
            current_score = route["scoreMicros"]
            break
    if current_score is None or current_score != trace["preOutcomeScoreMicros"]:
        raise BundleRefusal(f"{label} trace pre-outcome score does not replay from raw routing payload")
    delta = int(outcome["outcomeScoreMicros"]) * 100_000 // 1_000_000
    contexts: list[dict[str, Any]] = []
    updated = 0
    for context in payload["contexts"]:
        routes: list[dict[str, Any]] = []
        for route in context["routes"]:
            next_score = route["scoreMicros"]
            if context is expected_context and route["routeId"] == trace["routeId"]:
                next_score = max(-100_000, min(100_000, int(next_score) + delta))
                updated += 1
            routes.append({"routeId": route["routeId"], "scoreMicros": next_score})
        contexts.append({"contextSha256": context["contextSha256"], "stratum": context["stratum"], "routes": routes})
    if updated != 1:
        raise BundleRefusal(f"{label} raw credit update did not affect exactly one route")
    next_payload = {
        "schemaVersion": payload["schemaVersion"],
        "contexts": contexts,
        "structuralStatus": payload["structuralStatus"],
    }
    after_hash = _v2_hash_object(next_payload, f"{label} successor routing payload")
    outcome_id = str(outcome["outcomeId"])
    if outcome_id in consumed_outcome_ids:
        raise BundleRefusal(f"{label} attempts to consume one DNRD outcome twice")
    expected_credit = {
        "schemaVersion": "hswm-dnrd-credit-receipt/v1",
        "outcomeId": outcome_id,
        "traceId": trace["traceId"],
        "beforePayloadSha256": before_hash,
        "afterPayloadSha256": after_hash,
        "deltaMicros": delta,
        "updatedRouteCount": 1,
        "consumedOutcomeIds": sorted([*consumed_outcome_ids, outcome_id], key=_v2_text_key),
        "status": "LOCAL_EXPERIMENTAL_STRUCTURAL_CREDIT_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING",
    }
    return next_payload, expected_credit


def _v2_commit_writes(
    record: Mapping[str, Any], objects: Mapping[str, bytes], label: str, used: set[str]
) -> tuple[list[Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    raw_bindings = record["writeBindings"]
    if type(raw_bindings) is not list or not 1 <= len(raw_bindings) <= 64:
        raise BundleRefusal(f"{label}.writeBindings is not a bounded nonempty V2 binding list")
    atoms: list[Mapping[str, Any]] = []
    payloads: dict[str, Mapping[str, Any]] = {}
    previous_id = ""
    for index, raw_binding in enumerate(raw_bindings):
        binding = _check_exact_keys(raw_binding, {"key", "payload", "envelope"}, f"{label}.writeBindings[{index}]")
        key = _v2_key(binding["key"], f"{label}.writeBindings[{index}].key")
        key_id = _v2_key_id(key)
        if key_id <= previous_id:
            raise BundleRefusal(f"{label}.writeBindings are not in strict canonical key order")
        previous_id = key_id
        payload_descriptor = _v2_descriptor(
            binding["payload"], f"{label}.writeBindings[{index}].payload", media_type=V2_DNRD_CONTENT_MEDIA_TYPE, minimum_bytes=1
        )
        envelope_descriptor = _v2_descriptor(
            binding["envelope"], f"{label}.writeBindings[{index}].envelope", media_type=V2_ATOM_ENVELOPE_MEDIA_TYPE, minimum_bytes=1
        )
        envelope = _v2_object_for_descriptor(objects, envelope_descriptor, f"{label}.writeBindings[{index}].envelope", used)
        atom = _v2_atom(envelope, f"{label}.writeBindings[{index}].envelope atom")
        raw_envelope = objects[str(envelope_descriptor["sha256"])]
        if (
            len(raw_envelope) != envelope_descriptor["byteLength"]
            or _sha_bytes(raw_envelope) != envelope_descriptor["sha256"]
            or not _v2_same_key(key, atom["key"])
            or atom["content"] != payload_descriptor
        ):
            raise BundleRefusal(f"{label}.writeBindings[{index}] does not bijectively bind raw atom envelope/content")
        if key_id in payloads:
            raise BundleRefusal(f"{label}.writeBindings repeat one canonical atom key")
        payloads[key_id] = _v2_atom_payload(atom, objects, f"{label}.writeBindings[{index}].atom", used)
        atoms.append(atom)
    return atoms, payloads


def _v2_validate_receipt_and_provenance(
    *,
    record: Mapping[str, Any],
    previous_revision: int,
    atoms: Sequence[Mapping[str, Any]],
    original_writes: Sequence[Mapping[str, Any]],
    original_reads: Sequence[Mapping[str, Any]],
    objects: Mapping[str, bytes],
    used: set[str],
    label: str,
) -> None:
    receipt = _check_exact_keys(
        record["receipt"],
        {
            "_tag", "contractVersion", "transitionId", "schemaVersion", "previousStateRevision",
            "nextStateRevision", "readSet", "writeSet", "traceRef", "guard", "actorClaim",
            "authorizationRef", "scope", "decidedAt", "decision", "provenanceSha256",
        },
        f"{label}.receipt",
    )
    decided_at = _v2_instant(receipt["decidedAt"], f"{label}.receipt.decidedAt")
    if (
        receipt["_tag"] != "CanonicalAtomV2EffectReceipt"
        or receipt["contractVersion"] != "hswm-canonical-effect-receipt/v2"
        or receipt["schemaVersion"] != V2_SCHEMA_VERSION
        or receipt["previousStateRevision"] != previous_revision
        or receipt["nextStateRevision"] != previous_revision + 1
        or receipt["traceRef"] is not None
        or receipt["actorClaim"] != V2_ACTOR
        or receipt["authorizationRef"] != V2_AUTHORIZATION
        or receipt["scope"] != V2_SCOPE
        or receipt["decision"] != "ACCEPTED"
    ):
        raise BundleRefusal(f"{label}.receipt does not describe the exact local non-authorizing V2 transition")
    expected_guard = {
        "schema": "PASSED", "ownerTotality": "PASSED", "references": "PASSED", "revision": "PASSED",
        "permission": "REFERENCE_GRANT_MATCHED_NOT_CANONICAL_PERMIT",
    }
    if receipt["guard"] != expected_guard:
        raise BundleRefusal(f"{label}.receipt guard is not the deterministic V2 guard receipt")
    raw_read_set = receipt["readSet"]
    raw_write_set = receipt["writeSet"]
    if type(raw_read_set) is not list or type(raw_write_set) is not list:
        raise BundleRefusal(f"{label}.receipt read/write sets are malformed")
    read_set = [_v2_key(item, f"{label}.receipt.readSet[{index}]") for index, item in enumerate(raw_read_set)]
    write_set = [_v2_key(item, f"{label}.receipt.writeSet[{index}]") for index, item in enumerate(raw_write_set)]
    expected_read_set = _v2_sorted_keys(list(original_reads))
    expected_write_set = _v2_sorted_keys([atom["key"] for atom in atoms])
    if read_set != expected_read_set or write_set != expected_write_set:
        raise BundleRefusal(f"{label}.receipt read/write sets do not replay from exact causal transition inputs")
    transition_id = "dnrd:transition:" + str(previous_revision) + ":" + ":".join(
        str(atom["key"]["atomUid"]) for atom in original_writes
    )
    if receipt["transitionId"] != transition_id:
        raise BundleRefusal(f"{label}.receipt transition ID does not bind exact write order")
    provenance_sha = _sha(receipt["provenanceSha256"], f"{label}.receipt.provenanceSha256")
    raw_provenance = objects.get(provenance_sha)
    if raw_provenance is None or _sha_bytes(raw_provenance) != provenance_sha:
        raise BundleRefusal(f"{label}.receipt has no raw immutable provenance preimage object")
    used.add(provenance_sha)
    provenance = _v2_object_bytes(raw_provenance, f"{label}.receipt provenance preimage")
    expected_provenance = {
        "contract_version": "hswm-dnrd-local-transition-provenance/v1",
        "clock_trust": "UNATTESTED_OS_CLOCK_ORDER_ESTABLISHED_BY_STATE_REVISION_ONLY",
        "decided_at": decided_at,
        "expected_state_revision": previous_revision,
        "read_set": [dict(key) for key in original_reads],
        "trace_ref": None,
        "writes": [
            {
                "key": dict(atom["key"]),
                "kind": atom["kind"],
                "responsibility_owner": atom["responsibilityOwner"],
                "content": dict(atom["content"]),
                "atom_provenance": dict(atom["provenance"]),
                "lifecycle": atom["lifecycle"],
                "references": [dict(reference) for reference in atom["references"]],
            }
            for atom in original_writes
        ],
    }
    if provenance != expected_provenance:
        raise BundleRefusal(f"{label}.receipt provenance preimage does not reproduce exact raw transition causality")


def _replay_v2_mount(
    files: Mapping[str, bytes], *, mount: Mapping[str, Any], registry: Mapping[str, Any], scorer_sha256: str
) -> dict[str, Any]:
    """Replay one raw local V2 mount without importing the TS adapter."""
    mount_id = str(mount["mount_id"])
    prefix = f"mounts/{mount_id}/"
    objects = _closure_object_store(files, mount_id)
    used_objects: set[str] = set()

    binding_paths = sorted(path for path in files if path.startswith(prefix + "schema-bindings/"))
    binding_name = _v2_hash_object({"schemaVersion": V2_SCHEMA_VERSION}, f"bridge mount {mount_id} schema binding name")
    if binding_paths != [prefix + "schema-bindings/" + binding_name]:
        raise BundleRefusal(f"bridge mount {mount_id} does not retain one exact schema-binding file")
    binding = _closure_v2_object(files, binding_paths[0], f"bridge mount {mount_id} schema binding")
    expected_schema_descriptor, expected_schema_bytes = _v2_expected_schema_descriptor()
    if binding != {"schemaVersion": V2_SCHEMA_VERSION, "content": expected_schema_descriptor}:
        raise BundleRefusal(f"bridge mount {mount_id} schema binding differs from frozen DNRD V2 schema")
    schema_object = _v2_object_for_descriptor(objects, expected_schema_descriptor, f"bridge mount {mount_id} schema content", used_objects)
    if schema_object != _v2_expected_dnrd_schema() or objects[str(expected_schema_descriptor["sha256"])] != expected_schema_bytes:
        raise BundleRefusal(f"bridge mount {mount_id} raw schema content is not the frozen DNRD schema bytes")
    schema_binding = {"schemaVersion": V2_SCHEMA_VERSION, "content": expected_schema_descriptor}
    schema_sha = str(expected_schema_descriptor["sha256"])

    journal_object_prefix = prefix + "journal-objects/"
    journal_slot_prefix = prefix + "journal-slots/"
    journal_objects: dict[str, bytes] = {}
    slots: dict[str, bytes] = {}
    for path, raw in files.items():
        if path.startswith(journal_object_prefix):
            digest = path.removeprefix(journal_object_prefix)
            if len(raw) > V2_JOURNAL_MAX_BYTES or _sha_bytes(raw) != digest:
                raise BundleRefusal(f"bridge mount {mount_id} journal object filename/hash/size mismatch")
            journal_objects[digest] = raw
        elif path.startswith(journal_slot_prefix):
            name = path.removeprefix(journal_slot_prefix)
            if len(raw) > V2_JOURNAL_MAX_BYTES or not re.fullmatch(r"[0-9a-f]{64}", name):
                raise BundleRefusal(f"bridge mount {mount_id} journal slot is malformed or unbounded")
            slots[name] = raw
    if not slots or not journal_objects:
        raise BundleRefusal(f"bridge mount {mount_id} has no replayable journal records")
    expected_slot_names = {
        _v2_slot_name(V2_LINEAGE, schema_sha, revision)
        for revision in range(len(slots))
    }
    if set(slots) != expected_slot_names:
        raise BundleRefusal(f"bridge mount {mount_id} journal slots are not one contiguous state-revision prefix")

    current_atoms: dict[str, Mapping[str, Any]] = {}
    current_payloads: dict[str, Mapping[str, Any]] = {}
    accepted_transition_ids: list[str] = []
    head_descriptor: Mapping[str, Any] | None = None
    head_info: dict[str, dict[str, Any]] = {}
    journal_hashes: set[str] = set()
    record_digests: list[str] = []

    for revision in range(len(slots)):
        slot_name = _v2_slot_name(V2_LINEAGE, schema_sha, revision)
        raw_record = slots[slot_name]
        record_digest = _sha_bytes(raw_record)
        raw_object = journal_objects.get(record_digest)
        if raw_object is None or raw_object != raw_record:
            raise BundleRefusal(f"bridge mount {mount_id} journal slot/object bytes are not exact equals")
        journal_hashes.add(record_digest)
        record_digests.append(record_digest)
        record = _v2_object_bytes(raw_record, f"bridge mount {mount_id} journal revision {revision}")
        descriptor = {
            "mediaType": V2_JOURNAL_MEDIA_TYPE,
            "byteLength": len(raw_record),
            "sha256": record_digest,
        }
        if revision == 0:
            genesis = _check_exact_keys(
                record,
                {
                    "_tag", "contractVersion", "encoding", "journalLineageId", "schema", "stateRevision",
                    "bootstrapClosed", "predecessor", "resultingStateSha256",
                },
                f"bridge mount {mount_id} journal genesis",
            )
            initial = {
                "schemaVersion": V2_SCHEMA_VERSION,
                "revision": 0,
                "bootstrapClosed": False,
                "atoms": [],
                "acceptedTransitionIds": [],
            }
            if (
                genesis["_tag"] != "CanonicalAtomV2StateJournalGenesis"
                or genesis["contractVersion"] != V2_JOURNAL_CONTRACT
                or genesis["encoding"] != V2_JSON_SCHEMA
                or genesis["journalLineageId"] != V2_LINEAGE
                or genesis["schema"] != schema_binding
                or genesis["stateRevision"] != 0
                or genesis["bootstrapClosed"] is not False
                or genesis["predecessor"] is not None
                or genesis["resultingStateSha256"] != _v2_hash_object(initial, f"bridge mount {mount_id} initial state")
            ):
                raise BundleRefusal(f"bridge mount {mount_id} genesis does not reproduce frozen V2 state SHA")
            head_descriptor = descriptor
            continue

        commit = _check_exact_keys(
            record,
            {
                "_tag", "contractVersion", "encoding", "journalLineageId", "schema", "stateRevision",
                "predecessor", "receipt", "writeBindings", "previousStateSha256", "resultingStateSha256", "durability",
            },
            f"bridge mount {mount_id} journal revision {revision}",
        )
        state_before = {
            "schemaVersion": V2_SCHEMA_VERSION,
            "revision": revision - 1,
            "bootstrapClosed": revision - 1 > 0,
            "atoms": [current_atoms[key] for key in sorted(current_atoms, key=lambda item: _v2_key_sort(current_atoms[item]["key"]))],
            "acceptedTransitionIds": accepted_transition_ids,
        }
        before_hash = _v2_hash_object(state_before, f"bridge mount {mount_id} state before revision {revision}")
        if (
            commit["_tag"] != "CanonicalAtomV2StateJournalCommit"
            or commit["contractVersion"] != V2_JOURNAL_CONTRACT
            or commit["encoding"] != V2_JSON_SCHEMA
            or commit["journalLineageId"] != V2_LINEAGE
            or commit["schema"] != schema_binding
            or commit["stateRevision"] != revision
            or commit["predecessor"] != head_descriptor
            or commit["previousStateSha256"] != before_hash
            or commit["durability"] != "LOCAL_PREDECESSOR_BOUND_JOURNAL_V1_NOT_CANONICAL_PERMIT_NOT_LEARNING"
        ):
            raise BundleRefusal(f"bridge mount {mount_id} journal predecessor/schema/state binding fails at revision {revision}")
        _v2_journal_descriptor(commit["predecessor"], f"bridge mount {mount_id} predecessor {revision}")
        atoms, written_payloads = _v2_commit_writes(
            commit, objects, f"bridge mount {mount_id} journal revision {revision}", used_objects
        )
        ids = [_v2_key_id(atom["key"]) for atom in atoms]
        if len(set(ids)) != len(ids) or any(key in current_atoms for key in ids):
            raise BundleRefusal(f"bridge mount {mount_id} writes duplicate/overwrite immutable canonical atoms")
        for atom in atoms:
            if atom["key"]["schemaVersion"] != V2_SCHEMA_VERSION or atom["key"]["lineageId"] != V2_LINEAGE:
                raise BundleRefusal(f"bridge mount {mount_id} writes an atom outside frozen schema/lineage")

        routing_atoms = sorted(
            (atom for atom in current_atoms.values() if atom["kind"] == "dnrd:routing-disposition"),
            key=lambda atom: int(atom["key"]["revisionId"]),
        )
        latest_routing = routing_atoms[-1] if routing_atoms else None
        kinds = {str(atom["kind"]) for atom in atoms}
        original_writes: list[Mapping[str, Any]]
        original_reads: list[Mapping[str, Any]]
        if kinds == {"dnrd:routing-disposition"} and len(atoms) == 1:
            routing = atoms[0]
            payload = _v2_routing_payload(written_payloads[ids[0]], registry, f"bridge mount {mount_id} bootstrap routing payload")
            if (
                latest_routing is not None
                or routing["key"]["atomUid"] != "dnrd:routing"
                or routing["key"]["revisionId"] != 0
                or routing["references"] != []
                or routing["content"]["sha256"] != _v2_hash_object(payload, f"bridge mount {mount_id} bootstrap payload")
            ):
                raise BundleRefusal(f"bridge mount {mount_id} bootstrap routing transition is invalid")
            _v2_provenance(routing, mode="BOOTSTRAP", evidence_sha256=str(routing["content"]["sha256"]), source=None, label=f"bridge mount {mount_id} bootstrap routing")
            original_writes, original_reads = [routing], []
        elif kinds == {"dnrd:trajectory"} and len(atoms) == 1:
            if latest_routing is None:
                raise BundleRefusal(f"bridge mount {mount_id} trajectory has no prior routing disposition")
            trajectory = atoms[0]
            trace = _v2_trace(written_payloads[ids[0]], f"bridge mount {mount_id} trajectory trace")
            routing_payload = current_payloads[_v2_key_id(latest_routing["key"])]
            _v2_routing_payload(routing_payload, registry, f"bridge mount {mount_id} trajectory prior routing payload")
            if (
                trajectory["key"]["atomUid"] != "dnrd:trace:" + str(trace["traceId"])
                or trajectory["key"]["revisionId"] != 0
                or trajectory["references"] != []
                or trace["routingPayloadSha256"] != latest_routing["content"]["sha256"]
            ):
                raise BundleRefusal(f"bridge mount {mount_id} trajectory does not bind exact prior routing state")
            _v2_provenance(
                trajectory, mode="OBSERVATION", evidence_sha256=str(trace["responseSha256"]), source=latest_routing["key"],
                label=f"bridge mount {mount_id} trajectory",
            )
            original_writes, original_reads = [trajectory], [latest_routing["key"]]
        elif kinds == {"dnrd:outcome", "dnrd:credit", "dnrd:routing-disposition"} and len(atoms) == 3:
            if latest_routing is None:
                raise BundleRefusal(f"bridge mount {mount_id} credit transition has no prior routing disposition")
            outcome_atom = next(atom for atom in atoms if atom["kind"] == "dnrd:outcome")
            credit_atom = next(atom for atom in atoms if atom["kind"] == "dnrd:credit")
            routing = next(atom for atom in atoms if atom["kind"] == "dnrd:routing-disposition")
            outcome = _v2_outcome(
                written_payloads[_v2_key_id(outcome_atom["key"])], f"bridge mount {mount_id} outcome", scorer_sha256
            )
            credit = _v2_credit(written_payloads[_v2_key_id(credit_atom["key"])], f"bridge mount {mount_id} credit")
            successor = _v2_routing_payload(
                written_payloads[_v2_key_id(routing["key"])], registry, f"bridge mount {mount_id} successor routing payload"
            )
            trace_key_id = _v2_key_id({"schemaVersion": V2_SCHEMA_VERSION, "lineageId": V2_LINEAGE, "atomUid": "dnrd:trace:" + str(outcome["traceId"]), "revisionId": 0})
            trace_atom = current_atoms.get(trace_key_id)
            if trace_atom is None or trace_atom["kind"] != "dnrd:trajectory":
                raise BundleRefusal(f"bridge mount {mount_id} outcome lacks its exact sealed trajectory atom")
            trace = current_payloads[trace_key_id]
            _v2_trace(trace, f"bridge mount {mount_id} credited trace")
            expected_outcome_ref = [_v2_reference_record("dnrd:reference", "trajectory", trace_atom["key"])]
            expected_credit_refs = [
                _v2_reference_record("dnrd:reference", "trajectory", trace_atom["key"]),
                _v2_reference_record("dnrd:reference", "outcome", outcome_atom["key"]),
            ]
            expected_routing_refs = [
                _v2_reference_record("dnrd:reference", "credit", credit_atom["key"]),
                _v2_reference_record("hswm:reference:supersedes", "hswm:role:predecessor", latest_routing["key"]),
            ]
            if (
                outcome_atom["key"]["atomUid"] != "dnrd:outcome:" + str(outcome["outcomeId"])
                or credit_atom["key"]["atomUid"] != "dnrd:credit:" + str(outcome["outcomeId"])
                or outcome_atom["key"]["revisionId"] != 0
                or credit_atom["key"]["revisionId"] != 0
                or routing["key"]["atomUid"] != "dnrd:routing"
                or routing["key"]["revisionId"] != latest_routing["key"]["revisionId"] + 1
                or outcome_atom["references"] != expected_outcome_ref
                or credit_atom["references"] != expected_credit_refs
                or routing["references"] != expected_routing_refs
            ):
                raise BundleRefusal(f"bridge mount {mount_id} outcome/credit/routing typed-reference chain is invalid")
            _v2_provenance(outcome_atom, mode="DERIVATION", evidence_sha256=str(outcome["scorerObservationSha256"]), source=trace_atom["key"], label=f"bridge mount {mount_id} outcome")
            _v2_provenance(credit_atom, mode="DERIVATION", evidence_sha256=str(credit["afterPayloadSha256"]), source=outcome_atom["key"], label=f"bridge mount {mount_id} credit")
            _v2_provenance(routing, mode="DERIVATION", evidence_sha256=str(credit["afterPayloadSha256"]), source=credit_atom["key"], label=f"bridge mount {mount_id} routing successor")
            prior_outcomes = sorted(
                (
                    str(current_payloads[_v2_key_id(atom["key"])]["outcomeId"])
                    for atom in current_atoms.values() if atom["kind"] == "dnrd:outcome"
                ),
                key=_v2_text_key,
            )
            expected_payload, expected_credit = _v2_expected_credit_update(
                payload=current_payloads[_v2_key_id(latest_routing["key"])], trace=trace, outcome=outcome,
                consumed_outcome_ids=prior_outcomes, label=f"bridge mount {mount_id} credit update",
            )
            if credit != expected_credit or successor != expected_payload or routing["content"]["sha256"] != expected_credit["afterPayloadSha256"]:
                raise BundleRefusal(f"bridge mount {mount_id} credit/routing payload does not replay exact scorer-bound update")
            original_writes, original_reads = [outcome_atom, credit_atom, routing], [trace_atom["key"], latest_routing["key"]]
        else:
            raise BundleRefusal(f"bridge mount {mount_id} journal has an unsupported non-DNRD transaction shape")

        _v2_validate_receipt_and_provenance(
            record=commit, previous_revision=revision - 1, atoms=atoms, original_writes=original_writes,
            original_reads=original_reads, objects=objects, used=used_objects,
            label=f"bridge mount {mount_id} journal revision {revision}",
        )
        receipt = commit["receipt"]
        transition_id = str(receipt["transitionId"])
        if transition_id in accepted_transition_ids:
            raise BundleRefusal(f"bridge mount {mount_id} journal repeats an accepted transition ID")
        current_atoms.update({key: atom for key, atom in zip(ids, atoms, strict=True)})
        current_payloads.update(written_payloads)
        accepted_transition_ids.append(transition_id)
        state_after = {
            "schemaVersion": V2_SCHEMA_VERSION,
            "revision": revision,
            "bootstrapClosed": True,
            "atoms": [current_atoms[key] for key in sorted(current_atoms, key=lambda item: _v2_key_sort(current_atoms[item]["key"]))],
            "acceptedTransitionIds": accepted_transition_ids,
        }
        if commit["resultingStateSha256"] != _v2_hash_object(state_after, f"bridge mount {mount_id} state after revision {revision}"):
            raise BundleRefusal(f"bridge mount {mount_id} resulting state SHA does not replay raw V2 journal")
        head_descriptor = descriptor
        current_routing = max(
            (atom for atom in current_atoms.values() if atom["kind"] == "dnrd:routing-disposition"),
            key=lambda atom: int(atom["key"]["revisionId"]),
            default=None,
        )
        if current_routing is not None:
            head_info[record_digest] = {
                "revision": revision,
                "routing_payload_sha256": current_routing["content"]["sha256"],
                "state_sha256": commit["resultingStateSha256"],
            }

    if set(journal_objects) != journal_hashes:
        raise BundleRefusal(f"bridge mount {mount_id} journal objects are not exactly the slot-addressed record set")
    if set(objects) != used_objects:
        raise BundleRefusal(f"bridge mount {mount_id} has unreferenced or missing raw content objects")
    if head_descriptor is None or not current_atoms:
        raise BundleRefusal(f"bridge mount {mount_id} replay did not reach a durable routing state")
    routing_atoms = sorted(
        (atom for atom in current_atoms.values() if atom["kind"] == "dnrd:routing-disposition"),
        key=lambda atom: int(atom["key"]["revisionId"]),
    )
    if not routing_atoms or [atom["key"]["revisionId"] for atom in routing_atoms] != list(range(len(routing_atoms))):
        raise BundleRefusal(f"bridge mount {mount_id} routing dispositions are not one contiguous revision chain")
    return {
        "heads": head_info,
        "atoms": current_atoms,
        "payloads": current_payloads,
        "objects": objects,
        "routing_atoms": routing_atoms,
        "final_revision": len(slots) - 1,
        "record_digests": record_digests,
    }


def _require_full_w0_bootstrap_prefix(
    w0_replay: Mapping[str, Any], full_replay: Mapping[str, Any], *, stream_id: str
) -> None:
    """Bind FULL's durable bootstrap to the separately retained W0 mount.

    The registry's ``source_state_sha256`` is metadata.  It cannot by itself
    demonstrate that the copied FULL mount actually began from the W0 bytes.
    Both raw closures must therefore retain the exact genesis and revision-one
    bootstrap journal records, and replay those records to the same routing
    payload/state objects.  This comparison is intentionally limited to the
    W0→FULL initialization prefix; RAW and DERANGED are separately materialized
    control mounts and are not claimed to share that byte prefix.
    """
    w0_records = w0_replay.get("record_digests")
    full_records = full_replay.get("record_digests")
    if (
        type(w0_records) is not list
        or type(full_records) is not list
        or len(w0_records) < 2
        or len(full_records) < 2
        or w0_records[:2] != full_records[:2]
    ):
        raise BundleRefusal(
            f"FULL/W0 raw closure lacks an exact shared genesis/bootstrap journal prefix for {stream_id}"
        )
    bootstrap_digest = str(w0_records[1])
    w0_head = w0_replay.get("heads", {}).get(bootstrap_digest)
    full_head = full_replay.get("heads", {}).get(bootstrap_digest)
    if (
        type(w0_head) is not dict
        or type(full_head) is not dict
        or w0_head != full_head
        or w0_head.get("revision") != 1
    ):
        raise BundleRefusal(f"FULL/W0 bootstrap journal head does not replay identically for {stream_id}")
    routing_sha = w0_head.get("routing_payload_sha256")
    if (
        not isinstance(routing_sha, str)
        or w0_replay.get("objects", {}).get(routing_sha)
        != full_replay.get("objects", {}).get(routing_sha)
    ):
        raise BundleRefusal(f"FULL/W0 bootstrap routing payload bytes differ for {stream_id}")


def _v2_trace_wire(trace: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    context_by_sha = {item["context_sha256"]: item for item in registry["contexts"]}
    context = context_by_sha.get(trace["contextSha256"])
    if context is None:
        raise BundleRefusal("raw V2 trace lacks a registered raw context binding")
    return {
        "trace_id": trace["traceId"],
        "episode_id": trace["episodeId"],
        "context_key": context["context_key"],
        "context_sha256": trace["contextSha256"],
        "stratum": trace["stratum"],
        "selected_route_id": trace["routeId"],
        "pre_outcome_score_micros": trace["preOutcomeScoreMicros"],
        "routing_payload_sha256": trace["routingPayloadSha256"],
        "request_sha256": trace["requestSha256"],
        "response_sha256": trace["responseSha256"],
        "status": trace["status"],
    }


def _validate_bridge_mount_closure(
    root: Path,
    *,
    closure: Mapping[str, Any],
    closure_bytes: bytes,
    candidate: Mapping[str, Any],
    state_evidence: Mapping[str, Any],
    public: Mapping[str, Any],
    runner_events: Sequence[Mapping[str, Any]],
    training_canaries: frozenset[str],
) -> None:
    """Independently replay the bounded raw V2 causal spine.

    This is intentionally narrower than a generic HSWM interpreter.  It
    verifies the DNRD schema, all 16 mounts, content-addressed V2 journal,
    source/credit/routing chain, and the retained runner boundary.  A copied
    candidate boolean cannot stand in for any of these raw bytes.
    """
    data = _check_exact_keys(
        closure,
        {"schema_version", "layout", "bridge_state_evidence_sha256", "closure_plan_sha256", "mounts", "files", "receipt_sha256"},
        "bridge mount closure",
    )
    if data["schema_version"] != MOUNT_CLOSURE_SCHEMA or data["layout"] != MOUNT_CLOSURE_LAYOUT:
        raise BundleRefusal("bridge mount closure schema/layout mismatch")
    _bundle_sha_receipt(data, "bridge mount closure")
    if candidate["bindings"]["bridge_mount_closure_sha256"] != _sha_bytes(closure_bytes):
        raise BundleRefusal("candidate bridge-mount-closure binding does not match retained manifest bytes")
    state_sha = _sha(data["bridge_state_evidence_sha256"], "bridge mount closure.bridge_state_evidence_sha256")
    if state_sha != candidate["bindings"]["bridge_state_evidence_sha256"]:
        raise BundleRefusal("bridge mount closure does not bind the same raw bridge-state evidence bytes as candidate")
    mounts_raw = data["mounts"]
    if type(mounts_raw) is not list or len(mounts_raw) != 16:
        raise BundleRefusal("bridge mount closure must retain exactly 16 raw evidence mounts")
    mounts: list[Mapping[str, Any]] = []
    previous: tuple[str, str] | None = None
    mount_ids: set[str] = set()
    public_streams = {str(stream["stream_id"]): stream for stream in public["streams"]}
    expected_pairs = {(stream_id, arm) for stream_id in public_streams for arm in CLOSURE_ARMS}
    seen_pairs: set[tuple[str, str]] = set()
    for index, raw_mount in enumerate(mounts_raw):
        mount = _check_exact_keys(
            raw_mount,
            {
                "stream_id", "arm", "mount_id", "mount_role", "pre_evaluation_journal_sha256",
                "post_evaluation_journal_sha256", "pre_evaluation_routing_payload_sha256",
                "post_evaluation_routing_payload_sha256",
            },
            f"bridge mount closure.mounts[{index}]",
        )
        stream_id = _string(mount["stream_id"], f"bridge mount closure.mounts[{index}].stream_id")
        arm = _string(mount["arm"], f"bridge mount closure.mounts[{index}].arm")
        pair = (stream_id, arm)
        if pair not in expected_pairs or pair in seen_pairs or (previous is not None and pair <= previous):
            raise BundleRefusal("bridge mount closure mount coverage/order is not exact public stream/arm support")
        previous = pair
        seen_pairs.add(pair)
        mount_id = _string(mount["mount_id"], f"bridge mount closure.mounts[{index}].mount_id")
        if not V2_MOUNT_ID.fullmatch(mount_id) or mount_id in mount_ids or mount["mount_role"] != CLOSURE_MOUNT_ROLES[arm]:
            raise BundleRefusal("bridge mount closure does not retain distinct raw mount IDs and expected immutable roles")
        mount_ids.add(mount_id)
        for key in (
            "pre_evaluation_journal_sha256", "post_evaluation_journal_sha256",
            "pre_evaluation_routing_payload_sha256", "post_evaluation_routing_payload_sha256",
        ):
            _sha(mount[key], f"bridge mount closure.mounts[{index}].{key}")
        mounts.append(mount)
    if seen_pairs != expected_pairs:
        raise BundleRefusal("bridge mount closure does not retain all exact 16 stream/arm mounts")
    if data["closure_plan_sha256"] != _canonical_hash(_closure_plan_from_mounts(mounts, state_sha)):
        raise BundleRefusal("bridge mount closure plan hash does not rederive from exact retained mounts/state evidence")

    files = _closure_files(root, data)
    # This is intentionally ahead of the layout/replay checks: a retained
    # object which is hash-valid but semantically unreferenced still belongs to
    # the authoritative evidence universe and must not carry a training-only
    # marker into the heldout/durable closure.
    _reject_training_canary_in_raw_closure(files, training_canaries)
    _validate_closure_layout(files, mounts)
    evidence = _closure_state_evidence_map(state_evidence, public)
    by_pair = {(str(mount["stream_id"]), str(mount["arm"])): mount for mount in mounts}
    for pair, mount in by_pair.items():
        observation = evidence[pair]
        pre, post = observation["pre"], observation["post"]
        pre_rec, post_rec = observation["pre_recovery"], observation["post_recovery"]
        if (
            mount["mount_id"] != pre["mount_id"]
            or mount["mount_id"] != post["mount_id"]
            or mount["mount_role"] != pre["mount_role"]
            or mount["mount_role"] != post["mount_role"]
            or mount["pre_evaluation_journal_sha256"] != pre_rec["journal_sha256"]
            or mount["post_evaluation_journal_sha256"] != post_rec["journal_sha256"]
            or mount["pre_evaluation_routing_payload_sha256"] != pre["routing_payload_sha256"]
            or mount["post_evaluation_routing_payload_sha256"] != post["routing_payload_sha256"]
        ):
            raise BundleRefusal("bridge mount closure does not bind raw pre/post recovery role, mount, journal, and routing evidence")

    registries: dict[str, Mapping[str, Any]] = {}
    for mount in mounts:
        registries[str(mount["mount_id"])] = _closure_registry(
            files, mount=mount, stream=public_streams[str(mount["stream_id"])], scorer_sha256=str(candidate["bindings"]["scorer_sha256"])
        )
    _validate_closure_reservations(files, public, str(candidate["bindings"]["scorer_sha256"]), mounts, registries)

    # DNRD role lineage is a raw registry fact, not a candidate projection.
    for stream_id in public_streams:
        w0 = by_pair[(stream_id, "NO_MEMORY_ROLLBACK")]
        full = by_pair[(stream_id, "FULL")]
        raw = by_pair[(stream_id, "RAW_EQUAL_BUDGET")]
        deranged = by_pair[(stream_id, "BINDING_DERANGED_NUMERIC_PLACEBO")]
        for child, source in ((full, w0), (raw, w0), (deranged, full)):
            registry = registries[str(child["mount_id"])]
            if (
                registry["source_mount_id"] != source["mount_id"]
                or registry["source_state_sha256"] != source["pre_evaluation_routing_payload_sha256"]
            ):
                raise BundleRefusal("bridge mount registry source lineage does not bind the required W0/FULL control topology")
        w0_registry = registries[str(w0["mount_id"])]
        if w0_registry["source_mount_id"] is not None or w0_registry["source_state_sha256"] is not None:
            raise BundleRefusal("W0 rollback registry must have no predecessor mount/state")

    replays: dict[str, dict[str, Any]] = {}
    for mount in mounts:
        mount_id = str(mount["mount_id"])
        replay = _replay_v2_mount(
            files, mount=mount, registry=registries[mount_id], scorer_sha256=str(candidate["bindings"]["scorer_sha256"])
        )
        heads = replay["heads"]
        pre = heads.get(mount["pre_evaluation_journal_sha256"])
        post = heads.get(mount["post_evaluation_journal_sha256"])
        if (
            pre is None or post is None
            or pre["routing_payload_sha256"] != mount["pre_evaluation_routing_payload_sha256"]
            or post["routing_payload_sha256"] != mount["post_evaluation_routing_payload_sha256"]
        ):
            raise BundleRefusal("bridge mount pre/post journal head does not replay to its bound durable routing payload")
        expected_revisions = (17, 25) if mount["arm"] == "FULL" else (1, 9)
        if (pre["revision"], post["revision"]) != expected_revisions or replay["final_revision"] != expected_revisions[1]:
            raise BundleRefusal("bridge mount raw V2 journal does not retain the exact DNRD training/evaluation causal prefix")
        replays[mount_id] = replay

    # FULL is the only paired mount formed by a byte-copy of W0 during
    # initialization.  Prove the raw common genesis/bootstrap prefix rather
    # than treating registry source-state metadata as evidence of that copy.
    for stream_id in public_streams:
        _require_full_w0_bootstrap_prefix(
            replays[str(by_pair[(stream_id, "NO_MEMORY_ROLLBACK")]["mount_id"])],
            replays[str(by_pair[(stream_id, "FULL")]["mount_id"])],
            stream_id=stream_id,
        )

    # Re-derive raw arm state relationships from mounted content objects, not
    # from candidate parity booleans or score projections.
    for stream_id in public_streams:
        w0 = by_pair[(stream_id, "NO_MEMORY_ROLLBACK")]
        full = by_pair[(stream_id, "FULL")]
        raw = by_pair[(stream_id, "RAW_EQUAL_BUDGET")]
        deranged = by_pair[(stream_id, "BINDING_DERANGED_NUMERIC_PLACEBO")]
        def routing_payload(mount: Mapping[str, Any]) -> tuple[Mapping[str, Any], bytes]:
            replay = replays[str(mount["mount_id"])]
            latest = replay["routing_atoms"][-1]
            descriptor = latest["content"]
            return replay["payloads"][_v2_key_id(latest["key"])], replay["objects"][descriptor["sha256"]]
        w0_payload, _ = routing_payload(w0)
        full_payload, full_raw = routing_payload(full)
        raw_payload, raw_raw = routing_payload(raw)
        deranged_payload, _ = routing_payload(deranged)
        if any(route["scoreMicros"] != 0 for context in w0_payload["contexts"] for route in context["routes"]):
            raise BundleRefusal("raw W0 mount routing payload is not the exact zero baseline")
        if full_raw != raw_raw or full_payload != raw_payload:
            raise BundleRefusal("raw FULL/RAW closure routing payload bytes are not exact equals")
        donor_context = {context["contextSha256"]: context for context in full_payload["contexts"]}
        expected_deranged_contexts: list[dict[str, Any]] = []
        registry = registries[str(deranged["mount_id"])]
        key_to_context = {row["context_key"]: row for row in registry["contexts"]}
        for receiver in registry["contexts"]:
            donor_key = registry["matched_derangement"][receiver["context_key"]]
            donor = donor_context[key_to_context[donor_key]["context_sha256"]]
            expected_deranged_contexts.append(
                {"contextSha256": receiver["context_sha256"], "stratum": receiver["stratum"], "routes": donor["routes"]}
            )
        expected_deranged = {
            "schemaVersion": full_payload["schemaVersion"], "contexts": expected_deranged_contexts,
            "structuralStatus": full_payload["structuralStatus"],
        }
        if deranged_payload != expected_deranged:
            raise BundleRefusal("raw DERANGED closure routing payload does not rederive from exact mounted FULL permutation")

    # Cross-link every durable trajectory to the independently reconciled
    # runner/model/scorer occurrence.  Model raw-body linkage was established
    # earlier by _reconcile_model_events; this ties its trace digest into V2.
    episode_stream: dict[str, str] = {}
    for stream_id, stream in public_streams.items():
        for episode in stream["training"] + stream["heldout"]:
            episode_stream[str(episode["episode_id"])] = stream_id
    runner_by_mount_trace: dict[tuple[str, str], Mapping[str, Any]] = {}
    for event in runner_events:
        request = event["request"]
        stream_id = episode_stream.get(str(request["episode_id"]))
        if stream_id is None:
            raise BundleRefusal("runner event cannot be associated with one public closure stream")
        arm = "FULL" if event["phase"] == "training" else str(event["arm"])
        mount_id = str(by_pair[(stream_id, arm)]["mount_id"])
        trace_id = str(event["trace"]["trace_id"])
        key = (mount_id, trace_id)
        if key in runner_by_mount_trace:
            raise BundleRefusal("runner event repeats one mount-local durable trajectory identity")
        runner_by_mount_trace[key] = event
    durable_trace_keys: set[tuple[str, str]] = set()
    for mount in mounts:
        mount_id = str(mount["mount_id"])
        replay = replays[mount_id]
        registry = registries[mount_id]
        atom_by_id = replay["atoms"]
        payload_by_id = replay["payloads"]
        credits = [atom for atom in atom_by_id.values() if atom["kind"] == "dnrd:credit"]
        outcomes = [atom for atom in atom_by_id.values() if atom["kind"] == "dnrd:outcome"]
        if mount["arm"] == "FULL":
            if len(credits) != 8 or len(outcomes) != 8:
                raise BundleRefusal("FULL mount does not retain exactly one durable outcome/credit per training exposure")
        elif credits or outcomes:
            raise BundleRefusal("W0/RAW/DERANGED control mounts must retain no durable outcome or credit")
        credited_episodes: set[str] = set()
        for atom in atom_by_id.values():
            if atom["kind"] != "dnrd:trajectory":
                continue
            trace = payload_by_id[_v2_key_id(atom["key"])]
            trace_id = str(trace["traceId"])
            key = (mount_id, trace_id)
            event = runner_by_mount_trace.get(key)
            if event is None or _v2_trace_wire(trace, registry) != event["trace"]:
                raise BundleRefusal("raw durable trajectory does not exactly cross-link runner/model-bound trace evidence")
            durable_trace_keys.add(key)
        for credit_atom in credits:
            refs = credit_atom["references"]
            trace_ref = refs[0]["target"]
            outcome_ref = refs[1]["target"]
            trace = payload_by_id[_v2_key_id(trace_ref)]
            outcome = payload_by_id[_v2_key_id(outcome_ref)]
            credit = payload_by_id[_v2_key_id(credit_atom["key"])]
            event = runner_by_mount_trace.get((mount_id, str(trace["traceId"])))
            if (
                event is None or event["phase"] != "training" or event["credit_receipt"] is None
                or event["credit_receipt"]["observation"] != outcome
                or event["credit_receipt"]["credit_receipt"] != credit
                or event["scorer_outcome"]["outcome_digest"] != outcome["scorerObservationSha256"]
                or event["scorer_outcome"]["reward"] != outcome["outcomeScoreMicros"]
            ):
                raise BundleRefusal("durable outcome/credit does not cross-link exact runner scorer/credit receipt")
            episode_id = str(trace["episodeId"])
            if episode_id in credited_episodes:
                raise BundleRefusal("raw V2 closure credits one training episode more than once")
            credited_episodes.add(episode_id)
        if mount["arm"] == "FULL":
            expected_training = {row["episode_id"] for row in registry["training"]}
            if credited_episodes != expected_training:
                raise BundleRefusal("FULL raw V2 closure does not credit exact registered training exposure support once each")
    if durable_trace_keys != set(runner_by_mount_trace):
        raise BundleRefusal("raw V2 closure trajectories do not exactly cover all runner/model/scorer events")


def _validate_verifier_runtime_bundle_evidence(
    root: Path,
    raw: bytes,
    preregistration: Mapping[str, Any],
    config: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> None:
    """Rehash and inspect the exact verifier bytes retained by the occurrence."""
    if not raw or len(raw) > VERIFIER_RUNTIME_BUNDLE_MAX_BYTES:
        raise BundleRefusal("retained verifier runtime bundle exceeds its byte boundary")
    try:
        source = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise BundleRefusal("retained verifier runtime bundle must be strict UTF-8") from error
    if "\x00" in source or any(
        pattern.search(source) is not None
        for pattern in _ORDINARY_ESM_DEPENDENCY_PATTERNS
    ):
        raise BundleRefusal(
            "retained verifier runtime bundle contains an ordinary external ESM dependency"
        )
    target = _bundle_plain_file(root, VERIFIER_RUNTIME_BUNDLE_EVIDENCE_PATH)
    if stat.S_IMODE(target.stat().st_mode) != 0o400:
        raise BundleRefusal("retained verifier runtime bundle mode is not owner-read-only")
    digest = _sha_bytes(raw)
    binding = preregistration.get("runtime_bindings")
    if type(binding) is not dict or (
        digest != OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256
        or config.get("verifier_runtime_bundle_sha256") != digest
        or binding.get("verifier_runtime_bundle_sha256") != digest
        or runtime.get("verifier_runtime_bundle_sha256") != digest
        or runtime.get("verifier_runtime_bundle_evidence_path")
        != VERIFIER_RUNTIME_BUNDLE_EVIDENCE_PATH
        or runtime.get("verifier_runtime_bundle_dependency_policy")
        != VERIFIER_RUNTIME_BUNDLE_DEPENDENCY_POLICY
    ):
        raise BundleRefusal(
            "retained verifier runtime bundle does not match the official Source-A/B/runtime identity"
        )


def _validate_bundle_index(root: Path) -> Mapping[str, str]:
    """Close the evidence input set before interpreting any candidate fields."""
    index, raw = _bundle_object(root, "bundle_index.json")
    data = _check_exact_keys(index, {"schema_version", "artifacts", "receipt_sha256"}, "bundle index")
    if data["schema_version"] != "hswm-dnrd-evidence-bundle-index/v1":
        raise BundleRefusal("bundle index schema mismatch")
    _bundle_sha_receipt(data, "bundle index")
    rows = data["artifacts"]
    if type(rows) is not list or not rows:
        raise BundleRefusal("bundle index must list nonempty artifact closure")
    listed: dict[str, str] = {}
    previous = ""
    for index_number, raw_row in enumerate(rows):
        row = _check_exact_keys(raw_row, {"path", "sha256", "bytes"}, f"bundle index.artifacts[{index_number}]")
        path = _string(row["path"], f"bundle index.artifacts[{index_number}].path")
        if (
            path <= previous
            or path == "bundle_index.json"
            or path.startswith("/")
            or path.startswith("judge/")
            or any(part in {"", ".", ".."} for part in Path(path).parts)
        ):
            raise BundleRefusal("bundle index paths must be sorted safe input paths")
        previous = path
        # A runtime closure is later re-walked against its pinned v4 manifest.
        # Permit an empty member here only in that narrow namespace so the
        # index can reach that exact-path/hash/size authorization; ordinary
        # evidence artifacts remain nonempty.
        empty_permitted = path in {"runner_events.jsonl", "model_events.jsonl"} or path.startswith("bridge_runtime_closure/")
        target = _bundle_plain_file(root, path, allow_empty=empty_permitted)
        content = target.read_bytes()
        if (
            row["bytes"] != len(content)
            or (row["bytes"] <= 0 and not (empty_permitted and len(content) == 0))
            or row["sha256"] != _sha_bytes(content)
        ):
            raise BundleRefusal(f"bundle index artifact hash/size mismatch: {path}")
        listed[path] = str(row["sha256"])

    actual: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if relative == "judge" or relative.startswith("judge/"):
            continue
        info = path.lstat()
        if path.is_symlink():
            raise BundleRefusal(f"bundle contains forbidden symbolic link: {relative}")
        if path.is_file():
            if relative != "bundle_index.json":
                actual.add(relative)
        elif not path.is_dir():
            raise BundleRefusal(f"bundle contains nonregular artifact: {relative}")
    if actual != set(listed):
        raise BundleRefusal(
            "bundle index does not exactly cover input files: "
            f"missing={sorted(actual - set(listed))}, excess={sorted(set(listed) - actual)}"
        )
    required_inputs = set(BUNDLE_COMMON_REQUIRED_FILES) - {"bundle_index.json"}
    if not required_inputs.issubset(listed):
        raise BundleRefusal("bundle index omits a required complete-occurrence artifact")
    has_candidate = "candidate.json" in listed
    has_inconclusive = "inconclusive.json" in listed
    has_void = "void_protocol.json" in listed
    if sum((has_candidate, has_inconclusive, has_void)) != 1:
        raise BundleRefusal("bundle must index exactly one candidate, inconclusive, or void-protocol terminal artifact")
    if has_candidate and not (set(BUNDLE_CANDIDATE_REQUIRED_FILES) - {"bundle_index.json"}).issubset(listed):
        raise BundleRefusal("candidate bundle index omits required state-evidence artifacts")
    return {**listed, "bundle_index.json": _sha_bytes(raw)}


def _git_oid(value: object, label: str) -> str:
    result = _string(value, label)
    if len(result) != 40 or any(character not in HEX64 for character in result):
        raise BundleRefusal(f"{label} must be a lowercase 40-hex Git OID")
    return result


def _validate_runtime_and_attempt(
    runtime: Mapping[str, Any],
    attempt: Mapping[str, Any],
    candidate: Mapping[str, Any],
    preregistration_ci: Mapping[str, Any],
    pulse: Mapping[str, Any],
) -> None:
    runtime_data = _check_exact_keys(
        runtime,
        {
            "schema_version", "execution_adapter_boundary", "bridge_implementation_sha256", "bridge_runtime_root", "bridge_state_root",
            "execution_path_base",
            "bridge_execution_root", "bridge_implementation_execution_path",
            "bridge_runtime_tree_manifest_sha256", "bridge_command", "bridge_config",
            "scorer_implementation_sha256", "scorer_implementation_source_path",
            "scorer_execution_root", "scorer_implementation_execution_path",
            "scorer_command", "scorer_import_root",
            "node_executable_path", "node_executable_sha256", "node_version", "python_executable_path",
            "python_executable_sha256", "python_version", "unicode_data_version", "subprocess_environment",
            "verifier_command", "verifier_helper_sha256", "verifier_package_lock_sha256",
            "verifier_runtime_bundle_sha256", "verifier_runtime_bundle_evidence_path",
            "verifier_runtime_bundle_dependency_policy", "verifier_argument_contract", "verifier_working_directory",
            "verifier_subprocess_environment", "verifier_timeout_seconds",
            "execution_closure_file_mode", "execution_closure_directory_mode",
            "execution_closure_isolation_claim",
            "receipt_sha256",
        },
        "runtime receipt",
    )
    if runtime_data["schema_version"] != RUNTIME_RECEIPT_SCHEMA:
        raise BundleRefusal("runtime receipt schema mismatch")
    runtime_id = _bundle_sha_receipt(runtime_data, "runtime receipt")
    if candidate["bindings"]["runtime_receipt_sha256"] != runtime_id:
        raise BundleRefusal("candidate runtime receipt binding does not match retained receipt")
    if runtime_data["execution_adapter_boundary"] != PRODUCTION_EXECUTION_ADAPTER_BOUNDARY:
        raise BundleRefusal(
            "runtime receipt was not emitted by the production hash-bound adapter boundary"
        )
    for key in (
        "bridge_implementation_sha256", "bridge_runtime_tree_manifest_sha256", "scorer_implementation_sha256",
        "node_executable_sha256", "python_executable_sha256", "verifier_helper_sha256",
        "verifier_package_lock_sha256", "verifier_runtime_bundle_sha256",
    ):
        _sha(runtime_data[key], f"runtime receipt.{key}")
    for key in (
        "bridge_runtime_root", "execution_path_base", "bridge_execution_root",
        "bridge_implementation_execution_path",
        "bridge_state_root", "scorer_implementation_source_path", "scorer_execution_root",
        "scorer_implementation_execution_path", "scorer_import_root", "node_executable_path",
        "node_version", "python_executable_path", "python_version", "unicode_data_version",
        "verifier_working_directory",
        "verifier_runtime_bundle_evidence_path", "verifier_runtime_bundle_dependency_policy",
        "execution_closure_file_mode", "execution_closure_directory_mode",
        "execution_closure_isolation_claim",
    ):
        _string(runtime_data[key], f"runtime receipt.{key}")
    for key in ("bridge_command", "scorer_command", "verifier_command", "verifier_argument_contract"):
        command = runtime_data[key]
        if type(command) is not list or not command or any(type(item) is not str or not item for item in command):
            raise BundleRefusal(f"runtime receipt.{key} must be a nonempty command string list")
    if (
        type(runtime_data["bridge_config"]) is not dict
        or type(runtime_data["subprocess_environment"]) is not dict
        or type(runtime_data["verifier_subprocess_environment"]) is not dict
    ):
        raise BundleRefusal("runtime receipt bridge config/environment must be objects")
    if (
        runtime_data["verifier_argument_contract"] != list(VERIFIER_ARGUMENT_CONTRACT)
        or runtime_data["subprocess_environment"] != PINNED_SUBPROCESS_ENVIRONMENT
        or runtime_data["verifier_subprocess_environment"] != PINNED_SUBPROCESS_ENVIRONMENT
        or runtime_data["verifier_runtime_bundle_evidence_path"]
        != VERIFIER_RUNTIME_BUNDLE_EVIDENCE_PATH
        or runtime_data["verifier_runtime_bundle_dependency_policy"]
        != VERIFIER_RUNTIME_BUNDLE_DEPENDENCY_POLICY
        or runtime_data["verifier_timeout_seconds"] != VERIFIER_TIMEOUT_SECONDS
        or type(runtime_data["verifier_timeout_seconds"]) is not int
    ):
        raise BundleRefusal("runtime receipt verifier invocation boundary drifted")
    if runtime_data["scorer_implementation_sha256"] != candidate["bindings"]["scorer_sha256"]:
        raise BundleRefusal("runtime receipt scorer identity differs from candidate binding")
    if (
        runtime_data["execution_closure_file_mode"] != "0400"
        or runtime_data["execution_closure_directory_mode"] != "0500"
        or runtime_data["execution_path_base"] != "CONFIGURED_OUTPUT_ROOT"
        or runtime_data["execution_closure_isolation_claim"]
        != EXECUTION_CLOSURE_ISOLATION_CLAIM
    ):
        raise BundleRefusal("runtime receipt overstates or changes copied-closure isolation")

    attempt_data = _check_exact_keys(
        attempt,
        {
            "schema_version", "occurrence_id", "source_commit", "source_tree_oid", "source_manifest_sha256",
            "preregistration_commit", "preregistration_tree_oid", "preregistration_sha256",
            "preregistration_ci_receipt_sha256", "pulse_receipt_sha256", "runtime_receipt_sha256", "terminal_intent_schema",
            "terminal_artifact_relative_path", "enforcement_scope", "receipt_sha256",
        },
        "durable attempt marker",
    )
    if (
        attempt_data["schema_version"] != "hswm-dnrd-durable-attempt-marker/v5"
        or attempt_data["enforcement_scope"]
        != "DETERMINISTIC_OCCURRENCE_ID_FILE_AND_PARENT_DIRECTORY_FSYNC_MARKER_UNDER_"
        "B_PINNED_LOCAL_REGISTRY_ONLY_SAME_UID_CROSS_HOST_AND_GLOBAL_SINGLETON_NOT_PROVEN"
    ):
        raise BundleRefusal("durable attempt marker schema/scope mismatch")
    _bundle_sha_receipt(attempt_data, "durable attempt marker")
    if (
        attempt_data["terminal_intent_schema"] != "hswm-dnrd-terminal-intent/v1"
        or attempt_data["terminal_artifact_relative_path"] != "terminal-intent.json"
    ):
        raise BundleRefusal("durable attempt marker terminal-intent binding mismatch")
    bindings = candidate["bindings"]
    for key in (
        "source_manifest_sha256", "preregistration_sha256", "preregistration_ci_receipt_sha256",
        "pulse_receipt_sha256", "runtime_receipt_sha256",
    ):
        if attempt_data.get(key) != bindings[key]:
            raise BundleRefusal(f"attempt lock does not bind candidate {key}")
    chronology = candidate["chronology"]
    if (
        attempt_data["source_commit"] != chronology["source_commit"]
        or attempt_data["source_tree_oid"] != chronology["source_tree_oid"]
        or attempt_data["preregistration_commit"] != chronology["preregistration_commit"]
        or attempt_data["preregistration_tree_oid"] != chronology["preregistration_tree_oid"]
    ):
        raise BundleRefusal("durable attempt marker Git identities differ from candidate chronology")

    # Deliberately rederive the registry filename identity from semantic
    # commitments only.  Receipt/pulse-verifier/runtime hashes remain audit
    # bindings above, but may not turn one science occurrence into multiple
    # local markers merely because their byte representation changes.
    pulse_value = _check_exact_keys(
        pulse,
        {
            "minimum_eligible_time_unix", "projection", "schema_version", "seed_hex",
            "source_binding", "source_freeze_unix", "preregistration_ci_completed_unix",
            "receipt_sha256",
        },
        "pulse binding for attempt occurrence identity",
    )
    projection = _check_exact_keys(
        pulse_value["projection"],
        {
            "chain_hash", "round", "round_time_unix", "randomness_hex",
            "verification_receipt_sha256", "verification_succeeded",
        },
        "pulse projection for attempt occurrence identity",
    )
    run_id = _integer(
        preregistration_ci["run_id"], "preregistration B CI run ID for attempt occurrence identity", minimum=1
    )
    completed_at = _integer(
        preregistration_ci["completed_at_unix"], "preregistration B CI completion for attempt occurrence identity", minimum=1
    )
    if pulse_value["preregistration_ci_completed_unix"] != completed_at:
        raise BundleRefusal("attempt occurrence identity B-CI completion differs from pulse")
    occurrence = {
        "experiment_id": EXPERIMENT_ID,
        "occurrence_schema": "hswm-dnrd-occurrence-id/v1",
        "source_commit": chronology["source_commit"],
        "source_manifest_sha256": bindings["source_manifest_sha256"],
        "source_tree_oid": chronology["source_tree_oid"],
        "preregistration_ci_completed_at_unix": completed_at,
        "preregistration_ci_run_id": run_id,
        "preregistration_commit": chronology["preregistration_commit"],
        "preregistration_sha256": bindings["preregistration_sha256"],
        "preregistration_tree_oid": chronology["preregistration_tree_oid"],
        "quicknet_chain_hash": _sha(projection["chain_hash"], "attempt occurrence Quicknet chain hash"),
        "quicknet_randomness_hex": _sha(projection["randomness_hex"], "attempt occurrence Quicknet randomness"),
        "quicknet_round": _integer(projection["round"], "attempt occurrence Quicknet round", minimum=1),
        "seed_hex": _sha(pulse_value["seed_hex"], "attempt occurrence future seed"),
    }
    if attempt_data["occurrence_id"] != _canonical_hash(occurrence):
        raise BundleRefusal("durable attempt marker occurrence ID does not rederive from immutable semantics")


def _validate_config_readback(
    config: Mapping[str, Any], candidate: Mapping[str, Any], runtime: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Validate the secret-free execution readback used for raw preflight replay."""
    data = _check_exact_keys(
        config,
        {
            "repo_root", "source_a_commit", "source_a_tree", "source_manifest_path",
            "source_manifest_sha256", "prereg_b_commit", "prereg_b_tree", "prereg_path", "prereg_sha256",
            "source_freeze_unix", "preregistration_ci_completed_unix", "output_root",
            "model_endpoint", "bridge_implementation_path", "bridge_implementation_sha256",
            "bridge_command", "bridge_config", "scorer_implementation_path",
            "scorer_implementation_sha256", "scorer_command", "verifier_command",
            "verifier_helper_path", "verifier_helper_sha256", "verifier_package_lock_path",
            "verifier_package_lock_sha256", "verifier_runtime_bundle_path",
            "verifier_runtime_bundle_sha256", "attempt_registry_root", "preregistration_ci_receipt_path",
            "preregistration_ci_receipt_sha256", "source_ci_receipt_path", "source_ci_receipt_sha256",
            "structured_output_qualification_path", "structured_output_qualification_sha256",
            "tokenizer_preflight_prompt", "bridge_runtime_root", "bridge_state_root",
            "bridge_runtime_tree_manifest_path", "bridge_runtime_tree_manifest_sha256",
            "node_executable_path", "node_executable_sha256", "node_version", "python_executable_path",
            "python_executable_sha256", "python_version", "unicode_data_version", "scorer_import_root",
            "model_api_key_environment",
        },
        "execution config readback",
    )
    chronology, bindings = candidate["chronology"], candidate["bindings"]
    if (
        data["source_a_commit"] != chronology["source_commit"]
        or data["source_a_tree"] != chronology["source_tree_oid"]
        or data["source_manifest_sha256"] != bindings["source_manifest_sha256"]
        or data["prereg_b_commit"] != chronology["preregistration_commit"]
        or data["prereg_b_tree"] != chronology["preregistration_tree_oid"]
        or data["prereg_sha256"] != bindings["preregistration_sha256"]
        or data["source_freeze_unix"] != chronology["source_frozen_at_unix"]
        or data["preregistration_ci_completed_unix"]
        != chronology["preregistration_ci_completed_at_unix"]
        or data["preregistration_ci_receipt_sha256"]
        != bindings["preregistration_ci_receipt_sha256"]
        or data["bridge_implementation_sha256"] != runtime["bridge_implementation_sha256"]
        or data["scorer_implementation_sha256"] != runtime["scorer_implementation_sha256"]
        or data["bridge_config"] != runtime["bridge_config"]
        or data["bridge_runtime_tree_manifest_sha256"] != runtime["bridge_runtime_tree_manifest_sha256"]
        or data["node_executable_path"] != runtime["node_executable_path"]
        or data["node_executable_sha256"] != runtime["node_executable_sha256"]
        or data["node_version"] != runtime["node_version"]
        or data["python_executable_path"] != runtime["python_executable_path"]
        or data["python_executable_sha256"] != runtime["python_executable_sha256"]
        or data["python_version"] != runtime["python_version"]
        or data["unicode_data_version"] != runtime["unicode_data_version"]
        or data["verifier_helper_sha256"] != runtime["verifier_helper_sha256"]
        or data["verifier_package_lock_sha256"]
        != runtime["verifier_package_lock_sha256"]
        or data["verifier_runtime_bundle_sha256"]
        != runtime["verifier_runtime_bundle_sha256"]
    ):
        raise BundleRefusal("execution config readback does not match candidate chronology/runtime pins")
    if data["tokenizer_preflight_prompt"] != TOKENIZER_PREFLIGHT_PROMPT:
        raise BundleRefusal("execution config tokenizer preflight prompt differs from the frozen DNRD-4S1 structured-response probe")
    if (
        type(data["preregistration_ci_completed_unix"]) is not int
        or data["preregistration_ci_completed_unix"] <= 0
    ):
        raise BundleRefusal("execution config preregistration B-CI completion time is malformed")
    for key in (
        "repo_root", "source_manifest_path", "prereg_path", "output_root", "model_endpoint",
        "bridge_implementation_path", "scorer_implementation_path", "verifier_helper_path",
        "verifier_package_lock_path", "verifier_runtime_bundle_path", "attempt_registry_root",
        "preregistration_ci_receipt_path", "source_ci_receipt_path", "structured_output_qualification_path", "tokenizer_preflight_prompt",
        "bridge_runtime_root", "bridge_state_root", "bridge_runtime_tree_manifest_path",
        "node_executable_path", "node_version", "python_executable_path", "python_version",
        "unicode_data_version", "scorer_import_root", "model_api_key_environment",
    ):
        _string(data[key], f"execution config readback.{key}")
    for key in (
        "preregistration_ci_receipt_sha256", "verifier_helper_sha256", "verifier_package_lock_sha256",
        "verifier_runtime_bundle_sha256", "source_ci_receipt_sha256",
        "structured_output_qualification_sha256",
    ):
        _sha(data[key], f"execution config readback.{key}")
    for key in ("bridge_command", "scorer_command", "verifier_command"):
        command = data[key]
        if type(command) is not list or not command or any(
            type(item) is not str or not item for item in command
        ):
            raise BundleRefusal(f"execution config readback.{key} is malformed")

    repo_root = Path(str(data["repo_root"]))
    output_root = Path(str(data["output_root"]))
    source_runtime_root = Path(str(data["bridge_runtime_root"]))
    source_bridge = Path(str(data["bridge_implementation_path"]))
    source_scorer = Path(str(data["scorer_implementation_path"]))
    verifier_helper = Path(str(data["verifier_helper_path"]))
    verifier_lock = Path(str(data["verifier_package_lock_path"]))
    verifier_bundle = Path(str(data["verifier_runtime_bundle_path"]))
    qualification_path = Path(str(data["structured_output_qualification_path"]))
    preregistration_ci_path = Path(str(data["preregistration_ci_receipt_path"]))
    node_path = str(data["node_executable_path"])
    python_path = str(data["python_executable_path"])
    if not all(
        path.is_absolute()
        for path in (
            repo_root, output_root, source_runtime_root, source_bridge, source_scorer,
            verifier_helper, verifier_lock, verifier_bundle, qualification_path,
            preregistration_ci_path,
        )
    ):
        raise BundleRefusal("execution config source/output/runtime paths must be absolute")
    try:
        bridge_relative = source_bridge.relative_to(source_runtime_root)
        scorer_relative = source_scorer.relative_to(repo_root)
    except ValueError as error:
        raise BundleRefusal("execution implementation escapes its frozen source root") from error
    expected_bridge_root = Path("bridge_runtime_closure")
    expected_bridge = expected_bridge_root / bridge_relative
    expected_scorer_root = Path("source_closure")
    expected_scorer = expected_scorer_root / scorer_relative
    expected_verifier_helper = repo_root / "_research/dnrd/verify-beacon.mjs"
    expected_verifier_lock = repo_root / "tools/swm0w_drand/package-lock.json"
    expected_verifier_bundle = (
        repo_root / "tools/swm0w_drand/node_modules/drand-client/build/esm/index.mjs"
    )
    if (
        scorer_relative.as_posix() != "_research/dnrd/scorer.py"
        or data["scorer_import_root"] != data["repo_root"]
        or data["bridge_command"] != [node_path, str(source_bridge)]
        or data["scorer_command"]
        != [python_path, *SCORER_ARGUMENT_CONTRACT]
        or verifier_helper != expected_verifier_helper
        or verifier_lock != expected_verifier_lock
        or verifier_bundle != expected_verifier_bundle
        or data["verifier_command"] != [node_path, str(verifier_helper)]
        or runtime["bridge_runtime_root"] != str(source_runtime_root)
        or runtime["bridge_execution_root"] != str(expected_bridge_root)
        or runtime["bridge_implementation_execution_path"] != str(expected_bridge)
        or runtime["bridge_command"]
        != [node_path, "{OUTPUT_ROOT}/" + expected_bridge.as_posix()]
        or runtime["scorer_implementation_source_path"] != str(source_scorer)
        or runtime["scorer_execution_root"] != str(expected_scorer_root)
        or runtime["scorer_implementation_execution_path"] != str(expected_scorer)
        or runtime["scorer_command"] != data["scorer_command"]
        or runtime["scorer_import_root"] != str(expected_scorer_root)
        or runtime["verifier_command"] != data["verifier_command"]
        or runtime["verifier_argument_contract"] != list(VERIFIER_ARGUMENT_CONTRACT)
        or runtime["verifier_working_directory"] != str(verifier_helper.parent)
        or runtime["subprocess_environment"] != PINNED_SUBPROCESS_ENVIRONMENT
        or runtime["verifier_subprocess_environment"] != PINNED_SUBPROCESS_ENVIRONMENT
        or runtime["verifier_runtime_bundle_evidence_path"]
        != VERIFIER_RUNTIME_BUNDLE_EVIDENCE_PATH
        or runtime["verifier_runtime_bundle_dependency_policy"]
        != VERIFIER_RUNTIME_BUNDLE_DEPENDENCY_POLICY
        or runtime["verifier_timeout_seconds"] != VERIFIER_TIMEOUT_SECONDS
    ):
        raise BundleRefusal(
            "runtime receipt does not distinguish frozen source paths from copied execution paths"
        )
    return data


def _validate_deployment(
    deployment: Mapping[str, Any], candidate: Mapping[str, Any], config: Mapping[str, Any]
) -> tuple[str, str, Mapping[str, Any]]:
    required = {
        "schema_version", "endpoint", "model", "model_root", "model_max_model_len", "vllm_version",
        "chat_config", "model_list_request_sha256", "model_list_response_sha256", "model_list_response_utf8",
        "version_request_sha256", "version_response_sha256", "version_response_utf8",
        "tokenizer_request_sha256", "tokenizer_response_sha256", "tokenizer_response_utf8",
        "tokenizer_count", "provider_cache_independence", "generation_calls", "non_generation_http_calls",
        "preflight_call_order", "receipt_sha256",
    }
    value = _check_exact_keys(deployment, required, "deployment receipt")
    if (
        value["schema_version"] != "hswm-dnrd-live-preflight-receipt/v1"
        or value["model"] != "qwen3.6-35b-a3b"
        or value["model_root"] != "Qwen/Qwen3.6-35B-A3B-FP8"
        or value["model_max_model_len"] != 32768
        or value["vllm_version"] != "0.25.1"
        or value["provider_cache_independence"] != PROVIDER_CACHE_UNOBSERVABLE
        or value["generation_calls"] != 0
        or value["non_generation_http_calls"] != 3
        or value["preflight_call_order"] != ["GET /v1/models", "GET /version", "POST /tokenize"]
    ):
        raise BundleRefusal("deployment receipt does not attest the frozen non-generation boundary")
    _bundle_sha_receipt(value, "deployment receipt")
    if candidate["bindings"]["model_deployment_sha256"] != _canonical_hash(value):
        raise BundleRefusal("candidate deployment binding does not match retained receipt bytes")
    endpoint = _string(value["endpoint"], "deployment receipt.endpoint")
    try:
        parsed_endpoint = urlsplit(_string(config["model_endpoint"], "execution config readback.model_endpoint"))
    except ValueError as error:
        raise BundleRefusal("execution config readback model endpoint is invalid") from error
    if (
        parsed_endpoint.scheme not in {"http", "https"}
        or not parsed_endpoint.netloc
        or parsed_endpoint.query
        or parsed_endpoint.fragment
        or parsed_endpoint.path.rstrip("/") not in {"", "/v1"}
        or endpoint != f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}"
    ):
        raise BundleRefusal("deployment receipt endpoint does not replay the configured normalized model endpoint")
    chat_config = value["chat_config"]
    if chat_config != {
        "chat_template_kwargs": {"enable_thinking": False}, "logprobs": False, "n": 1,
        "stream": False, "temperature": 0, "top_p": 1,
    }:
        raise BundleRefusal("deployment chat configuration differs from the frozen generation contract")
    if type(value["tokenizer_count"]) is not int or value["tokenizer_count"] < 0:
        raise BundleRefusal("deployment tokenizer count is malformed")
    raw_objects: dict[str, Mapping[str, Any]] = {}
    for prefix in ("model_list", "version", "tokenizer"):
        raw = _string(value[f"{prefix}_response_utf8"], f"deployment {prefix} raw body")
        if _sha_bytes(raw.encode("utf-8")) != _sha(value[f"{prefix}_response_sha256"], f"deployment {prefix} digest"):
            raise BundleRefusal(f"deployment {prefix} raw response digest mismatch")
        parsed = _parse_json_bytes(raw.encode("utf-8"), f"deployment {prefix} raw body", canonical=False)
        if type(parsed) is not dict:
            raise BundleRefusal(f"deployment {prefix} raw body must be an object")
        raw_objects[prefix] = parsed
        _sha(value[f"{prefix}_request_sha256"], f"deployment {prefix} request digest")
    models = raw_objects["model_list"].get("data")
    matching = [row for row in models if type(row) is dict and row.get("id") == value["model"]] if type(models) is list else []
    if len(matching) != 1 or matching[0].get("root") != value["model_root"] or matching[0].get("max_model_len") != value["model_max_model_len"]:
        raise BundleRefusal("deployment model-list raw body does not attest served model identity")
    if raw_objects["version"].get("version") != value["vllm_version"]:
        raise BundleRefusal("deployment version raw body does not attest vLLM version")
    tokenizer = raw_objects["tokenizer"]
    if tokenizer.get("count") != value["tokenizer_count"] or (
        "tokens" in tokenizer and (type(tokenizer["tokens"]) is not list or len(tokenizer["tokens"]) != value["tokenizer_count"])
    ):
        raise BundleRefusal("deployment tokenizer raw body is inconsistent")
    tokenizer_body = _canonical_bytes({"model": value["model"], "prompt": config["tokenizer_preflight_prompt"]})

    def preflight_request_digest(method: str, url: str, body: bytes | None) -> str:
        return _sha_bytes(
            _canonical_bytes(
                {
                    "body_sha256": _sha_bytes(body or b""),
                    "content_type": "application/json",
                    "method": method,
                    "url": url,
                }
            )
        )

    expected_requests = {
        "model_list_request_sha256": preflight_request_digest("GET", f"{endpoint}/v1/models", None),
        "version_request_sha256": preflight_request_digest("GET", f"{endpoint}/version", None),
        "tokenizer_request_sha256": preflight_request_digest("POST", f"{endpoint}/tokenize", tokenizer_body),
    }
    if any(value[key] != digest for key, digest in expected_requests.items()):
        raise BundleRefusal("deployment preflight request digests do not replay frozen endpoint/body bytes")
    return endpoint, str(value["model"]), chat_config


def _quicknet_time(round_number: int) -> int:
    if type(round_number) is not int or round_number < 1:
        raise BundleRefusal("Quicknet round must be a positive integer")
    return 1_692_803_367 + (round_number - 1) * 3


def _first_eligible_round(source_unix: int, preregistration_ci_unix: int) -> int:
    threshold = max(source_unix, preregistration_ci_unix) + 900
    genesis = 1_692_803_367
    if threshold <= genesis:
        return 1
    return ((threshold - genesis + 2) // 3) + 1


def _validate_pulse(
    pulse: Mapping[str, Any],
    verifier_bytes: bytes,
    candidate: Mapping[str, Any],
    preregistration_ci: Mapping[str, Any],
    preregistration: Mapping[str, Any],
) -> None:
    keys = {
        "minimum_eligible_time_unix", "projection", "schema_version", "seed_hex", "source_binding",
        "source_freeze_unix", "preregistration_ci_completed_unix", "receipt_sha256",
    }
    value = _check_exact_keys(pulse, keys, "pulse binding")
    if value["schema_version"] != PULSE_BINDING_SCHEMA:
        raise BundleRefusal("pulse binding schema mismatch")
    receipt = _bundle_sha_receipt(value, "pulse binding")
    if candidate["bindings"]["pulse_receipt_sha256"] != receipt:
        raise BundleRefusal("candidate pulse receipt binding does not match retained pulse binding")
    source_time = _integer(value["source_freeze_unix"], "pulse.source_freeze_unix", minimum=1)
    ci_completed_time = _integer(
        value["preregistration_ci_completed_unix"],
        "pulse.preregistration_ci_completed_unix",
        minimum=1,
    )
    if ci_completed_time != preregistration_ci["completed_at_unix"]:
        raise BundleRefusal("pulse binding B-CI completion time differs from retained receipt")
    if (
        candidate["chronology"]["source_frozen_at_unix"] != source_time
        or candidate["chronology"]["preregistration_ci_completed_at_unix"]
        != ci_completed_time
    ):
        raise BundleRefusal("candidate chronology source/B-CI times differ from pulse binding")
    if value["minimum_eligible_time_unix"] != max(source_time, ci_completed_time) + 900:
        raise BundleRefusal("pulse binding minimum eligible time is incorrect")
    binding = _check_exact_keys(
        value["source_binding"],
        {
            "experiment_id", "preregistration_blob_sha256", "preregistration_ci_completed_unix",
            "preregistration_ci_receipt_sha256", "preregistration_commit", "preregistration_tree_oid",
            "source_commit", "source_manifest_sha256", "source_tree_oid",
        },
        "pulse source binding",
    )
    if binding["experiment_id"] != EXPERIMENT_ID:
        raise BundleRefusal("pulse source binding experiment identity mismatch")
    for key in (
        "preregistration_blob_sha256",
        "preregistration_ci_receipt_sha256",
        "source_manifest_sha256",
    ):
        _sha(binding[key], f"pulse source binding.{key}")
    for key in (
        "preregistration_commit",
        "preregistration_tree_oid",
        "source_commit",
        "source_tree_oid",
    ):
        _git_oid(binding[key], f"pulse source binding.{key}")
    if _integer(
        binding["preregistration_ci_completed_unix"],
        "pulse source binding.preregistration_ci_completed_unix",
        minimum=1,
    ) != ci_completed_time:
        raise BundleRefusal("pulse source binding B-CI completion time differs from pulse binding")
    if (
        binding["source_manifest_sha256"] != candidate["bindings"]["source_manifest_sha256"]
        or binding["preregistration_blob_sha256"] != candidate["bindings"]["preregistration_sha256"]
        or binding["preregistration_ci_receipt_sha256"]
        != candidate["bindings"]["preregistration_ci_receipt_sha256"]
        or binding["source_commit"] != candidate["chronology"]["source_commit"]
        or binding["source_tree_oid"] != candidate["chronology"]["source_tree_oid"]
        or binding["preregistration_commit"] != candidate["chronology"]["preregistration_commit"]
        or binding["preregistration_tree_oid"]
        != candidate["chronology"]["preregistration_tree_oid"]
    ):
        raise BundleRefusal("pulse source binding differs from candidate/source B-CI identities")
    projection = _check_exact_keys(
        value["projection"],
        {"chain_hash", "round", "round_time_unix", "randomness_hex", "verification_receipt_sha256", "verification_succeeded"},
        "pulse projection",
    )
    if (
        projection["chain_hash"] != QUICKNET_CHAIN["hash"]
        or projection["verification_succeeded"] is not True
    ):
        raise BundleRefusal("pulse projection does not attest the frozen verified Quicknet chain")
    round_number = _integer(projection["round"], "pulse projection.round", minimum=1)
    if (
        round_number != _first_eligible_round(source_time, ci_completed_time)
        or projection["round_time_unix"] != _quicknet_time(round_number)
        or projection["round_time_unix"] < value["minimum_eligible_time_unix"]
        or candidate["chronology"]["pulse_round"] != round_number
        or candidate["chronology"]["pulse_chain_hash"] != projection["chain_hash"]
        or candidate["chronology"]["pulse_at_unix"] != projection["round_time_unix"]
    ):
        raise BundleRefusal("pulse projection is not the first eligible future Quicknet round")
    _sha(projection["randomness_hex"], "pulse projection.randomness_hex")
    if _sha_bytes(verifier_bytes) != _sha(projection["verification_receipt_sha256"], "pulse projection verifier receipt"):
        raise BundleRefusal("pulse projection does not bind the retained raw verifier receipt bytes")

    # The verifier receipt remains an external cryptographic-verifier claim,
    # not BLS verification performed by this standard-library judge.  We still
    # verify its exact bytes, self-addressed fields, chain/pulse consistency,
    # and signature->randomness derivation so a substituted arbitrary JSON
    # receipt cannot silently stand in for it.
    verifier = _parse_json_bytes(verifier_bytes, "pulse verifier receipt", canonical=False)
    if type(verifier) is not dict:
        raise BundleRefusal("pulse verifier receipt root must be an object")
    if not verifier_bytes.endswith(b"\n") or verifier_bytes[:-1].endswith(b"\n"):
        raise BundleRefusal("pulse verifier receipt must retain exactly one terminal LF")
    if _canonical_bytes(verifier) + b"\n" != verifier_bytes:
        raise BundleRefusal("pulse verifier receipt bytes are not canonical verifier output")
    verifier_data = _check_exact_keys(
        verifier,
        {
            "chain", "chronology_claim_allowed", "helper_version", "input_fixture_sha256",
            "mode", "pulse", "pulse_source_url", "receipt_sha256", "schema_version",
            "verification", "verified_at_unix", "verifier",
        },
        "pulse verifier receipt",
    )
    if verifier_data["schema_version"] != "hswm-swm0w-drand-verification-receipt/v1":
        raise BundleRefusal("pulse verifier receipt schema mismatch")
    _bundle_sha_receipt(verifier_data, "pulse verifier receipt")
    if (
        verifier_data["helper_version"] != "hswm-swm0w-drand-node-verifier/v1"
        or verifier_data["chronology_claim_allowed"] is not False
        or verifier_data["mode"] != "online"
        or verifier_data["input_fixture_sha256"] is not None
    ):
        raise BundleRefusal("pulse verifier receipt does not retain the frozen online verification boundary")
    chain = _check_exact_keys(verifier_data["chain"], set(QUICKNET_CHAIN), "pulse verifier receipt.chain")
    if dict(chain) != QUICKNET_CHAIN:
        raise BundleRefusal("pulse verifier receipt chain does not match frozen Quicknet identity")
    raw_pulse = _check_exact_keys(
        verifier_data["pulse"], {"randomness", "round", "round_time_unix", "signature"},
        "pulse verifier receipt.pulse",
    )
    if (
        raw_pulse.get("round") != round_number
        or raw_pulse.get("round_time_unix") != projection["round_time_unix"]
        or raw_pulse.get("randomness") != projection["randomness_hex"]
    ):
        raise BundleRefusal("pulse verifier receipt does not attest pulse projection")
    signature = _hex_of_length(raw_pulse["signature"], "pulse verifier receipt signature", 96)
    if _sha_bytes(bytes.fromhex(signature)) != projection["randomness_hex"]:
        raise BundleRefusal("pulse verifier receipt randomness is not SHA-256(signature)")
    verification = _check_exact_keys(
        verifier_data["verification"],
        {
            "accepted_beacon_sha256", "accepted_by", "network_policy", "randomness_derivation",
            "signature_scheme",
        },
        "pulse verifier receipt.verification",
    )
    accepted_beacon = {
        "randomness": projection["randomness_hex"],
        "round": round_number,
        "signature": signature,
    }
    if (
        verification["accepted_beacon_sha256"] != _canonical_hash(accepted_beacon)
        or verification["accepted_by"] != "drand-client.fetchBeacon"
        or verification["network_policy"] != "ONLINE_EXPLICIT"
        or verification["randomness_derivation"] != "SHA256(raw_signature_bytes)"
        or verification["signature_scheme"] != QUICKNET_CHAIN["scheme_id"]
    ):
        raise BundleRefusal("pulse verifier receipt verification projection is inconsistent")
    expected_url = f"https://api.drand.sh/{QUICKNET_CHAIN['hash']}/public/{round_number}"
    if (
        verifier_data["pulse_source_url"] != expected_url
        or _integer(verifier_data["verified_at_unix"], "pulse verifier receipt.verified_at_unix", minimum=1)
        < projection["round_time_unix"]
    ):
        raise BundleRefusal("pulse verifier receipt URL or verification time is inconsistent")
    verifier_identity = _check_exact_keys(
        verifier_data["verifier"],
        {
            "git_commit", "git_tag_url", "helper_sha256", "npm_integrity", "npm_shasum",
            "package", "package_json_sha256", "package_lock_sha256", "runtime_bundle_sha256",
            "runtime_engine", "runtime_exec_sha256", "runtime_trust_status", "runtime_version",
            "source_tarball", "version",
        },
        "pulse verifier receipt.verifier",
    )
    _hex_of_length(verifier_identity["git_commit"], "pulse verifier receipt.verifier.git_commit", 40)
    for key in (
        "helper_sha256", "package_json_sha256", "package_lock_sha256", "runtime_bundle_sha256",
        "runtime_exec_sha256",
    ):
        _sha(verifier_identity[key], f"pulse verifier receipt.verifier.{key}")
    pins = preregistration.get("runtime_bindings")
    if type(pins) is not dict or (
        verifier_identity["helper_sha256"] != pins.get("verifier_helper_sha256")
        or verifier_identity["package_lock_sha256"] != pins.get("verifier_package_lock_sha256")
        or verifier_identity["runtime_bundle_sha256"] != pins.get("verifier_runtime_bundle_sha256")
        or verifier_identity["runtime_exec_sha256"] != pins.get("node_executable_sha256")
        or verifier_identity["runtime_version"] != pins.get("node_version")
        or verifier_identity["package"] != "drand-client"
        or verifier_identity["version"] != "1.4.2"
        or verifier_identity["runtime_engine"] != "Node.js"
        or verifier_identity["runtime_trust_status"] != "TRUSTED_LOCAL_OS_AND_NODE_RUNTIME_REQUIRED"
    ):
        raise BundleRefusal("pulse verifier provenance does not match preregistered frozen pins")
    for key in ("git_tag_url", "npm_integrity", "npm_shasum", "runtime_version", "source_tarball"):
        _string(verifier_identity[key], f"pulse verifier receipt.verifier.{key}")

    # Re-derive the domain-separated seed rather than treating the pulse
    # binding's seed as an unexplained fixture selector.  ``seed.py`` uses
    # ensure_ascii=False; retain that exact serialization choice here.
    seed_material = {
        "domain": SEED_DOMAIN,
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": binding["preregistration_commit"],
        "quicknet_chain_hash": projection["chain_hash"],
        "quicknet_randomness_hex": projection["randomness_hex"],
        "quicknet_round": round_number,
        "source_commit": binding["source_commit"],
        "schema_version": "hswm-dnrd-future-seed-material/v5",
    }
    try:
        expected_seed = sha256(
            json.dumps(
                seed_material, allow_nan=False, ensure_ascii=False,
                separators=(",", ":"), sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
    except (TypeError, ValueError) as error:  # defensive: every field was validated above
        raise BundleRefusal("pulse seed material is not finite canonical JSON") from error
    if value["seed_hex"] != expected_seed:
        raise BundleRefusal("pulse binding seed does not rederive from frozen chronology and verified pulse")


def _contains_any_canary(value: object, canaries: frozenset[str]) -> bool:
    if type(value) is str:
        return any(canary in value for canary in canaries)
    if isinstance(value, Mapping):
        return any(
            _contains_any_canary(key, canaries) or _contains_any_canary(child, canaries)
            for key, child in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_any_canary(child, canaries) for child in value)
    return False


def _expected_training_canary(seed: bytes, stream_index: int, ordinal: int) -> str:
    label = f"training-provenance:{stream_index}:{ordinal}".encode("ascii")
    return TRAINING_CANARY_PREFIX + sha256(seed + b"\0" + label).hexdigest()[:32]


def _validate_training_provenance_canaries(
    public: Mapping[str, Any], seed: bytes
) -> frozenset[str]:
    """Re-derive the future-seeded, training-only public canary set.

    These markers are intentionally not a behavior or efficacy signal.  They
    make one falsifiable leakage check possible: a deterministic training-only
    string must neither occur in heldout materials nor enter routing state.
    """
    streams = public.get("streams")
    if type(streams) is not list or len(streams) != 4:
        raise BundleRefusal("public manifest has no exact four-stream canary support")
    canaries: list[str] = []
    training_rows: list[tuple[str, Mapping[str, Any]]] = []
    stream_support_rows: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for stream_index, raw_stream in enumerate(streams):
        if type(raw_stream) is not dict:
            raise BundleRefusal("public canary stream is malformed")
        training = raw_stream.get("training")
        heldout = raw_stream.get("heldout")
        if type(training) is not list or len(training) != 8 or type(heldout) is not list or len(heldout) != 8:
            raise BundleRefusal("public canary stream lacks exact training/heldout support")
        for ordinal, raw_episode in enumerate(training):
            if type(raw_episode) is not dict:
                raise BundleRefusal("public training canary episode is malformed")
            expected = _expected_training_canary(seed, stream_index, ordinal)
            prompt = raw_episode.get("prompt")
            if (
                raw_episode.get("provenance_canary") != expected
                or type(prompt) is not str
                or not prompt.endswith(f"\nTraining provenance marker: {expected}")
                or prompt.count(expected) != 1
            ):
                raise BundleRefusal("public training provenance canary does not deterministically rederive from pulse seed")
            canaries.append(expected)
            training_rows.append((expected, raw_episode))
        for raw_episode in heldout:
            if type(raw_episode) is not dict or "provenance_canary" in raw_episode:
                raise BundleRefusal("heldout public episode carries a forbidden training provenance canary field")
        routing_support = {
            "context_keys": raw_stream.get("context_keys"),
            "route_ids": raw_stream.get("route_ids"),
            "matched_derangement": raw_stream.get("matched_derangement"),
        }
        # Check after all canaries have been collected below; retain this
        # projection locally rather than changing hash-bound public evidence.
        stream_support_rows.append((raw_stream, routing_support))
    if len(canaries) != 32 or len(set(canaries)) != 32:
        raise BundleRefusal("public training provenance canaries are not exact unique 32-marker support")
    frozen = frozenset(canaries)
    for raw_stream, routing_support in stream_support_rows:
        if _contains_any_canary(routing_support, frozen):
            raise BundleRefusal("training provenance canary appears in public routing context/support")
        for raw_episode in raw_stream["heldout"]:
            if _contains_any_canary(raw_episode, frozen):
                raise BundleRefusal("training provenance canary appears in a heldout public episode")
    for expected, episode in training_rows:
        prompt = str(episode["prompt"])
        if {canary for canary in frozen if canary in prompt} != {expected}:
            raise BundleRefusal("public training prompt contains the wrong provenance canary")
        non_prompt = {
            key: value for key, value in episode.items()
            if key not in {"prompt", "provenance_canary"}
        }
        if _contains_any_canary(non_prompt, frozen):
            raise BundleRefusal("training provenance canary escaped its declared training prompt")
    return frozen


def _validate_fixture_seed_binding(
    public: Mapping[str, Any], private: Mapping[str, Any], pulse: Mapping[str, Any]
) -> frozenset[str]:
    """Bind the public/private fixture pair to the independently derived seed.

    The stdlib adjudicator does not import the fixture generator it is judging.
    It therefore proves the seed commitment and exact private/public embedding;
    complete generator re-execution remains a source/runtime-trusted step.
    """
    seed = _sha(pulse.get("seed_hex"), "pulse binding.seed_hex")
    if public.get("seed_commitment") != sha256(bytes.fromhex(seed)).hexdigest():
        raise BundleRefusal("public manifest seed commitment does not match the rederived pulse seed")
    if private.get("seed_hex") != seed:
        raise BundleRefusal("private scorer manifest seed does not match the rederived pulse seed")
    return _validate_training_provenance_canaries(public, bytes.fromhex(seed))


def _raw_response_contains_training_canary(
    raw_response_utf8: object, canaries: frozenset[str]
) -> bool:
    """Scan both retained response bytes and their strict JSON projection.

    JSON escaping can otherwise conceal an ASCII canary in an accepted raw
    response.  The model-boundary verifier separately validates this same raw
    response, so parsing it again here is a conservative, bounded cross-check.
    """
    raw = _string(raw_response_utf8, "accepted model raw response canary scan")
    if _contains_any_canary(raw, canaries):
        return True
    decoded = _parse_json_bytes(
        raw.encode("utf-8"), "accepted model raw response canary scan", canonical=False
    )
    return _contains_any_canary(decoded, canaries)


def _recompute_training_canary_leakage(
    *,
    canaries: frozenset[str],
    state_evidence: Mapping[str, Any],
    call_evidence: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> bool:
    """Derive the retained-evidence canary result without candidate booleans.

    The public manifest check handles routing keys and public heldout material.
    This function covers heldout requests plus every training/heldout sealed
    response and accepted raw completion body, as well as the complete durable
    bridge-state observation.  Training requests are excluded because they are
    the one surface on which each marker is intentionally presented.
    The raw mount closure is scanned separately at byte level before its V2
    semantic replay.
    """
    if _contains_any_canary(state_evidence, canaries):
        return True
    for event, accepted in call_evidence:
        if (
            (
                event.get("phase") == "heldout"
                and _contains_any_canary(event.get("request"), canaries)
            )
            or _contains_any_canary(event.get("sealed_response"), canaries)
            or _raw_response_contains_training_canary(
                accepted.get("raw_response_utf8"), canaries
            )
        ):
            return True
    return False


def _validate_recomputed_canary_overlap(
    overlap: Mapping[str, Any], observed_canary_leakage: bool
) -> None:
    """Bind both candidate leakage bits to the independently observed result."""
    if (
        _boolean(overlap.get("leak_detected"), "candidate.overlap.leak_detected")
        is not observed_canary_leakage
        or _boolean(
            overlap.get("watermark_detected"), "candidate.overlap.watermark_detected"
        )
        is not observed_canary_leakage
    ):
        raise BundleRefusal(
            "candidate leak/watermark projection does not equal independently observed training-canary evidence"
        )
    if observed_canary_leakage:
        raise BundleRefusal(
            "training provenance canary leaked into retained heldout or durable evidence"
        )


def _reject_training_canary_in_raw_closure(
    files: Mapping[str, bytes], canaries: frozenset[str]
) -> None:
    """Reject a training canary in *any* retained raw bridge-closure byte.

    This deliberately runs before the restricted V2 replay.  Thus a copied,
    hash-bound but otherwise unreferenced object/journal file cannot evade the
    leakage check merely because it has no semantic role in a valid trajectory.
    The canaries are ASCII and raw V2 files are UTF-8 canonical JSON, so exact
    byte scanning is the relevant evidence boundary.
    """
    markers = tuple(marker.encode("ascii") for marker in canaries)
    for path, raw in files.items():
        if any(marker in raw for marker in markers):
            raise BundleRefusal(
                "training provenance canary occurs in retained raw bridge mount closure bytes: "
                f"{path}"
            )


def _normalize(value: str) -> str:
    # Imported lazily to make the dependency visibly standard-library only.
    import unicodedata

    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _public_manifest_index(public: Mapping[str, Any], private: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    top = _check_exact_keys(
        public,
        {"schema_version", "family", "seed_commitment", "streams", "private_manifest_commitment"},
        "public manifest",
    )
    if top["schema_version"] != PUBLIC_MANIFEST_SCHEMA or top["family"] != "REPEATED_CONTEXT_TABULAR_ROUTING_MECHANICS_V2":
        raise BundleRefusal("public manifest identity mismatch")
    _sha(top["seed_commitment"], "public manifest.seed_commitment")
    if type(top["streams"]) is not list or len(top["streams"]) != 4:
        raise BundleRefusal("public manifest must contain exactly four streams")
    private_top = _check_exact_keys(
        private,
        {"schema_version", "family", "seed_hex", "public_manifest", "private_bindings"},
        "private manifest",
    )
    if (
        private_top["schema_version"] != "hswm-dnrd-private-scorer-manifest/v2"
        or private_top["family"] != top["family"]
        or private_top["public_manifest"] != {key: value for key, value in public.items() if key != "private_manifest_commitment"}
        or _canonical_hash(private) != top["private_manifest_commitment"]
    ):
        raise BundleRefusal("private scorer manifest does not exactly bind public fixture")
    if type(private_top["private_bindings"]) is not list or len(private_top["private_bindings"]) != 4:
        raise BundleRefusal("private manifest must contain exactly four stream bindings")

    episodes: dict[str, Mapping[str, Any]] = {}
    stream_by_episode: dict[str, Mapping[str, Any]] = {}
    bindings: dict[str, Mapping[str, Any]] = {}
    for index, raw_stream in enumerate(top["streams"]):
        stream = _check_exact_keys(
            raw_stream,
            {"stream_id", "route_ids", "context_keys", "matched_derangement", "training", "heldout"},
            f"public streams[{index}]",
        )
        expected_stream_id = f"stream-{index}"
        if stream["stream_id"] != expected_stream_id:
            raise BundleRefusal("public stream IDs must be canonical stream-0 through stream-3")
        routes, contexts = stream["route_ids"], stream["context_keys"]
        if (
            type(routes) is not list or len(routes) != 2 or len(set(routes)) != 2
            or type(contexts) is not list or len(contexts) != 4 or len(set(contexts)) != 4
            or any(type(item) is not str or not item for item in routes + contexts)
        ):
            raise BundleRefusal("public stream route/context support is malformed")
        derangement = stream["matched_derangement"]
        if type(derangement) is not dict or set(derangement) != set(contexts) or set(derangement.values()) != set(contexts) or any(source == target for source, target in derangement.items()):
            raise BundleRefusal("public stream matched derangement is not exact fixed-point-free support")
        training, heldout = stream["training"], stream["heldout"]
        if type(training) is not list or type(heldout) is not list or len(training) != 8 or len(heldout) != 8:
            raise BundleRefusal("each public stream must contain exactly eight training and eight heldout episodes")
        forced_pairs: set[tuple[str, str]] = set()
        heldout_context_count = {context: 0 for context in contexts}
        positional_balance = [{arm: 0 for arm in ARMS} for _ in ARMS]
        for phase, group in (("training", training), ("heldout", heldout)):
            for position, raw_episode in enumerate(group):
                episode = _check_episode(raw_episode, stream, phase, f"public {expected_stream_id}.{phase}[{position}]")
                episode_id = str(episode["episode_id"])
                if episode_id in episodes:
                    raise BundleRefusal("public manifest repeats an episode ID")
                episodes[episode_id] = episode
                stream_by_episode[episode_id] = stream
                if phase == "training":
                    forced_pairs.add((str(episode["context_key"]), str(episode["forced_route_id"])))
                else:
                    heldout_context_count[str(episode["context_key"])] += 1
                    arm_order = episode["arm_order"]
                    for arm_position, arm in enumerate(arm_order):
                        positional_balance[arm_position][arm] += 1
        if forced_pairs != {(context, route) for context in contexts for route in routes}:
            raise BundleRefusal("public training forced-exposure support is incomplete")
        if any(count != 2 for count in heldout_context_count.values()) or any(
            sorted(values.values()) != [2, 3, 3] for values in positional_balance
        ):
            raise BundleRefusal("public heldout context or arm-order support is unbalanced")

        raw_binding = private_top["private_bindings"][index]
        binding = _check_exact_keys(raw_binding, {"stream_id", "context_correct_route"}, f"private binding[{index}]")
        if binding["stream_id"] != expected_stream_id:
            raise BundleRefusal("private/public stream binding order mismatch")
        correct = binding["context_correct_route"]
        if type(correct) is not dict or set(correct) != set(contexts) or any(route not in routes for route in correct.values()):
            raise BundleRefusal("private correct-route support is malformed")
        if [correct[context] for context in contexts].count(routes[0]) != 2 or [correct[context] for context in contexts].count(routes[1]) != 2:
            raise BundleRefusal("private correct routes are not 2/2 balanced")
        bindings[expected_stream_id] = binding

    # Recompute the public training/heldout leakage indicators.  The historical
    # repository scan is source-A evidence outside the generated task payload;
    # no unretained boolean can create a GO here.
    training_episodes = [episode for episode in episodes.values() if episode["phase"] == "training"]
    heldout_episodes = [episode for episode in episodes.values() if episode["phase"] == "heldout"]
    for field in ("episode_id", "entity", "surface_template", "prompt"):
        left = {_normalize(str(item[field])) for item in training_episodes}
        right = {_normalize(str(item[field])) for item in heldout_episodes}
        if left & right:
            raise BundleRefusal(f"public manifest has training/heldout normalized {field} leakage")
    return episodes, stream_by_episode, bindings


def _check_episode(
    value: object, stream: Mapping[str, Any], phase: str, label: str
) -> Mapping[str, Any]:
    required = {
        "episode_id", "stream_id", "phase", "context_key", "candidate_route_ids", "entity", "aliases",
        "surface_template", "prompt", "route_evidence",
    }
    phase_fields = (
        {"forced_route_id", "provenance_canary"}
        if phase == "training"
        else {"arm_order"}
    )
    episode = _check_exact_keys(value, required | phase_fields, label)
    if (
        episode["stream_id"] != stream["stream_id"]
        or episode["phase"] != phase
        or episode["context_key"] not in stream["context_keys"]
        or episode["candidate_route_ids"] != stream["route_ids"]
    ):
        raise BundleRefusal(f"{label} does not retain exact stream support")
    for key in ("episode_id", "entity", "surface_template", "prompt"):
        _string(episode[key], f"{label}.{key}")
    if "return a JSON object whose only field is response_token from selected evidence." not in episode["prompt"]:
        raise BundleRefusal(f"{label} does not retain the frozen structured response instruction")
    if type(episode["aliases"]) is not list or not episode["aliases"] or any(type(alias) is not str or not alias for alias in episode["aliases"]):
        raise BundleRefusal(f"{label}.aliases is malformed")
    evidence = episode["route_evidence"]
    if type(evidence) is not list or len(evidence) != 2:
        raise BundleRefusal(f"{label}.route_evidence must contain exact two route records")
    seen: set[str] = set()
    for evidence_index, raw_record in enumerate(evidence):
        record = _check_exact_keys(raw_record, {"route_id", "evidence_text", "response_token"}, f"{label}.route_evidence[{evidence_index}]")
        route = _string(record["route_id"], f"{label}.route_evidence[{evidence_index}].route_id")
        if route not in stream["route_ids"] or route in seen:
            raise BundleRefusal(f"{label}.route_evidence has invalid route support")
        seen.add(route)
        text, token = _string(record["evidence_text"], f"{label}.evidence_text"), _string(record["response_token"], f"{label}.response_token")
        if RESPONSE_TOKEN_RE.fullmatch(token) is None or len(token.encode("ascii")) != 26:
            raise BundleRefusal(f"{label}.route_evidence response token violates exact DNRD-4S1 form")
        if route not in text or token not in text:
            raise BundleRefusal(f"{label}.route_evidence does not bind route/token")
    if [record["route_id"] for record in evidence] != stream["route_ids"]:
        raise BundleRefusal(f"{label}.route_evidence route order drifted")
    if phase == "training":
        if episode["forced_route_id"] not in stream["route_ids"]:
            raise BundleRefusal(f"{label}.forced_route_id is outside route support")
        canary = _string(episode["provenance_canary"], f"{label}.provenance_canary")
        if (
            not canary.startswith(TRAINING_CANARY_PREFIX)
            or episode["prompt"].count(canary) != 1
            or not episode["prompt"].endswith(f"\nTraining provenance marker: {canary}")
        ):
            raise BundleRefusal(f"{label}.provenance_canary is not confined to its declared training prompt")
    else:
        if type(episode["arm_order"]) is not list or len(episode["arm_order"]) != 3 or set(episode["arm_order"]) != set(ARMS):
            raise BundleRefusal(f"{label}.arm_order must be one exact three-arm permutation")
    return episode


def _scores_from_state_entry(
    value: object, stream: Mapping[str, Any], arm: str, label: str
) -> tuple[Mapping[str, Mapping[str, int]], Mapping[str, Any]]:
    entry = _check_exact_keys(
        value,
        {
            "mount_id", "mount_role", "state_sha256", "routing_payload_utf8", "routing_payload_sha256", "routing_payload_bytes",
            "score_projection_utf8", "score_projection_sha256", "score_projection_bytes",
        },
        label,
    )
    _string(entry["mount_id"], f"{label}.mount_id")
    if entry["mount_role"] != MOUNT_ROLES[arm]:
        raise BundleRefusal(f"{label}.mount_role does not match the frozen {arm} arm role")
    _sha(entry["state_sha256"], f"{label}.state_sha256")
    durable_text = _string(entry["routing_payload_utf8"], f"{label}.routing_payload_utf8")
    durable_bytes = durable_text.encode("utf-8")
    if entry["routing_payload_bytes"] != len(durable_bytes) or entry["routing_payload_bytes"] <= 0:
        raise BundleRefusal(f"{label}.routing_payload_bytes mismatch")
    if (
        _sha_bytes(durable_bytes) != _sha(entry["routing_payload_sha256"], f"{label}.routing_payload_sha256")
        or entry["state_sha256"] != entry["routing_payload_sha256"]
    ):
        raise BundleRefusal(f"{label}.routing_payload_sha256 mismatch")
    durable = _parse_json_bytes(durable_bytes, f"{label}.routing_payload_utf8", canonical=True)
    durable_data = _check_exact_keys(durable, {"schemaVersion", "contexts", "structuralStatus"}, f"{label}.routing_payload")
    if (
        durable_data["schemaVersion"] != "hswm-dnrd-routing-payload/v1"
        or durable_data["structuralStatus"]
        != "LOCAL_EXPERIMENTAL_ROUTING_PAYLOAD_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
        or type(durable_data["contexts"]) is not list
        or len(durable_data["contexts"]) != len(stream["context_keys"])
    ):
        raise BundleRefusal(f"{label}.routing_payload is not an exact DNRD durable routing payload")
    context_by_digest = {
        _sha_bytes(context.encode("utf-8")): context for context in stream["context_keys"]
    }
    expected_stratum = f"stratum:{_sha_bytes(str(stream['stream_id']).encode('utf-8'))}"
    durable_scores: dict[str, dict[str, int]] = {}
    previous_context_key = ""
    for context_index, raw_context in enumerate(durable_data["contexts"]):
        context = _check_exact_keys(raw_context, {"contextSha256", "stratum", "routes"}, f"{label}.routing_payload.contexts[{context_index}]")
        context_sha = _sha(context["contextSha256"], f"{label}.routing_payload.contexts[{context_index}].contextSha256")
        context_key = f"{_string(context['stratum'], f'{label}.routing_payload.contexts[{context_index}].stratum')}\0{context_sha}"
        if context_key <= previous_context_key or context["stratum"] != expected_stratum or context_sha not in context_by_digest:
            raise BundleRefusal(f"{label}.routing_payload context ordering/support mismatch")
        previous_context_key = context_key
        raw_routes = context["routes"]
        if type(raw_routes) is not list or len(raw_routes) != len(stream["route_ids"]):
            raise BundleRefusal(f"{label}.routing_payload route count mismatch")
        route_scores: dict[str, int] = {}
        previous_route = ""
        for route_index, raw_route in enumerate(raw_routes):
            route = _check_exact_keys(raw_route, {"routeId", "scoreMicros"}, f"{label}.routing_payload.routes[{route_index}]")
            route_id = _strict_identifier(route["routeId"], f"{label}.routing_payload.routes[{route_index}].routeId")
            score = route["scoreMicros"]
            if route_id <= previous_route or route_id not in stream["route_ids"] or type(score) is not int or score < -100_000 or score > 100_000:
                raise BundleRefusal(f"{label}.routing_payload route ordering/score mismatch")
            previous_route = route_id
            route_scores[route_id] = score
        if set(route_scores) != set(stream["route_ids"]):
            raise BundleRefusal(f"{label}.routing_payload route support mismatch")
        durable_scores[context_by_digest[context_sha]] = route_scores
    if set(durable_scores) != set(stream["context_keys"]):
        raise BundleRefusal(f"{label}.routing_payload durable context support mismatch")
    projection_text = _string(entry["score_projection_utf8"], f"{label}.score_projection_utf8")
    projection_bytes = projection_text.encode("utf-8")
    if entry["score_projection_bytes"] != len(projection_bytes) or entry["score_projection_bytes"] <= 0:
        raise BundleRefusal(f"{label}.score_projection_bytes mismatch")
    if _sha_bytes(projection_bytes) != _sha(entry["score_projection_sha256"], f"{label}.score_projection_sha256"):
        raise BundleRefusal(f"{label}.score_projection_sha256 mismatch")
    payload = _parse_json_bytes(projection_bytes, f"{label}.score_projection_utf8", canonical=True)
    data = _check_exact_keys(payload, {"scores"}, f"{label}.score_projection")
    scores = data["scores"]
    if type(scores) is not dict or set(scores) != set(stream["context_keys"]):
        raise BundleRefusal(f"{label}.scores context support mismatch")
    frozen: dict[str, Mapping[str, int]] = {}
    for context in stream["context_keys"]:
        route_scores = scores[context]
        if type(route_scores) is not dict or set(route_scores) != set(stream["route_ids"]):
            raise BundleRefusal(f"{label}.scores route support mismatch")
        if any(type(score) is not int or score < -100_000 or score > 100_000 for score in route_scores.values()):
            raise BundleRefusal(f"{label}.scores contains out-of-range numeric score")
        frozen[context] = dict(route_scores)
    if frozen != durable_scores:
        raise BundleRefusal(f"{label}.score projection does not exactly rederive retained durable routing payload")
    return frozen, entry


def _route_digest(context_key: str, route: str, score: int) -> str:
    return _canonical_hash({"context_key": context_key, "selected_route_id": route, "score": score})


def _select(scores: Mapping[str, Mapping[str, int]], episode: Mapping[str, Any]) -> str:
    context = str(episode["context_key"])
    return sorted(episode["candidate_route_ids"], key=lambda route: (-scores[context][route], route))[0]


def _expected_prompt(episode: Mapping[str, Any], route: str) -> str:
    matching = [record for record in episode["route_evidence"] if record["route_id"] == route]
    if len(matching) != 1:
        raise BundleRefusal("public episode has no unique selected route evidence")
    return f"{episode['prompt']}\nSelected evidence:\n{matching[0]['evidence_text']}"


def _model_request_digest(request: Mapping[str, Any]) -> str:
    value = _check_exact_keys(
        request,
        {
            "episode_id", "selected_route_id", "prompt", "max_output_tokens",
            "ordinal", "phase", "arm", "candidate_response_tokens", "pre_dispatch_receipt_sha256",
        },
        "model request",
    )
    for key in ("episode_id", "selected_route_id", "prompt"):
        _string(value[key], f"model request.{key}")
    ordinal = _integer(value["ordinal"], "model request.ordinal", minimum=1)
    phase, arm = value["phase"], value["arm"]
    if (
        value["max_output_tokens"] != MAX_OUTPUT_TOKENS
        or phase not in {"training", "heldout"}
        or (phase == "training" and arm is not None)
        or (phase == "heldout" and arm not in ARMS)
        or (ordinal <= 32 and phase != "training")
        or (ordinal > 32 and phase != "heldout")
    ):
        raise BundleRefusal("model request identity/configuration violates the frozen schedule")
    _candidate_response_tokens(value["candidate_response_tokens"], "model request.candidate_response_tokens")
    _sha(value["pre_dispatch_receipt_sha256"], "model request.pre_dispatch_receipt_sha256")
    return _canonical_hash(dict(value))


def _candidate_response_tokens(value: object, label: str) -> tuple[str, str]:
    if type(value) is not list or len(value) != 2 or any(type(token) is not str for token in value):
        raise BundleRefusal(f"{label} must contain exactly two response tokens")
    first, second = value
    if (
        RESPONSE_TOKEN_RE.fullmatch(first) is None
        or RESPONSE_TOKEN_RE.fullmatch(second) is None
        or first >= second
    ):
        raise BundleRefusal(f"{label} must contain distinct lexically sorted DNRD-4S1 response tokens")
    return first, second


def _structured_response_token(content: str, candidates: tuple[str, str]) -> str:
    def no_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate object key")
            result[key] = value
        return result

    try:
        value = json.loads(
            content,
            object_pairs_hook=no_duplicate_object_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("non-finite number")),
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise BundleRefusal("accepted model body is not one strict structured JSON response") from error
    if type(value) is not dict or set(value) != {"response_token"}:
        raise BundleRefusal("accepted model body structured response has an invalid key set")
    token = value["response_token"]
    if type(token) is not str or RESPONSE_TOKEN_RE.fullmatch(token) is None:
        raise BundleRefusal("accepted model body structured response token violates DNRD-4S1 form")
    if token not in candidates:
        raise BundleRefusal("accepted model body structured response token is outside its request candidates")
    return token


def _response_digest_from_raw(
    raw_text: str, model: str, candidates: tuple[str, str]
) -> tuple[str, str, int, int, Mapping[str, int]]:
    raw = _parse_json_bytes(raw_text.encode("utf-8"), "accepted model raw response", canonical=False)
    if type(raw) is not dict or raw.get("model") != model:
        raise BundleRefusal("accepted model body does not attest frozen served model")
    choices = raw.get("choices")
    if type(choices) is not list or len(choices) != 1 or type(choices[0]) is not dict:
        raise BundleRefusal("accepted model body must contain exactly one choice")
    choice = choices[0]
    message = choice.get("message")
    if choice.get("finish_reason") != "stop" or type(message) is not dict or type(message.get("content")) is not str:
        raise BundleRefusal("accepted model body choice is not an exact stopped textual completion")
    token = _structured_response_token(message["content"], candidates)
    usage = raw.get("usage")
    if type(usage) is not dict:
        raise BundleRefusal("accepted model body lacks usage")
    prompt_tokens, completion_tokens, total_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens"), usage.get("total_tokens")
    if any(type(value) is not int or value < 0 for value in (prompt_tokens, completion_tokens, total_tokens)) or total_tokens != prompt_tokens + completion_tokens:
        raise BundleRefusal("accepted model body usage arithmetic is invalid")
    extra = {
        key: value for key, value in usage.items()
        if key not in {"prompt_tokens", "completion_tokens", "total_tokens"} and type(key) is str and type(value) is int and value >= 0
    }
    response = {
        "response_token": token,
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "client_cache_hit": False,
        "server_usage": extra,
    }
    return _canonical_hash(response), token, prompt_tokens, completion_tokens, extra


def _structured_chat_config(value: object, label: str) -> tuple[Mapping[str, Any], tuple[str, str]]:
    """Validate the complete DNRD-4S1 provider constraint retained per event."""
    if type(value) is not dict:
        raise BundleRefusal(f"{label} must be an object")
    response_format = value.get("response_format")
    if type(response_format) is not dict:
        raise BundleRefusal(f"{label}.response_format must be an object")
    json_schema = response_format.get("json_schema")
    if type(json_schema) is not dict:
        raise BundleRefusal(f"{label}.response_format.json_schema must be an object")
    schema = json_schema.get("schema")
    if type(schema) is not dict:
        raise BundleRefusal(f"{label}.response_format.json_schema.schema must be an object")
    token_schema = schema.get("properties", {}).get("response_token") if type(schema.get("properties")) is dict else None
    candidates = _candidate_response_tokens(
        token_schema.get("enum") if type(token_schema) is dict else None,
        f"{label}.response_format.json_schema.schema.properties.response_token.enum",
    )
    expected_schema = {
        "type": "object",
        "properties": {
            "response_token": {
                "type": "string",
                "enum": list(candidates),
                "pattern": r"^token-[0-9a-f]{20}$",
                "minLength": 26,
                "maxLength": 26,
            },
        },
        "required": ["response_token"],
        "additionalProperties": False,
    }
    expected_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "hswm_dnrd_response_token",
            "strict": True,
            "schema": expected_schema,
        },
    }
    expected = {
        "chat_template_kwargs": {"enable_thinking": False},
        "logprobs": False,
        "n": 1,
        "stream": False,
        "temperature": 0,
        "top_p": 1,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "response_format": expected_format,
        "response_format_schema_sha256": _canonical_hash(expected_schema),
    }
    if value != expected:
        raise BundleRefusal(f"{label} differs from the frozen DNRD-4S1 structured-output contract")
    return value, candidates


def _validate_trace(
    trace: object,
    *,
    request: Mapping[str, Any],
    episode: Mapping[str, Any],
    route: str,
    expected_state_sha256: str,
    expected_score: int,
    expected_response_sha256: str,
    label: str,
) -> Mapping[str, Any]:
    data = _check_exact_keys(
        trace,
        {
            "trace_id", "episode_id", "context_key", "context_sha256", "stratum", "selected_route_id",
            "pre_outcome_score_micros", "routing_payload_sha256", "request_sha256", "response_sha256", "status",
        },
        label,
    )
    for key in ("trace_id", "context_sha256", "routing_payload_sha256", "request_sha256", "response_sha256"):
        _sha(data[key], f"{label}.{key}")
    if (
        data["episode_id"] != episode["episode_id"]
        or data["context_key"] != episode["context_key"]
        or data["context_sha256"] != _sha_bytes(str(episode["context_key"]).encode("utf-8"))
        or data["selected_route_id"] != route
        or data["routing_payload_sha256"] != expected_state_sha256
        or data["request_sha256"] != _model_request_digest(request)
        or data["response_sha256"] != expected_response_sha256
        or data["status"] != TRACE_STATUS
        or data["pre_outcome_score_micros"] != expected_score
    ):
        raise BundleRefusal(f"{label} does not bind exact state/request/response/route score")
    stratum = _string(data["stratum"], f"{label}.stratum")
    expected_stratum = f"stratum:{_sha_bytes(str(episode['stream_id']).encode('utf-8'))}"
    if stratum != expected_stratum:
        raise BundleRefusal(f"{label}.stratum does not replay frozen stream stratum")
    expected_trace_id = _canonical_hash(
        {
            "schemaVersion": "hswm-dnrd-eligibility-trace/v1",
            "episodeId": episode["episode_id"],
            "routingPayloadSha256": expected_state_sha256,
            "contextSha256": data["context_sha256"],
            "stratum": stratum,
            "routeId": route,
            "preOutcomeScoreMicros": expected_score,
            "requestSha256": data["request_sha256"],
            "responseSha256": expected_response_sha256,
            "status": TRACE_STATUS,
        }
    )
    if data["trace_id"] != expected_trace_id:
        raise BundleRefusal(f"{label}.trace_id does not reproduce frozen eligibility-trace commitment")
    return data


def _validate_sealed_and_outcome(
    sealed: object,
    outcome: object,
    *,
    episode: Mapping[str, Any],
    route: str,
    private_binding: Mapping[str, Any],
    private_commitment: str,
    scorer_sha256: str,
    answer: str,
    label: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    sealed_data = _check_exact_keys(
        sealed,
        {"schema_version", "episode_id", "selected_route_id", "answer", "private_manifest_commitment", "response_commitment"},
        f"{label}.sealed_response",
    )
    unsigned = {key: value for key, value in sealed_data.items() if key != "response_commitment"}
    if (
        sealed_data["schema_version"] != "hswm-dnrd-sealed-response/v2"
        or sealed_data["episode_id"] != episode["episode_id"]
        or sealed_data["selected_route_id"] != route
        or sealed_data["answer"] != answer
        or sealed_data["private_manifest_commitment"] != private_commitment
        or sealed_data["response_commitment"] != _canonical_hash(unsigned)
    ):
        raise BundleRefusal(f"{label}.sealed_response is not bound to the actual model response/private manifest")
    outcome_data = _check_exact_keys(
        outcome,
        {"episode_id", "selected_route_id", "reward", "outcome_digest", "scorer_source_identity", "scorer_address", "role_separation"},
        f"{label}.scorer_outcome",
    )
    if (
        outcome_data["episode_id"] != episode["episode_id"]
        or outcome_data["selected_route_id"] != route
        or outcome_data["scorer_source_identity"] != scorer_sha256
        or outcome_data["scorer_address"] != "_research/dnrd/scorer.py"
        or outcome_data["role_separation"] != SCORER_ROLE_SEPARATION
    ):
        raise BundleRefusal(f"{label}.scorer_outcome scorer provenance mismatch")
    reward = _reward(outcome_data["reward"], f"{label}.scorer_outcome.reward")
    correct_route = private_binding["context_correct_route"][episode["context_key"]]
    expected_reward = 1_000_000 if route == correct_route else -1_000_000
    if reward != expected_reward:
        raise BundleRefusal(f"{label}.scorer_outcome reward does not replay from retained private scorer manifest")
    expected_digest = _canonical_hash(
        {
            "episode_id": episode["episode_id"],
            "selected_route_id": route,
            "private_manifest_commitment": private_commitment,
            "reward": reward,
            "scorer_source_identity": scorer_sha256,
        }
    )
    if outcome_data["outcome_digest"] != expected_digest:
        raise BundleRefusal(f"{label}.scorer_outcome digest does not bind the response-independent route/scorer/reward basis")
    return sealed_data, outcome_data


def _validate_credit_receipt(
    receipt: object,
    *,
    trace: Mapping[str, Any],
    outcome: Mapping[str, Any],
    expected_before: str,
    consumed: set[str],
    label: str,
) -> tuple[str, str]:
    data = _check_exact_keys(
        receipt,
        {"credit_receipt", "observation", "scorer_provenance", "status"},
        label,
    )
    if data["status"] != "LOCAL_EXPERIMENTAL_STRUCTURAL_OUTCOME_RECEIPT_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING":
        raise BundleRefusal(f"{label}.status is not frozen local experimental outcome status")
    provenance = _check_exact_keys(data["scorer_provenance"], {"scorer_address", "scorer_source_identity", "role_separation"}, f"{label}.scorer_provenance")
    if (
        provenance["scorer_address"] != outcome["scorer_address"]
        or provenance["scorer_source_identity"] != outcome["scorer_source_identity"]
        or provenance["role_separation"] != outcome["role_separation"]
    ):
        raise BundleRefusal(f"{label}.scorer_provenance does not match scorer outcome")
    observation = _check_exact_keys(
        data["observation"],
        {
            "schemaVersion", "traceId", "producerAddress", "scorerAddress", "outcomeScoreMicros",
            "scorerProvenanceAddress", "scorerSourceSha256", "scorerObservationSha256", "independence", "status", "outcomeId",
        },
        f"{label}.observation",
    )
    observation_unsigned = {key: value for key, value in observation.items() if key != "outcomeId"}
    if (
        observation["schemaVersion"] != "hswm-dnrd-outcome-observation/v1"
        or observation["traceId"] != trace["trace_id"]
        or observation["producerAddress"] != "principal:dnrd-producer"
        or observation["scorerAddress"] != "principal:dnrd-scorer"
        or observation["scorerProvenanceAddress"] != "repo:_research/dnrd/scorer.py"
        or observation["scorerSourceSha256"] != outcome["scorer_source_identity"]
        or observation["outcomeScoreMicros"] != outcome["reward"]
        or observation["scorerObservationSha256"] != outcome["outcome_digest"]
        or observation["independence"] != "DECLARED_ROLE_SEPARATION_NOT_INDEPENDENTLY_PROVEN"
        or observation["status"] != "LOCAL_EXPERIMENTAL_OUTCOME_NOT_EXTERNAL_TRUTH_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
        or observation["outcomeId"] != _canonical_hash(observation_unsigned)
    ):
        raise BundleRefusal(f"{label}.observation does not bind exact trace/outcome")
    credit = _check_exact_keys(
        data["credit_receipt"],
        {
            "schemaVersion", "outcomeId", "traceId", "beforePayloadSha256", "afterPayloadSha256",
            "deltaMicros", "updatedRouteCount", "consumedOutcomeIds", "status",
        },
        f"{label}.credit_receipt",
    )
    expected_consumed = sorted([*consumed, observation["outcomeId"]])
    if (
        credit["schemaVersion"] != "hswm-dnrd-credit-receipt/v1"
        or credit["outcomeId"] != observation["outcomeId"]
        or credit["traceId"] != trace["trace_id"]
        or credit["beforePayloadSha256"] != expected_before
        or credit["deltaMicros"] != outcome["reward"] * 100_000 // 1_000_000
        or credit["updatedRouteCount"] != 1
        or credit["consumedOutcomeIds"] != expected_consumed
        or credit["status"] != "LOCAL_EXPERIMENTAL_STRUCTURAL_CREDIT_NOT_CANONICAL_PERMIT_NOT_ADMISSION_NOT_LEARNING"
    ):
        raise BundleRefusal(f"{label}.credit_receipt violates frozen one-trace/one-outcome credit rule")
    _sha(credit["afterPayloadSha256"], f"{label}.credit_receipt.afterPayloadSha256")
    return str(credit["afterPayloadSha256"]), str(observation["outcomeId"])


def _reconcile_model_events(
    model_events: Sequence[Mapping[str, Any]],
    runner_events: Sequence[Mapping[str, Any]],
    *,
    endpoint: str,
    model: str,
    chat_config: Mapping[str, Any],
) -> Mapping[str, Mapping[str, Any]]:
    # The durable runner ledger retains one PRE row and one completed row per
    # successful call.  Only the completed row has a model-bound request.
    runner_events = [
        item for item in runner_events
        if item.get("event") == "COMPLETED_CALL"
    ]
    if len(model_events) != 256:
        raise BundleRefusal("complete candidate requires exactly 256 observed+accepted model boundary events")
    chat_endpoint = f"{endpoint.rstrip('/')}/v1/chat/completions"
    expected_common = {
        "schema_version", "event", "ordinal", "phase", "arm", "dnrd_request_sha256", "endpoint", "model",
        "request_sha256", "raw_response_sha256", "chat_config", "elapsed_nanoseconds", "provider_cache_independence",
    }
    observed: dict[str, Mapping[str, Any]] = {}
    accepted: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(model_events):
        name = item.get("event")
        if name == "CHAT_COMPLETION_OBSERVED":
            value = _check_exact_keys(item, expected_common | {"http_status"}, f"model_events[{index}]")
            target = observed
        elif name == "CHAT_COMPLETION_ACCEPTED":
            value = _check_exact_keys(item, expected_common | {"usage", "dnrd_response_sha256", "raw_response_utf8"}, f"model_events[{index}]")
            target = accepted
        else:
            raise BundleRefusal("complete candidate model ledger may contain only observed and accepted calls")
        ordinal = _integer(value["ordinal"], f"model_events[{index}].ordinal", minimum=1)
        phase, arm = value["phase"], value["arm"]
        if phase not in {"training", "heldout"} or (phase == "training" and arm is not None) or (phase == "heldout" and arm not in ARMS):
            raise BundleRefusal("model event phase/arm identity is malformed")
        request_id = _sha(value["dnrd_request_sha256"], f"model_events[{index}].dnrd_request_sha256")
        if (
            value["schema_version"] != LIVE_EVENT_SCHEMA
            or value["endpoint"] != chat_endpoint
            or value["model"] != model
            or value["provider_cache_independence"] != PROVIDER_CACHE_UNOBSERVABLE
            or type(value["elapsed_nanoseconds"]) is not int
            or value["elapsed_nanoseconds"] < 0
        ):
            raise BundleRefusal("model event live-boundary identity/configuration mismatch")
        _, event_candidates = _structured_chat_config(
            value["chat_config"], f"model_events[{index}].chat_config"
        )
        _sha(value["request_sha256"], f"model_events[{index}].request_sha256")
        _sha(value["raw_response_sha256"], f"model_events[{index}].raw_response_sha256")
        if name == "CHAT_COMPLETION_OBSERVED":
            if type(value["http_status"]) is not int or not 200 <= value["http_status"] < 300:
                raise BundleRefusal("observed model response must retain successful exact HTTP status")
        else:
            raw = _string(value["raw_response_utf8"], f"model_events[{index}].raw_response_utf8")
            if _sha_bytes(raw.encode("utf-8")) != value["raw_response_sha256"]:
                raise BundleRefusal("accepted model raw body digest mismatch")
            response_digest, _, prompt_tokens, completion_tokens, extra = _response_digest_from_raw(raw, model, event_candidates)
            if value["dnrd_response_sha256"] != response_digest:
                raise BundleRefusal("accepted model response digest does not replay from raw body")
            expected_usage = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, **extra}
            if value["usage"] != expected_usage:
                raise BundleRefusal("accepted model usage event does not replay from raw body")
        if request_id in target:
            raise BundleRefusal("model event ledger repeats one observed/accepted DNRD call")
        target[request_id] = value

    expected_calls: dict[str, Mapping[str, Any]] = {}
    for index, event in enumerate(runner_events):
        request = event.get("request")
        if type(request) is not dict:
            raise BundleRefusal(f"runner_events[{index}] has no request object")
        request_id = _model_request_digest(request)
        if request_id in expected_calls:
            raise BundleRefusal("runner ledger repeats a DNRD request identity")
        expected_calls[request_id] = event
    if set(observed) != set(expected_calls) or set(accepted) != set(expected_calls):
        raise BundleRefusal("model event ledger does not exactly cover every runner event")
    for request_id, runner_event in expected_calls.items():
        request = runner_event["request"]
        body = {
            "chat_template_kwargs": {"enable_thinking": False},
            "max_tokens": MAX_OUTPUT_TOKENS,
            "messages": [{"content": request["prompt"], "role": "user"}],
            "model": model,
            "n": 1,
            "stream": False,
            "temperature": 0,
            "top_p": 1,
            "logprobs": False,
            "response_format": _structured_chat_config(
                observed[request_id]["chat_config"], "observed event chat_config"
            )[0]["response_format"],
        }
        expected_body_hash = _sha_bytes(_canonical_bytes(body))
        trace = runner_event.get("trace")
        if type(trace) is not dict:
            raise BundleRefusal("runner event trace is not an object")
        for event in (observed[request_id], accepted[request_id]):
            if (
                event["ordinal"] != request["ordinal"]
                or event["phase"] != request["phase"]
                or event["arm"] != request["arm"]
                or event["request_sha256"] != expected_body_hash
                or _structured_chat_config(event["chat_config"], "model event chat_config")[1]
                != _candidate_response_tokens(request["candidate_response_tokens"], "runner request.candidate_response_tokens")
            ):
                raise BundleRefusal("model event does not bind exact runner request/provider body")
        if accepted[request_id]["dnrd_response_sha256"] != trace.get("response_sha256"):
            raise BundleRefusal("accepted model event response digest does not bind bridge trace")
        if observed[request_id]["raw_response_sha256"] != accepted[request_id]["raw_response_sha256"]:
            raise BundleRefusal("observed and accepted model event raw-response digest mismatch")
    return accepted


_REJECTED_RESPONSE_FIXED_MESSAGES = {
    "chat completion is not UTF-8 JSON": "CHAT_COMPLETION_NOT_UTF8_JSON",
    "chat completion must be a JSON object": "CHAT_COMPLETION_NOT_OBJECT",
    "chat completion model does not match frozen DNRD model": "MODEL_ID_MISMATCH",
    "chat completion must contain exactly one object choice": "CHOICE_CARDINALITY",
    "chat completion choice must finish with exact reason 'stop'": "FINISH_REASON_NOT_STOP",
    "chat completion choice must contain textual message.content": "MESSAGE_CONTENT_NOT_TEXT",
    "chat completion structured response is not strict JSON": "STRUCTURED_RESPONSE_NOT_STRICT_JSON",
    "chat completion structured response must be an object with exactly response_token": "STRUCTURED_RESPONSE_KEYSET_INVALID",
    "chat completion structured response_token violates exact DNRD-4S1 form": "RESPONSE_TOKEN_FORM_INVALID",
    "chat completion structured response_token is not one of the request candidates": "RESPONSE_TOKEN_NOT_REQUEST_CANDIDATE",
    "chat completion must contain object usage": "USAGE_NOT_OBJECT",
    "usage.prompt_tokens must be a nonnegative integer": "USAGE_PROMPT_TOKENS_INVALID",
    "usage.completion_tokens must be a nonnegative integer": "USAGE_COMPLETION_TOKENS_INVALID",
    "usage.total_tokens must be a nonnegative integer": "USAGE_TOTAL_TOKENS_INVALID",
    "usage.total_tokens must equal prompt_tokens + completion_tokens": "USAGE_ARITHMETIC_MISMATCH",
    "chat completion response exceeds frozen 1 MiB byte limit": "RESPONSE_BODY_EXCEEDS_1_MIB",
}
_AMBIGUOUS_FAILURE_MESSAGE = "model request outcome is ambiguous or post-dispatch"


def _rejected_response_stage(message: str) -> str | None:
    if re.fullmatch(r"HTTP response status [0-9]+", message, re.ASCII):
        return "HTTP_STATUS_NOT_2XX"
    return _REJECTED_RESPONSE_FIXED_MESSAGES.get(message)


def _inconclusive_call_context(value: Mapping[str, Any], label: str) -> tuple[int, str, str | None, str]:
    """Validate the public identity common to every DNRD-4S1 live event."""
    ordinal = _integer(value["ordinal"], f"{label}.ordinal", minimum=1)
    phase = value["phase"]
    arm = value["arm"]
    if (
        phase not in {"training", "heldout"}
        or (phase == "training" and arm is not None)
        or (phase == "heldout" and arm not in ARMS)
    ):
        raise BundleRefusal(f"{label} phase/arm identity is malformed")
    if (ordinal <= 32 and (phase != "training" or arm is not None)) or (
        ordinal > 32 and (phase != "heldout" or arm not in ARMS)
    ):
        raise BundleRefusal(f"{label} does not match the frozen ordinal phase/arm schedule")
    return ordinal, str(phase), arm, _sha(value["dnrd_request_sha256"], f"{label}.dnrd_request_sha256")


def _validate_inconclusive_ledgers(
    occurrence: Mapping[str, Any],
    runner_events: Sequence[Mapping[str, Any]],
    model_events: Sequence[Mapping[str, Any]],
) -> None:
    """Replay the prefix observed before a post-dispatch DNRD-4S1 interruption.

    An incomplete occurrence cannot replay state/credit effects, but it can
    still prove that its retained boundary ledger is one ordered, no-retry
    prefix.  This deliberately permits no runner event for the failing call:
    a runner event exists only after an accepted response has been sealed.
    """
    calls = _integer(occurrence["calls_completed"], "inconclusive occurrence.calls_completed", minimum=1)
    if not model_events:
        raise BundleRefusal("inconclusive occurrence with dispatched calls must retain model boundary events")
    common = {
        "schema_version", "event", "ordinal", "phase", "arm", "dnrd_request_sha256", "endpoint", "model",
        "request_sha256", "chat_config", "elapsed_nanoseconds", "provider_cache_independence",
    }
    observed_keys = common | {"raw_response_sha256", "http_status"}
    accepted_keys = common | {"raw_response_sha256", "usage", "dnrd_response_sha256", "raw_response_utf8"}
    rejected_keys = common | {
        "raw_response_sha256", "raw_response_encoding", "raw_response_base64", "raw_response_bytes", "http_status",
        "failure_stage_code", "failure_message", "failure_message_sha256",
    }
    ambiguous_keys = common | {"failure_type"}
    # The response-rejected transport variant retains no body because there was
    # no exact HTTP observation to hash.  Its occurrence failure is fixed.
    rejected_oversize_keys = common | {
        "retained_response_prefix_encoding", "retained_response_prefix_base64",
        "retained_response_prefix_sha256", "retained_response_prefix_bytes",
        "response_body_bytes_lower_bound", "http_status", "failure_stage_code",
        "failure_message", "failure_message_sha256",
    }
    transport_rejected_keys = common | {"failure_stage_code", "failure_message", "failure_message_sha256"}
    by_ordinal: dict[int, list[Mapping[str, Any]]] = {}
    failure_message: str | None = None
    last_ordinal = 0
    for index, item in enumerate(model_events):
        if type(item) is not dict:
            raise BundleRefusal(f"model_events[{index}] must be an object")
        name = item.get("event")
        if name == "CHAT_COMPLETION_OBSERVED":
            value = _check_exact_keys(item, observed_keys, f"model_events[{index}]")
        elif name == "CHAT_COMPLETION_ACCEPTED":
            value = _check_exact_keys(item, accepted_keys, f"model_events[{index}]")
        elif name == "CHAT_COMPLETION_REJECTED":
            # Response-size rejection intentionally binds its hash and size but
            # does not expose an unbounded body in the public ledger.
            keys = rejected_oversize_keys if item.get("failure_stage_code") == "RESPONSE_BODY_EXCEEDS_1_MIB" else rejected_keys
            value = _check_exact_keys(item, keys, f"model_events[{index}]")
        elif name == "AMBIGUOUS_OR_POST_DISPATCH_FAILURE":
            value = _check_exact_keys(item, ambiguous_keys, f"model_events[{index}]")
        elif name == "TRANSPORT_RESPONSE_REJECTED":
            value = _check_exact_keys(item, transport_rejected_keys, f"model_events[{index}]")
        else:
            raise BundleRefusal("inconclusive model ledger has an unknown event type")
        ordinal, _, _, _ = _inconclusive_call_context(value, f"model_events[{index}]")
        if ordinal < last_ordinal or ordinal > last_ordinal + 1:
            raise BundleRefusal("inconclusive model ledger ordinals are out of order")
        last_ordinal = ordinal
        if (
            value["schema_version"] != LIVE_EVENT_SCHEMA
            or value["model"] != "qwen3.6-35b-a3b"
            or not isinstance(value["endpoint"], str)
            or not value["endpoint"].endswith("/v1/chat/completions")
            or value["provider_cache_independence"] != PROVIDER_CACHE_UNOBSERVABLE
            or type(value["elapsed_nanoseconds"]) is not int
            or value["elapsed_nanoseconds"] < 0
        ):
            raise BundleRefusal("inconclusive model event live-boundary identity/configuration mismatch")
        _, event_candidates = _structured_chat_config(
            value["chat_config"], f"model_events[{index}].chat_config"
        )
        _sha(value["request_sha256"], f"model_events[{index}].request_sha256")
        if name in {"CHAT_COMPLETION_OBSERVED", "CHAT_COMPLETION_ACCEPTED"} or (
            name == "CHAT_COMPLETION_REJECTED"
            and value["failure_stage_code"] != "RESPONSE_BODY_EXCEEDS_1_MIB"
        ):
            _sha(value["raw_response_sha256"], f"model_events[{index}].raw_response_sha256")
        if name == "CHAT_COMPLETION_OBSERVED" and type(value["http_status"]) is not int:
            raise BundleRefusal("inconclusive observed model event lacks exact HTTP status")
        if name == "CHAT_COMPLETION_ACCEPTED":
            raw = _string(value["raw_response_utf8"], f"model_events[{index}].raw_response_utf8")
            if _sha_bytes(raw.encode("utf-8")) != value["raw_response_sha256"]:
                raise BundleRefusal("inconclusive accepted raw body digest mismatch")
            response_digest, _, prompt_tokens, completion_tokens, extra = _response_digest_from_raw(
                raw, str(value["model"]), event_candidates
            )
            if value["dnrd_response_sha256"] != response_digest or value["usage"] != {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, **extra}:
                raise BundleRefusal("inconclusive accepted model response does not replay from raw body")
        if name == "CHAT_COMPLETION_REJECTED":
            if type(value["http_status"]) is not int:
                raise BundleRefusal("rejected response lacks exact HTTP status")
            message = _string(value["failure_message"], f"model_events[{index}].failure_message")
            if _rejected_response_stage(message) != value["failure_stage_code"]:
                raise BundleRefusal("rejected response message does not derive its frozen failure stage")
            if value["failure_stage_code"] == "HTTP_STATUS_NOT_2XX" and message != f"HTTP response status {value['http_status']}":
                raise BundleRefusal("HTTP rejection message does not bind the observed status")
            if value["failure_stage_code"] == "RESPONSE_BODY_EXCEEDS_1_MIB":
                if (
                    value["retained_response_prefix_encoding"] != "base64"
                    or type(value["retained_response_prefix_base64"]) is not str
                ):
                    raise BundleRefusal("oversize response does not retain a canonical base64 prefix")
                try:
                    prefix = base64.b64decode(value["retained_response_prefix_base64"], validate=True)
                except Exception as error:
                    raise BundleRefusal("oversize response retained prefix base64 is invalid") from error
                if (
                    type(value["retained_response_prefix_bytes"]) is not int
                    or type(value["response_body_bytes_lower_bound"]) is not int
                    or value["retained_response_prefix_bytes"] != len(prefix)
                    or value["retained_response_prefix_bytes"] != 1_048_577
                    or value["response_body_bytes_lower_bound"] != 1_048_577
                    or _sha_bytes(prefix) != _sha(
                        value["retained_response_prefix_sha256"],
                        f"model_events[{index}].retained_response_prefix_sha256",
                    )
                ):
                    raise BundleRefusal("oversize response retained prefix does not bind the frozen byte boundary")
            else:
                if type(value["raw_response_bytes"]) is not int or value["raw_response_bytes"] < 0:
                    raise BundleRefusal("rejected response byte length is invalid")
                if value["raw_response_encoding"] != "base64" or type(value["raw_response_base64"]) is not str:
                    raise BundleRefusal("rejected response does not retain canonical base64 bytes")
                try:
                    raw = base64.b64decode(value["raw_response_base64"], validate=True)
                except Exception as error:
                    raise BundleRefusal("rejected response base64 is invalid") from error
                if value["raw_response_bytes"] != len(raw) or _sha_bytes(raw) != value["raw_response_sha256"]:
                    raise BundleRefusal("rejected response raw bytes/hash do not replay")
            if _sha_bytes(message.encode("utf-8")) != _sha(value["failure_message_sha256"], f"model_events[{index}].failure_message_sha256"):
                raise BundleRefusal("rejected response failure message digest mismatch")
            failure_message = message
        if name == "AMBIGUOUS_OR_POST_DISPATCH_FAILURE":
            _string(value["failure_type"], f"model_events[{index}].failure_type")
            failure_message = _AMBIGUOUS_FAILURE_MESSAGE
        if name == "TRANSPORT_RESPONSE_REJECTED":
            if value["failure_stage_code"] != "TRANSPORT_RESPONSE_NOT_EXACT_HTTP_RESPONSE":
                raise BundleRefusal("transport response rejection has a non-frozen stage code")
            message = _string(value["failure_message"], f"model_events[{index}].failure_message")
            if message != "transport did not return an exact HTTP observation" or _sha_bytes(message.encode("utf-8")) != _sha(value["failure_message_sha256"], f"model_events[{index}].failure_message_sha256"):
                raise BundleRefusal("transport response rejection does not retain fixed failure semantics")
            failure_message = message
        by_ordinal.setdefault(ordinal, []).append(value)

    if set(by_ordinal) != set(range(1, calls + 1)):
        raise BundleRefusal("inconclusive model calls must form ordinal prefix 1..calls_completed")
    terminal_count = 0
    accepted_by_digest: dict[str, Mapping[str, Any]] = {}
    call_request_digests: set[str] = set()
    for ordinal in range(1, calls + 1):
        events = by_ordinal[ordinal]
        names = [event["event"] for event in events]
        identities = {(event["phase"], event["arm"], event["dnrd_request_sha256"], event["endpoint"], event["request_sha256"]) for event in events}
        if len(identities) != 1:
            raise BundleRefusal("inconclusive model call events disagree on exact identity")
        call_request_digest = str(events[0]["dnrd_request_sha256"])
        if call_request_digest in call_request_digests:
            raise BundleRefusal("inconclusive model ledger repeats a request identity across ordinals")
        call_request_digests.add(call_request_digest)
        if names == ["CHAT_COMPLETION_OBSERVED", "CHAT_COMPLETION_ACCEPTED"]:
            if events[0]["raw_response_sha256"] != events[1]["raw_response_sha256"]:
                raise BundleRefusal("observed/accepted raw response digest mismatch")
            digest = str(events[1]["dnrd_request_sha256"])
            if digest in accepted_by_digest:
                raise BundleRefusal("inconclusive model ledger repeats accepted request identity")
            accepted_by_digest[digest] = events[1]
        elif names == ["CHAT_COMPLETION_OBSERVED", "CHAT_COMPLETION_REJECTED"]:
            if events[0]["raw_response_sha256"] != events[1]["raw_response_sha256"]:
                raise BundleRefusal("observed/rejected raw response digest mismatch")
            terminal_count += 1
        elif (
            names == ["CHAT_COMPLETION_REJECTED"]
            and events[0]["failure_stage_code"] == "RESPONSE_BODY_EXCEEDS_1_MIB"
        ):
            terminal_count += 1
        elif names in (["AMBIGUOUS_OR_POST_DISPATCH_FAILURE"], ["TRANSPORT_RESPONSE_REJECTED"]):
            terminal_count += 1
        else:
            raise BundleRefusal("inconclusive model call event ordering is invalid")
    if terminal_count != 1 or by_ordinal[calls][-1]["event"] == "CHAT_COMPLETION_ACCEPTED":
        raise BundleRefusal("inconclusive occurrence must end in exactly one rejected post-dispatch call")
    if failure_message is None or occurrence["failure_digest"] != _canonical_hash({"type": occurrence["failure_type"], "message": failure_message}):
        raise BundleRefusal("inconclusive occurrence failure digest does not bind retained terminal event")

    # Retain durable pre-dispatch provenance even when the following model
    # call does not complete.  Every completed row must immediately follow
    # its PRE row; one final PRE-only row is allowed for the terminal call.
    normalized_runner_events: list[Mapping[str, Any]] = []
    terminal_pre: Mapping[str, Any] | None = None
    cursor = 0
    while cursor < len(runner_events):
        pre = _check_exact_keys(
            runner_events[cursor],
            {"schema_version", "event", "ordinal", "phase", "arm", "request", "pre_dispatch_readout"},
            f"runner_events[{cursor}]",
        )
        if pre["schema_version"] != RUNNER_EVENT_SCHEMA or pre["event"] != "PRE_DISPATCH_READOUT" or pre["request"].get("pre_dispatch_receipt_sha256") is not None:
            raise BundleRefusal("inconclusive runner PRE_DISPATCH_READOUT is malformed")
        pre_receipt = _canonical_hash(pre)
        if cursor + 1 < len(runner_events) and runner_events[cursor + 1].get("event") == "COMPLETED_CALL":
            completed = _check_exact_keys(
                runner_events[cursor + 1],
                {"schema_version", "event", "ordinal", "phase", "arm", "request", "sealed_response", "trace", "scorer_outcome", "credit_receipt", "route_digest_sha256", "pre_dispatch_receipt_sha256", "route_replay"},
                f"runner_events[{cursor + 1}]",
            )
            if (
                completed["schema_version"] != RUNNER_EVENT_SCHEMA
                or completed["ordinal"] != pre["ordinal"]
                or any(completed[key] != pre[key] for key in ("phase", "arm"))
                or completed["pre_dispatch_receipt_sha256"] != pre_receipt
                or completed["request"].get("pre_dispatch_receipt_sha256") != pre_receipt
                or {key: value for key, value in completed["request"].items() if key != "pre_dispatch_receipt_sha256"}
                != {key: value for key, value in pre["request"].items() if key != "pre_dispatch_receipt_sha256"}
            ):
                raise BundleRefusal("inconclusive runner completed row does not bind its pre-dispatch receipt")
            row = dict(completed)
            row.pop("event")
            row.pop("pre_dispatch_receipt_sha256")
            row["pre_dispatch_readout"] = pre["pre_dispatch_readout"]
            normalized_runner_events.append(row)
            cursor += 2
        else:
            if cursor != len(runner_events) - 1:
                raise BundleRefusal("inconclusive runner ledger has a nonterminal PRE-only row")
            terminal_pre = pre
            cursor += 1
    runner_events = normalized_runner_events
    seen_runner_digests: set[str] = set()
    previous_ordinal = 0
    for index, event in enumerate(runner_events):
        runner = _check_exact_keys(
            event,
            {
                "schema_version", "ordinal", "phase", "arm", "request",
                "sealed_response", "trace", "scorer_outcome", "credit_receipt",
                "route_digest_sha256", "pre_dispatch_readout", "route_replay",
            },
            f"runner_events[{index}]",
        )
        request = runner["request"]
        if type(request) is not dict:
            raise BundleRefusal(f"runner_events[{index}] has no request object")
        try:
            digest = _model_request_digest(request)
        except JudgeRefusal as error:
            raise BundleRefusal(f"runner_events[{index}] request is malformed") from error
        ordinal = request.get("ordinal")
        if (
            runner["schema_version"] != RUNNER_EVENT_SCHEMA
            or runner["ordinal"] != ordinal
            or runner["phase"] != request["phase"]
            or runner["arm"] != request["arm"]
            or type(ordinal) is not int
            or ordinal <= previous_ordinal
            or digest in seen_runner_digests
        ):
            raise BundleRefusal("runner events must be an ordered unique accepted-call prefix")
        previous_ordinal = ordinal
        seen_runner_digests.add(digest)
        accepted = accepted_by_digest.get(digest)
        if accepted is None:
            raise BundleRefusal("runner event does not map to an exact accepted model call")
        provider_body = {
            "chat_template_kwargs": {"enable_thinking": False},
            "max_tokens": MAX_OUTPUT_TOKENS,
            "messages": [{"content": request["prompt"], "role": "user"}],
            "model": "qwen3.6-35b-a3b",
            "n": 1,
            "stream": False,
            "temperature": 0,
            "top_p": 1,
            "logprobs": False,
            "response_format": _structured_chat_config(
                accepted["chat_config"],
                "accepted model event chat_config",
            )[0]["response_format"],
        }
        if (
            any(accepted[key] != request[key] for key in ("ordinal", "phase", "arm"))
            or accepted["request_sha256"] != _sha_bytes(_canonical_bytes(provider_body))
        ):
            raise BundleRefusal("runner event does not map to an exact accepted model call")
    if seen_runner_digests != set(accepted_by_digest):
        raise BundleRefusal(
            "runner event identities do not exactly cover accepted prior model calls"
        )
    if terminal_pre is None:
        raise BundleRefusal("inconclusive runner ledger lacks the terminal pre-dispatch receipt")
    terminal_context = by_ordinal[calls][0]
    pre_request = _check_exact_keys(
        terminal_pre["request"],
        {"episode_id", "selected_route_id", "prompt", "max_output_tokens", "ordinal", "phase", "arm", "candidate_response_tokens", "pre_dispatch_receipt_sha256"},
        "terminal PRE_DISPATCH_READOUT.request",
    )
    if terminal_pre["ordinal"] != calls or any(
        terminal_pre[key] != terminal_context[key] for key in ("phase", "arm")
    ) or pre_request["ordinal"] != calls or pre_request["phase"] != terminal_context["phase"] or pre_request["arm"] != terminal_context["arm"]:
        raise BundleRefusal("terminal PRE_DISPATCH_READOUT does not bind the terminal model-call schedule")
    reconstructed_request = dict(pre_request)
    reconstructed_request["pre_dispatch_receipt_sha256"] = _canonical_hash(terminal_pre)
    try:
        terminal_digest = _model_request_digest(reconstructed_request)
    except JudgeRefusal as error:
        raise BundleRefusal("terminal PRE_DISPATCH_READOUT request is malformed") from error
    if terminal_digest != terminal_context["dnrd_request_sha256"]:
        raise BundleRefusal("terminal PRE_DISPATCH_READOUT receipt does not bind the terminal model request")


def _runner_event(
    value: object, *, ordinal: int, phase: str, arm: str | None, episode: Mapping[str, Any], label: str
) -> Mapping[str, Any]:
    event = _check_exact_keys(
        value,
        {
            "schema_version", "ordinal", "phase", "arm", "request", "sealed_response", "trace",
            "scorer_outcome", "credit_receipt", "route_digest_sha256", "route_replay",
            "pre_dispatch_readout",
        },
        label,
    )
    if event["schema_version"] != RUNNER_EVENT_SCHEMA or event["ordinal"] != ordinal or event["phase"] != phase or event["arm"] != arm:
        raise BundleRefusal(f"{label} ordinal/phase/arm does not match frozen global schedule")
    request = _check_exact_keys(
        event["request"],
        {"episode_id", "selected_route_id", "prompt", "max_output_tokens", "ordinal", "phase", "arm", "candidate_response_tokens", "pre_dispatch_receipt_sha256"},
        f"{label}.request",
    )
    if (
        request["episode_id"] != episode["episode_id"]
        or request["ordinal"] != ordinal
        or request["phase"] != phase
        or request["arm"] != arm
        or request["max_output_tokens"] != MAX_OUTPUT_TOKENS
        or request["selected_route_id"] not in episode["candidate_route_ids"]
        or request["prompt"] != _expected_prompt(episode, str(request["selected_route_id"]))
        or _candidate_response_tokens(request["candidate_response_tokens"], f"{label}.request.candidate_response_tokens")
        != tuple(sorted(record["response_token"] for record in episode["route_evidence"]))
    ):
        raise BundleRefusal(f"{label}.request is not a frozen public episode/selected-evidence request")
    _sha(event["route_digest_sha256"], f"{label}.route_digest_sha256")
    readout = _check_exact_keys(
        event["pre_dispatch_readout"],
        {
            "selected_route_id", "route_digest_sha256", "pre_outcome_score_micros",
            "recovery", "routing_payload_sha256",
        },
        f"{label}.pre_dispatch_readout",
    )
    if (
        readout["selected_route_id"] != request["selected_route_id"]
        or readout["route_digest_sha256"] != event["route_digest_sha256"]
    ):
        raise BundleRefusal(f"{label}.pre_dispatch_readout does not bind the selected route")
    _integer(readout["pre_outcome_score_micros"], f"{label}.pre_dispatch_readout.pre_outcome_score_micros")
    _sha(readout["routing_payload_sha256"], f"{label}.pre_dispatch_readout.routing_payload_sha256")
    recovery = _check_exact_keys(
        readout["recovery"],
        {"recovered", "fresh_process", "journal_sha256", "process_instance_id"},
        f"{label}.pre_dispatch_readout.recovery",
    )
    if recovery["recovered"] is not True or recovery["fresh_process"] is not True:
        raise BundleRefusal(f"{label}.pre_dispatch_readout lacks fresh recovery")
    _sha(recovery["journal_sha256"], f"{label}.pre_dispatch_readout.recovery.journal_sha256")
    _process_instance_id(recovery["process_instance_id"], f"{label}.pre_dispatch_readout.recovery.process_instance_id")
    return event


def _copy_scores(scores: Mapping[str, Mapping[str, int]]) -> dict[str, dict[str, int]]:
    return {context: dict(routes) for context, routes in scores.items()}


def _flat_scores(scores: Mapping[str, Mapping[str, int]]) -> list[int]:
    return [scores[context][route] for context in sorted(scores) for route in sorted(scores[context])]


def _reconcile_events_and_state(
    *,
    candidate: Mapping[str, Any],
    public: Mapping[str, Any],
    private: Mapping[str, Any],
    runner_events: Sequence[Mapping[str, Any]],
    accepted_model_events: Mapping[str, Mapping[str, Any]],
    state_evidence: Mapping[str, Any],
    active_state_byte_ceiling: int,
    training_canaries: frozenset[str],
) -> tuple[dict[str, bool], list[dict[str, object]], list[dict[str, object]]]:
    if len(runner_events) != 256:
        raise BundleRefusal("complete candidate requires exactly 128 PRE_DISPATCH_READOUT and 128 COMPLETED_CALL rows")
    completed_rows: list[Mapping[str, Any]] = []
    for ordinal in range(1, 129):
        first, second = runner_events[(ordinal - 1) * 2 : ordinal * 2]
        pre = _check_exact_keys(
            first,
            {"schema_version", "event", "ordinal", "phase", "arm", "request", "pre_dispatch_readout"},
            f"runner_events[{(ordinal - 1) * 2}]",
        )
        completed = _check_exact_keys(
            second,
            {"schema_version", "event", "ordinal", "phase", "arm", "request", "sealed_response", "trace", "scorer_outcome", "credit_receipt", "route_digest_sha256", "pre_dispatch_receipt_sha256", "route_replay"},
            f"runner_events[{(ordinal - 1) * 2 + 1}]",
        )
        if (
            pre["schema_version"] != RUNNER_EVENT_SCHEMA or completed["schema_version"] != RUNNER_EVENT_SCHEMA
            or pre["event"] != "PRE_DISPATCH_READOUT" or completed["event"] != "COMPLETED_CALL"
            or pre["ordinal"] != ordinal or completed["ordinal"] != ordinal
            or any(pre[key] != completed[key] for key in ("phase", "arm"))
            or pre["request"].get("pre_dispatch_receipt_sha256") is not None
            or completed["pre_dispatch_receipt_sha256"] != _canonical_hash(pre)
            or completed["request"].get("pre_dispatch_receipt_sha256") != completed["pre_dispatch_receipt_sha256"]
        ):
            raise BundleRefusal("runner PRE_DISPATCH_READOUT/COMPLETED_CALL linkage is not exact")
        pre_base = {key: value for key, value in pre["request"].items() if key != "pre_dispatch_receipt_sha256"}
        completed_base = {key: value for key, value in completed["request"].items() if key != "pre_dispatch_receipt_sha256"}
        if pre_base != completed_base:
            raise BundleRefusal("completed runner request differs from its pre-dispatch readout request")
        normalized = dict(completed)
        normalized.pop("event")
        normalized.pop("pre_dispatch_receipt_sha256")
        normalized["pre_dispatch_readout"] = pre["pre_dispatch_readout"]
        completed_rows.append(normalized)
    runner_events = completed_rows
    episodes, stream_by_episode, private_bindings = _public_manifest_index(public, private)
    overlap = candidate["overlap"]
    if (
        overlap["training_heldout_exact_overlap"] != 0
        or overlap["training_heldout_normalized_overlap"] != 0
        or overlap["prior_item_overlap"] != 0
    ):
        raise BundleRefusal("candidate overlap projection does not match retained public fixture checks")
    evidence_data = _check_exact_keys(state_evidence, {"schema_version", "streams"}, "bridge state evidence")
    if evidence_data["schema_version"] != "hswm-dnrd-bridge-state-evidence/v2" or type(evidence_data["streams"]) is not list:
        raise BundleRefusal("bridge state evidence schema mismatch")
    public_streams = {stream["stream_id"]: stream for stream in public["streams"]}
    evidence_by_stream: dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(evidence_data["streams"]):
        row = _check_exact_keys(raw, {"stream_id", "pre_evaluation", "post_evaluation", "fixed_rule_replay"}, f"bridge state evidence.streams[{index}]")
        stream_id = _string(row["stream_id"], f"bridge state evidence.streams[{index}].stream_id")
        if stream_id in evidence_by_stream or stream_id not in public_streams:
            raise BundleRefusal("bridge state evidence stream coverage mismatch")
        evidence_by_stream[stream_id] = row
    if set(evidence_by_stream) != set(public_streams):
        raise BundleRefusal("bridge state evidence does not exactly cover public streams")

    candidates = {stream["stream_id"]: stream for stream in candidate["streams"]}
    if set(candidates) != set(public_streams):
        raise BundleRefusal("candidate stream IDs do not match public evidence")
    state_scores: dict[str, dict[str, Mapping[str, int]]] = {}
    state_entries: dict[str, dict[str, Mapping[str, Any]]] = {}
    all_recovery_process_ids: set[str] = set()
    for stream_id, stream in public_streams.items():
        row = evidence_by_stream[stream_id]
        pre = _check_exact_keys(row["pre_evaluation"], {"arms", "fresh_recovery"}, f"bridge state evidence.{stream_id}.pre_evaluation")
        post = _check_exact_keys(row["post_evaluation"], {"arms", "fresh_recovery"}, f"bridge state evidence.{stream_id}.post_evaluation")
        arms = _check_exact_keys(pre["arms"], set(ARMS), f"bridge state evidence.{stream_id}.pre_evaluation.arms")
        recovery = _check_exact_keys(pre["fresh_recovery"], set(ARMS), f"bridge state evidence.{stream_id}.pre_evaluation.fresh_recovery")
        post_arms = _check_exact_keys(post["arms"], set(ARMS), f"bridge state evidence.{stream_id}.post_evaluation.arms")
        post_recovery = _check_exact_keys(post["fresh_recovery"], set(ARMS), f"bridge state evidence.{stream_id}.post_evaluation.fresh_recovery")
        process_ids: set[str] = set()
        state_scores[stream_id] = {}
        state_entries[stream_id] = {}
        for arm in ARMS:
            scores, entry = _scores_from_state_entry(arms[arm], stream, arm, f"bridge state evidence.{stream_id}.{arm}")
            state_scores[stream_id][arm] = scores
            state_entries[stream_id][arm] = entry
            rec = _check_exact_keys(recovery[arm], {"recovered", "fresh_process", "journal_sha256", "process_instance_id"}, f"bridge state evidence.{stream_id}.pre_evaluation.fresh_recovery.{arm}")
            if rec["recovered"] is not True or rec["fresh_process"] is not True:
                raise DiagnosticFailure("DIAGNOSTIC_NO_GO", f"state evidence lacks fresh recovery for {stream_id}/{arm}")
            _sha(rec["journal_sha256"], f"state evidence {stream_id}/{arm} journal")
            pre_process_id = _process_instance_id(rec["process_instance_id"], f"state evidence {stream_id}/{arm} process instance")
            if pre_process_id in process_ids:
                raise DiagnosticFailure("VOID_PROTOCOL", f"state evidence reuses a recovery process instance for {stream_id}")
            process_ids.add(pre_process_id)
            if pre_process_id in all_recovery_process_ids:
                raise DiagnosticFailure("VOID_PROTOCOL", "state evidence reuses a recovery process instance across streams")
            all_recovery_process_ids.add(pre_process_id)
            post_entry = _check_exact_keys(post_arms[arm], set(arms[arm]), f"bridge state evidence.{stream_id}.post_evaluation.{arm}")
            if post_entry != arms[arm]:
                raise DiagnosticFailure("DIAGNOSTIC_NO_GO", f"post-evaluation routing state changed for {stream_id}/{arm}")
            post_rec = _check_exact_keys(post_recovery[arm], {"recovered", "fresh_process", "journal_sha256", "process_instance_id"}, f"bridge state evidence.{stream_id}.post_evaluation.fresh_recovery.{arm}")
            if post_rec["recovered"] is not True or post_rec["fresh_process"] is not True:
                raise DiagnosticFailure("DIAGNOSTIC_NO_GO", f"post-evaluation recovery lacks fresh process for {stream_id}/{arm}")
            _sha(post_rec["journal_sha256"], f"post-evaluation state evidence {stream_id}/{arm} journal")
            post_process_id = _process_instance_id(post_rec["process_instance_id"], f"post-evaluation state evidence {stream_id}/{arm} process instance")
            if post_process_id in process_ids:
                raise DiagnosticFailure("VOID_PROTOCOL", f"post-evaluation state evidence reuses a recovery process instance for {stream_id}")
            process_ids.add(post_process_id)
            if post_process_id in all_recovery_process_ids:
                raise DiagnosticFailure("VOID_PROTOCOL", "post-evaluation state evidence reuses a recovery process instance across streams")
            all_recovery_process_ids.add(post_process_id)
        if len({state_entries[stream_id][arm]["mount_id"] for arm in ARMS}) != 3:
            raise DiagnosticFailure("VOID_PROTOCOL", f"state evidence reuses an arm mount for {stream_id}")
        if any(
            value != 0
            for routes in state_scores[stream_id]["NO_MEMORY_ROLLBACK"].values()
            for value in routes.values()
        ):
            raise BundleRefusal("NO_MEMORY_ROLLBACK durable routing payload is not the exact zero W0 baseline")

    # Every ordinal is checked against the one frozen schedule before any
    # candidate projection is consulted.  This rules out interleaved training
    # or arbitrary arm labels.
    expected_schedule: list[tuple[Mapping[str, Any], str | None]] = []
    for stream in public["streams"]:
        expected_schedule.extend((episode, None) for episode in stream["training"])
    for stream in public["streams"]:
        for episode in stream["heldout"]:
            expected_schedule.extend((episode, arm) for arm in episode["arm_order"])
    if len(expected_schedule) != 128:
        raise BundleRefusal("public manifest does not regenerate frozen 128-call schedule")

    by_stream_events: dict[str, list[Mapping[str, Any]]] = {stream_id: [] for stream_id in public_streams}
    training_current_scores: dict[str, dict[str, dict[str, int]]] = {
        stream_id: _copy_scores(state_scores[stream_id]["NO_MEMORY_ROLLBACK"])
        for stream_id in public_streams
    }
    training_current_sha = {
        stream_id: str(state_entries[stream_id]["NO_MEMORY_ROLLBACK"]["state_sha256"])
        for stream_id in public_streams
    }
    consumed: dict[str, set[str]] = {stream_id: set() for stream_id in public_streams}
    candidate_probes: dict[str, dict[str, Mapping[str, Any]]] = {
        stream_id: {probe["probe_id"]: probe for probe in candidates[stream_id]["probes"]}
        for stream_id in public_streams
    }
    observations: dict[str, dict[str, dict[str, Mapping[str, Any]]]] = {
        stream_id: {} for stream_id in public_streams
    }
    replay_by_probe: dict[str, dict[str, Mapping[str, Any]]] = {stream_id: {} for stream_id in public_streams}
    call_canary_evidence: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []

    for position, (episode, arm) in enumerate(expected_schedule, start=1):
        phase = str(episode["phase"])
        event = _runner_event(
            runner_events[position - 1], ordinal=position, phase=phase, arm=arm, episode=episode,
            label=f"runner_events[{position - 1}]",
        )
        request = event["request"]
        request_id = _model_request_digest(request)
        accepted = accepted_model_events.get(request_id)
        if accepted is None:
            raise BundleRefusal("runner event lacks matching accepted model-boundary observation")
        call_canary_evidence.append((event, accepted))
        _, answer, _, _, _ = _response_digest_from_raw(
            str(accepted["raw_response_utf8"]),
            str(accepted["model"]),
            _structured_chat_config(accepted["chat_config"], "accepted model event chat_config")[1],
        )
        stream_id = str(episode["stream_id"])
        by_stream_events[stream_id].append(event)
        route = str(request["selected_route_id"])
        private_binding = private_bindings[stream_id]
        private_commitment = str(public["private_manifest_commitment"])
        scorer_sha = str(candidate["bindings"]["scorer_sha256"])
        if phase == "training":
            if route != episode["forced_route_id"] or event["route_replay"] is not None:
                raise BundleRefusal("training event must use forced route and null route replay")
            current = training_current_scores[stream_id]
            score = current[str(episode["context_key"])][route]
            trace = _validate_trace(
                event["trace"], request=request, episode=episode, route=route,
                expected_state_sha256=training_current_sha[stream_id], expected_score=score,
                expected_response_sha256=str(accepted["dnrd_response_sha256"]), label=f"runner_events[{position - 1}].trace",
            )
            if event["route_digest_sha256"] != _route_digest(str(episode["context_key"]), route, score):
                raise BundleRefusal("training event route digest does not replay from W0/credit state")
            _, outcome = _validate_sealed_and_outcome(
                event["sealed_response"], event["scorer_outcome"], episode=episode, route=route,
                private_binding=private_binding, private_commitment=private_commitment, scorer_sha256=scorer_sha,
                answer=answer, label=f"runner_events[{position - 1}]",
            )
            after, outcome_id = _validate_credit_receipt(
                event["credit_receipt"], trace=trace, outcome=outcome,
                expected_before=training_current_sha[stream_id], consumed=consumed[stream_id],
                label=f"runner_events[{position - 1}].credit_receipt",
            )
            consumed[stream_id].add(outcome_id)
            training_current_sha[stream_id] = after
            current[str(episode["context_key"])][route] = max(
                -100_000, min(100_000, score + int(outcome["reward"]) * 100_000 // 1_000_000)
            )
        else:
            if event["credit_receipt"] is not None:
                raise BundleRefusal("heldout evaluation event must never carry a credit receipt")
            arm_scores = state_scores[stream_id][str(arm)]
            selected = _select(arm_scores, episode)
            if route != selected:
                raise BundleRefusal("heldout selected route does not replay from retained arm routing payload")
            score = arm_scores[str(episode["context_key"])][route]
            trace = _validate_trace(
                event["trace"], request=request, episode=episode, route=route,
                expected_state_sha256=str(state_entries[stream_id][str(arm)]["state_sha256"]), expected_score=score,
                expected_response_sha256=str(accepted["dnrd_response_sha256"]), label=f"runner_events[{position - 1}].trace",
            )
            digest = _route_digest(str(episode["context_key"]), route, score)
            if event["route_digest_sha256"] != digest:
                raise BundleRefusal("heldout route digest does not replay from retained arm routing payload")
            _, outcome = _validate_sealed_and_outcome(
                event["sealed_response"], event["scorer_outcome"], episode=episode, route=route,
                private_binding=private_binding, private_commitment=private_commitment, scorer_sha256=scorer_sha,
                answer=answer, label=f"runner_events[{position - 1}]",
            )
            replay = _check_exact_keys(event["route_replay"], {"initial_w0", "rollback", "restore"}, f"runner_events[{position - 1}].route_replay")
            expected_replay = {
                "initial_w0": _route_only_from_scores(state_scores[stream_id]["NO_MEMORY_ROLLBACK"], episode),
                "rollback": _route_only_from_scores(state_scores[stream_id]["NO_MEMORY_ROLLBACK"], episode),
                "restore": _route_only_from_scores(state_scores[stream_id]["FULL"], episode),
            }
            if replay != expected_replay:
                raise BundleRefusal(
                    "heldout route observations do not rederive retained W0/FULL mount selections"
                )
            observations[stream_id].setdefault(str(episode["episode_id"]), {})[str(arm)] = {
                "selected_route_id": route,
                "route_digest_sha256": digest,
                "route_reward_micros": int(outcome["reward"]),
            }
            replay_by_probe[stream_id][str(episode["episode_id"])] = expected_replay

    stream_checks: list[dict[str, object]] = []
    for stream_id, stream in public_streams.items():
        candidate_stream = candidates[stream_id]
        state = state_entries[stream_id]
        score = state_scores[stream_id]
        if (
            candidate_stream["w0"]["state_sha256"] != state["NO_MEMORY_ROLLBACK"]["state_sha256"]
            or candidate_stream["w1"]["state_sha256"] != state["FULL"]["state_sha256"]
            or candidate_stream["clean_process_recovery"]["journal_sha256"]
            != evidence_by_stream[stream_id]["pre_evaluation"]["fresh_recovery"]["FULL"]["journal_sha256"]
            or candidate_stream["clean_process_recovery"]["process_instance_id"]
            != evidence_by_stream[stream_id]["pre_evaluation"]["fresh_recovery"]["FULL"]["process_instance_id"]
        ):
            raise BundleRefusal(
                "candidate W0/FULL/recovery observations do not match raw bridge-state evidence"
            )
        if training_current_sha[stream_id] != state["FULL"]["state_sha256"] or training_current_scores[stream_id] != score["FULL"]:
            raise BundleRefusal("training credit chain does not reproduce retained FULL state evidence")
        full_entry = state["FULL"]
        fixed_replay = _check_exact_keys(
            candidate_stream["fixed_rule_replay"],
            {
                "schema_version", "rule", "w1_state_sha256", "w1_journal_sha256",
                "w1_routing_payload_sha256", "w1_routing_payload_bytes",
                "replay_state_sha256", "replay_journal_sha256",
                "replay_routing_payload_sha256", "replay_routing_payload_bytes",
                "replay_process_instance_id", "heldout_readouts",
            },
            f"candidate fixed-rule replay {stream_id}",
        )
        expected_readouts = [
            {
                "episode_id": episode["episode_id"],
                "selected_route_id": _select(score["FULL"], episode),
                "route_digest_sha256": _route_digest(
                    str(episode["context_key"]),
                    _select(score["FULL"], episode),
                    score["FULL"][str(episode["context_key"])][_select(score["FULL"], episode)],
                ),
            }
            for episode in stream["heldout"]
        ]
        if (
            fixed_replay["schema_version"] != "hswm-dnrd-fixed-rule-replay-observation/v1"
            or fixed_replay["rule"] != "signed_reward_times_100000_div_1000000/v1"
            or fixed_replay["w1_state_sha256"] != state["FULL"]["state_sha256"]
            or fixed_replay["replay_state_sha256"] != fixed_replay["w1_state_sha256"]
            or fixed_replay["w1_routing_payload_sha256"] != full_entry["routing_payload_sha256"]
            or fixed_replay["w1_routing_payload_bytes"] != full_entry["routing_payload_bytes"]
            or fixed_replay["replay_routing_payload_sha256"] != fixed_replay["w1_routing_payload_sha256"]
            or fixed_replay["replay_routing_payload_bytes"] != fixed_replay["w1_routing_payload_bytes"]
            or fixed_replay["heldout_readouts"] != expected_readouts
        ):
            raise BundleRefusal("fixed-rule replay gate does not reproduce FULL state/routing payload/readouts")
        _process_instance_id(
            fixed_replay["replay_process_instance_id"],
            f"candidate fixed-rule replay {stream_id}.replay_process_instance_id",
        )
        expected_deranged = {
            receiver: dict(score["FULL"][donor]) for receiver, donor in stream["matched_derangement"].items()
        }
        if expected_deranged != score["BINDING_DERANGED_NUMERIC_PLACEBO"]:
            raise BundleRefusal("DERANGED control does not equal exact public context permutation of FULL scores")
        deranged_entry = state["BINDING_DERANGED_NUMERIC_PLACEBO"]
        full_values, deranged_values = _flat_scores(score["FULL"]), _flat_scores(score["BINDING_DERANGED_NUMERIC_PLACEBO"])
        derived_derangement = {
            "algorithm": "within-stratum-no-fixed-point/v1",
            "seed_sha256": _canonical_hash(stream["matched_derangement"]),
            "fixed_point_count": sum(source == target for source, target in stream["matched_derangement"].items()),
            "preserves_update_multiset": sorted(full_values) == sorted(deranged_values),
            "preserves_precision": all(type(value) is int for value in full_values + deranged_values),
            "preserves_l1_l2_norms": sum(abs(value) for value in full_values) == sum(abs(value) for value in deranged_values) and sum(value * value for value in full_values) == sum(value * value for value in deranged_values),
            "preserves_routing_payload_byte_count": full_entry["routing_payload_bytes"] == deranged_entry["routing_payload_bytes"],
            "routing_payload_content_differs": full_entry["routing_payload_utf8"] != deranged_entry["routing_payload_utf8"],
        }
        if candidate_stream["derangement"] != derived_derangement:
            raise BundleRefusal("candidate derangement fields do not replay from raw state evidence")
        if candidate_stream["w0_replay_mismatch_probe_ids"] != []:
            raise DiagnosticFailure("DIAGNOSTIC_NO_GO", "candidate records W0 replay mismatch")
        candidate_probe_rows = candidate_probes[stream_id]
        if set(candidate_probe_rows) != {episode["episode_id"] for episode in stream["heldout"]}:
            raise BundleRefusal("candidate probe IDs do not exactly cover public heldout episodes")
        for probe_id, expected_arms in observations[stream_id].items():
            probe = candidate_probe_rows.get(probe_id)
            if probe is None or probe["arms"] != expected_arms or probe["rollback"] != replay_by_probe[stream_id][probe_id]["rollback"] or probe["restore"] != replay_by_probe[stream_id][probe_id]["restore"]:
                raise BundleRefusal("candidate probe observation does not replay from runner/state evidence")
            if replay_by_probe[stream_id][probe_id]["initial_w0"] != replay_by_probe[stream_id][probe_id]["rollback"]:
                raise DiagnosticFailure("DIAGNOSTIC_NO_GO", "state evidence shows rollback did not exactly recover W0")
        group = by_stream_events[stream_id]
        outcomes = [event["scorer_outcome"] for event in group]
        traces = [event["trace"] for event in group]
        receipts = [event["credit_receipt"] for event in group if event["phase"] == "training"]
        linkage = candidate_stream["local_v2_linkage"]
        if (
            linkage["outcome_ledger_sha256"] != _canonical_hash(outcomes)
            or linkage["credit_ledger_sha256"] != _canonical_hash(receipts)
            or linkage["transition_evidence_sha256"] != _canonical_hash(traces)
        ):
            raise BundleRefusal("candidate local V2 linkage hashes do not replay from retained event records")
        positive_counts = {
            arm: sum(
                observation["route_reward_micros"] > 0
                for arm_observations in observations[stream_id].values()
                for observed_arm, observation in arm_observations.items()
                if observed_arm == arm
            )
            for arm in ARMS
        }
        full_changed_w0 = sum(
            arms["FULL"]["selected_route_id"] != arms["NO_MEMORY_ROLLBACK"]["selected_route_id"]
            for arms in observations[stream_id].values()
        )
        full_changed_deranged = sum(
            arms["FULL"]["selected_route_id"] != arms["BINDING_DERANGED_NUMERIC_PLACEBO"]["selected_route_id"]
            for arms in observations[stream_id].values()
        )
        stream_checks.append({
            "stream_id": stream_id,
            "positive_route_reward_counts": positive_counts,
            "full_vs_w0_selected_route_differences": full_changed_w0,
            "full_vs_deranged_selected_route_differences": full_changed_deranged,
        })

    observed_canary_leakage = _recompute_training_canary_leakage(
        canaries=training_canaries,
        state_evidence=state_evidence,
        call_evidence=call_canary_evidence,
    )
    _validate_recomputed_canary_overlap(overlap, observed_canary_leakage)

    derived_parity = {
        "same_served_model_id_and_chat_endpoint": True,
        "equal_client_dispatched_and_logical_requests": True,
        "equal_generation_limits_input_token_parity_not_claimed": all(
            event["request"]["max_output_tokens"] == MAX_OUTPUT_TOKENS
            for event in runner_events
        ) and all(
            event["chat_config"].get("max_tokens") == MAX_OUTPUT_TOKENS
            for event in accepted_model_events.values()
        ),
        "equal_candidate_evidence_universe": True,
        "all_active_payloads_within_byte_ceiling": all(
            entry["routing_payload_bytes"] <= active_state_byte_ceiling
            for entries in state_entries.values() for entry in entries.values()
        ),
        "full_deranged_numeric_payload_byte_count_equal": all(
            entries["FULL"]["routing_payload_bytes"] == entries["BINDING_DERANGED_NUMERIC_PLACEBO"]["routing_payload_bytes"]
            for entries in state_entries.values()
        ),
        "arm_labels_hidden_from_model": all(
            all(arm not in event["request"]["prompt"] for arm in ARMS) for event in runner_events
        ),
        "fresh_process_recovery_observed": True,
        "distinct_arm_mount_ids": True,
        "evaluation_read_only_wrt_routing_observed": True,
    }
    if candidate["parity"] != derived_parity:
        raise BundleRefusal("candidate parity values do not equal independently replayed evidence")
    derived_calls = {
        "common_training_model_calls": 32, "evaluation_model_calls": 96,
        "client_dispatched_generation_requests": 128,
        "logical_model_calls": 128, "route_only_model_calls": 0, "scorer_model_calls": 0,
        "retries": 0, "client_cache_hits": 0, "post_first_call_operational_failure": False,
    }
    if candidate["call_ledger"] != derived_calls:
        raise BundleRefusal("candidate call ledger does not equal independently replayed schedule")
    return derived_parity, stream_checks, []


def _route_only_from_scores(scores: Mapping[str, Mapping[str, int]], episode: Mapping[str, Any]) -> dict[str, str]:
    route = _select(scores, episode)
    return {"selected_route_id": route, "route_digest_sha256": _route_digest(str(episode["context_key"]), route, scores[str(episode["context_key"])][route])}


def _git_object_oid(kind: str, content: bytes) -> str:
    import hashlib

    return hashlib.sha1(f"{kind} {len(content)}\0".encode("ascii") + content).hexdigest()


def _commit_headers(raw: str, label: str) -> tuple[str, list[str], int]:
    # Git commit objects are header lines followed by a blank line and message.
    # Continuation lines may occur in identities, but the frozen fields here do
    # not use them; reject ambiguity rather than guess.
    head = raw.split("\n\n", 1)[0]
    tree: str | None = None
    parents: list[str] = []
    epoch: int | None = None
    for line in head.split("\n"):
        if line.startswith("tree "):
            candidate = _git_oid(line.removeprefix("tree "), f"{label}.tree")
            if tree is not None:
                raise BundleRefusal(f"{label} repeats Git tree header")
            tree = candidate
        elif line.startswith("parent "):
            parents.append(_git_oid(line.removeprefix("parent "), f"{label}.parent"))
        elif line.startswith("committer "):
            parts = line.rsplit(" ", 2)
            if len(parts) != 3 or not parts[1].isdigit():
                raise BundleRefusal(f"{label}.committer epoch is invalid")
            epoch = int(parts[1])
    if tree is None or epoch is None or epoch <= 0:
        raise BundleRefusal(f"{label} must retain one Git tree and positive committer epoch")
    return tree, parents, epoch


def _git_tree_entries(raw: bytes, label: str) -> Mapping[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    offset = 0
    while offset < len(raw):
        space = raw.find(b" ", offset)
        nul = raw.find(b"\0", offset)
        if space < 1 or nul < space or nul + 21 > len(raw):
            raise BundleRefusal(f"{label} is not a parseable Git tree object")
        try:
            mode = raw[offset:space].decode("ascii")
            name = raw[space + 1:nul].decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise BundleRefusal(f"{label} tree name is not UTF-8") from error
        if mode not in {"40000", "100644", "100755", "120000"} or not name or "/" in name or name in {".", ".."}:
            raise BundleRefusal(f"{label} has invalid tree mode/name")
        oid = raw[nul + 1:nul + 21].hex()
        if name in entries:
            raise BundleRefusal(f"{label} repeats tree entry name")
        entries[name] = (mode, oid)
        offset = nul + 21
    if not entries:
        raise BundleRefusal(f"{label} tree is empty")
    return entries


def _tree_blob_oid(
    root_oid: str, path: str, objects: Mapping[str, bytes], label: str
) -> str:
    parts = Path(path).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise BundleRefusal(f"{label} is not a safe repository-relative path")
    tree_oid = root_oid
    for index, part in enumerate(parts):
        raw = objects.get(tree_oid)
        if raw is None:
            raise BundleRefusal(f"{label} tree proof omits tree object {tree_oid}")
        entries = _git_tree_entries(raw, f"{label} tree {tree_oid}")
        found = entries.get(part)
        if found is None:
            raise BundleRefusal(f"{label} path is absent from proved tree")
        mode, object_oid = found
        if index == len(parts) - 1:
            if mode not in {"100644", "100755"}:
                raise BundleRefusal(f"{label} final path is not a regular blob")
            return object_oid
        if mode != "40000":
            raise BundleRefusal(f"{label} intermediate path is not a tree")
        tree_oid = object_oid
    raise AssertionError("unreachable path traversal")


def _validate_preregistration_ci_git_binding(
    *,
    preregistration_ci: Mapping[str, Any],
    candidate: Mapping[str, Any],
    preregistration_commit: str,
    preregistration_tree_oid: str,
    preregistration_path: str,
    preregistration_git_blob_oid: str,
    preregistration_sha256: str,
    preregistration_committed_at_unix: int,
) -> None:
    """Join the B-CI identity to raw A→B Git objects, not config projections."""
    receipt = _check_exact_keys(
        preregistration_ci,
        {
            "schema_version", "provider", "run_id", "head_sha", "head_tree_oid",
            "preregistration_path", "preregistration_git_blob_oid", "preregistration_sha256",
            "status", "conclusion", "completed_at_utc", "completed_at_unix",
            "raw_response_sha256", "raw_response_utf8", "discovery_query", "critical_projection",
            "raw_list_response_sha256", "raw_list_response_utf8", "receipt_sha256",
        },
        "preregistration B CI receipt",
    )
    ci_completed_at = _integer(
        receipt["completed_at_unix"],
        "preregistration B CI receipt.completed_at_unix",
        minimum=1,
    )
    chronology = candidate["chronology"]
    if (
        receipt["head_sha"] != preregistration_commit
        or receipt["head_tree_oid"] != preregistration_tree_oid
        or receipt["preregistration_path"] != preregistration_path
        or receipt["preregistration_git_blob_oid"] != preregistration_git_blob_oid
        or receipt["preregistration_sha256"] != preregistration_sha256
        or ci_completed_at < preregistration_committed_at_unix
        or chronology["preregistration_ci_completed_at_unix"] != ci_completed_at
    ):
        raise BundleRefusal(
            "preregistration B CI receipt does not cross-check raw A-to-B Git tree/blob/chronology"
        )


def _validate_git_chronology(
    root: Path,
    chronology: Mapping[str, Any],
    candidate: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    source_bytes: bytes,
    prereg_bytes: bytes,
    preregistration_ci: Mapping[str, Any],
) -> None:
    source_data = _check_exact_keys(
        chronology,
        {"schema_version", "source", "preregistration", "a_to_b_changed_paths", "tree_objects", "receipt_sha256"},
        "git chronology evidence",
    )
    if source_data["schema_version"] != "hswm-dnrd-git-chronology-evidence/v4":
        raise BundleRefusal("git chronology evidence schema mismatch")
    _bundle_sha_receipt(source_data, "git chronology evidence")
    # This binding is deliberately raw artifact bytes rather than the internal
    # receipt ID, so every tree object/path proof is included in the candidate
    # occurrence identity.
    # The caller already read the exact file; its hash is supplied separately.
    source = _check_exact_keys(
        source_data["source"],
        {
            "commit_oid", "commit_raw_utf8", "tree_oid", "commit_time_unix",
            "source_manifest_path", "source_manifest_blob_sha256", "file_blobs",
        },
        "git chronology source",
    )
    prereg = _check_exact_keys(
        source_data["preregistration"],
        {
            "commit_oid", "commit_raw_utf8", "parent_oid", "tree_oid", "commit_time_unix",
            "path", "blob_oid", "blob_sha256",
        },
        "git chronology preregistration",
    )
    source_raw = _string(source["commit_raw_utf8"], "git chronology source.commit_raw_utf8")
    prereg_raw = _string(prereg["commit_raw_utf8"], "git chronology preregistration.commit_raw_utf8")
    source_oid = _git_oid(source["commit_oid"], "git chronology source.commit_oid")
    prereg_oid = _git_oid(prereg["commit_oid"], "git chronology preregistration.commit_oid")
    if _git_object_oid("commit", source_raw.encode("utf-8")) != source_oid or _git_object_oid("commit", prereg_raw.encode("utf-8")) != prereg_oid:
        raise BundleRefusal("Git chronology raw commit bytes do not reproduce commit object identities")
    source_tree, source_parents, source_time = _commit_headers(source_raw, "source commit")
    prereg_tree, prereg_parents, prereg_time = _commit_headers(prereg_raw, "preregistration commit")
    if source_parents and len(source_parents) < 1:
        raise BundleRefusal("unreachable source parent validation")
    if (
        source["tree_oid"] != source_tree
        or prereg["tree_oid"] != prereg_tree
        or source["commit_time_unix"] != source_time
        or prereg["commit_time_unix"] != prereg_time
        or prereg["parent_oid"] != source_oid
        or prereg_parents != [source_oid]
    ):
        raise BundleRefusal("Git chronology commit parent/tree/time projection does not replay raw commits")
    candidate_chronology = candidate["chronology"]
    if (
        candidate_chronology["source_commit"] != source_oid
        or candidate_chronology["preregistration_commit"] != prereg_oid
        or candidate_chronology["source_tree_oid"] != source_tree
        or candidate_chronology["preregistration_tree_oid"] != prereg_tree
        or candidate_chronology["source_frozen_at_unix"] != source_time
    ):
        raise BundleRefusal("candidate chronology does not replay raw Git source-A/B evidence")
    objects = source_data["tree_objects"]
    if type(objects) is not list or not objects:
        raise BundleRefusal("Git chronology evidence has no binary tree object proof")
    import base64

    trees: dict[str, bytes] = {}
    previous = ""
    for index, row in enumerate(objects):
        item = _check_exact_keys(row, {"oid", "raw_base64"}, f"git chronology tree_objects[{index}]")
        oid = _git_oid(item["oid"], f"git chronology tree_objects[{index}].oid")
        if oid <= previous or oid in trees:
            raise BundleRefusal("Git chronology tree objects must be unique sorted by object ID")
        previous = oid
        encoded = _string(item["raw_base64"], f"git chronology tree_objects[{index}].raw_base64")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception as error:
            raise BundleRefusal("Git chronology tree object base64 is invalid") from error
        if _git_object_oid("tree", raw) != oid:
            raise BundleRefusal("Git chronology raw tree bytes do not reproduce tree object identity")
        trees[oid] = raw
    source_path = _string(source["source_manifest_path"], "git chronology source.source_manifest_path")
    prereg_path = _string(prereg["path"], "git chronology preregistration.path")
    source_blob = _tree_blob_oid(source_tree, source_path, trees, "source manifest")
    prereg_blob = _tree_blob_oid(prereg_tree, prereg_path, trees, "preregistration")
    if (
        source_blob != _git_object_oid("blob", source_bytes)
        or prereg_blob != _git_object_oid("blob", prereg_bytes)
        or prereg["blob_oid"] != prereg_blob
        or source["source_manifest_blob_sha256"] != _sha_bytes(source_bytes)
        or prereg["blob_sha256"] != _sha_bytes(prereg_bytes)
    ):
        raise BundleRefusal("Git chronology tree proof does not bind retained source/preregistration blobs")
    _validate_preregistration_ci_git_binding(
        preregistration_ci=preregistration_ci,
        candidate=candidate,
        preregistration_commit=prereg_oid,
        preregistration_tree_oid=prereg_tree,
        preregistration_path=prereg_path,
        preregistration_git_blob_oid=prereg_blob,
        preregistration_sha256=_sha_bytes(prereg_bytes),
        preregistration_committed_at_unix=prereg_time,
    )
    manifest_rows = source_manifest.get("files")
    file_blobs = source["file_blobs"]
    if type(manifest_rows) is not list or type(file_blobs) is not list:
        raise BundleRefusal("Git chronology source-file proof list is malformed")
    expected_rows = {
        _string(row["path"], f"source manifest Git member {index}.path"): _sha(
            row["sha256"], f"source manifest Git member {index}.sha256"
        )
        for index, row in enumerate(manifest_rows)
    }
    proved_rows: dict[str, tuple[str, str]] = {}
    previous_path = ""
    for index, raw_row in enumerate(file_blobs):
        row = _check_exact_keys(
            raw_row,
            {"path", "blob_oid", "sha256"},
            f"git chronology source.file_blobs[{index}]",
        )
        path = _string(row["path"], f"git chronology source.file_blobs[{index}].path")
        blob_oid = _git_oid(
            row["blob_oid"], f"git chronology source.file_blobs[{index}].blob_oid"
        )
        digest = _sha(
            row["sha256"], f"git chronology source.file_blobs[{index}].sha256"
        )
        if path <= previous_path or path in proved_rows:
            raise BundleRefusal("Git chronology source-file proofs must be unique and sorted")
        previous_path = path
        proved_rows[path] = (blob_oid, digest)
    if set(proved_rows) != set(expected_rows):
        raise BundleRefusal("Git chronology source-file proofs do not exactly cover the source manifest")
    for path, expected_sha256 in expected_rows.items():
        blob_oid, digest = proved_rows[path]
        body = _bundle_plain_file(root, f"source_closure/{path}").read_bytes()
        if (
            digest != expected_sha256
            or _sha_bytes(body) != expected_sha256
            or _git_object_oid("blob", body) != blob_oid
            or _tree_blob_oid(source_tree, path, trees, f"source file {path}") != blob_oid
        ):
            raise BundleRefusal(
                "Git chronology source-file proof does not bind retained Source-A bytes"
            )
    changed = source_data["a_to_b_changed_paths"]
    if type(changed) is not list or changed != [prereg_path]:
        raise BundleRefusal("Git chronology evidence does not attest the sole A-to-B preregistration path")
    if candidate["chronology"]["preregistration_committed_at_unix"] != prereg["commit_time_unix"]:
        raise BundleRefusal("candidate chronology preregistration commit time differs from raw Git evidence")


def _bundle_receipt_sha(
    *,
    candidate_bytes: bytes,
    artifact_hashes: Mapping[str, str],
    terminal: str,
    detail: str | None,
    verification_status: str,
) -> str:
    receipt = {
        "schema_version": "hswm-dnrd-bundle-verification-receipt/v2",
        "candidate_artifact_sha256": _sha_bytes(candidate_bytes),
        "artifact_sha256": dict(sorted(artifact_hashes.items())),
        "terminal": terminal,
        "detail": detail,
        "verification_status": verification_status,
    }
    return _canonical_hash(receipt)


def _bundle_result(
    candidate: Mapping[str, Any],
    candidate_bytes: bytes,
    *,
    terminal: str,
    artifact_hashes: Mapping[str, str],
    stream_checks: Sequence[Mapping[str, Any]] = (),
    utility_report: Sequence[Mapping[str, Any]] = (),
    failure_reason: str | None = None,
    bundle_verified: bool = True,
) -> dict[str, Any]:
    result = _judgment(
        candidate,
        terminal=terminal,
        stream_route_checks=[dict(item) for item in stream_checks],
        utility_report=[dict(item) for item in utility_report],
        failure_reason=failure_reason,
    )
    if bundle_verified:
        authority = "AUTHORITATIVE_EVIDENCE_BUNDLE_VERIFIED"
        verification_status = "FULL_BUNDLE_REPLAY_VERIFIED"
        claim_boundary = (
            "Verified finite engineering-conformance bundle only, not scientific effect evidence; "
            "no efficacy, general intelligence, canonical Permit, admission, or learning claim is "
            "established. Model responses are format/liveness observations rather than causes of "
            "the route rewards or updates. Scorer role separation "
            "is declared only as DECLARED_ROLE_SEPARATION_NOT_PROVEN; no stronger scorer-role "
            "property is established, and model-serving identity/determinism remains unproven. "
            "The retained verifier receipt is rehashed and internally cross-checked, not "
            "re-verified for BLS cryptography by this stdlib adjudicator. The durable attempt "
            "marker is observed under its declared registry scope; global singleton/no-rerun "
            "enforcement is not proven by this bundle. Fixture generation beyond its seed "
            "commitment/private-public embedding and dynamically loaded/host runtime dependencies "
            "remain source/runtime-trusted rather than independently re-executed here. The selected "
            "runtime build is not independently reexecuted by this adjudicator. Paired mount "
            "comparisons are retained-state observations, not a claim of one temporal remount or restoration."
        )
    else:
        authority = "INCOMPLETE_OR_INVALID_EVIDENCE_BUNDLE_NOT_VERIFIED"
        verification_status = "FAILED"
        claim_boundary = (
            "The candidate artifact was retained, but full evidence-bundle replay failed. This "
            "VOID_PROTOCOL record cannot establish a verified occurrence, efficacy, general intelligence, "
            "canonical Permit, admission, or learning."
        )
    result["authority"] = authority
    result["candidate_artifact_sha256"] = _sha_bytes(candidate_bytes)
    result["bundle_verification_receipt_sha256"] = _bundle_receipt_sha(
        candidate_bytes=candidate_bytes,
        artifact_hashes=artifact_hashes,
        terminal=terminal,
        detail=failure_reason,
        verification_status=verification_status,
    )
    result["claim_boundary"] = claim_boundary
    return result


def _inconclusive_bundle_result(
    occurrence: Mapping[str, Any],
    occurrence_bytes: bytes,
    *,
    terminal: str,
    artifact_hashes: Mapping[str, str],
    failure_reason: str | None = None,
) -> dict[str, Any]:
    if terminal == "INCONCLUSIVE_OCCURRENCE":
        authority = "INDEXED_INCONCLUSIVE_MODEL_BOUNDARY_AND_RUNNER_IDENTITY_LEDGER_VERIFIED"
        verification_status = "PARTIAL_MODEL_BOUNDARY_AND_RUNNER_IDENTITY_LEDGER_VERIFIED"
        claim_boundary = (
            "The indexed model-boundary ledger and accepted-call-to-runner-row identity coverage "
            "were verified. Runner-row semantic contents, the terminal request preimage, and retained "
            "common context were not replayed as a completed candidate. This partial occurrence cannot "
            "establish efficacy, general intelligence, canonical Permit, admission, or learning."
        )
    elif terminal == "VOID_PROTOCOL":
        # A retained inconclusive artifact is useful forensic context, but a
        # missing or contradictory index means the bundle itself was not
        # verified.  Do not let the valid-inconclusive wording overstate that
        # partial observation as an authoritative evidence bundle.
        authority = "INCOMPLETE_OR_INVALID_EVIDENCE_BUNDLE_NOT_VERIFIED"
        verification_status = "FAILED"
        claim_boundary = (
            "A post-first-call inconclusive artifact was retained, but the evidence bundle failed "
            "structural verification. This VOID_PROTOCOL record cannot establish a verified occurrence, "
            "efficacy, general intelligence, canonical Permit, admission, or learning."
        )
    else:
        raise BundleRefusal("inconclusive bundle result has an unknown terminal")
    receipt = {
        "schema_version": "hswm-dnrd-bundle-verification-receipt/v2",
        "inconclusive_artifact_sha256": _sha_bytes(occurrence_bytes),
        "artifact_sha256": dict(sorted(artifact_hashes.items())),
        "terminal": terminal,
        "detail": failure_reason,
        "verification_status": verification_status,
    }
    return {
        "schema_version": JUDGMENT_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "authority": authority,
        "terminal": terminal,
        "inconclusive_artifact_sha256": _sha_bytes(occurrence_bytes),
        "calls_completed": occurrence.get("calls_completed"),
        "scientific_status": "UNJUDGED",
        "efficacy_claim": "NOT_EVALUATED",
        "canonical_permit": "NOT_ESTABLISHED",
        "learning_claim": "NOT_ESTABLISHED",
        "failure_reason": failure_reason,
        "bundle_verification_receipt_sha256": _canonical_hash(receipt),
        "claim_boundary": claim_boundary,
    }


def _missing_terminal_artifacts_result() -> dict[str, Any]:
    """Seal the absence of both permitted terminal artifacts conservatively.

    A post-dispatch executor failure can occur after the attempt marker and
    boundary ledgers exist but before it writes either terminal projection.
    That is *not* evidence for an inconclusive occurrence: the required
    occurrence object was never retained.  Returning a deterministic negative
    judgment lets the caller retain a machine-readable terminal without
    inventing an artifact or turning this adjudicator failure into an exit-2
    refusal.
    """
    terminalization_check = "CANDIDATE_AND_INCONCLUSIVE_ARTIFACTS_ABSENT"
    failure_reason = (
        "bounded evidence bundle contains neither candidate.json nor "
        "inconclusive.json; no scientific occurrence artifact was retained"
    )
    receipt = {
        "schema_version": "hswm-dnrd-bundle-verification-receipt/v2",
        "artifact_sha256": {},
        "terminal": "VOID_PROTOCOL",
        "detail": failure_reason,
        "verification_status": "TERMINAL_ARTIFACT_ABSENCE",
        "terminalization_check": terminalization_check,
    }
    return {
        "schema_version": JUDGMENT_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "authority": "TERMINAL_ARTIFACT_ABSENCE_NOT_A_SCIENTIFIC_OCCURRENCE",
        "terminal": "VOID_PROTOCOL",
        "scientific_status": "UNJUDGED",
        "efficacy_claim": "NOT_EVALUATED",
        "canonical_permit": "NOT_ESTABLISHED",
        "learning_claim": "NOT_ESTABLISHED",
        "failure_reason": failure_reason,
        "terminalization_check": terminalization_check,
        "bundle_verification_receipt_sha256": _canonical_hash(receipt),
        "claim_boundary": (
            "Neither candidate nor inconclusive occurrence artifact was retained. "
            "This VOID_PROTOCOL terminal is a protocol-closure record, not a verified "
            "occurrence and establishes no efficacy, general intelligence, canonical Permit, "
            "admission, or learning."
        ),
    }


def _void_protocol_bundle_result(root: Path) -> dict[str, Any]:
    """Validate a pre-dispatch terminal without inventing an occurrence."""
    value, raw = _bundle_object(root, "void_protocol.json")
    if value.get("schema_version") != "hswm-dnrd-void-protocol/v2" or value.get("experiment_id") != EXPERIMENT_ID:
        raise BundleRefusal("void protocol terminal schema/identity is invalid")
    if value.get("post_first_call") is False:
        data = _check_exact_keys(
            value,
            {"schema_version", "experiment_id", "post_first_call", "failure_type", "failure_digest"},
            "pre-dispatch void protocol terminal",
        )
    elif value.get("post_first_call") is True:
        data = _check_exact_keys(
            value,
            {
                "schema_version", "experiment_id", "post_first_call", "calls_observed",
                "accepted_model_calls", "runner_completed_calls", "model_events_sha256",
                "runner_events_sha256", "failure_stage", "failure_type", "failure_digest",
            },
            "post-dispatch void protocol terminal",
        )
        if (
            data["failure_stage"] != "POST_DISPATCH_INTERNAL_FINALIZATION"
            or type(data["calls_observed"]) is not int or not 1 <= data["calls_observed"] <= 128
            or type(data["accepted_model_calls"]) is not int or not 0 <= data["accepted_model_calls"] <= data["calls_observed"]
            or type(data["runner_completed_calls"]) is not int or not 0 <= data["runner_completed_calls"] <= data["accepted_model_calls"]
        ):
            raise BundleRefusal("post-dispatch void terminal counters/stage are invalid")
        indexed = _validate_bundle_index(root)
        for relative, field in (("model_events.jsonl", "model_events_sha256"), ("runner_events.jsonl", "runner_events_sha256")):
            body = _bundle_plain_file(root, relative, allow_empty=True).read_bytes()
            if _sha_bytes(body) != data[field] or indexed.get(relative) != data[field]:
                raise BundleRefusal("post-dispatch void terminal ledger hash does not bind indexed bytes")
        model_rows, _ = _bundle_jsonl(root, "model_events.jsonl", allow_empty=True)
        runner_rows, _ = _bundle_jsonl(root, "runner_events.jsonl", allow_empty=True)
        if (
            sum(row.get("event") == "CHAT_COMPLETION_ACCEPTED" for row in model_rows) != data["accepted_model_calls"]
            or sum(row.get("event") == "COMPLETED_CALL" for row in runner_rows) != data["runner_completed_calls"]
        ):
            raise BundleRefusal("post-dispatch void terminal counters do not replay from retained ledgers")
    else:
        raise BundleRefusal("void protocol terminal post_first_call must be boolean")
    _string(data["failure_type"], "void protocol terminal.failure_type")
    _sha(data["failure_digest"], "void protocol terminal.failure_digest")
    result = _missing_terminal_artifacts_result()
    result["authority"] = (
        "POST_DISPATCH_VOID_PROTOCOL_TERMINAL_LEDGER_BOUND"
        if value["post_first_call"] else "PRE_DISPATCH_VOID_PROTOCOL_TERMINAL_RETAINED"
    )
    result["void_protocol_artifact_sha256"] = _sha_bytes(raw)
    result["terminalization_check"] = (
        "POST_DISPATCH_VOID_PROTOCOL_LEDGER_HASHES_VALIDATED"
        if value["post_first_call"] else "PRE_DISPATCH_VOID_PROTOCOL_ARTIFACT_VALIDATED"
    )
    return result


def _judge_inconclusive_bundle(root: Path) -> dict[str, Any]:
    """Validate a retained aborted occurrence without treating it as a candidate."""
    occurrence, occurrence_bytes = _bundle_object(root, "inconclusive.json")
    artifact_hashes: dict[str, str] = {"inconclusive.json": _sha_bytes(occurrence_bytes)}
    try:
        artifact_hashes = dict(_validate_bundle_index(root))
        if (root / "candidate.json").exists() or (root / "bridge_state_evidence.json").exists():
            raise BundleRefusal("inconclusive occurrence must not retain candidate-only artifacts")
        missing = [
            relative for relative in sorted(BUNDLE_COMMON_REQUIRED_FILES)
            if not (root / relative).is_file()
        ]
        if missing:
            raise BundleRefusal("inconclusive bundle is missing common artifacts: " + ", ".join(missing))
        for relative in sorted({*BUNDLE_COMMON_REQUIRED_FILES, "inconclusive.json"}):
            artifact_hashes[relative] = _sha_bytes(
                _bundle_plain_file(root, relative, allow_empty=relative in {"runner_events.jsonl", "model_events.jsonl"}).read_bytes()
            )
        data = _check_exact_keys(
            occurrence,
            {
                "schema_version", "experiment_id", "post_first_call", "calls_completed",
                "client_cache_hits", "failure_type", "failure_digest",
            },
            "inconclusive occurrence",
        )
        if (
            data["schema_version"] != INCONCLUSIVE_SCHEMA
            or data["experiment_id"] != EXPERIMENT_ID
            or data["post_first_call"] is not True
            or _integer(data["calls_completed"], "inconclusive occurrence.calls_completed", minimum=1) > 128
            or _integer(data["client_cache_hits"], "inconclusive occurrence.client_cache_hits") != 0
        ):
            raise BundleRefusal("inconclusive occurrence does not retain the frozen no-retry boundary")
        _string(data["failure_type"], "inconclusive occurrence.failure_type")
        _sha(data["failure_digest"], "inconclusive occurrence.failure_digest")
        runner_events, _ = _bundle_jsonl(root, "runner_events.jsonl", allow_empty=True)
        model_events, _ = _bundle_jsonl(root, "model_events.jsonl", allow_empty=True)
        _validate_inconclusive_ledgers(data, runner_events, model_events)
        return _inconclusive_bundle_result(
            occurrence, occurrence_bytes, terminal="INCONCLUSIVE_OCCURRENCE",
            artifact_hashes=artifact_hashes,
        )
    except BundleRefusal as failure:
        return _inconclusive_bundle_result(
            occurrence, occurrence_bytes, terminal="VOID_PROTOCOL",
            artifact_hashes=artifact_hashes, failure_reason=str(failure),
        )


def judge_bundle(bundle_dir: str | Path) -> dict[str, Any]:
    """Authoritatively adjudicate one retained DNRD evidence bundle.

    A structural candidate can never be upgraded by this function unless every
    hash-bound artifact and every 128-call event replay agrees.  Artifact
    absence or contradiction produces a conservative ``VOID_PROTOCOL``
    judgment (with a generated receipt), while a malformed candidate itself is
    refused just like the legacy structural helper.
    """

    root = Path(bundle_dir)
    try:
        info = root.lstat()
    except FileNotFoundError as error:
        raise BundleRefusal("bundle directory is absent") from error
    if root.is_symlink() or not root.is_dir() or not info:
        raise BundleRefusal("bundle root must be a plain directory")
    obsolete_ratification = root / "ratification_receipt.json"
    if obsolete_ratification.exists() or obsolete_ratification.is_symlink():
        raise BundleRefusal(
            "DNRD-4S1 evidence bundles must not retain obsolete ratification_receipt.json"
        )
    if (root / "void_protocol.json").exists():
        if (root / "candidate.json").exists() or (root / "inconclusive.json").exists():
            raise BundleRefusal("void protocol terminal may not coexist with a scientific occurrence artifact")
        return _void_protocol_bundle_result(root)
    if not (root / "candidate.json").exists() and not (root / "inconclusive.json").exists():
        return _missing_terminal_artifacts_result()
    if not (root / "candidate.json").exists() and (root / "inconclusive.json").exists():
        return _judge_inconclusive_bundle(root)
    candidate, candidate_bytes = _bundle_object(root, "candidate.json")
    # Refuse malformed measurement objects early.  The resulting structural
    # outcome is deliberately not treated as authoritative until replay below.
    structural = judge(candidate)
    artifact_hashes: dict[str, str] = {"candidate.json": _sha_bytes(candidate_bytes)}
    try:
        artifact_hashes = dict(_validate_bundle_index(root))
        missing = [relative for relative in sorted(BUNDLE_CANDIDATE_REQUIRED_FILES) if not (root / relative).is_file()]
        if missing:
            raise BundleRefusal(f"bundle is missing required complete-occurrence artifacts: {', '.join(missing)}")
        # Plain-file checks and byte hashes happen before parsing so a synthetic
        # candidate cannot provide an arbitrary digest for a substituted ledger.
        raw_artifacts: dict[str, bytes] = {}
        for relative in sorted(BUNDLE_CANDIDATE_REQUIRED_FILES):
            path = _bundle_plain_file(root, relative)
            raw_artifacts[relative] = path.read_bytes()
            artifact_hashes[relative] = _sha_bytes(raw_artifacts[relative])
        source, source_bytes = _bundle_object(root, "source_manifest.json")
        preregistration, preregistration_bytes = _bundle_object(root, "preregistration.json")
        source_ci, _ = _bundle_object(root, "source_ci_receipt.json")
        preregistration_ci, preregistration_ci_bytes = _bundle_object(
            root, "preregistration_ci_receipt.json"
        )
        qualification_bytes = _bundle_plain_file(root, "structured_output_qualification.json").read_bytes()
        runtime, _ = _bundle_object(root, "runtime_receipt.json")
        attempt, _ = _bundle_object(root, "attempt_lock_receipt.json")
        terminal_intent, _ = _bundle_object(root, "terminal-intent.json")
        config_readback, _ = _bundle_object(root, "config_readback.json")
        public, public_bytes = _bundle_object(root, "public_manifest.json")
        private, _ = _bundle_object(root, "private/private_manifest.json")
        deployment, _ = _bundle_object(root, "deployment_receipt.json")
        pulse, _ = _bundle_object(root, "pulse_binding.json")
        chronology, chronology_bytes = _bundle_object(root, "git_chronology_evidence.json")
        state_evidence, state_bytes = _bundle_object(root, "bridge_state_evidence.json")
        mount_closure, mount_closure_bytes = _bundle_object(root, "bridge_mount_closure.json")
        runner_events, runner_bytes = _bundle_jsonl(root, "runner_events.jsonl")
        model_events, model_bytes = _bundle_jsonl(root, "model_events.jsonl")
        verifier_bytes = raw_artifacts["pulse_verifier_receipt.json"]

        bindings = candidate["bindings"]
        if bindings["split_manifest_sha256"] != _sha_bytes(public_bytes):
            raise BundleRefusal("candidate split-manifest binding does not match retained public bytes")
        if bindings["event_ledger_sha256"] != _sha_bytes(runner_bytes):
            raise BundleRefusal("candidate runner-event-ledger binding does not match retained JSONL bytes")
        if bindings["model_event_ledger_sha256"] != _sha_bytes(model_bytes):
            raise BundleRefusal("candidate model-event-ledger binding does not match retained JSONL bytes")
        if bindings["bridge_state_evidence_sha256"] != _sha_bytes(state_bytes):
            raise BundleRefusal("candidate bridge-state-evidence binding does not match retained bytes")
        if bindings["bridge_mount_closure_sha256"] != _sha_bytes(mount_closure_bytes):
            raise BundleRefusal("candidate bridge-mount-closure binding does not match retained bytes")
        if bindings["git_chronology_evidence_sha256"] != _sha_bytes(chronology_bytes):
            raise BundleRefusal("candidate Git chronology binding does not match retained bytes")

        _validate_source_and_preregistration(
            source=source, preregistration=preregistration, source_ci=source_ci,
            preregistration_ci=preregistration_ci, candidate=candidate,
            source_bytes=source_bytes, preregistration_bytes=preregistration_bytes,
            preregistration_ci_bytes=preregistration_ci_bytes,
        )
        _validate_source_closure(root, source)
        config = _validate_config_readback(config_readback, candidate, runtime)
        if _sha_bytes(qualification_bytes) != config["structured_output_qualification_sha256"]:
            raise BundleRefusal("structured-output qualification bytes do not match the pinned config digest")
        _structured_output_qualification(
            qualification_bytes,
            config=config,
            public=public,
            private=private,
            source=source,
            preregistration=preregistration,
        )
        intent = _check_exact_keys(
            terminal_intent,
            {"schema_version", "experiment_id", "attempt_lock_receipt_sha256", "terminal_artifact_paths", "no_retry_or_resume"},
            "terminal intent",
        )
        if (
            intent["schema_version"] != "hswm-dnrd-terminal-intent/v1"
            or intent["experiment_id"] != EXPERIMENT_ID
            or intent["attempt_lock_receipt_sha256"] != attempt["receipt_sha256"]
            or intent["terminal_artifact_paths"] != ["candidate.json", "inconclusive.json", "void_protocol.json"]
            or intent["no_retry_or_resume"] is not True
        ):
            raise BundleRefusal("terminal intent does not bind the consumed attempt and exact terminal paths")
        _validate_preregistration_runtime_binding(preregistration, runtime, config)
        _validate_verifier_source_binding(source, preregistration, config)
        _validate_verifier_runtime_bundle_evidence(
            root,
            raw_artifacts[VERIFIER_RUNTIME_BUNDLE_EVIDENCE_PATH],
            preregistration,
            config,
            runtime,
        )
        active_state_byte_ceiling = _preregistration_active_state_byte_ceiling(preregistration)
        endpoint, model, chat_config = _validate_deployment(deployment, candidate, config)
        _validate_pulse(
            pulse, verifier_bytes, candidate, preregistration_ci, preregistration
        )
        _validate_runtime_and_attempt(
            runtime, attempt, candidate, preregistration_ci, pulse
        )
        training_canaries = _validate_fixture_seed_binding(public, private, pulse)
        _validate_git_chronology(
            root,
            chronology,
            candidate,
            source,
            source_bytes,
            preregistration_bytes,
            preregistration_ci,
        )
        _validate_runtime_closure(
            root, runtime, source=source, candidate=candidate, chronology=chronology
        )
        accepted = _reconcile_model_events(
            model_events, runner_events, endpoint=endpoint, model=model, chat_config=chat_config,
        )
        _validate_bridge_mount_closure(
            root,
            closure=mount_closure,
            closure_bytes=mount_closure_bytes,
            candidate=candidate,
            state_evidence=state_evidence,
            public=public,
            runner_events=runner_events,
            training_canaries=training_canaries,
        )
        _, stream_checks, utility_report = _reconcile_events_and_state(
            candidate=candidate, public=public, private=private, runner_events=runner_events,
            accepted_model_events=accepted, state_evidence=state_evidence,
            active_state_byte_ceiling=active_state_byte_ceiling,
            training_canaries=training_canaries,
        )
        _validate_source_closure_overlap(root, source, public, candidate)
        # Structural helper encodes the frozen GO/NO-GO terminal rules after
        # the evidence projection has independently been rebuilt.  It cannot
        # turn a contradictory bundle into GO because any contradiction above
        # returns VOID before this point.
        terminal = structural["terminal"]
        if terminal == "DIAGNOSTIC_INTEGRITY_GO_NO_UTILITY_CLAIM":
            if not all(
                item["positive_route_reward_counts"].get("FULL") == 8
                and item["positive_route_reward_counts"].get("NO_MEMORY_ROLLBACK") == 4
                and int(item["positive_route_reward_counts"].get("BINDING_DERANGED_NUMERIC_PLACEBO", 9)) <= 4
                and item["full_vs_w0_selected_route_differences"] == 4
                and int(item["full_vs_deranged_selected_route_differences"]) >= 4
                for item in stream_checks
            ):
                terminal = "DIAGNOSTIC_NO_GO"
        return _bundle_result(
            candidate, candidate_bytes, terminal=terminal, artifact_hashes=artifact_hashes,
            stream_checks=stream_checks, utility_report=utility_report,
        )
    except DiagnosticFailure as failure:
        return _bundle_result(
            candidate, candidate_bytes, terminal=failure.terminal, artifact_hashes=artifact_hashes,
            failure_reason=str(failure),
        )
    except BundleRefusal as failure:
        return _bundle_result(
            candidate, candidate_bytes, terminal="VOID_PROTOCOL", artifact_hashes=artifact_hashes,
            failure_reason=str(failure), bundle_verified=False,
        )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(f"usage: {Path(sys.argv[0]).name} EVIDENCE_BUNDLE_DIR | CANDIDATE.json", file=sys.stderr)
        return 2
    try:
        target = Path(args[0])
        result = judge_bundle(target) if target.is_dir() else judge(_load_json(target))
    except (OSError, json.JSONDecodeError, JudgeRefusal, ValueError) as error:
        print(json.dumps({"status": "JUDGMENT_REFUSED", "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    # A valid negative result is scientific evidence and must not be discarded
    # by CI as a command failure.  Only malformed/refused candidates are nonzero.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
