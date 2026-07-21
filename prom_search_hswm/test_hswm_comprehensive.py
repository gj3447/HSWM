#!/usr/bin/env python3
"""
ML9 — HSWM 종합 연구: 재귀 10-level 트리 + 실제 수평 HSWM↔HSWM 엣지 + 깊이 sweep + 다중지표.

LakatoTree: LakatosTree_PromSearchHSWM_20260721 / node ML9-hswm-comprehensive
USER: "수평 HSWM↔HSWM 제대로 만들고, 재귀 10-level 도 해보고, 다방면 연구 후 결론."

구조:
  L2 = paragraph 청크(1425). 재귀 RAPTOR 트리(binary KMeans, ~10 level) — 내부노드=하위트리 centroid=HSWM.
  수평 엣지 = 실제 교차참조("第X章" 언급) chapter→chapter (centroid cosine 아닌 진짜 관계).

다방면 (facets):
  F1 깊이 sweep: 트리 frontier level L=1..10에서 라우팅 → coverage/recall vs 깊이 (10-level 이득?).
  F2 방법 A/B: flat / two_level(章) / raptor_deep / raptor+xref(수평엣지) — weighted vs blind.
  F3 다중지표: coverage@k, recall@k, precision@k, diverse_recall(=2·rec·cov/(rec+cov), breadth+depth 결합).
       ← 적대검증 대비: coverage 단독은 blind가 trivially 이기므로 결합지표로 가중의 값 노출.
결론은 evidence.conclusion 에 자동 요약.
"""
import json, sys, re, statistics
from pathlib import Path
import numpy as np

BOOK = Path("/Volumes/GM/oss-clones/ai-agent-book/book")
HERE = Path(__file__).parent
SEED = 333
CONCEPTS = [("harness", "harness 하네스 에이전트 스캐폴딩"), ("RAG", "검색 증강 생성 RAG"),
            ("多 Agent", "다중 에이전트 협업 오케스트레이션"), ("KV Cache", "KV 캐시 프롬프트 캐싱"),
            ("Coding Agent", "코딩 에이전트 코드 생성"), ("评估", "에이전트 평가 통계"),
            ("上下文", "상하문 맥락 압축"), ("记忆", "사용자 기억 메모리 지식베이스"),
            ("工具", "도구 tool 함수 호출 MCP"), ("强化学习", "강화학습 RL 보상 후속훈련")]
KS = [20, 40]

def chunk_book():
    chunks, chap, chapnum = [], [], []
    for f in sorted(BOOK.glob("chapter*.md"), key=lambda p: int(re.search(r"\d+", p.stem).group())):
        n = int(re.search(r"\d+", f.stem).group())
        for para in re.split(r"\n\s*\n", f.read_text(encoding="utf-8")):
            t = " ".join(para.split())
            if len(t) >= 90 and not t.startswith("#") and not t.startswith("!["):
                chunks.append(t); chap.append(f.stem); chapnum.append(n)
    return chunks, chap, chapnum

def parse_xref():
    """실제 교차참조: chapterN 파일이 '第M章' 언급 → edge N->M."""
    edges = {}
    zh = "零一二三四五六七八九十"
    def zh2int(s):
        if s == "十": return 10
        if s.startswith("十"): return 10 + zh.index(s[1])
        if s.endswith("十"): return zh.index(s[0]) * 10
        return zh.index(s) if s in zh else None
    for f in sorted(BOOK.glob("chapter*.md")):
        n = int(re.search(r"\d+", f.stem).group())
        txt = f.read_text(encoding="utf-8")
        refs = set()
        for m in re.findall(r"第([一二三四五六七八九十]+)章", txt):
            v = zh2int(m)
            if v and v != n and 1 <= v <= 10:
                refs.add(v)
        edges[n] = sorted(refs)
    return edges

def build_tree(E, indices, level, max_level, min_size, nid, store):
    node = {"id": nid[0], "level": level, "leaves": list(indices),
            "centroid": E[indices].mean(0), "children": []}
    store.append(node); nid[0] += 1
    if len(indices) <= min_size or level >= max_level:
        return node
    from sklearn.cluster import KMeans
    lab = KMeans(n_clusters=2, random_state=SEED, n_init=5).fit_predict(E[indices])
    for c in (0, 1):
        sub = [indices[i] for i in range(len(indices)) if lab[i] == c]
        if sub:
            ch = build_tree(E, sub, level + 1, max_level, min_size, nid, store)
            node["children"].append(ch)
    return node

def frontier(root, L):
    """트리를 깊이 L에서 컷 — level==L 노드 또는 그보다 얕은 leaf."""
    out = []
    stack = [root]
    while stack:
        nd = stack.pop()
        if nd["level"] >= L or not nd["children"]:
            out.append(nd)
        else:
            stack.extend(nd["children"])
    return out

def route(E, qv, nodes, k, mode):
    """frontier 노드들에 예산 배분 → 각 노드 subtree서 top leaf."""
    sc = {i: float(nodes[i]["centroid"] @ qv) for i in range(len(nodes))}
    if mode == "blind":
        budget = {i: max(1, k // len(nodes)) for i in range(len(nodes))}
    else:
        pos = {i: max(0.0, sc[i]) for i in range(len(nodes))}
        tot = sum(pos.values()) or 1e-9
        budget = {i: int(round(k * pos[i] / tot)) for i in range(len(nodes))}
    picked = []
    for i, nd in enumerate(nodes):
        b = budget.get(i, 0)
        if b <= 0: continue
        lv = nd["leaves"]
        s = E[lv] @ qv
        for j in list(np.argsort(-s)[:b]):
            picked.append(lv[j])
    return sorted(set(picked), key=lambda x: -float(E[x] @ qv))[:k]

def flat(E, qv, k):
    return list(np.argsort(-(E @ qv))[:k])

def metrics(got, gold, gold_chaps, chap, k):
    gs = set(gold)
    hit = [i for i in got if i in gs]
    recall = len(hit) / len(gold) if gold else 0.0
    precision = len(hit) / k
    cov = len(set(chap[i] for i in hit)) / len(gold_chaps) if gold_chaps else 0.0
    div = (2 * recall * cov / (recall + cov)) if (recall + cov) > 0 else 0.0
    return recall, precision, cov, div

def main():
    chunks, chap, chapnum = chunk_book()
    xref = parse_xref()
    from sentence_transformers import SentenceTransformer
    import torch
    torch.manual_seed(SEED)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    E = model.encode(chunks, normalize_embeddings=True, convert_to_numpy=True, batch_size=64)
    Q = model.encode([q for _, q in CONCEPTS], normalize_embeddings=True, convert_to_numpy=True)

    store = []
    root = build_tree(E, list(range(len(chunks))), 0, 10, 4, [0], store)
    max_depth = max(n["level"] for n in store)
    idx_by_chap = {c: [i for i, x in enumerate(chap) if x == c] for c in sorted(set(chap))}

    golds = []
    for anchor, _ in CONCEPTS:
        g = [i for i, t in enumerate(chunks) if anchor.lower() in t.lower()]
        golds.append((g, set(chap[i] for i in g)))

    # F1 깊이 sweep (weighted routing, k=40)
    depth_sweep = {}
    for L in range(1, 11):
        fr = frontier(root, L)
        cov, rec = [], []
        for qi, (g, gc) in enumerate(golds):
            got = route(E, Q[qi], fr, 40, "weighted")
            r, p, c, d = metrics(got, g, gc, chap, 40)
            cov.append(c); rec.append(r)
        depth_sweep[L] = {"n_frontier": len(fr), "coverage@40": round(statistics.mean(cov), 4),
                          "recall@40": round(statistics.mean(rec), 4)}

    # F2 방법 A/B + F3 다중지표
    def two_level_nodes():
        return [{"leaves": idx_by_chap[c], "centroid": E[idx_by_chap[c]].mean(0)} for c in sorted(idx_by_chap)]
    tl = two_level_nodes()
    deep_fr = frontier(root, max_depth)  # 최심 frontier
    methods = {}
    for name, fn in [
        ("flat", lambda qv, k: flat(E, qv, k)),
        ("two_level_weighted", lambda qv, k: route(E, qv, tl, k, "weighted")),
        ("two_level_blind", lambda qv, k: route(E, qv, tl, k, "blind")),
        ("raptor_deep_weighted", lambda qv, k: route(E, qv, deep_fr, k, "weighted")),
        ("raptor_deep_blind", lambda qv, k: route(E, qv, deep_fr, k, "blind")),
    ]:
        methods[name] = fn

    # xref-augmented: two_level_weighted + 참조 章 top chunk 주입
    def xref_aug(qv, k):
        base = route(E, qv, tl, max(4, k - 6), "weighted")
        top_chap = max(sorted(idx_by_chap), key=lambda c: float(E[idx_by_chap[c]].mean(0) @ qv))
        tn = int(re.search(r"\d+", top_chap).group())
        extra = []
        for rc in xref.get(tn, []):
            ci = idx_by_chap.get(f"chapter{rc}", [])
            if ci:
                s = E[ci] @ qv
                extra.extend([ci[j] for j in list(np.argsort(-s)[:2])])
        return sorted(set(base + extra), key=lambda x: -float(E[x] @ qv))[:k]
    methods["two_level_weighted_xref"] = xref_aug

    results = {m: {k: {"recall": [], "precision": [], "coverage": [], "diverse": []} for k in KS} for m in methods}
    for qi, (g, gc) in enumerate(golds):
        for m, fn in methods.items():
            for k in KS:
                got = fn(Q[qi], k)
                r, p, c, d = metrics(got, g, gc, chap, k)
                R = results[m][k]
                R["recall"].append(r); R["precision"].append(p); R["coverage"].append(c); R["diverse"].append(d)
    summary = {m: {k: {mm: round(statistics.mean(v), 4) for mm, v in results[m][k].items()} for k in KS} for m in methods}

    # 결론 자동 요약
    f_cov = summary["flat"][20]["coverage"]; f_div = summary["flat"][20]["diverse"]
    conclusion = {
        "depth_helps": depth_sweep[max(2, max_depth)]["coverage@40"] > depth_sweep[1]["coverage@40"],
        "depth_optimum_L": max(range(1, 11), key=lambda L: depth_sweep[L]["coverage@40"]),
        "raptor_deep_cov_gt_two_level@20": summary["raptor_deep_weighted"][20]["coverage"] > summary["two_level_weighted"][20]["coverage"],
        "raptor_deep_diverse_gt_flat@20": summary["raptor_deep_weighted"][20]["diverse"] > f_div,
        "xref_diverse_gt_two_level@20": summary["two_level_weighted_xref"][20]["diverse"] > summary["two_level_weighted"][20]["diverse"],
        "weighted_diverse_gt_blind@20_twolevel": summary["two_level_weighted"][20]["diverse"] > summary["two_level_blind"][20]["diverse"],
        "best_method_by_diverse@40": max(methods, key=lambda m: summary[m][40]["diverse"]),
    }
    ev = {
        "experiment": "hswm_comprehensive_ml9",
        "tree": "LakatosTree_PromSearchHSWM_20260721", "node": "ML9-hswm-comprehensive",
        "structure": {"chunks": len(chunks), "tree_nodes": len(store), "tree_max_depth": max_depth,
                      "xref_edges": {str(k): v for k, v in xref.items() if v}, "concepts": len(CONCEPTS)},
        "F1_depth_sweep": depth_sweep,
        "F2F3_methods": summary,
        "conclusion": conclusion,
        "caveats": "gold=anchor-string(crude). coverage 단독은 blind가 trivially 유리→diverse_recall(rec+cov 결합)이 정직지표. 수평엣지=실제 第X章 참조.",
    }
    out = HERE / "evidence" / "EVIDENCE_hswm_comprehensive_ml9_2026-07-21.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    print(f"\nEVIDENCE -> {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
