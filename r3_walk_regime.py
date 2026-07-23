"""R3 — 걷기 승리 regime 통제 재현 (PROM-8 C4/C8, USER "연산>절약" 정전).

지금까지 걷기는 조밀·소규모 substrate에서만 시험됐다(C4 비판).  R3는 PhantomWiki로
**pool 크기**와 **bridge 희박도(friendship-k)**를 독립 dial로 돌려, strict max-product
K≤2 걷기가 flat cosine을 이기는 regime을 통제 재현한다.  density dial을 독립 변수로
돌린 걷기 실험은 선행연구에 없다(PROM-8 C8 빈칸).

  arms      flat = cosine only  /  walk = cosine + strict K≤2 max-product (μ=0.1)
  축1 크기   small 50 / mid 506 / large 5057 (friendship-k 3 고정)
  축2 밀도   sparse fk1 / large fk3 / dense fk9 (5057 고정)
  층화      question difficulty(hop) — hard = difficulty ≥ 6
  채점      best-trace recall@10 (여러 유효 추론 사슬 중 최선 사슬의 회수율)

전 arc는 원문 exact span 바인딩(r3_phantom_ingest, 손실 0). LLM/network 0.
Do not run before PREREG_R3_WALK_REGIME_2026-07-23.json records a live prediction.
"""
from __future__ import annotations

from hashlib import sha256
import json
import random
from pathlib import Path

import numpy as np

import typed_composition as typed
from r1_predicate_alias import build_predicate_alias_index, query_term_closure
from r3_phantom_ingest import build_graph, load_universe, source_id_for
from t3_score_null import walk_scores_strict

HERE = Path(__file__).parent
UNIVERSES = {
    "small_t2_fk3": {"axis": "size", "articles": 50, "fk": 3},
    "mid_t20_fk3": {"axis": "size", "articles": 506, "fk": 3},
    "large_t200_fk3": {"axis": "both", "articles": 5057, "fk": 3},
    "sparse_t200_fk1": {"axis": "density", "articles": 5057, "fk": 1},
    "dense_t200_fk9": {"axis": "density", "articles": 5057, "fk": 9},
}
ROOT = Path("/Volumes/GM/hswm_lab/phantomwiki_r3")
PREREG = HERE / "PREREG_R3_WALK_REGIME_2026-07-23.json"
EVIDENCE = HERE / "EVIDENCE_R3_WALK_REGIME_2026-07-23.json"
FROZEN_MODULES = ("r3_phantom_ingest.py", "r3_walk_regime.py",
                  "t3_score_null.py", "r1_predicate_alias.py")

MODEL = "all-MiniLM-L6-v2"
TOP_K = 10
SEED_K = 3
MU = 0.1
HARD_HOP = 6
MAX_TRACES = 20
MAX_TRACE_ENTITIES = 8
BOOTSTRAP_REPS = 2000
BOOT_SEED = 9317


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
    if locked["locked_parameters"] != locked_parameters():
        raise RuntimeError("locked parameter drift")
    return locked


def locked_parameters() -> dict:
    return {"model": MODEL, "top_k": TOP_K, "seed_k": SEED_K, "mu": MU,
            "hard_hop": HARD_HOP, "max_traces": MAX_TRACES,
            "max_trace_entities": MAX_TRACE_ENTITIES,
            "bootstrap_reps": BOOTSTRAP_REPS, "boot_seed": BOOT_SEED,
            "universes": sorted(UNIVERSES)}


def trace_golds(question: dict, titles: set[str]) -> list[set[str]]:
    """유효 추론 사슬별 gold 문서 집합 (결정론 상한 적용)."""
    traces = question.get("solution_traces")
    if isinstance(traces, str):
        try:
            traces = json.loads(traces)
        except Exception:
            traces = []
    answers = [a for a in (question.get("answer") or []) if isinstance(a, str)]
    out: list[set[str]] = []
    for tr in (traces or [])[:MAX_TRACES]:
        names = {v for v in (tr or {}).values()
                 if isinstance(v, str) and v in titles}
        if not names or len(names) > MAX_TRACE_ENTITIES:
            continue
        out.append({source_id_for(n) for n in names})
    if not out and answers:
        names = {a for a in answers if a in titles}
        if names and len(names) <= MAX_TRACE_ENTITIES:
            out.append({source_id_for(n) for n in names})
    return out


def best_trace_recall(ranked_sids: list[str], golds: list[set[str]]) -> float:
    top = set(ranked_sids[:TOP_K])
    return max((len(top & g) / len(g) for g in golds), default=0.0)


def paired_bootstrap(values: list[float], seed: int) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(BOOTSTRAP_REPS))
    return means[int(0.025 * BOOTSTRAP_REPS)], means[int(0.975 * BOOTSTRAP_REPS)]


def main() -> int:
    locked = preregistration_guard()
    from sentence_transformers import SentenceTransformer
    import torch
    torch.manual_seed(BOOT_SEED)
    torch.set_num_threads(2)
    model = SentenceTransformer(MODEL, cache_folder="/Volumes/GM/hswm_lab/st_cache")

    def embed(texts: list[str]) -> np.ndarray:
        return model.encode(texts, normalize_embeddings=True,
                            convert_to_numpy=True, batch_size=64,
                            show_progress_bar=False).astype(np.float64)

    policy = typed.TypedCompositionPolicyV1(seed_k=SEED_K)
    per_universe: dict[str, dict] = {}

    for uni in sorted(UNIVERSES):
        articles, questions = load_universe(ROOT / uni)
        target_ids, graph, _, _, stats = build_graph(articles)
        titles = {a["title"] for a in articles}
        title_by_ord = {source_id_for(a["title"]): a["title"] for a in articles}

        doc_texts = [a["article"] for a in sorted(articles, key=lambda x: x["title"])]
        doc_vecs = embed(doc_texts)

        rows = []
        for q in questions:
            if q.get("is_aggregation_question"):
                continue
            golds = trace_golds(q, titles)
            if golds:
                rows.append((q, golds))
        rows.sort(key=lambda r: r[0]["id"])
        q_vecs = embed([q["question"] for q, _ in rows])

        alias_index = build_predicate_alias_index(
            [a.source_predicate.exact for a in graph.arcs]
            + [a.target_predicate.exact for a in graph.arcs
               if a.target_predicate is not None])
        titles_map = {sid: title_by_ord[sid] for sid in target_ids}

        per_query = []
        for (q, golds), qv in zip(rows, q_vecs):
            static = doc_vecs @ qv
            order_flat = np.argsort(-static, kind="stable")[:TOP_K]
            flat_ids = [target_ids[i] for i in order_flat]
            seeds = tuple(int(i) for i in np.argsort(-static, kind="stable")[:SEED_K])
            q_terms = query_term_closure(q["question"])
            _, k2, strict_d2, _ = walk_scores_strict(
                q_terms, static, graph, policy, seeds=seeds,
                alias_index=alias_index)
            order_walk = np.argsort(-k2, kind="stable")[:TOP_K]
            walk_ids = [target_ids[i] for i in order_walk]
            per_query.append({
                "id": q["id"], "hop": int(q.get("difficulty", 0)),
                "flat": best_trace_recall(flat_ids, golds),
                "walk": best_trace_recall(walk_ids, golds),
                "walk_depth2_targets": strict_d2,
            })

        def block(rows_):
            if not rows_:
                return {"n": 0}
            deltas = [r["walk"] - r["flat"] for r in rows_]
            lo, hi = paired_bootstrap(deltas, BOOT_SEED)
            return {
                "n": len(rows_),
                "flat_recall10": round(sum(r["flat"] for r in rows_) / len(rows_), 6),
                "walk_recall10": round(sum(r["walk"] for r in rows_) / len(rows_), 6),
                "delta": round(sum(deltas) / len(deltas), 6),
                "bootstrap95": [round(lo, 6), round(hi, 6)],
                "queries_with_depth2": sum(1 for r in rows_ if r["walk_depth2_targets"] > 0),
            }

        hard = [r for r in per_query if r["hop"] >= HARD_HOP]
        easy = [r for r in per_query if r["hop"] < HARD_HOP]
        per_universe[uni] = {
            "config": UNIVERSES[uni],
            "ingest": {"articles": stats.articles, "facts_bound": stats.facts_bound,
                       "facts_unbound": stats.facts_unbound,
                       "person_arcs": stats.person_arcs},
            "all": block(per_query), "hard_hop": block(hard), "easy_hop": block(easy),
        }
        print(json.dumps({uni: {"hard": per_universe[uni]["hard_hop"],
                                "all": per_universe[uni]["all"]}},
                         ensure_ascii=False), flush=True)

    primary = per_universe["sparse_t200_fk1"]["hard_hop"]["delta"]
    primary_ci = per_universe["sparse_t200_fk1"]["hard_hop"]["bootstrap95"]
    novel = round(primary - per_universe["dense_t200_fk9"]["hard_hop"]["delta"], 6)

    evidence = {
        "schema": "hswm-r3-walk-regime-evidence/v1",
        "programme": "LakatosTree_PromSearchHSWM_20260721",
        "branch": "R3-walk-regime-density-dial",
        "preregistration": {"path": PREREG.name, "sha256": _sha(PREREG),
                            "prediction_receipt_sha256": locked["prediction_receipt_sha256"]},
        "measurement": {
            "metric": "sparse_hardhop_walk_minus_flat_recall10",
            "value": primary,
            "bootstrap95": primary_ci,
            "novel_metric": "density_monotonicity_sparse_minus_dense_delta",
            "novel_value": novel,
            "per_universe": per_universe,
            "size_axis": {u: per_universe[u]["hard_hop"]["delta"]
                          for u in ("small_t2_fk3", "mid_t20_fk3", "large_t200_fk3")},
            "density_axis": {u: per_universe[u]["hard_hop"]["delta"]
                             for u in ("sparse_t200_fk1", "large_t200_fk3", "dense_t200_fk9")},
        },
        "budget": {"llm": 0, "network": 0, "extraction_model": 0,
                   "note": "PhantomWiki facts = deterministic ingest; only MiniLM doc/query embeddings"},
        "limitations": [
            "Synthetic template corpus: language is uniform, so lexical/embedding difficulty is unrepresentative of real prose.",
            "best-trace recall@10 credits any single valid reasoning chain; it is a retrieval-side metric, not answer accuracy.",
            "Walk arm reuses the strict T3 walker with mu-additive scoring; the frozen kernel's exact arithmetic is not reproduced.",
        ],
    }
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(json.dumps({"evidence_sha256": _sha(EVIDENCE), "primary": primary,
                      "primary_ci": primary_ci, "novel": novel,
                      "size_axis": evidence["measurement"]["size_axis"],
                      "density_axis": evidence["measurement"]["density_axis"]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
