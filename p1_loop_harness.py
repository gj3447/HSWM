"""Bounded four-arm HSWM P1 loop with absorption-FSM and CAS activation.

The harness owns orchestration only.  An environment port performs retrieval,
fixed-model answering, sealed evaluation, and fresh/canary probes.  The harness
never passes gold answers into the learner and never mutates active weights;
all mutations are immutable candidates promoted through the existing
absorption FSM and ``SQLiteWeightStore`` compare-and-swap activation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
from typing import Protocol, Sequence

from hswm_weight_snapshot import WeightSnapshotV1, canonical_sha256
from hswm_weight_store import SQLiteWeightStore, StaleWeightEpochError
from p1_eligibility_tag import ActivationTraceV1, derive_eligibility_tags
from p1_m_commit import (
    ARMS,
    ArmId,
    P1LearningPolicyV1,
    build_commit_decision,
    expanding_baseline,
    make_outcome_receipt,
)
from prom_search_hswm.hswm_absorption_fsm import (
    CandidateConfig,
    Command,
    make_event,
    step,
)


EPISODES = 5
QUESTIONS_PER_EPISODE = 40
SHUFFLE_SEED = 9173
CANARY_EPSILON = 0.02


class P1HarnessError(RuntimeError):
    """The bounded experiment or its environment violated a frozen contract."""


@dataclass(frozen=True)
class EpisodeObservationV1:
    arm_id: ArmId
    episode_index: int
    episode_id: str
    snapshot_id: str
    reward: float
    recall10: float
    evaluator_receipt_sha256: str
    winning_traces: tuple[ActivationTraceV1, ...]
    correct_question_ids: tuple[str, ...] = ()
    model_calls: int = QUESTIONS_PER_EPISODE

    def __post_init__(self) -> None:
        if self.arm_id not in ARMS:
            raise P1HarnessError("observation has an unknown arm")
        if self.episode_index < 1:
            raise P1HarnessError("episode_index must be positive")
        for label, value in (("reward", self.reward), ("recall10", self.recall10)):
            if not 0.0 <= value <= 1.0:
                raise P1HarnessError(f"{label} must be in [0, 1]")
        if self.model_calls != QUESTIONS_PER_EPISODE:
            raise P1HarnessError("every arm/episode must make exactly 40 answer calls")
        if any(
            trace.episode_id != self.episode_id or trace.snapshot_id != self.snapshot_id
            for trace in self.winning_traces
        ):
            raise P1HarnessError("winning trace is not bound to the observation cut")


@dataclass(frozen=True)
class CandidateGateV1:
    evidence_hash: str
    unseen_delta: float
    unseen_ci_low: float
    retention_delta: float
    canary_drop: float
    fresh_holdout: bool = True
    evidence_replayed: bool = True
    equal_budget: bool = True
    no_overlap: bool = True
    independent_evaluator: bool = True

    @property
    def canary_passed(self) -> bool:
        return self.canary_drop <= CANARY_EPSILON


class P1EnvironmentPort(Protocol):
    """Gold remains inside this port; observations expose only receipts/traces."""

    def observe_episode(
        self,
        arm_id: ArmId,
        episode_index: int,
        snapshot: WeightSnapshotV1,
    ) -> EpisodeObservationV1: ...

    def evaluate_candidate(
        self,
        arm_id: ArmId,
        episode_index: int,
        base_snapshot: WeightSnapshotV1,
        candidate_snapshot: WeightSnapshotV1,
        history: Sequence[EpisodeObservationV1],
    ) -> CandidateGateV1: ...


@dataclass(frozen=True)
class EpisodeRunReceiptV1:
    arm_id: ArmId
    episode_index: int
    episode_id: str
    base_snapshot_id: str
    active_snapshot_id: str
    reward: float
    recall10: float
    baseline: float | None
    observed_modulation: float
    applied_modulation: float
    candidate_id: str | None
    proposed_l1: float
    fsm_final_state: str
    activation_receipt_id: str | None
    committed_deltas: tuple[tuple[str, float], ...]
    canary_drop: float | None
    model_calls: int

    def canonical(self) -> dict[str, object]:
        return {
            "arm_id": self.arm_id,
            "episode_index": self.episode_index,
            "episode_id": self.episode_id,
            "base_snapshot_id": self.base_snapshot_id,
            "active_snapshot_id": self.active_snapshot_id,
            "reward": self.reward,
            "recall10": self.recall10,
            "baseline": self.baseline,
            "observed_modulation": self.observed_modulation,
            "applied_modulation": self.applied_modulation,
            "candidate_id": self.candidate_id,
            "proposed_l1": self.proposed_l1,
            "fsm_final_state": self.fsm_final_state,
            "activation_receipt_id": self.activation_receipt_id,
            "committed_deltas": [list(item) for item in self.committed_deltas],
            "canary_drop": self.canary_drop,
            "model_calls": self.model_calls,
        }


@dataclass(frozen=True)
class ArmRunReceiptV1:
    arm_id: ArmId
    starting_snapshot_id: str
    final_snapshot_id: str
    episodes: tuple[EpisodeRunReceiptV1, ...]

    def canonical(self) -> dict[str, object]:
        return {
            "arm_id": self.arm_id,
            "starting_snapshot_id": self.starting_snapshot_id,
            "final_snapshot_id": self.final_snapshot_id,
            "episodes": [episode.canonical() for episode in self.episodes],
        }


@dataclass(frozen=True)
class P1ExperimentReceiptV1:
    experiment_id: str
    preregistration_sha256: str
    split_manifest_sha256: str
    shuffle_permutation: tuple[int, ...]
    arms: tuple[ArmRunReceiptV1, ...]
    receipt_id: str
    schema_version: str = "hswm-p1-experiment-receipt/v1"

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "preregistration_sha256": self.preregistration_sha256,
            "split_manifest_sha256": self.split_manifest_sha256,
            "shuffle_seed": SHUFFLE_SEED,
            "shuffle_permutation": list(self.shuffle_permutation),
            "arms": [arm.canonical() for arm in self.arms],
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "receipt_id": self.receipt_id}


def modulation_permutation(length: int, seed: int = SHUFFLE_SEED) -> tuple[int, ...]:
    if length < 2:
        raise P1HarnessError("shuffle requires at least two episodes")
    indices = list(range(length))
    random.Random(seed).shuffle(indices)
    if indices == list(range(length)):
        indices = indices[1:] + indices[:1]
    return tuple(indices)


def _reduce(
    config: CandidateConfig, event_type: str, event_id: str, actor: str, **payload: object
) -> tuple[CandidateConfig, Command]:
    event = make_event(config, event_type, event_id, actor, **payload)
    updated, commands = step(config, event)
    if len(commands) != 1 or commands[0].kind == "AuditInvalidTransition":
        detail = commands[0].payload.get("reason") if commands else "missing_command"
        raise P1HarnessError(f"absorption FSM rejected {event_type}: {detail}")
    return updated, commands[0]


def _run_candidate_gate(
    *,
    candidate_id: str,
    base_snapshot_id: str,
    preregistration_sha256: str,
    split_manifest_sha256: str,
    gate: CandidateGateV1,
    store: SQLiteWeightStore,
) -> tuple[str, str | None]:
    config = CandidateConfig(
        candidate_id=candidate_id,
        implementer_id="p1-loop-harness",
        base_version=base_snapshot_id,
        rollback_target_hash=base_snapshot_id,
    )
    prefix = candidate_id[:16]
    config, _ = _reduce(
        config,
        "ABSORB",
        f"{prefix}:absorb",
        "p1-loop-harness",
        source_manifest_hash=split_manifest_sha256,
    )
    config, _ = _reduce(
        config,
        "FREEZE",
        f"{prefix}:freeze",
        "p1-loop-harness",
        candidate_hash=candidate_id,
        prereg_hash=preregistration_sha256,
        split_manifest_hash=split_manifest_sha256,
    )
    config, _ = _reduce(
        config,
        "START_EVALUATION",
        f"{prefix}:evaluate",
        "independent-environment",
        candidate_hash=candidate_id,
        fresh_holdout=gate.fresh_holdout,
        holdout_epoch=f"candidate:{candidate_id}",
        evaluator_id="sealed-environment",
    )
    config, _ = _reduce(
        config,
        "EVALUATION_RECORDED",
        f"{prefix}:evaluated",
        "sealed-environment",
        candidate_hash=candidate_id,
        evidence_hash=gate.evidence_hash,
        evidence_replayed=gate.evidence_replayed,
        equal_budget=gate.equal_budget,
        no_overlap=gate.no_overlap,
        independent_evaluator=gate.independent_evaluator,
        unseen_delta=gate.unseen_delta,
        unseen_ci_low=gate.unseen_ci_low,
        retention_delta=gate.retention_delta,
        reason="fresh_evaluation_gate_failed",
    )
    if config.state != "canary":
        return config.state, None
    if not gate.canary_passed:
        config, _ = _reduce(
            config,
            "CANARY_FAILED",
            f"{prefix}:canary-failed",
            "sealed-environment",
            reason="canary_drop_exceeded_epsilon",
        )
        return config.state, None
    config, _ = _reduce(
        config,
        "CANARY_OBSERVATION",
        f"{prefix}:canary",
        "sealed-environment",
        no_regression=True,
        equal_budget=True,
        window_id=f"canary:{candidate_id}",
    )
    config, _ = _reduce(
        config,
        "REQUEST_PROMOTION",
        f"{prefix}:promotion",
        "p1-loop-harness",
        request_id=f"activate:{candidate_id}",
    )
    try:
        activation = store.activate(candidate_id)
    except StaleWeightEpochError:
        config, _ = _reduce(
            config,
            "ACTIVATION_FAILED",
            f"{prefix}:stale",
            "weight-store",
            failure_class="stale_base",
            reason="active_epoch_cas_lost",
        )
        return config.state, None
    config, _ = _reduce(
        config,
        "ACTIVATION_COMMITTED",
        f"{prefix}:activated",
        "weight-store",
        candidate_hash=candidate_id,
        base_version=base_snapshot_id,
        receipt_hash=activation.receipt_id,
    )
    return config.state, activation.receipt_id


def _run_arm(
    arm_id: ArmId,
    *,
    initial_snapshot: WeightSnapshotV1,
    environment: P1EnvironmentPort,
    work_directory: Path,
    preregistration_sha256: str,
    split_manifest_sha256: str,
    policy: P1LearningPolicyV1,
    modulation_override: Sequence[float] | None = None,
    l1_override: Sequence[float] | None = None,
) -> ArmRunReceiptV1:
    if modulation_override is not None and len(modulation_override) != EPISODES:
        raise P1HarnessError("modulation override length differs from episode count")
    if l1_override is not None and len(l1_override) != EPISODES:
        raise P1HarnessError("L1 override length differs from episode count")
    history: list[EpisodeObservationV1] = []
    rewards: list[float] = []
    receipts: list[EpisodeRunReceiptV1] = []
    store_path = work_directory / f"{arm_id}.weights.sqlite3"
    with SQLiteWeightStore(store_path, initial_snapshot=initial_snapshot) as store:
        for episode_index in range(1, EPISODES + 1):
            base = store.active_snapshot()
            observation = environment.observe_episode(arm_id, episode_index, base)
            expected_episode = f"episode:{episode_index}"
            if (
                observation.arm_id != arm_id
                or observation.episode_index != episode_index
                or observation.episode_id != expected_episode
                or observation.snapshot_id != base.snapshot_id
            ):
                raise P1HarnessError("environment observation cut mismatch")
            outcome = make_outcome_receipt(
                arm_id=arm_id,
                episode_id=observation.episode_id,
                reward=observation.reward,
                evaluator_receipt_sha256=observation.evaluator_receipt_sha256,
            )
            baseline = expanding_baseline(outcome, rewards)
            applied_modulation = (
                baseline.modulation
                if modulation_override is None
                else float(modulation_override[episode_index - 1])
            )
            tags = derive_eligibility_tags(
                observation.episode_id, observation.winning_traces
            )
            decision = build_commit_decision(
                base,
                tags,
                outcome=outcome,
                modulation=applied_modulation,
                policy=policy,
                uniform_target_l1=(
                    None if l1_override is None else float(l1_override[episode_index - 1])
                ),
            )
            fsm_state = "no_candidate"
            activation_id = None
            canary_drop = None
            if decision.candidate is not None:
                staged = store.stage(decision.candidate)
                gate = environment.evaluate_candidate(
                    arm_id, episode_index, base, staged, tuple(history)
                )
                canary_drop = gate.canary_drop
                fsm_state, activation_id = _run_candidate_gate(
                    candidate_id=decision.candidate.candidate_id,
                    base_snapshot_id=base.snapshot_id,
                    preregistration_sha256=preregistration_sha256,
                    split_manifest_sha256=split_manifest_sha256,
                    gate=gate,
                    store=store,
                )
            active = store.active_snapshot()
            committed_deltas = (
                ()
                if activation_id is None or decision.candidate is None
                else tuple(
                    (
                        delta.edge_id,
                        delta.after_log_salience - delta.before_log_salience,
                    )
                    for delta in decision.candidate.deltas
                )
            )
            receipts.append(
                EpisodeRunReceiptV1(
                    arm_id=arm_id,
                    episode_index=episode_index,
                    episode_id=observation.episode_id,
                    base_snapshot_id=base.snapshot_id,
                    active_snapshot_id=active.snapshot_id,
                    reward=observation.reward,
                    recall10=observation.recall10,
                    baseline=baseline.baseline,
                    observed_modulation=baseline.modulation,
                    applied_modulation=applied_modulation,
                    candidate_id=(
                        None if decision.candidate is None else decision.candidate.candidate_id
                    ),
                    proposed_l1=decision.actual_l1,
                    fsm_final_state=fsm_state,
                    activation_receipt_id=activation_id,
                    committed_deltas=committed_deltas,
                    canary_drop=canary_drop,
                    model_calls=observation.model_calls,
                )
            )
            rewards.append(observation.reward)
            history.append(observation)
        final_snapshot = store.active_snapshot()
    return ArmRunReceiptV1(
        arm_id=arm_id,
        starting_snapshot_id=initial_snapshot.snapshot_id,
        final_snapshot_id=final_snapshot.snapshot_id,
        episodes=tuple(receipts),
    )


def run_p1_experiment(
    *,
    experiment_id: str,
    initial_snapshot: WeightSnapshotV1,
    environment: P1EnvironmentPort,
    work_directory: str | Path,
    preregistration_sha256: str,
    split_manifest_sha256: str,
    policy: P1LearningPolicyV1 = P1LearningPolicyV1(),
) -> P1ExperimentReceiptV1:
    work = Path(work_directory)
    work.mkdir(parents=True, exist_ok=True)
    a1 = _run_arm(
        "A1_tagged_commit",
        initial_snapshot=initial_snapshot,
        environment=environment,
        work_directory=work,
        preregistration_sha256=preregistration_sha256,
        split_manifest_sha256=split_manifest_sha256,
        policy=policy,
    )
    a1_modulations = tuple(episode.observed_modulation for episode in a1.episodes)
    a1_l1 = tuple(episode.proposed_l1 for episode in a1.episodes)
    permutation = modulation_permutation(EPISODES)
    shuffled = tuple(a1_modulations[index] for index in permutation)
    a2 = _run_arm(
        "A2_no_commit",
        initial_snapshot=initial_snapshot,
        environment=environment,
        work_directory=work,
        preregistration_sha256=preregistration_sha256,
        split_manifest_sha256=split_manifest_sha256,
        policy=policy,
    )
    a3 = _run_arm(
        "A3_shuffled_M",
        initial_snapshot=initial_snapshot,
        environment=environment,
        work_directory=work,
        preregistration_sha256=preregistration_sha256,
        split_manifest_sha256=split_manifest_sha256,
        policy=policy,
        modulation_override=shuffled,
    )
    a4 = _run_arm(
        "A4_uniform_commit",
        initial_snapshot=initial_snapshot,
        environment=environment,
        work_directory=work,
        preregistration_sha256=preregistration_sha256,
        split_manifest_sha256=split_manifest_sha256,
        policy=policy,
        modulation_override=a1_modulations,
        l1_override=a1_l1,
    )
    arms = (a1, a2, a3, a4)
    unsigned = {
        "schema_version": "hswm-p1-experiment-receipt/v1",
        "experiment_id": experiment_id,
        "preregistration_sha256": preregistration_sha256,
        "split_manifest_sha256": split_manifest_sha256,
        "shuffle_seed": SHUFFLE_SEED,
        "shuffle_permutation": list(permutation),
        "arms": [arm.canonical() for arm in arms],
    }
    return P1ExperimentReceiptV1(
        experiment_id=experiment_id,
        preregistration_sha256=preregistration_sha256,
        split_manifest_sha256=split_manifest_sha256,
        shuffle_permutation=permutation,
        arms=arms,
        receipt_id=canonical_sha256(unsigned),
    )


__all__ = [
    "CANARY_EPSILON",
    "CandidateGateV1",
    "EPISODES",
    "EpisodeObservationV1",
    "P1EnvironmentPort",
    "P1ExperimentReceiptV1",
    "P1HarnessError",
    "QUESTIONS_PER_EPISODE",
    "SHUFFLE_SEED",
    "modulation_permutation",
    "run_p1_experiment",
]
