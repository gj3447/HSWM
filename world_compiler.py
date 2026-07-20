"""Pure evidence-preserving compiler for ``WorldArtifactV1``.

``compile_world`` consumes only frozen source and observation records.  It
never fetches a source, invokes a model, reads a clock, or mutates an input.
Every failure is returned as a deterministically ordered typed rejection.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import math
import struct
from typing import TypeVar

from world_ir import (
    BuildManifestV1,
    CompileIssueV1,
    CompilePolicyV1,
    CompileRejectionV1,
    EmbeddingObservationV1,
    EntityV1,
    EvidenceUnitV1,
    FieldTargetV1,
    MentionObservationV1,
    MentionV1,
    ObservationBundleV1,
    RejectCode,
    SCHEMA_VERSION,
    CANONICALIZATION_VERSION,
    SourceBundleV1,
    SourceSnapshotV1,
    TextSelectorV1,
    WorldArtifactV1,
    canonical_json,
    content_id,
    entity_id,
    evidence_unit_id,
    field_target_id,
    sha256_text,
)


COMPILER_VERSION = "epwc-python/v1"
SUPPORTED_PROJECTIONS = frozenset({"paragraph-v1"})
_T = TypeVar("_T")


def _issue(code: RejectCode, path: str, subject_id: str, detail: str) -> CompileIssueV1:
    return CompileIssueV1(code=code, path=path, subject_id=subject_id, detail=detail)


def _reject(issues: list[CompileIssueV1]) -> CompileRejectionV1:
    ordered = tuple(sorted(issues, key=lambda x: (x.code.value, x.path, x.subject_id, x.detail)))
    return CompileRejectionV1(schema_version=SCHEMA_VERSION, issues=ordered)


def _dedupe(records: tuple[_T, ...], id_attr: str, path: str,
            issues: list[CompileIssueV1]) -> dict[str, _T]:
    variants: dict[str, list[_T]] = {}
    for record in records:
        rid = str(getattr(record, id_attr))
        unique = variants.setdefault(rid, [])
        if not any(previous == record for previous in unique):
            unique.append(record)
    out: dict[str, _T] = {}
    for rid, unique in variants.items():
        if len(unique) > 1:
            issues.append(_issue(
                RejectCode.DUPLICATE_ID_CONFLICT, path, rid,
                "same stable ID has a different payload",
            ))
        else:
            out[rid] = unique[0]
    return out


def _selector_issues(selector: TextSelectorV1, source: SourceSnapshotV1,
                     path: str, subject_id: str) -> list[CompileIssueV1]:
    issues: list[CompileIssueV1] = []
    if selector.start == selector.end or not selector.exact:
        issues.append(_issue(
            RejectCode.INVALID_SELECTOR_RANGE, path, subject_id,
            "mention selectors must bind a non-empty exact span",
        ))
        return issues
    if selector.start < 0 or selector.end < selector.start or selector.end > len(source.content):
        issues.append(_issue(
            RejectCode.INVALID_SELECTOR_RANGE, path, subject_id,
            f"selector [{selector.start},{selector.end}) outside source length {len(source.content)}",
        ))
        return issues
    if source.content[selector.start:selector.end] != selector.exact:
        issues.append(_issue(
            RejectCode.SELECTOR_QUOTE_MISMATCH, path, subject_id,
            "selector exact text does not match bound source",
        ))
    if selector.prefix:
        actual = source.content[max(0, selector.start - len(selector.prefix)):selector.start]
        if actual != selector.prefix:
            issues.append(_issue(
                RejectCode.SELECTOR_CONTEXT_MISMATCH, path, subject_id,
                "selector prefix does not match bound source",
            ))
    if selector.suffix:
        actual = source.content[selector.end:selector.end + len(selector.suffix)]
        if actual != selector.suffix:
            issues.append(_issue(
                RejectCode.SELECTOR_CONTEXT_MISMATCH, path, subject_id,
                "selector suffix does not match bound source",
            ))
    return issues


def _embedding_digest(vector: tuple[float, ...]) -> str:
    return sha256(struct.pack(f"<{len(vector)}d", *vector)).hexdigest()


def compile_world(
    sources: SourceBundleV1,
    observations: ObservationBundleV1,
    policy: CompilePolicyV1,
) -> WorldArtifactV1 | CompileRejectionV1:
    """Compile frozen evidence and observations into one immutable artifact."""
    issues: list[CompileIssueV1] = []
    if policy.projection not in SUPPORTED_PROJECTIONS:
        issues.append(_issue(
            RejectCode.SCHEMA_INCOMPATIBLE, "policy.projection", policy.policy_id,
            f"unsupported projection {policy.projection!r}; supported={sorted(SUPPORTED_PROJECTIONS)}",
        ))
    if policy.min_mention_document_frequency < 1:
        issues.append(_issue(
            RejectCode.SCHEMA_INCOMPATIBLE, "policy.min_mention_document_frequency",
            policy.policy_id, "minimum document frequency must be >= 1",
        ))

    source_by_id = _dedupe(sources.sources, "source_id", "sources", issues)
    for sid, source in source_by_id.items():
        if sha256_text(source.content) != source.content_sha256:
            issues.append(_issue(
                RejectCode.SOURCE_HASH_MISMATCH, "sources.content_sha256", sid,
                "content SHA-256 does not match UTF-8 source bytes",
            ))
        expected_source_id = content_id("src", {
            "locator": source.locator, "content_sha256": source.content_sha256,
        })
        if sid != expected_source_id:
            issues.append(_issue(
                RejectCode.SOURCE_HASH_MISMATCH, "sources.source_id", sid,
                "source stable ID does not match locator and content digest",
            ))
    if issues:
        return _reject(issues)

    canonical_sources = tuple(sorted(source_by_id.values(), key=lambda x: x.source_id))
    evidence_units = tuple(
        EvidenceUnitV1(
            unit_id=evidence_unit_id(source.source_id),
            source_id=source.source_id,
            unit_kind="document",
            ordinal=0,
            selector=TextSelectorV1(
                start=0, end=len(source.content), exact=source.content,
                normalization_policy_hash=policy.normalization_policy_hash,
            ),
            text_sha256=source.content_sha256,
        )
        for source in canonical_sources
    )
    evidence_by_source = {unit.source_id: unit for unit in evidence_units}

    mention_obs_by_id = _dedupe(observations.mentions, "observation_id", "observations.mentions", issues)
    for oid, observation in mention_obs_by_id.items():
        expected_observation_id = content_id("obs_mention", {
            "source_id": observation.source_id,
            "selector": observation.selector,
            "normalized_surface": observation.normalized_surface,
            "mention_kind": observation.mention_kind,
            "producer": observation.producer,
            "producer_version": observation.producer_version,
        })
        if oid != expected_observation_id:
            issues.append(_issue(
                RejectCode.OBSERVATION_HASH_MISMATCH, "observations.mentions.observation_id",
                oid, "mention stable ID does not match its payload",
            ))
        source = source_by_id.get(observation.source_id)
        if source is None:
            issues.append(_issue(
                RejectCode.DANGLING_REFERENCE, "observations.mentions.source_id", oid,
                f"unknown source {observation.source_id}",
            ))
            continue
        issues.extend(_selector_issues(
            observation.selector, source, "observations.mentions.selector", oid,
        ))
        if observation.output_sha256 != sha256_text(observation.selector.exact):
            issues.append(_issue(
                RejectCode.OBSERVATION_HASH_MISMATCH, "observations.mentions.output_sha256",
                oid, "mention output digest does not match selector exact text",
            ))
        if observation.selector.normalization_policy_hash != policy.normalization_policy_hash:
            issues.append(_issue(
                RejectCode.NORMALIZATION_POLICY_MISMATCH,
                "observations.mentions.selector.normalization_policy_hash", oid,
                "mention selector and compile policy use different normalization policies",
            ))
        if not observation.normalized_surface:
            issues.append(_issue(
                RejectCode.SCHEMA_INCOMPATIBLE, "observations.mentions.normalized_surface",
                oid, "normalized surface must not be empty",
            ))
    if issues:
        return _reject(issues)

    canonical_mention_obs = tuple(sorted(mention_obs_by_id.values(), key=lambda x: x.observation_id))
    title_labels = {o.normalized_surface for o in canonical_mention_obs if o.mention_kind == "title"}
    body_docs: dict[str, set[str]] = {}
    for observation in canonical_mention_obs:
        if observation.mention_kind != "title":
            body_docs.setdefault(observation.normalized_surface, set()).add(observation.source_id)
    bound_labels = title_labels | {
        label for label, docs in body_docs.items()
        if len(docs) >= policy.min_mention_document_frequency
    }
    entity_id_by_label = {
        label: entity_id(label, policy.normalization_policy_hash)
        for label in sorted(bound_labels)
    }

    mentions: list[MentionV1] = []
    mention_ids_by_label: dict[str, list[str]] = {}
    aliases_by_label: dict[str, set[str]] = {}
    for observation in canonical_mention_obs:
        unit = evidence_by_source[observation.source_id]
        mention_id = content_id("mention", {
            "observation_id": observation.observation_id,
            "evidence_unit_id": unit.unit_id,
        })
        bound_id = entity_id_by_label.get(observation.normalized_surface)
        mention = MentionV1(
            mention_id=mention_id,
            observation_id=observation.observation_id,
            source_id=observation.source_id,
            evidence_unit_id=unit.unit_id,
            selector=observation.selector,
            surface=observation.selector.exact,
            normalized_surface=observation.normalized_surface,
            mention_kind=observation.mention_kind,
            bound_entity_id=bound_id,
        )
        mentions.append(mention)
        if bound_id is not None:
            mention_ids_by_label.setdefault(observation.normalized_surface, []).append(mention_id)
            aliases_by_label.setdefault(observation.normalized_surface, set()).add(observation.selector.exact)

    entities = tuple(
        EntityV1(
            entity_id=entity_id_by_label[label], label=label,
            aliases=tuple(sorted(aliases_by_label.get(label, {label}))),
            mention_ids=tuple(sorted(mention_ids_by_label.get(label, ()))),
        )
        for label in sorted(bound_labels)
    )

    provisional_targets: list[FieldTargetV1] = []
    for source in canonical_sources:
        unit = evidence_by_source[source.source_id]
        member_ids = tuple(sorted({
            entity_id_by_label[o.normalized_surface]
            for o in canonical_mention_obs
            if o.source_id == source.source_id and o.normalized_surface in entity_id_by_label
        }))
        target_id = field_target_id(source.source_id, policy.projection)
        if not member_ids:
            issues.append(_issue(
                RejectCode.EMPTY_FIELD_TARGET, "field_targets.member_entity_ids", target_id,
                "projection target has no bound entity",
            ))
        provisional_targets.append(FieldTargetV1(
            target_id=target_id, target_kind="evidence_unit", source_id=source.source_id,
            text=source.content, evidence_unit_ids=(unit.unit_id,),
            member_entity_ids=member_ids, embedding_observation_id=None,
        ))
    if issues:
        return _reject(issues)

    target_by_id = {target.target_id: target for target in provisional_targets}
    entity_by_id = {entity.entity_id: entity for entity in entities}
    embedding_obs_by_id = _dedupe(
        observations.embeddings, "observation_id", "observations.embeddings", issues,
    )
    embedding_by_target: dict[str, EmbeddingObservationV1] = {}
    dimensions: set[int] = set()
    for oid, observation in embedding_obs_by_id.items():
        expected_observation_id = content_id("obs_embedding", {
            "target_kind": observation.target_kind,
            "target_id": observation.target_id,
            "producer": observation.producer,
            "model_revision": observation.model_revision,
            "config_sha256": observation.config_sha256,
            "input_sha256": observation.input_sha256,
            "dimension": len(observation.vector),
            "vector_sha256": observation.output_sha256,
        })
        if oid != expected_observation_id:
            issues.append(_issue(
                RejectCode.OBSERVATION_HASH_MISMATCH,
                "observations.embeddings.observation_id", oid,
                "embedding stable ID does not match its payload",
            ))
        if observation.target_kind == "entity":
            target_text = entity_by_id.get(observation.target_id)
            input_text = target_text.label if target_text is not None else None
        elif observation.target_kind == "field_target":
            target_text = target_by_id.get(observation.target_id)
            input_text = target_text.text if target_text is not None else None
        else:
            input_text = None
        if input_text is None:
            issues.append(_issue(
                RejectCode.DANGLING_REFERENCE, "observations.embeddings.target_id", oid,
                f"unknown {observation.target_kind} target {observation.target_id}",
            ))
            continue
        previous = embedding_by_target.get(observation.target_id)
        if previous is not None and previous != observation:
            issues.append(_issue(
                RejectCode.MULTIPLE_EMBEDDINGS, "observations.embeddings.target_id",
                observation.target_id, "more than one embedding observation targets the same record",
            ))
        else:
            embedding_by_target[observation.target_id] = observation
        if not observation.vector or any(not math.isfinite(x) for x in observation.vector):
            issues.append(_issue(
                RejectCode.NONFINITE_VECTOR, "observations.embeddings.vector", oid,
                "embedding must be non-empty and finite",
            ))
            continue
        dimensions.add(len(observation.vector))
        if observation.output_sha256 != _embedding_digest(observation.vector):
            issues.append(_issue(
                RejectCode.OBSERVATION_HASH_MISMATCH, "observations.embeddings.output_sha256",
                oid, "embedding output digest does not match canonical float64 bytes",
            ))
        if observation.input_sha256 != sha256_text(input_text):
            issues.append(_issue(
                RejectCode.OBSERVATION_HASH_MISMATCH, "observations.embeddings.input_sha256",
                oid, "embedding input digest does not match target text",
            ))
    if len(dimensions) > 1:
        issues.append(_issue(
            RejectCode.EMBEDDING_DIMENSION_MISMATCH, "observations.embeddings.vector",
            "embedding-bundle", f"multiple embedding dimensions: {sorted(dimensions)}",
        ))
    if issues:
        return _reject(issues)

    field_targets = tuple(sorted((
        replace(target, embedding_observation_id=(
            embedding_by_target[target.target_id].observation_id
            if target.target_id in embedding_by_target else None
        ))
        for target in provisional_targets
    ), key=lambda x: x.target_id))
    canonical_mentions = tuple(sorted(mentions, key=lambda x: x.mention_id))
    canonical_embeddings = tuple(sorted(embedding_obs_by_id.values(), key=lambda x: x.observation_id))
    policy_sha = sha256_text(canonical_json(policy))
    source_root = sha256_text(canonical_json(canonical_sources))
    observation_root = sha256_text(canonical_json({
        "mentions": canonical_mention_obs,
        "embeddings": canonical_embeddings,
    }))
    artifact_core = {
        "schema_version": SCHEMA_VERSION,
        "compiler_version": COMPILER_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "policy": policy,
        "sources": canonical_sources,
        "mention_observations": canonical_mention_obs,
        "evidence_units": evidence_units,
        "mentions": canonical_mentions,
        "entities": entities,
        "field_targets": field_targets,
        "embedding_observations": canonical_embeddings,
    }
    try:
        build_id = content_id("world", artifact_core)
    except (TypeError, ValueError) as exc:
        return _reject([_issue(
            RejectCode.CANONICALIZATION_ERROR, "artifact", "world", str(exc),
        )])
    stats = (
        ("sources", len(canonical_sources)),
        ("evidence_units", len(evidence_units)),
        ("mentions", len(canonical_mentions)),
        ("bound_mentions", sum(m.bound_entity_id is not None for m in canonical_mentions)),
        ("entities", len(entities)),
        ("field_targets", len(field_targets)),
        ("embedding_observations", len(canonical_embeddings)),
    )
    manifest = BuildManifestV1(
        schema_version=SCHEMA_VERSION,
        compiler_version=COMPILER_VERSION,
        canonicalization_version=CANONICALIZATION_VERSION,
        policy_sha256=policy_sha,
        source_root_sha256=source_root,
        observation_root_sha256=observation_root,
        projection=policy.projection,
        build_id=build_id,
        stats=stats,
    )
    return WorldArtifactV1(
        build_id=build_id,
        manifest=manifest,
        policy=policy,
        sources=canonical_sources,
        mention_observations=canonical_mention_obs,
        evidence_units=evidence_units,
        mentions=canonical_mentions,
        entities=entities,
        field_targets=field_targets,
        embedding_observations=canonical_embeddings,
    )


def verify_world_artifact(artifact: WorldArtifactV1) -> tuple[CompileIssueV1, ...]:
    """Recompile the artifact's attached preimages and verify every record."""
    rebuilt = compile_world(
        SourceBundleV1(artifact.sources),
        ObservationBundleV1(
            mentions=artifact.mention_observations,
            embeddings=artifact.embedding_observations,
        ),
        artifact.policy,
    )
    if isinstance(rebuilt, CompileRejectionV1):
        return rebuilt.issues
    issues: list[CompileIssueV1] = []
    if rebuilt.build_id != artifact.build_id or artifact.manifest.build_id != artifact.build_id:
        issues.append(_issue(
            RejectCode.CANONICALIZATION_ERROR, "artifact.build_id", artifact.build_id,
            f"recomputed build ID is {rebuilt.build_id}",
        ))
    if rebuilt != artifact:
        issues.append(_issue(
            RejectCode.CANONICALIZATION_ERROR, "artifact.records", artifact.build_id,
            "artifact records differ from deterministic recompilation",
        ))
    return tuple(sorted(issues, key=lambda x: (x.code.value, x.path, x.subject_id, x.detail)))
