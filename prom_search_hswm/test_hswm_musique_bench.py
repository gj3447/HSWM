#!/usr/bin/env python3
"""
ML14 — 실 벤치 재현: MuSiQue multi-hop서 PPR 딥HSWM vs flat vs iterative (bootstrap CI).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML14-musique-bench
ML13(toy)=PPR +5.8pp. 이걸 실 벤치(MuSiQue-ans dev, Trivedi 2022)로 꼼꼼히 재현.
세팅(HippoRAG식): N질문 paragraph를 한 corpus로 풀링 → 질문마다 gold supporting(≥2 문서 multi-hop) recall.
방법: flat / ppr α{0.15,0.3,0.5} APPNP / ppr_rerank(flat top-100 위 2-stage) / iterative(PRF 1-step, 그래프無 대조).
지표: recall@2/@5/@10 + full_chain@10(모든 supporting top-10) . bootstrap 95%CI (질문 resample) ppr_rerank−flat.
정직: 약baseline이 graph이득 부풀림(Agent3) → 영어 retriever 우선. gold=공식 is_supporting(crude 아님).
"""
import json, sys, statistics, random, hashlib
from pathlib import Path
import numpy as np

MUSIQUE=Path("/Volumes/GM/bench/musique_dev.jsonl"); HERE=Path(__file__).parent
N_Q=300; KNN=10; SEED=333; KS=[2,5,10]; BOOT=2000

def load(n):
    exs=[]
    with open(MUSIQUE) as f:
        for line in f:
            exs.append(json.loads(line))
    rng=random.Random(SEED); rng.shuffle(exs)
    exs=[e for e in exs if e.get("answerable",True)][:n]
    # pool paragraphs, dedupe
    pool=[]; key2idx={}
    qgold=[]  # per-question set of pool idx (supporting)
    qtext=[]
    for e in exs:
        g=set()
        for p in e["paragraphs"]:
            k=hashlib.md5((p["title"]+"||"+p["paragraph_text"]).encode()).hexdigest()
            if k not in key2idx:
                key2idx[k]=len(pool); pool.append(p["title"]+". "+p["paragraph_text"])
            if p["is_supporting"]: g.add(key2idx[k])
        qgold.append(g); qtext.append(e["question"])
    return pool,qtext,qgold

def build_adj(E,knn):
    n=len(E); A=np.zeros((n,n),np.float32)
    B=1000
    for st in range(0,n,B):
        S=E[st:st+B]@E.T
        for r in range(S.shape[0]):
            i=st+r; S[r,i]=-2
            for j in np.argsort(-S[r])[:knn]:
                w=max(0.0,float(S[r,j])); A[i,j]=w; A[j,i]=max(A[j,i],w)
    A=A+np.eye(n,dtype=np.float32); d=A.sum(1); di=1/np.sqrt(np.maximum(d,1e-9))
    return (A*di[:,None])*di[None,:]

def recall(ranked,gold,k): return len(set(ranked[:k])&gold)/len(gold) if gold else 0.0
def fullchain(ranked,gold,k): return 1.0 if gold and gold<=set(ranked[:k]) else 0.0

def boot(diffs,reps=BOOT,seed=1):
    rng=random.Random(seed); n=len(diffs); ms=[]
    for _ in range(reps): ms.append(sum(diffs[rng.randrange(n)] for _ in range(n))/n)
    ms.sort(); return round(ms[int(.025*reps)],4),round(ms[int(.975*reps)],4)

def main():
    pool,qtext,qgold=load(N_Q)
    from sentence_transformers import SentenceTransformer
    import torch; torch.manual_seed(SEED)
    model_used="all-MiniLM-L6-v2"
    try: m=SentenceTransformer("all-MiniLM-L6-v2")
    except Exception: m=SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2"); model_used="paraphrase-multilingual(fallback)"
    E=m.encode(pool,normalize_embeddings=True,convert_to_numpy=True,batch_size=128,show_progress_bar=False).astype(np.float32)
    Qe=m.encode(qtext,normalize_embeddings=True,convert_to_numpy=True,batch_size=128,show_progress_bar=False).astype(np.float32)
    Ahat=build_adj(E,KNN)

    Ssim=Qe@E.T  # (nq, npool)
    methods=["flat","iterative","ppr_a0.15","ppr_a0.3","ppr_a0.5","ppr_rerank_a0.3"]
    per={mm:{f"r@{k}":[] for k in KS} for mm in methods}
    for mm in methods: per[mm]["chain@10"]=[]
    # batch APPNP: seed = relu(sim).T  (npool, nq)
    def appnp_all(alpha,K=10):
        s=np.maximum(Ssim,0).T.astype(np.float32)  # (npool,nq)
        pi=s.copy()
        for _ in range(K): pi=(1-alpha)*(Ahat@pi)+alpha*s
        return pi  # (npool,nq)
    ppr={a:appnp_all(a) for a in (0.15,0.3,0.5)}

    for qi in range(len(qtext)):
        gold=qgold[qi]; sim=Ssim[qi]
        flat=list(np.argsort(-sim))
        # iterative PRF: top-1 para 임베딩으로 질의 확장 후 재검색
        q2=Qe[qi]+E[flat[0]]; q2=q2/(np.linalg.norm(q2)+1e-9)
        it=list(np.argsort(-(E@q2)))
        ranks={"flat":flat,"iterative":it,
               "ppr_a0.15":list(np.argsort(-ppr[0.15][:,qi])),
               "ppr_a0.3":list(np.argsort(-ppr[0.3][:,qi])),
               "ppr_a0.5":list(np.argsort(-ppr[0.5][:,qi]))}
        # ppr_rerank: flat top-100 위 ppr0.3
        cand=flat[:100]; sc={i:ppr[0.3][i,qi] for i in cand}
        ranks["ppr_rerank_a0.3"]=sorted(cand,key=lambda i:-sc[i])+flat[100:]
        for mm in methods:
            for k in KS: per[mm][f"r@{k}"].append(recall(ranks[mm],gold,k))
            per[mm]["chain@10"].append(fullchain(ranks[mm],gold,10))

    summary={mm:{k:round(statistics.mean(v),4) for k,v in per[mm].items()} for mm in methods}
    best=max(methods,key=lambda mm:summary[mm]["r@10"])
    diff_pf=[per["ppr_rerank_a0.3"]["r@10"][i]-per["flat"]["r@10"][i] for i in range(len(qtext))]
    diff_pi=[per["ppr_rerank_a0.3"]["r@10"][i]-per["iterative"]["r@10"][i] for i in range(len(qtext))]
    ci_pf=boot(diff_pf); ci_pi=boot(diff_pi)
    ev={"experiment":"hswm_musique_bench_ml14","tree":"LakatosTree_PromSearchHSWM_20260721","node":"ML14-musique-bench",
        "setup":{"benchmark":"MuSiQue-ans dev (Trivedi 2022)","n_questions":len(qtext),"corpus_paragraphs":len(pool),
                 "model":model_used,"graph":f"kNN={KNN}","gold":"official is_supporting (multi-hop chain, >=2 docs)"},
        "recall_by_method":summary,
        "bootstrap_95CI":{"ppr_rerank_minus_flat_r@10":{"mean":round(statistics.mean(diff_pf),4),"CI":ci_pf},
                          "ppr_rerank_minus_iterative_r@10":{"mean":round(statistics.mean(diff_pi),4),"CI":ci_pi}},
        "conclusion":{
          "best_method":best,
          "best_ppr_r@10":round(max(summary[mm]["r@10"] for mm in methods if "ppr" in mm),4),
          "flat_r@10":summary["flat"]["r@10"],
          "ppr_beats_flat_significant": ci_pf[0]>0,
          "ppr_beats_iterative_significant": ci_pi[0]>0,
          "ppr_gain_over_flat_r@10": round(max(summary[mm]["r@10"] for mm in methods if "ppr" in mm)-summary["flat"]["r@10"],4),
        },
        "note":"실 벤치 MuSiQue. gold=공식 supporting(진짜 multi-hop). CI 하한>0 = 유의. Agent3 사전확률 +3~5pp 단일책; 벤치는 더 클수도."}
    out=HERE/"evidence"/"EVIDENCE_hswm_musique_bench_ml14_2026-07-21.json"
    out.write_text(json.dumps(ev,ensure_ascii=False,indent=2))
    print(json.dumps(ev,ensure_ascii=False,indent=2)); print(f"\nEVIDENCE -> {out}",file=sys.stderr)

if __name__=="__main__": main()
