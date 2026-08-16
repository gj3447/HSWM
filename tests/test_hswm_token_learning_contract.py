from __future__ import annotations

import json

import pytest

from hswm.learning.token_learning_contract import (
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
        model_context_sha256=_sha("3"),
        snapshot_id=base.snapshot_id,
        input_sha256=_sha("4"),
        output_sha256=_sha("5"),
        token_count=144,
        action_sha256=_sha("6"),
        used_edge_ids=("edge:b", "edge:a"),
        pre_outcome_seal_sha256=_sha("7"),
    )
    tags = derive_eligibility_tags(
        trajectory.episode_id, (trajectory.activation_trace(),)
    )
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
        model_context_sha256=trajectory.model_context_sha256,
        snapshot_id=trajectory.snapshot_id,
        input_sha256=trajectory.input_sha256,
        output_sha256=trajectory.output_sha256,
        token_count=trajectory.token_count,
        action_sha256=trajectory.action_sha256,
        used_edge_ids=reversed(trajectory.used_edge_ids),
        pre_outcome_seal_sha256=trajectory.pre_outcome_seal_sha256,
    )

    assert replay == trajectory
    assert trajectory.activation_trace().question_id == trajectory.trajectory_id
    encoded = json.dumps(trajectory.canonical(), sort_keys=True)
    assert "raw prompt" not in encoded
    assert "raw response" not in encoded


def test_three_evidence_levels_use_one_optional_causal_receipt(tmp_path):
    base, trajectory, tags, outcome, candidate = _chain()
    observed = make_token_learning_receipt((trajectory,), tags, outcome=outcome)
    with SQLiteWeightStore(tmp_path / "weights.sqlite3", initial_snapshot=base) as store:
        store.stage(candidate)
        activation = store.activate(candidate.candidate_id)
    durable = make_token_learning_receipt(
        (trajectory,), tags, outcome=outcome, candidate=candidate, activation=activation
    )
    causal = make_token_learning_receipt(
        (trajectory,),
        tags,
        outcome=outcome,
        candidate=candidate,
        activation=activation,
        causal_test_receipt_sha256=_sha("b"),
    )

    assert observed.evidence_level == "OBSERVED_ONLY"
    assert durable.evidence_level == "DURABLE_UPDATE"
    assert causal.evidence_level == "CAUSALLY_VALIDATED"
    assert not observed.supports_learned_coordination_claim
    assert not durable.supports_learned_coordination_claim
    assert causal.supports_learned_coordination_claim


def test_candidate_only_and_causal_without_activation_are_rejected(tmp_path):
    base, trajectory, tags, outcome, candidate = _chain()
    with pytest.raises(TokenLearningContractError, match="candidate-only"):
        make_token_learning_receipt(
            (trajectory,), tags, outcome=outcome, candidate=candidate
        )
    with pytest.raises(TokenLearningContractError, match="causal evidence"):
        make_token_learning_receipt(
            (trajectory,),
            tags,
            outcome=outcome,
            causal_test_receipt_sha256=_sha("b"),
        )

    wrong_outcome = make_outcome_receipt(
        arm_id="A1_tagged_commit",
        episode_id="episode:other",
        reward=0.8,
        evaluator_receipt_sha256=_sha("a"),
    )
    with pytest.raises(TokenLearningContractError, match="different episode"):
        make_token_learning_receipt((trajectory,), tags, outcome=wrong_outcome)

    with pytest.raises(TokenLearningContractError, match="positive integer"):
        make_token_trajectory(
            episode_id=trajectory.episode_id,
            function_id=trajectory.function_id,
            decision_kind=trajectory.decision_kind,
            model_context_sha256=trajectory.model_context_sha256,
            snapshot_id=trajectory.snapshot_id,
            input_sha256=trajectory.input_sha256,
            output_sha256=trajectory.output_sha256,
            token_count=0,
            action_sha256=trajectory.action_sha256,
            used_edge_ids=trajectory.used_edge_ids,
            pre_outcome_seal_sha256=trajectory.pre_outcome_seal_sha256,
        )


def test_episode_receipt_requires_a_closed_orchestration_graph():
    _, trajectory, tags, outcome, _ = _chain()
    orphan = make_token_trajectory(
        episode_id=trajectory.episode_id,
        function_id="tool-runner",
        decision_kind="TOOL_USE",
        parent_trajectory_ids=(_sha("f"),),
        model_context_sha256=trajectory.model_context_sha256,
        snapshot_id=trajectory.snapshot_id,
        input_sha256=_sha("b"),
        output_sha256=_sha("c"),
        token_count=20,
        action_sha256=_sha("d"),
        used_edge_ids=trajectory.used_edge_ids,
        pre_outcome_seal_sha256=_sha("e"),
    )

    with pytest.raises(TokenLearningContractError, match="outside the sealed"):
        make_token_learning_receipt((orphan,), tags, outcome=outcome)
