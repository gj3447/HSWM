#!/usr/bin/env python3
"""
ML19 — 통합 HSWM payoff 재판정 (다방면: 다baseline × 다지표 × 도메인-강건).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML19-integrated-payoff
정전: INDEX.md §4-A. LakatoTree(ML18)가 요구한 "구조가 room 있는 판서 payoff 보여라".
확증조각 합체: n-ary 하이퍼그래프(ML16) + semantic SEED(ML17) + solid depth(ML18, GCNII residual).
하나(aggregate recall, flat 못이김)에 안 갇히게 여러 각도:

 baseline (다):  flat(임베딩) / binary_ppr(HippoRAG식 이진엔티티+qseed) / hypergraph(ML16확증)
                / hypergraph_soliddeep(GCNII K8) / hyper_fuse(RRF flat+hyper)
 지표 (다):     recall@10(참조) / hardhop@10(hop2 다리) / fullchain@10·@20(gold 전부=진짜 multi-hop성공)
 강건 (이식):   질의를 top-SV 중앙값으로 2 semantic 도메인 분할 → fullchain 이득이 A·B 양쪽 유지?

예측 사전등록:
 P1 hypergraph fullchain@10 > flat (구조가 multi-hop 합성서 payoff). base flat.
 P2 hypergraph hardhop@10 > binary_ppr (n-ary>이진 다리, ML16 확장).
 P3 fullchain@10 이득(hyper-flat) 부호가 도메인 A·B 양쪽 동일 (도메인-강건, 이식성).
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

def build_graphs(pool):
    n=len(pool); el=[ents(p) for p in pool]; inv=defaultdict(list)
    for i,es in enumerate(el):
        for e in es: inv[e].append(i)
    ent=[e for e,ps in inv.items() if DF_MIN<=len(ps)<=DF_MAX]; eidx={e:j for j,e in enumerate(ent)}; me=len(ent)
    H=np.zeros((n,me),np.float32)
    for e in ent:
        for p in inv[e]: H[p,eidx[e]]=1.0
    idf=np.array([math.log(n/len(inv[e])) for e in ent],np.float32); De=np.array([len(inv[e]) for e in ent],np.float32)
    HW=H*idf[None,:]
    # Zhou n-ary hypergraph (De^-1 = n-ary)
    Theta=(HW*(1/De)[None,:])@H.T; np.fill_diagonal(Theta,0)
    Dv=Theta.sum(1); dvi=1/np.sqrt(np.maximum(Dv,1e-9)); Theta=((Theta*dvi[:,None])*dvi[None,:]).astype(np.float32)
    # binary clique (De 정규화 없음 = HippoRAG식 이진)
    Ab=HW@H.T; np.fill_diagonal(Ab,0); db=Ab.sum(1); dbi=1/np.sqrt(np.maximum(db,1e-9))
    Ab=((Ab*dbi[:,None])*dbi[None,:]).astype(np.float32)
    return Theta,Ab,el,inv,n,me

def appnp(A,S,al=0.3,K=10):
    s=np.maximum(S,0).astype(np.float32); pi=s.copy()
    for _ in range(K): pi=(1-al)*(A@pi)+al*s
    return pi
def gcnii(A,S,al=0.15,K=8,lam=0.5):
    s=np.maximum(S,0).astype(np.float32); pi=s.copy()
    for l in range(1,K+1):
        beta=lam/l; pi=(1-beta)*((1-al)*(A@pi)+al*s)+beta*pi
    return pi
def recall(r,g,k):return len(set(r[:k])&g)/len(g) if g else 0.0
def fullchain(r,g,k):return 1.0 if g and g<=set(r[:k]) else 0.0
def boot(d,reps=BOOT,seed=1):
    if not d: return (0.0,0.0)
    rng=random.Random(seed);n=len(d);ms=[sum(d[rng.randrange(n)] for _ in range(n))/n for _ in range(reps)];ms.sort()
    return round(ms[int(.025*reps)],4),round(ms[int(.975*reps)],4)

def main():
    pool,qt,qg=load(N_Q)
    from sentence_transformers import SentenceTransformer
    import torch; torch.manual_seed(SEED)
    try:m=SentenceTransformer("all-MiniLM-L6-v2");mu="all-MiniLM-L6-v2"
    except Exception:m=SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2");mu="ml(fb)"
    E=m.encode(pool,normalize_embeddings=True,convert_to_numpy=True,batch_size=128,show_progress_bar=False).astype(np.float32)
    Qe=m.encode(qt,normalize_embeddings=True,convert_to_numpy=True,batch_size=128,show_progress_bar=False).astype(np.float32)
    Ssim=(Qe@E.T).astype(np.float32); Sful=Ssim.T.astype(np.float32)
    Theta,Ab,el,inv,N,me=build_graphs(pool)
    # query-entity seed (HippoRAG 충실)
    qseed=np.zeros((N,len(qt)),np.float32)
    for qi,q in enumerate(qt):
        qe=ents(q)
        for i,es in enumerate(el):
            sh=qe&es
            if sh: qseed[i,qi]=sum(math.log(N/max(1,len(inv.get(e,[1])))) for e in sh)

    ppr_hyper=appnp(Theta,Sful,0.3,10)          # ML16 확증 config
    ppr_soliddeep=gcnii(Theta,Sful,0.15,8)      # + solid GCNII 깊이(ML18)
    ppr_binary=appnp(Ab,qseed,0.3,10)           # HippoRAG식 이진+qseed
    def rrf(a,b,k=60):
        ra={i:r for r,i in enumerate(np.argsort(-a))};rb={i:r for r,i in enumerate(np.argsort(-b))}
        return list(np.argsort(-np.array([1/(k+ra[i])+1/(k+rb[i]) for i in range(len(a))])))

    methods=["flat","binary_ppr","hypergraph","hypergraph_soliddeep","hyper_fuse"]
    R={mm:{"recall@10":[],"hardhop@10":[],"fullchain@10":[],"fullchain@20":[]} for mm in methods}
    fc_hyper_flat=[]  # per-q fullchain@10 diff (hyper−flat)
    hh_hyper_bin=[]   # per-q hardhop@10 diff (hyper−binary)
    for qi in range(len(qt)):
        g=qg[qi];sim=Ssim[qi];flat=list(np.argsort(-sim))
        ranks={"flat":flat,"binary_ppr":list(np.argsort(-ppr_binary[:,qi])),
               "hypergraph":list(np.argsort(-ppr_hyper[:,qi])),
               "hypergraph_soliddeep":list(np.argsort(-ppr_soliddeep[:,qi])),
               "hyper_fuse":rrf(sim,ppr_hyper[:,qi])}
        multi=len(g)>=2; hd=min(g,key=lambda d:sim[d]) if multi else None
        for mm in methods:
            r=ranks[mm]
            R[mm]["recall@10"].append(recall(r,g,10))
            if multi:
                R[mm]["hardhop@10"].append(1.0 if hd in r[:10] else 0.0)
                R[mm]["fullchain@10"].append(fullchain(r,g,10))
                R[mm]["fullchain@20"].append(fullchain(r,g,20))
        if multi:
            fc_hyper_flat.append(R["hypergraph"]["fullchain@10"][-1]-R["flat"]["fullchain@10"][-1])
            hh_hyper_bin.append(R["hypergraph"]["hardhop@10"][-1]-R["binary_ppr"]["hardhop@10"][-1])
    summ={mm:{k:round(statistics.mean(v),4) for k,v in R[mm].items() if v} for mm in methods}
    n_multi=len(fc_hyper_flat)

    # 도메인 강건 (이식): top-SV 중앙값으로 질의 2분할, 각 도메인서 fullchain@10 hyper−flat
    Qc=Qe-Qe.mean(0,keepdims=True); U,Sv,Vt=np.linalg.svd(Qc,full_matrices=False); proj=Qc@Vt[0]
    med=float(np.median(proj)); domA=[qi for qi in range(len(qt)) if proj[qi]<med]; domB=[qi for qi in range(len(qt)) if proj[qi]>=med]
    def fc_diff_on(sub):
        d=[fullchain(list(np.argsort(-ppr_hyper[:,qi])),qg[qi],10)-fullchain(list(np.argsort(-Ssim[qi])),qg[qi],10)
           for qi in sub if len(qg[qi])>=2]
        return round(statistics.mean(d),4) if d else 0.0, len(d)
    dA,nA=fc_diff_on(domA); dB,nB=fc_diff_on(domB)

    ev={"experiment":"hswm_integrated_payoff_ml19","tree":"LakatosTree_PromSearchHSWM_20260721","node":"ML19-integrated-payoff",
        "canon":"INDEX.md §4-A. 확증조각(ML16 n-ary + ML17 sem-seed + ML18 solid) 합체를 multi-hop payoff 지표로.",
        "setup":{"benchmark":"MuSiQue-ans dev","n_questions":len(qt),"n_multihop(|gold|>=2)":n_multi,"corpus":N,"hyperedges":me,"model":mu},
        "metrics_by_method":summ,
        "payoff_CI":{
          "P1_fullchain@10_hypergraph_minus_flat":{"mean":round(statistics.mean(fc_hyper_flat),4),"CI":boot(fc_hyper_flat)},
          "P2_hardhop@10_hypergraph_minus_binary":{"mean":round(statistics.mean(hh_hyper_bin),4),"CI":boot(hh_hyper_bin)},
        },
        "P3_domain_robustness":{"domA_fullchain_diff":dA,"nA":nA,"domB_fullchain_diff":dB,"nB":nB,
                                "sign_consistent": (dA>=0)==(dB>=0)},
        "verdict":{
          "P1_hyper_beats_flat_fullchain": summ["hypergraph"]["fullchain@10"]>summ["flat"]["fullchain@10"],
          "P1_sig": boot(fc_hyper_flat)[0]>0,
          "P2_hyper_beats_binary_hardhop": summ["hypergraph"]["hardhop@10"]>summ["binary_ppr"]["hardhop@10"],
          "P2_sig": boot(hh_hyper_bin)[0]>0,
          "P3_domain_robust": (dA>=0)==(dB>=0),
          "best_fullchain@10": max(methods,key=lambda mm:summ[mm].get("fullchain@10",0)),
          "best_hardhop@10": max(methods,key=lambda mm:summ[mm].get("hardhop@10",0)),
        },
        "note":"다방면: 다baseline(flat/binary/hyper/soliddeep/fuse) × 다지표(recall/hardhop/fullchain) × 도메인강건. fullchain=진짜 multi-hop성공(gold전부)."}
    out=HERE/"evidence"/"EVIDENCE_hswm_integrated_payoff_ml19_2026-07-21.json"
    out.write_text(json.dumps(ev,ensure_ascii=False,indent=2))
    print(json.dumps(ev,ensure_ascii=False,indent=2)); print(f"\nEVIDENCE -> {out}",file=sys.stderr)

if __name__=="__main__": main()
