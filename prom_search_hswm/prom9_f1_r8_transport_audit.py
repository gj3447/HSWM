#!/usr/bin/env python3
"""Read-only SQLite exporter for HSWM F1 r8 transport evidence.

Both databases are opened through SQLite ``mode=ro`` URIs.  ``genesis``
freezes an empty WAL database pair before any model call.  Each read-only audit
connection configures its own connection-local ``synchronous=FULL`` setting;
that readback does not purport to recover the closed writer's setting.  Writer
FULL evidence belongs to the live ledger/spool audit receipts.  ``terminal``
then proves that the same device/inode pair contains only fully accepted calls
and fully completed spool results, and exports every durable byte preimage.

This module never opens gold, invokes a model, or mutates either database.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote

from prom_search_hswm.hswm_f1_durable_transport import (
    DURABLE_CALL_SCHEMA,
    SQLiteF1CallLedger,
)
from prom_search_hswm.hswm_function_network import verify_run
from prom_search_hswm.hswm_result_spool import SQLiteResultSpool
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256


GENESIS_SCHEMA = "hswm-prom9-f1-r8-transport-genesis/v1"
TRANSPORT_BINDINGS_SCHEMA = "hswm-prom9-f1-r8-transport-bindings/v1"
_EXPECTED_USER_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EVENT_GENESIS = "0" * 64

_ATTEMPT_COLUMNS = {
    "call_state": [
        "physical_call_id",
        "intent_sha256",
        "intent_bytes",
        "request_sha256",
        "endpoint",
        "request_bytes",
        "status",
        "response_status",
        "response_headers",
        "response_body",
        "response_sha256",
        "model_response",
        "model_response_sha256",
        "call_receipt",
        "call_receipt_sha256",
        "terminal_code",
    ],
    "item_runs": [
        "run_id",
        "arm_id",
        "item_id",
        "run_receipt_sha256",
        "item_run_bytes",
    ],
    "attempt_events": [
        "sequence",
        "physical_call_id",
        "event_type",
        "event_bytes",
        "previous_event_sha256",
        "event_sha256",
    ],
}

_SPOOL_COLUMNS = {
    "spool_calls": [
        "physical_call_id",
        "intent_sha256",
        "request_sha256",
        "request_bytes",
        "status",
        "response_status",
        "response_headers",
        "response_body",
        "response_sha256",
        "error_class",
    ]
}

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

_GENESIS_FIELDS = {
    "schema_version",
    "run_id",
    "attempt_integrity",
    "spool_integrity",
    "attempt_journal_mode",
    "attempt_audit_connection_synchronous",
    "spool_journal_mode",
    "spool_audit_connection_synchronous",
    "attempt_user_version",
    "spool_user_version",
    "attempt_schema_sha256",
    "spool_schema_sha256",
    "attempt_db_identity",
    "spool_db_identity",
    "call_count",
    "item_run_count",
    "attempt_event_count",
    "spool_call_count",
    "genesis_sha256",
}


class TransportAuditRefusal(RuntimeError):
    """The database pair cannot support an r8 transport claim."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise TransportAuditRefusal(f"{label} must be a lowercase SHA-256")
    return value


def _require_nonempty(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TransportAuditRefusal(f"{label} must be non-empty text")
    return value


def _require_count(value: object, label: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        qualifier = "non-negative" if allow_zero else "positive"
        raise TransportAuditRefusal(f"{label} must be a {qualifier} integer")
    return value


def _blob(value: object, label: str) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise TransportAuditRefusal(f"{label} is not a SQLite BLOB")
    return bytes(value)


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


class _DuplicateKey(ValueError):
    pass


def _strict_json(raw: bytes | str, label: str) -> Any:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise _DuplicateKey(key)
            result[key] = value
        return result

    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        return json.loads(
            text,
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite constant {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKey, ValueError) as error:
        raise TransportAuditRefusal(f"{label} is not strict JSON: {error}") from error


def _strict_object(raw: bytes | str, label: str) -> dict[str, object]:
    value = _strict_json(raw, label)
    if not isinstance(value, dict):
        raise TransportAuditRefusal(f"{label} must be a JSON object")
    return value


def _read_object(path: Path, label: str) -> dict[str, object]:
    try:
        raw = Path(path).read_bytes()
    except OSError as error:
        raise TransportAuditRefusal(f"cannot read {label}: {error}") from error
    return _strict_object(raw, label)


def _database_identity(path: Path, label: str) -> dict[str, object]:
    try:
        resolved = Path(path).resolve(strict=True)
        info = resolved.stat()
    except OSError as error:
        raise TransportAuditRefusal(f"cannot stat {label}: {error}") from error
    if not resolved.is_file():
        raise TransportAuditRefusal(f"{label} is not a regular file: {resolved}")
    return {
        "resolved_path": str(resolved),
        "st_dev": int(info.st_dev),
        "st_ino": int(info.st_ino),
    }


def _open_read_only(path: Path, label: str) -> sqlite3.Connection:
    resolved = Path(path).resolve(strict=True)
    uri = f"file:{quote(str(resolved), safe='/')}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        # SQLite synchronous is connection-scoped and cannot be recovered from
        # a closed writer.  Configure this read-only audit connection to FULL
        # before its snapshot and report precisely that readback.  The runner's
        # live ledger/spool audit receipts are the writer-setting evidence.
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN")
    except (OSError, sqlite3.Error) as error:
        try:
            connection.close()
        except UnboundLocalError:
            pass
        raise TransportAuditRefusal(f"cannot open {label} read-only: {error}") from error
    return connection


def _schema_readback(
    connection: sqlite3.Connection,
    expected: Mapping[str, list[str]],
    label: str,
) -> tuple[int, str]:
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if tables != set(expected):
        raise TransportAuditRefusal(f"{label} table set drifted")
    observed: dict[str, list[str]] = {}
    for table, columns in expected.items():
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        observed[table] = [str(row[1]) for row in rows]
        if observed[table] != columns:
            raise TransportAuditRefusal(f"{label} columns drifted for {table}")
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version != _EXPECTED_USER_VERSION:
        raise TransportAuditRefusal(
            f"{label} user_version is {version}, expected {_EXPECTED_USER_VERSION}"
        )
    return version, canonical_sha256({"user_version": version, "tables": observed})


def _integrity_readback(connection: sqlite3.Connection, label: str) -> str:
    values = [str(row[0]) for row in connection.execute("PRAGMA integrity_check")]
    if values != ["ok"]:
        raise TransportAuditRefusal(f"{label} integrity_check failed")
    return values[0]


def _durability_readback(
    connection: sqlite3.Connection, label: str
) -> tuple[str, str]:
    journal = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).casefold()
    synchronous = str(connection.execute("PRAGMA synchronous").fetchone()[0])
    if journal != "wal" or synchronous != "2":
        raise TransportAuditRefusal(f"{label} is not WAL/FULL")
    return journal, synchronous


def _count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _same_database_pair(
    attempt_identity: Mapping[str, object], spool_identity: Mapping[str, object]
) -> None:
    attempt_key = (attempt_identity.get("st_dev"), attempt_identity.get("st_ino"))
    spool_key = (spool_identity.get("st_dev"), spool_identity.get("st_ino"))
    if attempt_key == spool_key:
        raise TransportAuditRefusal("attempt ledger and result spool are the same inode")


def _self_hash(value: Mapping[str, object], field: str, label: str) -> str:
    unsigned = dict(value)
    declared = unsigned.pop(field, None)
    if not isinstance(declared, str) or canonical_sha256(unsigned) != declared:
        raise TransportAuditRefusal(f"{label} self-hash drifted")
    return declared


def _verify_genesis(
    value: Mapping[str, object],
    *,
    run_id: str,
    attempt_identity: Mapping[str, object],
    spool_identity: Mapping[str, object],
) -> str:
    if (
        set(value) != _GENESIS_FIELDS
        or value.get("schema_version") != GENESIS_SCHEMA
        or value.get("run_id") != run_id
    ):
        raise TransportAuditRefusal("transport genesis schema or run identity drifted")
    declared = _self_hash(value, "genesis_sha256", "transport genesis")
    if (
        value.get("attempt_integrity") != "ok"
        or value.get("spool_integrity") != "ok"
        or str(value.get("attempt_journal_mode")).casefold() != "wal"
        or str(value.get("spool_journal_mode")).casefold() != "wal"
        or str(value.get("attempt_audit_connection_synchronous")) != "2"
        or str(value.get("spool_audit_connection_synchronous")) != "2"
        or value.get("attempt_user_version") != _EXPECTED_USER_VERSION
        or value.get("spool_user_version") != _EXPECTED_USER_VERSION
        or any(
            value.get(field) != 0
            for field in (
                "call_count",
                "item_run_count",
                "attempt_event_count",
                "spool_call_count",
            )
        )
    ):
        raise TransportAuditRefusal(
            "transport genesis is not empty WAL with FULL read-only audit connections"
        )
    if (
        value.get("attempt_db_identity") != dict(attempt_identity)
        or value.get("spool_db_identity") != dict(spool_identity)
    ):
        raise TransportAuditRefusal("transport database device/inode changed since genesis")
    _require_sha256(value.get("attempt_schema_sha256"), "genesis attempt schema")
    _require_sha256(value.get("spool_schema_sha256"), "genesis spool schema")
    return declared


def export_genesis(
    *, run_id: str, attempt_db: Path, spool_db: Path
) -> dict[str, object]:
    """Export a self-hashed receipt for an empty, immutable-identity DB pair."""

    run_id = _require_nonempty(run_id, "run_id")
    attempt_identity = _database_identity(attempt_db, "attempt ledger")
    spool_identity = _database_identity(spool_db, "result spool")
    _same_database_pair(attempt_identity, spool_identity)
    attempt = _open_read_only(attempt_db, "attempt ledger")
    spool = _open_read_only(spool_db, "result spool")
    try:
        attempt_integrity = _integrity_readback(attempt, "attempt ledger")
        spool_integrity = _integrity_readback(spool, "result spool")
        attempt_journal, attempt_sync = _durability_readback(attempt, "attempt ledger")
        spool_journal, spool_sync = _durability_readback(spool, "result spool")
        attempt_version, attempt_schema = _schema_readback(
            attempt, _ATTEMPT_COLUMNS, "attempt ledger"
        )
        spool_version, spool_schema = _schema_readback(
            spool, _SPOOL_COLUMNS, "result spool"
        )
        counts = {
            "call_count": _count(attempt, "call_state"),
            "item_run_count": _count(attempt, "item_runs"),
            "attempt_event_count": _count(attempt, "attempt_events"),
            "spool_call_count": _count(spool, "spool_calls"),
        }
        if any(counts.values()):
            raise TransportAuditRefusal("genesis export requires two logically empty databases")
    finally:
        attempt.close()
        spool.close()
    if (
        attempt_identity != _database_identity(attempt_db, "attempt ledger")
        or spool_identity != _database_identity(spool_db, "result spool")
    ):
        raise TransportAuditRefusal("transport database identity changed during genesis export")
    unsigned = {
        "schema_version": GENESIS_SCHEMA,
        "run_id": run_id,
        "attempt_integrity": attempt_integrity,
        "spool_integrity": spool_integrity,
        "attempt_journal_mode": attempt_journal,
        "attempt_audit_connection_synchronous": attempt_sync,
        "spool_journal_mode": spool_journal,
        "spool_audit_connection_synchronous": spool_sync,
        "attempt_user_version": attempt_version,
        "spool_user_version": spool_version,
        "attempt_schema_sha256": attempt_schema,
        "spool_schema_sha256": spool_schema,
        "attempt_db_identity": attempt_identity,
        "spool_db_identity": spool_identity,
        **counts,
    }
    return {**unsigned, "genesis_sha256": canonical_sha256(unsigned)}


def _accepted_projection(row: sqlite3.Row) -> dict[str, object]:
    return {
        "physical_call_id": str(row["physical_call_id"]),
        "intent_sha256": str(row["intent_sha256"]),
        "request_sha256": str(row["request_sha256"]),
        "response_sha256": str(row["response_sha256"]),
        "call_receipt_sha256": str(row["call_receipt_sha256"]),
    }


def _export_accepted_call(
    row: sqlite3.Row, *, run_id: str
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    try:
        SQLiteF1CallLedger._verify_accepted_row_binding(row)
    except Exception as error:
        raise TransportAuditRefusal("accepted call failed durable binding validation") from error
    physical_call_id = _require_sha256(row["physical_call_id"], "physical_call_id")
    for field in (
        "intent_sha256",
        "request_sha256",
        "response_sha256",
        "model_response_sha256",
        "call_receipt_sha256",
    ):
        _require_sha256(row[field], f"accepted {field}")
    intent = _blob(row["intent_bytes"], "accepted intent_bytes")
    request = _blob(row["request_bytes"], "accepted request_bytes")
    response_headers = _blob(row["response_headers"], "accepted response_headers")
    response_body = _blob(row["response_body"], "accepted response_body")
    model_response = _blob(row["model_response"], "accepted model_response")
    call_receipt = _blob(row["call_receipt"], "accepted call_receipt")
    intent_value = _strict_object(intent, "accepted intent")
    receipt_value = _strict_object(call_receipt, "accepted call receipt")
    call_value = intent_value.get("call")
    if (
        not isinstance(call_value, dict)
        or intent_value.get("schema_version") != DURABLE_CALL_SCHEMA
        or intent_value.get("spool_route") != row["endpoint"]
        or intent_value.get("request_sha256") != row["request_sha256"]
        or call_value.get("physical_call_id") != physical_call_id
        or call_value.get("run_id") != run_id
        or receipt_value.get("physical_call_id") != physical_call_id
        or receipt_value.get("run_id") != run_id
    ):
        raise TransportAuditRefusal("accepted call run or physical identity drifted")
    expected_physical_call_id = canonical_sha256(
        {
            "run_id": receipt_value.get("run_id"),
            "arm_id": receipt_value.get("arm_id"),
            "item_id": receipt_value.get("item_id"),
            "call_index": receipt_value.get("call_index"),
            "function_id": receipt_value.get("function_id"),
            "registry_prompt_sha256": receipt_value.get("prompt_sha256"),
            "input_port_sha256": receipt_value.get("input_port_sha256"),
        }
    )
    if physical_call_id != expected_physical_call_id:
        raise TransportAuditRefusal("accepted physical_call_id preimage drifted")
    if row["status"] != "ACCEPTED" or row["terminal_code"] is not None:
        raise TransportAuditRefusal("terminal call-state row is not cleanly ACCEPTED")
    response_status = row["response_status"]
    if response_status != 200:
        raise TransportAuditRefusal("accepted response_status is not HTTP 200")

    canonical = _accepted_projection(row)
    enriched = {
        "physical_call_id": physical_call_id,
        "intent_sha256": str(row["intent_sha256"]),
        "request_sha256": str(row["request_sha256"]),
        "response_sha256": str(row["response_sha256"]),
        "model_response_sha256": str(row["model_response_sha256"]),
        "call_receipt_sha256": str(row["call_receipt_sha256"]),
        "response_status": response_status,
        "intent_bytes_b64": _b64(intent),
        "request_bytes_b64": _b64(request),
        "response_body_b64": _b64(response_body),
        "model_response_bytes_b64": _b64(model_response),
    }
    auxiliary = {
        "physical_call_id": physical_call_id,
        "endpoint": str(row["endpoint"]),
        "response_headers_sha256": _sha256_bytes(response_headers),
        "response_headers_b64": _b64(response_headers),
        "call_receipt_bytes_sha256": _sha256_bytes(call_receipt),
        "call_receipt_bytes_b64": _b64(call_receipt),
    }
    return canonical, enriched, auxiliary


def _export_spool_call(
    row: sqlite3.Row,
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        SQLiteResultSpool._verify_row(row)
    except Exception as error:
        raise TransportAuditRefusal("spool call failed durable binding validation") from error
    physical_call_id = _require_sha256(row["physical_call_id"], "spool physical_call_id")
    for field in ("intent_sha256", "request_sha256", "response_sha256"):
        _require_sha256(row[field], f"spool {field}")
    if row["status"] != "COMPLETE" or row["error_class"] is not None:
        raise TransportAuditRefusal("result spool contains UNKNOWN or incomplete outcomes")
    response_status = row["response_status"]
    if response_status != 200:
        raise TransportAuditRefusal("spool response_status is not HTTP 200")
    request = _blob(row["request_bytes"], "spool request_bytes")
    headers = _blob(row["response_headers"], "spool response_headers")
    body = _blob(row["response_body"], "spool response_body")
    binding = {
        "physical_call_id": physical_call_id,
        "intent_sha256": str(row["intent_sha256"]),
        "request_sha256": str(row["request_sha256"]),
        "response_sha256": str(row["response_sha256"]),
    }
    preimage = {
        **binding,
        "status": "COMPLETE",
        "response_status": response_status,
        "request_bytes_b64": _b64(request),
        "response_headers_sha256": _sha256_bytes(headers),
        "response_headers_b64": _b64(headers),
        "response_body_b64": _b64(body),
        "error_class": None,
    }
    return binding, preimage


def _export_event_chain(
    rows: Sequence[sqlite3.Row], accepted_ids: set[str]
) -> tuple[list[dict[str, object]], str]:
    previous = _EVENT_GENESIS
    local_states: dict[str, str | None] = {}
    exported: list[dict[str, object]] = []
    for expected_sequence, row in enumerate(rows):
        sequence = row["sequence"]
        physical_call_id = str(row["physical_call_id"])
        event_type = str(row["event_type"])
        event_bytes = _blob(row["event_bytes"], "attempt event_bytes")
        event_sha = _require_sha256(row["event_sha256"], "attempt event_sha256")
        row_previous = _require_sha256(
            row["previous_event_sha256"], "attempt previous_event_sha256"
        )
        value = _strict_object(event_bytes, "attempt event")
        if (
            sequence != expected_sequence
            or physical_call_id not in accepted_ids
            or row_previous != previous
            or _sha256_bytes(event_bytes) != event_sha
            or canonical_json(value).encode("utf-8") != event_bytes
            or set(value)
            != {
                "schema_version",
                "sequence",
                "physical_call_id",
                "event_type",
                "detail",
                "previous_event_sha256",
            }
            or value.get("schema_version") != DURABLE_CALL_SCHEMA
            or value.get("sequence") != sequence
            or value.get("physical_call_id") != physical_call_id
            or value.get("event_type") != event_type
            or value.get("previous_event_sha256") != previous
            or not isinstance(value.get("detail"), dict)
        ):
            raise TransportAuditRefusal("attempt event chain bytes or identity drifted")
        allowed_previous = _EVENT_TRANSITIONS.get(event_type)
        local_previous = local_states.get(physical_call_id)
        if allowed_previous is None or local_previous not in allowed_previous:
            raise TransportAuditRefusal("attempt event transition drifted")
        local_states[physical_call_id] = event_type
        exported.append(
            {
                "sequence": sequence,
                "physical_call_id": physical_call_id,
                "event_type": event_type,
                "previous_event_sha256": previous,
                "event_sha256": event_sha,
                "event_bytes_b64": _b64(event_bytes),
            }
        )
        previous = event_sha
    if set(local_states) != accepted_ids or any(
        state != "ACCEPTED" for state in local_states.values()
    ):
        raise TransportAuditRefusal("accepted call set differs from terminal event tails")
    return exported, previous


def _export_item_runs(
    rows: Sequence[sqlite3.Row],
    *,
    run_id: str,
    accepted_receipts: Mapping[str, bytes],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    bindings: list[dict[str, object]] = []
    preimages: list[dict[str, object]] = []
    covered: list[str] = []
    for row in rows:
        raw = _blob(row["item_run_bytes"], "item-run bytes")
        value = _strict_object(raw, "item-run receipt")
        if canonical_json(value).encode("utf-8") != raw:
            raise TransportAuditRefusal("item-run receipt is not canonical JSON")
        identity = {
            "run_id": str(row["run_id"]),
            "arm_id": str(row["arm_id"]),
            "item_id": str(row["item_id"]),
            "run_receipt_sha256": str(row["run_receipt_sha256"]),
        }
        if (
            identity["run_id"] != run_id
            or value.get("run_id") != identity["run_id"]
            or value.get("arm_id") != identity["arm_id"]
            or value.get("item_id") != identity["item_id"]
        ):
            raise TransportAuditRefusal("item-run row identity drifted")
        calls = value.get("calls")
        if not isinstance(calls, list) or len(calls) != 3:
            raise TransportAuditRefusal("item-run must contain exactly three calls")
        for call in calls:
            if not isinstance(call, dict):
                raise TransportAuditRefusal("item-run call is not an object")
            if (
                call.get("run_id") != identity["run_id"]
                or call.get("arm_id") != identity["arm_id"]
                or call.get("item_id") != identity["item_id"]
            ):
                raise TransportAuditRefusal("item-run call identity drifted")
        if value.get("answer") != calls[2].get("output_payload"):
            raise TransportAuditRefusal(
                "item-run answer differs from the third call output"
            )
        total_fields = (
            ("total_input_tokens", "input_tokens"),
            ("total_output_tokens", "output_tokens"),
            ("total_allowed_output_tokens", "allowed_output_tokens"),
        )
        for total_field, call_field in total_fields:
            declared_total = _require_count(
                value.get(total_field), total_field, allow_zero=True
            )
            observed_total = sum(
                _require_count(call.get(call_field), call_field, allow_zero=True)
                for call in calls
            )
            if declared_total != observed_total:
                raise TransportAuditRefusal(
                    f"item-run {total_field} differs from call receipts"
                )
        try:
            receipt_sha = verify_run(value)
        except Exception as error:
            raise TransportAuditRefusal("item-run receipt failed validation") from error
        if receipt_sha != identity["run_receipt_sha256"]:
            raise TransportAuditRefusal("item-run receipt hash drifted")
        for call in calls:
            physical_call_id = str(call.get("physical_call_id"))
            accepted_raw = accepted_receipts.get(physical_call_id)
            if accepted_raw is None or canonical_json(call).encode("utf-8") != accepted_raw:
                raise TransportAuditRefusal(
                    "item-run call differs from its accepted receipt preimage"
                )
            covered.append(physical_call_id)
        bindings.append(identity)
        preimages.append(
            {
                **identity,
                "item_run_bytes_sha256": _sha256_bytes(raw),
                "item_run_bytes_b64": _b64(raw),
            }
        )
    if len(covered) != len(set(covered)) or set(covered) != set(accepted_receipts):
        raise TransportAuditRefusal(
            "item-run receipts do not cover every accepted physical call exactly once"
        )
    return bindings, preimages


def export_terminal_bindings(
    *,
    run_id: str,
    genesis_receipt: Mapping[str, object],
    attempt_db: Path,
    spool_db: Path,
    expected_calls: int,
    expected_item_runs: int,
    expected_attempt_events: int | None = None,
) -> dict[str, object]:
    """Export terminal byte bindings from the frozen read-only DB pair."""

    run_id = _require_nonempty(run_id, "run_id")
    expected_calls = _require_count(expected_calls, "expected_calls")
    expected_item_runs = _require_count(expected_item_runs, "expected_item_runs")
    if expected_calls != expected_item_runs * 3:
        raise TransportAuditRefusal("F1 terminal counts require exactly three calls per item-run")
    if expected_attempt_events is not None:
        expected_attempt_events = _require_count(
            expected_attempt_events, "expected_attempt_events"
        )
    attempt_identity = _database_identity(attempt_db, "attempt ledger")
    spool_identity = _database_identity(spool_db, "result spool")
    _same_database_pair(attempt_identity, spool_identity)
    genesis_sha = _verify_genesis(
        genesis_receipt,
        run_id=run_id,
        attempt_identity=attempt_identity,
        spool_identity=spool_identity,
    )

    attempt = _open_read_only(attempt_db, "attempt ledger")
    spool = _open_read_only(spool_db, "result spool")
    try:
        attempt_integrity = _integrity_readback(attempt, "attempt ledger")
        spool_integrity = _integrity_readback(spool, "result spool")
        attempt_journal, attempt_sync = _durability_readback(attempt, "attempt ledger")
        spool_journal, spool_sync = _durability_readback(spool, "result spool")
        attempt_version, attempt_schema = _schema_readback(
            attempt, _ATTEMPT_COLUMNS, "attempt ledger"
        )
        spool_version, spool_schema = _schema_readback(
            spool, _SPOOL_COLUMNS, "result spool"
        )
        if (
            attempt_version != genesis_receipt.get("attempt_user_version")
            or spool_version != genesis_receipt.get("spool_user_version")
            or attempt_schema != genesis_receipt.get("attempt_schema_sha256")
            or spool_schema != genesis_receipt.get("spool_schema_sha256")
            or attempt_journal != genesis_receipt.get("attempt_journal_mode")
            or spool_journal != genesis_receipt.get("spool_journal_mode")
            or attempt_sync
            != str(genesis_receipt.get("attempt_audit_connection_synchronous"))
            or spool_sync
            != str(genesis_receipt.get("spool_audit_connection_synchronous"))
        ):
            raise TransportAuditRefusal("terminal schema or durability differs from genesis")

        call_rows = attempt.execute(
            "SELECT * FROM call_state ORDER BY physical_call_id"
        ).fetchall()
        item_rows = attempt.execute(
            "SELECT * FROM item_runs ORDER BY run_id,arm_id,item_id"
        ).fetchall()
        event_rows = attempt.execute(
            "SELECT * FROM attempt_events ORDER BY sequence"
        ).fetchall()
        spool_rows = spool.execute(
            "SELECT * FROM spool_calls ORDER BY physical_call_id"
        ).fetchall()
        if (
            len(call_rows) != expected_calls
            or len(spool_rows) != expected_calls
            or len(item_rows) != expected_item_runs
            or (
                expected_attempt_events is not None
                and len(event_rows) != expected_attempt_events
            )
        ):
            raise TransportAuditRefusal("terminal SQLite counts differ from frozen expectations")

        call_statuses = Counter(str(row["status"]) for row in call_rows)
        spool_statuses = Counter(str(row["status"]) for row in spool_rows)
        if call_statuses != Counter({"ACCEPTED": expected_calls}):
            raise TransportAuditRefusal("attempt ledger contains non-ACCEPTED calls")
        if spool_statuses != Counter({"COMPLETE": expected_calls}):
            raise TransportAuditRefusal("result spool contains UNKNOWN or incomplete outcomes")

        canonical_accepted: list[dict[str, object]] = []
        accepted_calls: list[dict[str, object]] = []
        accepted_auxiliary: list[dict[str, object]] = []
        accepted_receipts: dict[str, bytes] = {}
        for row in call_rows:
            canonical, enriched, auxiliary = _export_accepted_call(row, run_id=run_id)
            physical_call_id = str(row["physical_call_id"])
            canonical_accepted.append(canonical)
            accepted_calls.append(enriched)
            accepted_auxiliary.append(auxiliary)
            accepted_receipts[physical_call_id] = _blob(
                row["call_receipt"], "accepted call_receipt"
            )

        spool_bindings: list[dict[str, object]] = []
        spool_preimages: list[dict[str, object]] = []
        spool_rows_by_id: dict[str, sqlite3.Row] = {}
        for row in spool_rows:
            binding, preimage = _export_spool_call(row)
            physical_call_id = str(row["physical_call_id"])
            spool_bindings.append(binding)
            spool_preimages.append(preimage)
            spool_rows_by_id[physical_call_id] = row

        accepted_rows_by_id = {str(row["physical_call_id"]): row for row in call_rows}
        if set(accepted_rows_by_id) != set(spool_rows_by_id):
            raise TransportAuditRefusal("attempt/spool physical-call ID sets conflict")
        for physical_call_id, accepted_row in accepted_rows_by_id.items():
            spool_row = spool_rows_by_id[physical_call_id]
            if (
                accepted_row["intent_sha256"] != spool_row["intent_sha256"]
                or accepted_row["request_sha256"] != spool_row["request_sha256"]
                or accepted_row["response_sha256"] != spool_row["response_sha256"]
                or accepted_row["response_status"] != spool_row["response_status"]
                or _blob(accepted_row["request_bytes"], "accepted request")
                != _blob(spool_row["request_bytes"], "spool request")
                or _blob(accepted_row["response_body"], "accepted response")
                != _blob(spool_row["response_body"], "spool response")
            ):
                raise TransportAuditRefusal(
                    "attempt/spool identity or byte preimage conflict"
                )

        events, event_tip = _export_event_chain(
            event_rows, set(accepted_rows_by_id)
        )
        item_bindings, item_preimages = _export_item_runs(
            item_rows,
            run_id=run_id,
            accepted_receipts=accepted_receipts,
        )
    finally:
        attempt.close()
        spool.close()

    if (
        attempt_identity != _database_identity(attempt_db, "attempt ledger")
        or spool_identity != _database_identity(spool_db, "result spool")
    ):
        raise TransportAuditRefusal("transport database identity changed during terminal export")

    unsigned = {
        "schema_version": TRANSPORT_BINDINGS_SCHEMA,
        "run_id": run_id,
        "db_genesis_sha256": genesis_sha,
        "attempt_integrity": attempt_integrity,
        "spool_integrity": spool_integrity,
        "attempt_journal_mode": attempt_journal,
        "attempt_audit_connection_synchronous": attempt_sync,
        "spool_journal_mode": spool_journal,
        "spool_audit_connection_synchronous": spool_sync,
        "attempt_user_version": attempt_version,
        "spool_user_version": spool_version,
        "attempt_schema_sha256": attempt_schema,
        "spool_schema_sha256": spool_schema,
        "attempt_db_identity": attempt_identity,
        "spool_db_identity": spool_identity,
        "call_count": len(accepted_calls),
        "item_run_count": len(item_bindings),
        "attempt_event_count": len(events),
        "spool_call_count": len(spool_bindings),
        "attempt_status_counts": {"ACCEPTED": len(accepted_calls)},
        "spool_status_counts": {"COMPLETE": len(spool_bindings)},
        "spool_unknown_count": 0,
        "identity_conflict_count": 0,
        "event_chain_tip_sha256": event_tip,
        "accepted_call_root_sha256": canonical_sha256(canonical_accepted),
        "accepted_call_export_root_sha256": canonical_sha256(accepted_calls),
        "accepted_call_auxiliary_root_sha256": canonical_sha256(accepted_auxiliary),
        "spool_binding_root_sha256": canonical_sha256(spool_bindings),
        "spool_preimage_root_sha256": canonical_sha256(spool_preimages),
        "item_run_root_sha256": canonical_sha256(item_bindings),
        "item_run_preimage_root_sha256": canonical_sha256(item_preimages),
        "attempt_event_root_sha256": canonical_sha256(events),
        "accepted_calls": accepted_calls,
        "accepted_call_auxiliary_preimages": accepted_auxiliary,
        "spool_bindings": spool_bindings,
        "spool_call_preimages": spool_preimages,
        "item_run_bindings": item_bindings,
        "item_run_preimages": item_preimages,
        "attempt_events": events,
    }
    return {**unsigned, "bindings_sha256": canonical_sha256(unsigned)}


# Concise alias for callers that model the two exporter phases symmetrically.
export_terminal = export_terminal_bindings


def write_private_once(path: Path, value: Mapping[str, object]) -> None:
    """Durably create a mode-0600 JSON artifact without replacing a prior one."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    temporary = destination.with_name(f".{destination.name}.partial-{os.getpid()}")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise TransportAuditRefusal(
            f"stale partial output requires inspection: {temporary}"
        ) from error
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as error:
            raise TransportAuditRefusal(f"refusing to replace output: {destination}") from error
        directory = os.open(str(destination.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    genesis = subparsers.add_parser("genesis")
    genesis.add_argument("--run-id", required=True)
    genesis.add_argument("--attempt-db", type=Path, required=True)
    genesis.add_argument("--spool-db", type=Path, required=True)
    genesis.add_argument("--output", type=Path, required=True)
    terminal = subparsers.add_parser("terminal")
    terminal.add_argument("--run-id", required=True)
    terminal.add_argument("--genesis-receipt", type=Path, required=True)
    terminal.add_argument("--attempt-db", type=Path, required=True)
    terminal.add_argument("--spool-db", type=Path, required=True)
    terminal.add_argument("--expected-calls", type=int, required=True)
    terminal.add_argument("--expected-item-runs", type=int, required=True)
    terminal.add_argument("--expected-attempt-events", type=int)
    terminal.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "genesis":
            result = export_genesis(
                run_id=args.run_id,
                attempt_db=args.attempt_db,
                spool_db=args.spool_db,
            )
            status = "EMPTY_TRANSPORT_GENESIS_EXPORTED"
            digest_field = "genesis_sha256"
        elif args.command == "terminal":
            result = export_terminal_bindings(
                run_id=args.run_id,
                genesis_receipt=_read_object(
                    args.genesis_receipt, "transport genesis receipt"
                ),
                attempt_db=args.attempt_db,
                spool_db=args.spool_db,
                expected_calls=args.expected_calls,
                expected_item_runs=args.expected_item_runs,
                expected_attempt_events=args.expected_attempt_events,
            )
            status = "TERMINAL_TRANSPORT_BINDINGS_EXPORTED"
            digest_field = "bindings_sha256"
        else:  # pragma: no cover - argparse constrains this branch.
            raise TransportAuditRefusal("unsupported transport audit command")
        write_private_once(args.output, result)
    except Exception:
        print(json.dumps({"status": "REFUSED"}), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {"status": status, digest_field: result[digest_field]}, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "GENESIS_SCHEMA",
    "TRANSPORT_BINDINGS_SCHEMA",
    "TransportAuditRefusal",
    "export_genesis",
    "export_terminal",
    "export_terminal_bindings",
    "main",
    "write_private_once",
]
