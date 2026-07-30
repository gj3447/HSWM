"""Crash-durable F1 call journal and result-spool client.

The local ledger persists every call state transition with SQLite WAL/FULL.
The network boundary is an idempotent result spool, not the model endpoint
itself: repeated delivery may replay bytes, but it may not create a second
inference for the same ``physical_call_id``.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from prom_search_hswm.hswm_call_receipt import (
    CallReceiptV1,
    FunctionCallError,
    ModelCallV1,
    ModelResponseV1,
    verify_call_receipt,
)
from prom_search_hswm.hswm_result_spool import RawHTTPResponse, SPOOL_ROUTE_PREFIX
from prom_search_hswm.hswm_typed_ports import (
    canonical_json,
    canonical_sha256,
    output_json_schema,
    output_schema_sha256,
    validate_port,
)


DURABLE_CALL_SCHEMA = "hswm-f1-durable-call-ledger/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GENESIS = "0" * 64
_TERMINAL = frozenset({"ACCEPTED", "REJECTED_PROTOCOL", "AMBIGUOUS_ABORT"})
_EVENT_TRANSITIONS = {
    "PREPARED": (None,),
    "SENT": ("PREPARED", "DELIVERY_AMBIGUOUS", "SENT"),
    "DELIVERY_AMBIGUOUS": ("SENT",),
    "RAW_COMPLETE": ("SENT",),
    "ENVELOPE_VALID": ("RAW_COMPLETE",),
    "SCHEMA_VALID": ("ENVELOPE_VALID",),
    "ACCEPTED": ("SCHEMA_VALID",),
    "REJECTED_PROTOCOL": (
        "RAW_COMPLETE",
        "ENVELOPE_VALID",
        "SCHEMA_VALID",
        "SENT",
    ),
    "AMBIGUOUS_ABORT": ("PREPARED", "SENT", "DELIVERY_AMBIGUOUS"),
}


class DurableTransportError(FunctionCallError):
    pass


class DurableIntentConflict(DurableTransportError):
    pass


class DurableLedgerIntegrityError(DurableTransportError):
    pass


class AmbiguousModelOutcome(DurableTransportError):
    pass


class ProtocolRejected(DurableTransportError):
    pass


class _DuplicateKey(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return canonical_json(value).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _strict_json(raw: bytes | str, label: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise _DuplicateKey(key)
            result[key] = value
        return result

    def constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant {value}")

    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKey, ValueError) as error:
        raise ProtocolRejected(f"{label} is not strict RFC 8259 JSON: {error}") from error


def _require_sha256(value: str, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise DurableTransportError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _make_private_sqlite_files(path: Path) -> None:
    for candidate in (Path(path), Path(f"{path}-wal"), Path(f"{path}-shm")):
        try:
            candidate.chmod(0o600)
        except FileNotFoundError:
            continue


def _model_response_value(response: ModelResponseV1) -> dict[str, object]:
    return {
        "payload": response.payload,
        "model": response.model,
        "model_revision": response.model_revision,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "latency_ms": response.latency_ms,
        "cache_status": response.cache_status,
        "retries": response.retries,
    }


def _model_response_from_value(value: object) -> ModelResponseV1:
    if not isinstance(value, dict) or set(value) != {
        "payload",
        "model",
        "model_revision",
        "input_tokens",
        "output_tokens",
        "latency_ms",
        "cache_status",
        "retries",
    }:
        raise DurableLedgerIntegrityError("stored model response schema drifted")
    if not isinstance(value["payload"], dict):
        raise DurableLedgerIntegrityError("stored model response payload drifted")
    try:
        return ModelResponseV1(**value)
    except TypeError as error:
        raise DurableLedgerIntegrityError("stored model response fields drifted") from error


class SQLiteF1CallLedger:
    """Append-audited projection store for calls and completed item-arms."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existed = self.path.exists()
        if not existed:
            descriptor = os.open(
                self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            os.close(descriptor)
            _fsync_parent(self.path)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(self.path), isolation_level=None, timeout=10.0, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA busy_timeout=10000")
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
        if version not in (0, 1):
            raise DurableLedgerIntegrityError(f"unsupported F1 ledger schema version {version}")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS call_state (
                physical_call_id TEXT PRIMARY KEY,
                intent_sha256 TEXT NOT NULL,
                intent_bytes BLOB NOT NULL,
                request_sha256 TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                request_bytes BLOB NOT NULL,
                status TEXT NOT NULL CHECK(status IN (
                    'PREPARED','SENT','DELIVERY_AMBIGUOUS','RAW_COMPLETE',
                    'ENVELOPE_VALID','SCHEMA_VALID','ACCEPTED',
                    'REJECTED_PROTOCOL','AMBIGUOUS_ABORT'
                )),
                response_status INTEGER,
                response_headers BLOB,
                response_body BLOB,
                response_sha256 TEXT,
                model_response BLOB,
                model_response_sha256 TEXT,
                call_receipt BLOB,
                call_receipt_sha256 TEXT,
                terminal_code TEXT
            );
            CREATE TABLE IF NOT EXISTS attempt_events (
                sequence INTEGER PRIMARY KEY,
                physical_call_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_bytes BLOB NOT NULL,
                previous_event_sha256 TEXT NOT NULL,
                event_sha256 TEXT NOT NULL,
                FOREIGN KEY (physical_call_id) REFERENCES call_state(physical_call_id)
            );
            CREATE TABLE IF NOT EXISTS item_runs (
                run_id TEXT NOT NULL,
                arm_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                run_receipt_sha256 TEXT NOT NULL,
                item_run_bytes BLOB NOT NULL,
                PRIMARY KEY (run_id,arm_id,item_id)
            );
            """
        )
        self._connection.execute("PRAGMA user_version=1")
        _make_private_sqlite_files(self.path)
        if not existed:
            _fsync_parent(self.path)
        self.verify_event_chain()

    @property
    def journal_mode(self) -> str:
        return str(self._connection.execute("PRAGMA journal_mode").fetchone()[0]).casefold()

    @property
    def synchronous(self) -> int:
        return int(self._connection.execute("PRAGMA synchronous").fetchone()[0])

    @staticmethod
    def _verify_call_row(row: sqlite3.Row) -> None:
        intent_bytes = bytes(row["intent_bytes"])
        if _sha256_bytes(intent_bytes) != row["intent_sha256"]:
            raise DurableLedgerIntegrityError("stored F1 intent bytes drifted")
        intent_value = _strict_json(intent_bytes, "stored F1 intent")
        if not isinstance(intent_value, dict) or _canonical_bytes(intent_value) != intent_bytes:
            raise DurableLedgerIntegrityError("stored F1 intent is not canonical")
        request_bytes = bytes(row["request_bytes"])
        if _sha256_bytes(request_bytes) != row["request_sha256"]:
            raise DurableLedgerIntegrityError("stored F1 request bytes drifted")
        if row["response_body"] is not None:
            response_body = bytes(row["response_body"])
            if _sha256_bytes(response_body) != row["response_sha256"]:
                raise DurableLedgerIntegrityError("stored F1 response bytes drifted")
            headers = _strict_json(bytes(row["response_headers"]), "stored response headers")
            if not isinstance(headers, dict) or _canonical_bytes(headers) != bytes(row["response_headers"]):
                raise DurableLedgerIntegrityError("stored F1 response headers are not canonical")
        if row["model_response"] is not None:
            raw = bytes(row["model_response"])
            if _sha256_bytes(raw) != row["model_response_sha256"]:
                raise DurableLedgerIntegrityError("stored model response bytes drifted")
            value = _strict_json(raw, "stored model response")
            _model_response_from_value(value)
            if _canonical_bytes(value) != raw:
                raise DurableLedgerIntegrityError("stored model response is not canonical")
        if row["call_receipt"] is not None:
            raw = bytes(row["call_receipt"])
            value = _strict_json(raw, "stored call receipt")
            if not isinstance(value, dict) or _canonical_bytes(value) != raw:
                raise DurableLedgerIntegrityError("stored call receipt is not canonical")
            declared = verify_call_receipt(value)
            if declared != row["call_receipt_sha256"]:
                raise DurableLedgerIntegrityError("stored call receipt digest drifted")

    @staticmethod
    def _verify_accepted_row_binding(row: sqlite3.Row) -> None:
        SQLiteF1CallLedger._verify_call_row(row)
        status = str(row["status"])
        response_required = status in {
            "RAW_COMPLETE",
            "ENVELOPE_VALID",
            "SCHEMA_VALID",
            "ACCEPTED",
            "REJECTED_PROTOCOL",
        }
        model_required = status in {"SCHEMA_VALID", "ACCEPTED"}
        receipt_required = status == "ACCEPTED"
        if response_required and row["response_body"] is None:
            raise DurableLedgerIntegrityError("F1 status lacks its durable raw response")
        if model_required and row["model_response"] is None:
            raise DurableLedgerIntegrityError("F1 status lacks its durable model response")
        if receipt_required and row["call_receipt"] is None:
            raise DurableLedgerIntegrityError("ACCEPTED F1 call lacks its receipt")
        if not receipt_required:
            return
        intent = _strict_json(bytes(row["intent_bytes"]), "stored F1 intent")
        request = _strict_json(bytes(row["request_bytes"]), "stored F1 request")
        response_value = _strict_json(
            bytes(row["model_response"]), "stored model response"
        )
        receipt = _strict_json(bytes(row["call_receipt"]), "stored call receipt")
        if (
            not isinstance(intent, dict)
            or not isinstance(intent.get("call"), dict)
            or not isinstance(request, dict)
            or not isinstance(response_value, dict)
            or not isinstance(receipt, dict)
        ):
            raise DurableLedgerIntegrityError("accepted F1 binding shape drifted")
        stored_call = intent["call"]
        response = _model_response_from_value(response_value)
        response_headers = _strict_json(
            bytes(row["response_headers"]), "accepted F1 response headers"
        )
        if not isinstance(response_headers, dict):
            raise DurableLedgerIntegrityError("accepted F1 response headers drifted")
        expected_spool_headers = {
            "x-hswm-spool-call-id": row["physical_call_id"],
            "x-hswm-spool-intent-sha256": row["intent_sha256"],
            "x-hswm-spool-request-sha256": row["request_sha256"],
            "x-hswm-spool-response-sha256": row["response_sha256"],
            "x-hswm-spool-server-revision": stored_call.get("model_revision"),
        }
        for key, expected_value in expected_spool_headers.items():
            if response_headers.get(key) != expected_value:
                raise DurableLedgerIntegrityError(
                    f"accepted F1 spool attestation drifted: {key}"
                )
        if response_headers.get("x-hswm-spool-replayed") not in {"true", "false"}:
            raise DurableLedgerIntegrityError("accepted F1 spool replay flag drifted")
        messages = request.get("messages")
        if (
            not isinstance(messages, list)
            or len(messages) != 2
            or not isinstance(messages[0], dict)
            or not isinstance(messages[1], dict)
        ):
            raise DurableLedgerIntegrityError("accepted F1 request messages drifted")
        stored_input = _strict_json(
            str(messages[1].get("content", "")), "accepted F1 input payload"
        )
        expected = {
            "physical_call_id": stored_call.get("physical_call_id"),
            "run_id": stored_call.get("run_id"),
            "arm_id": stored_call.get("arm_id"),
            "item_id": stored_call.get("item_id"),
            "call_index": stored_call.get("call_index"),
            "function_id": stored_call.get("function_id"),
            "model": response.model,
            "model_revision": response.model_revision,
            "prompt_sha256": canonical_sha256(
                {"prompt": messages[0].get("content")}
            ),
            "input_type": stored_call.get("input_type"),
            "input_payload": stored_input,
            "output_type": stored_call.get("output_type"),
            "output_payload": response.payload,
            "allowed_output_tokens": stored_call.get("max_output_tokens"),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "latency_ms": response.latency_ms,
            "cache_status": response.cache_status,
            "retries": response.retries,
        }
        for key, expected_value in expected.items():
            if receipt.get(key) != expected_value:
                raise DurableLedgerIntegrityError(
                    f"accepted receipt is not bound to intent/response: {key}"
                )

    def _append_event_tx(
        self, physical_call_id: str, event_type: str, detail: Mapping[str, object]
    ) -> None:
        last = self._connection.execute(
            "SELECT sequence,event_sha256 FROM attempt_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        sequence = 0 if last is None else int(last["sequence"]) + 1
        previous = _GENESIS if last is None else str(last["event_sha256"])
        event = {
            "schema_version": DURABLE_CALL_SCHEMA,
            "sequence": sequence,
            "physical_call_id": physical_call_id,
            "event_type": event_type,
            "detail": dict(detail),
            "previous_event_sha256": previous,
        }
        event_bytes = _canonical_bytes(event)
        digest = _sha256_bytes(event_bytes)
        self._connection.execute(
            """
            INSERT INTO attempt_events(
                sequence,physical_call_id,event_type,event_bytes,
                previous_event_sha256,event_sha256
            ) VALUES(?,?,?,?,?,?)
            """,
            (sequence, physical_call_id, event_type, event_bytes, previous, digest),
        )

    def verify_event_chain(self) -> str:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM attempt_events ORDER BY sequence"
            ).fetchall()
            previous = _GENESIS
            for expected, row in enumerate(rows):
                if row["sequence"] != expected or row["previous_event_sha256"] != previous:
                    raise DurableLedgerIntegrityError("F1 attempt event order or chain drifted")
                raw = bytes(row["event_bytes"])
                value = _strict_json(raw, "F1 attempt event")
                if not isinstance(value, dict) or _canonical_bytes(value) != raw:
                    raise DurableLedgerIntegrityError("F1 attempt event is not canonical")
                if (
                    value.get("sequence") != expected
                    or value.get("physical_call_id") != row["physical_call_id"]
                    or value.get("event_type") != row["event_type"]
                    or value.get("previous_event_sha256") != previous
                    or _sha256_bytes(raw) != row["event_sha256"]
                ):
                    raise DurableLedgerIntegrityError("F1 attempt event content drifted")
                previous = str(row["event_sha256"])
            return previous

    def prepare(
        self,
        *,
        physical_call_id: str,
        intent_sha256: str,
        intent_bytes: bytes,
        request_sha256: str,
        endpoint: str,
        request_bytes: bytes,
    ) -> str:
        _require_sha256(physical_call_id, "physical_call_id")
        _require_sha256(intent_sha256, "intent_sha256")
        if _sha256_bytes(intent_bytes) != intent_sha256:
            raise DurableTransportError("intent_sha256 does not match intent bytes")
        _require_sha256(request_sha256, "request_sha256")
        if _sha256_bytes(request_bytes) != request_sha256:
            raise DurableTransportError("request_sha256 does not match request bytes")
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                row = self._connection.execute(
                    "SELECT * FROM call_state WHERE physical_call_id=?",
                    (physical_call_id,),
                ).fetchone()
                if row is not None:
                    self._verify_call_row(row)
                    if (
                        row["intent_sha256"] != intent_sha256
                        or bytes(row["intent_bytes"]) != intent_bytes
                        or row["request_sha256"] != request_sha256
                        or row["endpoint"] != endpoint
                        or bytes(row["request_bytes"]) != request_bytes
                    ):
                        raise DurableIntentConflict(
                            "same physical_call_id carries different durable intent"
                        )
                    self._connection.execute("COMMIT")
                    return str(row["status"])
                self._connection.execute(
                    """
                    INSERT INTO call_state(
                        physical_call_id,intent_sha256,intent_bytes,request_sha256,
                        endpoint,request_bytes,status
                    ) VALUES(?,?,?,?,?,?,'PREPARED')
                    """,
                    (
                        physical_call_id,
                        intent_sha256,
                        intent_bytes,
                        request_sha256,
                        endpoint,
                        request_bytes,
                    ),
                )
                self._append_event_tx(
                    physical_call_id,
                    "PREPARED",
                    {"intent_sha256": intent_sha256, "request_sha256": request_sha256},
                )
                self._connection.execute("COMMIT")
                return "PREPARED"
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def status(self, physical_call_id: str) -> str:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM call_state WHERE physical_call_id=?", (physical_call_id,)
            ).fetchone()
            if row is None:
                raise DurableLedgerIntegrityError("F1 call disappeared from ledger")
            self._verify_call_row(row)
            return str(row["status"])

    def _transition(
        self,
        physical_call_id: str,
        new_status: str,
        detail: Mapping[str, object],
        *,
        assignments: Mapping[str, object] | None = None,
    ) -> None:
        if new_status not in _EVENT_TRANSITIONS:
            raise DurableLedgerIntegrityError(f"unknown F1 transition {new_status}")
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                row = self._connection.execute(
                    "SELECT * FROM call_state WHERE physical_call_id=?", (physical_call_id,)
                ).fetchone()
                if row is None:
                    raise DurableLedgerIntegrityError("transition target is absent")
                self._verify_call_row(row)
                current = str(row["status"])
                if current not in _EVENT_TRANSITIONS[new_status]:
                    raise DurableLedgerIntegrityError(
                        f"invalid F1 transition {current} -> {new_status}"
                    )
                values = dict(assignments or {})
                allowed_columns = {
                    "response_status",
                    "response_headers",
                    "response_body",
                    "response_sha256",
                    "model_response",
                    "model_response_sha256",
                    "call_receipt",
                    "call_receipt_sha256",
                    "terminal_code",
                }
                if not set(values).issubset(allowed_columns):
                    raise DurableLedgerIntegrityError("transition attempted an unknown column")
                clauses = ["status=?", *[f"{column}=?" for column in values]]
                parameters = [new_status, *values.values(), physical_call_id]
                self._connection.execute(
                    f"UPDATE call_state SET {','.join(clauses)} WHERE physical_call_id=?",
                    parameters,
                )
                self._append_event_tx(physical_call_id, new_status, detail)
                self._connection.execute("COMMIT")
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def mark_sent(self, physical_call_id: str, delivery_ordinal: int) -> None:
        self._transition(
            physical_call_id,
            "SENT",
            {"delivery_ordinal": delivery_ordinal, "same_inference_identity": True},
        )

    def mark_delivery_ambiguous(
        self, physical_call_id: str, delivery_ordinal: int, error_class: str
    ) -> None:
        self._transition(
            physical_call_id,
            "DELIVERY_AMBIGUOUS",
            {"delivery_ordinal": delivery_ordinal, "error_class": error_class},
        )

    def store_raw(self, physical_call_id: str, response: RawHTTPResponse) -> None:
        headers = {str(key).casefold(): str(value) for key, value in response.headers.items()}
        header_bytes = _canonical_bytes({key: headers[key] for key in sorted(headers)})
        response_sha256 = _sha256_bytes(response.body)
        self._transition(
            physical_call_id,
            "RAW_COMPLETE",
            {
                "http_status": response.status,
                "response_sha256": response_sha256,
                "response_bytes": len(response.body),
            },
            assignments={
                "response_status": response.status,
                "response_headers": header_bytes,
                "response_body": response.body,
                "response_sha256": response_sha256,
            },
        )

    def mark_envelope_valid(
        self, physical_call_id: str, *, finish_reason: str, served_model: str
    ) -> None:
        self._transition(
            physical_call_id,
            "ENVELOPE_VALID",
            {"finish_reason": finish_reason, "served_model": served_model},
        )

    def mark_schema_valid(
        self, physical_call_id: str, response: ModelResponseV1, *, output_type: str
    ) -> None:
        value = _model_response_value(response)
        raw = _canonical_bytes(value)
        self._transition(
            physical_call_id,
            "SCHEMA_VALID",
            {
                "output_type": output_type,
                "output_schema_sha256": output_schema_sha256(output_type),
                "model_response_sha256": _sha256_bytes(raw),
            },
            assignments={
                "model_response": raw,
                "model_response_sha256": _sha256_bytes(raw),
            },
        )

    def reject_protocol(self, physical_call_id: str, code: str) -> None:
        current = self.status(physical_call_id)
        if current == "REJECTED_PROTOCOL":
            return
        self._transition(
            physical_call_id,
            "REJECTED_PROTOCOL",
            {"code": code},
            assignments={"terminal_code": code},
        )

    def ambiguous_abort(self, physical_call_id: str, code: str) -> None:
        current = self.status(physical_call_id)
        if current == "AMBIGUOUS_ABORT":
            return
        self._transition(
            physical_call_id,
            "AMBIGUOUS_ABORT",
            {"code": code},
            assignments={"terminal_code": code},
        )

    def raw_response(self, physical_call_id: str) -> RawHTTPResponse:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM call_state WHERE physical_call_id=?", (physical_call_id,)
            ).fetchone()
            if row is None:
                raise DurableLedgerIntegrityError("raw response target is absent")
            self._verify_call_row(row)
            if row["response_body"] is None:
                raise DurableLedgerIntegrityError("raw response is not durable")
            return RawHTTPResponse(
                status=int(row["response_status"]),
                headers=dict(_strict_json(bytes(row["response_headers"]), "stored headers")),
                body=bytes(row["response_body"]),
            )

    def model_response(self, physical_call_id: str) -> ModelResponseV1:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM call_state WHERE physical_call_id=?", (physical_call_id,)
            ).fetchone()
            if row is None:
                raise DurableLedgerIntegrityError("model response target is absent")
            self._verify_call_row(row)
            if row["model_response"] is None:
                raise DurableLedgerIntegrityError("model response is not durable")
            return _model_response_from_value(
                _strict_json(bytes(row["model_response"]), "stored model response")
            )

    def accept_call_receipt(self, receipt: CallReceiptV1) -> None:
        value = receipt.canonical()
        verify_call_receipt(value)
        raw = _canonical_bytes(value)
        physical_call_id = receipt.physical_call_id
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM call_state WHERE physical_call_id=?", (physical_call_id,)
            ).fetchone()
            if row is None:
                raise DurableLedgerIntegrityError("call receipt target is absent")
            self._verify_call_row(row)
            intent = _strict_json(bytes(row["intent_bytes"]), "stored F1 intent")
            request = _strict_json(bytes(row["request_bytes"]), "stored F1 request")
            response = self.model_response(physical_call_id)
            if not isinstance(intent, dict) or not isinstance(intent.get("call"), dict):
                raise DurableLedgerIntegrityError("stored call intent shape drifted")
            stored_call = intent["call"]
            messages = request.get("messages") if isinstance(request, dict) else None
            if (
                not isinstance(messages, list)
                or len(messages) != 2
                or not isinstance(messages[0], dict)
                or not isinstance(messages[1], dict)
            ):
                raise DurableLedgerIntegrityError("stored OpenAI request messages drifted")
            stored_input = _strict_json(
                str(messages[1].get("content", "")), "stored F1 input payload"
            )
            expected = {
                "physical_call_id": stored_call.get("physical_call_id"),
                "run_id": stored_call.get("run_id"),
                "arm_id": stored_call.get("arm_id"),
                "item_id": stored_call.get("item_id"),
                "call_index": stored_call.get("call_index"),
                "function_id": stored_call.get("function_id"),
                "model": response.model,
                "model_revision": response.model_revision,
                "prompt_sha256": canonical_sha256(
                    {"prompt": messages[0].get("content")}
                ),
                "input_type": stored_call.get("input_type"),
                "input_payload": stored_input,
                "output_type": stored_call.get("output_type"),
                "output_payload": response.payload,
                "allowed_output_tokens": stored_call.get("max_output_tokens"),
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "latency_ms": response.latency_ms,
                "cache_status": response.cache_status,
                "retries": response.retries,
            }
            for key, expected_value in expected.items():
                if value.get(key) != expected_value:
                    raise DurableIntentConflict(
                        f"call receipt differs from durable intent/response: {key}"
                    )
            current = str(row["status"])
            if current == "ACCEPTED":
                if bytes(row["call_receipt"]) != raw:
                    raise DurableIntentConflict("accepted call receipt replay differs")
                return
        self._transition(
            physical_call_id,
            "ACCEPTED",
            {"call_receipt_sha256": receipt.receipt_sha256},
            assignments={
                "call_receipt": raw,
                "call_receipt_sha256": receipt.receipt_sha256,
            },
        )

    def accept_item_run(self, value: Mapping[str, object]) -> None:
        from prom_search_hswm.hswm_function_network import verify_run

        verify_run(value)
        required = {"run_id", "arm_id", "item_id", "run_receipt_sha256"}
        if not required.issubset(value):
            raise DurableLedgerIntegrityError("item-run receipt lacks identity fields")
        raw = _canonical_bytes(dict(value))
        key = (str(value["run_id"]), str(value["arm_id"]), str(value["item_id"]))
        receipt_sha = str(value["run_receipt_sha256"])
        _require_sha256(receipt_sha, "run_receipt_sha256")
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                calls = value.get("calls")
                if not isinstance(calls, list):
                    raise DurableLedgerIntegrityError("item-run calls are invalid")
                for call in calls:
                    if not isinstance(call, dict):
                        raise DurableLedgerIntegrityError("item-run call is invalid")
                    physical_call_id = str(call.get("physical_call_id"))
                    accepted = self._connection.execute(
                        "SELECT * FROM call_state WHERE physical_call_id=?",
                        (physical_call_id,),
                    ).fetchone()
                    if accepted is None:
                        raise DurableLedgerIntegrityError(
                            "item-run references an absent durable call"
                        )
                    self._verify_call_row(accepted)
                    if (
                        accepted["status"] != "ACCEPTED"
                        or bytes(accepted["call_receipt"]) != _canonical_bytes(call)
                    ):
                        raise DurableIntentConflict(
                            "item-run call differs from its durable accepted receipt"
                        )
                row = self._connection.execute(
                    "SELECT * FROM item_runs WHERE run_id=? AND arm_id=? AND item_id=?", key
                ).fetchone()
                if row is not None:
                    if row["run_receipt_sha256"] != receipt_sha or bytes(row["item_run_bytes"]) != raw:
                        raise DurableIntentConflict("item-run replay differs from durable receipt")
                    self._connection.execute("COMMIT")
                    return
                self._connection.execute(
                    """
                    INSERT INTO item_runs(
                        run_id,arm_id,item_id,run_receipt_sha256,item_run_bytes
                    ) VALUES(?,?,?,?,?)
                    """,
                    (*key, receipt_sha, raw),
                )
                self._connection.execute("COMMIT")
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def audit(self) -> dict[str, object]:
        from prom_search_hswm.hswm_function_network import verify_run

        chain_tip = self.verify_event_chain()
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM call_state ORDER BY physical_call_id"
            ).fetchall()
            statuses: dict[str, int] = {}
            accepted = []
            spool_bindings = []
            for row in rows:
                self._verify_accepted_row_binding(row)
                status = str(row["status"])
                last_event = self._connection.execute(
                    """
                    SELECT event_type FROM attempt_events
                    WHERE physical_call_id=? ORDER BY sequence DESC LIMIT 1
                    """,
                    (row["physical_call_id"],),
                ).fetchone()
                if last_event is None or last_event["event_type"] != status:
                    raise DurableLedgerIntegrityError(
                        "call-state projection differs from its append-only event tail"
                    )
                statuses[status] = statuses.get(status, 0) + 1
                if status == "ACCEPTED":
                    spool_binding = {
                        "physical_call_id": row["physical_call_id"],
                        "intent_sha256": row["intent_sha256"],
                        "request_sha256": row["request_sha256"],
                        "response_sha256": row["response_sha256"],
                    }
                    spool_bindings.append(spool_binding)
                    accepted.append(
                        {
                            **spool_binding,
                            "call_receipt_sha256": row["call_receipt_sha256"],
                        }
                    )
            item_rows = self._connection.execute(
                "SELECT * FROM item_runs ORDER BY run_id,arm_id,item_id"
            ).fetchall()
            item_bindings = []
            for row in item_rows:
                raw = bytes(row["item_run_bytes"])
                value = _strict_json(raw, "durable item-run receipt")
                if not isinstance(value, dict) or _canonical_bytes(value) != raw:
                    raise DurableLedgerIntegrityError(
                        "durable item-run receipt is not canonical"
                    )
                declared = verify_run(value)
                if (
                    value.get("run_id") != row["run_id"]
                    or value.get("arm_id") != row["arm_id"]
                    or value.get("item_id") != row["item_id"]
                    or declared != row["run_receipt_sha256"]
                ):
                    raise DurableLedgerIntegrityError(
                        "durable item-run identity or receipt digest drifted"
                    )
                calls = value.get("calls")
                if not isinstance(calls, list) or len(calls) != 3:
                    raise DurableLedgerIntegrityError(
                        "durable item-run does not bind exactly three calls"
                    )
                for call in calls:
                    if not isinstance(call, dict):
                        raise DurableLedgerIntegrityError(
                            "durable item-run call is malformed"
                        )
                    accepted_row = self._connection.execute(
                        "SELECT * FROM call_state WHERE physical_call_id=?",
                        (str(call.get("physical_call_id")),),
                    ).fetchone()
                    if (
                        accepted_row is None
                        or accepted_row["status"] != "ACCEPTED"
                        or bytes(accepted_row["call_receipt"]) != _canonical_bytes(call)
                    ):
                        raise DurableLedgerIntegrityError(
                            "durable item-run is not bound to accepted call receipts"
                        )
                item_bindings.append(
                    {
                        "run_id": row["run_id"],
                        "arm_id": row["arm_id"],
                        "item_id": row["item_id"],
                        "run_receipt_sha256": row["run_receipt_sha256"],
                    }
                )
            unsigned = {
                "schema_version": DURABLE_CALL_SCHEMA,
                "journal_mode": self.journal_mode,
                "synchronous": self.synchronous,
                "event_chain_tip_sha256": chain_tip,
                "call_count": len(rows),
                "status_counts": statuses,
                "accepted_call_root_sha256": canonical_sha256(accepted),
                "spool_binding_root_sha256": canonical_sha256(spool_bindings),
                "item_run_count": len(item_rows),
                "item_run_root_sha256": canonical_sha256(item_bindings),
            }
            return {**unsigned, "audit_sha256": canonical_sha256(unsigned)}

    def close(self) -> None:
        with self._lock:
            self._connection.close()


Transport = Callable[[urllib_request.Request, float], RawHTTPResponse]
FaultInjector = Callable[[str, ModelCallV1], None]


class DurableSpoolJSONPort:
    """Strict JSON model port backed by the durable result-spool protocol."""

    def __init__(
        self,
        spool_endpoint: str,
        ledger_path: str | Path,
        *,
        spool_token_env: str | None = None,
        timeout_seconds: float = 180.0,
        transport: Transport | None = None,
        max_delivery_attempts: int = 8,
        delivery_backoff_s: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 60.0),
        max_response_bytes: int = 4_000_000,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        if not spool_endpoint.startswith(("http://", "https://")):
            raise DurableTransportError("spool endpoint must be HTTP(S)")
        if (
            isinstance(max_delivery_attempts, bool)
            or not isinstance(max_delivery_attempts, int)
            or max_delivery_attempts < 1
        ):
            raise DurableTransportError("max_delivery_attempts must be positive")
        if timeout_seconds <= 0 or max_response_bytes <= 0:
            raise DurableTransportError("timeout and response byte cap must be positive")
        self.spool_endpoint = spool_endpoint.rstrip("/")
        self.spool_token_env = spool_token_env
        self.timeout_seconds = timeout_seconds
        self.max_delivery_attempts = max_delivery_attempts
        self.delivery_backoff_s = tuple(delivery_backoff_s)
        self.max_response_bytes = max_response_bytes
        self._transport = transport or self._urlopen
        self.fault_injector = fault_injector
        self.ledger = SQLiteF1CallLedger(ledger_path)
        self._call_lock_guard = threading.Lock()
        self._call_locks: dict[str, threading.RLock] = {}

    def _urlopen(self, request: urllib_request.Request, timeout: float) -> RawHTTPResponse:
        try:
            with urllib_request.urlopen(request, timeout=timeout) as response:
                return RawHTTPResponse(
                    status=int(response.status),
                    headers={key: value for key, value in response.headers.items()},
                    body=response.read(self.max_response_bytes + 1),
                )
        except urllib_error.HTTPError as error:
            return RawHTTPResponse(
                status=int(error.code),
                headers={key: value for key, value in error.headers.items()},
                body=error.read(self.max_response_bytes + 1),
            )

    def _fault(self, stage: str, call: ModelCallV1) -> None:
        if self.fault_injector is not None:
            self.fault_injector(stage, call)

    @staticmethod
    def _request_body(call: ModelCallV1) -> dict[str, object]:
        return {
            "model": call.model,
            "messages": [
                {"role": "system", "content": call.system_prompt},
                {"role": "user", "content": canonical_json(call.input_payload)},
            ],
            "temperature": 0,
            "top_p": 1,
            "max_tokens": call.max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": call.output_type,
                    "strict": True,
                    "schema": output_json_schema(call.output_type),
                },
            },
            "chat_template_kwargs": {"enable_thinking": False},
        }

    def _intent(
        self, call: ModelCallV1, request_bytes: bytes
    ) -> tuple[str, str, str, bytes]:
        route = f"{self.spool_endpoint}{SPOOL_ROUTE_PREFIX}{call.physical_call_id}"
        request_sha256 = _sha256_bytes(request_bytes)
        value = {
            "schema_version": DURABLE_CALL_SCHEMA,
            "spool_route": route,
            "call": asdict(call),
            "request_sha256": request_sha256,
            "output_schema_sha256": output_schema_sha256(call.output_type),
        }
        intent_bytes = _canonical_bytes(value)
        return route, request_sha256, _sha256_bytes(intent_bytes), intent_bytes

    @staticmethod
    def _spool_error_code(response: RawHTTPResponse) -> str:
        try:
            value = _strict_json(response.body, "spool error")
            if isinstance(value, dict) and isinstance(value.get("code"), str):
                return value["code"]
        except ProtocolRejected:
            pass
        return f"SPOOL_HTTP_{response.status}"

    def _verify_spool_response(
        self,
        response: RawHTTPResponse,
        *,
        call: ModelCallV1,
        intent_sha256: str,
        request_sha256: str,
    ) -> None:
        headers = {str(key).casefold(): str(value) for key, value in response.headers.items()}
        expected = {
            "x-hswm-spool-call-id": call.physical_call_id,
            "x-hswm-spool-intent-sha256": intent_sha256,
            "x-hswm-spool-request-sha256": request_sha256,
            "x-hswm-spool-response-sha256": _sha256_bytes(response.body),
            "x-hswm-spool-server-revision": call.model_revision,
        }
        for key, value in expected.items():
            if headers.get(key) != value:
                raise ProtocolRejected(f"result spool attestation mismatch: {key}")
        if headers.get("x-hswm-spool-replayed") not in {"true", "false"}:
            raise ProtocolRejected("result spool replay flag is missing")
        if len(response.body) > self.max_response_bytes:
            raise ProtocolRejected("model response exceeds configured byte limit")
        declared = headers.get("content-length")
        if declared is not None:
            try:
                expected_length = int(declared)
            except ValueError as error:
                raise ProtocolRejected("response Content-Length is invalid") from error
            if expected_length != len(response.body):
                raise ProtocolRejected("HTTP response framing is incomplete")

    def _parse_durable_raw(self, call: ModelCallV1) -> ModelResponseV1:
        status = self.ledger.status(call.physical_call_id)
        if status in {"SCHEMA_VALID", "ACCEPTED"}:
            return self.ledger.model_response(call.physical_call_id)
        raw = self.ledger.raw_response(call.physical_call_id)
        started = time.monotonic()
        try:
            if raw.status != 200:
                raise ProtocolRejected(f"model endpoint returned HTTP {raw.status}")
            envelope = _strict_json(raw.body, "OpenAI response envelope")
            if not isinstance(envelope, dict):
                raise ProtocolRejected("OpenAI response envelope must be an object")
            choices = envelope.get("choices")
            if not isinstance(choices, list) or len(choices) != 1:
                raise ProtocolRejected("OpenAI response must contain exactly one choice")
            choice = choices[0]
            if not isinstance(choice, dict):
                raise ProtocolRejected("OpenAI response choice must be an object")
            finish_reason = choice.get("finish_reason")
            if finish_reason != "stop":
                raise ProtocolRejected(f"model finish_reason is not stop: {finish_reason!r}")
            message = choice.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise ProtocolRejected("OpenAI response message content is invalid")
            served_model = envelope.get("model")
            if served_model != call.model:
                raise ProtocolRejected("served model identity drifted")
            usage = envelope.get("usage")
            if not isinstance(usage, dict):
                raise ProtocolRejected("OpenAI response usage is invalid")
            input_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens")
            if (
                isinstance(input_tokens, bool)
                or not isinstance(input_tokens, int)
                or input_tokens < 0
                or isinstance(output_tokens, bool)
                or not isinstance(output_tokens, int)
                or output_tokens < 0
            ):
                raise ProtocolRejected("OpenAI response token usage is invalid")
            if status == "RAW_COMPLETE":
                self.ledger.mark_envelope_valid(
                    call.physical_call_id,
                    finish_reason=finish_reason,
                    served_model=served_model,
                )
                self._fault("after_envelope", call)
            payload = _strict_json(message["content"], "model message content")
            if not isinstance(payload, dict):
                raise ProtocolRejected("model content must be one JSON object")
            normalized = validate_port(call.output_type, payload)
            response = ModelResponseV1(
                payload=normalized,
                model=call.model,
                model_revision=call.model_revision,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=max(0, int((time.monotonic() - started) * 1000)),
                cache_status="provider-unknown",
                retries=0,
            )
            if self.ledger.status(call.physical_call_id) == "ENVELOPE_VALID":
                self.ledger.mark_schema_valid(
                    call.physical_call_id, response, output_type=call.output_type
                )
                self._fault("after_schema", call)
            return self.ledger.model_response(call.physical_call_id)
        except ProtocolRejected as error:
            self.ledger.reject_protocol(call.physical_call_id, type(error).__name__)
            raise
        except Exception as error:
            self.ledger.reject_protocol(call.physical_call_id, type(error).__name__)
            raise ProtocolRejected(f"model response validation failed: {error}") from error

    def __call__(self, call: ModelCallV1) -> ModelResponseV1:
        with self._call_lock_guard:
            call_lock = self._call_locks.setdefault(
                call.physical_call_id, threading.RLock()
            )
        with call_lock:
            return self._execute_call(call)

    def _execute_call(self, call: ModelCallV1) -> ModelResponseV1:
        body = self._request_body(call)
        request_bytes = _canonical_bytes(body)
        route, request_sha256, intent_sha256, intent_bytes = self._intent(
            call, request_bytes
        )
        status = self.ledger.prepare(
            physical_call_id=call.physical_call_id,
            intent_sha256=intent_sha256,
            intent_bytes=intent_bytes,
            request_sha256=request_sha256,
            endpoint=route,
            request_bytes=request_bytes,
        )
        self._fault("after_prepare", call)
        if status == "ACCEPTED":
            return self.ledger.model_response(call.physical_call_id)
        if status == "REJECTED_PROTOCOL":
            raise ProtocolRejected("prior physical call was protocol-rejected")
        if status == "AMBIGUOUS_ABORT":
            raise AmbiguousModelOutcome("prior physical call ended with ambiguous outcome")
        if status in {"RAW_COMPLETE", "ENVELOPE_VALID", "SCHEMA_VALID"}:
            return self._parse_durable_raw(call)

        headers = {
            "Content-Type": "application/json",
            "X-HSWM-Intent-SHA256": intent_sha256,
            "X-HSWM-Model-Revision": call.model_revision,
        }
        if self.spool_token_env:
            spool_token = os.environ.get(self.spool_token_env)
            if not spool_token:
                raise DurableTransportError(
                    f"missing result-spool token environment: {self.spool_token_env}"
                )
            headers["Authorization"] = f"Bearer {spool_token}"

        last_error: BaseException | None = None
        for ordinal in range(1, self.max_delivery_attempts + 1):
            self.ledger.mark_sent(call.physical_call_id, ordinal)
            self._fault("after_sent", call)
            request = urllib_request.Request(
                route, data=request_bytes, headers=headers, method="PUT"
            )
            try:
                response = self._transport(request, self.timeout_seconds)
                if not isinstance(response, RawHTTPResponse):
                    raise DurableTransportError("transport must return RawHTTPResponse")
            except (
                urllib_error.URLError,
                TimeoutError,
                socket.timeout,
                OSError,
                http.client.IncompleteRead,
            ) as error:
                last_error = error
                self.ledger.mark_delivery_ambiguous(
                    call.physical_call_id, ordinal, type(error).__name__
                )
                if ordinal >= self.max_delivery_attempts:
                    self.ledger.ambiguous_abort(
                        call.physical_call_id, "SPOOL_RECONCILIATION_EXHAUSTED"
                    )
                    raise AmbiguousModelOutcome(
                        f"result-spool delivery remained ambiguous: {type(error).__name__}"
                    ) from error
                if self.delivery_backoff_s:
                    time.sleep(
                        self.delivery_backoff_s[
                            min(ordinal - 1, len(self.delivery_backoff_s) - 1)
                        ]
                    )
                continue
            if response.status == 425:
                code = self._spool_error_code(response)
                if code == "OUTCOME_PENDING":
                    self.ledger.mark_delivery_ambiguous(
                        call.physical_call_id, ordinal, code
                    )
                    if ordinal >= self.max_delivery_attempts:
                        self.ledger.ambiguous_abort(
                            call.physical_call_id, "SPOOL_RECONCILIATION_EXHAUSTED"
                        )
                        raise AmbiguousModelOutcome(
                            "result spool remained pending through the reconciliation budget"
                        )
                    if self.delivery_backoff_s:
                        time.sleep(
                            self.delivery_backoff_s[
                                min(ordinal - 1, len(self.delivery_backoff_s) - 1)
                            ]
                        )
                    continue
                self.ledger.ambiguous_abort(call.physical_call_id, code)
                raise AmbiguousModelOutcome(f"result spool refused recovery: {code}")
            if response.status == 409:
                code = self._spool_error_code(response)
                self.ledger.ambiguous_abort(call.physical_call_id, code)
                raise AmbiguousModelOutcome(f"result spool identity conflict: {code}")
            try:
                self._verify_spool_response(
                    response,
                    call=call,
                    intent_sha256=intent_sha256,
                    request_sha256=request_sha256,
                )
            except ProtocolRejected as error:
                self.ledger.store_raw(call.physical_call_id, response)
                self.ledger.reject_protocol(call.physical_call_id, "SPOOL_ATTESTATION_INVALID")
                raise
            self.ledger.store_raw(call.physical_call_id, response)
            self._fault("after_raw", call)
            return self._parse_durable_raw(call)
        raise AmbiguousModelOutcome(f"unreachable delivery exhaustion: {last_error}")

    def accept_call_receipt(self, receipt: CallReceiptV1) -> None:
        self.ledger.accept_call_receipt(receipt)

    def accept_item_run(self, value: Mapping[str, object]) -> None:
        self.ledger.accept_item_run(value)

    def audit(self) -> dict[str, object]:
        return self.ledger.audit()

    def close(self) -> None:
        self.ledger.close()

    def __enter__(self) -> "DurableSpoolJSONPort":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


__all__ = [
    "AmbiguousModelOutcome",
    "DURABLE_CALL_SCHEMA",
    "DurableIntentConflict",
    "DurableLedgerIntegrityError",
    "DurableSpoolJSONPort",
    "DurableTransportError",
    "ProtocolRejected",
    "SQLiteF1CallLedger",
]
