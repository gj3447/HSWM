"""H3 relational-retrieval falsifier over the B1 title-anchor world.

The comparator holds paragraph targets, bge-m3 vectors, candidate universe,
and static cosine scores fixed.  The only treatment is an evidence-bound
directed title topology consumed by :mod:`composition`.  Relation labels are
loaded into :mod:`relation_eval` solely to form leakage-safe held-out groups;
they never enter the builder or scorer.

This is a research comparison, not a production certificate.  A positive
result may support *relational retrieval intelligence*.  It cannot support a
reasoner claim until downstream answer transfer and certified admission for
this new kernel are separately established.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import os
import re
import sys
import time
from typing import Any, Iterable

import numpy as np

import ab_p5_full as ab
import composition as comp
from hypergraph import Hypergraph
import metrics
import relation_eval as reval
import title_anchor_builder as tab
import traversal as tv
import traversal_cert as tcert
import world_builder as wb
from weight_field import WeightField


N_ROWS = 200
K_METRIC = 10
SPLIT_SEED = 42
SELECT_Z_ADJ = 2.5
SHUFFLE_SEEDS = (0, 1, 2, 3, 4)
COMPOSITION_GRID = tuple(
    comp.CompositionPolicyV1(seed_k=seed_k, hops=hops, mu=mu, direction=direction)
    for direction in ("forward", "bidirectional")
    for seed_k in (3, 10, 20)
    for hops in (1, 2)
    for mu in (0.025, 0.05, 0.1, 0.2)
)
TOKEN_RE = re.compile(r"(?u)\b\w\w+\b")


@dataclass(frozen=True)
class DatasetBundle:
    dataset: str
    rows: tuple[dict, ...]
    world: wb.BuiltWorld
    unit_embeddings: np.ndarray
    query_embeddings: np.ndarray
    embedding_cache_path: str
    embedding_cache_sha256: str
    raw_rows: tuple[dict, ...]
    relation_suite: reval.RelationEvaluationSuiteV1
    val_ids: tuple[int, ...]
    test_ids: tuple[int, ...]
    component_by_query: tuple[str, ...]


def _file_sha256(path: str) -> str:
    digest = sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sample_rows(dataset: str, cache_dir: str, n_rows: int = N_ROWS) -> list[dict]:
    all_rows = ab.load_pool(dataset, cache_dir)
    by_hop: dict[int, list[dict]] = {}
    for row in all_rows:
        by_hop.setdefault(wb.parse_hop(row), []).append(row)
    rows: list[dict] = []
    cursor = 0
    while len(rows) < n_rows and any(cursor < len(items) for items in by_hop.values()):
        for hop in sorted(by_hop):
            if cursor < len(by_hop[hop]) and len(rows) < n_rows:
                rows.append(by_hop[hop][cursor])
        cursor += 1
    if len(rows) != n_rows:
        raise RuntimeError(f"{dataset}: requested {n_rows} rows, found {len(rows)}")
    return rows


def _raw_cache_path(dataset: str, cache_dir: str) -> str:
    return os.path.join(cache_dir, f"h3_relation_raw_{dataset}.json")


def _fetch_raw_map(dataset: str, cache_dir: str) -> dict[str, dict]:
    """Acquire evaluation labels outside the compiler and freeze them locally."""
    path = _raw_cache_path(dataset, cache_dir)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("dataset") != dataset or not isinstance(payload.get("rows"), list):
            raise RuntimeError(f"malformed raw relation cache {path}")
        actual = sha256(
            reval.canonical_json(tuple(payload["rows"])).encode("utf-8")
        ).hexdigest()
        if actual != payload.get("rows_sha256"):
            raise RuntimeError(f"raw relation cache digest mismatch: {path}")
        return {str(row["id"]): row for row in payload["rows"]}
    offsets, url = (
        (ab.MUSIQUE_OFFSETS, ab.MUSIQUE_ROWS_URL)
        if dataset == "musique" else
        (ab.WIKI2_OFFSETS, ab.WIKI2_ROWS_URL)
    )
    rows: list[dict] = []
    for offset in offsets:
        payload = ab._http_json(url.format(off=offset), timeout=120)
        rows.extend(item["row"] for item in payload["rows"])
    frozen = {
        "dataset": dataset,
        "source": url,
        "offsets": list(offsets),
        "rows_sha256": sha256(reval.canonical_json(tuple(rows)).encode("utf-8")).hexdigest(),
        "rows": rows,
    }
    os.makedirs(cache_dir, exist_ok=True)
    tmp = path + f".tmp{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(frozen, handle, ensure_ascii=False)
    os.replace(tmp, path)
    return {str(row["id"]): row for row in rows}


def load_bundle(dataset: str, cache_dir: str = ".ab_p5_cache",
                n_rows: int = N_ROWS) -> DatasetBundle:
    rows = _sample_rows(dataset, cache_dir, n_rows)
    shape_world = wb.build(rows, embed_fn=lambda texts: np.zeros((len(texts), 8)))
    vocab_sha = sha256((
        "\n".join(shape_world.entities) + f"|u{len(shape_world.unit_texts)}"
    ).encode()).hexdigest()[:12]
    embedding_path = os.path.join(cache_dir, f"cert_embed_{dataset}_{vocab_sha}.npz")
    if not os.path.exists(embedding_path):
        raise RuntimeError(
            f"missing frozen bge-m3 cache {embedding_path}; run traversal_cert.py real first"
        )
    frozen = np.load(embedding_path)
    entity, unit, query = frozen["ent"], frozen["unit"], frozen["q"]
    calls = iter((entity, unit))
    world = wb.build(rows, embed_fn=lambda texts: next(calls))
    if query.shape[0] != len(rows):
        raise RuntimeError("query embedding count does not match sampled rows")

    raw_map = _fetch_raw_map(dataset, cache_dir)
    try:
        raw_rows = tuple(raw_map[str(row["id"])] for row in rows)
    except KeyError as exc:
        raise RuntimeError(f"raw relation row missing for qid {exc.args[0]}") from exc
    suite = reval.build_relation_evaluation_suite(
        dataset, raw_rows, split_spec=(("val", 0.5), ("test", 0.5)), seed=SPLIT_SEED,
    )
    example_by_qid = {example.qid: example for example in suite.examples}
    assignment_by_occurrence = {item.occurrence_id: item for item in suite.assignments}
    split_by_query: list[str] = []
    component_by_query: list[str] = []
    for row in rows:
        example = example_by_qid[str(row["id"])]
        assignment = assignment_by_occurrence[example.occurrence_id]
        split_by_query.append(assignment.split)
        component_by_query.append(assignment.component_id)
    val = tuple(index for index, split in enumerate(split_by_query) if split == "val")
    test = tuple(index for index, split in enumerate(split_by_query) if split == "test")
    if not val or not test:
        raise RuntimeError("relation-disjoint split produced an empty partition")
    return DatasetBundle(
        dataset=dataset, rows=tuple(rows), world=world,
        unit_embeddings=np.asarray(unit, dtype=np.float64),
        query_embeddings=np.asarray(query, dtype=np.float64),
        embedding_cache_path=embedding_path,
        embedding_cache_sha256=_file_sha256(embedding_path),
        raw_rows=raw_rows, relation_suite=suite,
        val_ids=val, test_ids=test,
        component_by_query=tuple(component_by_query),
    )


def _paragraph_inputs(rows: Iterable[dict]) -> tuple[tab.ParagraphInputV1, ...]:
    seen: set[tuple[str, str]] = set()
    out: list[tab.ParagraphInputV1] = []
    for row in rows:
        # This explicit narrow copy is the compiler boundary.  The assertion
        # catches accidental future replacement with a raw QA row.
        for paragraph in row["paragraphs"]:
            key = (str(paragraph["title"]), str(paragraph["paragraph_text"]))
            if key in seen:
                continue
            seen.add(key)
            source_id = reval.content_id("paragraph_source", {
                "title": key[0], "text_sha256": sha256(key[1].encode("utf-8")).hexdigest(),
            })
            clean = {"source_id": source_id, "title": key[0], "text": key[1]}
            reval.assert_compiler_payload_clean(clean)
            out.append(tab.ParagraphInputV1(**clean))
    return tuple(out)


def build_composition_graph(bundle: DatasetBundle
                            ) -> tuple[tab.TitleAnchorBuildV1, comp.CompositionGraphV1]:
    title_build = tab.build_title_anchor_graph(_paragraph_inputs(bundle.rows))
    issues = tab.verify_title_anchor_build(title_build)
    if issues:
        raise RuntimeError(f"title-anchor build failed verification: {issues}")
    if title_build.paragraph_graph.unit_texts != tuple(bundle.world.unit_texts):
        raise RuntimeError("B1 changed target text/order; embedding comparison is invalid")
    ordinal = {
        source_id: index
        for index, source_id in enumerate(title_build.paragraph_graph.target_source_ids)
    }
    receipt_by_id = {receipt.receipt_id: receipt for receipt in title_build.evidence_spans}
    arcs: list[comp.EvidenceArcV1] = []
    for link in title_build.directed_links:
        receipt = receipt_by_id[link.evidence_receipt_ids[0]]
        arcs.append(comp.EvidenceArcV1(
            source_target=ordinal[link.subject_source_id],
            target_target=ordinal[link.object_source_id],
            source_id=receipt.source_id,
            selector_start=receipt.body_start,
            selector_end=receipt.body_end,
            selector_exact=receipt.exact_quote,
            anchor_label=receipt.normalized_alias,
        ))
    graph = comp.make_graph(title_build.paragraph_graph.target_source_ids, arcs)
    return title_build, graph


def cosine_scores(bundle: DatasetBundle) -> np.ndarray:
    unit = bundle.unit_embeddings / np.maximum(
        np.linalg.norm(bundle.unit_embeddings, axis=1, keepdims=True), 1e-12,
    )
    query = bundle.query_embeddings / np.maximum(
        np.linalg.norm(bundle.query_embeddings, axis=1, keepdims=True), 1e-12,
    )
    return query @ unit.T


def _array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(value, dtype="<f8"))
    return sha256(array.tobytes()).hexdigest()


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.casefold())


def bm25_scores(bundle: DatasetBundle, k1: float = 1.5, b: float = 0.75) -> np.ndarray:
    documents = [_tokens(text) for text in bundle.world.unit_texts]
    lengths = np.array([len(document) for document in documents], dtype=np.float64)
    average = max(float(lengths.mean()), 1.0)
    postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for doc_id, document in enumerate(documents):
        for token, frequency in Counter(document).items():
            postings[token].append((doc_id, frequency))
    n_docs = len(documents)
    out = np.zeros((len(bundle.rows), n_docs), dtype=np.float64)
    for query_id, row in enumerate(bundle.rows):
        for token in set(_tokens(row["question"])):
            posting = postings.get(token, ())
            df = len(posting)
            if not df:
                continue
            idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
            for doc_id, frequency in posting:
                denominator = frequency + k1 * (1.0 - b + b * lengths[doc_id] / average)
                out[query_id, doc_id] += idf * frequency * (k1 + 1.0) / denominator
    return out


def _ranks(scores: np.ndarray) -> np.ndarray:
    order = np.argsort(-scores, axis=1, kind="stable")
    ranks = np.empty_like(order)
    row = np.arange(scores.shape[0])[:, None]
    ranks[row, order] = np.arange(1, scores.shape[1] + 1)
    return ranks


def rrf_scores(cosine: np.ndarray, bm25: np.ndarray, k: float = 60.0) -> np.ndarray:
    return 1.0 / (k + _ranks(cosine)) + 1.0 / (k + _ranks(bm25))


def query_metrics(scores: np.ndarray, gold: np.ndarray) -> dict[str, float]:
    order = np.argsort(-scores, kind="stable")
    gold_set = set(int(item) for item in gold)
    top = set(int(item) for item in order[:K_METRIC])
    return {
        "ndcg10": float(metrics.ndcg_at_k(
            scores, gold, np.arange(scores.size), k=K_METRIC, seed=1,
        )),
        "asr10": float(gold_set.issubset(top)),
        "support_recall10": len(gold_set & top) / max(len(gold_set), 1),
    }


def evaluate_matrix(scores: np.ndarray, bundle: DatasetBundle,
                    query_ids: Iterable[int]) -> dict[str, np.ndarray]:
    query_ids = tuple(query_ids)
    if scores.ndim != 2:
        raise ValueError("score matrix must be rank 2")
    if scores.shape[0] == len(bundle.rows):
        score_rows = query_ids
    elif scores.shape[0] == len(query_ids):
        score_rows = tuple(range(len(query_ids)))
    else:
        raise ValueError("score rows must be full-corpus queries or align to query_ids")
    rows = [
        query_metrics(scores[score_row], bundle.world.queries[query_id].gold)
        for score_row, query_id in zip(score_rows, query_ids, strict=True)
    ]
    return {
        metric: np.array([row[metric] for row in rows], dtype=np.float64)
        for metric in ("ndcg10", "asr10", "support_recall10")
    }


def _metric_means(values: dict[str, np.ndarray]) -> dict[str, float]:
    return {key: round(float(value.mean()), 6) for key, value in values.items()}


def _paired_gate(delta: np.ndarray, z: float = SELECT_Z_ADJ) -> dict[str, Any]:
    se = float(delta.std(ddof=1)) / math.sqrt(delta.size) if delta.size > 1 else math.inf
    mean = float(delta.mean())
    return {
        "mean_delta": round(mean, 6), "se": round(se, 6), "z_adjusted": z,
        "passes": bool(mean > 0 and mean >= z * se),
    }


def select_composition_policy(static: np.ndarray, bundle: DatasetBundle,
                              graph: comp.CompositionGraphV1,
                              val_ids: tuple[int, ...]) -> tuple[comp.CompositionPolicyV1, dict]:
    base = evaluate_matrix(static, bundle, val_ids)
    surface: list[tuple[float, float, comp.CompositionPolicyV1, np.ndarray]] = []
    for policy in COMPOSITION_GRID:
        matrix = np.stack([
            comp.compose_scores(static[query_id], graph, policy)[0]
            for query_id in val_ids
        ])
        result = evaluate_matrix(matrix, bundle, val_ids)
        surface.append((float(result["ndcg10"].mean()), float(result["asr10"].mean()),
                        policy, result["ndcg10"] - base["ndcg10"]))
    best_ndcg, best_asr, best, delta = max(
        surface, key=lambda item: (item[0], item[1], -item[2].mu)
    )
    gate = _paired_gate(delta)
    chosen = best if gate["passes"] else comp.CompositionPolicyV1(
        seed_k=best.seed_k, hops=best.hops, mu=0.0, direction=best.direction,
    )
    top = sorted(surface, key=lambda item: (item[0], item[1]), reverse=True)[:10]
    return chosen, {
        "base_ndcg10": round(float(base["ndcg10"].mean()), 6),
        "best_ndcg10": round(best_ndcg, 6), "best_asr10": round(best_asr, 6),
        "best_policy": asdict(best), "chosen_policy": asdict(chosen), "gate": gate,
        "top10_surface": [
            {"ndcg10": round(ndcg, 6), "asr10": round(asr, 6), "policy": asdict(policy)}
            for ndcg, asr, policy, _ in top
        ],
    }


def evaluate_composition(static: np.ndarray, bundle: DatasetBundle,
                         graph: comp.CompositionGraphV1,
                         policy: comp.CompositionPolicyV1,
                         query_ids: tuple[int, ...]) -> tuple[dict[str, np.ndarray], dict]:
    rows: list[np.ndarray] = []
    trips: Counter[str] = Counter()
    applied = 0
    promoted = []
    for query_id in query_ids:
        scores, _residual, receipt = comp.compose_scores(static[query_id], graph, policy)
        rows.append(scores)
        if receipt.reached_targets:
            applied += 1
        else:
            trips[receipt.trip_reason or "unknown"] += 1
        if receipt.trip_reason and receipt.reached_targets:
            trips[receipt.trip_reason] += 1
        promoted.append(len(receipt.promoted_paths))
    matrix = np.stack(rows)
    return evaluate_matrix(matrix, bundle, query_ids), {
        "apply_coverage": round(applied / len(query_ids), 6),
        "fallback_rate": round((len(query_ids) - applied) / len(query_ids), 6),
        "trip_reasons": dict(sorted(trips.items())),
        "mean_promoted_paths": round(float(np.mean(promoted)), 4),
    }


def _b1_diffusion_world(bundle: DatasetBundle, build: tab.TitleAnchorBuildV1
                        ) -> tuple[wb.BuiltWorld, WeightField, tv.TraversalIndex]:
    n = len(build.paragraph_graph.target_source_ids)
    members = []
    for source, outgoing in enumerate(build.paragraph_graph.outgoing_target_ordinals):
        members.append(np.array(sorted({source, *outgoing}), dtype=np.int64))
    # Node vectors are structurally irrelevant because target embeddings are
    # explicit; use finite zeros to avoid spending a different embedding budget.
    graph = Hypergraph(
        node_emb=np.zeros((n, bundle.unit_embeddings.shape[1]), dtype=np.float64),
        members=members, edge_freq=np.ones(n), edge_recency=np.zeros(n),
    )
    graph.unit_emb = bundle.unit_embeddings.copy()  # type: ignore[attr-defined]
    world = wb.BuiltWorld(
        hg=graph, entities=list(build.paragraph_graph.target_source_ids),
        unit_texts=list(build.paragraph_graph.unit_texts), queries=bundle.world.queries,
        stats=dict(build.stats),
    )
    field = WeightField(graph, M=None, target_emb=bundle.unit_embeddings)
    return world, field, tv.build_index(graph)


def evaluate_diffusion(bundle: DatasetBundle, build: tab.TitleAnchorBuildV1,
                       query_ids: tuple[int, ...], val_ids: tuple[int, ...]) -> tuple[dict, dict]:
    world, field, index = _b1_diffusion_world(bundle, build)
    mu, selection = tcert.select_mu(
        field, world, list(val_ids), bundle.query_embeddings, index, seed=0,
    )
    rows = []
    trips: Counter[str] = Counter()
    probe_mu = mu if mu > 0 else 0.4
    for query_id in query_ids:
        ids, values, receipt = tv.traverse(
            field, bundle.query_embeddings[query_id], k=world.hg.M,
            mu=probe_mu, index=index,
        )
        scores = np.empty(world.hg.M)
        scores[ids] = values
        rows.append(scores)
        trips[receipt.abstain_reason or "no_abstain"] += 1
    probe = evaluate_matrix(np.stack(rows), bundle, query_ids)
    return {
        "chosen_mu": mu, "selection": selection, "probe_mu": probe_mu,
        "probe_metrics": _metric_means(probe),
    }, {key: round(value / len(query_ids), 6) for key, value in sorted(trips.items())}


def cluster_bootstrap(delta: np.ndarray, components: tuple[str, ...],
                      n_boot: int = 10000, seed: int = 0,
                      n_permutations: int = 0) -> dict[str, Any]:
    if delta.size != len(components) or delta.size == 0:
        raise ValueError("delta/components must be non-empty and aligned")
    grouped: dict[str, np.ndarray] = {}
    for component in sorted(set(components)):
        grouped[component] = np.flatnonzero(np.array(components) == component)
    keys = tuple(grouped)
    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot, dtype=np.float64)
    for index in range(n_boot):
        selected = rng.integers(0, len(keys), len(keys))
        values = np.concatenate([delta[grouped[keys[item]]] for item in selected])
        draws[index] = float(values.mean())
    permutation_p = None
    if n_permutations:
        sums = np.array([float(delta[grouped[key]].sum()) for key in keys])
        observed = float(delta.mean())
        greater_or_equal = 0
        remaining = n_permutations
        while remaining:
            batch = min(5000, remaining)
            signs = rng.choice(np.array((-1.0, 1.0)), size=(batch, len(keys)))
            null = (signs @ sums) / delta.size
            greater_or_equal += int(np.sum(null >= observed))
            remaining -= batch
        permutation_p = round(
            (greater_or_equal + 1) / (n_permutations + 1), 6,
        )
    return {
        "n_queries": int(delta.size), "n_components": len(keys),
        "mean_delta": round(float(delta.mean()), 6),
        "ci95": [round(float(np.percentile(draws, 2.5)), 6),
                 round(float(np.percentile(draws, 97.5)), 6)],
        "p_delta_le_zero": round(float((draws <= 0).mean()), 6),
        "p_cluster_signflip_one_sided": permutation_p,
        "n_permutations": n_permutations,
    }


def _bh_qvalues(items: list[tuple[str, float]]) -> dict[str, float]:
    """Benjamini-Hochberg q-values, monotone from largest rank downward."""
    ordered = sorted(items, key=lambda item: (item[1], item[0]))
    m = len(ordered)
    out: dict[str, float] = {}
    running = 1.0
    for rank in range(m, 0, -1):
        key, p = ordered[rank - 1]
        running = min(running, p * m / rank)
        out[key] = round(min(running, 1.0), 6)
    return out


def bridge_diagnostics(bundle: DatasetBundle, graph: comp.CompositionGraphV1) -> dict:
    weak = {tuple(sorted((arc.source_target, arc.target_target))) for arc in graph.arcs}
    connected = 0
    pair_hits = 0
    pairs = 0
    gold_to_noise = []
    adjacency = defaultdict(set)
    for arc in graph.arcs:
        adjacency[arc.source_target].add(arc.target_target)
        adjacency[arc.target_target].add(arc.source_target)
    for query in bundle.world.queries:
        gold = [int(item) for item in query.gold]
        for left in range(len(gold)):
            for right in range(left + 1, len(gold)):
                pairs += 1
                pair_hits += tuple(sorted((gold[left], gold[right]))) in weak
        seen = {gold[0]}
        while True:
            grown = seen | {
                target for source in tuple(seen) for target in adjacency[source]
                if target in set(gold)
            }
            if grown == seen:
                break
            seen = grown
        connected += len(seen) == len(set(gold))
        noise_links = sum(
            target not in set(gold) for source in gold for target in adjacency[source]
        )
        gold_to_noise.append(noise_links / max(sum(len(adjacency[source]) for source in gold), 1))
    return {
        "gold_pair_direct_link_rate": round(pair_hits / max(pairs, 1), 6),
        "gold_chain_connected_rate": round(connected / len(bundle.world.queries), 6),
        "mean_gold_incident_noise_fraction": round(float(np.mean(gold_to_noise)), 6),
    }


def _test_components(bundle: DatasetBundle) -> tuple[str, ...]:
    return tuple(bundle.component_by_query[index] for index in bundle.test_ids)


def run_dataset(dataset: str, cache_dir: str = ".ab_p5_cache") -> dict[str, Any]:
    started = time.time()
    bundle = load_bundle(dataset, cache_dir)
    build, graph = build_composition_graph(bundle)
    static = cosine_scores(bundle)
    lexical = bm25_scores(bundle)
    hybrid = rrf_scores(static, lexical)
    baseline_matrices = {"cosine": static, "bm25": lexical, "rrf": hybrid}
    val_metrics = {
        name: evaluate_matrix(matrix, bundle, bundle.val_ids)
        for name, matrix in baseline_matrices.items()
    }
    strongest = max(
        baseline_matrices,
        key=lambda name: (
            float(val_metrics[name]["ndcg10"].mean()),
            float(val_metrics[name]["asr10"].mean()),
        ),
    )
    policy, selection = select_composition_policy(static, bundle, graph, bundle.val_ids)
    static_test = evaluate_matrix(static, bundle, bundle.test_ids)
    composition_test, composition_receipt = evaluate_composition(
        static, bundle, graph, policy, bundle.test_ids,
    )
    test_baselines = {
        name: evaluate_matrix(matrix, bundle, bundle.test_ids)
        for name, matrix in baseline_matrices.items()
    }
    components = _test_components(bundle)
    comparisons: dict[str, dict[str, Any]] = {}
    for metric in ("ndcg10", "asr10", "support_recall10"):
        comparisons[metric] = {
            "vs_static": cluster_bootstrap(
                composition_test[metric] - static_test[metric], components,
                seed=100 + len(metric), n_permutations=100000,
            ),
            "vs_strongest_baseline": cluster_bootstrap(
                composition_test[metric] - test_baselines[strongest][metric], components,
                seed=200 + len(metric), n_permutations=100000,
            ),
        }

    nulls: list[dict[str, Any]] = []
    null_harness_broken = False
    for shuffle_seed in SHUFFLE_SEEDS:
        null_graph = comp.degree_preserving_shuffle(graph, shuffle_seed)
        real_pairs = {(arc.source_target, arc.target_target) for arc in graph.arcs}
        null_pairs = {(arc.source_target, arc.target_target) for arc in null_graph.arcs}
        changed_fraction = 1.0 - len(real_pairs & null_pairs) / max(len(real_pairs), 1)
        null_policy, null_selection = select_composition_policy(
            static, bundle, null_graph, bundle.val_ids,
        )
        null_harness_broken |= null_policy.mu > 0
        null_test, null_receipt = evaluate_composition(
            static, bundle, null_graph, policy, bundle.test_ids,
        )
        nulls.append({
            "seed": shuffle_seed,
            "topology_sha256": null_graph.topology_sha256,
            "changed_edge_fraction": round(changed_fraction, 6),
            "selected_policy": asdict(null_policy),
            "selection_gate": null_selection["gate"],
            "real_policy_metrics": _metric_means(null_test),
            "real_minus_null": {
                metric: cluster_bootstrap(
                    composition_test[metric] - null_test[metric], components,
                    seed=300 + shuffle_seed * 10 + len(metric),
                )
                for metric in ("ndcg10", "asr10")
            },
            "receipt": null_receipt,
        })

    diffusion, diffusion_trips = evaluate_diffusion(
        bundle, build, bundle.test_ids, bundle.val_ids,
    )
    nd = comparisons["ndcg10"]["vs_static"]
    asr = comparisons["asr10"]["vs_static"]
    strong_nd = comparisons["ndcg10"]["vs_strongest_baseline"]
    strong_asr = comparisons["asr10"]["vs_strongest_baseline"]
    topology_ok = all(
        item["real_minus_null"][metric]["ci95"][0] > 0
        for item in nulls for metric in ("ndcg10", "asr10")
    )
    pass_dataset = bool(
        policy.mu > 0 and not null_harness_broken and
        nd["mean_delta"] >= 0.02 and nd["ci95"][0] > 0 and
        asr["mean_delta"] >= 0.03 and asr["ci95"][0] > 0 and
        strong_nd["mean_delta"] >= 0.02 and strong_nd["ci95"][0] > 0 and
        strong_asr["mean_delta"] >= 0.03 and strong_asr["ci95"][0] > 0 and
        composition_receipt["apply_coverage"] >= 0.5 and topology_ok
    )
    query_hops = Counter(bundle.world.queries[index].hop for index in bundle.test_ids)
    component_sizes = Counter(components)
    return {
        "dataset": dataset,
        "verdict": "H3_DATASET_PASS" if pass_dataset else (
            "HARNESS_BROKEN" if null_harness_broken else "H3_DATASET_FAIL"
        ),
        "pass": pass_dataset,
        "scope": "relational retrieval only; downstream F1 and deployable kernel certification open",
        "n_rows": len(bundle.rows), "n_val": len(bundle.val_ids), "n_test": len(bundle.test_ids),
        "test_hops": dict(sorted(query_hops.items())),
        "relation_split": {
            "suite_id": bundle.relation_suite.suite_id,
            "raw_snapshot_sha256": bundle.relation_suite.raw_snapshot_sha256,
            "n_components_test": len(component_sizes),
            "max_component_test": max(component_sizes.values()),
            "template_evidence_disjoint": True,
        },
        "embedding": {
            "model": "bge-m3", "cache_path": bundle.embedding_cache_path,
            "cache_sha256": bundle.embedding_cache_sha256,
            "unit_shape": list(bundle.unit_embeddings.shape),
            "query_shape": list(bundle.query_embeddings.shape),
            "unit_text_root_sha256": sha256(
                reval.canonical_json(tuple(bundle.world.unit_texts)).encode("utf-8")
            ).hexdigest(),
            "query_text_root_sha256": sha256(
                reval.canonical_json(tuple(row["question"] for row in bundle.rows)).encode("utf-8")
            ).hexdigest(),
            "legacy_cache_limit": (
                "NPZ stores vectors but not per-input preimage hashes; fresh confirmatory run "
                "must emit an embedding manifest"
            ),
        },
        "builder": {
            "build_id": build.build_id, "topology_sha256": graph.topology_sha256,
            "verification_issues": list(tab.verify_title_anchor_build(build)),
            "stats": build.stats, "bridge_diagnostics": bridge_diagnostics(bundle, graph),
            "input_fields": ["source_id", "title", "text"],
            "evaluation_labels_seen": 0,
        },
        "selection": selection,
        "strongest_baseline": strongest,
        "test_metrics": {
            **{name: _metric_means(values) for name, values in test_baselines.items()},
            "composition": _metric_means(composition_test),
        },
        "score_digests": {
            "static_cosine_float64_sha256": _array_sha256(static),
        },
        "comparisons": comparisons,
        "composition_receipt": composition_receipt,
        "diffusion_control": {**diffusion, "trip_rates": diffusion_trips},
        "null_gate": {
            "verdict": "HARNESS_BROKEN" if null_harness_broken else "PASS",
            "all_shuffles_selected_mu0": not null_harness_broken,
            "real_topology_beats_every_shuffle": topology_ok,
            "shuffles": nulls,
        },
        "elapsed_s": round(time.time() - started, 3),
    }


def run_all(cache_dir: str = ".ab_p5_cache") -> dict[str, Any]:
    reports = [run_dataset(dataset, cache_dir) for dataset in ("musique", "2wiki")]
    primary_p = []
    for report in reports:
        for metric in ("ndcg10", "asr10"):
            key = f"{report['dataset']}:{metric}"
            p = report["comparisons"][metric]["vs_static"]["p_cluster_signflip_one_sided"]
            primary_p.append((key, float(p)))
    qvalues = _bh_qvalues(primary_p)
    for report in reports:
        q = {
            metric: qvalues[f"{report['dataset']}:{metric}"]
            for metric in ("ndcg10", "asr10")
        }
        report["multiplicity"] = {
            "family": "2 datasets x 2 primary metrics",
            "method": "Benjamini-Hochberg",
            "qvalues": q,
            "passes_q_lt_0.05": all(value < 0.05 for value in q.values()),
        }
        if report["pass"] and not report["multiplicity"]["passes_q_lt_0.05"]:
            report["pass"] = False
            report["verdict"] = "H3_DATASET_FAIL_MULTIPLICITY"
    passed = sum(report["pass"] for report in reports)
    verdict = (
        "H3_RELATIONAL_RETRIEVAL_PASS" if passed == len(reports) else
        "H3_DATASET_SPECIFIC_ONLY" if passed == 1 else
        "H3_REFUTED_OR_INCONCLUSIVE"
    )
    if any(report["verdict"] == "HARNESS_BROKEN" for report in reports):
        verdict = "HARNESS_BROKEN"
    return {
        "experiment": "H3 B1 exact-title role-preserving max-semiring falsifier",
        "preregistered_thresholds": {
            "ndcg10_delta": 0.02, "asr10_delta": 0.03,
            "cluster_bootstrap_ci_lower": ">0", "apply_coverage": 0.5,
            "null_shuffles": len(SHUFFLE_SEEDS),
        },
        "verdict": verdict,
        "claim_allowed": (
            "relational retrieval intelligence" if verdict == "H3_RELATIONAL_RETRIEVAL_PASS"
            else "none beyond dataset-specific mechanism evidence"
        ),
        "claim_forbidden": [
            "general reasoner", "downstream answer uplift", "deployable certified composition kernel",
            "n-ary reasoning", "ontology reasoning",
        ],
        "datasets": reports,
    }


def main() -> None:
    output = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "h3_title_anchor_result.json"
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else ".ab_p5_cache"
    report = run_all(cache)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps({
        "verdict": report["verdict"],
        "datasets": [
            {"dataset": item["dataset"], "verdict": item["verdict"],
             "test_metrics": item["test_metrics"],
             "null_gate": item["null_gate"]["verdict"]}
            for item in report["datasets"]
        ],
        "out": output,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
