#!/usr/bin/env python3
"""prom_p4_equalcompute_ab — P4 equal-compute control A/B judge (W1-T3).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node P4-equal-compute-control.
사전등록 원문 준수 (2026-07-21T03:59:52Z 등록, 무변경):
- pred_metric        = semantic_minus_equalcompute_binding_gain (baseline 0.0, noise 0.03,
                       higher, ratio)
- pred_novel_metric  = semantic_layer_over_more_blind_search_gap (threshold 0.1, higher)
- pred_closes        = Q-real-gain-vs-compute
- 예측 원문: "semantic weave 이득이 equal-compute control(같은 토큰을 더 많은 맹목
  웹검색에 쓴 arm)을 이긴다. null=이득 0(그냥 검색 더 많이의 재포장). 이 예측이
  null이면 전체 프로그램 degenerating."
- tree hard_core 불변식 (iii)이 이 노드 자체: "개선은 equal-compute control을 이겨야만
  인정(그냥 N↑ 아님)".

이 스크립트 자체가 judge (기존 트리 패턴). 3-arm — 동일 gold·동일 candidate pool:
- gold = data/binding_gold_p1.json (W1-T1 동결, P1과 공유; n=66, SEED=333 split 33/33).
- candidate pool = 전역 target_pool ∪ distractor_pool (113 후보, T::/D:: prefix,
  P1/τ 절차와 동일 풀). 측정은 eval(held-out) 33 finding 에서만.
- τ = P1과 동일 캘리브레이션 절차 (prom_binding_common.tau_from_gold — calibration split
  전용 mismatched-pair cosine null_mean + 3·null_std, gold 튜닝 없음, 완전 결정론).

arm1 lexical_1x (현 PROM baseline): 정규화 Jaccard 토큰 매칭 1패스
  (prom_binding_common.toks = prom_legend_recall.py L63-65 토크나이저; Jaccard =
  lexical_rank L67-76 동일 수식). bound ⟺ top-1 후보가 gold target AND Jaccard>0.
  + P1 lexical arm(정규화 CONTAINS) 밀도도 교차참조로 병기 (판정 불사용).

arm2 equalcompute_lexical (control): 같은 compute 예산을 더 많은 맹목 lexical 검색에
  투입 — finding 텍스트 파생 query 변형 다발(전문/토큰 n-gram 윈도/희소 키워드 추출/
  라틴·한글 정규화 변형/제목head) 각각을 전 후보(깊은 k = 전수 113 스캔)에 Jaccard
  스코어 → rank-union = blind RRF (hswm_fusion.py fuse(strategy='blind') 재사용 —
  control arm의 rank-union 전용; ML5의 '융합 개선 주장' 부활 아님).
  bound ⟺ RRF top-1 후보가 gold target AND 그 후보가 ≥1 변형에서 Jaccard>0.
  compute 회계 (사전선언): primary = 스코어링 처리 (query토큰수×후보토큰수) 총량
  (토큰수 = _TOK 매치 수, 비유니크), secondary(robustness) = wall-clock CPU초.
  assert lexical_budget >= semantic_budget — 양쪽 예산을 _facts에 기록
  (_facts.equal_compute_verified).

arm3 semantic_weave: 임베딩 cosine 바인딩 1패스 (P1과 동일 모델
  paraphrase-multilingual-MiniLM-L12-v2, 동일 규칙: top-1 cosine≥τ AND top-1=gold).

측정 (사전등록 그대로):
- value = binding_density(semantic_weave) − binding_density(equalcompute_lexical)
        = semantic_minus_equalcompute_binding_gain
- novel_measured = 같은 gap = semantic_layer_over_more_blind_search_gap
- MC-null permutation z 동반 (eval gold 배정 순열, NULL_PERMS=2000, SEED=333) —
  z<3이면 사실만 기록 (자기채점 금지, _facts는 부울·수치만).

금지 라인 (반증 종결 — 코드에 부재함을 명기): entity 정점추가(V∪E 종결) /
naive semantic-on-recommendation(P2b REFUTED) / 의미 엣지가중 Theta_sem(ML17) /
GCNII 딥스택(ML19) / 재투영 다층. blind RRF는 control arm의 rank-union 도구로만 사용.

실행: ./run_on_gm.sh prom_p4_equalcompute_ab.py  (GM 마운트 필수, 모델캐시 GM —
W1-T2에서 이미 캐시됨)
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import prom_binding_common as C

HERE = Path(__file__).parent
EVIDENCE_PATH = HERE / "evidence" / "EVIDENCE_p4_equalcompute_2026-07-22.json"
NODE = "P4-equal-compute-control"

# 사전등록 원문 (LakatoTree 노드에서 전사 — 변경 금지)
PREREG = {
    "metric": "semantic_minus_equalcompute_binding_gain",
    "baseline": 0.0,
    "noise_band": 0.03,
    "direction": "higher",
    "scale_type": "ratio",
    "novel_metric": "semantic_layer_over_more_blind_search_gap",
    "novel_direction": "higher",
    "novel_threshold": 0.1,
    "closes": "Q-real-gain-vs-compute",
    "registered_at": "2026-07-21T03:59:52.782999+00:00",
}

NGRAM_WINDOW = 6
NGRAM_STRIDE = 3
N_KEYWORDS = 8
N_HEAD = 10


def ordered_toks(s: str) -> list:
    """순서 보존 토큰열 (C.toks와 동일 정규식 _TOK, set 아님 — n-gram/예산 계수용)."""
    return C._TOK.findall(s.lower())


def query_variants(finding_text: str, df: dict) -> dict:
    """finding 텍스트 파생 결정론 query 변형 다발 (맹목 lexical 검색 확장).

    df: 후보 풀 내 토큰 document frequency (희소 키워드 추출용 — gold 정보 불사용).
    """
    ot = ordered_toks(finding_text)
    variants = {"full": finding_text}
    # 토큰 n-gram 윈도 분해
    for wi, start in enumerate(range(0, max(1, len(ot) - NGRAM_WINDOW + 1), NGRAM_STRIDE)):
        win = ot[start:start + NGRAM_WINDOW]
        if len(win) >= 2:
            variants[f"ngram{wi:02d}"] = " ".join(win)
    # 희소 키워드 추출 (후보 풀 df 오름차순 → 희소 우선, 동률은 토큰 사전순)
    uniq = sorted(set(ot), key=lambda t: (df.get(t, 0), t))
    if uniq:
        variants["keywords"] = " ".join(uniq[:N_KEYWORDS])
    # 정규화 변형: 라틴만 / 한글만
    latin = [t for t in ot if t[0].isascii()]
    hangul = [t for t in ot if "가" <= t[0] <= "힣"]
    if latin:
        variants["latin_only"] = " ".join(latin)
    if hangul:
        variants["hangul_only"] = " ".join(hangul)
    # 제목/head 추출
    if len(ot) >= 2:
        variants["head"] = " ".join(ot[:N_HEAD])
    return variants


def jaccard_scores(query: str, cand_tok_sets: list) -> list:
    """후보 순서 정렬 Jaccard 점수 (prom_legend_recall.py lexical_rank L67-76 수식)."""
    qt = C.toks(query)
    out = []
    for ct in cand_tok_sets:
        inter = len(qt & ct)
        out.append(inter / (len(qt | ct) or 1))
    return out


def argmax_first(scores) -> int:
    """결정론 top-1: 최대값 중 최소 index (후보 순서 = T:: 정렬 후 D:: 정렬)."""
    best = max(scores)
    return scores.index(best)


def main():
    import numpy as np

    # --- gold (frozen, P1과 공유) + split 검증 ---
    gold = C.load_gold()
    C.verify_split(gold)
    fins_eval = [f for f in gold["findings"] if f["split"] == "eval"]
    n_eval = len(fins_eval)
    n_cal = sum(1 for f in gold["findings"] if f["split"] == "calibration")

    # --- τ: P1과 동일 캘리브레이션 절차 (calibration split 전용, gold 튜닝 없음) ---
    tau_info = C.tau_from_gold(gold, subset="calibration")
    tau = tau_info["tau"]

    # --- 후보 풀 (전역, P1/τ 절차와 동일) ---
    cand_ids, cand_texts, _is_target = C.build_candidate_pool(gold)
    n_cand = len(cand_ids)
    cand_tok_sets = [C.toks(t) for t in cand_texts]
    cand_tok_counts = [len(ordered_toks(t)) for t in cand_texts]
    total_cand_tokens = sum(cand_tok_counts)
    gold_sets = [{f"T::{tid}" for tid in f["gold_target_ids"]} for f in fins_eval]

    # 후보 풀 토큰 document frequency (키워드 변형용 — gold 정보 불사용)
    df: dict = {}
    for ct in cand_tok_sets:
        for t in ct:
            df[t] = df.get(t, 0) + 1

    # ---------------- arm3 semantic_weave (1패스, P1 규칙 동일) ----------------
    t0 = time.process_time()
    fin_emb = C.embed([f["finding_text"] for f in fins_eval])
    cand_emb = C.embed(cand_texts)
    cos = C.cosine_matrix(fin_emb, cand_emb)  # (n_eval, n_cand)
    sem_top1_idx = [int(np.argmax(cos[i])) for i in range(n_eval)]
    sem_top1_cos = [float(cos[i][sem_top1_idx[i]]) for i in range(n_eval)]
    sem_cpu_s = time.process_time() - t0

    sem_fire = [sem_top1_cos[i] >= tau for i in range(n_eval)]
    sem_bound = [sem_fire[i] and cand_ids[sem_top1_idx[i]] in gold_sets[i]
                 for i in range(n_eval)]
    sem_density = sum(sem_bound) / n_eval
    sem_fires = sum(sem_fire)
    sem_correct = sum(sem_bound)
    sem_precision = sem_correct / sem_fires if sem_fires else 0.0

    # semantic 예산 (primary, 사전선언 단위): Σ_i Σ_j |toks(f_i)| × |toks(c_j)|
    fin_tok_counts = [len(ordered_toks(f["finding_text"])) for f in fins_eval]
    sem_budget = sum(fc * total_cand_tokens for fc in fin_tok_counts)

    # ---------------- arm1 lexical_1x (현 PROM baseline, 1패스) ----------------
    t0 = time.process_time()
    lex1_bound = []
    lex1_top1_nonzero = 0
    for i, f in enumerate(fins_eval):
        sc = jaccard_scores(f["finding_text"], cand_tok_sets)
        j = argmax_first(sc)
        nz = sc[j] > 0.0
        lex1_top1_nonzero += nz
        lex1_bound.append(nz and cand_ids[j] in gold_sets[i])
    lex1_cpu_s = time.process_time() - t0
    lex1_density = sum(lex1_bound) / n_eval
    lex1_budget = sem_budget  # 동일 1패스: 같은 query×후보 토큰곱

    # 교차참조: P1 lexical arm(정규화 CONTAINS) 재현 (판정 불사용)
    cand_text_by_id = dict(zip(cand_ids, cand_texts))
    contains_bound = sum(
        1 for i, f in enumerate(fins_eval)
        if any(C.norm_contains(f["finding_text"], cand_text_by_id[g])
               for g in gold_sets[i] if g in cand_text_by_id))
    contains_density = contains_bound / n_eval

    # ------------- arm2 equalcompute_lexical (control: 변형 다발 + RRF) -------------
    t0 = time.process_time()
    eq_bound = []
    eq_top1_ids = []            # MC-null용 고정 top-1
    eq_top1_support_flags = []  # MC-null용 고정 게이트
    eq_budget = 0
    n_variants_total = 0
    for i, f in enumerate(fins_eval):
        variants = query_variants(f["finding_text"], df)
        n_variants_total += len(variants)
        rankings = {}
        support = [False] * n_cand  # 어느 변형에서든 Jaccard>0인 후보
        for vname, vtext in variants.items():
            eq_budget += len(ordered_toks(vtext)) * total_cand_tokens
            sc = jaccard_scores(vtext, cand_tok_sets)
            rankings[vname] = sc
            for j, s in enumerate(sc):
                if s > 0.0:
                    support[j] = True
        fused = C.rrf_fuse(rankings)  # blind RRF rank-union (전수 113 = 깊은 k 스캔)
        j = argmax_first(fused)
        eq_top1_ids.append(cand_ids[j])
        eq_top1_support_flags.append(support[j])
        eq_bound.append(support[j] and cand_ids[j] in gold_sets[i])
    eq_cpu_s = time.process_time() - t0
    eq_density = sum(eq_bound) / n_eval
    eq_top1_supported = sum(eq_top1_support_flags)

    # --- equal-compute assert (primary 단위, 사전선언) ---
    assert eq_budget >= sem_budget, (
        f"equal-compute 미충족: lexical_budget={eq_budget} < semantic_budget={sem_budget}")
    equal_compute_verified = eq_budget >= sem_budget

    # ---------------- 사전등록 metric ----------------
    value = sem_density - eq_density          # semantic_minus_equalcompute_binding_gain
    gap = value                               # semantic_layer_over_more_blind_search_gap

    # --- MC-null: eval gold 배정 순열 하에서 gap 분포 (양 arm top-1/게이트 고정) ---
    def stat_under_null(rng):
        perm = gold_sets[:]
        rng.shuffle(perm)
        s = sum(1 for i in range(n_eval)
                if sem_fire[i] and cand_ids[sem_top1_idx[i]] in perm[i])
        e = sum(1 for i in range(n_eval)
                if eq_top1_support_flags[i] and eq_top1_ids[i] in perm[i])
        return (s - e) / n_eval

    z, null_mean, null_std = C.mc_null_z(value, stat_under_null)

    # ---------------- evidence ----------------
    ev = C.evidence_skeleton(
        experiment="prom_p4_equalcompute_ab",
        node=NODE,
        a_priori={"seed": C.SEED, "null_perms": C.NULL_PERMS, "model": C.MODEL_NAME,
                  "tau_rule": "calibration mismatched-pair null_mean + 3*null_std (P1 공유)",
                  "tau_k_sigma": C.TAU_K_SIGMA,
                  "compute_budget_primary": "스코어링 처리 (query토큰수×후보토큰수) 총량"
                                            " — 토큰수 = _TOK 매치 수(비유니크)",
                  "compute_budget_secondary": "wall-clock CPU초 (robustness, 비결정론)",
                  "variant_params": {"ngram_window": NGRAM_WINDOW,
                                     "ngram_stride": NGRAM_STRIDE,
                                     "n_keywords": N_KEYWORDS, "n_head": N_HEAD}},
        prereg=PREREG,
    )
    ev["gold"] = {
        "path": "data/binding_gold_p1.json",
        "sha256": hashlib.sha256((HERE / "data" / "binding_gold_p1.json").read_bytes()).hexdigest(),
        "n_findings": gold["n_findings"], "n_calibration": n_cal, "n_eval": n_eval,
        "n_candidates": n_cand, "n_targets": len(gold["target_pool"]),
        "n_distractors": len(gold["distractor_pool"]),
        "split_seed": gold["seed"], "shared_with_p1": True,
    }
    ev["tau_calibration"] = {k: (round(v, 6) if isinstance(v, float) else v)
                             for k, v in tau_info.items()}
    ev["arm1_lexical_1x"] = {
        "binding_density": round(lex1_density, 4),
        "bound": sum(lex1_bound), "top1_nonzero": lex1_top1_nonzero,
        "rule": "Jaccard top-1 in gold AND jaccard>0 (1패스)",
        "contains_crossref_density": round(contains_density, 4),
        "contains_crossref_bound": contains_bound,
    }
    ev["arm2_equalcompute_lexical"] = {
        "binding_density": round(eq_density, 4),
        "bound": sum(eq_bound), "top1_supported": eq_top1_supported,
        "n_variants_total": n_variants_total,
        "mean_variants_per_finding": round(n_variants_total / n_eval, 2),
        "scan_depth_k": n_cand,
        "rule": "blind-RRF rank-union top-1 in gold AND top-1 has jaccard>0 in >=1 variant",
    }
    ev["arm3_semantic_weave"] = {
        "binding_density": round(sem_density, 4),
        "precision": round(sem_precision, 4),
        "fires": sem_fires, "correct": sem_correct,
        "tau": round(tau, 6),
        "rule": "top-1 cosine >= tau AND top-1 in gold targets (P1 동일)",
    }
    ev["compute_budget"] = {
        "primary_unit": "query_tokens x candidate_tokens scored (total)",
        "semantic_budget_tokens": sem_budget,
        "equalcompute_budget_tokens": eq_budget,
        "lexical_1x_budget_tokens": lex1_budget,
        "equalcompute_over_semantic_ratio": round(eq_budget / sem_budget, 3),
        "equal_compute_verified": equal_compute_verified,
        "secondary_unit": "process CPU seconds (비결정론 — 참고용)",
        "semantic_cpu_s": round(sem_cpu_s, 2),
        "equalcompute_cpu_s": round(eq_cpu_s, 2),
        "lexical_1x_cpu_s": round(lex1_cpu_s, 2),
        "secondary_note": "semantic CPU에는 임베딩 비용 포함 — primary(토큰곱) 단위가"
                          " 사전선언 회계 (prereg '같은 토큰예산'); secondary는 투명성 기록",
    }
    ev["value_semantic_minus_equalcompute_binding_gain"] = round(value, 4)
    ev["novel_semantic_layer_over_more_blind_search_gap"] = round(gap, 4)
    ev["mc_null"] = {"null_mean_gap": round(null_mean, 4),
                     "null_std": round(null_std, 4), "z": round(z, 3),
                     "perms": C.NULL_PERMS,
                     "null": "eval gold 배정 순열 (양 arm top-1/게이트 고정)"}
    # 사실만 기록 — 판정은 LakatoTree 서버 (자기채점 금지)
    ev["_facts"] = C.check_facts({
        "n_eval": n_eval,
        "n_calibration": n_cal,
        "seed": C.SEED,
        "tau": round(tau, 6),
        "semantic_binding_density": round(sem_density, 4),
        "equalcompute_binding_density": round(eq_density, 4),
        "lexical_1x_binding_density": round(lex1_density, 4),
        "value": round(value, 4),
        "novel_gap": round(gap, 4),
        "mc_null_z": round(z, 3),
        "semantic_budget_tokens": sem_budget,
        "equalcompute_budget_tokens": eq_budget,
        "equal_compute_verified": equal_compute_verified,
        "value_above_baseline_plus_noise": value > PREREG["baseline"] + PREREG["noise_band"],
        "novel_gap_ge_threshold": gap >= PREREG["novel_threshold"],
        "gap_above_null": z > 3.0,
        "semantic_precision": round(sem_precision, 4),
    })
    C.write_evidence(ev, EVIDENCE_PATH)
    with open(EVIDENCE_PATH, "a", encoding="utf-8") as fh:
        fh.write("\n")  # repo end-of-file-fixer 규약 — 커밋본과 byte-identical 유지

    print(json.dumps(ev, ensure_ascii=False, indent=2))
    digest = hashlib.sha256(json.dumps(ev["_facts"], sort_keys=True).encode()).hexdigest()
    print(f"\nEVIDENCE -> {EVIDENCE_PATH}", file=sys.stderr)
    print(f"P4 OK facts_digest={digest}", file=sys.stderr)


if __name__ == "__main__":
    main()
