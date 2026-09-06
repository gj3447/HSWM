"""Bounded Python transport for the internal D4 Atom V2 study process.

This adapter does not authorize arbitrary atom mutation or judge D4. The
process constructs and validates the declared schema and persists its state
and exact Lean decision in one journal. Compilation requires a separate
recovery process; commit output is never used as a compiled disposition.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

from hswm.selfmod.contracts import canonical_json_bytes
from .d4_heldout_task import TaskContract, compile_recovered

CONTRACT_VERSION = "hswm-d4-study-process/v1"
MAX_REQUEST_BYTES = 262_144
MAX_RESPONSE_BYTES = 1_048_576
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_UID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")


class D4StudyBridgeError(RuntimeError):
    """A request, process, or persisted-state binding failed closed."""


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise D4StudyBridgeError(f"{label} is not a SHA-256 digest")
    return value


def _bytes(value: object, digest: object, label: str) -> bytes:
    if not isinstance(value, str) or len(value) > MAX_RESPONSE_BYTES:
        raise D4StudyBridgeError(f"{label} encoding is invalid")
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, TypeError) as error:
        raise D4StudyBridgeError(f"{label} encoding is invalid") from error
    if (not raw or len(raw) > MAX_REQUEST_BYTES
            or base64.urlsafe_b64encode(raw).decode().rstrip("=") != value
            or sha256(raw).hexdigest() != _digest(digest, label)):
        raise D4StudyBridgeError(f"{label} byte binding is invalid")
    return raw


def _object(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise D4StudyBridgeError("process JSON repeats a key")
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, UnicodeDecodeError) as error:
        raise D4StudyBridgeError("process output is not JSON") from error
    if not isinstance(value, dict):
        raise D4StudyBridgeError("process output is not an object")
    return value


@dataclass(frozen=True)
class RecoveredD4Disposition:
    receipt: Mapping[str, Any]
    post_state_bytes: bytes
    disposition_bytes: bytes
    compiled: Mapping[str, Any]


@dataclass(frozen=True)
class D4StudyProcess:
    runtime: Path
    script: Path
    lean_executable: Path
    timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        for label, path in (("runtime", self.runtime), ("script", self.script),
                            ("Lean executable", self.lean_executable)):
            if not path.is_absolute() or not path.is_file():
                raise D4StudyBridgeError(f"{label} must be an absolute existing file")
        if not 0 < self.timeout_seconds <= 120:
            raise D4StudyBridgeError("process timeout must be within (0,120] seconds")

    def _request(self, operation: str, *, root: Path, trust: Path,
                 occurrence_uid: str, **extra: Any) -> dict[str, Any]:
        if (not root.is_absolute() or not trust.is_absolute() or root.is_symlink()
                or trust.is_symlink() or trust != root / "trust-snapshot.json"
                or not _UID.fullmatch(occurrence_uid)):
            raise D4StudyBridgeError("process roots or occurrence identity are invalid")
        request = {"contractVersion": CONTRACT_VERSION, "operation": operation,
                   "rootPath": str(root), "trustSnapshotPath": str(trust),
                   "leanExecutable": str(self.lean_executable),
                   "occurrenceUid": occurrence_uid, **extra}
        raw = canonical_json_bytes(request)
        if len(raw) > MAX_REQUEST_BYTES:
            raise D4StudyBridgeError("process request exceeds byte budget")
        try:
            completed = subprocess.run([str(self.runtime), str(self.script)], input=raw,
                                       capture_output=True, timeout=self.timeout_seconds,
                                       check=False, shell=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise D4StudyBridgeError(f"D4 process did not finish: {type(error).__name__}") from error
        if completed.returncode != 0:
            raise D4StudyBridgeError(f"D4 process rejected the operation (exit {completed.returncode})")
        if len(completed.stdout) > MAX_RESPONSE_BYTES:
            raise D4StudyBridgeError("process response exceeds byte budget")
        receipt = _object(completed.stdout)
        if (receipt.get("contractVersion") != CONTRACT_VERSION
                or receipt.get("operation") != operation
                or receipt.get("occurrenceUid") != occurrence_uid):
            raise D4StudyBridgeError("process response identity drifted")
        state = _bytes(receipt.get("postStateBase64Url"), receipt.get("postStateSha256"), "post-state")
        head = receipt.get("head")
        if (not isinstance(head, dict)
                or set(head) != {"lineageId", "sequence", "stateDigest", "recordDigest"}
                or head["lineageId"] != f"lineage:d4:{occurrence_uid}"
                or type(head["sequence"]) is not int or head["sequence"] != 1
                or head["stateDigest"] != sha256(state).hexdigest()):
            raise D4StudyBridgeError("recovered head does not bind the post-state")
        _digest(head["recordDigest"], "head record")
        _digest(receipt.get("trustSnapshotSha256"), "trust snapshot")
        if not trust.is_file() or sha256(trust.read_bytes()).hexdigest() != receipt["trustSnapshotSha256"]:
            raise D4StudyBridgeError("trust snapshot bytes do not match process receipt")
        return receipt

    def commit(self, *, root: Path, trust: Path, occurrence_uid: str,
               payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        if set(payloads) != {"task", "instance", "trajectory", "outcome", "credit", "disposition"}:
            raise D4StudyBridgeError("D4 commit requires the six declared payloads")
        receipt = self._request("commit", root=root, trust=trust,
                                occurrence_uid=occurrence_uid, mode="ACTIVE",
                                lifetimeMs=60_000, payloads=dict(payloads))
        if receipt.get("mode") != "ACTIVE":
            raise D4StudyBridgeError("D4 commit mode drifted")
        for key in ("leanRequestSha256", "leanDecisionSha256", "commitRecordSha256"):
            _digest(receipt.get(key), key)
        return receipt

    def recover(self, *, root: Path, trust: Path, occurrence_uid: str,
                contract: TaskContract, expected_post_state_sha256: str) -> RecoveredD4Disposition:
        receipt = self._request("recover", root=root, trust=trust,
                                occurrence_uid=occurrence_uid)
        if receipt["postStateSha256"] != _digest(expected_post_state_sha256, "expected post-state"):
            raise D4StudyBridgeError("fresh recovery returned a different state")
        disposition = _bytes(receipt.get("compiledDispositionBase64Url"),
                             receipt.get("compiledDispositionSha256"), "compiled disposition")
        value = _object(disposition)
        if canonical_json_bytes(value) != disposition:
            raise D4StudyBridgeError("recovered disposition is not canonical JSON")
        compiled = compile_recovered(contract=contract, disposition=value)
        return RecoveredD4Disposition(receipt, _bytes(receipt["postStateBase64Url"],
                                       receipt["postStateSha256"], "post-state"), disposition, compiled)
