#!/usr/bin/env python3
"""Execute the preregistered HSWM durable-runtime engineering fault gates."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hswm_cellular_openai import FixtureCellPort
from hswm_cellular_runtime import (
    CellContract,
    RequestCellStep,
    make_packet,
    state_digest,
)
from hswm_cellular_store import (
    CommandIntentConflict,
    CommitReceipt,
    OutboxStatus,
    SqliteCellRuntime,
)


REGISTRY = {
    "cell-a": CellContract(
        cell_id="cell-a",
        input_type="question/v1",
        output_type="answer/v1",
    )
}


def make_request(text: str = "Return four") -> RequestCellStep:
    return RequestCellStep(
        expected_version=0,
        activation_id="activation-1",
        cell_id="cell-a",
        input=make_packet(
            packet_id="input-1",
            packet_type="question/v1",
            payload={"prompt": text},
            provenance={"source": "durable-fault-probe"},
        ),
    )


def new_store(root: Path, name: str = "runtime.sqlite3") -> SqliteCellRuntime:
    store = SqliteCellRuntime(root / name, REGISTRY)
    store.create_stream("stream-1", initial_budget=1)
    return store


def run_gate(check: Callable[[Path], dict[str, Any]], root: Path) -> tuple[bool, Any]:
    try:
        detail = check(root)
        return True, detail
    except Exception as error:
        return False, {"error": f"{type(error).__name__}: {error}"}


def gate_atomic(root: Path) -> dict[str, Any]:
    store = new_store(root, "atomic.sqlite3")
    receipt = store.submit("stream-1", make_request())
    assert isinstance(receipt, CommitReceipt)
    assert store.event_count("stream-1") == 1
    outbox = store.list_outbox()
    assert len(outbox) == 1 and outbox[0].source_sequence == 1
    return {"event_count": 1, "outbox_count": 1, "effect_id": outbox[0].effect_id}


def gate_reopen(root: Path) -> dict[str, Any]:
    path = root / "reopen.sqlite3"
    store = SqliteCellRuntime(path, REGISTRY)
    store.create_stream("stream-1", initial_budget=1)
    store.submit("stream-1", make_request())
    reopened = SqliteCellRuntime(path, REGISTRY)
    state = reopened.load_state("stream-1")
    pending = reopened.list_outbox(status=OutboxStatus.PENDING)
    assert state.version == 1 and len(pending) == 1
    return {"version": state.version, "pending_outbox": len(pending)}


def gate_competing_claim(root: Path) -> dict[str, Any]:
    path = root / "claim.sqlite3"
    store = SqliteCellRuntime(path, REGISTRY)
    store.create_stream("stream-1", initial_budget=1)
    store.submit("stream-1", make_request())

    def claim(token: str):
        record = SqliteCellRuntime(path, REGISTRY).claim_next(claim_token=token)
        return record.effect_id if record else None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ("claim-a", "claim-b")))
    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    return {"claim_results": results, "winner_count": 1}


def gate_unknown(root: Path) -> dict[str, Any]:
    store = new_store(root, "unknown.sqlite3")
    receipt = store.submit("stream-1", make_request())
    assert isinstance(receipt, CommitReceipt)
    claimed = store.claim_next(claim_token="claim-1")
    assert claimed is not None
    store.mark_unknown(
        claimed.effect_id,
        claim_token="claim-1",
        reason="simulated response loss",
    )
    assert store.claim_next(claim_token="claim-2") is None
    assert store.get_outbox(claimed.effect_id).status is OutboxStatus.UNKNOWN_OUTCOME
    return {"status": "UNKNOWN_OUTCOME", "second_claim": None}


def gate_completion_atomic(root: Path) -> dict[str, Any]:
    store = new_store(root, "completion.sqlite3")
    request_receipt = store.submit("stream-1", make_request())
    assert isinstance(request_receipt, CommitReceipt)
    claimed = store.claim_next(claim_token="claim-1")
    assert claimed is not None
    output = FixtureCellPort(response_text="4").invoke(claimed.effect)
    completion = store.complete_claimed(
        claimed.effect_id,
        claim_token="claim-1",
        output=output,
    )
    state = store.load_state("stream-1")
    row = store.get_outbox(claimed.effect_id)
    assert completion.event_sequences == (2,)
    assert state.version == 2 and state.pending == ()
    assert row.status is OutboxStatus.SUCCEEDED and row.completed_sequence == 2
    return {"version": 2, "outbox_status": "SUCCEEDED", "completed_sequence": 2}


def gate_exact_retry(root: Path) -> dict[str, Any]:
    store = new_store(root, "retry.sqlite3")
    first = store.submit("stream-1", make_request())
    second = store.submit("stream-1", make_request())
    assert isinstance(first, CommitReceipt) and isinstance(second, CommitReceipt)
    assert second.exact_retry and store.event_count("stream-1") == 1
    return {"event_count": 1, "exact_retry": True}


def gate_conflict(root: Path) -> dict[str, Any]:
    store = new_store(root, "conflict.sqlite3")
    store.submit("stream-1", make_request())
    try:
        store.submit("stream-1", make_request("different intent"))
    except CommandIntentConflict:
        return {"conflict_rejected": True}
    raise AssertionError("same command key with different intent was accepted")


def gate_replay_digest(root: Path) -> dict[str, Any]:
    path = root / "digest.sqlite3"
    store = SqliteCellRuntime(path, REGISTRY)
    store.create_stream("stream-1", initial_budget=1)
    store.submit("stream-1", make_request())
    store.dispatch_one(port=FixtureCellPort(), claim_token="claim-1")
    left = state_digest(store.load_state("stream-1"))
    right = state_digest(SqliteCellRuntime(path, REGISTRY).load_state("stream-1"))
    assert left == right
    return {"state_sha256": left}


def gate_typed_port(root: Path) -> dict[str, Any]:
    store = new_store(root, "port.sqlite3")
    store.submit("stream-1", make_request())
    port = FixtureCellPort(response_text="4")
    receipt = store.dispatch_one(port=port, claim_token="claim-1")
    assert receipt is not None and receipt.status is OutboxStatus.SUCCEEDED
    assert port.calls == 1
    state = store.load_state("stream-1")
    assert len(state.completed) == 1
    return {"port_calls": 1, "completed_count": 1}


GATES: tuple[tuple[str, Callable[[Path], dict[str, Any]]], ...] = (
    ("atomic_request_event_and_outbox", gate_atomic),
    ("pending_outbox_recovers_after_reopen", gate_reopen),
    ("single_claim_under_competition", gate_competing_claim),
    ("unknown_outcome_is_not_auto_retried", gate_unknown),
    ("completion_event_and_outbox_success_are_atomic", gate_completion_atomic),
    ("exact_command_retry_adds_no_event", gate_exact_retry),
    ("same_key_different_intent_is_rejected", gate_conflict),
    ("same_history_has_stable_digest", gate_replay_digest),
    ("typed_cell_port_completes", gate_typed_port),
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hswm-durable-fault-probe-") as directory:
        root = Path(directory)
        outcomes = {name: run_gate(check, root) for name, check in GATES}
    gates = {name: passed for name, (passed, _) in outcomes.items()}
    result = {
        "schema": "hswm-cellular-durable-runtime-validation/v1",
        "preregistration_id": "hswm-cellular-durable-runtime-v2-20260726",
        "fault_gates": gates,
        "details": {name: detail for name, (_, detail) in outcomes.items()},
        "model_probe": "FIXTURE_PASS",
        "status": "PASS" if all(gates.values()) else "FAIL",
        "scientific_status": "UNJUDGED",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
