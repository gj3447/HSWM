from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from hswm_cellular_openai import FixtureCellPort, UnknownModelOutcome
from hswm_cellular_runtime import (
    CellContract,
    KernelState,
    Rejected,
    RequestCellStep,
    make_packet,
    state_digest,
)
from hswm_cellular_store import (
    CommandIntentConflict,
    CommitReceipt,
    OutboxStateConflict,
    OutboxStatus,
    SqliteCellRuntime,
    StoreIntegrityError,
)


REGISTRY = {
    "cell-a": CellContract(
        cell_id="cell-a",
        input_type="question/v1",
        output_type="answer/v1",
    )
}


def packet(*, text: str = "What is 2+2?", packet_id: str = "input-1"):
    return make_packet(
        packet_id=packet_id,
        packet_type="question/v1",
        payload={"prompt": text},
        provenance={"source": "durable-runtime-test"},
    )


def request(*, text: str = "What is 2+2?", expected_version: int = 0):
    return RequestCellStep(
        expected_version=expected_version,
        activation_id="activation-1",
        cell_id="cell-a",
        input=packet(text=text),
    )


def prepared_store(tmp_path, *, budget: int = 1):
    path = tmp_path / "runtime.sqlite3"
    store = SqliteCellRuntime(path, REGISTRY)
    store.create_stream("stream-1", initial_budget=budget)
    return path, store


def test_request_event_and_outbox_commit_atomically_and_recover(tmp_path) -> None:
    path, store = prepared_store(tmp_path)
    receipt = store.submit("stream-1", request())
    assert isinstance(receipt, CommitReceipt)
    assert receipt.event_sequences == (1,)
    assert len(receipt.outbox_effect_ids) == 1
    assert store.event_count("stream-1") == 1
    assert store.list_outbox(status=OutboxStatus.PENDING)[0].source_sequence == 1

    reopened = SqliteCellRuntime(path, REGISTRY)
    recovered = reopened.load_state("stream-1")
    assert recovered.version == 1
    assert recovered.remaining_budget == 0
    assert len(recovered.pending) == 1
    assert len(reopened.list_outbox(status=OutboxStatus.PENDING)) == 1


def test_exact_request_retry_is_stable_and_different_intent_conflicts(tmp_path) -> None:
    _, store = prepared_store(tmp_path)
    first = store.submit("stream-1", request())
    retry = store.submit("stream-1", request())
    assert isinstance(first, CommitReceipt)
    assert isinstance(retry, CommitReceipt)
    assert retry.exact_retry is True
    assert retry.event_sequences == first.event_sequences
    assert retry.outbox_effect_ids == first.outbox_effect_ids
    assert store.event_count("stream-1") == 1
    assert store.command_receipt_count("stream-1") == 1

    with pytest.raises(CommandIntentConflict, match="different intent"):
        store.submit("stream-1", request(text="different payload"))


def test_only_one_competing_dispatcher_claims_pending_effect(tmp_path) -> None:
    path, store = prepared_store(tmp_path)
    store.submit("stream-1", request())

    def claim(token: str):
        return SqliteCellRuntime(path, REGISTRY).claim_next(claim_token=token)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ("claim-a", "claim-b")))
    claimed = [item for item in results if item is not None]
    assert len(claimed) == 1
    assert claimed[0].status is OutboxStatus.IN_FLIGHT
    assert claimed[0].attempts == 1


def test_unknown_outcome_is_durable_and_never_auto_retried(tmp_path) -> None:
    path, store = prepared_store(tmp_path)
    receipt = store.submit("stream-1", request())
    assert isinstance(receipt, CommitReceipt)
    effect_id = receipt.outbox_effect_ids[0]
    claimed = store.claim_next(claim_token="claim-1")
    assert claimed is not None
    unknown = store.mark_unknown(
        effect_id,
        claim_token="claim-1",
        reason="timeout after request may have reached model",
    )
    assert unknown.status is OutboxStatus.UNKNOWN_OUTCOME
    assert store.claim_next(claim_token="claim-2") is None

    reopened = SqliteCellRuntime(path, REGISTRY)
    assert reopened.get_outbox(effect_id).status is OutboxStatus.UNKNOWN_OUTCOME
    assert reopened.claim_next(claim_token="claim-3") is None


def test_invalid_completion_rolls_back_event_and_outbox_together(tmp_path) -> None:
    _, store = prepared_store(tmp_path)
    request_receipt = store.submit("stream-1", request())
    assert isinstance(request_receipt, CommitReceipt)
    effect_id = request_receipt.outbox_effect_ids[0]
    store.claim_next(claim_token="claim-1")
    wrong = make_packet(
        packet_id="wrong-1",
        packet_type="wrong/v1",
        payload={"text": "4"},
        provenance={"source": "test"},
    )
    with pytest.raises(OutboxStateConflict, match="typed completion rejected"):
        store.complete_claimed(
            effect_id,
            claim_token="claim-1",
            output=wrong,
        )
    assert store.event_count("stream-1") == 1
    assert store.get_outbox(effect_id).status is OutboxStatus.IN_FLIGHT

    output = FixtureCellPort(response_text="4").invoke(
        store.get_outbox(effect_id).effect
    )
    completion = store.complete_claimed(
        effect_id,
        claim_token="claim-1",
        output=output,
    )
    assert completion.event_sequences == (2,)
    final = store.load_state("stream-1")
    assert final.version == 2
    assert final.pending == ()
    assert final.completed[0].output_packet_id == output.packet_id
    completed = store.get_outbox(effect_id)
    assert completed.status is OutboxStatus.SUCCEEDED
    assert completed.completed_sequence == 2


def test_fixture_port_completes_once_and_finished_effect_is_not_redelivered(
    tmp_path,
) -> None:
    _, store = prepared_store(tmp_path)
    store.submit("stream-1", request())
    port = FixtureCellPort(response_text="4")
    dispatch = store.dispatch_one(port=port, claim_token="claim-1")
    assert dispatch is not None
    assert dispatch.status is OutboxStatus.SUCCEEDED
    assert dispatch.port_called is True
    assert port.calls == 1
    assert store.dispatch_one(port=port, claim_token="claim-2") is None
    assert port.calls == 1


class UnknownPort:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, effect):
        self.calls += 1
        raise UnknownModelOutcome("transport timed out after send")


def test_dispatch_unknown_does_not_blindly_call_port_twice(tmp_path) -> None:
    _, store = prepared_store(tmp_path)
    store.submit("stream-1", request())
    port = UnknownPort()
    first = store.dispatch_one(port=port, claim_token="claim-1")
    assert first is not None
    assert first.status is OutboxStatus.UNKNOWN_OUTCOME
    assert port.calls == 1
    assert store.dispatch_one(port=port, claim_token="claim-2") is None
    assert port.calls == 1


def test_reconciliation_commits_typed_output_without_reinvocation(tmp_path) -> None:
    _, store = prepared_store(tmp_path)
    request_receipt = store.submit("stream-1", request())
    assert isinstance(request_receipt, CommitReceipt)
    effect_id = request_receipt.outbox_effect_ids[0]
    claimed = store.claim_next(claim_token="claim-1")
    assert claimed is not None
    store.mark_unknown(effect_id, claim_token="claim-1", reason="lost response")
    port = FixtureCellPort(response_text="reconciled")
    output = port.invoke(claimed.effect)
    assert port.calls == 1
    receipt = store.reconcile_completed(effect_id, output=output)
    assert receipt.event_sequences == (2,)
    assert store.get_outbox(effect_id).status is OutboxStatus.SUCCEEDED


def test_reopen_replay_has_stable_state_digest(tmp_path) -> None:
    path, store = prepared_store(tmp_path)
    store.submit("stream-1", request())
    port = FixtureCellPort()
    store.dispatch_one(port=port, claim_token="claim-1")
    first = store.load_state("stream-1")
    second = SqliteCellRuntime(path, REGISTRY).load_state("stream-1")
    assert first == second
    assert state_digest(first) == state_digest(second)


def test_event_tampering_is_detected_on_replay(tmp_path) -> None:
    path, store = prepared_store(tmp_path)
    store.submit("stream-1", request())
    connection = sqlite3.connect(path)
    connection.execute(
        "UPDATE events SET event_json=? WHERE stream_id=? AND sequence=1",
        (b'{"tampered":true}', "stream-1"),
    )
    connection.commit()
    connection.close()
    with pytest.raises(StoreIntegrityError, match="SHA-256 mismatch"):
        store.load_state("stream-1")


def test_budget_rejection_persists_nothing(tmp_path) -> None:
    _, store = prepared_store(tmp_path, budget=0)
    decision = store.submit("stream-1", request())
    assert isinstance(decision, Rejected)
    assert store.event_count("stream-1") == 0
    assert store.list_outbox() == ()
    assert store.load_state("stream-1") == KernelState(remaining_budget=0)
