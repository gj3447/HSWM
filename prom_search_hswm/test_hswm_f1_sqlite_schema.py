from __future__ import annotations

from pathlib import Path
import re
import sqlite3

import pytest

from prom_search_hswm.hswm_f1_sqlite_schema import (
    LEDGER_SCHEMA_SQL,
    LEDGER_USER_VERSION,
    SPOOL_HISTORICAL_V8_SCHEMA_SQL,
    SPOOL_SCHEMA_SQL,
    SPOOL_USER_VERSION,
    SQLiteAuthorityRefusal,
    canonical_schema_sha256,
    exact_schema_readback,
)


def _canonical_attempt_database(path: Path) -> None:
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(LEDGER_SCHEMA_SQL)
        connection.execute(f"PRAGMA user_version={LEDGER_USER_VERSION}")
    finally:
        connection.close()
    path.chmod(0o600)


def _spool_database(path: Path, schema_sql: str) -> None:
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(schema_sql)
        connection.execute(f"PRAGMA user_version={SPOOL_USER_VERSION}")
    finally:
        connection.close()
    path.chmod(0o600)


def test_historical_v8_spool_schema_is_a_separate_exact_authority(
    tmp_path: Path,
) -> None:
    historical = tmp_path / "historical.sqlite3"
    current = tmp_path / "current.sqlite3"
    _spool_database(historical, SPOOL_HISTORICAL_V8_SCHEMA_SQL)
    _spool_database(current, SPOOL_SCHEMA_SQL)

    historical_connection = sqlite3.connect(historical, isolation_level=None)
    current_connection = sqlite3.connect(current, isolation_level=None)
    try:
        _, historical_sha = exact_schema_readback(
            historical_connection,
            "spool_historical_v8",
            "historical v8 spool",
        )
        _, current_sha = exact_schema_readback(
            current_connection, "spool", "current spool"
        )
        assert historical_sha == canonical_schema_sha256("spool_historical_v8")
        assert current_sha == canonical_schema_sha256("spool")
        assert historical_sha != current_sha
        with pytest.raises(SQLiteAuthorityRefusal, match="canonical schema drifted"):
            exact_schema_readback(historical_connection, "spool", "historical")
        with pytest.raises(SQLiteAuthorityRefusal, match="canonical schema drifted"):
            exact_schema_readback(
                current_connection, "spool_historical_v8", "current"
            )
    finally:
        historical_connection.close()
        current_connection.close()


def _rewrite_table_sql(path: Path, table: str, mutate) -> None:
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        assert row is not None and isinstance(row[0], str)
        changed = mutate(str(row[0]))
        assert changed != row[0]
        version = int(connection.execute("PRAGMA schema_version").fetchone()[0])
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute(
            "UPDATE sqlite_master SET sql=? WHERE type='table' AND name=?",
            (changed, table),
        )
        connection.execute(f"PRAGMA schema_version={version + 1}")
        connection.execute("PRAGMA writable_schema=OFF")
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("table", "mutate"),
    (
        (
            "call_state",
            lambda sql: re.sub(
                r"CHECK\s*\(status\s+IN\s*\([^)]*\)\)",
                "",
                sql,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "call_state",
            lambda sql: sql.replace(
                "physical_call_id TEXT PRIMARY KEY",
                "physical_call_id TEXT",
                1,
            ),
        ),
        (
            "call_state",
            lambda sql: sql.replace(
                "intent_sha256 TEXT NOT NULL",
                "intent_sha256 TEXT",
                1,
            ),
        ),
        (
            "call_state",
            lambda sql: sql.replace(
                "endpoint TEXT NOT NULL",
                "endpoint TEXT NOT NULL DEFAULT 'drift'",
                1,
            ),
        ),
        (
            "attempt_events",
            lambda sql: re.sub(
                r",\s*FOREIGN KEY\s*\(physical_call_id\)\s*"
                r"REFERENCES\s+call_state\s*\(physical_call_id\)",
                "",
                sql,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
    ),
    ids=("check", "primary-key", "not-null", "default", "foreign-key"),
)
def test_exact_schema_refuses_each_constraint_drift(
    tmp_path: Path, table: str, mutate
) -> None:
    path = tmp_path / "attempt.sqlite3"
    _canonical_attempt_database(path)
    _rewrite_table_sql(path, table, mutate)
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        with pytest.raises(SQLiteAuthorityRefusal, match="canonical schema drifted"):
            exact_schema_readback(connection, "attempt", "attempt ledger")
    finally:
        connection.close()


@pytest.mark.parametrize(
    "statement",
    (
        "CREATE INDEX explicit_status ON call_state(status)",
        "CREATE VIEW call_ids AS SELECT physical_call_id FROM call_state",
        "CREATE TRIGGER reject_call BEFORE INSERT ON call_state "
        "BEGIN SELECT RAISE(ABORT, 'blocked'); END",
    ),
    ids=("index", "view", "trigger"),
)
def test_exact_schema_refuses_executable_or_explicit_objects(
    tmp_path: Path, statement: str
) -> None:
    path = tmp_path / "attempt.sqlite3"
    _canonical_attempt_database(path)
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        connection.execute(statement)
    finally:
        connection.close()
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        with pytest.raises(
            SQLiteAuthorityRefusal,
            match="executable or explicit schema objects",
        ):
            exact_schema_readback(connection, "attempt", "attempt ledger")
    finally:
        connection.close()
