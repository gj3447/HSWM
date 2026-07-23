"""PhantomWiki → HSWM typed graph 결정론 인게스트 (R3, LLM 0콜).

PhantomWiki article은 ground-truth Prolog fact를 동봉하고 본문이 템플릿 문장이라
`fact ↔ 본문 문장`이 1:1이다.  따라서 추출기 없이도 **모든 arc가 원문 exact span에
바인딩된** typed graph를 만들 수 있다 — 우리 증거계약을 유지한 채 걷기 승리
regime(PROM-8 C4)으로 판을 옮기는 것이 R3의 목적.

규율:
  - span은 fact의 두 이름과 술어형이 **같은 줄**에 있을 때만 인정(줄 offset 기준),
    text[start:end] == exact 즉석 검증. 실패는 드롭·카운트(날조 0).
  - person-person fact만 arc가 된다. attribute fact(job/hobby/gender)는 claim으로만
    남아 seed 매칭에 기여.
  - target_claim_id = 대상 인물이 subject인 claim 중 결정론 첫 번째 → claim 연속성
    성립(T3 strict 워커가 그대로 걸을 수 있는 형태).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from claim_builder import ArgumentRoleV1, NaryClaimV1
from typed_composition import (
    SelectorSpanV1, TypedEvidenceArcV1, make_typed_graph,
)

FACT_RE = re.compile(r'^(\w+)\("([^"]+)",\s*"([^"]+)"\)\.$')
# 본문 술어 표면형 후보 (fact 술어 → 텍스트 등장형)
SURFACE = {
    "sister": ("sisters", "sister"), "brother": ("brothers", "brother"),
    "mother": ("mother",), "father": ("father",),
    "daughter": ("daughters", "daughter"), "son": ("sons", "son"),
    "wife": ("wife",), "husband": ("husband",),
    "friend": ("friends", "friend"),
    "job": ("occupation",), "hobby": ("hobby",), "gender": ("gender",),
    "dob": ("date of birth",),
}
PERSON_PREDICATES = frozenset({
    "sister", "brother", "mother", "father", "daughter", "son",
    "wife", "husband", "friend",
})


def _sha_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def source_id_for(title: str) -> str:
    return "phantom:" + sha256(title.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class IngestStats:
    articles: int
    facts_total: int
    facts_bound: int
    facts_unbound: int
    person_arcs: int
    attribute_claims: int


def _role(source_id: str, kind: str, role: str, text: str,
          start: int, exact: str) -> ArgumentRoleV1:
    return ArgumentRoleV1(
        role_id=f"role:{source_id}:{role}:{start}:{len(exact)}",
        source_id=source_id, role_kind=kind, role=role,
        start=start, end=start + len(exact), exact=exact,
        prefix="", suffix="", source_text_sha256=_sha_text(text))


def _selector(role: ArgumentRoleV1) -> SelectorSpanV1:
    return SelectorSpanV1(
        source_id=role.source_id, role_id=role.role_id, role=role.role,
        text_scope="body", start=role.start, end=role.end, exact=role.exact,
        source_text_sha256=role.source_text_sha256)


def _bind_line(text: str, subject: str, obj: str, predicate: str):
    """(line_offset, pred_start, pred_exact) — 세 요소가 한 줄에 있을 때만."""
    offset = 0
    for line in text.split("\n"):
        if subject in line and obj in line:
            for surf in SURFACE.get(predicate, (predicate,)):
                idx = line.find(surf)
                if idx >= 0:
                    return offset, offset + idx, surf
        offset += len(line) + 1
    return None


def load_universe(path: Path) -> tuple[list[dict], list[dict]]:
    articles = json.loads((path / "articles.json").read_text(encoding="utf-8"))
    questions: list[dict] = []
    for qf in sorted((path / "questions").glob("type*.json")):
        questions.extend(json.loads(qf.read_text(encoding="utf-8")))
    return articles, questions


def build_graph(articles: list[dict]):
    """returns (target_ids, graph, claims_by_source, title_by_source, stats)."""
    by_title = {a["title"]: a for a in articles}
    ordered = sorted(articles, key=lambda a: a["title"])
    target_ids = tuple(source_id_for(a["title"]) for a in ordered)
    ordinals = {sid: i for i, sid in enumerate(target_ids)}

    claims_by_source: dict[str, list[NaryClaimV1]] = {}
    subject_claim: dict[str, NaryClaimV1] = {}  # title -> 대표 claim (자기가 subject)
    pending: list[tuple[str, str, str, NaryClaimV1, ArgumentRoleV1]] = []
    facts_total = facts_bound = attribute_claims = 0

    for art in ordered:
        title, text = art["title"], art["article"]
        sid = source_id_for(title)
        claims_by_source.setdefault(sid, [])
        for i, raw in enumerate(art["facts"]):
            m = FACT_RE.match(raw.strip())
            if not m:
                continue
            facts_total += 1
            pred, subj, obj = m.group(1), m.group(2), m.group(3)
            if subj != title:
                continue  # 자기 문서의 주어만 (결정론·중복 방지)
            bound = _bind_line(text, subj, obj, pred)
            if not bound:
                continue
            _, pred_start, pred_exact = bound
            subj_start = text.find(subj)
            obj_start = text.find(obj, pred_start)
            if subj_start < 0 or obj_start < 0:
                continue
            if text[subj_start:subj_start + len(subj)] != subj or \
               text[obj_start:obj_start + len(obj)] != obj or \
               text[pred_start:pred_start + len(pred_exact)] != pred_exact:
                continue
            facts_bound += 1
            subject_role = _role(sid, "entity", "subject", text, subj_start, subj)
            predicate_role = _role(sid, "predicate", "predicate", text,
                                   pred_start, pred_exact)
            object_role = _role(sid, "entity", pred, text, obj_start, obj)
            claim = NaryClaimV1(
                claim_id=f"claim:{sid}:{i}", source_id=sid,
                subject=subject_role, predicate=predicate_role,
                arguments=(object_role,),
                observation_ids=(f"obs:{sid}:{i}",))
            claims_by_source[sid].append(claim)
            if title not in subject_claim:
                subject_claim[title] = claim
            if pred in PERSON_PREDICATES and obj in by_title:
                pending.append((title, obj, pred, claim, object_role))
            else:
                attribute_claims += 1

    arcs: list[TypedEvidenceArcV1] = []
    for subj_title, obj_title, pred, claim, object_role in pending:
        target_claim = subject_claim.get(obj_title)
        if target_claim is None:
            continue
        src_sid, tgt_sid = source_id_for(subj_title), source_id_for(obj_title)
        if ordinals[src_sid] == ordinals[tgt_sid]:
            continue
        arcs.append(TypedEvidenceArcV1(
            arc_id=f"arc:{claim.claim_id}:{object_role.start}",
            source_target=ordinals[src_sid], target_target=ordinals[tgt_sid],
            source_id=src_sid, target_id=tgt_sid,
            source_claim_id=claim.claim_id, target_claim_id=target_claim.claim_id,
            source_predicate=_selector(claim.predicate),
            target_predicate=_selector(target_claim.predicate),
            source_argument_role=pred,
            target_argument_role=target_claim.subject.role,
            join_entity_id=f"person:{obj_title}",
            source_selector=_selector(object_role),
            target_selector=_selector(target_claim.subject),
            origin="verified_shared_entity"))

    arcs.sort(key=lambda a: a.arc_id)
    graph = make_typed_graph(target_ids, tuple(arcs))
    stats = IngestStats(
        articles=len(ordered), facts_total=facts_total, facts_bound=facts_bound,
        facts_unbound=facts_total - facts_bound, person_arcs=len(arcs),
        attribute_claims=attribute_claims)
    title_by_source = {source_id_for(a["title"]): a["title"] for a in ordered}
    return target_ids, graph, claims_by_source, title_by_source, stats


def gold_sources(question: dict, titles: set[str]) -> set[str]:
    """solution trace 등장 인물 + 정답 인물의 article = gold 문서 집합."""
    names: set[str] = set()
    traces = question.get("solution_traces")
    if isinstance(traces, str):
        try:
            traces = json.loads(traces)
        except Exception:
            traces = []
    for tr in traces or []:
        for v in (tr or {}).values():
            if isinstance(v, str) and v in titles:
                names.add(v)
    for a in question.get("answer") or []:
        if isinstance(a, str) and a in titles:
            names.add(a)
    return {source_id_for(n) for n in names}
