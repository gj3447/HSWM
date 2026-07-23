from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import experimental_harness as harness  # noqa: E402


def _paired() -> harness.ExperimentHarness:
    return harness.ExperimentHarness(
        {
            "cut_id": "frozen-cut-1",
            "weights": {"edge-a": 1, "edge-b": 2},
            "history": [],
        },
        ["one_field", "separate_heads"],
        experiment_id="e1-test",
        run_names={
            "one_field": "run-one-field",
            "separate_heads": "run-separate-heads",
        },
    )


def _complete_log(run: harness.ArmRun) -> tuple[dict, ...]:
    run.append_event(
        request_id="input-1",
        event_type="input",
        payload={"task_id": "selection", "split_id": "dev", "query": "q1"},
    )
    run.append_event(
        request_id="score-1",
        event_type="score",
        payload={"task_id": "selection", "split_id": "dev", "scores": [0.2, 0.8]},
    )
    next_state = run.state
    next_state["weights"]["edge-a"] = 3
    next_state["history"].append("update-1")
    run.append_event(
        request_id="update-1",
        event_type="update",
        payload={"task_id": "selection", "split_id": "dev", "loss": 1},
        state_after=next_state,
    )
    run.append_event(
        request_id="evaluation-1",
        event_type="evaluation",
        payload={"task_id": "selection", "split_id": "dev", "metric": 1},
    )
    run.append_event(
        request_id="budget-1",
        event_type="budget",
        payload={
            "usage": {
                "schema": "hswm-budget-usage-event/v1",
                "usage_event_id": "step-1",
                "arm_id": run.arm_id,
                "task_id": "selection",
                "split_id": "dev",
                "dimension": "optimizer_steps",
                "amount": 1,
                "padding": False,
            }
        },
    )
    return run.events


def _rehash(event: dict) -> dict:
    changed = copy.deepcopy(event)
    changed.pop("event_sha256", None)
    digest = harness.canonical_sha256(changed)
    changed["event_sha256"] = digest
    return changed


def test_valid_paired_arms_are_isolated_and_replay_deterministically() -> None:
    experiment = _paired()
    one = experiment.arm("one_field")
    separate = experiment.arm("separate_heads")

    assert one.state == separate.state
    assert one.state is not separate.state
    leaked = one.state
    leaked["weights"]["edge-a"] = 999
    assert one.state["weights"]["edge-a"] == 1
    assert separate.state["weights"]["edge-a"] == 1

    events = _complete_log(one)
    assert separate.state["weights"]["edge-a"] == 1
    first = one.replay(events)
    second = one.replay(copy.deepcopy(events))

    assert first.terminal_state == one.state
    assert first.terminal_state_sha256 == one.state_sha256
    assert first.replay_sha256 == second.replay_sha256
    assert first.event_count == 5
    assert {event["event_type"] for event in events} == harness.EVENT_TYPES


def test_same_request_is_exact_retry_but_different_intent_is_conflict() -> None:
    run = _paired().arm("one_field")
    first = run.append_event(
        request_id="request-1",
        event_type="input",
        payload={"task_id": "t", "split_id": "s", "value": 1},
    )
    retry = run.append_event(
        request_id="request-1",
        event_type="input",
        payload={"task_id": "t", "split_id": "s", "value": 1},
    )
    assert retry == first
    assert len(run.events) == 1

    with pytest.raises(harness.HarnessViolation) as caught:
        run.append_event(
            request_id="request-1",
            event_type="input",
            payload={"task_id": "t", "split_id": "s", "value": 2},
        )
    assert caught.value.code == "REQUEST_ID_CONFLICT"
    assert len(run.events) == 1


@pytest.mark.parametrize("mutation", ["tamper", "reorder", "missing"])
def test_tampered_reordered_and_missing_events_fail_closed(mutation: str) -> None:
    run = _paired().arm("one_field")
    events = list(_complete_log(run))
    if mutation == "tamper":
        events[1]["payload"]["scores"][0] = 99
        expected = {"EVENT_INTENT_MISMATCH", "EVENT_HASH_MISMATCH"}
    elif mutation == "reorder":
        events[1], events[2] = events[2], events[1]
        expected = {"EVENT_SEQUENCE_MISMATCH"}
    else:
        del events[0]
        expected = {"EVENT_SEQUENCE_MISMATCH"}

    with pytest.raises(harness.HarnessViolation) as caught:
        run.replay(events)
    assert caught.value.code in expected


def test_cross_arm_event_parent_and_state_references_are_rejected() -> None:
    experiment = _paired()
    one = experiment.arm("one_field")
    separate = experiment.arm("separate_heads")
    one_event = one.append_event(
        request_id="one-input",
        event_type="input",
        payload={"task_id": "t", "split_id": "s"},
    )
    separate_event = separate.append_event(
        request_id="separate-input",
        event_type="input",
        payload={"task_id": "t", "split_id": "s"},
    )

    with pytest.raises(harness.HarnessViolation) as caught:
        separate.replay([one_event])
    assert caught.value.code == "CROSS_ARM_EVENT"

    wrong_parent = copy.deepcopy(separate_event)
    wrong_parent["parent_event_sha256"] = one_event["event_sha256"]
    with pytest.raises(harness.HarnessViolation) as caught:
        separate.replay([_rehash(wrong_parent)])
    assert caught.value.code == "EVENT_PARENT_MISMATCH"

    wrong_state = copy.deepcopy(separate_event)
    wrong_state["state_before"]["arm_id"] = "one_field"
    wrong_state["state_after"]["arm_id"] = "one_field"
    with pytest.raises(harness.HarnessViolation) as caught:
        separate.replay([_rehash(wrong_state)])
    assert caught.value.code == "CROSS_ARM_STATE_REFERENCE"


def test_missing_envelope_fields_and_padding_are_explicit_rejections() -> None:
    run = _paired().arm("one_field")
    event = run.append_event(
        request_id="input-1",
        event_type="input",
        payload={"task_id": "t", "split_id": "s"},
    )
    del event["parent_event_sha256"]
    with pytest.raises(harness.HarnessViolation) as caught:
        run.replay([event])
    assert caught.value.code == "EVENT_MISSING_FIELDS"

    with pytest.raises(harness.HarnessViolation) as caught:
        run.append_event(
            request_id="padding-1",
            event_type="budget",
            payload={"padding": True, "dimension": "online_model_calls", "amount": 1},
        )
    assert caught.value.code == "PADDING_EVENT_FORBIDDEN"


def test_update_requires_recorded_state_and_other_events_cannot_mutate() -> None:
    run = _paired().arm("one_field")
    with pytest.raises(harness.HarnessViolation) as caught:
        run.append_event(
            request_id="update-1", event_type="update", payload={"delta": 1}
        )
    assert caught.value.code == "UPDATE_STATE_REQUIRED"

    changed = run.state
    changed["weights"]["edge-a"] = 4
    with pytest.raises(harness.HarnessViolation) as caught:
        run.append_event(
            request_id="score-1",
            event_type="score",
            payload={"scores": [1]},
            state_after=changed,
        )
    assert caught.value.code == "NON_UPDATE_STATE_MUTATION"

    nullable = _paired().arm("one_field")
    nullable.append_event(
        request_id="update-null",
        event_type="update",
        payload={"reason": "canonical-null-state"},
        state_after=None,
    )
    assert nullable.replay().terminal_state is None


def test_replay_rejects_undeclared_envelope_extensions() -> None:
    run = _paired().arm("one_field")
    event = run.append_event(
        request_id="input-1", event_type="input", payload={"task_id": "t", "split_id": "s"}
    )
    event["equal_budget"] = True
    event = _rehash(event)
    with pytest.raises(harness.HarnessViolation) as caught:
        run.replay([event])
    assert caught.value.code == "EVENT_UNEXPECTED_FIELDS"
