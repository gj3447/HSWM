"""Read-only OSF registration evidence boundary for prospective occurrences.

This module neither creates nor changes an OSF registration.  It parses a
caller-supplied official OSF API v2 readback and independently supplied file
byte descriptor.  Its best possible result is a candidate for external audit;
it is never preregistration success, G0 evidence, or an HSWM admission path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urlparse


CLAIM_BOUNDARY = (
    "read-only external-registration evidence boundary; not preregistration "
    "success, G0 evidence, HSWM canonical state, Permit, outcome authority, "
    "or causal-credit path"
)
OSF_API_VERSION = "v2"
AUDIT_CANDIDATE = "CANDIDATE_FOR_EXTERNAL_AUDIT"
BLOCKED = "BLOCKED"
VOID = "VOID"
_OSF_ID = re.compile(r"^[a-z0-9]{5}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CANONICAL_HOSTS = frozenset({"osf.io", "api.osf.io", "files.osf.io"})


class OccurrenceRegistrationError(ValueError):
    """Raised when supplied OSF readback material is malformed or unsafe."""


@dataclass(frozen=True, slots=True)
class ContentDescriptor:
    """A named byte sequence described without carrying its contents."""

    path: str
    sha256: str
    bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path or self.path.strip() != self.path:
            raise OccurrenceRegistrationError("descriptor.path must be a non-empty trimmed string")
        if not isinstance(self.sha256, str) or not _SHA256.fullmatch(self.sha256):
            raise OccurrenceRegistrationError("descriptor.sha256 must be lowercase SHA-256")
        if isinstance(self.bytes, bool) or not isinstance(self.bytes, int) or self.bytes < 0:
            raise OccurrenceRegistrationError("descriptor.bytes must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class OSFRegistrationReadback:
    status: str
    claim_boundary: str
    registration_id: str
    registration_url: str
    file_metadata_url: str
    file_download_url: str
    read_back_download_url: str
    registration_timestamp: str
    pulse_timestamp: str
    withdrawn: bool
    expected_package: ContentDescriptor
    api_file: ContentDescriptor
    read_back_bytes: ContentDescriptor
    reason: str | None


def _timestamp(value: object, name: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value:
        raise OccurrenceRegistrationError(f"{name} must be an RFC 3339 timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise OccurrenceRegistrationError(f"{name} must be an RFC 3339 timestamp") from error
    if parsed.tzinfo is None:
        raise OccurrenceRegistrationError(f"{name} must include a UTC offset")
    return value, parsed.astimezone(timezone.utc)


def _url(value: object, *, kind: str, registration_id: str | None = None) -> str:
    if not isinstance(value, str):
        raise OccurrenceRegistrationError(f"{kind}_url must be an HTTPS OSF URL")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _CANONICAL_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise OccurrenceRegistrationError(f"{kind}_url must be an HTTPS canonical OSF URL")
    path = parsed.path
    if kind == "registration":
        api_match = re.fullmatch(r"/v2/registrations/([a-z0-9]{5})/", path)
        html_match = re.fullmatch(r"/([a-z0-9]{5})/", path)
        identifier = (api_match or html_match)
        if identifier is None or (registration_id is not None and identifier.group(1) != registration_id):
            raise OccurrenceRegistrationError("registration_url does not bind the registration identifier")
    elif kind == "file_metadata":
        if parsed.hostname != "api.osf.io" or not re.fullmatch(
            r"/v2/files/[A-Za-z0-9_-]+/", path
        ):
            raise OccurrenceRegistrationError("file_metadata_url must be an official OSF API v2 file URL")
    elif kind == "file_download":
        # OSF API v2 exposes file bytes through its WaterButler service.  This
        # shape follows the official API example rather than guessing an OSF
        # web-page download route.
        if parsed.hostname != "files.osf.io" or not re.fullmatch(
            r"/v1/resources/[A-Za-z0-9_-]+/providers/[A-Za-z0-9._-]+/[A-Za-z0-9._~-]+",
            path,
        ):
            raise OccurrenceRegistrationError(
                "file_download_url must be an official OSF WaterButler download URL"
            )
    else:
        raise AssertionError(f"unknown URL kind: {kind}")
    return value


def _descriptor(value: object, name: str) -> ContentDescriptor:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256", "bytes"}:
        raise OccurrenceRegistrationError(f"{name} must contain exactly path, sha256, and bytes")
    return ContentDescriptor(path=value["path"], sha256=value["sha256"], bytes=value["bytes"])


def _api_file_descriptor(file_readback: Mapping[str, Any]) -> tuple[str, str, ContentDescriptor]:
    data = file_readback.get("data")
    if not isinstance(data, Mapping) or data.get("type") != "files":
        raise OccurrenceRegistrationError("OSF file readback must contain data.type=files")
    attributes = data.get("attributes")
    links = data.get("links")
    if not isinstance(attributes, Mapping) or not isinstance(links, Mapping):
        raise OccurrenceRegistrationError("OSF file readback lacks attributes or links")
    hashes = attributes.get("extra")
    if not isinstance(hashes, Mapping) or not isinstance(hashes.get("hashes"), Mapping):
        raise OccurrenceRegistrationError("OSF file readback lacks extra.hashes")
    return (
        _url(links.get("self"), kind="file_metadata"),
        _url(links.get("download"), kind="file_download"),
        ContentDescriptor(
            path=attributes.get("name"),
            sha256=hashes["hashes"].get("sha256"),
            bytes=attributes.get("size"),
        ),
    )


def parse_osf_registration_readback(
    registration_readback: Mapping[str, Any],
    file_readback: Mapping[str, Any],
    *,
    expected_package: ContentDescriptor,
    read_back_bytes: ContentDescriptor,
    read_back_download_url: str,
    pulse_timestamp: str,
) -> OSFRegistrationReadback:
    """Parse a supplied official API v2 readback without fetching or authenticating.

    ``read_back_bytes`` must be independently obtained from ``links.download``
    by a separate reader. Its supplied provenance URL must exactly equal the
    canonical OSF-owned download URL. Byte equality is checked against both
    the intended package and OSF API metadata. Timestamp order is the only
    chronology check made here; it does not establish operator independence.
    """

    if not isinstance(registration_readback, Mapping):
        raise OccurrenceRegistrationError("OSF registration readback must be a mapping")
    data = registration_readback.get("data")
    if not isinstance(data, Mapping) or data.get("type") != "registrations":
        raise OccurrenceRegistrationError("OSF registration readback must contain data.type=registrations")
    registration_id = data.get("id")
    if not isinstance(registration_id, str) or not _OSF_ID.fullmatch(registration_id):
        raise OccurrenceRegistrationError("OSF registration identifier must be immutable five-character lowercase ID")
    attributes = data.get("attributes")
    links = data.get("links")
    if not isinstance(attributes, Mapping) or not isinstance(links, Mapping):
        raise OccurrenceRegistrationError("OSF registration readback lacks attributes or links")
    registration_url = _url(links.get("self"), kind="registration", registration_id=registration_id)
    registration_timestamp, registered_at = _timestamp(attributes.get("date_registered"), "date_registered")
    pulse_text, pulse_at = _timestamp(pulse_timestamp, "pulse_timestamp")
    withdrawn = attributes.get("withdrawn")
    if type(withdrawn) is not bool:
        raise OccurrenceRegistrationError("OSF registration readback withdrawn must be boolean")
    file_metadata_url, file_download_url, api_file = _api_file_descriptor(file_readback)
    if _url(read_back_download_url, kind="file_download") != file_download_url:
        raise OccurrenceRegistrationError(
            "read_back_download_url must exactly match OSF file links.download"
        )
    if expected_package != read_back_bytes or api_file != read_back_bytes:
        status, reason = VOID, "PACKAGE_OR_READBACK_BYTES_DO_NOT_MATCH"
    elif withdrawn:
        status, reason = VOID, "OSF_REGISTRATION_WITHDRAWN"
    elif registered_at >= pulse_at:
        # Once a pulse-bound registration exists, discovering that it was not
        # prospective invalidates that exact occurrence.  It cannot be repaired
        # by waiting, retrying, or selecting a replacement round.
        status, reason = VOID, "REGISTRATION_NOT_STRICTLY_BEFORE_PULSE"
    else:
        status, reason = AUDIT_CANDIDATE, None
    return OSFRegistrationReadback(
        status=status,
        claim_boundary=CLAIM_BOUNDARY,
        registration_id=registration_id,
        registration_url=registration_url,
        file_metadata_url=file_metadata_url,
        file_download_url=file_download_url,
        read_back_download_url=read_back_download_url,
        registration_timestamp=registration_timestamp,
        pulse_timestamp=pulse_text,
        withdrawn=withdrawn,
        expected_package=expected_package,
        api_file=api_file,
        read_back_bytes=read_back_bytes,
        reason=reason,
    )


def build_osf_readback_get_argv(url: str, *, allow_network: bool = False) -> tuple[str, ...]:
    """Return a safe, unauthenticated curl GET argv; never execute it.

    Network access is deliberately opt-in and no header/token/cookie argument
    is accepted, preventing credentials from crossing this readback boundary.
    """

    if allow_network is not True:
        raise OccurrenceRegistrationError("OSF readback HTTP argv requires explicit allow_network=True")
    # File and registration URLs are both permitted; this builder has no way to
    # know which endpoint is being requested, so validate either shape.
    try:
        safe_url = _url(url, kind="file_download")
    except OccurrenceRegistrationError:
        try:
            safe_url = _url(url, kind="file_metadata")
        except OccurrenceRegistrationError:
            safe_url = _url(url, kind="registration")
    return (
        "curl", "--fail", "--silent", "--show-error", "--location",
        "--proto", "=https", "--proto-redir", "=https", "--request", "GET", safe_url,
    )


__all__ = [
    "AUDIT_CANDIDATE",
    "BLOCKED",
    "CLAIM_BOUNDARY",
    "ContentDescriptor",
    "OSFRegistrationReadback",
    "OccurrenceRegistrationError",
    "VOID",
    "build_osf_readback_get_argv",
    "parse_osf_registration_readback",
]
