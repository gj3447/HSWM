"""Sealed, local-only no-learning calibration for the ALFWorld text adapter.

The runner executes one prospectively selected 8-train/4-valid-seen prefix. It
owns no memory, learning, revision, evaluator, or model-service policy. Raw
selected identities, visible transcripts, actions, and local outcomes remain in
the private return value; the public return value contains aggregates only.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping, Protocol

from _research.dnrd5.canonical_json import canonical_bytes

from .alfworld_b0_actor import (
    B0_ACTION_MAX_BYTES,
    B0_ACTION_MAX_HISTORY_STEPS,
    B0_ACTION_MAX_INPUT_BYTES,
    B0_ACTION_MAX_OBSERVATION_BYTES,
    B0_ACTION_MAX_OUTPUT_TOKENS,
    B0_ACTION_MAX_REQUEST_BYTES,
    B0_ACTION_PROTOCOL,
    B0_ACTION_RECEIPT_SCHEMA,
    B0_ACTION_SYSTEM_MESSAGE,
    B0_MAX_COMPLETION_CALLS,
    B0_MAX_TOKENIZE_CALLS,
    _action_schema,
)
from .alfworld_b0_selection import OpaqueGameSelection
from .alfworld_b0_runtime import dgx_sandbox_contract, load_local_game_binding
from .alfworld_text_runtime import (
    MAX_PROTOCOL_LINE_BYTES,
    AlfworldTextRuntimeClosed,
    LocalAlfworldTextRuntime,
    LocalGameBinding,
    LocalSandboxSpec,
    action_line,
    decode_preframe_failure_exit_code,
    read_one_line,
    validate_actor_projection,
    validate_outcome_receipt,
)


PROTOCOL_SCHEMA = "hswm-alfworld-b0-calibration-protocol/v1"
PRIVATE_SELECTION_SCHEMA = "hswm-alfworld-b0-selection-private-receipt/v1"
PRIVATE_RUN_SCHEMA = "hswm-alfworld-b0-calibration-private-run/v1"
PUBLIC_RUN_SCHEMA = "hswm-alfworld-b0-calibration-public-aggregate/v1"
COMPLETE_STATUS = "EXPLORATORY_B0_CALIBRATION_COMPLETE_G0_NOT_PASSED"
INCONCLUSIVE_STATUS = "INCONCLUSIVE_MEASUREMENT_NOT_READY"
VOID_STATUS = "VOID_PROTOCOL_OR_EVIDENCE_BINDING_BREACH"
TRAIN_EPISODES = 8
VALID_SEEN_EPISODES = 4
SCHEDULED_EPISODES = TRAIN_EPISODES + VALID_SEEN_EPISODES
COMPLETION_TIMEOUT_SECONDS = 120
MAX_OCCURRENCE_WALL_SECONDS = 36_000
DGX_RUNTIME_QUALIFICATION = {
    "path": "manifests/HSWM_ALFWORLD_TEXT_RUNTIME_DGX_QUALIFICATION_2026-08-30.json",
    "file_sha256": "a641218babb759159714f02fd539cf508997991f9469731788353941fb98595d",
    "receipt_sha256": "1723986c3203add3cac0fe121b3cf110830c49e9873cccd737cef95a43b01422",
    "status": "ENGINEERING_INSTRUMENT_QUALIFIED_DGX_ARM64_G0_NOT_PASSED",
    "evidence_commit": "dd395b7cbacf7b5204453043ce67ef8b17db52d6",
}
VLLM_METRICS_QUALIFICATION = {
    "path": "manifests/HSWM_ALFWORLD_B0_VLLM_METRICS_QUALIFICATION_2026-08-30.json",
    "file_sha256": "5a3e2ddfae77d37e1e858ebc42267b76a61805dc3dc4fcce92ec2fd706464b12",
    "receipt_sha256": "a1d40c17ad3b38f2d84f864821a50b91c0285c04b98af966c4effe4ceb05d4ca",
    "private_receipt_file_sha256": "94971d57e8f69410a4398f3f5f8cc622c88fabd8df9a6c40b0eb6c46a1f95a60",
    "status": "ENGINEERING_VLLM_METRICS_SEMANTICS_QUALIFIED_B0_NOT_RUN",
    "evidence_commit": "a45ef8fcc3be878deab3778f5dde935778276b2e",
    "probe_predecessor_protocol_sha256": "f754cb5fb6db2b97fa1b1a2055946f7dc63ce7c754909eec894e1848d07bc548",
}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_OPAQUE_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")
_FORBIDDEN_PUBLIC = (
    "opaque_uid",
    "task_group_uid",
    "relative_path",
    "observation",
    "actor_receipt",
    "private_terminal_receipt",
)


class AlfworldB0CalibrationError(RuntimeError):
    """The sealed B0 occurrence could not continue without changing its design."""


@dataclass(frozen=True, slots=True)
class VerifiedB0Protocol:
    """Exact executable subset of the prospective checked-in protocol."""

    uid: str
    version: str
    max_steps: int
    max_completions: int
    max_tokenizations: int
    completion_timeout_seconds: int
    max_wall_seconds: int
    served_model: str
    binding_sha256: str


class FrameReader(Protocol):
    def __call__(self, stream: Any, *, timeout_seconds: float, label: str) -> bytes: ...


class SandboxSpecFactory(Protocol):
    def __call__(
        self,
        selection: OpaqueGameSelection,
        binding: LocalGameBinding,
        game_file: Path,
        pool_manifest_sha256: str,
        local_locator_sha256: str,
        protocol: VerifiedB0Protocol,
    ) -> LocalSandboxSpec: ...


class RuntimeLauncher(Protocol):
    def __call__(self, spec: LocalSandboxSpec) -> Any: ...


def _sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise AlfworldB0CalibrationError(f"{label} must be a lowercase SHA-256")
    return value


def _read_mapping(
    value: Mapping[str, object] | Path, label: str
) -> tuple[dict[str, object], str]:
    if isinstance(value, Path):
        if not value.is_absolute() or not value.is_file() or value.is_symlink():
            raise AlfworldB0CalibrationError(
                f"{label} path must be an absolute non-symlink regular file"
            )
        try:
            raw = value.read_bytes()
            decoded = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AlfworldB0CalibrationError(f"{label} path is unreadable JSON") from error
        binding = sha256(raw).hexdigest()
    elif isinstance(value, Mapping):
        decoded = dict(value)
        try:
            rendered = json.dumps(
                decoded,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise AlfworldB0CalibrationError(f"{label} is not bounded JSON") from error
        binding = sha256(rendered).hexdigest()
    else:
        raise AlfworldB0CalibrationError(f"{label} must be a mapping or path")
    if not isinstance(decoded, dict):
        raise AlfworldB0CalibrationError(f"{label} must be a JSON object")
    return decoded, binding


def _exact_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AlfworldB0CalibrationError(f"{label} must be an exact object")
    return value


def verify_protocol(value: Mapping[str, object] | Path) -> VerifiedB0Protocol:
    """Fail closed unless every runtime-relevant preregistered field is exact."""

    raw, binding = _read_mapping(value, "protocol")
    if (
        raw.get("schema_version") != PROTOCOL_SCHEMA
        or raw.get("prospective_amendments")
        != [
            {
                "id": "ARM64_PDDL_ONLY_ENVIRONMENT_ADAPTER_AND_HASH_BOUND_RUNTIME_SPLIT",
                "superseded_protocol_file_sha256": "6d1f18f3ccc0e70ed8b4ba72a98462114fe647f26e7e19919fc3c1ecb072249d",
                "trigger": "A DGX package-install engineering attempt established that upstream TextWorld 1.7.0 invokes Inform7 setup and its official archive has no aarch64 compiler payload. The attempt stopped during dependency construction.",
                "change": "Preserve the historically qualified runtime bytes; move valid_unseen-opaque lookup into a B0-only source; install the exact official TextWorld 1.7.0 revision with an explicit PDDL-only build adapter that skips Inform7 setup and supplies no Inform7 capability.",
                "prospective_boundary": "NO_B0_SELECTION_NO_ALFWORLD_EPISODE_NO_MODEL_CALL_NO_OUTCOME_OBSERVED",
            },
            {
                "id": "DGX_TRUSTED_MAINTAINER_SUDO_BWRAP_NO_USERNS_ADAPTER",
                "superseded_protocol_file_sha256": "d4448317625a617e0e687bf0bd5bc108d49dc570bad44ed96b05dff5f5d054bc",
                "trigger": "Pre-B0 fixed-action engineering qualification reached the DGX sandbox launcher but stopped before its first actor frame. No B0 selection, model call, or B0 outcome occurred. Diagnostics established that the host AppArmor policy rejects the required unprivileged user namespace and that the exact privileged no-userns adapter can import ALFWorld, register the sealed game, construct the environment, and reset it.",
                "change": "Use a B0-only source-bound noninteractive sudo Bubblewrap adapter with explicit pid, ipc, uts, net, and best-effort cgroup namespaces; no user namespace; all capabilities dropped except CAP_DAC_READ_SEARCH; and a read-only /proc/controller-pid/fd/verified-fd game bind held by the controller through worker termination. Preserve the historical runtime implementation unchanged.",
                "prospective_boundary": "NO_B0_SELECTION_NO_MODEL_CALL_NO_B0_OUTCOME_OBSERVED_ENGINEERING_RESET_DIAGNOSTIC_ONLY",
            },
            {
                "id": "VLLM_METRICS_PUBLIC_PROJECTION_REPAIR_AFTER_NEUTRAL_PROBE",
                "superseded_protocol_file_sha256": "0519fc2820c3e00438958d51824c465805b22d4faeb01da636e986c83358848c",
                "trigger": "A pre-selection engineering probe issued exactly one neutral tokenize request and one tiny schema-constrained completion on a fresh service, then refused before writing either qualification receipt because its public leakage guard rejected the expected fixed ALFWorld source-path labels. Artifact packaging also rejected root-owned compile-cache bytes. No counter delta was inspected from the failed occurrence.",
                "change": "Permit the fixed committed ALFWorld source-path labels in the aggregate source binding while continuing to forbid task identities, episodes, games, selections, observations, outcomes, prompts, messages, content, and raw evidence. Place fresh container caches in the runner cache tree rather than published outputs and repeat under a new occurrence identifier.",
                "prospective_boundary": "NO_B0_SELECTION_NO_ALFWORLD_EPISODE_NO_TASK_OUTCOME_ONE_NEUTRAL_TOKENIZE_AND_ONE_NEUTRAL_COMPLETION_OCCURRED_NO_METRIC_DELTA_INSPECTED",
            },
            {
                "id": "DGX_GB10_CUDA_LAUNCH_BLOCKING_STARTUP_STABILIZATION",
                "superseded_protocol_file_sha256": "c2cda2508e968072d58256cacc7e9d4c792ce7be73c097ce1136803b873e87dd",
                "trigger": "The repaired fresh-service metrics occurrence exited during vLLM memory-profile warmup with cudaErrorNotPermitted at the native fused RMSNorm path on DGX GB10 before readiness and before either neutral probe POST. The owned container was removed and shared services were restored.",
                "change": "Add CUDA_LAUNCH_BLOCKING=1 to the exact pinned container environment, following the upstream vLLM GB10 warmup-race workaround while retaining enforce-eager and every model, image, decoding, cache, and request-budget identity. Detect an exited owned startup container immediately instead of waiting for the full readiness deadline.",
                "prospective_boundary": "NO_B0_SELECTION_NO_ALFWORLD_EPISODE_NO_TASK_OUTCOME_NO_NEUTRAL_PROBE_POST_STARTUP_ENGINEERING_FAILURE_ONLY",
            },
            {
                "id": "PRE_B0_ENGINEERING_EVIDENCE_AND_COMPLETION_COUNTER_SEMANTICS_BINDING",
                "superseded_protocol_file_sha256": "f754cb5fb6db2b97fa1b1a2055946f7dc63ce7c754909eec894e1848d07bc548",
                "trigger": "Before any B0 selection, one sealed fixed-look DGX runtime qualification and one fresh-service neutral vLLM metrics qualification were completed and committed. The neutral probe established that request_success_total increased by zero for one successful tokenize POST and by one for one successful completion POST, with running and prefix-cache counters remaining zero.",
                "change": "Bind both immutable public qualification manifests, require their committed bytes in the live start closure, and prospectively compare the final service success counter with issued completion POSTs only while continuing to account for tokenize and completion POSTs separately at the client gate.",
                "prospective_boundary": "NO_B0_SELECTION_NO_ALFWORLD_B0_EPISODE_NO_TASK_OUTCOME_ONE_NEUTRAL_TOKENIZE_AND_ONE_NEUTRAL_COMPLETION_ENGINEERING_PROBE_ONLY_NO_AGENT_OR_HSWM_EFFICACY",
            }
        ]
        or raw.get("registration_status")
        != "PROSPECTIVE_BEFORE_ANY_B0_SELECTION_ALFWORLD_EPISODE_OR_TASK_OUTCOME_AFTER_COMMITTED_ENGINEERING_RUNTIME_AND_NEUTRAL_METRICS_QUALIFICATIONS"
        or raw.get("scientific_status")
        != "EXPLORATORY_G0_CALIBRATION_ONLY_NOT_G0_PASS_NOT_G1_EFFICACY"
        or raw.get("claim_ceiling") != "ENGINEERING_AND_TASK_CALIBRATION_ONLY"
        or raw.get("research_order")
        != {"G0": "NOT_PASSED", "G1_THROUGH_G6": "LOCKED_BY_THIS_STUDY"}
    ):
        raise AlfworldB0CalibrationError("protocol scientific boundary drifted")

    uid, version = raw.get("study_uid"), raw.get("protocol_version")
    evidence = _exact_mapping(raw.get("current_evidence"), "protocol evidence")
    arm = _exact_mapping(raw.get("arm"), "protocol arm")
    task = _exact_mapping(raw.get("task_contract"), "protocol task contract")
    selection = _exact_mapping(
        raw.get("prospective_selection"), "protocol selection contract"
    )
    allocation = _exact_mapping(selection.get("allocation"), "protocol allocation")
    train = _exact_mapping(allocation.get("train"), "protocol train allocation")
    valid_seen = _exact_mapping(
        allocation.get("valid_seen"), "protocol valid-seen allocation"
    )
    valid_unseen = _exact_mapping(
        allocation.get("valid_unseen"), "protocol valid-unseen allocation"
    )
    actor = _exact_mapping(raw.get("actor_contract"), "protocol actor contract")
    environment_runtime = _exact_mapping(
        raw.get("environment_runtime"), "protocol environment runtime"
    )
    runtime = _exact_mapping(raw.get("model_runtime"), "protocol model runtime")
    stopping = _exact_mapping(
        raw.get("resource_and_stopping_contract"), "protocol stopping contract"
    )
    estimands = _exact_mapping(raw.get("estimands_and_decisions"), "protocol estimands")
    execution = _exact_mapping(
        raw.get("execution_source_binding"), "protocol source binding"
    )

    response_schema = _action_schema().schema_json
    actor_exact = (
        actor.get("implementation_path")
        == "src/hswm/experiments/alfworld_b0_actor.py"
        and actor.get("transport")
        == "ONE_SHOT_OPENAI_COMPATIBLE_REQUEST_PER_ACTION_NO_RETRY"
        and actor.get("system_prompt_utf8") == B0_ACTION_SYSTEM_MESSAGE
        and actor.get("system_prompt_sha256")
        == sha256(B0_ACTION_SYSTEM_MESSAGE.encode("utf-8")).hexdigest()
        and actor.get("user_payload_fields")
        == ["protocol", "episode_uid", "step_index", "history", "observation"]
        and actor.get("history_item_fields") == ["observation", "action"]
        and actor.get("history_length_equals_step_index") is True
        and actor.get("response_schema_canonical_json") == response_schema
        and actor.get("response_schema_sha256")
        == sha256(response_schema.encode("utf-8")).hexdigest()
        and actor.get("max_output_tokens_per_action") == B0_ACTION_MAX_OUTPUT_TOKENS
        and actor.get("max_observation_utf8_bytes") == B0_ACTION_MAX_OBSERVATION_BYTES
        and actor.get("max_canonical_user_payload_bytes") == B0_ACTION_MAX_INPUT_BYTES
        and actor.get("max_prepared_chat_request_bytes")
        == B0_ACTION_MAX_REQUEST_BYTES
        and actor.get("response_json_whitespace_policy")
        == "Parse one strict JSON object with duplicate keys forbidden; insignificant JSON whitespace is accepted and is not treated as provider-byte exactness."
        and actor.get("issued_post_gate")
        == "A fresh occurrence-local gate consumes one tokenize or completion allowance immediately before each transport attempt, including failed attempts; it refuses the 241st request of either kind before network dispatch."
    )
    schedule_exact = (
        train.get("groups") == TRAIN_EPISODES
        and train.get("games_per_group") == 1
        and valid_seen.get("groups") == VALID_SEEN_EPISODES
        and valid_seen.get("games_per_group") == 1
        and valid_unseen.get("groups_selected") == 0
        and valid_unseen.get("games_selected") == 0
        and selection.get("rank_task_groups_before_games") is True
        and selection.get("one_game_per_group") is True
        and selection.get("without_replacement") is True
        and selection.get("execution_order")
        == "All eight selected train games in committed rank order, then all four selected valid_seen games in committed rank order. No outcome-dependent reordering."
    )
    runtime_exact = (
        runtime.get("endpoint_origin") == "http://127.0.0.1:18080"
        and runtime.get("served_model") == "qwen3.6-35b-a3b"
        and runtime.get("max_model_len") == 32_768
        and runtime.get("max_num_seqs") == 1
        and runtime.get("prefix_cache") is False
        and runtime.get("async_scheduling") is False
        and runtime.get("enforce_eager") is True
        and runtime.get("language_model_only") is True
        and runtime.get("engine_seed") == 0
        and runtime.get("temperature") == 0.0
        and runtime.get("top_p") == 1.0
        and runtime.get("enable_thinking") is False
        and runtime.get("fresh_service_for_occurrence") is True
        and runtime.get("request_success_counter_at_start") == 0
        and runtime.get("request_success_counter_semantics")
        == "COMPLETED_GENERATION_REQUESTS_ONLY_TOKENIZE_EXCLUDED"
        and runtime.get("successful_tokenize_post_counter_delta") == 0
        and runtime.get("successful_completion_post_counter_delta") == 1
        and runtime.get("final_service_attestation")
        == "REQUEST_SUCCESS_TOTAL_EQUALS_ISSUED_COMPLETION_POST_COUNT_TOKENIZE_ACCOUNTED_SEPARATELY"
        and runtime.get("maximum_completion_posts") == B0_MAX_COMPLETION_CALLS
        and runtime.get("maximum_tokenize_posts") == B0_MAX_TOKENIZE_CALLS
        and runtime.get("maximum_total_http_posts")
        == B0_MAX_COMPLETION_CALLS + B0_MAX_TOKENIZE_CALLS
        and runtime.get("byte_exactness_required") is False
    )
    stopping_exact = (
        stopping.get("scheduled_episodes") == SCHEDULED_EPISODES
        and stopping.get("maximum_model_actions_per_episode")
        == B0_ACTION_MAX_HISTORY_STEPS
        and stopping.get("maximum_model_completions") == B0_MAX_COMPLETION_CALLS
        and stopping.get("maximum_tokenize_calls") == B0_MAX_TOKENIZE_CALLS
        and stopping.get("completion_timeout_seconds") == COMPLETION_TIMEOUT_SECONDS
        and stopping.get("maximum_occurrence_wall_seconds")
        == MAX_OCCURRENCE_WALL_SECONDS
        and stopping.get("retry_count") == 0
        and stopping.get("replacement_count") == 0
        and stopping.get("resume_allowed") is False
        and stopping.get("early_success_stop") is False
    )
    environment_exact = (
        environment_runtime.get("platform") == "DGX_AARCH64"
        and environment_runtime.get("python_version") == "3.9.25"
        and environment_runtime.get("upstream_repository")
        == "https://github.com/alfworld/alfworld"
        and environment_runtime.get("upstream_revision")
        == "aaba6870f86c5be6a08a491f32a50b906227bc3e"
        and environment_runtime.get("upstream_source_archive_sha256")
        == "5592fbb36124b08d24167c5f7612a55a2cc610e0c39170f638a69b628835ee3b"
        and environment_runtime.get("installation")
        == "INSTALL_ARM64_PDDL_ONLY_REQUIREMENTS_THEN_PATCHED_TEXTWORLD_SOURCE_NO_DEPS_THEN_SOURCE_PINNED_ALFWORLD_NO_DEPS"
        and environment_runtime.get("inherited_requirements_path")
        == "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/alfworld_text_runtime.requirements.v1.txt"
        and environment_runtime.get("inherited_requirements_sha256")
        == "2cd843b101554f7935709168be65be5039bcac41f32a2aa7b1b4f54f8ee320c8"
        and environment_runtime.get("arm64_pddl_only_requirements_path")
        == "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/alfworld_text_runtime.arm64_pddl_only.requirements.v1.txt"
        and environment_runtime.get("arm64_pddl_only_requirements_sha256")
        == "2835136ea0b72f65374d584ddae3c4951737e8c0eabb7effae7d588a313655e7"
        and environment_runtime.get("textworld")
        == {
            "upstream_repository": "https://github.com/microsoft/TextWorld",
            "upstream_tag": "1.7.0",
            "upstream_revision": "9fce9ee107fa042ef2656e41e0b362450a35ecd8",
            "patch_path": "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/textworld-pddl-only.v1.patch",
            "patch_sha256": "8b623fe87548694b3990896d69260ae3325c2d686cac62c7daf3963a23772c1d",
            "install_environment": {"TEXTWORLD_PDDL_ONLY": "1"},
            "capability": "PDDL_ONLY_NO_INFORM7_SETUP_OR_CAPABILITY",
        }
        and environment_runtime.get("install_order")
        == [
            "install arm64_pddl_only_requirements exactly",
            "checkout TextWorld upstream_revision exactly",
            "verify and apply textworld.patch_path",
            "install patched TextWorld with TEXTWORLD_PDDL_ONLY=1 and --no-deps",
            "install source-pinned ALFWorld with --no-deps",
            "supply HSWM from the clean execution checkout through PYTHONPATH",
        ]
        and environment_runtime.get("required_key_versions")
        == {
            "alfworld": "0.5.0",
            "fast-downward-textworld": "20.6.4",
            "jericho": "3.3.1",
            "numpy": "2.0.2",
            "textworld": "1.7.0",
        }
        and environment_runtime.get("sandbox") == dgx_sandbox_contract()
        and environment_runtime.get("dgx_fixed_action_qualification")
        == DGX_RUNTIME_QUALIFICATION
    )
    if (
        not isinstance(uid, str)
        or not uid
        or not isinstance(version, str)
        or not version
        or arm.get("id") != "B0_STATELESS_NO_LEARNING"
        or arm.get("count") != 1
        or arm.get("cross_episode_state") != "NONE"
        or evidence.get("dgx_runtime_qualification")
        != DGX_RUNTIME_QUALIFICATION
        or evidence.get("vllm_metrics_qualification")
        != VLLM_METRICS_QUALIFICATION
        or task.get("environment") != "ALFWORLD_TEXT_ONLY"
        or task.get("task_family") != "pick_clean_then_place_in_recep"
        or task.get("environment_horizon") != B0_ACTION_MAX_HISTORY_STEPS
        or task.get("fresh_environment_per_episode") is not True
        or task.get("simulator_terminal_outcome_hidden_from_actor") is not True
        or not schedule_exact
        or not actor_exact
        or not environment_exact
        or not runtime_exact
        or not stopping_exact
        or estimands.get("possible_complete_terminal") != COMPLETE_STATUS
        or estimands.get("effect_or_gate_decision") != "NONE"
        or execution.get("required_clean_committed_checkout") is not True
        or execution.get(
            "private_selection_receipt_must_precede_first_environment_or_model_call"
        )
        is not True
        or "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/runtime_qualification_contract.v1.json"
        not in execution.get("start_marker_must_hash_paths", [])
        or DGX_RUNTIME_QUALIFICATION["path"]
        not in execution.get("start_marker_must_hash_paths", [])
        or VLLM_METRICS_QUALIFICATION["path"]
        not in execution.get("start_marker_must_hash_paths", [])
        or "src/hswm/experiments/alfworld_b0_vllm_metrics.py"
        not in execution.get("start_marker_must_hash_paths", [])
        or "scripts/qualify_hswm_alfworld_b0_vllm_metrics.py"
        not in execution.get("start_marker_must_hash_paths", [])
        or raw.get("resource_and_stopping_contract", {}).get("failure_rule")
        != "Any asset, sudo authorization, sandbox identity, controller-held verified-FD bind, model-service, token-preflight, response-schema, action-grammar, outcome-receipt, source-binding, or request-counter failure seals the exact attempted prefix, forbids retry or resume, and terminates the occurrence as INCONCLUSIVE_MEASUREMENT_NOT_READY."
        or "The privileged DGX adapter is trusted-maintainer local engineering containment only; it is neither hostile-local-user security nor independent evaluation."
        not in raw.get("no_claim", [])
        or raw.get("allowed_terminals")
        != [COMPLETE_STATUS, INCONCLUSIVE_STATUS, VOID_STATUS]
    ):
        raise AlfworldB0CalibrationError("full protocol executable contract drifted")
    return VerifiedB0Protocol(
        uid=uid,
        version=version,
        max_steps=B0_ACTION_MAX_HISTORY_STEPS,
        max_completions=B0_MAX_COMPLETION_CALLS,
        max_tokenizations=B0_MAX_TOKENIZE_CALLS,
        completion_timeout_seconds=COMPLETION_TIMEOUT_SECONDS,
        max_wall_seconds=MAX_OCCURRENCE_WALL_SECONDS,
        served_model=str(runtime["served_model"]),
        binding_sha256=binding,
    )


def _selection_rows(
    value: object, split: str, count: int
) -> tuple[OpaqueGameSelection, ...]:
    if not isinstance(value, list) or len(value) != count:
        raise AlfworldB0CalibrationError(f"private selection {split} count drifted")
    rows: list[OpaqueGameSelection] = []
    for row in value:
        if (
            not isinstance(row, dict)
            or set(row) != {"split", "task_group_uid", "opaque_uid"}
            or row.get("split") != split
        ):
            raise AlfworldB0CalibrationError(f"private selection {split} row drifted")
        group, opaque = row.get("task_group_uid"), row.get("opaque_uid")
        if (
            not isinstance(group, str)
            or _OPAQUE_IDENTIFIER.fullmatch(group) is None
            or not isinstance(opaque, str)
            or _OPAQUE_IDENTIFIER.fullmatch(opaque) is None
        ):
            raise AlfworldB0CalibrationError(
                f"private selection {split} identifier is invalid"
            )
        rows.append(OpaqueGameSelection(split, group, opaque))
    if len({row.task_group_uid for row in rows}) != count or len(
        {row.opaque_uid for row in rows}
    ) != count:
        raise AlfworldB0CalibrationError(
            f"private selection {split} contains a duplicate"
        )
    return tuple(rows)


def verify_private_selection(
    value: Mapping[str, object] | Path,
    protocol: VerifiedB0Protocol,
    *,
    pool_manifest_sha256: str,
    local_locator_sha256: str,
) -> tuple[tuple[OpaqueGameSelection, ...], str, str]:
    """Verify exact selection order, self-hash, source, and pool commitments."""

    from . import alfworld_b0_selection as selector_module

    raw, rendered_sha = _read_mapping(value, "private selection receipt")
    expected = {
        "schema_version",
        "record_role",
        "status",
        "protocol",
        "selector_source_sha256",
        "input_commitments",
        "selection_digest_sha256",
        "selected",
        "valid_unseen_selected_group_count",
        "no_claim",
        "private_receipt_sha256",
    }
    unsigned = {key: item for key, item in raw.items() if key != "private_receipt_sha256"}
    if (
        set(raw) != expected
        or raw.get("schema_version") != PRIVATE_SELECTION_SCHEMA
        or raw.get("record_role")
        != "LOCAL_NONREPOSITORY_OPAQUE_B0_SELECTION_RECEIPT_NOT_FOR_REDISTRIBUTION"
        or raw.get("status") != "PROSPECTIVE_SELECTION_ONLY_G0_NOT_RUN"
        or raw.get("private_receipt_sha256")
        != sha256(canonical_bytes(unsigned)).hexdigest()
    ):
        raise AlfworldB0CalibrationError(
            "private selection receipt schema or self-hash drifted"
        )
    if raw.get("protocol") != {
        "uid": protocol.uid,
        "version": protocol.version,
        "protocol_file_sha256": protocol.binding_sha256,
    }:
        raise AlfworldB0CalibrationError("private selection protocol binding drifted")
    selector_sha = sha256(Path(selector_module.__file__).read_bytes()).hexdigest()
    if raw.get("selector_source_sha256") != selector_sha:
        raise AlfworldB0CalibrationError("private selection source binding drifted")
    if raw.get("input_commitments") != {
        "pool_manifest_rendered_json_sha256": _sha(
            pool_manifest_sha256, "pool manifest"
        ),
        "local_locator_rendered_json_sha256": _sha(
            local_locator_sha256, "local locator"
        ),
    }:
        raise AlfworldB0CalibrationError("private selection pool binding drifted")
    if raw.get("valid_unseen_selected_group_count") != 0:
        raise AlfworldB0CalibrationError("B0 selection must not consume valid_unseen")
    selected = raw.get("selected")
    if not isinstance(selected, dict) or set(selected) != {"train", "valid_seen"}:
        raise AlfworldB0CalibrationError("private selection split field set drifted")
    train = _selection_rows(selected["train"], "train", TRAIN_EPISODES)
    valid_seen = _selection_rows(
        selected["valid_seen"], "valid_seen", VALID_SEEN_EPISODES
    )
    rows = train + valid_seen
    if len({row.opaque_uid for row in rows}) != SCHEDULED_EPISODES:
        raise AlfworldB0CalibrationError("private selection reuses a game across splits")
    recomputed = sha256(
        canonical_bytes(
            {
                "train": [
                    {
                        "split": row.split,
                        "task_group_uid": row.task_group_uid,
                        "opaque_uid": row.opaque_uid,
                    }
                    for row in train
                ],
                "valid_seen": [
                    {
                        "split": row.split,
                        "task_group_uid": row.task_group_uid,
                        "opaque_uid": row.opaque_uid,
                    }
                    for row in valid_seen
                ],
            }
        )
    ).hexdigest()
    if raw.get("selection_digest_sha256") != recomputed:
        raise AlfworldB0CalibrationError("private selection digest does not bind rows")
    return rows, rendered_sha, recomputed


def _actor_counts(actor: Any) -> tuple[int, int]:
    value = getattr(actor, "request_counts", None)
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or any(type(item) is not int or item < 0 for item in value)
        or value[0] > B0_MAX_TOKENIZE_CALLS
        or value[1] > B0_MAX_COMPLETION_CALLS
    ):
        raise AlfworldB0CalibrationError("actor request gate counters drifted")
    return value


def _validate_actor_receipt(
    receipt: object,
    *,
    protocol: VerifiedB0Protocol,
    episode_uid: str,
    step_index: int,
    before: tuple[int, int],
    after: tuple[int, int],
) -> dict[str, object]:
    canonical = getattr(receipt, "canonical", None)
    if not callable(canonical):
        raise AlfworldB0CalibrationError("actor did not return a canonical receipt")
    value = canonical()
    expected = {
        "action",
        "action_sha256",
        "completion_call_count",
        "completion_call_index",
        "completion_latency_ms",
        "completion_request_sha256",
        "completion_response_sha256",
        "episode_uid",
        "input_tokens",
        "model",
        "output_tokens",
        "protocol",
        "receipt_sha256",
        "response_schema_sha256",
        "schema",
        "step_index",
        "tokenize_call_count",
        "tokenize_call_index",
        "token_preflight_token_count",
        "token_preflight_latency_ms",
        "token_preflight_receipt_sha256",
        "token_preflight_request_sha256",
        "token_preflight_response_sha256",
        "usage_reported",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise AlfworldB0CalibrationError("actor receipt field set drifted")
    unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
    action = value.get("action")
    if (
        value.get("receipt_sha256") != sha256(canonical_bytes(unsigned)).hexdigest()
        or value.get("schema") != B0_ACTION_RECEIPT_SCHEMA
        or value.get("protocol") != B0_ACTION_PROTOCOL
        or value.get("episode_uid") != episode_uid
        or value.get("step_index") != step_index
        or value.get("model") != protocol.served_model
        or value.get("response_schema_sha256") != _action_schema().schema_sha256
        or value.get("completion_call_count") != 1
        or value.get("tokenize_call_count") != 1
        or value.get("completion_call_index") != after[1]
        or value.get("tokenize_call_index") != after[0]
        or after != (before[0] + 1, before[1] + 1)
        or value.get("usage_reported") is not True
        or not isinstance(action, str)
        or not 1 <= len(action.encode("utf-8")) <= B0_ACTION_MAX_BYTES
        or any(not 0x20 <= ord(char) <= 0x7E for char in action)
    ):
        raise AlfworldB0CalibrationError("actor receipt identity or action drifted")
    for field in (
        "input_tokens",
        "output_tokens",
        "token_preflight_token_count",
        "completion_latency_ms",
        "token_preflight_latency_ms",
    ):
        if type(value.get(field)) is not int or int(value[field]) < 0:
            raise AlfworldB0CalibrationError("actor receipt resource value drifted")
    if value["input_tokens"] != value["token_preflight_token_count"]:
        raise AlfworldB0CalibrationError("token preflight and completion usage disagree")
    for field in (
        "action_sha256",
        "completion_request_sha256",
        "completion_response_sha256",
        "receipt_sha256",
        "response_schema_sha256",
        "token_preflight_receipt_sha256",
        "token_preflight_request_sha256",
        "token_preflight_response_sha256",
    ):
        _sha(value.get(field), f"actor receipt {field}")
    if value["action_sha256"] != sha256(action.encode("ascii")).hexdigest():
        raise AlfworldB0CalibrationError("actor action digest drifted")
    return value


def _default_launcher(spec: LocalSandboxSpec) -> Any:
    return LocalAlfworldTextRuntime(spec).launch()


def _terminate(process: Any) -> None:
    try:
        if getattr(process, "poll")() is None:
            getattr(process, "terminate")()
        getattr(process, "wait")(timeout=5)
    except Exception:
        pass


def _preframe_failure_phase(process: Any, *, timeout_seconds: float) -> str | None:
    """Recover only a registered worker phase after the initial actor pipe closes."""
    try:
        return_code = process.poll()
        if return_code is None:
            return_code = process.wait(timeout=min(1.0, timeout_seconds))
        return decode_preframe_failure_exit_code(return_code)
    except Exception:
        return None


def _headroom(train_successes: int, *, complete: bool) -> str:
    if not complete:
        return "INCONCLUSIVE_MEASUREMENT_NOT_READY_WITHOUT_HEADROOM_CLASSIFICATION"
    if train_successes <= 1:
        return "FLOOR_OR_INSTRUMENT_REPAIR"
    if train_successes <= 6:
        return "CANDIDATE_HEADROOM"
    return "SATURATION_OR_INSUFFICIENT_HEADROOM"


def _binomial_cdf(k: int, n: int, probability: float) -> float:
    return sum(
        math.comb(n, index)
        * probability**index
        * (1.0 - probability) ** (n - index)
        for index in range(k + 1)
    )


def _clopper_pearson(successes: int, trials: int) -> dict[str, str | int]:
    """Return a two-sided 95% exact binomial interval as decimal strings."""

    alpha_tail = 0.025
    if successes == 0:
        lower = 0.0
    else:
        low, high = 0.0, 1.0
        for _ in range(100):
            midpoint = (low + high) / 2.0
            tail = 1.0 - _binomial_cdf(successes - 1, trials, midpoint)
            if tail < alpha_tail:
                low = midpoint
            else:
                high = midpoint
        lower = (low + high) / 2.0
    if successes == trials:
        upper = 1.0
    else:
        low, high = 0.0, 1.0
        for _ in range(100):
            midpoint = (low + high) / 2.0
            if _binomial_cdf(successes, trials, midpoint) > alpha_tail:
                low = midpoint
            else:
                high = midpoint
        upper = (low + high) / 2.0
    return {
        "successes": successes,
        "trials": trials,
        "lower": f"{lower:.9f}",
        "upper": f"{upper:.9f}",
        "method": "TWO_SIDED_95_PERCENT_CLOPPER_PEARSON",
    }


def _private_receipt(
    *,
    protocol: VerifiedB0Protocol,
    selection_receipt_sha: str,
    selection_digest_sha: str,
    pool_manifest: Path,
    local_locator: Path,
    asset_root: Path,
    episodes: list[dict[str, object]],
    terminal: Mapping[str, object],
    totals: Mapping[str, object],
) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": PRIVATE_RUN_SCHEMA,
        "record_role": "LOCAL_NONREPOSITORY_B0_CALIBRATION_RUN_RECEIPT_NOT_FOR_REDISTRIBUTION",
        "status": terminal["status"],
        "claim_ceiling": "NO_LEARNING_NO_REVISION_NO_G0_PASS_NO_G1_NO_HSWM_EFFICACY_CLAIM",
        "protocol": {
            "uid": protocol.uid,
            "version": protocol.version,
            "max_steps": protocol.max_steps,
            "binding_sha256": protocol.binding_sha256,
        },
        "input_commitments": {
            "private_selection_receipt_sha256": selection_receipt_sha,
            "selection_digest_sha256": selection_digest_sha,
            "pool_manifest_path": str(pool_manifest),
            "local_locator_path": str(local_locator),
            "asset_root_path": str(asset_root),
        },
        "episode_prefix": episodes,
        "terminal": dict(terminal),
        "resource_totals": dict(totals),
    }
    value["private_receipt_sha256"] = sha256(canonical_bytes(value)).hexdigest()
    return value


def public_projection(private: Mapping[str, object]) -> dict[str, object]:
    """Verify a private receipt and project repository-safe aggregates only."""

    unsigned = {
        key: item for key, item in private.items() if key != "private_receipt_sha256"
    }
    if (
        private.get("schema_version") != PRIVATE_RUN_SCHEMA
        or private.get("private_receipt_sha256")
        != sha256(canonical_bytes(unsigned)).hexdigest()
    ):
        raise AlfworldB0CalibrationError("private run receipt self-binding drifted")
    episodes = private.get("episode_prefix")
    terminal = private.get("terminal")
    totals = private.get("resource_totals")
    protocol = private.get("protocol")
    inputs = private.get("input_commitments")
    if (
        not all(isinstance(item, dict) for item in (terminal, totals, protocol, inputs))
        or not isinstance(episodes, list)
    ):
        raise AlfworldB0CalibrationError("private run receipt shape drifted")
    split_counts = {"train": 0, "valid_seen": 0}
    success_counts = {"train": 0, "valid_seen": 0}
    invalid_counts = {"train": 0, "valid_seen": 0}
    for episode in episodes:
        if not isinstance(episode, dict) or episode.get("split") not in split_counts:
            raise AlfworldB0CalibrationError("private episode prefix split drifted")
        split = str(episode["split"])
        split_counts[split] += 1
        if episode.get("terminal") == "COMPLETE":
            outcome = episode.get("private_terminal_receipt")
            if not isinstance(outcome, dict) or type(outcome.get("success")) is not bool:
                raise AlfworldB0CalibrationError("complete private episode outcome drifted")
            success_counts[split] += int(outcome["success"])
        else:
            invalid_counts[split] += 1
    complete = terminal.get("status") == COMPLETE_STATUS
    if complete and (
        split_counts != {"train": TRAIN_EPISODES, "valid_seen": VALID_SEEN_EPISODES}
        or invalid_counts != {"train": 0, "valid_seen": 0}
    ):
        raise AlfworldB0CalibrationError("complete status lacks all 12 valid episodes")
    intervals: dict[str, object] | None = None
    if complete:
        intervals = {
            split: _clopper_pearson(success_counts[split], split_counts[split])
            for split in ("train", "valid_seen")
        }
    value: dict[str, object] = {
        "schema_version": PUBLIC_RUN_SCHEMA,
        "status": terminal["status"],
        "claim_ceiling": private.get("claim_ceiling"),
        "commitments": {
            "protocol_binding_sha256": protocol["binding_sha256"],
            "selection_digest_sha256": inputs["selection_digest_sha256"],
            "private_selection_receipt_sha256": inputs[
                "private_selection_receipt_sha256"
            ],
            "private_run_receipt_sha256": private["private_receipt_sha256"],
        },
        "split_counts": split_counts,
        "success_counts": success_counts,
        "invalid_counts": invalid_counts,
        "confidence_intervals": intervals,
        "resource_totals": dict(totals),
        "headroom_classification": _headroom(
            success_counts["train"], complete=complete
        ),
        "failure_class": terminal.get("error_type") if not complete else None,
    }
    encoded = canonical_bytes(value).decode("utf-8").lower()
    if any(token in encoded for token in _FORBIDDEN_PUBLIC):
        raise AlfworldB0CalibrationError("public projection leakage guard failed")
    value["public_projection_sha256"] = sha256(canonical_bytes(value)).hexdigest()
    return value


def _path_sha(path: Path, label: str) -> str:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise AlfworldB0CalibrationError(
            f"{label} must be an absolute non-symlink regular file"
        )
    return sha256(path.read_bytes()).hexdigest()


def run_b0_calibration(
    *,
    protocol: Mapping[str, object] | Path,
    private_selection_receipt: Mapping[str, object] | Path,
    pool_manifest: Path,
    local_locator: Path,
    asset_root: Path,
    sandbox_spec_factory: SandboxSpecFactory,
    actor: Any,
    runtime_launcher: RuntimeLauncher = _default_launcher,
    frame_reader: FrameReader = read_one_line,
    monotonic: Callable[[], float] = time.monotonic,
) -> tuple[dict[str, object], dict[str, object]]:
    """Run the committed train-8 then valid-seen-4 sequence exactly once."""

    protocol_value = verify_protocol(protocol)
    pool_sha = _path_sha(pool_manifest, "pool manifest")
    locator_sha = _path_sha(local_locator, "local locator")
    selected, selection_sha, selection_digest = verify_private_selection(
        private_selection_receipt,
        protocol_value,
        pool_manifest_sha256=pool_sha,
        local_locator_sha256=locator_sha,
    )
    if _actor_counts(actor) != (0, 0):
        raise AlfworldB0CalibrationError("B0 actor request gate is not fresh")

    episodes: list[dict[str, object]] = []
    totals: dict[str, object] = {
        "actor_call_count": 0,
        "environment_step_count": 0,
        "input_token_count": 0,
        "output_token_count": 0,
        "token_preflight_token_count": 0,
        "issued_completion_post_count": 0,
        "issued_tokenize_post_count": 0,
        "issued_http_post_count": 0,
        "validated_model_response_count": 0,
        "completed_episode_count": 0,
        "wall_microseconds": 0,
    }
    terminal: dict[str, object] = {
        "status": COMPLETE_STATUS,
        "reason": "ALL_12_EPISODES_COMPLETED_ONCE",
    }
    started = monotonic()
    deadline = started + protocol_value.max_wall_seconds

    def remaining_timeout() -> float:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise AlfworldB0CalibrationError("occurrence wall-time ceiling reached")
        return min(float(protocol_value.completion_timeout_seconds), remaining)

    try:
        for ordinal, selection in enumerate(selected):
            trace: list[dict[str, object]] = []
            binding: LocalGameBinding | None = None
            process: Any | None = None
            actor_attempt: dict[str, object] | None = None
            preframe_failure_phase: str | None = None
            try:
                observed_pool_sha, observed_locator_sha, binding, game_file = (
                    load_local_game_binding(
                        pool_manifest=pool_manifest,
                        local_locator=local_locator,
                        asset_root=asset_root,
                        opaque_uid=selection.opaque_uid,
                    )
                )
                if observed_pool_sha != pool_sha or observed_locator_sha != locator_sha:
                    raise AlfworldB0CalibrationError("per-game pool commitment drifted")
                spec = sandbox_spec_factory(
                    selection,
                    binding,
                    game_file,
                    pool_sha,
                    locator_sha,
                    protocol_value,
                )
                if (
                    not isinstance(spec, LocalSandboxSpec)
                    or spec.max_steps != protocol_value.max_steps
                    or spec.episode_uid != selection.opaque_uid
                    or spec.game_binding != binding
                    or spec.game_file != game_file
                    or spec.asset_root != asset_root
                    or spec.pool_manifest_sha256 != pool_sha
                    or spec.local_locator_sha256 != locator_sha
                ):
                    raise AlfworldB0CalibrationError("sandbox spec binding drifted")
                process = runtime_launcher(spec)
                if any(
                    getattr(process, name, None) is None
                    for name in ("stdin", "stdout", "stderr", "wait", "poll", "terminate")
                ):
                    raise AlfworldB0CalibrationError(
                        "runtime launcher did not return one fresh live transport"
                    )
                launch_return_code = process.poll()
                if launch_return_code is not None:
                    try:
                        preframe_failure_phase = decode_preframe_failure_exit_code(
                            launch_return_code
                        )
                    except Exception:
                        raise AlfworldB0CalibrationError(
                            "runtime launcher did not return one fresh live transport"
                        ) from None
                    raise AlfworldB0CalibrationError(
                        "runtime refused before initial actor frame"
                    )
                try:
                    actor_raw = frame_reader(
                        process.stdout,
                        timeout_seconds=remaining_timeout(),
                        label="actor frame",
                    )
                except AlfworldTextRuntimeClosed:
                    preframe_failure_phase = _preframe_failure_phase(
                        process,
                        timeout_seconds=remaining_timeout(),
                    )
                    if preframe_failure_phase is not None:
                        raise AlfworldB0CalibrationError(
                            "runtime refused before initial actor frame"
                        ) from None
                    raise
                actor_frame = validate_actor_projection(
                    actor_raw, episode_uid=spec.episode_uid, previous_step=None
                )
                if actor_frame["step_index"] != 0 or actor_frame["done"] is not False:
                    raise AlfworldB0CalibrationError("initial actor frame drifted")
                while not actor_frame["done"]:
                    step_index = actor_frame["step_index"]
                    if (
                        type(step_index) is not int
                        or step_index != len(trace)
                        or step_index >= protocol_value.max_steps
                    ):
                        raise AlfworldB0CalibrationError(
                            "nonterminal frame exceeds the 20-action horizon"
                        )
                    history = tuple(
                        {
                            "observation": str(row["observation"]),
                            "action": str(
                                _exact_mapping(
                                    row["actor_receipt"], "prior actor receipt"
                                )["action"]
                            ),
                        }
                        for row in trace
                    )
                    before = _actor_counts(actor)
                    actor_attempt = {
                        "step_index": step_index,
                        "request_counts_before": {
                            "tokenize": before[0],
                            "completion": before[1],
                        },
                    }
                    try:
                        receipt = actor.act(
                            episode_uid=spec.episode_uid,
                            step_index=step_index,
                            history=history,
                            observation=actor_frame["observation"],
                            deadline=deadline,
                            monotonic=monotonic,
                        )
                    finally:
                        after = _actor_counts(actor)
                        if after[0] < before[0] or after[1] < before[1]:
                            raise AlfworldB0CalibrationError(
                                "actor request counters moved backwards"
                            )
                        totals["issued_tokenize_post_count"] = after[0]
                        totals["issued_completion_post_count"] = after[1]
                        totals["issued_http_post_count"] = after[0] + after[1]
                        actor_attempt["request_counts_after"] = {
                            "tokenize": after[0],
                            "completion": after[1],
                        }
                    receipt_value = _validate_actor_receipt(
                        receipt,
                        protocol=protocol_value,
                        episode_uid=spec.episode_uid,
                        step_index=step_index,
                        before=before,
                        after=after,
                    )
                    trace.append(
                        {
                            "step_index": step_index,
                            "observation": actor_frame["observation"],
                            "actor_receipt": receipt_value,
                        }
                    )
                    actor_attempt = None
                    process.stdin.write(
                        action_line(
                            episode_uid=spec.episode_uid,
                            action=str(receipt_value["action"]),
                        )
                    )
                    process.stdin.flush()
                    totals["actor_call_count"] = int(totals["actor_call_count"]) + 1
                    totals["environment_step_count"] = int(
                        totals["environment_step_count"]
                    ) + 1
                    totals["validated_model_response_count"] = int(
                        totals["validated_model_response_count"]
                    ) + 1
                    for target, source in (
                        ("input_token_count", "input_tokens"),
                        ("output_token_count", "output_tokens"),
                        ("token_preflight_token_count", "token_preflight_token_count"),
                    ):
                        totals[target] = int(totals[target]) + int(receipt_value[source])
                    previous_step = step_index
                    actor_raw = frame_reader(
                        process.stdout,
                        timeout_seconds=remaining_timeout(),
                        label="actor frame",
                    )
                    actor_frame = validate_actor_projection(
                        actor_raw,
                        episode_uid=spec.episode_uid,
                        previous_step=previous_step,
                    )
                if actor_frame["step_index"] != len(trace):
                    raise AlfworldB0CalibrationError("terminal actor frame step drifted")
                outcome_raw = frame_reader(
                    process.stderr,
                    timeout_seconds=remaining_timeout(),
                    label="private terminal receipt",
                )
                outcome = validate_outcome_receipt(
                    outcome_raw,
                    episode_uid=spec.episode_uid,
                    source_game_sha256=binding.file_sha256,
                    actor_steps=len(trace),
                )
                process.stdin.close()
                if process.wait(timeout=remaining_timeout()) != 0:
                    raise AlfworldB0CalibrationError(
                        "runtime exited nonzero after terminal receipt"
                    )
                if (
                    process.stdout.read(MAX_PROTOCOL_LINE_BYTES + 1) != b""
                    or process.stderr.read(MAX_PROTOCOL_LINE_BYTES + 1) != b""
                ):
                    raise AlfworldB0CalibrationError(
                        "runtime emitted extra bytes after terminal receipts"
                    )
                totals["completed_episode_count"] = int(
                    totals["completed_episode_count"]
                ) + 1
                episodes.append(
                    {
                        "ordinal": ordinal,
                        "split": selection.split,
                        "selected": {
                            "task_group_uid": selection.task_group_uid,
                            "opaque_uid": selection.opaque_uid,
                        },
                        "binding": {
                            "relative_path": binding.relative_path,
                            "file_sha256": binding.file_sha256,
                            "bytes": binding.bytes,
                        },
                        "actor_trace": trace,
                        "private_terminal_receipt": dict(outcome),
                        "terminal": "COMPLETE",
                    }
                )
            except Exception as error:
                if process is not None:
                    _terminate(process)
                binding_value: dict[str, object] | None = None
                if binding is not None:
                    binding_value = {
                        "relative_path": binding.relative_path,
                        "file_sha256": binding.file_sha256,
                        "bytes": binding.bytes,
                    }
                failed_episode: dict[str, object] = {
                    "ordinal": ordinal,
                    "split": selection.split,
                    "selected": {
                        "task_group_uid": selection.task_group_uid,
                        "opaque_uid": selection.opaque_uid,
                    },
                    "binding": binding_value,
                    "actor_trace": trace,
                    "failed_actor_attempt": actor_attempt,
                    "terminal": "INCONCLUSIVE",
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
                if preframe_failure_phase is not None:
                    failed_episode["preframe_failure_phase"] = preframe_failure_phase
                episodes.append(failed_episode)
                terminal = {
                    "status": INCONCLUSIVE_STATUS,
                    "reason": "TRANSPORT_SCHEMA_OR_INTEGRITY_ERROR",
                    "error_type": type(error).__name__,
                }
                break
        final_counts = actor.seal()
        if final_counts != _actor_counts(actor):
            raise AlfworldB0CalibrationError("actor seal count drifted")
    except Exception as error:
        terminal = {
            "status": INCONCLUSIVE_STATUS,
            "reason": "INPUT_OR_RUNTIME_INTEGRITY_ERROR",
            "error_type": type(error).__name__,
        }
        try:
            actor.seal()
        except Exception:
            pass
    totals["wall_microseconds"] = int(
        round(max(0.0, monotonic() - started) * 1_000_000)
    )
    private = _private_receipt(
        protocol=protocol_value,
        selection_receipt_sha=selection_sha,
        selection_digest_sha=selection_digest,
        pool_manifest=pool_manifest,
        local_locator=local_locator,
        asset_root=asset_root,
        episodes=episodes,
        terminal=terminal,
        totals=totals,
    )
    return private, public_projection(private)
