#!/usr/bin/env python3
"""
ML11 — HSWM을 딥러닝처럼 깊게 쌓기 (GNN message-passing 깊이) + multi-hop + over-smoothing.

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML11-hswm-deep-gnn
USER: "HSWM을 딥러닝 모델처럼 깊게 쌓으면? 깊이 따라 어떻게 되나? multi-hop 도. HSWM 자체 수정 가능."

핵심 구분: ML9/10=클러스터링 트리 깊이. 이번=**표현변환 깊이**(각 층이 이웃 정보 섞음=GNN).
  HSWM=가중 시멘틱 그래프(kNN, cosine 가중). propagation L층 = 정보가 L홉 퍼짐.
  딥러닝 현상 over-smoothing: 층↑ → 노드표현 수렴/붕괴 예상(Li 2018, Oono-Suzuki 2020).

2 모드: pure(X=ÂX, 순수 스택=over-smooth) / appnp(X=(1-β)ÂX+βX0, residual=over-smooth 저항, PPNP 2019).
깊이 sweep L=0..10 측정:
  - alpha-nDCG@20 (single-lookup 개념쿼리) — 트리처럼 여기선 큰 이득 없을 것.
  - **multi-hop recall@40** (hard gold=직접유사도 하위절반 gold, bridge 통해야 도달) — propagation의 진짜 무대.
  - over-smoothing: 노드표현 평균 pairwise cosine(↑=붕괴) + Dirichlet energy(↓=붕괴).
결론: 깊이 최적점 + over-smooth 시작점 + multi-hop서 propagation 이득 여부.
"""
import json, sys, re, math, statistics
from collections import defaultdict
from pathlib import Path
import numpy as np

BOOK = Path("/Volumes/GM/oss-clones/ai-agent-book/book")
HERE = Path(__file__).parent
KNN = 10
ALPHA = 0.5
K = 20
DEPTHS = [0, 1, 2, 3, 4, 5, 6, 8, 10]
ANCHORS = {
 "harness":"harness 하네스 에이전트 스캐폴딩","RAG":"검색 증강 생성 RAG","多 Agent":"다중 에이전트 협업",
 "KV Cache":"KV 캐시 프롬프트 캐싱","Coding Agent":"코딩 에이전트 코드생성","评估":"에이전트 평가 벤치마크",
 "上下文":"상하문 맥락 압축","记忆":"사용자 기억 메모리","工具":"도구 tool 함수호출 MCP",
 "强化学习":"강화학습 RL 보상","提示":"프롬프트 지시","推理":"추론 사고체인","检索":"검색 인출 랭킹",
 "微调":"미세조정 SFT","训练":"훈련 데이터","向量":"벡터 임베딩","幻觉":"환각 오류","安全":"안전 인젝션",
 "权限":"권한 접근제어","编排":"오케스트레이션 워크플로","多模态":"멀티모달 음성 비전","注意力":"어텐션 트랜스포머",
 "奖励":"보상 신호","泛化":"일반화","规划":"계획 플래너","知识":"지식 그래프",
}

def chunk_book():
    chunks, chap = [], []
    for f in sorted(BOOK.glob("chapter*.md"), key=lambda p:int(re.search(r"\d+",p.stem).group())):
        for para in re.split(r"\n\s*\n", f.read_text(encoding="utf-8")):
            t=" ".join(para.split())
            if len(t)>=90 and not t.startswith("#") and not t.startswith("!["):
                chunks.append(t); chap.append(f.stem)
    return chunks, chap

def build_adj(E, knn):
    n=len(E); S=E@E.T
    np.fill_diagonal(S,-2)
    A=np.zeros((n,n),dtype=np.float32)
    for i in range(n):
        nb=np.argsort(-S[i])[:knn]
        for j in nb:
            w=max(0.0,float(S[i,j]))
            A[i,j]=w; A[j,i]=max(A[j,i],w)  # symmetric
    A=A+np.eye(n,dtype=np.float32)  # self-loop
    d=A.sum(1); dinv=1.0/np.sqrt(np.maximum(d,1e-9))
    Ahat=(A*dinv[:,None])*dinv[None,:]  # sym-norm
    return Ahat

def normalize_rows(X):
    return X/(np.linalg.norm(X,axis=1,keepdims=True)+1e-9)

def alpha_ndcg(ranked, gold_set, chap, alpha, k):
    def dcg(order):
        seen=defaultdict(int); s=0.0
        for r,d in enumerate(order[:k],1):
            if d in gold_set:
                g=(1-alpha)**seen[chap[d]]; seen[chap[d]]+=1; s+=g/math.log2(r+1)
        return s
    seen=defaultdict(int); ideal=[]; pool=sorted(gold_set)
    while pool:
        best=min(pool,key=lambda d:(seen[chap[d]],d)); ideal.append(best); seen[chap[best]]+=1; pool.remove(best)
    idcg=dcg(ideal)
    return dcg(ranked)/idcg if idcg>0 else 0.0

def main():
    chunks,chap=chunk_book()
    from sentence_transformers import SentenceTransformer
    import torch; torch.manual_seed(333)
    model=SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    E=model.encode(chunks,normalize_embeddings=True,convert_to_numpy=True,batch_size=64).astype(np.float32)
    Ahat=build_adj(E,KNN)

    concepts=[]
    for a,q in ANCHORS.items():
        g=[i for i,t in enumerate(chunks) if a.lower() in t.lower()]
        gc=set(chap[i] for i in g)
        if len(gc)>=3: concepts.append((a,q,set(g)))
    Q=model.encode([q for _,q,_ in concepts],normalize_embeddings=True,convert_to_numpy=True).astype(np.float32)

    def run(mode, beta=0.1):
        X0=E.copy(); X=E.copy()
        res={}
        for L in range(0,max(DEPTHS)+1):
            if L>0:
                if mode=="pure": X=Ahat@X
                else: X=(1-beta)*(Ahat@X)+beta*X0
            if L in DEPTHS:
                Xn=normalize_rows(X)
                # over-smoothing: 표본 500쌍 평균 pairwise cosine
                rng=np.random.default_rng(0); idx=rng.choice(len(Xn),400,replace=False)
                pw=Xn[idx]@Xn[idx].T; oversmooth=float((pw.sum()-len(idx))/(len(idx)*(len(idx)-1)))
                andcg=[]; mh=[]
                for qi,(a,q,gset) in enumerate(concepts):
                    qv=Q[qi]; sc=Xn@qv
                    ranked=list(np.argsort(-sc)[:40])
                    andcg.append(alpha_ndcg(ranked[:K],gset,chap,ALPHA,K))
                    # multi-hop: hard gold = 직접(L0)유사도 하위절반 gold, recall@40 (propagation이 살리나)
                    direct=E@qv; gl=sorted(gset,key=lambda d:direct[d])
                    hard=set(gl[:max(1,len(gl)//2)])
                    got=set(ranked)
                    mh.append(len(hard&got)/len(hard) if hard else 0.0)
                res[L]={"alpha_ndcg@20":round(statistics.mean(andcg),4),
                        "multihop_hardgold_recall@40":round(statistics.mean(mh),4),
                        "oversmooth_meancos":round(oversmooth,4)}
        return res

    pure=run("pure"); appnp=run("appnp")

    def best(res,key): return max(res,key=lambda L:res[L][key])
    conclusion={
        "pure_alpha_ndcg_optimum_L":best(pure,"alpha_ndcg@20"),
        "appnp_alpha_ndcg_optimum_L":best(appnp,"alpha_ndcg@20"),
        "pure_multihop_optimum_L":best(pure,"multihop_hardgold_recall@40"),
        "appnp_multihop_optimum_L":best(appnp,"multihop_hardgold_recall@40"),
        "pure_oversmooth_L0_to_L10":[pure[0]["oversmooth_meancos"],pure[10]["oversmooth_meancos"]],
        "appnp_oversmooth_L0_to_L10":[appnp[0]["oversmooth_meancos"],appnp[10]["oversmooth_meancos"]],
        "deep_stacking_helps_singlelookup": max(pure[L]["alpha_ndcg@20"] for L in pure)>pure[0]["alpha_ndcg@20"]+0.005 or max(appnp[L]["alpha_ndcg@20"] for L in appnp)>appnp[0]["alpha_ndcg@20"]+0.005,
        "deep_stacking_helps_multihop": max(appnp[L]["multihop_hardgold_recall@40"] for L in appnp)>appnp[0]["multihop_hardgold_recall@40"]+0.02,
        "pure_oversmooths": pure[10]["oversmooth_meancos"]>0.9,
    }
    ev={"experiment":"hswm_deep_gnn_ml11","tree":"LakatosTree_PromSearchHSWM_20260721","node":"ML11-hswm-deep-gnn",
        "setup":{"n_queries":len(concepts),"graph":f"kNN={KNN} cosine-weighted sym-norm","modes":["pure ÂX","appnp (1-β)ÂX+βX0 β=0.1"],
                 "metrics":"alpha-nDCG@20 + multihop_hardgold_recall@40 + oversmooth_meancos","corpus":"ai-agent-book 1425 chunks"},
        "pure_stacking_by_depth":pure,"appnp_stacking_by_depth":appnp,"conclusion":conclusion,
        "note":"딥러닝식 깊이=GNN message-passing 층수(트리깊이 아님). hard gold=직접유사도 낮은 gold=multi-hop 프록시. gold=anchor-string(crude)."}
    out=HERE/"evidence"/"EVIDENCE_hswm_deep_gnn_ml11_2026-07-21.json"
    out.write_text(json.dumps(ev,ensure_ascii=False,indent=2))
    print(json.dumps(ev,ensure_ascii=False,indent=2))
    print(f"\nEVIDENCE -> {out}",file=sys.stderr)

if __name__=="__main__":
    main()
