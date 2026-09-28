# 세 철학의 연산적 증명과 HSWM의 다음 실행 연결

2026-09-28 · `SECONDARY_AI_BOUNDED_FORMAL_RESULT_AND_ENGINEERING_IMPLEMENTATION`

[사용자 요청](../canon/sources/USER_PRIMARY_HSWM_PHILOSOPHY_COMPLETION_REQUEST_2026-09-28.txt)은 철학을 증명하고 HSWM을 완성하라는 것이다. **이번에는 실모델 실험 없이, 층 매핑의 필요·충분 조건, 관측 행동에 필요한 최소 구분, 실행되는 의미 그래프의 저장 변환을 Lean으로 증명한다.** 기존 [세 철학의 유한 번역](HSWM_THREE_PHILOSOPHIES_LEAN_2026-09-27.md)에서 일반적인 연산 계약으로 나아간다. 아래 수학적 번역은 사용자 원문을 바꾸거나 철학 전체의 참을 선언하지 않는다.

대상은 [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 token-native LLM-function macro-neural network다. 큰 Semantic Weight 그래프가 AI 상태이고 국소 LLM 연산이 그 상태를 읽고 바꾼다. living harness·world/self model·continuous learner는 같은 AI의 역할이다. CHU는 [HSWM보다 넓은 개념](../canon/USER_PRIMARY_CHU_HSWM_SOFTWARE_SCOPE_2026-09-27.md)이며, 여기의 유한 저장 형식과 동일하지 않다.

## 1. 양파껍질과 M = Map: 어느 층에서 시작해도 되는 조건

미시 상태 S를 국소 또는 상위 층 L로 보내는 q를 둔다. 같은 q 값으로 묶인 상태들을 q의 fibre라 한다. [OperationalAbstraction](../../formal/HSWMOperationalAbstraction.lean)은 다음 조건을 검사한다.

- 같은 fibre의 상태는 각 Step·Learn의 허용 여부가 같다.
- 허용된 Step의 출력과 다음 q 상태가 같다.
- 허용된 Learn 뒤의 q 상태가 같다.

각 L에 대한 실제 대표 상태를 주고 q(rep(l))=l임을 보이면, **같은 출력 타입과 항등 출력 매핑 아래에서** 위 조건은 출력·허용성·Step·Learn을 보존하는 층 연산이 존재할 필요·충분 조건이다. 충분성에서는 그 연산을 representative에서 직접 구성한다. 필요성은 이미 구성한 연산에만 의존하지 않고 임의의 정확한 층 연산에 적용된다. 다음 동치는 이 representative/retraction 가정을 포함하며, 서로 다른 출력 타입 사이의 임의 번역까지 증명한 것은 아니다.

```math
\mathrm{FibreCriterion}(S,q)
\quad\Longleftrightarrow\quad
\exists D_L:\mathrm{ExactRefinement}(D_S,D_L,q,\mathrm{id}).
```

이것은 같은 상태를 미리 맞다고 정의하는 정리가 아니다. 출력뿐 아니라 갱신과 허용성에 대한 구체적인 국소 등식을 만족해야 한다. 그 조건에서 **임의 길이의 유한 실행·학습 이력**을 보존한다. 기존 refinement 합성 정리로 호환되는 층 변환을 이어 붙일 수 있다.

물리·시냅스를 반드시 모두 재현해야 한다는 결론은 나오지 않는다. 필요한 구분을 보존하는 표현이라면 그 층에서 연산을 구성할 수 있다. 반대로 특정 현실 문제에서 작은 read가 충분하다거나, 실제 물리→의미 매핑을 발견했다는 결과도 아니다. ‘최외각’은 기존 원전대로 현재 모델링 경계에 상대적인 역할이며 절대적인 최종 우주 층을 증명하지 않는다.

## 2. 최소 비용 직관: 먼저 최소 정보와 저장 비용을 구별한다

[BehavioralMinimality](../../formal/HSWMBehavioralMinimality.lean)는 모든 유한 Step/Learn 이력의 출력이 같은 상태들을 하나의 행동 동치류로 묶는다. 여기의 정확한 encoding은 명시한 decode로 source 상태를 재구성한 뒤 모든 유한 출력 이력을 재현하는 encode/decode 쌍이다. 그런 encoding은 이 동치류보다 더 적은 행동 구분만 남길 수 없다. encoding의 도달 가능한 값에서 행동 동치류로 가는 사상이 존재하고, 그 사상은 전사이며 원본과의 대응을 만족하는 유일한 사상이다.

```math
q_{\mathrm{behavior}}=f\circ\mathrm{encode}_{\mathrm{reachable}}.
```

식의 encode는 도달 가능한 값의 subtype으로 향하며, f의 유일성은 이 원본 대응식을 만족하는 사상들 사이에서 성립한다. 이것은 **선언한 관측 계약 아래의 정보 구분 최소성**이다. byte 수·token 수·추론 시간·학습 비용의 최적성과 같지 않다. 동치류는 수학적으로 정의했으며 모든 무한 상태계에서 이를 계산하는 최소화 알고리즘을 만든 것이 아니다. 이 관점은 미래 suffix에 대한 구분으로 상태를 구성하는 [Mathlib의 Myhill–Nerode 형식화](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Computability/MyhillNerode.html)와 연결되는 해석이다. 해당 언어 정리를 그대로 HSWM에 적용했다고 주장하지 않는다.

관측 범위도 중요하다. 이 quotient는 `run`의 출력만 본다. **허용·거부 guard가 달라도 출력이 모두 같은 반례**를 같이 증명했다. 따라서 이를 canonical permission·provenance·lineage까지 보존하는 압축으로 사용하면 안 된다. 그런 항목을 줄이려면 먼저 관측 계약에 포함하고 보존 정리를 다시 세워야 한다. 1절의 강한 fibre 조건과 2절의 출력 동치를 같은 것으로 부르지 않는다.

‘하이퍼그래프가 어떤 비용 기준에서도 항상 가장 싸다’는 명제는 기존 [양방향 비용 반례](../../formal/HSWMHypergraphCostConditions.lean) 때문에 증명할 수 없다. 사용자 최소비용 가설은 유지하되, **무엇을 보존하고 어떤 비용을 최소화하는가**를 정해야 한다. 손실 없는 binary incidence 구현도 가능한 이상 특정 DB나 외형이 유일한 최소 표현이라는 결론도 나오지 않는다.

## 3. 소프트웨어 철학: 저장 표현을 바꿔도 같은 실행·학습을 한다

[ExecutableGraphEncoding](../../formal/HSWMExecutableGraphEncoding.lean)은 임의의 유한 관계 수, 관계별 arity, payload·역할·참여자 타입을 명시적으로 받는다. hyperedge family를 factor payload·role label·endpoint로 분해하며, 두 방향 왕복을 증명한다. 전체 원본 관계를 payload 하나에 숨기는 encoding은 아니다.

더 나아가 원래 그래프의 Step·Learn·허용성에서 incidence 표현의 연산을 **직접 구성**한다. 두 방향 refinement와 모든 유한 실행·학습 이력의 동일성을 증명한다. 따라서 의미 프로그램·역할·상태를 보존하는 저장 변환은 같은 소프트웨어 동작을 실현할 수 있다. relation arity와 주소는 이 계약 안에서 고정돼 있으며 열린 topology 생성까지 포괄하지 않는다.

기존 grammar-generated 의미 프로그램을 incidence 형태에 실제로 넣고, 같은 국소 reference interpreter가 읽는 예도 연결했다. outcome으로 계산한 관계 수정이 다음 출력에서 true→false의 차이를 만드는 기존 결과가 그 저장 표현에서도 성립한다. 이는 정확한 참조 인터프리터다. 실제 pretrained LLM이 같은 의미론을 얼마나 충실하게 실행하는지는 이 정리의 결론이 아니다.

### 이전 일반성 설명의 정정

기존 `HSWMHypergraphRepresentation.encodeNary`, `decodeNary`, `decode_encodeNary`는 payload와 유한 arity에는 일반적이지만, 실제 elaborated type의 Role·Vertex는 해당 모듈의 **고정 enum**이었다. generic 구조체와 unqualified 이름을 혼동해 이전 문서에서 역할·참여자 타입까지 일반적이라고 설명한 부분은 과도했다. 기존 고정 domain 정리와 반례는 유효하다.

이번 파일은 `{Payload Tag Endpoint : Type}`를 명시적으로 bind한 별도 codec으로 이 간극을 해결한다. 이전 source·receipt·문서의 바이트를 소급 변경하지 않는다. 새로운 일반화와 이 정정 기록을 현재 해석에 적용한다.

## 4. 증명과 실행 구현 사이의 연결

[선택된 의미 상태 API](../../src/hswm/effect-runtime/src/canonical-atom-v2-semantic-selected-state.ts)는 기존 TS/Effect graph runtime에서 선택한 durable branch를 다시 열고 다음 의미 실행에 연결한다. 순수한 기존 bigint 선택 함수와 Effect I/O를 사용하며 새로운 전역 가변 상태를 만들지 않는다.

- `selectFrozenSemanticDurableCandidate`는 평가 입력을 복사하고, baseline/candidate의 실제 canonical state와 의미 frame에서 결속값을 읽는다. candidate의 relation UID·schema·lineage·owner, 정확한 predecessor, 순서가 있는 role/type/key/owner/content hash, 기대한 training trace/outcome digest를 검사한다.
- 선택 기록은 양쪽 graph binding과 평가 입력 digest를 함께 남긴다. `reopenSelectedSemanticBranch`는 원래 round로 선택을 다시 계산하고 기록 전체를 비교한 뒤, 제공된 opener로 선택한 branch를 새로 열어 다시 검사한다. 통과한 runtime으로 다음 실행을 호출한다.
- 이 API는 library의 명시적 호출 경로다. 전역 canonical branch 전환이나 기존 lifecycle CLI의 기본 경로 변경은 아니다. candidate revision의 기존 admission 경로를 재사용하며 선택 기록을 Permit으로 취급하지 않는다.
- 양쪽 root와 다음 실행까지의 상태를 고정해 두는 것은 호출자의 조건이다. 입력 복사와 읽기 전후 상태 검사는 있지만, 여러 root/process를 묶는 transaction·lock은 없다. opener와 runtime은 호출자가 제공하는 서비스다.

[실제 파일 저장소를 사용하는 통합 검사](../../tests/effect-runtime/canonical-atom-v2-semantic-selected-state.test.ts)는 fixture 응답으로 허용된 의미 revision을 만든 뒤, candidate 선택 시 새 runtime의 다음 실행이 revision 1을 읽고 fallback 시 revision 0을 읽는지 확인한다. 잘못된 선택 기록·변경된 상태·평가 입력·훈련 receipt를 거절하는 검사도 포함한다. 이것은 미리 정한 transport fixture이며 실모델 학습 실험이 아니다.

평가 row·prediction·오염 허용량·비용은 호출자가 선언한다. 저장된 training receipt와 선택 입력을 결속해도 평가의 독립성이나 실제 성능을 인증하지 않는다. [직전 통계 증명](HSWM_FRESH_EVALUATION_LEAN_PROOF_2026-09-28.md)의 실수 confidence bound를 이 bigint guard가 자동 구현한다고 주장하지 않는다.

Lean 정리는 mathematical semantics를 검사하고, TypeScript transport 검사는 그 구현의 특정 계약을 검사한다. 둘을 함께 기록하더라도 TypeScript compiler·파일시스템·HTTP·pretrained LLM 전체의 refinement proof가 완성되는 것은 아니다. 기록된 평가값과 비용의 진위도 별도 의무다.

원문·증명·구현·음성 결과 사이의 관계는 [source-bound KG snapshot](../../ontology/development/HSWM_OPERATIONAL_PHILOSOPHY_PROOF_2026-09-28.v1.json)에 투영한다. 이는 저장소의 연구 탐색 기록이며 live KG 쓰기나 HSWM의 인지 상태가 아니다.

## 5. HSWM 완성 여부

**이번 결과로 HSWM 전체를 완성했다고 선언할 수 없다.** 목표를 작은 quotient·그래프 저장소·선택기로 바꾸지도 않는다. 새 증명은 CR-0/5/6의 일부 연산 계약에 연결되지만, 하나의 같은 구성에서 실제 LLM 실행·유용한 학습·인과 credit·변수/관계 발견·world/self·lineage·재귀 합성이 함께 성립한다는 CR-0..7과 FCL-1..8은 미완료다.

이미 [실제 의미 학습에서 개선이 없었던 결과](../../results/HSWM_DGX_SEMANTIC_LEARNING_2026-09-20.md)와 [JEV 한계](../../results/HSWM_JEV_PRINCIPLES_2026-09-21.md)는 유지한다. 이번 작업에는 새 실모델 호출이 없다. 구조·프로그램 검증을 실험 성능이나 인지 효능으로 바꾸지 않는다. Hyperon은 [고정 버전과 성숙도에 따른 필수 비교 대상](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)으로 계속 남는다.

증명 검사는 [Lean 공식 검증 지침](https://lean-lang.org/doc/reference/latest/ValidatingProofs/)에 따라 exact source를 새 import 디렉터리에서 컴파일하고 각 정리의 공리를 확인한다. 최종 fresh compile은 의존성 포함 **16개 모듈**, 새 정리 **27개**(층 조건 6·행동 최소성 13·실행 저장 변환 8)에서 통과했다. 새 정리의 공리 집합에는 `propext`, `Quot.sound`만 나타났고 `sorry`, 새 axiom, `native_decide`는 없다. 명제의 커널 검증과 그 명제가 사용자의 철학 또는 현실을 충분히 뜻하는지는 별개다. [재현 방법](../../_research/operational_philosophy_proof_v1/README.md)과 [정리별 기록](../../_research/operational_philosophy_proof_v1/lean-verification.v1.json)에 도구·source hash·검증 범위를 둔다.
