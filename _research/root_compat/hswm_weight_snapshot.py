"""Immutable slow-weight snapshots and candidate deltas for HSWM P1.

This module is the deterministic domain core.  It performs no IO and never
mutates an active snapshot.  A candidate is bound to one exact base snapshot,
epoch, topology, learning policy, and eligibility provenance root.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Iterable, Mapping, Sequence

SNAPSHOT_SCHEMA_VERSION = "hswm-weight-snapshot/v1"
CANDIDATE_SCHEMA_VERSION = "hswm-weight-candidate/v1"
DELTA_SCHEMA_VERSION = "hswm-weight-delta/v1"
GENESIS_SHA256 = "0" * 64
_HEX = frozenset("0123456789abcdef")


class WeightContractError(ValueError):
    """A snapshot or candidate violates the canonical P1 weight contract."""


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise WeightContractError(f"value is not canonical JSON: {error}") from error


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise WeightContractError(f"{label} must be non-empty text")
    return value


def _sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _HEX for character in value)
    ):
        raise WeightContractError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _epoch(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise WeightContractError(f"{label} must be a non-negative integer")
    return value


def _potential(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WeightContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result > 0.0:
        raise WeightContractError(f"{label} must be finite and <= 0")
    return 0.0 if result == 0.0 else result


def _weights(
    values: Iterable["SlowWeightV1"], *, label: str
) -> tuple["SlowWeightV1", ...]:
    by_id: dict[str, SlowWeightV1] = {}
    for weight in values:
        if not isinstance(weight, SlowWeightV1):
            raise WeightContractError(f"{label} must contain SlowWeightV1")
        if weight.edge_id in by_id:
            raise WeightContractError(f"duplicate {label} edge_id {weight.edge_id}")
        by_id[weight.edge_id] = weight
    if not by_id:
        raise WeightContractError(f"{label} must be non-empty")
    return tuple(by_id[edge_id] for edge_id in sorted(by_id))


@dataclass(frozen=True, order=True)
class SlowWeightV1:
    """Durable macro-weight in the same max-zero domain as open HSWM weights."""

    edge_id: str
    log_salience: float

    def __post_init__(self) -> None:
        _text(self.edge_id, "edge_id")
        object.__setattr__(
            self, "log_salience", _potential(self.log_salience, "log_salience")
        )

    def canonical(self) -> dict[str, object]:
        return {"edge_id": self.edge_id, "log_salience": self.log_salience}


@dataclass(frozen=True, order=True)
class WeightDeltaV1:
    edge_id: str
    before_log_salience: float
    after_log_salience: float
    eligibility_tag_sha256: str
    schema_version: str = DELTA_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _text(self.edge_id, "edge_id")
        before = _potential(self.before_log_salience, "before_log_salience")
        after = _potential(self.after_log_salience, "after_log_salience")
        if before == after:
            raise WeightContractError("weight delta must change log_salience")
        _sha256(self.eligibility_tag_sha256, "eligibility_tag_sha256")
        if self.schema_version != DELTA_SCHEMA_VERSION:
            raise WeightContractError("unsupported weight delta schema")
        object.__setattr__(self, "before_log_salience", before)
        object.__setattr__(self, "after_log_salience", after)

    def canonical(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "edge_id": self.edge_id,
            "before_log_salience": self.before_log_salience,
            "after_log_salience": self.after_log_salience,
            "eligibility_tag_sha256": self.eligibility_tag_sha256,
        }


@dataclass(frozen=True)
class WeightSnapshotV1:
    snapshot_id: str
    epoch: int
    parent_snapshot_id: str
    topology_sha256: str
    weights: tuple[SlowWeightV1, ...]
    provenance_root_sha256: str
    schema_version: str = SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _sha256(self.snapshot_id, "snapshot_id")
        _epoch(self.epoch, "epoch")
        _sha256(self.parent_snapshot_id, "parent_snapshot_id")
        _sha256(self.topology_sha256, "topology_sha256")
        _sha256(self.provenance_root_sha256, "provenance_root_sha256")
        if self.schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise WeightContractError("unsupported weight snapshot schema")
        normalized = _weights(self.weights, label="weights")
        object.__setattr__(self, "weights", normalized)
        if self.snapshot_id != canonical_sha256(self.unsigned()):
            raise WeightContractError("snapshot_id does not match canonical snapshot")

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "epoch": self.epoch,
            "parent_snapshot_id": self.parent_snapshot_id,
            "topology_sha256": self.topology_sha256,
            "weights": [weight.canonical() for weight in self.weights],
            "provenance_root_sha256": self.provenance_root_sha256,
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "snapshot_id": self.snapshot_id}

    def weight_map(self) -> dict[str, float]:
        return {weight.edge_id: weight.log_salience for weight in self.weights}


@dataclass(frozen=True)
class WeightCandidateV1:
    candidate_id: str
    base_snapshot_id: str
    base_epoch: int
    topology_sha256: str
    deltas: tuple[WeightDeltaV1, ...]
    learning_policy_sha256: str
    provenance_root_sha256: str
    schema_version: str = CANDIDATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _sha256(self.candidate_id, "candidate_id")
        _sha256(self.base_snapshot_id, "base_snapshot_id")
        _epoch(self.base_epoch, "base_epoch")
        _sha256(self.topology_sha256, "topology_sha256")
        _sha256(self.learning_policy_sha256, "learning_policy_sha256")
        _sha256(self.provenance_root_sha256, "provenance_root_sha256")
        if self.schema_version != CANDIDATE_SCHEMA_VERSION:
            raise WeightContractError("unsupported weight candidate schema")
        by_id: dict[str, WeightDeltaV1] = {}
        for delta in self.deltas:
            if not isinstance(delta, WeightDeltaV1):
                raise WeightContractError("deltas must contain WeightDeltaV1")
            if delta.edge_id in by_id:
                raise WeightContractError(f"duplicate delta edge_id {delta.edge_id}")
            by_id[delta.edge_id] = delta
        if not by_id:
            raise WeightContractError("candidate must contain at least one delta")
        normalized = tuple(by_id[edge_id] for edge_id in sorted(by_id))
        object.__setattr__(self, "deltas", normalized)
        if self.candidate_id != canonical_sha256(self.unsigned()):
            raise WeightContractError("candidate_id does not match canonical candidate")

    def unsigned(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "base_snapshot_id": self.base_snapshot_id,
            "base_epoch": self.base_epoch,
            "topology_sha256": self.topology_sha256,
            "deltas": [delta.canonical() for delta in self.deltas],
            "learning_policy_sha256": self.learning_policy_sha256,
            "provenance_root_sha256": self.provenance_root_sha256,
        }

    def canonical(self) -> dict[str, object]:
        return {**self.unsigned(), "candidate_id": self.candidate_id}


def make_initial_snapshot(
    weights: Iterable[SlowWeightV1],
    *,
    topology_sha256: str,
    provenance_root_sha256: str,
) -> WeightSnapshotV1:
    normalized = _weights(weights, label="weights")
    unsigned = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "epoch": 0,
        "parent_snapshot_id": GENESIS_SHA256,
        "topology_sha256": _sha256(topology_sha256, "topology_sha256"),
        "weights": [weight.canonical() for weight in normalized],
        "provenance_root_sha256": _sha256(
            provenance_root_sha256, "provenance_root_sha256"
        ),
    }
    return WeightSnapshotV1(
        snapshot_id=canonical_sha256(unsigned),
        epoch=0,
        parent_snapshot_id=GENESIS_SHA256,
        topology_sha256=topology_sha256,
        weights=normalized,
        provenance_root_sha256=provenance_root_sha256,
    )


def make_weight_candidate(
    base: WeightSnapshotV1,
    deltas: Iterable[WeightDeltaV1],
    *,
    learning_policy_sha256: str,
    provenance_root_sha256: str,
) -> WeightCandidateV1:
    normalized = tuple(deltas)
    unsigned = {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "base_snapshot_id": base.snapshot_id,
        "base_epoch": base.epoch,
        "topology_sha256": base.topology_sha256,
        "deltas": [delta.canonical() for delta in sorted(normalized)],
        "learning_policy_sha256": _sha256(
            learning_policy_sha256, "learning_policy_sha256"
        ),
        "provenance_root_sha256": _sha256(
            provenance_root_sha256, "provenance_root_sha256"
        ),
    }
    return WeightCandidateV1(
        candidate_id=canonical_sha256(unsigned),
        base_snapshot_id=base.snapshot_id,
        base_epoch=base.epoch,
        topology_sha256=base.topology_sha256,
        deltas=normalized,
        learning_policy_sha256=learning_policy_sha256,
        provenance_root_sha256=provenance_root_sha256,
    )


def apply_candidate(
    base: WeightSnapshotV1, candidate: WeightCandidateV1
) -> WeightSnapshotV1:
    if (
        candidate.base_snapshot_id != base.snapshot_id
        or candidate.base_epoch != base.epoch
        or candidate.topology_sha256 != base.topology_sha256
    ):
        raise WeightContractError("candidate is not bound to the supplied base")
    values = base.weight_map()
    for delta in candidate.deltas:
        if delta.edge_id not in values:
            raise WeightContractError(f"delta addresses unknown edge {delta.edge_id}")
        if values[delta.edge_id] != delta.before_log_salience:
            raise WeightContractError(f"delta before-value mismatch for {delta.edge_id}")
        values[delta.edge_id] = delta.after_log_salience
    weights = tuple(SlowWeightV1(edge_id, values[edge_id]) for edge_id in sorted(values))
    unsigned = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "epoch": base.epoch + 1,
        "parent_snapshot_id": base.snapshot_id,
        "topology_sha256": base.topology_sha256,
        "weights": [weight.canonical() for weight in weights],
        "provenance_root_sha256": candidate.candidate_id,
    }
    return WeightSnapshotV1(
        snapshot_id=canonical_sha256(unsigned),
        epoch=base.epoch + 1,
        parent_snapshot_id=base.snapshot_id,
        topology_sha256=base.topology_sha256,
        weights=weights,
        provenance_root_sha256=candidate.candidate_id,
    )


def snapshot_from_mapping(value: Mapping[str, object]) -> WeightSnapshotV1:
    weights = tuple(
        SlowWeightV1(str(item["edge_id"]), float(item["log_salience"]))
        for item in value["weights"]  # type: ignore[index,union-attr]
    )
    return WeightSnapshotV1(
        snapshot_id=str(value["snapshot_id"]),
        epoch=int(value["epoch"]),
        parent_snapshot_id=str(value["parent_snapshot_id"]),
        topology_sha256=str(value["topology_sha256"]),
        weights=weights,
        provenance_root_sha256=str(value["provenance_root_sha256"]),
        schema_version=str(value["schema_version"]),
    )


def candidate_from_mapping(value: Mapping[str, object]) -> WeightCandidateV1:
    deltas = tuple(
        WeightDeltaV1(
            edge_id=str(item["edge_id"]),
            before_log_salience=float(item["before_log_salience"]),
            after_log_salience=float(item["after_log_salience"]),
            eligibility_tag_sha256=str(item["eligibility_tag_sha256"]),
            schema_version=str(item["schema_version"]),
        )
        for item in value["deltas"]  # type: ignore[index,union-attr]
    )
    return WeightCandidateV1(
        candidate_id=str(value["candidate_id"]),
        base_snapshot_id=str(value["base_snapshot_id"]),
        base_epoch=int(value["base_epoch"]),
        topology_sha256=str(value["topology_sha256"]),
        deltas=deltas,
        learning_policy_sha256=str(value["learning_policy_sha256"]),
        provenance_root_sha256=str(value["provenance_root_sha256"]),
        schema_version=str(value["schema_version"]),
    )


def parse_snapshot(raw: bytes) -> WeightSnapshotV1:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WeightContractError(f"invalid snapshot JSON: {error}") from error
    if not isinstance(value, Mapping):
        raise WeightContractError("snapshot JSON must be an object")
    return snapshot_from_mapping(value)


def parse_candidate(raw: bytes) -> WeightCandidateV1:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WeightContractError(f"invalid candidate JSON: {error}") from error
    if not isinstance(value, Mapping):
        raise WeightContractError("candidate JSON must be an object")
    return candidate_from_mapping(value)


__all__ = [
    "CANDIDATE_SCHEMA_VERSION",
    "DELTA_SCHEMA_VERSION",
    "GENESIS_SHA256",
    "SNAPSHOT_SCHEMA_VERSION",
    "SlowWeightV1",
    "WeightCandidateV1",
    "WeightContractError",
    "WeightDeltaV1",
    "WeightSnapshotV1",
    "apply_candidate",
    "candidate_from_mapping",
    "canonical_json_bytes",
    "canonical_sha256",
    "make_initial_snapshot",
    "make_weight_candidate",
    "parse_candidate",
    "parse_snapshot",
    "snapshot_from_mapping",
]
