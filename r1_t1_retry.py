"""PROM-8 R1 — T1 re-trial with alias-closure + soft-weight + HippoRAG2-style seed.

Does NOT mutate frozen ``typed_composition.py`` (T1 sha intact).
Implements a research fork of the typed max-product walker with three
orthogonal levers from PROM_8 C2:

  (1) Wikidata-style offline alias-closure on query + predicate stems
  (2) soft edge-weight demotion (hard min_typed_match gate OFF; quality multiplies)
  (3) HippoRAG2-style seed: cosine top-k ∪ lexical title/entity-boosted paragraphs

Budget: frozen V5 embeddings only — no LLM, no network, no new embeddings.
Gold labels never consumed.

Run only after PREREG_R1_T1_RETRY_2026-07-22.json freezes registration.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np

import claim_builder as cb
import h3_b3_falsifier as fz
import typed_composition as typed
from chain_viability import enumerate_admissible_chains
from claim_weave import apply_weave, weave_c1, weave_c2, weave_c3
from r1_predicate_alias import (
    build_predicate_alias_index,
    query_term_closure,
    _norm_words,
)

HERE = Path(__file__).parent
CACHE = HERE / ".ab_p5_cache" / "h3_b3"
RUN = CACHE / "runs" / "qwen35-r3-schema-v4-20260720" / "development"
JOURNAL = RUN / "extractions.jsonl"
EMBED_NPZ = RUN / "embedding" / "embeddings.npz"
SEGMENTS = {
    "musique": CACHE / "musique_development_v4_segment.json",
    "2wiki": CACHE / "2wiki_development_v4_segment.json",
}
PREREG = HERE / "PREREG_R1_T1_RETRY_2026-07-22.json"
EVIDENCE = HERE / "EVIDENCE_R1_T1_RETRY_2026-07-22.json"

SEED_K = 3
SEED_K_HIPPO = 5  # slightly wider pool then cut to SEED_K after fusion


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def preregistration_guard() -> dict:
    if not PREREG.exists():
        raise RuntimeError(f"missing prereg: {PREREG}")
    locked = json.loads(PREREG.read_text(encoding="utf-8"))
    if locked.get("registered_before_measurement") is not True:
        raise RuntimeError("prereg not confirmed before measurement")
    if not locked.get("prediction_receipt_sha256"):
        raise RuntimeError("missing prediction receipt")
    # freeze r1 modules + frozen data
    for mod, expected in locked.get("module_sha256", {}).items():
        got = _sha(HERE / mod)
        if got != expected:
            raise RuntimeError(f"module drift {mod}: {got} != {expected}")
    if locked["embedding_npz_sha256"] != _sha(EMBED_NPZ):
        raise RuntimeError("embedding store drift")
    if locked["journal_sha256"] != _sha(JOURNAL):
        raise RuntimeError("journal drift")
    return locked


def load_embedding_store():
    store = np.load(EMBED_NPZ, allow_pickle=True)
    ids = [str(x) for x in store["ids"]]
    kinds = [str(x) for x in store["kinds"]]
    vectors = np.asarray(store["vectors"], dtype=np.float64)
    paragraph_vecs: dict[str, np.ndarray] = {}
    query_vecs: dict[tuple[str, str], np.ndarray] = {}
    for row_id, kind, vec in zip(ids, kinds, vectors):
        if kind == "paragraph":
            paragraph_vecs[row_id.split(":", 1)[1]] = vec
        elif kind == "query":
            _, dataset, qid = row_id.split(":", 2)
            query_vecs[(dataset, qid)] = vec
    return paragraph_vecs, query_vecs


@dataclass(frozen=True)
class ArmConfig:
    name: str
    use_alias: bool
    soft_gate: bool
    hippo_seed: bool


ARMS = (
    ArmConfig("A0_baseline", False, False, False),
    ArmConfig("A1_alias", True, False, False),
    ArmConfig("A2_soft", False, True, False),
    ArmConfig("A3_alias_soft", True, True, False),
    ArmConfig("A4_r1_full", True, True, True),  # PROM-8 R1 package
)


def _coverage(needles: frozenset[str] | set[str] | tuple[str, ...],
              query_terms: frozenset[str] | set[str]) -> float:
    if not needles or not query_terms:
        return 0.0
    hits = 0
    for needle in needles:
        for q in query_terms:
            if needle == q:
                hits += 1
                break
            if min(len(needle), len(q)) >= 5 and (
                    needle.startswith(q) or q.startswith(needle)):
                hits += 1
                break
    return float(hits) / float(len(needles))


def _relation_quality(
    query_terms: frozenset[str],
    arc: typed.TypedEvidenceArcV1,
    alias_index: dict[str, frozenset[str]] | None,
    use_alias: bool,
) -> tuple[float, float, float]:
    if use_alias and alias_index is not None:
        pred_terms = alias_index.get(
            arc.source_predicate.exact,
            frozenset(_norm_words(arc.source_predicate.exact)),
        )
    else:
        pred_terms = frozenset(_norm_words(arc.source_predicate.exact))
    role_text = typed._ROLE_SPLIT_RE.sub(" ", arc.source_argument_role)
    role_terms = frozenset(_norm_words(role_text))
    if use_alias:
        from r1_predicate_alias import expand_terms
        role_terms = expand_terms(role_terms)
    predicate_match = _coverage(pred_terms, query_terms)
    role_match = _coverage(role_terms, query_terms)
    quality = 0.75 * predicate_match + 0.25 * role_match
    return predicate_match, role_match, quality


def select_seeds(
    static: np.ndarray,
    query_terms: frozenset[str],
    graph: typed.TypedCompositionGraphV1,
    titles: dict[str, str],
    *,
    hippo: bool,
    k: int = SEED_K,
) -> tuple[int, ...]:
    """Cosine top-k, optionally fused with lexical title/entity boost (Hippo-style)."""
    n = graph.n_targets
    order = np.argsort(-static, kind="stable")
    if not hippo:
        return tuple(int(i) for i in order[:k])

    # lexical boost: title stem overlap with query (recognition-memory seed)
    lex_score = np.zeros(n, dtype=np.float64)
    for i, sid in enumerate(graph.target_ids):
        title_terms = frozenset(_norm_words(titles.get(sid, "")))
        if not title_terms:
            continue
        overlap = len(title_terms & query_terms) / max(1, len(title_terms))
        # also reward any query stem appearing in title
        hit = sum(1 for t in title_terms if t in query_terms)
        lex_score[i] = overlap + 0.25 * hit

    # outgoing-arc predicate/subject surface as weak entity cue
    for arc in graph.arcs:
        subj = frozenset(_norm_words(arc.source_selector.exact))
        if subj & query_terms:
            lex_score[arc.source_target] += 0.5 * (
                len(subj & query_terms) / max(1, len(subj))
            )

    # fuse: z-ish rank fusion without learning
    cos_rank = np.empty(n, dtype=np.float64)
    cos_rank[order] = np.arange(n, dtype=np.float64)
    lex_order = np.argsort(-lex_score, kind="stable")
    lex_rank = np.empty(n, dtype=np.float64)
    lex_rank[lex_order] = np.arange(n, dtype=np.float64)
    # lower rank better; RRF
    rrf = 1.0 / (60.0 + cos_rank) + 1.0 / (60.0 + lex_rank)
    fused = np.argsort(-rrf, kind="stable")
    return tuple(int(i) for i in fused[:k])


def walk_depth2(
    query_terms: frozenset[str],
    static: np.ndarray,
    graph: typed.TypedCompositionGraphV1,
    policy: typed.TypedCompositionPolicyV1,
    *,
    seeds: tuple[int, ...],
    soft_gate: bool,
    use_alias: bool,
    alias_index: dict[str, frozenset[str]] | None,
    min_typed_match: float,
) -> tuple[bool, int]:
    """Max-product K<=2 walker. Returns (reached_depth2, n_depth2_targets)."""
    if policy.mu == 0:
        return False, 0

    adjacency: list[list[typed.TypedEvidenceArcV1]] = [
        [] for _ in range(graph.n_targets)
    ]
    for arc in graph.arcs:
        adjacency[arc.source_target].append(arc)
    for row in adjacency:
        row.sort(key=lambda a: (a.target_target, a.arc_id))

    # depth-1 states
    frontier: list[tuple[float, int, str | None, frozenset[str], frozenset[int]]] = []
    for seed in seeds:
        if seed < 0 or seed >= graph.n_targets:
            continue
        frontier.append((
            max(float(static[seed]), 0.0), seed, None, frozenset(), frozenset({seed}),
        ))

    depth2_targets: set[int] = set()
    # hop 1
    hop1: list[tuple[float, int, str | None, frozenset[str], frozenset[int]]] = []
    for score, src, active, joins, nodes in frontier:
        if score <= 0:
            continue
        row = adjacency[src]
        if not row:
            continue
        fanout_w = float(len(row)) ** (-policy.fanout_exponent)
        for arc in row:
            if arc.target_target in nodes or arc.join_entity_id in joins:
                continue
            p_m, r_m, quality = _relation_quality(
                query_terms, arc, alias_index, use_alias,
            )
            if not soft_gate:
                if p_m < min_typed_match or quality < min_typed_match:
                    continue
            # soft: always keep if quality>0; hard-filtered above
            if soft_gate and quality <= 0:
                # tiny floor so pure structure can still walk when soft
                # but PROM soft is weight demotion not free pass — skip 0
                continue
            rel_w = quality if quality > 0 else 0.0
            if soft_gate and rel_w <= 0:
                continue
            if not soft_gate:
                rel_w = quality
            cand = score * fanout_w * rel_w
            if cand <= 0:
                continue
            hop1.append((
                cand, arc.target_target, arc.target_claim_id,
                joins | {arc.join_entity_id}, nodes | {arc.target_target},
            ))

    # hop 2
    for score, src, active, joins, nodes in hop1:
        if active is None:
            continue  # title terminal
        row = [a for a in adjacency[src] if a.source_claim_id == active]
        if not row:
            # also allow any outgoing if claim id mismatch sparsity
            row = adjacency[src]
        if not row:
            continue
        fanout_w = float(len(row)) ** (-policy.fanout_exponent)
        for arc in row:
            if arc.target_target in nodes or arc.join_entity_id in joins:
                continue
            p_m, r_m, quality = _relation_quality(
                query_terms, arc, alias_index, use_alias,
            )
            if not soft_gate:
                if p_m < min_typed_match or quality < min_typed_match:
                    continue
            if soft_gate and quality <= 0:
                continue
            rel_w = quality
            cand = score * fanout_w * rel_w
            if cand <= 0:
                continue
            depth2_targets.add(arc.target_target)

    return (len(depth2_targets) > 0), len(depth2_targets)


def main() -> int:
    locked = preregistration_guard()
    paragraph_vecs, query_vecs = load_embedding_store()
    segments = {n: fz.load_prepared_segment(p) for n, p in SEGMENTS.items()}
    artifact = fz.load_extraction_artifact(JOURNAL, tuple(segments.values()))
    policy = typed.TypedCompositionPolicyV1(seed_k=SEED_K)
    min_match = float(policy.min_typed_match)

    # prebuild graphs + alias index from all woven predicates
    prepared: dict[str, dict] = {}
    all_preds: list[str] = []
    for name in sorted(segments):
        segment = segments[name]
        paragraphs = fz._paragraph_inputs(segment)
        frozen = tuple(artifact.frozen_by_source[p.source_id] for p in paragraphs)
        build = cb.compile_claim_graph(paragraphs, frozen)
        if cb.verify_claim_graph(build):
            raise RuntimeError(f"{name}: claim graph verification failed")
        base = typed.graph_from_claim_build(build)
        titles = {p.source_id: p.title for p in paragraphs}
        woven = apply_weave(base, [
            weave_c1(build, titles, base),
            weave_c2(build, titles, base),
            weave_c3(build, titles, base),
        ])
        entrances = sorted({
            c.source_target for c in enumerate_admissible_chains(woven).chains
        })
        for arc in woven.arcs:
            all_preds.append(arc.source_predicate.exact)
            if arc.target_predicate is not None:
                all_preds.append(arc.target_predicate.exact)
        ordinal_vecs = np.stack([paragraph_vecs[sid] for sid in base.target_ids])
        rows = [r for r in segment.evaluation_rows if (name, r.qid) in query_vecs]
        if len(rows) != len(segment.evaluation_rows):
            raise RuntimeError(f"{name}: missing frozen query embeddings")
        rows.sort(key=lambda r: r.qid)
        prepared[name] = {
            "woven": woven,
            "titles": titles,
            "entrances": set(entrances),
            "ordinal_vecs": ordinal_vecs,
            "rows": rows,
            "n_entrance": len(entrances),
        }

    alias_index = build_predicate_alias_index(all_preds)

    per_dataset: dict[str, dict] = {}
    for name, pack in prepared.items():
        woven = pack["woven"]
        titles = pack["titles"]
        entrance_set = pack["entrances"]
        ordinal_vecs = pack["ordinal_vecs"]
        rows = pack["rows"]
        arm_rows: dict[str, dict] = {}
        for arm in ARMS:
            t1_hits = 0
            depth2_hits = 0
            depth2_targets_sum = 0
            for row in rows:
                scores = ordinal_vecs @ query_vecs[(name, row.qid)]
                if arm.use_alias:
                    q_terms = query_term_closure(row.question)
                else:
                    q_terms = frozenset(_norm_words(row.question))
                seeds = select_seeds(
                    scores, q_terms, woven, titles,
                    hippo=arm.hippo_seed, k=SEED_K if not arm.hippo_seed else SEED_K,
                )
                # hippo may use SEED_K still after fusion
                if entrance_set.intersection(seeds):
                    t1_hits += 1
                reached, n_t = walk_depth2(
                    q_terms, scores, woven, policy,
                    seeds=seeds,
                    soft_gate=arm.soft_gate,
                    use_alias=arm.use_alias,
                    alias_index=alias_index if arm.use_alias else None,
                    min_typed_match=min_match,
                )
                if reached:
                    depth2_hits += 1
                    depth2_targets_sum += n_t
            arm_rows[arm.name] = {
                "entrance_paragraphs": pack["n_entrance"],
                "queries": len(rows),
                "t1_seed_reaches_entrance": t1_hits,
                "kernel_legal_depth2_queries": depth2_hits,
                "depth2_targets_sum": depth2_targets_sum,
                "config": {
                    "use_alias": arm.use_alias,
                    "soft_gate": arm.soft_gate,
                    "hippo_seed": arm.hippo_seed,
                    "min_typed_match": min_match,
                    "seed_k": SEED_K,
                },
            }
        per_dataset[name] = arm_rows

    # headline = A4_r1_full min over datasets (PROM-8 R1 package)
    def _min_metric(arm_name: str, key: str) -> int:
        return min(per_dataset[d][arm_name][key] for d in per_dataset)

    headline_arm = "A4_r1_full"
    t1_min = _min_metric(headline_arm, "t1_seed_reaches_entrance")
    depth2_min = _min_metric(headline_arm, "kernel_legal_depth2_queries")
    baseline_t1 = _min_metric("A0_baseline", "t1_seed_reaches_entrance")
    baseline_d2 = _min_metric("A0_baseline", "kernel_legal_depth2_queries")

    # diagnostic decomposition for OQ1 (vocab vs structure)
    decomposition = {
        arm.name: {
            "t1_min": _min_metric(arm.name, "t1_seed_reaches_entrance"),
            "depth2_min": _min_metric(arm.name, "kernel_legal_depth2_queries"),
            "delta_t1_vs_A0": (
                _min_metric(arm.name, "t1_seed_reaches_entrance") - baseline_t1
            ),
            "delta_depth2_vs_A0": (
                _min_metric(arm.name, "kernel_legal_depth2_queries") - baseline_d2
            ),
        }
        for arm in ARMS
    }

    evidence = {
        "schema": "hswm-r1-t1-retry-evidence/v1",
        "programme": "LakatosTree_PromSearchHSWM_20260721",
        "branch": "R1-t1-retry-alias-soft-hipposeed",
        "prom8_ref": "HSWM/PROM_8_DYNAMIC_TWO_LANES_2026-07-22.md §4 R1",
        "preregistration": {
            "path": PREREG.name,
            "sha256": _sha(PREREG),
            "prediction_receipt_sha256": locked["prediction_receipt_sha256"],
        },
        "measurement": {
            "metric": "min_over_datasets_A4_t1_seed_reaches_entrance",
            "value": t1_min,
            "novel_metric": "min_over_datasets_A4_kernel_legal_depth2_queries",
            "novel_value": depth2_min,
            "baseline_A0": {
                "t1_min": baseline_t1,
                "depth2_min": baseline_d2,
            },
            "delta_vs_A0": {
                "t1": t1_min - baseline_t1,
                "depth2": depth2_min - baseline_d2,
            },
            "decomposition": decomposition,
            "per_dataset": per_dataset,
            "alias_predicates_indexed": len(alias_index),
        },
        "budget": {
            "llm_calls": 0,
            "network_calls": 0,
            "new_embedding_calls": 0,
            "note": "frozen V5 development embeddings; offline alias families only",
        },
        "gold_labels_consumed": False,
        "kill_evaluation": {
            "kill1_t1_still_zero_both": t1_min == 0,
            "kill2_t1_up_but_depth2_zero": t1_min > 0 and depth2_min == 0,
            "kill3_no_gain_vs_A0": (
                (t1_min - baseline_t1) <= 0 and (depth2_min - baseline_d2) <= 0
            ),
        },
        "limitations": [
            "Alias map is local family/morphology, not live Wikidata SPARQL dump.",
            "Soft gate still requires quality>0 (not free untyped walk).",
            "Hippo seed is cosine∪title/entity lexical RRF, not true query-triple embeddings.",
            "Research walker fork — not a change to frozen typed_composition.py.",
            "No answer-F1 / retrieval-quality claim.",
        ],
    }
    EVIDENCE.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "evidence": str(EVIDENCE),
        "evidence_sha256": _sha(EVIDENCE),
        "A4_t1_min": t1_min,
        "A4_depth2_min": depth2_min,
        "A0_t1_min": baseline_t1,
        "A0_depth2_min": baseline_d2,
        "decomposition": decomposition,
        "kill": evidence["kill_evaluation"],
        "per_dataset_A4": {
            d: per_dataset[d]["A4_r1_full"] for d in per_dataset
        },
        "per_dataset_A0": {
            d: per_dataset[d]["A0_baseline"] for d in per_dataset
        },
    }, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
