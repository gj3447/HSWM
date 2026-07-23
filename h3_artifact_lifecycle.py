"""First-write artifact lifecycle receipts for the H3 confirmatory run.

An output hash written only after production does not rule out cherry-picking.
This module therefore commits the destination *before* production and closes
the same durably anchored inode or exclusive run directory afterwards.  An
append log keeps a same-directory hard-link anchor so unlink/recreate cannot be
hidden by filesystem inode reuse.  Development opens are authorized by the
frozen manifest and preflight receipt.  Fresh opens require the additional
certificate-transition hash.

The helpers are intentionally storage-level.  Domain loaders still have to
revalidate extraction rows or embedding receipts before supplying the close
``validation`` object; consumers compare that object with their own result.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

from world_ir import canonical_json


OPEN_SCHEMA_VERSION = "hswm-h3-artifact-open/v2"
CLOSE_SCHEMA_VERSION = "hswm-h3-artifact-close/v2"
STAGES = ("development", "fresh")
MODES = ("append_log", "exclusive_bundle")
PARENT_KEYS = frozenset({
    "run_manifest_sha256", "protocol_sha256", "code_root_sha256",
    "preflight_receipt_sha256",
})
FRESH_PARENT_KEYS = PARENT_KEYS | {"certificate_transition_sha256"}
OPEN_KEYS = frozenset({
    "schema_version", "receipt_id", "stage", "artifact_kind", "mode",
    "authorization", "input_sha256", "config_sha256",
    "deployment_attestation_sha256", "producer_code_sha256", "reservation",
})
CLOSE_KEYS = frozenset({
    "schema_version", "receipt_id", "open_receipt_sha256", "open_receipt_id",
    "stage", "artifact_kind", "mode", "outputs", "validation",
})
SHA256_RE = re.compile(r"[0-9a-f]{64}")


class ArtifactLifecycleError(RuntimeError):
    """An output was not produced inside its committed first-write boundary."""


def _file_sha256_and_stat(
    path: str | Path,
    *,
    expected_identity: tuple[int, int] | None = None,
) -> tuple[str, os.stat_result]:
    candidate = Path(path)
    try:
        path_before = candidate.lstat()
    except OSError as exc:
        raise ArtifactLifecycleError(f"cannot inspect artifact: {candidate}") from exc
    if not stat.S_ISREG(path_before.st_mode):
        raise ArtifactLifecycleError(f"artifact is not a regular file: {candidate}")
    flags = os.O_RDONLY | int(getattr(os, "O_NOFOLLOW", 0))
    try:
        descriptor = os.open(candidate, flags)
    except OSError as exc:
        raise ArtifactLifecycleError(
            f"cannot open artifact without following links: {candidate}"
        ) from exc
    digest = sha256()
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ArtifactLifecycleError(f"artifact is not a regular file: {candidate}")
        identity = (int(opened.st_dev), int(opened.st_ino))
        path_identity = (int(path_before.st_dev), int(path_before.st_ino))
        if identity != path_identity:
            raise ArtifactLifecycleError(f"artifact changed while opening: {candidate}")
        if expected_identity is not None and identity != expected_identity:
            raise ArtifactLifecycleError("reserved path inode/device changed")
        for chunk in iter(lambda: os.read(descriptor, 1024 * 1024), b""):
            digest.update(chunk)
        closed = os.fstat(descriptor)
        try:
            path_after = candidate.lstat()
        except OSError as exc:
            raise ArtifactLifecycleError(
                f"artifact changed while hashing: {candidate}"
            ) from exc
        before_fingerprint = (
            int(opened.st_dev), int(opened.st_ino), int(opened.st_mode),
            int(opened.st_size), int(opened.st_mtime_ns), int(opened.st_ctime_ns),
        )
        if before_fingerprint != (
            int(closed.st_dev), int(closed.st_ino), int(closed.st_mode),
            int(closed.st_size), int(closed.st_mtime_ns), int(closed.st_ctime_ns),
        ) or before_fingerprint != (
            int(path_after.st_dev), int(path_after.st_ino), int(path_after.st_mode),
            int(path_after.st_size), int(path_after.st_mtime_ns),
            int(path_after.st_ctime_ns),
        ):
            raise ArtifactLifecycleError(f"artifact changed while hashing: {candidate}")
    finally:
        os.close(descriptor)
    return digest.hexdigest(), closed


def file_sha256(path: str | Path) -> str:
    digest, _ = _file_sha256_and_stat(path)
    return digest


def _sha(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ArtifactLifecycleError(f"{label} must be a lower-case SHA-256")
    return value


def _canonical_path(path: str | Path) -> str:
    value = Path(path).expanduser()
    if not value.is_absolute():
        value = Path.cwd() / value
    return str(value.resolve(strict=False))


def _append_anchor_path(output: Path) -> Path:
    """Return the durable same-filesystem identity anchor for an append log."""

    return output.with_name(f".{output.name}.hswm-open-anchor")


def _receipt_id(prefix: str, value: Mapping[str, Any]) -> str:
    body = {key: child for key, child in value.items() if key != "receipt_id"}
    return prefix + sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _write_once(path: str | Path, value: Mapping[str, Any]) -> str:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = (canonical_json(dict(value)) + "\n").encode("utf-8")
    try:
        descriptor = os.open(
            output, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError as exc:
        raise ArtifactLifecycleError(
            f"receipt path is first-write-wins: {output}"
        ) from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            output.unlink()
        except OSError:
            pass
        raise
    _fsync_directory(output.parent)
    return sha256(encoded).hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_authorization(stage: str, value: Any) -> dict[str, str]:
    expected = FRESH_PARENT_KEYS if stage == "fresh" else PARENT_KEYS
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ArtifactLifecycleError(
            f"{stage} authorization keys must be exactly {sorted(expected)}"
        )
    return {
        key: _sha(value[key], label=f"authorization.{key}")
        for key in sorted(expected)
    }


def _base_open(
    *,
    stage: str,
    artifact_kind: str,
    mode: str,
    authorization: Mapping[str, str],
    input_sha256: str,
    config_sha256: str,
    deployment_attestation_sha256: str,
    producer_code_sha256: str,
    reservation: Mapping[str, Any],
) -> dict[str, Any]:
    if stage not in STAGES or mode not in MODES or not artifact_kind:
        raise ArtifactLifecycleError("valid stage/artifact_kind/mode are required")
    value: dict[str, Any] = {
        "schema_version": OPEN_SCHEMA_VERSION,
        "receipt_id": "",
        "stage": stage,
        "artifact_kind": artifact_kind,
        "mode": mode,
        "authorization": _validate_authorization(stage, authorization),
        "input_sha256": _sha(input_sha256, label="input_sha256"),
        "config_sha256": _sha(config_sha256, label="config_sha256"),
        "deployment_attestation_sha256": _sha(
            deployment_attestation_sha256,
            label="deployment_attestation_sha256",
        ),
        "producer_code_sha256": _sha(
            producer_code_sha256, label="producer_code_sha256",
        ),
        "reservation": dict(reservation),
    }
    value["receipt_id"] = _receipt_id("hswm:h3_artifact_open:v2:", value)
    return value


def open_append_log(
    *,
    output_path: str | Path,
    open_receipt_path: str | Path,
    stage: str,
    artifact_kind: str,
    authorization: Mapping[str, str],
    input_sha256: str,
    config_sha256: str,
    deployment_attestation_sha256: str,
    producer_code_sha256: str,
) -> dict[str, Any]:
    """Reserve an exact empty append log with ``O_EXCL`` and bind its inode."""

    _base_open(
        stage=stage, artifact_kind=artifact_kind, mode="append_log",
        authorization=authorization, input_sha256=input_sha256,
        config_sha256=config_sha256,
        deployment_attestation_sha256=deployment_attestation_sha256,
        producer_code_sha256=producer_code_sha256,
        reservation={
            "output_path": "/preflight", "anchor_path": "/preflight.anchor",
            "device": 0, "inode": 0, "initial_size": 0,
        },
    )
    output = Path(_canonical_path(output_path))
    anchor = _append_anchor_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(
            output, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError as exc:
        raise ArtifactLifecycleError(
            f"append output must be nonexistent before OPEN: {output}"
        ) from exc
    anchor_created = False
    try:
        os.fsync(descriptor)
        opened = os.fstat(descriptor)
        try:
            os.link(output, anchor, follow_symlinks=False)
        except FileExistsError as exc:
            raise ArtifactLifecycleError(
                f"append identity anchor must be nonexistent before OPEN: {anchor}"
            ) from exc
        except OSError as exc:
            raise ArtifactLifecycleError(
                f"cannot create append identity anchor: {anchor}"
            ) from exc
        anchor_created = True
        observed = output.lstat()
        anchored = anchor.lstat()
        expected_identity = (int(opened.st_dev), int(opened.st_ino))
        if (
            not stat.S_ISREG(observed.st_mode)
            or not stat.S_ISREG(anchored.st_mode)
            or (int(observed.st_dev), int(observed.st_ino)) != expected_identity
            or (int(anchored.st_dev), int(anchored.st_ino)) != expected_identity
            or observed.st_nlink < 2
            or anchored.st_nlink < 2
        ):
            raise ArtifactLifecycleError("append identity changed during OPEN")
    except BaseException:
        if anchor_created:
            try:
                anchor.unlink()
            except OSError:
                pass
        try:
            output.unlink()
        except OSError:
            pass
        raise
    finally:
        os.close(descriptor)
    _fsync_directory(output.parent)
    reservation = {
        "output_path": str(output),
        "anchor_path": str(anchor),
        "device": int(opened.st_dev),
        "inode": int(opened.st_ino),
        "initial_size": int(opened.st_size),
    }
    if reservation["initial_size"] != 0:
        raise ArtifactLifecycleError("new append output was not empty")
    receipt = _base_open(
        stage=stage, artifact_kind=artifact_kind, mode="append_log",
        authorization=authorization, input_sha256=input_sha256,
        config_sha256=config_sha256,
        deployment_attestation_sha256=deployment_attestation_sha256,
        producer_code_sha256=producer_code_sha256, reservation=reservation,
    )
    try:
        _write_once(open_receipt_path, receipt)
    except BaseException:
        try:
            anchor.unlink()
        except OSError:
            pass
        try:
            output.unlink()
        except OSError:
            pass
        raise
    return receipt


def open_exclusive_bundle(
    *,
    run_directory: str | Path,
    expected_outputs: Mapping[str, str | Path],
    open_receipt_path: str | Path,
    stage: str,
    artifact_kind: str,
    authorization: Mapping[str, str],
    input_sha256: str,
    config_sha256: str,
    deployment_attestation_sha256: str,
    producer_code_sha256: str,
) -> dict[str, Any]:
    """Reserve a new run directory whose final outputs do not yet exist."""

    if not expected_outputs or any(not str(key) for key in expected_outputs):
        raise ArtifactLifecycleError("bundle outputs must be a non-empty mapping")
    _base_open(
        stage=stage, artifact_kind=artifact_kind, mode="exclusive_bundle",
        authorization=authorization, input_sha256=input_sha256,
        config_sha256=config_sha256,
        deployment_attestation_sha256=deployment_attestation_sha256,
        producer_code_sha256=producer_code_sha256,
        reservation={
            "run_directory": "/preflight", "device": 0, "inode": 0,
            "expected_outputs": {"preflight": "/preflight/output"},
        },
    )
    run_dir = Path(_canonical_path(run_directory))
    run_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.mkdir(run_dir, 0o700)
    except FileExistsError as exc:
        raise ArtifactLifecycleError(
            f"bundle run directory must be nonexistent before OPEN: {run_dir}"
        ) from exc
    opened = run_dir.stat()
    outputs: dict[str, str] = {}
    try:
        for key, path in sorted(expected_outputs.items()):
            output = Path(_canonical_path(path))
            if output.parent != run_dir:
                raise ArtifactLifecycleError(
                    "every exclusive bundle output must be a direct run-dir child"
                )
            if output.exists():
                raise ArtifactLifecycleError(
                    f"bundle output exists before OPEN: {output}"
                )
            outputs[str(key)] = str(output)
        receipt = _base_open(
            stage=stage, artifact_kind=artifact_kind, mode="exclusive_bundle",
            authorization=authorization, input_sha256=input_sha256,
            config_sha256=config_sha256,
            deployment_attestation_sha256=deployment_attestation_sha256,
            producer_code_sha256=producer_code_sha256,
            reservation={
                "run_directory": str(run_dir),
                "device": int(opened.st_dev),
                "inode": int(opened.st_ino),
                "expected_outputs": outputs,
            },
        )
        _write_once(open_receipt_path, receipt)
    except BaseException:
        try:
            run_dir.rmdir()
        except OSError:
            pass
        raise
    _fsync_directory(run_dir.parent)
    return receipt


def publish_no_replace(temporary_path: str | Path, final_path: str | Path) -> None:
    """Atomically publish a file without ever replacing an existing target."""

    temporary = Path(temporary_path)
    final = Path(final_path)
    if temporary.parent.resolve() != final.parent.resolve():
        raise ArtifactLifecycleError("temporary and final output must share a directory")
    try:
        os.link(temporary, final)
    except FileExistsError as exc:
        raise ArtifactLifecycleError(
            f"refusing to replace existing bundle output: {final}"
        ) from exc
    with final.open("rb") as handle:
        os.fsync(handle.fileno())
    temporary.unlink()
    _fsync_directory(final.parent)


def load_open_receipt(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactLifecycleError(f"invalid OPEN receipt: {exc}") from exc
    if not isinstance(value, Mapping) or set(value) != OPEN_KEYS:
        raise ArtifactLifecycleError("OPEN receipt keys do not match v2")
    value = dict(value)
    if value["schema_version"] != OPEN_SCHEMA_VERSION:
        raise ArtifactLifecycleError("OPEN receipt schema mismatch")
    if value.get("receipt_id") != _receipt_id("hswm:h3_artifact_open:v2:", value):
        raise ArtifactLifecycleError("OPEN receipt self-hash mismatch")
    stage, mode = value.get("stage"), value.get("mode")
    if stage not in STAGES or mode not in MODES or not value.get("artifact_kind"):
        raise ArtifactLifecycleError("OPEN receipt stage/kind/mode invalid")
    _validate_authorization(stage, value.get("authorization"))
    for key in (
        "input_sha256", "config_sha256", "deployment_attestation_sha256",
        "producer_code_sha256",
    ):
        _sha(value.get(key), label=key)
    reservation = value.get("reservation")
    if not isinstance(reservation, Mapping):
        raise ArtifactLifecycleError("OPEN reservation must be an object")
    if mode == "append_log":
        expected = {
            "output_path", "anchor_path", "device", "inode", "initial_size",
        }
        if (set(reservation) != expected or reservation.get("initial_size") != 0
                or not isinstance(reservation.get("output_path"), str)
                or not isinstance(reservation.get("anchor_path"), str)
                or type(reservation.get("device")) is not int
                or type(reservation.get("inode")) is not int):
            raise ArtifactLifecycleError("append OPEN reservation is malformed")
    else:
        expected = {"run_directory", "device", "inode", "expected_outputs"}
        if (set(reservation) != expected
                or type(reservation.get("device")) is not int
                or type(reservation.get("inode")) is not int
                or not isinstance(reservation.get("expected_outputs"), Mapping)
                or not reservation["expected_outputs"]):
            raise ArtifactLifecycleError("bundle OPEN reservation is malformed")
    return value


def _validate_live_reservation(open_receipt: Mapping[str, Any]) -> None:
    reservation = open_receipt["reservation"]
    if open_receipt["mode"] == "append_log":
        path = Path(reservation["output_path"])
    else:
        path = Path(reservation["run_directory"])
    try:
        observed = path.lstat()
    except OSError as exc:
        raise ArtifactLifecycleError("reserved artifact disappeared") from exc
    if (int(observed.st_dev), int(observed.st_ino)) != (
        reservation["device"], reservation["inode"],
    ):
        raise ArtifactLifecycleError("reserved path inode/device changed")
    if open_receipt["mode"] == "append_log" and not stat.S_ISREG(observed.st_mode):
        raise ArtifactLifecycleError("reserved append output is not a regular file")
    if open_receipt["mode"] == "append_log":
        anchor = Path(reservation["anchor_path"])
        try:
            anchored = anchor.lstat()
        except OSError as exc:
            raise ArtifactLifecycleError(
                "reserved append identity anchor disappeared"
            ) from exc
        if (
            not stat.S_ISREG(anchored.st_mode)
            or (int(anchored.st_dev), int(anchored.st_ino))
            != (reservation["device"], reservation["inode"])
            or observed.st_nlink < 2
            or anchored.st_nlink < 2
        ):
            raise ArtifactLifecycleError("reserved append identity anchor changed")
    if open_receipt["mode"] == "exclusive_bundle" and not stat.S_ISDIR(observed.st_mode):
        raise ArtifactLifecycleError("reserved bundle path is not a directory")


def _base_close(
    open_receipt: Mapping[str, Any],
    *,
    open_receipt_path: str | Path,
    outputs: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(validation, Mapping) or not validation:
        raise ArtifactLifecycleError("domain validation receipt is required")
    value: dict[str, Any] = {
        "schema_version": CLOSE_SCHEMA_VERSION,
        "receipt_id": "",
        "open_receipt_sha256": file_sha256(open_receipt_path),
        "open_receipt_id": open_receipt["receipt_id"],
        "stage": open_receipt["stage"],
        "artifact_kind": open_receipt["artifact_kind"],
        "mode": open_receipt["mode"],
        "outputs": dict(outputs),
        "validation": dict(validation),
    }
    value["receipt_id"] = _receipt_id("hswm:h3_artifact_close:v2:", value)
    return value


def close_append_log(
    *,
    open_receipt_path: str | Path,
    close_receipt_path: str | Path,
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    opened = load_open_receipt(open_receipt_path)
    if opened["mode"] != "append_log":
        raise ArtifactLifecycleError("OPEN receipt is not an append log")
    _validate_live_reservation(opened)
    reservation = opened["reservation"]
    path = Path(reservation["output_path"])
    output_sha256, observed = _file_sha256_and_stat(
        path,
        expected_identity=(reservation["device"], reservation["inode"]),
    )
    _validate_live_reservation(opened)
    size = observed.st_size
    if size <= 0:
        raise ArtifactLifecycleError("append log cannot CLOSE empty")
    receipt = _base_close(
        opened, open_receipt_path=open_receipt_path,
        outputs={
            "output_path": str(path), "output_sha256": output_sha256,
            "byte_count": int(size),
        },
        validation=validation,
    )
    _write_once(close_receipt_path, receipt)
    return load_close_receipt(
        close_receipt_path, open_receipt_path=open_receipt_path,
    )


def close_exclusive_bundle(
    *,
    open_receipt_path: str | Path,
    close_receipt_path: str | Path,
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    opened = load_open_receipt(open_receipt_path)
    if opened["mode"] != "exclusive_bundle":
        raise ArtifactLifecycleError("OPEN receipt is not an exclusive bundle")
    _validate_live_reservation(opened)
    outputs: dict[str, Any] = {}
    for key, path_value in sorted(
        opened["reservation"]["expected_outputs"].items()
    ):
        path = Path(path_value)
        try:
            observed = path.lstat()
        except OSError as exc:
            raise ArtifactLifecycleError(f"bundle output missing: {key}") from exc
        if not stat.S_ISREG(observed.st_mode) or observed.st_size <= 0:
            raise ArtifactLifecycleError(f"bundle output invalid: {key}")
        output_sha256, hashed = _file_sha256_and_stat(
            path,
            expected_identity=(int(observed.st_dev), int(observed.st_ino)),
        )
        outputs[str(key)] = {
            "path": str(path), "sha256": output_sha256,
            "byte_count": int(hashed.st_size),
        }
    receipt = _base_close(
        opened, open_receipt_path=open_receipt_path,
        outputs=outputs, validation=validation,
    )
    _write_once(close_receipt_path, receipt)
    return load_close_receipt(
        close_receipt_path, open_receipt_path=open_receipt_path,
    )


def load_close_receipt(
    path: str | Path,
    *,
    open_receipt_path: str | Path,
) -> dict[str, Any]:
    opened = load_open_receipt(open_receipt_path)
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactLifecycleError(f"invalid CLOSE receipt: {exc}") from exc
    if not isinstance(value, Mapping) or set(value) != CLOSE_KEYS:
        raise ArtifactLifecycleError("CLOSE receipt keys do not match v2")
    value = dict(value)
    if value["schema_version"] != CLOSE_SCHEMA_VERSION:
        raise ArtifactLifecycleError("CLOSE receipt schema mismatch")
    if value.get("receipt_id") != _receipt_id("hswm:h3_artifact_close:v2:", value):
        raise ArtifactLifecycleError("CLOSE receipt self-hash mismatch")
    if (value.get("open_receipt_sha256") != file_sha256(open_receipt_path)
            or value.get("open_receipt_id") != opened["receipt_id"]
            or value.get("stage") != opened["stage"]
            or value.get("artifact_kind") != opened["artifact_kind"]
            or value.get("mode") != opened["mode"]
            or not isinstance(value.get("outputs"), Mapping)
            or not isinstance(value.get("validation"), Mapping)):
        raise ArtifactLifecycleError("CLOSE receipt does not bind OPEN")
    _validate_live_reservation(opened)
    if opened["mode"] == "append_log":
        reservation = opened["reservation"]
        path = Path(reservation["output_path"])
        outputs = value["outputs"]
        if set(outputs) != {"output_path", "output_sha256", "byte_count"}:
            raise ArtifactLifecycleError("append CLOSE outputs malformed")
        output_sha256, observed = _file_sha256_and_stat(
            path,
            expected_identity=(reservation["device"], reservation["inode"]),
        )
        if (outputs["output_path"] != str(path)
                or outputs["output_sha256"] != output_sha256
                or outputs["byte_count"] != observed.st_size):
            raise ArtifactLifecycleError("append CLOSE output changed")
    else:
        expected = opened["reservation"]["expected_outputs"]
        if set(value["outputs"]) != set(expected):
            raise ArtifactLifecycleError("bundle CLOSE output set mismatch")
        for key, path_value in expected.items():
            output = value["outputs"][key]
            path = Path(path_value)
            output_sha256, observed = _file_sha256_and_stat(path)
            if (not isinstance(output, Mapping)
                    or set(output) != {"path", "sha256", "byte_count"}
                    or output["path"] != str(path)
                    or output["sha256"] != output_sha256
                    or output["byte_count"] != observed.st_size):
                raise ArtifactLifecycleError(f"bundle CLOSE output changed: {key}")
    return value


def authorization_code_root(code_sha256: Mapping[str, str]) -> str:
    """Canonical root used by OPEN receipts to bind the exact code set."""

    if not code_sha256:
        raise ArtifactLifecycleError("code hash mapping cannot be empty")
    for key, value in code_sha256.items():
        if not isinstance(key, str) or not key:
            raise ArtifactLifecycleError("code hash key must be non-empty")
        _sha(value, label=f"code_sha256.{key}")
    return sha256(canonical_json(dict(code_sha256)).encode("utf-8")).hexdigest()


def assert_authorization(
    receipt: Mapping[str, Any],
    *,
    stage: str,
    expected: Mapping[str, str],
) -> None:
    """Fail closed unless an OPEN receipt has the exact expected parents."""

    if receipt.get("stage") != stage:
        raise ArtifactLifecycleError("OPEN stage mismatch")
    observed = _validate_authorization(stage, receipt.get("authorization"))
    wanted = _validate_authorization(stage, expected)
    if observed != wanted:
        raise ArtifactLifecycleError("OPEN authorization parents mismatch")
