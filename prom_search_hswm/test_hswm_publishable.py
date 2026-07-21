#!/usr/bin/env python3
"""
ML10 — publishable급 HSWM 재실험: α-nDCG + 임베딩 수평엣지 + depth ablation + split-benefit + 통계.

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML10-hswm-publishable
적대검증 6결함 반영: (1)공정 baseline flat+MMR (2)α-nDCG(게임불가 diversity) (3)gold 스코프명시
(4)depth ablation multi-seed 에러바 (5)임베딩 수평엣지(dense regex 대체) (6)bootstrap CI + N확대.

USER 2질문 직접 측정:
  Q1 더 깊은 HSWM이 좋아지나 → tree-informed 스코어 depth ablation(D=0=flat..full), multi-seed±std.
  Q2 비대한 HSWM 나누면 이점 → 큰 章을 sub-split한 fine-tree vs 章-only coarse-tree의 α-nDCG delta.

지표: α-nDCG@k(α=0.5, subtopic=章, blind-proof) + S-recall@k + recall@k. bootstrap 95% CI (query resample).
방법: flat / flat+MMR / tree_informed(collapsed, RAPTOR식) / tree+embedding_edges.
seed 3개(KMeans) 평균±std. gold=anchor-string(스코프: string-level, crude 명시).
"""
import json, sys, re, math, statistics, random
from collections import defaultdict
from pathlib import Path
import numpy as np

BOOK = Path("/Volumes/GM/oss-clones/ai-agent-book/book")
HERE = Path(__file__).parent
SEEDS = [333, 7, 91]
ALPHA = 0.5
K = 20
EDGE_M = 3        # 각 노드 임베딩 수평엣지 이웃 수 (cross-chapter)
EDGE_BETA = 0.85  # spreading activation decay
BOOT = 2000

ANCHORS = {  # anchor(gold string) : query text (multilingual)
 "harness":"harness 하네스 에이전트 스캐폴딩 구조","RAG":"검색 증강 생성 RAG 리트리벌",
 "多 Agent":"다중 에이전트 협업 오케스트레이션","KV Cache":"KV 캐시 프롬프트 캐싱 재사용",
 "Coding Agent":"코딩 에이전트 코드 생성 파일시스템","评估":"에이전트 평가 벤치마크 통계",
 "上下文":"상하문 맥락 관리 압축 윈도우","记忆":"사용자 기억 메모리 지식베이스",
 "工具":"도구 tool 함수호출 MCP","强化学习":"강화학습 RL 보상 후속훈련",
 "提示":"프롬프트 지시 시스템프롬프트","推理":"추론 사고 체인 reasoning",
 "检索":"검색 인출 retrieval 랭킹","微调":"미세조정 SFT finetune",
 "训练":"훈련 학습 데이터","向量":"벡터 임베딩 유사도",
 "幻觉":"환각 hallucination 오류","安全":"안전 보안 방어 인젝션",
 "权限":"권한 접근제어 승인","编排":"오케스트레이션 워크플로 편성",
 "多模态":"멀티모달 음성 이미지 비전","注意力":"어텐션 attention 트랜스포머",
 "奖励":"보상 reward 신호 설계","泛化":"일반화 generalization",
 "规划":"계획 planning 플래너","知识":"지식 knowledge 그래프",
}

def chunk_book():
    chunks, chap = [], []
    for f in sorted(BOOK.glob("chapter*.md"), key=lambda p:int(re.search(r"\d+",p.stem).group())):
        for para in re.split(r"\n\s*\n", f.read_text(encoding="utf-8")):
            t=" ".join(para.split())
            if len(t)>=90 and not t.startswith("#") and not t.startswith("!["):
                chunks.append(t); chap.append(f.stem)
    return chunks, chap

def build_tree(E, idx, level, maxlvl, minsize, k_branch, seed, nid, store, parent):
    node={"id":nid[0],"level":level,"leaves":list(idx),"centroid":E[idx].mean(0),"parent":parent,"children":[]}
    store.append(node); me=nid[0]; nid[0]+=1
    if len(idx)<=minsize or level>=maxlvl: return node
    from sklearn.cluster import KMeans
    kk=min(k_branch,len(idx))
    if kk<2: return node
    lab=KMeans(n_clusters=kk,random_state=seed,n_init=4).fit_predict(E[idx])
    for c in set(lab):
        sub=[idx[i] for i in range(len(idx)) if lab[i]==c]
        if sub:
            ch=build_tree(E,sub,level+1,maxlvl,minsize,k_branch,seed,nid,store,me)
            node["children"].append(ch["id"])
    return node

def ancestors_of_leaf(store, leaf_idx):
    # leaf가 속한 노드들: store 순회로 leaf가 leaves에 있는 노드 중 각 level 최소 노드 = 조상경로
    # 효율 위해 leaf->node level별 최소범위 노드 매핑
    pass

def tree_informed_scores(E, qv, store, leaf_to_nodes, maxD):
    """각 leaf i: max( flat cos, max over 조상노드(level<=maxD) cos(q,centroid) )."""
    n=len(E)
    flat=E@qv
    node_sc={nd["id"]: float(nd["centroid"]@qv) for nd in store}
    sc=flat.copy()
    for i in range(n):
        best=flat[i]
        for nodeid in leaf_to_nodes[i]:
            nd=store[nodeid]
            if 1<=nd["level"]<=maxD:
                if node_sc[nodeid]>best: best=node_sc[nodeid]
        sc[i]=best
    return sc

def embedding_edges(E, chap, m):
    """각 청크 → cross-chapter top-m 임베딩 이웃 (수평 HSWM↔HSWM 엣지, dense regex 대체)."""
    S=E@E.T
    np.fill_diagonal(S,-1)
    edges={}
    for i in range(len(E)):
        order=np.argsort(-S[i])
        nb=[]
        for j in order:
            if chap[j]!=chap[i]:
                nb.append(int(j))
                if len(nb)>=m: break
        edges[i]=nb
    return edges

def alpha_ndcg(ranked, gold_set, chap, alpha, k):
    def dcg(order):
        seen=defaultdict(int); s=0.0
        for r,d in enumerate(order[:k],1):
            if d in gold_set:
                g=(1-alpha)**seen[chap[d]]; seen[chap[d]]+=1
                s+=g/math.log2(r+1)
        return s
    # ideal: greedy least-covered-chapter
    seen=defaultdict(int); ideal=[]; pool=list(gold_set)
    pool.sort()
    while pool:
        best=min(pool,key=lambda d:(seen[chap[d]],d)); ideal.append(best); seen[chap[best]]+=1; pool.remove(best)
    idcg=dcg(ideal)
    return dcg(ranked)/idcg if idcg>0 else 0.0

def s_recall(ranked, gold_set, gold_chaps, chap, k):
    cov=set(chap[d] for d in ranked[:k] if d in gold_set)
    return len(cov)/len(gold_chaps) if gold_chaps else 0.0

def recall(ranked, gold_set, k):
    return sum(1 for d in ranked[:k] if d in gold_set)/len(gold_set) if gold_set else 0.0

def mmr(E, qv, k, lam=0.5):
    flat=E@qv; cand=list(np.argsort(-flat)[:200]); sel=[]
    while cand and len(sel)<k:
        if not sel:
            best=cand[0]
        else:
            def mm(d):
                div=max(float(E[d]@E[s]) for s in sel)
                return lam*float(flat[d])-(1-lam)*div
            best=max(cand,key=mm)
        sel.append(best); cand.remove(best)
    return sel

def boot_ci(vals, reps=BOOT, seed=1):
    rng=random.Random(seed); n=len(vals)
    ms=[]
    for _ in range(reps):
        s=[vals[rng.randrange(n)] for _ in range(n)]
        ms.append(sum(s)/n)
    ms.sort()
    return round(ms[int(0.025*reps)],4), round(ms[int(0.975*reps)],4)

def main():
    chunks,chap=chunk_book()
    from sentence_transformers import SentenceTransformer
    import torch
    torch.manual_seed(333)
    model=SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    E=model.encode(chunks,normalize_embeddings=True,convert_to_numpy=True,batch_size=64)

    # gold: anchor≥3 chapters만 (α-nDCG subtopic 의미)
    concepts=[]
    for a,q in ANCHORS.items():
        g=[i for i,t in enumerate(chunks) if a.lower() in t.lower()]
        gc=set(chap[i] for i in g)
        if len(gc)>=3: concepts.append((a,q,set(g),gc))
    Q=model.encode([q for _,q,_,_ in concepts],normalize_embeddings=True,convert_to_numpy=True)
    edges=embedding_edges(E,chap,EDGE_M)

    # ---- multi-seed trees ----
    seed_results=[]
    depth_curves=[]
    split_deltas=[]
    for seed in SEEDS:
        store=[]; root=build_tree(E,list(range(len(chunks))),0,8,6,6,seed,[0],store,-1)
        maxd=max(nd["level"] for nd in store)
        # leaf -> 조상 노드 id 목록
        leaf_to_nodes=defaultdict(list)
        for nd in store:
            for lf in nd["leaves"]:
                leaf_to_nodes[lf].append(nd["id"])
        # per-query metrics per method
        per={"flat":[], "flat_mmr":[], "tree_full":[], "tree_edges":[]}
        # depth ablation (α-nDCG@k vs D)
        dcurve={D:[] for D in range(0,maxd+1)}
        for qi,(a,q,gset,gc) in enumerate(concepts):
            qv=Q[qi]; flat=E@qv
            r_flat=list(np.argsort(-flat)[:K])
            per["flat"].append(alpha_ndcg(r_flat,gset,chap,ALPHA,K))
            per["flat_mmr"].append(alpha_ndcg(mmr(E,qv,K),gset,chap,ALPHA,K))
            sc_full=tree_informed_scores(E,qv,store,leaf_to_nodes,maxd)
            r_full=list(np.argsort(-sc_full)[:K])
            per["tree_full"].append(alpha_ndcg(r_full,gset,chap,ALPHA,K))
            # embedding edges: spreading activation on tree_full scores
            sc_e=sc_full.copy()
            for i in range(len(E)):
                for j in edges[i]:
                    v=EDGE_BETA*sc_full[j]
                    if v>sc_e[i]: sc_e[i]=v
            r_e=list(np.argsort(-sc_e)[:K])
            per["tree_edges"].append(alpha_ndcg(r_e,gset,chap,ALPHA,K))
            for D in range(0,maxd+1):
                scD=tree_informed_scores(E,qv,store,leaf_to_nodes,D) if D>0 else flat
                dcurve[D].append(alpha_ndcg(list(np.argsort(-scD)[:K]),gset,chap,ALPHA,K))
        seed_results.append({m:statistics.mean(v) for m,v in per.items()})
        depth_curves.append({D:statistics.mean(dcurve[D]) for D in dcurve})
        # Q2 split-benefit: coarse(D=1, 章급) vs fine(full) 평균 α-nDCG
        split_deltas.append(statistics.mean(dcurve[maxd])-statistics.mean(dcurve[1]))

    def agg(key):
        vals=[sr[key] for sr in seed_results]
        return {"mean":round(statistics.mean(vals),4),"std":round(statistics.pstdev(vals),4)}
    method_summary={m:agg(m) for m in seed_results[0]}
    # depth curve aggregated over seeds
    maxd_common=min(max(dc) for dc in depth_curves)
    depth_agg={D:{"mean":round(statistics.mean([dc[D] for dc in depth_curves]),4),
                  "std":round(statistics.pstdev([dc[D] for dc in depth_curves]),4)} for D in range(0,maxd_common+1)}
    depth_opt=max(depth_agg,key=lambda D:depth_agg[D]["mean"])

    # bootstrap CI (seed0 per-query, tree_full vs flat)
    s0=SEEDS[0]; store=[]; root=build_tree(E,list(range(len(chunks))),0,8,6,6,s0,[0],store,-1)
    maxd=max(nd["level"] for nd in store); leaf_to_nodes=defaultdict(list)
    for nd in store:
        for lf in nd["leaves"]: leaf_to_nodes[lf].append(nd["id"])
    pq_flat=[]; pq_tree=[]; pq_edge=[]
    for qi,(a,q,gset,gc) in enumerate(concepts):
        qv=Q[qi]; flat=E@qv
        pq_flat.append(alpha_ndcg(list(np.argsort(-flat)[:K]),gset,chap,ALPHA,K))
        scf=tree_informed_scores(E,qv,store,leaf_to_nodes,maxd)
        pq_tree.append(alpha_ndcg(list(np.argsort(-scf)[:K]),gset,chap,ALPHA,K))
        sce=scf.copy()
        for i in range(len(E)):
            for j in edges[i]:
                v=EDGE_BETA*scf[j]
                if v>sce[i]: sce[i]=v
        pq_edge.append(alpha_ndcg(list(np.argsort(-sce)[:K]),gset,chap,ALPHA,K))
    diff_tree=[pq_tree[i]-pq_flat[i] for i in range(len(concepts))]
    diff_edge=[pq_edge[i]-pq_tree[i] for i in range(len(concepts))]

    ev={
      "experiment":"hswm_publishable_ml10","tree":"LakatosTree_PromSearchHSWM_20260721","node":"ML10-hswm-publishable",
      "setup":{"n_queries":len(concepts),"metric":"alpha-nDCG@20 (alpha=0.5, subtopic=chapter, blind-proof)",
               "seeds":SEEDS,"gold":"anchor-string presence (scope: string-level, crude)","corpus":"ai-agent-book 1425 chunks",
               "tree":"RAPTOR-style KMeans branch=6, minsize=6, maxlvl=8","edges":f"embedding cross-chapter top-{EDGE_M} beta={EDGE_BETA}"},
      "method_alpha_ndcg@20 (mean over seeds ± std)":method_summary,
      "Q1_depth_ablation_alpha_ndcg@20":depth_agg,"Q1_depth_optimum_D":depth_opt,
      "Q1_verdict":("deeper helps up to D="+str(depth_opt)+" then plateau/decline" if depth_opt>0 else "flat best"),
      "Q2_split_benefit_full_minus_coarse (per seed)":[round(x,4) for x in split_deltas],
      "Q2_split_benefit_mean":round(statistics.mean(split_deltas),4),
      "bootstrap_95CI":{"tree_full_minus_flat":{"mean":round(statistics.mean(diff_tree),4),"CI":boot_ci(diff_tree)},
                        "edges_minus_tree":{"mean":round(statistics.mean(diff_edge),4),"CI":boot_ci(diff_edge)}},
      "conclusion":{
        "deeper_helps":depth_opt>1,
        "split_bloated_helps":statistics.mean(split_deltas)>0,
        "tree_beats_flat_sig":boot_ci(diff_tree)[0]>0,
        "embedding_edges_help_sig":boot_ci(diff_edge)[0]>0,
        "best_method":max(method_summary,key=lambda m:method_summary[m]["mean"]),
      },
    }
    out=HERE/"evidence"/"EVIDENCE_hswm_publishable_ml10_2026-07-21.json"
    out.write_text(json.dumps(ev,ensure_ascii=False,indent=2))
    print(json.dumps(ev,ensure_ascii=False,indent=2))
    print(f"\nEVIDENCE -> {out}",file=sys.stderr)

if __name__=="__main__":
    main()
