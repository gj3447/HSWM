"""Development-only QKV probe over evidence-bound B1 title links.

This module tests a deliberately small alternative to score diffusion:

``Q``
    the current, unit-normalized query vector;
``K``
    the fixed paragraph vectors used by the static cosine baseline; and
``V``
    paragraph vectors read only through outgoing, exact-title evidence arcs.

At each layer, the current query attends to frontier keys, each source's mass
is divided over its accepted outgoing evidence arcs, and the referenced target
vectors form one value read.  The next query is
``normalize(query + gamma * value_read)``.  K=1 and K=2 therefore differ by a
real second evidence-bound read rather than by repeated score smoothing.

The scorer API accepts vectors, a frozen B1 graph, and a policy only.  It has no
question, answer, support, hop, or gold-label parameter.  Evaluation labels
exist solely in the development runner after scoring.  The loader likewise has
no fresh input: paths containing ``fresh`` are rejected before they are read,
and every loaded segment must declare ``split == "development"``.

This is an exploratory development probe, not a deployment certificate.  The
current historical embedding NPZ may be a superset of development IDs; joins
are by stable identity and exact text hash, never by array position.  Extra
records are ignored and reported.  A query whose exact preimage does not match
is excluded fail-closed from metrics.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import argparse
import json
import math
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

import composition as comp
import h3_b3_falsifier as h3
import h3_b3_prepare as prep
import metrics
import relation_eval as reval
import title_anchor_builder as tab
from world_ir import canonical_json


SCHEMA_VERSION = "hswm-qkv-b1-probe/v1"
RECEIPT_SCHEMA_VERSION = "hswm-qkv-b1-receipt/v1"
DEVELOPMENT_REPORT_SCHEMA_VERSION = "hswm-qkv-b1-development-report/v1"
K_METRIC = 10


class QKVB1IntegrityError(ValueError):
    """A vector, graph, segment, or stable-ID join violates the probe contract."""


@dataclass(frozen=True)
class QKVB1PolicyV1:
    """Frozen knobs for one forward, evidence-bound value-read arm."""

    seed_k: int = 10
    hops: int = 1
    gamma: float = 0.1
    temperature: float = 1.0
    max_fanout: int = 16

    def __post_init__(self) -> None:
        if self.seed_k < 1:
            raise ValueError("seed_k must be positive")
        if self.hops not in {1, 2}:
            raise ValueError("hops must be K1 or K2")
        if not math.isfinite(self.gamma) or self.gamma < 0:
            raise ValueError("gamma must be finite and non-negative")
        if not math.isfinite(self.temperature) or self.temperature <= 0:
            raise ValueError("temperature must be finite and positive")
        if self.max_fanout < 1:
            raise ValueError("max_fanout must be positive")


@dataclass(frozen=True)
class ValueArcReceiptV1:
    """One exact evidence arc that contributed to a layer value read."""

    depth: int
    arc_index: int
    source_target: int
    target_target: int
    source_id: str
    selector_start: int
    selector_end: int
    selector_exact: str
    anchor_label: str
    source_attention: float
    edge_weight: float


@dataclass(frozen=True)
class QKVLayerReceiptV1:
    depth: int
    query_before_sha256: str
    query_after_sha256: str
    value_read_sha256: str
    value_read_norm: float
    frontier_targets: tuple[int, ...]
    reached_targets: tuple[int, ...]
    skipped_fanout_sources: tuple[int, ...]
    arcs: tuple[ValueArcReceiptV1, ...]


@dataclass(frozen=True)
class QKVB1ReceiptV1:
    schema_version: str
    topology_sha256: str
    policy: QKVB1PolicyV1
    seed_targets: tuple[int, ...]
    static_score_sha256: str
    final_score_sha256: str
    layers: tuple[QKVLayerReceiptV1, ...]
    applied: bool
    trip_reason: str | None
    evaluator_labels_seen: int
    receipt_sha256: str
    research_only: bool = True


@dataclass(frozen=True)
class DevelopmentQueryV1:
    """Evaluator-owned row; never accepted by :func:`score_qkv_b1`."""

    qid: str
    query_vector: np.ndarray
    gold_ordinals: tuple[int, ...]
    hop: int


@dataclass(frozen=True)
class DevelopmentDatasetV1:
    dataset: str
    segment_path: str
    segment_sha256: str
    embedding_path: str
    embedding_sha256: str
    target_ids: tuple[str, ...]
    graph: comp.CompositionGraphV1
    key_vectors: np.ndarray
    value_vectors: np.ndarray
    queries: tuple[DevelopmentQueryV1, ...]
    dropped_query_ids: tuple[str, ...]
    unused_embedding_records: int
    builder_stats: Mapping[str, Any]


def _file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(value, dtype="<f8"))
    return sha256(array.tobytes(order="C")).hexdigest()


def _unit_vector(value: np.ndarray, *, label: str) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float64)
    if vector.ndim != 1 or not vector.size or not np.isfinite(vector).all():
        raise QKVB1IntegrityError(f"{label} must be one finite non-empty vector")
    norm = float(np.linalg.norm(vector))
    if abs(norm - 1.0) > 1e-5:
        raise QKVB1IntegrityError(f"{label} must be L2-normalized")
    return vector


def _unit_matrix(value: np.ndarray, *, label: str) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.ndim != 2 or not matrix.shape[0] or not matrix.shape[1]:
        raise QKVB1IntegrityError(f"{label} must be a non-empty matrix")
    if not np.isfinite(matrix).all():
        raise QKVB1IntegrityError(f"{label} contains a non-finite value")
    errors = np.abs(np.linalg.norm(matrix, axis=1) - 1.0)
    if float(errors.max()) > 1e-5:
        raise QKVB1IntegrityError(f"{label} rows must be L2-normalized")
    return matrix


def _softmax(logits: np.ndarray) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float64)
    shifted = values - float(values.max())
    weights = np.exp(shifted)
    return weights / float(weights.sum())


def _receipt_digest(
    *, topology_sha256: str, policy: QKVB1PolicyV1,
    seed_targets: tuple[int, ...], static_score_sha256: str,
    final_score_sha256: str, layers: tuple[QKVLayerReceiptV1, ...],
    applied: bool, trip_reason: str | None,
) -> str:
    payload = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "topology_sha256": topology_sha256,
        "policy": asdict(policy),
        "seed_targets": seed_targets,
        "static_score_sha256": static_score_sha256,
        "final_score_sha256": final_score_sha256,
        "layers": tuple(asdict(layer) for layer in layers),
        "applied": applied,
        "trip_reason": trip_reason,
        "evaluator_labels_seen": 0,
        "research_only": True,
    }
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _receipt(
    graph: comp.CompositionGraphV1, policy: QKVB1PolicyV1,
    seeds: tuple[int, ...], static: np.ndarray, final: np.ndarray,
    layers: tuple[QKVLayerReceiptV1, ...], *, trip_reason: str | None,
) -> QKVB1ReceiptV1:
    static_digest = _array_sha256(static)
    final_digest = _array_sha256(final)
    applied = bool(layers)
    receipt_digest = _receipt_digest(
        topology_sha256=graph.topology_sha256, policy=policy,
        seed_targets=seeds, static_score_sha256=static_digest,
        final_score_sha256=final_digest, layers=layers, applied=applied,
        trip_reason=trip_reason,
    )
    return QKVB1ReceiptV1(
        schema_version=RECEIPT_SCHEMA_VERSION,
        topology_sha256=graph.topology_sha256, policy=policy,
        seed_targets=seeds, static_score_sha256=static_digest,
        final_score_sha256=final_digest, layers=layers, applied=applied,
        trip_reason=trip_reason, evaluator_labels_seen=0,
        receipt_sha256=receipt_digest,
    )


def score_qkv_b1(
    query_vector: np.ndarray,
    key_vectors: np.ndarray,
    graph: comp.CompositionGraphV1,
    policy: QKVB1PolicyV1,
    *,
    value_vectors: np.ndarray | None,
) -> tuple[np.ndarray, QKVB1ReceiptV1]:
    """Score one query without accepting any evaluator-side metadata.

    ``gamma == 0`` and ``value_vectors is None`` are early static floors.  In
    both cases the returned score array is a byte-identical copy of the static
    ``K @ Q`` array and no evidence layer is reported as applied.
    """

    query = _unit_vector(query_vector, label="query_vector")
    keys = _unit_matrix(key_vectors, label="key_vectors")
    if keys.shape[0] != graph.n_targets:
        raise QKVB1IntegrityError("key rows and graph targets are not aligned")
    static = keys @ query
    seed_k = min(policy.seed_k, graph.n_targets)
    seeds = tuple(int(item) for item in np.argsort(-static, kind="stable")[:seed_k])
    if policy.gamma == 0:
        final = static.copy()
        return final, _receipt(
            graph, policy, seeds, static, final, (), trip_reason="gamma=0 static floor",
        )
    if value_vectors is None:
        final = static.copy()
        return final, _receipt(
            graph, policy, seeds, static, final, (), trip_reason="no value vectors",
        )
    values = _unit_matrix(value_vectors, label="value_vectors")
    if values.shape != keys.shape:
        raise QKVB1IntegrityError("value vectors must match the key matrix shape")

    outgoing: list[list[tuple[int, comp.EvidenceArcV1]]] = [
        [] for _ in range(graph.n_targets)
    ]
    for arc_index, arc in enumerate(graph.arcs):
        if (not arc.source_id or not arc.selector_exact or
                arc.selector_end - arc.selector_start != len(arc.selector_exact)):
            raise QKVB1IntegrityError("graph contains a non-evidenced outgoing arc")
        outgoing[arc.source_target].append((arc_index, arc))

    current_query = query.copy()
    frontier = seeds
    layer_receipts: list[QKVLayerReceiptV1] = []
    trip_reason: str | None = None
    for depth in range(1, policy.hops + 1):
        allowed: list[tuple[int, tuple[tuple[int, comp.EvidenceArcV1], ...]]] = []
        skipped: list[int] = []
        for source in sorted(set(frontier)):
            row = tuple(outgoing[source])
            if not row:
                continue
            if len(row) > policy.max_fanout:
                skipped.append(source)
                continue
            allowed.append((source, row))
        if skipped:
            # Safety is query-atomic.  A partial read from only the low-fanout
            # part of a frontier would silently change the treatment, so a
            # trip discards every earlier layer and returns the cosine floor.
            final = static.copy()
            return final, _receipt(
                graph, policy, seeds, static, final, (),
                trip_reason=(
                    f"depth {depth}: fanout gate tripped for "
                    f"{len(skipped)} frontier source(s)"
                ),
            )
        if not allowed:
            final = static.copy()
            return final, _receipt(
                graph, policy, seeds, static, final, (),
                trip_reason=f"depth {depth}: no outgoing evidence arc",
            )

        source_indices = np.asarray([item[0] for item in allowed], dtype=np.int64)
        source_logits = (keys[source_indices] @ current_query) / policy.temperature
        source_weights = _softmax(source_logits)
        value_read = np.zeros(keys.shape[1], dtype=np.float64)
        reached: set[int] = set()
        arc_receipts: list[ValueArcReceiptV1] = []
        for source_weight, (source, row) in zip(
            source_weights, allowed, strict=True,
        ):
            edge_weight = float(source_weight) / len(row)
            for arc_index, arc in row:
                value_read += edge_weight * values[arc.target_target]
                reached.add(arc.target_target)
                arc_receipts.append(ValueArcReceiptV1(
                    depth=depth, arc_index=arc_index,
                    source_target=source, target_target=arc.target_target,
                    source_id=arc.source_id,
                    selector_start=arc.selector_start,
                    selector_end=arc.selector_end,
                    selector_exact=arc.selector_exact,
                    anchor_label=arc.anchor_label,
                    source_attention=float(source_weight),
                    edge_weight=edge_weight,
                ))
        read_norm = float(np.linalg.norm(value_read))
        if read_norm <= 1e-12:
            final = static.copy()
            return final, _receipt(
                graph, policy, seeds, static, final, (),
                trip_reason=f"depth {depth}: zero value read",
            )
        updated = current_query + policy.gamma * value_read
        updated_norm = float(np.linalg.norm(updated))
        if updated_norm <= 1e-12 or not math.isfinite(updated_norm):
            raise QKVB1IntegrityError("query update produced an invalid vector")
        next_query = updated / updated_norm
        reached_targets = tuple(sorted(reached))
        layer_receipts.append(QKVLayerReceiptV1(
            depth=depth,
            query_before_sha256=_array_sha256(current_query),
            query_after_sha256=_array_sha256(next_query),
            value_read_sha256=_array_sha256(value_read),
            value_read_norm=read_norm,
            frontier_targets=tuple(int(item) for item in source_indices),
            reached_targets=reached_targets,
            skipped_fanout_sources=tuple(skipped),
            arcs=tuple(arc_receipts),
        ))
        current_query = next_query
        frontier = reached_targets

    final = static.copy() if not layer_receipts else keys @ current_query
    layers = tuple(layer_receipts)
    return final, _receipt(
        graph, policy, seeds, static, final, layers, trip_reason=trip_reason,
    )


def _b1_graph(build: tab.TitleAnchorBuildV1) -> comp.CompositionGraphV1:
    ordinal = {
        source_id: index
        for index, source_id in enumerate(build.paragraph_graph.target_source_ids)
    }
    receipts = {item.receipt_id: item for item in build.evidence_spans}
    arcs: list[comp.EvidenceArcV1] = []
    for link in build.directed_links:
        for receipt_id in link.evidence_receipt_ids:
            receipt = receipts[receipt_id]
            arcs.append(comp.EvidenceArcV1(
                source_target=ordinal[link.subject_source_id],
                target_target=ordinal[link.object_source_id],
                source_id=receipt.source_id,
                selector_start=receipt.body_start,
                selector_end=receipt.body_end,
                selector_exact=receipt.exact_quote,
                anchor_label=receipt.normalized_alias,
            ))
    return comp.make_graph(build.paragraph_graph.target_source_ids, arcs)


def _reject_fresh_path(path: str | Path) -> Path:
    source = Path(path)
    if any("fresh" in part.casefold() for part in source.parts):
        raise QKVB1IntegrityError("fresh paths are outside this development probe")
    return source


def _load_embedding_archive(
    path: str | Path,
) -> tuple[dict[str, tuple[str, str, np.ndarray]], str]:
    source = Path(path)
    try:
        with np.load(source, allow_pickle=False) as archive:
            if set(archive.files) != {"ids", "kinds", "text_sha256", "vectors"}:
                raise QKVB1IntegrityError("embedding NPZ members mismatch")
            ids = tuple(str(item) for item in archive["ids"].tolist())
            kinds = tuple(str(item) for item in archive["kinds"].tolist())
            hashes = tuple(str(item) for item in archive["text_sha256"].tolist())
            vectors = np.asarray(archive["vectors"], dtype=np.float64)
    except (OSError, ValueError) as exc:
        raise QKVB1IntegrityError(f"invalid embedding NPZ: {exc}") from exc
    if (vectors.ndim != 2 or vectors.shape[0] != len(ids) or
            len(kinds) != len(ids) or len(hashes) != len(ids)):
        raise QKVB1IntegrityError("embedding arrays are not aligned")
    if len(ids) != len(set(ids)):
        raise QKVB1IntegrityError("embedding IDs are not unique")
    if not np.isfinite(vectors).all():
        raise QKVB1IntegrityError("embedding vectors contain non-finite values")
    records = {
        identity: (kind, text_hash, vectors[index])
        for index, (identity, kind, text_hash) in enumerate(
            zip(ids, kinds, hashes, strict=True)
        )
    }
    return records, _file_sha256(source)


def load_development_datasets(
    development_segment_paths: Sequence[str | Path],
    embedding_npz_path: str | Path,
) -> tuple[DevelopmentDatasetV1, ...]:
    """Load only development segments and stable-ID/hash matched vectors.

    The embedding archive may contain unrelated extra IDs because the existing
    historical cache is a superset.  They are never joined into a graph or a
    query and their count is exposed in the returned receipt metadata.
    """

    if not development_segment_paths:
        raise QKVB1IntegrityError("at least one development segment is required")
    segment_paths = tuple(_reject_fresh_path(path) for path in development_segment_paths)
    embedding_records, embedding_digest = _load_embedding_archive(embedding_npz_path)
    out: list[DevelopmentDatasetV1] = []
    seen_datasets: set[str] = set()
    required_embedding_ids: set[str] = set()
    for segment_path in segment_paths:
        segment = h3.load_prepared_segment(segment_path)
        if segment.split != "development":
            raise QKVB1IntegrityError("only split=development segments are accepted")
        if segment.dataset in seen_datasets:
            raise QKVB1IntegrityError(f"duplicate development dataset {segment.dataset}")
        seen_datasets.add(segment.dataset)
        paragraphs: list[tab.ParagraphInputV1] = []
        for item in segment.paragraphs:
            compiler_payload = {
                "source_id": item.source_id, "title": item.title, "text": item.text,
            }
            reval.assert_compiler_payload_clean(compiler_payload)
            paragraphs.append(tab.ParagraphInputV1(**compiler_payload))
        build = tab.build_title_anchor_graph(tuple(paragraphs))
        issues = tab.verify_title_anchor_build(build)
        if issues:
            raise QKVB1IntegrityError(f"B1 verification failed: {issues[:5]}")
        graph = _b1_graph(build)
        paragraph_vectors: list[np.ndarray] = []
        for item in segment.paragraphs:
            identity = f"paragraph:{item.source_id}"
            required_embedding_ids.add(identity)
            record = embedding_records.get(identity)
            if record is None:
                raise QKVB1IntegrityError(f"missing paragraph embedding {identity}")
            expected_hash = sha256(f"{item.title} :: {item.text}".encode("utf-8")).hexdigest()
            if record[0] != "paragraph" or record[1] != expected_hash:
                raise QKVB1IntegrityError(f"paragraph embedding preimage mismatch {identity}")
            paragraph_vectors.append(record[2])
        key_vectors = _unit_matrix(
            np.stack(paragraph_vectors), label=f"{segment.dataset} paragraph vectors",
        )
        ordinal = {source_id: index for index, source_id in enumerate(graph.target_ids)}
        queries: list[DevelopmentQueryV1] = []
        dropped: list[str] = []
        for row in segment.evaluation_rows:
            identity = f"query:{segment.dataset}:{row.qid}"
            required_embedding_ids.add(identity)
            record = embedding_records.get(identity)
            if record is None:
                raise QKVB1IntegrityError(f"missing query embedding {identity}")
            expected_hash = sha256(row.question.encode("utf-8")).hexdigest()
            if record[0] != "query" or record[1] != expected_hash:
                dropped.append(row.qid)
                continue
            try:
                gold = tuple(sorted({ordinal[item] for item in row.gold_source_ids}))
            except KeyError as exc:
                raise QKVB1IntegrityError(
                    f"gold stable ID missing from candidate graph: {exc.args[0]}"
                ) from exc
            queries.append(DevelopmentQueryV1(
                qid=row.qid,
                query_vector=_unit_vector(record[2], label=f"query {row.qid}"),
                gold_ordinals=gold,
                hop=row.hop,
            ))
        if not queries:
            raise QKVB1IntegrityError(f"{segment.dataset} has no exact query preimages")
        out.append(DevelopmentDatasetV1(
            dataset=segment.dataset,
            segment_path=str(segment_path), segment_sha256=_file_sha256(segment_path),
            embedding_path=str(embedding_npz_path),
            embedding_sha256=embedding_digest,
            target_ids=graph.target_ids, graph=graph,
            key_vectors=key_vectors, value_vectors=key_vectors.copy(),
            queries=tuple(queries), dropped_query_ids=tuple(dropped),
            unused_embedding_records=0,
            builder_stats=dict(build.stats),
        ))
    unused = len(set(embedding_records) - required_embedding_ids)
    return tuple(replace(item, unused_embedding_records=unused) for item in out)


def _query_metrics(scores: np.ndarray, gold: tuple[int, ...], *, seed: int) -> dict[str, float]:
    gold_array = np.asarray(gold, dtype=np.int64)
    order = np.argsort(-scores, kind="stable")
    top = set(int(item) for item in order[:K_METRIC])
    gold_set = set(gold)
    return {
        "ndcg10": float(metrics.ndcg_at_k(
            scores, gold_array, np.arange(scores.size), k=K_METRIC, seed=seed,
        )),
        "asr10": float(gold_set.issubset(top)),
        "support_recall10": len(gold_set & top) / len(gold_set),
    }


def _mean_metrics(rows: Sequence[Mapping[str, float]]) -> dict[str, float]:
    return {
        name: round(float(np.mean([row[name] for row in rows])), 6)
        for name in ("ndcg10", "asr10", "support_recall10")
    }


def run_development_probe(
    datasets: Sequence[DevelopmentDatasetV1],
    policies: Sequence[QKVB1PolicyV1],
) -> dict[str, Any]:
    """Run static and QKV arms on evaluator-owned development rows only."""

    if not datasets or not policies:
        raise ValueError("datasets and at least one QKV policy are required")
    reports: list[dict[str, Any]] = []
    for dataset in datasets:
        static_scores = np.stack([
            dataset.key_vectors @ query.query_vector for query in dataset.queries
        ])
        static_rows = [
            _query_metrics(static_scores[index], query.gold_ordinals, seed=index + 1)
            for index, query in enumerate(dataset.queries)
        ]
        arms: list[dict[str, Any]] = []
        for policy in policies:
            scores: list[np.ndarray] = []
            receipts: list[QKVB1ReceiptV1] = []
            metric_rows: list[dict[str, float]] = []
            for index, query in enumerate(dataset.queries):
                final, receipt = score_qkv_b1(
                    query.query_vector, dataset.key_vectors, dataset.graph,
                    policy, value_vectors=dataset.value_vectors,
                )
                scores.append(final)
                receipts.append(receipt)
                metric_rows.append(_query_metrics(
                    final, query.gold_ordinals, seed=index + 1,
                ))
            means = _mean_metrics(metric_rows)
            static_means = _mean_metrics(static_rows)
            layer_counts = {
                str(depth): sum(
                    any(layer.depth == depth for layer in receipt.layers)
                    for receipt in receipts
                )
                for depth in range(1, policy.hops + 1)
            }
            receipt_root = sha256(canonical_json(tuple(
                receipt.receipt_sha256 for receipt in receipts
            )).encode("utf-8")).hexdigest()
            arm_id = sha256(canonical_json(asdict(policy)).encode("utf-8")).hexdigest()[:16]
            arms.append({
                "arm_id": f"qkv-b1-{arm_id}", "policy": asdict(policy),
                "metrics": means,
                "delta_vs_static": {
                    name: round(means[name] - static_means[name], 6)
                    for name in means
                },
                "apply_coverage": round(
                    sum(receipt.applied for receipt in receipts) / len(receipts), 6,
                ),
                "layer_apply_counts": layer_counts,
                "score_matrix_sha256": _array_sha256(np.stack(scores)),
                "receipt_root_sha256": receipt_root,
            })
        reports.append({
            "dataset": dataset.dataset,
            "n_queries": len(dataset.queries),
            "dropped_query_ids": list(dataset.dropped_query_ids),
            "n_targets": len(dataset.target_ids),
            "embedding": {
                "path": dataset.embedding_path,
                "sha256": dataset.embedding_sha256,
                "unused_superset_records": dataset.unused_embedding_records,
            },
            "segment": {
                "path": dataset.segment_path, "sha256": dataset.segment_sha256,
                "split": "development",
            },
            "builder": {
                "topology_sha256": dataset.graph.topology_sha256,
                "n_evidence_arcs": len(dataset.graph.arcs),
                "stats": dict(dataset.builder_stats),
                "evaluation_labels_seen": 0,
            },
            "static": {
                "metrics": _mean_metrics(static_rows),
                "score_matrix_sha256": _array_sha256(static_scores),
            },
            "arms": arms,
        })
    return {
        "schema_version": DEVELOPMENT_REPORT_SCHEMA_VERSION,
        "experiment": "B1-QKV evidence-bound paragraph value read",
        "scope": "development-only exploratory probe; fresh paths are not accepted",
        "claim_forbidden": [
            "fresh confirmatory result", "deployment certificate",
            "answer reasoning uplift", "general reasoner",
        ],
        "datasets": reports,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--development-segment", action="append", required=True,
        help="development v4 segment JSON; fresh paths are rejected",
    )
    parser.add_argument("--embedding-npz", required=True)
    parser.add_argument("--seed-k", type=int, default=10)
    parser.add_argument("--gamma", type=float, default=0.1)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--max-fanout", type=int, default=16)
    args = parser.parse_args(argv)
    datasets = load_development_datasets(
        args.development_segment, args.embedding_npz,
    )
    policies = tuple(QKVB1PolicyV1(
        seed_k=args.seed_k, hops=hops, gamma=args.gamma,
        temperature=args.temperature, max_fanout=args.max_fanout,
    ) for hops in (1, 2))
    print(json.dumps(
        run_development_probe(datasets, policies), ensure_ascii=False,
        sort_keys=True, separators=(",", ":"),
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
