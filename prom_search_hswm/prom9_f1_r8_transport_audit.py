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
import stat
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any
from urllib.parse import quote

from prom_search_hswm.hswm_f1_durable_transport import (
    DURABLE_CALL_SCHEMA,
    LEDGER_SCHEMA_SQL,
    LEDGER_USER_VERSION,
    SQLiteF1CallLedger,
)
from prom_search_hswm.hswm_function_network import verify_run
from prom_search_hswm.hswm_result_spool import (
    SPOOL_SCHEMA,
    SPOOL_SCHEMA_SQL,
    SPOOL_USER_VERSION,
    SQLiteResultSpool,
)
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.hswm_typed_ports import output_schema_sha256
from prom_search_hswm.prom9_f1_r8_private_output import (
    PrivateOutputRefusal,
    canonical_existing_private_path,
)


GENESIS_SCHEMA = "hswm-prom9-f1-r8-transport-genesis/v1"
RESUME_PREFIX_SCHEMA = "hswm-prom9-f1-r8-resume-prefix/v1"
TRANSPORT_BINDINGS_SCHEMA = "hswm-prom9-f1-r8-transport-bindings/v1"
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


def _strict_private_file(
    path: Path, label: str
) -> tuple[Path, os.stat_result]:
    try:
        target = canonical_existing_private_path(Path(path), label)
    except PrivateOutputRefusal as error:
        raise TransportAuditRefusal(f"{label} ancestry is unsafe") from error
    try:
        before = target.lstat()
        resolved = target.resolve(strict=True)
    except OSError as error:
        raise TransportAuditRefusal(f"cannot stat {label}: {error}") from error
    if resolved != target:
        raise TransportAuditRefusal(f"{label} ancestry may not traverse symlinks")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = -1
    try:
        descriptor = os.open(target, flags)
        opened = os.fstat(descriptor)
        after = target.lstat()
    except OSError as error:
        raise TransportAuditRefusal(f"cannot open {label}: {error}") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    identity = (before.st_dev, before.st_ino)
    observations = (before, opened, after)
    if (
        any(
            stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
            for info in observations
        )
        or any((info.st_dev, info.st_ino) != identity for info in observations)
        or any(info.st_uid != os.geteuid() for info in observations)
        or any(info.st_nlink != 1 for info in observations)
        or any(stat.S_IMODE(info.st_mode) != 0o600 for info in observations)
    ):
        raise TransportAuditRefusal(
            f"{label} must be one owner-private unique regular file"
        )
    return resolved, after


def private_database_identity(path: Path, label: str) -> dict[str, object]:
    resolved, info = _strict_private_file(path, label)
    return {
        "resolved_path": str(resolved),
        "st_dev": int(info.st_dev),
        "st_ino": int(info.st_ino),
    }


def _database_identity(path: Path, label: str) -> dict[str, object]:
    return private_database_identity(path, label)


def _file_generation(
    path: Path, label: str, *, required: bool
) -> dict[str, object] | None:
    try:
        before_path = path.lstat()
    except FileNotFoundError:
        if required:
            raise TransportAuditRefusal(f"{label} disappeared")
        return None
    except OSError as error:
        raise TransportAuditRefusal(f"cannot stat {label}: {error}") from error
    if (
        stat.S_ISLNK(before_path.st_mode)
        or not stat.S_ISREG(before_path.st_mode)
        or before_path.st_uid != os.geteuid()
        or before_path.st_nlink != 1
        or stat.S_IMODE(before_path.st_mode) != 0o600
    ):
        raise TransportAuditRefusal(f"{label} is not a unique regular file")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
        try:
            before_fd = os.fstat(descriptor)
            digest = hashlib.sha256()
            while block := os.read(descriptor, 1024 * 1024):
                digest.update(block)
            after_fd = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        after_path = path.lstat()
    except OSError as error:
        raise TransportAuditRefusal(f"cannot capture {label}: {error}") from error
    identity = (before_path.st_dev, before_path.st_ino)
    if (
        identity != (before_fd.st_dev, before_fd.st_ino)
        or identity != (after_fd.st_dev, after_fd.st_ino)
        or identity != (after_path.st_dev, after_path.st_ino)
        or before_path.st_nlink != 1
        or before_fd.st_nlink != 1
        or after_fd.st_nlink != 1
        or after_path.st_nlink != 1
        or any(
            info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            for info in (before_path, before_fd, after_fd, after_path)
        )
        or before_fd.st_size != after_fd.st_size
        or before_fd.st_mtime_ns != after_fd.st_mtime_ns
        or before_fd.st_ctime_ns != after_fd.st_ctime_ns
    ):
        raise TransportAuditRefusal(f"{label} changed during generation capture")
    return {
        "st_dev": int(after_fd.st_dev),
        "st_ino": int(after_fd.st_ino),
        "st_size": int(after_fd.st_size),
        "st_mtime_ns": int(after_fd.st_mtime_ns),
        "st_ctime_ns": int(after_fd.st_ctime_ns),
        "sha256": digest.hexdigest(),
    }


def _database_generation(path: Path, label: str) -> dict[str, object]:
    identity = private_database_identity(path, label)
    resolved = Path(str(identity["resolved_path"]))
    # SQLite's shared-memory sidecar is not evidence content, but it is still
    # part of the private authority boundary.  Validate it on every before/after
    # generation pass so a public, linked, or swapped SHM inode cannot be
    # touched by the read-only audit connection.
    return {
        "main": _file_generation(resolved, label, required=True),
        "wal": _file_generation(
            Path(f"{resolved}-wal"), f"{label} WAL", required=False
        ),
        "shm": _file_generation(
            Path(f"{resolved}-shm"), f"{label} SHM", required=False
        ),
    }


def _copy_generation_member(
    source: Path,
    destination: Path,
    expected: object,
    label: str,
    *,
    required: bool,
) -> None:
    if expected is None:
        if required:
            raise TransportAuditRefusal(f"{label} generation is absent")
        try:
            source.lstat()
        except FileNotFoundError:
            return
        except OSError as error:
            raise TransportAuditRefusal(f"cannot stat {label}: {error}") from error
        raise TransportAuditRefusal(f"{label} appeared after generation freeze")
    if not isinstance(expected, Mapping):
        raise TransportAuditRefusal(f"{label} generation is malformed")
    try:
        before_path = source.lstat()
    except OSError as error:
        raise TransportAuditRefusal(f"cannot stat {label}: {error}") from error
    source_fd = -1
    destination_fd = -1
    digest = hashlib.sha256()
    try:
        source_fd = os.open(
            source,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        before_fd = os.fstat(source_fd)
        destination_fd = os.open(
            destination,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        os.fchmod(destination_fd, 0o600)
        while block := os.read(source_fd, 1024 * 1024):
            digest.update(block)
            offset = 0
            while offset < len(block):
                written = os.write(destination_fd, block[offset:])
                if written <= 0:
                    raise TransportAuditRefusal(
                        f"{label} snapshot copy made no progress"
                    )
                offset += written
        os.fsync(destination_fd)
        after_fd = os.fstat(source_fd)
        after_path = source.lstat()
    except (OSError, TransportAuditRefusal) as error:
        if isinstance(error, TransportAuditRefusal):
            raise
        raise TransportAuditRefusal(f"cannot snapshot {label}: {error}") from error
    finally:
        if destination_fd >= 0:
            os.close(destination_fd)
        if source_fd >= 0:
            os.close(source_fd)
    observations = (before_path, before_fd, after_fd, after_path)
    expected_identity = (expected.get("st_dev"), expected.get("st_ino"))
    if (
        any(
            stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
            for info in observations
        )
        or any(
            (info.st_dev, info.st_ino) != expected_identity
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
            for info in observations
        )
        or after_fd.st_size != expected.get("st_size")
        or after_fd.st_mtime_ns != expected.get("st_mtime_ns")
        or after_fd.st_ctime_ns != expected.get("st_ctime_ns")
        or digest.hexdigest() != expected.get("sha256")
    ):
        raise TransportAuditRefusal(f"{label} differs from its frozen generation")


class FrozenSQLiteReadOnly:
    """SQLite connection over a private byte snapshot of one frozen source."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        temporary: tempfile.TemporaryDirectory,
        source: Path,
        label: str,
        generation: Mapping[str, object],
    ) -> None:
        self._connection: sqlite3.Connection | None = connection
        self._temporary: tempfile.TemporaryDirectory | None = temporary
        self._source = Path(source)
        self._label = label
        self._generation = dict(generation)

    def execute(self, *args: object, **kwargs: object) -> sqlite3.Cursor:
        if self._connection is None:
            raise TransportAuditRefusal("frozen SQLite audit connection is closed")
        return self._connection.execute(*args, **kwargs)

    def close(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.close()
        finally:
            self._connection = None
            if self._temporary is not None:
                self._temporary.cleanup()
                self._temporary = None
        if _database_generation(self._source, self._label) != self._generation:
            raise TransportAuditRefusal(
                f"{self._label} generation changed during frozen audit"
            )


def _open_read_only(
    path: Path, label: str, generation: Mapping[str, object]
) -> FrozenSQLiteReadOnly:
    identity = private_database_identity(path, label)
    resolved = Path(str(identity["resolved_path"]))
    temporary = tempfile.TemporaryDirectory(prefix="hswm-f1-sqlite-audit-")
    snapshot = Path(temporary.name) / "database.sqlite3"
    try:
        _copy_generation_member(
            resolved, snapshot, generation.get("main"), label, required=True
        )
        _copy_generation_member(
            Path(f"{resolved}-wal"),
            Path(f"{snapshot}-wal"),
            generation.get("wal"),
            f"{label} WAL",
            required=False,
        )
    except BaseException:
        temporary.cleanup()
        raise
    connection: sqlite3.Connection | None = None
    uri = f"file:{quote(str(snapshot), safe='/')}?mode=rw"
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
            if connection is not None:
                connection.close()
        except sqlite3.Error:
            pass
        temporary.cleanup()
        raise TransportAuditRefusal(f"cannot open {label} read-only: {error}") from error
    if (
        private_database_identity(path, label) != identity
        or _database_generation(path, label) != dict(generation)
    ):
        connection.close()
        temporary.cleanup()
        raise TransportAuditRefusal(f"{label} identity changed while opening")
    return FrozenSQLiteReadOnly(
        connection, temporary, Path(path), label, generation
    )


def open_frozen_sqlite_read_only(
    path: Path, label: str
) -> FrozenSQLiteReadOnly:
    """Open a stable private snapshot while generation-checking the source."""

    generation = _database_generation(path, label)
    return _open_read_only(path, label, generation)


def _schema_payload(
    connection: sqlite3.Connection,
    expected: Mapping[str, list[str]],
    label: str,
) -> dict[str, object]:
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
    table_metadata: dict[str, object] = {}
    for table, columns in expected.items():
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        observed[table] = [str(row[1]) for row in rows]
        if observed[table] != columns:
            raise TransportAuditRefusal(f"{label} columns drifted for {table}")
        indexes = connection.execute(f"PRAGMA index_list({table})").fetchall()
        table_metadata[table] = {
            "columns": [list(row) for row in rows],
            "indexes": [
                {
                    "index_list": list(index),
                    "index_info": [
                        list(value)
                        for value in connection.execute(
                            f"PRAGMA index_info({json.dumps(str(index[1]))})"
                        ).fetchall()
                    ],
                }
                for index in indexes
            ],
            "foreign_keys": [
                list(row)
                for row in connection.execute(
                    f"PRAGMA foreign_key_list({table})"
                ).fetchall()
            ],
        }
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    sqlite_master = [
        {
            "type": str(row[0]),
            "name": str(row[1]),
            "tbl_name": str(row[2]),
            "sql": None if row[3] is None else str(row[3]),
        }
        for row in connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name,tbl_name"
        ).fetchall()
    ]
    if any(
        entry["type"] in {"trigger", "view"}
        or (entry["type"] == "index" and entry["sql"] is not None)
        or entry["type"] not in {"table", "index"}
        for entry in sqlite_master
    ):
        raise TransportAuditRefusal(
            f"{label} contains executable or explicit schema objects"
        )
    return {
        "user_version": version,
        "tables": observed,
        "table_metadata": table_metadata,
        "sqlite_master": sqlite_master,
    }


def _schema_authority(
    authority: str,
) -> tuple[str, int, Mapping[str, list[str]]]:
    if authority == "attempt":
        return LEDGER_SCHEMA_SQL, LEDGER_USER_VERSION, _ATTEMPT_COLUMNS
    if authority == "spool":
        return SPOOL_SCHEMA_SQL, SPOOL_USER_VERSION, _SPOOL_COLUMNS
    raise TransportAuditRefusal(f"unknown SQLite schema authority {authority}")


@lru_cache(maxsize=2)
def _canonical_schema_payload(authority: str) -> dict[str, object]:
    schema_sql, user_version, columns = _schema_authority(authority)
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(schema_sql)
        connection.execute(f"PRAGMA user_version={user_version}")
        return _schema_payload(connection, columns, f"canonical {authority} schema")
    finally:
        connection.close()


def exact_schema_readback(
    connection: sqlite3.Connection,
    authority: str,
    label: str,
) -> tuple[int, str]:
    """Require byte-independent logical DDL equality to the runtime authority."""

    _schema_sql, expected_version, columns = _schema_authority(authority)
    observed = _schema_payload(connection, columns, label)
    version = int(observed["user_version"])
    if version != expected_version:
        raise TransportAuditRefusal(
            f"{label} user_version is {version}, expected {expected_version}"
        )
    if observed != _canonical_schema_payload(authority):
        raise TransportAuditRefusal(f"{label} canonical schema drifted")
    return version, canonical_sha256(observed)


def canonical_schema_sha256(authority: str) -> str:
    _schema_authority(authority)
    return canonical_sha256(_canonical_schema_payload(authority))


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
    count_fields = (
        "call_count",
        "item_run_count",
        "attempt_event_count",
        "spool_call_count",
    )
    if (
        value.get("attempt_integrity") != "ok"
        or value.get("spool_integrity") != "ok"
        or not isinstance(value.get("attempt_journal_mode"), str)
        or not isinstance(value.get("spool_journal_mode"), str)
        or str(value.get("attempt_journal_mode")).casefold() != "wal"
        or str(value.get("spool_journal_mode")).casefold() != "wal"
        or value.get("attempt_audit_connection_synchronous") != "2"
        or value.get("spool_audit_connection_synchronous") != "2"
        or type(value.get("attempt_user_version")) is not int
        or type(value.get("spool_user_version")) is not int
            or value.get("attempt_user_version") != LEDGER_USER_VERSION
            or value.get("spool_user_version") != SPOOL_USER_VERSION
        or any(
            type(value.get(field)) is not int or value.get(field) != 0
            for field in count_fields
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
    attempt_generation = _database_generation(attempt_db, "attempt ledger")
    spool_generation = _database_generation(spool_db, "result spool")
    attempt = _open_read_only(
        attempt_db, "attempt ledger", attempt_generation
    )
    spool = _open_read_only(spool_db, "result spool", spool_generation)
    try:
        attempt_integrity = _integrity_readback(attempt, "attempt ledger")
        spool_integrity = _integrity_readback(spool, "result spool")
        attempt_journal, attempt_sync = _durability_readback(attempt, "attempt ledger")
        spool_journal, spool_sync = _durability_readback(spool, "result spool")
        attempt_version, attempt_schema = exact_schema_readback(
            attempt, "attempt", "attempt ledger"
        )
        spool_version, spool_schema = exact_schema_readback(
            spool, "spool", "result spool"
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
    post_attempt_identity = _database_identity(attempt_db, "attempt ledger")
    post_spool_identity = _database_identity(spool_db, "result spool")
    if attempt_identity != post_attempt_identity or spool_identity != post_spool_identity:
        raise TransportAuditRefusal("transport database identity changed during genesis export")
    if (
        attempt_generation != _database_generation(attempt_db, "attempt ledger")
        or spool_generation != _database_generation(spool_db, "result spool")
    ):
        raise TransportAuditRefusal(
            "transport database generation changed during genesis export"
        )
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


def _validate_accepted_event_detail(
    *,
    event_type: str,
    detail: Mapping[str, object],
    row: sqlite3.Row,
    receipt: Mapping[str, object],
    last_delivery_ordinal: int | None,
) -> int | None:
    if event_type == "PREPARED":
        expected = {
            "intent_sha256": str(row["intent_sha256"]),
            "request_sha256": str(row["request_sha256"]),
        }
    elif event_type == "SENT":
        ordinal = detail.get("delivery_ordinal")
        next_ordinal = 1 if last_delivery_ordinal is None else last_delivery_ordinal + 1
        if (
            type(ordinal) is not int
            or ordinal != next_ordinal
            or detail.get("same_inference_identity") is not True
            or set(detail) != {"delivery_ordinal", "same_inference_identity"}
        ):
            raise TransportAuditRefusal("attempt SENT event detail drifted")
        return ordinal
    elif event_type == "DELIVERY_AMBIGUOUS":
        ordinal = detail.get("delivery_ordinal")
        if (
            type(ordinal) is not int
            or ordinal != last_delivery_ordinal
            or not isinstance(detail.get("error_class"), str)
            or not str(detail.get("error_class"))
            or set(detail) != {"delivery_ordinal", "error_class"}
        ):
            raise TransportAuditRefusal(
                "attempt DELIVERY_AMBIGUOUS event detail drifted"
            )
        return last_delivery_ordinal
    elif event_type == "RAW_COMPLETE":
        response = _blob(row["response_body"], "accepted response body")
        expected = {
            "http_status": row["response_status"],
            "response_sha256": str(row["response_sha256"]),
            "response_bytes": len(response),
        }
    elif event_type == "ENVELOPE_VALID":
        expected = {
            "finish_reason": "stop",
            "served_model": receipt.get("model"),
        }
    elif event_type == "SCHEMA_VALID":
        output_type = receipt.get("output_type")
        if not isinstance(output_type, str) or not output_type:
            raise TransportAuditRefusal("accepted call output type is invalid")
        expected = {
            "output_type": output_type,
            "output_schema_sha256": output_schema_sha256(output_type),
            "model_response_sha256": str(row["model_response_sha256"]),
        }
    elif event_type == "ACCEPTED":
        expected = {
            "call_receipt_sha256": str(row["call_receipt_sha256"]),
        }
    else:
        raise TransportAuditRefusal(
            "accepted call event history contains a non-resumable event"
        )
    if dict(detail) != expected:
        raise TransportAuditRefusal(f"attempt {event_type} event detail drifted")
    return last_delivery_ordinal


def _export_event_chain(
    rows: Sequence[sqlite3.Row], accepted_rows: Mapping[str, sqlite3.Row]
) -> tuple[list[dict[str, object]], str]:
    previous = _EVENT_GENESIS
    local_states: dict[str, str | None] = {}
    delivery_ordinals: dict[str, int | None] = {}
    receipts = {
        physical_id: _strict_object(
            _blob(row["call_receipt"], "accepted call receipt"),
            "accepted call receipt",
        )
        for physical_id, row in accepted_rows.items()
    }
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
            type(sequence) is not int
            or sequence != expected_sequence
            or physical_call_id not in accepted_rows
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
            or type(value.get("sequence")) is not int
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
        detail = value["detail"]
        assert isinstance(detail, Mapping)
        delivery_ordinals[physical_call_id] = _validate_accepted_event_detail(
            event_type=event_type,
            detail=detail,
            row=accepted_rows[physical_call_id],
            receipt=receipts[physical_call_id],
            last_delivery_ordinal=delivery_ordinals.get(physical_call_id),
        )
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
    if set(local_states) != set(accepted_rows) or any(
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


def export_resume_prefix(
    *,
    run_id: str,
    genesis_receipt: Mapping[str, object],
    attempt_db: Path,
    spool_db: Path,
    ordered_jobs: Sequence[tuple[str, str]],
    max_workers: int,
) -> dict[str, object]:
    """Export a content-blind, clean ACCEPTED prefix for safe restart.

    Only call-level prefixes with matching COMPLETE spool rows are resumable.
    Rejected, ambiguous, raw-only, foreign, gapped, or scheduler-impossible
    histories refuse before any caller can resume model traffic.
    """

    run_id = _require_nonempty(run_id, "run_id")
    if (
        isinstance(max_workers, bool)
        or not isinstance(max_workers, int)
        or not 1 <= max_workers <= 8
    ):
        raise TransportAuditRefusal("max_workers must be in [1,8]")
    jobs: list[tuple[str, str]] = []
    for raw in ordered_jobs:
        if (
            not isinstance(raw, tuple)
            or len(raw) != 2
            or any(not isinstance(value, str) or not value for value in raw)
        ):
            raise TransportAuditRefusal("ordered resume job identity is malformed")
        jobs.append(raw)
    if not jobs or len(set(jobs)) != len(jobs):
        raise TransportAuditRefusal("ordered resume jobs must be nonempty and unique")
    job_ordinal = {job: index for index, job in enumerate(jobs)}
    ordered_job_value = [
        {"item_id": item_id, "arm_id": arm_id}
        for item_id, arm_id in jobs
    ]

    attempt_identity = _database_identity(attempt_db, "attempt ledger")
    spool_identity = _database_identity(spool_db, "result spool")
    _same_database_pair(attempt_identity, spool_identity)
    genesis_sha = _verify_genesis(
        genesis_receipt,
        run_id=run_id,
        attempt_identity=attempt_identity,
        spool_identity=spool_identity,
    )
    attempt_generation = _database_generation(attempt_db, "attempt ledger")
    spool_generation = _database_generation(spool_db, "result spool")
    attempt = _open_read_only(
        attempt_db, "attempt ledger", attempt_generation
    )
    spool = _open_read_only(spool_db, "result spool", spool_generation)
    try:
        attempt_integrity = _integrity_readback(attempt, "attempt ledger")
        spool_integrity = _integrity_readback(spool, "result spool")
        attempt_journal, attempt_sync = _durability_readback(
            attempt, "attempt ledger"
        )
        spool_journal, spool_sync = _durability_readback(spool, "result spool")
        attempt_version, attempt_schema = exact_schema_readback(
            attempt, "attempt", "attempt ledger"
        )
        spool_version, spool_schema = exact_schema_readback(
            spool, "spool", "result spool"
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
            raise TransportAuditRefusal(
                "resume prefix schema or durability differs from genesis"
            )

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
        if any(str(row["status"]) != "ACCEPTED" for row in call_rows):
            raise TransportAuditRefusal(
                "resume prefix contains a non-ACCEPTED call"
            )
        if any(str(row["status"]) != "COMPLETE" for row in spool_rows):
            raise TransportAuditRefusal(
                "resume prefix contains UNKNOWN or incomplete spool outcomes"
            )

        canonical_accepted: list[dict[str, object]] = []
        accepted_receipts: dict[str, bytes] = {}
        positions: dict[tuple[str, str], list[int]] = {}
        for row in call_rows:
            canonical, _enriched, _auxiliary = _export_accepted_call(
                row, run_id=run_id
            )
            receipt_raw = _blob(row["call_receipt"], "resume call receipt")
            receipt = _strict_object(receipt_raw, "resume call receipt")
            job = (str(receipt.get("item_id")), str(receipt.get("arm_id")))
            call_index = receipt.get("call_index")
            if (
                job not in job_ordinal
                or isinstance(call_index, bool)
                or not isinstance(call_index, int)
                or call_index not in {1, 2, 3}
            ):
                raise TransportAuditRefusal(
                    "resume prefix contains a foreign call identity"
                )
            values = positions.setdefault(job, [])
            if call_index in values:
                raise TransportAuditRefusal(
                    "resume prefix repeats a call position"
                )
            values.append(call_index)
            physical_id = str(row["physical_call_id"])
            canonical_accepted.append(canonical)
            accepted_receipts[physical_id] = receipt_raw

        spool_bindings: list[dict[str, object]] = []
        spool_rows_by_id: dict[str, sqlite3.Row] = {}
        for row in spool_rows:
            binding, _preimage = _export_spool_call(row)
            physical_id = str(row["physical_call_id"])
            spool_bindings.append(binding)
            spool_rows_by_id[physical_id] = row
        accepted_rows_by_id = {
            str(row["physical_call_id"]): row for row in call_rows
        }
        if set(accepted_rows_by_id) != set(spool_rows_by_id):
            raise TransportAuditRefusal(
                "resume prefix attempt/spool physical-call sets conflict"
            )
        for physical_id, accepted_row in accepted_rows_by_id.items():
            spool_row = spool_rows_by_id[physical_id]
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
                    "resume prefix attempt/spool byte preimages conflict"
                )

        if call_rows:
            events, event_tip = _export_event_chain(
                event_rows, accepted_rows_by_id
            )
        else:
            if event_rows:
                raise TransportAuditRefusal(
                    "zero-call resume prefix contains attempt events"
                )
            events, event_tip = [], _EVENT_GENESIS

        item_bindings: list[dict[str, object]] = []
        item_run_jobs: set[tuple[str, str]] = set()
        for row in item_rows:
            job = (str(row["item_id"]), str(row["arm_id"]))
            if (
                row["run_id"] != run_id
                or job not in job_ordinal
                or job in item_run_jobs
                or sorted(positions.get(job, [])) != [1, 2, 3]
            ):
                raise TransportAuditRefusal(
                    "resume prefix item-run identity is not a completed job"
                )
            job_receipts = {
                physical_id: raw
                for physical_id, raw in accepted_receipts.items()
                if (
                    str(_strict_object(raw, "resume item-run call").get("item_id")),
                    str(_strict_object(raw, "resume item-run call").get("arm_id")),
                )
                == job
            }
            bindings, _preimages = _export_item_runs(
                [row], run_id=run_id, accepted_receipts=job_receipts
            )
            item_bindings.extend(bindings)
            item_run_jobs.add(job)

        for job, values in positions.items():
            if sorted(values) != list(range(1, len(values) + 1)):
                raise TransportAuditRefusal(
                    "resume prefix has a gapped call sequence"
                )
        populated_ordinals = sorted(job_ordinal[job] for job in positions)
        frontier_batch = (
            max(populated_ordinals) // max_workers
            if populated_ordinals
            else -1
        )
        if frontier_batch >= 0:
            for ordinal in range(frontier_batch * max_workers):
                job = jobs[ordinal]
                if (
                    sorted(positions.get(job, [])) != [1, 2, 3]
                    or job not in item_run_jobs
                ):
                    raise TransportAuditRefusal(
                        "resume prefix violates scheduler batch order"
                    )
        call_positions = [
            {
                "job_ordinal": job_ordinal[job],
                "item_id": job[0],
                "arm_id": job[1],
                "call_indices": sorted(indices),
                "item_run_committed": job in item_run_jobs,
            }
            for job, indices in sorted(
                positions.items(), key=lambda value: job_ordinal[value[0]]
            )
        ]
    finally:
        attempt.close()
        spool.close()

    post_attempt_identity = _database_identity(attempt_db, "attempt ledger")
    post_spool_identity = _database_identity(spool_db, "result spool")
    if attempt_identity != post_attempt_identity or spool_identity != post_spool_identity:
        raise TransportAuditRefusal(
            "transport database identity changed during resume-prefix export"
        )
    if (
        attempt_generation != _database_generation(attempt_db, "attempt ledger")
        or spool_generation != _database_generation(spool_db, "result spool")
    ):
        raise TransportAuditRefusal(
            "transport database generation changed during resume-prefix export"
        )

    attempt_audit_unsigned = {
        "schema_version": DURABLE_CALL_SCHEMA,
        "journal_mode": attempt_journal,
        "synchronous": int(attempt_sync),
        "event_chain_tip_sha256": event_tip,
        "call_count": len(canonical_accepted),
        "status_counts": (
            {"ACCEPTED": len(canonical_accepted)}
            if canonical_accepted
            else {}
        ),
        "accepted_call_root_sha256": canonical_sha256(canonical_accepted),
        "spool_binding_root_sha256": canonical_sha256(spool_bindings),
        "item_run_count": len(item_bindings),
        "item_run_root_sha256": canonical_sha256(item_bindings),
    }
    attempt_audit = {
        **attempt_audit_unsigned,
        "audit_sha256": canonical_sha256(attempt_audit_unsigned),
    }
    spool_audit_unsigned = {
        "schema_version": SPOOL_SCHEMA,
        "journal_mode": spool_journal,
        "synchronous": int(spool_sync),
        "call_count": len(spool_bindings),
        "status_counts": (
            {"COMPLETE": len(spool_bindings)} if spool_bindings else {}
        ),
        "completed_root_sha256": canonical_sha256(spool_bindings),
    }
    spool_audit = {
        **spool_audit_unsigned,
        "audit_sha256": canonical_sha256(spool_audit_unsigned),
    }
    zero_count = not canonical_accepted and not item_bindings and not events
    unsigned = {
        "schema_version": RESUME_PREFIX_SCHEMA,
        "run_id": run_id,
        "db_genesis_sha256": genesis_sha,
        "attempt_integrity": attempt_integrity,
        "spool_integrity": spool_integrity,
        "attempt_db_identity": attempt_identity,
        "spool_db_identity": spool_identity,
        "ordered_job_root_sha256": canonical_sha256(ordered_job_value),
        "job_count": len(jobs),
        "max_workers": max_workers,
        "frontier_batch": frontier_batch,
        "call_positions": call_positions,
        "call_count": len(canonical_accepted),
        "item_run_count": len(item_bindings),
        "attempt_event_count": len(events),
        "spool_call_count": len(spool_bindings),
        "event_chain_tip_sha256": event_tip,
        "attempt_event_root_sha256": canonical_sha256(events),
        "attempt_live_audit": attempt_audit,
        "spool_live_audit": spool_audit,
        "zero_count_genesis": zero_count,
    }
    return {
        **unsigned,
        "resume_prefix_sha256": canonical_sha256(unsigned),
    }


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
    attempt_generation = _database_generation(attempt_db, "attempt ledger")
    spool_generation = _database_generation(spool_db, "result spool")

    attempt = _open_read_only(
        attempt_db, "attempt ledger", attempt_generation
    )
    spool = _open_read_only(spool_db, "result spool", spool_generation)
    try:
        attempt_integrity = _integrity_readback(attempt, "attempt ledger")
        spool_integrity = _integrity_readback(spool, "result spool")
        attempt_journal, attempt_sync = _durability_readback(attempt, "attempt ledger")
        spool_journal, spool_sync = _durability_readback(spool, "result spool")
        attempt_version, attempt_schema = exact_schema_readback(
            attempt, "attempt", "attempt ledger"
        )
        spool_version, spool_schema = exact_schema_readback(
            spool, "spool", "result spool"
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
            event_rows, accepted_rows_by_id
        )
        item_bindings, item_preimages = _export_item_runs(
            item_rows,
            run_id=run_id,
            accepted_receipts=accepted_receipts,
        )
    finally:
        attempt.close()
        spool.close()

    post_attempt_identity = _database_identity(attempt_db, "attempt ledger")
    post_spool_identity = _database_identity(spool_db, "result spool")
    if attempt_identity != post_attempt_identity or spool_identity != post_spool_identity:
        raise TransportAuditRefusal("transport database identity changed during terminal export")
    if (
        attempt_generation != _database_generation(attempt_db, "attempt ledger")
        or spool_generation != _database_generation(spool_db, "result spool")
    ):
        raise TransportAuditRefusal(
            "transport database generation changed during terminal export"
        )

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
    "RESUME_PREFIX_SCHEMA",
    "TRANSPORT_BINDINGS_SCHEMA",
    "FrozenSQLiteReadOnly",
    "TransportAuditRefusal",
    "canonical_schema_sha256",
    "exact_schema_readback",
    "open_frozen_sqlite_read_only",
    "private_database_identity",
    "export_genesis",
    "export_resume_prefix",
    "export_terminal",
    "export_terminal_bindings",
    "main",
    "write_private_once",
]
