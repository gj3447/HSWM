"""A narrow W3C Trace Context 1.0 carrier for remote HSWM boundaries.

This module only parses and emits HTTP ``traceparent``/``tracestate`` headers
for distributed-observability correlation.  It is deliberately not a
provenance record, canonical atom, Permit, outcome, causal-credit, or learning
input.  Callers must keep it outside canonical state and use it only at an
actual process boundary.

Normative source: W3C Trace Context, Recommendation 2021-11-23,
https://www.w3.org/TR/2021/REC-trace-context-1-20211123/ sections 3.2--3.5.
The parser accepts the v00 format and safely downgrades a structurally valid
future version as described in section 3.2.4; ``ff`` and malformed input fail
closed.  The 512-character header caps are this adapter's documented local
resource limits under sections 3.2.4 and 3.3.1.5, not W3C MUSTs.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re


TRACE_CONTEXT_REC_URL = "https://www.w3.org/TR/2021/REC-trace-context-1-20211123/"
TRACE_CONTEXT_REC_VERSION = "W3C Trace Context Recommendation 2021-11-23 (v1)"
CLAIM_CEILING = (
    "Correlation-only HTTP carrier; not PROV, canonical state, Permit, "
    "outcome truth, causal credit, or learning evidence."
)
TRACEPARENT_HEADER = "traceparent"
TRACESTATE_HEADER = "tracestate"
MAX_TRACEPARENT_CHARS = 512
MAX_TRACESTATE_MEMBERS = 32
MAX_TRACESTATE_COMBINED_CHARS = 512

_V00_TRACEPARENT = re.compile(
    r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)
_FUTURE_TRACEPARENT = re.compile(
    r"^([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})(?:-|$)"
)
_SIMPLE_KEY = re.compile(r"^[a-z][a-z0-9_\-*/]{0,255}$")
_TENANT_ID = re.compile(r"^[a-z0-9][a-z0-9_\-*/]{0,240}$")
_SYSTEM_ID = re.compile(r"^[a-z][a-z0-9_\-*/]{0,13}$")


class TraceContextError(ValueError):
    """Raised when a locally constructed Trace Context value is invalid."""


@dataclass(frozen=True)
class TraceStateEntry:
    """One validated, opaque ``tracestate`` key/value member."""

    key: str
    value: str

    def __post_init__(self) -> None:
        if not _valid_tracestate_key(self.key):
            raise TraceContextError("invalid tracestate key")
        if not _valid_tracestate_value(self.value):
            raise TraceContextError("invalid tracestate value")


@dataclass(frozen=True)
class TraceContext:
    """Validated v00 correlation context; never an HSWM canonical object."""

    trace_id: str
    parent_id: str
    trace_flags: int
    tracestate: tuple[TraceStateEntry, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier("trace_id", self.trace_id, 32)
        _validate_identifier("parent_id", self.parent_id, 16)
        if type(self.trace_flags) is not int or not 0 <= self.trace_flags <= 1:
            raise TraceContextError("v00 only permits the sampled trace flag")
        if not isinstance(self.tracestate, tuple) or any(
            not isinstance(entry, TraceStateEntry) for entry in self.tracestate
        ):
            raise TraceContextError("tracestate must be an immutable entry tuple")
        if len(self.tracestate) > MAX_TRACESTATE_MEMBERS:
            raise TraceContextError("too many tracestate members")
        if len({entry.key for entry in self.tracestate}) != len(self.tracestate):
            raise TraceContextError("duplicate tracestate key")
        if len(_format_tracestate(self.tracestate)) > MAX_TRACESTATE_COMBINED_CHARS:
            raise TraceContextError("tracestate exceeds local carrier limit")

    @property
    def sampled(self) -> bool:
        """Whether the caller's sampled bit is set; it is not an authority."""
        return self.trace_flags == 1

    def format_traceparent(self) -> str:
        """Return the canonical v00 HTTP header value."""
        return f"00-{self.trace_id}-{self.parent_id}-{self.trace_flags:02x}"


HeaderValue = str | Sequence[str]


def extract_trace_context(headers: Mapping[str, HeaderValue]) -> TraceContext | None:
    """Extract a valid context or return ``None`` without trusting bad input.

    An absent or malformed ``traceparent`` fails closed and prevents any
    ``tracestate`` parsing, as required by REC section 3.3.  A malformed
    ``tracestate`` drops only the opaque tracestate data (REC section 3.3).
    """
    traceparents = _header_values(headers, TRACEPARENT_HEADER)
    if len(traceparents) != 1:
        return None
    parsed = _parse_traceparent(traceparents[0])
    if parsed is None:
        return None
    trace_id, parent_id, flags = parsed
    try:
        entries = _parse_tracestate(_header_values(headers, TRACESTATE_HEADER))
    except TraceContextError:
        entries = ()
    return TraceContext(trace_id, parent_id, flags, entries)


def inject_trace_context(
    context: TraceContext, headers: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Return outgoing headers with lowercase W3C carrier fields installed."""
    outgoing = dict(headers or {})
    for name in tuple(outgoing):
        if name.lower() in {TRACEPARENT_HEADER, TRACESTATE_HEADER}:
            del outgoing[name]
    outgoing[TRACEPARENT_HEADER] = context.format_traceparent()
    if context.tracestate:
        outgoing[TRACESTATE_HEADER] = _format_tracestate(context.tracestate)
    return outgoing


def _parse_traceparent(value: str) -> tuple[str, str, int] | None:
    if not _is_ascii(value) or len(value) > MAX_TRACEPARENT_CHARS:
        return None
    v00 = _V00_TRACEPARENT.fullmatch(value)
    if v00 is not None:
        trace_id, parent_id, flags = v00.groups()
    else:
        future = _FUTURE_TRACEPARENT.match(value)
        if future is None:
            return None
        version, trace_id, parent_id, flags = future.groups()
        if version in {"00", "ff"}:
            return None
    if trace_id == "0" * 32 or parent_id == "0" * 16:
        return None
    # Section 3.2.2.5.2 reserves all flags except sampled.  Ignore them on
    # receipt and emit only sampled, which is the safe v00 downgrade behavior.
    return trace_id, parent_id, int(flags, 16) & 0x01


def _parse_tracestate(header_values: tuple[str, ...]) -> tuple[TraceStateEntry, ...]:
    if not header_values:
        return ()
    if any(not _is_ascii(value) for value in header_values):
        raise TraceContextError("non-ASCII tracestate")
    combined = ",".join(header_values)
    if len(combined) > MAX_TRACESTATE_COMBINED_CHARS:
        raise TraceContextError("tracestate exceeds local carrier limit")
    raw_members = combined.split(",")
    # W3C list-members may be empty/OWS, but they still occupy one of the
    # grammar's maximum 32 member positions.
    if len(raw_members) > MAX_TRACESTATE_MEMBERS:
        raise TraceContextError("too many tracestate list-members")
    entries: list[TraceStateEntry] = []
    for raw_member in raw_members:
        member = raw_member.strip(" \t")
        if not member:
            continue
        if member.count("=") != 1:
            raise TraceContextError("invalid tracestate member")
        key, value = member.split("=", 1)
        entries.append(TraceStateEntry(key, value))
    if len({entry.key for entry in entries}) != len(entries):
        raise TraceContextError("duplicate tracestate key")
    return tuple(entries)


def _header_values(headers: Mapping[str, HeaderValue], name: str) -> tuple[str, ...]:
    values: list[str] = []
    for key, value in headers.items():
        if not isinstance(key, str) or key.lower() != name:
            continue
        if isinstance(value, str):
            candidates: Sequence[str] = (value,)
        elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            candidates = value
        else:
            return ()
        for candidate in candidates:
            if not isinstance(candidate, str):
                return ()
            values.append(candidate)
    return tuple(values)


def _validate_identifier(name: str, value: str, length: int) -> None:
    if (
        not isinstance(value, str)
        or len(value) != length
        or not re.fullmatch(r"[0-9a-f]+", value)
        or value == "0" * length
    ):
        raise TraceContextError(f"invalid {name}")


def _valid_tracestate_key(key: str) -> bool:
    if not isinstance(key, str) or len(key) > 256:
        return False
    if "@" not in key:
        return _SIMPLE_KEY.fullmatch(key) is not None
    if key.count("@") != 1:
        return False
    tenant_id, system_id = key.split("@")
    return _TENANT_ID.fullmatch(tenant_id) is not None and _SYSTEM_ID.fullmatch(system_id) is not None


def _valid_tracestate_value(value: str) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 256
        and all(0x20 <= ord(character) <= 0x7E and character not in {",", "="} for character in value)
        and value[-1] != " "
    )


def _format_tracestate(entries: Sequence[TraceStateEntry]) -> str:
    return ",".join(f"{entry.key}={entry.value}" for entry in entries)


def _is_ascii(value: object) -> bool:
    return isinstance(value, str) and value.isascii()
