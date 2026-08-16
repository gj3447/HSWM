from __future__ import annotations

from dataclasses import replace

import pytest

from hswm.cells.runtime import (
    Accepted,
    CellContract,
    CellStepCompleted,
    CellStepRequested,
    InvokeCellEffect,
    KernelInvariantError,
    KernelState,
    RecordCellOutput,
    Rejected,
    RejectionReason,
    RequestCellStep,
    decide,
    effects,
    evolve,
    evolve_accepted,
    execute_cell_effect,
    make_packet,
    replay,
    state_digest,
)


REGISTRY = {
    "cell-a": CellContract(
        cell_id="cell-a",
        input_type="question/v1",
        output_type="answer/v1",
    )
}


def input_packet(packet_type: str = "question/v1"):
    return make_packet(
        packet_id="packet-in-1",
        packet_type=packet_type,
        payload={"question": "2+2?"},
        provenance={"source": "unit-test"},
    )


def output_packet(packet_type: str = "answer/v1"):
    return make_packet(
        packet_id="packet-out-1",
        packet_type=packet_type,
        payload={"answer": "4"},
        provenance={"cell": "cell-a", "activation": "activation-1"},
    )


def request(state: KernelState, *, activation_id: str = "activation-1"):
    return RequestCellStep(
        expected_version=state.version,
        activation_id=activation_id,
        cell_id="cell-a",
        input=input_packet(),
    )


def accepted_request(state: KernelState) -> tuple[CellStepRequested, KernelState]:
    decision = decide(REGISTRY, state, request(state))
    assert isinstance(decision, Accepted)
    assert len(decision.events) == 1
    event = decision.events[0]
    assert isinstance(event, CellStepRequested)
    return event, evolve_accepted(state, decision)


def test_happy_path_is_request_event_effect_completion() -> None:
    initial = KernelState(remaining_budget=2)
    requested, pending_state = accepted_request(initial)

    assert pending_state.version == 1
    assert pending_state.remaining_budget == 1
    assert len(pending_state.pending) == 1
    assert effects(requested) == (
        InvokeCellEffect(
            activation_id="activation-1",
            cell_id="cell-a",
            input=requested.input,
            expected_output_type="answer/v1",
        ),
    )

    completion = decide(
        REGISTRY,
        pending_state,
        RecordCellOutput(
            expected_version=pending_state.version,
            activation_id="activation-1",
            output=output_packet(),
        ),
    )
    assert isinstance(completion, Accepted)
    final = evolve_accepted(pending_state, completion)

    assert final.version == 2
    assert final.remaining_budget == 1
    assert final.pending == ()
    assert final.completed[0].activation_id == "activation-1"
    assert effects(completion.events[0]) == ()


@pytest.mark.parametrize(
    ("state", "command_factory", "reason"),
    [
        (
            KernelState(remaining_budget=0),
            lambda state: request(state),
            RejectionReason.BUDGET_EXHAUSTED,
        ),
        (
            KernelState(remaining_budget=1, version=3),
            lambda state: replace(request(state), expected_version=2),
            RejectionReason.STALE_VERSION,
        ),
        (
            KernelState(remaining_budget=1),
            lambda state: replace(request(state), cell_id="missing-cell"),
            RejectionReason.UNKNOWN_CELL,
        ),
        (
            KernelState(remaining_budget=1),
            lambda state: replace(request(state), input=input_packet("wrong/v1")),
            RejectionReason.INPUT_TYPE_MISMATCH,
        ),
    ],
)
def test_request_rejections_have_stable_reasons(
    state: KernelState, command_factory, reason: RejectionReason
) -> None:
    decision = decide(REGISTRY, state, command_factory(state))
    assert isinstance(decision, Rejected)
    assert decision.reason is reason


def test_duplicate_activation_is_rejected_after_first_event() -> None:
    initial = KernelState(remaining_budget=2)
    _, pending_state = accepted_request(initial)
    duplicate = decide(
        REGISTRY,
        pending_state,
        request(pending_state, activation_id="activation-1"),
    )
    assert isinstance(duplicate, Rejected)
    assert duplicate.reason is RejectionReason.DUPLICATE_ACTIVATION


def test_completion_requires_pending_activation_and_output_type() -> None:
    initial = KernelState(remaining_budget=1)
    missing = decide(
        REGISTRY,
        initial,
        RecordCellOutput(
            expected_version=0,
            activation_id="missing",
            output=output_packet(),
        ),
    )
    assert isinstance(missing, Rejected)
    assert missing.reason is RejectionReason.UNKNOWN_ACTIVATION

    _, pending_state = accepted_request(initial)
    mismatch = decide(
        REGISTRY,
        pending_state,
        RecordCellOutput(
            expected_version=1,
            activation_id="activation-1",
            output=output_packet("wrong/v1"),
        ),
    )
    assert isinstance(mismatch, Rejected)
    assert mismatch.reason is RejectionReason.OUTPUT_TYPE_MISMATCH


def test_replay_is_deterministic_and_has_stable_digest() -> None:
    initial = KernelState(remaining_budget=2)
    requested, pending_state = accepted_request(initial)
    completion_decision = decide(
        REGISTRY,
        pending_state,
        RecordCellOutput(
            expected_version=1,
            activation_id="activation-1",
            output=output_packet(),
        ),
    )
    assert isinstance(completion_decision, Accepted)
    history = (requested, completion_decision.events[0])

    left = replay(initial, history)
    right = replay(initial, history)
    assert left == right
    assert state_digest(left) == state_digest(right)
    assert len(state_digest(left)) == 64


class StubCellPort:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, effect: InvokeCellEffect):
        self.calls += 1
        assert effect.expected_output_type == "answer/v1"
        return output_packet()


def test_effect_adapter_is_outside_reducer_and_records_output() -> None:
    initial = KernelState(remaining_budget=1)
    requested, pending_state = accepted_request(initial)
    port = StubCellPort()

    final, completed = execute_cell_effect(
        state=pending_state,
        effect=effects(requested)[0],
        registry=REGISTRY,
        port=port,
    )

    assert port.calls == 1
    assert isinstance(completed, CellStepCompleted)
    assert final.completed[0].output_packet_id == "packet-out-1"


def test_rejection_path_never_reaches_cell_port() -> None:
    state = KernelState(remaining_budget=0)
    port = StubCellPort()
    decision = decide(REGISTRY, state, request(state))
    assert isinstance(decision, Rejected)
    assert port.calls == 0


def test_replay_rejects_out_of_order_or_uncommitted_events() -> None:
    event = CellStepCompleted(
        sequence=1,
        activation_id="missing",
        cell_id="cell-a",
        output=output_packet(),
    )
    with pytest.raises(KernelInvariantError, match="no pending activation"):
        evolve(KernelState(remaining_budget=1), event)

    requested = CellStepRequested(
        sequence=2,
        activation_id="activation-1",
        cell_id="cell-a",
        input=input_packet(),
        expected_output_type="answer/v1",
    )
    with pytest.raises(KernelInvariantError, match="does not follow"):
        evolve(KernelState(remaining_budget=1), requested)
