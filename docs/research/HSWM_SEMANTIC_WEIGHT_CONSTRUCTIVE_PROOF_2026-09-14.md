# Semantic Weight 방법의 구성적 증명과 실현가능성의 경계

2026-09-14 · `SECONDARY_AI / BOUNDED_CONSTRUCTIVE_FORMALIZATION`

**전체 HSWM의 실현가능성은 아직 증명되지 않았다.** 앞선 의미 정의와 정확한 요약 조건만으로 그 결론은 따라오지 않는다. 이번에는 실제 outcome 갱신 알고리즘에서 제한된 관계 학습을 도출하고, 실행·학습 요약의 보존 정리와 관측 부족의 반례를 기계 검증한다. 수학적으로 증명할 수 있는 범위를 전체 목표와 구별한다.

[사용자 원문](../canon/sources/USER_PRIMARY_HSWM_RIGOROUS_REALIZABILITY_PROOF_2026-09-14.txt)은 HSWM을 구현할 수 있다는 엄밀한 증명을 요구한다. 이 요구가 아래 모형의 가정을 승인하거나 HSWM의 실현을 사실로 만들지는 않는다. [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 token-native LLM-function macro-neural network, [FCL-1..8](HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md), [목표 유지·방법 교체](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)를 보존한다.

**개념적 변화:** [앞선 이론](HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md)의 “어떤 요약이 실행과 학습을 보존하는가”에서, 하나의 명시적 관계 학습기가 무엇을 실제로 계산하고 어디에서 실패하는지로 나아간다. 기존 schema·canonical atom·owner·권한의 runtime 구현을 변경하지 않는다. 아래 state는 수학적 실행 상태이며 full canonical state나 cognition-bearing cell을 대신하지 않는다.

## 1. 먼저 증명할 수 없는 추론을 제거한다

정확한 quotient는 좋은 학습을 함의하지 않는다. `Learn(z,u)=z`, `q=id`인 고정 시스템도 실행과 학습의 요약 조건을 만족한다. 그러나 outcome이 다음 행동을 바꾸지 않는다. 따라서 다음 추론은 유효하지 않다.

```text
Semantic Weight의 형식적 정의와 P1–P5
  ⇒ 학습·인지·FCL-1..8을 실현하는 HSWM의 존재
```

이는 HSWM의 불가능성 증명이 아니다. 주어진 전제에서 요청한 결론이 아직 도출되지 않는다는 반례다. 유용한 학습기·관측·합성 규칙을 추가로 구성해야 한다. 전체 존재 정리의 양화와 CR-0..7은 [기존 구성적 실현 프로그램](HSWM_CONSTRUCTIVE_REALIZABILITY_PROGRAM_2026-09-10.md)의 목표를 그대로 사용한다.

## 2. 성공 여부와 독립적으로 정한 환경족

세 입력은 서로 다른 이름을 가진 Boolean role인 source, modulator, context다. 출력은 recipient의 Boolean 예측이다. 외부 법칙은 미지의 결정적 함수다.

```math
X=\{0,1\}^{3},\qquad f:X\to\{0,1\},\qquad
\mathcal E=\{f\mid f:X\to\{0,1\}\}.
```

환경족은 256개 함수 전체이며 학습기의 성공으로 골라 정의하지 않는다. 아래 가정은 강하며 현실의 LLM·도구·세계가 자동으로 만족하지 않는다.

| 가정 | 정확한 내용 | 가정이 빠지면 생기는 문제 |
|---|---|---|
| E1 · 고정된 의미와 변수 | 세 role과 recipient의 관측 의미가 사전에 고정돼 있다 | 아직 모르는 변수·참조를 발견하는 문제가 남음 |
| E2 · 완전한 허용 개입 | 입력 8가지를 모두 실제로 지정하고 결과를 읽을 수 있다 | 미관측 입력의 법칙을 일반적으로 식별할 수 없음 |
| E3 · 결정적 reset | 각 실행은 동일한 f를 따르며 숨은 carry-over·잡음·drift가 없다 | 마지막 관측 하나가 충분통계가 되지 않을 수 있음 |
| E4 · outcome의 데이터 흐름 | Step은 당시 state와 입력만 읽고, 뒤이어 Env가 f(x)를 반환한다 | 정답 누수로 학습처럼 보이는 계산을 만들 수 있음 |
| E5 · 제한된 목표 | 고정된 X에서의 출력 정확성을 측정한다 | 열린 세계 일반화·효용·권한·인지의 증명으로 확대할 수 없음 |

이것은 명시한 finite response-access 모형이다. `f`는 환경을 기술하는 수학적 인자이며, 실행되는 `Step`이나 `observe`가 읽는 숨은 정답 인자가 아니다. 정리를 증명하기 위해 모형의 환경을 함수로 적는 것과, 현실 학습기에 정답 함수를 제공하는 것을 구별한다. E4는 순수 함수의 값 의존관계이며 cryptographic seal·I/O 격리·평가자 진위·인과적 독립성의 증명이 아니다. 이 접근권의 현실적 확보는 미증명이다.

## 3. 같은 구성의 관측 갱신과 의미 연산

실행용 상태 T는 각 입력에 대해 미관측 또는 마지막 관측 값을 보관한다. 처음에는 모두 미관측이다. 한 outcome이 도착하면 해당 입력 자리만 갱신한다.

```math
T:X\to\{\bot,0,1\},\qquad T_0(x)=\bot,
```

```math
\mathrm{Observe}(T,(x,y))(x')=
\begin{cases}y,&x'=x,\\T(x'),&x'\ne x.\end{cases}
```

미관측 자리의 실행 기본값은 0으로 명시한다. 이는 불확실성의 과학적 calibration이 아니며, “미관측이므로 실제로 0”이라는 믿음도 아니다. 모든 입력을 사전 고정된 순서로 실행하고, 각각의 결과를 받은 다음 갱신한다. 학습기는 처음부터 f의 표를 소유하지 않는다.

**C1 · 관측에서 정확한 관계 법칙을 얻는 구성.** 어떤 f에 대해서도 8개의 지정된 outcome 갱신이 끝나면 모든 x에서 T(x)=f(x)다. 이유는 각 x가 한 번씩 실제 갱신되고 다른 입력의 갱신은 그 자리를 바꾸지 않기 때문이다. 이후 같은 X의 어떤 입력에 대해서도 예측은 f(x)다. 이는 미래 실행에 대한 결과지만, 이미 모든 입력을 관측했으므로 미관측 영역 일반화 정리가 아니다.

그 표를 역할 있는 다항 연산으로 읽는다. S는 세 role의 부분집합이고, 1_U는 U에 속한 role만 1인 입력이다. Boolean XOR를 더하기로 쓰는 체에서 다음 계수를 계산한다.

```math
\alpha_S=\bigoplus_{U\subseteq S}T(1_U),\qquad
d_\alpha(x)=\bigoplus_{S\subseteq\{1,2,3\}}
\alpha_S\prod_{i\in S}x_i.
```

빈 곱은 1이다. 이 모형의 Semantic Weight realization은 **role을 가진 monomial과 그 계수들을 함께 해석한 전이 성향**이다. 개별 계수 하나가 전체 의미나 실제 유용성·causal credit을 담는다고 정의하지 않는다. 일반 HSWM의 disposition을 Boolean 숫자로 제한하지도 않는다.

**C2 · 연산 재구성.** 모든 x에 대해 dα(x)=f(x)다. x=1_V라 놓으면 살아남는 항은 S⊆V이고, 이를 전개할 때 각 f(1_U)는 `U⊆S⊆V`인 S의 수만큼 나타난다. 이 수는 `2^(|V|−|U|)`이다. U=V일 때만 홀수이므로 XOR에서 f(1_V)만 남는다. 이것은 고전적인 Boolean Möbius inversion의 직접적인 유도이며 새로운 HSWM 고유 정리가 아니다. [원 논문의 기본 정리 Lemma 1](https://www.jstage.jst.go.jp/article/transfun/E106.A/7/E106.A_2022EAL2095/_pdf)

이 손증명의 조합론은 일반 유한 role 수에도 적용되지만, 이번 Lean 재구성 구현은 **정확히 세 Boolean 입력**을 다룬다. 일반 차원 코드나 sample-efficient 학습으로 확대하지 않는다.

**C3 · 실제 차이를 만드는 사례.** f(x)=source·modulator·context라면 삼중항 계수가 1이고 다른 계수는 0이다. 학습 후 이 삼중 관계를 실행하면 8개 입력 모두 맞고, 상수 0 기준은 세 입력이 모두 1일 때 틀린다. 전체 입력에 대한 오류 수가 1에서 0으로 감소한다. 사전에 고정한 균등 readout에서 정확도는 7/8에서 1이다. 이 수치는 정리에서 계산한 값이며 8회 현실 실험의 관측값이 아니다. source만 읽는 다른 f에서는 source와 modulator의 교환이 결과를 바꾸므로 role 이름을 지워도 된다는 결론도 나오지 않는다.

이 모형의 Env는 입력 x의 응답 label을 반환하며 학습기의 예측값에는 의존하지 않는다. 따라서 학습된 것은 고정 입력 개입의 응답 함수이고, 개선된 것은 그 함수의 예측 정확성이다. 예측 행동이 외부 세계를 바꾸는 제어 문제, reward에서 원인별 credit을 알아내는 문제는 증명에 포함되지 않는다. 순수 함수 표기의 Step→Env는 값 의존관계를 구분하며 실제 실행 순서나 호출 발생을 보증하지 않는다.

계수의 활성 support는 정해 둔 변수·monomial 안에서 관계 구조를 구별한다. **새 변수 발견, 열린 topology morphogenesis, 일반 pairwise architecture의 표현 불가능성은 여기서 증명하지 않는다.** 특히 hidden node와 비선형 함수를 가진 pairwise 회로도 같은 Boolean 함수를 계산할 수 있다.

## 4. 실행뿐 아니라 다음 학습도 보존하는가

원래 관측 이력 h를 남기고, 실행용 read view를 q(h)=h를 순서대로 Observe에 넣어 얻은 T로 둔다. 그러면 정의와 fold의 결합 법칙으로 다음이 성립한다.

```math
q(h\mathbin{+\!+}[(x,y)])=\mathrm{Observe}(q(h),(x,y)).
```

Step이 이 T에서 계산한 dα만 읽으면 q가 같은 두 이력의 현재 예측도 같다. 이후 같은 관측을 받을 때 다음 q도 같다. 동일한 record를 한 번 기록한 이력과 두 번 기록한 이력은 다르지만 q는 같으므로 이 read view는 비단사다. 원래 순서 이력을 전부 실행 때마다 읽을 필요가 없다는 좁은 충분성 결과다.

다만 q가 이력·권한·복구·시점까지 보존하는 것은 아니다. full provenance를 삭제하거나 이 read view를 새 canonical state라고 부를 수 없다. 반복 측정의 횟수로 uncertainty를 갱신하거나 순서·만료·관측 비용이 허용성에 영향을 주는 모델에는 이 q가 충분하지 않을 수 있다.

**Q1 · 일반 결정적 보존 정리.** [HSWMSemanticQuotient](../../formal/HSWMSemanticQuotient.lean)는 명시적 Step, Learn, 출력 사상과 상태 사상을 두고 두 연산의 보존 조건에서 유한한 실행·학습 event 열의 보존을 도출한다. 두 refinement를 이어 붙이는 결과도 같은 정의에서 도출한다. 이 정리는 실제로 보존 조건을 만족하는 q를 제시해야 적용할 수 있다. 확률 kernel의 일반 정리나 실제 Env·권한의 자동 보존을 주장하지 않는다.

**Q2 · 같은 학습기의 실제 적용.** [HSWMFiniteSemanticRefinement](../../formal/HSWMFiniteSemanticRefinement.lean)는 위 관측 기록 h와 T에 실제로 Q1을 적용한다. 두 실행은 같은 `semanticStep`을 읽고, 기록 append와 `Observe`의 교환 법칙을 직접 증명한다. 임의로 제공된 record 열에 대한 정제는 record의 진위를 보장하지 않는다. 따라서 별도의 `fullEpisode`가 `semanticStep`에서 trace를 만들고 Env에서 결과를 받아 기록하도록 정의하고, 이 구체적 episode와 원래 `episode` 사이의 요약 보존도 증명한다. 유한 sweep에 반복 적용하면 전체 관측 기록을 통해 얻은 예측 역시 f와 정확히 같다.

여기서 기록은 `(input,outcome)` 관측 record이며 예측·서명·평가자·권한을 포함한 canonical trajectory 전체가 아니다. 허용 label을 모두 true로 둔 유한 수학 모형에 관한 결과다. 실제 Permit, 인증, 독립 outcome custody를 구현했다는 주장이 아니다.

같은 구성 전체의 최종 Lean 명제는 다음과 같다. `fullSweep`은 앞서 정의한 실행·환경·관측 갱신을 실제로 계산하고, `semanticStep`은 그 결과에서 ANF 연산을 계산한다. 정확성이나 향상 witness를 별도 전제로 받지 않는다.

```lean
theorem fullSweep_semantic_prediction_exact (truth : Env) (input : Input) :
  semanticStep (summary (fullSweep allInputs truth [])) input = truth input
```

`fullSweep_cubic_strict_gain`은 같은 sweep에서 cubic 관계의 오류가 실제로 1에서 0으로 감소함을 도출한다. 두 명제의 양화는 이 문서 E1–E5의 명시적 함수·타입·환경 정의 안에 있다.

## 5. 합성에서 도출되는 결론의 정확한 범위

완전히 학습한 child 연산이 f와 모든 허용 입력에서 같으면, 선언된 결정적 상위 함수 g의 입력 자리에 그 연산을 넣어도 출력은 같다. 여러 입력과 유한 깊이의 식에 대한 반복 적용은 등식의 합성으로 증명된다. 이는 같은 구성에서 학습한 연산을 실제로 대입하는 결과다.

그러나 **정확한 함수 대입과 cognition-bearing HSWM의 합성은 다른 의무**다. 여기에는 shared outcome의 causal credit, 상위 persistent whole-state의 추가 효능, 충돌·지연·탈퇴·권한·self-model을 보존하는 동역학이 없다. 새 상위 함수를 배우려면 그 상위 환경에서 E1–E5가 다시 성립해야 하며, 하위 정리만으로 상위 관측 접근권이 생기지 않는다. 기존 [합성 간섭 반례](../../formal/HSWMCompositionInterference.lean)도 계속 유효하다.

## 6. 이 방법에 일반화를 공짜로 붙일 수 없는 증명

**N1 · 관측하지 않은 입력의 식별 불가능성.** 사전 고정된 질의 목록에서 u가 빠져 있다고 하자. f₀는 항상 0, f₁은 u에서만 1이고 나머지는 0으로 둔다. 두 환경의 모든 관측 transcript는 같지만 u에서 필요한 답은 다르다. transcript만 읽는 동일한 decoder는 두 환경에서 같은 답을 내므로 둘 모두를 맞힐 수 없다.

이 명제는 [HSWMSemanticLearningLimits](../../formal/HSWMSemanticLearningLimits.lean)에서 일반 입력 타입에 대해 검증한다. Lean 명제는 고정 질의 transcript에 관한 것이며 adaptive query complexity나 확률 학습의 일반 하한을 대신하지 않는다. 이 결과만으로도 “8개 중 일부만 관측했지만 아무 함수에나 정확한 의미를 배운다”는 주장은 배제된다.

정확한 무제약 함수 학습의 역할 수 n에 대한 exhaustive 구성은 2^n개 응답을 요구한다. 따라서 이 존재 구성 자체를 실제 거대 HSWM의 효율적인 학습 방법으로 채택할 수는 없다. 다음 단계에는 관계의 구조적 제약, 반복 가능한 관측과 개입, 잡음 가정에서 **더 적은 관측으로 무엇을 보장할 수 있는지**를 도출해야 한다. 그 가정을 “우리 방법이 잘되는 함수”로 정의해서는 안 된다.

## 7. 전체 HSWM에 남는 정확한 간극

| 기존 의무 | 이번에 얻은 수학적 부분 | 아직 증명하지 않은 부분 |
|---|---|---|
| CR-0 | role을 구별하는 관측 갱신과 연산 | 실제 canonical owner·Inv/Permit·receipt·실행 refinement |
| CR-1 | 명시한 환경의 정확한 학습, 고정 기준보다 엄격히 개선되는 예 | 잡음·비정상성·지속 학습·탐색 비용 포함 효용·강한 학습기 대비 |
| CR-2 | 허용된 입력 개입의 결정적 응답을 모두 읽는 식별 | 현실 개입 custody, revision의 causal efficacy 추정·일반 식별 |
| CR-3 | 해당 관측이 해당 표 자리를 바꾸는 명시적 갱신 | 공유 outcome에서 cell·incidence·coalition의 비중복 causal credit |
| CR-4 | 고정 변수의 n항 계수와 support를 구별 | 새로운 변수·coalition·topology의 생성·유용성·손상 회복 |
| CR-5 | 지정된 실행·갱신에 충분한 비단사 read view | world/self 공동 예측·불확실성·migration·통시적 동일성 |
| CR-6 | 결정적 등식 대입과 정확한 Step/Learn refinement 합성 | 상위 상태의 추가 학습 효능·shared coupling·권리·exit·복구 |
| CR-7 | 같은 유한 관측 learner에서 도출한 연산 정확성 | CR-0..6을 함께 만족하는 token-native LLM realization과 현실 연결 |

이 표의 “수학적 부분”을 CR 또는 FCL 통과로 기록하지 않는다. 완전한 HSWM을 증명하려면 동일한 실행 가능한 구성에서 오른쪽 열을 닫아야 한다. 기존 RED 결과와 강한 대조군 요구는 보존한다. LLM의 보편 근사·표현 능력이나 정리의 코드 존재만으로 실제 LLM이 이 알고리즘을 정확히 실행한다는 결론도 도출하지 않는다.

## 8. 증명 소스, 검증과 연구 그래프

- [유한 의미 관계 학습](../../formal/HSWMFiniteSemanticLearning.lean)
- [Step/Learn 보존 정리](../../formal/HSWMSemanticQuotient.lean)
- [같은 관측 learner에 대한 정제 적용](../../formal/HSWMFiniteSemanticRefinement.lean)
- [관측 부족과 학습 없는 반례](../../formal/HSWMSemanticLearningLimits.lean)
- [재검증 명령과 범위](../../_research/semantic_weight_proof_v1/README.md)
- [출처·정리별 검증 기록](../../_research/semantic_weight_proof_v1/verification.v1.json)
- [증명 의존 그래프](../../ontology/identity/hswm_core/HSWM_SEMANTIC_WEIGHT_CONSTRUCTIVE_PROOF_ONTOLOGY.v1.json)

Lean 검사는 정확한 statement와 사용 공리를 함께 감사한다. [공식 검증 지침](https://lean-lang.org/doc/reference/latest/ValidatingProofs/)에 따라 커널이 식을 받아들였다는 사실과 그 식이 의도한 HSWM 주장을 뜻한다는 판단을 구분한다. 기존 고정 Lean 도구를 재사용하며, 이번 elementary formalization을 새 과학 법칙이나 현실 효능의 발견으로 기록하지 않는다.

검증된 핵심은 `fullSweep_semantic_prediction_exact`, `fullSweep_cubic_strict_gain`, `fullHistory_trace_refines_table`, `run_refines_composed`, `no_fixed_transcript_decoder_exact_both`다. 정리별 exact source hash와 공리 집합은 검증 기록에 둔다. `propext`와 `Quot.sound`를 사용하는 정리도 있으므로 전체를 “공리 없는 증명”이라고 부르지 않는다.

연구 그래프는 사용자 요구, 모형 가정, 실제 theorem symbol, 반례, 기존 이론 및 미해결 CR/FCL을 출처에 결속한다. formal proof와 손증명·가정·현실 연결을 서로 다른 상태로 둔다. 이는 checked-in 연구 기록이며 live KG나 HSWM canonical learning state의 변경이 아니다.
