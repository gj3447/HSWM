"""Low-level SQLite authority for the HSWM F1 ledger and result spool.

This module deliberately imports no transport or runner code.  Both live
constructors and the read-only evidence exporter consume the same exact schema
preimage from here, avoiding a transport <-> audit import cycle.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
from collections.abc import Mapping
from functools import lru_cache
from urllib.parse import quote

from prom_search_hswm.hswm_typed_ports import canonical_sha256


LEDGER_USER_VERSION = 1
LEDGER_SCHEMA_SQL = """
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

SPOOL_USER_VERSION = 1
SPOOL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS spool_calls (
    physical_call_id TEXT PRIMARY KEY,
    intent_sha256 TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    request_bytes BLOB NOT NULL,
    status TEXT NOT NULL CHECK(status IN (
        'DISPATCHING', 'COMPLETE', 'UNKNOWN'
    )),
    response_status INTEGER,
    response_headers BLOB,
    response_body BLOB,
    response_sha256 TEXT,
    error_class TEXT,
    CHECK (
        (status = 'DISPATCHING'
         AND response_status IS NULL AND response_headers IS NULL
         AND response_body IS NULL AND response_sha256 IS NULL
         AND error_class IS NULL)
        OR
        (status = 'UNKNOWN'
         AND response_status IS NULL AND response_headers IS NULL
         AND response_body IS NULL AND response_sha256 IS NULL
         AND typeof(error_class) = 'text' AND length(error_class) > 0)
        OR
        (status = 'COMPLETE'
         AND typeof(response_status) = 'integer'
         AND response_status BETWEEN 100 AND 599
         AND response_headers IS NOT NULL AND response_body IS NOT NULL
         AND response_sha256 IS NOT NULL AND error_class IS NULL)
    )
);
"""

# Exact schema used by the quarantined F1 r8/v8 incident.  It remains a
# separate read-only evidence authority: live constructors must never fall
# back to this weaker historical CHECK constraint.
SPOOL_HISTORICAL_V8_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS spool_calls (
    physical_call_id TEXT PRIMARY KEY,
    intent_sha256 TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    request_bytes BLOB NOT NULL,
    status TEXT NOT NULL CHECK(status IN (
        'DISPATCHING', 'COMPLETE', 'UNKNOWN'
    )),
    response_status INTEGER,
    response_headers BLOB,
    response_body BLOB,
    response_sha256 TEXT,
    error_class TEXT,
    CHECK (
        (status = 'COMPLETE' AND response_status IS NOT NULL
         AND response_headers IS NOT NULL AND response_body IS NOT NULL
         AND response_sha256 IS NOT NULL)
        OR status != 'COMPLETE'
    )
);
"""

LEDGER_COLUMNS: Mapping[str, list[str]] = {
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
    "attempt_events": [
        "sequence",
        "physical_call_id",
        "event_type",
        "event_bytes",
        "previous_event_sha256",
        "event_sha256",
    ],
    "item_runs": [
        "run_id",
        "arm_id",
        "item_id",
        "run_receipt_sha256",
        "item_run_bytes",
    ],
}

SPOOL_COLUMNS: Mapping[str, list[str]] = {
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

SQLITE_FAMILY_MEMBERS = (
    ("main", ""),
    ("wal", "-wal"),
    ("shm", "-shm"),
    ("journal", "-journal"),
)


class SQLiteAuthorityRefusal(RuntimeError):
    """A SQLite namespace, schema, or frozen generation is not authoritative."""


def _canonical_sql(sql: str) -> str:
    output: list[str] = []
    quote_end: str | None = None
    pending_space = False
    index = 0
    while index < len(sql):
        character = sql[index]
        if quote_end is not None:
            output.append(character)
            if character == quote_end:
                if (
                    quote_end != "]"
                    and index + 1 < len(sql)
                    and sql[index + 1] == quote_end
                ):
                    output.append(sql[index + 1])
                    index += 1
                else:
                    quote_end = None
            index += 1
            continue
        if character.isspace():
            pending_space = bool(output)
            index += 1
            continue
        if pending_space:
            output.append(" ")
            pending_space = False
        output.append(character)
        if character in {"'", '"', "`"}:
            quote_end = character
        elif character == "[":
            quote_end = "]"
        index += 1
    if quote_end is not None:
        raise SQLiteAuthorityRefusal("SQLite schema contains an unterminated quote")
    return "".join(output).strip()


def _schema_authority(
    authority: str,
) -> tuple[str, int, Mapping[str, list[str]]]:
    if authority == "attempt":
        return LEDGER_SCHEMA_SQL, LEDGER_USER_VERSION, LEDGER_COLUMNS
    if authority == "spool":
        return SPOOL_SCHEMA_SQL, SPOOL_USER_VERSION, SPOOL_COLUMNS
    if authority == "spool_historical_v8":
        return (
            SPOOL_HISTORICAL_V8_SCHEMA_SQL,
            SPOOL_USER_VERSION,
            SPOOL_COLUMNS,
        )
    raise SQLiteAuthorityRefusal(f"unknown SQLite schema authority {authority}")


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
        raise SQLiteAuthorityRefusal(f"{label} table set drifted")
    observed: dict[str, list[str]] = {}
    table_metadata: dict[str, object] = {}
    for table, columns in expected.items():
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        observed[table] = [str(row[1]) for row in rows]
        if observed[table] != columns:
            raise SQLiteAuthorityRefusal(f"{label} columns drifted for {table}")
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
            "sql": None if row[3] is None else _canonical_sql(str(row[3])),
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
        raise SQLiteAuthorityRefusal(
            f"{label} contains executable or explicit schema objects"
        )
    return {
        "user_version": version,
        "tables": observed,
        "table_metadata": table_metadata,
        "sqlite_master": sqlite_master,
    }


@lru_cache(maxsize=3)
def canonical_schema_payload(authority: str) -> dict[str, object]:
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
    """Require logical DDL equality, including constraints and implicit indexes."""

    _schema_sql, expected_version, columns = _schema_authority(authority)
    try:
        observed = _schema_payload(connection, columns, label)
    except sqlite3.Error as error:
        raise SQLiteAuthorityRefusal(f"{label} canonical schema drifted") from error
    version = int(observed["user_version"])
    if version != expected_version:
        raise SQLiteAuthorityRefusal(
            f"{label} user_version is {version}, expected {expected_version}"
        )
    if observed != canonical_schema_payload(authority):
        raise SQLiteAuthorityRefusal(f"{label} canonical schema drifted")
    return version, canonical_sha256(observed)


def canonical_schema_sha256(authority: str) -> str:
    _schema_authority(authority)
    return canonical_sha256(canonical_schema_payload(authority))


def integrity_readback(connection: sqlite3.Connection, label: str) -> str:
    values = [str(row[0]) for row in connection.execute("PRAGMA integrity_check")]
    if values != ["ok"]:
        raise SQLiteAuthorityRefusal(f"{label} integrity_check failed")
    foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_keys:
        raise SQLiteAuthorityRefusal(f"{label} foreign_key_check failed")
    return "ok"


def require_wal_full(connection: sqlite3.Connection, label: str) -> None:
    journal = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).casefold()
    synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
    if journal != "wal" or synchronous != 2:
        raise SQLiteAuthorityRefusal(f"{label} is not WAL/FULL")


def open_private_parent(path: Path, label: str) -> int:
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path.parent, flags)
    except OSError as error:
        raise SQLiteAuthorityRefusal(f"cannot open {label} parent") from error
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise SQLiteAuthorityRefusal(
                f"{label} parent must be one owner-private 0700 directory"
            )
        verify_private_parent(path, descriptor, label)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def verify_private_parent(path: Path, descriptor: int, label: str) -> None:
    try:
        opened = os.fstat(descriptor)
        observed = path.parent.stat(follow_symlinks=False)
    except OSError as error:
        raise SQLiteAuthorityRefusal(f"{label} parent is unavailable") from error
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(observed.st_mode)
        or (opened.st_dev, opened.st_ino) != (observed.st_dev, observed.st_ino)
        or opened.st_uid != os.geteuid()
        or observed.st_uid != os.geteuid()
        or stat.S_IMODE(opened.st_mode) != 0o700
        or stat.S_IMODE(observed.st_mode) != 0o700
    ):
        raise SQLiteAuthorityRefusal(f"{label} parent identity drifted")


def _file_generation(
    path: Path,
    label: str,
    *,
    required: bool,
) -> dict[str, object] | None:
    try:
        before = path.lstat()
    except FileNotFoundError:
        if required:
            raise SQLiteAuthorityRefusal(f"{label} is absent")
        return None
    except OSError as error:
        raise SQLiteAuthorityRefusal(f"cannot stat {label}") from error
    descriptor = -1
    digest = hashlib.sha256()
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        while block := os.read(descriptor, 1024 * 1024):
            digest.update(block)
        after_fd = os.fstat(descriptor)
        after_path = path.lstat()
    except OSError as error:
        raise SQLiteAuthorityRefusal(f"cannot read {label}") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    observations = (before, opened, after_fd, after_path)
    identity = (before.st_dev, before.st_ino)
    if (
        any(
            stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
            for info in observations
        )
        or any((info.st_dev, info.st_ino) != identity for info in observations)
        or any(info.st_uid != os.geteuid() for info in observations)
        or any(info.st_nlink != 1 for info in observations)
        or any(stat.S_IMODE(info.st_mode) != 0o600 for info in observations)
        or before.st_size != after_fd.st_size
        or before.st_mtime_ns != after_fd.st_mtime_ns
        or before.st_ctime_ns != after_fd.st_ctime_ns
    ):
        raise SQLiteAuthorityRefusal(f"{label} changed during generation capture")
    return {
        "st_dev": int(after_fd.st_dev),
        "st_ino": int(after_fd.st_ino),
        "st_size": int(after_fd.st_size),
        "st_mtime_ns": int(after_fd.st_mtime_ns),
        "st_ctime_ns": int(after_fd.st_ctime_ns),
        "sha256": digest.hexdigest(),
    }


def database_generation(path: Path, label: str) -> dict[str, object]:
    return {
        name: _file_generation(
            Path(f"{path}{suffix}"),
            f"{label}{' ' + name.upper() if name != 'main' else ''}",
            required=name == "main",
        )
        for name, suffix in SQLITE_FAMILY_MEMBERS
    }


def validate_private_sqlite_family(path: Path, label: str) -> None:
    database_generation(path, label)


def require_sqlite_family_absent(path: Path, label: str) -> None:
    for name, suffix in SQLITE_FAMILY_MEMBERS:
        candidate = Path(f"{path}{suffix}")
        try:
            candidate.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise SQLiteAuthorityRefusal(f"cannot stat {label} {name}") from error
        raise SQLiteAuthorityRefusal(f"{label} SQLite family already exists")


def create_exclusive_main(path: Path, parent_descriptor: int, label: str) -> None:
    descriptor = -1
    try:
        descriptor = os.open(
            path.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
        os.fsync(parent_descriptor)
    except OSError as error:
        raise SQLiteAuthorityRefusal(f"cannot create private {label}") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def assert_database_generation(
    path: Path,
    label: str,
    expected: Mapping[str, object],
) -> None:
    if database_generation(path, label) != dict(expected):
        raise SQLiteAuthorityRefusal(f"{label} generation changed")


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
            raise SQLiteAuthorityRefusal(f"{label} generation is absent")
        try:
            source.lstat()
        except FileNotFoundError:
            return
        except OSError as error:
            raise SQLiteAuthorityRefusal(f"cannot stat {label}") from error
        raise SQLiteAuthorityRefusal(f"{label} appeared after generation freeze")
    if not isinstance(expected, Mapping):
        raise SQLiteAuthorityRefusal(f"{label} generation is malformed")
    source_fd = -1
    destination_fd = -1
    digest = hashlib.sha256()
    try:
        before = source.lstat()
        source_fd = os.open(
            source,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(source_fd)
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
                    raise SQLiteAuthorityRefusal(
                        f"{label} snapshot copy made no progress"
                    )
                offset += written
        os.fsync(destination_fd)
        after_fd = os.fstat(source_fd)
        after_path = source.lstat()
    except OSError as error:
        raise SQLiteAuthorityRefusal(f"cannot snapshot {label}") from error
    finally:
        if destination_fd >= 0:
            os.close(destination_fd)
        if source_fd >= 0:
            os.close(source_fd)
    expected_identity = (expected.get("st_dev"), expected.get("st_ino"))
    observations = (before, opened, after_fd, after_path)
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
        raise SQLiteAuthorityRefusal(f"{label} differs from its frozen generation")


class FrozenSQLiteReadOnly:
    """Query-only connection over a private byte snapshot of one generation."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        temporary: tempfile.TemporaryDirectory[str],
        source: Path,
        label: str,
        generation: Mapping[str, object],
    ) -> None:
        self.connection = connection
        self._temporary: tempfile.TemporaryDirectory[str] | None = temporary
        self._source = source
        self._label = label
        self.generation = dict(generation)

    def close(self) -> None:
        if self._temporary is None:
            return
        try:
            self.connection.close()
        finally:
            self._temporary.cleanup()
            self._temporary = None
        assert_database_generation(
            self._source, self._label, self.generation
        )

    def __enter__(self) -> sqlite3.Connection:
        return self.connection

    def __exit__(self, *_exc: object) -> None:
        self.close()


def open_frozen_sqlite_read_only(path: Path, label: str) -> FrozenSQLiteReadOnly:
    generation = database_generation(path, label)
    if generation.get("journal") is not None:
        raise SQLiteAuthorityRefusal(
            f"{label} has a rollback journal; recovery is not authorized"
        )
    temporary = tempfile.TemporaryDirectory(prefix="hswm-f1-sqlite-authority-")
    snapshot = Path(temporary.name) / "database.sqlite3"
    try:
        _copy_generation_member(
            path, snapshot, generation.get("main"), label, required=True
        )
        _copy_generation_member(
            Path(f"{path}-wal"),
            Path(f"{snapshot}-wal"),
            generation.get("wal"),
            f"{label} WAL",
            required=False,
        )
        assert_database_generation(path, label, generation)
        uri = f"file:{quote(str(snapshot), safe='/')}?mode=rw"
        connection = sqlite3.connect(uri, uri=True, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN")
    except BaseException:
        temporary.cleanup()
        raise
    return FrozenSQLiteReadOnly(connection, temporary, path, label, generation)


__all__ = [
    "LEDGER_COLUMNS",
    "LEDGER_SCHEMA_SQL",
    "LEDGER_USER_VERSION",
    "SPOOL_COLUMNS",
    "SPOOL_SCHEMA_SQL",
    "SPOOL_USER_VERSION",
    "SQLiteAuthorityRefusal",
    "assert_database_generation",
    "canonical_schema_sha256",
    "create_exclusive_main",
    "database_generation",
    "exact_schema_readback",
    "integrity_readback",
    "open_frozen_sqlite_read_only",
    "open_private_parent",
    "require_sqlite_family_absent",
    "require_wal_full",
    "validate_private_sqlite_family",
    "verify_private_parent",
]
