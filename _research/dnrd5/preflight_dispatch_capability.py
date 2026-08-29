"""Fail-closed, evidence-root-bound dispatch capability for one DNRD-5 block.

This is an execution safety instrument, not an occurrence executor or a
scientific result.  It deliberately composes around a provider callable rather
than importing or changing ``provider_gateway``.  An integration must route
*every* provider invocation through :meth:`dispatch` for this capability to be
an effective boundary.
"""

from __future__ import annotations

import fcntl
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, TypeVar

from _research.dnrd5.canonical_json import canonical_bytes, canonical_sha256, parse_canonical


SCHEMA = "hswm-dnrd5-preflight-dispatch-capability/v1"
LEDGER_SCHEMA = "hswm-dnrd5-preflight-dispatch-ledger/v1"
NONCLAIM = (
    "EXECUTION_SAFETY_INSTRUMENT_ONLY_NOT_AN_OCCURRENCE_OR_CAUSAL_OR_HSWM_"
    "SCIENTIFIC_RESULT"
)
BLOCK_START = "BLOCK_START_DURABLE_BEFORE_ANY_PROVIDER_DISPATCH"
BLOCK_SUCCESS = "BLOCK_TERMINAL_NINE_SLOTS_CONSUMED"
BLOCK_DEFECT = "BLOCK_TERMINAL_DEFECT_OR_DISPATCH_FAILURE"
BLOCK_CRASH = "BLOCK_TERMINAL_CRASH_OR_INTERRUPTED_WITHOUT_SAFE_RESUME"
ZERO = "0" * 64
_CALL_CLASSES = (
    "PRE_OUTCOME_TRAJECTORY",
    "REVISION_PROPOSAL",
    "FRESH_PROBE",
)
_EXPECTED_CLASSES = (
    "PRE_OUTCOME_TRAJECTORY",
    "REVISION_PROPOSAL",
    "REVISION_PROPOSAL",
    "REVISION_PROPOSAL",
    "REVISION_PROPOSAL",
    "FRESH_PROBE",
    "FRESH_PROBE",
    "FRESH_PROBE",
    "FRESH_PROBE",
)
_T = TypeVar("_T")


class PreflightDispatchRefusal(RuntimeError):
    """The capability has refused a dispatch and is not safely usable."""


def _is_lower_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


@dataclass(frozen=True, slots=True)
class DispatchSlot:
    """One opaque, precommitted provider-call position in a single block."""

    call_id: str
    call_class: str
    call_commitment_sha256: str


@dataclass(frozen=True, slots=True)
class ProviderDispatchBinding:
    """Opaque correlation supplied only from an already-consumed slot."""

    capability_binding_sha256: str
    slot_ordinal: int
    call_id: str
    call_class: str
    call_commitment_sha256: str


@dataclass(frozen=True, slots=True)
class ProviderDispatchEvidence:
    """Result-only provider correlation; test doubles cannot impersonate it."""
    evidence_kind: str
    call_commitment_sha256: str
    provider_start_record_sha256: str | None
    provider_terminal_record_sha256: str | None
    receipt_sha256: str | None


def _validate_block_id(block_id: str) -> None:
    if (
        type(block_id) is not str
        or len(block_id) != len("DNRD5-BLOCK-0001")
        or not block_id.startswith("DNRD5-BLOCK-")
        or not block_id[-4:].isdigit()
        or not 1 <= int(block_id[-4:]) <= 300
    ):
        raise PreflightDispatchRefusal("block_id is outside DNRD-5's 300-block universe")


def _schedule_descriptor(slots: Sequence[DispatchSlot]) -> list[dict[str, str]]:
    if type(slots) not in {tuple, list} or len(slots) != 9:
        raise PreflightDispatchRefusal("a dispatch capability requires exactly nine slots")
    out: list[dict[str, str]] = []
    call_ids: set[str] = set()
    for ordinal, (slot, expected_class) in enumerate(zip(slots, _EXPECTED_CLASSES), 1):
        if type(slot) is not DispatchSlot:
            raise PreflightDispatchRefusal("every precommitted slot must be DispatchSlot")
        if (
            type(slot.call_id) is not str
            or not slot.call_id
            or len(slot.call_id.encode("utf-8")) > 256
            or slot.call_id in call_ids
        ):
            raise PreflightDispatchRefusal("slot call IDs must be unique bounded text")
        if slot.call_class not in _CALL_CLASSES or slot.call_class != expected_class:
            raise PreflightDispatchRefusal("nine-slot call grammar drifted")
        if not _is_lower_sha256(slot.call_commitment_sha256):
            raise PreflightDispatchRefusal("slot must bind an exact 256-bit call commitment")
        call_ids.add(slot.call_id)
        out.append({"ordinal": str(ordinal), "call_id": slot.call_id, "call_class": slot.call_class, "call_commitment_sha256": slot.call_commitment_sha256})
    return out


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_exclusive(path: Path, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(path.parent)


def _read_binding(path: Path) -> dict[str, Any]:
    try:
        value = parse_canonical(path.read_bytes())
    except Exception as error:
        raise PreflightDispatchRefusal("capability binding is not canonical") from error
    keys = {"schema_version", "block_id", "evidence_root_sha256", "schedule", "schedule_sha256", "nonclaim"}
    if type(value) is not dict or set(value) != keys:
        raise PreflightDispatchRefusal("capability binding key set drifted")
    if value["schema_version"] != SCHEMA or value["nonclaim"] != NONCLAIM:
        raise PreflightDispatchRefusal("capability binding schema or nonclaim drifted")
    _validate_block_id(value["block_id"])
    if not _is_lower_sha256(value["evidence_root_sha256"]):
        raise PreflightDispatchRefusal("capability evidence root digest is invalid")
    if canonical_sha256(value["schedule"]) != value["schedule_sha256"]:
        raise PreflightDispatchRefusal("capability schedule digest drifted")
    # Reuse the constructor validation on a decoded schedule without accepting
    # a caller-controlled call grammar.
    decoded = tuple(DispatchSlot(item["call_id"], item["call_class"], item["call_commitment_sha256"]) for item in value["schedule"])
    if _schedule_descriptor(decoded) != value["schedule"]:
        raise PreflightDispatchRefusal("capability schedule shape drifted")
    return value


def _read_ledger(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or not raw[:-1]:
        raise PreflightDispatchRefusal("dispatch ledger framing is invalid")
    previous = ZERO
    rows: list[dict[str, Any]] = []
    for ordinal, line in enumerate(raw[:-1].split(b"\n"), 1):
        try:
            row = parse_canonical(line)
        except Exception as error:
            raise PreflightDispatchRefusal("dispatch ledger is not canonical") from error
        if type(row) is not dict or row.get("ordinal") != ordinal or row.get("previous_record_sha256") != previous:
            raise PreflightDispatchRefusal("dispatch ledger chronology drifted")
        core = {key: item for key, item in row.items() if key != "record_sha256"}
        if row.get("record_sha256") != canonical_sha256(core):
            raise PreflightDispatchRefusal("dispatch ledger hash chain drifted")
        previous = row["record_sha256"]
        rows.append(row)
    return rows


def _append(path: Path, core: dict[str, Any]) -> dict[str, Any]:
    fd = os.open(path, os.O_RDWR)
    with os.fdopen(fd, "r+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            rows = [] if handle.read() == b"" else _read_ledger(path)
            record = {
                **core,
                "ordinal": len(rows) + 1,
                "previous_record_sha256": rows[-1]["record_sha256"] if rows else ZERO,
            }
            record["record_sha256"] = canonical_sha256(record)
            handle.seek(0, os.SEEK_END)
            handle.write(canonical_bytes(record) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    _fsync_directory(path.parent)
    return record


class PreflightDispatchCapability:
    """One evidence-bound, non-resumable sequence of exactly nine dispatches."""

    def __init__(
        self, root: Path, evidence_root_bytes: bytes, *, _allow_open: bool = False
    ) -> None:
        if not isinstance(root, Path) or not root.is_dir():
            raise PreflightDispatchRefusal("capability root is not a directory")
        if type(evidence_root_bytes) is not bytes:
            raise PreflightDispatchRefusal("evidence root identity must be exact bytes")
        try:
            parse_canonical(evidence_root_bytes)
        except Exception as error:
            raise PreflightDispatchRefusal("evidence root identity must be canonical bytes") from error
        self._root = root
        self._binding_path = root / "dispatch_capability.json"
        self._ledger_path = root / "dispatch_capability.jsonl"
        self._lock_path = root / "dispatch_capability.lock"
        binding = _read_binding(self._binding_path)
        if binding["evidence_root_sha256"] != sha256(evidence_root_bytes).hexdigest():
            raise PreflightDispatchRefusal("provided evidence root identity is not capability-bound")
        self._binding = binding
        if not _allow_open:
            self._recover_interrupted_start()

    @classmethod
    def create(
        cls,
        root: Path,
        *,
        block_id: str,
        evidence_root_bytes: bytes,
        slots: Sequence[DispatchSlot],
    ) -> "PreflightDispatchCapability":
        if not isinstance(root, Path) or root.exists():
            raise PreflightDispatchRefusal("new capability root must not already exist")
        _validate_block_id(block_id)
        if type(evidence_root_bytes) is not bytes:
            raise PreflightDispatchRefusal("evidence root identity must be exact bytes")
        try:
            parse_canonical(evidence_root_bytes)
        except Exception as error:
            raise PreflightDispatchRefusal("evidence root identity must be canonical bytes") from error
        schedule = _schedule_descriptor(slots)
        root.mkdir(mode=0o700)
        _fsync_directory(root.parent)
        binding = {
            "schema_version": SCHEMA,
            "block_id": block_id,
            "evidence_root_sha256": sha256(evidence_root_bytes).hexdigest(),
            "schedule": schedule,
            "schedule_sha256": canonical_sha256(schedule),
            "nonclaim": NONCLAIM,
        }
        _write_exclusive(root / "dispatch_capability.json", canonical_bytes(binding))
        _write_exclusive(root / "dispatch_capability.jsonl", b"")
        _write_exclusive(root / "dispatch_capability.lock", b"")
        # The START record is written before this object can expose dispatch().
        # If this process dies immediately afterward, reopening terminalizes it
        # as a crash rather than allowing a potentially duplicate provider call.
        _append(
            root / "dispatch_capability.jsonl",
            {
                "schema_version": LEDGER_SCHEMA,
                "record_type": "START",
                "block_id": block_id,
                "evidence_root_sha256": binding["evidence_root_sha256"],
                "schedule_sha256": binding["schedule_sha256"],
                "terminal": BLOCK_START,
                "nonclaim": NONCLAIM,
            },
        )
        return cls(root, evidence_root_bytes, _allow_open=True)

    @property
    def block_id(self) -> str:
        return self._binding["block_id"]

    def binds_evidence_root(self, evidence_root_bytes: bytes, block_id: str) -> bool:
        """Return whether this live capability binds this exact gateway root."""
        return (
            type(evidence_root_bytes) is bytes
            and block_id == self.block_id
            and sha256(evidence_root_bytes).hexdigest()
            == self._binding["evidence_root_sha256"]
        )

    def provider_dispatch_binding(self, slot: DispatchSlot) -> ProviderDispatchBinding:
        """Expose the correlation only for the next live precommitted slot.

        This is descriptive evidence, not an authority issuer: ``dispatch``
        still has to consume the same slot before its callback can run.
        """
        if type(slot) is not DispatchSlot:
            raise PreflightDispatchRefusal("provider correlation requires an exact DispatchSlot")
        rows = self._rows_or_refuse_open()
        committed = [row for row in rows if row.get("record_type") == "CALL_TERMINAL"]
        expected = self._binding["schedule"][len(committed)] if len(committed) < 9 else None
        if expected is None or (slot.call_id, slot.call_class, slot.call_commitment_sha256) != (expected["call_id"], expected["call_class"], expected["call_commitment_sha256"]):
            raise PreflightDispatchRefusal("provider correlation is not the next evidence-bound slot")
        return ProviderDispatchBinding(
            canonical_sha256(self._binding), len(committed) + 1, slot.call_id, slot.call_class, slot.call_commitment_sha256
        )

    def _recover_interrupted_start(self) -> None:
        rows = _read_ledger(self._ledger_path)
        terminals = [row for row in rows if row.get("record_type") == "TERMINAL"]
        if len(terminals) > 1:
            raise PreflightDispatchRefusal("dispatch ledger has multiple block terminals")
        if terminals:
            return
        calls = [row for row in rows if row.get("record_type") == "CALL_TERMINAL"]
        # A fresh in-memory capability may continue only while the process that
        # issued it holds this instance.  Reopening any unterminated root is a
        # crash/restart boundary and therefore consumes the block permanently.
        if calls or len(rows) == 1:
            _append(
                self._ledger_path,
                {
                    "schema_version": LEDGER_SCHEMA,
                    "record_type": "TERMINAL",
                    "block_id": self.block_id,
                    "terminal": BLOCK_CRASH,
                    "consumed_slots": len(calls),
                    "nonclaim": NONCLAIM,
                },
            )

    def _rows_or_refuse_open(self) -> list[dict[str, Any]]:
        rows = _read_ledger(self._ledger_path)
        starts = [row for row in rows if row.get("record_type") == "START"]
        terminals = [row for row in rows if row.get("record_type") == "TERMINAL"]
        if len(starts) != 1 or len(terminals) > 1:
            raise PreflightDispatchRefusal("dispatch capability ledger is structurally closed")
        if terminals:
            raise PreflightDispatchRefusal("dispatch capability is permanently closed")
        call_starts = [row for row in rows if row.get("record_type") == "CALL_START"]
        call_terminals = [row for row in rows if row.get("record_type") == "CALL_TERMINAL"]
        started_slots = {row.get("slot_ordinal") for row in call_starts}
        terminal_slots = {row.get("slot_ordinal") for row in call_terminals}
        if started_slots != terminal_slots:
            # A durable pre-dispatch record means the provider callback may
            # already have begun.  It is never safe to infer a retry merely
            # because result evidence or a later append failed.
            self._close_defect("UNMATCHED_CALL_START")
            raise PreflightDispatchRefusal("dispatch capability has an unmatched durable CALL_START")
        return rows

    def dispatch(self, slot: DispatchSlot, transport: Callable[[], _T]) -> _T:
        """Run one precommitted call only after all local preflight checks pass.

        ``transport`` is intentionally a zero-knowledge callable.  Production
        integration may put a provider-gateway execution inside it; unit tests
        can use a no-network fake.  Any raised exception terminalizes the
        block, and an interrupted process cannot resume it.
        """
        lock_fd = os.open(self._lock_path, os.O_RDWR)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            return self._dispatch_locked(slot, transport)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def _dispatch_locked(self, slot: DispatchSlot, transport: Callable[[], _T]) -> _T:
        if type(slot) is not DispatchSlot or not callable(transport):
            self._close_defect("INVALID_DISPATCH_ARGUMENT")
            raise PreflightDispatchRefusal("dispatch slot and transport must be declared")
        rows = self._rows_or_refuse_open()
        committed = [row for row in rows if row.get("record_type") == "CALL_TERMINAL"]
        expected = self._binding["schedule"][len(committed)] if len(committed) < 9 else None
        if expected is None or {"call_id": slot.call_id, "call_class": slot.call_class, "call_commitment_sha256": slot.call_commitment_sha256} != {
            "call_id": expected["call_id"], "call_class": expected["call_class"]
            , "call_commitment_sha256": expected["call_commitment_sha256"]
        }:
            self._close_defect("SLOT_ORDER_OR_IDENTITY_DRIFT")
            raise PreflightDispatchRefusal("dispatch slot is not the next evidence-bound slot")
        _append(
            self._ledger_path,
            {
                "schema_version": LEDGER_SCHEMA,
                "record_type": "CALL_START",
                "block_id": self.block_id,
                "slot_ordinal": len(committed) + 1,
                "call_id": slot.call_id,
                "call_class": slot.call_class,
                "call_commitment_sha256": slot.call_commitment_sha256,
                "capability_binding_sha256": canonical_sha256(self._binding),
                "terminal": "DURABLE_BEFORE_SINGLE_PROVIDER_DISPATCH",
                "nonclaim": NONCLAIM,
            },
        )
        try:
            result = transport()
            evidence = result.dispatch_evidence if hasattr(result, "dispatch_evidence") and type(result.dispatch_evidence) is ProviderDispatchEvidence else ProviderDispatchEvidence("TEST_DOUBLE", slot.call_commitment_sha256, None, None, None)
            if evidence.call_commitment_sha256 != slot.call_commitment_sha256:
                raise PreflightDispatchRefusal("result evidence commitment drifted")
            _append(
                self._ledger_path,
                {
                    "schema_version": LEDGER_SCHEMA, "record_type": "CALL_TERMINAL",
                    "block_id": self.block_id, "slot_ordinal": len(committed) + 1,
                    "call_id": slot.call_id, "call_class": slot.call_class,
                    "call_commitment_sha256": slot.call_commitment_sha256,
                    "capability_binding_sha256": canonical_sha256(self._binding),
                    "evidence_kind": evidence.evidence_kind,
                    "provider_start_record_sha256": evidence.provider_start_record_sha256,
                    "provider_terminal_record_sha256": evidence.provider_terminal_record_sha256,
                    "receipt_sha256": evidence.receipt_sha256,
                    "outcome": "SUCCEEDED", "terminal": "SINGLE_PRECOMMITTED_SLOT_RETURNED",
                    "nonclaim": NONCLAIM,
                },
            )
        except BaseException:
            # This covers transport, hostile/lazy result evidence, and every
            # persistence step after CALL_START.  A failed terminal append is
            # itself an irrecoverable ambiguity; _rows_or_refuse_open also
            # detects that durable unmatched start in this live instance.
            self._close_defect("POST_CALL_START_FAILURE")
            raise
        if len(committed) + 1 == 9:
            _append(
                self._ledger_path,
                {
                    "schema_version": LEDGER_SCHEMA,
                    "record_type": "TERMINAL",
                    "block_id": self.block_id,
                    "terminal": BLOCK_SUCCESS,
                    "consumed_slots": 9,
                    "nonclaim": NONCLAIM,
                },
            )
        return result

    def _close_defect(self, defect: str) -> None:
        try:
            rows = _read_ledger(self._ledger_path)
            if any(row.get("record_type") == "TERMINAL" for row in rows):
                return
            _append(
                self._ledger_path,
                {
                    "schema_version": LEDGER_SCHEMA,
                    "record_type": "TERMINAL",
                    "block_id": self.block_id,
                    "terminal": BLOCK_DEFECT,
                    "defect": defect,
                    "consumed_slots": sum(row.get("record_type") == "CALL_TERMINAL" for row in rows),
                    "nonclaim": NONCLAIM,
                },
            )
        except Exception:
            # If the evidence journal itself is corrupt, fail closed.  A caller
            # must never infer that a failed terminal append makes dispatch safe.
            return


def read_dispatch_capability_ledger(root: Path) -> tuple[dict[str, Any], ...]:
    """Read the hash-verified local audit chain; it grants no new authority."""
    if not isinstance(root, Path):
        raise PreflightDispatchRefusal("capability root must be a Path")
    return tuple(_read_ledger(root / "dispatch_capability.jsonl"))


def validate_completed_dispatch_capability(root: Path) -> tuple[dict[str, Any], ...]:
    """Validate a complete nine-slot provider-evidence capability journal."""
    binding = _read_binding(root / "dispatch_capability.json")
    rows = list(read_dispatch_capability_ledger(root))
    expected_record_types = [
        "START",
        *(record_type for _ in range(9) for record_type in ("CALL_START", "CALL_TERMINAL")),
        "TERMINAL",
    ]
    if [row.get("record_type") for row in rows] != expected_record_types:
        raise PreflightDispatchRefusal(
            "completed capability record grammar or terminal position drifted"
        )
    common_keys = {
        "schema_version",
        "record_type",
        "block_id",
        "terminal",
        "nonclaim",
        "ordinal",
        "previous_record_sha256",
        "record_sha256",
    }
    start_keys = common_keys | {"evidence_root_sha256", "schedule_sha256"}
    call_start_keys = common_keys | {
        "slot_ordinal",
        "call_id",
        "call_class",
        "call_commitment_sha256",
        "capability_binding_sha256",
    }
    call_terminal_keys = call_start_keys | {
        "evidence_kind",
        "provider_start_record_sha256",
        "provider_terminal_record_sha256",
        "receipt_sha256",
        "outcome",
    }
    terminal_keys = common_keys | {"consumed_slots"}
    if (
        set(rows[0]) != start_keys
        or any(set(rows[index]) != call_start_keys for index in range(1, 19, 2))
        or any(set(rows[index]) != call_terminal_keys for index in range(2, 20, 2))
        or set(rows[-1]) != terminal_keys
    ):
        raise PreflightDispatchRefusal("completed capability record key set drifted")
    if (
        rows[0].get("schema_version") != LEDGER_SCHEMA
        or rows[0].get("block_id") != binding["block_id"]
        or rows[0].get("evidence_root_sha256") != binding["evidence_root_sha256"]
        or rows[0].get("schedule_sha256") != binding["schedule_sha256"]
        or rows[0].get("terminal") != BLOCK_START
        or rows[-1].get("schema_version") != LEDGER_SCHEMA
        or rows[-1].get("block_id") != binding["block_id"]
        or rows[-1].get("consumed_slots") != 9
        or any(row.get("nonclaim") != NONCLAIM for row in rows)
    ):
        raise PreflightDispatchRefusal("completed capability root or terminal binding drifted")
    starts = [row for row in rows if row.get("record_type") == "CALL_START"]
    calls = [row for row in rows if row.get("record_type") == "CALL_TERMINAL"]
    terminal = [row for row in rows if row.get("record_type") == "TERMINAL"]
    if len(starts) != 9 or len(calls) != 9 or len(terminal) != 1 or terminal[0].get("terminal") != BLOCK_SUCCESS:
        raise PreflightDispatchRefusal("completed capability requires one exact nine-slot terminal")
    digest = canonical_sha256(binding)
    for index, (start, call, expected) in enumerate(zip(starts, calls, binding["schedule"], strict=True), 1):
        if any(start.get(key) != expected[key] for key in ("call_id", "call_class", "call_commitment_sha256")) or any(call.get(key) != expected[key] for key in ("call_id", "call_class", "call_commitment_sha256")):
            raise PreflightDispatchRefusal("capability call commitment schedule drifted")
        if start.get("block_id") != binding["block_id"] or call.get("block_id") != binding["block_id"] or start.get("slot_ordinal") != index or call.get("slot_ordinal") != index or start.get("capability_binding_sha256") != digest or call.get("capability_binding_sha256") != digest:
            raise PreflightDispatchRefusal("capability slot correlation drifted")
        if (
            start.get("schema_version") != LEDGER_SCHEMA
            or call.get("schema_version") != LEDGER_SCHEMA
            or start.get("terminal") != "DURABLE_BEFORE_SINGLE_PROVIDER_DISPATCH"
            or call.get("terminal") != "SINGLE_PRECOMMITTED_SLOT_RETURNED"
            or call.get("outcome") != "SUCCEEDED"
            or call.get("evidence_kind") != "PROVIDER_EVIDENCE"
            or any(
                not _is_lower_sha256(call.get(key))
                for key in (
                    "provider_start_record_sha256",
                    "provider_terminal_record_sha256",
                    "receipt_sha256",
                )
            )
        ):
            raise PreflightDispatchRefusal("completed capability contains non-provider or incomplete result evidence")
    return tuple(calls)
