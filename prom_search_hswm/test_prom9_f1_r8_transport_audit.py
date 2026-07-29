from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from urllib import request as urllib_request

import pytest

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
    TRANSPORT_BINDINGS_SCHEMA,
    TransportAuditRefusal,
    export_genesis,
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

    def __call__(
        self, request: urllib_request.Request, _timeout: float
    ) -> RawHTTPResponse:
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
        registry = build_registry(
            REPO_ROOT / DEFAULT_PROTOCOL,
            model="fixed-model",
            model_revision="fixed-revision",
        )
        item = FunctionNetworkItemV1(
            item_id="item-1",
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
        live_audit = port.audit()
        spool_audit = spool.audit()
    finally:
        port.close()
        spool.close()
    return attempt_db, spool_db, genesis, live_audit, spool_audit


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
