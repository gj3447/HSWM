"""Durable, byte-replaying result spool for F1 model calls.

The spool is the only component allowed to dispatch an F1 ``physical_call_id``
to the upstream OpenAI-compatible endpoint.  It commits the first complete
HTTP response before returning bytes to a client.  An exact retry replays those
bytes; the same identifier with different request intent is rejected; and an
unknown post-dispatch outcome is never sampled again automatically.

This is a focused F1 transport module, not a general workflow engine.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import hmac
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import threading
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import quote, urlsplit, urlunsplit

from prom_search_hswm.hswm_f1_sqlite_schema import (
    SPOOL_SCHEMA_SQL,
    SPOOL_USER_VERSION,
    SQLiteAuthorityRefusal,
    assert_database_generation,
    create_exclusive_main,
    database_generation,
    exact_schema_readback,
    integrity_readback,
    open_frozen_sqlite_read_only,
    open_private_parent,
    require_sqlite_family_absent,
    require_wal_full,
    validate_private_sqlite_family as _validate_private_sqlite_family,
    verify_private_parent,
)
from prom_search_hswm.hswm_typed_ports import canonical_json, canonical_sha256
from prom_search_hswm.hswm_private_output import (
    PrivateOutputRefusal,
    canonical_output_path,
)


SPOOL_SCHEMA = "hswm-f1-result-spool/v1"
SPOOL_ROUTE_PREFIX = "/v1/hswm/calls/"
SPOOL_IDENTITY_SCHEMA = "hswm-f1-result-spool-identity/v2"
SPOOL_IDENTITY_ROUTE = "/v1/hswm/spool-identity"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MODEL_REVISION = re.compile(r"^[0-9a-f]{40}$")
_GENESIS = "0" * 64
_FORWARDED_RESPONSE_HEADERS = frozenset(
    {"content-type", "content-length", "x-request-id", "x-client-request-id"}
)


def _configure_checkpoint_policy(
    connection: sqlite3.Connection, label: str
) -> bool:
    """Disable implicit checkpoints before the connection can commit."""

    no_checkpoint_on_close = getattr(
        sqlite3, "SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE", None
    )
    setconfig = getattr(connection, "setconfig", None)
    getconfig = getattr(connection, "getconfig", None)
    checkpoint_on_close_disabled = False
    if (
        no_checkpoint_on_close is not None
        and callable(setconfig)
        and callable(getconfig)
    ):
        setconfig(no_checkpoint_on_close, True)
        if getconfig(no_checkpoint_on_close) is not True:
            raise SQLiteAuthorityRefusal(
                f"{label} checkpoint-on-close could not be disabled"
            )
        checkpoint_on_close_disabled = True

    connection.execute("PRAGMA wal_autocheckpoint=0")
    row = connection.execute("PRAGMA wal_autocheckpoint").fetchone()
    if row is None or int(row[0]) != 0:
        raise SQLiteAuthorityRefusal(
            f"{label} automatic WAL checkpointing is enabled"
        )
    return checkpoint_on_close_disabled


def _require_checkpoint_on_close_capability(label: str) -> None:
    """Prove the sealed close policy before opening an authority database."""

    no_checkpoint_on_close = getattr(
        sqlite3, "SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE", None
    )
    if no_checkpoint_on_close is None:
        raise SQLiteAuthorityRefusal(
            f"{label} sealed runtime lacks checkpoint-on-close control"
        )
    probe = sqlite3.connect(":memory:", isolation_level=None)
    try:
        setconfig = getattr(probe, "setconfig", None)
        getconfig = getattr(probe, "getconfig", None)
        if not callable(setconfig) or not callable(getconfig):
            raise SQLiteAuthorityRefusal(
                f"{label} sealed runtime lacks checkpoint-on-close control"
            )
        setconfig(no_checkpoint_on_close, True)
        if getconfig(no_checkpoint_on_close) is not True:
            raise SQLiteAuthorityRefusal(
                f"{label} sealed runtime cannot disable checkpoint-on-close"
            )
    except sqlite3.Error as error:
        raise SQLiteAuthorityRefusal(
            f"{label} sealed runtime cannot disable checkpoint-on-close"
        ) from error
    finally:
        probe.close()


class ResultSpoolError(RuntimeError):
    pass


class SpoolIdentityConflict(ResultSpoolError):
    pass


class SpoolOutcomeUnknown(ResultSpoolError):
    def __init__(self, message: str, *, code: str = "OUTCOME_UNKNOWN") -> None:
        super().__init__(message)
        self.code = code


class SpoolIntegrityError(ResultSpoolError):
    pass


@dataclass(frozen=True)
class ModelDeploymentBinding:
    """Exact immutable deployment identity admitted by the result spool."""

    upstream_endpoint: str
    deployment_receipt_sha256: str
    deployment_id: str
    served_model: str
    model_revision: str

    def __post_init__(self) -> None:
        normalized = normalize_upstream_endpoint(self.upstream_endpoint)
        if normalized != self.upstream_endpoint:
            raise ResultSpoolError("upstream endpoint is not canonical")
        digest = _require_sha256(
            self.deployment_receipt_sha256, "deployment receipt"
        )
        if self.deployment_id != f"hswm:model_deployment:v2:{digest}":
            raise ResultSpoolError("deployment ID differs from receipt hash")
        if not isinstance(self.served_model, str) or not self.served_model:
            raise ResultSpoolError("served model must be non-empty")
        if (
            not isinstance(self.model_revision, str)
            or _MODEL_REVISION.fullmatch(self.model_revision) is None
        ):
            raise ResultSpoolError(
                "model revision must be an exact lowercase 40-hex revision"
            )


@dataclass(frozen=True)
class RawHTTPResponse:
    status: int
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class SpoolResult:
    physical_call_id: str
    intent_sha256: str
    request_sha256: str
    status: int
    headers: dict[str, str]
    body: bytes
    body_sha256: str
    replayed: bool


UpstreamTransport = Callable[[urllib_request.Request, float], RawHTTPResponse]


def _canonical_bytes(value: object) -> bytes:
    return canonical_json(value).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_private_sqlite_family(path: Path, label: str) -> None:
    try:
        _validate_private_sqlite_family(Path(path), label)
    except SQLiteAuthorityRefusal as error:
        raise SpoolIntegrityError(str(error)) from error


def _require_sha256(value: str, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ResultSpoolError(f"{label} must be a lowercase SHA-256 digest")
    return value


def normalize_upstream_endpoint(endpoint: str) -> str:
    """Return the credential-free canonical OpenAI completions endpoint."""

    if not isinstance(endpoint, str):
        raise ResultSpoolError("upstream endpoint must be text")
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != "/v1/chat/completions"
    ):
        raise ResultSpoolError(
            "upstream endpoint must be a credential-free canonical "
            "/v1/chat/completions URL"
        )
    normalized = urlunsplit(
        (parsed.scheme, parsed.netloc, "/v1/chat/completions", "", "")
    )
    if endpoint != normalized:
        raise ResultSpoolError("upstream endpoint is not canonical")
    return normalized


def _deployment_binding_from_receipt(
    receipt: Mapping[str, object],
    *,
    upstream_endpoint: str,
    served_model: str,
    model_revision: str,
) -> ModelDeploymentBinding:
    snapshot = receipt.get("snapshot")
    receipt_endpoint = receipt.get("endpoint")
    if not isinstance(snapshot, Mapping) or not isinstance(receipt_endpoint, str):
        raise ResultSpoolError("deployment receipt identity is incomplete")
    expected_upstream = normalize_upstream_endpoint(
        f"{receipt_endpoint}/chat/completions"
    )
    normalized_upstream = normalize_upstream_endpoint(upstream_endpoint)
    if normalized_upstream != expected_upstream:
        raise ResultSpoolError(
            "upstream endpoint differs from the deployment receipt"
        )
    if receipt.get("served_model") != served_model:
        raise ResultSpoolError("served model differs from the deployment receipt")
    if snapshot.get("resolved_revision") != model_revision:
        raise ResultSpoolError("model revision differs from the deployment receipt")
    return ModelDeploymentBinding(
        upstream_endpoint=normalized_upstream,
        deployment_receipt_sha256=str(receipt.get("receipt_sha256", "")),
        deployment_id=str(receipt.get("deployment_id", "")),
        served_model=served_model,
        model_revision=model_revision,
    )


def load_model_deployment_binding(
    path: str | Path,
    *,
    upstream_endpoint: str,
    served_model: str,
    model_revision: str,
    verify_live_process: bool = True,
) -> ModelDeploymentBinding:
    """Load one private official receipt without rehashing model weights."""

    target = Path(path).expanduser()
    try:
        before = target.lstat()
    except OSError as error:
        raise ResultSpoolError("model deployment receipt is unavailable") from error
    if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
        raise ResultSpoolError("model deployment receipt must be a regular file")
    if stat.S_IMODE(before.st_mode) != 0o600:
        raise ResultSpoolError("model deployment receipt must have mode 0600")
    # Lazy import keeps ordinary control-plane imports from loading NumPy; the
    # deployment host pays this cost only at the explicit attestation gate.
    # The imported files are nevertheless closed-world dependencies.
    try:
        from model_deployment_receipt import (
            DeploymentAttestationError,
            load_deployment_receipt,
        )
    except ImportError as error:
        raise ResultSpoolError(
            "official model deployment verifier is unavailable"
        ) from error
    try:
        receipt = load_deployment_receipt(
            target,
            verify_snapshot=False,
            verify_live_process=verify_live_process,
        )
    except DeploymentAttestationError as error:
        raise ResultSpoolError("model deployment receipt verification failed") from error
    try:
        raw = target.read_bytes()
        after = target.lstat()
    except OSError as error:
        raise ResultSpoolError(
            "model deployment receipt changed while loading"
        ) from error
    identity = lambda value: (  # noqa: E731 - compact immutable stat projection
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
    if identity(before) != identity(after):
        raise ResultSpoolError("model deployment receipt changed while loading")
    if raw != (canonical_json(receipt) + "\n").encode("utf-8"):
        raise ResultSpoolError("model deployment receipt bytes are not canonical")
    return _deployment_binding_from_receipt(
        receipt,
        upstream_endpoint=upstream_endpoint,
        served_model=served_model,
        model_revision=model_revision,
    )


def _safe_headers(headers: Mapping[str, str]) -> dict[str, str]:
    normalized = {str(key).casefold(): str(value) for key, value in headers.items()}
    return {
        key: normalized[key]
        for key in sorted(normalized)
        if key in _FORWARDED_RESPONSE_HEADERS
    }


def _fsync_parent(path: Path) -> None:
    """Persist initial directory entry creation on local POSIX filesystems."""

    descriptor = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class SQLiteResultSpool:
    """SQLite WAL/FULL authority for one-result-per-physical-call replay."""

    def __init__(
        self,
        path: str | Path,
        *,
        require_no_checkpoint_on_close: bool = False,
    ) -> None:
        if type(require_no_checkpoint_on_close) is not bool:
            raise SpoolIntegrityError(
                "require_no_checkpoint_on_close must be boolean"
            )
        try:
            self.path = canonical_output_path(Path(path))
        except PrivateOutputRefusal as error:
            raise SpoolIntegrityError("result-spool path is not canonical") from error
        if require_no_checkpoint_on_close:
            try:
                _require_checkpoint_on_close_capability("result spool")
            except SQLiteAuthorityRefusal as error:
                raise SpoolIntegrityError(str(error)) from error
        self._require_no_checkpoint_on_close = require_no_checkpoint_on_close
        self._lock = threading.RLock()
        self._parent_fd = -1
        connection: sqlite3.Connection | None = None
        try:
            self._parent_fd = open_private_parent(self.path, "result spool")
            try:
                self.path.lstat()
                existed = True
            except FileNotFoundError:
                existed = False
            except OSError as error:
                raise SQLiteAuthorityRefusal(
                    "cannot stat result-spool path"
                ) from error

            frozen_generation: dict[str, object] | None = None
            if existed:
                frozen_store = open_frozen_sqlite_read_only(
                    self.path, "result spool"
                )
                frozen_generation = dict(frozen_store.generation)
                with frozen_store as frozen:
                    exact_schema_readback(frozen, "spool", "result spool")
                    integrity_readback(frozen, "result spool")
                    require_wal_full(frozen, "result spool")
                    self._verify_connection_rows(frozen)
            else:
                require_sqlite_family_absent(self.path, "result spool")
                create_exclusive_main(
                    self.path, self._parent_fd, "result spool"
                )

            verify_private_parent(self.path, self._parent_fd, "result spool")
            uri = f"file:{quote(str(self.path), safe='/')}?mode=rw"
            connection = sqlite3.connect(
                uri,
                uri=True,
                isolation_level=None,
                timeout=10.0,
                check_same_thread=False,
            )
            checkpoint_on_close_disabled = _configure_checkpoint_policy(
                connection, "result spool"
            )
            if require_no_checkpoint_on_close and not checkpoint_on_close_disabled:
                raise SQLiteAuthorityRefusal(
                    "result-spool sealed close policy is unavailable"
                )
            # sqlite3.connect has not executed DDL or a mutating PRAGMA yet.
            # Detect a cooperative namespace swap before touching that handle.
            verify_private_parent(self.path, self._parent_fd, "result spool")
            if frozen_generation is not None:
                assert_database_generation(
                    self.path, "result spool", frozen_generation
                )
            connection.row_factory = sqlite3.Row

            if existed:
                exact_schema_readback(connection, "spool", "result spool")
                integrity_readback(connection, "result spool")
                require_wal_full(connection, "result spool")
                self._verify_connection_rows(connection)
                live_generation = database_generation(self.path, "result spool")
                expected_wal = frozen_generation.get("wal")
                observed_wal = live_generation.get("wal")
                wal_is_unchanged_or_empty_audit_sidecar = (
                    observed_wal == expected_wal
                    or (
                        expected_wal is None
                        and isinstance(observed_wal, Mapping)
                        and observed_wal.get("st_size") == 0
                        and observed_wal.get("sha256") == hashlib.sha256(b"").hexdigest()
                    )
                )
                if (
                    live_generation.get("main")
                    != frozen_generation.get("main")
                    or not wal_is_unchanged_or_empty_audit_sidecar
                    or live_generation.get("journal") is not None
                ):
                    raise SQLiteAuthorityRefusal(
                        "result spool changed during live pre-write audit"
                    )
                verify_private_parent(self.path, self._parent_fd, "result spool")
                connection.execute("PRAGMA busy_timeout=10000")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("PRAGMA foreign_keys=ON")
            else:
                connection.execute("PRAGMA busy_timeout=10000")
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("PRAGMA foreign_keys=ON")
                connection.executescript(SPOOL_SCHEMA_SQL)
                connection.execute(f"PRAGMA user_version={SPOOL_USER_VERSION}")
                exact_schema_readback(connection, "spool", "result spool")
                integrity_readback(connection, "result spool")
                require_wal_full(connection, "result spool")
                self._verify_connection_rows(connection)

            # A DISPATCHING row cannot still have a live authoritative owner after
            # this store has been reopened.  Preserve it as UNKNOWN and never
            # redispatch that physical inference identity.
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE spool_calls SET status='UNKNOWN', error_class='SERVER_RESTART'
                WHERE status='DISPATCHING'
                """
            )
            connection.execute("COMMIT")
            self._verify_connection_rows(connection)
            exact_schema_readback(connection, "spool", "result spool")
            validate_private_sqlite_family(self.path, "result spool")
            verify_private_parent(self.path, self._parent_fd, "result spool")
            os.fsync(self._parent_fd)
        except (SQLiteAuthorityRefusal, sqlite3.Error) as error:
            if connection is not None:
                connection.close()
            if self._parent_fd >= 0:
                os.close(self._parent_fd)
                self._parent_fd = -1
            raise SpoolIntegrityError(str(error)) from error
        except BaseException:
            if connection is not None:
                connection.close()
            if self._parent_fd >= 0:
                os.close(self._parent_fd)
                self._parent_fd = -1
            raise
        self._connection = connection
        self._checkpoint_on_close_disabled = checkpoint_on_close_disabled

    @property
    def journal_mode(self) -> str:
        return str(self._connection.execute("PRAGMA journal_mode").fetchone()[0]).casefold()

    @property
    def synchronous(self) -> int:
        return int(self._connection.execute("PRAGMA synchronous").fetchone()[0])

    @property
    def wal_autocheckpoint(self) -> int:
        row = self._connection.execute("PRAGMA wal_autocheckpoint").fetchone()
        if row is None:
            raise SpoolIntegrityError(
                "result-spool WAL auto-checkpoint policy disappeared"
            )
        return int(row[0])

    @property
    def checkpoint_on_close_disabled(self) -> bool:
        no_checkpoint_on_close = getattr(
            sqlite3, "SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE", None
        )
        getconfig = getattr(self._connection, "getconfig", None)
        if no_checkpoint_on_close is None or not callable(getconfig):
            return False
        try:
            return getconfig(no_checkpoint_on_close) is True
        except sqlite3.Error as error:
            raise SpoolIntegrityError(
                "result-spool close policy cannot be read back"
            ) from error

    def require_checkpoint_policy(self) -> None:
        if self.wal_autocheckpoint != 0:
            raise SpoolIntegrityError(
                "result-spool automatic WAL checkpointing is enabled"
            )
        if (
            self._require_no_checkpoint_on_close
            and not self.checkpoint_on_close_disabled
        ):
            raise SpoolIntegrityError(
                "result-spool checkpoint-on-close control drifted"
            )

    @staticmethod
    def _verify_row(row: sqlite3.Row) -> None:
        for field in ("physical_call_id", "intent_sha256", "request_sha256"):
            value = row[field]
            if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
                raise SpoolIntegrityError(f"stored spool {field} drifted")
        request_bytes = bytes(row["request_bytes"])
        if not request_bytes:
            raise SpoolIntegrityError("stored spool request bytes are empty")
        if _sha256_bytes(request_bytes) != row["request_sha256"]:
            raise SpoolIntegrityError("stored spool request bytes drifted")
        status_value = row["status"]
        if not isinstance(status_value, str) or status_value not in {
            "DISPATCHING",
            "UNKNOWN",
            "COMPLETE",
        }:
            raise SpoolIntegrityError("stored spool status drifted")
        response_fields = (
            "response_status",
            "response_headers",
            "response_body",
            "response_sha256",
        )
        if status_value == "DISPATCHING":
            if any(row[field] is not None for field in response_fields) or row[
                "error_class"
            ] is not None:
                raise SpoolIntegrityError(
                    "DISPATCHING spool row contains outcome fields"
                )
            return
        if status_value == "UNKNOWN":
            error_class = row["error_class"]
            if (
                any(row[field] is not None for field in response_fields)
                or not isinstance(error_class, str)
                or not error_class
            ):
                raise SpoolIntegrityError("UNKNOWN spool row semantics drifted")
            return
        if status_value == "COMPLETE":
            response_status = row["response_status"]
            if (
                isinstance(response_status, bool)
                or not isinstance(response_status, int)
                or not 100 <= response_status <= 599
                or any(row[field] is None for field in response_fields[1:])
                or row["error_class"] is not None
                or not isinstance(row["response_sha256"], str)
                or _SHA256.fullmatch(row["response_sha256"]) is None
            ):
                raise SpoolIntegrityError("COMPLETE spool row semantics drifted")
            response = bytes(row["response_body"])
            if _sha256_bytes(response) != row["response_sha256"]:
                raise SpoolIntegrityError("stored spool response bytes drifted")
            try:
                headers = json.loads(bytes(row["response_headers"]).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise SpoolIntegrityError("stored spool response headers drifted") from error
            if not isinstance(headers, dict) or _canonical_bytes(headers) != bytes(row["response_headers"]):
                raise SpoolIntegrityError("stored spool response headers are not canonical")

    @classmethod
    def _verify_connection_rows(cls, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        rows = connection.execute(
            "SELECT * FROM spool_calls ORDER BY physical_call_id"
        ).fetchall()
        for row in rows:
            cls._verify_row(row)
        return rows

    @staticmethod
    def _result(row: sqlite3.Row, *, replayed: bool) -> SpoolResult:
        SQLiteResultSpool._verify_row(row)
        if row["status"] != "COMPLETE":
            status = str(row["status"])
            raise SpoolOutcomeUnknown(
                f"physical call outcome is {status}; fresh inference forbidden",
                code="OUTCOME_PENDING" if status == "DISPATCHING" else "OUTCOME_UNKNOWN",
            )
        return SpoolResult(
            physical_call_id=str(row["physical_call_id"]),
            intent_sha256=str(row["intent_sha256"]),
            request_sha256=str(row["request_sha256"]),
            status=int(row["response_status"]),
            headers=dict(json.loads(bytes(row["response_headers"]).decode("utf-8"))),
            body=bytes(row["response_body"]),
            body_sha256=str(row["response_sha256"]),
            replayed=replayed,
        )

    def execute(
        self,
        *,
        physical_call_id: str,
        intent_sha256: str,
        request_bytes: bytes,
        upstream: Callable[[bytes], RawHTTPResponse],
        pre_dispatch: Callable[[], None] | None = None,
    ) -> SpoolResult:
        """Dispatch at most once, then replay the first committed response bytes."""

        _require_sha256(physical_call_id, "physical_call_id")
        _require_sha256(intent_sha256, "intent_sha256")
        if not isinstance(request_bytes, bytes) or not request_bytes:
            raise ResultSpoolError("request_bytes must be non-empty bytes")
        request_sha256 = _sha256_bytes(request_bytes)
        with self._lock:
            self.require_checkpoint_policy()
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                row = self._connection.execute(
                    "SELECT * FROM spool_calls WHERE physical_call_id=?",
                    (physical_call_id,),
                ).fetchone()
                if row is not None:
                    self._verify_row(row)
                    if (
                        row["intent_sha256"] != intent_sha256
                        or row["request_sha256"] != request_sha256
                        or bytes(row["request_bytes"]) != request_bytes
                    ):
                        raise SpoolIdentityConflict(
                            "same physical_call_id carries different request intent"
                        )
                    self._connection.execute("COMMIT")
                    return self._result(row, replayed=True)
                if pre_dispatch is not None:
                    pre_dispatch()
                self._connection.execute(
                    """
                    INSERT INTO spool_calls(
                        physical_call_id,intent_sha256,request_sha256,
                        request_bytes,status
                    ) VALUES(?,?,?,?,'DISPATCHING')
                    """,
                    (physical_call_id, intent_sha256, request_sha256, request_bytes),
                )
                self._connection.execute("COMMIT")
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

        try:
            response = upstream(request_bytes)
            if not isinstance(response, RawHTTPResponse):
                raise ResultSpoolError("upstream must return RawHTTPResponse")
            if not 100 <= response.status <= 599:
                raise ResultSpoolError("upstream HTTP status is invalid")
            if not isinstance(response.body, bytes):
                raise ResultSpoolError("upstream response body must be bytes")
            safe_headers = _safe_headers(response.headers)
            headers_bytes = _canonical_bytes(safe_headers)
            response_sha256 = _sha256_bytes(response.body)
        except BaseException as error:
            with self._lock:
                self._connection.execute("BEGIN IMMEDIATE")
                self._connection.execute(
                    """
                    UPDATE spool_calls SET status='UNKNOWN', error_class=?
                    WHERE physical_call_id=? AND status='DISPATCHING'
                    """,
                    (type(error).__name__, physical_call_id),
                )
                self._connection.execute("COMMIT")
            raise SpoolOutcomeUnknown(
                f"upstream outcome unknown after dispatch: {type(error).__name__}"
            ) from error

        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                updated = self._connection.execute(
                    """
                    UPDATE spool_calls
                    SET status='COMPLETE', response_status=?, response_headers=?,
                        response_body=?, response_sha256=?, error_class=NULL
                    WHERE physical_call_id=? AND status='DISPATCHING'
                    """,
                    (
                        response.status,
                        headers_bytes,
                        response.body,
                        response_sha256,
                        physical_call_id,
                    ),
                )
                if updated.rowcount != 1:
                    raise SpoolIntegrityError("spool lost DISPATCHING state before commit")
                self._connection.execute("COMMIT")
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise
            row = self._connection.execute(
                "SELECT * FROM spool_calls WHERE physical_call_id=?", (physical_call_id,)
            ).fetchone()
            if row is None:
                raise SpoolIntegrityError("committed spool result disappeared")
            return self._result(row, replayed=False)

    def get(self, physical_call_id: str) -> SpoolResult:
        _require_sha256(physical_call_id, "physical_call_id")
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM spool_calls WHERE physical_call_id=?", (physical_call_id,)
            ).fetchone()
            if row is None:
                raise SpoolOutcomeUnknown(
                    "physical call is absent from result spool", code="OUTCOME_ABSENT"
                )
            return self._result(row, replayed=True)

    def audit(self) -> dict[str, object]:
        with self._lock:
            rows = self._verify_connection_rows(self._connection)
            statuses: dict[str, int] = {}
            completed = []
            for row in rows:
                status = str(row["status"])
                statuses[status] = statuses.get(status, 0) + 1
                if status == "COMPLETE":
                    completed.append(
                        {
                            "physical_call_id": row["physical_call_id"],
                            "intent_sha256": row["intent_sha256"],
                            "request_sha256": row["request_sha256"],
                            "response_sha256": row["response_sha256"],
                        }
                    )
            unsigned = {
                "schema_version": SPOOL_SCHEMA,
                "journal_mode": self.journal_mode,
                "synchronous": self.synchronous,
                "call_count": len(rows),
                "status_counts": statuses,
                "completed_root_sha256": canonical_sha256(completed),
            }
            return {**unsigned, "audit_sha256": canonical_sha256(unsigned)}

    def close(self) -> None:
        with self._lock:
            try:
                if self._require_no_checkpoint_on_close:
                    if not _configure_checkpoint_policy(
                        self._connection, "result spool"
                    ):
                        raise SpoolIntegrityError(
                            "result-spool sealed close policy drifted"
                        )
                self._connection.close()
            finally:
                if self._parent_fd >= 0:
                    os.close(self._parent_fd)
                    self._parent_fd = -1

    def __enter__(self) -> "SQLiteResultSpool":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


class ResultSpoolService:
    """HTTP-facing adapter from idempotent PUTs to one upstream POST."""

    def __init__(
        self,
        store: SQLiteResultSpool,
        *,
        upstream_endpoint: str,
        deployment_binding: ModelDeploymentBinding,
        deployment_receipt_path: str | Path,
        upstream_transport: UpstreamTransport | None = None,
        api_key: str | None = None,
        client_token: str | None = None,
        timeout_seconds: float = 180.0,
        max_response_bytes: int = 4_000_000,
    ) -> None:
        normalized_upstream = normalize_upstream_endpoint(upstream_endpoint)
        if normalized_upstream != deployment_binding.upstream_endpoint:
            raise ResultSpoolError("upstream endpoint differs from deployment binding")
        if timeout_seconds <= 0 or max_response_bytes <= 0:
            raise ResultSpoolError("timeout and response byte cap must be positive")
        self.store = store
        self.upstream_endpoint = normalized_upstream
        self.deployment_binding = deployment_binding
        self.deployment_receipt_path = Path(deployment_receipt_path)
        self.api_key = api_key
        self.client_token = client_token
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.upstream_transport = upstream_transport or self._urlopen

    def identity(self) -> dict[str, object]:
        resolved = self.store.path.resolve()
        try:
            info = resolved.stat()
        except OSError as error:
            raise SpoolIntegrityError("cannot stat live spool database") from error
        audit = self.store.audit()
        unsigned = {
            "schema_version": SPOOL_IDENTITY_SCHEMA,
            "normalized_upstream_endpoint": self.upstream_endpoint,
            "deployment_receipt_sha256": (
                self.deployment_binding.deployment_receipt_sha256
            ),
            "deployment_id": self.deployment_binding.deployment_id,
            "served_model": self.deployment_binding.served_model,
            "model_revision": self.deployment_binding.model_revision,
            "db_identity": {
                "resolved_path": str(resolved),
                "st_dev": int(info.st_dev),
                "st_ino": int(info.st_ino),
            },
            "audit": audit,
        }
        return {**unsigned, "identity_sha256": canonical_sha256(unsigned)}

    def _verify_live_deployment(self) -> None:
        observed = load_model_deployment_binding(
            self.deployment_receipt_path,
            upstream_endpoint=self.upstream_endpoint,
            served_model=self.deployment_binding.served_model,
            model_revision=self.deployment_binding.model_revision,
            verify_live_process=True,
        )
        if observed != self.deployment_binding:
            raise ResultSpoolError("live deployment differs from startup binding")

    def _verify_request_model(self, request_bytes: bytes) -> None:
        def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise ResultSpoolError(
                        f"upstream request contains duplicate JSON key {key!r}"
                    )
                value[key] = item
            return value

        try:
            value = json.loads(request_bytes.decode("utf-8"), object_pairs_hook=object_pairs)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ResultSpoolError("upstream request is not strict JSON") from error
        if not isinstance(value, Mapping):
            raise ResultSpoolError("upstream request must be a JSON object")
        if value.get("model") != self.deployment_binding.served_model:
            raise ResultSpoolError("request model differs from the attested served model")

    def _urlopen(self, request: urllib_request.Request, timeout: float) -> RawHTTPResponse:
        try:
            with urllib_request.urlopen(request, timeout=timeout) as response:
                body = response.read(self.max_response_bytes + 1)
                return RawHTTPResponse(
                    status=int(response.status),
                    headers={key: value for key, value in response.headers.items()},
                    body=body,
                )
        except urllib_error.HTTPError as error:
            return RawHTTPResponse(
                status=int(error.code),
                headers={key: value for key, value in error.headers.items()},
                body=error.read(self.max_response_bytes + 1),
            )

    def execute(
        self, physical_call_id: str, intent_sha256: str, request_bytes: bytes
    ) -> SpoolResult:
        self._verify_request_model(request_bytes)

        def upstream(body: bytes) -> RawHTTPResponse:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            request = urllib_request.Request(
                self.upstream_endpoint,
                data=body,
                headers=headers,
                method="POST",
            )
            response = self.upstream_transport(request, self.timeout_seconds)
            if len(response.body) > self.max_response_bytes:
                raise ResultSpoolError("upstream response exceeds configured byte limit")
            declared = response.headers.get("Content-Length") or response.headers.get("content-length")
            if declared is not None:
                try:
                    expected = int(declared)
                except ValueError as error:
                    raise ResultSpoolError("upstream Content-Length is invalid") from error
                if expected != len(response.body):
                    raise ResultSpoolError("upstream HTTP response body is incomplete")
            return response

        return self.store.execute(
            physical_call_id=physical_call_id,
            intent_sha256=intent_sha256,
            request_bytes=request_bytes,
            upstream=upstream,
            pre_dispatch=self._verify_live_deployment,
        )


class ResultSpoolHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        service: ResultSpoolService,
        *,
        disconnect_after_commit_once: bool = False,
        max_request_bytes: int = 4_000_000,
    ) -> None:
        self.service = service
        self.disconnect_after_commit_once = disconnect_after_commit_once
        self.max_request_bytes = max_request_bytes
        self._fault_lock = threading.Lock()
        if server_address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise ResultSpoolError(
                "result spool must bind loopback; use an authenticated TLS/SSH tunnel"
            )
        super().__init__(server_address, _ResultSpoolHandler)

    def consume_disconnect_fault(self) -> bool:
        with self._fault_lock:
            value = self.disconnect_after_commit_once
            self.disconnect_after_commit_once = False
            return value


class _ResultSpoolHandler(BaseHTTPRequestHandler):
    server: ResultSpoolHTTPServer

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _json_error(self, status: int, code: str, detail: str) -> None:
        body = _canonical_bytes({"status": "REFUSED", "code": code, "detail": detail})
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if self.server.service.client_token is None:
            return True
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.service.client_token}"
        if hmac.compare_digest(supplied, expected):
            return True
        self._json_error(
            HTTPStatus.UNAUTHORIZED,
            "UNAUTHORIZED",
            "result-spool bearer token is missing or invalid",
        )
        return False

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != SPOOL_IDENTITY_ROUTE:
            self._json_error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "unknown spool route")
            return
        if not self._authorized():
            return
        try:
            body = _canonical_bytes(self.server.service.identity())
        except ResultSpoolError as error:
            self._json_error(HTTPStatus.INTERNAL_SERVER_ERROR, "IDENTITY_ERROR", str(error))
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self.path.startswith(SPOOL_ROUTE_PREFIX):
            self._json_error(HTTPStatus.NOT_FOUND, "NOT_FOUND", "unknown spool route")
            return
        physical_call_id = self.path[len(SPOOL_ROUTE_PREFIX) :]
        intent_sha256 = self.headers.get("X-HSWM-Intent-SHA256", "")
        try:
            if not self._authorized():
                return
            _require_sha256(physical_call_id, "physical_call_id")
            _require_sha256(intent_sha256, "intent_sha256")
            if (
                self.headers.get("X-HSWM-Model-Revision")
                != self.server.service.deployment_binding.model_revision
            ):
                raise ResultSpoolError("model revision differs from the configured spool revision")
            declared = int(self.headers.get("Content-Length", "-1"))
            if declared < 1 or declared > self.server.max_request_bytes:
                raise ResultSpoolError("request Content-Length is missing or out of range")
            body = self.rfile.read(declared)
            if len(body) != declared:
                raise ResultSpoolError("request body is incomplete")
            result = self.server.service.execute(physical_call_id, intent_sha256, body)
        except SpoolIdentityConflict as error:
            self._json_error(HTTPStatus.CONFLICT, "IDENTITY_CONFLICT", str(error))
            return
        except SpoolOutcomeUnknown as error:
            self._json_error(HTTPStatus.TOO_EARLY, error.code, str(error))
            return
        except (ResultSpoolError, ValueError) as error:
            self._json_error(HTTPStatus.BAD_REQUEST, "INVALID_REQUEST", str(error))
            return
        if self.server.consume_disconnect_fault():
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.connection.close()
            self.close_connection = True
            return
        self.send_response(result.status)
        for key, value in result.headers.items():
            if key not in {"content-length"}:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(result.body)))
        self.send_header("X-HSWM-Spool-Call-Id", result.physical_call_id)
        self.send_header("X-HSWM-Spool-Intent-SHA256", result.intent_sha256)
        self.send_header("X-HSWM-Spool-Request-SHA256", result.request_sha256)
        self.send_header("X-HSWM-Spool-Response-SHA256", result.body_sha256)
        self.send_header("X-HSWM-Spool-Replayed", "true" if result.replayed else "false")
        self.send_header(
            "X-HSWM-Spool-Server-Revision",
            self.server.service.deployment_binding.model_revision,
        )
        self.end_headers()
        self.wfile.write(result.body)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--served-model", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--model-deployment-receipt", type=Path, required=True)
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=8010)
    parser.add_argument("--api-key-env")
    parser.add_argument("--client-token-env")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-response-bytes", type=int, default=4_000_000)
    args = parser.parse_args(argv)
    api_key = None
    if args.api_key_env:
        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            parser.error(f"missing API key environment: {args.api_key_env}")
    client_token = None
    if args.client_token_env:
        client_token = os.environ.get(args.client_token_env)
        if not client_token:
            parser.error(f"missing spool client token environment: {args.client_token_env}")
    try:
        deployment_binding = load_model_deployment_binding(
            args.model_deployment_receipt,
            upstream_endpoint=args.upstream,
            served_model=args.served_model,
            model_revision=args.model_revision,
            verify_live_process=True,
        )
    except ResultSpoolError as error:
        parser.error(str(error))
    try:
        store = SQLiteResultSpool(
            args.db, require_no_checkpoint_on_close=True
        )
    except SpoolIntegrityError as error:
        parser.error(str(error))
    service = ResultSpoolService(
        store,
        upstream_endpoint=deployment_binding.upstream_endpoint,
        deployment_binding=deployment_binding,
        deployment_receipt_path=args.model_deployment_receipt,
        api_key=api_key,
        client_token=client_token,
        timeout_seconds=args.timeout_seconds,
        max_response_bytes=args.max_response_bytes,
    )
    server = ResultSpoolHTTPServer((args.listen_host, args.listen_port), service)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ModelDeploymentBinding",
    "RawHTTPResponse",
    "ResultSpoolError",
    "ResultSpoolHTTPServer",
    "ResultSpoolService",
    "SPOOL_IDENTITY_ROUTE",
    "SPOOL_IDENTITY_SCHEMA",
    "SPOOL_ROUTE_PREFIX",
    "SPOOL_SCHEMA",
    "SQLiteResultSpool",
    "SpoolIdentityConflict",
    "SpoolIntegrityError",
    "SpoolOutcomeUnknown",
    "SpoolResult",
    "load_model_deployment_binding",
    "normalize_upstream_endpoint",
]
