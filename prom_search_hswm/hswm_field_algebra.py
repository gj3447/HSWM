#!/usr/bin/env python3
"""
HSWM field 대수 — B0 슬라이스 (DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md §3).

USER_PRIMARY (2026-07-22): "SOLID 한 여러개 HSWM 의 연결로 큰 HSWM 망을 구축하고
그 부분들이 나눠지고 합쳐지고 적용도 간단하게 쉽도록"

Field = 불변 값객체: Hypergraph(구조) + provenance(엣지→source digest들) +
ledger(적용된 event-id G-Set, S1 CvRDT 관례) + seam(가역 canonical binding arc들).

연산:
  merge(A, B)            — union + provenance/ledger/seam union. 가환·결합·멱등 (L1–L3).
  split(field, part_of)  — provenance 파티션. 다중소스 엣지는 같은 eid로 복제(재merge 시
                           CRDT dedup), 파트를 가로지르는 seam arc는 벗겨 반환 (가역).
  merge_all(parts, seam) — split 역방향. round-trip 비트동일 (L4).
  compose([...]) / readout — 적용 = 함수 하나 (R4). compose는 merge의 얇은 별칭
                           (B0은 eager; lazy overlay는 소비자 2+ 후 승격 게이트 뒤에서만).
  field_id(field)        — 구조+provenance+ledger+seam의 canonical sha256.
                           임베딩은 파생물이라 제외(문서화된 경계).

정직 경계: 이 모듈은 대수 법칙(L1–L4, 기계검증)만 소유한다. "merge가 검색에 이득"(F-B2)은
  여기서 주장하지 않는다 — Q-federated-hswm-merge-crossfield prereg + α-nDCG blind-proof
  뒤에서만. L5(no-harm)는 경험 법칙이라 B0 범위 밖.
동일 id·다른 payload = fail-closed (compile_world/S1 관례 그대로).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from hswm_hypergraph import Hypergraph, Hyperedge, Vertex


@dataclass(frozen=True)
class SeamArc:
    """가역 canonical identity binding — 두 정점이 '같은 것'이라는 증거 달린 주장.
    데이터일 뿐 정점을 파괴적으로 합치지 않는다 (Entity resolution never deletes)."""
    arc_id: str
    left_vid: str
    right_vid: str
    evidence: str          # 근거 문자열 (B1에서 selector로 강화)
    event_id: str          # CRDT dedup 키

    def canonical(self) -> dict:
        return {"arc_id": self.arc_id, "left_vid": self.left_vid,
                "right_vid": self.right_vid, "evidence": self.evidence,
                "event_id": self.event_id}


@dataclass
class Field:
    """불변 취급 값객체 (frozen dataclass가 아닌 건 Hypergraph 내부 dict 때문 —
    규율: 생성 후 변경 금지, 변경 = 새 Field)."""
    hg: Hypergraph
    provenance: dict[str, tuple[str, ...]]   # eid -> 정렬된 source digest들 (엣지마다 ≥1)
    ledger: frozenset[str]                   # 적용된 event-id G-Set
    seam: tuple[SeamArc, ...]                # arc_id 정렬

    def __post_init__(self):
        missing = sorted(set(self.hg.edges) - set(self.provenance))
        if missing:
            raise ValueError(f"provenance 없는 엣지 {missing} — 모든 엣지는 source에 바인딩")
        for arc in self.seam:
            for vid in (arc.left_vid, arc.right_vid):
                if vid not in self.hg.vertices:
                    raise ValueError(f"seam arc {arc.arc_id} → 미존재 정점 {vid}")
        self.hg.check_incidence()


# ---------- canonical 직렬화 / field_id ----------

def _canonical_dict(f: Field) -> dict:
    return {
        "schema": "hswm-field/v1",
        "vertices": [{"vid": v.vid, "name": v.name, "kind": v.kind}
                     for _, v in sorted(f.hg.vertices.items())],
        "edges": [{"eid": e.eid, "value": e.value, "members": list(e.members),
                   "clusters": list(e.clusters),
                   "provenance": list(f.provenance[e.eid])}
                  for _, e in sorted(f.hg.edges.items())],
        "ledger": sorted(f.ledger),
        "seam": [a.canonical() for a in sorted(f.seam, key=lambda a: a.arc_id)],
    }


def field_id(f: Field) -> str:
    blob = json.dumps(_canonical_dict(f), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# ---------- 내부: 방어적 재구성 (fields 간 객체 공유로 인한 오염 금지) ----------

def _rebuild(vertex_meta: dict[str, tuple[str, str]],
             edges: dict[str, Hyperedge]) -> Hypergraph:
    """(vid -> (name, kind)) + 엣지들로 새 Hypergraph. incidence는 엣지에서 재유도.
    엣지 members에 등장하는 정점은 meta에 반드시 있어야 함."""
    vertices: dict[str, Vertex] = {}
    new_edges: dict[str, Hyperedge] = {}
    for eid in sorted(edges):
        e = edges[eid]
        new_edges[eid] = Hyperedge(eid=e.eid, value=e.value,
                                   members=list(e.members),
                                   clusters=list(e.clusters))
    for e in new_edges.values():
        for vid in e.members:
            if vid not in vertices:
                name, kind = vertex_meta[vid]
                vertices[vid] = Vertex(vid=vid, name=name, kind=kind)
            vertices[vid].incident_edges.append(e.eid)
    for v in vertices.values():
        v.incident_edges.sort()
    return Hypergraph(vertices=vertices, edges=new_edges)


def _vertex_meta(*fields: Field) -> dict[str, tuple[str, str]]:
    """정점 메타 union. 같은 vid에 다른 name/kind = fail-closed."""
    meta: dict[str, tuple[str, str]] = {}
    for f in fields:
        for vid, v in f.hg.vertices.items():
            pair = (v.name, v.kind)
            if vid in meta and meta[vid] != pair:
                raise ValueError(f"정점 충돌 {vid}: {meta[vid]} vs {pair} — fail-closed")
            meta[vid] = pair
    return meta


# ---------- merge (L1 가환 · L2 결합 · L3 멱등) ----------

def merge(a: Field, b: Field, new_seam: tuple[SeamArc, ...] = ()) -> Field:
    """union + fail-closed 충돌검사. new_seam = 이번 merge에서 발견된 경계 identity arc들
    (B0은 호출자 제공; B1에서 자동 후보 생성으로 강화)."""
    meta = _vertex_meta(a, b)
    edges: dict[str, Hyperedge] = {}
    prov: dict[str, tuple[str, ...]] = {}
    for f in (a, b):
        for eid, e in f.hg.edges.items():
            payload = (e.value, tuple(e.members), tuple(e.clusters))
            if eid in edges:
                have = (edges[eid].value, tuple(edges[eid].members),
                        tuple(edges[eid].clusters))
                if have != payload:
                    raise ValueError(f"엣지 충돌 {eid}: 동일 id·다른 payload — fail-closed")
                prov[eid] = tuple(sorted(set(prov[eid]) | set(f.provenance[eid])))
            else:
                edges[eid] = e
                prov[eid] = f.provenance[eid]
    seam_by_id: dict[str, SeamArc] = {}
    for arc in (*a.seam, *b.seam, *new_seam):
        if arc.arc_id in seam_by_id:
            if seam_by_id[arc.arc_id] != arc:
                raise ValueError(f"seam 충돌 {arc.arc_id}: 동일 id·다른 payload — fail-closed")
        else:
            seam_by_id[arc.arc_id] = arc
    hg = _rebuild(meta, edges)
    # merge로 고립된 seam 정점이 생길 수 없음: arc 정점은 원 field 검증을 이미 통과,
    # union은 정점을 잃지 않음. 단 members 밖 정점(고립 정점)은 _rebuild가 떨군다 —
    # 고립 정점을 참조하는 arc가 있으면 여기서 fail-closed.
    seam = tuple(sorted(seam_by_id.values(), key=lambda x: x.arc_id))
    out = Field(hg=hg, provenance=prov,
                ledger=frozenset(a.ledger | b.ledger), seam=seam)
    return out


def merge_all(parts: list[Field], seam: tuple[SeamArc, ...] = ()) -> Field:
    if not parts:
        raise ValueError("빈 parts")
    acc = parts[0]
    for p in parts[1:]:
        acc = merge(acc, p)
    if seam:
        acc = merge(acc, acc, new_seam=seam)  # 멱등 union 위에 seam만 추가
    return acc


def compose(fields: list[Field]) -> Field:
    """적용 진입점 (R4). B0 = eager merge 별칭. lazy overlay 승격은 소비자 2+ 게이트 뒤."""
    return merge_all(fields)


# ---------- split (L4 왕복) ----------

def split(f: Field, part_of) -> tuple[dict[str, Field], tuple[SeamArc, ...]]:
    """provenance 파티션. part_of: source_digest -> part_label.
    엣지는 자기 source가 속한 모든 파트에 (같은 eid로) 들어감 — 재merge 시 CRDT dedup.
    파트를 가로지르는 seam arc는 벗겨서 별도 반환 (가역성 담지자).
    ledger는 전 파트 복제 (G-Set union이 재merge서 원상복구)."""
    meta = _vertex_meta(f)
    part_edges: dict[str, dict[str, Hyperedge]] = {}
    part_prov: dict[str, dict[str, tuple[str, ...]]] = {}
    for eid in sorted(f.hg.edges):
        e = f.hg.edges[eid]
        labels = sorted({part_of(s) for s in f.provenance[eid]})
        for lab in labels:
            in_part = tuple(sorted(s for s in f.provenance[eid] if part_of(s) == lab))
            part_edges.setdefault(lab, {})[eid] = e
            part_prov.setdefault(lab, {})[eid] = in_part
    parts: dict[str, Field] = {}
    crossing: list[SeamArc] = []
    for lab in sorted(part_edges):
        hg = _rebuild(meta, part_edges[lab])
        inner = tuple(a for a in f.seam
                      if a.left_vid in hg.vertices and a.right_vid in hg.vertices)
        parts[lab] = Field(hg=hg, provenance=part_prov[lab],
                           ledger=frozenset(f.ledger), seam=inner)
    kept = {a.arc_id for p in parts.values() for a in p.seam}
    crossing = tuple(a for a in sorted(f.seam, key=lambda x: x.arc_id)
                     if a.arc_id not in kept)
    return parts, crossing


# ---------- 왕복 재조립 ----------

def reassemble(parts: dict[str, Field], crossing_seam: tuple[SeamArc, ...]) -> Field:
    """split의 역: 파트 merge + 벗겨둔 seam 재적용. L4 = field_id 비트동일."""
    merged = merge_all([parts[k] for k in sorted(parts)])
    if crossing_seam:
        merged = merge(merged, merged, new_seam=crossing_seam)
    return merged
