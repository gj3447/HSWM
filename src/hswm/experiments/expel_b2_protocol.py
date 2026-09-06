"""Exact prospective B2 protocol construction and fail-closed verification.

Building a draft does not select tasks or launch anything. A live caller must
present the canonical frozen artifact with all implementation hashes intact.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from hswm.selfmod.contracts import canonical_json_bytes

from .alfworld_b0_calibration import DGX_RUNTIME_QUALIFICATION, VLLM_METRICS_QUALIFICATION
from .alfworld_b0_actor import B0_ACTION_MAX_OUTPUT_TOKENS, _action_schema
from .expel_b2_dgx import MODEL_RUNTIME, PROTOCOL_SCHEMA
from .expel_b2_selection import GROUP_DOMAIN, GAME_DOMAIN, SELECTION_SCHEMA
from .expel_b2_text_lesson import (
    ARM_ID, CLAIM_BOUNDARY, B2_ACTION_SYSTEM_MESSAGE, REFLECTION_PROMPT_UTF8,
    LESSON_WRAPPER_PREFIX_UTF8, LESSON_WRAPPER_SUFFIX_UTF8,
    ACTION_LESSON_SEPARATOR_UTF8,
    MAX_RULES, MAX_RULE_UTF8_BYTES, MAX_LESSON_UTF8_BYTES,
)
from .expel_b2_transport import REFLECTION_MAX_OUTPUT_TOKENS, _reflection_schema


PROTOCOL_UID = "sym:ExploratoryStudy:hswm-expel-b2-text-lesson-comparator-2026-09-06"
OCCURRENCE_UID = "hswm-expel-b2-text-lesson-20260906-v3"
PROTOCOL_VERSION = "v3"
FROZEN = "FROZEN_BEFORE_B2_SELECTION_EPISODE_MODEL_CALL_OR_OUTCOME"
DRAFT = "DRAFT_NOT_PREREGISTERED_NOT_FROZEN_NOT_RUN"
RELATIVE_PATH = (
    "_research/causal_composition/preregistrations/"
    "expel_b2_text_lesson_comparator_2026-09-06/protocol.v3.json"
)
V1_PROTOCOL_PATH = RELATIVE_PATH.replace("protocol.v3.json", "protocol.v1.json")
V2_PROTOCOL_PATH = RELATIVE_PATH.replace("protocol.v3.json", "protocol.v2.json")
B0_PROTOCOL_PATH = (
    "_research/causal_composition/preregistrations/"
    "alfworld_b0_calibration_2026-08-30/protocol.v1.json"
)
POOL_SHA256 = "68a7772f78091e6b4c0eddfde016e319be2222ce7ccb5cc1e0fd085ca0936815"
LOCATOR_SHA256 = "cfa8f4bd7357de4be5507e56c3a04d9cac789ff5bfd58786be8c3ec6c4f9e85c"

EXECUTION_SOURCES = (
    "src/hswm/experiments/expel_b2_protocol.py",
    "src/hswm/experiments/expel_b2_selection.py",
    "src/hswm/experiments/expel_b2_transport.py",
    "src/hswm/experiments/expel_b2_text_lesson.py",
    "src/hswm/experiments/expel_b2_sequence.py",
    "src/hswm/experiments/expel_b2_dgx.py",
    "src/hswm/experiments/expel_b2_live.py",
    "src/hswm/experiments/alfworld_b0_dgx.py",
    "src/hswm/experiments/alfworld_b0_actor.py",
    "src/hswm/experiments/alfworld_b0_runtime.py",
    "src/hswm/experiments/alfworld_b0_selection.py",
    "src/hswm/experiments/alfworld_b0_calibration.py",
    "src/hswm/experiments/alfworld_b0_live.py",
    "src/hswm/experiments/alfworld_text_runtime.py",
    "src/hswm/experiments/alfworld_text_worker.py",
    "src/hswm/experiments/continual_live.py",
    "src/hswm/selfmod/contracts.py",
    "scripts/qualify_hswm_alfworld_b0_runtime.py",
    "_research/dgx_q1/model_snapshot_manifest.py",
    "_research/dgx_q1/live_launcher.py",
    "_research/dgx_mi2/experiment.py",
    "_research/dnrd5/canonical_json.py",
    B0_PROTOCOL_PATH,
    V1_PROTOCOL_PATH,
    V2_PROTOCOL_PATH,
    "manifests/HSWM_ALFWORLD_TEXT_CLEAN_POOL_2026-08-30.json",
    DGX_RUNTIME_QUALIFICATION["path"],
    VLLM_METRICS_QUALIFICATION["path"],
    "_research/causal_composition/preregistrations/alfworld_b0_calibration_2026-08-30/runtime_qualification_contract.v1.json",
    "uv.lock", "pyproject.toml",
)


class B2ProtocolError(ValueError):
    """An unbound or amended protocol cannot authorize this occurrence."""


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def build_protocol(repo: Path, *, frozen: bool = False) -> dict[str, Any]:
    """Construct task-independent bytes; caller controls the reviewed publication."""
    base = json.loads((repo / B0_PROTOCOL_PATH).read_bytes())
    environment = base["environment_runtime"]
    sources = tuple(dict.fromkeys((*EXECUTION_SOURCES, environment["arm64_pddl_only_requirements_path"])))
    hashes = {}
    for relative in sources:
        path = repo / relative
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(repo.resolve()):
            raise B2ProtocolError("a required protocol source is absent or linked")
        hashes[relative] = _sha(path.read_bytes())
    return {
        "schema_version": PROTOCOL_SCHEMA, "study_uid": PROTOCOL_UID,
        "protocol_version": PROTOCOL_VERSION, "occurrence_uid": OCCURRENCE_UID,
        "registration_status": FROZEN if frozen else DRAFT,
        "authority": "SECONDARY_AI_RESEARCH_DESIGN", "arm_id": ARM_ID,
        "claim_boundary": CLAIM_BOUNDARY,
        "canonical_role": "External text-state secondary comparator; no canonical atom, owner, credit, Permit, or revision.",
        "predecessor": {
            "b2_v2": {
                "protocol_path": V2_PROTOCOL_PATH,
                "protocol_sha256": "5ef3784f54c7fed7bb5bc682b982ef9220513782764d9afed19104c7a1722680",
                "source_commit": "efffab201fc3b6ed4a6c3b680afa4c05ed54573d",
                "terminal": "INCONCLUSIVE_MEASUREMENT_NOT_READY",
                "observed_tokenize_posts": 1, "observed_completion_posts": 0,
                "failure": "PINNED_MODEL_CHAT_TEMPLATE_REJECTED_TWO_SYSTEM_MESSAGES_HTTP_400",
                "successor_delta": "JOIN_IDENTICAL_ACTION_INSTRUCTIONS_AND_LESSON_IN_ONE_LEADING_SYSTEM_MESSAGE",
                "criteria": "IDENTICAL_ALGORITHM_COUNTS_CAPS_FREEZE_AND_CLAIM_CEILING_NEW_OCCURRENCE_AND_SELECTION",
                "preservation": "V2_PROTOCOL_SELECTION_PREFIX_AND_WRAPPER_RETAINED_NO_RETRY_OR_RESUME",
            },
            "b2_v1": {
                "protocol_path": V1_PROTOCOL_PATH,
                "protocol_sha256": "98c6c46ba3d65dc98f5b148fbda1d9b151972b25c143a19fca6d20609970e1de",
                "source_commit": "c926769206b9d10f5c8461e8fdedf9c5ce1faf74",
                "terminal": "VOID_PROTOCOL_OR_EVIDENCE_BINDING_BREACH_PRELEASE",
                "failure": "WRONG_CALLER_ASSET_ROOT_NO_START_MARKER_NO_LEASE_NO_GAME_NO_MODEL",
                "successor_delta": "CORRECT_LOCATOR_RELATIVE_ASSET_ROOT_FULL_SELECTED_FILE_VALIDATION_AND_EXECUTABLE_MODULE_ENTRYPOINT",
                "preservation": "V1_PROTOCOL_SELECTION_WRAPPER_AND_VOID_RECEIPTS_RETAINED_NO_RETRY_OR_RESUME",
                "criteria": "IDENTICAL_ALGORITHM_COUNTS_CAPS_FREEZE_AND_CLAIM_CEILING_NEW_OCCURRENCE_AND_SELECTION",
            },
            "b0_evidence": "evidence/EVIDENCE_HSWM_ALFWORLD_B0_CALIBRATION_2026-08-30.json",
            "b0_status": "CONSUMED_INCONCLUSIVE_MEASUREMENT_NOT_READY_NO_RATE_NO_RETRY",
            "b0_numerical_comparison": "UNAVAILABLE_REQUIRES_SEPARATELY_PREREGISTERED_SUCCESSOR",
            "runtime_repair": "PINNED_UPSTREAM_ADDED_TO_SANDBOX_PYTHONPATH_IMPORT_ONLY_VERIFIED",
            "historical_exit_61_cause": "NOT_ESTABLISHED",
        },
        "model_runtime": MODEL_RUNTIME, "environment_runtime": environment,
        "current_evidence": {
            "dgx_runtime_qualification": DGX_RUNTIME_QUALIFICATION,
            "vllm_metrics_qualification": VLLM_METRICS_QUALIFICATION,
            "pool_manifest": {"path": "manifests/HSWM_ALFWORLD_TEXT_CLEAN_POOL_2026-08-30.json",
                              "rendered_json_sha256": POOL_SHA256},
            "local_locator_rendered_json_sha256": LOCATOR_SHA256,
        },
        "selection": {
            "schema_version": SELECTION_SCHEMA, "group_rank_domain": GROUP_DOMAIN,
            "game_rank_domain": GAME_DOMAIN, "train_groups": 8, "valid_seen_groups": 4,
            "group_then_game_rank_inputs": "OCCURRENCE_PROTOCOL_FILE_SHA_POOL_SHA_LOCATOR_SHA_SPLIT_GROUP_THEN_OPAQUE_UID",
            "cross_split_policy": "EXCLUDE_SELECTED_TRAIN_GROUPS_FROM_VALID_SEEN_BEFORE_RANKING",
            "replacement_refill_or_prior_arm_state": False,
            "valid_unseen": "SPLIT_TOKEN_ONLY_NO_RECORD_DETAIL_DECODE_NO_SELECTION_NO_GAME_ACCESS",
            "final_holdout": "NONE_VALID_SEEN_IS_DESCRIPTIVE_NOT_A_FINAL_HELDOUT_ESTIMATE",
        },
        "algorithm": {
            "family": ARM_ID, "direct_expel": False,
            "training": "8_TRAIN_EPISODES_EMPTY_LESSON_PER_EPISODE_ONE_REFLECTION_AFTER_EACH_VERIFIED_SUCCESS_ONLY",
            "evaluation": "FREEZE_AFTER_ALL_TRAIN_THEN_4_VALID_SEEN_EPISODES_IDENTICAL_FROZEN_LESSON_NO_UPDATES",
            "outcome_seal": "CANONICAL_WORKER_TERMINAL_PLUS_TRACE_DIGEST_JOINS_AND_CLEAN_PROCESS_EXIT_BEFORE_REFLECTION",
            "reflection_prompt_utf8": REFLECTION_PROMPT_UTF8,
            "reflection_prompt_bytes_sha256": _sha(REFLECTION_PROMPT_UTF8.encode()),
            "action_system_message_utf8": B2_ACTION_SYSTEM_MESSAGE,
            "action_system_message_sha256": _sha(B2_ACTION_SYSTEM_MESSAGE.encode()),
            "action_message_roles": ["system", "user"],
            "action_system_lesson_separator_utf8": ACTION_LESSON_SEPARATOR_UTF8,
            "model_chat_template_sha256": "e84f32a23fdda27689f868aa4a1a5621f41133e51a48d7f3efcbea2839574259",
            "action_response_schema_sha256": _action_schema().schema_sha256,
            "reflection_response_schema_sha256": _reflection_schema().schema_sha256,
            "lesson_wrapper_prefix_utf8": LESSON_WRAPPER_PREFIX_UTF8,
            "lesson_wrapper_suffix_utf8": LESSON_WRAPPER_SUFFIX_UTF8,
            "lesson_format_and_deduplication_algorithm": "PRINTABLE_ASCII_ONE_LINE_TRIM_SPACE_TAB_NEWLINE_REJECT_NUMBERING_BYTE_EXACT_DEDUP_FIRST_TRAIN_TERMINAL_ORDER",
            "maximum_lesson_count": MAX_RULES, "maximum_rule_utf8_bytes": MAX_RULE_UTF8_BYTES,
            "maximum_rendered_lesson_utf8_bytes": MAX_LESSON_UTF8_BYTES,
            "lesson_token_cap": "NO_SEPARATE_LESSON_TOKENIZE_CALL_5120_BYTE_CAP_PLUS_EVERY_FULL_CHAT_TOKEN_PREFLIGHT_WITHIN_32768_CONTEXT",
            "retrieval_embedding_model_and_revision": "NOT_APPLICABLE_LESSON_ONLY",
            "retrieval_similarity_metric_and_top_k": "NOT_APPLICABLE_NO_RETRIEVAL",
            "retrieval_query_construction": "NOT_APPLICABLE_NO_RETRIEVAL",
            "direct_arm_rule_cap_and_paper_vs_yaml_resolution": "NOT_APPLICABLE_NOT_DIRECT_EXPEL",
            "successful_trajectory_fewshot_count_order_ties_and_bytes": "ZERO_NO_FEWSHOT_CHANNEL",
            "FAISS_embedding_tokenizer_dependency_versions_and_index_build": "NO_FAISS_NO_EMBEDDING_PINNED_MODEL_SNAPSHOT_TOKENIZER_VIA_VLLM_TOKENIZE",
            "official_initial_fewshot_material_fairness_policy": "ZERO_INITIAL_FEWSHOTS_IN_B0_AND_B2",
            "episode_horizon_and_official_vs_common_environment_justification": "20_ACTIONS_COMMON_QUALIFIED_PDDL_ONLY_ALFWORLD_ADAPTER_NOT_DIRECT_EXPEL_RUNTIME_PARITY",
            "state_reset_and_cache_network_policy": "FRESH_B2_LESSON_TRAJECTORY_OUTPUT_AND_SERVICE_CACHE_ROOTS_NO_RESUME_PRIVATE_EVIDENCE_PRESERVED_WORKER_NETWORK_UNSHARED_MODEL_LOOPBACK_INGRESS_ONLY_EGRESS_NOT_INDEPENDENTLY_CLAIMED",
        },
        "budget": {"scheduled_episodes": 12, "maximum_actions_per_episode": 20,
            "maximum_action_posts_per_phase": 240, "maximum_reflection_posts_per_phase": 8,
            "maximum_tokenize_posts": 248, "maximum_completion_posts": 248,
            "maximum_total_http_posts": 496,
            "maximum_action_output_tokens": B0_ACTION_MAX_OUTPUT_TOKENS,
            "maximum_reflection_output_tokens": REFLECTION_MAX_OUTPUT_TOKENS,
            "request_timeout_seconds": 120, "occurrence_wall_seconds": 36_000,
            "deadline_policy": "DO_NOT_ISSUE_UNLESS_REMAINING_WALL_TIME_COVERS_REQUEST_TIMEOUT",
            "retries_replacement_refill_human_action_repairs": 0,
            "interactive_human_minutes_during_sequence": 0,
            "lifecycle_cost": "REPORT_ACTION_AND_REFLECTION_COUNTS_AND_OBSERVED_TOKENS_SEPARATELY_UNKNOWN_USAGE_STAYS_UNKNOWN_NOT_BUDGET_MATCHED_TO_B0",
        },
        "interpretation": {"success_rate": "ONLY_ALL_12_VALID_TERMINALS_AND_SUCCESSFUL_REFLECTION_PHASES_AND_FINAL_SERVICE_ATTESTATION",
            "incomplete_prefix": "PRESERVE_ALL_REQUEST_EVENTS_SEALED_TERMINALS_AND_ERROR_CLASS_NO_SUCCESS_RATE",
            "g0": "NOT_PASSED", "g1": "NOT_EVALUATED", "efficacy": "NOT_INFERRED",
            "canonical_hswm_admission": False, "independent_custody": False},
        "execution_source_binding": {"required_clean_committed_checkout": True,
            "start_marker_must_hash_paths": [*sources, RELATIVE_PATH],
            "fixed_source_sha256": hashes,
            "source_scope": "ENTIRE_CLEAN_COMMIT_AND_TREE_PLUS_EXPLICIT_RUNTIME_DEPENDENCIES"},
    }


def verify_protocol(path: Path) -> dict[str, Any]:
    repo = Path(__file__).resolve().parents[3]
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or path.resolve() != (repo / RELATIVE_PATH).resolve()):
        raise B2ProtocolError("B2 protocol must be its declared checked-in artifact")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise B2ProtocolError("B2 protocol is not JSON") from error
    expected = build_protocol(repo, frozen=True)
    if value != expected or raw != canonical_json_bytes(value) + b"\n":
        raise B2ProtocolError("B2 protocol is not the exact frozen source-bound contract")
    return value
