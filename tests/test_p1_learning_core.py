from __future__ import annotations

import math

import pytest

from hswm_weight_snapshot import SlowWeightV1, make_initial_snapshot
from p1_eligibility_tag import (
    EligibilityContractError,
    derive_eligibility_tags,
    make_activation_trace,
)
from p1_m_commit import (
    P1LearningPolicyV1,
    build_commit_decision,
    expanding_baseline,
    make_outcome_receipt,
)


TOPOLOGY_SHA = "1" * 64
PROVENANCE_SHA = "2" * 64
QUERY_A_SHA = "3" * 64
QUERY_B_SHA = "4" * 64
EVALUATOR_SHA = "5" * 64


def _base():
    return make_initial_snapshot(
        (
            SlowWeightV1("edge:a", -0.5),
            SlowWeightV1("edge:b", -0.5),
            SlowWeightV1("edge:c", -0.5),
        ),
        topology_sha256=TOPOLOGY_SHA,
        provenance_root_sha256=PROVENANCE_SHA,
    )


def _tags(base):
    trace_a = make_activation_trace(
        episode_id="episode:2",
        question_id="q:a",
        query_sha256=QUERY_A_SHA,
        snapshot_id=base.snapshot_id,
        target_id="target:a",
        edge_ids=("edge:a", "edge:b"),
        raw_contribution=2.0,
    )
    trace_b = make_activation_trace(
        episode_id="episode:2",
        question_id="q:b",
        query_sha256=QUERY_B_SHA,
        snapshot_id=base.snapshot_id,
        target_id="target:b",
        edge_ids=("edge:b", "edge:c"),
        raw_contribution=1.0,
    )
    return (trace_a, trace_b), derive_eligibility_tags(
        "episode:2", (trace_a, trace_b)
    )


def test_eligibility_credit_is_deterministic_and_normalized():
    base = _base()
    traces, tags = _tags(base)

    assert [tag.edge_id for tag in tags] == ["edge:a", "edge:b", "edge:c"]
    assert [tag.tag_strength for tag in tags] == pytest.approx(
        [1 / 3, 1 / 2, 1 / 6]
    )
    assert math.fsum(tag.tag_strength for tag in tags) == pytest.approx(1.0)
    assert tags == derive_eligibility_tags("episode:2", reversed(traces))
    assert tags[1].source_trace_ids == tuple(sorted(trace.trace_id for trace in traces))


def test_eligibility_rejects_cross_episode_and_cross_snapshot_batches():
    base = _base()
    traces, _ = _tags(base)
    other = make_activation_trace(
        episode_id="episode:3",
        question_id="q:c",
        query_sha256=QUERY_A_SHA,
        snapshot_id=base.snapshot_id,
        target_id="target:c",
        edge_ids=("edge:a",),
        raw_contribution=1.0,
    )

    with pytest.raises(EligibilityContractError, match="different episode"):
        derive_eligibility_tags("episode:2", (*traces, other))


def test_expanding_baseline_has_no_episode_one_update():
    episode_one = make_outcome_receipt(
        arm_id="A1_tagged_commit",
        episode_id="episode:1",
        reward=0.4,
        evaluator_receipt_sha256=EVALUATOR_SHA,
    )
    episode_two = make_outcome_receipt(
        arm_id="A1_tagged_commit",
        episode_id="episode:2",
        reward=0.8,
        evaluator_receipt_sha256=EVALUATOR_SHA,
    )

    first = expanding_baseline(episode_one, ())
    second = expanding_baseline(episode_two, (episode_one.reward,))

    assert first.baseline is None
    assert first.modulation == 0.0
    assert second.baseline == 0.4
    assert second.modulation == pytest.approx(0.4)


def test_tagged_uniform_and_no_commit_arms_obey_budget_contract():
    base = _base()
    _, tags = _tags(base)
    policy = P1LearningPolicyV1(eta=0.05)

    outcomes = {
        arm: make_outcome_receipt(
            arm_id=arm,
            episode_id="episode:2",
            reward=0.8,
            evaluator_receipt_sha256=EVALUATOR_SHA,
        )
        for arm in ("A1_tagged_commit", "A2_no_commit", "A4_uniform_commit")
    }
    tagged = build_commit_decision(
        base, tags, outcome=outcomes["A1_tagged_commit"], modulation=0.4, policy=policy
    )
    no_commit = build_commit_decision(
        base, tags, outcome=outcomes["A2_no_commit"], modulation=0.4, policy=policy
    )
    uniform = build_commit_decision(
        base, tags, outcome=outcomes["A4_uniform_commit"], modulation=0.4, policy=policy
    )

    assert tagged.candidate is not None
    assert no_commit.candidate is None
    assert no_commit.reason == "arm_no_commit"
    assert uniform.candidate is not None
    assert tagged.actual_l1 == pytest.approx(policy.eta * 0.4)
    assert uniform.actual_l1 == pytest.approx(tagged.actual_l1)
    tagged_changes = {
        delta.edge_id: delta.after_log_salience - delta.before_log_salience
        for delta in tagged.candidate.deltas
    }
    uniform_changes = {
        delta.edge_id: delta.after_log_salience - delta.before_log_salience
        for delta in uniform.candidate.deltas
    }
    assert tagged_changes == pytest.approx(
        {"edge:a": 0.02 / 3, "edge:b": 0.01, "edge:c": 0.02 / 6}
    )
    assert len(set(round(value, 14) for value in uniform_changes.values())) == 1


def test_commit_rejects_tags_bound_to_another_base():
    base = _base()
    _, tags = _tags(base)
    advanced_base = make_initial_snapshot(
        tuple(base.weights),
        topology_sha256=base.topology_sha256,
        provenance_root_sha256="6" * 64,
    )
    outcome = make_outcome_receipt(
        arm_id="A1_tagged_commit",
        episode_id="episode:2",
        reward=0.8,
        evaluator_receipt_sha256=EVALUATOR_SHA,
    )

    with pytest.raises(ValueError, match="base snapshot"):
        build_commit_decision(advanced_base, tags, outcome=outcome, modulation=0.4)
