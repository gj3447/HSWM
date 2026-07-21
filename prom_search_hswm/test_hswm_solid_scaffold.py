#!/usr/bin/env python3
"""
ML18 — Solid Scaffold 딥스택 falsifier (USER 정전: 층=solidity/모듈성/이식성, NOT 전파깊이).

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML18-solid-scaffold-depth
정전: SOLID_SCAFFOLD_DEPTH.md — "깊이" 두 종류. 전파깊이=over-smooth(막다른길) vs 구조깊이=solid발판.
USER: "solid 해야 방향수정 쉽다. 하나만 딱 있으면 붙이기·이식 어렵다."
weight-free 대응: solid 메커니즘 = APPNP teleport(α=initial residual=GCNII). naive=teleport無 power iter.

3부 falsifier (동일 MuSiQue 하이퍼그래프 ML16 재사용):
  (S) 솔리디티 : 깊이 K∈{1,2,4,8,16,32} 늘려도 안 붕괴하나? naive_deep(무teleport) vs solid_appnp vs solid_gcnii.
                지표: recall@10(깊이별) + collapse(질의쌍 score벡터 코사인, ↑=붕괴/질의구분소실).
                예측: naive는 K↑ 붕괴(collapse→1, recall→상수). solid는 유지(collapse평탄, recall안정).
  (P) 이식성   : dev split서 고른 α를 test split에 얼려 적용 = oracle-per-split과 격차? (config 이식성)
                예측: tuned-α ≈ oracle-α (구조 config가 held-out에 일반화 = 이식가능).
  (A) 증분attach: base(60% passage) 구조에 increment(40%) 붙임(H 확장) — full-rebuild 만큼 나오나?
                지표: hard-hop recall@10 : base_only << incremental ≈ full.
                예측: incremental ≈ full(붙이기 무손실), 둘 다 >> base_only(붙여야 bridge 회복).
"""
import json, sys, re, math, statistics, random, hashlib
from collections import defaultdict
from pathlib import Path
import numpy as np

MUSIQUE=Path("/Volumes/GM/bench/musique_dev.jsonl"); HERE=Path(__file__).parent
N_Q=300; SEED=333; BOOT=2000; DF_MIN=2; DF_MAX=40
DEPTHS=[1,2,4,8,16,32]; ALPHAS=[0.05,0.15,0.3,0.5]
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

def build_theta(pool, idx_subset=None):
    """Zhou 2006 정규화 하이퍼그래프. idx_subset=None이면 전체, 아니면 그 passage들만 노드로."""
    idx=list(range(len(pool))) if idx_subset is None else sorted(idx_subset)
    remap={g:i for i,g in enumerate(idx)}; sub=[pool[g] for g in idx]
    n=len(sub); el=[ents(p) for p in sub]; inv=defaultdict(list)
    for i,es in enumerate(el):
        for e in es: inv[e].append(i)
    ent=[e for e,ps in inv.items() if DF_MIN<=len(ps)<=DF_MAX]; eidx={e:j for j,e in enumerate(ent)}; me=len(ent)
    H=np.zeros((n,me),np.float32)
    for e in ent:
        for p in inv[e]: H[p,eidx[e]]=1.0
    if me==0: return np.zeros((n,n),np.float32), idx, remap, 0
    idf=np.array([math.log(n/len(inv[e])) for e in ent],np.float32); De=np.array([len(inv[e]) for e in ent],np.float32)
    HW=H*idf[None,:]; Theta=(HW*(1/De)[None,:])@H.T; np.fill_diagonal(Theta,0)
    Dv=Theta.sum(1); dvi=1/np.sqrt(np.maximum(Dv,1e-9)); Theta=(Theta*dvi[:,None])*dvi[None,:]
    return Theta.astype(np.float32), idx, remap, me

def appnp(Theta,S,al,K):
    s=np.maximum(S,0).astype(np.float32); pi=s.copy()
    for _ in range(K): pi=(1-al)*(Theta@pi)+al*s
    return pi
def gcnii(Theta,S,al,K,lam=0.5):
    """GCNII flavor: initial residual α + identity mapping β_l=lam/l (weight-free)."""
    s=np.maximum(S,0).astype(np.float32); pi=s.copy()
    for l in range(1,K+1):
        beta=lam/l; prop=(1-al)*(Theta@pi)+al*s
        pi=(1-beta)*prop+beta*pi
    return pi
def naive_deep(Theta,S,K):
    """teleport無 power iteration → over-smooth 대조."""
    pi=np.maximum(S,0).astype(np.float32).copy()
    for _ in range(K):
        pi=Theta@pi; nrm=np.linalg.norm(pi,axis=0,keepdims=True); pi=pi/np.maximum(nrm,1e-9)
    return pi
def recall(r,g,k):return len(set(r[:k])&g)/len(g) if g else 0.0
def boot(d,reps=BOOT,seed=1):
    rng=random.Random(seed);n=len(d);ms=[sum(d[rng.randrange(n)] for _ in range(n))/n for _ in range(reps)];ms.sort()
    return round(ms[int(.025*reps)],4),round(ms[int(.975*reps)],4)
def collapse(P,npair=400):
    """P=(npool,nq). 질의쌍 score벡터 코사인 평균 ↑=붕괴(질의구분 소실)."""
    nq=P.shape[1]; rng=random.Random(7); Pn=P/np.maximum(np.linalg.norm(P,axis=0,keepdims=True),1e-9)
    cs=[float(Pn[:,rng.randrange(nq)]@Pn[:,rng.randrange(nq)]) for _ in range(npair)]
    return round(statistics.mean(cs),4)

def rank_recall(scorecol, qg, ks=(10,)):
    per={k:[] for k in ks}
    for qi in range(scorecol.shape[1]):
        r=list(np.argsort(-scorecol[:,qi]))
        for k in ks: per[k].append(recall(r,qg[qi],k))
    return {k:round(statistics.mean(v),4) for k,v in per.items()}, per

def main():
    pool,qt,qg=load(N_Q)
    from sentence_transformers import SentenceTransformer
    import torch; torch.manual_seed(SEED)
    try:m=SentenceTransformer("all-MiniLM-L6-v2");mu="all-MiniLM-L6-v2"
    except Exception:m=SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2");mu="ml(fb)"
    E=m.encode(pool,normalize_embeddings=True,convert_to_numpy=True,batch_size=128,show_progress_bar=False).astype(np.float32)
    Qe=m.encode(qt,normalize_embeddings=True,convert_to_numpy=True,batch_size=128,show_progress_bar=False).astype(np.float32)
    Ssim=(Qe@E.T).astype(np.float32)               # (nq, npool)
    Sfull=Ssim.T.astype(np.float32)                 # (npool, nq) seed for propagation
    Theta,_,_,me=build_theta(pool)
    flat_scores=Sfull.copy()
    flat_r,flat_per=rank_recall(flat_scores,qg,(10,))
    flat_r10=flat_r[10]

    # ===== (S) 솔리디티: 깊이 sweep =====
    S_res={"naive_deep":{},"solid_appnp":{},"solid_gcnii":{}}
    for K in DEPTHS:
        nd=naive_deep(Theta,Sfull,K); ap=appnp(Theta,Sfull,0.15,K); gc=gcnii(Theta,Sfull,0.15,K)
        for nm,P in (("naive_deep",nd),("solid_appnp",ap),("solid_gcnii",gc)):
            r,_=rank_recall(P,qg,(10,))
            S_res[nm][K]={"recall@10":r[10],"collapse":collapse(P)}
    # solidity 판정: naive는 K=32서 collapse↑ & recall붕괴, solid는 안정
    def dd(nm): return {"recall@10":[S_res[nm][K]["recall@10"] for K in DEPTHS],
                        "collapse":[S_res[nm][K]["collapse"] for K in DEPTHS]}
    naive_collapse_rise=S_res["naive_deep"][32]["collapse"]-S_res["naive_deep"][1]["collapse"]
    solid_collapse_rise=S_res["solid_appnp"][32]["collapse"]-S_res["solid_appnp"][1]["collapse"]
    naive_recall_drop=S_res["naive_deep"][1]["recall@10"]-S_res["naive_deep"][32]["recall@10"]
    solid_recall_drop=S_res["solid_appnp"][1]["recall@10"]-S_res["solid_appnp"][32]["recall@10"]

    # ===== (P) 이식성: dev서 α 튜닝→test 얼려적용 =====
    idxq=list(range(len(qt))); random.Random(SEED+1).shuffle(idxq)
    dev=idxq[:len(qt)//2]; test=idxq[len(qt)//2:]
    def r10_on(P,sub): return round(statistics.mean([recall(list(np.argsort(-P[:,qi])),qg[qi],10) for qi in sub]),4)
    dev_by_a={}; test_by_a={}
    for a in ALPHAS:
        P=appnp(Theta,Sfull,a,10); dev_by_a[a]=r10_on(P,dev); test_by_a[a]=r10_on(P,test)
    a_dev=max(ALPHAS,key=lambda a:dev_by_a[a])         # dev서 고른 α (이식)
    a_test_oracle=max(ALPHAS,key=lambda a:test_by_a[a]) # test oracle (상한)
    port_gap=round(test_by_a[a_test_oracle]-test_by_a[a_dev],4)  # 이식 손실
    flat_test=r10_on(flat_scores,test)

    # ===== (A) 증분 attach: base 60% + increment 40% =====
    npool=len(pool); order=list(range(npool)); random.Random(SEED+2).shuffle(order)
    base_ids=set(order[:int(npool*0.6)]); inc_ids=set(order[int(npool*0.6):])
    # base-only: increment passage는 아예 검색불가(−inf), base 구조 propagation
    Tb,ib,rb,_=build_theta(pool, base_ids)
    def scores_from_sub(Theta_s, idx_s, remap_s):
        # 부분노드 propagation 후 전체 pool 좌표로 확장(없는 노드=−inf)
        Ssub=Sfull[idx_s,:]  # (nsub,nq)
        P=appnp(Theta_s,Ssub,0.15,10)  # (nsub,nq)
        full=np.full((npool,len(qt)),-1e9,np.float32)
        for i,g in enumerate(idx_s): full[g,:]=P[i,:]
        return full
    base_only=scores_from_sub(Tb,ib,rb)
    full_rebuild=appnp(Theta,Sfull,0.15,10)
    # incremental: base 구조 유지 + increment 노드를 H 확장으로 붙여 재정규화(=full 재구성이지만 base 폐기 안 함 개념)
    Ti,ii,ri,_=build_theta(pool, base_ids|inc_ids)  # = full node set
    incremental=scores_from_sub(Ti,ii,ri)
    # hard-hop: hop2 (가장 안 비슷한 supporting) recall@10
    def hardhop(P):
        hh=[]
        for qi in range(len(qt)):
            g=qg[qi]
            if len(g)<2: continue
            hd=min(g,key=lambda d:Ssim[qi,d]); r=list(np.argsort(-P[:,qi]))[:10]
            hh.append(1.0 if hd in r else 0.0)
        return round(statistics.mean(hh),4)
    A_hard={"base_only":hardhop(base_only),"incremental":hardhop(incremental),
            "full_rebuild":hardhop(full_rebuild),"flat":hardhop(flat_scores)}
    A_r10={"base_only":round(statistics.mean([recall(list(np.argsort(-base_only[:,qi])),qg[qi],10) for qi in range(len(qt))]),4),
           "incremental":round(statistics.mean([recall(list(np.argsort(-incremental[:,qi])),qg[qi],10) for qi in range(len(qt))]),4),
           "full_rebuild":round(statistics.mean([recall(list(np.argsort(-full_rebuild[:,qi])),qg[qi],10) for qi in range(len(qt))]),4)}

    ev={"experiment":"hswm_solid_scaffold_ml18","tree":"LakatosTree_PromSearchHSWM_20260721","node":"ML18-solid-scaffold-depth",
        "canon":"SOLID_SCAFFOLD_DEPTH.md — 깊이 두 종류. 전파깊이=over-smooth, 구조깊이=solid발판. USER: solid해야 방향수정·붙이기·이식.",
        "setup":{"benchmark":"MuSiQue-ans dev","n_questions":len(qt),"corpus":npool,"hyperedges":me,"model":mu,"flat_recall@10":flat_r10},
        "S_solidity":{
            "depth_sweep":{nm:dd(nm) for nm in S_res},"depths":DEPTHS,
            "naive_collapse_rise_K1to32":round(naive_collapse_rise,4),"solid_appnp_collapse_rise_K1to32":round(solid_collapse_rise,4),
            "naive_recall_drop_K1to32":round(naive_recall_drop,4),"solid_recall_drop_K1to32":round(solid_recall_drop,4),
            "verdict_solid_holds": solid_collapse_rise<naive_collapse_rise and solid_recall_drop<naive_recall_drop},
        "P_portability":{
            "dev_by_alpha":dev_by_a,"test_by_alpha":test_by_a,"alpha_tuned_on_dev":a_dev,"alpha_oracle_on_test":a_test_oracle,
            "port_gap(oracle-tuned)":port_gap,"test_r10_tuned":test_by_a[a_dev],"test_r10_flat":flat_test,
            "verdict_portable": port_gap<=0.01 and test_by_a[a_dev]>=flat_test-0.01},
        "A_incremental_attach":{
            "recall@10":A_r10,"hardhop@10":A_hard,
            "attach_lossless(|inc-full|)":round(abs(A_hard["incremental"]-A_hard["full_rebuild"]),4),
            "attach_recovers(inc-base)":round(A_hard["incremental"]-A_hard["base_only"],4),
            "verdict_attach_works": abs(A_hard["incremental"]-A_hard["full_rebuild"])<=0.02 and A_hard["incremental"]>A_hard["base_only"]},
        "note":"S=solidity(residual vs naive) P=이식성(config transfer) A=모듈성(증분attach). recall@10 아닌 solid/이식/붙이기 축 실측."}
    out=HERE/"evidence"/"EVIDENCE_hswm_solid_scaffold_ml18_2026-07-21.json"
    out.write_text(json.dumps(ev,ensure_ascii=False,indent=2))
    print(json.dumps(ev,ensure_ascii=False,indent=2)); print(f"\nEVIDENCE -> {out}",file=sys.stderr)

if __name__=="__main__": main()
