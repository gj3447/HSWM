"""Lossless compatibility seam from legacy QA rows to ``WorldArtifactV1``.

The canonical artifact uses stable IDs and is invariant to input collection
order.  ``LegacyProjectionLayoutV1`` alone preserves the old first-seen dense
edge ordering; it is intentionally excluded from the artifact build ID.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from hypergraph import Hypergraph
from world_compiler import compile_world
import world_builder as wb
from world_ir import (
    CompileIssueV1,
    CompilePolicyV1,
    CompileRejectionV1,
    EmbeddingObservationV1,
    EvaluationQueryV1,
    EvaluationSuiteV1,
    ObservationBundleV1,
    RejectCode,
    SourceBundleV1,
    SourceSnapshotV1,
    TextSelectorV1,
    WorldArtifactV1,
    canonical_json,
    field_target_id,
    make_embedding_observation,
    make_mention_observation,
    make_source_snapshot,
    sha256_text,
)


LEGACY_POLICY = CompilePolicyV1()


@dataclass(frozen=True)
class LegacyProjectionLayoutV1:
    edge_ids_first_seen: tuple[str, ...]
    query_occurrence_ids: tuple[str, ...]


@dataclass(frozen=True)
class StableIdMap:
    entity_ids_by_dense: tuple[str, ...]
    target_ids_by_dense: tuple[str, ...]


@dataclass(frozen=True)
class LegacyCompileResult:
    artifact: WorldArtifactV1
    evaluation: EvaluationSuiteV1
    layout: LegacyProjectionLayoutV1
    world: wb.BuiltWorld
    stable_ids: StableIdMap


class LegacyCompileError(ValueError):
    def __init__(self, rejection: CompileRejectionV1):
        self.rejection = rejection
        summary = "; ".join(f"{x.code.value}:{x.path}" for x in rejection.issues)
        super().__init__(summary)


def _raise_issue(code: RejectCode, path: str, subject_id: str, detail: str) -> None:
    raise LegacyCompileError(CompileRejectionV1(
        schema_version="hswm-world-ir/v1",
        issues=(CompileIssueV1(code=code, path=path, subject_id=subject_id, detail=detail),),
    ))


def _selector(source: SourceSnapshotV1, start: int, end: int) -> TextSelectorV1:
    return TextSelectorV1(
        start=start,
        end=end,
        exact=source.content[start:end],
        prefix=source.content[max(0, start - 32):start],
        suffix=source.content[end:end + 32],
        normalization_policy_hash=LEGACY_POLICY.normalization_policy_hash,
    )


def _legacy_sources_and_mentions(rows: list[dict]):
    source_by_key: dict[tuple[str, str], SourceSnapshotV1] = {}
    first_seen_sources: list[SourceSnapshotV1] = []
    mentions = []
    for row in rows:
        for paragraph in row["paragraphs"]:
            title = paragraph["title"]
            text = paragraph["paragraph_text"]
            key = (title, text)
            if key in source_by_key:
                continue
            unit_text = f"{title} :: {text}"
            key_digest = sha256_text(canonical_json({"title": title, "paragraph_text": text}))
            source = make_source_snapshot(f"legacy://paragraph/{key_digest}", unit_text)
            source_by_key[key] = source
            first_seen_sources.append(source)

            title_selector = _selector(source, 0, len(title))
            mentions.append(make_mention_observation(
                source, title_selector, wb._norm_ent(title), "title",
                "legacy-title-anchor", "v1",
            ))
            body_offset = len(title) + len(" :: ")
            for match in wb._CAP_RE.finditer(text):
                surface = match.group(0)
                if len(surface) < 3:
                    continue
                normalized = wb._norm_ent(surface)
                if " " not in normalized and normalized in wb._MENTION_BLOCK:
                    continue
                mentions.append(make_mention_observation(
                    source,
                    _selector(source, body_offset + match.start(), body_offset + match.end()),
                    normalized,
                    "body",
                    "legacy-capitalization-heuristic",
                    "v1",
                ))
    return source_by_key, first_seen_sources, tuple(mentions)


def _require_artifact(result: WorldArtifactV1 | CompileRejectionV1) -> WorldArtifactV1:
    if isinstance(result, CompileRejectionV1):
        raise LegacyCompileError(result)
    return result


def _validate_embedding_matrix(value, expected_rows: int, path: str) -> np.ndarray:
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        _raise_issue(
            RejectCode.EMBEDDING_DIMENSION_MISMATCH, path, "legacy-embedder",
            f"embedder output is not a rectangular numeric matrix: {exc}",
        )
    if array.ndim != 2 or array.shape[0] != expected_rows or array.shape[1] == 0:
        _raise_issue(
            RejectCode.EMBEDDING_DIMENSION_MISMATCH, path, "legacy-embedder",
            f"expected ({expected_rows}, d>0), got {array.shape}",
        )
    if not np.isfinite(array).all():
        _raise_issue(
            RejectCode.NONFINITE_VECTOR, path, "legacy-embedder",
            "embedder returned NaN or infinity",
        )
    return array


def _embedding_observations(artifact: WorldArtifactV1, target_order: tuple[str, ...],
                            node_vectors: np.ndarray, target_vectors: np.ndarray,
                            injected: bool) -> tuple[EmbeddingObservationV1, ...]:
    producer = "legacy.injected_embed_fn" if injected else "doc_builder.hash_embed"
    model_revision = "unversioned" if injected else "hash-embed-v1"
    config_sha = sha256_text(canonical_json({
        "adapter": "legacy-paragraph-v1",
        "producer": producer,
        "dimension": int(node_vectors.shape[1]),
    }))
    targets = {target.target_id: target for target in artifact.field_targets}
    out: list[EmbeddingObservationV1] = []
    for entity, vector in zip(artifact.entities, node_vectors, strict=True):
        out.append(make_embedding_observation(
            "entity", entity.entity_id, entity.label,
            tuple(float(x) for x in vector), producer, model_revision, config_sha,
        ))
    for target_id, vector in zip(target_order, target_vectors, strict=True):
        target = targets[target_id]
        out.append(make_embedding_observation(
            "field_target", target.target_id, target.text,
            tuple(float(x) for x in vector), producer, model_revision, config_sha,
        ))
    return tuple(out)


def _evaluation_suite(rows: list[dict], source_by_key: dict[tuple[str, str], SourceSnapshotV1],
                      target_rank: dict[str, int]) -> EvaluationSuiteV1:
    queries: list[EvaluationQueryV1] = []
    for index, row in enumerate(rows):
        gold_ids = {
            field_target_id(source_by_key[(p["title"], p["paragraph_text"])].source_id,
                            LEGACY_POLICY.projection)
            for p in row["paragraphs"] if p.get("is_supporting")
        }
        queries.append(EvaluationQueryV1(
            occurrence_id=f"legacy-query:{index}",
            qid=str(row.get("id", index)),
            question=row["question"],
            answer=str(row.get("answer", "")),
            hop=wb.parse_hop(row),
            gold_target_ids=tuple(sorted(gold_ids, key=target_rank.__getitem__)),
        ))
    return EvaluationSuiteV1(tuple(queries))


def compile_legacy_rows(rows: list[dict], embed_fn: Callable | None = None,
                        dim: int = wb.DEFAULT_DIM) -> LegacyCompileResult:
    """Compile legacy normalized rows without leaking evaluation labels.

    The external embedder protocol is preserved exactly: one call over sorted
    entity labels followed by one call over first-seen unit texts.
    """
    source_by_key, first_seen_sources, mention_observations = _legacy_sources_and_mentions(rows)
    if not first_seen_sources:
        _raise_issue(RejectCode.SCHEMA_INCOMPATIBLE, "rows", "legacy-input",
                     "at least one paragraph is required")
    observations = ObservationBundleV1(mentions=mention_observations)
    skeleton = _require_artifact(compile_world(
        SourceBundleV1(tuple(first_seen_sources)), observations, LEGACY_POLICY,
    ))
    target_order = tuple(
        field_target_id(source.source_id, LEGACY_POLICY.projection)
        for source in first_seen_sources
    )
    target_by_id = {target.target_id: target for target in skeleton.field_targets}
    entity_labels = [entity.label for entity in skeleton.entities]
    unit_texts = [target_by_id[target_id].text for target_id in target_order]
    embed = embed_fn if embed_fn is not None else (lambda texts: wb.hash_embed(texts, dim))
    node_vectors = _validate_embedding_matrix(embed(entity_labels), len(entity_labels),
                                              "embeddings.entities")
    target_vectors = _validate_embedding_matrix(embed(unit_texts), len(unit_texts),
                                                "embeddings.field_targets")
    if node_vectors.shape[1] != target_vectors.shape[1]:
        _raise_issue(
            RejectCode.EMBEDDING_DIMENSION_MISMATCH, "embeddings", "legacy-embedder",
            f"entity dim {node_vectors.shape[1]} != field-target dim {target_vectors.shape[1]}",
        )
    embeddings = _embedding_observations(
        skeleton, target_order, node_vectors, target_vectors, injected=embed_fn is not None,
    )
    artifact = _require_artifact(compile_world(
        SourceBundleV1(tuple(first_seen_sources)),
        ObservationBundleV1(mentions=mention_observations, embeddings=embeddings),
        LEGACY_POLICY,
    ))
    target_rank = {target_id: rank for rank, target_id in enumerate(target_order)}
    evaluation = _evaluation_suite(rows, source_by_key, target_rank)
    layout = LegacyProjectionLayoutV1(
        edge_ids_first_seen=target_order,
        query_occurrence_ids=tuple(query.occurrence_id for query in evaluation.queries),
    )
    world, stable_ids = to_legacy_built_world(artifact, evaluation, layout=layout)
    return LegacyCompileResult(
        artifact=artifact, evaluation=evaluation, layout=layout,
        world=world, stable_ids=stable_ids,
    )


def to_legacy_built_world(
    artifact: WorldArtifactV1,
    suite: EvaluationSuiteV1,
    *,
    layout: LegacyProjectionLayoutV1 | None = None,
    projection: str = "paragraph-v1",
) -> tuple[wb.BuiltWorld, StableIdMap]:
    """Project stable IR records back to the positional ``BuiltWorld`` DTO."""
    if artifact.manifest.projection != projection:
        _raise_issue(RejectCode.SCHEMA_INCOMPATIBLE, "projection", artifact.build_id,
                     f"artifact projection {artifact.manifest.projection!r} != {projection!r}")
    target_by_id = {target.target_id: target for target in artifact.field_targets}
    if not target_by_id or not artifact.entities:
        _raise_issue(RejectCode.SCHEMA_INCOMPATIBLE, "artifact", artifact.build_id,
                     "legacy projection requires at least one entity and field target")
    target_ids = (layout.edge_ids_first_seen if layout is not None
                  else tuple(sorted(target_by_id)))
    if set(target_ids) != set(target_by_id) or len(target_ids) != len(target_by_id):
        _raise_issue(RejectCode.DANGLING_REFERENCE, "layout.edge_ids_first_seen",
                     artifact.build_id, "layout is not a bijection over field targets")

    entities = tuple(sorted(artifact.entities, key=lambda entity: entity.label))
    entity_ids = tuple(entity.entity_id for entity in entities)
    entity_dense = {entity_id: index for index, entity_id in enumerate(entity_ids)}
    embeddings = {observation.target_id: observation for observation in artifact.embedding_observations}
    missing = [stable_id for stable_id in entity_ids + target_ids if stable_id not in embeddings]
    if missing:
        _raise_issue(RejectCode.DANGLING_REFERENCE, "embedding_observations",
                     artifact.build_id, f"missing embeddings for {missing[:3]}")
    node_emb = np.asarray([embeddings[stable_id].vector for stable_id in entity_ids], dtype=np.float64)
    unit_emb = np.asarray([embeddings[stable_id].vector for stable_id in target_ids], dtype=np.float64)
    members = [
        np.asarray(sorted(entity_dense[entity_id] for entity_id in target_by_id[target_id].member_entity_ids),
                   dtype=np.int64)
        for target_id in target_ids
    ]
    hypergraph = Hypergraph(
        node_emb=node_emb,
        members=members,
        edge_freq=np.ones(len(target_ids)),
        edge_recency=np.zeros(len(target_ids)),
    )
    hypergraph.unit_emb = unit_emb  # type: ignore[attr-defined]

    target_dense = {target_id: index for index, target_id in enumerate(target_ids)}
    query_by_occurrence = {query.occurrence_id: query for query in suite.queries}
    occurrence_order = (layout.query_occurrence_ids if layout is not None
                        else tuple(query.occurrence_id for query in suite.queries))
    if set(occurrence_order) != set(query_by_occurrence) or len(occurrence_order) != len(query_by_occurrence):
        _raise_issue(RejectCode.DANGLING_REFERENCE, "layout.query_occurrence_ids",
                     artifact.build_id, "layout is not a bijection over evaluation queries")
    unknown_gold = sorted({
        target_id
        for query in suite.queries
        for target_id in query.gold_target_ids
        if target_id not in target_dense
    })
    if unknown_gold:
        _raise_issue(RejectCode.DANGLING_REFERENCE, "evaluation.gold_target_ids",
                     artifact.build_id, f"unknown gold targets {unknown_gold[:3]}")
    queries = [
        wb.WorldQuery(
            qid=query_by_occurrence[occurrence_id].qid,
            question=query_by_occurrence[occurrence_id].question,
            answer=query_by_occurrence[occurrence_id].answer,
            hop=query_by_occurrence[occurrence_id].hop,
            gold=np.asarray(sorted(
                target_dense[target_id]
                for target_id in query_by_occurrence[occurrence_id].gold_target_ids
            ), dtype=np.int64),
        )
        for occurrence_id in occurrence_order
    ]

    arity = np.asarray([member.size for member in members])
    degree = np.bincount(np.concatenate(members), minlength=len(entities))
    hop_counts: dict[int, int] = {}
    for query in queries:
        hop_counts[query.hop] = hop_counts.get(query.hop, 0) + 1
    unbound_body = {
        (mention.source_id, mention.normalized_surface)
        for mention in artifact.mentions
        if mention.mention_kind == "body" and mention.bound_entity_id is None
    }
    producers = {observation.producer for observation in artifact.embedding_observations}
    embedder_label = ("hash_embed STAND-IN" if producers == {"doc_builder.hash_embed"}
                      else "injected")
    stats = {
        "n_edges": len(target_ids), "n_nodes": len(entities), "nnz": int(arity.sum()),
        "arity": {"mean": round(float(arity.mean()), 2), "p50": int(np.median(arity)),
                  "p90": int(np.percentile(arity, 90)), "max": int(arity.max())},
        "node_degree": {"mean": round(float(degree.mean()), 2),
                        "p90": int(np.percentile(degree, 90)), "max": int(degree.max())},
        "top_hubs": [entities[i].label for i in np.argsort(-degree)[:5]],
        "density_mean_deg_over_M": round(float(degree.mean()) / max(len(target_ids), 1), 4),
        "queries_per_hop": dict(sorted(hop_counts.items())),
        "gold_recall_structural": 1.0,
        "mention_misses_df_gate": len(unbound_body),
        "embedder": embedder_label,
    }
    world = wb.BuiltWorld(
        hg=hypergraph,
        entities=[entity.label for entity in entities],
        unit_texts=[target_by_id[target_id].text for target_id in target_ids],
        queries=queries,
        stats=stats,
    )
    return world, StableIdMap(entity_ids_by_dense=entity_ids, target_ids_by_dense=target_ids)
