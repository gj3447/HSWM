from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from urllib import request as urllib_request

import pytest

import prom_search_hswm.prom9_f1_r8_transport_audit as transport_audit
from prom_search_hswm.hswm_f1_durable_transport import DurableSpoolJSONPort
from prom_search_hswm.hswm_function_network import (
    CallEnvelopeV1,
    EvidenceCandidateV1,
    FunctionNetworkItemV1,
    TYPED_ARM,
    run_item,
)
from prom_search_hswm.hswm_function_registry import build_registry
from prom_search_hswm.hswm_result_spool import (
    RawHTTPResponse,
    SQLiteResultSpool,
)
from prom_search_hswm.hswm_token_meter import FakeMeter
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.prom9_f1_r8_runner import initialize_transport_pair
from prom_search_hswm.prom9_f1_r8_transport_audit import (
    GENESIS_SCHEMA,
    RESUME_PREFIX_SCHEMA,
    TRANSPORT_BINDINGS_SCHEMA,
    TransportAuditRefusal,
    export_genesis,
    export_resume_prefix,
    export_terminal_bindings,
    main,
)
from prom_search_hswm.prom9_protocol import DEFAULT_PROTOCOL


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "f1-r8-transport-audit-test"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _model_body(request: urllib_request.Request, meter: FakeMeter) -> bytes:
    request_value = json.loads(bytes(request.data or b"").decode("utf-8"))
    payload = json.loads(request_value["messages"][1]["content"])
    request_id = payload["request_id"]
    if "query_text" in payload and "budget" in payload:
        output = {
            "request_id": request_id,
            "objectives": ["answer"],
            "required_evidence_types": ["text"],
            "constraints": ["use supplied evidence"],
            "abstain": False,
        }
    elif "candidate_table" in payload:
        table = payload["candidate_table"]
        row = table["rows"][0]
        bond_id = row[table["columns"].index("bond_id")]
        evidence_id = row[table["columns"].index("evidence_id")]
        output = {
            "request_id": request_id,
            "ordered_bond_ids": [bond_id],
            "bond_potentials": {bond_id: 0.0},
            "evidence_refs": [evidence_id],
            "abstain": False,
        }
    else:
        evidence = payload["selected_evidence"]
        output = {
            "request_id": request_id,
            "answer": "Paris",
            "supporting_evidence_ids": [value["evidence_id"] for value in evidence],
            "uncertainty": "low",
            "abstain": not bool(evidence),
        }
    body = {
        "model": request_value["model"],
        "usage": {
            "prompt_tokens": meter.count_chat_prompt(
                request_value["messages"][0]["content"],
                request_value["messages"][1]["content"],
            ),
            "completion_tokens": 1,
        },
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": canonical_json(output)},
            }
        ],
    }
    return canonical_json(body).encode("utf-8")


class _SpoolBackedTransport:
    def __init__(self, spool: SQLiteResultSpool, meter: FakeMeter) -> None:
        self.spool = spool
        self.meter = meter
        self.calls = 0

    def __call__(
        self, request: urllib_request.Request, _timeout: float
    ) -> RawHTTPResponse:
        self.calls += 1
        physical_call_id = request.full_url.rsplit("/", 1)[-1]
        intent_sha256 = str(request.get_header("X-hswm-intent-sha256"))
        request_bytes = bytes(request.data or b"")

        def upstream(_body: bytes) -> RawHTTPResponse:
            response_body = _model_body(request, self.meter)
            return RawHTTPResponse(
                status=200,
                headers={
                    "content-type": "application/json",
                    "content-length": str(len(response_body)),
                },
                body=response_body,
            )

        result = self.spool.execute(
            physical_call_id=physical_call_id,
            intent_sha256=intent_sha256,
            request_bytes=request_bytes,
            upstream=upstream,
        )
        headers = {
            **result.headers,
            "content-length": str(len(result.body)),
            "x-hswm-spool-call-id": result.physical_call_id,
            "x-hswm-spool-intent-sha256": result.intent_sha256,
            "x-hswm-spool-request-sha256": result.request_sha256,
            "x-hswm-spool-response-sha256": result.body_sha256,
            "x-hswm-spool-replayed": "true" if result.replayed else "false",
            "x-hswm-spool-server-revision": str(
                request.get_header("X-hswm-model-revision")
            ),
        }
        return RawHTTPResponse(status=result.status, headers=headers, body=result.body)


class _PrefixStop(BaseException):
    pass


class _StopAfterAcceptedReceipts:
    def __init__(self, delegate: DurableSpoolJSONPort, limit: int) -> None:
        self.delegate = delegate
        self.limit = limit
        self.accepted = 0

    def __call__(self, call):
        return self.delegate(call)

    def accept_call_receipt(self, receipt) -> None:
        self.delegate.accept_call_receipt(receipt)
        self.accepted += 1
        if self.accepted == self.limit:
            raise _PrefixStop

    def accept_item_run(self, value) -> None:
        self.delegate.accept_item_run(value)


def _run_test_item(
    *,
    item_id: str,
    port,
    meter: FakeMeter,
) -> None:
    registry = build_registry(
        REPO_ROOT / DEFAULT_PROTOCOL,
        model="fixed-model",
        model_revision="fixed-revision",
    )
    item = FunctionNetworkItemV1(
        item_id=item_id,
        query_text="What is the capital of France?",
        allowed_evidence_types=("text",),
        candidates=(
            EvidenceCandidateV1(
                bond_id="bond-1",
                evidence_id="evidence-1",
                source_entity_id="e" * 64,
                content="Paris is the capital of France.",
                observable={
                    "flat_position": 0,
                    "flat_score": 1.0,
                    "vector_score": 1.0,
                    "source_type": "text",
                },
            ),
        ),
        max_evidence_items=1,
        max_input_tokens=12_000,
        max_output_tokens_per_call=256,
        component_id="c" * 64,
    )
    run_item(
        run_id=RUN_ID,
        arm_id=TYPED_ARM,
        item=item,
        registry=registry,
        model_port=port,
        envelope=CallEnvelopeV1(
            input_caps=(4_000, 4_000, 4_000),
            output_caps=(256, 256, 256),
            filler_field="parity_filler",
            filler_unit="0000",
            max_filler_chars=10_000,
            meter=meter,
        ),
    )


def _populate_terminal_pair(
    tmp_path: Path,
) -> tuple[Path, Path, dict[str, object], dict[str, object], dict[str, object]]:
    attempt_db = tmp_path / "attempt.sqlite3"
    spool_db = tmp_path / "spool.sqlite3"
    initialize_transport_pair(attempt_db, spool_db)
    genesis = export_genesis(
        run_id=RUN_ID, attempt_db=attempt_db, spool_db=spool_db
    )

    meter = FakeMeter()
    spool = SQLiteResultSpool(spool_db)
    port = DurableSpoolJSONPort(
        "http://127.0.0.1:8011",
        attempt_db,
        transport=_SpoolBackedTransport(spool, meter),
        delivery_backoff_s=(0.0,),
    )
    try:
        _run_test_item(item_id="item-1", port=port, meter=meter)
        live_audit = port.audit()
        spool_audit = spool.audit()
    finally:
        port.close()
        spool.close()
    return attempt_db, spool_db, genesis, live_audit, spool_audit


def _populate_partial_pair(
    tmp_path: Path,
    *,
    item_id: str = "item-1",
    accepted_calls: int,
) -> tuple[Path, Path, dict[str, object]]:
    attempt_db = tmp_path / "attempt.sqlite3"
    spool_db = tmp_path / "spool.sqlite3"
    initialize_transport_pair(attempt_db, spool_db)
    genesis = export_genesis(
        run_id=RUN_ID, attempt_db=attempt_db, spool_db=spool_db
    )
    meter = FakeMeter()
    spool = SQLiteResultSpool(spool_db)
    durable_port = DurableSpoolJSONPort(
        "http://127.0.0.1:8011",
        attempt_db,
        transport=_SpoolBackedTransport(spool, meter),
        delivery_backoff_s=(0.0,),
    )
    stopping_port = _StopAfterAcceptedReceipts(durable_port, accepted_calls)
    try:
        with pytest.raises(_PrefixStop):
            _run_test_item(item_id=item_id, port=stopping_port, meter=meter)
    finally:
        durable_port.close()
        spool.close()
    return attempt_db, spool_db, genesis


def _terminal(
    attempt_db: Path,
    spool_db: Path,
    genesis: dict[str, object],
) -> dict[str, object]:
    return export_terminal_bindings(
        run_id=RUN_ID,
        genesis_receipt=genesis,
        attempt_db=attempt_db,
        spool_db=spool_db,
        expected_calls=3,
        expected_item_runs=1,
        expected_attempt_events=18,
    )


def test_empty_genesis_is_read_only_exact_and_deterministic(tmp_path: Path) -> None:
    attempt_db = tmp_path / "empty-attempt.sqlite3"
    spool_db = tmp_path / "empty-spool.sqlite3"
    initialize_transport_pair(attempt_db, spool_db)
    before = {
        path: (_sha256_file(path), path.stat().st_mtime_ns)
        for path in (attempt_db, spool_db)
    }
    first = export_genesis(run_id=RUN_ID, attempt_db=attempt_db, spool_db=spool_db)
    second = export_genesis(run_id=RUN_ID, attempt_db=attempt_db, spool_db=spool_db)
    assert first == second
    assert first["schema_version"] == GENESIS_SCHEMA
    assert first["attempt_integrity"] == first["spool_integrity"] == "ok"
    assert first["attempt_journal_mode"] == first["spool_journal_mode"] == "wal"
    assert first["attempt_audit_connection_synchronous"] == "2"
    assert first["spool_audit_connection_synchronous"] == "2"
    assert first["attempt_user_version"] == first["spool_user_version"] == 1
    assert all(
        first[field] == 0
        for field in (
            "call_count",
            "item_run_count",
            "attempt_event_count",
            "spool_call_count",
        )
    )
    unsigned = dict(first)
    declared = unsigned.pop("genesis_sha256")
    assert declared == canonical_sha256(unsigned)
    assert before == {
        path: (_sha256_file(path), path.stat().st_mtime_ns)
        for path in (attempt_db, spool_db)
    }


@pytest.mark.parametrize("unsafe_kind", ("public_mode", "hardlink"))
def test_genesis_refuses_unsafe_sqlite_shared_memory_sidecar(
    tmp_path: Path, unsafe_kind: str
) -> None:
    attempt_db = tmp_path / "attempt.sqlite3"
    spool_db = tmp_path / "spool.sqlite3"
    initialize_transport_pair(attempt_db, spool_db)
    shared_memory = Path(f"{attempt_db}-shm")
    shared_memory.unlink(missing_ok=True)
    if unsafe_kind == "public_mode":
        shared_memory.write_bytes(b"unsafe-shm")
        shared_memory.chmod(0o644)
    else:
        backing = tmp_path / "shared-shm-backing"
        backing.write_bytes(b"unsafe-shm")
        backing.chmod(0o600)
        os.link(backing, shared_memory)

    with pytest.raises(TransportAuditRefusal, match="SHM"):
        export_genesis(run_id=RUN_ID, attempt_db=attempt_db, spool_db=spool_db)

    if unsafe_kind == "public_mode":
        assert shared_memory.stat().st_mode & 0o777 == 0o644
    else:
        assert shared_memory.stat().st_nlink == 2


def test_genesis_refuses_world_writable_nonsticky_database_parent(
    tmp_path: Path,
) -> None:
    attempt_db = tmp_path / "attempt.sqlite3"
    spool_db = tmp_path / "spool.sqlite3"
    initialize_transport_pair(attempt_db, spool_db)
    tmp_path.chmod(0o777)
    try:
        with pytest.raises(TransportAuditRefusal, match="ancestry"):
            export_genesis(
                run_id=RUN_ID, attempt_db=attempt_db, spool_db=spool_db
            )
    finally:
        tmp_path.chmod(0o700)


def test_zero_resume_prefix_is_read_only_exact_and_deterministic(
    tmp_path: Path,
) -> None:
    attempt_db = tmp_path / "empty-attempt.sqlite3"
    spool_db = tmp_path / "empty-spool.sqlite3"
    initialize_transport_pair(attempt_db, spool_db)
    genesis = export_genesis(
        run_id=RUN_ID, attempt_db=attempt_db, spool_db=spool_db
    )
    before = {
        path: (_sha256_file(path), path.stat().st_mtime_ns)
        for path in (attempt_db, spool_db)
    }
    arguments = {
        "run_id": RUN_ID,
        "genesis_receipt": genesis,
        "attempt_db": attempt_db,
        "spool_db": spool_db,
        "ordered_jobs": [("item-1", TYPED_ARM)],
        "max_workers": 1,
    }
    first = export_resume_prefix(**arguments)
    second = export_resume_prefix(**arguments)
    assert first == second
    assert first["schema_version"] == RESUME_PREFIX_SCHEMA
    assert first["zero_count_genesis"] is True
    assert first["frontier_batch"] == -1
    assert first["call_positions"] == []
    assert first["call_count"] == first["spool_call_count"] == 0
    assert first["item_run_count"] == first["attempt_event_count"] == 0
    assert first["attempt_live_audit"]["status_counts"] == {}
    assert first["spool_live_audit"]["status_counts"] == {}
    unsigned = dict(first)
    declared = unsigned.pop("resume_prefix_sha256")
    assert declared == canonical_sha256(unsigned)
    assert before == {
        path: (_sha256_file(path), path.stat().st_mtime_ns)
        for path in (attempt_db, spool_db)
    }


@pytest.mark.parametrize("accepted_calls", (1, 2, 3))
def test_resume_prefix_accepts_only_contiguous_call_prefixes(
    tmp_path: Path,
    accepted_calls: int,
) -> None:
    attempt_db, spool_db, genesis = _populate_partial_pair(
        tmp_path, accepted_calls=accepted_calls
    )
    receipt = export_resume_prefix(
        run_id=RUN_ID,
        genesis_receipt=genesis,
        attempt_db=attempt_db,
        spool_db=spool_db,
        ordered_jobs=[("item-1", TYPED_ARM)],
        max_workers=1,
    )
    assert receipt["zero_count_genesis"] is False
    assert receipt["frontier_batch"] == 0
    assert receipt["call_count"] == receipt["spool_call_count"] == accepted_calls
    assert receipt["item_run_count"] == 0
    assert receipt["attempt_event_count"] == accepted_calls * 6
    assert receipt["call_positions"] == [
        {
            "job_ordinal": 0,
            "item_id": "item-1",
            "arm_id": TYPED_ARM,
            "call_indices": list(range(1, accepted_calls + 1)),
            "item_run_committed": False,
        }
    ]


@pytest.mark.parametrize("accepted_calls", (1, 2, 3))
def test_durable_resume_replays_prefix_and_calls_only_missing_suffix(
    tmp_path: Path,
    accepted_calls: int,
) -> None:
    attempt_db, spool_db, genesis = _populate_partial_pair(
        tmp_path, accepted_calls=accepted_calls
    )
    meter = FakeMeter()
    spool = SQLiteResultSpool(spool_db)
    transport = _SpoolBackedTransport(spool, meter)
    port = DurableSpoolJSONPort(
        "http://127.0.0.1:8011",
        attempt_db,
        transport=transport,
        delivery_backoff_s=(0.0,),
    )
    try:
        _run_test_item(item_id="item-1", port=port, meter=meter)
        assert transport.calls == 3 - accepted_calls
    finally:
        port.close()
        spool.close()
    receipt = export_resume_prefix(
        run_id=RUN_ID,
        genesis_receipt=genesis,
        attempt_db=attempt_db,
        spool_db=spool_db,
        ordered_jobs=[("item-1", TYPED_ARM)],
        max_workers=1,
    )
    assert receipt["call_count"] == 3
    assert receipt["item_run_count"] == 1
    assert receipt["call_positions"][0]["item_run_committed"] is True


def test_full_resume_prefix_matches_live_audits_without_mutation(
    tmp_path: Path,
) -> None:
    attempt_db, spool_db, genesis, live_audit, spool_audit = _populate_terminal_pair(
        tmp_path
    )
    before = {
        path: (_sha256_file(path), path.stat().st_mtime_ns)
        for path in (attempt_db, spool_db)
    }
    receipt = export_resume_prefix(
        run_id=RUN_ID,
        genesis_receipt=genesis,
        attempt_db=attempt_db,
        spool_db=spool_db,
        ordered_jobs=[("item-1", TYPED_ARM)],
        max_workers=1,
    )
    assert receipt["call_count"] == receipt["spool_call_count"] == 3
    assert receipt["item_run_count"] == 1
    assert receipt["attempt_event_count"] == 18
    assert receipt["attempt_live_audit"] == live_audit
    assert receipt["spool_live_audit"] == spool_audit
    assert receipt["call_positions"][0]["item_run_committed"] is True
    assert before == {
        path: (_sha256_file(path), path.stat().st_mtime_ns)
        for path in (attempt_db, spool_db)
    }


def test_resume_prefix_refuses_foreign_job_and_scheduler_gap(tmp_path: Path) -> None:
    attempt_db, spool_db, genesis = _populate_partial_pair(
        tmp_path, item_id="item-2", accepted_calls=1
    )
    with pytest.raises(TransportAuditRefusal, match="foreign call identity"):
        export_resume_prefix(
            run_id=RUN_ID,
            genesis_receipt=genesis,
            attempt_db=attempt_db,
            spool_db=spool_db,
            ordered_jobs=[("item-1", TYPED_ARM)],
            max_workers=1,
        )
    with pytest.raises(TransportAuditRefusal, match="scheduler batch order"):
        export_resume_prefix(
            run_id=RUN_ID,
            genesis_receipt=genesis,
            attempt_db=attempt_db,
            spool_db=spool_db,
            ordered_jobs=[("item-1", TYPED_ARM), ("item-2", TYPED_ARM)],
            max_workers=1,
        )


@pytest.mark.parametrize(
    ("database", "statement", "message"),
    (
        (
            "attempt",
            "UPDATE call_state SET status='SCHEMA_VALID' WHERE physical_call_id="
            "(SELECT physical_call_id FROM call_state LIMIT 1)",
            "non-ACCEPTED",
        ),
        (
            "spool",
            "UPDATE spool_calls SET status='UNKNOWN', error_class='TEST_UNKNOWN' "
            "WHERE physical_call_id=(SELECT physical_call_id FROM spool_calls LIMIT 1)",
            "UNKNOWN|incomplete",
        ),
        (
            "attempt",
            "UPDATE attempt_events SET previous_event_sha256='ffffffffffffffffffffffffffffffff"
            "ffffffffffffffffffffffffffffffff' WHERE sequence=1",
            "event chain",
        ),
    ),
)
def test_resume_prefix_refuses_dirty_or_ambiguous_histories(
    tmp_path: Path,
    database: str,
    statement: str,
    message: str,
) -> None:
    attempt_db, spool_db, genesis, _live, _spool = _populate_terminal_pair(tmp_path)
    target = attempt_db if database == "attempt" else spool_db
    connection = sqlite3.connect(target)
    connection.execute(statement)
    connection.commit()
    connection.close()
    with pytest.raises(TransportAuditRefusal, match=message):
        export_resume_prefix(
            run_id=RUN_ID,
            genesis_receipt=genesis,
            attempt_db=attempt_db,
            spool_db=spool_db,
            ordered_jobs=[("item-1", TYPED_ARM)],
            max_workers=1,
        )


def test_resume_refuses_same_inode_wal_change_during_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempt_db, spool_db, genesis, _live, _spool = _populate_terminal_pair(tmp_path)
    original = transport_audit._database_identity
    calls = {"count": 0}

    def mutate_before_post_identity(path: Path, label: str):
        calls["count"] += 1
        if calls["count"] == 3:
            connection = sqlite3.connect(attempt_db)
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE call_state SET status='SCHEMA_VALID' "
                "WHERE physical_call_id=(SELECT physical_call_id "
                "FROM call_state LIMIT 1)"
            )
            connection.commit()
            connection.close()
        return original(path, label)

    monkeypatch.setattr(
        transport_audit, "_database_identity", mutate_before_post_identity
    )
    with pytest.raises(TransportAuditRefusal, match="generation changed"):
        export_resume_prefix(
            run_id=RUN_ID,
            genesis_receipt=genesis,
            attempt_db=attempt_db,
            spool_db=spool_db,
            ordered_jobs=[("item-1", TYPED_ARM)],
            max_workers=1,
        )


def test_resume_refuses_executable_schema_drift(tmp_path: Path) -> None:
    attempt_db = tmp_path / "attempt.sqlite3"
    spool_db = tmp_path / "spool.sqlite3"
    initialize_transport_pair(attempt_db, spool_db)
    genesis = export_genesis(
        run_id=RUN_ID, attempt_db=attempt_db, spool_db=spool_db
    )
    connection = sqlite3.connect(attempt_db)
    connection.execute(
        "CREATE TRIGGER reject_item_run BEFORE INSERT ON item_runs "
        "BEGIN SELECT RAISE(ABORT, 'blocked'); END"
    )
    connection.commit()
    connection.close()
    with pytest.raises(TransportAuditRefusal, match="schema|executable"):
        export_resume_prefix(
            run_id=RUN_ID,
            genesis_receipt=genesis,
            attempt_db=attempt_db,
            spool_db=spool_db,
            ordered_jobs=[("item-1", TYPED_ARM)],
            max_workers=1,
        )


@pytest.mark.parametrize(
    ("statement", "database"),
    [
        (
            "CREATE TRIGGER reject_item_run BEFORE INSERT ON item_runs "
            "BEGIN SELECT RAISE(ABORT, 'blocked'); END",
            "attempt",
        ),
        ("CREATE VIEW call_ids AS SELECT physical_call_id FROM call_state", "attempt"),
        ("CREATE INDEX spool_status_index ON spool_calls(status)", "spool"),
    ],
)
def test_genesis_refuses_preexisting_executable_or_explicit_schema(
    tmp_path: Path, statement: str, database: str
) -> None:
    attempt_db = tmp_path / "attempt.sqlite3"
    spool_db = tmp_path / "spool.sqlite3"
    initialize_transport_pair(attempt_db, spool_db)
    target = attempt_db if database == "attempt" else spool_db
    connection = sqlite3.connect(target)
    connection.execute(statement)
    connection.commit()
    connection.close()
    with pytest.raises(
        TransportAuditRefusal,
        match="executable or explicit schema objects",
    ):
        export_genesis(
            run_id=RUN_ID,
            attempt_db=attempt_db,
            spool_db=spool_db,
        )


def test_genesis_refuses_same_columns_with_weakened_constraints(
    tmp_path: Path,
) -> None:
    attempt_db = tmp_path / "attempt.sqlite3"
    spool_db = tmp_path / "spool.sqlite3"
    initialize_transport_pair(attempt_db, spool_db)
    connection = sqlite3.connect(spool_db)
    connection.execute("DROP TABLE spool_calls")
    connection.execute(
        """
        CREATE TABLE spool_calls (
            physical_call_id TEXT PRIMARY KEY,
            intent_sha256 TEXT NOT NULL,
            request_sha256 TEXT NOT NULL,
            request_bytes BLOB NOT NULL,
            status TEXT NOT NULL,
            response_status INTEGER,
            response_headers BLOB,
            response_body BLOB,
            response_sha256 TEXT,
            error_class TEXT
        )
        """
    )
    connection.commit()
    connection.close()
    with pytest.raises(TransportAuditRefusal, match="canonical schema drifted"):
        export_genesis(
            run_id=RUN_ID,
            attempt_db=attempt_db,
            spool_db=spool_db,
        )


def _rechain_events(
    attempt_db: Path,
    mutate,
) -> None:
    connection = sqlite3.connect(attempt_db)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT * FROM attempt_events ORDER BY sequence"
    ).fetchall()
    previous = "0" * 64
    for row in rows:
        value = json.loads(bytes(row["event_bytes"]).decode("utf-8"))
        mutate(value)
        value["previous_event_sha256"] = previous
        raw = canonical_json(value).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        connection.execute(
            "UPDATE attempt_events SET event_bytes=?,"
            "previous_event_sha256=?,event_sha256=? WHERE sequence=?",
            (raw, previous, digest, row["sequence"]),
        )
        previous = digest
    connection.commit()
    connection.close()


def test_resume_refuses_rechained_event_detail_and_strict_type_drift(
    tmp_path: Path,
) -> None:
    detail_root = tmp_path / "detail"
    attempt_db, spool_db, genesis, _live, _spool = _populate_terminal_pair(
        detail_root
    )
    changed = {"value": False}

    def mutate_detail(value: dict[str, object]) -> None:
        if value.get("event_type") == "ACCEPTED" and not changed["value"]:
            value["detail"] = {"call_receipt_sha256": "f" * 64}
            changed["value"] = True

    _rechain_events(attempt_db, mutate_detail)
    with pytest.raises(TransportAuditRefusal, match="ACCEPTED event detail"):
        export_resume_prefix(
            run_id=RUN_ID,
            genesis_receipt=genesis,
            attempt_db=attempt_db,
            spool_db=spool_db,
            ordered_jobs=[("item-1", TYPED_ARM)],
            max_workers=1,
        )

    sequence_root = tmp_path / "sequence"
    attempt_db, spool_db, genesis, _live, _spool = _populate_terminal_pair(
        sequence_root
    )

    def mutate_sequence(value: dict[str, object]) -> None:
        if value.get("sequence") == 0:
            value["sequence"] = False

    _rechain_events(attempt_db, mutate_sequence)
    with pytest.raises(TransportAuditRefusal, match="event chain"):
        export_resume_prefix(
            run_id=RUN_ID,
            genesis_receipt=genesis,
            attempt_db=attempt_db,
            spool_db=spool_db,
            ordered_jobs=[("item-1", TYPED_ARM)],
            max_workers=1,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("call_count", False),
        ("attempt_user_version", True),
        ("attempt_audit_connection_synchronous", 2),
    ),
)
def test_resume_refuses_re_signed_genesis_type_confusion(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    attempt_db = tmp_path / "attempt.sqlite3"
    spool_db = tmp_path / "spool.sqlite3"
    initialize_transport_pair(attempt_db, spool_db)
    genesis = export_genesis(
        run_id=RUN_ID, attempt_db=attempt_db, spool_db=spool_db
    )
    forged = json.loads(json.dumps(genesis))
    forged[field] = value
    unsigned = dict(forged)
    unsigned.pop("genesis_sha256")
    forged["genesis_sha256"] = canonical_sha256(unsigned)
    with pytest.raises(TransportAuditRefusal, match="empty WAL"):
        export_resume_prefix(
            run_id=RUN_ID,
            genesis_receipt=forged,
            attempt_db=attempt_db,
            spool_db=spool_db,
            ordered_jobs=[("item-1", TYPED_ARM)],
            max_workers=1,
        )


def test_terminal_export_binds_all_preimages_and_existing_audit_roots(
    tmp_path: Path,
) -> None:
    attempt_db, spool_db, genesis, live_audit, spool_audit = _populate_terminal_pair(
        tmp_path
    )
    before = (_sha256_file(attempt_db), _sha256_file(spool_db))
    first = _terminal(attempt_db, spool_db, genesis)
    second = _terminal(attempt_db, spool_db, genesis)
    assert first == second
    assert before == (_sha256_file(attempt_db), _sha256_file(spool_db))
    assert first["schema_version"] == TRANSPORT_BINDINGS_SCHEMA
    assert first["call_count"] == first["spool_call_count"] == 3
    assert first["item_run_count"] == 1
    assert first["attempt_event_count"] == 18
    assert first["spool_unknown_count"] == first["identity_conflict_count"] == 0
    assert first["accepted_call_root_sha256"] == live_audit[
        "accepted_call_root_sha256"
    ]
    assert first["spool_binding_root_sha256"] == live_audit[
        "spool_binding_root_sha256"
    ]
    assert first["item_run_root_sha256"] == live_audit["item_run_root_sha256"]
    assert first["spool_binding_root_sha256"] == spool_audit[
        "completed_root_sha256"
    ]
    assert first["event_chain_tip_sha256"] == live_audit[
        "event_chain_tip_sha256"
    ]

    accepted_keys = {
        "physical_call_id",
        "intent_sha256",
        "request_sha256",
        "response_sha256",
        "model_response_sha256",
        "call_receipt_sha256",
        "response_status",
        "intent_bytes_b64",
        "request_bytes_b64",
        "response_body_b64",
        "model_response_bytes_b64",
    }
    for call in first["accepted_calls"]:
        assert set(call) == accepted_keys
        for digest, preimage in (
            ("intent_sha256", "intent_bytes_b64"),
            ("request_sha256", "request_bytes_b64"),
            ("response_sha256", "response_body_b64"),
            ("model_response_sha256", "model_response_bytes_b64"),
        ):
            assert hashlib.sha256(
                base64.b64decode(call[preimage], validate=True)
            ).hexdigest() == call[digest]
    for event in first["attempt_events"]:
        raw = base64.b64decode(event["event_bytes_b64"], validate=True)
        assert hashlib.sha256(raw).hexdigest() == event["event_sha256"]
    item_preimage = first["item_run_preimages"][0]
    item_raw = base64.b64decode(item_preimage["item_run_bytes_b64"], validate=True)
    assert hashlib.sha256(item_raw).hexdigest() == item_preimage[
        "item_run_bytes_sha256"
    ]
    unsigned = dict(first)
    declared = unsigned.pop("bindings_sha256")
    assert declared == canonical_sha256(unsigned)


def test_terminal_refuses_unknown_and_cross_database_identity_conflict(
    tmp_path: Path,
) -> None:
    attempt_db, spool_db, genesis, _live, _spool = _populate_terminal_pair(tmp_path)
    connection = sqlite3.connect(spool_db)
    connection.execute(
        "UPDATE spool_calls SET status='UNKNOWN', error_class='TEST_UNKNOWN' "
        "WHERE physical_call_id=(SELECT physical_call_id FROM spool_calls LIMIT 1)"
    )
    connection.commit()
    connection.close()
    with pytest.raises(TransportAuditRefusal, match="UNKNOWN|incomplete"):
        _terminal(attempt_db, spool_db, genesis)

    connection = sqlite3.connect(spool_db)
    connection.execute(
        "UPDATE spool_calls SET status='COMPLETE', error_class=NULL, intent_sha256=? "
        "WHERE physical_call_id=(SELECT physical_call_id FROM spool_calls LIMIT 1)",
        ("f" * 64,),
    )
    connection.commit()
    connection.close()
    with pytest.raises(TransportAuditRefusal, match="conflict"):
        _terminal(attempt_db, spool_db, genesis)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("answer", "answer differs"),
        ("token_total", "total_input_tokens differs"),
    ),
)
def test_terminal_refuses_item_run_semantic_drift_independently(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    attempt_db, spool_db, genesis, _live, _spool = _populate_terminal_pair(tmp_path)
    connection = sqlite3.connect(attempt_db)
    raw = connection.execute(
        "SELECT item_run_bytes FROM item_runs LIMIT 1"
    ).fetchone()[0]
    value = json.loads(bytes(raw).decode("utf-8"))
    if mutation == "answer":
        value["answer"]["uncertainty"] = "high"
    else:
        value["total_input_tokens"] += 1
    unsigned = dict(value)
    unsigned.pop("run_receipt_sha256")
    value["run_receipt_sha256"] = canonical_sha256(unsigned)
    mutated = canonical_json(value).encode("utf-8")
    connection.execute(
        "UPDATE item_runs SET run_receipt_sha256=?, item_run_bytes=?",
        (value["run_receipt_sha256"], mutated),
    )
    connection.commit()
    connection.close()
    with pytest.raises(TransportAuditRefusal, match=message):
        _terminal(attempt_db, spool_db, genesis)


def test_terminal_refuses_genesis_inode_schema_and_event_chain_drift(
    tmp_path: Path,
) -> None:
    attempt_db, spool_db, genesis, _live, _spool = _populate_terminal_pair(tmp_path)
    forged = json.loads(json.dumps(genesis))
    forged["attempt_db_identity"]["st_ino"] += 1
    unsigned = dict(forged)
    unsigned.pop("genesis_sha256")
    forged["genesis_sha256"] = canonical_sha256(unsigned)
    with pytest.raises(TransportAuditRefusal, match="device/inode"):
        _terminal(attempt_db, spool_db, forged)

    connection = sqlite3.connect(attempt_db)
    connection.execute("PRAGMA user_version=2")
    connection.commit()
    connection.close()
    with pytest.raises(TransportAuditRefusal, match="user_version"):
        _terminal(attempt_db, spool_db, genesis)

    connection = sqlite3.connect(attempt_db)
    connection.execute("PRAGMA user_version=1")
    connection.execute(
        "UPDATE attempt_events SET previous_event_sha256=? WHERE sequence=1",
        ("f" * 64,),
    )
    connection.commit()
    connection.close()
    with pytest.raises(TransportAuditRefusal, match="event chain"):
        _terminal(attempt_db, spool_db, genesis)


def test_genesis_cli_is_private_write_once(tmp_path: Path) -> None:
    attempt_db = tmp_path / "cli-attempt.sqlite3"
    spool_db = tmp_path / "cli-spool.sqlite3"
    output = tmp_path / "genesis.json"
    initialize_transport_pair(attempt_db, spool_db)
    arguments = [
        "genesis",
        "--run-id",
        RUN_ID,
        "--attempt-db",
        str(attempt_db),
        "--spool-db",
        str(spool_db),
        "--output",
        str(output),
    ]
    assert main(arguments) == 0
    assert os.stat(output).st_mode & 0o777 == 0o600
    assert main(arguments) == 1
