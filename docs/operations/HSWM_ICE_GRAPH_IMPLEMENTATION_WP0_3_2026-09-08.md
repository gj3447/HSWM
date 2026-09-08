# ICE 그래프 구현 WP0–3 — 부모 조건 보존과 선택 관측

2026-09-08 · `SECONDARY_AI / IMPLEMENTED_LOCAL_ENGINEERING / EFFICACY_UNJUDGED`.

이 문서는 [ICE 표준 그래프 작업 계획](HSWM_ICE_STANDARD_GRAPH_WORK_PLAN_2026-09-08.md)의 첫
작업 묶음에 실제로 들어간 local TypeScript/Effect 변경을 설명한다. HSWM의 target identity,
기존 실패 기록, 과학 gate 및 canonical admission은 바꾸지 않는다. 이 구현은 local SQLite atom과
실행 관측을 다루며, 외부 KG/RDF 투영 또는 HSWM 인지 자체가 아니다.

검증 receipt와 실행 환경, source revision, 검사 결과는
[`artifacts/ice_graph_wp0_3_2026-09-08/verification.json`](artifacts/ice_graph_wp0_3_2026-09-08/verification.json)에
기록한다. 이 문서는 그 결과의 수나 효능 판정을 미리 주장하지 않는다.

## 개념적 변화와 범위

기존 local specialization은 learned selector로 route guard를 대체할 수 있었다. 이제 child의
effective guard는 부모의 필수 guard와 selector의 `all` 합성이다. 그러므로 selector가 TRUE여도
부모 guard가 FALSE 또는 UNKNOWN이면 child는 eligible이 아니다. child는 부모의 immutable
revision/digest와 의미 digest를 scope에 묶고, source·members와 부모 reads를 유지하고 selector에 필요한 reads를 추가한다.

동시에 각 planning/execution occurrence에 당시 후보, 탈락 사유, 결정 규칙, 선택 revision,
입력 digest, 참여 cell revision, 출력 digest 및 예산을 남긴다. 이는 선택과 실행의 provenance를
읽기 위한 최소 기록이며, delivered context가 실제 read였다는 증거나 score가 보정된 성공확률이라는
주장은 아니다.

이번 전달물은 다음만 포함한다.

| 작업 | 현재 local 구현 | 주장하지 않는 것 |
| --- | --- | --- |
| WP0 | versioned local payload, Q1–Q6 조회 계약, 교정 v2의 의미 연결·누락 근거·구형 추천을 판별하는 fixture | native atom의 canonical admission, 전체 외부 KG의 최신성 보장 |
| WP1 | 부모 guard + selector 합성, parent revision/digest binding, legacy child 보존·withhold | specialization의 효능 또는 canonical relation admission |
| WP2 | 후보/선택/occurrence/output/version/cost 관측, provider usage의 strict 형식 확인 | 실제 read 증명, 인과 credit, net utility 또는 token 비용 완전 측정 |
| WP3 | 두 route를 가진 local fixture와 CLI에서 route 지정 실행의 입력 표면 | 학습이 대안을 더 잘 선택한다는 결과 |

v1 learner의 모델 수식, feature update, proposal heuristic은 변경하지 않았다. WP4의 feature-count
민감도 완화와 version-aware learner 비교, WP5의 전체 stage-feedback API/idempotency, WP6의
질문·조회·행동 생성, WP7의 실사용 효능 평가는 후속 작업이다.

## 구현 경계와 계약

### 조건과 specialization

`src/hswm/effect-runtime/src/adaptive-domain.ts`의 순수 planner는 eligible 후보와 stable rejection
reason을 계산한다. 기본 선택은 score 내림차순 뒤 UID 오름차순이며, 허용된 `--route` 지정은
`FORCE_ELIGIBLE_ROUTE`로 별도 표기한다. `predicted_success`는 local model score에서 나온
비보정 값이다.

`src/hswm/effect-runtime/src/adaptive-observation.ts`는 parent revision pin과 `mandatory_guard`,
selector, effective guard를 scope payload로 만들고, `src/hswm/effect-runtime/src/adaptive-runtime.ts`는
그 payload를 재계산해 child의 UID, route 의미, parent 의미와 비교한다. current parent의 semantic
meaning이 달라지거나 inactive가 되면 child는 planner에서 withheld된다.

과거 scope가 없는 child는 `LEGACY_UNBOUND_SPECIALIZATION`으로 남기고 수정하지 않는다. 그것은
eligible하지 않지만, active이며 valid한 bound child만 새 specialization을 막으므로 부모의 후속
bound successor는 만들 수 있다. 이 보존 정책은 기존 child가 새 부모 의미에 자동으로 적합하다고
말하지 않는다.

### 관측, feedback, 비용

planning observation은 candidate revision, scope status, learner digest, 선택 조건과 deterministic
selection 표기를 남긴다. trajectory occurrence는 cell 및 선택 relation revision, member participant,
input/output digest, budget 잔여를 묶는다. caller feedback은 episode의 root occurrence와 그때의
selected relation pin을 확인한다.

선택 뒤 parent/route 의미나 scope가 달라지면 feedback outcome은 보존하되 `SELECTION_SCOPE_INVALID`
또는 `SELECTION_MEANING_CHANGED`로 model weight 갱신을 막는다. root occurrence에 과거 선택 revision pin이 없거나 현재 선택 관계의 scope가 무효이면 역시 갱신하지 않는다. 이는 interim manual `feedback` episode API의 보호이지,
각 단계 산출물에 binding된 full stage-feedback 계약은 아니다. UNKNOWN result, pending feedback,
stage별 outcome은 여전히 별도 평가 대상이다.

episode 비용은 실제 leaf occurrence의 duration을 한 번씩만 합산한다. router duration은 inclusive
wall time이며 leaf sum과 합치지 않는다. provider usage는 제공자가 보고한 nonnegative integer
token 합계만 `REPORTED`로 기록한다. 명령의 token 사용량은 추정하지 않는다. 사람 검토·수정,
재시도, monetary cost와 초기 통합비는 `null`/미측정으로 남는다.

executor의 tool identity는 command의 configured literal argv 또는 LLM endpoint/configuration의
digest다. binary version은 아직 관측하지 않아 `null`이다. executor metadata에는 environment 또는
API key를 넣지 않는다. 실행 원문은 local state에 남고 공개 KG에는 source-bound 요약을 게시한다.

## Q1–Q6 상태

| 질문 | WP0–3에서 가능한 답 | 상태와 남은 공백 |
| --- | --- | --- |
| Q1 왜 이 행동을 골랐나? | 후보 revision/scope, rejection, tie/selection rule, selected relation, context와 occurrence input digest | 부분 구현. 실제 read/source evidence는 `NOT_INSTRUMENTED` |
| Q2 어느 평가가 무엇을 바꿨나? | episode/root occurrence/selected relation pin과 feedback outcome, matching일 때의 local successor | 부분 구현. stage artifact별 평가·중복 review API는 WP5 |
| Q3 어떤 조건이 보존됐나? | parent pin, mandatory guard, selector, effective guard, members/reads | 부분 구현. local scope validation만 제공 |
| Q4 왜 다음 질문이 달라졌나? | 없음 | 미구현: WP6 |
| Q5 사용해 이득이 있었나? | leaf duration과 제한된 provider usage/미측정 cost slots | 미평가: 품질·총비용·효능은 WP7 |
| Q6 지금 읽을 설계는 어느 버전인가? | [교정 설계 v2](../../ontology/evidence/HSWM_ICE_LEARNING_REMEDIATION_2026-09-08.v2.json)의 문제→대안·반박 방향과 기본 query의 v2 지정을 검사 | 범위를 지정한 계약 검사. 전체 KG에 대한 자동 최신 추천은 아님 |

## 표준 및 projection 경계

새 외부 의존성은 추가하지 않았다. RDF 1.1/N-Quads 1.1은 versioned named-graph 교환에,
SHACL 1.0은 기존 projection의 shape 점검에, PROV-O는 source→activity→derived-view 계보 표기에,
SPARQL 1.1은 기존 local read-only query 범위에 계속 사용할 수 있다. 이 local JSON payload의 업무
의미를 W3C 표준이 정의하거나, SHACL 통과가 outcome truth·causal credit·효능을 증명하는 것은 아니다.

projection 전에 source revision, payload schema/version, owner, role-bearing references와 digest
binding을 검토한다. source가 변하면 기존 projection은 새 구현의 근거가 아니며 successor record로
정정한다. history를 현재 payload에 맞춰 다시 쓰지 않는다.

## 실행 표면과 작은 fixture

native CLI의 development 경로는 `hswm-dev <profile> plan|run|status|feedback`이고, route 지정은
`--route`다. `--route`는 execution feasibility 또는 fixture coverage를 위한 강제 eligible 선택이며
학습 선택 우위의 증거가 아니다. `hswm-live --program FILE graph`는 local runtime graph의 detail
JSON을 출력한다. `atoms[].payload.observation`, `atoms[].payload.plan`,
`atoms[].payload.cost_observation`, `events[]`에서 occurrence와 전후 revision을 조회한다.

[WP3 fixture](../../_research/causal_composition/ice_learning_choice_v1/README.md)는
작은 정수 명제의 기존 반례 검증과 새 반례 탐색을 두 순서로 수행한다. 같은 context, member allowlist, budget 아래 두 route가 모두 eligible한지를
먼저 검사한다. 두 route fixture CLI input은 필요할 때 `--route`로 각각 선택해 command boundary,
trace, output digest와 비용 slots를 확인할 수 있다. frozen과 learning state, workspace, episode와
independent review label을 섞지 않는다. 미선택 route의 효과는 관측되지 않은 값으로 둔다.

## 확인해야 할 불변식

- parent FALSE 또는 UNKNOWN이고 selector TRUE인 child는 선택되지 않는다.
- active bound child만 새 child 생성을 막는다. legacy child는 immutable history로 남고 planner에서
  withheld된다.
- parent semantic meaning 변경 뒤에는 old child feedback outcome을 저장해도 weight를 갱신하지 않는다.
- `predicted_success`를 calibration, `feedback`을 독립 causal credit, local active를 canonical
  admission으로 읽지 않는다.
- router inclusive time과 leaf execution time을 더하지 않고, missing cost를 zero로 바꾸지 않는다.
- provider가 보고하지 않은 usage, binary version, actual source read는 만들어 내지 않는다.

이 불변식의 source/fixture 검사와 결과는 위 verification artifact에 결속한다. 해당 기록이 완성되고
source pin과 graph semantics를 다시 대조하기 전에는 이 문서를 실사용 성능 향상 또는 HSWM 학습
성공의 증거로 사용하지 않는다.
