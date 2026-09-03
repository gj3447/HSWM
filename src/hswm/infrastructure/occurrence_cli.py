"""Local, non-promoting CLI for the G0 external-occurrence boundary.

The commands in this module only inspect local bytes, construct deterministic
standard-format preparation records, and report readiness.  They never register an OSF
record, sign an envelope, contact Rekor or a TSA, claim a WORM object, start a
Temporal workflow, fetch a drand pulse, evaluate an episode, or publish data.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from hswm.infrastructure.occurrence_attestation import (
    DsseEnvelopeV1,
    InTotoStatementV1,
    cosign_attest_blob_argv,
    rfc3161_query_argv,
    rfc3161_verify_query_argv,
)
from hswm.infrastructure.occurrence_integrity import ContentDescriptorV1
from hswm.infrastructure.occurrence_preflight import (
    READY_STATUS,
    run_occurrence_preflight,
)
from hswm.infrastructure.occurrence_registration import (
    ContentDescriptor as RegistrationContentDescriptor,
    parse_osf_registration_readback,
)
from hswm.infrastructure.occurrence_worm import (
    CLAIM_BOUNDARY as WORM_CLAIM_BOUNDARY,
    build_s3_worm_claim_command,
)
from hswm.infrastructure.occurrence_workflow import (
    CLAIM_BOUNDARY as WORKFLOW_CLAIM_BOUNDARY,
    temporal_one_shot_launch_options,
)


MAX_LOCAL_INPUT_BYTES = 16 * 1024 * 1024
CLI_SCHEMA = "hswm-g0-occurrence-local-cli/v1"
CLI_CLAIM_BOUNDARY = (
    "local deterministic preparation and inspection only; not external "
    "registration, signature verification, execution, publication, outcome "
    "truth, Permit, causal credit, canonical admission, learning, or G0 evidence"
)


class OccurrenceCliError(ValueError):
    """Unsafe path, oversized input, or malformed command input."""


def _read_bytes(path: Path, label: str) -> bytes:
    if not isinstance(path, Path):
        raise OccurrenceCliError(f"{label} path is required")
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise OccurrenceCliError(f"{label} must be a regular file")
        size = resolved.stat().st_size
        if size > MAX_LOCAL_INPUT_BYTES:
            raise OccurrenceCliError(
                f"{label} exceeds the {MAX_LOCAL_INPUT_BYTES}-byte local limit"
            )
        return resolved.read_bytes()
    except OSError as exc:
        raise OccurrenceCliError(f"cannot read {label}: {path}") from exc


def _read_json(path: Path, label: str) -> Any:
    raw = _read_bytes(path, label)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OccurrenceCliError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject_nonfinite(value: str) -> None:
        raise OccurrenceCliError(
            f"{label} contains non-finite JSON number {value}"
        )

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise OccurrenceCliError(f"{label} must be strict UTF-8 JSON") from exc


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        raise OccurrenceCliError(f"{label} must be a JSON object")
    return value


def _descriptor(path: Path, media_type: str) -> ContentDescriptorV1:
    raw = _read_bytes(path, "subject")
    return ContentDescriptorV1(
        media_type=media_type,
        sha256=sha256(raw).hexdigest(),
        byte_length=len(raw),
    )


def _registration_descriptor(path: Path, registered_path: str) -> RegistrationContentDescriptor:
    raw = _read_bytes(path, "registration package")
    return RegistrationContentDescriptor(
        path=registered_path,
        sha256=sha256(raw).hexdigest(),
        bytes=len(raw),
    )


def _emit(value: Any) -> None:
    print(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hswm-g0-occurrence",
        description="Prepare and inspect the fail-closed G0 occurrence boundary.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "preflight", help="check local tools and presence-only external bindings"
    )

    describe = subparsers.add_parser(
        "describe", help="compute a content descriptor for one local file"
    )
    describe.add_argument("path", type=Path)
    describe.add_argument("--media-type", required=True)

    workflow = subparsers.add_parser(
        "workflow-options", help="emit exact one-shot Temporal adapter options"
    )
    workflow.add_argument("occurrence_uid")

    statement = subparsers.add_parser(
        "statement", help="construct an in-toto Statement v1 for local subject bytes"
    )
    statement.add_argument("--subject", required=True, type=Path)
    statement.add_argument("--subject-name", required=True)
    statement.add_argument("--media-type", required=True)
    statement.add_argument("--predicate-type", required=True)
    statement.add_argument("--predicate", required=True, type=Path)

    envelope = subparsers.add_parser(
        "parse-dsse", help="shape-check a DSSE envelope without claiming verification"
    )
    envelope.add_argument("path", type=Path)

    osf = subparsers.add_parser(
        "osf-readback", help="validate supplied OSF API v2 and package readbacks"
    )
    osf.add_argument("--registration", required=True, type=Path)
    osf.add_argument("--file-metadata", required=True, type=Path)
    osf.add_argument("--expected-package", required=True, type=Path)
    osf.add_argument("--read-back-package", required=True, type=Path)
    osf.add_argument(
        "--read-back-download-url", required=True,
        help="exact canonical OSF links.download URL used to obtain --read-back-package",
    )
    osf.add_argument("--registered-path", required=True)
    osf.add_argument("--pulse-timestamp", required=True)

    worm = subparsers.add_parser(
        "worm-command", help="emit but do not run one S3 Object Lock claim argv"
    )
    worm.add_argument("--bucket", required=True)
    worm.add_argument("--occurrence-uid", required=True)
    worm.add_argument("--body", required=True, type=Path)
    worm.add_argument("--retain-until", required=True)
    worm.add_argument("--claimant-account-id", required=True)
    worm.add_argument("--admin-account-id", required=True)
    worm.add_argument("--aws-cli", default="aws")

    attest = subparsers.add_parser(
        "cosign-attest-command", help="emit but do not run a Cosign attest-blob argv"
    )
    attest.add_argument("--blob", required=True, type=Path)
    attest.add_argument("--statement", required=True, type=Path)
    attest.add_argument("--bundle", required=True, type=Path)
    attest.add_argument("--cosign", default="cosign")

    timestamp_query = subparsers.add_parser(
        "rfc3161-query-command", help="emit but do not run a nonce-bearing TSA query argv"
    )
    timestamp_query.add_argument("--blob", required=True, type=Path)
    timestamp_query.add_argument("--request", required=True, type=Path)
    timestamp_query.add_argument("--openssl", default="openssl")

    timestamp_verify = subparsers.add_parser(
        "rfc3161-verify-command", help="emit but do not run a nonce-bound TSA verify argv"
    )
    timestamp_verify.add_argument("--request", required=True, type=Path)
    timestamp_verify.add_argument("--response", required=True, type=Path)
    timestamp_verify.add_argument("--ca-file", required=True, type=Path)
    timestamp_verify.add_argument("--untrusted", type=Path)
    timestamp_verify.add_argument("--openssl", default="openssl")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            report = run_occurrence_preflight()
            _emit(asdict(report))
            return 0 if report.status == READY_STATUS else 3

        if args.command == "describe":
            _emit(_descriptor(args.path, args.media_type).canonical())
            return 0

        if args.command == "workflow-options":
            options = temporal_one_shot_launch_options(args.occurrence_uid)
            _emit(
                {
                    "claim_boundary": WORKFLOW_CLAIM_BOUNDARY,
                    **options.as_external_adapter_options(),
                }
            )
            return 0

        if args.command == "statement":
            predicate = _object(_read_json(args.predicate, "predicate"), "predicate")
            statement = InTotoStatementV1(
                subject=_descriptor(args.subject, args.media_type),
                subject_name=args.subject_name,
                predicate_type=args.predicate_type,
                predicate=predicate,
            )
            _emit(statement.canonical())
            return 0

        if args.command == "parse-dsse":
            envelope = DsseEnvelopeV1.from_bytes(
                _read_bytes(args.path, "DSSE envelope")
            )
            statement = envelope.statement
            _emit(
                {
                    "claim_boundary": CLI_CLAIM_BOUNDARY,
                    "cryptographically_verified": envelope.cryptographically_verified,
                    "payload_sha256": envelope.payload_sha256,
                    "predicate_type": statement.predicate_type,
                    "schema_version": CLI_SCHEMA,
                    "signature_count": len(envelope.signatures),
                    "signature_keyids": [keyid for keyid, _ in envelope.signatures],
                    "subject_name": statement.subject_name,
                    "subject_sha256": statement.subject.sha256,
                }
            )
            return 0

        if args.command == "osf-readback":
            expected = _registration_descriptor(
                args.expected_package, args.registered_path
            )
            read_back = _registration_descriptor(
                args.read_back_package, args.registered_path
            )
            result = parse_osf_registration_readback(
                _object(
                    _read_json(args.registration, "OSF registration readback"),
                    "OSF registration readback",
                ),
                _object(
                    _read_json(args.file_metadata, "OSF file readback"),
                    "OSF file readback",
                ),
                expected_package=expected,
                read_back_bytes=read_back,
                read_back_download_url=args.read_back_download_url,
                pulse_timestamp=args.pulse_timestamp,
            )
            _emit(asdict(result))
            return 0 if result.status == "CANDIDATE_FOR_EXTERNAL_AUDIT" else 4

        if args.command == "worm-command":
            body = _read_bytes(args.body, "WORM claim body")
            command = build_s3_worm_claim_command(
                bucket=args.bucket,
                occurrence_uid=args.occurrence_uid,
                body_file=args.body,
                expected_body_sha256=sha256(body).hexdigest(),
                retain_until=args.retain_until,
                claimant_account_id=args.claimant_account_id,
                admin_account_id=args.admin_account_id,
                aws_cli=args.aws_cli,
            )
            _emit(
                {
                    "argv": list(command.argv),
                    "body_sha256": command.body_sha256,
                    "claim_boundary": WORM_CLAIM_BOUNDARY,
                    "execution": "NOT_EXECUTED",
                    "key": command.key,
                    "schema_version": command.schema_version,
                }
            )
            return 0

        if args.command == "cosign-attest-command":
            _emit(
                {
                    "argv": list(
                        cosign_attest_blob_argv(
                            cosign=args.cosign, blob=args.blob,
                            statement=args.statement, bundle=args.bundle,
                        )
                    ),
                    "claim_boundary": CLI_CLAIM_BOUNDARY,
                    "execution": "NOT_EXECUTED",
                    "schema_version": CLI_SCHEMA,
                }
            )
            return 0

        if args.command == "rfc3161-query-command":
            _emit(
                {
                    "argv": list(
                        rfc3161_query_argv(
                            openssl=args.openssl, blob=args.blob, request=args.request
                        )
                    ),
                    "claim_boundary": CLI_CLAIM_BOUNDARY,
                    "execution": "NOT_EXECUTED",
                    "schema_version": CLI_SCHEMA,
                }
            )
            return 0

        if args.command == "rfc3161-verify-command":
            _emit(
                {
                    "argv": list(
                        rfc3161_verify_query_argv(
                            openssl=args.openssl, request=args.request,
                            response=args.response, ca_file=args.ca_file,
                            untrusted=args.untrusted,
                        )
                    ),
                    "claim_boundary": CLI_CLAIM_BOUNDARY,
                    "execution": "NOT_EXECUTED",
                    "schema_version": CLI_SCHEMA,
                }
            )
            return 0
    except (OSError, TypeError, ValueError) as exc:
        parser.exit(2, f"{parser.prog}: error: {exc}\n")
    raise AssertionError("argparse accepted an unknown occurrence command")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "CLI_CLAIM_BOUNDARY",
    "CLI_SCHEMA",
    "MAX_LOCAL_INPUT_BYTES",
    "OccurrenceCliError",
    "main",
]
