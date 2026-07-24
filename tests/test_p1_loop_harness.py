from __future__ import annotations

import pytest

from hswm_weight_snapshot import SlowWeightV1, canonical_sha256, make_initial_snapshot
from p1_eligibility_tag import make_activation_trace
from p1_loop_harness import (
    CandidateGateV1,
    EpisodeObservationV1,
    modulation_permutation,
    run_p1_experiment,
)


PREREG_SHA = "1" * 64
SPLIT_SHA = "2" * 64


class SyntheticEnvironment:
    rewards = (0.2, 0.6, 0.1, 0.8, 0.4)

    def __init__(self, *, canary_drop: float = 0.0) -> None:
        self.canary_drop = canary_drop

    def observe_episode(self, arm_id, episode_index, snapshot):
        episode_id = f"episode:{episode_index}"
        query_sha = canonical_sha256(
            {"arm_id": arm_id, "episode_index": episode_index, "query": "sealed"}
        )
        trace_a = make_activation_trace(
            episode_id=episode_id,
            question_id=f"q:{episode_index}:a",
            query_sha256=query_sha,
            snapshot_id=snapshot.snapshot_id,
            target_id="target:a",
            edge_ids=("edge:a", "edge:b"),
            raw_contribution=2.0,
        )
        trace_b = make_activation_trace(
            episode_id=episode_id,
            question_id=f"q:{episode_index}:b",
            query_sha256=query_sha,
            snapshot_id=snapshot.snapshot_id,
            target_id="target:b",
            edge_ids=("edge:b",),
            raw_contribution=1.0,
        )
        return EpisodeObservationV1(
            arm_id=arm_id,
            episode_index=episode_index,
            episode_id=episode_id,
            snapshot_id=snapshot.snapshot_id,
            reward=self.rewards[episode_index - 1],
            recall10=0.2 + episode_index / 100,
            evaluator_receipt_sha256=canonical_sha256(
                {"arm_id": arm_id, "episode_index": episode_index, "sealed": True}
            ),
            winning_traces=(trace_a, trace_b),
            correct_question_ids=(f"q:{episode_index}:a",),
        )

    def evaluate_candidate(
        self, arm_id, episode_index, base_snapshot, candidate_snapshot, history
    ):
        return CandidateGateV1(
            evidence_hash=canonical_sha256(
                {
                    "arm_id": arm_id,
                    "episode_index": episode_index,
                    "base": base_snapshot.snapshot_id,
                    "candidate": candidate_snapshot.snapshot_id,
                    "history": len(history),
                }
            ),
            unseen_delta=0.02,
            unseen_ci_low=0.001,
            retention_delta=0.0,
            canary_drop=self.canary_drop,
        )


def _initial():
    return make_initial_snapshot(
        (SlowWeightV1("edge:a", -1.0), SlowWeightV1("edge:b", -1.0)),
        topology_sha256="3" * 64,
        provenance_root_sha256="4" * 64,
    )


def _by_arm(receipt):
    return {arm.arm_id: arm for arm in receipt.arms}


def test_four_arm_loop_uses_fsm_cas_shuffle_and_equal_l1(tmp_path):
    receipt = run_p1_experiment(
        experiment_id="synthetic-p1",
        initial_snapshot=_initial(),
        environment=SyntheticEnvironment(),
        work_directory=tmp_path,
        preregistration_sha256=PREREG_SHA,
        split_manifest_sha256=SPLIT_SHA,
    )
    arms = _by_arm(receipt)
    a1 = arms["A1_tagged_commit"]
    a2 = arms["A2_no_commit"]
    a3 = arms["A3_shuffled_M"]
    a4 = arms["A4_uniform_commit"]

    assert receipt.receipt_id == canonical_sha256(receipt.unsigned())
    assert a1.final_snapshot_id != a1.starting_snapshot_id
    assert a2.final_snapshot_id == a2.starting_snapshot_id
    assert all(
        episode.fsm_final_state == "active"
        for episode in a1.episodes[1:]
    )
    assert all(episode.model_calls == 40 for arm in receipt.arms for episode in arm.episodes)

    a1_modulations = tuple(episode.observed_modulation for episode in a1.episodes)
    a3_modulations = tuple(episode.applied_modulation for episode in a3.episodes)
    assert a3_modulations == tuple(
        a1_modulations[index] for index in modulation_permutation(5)
    )
    assert sorted(a3_modulations) == sorted(a1_modulations)
    assert tuple(episode.applied_modulation for episode in a4.episodes) == a1_modulations
    assert tuple(episode.proposed_l1 for episode in a4.episodes) == pytest.approx(tuple(
        episode.proposed_l1 for episode in a1.episodes
    ), abs=1e-12)


def test_canary_failure_rejects_candidate_without_active_mutation(tmp_path):
    receipt = run_p1_experiment(
        experiment_id="synthetic-p1-canary-fail",
        initial_snapshot=_initial(),
        environment=SyntheticEnvironment(canary_drop=0.03),
        work_directory=tmp_path,
        preregistration_sha256=PREREG_SHA,
        split_manifest_sha256=SPLIT_SHA,
    )

    for arm in receipt.arms:
        assert arm.final_snapshot_id == arm.starting_snapshot_id
        for episode in arm.episodes:
            if episode.candidate_id is not None:
                assert episode.fsm_final_state == "rejected"
                assert episode.activation_receipt_id is None
