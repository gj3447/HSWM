"""Versioned immutable records for the HSWM evidence-preserving world IR.

The IR is deliberately smaller than RDF/OWL and deliberately richer than the
legacy ``Hypergraph`` projection.  It preserves exact source evidence and
stable semantic identities; dense numpy indices belong to adapters, never to
the durable artifact.

This module contains data only plus deterministic hashing helpers.  It performs
no filesystem, network, model, clock, or random operation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import StrEnum
from hashlib import sha256
import json
import math
import struct
from typing import Any


SCHEMA_VERSION = "hswm-world-ir/v1"
CANONICALIZATION_VERSION = "json-sort-utf8-v1"


class RejectCode(StrEnum):
    SCHEMA_INCOMPATIBLE = "schema_incompatible"
    DUPLICATE_ID_CONFLICT = "duplicate_id_conflict"
    SOURCE_HASH_MISMATCH = "source_hash_mismatch"
    INVALID_SELECTOR_RANGE = "invalid_selector_range"
    SELECTOR_QUOTE_MISMATCH = "selector_quote_mismatch"
    SELECTOR_CONTEXT_MISMATCH = "selector_context_mismatch"
    OBSERVATION_HASH_MISMATCH = "observation_hash_mismatch"
    NORMALIZATION_POLICY_MISMATCH = "normalization_policy_mismatch"
    DANGLING_REFERENCE = "dangling_reference"
    EMPTY_FIELD_TARGET = "empty_field_target"
    MULTIPLE_EMBEDDINGS = "multiple_embeddings"
    EMBEDDING_DIMENSION_MISMATCH = "embedding_dimension_mismatch"
    NONFINITE_VECTOR = "nonfinite_vector"
    EVALUATION_LABEL_LEAKAGE = "evaluation_label_leakage"
    CANONICALIZATION_ERROR = "canonicalization_error"


def sha256_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _canonical_value(value: Any) -> Any:
    """Convert records to the repository's versioned canonical JSON domain.

    This is an intentionally narrow deterministic profile, not a claim of full
    RFC 8785 conformance.  The profile rejects non-finite floats and records its
    own version in every build manifest.
    """
    if is_dataclass(value):
        return _canonical_value(asdict(value))
    if isinstance(value, dict):
        return {str(k): _canonical_value(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical JSON forbids non-finite floats")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _canonical_value(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def content_id(kind: str, payload: Any) -> str:
    digest = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"hswm:{kind}:v1:{digest}"


@dataclass(frozen=True)
class TextSelectorV1:
    start: int
    end: int
    exact: str
    prefix: str = ""
    suffix: str = ""
    normalization_policy_hash: str = "identity-v1"


@dataclass(frozen=True)
class SourceSnapshotV1:
    source_id: str
    locator: str
    media_type: str
    content: str
    content_sha256: str


@dataclass(frozen=True)
class SourceBundleV1:
    sources: tuple[SourceSnapshotV1, ...]


@dataclass(frozen=True)
class MentionObservationV1:
    observation_id: str
    source_id: str
    selector: TextSelectorV1
    normalized_surface: str
    mention_kind: str
    producer: str
    producer_version: str
    output_sha256: str


@dataclass(frozen=True)
class EmbeddingObservationV1:
    observation_id: str
    target_kind: str
    target_id: str
    producer: str
    model_revision: str
    config_sha256: str
    input_sha256: str
    output_sha256: str
    vector: tuple[float, ...]


@dataclass(frozen=True)
class ObservationBundleV1:
    mentions: tuple[MentionObservationV1, ...] = ()
    embeddings: tuple[EmbeddingObservationV1, ...] = ()


@dataclass(frozen=True)
class CompilePolicyV1:
    policy_id: str = "legacy-paragraph-policy-v1"
    min_mention_document_frequency: int = 2
    normalization_policy_hash: str = "legacy-normalization-v1"
    projection: str = "paragraph-v1"


@dataclass(frozen=True)
class EvidenceUnitV1:
    unit_id: str
    source_id: str
    unit_kind: str
    ordinal: int
    selector: TextSelectorV1
    text_sha256: str


@dataclass(frozen=True)
class MentionV1:
    mention_id: str
    observation_id: str
    source_id: str
    evidence_unit_id: str
    selector: TextSelectorV1
    surface: str
    normalized_surface: str
    mention_kind: str
    bound_entity_id: str | None


@dataclass(frozen=True)
class EntityV1:
    entity_id: str
    label: str
    aliases: tuple[str, ...]
    mention_ids: tuple[str, ...]


@dataclass(frozen=True)
class FieldTargetV1:
    target_id: str
    target_kind: str
    source_id: str
    text: str
    evidence_unit_ids: tuple[str, ...]
    member_entity_ids: tuple[str, ...]
    embedding_observation_id: str | None


@dataclass(frozen=True)
class BuildManifestV1:
    schema_version: str
    compiler_version: str
    canonicalization_version: str
    policy_sha256: str
    source_root_sha256: str
    observation_root_sha256: str
    projection: str
    build_id: str
    stats: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class WorldArtifactV1:
    build_id: str
    manifest: BuildManifestV1
    policy: CompilePolicyV1
    sources: tuple[SourceSnapshotV1, ...]
    mention_observations: tuple[MentionObservationV1, ...]
    evidence_units: tuple[EvidenceUnitV1, ...]
    mentions: tuple[MentionV1, ...]
    entities: tuple[EntityV1, ...]
    field_targets: tuple[FieldTargetV1, ...]
    embedding_observations: tuple[EmbeddingObservationV1, ...]


@dataclass(frozen=True)
class EvaluationQueryV1:
    occurrence_id: str
    qid: str
    question: str
    answer: str
    hop: int
    gold_target_ids: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationSuiteV1:
    queries: tuple[EvaluationQueryV1, ...]


@dataclass(frozen=True)
class CompileIssueV1:
    code: RejectCode
    path: str
    subject_id: str
    detail: str


@dataclass(frozen=True)
class CompileRejectionV1:
    schema_version: str
    issues: tuple[CompileIssueV1, ...]


def make_source_snapshot(locator: str, content: str,
                         media_type: str = "text/plain") -> SourceSnapshotV1:
    digest = sha256_text(content)
    source_id = content_id("src", {"locator": locator, "content_sha256": digest})
    return SourceSnapshotV1(source_id=source_id, locator=locator,
                            media_type=media_type, content=content,
                            content_sha256=digest)


def evidence_unit_id(source_id: str) -> str:
    return content_id("evu", {"source_id": source_id, "kind": "document", "ordinal": 0})


def field_target_id(source_id: str, projection: str = "paragraph-v1") -> str:
    return content_id("tgt", {"source_id": source_id, "projection": projection})


def entity_id(label: str, normalization_policy_hash: str) -> str:
    return content_id("ent", {"label": label, "normalization_policy_hash": normalization_policy_hash})


def make_mention_observation(source: SourceSnapshotV1, selector: TextSelectorV1,
                             normalized_surface: str, mention_kind: str,
                             producer: str, producer_version: str) -> MentionObservationV1:
    payload = {
        "source_id": source.source_id,
        "selector": selector,
        "normalized_surface": normalized_surface,
        "mention_kind": mention_kind,
        "producer": producer,
        "producer_version": producer_version,
    }
    return MentionObservationV1(
        observation_id=content_id("obs_mention", payload),
        source_id=source.source_id,
        selector=selector,
        normalized_surface=normalized_surface,
        mention_kind=mention_kind,
        producer=producer,
        producer_version=producer_version,
        output_sha256=sha256_text(selector.exact),
    )


def make_embedding_observation(target_kind: str, target_id: str,
                               input_text: str, vector: tuple[float, ...],
                               producer: str, model_revision: str,
                               config_sha256: str) -> EmbeddingObservationV1:
    if not vector or any(not math.isfinite(v) for v in vector):
        raise ValueError("embedding vector must be non-empty and finite")
    vector_bytes = struct.pack(f"<{len(vector)}d", *vector)
    vector_sha256 = sha256(vector_bytes).hexdigest()
    payload = {
        "target_kind": target_kind,
        "target_id": target_id,
        "producer": producer,
        "model_revision": model_revision,
        "config_sha256": config_sha256,
        "input_sha256": sha256_text(input_text),
        "dimension": len(vector),
        "vector_sha256": vector_sha256,
    }
    return EmbeddingObservationV1(
        observation_id=content_id("obs_embedding", payload),
        target_kind=target_kind,
        target_id=target_id,
        producer=producer,
        model_revision=model_revision,
        config_sha256=config_sha256,
        input_sha256=sha256_text(input_text),
        output_sha256=vector_sha256,
        vector=vector,
    )
