#!/usr/bin/env python3
"""B2 oracle-gate headroom 진단 — PROM-8 R4의 선행 관문 (DIAGNOSTIC, 주장 없음).

A4 조사 결론: 게이트 실험(prereg) 전에 oracle 상한을 먼저 재야 한다 — oracle이
(in-field 복구 ∧ cross-field 유지)를 못 하면 문제는 라우팅이 아니라 merge 자체.

이 스크립트는 판정된 B2 하니스(prom_b2_crossfield_merge.py, sha 동결)를 수정하지
않고 그 함수들을 import해 같은 seed(7332)로 결정론 재계산만 한다. LakatoTree
제출 없음, PREREG 없음 — 산출물은 게이트 실험 설계의 입력일 뿐이다.

산출:
  1. oracle(질의별 최적 route) 상한: per-class recall + 복구/유지량
  2. route 선호 분포 (merged 승 / single 승 / tie) per class
  3. 관측가능 신호 1차 점검: field-affinity 마진(|top1_A − top1_B|)이 oracle
     라벨을 얼마나 가르나 (rank-AUC) — A4 kill "AUC<0.75면 신호 약함" 예비 측정
"""
from __future__ import annotations

import json
from pathlib import Path

from prom_b2_crossfield_merge import (
    HERE, LAM_B, LAM_V, N_Q, SEED, TOP_K,
    attach_embeddings, build_field, collect_texts, paragraphs_from_rows,
    rank_paragraphs, recall_at, seam_arcs_between, stratify,
)
from hswm_field_algebra import compose, merge

import random

DATA = Path("/Users/lagyeongjun/CD/SYMPOSIUM/GIT/HSWM/.ab_p5_cache/h3_relation_raw_2wiki.json")
OUT = HERE / "evidence" / "DIAG_b2_oracle_headroom_20260722.json"


def rank_auc(scores_pos: list[float], scores_neg: list[float]) -> float:
    """Mann-Whitney AUC: P(score_pos > score_neg) + 0.5 P(=)."""
    if not scores_pos or not scores_neg:
        return float("nan")
    wins = ties = 0
    for p in scores_pos:
        for n in scores_neg:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    return (wins + 0.5 * ties) / (len(scores_pos) * len(scores_neg))


def main() -> int:
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    rows = raw["rows"] if isinstance(raw, dict) else raw

    usable = []
    for row in rows:
        strat = stratify(row)
        if strat is not None:
            usable.append((row, *strat))
    order = list(range(len(usable)))
    random.Random(SEED).shuffle(order)
    usable = [usable[i] for i in order][:N_Q]

    pool = paragraphs_from_rows([row for row, _, _ in usable])
    f_a, f_b = build_field(pool, "A"), build_field(pool, "B")
    arcs = seam_arcs_between(f_a, f_b)
    f_merged = merge(f_a, f_b, new_seam=arcs)

    from sentence_transformers import SentenceTransformer
    import torch
    torch.manual_seed(SEED)
    model = SentenceTransformer(
        "all-MiniLM-L6-v2", cache_folder="/Volumes/GM/hswm_lab/st_cache")

    def embed_fn(texts):
        return model.encode(texts, normalize_embeddings=True,
                            convert_to_numpy=True, batch_size=128,
                            show_progress_bar=False).tolist()

    questions = [row["question"] for row, _, _ in usable]
    texts = collect_texts([f_a, f_b, f_merged], questions)
    table = dict(zip(texts, embed_fn(texts)))
    for f in (f_a, f_b, f_merged):
        attach_embeddings(f, table)

    per_query = []
    for row, klass, gold in usable:
        qv = table[row["question"]]
        ranked = {}
        top1 = {}
        for name, f in (("a", f_a), ("b", f_b), ("merged", f_merged)):
            pairs = rank_paragraphs(f, qv, top_k=TOP_K, lam_v=LAM_V, lam_b=LAM_B)
            ranked[name] = [eid for eid, _ in pairs]
            top1[name] = pairs[0][1] if pairs else 0.0
        r = {name: recall_at(ids, gold, TOP_K) for name, ids in ranked.items()}
        best_single = max(r["a"], r["b"])
        per_query.append({
            "class": klass,
            "merged": r["merged"],
            "best_single": best_single,
            "oracle": max(r["merged"], best_single),
            "route_pref": ("merged" if r["merged"] > best_single
                           else "single" if best_single > r["merged"] else "tie"),
            "affinity_margin": abs(top1["a"] - top1["b"]),
            "merged_minus_single_top1": top1["merged"] - max(top1["a"], top1["b"]),
        })

    def block(klass: str) -> dict:
        qs = [q for q in per_query if q["class"] == klass]
        n = len(qs)
        mean = lambda k: round(sum(q[k] for q in qs) / n, 6)
        pref = {p: sum(1 for q in qs if q["route_pref"] == p)
                for p in ("merged", "single", "tie")}
        return {"n": n, "merged": mean("merged"), "best_single": mean("best_single"),
                "oracle": mean("oracle"), "route_pref": pref}

    cross, infield = block("cross_field"), block("in_field")

    # 신호 점검: oracle 라벨(단, tie 제외)을 affinity 마진이 가르나.
    single_pref = [q for q in per_query if q["route_pref"] == "single"]
    merged_pref = [q for q in per_query if q["route_pref"] == "merged"]
    auc_affinity = rank_auc([q["affinity_margin"] for q in single_pref],
                            [q["affinity_margin"] for q in merged_pref])
    auc_top1gap = rank_auc([-q["merged_minus_single_top1"] for q in single_pref],
                           [-q["merged_minus_single_top1"] for q in merged_pref])

    diag = {
        "schema": "hswm-diagnostic/v1",
        "kind": "DIAGNOSTIC_NO_CLAIM",
        "purpose": "PROM-8 R4 oracle headroom precondition for the L5 gate experiment",
        "base_experiment": "EVIDENCE_b2_crossfield_merge_20260722.json (seed/params identical)",
        "per_class": {"cross_field": cross, "in_field": infield},
        "oracle_headroom": {
            "in_field_recovery_vs_merged": round(infield["oracle"] - infield["merged"], 6),
            "in_field_oracle_vs_best_single": round(infield["oracle"] - infield["best_single"], 6),
            "cross_field_retention_vs_merged": round(cross["oracle"] - cross["merged"], 6),
        },
        "signal_check": {
            "auc_affinity_margin_single_vs_merged_pref": round(auc_affinity, 4),
            "auc_top1_gap_single_vs_merged_pref": round(auc_top1gap, 4),
            "a4_kill_threshold_note": "A4 조사 kill: AUC<0.75면 무학습 신호 약함 → 학습형(B안)행",
        },
        "note": "oracle=질의별 사후 최적 route. 정의상 in-field는 best_single 이상, cross-field는 merged 이상 — 관건은 실현가능 신호의 분리도(AUC).",
    }
    OUT.write_text(json.dumps(diag, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(diag, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
