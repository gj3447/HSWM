"""ML-material identity weave — ReFinED QID + fastcoref 전파 (R2, PROM-8 C3).

결정론 weave(claim_weave.py: exact 표면/타이틀)가 T1에서 죽은 뒤(R1 kill#2),
진짜 identity 재료로 같은 자리를 다시 짠다:

  M1 qid_direct   claim 역할 span이 ReFinED span(QID 확정)과 containment로
                  겹치면 그 역할은 QID로 해소된다.  서로 다른 문단에서
                  비-주어 역할(QID q) → 주어(QID q) 인 claim 쌍마다 arc.
  M2 qid_coref    fastcoref 클러스터 안에서 QID가 정확히 하나로 확정되면
                  (겹침 QID 충돌 시 그 클러스터는 폐기·카운트) 클러스터의
                  모든 멘션이 그 QID를 상속 — 대명사/별칭 역할 span까지
                  M1이 닿게 하는 전파층.

계약 (claim_weave.py와 동일):
  - 모든 arc는 양끝 exact span + WeaveReceiptV1, origin=woven_* 라 strip 가역.
  - 텍스트 기반 동일성 강제: 재료 receipt의 source_text_sha256 == claim 역할의
    source_text_sha256 아니면 그 문단은 통째로 스킵·카운트 (다른 텍스트 위의
    span을 이어붙이는 날조 금지).
  - QID fan cap: 한 QID의 주어-claim이 max_fan 초과면 그 QID 전체 스킵·카운트
    (국가/거대 개체 arc 폭발 방지 — 커널 hub 게이트와 별개의 생성층 상한).
  - gold/question 무소비. build-time 산출물(r2_material/*.json)만 읽는다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from claim_builder import ClaimGraphBuildV1, NaryClaimV1
from claim_weave import WeaveReceiptV1, WeaveResultV1, _woven_arc
from typed_composition import TypedCompositionGraphV1

HERE = Path(__file__).parent
MATERIAL_DIR = HERE / ".ab_p5_cache" / "r2_material"

DEFAULT_MAX_FAN = 32


@dataclass(frozen=True)
class MlWeaveStats:
    paragraphs_sha_mismatch: int
    clusters_conflicted: int
    qids_fan_capped: int
    roles_resolved_direct: int
    roles_resolved_coref: int


def load_material(dataset: str) -> tuple[dict, dict]:
    link = json.loads((MATERIAL_DIR / f"{dataset}_link.json").read_text())
    coref = json.loads((MATERIAL_DIR / f"{dataset}_coref.json").read_text())
    link_by = {r["source_id"]: r for r in link["records"]}
    coref_by = {r["source_id"]: r for r in coref["records"]}
    return link_by, coref_by


def _contains(outer: tuple[int, int], inner: tuple[int, int]) -> bool:
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def _span_qid_map(link_rec: dict, coref_rec: dict | None) -> tuple[list[tuple[int, int, str, str]], int]:
    """(start, end, qid, how) 목록. coref 전파 포함. 반환 2번째 = 충돌 폐기 클러스터 수."""
    spans = [(s["start"], s["end"], s["qid"], "direct")
             for s in link_rec.get("spans", []) if s.get("qid")]
    conflicted = 0
    if coref_rec:
        for cluster in coref_rec.get("clusters", []):
            qids = set()
            for m in cluster:
                for (a, b, q, _) in spans:
                    if _contains((a, b), (m["start"], m["end"])) or \
                       _contains((m["start"], m["end"]), (a, b)):
                        qids.add(q)
            if len(qids) == 1:
                q = next(iter(qids))
                covered = {(a, b) for (a, b, _, _) in spans}
                for m in cluster:
                    key = (m["start"], m["end"])
                    if key not in covered:
                        spans.append((m["start"], m["end"], q, "coref"))
            elif len(qids) > 1:
                conflicted += 1
    return spans, conflicted


def _resolve_role(role, qid_spans: list[tuple[int, int, str, str]]) -> tuple[str, str] | None:
    """역할 span과 containment로 겹치는 QID. 다중 QID 충돌이면 None (보수)."""
    hits = {}
    for (a, b, q, how) in qid_spans:
        if _contains((role.start, role.end), (a, b)) or \
           _contains((a, b), (role.start, role.end)):
            hits[q] = how if q not in hits else hits[q]
    if len(hits) == 1:
        q, how = next(iter(hits.items()))
        return q, how
    return None


def weave_ml(
    build: ClaimGraphBuildV1,
    base_graph: TypedCompositionGraphV1,
    link_by_source: dict,
    coref_by_source: dict,
    *,
    max_fan: int = DEFAULT_MAX_FAN,
) -> tuple[WeaveResultV1, MlWeaveStats]:
    ordinals = {sid: i for i, sid in enumerate(base_graph.target_ids)}

    sha_mismatch = 0
    conflicted_total = 0
    n_direct = n_coref = 0

    # 문단별 QID span 지도 (텍스트 기반 sha 일치 강제)
    qid_spans_by_source: dict[str, list[tuple[int, int, str, str]]] = {}
    claims_by_source: dict[str, list[NaryClaimV1]] = {}
    for claim in build.nary_claims:
        claims_by_source.setdefault(claim.source_id, []).append(claim)
    for source_id, claims in claims_by_source.items():
        link_rec = link_by_source.get(source_id)
        if not link_rec:
            continue
        role_sha = claims[0].subject.source_text_sha256
        coref_rec = coref_by_source.get(source_id)
        if link_rec["source_text_sha256"] != role_sha or (
                coref_rec and coref_rec["source_text_sha256"] != role_sha):
            sha_mismatch += 1
            continue
        spans, conflicted = _span_qid_map(link_rec, coref_rec)
        conflicted_total += conflicted
        qid_spans_by_source[source_id] = spans

    # 역할 해소
    subject_qid: dict[str, list[NaryClaimV1]] = {}
    argument_hits: list[tuple[NaryClaimV1, object, str]] = []  # (claim, role, qid)
    for claim in sorted(build.nary_claims, key=lambda c: c.claim_id):
        spans = qid_spans_by_source.get(claim.source_id)
        if not spans:
            continue
        subj = _resolve_role(claim.subject, spans)
        if subj:
            q, how = subj
            subject_qid.setdefault(q, []).append(claim)
            n_direct += how == "direct"
            n_coref += how == "coref"
        for role in claim.arguments:
            if role.role_id == claim.subject.role_id:
                continue
            hit = _resolve_role(role, spans)
            if hit:
                q, how = hit
                argument_hits.append((claim, role, q))
                n_direct += how == "direct"
                n_coref += how == "coref"

    fan_capped = {q for q, row in subject_qid.items() if len(row) > max_fan}

    arcs, receipts, seen = [], [], set()
    for claim, role, q in argument_hits:
        if q in fan_capped:
            continue
        for target in subject_qid.get(q, ()):  # 주어가 같은 QID인 claim들
            woven = _woven_arc("m1_qid", ordinals, claim, role, target, f"qid:{q}")
            if woven and woven[0].arc_id not in seen:
                seen.add(woven[0].arc_id)
                arcs.append(woven[0])
                receipts.append(woven[1])

    stats = MlWeaveStats(
        paragraphs_sha_mismatch=sha_mismatch,
        clusters_conflicted=conflicted_total,
        qids_fan_capped=len(fan_capped),
        roles_resolved_direct=n_direct,
        roles_resolved_coref=n_coref,
    )
    return WeaveResultV1(arcs=tuple(arcs), receipts=tuple(receipts)), stats
