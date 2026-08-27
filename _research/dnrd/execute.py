"""One no-verdict execution boundary for the DNRD diagnostic.

This is deliberately DNRD-specific: it freezes one source/preregistration
identity, binds one future Quicknet pulse, performs the fixed three-request
non-generation preflight, and then invokes the fixed runner once.  It never
interprets a candidate or emits a scientific terminal.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
from typing import Any, Callable, Mapping, Protocol, Sequence

from .live import (
    CHAT_CONFIG,
    MODEL_ID,
    MODEL_MAX_LENGTH,
    MODEL_ROOT,
    PREFLIGHT_SCHEMA,
    VLLM_VERSION,
    OpenAICompatibleDnrdAnswerer,
    OpenAICompatibleDnrdConfig,
    UrllibHttpTransport,
    preflight_deployment_and_tokenizer,
)
from .runner import (
    ARMS,
    BRIDGE_MOUNT_CLOSURE_PLAN_SCHEMA,
    MAX_OUTPUT_TOKENS,
    MOUNT_ROLES,
    PROVIDER_CACHE_UNOBSERVABLE,
    Answerer,
    Bridge,
    BridgeMountClosureExport,
    BridgeMountClosureExporter,
    MeasurementMetadata,
    OutcomeScorer,
    RunnerResult,
    SubprocessJsonBridge,
    SubprocessOutcomeScorer,
    run_diagnostic,
)
from .seed import SourceFreezeBinding, bind_future_pulse, first_eligible_quicknet_round, projection_from_verifier_receipt_bytes
from .task_family import canonical_json, commitment, generate_manifests


class ExecutionRefusal(RuntimeError):
    """Pre-execution contract failure; no output directory is created."""


class GitRunner(Protocol):
    def __call__(self, args: Sequence[str], cwd: Path) -> str: ...


class GitBytesRunner(Protocol):
    def __call__(self, args: Sequence[str], cwd: Path) -> bytes: ...


class VerifierRunner(Protocol):
    def __call__(self, command: Sequence[str]) -> bytes: ...


class LivePreflight(Protocol):
    def __call__(self, config: "ExecutionConfig") -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ExecutionConfig:
    repo_root: Path
    source_a_commit: str
    source_a_tree: str
    source_manifest_path: str
    source_manifest_sha256: str
    prereg_b_commit: str
    prereg_path: str
    prereg_sha256: str
    source_freeze_unix: int
    ratification_unix: int
    ratification_text: str
    ratification_text_sha256: str
    output_root: Path
    model_endpoint: str
    bridge_implementation_path: Path
    bridge_implementation_sha256: str
    bridge_command: tuple[str, ...]
    bridge_config: Mapping[str, Any]
    scorer_implementation_path: Path
    scorer_implementation_sha256: str
    scorer_command: tuple[str, ...]
    verifier_command: tuple[str, ...]
    verifier_helper_path: Path
    verifier_helper_sha256: str
    verifier_package_lock_path: Path
    verifier_package_lock_sha256: str
    verifier_runtime_bundle_path: Path
    verifier_runtime_bundle_sha256: str
    # The following pins are mandatory for a production occurrence.  They are
    # optional only at construction time so test fixtures can exercise the
    # refusal path explicitly.
    attempt_registry_root: Path | None = None
    ratification_receipt_path: Path | None = None
    ratification_receipt_sha256: str | None = None
    source_ci_receipt_path: Path | None = None
    source_ci_receipt_sha256: str | None = None
    tokenizer_preflight_prompt: str | None = None
    bridge_runtime_root: Path | None = None
    bridge_state_root: Path | None = None
    bridge_runtime_tree_manifest_path: Path | None = None
    bridge_runtime_tree_manifest_sha256: str | None = None
    node_executable_path: Path | None = None
    node_executable_sha256: str | None = None
    node_version: str | None = None
    python_executable_path: Path | None = None
    python_executable_sha256: str | None = None
    python_version: str | None = None
    unicode_data_version: str | None = None
    scorer_import_root: Path | None = None
    model_api_key_environment: str = "HSWM_DNRD_API_KEY"


@dataclass(frozen=True)
class ExecutionDependencies:
    answerer: Answerer
    bridge: Bridge
    scorer: OutcomeScorer
    verifier_runner: VerifierRunner
    live_preflight: LivePreflight
    git_runner: GitRunner | None = None
    git_bytes_runner: GitBytesRunner | None = None
    model_event_ledger: Callable[[], Sequence[Mapping[str, Any]]] | None = None
    closure_exporter: BridgeMountClosureExporter | None = None


@dataclass(frozen=True)
class ExecutionResult:
    output_dir: Path
    runner_result: RunnerResult
    event_ledger_sha256: str
    model_event_ledger_sha256: str | None


_HEX = frozenset("0123456789abcdef")
SOURCE_MANIFEST_SCHEMA = "hswm-dnrd-source-freeze-manifest/v1"
SOURCE_CI_RECEIPT_SCHEMA = "hswm-dnrd-source-ci-receipt/v1"
RATIFICATION_RECEIPT_SCHEMA = "hswm-dnrd-ratification-receipt/v1"
RATIFICATION_TEMPLATE_VERSION = "hswm-dnrd-ratification-statement/v1"
RATIFICATION_TEMPLATE = (
    "I ratify HSWM-DNRD-1 preregistration SHA-256 {preregistration_sha256} "
    "under hswm-dnrd-ratification-statement/v1."
)
ATTEMPT_LOCK_SCHEMA = "hswm-dnrd-durable-attempt-marker/v1"
GIT_CHRONOLOGY_EVIDENCE_SCHEMA = "hswm-dnrd-git-chronology-evidence/v2"
BUNDLE_INDEX_SCHEMA = "hswm-dnrd-evidence-bundle-index/v1"
ATTEMPT_MARKER_SCOPE = (
    "DETERMINISTIC_DURABLE_MARKER_UNDER_CONFIGURED_REGISTRY_ONLY_GLOBAL_SINGLETON_NOT_PROVEN"
)
RUNTIME_TREE_MANIFEST_SCHEMA = "hswm-dnrd-bridge-runtime-tree-manifest/v3"
RUNTIME_RECEIPT_SCHEMA = "hswm-dnrd-runtime-receipt/v3"
EXECUTION_CLOSURE_ISOLATION_CLAIM = (
    "OWNER_READ_EXECUTE_ONLY_COPIED_CLOSURES_PER_INVOCATION_ENTRYPOINT_REHASHED_"
    "SAME_UID_ADVERSARIAL_IMMUTABILITY_NOT_PROVEN"
)
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
TEST_EXECUTION_ADAPTER_BOUNDARY = (
    "TEST_ONLY_INJECTED_DEPENDENCIES_NOT_ADMISSIBLE_SCIENTIFIC_EVIDENCE"
)
SCORER_ISOLATED_LAUNCH_CODE = (
    "import runpy,sys;sys.path.insert(0,'.');"
    "runpy.run_module('_research.dnrd.scorer',run_name='__main__')"
)
SCORER_ARGUMENT_CONTRACT = ("-I", "-S", "-c", SCORER_ISOLATED_LAUNCH_CODE)
BRIDGE_MOUNT_CLOSURE_SCHEMA = "hswm-dnrd-bridge-mount-closure/v1"
BRIDGE_MOUNT_CLOSURE_LAYOUT = "hswm-dnrd-ts-file-adapter-mount-closure/v1"
BRIDGE_MOUNT_CLOSURE_MAX_FILE_BYTES = 1_048_576
BRIDGE_MOUNT_CLOSURE_MAX_FILES = 4_096
BRIDGE_MOUNT_CLOSURE_MAX_TOTAL_BYTES = 16_777_216
_MOUNT_ID_RE = re.compile(
    r"^dnrd-mount-v1-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_DIGEST_FILENAME_RE = re.compile(r"^[0-9a-f]{64}$")
PREREG_SCHEMA = "hswm-durable-numeric-routing-diagnostic-preregistration/v1"
RAW_REPLAY_DESCRIPTION = (
    "For each stream, replay exactly eight retained training update records containing "
    "scorer-outcome integer rewards through the frozen numeric score rule from W0; the "
    "records are derived from sealed responses and outcome digests. This is an "
    "engineering replay control, not a model-visible raw-transcript, equal-token, or "
    "durable-state-superiority comparison, and it does not claim cryptographic "
    "signatures on the "
    "update records."
)
PREREG_CLAIM_BOUNDARY = {
    "canonical_role": (
        "BOUNDED_SCHEMA_APPROVED_DURABLE_NUMERIC_ROUTING_MECHANICS_PROJECTION_"
        "NOT_HSWM_COGNITION_NOT_LEARNING_NOT_EFFICACY"
    ),
    "predecessor_bindings": [
        "P1_SCALAR_SLOW_WEIGHT_SCIENTIFIC_RED_ZERO_ACTIVE_UPDATES",
        "P1V3_P1V4_SYNTHETIC_L0_ACTUATION_ONLY_NO_L1_INHERITANCE",
        "P1V3V4_L1_CAUSAL_LESSON_KILLED_BEFORE_REGISTRATION_NO_REVIVAL",
    ],
    "forbidden_rescues": [
        "NO_POST_FREEZE_TUNING_OR_GATE_RELAXATION",
        "NO_RETRY_RERUN_RESUME_REPLACEMENT_OR_SECOND_PULSE",
        "NO_RELABELING_NUMERIC_REPLAY_AS_RAW_TRANSCRIPT_COMPARISON",
        "NO_PROMOTION_TO_LLM_LEARNING_UNSEEN_GENERALIZATION_UTILITY_OR_HSWM_EFFICACY",
    ],
    "scientific_question": (
        "Under source/runtime-trusted repeated-context exhaustive forced exposure, "
        "does a fixed scorer-outcome-bound integer routing payload persist across "
        "fresh-process recovery and alter pre-model route selection relative to exact "
        "W0 rollback and context-binding derangement, while fixed-rule replay of the "
        "same retained training update records reproduces the numeric payload?"
    ),
    "hypotheses": {
        "integrity_go": (
            "All frozen mechanics, parity, leakage, recovery, rollback, derangement, "
            "and replay-fidelity checks hold in the singleton occurrence."
        ),
        "diagnostic_no_go": (
            "At least one non-void mechanics check lacks headroom, persistence, exact "
            "rollback, behavioral actuation, derangement sensitivity, or replay fidelity."
        ),
        "void": (
            "Identity, chronology, leakage, parity, call accounting, immutable evidence, "
            "or singleton protocol integrity is contradicted."
        ),
    },
    "testbed_claims": {
        "relationship_to_prior_p1": (
            "SEPARATE_MECHANICS_DIAGNOSTIC_NO_RESCUE_NO_EFFICACY_INHERITANCE"
        ),
        "analysis_unit": "ONE_FUTURE_SEEDED_REPEATED_CONTEXT_STREAM_BY_ARM_PROJECTION",
        "freshness": (
            "FUTURE_QUICKNET_SEEDED_IDENTIFIERS_AND_CANARIES_WITH_REPEATED_CONTEXT_KEYS"
        ),
    },
    "learning_boundary": {
        "fixture_scope": (
            "ALL_CONTEXT_ROUTE_CELLS_FORCED_ONCE_AND_SAME_CONTEXTS_REUSED_AT_HELDOUT"
        ),
        "model_role": "SELECTED_EVIDENCE_ECHO_BOUNDARY_NOT_THE_LEARNER_UNDER_TEST",
        "scorer_role": "DECLARED_ROLE_SEPARATION_NOT_PROVEN",
        "raw_role": "FIXED_RULE_RETAINED_UPDATE_RECORD_NUMERIC_REPLAY_FIDELITY_ONLY",
    },
    "arms": {
        "FULL": (
            "For each stream, apply exactly eight locally declared scorer outcomes to the "
            "durable integer routing payload before read-only repeated-context evaluation."
        ),
        "NO_MEMORY_ROLLBACK": (
            "Recover and evaluate the exact immutable W0 genesis payload with no learned update."
        ),
        "RAW_EQUAL_BUDGET": RAW_REPLAY_DESCRIPTION,
        "BINDING_DERANGED_NUMERIC_PLACEBO": (
            "Permute context bindings within stratum while preserving the matched numeric "
            "payload byte count, precision, update multiset, and L1/L2 norms; full history, "
            "atom, and reference parity are not claimed."
        ),
    },
    "interventions": {
        "rollback": "EXACT_W0_RECOVERY_AND_POST_FULL_RESTORE_REPLAY",
        "binding_derangement": "WITHIN_STRATUM_NO_FIXED_POINT_CONTEXT_PERMUTATION",
        "raw_replay": "SAME_RETAINED_UPDATE_RECORDS_SAME_FIXED_INTEGER_UPDATE_RULE_FROM_W0",
    },
    "parity_claims": {
        "compiler_input_audit": (
            "SOURCE_SELECTED_PACKAGE_AND_COMPILER_BYTES_PINNED_BUILD_NOT_INDEPENDENTLY_REEXECUTED"
        ),
        "canary": (
            "FUTURE_SEEDED_TRAINING_ONLY_MARKERS_FORBIDDEN_FROM_HELDOUT_REQUESTS_ALL_"
            "MODEL_RESPONSES_ROUTING_STATE_AND_ALL_RAW_CLOSURE_BYTES"
        ),
    },
    "diagnostic_readouts": [
        "W0_HEADROOM_ON_REPEATED_CONTEXTS",
        "FULL_VS_W0_PRE_MODEL_ROUTE_DIFFERENCE",
        "FULL_VS_BINDING_DERANGEMENT_PRE_MODEL_ROUTE_DIFFERENCE",
        "FULL_VS_RAW_FIXED_RULE_NUMERIC_REPLAY_EQUALITY",
        "FRESH_PROCESS_STATE_RECOVERY",
        "EXACT_ROLLBACK_AND_RESTORE",
        "LEAKAGE_PARITY_AND_CALL_ACCOUNTING",
    ],
    "void_conditions": [
        "SOURCE_PREREG_RUNTIME_OR_GIT_IDENTITY_DRIFT",
        "TRAINING_CANARY_OR_PRIOR_ITEM_LEAKAGE",
        "CALL_RETRY_CACHE_OR_SCHEDULE_CONTRADICTION",
        "NONZERO_CLIENT_CACHE_HIT_OR_PROVIDER_CACHE_INDEPENDENCE_CLAIM",
        "MUTABLE_OR_INCOMPLETE_SOURCE_RUNTIME_OR_STATE_EVIDENCE",
        "SECOND_SINGLETON_ATTEMPT_OR_POST_OBSERVATION_REPLACEMENT",
    ],
    "single_attempt_policy": (
        "ONE_DURABLE_MARKER_SCOPED_SINGLETON_OCCURRENCE_NO_RETRY_RERUN_RESUME_OR_REPLACEMENT"
    ),
    "required_before_measurement": [
        "CLEAN_PUSHED_SOURCE_A_WITH_EXACT_SOURCE_MANIFEST",
        "SUCCESSFUL_GITHUB_ACTIONS_RECEIPT_FOR_EXACT_SOURCE_A",
        "DIRECT_CHILD_PREREGISTRATION_B_CHANGING_EXACTLY_ONE_PREREG_PATH",
        "EXTERNAL_EXACT_PREREGISTRATION_SHA256_RATIFICATION_RECEIPT",
        "FIRST_ELIGIBLE_QUICKNET_PULSE_AT_LEAST_900_SECONDS_AFTER_SOURCE_A_AND_RATIFICATION",
    ],
    "result_promotion": {
        "only_go_terminal": "DIAGNOSTIC_INTEGRITY_GO_NO_UTILITY_CLAIM",
        "non_go_terminals": [
            "DIAGNOSTIC_NO_GO",
            "VOID_PROTOCOL",
            "INCONCLUSIVE_OCCURRENCE",
        ],
        "confirmatory_effect": (
            "MAY_ONLY_OPEN_A_SEPARATELY_PREREGISTERED_CONFIRMATORY_DESIGN"
        ),
        "forbidden_claims": [
            "LLM_LEARNING",
            "UNSEEN_CONTEXT_GENERALIZATION",
            "INDEPENDENT_OUTCOME_OR_SCORER_ISOLATION",
            "UTILITY_OR_DURABLE_STATE_SUPERIORITY",
            "HSWM_CONTINUOUS_LEARNING_OR_EFFICACY",
            "TOPOLOGY_ROLE_SPECIALIZATION_TRANSFER_OR_CONSOLIDATION",
        ],
    },
    "measurement_gate": (
        "NO_GENERATION_BEFORE_EXTERNAL_EXACT_HASH_RATIFICATION_AND_FIRST_ELIGIBLE_"
        "QUICKNET_PULSE_AT_LEAST_900_SECONDS_AFTER_SOURCE_A_AND_RATIFICATION"
    ),
}
CORE_SOURCE_FILES = frozenset(
    {
        "_research/dnrd/__init__.py",
        "_research/dnrd/task_family.py",
        "_research/dnrd/scorer.py",
        "_research/dnrd/seed.py",
        "_research/dnrd/runner.py",
        "_research/dnrd/live.py",
        "_research/dnrd/execute.py",
        "_research/dnrd/judge.py",
        "tests/test_hswm_dnrd_execute.py",
        "tests/test_hswm_dnrd_judge.py",
        "tests/test_hswm_dnrd_live.py",
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
        "docs/research/HSWM_DNRD_SOURCE_A_SCIENTIFIC_BOUNDARY_2026-08-27.md",
    }
)


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash_file(path: Path) -> str:
    _plain_file(path, f"required file {path}")
    return _sha_bytes(path.read_bytes())


_ORDINARY_ESM_DEPENDENCY_PATTERNS = (
    re.compile(r"(?m)^[ \t]*import(?:[ \t\r\n({*\"']|$)"),
    re.compile(r"\bimport[ \t\r\n]*\("),
    re.compile(
        r"(?ms)^[ \t]*export[ \t\r\n]+(?:\*|\{).{0,4096}?\bfrom"
        r"[ \t\r\n]*[\"']"
    ),
)


def _validated_verifier_runtime_bundle_bytes(
    path: Path, *, require_official_identity: bool
) -> bytes:
    """Read one bounded UTF-8 ESM bundle before Node is allowed to load it."""
    _plain_file(path, "verifier runtime bundle")
    raw = path.read_bytes()
    if not raw or len(raw) > VERIFIER_RUNTIME_BUNDLE_MAX_BYTES:
        raise ExecutionRefusal("verifier runtime bundle exceeds its exact byte boundary")
    try:
        source = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ExecutionRefusal("verifier runtime bundle must be strict UTF-8") from error
    if "\x00" in source or any(
        pattern.search(source) is not None
        for pattern in _ORDINARY_ESM_DEPENDENCY_PATTERNS
    ):
        raise ExecutionRefusal(
            "verifier runtime bundle contains an ordinary external ESM dependency"
        )
    if (
        require_official_identity
        and _sha_bytes(raw) != OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256
    ):
        raise ExecutionRefusal(
            "production verifier runtime bundle is not the Source-A-pinned official artifact"
        )
    return raw


def _hex(value: str, label: str, length: int = 64) -> None:
    if not isinstance(value, str) or len(value) != length or any(char not in _HEX for char in value):
        raise ExecutionRefusal(f"{label} must be lowercase {length}-hex")


def _frozen_date(value: object, label: str) -> str:
    """Accept one calendar-valid ISO date with no free-form metadata suffix."""
    if type(value) is not str or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ExecutionRefusal(f"{label} must be an exact ISO-8601 date (YYYY-MM-DD)")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise ExecutionRefusal(f"{label} must be a valid calendar date") from error
    return value


def _strict_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    """Load one canonical object without duplicate keys or NaN carriers."""
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ExecutionRefusal(f"{label} is not UTF-8") from error

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ExecutionRefusal(f"{label} repeats JSON key {key!r}")
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise ExecutionRefusal(f"{label} contains non-finite JSON value {value!r}")

    try:
        value = json.loads(text, object_pairs_hook=no_duplicates, parse_constant=reject_constant)
    except (json.JSONDecodeError, ExecutionRefusal) as error:
        if isinstance(error, ExecutionRefusal):
            raise
        raise ExecutionRefusal(f"{label} is not JSON") from error
    if type(value) is not dict:
        raise ExecutionRefusal(f"{label} root must be an object")
    if canonical_json(value) != data:
        raise ExecutionRefusal(f"{label} must be exact canonical JSON bytes")
    return value


def _exact_keys(value: object, expected: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise ExecutionRefusal(f"{label} key set drifted")
    return value


def _relative_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("/"):
        raise ExecutionRefusal(f"{label} must be a nonempty repository-relative path")
    path = Path(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ExecutionRefusal(f"{label} escapes its repository root")
    return value


def _plain_directory(path: Path, label: str, *, mode: int | None = None) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError as error:
        raise ExecutionRefusal(f"{label} is absent") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ExecutionRefusal(f"{label} must be a plain directory")
    if mode is not None and stat.S_IMODE(info.st_mode) != mode:
        raise ExecutionRefusal(f"{label} must have mode {mode:04o}")


def _plain_file(path: Path, label: str) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError as error:
        raise ExecutionRefusal(f"{label} is absent") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ExecutionRefusal(f"{label} must be a plain regular file")


def _plain_relative_file(root: Path, relative: str, label: str) -> Path:
    """Resolve one manifest path while rejecting every symlinked ancestor."""
    _relative_path(relative, label)
    _plain_directory(root, f"{label} root")
    current = root
    parts = Path(relative).parts
    for part in parts[:-1]:
        current = current / part
        _plain_directory(current, f"{label} parent {current}")
    target = root / relative
    _plain_file(target, label)
    return target


def _atomic_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    if path.exists():
        raise ExecutionRefusal(f"refusing to overwrite artifact {path}")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _atomic_json(path: Path, value: Mapping[str, Any], mode: int = 0o600) -> None:
    _atomic_bytes(path, canonical_json(value), mode)


def _copy_bounded_closure_file(
    *,
    source_root: Path,
    relative: str,
    expected_sha256: str,
    destination_root: Path,
) -> None:
    """Copy one manifest-addressed regular file without widening the closure."""
    _relative_path(relative, "closure file path")
    source = _plain_relative_file(source_root, relative, "closure source file")
    if _hash_file(source) != expected_sha256:
        raise ExecutionRefusal(f"closure source file hash drifted: {relative}")
    destination = destination_root / relative
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    for parent in (destination_root, *destination.parents):
        if parent.exists():
            _plain_directory(parent, f"closure destination parent {parent}")
    _atomic_bytes(destination, source.read_bytes(), 0o400)
    if _hash_file(destination) != expected_sha256:
        raise ExecutionRefusal(f"closure artifact hash drifted after copy: {relative}")


def _copy_source_closure(output_root: Path, repo_root: Path, manifest: Mapping[str, Any]) -> None:
    closure = output_root / "source_closure"
    closure.mkdir(mode=0o700)
    for row in manifest["files"]:
        _copy_bounded_closure_file(
            source_root=repo_root,
            relative=row["path"],
            expected_sha256=row["sha256"],
            destination_root=closure,
        )
    _seal_execution_closure(closure)


def _copy_runtime_closure(
    output_root: Path,
    runtime_root: Path,
    runtime_manifest: Mapping[str, Any],
) -> None:
    closure = output_root / "bridge_runtime_closure"
    closure.mkdir(mode=0o700)
    copied: set[str] = set()
    for row in runtime_manifest["files"]:
        _copy_bounded_closure_file(
            source_root=runtime_root,
            relative=row["path"],
            expected_sha256=row["sha256"],
            destination_root=closure,
        )
        copied.add(row["path"])
    for package in runtime_manifest["external_packages"]:
        for row in package["files"]:
            path, digest = row["path"], row["sha256"]
            if path in copied:
                raise ExecutionRefusal("runtime closure repeats a compiled/package file")
            _copy_bounded_closure_file(
                source_root=runtime_root,
                relative=path,
                expected_sha256=digest,
                destination_root=closure,
            )
            copied.add(path)
    _seal_execution_closure(closure)


def _seal_execution_closure(root: Path) -> None:
    """Remove owner-write bits after a complete copied execution closure exists."""
    directories = [root]
    for path in root.rglob("*"):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ExecutionRefusal("execution closure contains a symlink")
        if stat.S_ISDIR(info.st_mode):
            directories.append(path)
        elif not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o400:
            raise ExecutionRefusal("execution closure contains a non-0400 regular file")
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        os.chmod(directory, 0o500)


def _closure_directory_names(path: Path, label: str) -> list[str]:
    _plain_directory(path, label, mode=0o700)
    names: list[str] = []
    for child in path.iterdir():
        info = child.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ExecutionRefusal(f"{label} contains a symlink")
        names.append(child.name)
    if names != sorted(names):
        # ``Path.iterdir`` makes no ordering promise; this branch documents
        # that callers compare a sorted copy below rather than filesystem order.
        names.sort()
    return names


def _read_immutable_closure_source(root: Path, relative: str) -> bytes:
    path = _plain_relative_file(root, relative, "bridge mount closure source")
    flags = os.O_RDONLY | os.O_NONBLOCK
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o400
            or before.st_size < 1
            or before.st_size > BRIDGE_MOUNT_CLOSURE_MAX_FILE_BYTES
        ):
            raise ExecutionRefusal(
                "bridge mount closure source must be a bounded immutable 0400 file"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            body = handle.read(BRIDGE_MOUNT_CLOSURE_MAX_FILE_BYTES + 1)
        after = os.fstat(descriptor)
        if (
            len(body) != before.st_size
            or after.st_dev != before.st_dev
            or after.st_ino != before.st_ino
            or after.st_size != before.st_size
            or stat.S_IMODE(after.st_mode) != 0o400
        ):
            raise ExecutionRefusal("bridge mount closure source changed during read")
        return body
    finally:
        os.close(descriptor)


def _closure_destination_parent(root: Path, relative: str) -> None:
    _relative_path(relative, "bridge mount closure destination path")
    parent = root
    for part in Path(relative).parts[:-1]:
        parent = parent / part
        if parent.exists():
            _plain_directory(parent, "bridge mount closure destination parent", mode=0o700)
        else:
            parent.mkdir(mode=0o700)
            os.chmod(parent, 0o700)
            _plain_directory(parent, "bridge mount closure destination parent", mode=0o700)


def _closure_plan_mounts(plan: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    required = {"schema_version", "bridge_state_evidence_sha256", "streams"}
    _exact_keys(plan, required, "bridge mount closure plan")
    if plan["schema_version"] != BRIDGE_MOUNT_CLOSURE_PLAN_SCHEMA:
        raise ExecutionRefusal("bridge mount closure plan schema drifted")
    bridge_state_evidence_sha256 = plan["bridge_state_evidence_sha256"]
    _hex(bridge_state_evidence_sha256, "bridge mount closure plan state evidence")
    streams = plan["streams"]
    if type(streams) is not list or len(streams) != 4:
        raise ExecutionRefusal("bridge mount closure plan must name exactly four streams")
    mounts: list[dict[str, Any]] = []
    seen_streams: set[str] = set()
    seen_mounts: set[str] = set()
    expected_arm_fields = {
        "mount_id",
        "mount_role",
        "pre_evaluation_journal_sha256",
        "post_evaluation_journal_sha256",
        "pre_evaluation_routing_payload_sha256",
        "post_evaluation_routing_payload_sha256",
    }
    for index, item in enumerate(streams):
        stream = _exact_keys(item, {"stream_id", "arms"}, "bridge mount closure plan stream")
        stream_id = stream["stream_id"]
        if (
            not isinstance(stream_id, str)
            or stream_id != f"stream-{index}"
            or stream_id in seen_streams
            or type(stream["arms"]) is not dict
            or set(stream["arms"]) != set(ARMS)
        ):
            raise ExecutionRefusal("bridge mount closure plan stream support drifted")
        seen_streams.add(stream_id)
        for arm in ARMS:
            value = _exact_keys(
                stream["arms"][arm],
                expected_arm_fields,
                "bridge mount closure plan arm",
            )
            mount_id = value["mount_id"]
            if (
                not isinstance(mount_id, str)
                or _MOUNT_ID_RE.fullmatch(mount_id) is None
                or mount_id in seen_mounts
                or value["mount_role"] != MOUNT_ROLES[arm]
            ):
                raise ExecutionRefusal("bridge mount closure plan mount identity/role drifted")
            seen_mounts.add(mount_id)
            for key in (
                "pre_evaluation_journal_sha256",
                "post_evaluation_journal_sha256",
                "pre_evaluation_routing_payload_sha256",
                "post_evaluation_routing_payload_sha256",
            ):
                _hex(value[key], f"bridge mount closure plan {key}")
            mounts.append(
                {
                    "stream_id": stream_id,
                    "arm": arm,
                    "mount_id": mount_id,
                    "mount_role": value["mount_role"],
                    "pre_evaluation_journal_sha256": value[
                        "pre_evaluation_journal_sha256"
                    ],
                    "post_evaluation_journal_sha256": value[
                        "post_evaluation_journal_sha256"
                    ],
                    "pre_evaluation_routing_payload_sha256": value[
                        "pre_evaluation_routing_payload_sha256"
                    ],
                    "post_evaluation_routing_payload_sha256": value[
                        "post_evaluation_routing_payload_sha256"
                    ],
                }
            )
    if seen_streams != {"stream-0", "stream-1", "stream-2", "stream-3"} or len(
        seen_mounts
    ) != 16:
        raise ExecutionRefusal("bridge mount closure plan does not name exact DNRD mounts")
    return bridge_state_evidence_sha256, sorted(
        mounts, key=lambda item: (item["stream_id"], item["arm"])
    )


class _ProductionBridgeMountClosureExporter:
    """Copy an allowlisted, immutable raw V2 mount closure into one bundle.

    It is intentionally not a general state-root archive.  The runner plan
    fixes all sixteen mounts before this code touches the filesystem, and this
    exporter refuses any extra root, registry, reservation, directory, or
    object entry rather than widening evidence after an occurrence.
    """

    def __init__(self, state_root: Path, output_root: Path) -> None:
        self._state_root = state_root
        self._output_root = output_root

    def export(
        self,
        plan: Mapping[str, Any],
        *,
        forbidden_markers: frozenset[str],
    ) -> BridgeMountClosureExport:
        if (
            not forbidden_markers
            or any(
                not isinstance(marker, str)
                or not marker
                or marker.encode("utf-8").decode("utf-8") != marker
                for marker in forbidden_markers
            )
        ):
            raise ExecutionRefusal("bridge mount closure canary set is malformed")
        marker_bytes = tuple(marker.encode("utf-8") for marker in sorted(forbidden_markers))
        bridge_state_evidence_sha256, mounts = _closure_plan_mounts(plan)
        plan_sha256 = commitment(dict(plan))
        root = self._state_root
        _plain_directory(root, "bridge state root", mode=0o700)
        expected_root = {"root-config.json", "mounts", "registry", "streams", "controls"}
        if set(_closure_directory_names(root, "bridge state root")) != expected_root:
            raise ExecutionRefusal("bridge state root has unexpected mount-closure entries")
        mounts_root, registry_root = root / "mounts", root / "registry"
        streams_root, controls_root = root / "streams", root / "controls"
        mount_ids = {item["mount_id"] for item in mounts}
        if set(_closure_directory_names(mounts_root, "bridge mounts root")) != mount_ids:
            raise ExecutionRefusal("bridge mounts root does not equal the sixteen observed mounts")
        expected_registry = {f"{mount_id}.json" for mount_id in mount_ids}
        if set(_closure_directory_names(registry_root, "bridge registry root")) != expected_registry:
            raise ExecutionRefusal("bridge registry root does not equal observed mount metadata")
        expected_streams = {f"stream-{index}.json" for index in range(4)}
        if set(_closure_directory_names(streams_root, "bridge streams root")) != expected_streams:
            raise ExecutionRefusal("bridge stream reservations do not match the four streams")
        expected_controls = {
            f"stream-{index}-{arm}.json"
            for index in range(4)
            for arm in (
                "RAW_EQUAL_BUDGET",
                "BINDING_DERANGED_NUMERIC_PLACEBO",
            )
        }
        if set(_closure_directory_names(controls_root, "bridge controls root")) != expected_controls:
            raise ExecutionRefusal("bridge control reservations do not match frozen control arms")

        source_paths: list[str] = ["root-config.json"]
        source_paths.extend(f"streams/{name}" for name in sorted(expected_streams))
        source_paths.extend(f"controls/{name}" for name in sorted(expected_controls))
        source_paths.extend(
            f"registry/{mount_id}.json" for mount_id in sorted(mount_ids)
        )
        mount_leaf_directories = (
            "schema-bindings",
            "objects",
            "journal-objects",
            "journal-slots",
        )
        for mount_id in sorted(mount_ids):
            mount_root = mounts_root / mount_id
            if set(_closure_directory_names(mount_root, f"bridge mount {mount_id}")) != set(
                mount_leaf_directories
            ):
                raise ExecutionRefusal("bridge mount has unexpected durable directory entries")
            for leaf in mount_leaf_directories:
                leaf_root = mount_root / leaf
                names = _closure_directory_names(
                    leaf_root, f"bridge mount {mount_id} {leaf}"
                )
                if not names or any(_DIGEST_FILENAME_RE.fullmatch(name) is None for name in names):
                    raise ExecutionRefusal("bridge mount closure durable file name is invalid")
                source_paths.extend(f"mounts/{mount_id}/{leaf}/{name}" for name in names)

        if len(source_paths) > BRIDGE_MOUNT_CLOSURE_MAX_FILES:
            raise ExecutionRefusal("bridge mount closure exceeds the frozen file-count bound")
        if len(set(source_paths)) != len(source_paths):
            raise ExecutionRefusal("bridge mount closure source path plan is not one-to-one")
        closure_root = self._output_root / "bridge_mount_closure"
        manifest_path = self._output_root / "bridge_mount_closure.json"
        if closure_root.exists() or manifest_path.exists():
            raise ExecutionRefusal("refusing to overwrite bridge mount closure artifact")
        temporary_root = Path(
            tempfile.mkdtemp(prefix=".bridge-mount-closure-", dir=self._output_root)
        )
        os.chmod(temporary_root, 0o700)
        published_root = False
        try:
            copied_files: list[dict[str, Any]] = []
            total_bytes = 0
            watermark_detected = False
            for relative in sorted(source_paths):
                body = _read_immutable_closure_source(root, relative)
                watermark_detected = watermark_detected or any(
                    marker in body for marker in marker_bytes
                )
                parent_name = Path(relative).parent.name
                if parent_name in {"objects", "journal-objects"}:
                    if _sha_bytes(body) != Path(relative).name:
                        raise ExecutionRefusal(
                            "content/journal object filename does not bind exact bytes"
                        )
                total_bytes += len(body)
                if total_bytes > BRIDGE_MOUNT_CLOSURE_MAX_TOTAL_BYTES:
                    raise ExecutionRefusal(
                        "bridge mount closure exceeds the frozen total-byte bound"
                    )
                _closure_destination_parent(temporary_root, relative)
                destination = temporary_root / relative
                _atomic_bytes(destination, body, 0o400)
                _plain_file(destination, "copied bridge mount closure file")
                if stat.S_IMODE(destination.lstat().st_mode) != 0o400:
                    raise ExecutionRefusal("copied bridge mount closure file mode drifted")
                copied_files.append(
                    {
                        "path": relative,
                        "sha256": _sha_bytes(body),
                        "bytes": len(body),
                        "mode": 0o400,
                    }
                )
            if [item["path"] for item in copied_files] != sorted(
                item["path"] for item in copied_files
            ):
                raise ExecutionRefusal("bridge mount closure file listing is not canonical")
            unsigned = {
                "schema_version": BRIDGE_MOUNT_CLOSURE_SCHEMA,
                "layout": BRIDGE_MOUNT_CLOSURE_LAYOUT,
                "bridge_state_evidence_sha256": bridge_state_evidence_sha256,
                "closure_plan_sha256": plan_sha256,
                "mounts": mounts,
                "files": copied_files,
            }
            manifest = {**unsigned, "receipt_sha256": commitment(unsigned)}
            _atomic_json(manifest_path, manifest, 0o400)
            os.replace(temporary_root, closure_root)
            published_root = True
            return BridgeMountClosureExport(
                artifact_sha256=_sha_bytes(manifest_path.read_bytes()),
                watermark_detected=watermark_detected,
            )
        except Exception:
            if temporary_root.exists():
                shutil.rmtree(temporary_root)
            if published_root:
                # This directory was just installed from our private temporary
                # path and the manifest/candidate transaction has failed.
                shutil.rmtree(closure_root)
            if manifest_path.exists():
                manifest_path.unlink()
            raise


def _bundle_index(output_root: Path) -> dict[str, Any]:
    """Self-address every emitted artifact except this index (avoids a cycle)."""
    entries: list[dict[str, Any]] = []
    for path in sorted(output_root.rglob("*")):
        if path == output_root / "bundle_index.json" or path.is_dir():
            continue
        _plain_file(path, f"bundle artifact {path}")
        relative = path.relative_to(output_root).as_posix()
        body = path.read_bytes()
        entries.append(
            {
                "path": relative,
                "sha256": _sha_bytes(body),
                "bytes": len(body),
            }
        )
    if [entry["path"] for entry in entries] != sorted(entry["path"] for entry in entries):
        raise ExecutionRefusal("bundle index artifact paths are not canonical")
    unsigned = {
        "schema_version": BUNDLE_INDEX_SCHEMA,
        "artifacts": entries,
    }
    return {**unsigned, "receipt_sha256": commitment(unsigned)}


def _default_git(args: Sequence[str], cwd: Path) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise ExecutionRefusal(f"git {' '.join(args)} refused")
    return completed.stdout


def _default_git_bytes(args: Sequence[str], cwd: Path) -> bytes:
    completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=False)
    if completed.returncode != 0:
        raise ExecutionRefusal(f"git {' '.join(args)} refused")
    return bytes(completed.stdout)


def _git(config: ExecutionConfig, dependencies: ExecutionDependencies, *args: str) -> str:
    return (dependencies.git_runner or _default_git)(args, config.repo_root)


def _git_bytes(config: ExecutionConfig, dependencies: ExecutionDependencies, *args: str) -> bytes:
    """Read an exact Git object/body without lossy text decoding.

    The injected byte seam exists solely for hermetic execution tests.  A test
    that wants to claim tree-object evidence must provide raw bytes too; a
    text-only fake cannot silently stand in for binary Git tree objects.
    """
    if dependencies.git_bytes_runner is not None:
        return dependencies.git_bytes_runner(args, config.repo_root)
    if dependencies.git_runner is not None:
        raise ExecutionRefusal("injected git execution requires an exact byte-object runner")
    return _default_git_bytes(args, config.repo_root)


def _load_source_manifest(config: ExecutionConfig) -> dict[str, Any]:
    path = _plain_relative_file(
        config.repo_root, config.source_manifest_path, "source manifest"
    )
    raw = path.read_bytes()
    if _sha_bytes(raw) != config.source_manifest_sha256:
        raise ExecutionRefusal("source manifest content hash drifted")
    value = _strict_json_bytes(raw, "source manifest")
    manifest = _exact_keys(
        value,
        {
            "schema_version",
            "experiment_id",
            "source_commit_tree_bound_externally",
            "files",
        },
        "source manifest",
    )
    if (
        manifest["schema_version"] != SOURCE_MANIFEST_SCHEMA
        or manifest["experiment_id"] != "HSWM-DNRD-1"
        or manifest["source_commit_tree_bound_externally"]
        != "SOURCE_COMMIT_TREE_BOUND_EXTERNALLY_NO_SELF_CYCLE"
    ):
        raise ExecutionRefusal("source manifest external source-A binding declaration drifted")
    files = manifest["files"]
    if type(files) is not list or not files:
        raise ExecutionRefusal("source manifest must list frozen source files")
    seen: set[str] = set()
    ordered: list[str] = []
    for index, row in enumerate(files):
        entry = _exact_keys(row, {"path", "sha256"}, f"source manifest.files[{index}]")
        relative = _relative_path(entry["path"], f"source manifest.files[{index}].path")
        _hex(entry["sha256"], f"source manifest.files[{index}].sha256")
        if relative in seen:
            raise ExecutionRefusal("source manifest repeats a path")
        seen.add(relative)
        ordered.append(relative)
        if _hash_file(
            _plain_relative_file(config.repo_root, relative, "frozen source file")
        ) != entry["sha256"]:
            raise ExecutionRefusal(f"frozen source file hash drifted: {relative}")
    if ordered != sorted(ordered) or seen != CORE_SOURCE_FILES:
        raise ExecutionRefusal("source manifest lacks the exact DNRD source closure")
    return dict(manifest)


def _load_attested_receipt(
    *,
    path: Path | None,
    digest: str | None,
    schema: str,
    expected_keys: set[str],
    label: str,
) -> tuple[dict[str, Any], bytes]:
    if path is None or digest is None:
        raise ExecutionRefusal(f"{label} path and SHA-256 pin are required")
    _hex(digest, f"{label} SHA-256")
    raw = path.read_bytes()
    if _sha_bytes(raw) != digest:
        raise ExecutionRefusal(f"{label} content hash drifted")
    value = _strict_json_bytes(raw, label)
    receipt = _exact_keys(value, expected_keys, label)
    if receipt["schema_version"] != schema:
        raise ExecutionRefusal(f"{label} schema mismatch")
    unsigned = {key: item for key, item in receipt.items() if key != "receipt_sha256"}
    if receipt.get("receipt_sha256") != commitment(unsigned):
        raise ExecutionRefusal(f"{label} self-hash mismatch")
    return dict(receipt), raw


def _load_ratification_receipt(config: ExecutionConfig) -> tuple[dict[str, Any], bytes]:
    receipt, raw = _load_attested_receipt(
        path=config.ratification_receipt_path,
        digest=config.ratification_receipt_sha256,
        schema=RATIFICATION_RECEIPT_SCHEMA,
        expected_keys={
            "schema_version",
            "preregistration_sha256",
            "statement_sha256",
            "ratified_at_unix",
            "attested_by",
            "receipt_sha256",
        },
        label="ratification receipt",
    )
    if (
        receipt["preregistration_sha256"] != config.prereg_sha256
        or receipt["statement_sha256"] != config.ratification_text_sha256
        or receipt["ratified_at_unix"] != config.ratification_unix
        or type(receipt["ratified_at_unix"]) is not int
        or receipt["ratified_at_unix"] <= 0
        or not isinstance(receipt["attested_by"], str)
        or not receipt["attested_by"]
    ):
        raise ExecutionRefusal("ratification receipt does not attest exact text, preregistration, and time")
    return receipt, raw


def _load_source_ci_receipt(config: ExecutionConfig) -> tuple[dict[str, Any], bytes]:
    receipt, raw = _load_attested_receipt(
        path=config.source_ci_receipt_path,
        digest=config.source_ci_receipt_sha256,
        schema=SOURCE_CI_RECEIPT_SCHEMA,
        expected_keys={
            "schema_version",
            "provider",
            "run_id",
            "head_sha",
            "conclusion",
            "raw_response_sha256",
            "raw_response_utf8",
            "receipt_sha256",
        },
        label="source CI receipt",
    )
    if (
        receipt["provider"] != "GITHUB_ACTIONS"
        or type(receipt["run_id"]) is not int
        or receipt["run_id"] <= 0
        or receipt["head_sha"] != config.source_a_commit
        or receipt["conclusion"] != "success"
    ):
        raise ExecutionRefusal("source CI receipt is not a green exact-A GitHub Actions run")
    _hex(receipt["raw_response_sha256"], "source CI receipt raw response SHA-256")
    if (
        not isinstance(receipt["raw_response_utf8"], str)
        or _sha_bytes(receipt["raw_response_utf8"].encode("utf-8"))
        != receipt["raw_response_sha256"]
    ):
        raise ExecutionRefusal("source CI raw response bytes do not match the pinned digest")
    try:
        # This is the original API body, not a locally reformatted projection:
        # its exact UTF-8 bytes are already hash-bound above.  Remote JSON has
        # no canonical whitespace/key-order guarantee, but duplicate keys and
        # non-finite constants would make its semantic projection ambiguous.
        raw_api = _json_object_unformatted(
            receipt["raw_response_utf8"],
            "source CI raw API response",
        )
    except ExecutionRefusal as error:
        raise ExecutionRefusal("source CI receipt does not retain a strictly parseable raw API response") from error
    if (
        raw_api.get("id") != receipt["run_id"]
        or raw_api.get("head_sha") != receipt["head_sha"]
        or raw_api.get("conclusion") != receipt["conclusion"]
    ):
        raise ExecutionRefusal("source CI raw API response does not attest run/head/conclusion")
    return receipt, raw


def _validate_preregistration(
    config: ExecutionConfig,
    *,
    source_ci_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    prereg_path = _plain_relative_file(
        config.repo_root, config.prereg_path, "preregistration"
    )
    raw = prereg_path.read_bytes()
    if _sha_bytes(raw) != config.prereg_sha256:
        raise ExecutionRefusal("preregistration content hash drifted")
    prereg = _strict_json_bytes(raw, "preregistration")
    required = {
        "schema_version",
        "experiment_id",
        "protocol_version",
        "created_at",
        "status",
        "authority",
        "canonical_role",
        "predecessor_bindings",
        "forbidden_rescues",
        "scientific_question",
        "hypotheses",
        "testbed",
        "learning_boundary",
        "arms",
        "interventions",
        "parity_and_leakage",
        "diagnostic_readouts",
        "void_conditions",
        "single_attempt_policy",
        "required_before_measurement",
        "result_promotion",
        "measurement_gate",
        "ratification",
        "source_a_ci",
        "runtime_bindings",
    }
    data = _exact_keys(prereg, required, "preregistration")
    if (
        data["schema_version"] != PREREG_SCHEMA
        or data["experiment_id"] != "HSWM-DNRD-1"
        or data["protocol_version"] != "v1"
        or data["status"] != "FROZEN_AWAITING_EXACT_HASH_RATIFICATION"
    ):
        raise ExecutionRefusal("preregistration identity/status is not the frozen pre-ratification contract")
    _frozen_date(data["created_at"], "preregistration.created_at")
    authority = _exact_keys(
        data["authority"],
        {
            "broad_research_continuation_requested",
            "exact_content_hash_user_ratified_at_freeze",
            "measurement_authorized_at_freeze",
            "measurement_requires_external_exact_hash_ratification_receipt",
            "scientific_judgment_emitted",
            "external_governance_required",
        },
        "preregistration.authority",
    )
    if (
        authority["broad_research_continuation_requested"] is not True
        or authority["exact_content_hash_user_ratified_at_freeze"] is not False
        or authority["measurement_authorized_at_freeze"] is not False
        or authority["measurement_requires_external_exact_hash_ratification_receipt"] is not True
        or authority["scientific_judgment_emitted"] is not False
        or authority["external_governance_required"] is not False
    ):
        raise ExecutionRefusal("preregistration authority does not preserve external-ratification gating")
    ratification = _exact_keys(
        data["ratification"],
        {"statement_template_version", "statement_template"},
        "preregistration.ratification",
    )
    if (
        ratification["statement_template_version"] != RATIFICATION_TEMPLATE_VERSION
        or ratification["statement_template"] != RATIFICATION_TEMPLATE
    ):
        raise ExecutionRefusal("preregistration does not freeze the exact ratification statement")
    ci = _exact_keys(
        data["source_a_ci"],
        {"receipt_sha256", "run_id", "head_sha", "conclusion"},
        "preregistration.source_a_ci",
    )
    if (
        ci["receipt_sha256"] != config.source_ci_receipt_sha256
        or ci["run_id"] != source_ci_receipt["run_id"]
        or ci["head_sha"] != config.source_a_commit
        or ci["conclusion"] != "success"
    ):
        raise ExecutionRefusal("preregistration does not bind the green source-A CI receipt")
    runtime = _exact_keys(
        data["runtime_bindings"],
        {
            "model_endpoint",
            "bridge_implementation_sha256",
            "bridge_runtime_tree_manifest_sha256",
            "bridge_config_sha256",
            "scorer_implementation_sha256",
            "node_executable_sha256",
            "node_version",
            "python_executable_sha256",
            "python_version",
            "unicode_data_version",
            "verifier_helper_sha256",
            "verifier_package_lock_sha256",
            "verifier_runtime_bundle_sha256",
            "subprocess_environment",
        },
        "preregistration.runtime_bindings",
    )
    if (
        runtime["model_endpoint"] != config.model_endpoint
        or runtime["bridge_implementation_sha256"] != config.bridge_implementation_sha256
        or runtime["bridge_runtime_tree_manifest_sha256"]
        != config.bridge_runtime_tree_manifest_sha256
        or runtime["bridge_config_sha256"] != commitment(dict(config.bridge_config))
        or runtime["scorer_implementation_sha256"] != config.scorer_implementation_sha256
        or runtime["node_executable_sha256"] != config.node_executable_sha256
        or runtime["node_version"] != config.node_version
        or runtime["python_executable_sha256"] != config.python_executable_sha256
        or runtime["python_version"] != config.python_version
        or runtime["unicode_data_version"] != config.unicode_data_version
        or runtime["verifier_helper_sha256"] != config.verifier_helper_sha256
        or runtime["verifier_package_lock_sha256"] != config.verifier_package_lock_sha256
        or runtime["verifier_runtime_bundle_sha256"] != config.verifier_runtime_bundle_sha256
        or runtime["subprocess_environment"] != _pinned_subprocess_environment()
    ):
        raise ExecutionRefusal("preregistration runtime identities do not match the supplied frozen config")
    testbed = _exact_keys(
        data["testbed"],
        {
            "family",
            "relationship_to_prior_p1",
            "development_streams",
            "training_calls_per_stream_maximum",
            "paired_heldout_probes_per_stream",
            "evaluation_arms",
            "evaluation_calls",
            "shared_learning_or_compiler_calls_maximum",
            "client_dispatched_generation_request_ceiling",
            "analysis_unit",
            "model",
            "freshness",
        },
        "preregistration.testbed",
    )
    model = _exact_keys(
        testbed["model"],
        {
            "served_model_id",
            "substitution_allowed",
            "temperature",
            "thinking",
            "max_output_tokens",
            "deployment_readback_required",
            "exact_weight_revision_attested",
            "exact_weight_identity_claimed",
        },
        "preregistration.testbed.model",
    )
    if (
        testbed["family"] != "REPEATED_CONTEXT_TABULAR_ROUTING_MECHANICS_V1"
        or testbed["development_streams"] != 4
        or testbed["training_calls_per_stream_maximum"] != 8
        or testbed["paired_heldout_probes_per_stream"] != 8
        or testbed["evaluation_arms"] != 4
        or testbed["evaluation_calls"] != 128
        or testbed["shared_learning_or_compiler_calls_maximum"] != 32
        or testbed["client_dispatched_generation_request_ceiling"] != 160
        or model["served_model_id"] != MODEL_ID
        or model["substitution_allowed"] is not False
        or model["temperature"] != 0
        or model["thinking"] is not False
        or model["max_output_tokens"] != MAX_OUTPUT_TOKENS
        or model["deployment_readback_required"] is not True
        or model["exact_weight_revision_attested"] is not False
        or model["exact_weight_identity_claimed"] is not False
    ):
        raise ExecutionRefusal("preregistration testbed/model contract differs from frozen DNRD runtime")
    arms = _exact_keys(
        data["arms"],
        {
            "FULL",
            "NO_MEMORY_ROLLBACK",
            "RAW_EQUAL_BUDGET",
            "BINDING_DERANGED_NUMERIC_PLACEBO",
        },
        "preregistration.arms",
    )
    if arms["RAW_EQUAL_BUDGET"] != RAW_REPLAY_DESCRIPTION:
        raise ExecutionRefusal("preregistration RAW arm overclaims transcript/token/state parity")
    parity = _exact_keys(
        data["parity_and_leakage"],
        {
            "same_served_model_id_and_chat_endpoint",
            "equal_client_dispatched_and_logical_requests",
            "equal_generation_limits_input_token_parity_not_claimed",
            "equal_candidate_evidence_universe",
            "all_active_payloads_within_byte_ceiling",
            "active_state_byte_ceiling",
            "full_raw_numeric_payload_bytes_equal",
            "full_deranged_numeric_payload_byte_count_equal",
            "arm_labels_hidden_from_model",
            "fresh_process_recovery_observed",
            "distinct_arm_mount_ids",
            "evaluation_read_only_wrt_routing_observed",
            "cache_hits_required",
            "gold_open_only_after_response_seal",
            "compiler_input_audit",
            "canary",
        },
        "preregistration.parity_and_leakage",
    )
    required_true = {
        "same_served_model_id_and_chat_endpoint",
        "equal_client_dispatched_and_logical_requests",
        "equal_generation_limits_input_token_parity_not_claimed",
        "equal_candidate_evidence_universe",
        "all_active_payloads_within_byte_ceiling",
        "full_raw_numeric_payload_bytes_equal",
        "full_deranged_numeric_payload_byte_count_equal",
        "arm_labels_hidden_from_model",
        "fresh_process_recovery_observed",
        "distinct_arm_mount_ids",
        "evaluation_read_only_wrt_routing_observed",
        "gold_open_only_after_response_seal",
    }
    if (
        any(parity[key] is not True for key in required_true)
        or parity["active_state_byte_ceiling"] != 16_384
        or parity["cache_hits_required"] != 0
    ):
        raise ExecutionRefusal("preregistration does not freeze observable DNRD parity boundaries")
    claim_boundary = {
        "canonical_role": data["canonical_role"],
        "predecessor_bindings": data["predecessor_bindings"],
        "forbidden_rescues": data["forbidden_rescues"],
        "scientific_question": data["scientific_question"],
        "hypotheses": data["hypotheses"],
        "testbed_claims": {
            key: testbed[key]
            for key in ("relationship_to_prior_p1", "analysis_unit", "freshness")
        },
        "learning_boundary": data["learning_boundary"],
        "arms": dict(arms),
        "interventions": data["interventions"],
        "parity_claims": {
            key: parity[key] for key in ("compiler_input_audit", "canary")
        },
        "diagnostic_readouts": data["diagnostic_readouts"],
        "void_conditions": data["void_conditions"],
        "single_attempt_policy": data["single_attempt_policy"],
        "required_before_measurement": data["required_before_measurement"],
        "result_promotion": data["result_promotion"],
        "measurement_gate": data["measurement_gate"],
    }
    if claim_boundary != PREREG_CLAIM_BOUNDARY:
        raise ExecutionRefusal(
            "preregistration scientific claim boundary differs from the frozen mechanics-only contract"
        )
    return dict(data)


def _is_git_sha1(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _git_object_sha1(kind: str, raw: bytes) -> str:
    return hashlib.sha1(
        kind.encode("ascii") + b" " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()


def _commit_headers(raw: bytes, label: str) -> tuple[str, list[str], int]:
    """Parse only the Git commit headers needed for chronology verification."""
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ExecutionRefusal(f"{label} commit object is not UTF-8") from error
    header, _, _ = text.partition("\n\n")
    tree: str | None = None
    parents: list[str] = []
    committer_time: int | None = None
    for line in header.splitlines():
        if line.startswith("tree "):
            candidate = line.removeprefix("tree ")
            if tree is not None or not _is_git_sha1(candidate):
                raise ExecutionRefusal(f"{label} commit has malformed tree header")
            tree = candidate
        elif line.startswith("parent "):
            candidate = line.removeprefix("parent ")
            if not _is_git_sha1(candidate):
                raise ExecutionRefusal(f"{label} commit has malformed parent header")
            parents.append(candidate)
        elif line.startswith("committer "):
            fields = line.rsplit(" ", 2)
            if len(fields) != 3 or not fields[1].isdigit():
                raise ExecutionRefusal(f"{label} commit has malformed committer timestamp")
            committer_time = int(fields[1])
    if tree is None or committer_time is None:
        raise ExecutionRefusal(f"{label} commit lacks immutable tree/time headers")
    return tree, parents, committer_time


def _tree_entries(raw: bytes, label: str) -> list[tuple[bytes, bytes, str]]:
    """Parse a SHA-1 Git tree object without invoking a shell parser."""
    entries: list[tuple[bytes, bytes, str]] = []
    cursor = 0
    while cursor < len(raw):
        space = raw.find(b" ", cursor)
        nul = raw.find(b"\0", space + 1)
        if space <= cursor or nul < 0 or nul + 21 > len(raw):
            raise ExecutionRefusal(f"{label} has malformed binary tree entry")
        mode, name = raw[cursor:space], raw[space + 1 : nul]
        if not mode or not name or any(byte < 0x30 or byte > 0x37 for byte in mode):
            raise ExecutionRefusal(f"{label} has malformed binary tree mode/name")
        oid = raw[nul + 1 : nul + 21].hex()
        entries.append((mode, name, oid))
        cursor = nul + 21
    if not entries:
        raise ExecutionRefusal(f"{label} is an unexpectedly empty tree object")
    return entries


def _git_tree_path_blob(
    config: ExecutionConfig,
    dependencies: ExecutionDependencies,
    *,
    root_tree_oid: str,
    relative_path: str,
    tree_objects: dict[str, bytes],
) -> str:
    """Return the blob OID at one path while retaining every traversed tree."""
    current = root_tree_oid
    parts = Path(relative_path).parts
    if not parts:
        raise ExecutionRefusal("Git chronology path is empty")
    for index, part in enumerate(parts):
        raw = tree_objects.get(current)
        if raw is None:
            raw = _git_bytes(config, dependencies, "cat-file", "tree", current)
            if _git_object_sha1("tree", raw) != current:
                raise ExecutionRefusal("Git tree object bytes do not match their named object")
            tree_objects[current] = raw
        matches = [entry for entry in _tree_entries(raw, f"tree {current}") if entry[1] == part.encode("utf-8")]
        if len(matches) != 1:
            raise ExecutionRefusal("Git chronology tree does not contain the required frozen path")
        mode, _, target = matches[0]
        if index == len(parts) - 1:
            if mode in {b"40000", b"040000"}:
                raise ExecutionRefusal("Git chronology path resolves to a tree rather than a blob")
            return target
        if mode not in {b"40000", b"040000"}:
            raise ExecutionRefusal("Git chronology path crosses a non-tree entry")
        current = target
    raise AssertionError("unreachable Git tree traversal")


def _git_chronology_evidence(
    config: ExecutionConfig,
    dependencies: ExecutionDependencies,
    *,
    source_time: int,
    preregistration_time: int,
    changed_paths: Sequence[str],
) -> dict[str, Any]:
    """Build raw, self-contained proof of A→B topology and bound blobs.

    Git object bytes are copied into the occurrence bundle so the authoritative
    verifier does not need a mutable checkout to re-establish the chronology.
    Only SHA-1 repositories are accepted because the frozen evidence schema
    encodes Git's 20-byte tree object IDs explicitly.
    """
    if not _is_git_sha1(config.source_a_commit) or not _is_git_sha1(config.prereg_b_commit):
        raise ExecutionRefusal("DNRD git chronology evidence currently requires full SHA-1 commit IDs")
    source_raw = _git_bytes(config, dependencies, "cat-file", "commit", config.source_a_commit)
    prereg_raw = _git_bytes(config, dependencies, "cat-file", "commit", config.prereg_b_commit)
    if (
        _git_object_sha1("commit", source_raw) != config.source_a_commit
        or _git_object_sha1("commit", prereg_raw) != config.prereg_b_commit
    ):
        raise ExecutionRefusal("Git commit object bytes do not match frozen commit IDs")
    source_tree, source_parents, source_commit_time = _commit_headers(source_raw, "source A")
    prereg_tree, prereg_parents, prereg_commit_time = _commit_headers(prereg_raw, "preregistration B")
    if (
        source_tree != config.source_a_tree
        or source_commit_time != source_time
        or prereg_parents != [config.source_a_commit]
        or prereg_commit_time != preregistration_time
        or preregistration_time < source_time
        or preregistration_time > config.ratification_unix
    ):
        raise ExecutionRefusal("raw Git objects disagree with frozen A→B chronology")
    # A root commit is allowed to have its own parent; only B's direct-parent
    # relationship is part of the frozen source/preregistration occurrence.
    del source_parents
    tree_objects: dict[str, bytes] = {}
    source_blob_oid = _git_tree_path_blob(
        config,
        dependencies,
        root_tree_oid=source_tree,
        relative_path=config.source_manifest_path,
        tree_objects=tree_objects,
    )
    prereg_blob_oid = _git_tree_path_blob(
        config,
        dependencies,
        root_tree_oid=prereg_tree,
        relative_path=config.prereg_path,
        tree_objects=tree_objects,
    )
    frozen_source = _load_source_manifest(config)
    source_file_blobs: list[dict[str, str]] = []
    for index, row in enumerate(frozen_source["files"]):
        relative = str(row["path"])
        blob_oid = _git_tree_path_blob(
            config,
            dependencies,
            root_tree_oid=source_tree,
            relative_path=relative,
            tree_objects=tree_objects,
        )
        body = _plain_relative_file(
            config.repo_root, relative, f"frozen source Git member {index}"
        ).read_bytes()
        if (
            _git_object_sha1("blob", body) != blob_oid
            or _sha_bytes(body) != row["sha256"]
        ):
            raise ExecutionRefusal(
                f"frozen source bytes are not the Source-A Git blob: {relative}"
            )
        source_file_blobs.append(
            {"path": relative, "blob_oid": blob_oid, "sha256": str(row["sha256"])}
        )
    source_blob = _git_bytes(
        config, dependencies, "cat-file", "blob", source_blob_oid
    )
    prereg_blob = _git_bytes(
        config, dependencies, "cat-file", "blob", prereg_blob_oid
    )
    if (
        _git_object_sha1("blob", source_blob) != source_blob_oid
        or _git_object_sha1("blob", prereg_blob) != prereg_blob_oid
        or source_blob
        != _plain_relative_file(
            config.repo_root, config.source_manifest_path, "source manifest"
        ).read_bytes()
        or prereg_blob
        != _plain_relative_file(
            config.repo_root, config.prereg_path, "preregistration"
        ).read_bytes()
        or _sha_bytes(source_blob) != config.source_manifest_sha256
        or _sha_bytes(prereg_blob) != config.prereg_sha256
    ):
        raise ExecutionRefusal("Git tree/blob evidence differs from frozen bundle inputs")
    try:
        source_text = source_raw.decode("utf-8", errors="strict")
        prereg_text = prereg_raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ExecutionRefusal("Git commit evidence cannot be encoded as required UTF-8") from error
    unsigned = {
        "schema_version": GIT_CHRONOLOGY_EVIDENCE_SCHEMA,
        "source": {
            "commit_oid": config.source_a_commit,
            "commit_raw_utf8": source_text,
            "tree_oid": source_tree,
            "commit_time_unix": source_time,
            "source_manifest_path": config.source_manifest_path,
            "source_manifest_blob_sha256": _sha_bytes(source_blob),
            "file_blobs": source_file_blobs,
        },
        "preregistration": {
            "commit_oid": config.prereg_b_commit,
            "commit_raw_utf8": prereg_text,
            "parent_oid": config.source_a_commit,
            "tree_oid": prereg_tree,
            "commit_time_unix": preregistration_time,
            "path": config.prereg_path,
            "blob_sha256": _sha_bytes(prereg_blob),
        },
        "a_to_b_changed_paths": list(changed_paths),
        "tree_objects": [
            {"oid": oid, "raw_base64": base64.b64encode(raw).decode("ascii")}
            for oid, raw in sorted(tree_objects.items())
        ],
    }
    return {**unsigned, "receipt_sha256": commitment(unsigned)}


def _preflight_git(config: ExecutionConfig, dependencies: ExecutionDependencies) -> tuple[int, dict[str, Any]]:
    root = config.repo_root
    if not root.is_dir() or _git(config, dependencies, "status", "--porcelain").strip():
        raise ExecutionRefusal("checkout must be clean before DNRD execution")
    if _git(config, dependencies, "rev-parse", "HEAD").strip() != config.prereg_b_commit:
        raise ExecutionRefusal("checkout HEAD is not exact preregistration B")
    if _git(config, dependencies, "rev-parse", f"{config.prereg_b_commit}^").strip() != config.source_a_commit:
        raise ExecutionRefusal("B is not a direct child of source A")
    if _git(config, dependencies, "rev-parse", f"{config.source_a_commit}^{{tree}}").strip() != config.source_a_tree:
        raise ExecutionRefusal("source A tree identity drifted")
    changed = [line for line in _git(config, dependencies, "diff", "--name-only", config.source_a_commit, config.prereg_b_commit).splitlines() if line]
    if changed != [config.prereg_path]:
        raise ExecutionRefusal("B must change exactly the frozen preregistration path")
    source_manifest = _plain_relative_file(root, config.source_manifest_path, "source manifest")
    prereg = _plain_relative_file(root, config.prereg_path, "preregistration")
    if _hash_file(source_manifest) != config.source_manifest_sha256 or _hash_file(prereg) != config.prereg_sha256:
        raise ExecutionRefusal("source manifest or preregistration content hash drifted")
    source_time = int(_git(config, dependencies, "show", "-s", "--format=%ct", config.source_a_commit).strip())
    if source_time != config.source_freeze_unix or source_time >= config.ratification_unix:
        raise ExecutionRefusal("source freeze timestamp must equal A and precede ratification")
    preregistration_time = int(
        _git(config, dependencies, "show", "-s", "--format=%ct", config.prereg_b_commit).strip()
    )
    if preregistration_time < source_time or preregistration_time > config.ratification_unix:
        raise ExecutionRefusal("B commit time must fall after/equal A and no later than external ratification")
    return source_time, _git_chronology_evidence(
        config,
        dependencies,
        source_time=source_time,
        preregistration_time=preregistration_time,
        changed_paths=changed,
    )


def _runtime_regular_files(root: Path, relative_root: str, label: str) -> set[str]:
    """Return an exact regular-file tree while refusing links and special files."""
    _relative_path(relative_root, f"{label} root")
    package_root = root / relative_root
    _plain_directory(package_root, f"{label} root")
    result: set[str] = set()

    def visit(directory: Path) -> None:
        for child in directory.iterdir():
            info = child.lstat()
            relative = child.relative_to(root).as_posix()
            if stat.S_ISLNK(info.st_mode):
                raise ExecutionRefusal(f"{label} contains a symlink: {relative}")
            if stat.S_ISDIR(info.st_mode):
                visit(child)
            elif stat.S_ISREG(info.st_mode):
                result.add(relative)
            else:
                raise ExecutionRefusal(f"{label} contains a non-regular file: {relative}")

    visit(package_root)
    return result


def _runtime_manifest_rows(
    rows: object, *, label: str, root: Path, required_prefix: str | None = None
) -> dict[str, str]:
    if type(rows) is not list or not rows:
        raise ExecutionRefusal(f"{label} must be a nonempty file list")
    values: dict[str, str] = {}
    for index, row in enumerate(rows):
        item = _exact_keys(row, {"path", "sha256"}, f"{label}[{index}]")
        path = _relative_path(item["path"], f"{label}[{index}].path")
        if required_prefix is not None and not path.startswith(f"{required_prefix}/"):
            raise ExecutionRefusal(f"{label} escapes its declared package root")
        _hex(item["sha256"], f"{label}[{index}].sha256")
        if path in values:
            raise ExecutionRefusal(f"{label} repeats a file")
        if _hash_file(_plain_relative_file(root, path, f"{label} file")) != item["sha256"]:
            raise ExecutionRefusal(f"{label} file hash drifted: {path}")
        values[path] = item["sha256"]
    if list(values) != sorted(values):
        raise ExecutionRefusal(f"{label} must be canonically sorted")
    return values


def _runtime_package_dependencies(package_json: Path, label: str) -> tuple[str, str, set[str]]:
    try:
        parsed = _json_object_unformatted(package_json.read_text(encoding="utf-8"), label)
    except UnicodeDecodeError as error:
        raise ExecutionRefusal(f"{label} is not UTF-8") from error
    name, version = parsed.get("name"), parsed.get("version")
    dependencies = parsed.get("dependencies", {})
    if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
        raise ExecutionRefusal(f"{label} lacks a package name/version")
    if type(dependencies) is not dict or any(not isinstance(key, str) or not key for key in dependencies):
        raise ExecutionRefusal(f"{label}.dependencies is malformed")
    return name, version, set(dependencies)


def _runtime_tree_manifest(config: ExecutionConfig) -> dict[str, Any]:
    if (
        config.bridge_runtime_root is None
        or config.bridge_runtime_tree_manifest_path is None
        or config.bridge_runtime_tree_manifest_sha256 is None
    ):
        raise ExecutionRefusal("bridge runtime-root and transitive-tree pins are required")
    if not config.bridge_runtime_root.is_absolute() or not config.bridge_implementation_path.is_absolute():
        raise ExecutionRefusal("bridge runtime root and implementation path must be absolute")
    _plain_directory(config.bridge_runtime_root, "bridge runtime root")
    _hex(config.bridge_runtime_tree_manifest_sha256, "bridge runtime tree manifest")
    raw = config.bridge_runtime_tree_manifest_path.read_bytes()
    if _sha_bytes(raw) != config.bridge_runtime_tree_manifest_sha256:
        raise ExecutionRefusal("bridge runtime tree manifest hash drifted")
    manifest = _strict_json_bytes(raw, "bridge runtime tree manifest")
    data = _exact_keys(
        manifest,
        {"schema_version", "root_path", "entrypoint", "files", "external_packages", "build_provenance"},
        "bridge runtime tree manifest",
    )
    try:
        entrypoint_relative = str(
            config.bridge_implementation_path.resolve().relative_to(
                config.bridge_runtime_root.resolve()
            )
        )
    except ValueError as error:
        raise ExecutionRefusal("bridge implementation must reside under its pinned runtime root") from error
    if (
        data["schema_version"] != RUNTIME_TREE_MANIFEST_SCHEMA
        or data["root_path"] != str(config.bridge_runtime_root)
        or data["entrypoint"] != entrypoint_relative
    ):
        raise ExecutionRefusal("bridge runtime tree identity does not bind the implementation")
    compiled = _runtime_manifest_rows(
        data["files"], label="bridge runtime files", root=config.bridge_runtime_root
    )
    known = set(compiled)
    entrypoint = entrypoint_relative
    if entrypoint not in known:
        raise ExecutionRefusal("bridge implementation is absent from its transitive runtime tree")
    packages = data["external_packages"]
    if type(packages) is not list or len(packages) > RUNTIME_CLOSURE_MAX_FILES:
        raise ExecutionRefusal("bridge runtime external package pinset is malformed")
    package_names: set[str] = set()
    package_order: list[str] = []
    package_files: set[str] = set()
    package_file_hashes: dict[str, str] = {}
    package_roots: dict[str, str] = {}
    package_dependencies: dict[str, set[str]] = {}
    package_versions: dict[str, str] = {}
    total_files = len(compiled)
    total_bytes = sum(_plain_relative_file(config.bridge_runtime_root, path, "bridge runtime compiled file").stat().st_size for path in compiled)
    for index, row in enumerate(packages):
        item = _exact_keys(
            row,
            {
                "name", "version", "package_root", "package_json_path", "package_json_sha256",
                "resolved_entrypoint_path", "resolved_entrypoint_sha256", "files",
            },
            f"bridge runtime external_packages[{index}]",
        )
        if not isinstance(item["name"], str) or not item["name"] or not isinstance(item["version"], str) or not item["version"]:
            raise ExecutionRefusal("bridge external package name is malformed")
        root_relative = _relative_path(item["package_root"], "bridge external package root")
        relative = _relative_path(item["package_json_path"], "bridge external package path")
        if relative != f"{root_relative}/package.json":
            raise ExecutionRefusal("bridge external package JSON must reside at its declared root")
        _hex(item["package_json_sha256"], "bridge external package package.json SHA-256")
        entrypoint_path = _relative_path(item["resolved_entrypoint_path"], "bridge external package entrypoint")
        if not entrypoint_path.startswith(f"{root_relative}/"):
            raise ExecutionRefusal("bridge external package entrypoint escapes its declared root")
        _hex(item["resolved_entrypoint_sha256"], "bridge external package entrypoint SHA-256")
        package_json = _plain_relative_file(config.bridge_runtime_root, relative, "bridge external package")
        discovered_name, discovered_version, dependencies = _runtime_package_dependencies(package_json, "bridge external package package.json")
        if (
            item["name"] in package_names
            or item["name"] != discovered_name
            or item["version"] != discovered_version
            or root_relative != f"node_modules/{discovered_name}"
            or _hash_file(package_json) != item["package_json_sha256"]
        ):
            raise ExecutionRefusal("bridge external package identity drifted")
        rows = _runtime_manifest_rows(
            item["files"],
            label=f"bridge external package {item['name']} files",
            root=config.bridge_runtime_root,
            required_prefix=root_relative,
        )
        actual = _runtime_regular_files(config.bridge_runtime_root, root_relative, f"bridge external package {item['name']}")
        if set(rows) != actual or relative not in rows or rows[relative] != item["package_json_sha256"]:
            raise ExecutionRefusal("bridge external package file closure is not exact")
        if entrypoint_path not in rows or rows[entrypoint_path] != item["resolved_entrypoint_sha256"]:
            raise ExecutionRefusal("bridge external package entrypoint is absent or drifted")
        if package_files & set(rows):
            raise ExecutionRefusal("bridge external package closures overlap")
        package_files.update(rows)
        package_file_hashes.update(rows)
        total_files += len(rows)
        total_bytes += sum(_plain_relative_file(config.bridge_runtime_root, path, "bridge external package file").stat().st_size for path in rows)
        package_names.add(item["name"])
        package_order.append(item["name"])
        package_roots[item["name"]] = root_relative
        package_dependencies[item["name"]] = dependencies
        package_versions[item["name"]] = discovered_version
    if package_order != sorted(package_order):
        raise ExecutionRefusal("bridge runtime external packages must be canonically sorted")
    if total_files > RUNTIME_CLOSURE_MAX_FILES or total_bytes > RUNTIME_CLOSURE_MAX_TOTAL_BYTES:
        raise ExecutionRefusal("bridge runtime closure exceeds conservative file/byte limits")
    for name, dependencies in package_dependencies.items():
        if not dependencies.issubset(package_names):
            raise ExecutionRefusal(f"bridge external package dependencies are not recursively pinned: {name}")
    source_manifest = _load_source_manifest(config)
    source_rows = {str(row["path"]): str(row["sha256"]) for row in source_manifest["files"]}
    provenance = _exact_keys(
        data["build_provenance"],
        {
            "source_a_commit", "source_a_tree", "source_manifest_path",
            "source_manifest_sha256", "node_executable_sha256", "node_version",
            "dependency_materialization_command", "compilation_command",
            "claim_boundary", "source_inputs", "package_roots", "typescript",
        },
        "bridge runtime build provenance",
    )
    if (
        provenance["source_a_commit"] != config.source_a_commit
        or provenance["source_a_tree"] != config.source_a_tree
        or provenance["source_manifest_path"] != config.source_manifest_path
        or provenance["source_manifest_sha256"] != config.source_manifest_sha256
        or provenance["node_executable_sha256"] != config.node_executable_sha256
        or provenance["node_version"] != config.node_version
        or provenance["dependency_materialization_command"]
        != ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"]
        or provenance["compilation_command"]
        != [
            "{PINNED_NODE_EXECUTABLE}",
            "node_modules/typescript/lib/tsc.js",
            "-p",
            "tsconfig.dnrd.json",
        ]
        or provenance["claim_boundary"]
        != "SOURCE_SELECTED_PACKAGE_AND_COMPILER_BYTES_PINNED_BUILD_NOT_INDEPENDENTLY_REEXECUTED"
        or provenance["package_roots"] != ["@types/node", "effect", "typescript"]
    ):
        raise ExecutionRefusal("bridge runtime build provenance does not bind source-A or the fixed build recipe")
    build_roots = set(provenance["package_roots"])
    selected_package_closure = set(build_roots)
    pending_packages = list(build_roots)
    while pending_packages:
        package_name = pending_packages.pop()
        dependencies = package_dependencies.get(package_name)
        if dependencies is None:
            raise ExecutionRefusal("bridge build package root is absent from the retained package closure")
        for dependency in dependencies:
            if dependency not in selected_package_closure:
                selected_package_closure.add(dependency)
                pending_packages.append(dependency)
    if package_names != selected_package_closure:
        raise ExecutionRefusal("bridge runtime packages do not equal the exact selected build/runtime dependency closure")
    inputs = _runtime_manifest_rows(
        provenance["source_inputs"], label="bridge runtime build source inputs", root=config.repo_root
    )
    if inputs != source_rows:
        raise ExecutionRefusal("bridge runtime build inputs do not exactly reproduce source-freeze manifest")
    required_inputs = {
        "src/hswm/effect-runtime/package.json", "src/hswm/effect-runtime/package-lock.json",
        "src/hswm/effect-runtime/tsconfig.json", "src/hswm/effect-runtime/tsconfig.build.json",
        "src/hswm/effect-runtime/tsconfig.dnrd.json", "src/hswm/effect-runtime/.npmrc",
    }
    if not required_inputs.issubset(inputs):
        raise ExecutionRefusal("bridge runtime build provenance lacks a required package/lock/config input")
    package_source = _json_object_unformatted(
        _plain_relative_file(
            config.repo_root,
            "src/hswm/effect-runtime/package.json",
            "frozen Effect runtime package.json",
        ).read_text(encoding="utf-8"),
        "frozen Effect runtime package.json",
    )
    dependencies = package_source.get("dependencies")
    dev_dependencies = package_source.get("devDependencies")
    if type(dependencies) is not dict or type(dev_dependencies) is not dict:
        raise ExecutionRefusal("frozen Effect runtime package dependency declarations are malformed")
    expected_root_versions = {
        "effect": dependencies.get("effect"),
        "typescript": dev_dependencies.get("typescript"),
        "@types/node": dev_dependencies.get("@types/node"),
    }
    if any(
        not isinstance(version, str)
        or package_versions.get(name) != version
        for name, version in expected_root_versions.items()
    ):
        raise ExecutionRefusal("selected build package roots do not match exact source package versions")
    package_lock = _json_object_unformatted(
        _plain_relative_file(
            config.repo_root,
            "src/hswm/effect-runtime/package-lock.json",
            "frozen Effect runtime package lock",
        ).read_text(encoding="utf-8"),
        "frozen Effect runtime package lock",
    )
    lock_packages = package_lock.get("packages")
    if type(lock_packages) is not dict:
        raise ExecutionRefusal("frozen Effect runtime package lock lacks package rows")
    for name, version in package_versions.items():
        locked = lock_packages.get(f"node_modules/{name}")
        if type(locked) is not dict or locked.get("version") != version:
            raise ExecutionRefusal("selected build/runtime package version differs from the frozen package lock")
    compiler = _exact_keys(
        provenance["typescript"],
        {"package_json_path", "package_json_sha256", "bin_tsc_path", "bin_tsc_sha256", "lib_tsc_path", "lib_tsc_sha256", "lib_typescript_path", "lib_typescript_sha256"},
        "bridge runtime TypeScript compiler pin",
    )
    for key in ("package_json_path", "bin_tsc_path", "lib_tsc_path", "lib_typescript_path"):
        path = _relative_path(compiler[key], f"bridge runtime TypeScript compiler.{key}")
        if not path.startswith("node_modules/typescript/"):
            raise ExecutionRefusal("bridge runtime TypeScript compiler path escapes the compiler package")
    for key in ("package_json_sha256", "bin_tsc_sha256", "lib_tsc_sha256", "lib_typescript_sha256"):
        _hex(compiler[key], f"bridge runtime TypeScript compiler.{key}")
    for path_key, sha_key in (("package_json_path", "package_json_sha256"), ("bin_tsc_path", "bin_tsc_sha256"), ("lib_tsc_path", "lib_tsc_sha256"), ("lib_typescript_path", "lib_typescript_sha256")):
        compiler_path = compiler[path_key]
        if (
            not compiler_path.startswith(f"{package_roots['typescript']}/")
            or package_file_hashes.get(compiler_path) != compiler[sha_key]
            or _hash_file(
                _plain_relative_file(
                    config.bridge_runtime_root,
                    compiler_path,
                    "bridge runtime TypeScript compiler",
                )
            )
            != compiler[sha_key]
        ):
            raise ExecutionRefusal("bridge runtime TypeScript compiler bytes drifted")
    compiler_name, _, _ = _runtime_package_dependencies(
        _plain_relative_file(config.bridge_runtime_root, compiler["package_json_path"], "bridge runtime TypeScript package"),
        "bridge runtime TypeScript package.json",
    )
    if compiler_name != "typescript":
        raise ExecutionRefusal("bridge runtime compiler package is not TypeScript")
    # A conservative static closure check catches missing sibling .js files and
    # unpinned bare package imports without attempting to execute JavaScript.
    import re

    import_pattern = re.compile(r"(?:\bfrom\s*|\bimport\s*\()\s*[\"']([^\"']+)[\"']")
    for relative in sorted(known):
        if not relative.endswith(".js"):
            continue
        source = (config.bridge_runtime_root / relative).read_text(encoding="utf-8")
        for target in import_pattern.findall(source):
            if target.startswith("."):
                normalized = (Path(relative).parent / target).as_posix()
                if not normalized.endswith(".js"):
                    normalized += ".js"
                if normalized not in known:
                    raise ExecutionRefusal("bridge runtime tree omits a static relative JavaScript import")
            elif not target.startswith(("node:", "#")) and target not in package_names:
                raise ExecutionRefusal("bridge runtime tree omits a static external package identity")
    return dict(data)


def _execution_closure_paths(config: ExecutionConfig) -> dict[str, Path]:
    """Derive the copied paths that production subprocesses actually execute."""
    assert config.bridge_runtime_root is not None
    try:
        bridge_relative = config.bridge_implementation_path.resolve().relative_to(
            config.bridge_runtime_root.resolve()
        )
        scorer_relative = config.scorer_implementation_path.resolve().relative_to(
            config.repo_root.resolve()
        )
    except ValueError as error:
        raise ExecutionRefusal(
            "bridge/scorer implementations must reside under their frozen source roots"
        ) from error
    if bridge_relative.is_absolute() or scorer_relative.is_absolute():
        raise ExecutionRefusal("derived execution-closure path is not relative")
    return {
        "bridge_root": config.output_root / "bridge_runtime_closure",
        "bridge_implementation": config.output_root
        / "bridge_runtime_closure"
        / bridge_relative,
        "scorer_root": config.output_root / "source_closure",
        "scorer_implementation": config.output_root / "source_closure" / scorer_relative,
    }


def _runtime_receipt(
    config: ExecutionConfig, *, execution_adapter_boundary: str
) -> dict[str, Any]:
    assert config.bridge_runtime_tree_manifest_sha256 is not None
    assert config.bridge_runtime_root is not None
    assert config.bridge_state_root is not None
    assert config.node_executable_path is not None
    assert config.node_executable_sha256 is not None
    assert config.node_version is not None
    assert config.python_executable_path is not None
    assert config.python_executable_sha256 is not None
    assert config.python_version is not None
    assert config.unicode_data_version is not None
    paths = _execution_closure_paths(config)
    bridge_root_relative = paths["bridge_root"].relative_to(config.output_root).as_posix()
    bridge_implementation_relative = paths["bridge_implementation"].relative_to(
        config.output_root
    ).as_posix()
    scorer_root_relative = paths["scorer_root"].relative_to(config.output_root).as_posix()
    scorer_implementation_relative = paths["scorer_implementation"].relative_to(
        config.output_root
    ).as_posix()
    unsigned = {
        "schema_version": RUNTIME_RECEIPT_SCHEMA,
        "execution_adapter_boundary": execution_adapter_boundary,
        "bridge_implementation_sha256": config.bridge_implementation_sha256,
        "bridge_runtime_root": str(config.bridge_runtime_root),
        "execution_path_base": "CONFIGURED_OUTPUT_ROOT",
        "bridge_execution_root": bridge_root_relative,
        "bridge_implementation_execution_path": bridge_implementation_relative,
        "bridge_state_root": str(config.bridge_state_root),
        "bridge_runtime_tree_manifest_sha256": config.bridge_runtime_tree_manifest_sha256,
        "bridge_command": [
            str(config.node_executable_path),
            "{OUTPUT_ROOT}/" + bridge_implementation_relative,
        ],
        "bridge_config": dict(config.bridge_config),
        "scorer_implementation_sha256": config.scorer_implementation_sha256,
        "scorer_implementation_source_path": str(config.scorer_implementation_path),
        "scorer_execution_root": scorer_root_relative,
        "scorer_implementation_execution_path": scorer_implementation_relative,
        "scorer_command": list(config.scorer_command),
        "scorer_import_root": scorer_root_relative,
        "node_executable_path": str(config.node_executable_path),
        "node_executable_sha256": config.node_executable_sha256,
        "node_version": config.node_version,
        "python_executable_path": str(config.python_executable_path),
        "python_executable_sha256": config.python_executable_sha256,
        "python_version": config.python_version,
        "unicode_data_version": config.unicode_data_version,
        "subprocess_environment": _pinned_subprocess_environment(),
        "verifier_command": list(config.verifier_command),
        "verifier_helper_sha256": config.verifier_helper_sha256,
        "verifier_package_lock_sha256": config.verifier_package_lock_sha256,
        "verifier_runtime_bundle_sha256": config.verifier_runtime_bundle_sha256,
        "verifier_runtime_bundle_evidence_path": VERIFIER_RUNTIME_BUNDLE_EVIDENCE_PATH,
        "verifier_runtime_bundle_dependency_policy": (
            VERIFIER_RUNTIME_BUNDLE_DEPENDENCY_POLICY
        ),
        "verifier_argument_contract": list(VERIFIER_ARGUMENT_CONTRACT),
        "verifier_working_directory": str(config.verifier_helper_path.parent),
        "verifier_subprocess_environment": _pinned_subprocess_environment(),
        "verifier_timeout_seconds": VERIFIER_TIMEOUT_SECONDS,
        "execution_closure_file_mode": "0400",
        "execution_closure_directory_mode": "0500",
        "execution_closure_isolation_claim": EXECUTION_CLOSURE_ISOLATION_CLAIM,
    }
    return {**unsigned, "receipt_sha256": commitment(unsigned)}


def _assert_distinct_roots(config: ExecutionConfig) -> None:
    assert config.bridge_runtime_root is not None
    assert config.bridge_state_root is not None
    assert config.attempt_registry_root is not None
    roots = {
        "repository": config.repo_root.resolve(),
        "bridge_runtime": config.bridge_runtime_root.resolve(),
        "bridge_state": config.bridge_state_root.resolve(),
        "attempt_registry": config.attempt_registry_root.resolve(),
        "output": config.output_root.resolve(),
    }
    # The code runtime may sit under the repository; every mutable occurrence
    # root must otherwise be separate rather than a child/parent alias.
    mutable = ("bridge_state", "attempt_registry", "output")
    for left in mutable:
        for right in roots:
            if left == right:
                continue
            left_path, right_path = roots[left], roots[right]
            if left_path == right_path or left_path in right_path.parents or right_path in left_path.parents:
                raise ExecutionRefusal(f"mutable DNRD root {left} overlaps {right}")


def _verify_static_pins(
    config: ExecutionConfig, *, require_official_runtime_identity: bool = False
) -> dict[str, Any]:
    for label, path in (
        ("repository root", config.repo_root),
        ("output root", config.output_root),
        ("bridge implementation", config.bridge_implementation_path),
        ("scorer implementation", config.scorer_implementation_path),
        ("verifier helper", config.verifier_helper_path),
        ("verifier package lock", config.verifier_package_lock_path),
        ("verifier runtime bundle", config.verifier_runtime_bundle_path),
    ):
        if not path.is_absolute():
            raise ExecutionRefusal(f"{label} must be an absolute path")
    for label, path, digest in (
        ("bridge implementation", config.bridge_implementation_path, config.bridge_implementation_sha256),
        ("scorer implementation", config.scorer_implementation_path, config.scorer_implementation_sha256),
        ("verifier helper", config.verifier_helper_path, config.verifier_helper_sha256),
        ("verifier package lock", config.verifier_package_lock_path, config.verifier_package_lock_sha256),
        ("verifier runtime bundle", config.verifier_runtime_bundle_path, config.verifier_runtime_bundle_sha256),
    ):
        _hex(digest, label)
        if _hash_file(path) != digest:
            raise ExecutionRefusal(f"{label} hash drifted")
    _validated_verifier_runtime_bundle_bytes(
        config.verifier_runtime_bundle_path,
        require_official_identity=require_official_runtime_identity,
    )
    required = (
        config.attempt_registry_root,
        config.ratification_receipt_path,
        config.ratification_receipt_sha256,
        config.source_ci_receipt_path,
        config.source_ci_receipt_sha256,
        config.tokenizer_preflight_prompt,
        config.bridge_state_root,
        config.node_executable_path,
        config.node_executable_sha256,
        config.node_version,
        config.python_executable_path,
        config.python_executable_sha256,
        config.python_version,
        config.unicode_data_version,
        config.scorer_import_root,
    )
    if any(value is None for value in required):
        raise ExecutionRefusal("production DNRD runtime pins are incomplete")
    assert config.attempt_registry_root is not None
    assert config.ratification_receipt_path is not None
    assert config.source_ci_receipt_path is not None
    assert config.tokenizer_preflight_prompt is not None
    assert config.bridge_state_root is not None
    assert config.node_executable_path is not None
    assert config.node_executable_sha256 is not None
    assert config.node_version is not None
    assert config.python_executable_path is not None
    assert config.python_executable_sha256 is not None
    assert config.python_version is not None
    assert config.unicode_data_version is not None
    assert config.scorer_import_root is not None
    for label, path in (
        ("singleton attempt registry", config.attempt_registry_root),
        ("ratification receipt", config.ratification_receipt_path),
        ("source CI receipt", config.source_ci_receipt_path),
        ("bridge mutable state root", config.bridge_state_root),
        ("node executable", config.node_executable_path),
        ("python executable", config.python_executable_path),
        ("scorer import root", config.scorer_import_root),
    ):
        if not path.is_absolute():
            raise ExecutionRefusal(f"{label} must be an absolute path")
    _plain_directory(config.attempt_registry_root, "singleton attempt registry", mode=0o700)
    _plain_directory(config.bridge_state_root, "bridge mutable state root", mode=0o700)
    if any(config.bridge_state_root.iterdir()):
        raise ExecutionRefusal("bridge mutable state root must be empty before a singleton occurrence")
    if not config.tokenizer_preflight_prompt:
        raise ExecutionRefusal("tokenizer preflight prompt must be frozen nonempty text")
    _assert_distinct_roots(config)
    if _sha_bytes(config.ratification_text.encode("utf-8")) != config.ratification_text_sha256:
        raise ExecutionRefusal("ratification text hash drifted")
    expected_statement = RATIFICATION_TEMPLATE.format(preregistration_sha256=config.prereg_sha256)
    if config.ratification_text != expected_statement:
        raise ExecutionRefusal("ratification text is not the exact preregistration-bound statement")
    _hex(config.node_executable_sha256, "node executable")
    _hex(config.python_executable_sha256, "python executable")
    if _hash_file(config.node_executable_path) != config.node_executable_sha256:
        raise ExecutionRefusal("node executable hash drifted")
    if _hash_file(config.python_executable_path) != config.python_executable_sha256:
        raise ExecutionRefusal("python executable hash drifted")
    if require_official_runtime_identity and (
        config.verifier_runtime_bundle_sha256
        != OFFICIAL_DRAND_CLIENT_RUNTIME_BUNDLE_SHA256
        or config.node_executable_sha256 != OFFICIAL_NODE_EXECUTABLE_SHA256
        or config.node_version != OFFICIAL_NODE_VERSION
        or config.python_executable_sha256 != OFFICIAL_PYTHON_EXECUTABLE_SHA256
        or config.python_version != OFFICIAL_PYTHON_VERSION
        or config.unicode_data_version != OFFICIAL_UNICODE_DATA_VERSION
    ):
        raise ExecutionRefusal(
            "production Node/Python/Unicode/verifier identities differ from Source-A protocol constants"
        )
    try:
        node_version = subprocess.run(
            [str(config.node_executable_path), "--version"],
            text=True,
            capture_output=True,
            check=False,
            cwd=config.repo_root,
            env=_pinned_subprocess_environment(),
            timeout=VERIFIER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise ExecutionRefusal("node executable version preflight timed out") from error
    if node_version.returncode != 0 or node_version.stdout.strip() != config.node_version:
        raise ExecutionRefusal("node executable version drifted")
    expected_python = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if (
        config.python_executable_path.resolve() != Path(sys.executable).resolve()
        or config.python_version != expected_python
        or config.unicode_data_version != unicodedata.unidata_version
    ):
        raise ExecutionRefusal("active Python/Unicode runtime differs from frozen scorer runtime")
    if config.scorer_import_root.resolve() != config.repo_root.resolve():
        raise ExecutionRefusal("scorer import root must be the frozen repository root")
    if config.scorer_implementation_path.resolve() != (
        config.repo_root / "_research/dnrd/scorer.py"
    ).resolve():
        raise ExecutionRefusal("scorer implementation must be the frozen DNRD scorer source")
    expected_verifier_helper = config.repo_root / "_research/dnrd/verify-beacon.mjs"
    expected_verifier_lock = config.repo_root / "tools/swm0w_drand/package-lock.json"
    expected_verifier_bundle = (
        config.repo_root
        / "tools/swm0w_drand/node_modules/drand-client/build/esm/index.mjs"
    )
    if (
        config.verifier_helper_path != expected_verifier_helper
        or config.verifier_package_lock_path != expected_verifier_lock
        or config.verifier_runtime_bundle_path != expected_verifier_bundle
    ):
        raise ExecutionRefusal("verifier helper/lock/bundle topology drifted")
    if (
        tuple(config.bridge_command)
        != (str(config.node_executable_path), str(config.bridge_implementation_path))
        or tuple(config.scorer_command)
        != (str(config.python_executable_path), *SCORER_ARGUMENT_CONTRACT)
        or tuple(config.verifier_command)
        != (str(config.node_executable_path), str(config.verifier_helper_path))
    ):
        raise ExecutionRefusal("bridge/scorer/verifier command binding drifted")
    if set(config.bridge_config) != {"root_path", "frozen_scorer_source_sha256"}:
        raise ExecutionRefusal("bridge configuration field set drifted")
    if (
        config.bridge_state_root is None
        or config.bridge_config["root_path"] != str(config.bridge_state_root)
        or config.bridge_config["frozen_scorer_source_sha256"] != config.scorer_implementation_sha256
    ):
        raise ExecutionRefusal("bridge configuration does not bind its dedicated root and scorer")
    try:
        base_endpoint = OpenAICompatibleDnrdConfig(config.model_endpoint).base_url
    except ValueError as error:
        raise ExecutionRefusal("model endpoint is not a valid frozen OpenAI-compatible base URL") from error
    if not config.model_endpoint.startswith(("http://", "https://")) or base_endpoint != config.model_endpoint.rstrip("/").removesuffix("/v1"):
        raise ExecutionRefusal("model endpoint normalization drifted")
    _runtime_tree_manifest(config)
    return _runtime_receipt(
        config,
        execution_adapter_boundary=(
            PRODUCTION_EXECUTION_ADAPTER_BOUNDARY
            if require_official_runtime_identity
            else TEST_EXECUTION_ADAPTER_BOUNDARY
        ),
    )


def _generated_overlap(root: Path, public: Mapping[str, Any], git_paths: Sequence[str]) -> None:
    strings: set[str] = set()
    for stream in public["streams"]:
        for episode in stream["training"] + stream["heldout"]:
            strings.update((episode["episode_id"], episode["entity"], episode["surface_template"], episode["prompt"]))
            strings.update(episode["aliases"])
            for evidence in episode["route_evidence"]:
                strings.update((evidence["evidence_text"], evidence["response_token"], evidence["route_id"]))
    needles = [item.encode("utf-8") for item in strings if len(item) >= 16]
    for relative in git_paths:
        path = root / relative
        if not path.is_file():
            continue
        body = path.read_bytes()
        if any(needle in body for needle in needles):
            raise ExecutionRefusal(f"generated high-entropy string already occurs in tracked tree: {relative}")


def _json_object_unformatted(data: str, label: str) -> dict[str, Any]:
    """Strictly parse an externally observed JSON object without reformatting it.

    Unlike source/preregistration artifacts, a remote HTTP body is not
    required to be canonical JSON.  The caller binds its original UTF-8 bytes
    separately; this parser only rejects semantic ambiguities such as duplicate
    keys and NaN/Infinity before inspecting the resulting fields.
    """
    if not isinstance(data, str):
        raise ExecutionRefusal(f"{label} is not text")

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ExecutionRefusal(f"{label} repeats JSON key {key!r}")
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise ExecutionRefusal(f"{label} contains non-finite JSON value {value!r}")

    try:
        value = json.loads(
            data,
            object_pairs_hook=no_duplicates,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, ExecutionRefusal) as error:
        if isinstance(error, ExecutionRefusal):
            raise
        raise ExecutionRefusal(f"{label} is not UTF-8 JSON") from error
    if type(value) is not dict:
        raise ExecutionRefusal(f"{label} must be a JSON object")
    return value


def _preflight_request_digest(method: str, url: str, body: bytes | None) -> str:
    return _sha_bytes(
        canonical_json(
            {
                "body_sha256": _sha_bytes(body or b""),
                "content_type": "application/json",
                "method": method,
                "url": url,
            }
        )
    )


def _deployment_receipt(
    preflight: Mapping[str, Any],
    endpoint: str,
    *,
    tokenizer_prompt: str,
) -> dict[str, Any]:
    """Strictly verify the actual three-call live preflight receipt.

    This deliberately attests served id/root/max length/vLLM/chat settings and
    raw response observations.  It does *not* invent an unavailable checkpoint
    revision, tokenizer revision, template revision, or provider-cache claim.
    """
    required = {
        "schema_version",
        "endpoint",
        "model",
        "model_root",
        "model_max_model_len",
        "vllm_version",
        "chat_config",
        "model_list_request_sha256",
        "model_list_response_sha256",
        "model_list_response_utf8",
        "version_request_sha256",
        "version_response_sha256",
        "version_response_utf8",
        "tokenizer_request_sha256",
        "tokenizer_response_sha256",
        "tokenizer_response_utf8",
        "tokenizer_count",
        "provider_cache_independence",
        "generation_calls",
        "non_generation_http_calls",
        "preflight_call_order",
        "receipt_sha256",
    }
    if set(preflight) != required:
        raise ExecutionRefusal("live preflight receipt exact schema drifted")
    try:
        base_endpoint = OpenAICompatibleDnrdConfig(endpoint).base_url
    except ValueError as error:
        raise ExecutionRefusal("live preflight endpoint configuration is invalid") from error
    if (
        preflight["schema_version"] != PREFLIGHT_SCHEMA
        or preflight["endpoint"] != base_endpoint
        or preflight["model"] != MODEL_ID
        or preflight["model_root"] != MODEL_ROOT
        or preflight["model_max_model_len"] != MODEL_MAX_LENGTH
        or preflight["vllm_version"] != VLLM_VERSION
        or preflight["chat_config"] != CHAT_CONFIG
        or preflight["provider_cache_independence"] != PROVIDER_CACHE_UNOBSERVABLE
        or preflight["generation_calls"] != 0
        or preflight["non_generation_http_calls"] != 3
        or preflight["preflight_call_order"]
        != ["GET /v1/models", "GET /version", "POST /tokenize"]
        or type(preflight["tokenizer_count"]) is not int
        or preflight["tokenizer_count"] < 0
    ):
        raise ExecutionRefusal("live preflight does not evidence the exact frozen deployment/readback boundary")
    for digest in (
        "model_list_request_sha256",
        "model_list_response_sha256",
        "version_request_sha256",
        "version_response_sha256",
        "tokenizer_request_sha256",
        "tokenizer_response_sha256",
        "receipt_sha256",
    ):
        _hex(preflight[digest], f"preflight.{digest}")
    raw_bodies: dict[str, dict[str, Any]] = {}
    for prefix in ("model_list", "version", "tokenizer"):
        text_key, digest_key = f"{prefix}_response_utf8", f"{prefix}_response_sha256"
        if not isinstance(preflight[text_key], str) or _sha_bytes(
            preflight[text_key].encode("utf-8")
        ) != preflight[digest_key]:
            raise ExecutionRefusal("retained raw preflight response does not match its digest")
        raw_bodies[prefix] = _json_object_unformatted(preflight[text_key], f"preflight.{prefix} response")
    models_url = f"{base_endpoint}/v1/models"
    version_url = f"{base_endpoint}/version"
    tokenizer_url = f"{base_endpoint}/tokenize"
    tokenizer_body = canonical_json({"model": MODEL_ID, "prompt": tokenizer_prompt})
    if (
        preflight["model_list_request_sha256"] != _preflight_request_digest("GET", models_url, None)
        or preflight["version_request_sha256"] != _preflight_request_digest("GET", version_url, None)
        or preflight["tokenizer_request_sha256"]
        != _preflight_request_digest("POST", tokenizer_url, tokenizer_body)
    ):
        raise ExecutionRefusal("preflight request identities do not bind exact endpoint/order/body")
    data = raw_bodies["model_list"].get("data")
    matching = [row for row in data if type(row) is dict and row.get("id") == MODEL_ID] if type(data) is list else []
    if (
        len(matching) != 1
        or matching[0].get("root") != MODEL_ROOT
        or matching[0].get("max_model_len") != MODEL_MAX_LENGTH
        or raw_bodies["version"].get("version") != VLLM_VERSION
    ):
        raise ExecutionRefusal("retained preflight responses do not attest frozen served deployment")
    tokenized = raw_bodies["tokenizer"]
    if tokenized.get("count") != preflight["tokenizer_count"] or (
        "tokens" in tokenized
        and (type(tokenized["tokens"]) is not list or len(tokenized["tokens"]) != preflight["tokenizer_count"])
    ):
        raise ExecutionRefusal("retained tokenizer preflight response is inconsistent")
    unsigned = {key: value for key, value in preflight.items() if key != "receipt_sha256"}
    if preflight["receipt_sha256"] != commitment(unsigned):
        raise ExecutionRefusal("live preflight receipt self-hash mismatch")
    return dict(preflight)


def _attempt_lock(
    config: ExecutionConfig,
    *,
    pulse_receipt_sha256: str,
    runtime_receipt_sha256: str,
) -> dict[str, Any]:
    if config.attempt_registry_root is None:
        raise ExecutionRefusal("singleton attempt registry is required")
    unsigned = {
        "schema_version": ATTEMPT_LOCK_SCHEMA,
        "enforcement_scope": ATTEMPT_MARKER_SCOPE,
        "source_commit": config.source_a_commit,
        "source_tree_oid": config.source_a_tree,
        "source_manifest_sha256": config.source_manifest_sha256,
        "preregistration_commit": config.prereg_b_commit,
        "preregistration_sha256": config.prereg_sha256,
        "ratification_statement_sha256": config.ratification_text_sha256,
        "pulse_receipt_sha256": pulse_receipt_sha256,
        "runtime_receipt_sha256": runtime_receipt_sha256,
    }
    lock = {**unsigned, "receipt_sha256": commitment(unsigned)}
    target = config.attempt_registry_root / f"{lock['receipt_sha256']}.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(target, flags, 0o400)
    except FileExistsError as error:
        raise ExecutionRefusal("this exact frozen DNRD occurrence already has a durable attempt lock") from error
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json(lock))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(target, 0o400)
    except Exception:
        # Do not remove a possibly-visible marker: ambiguity must consume the
        # identity rather than permit a replacement attempt.
        raise
    return lock


def _jsonl(events: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_json(dict(event)) + b"\n" for event in events)


def _pinned_subprocess_environment() -> dict[str, str]:
    """No inherited import/cwd/cache behavior enters bridge or scorer processes."""
    return {
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONUTF8": "1",
        "TZ": "UTC",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }


def _production_dependencies(config: ExecutionConfig) -> ExecutionDependencies:
    """Construct the one real runtime path without persisting a secret."""
    api_key = os.environ.get(config.model_api_key_environment)
    if not api_key:
        raise ExecutionRefusal(
            f"required model credential environment variable is absent: {config.model_api_key_environment}"
        )
    events: list[Mapping[str, Any]] = []
    transport = UrllibHttpTransport()
    live_config = OpenAICompatibleDnrdConfig(config.model_endpoint, api_key=api_key)
    answerer = OpenAICompatibleDnrdAnswerer(live_config, transport, event_sink=events.append)
    if config.node_executable_path is None or config.python_executable_path is None:
        raise ExecutionRefusal("production subprocess executable pins are incomplete")
    paths = _execution_closure_paths(config)
    bridge = SubprocessJsonBridge(
        (str(config.node_executable_path), str(paths["bridge_implementation"])),
        implementation_path=paths["bridge_implementation"],
        implementation_sha256=config.bridge_implementation_sha256,
        config=config.bridge_config,
        working_directory=paths["bridge_root"],
        environment=_pinned_subprocess_environment(),
        deferred_binding=True,
    )
    scorer = SubprocessOutcomeScorer(
        config.scorer_command,
        implementation_path=paths["scorer_implementation"],
        implementation_sha256=config.scorer_implementation_sha256,
        private_manifest_path=config.output_root / "private" / "private_manifest.json",
        working_directory=paths["scorer_root"],
        environment=_pinned_subprocess_environment(),
        deferred_binding=True,
    )
    assert config.bridge_state_root is not None
    closure_exporter = _ProductionBridgeMountClosureExporter(
        config.bridge_state_root,
        config.output_root,
    )

    def verifier(command: Sequence[str]) -> bytes:
        expected_prefix = (
            *config.verifier_command,
            "online",
            "--expected-round",
        )
        if (
            len(command) != len(expected_prefix) + 1
            or tuple(command[:-1]) != expected_prefix
            or not str(command[-1]).isdigit()
            or int(command[-1]) < 1
        ):
            raise ExecutionRefusal("online pulse verifier invocation drifted")
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                cwd=config.verifier_helper_path.parent,
                env=_pinned_subprocess_environment(),
                timeout=VERIFIER_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as error:
            raise ExecutionRefusal("pinned online pulse verifier timed out") from error
        if completed.returncode != 0:
            raise ExecutionRefusal("pinned online pulse verifier refused")
        return bytes(completed.stdout)

    def preflight(_: ExecutionConfig) -> Mapping[str, Any]:
        assert config.tokenizer_preflight_prompt is not None
        return preflight_deployment_and_tokenizer(
            live_config,
            transport,
            tokenizer_prompt=config.tokenizer_preflight_prompt,
        )

    return ExecutionDependencies(
        answerer=answerer,
        bridge=bridge,
        scorer=scorer,
        verifier_runner=verifier,
        live_preflight=preflight,
        model_event_ledger=lambda: tuple(events),
        closure_exporter=closure_exporter,
    )


def _execute(
    config: ExecutionConfig,
    dependencies: ExecutionDependencies | None,
) -> ExecutionResult:
    """Bind production status to internal dependency construction, never a flag."""
    require_official_runtime_identity = dependencies is None
    runtime_receipt = _verify_static_pins(
        config,
        require_official_runtime_identity=require_official_runtime_identity,
    )
    verifier_runtime_bundle_bytes = _validated_verifier_runtime_bundle_bytes(
        config.verifier_runtime_bundle_path,
        require_official_identity=require_official_runtime_identity,
    )
    source_ci_receipt, source_ci_bytes = _load_source_ci_receipt(config)
    ratification_receipt, ratification_bytes = _load_ratification_receipt(config)
    source_manifest = _load_source_manifest(config)
    runtime_tree_manifest = _runtime_tree_manifest(config)
    preregistration = _validate_preregistration(config, source_ci_receipt=source_ci_receipt)
    if dependencies is None:
        dependencies = _production_dependencies(config)
    source_time, git_chronology_evidence = _preflight_git(config, dependencies)
    if config.output_root.exists():
        raise ExecutionRefusal("output root must be a new dedicated path")
    if dependencies.model_event_ledger is None:
        raise ExecutionRefusal("execution requires the actual live answerer event ledger")
    if dependencies.closure_exporter is None:
        raise ExecutionRefusal("execution requires the production/raw bridge mount-closure exporter")
    source_binding = SourceFreezeBinding(
        config.source_a_commit,
        config.source_a_tree,
        config.source_manifest_sha256,
        config.prereg_b_commit,
        config.prereg_sha256,
        config.ratification_text_sha256,
    )
    eligible_round = first_eligible_quicknet_round(
        source_freeze_unix=source_time,
        user_ratification_unix=config.ratification_unix,
    )
    verifier_bytes = dependencies.verifier_runner(
        [*config.verifier_command, "online", "--expected-round", str(eligible_round)]
    )
    projection = projection_from_verifier_receipt_bytes(
        verifier_bytes,
        expected_helper_sha256=config.verifier_helper_sha256,
        expected_package_lock_sha256=config.verifier_package_lock_sha256,
        expected_runtime_bundle_sha256=config.verifier_runtime_bundle_sha256,
        expected_runtime_exec_sha256=config.node_executable_sha256,
        expected_runtime_version=config.node_version,
    )
    pulse = bind_future_pulse(
        source_freeze_unix=source_time,
        user_ratification_unix=config.ratification_unix,
        projection=projection,
        source_binding=source_binding,
    )
    # Consume this frozen occurrence before deriving any test material or
    # entering the live boundary.  A later failure must not open a replacement
    # attempt merely by choosing another output directory.
    attempt_lock = _attempt_lock(
        config,
        pulse_receipt_sha256=pulse.receipt_sha256,
        runtime_receipt_sha256=runtime_receipt["receipt_sha256"],
    )
    public, private = generate_manifests(bytes.fromhex(pulse.seed_hex))
    tracked = [item for item in _git(config, dependencies, "ls-files").splitlines() if item]
    _generated_overlap(config.repo_root, public, tracked)
    assert config.tokenizer_preflight_prompt is not None
    deployment = _deployment_receipt(
        dependencies.live_preflight(config),
        config.model_endpoint,
        tokenizer_prompt=config.tokenizer_preflight_prompt,
    )

    config.output_root.mkdir(mode=0o700, parents=False)
    os.chmod(config.output_root, 0o700)
    private_dir = config.output_root / "private"
    private_dir.mkdir(mode=0o700)
    _atomic_bytes(
        config.output_root / "source_manifest.json",
        _plain_relative_file(config.repo_root, config.source_manifest_path, "source manifest").read_bytes(),
    )
    _copy_source_closure(config.output_root, config.repo_root, source_manifest)
    _atomic_bytes(
        config.output_root / "preregistration.json",
        _plain_relative_file(config.repo_root, config.prereg_path, "preregistration").read_bytes(),
    )
    _atomic_bytes(config.output_root / "source_ci_receipt.json", source_ci_bytes)
    _atomic_bytes(config.output_root / "ratification_receipt.json", ratification_bytes)
    _atomic_json(config.output_root / "git_chronology_evidence.json", git_chronology_evidence)
    _atomic_json(config.output_root / "public_manifest.json", public)
    _atomic_json(private_dir / "private_manifest.json", private, 0o600)
    _atomic_bytes(config.output_root / "pulse_verifier_receipt.json", verifier_bytes)
    _atomic_json(config.output_root / "pulse_binding.json", pulse.canonical())
    _atomic_json(config.output_root / "deployment_receipt.json", deployment)
    _atomic_json(config.output_root / "runtime_receipt.json", runtime_receipt)
    _atomic_bytes(
        config.output_root / VERIFIER_RUNTIME_BUNDLE_EVIDENCE_PATH,
        verifier_runtime_bundle_bytes,
        0o400,
    )
    assert config.bridge_runtime_tree_manifest_path is not None
    assert config.bridge_runtime_root is not None
    _atomic_bytes(
        config.output_root / "bridge_runtime_tree_manifest.json",
        config.bridge_runtime_tree_manifest_path.read_bytes(),
        0o400,
    )
    _copy_runtime_closure(
        config.output_root,
        config.bridge_runtime_root,
        runtime_tree_manifest,
    )
    _atomic_json(config.output_root / "attempt_lock_receipt.json", attempt_lock)
    readback = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in asdict(config).items()
        if key not in {"ratification_text"}
    }
    _atomic_json(config.output_root / "config_readback.json", readback)

    runner_events: list[Mapping[str, Any]] = []

    def sink(event: Mapping[str, Any]) -> None:
        runner_events.append(dict(event))

    bindings = {
        "source_manifest_sha256": config.source_manifest_sha256,
        "preregistration_sha256": config.prereg_sha256,
        "pulse_receipt_sha256": pulse.receipt_sha256,
        "split_manifest_sha256": commitment(public),
        "model_deployment_sha256": commitment(deployment),
        "scorer_sha256": config.scorer_implementation_sha256,
        "runtime_receipt_sha256": runtime_receipt["receipt_sha256"],
        "git_chronology_evidence_sha256": _sha_bytes(
            (config.output_root / "git_chronology_evidence.json").read_bytes()
        ),
    }
    metadata = MeasurementMetadata(
        bindings=bindings,
        chronology={
            "source_commit": config.source_a_commit,
            "preregistration_commit": config.prereg_b_commit,
            "source_tree_oid": config.source_a_tree,
            "source_frozen_at_unix": source_time,
            "preregistration_committed_at_unix": git_chronology_evidence["preregistration"]["commit_time_unix"],
            "external_ratification_at_unix": config.ratification_unix,
            "pulse_round": projection.round,
            "pulse_chain_hash": projection.chain_hash,
            "pulse_at_unix": projection.round_time_unix,
        },
        overlap={
            "normalizer_sha256": _sha_bytes(b"NFKC_CASEFOLD_TRIM_COLLAPSE_SPACE_V1"),
            "training_heldout_exact_overlap": 0,
            "training_heldout_normalized_overlap": 0,
            "prior_item_overlap": 0,
            "leak_detected": False,
            "watermark_detected": False,
        },
        deployment_receipt=deployment,
        scorer_source_identity=config.scorer_implementation_sha256,
        scorer_address="_research/dnrd/scorer.py",
        # The byte ceiling comes from the parsed preregistration; W0 is not
        # padded to imitate byte equality with W1.
        active_state_byte_ceiling=preregistration["parity_and_leakage"]["active_state_byte_ceiling"],
    )
    result = run_diagnostic(
        public,
        private_manifest_commitment=public["private_manifest_commitment"],
        answerer=dependencies.answerer,
        bridge=dependencies.bridge,
        scorer=dependencies.scorer,
        metadata=metadata,
        event_sink=sink,
        model_event_ledger_provider=dependencies.model_event_ledger,
        closure_exporter=dependencies.closure_exporter,
    )
    model_events = tuple(dict(event) for event in dependencies.model_event_ledger())
    runner_bytes, model_bytes = _jsonl(runner_events), _jsonl(model_events)
    _atomic_bytes(config.output_root / "runner_events.jsonl", runner_bytes)
    _atomic_bytes(config.output_root / "model_events.jsonl", model_bytes)
    runner_digest = _sha_bytes(runner_bytes)
    model_digest = _sha_bytes(model_bytes)
    if result.candidate is not None:
        if (
            result.runner_event_ledger_sha256 != runner_digest
            or result.model_event_ledger_sha256 != model_digest
            or result.bridge_state_evidence is None
            or result.bridge_state_evidence_sha256 is None
            or result.bridge_mount_closure_sha256 is None
            or result.candidate["bindings"].get("event_ledger_sha256") != runner_digest
            or result.candidate["bindings"].get("model_event_ledger_sha256") != model_digest
            or result.candidate["bindings"].get("bridge_state_evidence_sha256")
            != result.bridge_state_evidence_sha256
            or result.candidate["bindings"].get("bridge_mount_closure_sha256")
            != result.bridge_mount_closure_sha256
        ):
            raise RuntimeError("runner candidate ledger binding differs from exact emitted JSONL")
        _atomic_json(config.output_root / "bridge_state_evidence.json", result.bridge_state_evidence)
        if _sha_bytes((config.output_root / "bridge_state_evidence.json").read_bytes()) != result.bridge_state_evidence_sha256:
            raise RuntimeError("bridge state evidence bytes differ from runner-bound receipt")
        closure_manifest = config.output_root / "bridge_mount_closure.json"
        if (
            not closure_manifest.is_file()
            or _sha_bytes(closure_manifest.read_bytes())
            != result.bridge_mount_closure_sha256
        ):
            raise RuntimeError("bridge mount closure bytes differ from runner-bound receipt")
        _atomic_json(config.output_root / "candidate.json", result.candidate)
    elif result.inconclusive_occurrence is not None:
        _atomic_json(config.output_root / "inconclusive.json", result.inconclusive_occurrence)
    else:
        raise RuntimeError("runner returned neither candidate nor inconclusive occurrence")
    _atomic_json(config.output_root / "bundle_index.json", _bundle_index(config.output_root))
    return ExecutionResult(config.output_root, result, runner_digest, result.model_event_ledger_sha256)


def execute_with_dependencies(config: ExecutionConfig, dependencies: ExecutionDependencies) -> ExecutionResult:
    """Test-only seam.  Production callers must use :func:`execute`."""
    return _execute(config, dependencies)


def execute(config: ExecutionConfig) -> ExecutionResult:
    """Run one production DNRD occurrence through only hash-bound adapters."""
    return _execute(config, None)


def _config_from_json(path: Path) -> ExecutionConfig:
    raw = path.read_bytes()
    value = _strict_json_bytes(raw, "runtime configuration")
    expected = {
        "repo_root",
        "source_a_commit",
        "source_a_tree",
        "source_manifest_path",
        "source_manifest_sha256",
        "prereg_b_commit",
        "prereg_path",
        "prereg_sha256",
        "source_freeze_unix",
        "ratification_unix",
        "ratification_text",
        "ratification_text_sha256",
        "output_root",
        "model_endpoint",
        "bridge_implementation_path",
        "bridge_implementation_sha256",
        "bridge_command",
        "bridge_config",
        "scorer_implementation_path",
        "scorer_implementation_sha256",
        "scorer_command",
        "verifier_command",
        "verifier_helper_path",
        "verifier_helper_sha256",
        "verifier_package_lock_path",
        "verifier_package_lock_sha256",
        "verifier_runtime_bundle_path",
        "verifier_runtime_bundle_sha256",
        "attempt_registry_root",
        "ratification_receipt_path",
        "ratification_receipt_sha256",
        "source_ci_receipt_path",
        "source_ci_receipt_sha256",
        "tokenizer_preflight_prompt",
        "bridge_runtime_root",
        "bridge_state_root",
        "bridge_runtime_tree_manifest_path",
        "bridge_runtime_tree_manifest_sha256",
        "node_executable_path",
        "node_executable_sha256",
        "node_version",
        "python_executable_path",
        "python_executable_sha256",
        "python_version",
        "unicode_data_version",
        "scorer_import_root",
        "model_api_key_environment",
    }
    data = _exact_keys(value, expected, "runtime configuration")
    forbidden_secret_keys = {key for key in data if key.casefold() in {"api_key", "token", "password", "secret"}}
    if forbidden_secret_keys:
        raise ExecutionRefusal("runtime configuration must name an environment variable, never persist a secret")
    path_keys = {
        "repo_root",
        "output_root",
        "bridge_implementation_path",
        "scorer_implementation_path",
        "verifier_helper_path",
        "verifier_package_lock_path",
        "verifier_runtime_bundle_path",
        "attempt_registry_root",
        "ratification_receipt_path",
        "source_ci_receipt_path",
        "bridge_runtime_root",
        "bridge_state_root",
        "bridge_runtime_tree_manifest_path",
        "node_executable_path",
        "python_executable_path",
        "scorer_import_root",
    }
    kwargs = dict(data)
    for key in path_keys:
        if not isinstance(kwargs[key], str) or not kwargs[key]:
            raise ExecutionRefusal(f"runtime configuration {key} must be an absolute path string")
        kwargs[key] = Path(kwargs[key])
        if not kwargs[key].is_absolute():
            raise ExecutionRefusal(f"runtime configuration {key} must be an absolute path string")
    for key in ("bridge_command", "scorer_command", "verifier_command"):
        if type(kwargs[key]) is not list or not all(isinstance(item, str) and item for item in kwargs[key]):
            raise ExecutionRefusal(f"runtime configuration {key} must be a nonempty string array")
        kwargs[key] = tuple(kwargs[key])
    if type(kwargs["bridge_config"]) is not dict:
        raise ExecutionRefusal("runtime configuration bridge_config must be an object")
    return ExecutionConfig(**kwargs)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(f"usage: {Path(sys.argv[0]).name} RUNTIME_CONFIG.json", file=sys.stderr)
        return 2
    try:
        execute(_config_from_json(Path(args[0])))
    except ExecutionRefusal as error:
        print(f"DNRD execution refused: {error}", file=sys.stderr)
        return 2
    return 0
