"""Immutable query-agnostic F5v2 B-prime topic cache.

The cache derives a deterministic slow-W candidate and slow-H membership candidate
from CPL1 numeric packets.  It preserves every source packet/provenance digest,
records sign-disagreeing observations in an exception ledger, and writes each
content-addressed object at most once.  This is an offline file-cache prototype,
not a scientific promotion verdict, a SQLite CAS epoch store, or slow-H
activation.  Episode/topic-freeze metadata belongs to a future outer envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from f5v2_operators import (
    CPL1NumericPacket,
    F5V2ContractError,
    append_only_sha256,
    canonical_source_cut_sha256,
    canonical_json_bytes,
    parse_cpl1_numeric_packet,
)


R_ARM_ID = "R_QFR_EPHEMERAL"
B0_ARM_ID = "B0_EXTRACTIVE_DURABLE_CACHE"
BPRIME_ARM_ID = "B_PRIME_DURABLE_SLOW_W_H"
B0_BLOCK_SCHEMA = "hswm-f5v2-b0-topic-block/v1"
B0_MANIFEST_SCHEMA = "hswm-f5v2-b0-topic-cache-manifest/v1"
BLOCK_SCHEMA = "hswm-f5v2-bprime-topic-block/v1"
MANIFEST_SCHEMA = "hswm-f5v2-bprime-topic-cache-manifest/v1"
DERIVATION_POLICY = "confidence-weighted-mean-sign-exceptions/v1"
DERIVATION_POLICY_SHA256 = sha256(DERIVATION_POLICY.encode("utf-8")).hexdigest()


class TopicCacheIntegrityError(RuntimeError):
    """Raised for malformed, conflicting, dangling, or tampered cache state."""


def _digest(value: Any) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _exact_fields(value: object, expected: set[str], *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TopicCacheIntegrityError(f"{label} must be an object")
    fields = set(value)
    unexpected = sorted(fields - expected)
    missing = sorted(expected - fields)
    if unexpected:
        raise TopicCacheIntegrityError(
            f"{label} has unexpected fields: {', '.join(unexpected)}"
        )
    if missing:
        raise TopicCacheIntegrityError(f"{label} has missing fields: {', '.join(missing)}")
    return value


def _sha(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise TopicCacheIntegrityError(f"{label} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class TopicWeightUpdateV1:
    packet_sha256: str
    edge_or_hyperedge_id: str
    numeric_delta: float
    confidence: float
    provenance_sha256: str

    @classmethod
    def from_packet(cls, packet: CPL1NumericPacket) -> "TopicWeightUpdateV1":
        return cls(
            packet_sha256=packet.packet_sha256,
            edge_or_hyperedge_id=packet.edge_or_hyperedge_id,
            numeric_delta=packet.numeric_delta,
            confidence=packet.confidence,
            provenance_sha256=packet.provenance_sha256,
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "packet_sha256": self.packet_sha256,
            "edge_or_hyperedge_id": self.edge_or_hyperedge_id,
            "numeric_delta": self.numeric_delta,
            "confidence": self.confidence,
            "provenance_sha256": self.provenance_sha256,
        }


def _derive(updates: Sequence[TopicWeightUpdateV1]) -> tuple[float, tuple[str, ...]]:
    denominator = sum(update.confidence for update in updates)
    if denominator > 0.0:
        rule = sum(
            update.numeric_delta * update.confidence for update in updates
        ) / denominator
    else:
        rule = sum(update.numeric_delta for update in updates) / len(updates)
    rule = 0.0 if rule == 0.0 else rule
    exceptions = tuple(
        update.packet_sha256
        for update in updates
        if rule != 0.0
        and update.numeric_delta != 0.0
        and math.copysign(1.0, update.numeric_delta) != math.copysign(1.0, rule)
    )
    return rule, exceptions


@dataclass(frozen=True, slots=True)
class TopicBlockV1:
    block_id: str
    topic_key: str
    shared_schema_sha256: str
    source_cut_sha256: str
    slow_w_rule: float
    slow_w_updates: tuple[TopicWeightUpdateV1, ...]
    slow_h_members: tuple[str, ...]
    exception_packet_sha256s: tuple[str, ...]
    derivation_policy_sha256: str = DERIVATION_POLICY_SHA256
    arm_id: str = BPRIME_ARM_ID
    schema_version: str = BLOCK_SCHEMA

    def _unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "arm_id": self.arm_id,
            "topic_key": self.topic_key,
            "shared_schema_sha256": self.shared_schema_sha256,
            "source_cut_sha256": self.source_cut_sha256,
            "derivation_policy_sha256": self.derivation_policy_sha256,
            "slow_w_rule": self.slow_w_rule,
            "slow_w_updates": [update.canonical() for update in self.slow_w_updates],
            "slow_h_members": list(self.slow_h_members),
            "exception_packet_sha256s": list(self.exception_packet_sha256s),
        }

    def canonical(self) -> dict[str, Any]:
        return {"block_id": self.block_id, **self._unsigned()}


@dataclass(frozen=True, slots=True)
class TopicCacheManifestV1:
    manifest_id: str
    source_cut_sha256: str
    shared_schema_sha256: str
    block_ids: tuple[str, ...]
    packet_count: int
    derivation_policy_sha256: str = DERIVATION_POLICY_SHA256
    arm_id: str = BPRIME_ARM_ID
    schema_version: str = MANIFEST_SCHEMA

    def _unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "arm_id": self.arm_id,
            "source_cut_sha256": self.source_cut_sha256,
            "shared_schema_sha256": self.shared_schema_sha256,
            "block_ids": list(self.block_ids),
            "packet_count": self.packet_count,
            "derivation_policy_sha256": self.derivation_policy_sha256,
        }

    def canonical(self) -> dict[str, Any]:
        return {"manifest_id": self.manifest_id, **self._unsigned()}


@dataclass(frozen=True, slots=True)
class LoadedTopicCache:
    manifest: TopicCacheManifestV1
    blocks: tuple[TopicBlockV1, ...]


@dataclass(frozen=True, slots=True)
class B0AtomicPacketV1:
    packet_sha256: str
    packet: CPL1NumericPacket

    @classmethod
    def from_packet(cls, packet: CPL1NumericPacket) -> "B0AtomicPacketV1":
        return cls(packet_sha256=packet.packet_sha256, packet=packet)

    def canonical(self) -> dict[str, Any]:
        return {
            "packet_sha256": self.packet_sha256,
            "packet": self.packet.canonical(),
        }


@dataclass(frozen=True, slots=True)
class B0TopicBlockV1:
    block_id: str
    topic_key: str
    shared_schema_sha256: str
    source_cut_sha256: str
    packets: tuple[B0AtomicPacketV1, ...]
    arm_id: str = B0_ARM_ID
    schema_version: str = B0_BLOCK_SCHEMA

    def _unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "arm_id": self.arm_id,
            "topic_key": self.topic_key,
            "shared_schema_sha256": self.shared_schema_sha256,
            "source_cut_sha256": self.source_cut_sha256,
            "packets": [packet.canonical() for packet in self.packets],
        }

    def canonical(self) -> dict[str, Any]:
        return {"block_id": self.block_id, **self._unsigned()}


@dataclass(frozen=True, slots=True)
class B0TopicCacheManifestV1:
    manifest_id: str
    source_cut_sha256: str
    shared_schema_sha256: str
    block_ids: tuple[str, ...]
    packet_count: int
    arm_id: str = B0_ARM_ID
    schema_version: str = B0_MANIFEST_SCHEMA

    def _unsigned(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "arm_id": self.arm_id,
            "source_cut_sha256": self.source_cut_sha256,
            "shared_schema_sha256": self.shared_schema_sha256,
            "block_ids": list(self.block_ids),
            "packet_count": self.packet_count,
        }

    def canonical(self) -> dict[str, Any]:
        return {"manifest_id": self.manifest_id, **self._unsigned()}


@dataclass(frozen=True, slots=True)
class LoadedB0TopicCache:
    manifest: B0TopicCacheManifestV1
    blocks: tuple[B0TopicBlockV1, ...]


def _make_block(
    topic_key: str,
    packets: Sequence[CPL1NumericPacket],
    *,
    shared_schema_sha256: str,
    source_cut_sha256: str,
) -> TopicBlockV1:
    updates = tuple(
        sorted(
            (TopicWeightUpdateV1.from_packet(packet) for packet in packets),
            key=lambda update: update.packet_sha256,
        )
    )
    rule, exceptions = _derive(updates)
    provisional = TopicBlockV1(
        block_id="0" * 64,
        topic_key=topic_key,
        shared_schema_sha256=shared_schema_sha256,
        source_cut_sha256=source_cut_sha256,
        slow_w_rule=rule,
        slow_w_updates=updates,
        slow_h_members=(topic_key,),
        exception_packet_sha256s=exceptions,
    )
    return TopicBlockV1(
        block_id=_digest(provisional._unsigned()),
        topic_key=provisional.topic_key,
        shared_schema_sha256=provisional.shared_schema_sha256,
        source_cut_sha256=provisional.source_cut_sha256,
        slow_w_rule=provisional.slow_w_rule,
        slow_w_updates=provisional.slow_w_updates,
        slow_h_members=provisional.slow_h_members,
        exception_packet_sha256s=provisional.exception_packet_sha256s,
    )


def _parse_update(value: object, *, schema_sha256: str) -> TopicWeightUpdateV1:
    item = _exact_fields(
        value,
        {
            "packet_sha256",
            "edge_or_hyperedge_id",
            "numeric_delta",
            "confidence",
            "provenance_sha256",
        },
        label="slow-W update",
    )
    try:
        packet = parse_cpl1_numeric_packet(
            {
                "shared_schema_sha256": schema_sha256,
                "edge_or_hyperedge_id": item["edge_or_hyperedge_id"],
                "numeric_delta": item["numeric_delta"],
                "confidence": item["confidence"],
                "provenance_sha256": item["provenance_sha256"],
            }
        )
    except F5V2ContractError as exc:
        raise TopicCacheIntegrityError(f"invalid slow-W update: {exc}") from exc
    packet_sha = _sha(item["packet_sha256"], label="packet_sha256")
    if packet.packet_sha256 != packet_sha:
        raise TopicCacheIntegrityError("slow-W update packet digest mismatch")
    return TopicWeightUpdateV1.from_packet(packet)


def _parse_block(value: object) -> TopicBlockV1:
    item = _exact_fields(
        value,
        {
            "block_id",
            "schema_version",
            "arm_id",
            "topic_key",
            "shared_schema_sha256",
            "source_cut_sha256",
            "derivation_policy_sha256",
            "slow_w_rule",
            "slow_w_updates",
            "slow_h_members",
            "exception_packet_sha256s",
        },
        label="topic block",
    )
    if item["schema_version"] != BLOCK_SCHEMA:
        raise TopicCacheIntegrityError("topic block schema version mismatch")
    if item["arm_id"] != BPRIME_ARM_ID:
        raise TopicCacheIntegrityError("topic block arm mismatch")
    schema_sha = _sha(item["shared_schema_sha256"], label="shared schema digest")
    if not isinstance(item["slow_w_updates"], list) or not item["slow_w_updates"]:
        raise TopicCacheIntegrityError("slow_w_updates must be a non-empty list")
    updates = tuple(
        _parse_update(update, schema_sha256=schema_sha)
        for update in item["slow_w_updates"]
    )
    if not isinstance(item["topic_key"], str) or not item["topic_key"]:
        raise TopicCacheIntegrityError("topic_key must be non-empty")
    if any(update.edge_or_hyperedge_id != item["topic_key"] for update in updates):
        raise TopicCacheIntegrityError("topic block contains a cross-topic update")
    if not isinstance(item["slow_w_rule"], (int, float)) or isinstance(
        item["slow_w_rule"], bool
    ) or not math.isfinite(float(item["slow_w_rule"])):
        raise TopicCacheIntegrityError("slow_w_rule must be finite")
    if not isinstance(item["slow_h_members"], list) or item["slow_h_members"] != [item["topic_key"]]:
        raise TopicCacheIntegrityError("slow-H membership mismatch")
    if not isinstance(item["exception_packet_sha256s"], list):
        raise TopicCacheIntegrityError("exception ledger must be a list")
    expected_rule, expected_exceptions = _derive(updates)
    if float(item["slow_w_rule"]) != expected_rule:
        raise TopicCacheIntegrityError("derived slow-W rule mismatch")
    if tuple(item["exception_packet_sha256s"]) != expected_exceptions:
        raise TopicCacheIntegrityError("exception ledger mismatch")
    block = TopicBlockV1(
        block_id=_sha(item["block_id"], label="block digest"),
        topic_key=item["topic_key"],
        shared_schema_sha256=schema_sha,
        source_cut_sha256=_sha(item["source_cut_sha256"], label="source cut digest"),
        slow_w_rule=expected_rule,
        slow_w_updates=updates,
        slow_h_members=tuple(item["slow_h_members"]),
        exception_packet_sha256s=expected_exceptions,
        derivation_policy_sha256=_sha(
            item["derivation_policy_sha256"], label="derivation policy digest"
        ),
        schema_version=item["schema_version"],
    )
    if block.derivation_policy_sha256 != DERIVATION_POLICY_SHA256:
        raise TopicCacheIntegrityError("derivation policy mismatch")
    if _digest(block._unsigned()) != block.block_id:
        raise TopicCacheIntegrityError("topic block digest mismatch")
    return block


def _make_manifest(
    blocks: Sequence[TopicBlockV1],
    *,
    source_cut_sha256: str,
    shared_schema_sha256: str,
    packet_count: int,
) -> TopicCacheManifestV1:
    provisional = TopicCacheManifestV1(
        manifest_id="0" * 64,
        source_cut_sha256=source_cut_sha256,
        shared_schema_sha256=shared_schema_sha256,
        block_ids=tuple(sorted(block.block_id for block in blocks)),
        packet_count=packet_count,
    )
    return TopicCacheManifestV1(
        manifest_id=_digest(provisional._unsigned()),
        source_cut_sha256=provisional.source_cut_sha256,
        shared_schema_sha256=provisional.shared_schema_sha256,
        block_ids=provisional.block_ids,
        packet_count=provisional.packet_count,
    )


def _parse_manifest(value: object) -> TopicCacheManifestV1:
    item = _exact_fields(
        value,
        {
            "manifest_id",
            "schema_version",
            "arm_id",
            "source_cut_sha256",
            "shared_schema_sha256",
            "block_ids",
            "packet_count",
            "derivation_policy_sha256",
        },
        label="manifest",
    )
    if item["schema_version"] != MANIFEST_SCHEMA:
        raise TopicCacheIntegrityError("manifest schema version mismatch")
    if item["arm_id"] != BPRIME_ARM_ID:
        raise TopicCacheIntegrityError("manifest arm mismatch")
    if not isinstance(item["block_ids"], list) or not item["block_ids"]:
        raise TopicCacheIntegrityError("manifest block_ids must be non-empty")
    block_ids = tuple(_sha(value, label="block digest") for value in item["block_ids"])
    if len(block_ids) != len(set(block_ids)):
        raise TopicCacheIntegrityError("manifest contains duplicate block digest")
    if not isinstance(item["packet_count"], int) or isinstance(item["packet_count"], bool) or item["packet_count"] < 1:
        raise TopicCacheIntegrityError("manifest packet_count must be positive")
    manifest = TopicCacheManifestV1(
        manifest_id=_sha(item["manifest_id"], label="manifest digest"),
        source_cut_sha256=_sha(item["source_cut_sha256"], label="source cut digest"),
        shared_schema_sha256=_sha(item["shared_schema_sha256"], label="shared schema digest"),
        block_ids=block_ids,
        packet_count=item["packet_count"],
        derivation_policy_sha256=_sha(
            item["derivation_policy_sha256"], label="derivation policy digest"
        ),
        schema_version=item["schema_version"],
    )
    if manifest.derivation_policy_sha256 != DERIVATION_POLICY_SHA256:
        raise TopicCacheIntegrityError("manifest derivation policy mismatch")
    if _digest(manifest._unsigned()) != manifest.manifest_id:
        raise TopicCacheIntegrityError("manifest digest mismatch")
    return manifest


def _make_b0_block(
    topic_key: str,
    packets: Sequence[CPL1NumericPacket],
    *,
    shared_schema_sha256: str,
    source_cut_sha256: str,
) -> B0TopicBlockV1:
    atomic = tuple(
        B0AtomicPacketV1.from_packet(packet)
        for packet in sorted(packets, key=lambda item: item.packet_sha256)
    )
    provisional = B0TopicBlockV1(
        block_id="0" * 64,
        topic_key=topic_key,
        shared_schema_sha256=shared_schema_sha256,
        source_cut_sha256=source_cut_sha256,
        packets=atomic,
    )
    return B0TopicBlockV1(
        block_id=_digest(provisional._unsigned()),
        topic_key=provisional.topic_key,
        shared_schema_sha256=provisional.shared_schema_sha256,
        source_cut_sha256=provisional.source_cut_sha256,
        packets=provisional.packets,
    )


def _parse_b0_atomic(value: object) -> B0AtomicPacketV1:
    item = _exact_fields(
        value,
        {"packet_sha256", "packet"},
        label="B0 atomic packet",
    )
    try:
        packet = parse_cpl1_numeric_packet(item["packet"])
    except F5V2ContractError as exc:
        raise TopicCacheIntegrityError(f"invalid B0 atomic packet: {exc}") from exc
    digest = _sha(item["packet_sha256"], label="B0 packet digest")
    if digest != packet.packet_sha256:
        raise TopicCacheIntegrityError("B0 packet digest mismatch")
    return B0AtomicPacketV1(packet_sha256=digest, packet=packet)


def _parse_b0_block(value: object) -> B0TopicBlockV1:
    item = _exact_fields(
        value,
        {
            "block_id",
            "schema_version",
            "arm_id",
            "topic_key",
            "shared_schema_sha256",
            "source_cut_sha256",
            "packets",
        },
        label="B0 topic block",
    )
    if item["schema_version"] != B0_BLOCK_SCHEMA or item["arm_id"] != B0_ARM_ID:
        raise TopicCacheIntegrityError("B0 topic block schema or arm mismatch")
    if not isinstance(item["topic_key"], str) or not item["topic_key"]:
        raise TopicCacheIntegrityError("B0 topic_key must be non-empty")
    if not isinstance(item["packets"], list) or not item["packets"]:
        raise TopicCacheIntegrityError("B0 packets must be a non-empty list")
    packets = tuple(_parse_b0_atomic(packet) for packet in item["packets"])
    packet_ids = tuple(packet.packet_sha256 for packet in packets)
    if packet_ids != tuple(sorted(packet_ids)) or len(packet_ids) != len(set(packet_ids)):
        raise TopicCacheIntegrityError("B0 packets are not canonical and unique")
    if any(packet.packet.edge_or_hyperedge_id != item["topic_key"] for packet in packets):
        raise TopicCacheIntegrityError("B0 topic block contains a cross-topic packet")
    schema_sha = _sha(item["shared_schema_sha256"], label="B0 shared schema digest")
    if any(packet.packet.shared_schema_sha256 != schema_sha for packet in packets):
        raise TopicCacheIntegrityError("B0 topic block mixes shared schemas")
    block = B0TopicBlockV1(
        block_id=_sha(item["block_id"], label="B0 block digest"),
        topic_key=item["topic_key"],
        shared_schema_sha256=schema_sha,
        source_cut_sha256=_sha(item["source_cut_sha256"], label="B0 source cut digest"),
        packets=packets,
    )
    if _digest(block._unsigned()) != block.block_id:
        raise TopicCacheIntegrityError("B0 topic block digest mismatch")
    return block


def _make_b0_manifest(
    blocks: Sequence[B0TopicBlockV1],
    *,
    source_cut_sha256: str,
    shared_schema_sha256: str,
    packet_count: int,
) -> B0TopicCacheManifestV1:
    provisional = B0TopicCacheManifestV1(
        manifest_id="0" * 64,
        source_cut_sha256=source_cut_sha256,
        shared_schema_sha256=shared_schema_sha256,
        block_ids=tuple(sorted(block.block_id for block in blocks)),
        packet_count=packet_count,
    )
    return B0TopicCacheManifestV1(
        manifest_id=_digest(provisional._unsigned()),
        source_cut_sha256=provisional.source_cut_sha256,
        shared_schema_sha256=provisional.shared_schema_sha256,
        block_ids=provisional.block_ids,
        packet_count=provisional.packet_count,
    )


def _parse_b0_manifest(value: object) -> B0TopicCacheManifestV1:
    item = _exact_fields(
        value,
        {
            "manifest_id",
            "schema_version",
            "arm_id",
            "source_cut_sha256",
            "shared_schema_sha256",
            "block_ids",
            "packet_count",
        },
        label="B0 manifest",
    )
    if item["schema_version"] != B0_MANIFEST_SCHEMA or item["arm_id"] != B0_ARM_ID:
        raise TopicCacheIntegrityError("B0 manifest schema or arm mismatch")
    if not isinstance(item["block_ids"], list) or not item["block_ids"]:
        raise TopicCacheIntegrityError("B0 manifest block_ids must be non-empty")
    block_ids = tuple(_sha(value, label="B0 block digest") for value in item["block_ids"])
    if block_ids != tuple(sorted(block_ids)) or len(block_ids) != len(set(block_ids)):
        raise TopicCacheIntegrityError("B0 manifest block_ids are not canonical and unique")
    if not isinstance(item["packet_count"], int) or isinstance(item["packet_count"], bool) or item["packet_count"] < 1:
        raise TopicCacheIntegrityError("B0 manifest packet_count must be positive")
    manifest = B0TopicCacheManifestV1(
        manifest_id=_sha(item["manifest_id"], label="B0 manifest digest"),
        source_cut_sha256=_sha(item["source_cut_sha256"], label="B0 source cut digest"),
        shared_schema_sha256=_sha(item["shared_schema_sha256"], label="B0 shared schema digest"),
        block_ids=block_ids,
        packet_count=item["packet_count"],
    )
    if _digest(manifest._unsigned()) != manifest.manifest_id:
        raise TopicCacheIntegrityError("B0 manifest digest mismatch")
    return manifest


def _read_json(path: Path, *, label: str) -> Any:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise TopicCacheIntegrityError(f"cannot read {label}: {exc}") from exc
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TopicCacheIntegrityError(f"invalid {label} JSON: {exc}") from exc


def _write_once(path: Path, value: Mapping[str, Any]) -> None:
    payload = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise TopicCacheIntegrityError(f"content-addressed write conflict at {path}")
        return
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def build_b0_extractive_cache(
    cache_dir: str | Path,
    packets: Sequence[CPL1NumericPacket],
    *,
    expected_source_cut_sha256: str | None = None,
) -> B0TopicCacheManifestV1:
    """Build the durable query-agnostic B0 arm without derived state."""

    source = tuple(packets)
    if not source or any(not isinstance(packet, CPL1NumericPacket) for packet in source):
        raise TopicCacheIntegrityError("B0 source must be non-empty CPL1 packets")
    packet_ids = tuple(packet.packet_sha256 for packet in source)
    if len(packet_ids) != len(set(packet_ids)):
        raise TopicCacheIntegrityError("B0 source contains duplicate packet digest")
    schemas = {packet.shared_schema_sha256 for packet in source}
    if len(schemas) != 1:
        raise TopicCacheIntegrityError("B0 source mixes shared schemas")
    raw_append_before = append_only_sha256(source)
    source_cut = canonical_source_cut_sha256(source)
    if expected_source_cut_sha256 is not None:
        _sha(expected_source_cut_sha256, label="expected B0 source cut digest")
        if source_cut != expected_source_cut_sha256:
            raise TopicCacheIntegrityError("B0 source cut digest mismatch")
    grouped: dict[str, list[CPL1NumericPacket]] = {}
    for packet in source:
        grouped.setdefault(packet.edge_or_hyperedge_id, []).append(packet)
    shared_schema = next(iter(schemas))
    blocks = tuple(
        _make_b0_block(
            topic_key,
            grouped[topic_key],
            shared_schema_sha256=shared_schema,
            source_cut_sha256=source_cut,
        )
        for topic_key in sorted(grouped)
    )
    manifest = _make_b0_manifest(
        blocks,
        source_cut_sha256=source_cut,
        shared_schema_sha256=shared_schema,
        packet_count=len(source),
    )
    root = Path(cache_dir)
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        loaded = load_b0_extractive_cache(root)
        if loaded.manifest != manifest or set(loaded.blocks) != set(blocks):
            raise TopicCacheIntegrityError("immutable B0 cache conflicts with source")
        return manifest
    by_id = {block.block_id: block for block in blocks}
    for block_id in manifest.block_ids:
        _write_once(root / "blocks" / f"{block_id}.json", by_id[block_id].canonical())
    _write_once(manifest_path, manifest.canonical())
    if append_only_sha256(source) != raw_append_before:
        raise TopicCacheIntegrityError("raw append source changed during B0 build")
    return manifest


def verify_b0_extractive_cache(
    cache_dir: str | Path,
    *,
    expected_source_cut_sha256: str | None = None,
) -> LoadedB0TopicCache:
    root = Path(cache_dir)
    manifest = _parse_b0_manifest(_read_json(root / "manifest.json", label="B0 manifest"))
    if expected_source_cut_sha256 is not None:
        _sha(expected_source_cut_sha256, label="expected B0 source cut digest")
        if manifest.source_cut_sha256 != expected_source_cut_sha256:
            raise TopicCacheIntegrityError("B0 source cut digest mismatch")
    blocks: list[B0TopicBlockV1] = []
    for block_id in manifest.block_ids:
        block = _parse_b0_block(
            _read_json(root / "blocks" / f"{block_id}.json", label="B0 topic block")
        )
        if block.block_id != block_id:
            raise TopicCacheIntegrityError("B0 manifest block digest mismatch")
        if block.source_cut_sha256 != manifest.source_cut_sha256:
            raise TopicCacheIntegrityError("B0 block source cut mismatch")
        if block.shared_schema_sha256 != manifest.shared_schema_sha256:
            raise TopicCacheIntegrityError("B0 block shared schema mismatch")
        blocks.append(block)
    if sum(len(block.packets) for block in blocks) != manifest.packet_count:
        raise TopicCacheIntegrityError("B0 manifest packet_count mismatch")
    if len({block.topic_key for block in blocks}) != len(blocks):
        raise TopicCacheIntegrityError("B0 manifest contains duplicate topic blocks")
    return LoadedB0TopicCache(manifest=manifest, blocks=tuple(blocks))


def load_b0_extractive_cache(cache_dir: str | Path) -> LoadedB0TopicCache:
    return verify_b0_extractive_cache(cache_dir)


def select_b0_extractive_blocks(
    cache_dir: str | Path,
    *,
    edge_or_hyperedge_ids: Sequence[str],
) -> tuple[B0TopicBlockV1, ...]:
    requested = tuple(edge_or_hyperedge_ids)
    if not requested or len(requested) != len(set(requested)):
        raise TopicCacheIntegrityError("B0 structural selection must be unique and non-empty")
    loaded = verify_b0_extractive_cache(cache_dir)
    by_topic = {block.topic_key: block for block in loaded.blocks}
    unknown = [topic for topic in requested if topic not in by_topic]
    if unknown:
        raise TopicCacheIntegrityError(f"unknown B0 topic block: {', '.join(unknown)}")
    return tuple(by_topic[topic] for topic in requested)


def build_bprime_candidate_cache(
    cache_dir: str | Path,
    packets: Sequence[CPL1NumericPacket],
    *,
    expected_source_cut_sha256: str | None = None,
) -> TopicCacheManifestV1:
    """Build or reopen one immutable B-prime cache without accepting a query."""

    source = tuple(packets)
    if not source or any(not isinstance(packet, CPL1NumericPacket) for packet in source):
        raise TopicCacheIntegrityError("cache source must be non-empty CPL1 packets")
    packet_ids = tuple(packet.packet_sha256 for packet in source)
    if len(packet_ids) != len(set(packet_ids)):
        raise TopicCacheIntegrityError("cache source contains duplicate packet digest")
    schemas = {packet.shared_schema_sha256 for packet in source}
    if len(schemas) != 1:
        raise TopicCacheIntegrityError("cache source mixes shared schemas")
    # The raw append receipt stays order-sensitive and is used only to prove the
    # input was not rewritten.  Durable cache identity uses a sorted source cut.
    raw_append_before = append_only_sha256(source)
    source_cut = canonical_source_cut_sha256(source)
    if expected_source_cut_sha256 is not None:
        _sha(expected_source_cut_sha256, label="expected source cut digest")
        if source_cut != expected_source_cut_sha256:
            raise TopicCacheIntegrityError("source cut digest mismatch")

    grouped: dict[str, list[CPL1NumericPacket]] = {}
    for packet in source:
        grouped.setdefault(packet.edge_or_hyperedge_id, []).append(packet)
    shared_schema = next(iter(schemas))
    blocks = tuple(
        _make_block(
            topic_key,
            grouped[topic_key],
            shared_schema_sha256=shared_schema,
            source_cut_sha256=source_cut,
        )
        for topic_key in sorted(grouped)
    )
    manifest = _make_manifest(
        blocks,
        source_cut_sha256=source_cut,
        shared_schema_sha256=shared_schema,
        packet_count=len(source),
    )
    root = Path(cache_dir)
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        loaded = load_bprime_candidate_cache(root)
        if loaded.manifest != manifest or set(loaded.blocks) != set(blocks):
            raise TopicCacheIntegrityError("immutable cache manifest conflicts with source")
        return manifest
    for block in blocks:
        _write_once(root / "blocks" / f"{block.block_id}.json", block.canonical())
    _write_once(manifest_path, manifest.canonical())
    if append_only_sha256(source) != raw_append_before:
        raise TopicCacheIntegrityError("raw append source changed during cache build")
    return manifest


def verify_bprime_candidate_cache(
    cache_dir: str | Path,
    *,
    expected_source_cut_sha256: str | None = None,
) -> LoadedTopicCache:
    root = Path(cache_dir)
    manifest = _parse_manifest(_read_json(root / "manifest.json", label="manifest"))
    if expected_source_cut_sha256 is not None:
        _sha(expected_source_cut_sha256, label="expected source cut digest")
        if manifest.source_cut_sha256 != expected_source_cut_sha256:
            raise TopicCacheIntegrityError("source cut digest mismatch")
    blocks: list[TopicBlockV1] = []
    for block_id in manifest.block_ids:
        block = _parse_block(
            _read_json(root / "blocks" / f"{block_id}.json", label="topic block")
        )
        if block.block_id != block_id:
            raise TopicCacheIntegrityError("manifest block digest mismatch")
        if block.source_cut_sha256 != manifest.source_cut_sha256:
            raise TopicCacheIntegrityError("topic block source cut mismatch")
        if block.shared_schema_sha256 != manifest.shared_schema_sha256:
            raise TopicCacheIntegrityError("topic block shared schema mismatch")
        blocks.append(block)
    if sum(len(block.slow_w_updates) for block in blocks) != manifest.packet_count:
        raise TopicCacheIntegrityError("manifest packet_count mismatch")
    if len({block.topic_key for block in blocks}) != len(blocks):
        raise TopicCacheIntegrityError("manifest contains duplicate topic blocks")
    return LoadedTopicCache(manifest=manifest, blocks=tuple(blocks))


def load_bprime_candidate_cache(cache_dir: str | Path) -> LoadedTopicCache:
    return verify_bprime_candidate_cache(cache_dir)


def select_bprime_candidate_blocks(
    cache_dir: str | Path,
    *,
    edge_or_hyperedge_ids: Sequence[str],
) -> tuple[TopicBlockV1, ...]:
    """Select verified blocks by structural ID; no query is accepted or stored."""

    requested = tuple(edge_or_hyperedge_ids)
    if not requested or len(requested) != len(set(requested)):
        raise TopicCacheIntegrityError("structural block selection must be unique and non-empty")
    loaded = verify_bprime_candidate_cache(cache_dir)
    by_topic = {block.topic_key: block for block in loaded.blocks}
    unknown = [topic for topic in requested if topic not in by_topic]
    if unknown:
        raise TopicCacheIntegrityError(f"unknown topic block: {', '.join(unknown)}")
    return tuple(by_topic[topic] for topic in requested)
