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
from urllib.parse import quote

from prom_search_hswm.hswm_call_receipt import (
    CallReceiptV1,
    FunctionCallError,
    ModelCallV1,
    ModelResponseV1,
    verify_call_receipt,
)
from prom_search_hswm.hswm_f1_sqlite_schema import (
    LEDGER_SCHEMA_SQL,
    LEDGER_USER_VERSION,
    SQLiteAuthorityRefusal,
    assert_database_generation,
    create_exclusive_main,
    database_generation,
    exact_schema_readback,
    integrity_readback,
    open_frozen_sqlite_read_only,
    open_private_parent,
    require_sqlite_family_absent,
    require_wal_full,
    verify_private_parent,
)
from prom_search_hswm.hswm_result_spool import (
    RawHTTPResponse,
    SPOOL_ROUTE_PREFIX,
    SpoolIntegrityError,
    validate_private_sqlite_family,
)
from prom_search_hswm.hswm_typed_ports import (
    canonical_json,
    canonical_sha256,
    output_json_schema,
    output_schema_sha256,
    validate_port,
)
from prom_search_hswm.prom9_f1_r8_private_output import (
    PrivateOutputRefusal,
    canonical_output_path,
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
_INTENT_FIELDS = {
    "schema_version",
    "spool_route",
    "call",
    "request_sha256",
    "output_schema_sha256",
}


def _configure_checkpoint_policy(
    connection: sqlite3.Connection, label: str
) -> bool:
    """Disable implicit checkpoints before the connection can commit.

    ``wal_autocheckpoint`` is available on every supported Python runtime.
    Python 3.12 additionally exposes SQLite's no-checkpoint-on-close setting;
    feature-detect it so the library remains importable on Python 3.11 while
    allowing the sealed runtime to require the stronger policy explicitly.
    """

    no_checkpoint_on_close = getattr(
        sqlite3, "SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE", None
    )
    setconfig = getattr(connection, "setconfig", None)
    getconfig = getattr(connection, "getconfig", None)
    checkpoint_on_close_disabled = False
    if (
        no_checkpoint_on_close is not None
        and callable(setconfig)
        and callable(getconfig)
    ):
        setconfig(no_checkpoint_on_close, True)
        if getconfig(no_checkpoint_on_close) is not True:
            raise SQLiteAuthorityRefusal(
                f"{label} checkpoint-on-close could not be disabled"
            )
        checkpoint_on_close_disabled = True

    connection.execute("PRAGMA wal_autocheckpoint=0")
    row = connection.execute("PRAGMA wal_autocheckpoint").fetchone()
    if row is None or int(row[0]) != 0:
        raise SQLiteAuthorityRefusal(
            f"{label} automatic WAL checkpointing is enabled"
        )
    return checkpoint_on_close_disabled


_MODEL_CALL_FIELDS = {
    "physical_call_id",
    "run_id",
    "arm_id",
    "item_id",
    "call_index",
    "function_id",
    "model",
    "model_revision",
    "system_prompt",
    "input_type",
    "input_payload",
    "output_type",
    "max_output_tokens",
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


def _logical_call_slot(
    intent_bytes: bytes,
    *,
    expected_physical_call_id: str,
    label: str,
) -> tuple[str, str, str, int]:
    """Strictly recover the one logical execution slot bound by an intent."""

    value = _strict_json(intent_bytes, label)
    if (
        not isinstance(value, dict)
        or set(value) != _INTENT_FIELDS
        or value.get("schema_version") != DURABLE_CALL_SCHEMA
        or not isinstance(value.get("call"), dict)
        or set(value["call"]) != _MODEL_CALL_FIELDS
    ):
        raise DurableLedgerIntegrityError(f"{label} schema drifted")
    call = value["call"]
    physical_call_id = call.get("physical_call_id")
    if (
        physical_call_id != expected_physical_call_id
        or not isinstance(physical_call_id, str)
        or _SHA256.fullmatch(physical_call_id) is None
    ):
        raise DurableLedgerIntegrityError(f"{label} physical identity drifted")
    logical_values = (call.get("run_id"), call.get("arm_id"), call.get("item_id"))
    if any(not isinstance(item, str) or not item for item in logical_values):
        raise DurableLedgerIntegrityError(f"{label} logical identity drifted")
    call_index = call.get("call_index")
    if type(call_index) is not int or call_index not in {1, 2, 3}:
        raise DurableLedgerIntegrityError(f"{label} call index drifted")
    return (*logical_values, call_index)


class SQLiteF1CallLedger:
    """Append-audited projection store for calls and completed item-arms."""

    def __init__(self, path: str | Path) -> None:
        try:
            self.path = canonical_output_path(Path(path))
        except PrivateOutputRefusal as error:
            raise DurableLedgerIntegrityError(
                "F1 ledger path is not canonical"
            ) from error
        self._lock = threading.RLock()
        self._parent_fd = -1
        connection: sqlite3.Connection | None = None
        try:
            self._parent_fd = open_private_parent(self.path, "F1 call ledger")
            try:
                self.path.lstat()
                existed = True
            except FileNotFoundError:
                existed = False
            except OSError as error:
                raise SQLiteAuthorityRefusal(
                    "cannot stat F1 ledger path"
                ) from error

            frozen_generation: dict[str, object] | None = None
            if existed:
                frozen_store = open_frozen_sqlite_read_only(
                    self.path, "F1 call ledger"
                )
                frozen_generation = dict(frozen_store.generation)
                with frozen_store as frozen:
                    exact_schema_readback(frozen, "attempt", "F1 call ledger")
                    integrity_readback(frozen, "F1 call ledger")
                    require_wal_full(frozen, "F1 call ledger")
                    self._audit_connection(frozen)
            else:
                require_sqlite_family_absent(self.path, "F1 call ledger")
                create_exclusive_main(
                    self.path, self._parent_fd, "F1 call ledger"
                )

            verify_private_parent(self.path, self._parent_fd, "F1 call ledger")
            uri = f"file:{quote(str(self.path), safe='/')}?mode=rw"
            connection = sqlite3.connect(
                uri,
                uri=True,
                isolation_level=None,
                timeout=10.0,
                check_same_thread=False,
            )
            checkpoint_on_close_disabled = _configure_checkpoint_policy(
                connection, "F1 call ledger"
            )
            # No mutating PRAGMA or DDL precedes these namespace/generation checks.
            verify_private_parent(self.path, self._parent_fd, "F1 call ledger")
            if frozen_generation is not None:
                assert_database_generation(
                    self.path, "F1 call ledger", frozen_generation
                )
            connection.row_factory = sqlite3.Row

            if existed:
                exact_schema_readback(connection, "attempt", "F1 call ledger")
                integrity_readback(connection, "F1 call ledger")
                require_wal_full(connection, "F1 call ledger")
                self._audit_connection(connection)
                live_generation = database_generation(self.path, "F1 call ledger")
                expected_wal = frozen_generation.get("wal")
                observed_wal = live_generation.get("wal")
                wal_is_unchanged_or_empty_audit_sidecar = (
                    observed_wal == expected_wal
                    or (
                        expected_wal is None
                        and isinstance(observed_wal, Mapping)
                        and observed_wal.get("st_size") == 0
                        and observed_wal.get("sha256") == hashlib.sha256(b"").hexdigest()
                    )
                )
                if (
                    live_generation.get("main")
                    != frozen_generation.get("main")
                    or not wal_is_unchanged_or_empty_audit_sidecar
                    or live_generation.get("journal") is not None
                ):
                    raise SQLiteAuthorityRefusal(
                        "F1 call ledger changed during live pre-write audit"
                    )
                verify_private_parent(
                    self.path, self._parent_fd, "F1 call ledger"
                )
                connection.execute("PRAGMA busy_timeout=10000")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("PRAGMA foreign_keys=ON")
            else:
                connection.execute("PRAGMA busy_timeout=10000")
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("PRAGMA foreign_keys=ON")
                connection.executescript(LEDGER_SCHEMA_SQL)
                connection.execute(f"PRAGMA user_version={LEDGER_USER_VERSION}")
                exact_schema_readback(connection, "attempt", "F1 call ledger")
                integrity_readback(connection, "F1 call ledger")
                require_wal_full(connection, "F1 call ledger")
                self._audit_connection(connection)

            try:
                validate_private_sqlite_family(self.path, "F1 call ledger")
            except SpoolIntegrityError as error:
                raise SQLiteAuthorityRefusal(str(error)) from error
            verify_private_parent(self.path, self._parent_fd, "F1 call ledger")
            os.fsync(self._parent_fd)
        except (SQLiteAuthorityRefusal, sqlite3.Error) as error:
            if connection is not None:
                connection.close()
            if self._parent_fd >= 0:
                os.close(self._parent_fd)
                self._parent_fd = -1
            raise DurableLedgerIntegrityError(str(error)) from error
        except DurableLedgerIntegrityError:
            if connection is not None:
                connection.close()
            if self._parent_fd >= 0:
                os.close(self._parent_fd)
                self._parent_fd = -1
            raise
        except Exception as error:
            if connection is not None:
                connection.close()
            if self._parent_fd >= 0:
                os.close(self._parent_fd)
                self._parent_fd = -1
            raise DurableLedgerIntegrityError(
                "F1 call ledger failed its pre-write logical audit"
            ) from error
        except BaseException:
            if connection is not None:
                connection.close()
            if self._parent_fd >= 0:
                os.close(self._parent_fd)
                self._parent_fd = -1
            raise
        self._connection = connection
        self._checkpoint_on_close_disabled = checkpoint_on_close_disabled

    @classmethod
    def _audit_connection(cls, connection: sqlite3.Connection) -> dict[str, object]:
        probe = object.__new__(cls)
        probe._connection = connection
        probe._lock = threading.RLock()
        probe._parent_fd = -1
        return probe.audit()

    @property
    def journal_mode(self) -> str:
        return str(self._connection.execute("PRAGMA journal_mode").fetchone()[0]).casefold()

    @property
    def synchronous(self) -> int:
        return int(self._connection.execute("PRAGMA synchronous").fetchone()[0])

    @property
    def wal_autocheckpoint(self) -> int:
        row = self._connection.execute("PRAGMA wal_autocheckpoint").fetchone()
        if row is None:
            raise DurableLedgerIntegrityError(
                "F1 call ledger WAL auto-checkpoint policy disappeared"
            )
        return int(row[0])

    @property
    def checkpoint_on_close_disabled(self) -> bool:
        return self._checkpoint_on_close_disabled

    @staticmethod
    def _verify_call_row(row: sqlite3.Row) -> None:
        intent_bytes = bytes(row["intent_bytes"])
        if _sha256_bytes(intent_bytes) != row["intent_sha256"]:
            raise DurableLedgerIntegrityError("stored F1 intent bytes drifted")
        intent_value = _strict_json(intent_bytes, "stored F1 intent")
        if not isinstance(intent_value, dict) or _canonical_bytes(intent_value) != intent_bytes:
            raise DurableLedgerIntegrityError("stored F1 intent is not canonical")
        _logical_call_slot(
            intent_bytes,
            expected_physical_call_id=str(row["physical_call_id"]),
            label="stored F1 intent",
        )
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
        intent_value = _strict_json(intent_bytes, "new F1 intent")
        if not isinstance(intent_value, dict) or _canonical_bytes(intent_value) != intent_bytes:
            raise DurableTransportError("new F1 intent is not canonical")
        logical_slot = _logical_call_slot(
            intent_bytes,
            expected_physical_call_id=physical_call_id,
            label="new F1 intent",
        )
        _require_sha256(request_sha256, "request_sha256")
        if _sha256_bytes(request_bytes) != request_sha256:
            raise DurableTransportError("request_sha256 does not match request bytes")
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                row = None
                seen_slots: dict[tuple[str, str, str, int], str] = {}
                for existing in self._connection.execute(
                    "SELECT * FROM call_state ORDER BY physical_call_id"
                ).fetchall():
                    self._verify_call_row(existing)
                    existing_slot = _logical_call_slot(
                        bytes(existing["intent_bytes"]),
                        expected_physical_call_id=str(existing["physical_call_id"]),
                        label="stored F1 intent",
                    )
                    prior_physical_id = seen_slots.get(existing_slot)
                    if (
                        prior_physical_id is not None
                        and prior_physical_id != str(existing["physical_call_id"])
                    ):
                        raise DurableLedgerIntegrityError(
                            "F1 ledger repeats a logical call slot"
                        )
                    seen_slots[existing_slot] = str(existing["physical_call_id"])
                    if str(existing["physical_call_id"]) == physical_call_id:
                        row = existing
                    elif existing_slot == logical_slot:
                        raise DurableIntentConflict(
                            "logical call slot already has a different physical_call_id"
                        )
                if row is not None:
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

    def reserve_next_delivery(
        self, physical_call_id: str, *, max_delivery_attempts: int
    ) -> int | None:
        """Persist the next lifetime delivery ordinal, or exhaust atomically."""

        if (
            isinstance(max_delivery_attempts, bool)
            or not isinstance(max_delivery_attempts, int)
            or max_delivery_attempts < 1
        ):
            raise DurableTransportError("max_delivery_attempts must be positive")
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self.verify_event_chain()
                row = self._connection.execute(
                    "SELECT * FROM call_state WHERE physical_call_id=?",
                    (physical_call_id,),
                ).fetchone()
                if row is None:
                    raise DurableLedgerIntegrityError(
                        "delivery reservation target is absent"
                    )
                self._verify_call_row(row)
                current = str(row["status"])
                if current not in _EVENT_TRANSITIONS["SENT"]:
                    raise DurableLedgerIntegrityError(
                        f"invalid F1 delivery reservation from {current}"
                    )
                sent_rows = self._connection.execute(
                    """
                    SELECT * FROM attempt_events
                    WHERE physical_call_id=? AND event_type='SENT'
                    ORDER BY sequence
                    """,
                    (physical_call_id,),
                ).fetchall()
                for expected_ordinal, event_row in enumerate(sent_rows, start=1):
                    raw = bytes(event_row["event_bytes"])
                    value = _strict_json(raw, "stored F1 SENT event")
                    detail = value.get("detail") if isinstance(value, dict) else None
                    if (
                        not isinstance(value, dict)
                        or _canonical_bytes(value) != raw
                        or _sha256_bytes(raw) != event_row["event_sha256"]
                        or value.get("physical_call_id") != physical_call_id
                        or value.get("event_type") != "SENT"
                        or not isinstance(detail, dict)
                        or set(detail)
                        != {"delivery_ordinal", "same_inference_identity"}
                        or detail.get("delivery_ordinal") != expected_ordinal
                        or detail.get("same_inference_identity") is not True
                    ):
                        raise DurableLedgerIntegrityError(
                            "stored F1 delivery ordinals drifted"
                        )
                used = len(sent_rows)
                if used > max_delivery_attempts:
                    raise DurableLedgerIntegrityError(
                        "stored F1 deliveries exceed the configured lifetime budget"
                    )
                if used == max_delivery_attempts:
                    code = "SPOOL_RECONCILIATION_EXHAUSTED"
                    self._connection.execute(
                        "UPDATE call_state SET status='AMBIGUOUS_ABORT', terminal_code=? "
                        "WHERE physical_call_id=?",
                        (code, physical_call_id),
                    )
                    self._append_event_tx(
                        physical_call_id, "AMBIGUOUS_ABORT", {"code": code}
                    )
                    self._connection.execute("COMMIT")
                    return None
                ordinal = used + 1
                self._connection.execute(
                    "UPDATE call_state SET status='SENT' WHERE physical_call_id=?",
                    (physical_call_id,),
                )
                self._append_event_tx(
                    physical_call_id,
                    "SENT",
                    {
                        "delivery_ordinal": ordinal,
                        "same_inference_identity": True,
                    },
                )
                self._connection.execute("COMMIT")
                return ordinal
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

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
            logical_slots: set[tuple[str, str, str, int]] = set()
            for row in rows:
                self._verify_accepted_row_binding(row)
                logical_slot = _logical_call_slot(
                    bytes(row["intent_bytes"]),
                    expected_physical_call_id=str(row["physical_call_id"]),
                    label="stored F1 intent",
                )
                if logical_slot in logical_slots:
                    raise DurableLedgerIntegrityError(
                        "F1 ledger repeats a logical call slot"
                    )
                logical_slots.add(logical_slot)
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
            try:
                self._connection.close()
            finally:
                if self._parent_fd >= 0:
                    os.close(self._parent_fd)
                    self._parent_fd = -1


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

        while True:
            ordinal = self.ledger.reserve_next_delivery(
                call.physical_call_id,
                max_delivery_attempts=self.max_delivery_attempts,
            )
            if ordinal is None:
                raise AmbiguousModelOutcome(
                    "result-spool reconciliation lifetime budget was already exhausted"
                )
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
