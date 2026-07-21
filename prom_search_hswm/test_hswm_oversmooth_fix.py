#!/usr/bin/env python3
"""
ML12 — over-smoothing을 *푼다*: 깊은 HSWM을 가능하게 (USER: 문제는 해결할 job이다).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML12-oversmooth-fix
ML11: 순수 스택 → over-smoothing(cos 0.37→0.97) 붕괴. USER 지적: 이건 단정할 벽이 아니라
  딥러닝이 ResNet으로 vanishing gradient 풀었듯 *풀어야 할 문제*.
알려진 over-smoothing 해법 구현·실측:
  pure        : X=ÂX (baseline, 붕괴)
  pairnorm    : 매 층 후 center+rescale (Zhao&Akoglu 2020) — 표현분산 보존
  dropedge    : 매 층 엣지 30% 무작위 드롭 (Rong 2020) — 평활 지연
  gcnii       : 강한 initial-residual α=0.3 + identity (Chen 2020 근사) — 깊이 저항
  jk_maxdepth : Jumping Knowledge — 노드마다 최적 깊이 선택(query-time max over L, Xu 2018)
측정(깊이 L=0..15):
  1) over-smoothing 풀렸나 = oversmooth_meancos가 깊이서 낮게 유지되나 (pure 0.97 대비).
  2) 풀린 뒤 깊은 HSWM이 검색 이득 = α-nDCG@20 + multihop hard-gold recall이 L0 넘나.
결론: (a)over-smoothing 해결여부 (b)해결 후에도 깊이가 이 task서 값 있나(=multi-hop 신호 有無).
"""
import json, sys, re, math, statistics
from collections import defaultdict
from pathlib import Path
import numpy as np

BOOK=Path("/Volumes/GM/oss-clones/ai-agent-book/book"); HERE=Path(__file__).parent
KNN=10; ALPHA=0.5; K=20; MAXL=15; DEPTHS=[0,1,2,3,4,6,8,10,12,15]
ANCHORS={"harness":"harness 하네스 에이전트","RAG":"검색 증강 생성 RAG","多 Agent":"다중 에이전트 협업",
 "KV Cache":"KV 캐시 프롬프트 캐싱","Coding Agent":"코딩 에이전트 코드생성","评估":"에이전트 평가",
 "上下文":"상하문 맥락 압축","记忆":"사용자 기억 메모리","工具":"도구 함수호출 MCP","强化学习":"강화학습 보상",
 "提示":"프롬프트 지시","推理":"추론 사고체인","检索":"검색 인출","微调":"미세조정 SFT","训练":"훈련",
 "向量":"벡터 임베딩","幻觉":"환각","安全":"안전 인젝션","权限":"권한","编排":"오케스트레이션",
 "多模态":"멀티모달 음성","注意力":"어텐션","奖励":"보상","泛化":"일반화","规划":"계획","知识":"지식"}

def chunk_book():
    ch,cp=[],[]
    for f in sorted(BOOK.glob("chapter*.md"),key=lambda p:int(re.search(r"\d+",p.stem).group())):
        for para in re.split(r"\n\s*\n",f.read_text(encoding="utf-8")):
            t=" ".join(para.split())
            if len(t)>=90 and not t.startswith("#") and not t.startswith("!["): ch.append(t); cp.append(f.stem)
    return ch,cp

def adj(E,knn,drop=0.0,seed=0):
    n=len(E); S=E@E.T; np.fill_diagonal(S,-2); A=np.zeros((n,n),np.float32)
    rng=np.random.default_rng(seed)
    for i in range(n):
        for j in np.argsort(-S[i])[:knn]:
            if drop>0 and rng.random()<drop: continue
            w=max(0.0,float(S[i,j])); A[i,j]=w; A[j,i]=max(A[j,i],w)
    A=A+np.eye(n,dtype=np.float32); d=A.sum(1); di=1/np.sqrt(np.maximum(d,1e-9))
    return (A*di[:,None])*di[None,:]

def rown(X): return X/(np.linalg.norm(X,axis=1,keepdims=True)+1e-9)
def pairnorm(X,s=1.0):
    Xc=X-X.mean(0); rms=np.sqrt((Xc**2).sum(1).mean()); return s*Xc/(rms+1e-9)

def oversmooth(Xn):
    rng=np.random.default_rng(0); idx=rng.choice(len(Xn),400,replace=False)
    pw=Xn[idx]@Xn[idx].T; return float((pw.sum()-len(idx))/(len(idx)*(len(idx)-1)))

def alpha_ndcg(ranked,gs,cp,a,k):
    def dcg(o):
        sn=defaultdict(int); s=0.0
        for r,d in enumerate(o[:k],1):
            if d in gs: g=(1-a)**sn[cp[d]]; sn[cp[d]]+=1; s+=g/math.log2(r+1)
        return s
    sn=defaultdict(int); ideal=[]; pool=sorted(gs)
    while pool: b=min(pool,key=lambda d:(sn[cp[d]],d)); ideal.append(b); sn[cp[b]]+=1; pool.remove(b)
    idc=dcg(ideal); return dcg(ranked)/idc if idc>0 else 0.0

def main():
    ch,cp=chunk_book()
    from sentence_transformers import SentenceTransformer
    import torch; torch.manual_seed(333)
    m=SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    E=m.encode(ch,normalize_embeddings=True,convert_to_numpy=True,batch_size=64).astype(np.float32)
    concepts=[(a,q,set(i for i,t in enumerate(ch) if a.lower() in t.lower())) for a,q in ANCHORS.items()]
    concepts=[(a,q,g) for a,q,g in concepts if len(set(cp[i] for i in g))>=3]
    Q=m.encode([q for _,q,_ in concepts],normalize_embeddings=True,convert_to_numpy=True).astype(np.float32)
    Ahat=adj(E,KNN)

    def evaldepth(Xn):
        an=[]; mh=[]
        for qi,(a,q,gs) in enumerate(concepts):
            qv=Q[qi]; sc=Xn@qv; ranked=list(np.argsort(-sc)[:40])
            an.append(alpha_ndcg(ranked[:K],gs,cp,ALPHA,K))
            direct=E@qv; gl=sorted(gs,key=lambda d:direct[d]); hard=set(gl[:max(1,len(gl)//2)])
            mh.append(len(hard&set(ranked))/len(hard) if hard else 0.0)
        return statistics.mean(an),statistics.mean(mh)

    methods={}
    # pure / pairnorm / gcnii / dropedge : iterative
    for name,cfg in [("pure",{}),("pairnorm",{"pn":True}),("gcnii",{"ir":0.3}),("dropedge",{"de":0.3})]:
        X0=E.copy(); X=E.copy(); rec={}
        for L in range(0,MAXL+1):
            if L>0:
                A_=adj(E,KNN,drop=cfg.get("de",0.0),seed=L) if cfg.get("de") else Ahat
                X=A_@X
                if "ir" in cfg: X=(1-cfg["ir"])*X+cfg["ir"]*X0
                if cfg.get("pn"): X=pairnorm(X)
            if L in DEPTHS:
                Xn=rown(X); an,mh=evaldepth(Xn); rec[L]={"a":round(an,4),"mh":round(mh,4),"os":round(oversmooth(Xn),4)}
        methods[name]=rec
    # jk_maxdepth : 노드마다 최적 깊이 (query-time max over 저장층)
    layers={}; X=E.copy()
    for L in range(0,MAXL+1):
        if L>0: X=Ahat@X
        if L in DEPTHS: layers[L]=rown(X).copy()
    jk={}
    for Lmax in DEPTHS:
        an=[]; mh=[]
        avail=[l for l in DEPTHS if l<=Lmax]
        for qi,(a,q,gs) in enumerate(concepts):
            qv=Q[qi]
            sc=np.max(np.stack([layers[l]@qv for l in avail]),axis=0)  # 노드별 최적 깊이
            ranked=list(np.argsort(-sc)[:40]); an.append(alpha_ndcg(ranked[:K],gs,cp,ALPHA,K))
            direct=E@qv; gl=sorted(gs,key=lambda d:direct[d]); hard=set(gl[:max(1,len(gl)//2)])
            mh.append(len(hard&set(ranked))/len(hard) if hard else 0.0)
        jk[Lmax]={"a":round(statistics.mean(an),4),"mh":round(statistics.mean(mh),4)}
    methods["jk_maxdepth"]=jk

    L0=methods["pure"][0]["a"]
    def bestA(rec): return max(rec[L]["a"] for L in rec)
    conclusion={
      "L0_alpha_ndcg":L0,
      "oversmooth_at_L15":{n:methods[n].get(15,{}).get("os") for n in ["pure","pairnorm","gcnii","dropedge"]},
      "oversmoothing_SOLVED":{n:(methods[n].get(15,{}).get("os",1)<0.7) for n in ["pairnorm","gcnii","dropedge"]},
      "best_alpha_ndcg":{n:round(bestA(methods[n]),4) for n in methods},
      "any_deep_beats_L0_alpha": any(bestA(methods[n])>L0+0.005 for n in methods),
      "jk_beats_L0": bestA(jk)>L0+0.005,
      "best_multihop":{n:round(max(methods[n][L]["mh"] for L in methods[n]),4) for n in methods},
    }
    ev={"experiment":"hswm_oversmooth_fix_ml12","tree":"LakatosTree_PromSearchHSWM_20260721","node":"ML12-oversmooth-fix",
        "premise":"USER: over-smoothing은 단정할 벽이 아니라 풀 job (ResNet이 vanishing gradient 풀었듯).",
        "setup":{"n_queries":len(concepts),"graph":f"kNN={KNN}","depths":DEPTHS,"methods":list(methods),
                 "mitigations":"pairnorm(Zhao2020)/dropedge(Rong2020)/gcnii-ir(Chen2020)/JK(Xu2018)"},
        "by_method_depth":methods,"conclusion":conclusion,
        "note":"os=oversmooth 평균 pairwise cos(낮을수록 표현 구별 유지). a=α-nDCG@20. mh=multihop hard-gold recall@40."}
    out=HERE/"evidence"/"EVIDENCE_hswm_oversmooth_fix_ml12_2026-07-21.json"
    out.write_text(json.dumps(ev,ensure_ascii=False,indent=2))
    print(json.dumps(ev,ensure_ascii=False,indent=2)); print(f"\nEVIDENCE -> {out}",file=sys.stderr)

if __name__=="__main__": main()
