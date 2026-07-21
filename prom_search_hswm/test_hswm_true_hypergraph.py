#!/usr/bin/env python3
"""
ML16 — 진짜 하이퍼그래프 HSWM 재판정 (USER 핵심주장: n-ary 하이퍼그래프의 유용성).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML16-true-hypergraph
지적 정정: ML13-15는 전부 pairwise(이진) 그래프=HippoRAG식. USER 주장=하이퍼그래프(n-ary) SWM.
이번엔 진짜 하이퍼그래프: 노드=passage, 하이퍼엣지=엔티티(그 엔티티 담은 passage들의 n-ary 집합).

Zhou et al. 2006 정규화 하이퍼그래프 adjacency:
  Θ = Dv^-1/2 · H · W · De^-1 · H^T · Dv^-1/2
  H=incidence(passage×entity), W=diag idf(entity), De=하이퍼엣지 차수(그 엔티티 담은 passage 수),
  Dv=노드 차수. **De^-1 = 하이퍼엣지 크기 정규화 = n-ary 인지 항** (큰/흔한 엔티티묶음 희석).
대조:
  flat            : passage 임베딩 코사인 (baseline)
  binary_clique   : 같은 엔티티, De 정규화 없이 pairwise idf (=ML15식 이진 붕괴)
  hypergraph_zhou : 진짜 하이퍼그래프 정규화 (n-ary 보존)
  hyper_rerank    : 하이퍼그래프 PPR로 flat top-100 재랭킹 (2-stage)
  hyper_fuse      : RRF(flat, hypergraph)
지표: recall@2/5/10 + hard-hop(hop2) recall@10 + bootstrap CI vs flat, vs binary.
"""
import json, sys, re, math, statistics, random, hashlib
from collections import defaultdict
from pathlib import Path
import numpy as np

MUSIQUE=Path("/Volumes/GM/bench/musique_dev.jsonl"); HERE=Path(__file__).parent
N_Q=300; SEED=333; KS=[2,5,10]; BOOT=2000; DF_MIN=2; DF_MAX=40
STOP={"The","A","An","In","On","At","He","She","It","They","This","That","His","Her","When","After",
      "Before","There","Their","These","Those","As","Of","For","And","But","Also","However","Its"}
def ents(t):return {mm.lower() for mm in re.findall(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b",t) if mm not in STOP and len(mm)>2}

def load(n):
    exs=[json.loads(l) for l in open(MUSIQUE)]; random.Random(SEED).shuffle(exs)
    exs=[e for e in exs if e.get("answerable",True)][:n]
    pool=[];k2i={};qgold=[];qt=[]
    for e in exs:
        g=set()
        for p in e["paragraphs"]:
            k=hashlib.md5((p["title"]+"||"+p["paragraph_text"]).encode()).hexdigest()
            if k not in k2i:k2i[k]=len(pool);pool.append(p["title"]+". "+p["paragraph_text"])
            if p["is_supporting"]:g.add(k2i[k])
        qgold.append(g);qt.append(e["question"])
    return pool,qt,qgold

def build_hyper(pool):
    """incidence H (npassage x nentity, idf), + Zhou 정규화 Θ 와 binary clique A 반환."""
    n=len(pool); el=[ents(p) for p in pool]; inv=defaultdict(list)
    for i,es in enumerate(el):
        for e in es: inv[e].append(i)
    ent=[e for e,ps in inv.items() if DF_MIN<=len(ps)<=DF_MAX]
    eidx={e:j for j,e in enumerate(ent)}; me=len(ent)
    N=n
    H=np.zeros((n,me),np.float32)
    for e in ent:
        for p in inv[e]: H[p,eidx[e]]=1.0
    idf=np.array([math.log(N/len(inv[e])) for e in ent],np.float32)  # W diag
    De=np.array([len(inv[e]) for e in ent],np.float32)               # 하이퍼엣지 차수
    HW=H*idf[None,:]  # H·W
    # Zhou: Θ = Dv^-1/2 H W De^-1 H^T Dv^-1/2
    HWDe=HW*(1.0/De)[None,:]           # H·W·De^-1
    Theta=HWDe@H.T                      # (n,n)  (De^-1 정규화된 하이퍼그래프)
    np.fill_diagonal(Theta,0)
    Dv=Theta.sum(1); dvi=1/np.sqrt(np.maximum(Dv,1e-9))
    Theta=(Theta*dvi[:,None])*dvi[None,:]
    Theta=Theta+np.eye(n,dtype=np.float32)*0  # self via appnp teleport
    # binary clique (De 정규화 없음, idf pairwise)
    Aclq=(HW)@H.T; np.fill_diagonal(Aclq,0)
    dc=Aclq.sum(1); dci=1/np.sqrt(np.maximum(dc,1e-9)); Aclq=(Aclq*dci[:,None])*dci[None,:]
    return Theta,Aclq,me

def appnp(Ahat,S,al=0.3,K=10):
    s=np.maximum(S,0).T.astype(np.float32);pi=s.copy()
    for _ in range(K):pi=(1-al)*(Ahat@pi)+al*s
    return pi
def recall(r,g,k):return len(set(r[:k])&g)/len(g) if g else 0.0
def boot(d,reps=BOOT,seed=1):
    rng=random.Random(seed);n=len(d);ms=[sum(d[rng.randrange(n)] for _ in range(n))/n for _ in range(reps)];ms.sort()
    return round(ms[int(.025*reps)],4),round(ms[int(.975*reps)],4)

def main():
    pool,qt,qgold=load(N_Q)
    from sentence_transformers import SentenceTransformer
    import torch; torch.manual_seed(SEED)
    try:m=SentenceTransformer("all-MiniLM-L6-v2");mu="all-MiniLM-L6-v2"
    except Exception:m=SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2");mu="ml(fb)"
    E=m.encode(pool,normalize_embeddings=True,convert_to_numpy=True,batch_size=128,show_progress_bar=False).astype(np.float32)
    Qe=m.encode(qt,normalize_embeddings=True,convert_to_numpy=True,batch_size=128,show_progress_bar=False).astype(np.float32)
    Ssim=Qe@E.T
    Theta,Aclq,me=build_hyper(pool)
    ppr_h=appnp(Theta,Ssim); ppr_c=appnp(Aclq,Ssim)

    def rrf(a,b,k=60):
        ra={i:r for r,i in enumerate(np.argsort(-a))};rb={i:r for r,i in enumerate(np.argsort(-b))}
        return list(np.argsort(-np.array([1/(k+ra[i])+1/(k+rb[i]) for i in range(len(a))])))

    methods=["flat","binary_clique","hypergraph_zhou","hyper_rerank","hyper_fuse"]
    per={mm:{f"r@{k}":[] for k in KS} for mm in methods}; hard={mm:[] for mm in methods}
    for qi in range(len(qt)):
        g=qgold[qi];sim=Ssim[qi];flat=list(np.argsort(-sim))
        ranks={"flat":flat,"binary_clique":list(np.argsort(-ppr_c[:,qi])),
               "hypergraph_zhou":list(np.argsort(-ppr_h[:,qi]))}
        cand=flat[:100];sc={i:ppr_h[i,qi] for i in cand}
        ranks["hyper_rerank"]=sorted(cand,key=lambda i:-sc[i])+flat[100:]
        ranks["hyper_fuse"]=rrf(sim,ppr_h[:,qi])
        for mm in methods:
            for k in KS: per[mm][f"r@{k}"].append(recall(ranks[mm],g,k))
            if len(g)>=2:
                hh=min(g,key=lambda d:sim[d]); hard[mm].append(1.0 if hh in ranks[mm][:10] else 0.0)
    summary={mm:{k:round(statistics.mean(v),4) for k,v in per[mm].items()} for mm in methods}
    for mm in methods: summary[mm]["hardhop_r@10"]=round(statistics.mean(hard[mm]),4)
    def ci(mm,base):
        d=[per[mm]["r@10"][i]-per[base]["r@10"][i] for i in range(len(qt))]
        return {"mean":round(statistics.mean(d),4),"CI":boot(d)}
    ev={"experiment":"hswm_true_hypergraph_ml16","tree":"LakatosTree_PromSearchHSWM_20260721","node":"ML16-true-hypergraph",
        "correction":"ML13-15는 pairwise(이진)=HippoRAG식. 이번이 진짜 n-ary 하이퍼그래프(Zhou 2006 정규화).",
        "setup":{"benchmark":"MuSiQue-ans dev","n_questions":len(qt),"corpus_paragraphs":len(pool),"n_hyperedges(entities)":me,"model":mu},
        "recall_by_method":summary,
        "CI_hypergraph_vs_flat_r@10":ci("hypergraph_zhou","flat"),
        "CI_hypergraph_vs_binary_r@10":ci("hypergraph_zhou","binary_clique"),
        "CI_hyperfuse_vs_flat_r@10":ci("hyper_fuse","flat"),
        "conclusion":{
          "best_method":max(methods,key=lambda mm:summary[mm]["r@10"]),
          "hypergraph_beats_binary": summary["hypergraph_zhou"]["r@10"]>summary["binary_clique"]["r@10"],
          "hypergraph_beats_flat_sig": ci("hypergraph_zhou","flat")["CI"][0]>0,
          "hyperfuse_beats_flat_sig": ci("hyper_fuse","flat")["CI"][0]>0,
          "hypergraph_hardhop_vs_flat": round(summary["hypergraph_zhou"]["hardhop_r@10"]-summary["flat"]["hardhop_r@10"],4),
        },
        "note":"De^-1=하이퍼엣지 크기 정규화=n-ary 핵심. hypergraph>binary면 n-ary 구조가 값 더함. >flat면 USER 주장 실증."}
    out=HERE/"evidence"/"EVIDENCE_hswm_true_hypergraph_ml16_2026-07-21.json"
    out.write_text(json.dumps(ev,ensure_ascii=False,indent=2))
    print(json.dumps(ev,ensure_ascii=False,indent=2));print(f"\nEVIDENCE -> {out}",file=sys.stderr)

if __name__=="__main__": main()
