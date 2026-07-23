"""SQLite staging and compare-and-swap activation for HSWM slow weights."""
from __future__ import annotations

from dataclasses import dataclass
import hmac
import json
from pathlib import Path
import sqlite3
import threading

from hswm_weight_snapshot import (
    WeightCandidateV1,
    WeightContractError,
    WeightSnapshotV1,
    apply_candidate,
    canonical_json_bytes,
    canonical_sha256,
    parse_candidate,
    parse_snapshot,
)


ACTIVATION_RECEIPT_SCHEMA_VERSION = "hswm-weight-activation-receipt/v1"


class WeightStoreError(RuntimeError):
    """Base class for durable weight-store failures."""


class StaleWeightEpochError(WeightStoreError):
    """A candidate no longer targets the active snapshot and epoch."""


class CandidateConflictError(WeightStoreError):
    """A candidate identity was reused with different canonical bytes."""


@dataclass(frozen=True)
class ActivationReceiptV1:
    receipt_id: str
    candidate_id: str
    base_snapshot_id: str
    base_epoch: int
    active_snapshot_id: str
    active_epoch: int
    schema_version: str = ACTIVATION_RECEIPT_SCHEMA_VERSION

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "base_snapshot_id": self.base_snapshot_id,
            "base_epoch": self.base_epoch,
            "active_snapshot_id": self.active_snapshot_id,
            "active_epoch": self.active_epoch,
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "receipt_id": self.receipt_id}


def _make_receipt(
    candidate: WeightCandidateV1, snapshot: WeightSnapshotV1
) -> ActivationReceiptV1:
    unsigned = {
        "schema_version": ACTIVATION_RECEIPT_SCHEMA_VERSION,
        "candidate_id": candidate.candidate_id,
        "base_snapshot_id": candidate.base_snapshot_id,
        "base_epoch": candidate.base_epoch,
        "active_snapshot_id": snapshot.snapshot_id,
        "active_epoch": snapshot.epoch,
    }
    return ActivationReceiptV1(
        receipt_id=canonical_sha256(unsigned),
        **{key: value for key, value in unsigned.items() if key != "schema_version"},
    )


def _parse_receipt(raw: bytes) -> ActivationReceiptV1:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WeightStoreError(f"invalid activation receipt JSON: {error}") from error
    receipt = ActivationReceiptV1(
        receipt_id=str(value["receipt_id"]),
        candidate_id=str(value["candidate_id"]),
        base_snapshot_id=str(value["base_snapshot_id"]),
        base_epoch=int(value["base_epoch"]),
        active_snapshot_id=str(value["active_snapshot_id"]),
        active_epoch=int(value["active_epoch"]),
        schema_version=str(value["schema_version"]),
    )
    if receipt.schema_version != ACTIVATION_RECEIPT_SCHEMA_VERSION:
        raise WeightStoreError("unsupported activation receipt schema")
    if receipt.receipt_id != canonical_sha256(receipt.unsigned()):
        raise WeightStoreError("activation receipt digest mismatch")
    return receipt


class SQLiteWeightStore:
    """Single-writer durable store for staged and active weight snapshots."""

    def __init__(self, path: str | Path, *, initial_snapshot: WeightSnapshotV1) -> None:
        self.path = str(path)
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
            CREATE TABLE IF NOT EXISTS weight_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                epoch INTEGER NOT NULL,
                parent_snapshot_id TEXT NOT NULL,
                topology_sha256 TEXT NOT NULL,
                canonical_snapshot BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS staged_weight_candidates (
                candidate_id TEXT PRIMARY KEY,
                base_snapshot_id TEXT NOT NULL,
                base_epoch INTEGER NOT NULL,
                snapshot_id TEXT NOT NULL UNIQUE,
                canonical_candidate BLOB NOT NULL,
                FOREIGN KEY(snapshot_id) REFERENCES weight_snapshots(snapshot_id)
            );
            CREATE TABLE IF NOT EXISTS active_weight_snapshot (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                snapshot_id TEXT NOT NULL,
                epoch INTEGER NOT NULL,
                FOREIGN KEY(snapshot_id) REFERENCES weight_snapshots(snapshot_id)
            );
            CREATE TABLE IF NOT EXISTS weight_activation_receipts (
                receipt_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL UNIQUE,
                canonical_receipt BLOB NOT NULL,
                FOREIGN KEY(candidate_id) REFERENCES staged_weight_candidates(candidate_id)
            );
            """
        )
        self._initialize(initial_snapshot)

    @property
    def journal_mode(self) -> str:
        return str(self._connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    @property
    def synchronous(self) -> int:
        return int(self._connection.execute("PRAGMA synchronous").fetchone()[0])

    def _insert_snapshot(self, snapshot: WeightSnapshotV1) -> None:
        raw = canonical_json_bytes(snapshot.canonical())
        prior = self._connection.execute(
            "SELECT canonical_snapshot FROM weight_snapshots WHERE snapshot_id = ?",
            (snapshot.snapshot_id,),
        ).fetchone()
        if prior is not None:
            if not hmac.compare_digest(bytes(prior[0]), raw):
                raise CandidateConflictError("snapshot identity carries different bytes")
            return
        self._connection.execute(
            """
            INSERT INTO weight_snapshots(
                snapshot_id, epoch, parent_snapshot_id, topology_sha256,
                canonical_snapshot
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                snapshot.snapshot_id,
                snapshot.epoch,
                snapshot.parent_snapshot_id,
                snapshot.topology_sha256,
                raw,
            ),
        )

    def _initialize(self, initial_snapshot: WeightSnapshotV1) -> None:
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                self._insert_snapshot(initial_snapshot)
                active = self._connection.execute(
                    "SELECT snapshot_id, epoch FROM active_weight_snapshot WHERE singleton = 1"
                ).fetchone()
                if active is None:
                    self._connection.execute(
                        """
                        INSERT INTO active_weight_snapshot(singleton, snapshot_id, epoch)
                        VALUES (1, ?, ?)
                        """,
                        (initial_snapshot.snapshot_id, initial_snapshot.epoch),
                    )
                else:
                    current = self._load_snapshot(str(active["snapshot_id"]))
                    if current.topology_sha256 != initial_snapshot.topology_sha256:
                        raise WeightStoreError(
                            "configured initial snapshot topology differs from active topology"
                        )
                self._connection.execute("COMMIT")
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def _load_snapshot(self, snapshot_id: str) -> WeightSnapshotV1:
        row = self._connection.execute(
            """
            SELECT snapshot_id, epoch, parent_snapshot_id, topology_sha256,
                   canonical_snapshot
            FROM weight_snapshots WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        ).fetchone()
        if row is None:
            raise WeightStoreError(f"missing weight snapshot {snapshot_id}")
        raw_value = row["canonical_snapshot"]
        raw = bytes(raw_value) if not isinstance(raw_value, bytes) else raw_value
        try:
            snapshot = parse_snapshot(raw)
        except WeightContractError as error:
            raise WeightStoreError(str(error)) from error
        duplicated = {
            "snapshot_id": snapshot.snapshot_id,
            "epoch": snapshot.epoch,
            "parent_snapshot_id": snapshot.parent_snapshot_id,
            "topology_sha256": snapshot.topology_sha256,
        }
        for column, expected in duplicated.items():
            if row[column] != expected:
                raise WeightStoreError(f"snapshot column {column} differs from canonical bytes")
        return snapshot

    def _load_candidate(self, candidate_id: str) -> tuple[WeightCandidateV1, WeightSnapshotV1]:
        row = self._connection.execute(
            """
            SELECT candidate_id, base_snapshot_id, base_epoch, snapshot_id,
                   canonical_candidate
            FROM staged_weight_candidates WHERE candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise WeightStoreError(f"candidate {candidate_id} is not staged")
        raw_value = row["canonical_candidate"]
        raw = bytes(raw_value) if not isinstance(raw_value, bytes) else raw_value
        try:
            candidate = parse_candidate(raw)
        except WeightContractError as error:
            raise WeightStoreError(str(error)) from error
        for column, expected in {
            "candidate_id": candidate.candidate_id,
            "base_snapshot_id": candidate.base_snapshot_id,
            "base_epoch": candidate.base_epoch,
        }.items():
            if row[column] != expected:
                raise WeightStoreError(f"candidate column {column} differs from canonical bytes")
        return candidate, self._load_snapshot(str(row["snapshot_id"]))

    def active_snapshot(self) -> WeightSnapshotV1:
        with self._lock:
            row = self._connection.execute(
                "SELECT snapshot_id, epoch FROM active_weight_snapshot WHERE singleton = 1"
            ).fetchone()
            if row is None:
                raise WeightStoreError("active weight snapshot is missing")
            snapshot = self._load_snapshot(str(row["snapshot_id"]))
            if row["epoch"] != snapshot.epoch:
                raise WeightStoreError("active epoch differs from canonical snapshot")
            return snapshot

    def stage(self, candidate: WeightCandidateV1) -> WeightSnapshotV1:
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                existing = self._connection.execute(
                    """
                    SELECT canonical_candidate, snapshot_id
                    FROM staged_weight_candidates WHERE candidate_id = ?
                    """,
                    (candidate.candidate_id,),
                ).fetchone()
                candidate_raw = canonical_json_bytes(candidate.canonical())
                if existing is not None:
                    stored_raw = bytes(existing["canonical_candidate"])
                    if not hmac.compare_digest(stored_raw, candidate_raw):
                        raise CandidateConflictError(
                            "candidate identity carries different canonical bytes"
                        )
                    snapshot = self._load_snapshot(str(existing["snapshot_id"]))
                    self._connection.execute("COMMIT")
                    return snapshot
                active_row = self._connection.execute(
                    "SELECT snapshot_id, epoch FROM active_weight_snapshot WHERE singleton = 1"
                ).fetchone()
                if active_row is None:
                    raise WeightStoreError("active weight snapshot is missing")
                if (
                    active_row["snapshot_id"] != candidate.base_snapshot_id
                    or active_row["epoch"] != candidate.base_epoch
                ):
                    raise StaleWeightEpochError("candidate base is no longer active")
                base = self._load_snapshot(candidate.base_snapshot_id)
                snapshot = apply_candidate(base, candidate)
                self._insert_snapshot(snapshot)
                self._connection.execute(
                    """
                    INSERT INTO staged_weight_candidates(
                        candidate_id, base_snapshot_id, base_epoch, snapshot_id,
                        canonical_candidate
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        candidate.candidate_id,
                        candidate.base_snapshot_id,
                        candidate.base_epoch,
                        snapshot.snapshot_id,
                        candidate_raw,
                    ),
                )
                self._connection.execute("COMMIT")
                return snapshot
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def activate(self, candidate_id: str) -> ActivationReceiptV1:
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                prior = self._connection.execute(
                    """
                    SELECT canonical_receipt FROM weight_activation_receipts
                    WHERE candidate_id = ?
                    """,
                    (candidate_id,),
                ).fetchone()
                if prior is not None:
                    raw_value = prior["canonical_receipt"]
                    raw = bytes(raw_value) if not isinstance(raw_value, bytes) else raw_value
                    receipt = _parse_receipt(raw)
                    self._connection.execute("COMMIT")
                    return receipt

                candidate, snapshot = self._load_candidate(candidate_id)
                active = self._connection.execute(
                    "SELECT snapshot_id, epoch FROM active_weight_snapshot WHERE singleton = 1"
                ).fetchone()
                if (
                    active is None
                    or active["snapshot_id"] != candidate.base_snapshot_id
                    or active["epoch"] != candidate.base_epoch
                ):
                    raise StaleWeightEpochError("candidate lost the active-epoch CAS")
                updated = self._connection.execute(
                    """
                    UPDATE active_weight_snapshot
                    SET snapshot_id = ?, epoch = ?
                    WHERE singleton = 1 AND snapshot_id = ? AND epoch = ?
                    """,
                    (
                        snapshot.snapshot_id,
                        snapshot.epoch,
                        candidate.base_snapshot_id,
                        candidate.base_epoch,
                    ),
                )
                if updated.rowcount != 1:
                    raise StaleWeightEpochError("candidate lost the active-epoch CAS")
                receipt = _make_receipt(candidate, snapshot)
                self._connection.execute(
                    """
                    INSERT INTO weight_activation_receipts(
                        receipt_id, candidate_id, canonical_receipt
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        receipt.receipt_id,
                        receipt.candidate_id,
                        canonical_json_bytes(receipt.canonical()),
                    ),
                )
                self._connection.execute("COMMIT")
                return receipt
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> "SQLiteWeightStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


__all__ = [
    "ACTIVATION_RECEIPT_SCHEMA_VERSION",
    "ActivationReceiptV1",
    "CandidateConflictError",
    "SQLiteWeightStore",
    "StaleWeightEpochError",
    "WeightStoreError",
]
