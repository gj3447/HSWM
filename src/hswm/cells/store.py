"""SQLite event store and transactional outbox for the HSWM cell kernel.

The store is the sole durable writer for one or more named cell streams.  It
atomically commits accepted events, stream state, command idempotency receipts,
and outbox intents.  External model calls occur after that transaction.

Unknown external outcomes are deliberately not retried.  They enter an
explicit reconciliation state because an ordinary HTTP model endpoint cannot
prove exactly-once execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from .runtime import (
    Accepted,
    CellContract,
    CellPort,
    CellStepCompleted,
    CellStepRequested,
    Command,
    Effect,
    Event,
    InvokeCellEffect,
    KernelState,
    PacketEnvelope,
    RecordCellOutput,
    Rejected,
    RequestCellStep,
    canonical_json_bytes,
    decide,
    effects,
    evolve,
    state_digest,
)


STORE_SCHEMA_VERSION = 1
STORE_PROTOCOL = "hswm-cellular-store/v1"


class StoreError(RuntimeError):
    pass


class StoreIntegrityError(StoreError):
    pass


class StreamNotFound(StoreError):
    pass


class CommandIntentConflict(StoreError):
    pass


class OutboxStateConflict(StoreError):
    pass


class OutboxStatus(str, Enum):
    PENDING = "PENDING"
    IN_FLIGHT = "IN_FLIGHT"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"
    SUCCEEDED = "SUCCEEDED"
    FAILED_PERMANENT = "FAILED_PERMANENT"


@dataclass(frozen=True, slots=True)
class CommitReceipt:
    stream_id: str
    command_key: str
    intent_sha256: str
    event_sequences: tuple[int, ...]
    outbox_effect_ids: tuple[str, ...]
    committed_state_sha256: str
    exact_retry: bool


@dataclass(frozen=True, slots=True)
class OutboxRecord:
    effect_id: str
    stream_id: str
    source_sequence: int
    activation_id: str
    status: OutboxStatus
    attempts: int
    effect: InvokeCellEffect
    effect_sha256: str
    claim_token: str | None
    last_error: str | None
    output_payload_sha256: str | None
    completed_sequence: int | None


@dataclass(frozen=True, slots=True)
class DispatchReceipt:
    effect_id: str
    status: OutboxStatus
    port_called: bool
    completion: CommitReceipt | None
    error: str | None = None


def _sha256(value: Any) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _packet_value(packet: PacketEnvelope) -> dict[str, Any]:
    return {
        "packet_id": packet.packet_id,
        "packet_type": packet.packet_type,
        "payload": packet.payload,
        "payload_sha256": packet.payload_sha256,
        "provenance_sha256": packet.provenance_sha256,
    }


def _packet_from_value(value: Any) -> PacketEnvelope:
    if not isinstance(value, dict) or set(value) != {
        "packet_id",
        "packet_type",
        "payload",
        "payload_sha256",
        "provenance_sha256",
    }:
        raise StoreIntegrityError("stored packet field set is invalid")
    packet = PacketEnvelope(
        packet_id=value["packet_id"],
        packet_type=value["packet_type"],
        payload=value["payload"],
        payload_sha256=value["payload_sha256"],
        provenance_sha256=value["provenance_sha256"],
    )
    actual = sha256(canonical_json_bytes(packet.payload)).hexdigest()
    if actual != packet.payload_sha256:
        raise StoreIntegrityError("stored packet payload digest mismatch")
    return packet


def _command_key(command: Command) -> str:
    if isinstance(command, RequestCellStep):
        return f"request:{command.activation_id}"
    return f"complete:{command.activation_id}"


def _command_value(command: Command) -> dict[str, Any]:
    if isinstance(command, RequestCellStep):
        return {
            "type": "RequestCellStep",
            "expected_version": command.expected_version,
            "activation_id": command.activation_id,
            "cell_id": command.cell_id,
            "input": _packet_value(command.input),
        }
    return {
        "type": "RecordCellOutput",
        "expected_version": command.expected_version,
        "activation_id": command.activation_id,
        "output": _packet_value(command.output),
    }


def _event_value(event: Event) -> dict[str, Any]:
    if isinstance(event, CellStepRequested):
        return {
            "type": "CellStepRequested",
            "sequence": event.sequence,
            "activation_id": event.activation_id,
            "cell_id": event.cell_id,
            "input": _packet_value(event.input),
            "expected_output_type": event.expected_output_type,
        }
    return {
        "type": "CellStepCompleted",
        "sequence": event.sequence,
        "activation_id": event.activation_id,
        "cell_id": event.cell_id,
        "output": _packet_value(event.output),
    }


def _event_from_value(value: Any) -> Event:
    if not isinstance(value, dict):
        raise StoreIntegrityError("stored event must be an object")
    kind = value.get("type")
    if kind == "CellStepRequested" and set(value) == {
        "type",
        "sequence",
        "activation_id",
        "cell_id",
        "input",
        "expected_output_type",
    }:
        return CellStepRequested(
            sequence=value["sequence"],
            activation_id=value["activation_id"],
            cell_id=value["cell_id"],
            input=_packet_from_value(value["input"]),
            expected_output_type=value["expected_output_type"],
        )
    if kind == "CellStepCompleted" and set(value) == {
        "type",
        "sequence",
        "activation_id",
        "cell_id",
        "output",
    }:
        return CellStepCompleted(
            sequence=value["sequence"],
            activation_id=value["activation_id"],
            cell_id=value["cell_id"],
            output=_packet_from_value(value["output"]),
        )
    raise StoreIntegrityError(f"unknown or malformed stored event {kind!r}")


def _effect_value(effect: Effect) -> dict[str, Any]:
    if not isinstance(effect, InvokeCellEffect):
        raise StoreIntegrityError(f"unsupported effect {type(effect).__name__}")
    return {
        "type": "InvokeCell",
        "activation_id": effect.activation_id,
        "cell_id": effect.cell_id,
        "input": _packet_value(effect.input),
        "expected_output_type": effect.expected_output_type,
    }


def _effect_from_value(value: Any) -> InvokeCellEffect:
    if not isinstance(value, dict) or value.get("type") != "InvokeCell" or set(value) != {
        "type",
        "activation_id",
        "cell_id",
        "input",
        "expected_output_type",
    }:
        raise StoreIntegrityError("stored effect is malformed")
    return InvokeCellEffect(
        activation_id=value["activation_id"],
        cell_id=value["cell_id"],
        input=_packet_from_value(value["input"]),
        expected_output_type=value["expected_output_type"],
    )


def _receipt_value(receipt: CommitReceipt) -> dict[str, Any]:
    return {
        "stream_id": receipt.stream_id,
        "command_key": receipt.command_key,
        "intent_sha256": receipt.intent_sha256,
        "event_sequences": list(receipt.event_sequences),
        "outbox_effect_ids": list(receipt.outbox_effect_ids),
        "committed_state_sha256": receipt.committed_state_sha256,
    }


def _receipt_from_value(value: Any, *, exact_retry: bool) -> CommitReceipt:
    if not isinstance(value, dict) or set(value) != {
        "stream_id",
        "command_key",
        "intent_sha256",
        "event_sequences",
        "outbox_effect_ids",
        "committed_state_sha256",
    }:
        raise StoreIntegrityError("stored command receipt is malformed")
    return CommitReceipt(
        stream_id=value["stream_id"],
        command_key=value["command_key"],
        intent_sha256=value["intent_sha256"],
        event_sequences=tuple(value["event_sequences"]),
        outbox_effect_ids=tuple(value["outbox_effect_ids"]),
        committed_state_sha256=value["committed_state_sha256"],
        exact_retry=exact_retry,
    )


class SqliteCellRuntime:
    """Single-authority durable shell around ``hswm_cellular_runtime``."""

    def __init__(self, path: str | Path, registry: Mapping[str, CellContract]) -> None:
        self.path = Path(path)
        self.registry = dict(registry)
        if not self.registry:
            raise ValueError("registry must contain at least one cell contract")
        for key, contract in self.registry.items():
            if key != contract.cell_id:
                raise ValueError("registry key must equal contract.cell_id")
        self.registry_sha256 = _sha256(
            [
                {
                    "cell_id": contract.cell_id,
                    "input_type": contract.input_type,
                    "output_type": contract.output_type,
                }
                for _, contract in sorted(self.registry.items())
            ]
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=10.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, STORE_SCHEMA_VERSION):
                raise StoreIntegrityError(f"unsupported SQLite schema version {version}")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS streams (
                    stream_id TEXT PRIMARY KEY,
                    initial_budget INTEGER NOT NULL CHECK (initial_budget >= 0),
                    version INTEGER NOT NULL CHECK (version >= 0),
                    state_sha256 TEXT NOT NULL,
                    registry_sha256 TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    stream_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL CHECK (sequence > 0),
                    event_type TEXT NOT NULL,
                    event_json BLOB NOT NULL,
                    event_sha256 TEXT NOT NULL,
                    PRIMARY KEY (stream_id, sequence),
                    FOREIGN KEY (stream_id) REFERENCES streams(stream_id)
                );

                CREATE TABLE IF NOT EXISTS command_receipts (
                    stream_id TEXT NOT NULL,
                    command_key TEXT NOT NULL,
                    intent_sha256 TEXT NOT NULL,
                    receipt_json BLOB NOT NULL,
                    PRIMARY KEY (stream_id, command_key),
                    FOREIGN KEY (stream_id) REFERENCES streams(stream_id)
                );

                CREATE TABLE IF NOT EXISTS outbox (
                    effect_id TEXT PRIMARY KEY,
                    stream_id TEXT NOT NULL,
                    source_sequence INTEGER NOT NULL,
                    activation_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN (
                        'PENDING', 'IN_FLIGHT', 'UNKNOWN_OUTCOME',
                        'SUCCEEDED', 'FAILED_PERMANENT'
                    )),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                    effect_json BLOB NOT NULL,
                    effect_sha256 TEXT NOT NULL,
                    claim_token TEXT,
                    last_error TEXT,
                    output_payload_sha256 TEXT,
                    completed_sequence INTEGER,
                    UNIQUE (stream_id, source_sequence, activation_id),
                    FOREIGN KEY (stream_id, source_sequence)
                        REFERENCES events(stream_id, sequence)
                );

                CREATE INDEX IF NOT EXISTS outbox_pending_order
                    ON outbox(status, stream_id, source_sequence, effect_id);
                """
            )
            connection.execute(f"PRAGMA user_version={STORE_SCHEMA_VERSION}")

    def create_stream(self, stream_id: str, *, initial_budget: int) -> KernelState:
        if not stream_id:
            raise ValueError("stream_id must be non-empty")
        initial = KernelState(remaining_budget=initial_budget)
        digest = state_digest(initial)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM streams WHERE stream_id=?", (stream_id,)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO streams(stream_id,initial_budget,version,state_sha256,registry_sha256) VALUES(?,?,?,?,?)",
                    (stream_id, initial_budget, 0, digest, self.registry_sha256),
                )
                connection.commit()
                return initial
            if (
                row["initial_budget"] != initial_budget
                or row["registry_sha256"] != self.registry_sha256
            ):
                connection.rollback()
                raise CommandIntentConflict(
                    "existing stream has a different initial budget or registry"
                )
            connection.commit()
        return self.load_state(stream_id)

    def _load_state_in_tx(
        self, connection: sqlite3.Connection, stream_id: str
    ) -> KernelState:
        stream = connection.execute(
            "SELECT * FROM streams WHERE stream_id=?", (stream_id,)
        ).fetchone()
        if stream is None:
            raise StreamNotFound(stream_id)
        if stream["registry_sha256"] != self.registry_sha256:
            raise StoreIntegrityError("cell registry digest differs from stream authority")
        state = KernelState(remaining_budget=stream["initial_budget"])
        rows = connection.execute(
            "SELECT * FROM events WHERE stream_id=? ORDER BY sequence", (stream_id,)
        ).fetchall()
        for row in rows:
            raw = bytes(row["event_json"])
            value = json.loads(raw.decode("utf-8"))
            if canonical_json_bytes(value) != raw:
                raise StoreIntegrityError("stored event JSON is not canonical")
            if sha256(raw).hexdigest() != row["event_sha256"]:
                raise StoreIntegrityError("stored event SHA-256 mismatch")
            event = _event_from_value(value)
            if event.sequence != row["sequence"]:
                raise StoreIntegrityError("event payload sequence differs from row key")
            state = evolve(state, event)
        if state.version != stream["version"]:
            raise StoreIntegrityError("replayed version differs from stream version")
        if state_digest(state) != stream["state_sha256"]:
            raise StoreIntegrityError("replayed state digest differs from stream digest")
        return state

    def load_state(self, stream_id: str) -> KernelState:
        with self._connect() as connection:
            return self._load_state_in_tx(connection, stream_id)

    def _existing_receipt(
        self,
        connection: sqlite3.Connection,
        stream_id: str,
        command_key: str,
        intent_sha256: str,
    ) -> CommitReceipt | None:
        row = connection.execute(
            "SELECT intent_sha256,receipt_json FROM command_receipts WHERE stream_id=? AND command_key=?",
            (stream_id, command_key),
        ).fetchone()
        if row is None:
            return None
        if row["intent_sha256"] != intent_sha256:
            raise CommandIntentConflict(
                f"command key {command_key!r} was already used with different intent"
            )
        raw = bytes(row["receipt_json"])
        value = json.loads(raw.decode("utf-8"))
        if canonical_json_bytes(value) != raw:
            raise StoreIntegrityError("stored command receipt is not canonical")
        return _receipt_from_value(value, exact_retry=True)

    def _append_accepted_in_tx(
        self,
        connection: sqlite3.Connection,
        stream_id: str,
        state: KernelState,
        command: Command,
        accepted: Accepted,
        *,
        command_key: str,
        intent_sha256: str,
    ) -> CommitReceipt:
        sequences: list[int] = []
        effect_ids: list[str] = []
        for event in accepted.events:
            if event.sequence != state.version + 1:
                raise StoreIntegrityError("accepted event sequence is not contiguous")
            value = _event_value(event)
            raw = canonical_json_bytes(value)
            event_sha = sha256(raw).hexdigest()
            connection.execute(
                "INSERT INTO events(stream_id,sequence,event_type,event_json,event_sha256) VALUES(?,?,?,?,?)",
                (stream_id, event.sequence, value["type"], raw, event_sha),
            )
            sequences.append(event.sequence)
            for effect in effects(event):
                effect_value = _effect_value(effect)
                effect_raw = canonical_json_bytes(effect_value)
                effect_sha = sha256(effect_raw).hexdigest()
                effect_id = "fx-" + _sha256(
                    {
                        "protocol": STORE_PROTOCOL,
                        "stream_id": stream_id,
                        "source_sequence": event.sequence,
                        "effect_sha256": effect_sha,
                    }
                )
                connection.execute(
                    """
                    INSERT INTO outbox(
                        effect_id,stream_id,source_sequence,activation_id,status,
                        attempts,effect_json,effect_sha256
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        effect_id,
                        stream_id,
                        event.sequence,
                        effect.activation_id,
                        OutboxStatus.PENDING.value,
                        0,
                        effect_raw,
                        effect_sha,
                    ),
                )
                effect_ids.append(effect_id)
            state = evolve(state, event)

        committed_digest = state_digest(state)
        connection.execute(
            "UPDATE streams SET version=?,state_sha256=? WHERE stream_id=?",
            (state.version, committed_digest, stream_id),
        )
        receipt = CommitReceipt(
            stream_id=stream_id,
            command_key=command_key,
            intent_sha256=intent_sha256,
            event_sequences=tuple(sequences),
            outbox_effect_ids=tuple(effect_ids),
            committed_state_sha256=committed_digest,
            exact_retry=False,
        )
        connection.execute(
            "INSERT INTO command_receipts(stream_id,command_key,intent_sha256,receipt_json) VALUES(?,?,?,?)",
            (
                stream_id,
                command_key,
                intent_sha256,
                canonical_json_bytes(_receipt_value(receipt)),
            ),
        )
        return receipt

    def submit(self, stream_id: str, command: Command) -> CommitReceipt | Rejected:
        key = _command_key(command)
        intent_sha = _sha256(_command_value(command))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = self._existing_receipt(connection, stream_id, key, intent_sha)
            if existing is not None:
                connection.commit()
                return existing
            state = self._load_state_in_tx(connection, stream_id)
            decision = decide(self.registry, state, command)
            if isinstance(decision, Rejected):
                connection.rollback()
                return decision
            receipt = self._append_accepted_in_tx(
                connection,
                stream_id,
                state,
                command,
                decision,
                command_key=key,
                intent_sha256=intent_sha,
            )
            connection.commit()
            return receipt

    def _outbox_record(self, row: sqlite3.Row) -> OutboxRecord:
        raw = bytes(row["effect_json"])
        value = json.loads(raw.decode("utf-8"))
        if canonical_json_bytes(value) != raw:
            raise StoreIntegrityError("stored effect JSON is not canonical")
        if sha256(raw).hexdigest() != row["effect_sha256"]:
            raise StoreIntegrityError("stored effect SHA-256 mismatch")
        return OutboxRecord(
            effect_id=row["effect_id"],
            stream_id=row["stream_id"],
            source_sequence=row["source_sequence"],
            activation_id=row["activation_id"],
            status=OutboxStatus(row["status"]),
            attempts=row["attempts"],
            effect=_effect_from_value(value),
            effect_sha256=row["effect_sha256"],
            claim_token=row["claim_token"],
            last_error=row["last_error"],
            output_payload_sha256=row["output_payload_sha256"],
            completed_sequence=row["completed_sequence"],
        )

    def get_outbox(self, effect_id: str) -> OutboxRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM outbox WHERE effect_id=?", (effect_id,)
            ).fetchone()
        if row is None:
            raise OutboxStateConflict(f"unknown effect {effect_id!r}")
        return self._outbox_record(row)

    def list_outbox(self, *, status: OutboxStatus | None = None) -> tuple[OutboxRecord, ...]:
        with self._connect() as connection:
            if status is None:
                rows = connection.execute(
                    "SELECT * FROM outbox ORDER BY stream_id,source_sequence,effect_id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM outbox WHERE status=? ORDER BY stream_id,source_sequence,effect_id",
                    (status.value,),
                ).fetchall()
        return tuple(self._outbox_record(row) for row in rows)

    def claim_next(self, *, claim_token: str) -> OutboxRecord | None:
        if not claim_token:
            raise ValueError("claim_token must be non-empty")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT effect_id FROM outbox WHERE status=? ORDER BY stream_id,source_sequence,effect_id LIMIT 1",
                (OutboxStatus.PENDING.value,),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            effect_id = row["effect_id"]
            changed = connection.execute(
                """
                UPDATE outbox
                SET status=?,attempts=attempts+1,claim_token=?,last_error=NULL
                WHERE effect_id=? AND status=?
                """,
                (
                    OutboxStatus.IN_FLIGHT.value,
                    claim_token,
                    effect_id,
                    OutboxStatus.PENDING.value,
                ),
            ).rowcount
            if changed != 1:
                connection.rollback()
                return None
            claimed = connection.execute(
                "SELECT * FROM outbox WHERE effect_id=?", (effect_id,)
            ).fetchone()
            connection.commit()
        return self._outbox_record(claimed)

    def mark_safe_failure(
        self, effect_id: str, *, claim_token: str, reason: str
    ) -> OutboxRecord:
        if not reason:
            raise ValueError("reason must be non-empty")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """
                UPDATE outbox SET status=?,claim_token=NULL,last_error=?
                WHERE effect_id=? AND status=? AND claim_token=?
                """,
                (
                    OutboxStatus.PENDING.value,
                    reason,
                    effect_id,
                    OutboxStatus.IN_FLIGHT.value,
                    claim_token,
                ),
            ).rowcount
            if changed != 1:
                connection.rollback()
                raise OutboxStateConflict("safe failure does not own an in-flight effect")
            row = connection.execute(
                "SELECT * FROM outbox WHERE effect_id=?", (effect_id,)
            ).fetchone()
            connection.commit()
        return self._outbox_record(row)

    def mark_unknown(
        self, effect_id: str, *, claim_token: str, reason: str
    ) -> OutboxRecord:
        if not reason:
            raise ValueError("reason must be non-empty")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """
                UPDATE outbox SET status=?,last_error=?
                WHERE effect_id=? AND status=? AND claim_token=?
                """,
                (
                    OutboxStatus.UNKNOWN_OUTCOME.value,
                    reason,
                    effect_id,
                    OutboxStatus.IN_FLIGHT.value,
                    claim_token,
                ),
            ).rowcount
            if changed != 1:
                connection.rollback()
                raise OutboxStateConflict("unknown outcome does not own an in-flight effect")
            row = connection.execute(
                "SELECT * FROM outbox WHERE effect_id=?", (effect_id,)
            ).fetchone()
            connection.commit()
        return self._outbox_record(row)

    def abandon_unknown(self, effect_id: str, *, reason: str) -> OutboxRecord:
        if not reason:
            raise ValueError("reason must be non-empty")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """
                UPDATE outbox SET status=?,last_error=?
                WHERE effect_id=? AND status=?
                """,
                (
                    OutboxStatus.FAILED_PERMANENT.value,
                    reason,
                    effect_id,
                    OutboxStatus.UNKNOWN_OUTCOME.value,
                ),
            ).rowcount
            if changed != 1:
                connection.rollback()
                raise OutboxStateConflict("only an unknown outcome can be abandoned")
            row = connection.execute(
                "SELECT * FROM outbox WHERE effect_id=?", (effect_id,)
            ).fetchone()
            connection.commit()
        return self._outbox_record(row)

    def _complete_in_tx(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        output: PacketEnvelope,
        *,
        allowed_status: OutboxStatus,
        claim_token: str | None,
    ) -> CommitReceipt:
        status = OutboxStatus(row["status"])
        if status is OutboxStatus.SUCCEEDED:
            if row["output_payload_sha256"] != output.payload_sha256:
                raise OutboxStateConflict("completed effect has a different output digest")
            receipt_row = connection.execute(
                "SELECT receipt_json FROM command_receipts WHERE stream_id=? AND command_key=?",
                (row["stream_id"], f"complete:{row['activation_id']}"),
            ).fetchone()
            if receipt_row is None:
                raise StoreIntegrityError("succeeded outbox lacks completion receipt")
            return _receipt_from_value(
                json.loads(bytes(receipt_row["receipt_json"]).decode("utf-8")),
                exact_retry=True,
            )
        if status is not allowed_status:
            raise OutboxStateConflict(
                f"effect status {status.value} cannot complete as {allowed_status.value}"
            )
        if allowed_status is OutboxStatus.IN_FLIGHT and row["claim_token"] != claim_token:
            raise OutboxStateConflict("claim token does not own the in-flight effect")

        state = self._load_state_in_tx(connection, row["stream_id"])
        command = RecordCellOutput(
            expected_version=state.version,
            activation_id=row["activation_id"],
            output=output,
        )
        key = _command_key(command)
        intent_sha = _sha256(_command_value(command))
        existing = self._existing_receipt(
            connection, row["stream_id"], key, intent_sha
        )
        if existing is not None:
            receipt = existing
        else:
            decision = decide(self.registry, state, command)
            if isinstance(decision, Rejected):
                raise OutboxStateConflict(
                    f"typed completion rejected: {decision.reason.value}: {decision.detail}"
                )
            receipt = self._append_accepted_in_tx(
                connection,
                row["stream_id"],
                state,
                command,
                decision,
                command_key=key,
                intent_sha256=intent_sha,
            )
        completed_sequence = receipt.event_sequences[-1]
        connection.execute(
            """
            UPDATE outbox SET
                status=?,claim_token=NULL,last_error=NULL,
                output_payload_sha256=?,completed_sequence=?
            WHERE effect_id=?
            """,
            (
                OutboxStatus.SUCCEEDED.value,
                output.payload_sha256,
                completed_sequence,
                row["effect_id"],
            ),
        )
        return receipt

    def complete_claimed(
        self, effect_id: str, *, claim_token: str, output: PacketEnvelope
    ) -> CommitReceipt:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM outbox WHERE effect_id=?", (effect_id,)
            ).fetchone()
            if row is None:
                connection.rollback()
                raise OutboxStateConflict(f"unknown effect {effect_id!r}")
            receipt = self._complete_in_tx(
                connection,
                row,
                output,
                allowed_status=OutboxStatus.IN_FLIGHT,
                claim_token=claim_token,
            )
            connection.commit()
            return receipt

    def reconcile_completed(
        self, effect_id: str, *, output: PacketEnvelope
    ) -> CommitReceipt:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM outbox WHERE effect_id=?", (effect_id,)
            ).fetchone()
            if row is None:
                connection.rollback()
                raise OutboxStateConflict(f"unknown effect {effect_id!r}")
            receipt = self._complete_in_tx(
                connection,
                row,
                output,
                allowed_status=OutboxStatus.UNKNOWN_OUTCOME,
                claim_token=None,
            )
            connection.commit()
            return receipt

    def dispatch_one(
        self,
        *,
        port: CellPort,
        claim_token: str,
    ) -> DispatchReceipt | None:
        record = self.claim_next(claim_token=claim_token)
        if record is None:
            return None
        try:
            output = port.invoke(record.effect)
        except Exception as error:  # adapter boundary intentionally catches typed and unknown failures
            safe_to_retry = bool(getattr(error, "safe_to_retry", False))
            if safe_to_retry:
                self.mark_safe_failure(
                    record.effect_id,
                    claim_token=claim_token,
                    reason=f"{type(error).__name__}: {error}",
                )
                return DispatchReceipt(
                    effect_id=record.effect_id,
                    status=OutboxStatus.PENDING,
                    port_called=True,
                    completion=None,
                    error=str(error),
                )
            self.mark_unknown(
                record.effect_id,
                claim_token=claim_token,
                reason=f"{type(error).__name__}: {error}",
            )
            return DispatchReceipt(
                effect_id=record.effect_id,
                status=OutboxStatus.UNKNOWN_OUTCOME,
                port_called=True,
                completion=None,
                error=str(error),
            )
        completion = self.complete_claimed(
            record.effect_id,
            claim_token=claim_token,
            output=output,
        )
        return DispatchReceipt(
            effect_id=record.effect_id,
            status=OutboxStatus.SUCCEEDED,
            port_called=True,
            completion=completion,
        )

    def event_count(self, stream_id: str) -> int:
        with self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM events WHERE stream_id=?", (stream_id,)
                ).fetchone()[0]
            )

    def command_receipt_count(self, stream_id: str) -> int:
        with self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM command_receipts WHERE stream_id=?",
                    (stream_id,),
                ).fetchone()[0]
            )


__all__ = [
    "CommandIntentConflict",
    "CommitReceipt",
    "DispatchReceipt",
    "OutboxRecord",
    "OutboxStateConflict",
    "OutboxStatus",
    "STORE_PROTOCOL",
    "STORE_SCHEMA_VERSION",
    "SqliteCellRuntime",
    "StoreError",
    "StoreIntegrityError",
    "StreamNotFound",
]
