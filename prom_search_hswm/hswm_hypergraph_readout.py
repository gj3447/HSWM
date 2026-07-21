#!/usr/bin/env python3
"""
V∪E readout 프리미티브 — 하이퍼그래프 위에서 질의→읽어낼 unit 랭킹.  [step 2]

KQV T5(../PROM_KQV_ATTENTION_BACKBONE §3): 하이퍼엣지를 1급 채점단위로 물질화할 때만
힘을 더한다(TokenGT ≥ 2-IGN). 이 모듈은 그 "1급 채점"을 구현 —
  - node_only(baseline): 정점 V만 후보로 retrieval (= entity 검색만).
  - edge_only          : 하이퍼엣지 E만 후보 (= 현 ML3 finding-cosine과 동형).
  - v_union_e(T5)      : V∪E 전체를 한 후보풀에 넣고 cosine readout.
    엣지 히트는 그 members(정점)로, 정점 히트는 incident_edges(엣지)로 1-hop 확장 가능.

정직 경계: 여기까지는 *프리미티브*. "v_union_e > node_only/edge_only"라는 성능 주장은
  LakatoTree T5 예측 사전등록 + held-out gold + MC-null z>3 + equal-compute control 뒤에서만
  (LakatosTree_PromSearchHSWM_20260721, 실험 B). 이 self-test는 smoke이지 판정이 아니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hswm_hypergraph import Hypergraph, build_hypergraph, load_badiou_findings


def _cos(a, b) -> float:
    # 임베딩은 normalize_embeddings=True 가정(단위벡터) → 내적=cosine. 방어적 정규화 포함.
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


def candidate_pool(hg: Hypergraph, mode: str) -> list[tuple[str, str, object]]:
    """(kind, id, embedding) 리스트. mode: node_only | edge_only | v_union_e."""
    pool = []
    if mode in ("node_only", "v_union_e"):
        for vid in sorted(hg.vertices):
            v = hg.vertices[vid]
            if v.embedding is not None:
                pool.append(("V", vid, v.embedding))
    if mode in ("edge_only", "v_union_e"):
        for eid in sorted(hg.edges):
            e = hg.edges[eid]
            if e.embedding is not None:
                pool.append(("E", eid, e.embedding))
    return pool


def readout(hg: Hypergraph, query_vec, mode: str = "v_union_e", top_k: int = 10):
    """질의 임베딩 → (kind, id, score) 상위 top_k. 결정론(동점은 id 사전순)."""
    pool = candidate_pool(hg, mode)
    scored = [(kind, uid, _cos(query_vec, emb)) for kind, uid, emb in pool]
    scored.sort(key=lambda r: (-r[2], r[0], r[1]))
    return scored[:top_k]


def expand(hg: Hypergraph, unit_kind: str, unit_id: str) -> dict:
    """읽어낸 unit → 1-hop 이웃(엣지 히트→members / 정점 히트→incident_edges) + 값 payload."""
    if unit_kind == "E":
        e = hg.edges[unit_id]
        return {"value": e.value, "members": e.members, "clusters": e.clusters}
    v = hg.vertices[unit_id]
    return {"name": v.name, "kind": v.kind,
            "incident_edges": v.incident_edges,
            "values": [hg.edges[eid].value for eid in v.incident_edges]}


# --- smoke test (실 임베딩. 판정 아님 — 프리미티브가 실 인프라와 맞물리나) ---
if __name__ == "__main__":
    from sentence_transformers import SentenceTransformer
    import torch
    torch.manual_seed(333)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    def embed(texts):
        return model.encode(texts, normalize_embeddings=True, convert_to_numpy=True).tolist()

    hg = build_hypergraph(load_badiou_findings(), embed=embed)
    q = embed(["Cohen forcing and the event as self-membership"])[0]

    print(f"하이퍼그래프: V={len(hg.vertices)} E={len(hg.edges)} V∪E={len(hg.units())}")
    for mode in ("node_only", "edge_only", "v_union_e"):
        top = readout(hg, q, mode=mode, top_k=5)
        print(f"\n[{mode}] top-5:")
        for kind, uid, sc in top:
            label = hg.edges[uid].clusters if kind == "E" else hg.vertices[uid].kind
            print(f"   {kind} {uid:16s} cos={sc:.3f}  ({label})")
    print("\nsmoke OK — 프리미티브가 실 임베딩과 맞물림. 성능 판정은 실험 B(T5 사전등록) 뒤.")
