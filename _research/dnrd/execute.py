"""One no-verdict execution boundary for the DNRD diagnostic.

This is deliberately DNRD-specific: it freezes one source/preregistration
identity, binds one future Quicknet pulse, performs the fixed three-request
non-generation preflight, and then invokes the fixed runner once.  It never
interprets a candidate or emits a scientific terminal.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
from .seed import (
    EXPERIMENT_ID,
    SourceFreezeBinding,
    bind_future_pulse,
    first_eligible_quicknet_round,
    projection_from_verifier_receipt_bytes,
)
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
    prereg_b_tree: str
    prereg_path: str
    prereg_sha256: str
    source_freeze_unix: int
    preregistration_ci_completed_unix: int
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
    preregistration_ci_receipt_path: Path | None = None
    preregistration_ci_receipt_sha256: str | None = None
    source_ci_receipt_path: Path | None = None
    source_ci_receipt_sha256: str | None = None
    structured_output_qualification_path: Path | None = None
    structured_output_qualification_sha256: str | None = None
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
    model_event_ledger_path: Path | None = None


@dataclass(frozen=True)
class ExecutionResult:
    output_dir: Path
    runner_result: RunnerResult
    event_ledger_sha256: str
    model_event_ledger_sha256: str | None


_HEX = frozenset("0123456789abcdef")
SOURCE_MANIFEST_SCHEMA = "hswm-dnrd-source-freeze-manifest/v1"
SOURCE_CI_RECEIPT_SCHEMA = "hswm-dnrd-source-ci-receipt/v2"
STRUCTURED_OUTPUT_QUALIFICATION_SCHEMA = "hswm-dnrd4s1-structured-output-qualification-summary/v1"
STRUCTURED_OUTPUT_QUALIFICATION_DOMAIN = "HSWM-DNRD4S1-STRUCTURED-OUTPUT-QUALIFICATION-v1"
STRUCTURED_OUTPUT_QUALIFICATION_RECORD_ROLE = (
    "CONTENT_ADDRESSED_OPERATOR_SUMMARY_OF_DISJOINT_NONSCIENTIFIC_LIVE_"
    "QUALIFICATION_NOT_SCIENTIFIC_EVIDENCE"
)
QUALIFICATION_SOURCE_PATHS = (
    "_research/dnrd/live.py",
    "_research/dnrd/qualify.py",
    "_research/dnrd/runner.py",
    "_research/dnrd/task_family.py",
)
PREREGISTRATION_B_CI_RECEIPT_SCHEMA = "hswm-dnrd-preregistration-b-ci-receipt/v2"
ATTEMPT_LOCK_SCHEMA = "hswm-dnrd-durable-attempt-marker/v5"
GIT_CHRONOLOGY_EVIDENCE_SCHEMA = "hswm-dnrd-git-chronology-evidence/v4"
BUNDLE_INDEX_SCHEMA = "hswm-dnrd-evidence-bundle-index/v1"
VOID_PROTOCOL_SCHEMA = "hswm-dnrd-void-protocol/v2"
TERMINAL_INTENT_SCHEMA = "hswm-dnrd-terminal-intent/v1"
ATTEMPT_MARKER_SCOPE = (
    "DETERMINISTIC_OCCURRENCE_ID_FILE_AND_PARENT_DIRECTORY_FSYNC_MARKER_UNDER_"
    "B_PINNED_LOCAL_REGISTRY_ONLY_SAME_UID_CROSS_HOST_AND_GLOBAL_SINGLETON_NOT_PROVEN"
)
RUNTIME_TREE_MANIFEST_SCHEMA = "hswm-dnrd-bridge-runtime-tree-manifest/v4"
RUNTIME_RECEIPT_SCHEMA = "hswm-dnrd-runtime-receipt/v3"
EXECUTION_CLOSURE_ISOLATION_CLAIM = (
    "OWNER_READ_EXECUTE_ONLY_COPIED_CLOSURES_PER_INVOCATION_ENTRYPOINT_REHASHED_"
    "SAME_UID_ADVERSARIAL_IMMUTABILITY_NOT_PROVEN"
)
RUNTIME_CLOSURE_MAX_FILES = 8_192
RUNTIME_CLOSURE_MAX_TOTAL_BYTES = 67_108_864
VERIFIER_TIMEOUT_SECONDS = 60
TOKENIZER_PREFLIGHT_PROMPT = (
    '{"response_token":"token-ffffffffffffffffffff"}'
)
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
PREREG_SCHEMA = "hswm-durable-numeric-routing-diagnostic-preregistration/v4"
PROTOCOL_VERSION = "v4s1"
PREREG_CLAIM_BOUNDARY = {
    "canonical_role": (
        "BOUNDED_SCHEMA_APPROVED_DURABLE_NUMERIC_ROUTING_ENGINEERING_CONFORMANCE_"
        "PROJECTION_NOT_SCIENTIFIC_EFFECT_EVIDENCE_NOT_HSWM_COGNITION_NOT_LEARNING_"
        "NOT_EFFICACY"
    ),
    "predecessor_bindings": [
        "P1_SCALAR_SLOW_WEIGHT_SCIENTIFIC_RED_ZERO_ACTIVE_UPDATES",
        "P1V3_P1V4_SYNTHETIC_L0_ACTUATION_ONLY_NO_L1_INHERITANCE",
        "P1V3V4_L1_CAUSAL_LESSON_KILLED_BEFORE_REGISTRATION_NO_REVIVAL",
        "DNRD1_VOID_PROTOCOL_POST_FIRST_CALL_NO_MECHANICS_RESULT_NO_RETRY",
        "DNRD2_JUDGMENT_REFUSED_POST_THIRD_CALL_NO_MECHANICS_RESULT_NO_RETRY",
        "DNRD3_STRUCTURAL_VOID_POST_128_CALLS_NO_MECHANICS_RESULT_NO_RETRY",
        "DNRD3_PREREGISTRATION_SHA256=2bcbe110cac8b69b3889761c05635a8af62b09a443e2a10a2a4a62aad0791226",
        "DNRD3_RESULT_COMMIT=43c1b9885352ed99e6845884b0adec0445f1be4b",
        "DNRD3_CHECKED_EVIDENCE_RECEIPT_SELF_SHA256=55c9de56932b3b28ab049e056e93051312442ca84c29c90182ffc485d996e829",
        "DNRD4_FROZEN_UNEXECUTED_PREMARKER_STATIC_INSTRUMENT_REFUSAL_NO_QUICKNET_NO_MARKER_NO_GENERATION_NO_OCCURRENCE_NO_JUDGMENT",
        "DNRD4_SOURCE_A_COMMIT=276fc42354169cb5f0f0bc6cbaf34052047cd630",
        "DNRD4_PREREGISTRATION_B_COMMIT=b1dc53d8efdaee24d1ffad10cc558a48321bc6ac",
        "DNRD4_PREREGISTRATION_SHA256=87cdf810e3c4c88a8b755f5b31bd3b98dad6bff9d5c320e58eaeb7b2659a3762",
        "DNRD4_INVALID_RUNTIME_MANIFEST_SHA256=fbca6ec3d59fc575f7a9effc4f7add15da8d56e280b5434981f84355f9cdd737",
    ],
    "forbidden_rescues": [
        "NO_POST_FREEZE_TUNING_OR_GATE_RELAXATION",
        "NO_RETRY_RERUN_RESUME_REPLACEMENT_OR_SECOND_PULSE",
        "NO_RELABELING_DNRD4S1_AS_A_DNRD1_DNRD2_DNRD3_OR_DNRD4_RETRY_REPAIR_REPLACEMENT_OR_RESULT",
        "NO_RELABELING_NUMERIC_REPLAY_AS_RAW_TRANSCRIPT_COMPARISON",
        "NO_PROMOTION_TO_SCIENTIFIC_EFFECT_EVIDENCE_LLM_LEARNING_UNSEEN_GENERALIZATION_"
        "UTILITY_OR_HSWM_EFFICACY",
    ],
    "scientific_question": (
        "In one source/runtime-trusted finite engineering-conformance occurrence with "
        "repeated-context exhaustive forced exposure, does a response-independent "
        "scorer-outcome-bound integer routing payload persist across fresh-process recovery "
        "and alter pre-model route selection relative to exact W0 rollback and context-binding "
        "derangement, while fixed-rule replay of the same retained training update records "
        "reproduces W1 without model dispatch?"
    ),
    "hypotheses": {
        "integrity_go": (
            "All frozen deterministic engineering-conformance mechanics, parity, leakage, "
            "recovery, rollback, derangement, and replay-fidelity checks hold in the singleton "
            "occurrence; this is not a scientific effect hypothesis."
        ),
        "diagnostic_no_go": (
            "At least one non-void engineering-conformance check lacks headroom, persistence, "
            "exact rollback, pre-model routing actuation, derangement sensitivity, or replay "
            "fidelity."
        ),
        "void": (
            "Identity, chronology, leakage, parity, call accounting, immutable evidence, "
            "or singleton protocol integrity is contradicted."
        ),
        "primary_finite_rule": (
            "IN_EACH_OF_FOUR_STREAMS_FULL_ROUTE_REWARD_POSITIVE_8_OF_8_W0_POSITIVE_"
            "4_OF_8_DERANGED_POSITIVE_AT_MOST_4_OF_8_FULL_DIFFERS_FROM_W0_EXACTLY_"
            "4_OF_8_AND_FROM_DERANGED_AT_LEAST_4_OF_8_ALL_READ_BEFORE_MODEL_DISPATCH"
        ),
    },
    "testbed_claims": {
        "relationship_to_prior_p1": (
            "SEPARATE_ENGINEERING_CONFORMANCE_DIAGNOSTIC_NO_RESCUE_NO_EFFECT_OR_EFFICACY_"
            "INHERITANCE"
        ),
        "analysis_unit": (
            "ONE_FUTURE_SEEDED_REPEATED_CONTEXT_STREAM_BY_ARM_FINITE_CONFORMANCE_"
            "PROJECTION_NOT_AN_INDEPENDENT_SAMPLE"
        ),
        "freshness": (
            "FUTURE_QUICKNET_SEEDED_IDENTIFIERS_AND_CANARIES_WITH_REPEATED_CONTEXT_KEYS"
        ),
    },
    "learning_boundary": {
        "fixture_scope": (
            "ALL_CONTEXT_ROUTE_CELLS_FORCED_ONCE_AND_SAME_CONTEXTS_REUSED_AT_HELDOUT"
        ),
        "model_role": (
            "STRICT_FORMAT_AND_LIVENESS_BOUNDARY_RESPONSE_NOT_REQUIRED_TO_MATCH_SELECTED_ROUTE_"
            "EVIDENCE_NOT_THE_LEARNER_UNDER_TEST"
        ),
        "response_boundary": (
            "SERVER_CONSTRAINED_STRICT_JSON_TWO_PUBLIC_CANDIDATE_ENUM_MAX_OUTPUT_64_"
            "EXACT_STOP_REQUIRED_PER_CALL_RESPONSE_IS_POST_ROUTE_NUISANCE_NOT_OUTCOME"
        ),
        "scorer_role": "DECLARED_ROLE_SEPARATION_NOT_PROVEN",
        "replay_role": (
            "NO_MODEL_ADMISSION_GATE_FOR_FIXED_RULE_RETAINED_UPDATE_RECORD_REPLAY_ONLY"
        ),
    },
    "arms": {
        "FULL": (
            "For each stream, apply exactly eight locally declared scorer outcomes to the "
            "durable integer routing payload before read-only repeated-context evaluation."
        ),
        "NO_MEMORY_ROLLBACK": (
            "Recover and evaluate the exact immutable W0 genesis payload with no learned update."
        ),
        "BINDING_DERANGED_NUMERIC_PLACEBO": (
            "Permute context bindings within stratum while preserving the matched numeric "
            "payload byte count, precision, update multiset, and L1/L2 norms; full history, "
            "atom, and reference parity are not claimed."
        ),
    },
    "interventions": {
        "rollback": "EXACT_W0_RECOVERY_AND_POST_FULL_RESTORE_REPLAY",
        "binding_derangement": "WITHIN_STRATUM_NO_FIXED_POINT_CONTEXT_PERMUTATION",
        "fixed_rule_replay_gate": (
            "NO_MODEL_DISPATCH_SAME_RETAINED_UPDATE_RECORDS_SAME_FIXED_INTEGER_UPDATE_RULE_"
            "FROM_W0_MUST_REPRODUCE_W1_NUMERIC_PAYLOAD_AND_ROUTE_READOUT"
        ),
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
        "FIXED_RULE_REPLAY_W1_NUMERIC_PAYLOAD_AND_PRE_MODEL_READOUT_EQUALITY_GATE",
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
        "ONE_OCCURRENCE_ID_DERIVED_ONLY_FROM_IMMUTABLE_DNRD4S1_SEMANTICS_FILE_AND_PARENT_"
        "DIRECTORY_FSYNC_MARKER_UNDER_B_PINNED_LOCAL_REGISTRY_SCOPED_SINGLETON_OCCURRENCE_"
        "DNRD1_DNRD2_AND_DNRD3_REMAIN_CONSUMED_DNRD4_REMAINS_FROZEN_UNEXECUTED_"
        "NO_RETRY_RERUN_RESUME_OR_REPLACEMENT"
    ),
    "required_before_measurement": [
        "CLEAN_PUSHED_SOURCE_A_WITH_EXACT_SOURCE_MANIFEST",
        "SUCCESSFUL_GITHUB_ACTIONS_RECEIPT_FOR_EXACT_SOURCE_A",
        "DIRECT_CHILD_PREREGISTRATION_B_CHANGING_EXACTLY_ONE_PREREG_PATH",
        "SUCCESSFUL_GITHUB_ACTIONS_RECEIPT_FOR_EXACT_PREREGISTRATION_B",
        "FIRST_ELIGIBLE_QUICKNET_PULSE_AT_LEAST_900_SECONDS_AFTER_SOURCE_A_AND_PREREGISTRATION_B_CI",
        "DNRD1_DNRD2_AND_DNRD3_ATTEMPT_MARKERS_AND_OCCURRENCES_REMAIN_UNCHANGED_AND_CONSUMED",
        "DNRD4_FROZEN_A_B_MANIFEST_AND_ABSENT_OCCURRENCE_REMAIN_UNCHANGED_AND_UNCONSUMED",
    ],
    "result_promotion": {
        "only_go_terminal": "DIAGNOSTIC_INTEGRITY_GO_NO_UTILITY_CLAIM",
        "non_go_terminals": [
            "DIAGNOSTIC_NO_GO",
            "VOID_PROTOCOL",
            "INCONCLUSIVE_OCCURRENCE",
        ],
        "confirmatory_effect": (
            "MAY_ONLY_OPEN_A_SEPARATELY_PREREGISTERED_RESPONSE_DEPENDENT_INDEPENDENT_OUTCOME_"
            "CAUSAL_DESIGN"
        ),
        "forbidden_claims": [
            "SCIENTIFIC_EFFECT_EVIDENCE",
            "MODEL_RESPONSE_CAUSED_OUTCOME_OR_ROUTING_UPDATE",
            "INDEPENDENT_SAMPLING_POPULATION_ESTIMATE_OR_ERROR_RATE",
            "LLM_LEARNING",
            "UNSEEN_CONTEXT_GENERALIZATION",
            "INDEPENDENT_OUTCOME_OR_SCORER_ISOLATION",
            "UTILITY_OR_DURABLE_STATE_SUPERIORITY",
            "HSWM_CONTINUOUS_LEARNING_OR_EFFICACY",
            "TOPOLOGY_ROLE_SPECIALIZATION_TRANSFER_OR_CONSOLIDATION",
        ],
    },
    "measurement_gate": (
        "NO_GENERATION_BEFORE_SUCCESSFUL_PREREGISTRATION_B_CI_AND_FIRST_ELIGIBLE_"
        "QUICKNET_PULSE_AT_LEAST_900_SECONDS_AFTER_SOURCE_A_AND_PREREGISTRATION_B_CI"
    ),
}
CORE_SOURCE_FILES = frozenset(
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
        "tests/test_hswm_dnrd_integration.py",
        "tests/test_hswm_dnrd_judge.py",
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
        "src/hswm/effect-runtime/src/canonical-atom-v2-dnrd5-identity.ts",
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


def _plain_file(path: Path, label: str, *, mode: int | None = None) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError as error:
        raise ExecutionRefusal(f"{label} is absent") from error
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ExecutionRefusal(f"{label} must be a plain regular file")
    if mode is not None and stat.S_IMODE(info.st_mode) != mode:
        raise ExecutionRefusal(f"{label} must have mode {mode:04o}")


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
        stream = _exact_keys(
            item, {"stream_id", "arms", "fixed_rule_replay"},
            "bridge mount closure plan stream",
        )
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
        replay = _exact_keys(
            stream["fixed_rule_replay"], expected_arm_fields,
            "bridge mount closure plan fixed-rule replay",
        )
        replay_mount_id = replay["mount_id"]
        if (
            not isinstance(replay_mount_id, str)
            or _MOUNT_ID_RE.fullmatch(replay_mount_id) is None
            or replay_mount_id in seen_mounts
            or replay["mount_role"] != MOUNT_ROLES["RAW_EQUAL_BUDGET"]
        ):
            raise ExecutionRefusal("bridge mount closure replay-gate identity/role drifted")
        seen_mounts.add(replay_mount_id)
        for key in (
            "pre_evaluation_journal_sha256", "post_evaluation_journal_sha256",
            "pre_evaluation_routing_payload_sha256", "post_evaluation_routing_payload_sha256",
        ):
            _hex(replay[key], f"bridge mount closure replay-gate {key}")
        mounts.append({"stream_id": stream_id, "arm": "RAW_EQUAL_BUDGET", **dict(replay)})
    if seen_streams != {"stream-0", "stream-1", "stream-2", "stream-3"} or len(
        seen_mounts
    ) != 16:
        raise ExecutionRefusal("bridge mount closure plan must name twelve scientific-arm mounts and four replay-gate mounts")
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
            raise ExecutionRefusal("bridge mounts root does not equal the observed scientific-arm and replay-gate mounts")
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
    for path in output_root.rglob("*"):
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
    # Canonical order is defined over the serialized receipt paths, not
    # pathlib's component-wise ordering (which differs at file/directory
    # prefix collisions such as ``assert.d.ts`` and ``assert/strict.d.ts``).
    entries.sort(key=lambda entry: entry["path"])
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
        or manifest["experiment_id"] != EXPERIMENT_ID
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


def _strict_utc_unix(value: object, label: str) -> int:
    """Parse the sole accepted GitHub timestamp spelling without local-time drift."""
    if not isinstance(value, str):
        raise ExecutionRefusal(f"{label} must be a UTC RFC3339 text value")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ExecutionRefusal(f"{label} must be exact UTC RFC3339 seconds") from error
    return int(parsed.timestamp())


def _validate_ci_v2_evidence(receipt: Mapping[str, Any], *, label: str) -> None:
    """Validate the non-selectable GitHub query/list evidence retained in v2."""
    head_sha = receipt["head_sha"]
    query = receipt["discovery_query"]
    expected_path = f"/repos/gj3447/HSWM/actions/workflows/ci.yml/runs?event=push&branch=main&head_sha={head_sha}&per_page=100&page=1"
    if query != {"request_path": expected_path, "workflow_path": ".github/workflows/ci.yml", "event": "push", "branch": "main", "head_sha": head_sha, "per_page": 100, "page": 1}:
        raise ExecutionRefusal(f"{label} discovery query drifted")
    digest = receipt["raw_list_response_sha256"]
    if not isinstance(receipt["raw_list_response_utf8"], str) or _sha_bytes(receipt["raw_list_response_utf8"].encode("utf-8")) != digest:
        raise ExecutionRefusal(f"{label} raw workflow-runs list bytes do not match pinned digest")
    listed = _json_object_unformatted(receipt["raw_list_response_utf8"], f"{label} raw workflow-runs list")
    rows = listed.get("workflow_runs")
    if listed.get("total_count") != 1 or not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ExecutionRefusal(f"{label} workflow-runs list does not prove uniqueness")
    api = _json_object_unformatted(receipt["raw_response_utf8"], f"{label} raw API response")
    fields = ("id", "workflow_id", "run_number", "name", "path", "event", "head_branch", "head_sha", "run_attempt", "status", "conclusion", "created_at", "run_started_at", "updated_at", "pull_requests")
    def projection(value: Mapping[str, Any]) -> dict[str, Any]:
        head, repo, head_repo = value.get("head_commit"), value.get("repository"), value.get("head_repository")
        if not isinstance(head, dict) or not isinstance(repo, dict) or not isinstance(head_repo, dict):
            raise ExecutionRefusal(f"{label} CI projection lacks head/repository identity")
        return {**{field: value.get(field) for field in fields}, "head_commit": {"id": head.get("id"), "tree_id": head.get("tree_id")}, "repository": {"id": repo.get("id"), "full_name": repo.get("full_name")}, "head_repository": {"id": head_repo.get("id"), "full_name": head_repo.get("full_name")}}
    selected, listed_projection = projection(api), projection(rows[0])
    if selected != receipt["critical_projection"] or listed_projection != selected:
        raise ExecutionRefusal(f"{label} selected/listed CI critical projection drifted")
    if (selected["id"] != receipt["run_id"] or type(selected["workflow_id"]) is not int or selected["workflow_id"] <= 0 or type(selected["run_number"]) is not int or selected["run_number"] <= 0 or selected["name"] != "CI" or selected["path"] != ".github/workflows/ci.yml" or selected["event"] != "push" or selected["head_branch"] != "main" or selected["head_sha"] != head_sha or selected["run_attempt"] != 1 or selected["status"] != "completed" or selected["conclusion"] != "success" or selected["pull_requests"] != [] or selected["repository"] != selected["head_repository"] or selected["repository"].get("full_name") != "gj3447/HSWM" or type(selected["repository"].get("id")) is not int or selected["repository"]["id"] <= 0 or selected["head_commit"].get("id") != head_sha):
        raise ExecutionRefusal(f"{label} is not an eligible unique first-attempt CI run")
    created = _strict_utc_unix(selected["created_at"], f"{label}.created_at")
    started = _strict_utc_unix(selected["run_started_at"], f"{label}.run_started_at")
    updated = _strict_utc_unix(selected["updated_at"], f"{label}.updated_at")
    if not created <= started <= updated:
        raise ExecutionRefusal(f"{label} timestamps not ordered")


def _load_preregistration_ci_receipt(
    config: ExecutionConfig, dependencies: ExecutionDependencies
) -> tuple[dict[str, Any], bytes]:
    receipt, raw = _load_attested_receipt(
        path=config.preregistration_ci_receipt_path,
        digest=config.preregistration_ci_receipt_sha256,
        schema=PREREGISTRATION_B_CI_RECEIPT_SCHEMA,
        expected_keys={
            "schema_version",
            "provider",
            "run_id",
            "head_sha",
            "head_tree_oid",
            "preregistration_path",
            "preregistration_sha256",
            "preregistration_git_blob_oid",
            "status",
            "conclusion",
            "completed_at_utc",
            "completed_at_unix",
            "raw_response_sha256",
            "raw_response_utf8",
            "discovery_query",
            "critical_projection",
            "raw_list_response_sha256",
            "raw_list_response_utf8",
            "receipt_sha256",
        },
        label="preregistration B CI receipt",
    )
    for key in ("head_sha", "head_tree_oid", "preregistration_git_blob_oid"):
        _hex(receipt[key], f"preregistration B CI receipt.{key}", length=40)
    for key in ("preregistration_sha256", "raw_response_sha256"):
        _hex(receipt[key], f"preregistration B CI receipt.{key}")
    if (
        receipt["provider"] != "GITHUB_ACTIONS"
        or type(receipt["run_id"]) is not int or receipt["run_id"] <= 0
        or receipt["head_sha"] != config.prereg_b_commit
        or receipt["head_tree_oid"] != config.prereg_b_tree
        or receipt["preregistration_path"] != config.prereg_path
        or receipt["preregistration_sha256"] != config.prereg_sha256
        or receipt["status"] != "completed"
        or receipt["conclusion"] != "success"
        or type(receipt["completed_at_unix"]) is not int
        or receipt["completed_at_unix"] <= 0
        or receipt["completed_at_unix"] != config.preregistration_ci_completed_unix
    ):
        raise ExecutionRefusal("preregistration B CI receipt identity/status/completion drifted")
    _validate_ci_v2_evidence(receipt, label="preregistration B CI receipt")
    if _strict_utc_unix(receipt["completed_at_utc"], "preregistration B CI receipt.completed_at_utc") != receipt["completed_at_unix"]:
        raise ExecutionRefusal("preregistration B CI receipt UTC completion time drifted")
    if (
        not isinstance(receipt["raw_response_utf8"], str)
        or _sha_bytes(receipt["raw_response_utf8"].encode("utf-8")) != receipt["raw_response_sha256"]
    ):
        raise ExecutionRefusal("preregistration B CI raw response bytes do not match the pinned digest")
    raw_api = _json_object_unformatted(receipt["raw_response_utf8"], "preregistration B CI raw API response")
    head_commit = raw_api.get("head_commit")
    if (
        raw_api.get("id") != receipt["run_id"]
        or raw_api.get("head_sha") != receipt["head_sha"]
        or raw_api.get("status") != receipt["status"]
        or raw_api.get("conclusion") != receipt["conclusion"]
        or raw_api.get("updated_at") != receipt["completed_at_utc"]
        or not isinstance(head_commit, dict)
        or head_commit.get("id") != receipt["head_sha"]
        or head_commit.get("tree_id") != receipt["head_tree_oid"]
    ):
        raise ExecutionRefusal("preregistration B CI raw API response does not attest frozen run/head/tree/completion")
    b_tree = _git(config, dependencies, "rev-parse", f"{config.prereg_b_commit}^{{tree}}").strip()
    if b_tree != config.prereg_b_tree:
        raise ExecutionRefusal("local preregistration B tree differs from config")
    tree_objects: dict[str, bytes] = {}
    blob_oid = _git_tree_path_blob(
        config, dependencies, root_tree_oid=b_tree, relative_path=config.prereg_path,
        tree_objects=tree_objects,
    )
    prereg_bytes = _plain_relative_file(config.repo_root, config.prereg_path, "preregistration").read_bytes()
    if (
        blob_oid != receipt["preregistration_git_blob_oid"]
        or _git_object_sha1("blob", prereg_bytes) != blob_oid
        or _sha_bytes(prereg_bytes) != receipt["preregistration_sha256"]
    ):
        raise ExecutionRefusal("preregistration B CI receipt local Git tree/blob binding drifted")
    return receipt, raw


def _load_source_ci_receipt(
    config: ExecutionConfig,
) -> tuple[dict[str, Any], bytes, int]:
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
            "discovery_query",
            "critical_projection",
            "raw_list_response_sha256",
            "raw_list_response_utf8",
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
    _validate_ci_v2_evidence(receipt, label="source CI receipt")
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
    head_commit = raw_api.get("head_commit")
    completed_at = _strict_utc_unix(
        raw_api.get("updated_at"), "source CI raw API response.updated_at"
    )
    if (
        raw_api.get("id") != receipt["run_id"]
        or raw_api.get("head_sha") != receipt["head_sha"]
        or raw_api.get("status") != "completed"
        or raw_api.get("conclusion") != receipt["conclusion"]
        or not isinstance(head_commit, dict)
        or head_commit.get("id") != config.source_a_commit
        or head_commit.get("tree_id") != config.source_a_tree
        or completed_at < config.source_freeze_unix
    ):
        raise ExecutionRefusal(
            "source CI raw API response does not attest completed run/head/tree/chronology"
        )
    return receipt, raw, completed_at


def _load_structured_output_qualification(
    config: ExecutionConfig,
    *,
    source_manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes, frozenset[str]]:
    """Load only the bounded, non-scientific output-format qualification.

    The raw provider bodies were deliberately not retained.  This receipt is
    an operational qualification and supplies no experiment outcome.
    """
    path, digest = (
        config.structured_output_qualification_path,
        config.structured_output_qualification_sha256,
    )
    if path is None or digest is None:
        raise ExecutionRefusal("structured-output qualification path and SHA-256 pin are required")
    _hex(digest, "structured-output qualification SHA-256")
    raw = path.read_bytes()
    if _sha_bytes(raw) != digest:
        raise ExecutionRefusal("structured-output qualification content hash drifted")
    # This external operator receipt deliberately uses canonical JSONL-style
    # encoding: one canonical object followed by exactly one LF.  Preserve
    # and hash those original bytes, but parse only its canonical object.
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise ExecutionRefusal("structured-output qualification must be one canonical JSON object followed by LF")
    value = _strict_json_bytes(raw[:-1], "structured-output qualification")
    required = {
        "schema_version", "domain", "event_schema", "experiment_occurrence",
        "future_seed_material_used", "record_role", "raw_full_stdout_record_persisted",
        "retry_count", "max_output_tokens", "model_endpoint", "served_model_id",
        "vllm_version", "provider_cache_independence", "calls", "started_at_unix_ns",
        "ended_at_unix_ns", "source_files", "python_executable_sha256",
        "python_version", "unicode_data_version",
    }
    data = _exact_keys(value, required, "structured-output qualification")
    if (
        data["schema_version"] != STRUCTURED_OUTPUT_QUALIFICATION_SCHEMA
        or data["domain"] != STRUCTURED_OUTPUT_QUALIFICATION_DOMAIN
        or data["event_schema"] != "hswm-dnrd-live-model-event/v3"
        or data["experiment_occurrence"] is not False
        or data["future_seed_material_used"] is not False
        or data["record_role"] != STRUCTURED_OUTPUT_QUALIFICATION_RECORD_ROLE
        or data["raw_full_stdout_record_persisted"] is not False
        or type(data["retry_count"]) is not int
        or data["retry_count"] != 0
        or type(data["max_output_tokens"]) is not int
        or data["max_output_tokens"] != MAX_OUTPUT_TOKENS
        or data["model_endpoint"] != config.model_endpoint
        or data["served_model_id"] != MODEL_ID
        or data["vllm_version"] != VLLM_VERSION
        or data["provider_cache_independence"] != PROVIDER_CACHE_UNOBSERVABLE
        or type(data["calls"]) is not list or len(data["calls"]) != 3
    ):
        raise ExecutionRefusal("structured-output qualification does not bind the frozen non-scientific contract")
    if (
        type(data["started_at_unix_ns"]) is not int
        or type(data["ended_at_unix_ns"]) is not int
        or data["started_at_unix_ns"] <= 0
        or data["ended_at_unix_ns"] <= data["started_at_unix_ns"]
    ):
        raise ExecutionRefusal("structured-output qualification time interval is invalid")
    source_rows = source_manifest.get("files")
    if type(source_rows) is not list:
        raise ExecutionRefusal(
            "source manifest files are unavailable to qualification validation"
        )
    source_hashes = {
        row.get("path"): row.get("sha256")
        for row in source_rows
        if type(row) is dict
    }
    source_files = data["source_files"]
    if type(source_files) is not list or len(source_files) != len(QUALIFICATION_SOURCE_PATHS):
        raise ExecutionRefusal("structured-output qualification source-file closure drifted")
    for index, expected_path in enumerate(QUALIFICATION_SOURCE_PATHS):
        source_file = _exact_keys(
            source_files[index],
            {"path", "sha256"},
            f"structured-output qualification.source_files[{index}]",
        )
        if source_file["path"] != expected_path:
            raise ExecutionRefusal("structured-output qualification source-file order drifted")
        _hex(
            source_file["sha256"],
            f"structured-output qualification.source_files[{index}].sha256",
        )
        if source_file["sha256"] != source_hashes.get(expected_path):
            raise ExecutionRefusal(
                "structured-output qualification source identities do not match Source A"
            )
    _hex(
        data["python_executable_sha256"],
        "structured-output qualification Python executable SHA-256",
    )
    if (
        data["python_executable_sha256"] != config.python_executable_sha256
        or data["python_executable_sha256"] != OFFICIAL_PYTHON_EXECUTABLE_SHA256
        or data["python_version"] != config.python_version
        or data["python_version"] != OFFICIAL_PYTHON_VERSION
        or data["unicode_data_version"] != config.unicode_data_version
        or data["unicode_data_version"] != OFFICIAL_UNICODE_DATA_VERSION
    ):
        raise ExecutionRefusal(
            "structured-output qualification Python/Unicode runtime identities do not match frozen runtime"
        )
    tokens: set[str] = set()
    requested_candidate_indices: set[int] = set()
    expected_call = {
        "candidate_response_tokens", "completion_tokens", "dnrd_request_sha256",
        "dnrd_response_sha256", "finish_reason", "http_request_sha256", "http_status",
        "ordinal", "prompt_tokens", "raw_response_sha256", "requested_token",
        "response_format_schema_sha256", "returned_token",
    }
    for ordinal, call in enumerate(data["calls"], start=1):
        call = _exact_keys(call, expected_call, f"structured-output qualification.calls[{ordinal - 1}]")
        candidates = call["candidate_response_tokens"]
        if (
            type(call["ordinal"]) is not int or call["ordinal"] != ordinal
            or type(call["http_status"]) is not int or call["http_status"] != 200
            or call["finish_reason"] != "stop" or type(candidates) is not list
            or len(candidates) != 2 or candidates != sorted(candidates)
            or len(set(candidates)) != 2 or call["requested_token"] not in candidates
            or call["returned_token"] != call["requested_token"]
            or type(call["prompt_tokens"]) is not int or call["prompt_tokens"] < 0
            or type(call["completion_tokens"]) is not int
            or not 0 < call["completion_tokens"] <= MAX_OUTPUT_TOKENS
        ):
            raise ExecutionRefusal("structured-output qualification call contract drifted")
        for token in candidates:
            if not isinstance(token, str) or re.fullmatch(r"token-[0-9a-f]{20}", token) is None:
                raise ExecutionRefusal("structured-output qualification token form drifted")
            tokens.add(token)
        for key in ("dnrd_request_sha256", "dnrd_response_sha256", "http_request_sha256", "raw_response_sha256", "response_format_schema_sha256"):
            _hex(call[key], f"structured-output qualification {key}")
        expected_schema = {
            "type": "object",
            "properties": {
                "response_token": {
                    "type": "string",
                    "enum": candidates,
                    "pattern": r"^token-[0-9a-f]{20}$",
                    "minLength": 26,
                    "maxLength": 26,
                }
            },
            "required": ["response_token"],
            "additionalProperties": False,
        }
        if call["response_format_schema_sha256"] != commitment(expected_schema):
            raise ExecutionRefusal("structured-output qualification response schema digest drifted")
        requested_candidate_indices.add(candidates.index(call["requested_token"]))
    if len(tokens) != 6:
        raise ExecutionRefusal("structured-output qualification must contain six disjoint candidate tokens")
    if requested_candidate_indices != {0, 1}:
        raise ExecutionRefusal("structured-output qualification must exercise both candidate enum positions")
    return dict(data), raw, frozenset(tokens)


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
        "preregistration_b_ci_gate",
        "source_a_ci",
        "runtime_bindings",
    }
    data = _exact_keys(prereg, required, "preregistration")
    if (
        data["schema_version"] != PREREG_SCHEMA
        or data["experiment_id"] != EXPERIMENT_ID
        or data["protocol_version"] != PROTOCOL_VERSION
        or data["status"] != "FROZEN_AWAITING_SUCCESSFUL_PREREGISTRATION_B_CI_AND_FUTURE_PULSE"
    ):
        raise ExecutionRefusal("preregistration identity/status is not the frozen B-CI contract")
    _frozen_date(data["created_at"], "preregistration.created_at")
    authority = _exact_keys(
        data["authority"],
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
        raise ExecutionRefusal("preregistration authority does not preserve B-CI chronology gating")
    preregistration_b_ci_gate = _exact_keys(
        data["preregistration_b_ci_gate"],
        {"receipt_schema", "provider", "status", "conclusion", "minimum_lead_seconds", "selection_rule"},
        "preregistration.preregistration_b_ci_gate",
    )
    if (
        preregistration_b_ci_gate["receipt_schema"] != PREREGISTRATION_B_CI_RECEIPT_SCHEMA
        or preregistration_b_ci_gate["provider"] != "GITHUB_ACTIONS"
        or preregistration_b_ci_gate["status"] != "completed"
        or preregistration_b_ci_gate["conclusion"] != "success"
        or type(preregistration_b_ci_gate["minimum_lead_seconds"]) is not int
        or preregistration_b_ci_gate["minimum_lead_seconds"] != 900
        or preregistration_b_ci_gate["selection_rule"] != "EXACT_UNFILTERED_PUSH_MAIN_HEAD_SHA_WORKFLOW_LIST_TOTAL_COUNT_ONE_FIRST_ATTEMPT"
    ):
        raise ExecutionRefusal("preregistration does not freeze the B-CI receipt chronology gate")
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
            "structured_output_qualification_sha256",
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
        or runtime["structured_output_qualification_sha256"]
        != config.structured_output_qualification_sha256
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
        testbed["family"] != "REPEATED_CONTEXT_TABULAR_ROUTING_MECHANICS_V2"
        or testbed["development_streams"] != 4
        or testbed["training_calls_per_stream_maximum"] != 8
        or testbed["paired_heldout_probes_per_stream"] != 8
        or testbed["evaluation_arms"] != 3
        or testbed["evaluation_calls"] != 96
        or testbed["shared_learning_or_compiler_calls_maximum"] != 32
        or testbed["client_dispatched_generation_request_ceiling"] != 128
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
            "BINDING_DERANGED_NUMERIC_PLACEBO",
        },
        "preregistration.arms",
    )
    parity = _exact_keys(
        data["parity_and_leakage"],
        {
            "same_served_model_id_and_chat_endpoint",
            "equal_client_dispatched_and_logical_requests",
            "equal_generation_limits_input_token_parity_not_claimed",
            "equal_candidate_evidence_universe",
            "all_active_payloads_within_byte_ceiling",
            "active_state_byte_ceiling",
            "full_fixed_rule_replay_numeric_payload_bytes_equal",
            "full_deranged_numeric_payload_byte_count_equal",
            "arm_labels_hidden_from_model",
            "fresh_process_recovery_observed",
            "distinct_arm_mount_ids",
            "evaluation_read_only_wrt_routing_observed",
            "pre_dispatch_readout_bound_before_model_response",
            "scorer_outcome_response_independent",
            "cache_hits_required",
            "private_route_binding_open_only_after_response_seal",
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
        "full_fixed_rule_replay_numeric_payload_bytes_equal",
        "full_deranged_numeric_payload_byte_count_equal",
        "arm_labels_hidden_from_model",
        "fresh_process_recovery_observed",
        "distinct_arm_mount_ids",
        "evaluation_read_only_wrt_routing_observed",
        "pre_dispatch_readout_bound_before_model_response",
        "scorer_outcome_response_independent",
        "private_route_binding_open_only_after_response_seal",
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
        or prereg_tree != config.prereg_b_tree
        or preregistration_time > config.preregistration_ci_completed_unix
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
            "blob_oid": prereg_blob_oid,
            "blob_sha256": _sha_bytes(prereg_blob),
        },
        "a_to_b_changed_paths": list(changed_paths),
        "tree_objects": [
            {"oid": oid, "raw_base64": base64.b64encode(raw).decode("ascii")}
            for oid, raw in sorted(tree_objects.items())
        ],
    }
    return {**unsigned, "receipt_sha256": commitment(unsigned)}


def _preflight_git(
    config: ExecutionConfig,
    dependencies: ExecutionDependencies,
    *,
    source_ci_completed_unix: int,
) -> tuple[int, dict[str, Any]]:
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
    if source_time != config.source_freeze_unix:
        raise ExecutionRefusal("source freeze timestamp must equal A")
    preregistration_time = int(
        _git(config, dependencies, "show", "-s", "--format=%ct", config.prereg_b_commit).strip()
    )
    if (
        preregistration_time < source_time
        or preregistration_time < source_ci_completed_unix
        or preregistration_time > config.preregistration_ci_completed_unix
    ):
        raise ExecutionRefusal(
            "B commit time must follow source-A CI and be no later than B-CI completion"
        )
    if _git(config, dependencies, "rev-parse", f"{config.prereg_b_commit}^{{tree}}").strip() != config.prereg_b_tree:
        raise ExecutionRefusal("B tree identity drifted")
    remote_head = _git(config, dependencies, "ls-remote", "--refs", "origin", "refs/heads/main").strip().split()
    if len(remote_head) != 2 or remote_head[0] != config.prereg_b_commit or remote_head[1] != "refs/heads/main":
        raise ExecutionRefusal("remote canonical main head is not exact preregistration B")
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
    rows: object, *, label: str, root: Path, required_prefix: str | None = None,
    require_bytes: bool = True,
) -> dict[str, str]:
    if type(rows) is not list or not rows:
        raise ExecutionRefusal(f"{label} must be a nonempty file list")
    values: dict[str, str] = {}
    for index, row in enumerate(rows):
        item = _exact_keys(row, {"path", "sha256", "bytes"} if require_bytes else {"path", "sha256"}, f"{label}[{index}]")
        path = _relative_path(item["path"], f"{label}[{index}].path")
        if required_prefix is not None and not path.startswith(f"{required_prefix}/"):
            raise ExecutionRefusal(f"{label} escapes its declared package root")
        _hex(item["sha256"], f"{label}[{index}].sha256")
        if require_bytes and (type(item["bytes"]) is not int or item["bytes"] < 0):
            raise ExecutionRefusal(f"{label}[{index}].bytes must be a nonnegative integer")
        if path in values:
            raise ExecutionRefusal(f"{label} repeats a file")
        target = _plain_relative_file(root, path, f"{label} file")
        if _hash_file(target) != item["sha256"] or (require_bytes and target.stat().st_size != item["bytes"]):
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
        provenance["source_inputs"], label="bridge runtime build source inputs", root=config.repo_root,
        require_bytes=False,
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


def _expected_attempt_registry_root(bridge_state_root: Path) -> Path:
    """Return the sole local registry location for a B-pinned bridge root."""
    return bridge_state_root.resolve().parent / "attempt-registry"


def _occurrence_id(
    config: ExecutionConfig,
    *,
    preregistration_ci_run_id: int,
    preregistration_ci_completed_unix: int,
    quicknet_chain_hash: str,
    quicknet_round: int,
    quicknet_randomness_hex: str,
    seed_hex: str,
) -> str:
    """Content-address the immutable semantics of one DNRD-4S1 occurrence.

    Receipt bytes and local paths deliberately do not participate: they are
    mandatory audit bindings, but changing their representation must not open
    a second marker for the same source/B-CI/Quicknet/seed occurrence.
    """
    if type(preregistration_ci_run_id) is not int or preregistration_ci_run_id <= 0:
        raise ExecutionRefusal("preregistration B CI run ID is malformed for occurrence identity")
    if type(preregistration_ci_completed_unix) is not int or preregistration_ci_completed_unix <= 0:
        raise ExecutionRefusal("preregistration B CI completion is malformed for occurrence identity")
    if type(quicknet_round) is not int or quicknet_round <= 0:
        raise ExecutionRefusal("Quicknet round is malformed for occurrence identity")
    for label, value in (
        ("Quicknet chain hash", quicknet_chain_hash),
        ("Quicknet randomness", quicknet_randomness_hex),
        ("future seed", seed_hex),
    ):
        _hex(value, label)
    return commitment({
        "experiment_id": EXPERIMENT_ID,
        "occurrence_schema": "hswm-dnrd-occurrence-id/v1",
        "source_commit": config.source_a_commit,
        "source_manifest_sha256": config.source_manifest_sha256,
        "source_tree_oid": config.source_a_tree,
        "preregistration_ci_completed_at_unix": preregistration_ci_completed_unix,
        "preregistration_ci_run_id": preregistration_ci_run_id,
        "preregistration_commit": config.prereg_b_commit,
        "preregistration_sha256": config.prereg_sha256,
        "preregistration_tree_oid": config.prereg_b_tree,
        "quicknet_chain_hash": quicknet_chain_hash,
        "quicknet_randomness_hex": quicknet_randomness_hex,
        "quicknet_round": quicknet_round,
        "seed_hex": seed_hex,
    })


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
        config.preregistration_ci_receipt_path,
        config.preregistration_ci_receipt_sha256,
        config.source_ci_receipt_path,
        config.source_ci_receipt_sha256,
        config.structured_output_qualification_path,
        config.structured_output_qualification_sha256,
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
    assert config.preregistration_ci_receipt_path is not None
    assert config.source_ci_receipt_path is not None
    assert config.structured_output_qualification_path is not None
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
    if config.attempt_registry_root.resolve() != _expected_attempt_registry_root(
        config.bridge_state_root
    ):
        raise ExecutionRefusal(
            "singleton attempt registry must be bridge-state parent/attempt-registry"
        )
    for label, path in (
        ("singleton attempt registry", config.attempt_registry_root),
        ("preregistration B CI receipt", config.preregistration_ci_receipt_path),
        ("source CI receipt", config.source_ci_receipt_path),
        ("structured-output qualification", config.structured_output_qualification_path),
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
    if config.tokenizer_preflight_prompt != TOKENIZER_PREFLIGHT_PROMPT:
        raise ExecutionRefusal("tokenizer preflight prompt differs from the frozen DNRD-4S1 structured-response probe")
    _assert_distinct_roots(config)
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
    preregistration_ci_run_id: int,
    preregistration_ci_completed_unix: int,
    quicknet_chain_hash: str,
    quicknet_round: int,
    quicknet_randomness_hex: str,
    seed_hex: str,
    pulse_receipt_sha256: str,
    runtime_receipt_sha256: str,
) -> dict[str, Any]:
    if config.attempt_registry_root is None:
        raise ExecutionRefusal("singleton attempt registry is required")
    _hex(pulse_receipt_sha256, "pulse receipt SHA-256")
    _hex(runtime_receipt_sha256, "runtime receipt SHA-256")
    occurrence_id = _occurrence_id(
        config,
        preregistration_ci_run_id=preregistration_ci_run_id,
        preregistration_ci_completed_unix=preregistration_ci_completed_unix,
        quicknet_chain_hash=quicknet_chain_hash,
        quicknet_round=quicknet_round,
        quicknet_randomness_hex=quicknet_randomness_hex,
        seed_hex=seed_hex,
    )
    unsigned = {
        "schema_version": ATTEMPT_LOCK_SCHEMA,
        "enforcement_scope": ATTEMPT_MARKER_SCOPE,
        "occurrence_id": occurrence_id,
        "source_commit": config.source_a_commit,
        "source_tree_oid": config.source_a_tree,
        "source_manifest_sha256": config.source_manifest_sha256,
        "preregistration_commit": config.prereg_b_commit,
        "preregistration_tree_oid": config.prereg_b_tree,
        "preregistration_sha256": config.prereg_sha256,
        "preregistration_ci_receipt_sha256": config.preregistration_ci_receipt_sha256,
        "pulse_receipt_sha256": pulse_receipt_sha256,
        "runtime_receipt_sha256": runtime_receipt_sha256,
        "terminal_intent_schema": TERMINAL_INTENT_SCHEMA,
        "terminal_artifact_relative_path": "terminal-intent.json",
    }
    lock = {**unsigned, "receipt_sha256": commitment(unsigned)}
    target = config.attempt_registry_root / f"{occurrence_id}.json"
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
        _fsync_directory(config.attempt_registry_root)
    except Exception:
        # Do not remove a possibly-visible marker: ambiguity must consume the
        # identity rather than permit a replacement attempt.
        raise
    return lock


def _post_dispatch_ledger_snapshot(output_root: Path) -> dict[str, Any]:
    """Bind retained ledgers for a non-scientific post-dispatch void terminal."""
    result: dict[str, Any] = {}
    for name, event_name, count_key in (
        ("model_events.jsonl", "CHAT_COMPLETION_ACCEPTED", "accepted_model_calls"),
        ("runner_events.jsonl", "COMPLETED_CALL", "runner_completed_calls"),
    ):
        path = output_root / name
        if not path.is_file():
            result[count_key] = 0
            result[f"{name[:-6]}_sha256"] = _sha_bytes(b"")
            continue
        raw = path.read_bytes()
        result[f"{name[:-6]}_sha256"] = _sha_bytes(raw)
        try:
            rows = [_strict_json_bytes(line, f"{name} terminal snapshot") for line in raw.splitlines()]
            result[count_key] = sum(row.get("event") == event_name for row in rows)
        except Exception:
            # The index/hash still preserve forensic bytes.  Do not invent a
            # successful count if a post-dispatch filesystem/ledger failure
            # made them unparsable.
            result[count_key] = 0
    return result


def _terminal_record(*, output_root: Path, post_first_call: bool, calls_completed: int, error: Exception) -> dict[str, Any]:
    """A conservative terminal, never a scientific judgment."""
    digest = commitment({"type": type(error).__name__, "message": str(error)})
    if post_first_call:
        # This is intentionally VOID rather than INCONCLUSIVE: an internal
        # finalization failure after accepted model calls is not a rejected
        # terminal model boundary.  It cannot be promoted into a partial
        # scientific occurrence.
        return {
            "schema_version": VOID_PROTOCOL_SCHEMA,
            "experiment_id": EXPERIMENT_ID, "post_first_call": True,
            "calls_observed": calls_completed,
            "failure_stage": "POST_DISPATCH_INTERNAL_FINALIZATION",
            "failure_type": type(error).__name__, "failure_digest": digest,
            **_post_dispatch_ledger_snapshot(output_root),
        }
    return {
        "schema_version": VOID_PROTOCOL_SCHEMA, "experiment_id": EXPERIMENT_ID,
        "post_first_call": False, "failure_type": type(error).__name__,
        "failure_digest": digest,
    }


def _runner_inconclusive_is_terminal_model_boundary(
    occurrence: Mapping[str, Any], model_events: Sequence[Mapping[str, Any]]
) -> bool:
    """Keep INCONCLUSIVE reserved for an observed terminal model failure."""
    if not model_events:
        return False
    last = model_events[-1]
    return last.get("event") in {
        "CHAT_COMPLETION_REJECTED",
        "AMBIGUOUS_OR_POST_DISPATCH_FAILURE",
        "TRANSPORT_RESPONSE_REJECTED",
    }


def _runner_post_dispatch_void(
    output_root: Path, occurrence: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": VOID_PROTOCOL_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "post_first_call": True,
        "calls_observed": occurrence["calls_completed"],
        "failure_stage": "POST_DISPATCH_INTERNAL_FINALIZATION",
        "failure_type": occurrence["failure_type"],
        "failure_digest": occurrence["failure_digest"],
        **_post_dispatch_ledger_snapshot(output_root),
    }


def _persist_terminal_if_possible(
    output_root: Path, *, post_first_call: bool, calls_completed: int = 0, error: Exception
) -> None:
    """Best-effort fail-closed record; never masks the triggering error."""
    try:
        if not output_root.exists():
            return
        terminal_exists = any(
            (output_root / terminal).exists()
            for terminal in ("candidate.json", "inconclusive.json", "void_protocol.json")
        )
        name = "void_protocol.json"
        if not terminal_exists and not (output_root / name).exists():
            _atomic_json(output_root / name, _terminal_record(
                output_root=output_root, post_first_call=post_first_call, calls_completed=calls_completed, error=error
            ))
        if not (output_root / "bundle_index.json").exists():
            _atomic_json(output_root / "bundle_index.json", _bundle_index(output_root))
    except Exception:
        # terminal-intent is written before any post-lock action and remains
        # the durable fail-closed pointer when this filesystem is unusable.
        pass


def _post_dispatch_progress(dependencies: ExecutionDependencies) -> tuple[bool, int]:
    """Use durable live-boundary observations, never runner bookkeeping."""
    try:
        # A production occurrence must derive this decision from the fsynced
        # ledger, rather than a mutable answerer/runner snapshot.  Test seams
        # without a ledger path retain the provider fallback solely because
        # they cannot exercise the production durable boundary.
        if dependencies.model_event_ledger_path is not None:
            path = dependencies.model_event_ledger_path
            if not path.exists():
                return False, 0
            _plain_file(path, "durable live model event ledger", mode=0o600)
            raw = path.read_bytes()
            if not raw:
                return False, 0
            if not raw.endswith(b"\n"):
                raise ExecutionRefusal(
                    "durable model event ledger lacks its terminal LF"
                )
            rows = raw[:-1].split(b"\n")
            if not rows or any(not row for row in rows):
                raise ExecutionRefusal(
                    "durable model event ledger contains an empty JSONL row"
                )
            events = tuple(
                _strict_json_bytes(line, "durable model event row")
                for line in rows
            )
        elif dependencies.model_event_ledger is not None:
            events = tuple(dependencies.model_event_ledger())
        else:
            return False, 0
        # Any durable live-boundary row is conservative post-dispatch evidence:
        # rejected/ambiguous transport outcomes cannot reopen a singleton.
        identities = {
            (event.get("ordinal"), event.get("dnrd_request_sha256"))
            for event in events
            if isinstance(event, Mapping)
            and isinstance(event.get("ordinal"), int)
            and isinstance(event.get("dnrd_request_sha256"), str)
        }
        return bool(events), max(1, len(identities)) if events else 0
    except Exception:
        # A failed reread after dispatch is conservatively post-call.
        present = dependencies.model_event_ledger_path is not None and dependencies.model_event_ledger_path.exists()
        return present, 1 if present else 0


def _post_lock_step(
    output_root: Path, dependencies: ExecutionDependencies, operation: Callable[[], Any]
) -> Any:
    """Apply the terminal guarantee to one post-lock operation."""
    try:
        return operation()
    except Exception as error:
        post_first_call, calls_completed = _post_dispatch_progress(dependencies)
        _persist_terminal_if_possible(output_root, post_first_call=post_first_call,
            calls_completed=calls_completed, error=error)
        raise


def _jsonl(events: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_json(dict(event)) + b"\n" for event in events)


def _fsync_directory(path: Path) -> None:
    """Durably order a just-created directory entry on a local Unix filesystem."""
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class _DurableJsonlEventLedger:
    """Append and fsync each live-model observation before control proceeds."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._events: list[Mapping[str, Any]] = []
        self._created = False

    def __call__(self, event: Mapping[str, Any]) -> None:
        value = dict(event)
        row = canonical_json(value) + b"\n"
        _plain_directory(
            self.path.parent, "live model event ledger parent", mode=0o700
        )
        flags = os.O_WRONLY
        if self._created:
            flags |= os.O_APPEND
        else:
            flags |= os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.path, flags, 0o600)
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise ExecutionRefusal(
                    "live model event ledger is not a plain owner-only file"
                )
            view = memoryview(row)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("live model event ledger write made no progress")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if not self._created:
            _fsync_directory(self.path.parent)
            self._created = True
        self._events.append(value)

    def snapshot(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(dict(event) for event in self._events)


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
    model_event_ledger = _DurableJsonlEventLedger(
        config.output_root / "model_events.jsonl"
    )
    transport = UrllibHttpTransport()
    live_config = OpenAICompatibleDnrdConfig(config.model_endpoint, api_key=api_key)
    answerer = OpenAICompatibleDnrdAnswerer(
        live_config, transport, event_sink=model_event_ledger
    )
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
        model_event_ledger=model_event_ledger.snapshot,
        closure_exporter=closure_exporter,
        model_event_ledger_path=model_event_ledger.path,
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
    source_ci_receipt, source_ci_bytes, source_ci_completed_unix = (
        _load_source_ci_receipt(config)
    )
    source_manifest = _load_source_manifest(config)
    qualification, qualification_bytes, qualification_tokens = (
        _load_structured_output_qualification(
            config, source_manifest=source_manifest
        )
    )
    runtime_tree_manifest = _runtime_tree_manifest(config)
    preregistration = _validate_preregistration(config, source_ci_receipt=source_ci_receipt)
    if dependencies is None:
        dependencies = _production_dependencies(config)
    preregistration_ci_receipt, preregistration_ci_bytes = _load_preregistration_ci_receipt(
        config, dependencies
    )
    source_time, git_chronology_evidence = _preflight_git(
        config,
        dependencies,
        source_ci_completed_unix=source_ci_completed_unix,
    )
    if config.output_root.exists():
        raise ExecutionRefusal("output root must be a new dedicated path")
    if dependencies.model_event_ledger is None:
        raise ExecutionRefusal("execution requires the actual live answerer event ledger")
    if (
        dependencies.model_event_ledger_path is not None
        and dependencies.model_event_ledger_path
        != config.output_root / "model_events.jsonl"
    ):
        raise ExecutionRefusal(
            "durable live model event ledger path is outside the output root"
        )
    if dependencies.closure_exporter is None:
        raise ExecutionRefusal("execution requires the production/raw bridge mount-closure exporter")
    source_binding = SourceFreezeBinding(
        source_commit=config.source_a_commit,
        source_tree_oid=config.source_a_tree,
        source_manifest_sha256=config.source_manifest_sha256,
        preregistration_commit=config.prereg_b_commit,
        preregistration_tree_oid=config.prereg_b_tree,
        preregistration_blob_sha256=config.prereg_sha256,
        preregistration_ci_completed_unix=config.preregistration_ci_completed_unix,
        preregistration_ci_receipt_sha256=config.preregistration_ci_receipt_sha256 or "",
    )
    eligible_round = first_eligible_quicknet_round(
        source_freeze_unix=source_time,
        preregistration_ci_completed_unix=config.preregistration_ci_completed_unix,
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
        preregistration_ci_completed_unix=config.preregistration_ci_completed_unix,
        projection=projection,
        source_binding=source_binding,
    )
    # Consume this frozen occurrence before deriving any test material or
    # entering the live boundary.  A later failure must not open a replacement
    # attempt merely by choosing another output directory.
    attempt_lock = _attempt_lock(
        config,
        preregistration_ci_run_id=preregistration_ci_receipt["run_id"],
        preregistration_ci_completed_unix=preregistration_ci_receipt["completed_at_unix"],
        quicknet_chain_hash=projection.chain_hash,
        quicknet_round=projection.round,
        quicknet_randomness_hex=projection.randomness_hex,
        seed_hex=pulse.seed_hex,
        pulse_receipt_sha256=pulse.receipt_sha256,
        runtime_receipt_sha256=runtime_receipt["receipt_sha256"],
    )
    # Establish a durable owner-only terminal pointer before any post-lock
    # materialization or provider request.  If the output filesystem later
    # fails completely, the immutable attempt marker still declares that this
    # consumed occurrence has no retry/resume path.
    try:
        config.output_root.mkdir(mode=0o700, parents=False)
        os.chmod(config.output_root, 0o700)
        _fsync_directory(config.output_root.parent)
        _atomic_json(config.output_root / "terminal-intent.json", {
            "schema_version": TERMINAL_INTENT_SCHEMA,
            "experiment_id": EXPERIMENT_ID,
            "attempt_lock_receipt_sha256": attempt_lock["receipt_sha256"],
            "terminal_artifact_paths": ["candidate.json", "inconclusive.json", "void_protocol.json"],
            "no_retry_or_resume": True,
        })
    except Exception as error:
        # The immutable attempt marker already consumes this identity.  If the
        # output directory exists and remains usable, also retain the strongest
        # possible pre-dispatch terminal/index; otherwise the marker is the
        # final durable no-retry record.
        _persist_terminal_if_possible(
            config.output_root,
            post_first_call=False,
            calls_completed=0,
            error=error,
        )
        raise
    # From this point forward the occurrence is consumed *and* has a durable
    # terminal pointer.  Every post-lock operation goes through this small
    # guard; do not add an unguarded write/validation/copy below it.
    def post_lock(operation: Callable[[], Any]) -> Any:
        return _post_lock_step(config.output_root, dependencies, operation)

    public, private = post_lock(lambda: generate_manifests(bytes.fromhex(pulse.seed_hex)))
    fixture_bytes = post_lock(lambda: canonical_json({"public": public, "private": private}))
    def validate_fixture() -> None:
        if any(token.encode("ascii") in fixture_bytes for token in qualification_tokens):
            raise ExecutionRefusal("future-seeded DNRD fixture overlaps structured-output qualification candidate tokens")
        tracked = [item for item in _git(config, dependencies, "ls-files").splitlines() if item]
        _generated_overlap(config.repo_root, public, tracked)
    post_lock(validate_fixture)
    assert config.tokenizer_preflight_prompt is not None
    deployment = post_lock(lambda: _deployment_receipt(
        dependencies.live_preflight(config), config.model_endpoint,
        tokenizer_prompt=config.tokenizer_preflight_prompt,
    ))

    private_dir = config.output_root / "private"
    post_lock(lambda: private_dir.mkdir(mode=0o700))
    post_lock(lambda: _atomic_bytes(
        config.output_root / "source_manifest.json",
        _plain_relative_file(config.repo_root, config.source_manifest_path, "source manifest").read_bytes(),
    ))
    post_lock(lambda: _copy_source_closure(config.output_root, config.repo_root, source_manifest))
    post_lock(lambda: _atomic_bytes(
        config.output_root / "preregistration.json",
        _plain_relative_file(config.repo_root, config.prereg_path, "preregistration").read_bytes(),
    ))
    post_lock(lambda: _atomic_bytes(config.output_root / "source_ci_receipt.json", source_ci_bytes))
    post_lock(lambda: _atomic_bytes(
        config.output_root / "preregistration_ci_receipt.json", preregistration_ci_bytes
    ))
    post_lock(lambda: _atomic_json(config.output_root / "git_chronology_evidence.json", git_chronology_evidence))
    post_lock(lambda: _atomic_json(config.output_root / "public_manifest.json", public))
    post_lock(lambda: _atomic_json(private_dir / "private_manifest.json", private, 0o600))
    post_lock(lambda: _atomic_bytes(config.output_root / "pulse_verifier_receipt.json", verifier_bytes))
    post_lock(lambda: _atomic_json(config.output_root / "pulse_binding.json", pulse.canonical()))
    post_lock(lambda: _atomic_json(config.output_root / "deployment_receipt.json", deployment))
    post_lock(lambda: _atomic_bytes(
        config.output_root / "structured_output_qualification.json",
        qualification_bytes,
        0o400,
    ))
    post_lock(lambda: _atomic_json(config.output_root / "runtime_receipt.json", runtime_receipt))
    post_lock(lambda: _atomic_bytes(
        config.output_root / VERIFIER_RUNTIME_BUNDLE_EVIDENCE_PATH,
        verifier_runtime_bundle_bytes,
        0o400,
    ))
    assert config.bridge_runtime_tree_manifest_path is not None
    assert config.bridge_runtime_root is not None
    post_lock(lambda: _atomic_bytes(
        config.output_root / "bridge_runtime_tree_manifest.json",
        config.bridge_runtime_tree_manifest_path.read_bytes(),
        0o400,
    ))
    post_lock(lambda: _copy_runtime_closure(
        config.output_root, config.bridge_runtime_root, runtime_tree_manifest
    ))
    post_lock(lambda: _atomic_json(config.output_root / "attempt_lock_receipt.json", attempt_lock))
    readback = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in asdict(config).items()
    }
    post_lock(lambda: _atomic_json(config.output_root / "config_readback.json", readback))

    runner_event_ledger = post_lock(lambda: _DurableJsonlEventLedger(
        config.output_root / "runner_events.jsonl"
    ))

    def sink(event: Mapping[str, Any]) -> None:
        runner_event_ledger(event)

    bindings = post_lock(lambda: {
        "source_manifest_sha256": config.source_manifest_sha256,
        "preregistration_sha256": config.prereg_sha256,
        "preregistration_ci_receipt_sha256": config.preregistration_ci_receipt_sha256,
        "pulse_receipt_sha256": pulse.receipt_sha256,
        "split_manifest_sha256": commitment(public),
        "model_deployment_sha256": commitment(deployment),
        "scorer_sha256": config.scorer_implementation_sha256,
        "runtime_receipt_sha256": runtime_receipt["receipt_sha256"],
        "git_chronology_evidence_sha256": _sha_bytes(
            (config.output_root / "git_chronology_evidence.json").read_bytes()
        ),
    })
    metadata = post_lock(lambda: MeasurementMetadata(
        bindings=bindings,
        chronology={
            "source_commit": config.source_a_commit,
            "preregistration_commit": config.prereg_b_commit,
            "source_tree_oid": config.source_a_tree,
            "preregistration_tree_oid": config.prereg_b_tree,
            "source_frozen_at_unix": source_time,
            "source_ci_completed_at_unix": source_ci_completed_unix,
            "preregistration_committed_at_unix": git_chronology_evidence["preregistration"]["commit_time_unix"],
            "preregistration_ci_completed_at_unix": config.preregistration_ci_completed_unix,
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
    ))
    result = post_lock(lambda: run_diagnostic(
            public,
            private_manifest_commitment=public["private_manifest_commitment"],
            answerer=dependencies.answerer,
            bridge=dependencies.bridge,
            scorer=dependencies.scorer,
            metadata=metadata,
            event_sink=sink,
            model_event_ledger_provider=dependencies.model_event_ledger,
            closure_exporter=dependencies.closure_exporter,
    ))
    model_events = post_lock(lambda: tuple(dict(event) for event in dependencies.model_event_ledger()))
    runner_events = post_lock(lambda: tuple(dict(event) for event in runner_event_ledger.snapshot()))
    runner_bytes, model_bytes = post_lock(
        lambda: (_jsonl(runner_events), _jsonl(model_events))
    )
    runner_event_path = config.output_root / "runner_events.jsonl"
    def validate_runner_ledger() -> None:
        _plain_file(runner_event_path, "durable runner event ledger", mode=0o600)
        if runner_event_path.read_bytes() != runner_bytes:
            raise RuntimeError("durable runner event ledger differs from in-memory event sequence")
    post_lock(validate_runner_ledger)
    model_event_path = config.output_root / "model_events.jsonl"
    if dependencies.model_event_ledger_path is None:
        post_lock(lambda: _atomic_bytes(model_event_path, model_bytes))
    else:
        def validate_model_ledger() -> None:
            _plain_file(
                model_event_path, "durable live model event ledger", mode=0o600
            )
            retained_model_bytes = model_event_path.read_bytes()
            if retained_model_bytes != model_bytes:
                raise RuntimeError("durable live model event ledger differs from in-memory event sequence")
        post_lock(validate_model_ledger)
    runner_digest = _sha_bytes(runner_bytes)
    model_digest = _sha_bytes(model_bytes)
    if result.candidate is not None:
        def validate_candidate_bindings() -> None:
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
        post_lock(validate_candidate_bindings)
        post_lock(lambda: _atomic_json(config.output_root / "bridge_state_evidence.json", result.bridge_state_evidence))
        def validate_candidate_artifacts() -> None:
            if _sha_bytes((config.output_root / "bridge_state_evidence.json").read_bytes()) != result.bridge_state_evidence_sha256:
                raise RuntimeError("bridge state evidence bytes differ from runner-bound receipt")
            closure_manifest = config.output_root / "bridge_mount_closure.json"
            if (
                not closure_manifest.is_file()
                or _sha_bytes(closure_manifest.read_bytes())
                != result.bridge_mount_closure_sha256
            ):
                raise RuntimeError("bridge mount closure bytes differ from runner-bound receipt")
        post_lock(validate_candidate_artifacts)
        post_lock(lambda: _atomic_json(config.output_root / "candidate.json", result.candidate))
    elif result.inconclusive_occurrence is not None:
        if _runner_inconclusive_is_terminal_model_boundary(
            result.inconclusive_occurrence, model_events
        ):
            post_lock(lambda: _atomic_json(config.output_root / "inconclusive.json", result.inconclusive_occurrence))
        else:
            post_lock(lambda: _atomic_json(
                config.output_root / "void_protocol.json",
                _runner_post_dispatch_void(config.output_root, result.inconclusive_occurrence),
            ))
    else:
        post_lock(lambda: (_ for _ in ()).throw(RuntimeError("runner returned neither candidate nor inconclusive occurrence")))
    post_lock(lambda: _atomic_json(config.output_root / "bundle_index.json", _bundle_index(config.output_root)))
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
        "prereg_b_tree",
        "prereg_path",
        "prereg_sha256",
        "source_freeze_unix",
        "preregistration_ci_completed_unix",
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
        "preregistration_ci_receipt_path",
        "preregistration_ci_receipt_sha256",
        "source_ci_receipt_path",
        "source_ci_receipt_sha256",
        "structured_output_qualification_path",
        "structured_output_qualification_sha256",
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
        "preregistration_ci_receipt_path",
        "source_ci_receipt_path",
        "structured_output_qualification_path",
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


if __name__ == "__main__":
    raise SystemExit(main())
