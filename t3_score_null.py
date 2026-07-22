"""T3 rung — K2가 K1 score digest를 실제로 바꾸고, second-edge null이 죽이는가.

H3-C0 waterfall 최종 rung. A5(ML-woven) 그래프 위에서:

  T3a  strict claim-continuity 재감사 — R1/R2 워커(hop-2에서 연속 arc 부재 시
       임의 arc 허용 fallback)가 관대 집계였는지 정면 검증.  이 워커는 커널
       정본과 동일하게 fallback 없이 계산하고, lenient 수치도 병기 공표한다.
       strict에서 depth-2 min이 0으로 돌아가면 R2 판정은 정정 대상이다.
  T3b  score-digest 변화 — K1(1-hop max-product 기여)과 K2(2-hop 포함) 최종
       점수 벡터의 sha256 digest가 질의별로 달라지는가.
  T3c  second-edge null — 비말단 arc들의 target_claim_id를 결정론 셔플로
       치환(연속성 파괴)한 null 그래프에서 T3b 변화가 소멸하는가.

예산: frozen 자산 재사용, LLM/network/신규 embedding 0, gold 무소비.
Do not run before PREREG_T3_SCORE_NULL_2026-07-23.json records a live prediction.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import random
from pathlib import Path

import numpy as np

import claim_builder as cb
import h3_b3_falsifier as fz
import typed_composition as typed
from claim_weave import apply_weave, weave_c1, weave_c2, weave_c3
from claim_weave_ml import load_material, weave_ml
from r1_predicate_alias import build_predicate_alias_index, query_term_closure
from r1_t1_retry import (
    EMBED_NPZ, JOURNAL, SEED_K, SEGMENTS,
    _relation_quality, load_embedding_store, select_seeds,
)

HERE = Path(__file__).parent
PREREG = HERE / "PREREG_T3_SCORE_NULL_2026-07-23.json"
EVIDENCE = HERE / "EVIDENCE_T3_SCORE_NULL_2026-07-23.json"
FROZEN_MODULES = (
    "claim_weave.py", "claim_weave_ml.py", "r1_predicate_alias.py",
    "r1_t1_retry.py", "t3_score_null.py",
)
MATERIAL_KEYS = ("musique_link", "musique_coref", "2wiki_link", "2wiki_coref")
NULL_SEED = 4242
MU = 0.1


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def preregistration_guard() -> dict:
    if not PREREG.exists():
        raise RuntimeError(f"missing preregistration: {PREREG}")
    locked = json.loads(PREREG.read_text(encoding="utf-8"))
    if locked.get("registered_before_measurement") is not True:
        raise RuntimeError("preregistration not confirmed before measurement")
    if not locked.get("prediction_receipt_sha256"):
        raise RuntimeError("preregistration lacks a prediction receipt")
    for module in FROZEN_MODULES:
        if locked["module_sha256"].get(module) != _sha(HERE / module):
            raise RuntimeError(f"frozen module drift: {module}")
    mat_dir = HERE / ".ab_p5_cache" / "r2_material"
    for key in MATERIAL_KEYS:
        ds, phase = key.rsplit("_", 1)
        if locked["material_sha256"][key] != _sha(mat_dir / f"{ds}_{phase}.json"):
            raise RuntimeError(f"frozen material drift: {key}")
    if locked["embedding_npz_sha256"] != _sha(EMBED_NPZ):
        raise RuntimeError("frozen embedding store drift")
    return locked


def null_graph(graph: typed.TypedCompositionGraphV1, seed: int) -> typed.TypedCompositionGraphV1:
    """비말단 arc의 target_claim_id를 파생 셔플로 치환 — 연속성만 파괴,
    구조(노드·엣지 수·선택자)는 보존. target_predicate는 존재 제약상 유지."""
    nonterminal = [a for a in graph.arcs if a.target_claim_id is not None]
    ids = [a.target_claim_id for a in nonterminal]
    rng = random.Random(seed)
    shuffled = ids[:]
    rng.shuffle(shuffled)
    # 고정점(자기 자리) 최소화: 한 칸 회전 fallback
    if any(a == b for a, b in zip(ids, shuffled)) and len(ids) > 1:
        shuffled = shuffled[1:] + shuffled[:1]
    mapping = {a.arc_id: s for a, s in zip(nonterminal, shuffled)}
    arcs = tuple(
        replace(a, target_claim_id=mapping[a.arc_id]) if a.arc_id in mapping else a
        for a in sorted(graph.arcs, key=lambda x: x.arc_id)
    )
    return typed.make_typed_graph(graph.target_ids, arcs)


def walk_scores_strict(
    query_terms: frozenset[str],
    static: np.ndarray,
    graph: typed.TypedCompositionGraphV1,
    policy: typed.TypedCompositionPolicyV1,
    *,
    seeds: tuple[int, ...],
    alias_index,
) -> tuple[np.ndarray, np.ndarray, int, int]:
    """(k1_scores, k2_scores, strict_depth2_targets, lenient_depth2_targets).

    max-product 기여를 mu 가중으로 static에 더한다.  hop-2는 strict claim
    연속만 (커널 정본).  lenient 카운트는 R1/R2 fallback 재현 진단용 —
    점수에는 절대 반영하지 않는다.
    """
    n = graph.n_targets
    adjacency: list[list[typed.TypedEvidenceArcV1]] = [[] for _ in range(n)]
    for arc in graph.arcs:
        adjacency[arc.source_target].append(arc)
    for row in adjacency:
        row.sort(key=lambda a: (a.target_target, a.arc_id))

    contrib1 = np.zeros(n)
    contrib2 = np.zeros(n)
    strict_d2: set[int] = set()
    lenient_d2: set[int] = set()

    hop1_states = []
    for seed in seeds:
        base = max(float(static[seed]), 0.0)
        if base <= 0:
            continue
        row = adjacency[seed]
        if not row:
            continue
        fan_w = float(len(row)) ** (-policy.fanout_exponent)
        for arc in row:
            _, _, quality = _relation_quality(query_terms, arc, alias_index, True)
            if quality <= 0:
                continue
            cand = base * fan_w * quality
            if cand <= 0:
                continue
            t = arc.target_target
            contrib1[t] = max(contrib1[t], cand)
            hop1_states.append((cand, t, arc.target_claim_id,
                                {arc.join_entity_id}, {seed, t}))

    for score, src, active, joins, nodes in hop1_states:
        if active is None:
            continue
        strict_row = [a for a in adjacency[src] if a.source_claim_id == active]
        lenient_row = strict_row if strict_row else adjacency[src]
        for tag, row in (("strict", strict_row), ("lenient", lenient_row)):
            if not row:
                continue
            fan_w = float(len(row)) ** (-policy.fanout_exponent)
            for arc in row:
                if arc.target_target in nodes or arc.join_entity_id in joins:
                    continue
                _, _, quality = _relation_quality(query_terms, arc, alias_index, True)
                if quality <= 0:
                    continue
                cand = score * fan_w * quality
                if cand <= 0:
                    continue
                if tag == "strict":
                    contrib2[arc.target_target] = max(
                        contrib2[arc.target_target], cand)
                    strict_d2.add(arc.target_target)
                lenient_d2.add(arc.target_target)

    k1 = static + MU * contrib1
    k2 = static + MU * np.maximum(contrib1, contrib2)
    return k1, k2, len(strict_d2), len(lenient_d2)


def _digest(vec: np.ndarray) -> str:
    return sha256(np.ascontiguousarray(vec, dtype=np.float64).tobytes()).hexdigest()


def main() -> int:
    locked = preregistration_guard()
    paragraph_vecs, query_vecs = load_embedding_store()
    segments = {n: fz.load_prepared_segment(p) for n, p in SEGMENTS.items()}
    artifact = fz.load_extraction_artifact(JOURNAL, tuple(segments.values()))
    policy = typed.TypedCompositionPolicyV1(seed_k=SEED_K)

    per_dataset: dict[str, dict] = {}
    all_preds: list[str] = []
    prepared = {}
    for name in sorted(segments):
        segment = segments[name]
        paragraphs = fz._paragraph_inputs(segment)
        frozen = tuple(artifact.frozen_by_source[p.source_id] for p in paragraphs)
        build = cb.compile_claim_graph(paragraphs, frozen)
        if cb.verify_claim_graph(build):
            raise RuntimeError(f"{name}: claim graph verification failed")
        base = typed.graph_from_claim_build(build)
        titles = {p.source_id: p.title for p in paragraphs}
        det = apply_weave(base, [
            weave_c1(build, titles, base),
            weave_c2(build, titles, base),
            weave_c3(build, titles, base),
        ])
        link_by, coref_by = load_material(name)
        ml, _ = weave_ml(build, base, link_by, coref_by)
        a5 = apply_weave(det, [ml])
        a5_null = null_graph(a5, NULL_SEED)
        for g in (a5,):
            for arc in g.arcs:
                all_preds.append(arc.source_predicate.exact)
                if arc.target_predicate is not None:
                    all_preds.append(arc.target_predicate.exact)
        rows = [r for r in segment.evaluation_rows if (name, r.qid) in query_vecs]
        rows.sort(key=lambda r: r.qid)
        prepared[name] = {
            "a5": a5, "a5_null": a5_null, "titles": titles,
            "ordinal_vecs": np.stack([paragraph_vecs[s] for s in base.target_ids]),
            "rows": rows,
        }

    alias_index = build_predicate_alias_index(all_preds)

    for name, pack in prepared.items():
        row_stats = {"real": {"digest_changed": 0, "strict_d2": 0, "lenient_d2": 0},
                     "null": {"digest_changed": 0, "strict_d2": 0}}
        for row in pack["rows"]:
            scores = pack["ordinal_vecs"] @ query_vecs[(name, row.qid)]
            q_terms = query_term_closure(row.question)
            for arm, graph in (("real", pack["a5"]), ("null", pack["a5_null"])):
                seeds = select_seeds(scores, q_terms, graph, pack["titles"],
                                     hippo=True, k=SEED_K)
                k1, k2, sd2, ld2 = walk_scores_strict(
                    q_terms, scores, graph, policy,
                    seeds=seeds, alias_index=alias_index)
                changed = _digest(k1) != _digest(k2)
                row_stats[arm]["digest_changed"] += changed
                if arm == "real":
                    row_stats[arm]["strict_d2"] += sd2 > 0
                    row_stats[arm]["lenient_d2"] += ld2 > 0
                else:
                    row_stats[arm]["strict_d2"] += sd2 > 0
        per_dataset[name] = row_stats

    primary = min(d["real"]["digest_changed"] for d in per_dataset.values())
    novel = sum(d["real"]["digest_changed"] - d["null"]["digest_changed"]
                for d in per_dataset.values())
    strict_d2_min = min(d["real"]["strict_d2"] for d in per_dataset.values())

    evidence = {
        "schema": "hswm-t3-score-null-evidence/v1",
        "programme": "LakatosTree_PromSearchHSWM_20260721",
        "branch": "T3-score-digest-null",
        "preregistration": {"path": PREREG.name, "sha256": _sha(PREREG),
                            "prediction_receipt_sha256": locked["prediction_receipt_sha256"]},
        "measurement": {
            "metric": "min_over_datasets_real_k2_digest_changed_queries",
            "value": primary,
            "novel_metric": "sum_real_minus_null_k2_digest_changed_queries",
            "novel_value": novel,
            "strict_reaudit": {
                "strict_depth2_min": strict_d2_min,
                "note": "R1/R2 워커의 lenient fallback 재감사 — lenient 병기",
            },
            "per_dataset": per_dataset,
            "config": {"mu": MU, "seed_k": SEED_K, "null_seed": NULL_SEED,
                       "arm": "A5 ML-woven, alias+soft(hard floor quality>0)+hippo seed",
                       "continuity": "strict (kernel-canonical), lenient diagnostics only"},
        },
        "budget": {"query_time_llm": 0, "network": 0, "new_embedding": 0},
        "gold_labels_consumed": False,
        "limitations": [
            "Score semantics are the research walker's (max-product + mu-add), not the frozen kernel's exact arithmetic; digest change is a mechanism check, not a retrieval-quality claim.",
            "Null breaks continuity only; selector/predicate text untouched, so lexical-quality artifacts are not nulled (that would need a predicate-shuffle null, deferred).",
        ],
    }
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(json.dumps({
        "evidence_sha256": _sha(EVIDENCE),
        "primary_min_digest_changed": primary,
        "novel_real_minus_null": novel,
        "strict_depth2_min": strict_d2_min,
        "per_dataset": per_dataset,
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
