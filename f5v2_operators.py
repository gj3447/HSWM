"""Pure F5v2 packet and ephemeral retrieval operators.

Only the five-field CPL1 numeric transfer payload may cross this boundary.
Episode identity, outcome, frozen-topic attestation, and other experimental
metadata belong in a future versioned envelope; they are not silently inferred
or added to this payload.
Query-conditioned extractive/QFR objects are deliberately marked non-durable.
The preregistered durable B0 and B-prime candidate stores live in
:mod:`f5v2_topic_cache`.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
from typing import Any, Mapping, Sequence


APPEND_ONLY_SCHEMA = "hswm-f5v2-append-only/v1"
CANONICAL_SOURCE_CUT_SCHEMA = "hswm-f5v2-canonical-source-cut/v1"
_PACKET_FIELDS = frozenset(
    {
        "shared_schema_sha256",
        "edge_or_hyperedge_id",
        "numeric_delta",
        "confidence",
        "provenance_sha256",
    }
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class F5V2ContractError(ValueError):
    """Raised when an F5v2 value would violate the frozen data boundary."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic JSON bytes and reject non-finite JSON values."""

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise F5V2ContractError(f"value is not canonical JSON: {exc}") from exc


def _digest(value: Any) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _require_sha256(name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise F5V2ContractError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise F5V2ContractError(f"{name} must be a non-empty string")
    if value != value.strip() or len(value) > 512 or any(ord(ch) < 32 for ch in value):
        raise F5V2ContractError(f"{name} has invalid whitespace or control characters")
    return value


def _require_finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise F5V2ContractError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise F5V2ContractError(f"{name} must be finite")
    return 0.0 if result == 0.0 else result


@dataclass(frozen=True, slots=True)
class CPL1NumericPacket:
    """Exact query-free numeric packet emitted by the CPL1 transfer boundary."""

    shared_schema_sha256: str
    edge_or_hyperedge_id: str
    numeric_delta: float
    confidence: float
    provenance_sha256: str

    def __post_init__(self) -> None:
        _require_sha256("shared_schema_sha256", self.shared_schema_sha256)
        _require_identifier("edge_or_hyperedge_id", self.edge_or_hyperedge_id)
        delta = _require_finite_number("numeric_delta", self.numeric_delta)
        confidence = _require_finite_number("confidence", self.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise F5V2ContractError("confidence must be between 0 and 1")
        object.__setattr__(self, "numeric_delta", delta)
        object.__setattr__(self, "confidence", confidence)
        _require_sha256("provenance_sha256", self.provenance_sha256)

    def canonical(self) -> dict[str, Any]:
        return {
            "shared_schema_sha256": self.shared_schema_sha256,
            "edge_or_hyperedge_id": self.edge_or_hyperedge_id,
            "numeric_delta": self.numeric_delta,
            "confidence": self.confidence,
            "provenance_sha256": self.provenance_sha256,
        }

    @property
    def packet_sha256(self) -> str:
        return _digest(self.canonical())


CPL1NumericPacketV1 = CPL1NumericPacket


def parse_cpl1_numeric_packet(value: Mapping[str, object]) -> CPL1NumericPacket:
    """Parse an exact five-field packet; unknown fields fail closed."""

    if not isinstance(value, Mapping):
        raise F5V2ContractError("CPL1 numeric packet must be an object")
    fields = set(value)
    unexpected = sorted(fields - _PACKET_FIELDS)
    missing = sorted(_PACKET_FIELDS - fields)
    if unexpected:
        raise F5V2ContractError(f"unexpected fields: {', '.join(unexpected)}")
    if missing:
        raise F5V2ContractError(f"missing fields: {', '.join(missing)}")
    return CPL1NumericPacket(
        shared_schema_sha256=value["shared_schema_sha256"],  # type: ignore[arg-type]
        edge_or_hyperedge_id=value["edge_or_hyperedge_id"],  # type: ignore[arg-type]
        numeric_delta=value["numeric_delta"],  # type: ignore[arg-type]
        confidence=value["confidence"],  # type: ignore[arg-type]
        provenance_sha256=value["provenance_sha256"],  # type: ignore[arg-type]
    )


def _packets(value: Sequence[CPL1NumericPacket]) -> tuple[CPL1NumericPacket, ...]:
    if isinstance(value, (str, bytes)):
        raise F5V2ContractError("packets must be a packet sequence")
    result = tuple(value)
    if not result:
        raise F5V2ContractError("at least one packet is required")
    if any(not isinstance(item, CPL1NumericPacket) for item in result):
        raise F5V2ContractError("packets must contain only CPL1NumericPacket values")
    digests = [item.packet_sha256 for item in result]
    if len(digests) != len(set(digests)):
        raise F5V2ContractError("duplicate packet digest is ambiguous")
    return result


@dataclass(frozen=True, slots=True)
class ProvenanceSpan:
    """One indivisible, verbatim CPL1 packet selected by B0."""

    packet: CPL1NumericPacket

    @property
    def packet_sha256(self) -> str:
        return self.packet.packet_sha256

    def canonical(self) -> dict[str, Any]:
        return {
            "packet_sha256": self.packet_sha256,
            "packet": self.packet.canonical(),
        }


@dataclass(frozen=True, slots=True)
class ReassemblyBlock:
    """Ephemeral query-focused retrieval/reassembly result."""

    mode: str
    query_sha256: str
    spans: tuple[ProvenanceSpan, ...]
    content: str
    cited_packet_sha256s: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.mode not in {"R_EXTRACTIVE", "QFR"}:
            raise F5V2ContractError(f"unknown reassembly mode {self.mode!r}")
        _require_sha256("query_sha256", self.query_sha256)
        if not self.spans:
            raise F5V2ContractError("reassembly must contain at least one span")
        if not isinstance(self.content, str) or not self.content.strip():
            raise F5V2ContractError("reassembly content must be non-empty")

    @property
    def durable(self) -> bool:
        return False

    def canonical(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "query_sha256": self.query_sha256,
            "spans": [span.canonical() for span in self.spans],
            "content": self.content,
            "cited_packet_sha256s": list(self.cited_packet_sha256s),
            "durable": False,
        }


def _query_sha256(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        raise F5V2ContractError("query must be a non-empty string")
    return sha256(query.encode("utf-8")).hexdigest()


def build_qfr_extractive_source(
    query: str,
    packets: Sequence[CPL1NumericPacket],
    *,
    selected_packet_sha256s: Sequence[str] | None = None,
) -> ReassemblyBlock:
    """Build R/QFR's ephemeral extractive source from indivisible packets."""

    source = _packets(packets)
    by_digest = {packet.packet_sha256: packet for packet in source}
    selected = (
        tuple(by_digest)
        if selected_packet_sha256s is None
        else tuple(selected_packet_sha256s)
    )
    if not selected:
        raise F5V2ContractError("B0 must select at least one packet")
    if len(selected) != len(set(selected)):
        raise F5V2ContractError("B0 packet selection contains duplicates")
    for digest in selected:
        _require_sha256("selected packet digest", digest)
        if digest not in by_digest:
            raise F5V2ContractError(f"unknown packet {digest}")
    spans = tuple(ProvenanceSpan(by_digest[digest]) for digest in selected)
    content = canonical_json_bytes(
        {"packets": [span.packet.canonical() for span in spans]}
    ).decode("utf-8")
    return ReassemblyBlock(
        mode="R_EXTRACTIVE",
        query_sha256=_query_sha256(query),
        spans=spans,
        content=content,
        cited_packet_sha256s=selected,
    )


def build_abstractive_qfr(
    query: str,
    b0: ReassemblyBlock,
    *,
    content: str,
    cited_packet_sha256s: Sequence[str] | None = None,
) -> ReassemblyBlock:
    """Build an ephemeral abstraction whose citations are bounded by its B0."""

    if not isinstance(b0, ReassemblyBlock) or b0.mode != "R_EXTRACTIVE":
        raise F5V2ContractError("QFR requires an R_EXTRACTIVE source")
    if _query_sha256(query) != b0.query_sha256:
        raise F5V2ContractError("query does not match B0")
    available = tuple(span.packet_sha256 for span in b0.spans)
    cited = available if cited_packet_sha256s is None else tuple(cited_packet_sha256s)
    if not cited:
        raise F5V2ContractError("QFR must cite at least one B0 packet")
    if len(cited) != len(set(cited)):
        raise F5V2ContractError("QFR citations contain duplicates")
    for digest in cited:
        _require_sha256("cited packet digest", digest)
        if digest not in available:
            raise F5V2ContractError(f"cited packet {digest} is not present in B0")
    return ReassemblyBlock(
        mode="QFR",
        query_sha256=b0.query_sha256,
        spans=b0.spans,
        content=content,
        cited_packet_sha256s=cited,
    )


def render_append_only(packets: Sequence[CPL1NumericPacket]) -> str:
    """Render an immutable source cut without reordering or rewriting packets."""

    source = _packets(packets)
    return canonical_json_bytes(
        {
            "schema_version": APPEND_ONLY_SCHEMA,
            "packets": [packet.canonical() for packet in source],
        }
    ).decode("utf-8")


def append_only_sha256(packets: Sequence[CPL1NumericPacket]) -> str:
    return sha256(render_append_only(packets).encode("utf-8")).hexdigest()


def canonical_source_cut_sha256(packets: Sequence[CPL1NumericPacket]) -> str:
    """Hash the packet set independently of caller iteration or append order.

    This cache identity is intentionally distinct from :func:`append_only_sha256`,
    which remains the byte/order-sensitive raw-log integrity receipt.
    """

    source = sorted(_packets(packets), key=lambda packet: packet.packet_sha256)
    return _digest(
        {
            "schema_version": CANONICAL_SOURCE_CUT_SCHEMA,
            "packets": [packet.canonical() for packet in source],
        }
    )
