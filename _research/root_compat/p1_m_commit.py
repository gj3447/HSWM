"""Post-hoc reward modulation and bounded candidate construction for HSWM P1."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Literal, Sequence

from hswm_weight_snapshot import (
    WeightCandidateV1,
    WeightDeltaV1,
    WeightSnapshotV1,
    canonical_sha256,
    make_weight_candidate,
)
from p1_eligibility_tag import EligibilityTagV1


ArmId = Literal[
    "A1_tagged_commit",
    "A2_no_commit",
    "A3_shuffled_M",
    "A4_uniform_commit",
]
ARMS: tuple[ArmId, ...] = (
    "A1_tagged_commit",
    "A2_no_commit",
    "A3_shuffled_M",
    "A4_uniform_commit",
)
OUTCOME_SCHEMA_VERSION = "hswm-p1-outcome-receipt/v1"
BASELINE_SCHEMA_VERSION = "hswm-p1-baseline-receipt/v1"
POLICY_SCHEMA_VERSION = "hswm-p1-learning-policy/v1"


class P1CommitContractError(ValueError):
    """Reward, baseline, tags, or weight update violate the frozen P1 rule."""


def _unit(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise P1CommitContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise P1CommitContractError(f"{label} must be finite and in [0, 1]")
    return result


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise P1CommitContractError(f"{label} must be non-empty text")
    return value


def _sha(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise P1CommitContractError(f"{label} must be a lowercase SHA-256")
    return value


@dataclass(frozen=True)
class P1LearningPolicyV1:
    eta: float = 0.05
    lower_log_salience: float = -20.0
    upper_log_salience: float = 0.0
    schema_version: str = POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not math.isfinite(self.eta) or self.eta <= 0.0:
            raise P1CommitContractError("eta must be finite and positive")
        if (
            not math.isfinite(self.lower_log_salience)
            or not math.isfinite(self.upper_log_salience)
            or self.lower_log_salience >= self.upper_log_salience
            or self.upper_log_salience != 0.0
        ):
            raise P1CommitContractError("weight bounds must satisfy lower < upper == 0")
        if self.schema_version != POLICY_SCHEMA_VERSION:
            raise P1CommitContractError("unsupported learning policy schema")

    def canonical(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "eta": self.eta,
            "lower_log_salience": self.lower_log_salience,
            "upper_log_salience": self.upper_log_salience,
        }

    @property
    def policy_sha256(self) -> str:
        return canonical_sha256(self.canonical())


@dataclass(frozen=True)
class OutcomeReceiptV1:
    receipt_id: str
    arm_id: ArmId
    episode_id: str
    reward: float
    evaluator_receipt_sha256: str
    schema_version: str = OUTCOME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _sha(self.receipt_id, "receipt_id")
        if self.arm_id not in ARMS:
            raise P1CommitContractError("unknown P1 arm")
        _text(self.episode_id, "episode_id")
        object.__setattr__(self, "reward", _unit(self.reward, "reward"))
        _sha(self.evaluator_receipt_sha256, "evaluator_receipt_sha256")
        if self.schema_version != OUTCOME_SCHEMA_VERSION:
            raise P1CommitContractError("unsupported outcome schema")
        if self.receipt_id != canonical_sha256(self.unsigned()):
            raise P1CommitContractError("outcome receipt digest mismatch")

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "arm_id": self.arm_id,
            "episode_id": self.episode_id,
            "reward": self.reward,
            "evaluator_receipt_sha256": self.evaluator_receipt_sha256,
        }


def make_outcome_receipt(
    *,
    arm_id: ArmId,
    episode_id: str,
    reward: float,
    evaluator_receipt_sha256: str,
) -> OutcomeReceiptV1:
    unsigned = {
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "arm_id": arm_id,
        "episode_id": _text(episode_id, "episode_id"),
        "reward": _unit(reward, "reward"),
        "evaluator_receipt_sha256": _sha(
            evaluator_receipt_sha256, "evaluator_receipt_sha256"
        ),
    }
    if arm_id not in ARMS:
        raise P1CommitContractError("unknown P1 arm")
    return OutcomeReceiptV1(
        receipt_id=canonical_sha256(unsigned),
        **{key: value for key, value in unsigned.items() if key != "schema_version"},
    )


@dataclass(frozen=True)
class BaselineReceiptV1:
    receipt_id: str
    arm_id: ArmId
    episode_id: str
    prior_rewards: tuple[float, ...]
    current_reward: float
    baseline: float | None
    modulation: float
    schema_version: str = BASELINE_SCHEMA_VERSION

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "arm_id": self.arm_id,
            "episode_id": self.episode_id,
            "prior_rewards": list(self.prior_rewards),
            "current_reward": self.current_reward,
            "baseline": self.baseline,
            "modulation": self.modulation,
        }


def expanding_baseline(
    outcome: OutcomeReceiptV1, prior_rewards: Sequence[float]
) -> BaselineReceiptV1:
    prior = tuple(_unit(value, "prior_reward") for value in prior_rewards)
    baseline = None if not prior else math.fsum(prior) / len(prior)
    modulation = 0.0 if baseline is None else outcome.reward - baseline
    unsigned = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "arm_id": outcome.arm_id,
        "episode_id": outcome.episode_id,
        "prior_rewards": list(prior),
        "current_reward": outcome.reward,
        "baseline": baseline,
        "modulation": modulation,
    }
    return BaselineReceiptV1(
        receipt_id=canonical_sha256(unsigned),
        arm_id=outcome.arm_id,
        episode_id=outcome.episode_id,
        prior_rewards=prior,
        current_reward=outcome.reward,
        baseline=baseline,
        modulation=modulation,
    )


@dataclass(frozen=True)
class CommitDecisionV1:
    arm_id: ArmId
    episode_id: str
    modulation: float
    candidate: WeightCandidateV1 | None
    actual_l1: float
    reason: str


def _uniform_allocations(
    before: dict[str, float],
    *,
    total_l1: float,
    direction: int,
    policy: P1LearningPolicyV1,
) -> dict[str, float]:
    capacities = {
        edge_id: (
            policy.upper_log_salience - value
            if direction > 0
            else value - policy.lower_log_salience
        )
        for edge_id, value in before.items()
    }
    allocations = {edge_id: 0.0 for edge_id in before}
    active = [edge_id for edge_id in sorted(before) if capacities[edge_id] > 0.0]
    remaining = total_l1
    while active and remaining > 1e-15:
        share = remaining / len(active)
        spent = 0.0
        next_active = []
        for edge_id in active:
            capacity = capacities[edge_id] - allocations[edge_id]
            amount = min(share, capacity)
            allocations[edge_id] += amount
            spent += amount
            if capacity - amount > 1e-15:
                next_active.append(edge_id)
        if spent <= 0.0:
            break
        remaining = max(0.0, remaining - spent)
        active = next_active
    if remaining > 1e-12:
        raise P1CommitContractError("uniform arm cannot match tagged L1 budget")
    return allocations


def build_commit_decision(
    base: WeightSnapshotV1,
    tags: Iterable[EligibilityTagV1],
    *,
    outcome: OutcomeReceiptV1,
    modulation: float,
    policy: P1LearningPolicyV1 = P1LearningPolicyV1(),
    uniform_target_l1: float | None = None,
) -> CommitDecisionV1:
    """Build an immutable candidate; only the store may later stage/activate it."""

    if outcome.arm_id not in ARMS:
        raise P1CommitContractError("unknown P1 arm")
    if not math.isfinite(modulation) or not -1.0 <= modulation <= 1.0:
        raise P1CommitContractError("modulation must be finite and in [-1, 1]")
    if uniform_target_l1 is not None and (
        not math.isfinite(uniform_target_l1) or uniform_target_l1 < 0.0
    ):
        raise P1CommitContractError("uniform_target_l1 must be finite and non-negative")
    if uniform_target_l1 is not None and outcome.arm_id != "A4_uniform_commit":
        raise P1CommitContractError("uniform_target_l1 is only valid for A4")
    tag_tuple = tuple(tags)
    if len({tag.edge_id for tag in tag_tuple}) != len(tag_tuple):
        raise P1CommitContractError("eligibility tags must have unique edge IDs")
    if any(
        tag.episode_id != outcome.episode_id or tag.snapshot_id != base.snapshot_id
        for tag in tag_tuple
    ):
        raise P1CommitContractError("tags must bind the outcome episode and base snapshot")
    if tag_tuple and not math.isclose(
        math.fsum(tag.tag_strength for tag in tag_tuple), 1.0, abs_tol=1e-12
    ):
        raise P1CommitContractError("tag strengths must sum to one")
    before_map = base.weight_map()
    if any(tag.edge_id not in before_map for tag in tag_tuple):
        raise P1CommitContractError("eligibility tag addresses an unknown edge")
    if outcome.arm_id == "A2_no_commit":
        return CommitDecisionV1(
            outcome.arm_id, outcome.episode_id, modulation, None, 0.0, "arm_no_commit"
        )
    if not tag_tuple:
        return CommitDecisionV1(
            outcome.arm_id, outcome.episode_id, modulation, None, 0.0, "no_winning_trace"
        )
    if modulation == 0.0:
        return CommitDecisionV1(
            outcome.arm_id, outcome.episode_id, modulation, None, 0.0, "zero_modulation"
        )

    tagged_after: dict[str, float] = {}
    tag_by_edge = {tag.edge_id: tag for tag in tag_tuple}
    for tag in tag_tuple:
        before = before_map[tag.edge_id]
        requested = before + policy.eta * modulation * tag.tag_strength
        tagged_after[tag.edge_id] = min(
            policy.upper_log_salience,
            max(policy.lower_log_salience, requested),
        )
    tagged_l1 = math.fsum(
        abs(tagged_after[edge_id] - before_map[edge_id]) for edge_id in tagged_after
    )
    if tagged_l1 <= 0.0:
        return CommitDecisionV1(
            outcome.arm_id, outcome.episode_id, modulation, None, 0.0, "all_deltas_clipped"
        )

    if outcome.arm_id == "A4_uniform_commit":
        direction = 1 if modulation > 0.0 else -1
        touched_before = {tag.edge_id: before_map[tag.edge_id] for tag in tag_tuple}
        allocations = _uniform_allocations(
            touched_before,
            total_l1=tagged_l1 if uniform_target_l1 is None else uniform_target_l1,
            direction=direction,
            policy=policy,
        )
        after_by_edge = {
            edge_id: before + direction * allocations[edge_id]
            for edge_id, before in touched_before.items()
        }
    else:
        after_by_edge = tagged_after

    deltas = tuple(
        WeightDeltaV1(
            edge_id=edge_id,
            before_log_salience=before_map[edge_id],
            after_log_salience=after,
            eligibility_tag_sha256=tag_by_edge[edge_id].tag_id,
        )
        for edge_id, after in sorted(after_by_edge.items())
        if after != before_map[edge_id]
    )
    if not deltas:
        return CommitDecisionV1(
            outcome.arm_id,
            outcome.episode_id,
            modulation,
            None,
            0.0,
            "zero_uniform_budget",
        )
    actual_l1 = math.fsum(
        abs(delta.after_log_salience - delta.before_log_salience) for delta in deltas
    )
    provenance_root = canonical_sha256(
        {
            "arm_id": outcome.arm_id,
            "episode_id": outcome.episode_id,
            "outcome_receipt_id": outcome.receipt_id,
            "eligibility_tag_ids": [tag.tag_id for tag in sorted(tag_tuple)],
            "modulation": modulation,
            "actual_l1": actual_l1,
        }
    )
    candidate = make_weight_candidate(
        base,
        deltas,
        learning_policy_sha256=policy.policy_sha256,
        provenance_root_sha256=provenance_root,
    )
    return CommitDecisionV1(
        outcome.arm_id,
        outcome.episode_id,
        modulation,
        candidate,
        actual_l1,
        "candidate_ready",
    )


__all__ = [
    "ARMS",
    "ArmId",
    "BaselineReceiptV1",
    "CommitDecisionV1",
    "OutcomeReceiptV1",
    "P1CommitContractError",
    "P1LearningPolicyV1",
    "build_commit_decision",
    "expanding_baseline",
    "make_outcome_receipt",
]
