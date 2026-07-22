#!/usr/bin/env python3
"""prom_p1_binding_density — P1 binding density judge (W1-T2).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node P1-binding-density.
사전등록 원문 준수 (2026-07-21T03:59:44Z 등록, 무변경):
- pred_metric        = held_out_binding_density   (baseline 0.05, noise 0.03, higher, ratio)
- pred_novel_metric  = semantic_minus_lexical_binding_gap (threshold 0.2, higher)
- pred_closes        = Q-binding-density
- frontier_rule: "lexical→semantic 치환은 held-out gold set 성능 + MC-null 캘리브레이션 τ
  없이는 progressive 승격 금지". binding density 정의 = "외부 finding이 내부 KG에
  cosine≥τ로 바인딩되는 비율".

이 스크립트 자체가 judge (기존 트리 패턴). 측정 로직:
- gold = data/binding_gold_p1.json (W1-T1 동결, n=66; SEED=333 calibration/eval 33/33).
- τ = calibration split 전용 MC-null 캘리브레이션 (prom_binding_common.tau_from_gold —
  mismatched-pair cosine null_mean + 3·null_std, gold 튜닝 없음, 완전 결정론).
- 측정은 eval(held-out) split 33 finding 에서만.
- candidate pool = 전역 target_pool ∪ distractor_pool (113 후보, T::/D:: prefix 규약 —
  τ 절차와 동일 풀, per-finding 축소 없음).
- lexical arm  (현 PROM Step 2.5 CONTAINS 재현): finding이 bound ⟺ 어느 gold target과
  정규화 CONTAINS 매치 (prom_binding_common.norm_contains).
- semantic arm: finding이 bound ⟺ top-1 후보 cosine ≥ τ AND top-1 = gold target.
- value = semantic held_out_binding_density, novel_measured = semantic − lexical gap.

동반 기록 (_facts = 부울·수치만, 자기채점 금지):
- MC-null permutation z (gold 배정 순열, NULL_PERMS=2000, SEED=333 — mc_null_z 재사용)
- precision (과병합 Goodhart 가드 — P2 교훈): fires(top1 cos≥τ) 중 top1=gold 비율
- τ sweep 투명성 (prom_consensus_bench.py L149-152 패턴)

금지 라인 (반증 종결 — 코드에 부재함을 명기): entity 정점추가(V∪E 종결) /
naive semantic-on-recommendation(P2b MC-null z=0.189 REFUTED) / 의미 엣지가중(ML17) /
GCNII 딥스택(ML19) / 재투영 다층. 이 스크립트는 flat cosine top-1 바인딩 판정만 한다.

실행: ./run_on_gm.sh prom_p1_binding_density.py  (GM 마운트 필수, 모델캐시 GM)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import prom_binding_common as C

HERE = Path(__file__).parent
EVIDENCE_PATH = HERE / "evidence" / "EVIDENCE_p1_binding_density_2026-07-22.json"
NODE = "P1-binding-density"

# 사전등록 원문 (LakatoTree 노드에서 전사 — 변경 금지)
PREREG = {
    "metric": "held_out_binding_density",
    "baseline": 0.05,
    "noise_band": 0.03,
    "direction": "higher",
    "scale_type": "ratio",
    "novel_metric": "semantic_minus_lexical_binding_gap",
    "novel_direction": "higher",
    "novel_threshold": 0.2,
    "closes": "Q-binding-density",
    "registered_at": "2026-07-21T03:59:44.351379+00:00",
}

TAU_SWEEP_GRID = [0.30, 0.40, 0.50, 0.60, 0.70]


def density_and_precision(top1_idx, top1_cos, gold_sets, cand_ids, tau):
    """semantic arm: density = P(top1 cos≥τ ∧ top1∈gold), precision = 그중 fires 대비."""
    n = len(top1_idx)
    fires = 0
    correct = 0
    for i in range(n):
        if top1_cos[i] >= tau:
            fires += 1
            if cand_ids[top1_idx[i]] in gold_sets[i]:
                correct += 1
    density = correct / n if n else 0.0
    precision = correct / fires if fires else 0.0
    return density, precision, fires, correct


def main():
    import numpy as np

    # --- gold (frozen) + split 검증 ---
    gold = C.load_gold()
    C.verify_split(gold)
    fins_eval = [f for f in gold["findings"] if f["split"] == "eval"]
    n_eval = len(fins_eval)
    n_cal = sum(1 for f in gold["findings"] if f["split"] == "calibration")

    # --- τ: calibration split 전용 MC-null 캘리브레이션 (gold 튜닝 없음) ---
    tau_info = C.tau_from_gold(gold, subset="calibration")
    tau = tau_info["tau"]

    # --- 후보 풀 (전역, τ 절차와 동일) + 임베딩 ---
    cand_ids, cand_texts, _is_target = C.build_candidate_pool(gold)
    fin_emb = C.embed([f["finding_text"] for f in fins_eval])
    cand_emb = C.embed(cand_texts)
    cos = C.cosine_matrix(fin_emb, cand_emb)  # (n_eval, n_cand)

    gold_sets = [{f"T::{tid}" for tid in f["gold_target_ids"]} for f in fins_eval]
    top1_idx = [int(np.argmax(cos[i])) for i in range(n_eval)]
    top1_cos = [float(cos[i][top1_idx[i]]) for i in range(n_eval)]

    # --- semantic arm (held_out_binding_density) ---
    sem_density, sem_precision, sem_fires, sem_correct = density_and_precision(
        top1_idx, top1_cos, gold_sets, cand_ids, tau)

    # --- lexical arm (현 PROM Step 2.5 정규화 CONTAINS 재현) ---
    cand_text_by_id = dict(zip(cand_ids, cand_texts))
    lex_bound = 0
    lex_any_match = 0          # CONTAINS가 어느 후보든 문 finding 수 (투명성)
    lex_nongold_matches = 0    # CONTAINS가 비gold 후보를 문 총 횟수 (과병합 투명성)
    for i, f in enumerate(fins_eval):
        ft = f["finding_text"]
        hit_gold = any(C.norm_contains(ft, cand_text_by_id[g])
                       for g in gold_sets[i] if g in cand_text_by_id)
        any_hit = False
        for cid in cand_ids:
            if C.norm_contains(ft, cand_text_by_id[cid]):
                any_hit = True
                if cid not in gold_sets[i]:
                    lex_nongold_matches += 1
        lex_bound += hit_gold
        lex_any_match += any_hit
    lex_density = lex_bound / n_eval if n_eval else 0.0

    # --- 사전등록 metric ---
    value = sem_density                      # held_out_binding_density
    gap = sem_density - lex_density          # semantic_minus_lexical_binding_gap

    # --- MC-null: eval gold 배정 순열 하에서 semantic density 분포 ---
    def stat_under_null(rng):
        perm = gold_sets[:]
        rng.shuffle(perm)
        c = sum(1 for i in range(n_eval)
                if top1_cos[i] >= tau and cand_ids[top1_idx[i]] in perm[i])
        return c / n_eval

    z, null_mean, null_std = C.mc_null_z(sem_density, stat_under_null)

    # --- τ sweep 투명성 (판정에 불사용 — 사전등록 τ 절차는 위 하나뿐) ---
    sweep = {}
    for t in TAU_SWEEP_GRID + [round(tau, 4)]:
        d, p, fi, _ = density_and_precision(top1_idx, top1_cos, gold_sets, cand_ids, t)
        sweep[f"{t:.4f}"] = {"density": round(d, 4), "precision": round(p, 4), "fires": fi}

    # --- evidence ---
    ev = C.evidence_skeleton(
        experiment="prom_p1_binding_density",
        node=NODE,
        a_priori={"seed": C.SEED, "null_perms": C.NULL_PERMS, "model": C.MODEL_NAME,
                  "tau_rule": "calibration mismatched-pair null_mean + 3*null_std",
                  "tau_k_sigma": C.TAU_K_SIGMA},
        prereg=PREREG,
    )
    ev["gold"] = {
        "path": "data/binding_gold_p1.json",
        "sha256": hashlib.sha256((HERE / "data" / "binding_gold_p1.json").read_bytes()).hexdigest(),
        "n_findings": gold["n_findings"], "n_calibration": n_cal, "n_eval": n_eval,
        "n_candidates": len(cand_ids), "n_targets": len(gold["target_pool"]),
        "n_distractors": len(gold["distractor_pool"]),
        "split_seed": gold["seed"], "overlapping": True,
    }
    ev["tau_calibration"] = {k: (round(v, 6) if isinstance(v, float) else v)
                             for k, v in tau_info.items()}
    ev["lexical_current_prom"] = {
        "binding_density": round(lex_density, 4),
        "bound": lex_bound, "any_contains_match": lex_any_match,
        "nongold_contains_matches": lex_nongold_matches,
        "note": "정규화 CONTAINS (PROM Step 2.5 재현), gold target 매치 = bound",
    }
    ev["semantic"] = {
        "binding_density": round(sem_density, 4),
        "precision": round(sem_precision, 4),
        "fires": sem_fires, "correct": sem_correct,
        "tau": round(tau, 6),
        "rule": "top-1 cosine >= tau AND top-1 in gold targets",
    }
    ev["value_held_out_binding_density"] = round(value, 4)
    ev["novel_semantic_minus_lexical_binding_gap"] = round(gap, 4)
    ev["mc_null"] = {"null_mean_density": round(null_mean, 4),
                     "null_std": round(null_std, 4), "z": round(z, 3),
                     "perms": C.NULL_PERMS,
                     "null": "eval gold 배정 순열 (top-1/τ 고정)"}
    ev["tau_sweep"] = sweep
    # 사실만 기록 — 판정은 LakatoTree 서버 (자기채점 금지)
    ev["_facts"] = C.check_facts({
        "n_eval": n_eval,
        "n_calibration": n_cal,
        "seed": C.SEED,
        "tau": round(tau, 6),
        "value": round(value, 4),
        "novel_gap": round(gap, 4),
        "mc_null_z": round(z, 3),
        "value_above_baseline_plus_noise": value > PREREG["baseline"] + PREREG["noise_band"],
        "novel_gap_ge_threshold": gap >= PREREG["novel_threshold"],
        "semantic_above_null": z > 3.0,
        "precision": round(sem_precision, 4),
        "precision_not_collapsed": sem_precision >= 0.8 or sem_precision >= (
            lex_bound / lex_any_match if lex_any_match else 0.0),
    })
    C.write_evidence(ev, EVIDENCE_PATH)
    with open(EVIDENCE_PATH, "a", encoding="utf-8") as fh:
        fh.write("\n")  # repo end-of-file-fixer 규약 — 커밋본과 byte-identical 유지

    print(json.dumps(ev, ensure_ascii=False, indent=2))
    digest = hashlib.sha256(json.dumps(ev["_facts"], sort_keys=True).encode()).hexdigest()
    print(f"\nEVIDENCE -> {EVIDENCE_PATH}", file=sys.stderr)
    print(f"P1 OK facts_digest={digest}", file=sys.stderr)


if __name__ == "__main__":
    main()
