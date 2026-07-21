#!/usr/bin/env python3
"""
ML13 (JOB2) — 진짜 multi-hop task서 PPR/APPNP 딥 HSWM vs flat vs iterative.

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML13-job2-multihop
PROM 3-agent 종합: PPR/APPNP(teleport restart)가 최선 training-free 딥전파(정규화강화 아님,
  Oversmoothing Fallacy). 단일책 스케일 이득 사전확률 +3~5pp or null. 필수 대조군=flat+iterative.

진짜 multi-hop task: 개념쌍(A@章X, B@章Y) 질의. gold=A·B 동시포함 bridge청크(서로 다른 章 ≥2 걸침).
  가짜 multi-hop(단일청크 답) 방지: bridge가 ≥2 章에 퍼진 쌍만 채택.
방법 4:
  flat        : cos(query_AB, chunk) top-k (단일층 baseline)
  ppr         : APPNP π=(1-α)Âπ+α·s, s=query relevance seed, α∈{0.15,0.3,0.5} — 딥 확산(붕괴저항)
  iterative   : A로 top + B로 top 합집합 (그래프 없이 '반복검색' 대조군, 문헌 핵심 대조)
  ppr_rerank  : flat top-100 후보 위에서만 PPR (2-stage, HippoRAG/GNRR 패턴)
지표: bridge recall@20 + α-nDCG@20. 정직 사전확률 명시.
"""
import json, sys, re, math, statistics, itertools
from collections import defaultdict
from pathlib import Path
import numpy as np

BOOK=Path("/Volumes/GM/oss-clones/ai-agent-book/book"); HERE=Path(__file__).parent
KNN=10; K=20
# 개념쌍 (서로 다른 章 경향) : (anchorA, queryA-KO, anchorB, queryB-KO)
PAIRS=[("harness","하네스 스캐폴딩","评估","평가 벤치마크"),
       ("记忆","사용자 기억 메모리","多 Agent","다중 에이전트 협업"),
       ("工具","도구 함수호출","Coding Agent","코딩 에이전트"),
       ("RAG","검색증강생성","上下文","맥락 압축"),
       ("强化学习","강화학습 보상","评估","평가 통계"),
       ("提示","프롬프트 지시","安全","안전 인젝션"),
       ("多模态","멀티모달 음성","工具","도구 호출"),
       ("记忆","기억 지식베이스","检索","검색 인출"),
       ("KV Cache","KV 캐시","推理","추론 사고"),
       ("规划","계획 플래너","多 Agent","다중 에이전트"),
       ("知识","지식 그래프","检索","검색 랭킹"),
       ("编排","오케스트레이션 워크플로","多 Agent","다중 에이전트")]

def chunk_book():
    ch,cp=[],[]
    for f in sorted(BOOK.glob("chapter*.md"),key=lambda p:int(re.search(r"\d+",p.stem).group())):
        for para in re.split(r"\n\s*\n",f.read_text(encoding="utf-8")):
            t=" ".join(para.split())
            if len(t)>=90 and not t.startswith("#") and not t.startswith("!["): ch.append(t); cp.append(f.stem)
    return ch,cp

def adj(E,knn):
    n=len(E); S=E@E.T; np.fill_diagonal(S,-2); A=np.zeros((n,n),np.float32)
    for i in range(n):
        for j in np.argsort(-S[i])[:knn]:
            w=max(0.0,float(S[i,j])); A[i,j]=w; A[j,i]=max(A[j,i],w)
    A=A+np.eye(n,dtype=np.float32); d=A.sum(1); di=1/np.sqrt(np.maximum(d,1e-9))
    return (A*di[:,None])*di[None,:]

def appnp(Ahat,s,alpha,K=10):
    pi=s.copy()
    for _ in range(K): pi=(1-alpha)*(Ahat@pi)+alpha*s
    return pi

def recall(ranked,gold,k): return len(set(ranked[:k])&gold)/len(gold) if gold else 0.0

def main():
    ch,cp=chunk_book()
    from sentence_transformers import SentenceTransformer
    import torch; torch.manual_seed(333)
    m=SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    E=m.encode(ch,normalize_embeddings=True,convert_to_numpy=True,batch_size=64).astype(np.float32)
    Ahat=adj(E,KNN)

    # 진짜 multi-hop 쌍 선별: bridge(A·B 동시포함)가 ≥3개 & ≥2 章
    tasks=[]
    for aA,qA,aB,qB in PAIRS:
        bridge=[i for i,t in enumerate(ch) if aA.lower() in t.lower() and aB.lower() in t.lower()]
        bchaps=set(cp[i] for i in bridge)
        if len(bridge)>=3 and len(bchaps)>=2:
            tasks.append({"A":aA,"B":aB,"qA":qA,"qB":qB,"q":qA+" "+qB,"gold":set(bridge),
                          "n_bridge":len(bridge),"n_chap":len(bchaps)})
    if not tasks:
        print(json.dumps({"error":"no real multi-hop pairs (bridge≥3 & ≥2 chapters)"}));return

    Qab=m.encode([t["q"] for t in tasks],normalize_embeddings=True,convert_to_numpy=True).astype(np.float32)
    QA=m.encode([t["qA"] for t in tasks],normalize_embeddings=True,convert_to_numpy=True).astype(np.float32)
    QB=m.encode([t["qB"] for t in tasks],normalize_embeddings=True,convert_to_numpy=True).astype(np.float32)

    res=defaultdict(list)
    for ti,t in enumerate(tasks):
        s=E@Qab[ti]; gold=t["gold"]
        flat=list(np.argsort(-s)[:100]); res["flat"].append(recall(flat,gold,K))
        # iterative: A top + B top 합집합
        sa=E@QA[ti]; sb=E@QB[ti]
        it=sorted(set(list(np.argsort(-sa)[:K//2])+list(np.argsort(-sb)[:K//2])),key=lambda i:-max(sa[i],sb[i]))
        res["iterative"].append(recall(it,gold,K))
        # ppr full
        for a in (0.15,0.3,0.5):
            pi=appnp(Ahat,np.maximum(s,0),a); res[f"ppr_a{a}"].append(recall(list(np.argsort(-pi)),gold,K))
        # ppr rerank on flat-100 후보만
        cand=flat; sc=np.full(len(E),-1e9);
        pi=appnp(Ahat,np.maximum(s,0),0.3)
        for i in cand: sc[i]=pi[i]
        res["ppr_rerank_a0.3"].append(recall(list(np.argsort(-sc)),gold,K))

    summary={k:round(statistics.mean(v),4) for k,v in res.items()}
    best=max(summary,key=lambda k:summary[k])
    ev={"experiment":"hswm_job2_multihop_ml13","tree":"LakatosTree_PromSearchHSWM_20260721","node":"ML13-job2-multihop",
        "prior":"단일책 스케일 그래프 이득 사전확률 +3~5pp or null (Agent3 문헌). >이면 가짜multi-hop/약baseline 의심.",
        "task":{"n_real_multihop_pairs":len(tasks),"gold":"A·B 동시포함 bridge청크(≥2 章)","metric":"bridge recall@20",
                "pairs":[{"A":t["A"],"B":t["B"],"n_bridge":t["n_bridge"],"n_chap":t["n_chap"]} for t in tasks]},
        "recall@20_by_method":summary,
        "conclusion":{
          "best_method":best,
          "best_ppr_beats_flat": max(summary[k] for k in summary if k.startswith("ppr"))>summary["flat"],
          "ppr_gain_over_flat": round(max(summary[k] for k in summary if k.startswith("ppr"))-summary["flat"],4),
          "iterative_vs_flat": round(summary["iterative"]-summary["flat"],4),
          "ppr_beats_iterative": max(summary[k] for k in summary if k.startswith("ppr"))>summary["iterative"],
        },
        "note":"진짜 multi-hop(bridge≥2章). ppr=APPNP teleport K=10. gold=anchor-string 교집합(crude)."}
    out=HERE/"evidence"/"EVIDENCE_hswm_job2_multihop_ml13_2026-07-21.json"
    out.write_text(json.dumps(ev,ensure_ascii=False,indent=2))
    print(json.dumps(ev,ensure_ascii=False,indent=2)); print(f"\nEVIDENCE -> {out}",file=sys.stderr)

if __name__=="__main__": main()
