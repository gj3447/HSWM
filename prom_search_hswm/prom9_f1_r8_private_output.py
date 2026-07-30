#!/usr/bin/env python3
"""Fenced private HSWM r8 outputs with post-RESERVED crash recovery.

The SQLite journal is the state-machine authority.  Output files are effects
owned by one non-blocking journal lease and advance monotonically through:

``RESERVATION_PREPARED -> RESERVED -> COMMIT_PREPARED -> COMMITTED``.

The payload is durably recorded before the reserved output inode is truncated.
A restart after ``RESERVED`` therefore reconciles the same effect instead of
blindly starting a second write path.  Interrupted namespace initialization
adopts only the exact journal-derived marker on the same private inode; every
other pre-``RESERVED`` observation is fail-closed.
"""
from __future__ import annotations

import fcntl
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import sqlite3
import stat
from collections.abc import Callable, Iterator, Mapping, Sequence

from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256


RESERVATION_SCHEMA = "hswm-prom9-f1-r8-private-output-reservation/v2"
JOURNAL_SCHEMA = "hswm-prom9-f1-r8-private-output-journal/v2"
JOURNAL_USER_VERSION = 2
JOURNAL_SCHEMA_SHA256 = (
    "359b975d8e3a0eaaef89e94f483c4d35a402b14cd247ff3bbdf79de52e1d17bb"
)
RESUME_PREFIX_SCHEMA = "hswm-prom9-f1-r8-resume-prefix/v1"
RESUME_PREFIX_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "db_genesis_sha256",
        "attempt_integrity",
        "spool_integrity",
        "attempt_db_identity",
        "spool_db_identity",
        "ordered_job_root_sha256",
        "job_count",
        "max_workers",
        "frontier_batch",
        "call_positions",
        "call_count",
        "item_run_count",
        "attempt_event_count",
        "spool_call_count",
        "event_chain_tip_sha256",
        "attempt_event_root_sha256",
        "attempt_live_audit",
        "spool_live_audit",
        "zero_count_genesis",
        "resume_prefix_sha256",
    }
)
RESUME_CALL_POSITION_FIELDS = frozenset(
    {
        "job_ordinal",
        "item_id",
        "arm_id",
        "call_indices",
        "item_run_committed",
    }
)
RESERVATION_STATES = (
    "RESERVATION_PREPARED",
    "RESERVED",
    "COMMIT_PREPARED",
    "COMMITTED",
)
RESERVATION_FSM = {
    "schema_version": "hswm-private-output-fsm-summary/v1",
    "name": "hswm-r8-private-output-reservation",
    "initial": "RESERVATION_PREPARED",
    "states": list(RESERVATION_STATES),
    "terminal_states": ["COMMITTED"],
    "transitions": [
        {
            "event": "MARKER_DURABLE",
            "from": "RESERVATION_PREPARED",
            "to": "RESERVED",
        },
        {
            "event": "EXACT_MARKER_RECOVERED",
            "from": "RESERVATION_PREPARED",
            "to": "RESERVED",
        },
        {
            "event": "PAYLOAD_DURABLE_IN_JOURNAL",
            "from": "RESERVED",
            "to": "COMMIT_PREPARED",
        },
        {
            "event": "SAME_INODE_READBACK_EXACT",
            "from": "COMMIT_PREPARED",
            "to": "COMMITTED",
        },
    ],
    "invalid_event_policy": "reject-without-state-change",
    "safety_properties": [
        "payload is journal-durable before output truncation",
        "state never moves backward",
        "only one non-blocking journal lease owns effects",
        "COMMIT_PREPARED is reconciled on the same inode",
        "SQLite commits are fully checkpointed and fsynced before success",
    ],
}

_META_COLUMNS = (
    "singleton",
    "schema_version",
    "run_id",
    "journal_path",
    "journal_dev",
    "journal_ino",
    "lock_path",
    "lock_dev",
    "lock_ino",
    "lock_nonce_sha256",
    "output_set_sha256",
)
_RESERVATION_COLUMNS = (
    "role",
    "output_path",
    "reservation_nonce",
    "marker_bytes",
    "marker_sha256",
    "output_dev",
    "output_ino",
    "state",
    "prepared_payload",
    "prepared_sha256",
    "prepared_size",
)
_AUDIT_COLUMNS = (
    "ordinal",
    "receipt_bytes",
    "receipt_sha256",
)


class PrivateOutputRefusal(RuntimeError):
    """An output namespace, journal, or reserved inode is unsafe."""


def _exclusive_process_group(group_id: int) -> bool:
    """Return whether a writable group contains only the effective user."""

    try:
        current = pwd.getpwuid(os.geteuid())
        group = grp.getgrgid(group_id)
        if group_id != current.pw_gid:
            return False
        members = set(group.gr_mem)
        members.update(
            entry.pw_name for entry in pwd.getpwall() if entry.pw_gid == group_id
        )
    except (KeyError, OSError):
        return False
    return members == {current.pw_name}


def _safe_directory_permissions(info: os.stat_result) -> bool:
    """Validate one directory in a no-follow canonical ancestry walk."""

    if not stat.S_ISDIR(info.st_mode):
        return False
    mode = stat.S_IMODE(info.st_mode)
    if mode & 0o002:
        return bool(info.st_mode & stat.S_ISVTX)
    if mode & 0o020:
        return (
            info.st_uid == os.geteuid()
            and _exclusive_process_group(int(info.st_gid))
        )
    return True


def _requires_owned_child(info: os.stat_result) -> bool:
    """Identify a shared sticky ancestor whose child must belong to us."""

    mode = stat.S_IMODE(info.st_mode)
    if not mode & 0o022:
        return False
    if (
        not mode & 0o002
        and info.st_uid == os.geteuid()
        and _exclusive_process_group(int(info.st_gid))
    ):
        return False
    return bool(info.st_mode & stat.S_ISVTX)


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise PrivateOutputRefusal("private output write made no progress")
        offset += written


def _canonical_parent(path: Path) -> tuple[Path, str]:
    target = Path(os.path.abspath(os.fspath(Path(path).expanduser())))
    if not target.name or target.name in {".", ".."}:
        raise PrivateOutputRefusal("private output name is invalid")
    current_fd = os.open(
        target.anchor,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        current_info = os.fstat(current_fd)
        if not _safe_directory_permissions(current_info):
            raise PrivateOutputRefusal(
                "private output ancestry is not safely writable"
            )
        require_owned = _requires_owned_child(current_info)
        for part in target.parent.parts[1:]:
            created = False
            try:
                os.mkdir(part, 0o700, dir_fd=current_fd)
                created = True
            except FileExistsError:
                pass
            except OSError as error:
                raise PrivateOutputRefusal(
                    "private output parent is unavailable"
                ) from error
            if created:
                os.fsync(current_fd)
            try:
                next_fd = os.open(
                    part,
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_CLOEXEC", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=current_fd,
                )
            except OSError as error:
                raise PrivateOutputRefusal(
                    "private output parent may not traverse a symlink"
                ) from error
            info = os.fstat(next_fd)
            if (
                not _safe_directory_permissions(info)
                or (require_owned and info.st_uid != os.geteuid())
            ):
                os.close(next_fd)
                raise PrivateOutputRefusal(
                    "private output parent is not a private directory"
                )
            require_owned = _requires_owned_child(info)
            os.close(current_fd)
            current_fd = next_fd
        os.fsync(current_fd)
    finally:
        os.close(current_fd)
    return target.parent, target.name


def _open_private_directory(path: Path, label: str) -> int:
    target = Path(os.path.abspath(os.fspath(path)))
    descriptor = os.open(
        target.anchor,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        info = os.fstat(descriptor)
        if not _safe_directory_permissions(info):
            raise PrivateOutputRefusal(f"{label} ancestry is unsafe")
        require_owned = _requires_owned_child(info)
        for part in target.parts[1:]:
            next_descriptor = os.open(
                part,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=descriptor,
            )
            info = os.fstat(next_descriptor)
            if (
                not _safe_directory_permissions(info)
                or (require_owned and info.st_uid != os.geteuid())
            ):
                os.close(next_descriptor)
                raise PrivateOutputRefusal(f"{label} is not a private directory")
            require_owned = _requires_owned_child(info)
            os.close(descriptor)
            descriptor = next_descriptor
        info = os.fstat(descriptor)
        if not _safe_directory_permissions(info):
            raise PrivateOutputRefusal(f"{label} is not a private directory")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _directory_identity(path: Path, descriptor: int, label: str) -> tuple[int, int]:
    path_descriptor = -1
    try:
        path_descriptor = _open_private_directory(path, label)
        path_info = os.fstat(path_descriptor)
        opened = os.fstat(descriptor)
    except OSError as error:
        raise PrivateOutputRefusal(f"{label} is unavailable") from error
    finally:
        if path_descriptor >= 0:
            os.close(path_descriptor)
    identity = (opened.st_dev, opened.st_ino)
    if (
        not stat.S_ISDIR(path_info.st_mode)
        or not stat.S_ISDIR(opened.st_mode)
        or (path_info.st_dev, path_info.st_ino) != identity
        or not _safe_directory_permissions(path_info)
        or not _safe_directory_permissions(opened)
    ):
        raise PrivateOutputRefusal(f"{label} identity drifted")
    return identity


def canonical_output_path(path: Path) -> Path:
    parent, name = _canonical_parent(path)
    return parent / name


def canonical_existing_private_path(path: Path, label: str) -> Path:
    """Return an existing-path spelling whose parent ancestry is private.

    Unlike :func:`canonical_output_path`, this read-side validator never creates
    a missing parent.  Leaf identity and permissions remain the caller's
    responsibility.
    """

    target = Path(os.path.abspath(os.fspath(Path(path).expanduser())))
    if not target.name or target.name in {".", ".."}:
        raise PrivateOutputRefusal(f"{label} name is invalid")
    descriptor = -1
    try:
        descriptor = _open_private_directory(target.parent, f"{label} parent")
    except (OSError, PrivateOutputRefusal) as error:
        raise PrivateOutputRefusal(f"{label} parent ancestry is unsafe") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return target


def _path_occupied(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as error:
        raise PrivateOutputRefusal("private output path is unavailable") from error
    return True


def _json_payload(value: Mapping[str, object]) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise PrivateOutputRefusal(
            "private output is not canonical finite JSON"
        ) from error


def _strict_mapping(payload: bytes, label: str) -> dict[str, object]:
    class DuplicateKey(ValueError):
        pass

    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise DuplicateKey(key)
            result[key] = value
        return result

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda item: (_ for _ in ()).throw(
                ValueError(f"non-finite value {item}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, DuplicateKey, ValueError) as error:
        raise PrivateOutputRefusal(f"{label} is not strict JSON") from error
    if not isinstance(value, dict) or _json_payload(value) != payload:
        raise PrivateOutputRefusal(f"{label} is not canonical JSON object bytes")
    return value


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_resume_prefix_audit(
    value: Mapping[str, object], *, run_id: str
) -> None:
    unsigned = dict(value)
    declared = unsigned.pop("resume_prefix_sha256", None)
    counts = (
        "job_count",
        "call_count",
        "item_run_count",
        "attempt_event_count",
        "spool_call_count",
    )
    digests = (
        "db_genesis_sha256",
        "ordered_job_root_sha256",
        "event_chain_tip_sha256",
        "attempt_event_root_sha256",
    )
    if (
        set(value) != RESUME_PREFIX_FIELDS
        or value.get("schema_version") != RESUME_PREFIX_SCHEMA
        or value.get("run_id") != run_id
        or not _is_sha256(declared)
        or canonical_sha256(unsigned) != declared
        or value.get("attempt_integrity") != "ok"
        or value.get("spool_integrity") != "ok"
        or any(not _is_sha256(value.get(field)) for field in digests)
        or any(
            type(value.get(field)) is not int or int(value[field]) < 0
            for field in counts
        )
        or type(value.get("max_workers")) is not int
        or not 1 <= int(value["max_workers"]) <= 8
        or type(value.get("frontier_batch")) is not int
        or int(value["frontier_batch"]) < -1
        or not isinstance(value.get("zero_count_genesis"), bool)
        or not isinstance(value.get("attempt_db_identity"), Mapping)
        or not isinstance(value.get("spool_db_identity"), Mapping)
        or not isinstance(value.get("attempt_live_audit"), Mapping)
        or not isinstance(value.get("spool_live_audit"), Mapping)
        or not isinstance(value.get("call_positions"), list)
    ):
        raise PrivateOutputRefusal("resume audit semantic binding drifted")
    for position in value["call_positions"]:
        if (
            not isinstance(position, Mapping)
            or set(position) != RESUME_CALL_POSITION_FIELDS
            or type(position.get("job_ordinal")) is not int
            or int(position["job_ordinal"]) < 0
            or not isinstance(position.get("item_id"), str)
            or not position["item_id"]
            or not isinstance(position.get("arm_id"), str)
            or not position["arm_id"]
            or not isinstance(position.get("call_indices"), list)
            or any(
                type(index) is not int or not 1 <= index <= 3
                for index in position["call_indices"]
            )
            or not isinstance(position.get("item_run_committed"), bool)
        ):
            raise PrivateOutputRefusal("resume audit call positions drifted")


def _read_descriptor(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    observed = bytearray()
    while block := os.read(descriptor, 1024 * 1024):
        observed.extend(block)
    return bytes(observed)


def _fsync_parent(path: Path, *, parent_fd: int | None = None) -> None:
    if parent_fd is not None:
        os.fsync(parent_fd)
        return
    descriptor = os.open(
        path.parent,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _preflight_sqlite_family(path: Path) -> None:
    for member in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        try:
            info = member.lstat()
        except FileNotFoundError:
            if member == path:
                raise PrivateOutputRefusal("reservation journal disappeared")
            continue
        except OSError as error:
            raise PrivateOutputRefusal(
                "reservation journal family is unavailable"
            ) from error
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise PrivateOutputRefusal(
                "reservation journal family is not private"
            )
    if _path_occupied(Path(f"{path}-journal")):
        raise PrivateOutputRefusal(
            "reservation rollback journal is unexpectedly occupied"
        )


def _journal_schema_sha256(connection: sqlite3.Connection) -> str:
    tables: dict[str, object] = {}
    for table in ("journal_meta", "reservations", "resume_audits"):
        columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
        indexes = connection.execute(f"PRAGMA index_list({table})").fetchall()
        tables[table] = {
            "columns": [list(row) for row in columns],
            "indexes": [
                {
                    "index_list": list(index),
                    "index_info": [
                        list(row)
                        for row in connection.execute(
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
    return canonical_sha256(
        {
            "user_version": int(
                connection.execute("PRAGMA user_version").fetchone()[0]
            ),
            "tables": tables,
            "sqlite_master": sqlite_master,
        }
    )


class PrivateOutputReservation:
    """One journal-owned output effect."""

    def __init__(self, owner: "PrivateOutputJournal", role: str) -> None:
        self._owner = owner
        self.role = role
        row = owner._reservation_row(role)
        self.path = Path(str(row["output_path"]))
        self._fd = owner._open_owned_output(row)
        self._closed = False

    @property
    def ledger_state(self) -> str:
        """Return the durable FSM state without attesting the output path."""

        return str(self._owner._reservation_row(self.role)["state"])

    @property
    def state(self) -> str:
        """Compatibility alias for :attr:`ledger_state`.

        This is a journal claim, not a fresh filesystem-effect attestation.
        Methods that return output content revalidate the held descriptor and
        canonical pathname before returning.
        """

        return self.ledger_state

    def _row_and_bytes(self) -> tuple[sqlite3.Row, bytes]:
        row = self._owner._reservation_row(self.role)
        return row, _read_descriptor(self._fd)

    def _verify_identity(self, row: sqlite3.Row) -> None:
        self._owner._verify_output_parent_identity(self.role)
        self._owner._verify_journal_identity()
        try:
            path_info = os.stat(
                self.path.name,
                dir_fd=self._owner._parent_fds[self.role],
                follow_symlinks=False,
            )
            opened = os.fstat(self._fd)
        except OSError as error:
            raise PrivateOutputRefusal(
                "reserved output path disappeared"
            ) from error
        identity = (int(row["output_dev"]), int(row["output_ino"]))
        if (
            not stat.S_ISREG(path_info.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or (path_info.st_dev, path_info.st_ino) != identity
            or (opened.st_dev, opened.st_ino) != identity
            or path_info.st_nlink != 1
            or opened.st_nlink != 1
            or stat.S_IMODE(path_info.st_mode) != 0o600
            or stat.S_IMODE(opened.st_mode) != 0o600
        ):
            raise PrivateOutputRefusal(
                "reserved output inode ownership drifted"
            )

    def _verify_marker(self, row: sqlite3.Row) -> None:
        self._verify_identity(row)
        marker = bytes(row["marker_bytes"])
        if (
            marker != self._owner._marker(row)
            or not isinstance(row["marker_sha256"], str)
            or hashlib.sha256(marker).hexdigest() != row["marker_sha256"]
            or _read_descriptor(self._fd) != marker
        ):
            raise PrivateOutputRefusal("reserved output marker drifted")

    def _prepared(self, row: sqlite3.Row) -> tuple[bytes, str]:
        payload = row["prepared_payload"]
        digest = row["prepared_sha256"]
        size = row["prepared_size"]
        if (
            not isinstance(payload, bytes)
            or not isinstance(digest, str)
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size != len(payload)
            or hashlib.sha256(payload).hexdigest() != digest
        ):
            raise PrivateOutputRefusal(
                "prepared private output payload drifted"
            )
        _strict_mapping(payload, "prepared private output")
        return payload, digest

    def _reconcile_prepared(self, row: sqlite3.Row) -> str:
        self._verify_identity(row)
        payload, digest = self._prepared(row)
        observed = _read_descriptor(self._fd)
        marker = bytes(row["marker_bytes"])
        if observed != marker and observed != payload and not payload.startswith(
            observed
        ):
            raise PrivateOutputRefusal(
                "prepared private output contains an unexpected byte sequence"
            )
        if observed != payload:
            os.ftruncate(self._fd, 0)
            os.lseek(self._fd, 0, os.SEEK_SET)
            _write_all(self._fd, payload)
        os.fsync(self._fd)
        self._verify_identity(row)
        if _read_descriptor(self._fd) != payload:
            raise PrivateOutputRefusal("private output readback drifted")
        _fsync_parent(
            self.path,
            parent_fd=self._owner._parent_fds[self.role],
        )
        def verify_effect() -> None:
            self._verify_identity(row)
            if _read_descriptor(self._fd) != payload:
                raise PrivateOutputRefusal("private output readback drifted")

        self._owner._transition(
            self.role,
            expected="COMMIT_PREPARED",
            target="COMMITTED",
            effect_verifier=verify_effect,
        )
        _fsync_parent(
            self.path,
            parent_fd=self._owner._parent_fds[self.role],
        )
        verify_effect()
        return digest

    def prepared_value(self) -> dict[str, object] | None:
        """Inspect a journaled value without materializing a prepared effect.

        Callers use this boundary to validate the journal-durable payload
        against the current run authorities before allowing crash recovery to
        rewrite an interrupted output.  ``COMMIT_PREPARED`` therefore remains
        observational here; :meth:`commit` performs the authorized reconcile.
        """

        row = self._owner._reservation_row(self.role)
        state = str(row["state"])
        if state == "RESERVED":
            self._verify_marker(row)
            return None
        if state not in {"COMMIT_PREPARED", "COMMITTED"}:
            raise PrivateOutputRefusal("private output state is not readable")
        self._verify_identity(row)
        payload, _digest = self._prepared(row)
        observed = _read_descriptor(self._fd)
        if state == "COMMITTED":
            if observed != payload:
                raise PrivateOutputRefusal("committed private output drifted")
            self._owner._sync_journal()
            self._verify_identity(row)
            if _read_descriptor(self._fd) != payload:
                raise PrivateOutputRefusal("committed private output drifted")
        else:
            marker = bytes(row["marker_bytes"])
            if (
                observed != marker
                and observed != payload
                and not payload.startswith(observed)
            ):
                raise PrivateOutputRefusal(
                    "prepared private output contains an unexpected byte sequence"
                )
        return _strict_mapping(payload, "prepared private output")

    def committed_value(self) -> dict[str, object] | None:
        value = self.prepared_value()
        if value is None:
            return None
        row = self._owner._reservation_row(self.role)
        state = str(row["state"])
        if state == "COMMIT_PREPARED":
            self._reconcile_prepared(row)
            row = self._owner._reservation_row(self.role)
            state = str(row["state"])
        if state != "COMMITTED":
            raise PrivateOutputRefusal("private output state is not readable")
        self._verify_identity(row)
        payload, _digest = self._prepared(row)
        if _read_descriptor(self._fd) != payload:
            raise PrivateOutputRefusal("committed private output drifted")
        return value

    def commit(self, value: Mapping[str, object]) -> str:
        if self._closed or self._owner.closed:
            raise PrivateOutputRefusal(
                "private output reservation is no longer writable"
            )
        if not isinstance(value, Mapping):
            raise PrivateOutputRefusal("private output must be a JSON object")
        payload = _json_payload(value)
        digest = hashlib.sha256(payload).hexdigest()
        row = self._owner._reservation_row(self.role)
        state = str(row["state"])
        if state in {"COMMIT_PREPARED", "COMMITTED"}:
            prepared, prepared_digest = self._prepared(row)
            if prepared != payload or prepared_digest != digest:
                raise PrivateOutputRefusal(
                    "private output recommit differs from prepared payload"
                )
            if state == "COMMIT_PREPARED":
                return self._reconcile_prepared(row)
            self._verify_identity(row)
            if _read_descriptor(self._fd) != payload:
                raise PrivateOutputRefusal("committed private output drifted")
            self._owner._sync_journal()
            self._verify_identity(row)
            if _read_descriptor(self._fd) != payload:
                raise PrivateOutputRefusal("committed private output drifted")
            return digest
        if state != "RESERVED":
            raise PrivateOutputRefusal("private output state cannot commit")
        self._verify_marker(row)
        self._owner._prepare_commit(self.role, payload, digest)
        return self._reconcile_prepared(
            self._owner._reservation_row(self.role)
        )

    def close(self) -> None:
        if self._closed:
            return
        os.close(self._fd)
        self._closed = True

    def __enter__(self) -> "PrivateOutputReservation":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()


class PrivateOutputJournal(Mapping[str, PrivateOutputReservation]):
    """Fenced owner of one closed output set and its durable effect ledger."""

    def __init__(
        self,
        outputs: Sequence[tuple[str, Path]],
        *,
        run_id: str,
        journal_path: Path,
        resume: bool,
        forbidden_paths: Sequence[Path] = (),
    ) -> None:
        if not isinstance(run_id, str) or not run_id:
            raise PrivateOutputRefusal("reservation run_id must be non-empty")
        if not outputs or any(
            not isinstance(role, str) or not role for role, _path in outputs
        ):
            raise PrivateOutputRefusal("at least one named output is required")
        normalized = [
            (role, canonical_output_path(path)) for role, path in outputs
        ]
        roles = [role for role, _path in normalized]
        paths = [path for _role, path in normalized]
        if len(set(roles)) != len(roles):
            raise PrivateOutputRefusal("private output role repeats")
        if len(set(paths)) != len(paths):
            raise PrivateOutputRefusal("private output paths collide")
        self.path = canonical_output_path(journal_path)
        self._lock_path = canonical_output_path(Path(f"{self.path}.lock"))
        self._journal_family = {
            self.path,
            self._lock_path,
            canonical_output_path(Path(f"{self.path}-wal")),
            canonical_output_path(Path(f"{self.path}-shm")),
            canonical_output_path(Path(f"{self.path}-journal")),
        }
        if self._journal_family & set(paths):
            raise PrivateOutputRefusal("reservation journal aliases an output")
        forbidden: set[Path] = set()
        for raw in forbidden_paths:
            try:
                forbidden.add(Path(raw).expanduser().resolve(strict=True))
            except OSError as error:
                raise PrivateOutputRefusal(
                    "forbidden input path is unavailable"
                ) from error
        if set(paths) & forbidden or self._journal_family & forbidden:
            raise PrivateOutputRefusal(
                "private output or journal aliases an input or database"
            )
        self.run_id = run_id
        self._outputs = normalized
        self.output_set_sha256 = canonical_sha256(
            [{"role": role, "path": str(path)} for role, path in normalized]
        )
        self._closed = False
        self._parent_fds: dict[str, int] = {}
        self._parent_identities: dict[str, tuple[int, int]] = {}
        self._reservations: dict[str, PrivateOutputReservation] = {}
        self._connection: sqlite3.Connection | None = None
        self._journal_fd = -1
        self._lock_fd = -1
        self._journal_parent_fd = -1
        self._journal_parent_identity: tuple[int, int] | None = None
        self._journal_identity: tuple[int, int] | None = None
        self._lock_identity: tuple[int, int] | None = None
        self._lock_bytes: bytes | None = None
        try:
            self._journal_parent_fd = _open_private_directory(
                self.path.parent,
                "reservation journal parent",
            )
            self._journal_parent_identity = _directory_identity(
                self.path.parent,
                self._journal_parent_fd,
                "reservation journal parent",
            )
            self._acquire_journal(resume=resume)
            if resume:
                self._validate_existing_journal()
            else:
                self._initialize_journal()
            for role, path in self._outputs:
                self._parent_fds[role] = _open_private_directory(
                    path.parent,
                    f"private output parent for {role}",
                )
                self._parent_identities[role] = _directory_identity(
                    path.parent,
                    self._parent_fds[role],
                    f"private output parent for {role}",
                )
            self._materialize_markers()
            for role, _path in self._outputs:
                self._reservations[role] = PrivateOutputReservation(self, role)
        except BaseException:
            try:
                self.close()
            except BaseException:
                pass
            raise

    @property
    def closed(self) -> bool:
        return self._closed

    def _acquire_journal(self, *, resume: bool) -> None:
        common_flags = os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(
            os, "O_NOFOLLOW", 0
        )
        if resume:
            try:
                before = self.path.lstat()
                lock_before = self._lock_path.lstat()
            except OSError as error:
                raise PrivateOutputRefusal(
                    "resume requires an existing reservation journal"
                ) from error
            if (
                stat.S_ISLNK(before.st_mode)
                or not stat.S_ISREG(before.st_mode)
                or stat.S_ISLNK(lock_before.st_mode)
                or not stat.S_ISREG(lock_before.st_mode)
            ):
                raise PrivateOutputRefusal("reservation journal is unsafe")
            if (
                stat.S_IMODE(before.st_mode) != 0o600
                or stat.S_IMODE(lock_before.st_mode) != 0o600
            ):
                raise PrivateOutputRefusal("reservation journal is not private")
            lock_flags = common_flags
            journal_flags = common_flags
        else:
            if (
                any(_path_occupied(member) for member in self._journal_family)
                or any(_path_occupied(path) for _role, path in self._outputs)
            ):
                raise PrivateOutputRefusal(
                    "private output path or reservation journal is already occupied"
                )
            lock_flags = common_flags | os.O_CREAT | os.O_EXCL
            journal_flags = common_flags | os.O_CREAT | os.O_EXCL
        try:
            self._lock_fd = os.open(
                self._lock_path.name,
                lock_flags,
                0o600,
                dir_fd=self._journal_parent_fd,
            )
        except FileExistsError as error:
            raise PrivateOutputRefusal(
                "reservation journal is already occupied"
            ) from error
        try:
            fcntl.flock(
                self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB
            )
        except (BlockingIOError, OSError) as error:
            raise PrivateOutputRefusal(
                "reservation journal is owned by another runner"
            ) from error
        if not resume:
            os.fchmod(self._lock_fd, 0o600)
        lock_info = os.fstat(self._lock_fd)
        if (
            not stat.S_ISREG(lock_info.st_mode)
            or lock_info.st_nlink != 1
            or stat.S_IMODE(lock_info.st_mode) != 0o600
        ):
            raise PrivateOutputRefusal("reservation journal lock is not private")
        self._lock_identity = (lock_info.st_dev, lock_info.st_ino)
        if resume:
            lock_bytes = _read_descriptor(self._lock_fd)
            if (
                len(lock_bytes) != 65
                or lock_bytes[-1:] != b"\n"
                or any(
                    character not in b"0123456789abcdef"
                    for character in lock_bytes[:-1]
                )
            ):
                raise PrivateOutputRefusal(
                    "reservation journal lock binding drifted"
                )
        else:
            lock_bytes = (secrets.token_hex(32) + "\n").encode("ascii")
            _write_all(self._lock_fd, lock_bytes)
        self._lock_bytes = lock_bytes
        os.fsync(self._lock_fd)
        _fsync_parent(
            self._lock_path, parent_fd=self._journal_parent_fd
        )
        try:
            self._journal_fd = os.open(
                self.path.name,
                journal_flags,
                0o600,
                dir_fd=self._journal_parent_fd,
            )
        except FileExistsError as error:
            raise PrivateOutputRefusal(
                "reservation journal is already occupied"
            ) from error
        if not resume:
            os.fchmod(self._journal_fd, 0o600)
        info = os.fstat(self._journal_fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise PrivateOutputRefusal("reservation journal is not private")
        self._journal_identity = (info.st_dev, info.st_ino)
        if resume:
            _preflight_sqlite_family(self.path)
        previous_umask = os.umask(0o077)
        try:
            try:
                self._connection = sqlite3.connect(
                    f"{self.path.as_uri()}?mode=rw",
                    isolation_level=None,
                    uri=True,
                )
            except sqlite3.Error as error:
                raise PrivateOutputRefusal(
                    "reservation journal parent identity or SQLite binding drifted"
                ) from error
        finally:
            os.umask(previous_umask)
        self._connection.row_factory = sqlite3.Row
        self._verify_journal_identity()
        self._connection.execute("PRAGMA busy_timeout=0")
        self._connection.execute("PRAGMA wal_autocheckpoint=0")
        if int(
            self._connection.execute("PRAGMA wal_autocheckpoint").fetchone()[0]
        ) != 0:
            raise PrivateOutputRefusal(
                "reservation journal automatic checkpointing is enabled"
            )

    @property
    def _db(self) -> sqlite3.Connection:
        if self._connection is None:
            raise PrivateOutputRefusal("reservation journal is closed")
        return self._connection

    def _verify_journal_identity(self) -> None:
        if (
            self._closed
            or self._journal_identity is None
            or self._lock_identity is None
            or self._lock_bytes is None
            or self._journal_parent_identity is None
        ):
            raise PrivateOutputRefusal("reservation journal is closed")
        observed_parent = _directory_identity(
            self.path.parent,
            self._journal_parent_fd,
            "reservation journal parent",
        )
        if observed_parent != self._journal_parent_identity:
            raise PrivateOutputRefusal(
                "reservation journal parent identity drifted"
            )
        try:
            path_info = os.stat(
                self.path.name,
                dir_fd=self._journal_parent_fd,
                follow_symlinks=False,
            )
            opened = os.fstat(self._journal_fd)
            lock_path_info = os.stat(
                self._lock_path.name,
                dir_fd=self._journal_parent_fd,
                follow_symlinks=False,
            )
            lock_opened = os.fstat(self._lock_fd)
            lock_bytes = _read_descriptor(self._lock_fd)
        except OSError as error:
            raise PrivateOutputRefusal("reservation journal disappeared") from error
        if (
            stat.S_ISLNK(path_info.st_mode)
            or not stat.S_ISREG(path_info.st_mode)
            or (path_info.st_dev, path_info.st_ino) != self._journal_identity
            or (opened.st_dev, opened.st_ino) != self._journal_identity
            or path_info.st_nlink != 1
            or opened.st_nlink != 1
            or stat.S_IMODE(path_info.st_mode) != 0o600
            or stat.S_IMODE(opened.st_mode) != 0o600
            or stat.S_ISLNK(lock_path_info.st_mode)
            or not stat.S_ISREG(lock_path_info.st_mode)
            or (lock_path_info.st_dev, lock_path_info.st_ino)
            != self._lock_identity
            or (lock_opened.st_dev, lock_opened.st_ino)
            != self._lock_identity
            or lock_path_info.st_nlink != 1
            or lock_opened.st_nlink != 1
            or stat.S_IMODE(lock_path_info.st_mode) != 0o600
            or stat.S_IMODE(lock_opened.st_mode) != 0o600
            or lock_bytes != self._lock_bytes
        ):
            raise PrivateOutputRefusal("reservation journal identity drifted")

    def _verify_output_parent_identity(self, role: str) -> None:
        expected = self._parent_identities.get(role)
        descriptor = self._parent_fds.get(role)
        path = dict(self._outputs).get(role)
        if expected is None or descriptor is None or path is None:
            raise PrivateOutputRefusal("private output parent is not owned")
        observed = _directory_identity(
            path.parent, descriptor, f"private output parent for {role}"
        )
        if observed != expected:
            raise PrivateOutputRefusal(
                f"private output parent for {role} identity drifted"
            )

    def _sync_journal(self) -> None:
        """Checkpoint the WAL fully, then fsync the bound database family."""

        self._verify_journal_identity()
        checkpoint = self._db.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()
        if (
            checkpoint is None
            or len(checkpoint) != 3
            or any(type(value) is not int for value in checkpoint)
            or tuple(checkpoint) != (0, 0, 0)
        ):
            raise PrivateOutputRefusal(
                "reservation journal WAL checkpoint was incomplete"
            )
        self._verify_journal_identity()
        os.fsync(self._journal_fd)
        os.fsync(self._journal_parent_fd)
        self._verify_journal_identity()

    def _initialize_journal(self) -> None:
        self._verify_journal_identity()
        journal_mode = str(
            self._db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        ).casefold()
        self._db.execute("PRAGMA synchronous=FULL")
        synchronous = int(
            self._db.execute("PRAGMA synchronous").fetchone()[0]
        )
        if journal_mode != "wal" or synchronous != 2:
            raise PrivateOutputRefusal(
                "reservation journal is not WAL/FULL"
            )
        self._db.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE journal_meta(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                schema_version TEXT NOT NULL,
                run_id TEXT NOT NULL,
                journal_path TEXT NOT NULL,
                journal_dev INTEGER NOT NULL,
                journal_ino INTEGER NOT NULL,
                lock_path TEXT NOT NULL,
                lock_dev INTEGER NOT NULL,
                lock_ino INTEGER NOT NULL,
                lock_nonce_sha256 TEXT NOT NULL,
                output_set_sha256 TEXT NOT NULL
            );
            CREATE TABLE reservations(
                role TEXT PRIMARY KEY,
                output_path TEXT NOT NULL UNIQUE,
                reservation_nonce TEXT NOT NULL UNIQUE,
                marker_bytes BLOB,
                marker_sha256 TEXT,
                output_dev INTEGER,
                output_ino INTEGER,
                state TEXT NOT NULL CHECK(state IN (
                    'RESERVATION_PREPARED','RESERVED',
                    'COMMIT_PREPARED','COMMITTED'
                )),
                prepared_payload BLOB,
                prepared_sha256 TEXT,
                prepared_size INTEGER,
                CHECK(
                    (
                        state='RESERVATION_PREPARED'
                        AND marker_bytes IS NULL
                        AND marker_sha256 IS NULL
                        AND output_dev IS NULL
                        AND output_ino IS NULL
                        AND prepared_payload IS NULL
                        AND prepared_sha256 IS NULL
                        AND prepared_size IS NULL
                    ) OR (
                        state='RESERVED'
                        AND marker_bytes IS NOT NULL
                        AND marker_sha256 IS NOT NULL
                        AND output_dev IS NOT NULL
                        AND output_ino IS NOT NULL
                        AND prepared_payload IS NULL
                        AND prepared_sha256 IS NULL
                        AND prepared_size IS NULL
                    ) OR (
                        state IN ('COMMIT_PREPARED','COMMITTED')
                        AND marker_bytes IS NOT NULL
                        AND marker_sha256 IS NOT NULL
                        AND output_dev IS NOT NULL
                        AND output_ino IS NOT NULL
                        AND prepared_payload IS NOT NULL
                        AND prepared_sha256 IS NOT NULL
                        AND prepared_size IS NOT NULL
                    )
                )
            );
            CREATE TABLE resume_audits(
                ordinal INTEGER PRIMARY KEY CHECK(ordinal>=0),
                receipt_bytes BLOB NOT NULL,
                receipt_sha256 TEXT NOT NULL UNIQUE
            );
            PRAGMA user_version=2;
            COMMIT;
            """
        )
        if _journal_schema_sha256(self._db) != JOURNAL_SCHEMA_SHA256:
            raise PrivateOutputRefusal(
                "reservation journal schema manifest drifted"
            )
        assert self._journal_identity is not None
        assert self._lock_identity is not None
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._db.execute(
                "INSERT INTO journal_meta VALUES(1,?,?,?,?,?,?,?,?,?,?)",
                (
                    JOURNAL_SCHEMA,
                    self.run_id,
                    str(self.path),
                    self._journal_identity[0],
                    self._journal_identity[1],
                    str(self._lock_path),
                    self._lock_identity[0],
                    self._lock_identity[1],
                    hashlib.sha256(self._lock_bytes or b"").hexdigest(),
                    self.output_set_sha256,
                ),
            )
            for role, path in self._outputs:
                self._db.execute(
                    """
                    INSERT INTO reservations(
                        role,output_path,reservation_nonce,state
                    ) VALUES(?,?,?,'RESERVATION_PREPARED')
                    """,
                    (role, str(path), secrets.token_hex(32)),
                )
            self._db.execute("COMMIT")
        except BaseException:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise
        self._sync_journal()

    def _schema_columns(self, table: str) -> tuple[str, ...]:
        return tuple(
            str(row[1])
            for row in self._db.execute(f"PRAGMA table_info({table})")
        )

    def _validate_reservation_row(self, row: sqlite3.Row) -> None:
        nonce = row["reservation_nonce"]
        state = row["state"]
        if (
            not isinstance(nonce, str)
            or len(nonce) != 64
            or any(character not in "0123456789abcdef" for character in nonce)
            or state not in RESERVATION_STATES
        ):
            raise PrivateOutputRefusal("reservation row identity drifted")
        marker_fields = (
            "marker_bytes",
            "marker_sha256",
            "output_dev",
            "output_ino",
        )
        prepared_fields = (
            "prepared_payload",
            "prepared_sha256",
            "prepared_size",
        )
        if state == "RESERVATION_PREPARED":
            if any(row[field] is not None for field in marker_fields + prepared_fields):
                raise PrivateOutputRefusal(
                    "prepared reservation carries premature effect bindings"
                )
            return
        if any(row[field] is None for field in marker_fields):
            raise PrivateOutputRefusal("reservation marker binding is incomplete")
        marker = row["marker_bytes"]
        if (
            not isinstance(marker, bytes)
            or marker != self._marker(row)
            or not isinstance(row["marker_sha256"], str)
            or hashlib.sha256(marker).hexdigest() != row["marker_sha256"]
            or isinstance(row["output_dev"], bool)
            or not isinstance(row["output_dev"], int)
            or row["output_dev"] < 0
            or isinstance(row["output_ino"], bool)
            or not isinstance(row["output_ino"], int)
            or row["output_ino"] < 1
        ):
            raise PrivateOutputRefusal("reservation marker binding drifted")
        if state == "RESERVED":
            if any(row[field] is not None for field in prepared_fields):
                raise PrivateOutputRefusal(
                    "reserved output carries premature payload bindings"
                )
            return
        payload = row["prepared_payload"]
        digest = row["prepared_sha256"]
        size = row["prepared_size"]
        if (
            not isinstance(payload, bytes)
            or not isinstance(digest, str)
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size != len(payload)
            or hashlib.sha256(payload).hexdigest() != digest
        ):
            raise PrivateOutputRefusal("prepared private output payload drifted")
        _strict_mapping(payload, "prepared private output")

    def _validate_resume_audits(self) -> None:
        rows = self._db.execute(
            "SELECT * FROM resume_audits ORDER BY ordinal"
        ).fetchall()
        if [row["ordinal"] for row in rows] != list(range(len(rows))):
            raise PrivateOutputRefusal("resume audit ordinals drifted")
        for row in rows:
            payload = row["receipt_bytes"]
            digest = row["receipt_sha256"]
            if (
                not isinstance(payload, bytes)
                or not isinstance(digest, str)
                or hashlib.sha256(payload).hexdigest() != digest
            ):
                raise PrivateOutputRefusal("resume audit binding drifted")
            value = _strict_mapping(payload, "resume audit")
            _validate_resume_prefix_audit(value, run_id=self.run_id)

    def _validate_existing_journal(self) -> None:
        self._verify_journal_identity()
        for member in (
            self.path,
            Path(f"{self.path}-wal"),
            Path(f"{self.path}-shm"),
        ):
            try:
                info = member.lstat()
            except FileNotFoundError:
                if member == self.path:
                    raise PrivateOutputRefusal(
                        "reservation journal disappeared"
                    )
                continue
            if (
                stat.S_ISLNK(info.st_mode)
                or not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise PrivateOutputRefusal(
                    "reservation journal family is not private"
                )
        if [str(row[0]) for row in self._db.execute("PRAGMA integrity_check")] != [
            "ok"
        ]:
            raise PrivateOutputRefusal("reservation journal integrity failed")
        if (
            int(self._db.execute("PRAGMA user_version").fetchone()[0])
            != JOURNAL_USER_VERSION
            or str(self._db.execute("PRAGMA journal_mode").fetchone()[0]).casefold()
            != "wal"
        ):
            raise PrivateOutputRefusal("reservation journal schema drifted")
        self._db.execute("PRAGMA synchronous=FULL")
        if int(self._db.execute("PRAGMA synchronous").fetchone()[0]) != 2:
            raise PrivateOutputRefusal("reservation journal is not WAL/FULL")
        tables = {
            str(row[0])
            for row in self._db.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if (
            tables != {"journal_meta", "reservations", "resume_audits"}
            or self._schema_columns("journal_meta") != _META_COLUMNS
            or self._schema_columns("reservations") != _RESERVATION_COLUMNS
            or self._schema_columns("resume_audits") != _AUDIT_COLUMNS
        ):
            raise PrivateOutputRefusal("reservation journal table shape drifted")
        forbidden_objects = self._db.execute(
            "SELECT type,name FROM sqlite_master "
            "WHERE type IN ('trigger','view') "
            "OR (type='index' AND sql IS NOT NULL)"
        ).fetchall()
        if forbidden_objects:
            raise PrivateOutputRefusal(
                "reservation journal executable schema drifted"
            )
        if _journal_schema_sha256(self._db) != JOURNAL_SCHEMA_SHA256:
            raise PrivateOutputRefusal(
                "reservation journal schema manifest drifted"
            )
        meta_rows = self._db.execute("SELECT * FROM journal_meta").fetchall()
        assert self._journal_identity is not None
        assert self._lock_identity is not None
        if len(meta_rows) != 1:
            raise PrivateOutputRefusal("reservation journal metadata drifted")
        meta = meta_rows[0]
        if (
            meta["singleton"] != 1
            or meta["schema_version"] != JOURNAL_SCHEMA
            or meta["run_id"] != self.run_id
            or meta["journal_path"] != str(self.path)
            or (meta["journal_dev"], meta["journal_ino"])
            != self._journal_identity
            or meta["lock_path"] != str(self._lock_path)
            or (meta["lock_dev"], meta["lock_ino"])
            != self._lock_identity
            or meta["lock_nonce_sha256"]
            != hashlib.sha256(self._lock_bytes or b"").hexdigest()
            or meta["output_set_sha256"] != self.output_set_sha256
        ):
            raise PrivateOutputRefusal("reservation journal identity binding drifted")
        rows = self._db.execute(
            "SELECT * FROM reservations ORDER BY role"
        ).fetchall()
        expected = {role: str(path) for role, path in self._outputs}
        if (
            len(rows) != len(expected)
            or {str(row["role"]): str(row["output_path"]) for row in rows}
            != expected
        ):
            raise PrivateOutputRefusal("reservation output-set binding drifted")
        for row in rows:
            self._validate_reservation_row(row)
        self._validate_resume_audits()
        self._sync_journal()

    def _marker(self, row: sqlite3.Row) -> bytes:
        assert self._journal_identity is not None
        value = {
            "schema_version": RESERVATION_SCHEMA,
            "status": "RESERVED_NO_RESULT",
            "run_id": self.run_id,
            "role": str(row["role"]),
            "output_path": str(row["output_path"]),
            "journal": {
                "resolved_path": str(self.path),
                "st_dev": self._journal_identity[0],
                "st_ino": self._journal_identity[1],
            },
            "reservation_nonce": str(row["reservation_nonce"]),
            "output_set_sha256": self.output_set_sha256,
        }
        return (canonical_json(value) + "\n").encode("utf-8")

    def _materialize_markers(self) -> None:
        for role, path in self._outputs:
            self._verify_output_parent_identity(role)
            row = self._reservation_row(role)
            state = str(row["state"])
            if state == "RESERVATION_PREPARED":
                marker = self._marker(row)
                flags = (
                    os.O_RDWR
                    | os.O_CREAT
                    | os.O_EXCL
                    | getattr(os, "O_CLOEXEC", 0)
                    | getattr(os, "O_NOFOLLOW", 0)
                )
                try:
                    descriptor = os.open(
                        path.name,
                        flags,
                        0o600,
                        dir_fd=self._parent_fds[role],
                    )
                    created = True
                except FileExistsError:
                    descriptor = os.open(
                        path.name,
                        os.O_RDWR
                        | getattr(os, "O_CLOEXEC", 0)
                        | getattr(os, "O_NOFOLLOW", 0),
                        dir_fd=self._parent_fds[role],
                    )
                    created = False
                try:
                    if created:
                        os.fchmod(descriptor, 0o600)
                    info = os.fstat(descriptor)
                    observed = b"" if created else _read_descriptor(descriptor)
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or info.st_nlink != 1
                        or stat.S_IMODE(info.st_mode) != 0o600
                        or (not created and observed != marker)
                    ):
                        raise PrivateOutputRefusal(
                            "prepared reservation marker cannot be adopted"
                        )
                    if created:
                        _write_all(descriptor, marker)
                    os.fsync(descriptor)
                    output_identity = (info.st_dev, info.st_ino)
                finally:
                    os.close(descriptor)
                _fsync_parent(
                    path, parent_fd=self._parent_fds[role]
                )
                self._verify_output_parent_identity(role)
                self._verify_journal_identity()
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    changed = self._db.execute(
                        """
                        UPDATE reservations SET
                            marker_bytes=?,marker_sha256=?,
                            output_dev=?,output_ino=?,state='RESERVED'
                        WHERE role=? AND state='RESERVATION_PREPARED'
                        """,
                        (
                            marker,
                            hashlib.sha256(marker).hexdigest(),
                            output_identity[0],
                            output_identity[1],
                            role,
                        ),
                    ).rowcount
                    if changed != 1:
                        raise PrivateOutputRefusal(
                            "reservation marker transition conflicted"
                        )
                    self._db.execute("COMMIT")
                except BaseException:
                    if self._db.in_transaction:
                        self._db.execute("ROLLBACK")
                    raise
                self._sync_journal()
                self._verify_output_parent_identity(role)
            else:
                if any(
                    row[key] is None
                    for key in (
                        "marker_bytes",
                        "marker_sha256",
                        "output_dev",
                        "output_ino",
                    )
                ):
                    raise PrivateOutputRefusal(
                        "reservation marker binding is incomplete"
                    )

    def _reservation_row(self, role: str) -> sqlite3.Row:
        self._verify_journal_identity()
        row = self._db.execute(
            "SELECT * FROM reservations WHERE role=?", (role,)
        ).fetchone()
        if row is None:
            raise PrivateOutputRefusal("private output role is not reserved")
        return row

    def _open_owned_output(self, row: sqlite3.Row) -> int:
        path = Path(str(row["output_path"]))
        self._verify_output_parent_identity(str(row["role"]))
        try:
            descriptor = os.open(
                path.name,
                os.O_RDWR
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=self._parent_fds[str(row["role"])],
            )
        except OSError as error:
            raise PrivateOutputRefusal("reserved output is unavailable") from error
        try:
            info = os.fstat(descriptor)
        except OSError:
            os.close(descriptor)
            raise
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or (info.st_dev, info.st_ino)
            != (row["output_dev"], row["output_ino"])
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            os.close(descriptor)
            raise PrivateOutputRefusal("reserved output inode ownership drifted")
        return descriptor

    def _prepare_commit(self, role: str, payload: bytes, digest: str) -> None:
        self._verify_journal_identity()
        self._db.execute("BEGIN IMMEDIATE")
        try:
            changed = self._db.execute(
                """
                UPDATE reservations SET
                    state='COMMIT_PREPARED',prepared_payload=?,
                    prepared_sha256=?,prepared_size=?
                WHERE role=? AND state='RESERVED'
                """,
                (payload, digest, len(payload), role),
            ).rowcount
            if changed != 1:
                raise PrivateOutputRefusal(
                    "private output prepare transition conflicted"
                )
            self._db.execute("COMMIT")
        except BaseException:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise
        self._sync_journal()

    def _transition(
        self,
        role: str,
        *,
        expected: str,
        target: str,
        effect_verifier: Callable[[], None],
    ) -> None:
        if (expected, target) != ("COMMIT_PREPARED", "COMMITTED"):
            raise PrivateOutputRefusal("private output transition is forbidden")
        self._verify_journal_identity()
        self._db.execute("BEGIN IMMEDIATE")
        try:
            changed = self._db.execute(
                "UPDATE reservations SET state=? WHERE role=? AND state=?",
                (target, role, expected),
            ).rowcount
            if changed != 1:
                raise PrivateOutputRefusal(
                    "private output state transition conflicted"
                )
            effect_verifier()
            self._verify_journal_identity()
            self._db.execute("COMMIT")
        except BaseException:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise
        self._sync_journal()
        effect_verifier()

    def record_resume_audit(self, receipt: Mapping[str, object]) -> str:
        if not isinstance(receipt, Mapping):
            raise PrivateOutputRefusal("resume audit must be a JSON object")
        value = dict(receipt)
        _validate_resume_prefix_audit(value, run_id=self.run_id)
        payload = _json_payload(value)
        digest = hashlib.sha256(payload).hexdigest()
        _strict_mapping(payload, "resume audit")
        self._verify_journal_identity()
        existing = self._db.execute(
            "SELECT ordinal,receipt_bytes FROM resume_audits "
            "WHERE receipt_sha256=?",
            (digest,),
        ).fetchone()
        if existing is not None:
            if bytes(existing["receipt_bytes"]) != payload:
                raise PrivateOutputRefusal("resume audit hash collision")
            self._sync_journal()
            return digest
        ordinal = int(
            self._db.execute(
                "SELECT COALESCE(MAX(ordinal),-1)+1 FROM resume_audits"
            ).fetchone()[0]
        )
        self._db.execute("BEGIN IMMEDIATE")
        try:
            self._db.execute(
                "INSERT INTO resume_audits VALUES(?,?,?)",
                (ordinal, payload, digest),
            )
            self._db.execute("COMMIT")
        except BaseException:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise
        self._sync_journal()
        return digest

    def __getitem__(self, role: str) -> PrivateOutputReservation:
        return self._reservations[role]

    def __iter__(self) -> Iterator[str]:
        return iter(self._reservations)

    def __len__(self) -> int:
        return len(self._reservations)

    def close(self) -> None:
        if self._closed:
            return
        errors: list[BaseException] = []
        for reservation in self._reservations.values():
            try:
                reservation.close()
            except BaseException as error:
                errors.append(error)
        if errors:
            raise errors[0]
        if self._connection is not None:
            try:
                self._connection.close()
            except BaseException as error:
                raise error
            else:
                self._connection = None
        for role, descriptor in list(self._parent_fds.items()):
            try:
                os.close(descriptor)
            except BaseException as error:
                errors.append(error)
            else:
                self._parent_fds.pop(role, None)
        if self._journal_fd >= 0:
            try:
                os.close(self._journal_fd)
            except BaseException as error:
                errors.append(error)
            else:
                self._journal_fd = -1
        if errors:
            raise errors[0]
        if self._lock_fd >= 0:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            except BaseException as error:
                errors.append(error)
            try:
                os.close(self._lock_fd)
            except BaseException as error:
                errors.append(error)
            else:
                self._lock_fd = -1
        if self._journal_parent_fd >= 0:
            try:
                os.close(self._journal_parent_fd)
            except BaseException as error:
                errors.append(error)
            else:
                self._journal_parent_fd = -1
        self._closed = (
            not errors
            and all(value._closed for value in self._reservations.values())
            and not self._parent_fds
            and self._connection is None
            and self._journal_fd < 0
            and self._lock_fd < 0
            and self._journal_parent_fd < 0
        )
        if errors:
            raise errors[0]

    def __enter__(self) -> "PrivateOutputJournal":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()


def reserve_private_outputs(
    outputs: Sequence[tuple[str, Path]],
    *,
    run_id: str,
    journal_path: Path,
    resume: bool = False,
    forbidden_paths: Sequence[Path] = (),
) -> PrivateOutputJournal:
    """Acquire one fenced v2 journal for an exact closed output set."""

    return PrivateOutputJournal(
        outputs,
        run_id=run_id,
        journal_path=journal_path,
        resume=resume,
        forbidden_paths=forbidden_paths,
    )


__all__ = [
    "JOURNAL_SCHEMA",
    "JOURNAL_SCHEMA_SHA256",
    "JOURNAL_USER_VERSION",
    "PrivateOutputJournal",
    "PrivateOutputRefusal",
    "PrivateOutputReservation",
    "RESERVATION_FSM",
    "RESERVATION_SCHEMA",
    "RESERVATION_STATES",
    "canonical_existing_private_path",
    "canonical_output_path",
    "reserve_private_outputs",
]
