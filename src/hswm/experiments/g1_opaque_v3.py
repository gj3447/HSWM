"""Opaque-action identifiability v3: the single-owner G0-local instrument.

v3 keeps the v2 opaque task, the one-disposition local Step/Learn mechanics,
and the same no-retry journal, and adds exactly what the ratified G0-local
sub-gate requires:

* the outcome is produced by a separate salt-keyed evaluator process that
  answers one sealed-trajectory question per episode and reports its OS uid;
* candidate position is randomized and balanced 16/16 from a secret seed
  whose commitment is public, and every no-state arm is analysed by position
  stratum;
* an OUTCOME_INDEPENDENT_SHAM arm admits a disposition from a precommitted
  bit that never saw the outcome;
* every credited base-to-successor transition is committed through the real
  Atom v2 local Permit path before the compiled state is activated;
* the reveal is read by the instrument only after every behavior call of
  every episode is sealed, and the verifier proves each feedback bit with the
  evaluator salt.

A completed occurrence that satisfies the preregistered rule is a
``MEASUREMENT_READY_SINGLE_OWNER`` candidate under the declared opaque task.
It is not G0-external, not a G1 efficacy result, and not HSWM cognition,
learning, or scientific efficacy evidence.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from hashlib import sha256
import json
import time
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from hswm.experiments import atom_v2_permit_bridge, g1_micro
from hswm.experiments import g1_opaque_evaluator_process as evaluator_process
from hswm.experiments.continual_live import ChatBackend
from hswm.experiments.g1_micro import (
    G1MicroError,
    G1MicroStore,
    LOCAL_SCOPE_NONCLAIM,
    OpaquePilotArm,
    OpaquePilotTask,
    PRINCIPALS,
    STATE_OWNER,
    _atom_v2_commit_transition,
    _canonical_object,
    _digest,
    _file_manifest,
    _journal_manifest,
    _ref,
    compile_disposition,
    make_genesis_state,
    make_local_permit,
    make_permit_policy,
    make_record,
    make_state,
    state_sha256,
    validate_record,
    verify_atom_v2_commit_binding,
)
from hswm.selfmod.contracts import canonical_json_bytes, canonical_sha256


V3_PROTOCOL = "hswm-g1-opaque-identifiability-v3/v1"
V3_STUDY_UID_PREFIX = "sym:ExploratoryStudy:hswm-g1-opaque-identifiability-v3-"
EPISODE_COUNT = 32
ARMS = (
    "ACTIVE", "FORCED_OPPOSITE_FEEDBACK", "OUTCOME_INDEPENDENT_SHAM",
    "NO_UPDATE", "REMOVE", "RESTORE",
)
STATEFUL_ARMS = ("ACTIVE", "FORCED_OPPOSITE_FEEDBACK", "OUTCOME_INDEPENDENT_SHAM")
NO_STATE_ARMS = ("OUTCOME_INDEPENDENT_SHAM", "NO_UPDATE", "REMOVE")
CALL_SEQUENCE = (
    "pre_outcome_trajectory", "active_revision_proposal", "forced_opposite_revision_proposal",
    "outcome_independent_sham_revision_proposal", "active_fresh_probe",
    "forced_opposite_fresh_probe", "outcome_independent_sham_fresh_probe",
    "no_update_fresh_probe", "removed_state_fresh_probe", "restored_state_fresh_probe",
)
JOURNAL_OPERATIONS = (
    "pre_outcome_trajectory", "propose_revision", "propose_revision", "propose_revision",
    *("fresh_behavior_probe" for _ in range(6)),
)
CALLS_PER_EPISODE = len(CALL_SEQUENCE)
PROVIDER_CALL_CAP = EPISODE_COUNT * CALLS_PER_EPISODE
HTTP_POST_ACCOUNTING = {
    "completion_posts": PROVIDER_CALL_CAP,
    "tokenize_preflight_posts": PROVIDER_CALL_CAP,
    "total_posts": 2 * PROVIDER_CALL_CAP,
}
SCIENTIFIC_STATUS = "G0_LOCAL_SINGLE_OWNER_CANDIDATE_NOT_G0_EXTERNAL_NOT_G1_EFFICACY_OR_GATE"
RESEARCH_ORDER = {
    "G0_LOCAL": "CANDIDATE_NOT_PASSED_UNTIL_OCCURRENCE",
    "G0_EXTERNAL": "DEFERRED_PUBLICATION_GATE_UNTIL_SECOND_PARTY",
    "G1": "NOT_EVALUATED",
    "G2_THROUGH_G6": "LOCKED",
}
CLAIM_CEILING_IF_OBSERVED = "MEASUREMENT_READY_SINGLE_OWNER_UNDER_DECLARED_OPAQUE_TASK"
TERMINALS = (
    "INCONCLUSIVE_MEASUREMENT_NOT_READY",
    "V3_COMPLETE_G0_LOCAL_IDENTIFIABILITY_OBSERVED_NO_EFFICACY_INFERENCE",
    "V3_COMPLETE_NO_SEPARATION_NO_EFFICACY_INFERENCE",
)
WILSON_Z = 1.959963984540054
IDENTIFIABILITY_RULE = {
    "active_correct_min": 30,
    "restore_correct_min": 30,
    "forced_opposite_correct_max": 2,
    "outcome_independent_sham_correct_max": 21,
    "no_update_correct_max": 21,
    "remove_correct_max": 21,
    "no_state_arm_per_position_stratum_correct_max": 12,
    "delta_state_min": 0.5,
    "exact_remove_and_restore": EPISODE_COUNT,
    "active_credit_and_admission": EPISODE_COUNT,
    "forced_opposite_credit_and_admission": EPISODE_COUNT,
    "sham_credit_and_admission": EPISODE_COUNT,
    "atom_v2_permit_commits": 3 * EPISODE_COUNT,
    "correct_position_balance": [16, 16],
    "sham_bit_balance": [16, 16],
    "evaluator_feedback_verified": EPISODE_COUNT,
}
ANALYSIS = {
    "branch_correct_denominators": EPISODE_COUNT,
    "confirmatory_statistics": "NONE_PREREGISTERED_DESCRIPTIVE_RULE_ONLY",
    "g0_local_identifiability_rule": IDENTIFIABILITY_RULE,
    "primary_estimand": (
        "delta_state=mean_i((ACTIVE_i+RESTORE_i)/2-(FORCED_OPPOSITE_FEEDBACK_i+"
        "OUTCOME_INDEPENDENT_SHAM_i+NO_UPDATE_i+REMOVE_i)/4)"
    ),
    "secondary_estimands": [
        "six_branch_signature_rate=mean_i[ACTIVE_i=1 and RESTORE_i=1 and FORCED_OPPOSITE_FEEDBACK_i=0 and OUTCOME_INDEPENDENT_SHAM_i=sham_disposition_correct_i and NO_UPDATE_i=0 and REMOVE_i=0]",
        "ACTIVE-minus-FORCED_OPPOSITE_FEEDBACK",
        "ACTIVE-minus-OUTCOME_INDEPENDENT_SHAM",
        "ACTIVE-minus-mean(NO_UPDATE,REMOVE)",
        "RESTORE-minus-REMOVE",
        "branch_correct_counts_with_Wilson_95_percent_intervals",
        "no_state_correct_counts_stratified_by_correct_candidate_position",
        "credit_and_admission_counts_per_stateful_arm",
        "atom_v2_permit_commit_count",
        "exact_remove_and_restore_count",
    ],
    "terminal_order": list(TERMINALS),
    "wilson_z": WILSON_Z,
}
PERMIT_POLICY = {
    "grant_timing": "AFTER_OUTCOME_CREDIT_AND_EXACT_PROPOSAL_UNDER_PREOUTCOME_POLICY",
    "max_consumptions_per_grant": 1,
    "revision_kind": "OPAQUE_ACTION_CODE_DISPOSITION",
    "write_operation": "UPSERT_ONE_DISPOSITION",
    "write_target": "local:g1-micro-state:dispositions",
}
LEAKAGE_CONTRACT = {
    "branch_labels_model_visible": False,
    "forbidden_request_substrings": [
        "correct_action_code", "leakage_canary", "salt", "evaluator_feedback", "feedback_mac",
        "sham_feedback_correct", "reveal_commitment", "seed_commitment",
    ],
    "model_visible_task_fields": ["cue", "action_codes", "compiled_disposition", "trajectory_action_code", "feedback_correct"],
    "required_checks": [
        "Every raw generation and tokenizer request preimage is scanned before result sealing and again with the reveal salts and canaries after the reveal is attached.",
        "The actor process never reads the evaluator reveal before every behavior call of every episode is sealed.",
        "REMOVE compiles the exact genesis state and uses the same candidate order as ACTIVE, FORCED_OPPOSITE_FEEDBACK, OUTCOME_INDEPENDENT_SHAM, and RESTORE; NO_UPDATE is the opposite-order position sentinel.",
        "All branch calls use the same operation schemas without a model-visible arm label.",
    ],
}
PROSE = {
    "canonical_role": "A single-owner G0-local occurrence asking whether the local outcome-credit-Permit-admission-fresh-probe-remove-restore instrument produces a state-mediated signature when the outcome is produced by a separate salt-keyed evaluator process, candidate position is randomized and balanced, an outcome-independent sham disposition is admitted alongside the outcome-bound one, and every admission crosses the real Atom v2 local Permit path.",
    "conceptual_delta": "Replace the same-process evaluator, fixed candidate positions, and experiment-local grant of v2 with a separate-process keyed evaluator, seeded position balance, an outcome-independent sham arm, and a real local Permit commit per admission, while keeping the opaque task and the eight-call mechanics otherwise unchanged.",
    "control_boundary": "FORCED_OPPOSITE_FEEDBACK is an outcome-dependent counterfactual control. OUTCOME_INDEPENDENT_SHAM is the outcome-independent sham: its feedback bit is precommitted in the protocol and its admitted disposition is correct only by chance. NO_UPDATE and REMOVE are no-state controls. None of these is a reuse-first comparator; a later G1 still requires the full control family and comparators under D-3.",
    "current_evidence": "The 2026-08-30 opaque v2 occurrence observed ACTIVE and RESTORE at 8/8, FORCED_OPPOSITE_FEEDBACK at 0/8, and NO_UPDATE and REMOVE at 4/8 with a first-candidate position bias, using a same-process evaluator and an experiment-local grant. G0 is NOT_PASSED and G1 is LOCKED.",
    "state_intervention": "One cue-bound opaque action-code disposition is behavior-readable per stateful arm and episode. REMOVE activates the ACTIVE store's exact empty genesis state; RESTORE reactivates the exact ACTIVE state bytes. Audit records, evaluator feedback, and Permit receipts are outside the model behavior readset.",
    "stopping_rule": "Exactly thirty-two precommitted episodes in ordinal order with ten calls each. No retry, replacement, refill, resume, adaptive selection, partial-look adaptation, or second occurrence. A schema-valid proposal that does not follow its feedback rule is retained as NO_CREDIT/NO_ADMISSION and the episode continues. Any call, parse, evaluator, Permit, or structural failure aborts the study, preserves the exact prefix, consumes the registry, and yields INCONCLUSIVE_MEASUREMENT_NOT_READY. A VOID is repaired and rerun within 24 hours under this protocol family, never as a new instrument family.",
    "evaluator_custody": "The evaluator reveal is generated with the protocol from a secret seed whose SHA-256 commitment is public. It is held only by the evaluator OS user, unreadable by the actor process, and loaded by the evaluator process before the registry claim. The actor instrument reads the reveal only after every behavior call is sealed; the runtime binding records SEPARATE_OS_USER or SAME_OS_USER from the evaluator's reported uid.",
}
PROTOCOL_FIELDS = {
    "analysis", "arms", "atom_v2_permit_commit", "canonical_role", "claim_ceiling_if_observed",
    "conceptual_delta", "consumption_registry", "control_boundary", "current_evidence",
    "episode_count", "episodes", "evaluator_boundary", "evaluator_custody",
    "evaluator_reveal_contract", "freeze", "generation", "http_post_accounting",
    "leakage_contract", "live_binding", "model_call_sequence_per_episode", "nonclaim",
    "permit_policy", "provider_call_cap", "research_order", "schema_version",
    "scientific_status", "state_intervention", "stopping_rule", "study_uid", "tokenizer_binding",
}
EPISODE_FIELDS = {
    "action_codes", "cue", "episode_uid", "evaluator_commitment_sha256", "no_update_action_order",
    "ordinal", "remove_action_order", "sham_feedback_correct", "stateful_probe_action_order",
    "trajectory_action_order",
}
LIVE_BINDING_FIELDS = {
    "async_scheduling", "container_image", "container_image_id", "enforce_eager", "endpoint_origin",
    "expected_max_model_len", "gpu_memory_utilization_milli", "gpu_name", "gpu_uuid", "max_num_seqs",
    "model_repository", "model_revision", "model_snapshot_manifest_sha256", "network_boundary",
    "prefix_cache", "served_model", "vllm_version",
}
_ACTION_CODE = re.compile(r"act_[0-9a-f]{8}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class OpaqueV3Task(OpaquePilotTask):
    """Public task view for the actor: no correct code, salt, or canary."""

    sham_feedback_correct: bool = False
    precommitted_commitment_sha256: str = ""

    @property
    def commitment_sha256(self) -> str:  # type: ignore[override]
        return self.precommitted_commitment_sha256


# ---------------------------------------------------------------------------
# Deterministic generation from a secret seed
# ---------------------------------------------------------------------------


def _hex(seed: bytes, *labels: str) -> str:
    return sha256(seed + b"|" + "|".join(labels).encode("utf-8")).hexdigest()


def _permutation(seed: bytes, label: str, count: int) -> list[int]:
    order = list(range(count))
    for index in range(count - 1, 0, -1):
        swap = int(_hex(seed, label, str(index)), 16) % (index + 1)
        order[index], order[swap] = order[swap], order[index]
    return order


def _balanced_bits(seed: bytes, label: str, count: int) -> list[bool]:
    bits = [True] * (count // 2) + [False] * (count - count // 2)
    return [bits[index] for index in _permutation(seed, label, count)]


CANDIDATE_PAIRS_PER_EPISODE = 32


def v3_code_pool(seed: bytes) -> dict[str, list[list[str]]]:
    """Public, seed-derived candidate action-code pairs per episode ordinal.

    Candidate index 0 is the historical single derivation; later indexes extend
    it so the freeze can select the first pair whose two codes have equal
    standalone offline token counts.  The pool carries no secret: which pair
    is selected depends only on the public measurement, and which code is
    correct is derived separately from the seed.
    """

    if not isinstance(seed, bytes) or len(seed) < 32:
        raise G1MicroError("v3 seed must be at least 32 bytes")
    pool: dict[str, list[list[str]]] = {}
    for ordinal in range(1, EPISODE_COUNT + 1):
        label = str(ordinal)
        pairs: list[list[str]] = []
        for index in range(CANDIDATE_PAIRS_PER_EPISODE):
            tag = label if index == 0 else f"{label}:{index}"
            pairs.append(["act_" + _hex(seed, "code-a", tag)[:8], "act_" + _hex(seed, "code-b", tag)[:8]])
        pool[label] = pairs
    return pool


def _select_pair(
    pairs: list[list[str]], *, ordinal: int, used: set[str], token_counts: Mapping[str, int] | None
) -> tuple[list[str], int]:
    for index, (code_a, code_b) in enumerate(pairs):
        if code_a == code_b or code_a in used or code_b in used:
            continue
        if token_counts is None:
            return [code_a, code_b], index
        count_a, count_b = token_counts.get(code_a), token_counts.get(code_b)
        if isinstance(count_a, int) and isinstance(count_b, int) and count_a > 0 and count_a == count_b:
            return [code_a, code_b], index
    if token_counts is None:
        raise G1MicroError("v3 seed produced colliding action codes; choose another seed")
    raise G1MicroError(f"v3 episode {ordinal} has no candidate pair with equal offline token counts; choose another seed")


def generate_v3(
    *,
    seed: bytes,
    study_date: str,
    live_binding: Mapping[str, Any],
    tokenizer_model: Mapping[str, str],
    consumption_registry_path: str,
    token_counts: Mapping[str, int] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (public protocol, secret evaluator reveal) for one seed.

    With ``token_counts`` (public standalone offline token counts of the
    seed-derived candidate pool) each episode takes the first candidate pair
    whose codes tokenize to equal counts, so the freeze precondition holds by
    construction.  Without it the first candidate is used (tests only).
    """

    if not isinstance(seed, bytes) or len(seed) < 32:
        raise G1MicroError("v3 seed must be at least 32 bytes")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", study_date):
        raise G1MicroError("v3 study date must be YYYY-MM-DD")
    if set(live_binding) != LIVE_BINDING_FIELDS:
        raise G1MicroError("v3 live binding field set drifted")
    positions = _balanced_bits(seed, "correct-position", EPISODE_COUNT)
    sham_bits = _balanced_bits(seed, "sham-bit", EPISODE_COUNT)
    study_uid = f"{V3_STUDY_UID_PREFIX}{study_date}"
    pool = v3_code_pool(seed)
    episodes: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    used: set[str] = set()
    selected_indexes: list[int] = []
    for ordinal in range(1, EPISODE_COUNT + 1):
        label = str(ordinal)
        uid8 = _hex(seed, "episode", label)[:8]
        (code_a, code_b), selected = _select_pair(pool[label], ordinal=ordinal, used=used, token_counts=token_counts)
        selected_indexes.append(selected)
        used.update((code_a, code_b))
        correct, other = (code_a, code_b) if int(_hex(seed, "correct", label)[0], 16) < 8 else (code_b, code_a)
        stateful = [correct, other] if positions[ordinal - 1] else [other, correct]
        trajectory_order = [code_a, code_b] if int(_hex(seed, "trajectory-order", label)[0], 16) < 8 else [code_b, code_a]
        entry = {
            "correct_action_code": correct,
            "episode_uid": f"episode:opaque-v3-{uid8}",
            "leakage_canary": "canary_" + _hex(seed, "canary", label)[:12],
            "ordinal": ordinal,
            "salt": _hex(seed, "salt", label)[:32],
        }
        entries.append(entry)
        episodes.append({
            "action_codes": [code_a, code_b],
            "cue": f"cue_{uid8}",
            "episode_uid": entry["episode_uid"],
            "evaluator_commitment_sha256": canonical_sha256(entry),
            "no_update_action_order": list(reversed(stateful)),
            "ordinal": ordinal,
            "remove_action_order": list(stateful),
            "sham_feedback_correct": sham_bits[ordinal - 1],
            "stateful_probe_action_order": list(stateful),
            "trajectory_action_order": trajectory_order,
        })
    root = canonical_sha256({"episode_commitments": [item["evaluator_commitment_sha256"] for item in episodes]})
    protocol = {
        "schema_version": V3_PROTOCOL,
        "study_uid": study_uid,
        "episode_count": EPISODE_COUNT,
        "episodes": episodes,
        "arms": list(ARMS),
        "model_call_sequence_per_episode": list(CALL_SEQUENCE),
        "provider_call_cap": PROVIDER_CALL_CAP,
        "http_post_accounting": dict(HTTP_POST_ACCOUNTING),
        "analysis": json.loads(json.dumps(ANALYSIS)),
        "permit_policy": dict(PERMIT_POLICY),
        "atom_v2_permit_commit": {
            "required": True,
            "contract_version": atom_v2_permit_bridge.CONTRACT_VERSION,
            "claim_boundary": atom_v2_permit_bridge.CLAIM_BOUNDARY,
        },
        "evaluator_boundary": evaluator_process.EVALUATOR_BOUNDARY,
        "evaluator_reveal_contract": {
            "entry_commitment_formula": "canonical_sha256({ordinal,episode_uid,correct_action_code,salt,leakage_canary})",
            "root_formula": f"canonical_sha256({{episode_commitments:[ordered {EPISODE_COUNT} entry commitments]}})",
            "reveal_commitment_root": root,
            "reveal_schema_version": evaluator_process.REVEAL_SCHEMA,
            "protocol_binding": "Reveal outer object must contain this protocol canonical SHA-256 after protocol freeze; the commitment root excludes that outer binding to avoid a circular digest.",
            "custody": "SEPARATE_PROCESS_SEPARATE_OS_USER_REQUIRED_FOR_LIVE_OCCURRENCE",
            "timing": "Loaded by the evaluator process before the registry claim; read by the actor instrument only after every behavior call of every episode is sealed.",
        },
        "leakage_contract": json.loads(json.dumps(LEAKAGE_CONTRACT)),
        "scientific_status": SCIENTIFIC_STATUS,
        "research_order": dict(RESEARCH_ORDER),
        "claim_ceiling_if_observed": CLAIM_CEILING_IF_OBSERVED,
        "nonclaim": LOCAL_SCOPE_NONCLAIM,
        "consumption_registry": {"path": consumption_registry_path},
        "live_binding": dict(live_binding),
        "tokenizer_binding": {
            "status": "PENDING_DGX_OFFLINE_MEASUREMENT",
            "condition": "PAIRWISE_EQUAL_STANDALONE_ACTION_CODE_TOKEN_COUNTS_BEFORE_REGISTRY_CLAIM",
            "container_image": tokenizer_model["container_image"],
            "container_image_id": tokenizer_model["container_image_id"],
            "model_repository": tokenizer_model["model_repository"],
            "model_revision": tokenizer_model["model_revision"],
            "snapshot_manifest_sha256": tokenizer_model["snapshot_manifest_sha256"],
            "episodes": [],
            "interpretation_boundary": "Pairwise equal standalone token counts reduce a length cue; they do not prove semantic opacity or exchangeability.",
        },
        "generation": {
            "generator": "scripts/generate_hswm_g1_opaque_v3.py",
            "seed_commitment_sha256": sha256(seed).hexdigest(),
            "correct_position_balance": [sum(positions), EPISODE_COUNT - sum(positions)],
            "sham_bit_balance": [sum(sham_bits), EPISODE_COUNT - sum(sham_bits)],
            "seed_custody": "The seed and the derived reveal are held only by the evaluator OS user; the public protocol carries the seed commitment and the reveal commitment root.",
            "code_selection": {
                "candidates_per_episode": CANDIDATE_PAIRS_PER_EPISODE,
                "pool_sha256": canonical_sha256(pool),
                "rule": (
                    "FIRST_SEED_ORDERED_CANDIDATE_PAIR_WITH_EQUAL_OFFLINE_TOKEN_COUNTS"
                    if token_counts is not None else "FIRST_SEED_ORDERED_CANDIDATE_PAIR_UNMEASURED"
                ),
                "selected_candidate_index": selected_indexes,
                "token_counts_sha256": None if token_counts is None else canonical_sha256(dict(token_counts)),
            },
        },
        "freeze": {"status": "DRAFT_NOT_FROZEN"},
        **PROSE,
    }
    reveal = {
        "episodes": entries,
        "protocol_canonical_sha256": canonical_sha256(protocol),
        "reveal_commitment_root": root,
        "schema_version": evaluator_process.REVEAL_SCHEMA,
        "study_uid": study_uid,
    }
    validate_v3_protocol(protocol)
    return protocol, reveal


# ---------------------------------------------------------------------------
# Validation and tasks
# ---------------------------------------------------------------------------


def validate_v3_protocol(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping) or set(value) != PROTOCOL_FIELDS or value["schema_version"] != V3_PROTOCOL:
        raise G1MicroError("v3 protocol field set or schema drifted")
    if not isinstance(value["study_uid"], str) or not value["study_uid"].startswith(V3_STUDY_UID_PREFIX):
        raise G1MicroError("v3 study uid drifted")
    episodes = value["episodes"]
    if value["episode_count"] != EPISODE_COUNT or not isinstance(episodes, list) or len(episodes) != EPISODE_COUNT:
        raise G1MicroError("v3 requires exactly thirty-two preregistered episodes")
    uids: set[str] = set()
    codes: set[str] = set()
    sham_true = 0
    commitments: list[str] = []
    for ordinal, episode in enumerate(episodes, start=1):
        if (
            not isinstance(episode, Mapping) or set(episode) != EPISODE_FIELDS or episode["ordinal"] != ordinal
            or not isinstance(episode["cue"], str) or not isinstance(episode["episode_uid"], str)
            or episode["episode_uid"] in uids or not isinstance(episode["action_codes"], list)
            or len(episode["action_codes"]) != 2 or len(set(episode["action_codes"])) != 2
            or any(not isinstance(code, str) or not _ACTION_CODE.fullmatch(code) for code in episode["action_codes"])
            or type(episode["sham_feedback_correct"]) is not bool
        ):
            raise G1MicroError("v3 public episode contract drifted")
        if any(code in codes for code in episode["action_codes"]):
            raise G1MicroError("v3 action codes must be unique across episodes")
        codes.update(episode["action_codes"])
        uids.add(episode["episode_uid"])
        if not isinstance(episode["evaluator_commitment_sha256"], str) or not _SHA256.fullmatch(episode["evaluator_commitment_sha256"]):
            raise G1MicroError("v3 evaluator commitment is invalid")
        commitments.append(episode["evaluator_commitment_sha256"])
        for key in ("no_update_action_order", "remove_action_order", "stateful_probe_action_order", "trajectory_action_order"):
            if list(episode[key]) not in (episode["action_codes"], episode["action_codes"][::-1]):
                raise G1MicroError("v3 candidate orders must permute the episode codes")
        if episode["no_update_action_order"] != episode["stateful_probe_action_order"][::-1] or episode["remove_action_order"] != episode["stateful_probe_action_order"]:
            raise G1MicroError("v3 candidate order counterbalance drifted")
        sham_true += int(episode["sham_feedback_correct"])
    if sham_true != EPISODE_COUNT // 2:
        raise G1MicroError("v3 sham bits must be balanced 16/16")
    if value["evaluator_reveal_contract"]["reveal_commitment_root"] != canonical_sha256({"episode_commitments": commitments}):
        raise G1MicroError("v3 reveal commitment root does not match the public commitments")
    if (
        value["arms"] != list(ARMS) or value["model_call_sequence_per_episode"] != list(CALL_SEQUENCE)
        or value["provider_call_cap"] != PROVIDER_CALL_CAP or value["http_post_accounting"] != HTTP_POST_ACCOUNTING
        or value["analysis"] != json.loads(json.dumps(ANALYSIS)) or value["permit_policy"] != PERMIT_POLICY
        or value["leakage_contract"] != json.loads(json.dumps(LEAKAGE_CONTRACT))
        or value["scientific_status"] != SCIENTIFIC_STATUS or value["research_order"] != RESEARCH_ORDER
        or value["claim_ceiling_if_observed"] != CLAIM_CEILING_IF_OBSERVED or value["nonclaim"] != LOCAL_SCOPE_NONCLAIM
        or value["evaluator_boundary"] != evaluator_process.EVALUATOR_BOUNDARY
        or any(value.get(key) != text for key, text in PROSE.items())
    ):
        raise G1MicroError("v3 fixed scientific, procedural, or accounting contract drifted")
    commit = value["atom_v2_permit_commit"]
    if commit != {"required": True, "contract_version": atom_v2_permit_bridge.CONTRACT_VERSION, "claim_boundary": atom_v2_permit_bridge.CLAIM_BOUNDARY}:
        raise G1MicroError("v3 requires the Atom v2 local Permit commit for every admission")
    registry = value["consumption_registry"]
    if not isinstance(registry, Mapping) or set(registry) != {"path"} or not isinstance(registry["path"], str) or not registry["path"]:
        raise G1MicroError("v3 consumption registry drifted")
    if not isinstance(value["live_binding"], Mapping) or set(value["live_binding"]) != LIVE_BINDING_FIELDS:
        raise G1MicroError("v3 live binding field set drifted")
    tokenizer = value["tokenizer_binding"]
    if not isinstance(tokenizer, Mapping) or tokenizer.get("status") not in {"PENDING_DGX_OFFLINE_MEASUREMENT", "MEASURED"}:
        raise G1MicroError("v3 tokenizer binding status drifted")
    if tokenizer["status"] == "MEASURED" and (not isinstance(tokenizer.get("episodes"), list) or len(tokenizer["episodes"]) != EPISODE_COUNT):
        raise G1MicroError("v3 measured tokenizer binding must cover every episode")
    generation = value["generation"]
    if (
        not isinstance(generation, Mapping) or not _SHA256.fullmatch(str(generation.get("seed_commitment_sha256", "")))
        or generation.get("correct_position_balance") != [16, 16] or generation.get("sham_bit_balance") != [16, 16]
    ):
        raise G1MicroError("v3 generation record drifted")
    if value["freeze"].get("status") not in {"DRAFT_NOT_FROZEN", "FROZEN"}:
        raise G1MicroError("v3 freeze status drifted")


def v3_tasks(protocol: Mapping[str, Any]) -> tuple[OpaqueV3Task, ...]:
    validate_v3_protocol(protocol)
    return tuple(
        OpaqueV3Task(
            study_uid=str(protocol["study_uid"]), ordinal=int(item["ordinal"]),
            episode_uid=str(item["episode_uid"]), cue=str(item["cue"]),
            action_codes=(str(item["action_codes"][0]), str(item["action_codes"][1])),
            correct_action_code="", salt="", canary="",
            orders={key: list(item[key]) for key in ("trajectory_action_order", "stateful_probe_action_order", "no_update_action_order", "remove_action_order")},
            sham_feedback_correct=bool(item["sham_feedback_correct"]),
            precommitted_commitment_sha256=str(item["evaluator_commitment_sha256"]),
        )
        for item in protocol["episodes"]
    )


def load_v3_protocol(path: str | Path) -> tuple[dict[str, Any], str]:
    """Load a pretty-printed or canonical protocol file; the digest is always canonical."""

    try:
        value = json.loads(Path(path).read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise G1MicroError("v3 protocol is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise G1MicroError("v3 protocol must be one JSON object")
    validate_v3_protocol(value)
    return value, canonical_sha256(value)


# ---------------------------------------------------------------------------
# One episode
# ---------------------------------------------------------------------------


def _record(kind: str, task: OpaqueV3Task, payload: Mapping[str, Any], refs: Sequence[Mapping[str, str]] = ()) -> dict[str, Any]:
    return make_record(kind, owner_uid=PRINCIPALS["outcome_evaluator_uid"], payload={"episode_uid": task.episode_uid, **payload}, refs=refs)


def _other(task: OpaqueV3Task, code: str) -> str:
    if code not in task.action_codes:
        raise G1MicroError("v3 action code is outside its episode")
    return next(item for item in task.action_codes if item != code)


def _scan_requests(path: Path, forbidden: Sequence[str]) -> None:
    for line in path.read_bytes().splitlines():
        row = _canonical_object(line, "v3 journal row")
        texts: list[str] = []
        raw = row.get("raw_request_json")
        if isinstance(raw, str):
            texts.append(raw)
        raw64 = row.get("raw_request_base64")
        if isinstance(raw64, str):
            try:
                texts.append(base64.b64decode(raw64, validate=True).decode("utf-8", "strict"))
            except (binascii.Error, UnicodeDecodeError) as error:
                raise G1MicroError("v3 raw request preimage is malformed") from error
        for text in texts:
            if any(secret and secret in text for secret in forbidden):
                raise G1MicroError("evaluator-only content leaked into a model request")


def _episode(
    *,
    backend: ChatBackend,
    task: OpaqueV3Task,
    output: Path,
    protocol_sha256: str,
    evaluator: evaluator_process.EvaluatorEndpoint,
    permit_commit: atom_v2_permit_bridge.LocalPermitCommitProcess,
) -> dict[str, Any]:
    output.mkdir(parents=True)
    arm = OpaquePilotArm(backend=backend, journal_path=output / "attempt_ledger.jsonl", isolation_id=task.episode_uid)
    trajectory, trajectory_evidence = arm.trajectory(task)
    trajectory_record = make_record(
        "SealedTrajectory", owner_uid=PRINCIPALS["executor_uid"],
        payload={"episode_uid": task.episode_uid, "action_code": trajectory, "call_evidence": trajectory_evidence},
    )
    feedback = evaluator.call(
        study_uid=task.study_uid, protocol_sha256=protocol_sha256, episode_uid=task.episode_uid,
        trajectory_sha256=trajectory_record["record_sha256"], action_code=trajectory,
    )
    actual = bool(feedback["choice_was_correct"])
    separation = evaluator_process.EvaluatorEndpoint.separation(feedback)
    outcome = _record(
        "OpaqueOutcome", task,
        {"choice_was_correct": actual, "evaluator_feedback": dict(feedback), "evaluator_separation": separation},
        (_ref("trajectory", trajectory_record),),
    )
    forced_record = _record(
        "ForcedOppositeFeedback", task,
        {"choice_was_correct": not actual, "derived_from_outcome_sha256": outcome["record_sha256"]},
        (_ref("outcome", outcome),),
    )
    sham_record = _record(
        "OutcomeIndependentShamFeedback", task,
        {"choice_was_correct": task.sham_feedback_correct, "precommitted_in_protocol": True},
        (_ref("trajectory", trajectory_record),),
    )
    proposals = {
        "ACTIVE": (arm.propose(task, trajectory_code=trajectory, feedback_correct=actual), outcome, actual),
        "FORCED_OPPOSITE_FEEDBACK": (arm.propose(task, trajectory_code=trajectory, feedback_correct=not actual), forced_record, not actual),
        "OUTCOME_INDEPENDENT_SHAM": (arm.propose(task, trajectory_code=trajectory, feedback_correct=task.sham_feedback_correct), sham_record, task.sham_feedback_correct),
    }
    stores = {branch: G1MicroStore(output / f"{branch.lower()}.sqlite3") for branch in STATEFUL_ARMS}

    def admission(branch: str) -> dict[str, Any]:
        (code, call_evidence), feedback_record, bit = proposals[branch]
        store = stores[branch]
        proposal = make_record(
            "RevisionProposal", owner_uid=PRINCIPALS["proposer_uid"],
            payload={"action_code": code, "branch": branch, "call_evidence": dict(call_evidence), "revision_kind": "OPAQUE_ACTION_CODE_DISPOSITION"},
            refs=(_ref("trajectory", trajectory_record), _ref("feedback", feedback_record)),
        )
        expected = trajectory if bit else _other(task, trajectory)
        credit = make_record(
            "CreditDecision", owner_uid=PRINCIPALS["credit_adjudicator_uid"],
            payload={"decision": "CREDIT" if code == expected else "NO_CREDIT", "expected_action_code": expected, "proposed_action_code": code},
            refs=(_ref("trajectory", trajectory_record), _ref("feedback", feedback_record), _ref("proposal", proposal)),
        )
        if code != expected:
            return {"proposal": proposal, "credit": credit, "admission": None}
        disposition = g1_micro._opaque_disposition(task, code, trajectory=trajectory_record, feedback=feedback_record, proposal=proposal, credit=credit)
        successor = make_state([disposition])
        policy = make_permit_policy(task, protocol_sha256)
        base = store.active()
        permit = make_local_permit(
            task=task, permit_policy=policy, base_state=base.state, base_generation=base.generation,
            trajectory=trajectory_record, feedback=feedback_record, proposal=proposal, credit=credit,
            disposition=disposition, successor_state=successor,
        )
        store.issue_permit(permit, permit_policy=policy)
        commit = _atom_v2_commit_transition(
            permit_commit, commit_root=output / "atom-v2-permit-commit" / branch.lower(),
            episode_uid=task.episode_uid, branch=branch, base_state=base.state, successor_state=successor,
            permit=permit, permit_policy=policy, proposal=proposal, disposition=disposition,
        )
        receipts = store.admit(permit=permit, proposal=proposal, feedback=feedback_record, credit=credit, successor_state=successor)
        return {
            "proposal": proposal, "credit": credit, "admission": receipts, "disposition": disposition,
            "permit_policy": policy, "permit": permit, "successor_state": successor, "atom_v2_permit_commit": commit,
        }

    dispositions = {branch: admission(branch) for branch in STATEFUL_ARMS}
    probes: dict[str, dict[str, Any]] = {}

    def observe(branch: str, state: Mapping[str, Any], order: Sequence[str]) -> None:
        compiled = compile_disposition(state, cue=task.cue)
        observed, evidence = arm.probe(task, compiled, order=order)
        probes[branch] = _record("OpaqueFreshBehaviorObservation", task, {
            "branch": branch, "call_evidence": evidence, "choice": observed, "candidate_order": list(order),
            "compiled_disposition": compiled, "state_sha256": state_sha256(state),
        })

    stateful_order = task.orders["stateful_probe_action_order"]
    observe("ACTIVE", stores["ACTIVE"].active().state, stateful_order)
    observe("FORCED_OPPOSITE_FEEDBACK", stores["FORCED_OPPOSITE_FEEDBACK"].active().state, stateful_order)
    observe("OUTCOME_INDEPENDENT_SHAM", stores["OUTCOME_INDEPENDENT_SHAM"].active().state, stateful_order)
    observe("NO_UPDATE", make_genesis_state(), task.orders["no_update_action_order"])
    remove_receipt = restore_receipt = None
    active = dispositions["ACTIVE"]
    if active["admission"] is not None:
        store = stores["ACTIVE"]
        pointer = store.active()
        snapshot_sha = pointer.state_sha256
        source = active["admission"]["admission"]["record_sha256"]
        remove_receipt = store.activate_exact(state_sha256(make_genesis_state()), expected_generation=pointer.generation, operation="REMOVE_TO_GENESIS", source_admission_sha256=source)
        observe("REMOVE", store.active().state, task.orders["remove_action_order"])
        restore_receipt = store.activate_exact(snapshot_sha, expected_generation=store.active().generation, operation="RESTORE_ACTIVE_SNAPSHOT", source_admission_sha256=source)
        observe("RESTORE", store.active().state, stateful_order)
    else:
        observe("REMOVE", make_genesis_state(), task.orders["remove_action_order"])
        observe("RESTORE", make_genesis_state(), stateful_order)
    journal = _journal_manifest(output / "attempt_ledger.jsonl", expected_operations=JOURNAL_OPERATIONS)
    if journal["completed_calls"] != CALLS_PER_EPISODE or not journal["raw_preimages_valid"] or not journal["operation_order_valid"] or journal["failure_events"] or not journal["all_rows_accounted"]:
        raise G1MicroError("v3 episode call chronology drifted")
    _scan_requests(output / "attempt_ledger.jsonl", LEAKAGE_CONTRACT["forbidden_request_substrings"])
    for store in stores.values():
        store.checkpoint()
    return {
        "episode_uid": task.episode_uid,
        "task_commitment_sha256": task.commitment_sha256,
        "trajectory": trajectory_record,
        "outcome": outcome,
        "forced_opposite_feedback": forced_record,
        "sham_feedback": sham_record,
        "evaluator_separation": separation,
        "dispositions": dispositions,
        "state_interventions": {"REMOVE": remove_receipt, "RESTORE": restore_receipt},
        "state_store_artifacts": _file_manifest(tuple(output / f"{branch.lower()}.sqlite3" for branch in STATEFUL_ARMS)),
        "store_receipts": {branch: stores[branch].logical_receipts() for branch in STATEFUL_ARMS},
        "probes": probes,
        "journal": journal,
    }


# ---------------------------------------------------------------------------
# Post-seal scoring and metrics
# ---------------------------------------------------------------------------


def _wilson(count: int, n: int) -> list[float]:
    z = WILSON_Z
    p = count / n
    scale = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / scale
    radius = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / scale
    return [centre - radius, centre + radius]


def score_episodes(episodes: Sequence[Mapping[str, Any]], *, protocol: Mapping[str, Any], reveal: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Score sealed episodes with the attached reveal; verify each feedback bit's salt key."""

    if reveal["study_uid"] != protocol["study_uid"] or reveal["reveal_commitment_root"] != protocol["evaluator_reveal_contract"]["reveal_commitment_root"]:
        raise G1MicroError("v3 reveal does not bind this protocol")
    entries = {item["episode_uid"]: item for item in reveal["episodes"]}
    public = {item["episode_uid"]: item for item in protocol["episodes"]}
    scores: list[dict[str, Any]] = []
    for episode in episodes:
        uid = episode["episode_uid"]
        entry = entries[uid]
        item = public[uid]
        if canonical_sha256(entry) != item["evaluator_commitment_sha256"]:
            raise G1MicroError("v3 reveal entry does not match its public commitment")
        correct = entry["correct_action_code"]
        feedback = episode["outcome"]["payload"]["evaluator_feedback"]
        evaluator_process.verify_feedback(feedback, reveal=reveal)
        trajectory = episode["trajectory"]
        if feedback["trajectory_sha256"] != trajectory["record_sha256"] or feedback["action_code"] != trajectory["payload"]["action_code"]:
            raise G1MicroError("v3 evaluator feedback does not bind the sealed trajectory")
        if episode["outcome"]["payload"]["choice_was_correct"] is not (trajectory["payload"]["action_code"] == correct):
            raise G1MicroError("v3 outcome disagrees with the reveal")
        probe_scores: dict[str, Any] = {}
        for branch, probe in episode["probes"].items():
            payload = probe["payload"]
            order = list(payload["candidate_order"])
            probe_scores[branch] = {
                "correct": payload["choice"] == correct,
                "correct_position": order.index(correct) + 1,
            }
        sham = episode["dispositions"]["OUTCOME_INDEPENDENT_SHAM"]
        sham_code = None if sham["admission"] is None else sham["disposition"]["payload"]["action_code"]
        scores.append({
            "episode_uid": uid,
            "correct_action_code": correct,
            "correct_position_stateful": list(item["stateful_probe_action_order"]).index(correct) + 1,
            "sham_disposition_correct": None if sham_code is None else sham_code == correct,
            "probes": probe_scores,
            "evaluator_feedback_verified": True,
            "evaluator_separation": episode["evaluator_separation"],
        })
    return scores


def v3_metrics(episodes: Sequence[Mapping[str, Any]], scores: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(episodes)
    counts = {arm: sum(int(score["probes"][arm]["correct"]) for score in scores) for arm in ARMS}
    admissions = {
        arm: sum(int(episode["dispositions"][arm]["admission"] is not None) for episode in episodes) for arm in STATEFUL_ARMS
    }
    commits = sum(
        int("atom_v2_permit_commit" in episode["dispositions"][arm]) for episode in episodes for arm in STATEFUL_ARMS
    )
    transitions = sum(
        int(episode["state_interventions"]["REMOVE"] is not None and episode["state_interventions"]["RESTORE"] is not None)
        for episode in episodes
    )
    by_position = {
        arm: {
            str(position): sum(int(score["probes"][arm]["correct"]) for score in scores if score["probes"][arm]["correct_position"] == position)
            for position in (1, 2)
        }
        for arm in NO_STATE_ARMS
    }
    stratum_sizes = {
        arm: {str(position): sum(1 for score in scores if score["probes"][arm]["correct_position"] == position) for position in (1, 2)}
        for arm in NO_STATE_ARMS
    }
    delta = sum(
        (int(s["probes"]["ACTIVE"]["correct"]) + int(s["probes"]["RESTORE"]["correct"])) / 2
        - (int(s["probes"]["FORCED_OPPOSITE_FEEDBACK"]["correct"]) + int(s["probes"]["OUTCOME_INDEPENDENT_SHAM"]["correct"]) + int(s["probes"]["NO_UPDATE"]["correct"]) + int(s["probes"]["REMOVE"]["correct"])) / 4
        for s in scores
    ) / n
    signature = sum(
        int(
            s["probes"]["ACTIVE"]["correct"] and s["probes"]["RESTORE"]["correct"]
            and not s["probes"]["FORCED_OPPOSITE_FEEDBACK"]["correct"]
            and s["probes"]["OUTCOME_INDEPENDENT_SHAM"]["correct"] == bool(s["sham_disposition_correct"])
            and not s["probes"]["NO_UPDATE"]["correct"] and not s["probes"]["REMOVE"]["correct"]
        )
        for s in scores
    )
    positions = [sum(1 for s in scores if s["correct_position_stateful"] == 1), sum(1 for s in scores if s["correct_position_stateful"] == 2)]
    feedback_verified = sum(int(s["evaluator_feedback_verified"]) for s in scores)
    separated = sum(int(s["evaluator_separation"] == "SEPARATE_OS_USER") for s in scores)
    rule = IDENTIFIABILITY_RULE
    observed = (
        n == EPISODE_COUNT
        and counts["ACTIVE"] >= rule["active_correct_min"] and counts["RESTORE"] >= rule["restore_correct_min"]
        and counts["FORCED_OPPOSITE_FEEDBACK"] <= rule["forced_opposite_correct_max"]
        and counts["OUTCOME_INDEPENDENT_SHAM"] <= rule["outcome_independent_sham_correct_max"]
        and counts["NO_UPDATE"] <= rule["no_update_correct_max"] and counts["REMOVE"] <= rule["remove_correct_max"]
        and all(by_position[arm][pos] <= rule["no_state_arm_per_position_stratum_correct_max"] for arm in NO_STATE_ARMS for pos in ("1", "2"))
        and delta >= rule["delta_state_min"] and transitions == rule["exact_remove_and_restore"]
        and admissions["ACTIVE"] == rule["active_credit_and_admission"]
        and admissions["FORCED_OPPOSITE_FEEDBACK"] == rule["forced_opposite_credit_and_admission"]
        and admissions["OUTCOME_INDEPENDENT_SHAM"] == rule["sham_credit_and_admission"]
        and commits == rule["atom_v2_permit_commits"] and positions == rule["correct_position_balance"]
        and feedback_verified == rule["evaluator_feedback_verified"]
    )
    terminal = TERMINALS[1] if observed else TERMINALS[2]
    return {
        "episode_count": n,
        "branch_correct": counts,
        "branch_wilson_95": {arm: _wilson(count, n) for arm, count in counts.items()},
        "credit_and_admission": admissions,
        "atom_v2_permit_commits": commits,
        "exact_remove_and_restore_count": transitions,
        "delta_state": delta,
        "six_branch_signature_rate": signature / n,
        "contrasts": {
            "ACTIVE-minus-FORCED_OPPOSITE_FEEDBACK": (counts["ACTIVE"] - counts["FORCED_OPPOSITE_FEEDBACK"]) / n,
            "ACTIVE-minus-OUTCOME_INDEPENDENT_SHAM": (counts["ACTIVE"] - counts["OUTCOME_INDEPENDENT_SHAM"]) / n,
            "ACTIVE-minus-mean(NO_UPDATE,REMOVE)": (counts["ACTIVE"] - (counts["NO_UPDATE"] + counts["REMOVE"]) / 2) / n,
            "RESTORE-minus-REMOVE": (counts["RESTORE"] - counts["REMOVE"]) / n,
        },
        "no_state_correct_by_position": by_position,
        "no_state_position_stratum_sizes": stratum_sizes,
        "correct_position_balance_stateful": positions,
        "evaluator_feedback_verified": feedback_verified,
        "evaluator_separate_os_user_episodes": separated,
        "g0_local_identifiability_observed": observed,
        "terminal": terminal,
        "wilson_denominator": n,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_v3_with_backend(
    *,
    backend: ChatBackend,
    protocol: Mapping[str, Any],
    protocol_sha256: str,
    output_dir: str | Path,
    execution_registry_path: str | Path,
    evaluator: evaluator_process.EvaluatorEndpoint,
    permit_commit: atom_v2_permit_bridge.LocalPermitCommitProcess,
    reveal_path_after_seal: str | Path,
    runtime_binding: Mapping[str, Any] | None = None,
    allow_pending_tokenizer_binding: bool = False,
    seal_marker_out: str | Path | None = None,
    reveal_wait_seconds: float = 1800.0,
) -> dict[str, Any]:
    """One outer no-refill claim for the thirty-two-episode G0-local occurrence."""

    validate_v3_protocol(protocol)
    if canonical_sha256(protocol) != protocol_sha256:
        raise G1MicroError("v3 protocol freeze drifted")
    if protocol["tokenizer_binding"]["status"] != "MEASURED" and not allow_pending_tokenizer_binding:
        raise G1MicroError("v3 live occurrence requires the measured tokenizer binding")
    if not isinstance(permit_commit, atom_v2_permit_bridge.LocalPermitCommitProcess):
        raise G1MicroError("v3 requires the Atom v2 local Permit commit process")
    output, registry = Path(output_dir), Path(execution_registry_path)
    if output.exists() or registry.exists() or str(registry) != protocol["consumption_registry"]["path"]:
        raise G1MicroError("v3 output or one-shot registry is unavailable")
    if runtime_binding is not None:
        g1_micro.validate_dgx_runtime_binding(runtime_binding, protocol=protocol, protocol_sha256=protocol_sha256, source_manifest=g1_micro._source_manifest())
    tasks = v3_tasks(protocol)
    start = make_record("OpaqueV3ExecutionStart", owner_uid="principal:g1-micro-execution-custodian", payload={
        "episode_commitment_sha256s": [task.commitment_sha256 for task in tasks],
        "evaluator_argv": list(evaluator.argv()),
        "permit_commit_process": permit_commit.describe(),
        "runtime_binding_sha256": None if runtime_binding is None else runtime_binding["record_sha256"],
        "source_manifest": g1_micro._source_manifest(),
        "output_directory": str(output.resolve()),
        "planned_episode_count": EPISODE_COUNT,
        "protocol_sha256": protocol_sha256,
        "tokenizer_binding_status": protocol["tokenizer_binding"]["status"],
        "retry_or_refill_permitted": False,
        "status": "STARTED_BEFORE_FIRST_HTTP_POST",
    })
    g1_micro._atomic_write(registry, canonical_json_bytes(start), create_parent=False)
    try:
        output.mkdir(parents=True)
        episodes = [
            _episode(backend=backend, task=task, output=output / "episodes" / f"{task.ordinal:02d}", protocol_sha256=protocol_sha256, evaluator=evaluator, permit_commit=permit_commit)
            for task in tasks
        ]
        sealed_journals = {episode["episode_uid"]: _digest((output / "episodes" / f"{task.ordinal:02d}" / "attempt_ledger.jsonl").read_bytes()) for task, episode in zip(tasks, episodes, strict=True)}
        seal_digest = canonical_sha256({"sealed_journals": sealed_journals})
        # The seal marker is the actor's public signal that every behavior call
        # is sealed.  The evaluator user publishes the reveal only after seeing
        # it; the actor waits, bounded, and never asks for the reveal earlier.
        marker = canonical_json_bytes({
            "schema_version": "hswm-g1-opaque-v3-seal-marker/v1", "study_uid": protocol["study_uid"],
            "protocol_canonical_sha256": protocol_sha256, "sealed_journals": sealed_journals,
            "sealed_journals_sha256": seal_digest, "behavior_calls_sealed": PROVIDER_CALL_CAP,
            "claim_boundary": "seal marker only; it authorizes the evaluator to publish the reveal and proves nothing else",
        })
        g1_micro._atomic_write(output / "sealed_before_reveal.json", marker)
        if seal_marker_out is not None:
            g1_micro._atomic_write(Path(seal_marker_out), marker)
        reveal_file = Path(reveal_path_after_seal)
        reveal_deadline = time.monotonic() + float(reveal_wait_seconds)
        while not reveal_file.is_file():
            if time.monotonic() >= reveal_deadline:
                raise G1MicroError("v3 reveal was not published after the seal within the wait bound")
            time.sleep(1)
        reveal_raw = reveal_file.read_bytes()
        reveal = evaluator_process.load_reveal(reveal_file)
        if reveal["protocol_canonical_sha256"] != protocol_sha256:
            raise G1MicroError("v3 reveal is bound to another protocol freeze")
        for task in tasks:
            entry = next(item for item in reveal["episodes"] if item["episode_uid"] == task.episode_uid)
            _scan_requests(output / "episodes" / f"{task.ordinal:02d}" / "attempt_ledger.jsonl", (entry["salt"], entry["leakage_canary"]))
        scores = score_episodes(episodes, protocol=protocol, reveal=reveal)
        metrics = v3_metrics(episodes, scores)
        g1_micro._atomic_write(output / "evaluator_reveal.json", reveal_raw)
        ledger_path = Path(evaluator.ledger_path)
        ledger_sha = _digest(ledger_path.read_bytes()) if ledger_path.is_file() else None
        unsigned = {
            "schema_version": V3_PROTOCOL,
            "study_uid": protocol["study_uid"],
            "protocol_canonical_sha256": protocol_sha256,
            "episode_count": EPISODE_COUNT,
            "episodes": episodes,
            "scores": scores,
            "metrics": metrics,
            "terminal": metrics["terminal"],
            "claim_ceiling": CLAIM_CEILING_IF_OBSERVED if metrics["g0_local_identifiability_observed"] else "INSTRUMENT_VALIDATION_ONLY",
            "scientific_status": SCIENTIFIC_STATUS,
            "evaluator_boundary": evaluator_process.EVALUATOR_BOUNDARY,
            "evaluator_reveal": {"path": "evaluator_reveal.json", "sha256": _digest(reveal_raw)},
            "evaluator_ledger": {"path": str(ledger_path), "sha256": ledger_sha},
            "reveal_attached_after_seal": {"sealed_journals_sha256": seal_digest, "behavior_calls_sealed_before_reveal_read": PROVIDER_CALL_CAP},
            "atom_v2_permit_commit_process": permit_commit.describe(),
            "tokenizer_binding_status": protocol["tokenizer_binding"]["status"],
            "runtime_binding": None if runtime_binding is None else dict(runtime_binding),
            "total_completion_posts": PROVIDER_CALL_CAP,
            "total_tokenize_posts": PROVIDER_CALL_CAP,
            "total_http_posts": 2 * PROVIDER_CALL_CAP,
            "scope_nonclaim": LOCAL_SCOPE_NONCLAIM,
            "verification_scope": "LOCAL_STRUCTURAL_G0_LOCAL_IDENTIFIABILITY_ONLY_NOT_EFFICACY",
        }
        bundle = {**unsigned, "bundle_sha256": canonical_sha256(unsigned)}
        verify_v3_bundle(bundle, base_dir=output, protocol=protocol)
        g1_micro._atomic_write(output / "result.json", canonical_json_bytes(bundle))
    except BaseException as error:
        abort = make_record("OpaqueV3ExecutionAbort", owner_uid="principal:g1-micro-execution-custodian", payload={
            "error_type": type(error).__name__, "retry_or_refill_permitted": False, "terminal": TERMINALS[0],
        }, refs=(_ref("execution_start", start),))
        if not output.exists():
            output.mkdir(parents=True)
        g1_micro._atomic_write(output / "abort.json", canonical_json_bytes(abort))
        g1_micro._replace_canonical(registry, canonical_json_bytes(make_record("OpaqueV3ExecutionSeal", owner_uid="principal:g1-micro-execution-custodian", payload={"abort_sha256": abort["record_sha256"], "result_sha256": None, "start": start, "status": "ABORTED_NO_RERUN"}, refs=(_ref("execution_start", start),))))
        raise
    seal = make_record("OpaqueV3ExecutionSeal", owner_uid="principal:g1-micro-execution-custodian", payload={"abort_sha256": None, "result_sha256": bundle["bundle_sha256"], "start": start, "status": "COMPLETED_NO_RERUN"}, refs=(_ref("execution_start", start),))
    g1_micro._replace_canonical(registry, canonical_json_bytes(seal))
    return bundle


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

BUNDLE_FIELDS = {
    "bundle_sha256", "schema_version", "study_uid", "protocol_canonical_sha256", "episode_count", "episodes",
    "scores", "metrics", "terminal", "claim_ceiling", "scientific_status", "evaluator_boundary",
    "evaluator_reveal", "evaluator_ledger", "reveal_attached_after_seal", "atom_v2_permit_commit_process",
    "tokenizer_binding_status", "runtime_binding", "total_completion_posts", "total_tokenize_posts",
    "total_http_posts", "scope_nonclaim", "verification_scope",
}


def verify_v3_bundle(bundle: Mapping[str, Any], *, base_dir: str | Path, protocol: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Reconstruct every episode from retained records, journals, and the attached reveal."""

    if not isinstance(bundle, Mapping) or set(bundle) != BUNDLE_FIELDS or bundle["schema_version"] != V3_PROTOCOL:
        raise G1MicroError("v3 bundle boundary drifted")
    unsigned = dict(bundle)
    digest = unsigned.pop("bundle_sha256")
    if digest != canonical_sha256(unsigned):
        raise G1MicroError("v3 bundle digest mismatch")
    if (
        bundle["episode_count"] != EPISODE_COUNT or bundle["total_completion_posts"] != PROVIDER_CALL_CAP
        or bundle["total_tokenize_posts"] != PROVIDER_CALL_CAP or bundle["total_http_posts"] != 2 * PROVIDER_CALL_CAP
        or bundle["scope_nonclaim"] != LOCAL_SCOPE_NONCLAIM or bundle["scientific_status"] != SCIENTIFIC_STATUS
        or bundle["evaluator_boundary"] != evaluator_process.EVALUATOR_BOUNDARY or bundle["terminal"] not in TERMINALS[1:]
    ):
        raise G1MicroError("v3 bundle fixed boundary drifted")
    base = Path(base_dir)
    reveal_path = base / bundle["evaluator_reveal"]["path"]
    reveal_raw = reveal_path.read_bytes()
    if _digest(reveal_raw) != bundle["evaluator_reveal"]["sha256"]:
        raise G1MicroError("v3 attached reveal digest drifted")
    reveal = evaluator_process.load_reveal(reveal_path)
    if reveal["protocol_canonical_sha256"] != bundle["protocol_canonical_sha256"]:
        raise G1MicroError("v3 reveal protocol binding drifted")
    if protocol is not None:
        validate_v3_protocol(protocol)
        if canonical_sha256(protocol) != bundle["protocol_canonical_sha256"]:
            raise G1MicroError("v3 verifier protocol binding drifted")
        if bundle["runtime_binding"] is not None:
            g1_micro.validate_dgx_runtime_binding(bundle["runtime_binding"], protocol=protocol, protocol_sha256=bundle["protocol_canonical_sha256"], source_manifest=g1_micro._source_manifest())
        tasks = {task.episode_uid: task for task in v3_tasks(protocol)}
    else:
        tasks = {}
    episodes = bundle["episodes"]
    if len(episodes) != EPISODE_COUNT:
        raise G1MicroError("v3 episode set is incomplete")
    entries = {item["episode_uid"]: item for item in reveal["episodes"]}
    sealed: dict[str, str] = {}
    for ordinal, episode in enumerate(episodes, start=1):
        for record in g1_micro._record_tree(episode):
            validate_record(record)
        uid = episode["episode_uid"]
        entry = entries.get(uid)
        if entry is None or canonical_sha256(entry) != episode["task_commitment_sha256"]:
            raise G1MicroError("v3 episode does not join the reveal commitment")
        trajectory = episode["trajectory"]
        task = tasks.get(uid)
        if task is not None and task.commitment_sha256 != episode["task_commitment_sha256"]:
            raise G1MicroError("v3 episode commitment differs from the protocol")
        feedback = episode["outcome"]["payload"]["evaluator_feedback"]
        evaluator_process.verify_feedback(feedback, reveal=reveal)
        actual = trajectory["payload"]["action_code"] == entry["correct_action_code"]
        expected_outcome = make_record("OpaqueOutcome", owner_uid=PRINCIPALS["outcome_evaluator_uid"], payload={
            "episode_uid": uid, "choice_was_correct": actual, "evaluator_feedback": feedback,
            "evaluator_separation": episode["evaluator_separation"],
        }, refs=(_ref("trajectory", trajectory),))
        if episode["outcome"] != expected_outcome:
            raise G1MicroError("v3 outcome does not reconstruct")
        expected_forced = make_record("ForcedOppositeFeedback", owner_uid=PRINCIPALS["outcome_evaluator_uid"], payload={
            "episode_uid": uid, "choice_was_correct": not actual, "derived_from_outcome_sha256": expected_outcome["record_sha256"],
        }, refs=(_ref("outcome", expected_outcome),))
        if episode["forced_opposite_feedback"] != expected_forced:
            raise G1MicroError("v3 forced feedback does not reconstruct")
        sham_bit = episode["sham_feedback"]["payload"]["choice_was_correct"]
        if task is not None and sham_bit is not task.sham_feedback_correct:
            raise G1MicroError("v3 sham bit differs from the precommitted protocol bit")
        expected_sham = make_record("OutcomeIndependentShamFeedback", owner_uid=PRINCIPALS["outcome_evaluator_uid"], payload={
            "episode_uid": uid, "choice_was_correct": sham_bit, "precommitted_in_protocol": True,
        }, refs=(_ref("trajectory", trajectory),))
        if episode["sham_feedback"] != expected_sham:
            raise G1MicroError("v3 sham feedback does not reconstruct")
        codes = tuple(sorted({trajectory["payload"]["action_code"], *(
            episode["dispositions"][arm]["proposal"]["payload"]["action_code"] for arm in STATEFUL_ARMS
        )}))
        if task is not None:
            codes = task.action_codes
        for branch, feedback_record, bit in (
            ("ACTIVE", episode["outcome"], actual),
            ("FORCED_OPPOSITE_FEEDBACK", episode["forced_opposite_feedback"], not actual),
            ("OUTCOME_INDEPENDENT_SHAM", episode["sham_feedback"], sham_bit),
        ):
            data = episode["dispositions"][branch]
            proposal, credit = data["proposal"], data["credit"]
            code = proposal["payload"]["action_code"]
            trajectory_code = trajectory["payload"]["action_code"]
            other = next((item for item in codes if item != trajectory_code), None)
            if other is None:
                raise G1MicroError("v3 episode code pair cannot be reconstructed")
            expected = trajectory_code if bit else other
            expected_proposal = make_record("RevisionProposal", owner_uid=PRINCIPALS["proposer_uid"], payload={
                "action_code": code, "branch": branch, "call_evidence": proposal["payload"]["call_evidence"], "revision_kind": "OPAQUE_ACTION_CODE_DISPOSITION",
            }, refs=(_ref("trajectory", trajectory), _ref("feedback", feedback_record)))
            expected_credit = make_record("CreditDecision", owner_uid=PRINCIPALS["credit_adjudicator_uid"], payload={
                "decision": "CREDIT" if code == expected else "NO_CREDIT", "expected_action_code": expected, "proposed_action_code": code,
            }, refs=(_ref("trajectory", trajectory), _ref("feedback", feedback_record), _ref("proposal", expected_proposal)))
            if proposal != expected_proposal or credit != expected_credit:
                raise G1MicroError("v3 proposal/credit rule does not reconstruct")
            if credit["payload"]["decision"] == "NO_CREDIT":
                if data.get("admission") is not None or any(key in data for key in ("disposition", "permit", "permit_policy", "successor_state", "atom_v2_permit_commit")):
                    raise G1MicroError("v3 nonadherent proposal was admitted")
                continue
            if task is None:
                continue
            disposition = g1_micro._opaque_disposition(task, code, trajectory=trajectory, feedback=feedback_record, proposal=proposal, credit=credit)
            successor = make_state([disposition])
            policy = make_permit_policy(task, bundle["protocol_canonical_sha256"])
            permit = make_local_permit(task=task, permit_policy=policy, base_state=make_genesis_state(), base_generation=0, trajectory=trajectory, feedback=feedback_record, proposal=proposal, credit=credit, disposition=disposition, successor_state=successor)
            if data.get("disposition") != disposition or data.get("successor_state") != successor or data.get("permit_policy") != policy or data.get("permit") != permit:
                raise G1MicroError("v3 credit-to-permit/state construction drifted")
            expected_admission = make_record("LocalAdmissionReceipt", owner_uid=STATE_OWNER, payload={
                "base_generation": 0, "base_state_sha256": state_sha256(make_genesis_state()),
                "exact_write_set": permit["payload"]["write_set"], "resulting_generation": 1,
                "resulting_state_sha256": state_sha256(successor), "terminal": "ADMITTED_LOCAL_EXPLORATORY",
            }, refs=(_ref("permit", permit), _ref("proposal", proposal), _ref("feedback", feedback_record), _ref("credit", credit)))
            expected_consumption = G1MicroStore._burn_record(permit, terminal="ADMITTED_LOCAL_EXPLORATORY", admission_sha256=expected_admission["record_sha256"])
            if data["admission"] != {"admission": expected_admission, "consumption": expected_consumption}:
                raise G1MicroError("v3 admission/consumption does not reconstruct")
            if "atom_v2_permit_commit" not in data:
                raise G1MicroError("v3 credited admission lacks its Atom v2 Permit commit")
            verify_atom_v2_commit_binding(
                data["atom_v2_permit_commit"], episode_uid=uid, branch=branch, base_state=make_genesis_state(),
                successor_state=successor, permit=permit, permit_policy=policy, proposal=proposal, disposition=disposition,
                resulting_state_sha256=expected_admission["payload"]["resulting_state_sha256"],
            )
        if task is not None:
            active = episode["dispositions"]["ACTIVE"]
            expected_states = {
                "ACTIVE": active["successor_state"] if active["admission"] is not None else make_genesis_state(),
                "FORCED_OPPOSITE_FEEDBACK": episode["dispositions"]["FORCED_OPPOSITE_FEEDBACK"].get("successor_state", make_genesis_state()),
                "OUTCOME_INDEPENDENT_SHAM": episode["dispositions"]["OUTCOME_INDEPENDENT_SHAM"].get("successor_state", make_genesis_state()),
                "NO_UPDATE": make_genesis_state(),
                "REMOVE": make_genesis_state(),
                "RESTORE": active["successor_state"] if active["admission"] is not None else make_genesis_state(),
            }
            expected_orders = {
                "NO_UPDATE": task.orders["no_update_action_order"], "REMOVE": task.orders["remove_action_order"],
                **{arm: task.orders["stateful_probe_action_order"] for arm in ("ACTIVE", "FORCED_OPPOSITE_FEEDBACK", "OUTCOME_INDEPENDENT_SHAM", "RESTORE")},
            }
            if set(episode["probes"]) != set(ARMS):
                raise G1MicroError("v3 probe branch set is incomplete")
            for branch, probe in episode["probes"].items():
                payload = probe["payload"]
                if payload["compiled_disposition"] != compile_disposition(expected_states[branch], cue=task.cue) or payload["state_sha256"] != state_sha256(expected_states[branch]) or list(payload["candidate_order"]) != list(expected_orders[branch]) or payload["choice"] not in task.action_codes:
                    raise G1MicroError(f"v3 {branch} observation cannot be reconstructed")
        journal_path = base / "episodes" / f"{ordinal:02d}" / "attempt_ledger.jsonl"
        if not journal_path.is_file():
            raise G1MicroError("v3 retained episode journal is missing")
        replayed = _journal_manifest(journal_path, expected_operations=JOURNAL_OPERATIONS)
        if replayed != episode["journal"] or replayed["completed_calls"] != CALLS_PER_EPISODE or not replayed["raw_preimages_valid"] or not replayed["operation_order_valid"] or replayed["failure_events"] or not replayed["all_rows_accounted"]:
            raise G1MicroError("v3 retained journal cannot be replayed")
        _scan_requests(journal_path, (*LEAKAGE_CONTRACT["forbidden_request_substrings"], entry["salt"], entry["leakage_canary"]))
        sealed[uid] = _digest(journal_path.read_bytes())
    if bundle["reveal_attached_after_seal"] != {"sealed_journals_sha256": canonical_sha256({"sealed_journals": sealed}), "behavior_calls_sealed_before_reveal_read": PROVIDER_CALL_CAP}:
        raise G1MicroError("v3 sealed-journal digest does not bind the reveal attachment")
    if protocol is not None:
        scores = score_episodes(episodes, protocol=protocol, reveal=reveal)
        if scores != bundle["scores"]:
            raise G1MicroError("v3 scores do not reconstruct from the reveal")
    metrics = v3_metrics(episodes, bundle["scores"])
    if metrics != bundle["metrics"] or bundle["terminal"] != metrics["terminal"]:
        raise G1MicroError("v3 metrics or terminal do not reconstruct")
    expected_ceiling = CLAIM_CEILING_IF_OBSERVED if metrics["g0_local_identifiability_observed"] else "INSTRUMENT_VALIDATION_ONLY"
    if bundle["claim_ceiling"] != expected_ceiling:
        raise G1MicroError("v3 claim ceiling exceeds its observed rule")
    return {
        "bundle_sha256": bundle["bundle_sha256"],
        "terminal": bundle["terminal"],
        "claim_ceiling": bundle["claim_ceiling"],
        "evaluator_separate_os_user_episodes": metrics["evaluator_separate_os_user_episodes"],
        "verification": "VALID_LOCAL_STRUCTURAL_G0_LOCAL_RECONSTRUCTION",
    }


# ---------------------------------------------------------------------------
# Live entrypoint
# ---------------------------------------------------------------------------


def preflight_v3(
    *,
    protocol_path: str | Path,
    output_dir: str | Path,
    execution_registry_path: str | Path,
    evaluator: evaluator_process.EvaluatorEndpoint,
    permit_commit: atom_v2_permit_bridge.LocalPermitCommitProcess | None,
    reveal_path_after_seal: str | Path,
    allow_same_user: bool = False,
) -> dict[str, Any]:
    """Zero-POST checks: protocol freeze, one-shot registry, Permit process, and reveal custody."""

    protocol, protocol_sha = load_v3_protocol(protocol_path)
    output, registry = Path(output_dir), Path(execution_registry_path)
    problems: list[str] = []
    if output.exists():
        problems.append("OUTPUT_DIRECTORY_EXISTS")
    if registry.exists():
        problems.append("ONE_SHOT_REGISTRY_ALREADY_CONSUMED")
    if str(registry) != protocol["consumption_registry"]["path"]:
        problems.append("REGISTRY_PATH_DIFFERS_FROM_PROTOCOL")
    if protocol["freeze"]["status"] != "FROZEN":
        problems.append("PROTOCOL_NOT_FROZEN")
    if protocol["tokenizer_binding"]["status"] != "MEASURED":
        problems.append("TOKENIZER_BINDING_NOT_MEASURED")
    if permit_commit is None:
        problems.append("ATOM_V2_PERMIT_COMMIT_PROCESS_ABSENT")
    reveal = Path(reveal_path_after_seal)
    reveal_readable_now = False
    try:
        with reveal.open("rb"):
            reveal_readable_now = True
    except OSError:
        reveal_readable_now = False
    custody = "ACTOR_CANNOT_READ_REVEAL_BEFORE_RUN" if not reveal_readable_now else "ACTOR_CAN_READ_REVEAL_BEFORE_RUN"
    if reveal_readable_now and not allow_same_user:
        problems.append("REVEAL_READABLE_BY_ACTOR_BEFORE_RUN")
    return {
        "schema_version": "hswm-g1-opaque-v3-preflight/v1",
        "protocol_canonical_sha256": protocol_sha,
        "study_uid": protocol["study_uid"],
        "evaluator_argv": list(evaluator.argv()),
        "permit_commit_process": None if permit_commit is None else permit_commit.describe(),
        "reveal_custody": custody,
        "problems": problems,
        "status": "PREFLIGHT_OK_ZERO_POST" if not problems else "PREFLIGHT_BLOCKED_ZERO_POST",
        "claim_boundary": "zero-POST preflight; not a run, a G0 pass, or evidence",
    }


def run_v3_live(
    *,
    protocol_path: str | Path,
    endpoint: str,
    model: str,
    expected_max_model_len: int,
    output_dir: str | Path,
    execution_registry_path: str | Path,
    runtime_binding_path: str | Path,
    evaluator: evaluator_process.EvaluatorEndpoint,
    permit_commit: atom_v2_permit_bridge.LocalPermitCommitProcess,
    reveal_path_after_seal: str | Path,
    allow_same_user: bool = False,
    seal_marker_out: str | Path | None = None,
    reveal_wait_seconds: float = 1800.0,
) -> dict[str, Any]:
    """Official live entrypoint for one frozen v3 occurrence against the pinned server."""

    preflight = preflight_v3(
        protocol_path=protocol_path, output_dir=output_dir, execution_registry_path=execution_registry_path,
        evaluator=evaluator, permit_commit=permit_commit, reveal_path_after_seal=reveal_path_after_seal,
        allow_same_user=allow_same_user,
    )
    if preflight["problems"]:
        raise G1MicroError(f"v3 preflight blocked: {','.join(preflight['problems'])}")
    protocol, protocol_sha = load_v3_protocol(protocol_path)
    binding_file = Path(runtime_binding_path)
    if not binding_file.is_file() or binding_file.is_symlink():
        raise G1MicroError("measured DGX runtime binding is absent or linked")
    runtime_binding = _canonical_object(binding_file.read_bytes(), "DGX runtime binding")
    backend = g1_micro.OpenAICompatibleBackend(
        g1_micro.OpenAIBackendConfig(endpoint=endpoint, model=model, expected_max_model_len=expected_max_model_len)
    )
    return run_v3_with_backend(
        backend=backend, protocol=protocol, protocol_sha256=protocol_sha, output_dir=output_dir,
        execution_registry_path=execution_registry_path, evaluator=evaluator, permit_commit=permit_commit,
        reveal_path_after_seal=reveal_path_after_seal, runtime_binding=runtime_binding,
        seal_marker_out=seal_marker_out, reveal_wait_seconds=reveal_wait_seconds,
    )


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    import shlex
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18080")
    parser.add_argument("--model", default="qwen3.6-35b-a3b")
    parser.add_argument("--expected-max-model-len", type=int, default=32768)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execution-registry", type=Path, required=True)
    parser.add_argument("--runtime-binding", type=Path)
    parser.add_argument("--evaluator-argv-prefix", required=True, help="shell-quoted argv that launches the evaluator process as its own OS user, e.g. 'sudo -n -u hswm-evaluator /opt/hswm/.venv/bin/python -m hswm.experiments.g1_opaque_evaluator_process'")
    parser.add_argument("--evaluator-reveal", required=True, help="reveal path as seen by the evaluator user")
    parser.add_argument("--evaluator-ledger", required=True)
    parser.add_argument("--reveal-after-seal", type=Path, required=True, help="path from which the actor reads the reveal only after every call is sealed")
    parser.add_argument("--permit-process-script", type=Path, help="built canonical-atom-v2-local-permit-commit-process.js; defaults to the repository dist")
    parser.add_argument("--node", help="absolute node executable; defaults to PATH lookup")
    parser.add_argument("--allow-same-user", action="store_true", help="tests only: do not require evaluator custody separation")
    parser.add_argument("--seal-marker-out", type=Path, help="extra copy of the seal marker at a path the evaluator user can watch")
    parser.add_argument("--reveal-wait-seconds", type=float, default=1800.0)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)

    evaluator = evaluator_process.EvaluatorEndpoint(
        argv_prefix=tuple(shlex.split(args.evaluator_argv_prefix)),
        reveal_path=args.evaluator_reveal, ledger_path=args.evaluator_ledger,
    )
    repo_root = Path(__file__).resolve().parents[3]
    if args.permit_process_script is not None:
        node = args.node or __import__("shutil").which("node")
        permit_commit = None if node is None else atom_v2_permit_bridge.LocalPermitCommitProcess(runtime=str(Path(node).resolve()), script=str(args.permit_process_script.resolve()))
    else:
        permit_commit = atom_v2_permit_bridge.default_process(repo_root, runtime=args.node)
    preflight = preflight_v3(
        protocol_path=args.protocol, output_dir=args.output_dir, execution_registry_path=args.execution_registry,
        evaluator=evaluator, permit_commit=permit_commit, reveal_path_after_seal=args.reveal_after_seal,
        allow_same_user=args.allow_same_user,
    )
    if args.preflight_only:
        print(canonical_json_bytes(preflight).decode("utf-8"))
        return 0 if not preflight["problems"] else 2
    if preflight["problems"]:
        sys.stderr.write(f"V3_PREFLIGHT_BLOCKED:{','.join(preflight['problems'])}\n")
        return 2
    if args.runtime_binding is None:
        raise G1MicroError("live execution requires --runtime-binding")
    assert permit_commit is not None
    bundle = run_v3_live(
        protocol_path=args.protocol, endpoint=args.endpoint, model=args.model,
        expected_max_model_len=args.expected_max_model_len, output_dir=args.output_dir,
        execution_registry_path=args.execution_registry, runtime_binding_path=args.runtime_binding,
        evaluator=evaluator, permit_commit=permit_commit, reveal_path_after_seal=args.reveal_after_seal,
        allow_same_user=args.allow_same_user, seal_marker_out=args.seal_marker_out, reveal_wait_seconds=args.reveal_wait_seconds,
    )
    print(canonical_json_bytes({
        "bundle_sha256": bundle["bundle_sha256"], "result_path": str(args.output_dir / "result.json"),
        "terminal": bundle["terminal"], "claim_ceiling": bundle["claim_ceiling"],
    }).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
