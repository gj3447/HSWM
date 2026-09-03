"""Thin, SDK-free S3 Object Lock claim boundary for one G0 occurrence.

The command is intentionally only an external adapter request.  It does not
execute AWS CLI, retry failures, trust a caller timestamp, or prove bucket
policy/readback/organizational independence.  A separately operated external
policy and readback verification are still required before a claim is usable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
import base64
import re
from typing import Any, Mapping


COMMAND_SCHEMA = "hswm-g0-occurrence-s3-worm-claim-command/v1"
RESULT_SCHEMA = "hswm-g0-occurrence-s3-worm-claim-result/v1"
CLAIM_BOUNDARY = (
    "S3 put-object plus version-pinned readback classification only; bucket policy, Object Lock "
    "configuration, conditional-write enforcement, external time, and "
    "claimant/admin organizational independence require separate verification"
)
_UID = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ACCOUNT = re.compile(r"[0-9]{12}\Z")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]\Z")


class WormClaimTerminal(StrEnum):
    CANDIDATE_CLAIMED = "CANDIDATE_CLAIMED"
    VOID_DUPLICATE = "VOID_DUPLICATE"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True, slots=True)
class S3WormClaimCommandV1:
    bucket: str
    key: str
    body_file: Path
    body_sha256: str
    checksum_sha256_base64: str
    retain_until: str
    claimant_account_id: str
    admin_account_id: str
    argv: tuple[str, ...]
    schema_version: str = COMMAND_SCHEMA


@dataclass(frozen=True, slots=True)
class S3WormClaimResultV1:
    terminal: WormClaimTerminal
    http_status: int
    reason: str
    version_id: str | None
    etag: str | None
    checksum_sha256: str | None
    object_lock_mode: str | None
    object_lock_retain_until: str | None
    retry_permitted: bool
    claim_boundary: str = CLAIM_BOUNDARY
    schema_version: str = RESULT_SCHEMA


@dataclass(frozen=True, slots=True)
class S3WormClaimReadbackCommandsV1:
    """Exact version-pinned readbacks required before a successful write is usable."""

    head_object_argv: tuple[str, ...]
    get_retention_argv: tuple[str, ...]


def build_s3_worm_claim_command(
    *,
    bucket: str,
    occurrence_uid: str,
    body_file: Path,
    expected_body_sha256: str,
    retain_until: str,
    claimant_account_id: str,
    admin_account_id: str,
    aws_cli: str = "aws",
) -> S3WormClaimCommandV1:
    """Build the only allowed CLI argv for a create-once claim object."""

    _require_bucket(bucket)
    _require_uid(occurrence_uid)
    _require_sha256(expected_body_sha256)
    _require_account(claimant_account_id, "claimant_account_id")
    _require_account(admin_account_id, "admin_account_id")
    if claimant_account_id == admin_account_id:
        raise ValueError("claimant and WORM admin accounts must be distinct")
    if not isinstance(aws_cli, str) or not aws_cli:
        raise ValueError("aws_cli must be a non-empty command")
    _utc_timestamp(retain_until, "retain_until", require_z=True)
    resolved = Path(body_file).resolve()
    if not resolved.is_file():
        raise ValueError("claim body_file must already exist as a regular file")
    observed = _file_sha256(resolved)
    if observed != expected_body_sha256:
        raise ValueError("claim body SHA-256 differs from expected descriptor")
    checksum = base64.b64encode(bytes.fromhex(expected_body_sha256)).decode("ascii")
    key = f"occurrences/{occurrence_uid}/claim.json"
    argv = (
        aws_cli,
        "s3api",
        "put-object",
        "--bucket",
        bucket,
        "--key",
        key,
        "--body",
        str(resolved),
        "--if-none-match",
        "*",
        "--checksum-algorithm",
        "SHA256",
        "--checksum-sha256",
        checksum,
        "--object-lock-mode",
        "COMPLIANCE",
        "--object-lock-retain-until-date",
        retain_until,
        "--expected-bucket-owner",
        admin_account_id,
        "--no-cli-pager",
    )
    return S3WormClaimCommandV1(
        bucket=bucket,
        key=key,
        body_file=resolved,
        body_sha256=expected_body_sha256,
        checksum_sha256_base64=checksum,
        retain_until=retain_until,
        claimant_account_id=claimant_account_id,
        admin_account_id=admin_account_id,
        argv=argv,
    )


def build_s3_worm_claim_readback_commands(
    command: S3WormClaimCommandV1,
    *,
    version_id: str,
    aws_cli: str = "aws",
) -> S3WormClaimReadbackCommandsV1:
    """Build read-only, version-specific commands after the single write attempt.

    ``put-object`` does not normally return Object Lock state.  A 200 response
    therefore cannot establish a candidate claim by itself.
    """
    if not isinstance(command, S3WormClaimCommandV1):
        raise TypeError("command must be S3WormClaimCommandV1")
    if not isinstance(version_id, str) or not version_id:
        raise ValueError("version_id must be a non-empty S3 version identifier")
    if (
        len(version_id) > 1024
        or version_id.startswith("-")
        or any(ord(character) < 0x20 or character.isspace() for character in version_id)
    ):
        raise ValueError("version_id must be a bounded non-option S3 version identifier")
    if not isinstance(aws_cli, str) or not aws_cli:
        raise ValueError("aws_cli must be a non-empty command")
    common = (
        "--bucket", command.bucket, "--key", command.key, "--version-id", version_id,
        "--expected-bucket-owner", command.admin_account_id, "--no-cli-pager",
    )
    return S3WormClaimReadbackCommandsV1(
        head_object_argv=(
            aws_cli, "s3api", "head-object", *common, "--checksum-mode", "ENABLED"
        ),
        get_retention_argv=(aws_cli, "s3api", "get-object-retention", *common),
    )


def classify_s3_worm_claim_result(
    command: S3WormClaimCommandV1,
    *,
    http_status: int,
    put_response_metadata: Mapping[str, Any] | None,
    head_object_metadata: Mapping[str, Any] | None = None,
    retention_metadata: Mapping[str, Any] | None = None,
) -> S3WormClaimResultV1:
    """Classify one externally executed request without retrying it.

    A 200 is only a *candidate* claim after separately supplied, version-pinned
    ``head-object`` and ``get-object-retention`` readbacks agree with the exact
    command.  409/412 are terminal duplicate VOID, and every other result
    remains inconclusive with retries forbidden.
    """

    if not isinstance(command, S3WormClaimCommandV1):
        raise TypeError("command must be S3WormClaimCommandV1")
    if type(http_status) is not int:
        raise TypeError("http_status must be int")
    put = put_response_metadata if isinstance(put_response_metadata, Mapping) else {}
    head = head_object_metadata if isinstance(head_object_metadata, Mapping) else {}
    retention = retention_metadata if isinstance(retention_metadata, Mapping) else {}
    if http_status in {409, 412}:
        return _result(
            WormClaimTerminal.VOID_DUPLICATE,
            http_status,
            "DUPLICATE_OR_PREEXISTING_OCCURRENCE_CLAIM",
            put,
        )
    if http_status != 200:
        return _result(
            WormClaimTerminal.INCONCLUSIVE,
            http_status,
            "S3_PUT_FAILED_NO_RETRY",
            put,
        )
    required = {
        "VersionId": _text(put.get("VersionId")),
        "PutETag": _text(put.get("ETag")),
        "PutChecksumSHA256": _text(put.get("ChecksumSHA256")),
        "HeadVersionId": _text(head.get("VersionId")),
        "ETag": _text(head.get("ETag")),
        "ChecksumSHA256": _text(head.get("ChecksumSHA256")),
        "ObjectLockMode": _nested_text(retention, "Retention", "Mode"),
        "ObjectLockRetainUntilDate": _nested_text(retention, "Retention", "RetainUntilDate"),
    }
    if (
        not all(required.values())
        or required["HeadVersionId"] != required["VersionId"]
        or required["ETag"] != required["PutETag"]
        or required["PutChecksumSHA256"] != command.checksum_sha256_base64
        or required["ChecksumSHA256"] != command.checksum_sha256_base64
        or required["ObjectLockMode"] != "COMPLIANCE"
        or not _same_utc_timestamp(
            required["ObjectLockRetainUntilDate"], command.retain_until
        )
    ):
        return _result(
            WormClaimTerminal.INCONCLUSIVE,
            http_status,
            "S3_SUCCESS_RESPONSE_MISSING_OR_MISMATCHED_WORM_FIELDS_NO_RETRY",
            put,
        )
    return _result(
        WormClaimTerminal.CANDIDATE_CLAIMED,
        http_status,
        "CANDIDATE_CLAIM_REQUIRES_EXTERNAL_POLICY_AND_READBACK_VERIFICATION",
        {**put, **head, "ObjectLockMode": required["ObjectLockMode"],
         "ObjectLockRetainUntilDate": required["ObjectLockRetainUntilDate"]},
    )


def _result(
    terminal: WormClaimTerminal,
    http_status: int,
    reason: str,
    metadata: Mapping[str, Any],
) -> S3WormClaimResultV1:
    return S3WormClaimResultV1(
        terminal=terminal,
        http_status=http_status,
        reason=reason,
        version_id=_text(metadata.get("VersionId")),
        etag=_text(metadata.get("ETag")),
        checksum_sha256=_text(metadata.get("ChecksumSHA256")),
        object_lock_mode=_text(metadata.get("ObjectLockMode")),
        object_lock_retain_until=_text(metadata.get("ObjectLockRetainUntilDate")),
        retry_permitted=False,
    )


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and bool(value) else None


def _nested_text(value: Mapping[str, Any], *keys: str) -> str | None:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return _text(current)


def _utc_timestamp(value: Any, name: str, *, require_z: bool = False) -> datetime:
    if not isinstance(value, str) or not value or (require_z and not value.endswith("Z")):
        raise ValueError(f"{name} must be an explicit UTC RFC3339 timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{name} must be an explicit UTC RFC3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError(f"{name} must be an explicit UTC RFC3339 timestamp")
    return parsed.astimezone(timezone.utc)


def _same_utc_timestamp(left: Any, right: Any) -> bool:
    try:
        return _utc_timestamp(left, "readback retention") == _utc_timestamp(
            right, "command retention"
        )
    except ValueError:
        return False


def _require_uid(value: str) -> None:
    if not isinstance(value, str) or _UID.fullmatch(value) is None:
        raise ValueError("occurrence_uid must be a bounded stable identifier")


def _require_sha256(value: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError("expected_body_sha256 must be lowercase SHA-256")


def _require_account(value: str, name: str) -> None:
    if not isinstance(value, str) or _ACCOUNT.fullmatch(value) is None:
        raise ValueError(f"{name} must be a 12-digit AWS account ID")


def _require_bucket(value: str) -> None:
    if not isinstance(value, str) or _BUCKET.fullmatch(value) is None:
        raise ValueError("bucket must be a DNS-compatible S3 bucket name")


__all__ = [
    "CLAIM_BOUNDARY",
    "COMMAND_SCHEMA",
    "RESULT_SCHEMA",
    "S3WormClaimCommandV1",
    "S3WormClaimReadbackCommandsV1",
    "S3WormClaimResultV1",
    "WormClaimTerminal",
    "build_s3_worm_claim_command",
    "build_s3_worm_claim_readback_commands",
    "classify_s3_worm_claim_result",
]
