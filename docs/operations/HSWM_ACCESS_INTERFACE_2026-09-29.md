# HSWM 접근 인터페이스 — AI 직접 호출과 자연어 입력

2026-09-29. [사용자 질문](../canon/sources/USER_PRIMARY_HSWM_ACCESS_QUESTION_2026-09-29.txt)에 대한
`SECONDARY_AI / PROPOSED_DESIGN` 제안이다. 아래 API 이름·개발 순서는 사용자 확정 지시나
이미 구현된 통일 인터페이스로 취급하지 않는다.

## 보존할 방향

**그래프가 AI의 지속 상태와 프로그램이고, TS/Effect는 그 내용을 해석하는 버전 있는 실행기다.**
학습은 그래프 revision을 바꾸며, 실행기 기능을 개발·수정하는 일과 구별한다.
이 기준을 [AGENTS.md](../../AGENTS.md)에도 명시했다.
[9월 28일 방향 정정](../research/HSWM_GRAPH_PROGRAM_DIRECTION_2026-09-28.md)의 라이브 노트
`sym:Note:chatgpt-hswm-graph-program-direction-20260928`를 다시 읽어 description SHA-256
`4d6772400c4ba78afddf0bcc175def6c478f60d0bcdd1aafcc3f933a27feb02a`가 이전 게시와 일치함을 확인했다.
정정 노트는 SECONDARY_AI이며, 옛 대표 `sym:Concept:hswm` 본문을 덮어쓴 상태는 아니다.

## 권장 인터페이스

먼저 **조회·실행·관측·수정의 입력과 결과가 뜻하는 바**를 정한다. AI와 개발자는 이를
typed API로 직접 호출하고, 사람의 자연어 요청도 같은 API로 변환한다. 자연어 변환을
모든 호출의 필수 단계로 두지 않는다. 별도 문자열 언어가 필요해지면 같은 요청 구조를
생성하는 문법으로 추가한다. JSON은 이 구조의 직렬화이며 실행 의미 자체는 계약이 정한다.
이 구조화된 요청이 최초의 기계용 문법이다. AI 직접 호출도 명시된 입력 형식을 따르며,
매번 자연어를 별도 문자열 query로 번역할 필요가 없다는 뜻이다.

| 사용 주체/목적 | 권장 입구 | 역할 |
| --- | --- | --- |
| 내부 LLM·외부 AI | schema가 있는 tool call 또는 구조화된 요청 | 대상·문맥·예산을 지정해 직접 읽거나 실행한다. |
| TS 프로그램 | typed SDK + Effect service | 같은 요청과 실행 의미를 사용한다. |
| 사람의 자연어 질문 | 자연어 → 구조화된 요청 후보 → 검증 → 같은 API | 의미 해석을 담당한다. 검사 후 정상 요청은 자동 실행하며 새 수동 승인 절차를 만들지 않는다. |
| 연구·운영 분석 | 기존 SPARQL 및 선택적 Neo4j/Cypher projection | 저장된 구조·출처를 조회한다. canonical 수정 경로와 구별한다. |

DB처럼 영속성·정확한 버전·참조·일관성을 제공하면서, 국소 LLM 실행과 outcome 학습도
호출할 수 있어야 한다. HSWM 전체 정체성은 [하나의 AI](../canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md)다.
Neo4j 채택, 프로세스 분리, MCP 제공은 배포·저장·전송 선택이다. 우선 기존 embedded
TS/Effect API에 얇은 접근 계층을 두고, 실제 외부 호출 요구에 맞춰 MCP/HTTP를 연결한다.
HSWM 내부의 모든 국소 연산을 MCP 왕복으로 만들 필요는 없다.

## 먼저 정할 동작 계약

아래 이름은 제안이며 `runSemanticProgram` 이외의 통일 facade는 아직 구현하지 않았다.

| 동작 | 최소 계약 | 기존 연결점 |
| --- | --- | --- |
| `read` | schema·lineage 안의 정확한 atom key 또는 명시적 current 선택, 관계/역할 조건, node·byte 예산. 결과에 resolved revision·순서 있는 incidence·근거·완전/부분 결과를 표시한다. | `CanonicalAtomV2DurableGraphView`, `readLlmSemanticFrame` |
| `run` | 선택한 program·입력·host budget을 고정하고 국소 LLM 연산을 실행한다. 결과에 program/read revision·trace·실행 비용을 결속한다. | `runSemanticProgram`, `executeLlmSemanticRelation`; 현재 program API는 입력 event가 step content 안에 있다. |
| `observe` | 실행 trace와 외부 관측 outcome을 연결한다. 사용자 평가·모델 추정·환경 관측의 출처를 구별한다. | `stageLlmSemanticOutcome` |
| `revise` | base revision·변경 후보·근거를 받아 기존 schema/owner/CAS/admission 경로로 처리한다. 단순 저장과 outcome-bound learning의 지위를 구별한다. | `prepareLlmSemanticRelationRevision`, `learnLlmSemanticRelation` |

읽기 결과가 비어 있는 것과 예산 때문에 검색이 덜 끝난 것은 다르다. 찾은 후보·추정 관계와
이미 저장된 assertion도 구별한다. n항 관계의 UID·역할·순서·문맥·예외를 유지하고,
관련 부분만 국소 입력으로 전달한다. 전체 그래프를 매번 prompt에 넣지 않는다.
호출자는 host가 발급한 접근 범위를 사용하며 요청 JSON이 스스로 권한을 만드는 것은 아니다.

자연어 예: “이 관측과 관련된 이전 예측과 예외를 찾아줘”를 제한된 `read` 조건으로 변환한다.
AI는 같은 조건을 곧바로 구성할 수 있다. “이 관측으로 다음 예측을 바꿔줘”는 별도 실행·학습
동작이며 조회 결과가 암묵적으로 graph write를 일으키지 않는다. 구조 검사는 요청 형식을
검증할 뿐 자연어 해석의 정확성을 증명하지 않으므로, 반환값에 해석한 조건을 함께 둔다.

## 현재 코드와 공식 자료의 근거

- [durable runtime](../../src/hswm/effect-runtime/src/canonical-atom-v2-durable-runtime.ts)은
  public graph view와 submit 경로를 구별한다. snapshot에서 시작할 수 있으나 사용자용
  범위·예산·부분 결과 계약을 갖춘 통일 query facade는 추가해야 한다.
- [semantic runtime](../../src/hswm/effect-runtime/src/canonical-atom-v2-llm-semantic-runtime.ts)과
  [graph program 실행기](../../src/hswm/effect-runtime/src/canonical-atom-v2-semantic-program-runtime.ts)를 재사용한다.
  현재 program은 최대 16개 예측 step의 순차 실행이며 일반 scheduler는 아니다.
- [기존 SPARQL](../../src/hswm/effect-runtime/src/native-kg-standards.ts)은 KG projection의
  local SELECT/ASK를 제공한다. [Neo4j adapter](../../src/hswm/effect-runtime/src/canonical-atom-v2-neo4j-projection.ts)는
  현재 verified projection을 게시하며 canonical atom을 수정하지 않는다.
- [MCP Tools 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)는
  이름·inputSchema가 있는 모델 호출과 structuredContent/outputSchema를 정의한다.
  이를 외부 AI용 adapter의 참조로 사용한다. 현재 HSWM MCP facade 구현 완료를 주장하지 않는다.
- [Cypher 공식 설명](https://neo4j.com/docs/cypher-manual/current/introduction/)은 property graph의
  선언적 조회 언어를 다룬다. 조회 언어·DB 사용성과 HSWM 전체 인지 동역학은 다른 설계 층이다.
- Hyperon `hyperon-experimental v0.2.10`, commit `3f76dc460da6961f57f69f6c3e550c59c74ada83`의
  [minimal MeTTa 명세](https://raw.githubusercontent.com/trueagi-io/hyperon-experimental/3f76dc460da6961f57f69f6c3e550c59c74ada83/docs/minimal-metta.md)는
  AtomSpace·binding·atom 평가의 관계를 명시한다. 그래프 조회와 실행 언어를 함께 생각할
  직접 선행이다. 이 문서는 최종 명세가 아니며 [기존 성숙도 구분](../research/HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)을 유지한다.

공식 원문은 [source captures](artifacts/hswm_access_interface_2026-09-29/source-captures.v1.json),
라이브 정정 확인과 새 설계 노트의 게시·readback은
[publication](artifacts/hswm_access_interface_2026-09-29/publication.v1.json)에 남긴다.
이 기록은 인터페이스 제안이며 새 runtime·Lean 증명·모델 효능 결과가 아니다.

## 개발 순서

1. 기존 schema와 key를 사용하는 bounded `read` 요청/결과 계약과 typed facade를 구현한다.
2. 기존 program 실행·outcome·revision API를 같은 접근 계층에 연결하고 구조화된 호출 예를 만든다.
3. 외부 AI에 필요한 MCP adapter와 사람에게 필요한 자연어 변환을 그 위에 붙인다.
4. 반복 사용에서 구조화된 요청이 불편하다는 근거가 생기면 문자열 DSL 문법을 검토한다.
