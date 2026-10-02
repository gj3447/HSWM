# Research coordination graph and USL interface boundaries

기존 주제 ID: `research_coordination_and_usl_interfaces`. 정리: 2026-10-02, `SECONDARY_AI`.

[전체 연구 지도](../HSWM_RESEARCH_ATLAS_2026-10-02.md) · [이전 주제 registry](../../../ontology/knowledge_map/HSWM_KNOWLEDGE_MAP_TOPICS_2026-09-13.v1.json)

주제별 배치는 탐색 해석이다. 원문 권위·역사적 상태·실험 판정은 원문에 남으며, 같은 문서가 여러 주제에 나타날 수 있다.

조사 대상 Git cut: `a7272a13cd6d304b7f8a1911dca0158e0bc67f29`. 아래 16개 요약은 이 cut의 원문에 결속된다.

## [CHU와 HSWM의 계산 구조](../../../docs/research/CHU_HSWM_COMPUTATIONAL_ARCHITECTURE_2026-09-27.md)

CHU는 계산 가능한 모델·프로그램·상태를 포괄하는 넓은 개념이고 HSWM은 그 안의 LLM 함수·지속 Semantic Weight AI로 구분한다. 이는 표준 그래프 계약을 위한 SECONDARY_AI 구조 해석이며 CHU 실행환경 완성 보고가 아니다.

- 자료 역할: `THEORY` · 관점: `map`, `philosophy`
- 원문 상태: SECONDARY_AI_ARCHITECTURE_2026-09-27_IMPLEMENTATION_LIMITS_EXPLICIT
- 주장 한계: Conceptual architecture, not completed CHU or HSWM execution.
- 원문 위치: ## 1. 포함 범위와 능력을 다른 관계로 표현한다

## [HSWM ⇄ 하네스 문서 렌즈-쌍대성 설계 정합서](../../../docs/research/DESIGN_HARNESS_DOC_HSWM_LENS_DUALITY_2026-07-21.md)

HSWM source와 하네스 문서를 asymmetric delta lens의 lossy view로 제안하고 shared spine의 consistency만 보존 대상으로 둔다. 이 쌍대성과 場 단위는 사용자 비준 전 제안이며 실제 runtime이 deprecated toy lens를 쓴다는 blocker를 남긴다.

- 자료 역할: `THEORY` · 관점: `hypothesis`, `plan`, `philosophy`, `comparison`
- 원문 상태: HISTORICAL_SECONDARY_AI_PROPOSAL
- 주장 한계: Proposal is neither ratified canon nor a runtime deployment claim.
- 원문 위치: status: `SECONDARY_AI_PROPOSAL`

## [HSWM 추가 도구와 논문 본문 검토](../../../docs/research/HSWM_ADDITIONAL_TOOLS_AND_PAPER_REVIEW_2026-09-27.md)

Reasoning Gym·XGrammar·Docling/GROBID를 실험·근거수집 후보로, HyperNetX와 HyperGraphRAG를 제한된 분석·대조군으로 검토한다. 버전 고정 출처와 적용 설계만 추가했으며 패키지 설치나 모델 실험 결과는 없다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `plan`, `operations`
- 원문 상태: HISTORICAL_SECONDARY_AI_TOOL_AND_PAPER_REVIEW
- 주장 한계: Tool review is not installation, a new writer, or efficacy evidence.
- 원문 위치: 이번에 가져온 것은 버전을 고정한 출처와 적용 설계이며 패키지 설치나 모델 실험 결과가 아니다.

## [HSWM cross-project graph and harness engineering adoption profile](../../../docs/research/HSWM_CROSS_PROJECT_GRAPH_HARNESS_ADOPTION_2026-09-01.md)

다른 project에서 graph/harness 규율을 채택할 때 source pin·permission·boundary를 지키는 rollout profile을 제안한다. cross-project 연결은 해당 project의 결과나 HSWM learning efficacy를 자동으로 공유하지 않는다.

- 자료 역할: `PROTOCOL` · 관점: `operations`, `map`, `plan`
- 원문 상태: HISTORICAL_ADOPTION_PROFILE_NOT_DEPLOYMENT_EVIDENCE
- 주장 한계: adoption profile은 remote access·publication·causal efficacy 권한을 부여하지 않는다.
- 원문 위치: ## 7. Recommended rollout

## [HSWM-like 도구의 CLI 계약과 CHU·HSWM·USL의 관계](../../../docs/research/HSWM_LIKE_CLI_USL_CHU_CONTRACT_2026-09-29.md)

CHU·HSWM·USL·독립 CLI의 책임을 분리하고 HSWM-like tool이 직접 실행 가능한 program이어야 한다는 profile을 제안한다. 모든 tool 구현·CHU/HSWM execution 통합은 완료되지 않았고 제안은 user ratification이 아니다.

- 자료 역할: `THEORY` · 관점: `operations`, `map`, `philosophy`
- 원문 상태: SECONDARY_AI_DESIGN_PROPOSED_2026-09-29
- 주장 한계: CLI and ecosystem contract proposal only.
- 원문 위치: ## 1. 세 체계와 도구의 책임

## [HSWM-like rule ontology and evaluation](../../../docs/research/HSWM_LIKE_RULE_ONTOLOGY_AND_EVALUATION_2026-09-29.md)

source fidelity·multiscale map·role composition·context activation·local adjustability·evaluability 축으로 HSWM-like profile을 제안한다. template score는 INCOMPLETE/null이며 score가 canonical status·confidence·learning efficacy를 자동 변경하지 않는다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `plan`, `negative`
- 원문 상태: HISTORICAL_SECONDARY_AI_PROPOSED_INCOMPLETE_SCORE_NULL
- 주장 한계: Evaluation profile is not canonical status or efficacy evidence.
- 원문 위치: 규칙의 HSWM적 구성: 온톨로지와 평가 v1

## [HSWM philosophy KG remediation](../../../docs/research/HSWM_PHILOSOPHY_KG_REMEDIATION_2026-09-07.md)

철학 KG의 source·authority·claim boundary를 정리하고 오해 가능한 관계를 remediation 대상으로 둔다. KG 항목의 정합성은 사용자 정체성의 자동 비준이나 scientific efficacy의 근거가 아니다.

- 자료 역할: `REVIEW` · 관점: `philosophy`, `map`, `negative`
- 원문 상태: HISTORICAL_SECONDARY_AI_KG_REMEDIATION
- 주장 한계: KG remediation is not canon ratification or outcome evidence.
- 원문 위치: HSWM 철학 KG 수리 후속 기록

## [HSWM 프로그램과 HSWM적인 성질의 구분](../../../docs/research/HSWM_PROGRAM_AND_HSWM_LIKENESS_2026-09-29.md)

HSWM system 이름과 HSWM-like/HSWM-likeness라는 부분적 설계 성질을 분리하는 용어 제안이다. 표기 권고와 profile은 SECONDARY_AI이며 사용자 ratification이나 전체 HSWM 효능을 뜻하지 않는다.

- 자료 역할: `THEORY` · 관점: `philosophy`, `map`
- 원문 상태: SECONDARY_AI_PROPOSED_TERMINOLOGY_2026-09-29
- 주장 한계: Naming and scope proposal only.
- 원문 위치: ## 온톨로지와 점수의 범위 수정

## [HSWM 연구 통합 그래프 — 2026-09-20](../../../docs/research/HSWM_RESEARCH_INTEGRATION_2026-09-20.md)

Jev observation, DGX learning, proof/work-plan을 source-bound integration graph로 연결하고 open obligations를 유지한다. 통합 graph는 각 input의 실험·proof·runtime 상태를 재평가하거나 completion으로 승격하지 않는다.

- 자료 역할: `NAVIGATION` · 관점: `map`, `operations`, `plan`
- 원문 상태: HISTORICAL_SOURCE_BOUND_RESEARCH_INTEGRATION
- 주장 한계: integration projection은 HSWM cognition·learning·efficacy evidence가 아니다.
- 원문 위치: ## 표준과 검증

## [HSWM 과학 연구 도구화 조사 — 2026-09-13](../../../docs/research/HSWM_SCIENTIFIC_RESEARCH_TOOLING_2026-09-13.md)

RDF/SHACL/SPARQL/PROV, formal proof, experiment tracking 도구를 HSWM 연구 requirement와 capability gap에 맞춰 조사한다. tool availability와 graph projection은 도구 채택, model run, scientific efficacy를 뜻하지 않는다.

- 자료 역할: `REVIEW` · 관점: `operations`, `map`, `comparison`
- 원문 상태: HISTORICAL_RESEARCH_TOOLING_SURVEY
- 주장 한계: tool survey는 HSWM cognition이나 implementation completion의 증거가 아니다.
- 원문 위치: ## Source appendix

## [USL을 HSWM 어댑터로 도입하기](../../../docs/research/HSWM_USL_ADAPTER_ADVERSARIAL_REVIEW_2026-09-08.md)

역할 있는 USL reference를 finite observation으로 변환해 behavior proposal과 re-observation proposal을 바꾸는 adapter를 구현·검토했다. semantic truth, task success, causal credit은 NOT_EVALUATED이며 adapter pass는 G0/G1/D-4나 효능을 변경하지 않는다.

- 자료 역할: `IMPLEMENTATION` · 관점: `implementation`, `comparison`, `negative`
- 원문 상태: EXPERIMENTAL_EXTERNAL_REFERENCE_OBSERVATION_2026-09-08
- 주장 한계: External-reference observation adapter only.
- 원문 위치: ## 사용 순서와 검증 범위

## [HSWM USL latest adversarial review](../../../docs/research/HSWM_USL_LATEST_ADVERSARIAL_REVIEW_2026-09-08.md)

USL adapter와 relation instrument의 current claims·source boundaries·remaining adversarial risks를 검토한다. bridge·registry·test evidence는 cross-project semantic learning이나 remote authority를 자동으로 만들지 않는다.

- 자료 역할: `REVIEW` · 관점: `comparison`, `operations`, `negative`
- 원문 상태: HISTORICAL_SECONDARY_AI_ADVERSARIAL_REVIEW
- 주장 한계: USL review is not remote execution, authorization, or efficacy evidence.
- 원문 위치: 최신 USL 적대적 검증 — 관측 수정 이후

## [HSWM과 USL — 의미 연결을 경험·계산·재귀 합성으로 내리는 설계](../../../docs/research/HSWM_USL_SEMANTIC_ENGINEERING_BRIDGE_2026-09-07.md)

USL link를 HSWM condition·observation·relation composition과 연결하는 semantic-engineering bridge를 설계한다. bridge는 non-executed proposal이며 USL binding이 access, canonical write, learning outcome을 부여하지 않는다.

- 자료 역할: `PLAN` · 관점: `map`, `plan`, `hypothesis`
- 원문 상태: HISTORICAL_USL_BRIDGE_PROPOSAL_NOT_EXECUTED
- 주장 한계: USL semantic bridge는 implementation·permission·efficacy 증거가 아니다.
- 원문 위치: ## 8. 이번 산출물의 확인 범위

## [USL v2 구현 독립 검토](../../../docs/research/HSWM_USL_V2_IMPLEMENTATION_REVIEW_2026-09-08.md)

USL v2의 sourceText time-of-check/time-of-use 결속 결함과 contradictory observation JSON validation 누락을 재현했고 HSWM adapter version mismatch도 기록했다. 제한된 CLI 검토는 integration readiness를 높일 수 있으나 observation은 cognition·learning·causal judgement를 대신하지 않는다.

- 자료 역할: `REVIEW` · 관점: `implementation`, `negative`, `comparison`
- 원문 상태: INDEPENDENT_IMPLEMENTATION_REVIEW_2026-09-08_DEFECTS_RECORDED
- 주장 한계: USL library audit, not HSWM efficacy evidence.
- 원문 위치: ## 먼저 수정할 항목

## [HSWM whole map](../../../docs/research/HSWM_WHOLE_MAP_2026-10-01.md)

9월 연구 지도에 runtime·standard projection·historical gate·infrastructure boundary를 더해 전체 내용을 source-bound navigation으로 배열한다. 지도는 live state·deployment·causal credit·LLM efficacy를 증명하지 않는다는 claim ceiling을 유지한다.

- 자료 역할: `NAVIGATION` · 관점: `map`, `negative`, `history`
- 원문 상태: HISTORICAL_SECONDARY_AI_WHOLE_MAP_NAVIGATION
- 주장 한계: Map is source navigation, not a canonical state or efficacy publication.
- 원문 위치: HSWM 전체 연구 지도 — 2026-10-01

## [PROM 8 dynamic two lanes](../../../docs/research/PROM_8_DYNAMIC_TWO_LANES_2026-07-22.md)

dynamic two-lane research/program organization을 통해 exploration과 controlled evidence lanes를 구분한다. lane organization 자체는 learning effect나 scientific completion을 만들지 않는다.

- 자료 역할: `NAVIGATION` · 관점: `plan`, `operations`, `history`
- 원문 상태: HISTORICAL_PROM_PROGRAM_ORGANIZATION
- 주장 한계: Process organization is not efficacy evidence.
- 원문 위치: PROM 8 — "동적 HSWM" 두 차선 전방위 리서치 (2026-07-22)

## 역사적 열린 질문

아래 질문은 2026-09-13 registry의 기록이며 이번 정리로 해결 판정하지 않았다.

- How can bounded coordination artifacts remain useful without being misreported as HSWM cognition or learning?
- Can a source-authenticated external graph interface support a future experiment without becoming a canonical-write path?
