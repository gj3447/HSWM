#!/usr/bin/env python3
"""
ML15 — 롱기누스식 엔티티/참조 엣지 HSWM 재판정 (다양한 변종) on MuSiQue.

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML15-entity-graph-bench
ML14: 임베딩-코사인 엣지 HSWM = flat 못이김(멀티홉엔 유사도 아니라 공유엔티티=참조 필요).
USER 정전 "weight-semantic 롱기누스(참조 바인딩) 엣지" 제대로 구현: 엣지=공유 엔티티(co-reference).
확인됨: MuSiQue 2-hop 두 supporting이 공유엔티티('steve hillage')로 이어짐 — 코사인은 못 잇던 다리.

다양한 방법 재판정 (동일 MuSiQue 300q/4702 para, 공식 gold, bootstrap CI):
  flat            : 임베딩 코사인 top-k (baseline)
  emb_ppr         : 임베딩-그래프 PPR (ML14 실패, 참조용)
  ent_ppr         : 엔티티-공유 그래프 PPR, 임베딩 seed
  ent_ppr_idf     : 엔티티 그래프 IDF가중(희소엔티티=강한다리) PPR
  ent_qseed       : 엔티티 그래프, query-엔티티 seed (HippoRAG 충실)
  hybrid_ppr      : 엔티티+임베딩 그래프 결합 PPR
  ent_rerank      : 엔티티-PPR로 flat top-100 재랭킹 (2-stage)
  fuse_flat_ent   : RRF(flat, ent_ppr_idf) 융합
지표: recall@2/5/10 + bootstrap 95%CI vs flat.
"""
import json, sys, re, math, statistics, random, hashlib
from collections import defaultdict
from pathlib import Path
import numpy as np

MUSIQUE=Path("/Volumes/GM/bench/musique_dev.jsonl"); HERE=Path(__file__).parent
N_Q=300; KNN=10; SEED=333; KS=[2,5,10]; BOOT=2000; DF_CAP=40
STOP={"The","A","An","In","On","At","He","She","It","They","This","That","His","Her","When",
      "After","Before","There","Their","These","Those","As","Of","For","And","But","Also","However","Its"}

def ents(t):
    e=set()
    for m in re.findall(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b",t):
        if m not in STOP and len(m)>2: e.add(m.lower())
    return e

def load(n):
    exs=[json.loads(l) for l in open(MUSIQUE)]
    rng=random.Random(SEED); rng.shuffle(exs)
    exs=[e for e in exs if e.get("answerable",True)][:n]
    pool=[]; key2idx={}; qgold=[]; qtext=[]
    for e in exs:
        g=set()
        for p in e["paragraphs"]:
            k=hashlib.md5((p["title"]+"||"+p["paragraph_text"]).encode()).hexdigest()
            if k not in key2idx: key2idx[k]=len(pool); pool.append(p["title"]+". "+p["paragraph_text"])
            if p["is_supporting"]: g.add(key2idx[k])
        qgold.append(g); qtext.append(e["question"])
    return pool,qtext,qgold

def norm_adj(A):
    A=A+np.eye(A.shape[0],dtype=np.float32); d=A.sum(1); di=1/np.sqrt(np.maximum(d,1e-9))
    return (A*di[:,None])*di[None,:]

def emb_adj(E,knn):
    n=len(E); A=np.zeros((n,n),np.float32); B=1000
    for st in range(0,n,B):
        S=E[st:st+B]@E.T
        for r in range(S.shape[0]):
            i=st+r; S[r,i]=-2
            for j in np.argsort(-S[r])[:knn]:
                w=max(0.0,float(S[r,j])); A[i,j]=w; A[j,i]=max(A[j,i],w)
    return norm_adj(A)

def entity_adj(pool,idf_weight):
    n=len(pool); ent_list=[ents(p) for p in pool]
    inv=defaultdict(list)
    for i,es in enumerate(ent_list):
        for e in es: inv[e].append(i)
    df={e:len(ps) for e,ps in inv.items()}
    N=n; A=np.zeros((n,n),np.float32)
    for e,ps in inv.items():
        if not (2<=len(ps)<=DF_CAP): continue
        w=math.log(N/df[e]) if idf_weight else 1.0
        for a in range(len(ps)):
            for b in range(a+1,len(ps)):
                A[ps[a],ps[b]]+=w; A[ps[b],ps[a]]+=w
    return norm_adj(A), ent_list, df, N

def appnp_all(Ahat,S,alpha,K=10):
    s=np.maximum(S,0).T.astype(np.float32); pi=s.copy()
    for _ in range(K): pi=(1-alpha)*(Ahat@pi)+alpha*s
    return pi
def recall(r,g,k): return len(set(r[:k])&g)/len(g) if g else 0.0
def boot(d,reps=BOOT,seed=1):
    rng=random.Random(seed); n=len(d); ms=[sum(d[rng.randrange(n)] for _ in range(n))/n for _ in range(reps)]
    ms.sort(); return round(ms[int(.025*reps)],4),round(ms[int(.975*reps)],4)

def main():
    pool,qtext,qgold=load(N_Q)
    from sentence_transformers import SentenceTransformer
    import torch; torch.manual_seed(SEED)
    try: m=SentenceTransformer("all-MiniLM-L6-v2"); mu="all-MiniLM-L6-v2"
    except Exception: m=SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2"); mu="multilingual(fb)"
    E=m.encode(pool,normalize_embeddings=True,convert_to_numpy=True,batch_size=128,show_progress_bar=False).astype(np.float32)
    Qe=m.encode(qtext,normalize_embeddings=True,convert_to_numpy=True,batch_size=128,show_progress_bar=False).astype(np.float32)
    Ssim=Qe@E.T
    Aemb=emb_adj(E,KNN)
    Aent,ent_list,df,N=entity_adj(pool,idf_weight=False)
    Aent_idf,_,_,_=entity_adj(pool,idf_weight=True)
    Ahyb=norm_adj((Aemb+Aent_idf).astype(np.float32))

    # query-entity seed (HippoRAG): passage에 든 query 엔티티의 idf 합
    qseed=np.zeros((len(qtext),len(pool)),np.float32)
    for qi,q in enumerate(qtext):
        qe=ents(q)
        for i,es in enumerate(ent_list):
            sh=qe&es
            if sh: qseed[qi,i]=sum(math.log(N/max(1,df.get(e,1))) for e in sh)

    ppr_emb=appnp_all(Aemb,Ssim,0.3)
    ppr_ent=appnp_all(Aent,Ssim,0.3)
    ppr_ent_idf=appnp_all(Aent_idf,Ssim,0.3)
    ppr_ent_qseed=appnp_all(Aent_idf,qseed,0.3)
    ppr_hyb=appnp_all(Ahyb,Ssim,0.3)

    def rank_rrf(a,b,k=60):
        ra={i:r for r,i in enumerate(np.argsort(-a))}; rb={i:r for r,i in enumerate(np.argsort(-b))}
        sc=[1/(k+ra[i])+1/(k+rb[i]) for i in range(len(a))]; return list(np.argsort(-np.array(sc)))

    methods=["flat","emb_ppr","ent_ppr","ent_ppr_idf","ent_qseed","hybrid_ppr","ent_rerank","fuse_flat_ent"]
    per={mm:{f"r@{k}":[] for k in KS} for mm in methods}
    for qi in range(len(qtext)):
        g=qgold[qi]; sim=Ssim[qi]; flat=list(np.argsort(-sim))
        ranks={"flat":flat,
               "emb_ppr":list(np.argsort(-ppr_emb[:,qi])),
               "ent_ppr":list(np.argsort(-ppr_ent[:,qi])),
               "ent_ppr_idf":list(np.argsort(-ppr_ent_idf[:,qi])),
               "ent_qseed":list(np.argsort(-ppr_ent_qseed[:,qi])),
               "hybrid_ppr":list(np.argsort(-ppr_hyb[:,qi]))}
        cand=flat[:100]; sc={i:ppr_ent_idf[i,qi] for i in cand}
        ranks["ent_rerank"]=sorted(cand,key=lambda i:-sc[i])+flat[100:]
        ranks["fuse_flat_ent"]=rank_rrf(sim,ppr_ent_idf[:,qi])
        for mm in methods:
            for k in KS: per[mm][f"r@{k}"].append(recall(ranks[mm],g,k))
    summary={mm:{k:round(statistics.mean(v),4) for k,v in per[mm].items()} for mm in methods}
    best=max(methods,key=lambda mm:summary[mm]["r@10"])
    def ci_vs_flat(mm):
        d=[per[mm]["r@10"][i]-per["flat"]["r@10"][i] for i in range(len(qtext))]
        return {"mean":round(statistics.mean(d),4),"CI":boot(d)}
    cis={mm:ci_vs_flat(mm) for mm in methods if mm!="flat"}
    ev={"experiment":"hswm_entity_bench_ml15","tree":"LakatosTree_PromSearchHSWM_20260721","node":"ML15-entity-graph-bench",
        "setup":{"benchmark":"MuSiQue-ans dev","n_questions":len(qtext),"corpus_paragraphs":len(pool),"model":mu,
                 "entity_edges":"regex proper-noun NER, shared-entity graph, df 2..40","gold":"official is_supporting"},
        "recall_by_method":summary,
        "bootstrap_95CI_vs_flat_r@10":cis,
        "conclusion":{
          "best_method":best,"best_r@10":summary[best]["r@10"],"flat_r@10":summary["flat"]["r@10"],
          "best_gain_over_flat":round(summary[best]["r@10"]-summary["flat"]["r@10"],4),
          "any_entity_beats_flat_sig": any(cis[mm]["CI"][0]>0 for mm in cis if "ent" in mm or "fuse" in mm or "hybrid" in mm),
          "entity_beats_embedding_ppr": max(summary[mm]["r@10"] for mm in methods if "ent" in mm or "hybrid" in mm or "fuse" in mm)>summary["emb_ppr"]["r@10"],
        },
        "note":"롱기누스 엔티티엣지 재판정. flat=강baseline. CI하한>0=유의개선. emb_ppr=ML14 실패 참조."}
    out=HERE/"evidence"/"EVIDENCE_hswm_entity_bench_ml15_2026-07-21.json"
    out.write_text(json.dumps(ev,ensure_ascii=False,indent=2))
    print(json.dumps(ev,ensure_ascii=False,indent=2)); print(f"\nEVIDENCE -> {out}",file=sys.stderr)

if __name__=="__main__": main()
