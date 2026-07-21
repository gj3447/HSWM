#!/usr/bin/env python3
"""
HSWM fusion engine — PROM Step 3/4 검색 프리미티브.

PROM을 HSWM으로: 인터넷場 + 내부KG場 + raw場을 *무조건 RRF*로 섞지 말고,
場별 관련도를 측정해 가중/게이트 융합(measurement-driven conditional dispatch).

문헌 근거 (THEORY_GROUNDING.md): Cormack 2009 RRF / Balancing-the-Blend arXiv:2508.01405
weakest-link / DAT arXiv:2503.23013 per-query adaptive weight / Markovits CIKM 2012 QPP-fusion.

재사용 API:
  rankings: dict[field_name -> list[float]]  # 각 場이 candidate마다 매긴 score (높을수록 관련)
  fuse(rankings, strategy, anchor='raw', ...) -> list[float] fused score per candidate.
전략: blind / confidence / agreement / gated_agreement.  anchor場(raw)은 항상 신뢰 기준.
"""
from __future__ import annotations
import statistics

RRF_K = 60


def _ranks_from_scores(scores):
    """score 높은 순 → rank(1=best) per index."""
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    rk = [0] * len(scores)
    for r, idx in enumerate(order):
        rk[idx] = r + 1
    return rk


def field_confidence(scores):
    """post-retrieval QPP (NQC/clarity 류): top이 mean서 얼마나 떨어져 확신하나.
    flat 분포(신호 無) → ~0. 단 'confident-but-wrong'은 못 거른다(한계 명시)."""
    if not scores:
        return 0.0
    mx = max(scores); mean = statistics.mean(scores)
    sd = statistics.pstdev(scores) or 1e-9
    return max(0.0, (mx - mean) / sd)


def field_agreement(scores, anchor_scores, top_n=10):
    """anchor場(raw) top-N과 이 場 top-N의 겹침 비율. off-domain場(anchor와 딴판) → 낮음.
    confident-but-wrong을 잡는 핵심 신호: 확신해도 anchor와 어긋나면 down-weight."""
    def top_set(s):
        return set(sorted(range(len(s)), key=lambda i: -s[i])[:top_n])
    a = top_set(scores); b = top_set(anchor_scores)
    return len(a & b) / max(1, len(b))


def _norm_weights(w):
    tot = sum(w.values())
    if tot <= 0:
        return {k: 1.0 / len(w) for k in w}
    return {k: v / tot for k, v in w.items()}


def compute_weights(rankings, strategy, anchor="raw", gate_threshold=0.2, external_weights=None):
    """場별 가중치 + (게이트 시) 배제 목록 반환.  returns (weights: dict, dropped: list)."""
    names = list(rankings)
    dropped = []
    if strategy == "blind":
        return {n: 1.0 for n in names}, dropped
    if strategy == "external":
        # LLM-judge 등 외부 측정 가중치 주입 (DAT식). 0 가중은 배제로 기록.
        w = dict(external_weights or {})
        dropped = [n for n in names if w.get(n, 0.0) <= 0.0 and n != anchor]
        kept = {n: w.get(n, 0.0) for n in names if n not in dropped}
        return _norm_weights(kept), dropped

    anchor_scores = rankings.get(anchor)
    raw_w = {}
    for n in names:
        if strategy == "confidence":
            raw_w[n] = field_confidence(rankings[n])
        elif strategy in ("agreement", "gated_agreement"):
            if n == anchor or anchor_scores is None:
                raw_w[n] = 1.0
            else:
                raw_w[n] = field_agreement(rankings[n], anchor_scores)
        else:
            raise ValueError(f"unknown strategy {strategy}")

    if strategy == "gated_agreement":
        for n in names:
            if n != anchor and raw_w[n] < gate_threshold:
                dropped.append(n)
        raw_w = {n: v for n, v in raw_w.items() if n not in dropped}
        # 게이트 통과 場은 균일(신호 있는 場만 동등 RRF) — Cormack: 비슷한 수준 場엔 무가중이 견고
        return {n: 1.0 for n in raw_w}, dropped

    return _norm_weights(raw_w), dropped


def fuse(rankings, strategy="gated_agreement", anchor="raw", gate_threshold=0.2, k=RRF_K, external_weights=None):
    """가중 RRF. return (fused_scores: list[float], weights, dropped)."""
    weights, dropped = compute_weights(rankings, strategy, anchor, gate_threshold, external_weights)
    n_cand = len(next(iter(rankings.values())))
    field_ranks = {name: _ranks_from_scores(sc) for name, sc in rankings.items() if name in weights}
    fused = [0.0] * n_cand
    for name, w in weights.items():
        rk = field_ranks[name]
        for i in range(n_cand):
            fused[i] += w * (1.0 / (k + rk[i]))
    return fused, weights, dropped


# --- self-test (프리미티브 sanity, 실험 아님) ---
if __name__ == "__main__":
    # 3 candidate, raw+kg가 cand0을 신뢰, web은 cand2를 confident-but-wrong로 밀어올림
    R = {"raw": [0.9, 0.3, 0.1], "kg": [0.8, 0.2, 0.1], "web": [0.1, 0.2, 0.95]}
    for strat in ("blind", "confidence", "agreement", "gated_agreement"):
        fused, w, dropped = fuse(R, strat)
        top = max(range(3), key=lambda i: fused[i])
        print(f"{strat:16s} top=cand{top} weights={ {k: round(v,2) for k,v in w.items()} } dropped={dropped}")
    print("expect: blind/confidence 은 web에 흔들릴 수 있고, agreement/gated 는 cand0 유지")
