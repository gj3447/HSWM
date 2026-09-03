"""HSWM strict-profile parsing and local wrappers for occurrence attestations.

These functions prepare standard-format evidence for an independently operated
auditor.  They neither sign nor fetch data, and parsing an envelope is never a
claim that its signature, certificate, transparency inclusion, or timestamp is
valid.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from hswm.experiments import swm0w_beacon as beacon
from hswm.infrastructure.occurrence_integrity import ContentDescriptorV1, OccurrenceIntegrityError


INTOTO_STATEMENT_V1 = "https://in-toto.io/Statement/v1"
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
HSWM_STRICT_ATTESTATION_PROFILE_V1 = (
    "hswm-occurrence-strict-attestation-profile/v1: exactly one in-toto "
    "Statement/v1 subject with a SHA-256 digest, exact envelope members, "
    "standard base64, and non-empty keyed signatures"
)
COSIGN_VERSION = "3.1.3"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class OccurrenceAttestationError(OccurrenceIntegrityError):
    """Malformed HSWM strict-profile material or unsafe verifier request.

    This adapter deliberately does not parse every valid DSSE or in-toto
    document. General conformance remains with the upstream standards and
    their suites; this profile only accepts the frozen HSWM package shape.
    """


def _exact(value: Any, keys: set[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise OccurrenceAttestationError(
            f"{name} keys do not match {HSWM_STRICT_ATTESTATION_PROFILE_V1}"
        )
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise OccurrenceAttestationError(f"{name} must be a bounded non-empty string")
    return value


def _strict_json_bytes(raw: bytes, name: str) -> Any:
    if not isinstance(raw, bytes):
        raise OccurrenceAttestationError(f"{name} bytes are required")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise OccurrenceAttestationError(
                    f"{name} contains duplicate key {key!r}"
                )
            result[key] = value
        return result

    def reject_nonfinite(value: str) -> None:
        raise OccurrenceAttestationError(
            f"{name} contains non-finite JSON number {value}"
        )

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise OccurrenceAttestationError(f"{name} is not strict UTF-8 JSON") from exc


@dataclass(frozen=True, slots=True)
class InTotoStatementV1:
    """One-subject SHA-256 subset of in-toto Statement v1 for HSWM occurrences."""
    subject: ContentDescriptorV1
    subject_name: str
    predicate_type: str
    predicate: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.subject, ContentDescriptorV1):
            raise OccurrenceAttestationError("statement subject must be a content descriptor")
        _text(self.subject_name, "subject_name")
        _text(self.predicate_type, "predicate_type")
        if not isinstance(self.predicate, Mapping):
            raise OccurrenceAttestationError("predicate must be an object")
        # Round-trip through the checkout's strict JSON encoder before signing.
        beacon.canonical_json(self.predicate)

    def canonical(self) -> dict[str, Any]:
        return {
            "_type": INTOTO_STATEMENT_V1,
            "predicate": dict(self.predicate),
            "predicateType": self.predicate_type,
            "subject": [{"digest": {"sha256": self.subject.sha256}, "name": self.subject_name}],
        }

    def bytes(self) -> bytes:
        return beacon.canonical_json(self.canonical()).encode("utf-8")

    @classmethod
    def from_bytes(cls, raw: bytes) -> "InTotoStatementV1":
        value = _strict_json_bytes(raw, "in-toto statement")
        item = _exact(value, {"_type", "subject", "predicateType", "predicate"}, "in-toto statement")
        if item["_type"] != INTOTO_STATEMENT_V1:
            raise OccurrenceAttestationError("HSWM strict profile requires in-toto Statement v1")
        if type(item["subject"]) is not list or len(item["subject"]) != 1:
            raise OccurrenceAttestationError("HSWM strict profile requires exactly one statement subject")
        subject = _exact(item["subject"][0], {"name", "digest"}, "statement subject")
        digest = _exact(subject["digest"], {"sha256"}, "statement subject digest")
        descriptor = ContentDescriptorV1(media_type="application/octet-stream", sha256=digest["sha256"], byte_length=0)
        # in-toto subject has no standardized byte length.  The adapter binds
        # the mandated SHA-256; callers pair it with a full local descriptor.
        return cls(subject=descriptor, subject_name=_text(subject["name"], "subject name"),
                   predicate_type=_text(item["predicateType"], "predicateType"), predicate=item["predicate"])


@dataclass(frozen=True, slots=True)
class DsseEnvelopeV1:
    """Strict HSWM DSSE subset; parsing it never verifies a signature."""
    payload: bytes
    signatures: tuple[tuple[str, bytes], ...]

    @property
    def statement(self) -> InTotoStatementV1:
        return InTotoStatementV1.from_bytes(self.payload)

    @property
    def payload_sha256(self) -> str:
        return sha256(self.payload).hexdigest()

    @property
    def cryptographically_verified(self) -> bool:
        """Always false: parsing is intentionally not signature verification."""
        return False

    @classmethod
    def from_mapping(cls, value: Any) -> "DsseEnvelopeV1":
        item = _exact(value, {"payloadType", "payload", "signatures"}, "DSSE envelope")
        if item["payloadType"] != DSSE_PAYLOAD_TYPE:
            raise OccurrenceAttestationError(
                "HSWM strict DSSE profile requires payloadType application/vnd.in-toto+json"
            )
        if not isinstance(item["payload"], str):
            raise OccurrenceAttestationError("HSWM strict DSSE profile payload must be standard base64 text")
        try:
            payload = base64.b64decode(item["payload"], validate=True)
        except (ValueError, TypeError) as exc:
            raise OccurrenceAttestationError("HSWM strict DSSE profile payload is invalid standard base64") from exc
        if type(item["signatures"]) is not list or not item["signatures"]:
            raise OccurrenceAttestationError("HSWM strict DSSE profile signatures must be a non-empty array")
        signatures: list[tuple[str, bytes]] = []
        for index, raw_signature in enumerate(item["signatures"]):
            sig = _exact(raw_signature, {"keyid", "sig"}, f"DSSE signature {index}")
            keyid = _text(sig["keyid"], "DSSE keyid")
            if not isinstance(sig["sig"], str):
                raise OccurrenceAttestationError("HSWM strict DSSE profile signature must be standard base64 text")
            try:
                decoded = base64.b64decode(sig["sig"], validate=True)
            except (ValueError, TypeError) as exc:
                raise OccurrenceAttestationError(
                    "HSWM strict DSSE profile signature is invalid standard base64"
                ) from exc
            if not decoded:
                raise OccurrenceAttestationError("DSSE signature must not be empty")
            signatures.append((keyid, decoded))
        if len({keyid for keyid, _ in signatures}) != len(signatures):
            raise OccurrenceAttestationError("DSSE signature keyids must be unique")
        envelope = cls(payload=payload, signatures=tuple(signatures))
        envelope.statement  # reject a non-in-toto JSON payload now
        return envelope

    @classmethod
    def from_bytes(cls, raw: bytes) -> "DsseEnvelopeV1":
        """Parse strict JSON bytes before applying the frozen DSSE profile."""

        return cls.from_mapping(_strict_json_bytes(raw, "DSSE envelope"))


def cosign_verify_blob_argv(
    *,
    cosign: str,
    blob: Path,
    bundle: Path,
    trusted_root: Path,
    identity: str,
    issuer: str,
) -> tuple[str, ...]:
    """Build bundle/tlog verification with an explicit pinned trust root."""
    return (
        _text(cosign, "cosign executable"), "verify-blob", "--bundle", str(_file(bundle, "bundle")),
        "--trusted-root", str(_file(trusted_root, "Sigstore trusted root")),
        "--certificate-identity", _text(identity, "certificate identity"),
        "--certificate-oidc-issuer", _text(issuer, "certificate issuer"), str(_file(blob, "blob")),
    )


def cosign_attest_blob_argv(*, cosign: str, blob: Path, statement: Path, bundle: Path) -> tuple[str, ...]:
    """Build Cosign 3.1.3 attestation argv using ambient short-lived identity.

    The deliberately narrow signature has no token, password, key, or secret
    argument.  Keyless OIDC or a configured KMS identity is resolved by Cosign
    outside this adapter.
    """
    return (
        _text(cosign, "cosign executable"), "attest-blob", "--statement", str(_file(statement, "statement")),
        "--bundle", str(_new_output_file(bundle, "bundle")), "--yes", str(_file(blob, "blob")),
    )


def cosign_verify_blob_attestation_argv(
    *,
    cosign: str,
    bundle: Path,
    statement_output: Path,
    trusted_root: Path,
    identity: str,
    issuer: str,
) -> tuple[str, ...]:
    """Build Cosign statement-only verification argv with a new output file.

    ``--statement-only`` verifies the attestation in the bundle and deliberately
    has no positional artifact blob. Artifact binding is a distinct operation;
    use :func:`cosign_verify_blob_attestation_artifact_argv` for that form.
    """
    return (
        _text(cosign, "cosign executable"), "verify-blob-attestation", "--statement-only",
        "--bundle", str(_file(bundle, "bundle")),
        "--trusted-root", str(_file(trusted_root, "Sigstore trusted root")),
        "--certificate-identity", _text(identity, "certificate identity"),
        "--certificate-oidc-issuer", _text(issuer, "certificate issuer"),
        "--output-file", str(_new_output_file(statement_output, "verified statement output")),
    )


def cosign_verify_blob_attestation_artifact_argv(
    *,
    cosign: str,
    blob: Path,
    bundle: Path,
    trusted_root: Path,
    identity: str,
    issuer: str,
) -> tuple[str, ...]:
    """Build artifact-bound Cosign attestation verification without statement-only."""
    return (
        _text(cosign, "cosign executable"), "verify-blob-attestation",
        "--bundle", str(_file(bundle, "bundle")),
        "--trusted-root", str(_file(trusted_root, "Sigstore trusted root")),
        "--certificate-identity", _text(identity, "certificate identity"),
        "--certificate-oidc-issuer", _text(issuer, "certificate issuer"),
        str(_file(blob, "blob")),
    )


def rfc3161_verify_argv(
    *,
    openssl: str,
    blob: Path,
    response: Path,
    ca_file: Path,
    untrusted: Path | None = None,
) -> tuple[str, ...]:
    """Build data-imprint verification for a trusted historical response.

    A live occurrence should use :func:`rfc3161_verify_query_argv`, which also
    binds the nonce from the original request.
    """
    argv: list[str] = [_text(openssl, "openssl executable"), "ts", "-verify", "-data", str(_file(blob, "blob")),
                       "-in", str(_file(response, "RFC3161 response")), "-CAfile", str(_file(ca_file, "CA file"))]
    if untrusted is not None:
        argv.extend(("-untrusted", str(_file(untrusted, "untrusted chain"))))
    return tuple(argv)


def rfc3161_query_argv(
    *, openssl: str, blob: Path, request: Path
) -> tuple[str, ...]:
    """Build a nonce-bearing SHA-256 RFC3161 request without executing it."""
    return (
        _text(openssl, "openssl executable"), "ts", "-query", "-data",
        str(_file(blob, "blob")), "-sha256", "-cert", "-out",
        str(_new_output_file(request, "RFC3161 request")),
    )


def rfc3161_submit_argv(
    *, curl: str, request: Path, response: Path, tsa_url: str,
    allow_network: bool = False,
) -> tuple[str, ...]:
    """Build a credential-free TSA POST; network use is explicitly opt-in."""
    if allow_network is not True:
        raise OccurrenceAttestationError(
            "RFC3161 submission requires explicit allow_network=True"
        )
    parsed = urlparse(_text(tsa_url, "TSA URL"))
    if (
        parsed.scheme != "https" or not parsed.hostname
        or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment
    ):
        raise OccurrenceAttestationError(
            "TSA URL must be credential-free HTTPS without query or fragment"
        )
    request_file = _file(request, "RFC3161 request")
    response_file = _new_output_file(response, "RFC3161 response")
    return (
        _text(curl, "curl executable"), "--fail-with-body", "--silent",
        "--show-error", "--request", "POST", "--header",
        "Content-Type: application/timestamp-query", "--header",
        "Accept: application/timestamp-reply", "--data-binary",
        f"@{request_file}", "--output", str(response_file), tsa_url,
    )


def rfc3161_verify_query_argv(
    *, openssl: str, request: Path, response: Path, ca_file: Path,
    untrusted: Path | None = None,
) -> tuple[str, ...]:
    """Build verification against the original request, including its nonce."""
    argv: list[str] = [
        _text(openssl, "openssl executable"), "ts", "-verify", "-queryfile",
        str(_file(request, "RFC3161 request")), "-in",
        str(_file(response, "RFC3161 response")), "-CAfile",
        str(_file(ca_file, "CA file")),
    ]
    if untrusted is not None:
        argv.extend(("-untrusted", str(_file(untrusted, "untrusted chain"))))
    return tuple(argv)


def _file(path: Path, name: str) -> Path:
    if not isinstance(path, Path) or not path.is_file():
        raise OccurrenceAttestationError(f"{name} must be an existing regular file")
    return path.resolve()


def _new_output_file(path: Path, name: str) -> Path:
    """Resolve an attestation output without permitting an implicit overwrite."""
    if not isinstance(path, Path):
        raise OccurrenceAttestationError(f"{name} must be a filesystem path")
    resolved = path.resolve()
    if not resolved.parent.is_dir():
        raise OccurrenceAttestationError(f"{name} parent directory must already exist")
    if resolved.exists():
        raise OccurrenceAttestationError(f"{name} output must not already exist")
    return resolved


@dataclass(frozen=True, slots=True)
class LocalVerificationResultV1:
    argv: tuple[str, ...]
    ran: bool
    verified: bool
    stdout_sha256: str | None
    stderr_sha256: str | None


def verify_with_pinned_binary(
    *,
    argv: Sequence[str],
    executable: Path,
    executable_sha256: str,
    expected_version_text: str,
    pinned_inputs: Mapping[Path, str] | None = None,
    timeout_seconds: float = 30.0,
) -> LocalVerificationResultV1:
    """Run direct argv only after executable, version, and input-byte pins.

    A nonzero exit is a non-verification result, not an exception disguised as
    success.  Every declared input is held open and substituted with its
    ``/proc/self/fd`` path, closing path-swap races between hashing and verifier
    execution.  The caller must preserve the returned outputs separately.
    """
    executable = _file(executable, "verifier executable")
    if not isinstance(executable_sha256, str) or not _SHA256.fullmatch(executable_sha256):
        raise OccurrenceAttestationError("executable_sha256 must be lowercase SHA-256")
    if not isinstance(expected_version_text, str) or not expected_version_text:
        raise OccurrenceAttestationError("expected version text is required")
    selected = tuple(argv)
    if not selected or selected[0] != str(executable):
        raise OccurrenceAttestationError("argv must begin with the pinned executable")
    if any(not isinstance(argument, str) or "\x00" in argument for argument in selected):
        raise OccurrenceAttestationError("argv contains an invalid argument")
    if pinned_inputs is not None and not isinstance(pinned_inputs, Mapping):
        raise OccurrenceAttestationError("pinned_inputs must be a path/digest mapping")
    try:
        descriptor = os.open(executable, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        raise OccurrenceAttestationError("cannot open pinned verifier executable") from exc
    input_descriptors: list[int] = []
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OccurrenceAttestationError("verifier executable is not a regular file")
        digest = sha256()
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != executable_sha256:
            raise OccurrenceAttestationError("verifier executable SHA-256 mismatch")
        os.lseek(descriptor, 0, os.SEEK_SET)
        fd_executable = f"/proc/self/fd/{descriptor}"
        if not Path(fd_executable).exists():
            raise OccurrenceAttestationError(
                "immutable descriptor execution requires Linux /proc/self/fd"
            )
        replacements: dict[str, str] = {}
        for input_path, expected_sha256 in (pinned_inputs or {}).items():
            if not isinstance(input_path, Path):
                raise OccurrenceAttestationError(
                    "pinned input keys must be filesystem paths"
                )
            _digest_text = expected_sha256
            if not isinstance(_digest_text, str) or not _SHA256.fullmatch(
                _digest_text
            ):
                raise OccurrenceAttestationError(
                    "pinned input digest must be lowercase SHA-256"
                )
            resolved_input = _file(input_path, "pinned verifier input")
            resolved_text = str(resolved_input)
            if resolved_text in replacements:
                raise OccurrenceAttestationError("pinned verifier inputs must be unique")
            input_descriptor = os.open(
                resolved_input, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            )
            input_descriptors.append(input_descriptor)
            if not stat.S_ISREG(os.fstat(input_descriptor).st_mode):
                raise OccurrenceAttestationError(
                    "pinned verifier input is not a regular file"
                )
            input_digest = sha256()
            with os.fdopen(input_descriptor, "rb", closefd=False) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    input_digest.update(chunk)
            if input_digest.hexdigest() != _digest_text:
                raise OccurrenceAttestationError("pinned verifier input SHA-256 mismatch")
            os.lseek(input_descriptor, 0, os.SEEK_SET)
            fd_input = f"/proc/self/fd/{input_descriptor}"
            if not Path(fd_input).exists():
                raise OccurrenceAttestationError(
                    "immutable input execution requires Linux /proc/self/fd"
                )
            replacements[resolved_text] = fd_input
        selected_for_execution = tuple(
            replacements.get(argument, argument) for argument in selected
        )
        if any(path not in selected for path in replacements):
            raise OccurrenceAttestationError(
                "every pinned input must occur exactly in verifier argv"
            )
        run_options = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "timeout": timeout_seconds,
            "check": False,
            "executable": fd_executable,
            "pass_fds": (descriptor, *input_descriptors),
        }
        version = subprocess.run(
            (str(executable), "version"), text=True, **run_options
        )
        version_text = version.stdout + version.stderr
        if version.returncode != 0 or version_text != expected_version_text:
            raise OccurrenceAttestationError("verifier version text mismatch")
        os.lseek(descriptor, 0, os.SEEK_SET)
        completed = subprocess.run(selected_for_execution, **run_options)
    finally:
        for input_descriptor in input_descriptors:
            os.close(input_descriptor)
        os.close(descriptor)
    return LocalVerificationResultV1(argv=selected, ran=True, verified=completed.returncode == 0,
                                     stdout_sha256=sha256(completed.stdout).hexdigest(),
                                     stderr_sha256=sha256(completed.stderr).hexdigest())
