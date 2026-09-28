# 그래프 안의 프로그램과 고정 실행기 — 방향 재점검

2026-09-28. [사용자 질문·수정 요청](../canon/sources/USER_PRIMARY_HSWM_GRAPH_PROGRAM_CLARIFICATION_2026-09-28.txt)을
기존 [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md),
[상태·국소 연산자 정의](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md),
[CHU 소프트웨어 방향](../canon/USER_PRIMARY_CHU_HSWM_SOFTWARE_SCOPE_2026-09-27.md)과 대조했다.
사용자 발화는 `USER_PRIMARY` 출처이며 아래 세부 구현·감사 판정은 `SECONDARY_AI`다.
질문에 등장한 DB/FSM 비유를 새 고정 subsystem 분해로 승격하지 않는다.

## 1. 바로잡는 설명

**HSWM의 학습은 canonical graph 안의 의미·관계·프로그램을 revision하는 일이다.
학습마다 TypeScript 소스파일을 편집하고 재컴파일하는 것이 아니다.**
TS/Effect가 정본이라는 말은 실행기 구현의 기준이다. AI의 지속 상태가 TS 소스라는 뜻이 아니다.
실행기를 개발·고치는 일과 실행 중 graph state/program을 바꾸는 일을 구별한다.
실행기는 한 실행 버전 범위에서 고정돼 있어도 다른 graph program을 해석할 수 있다.

| 대상 | 의미와 갱신 경로 |
| --- | --- |
| canonical hypergraph | schema·owner·revision·typed reference 아래의 AI 상태. 실행에 쓰는 프로그램도 atom으로 표현할 수 있다. |
| Semantic Weight·program | LLM이 해석하는 의미·역할·문맥·예외와 실행 계약. outcome에 결속된 revision이 다음 실행을 바꾼다. |
| TS/Effect 실행기 | graph에서 프로그램과 입력을 읽고 허용된 연산자를 호출하며 검증·저장 I/O를 수행한다. 엔진 개발과 학습을 구별한다. |
| FSM | 실행 단계·전이를 기술하는 방식. 연구용 고정 control FSM과 그래프에 선언된 변경 가능한 동작을 구별한다. |
| JSON | schema가 정한 데이터의 직렬화. 문자열 존재만으로 실행 의미나 실행 권한을 얻지 않는다. |
| RDF·저장소 KG·라이브 연구 KG | 설명·조회·교환용 projection과 연구 기록. 실행 중 canonical AI state에 쓰는 암묵적 경로가 아니다. |

현재 semantic runtime도 graph relation을 읽고 successor atom을 만든다.
이 기존 동작은 사용자 방향과 일치한다. 최근 설명의 “TS/Effect의 수정”은 graph revision과
실행기 개발을 혼동하게 했고, “HSWM 전체 TS를 증명한다”는 표현은 목표를 너무 넓혔다.
Lean의 구체적인 연결 목표는 **고정 interpreter가 graph-resident program과 상태 전이를
명세대로 해석하는가**다.

## 2. 문서·KG 감사 결과

| 확인 대상 | 판정 | 조치 |
| --- | --- | --- |
| 헌법·9월 14일 상태 정의 | executable contract도 canonical atom이며 graph가 AI state라고 명시한다. 학습을 TS 소스 편집으로 정의하지 않는다. | 원문과 기존 hash를 보존한다. |
| [구현 아키텍처](HSWM_IMPLEMENTABLE_ARCHITECTURE_2026-09-27.md)·[CHU 실행 계약](CHU_HSWM_COMPUTATIONAL_ARCHITECTURE_2026-09-27.md) | 상태/실행 의미/실행기를 구별하며 범용 scheduler가 설계 단계임을 명시한다. | 당시 미구현 기록은 유지하고 이 후속 구현을 연결한다. |
| [최근 Lean 검토](HSWM_LEAN_VALIDATION_REVIEW_2026-09-28.md)와 그 KG | 조건부 모델·TS adapter·효능의 경계는 맞다. 다음 증명의 초점은 graph program 해석으로 더 분명하게 적어야 한다. | 이전 bytes를 덮어쓰지 않고 이 해석 정정을 연결한다. |
| 라이브 `sym:Concept:hswm`의 `definition` | 2026-08-20 version에 폐기된 `H/W/A/F`와 `Pi`가 남아 있다. USER_PRIMARY label만으로 최신 사용자 원문과 일치한다고 볼 수 없다. | 8월 26일의 [폐기 원문·정의](../canon/USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.md)를 출처로 정정 노트를 연결한다. 기존 canonical 레코드는 현재 writer가 덮어쓸 수 없다. |
| 라이브 CHU 범위·실행 계약 노트 | 정확한 UID로 조회한 전체 description은 이전 게시 hash와 일치한다. 일반 검색에서 `chatgpt-` UID prefix를 name처럼 사용하면 찾지 못했지만 기록은 존재한다. | 삭제·누락으로 판정하지 않는다. 기존 방향을 이어받는다. |

라이브 감사는 HSWM 대표 record, CHU 범위·실행 계약 노트와 직접 연결된 claim history를
읽은 한정된 검사다. 전체 외부 KG의 무오류를 주장하지 않는다. 상세 readback은
[`live-audit.v1.json`](../../_research/graph_program_direction_2026-09-28/live-audit.v1.json)에 보존한다.
정정 노트와 관계는 writer의 `SECONDARY_AI / PENDING_OR_PRELIMINARY` 규칙을 따른다.
이는 사용자 승인이 필요한 새 개발 gate가 아니라 해당 저장 도구의 기록 분류다.

## 3. 최소 실행 연결

일반 CHU VM을 새로 만드는 대신 기존 canonical atom runtime과 LLM 의미 실행을 재사용한다.
버전 있는 `semantic_program` atom에 순서 있는 국소 실행 선언을 저장하고,
고정 TS/Effect interpreter가 그 순서와 typed relation reference를 읽는다.
프로그램 revision으로 호출 순서를 바꾸면 같은 엔진이 달라진 순서를 실행해야 한다.

실행 program은 기존 schema가 허용한 atom kind, 한 owner, LINEAR predecessor,
정확한 target revision과 content digest를 따른다. 프로그램이 요구하는 kernel 이름은
호스트가 제공한 capability에서 해석한다. endpoint·credential·admission 권한을
그래프 데이터에서 임의로 만들어내지 않는다. host budget, schema와 CAS도 유지한다.

이 작은 profile은 ordered LLM invocation을 위한 공학적 구현이다. 분기·반복·병렬 스케줄링,
outcome에 의한 자율 program synthesis, CHU 전체 실행기의 완성을 주장하지 않는다.
프로그램을 수동 revision해 동작이 바뀐다는 검사는 graph-driven execution의 증거이며
LLM이 좋은 프로그램을 학습했다는 증거가 아니다.

### 구현과 사용 경계

[`canonical-atom-v2-semantic-program.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-semantic-program.ts)는
UTF-8 JSON·중복 키·32 KiB 상한·최대 16 step·opcode·정확한 현재 target revision을 검사하는
순수 domain 함수다. `semantic_program`의 content 예시는 다음과 같다.

```json
{
  "contract": "hswm-semantic-program/v1",
  "steps": [
    {"role": "a", "event": "event:a", "kernelId": "kernel:local", "opcode": "LLM_SEMANTIC_PREDICT_V1"},
    {"role": "b", "event": "event:b", "kernelId": "kernel:local", "opcode": "LLM_SEMANTIC_PREDICT_V1"}
  ]
}
```

atom의 `hswm:semantic-program:target` reference 배열도 같은 `a`, `b` 순서여야 하며
각각 정확한 `semantic_relation` key를 가리킨다. predecessor reference는 별도로 보존한다.
schema에서 program kind·owner·LINEAR 정책·허용 role을 먼저 선언하고 기존 admission 경로로
저장해야 한다. 이 JSON만 저장하면 아무 기존 schema에서나 자동 실행된다는 뜻은 아니다.

[`canonical-atom-v2-semantic-program-runtime.ts`](../../src/hswm/effect-runtime/src/canonical-atom-v2-semantic-program-runtime.ts)의
`runSemanticProgram({ programUid, kernels, http, maximumSteps })`는 공개 package API로 연결했다.
기존 `CanonicalAtomV2DurableRuntime` Effect service를 제공하면 current program을 읽어
기존 `executeLlmSemanticRelation`을 호출한다. caller의 kernel binding은 함수 호출 시 복사한다.
매 호출 전과 마지막 응답 뒤 state revision과 program·target을 재검사한다.
검사 사이에 이미 실행한 모델 요청을 되돌리는 transaction은 아니며, 변경 감지 시 성공을
반환하지 않는다. 이 runner는 예측 trace만 staging하고 canonical state를 직접 commit하지 않는다.

[`실행 회귀 검사`](../../tests/effect-runtime/canonical-atom-v2-semantic-program.test.ts)는
실제 파일 기반 durable runtime에서 수동으로 승인한 v0 `A→B`와 v1 `B→A`를 재시작 후
같은 함수로 실행한다. kernel 객체 변경, unknown opcode, reference 순서 불일치,
stale target, 첫 호출 및 마지막 호출 중 graph drift도 검사했다.
새 검사 2개와 기존 의미 runtime·선택 상태 검사 11개, 합계 **13개가 통과**했다.
HTTP 응답은 작성된 fixture다. 실제 LLM 호출·효능 측정·program 학습은 수행하지 않았다.

## 4. 표준 그래프 공학과 Lean 연결

RDF 1.1·SHACL 1.0·SPARQL 1.1·JSON-LD 1.1·PROV-O의 기존 도구를 유지한다.
프로그램·호출·대상 관계는 안정된 식별자와 명시적 역할·순서·revision을 가진다.
RDF로 내보낼 때 프로그램의 n항 관계와 ordered step을 무순서 pair edge로 축약하지 않는다.
[W3C n-ary relation Note](https://www.w3.org/TR/swbp-n-aryRelations/)의 relation instance와
ordered argument 패턴을 따른다. 이 Note는 실행 언어 표준이 아니다.

[W3C SCXML](https://www.w3.org/TR/scxml/)도 상태·전이 선언과 interpreter의 실행 의미를
구별하는 참조 사례다. 이번 profile은 SCXML 구현·준수 선언이 아니며 XML engine이나
새 graph backend를 도입하지 않는다. 새로운 HSWM program vocabulary는 local schema다.
두 W3C 원문은 내려받아 본문 SHA-256·크기를 재검사했으며
[`source-captures.v1.json`](../../_research/graph_program_direction_2026-09-28/source-captures.v1.json)에 고정했다.

기존 [stored program 정리](../../formal/HSWMExecutableGraphEncoding.lean)의
`storeProgram`/`executeStored`와 [의미 그래프 정리](../../formal/HSWMLLMSemanticGraph.lean)의
current relation 실행·revision 후 재읽기가 이미 이 방향을 모델링한다. 이 정리들은
유한 모형과 추상 interpreter에 대한 것이며 새 TS program 구현의 증명으로 전용하지 않는다.
다음 대응은 decoded program·read-set·실행 결과를 한 명세로 묶고, 고정 interpreter의
행동이 이를 보존함을 보이는 것이다. 소스코드 자기수정을 증명 대상으로 삼지 않는다.

Hyperon 비교는 `hyperon-experimental v0.2.10`, commit
`3f76dc460da6961f57f69f6c3e550c59c74ada83`의 MeTTa/AtomSpace 경로와 기존
[성숙도 구분](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)을 유지한다.
graph에 프로그램을 두는 발상 자체를 HSWM의 최초 발명으로 주장하지 않는다.
이번에는 비교 benchmark·Hyperon 채택·새 효능 평가를 수행하지 않는다.

## 5. 재현과 게시 기록

검증 명령·결과는 [`verification.v1.json`](../../_research/graph_program_direction_2026-09-28/verification.v1.json),
라이브 정정 노트의 원문·readback·관계 상태는
[`publication.v1.json`](../../_research/graph_program_direction_2026-09-28/publication.v1.json)에 기록한다.
저장소의 [출처 결속 KG](../../ontology/development/HSWM_GRAPH_PROGRAM_DIRECTION_2026-09-28.v1.json)는
사용자 원문과 AI 해석, 실행기·프로그램·projection·과거 분해·구현 범위를 구별한다.
[SPARQL](../../ontology/queries/hswm_graph_program_direction_2026-09-28/direction.rq)과
[SHACL](../../ontology/queries/hswm_graph_program_direction_2026-09-28/direction-shapes.ttl)을
기존 graph tooling으로 실행한다. 과거 증명·실험 hash, 음성 결과, CR-0..7/FCL-1..8와
프랙탈 목표는 보존하며 이번 구현에 대한 새 Lean refinement 증명을 주장하지 않는다.
