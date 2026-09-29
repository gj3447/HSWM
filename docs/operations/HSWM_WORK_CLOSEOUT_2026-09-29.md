# HSWM 연구·구현 작업 기록 마무리

2026-09-29. [기록·마무리 요청](artifacts/hswm_work_closeout_2026-09-29/user-request.txt)에 따라
이번 대화에서 이어 온 방향·연구·구현·미완료 항목을 기존 출처에 연결한다.
**완료 범위는 기록 정리다. 전체 HSWM 또는 통합 API의 구현 완료 판정이 아니다.**
이 문서의 요약·상태 판독은 `SECONDARY_AI`이며 사용자 원문과 구분한다.

## 이어받을 기준

그래프가 AI의 지속 상태와 프로그램이고, TS/Effect는 이를 해석하는 버전 있는 실행기다.
학습은 graph revision으로 다음 동작을 바꾼다. HSWM은 LLM 국소 연산자와 Semantic Weight
하이퍼그래프로 작동하는 하나의 AI이며, CHU는 HSWM과 비LLM 세계 모델도 포괄하는 더 넓은
개념이다. JSON은 직렬화, RDF·연구 KG·현재 Neo4j adapter는 projection의 역할을 가진다.
이 기준은 [작업 규칙](../../AGENTS.md), [방향 정정](../research/HSWM_GRAPH_PROGRAM_DIRECTION_2026-09-28.md),
[CHU 범위](../canon/USER_PRIMARY_CHU_HSWM_SOFTWARE_SCOPE_2026-09-27.md)에 연결한다.

## 작업별 상태와 근거

아래 검증 수치는 각 날짜의 기존 기록이다. 이번에 모델 실행·Lean replay·runtime 테스트를
다시 수행했다는 뜻이 아니다. 과거 원문·hash·음성 결과를 그대로 보존한다.

| ID | 작업과 기록된 상태 | 출처와 경계 |
| --- | --- | --- |
| `identity` | 그래프 상태·프로그램과 실행기의 구분을 문서·작업 규칙·KG에 기록 | [방향 정정](../research/HSWM_GRAPH_PROGRAM_DIRECTION_2026-09-28.md). 학습 때마다 TS 소스를 수정한다는 해석을 배제한다. |
| `philosophy` | 세 철학의 공학적 번역과 유한·조건부 Lean 모형을 기록 | [세 철학](../research/HSWM_THREE_PHILOSOPHIES_LEAN_2026-09-27.md). 물리 우주 전체·보편 최소비용·현실 LLM 효능의 증명이 아니다. |
| `chu-map` | CHU/HSWM 범위와 층간 Map의 설계·유한 구현을 연결 | [CHU 실행 구조](../research/CHU_HSWM_COMPUTATIONAL_ARCHITECTURE_2026-09-27.md), [Map 구현](../../_research/cross_layer_map_v1/README.md). 범용 CHU VM의 완성은 아니다. |
| `sources` | 연구 환경·표준 사용법과 원문 수집 이력 보존 | [연구 workflow](HSWM_RESEARCH_WORKFLOW.md), [원문 archive](../../_research/source_archive_2026-09-28/README.md). 9월 28일 집계는 852개 원 URL 중 810개 확보·42개 미확보다. 추가 원문 captures는 해당 후속 문서에 별도로 남아 있다. |
| `lean` | 실제 Lean 검사 범위와 실행 구현 간 공백을 재점검 | [검증 감사](../research/HSWM_LEAN_VALIDATION_REVIEW_2026-09-28.md). 구조 import closure·통계 프로젝트 replay 기록은 통과이고, Mathlib 포함 전체 통계 fresh replay는 600초 제한으로 미완료다. |
| `runtime` | 고정 실행기로 durable graph program의 순서를 바꾸는 최소 구현 검증 | [구현·13개 관련 검사](../../_research/graph_program_direction_2026-09-28/verification.v1.json). 수동 revision `A→B`/`B→A`, scripted HTTP fixture의 결과다. |
| `access-design` | AI 직접 typed API·선택적 자연어 입력·기존 SPARQL 조회라는 설계 제안 기록 | [접근 설계](HSWM_ACCESS_INTERFACE_2026-09-29.md). 사용자 질문과 AI 제안을 구별한다. |
| `access-implementation` | 통일 read/run/observe/revise facade와 HSWM MCP/NL 입구는 미구현 | [접근 설계의 개발 순서](HSWM_ACCESS_INTERFACE_2026-09-29.md#개발-순서). 기존 개별 함수의 존재를 이 통합 인터페이스의 완성으로 계산하지 않는다. |
| `efficacy` | 전체 HSWM 효능·재귀 실현·CR/FCL 완료는 확립되지 않음 | [기존 연구 자기점검](../research/HSWM_RESEARCH_SELF_REVIEW_2026-09-27.md). 실제 모델의 과거 음성 결과와 미해결 의무를 유지한다. |
| `live-kg` | 방향 정정·접근 설계 노트와 옛 대표 record의 현재 존재·본문 digest·source_ref를 재확인 | [현재 readback](artifacts/hswm_work_closeout_2026-09-29/live-check.v1.json). 옛 HSWM 대표 본문은 남아 있고 정정 노트/관계는 SECONDARY_AI/PROPOSED다. |

Hyperon은 기존 `hyperon-experimental v0.2.10` / commit
`3f76dc460da6961f57f69f6c3e550c59c74ada83` 비교 범위를 이어받는다. 이번 기록은 새 benchmark나
도구 설치가 아니며, [기존 비교 성숙도](../research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)를 바꾸지 않는다.

## 표준 그래프 기록과 확인할 질문

[마무리 KG](../../ontology/development/HSWM_WORK_CLOSEOUT_2026-09-29.v1.json)는 이전 bundle을
덮어쓰지 않는 읽기용 snapshot이다. 안정된 UID, 명시적 타입·권위·상태, 출처 path·SHA-256을
결속한다. 이전 검사 결과를 인용하는 상태 기록과 이번 라이브 KG 관측을 분리한다.
기존 RDF 1.1 projection, SHACL 1.0, SPARQL 1.1, PROV-O 도구를 그대로 사용한다.

| 재사용 관계 | domain → range / cardinality | 의미 |
| --- | --- | --- |
| `HAS_COMPONENT` | 마무리 bundle → 작업 상태 기록 / 이 snapshot에서 10개 | 이번 기록의 구성 항목. AI 내부 subsystem 분해가 아니다. |
| `HAS_SOURCE` | 마무리 bundle → 사용자 요청 source / 1개 | 기록 작업의 직접 요청. AI 요약에 사용자 권위를 부여하지 않는다. |
| `REFERENCES` | 작업 상태 기록 → 기존 KG note / 0개 이상 | 기존 출처 참조. 동치·인과·권한·사용자 승인 관계가 아니다. |

[status.rq](../../ontology/queries/hswm_work_closeout_2026-09-29/status.rq)는
“무엇이 구현·검증되었고 무엇이 제안·미구현인가?”를 출처와 함께 조회한다.
[pending.rq](../../ontology/queries/hswm_work_closeout_2026-09-29/pending.rq)는
“통합 API, 효능, 옛 대표 정의에서 남은 것은 무엇인가?”를 조회한다.
[SHACL](../../ontology/queries/hswm_work_closeout_2026-09-29/closeout-shapes.ttl)은
기록 완료를 시스템 완료로 바꾸거나 미구현 API를 구현 완료로 바꾸는 오류를 거절한다.
조회는 개수뿐 아니라 예상 UID·상태·source를 대조한다.

이번 검증과 라이브 게시 내역은
[validation](artifacts/hswm_work_closeout_2026-09-29/validation.v1.json)과
[publication](artifacts/hswm_work_closeout_2026-09-29/publication.v1.json)에 둔다.
외부 KG 게시에는 기존 owner publisher를 사용하고, 기존 두 노트와 HSWM 개념을 연결한다.
이는 전체 로컬 bundle의 복제나 사용자 정전 승격이 아니다.

## 이후 재개 지점

다음 구현 지점은 기존 key/schema를 쓰는 bounded read facade, 기존 실행·관측·revision
API의 통합, 필요한 외부 AI adapter 순서다. 별도 문자열 query 언어와 자연어 변환은
같은 동작 계약 위에 연결한다. 이 목록은 후속 작업으로 남기며, 이번 마무리 작업에서
runtime 코드를 추가하거나 개발 범위를 확대하지 않는다.
