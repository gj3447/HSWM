# Semantic Weight의 Lean4 정의와 하이퍼그래프가 필요한 정확한 범위

2026-09-14 · `SECONDARY_AI_OPERATIONAL_FORMALIZATION`

**Semantic Weight는 역할을 가진 다자 관계를 현재 문맥에서 읽었을 때, 수신자들의 다음 반응이 함께 어떻게 달라지는지를 정하는 전이 성향이다.** 그 성향은 관계에 기록된 의미·예외·근거를 국소 LLM 연산자가 해석하면서 실현된다. 관계를 고친 경험이 이후 성향을 바꾸어야 HSWM의 학습 목표와 연결된다.

[사용자 요청](../canon/sources/USER_PRIMARY_HSWM_SEMANTIC_WEIGHT_DEFINITION_REQUEST_2026-09-14.txt)에 따라 [기존 D1–D6 정의](HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md)를 Lean의 정확한 연산 계약과 표현 보존·손실 정리로 구체화한다. [상태와 국소 연산자 정전](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md)의 **거대한 하이퍼그래프가 AI 상태 자체이고 LLM은 작은 국소 입력을 받는 내부 신경 연산자**라는 정체성을 유지한다. 이하의 수학적 정의는 AI의 형식화이며 사용자 원문에 소급하지 않는다.

**개념적 변화:** 이전 [LLM 의미 그래프 증명](HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.md)은 주로 문자열·역할·outcome·revision의 데이터 흐름을 검사했다. 여기서는 저장된 표현을 읽어 얻는 **전이의 의미**, 그 의미에 충분한 국소 입력, 다자 관계의 보존 조건을 직접 대상으로 삼는다. 새로운 실모델 효능이나 전체 HSWM의 완성을 보고하는 연구는 아니다.

## 1. 상태·표현·전이 성향을 연결하는 정의

`S`는 기존 schema와 canonical atom들의 하이퍼그래프 상태다. 관계 버전 `e`의 역할 incidence는 어떤 참여자가 어떤 역할·순서·타입으로 결속됐는지를 가리킨다. 같은 참여자가 여러 역할에 나타날 수도 있다. 허용 입력 `i`에는 역할별 활성과 문맥을 담고, `Read_e(S,i)`는 해당 연산에 필요한 국소 정보를 선택한다.

```math
d^{\beta}_{e,S}(i)
=\mathrm{LLM}_{\beta}\bigl(\mathrm{Encode}_{e,\beta}(\mathrm{Read}_{e}(S,i),i)\bigr).
```

오른쪽은 하나의 **공동 출력 법칙**을 반환한다. 결정적 실행이면 수신자별 message·전이 제안을 함께 묶은 값이다. 확률적 실행이면 그 결합된 값에 대한 조건부 분포다. 각 수신자의 주변분포를 곱해 독립성을 암묵적으로 가정하지 않는다. `β`는 모델 버전과 실행 계약을 고정한다. cache·seed·session이 법칙을 바꾸면 조건화하거나 주변화하는 범위를 별도로 명시해야 한다.

이 식에서 Semantic Weight는 특정 입력의 출력 한 개가 아니라, **허용된 입력들을 다음 반응으로 보내는 함수 전체의 성향**이다. 자연어 관계 설명은 그 성향을 실현하는 저장 표현 중 하나다. 같은 설명도 문맥·역할·모델이 달라지면 다른 전이가 될 수 있고, 다른 설명이 같은 선언 범위의 전이를 실현할 수도 있다.

[Lean 정의](../../formal/HSWMSemanticWeightDefinition.lean)는 `SemanticWeight`의 국소 읽기와 `disposition`, 이를 평가하는 `behavior`, LLM으로 직접 구성하는 `fromLlm`을 둔다. `Law`는 명시적 타입 매개변수다. 적절히 정의한 확률분포 타입이나 결정적 공동 출력 타입을 넣을 수 있다. **이번 Lean 파일은 일반 확률분포의 정규화·가측성·모델 calibration을 증명하지 않는다.** 공동 수신자별 값을 나타내는 구체적인 타입도 따로 제공한다.

`RoleContext`는 역할이 표시된 유한 incidence 목록과 문맥을 담는 컨테이너다. 실제 schema에서 허용되는 역할 조합·활성 타입·입력 진위를 자동 검사하는 증명은 아니다. `JointMessage`를 출력 타입으로 선택할 수 있지만, 임의의 `Law` 값이 공동 확률분포라는 주장을 증명한 것도 아니다. 이 인터페이스가 하위 출력들의 독립성을 강제하지 않는다는 범위다.

정확히는 Lean의 `SemanticWeight` 구조체가 관계족의 읽기·해석 방식을 정하고, `behavior weight S`라는 함수가 상태 `S`에서의 성향을 나타낸다. `State`를 HSWM 그래프에 대응시키고 어느 relation version을 읽는지 지정하는 것은 실제 구현의 의무다. 상수 연산도 이 타입을 만족하므로 **이 정의를 가진다는 사실만으로 학습 가능성이나 유용한 학습이 증명되지는 않는다.**

이것은 새로운 H/W/A/F/Π 분해가 아니다. `Read`, 입력 직렬화와 출력 법칙은 같은 상태에 관한 수학적 인터페이스이며 별도 canonical 상태나 인지 시스템이 아니다. 각 atom의 owner, provenance, 허용성, 전체 Step/Learn 구현과의 대응은 [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)과 기존 증명 의무를 이어받는다.

## 2. 왜 이름을 의미 가중치라고 부르는가

예를 들어 하나의 관계가 “이 문이 잠겼고 이 열쇠가 그 잠금장치에 맞으며 사용 권한이 있으면, 열기 행동이 성공할 것으로 예측한다”는 조건을 표현한다고 하자. 여기에는 문·열쇠·잠금장치·권한·행동·예측 수신자가 서로 다른 역할로 결속된다. “이 문에서는 열쇠가 파손돼 예외가 된다”는 경험은 이후 같은 역할 조합의 반응을 바꿀 수 있다. 이는 설명을 위한 가상 사례이며 수행한 실험이 아니다.

| 구분 | 의미 |
|---|---|
| 저장 표현 | 관계의 의미 설명, 역할 참조, 조건·예외, 근거와 revision |
| Semantic Weight의 전이 성향 | 그 표현을 현재 국소 문맥에서 해석했을 때 가능한 공동 반응의 법칙 |
| 읽기 점수·attention | 이번 계산에 그 관계를 얼마나 선택·활성화할지 정하는 값 |
| 인과 효과 | 명시한 관계 개입이 실제 결과에 만든 차이 |
| 학습 갱신 | 예측 뒤 얻은 outcome과 근거로 이후 상태·성향을 바꾸는 연산 |

“가중치”라는 이름은 변화 가능한 영향의 성향을 가리킨다. 그 저장 형태가 항상 실수 하나여야 한다는 제한은 아니다. 반대로 실수·정수에 충분한 정보를 부호화하거나 비선형 연산과 함께 쓰는 모든 방법이 불가능하다는 뜻도 아니다.

LLM의 언어적 의미 능력은 이 성향을 실현하는 자원이다. 센서가 어느 문을 관측했는지, 예측이 실제 세계와 맞는지까지 함수의 이름으로 참이 되지는 않는다. 지시 대상·관측 절차·fresh 사례에서의 적합성·인과 개입은 기존 D2a/D5의 별도 검증 대상이다.

## 3. 국소 입력과 학습에 필요한 조건

**국소 입력의 충분성.** 같은 국소 읽기와 같은 역할·문맥 입력을 받은 고정 연산자는 같은 공동 출력 법칙을 낸다. 따라서 서로 다른 반응이 필요한 두 상태를 읽기 과정에서 합쳐 버리면, 그 읽기만 사용하는 어떤 decoder도 둘 모두를 정확히 복원할 수 없다. 정리는 목표 반응을 읽기와 독립적으로 두며, 상수 읽기로 서로 다른 Boolean 정답을 구별할 수 없다는 실제 반례를 포함한다.

이는 작은 입력이 불가능하다는 증명이 아니다. 어떤 차이를 버려도 되는지에 대한 기준이다. 유용한 작은 읽기를 구성하는 일, 그 선택 비용, 여러 국소 연산을 통해 필요한 정보가 전달되는 조건은 아직 연구해야 한다. 타입이 `Read`라는 사실만으로 token budget이 작아지지 않는다.

**현재 성향과 학습 상태의 차이.** 같은 현재 예측을 가진 두 상태가 서로 다른 잠재 정보를 보존하고 있으면, 같은 outcome 뒤에 다른 다음 읽기·예측을 가질 수 있다. Lean의 Boolean 반례는 이 차이를 직접 계산한다. 따라서 현재 행동이 같은 관계를 합치려면, 이후 Learn도 그 동등성을 보존하는지 추가로 확인해야 한다. 이 조건은 기존 P1과 CR-5/6으로 연결되며 불확실성·예외를 삭제할 근거가 되지 않는다.

**역할과 열거 순서.** source와 recipient를 교환하면 의미가 바뀔 수 있다. 이미 붙어 있는 역할 표시는 유지하고 목록 표시 순서만 바꾸는 일과 다르다. 이번 Lean 예는 두 역할의 구체적 차이를 보여준다. 임의 schema의 모든 순열에 대한 불변성을 자동 부여하지 않는다.

## 4. 하이퍼그래프가 필요한 범위와 필요하지 않은 범위

정확한 답은 **다자 결속을 직접 보존해야 하며, 하이퍼그래프와 동등한 정보를 가진 표현도 가능하다**는 것이다. “오직 특정 hypergraph 저장 엔진만 HSWM을 구현할 수 있다”는 명제는 성립하지 않는다.

### 4.1 원래 노드 사이의 쌍별 연결만 남기면 잃는 것

네 참여자 `a,b,c,d` 위의 두 관계족을 보자.

```text
A = {abc, abd, acd, bcd}
B = {abc, abd, acd}
```

둘 모두 “같은 관계에 등장한 적 있는 두 참여자를 연결한다”는 쌍별 투영에서는 여섯 쌍을 전부 연결한다. 그런데 `bcd`라는 공동 관계는 A에만 있다. [Lean 표현 정리](../../formal/HSWMHypergraphRepresentation.lean)는 두 투영의 동일성과 원래 관계족의 차이, 그 투영만 읽는 decoder의 복원 불가능성을 증명한다.

또한 “이 삼중 관계가 있는가”에 응답하는 간단한 연산에서는 `bcd`에 대한 반응도 달라진다. 같은 쌍별 투영만 받은 연산자가 두 응답 모두를 맞힐 수 없다는 반례로 연결한다. 이는 선언된 관계 응답에 관한 사례이며 LLM의 실제 세계 이해를 검사한 것은 아니다.

이 반례의 투영은 **쌍의 존재 여부만** 남긴다. 관계 수·incidence·역할·payload를 추가로 전달하는 표현에까지 불가능성을 확대하지 않는다. HSWM에서 중요한 것은 어떤 참여자들이 하나의 관계로 결속돼 같은 예외·근거·revision의 대상인지를 보존하는 것이다. 쌍별 유사성만으로 이를 대신할 수 없다.

### 4.2 이항 그래프로도 손실 없이 구현할 수 있다

관계마다 별도 factor node를 만들고, 각 참여자로 향하는 이항 edge에 역할을 붙이면 된다. 새 Lean 모형은 factor의 식별 정보와 역할별 incidence에서 원래 관계를 복원한다. factor payload에 원래 관계 전체를 숨겨 두고 그대로 꺼내는 복원은 사용하지 않는다. 정리는 모형이 선언한 정상적인 incidence encoding에 관한 것이며 임의의 깨진 외부 그래프를 자동 수리하는 알고리즘은 아니다.

일반 정리 `decode_encodeNary`는 임의의 유한 factor 수, factor마다 다른 유한 arity, 임의의 역할·참여자·payload 타입을 다룬다. factor 주소 `Fin n`과 incidence slot 주소 `Fin (arity factor)`를 보존하고, 분리된 역할 표시와 endpoint를 다시 결합한다. 같은 참여자의 여러 slot 참여도 허용한다. 이는 정해진 snapshot의 정확한 복원이며, 영구 UID 배정·변경 중의 주소 안정성·revision 계보·canonical admission까지 자동 증명하지 않는다. 별도의 `decode_encode`는 세 역할의 작은 예다.

이는 [factor graph의 원 논문](https://www.isiweb.ee.ethz.ch/papers/arch/aloe-2001-1.pdf)이 다변수 함수를 변수 node와 factor node로 표현하는 방식과 연결된다. [W3C의 n-ary relation 패턴](https://www.w3.org/TR/swbp-n-aryRelations/)도 관계 인스턴스를 노드로 두고 참여 역할을 연결한다. 후자는 **2006 Working Group Note**이며 W3C Recommendation으로 표시하지 않는다.

따라서 HSWM의 의미적 구조는 role-bearing hypergraph로 두면서, 실제 저장은 적절한 property graph·RDF·관계형 데이터베이스의 incidence 표현으로 구현할 수 있다. 그때도 relation identity·역할·다중 참여·의미·revision·계보의 보존을 별도로 확인해야 한다. 여기서 든 저장 방식 전체를 이번 Lean 정리가 검증한 것은 아니다.

### 4.3 다자 상호작용은 쌍별 항의 단순 합보다 강하다

세 Boolean 입력의 삼중 상호작용 `x AND y AND z`를 0/1 정수 함수로 보자. 원래 세 입력만 사용하는 단항·이항 함수들의 합은 세 변수에 대한 혼합 3차 차분이 항상 0이다. 삼중 AND의 차분은 1이므로 이런 합과 같을 수 없다. Lean은 그 항등식과 불가능성을 검사한다.

그러나 두 이항 AND를 합성하면 같은 함수를 계산할 수 있다. hidden node·factor node·비선형 합성·상위 특징을 허용하는 신경망에는 위의 제한이 적용되지 않는다. 이 결과는 HSWM의 다자 관계를 쌍별 scalar 합으로 제한할 수 없는 이유 중 하나이며, 모든 pairwise GNN의 표현력 하한이 아니다.

## 5. Hyperon과 비교할 실제 차이

Hyperon은 필수 핵심 비교 대상이다. [공식 2026 백서](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf)의 Atomspace·MeTTa·MORK와 neural read/write bridge는 관계 상태와 국소 연산의 결합에 이미 직접 닿아 있다. [기존 소스 고정 조사](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)의 구현·prototype·설계·가설 구분을 보존한다.

이번 정의만으로 HSWM의 독창성이나 Hyperon 대비 우위를 얻지 않는다. 비교할 것은 역할을 가진 관계 성향을 어떤 자료에서 배우는지, 독립 outcome이 잘못된 관계를 교정하는지, 그 revision이 같은 상태의 다음 계산을 바꾸는지, 합성 뒤에도 이 능력이 유지되는지다. “Semantic Weight”라는 명칭만으로 새로운 수학적 객체가 되지는 않는다.

## 6. 검증과 남은 의무

두 파일의 named theorem **22개**를 검사했다. 아래는 핵심 명제와 그 경계다.

| Lean 명제 | 확인하는 것 |
|---|---|
| `from_llm_behavior_is_operator` | 주어진 LLM encoder/operator에서 성향을 직접 구성한다. 실제 모델의 정답성 전제나 결론은 없다. |
| `no_read_only_decoder_for_lost_distinction` | 읽기에서 합쳐진 두 상태의 목표 반응이 다르면 그 읽기만으로 둘을 복원할 수 없다. |
| `same_behavior_does_not_imply_same_learned_successor` | 같은 현재 행동·같은 outcome이어도 다음 행동이 달라질 수 있는 구체적 반례. |
| `decode_encodeNary` | 임의 유한 arity의 역할·slot·endpoint·payload를 incidence 표현에서 정확히 복원한다. |
| `no_pair_projection_response_decoder` | 쌍별 존재 투영만으로 두 관계족의 실제 삼중 관계 질의 응답을 모두 맞힐 수 없다. |
| `cubic_not_unaryPairwise` / `cubic_has_binary_composition` | 단항·이항 항의 합은 삼중 AND를 표현하지 못하지만 이항 연산의 합성은 표현한다. |

[재검증 방법](../../_research/semantic_weight_definition_v1/README.md)과 [정리별 검증 기록](../../_research/semantic_weight_definition_v1/lean-verification.v1.json)은 기존 고정 Lean 4.32.1·Std로 정확한 source와 각 정리의 공리를 검사한다. `sorry`나 목표를 선언하는 새 axiom을 허용하지 않는다. 커널 검증은 [공식 Lean 설명](https://lean-lang.org/doc/reference/latest/ValidatingProofs/)처럼 주어진 명제의 증명 검증이며, 그 명제가 현실 HSWM에 적용되는지는 별도 판단이다.

[연구 KG](../../ontology/identity/hswm_core/HSWM_SEMANTIC_WEIGHT_DEFINITION_ONTOLOGY.v1.json)는 정의·정리·반례·가정·기존 CR/FCL 의무와 필수 Hyperon 비교를 source-bound relation으로 연결한다. 이번 결과는 elementary representation/operational formalization이다. 기존 runtime와 역사적 증거를 수정하지 않으며, 새 실모델 학습 성능이나 CR/FCL 완료 판정을 만들지 않는다.
