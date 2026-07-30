from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from urllib import request as urllib_request

import pytest

from prom_search_hswm.hswm_call_receipt import ModelCallV1, invoke_function
from prom_search_hswm.hswm_f1_durable_transport import (
    AmbiguousModelOutcome,
    DurableIntentConflict,
    DurableLedgerIntegrityError,
    DurableSpoolJSONPort,
    ProtocolRejected,
    SQLiteF1CallLedger,
)
from prom_search_hswm.hswm_function_registry import FunctionSpecV1
from prom_search_hswm.hswm_result_spool import (
    ModelDeploymentBinding,
    RawHTTPResponse,
    ResultSpoolError,
    ResultSpoolHTTPServer,
    ResultSpoolService,
    SQLiteResultSpool,
    SpoolIntegrityError,
)
import prom_search_hswm.hswm_result_spool as result_spool
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.prom9_protocol import DEFAULT_PROTOCOL


DEPLOYMENT_SHA256 = "d" * 64
MODEL_REVISION = "f" * 40


@pytest.mark.parametrize(
    ("constructor", "error_type", "filename"),
    (
        (SQLiteF1CallLedger, DurableLedgerIntegrityError, "attempt.sqlite3"),
        (SQLiteResultSpool, SpoolIntegrityError, "spool.sqlite3"),
    ),
)
@pytest.mark.parametrize("unsafe_kind", ("public_mode", "hardlink", "symlink"))
def test_sqlite_authorities_refuse_unsafe_existing_inodes_without_repair(
    tmp_path: Path,
    constructor,
    error_type: type[Exception],
    filename: str,
    unsafe_kind: str,
) -> None:
    path = tmp_path / filename
    backing = tmp_path / f"backing-{filename}"
    payload = b"do-not-mutate"
    if unsafe_kind == "public_mode":
        path.write_bytes(payload)
        path.chmod(0o644)
        observed = path
    else:
        backing.write_bytes(payload)
        backing.chmod(0o600)
        if unsafe_kind == "hardlink":
            os.link(backing, path)
        else:
            path.symlink_to(backing)
        observed = backing
    before_mode = observed.stat().st_mode & 0o777
    before_payload = observed.read_bytes()

    with pytest.raises(error_type):
        constructor(path)

    assert observed.read_bytes() == before_payload
    assert observed.stat().st_mode & 0o777 == before_mode
    if unsafe_kind == "public_mode":
        assert before_mode == 0o644
    elif unsafe_kind == "hardlink":
        assert observed.stat().st_nlink == 2
    else:
        assert path.is_symlink()


@pytest.mark.parametrize(
    ("constructor", "filename"),
    (
        (SQLiteF1CallLedger, "attempt.sqlite3"),
        (SQLiteResultSpool, "spool.sqlite3"),
    ),
)
def test_sqlite_authorities_create_owner_private_main_files(
    tmp_path: Path, constructor, filename: str
) -> None:
    path = tmp_path / filename
    store = constructor(path)
    try:
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.stat().st_nlink == 1
    finally:
        store.close()


@pytest.mark.parametrize(
    ("constructor", "filename"),
    (
        (SQLiteF1CallLedger, "attempt.sqlite3"),
        (SQLiteResultSpool, "spool.sqlite3"),
    ),
)
def test_sqlite_authorities_disable_implicit_checkpoints_on_fresh_and_reopen(
    tmp_path: Path, constructor, filename: str
) -> None:
    path = tmp_path / filename
    feature_available = all(
        (
            hasattr(sqlite3, "SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE"),
            hasattr(sqlite3.Connection, "setconfig"),
            hasattr(sqlite3.Connection, "getconfig"),
        )
    )
    for _ in range(2):
        store = constructor(path)
        try:
            assert store.wal_autocheckpoint == 0
            assert store.checkpoint_on_close_disabled is feature_available
        finally:
            store.close()


def _wal_frame_count(path: Path, page_size: int) -> int:
    wal_path = Path(f"{path}-wal")
    size = wal_path.stat().st_size
    assert size >= 32
    frame_size = page_size + 24
    assert (size - 32) % frame_size == 0
    return (size - 32) // frame_size


def test_result_spool_crosses_default_checkpoint_boundary_without_checkpoint(
    tmp_path: Path,
) -> None:
    path = tmp_path / "checkpoint-boundary.sqlite3"
    store = SQLiteResultSpool(path)
    main_preimage = path.read_bytes()
    page_size = int(store._connection.execute("PRAGMA page_size").fetchone()[0])
    upstream_calls = 0
    last_physical_call_id = ""

    def upstream(_request: bytes) -> RawHTTPResponse:
        nonlocal upstream_calls
        upstream_calls += 1
        return RawHTTPResponse(
            status=200,
            headers={"content-type": "application/json"},
            body=b'{"ok":true}',
        )

    try:
        for index in range(700):
            last_physical_call_id = hashlib.sha256(
                f"checkpoint-call-{index}".encode("ascii")
            ).hexdigest()
            intent_sha256 = hashlib.sha256(
                f"checkpoint-intent-{index}".encode("ascii")
            ).hexdigest()
            request_bytes = canonical_json({"index": index}).encode("utf-8")
            store.execute(
                physical_call_id=last_physical_call_id,
                intent_sha256=intent_sha256,
                request_bytes=request_bytes,
                upstream=upstream,
            )
            if _wal_frame_count(path, page_size) > 1000:
                break
        frames_before_close = _wal_frame_count(path, page_size)
        checkpoint_on_close_disabled = store.checkpoint_on_close_disabled
        assert frames_before_close > 1000
        assert path.read_bytes() == main_preimage
        assert upstream_calls == index + 1
    finally:
        store.close()

    if checkpoint_on_close_disabled:
        assert _wal_frame_count(path, page_size) == frames_before_close
        reopened = SQLiteResultSpool(path)
        try:
            replay = reopened.get(last_physical_call_id)
            assert replay.body == b'{"ok":true}'
            assert replay.replayed is True
            assert reopened.wal_autocheckpoint == 0
            assert reopened.checkpoint_on_close_disabled is True
            assert upstream_calls == index + 1
        finally:
            reopened.close()


def _sqlite_family_snapshot(path: Path) -> dict[str, tuple[bytes, int, int, int]]:
    result: dict[str, tuple[bytes, int, int, int]] = {}
    for suffix in ("", "-wal", "-shm", "-journal"):
        member = Path(f"{path}{suffix}")
        try:
            info = member.lstat()
        except FileNotFoundError:
            continue
        result[suffix] = (
            member.read_bytes(),
            info.st_mode & 0o777,
            info.st_dev,
            info.st_ino,
        )
    return result


@pytest.mark.parametrize(
    ("constructor", "error_type", "filename"),
    (
        (SQLiteF1CallLedger, DurableLedgerIntegrityError, "attempt.sqlite3"),
        (SQLiteResultSpool, SpoolIntegrityError, "spool.sqlite3"),
    ),
)
@pytest.mark.parametrize("invalid_existing", ("zero-byte", "version-2", "journal"))
def test_sqlite_authorities_refuse_unknown_existing_lifecycle_without_mutation(
    tmp_path: Path,
    constructor,
    error_type: type[Exception],
    filename: str,
    invalid_existing: str,
) -> None:
    path = tmp_path / filename
    if invalid_existing == "zero-byte":
        path.write_bytes(b"")
        path.chmod(0o600)
    else:
        store = constructor(path)
        store.close()
        if invalid_existing == "version-2":
            connection = sqlite3.connect(path)
            connection.execute("PRAGMA user_version=2")
            connection.commit()
            connection.close()
        else:
            journal = Path(f"{path}-journal")
            journal.write_bytes(b"rollback-journal-must-be-preserved")
            journal.chmod(0o600)
    before = _sqlite_family_snapshot(path)

    with pytest.raises(error_type):
        constructor(path)

    assert _sqlite_family_snapshot(path) == before


@pytest.mark.parametrize(
    ("constructor", "error_type", "filename", "table"),
    (
        (
            SQLiteF1CallLedger,
            DurableLedgerIntegrityError,
            "weak-attempt.sqlite3",
            "call_state",
        ),
        (SQLiteResultSpool, SpoolIntegrityError, "weak-spool.sqlite3", "spool_calls"),
    ),
)
def test_sqlite_authorities_refuse_weakened_check_before_mutation(
    tmp_path: Path,
    constructor,
    error_type: type[Exception],
    filename: str,
    table: str,
) -> None:
    path = tmp_path / filename
    store = constructor(path)
    store.close()
    connection = sqlite3.connect(path)
    sql = str(
        connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
    )
    weakened = re.sub(
        r"CHECK\s*\(status\s+IN\s*\([^)]*\)\)",
        "",
        sql,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert weakened != sql
    connection.execute("PRAGMA writable_schema=ON")
    connection.execute(
        "UPDATE sqlite_master SET sql=? WHERE type='table' AND name=?",
        (weakened, table),
    )
    connection.execute("PRAGMA writable_schema=OFF")
    connection.commit()
    connection.close()
    before = _sqlite_family_snapshot(path)

    with pytest.raises(error_type):
        constructor(path)

    assert _sqlite_family_snapshot(path) == before


@pytest.mark.parametrize(
    ("constructor", "error_type", "filename"),
    (
        (SQLiteF1CallLedger, DurableLedgerIntegrityError, "attempt.sqlite3"),
        (SQLiteResultSpool, SpoolIntegrityError, "spool.sqlite3"),
    ),
)
def test_sqlite_authorities_detect_parent_swap_before_mutating_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    constructor,
    error_type: type[Exception],
    filename: str,
) -> None:
    active_parent = tmp_path / "active"
    replacement_parent = tmp_path / "replacement"
    active_parent.mkdir(mode=0o700)
    replacement_parent.mkdir(mode=0o700)
    active_path = active_parent / filename
    replacement_path = replacement_parent / filename
    active = constructor(active_path)
    active.close()
    replacement = constructor(replacement_path)
    replacement.close()
    replacement_before = _sqlite_family_snapshot(replacement_path)
    original_connect = sqlite3.connect
    swapped = {"done": False}

    def swapping_connect(database, *args, **kwargs):
        if (
            not swapped["done"]
            and isinstance(database, str)
            and str(active_path) in database
        ):
            active_parent.rename(tmp_path / "old-active")
            replacement_parent.rename(active_parent)
            swapped["done"] = True
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", swapping_connect)
    with pytest.raises(error_type, match="parent identity drifted"):
        constructor(active_path)

    assert swapped["done"] is True
    assert _sqlite_family_snapshot(active_path) == replacement_before


@pytest.mark.parametrize("call_index", (True, 0, 4))
def test_invalid_call_index_is_refused_before_ledger_or_transport_mutation(
    tmp_path: Path, call_index: object
) -> None:
    transport = AttestedTransport()
    with DurableSpoolJSONPort(
        "http://spool", tmp_path / "invalid-call-index.sqlite3", transport=transport
    ) as port:
        call = ModelCallV1(
            physical_call_id="a" * 64,
            run_id="run",
            arm_id="arm",
            item_id="item",
            call_index=call_index,
            function_id="QF_QUERY_COMPILER",
            model="fixed-model",
            model_revision=MODEL_REVISION,
            system_prompt="one",
            input_type="QueryEnvelopeV1",
            input_payload=_input(),
            output_type="QueryPlanV1",
            max_output_tokens=256,
        )
        with pytest.raises(DurableLedgerIntegrityError, match="call index"):
            port(call)
        assert port.audit()["call_count"] == 0
    assert transport.calls == 0


@pytest.mark.parametrize(
    ("status", "response_status", "response_headers", "response_body", "response_sha", "error"),
    (
        ("DISPATCHING", 200, None, None, None, None),
        ("DISPATCHING", None, None, None, None, "unexpected-error"),
        ("UNKNOWN", None, None, None, None, None),
        ("UNKNOWN", 200, None, None, None, "server-restart"),
        ("COMPLETE", 200, None, b"{}", hashlib.sha256(b"{}").hexdigest(), None),
        (
            "COMPLETE",
            200,
            b"{}",
            b"{}",
            hashlib.sha256(b"{}").hexdigest(),
            "unexpected-error",
        ),
    ),
)
def test_spool_schema_refuses_inverse_state_field_combinations(
    tmp_path: Path,
    status: str,
    response_status: int | None,
    response_headers: bytes | None,
    response_body: bytes | None,
    response_sha: str | None,
    error: str | None,
) -> None:
    store = SQLiteResultSpool(tmp_path / "semantic-spool.sqlite3")
    request = b"{}"
    try:
        with pytest.raises(sqlite3.IntegrityError):
            store._connection.execute(
                """
                INSERT INTO spool_calls(
                    physical_call_id,intent_sha256,request_sha256,request_bytes,
                    status,response_status,response_headers,response_body,
                    response_sha256,error_class
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "a" * 64,
                    "b" * 64,
                    hashlib.sha256(request).hexdigest(),
                    request,
                    status,
                    response_status,
                    response_headers,
                    response_body,
                    response_sha,
                    error,
                ),
            )
        assert store.audit()["call_count"] == 0
    finally:
        store.close()


def _deployment_binding(endpoint: str) -> ModelDeploymentBinding:
    return ModelDeploymentBinding(
        upstream_endpoint=endpoint,
        deployment_receipt_sha256=DEPLOYMENT_SHA256,
        deployment_id=f"hswm:model_deployment:v2:{DEPLOYMENT_SHA256}",
        served_model="fixed-model",
        model_revision=MODEL_REVISION,
    )


def _function() -> FunctionSpecV1:
    prompt = "Compile one typed query plan."
    return FunctionSpecV1(
        function_id="QF_QUERY_COMPILER",
        model="fixed-model",
        model_revision=MODEL_REVISION,
        input_type="QueryEnvelopeV1",
        output_type="QueryPlanV1",
        prompt=prompt,
        prompt_sha256=canonical_sha256({"prompt": prompt}),
    )


def _input(request_id: str = "request-1") -> dict[str, object]:
    return {
        "request_id": request_id,
        "query_text": "What is the capital of France?",
        "allowed_evidence_types": ["text"],
        "budget": {
            "max_candidates": 1,
            "max_evidence_items": 1,
            "max_input_tokens": 4096,
            "max_output_tokens": 256,
        },
        "parity_filler": "",
    }


def _query_plan(request_id: str = "request-1") -> dict[str, object]:
    return {
        "request_id": request_id,
        "objectives": ["answer"],
        "required_evidence_types": ["text"],
        "constraints": ["use supplied evidence"],
        "abstain": False,
    }


def _openai_bytes(
    payload: dict[str, object],
    *,
    model: str = "fixed-model",
    finish_reason: str = "stop",
    content_text: str | None = None,
    outer_extra: str = "",
) -> bytes:
    content = canonical_json(payload) if content_text is None else content_text
    value = {
        "model": model,
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content},
            }
        ],
    }
    raw = canonical_json(value)
    if outer_extra:
        raw = raw[:-1] + outer_extra + "}"
    return raw.encode("utf-8")


class AttestedTransport:
    def __init__(self, body_factory=None) -> None:
        self.calls = 0
        self.body_factory = body_factory or (lambda _request: _openai_bytes(_query_plan()))

    def __call__(
        self, request: urllib_request.Request, _timeout: float
    ) -> RawHTTPResponse:
        self.calls += 1
        call_id = request.full_url.rsplit("/", 1)[-1]
        intent = request.get_header("X-hswm-intent-sha256")
        request_bytes = bytes(request.data or b"")
        body = self.body_factory(request)
        return RawHTTPResponse(
            status=200,
            headers={
                "content-type": "application/json",
                "content-length": str(len(body)),
                "x-hswm-spool-call-id": call_id,
                "x-hswm-spool-intent-sha256": str(intent),
                "x-hswm-spool-request-sha256": canonical_sha256(
                    json.loads(request_bytes.decode("utf-8"))
                ),
                "x-hswm-spool-response-sha256": __import__("hashlib").sha256(body).hexdigest(),
                "x-hswm-spool-replayed": "false",
                "x-hswm-spool-server-revision": str(
                    request.get_header("X-hswm-model-revision")
                ),
            },
            body=body,
        )


def _invoke(port: DurableSpoolJSONPort, request_id: str = "request-1"):
    return invoke_function(
        run_id="run-1",
        arm_id="arm-1",
        item_id="item-1",
        call_index=1,
        function=_function(),
        input_payload=_input(request_id),
        max_output_tokens=256,
        model_port=port,
    )


def test_success_is_fsynced_and_replayed_without_a_second_delivery(tmp_path: Path) -> None:
    transport = AttestedTransport()
    ledger = tmp_path / "calls.sqlite3"
    with DurableSpoolJSONPort(
        "http://spool",
        ledger,
        transport=transport,
        delivery_backoff_s=(0.0,),
    ) as port:
        first = _invoke(port)
        second = _invoke(port)
        audit = port.audit()
    assert first == second
    assert transport.calls == 1
    assert audit["journal_mode"] == "wal"
    assert audit["synchronous"] == 2
    assert audit["status_counts"] == {"ACCEPTED": 1}

    with DurableSpoolJSONPort(
        "http://spool",
        ledger,
        transport=lambda *_args: pytest.fail("accepted call touched transport"),
    ) as reopened:
        assert _invoke(reopened) == first


def test_same_physical_id_with_different_intent_is_rejected(tmp_path: Path) -> None:
    transport = AttestedTransport()
    port = DurableSpoolJSONPort("http://spool", tmp_path / "calls.db", transport=transport)
    call = ModelCallV1(
        physical_call_id="a" * 64,
        run_id="run",
        arm_id="arm",
        item_id="item",
        call_index=1,
        function_id="QF_QUERY_COMPILER",
        model="fixed-model",
        model_revision=MODEL_REVISION,
        system_prompt="one",
        input_type="QueryEnvelopeV1",
        input_payload=_input(),
        output_type="QueryPlanV1",
        max_output_tokens=256,
    )
    port(call)
    with pytest.raises(DurableIntentConflict):
        port(ModelCallV1(**{**call.__dict__, "system_prompt": "different"}))
    port.close()
    assert transport.calls == 1


def test_different_physical_id_cannot_reuse_a_logical_call_slot(
    tmp_path: Path,
) -> None:
    transport = AttestedTransport()
    port = DurableSpoolJSONPort(
        "http://spool", tmp_path / "logical-slot.db", transport=transport
    )
    first = ModelCallV1(
        physical_call_id="a" * 64,
        run_id="run",
        arm_id="arm",
        item_id="item",
        call_index=1,
        function_id="QF_QUERY_COMPILER",
        model="fixed-model",
        model_revision=MODEL_REVISION,
        system_prompt="one",
        input_type="QueryEnvelopeV1",
        input_payload=_input(),
        output_type="QueryPlanV1",
        max_output_tokens=256,
    )
    port(first)
    before = port.audit()
    with pytest.raises(DurableIntentConflict, match="logical call slot"):
        port(ModelCallV1(**{**first.__dict__, "physical_call_id": "b" * 64}))
    after = port.audit()
    port.close()
    assert after == before
    assert transport.calls == 1


def test_existing_physical_id_refuses_a_preexisting_duplicate_logical_slot(
    tmp_path: Path,
) -> None:
    path = tmp_path / "preexisting-logical-slot.db"
    first = ModelCallV1(
        physical_call_id="a" * 64,
        run_id="run",
        arm_id="arm",
        item_id="item",
        call_index=1,
        function_id="QF_QUERY_COMPILER",
        model="fixed-model",
        model_revision=MODEL_REVISION,
        system_prompt="one",
        input_type="QueryEnvelopeV1",
        input_payload=_input(),
        output_type="QueryPlanV1",
        max_output_tokens=256,
    )
    second = ModelCallV1(**{**first.__dict__, "physical_call_id": "b" * 64})
    seed = DurableSpoolJSONPort(
        "http://spool",
        path,
        transport=lambda *_args: pytest.fail("seed touched transport"),
    )
    first_request = canonical_json(seed._request_body(first)).encode("utf-8")
    first_route, first_request_sha, first_intent_sha, first_intent = seed._intent(
        first, first_request
    )
    assert seed.ledger.prepare(
        physical_call_id=first.physical_call_id,
        intent_sha256=first_intent_sha,
        intent_bytes=first_intent,
        request_sha256=first_request_sha,
        endpoint=first_route,
        request_bytes=first_request,
    ) == "PREPARED"
    second_request = canonical_json(seed._request_body(second)).encode("utf-8")
    second_route, second_request_sha, second_intent_sha, second_intent = seed._intent(
        second, second_request
    )
    connection = seed.ledger._connection
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        """
        INSERT INTO call_state(
            physical_call_id,intent_sha256,intent_bytes,request_sha256,
            endpoint,request_bytes,status
        ) VALUES(?,?,?,?,?,?,'PREPARED')
        """,
        (
            second.physical_call_id,
            second_intent_sha,
            second_intent,
            second_request_sha,
            second_route,
            second_request,
        ),
    )
    seed.ledger._append_event_tx(
        second.physical_call_id,
        "PREPARED",
        {
            "intent_sha256": second_intent_sha,
            "request_sha256": second_request_sha,
        },
    )
    connection.execute("COMMIT")
    counts = (
        connection.execute("SELECT COUNT(*) FROM call_state").fetchone()[0],
        connection.execute("SELECT COUNT(*) FROM attempt_events").fetchone()[0],
    )
    unrelated = ModelCallV1(
        **{
            **first.__dict__,
            "physical_call_id": "c" * 64,
            "item_id": "unrelated-item",
        }
    )
    with pytest.raises(DurableLedgerIntegrityError, match="repeats a logical call slot"):
        seed(unrelated)
    assert (
        connection.execute("SELECT COUNT(*) FROM call_state").fetchone()[0],
        connection.execute("SELECT COUNT(*) FROM attempt_events").fetchone()[0],
    ) == counts
    seed.close()

    before = _sqlite_family_snapshot(path)
    transport = AttestedTransport()
    with pytest.raises(DurableLedgerIntegrityError, match="repeats a logical call slot"):
        DurableSpoolJSONPort("http://spool", path, transport=transport)
    assert _sqlite_family_snapshot(path) == before
    assert transport.calls == 0


@pytest.mark.parametrize(
    "body",
    [
        b'{"model":"fixed-model","choices":[',
        _openai_bytes(_query_plan(), content_text='{"request_id":"cut'),
        _openai_bytes(_query_plan(), finish_reason="length"),
        _openai_bytes(
            {
                "request_id": "request-1",
                "objectives": ["answer"],
                "required_evidence_types": ["text"],
                "abstain": False,
            }
        ),
        _openai_bytes(
            _query_plan(),
            content_text='{"request_id":"request-1","request_id":"request-1",'
            '"objectives":["answer"],"required_evidence_types":["text"],'
            '"constraints":[],"abstain":false}',
        ),
    ],
)
def test_invalid_attempts_leave_zero_accepted_receipts(
    tmp_path: Path, body: bytes
) -> None:
    transport = AttestedTransport(lambda _request: body)
    with DurableSpoolJSONPort(
        "http://spool", tmp_path / "invalid.db", transport=transport
    ) as port:
        with pytest.raises(ProtocolRejected):
            _invoke(port)
        with pytest.raises(ProtocolRejected, match="prior physical call"):
            _invoke(port)
        assert port.audit()["status_counts"] == {"REJECTED_PROTOCOL": 1}
    assert transport.calls == 1


class SimulatedCrash(BaseException):
    pass


def test_crash_after_raw_commit_recovers_offline(tmp_path: Path) -> None:
    transport = AttestedTransport()
    fired = {"value": False}

    def crash(stage: str, _call: ModelCallV1) -> None:
        if stage == "after_raw" and not fired["value"]:
            fired["value"] = True
            raise SimulatedCrash

    ledger = tmp_path / "crash.db"
    port = DurableSpoolJSONPort(
        "http://spool", ledger, transport=transport, fault_injector=crash
    )
    with pytest.raises(SimulatedCrash):
        _invoke(port)
    port.close()
    assert transport.calls == 1

    with DurableSpoolJSONPort(
        "http://spool",
        ledger,
        transport=lambda *_args: pytest.fail("RAW_COMPLETE recovery touched network"),
    ) as reopened:
        output, _receipt = _invoke(reopened)
        assert output == _query_plan()
        assert reopened.audit()["status_counts"] == {"ACCEPTED": 1}


def _sent_ordinals(path: Path) -> list[int]:
    connection = __import__("sqlite3").connect(path)
    try:
        rows = connection.execute(
            "SELECT event_bytes FROM attempt_events "
            "WHERE event_type='SENT' ORDER BY sequence"
        ).fetchall()
    finally:
        connection.close()
    return [json.loads(bytes(row[0]).decode("utf-8"))["detail"]["delivery_ordinal"] for row in rows]


def test_crash_after_sent_resumes_with_the_next_lifetime_ordinal(
    tmp_path: Path,
) -> None:
    path = tmp_path / "after-sent.db"
    fired = {"value": False}

    def crash(stage: str, _call: ModelCallV1) -> None:
        if stage == "after_sent" and not fired["value"]:
            fired["value"] = True
            raise SimulatedCrash

    first_transport = AttestedTransport()
    port = DurableSpoolJSONPort(
        "http://spool",
        path,
        transport=first_transport,
        max_delivery_attempts=2,
        delivery_backoff_s=(0.0,),
        fault_injector=crash,
    )
    with pytest.raises(SimulatedCrash):
        _invoke(port)
    port.close()
    assert first_transport.calls == 0

    resumed_transport = AttestedTransport()
    with DurableSpoolJSONPort(
        "http://spool",
        path,
        transport=resumed_transport,
        max_delivery_attempts=2,
        delivery_backoff_s=(0.0,),
    ) as reopened:
        output, _receipt = _invoke(reopened)
        assert output == _query_plan()
        assert reopened.audit()["status_counts"] == {"ACCEPTED": 1}
    assert resumed_transport.calls == 1
    assert _sent_ordinals(path) == [1, 2]


def test_crash_after_last_sent_aborts_before_any_restart_transport(
    tmp_path: Path,
) -> None:
    path = tmp_path / "after-last-sent.db"

    def crash(stage: str, _call: ModelCallV1) -> None:
        if stage == "after_sent":
            raise SimulatedCrash

    first_transport = AttestedTransport()
    port = DurableSpoolJSONPort(
        "http://spool",
        path,
        transport=first_transport,
        max_delivery_attempts=1,
        delivery_backoff_s=(0.0,),
        fault_injector=crash,
    )
    with pytest.raises(SimulatedCrash):
        _invoke(port)
    port.close()
    assert first_transport.calls == 0

    resumed_transport = AttestedTransport()
    with DurableSpoolJSONPort(
        "http://spool",
        path,
        transport=resumed_transport,
        max_delivery_attempts=1,
        delivery_backoff_s=(0.0,),
    ) as reopened:
        with pytest.raises(AmbiguousModelOutcome, match="lifetime budget"):
            _invoke(reopened)
        assert reopened.audit()["status_counts"] == {"AMBIGUOUS_ABORT": 1}
    assert resumed_transport.calls == 0
    assert _sent_ordinals(path) == [1]


def test_pending_spool_result_is_reconciled_without_new_call_identity(
    tmp_path: Path,
) -> None:
    accepted = AttestedTransport()
    calls = {"count": 0}

    def pending_then_complete(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            body = canonical_json(
                {"status": "REFUSED", "code": "OUTCOME_PENDING", "detail": "running"}
            ).encode("utf-8")
            return RawHTTPResponse(
                status=425,
                headers={"content-type": "application/json", "content-length": str(len(body))},
                body=body,
            )
        return accepted(request, timeout)

    with DurableSpoolJSONPort(
        "http://spool",
        tmp_path / "pending.db",
        transport=pending_then_complete,
        max_delivery_attempts=2,
        delivery_backoff_s=(0.0,),
    ) as port:
        output, _receipt = _invoke(port)
        audit = port.audit()
    assert output == _query_plan()
    assert calls["count"] == 2
    assert audit["status_counts"] == {"ACCEPTED": 1}


def test_disconnect_after_spool_commit_replays_identical_bytes_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upstream_calls = {"count": 0}
    response_body = _openai_bytes(_query_plan())

    def upstream(_request: urllib_request.Request, _timeout: float) -> RawHTTPResponse:
        upstream_calls["count"] += 1
        return RawHTTPResponse(
            status=200,
            headers={"content-type": "application/json", "content-length": str(len(response_body))},
            body=response_body,
        )

    spool = SQLiteResultSpool(tmp_path / "spool.db")
    upstream_endpoint = "http://upstream/v1/chat/completions"
    binding = _deployment_binding(upstream_endpoint)
    monkeypatch.setattr(
        result_spool,
        "load_model_deployment_binding",
        lambda *_args, **_kwargs: binding,
    )
    service = ResultSpoolService(
        spool,
        upstream_endpoint=upstream_endpoint,
        deployment_binding=binding,
        deployment_receipt_path=tmp_path / "deployment.json",
        upstream_transport=upstream,
        client_token="spool-client-secret",
    )
    server = ResultSpoolHTTPServer(
        ("127.0.0.1", 0), service, disconnect_after_commit_once=True
    )
    thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setenv("HSWM_TEST_SPOOL_TOKEN", "spool-client-secret")
    try:
        with DurableSpoolJSONPort(
            endpoint,
            tmp_path / "client.db",
            spool_token_env="HSWM_TEST_SPOOL_TOKEN",
            max_delivery_attempts=2,
            delivery_backoff_s=(0.0,),
        ) as port:
            output, _receipt = _invoke(port)
            client_audit = port.audit()
        spool_audit = spool.audit()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        spool.close()
    assert output == _query_plan()
    assert upstream_calls["count"] == 1
    assert spool_audit["status_counts"] == {"COMPLETE": 1}
    assert client_audit["status_counts"] == {"ACCEPTED": 1}
    assert (
        spool_audit["completed_root_sha256"]
        == client_audit["spool_binding_root_sha256"]
    )
    assert b"spool-client-secret" not in (tmp_path / "client.db").read_bytes()
    assert b"spool-client-secret" not in (tmp_path / "spool.db").read_bytes()


def test_spool_refuses_plain_non_loopback_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spool = SQLiteResultSpool(tmp_path / "loopback.db")
    upstream_endpoint = "http://upstream/v1/chat/completions"
    binding = _deployment_binding(upstream_endpoint)
    monkeypatch.setattr(
        result_spool,
        "load_model_deployment_binding",
        lambda *_args, **_kwargs: binding,
    )
    service = ResultSpoolService(
        spool,
        upstream_endpoint=upstream_endpoint,
        deployment_binding=binding,
        deployment_receipt_path=tmp_path / "deployment.json",
        upstream_transport=lambda *_args: pytest.fail("server should not start"),
    )
    try:
        with pytest.raises(ResultSpoolError, match="bind loopback"):
            ResultSpoolHTTPServer(("0.0.0.0", 0), service)
    finally:
        spool.close()


def test_event_chain_tamper_is_detected_on_reopen(tmp_path: Path) -> None:
    path = tmp_path / "tamper.db"
    with DurableSpoolJSONPort(
        "http://spool", path, transport=AttestedTransport()
    ) as port:
        _invoke(port)
    connection = __import__("sqlite3").connect(path)
    connection.execute("UPDATE attempt_events SET event_type='CORRUPT' WHERE sequence=0")
    connection.commit()
    connection.close()
    with pytest.raises(DurableLedgerIntegrityError):
        SQLiteF1CallLedger(path)


def test_item_run_byte_tamper_is_detected_by_audit(tmp_path: Path) -> None:
    from prom_search_hswm.prom_f1_function_network import run_suite
    from prom_search_hswm.test_prom9_experiment_harness import _f1_manifest
    from prom_search_hswm.hswm_token_meter import FakeMeter

    manifest = _f1_manifest(FakeMeter())
    manifest["items"] = manifest["items"][:1]
    manifest["token_envelope"]["per_call_input_caps"] = {
        key: value + 1000
        for key, value in manifest["token_envelope"]["per_call_input_caps"].items()
    }
    path = tmp_path / "item-tamper.db"
    with DurableSpoolJSONPort(
        "http://spool", path, transport=FunctionNetworkTransport()
    ) as port:
        run_suite(
            manifest,
            protocol_path=DEFAULT_PROTOCOL,
            model_port=port,
            token_meter=FakeMeter(),
            max_workers=1,
        )
    connection = __import__("sqlite3").connect(path)
    raw = bytearray(connection.execute("SELECT item_run_bytes FROM item_runs LIMIT 1").fetchone()[0])
    raw[-2] = ord("0") if raw[-2] != ord("0") else ord("1")
    connection.execute("UPDATE item_runs SET item_run_bytes=?", (bytes(raw),))
    connection.commit()
    connection.close()
    with pytest.raises(DurableLedgerIntegrityError, match="pre-write logical audit"):
        SQLiteF1CallLedger(path)


def test_server_process_kill_after_dispatch_never_redispatches(tmp_path: Path) -> None:
    path = tmp_path / "killed-spool.db"
    program = f"""
import os
from prom_search_hswm.hswm_result_spool import SQLiteResultSpool
store = SQLiteResultSpool({str(path)!r})
store.execute(
    physical_call_id={'a' * 64!r},
    intent_sha256={'b' * 64!r},
    request_bytes=b'{{}}',
    upstream=lambda _body: os._exit(77),
)
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=Path(__file__).parents[1],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    assert result.returncode == 77
    calls = {"count": 0}
    reopened = SQLiteResultSpool(path)
    try:
        def forbidden(_body):
            calls["count"] += 1
            return RawHTTPResponse(200, {}, b"{}")

        from prom_search_hswm.hswm_result_spool import SpoolOutcomeUnknown

        with pytest.raises(SpoolOutcomeUnknown, match="UNKNOWN"):
            reopened.execute(
                physical_call_id="a" * 64,
                intent_sha256="b" * 64,
                request_bytes=b"{}",
                upstream=forbidden,
            )
        assert calls["count"] == 0
        assert reopened.audit()["status_counts"] == {"UNKNOWN": 1}
    finally:
        reopened.close()


class FunctionNetworkTransport(AttestedTransport):
    def __init__(self) -> None:
        super().__init__(self._body)

    @staticmethod
    def _body(request: urllib_request.Request) -> bytes:
        request_value = json.loads(bytes(request.data or b"").decode("utf-8"))
        payload = json.loads(request_value["messages"][1]["content"])
        request_id = payload["request_id"]
        if "query_text" in payload and "budget" in payload:
            output = _query_plan(request_id)
        elif "candidate_table" in payload:
            columns = payload["candidate_table"]["columns"]
            row = payload["candidate_table"]["rows"][0]
            bond_id = row[columns.index("bond_id")]
            evidence_id = row[columns.index("evidence_id")]
            output = {
                "request_id": request_id,
                "ordered_bond_ids": [bond_id],
                "bond_potentials": {bond_id: 0.0},
                "evidence_refs": [evidence_id],
                "abstain": False,
            }
        else:
            evidence_ids = [item["evidence_id"] for item in payload["selected_evidence"]]
            output = {
                "request_id": request_id,
                "answer": "Paris",
                "supporting_evidence_ids": evidence_ids,
                "uncertainty": "low",
                "abstain": False,
            }
        from prom_search_hswm.hswm_token_meter import FakeMeter

        prompt_tokens = FakeMeter().count_chat_prompt(
            request_value["messages"][0]["content"],
            request_value["messages"][1]["content"],
        )
        value = {
            "model": request_value["model"],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 1},
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": canonical_json(output)},
                }
            ],
        }
        return canonical_json(value).encode("utf-8")


def test_one_item_five_arm_fixture_is_durable_15_calls_5_items(tmp_path: Path) -> None:
    from prom_search_hswm.prom_f1_function_network import run_suite
    from prom_search_hswm.test_prom9_experiment_harness import _f1_manifest
    from prom_search_hswm.hswm_token_meter import FakeMeter

    manifest = _f1_manifest(FakeMeter())
    manifest["items"] = manifest["items"][:1]
    manifest["token_envelope"]["per_call_input_caps"] = {
        key: value + 1000
        for key, value in manifest["token_envelope"]["per_call_input_caps"].items()
    }
    transport = FunctionNetworkTransport()
    with DurableSpoolJSONPort(
        "http://spool",
        tmp_path / "fixture.db",
        transport=transport,
        delivery_backoff_s=(0.0,),
    ) as port:
        first = run_suite(
            manifest,
            protocol_path=DEFAULT_PROTOCOL,
            model_port=port,
            token_meter=FakeMeter(),
            max_workers=2,
        )
        second = run_suite(
            manifest,
            protocol_path=DEFAULT_PROTOCOL,
            model_port=port,
            token_meter=FakeMeter(),
            max_workers=2,
        )
        audit = port.audit()
    assert first == second
    assert transport.calls == 15
    assert audit["status_counts"] == {"ACCEPTED": 15}
    assert audit["item_run_count"] == 5
    assert first["transport_audit"] == audit
