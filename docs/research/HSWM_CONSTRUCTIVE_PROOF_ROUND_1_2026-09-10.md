# HSWM 구성적 증명 연구 — 첫 형식검증 라운드

2026-09-10 · `SECONDARY_AI / BOUNDED_FORMAL_MODEL_RESULTS`.

**이번에 얻은 것:** 유한 선택 규칙의 조건부 개선, 유한 무작위 배정의 식별식,
국소 개선의 단순 합성이 실패하는 반례와 제한된 보완 조건을 Lean으로 검사했다.
전체 HSWM 구성의 존재, 실제 LLM 효능, 확률적 학습 보장 또는 FCL 통과를 증명한 것은 아니다.

## 1. 목표와 실제로 진행한 연구

사용자는 [구성적 실현가능성 프로그램](HSWM_CONSTRUCTIVE_REALIZABILITY_PROGRAM_2026-09-10.md)을
먼저 실행하고, 나비에–스토크 연구에서 참고한 병렬 탐색·반례 검토·통합·형식검증을
적용하라고 요청했다. 그 방향은 `USER_PRIMARY`, 아래 모델·정리·해석은 `SECONDARY_AI`다.

목표는 [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 token-native HSWM이다.
그 evolving hypergraph가 living harness, world/self model, continuous learner로 함께
작동하며 상위 HSWM으로 다시 합성되는 [전체 FCL 계약](../canon/USER_PRIMARY_HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.md)을
그대로 유지한다. 이번의 개념적 변화는 앞서 쓴 분석적 유도의 일부와 미해결 합성 조건을
실행 가능한 정의·정리·반례로 바꾼 것이다. 새 schema, owner, Permit 또는 canonical-write
경로를 추가하지 않는다.

세 탐색자는 각각 선택 규칙, 인과 식별, 합성 구성·반례를 맡았다. 원래 세 후보와 보고서는
소스 해시를 가진 로컬 불변 사본으로 보존하며, 후속 비평·통합·검증은 작업 의존성을 따른다.
역할 분리는 같은 환경의 AI 작업자 분리다. 외부 수학계 검증이나 현실 outcome의 독립 보관을
달성했다는 뜻은 아니다. 실제 token 사용량은 제공되지 않아 `null/UNKNOWN`으로 기록한다.

## 2. 선택 규칙: 오차와 후보 간격 조건에서 갱신 결과를 도출

[HSWMFiniteSelection.lean](../../formal/HSWMFiniteSelection.lean)의 실행 입력은 후보 ID와
경험적 정수 점수다. `select`는 실제 `List.maxOn?` 계산이고 `update`는 엄격한 `2 epsilon`
문턱을 넘을 때만 선택을 바꾼다. 진짜 점수 `truth`는 정리의 의미론 인자로만 존재하며
선택·갱신 함수가 읽는 입력에는 없다.

정수는 선언할 공통 양의 분모에 대한 고정 격자 단위로 해석할 수 있다. 분모 선택·실수와의
오차·실제 표본 평균 계산을 이 파일이 증명한 것으로 취급하지 않는다.

| 정리 | 기계 검증한 결론 |
| --- | --- |
| `select_exists`, `select_member`, `select_argmax` | 비어 있지 않은 유한 목록에서 실제 후보를 반환하고 그 경험 점수가 목록의 최대다. |
| `select equalCandidates = some equalBaseline`의 `example` | 점수 7인 두 후보의 구체적인 동점 예에서 앞 후보를 고른다. |
| `accepted_has_true_gain` | 모든 후보의 점수 오차가 epsilon 이내이고 문턱을 넘으면 선택의 진짜 점수가 기준보다 높다. |
| `selected_near_any_candidate` | 선택한 진짜 점수는 목록의 어떤 후보보다도 최대 2 epsilon만큼 낮을 수 있다. |
| `gap_forces_acceptance`, `gap_forces_improving_update` | 목록에 진짜 개선 폭이 4 epsilon보다 큰 후보가 있으면 실제 계산한 갱신이 수락되고 진짜 점수가 개선된다. |
| `available_gap_improves_computed_update` | 선택 후보를 호출자가 별도 증거로 제공하지 않아도, 비어 있지 않은 목록의 실제 계산에서 개선 결론을 얻는다. |
| `witness_update_improves`, `equal_score_no_gain_counterexample` | 실제 계산되는 작은 양성 예와, 점수가 같으면 엄격한 개선이 없다는 반례. |

기준 후보가 목록 안에 있다는 조건까지 포함하면 다음과 같이 읽는다.

```math
p_0\in P,\qquad \forall p\in P:\ |\widehat\mu(p)-\mu(p)|\le\epsilon,
\qquad
\exists p\in P:\ \mu(p)-\mu(p_0)>4\epsilon
\quad\Longrightarrow\quad
\mu(\mathrm{update}(P,p_0,\epsilon))>\mu(p_0).
```

여기서 오차 조건은 여전히 명시한 전제다. **Hoeffding 부등식, 그 전제가 높은 확률로
성립한다는 정리, fresh 평가의 독립성, 반복 갱신·누적 순효용은 이번 Lean 파일에 없다.**
앞선 문서의 확률적 유도와 이번 정수 산술 정리를 서로 다른 증거로 유지한다.

`ordinary_same_rule_equivalence`는 같은 함수를 사용하는 비교자가 같은 결과를 낸다는
정의적 등식이다. 이를 실제 native/text/program learner 비교 실험으로 세지 않는다.
이 정리는 HSWM 고유 우위를 입증하지 않으며 정적 관계 포장 RR-1도 구제하지 않는다.

## 3. 인과 식별: 무엇을 평균내면 어떤 효과가 나오는가

[HSWMFiniteRandomizedIdentification.lean](../../formal/HSWMFiniteRandomizedIdentification.lean)은
두 대상 각각의 고정된 control/treated 잠재 점수를 정의한다. 한 대상만 처치하는 두 배정에서
실제 관측 점수는 해당 잠재 점수를 선택하도록 계산한다. 이 정의가 consistency와 제한된
간섭 없음의 모형이다. 현실이 그 모형을 만족한다고 전제 없이 결론내리지 않는다.

첫 대상을 처치한 차이를 `D_1`, 둘째를 처치한 차이를 `D_2`라 하면

```math
D_1=Y_1(1)-Y_2(0),\qquad D_2=Y_2(1)-Y_1(0),
```

```math
D_1+D_2=[Y_1(1)-Y_1(0)]+[Y_2(1)-Y_2(0)].
```

`fairPairedRandomizationIdentifiesPairEffect`가 이 정수 등식을 증명한다. 두 배정에 같은
가중치를 주고 양변을 **정수 나눗셈이 아닌 유리수/실수 의미로** 2로 나누면 기대 관측 차이가
평균 처치 효과다. Lean 파일은 분모를 제거한 등식까지 검사하며 별도의 확률 라이브러리를
사용하지 않는다.

`fairPairedRandomizationIdentifiesTotalEffect`는 유한 block 목록으로 등식을 더한다.
코드는 모든 block에 공통으로 첫 배정 또는 둘째 배정을 적용한 두 합계를 다룬다.
독립적인 모든 배정 벡터를 열거한 정리나 block 간 독립성을 증명한 것으로 부르지 않는다.

두 반례도 직접 계산된다.

- 각 대상의 처치 효과가 `+1`이어도 기본 점수가 `0`과 `100`인 두 대상 중 첫 대상만
  항상 처치하면 관측 차이는 `-99`다. 편향된 배정에서 관측 부호가 실제 효과와 반대다.
- 실제 효과가 둘 다 `0`이어도 배정별 관측 차이는 `-10`, `+10`이 될 수 있다.
  공정한 배정의 기대값은 0이며, 공정한 배정 자체가 양의 효과를 만들지는 않는다.

이것은 opaque `causalIdentification`을 받아 결론을 꺼내는 대신 구체적인 작은 모형의
식을 유도한 출발점이다. 기존 DNRD-5의 four-arm 의미론, 배정 발생, blinding, 실제 평가기,
독립 custody, 통계적 판정 또는 `causallyIdentified` 필드를 채운 것은 아니다.
결과를 보기 전에 비교 설계를 정한다는 연구 원칙의 외부 참고는
[Rubin의 potential-outcomes 논의](https://arxiv.org/abs/0811.1640v1)에 있다.
이 외부 논문이 이번 HSWM 구현을 검증한 것은 아니다.

## 4. 합성: 각각 좋아지는 변경을 같이 적용하면 실패할 수 있다

[HSWMCompositionInterference.lean](../../formal/HSWMCompositionInterference.lean)의 강한 반례는
같은 목적함수를 평가하는 두 cell이다. 각각은 자기 좌표만 수정할 수 있다.

| 왼쪽 상태 | 오른쪽 상태 | 공통 효용 U |
| --- | --- | --- |
| 0 | 0 | 1 |
| 1 | 0 | 2 |
| 0 | 1 | 2 |
| 1 | 1 | 0 |

처음 상태 `(0,0)`에서 왼쪽만 바꾸거나 오른쪽만 바꾸면 각각 `1 -> 2`로 개선된다.
그러나 두 변경을 모두 적용하면 `(1,1)`이 되어 `1 -> 0`으로 악화된다.
`stale_unilateral_improvements`와 `commuting_writes_have_negative_semantic_interaction`이
이 사실을 증명한다. 서로 다른 좌표에 쓰므로 이 두 쓰기 순서는 교환 가능하지만,
효용의 상호작용까지 독립인 것은 아니다.

따라서 **개별 변경의 개선 증명 + 충돌 없는 저장만으로는 합성 후 개선이 따라오지 않는다.**
이는 이 구체적인 낡은 상태 기준 병렬 적용 규칙의 반례다. 모든 HSWM 합성이 불가능하다는
증명이 아니고, 실제 HSWM 런타임에서 이 실패를 관측했다는 주장도 아니다.

두 가지 제한된 보완을 함께 증명했다.

1. `serialReevaluate`는 첫 후보를 실제 효용 비교 후 수락하고, 변경된 상태에서 둘째 후보를
   다시 비교한다. 이 표에서는 `(1,0)`을 수락하고 `(1,1)`을 거절해 효용 2를 유지한다.
   이 모형은 정확한 공통 효용을 계산할 수 있다. 현실에서는 재평가 비용, 노이즈, outcome
   지연, commit 사이의 간섭과 권한까지 별도로 다뤄야 한다.
2. 일반적인 네 정수 효용에 대해 interaction을 다음과 같이 정의하고 분해식을 증명했다.

```math
I=U_{11}-U_{10}-U_{01}+U_{00},
\qquad
U_{11}-U_{00}=(U_{10}-U_{00})+(U_{01}-U_{00})+I.
```

`additive_strict_gains_imply_joint_gain`은 `I=0`인 제한된 경우 두 국소 개선이 양수이면
공동 개선도 양수임을 증명한다. 반례의 interaction은 `-3`, 두 국소 개선은 각각 `1`이므로
공동 개선은 `-1`이다. 모든 n-ary interaction을 0으로 가정해 전체 FCL을 닫을 수는 없다.
유용한 상호작용을 허용하면서 해로운 교차 효과를 제한하는 합성 규칙이 아직 필요하다.

처음 탐색한 단순 XOR/shared-outcome overwrite 반례도 파일에 보존했다. 그 규칙은
격리된 상태에서도 좋은 학습을 보장하지 않으므로, 좋은 하위 학습기의 합성이 실패한다는
근거로는 위의 공통 목적함수 반례를 사용한다.

## 5. 세 결과를 전체 목표에 연결할 때 남는 일

세 파일은 서로 다른 제한 모형의 정리다. 이를 합친 것만으로 하나의 실제 HSWM witness가
존재하지는 않는다. 각 정리에서 사용하는 정책, 잠재 outcome, cell 상태, 시간과 intervention을
같은 구성으로 대응시키고 그 가정들이 동시에 성립함을 보여야 한다.

| 의무 | 이번에 추가한 근거 | 남은 연결 |
| --- | --- | --- |
| CR-1 | 계산되는 선택 규칙의 조건부 정수 격자 개선 | 표본에서 오차 bound 도출, 지속 관계 갱신·실제 LLM·강한 비교군 |
| CR-2 | 고정 잠재 outcome과 두 배정의 정확한 식별 등식 | 실제 배정·외부 outcome·프로토콜 의미론·불확실성 |
| CR-6 | 낡은 상태에서 평가한 병렬 개선의 반례, serial 재평가와 가법적 충분조건 | n-ary 간섭을 허용하는 효과 보존, typed 합성·권리·exit·계보 |
| CR-0/3/4/5/7 | 이번 라운드로 완료 판정을 추가하지 않음 | 같은 구성 안의 안전성·다중규모 credit·coalition·topology·world/self·연속성과 현실 연결 |

다음 구성 후보는 **같은 외부 outcome과 효용 아래 제안·평가·적용 상태를 결속하고,
다른 revision 때문에 문맥이 변하면 기존 국소 개선 증명도 재평가하는 방식**이다.
재평가 순서가 숨은 중앙 commander가 되지 않는지, 얼마나 병렬화할 수 있는지, 비용 안에서
강한 program learner와 구별되는지는 열린 질문이다. 위 두 cell의 성공으로 FCL-3/8을
통과시키지 않는다.

## 6. 재현과 주장 범위

검사 방법은 [연구 프로그램 README](../../_research/constructive_realizability_v1/README.md)에 있다.
기존 pin `leanprover/lean4:v4.32.1`과 `Std`를 사용한다. 새로운 패키지를 설치하지 않았다.
새 파일들은 명시적인 개별 Lean 명령으로 검사하며 기존 default Lake target을 변경하지 않는다.

직접 source compile, `--trust=0` 재검사, 각 named theorem의 `#print axioms`,
별도 맥락의 의미 검토를 구분해 기록한다. 표준 Lean 공리 의존성과 과학적 전제는 다른 것이다.
컴파일 성공은 전제와 결론의 논리적 연결을 확인하며 현실이 그 전제에 맞는지를 대신하지 않는다.
전체 HSWM, FCL-1..8와 과거 음성 결과의 판정은 유지한다.

이번 산출물은 알려진 유한 수학과 구체적 구성 반례의 형식화이며 새 경험적 학습 결과나
과학적 신규성 주장이 아니다. 새 F1/R8 효능 결과 행으로 계산하지 않는다. 실패한 초안,
작업 기록과 raw 출력은 로컬에 보존하고 공개 KG에는 소스에 결속된 범위·판정만 남긴다.
