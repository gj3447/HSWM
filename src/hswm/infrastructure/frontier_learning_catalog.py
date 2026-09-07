"""Build a fixed literature reference projection; never execute or admit research."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
DATE = "2026-09-07"
BASE_COMMIT = "7d772925c5373d7747dc0e9e56653f99ce1c5002"
UID = "sym:AbstractNode:hswm-frontier-learning-theory-2026-09-07-v1"
OUT = "ontology/identity/hswm_core/HSWM_FRONTIER_LEARNING_THEORY_ONTOLOGY.v1.json"
DOC = "docs/research/HSWM_FRONTIER_LEARNING_THEORY_KG_2026-09-07.md"
NONCLAIM = "LITERATURE_REFERENCE_ONLY_NOT_IMPLEMENTED_NOT_HSWM_LEARNING_EFFICACY_OR_FCL_PROMOTION"
SHARDS = [f"_research/causal_composition/literature/frontier_{s}_{DATE}.json"
          for s in ("memory", "agent_world", "causal_program")]
ANCHORS = [
    "ontology/identity/hswm_core/HSWM_CONDITIONAL_CAPABILITY_CONTRACT_ONTOLOGY.v1.json",
    "ontology/identity/hswm_core/HSWM_HYPERGRAPH_LEARNING_PLAN_ONTOLOGY.v1.json",
    "ontology/identity/hswm_core/HSWM_RESEARCH_INSIGHTS_2026-09-06.v1.json",
]
FAMILIES = {
    "continual_memory": "계속학습·망각 제어 / Continual learning",
    "test_time_adaptation": "추론 중 학습·신경 기억 / Test-time adaptation",
    "agent_memory": "경험·성찰·기억 관리 / Agent memory",
    "reasoning_rl": "추론 강화학습·계산 배분 / Reasoning and RL",
    "world_models": "예측·월드모델 / World models",
    "workflow_optimization": "프롬프트·작업 흐름 학습 / Workflow optimization",
    "program_abstraction": "조건식·프로그램·추상화 / Program abstraction",
    "causal_identification": "인과 식별·개입 설계 / Causal identification",
    "higher_order_relations": "고차 관계·하이퍼그래프 / Higher-order relations",
    "structured_exploration": "구조화된 후보 탐색 / Structured exploration",
    "collective_credit": "공동 행동·기여도 / Collective credit",
}


def classify(family):
    if family in FAMILIES:
        return family
    if "continual" in family:
        return "continual_memory"
    if any(s in family for s in ("world_model", "world-model")):
        return "world_models"
    if any(s in family for s in ("workflow", "context_evolution")):
        return "workflow_optimization"
    if any(s in family for s in ("reinforcement", "test_time_compute", "acting_workflow")):
        return "reasoning_rl"
    if any(s in family for s in ("agent", "memory_management", "reasoning_memory")):
        return "agent_memory"
    if any(s in family for s in ("test-time", "test_time", "neural-memory", "nested-learning")):
        return "test_time_adaptation"
    raise ValueError(f"unclassified family: {family}")


def load_works():
    works, seen = [], set()
    for relative in SHARDS:
        data = json.loads((ROOT / relative).read_text())
        key = "entries" if "entries" in data else "works"
        for i, row in enumerate(data[key]):
            row = dict(row)
            identity = re.sub(r"v\d+$", "", row["url"])
            if identity in seen:
                continue
            seen.add(identity)
            row.update(source_path=relative, source_pointer=f"/{key}/{i}",
                       category=classify(row["family"]))
            if row["date"] and row["date"] > DATE:
                raise ValueError("source after declared cutoff")
            works.append(row)
    return sorted(works, key=lambda r: (r["category"], r["id"]))


def node(uid, name, description, role, **extra):
    return {"uid": uid, "labels": ["AbstractNode", "Concept"], "properties": {
        "name": name, "description": description, "standard_graph_role": role,
        "authority_class": "SECONDARY_AI", "status": "REFERENCE_RECORDED_UNTESTED_IN_HSWM",
        "claim_boundary": NONCLAIM, "projection_nonclaim": NONCLAIM,
        "ontology_sensitivity_v1": "NORMAL", "ontology_authority_class_v1": "SECONDARY_AI",
        "ontology_epistemic_state_v1": "PENDING", "ontology_record_lifecycle_v1": "ACTIVE",
        "ontology_review_required_v1": True, "ontology_canonical_scope_v1": "AI_ANALYSIS_NOT_USER_RATIFIED",
        "ontology_domain_v1": "AI", "ontology_kind_v1": "CONCEPT",
        "ontology_plane_v1": "RESEARCH_PROJECTION", "ontology_semantic_roles_v1": [role], **extra}}


def nid(slug):
    return "sym:AbstractNode:hswm-frontier-" + slug + "-2026-09-07-v1"


def document(works):
    lines = ["# HSWM 최신 학습 연구 참조 KG", "",
        f"기준일: {DATE}. 상태: SECONDARY_AI_LITERATURE_REFERENCE / HSWM 적용 효과 미검증.", "",
        "HSWM은 하나의 token-native LLM-function macro-neural network다. 이 KG는 그 본체의 학습기가 아니라 연구·구현 후보를 찾는 bounded projection이다. 이번 변화는 **논문 → 기전 → HSWM 적용 가설 → 반증 실험 → 기존 계약**을 조회 가능하게 연결한 것이다. 각 canonical atom의 schema-relative single owner, typed reference, outcome-bound revision 및 Inv/Permit 목표는 변경하지 않는다. FCL-1..8과 SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED를 보존한다.", "",
        f"선정한 {len(works)}개 연구를 {len(FAMILIES)}개 축으로 묶었다. 2025–2026년 연구를 우선하고 비교에 필요한 과거 기초 연구도 포함했다. 전수 조사·체계적 문헌고찰·모든 최신 이론 수록 주장이 아니다. 검색어·검토 범위·정확한 출처 URL은 세 문헌 JSON에 남긴다. 초록만 읽은 논문은 proof/전문 검토 또는 독립 재현으로 표시하지 않는다. 연도는 각 항목의 날짜 정의와 verification_note를 함께 읽는다.", "",
        "## 활용 방법", "",
        "MCP ontology_search에 아래 제목이나 논문 이름을 넣고 `include_preliminary=true`를 사용한다. 찾은 UID에 ontology_neighbors를 같은 옵션으로 호출하면 인접한 기전·적용 가설·실험을 따라갈 수 있다. 기본 검색은 미검토 AI 노드를 숨기므로 이 옵션을 생략하면 누락될 수 있다.", "",
        f"- 시작 노드: `{UID}`", "- 검색어 예: `HSWM 최신 학습 연구`, `Nested Learning`, `Narcissus`, `인과 식별`.",
        "- 구조화 조회: [Cypher](../../ontology/queries/HSWM_FRONTIER_LEARNING_THEORY_2026-09-07.cypher), [SPARQL](../../ontology/queries/HSWM_FRONTIER_LEARNING_THEORY_2026-09-07.sparql).",
        "- [온톨로지 JSON](../../ontology/identity/hswm_core/HSWM_FRONTIER_LEARNING_THEORY_ONTOLOGY.v1.json), [검증·게시 기록](../../ontology/projections/hswm_frontier_learning_theory_2026-09-07/verification.json).", "",
        "각 논문에 원 출처, 발표 상태, 확인 범위, 논문 기전, HSWM 적용 후보, 한계, 반증 조건, 적용 우선순위를 기록한다. near/medium/long은 AI가 제안한 연구 검토 순서이며 효능 등급이 아니다. 현재 interpreter가 논문이나 KG를 자동으로 읽어 알고리즘을 바꾸는 기능은 없다.", "",
        "## 지금 검토할 연결", "",
        "1. 조건식 생성: TheoryCoder-2·Narcissus·DreamCoder를 현재 유한 AST 후보 합성과 비교한다. 새 관측 field를 발견한 것으로 세지 않는다.",
        "2. 경험 재사용: ExpeL·Reflexion·ReasoningBank·ACE를 같은 이력과 비용을 가진 강한 대조로 고려한다. 논문 보고 성능을 HSWM 예상 성능으로 옮기지 않는다.",
        "3. 인과 credit: Causal ABA·intervention-only discovery에서 불완전한 prior와 식별 불가능성을 구분하는 방법을 참고한다. 그래프의 그럴듯함이 독립 outcome을 대체하지 않는다.",
        "4. 기억 갱신: Nested Learning·Titans·TTT는 다른 갱신 시간척도와 backend 비교 후보다. tensor/모델 내부 학습을 typed relation revision으로 즉시 치환할 수 없다.", "",
        "[현재 preview 구현](HSWM_CONDITIONAL_CAPABILITY_REFERENCE_2026-09-07.md)은 별도 구현상태 노드로 연결했다. 기존 ‘미구현’ 설계 projection의 역사적 bytes를 고치지 않았다. 31개 소프트웨어 검사 통과는 논문 기전 적용·HSWM 효능 입증이 아니다. G0 NOT_PASSED, G1 NOT_EVALUATED, D-4 미완료와 기존 P1 RED는 유지한다.", "",
        "## 연구 목록", "", "| 축 | 연구·원 출처 | 연도 | HSWM 검토 순서 |", "|---|---|---:|---|" ]
    for w in works:
        lines.append(f"| {FAMILIES[w['category']]} | [{w['title']}]({w['url']}) | {w['year']} | {w['priority']} |")
    lines += ["", "## 표현과 갱신", "",
        "공식 명세를 다시 확인한 [RDF 1.1](https://www.w3.org/TR/rdf11-concepts/), [SHACL 1.0](https://www.w3.org/TR/shacl/), [PROV-O](https://www.w3.org/TR/prov-o/), [SPARQL 1.1](https://www.w3.org/TR/sparql11-query/)을 기존 projection 도구로 재사용한다. SHACL은 구조를 검사하며 논문 주장이나 인과성을 검증하지 않는다. HSWM 어휘는 자체 도메인 설계이고 W3C 표준이 아니다.", "",
        "새 패키지·모델·논문 전문을 설치하거나 배포하지 않았다. RDFLib 7.6.0(BSD-3-Clause)·PySHACL 0.40.1(Apache-2.0)은 기존 [잠금 파일](../../_research/graph_standards/runtime/uv.lock)과 [권위·라이선스 기록](../../_research/graph_standards/HSWM_GRAPH_STANDARDS_ACCEPTANCE.v1.json)의 독립 구현이다. 원문은 링크로 참조하고 직접 작성한 요약·HSWM 가설만 저장한다.", "",
        "향후 새 논문을 넣을 때 원 출처·날짜·버전·검토 범위를 확인하고 적용 기전과 반증 조건을 적는다. 기존 게시본을 덮어쓰지 않고 후속 version/bundle과 출처 계보로 갱신한다. 이 KG의 크기 증가는 과학적 성과로 승격하지 않는다.", "",
        "```sh", "uv run python -m hswm.infrastructure.frontier_learning_catalog",
        "uv run --project _research/graph_standards/runtime --locked --extra graph python -m hswm.infrastructure.frontier_learning_projection --export-dir ontology/projections/hswm_frontier_learning_theory_2026-09-07", "```", ""]
    return "\n".join(lines)


def build(works):
    nodes = [node(UID, "HSWM 최신 학습 연구 참조 KG 2026-09-07", "논문 → 기전 → HSWM 적용 후보 → 반증 조건. 이론 목록과 구현·효능을 구분한 참조 지도.", "FRONTIER_CATALOG", source_commit=BASE_COMMIT, cutoff_date=DATE, paper_count=len(works), aliases=["HSWM frontier learning", "최신 AI 학습 이론", "학습 이론 지도"])]
    relations, anchors = [], []
    def edge(a, t, b):
        relations.append({"from_uid": a, "type": t, "to_uid": b,
                          "authority_class": "SECONDARY_AI", "scope": "FRONTIER_LITERATURE_REFERENCE_2026_09_07", "status": "REFERENCE_LINK_NOT_EFFICACY"})
    for path in ANCHORS:
        d = json.loads((ROOT/path).read_text())
        n = next(n for n in d["nodes"] if n["uid"] == d["bundle_uid"])
        anchors.append({"uid": n["uid"], "name": n["properties"]["name"], "required_labels": n["labels"]})
        edge(UID, "PRESERVES", n["uid"])
    implementation = nid("conditional-preview-status")
    nodes.append(node(implementation, "조건부 능력 preview 구현 상태 7d77292", "31개 소프트웨어 검사 통과. 제한된 AST/preview와 공개 예시 합성. 외부 outcome-credit-admission 및 이 KG의 논문별 기전 적용은 미완료.", "IMPLEMENTATION_SNAPSHOT", source_commit=BASE_COMMIT, source_paths=["src/hswm/cells/conditional.py", "docs/research/HSWM_CONDITIONAL_CAPABILITY_REFERENCE_2026-09-07.md"], implementation_status="BOUNDED_PREVIEW_IMPLEMENTED", efficacy_status="NOT_EVALUATED"))
    edge(UID,"HAS_CONCEPT",implementation)
    edge(implementation,"HAS_SOURCE",anchors[0]["uid"])
    for family, name in FAMILIES.items():
        nodes.append(node(nid(family),name,"원 출처가 있는 연구 기전을 탐색하는 분류. HSWM subsystem 분해가 아님.","THEORY_FAMILY",family=family))
        edge(UID,"HAS_CONCEPT",nid(family))
    for w in works:
        slug = re.sub(r"[^a-z0-9-]", "-", w["id"].lower()).strip("-")
        paper, mechanism, bridge, test = (nid(slug+"-"+s) for s in ("paper","mechanism","bridge","test"))
        origin={"source_paths":[w["source_path"]],"primary_artifact_path":w["source_path"],"primary_artifact_json_pointer":w["source_pointer"]}
        nodes.append(node(paper,w["title"],w["mechanism"]+" Source: "+w["url"],"LITERATURE_SOURCE",url=w["url"],aliases=[w["id"],w.get("slug",w["id"])] + ({"2602.00929":["TheoryCoder-2"],"2301.04104":["DreamerV3","Dreamer"],"1705.08926":["COMA"],"2503.01203":["Hyper-FM"],"2604.00830":["Meta-TTL"]}.get(re.sub(r"v\d+$", "",w["url"].rsplit("/",1)[-1]),[])),authors=w["authors"],year=w["year"],source_date=w["date"] or "UNVERIFIED",source_version=("ARXIV_V"+re.search(r"v(\d+)$",w["url"]).group(1) if "arxiv.org/abs/" in w["url"] else "PUBLISHER_RECORD"),source_verified_on=DATE,date_semantics=("FIRST_ARXIV_SUBMISSION" if "arxiv.org/abs/" in w["url"] else "PUBLISHER_DATE"),source_status=w["source_status"],inspected_scope=w["inspected_scope"],verification_note=w["verification_note"],source_authority_class="EXTERNAL_PRIMARY_SOURCE_REPORTED",family=w["category"],**origin))
        nodes.append(node(mechanism,"기전 — "+w["title"],w["mechanism"],"REPORTED_MECHANISM",family=w["category"],limitation=w["limitation"],**origin))
        nodes.append(node(bridge,"HSWM 적용 후보 — "+w["title"],w["hswm_bridge"],"HSWM_BRIDGE_CANDIDATE",family=w["category"],priority=w["priority"],limitation=w["limitation"],implementation_status="NOT_IMPLEMENTED_FROM_THIS_SOURCE",efficacy_status="UNTESTED_IN_HSWM",**origin))
        nodes.append(node(test,"반증 조건 — "+w["title"],w["falsifier"],"PROPOSED_FALSIFIER",test_status="NOT_EXECUTED",**origin))
        for a,t,b in [(UID,"HAS_SOURCE",paper),(paper,"HAS_CONCEPT",mechanism),(mechanism,"HAS_SOURCE",paper),(nid(w["category"]),"HAS_CONCEPT",mechanism),(mechanism,"SPECULATIVE_LINK",bridge),(bridge,"REQUIRES",test),(test,"TESTS",bridge),(bridge,"HAS_SOURCE",paper),(bridge,"SPECULATIVE_LINK",anchors[0 if w["category"] in {"program_abstraction","agent_memory","causal_identification","workflow_optimization"} else 1]["uid"])]:
            edge(a,t,b)
    bindings = SHARDS + ANCHORS + [DOC,"docs/canon/HSWM_CONSTITUTION_2026-08-20.md","docs/canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md","docs/research/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md","ontology/identity/human_universal_body/HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_ONTOLOGY.v1.json","src/hswm/cells/conditional.py","docs/research/HSWM_CONDITIONAL_CAPABILITY_REFERENCE_2026-09-07.md","_research/graph_standards/runtime/uv.lock"]
    return {"schema_version":"hswm-frontier-learning-theory/v1","bundle_uid":UID,"status":"LITERATURE_REFERENCE_HSWM_BRIDGES_UNTESTED","nonclaim":NONCLAIM,"authority_boundary":"All new nodes are SECONDARY_AI curation. Reported primary-source mechanisms are explicitly distinguished from proposed HSWM bridges; no USER_PRIMARY ratification or efficacy inherited.","source_accessed_on":DATE,"artifact_bindings":[{"path":p,"sha256":sha256((ROOT/p).read_bytes()).hexdigest()} for p in bindings],"expected_counts":{"nodes":len(nodes),"anchors":len(anchors),"relations":len(relations),"papers":len(works),"families":len(FAMILIES)},"anchors":anchors,"nodes":nodes,"relations":relations}


def main():
    works=load_works()
    (ROOT/DOC).write_text(document(works),encoding="utf-8")
    data=build(works)
    (ROOT/OUT).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(data["expected_counts"]))


if __name__ == "__main__":
    main()
