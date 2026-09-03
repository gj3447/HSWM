"""Future-randomness-bound synthetic outcome instrument for a narrow G0 study.

This module deliberately does *not* establish an independent outcome owner,
CF-07, G0, G1, or a causal-learning result.  It only projects a sealed set of
opaque two-action episodes through a future drand pulse that has been verified
by :mod:`hswm.experiments.swm0w_beacon`.

Callers must use ``verify_and_project_online`` (which executes the pinned BLS
verifier) for a live occurrence and arrange an independent replay themselves.
The historical offline helper is only a known-answer/metamorphic qualification
path.  A receipt or a ``TaskSeedBindingV1`` supplied by itself is not evidence
that BLS verification was executed.

This module also implements neither a durable external singleton/no-retry
registry nor independently timestamped registration/action seals.  Its receipts
encode those absences as fixed false fields and remain non-promoting.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from hswm.experiments import swm0w_beacon as beacon


REGISTRATION_SCHEMA = "hswm-g0-future-outcome-registration-payload/v1"
PLAN_SCHEMA = "hswm-g0-future-outcome-plan/v1"
ACTION_SEAL_SCHEMA = "hswm-g0-future-outcome-action-seal/v1"
RECEIPT_SCHEMA = "hswm-g0-future-outcome-receipt/v1"
MAPPING_DOMAIN = b"HSWM-G0-FUTURE-OUTCOME-OPAQUE-ACTION-V1"
EPISODE_COUNT = beacon.TASK_COUNT
CLAIM_CEILING = (
    "FUTURE_RANDOMNESS_BOUND_SYNTHETIC_OUTCOME_INSTRUMENT_ONLY_"
    "NOT_INDEPENDENT_OWNER_NOT_CF07_NOT_G0_NOT_G1"
)
ACTION_CHRONOLOGY_INDEPENDENTLY_ESTABLISHED = False
EXTERNAL_SINGLETON_NO_RETRY_REGISTRY_IMPLEMENTED = False
REGISTRATION_TIMESTAMP_INDEPENDENTLY_ESTABLISHED = False
VERIFIER_EXECUTION_EVIDENCE_EMBEDDED = False
RECEIPT_ALONE_PROVES_VERIFIER_EXECUTION = False
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class G0FutureOutcomeError(ValueError):
    """Raised when a future-outcome plan, seal, or projection is malformed."""


def _sha256(value: Any) -> str:
    return beacon.canonical_sha256(value)


def _require_digest(value: str, name: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise G0FutureOutcomeError(f"{name} must be lowercase SHA-256")
    return value


def _require_identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 160:
        raise G0FutureOutcomeError(f"{name} must be a non-empty bounded string")
    if any(ord(character) < 0x21 or ord(character) > 0x7E for character in value):
        raise G0FutureOutcomeError(f"{name} must be printable ASCII without whitespace")
    return value


@dataclass(frozen=True, slots=True)
class OpaqueEpisodeV1:
    """One predeclared two-action episode; action-code order is significant."""

    episode_uid: str
    action_codes: tuple[str, str]

    def __post_init__(self) -> None:
        _require_identifier(self.episode_uid, "episode_uid")
        if type(self.action_codes) is not tuple or len(self.action_codes) != 2:
            raise G0FutureOutcomeError("action_codes must be an ordered pair")
        first, second = self.action_codes
        _require_identifier(first, "action_codes[0]")
        _require_identifier(second, "action_codes[1]")
        if first == second:
            raise G0FutureOutcomeError("opaque action codes must be distinct")

    def canonical(self) -> dict[str, Any]:
        return {"action_codes": list(self.action_codes), "episode_uid": self.episode_uid}


def registration_payload(
    *,
    experiment_id: str,
    chain_hash: str,
    round_number: int,
    round_time_unix: int,
    episodes: Sequence[OpaqueEpisodeV1],
    analysis_sha256: str,
    holdout_sha256: str,
    arm_schedule_sha256: str,
) -> dict[str, Any]:
    """Return the acyclic bytes whose digest must be externally registered.

    The full beacon commitment cannot appear here because its registration hash
    is this payload's digest.  Its immutable chain/round/time fields are bound
    instead, and ``FutureOutcomePlanV1`` verifies their equality afterwards.
    """

    _require_identifier(experiment_id, "experiment_id")
    if chain_hash != beacon.QUICKNET_CHAIN_HASH:
        raise G0FutureOutcomeError("registration must use pinned Quicknet")
    if type(round_number) is not int or type(round_time_unix) is not int:
        raise G0FutureOutcomeError("round_number and round_time_unix must be integers")
    if round_time_unix != beacon.quicknet_round_time(round_number):
        raise G0FutureOutcomeError("registration round/time mismatch")
    normalized = tuple(episodes)
    if len(normalized) != EPISODE_COUNT:
        raise G0FutureOutcomeError(f"plan must contain exactly {EPISODE_COUNT} episodes")
    if any(not isinstance(episode, OpaqueEpisodeV1) for episode in normalized):
        raise G0FutureOutcomeError("episodes must be OpaqueEpisodeV1 values")
    identifiers = [episode.episode_uid for episode in normalized]
    if len(set(identifiers)) != EPISODE_COUNT:
        raise G0FutureOutcomeError("episode UIDs must be unique")
    return {
        "analysis_sha256": _require_digest(analysis_sha256, "analysis_sha256"),
        "arm_schedule_sha256": _require_digest(arm_schedule_sha256, "arm_schedule_sha256"),
        "chain_hash": chain_hash,
        "episodes": [episode.canonical() for episode in normalized],
        "experiment_id": experiment_id,
        "holdout_sha256": _require_digest(holdout_sha256, "holdout_sha256"),
        "round": round_number,
        "round_time_unix": round_time_unix,
        "schema_version": REGISTRATION_SCHEMA,
    }


@dataclass(frozen=True, slots=True)
class FutureOutcomePlanV1:
    """A future-round-bound, exact twenty-episode synthetic-outcome plan."""

    commitment: beacon.FutureRoundCommitmentV1
    episodes: tuple[OpaqueEpisodeV1, ...]
    analysis_sha256: str
    holdout_sha256: str
    arm_schedule_sha256: str
    registration_payload_sha256: str
    plan_sha256: str

    def __post_init__(self) -> None:
        if type(self.episodes) is not tuple:
            raise G0FutureOutcomeError("plan episodes must be an immutable ordered tuple")
        if any(not isinstance(episode, OpaqueEpisodeV1) for episode in self.episodes):
            raise G0FutureOutcomeError("plan episodes must be OpaqueEpisodeV1 values")
        if not isinstance(self.commitment, beacon.FutureRoundCommitmentV1):
            raise G0FutureOutcomeError("plan requires a validated future-round commitment")
        payload = registration_payload(
            experiment_id=self.commitment.experiment_id,
            chain_hash=self.commitment.chain_hash,
            round_number=self.commitment.round,
            round_time_unix=self.commitment.round_time_unix,
            episodes=self.episodes,
            analysis_sha256=self.analysis_sha256,
            holdout_sha256=self.holdout_sha256,
            arm_schedule_sha256=self.arm_schedule_sha256,
        )
        payload_digest = _sha256(payload)
        _require_digest(self.registration_payload_sha256, "registration_payload_sha256")
        if self.registration_payload_sha256 != payload_digest:
            raise G0FutureOutcomeError("registration payload digest mismatch")
        if self.commitment.registration_evidence_sha256 != payload_digest:
            raise G0FutureOutcomeError("beacon registration evidence does not bind exact plan")
        _require_digest(self.plan_sha256, "plan_sha256")
        if self.plan_sha256 != _sha256(self.unsigned()):
            raise G0FutureOutcomeError("plan self-hash mismatch")

    def registration_payload(self) -> dict[str, Any]:
        return registration_payload(
            experiment_id=self.commitment.experiment_id,
            chain_hash=self.commitment.chain_hash,
            round_number=self.commitment.round,
            round_time_unix=self.commitment.round_time_unix,
            episodes=self.episodes,
            analysis_sha256=self.analysis_sha256,
            holdout_sha256=self.holdout_sha256,
            arm_schedule_sha256=self.arm_schedule_sha256,
        )

    def unsigned(self) -> dict[str, Any]:
        return {
            "commitment": self.commitment.canonical(),
            "registration_payload_sha256": self.registration_payload_sha256,
            "schema_version": PLAN_SCHEMA,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "plan_sha256": self.plan_sha256}


def make_plan(
    *,
    commitment: beacon.FutureRoundCommitmentV1,
    episodes: Sequence[OpaqueEpisodeV1],
    analysis_sha256: str,
    holdout_sha256: str,
    arm_schedule_sha256: str,
) -> FutureOutcomePlanV1:
    if not isinstance(commitment, beacon.FutureRoundCommitmentV1):
        raise G0FutureOutcomeError("plan requires a validated future-round commitment")
    planned = tuple(episodes)
    payload = registration_payload(
        experiment_id=commitment.experiment_id,
        chain_hash=commitment.chain_hash,
        round_number=commitment.round,
        round_time_unix=commitment.round_time_unix,
        episodes=planned,
        analysis_sha256=analysis_sha256,
        holdout_sha256=holdout_sha256,
        arm_schedule_sha256=arm_schedule_sha256,
    )
    registration_digest = _sha256(payload)
    unsigned = {
        "commitment": commitment.canonical(),
        "registration_payload_sha256": registration_digest,
        "schema_version": PLAN_SCHEMA,
    }
    return FutureOutcomePlanV1(
        commitment=commitment,
        episodes=planned,
        analysis_sha256=analysis_sha256,
        holdout_sha256=holdout_sha256,
        arm_schedule_sha256=arm_schedule_sha256,
        registration_payload_sha256=registration_digest,
        plan_sha256=_sha256(unsigned),
    )


@dataclass(frozen=True, slots=True)
class SealedActionV1:
    episode_uid: str
    action_code: str

    def __post_init__(self) -> None:
        _require_identifier(self.episode_uid, "sealed episode_uid")
        _require_identifier(self.action_code, "sealed action_code")

    def canonical(self) -> dict[str, str]:
        return {"action_code": self.action_code, "episode_uid": self.episode_uid}


@dataclass(frozen=True, slots=True)
class PrePulseActionSealV1:
    """Caller-declared complete action set, sealed before public-pulse time.

    ``completed_at_unix`` is not independent chronology evidence; every output
    from this module records that limitation explicitly.
    """

    plan_sha256: str
    completed_at_unix: int
    actions: tuple[SealedActionV1, ...]
    action_seal_sha256: str

    def __post_init__(self) -> None:
        _require_digest(self.plan_sha256, "seal plan_sha256")
        if type(self.completed_at_unix) is not int or self.completed_at_unix < 0:
            raise G0FutureOutcomeError("seal completed_at_unix must be a non-negative integer")
        if type(self.actions) is not tuple or len(self.actions) != EPISODE_COUNT:
            raise G0FutureOutcomeError(f"seal must contain exactly {EPISODE_COUNT} actions")
        if any(not isinstance(action, SealedActionV1) for action in self.actions):
            raise G0FutureOutcomeError("seal actions must be SealedActionV1 values")
        if len({action.episode_uid for action in self.actions}) != EPISODE_COUNT:
            raise G0FutureOutcomeError(
                "seal must contain every episode exactly once; duplicates are forbidden"
            )
        _require_digest(self.action_seal_sha256, "action_seal_sha256")
        if self.action_seal_sha256 != _sha256(self.unsigned()):
            raise G0FutureOutcomeError("action seal self-hash mismatch")

    def unsigned(self) -> dict[str, Any]:
        return {
            "actions": [action.canonical() for action in self.actions],
            "completed_at_unix": self.completed_at_unix,
            "plan_sha256": self.plan_sha256,
            "schema_version": ACTION_SEAL_SCHEMA,
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "action_seal_sha256": self.action_seal_sha256}


def make_action_seal(
    *, plan: FutureOutcomePlanV1, completed_at_unix: int, actions: Sequence[SealedActionV1]
) -> PrePulseActionSealV1:
    if not isinstance(plan, FutureOutcomePlanV1):
        raise G0FutureOutcomeError("seal requires a validated plan")
    sealed = tuple(actions)
    if any(not isinstance(action, SealedActionV1) for action in sealed):
        raise G0FutureOutcomeError("seal actions must be SealedActionV1 values")
    unsigned = {
        "actions": [action.canonical() for action in sealed],
        "completed_at_unix": completed_at_unix,
        "plan_sha256": plan.plan_sha256,
        "schema_version": ACTION_SEAL_SCHEMA,
    }
    seal = PrePulseActionSealV1(
        plan_sha256=plan.plan_sha256,
        completed_at_unix=completed_at_unix,
        actions=sealed,
        action_seal_sha256=_sha256(unsigned),
    )
    _validate_action_seal(plan, seal)
    return seal


def _validate_action_seal(plan: FutureOutcomePlanV1, seal: PrePulseActionSealV1) -> None:
    if not isinstance(plan, FutureOutcomePlanV1):
        raise G0FutureOutcomeError("action seal requires a validated plan")
    # Re-run the transitive registration binding immediately before any action
    # set is accepted.  This catches accidental or hostile nested mutation even
    # if a caller constructed a dataclass without using make_plan().
    plan.__post_init__()
    if seal.plan_sha256 != plan.plan_sha256:
        raise G0FutureOutcomeError("action seal belongs to a different plan")
    if seal.completed_at_unix >= plan.commitment.round_time_unix:
        raise G0FutureOutcomeError("action seal must complete strictly before pulse time")
    planned = {episode.episode_uid: episode for episode in plan.episodes}
    sealed = {action.episode_uid: action for action in seal.actions}
    if set(sealed) != set(planned):
        raise G0FutureOutcomeError("action seal episode set differs from exact plan")
    for episode_uid, action in sealed.items():
        if action.action_code not in planned[episode_uid].action_codes:
            raise G0FutureOutcomeError("sealed action is not one of the opaque planned actions")


def derive_correct_action(*, seed: bytes, plan_sha256: str, episode: OpaqueEpisodeV1) -> str:
    """Pure, domain-separated mapping; this is synthetic truth, not an owner."""

    if not isinstance(seed, bytes) or len(seed) != 32:
        raise G0FutureOutcomeError("verified task seed must be exactly 32 bytes")
    if not isinstance(episode, OpaqueEpisodeV1):
        raise G0FutureOutcomeError("episode must be OpaqueEpisodeV1")
    _require_digest(plan_sha256, "plan_sha256")
    digest = sha256(
        b"\x00".join(
            (
                MAPPING_DOMAIN,
                seed,
                bytes.fromhex(plan_sha256),
                episode.episode_uid.encode("ascii"),
                episode.action_codes[0].encode("ascii"),
                episode.action_codes[1].encode("ascii"),
            )
        )
    ).digest()
    return episode.action_codes[digest[0] & 1]


@dataclass(frozen=True, slots=True)
class SyntheticOutcomeV1:
    """Immutable synthetic score for one exactly sealed opaque episode."""

    episode_uid: str
    selected_action_code: str
    correct_action_code: str
    is_correct: bool

    def __post_init__(self) -> None:
        _require_identifier(self.episode_uid, "outcome episode_uid")
        _require_identifier(self.selected_action_code, "selected_action_code")
        _require_identifier(self.correct_action_code, "correct_action_code")
        if type(self.is_correct) is not bool:
            raise G0FutureOutcomeError("is_correct must be a boolean")
        if self.is_correct is not (self.selected_action_code == self.correct_action_code):
            raise G0FutureOutcomeError("is_correct does not match selected/correct action codes")

    def canonical(self) -> dict[str, Any]:
        return {
            "correct_action_code": self.correct_action_code,
            "episode_uid": self.episode_uid,
            "is_correct": self.is_correct,
            "selected_action_code": self.selected_action_code,
        }


_RECEIPT_CONSTRUCTION_TOKEN = object()


@dataclass(frozen=True, slots=True)
class FutureOutcomeReceiptV1:
    plan_sha256: str
    action_seal_sha256: str
    verifier_receipt_sha256: str
    binding_sha256: str
    verification_mode: str
    outcomes: tuple[SyntheticOutcomeV1, ...]
    outcome_owner_independence_established: bool
    cf07_satisfied: bool
    g0_pass_allowed: bool
    claim_ceiling: str
    independent_replay_required: bool
    action_chronology_independently_established: bool
    registration_timestamp_independently_established: bool
    external_singleton_no_retry_registry_implemented: bool
    verifier_execution_evidence_embedded: bool
    receipt_alone_proves_verifier_execution: bool
    receipt_sha256: str
    _construction_token: InitVar[object | None] = None

    def __post_init__(self, _construction_token: object | None) -> None:
        _require_digest(self.plan_sha256, "receipt plan_sha256")
        _require_digest(self.action_seal_sha256, "receipt action_seal_sha256")
        _require_digest(self.verifier_receipt_sha256, "verifier_receipt_sha256")
        _require_digest(self.binding_sha256, "binding_sha256")
        if self.verification_mode not in {"online", "offline"}:
            raise G0FutureOutcomeError("receipt verification_mode must be online or offline")
        if type(self.outcomes) is not tuple or len(self.outcomes) != EPISODE_COUNT:
            raise G0FutureOutcomeError(f"receipt must contain exactly {EPISODE_COUNT} outcomes")
        if any(not isinstance(outcome, SyntheticOutcomeV1) for outcome in self.outcomes):
            raise G0FutureOutcomeError("receipt outcomes must be SyntheticOutcomeV1 values")
        if len({outcome.episode_uid for outcome in self.outcomes}) != EPISODE_COUNT:
            raise G0FutureOutcomeError("receipt outcomes must cover each episode exactly once")
        if self.outcome_owner_independence_established is not False:
            raise G0FutureOutcomeError("outcome owner independence cannot be promoted here")
        if self.cf07_satisfied is not False:
            raise G0FutureOutcomeError("CF-07 cannot be promoted here")
        if self.g0_pass_allowed is not False:
            raise G0FutureOutcomeError("G0 pass cannot be promoted here")
        if self.independent_replay_required is not True:
            raise G0FutureOutcomeError("independent replay remains required")
        if self.action_chronology_independently_established is not False:
            raise G0FutureOutcomeError("caller action timestamp is not independent chronology")
        if self.registration_timestamp_independently_established is not False:
            raise G0FutureOutcomeError(
                "caller registration timestamp is not independent chronology"
            )
        if self.external_singleton_no_retry_registry_implemented is not False:
            raise G0FutureOutcomeError(
                "no durable external singleton/no-retry registry is implemented here"
            )
        if self.verifier_execution_evidence_embedded is not False:
            raise G0FutureOutcomeError("receipt does not embed verifier execution evidence")
        if self.receipt_alone_proves_verifier_execution is not False:
            raise G0FutureOutcomeError("receipt alone cannot prove verifier execution")
        if self.claim_ceiling != CLAIM_CEILING:
            raise G0FutureOutcomeError("receipt claim ceiling is fixed")
        _require_digest(self.receipt_sha256, "receipt_sha256")
        if self.receipt_sha256 != _sha256(self.unsigned()):
            raise G0FutureOutcomeError("receipt self-hash mismatch")
        if _construction_token is not _RECEIPT_CONSTRUCTION_TOKEN:
            raise G0FutureOutcomeError(
                "receipt must be constructed by the verified projection path"
            )

    def unsigned(self) -> dict[str, Any]:
        return {
            "action_seal_sha256": self.action_seal_sha256,
            "binding_sha256": self.binding_sha256,
            "cf07_satisfied": self.cf07_satisfied,
            "claim_ceiling": self.claim_ceiling,
            "g0_pass_allowed": self.g0_pass_allowed,
            "independent_replay_required": self.independent_replay_required,
            "external_singleton_no_retry_registry_implemented": (
                self.external_singleton_no_retry_registry_implemented
            ),
            "action_chronology_independently_established": (
                self.action_chronology_independently_established
            ),
            "registration_timestamp_independently_established": (
                self.registration_timestamp_independently_established
            ),
            "outcome_owner_independence_established": (
                self.outcome_owner_independence_established
            ),
            "outcomes": [outcome.canonical() for outcome in self.outcomes],
            "plan_sha256": self.plan_sha256,
            "schema_version": RECEIPT_SCHEMA,
            "verification_mode": self.verification_mode,
            "verifier_execution_evidence_embedded": (
                self.verifier_execution_evidence_embedded
            ),
            "verifier_receipt_sha256": self.verifier_receipt_sha256,
            "receipt_alone_proves_verifier_execution": (
                self.receipt_alone_proves_verifier_execution
            ),
        }

    def canonical(self) -> dict[str, Any]:
        return {**self.unsigned(), "receipt_sha256": self.receipt_sha256}


_EXECUTION_CAPABILITY = object()


@dataclass(frozen=True, slots=True)
class _VerifiedExecutionCapability:
    """Internal hand-off made only by the pinned verifier invocation path.

    This is an API guard, not an attestation boundary: the resulting receipt
    deliberately records that it embeds no verifier bundle and cannot prove a
    BLS execution to a third party.
    """

    _capability: object
    verifier_receipt: Mapping[str, Any]
    binding: beacon.TaskSeedBindingV1

    def __post_init__(self) -> None:
        if self._capability is not _EXECUTION_CAPABILITY:
            raise G0FutureOutcomeError(
                "projection requires an internal verified-execution capability"
            )
        if not isinstance(self.verifier_receipt, Mapping):
            raise G0FutureOutcomeError("verified execution receipt must be a mapping")
        if not isinstance(self.binding, beacon.TaskSeedBindingV1):
            raise G0FutureOutcomeError("verified execution requires a task-seed binding")


def _verified_execution(
    *, verifier_receipt: Mapping[str, Any], binding: beacon.TaskSeedBindingV1
) -> _VerifiedExecutionCapability:
    """Create the private hand-off immediately after a pinned verifier call."""

    return _VerifiedExecutionCapability(
        _EXECUTION_CAPABILITY,
        verifier_receipt,
        binding,
    )


def _project_after_verified_execution(
    *,
    plan: FutureOutcomePlanV1,
    seal: PrePulseActionSealV1,
    execution: _VerifiedExecutionCapability,
) -> FutureOutcomeReceiptV1:
    """Project a bundle handed off by this module's verifier invocation path.

    ``validate_task_seed_bundle_links`` verifies linkage, not a new BLS run. It
    is intentionally private: public live entry points below call
    ``verify_and_bind_online`` themselves.  This in-process API guard is not a
    third-party attestation; the receipt says so and independent replay remains
    required.
    """

    if not isinstance(execution, _VerifiedExecutionCapability):
        raise G0FutureOutcomeError("projection requires a verified-execution capability")
    _validate_action_seal(plan, seal)
    try:
        verified = beacon.validate_verifier_receipt(
            execution.verifier_receipt,
            plan.commitment,
        )
        beacon.validate_task_seed_bundle_links(
            plan.commitment,
            execution.verifier_receipt,
            execution.binding,
        )
    except beacon.SWM0WBeaconError as exc:
        raise G0FutureOutcomeError(f"verified beacon bundle is invalid: {exc}") from exc
    if verified.mode not in {"online", "offline"}:
        raise G0FutureOutcomeError("unsupported verified beacon mode")
    seeds = execution.binding.task_seed_bytes()
    by_episode = {action.episode_uid: action.action_code for action in seal.actions}
    outcomes: list[SyntheticOutcomeV1] = []
    for episode, seed in zip(plan.episodes, seeds, strict=True):
        correct_action = derive_correct_action(
            seed=seed,
            plan_sha256=plan.plan_sha256,
            episode=episode,
        )
        selected_action = by_episode[episode.episode_uid]
        outcomes.append(
            SyntheticOutcomeV1(
                correct_action_code=correct_action,
                episode_uid=episode.episode_uid,
                is_correct=selected_action == correct_action,
                selected_action_code=selected_action,
            )
        )
    projected_outcomes = tuple(outcomes)
    _validate_projected_outcomes(
        plan=plan,
        seal=seal,
        outcomes=projected_outcomes,
    )
    unsigned = {
        "action_seal_sha256": seal.action_seal_sha256,
        "binding_sha256": execution.binding.binding_sha256,
        "cf07_satisfied": False,
        "claim_ceiling": CLAIM_CEILING,
        "g0_pass_allowed": False,
        "independent_replay_required": True,
        "action_chronology_independently_established": (
            ACTION_CHRONOLOGY_INDEPENDENTLY_ESTABLISHED
        ),
        "external_singleton_no_retry_registry_implemented": (
            EXTERNAL_SINGLETON_NO_RETRY_REGISTRY_IMPLEMENTED
        ),
        "outcome_owner_independence_established": False,
        "outcomes": [outcome.canonical() for outcome in outcomes],
        "plan_sha256": plan.plan_sha256,
        "schema_version": RECEIPT_SCHEMA,
        "verification_mode": verified.mode,
        "registration_timestamp_independently_established": (
            REGISTRATION_TIMESTAMP_INDEPENDENTLY_ESTABLISHED
        ),
        "verifier_execution_evidence_embedded": VERIFIER_EXECUTION_EVIDENCE_EMBEDDED,
        "verifier_receipt_sha256": verified.verifier_receipt_sha256,
        "receipt_alone_proves_verifier_execution": (
            RECEIPT_ALONE_PROVES_VERIFIER_EXECUTION
        ),
    }
    return FutureOutcomeReceiptV1(
        plan_sha256=plan.plan_sha256,
        action_seal_sha256=seal.action_seal_sha256,
        verifier_receipt_sha256=verified.verifier_receipt_sha256,
        binding_sha256=execution.binding.binding_sha256,
        verification_mode=verified.mode,
        outcomes=projected_outcomes,
        outcome_owner_independence_established=False,
        cf07_satisfied=False,
        g0_pass_allowed=False,
        claim_ceiling=CLAIM_CEILING,
        independent_replay_required=True,
        action_chronology_independently_established=(
            ACTION_CHRONOLOGY_INDEPENDENTLY_ESTABLISHED
        ),
        registration_timestamp_independently_established=(
            REGISTRATION_TIMESTAMP_INDEPENDENTLY_ESTABLISHED
        ),
        external_singleton_no_retry_registry_implemented=(
            EXTERNAL_SINGLETON_NO_RETRY_REGISTRY_IMPLEMENTED
        ),
        verifier_execution_evidence_embedded=VERIFIER_EXECUTION_EVIDENCE_EMBEDDED,
        receipt_alone_proves_verifier_execution=(
            RECEIPT_ALONE_PROVES_VERIFIER_EXECUTION
        ),
        receipt_sha256=_sha256(unsigned),
        _construction_token=_RECEIPT_CONSTRUCTION_TOKEN,
    )


def _validate_projected_outcomes(
    *,
    plan: FutureOutcomePlanV1,
    seal: PrePulseActionSealV1,
    outcomes: tuple[SyntheticOutcomeV1, ...],
) -> None:
    expected_uids = tuple(episode.episode_uid for episode in plan.episodes)
    if tuple(outcome.episode_uid for outcome in outcomes) != expected_uids:
        raise G0FutureOutcomeError(
            "receipt outcome roster differs from the ordered plan roster"
        )
    selected_by_uid = {
        action.episode_uid: action.action_code for action in seal.actions
    }
    for episode, outcome in zip(plan.episodes, outcomes, strict=True):
        if outcome.selected_action_code != selected_by_uid[episode.episode_uid]:
            raise G0FutureOutcomeError(
                "receipt selected action differs from the sealed action"
            )
        if outcome.correct_action_code not in episode.action_codes:
            raise G0FutureOutcomeError(
                "receipt correct action is outside the planned opaque pair"
            )


def validate_future_outcome_receipt_links(
    *,
    plan: FutureOutcomePlanV1,
    seal: PrePulseActionSealV1,
    receipt: FutureOutcomeReceiptV1,
) -> None:
    """Validate only plan/seal/outcome links, not BLS execution or independence."""

    if not isinstance(receipt, FutureOutcomeReceiptV1):
        raise G0FutureOutcomeError("receipt must be FutureOutcomeReceiptV1")
    receipt.__post_init__(_RECEIPT_CONSTRUCTION_TOKEN)
    _validate_action_seal(plan, seal)
    if receipt.plan_sha256 != plan.plan_sha256:
        raise G0FutureOutcomeError("receipt belongs to a different plan")
    if receipt.action_seal_sha256 != seal.action_seal_sha256:
        raise G0FutureOutcomeError("receipt belongs to a different action seal")
    _validate_projected_outcomes(
        plan=plan,
        seal=seal,
        outcomes=receipt.outcomes,
    )


def verify_and_project_online(
    *,
    plan: FutureOutcomePlanV1,
    seal: PrePulseActionSealV1,
    allow_network: bool = False,
) -> FutureOutcomeReceiptV1:
    """Execute pinned online BLS verification, then create a non-promoting receipt."""

    verifier_receipt, binding = beacon.verify_and_bind_online(
        plan.commitment, allow_network=allow_network
    )
    return _project_after_verified_execution(
        plan=plan,
        seal=seal,
        execution=_verified_execution(
            verifier_receipt=verifier_receipt,
            binding=binding,
        ),
    )


def verify_and_project_offline_known_answer(
    *,
    plan: FutureOutcomePlanV1,
    seal: PrePulseActionSealV1,
    pulse_file: Path | None = None,
) -> FutureOutcomeReceiptV1:
    """Historical-fixture qualification only; never use this as a live occurrence."""

    verifier_receipt, binding = beacon.verify_and_bind_offline(
        plan.commitment, pulse_file=pulse_file
    )
    return _project_after_verified_execution(
        plan=plan,
        seal=seal,
        execution=_verified_execution(
            verifier_receipt=verifier_receipt,
            binding=binding,
        ),
    )


__all__ = [
    "ACTION_SEAL_SCHEMA",
    "ACTION_CHRONOLOGY_INDEPENDENTLY_ESTABLISHED",
    "EXTERNAL_SINGLETON_NO_RETRY_REGISTRY_IMPLEMENTED",
    "CLAIM_CEILING",
    "EPISODE_COUNT",
    "FutureOutcomePlanV1",
    "FutureOutcomeReceiptV1",
    "G0FutureOutcomeError",
    "RECEIPT_ALONE_PROVES_VERIFIER_EXECUTION",
    "REGISTRATION_TIMESTAMP_INDEPENDENTLY_ESTABLISHED",
    "VERIFIER_EXECUTION_EVIDENCE_EMBEDDED",
    "OpaqueEpisodeV1",
    "PrePulseActionSealV1",
    "SealedActionV1",
    "SyntheticOutcomeV1",
    "derive_correct_action",
    "make_action_seal",
    "make_plan",
    "registration_payload",
    "validate_future_outcome_receipt_links",
    "verify_and_project_offline_known_answer",
    "verify_and_project_online",
]
