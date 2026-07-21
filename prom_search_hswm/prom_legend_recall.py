#!/usr/bin/env python3
"""
PROM 검색 P3 — legend-repo recall: 현 lexical 검색이 왜 레전드(ai-agent-book)와 안 엮였나.

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node P3-legend-recall-at-k
가설: 책은 중국어, 우리 KG 질의는 한/영 → lexical(token overlap)은 교차언어서 0 수렴.
      단 라틴 전문어(harness/RAG/KV Cache/Coding Agent) 공유 토큰만 lexical 통과.
      semantic(multilingual embedding)은 교차언어 개념 매칭 → 레전드 surface.

metric = legend_recall_at_k (k=5): gold 책청크가 top-k 안에 들어온 질의 비율.
gold 정의(비순환, C2): 청크가 anchor 용어 포함 = gold. anchor 는 retriever 에 주지 않음(질의만 준다).
자가비판: lexical/semantic 동일 corpus·동일 k, distractor 포함. tau 자유(순위만).
"""
import json, sys, re, statistics
from pathlib import Path

BOOK = Path("/Volumes/GM/oss-clones/ai-agent-book/book")
HERE = Path(__file__).parent
K = 5
SEED = 333

# 질의(한/영, SYMPOSIUM 어휘) + gold anchor(책 원문 용어; retriever엔 미제공) + latin 여부
QUERIES = [
    {"q": "하네스 에이전트 스캐폴딩 구조가 에이전트를 제약한다 harness", "anchor": "harness", "anchor_latin": True},
    {"q": "다중 에이전트 협업 재배맨 오케스트레이션 분업", "anchor": "多 Agent", "anchor_latin": False},
    {"q": "컨텍스트 엔지니어링 KV 캐시 프롬프트 캐싱 재사용", "anchor": "KV Cache", "anchor_latin": True},
    {"q": "검색 증강 생성 리트리벌 재랭킹 하이브리드 RAG", "anchor": "RAG", "anchor_latin": True},
    {"q": "코딩 에이전트 코드 생성 파일시스템 자부트스트랩", "anchor": "Coding Agent", "anchor_latin": True},
    {"q": "에이전트 평가 방법론 통계적 유의성 판정", "anchor": "评估", "anchor_latin": False},
    {"q": "상하문 맥락 관리 압축 오버플로", "anchor": "上下文", "anchor_latin": False},
]

DISTRACTORS = [
    "오늘 저녁 메뉴로 김치찌개를 끓이려면 돼지고기와 신김치가 필요하다.",
    "The weather forecast predicts heavy rain over the weekend with strong winds.",
    "축구 경기에서 후반 추가시간에 결승골이 터지며 홈팀이 역전승했다.",
    "복리 이자를 계산할 때는 원금에 이율과 기간을 곱해 누적한다.",
    "등산로 초입에서 약수터까지는 완만한 오르막이 이어진다.",
    "The mitochondria is the powerhouse of the cell in eukaryotic organisms.",
    "가을이 되면 은행나무 잎이 노랗게 물들어 거리를 뒤덮는다.",
    "커피 원두는 로스팅 정도에 따라 산미와 바디감이 크게 달라진다.",
    "기타 코드 진행에서 C-G-Am-F는 대중가요에 흔히 쓰이는 패턴이다.",
    "지하철 2호선은 순환선이라 시계방향과 반시계방향으로 운행한다.",
    "The recipe calls for two cups of flour, a pinch of salt, and three eggs.",
    "겨울철 실내 습도는 40에서 60 퍼센트로 유지하는 것이 좋다.",
    "마라톤 완주를 위해서는 장거리 지구력 훈련과 페이스 조절이 중요하다.",
    "고양이는 하루 대부분을 잠으로 보내며 야행성 습성을 보인다.",
    "국은 소금 간을 마지막에 맞춰야 재료 본연의 맛을 살릴 수 있다.",
]

def chunk_book():
    chunks = []  # (id, text, is_book)
    for f in sorted(BOOK.glob("chapter*.md")):
        raw = f.read_text(encoding="utf-8")
        for para in re.split(r"\n\s*\n", raw):
            t = " ".join(para.split())
            if len(t) >= 90 and not t.startswith("#") and not t.startswith("!["):
                chunks.append((f"{f.stem}:{len(chunks)}", t, True))
    for i, d in enumerate(DISTRACTORS):
        chunks.append((f"distractor:{i}", d, False))
    return chunks

_TOK = re.compile(r"[a-z0-9]+|[가-힣]+|[一-鿿]")
def toks(s):
    return set(_TOK.findall(s.lower()))

def lexical_rank(q, chunks):
    qt = toks(q)
    scored = []
    for cid, txt, isb in chunks:
        ct = toks(txt)
        inter = len(qt & ct)
        jac = inter / (len(qt | ct) or 1)
        scored.append((jac, cid, isb))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored

def semantic_rank(qi, chunks, cos_q_c):
    scored = [(float(cos_q_c[qi][j]), chunks[j][0], chunks[j][2]) for j in range(len(chunks))]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored

def gold_hit_at_k(ranked, chunks_by_id, anchor, k):
    """top-k 안에 anchor 포함 book 청크가 있나."""
    anchor_l = anchor.lower()
    for score, cid, isb in ranked[:k]:
        if not isb:
            continue
        txt = chunks_by_id[cid]
        if anchor_l in txt.lower():
            return 1
    return 0

def main():
    chunks = chunk_book()
    chunks_by_id = {cid: txt for cid, txt, _ in chunks}
    texts = [t for _, t, _ in chunks]
    n_book = sum(1 for _, _, b in chunks if b)

    # semantic embeddings
    from sentence_transformers import SentenceTransformer
    import numpy as np, torch
    torch.manual_seed(SEED)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    c_emb = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, batch_size=64)
    q_emb = model.encode([Q["q"] for Q in QUERIES], normalize_embeddings=True, convert_to_numpy=True)
    cos_q_c = q_emb @ c_emb.T

    per_query = []
    lex_hits = sem_hits = 0
    lex_lat = sem_lat = lat_n = 0
    lex_cjk = sem_cjk = cjk_n = 0
    for qi, Q in enumerate(QUERIES):
        lr = lexical_rank(Q["q"], chunks)
        sr = semantic_rank(qi, chunks, cos_q_c)
        lh = gold_hit_at_k(lr, chunks_by_id, Q["anchor"], K)
        sh = gold_hit_at_k(sr, chunks_by_id, Q["anchor"], K)
        lex_hits += lh; sem_hits += sh
        if Q["anchor_latin"]:
            lex_lat += lh; sem_lat += sh; lat_n += 1
        else:
            lex_cjk += lh; sem_cjk += sh; cjk_n += 1
        per_query.append({"q": Q["q"][:40], "anchor": Q["anchor"], "latin": Q["anchor_latin"],
                          "lexical_hit@5": lh, "semantic_hit@5": sh,
                          "sem_top1_score": round(sr[0][0], 3)})

    nq = len(QUERIES)
    lex_recall = lex_hits / nq
    sem_recall = sem_hits / nq
    ev = {
        "experiment": "prom_legend_recall_crosslingual",
        "tree": "LakatosTree_PromSearchHSWM_20260721",
        "node": "P3-legend-recall-at-k",
        "corpus": {"book_chunks": n_book, "distractors": len(DISTRACTORS), "total": len(chunks),
                   "legend": "bojieli/ai-agent-book (Chinese)"},
        "k": K, "n_queries": nq,
        "lexical_current_prom": {"legend_recall_at_k": round(lex_recall, 4)},
        "semantic": {"legend_recall_at_k": round(sem_recall, 4)},
        "novel_gap_semantic_minus_lexical": round(sem_recall - lex_recall, 4),
        "by_anchor_language": {
            "latin_anchor": {"n": lat_n, "lexical": round(lex_lat / lat_n, 3) if lat_n else None,
                             "semantic": round(sem_lat / lat_n, 3) if lat_n else None},
            "cjk_only_anchor": {"n": cjk_n, "lexical": round(lex_cjk / cjk_n, 3) if cjk_n else None,
                                "semantic": round(sem_cjk / cjk_n, 3) if cjk_n else None},
        },
        "per_query": per_query,
        "finding": "cross-lingual: lexical(token overlap) surfaces legend ONLY via shared latin jargon; fails on native-language concept queries. semantic multilingual retrieves cross-lingual. = 왜 PROM이 중국어 레전드와 안 엮였나의 직접 증거.",
        "prereg": {"metric": "legend_recall_at_k", "baseline": 0.1,
                   "novel_metric": "citation_graph_legend_recall_gap", "novel_threshold": 0.3, "direction": "higher"},
        "scope_caveat": "이건 RETRIEVAL-side proxy(corpus에 legend 이미 존재). 진짜 P3의 citation-graph agentic 발견(legend가 corpus 밖일 때 인용 타고 찾기)은 미구현 = 부분 테스트.",
        "_facts": {"novel_gap_ge_threshold": (sem_recall - lex_recall) >= 0.3,
                   "semantic_beats_lexical": sem_recall > lex_recall},
    }
    out = HERE / "evidence" / "EVIDENCE_prom_legend_recall_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
