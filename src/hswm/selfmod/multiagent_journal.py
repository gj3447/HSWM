"""Durable idempotency journal for structural HSWM execution.

The self-model database remains responsible only for tokens and snapshots.
This sibling journal reserves an episode before external effects, records each
step request before dispatch, and stores validated completions.  An in-flight
or unknown effect is never blindly invoked again.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from hswm.cells.runtime import InvokeCellEffect, PacketEnvelope

from .contracts import canonical_json_bytes, canonical_sha256


JOURNAL_SCHEMA_VERSION = 2


class MultiAgentJournalError(RuntimeError):
    pass


class ExecutionIntentConflict(MultiAgentJournalError):
    pass


class ExecutionNotRunnable(MultiAgentJournalError):
    pass


class StepIntentConflict(MultiAgentJournalError):
    pass


class StepOutcomeUnknown(MultiAgentJournalError):
    pass


class ExecutionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"
    FAILED_PERMANENT = "FAILED_PERMANENT"


class JournalStepStatus(str, Enum):
    PENDING = "PENDING"
    IN_FLIGHT = "IN_FLIGHT"
    SUCCEEDED = "SUCCEEDED"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    episode_id: str
    intent: Mapping[str, Any]
    intent_sha256: str
    status: ExecutionStatus
    receipt: Mapping[str, Any] | None
    exact_retry: bool
    last_error: str | None


@dataclass(frozen=True, slots=True)
class JournalStepRecord:
    episode_id: str
    sequence: int
    cell_id: str
    effect_sha256: str
    status: JournalStepStatus
    attempts: int
    claim_token: str | None
    output: PacketEnvelope | None
    last_error: str | None


def _packet_value(packet: PacketEnvelope) -> dict[str, Any]:
    return {
        "packet_id": packet.packet_id,
        "packet_type": packet.packet_type,
        "payload": packet.payload,
        "payload_sha256": packet.payload_sha256,
        "provenance_sha256": packet.provenance_sha256,
    }


def _packet_from_value(value: Any) -> PacketEnvelope:
    expected = {
        "packet_id",
        "packet_type",
        "payload",
        "payload_sha256",
        "provenance_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise MultiAgentJournalError("stored packet field set is invalid")
    packet = PacketEnvelope(
        packet_id=value["packet_id"],
        packet_type=value["packet_type"],
        payload=value["payload"],
        payload_sha256=value["payload_sha256"],
        provenance_sha256=value["provenance_sha256"],
    )
    if canonical_sha256(packet.payload) != packet.payload_sha256:
        raise MultiAgentJournalError("stored packet payload digest mismatch")
    return packet


def _effect_value(effect: InvokeCellEffect) -> dict[str, Any]:
    return {
        "activation_id": effect.activation_id,
        "cell_id": effect.cell_id,
        "input": _packet_value(effect.input),
        "expected_output_type": effect.expected_output_type,
    }


def _effect_from_value(value: Any) -> InvokeCellEffect:
    expected = {
        "activation_id",
        "cell_id",
        "input",
        "expected_output_type",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise MultiAgentJournalError("stored effect field set is invalid")
    return InvokeCellEffect(
        activation_id=value["activation_id"],
        cell_id=value["cell_id"],
        input=_packet_from_value(value["input"]),
        expected_output_type=value["expected_output_type"],
    )


def _decode(raw: bytes, digest: str, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MultiAgentJournalError(f"stored {label} is invalid JSON") from error
    if not isinstance(value, Mapping) or canonical_json_bytes(value) != raw:
        raise MultiAgentJournalError(f"stored {label} is not canonical")
    if canonical_sha256(value) != digest:
        raise MultiAgentJournalError(f"stored {label} digest mismatch")
    return value


class SQLiteMultiAgentJournal:
    """Transactional reservation and step-completion journal."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
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
            if version not in (0, JOURNAL_SCHEMA_VERSION):
                raise MultiAgentJournalError(
                    f"unsupported multi-agent journal schema {version}"
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    episode_id TEXT PRIMARY KEY,
                    intent_json BLOB NOT NULL,
                    intent_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN (
                        'ACTIVE', 'COMPLETED', 'UNKNOWN_OUTCOME',
                        'FAILED_PERMANENT'
                    )),
                    receipt_json BLOB,
                    receipt_sha256 TEXT,
                    last_error TEXT
                );
                CREATE TABLE IF NOT EXISTS steps (
                    episode_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL CHECK(sequence > 0),
                    cell_id TEXT NOT NULL,
                    effect_json BLOB NOT NULL,
                    effect_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN (
                        'PENDING', 'IN_FLIGHT', 'SUCCEEDED', 'UNKNOWN_OUTCOME'
                    )),
                    attempts INTEGER NOT NULL CHECK(attempts >= 0),
                    claim_token TEXT,
                    output_json BLOB,
                    output_sha256 TEXT,
                    last_error TEXT,
                    PRIMARY KEY(episode_id, sequence),
                    FOREIGN KEY(episode_id) REFERENCES executions(episode_id)
                );
                """
            )
            connection.execute(f"PRAGMA user_version={JOURNAL_SCHEMA_VERSION}")

    def _execution_record(self, row: sqlite3.Row, *, exact_retry: bool) -> ExecutionRecord:
        intent = _decode(
            bytes(row["intent_json"]), row["intent_sha256"], "execution intent"
        )
        receipt: Mapping[str, Any] | None = None
        if row["receipt_json"] is not None:
            if row["receipt_sha256"] is None:
                raise MultiAgentJournalError("stored receipt digest is missing")
            receipt = _decode(
                bytes(row["receipt_json"]),
                row["receipt_sha256"],
                "execution receipt",
            )
        status = ExecutionStatus(row["status"])
        if status is ExecutionStatus.COMPLETED and receipt is None:
            raise MultiAgentJournalError("completed execution has no receipt")
        if status is not ExecutionStatus.COMPLETED and receipt is not None:
            raise MultiAgentJournalError("unfinished execution carries a receipt")
        return ExecutionRecord(
            episode_id=row["episode_id"],
            intent=intent,
            intent_sha256=row["intent_sha256"],
            status=status,
            receipt=receipt,
            exact_retry=exact_retry,
            last_error=row["last_error"],
        )

    def reserve_execution(
        self,
        *,
        episode_id: str,
        intent: Mapping[str, Any],
    ) -> ExecutionRecord:
        raw = canonical_json_bytes(intent)
        digest = canonical_sha256(intent)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM executions WHERE episode_id=?", (episode_id,)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO executions VALUES(?,?,?,?,NULL,NULL,NULL)",
                    (episode_id, raw, digest, ExecutionStatus.ACTIVE.value),
                )
                row = connection.execute(
                    "SELECT * FROM executions WHERE episode_id=?", (episode_id,)
                ).fetchone()
                connection.commit()
                return self._execution_record(row, exact_retry=False)
            _decode(
                bytes(row["intent_json"]), row["intent_sha256"], "execution intent"
            )
            if row["intent_sha256"] != digest or bytes(row["intent_json"]) != raw:
                connection.rollback()
                raise ExecutionIntentConflict(
                    f"episode {episode_id!r} was reserved with a different intent"
                )
            connection.commit()
        return self._execution_record(row, exact_retry=True)

    def execution_record(self, *, episode_id: str) -> ExecutionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM executions WHERE episode_id=?", (episode_id,)
            ).fetchone()
        return None if row is None else self._execution_record(row, exact_retry=True)

    def _step_record(self, row: sqlite3.Row) -> JournalStepRecord:
        effect_value = _decode(
            bytes(row["effect_json"]), row["effect_sha256"], "step effect"
        )
        _effect_from_value(effect_value)
        output: PacketEnvelope | None = None
        if row["output_json"] is not None:
            if row["output_sha256"] is None:
                raise MultiAgentJournalError("stored step output digest is missing")
            output_value = _decode(
                bytes(row["output_json"]), row["output_sha256"], "step output"
            )
            output = _packet_from_value(output_value)
        status = JournalStepStatus(row["status"])
        if status is JournalStepStatus.SUCCEEDED and output is None:
            raise MultiAgentJournalError("succeeded step has no output")
        if status is not JournalStepStatus.SUCCEEDED and output is not None:
            raise MultiAgentJournalError("unfinished step carries an output")
        return JournalStepRecord(
            episode_id=row["episode_id"],
            sequence=row["sequence"],
            cell_id=row["cell_id"],
            effect_sha256=row["effect_sha256"],
            status=status,
            attempts=row["attempts"],
            claim_token=row["claim_token"],
            output=output,
            last_error=row["last_error"],
        )

    def reserve_step(
        self,
        *,
        episode_id: str,
        sequence: int,
        cell_id: str,
        effect: InvokeCellEffect,
    ) -> JournalStepRecord:
        effect_value = _effect_value(effect)
        raw = canonical_json_bytes(effect_value)
        digest = canonical_sha256(effect_value)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            execution = connection.execute(
                "SELECT status,last_error FROM executions WHERE episode_id=?",
                (episode_id,),
            ).fetchone()
            if execution is None:
                connection.rollback()
                raise ExecutionNotRunnable("execution was not reserved")
            if execution["status"] != ExecutionStatus.ACTIVE.value:
                connection.rollback()
                raise ExecutionNotRunnable(
                    f"execution is {execution['status']}: {execution['last_error'] or ''}"
                )
            row = connection.execute(
                "SELECT * FROM steps WHERE episode_id=? AND sequence=?",
                (episode_id, sequence),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO steps(
                        episode_id,sequence,cell_id,effect_json,effect_sha256,
                        status,attempts
                    ) VALUES(?,?,?,?,?,?,0)
                    """,
                    (
                        episode_id,
                        sequence,
                        cell_id,
                        raw,
                        digest,
                        JournalStepStatus.PENDING.value,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM steps WHERE episode_id=? AND sequence=?",
                    (episode_id, sequence),
                ).fetchone()
                connection.commit()
                return self._step_record(row)
            _decode(bytes(row["effect_json"]), row["effect_sha256"], "step effect")
            if (
                row["cell_id"] != cell_id
                or row["effect_sha256"] != digest
                or bytes(row["effect_json"]) != raw
            ):
                connection.rollback()
                raise StepIntentConflict(
                    f"step {sequence} was reserved with a different intent"
                )
            connection.commit()
        return self._step_record(row)

    def claim_step(
        self,
        *,
        episode_id: str,
        sequence: int,
        claim_token: str,
    ) -> JournalStepRecord:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM steps WHERE episode_id=? AND sequence=?",
                (episode_id, sequence),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise StepIntentConflict("step was not reserved")
            status = JournalStepStatus(row["status"])
            if status is not JournalStepStatus.PENDING:
                connection.rollback()
                raise StepOutcomeUnknown(
                    f"step {sequence} is {status.value}; external dispatch is forbidden"
                )
            changed = connection.execute(
                """
                UPDATE steps SET status=?,attempts=attempts+1,claim_token=?,last_error=NULL
                WHERE episode_id=? AND sequence=? AND status=?
                """,
                (
                    JournalStepStatus.IN_FLIGHT.value,
                    claim_token,
                    episode_id,
                    sequence,
                    JournalStepStatus.PENDING.value,
                ),
            ).rowcount
            if changed != 1:
                connection.rollback()
                raise StepOutcomeUnknown("step claim lost a concurrent race")
            row = connection.execute(
                "SELECT * FROM steps WHERE episode_id=? AND sequence=?",
                (episode_id, sequence),
            ).fetchone()
            connection.commit()
        return self._step_record(row)

    def complete_step(
        self,
        *,
        episode_id: str,
        sequence: int,
        claim_token: str,
        output: PacketEnvelope,
    ) -> JournalStepRecord:
        output_value = _packet_value(output)
        raw = canonical_json_bytes(output_value)
        digest = canonical_sha256(output_value)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM steps WHERE episode_id=? AND sequence=?",
                (episode_id, sequence),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise StepIntentConflict("step was not reserved")
            effect_value = _decode(
                bytes(row["effect_json"]), row["effect_sha256"], "step effect"
            )
            effect = _effect_from_value(effect_value)
            if output.packet_type != effect.expected_output_type:
                connection.rollback()
                raise StepIntentConflict("step output packet type is invalid")
            if canonical_sha256(output.payload) != output.payload_sha256:
                connection.rollback()
                raise StepIntentConflict("step output payload digest is invalid")
            status = JournalStepStatus(row["status"])
            if status is JournalStepStatus.SUCCEEDED:
                _decode(
                    bytes(row["output_json"]), row["output_sha256"], "step output"
                )
                if row["output_sha256"] != digest or bytes(row["output_json"]) != raw:
                    connection.rollback()
                    raise StepIntentConflict("step already has a different output")
                connection.commit()
                return self._step_record(row)
            if (
                status is not JournalStepStatus.IN_FLIGHT
                or row["claim_token"] != claim_token
            ):
                connection.rollback()
                raise StepOutcomeUnknown("step completion does not own the dispatch")
            connection.execute(
                """
                UPDATE steps SET
                    status=?,claim_token=NULL,output_json=?,output_sha256=?,last_error=NULL
                WHERE episode_id=? AND sequence=?
                """,
                (
                    JournalStepStatus.SUCCEEDED.value,
                    raw,
                    digest,
                    episode_id,
                    sequence,
                ),
            )
            row = connection.execute(
                "SELECT * FROM steps WHERE episode_id=? AND sequence=?",
                (episode_id, sequence),
            ).fetchone()
            connection.commit()
        return self._step_record(row)

    def mark_step_failure(
        self,
        *,
        episode_id: str,
        sequence: int,
        claim_token: str,
        reason: str,
        safe_to_retry: bool,
    ) -> JournalStepRecord:
        next_status = (
            JournalStepStatus.PENDING
            if safe_to_retry
            else JournalStepStatus.UNKNOWN_OUTCOME
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """
                UPDATE steps SET status=?,claim_token=NULL,last_error=?
                WHERE episode_id=? AND sequence=? AND status=? AND claim_token=?
                """,
                (
                    next_status.value,
                    reason,
                    episode_id,
                    sequence,
                    JournalStepStatus.IN_FLIGHT.value,
                    claim_token,
                ),
            ).rowcount
            if changed != 1:
                connection.rollback()
                raise StepOutcomeUnknown("failed step does not own the dispatch")
            if not safe_to_retry:
                connection.execute(
                    "UPDATE executions SET status=?,last_error=? WHERE episode_id=?",
                    (ExecutionStatus.UNKNOWN_OUTCOME.value, reason, episode_id),
                )
            row = connection.execute(
                "SELECT * FROM steps WHERE episode_id=? AND sequence=?",
                (episode_id, sequence),
            ).fetchone()
            connection.commit()
        return self._step_record(row)

    def fail_execution(self, *, episode_id: str, reason: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """
                UPDATE executions SET status=?,last_error=?
                WHERE episode_id=? AND status=?
                """,
                (
                    ExecutionStatus.FAILED_PERMANENT.value,
                    reason,
                    episode_id,
                    ExecutionStatus.ACTIVE.value,
                ),
            ).rowcount
            if changed != 1:
                connection.rollback()
                raise ExecutionNotRunnable("execution cannot be failed from its state")
            connection.commit()

    def complete_execution(
        self,
        *,
        episode_id: str,
        receipt: Mapping[str, Any],
    ) -> ExecutionRecord:
        raw = canonical_json_bytes(receipt)
        digest = canonical_sha256(receipt)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM executions WHERE episode_id=?", (episode_id,)
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ExecutionNotRunnable("execution was not reserved")
            status = ExecutionStatus(row["status"])
            if status is ExecutionStatus.COMPLETED:
                _decode(
                    bytes(row["receipt_json"]),
                    row["receipt_sha256"],
                    "execution receipt",
                )
                if (
                    row["receipt_sha256"] != digest
                    or bytes(row["receipt_json"]) != raw
                ):
                    connection.rollback()
                    raise ExecutionIntentConflict(
                        "execution already has a different receipt"
                    )
                connection.commit()
                return self._execution_record(row, exact_retry=True)
            if status is not ExecutionStatus.ACTIVE:
                connection.rollback()
                raise ExecutionNotRunnable(
                    f"execution is {status.value}: {row['last_error'] or ''}"
                )
            connection.execute(
                """
                UPDATE executions SET
                    status=?,receipt_json=?,receipt_sha256=?,last_error=NULL
                WHERE episode_id=?
                """,
                (ExecutionStatus.COMPLETED.value, raw, digest, episode_id),
            )
            row = connection.execute(
                "SELECT * FROM executions WHERE episode_id=?", (episode_id,)
            ).fetchone()
            connection.commit()
        return self._execution_record(row, exact_retry=False)

    def step_record(self, *, episode_id: str, sequence: int) -> JournalStepRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM steps WHERE episode_id=? AND sequence=?",
                (episode_id, sequence),
            ).fetchone()
        if row is None:
            raise StepIntentConflict("unknown journal step")
        return self._step_record(row)


__all__ = [
    "ExecutionIntentConflict",
    "ExecutionNotRunnable",
    "ExecutionRecord",
    "ExecutionStatus",
    "JOURNAL_SCHEMA_VERSION",
    "JournalStepRecord",
    "JournalStepStatus",
    "MultiAgentJournalError",
    "SQLiteMultiAgentJournal",
    "StepIntentConflict",
    "StepOutcomeUnknown",
]
