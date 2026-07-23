from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from feedback_ports import CapabilityAuthority, CapabilityRole
from feedback_runtime import (
    EventKind,
    FeedbackRuntime,
    IdempotencyConflict,
    IntegrityError,
)
from feedback_store import SQLiteFeedbackStore


STREAM = "durable-stream"
CUT = "durable-cut"
SECRET = b"durable-feedback-secret-32-bytes"


def open_runtime(path):
    authority = CapabilityAuthority(authority_id="durable-authority", secret=SECRET)
    store = SQLiteFeedbackStore(path, initial_cut_id=CUT)
    runtime = FeedbackRuntime(
        store=store,
        authority=authority,
        stream_id=STREAM,
        initial_cut_id=CUT,
    )
    caps = {
        role: authority.mint(
            stream_id=STREAM,
            principal_id=f"durable-{role.value}",
            role=role,
        )
        for role in CapabilityRole
    }
    return runtime, store, caps


def to_judged(runtime, caps):
    runtime.submit(
        runtime.command(
            EventKind.ATTACH,
            request_id="a",
            capability=caps[CapabilityRole.PROPOSER],
            payload={"attachment_id": "a"},
        )
    )
    proposal = runtime.submit(
        runtime.command(
            EventKind.PROPOSE,
            request_id="p",
            capability=caps[CapabilityRole.PROPOSER],
            payload={"proposal_id": "p", "action": "change"},
        )
    )
    observed = runtime.submit(
        runtime.command(
            EventKind.OBSERVE,
            request_id="o",
            capability=caps[CapabilityRole.EXECUTOR],
            payload={
                "receipt_id": "o",
                "proposal_event_sha256": proposal.event_sha256,
                "observation": {"ok": True},
                "adapter_identity": "executor:durable",
            },
        )
    )
    runtime.submit(
        runtime.command(
            EventKind.JUDGE,
            request_id="j",
            capability=caps[CapabilityRole.JUDGE],
            payload={
                "judgment_receipt_id": "j",
                "proposal_event_sha256": proposal.event_sha256,
                "observation_event_sha256": observed.event_sha256,
                "verdict": "ACCEPT",
                "adapter_identity": "judge:durable",
            },
        )
    )


def test_wal_full_ordered_replay_and_restart_recovery(tmp_path):
    path = tmp_path / "restart.db"
    runtime, store, caps = open_runtime(path)
    assert store.journal_mode == "wal"
    assert store.synchronous == 2
    to_judged(runtime, caps)
    before = runtime.projection()
    store.close()

    runtime, store, caps = open_runtime(path)
    try:
        assert runtime.projection() == before
        runtime.submit(
            runtime.commit_command(
                request_id="c", capability=caps[CapabilityRole.COMMITTER]
            )
        )
        committed = runtime.projection()
    finally:
        store.close()

    runtime, store, caps = open_runtime(path)
    try:
        assert runtime.projection() == committed
        runtime.submit(
            runtime.dispatch_command(
                request_id="d", capability=caps[CapabilityRole.DISPATCHER]
            )
        )
        dispatched = runtime.projection()
    finally:
        store.close()

    runtime, store, _caps = open_runtime(path)
    try:
        assert runtime.projection() == dispatched
        assert runtime.state().phase == "dispatched"
        assert runtime.state().sequence == 6
    finally:
        store.close()


def test_byte_tamper_and_duplicated_column_tamper_are_detected(tmp_path):
    byte_path = tmp_path / "byte.db"
    runtime, store, caps = open_runtime(byte_path)
    runtime.submit(
        runtime.command(
            EventKind.ATTACH,
            request_id="a",
            capability=caps[CapabilityRole.PROPOSER],
            payload={"attachment_id": "a"},
        )
    )
    store.close()
    connection = sqlite3.connect(byte_path)
    raw = connection.execute(
        "SELECT canonical_event FROM feedback_events WHERE sequence=0"
    ).fetchone()[0]
    changed = bytearray(raw)
    changed[-2] = ord("1") if changed[-2] != ord("1") else ord("2")
    connection.execute(
        "UPDATE feedback_events SET canonical_event=? WHERE sequence=0", (bytes(changed),)
    )
    connection.commit()
    connection.close()
    _runtime, reopened, _caps = open_runtime(byte_path)
    try:
        with pytest.raises(IntegrityError):
            reopened.events(STREAM)
    finally:
        reopened.close()


def test_canonical_extra_top_level_envelope_field_is_rejected(tmp_path):
    path = tmp_path / "extra-envelope-field.db"
    runtime, store, caps = open_runtime(path)
    runtime.submit(
        runtime.command(
            EventKind.ATTACH,
            request_id="a",
            capability=caps[CapabilityRole.PROPOSER],
            payload={"attachment_id": "a"},
        )
    )
    store.close()

    connection = sqlite3.connect(path)
    raw = connection.execute(
        "SELECT canonical_event FROM feedback_events WHERE sequence=0"
    ).fetchone()[0]
    envelope = json.loads(raw.decode("utf-8"))
    envelope["undeclared_top_level_field"] = "silent-drop-attempt"
    tampered = json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    connection.execute(
        "UPDATE feedback_events SET canonical_event=? WHERE sequence=0", (tampered,)
    )
    connection.commit()
    connection.close()

    _runtime, reopened, _caps = open_runtime(path)
    try:
        with pytest.raises(IntegrityError, match="field set"):
            reopened.events(STREAM)
    finally:
        reopened.close()


def test_request_hash_tamper_and_retry_fast_path_chain_tamper_are_detected(tmp_path):
    request_path = tmp_path / "request-hash.db"
    runtime, store, caps = open_runtime(request_path)
    runtime.submit(
        runtime.command(
            EventKind.ATTACH,
            request_id="a",
            capability=caps[CapabilityRole.PROPOSER],
            payload={"attachment_id": "a"},
        )
    )
    store.close()
    connection = sqlite3.connect(request_path)
    connection.execute("UPDATE feedback_events SET request_sha256=?", ("f" * 64,))
    connection.commit()
    connection.close()
    _runtime, reopened, _caps = open_runtime(request_path)
    try:
        with pytest.raises(IntegrityError, match="request_sha256"):
            reopened.lookup_request(STREAM, "a")
    finally:
        reopened.close()

    chain_path = tmp_path / "retry-chain.db"
    runtime, store, caps = open_runtime(chain_path)
    runtime.submit(
        runtime.command(
            EventKind.ATTACH,
            request_id="a",
            capability=caps[CapabilityRole.PROPOSER],
            payload={"attachment_id": "a"},
        )
    )
    retry = runtime.command(
        EventKind.PROPOSE,
        request_id="p",
        capability=caps[CapabilityRole.PROPOSER],
        payload={"proposal_id": "p", "action": "x"},
    )
    runtime.submit(retry)
    store.close()
    connection = sqlite3.connect(chain_path)
    connection.execute(
        "UPDATE feedback_events SET principal_id='corrupt-earlier' WHERE sequence=0"
    )
    connection.commit()
    connection.close()
    runtime, reopened, _caps = open_runtime(chain_path)
    try:
        with pytest.raises(IntegrityError, match="principal_id"):
            runtime.submit(retry)
    finally:
        reopened.close()

    column_path = tmp_path / "column.db"
    runtime, store, caps = open_runtime(column_path)
    runtime.submit(
        runtime.command(
            EventKind.ATTACH,
            request_id="a",
            capability=caps[CapabilityRole.PROPOSER],
            payload={"attachment_id": "a"},
        )
    )
    store.close()
    connection = sqlite3.connect(column_path)
    connection.execute("UPDATE feedback_events SET principal_id='tampered'")
    connection.commit()
    connection.close()
    _runtime, reopened, _caps = open_runtime(column_path)
    try:
        with pytest.raises(IntegrityError, match="principal_id"):
            reopened.events(STREAM)
    finally:
        reopened.close()


def test_two_writers_same_request_insert_once(tmp_path):
    path = tmp_path / "same.db"
    runtime1, store1, caps1 = open_runtime(path)
    runtime2, store2, caps2 = open_runtime(path)
    command1 = runtime1.command(
        EventKind.ATTACH,
        request_id="shared",
        capability=caps1[CapabilityRole.PROPOSER],
        payload={"attachment_id": "a"},
    )
    command2 = runtime2.command(
        EventKind.ATTACH,
        request_id="shared",
        capability=caps2[CapabilityRole.PROPOSER],
        payload={"attachment_id": "a"},
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda item: item[0].submit(item[1]), [(runtime1, command1), (runtime2, command2)]))
        assert results[0].event_sha256 == results[1].event_sha256
        assert len(store1.events(STREAM)) == 1
    finally:
        store1.close()
        store2.close()


def test_two_writers_conflicting_intent_first_write_wins(tmp_path):
    path = tmp_path / "conflict.db"
    runtime1, store1, caps1 = open_runtime(path)
    runtime2, store2, caps2 = open_runtime(path)
    commands = [
        runtime1.command(
            EventKind.ATTACH,
            request_id="shared",
            capability=caps1[CapabilityRole.PROPOSER],
            payload={"attachment_id": "a"},
        ),
        runtime2.command(
            EventKind.ATTACH,
            request_id="shared",
            capability=caps2[CapabilityRole.PROPOSER],
            payload={"attachment_id": "b"},
        ),
    ]

    def submit(pair):
        try:
            return pair[0].submit(pair[1])
        except IdempotencyConflict as error:
            return error

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, [(runtime1, commands[0]), (runtime2, commands[1])]))
        assert sum(isinstance(result, IdempotencyConflict) for result in results) == 1
        assert len(store1.events(STREAM)) == 1
    finally:
        store1.close()
        store2.close()
