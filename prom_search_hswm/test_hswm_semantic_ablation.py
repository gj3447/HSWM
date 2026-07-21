#!/usr/bin/env python3
"""
ML17 — "Semantic Weight Mapper" 유의성 ablation on MuSiQue.

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML17-semantic-weight-ablation
ML16: n-ary 하이퍼그래프(구조) > 이진, hard-hop>flat. 이제 HSWM의 "Semantic Weight" 성분 분리:
  그래프 엣지/시드에 의미(임베딩) 가중을 넣는 게 구조-only 대비 값 더하나?
  예측: 멀티홉 다리는 의미가 *다른* 문단을 잇는 것 → semantic 엣지가중이 다리를 죽일 수도(hard-hop↓).

Ablation (동일 하이퍼그래프 구조 위):
  flat                 : 의미-only, 구조 無 (baseline)
  hyper_struct_semseed : 구조 하이퍼그래프 + query-임베딩 seed (=ML16). 의미는 seed에만.
  hyper_struct_entseed : 구조 하이퍼그래프 + query-엔티티 seed. 의미 seed 제거 = 순수 구조.
  hyper_semedge        : 구조 하이퍼그래프 엣지에 의미(cos) 가중 곱. 의미를 엣지에도.
  hyper_fuse           : RRF(flat, hyper_struct). 의미(flat)+구조(hyper) 랭크융합.
분해 질문: (a)semantic SEED 유의? (semseed vs entseed) (b)semantic EDGE 유의? (semedge vs struct)
지표: recall@10 + hard-hop@10 + CI.
"""
import json, sys, re, math, statistics, random, hashlib
from collections import defaultdict
from pathlib import Path
import numpy as np

MUSIQUE=Path("/Volumes/GM/bench/musique_dev.jsonl"); HERE=Path(__file__).parent
N_Q=300; SEED=333; BOOT=2000; DF_MIN=2; DF_MAX=40
STOP={"The","A","An","In","On","At","He","She","It","They","This","That","His","Her","When","After",
      "Before","There","Their","These","Those","As","Of","For","And","But","Also","However","Its"}
def ents(t):return {mm.lower() for mm in re.findall(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b",t) if mm not in STOP and len(mm)>2}

def load(n):
    exs=[json.loads(l) for l in open(MUSIQUE)]; random.Random(SEED).shuffle(exs)
    exs=[e for e in exs if e.get("answerable",True)][:n]
    pool=[];k2i={};qg=[];qt=[]
    for e in exs:
        g=set()
        for p in e["paragraphs"]:
            k=hashlib.md5((p["title"]+"||"+p["paragraph_text"]).encode()).hexdigest()
            if k not in k2i:k2i[k]=len(pool);pool.append(p["title"]+". "+p["paragraph_text"])
            if p["is_supporting"]:g.add(k2i[k])
        qg.append(g);qt.append(e["question"])
    return pool,qt,qg

def appnp(Ahat,S,al=0.3,K=10):
    s=np.maximum(S,0).T.astype(np.float32);pi=s.copy()
    for _ in range(K):pi=(1-al)*(Ahat@pi)+al*s
    return pi
def recall(r,g,k):return len(set(r[:k])&g)/len(g) if g else 0.0
def boot(d,reps=BOOT,seed=1):
    rng=random.Random(seed);n=len(d);ms=[sum(d[rng.randrange(n)] for _ in range(n))/n for _ in range(reps)];ms.sort()
    return round(ms[int(.025*reps)],4),round(ms[int(.975*reps)],4)

def main():
    pool,qt,qg=load(N_Q)
    from sentence_transformers import SentenceTransformer
    import torch;torch.manual_seed(SEED)
    try:m=SentenceTransformer("all-MiniLM-L6-v2");mu="all-MiniLM-L6-v2"
    except Exception:m=SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2");mu="ml(fb)"
    E=m.encode(pool,normalize_embeddings=True,convert_to_numpy=True,batch_size=128,show_progress_bar=False).astype(np.float32)
    Qe=m.encode(qt,normalize_embeddings=True,convert_to_numpy=True,batch_size=128,show_progress_bar=False).astype(np.float32)
    Ssim=Qe@E.T
    # entity hypergraph (Zhou), + entity seed
    el=[ents(p) for p in pool];inv=defaultdict(list)
    for i,es in enumerate(el):
        for e in es:inv[e].append(i)
    ent=[e for e,ps in inv.items() if DF_MIN<=len(ps)<=DF_MAX];eidx={e:j for j,e in enumerate(ent)};me=len(ent);N=len(pool)
    H=np.zeros((N,me),np.float32)
    for e in ent:
        for p in inv[e]:H[p,eidx[e]]=1.0
    idf=np.array([math.log(N/len(inv[e])) for e in ent],np.float32);De=np.array([len(inv[e]) for e in ent],np.float32)
    HW=H*idf[None,:];Theta=(HW*(1/De)[None,:])@H.T;np.fill_diagonal(Theta,0)
    Dv=Theta.sum(1);dvi=1/np.sqrt(np.maximum(Dv,1e-9));Theta=(Theta*dvi[:,None])*dvi[None,:]
    # semantic-edge weighted hypergraph: 구조 연결 × 의미 유사도 (음수 clip)
    cosE=np.maximum(E@E.T,0).astype(np.float32)
    Theta_sem=Theta*cosE; ds=Theta_sem.sum(1);dsi=1/np.sqrt(np.maximum(ds,1e-9));Theta_sem=(Theta_sem*dsi[:,None])*dsi[None,:]
    # entity seed
    qseed=np.zeros((len(qt),N),np.float32)
    for qi,q in enumerate(qt):
        qe=ents(q)
        for i,es in enumerate(el):
            sh=qe&es
            if sh:qseed[qi,i]=sum(math.log(N/max(1,len(inv.get(e,[1])))) for e in sh)

    ppr_semseed=appnp(Theta,Ssim)      # 구조 그래프 + 의미 seed (ML16)
    ppr_entseed=appnp(Theta,qseed)     # 구조 그래프 + 엔티티 seed (의미 seed 제거)
    ppr_semedge=appnp(Theta_sem,Ssim)  # 의미-엣지가중 그래프 + 의미 seed

    def rrf(a,b,k=60):
        ra={i:r for r,i in enumerate(np.argsort(-a))};rb={i:r for r,i in enumerate(np.argsort(-b))}
        return list(np.argsort(-np.array([1/(k+ra[i])+1/(k+rb[i]) for i in range(len(a))])))

    methods=["flat","hyper_struct_semseed","hyper_struct_entseed","hyper_semedge","hyper_fuse"]
    per={mm:[] for mm in methods};hard={mm:[] for mm in methods}
    for qi in range(len(qt)):
        g=qg[qi];sim=Ssim[qi];flat=list(np.argsort(-sim))
        ranks={"flat":flat,
               "hyper_struct_semseed":list(np.argsort(-ppr_semseed[:,qi])),
               "hyper_struct_entseed":list(np.argsort(-ppr_entseed[:,qi])),
               "hyper_semedge":list(np.argsort(-ppr_semedge[:,qi])),
               "hyper_fuse":rrf(sim,ppr_semseed[:,qi])}
        for mm in methods:
            per[mm].append(recall(ranks[mm],g,10))
            if len(g)>=2:hard[mm].append(1.0 if min(g,key=lambda d:sim[d]) in ranks[mm][:10] else 0.0)
    summ={mm:{"recall@10":round(statistics.mean(per[mm]),4),"hardhop@10":round(statistics.mean(hard[mm]),4)} for mm in methods}
    def ci(a,b):
        d=[per[a][i]-per[b][i] for i in range(len(qt))];return {"mean":round(statistics.mean(d),4),"CI":boot(d)}
    ev={"experiment":"hswm_semantic_ablation_ml17","tree":"LakatosTree_PromSearchHSWM_20260721","node":"ML17-semantic-weight-ablation",
        "setup":{"benchmark":"MuSiQue-ans dev","n_questions":len(qt),"corpus":N,"hyperedges":me,"model":mu},
        "recall_and_hardhop":summ,
        "ablation_CI":{
          "semantic_SEED_effect(semseed−entseed)":ci("hyper_struct_semseed","hyper_struct_entseed"),
          "semantic_EDGE_effect(semedge−struct)":ci("hyper_semedge","hyper_struct_semseed"),
          "fuse_vs_flat":ci("hyper_fuse","flat"),
        },
        "conclusion":{
          "semantic_seed_helps": summ["hyper_struct_semseed"]["recall@10"]>summ["hyper_struct_entseed"]["recall@10"],
          "semantic_edge_helps_recall": summ["hyper_semedge"]["recall@10"]>summ["hyper_struct_semseed"]["recall@10"],
          "semantic_edge_hardhop_delta": round(summ["hyper_semedge"]["hardhop@10"]-summ["hyper_struct_semseed"]["hardhop@10"],4),
          "best_method":max(methods,key=lambda mm:summ[mm]["recall@10"]),
          "best_hardhop":max(methods,key=lambda mm:summ[mm]["hardhop@10"]),
        },
        "note":"Semantic Weight Mapper 유의성. semantic_seed=의미시드효과, semantic_edge=의미엣지가중효과. 멀티홉 다리(hard-hop)는 의미-이질이라 semantic edge가 죽일 수 있음 = 예측검증."}
    out=HERE/"evidence"/"EVIDENCE_hswm_semantic_ablation_ml17_2026-07-21.json"
    out.write_text(json.dumps(ev,ensure_ascii=False,indent=2))
    print(json.dumps(ev,ensure_ascii=False,indent=2));print(f"\nEVIDENCE -> {out}",file=sys.stderr)

if __name__=="__main__": main()
