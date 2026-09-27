# 세 철학의 Lean4 번역: 보존, 표현 비용, 실행되는 의미 프로그램

2026-09-27 · `SECONDARY_AI_BOUNDED_FORMALIZATION`.

**세 철학에서 증명 가능한 계산적 명제와, 아직 세계에 대한 가설인 부분을 분리한다.**
이번 [사용자 요청](../canon/sources/USER_PRIMARY_THREE_PHILOSOPHIES_LEAN_REQUEST_2026-09-27.txt)은
세 철학의 증명을 요구한다. 아래 타입·비용 함수·참조 세계는 그 요청에 대한 AI의 명시적
수학적 번역이며 사용자 발화 자체나 전체 HSWM의 정의를 대체하지 않는다.

| 사용자 철학 | Lean에서 다루는 명제 | 남아 있는 원래 주장의 범위 |
| --- | --- | --- |
| 양파껍질 바깥의 세계 모델링, M = Map | 관측·허용성·전이·학습을 보존하는 층 매핑은 유한 실행 이력을 보존하며 합성된다. 정보를 버려도 충분한 경우와 실패하는 경우를 구성한다. | 실제 물리·뇌·의미 층에 맞는 매핑의 존재, 정확성, 절대 최외각 또는 전지성 |
| 하이퍼그래프가 세계 기술의 최소 비용 체계 | 역할 있는 n항 표현의 정확한 incidence 왕복, 선언한 두 저장 표현의 조건부 비용 우위·동률·반대 방향 반례 | 모든 표현·하드웨어·과제·비용에서의 보편 최적성, Transformer/ZFC/Wolfram에서의 필연적 수렴 |
| AI는 소프트웨어이며 의미 그래프가 프로그램·상태 | 국소 인터프리터가 그래프 프로그램을 실행하고, 실제로 계산한 관계 수정이 다음 출력과 유한 평가 점수를 바꾼다. 더 넓은 실행 가능한 모형에 의미 기계와 비신경 세계 모형을 함께 넣는다. | 실제 pretrained LLM의 정확한 실현, 전체 CHU의 계산가능성·구현, 문서와 인터넷 전체의 미래 형태 |

사용자 원전은 [M = Map](../canon/USER_PRIMARY_HSWM_CROSS_LAYER_MAP_2026-09-27.md),
[최소 비용 가설](../canon/USER_PRIMARY_HSWM_MINIMUM_COST_HYPERGRAPH_2026-09-27.md),
[CHU와 HSWM 소프트웨어 범위](../canon/USER_PRIMARY_CHU_HSWM_SOFTWARE_SCOPE_2026-09-27.md)다.
최소 비용 원전의 “셋째 미제시”는 당시 기록이며, 이후 추가된 소프트웨어 발화를 함께 읽는다.
기존 원전의 바이트나 권위를 소급 변경하지 않는다.

## 1. M = Map: 모든 세부 복원 대신 필요한 동작 보존

[HSWMMultiscaleSimulation.lean](../../formal/HSWMMultiscaleSimulation.lean)은 기존
[Step/Learn refinement](../../formal/HSWMSemanticQuotient.lean)를 구체적인 여러 표현 층에 적용한다.
`ExactRefinement`에는 관측 출력, 실행 허용성, 학습 허용성, Step과 Learn의 교환 조건이
모두 필요하다. 단순히 두 상태에 같은 이름을 붙이는 매핑은 그 계약을 만족하지 않는다.

`physicalSynapticSemantic_trace_preserved`는 그 매핑을 따라 임의의 유한 Step/Learn 이력을
옮겨도 출력과 최종 상태가 일치함을 증명한다. 작은 구성에서는 미시 상태의 불필요한 한
비트를 버려도 동작을 보존한다. 반대로 예측에 필요한 비트를 버리는 매핑은
`erasing_predictive_bit_fails`에서 실패한다. 파일의 physical/synaptic/semantic 이름은
이 계산 예제의 층 이름이며 실제 물리학·뇌의 구현을 뜻하지 않는다.

이 구성은 `CONSTRUCTED_FINITE_REFERENCE_MODEL`이다. 행동은 하나(`Unit`)이고,
모든 Step/Learn을 허용하며, 관측은 Boolean 하나다. Learn은 제공된 Boolean을
저장한다. 따라서 실제 물리·시냅스 자료에서 이 매핑을 발견했다는 결과는 아니다.

공학적으로는 매핑마다 입력 타입·출력 타입·보존할 관측과 Step/Learn을 명시하고, 관측이
달라야 하는 두 상태가 같은 local read로 합쳐지는지 확인해야 한다. 무조건 작은 frame이면
충분하다는 결론이나 실제 뇌를 모두 시뮬레이션해야 한다는 요구는 나오지 않는다.

## 2. 하이퍼그래프: 정보 보존과 비용 최적성은 각각 증명한다

[HSWMHypergraphCostConditions.lean](../../formal/HSWMHypergraphCostConditions.lean)은
기존 `decode_encodeNary`를 재사용한다. 이항 저장도 relation/factor 주소와 역할·slot을
보존하면 n항 관계를 정확히 복원한다. 기존 bare clique 손실 반례는 그대로 유효하며,
이를 모든 이항 그래프의 표현 불가능성으로 확대하지 않는다.

이번 비용 모델은 payload·header·typed slot의 선언된 정수 단위만 센다. 직접 표현의
header와 slot이 각각 경쟁 표현보다 비싸지 않으면 전체도 비싸지 않다. 동일한 field 비용을
부과하면 동률이다. 모든 필드 비용이 양수인 구성에서도 직접 표현 `5 < 8`, factor 표현
`8 < 15`의 양방향 사례가 존재한다. 따라서 이 선언된 모델족에서도 어느 한 표현의
무조건적인 우위는 성립하지 않는다.

이것은 사용자의 최소 비용 가설을 검증 가능한 조건으로 좁힌 결과다. 실제 저장 바이트,
검색·추론·업데이트 시간, LLM 토큰·오류 비용은 이 정리의 측정값이 아니다. 적절한 과제와
동등 정보의 대조군을 정해 그 비용을 측정해야 한다. 비용을 정하지 않은 원래의 보편
최소 비용 주장이 이번에 증명됐다고 보고하지 않는다.

## 3. 소프트웨어: 저장된 의미를 읽고 수정한 뒤 다시 실행한다

[HSWMSemanticSoftware.lean](../../formal/HSWMSemanticSoftware.lean)의 상태는 관계 payload와
역할 주소를 가진 graph다. `execute`는 프로그램과 주소로 읽은 국소 신호만 연산자에 준다.
`reference_executes_semantic_weight`는 이 실행과 기존 Semantic Weight 해석의 일치를 보인다.

`computedRevision`은 관측에서 후보를 실제 합성하고, 기존 noisy-feedback 선택 함수를
실행한다. `computed_revision_selects_generated_program`은 그 계산이 생성된 관계를 선택함을,
`stored_revision_changes_next_execution`은 같은 입력의 다음 예측이 달라짐을 증명한다.
`outcome_revised_local_program_has_strict_gain`은 같은 인터프리터로 실행한 수정 전후 점수를
비교하여 비용을 넘는 엄격한 향상을 도출한다. 향상 자체를 전제로 넣지 않는다.

기존 [생성·학습 bridge](../../formal/HSWMGeneratedLearningBridge.lean)의 작성된 유한 문법·비상수 세계와
가중 평가 모집단을 그대로 사용한다. 참 정답 질량은 `10/16 → 16/16`, 추가 비용은
`1/16`이고 참 순이득은 `5/16`이다. 평가 모집단은 합성 관측과 겹치는 전체 유한 census다.
독립적인 새 현실 과제의 일반화 성과로 보고하지 않는다.
세계의 참 함수·관측 모집단·오염량은 이 `CONSTRUCTED_FINITE_REFERENCE_MODEL`에
명시되어 있다. 계산으로 후보를 선택했다는 사실은 현실의 인과 효능을 발견했다는 뜻이 아니다.

`BoundedEnvelope`에는 이 의미 기계와 비신경 Boolean 세계 시뮬레이터가 함께 있다.
이 유한 의미 기계의 실행·수정을 삽입해도 동작이 보존되고, 그 삽입으로 얻을 수 없는 다른
세계 모형도 존재한다. 이는 CHU가 HSWM보다 넓을 수 있다는 실행 가능한 작은 포함 관계의
예시다. 이 두 variant의 합 타입이 실제 CHU/HSWM 정의의 삽입 정리인 것은 아니며,
전체 CHU를 두 종류로 제한하거나 CHU 전체의 구현을 선언하지 않는다.

연산자가 그래프 프로그램을 무시하면 저장 내용을 바꾸어도 결과는 그대로라는 반례도 있다.
`faithful_operator_inherits_computed_gain`은 실제 연산자의 정확한 국소 의미 실행이 주어졌을
때 향상이 전달됨을 보인다. 그 `Faithful` 조건 자체를 현실 LLM에 대해 증명하거나 측정한
것은 아니다. 현재 정리는 고정된 결정적 연산자를 다루며 확률적 모델 호출의 법칙은 추가
연구 대상이다.

## 4. 이미 증명한 학습 효과와 TS 정본의 연결

앞선 “실제 LLM 개선 미검증”은 “학습 향상 정리가 없다”는 뜻이 아니다.
[기존 성능 bridge](HSWM_LITERATURE_TO_PERFORMANCE_PROOF_2026-09-14.md)는 선언한 공동
오류 법칙에서 `18/27 → 20/27` 향상을 도출했고,
[frontier proof](HSWM_SEMANTIC_FRONTIER_PROOFS_2026-09-14.md)는 문법 생성·잡음·비용·재귀
실행으로 확장했다. 이번 소프트웨어 정리는 그 결과를 같은 실행·수정 인터프리터에 연결한다.

[TS 순수 선택 함수](../../src/hswm/effect-runtime/src/semantic-learning-selection-domain.ts)는
Lean `HSWM.NoisyFeedback.choose`의 계산을 `bigint` 자연수 질량으로 옮겼다.
관측 점수 차이가 `2 × 오류 허용량 + 비용`을 엄격히 넘을 때 후보를 선택하며, 진실 함수를
입력받지 않는다. 오류 허용량을 실제보다 작게 선언하면 나쁜 후보를 선택할 수 있다는
기존 반례도 테스트한다.

[development 보고서 adapter](../../src/hswm/effect-runtime/src/semantic-lifecycle-selection.ts)는
동일 근거와 읽은 상태가 결속된 평가만 선택 입력으로 받는다. null·거절 예측은 Boolean
예측 정리의 전제를 만족하지 않으므로 `NOT_APPLICABLE`로 남긴다. 이 함수는 현재 v1
실행기의 자동 commit/선택 경로를 교체하지 않는다. TS 코드의 전수 정제나 전체 런타임
정확성을 Lean으로 새로 증명한 것은 아니며, 실제 LLM의 새로운 호출과 미관측 입력에 대한
이득도 따로 검증해야 한다.

## 검증과 미완료 의무

[재실행 안내](../../_research/three_philosophies_proof_v1/README.md)와
[새 검증 기록](../../_research/three_philosophies_proof_v1/lean-verification.v1.json)에 정확한
소스 해시·고정 Lean 버전·정리별 공리를 기록한다. 기존 증명 기록은 덮어쓰지 않는다.
Lean 4.32.1의 정확한 바이너리로 의존 모듈까지 13개를 새 import 디렉터리에서
`--trust=0` 컴파일했다. 새 모듈의 이름 있는 정리 33개(매핑 9, 비용 10, 소프트웨어 14)를
`#print axioms`로 검사했다. 보고된 공리는 `propext`, `Quot.sound`, `Classical.choice`
이내이며 `sorryAx`나 추가 공리는 없었다. 정리 수는 보조 정리·반례를 포함한 검사 대상 수다.
공개 검증 기록은 호스트 절대 경로 세 필드만 제거한 투영이다. 별도 독립 커널 검증기를
실행한 결과는 아니며, TS 전체 코드의 형식 검증도 아니다.
[Lean 공식 지침](https://lean-lang.org/doc/reference/latest/ValidatingProofs/)에 따라
명제가 커널 검사를 통과한 사실과 그 명제가 사용자의 전체 철학을 뜻하는지는 구별한다.

이번 결과는 제한된 수학적 번역의 기계 검증이다. 실제 LLM 의미 실행, 관측의 현실적
진실성·오염 상한, 규모가 커진 graph의 충분한 국소 읽기, 동등 비용의 Hyperon 비교,
전체 CR-0..7/FCL-1..8은 미완료로 유지한다. 프로그램 전체는 `UNJUDGED`다.
