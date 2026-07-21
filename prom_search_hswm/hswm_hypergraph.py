#!/usr/bin/env python3
"""
HSWM 하이퍼그래프 빌더 — 문서 → (정점 V ∪ 하이퍼엣지 E) 그래프.  [P0 blocker 해소]

배경 (KQV 등뼈, ../PROM_KQV_ATTENTION_BACKBONE_2026-07-19.md §4):
  T5 "하이퍼엣지 1급 채점(V∪E readout)"의 ⛔P0 blocker = "문서→하이퍼그래프 빌더가 없다 —
  HSWM 실증 기반은 curated KG뿐". 이 모듈이 그 빌더다. curated KG 없이 raw findings에서
  하이퍼그래프를 자동 구성해 V∪E readout(hswm_hypergraph_readout.py)이 읽을 구조를 만든다.

구성 (HyperGraphRAG식, arXiv:2503.21322 충실):
  - 정점 V = entity(인용 학자/고유명, lexicon match) ∪ topic 라벨(cluster_axes).
  - 하이퍼엣지 E = 각 finding. finding이 언급한 entity+topic 정점들을 k-항으로 묶음.
    edge.value = finding 원문(readout이 실제로 읽어낼 payload = "V"의 값 채널).
  - V·E 양쪽에 임베딩(정점=name/label, 엣지=finding text). 주입식(embed 콜백)이라
    구조 검증은 torch 없이, 실측은 sentence-transformers로.

정직 경계: 이 모듈은 *구조를 짓기만* 한다. "V∪E가 node-only보다 낫다"는 주장은
  LakatoTree T5 예측 사전등록 + held-out gold + MC-null + equal-compute 게이트(실험 B) 뒤에서만.
  LakatoTree: LakatosTree_PromSearchHSWM_20260721 (P0 = 이 빌더가 닫음).
"""
from __future__ import annotations

import itertools
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).parent

# 인용 학자/고유명 lexicon — prom_fieldoffields.py와 동일 출처(badiou RF 텍스트 등장 고유명).
# entity 추출기의 기본값. 다른 코퍼스는 lexicon/extractor 주입으로 교체.
DEFAULT_LEXICON = [
    "hallward", "bosteels", "bartlett", "clemens", "pluth", "feltham", "baki",
    "livingston", "norris", "bolz", "laruelle", "meillassoux", "brassier",
    "wolfendale", "zizek", "ranciere", "bensaid", "critchley", "toscano",
    "adorno", "lacan", "chiesa", "fink", "boucher", "watkin", "plotnitsky",
    "veilahti", "rorty", "nietzsche", "wittgenstein", "beckett", "mallarme",
    "celan", "levinas", "miller", "cohen", "mirimanoff", "grothendieck",
    "church", "kierkegaard", "paul", "antigone",
]


@dataclass
class Vertex:
    """정점 = entity 또는 topic 라벨. V∪E readout의 1급 채점단위(entity 측)."""
    vid: str                    # 정규화 키 (kind:name)
    name: str                   # 원 라벨 (예: "hallward", "event")
    kind: str                   # "entity" | "topic"
    incident_edges: list[str] = field(default_factory=list)  # 이 정점을 묶는 하이퍼엣지 eid들
    embedding: object = None    # embed 후 채워짐 (없으면 None)

    @property
    def embed_text(self) -> str:
        # topic은 라벨만으론 신호가 얇아 kind 접두로 문맥 최소 부여.
        return self.name if self.kind == "entity" else f"topic: {self.name}"


@dataclass
class Hyperedge:
    """하이퍼엣지 = finding. k-항 관계 + 값 payload. V∪E readout의 1급 채점단위(관계 측)."""
    eid: str                    # finding id (rf)
    value: str                  # finding 원문 = 읽어낼 실제 내용("V"의 값)
    members: list[str] = field(default_factory=list)  # 묶인 정점 vid들 (정렬)
    clusters: list[str] = field(default_factory=list)  # gold 라벨(eval 전용, 구성엔 미사용)
    embedding: object = None

    @property
    def arity(self) -> int:
        return len(self.members)

    @property
    def embed_text(self) -> str:
        return self.value


@dataclass
class Hypergraph:
    vertices: dict[str, Vertex]
    edges: dict[str, Hyperedge]

    # --- 구조 조회 ---
    def units(self) -> list[tuple[str, str]]:
        """V∪E 후보 리스트: [("V", vid)...] + [("E", eid)...]. 결정론 정렬."""
        return ([("V", v) for v in sorted(self.vertices)]
                + [("E", e) for e in sorted(self.edges)])

    def dangling_edges(self) -> list[str]:
        """정점 0개인 하이퍼엣지(어떤 entity/topic과도 안 묶인 fact). 여전히 1급 E."""
        return sorted(eid for eid, e in self.edges.items() if e.arity == 0)

    def check_incidence(self) -> None:
        """양방향 incidence 불변식 강제 — 위반 시 AssertionError(테스트/fsck용)."""
        for eid, e in self.edges.items():
            for vid in e.members:
                assert vid in self.vertices, f"edge {eid} → 미존재 정점 {vid}"
                assert eid in self.vertices[vid].incident_edges, \
                    f"incidence 비대칭: {eid}∋{vid} 인데 {vid}.incident에 {eid} 없음"
        for vid, v in self.vertices.items():
            for eid in v.incident_edges:
                assert eid in self.edges, f"정점 {vid} → 미존재 엣지 {eid}"
                assert vid in self.edges[eid].members, \
                    f"incidence 비대칭: {vid}∈{eid}.incident 인데 {eid}.members에 {vid} 없음"


def default_extractor(text: str, lexicon=DEFAULT_LEXICON) -> set[str]:
    """entity 추출 기본값: lexicon 고유명 word-boundary 매치(부분문자열 오탐 회피)."""
    t = text.lower()
    found = set()
    for e in lexicon:
        if re.search(rf"\b{re.escape(e)}\b", t):
            found.add(e)
    return found


def build_hypergraph(findings, *, extractor=default_extractor, embed=None,
                     topic_vertices=True) -> Hypergraph:
    """
    findings: [{"rf": str, "text": str, "clusters": [str], ...}] (gold_badiou24.json findings 형).
    extractor: text -> set[entity_name]. 기본 = lexicon 매치.
    embed: list[str] -> list[vec] (정규화 임베딩). None이면 embedding=None(구조만).
    topic_vertices: gold cluster의 topic축을 정점화할지. **평가에서 gold==topic이면 반드시 False**
      (안 그러면 topic 정점 확장이 gold를 그대로 읽는 leakage). 기본 True(일반 빌드는 topic 유효 구조).

    반환 Hypergraph. 결정론(입력순 + 정렬).
    """
    vertices: dict[str, Vertex] = {}
    edges: dict[str, Hyperedge] = {}

    def ensure_vertex(name: str, kind: str) -> str:
        vid = f"{kind}:{name}"
        if vid not in vertices:
            vertices[vid] = Vertex(vid=vid, name=name, kind=kind)
        return vid

    for f in findings:
        eid = f["rf"]
        if eid in edges:
            raise ValueError(f"중복 finding id {eid} — id는 유일해야 함")
        member_vids: set[str] = set()
        # entity 정점
        for ent in extractor(f["text"]):
            member_vids.add(ensure_vertex(ent, "entity"))
        # topic 정점 = gold cluster 중 topic축(role축 primary/secondary/critique 제외).
        #   role은 finding의 *속성*이지 재사용 정점이 아님 → 하이퍼엣지가 묶는 건 topic 개체.
        if topic_vertices:
            for cl in f.get("clusters", []):
                if cl not in ("primary", "secondary", "critique"):
                    member_vids.add(ensure_vertex(cl, "topic"))
        edge = Hyperedge(
            eid=eid,
            value=f["text"],
            members=sorted(member_vids),
            clusters=list(f.get("clusters", [])),
        )
        edges[eid] = edge
        for vid in edge.members:
            vertices[vid].incident_edges.append(eid)

    # incident_edges 결정론 정렬
    for v in vertices.values():
        v.incident_edges.sort()

    hg = Hypergraph(vertices=vertices, edges=edges)

    if embed is not None:
        v_order = sorted(hg.vertices)
        e_order = sorted(hg.edges)
        texts = [hg.vertices[v].embed_text for v in v_order] + \
                [hg.edges[e].embed_text for e in e_order]
        vecs = embed(texts)
        for i, v in enumerate(v_order):
            hg.vertices[v].embedding = vecs[i]
        for j, e in enumerate(e_order):
            hg.edges[e].embedding = vecs[len(v_order) + j]

    hg.check_incidence()
    return hg


def load_badiou_findings() -> list[dict]:
    return json.loads((HERE / "data" / "gold_badiou24.json").read_text())["findings"]


# --- self-test (구조 sanity, 실험 아님. embedding 없이 torch-free) ---
if __name__ == "__main__":
    findings = load_badiou_findings()
    hg = build_hypergraph(findings)
    print(f"findings={len(findings)}  V={len(hg.vertices)}  E={len(hg.edges)}  "
          f"V∪E={len(hg.units())}")
    kinds = {}
    for v in hg.vertices.values():
        kinds[v.kind] = kinds.get(v.kind, 0) + 1
    print(f"  정점 종류: {kinds}")
    arity = [e.arity for e in hg.edges.values()]
    print(f"  하이퍼엣지 arity: min={min(arity)} max={max(arity)} "
          f"mean={sum(arity)/len(arity):.2f}  dangling={hg.dangling_edges()}")
    # 최고 차수 정점 = 4-fold readout hub 후보(KQV T2)
    hubs = sorted(hg.vertices.values(), key=lambda v: -len(v.incident_edges))[:5]
    print("  hub 정점(최다 incidence):")
    for v in hubs:
        print(f"    {v.vid:20s} deg={len(v.incident_edges)}  edges={v.incident_edges}")
    hg.check_incidence()
    print("  incidence 불변식: OK")
