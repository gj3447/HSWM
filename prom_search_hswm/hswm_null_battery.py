#!/usr/bin/env python3
"""
HSWM null battery + confound audit — F2~F5 공용 대조군/감사 코어 (B0 슬라이스).

seed-rf-hswm4-null-battery-confound-audit-20260725 (PROM 16 consensus C2/C3):
강한 null이 결정적 — naive/random 대조가 자주 이긴다 (C1 clique kill 일반화).
오탐 차단 4게이트: freeze ablation / headroom band / 이종 judge / leakage 감사.

컴포넌트 (전부 결정론, stdlib-only):
  headroom_band_ok            — p1v2형 포화 방지 (base 정답률 30~70%만 채택)
  deranged_placebo_store      — SHA-deranged placebo (동일 스키마/토큰, 무관 내용, 고정점 0)
  random_edit_plan            — same-size random edit (F2 arm b: 동일 편집 수, 랜덤 타깃)
  degree_preserving_shuffle   — F4 arm B null: 노드 재라벨로 degree sequence·엣지 크기 보존
  make_canary / canary_detected — planted-ground-truth 침투 감사 (A4/B3)
  disjoint_audit              — 3등급 disjoint 감사: exact + token-Jaccard near-dup
  run_verdict                 — run 무효 조건 집계 (freeze/judge sha 변경, leakage>0, replay 실패)

정직 경계: 이 모듈은 대조군 생성과 감사 판정만 소유한다. 어떤 arm의 성능 주장도
  여기서 하지 않는다 — sealed run + 서버 replay + 장부 판정은 게이트 하네스의 일.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass


def _rng(seed: str, purpose: str) -> random.Random:
    """목적별 스트림 분리 결정론 RNG."""
    return random.Random(f"hswm-null-battery:{seed}:{purpose}")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- (h) headroom band (finding a3: 포화/바닥 태스크에서 개입 효과 측정 불가) ---

def headroom_band_ok(base_accuracy: float, lo: float = 0.3, hi: float = 0.7) -> bool:
    """base(frozen/no-memory) 정답률이 [lo, hi] 안이어야 개입 효과 측정 가능.
    >= hi = p1v2형 포화 (재등록 필요), <= lo = 바닥 (신호 없음)."""
    return lo <= base_accuracy <= hi


# --- (a) SHA-deranged placebo store (finding a4: form==content 효과 검출) ---

def deranged_placebo_store(store: dict[str, str], content_pool: list[str],
                           seed: str) -> dict[str, str]:
    """동일 id 집합·동일 스키마를 유지하되 내용은 무관 풀로 교체한 placebo.
    진짜 스토어와 형식(키, 개수, 대략 토큰 길이)만 같고 의미만 다르다.
    content_pool 길이가 store보다 작으면 실패(fail-closed) — 채우기 반복 금지."""
    if len(content_pool) < len(store):
        raise ValueError("content_pool must be >= store size (no reuse)")
    r = _rng(seed, "placebo")
    pool = list(content_pool)
    r.shuffle(pool)
    return {k: pool[i] for i, k in enumerate(sorted(store))}


# --- (b) same-size random edit (finding a1: '아무 변화나 도움' 대조) ---

@dataclass(frozen=True)
class EditPlan:
    """동일 편집 수를 보장하는 랜덤 편집 계획 (credit-informed arm과 1:1 매칭)."""
    inserts: tuple[str, ...]    # 새로 삽입할 항목 id (외부 풀에서)
    deletes: tuple[str, ...]    # 삭제 대상 id
    reweights: tuple[tuple[str, float], ...]  # (id, multiplier)

    def size(self) -> int:
        return len(self.inserts) + len(self.deletes) + len(self.reweights)


def random_edit_plan(store_ids: list[str], n_insert: int, n_delete: int,
                     n_reweight: int, seed: str) -> EditPlan:
    """타깃만 랜덤인 동일-크기 편집. multiplier ∈ [0.5, 1.5] 결정론."""
    if n_delete + n_reweight > len(store_ids):
        raise ValueError("edit targets exceed store size")
    r = _rng(seed, "random-edit")
    targets = r.sample(sorted(store_ids), n_delete + n_reweight)
    deletes = tuple(targets[:n_delete])
    reweights = tuple((t, 0.5 + r.random()) for t in targets[n_delete:])
    inserts = tuple(f"rand-ins-{_sha(seed + str(i))[:12]}" for i in range(n_insert))
    return EditPlan(inserts=inserts, deletes=deletes, reweights=reweights)


# --- (d) F4 arm B null: degree-preserving shuffle (finding c4) ---

def degree_preserving_shuffle(hyperedges: list[list[str]], seed: str) -> list[list[str]]:
    """노드 재라벨 π로 위상을 셔플. 각 노드의 degree와 각 엣지의 크기·총 엣지 수는
    정확히 보존 (π는 전단사) — '구조가 인과적 일을 하는가'의 대조군."""
    nodes = sorted({v for e in hyperedges for v in e})
    r = _rng(seed, "topo-shuffle")
    perm = list(nodes)
    r.shuffle(perm)
    pi = dict(zip(nodes, perm))
    return [sorted(pi[v] for v in e) for e in hyperedges]


def bipartite_degree_preserving_shuffle(edges: list[tuple[str, str]],
                                        right_nodes: list[str],
                                        seed: str) -> list[tuple[str, str]]:
    """Bipartite (anchor ↔ lesson) degree-preserving shuffle (F4-r2 arm B).
    오른쪽(레슨) 노드만 전단사 π로 재라벨 — 앵커(왼쪽) degree는 정확히 보존,
    레슨 측 degree sequence는 multiset으로 보존, 총 엣지 수 보존.
    right_nodes 는 레슨 측 전체 노드(고립 노드 포함)여야 degree sequence가 정확."""
    if not edges:
        return []
    right = sorted(set(right_nodes))
    r = _rng(seed, "bipartite-shuffle")
    perm = list(right)
    r.shuffle(perm)
    pi = dict(zip(right, perm))
    return sorted((anchor, pi[lesson]) for anchor, lesson in edges)


def degree_sequence(hyperedges: list[list[str]]) -> dict[str, int]:
    deg: dict[str, int] = {}
    for e in hyperedges:
        for v in e:
            deg[v] = deg.get(v, 0) + 1
    return deg


# --- (f) canary lesson — planted-ground-truth 침투 감사 (findings a4/b3) ---

def make_canary(tag: str, seed: str) -> str:
    """고유 토큰 침투 표지. 이 토큰은 자연 코퍼스에 존재하지 않으므로
    B의 응답에 등장하면 채널 누수(또는 진짜 전이 서명)의 결정적 증거."""
    return f"CANARY-{_sha(tag + ':' + seed)[:16]}"


def canary_detected(response: str, canary: str) -> bool:
    return canary in response


# --- (g) disjoint corpus audit (finding b4: leakage>0 → run 무효) ---

def _tokens(text: str) -> set[str]:
    return {t for t in text.lower().split() if t}


def disjoint_audit(train_queries: list[str], eval_queries: list[str],
                   near_dup_threshold: float = 0.6) -> dict:
    """exact-query overlap + token-Jaccard near-dup 감사.
    leakage = exact 일치 또는 Jaccard >= threshold 인 (train, eval) 쌍 수."""
    exact = set(train_queries) & set(eval_queries)
    train_tok = [(q, _tokens(q)) for q in train_queries]
    pairs = []
    for eq in eval_queries:
        et = _tokens(eq)
        if not et:
            continue
        for tq, tt in train_tok:
            if not tt:
                continue
            j = len(et & tt) / len(et | tt)
            if j >= near_dup_threshold:
                pairs.append((tq, eq, round(j, 4)))
    leakage = len(exact) + len(pairs)
    return {
        "leakage": leakage,
        "exact_overlaps": sorted(exact),
        "near_dup_pairs": pairs,
        "near_dup_threshold": near_dup_threshold,
        "verdict": "VOID" if leakage > 0 else "CLEAN",
    }


# --- run 무효 조건 (공통 섀시 §0.1-6) ---

def run_verdict(*, freeze_hash_changed: bool = False,
                judge_sha_changed: bool = False,
                leakage: int = 0,
                replay_failed: bool = False) -> dict:
    """하나라도 해당하면 run 무효 (fail-closed)."""
    voids = []
    if freeze_hash_changed:
        voids.append("freeze_hash_changed")
    if judge_sha_changed:
        voids.append("judge_sha_changed")
    if leakage > 0:
        voids.append("leakage>0")
    if replay_failed:
        voids.append("replay_failed")
    return {"valid": not voids, "voids": voids}
