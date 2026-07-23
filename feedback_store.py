"""SQLite single-writer event store for :mod:`feedback_runtime`.

Every read verifies canonical bytes, duplicated index columns, the hash chain,
and the pure reducer.  Writes use ``BEGIN IMMEDIATE`` so idempotency resolution
and the append happen in one transaction across competing processes.
"""
from __future__ import annotations

import hmac
import sqlite3
import threading
from pathlib import Path
from typing import Any

from feedback_runtime import (
    EventEnvelope,
    IdempotencyConflict,
    IntegrityError,
    fold,
    request_sha256 as derive_request_sha256,
)


class SQLiteFeedbackStore:
    def __init__(self, path: str | Path, *, initial_cut_id: str) -> None:
        if not initial_cut_id:
            raise ValueError("initial_cut_id must be non-empty")
        self.path = str(path)
        self.initial_cut_id = initial_cut_id
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.path,
            timeout=10.0,
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA busy_timeout=10000")
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS feedback_streams (
                stream_id TEXT PRIMARY KEY,
                initial_cut_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feedback_events (
                stream_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                request_id TEXT NOT NULL,
                request_sha256 TEXT NOT NULL,
                kind TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                input_cut_id TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                previous_event_sha256 TEXT NOT NULL,
                event_sha256 TEXT NOT NULL,
                canonical_event BLOB NOT NULL,
                PRIMARY KEY (stream_id, sequence),
                UNIQUE (stream_id, request_id),
                FOREIGN KEY (stream_id) REFERENCES feedback_streams(stream_id)
            );
            """
        )

    @property
    def journal_mode(self) -> str:
        return str(self._connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    @property
    def synchronous(self) -> int:
        return int(self._connection.execute("PRAGMA synchronous").fetchone()[0])

    def _bind_stream(self, stream_id: str) -> None:
        row = self._connection.execute(
            "SELECT initial_cut_id FROM feedback_streams WHERE stream_id = ?",
            (stream_id,),
        ).fetchone()
        if row is None:
            self._connection.execute(
                "INSERT INTO feedback_streams(stream_id, initial_cut_id) VALUES (?, ?)",
                (stream_id, self.initial_cut_id),
            )
        elif row["initial_cut_id"] != self.initial_cut_id:
            raise IntegrityError("stream initial cut differs from the configured cut")

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> EventEnvelope:
        raw_value = row["canonical_event"]
        raw = bytes(raw_value) if not isinstance(raw_value, bytes) else raw_value
        event = EventEnvelope.from_canonical_bytes(raw)
        duplicated: dict[str, Any] = {
            "stream_id": event.stream_id,
            "sequence": event.sequence,
            "request_id": event.request_id,
            "kind": str(event.kind),
            "principal_id": event.principal_id,
            "input_cut_id": event.input_cut_id,
            "payload_sha256": event.payload_sha256,
            "previous_event_sha256": event.previous_event_sha256,
            "event_sha256": event.event_sha256,
        }
        for column, expected in duplicated.items():
            if row[column] != expected:
                raise IntegrityError(f"SQL column {column} differs from canonical event")
        expected_request = derive_request_sha256(
            stream_id=event.stream_id,
            request_id=event.request_id,
            kind=event.kind,
            trusted_principal_id=event.principal_id,
            input_cut_id=event.input_cut_id,
            causal_parent_ids=event.causal_parent_ids,
            payload_sha256=event.payload_sha256,
        )
        if not hmac.compare_digest(str(row["request_sha256"]), expected_request):
            raise IntegrityError("request_sha256 differs from canonical event intent")
        return event

    def _verified_events(self, stream_id: str) -> list[EventEnvelope]:
        rows = self._connection.execute(
            """
            SELECT stream_id, sequence, request_id, request_sha256, kind,
                   principal_id, input_cut_id, payload_sha256,
                   previous_event_sha256, event_sha256, canonical_event
            FROM feedback_events
            WHERE stream_id = ?
            ORDER BY sequence ASC
            """,
            (stream_id,),
        ).fetchall()
        events = [self._event_from_row(row) for row in rows]
        fold(events, stream_id=stream_id, initial_cut_id=self.initial_cut_id)
        return events

    def lookup_request(
        self, stream_id: str, request_id: str
    ) -> tuple[str, EventEnvelope] | None:
        with self._lock:
            # Retry/idempotency reads must not bypass corruption in an earlier
            # row.  Verify the entire ordered stream before serving the lookup.
            self._verified_events(stream_id)
            row = self._connection.execute(
                """
                SELECT stream_id, sequence, request_id, request_sha256, kind,
                       principal_id, input_cut_id, payload_sha256,
                       previous_event_sha256, event_sha256, canonical_event
                FROM feedback_events
                WHERE stream_id = ? AND request_id = ?
                """,
                (stream_id, request_id),
            ).fetchone()
            if row is None:
                return None
            event = self._event_from_row(row)
            return str(row["request_sha256"]), event

    def events(self, stream_id: str) -> list[EventEnvelope]:
        with self._lock:
            row = self._connection.execute(
                "SELECT initial_cut_id FROM feedback_streams WHERE stream_id = ?",
                (stream_id,),
            ).fetchone()
            if row is not None and row["initial_cut_id"] != self.initial_cut_id:
                raise IntegrityError("stream initial cut differs from the configured cut")
            return self._verified_events(stream_id)

    def append(
        self, event: EventEnvelope, request_sha256: str
    ) -> tuple[EventEnvelope, bool]:
        event.verify_integrity()
        if len(request_sha256) != 64:
            raise IntegrityError("request_sha256 must be a SHA-256 digest")
        expected_request = derive_request_sha256(
            stream_id=event.stream_id,
            request_id=event.request_id,
            kind=event.kind,
            trusted_principal_id=event.principal_id,
            input_cut_id=event.input_cut_id,
            causal_parent_ids=event.causal_parent_ids,
            payload_sha256=event.payload_sha256,
        )
        if not hmac.compare_digest(request_sha256, expected_request):
            raise IntegrityError("request_sha256 does not match event intent")
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self._bind_stream(event.stream_id)
                current = self._verified_events(event.stream_id)
                prior = self._connection.execute(
                    """
                    SELECT stream_id, sequence, request_id, request_sha256, kind,
                           principal_id, input_cut_id, payload_sha256,
                           previous_event_sha256, event_sha256, canonical_event
                    FROM feedback_events
                    WHERE stream_id = ? AND request_id = ?
                    """,
                    (event.stream_id, event.request_id),
                ).fetchone()
                if prior is not None:
                    stored = self._event_from_row(prior)
                    if not hmac.compare_digest(str(prior["request_sha256"]), request_sha256):
                        raise IdempotencyConflict(
                            "same request_id carries different intent"
                        )
                    self._connection.execute("COMMIT")
                    return stored, False

                # The fold including the candidate proves ordering, parents, cut,
                # payload contract, and per-stream role separation atomically.
                fold(
                    [*current, event],
                    stream_id=event.stream_id,
                    initial_cut_id=self.initial_cut_id,
                )
                self._connection.execute(
                    """
                    INSERT INTO feedback_events(
                        stream_id, sequence, request_id, request_sha256, kind,
                        principal_id, input_cut_id, payload_sha256,
                        previous_event_sha256, event_sha256, canonical_event
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.stream_id,
                        event.sequence,
                        event.request_id,
                        request_sha256,
                        str(event.kind),
                        event.principal_id,
                        event.input_cut_id,
                        event.payload_sha256,
                        event.previous_event_sha256,
                        event.event_sha256,
                        event.canonical_bytes(),
                    ),
                )
                self._connection.execute("COMMIT")
                return event, True
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "SQLiteFeedbackStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
