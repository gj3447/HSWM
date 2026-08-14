from __future__ import annotations

import json

import pytest

from hswm_token_learning_contract import (
    TokenLearningContractError,
    make_token_learning_receipt,
    make_token_trajectory,
)
from hswm_weight_snapshot import SlowWeightV1, make_initial_snapshot
from hswm_weight_store import SQLiteWeightStore
from p1_eligibility_tag import derive_eligibility_tags
from p1_m_commit import build_commit_decision, make_outcome_receipt


def _sha(character: str) -> str:
    return character * 64


def _chain():
    base = make_initial_snapshot(
        (SlowWeightV1("edge:a", -0.5), SlowWeightV1("edge:b", -0.5)),
        topology_sha256=_sha("1"),
        provenance_root_sha256=_sha("2"),
    )
    trajectory = make_token_trajectory(
        episode_id="episode:token:1",
        function_id="answer-synthesizer",
        decision_kind="AGGREGATE",
        model_revision_sha256=_sha("3"),
        function_registry_sha256=_sha("4"),
        snapshot_id=base.snapshot_id,
        input_sha256=_sha("5"),
        output_sha256=_sha("6"),
        input_token_count=120,
        output_token_count=24,
        external_action_sha256=_sha("7"),
        tool_receipt_sha256s=(_sha("8"),),
        used_edge_ids=("edge:b", "edge:a"),
        raw_contribution=1.0,
        pre_outcome_seal_sha256=_sha("9"),
    )
    trace = trajectory.activation_trace()
    tags = derive_eligibility_tags(trajectory.episode_id, (trace,))
    outcome = make_outcome_receipt(
        arm_id="A1_tagged_commit",
        episode_id=trajectory.episode_id,
        reward=0.8,
        evaluator_receipt_sha256=_sha("a"),
    )
    decision = build_commit_decision(base, tags, outcome=outcome, modulation=0.4)
    assert decision.candidate is not None
    return base, trajectory, tags, outcome, decision.candidate


def test_trajectory_is_deterministic_pre_outcome_and_contains_no_raw_text():
    _, trajectory, _, _, _ = _chain()
    replay = make_token_trajectory(
        episode_id=trajectory.episode_id,
        function_id=trajectory.function_id,
        decision_kind=trajectory.decision_kind,
        parent_trajectory_ids=trajectory.parent_trajectory_ids,
        model_revision_sha256=trajectory.model_revision_sha256,
        function_registry_sha256=trajectory.function_registry_sha256,
        snapshot_id=trajectory.snapshot_id,
        input_sha256=trajectory.input_sha256,
        output_sha256=trajectory.output_sha256,
        input_token_count=trajectory.input_token_count,
        output_token_count=trajectory.output_token_count,
        external_action_sha256=trajectory.external_action_sha256,
        tool_receipt_sha256s=trajectory.tool_receipt_sha256s,
        used_edge_ids=reversed(trajectory.used_edge_ids),
        raw_contribution=trajectory.raw_contribution,
        pre_outcome_seal_sha256=trajectory.pre_outcome_seal_sha256,
    )

    assert replay == trajectory
    assert trajectory.activation_trace().question_id == trajectory.trajectory_id
    encoded = json.dumps(trajectory.canonical(), sort_keys=True)
    assert "raw prompt" not in encoded
    assert "raw response" not in encoded


def test_evidence_levels_do_not_call_token_storage_learning(tmp_path):
    base, trajectory, tags, outcome, candidate = _chain()

    observed = make_token_learning_receipt((trajectory,), tags, outcome=outcome)
    candidate_only = make_token_learning_receipt(
        (trajectory,), tags, outcome=outcome, candidate=candidate
    )
    with SQLiteWeightStore(tmp_path / "weights.sqlite3", initial_snapshot=base) as store:
        store.stage(candidate)
        activation = store.activate(candidate.candidate_id)
    durable = make_token_learning_receipt(
        (trajectory,),
        tags,
        outcome=outcome,
        candidate=candidate,
        activation=activation,
    )
    causal = make_token_learning_receipt(
        (trajectory,),
        tags,
        outcome=outcome,
        candidate=candidate,
        activation=activation,
        causal_evaluation_receipt_sha256=_sha("b"),
        fixed_context_replay_receipt_sha256=_sha("c"),
        matched_budget_receipt_sha256=_sha("d"),
        removal_ablation_receipt_sha256=_sha("e"),
    )

    assert observed.evidence_level == "OBSERVED_ONLY"
    assert candidate_only.evidence_level == "CANDIDATE_ONLY"
    assert durable.evidence_level == "DURABLE_UPDATE"
    assert causal.evidence_level == "CAUSALLY_VALIDATED"
    assert not observed.supports_learned_coordination_claim
    assert not candidate_only.supports_learned_coordination_claim
    assert not durable.supports_learned_coordination_claim
    assert causal.supports_learned_coordination_claim


def test_receipt_rejects_temporal_and_provenance_gaps(tmp_path):
    base, trajectory, tags, outcome, candidate = _chain()
    wrong_outcome = make_outcome_receipt(
        arm_id="A1_tagged_commit",
        episode_id="episode:other",
        reward=0.8,
        evaluator_receipt_sha256=_sha("a"),
    )
    with pytest.raises(TokenLearningContractError, match="different episode"):
        make_token_learning_receipt((trajectory,), tags, outcome=wrong_outcome)

    with SQLiteWeightStore(tmp_path / "weights.sqlite3", initial_snapshot=base) as store:
        store.stage(candidate)
        activation = store.activate(candidate.candidate_id)
    with pytest.raises(TokenLearningContractError, match="inseparable bundle"):
        make_token_learning_receipt(
            (trajectory,),
            tags,
            outcome=outcome,
            candidate=candidate,
            activation=activation,
            causal_evaluation_receipt_sha256=_sha("b"),
        )

    with pytest.raises(TokenLearningContractError, match="positive integer"):
        make_token_trajectory(
            episode_id=trajectory.episode_id,
            function_id=trajectory.function_id,
            decision_kind=trajectory.decision_kind,
            model_revision_sha256=trajectory.model_revision_sha256,
            function_registry_sha256=trajectory.function_registry_sha256,
            snapshot_id=trajectory.snapshot_id,
            input_sha256=trajectory.input_sha256,
            output_sha256=trajectory.output_sha256,
            input_token_count=0,
            output_token_count=1,
            external_action_sha256=trajectory.external_action_sha256,
            used_edge_ids=trajectory.used_edge_ids,
            raw_contribution=1.0,
            pre_outcome_seal_sha256=trajectory.pre_outcome_seal_sha256,
        )


def test_episode_receipt_requires_a_closed_orchestration_graph():
    _, trajectory, tags, outcome, _ = _chain()
    orphan = make_token_trajectory(
        episode_id=trajectory.episode_id,
        function_id="tool-runner",
        decision_kind="TOOL_USE",
        parent_trajectory_ids=(_sha("f"),),
        model_revision_sha256=trajectory.model_revision_sha256,
        function_registry_sha256=trajectory.function_registry_sha256,
        snapshot_id=trajectory.snapshot_id,
        input_sha256=_sha("b"),
        output_sha256=_sha("c"),
        input_token_count=16,
        output_token_count=4,
        external_action_sha256=_sha("d"),
        used_edge_ids=trajectory.used_edge_ids,
        raw_contribution=1.0,
        pre_outcome_seal_sha256=_sha("e"),
    )

    with pytest.raises(TokenLearningContractError, match="outside the sealed"):
        make_token_learning_receipt((orphan,), tags, outcome=outcome)
