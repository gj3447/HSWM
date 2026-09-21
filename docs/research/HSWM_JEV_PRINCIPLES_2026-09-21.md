# Jev의 결정 원리를 HSWM의 국소 의미 연산에 적용하기

2026-09-21 · `SECONDARY_AI` · 목표 정체성 유지, 구현과 효능은 별도 판단

HSWM은 하나의 큰 AI이며, 하이퍼그래프 신경망 조직 안에서 LLM 함수를 기본 계산 단위로 사용하고 하이퍼그래프 Semantic Weight로 작동한다. 큰 그래프가 AI의 상태이고 LLM은 작은 국소 입력을 읽는 내부 연산자다. 이번 변경은 이 연산자의 **출력을 읽고 검증하는 방식**이다. 새 분류기를 HSWM 밖에 붙여 전체 시스템을 대신하는 설계가 아니다. 그래프의 의미를 학습하는 것과 LLM 체크포인트를 학습하는 것은 서로 다른 개입으로 측정한다.

이번에는 기존 native 그래프의 의미·역할·문맥·예외·훈련 근거를 읽고, 같은 Qwen3-4B로 `0/1` 후보의 logprob를 직접 읽는 경로와 JSON으로 판정·확률을 생성하는 경로를 DGX에서 비교했다. calibration 전용 사례에서 온도를 맞추고 별도 test에서 평가한다. 실행 결과와 채택 판단은 [결과 보고서](../../results/HSWM_JEV_PRINCIPLES_2026-09-21.md)에 고정한다. 운영 기본 경로를 바꾸지는 않으며, 새 native 순수 함수는 연구 실행기에서 사용한다.

## 1. 공개 원리와 이번 구성의 정확한 차이

[TypeSafe의 설명](https://docs.typesafe.ai/introduction/machine-learning-primer)은 텍스트 생성 대신 결정과 보정된 확률을 반환하는 RLCD를 제시한다. [공식 primitive 문서](https://docs.typesafe.ai/primitives)는 같은 state를 읽는 여러 typed 질문을 설명한다. 공개 문서에서 확인한 것은 출력 계약과 설계 방향이다. 이 조사 범위에서 재현 가능한 RLCD의 전체 손실·훈련 데이터·옵티마이저·신경망 구현은 확인하지 못했다.

따라서 **기존 LM의 마지막 토큰 확률을 정규화하는 구성은 Jev 자체나 RLCD 재현이 아니다.** 이번에는 공개 원리 중 직접 typed 결정 읽기와 outcome을 이용한 확률 보정을 독립적으로 구성했다. [Guo 등의 온도 보정 연구](https://proceedings.mlr.press/v70/guo17a.html)는 두 번째 구성의 직접 참고 문헌이다. 구현은 사전 고정한 작은 온도 격자를 사용하므로 논문의 최적화 절차와도 구분한다.

## 2. 핵심 원리별 적용 구조

| 원리 | HSWM에서 적용할 정확한 자리 | 이번 상태 | 반드시 확인할 반례·경계 |
|---|---|---|---|
| P1. 언어 생성과 typed 결정을 분리 | 기존 relation version을 읽은 국소 LLM의 출력 계약과 trace | native 순수 함수 및 DGX 비교 실행 | 형태가 정확해도 의미가 틀릴 수 있음. 현재 고정된 이진 후보만 검사 |
| P2. 실제 outcome으로 확률 평가·보정 | 동일한 연산 계약과 relation version에 결속된 예측 평가 | calibration/test 분리, NLL·Brier·온도 보정 실행 | 보정으로 argmax 정답률은 바뀌지 않음. 확률·증거량·인과 credit은 서로 다름 |
| P3. 같은 state를 읽는 판단의 계산 공유 | 같은 snapshot을 읽고 의존성이 없는 국소 실행들의 스케줄링 | 설계만 검토. 이번 HTTP 호출은 직렬 | 다른 판단의 결과가 필요하면 새 단계가 필요. concurrent write와 stale snapshot은 별도 문제 |
| P4. 결정 공간도 상황에 맞게 구성 | relation·role incidence·문맥에 의해 후보 전이를 구성하는 graph Step/Learn | 기존 의미 수정만 재사용. 후보·토폴로지 발견은 미구현 | 올바른 후보가 목록에 없으면 후보 내 확신은 무의미. `other/expand`와 후보 recall을 별도로 평가 |
| P5. 개별 결정 대신 필요한 공동 법칙 보존 | role-bearing hyperedge의 공동 메시지·전이 제안 | 이론적 적용 조건만. 공동 출력 실험 없음 | 주변확률의 곱은 독립성을 가정한다. 배타·상보·삼중 상호작용을 잃는지 검사 |
| P6. 작은 typed 계약을 반복 합성 | 같은 HSWM 법칙을 유지하는 cell 및 상위 HSWM의 경계 | 프랙탈 전이 가설. 구현·실험 없음 | 하위 정확도와 calibration이 상위에서도 보존되는 것은 아님. 두 scale에서 개입 효과·lineage를 측정 |

P1–P3은 TypeSafe 공개 설계에서 가져온 원리의 적용이다. P4는 동적인 HSWM 그래프에 필요한 확장이고, P5–P6은 HSWM의 기존 공동 성향·프랙탈 계약이 부과하는 조건이다. 모두 Jev가 이미 해결한 기능이라고 서술하지 않는다.

## 3. Semantic Weight와 확률의 관계

Semantic Weight는 숫자 하나가 아니라 역할·문맥에 따른 **공동 전이 성향 전체**다. 이번 이진 확률은 그 성향을 특정 국소 입력에서 측정하는 아주 좁은 출력이다. 저장된 의미, 현재의 모델 예측, 세계의 실제 결과, 개입의 인과 효과는 구분한다.

```math
p_1=\frac{\exp(\ell_1)}{\exp(\ell_0)+\exp(\ell_1)},\qquad
m=\exp(\ell_0)+\exp(\ell_1).
```

`p1`은 두 토큰에 조건화한 확률이다. 원래 두 후보의 전체 질량 `m`도 기록한다. 서버의 후보 제한이 raw logprob 자체를 이미 정규화했다고 가정하지 않는다. 한 후보가 top-logprob 응답에서 빠지면 확률을 보충하지 않고 거부한다. 두 후보 내 확신이 높아도 원래 모델이 다른 응답을 선호할 수 있고, 이 확률이 정답 확률이라는 보장은 없다.

온도 보정은 `logit(p1)/T`에 sigmoid를 적용한다. `T>0`이므로 argmax를 유지한다. 0과 1로 출력된 확률은 이 구현에서 그대로 남는다. NLL 계산만 수치적 clip을 사용하며 그 설정을 기록한다. 보정 후 NLL이 내려가도 평탄한 `p1=0.5` 기준보다 나쁘면 유용한 분별력이 입증되지 않은 것이다.

행동 분포와 결과 예측도 구분해야 한다. “이 행동을 선택할 확률”은 “이 행동을 했을 때 성공할 확률”과 다르다. 후자는 상태·행동·관측 범위에 결속하고, 선택은 효용과 비용을 함께 고려해야 한다. 이번 authored binary 환경은 이 두 종류를 분리 학습하거나 실제 인과 효과를 식별한 실험이 아니다.

## 4. 왜 병렬 결정과 공동 결정은 다르게 다뤄야 하는가

예를 들어 두 출력이 항상 반대여야 하는 관계에서 각 출력의 주변확률이 각각 0.5라면, 주변분포의 곱은 금지된 같은 값에도 총 0.5를 배정한다. 반대로 `00/11`만 가능한 관계도 같은 주변확률을 갖는다. 개별 출력의 정확한 주변확률만으로 어느 공동 법칙인지 정할 수 없다.

따라서 여러 질문을 같이 처리한다는 계산상의 독립성과, 세계 변수들의 통계적 독립성을 혼동하면 안 된다. HSWM에서는 (a) 공동 후보 전이 자체를 읽거나, (b) 명시한 조건부 factorization을 사용하거나, (c) 허용 공동 상태를 보존하는 factor 표현을 선택해야 한다. 어느 선택도 전체 n-ary 구조가 저절로 학습됐다는 증거가 아니다. [정의·표현 연구](HSWM_SEMANTIC_WEIGHT_DEFINITION_AND_HYPERGRAPH_2026-09-14.md)의 tagged incidence 보존 결과와 pair-only 손실 범위를 그대로 유지한다.

## 5. 다음 실험을 결정하는 기준

1. **국소 의미 실행부터 해결한다.** 정확한 oracle 관계를 주어도 실행하지 못한다면 토폴로지나 scale을 늘려 그 실패를 덮지 않는다. 현재 run의 oracle·frozen·learned 결과를 먼저 비교한다.
2. **학습된 결정 출력을 별도 개입으로 시험한다.** 직접 logprob가 부정확하다면 이미 결정 학습된 모델과 동일 기반 모델의 supervised 결정 학습을 각각 독립 조건으로 둔다. proper loss는 사용 가능한 방법이며 RLCD라는 명칭을 붙이지 않는다. 학습 데이터·비용·새 사례·모델 변경 효과를 구분한다.
3. **후보와 국소 읽기를 검사한다.** 같은 local read가 서로 다른 정답 상태를 합쳐 버리는지를 확인하고, 부족하면 schema가 허용한 추가 읽기 후보를 구성한다. full-context·fixed-read·learned-read를 같은 예산으로 비교한다. `other/expand`는 고정 후보의 누락을 드러내는 수단이며 자율적 지식 창출의 증명이 아니다.
4. **그 다음 공동 법칙과 병렬 실행을 시험한다.** 동일 모델·snapshot·정보·비용에서 serial, batch, 실제 공유 연산을 구분한다. 메모리·시간·결합 제약 위반·stale revision을 함께 측정한다. 이번 token 출력 절약을 공유 trunk의 성능으로 환산하지 않는다.
5. **마지막으로 두 scale 합성을 검사한다.** 하위·상위 모두에서 동일한 typed Step/Learn, 권한·충돌·exit·provenance, outcome 개입 효과를 검사한다. 상위 wrapper의 정확도만으로 FCL-2/8을 완료 처리하지 않는다.

온도 보정은 그래프 내용의 의미 수정이 아니다. 이번 T는 결과 분석의 별도 보정 artifact이며 canonical graph에 기록하거나 후속 연산에 적용하지 않았다. 다음에 보정을 지속 상태로 사용할 경우 relation/model/출력 계약 버전과 calibration 표본·시간 범위를 결속하고, 새 outcome 뒤 stale 보정을 무효화하는 규칙이 필요하다.

## 6. 기존 목표와의 연결 및 필수 비교 대상

P1은 CR-0의 출력 계약을 좁게 구체화하지만 full permitted Step/Learn을 완성하지 않는다. P2는 CR-1/FCL-1의 후보 측정이며 CR-2의 인과 식별과 CR-3/FCL-4의 다중 scale credit을 제공하지 않는다. P4–P5는 CR-4/FCL-3·5에 닿는다. 예측을 자기 구조에 결속하는 일은 CR-5/FCL-6·7, P3·P6의 합성 보존은 CR-6/FCL-2·8에 연결된다. CR-7의 동시 witness와 외부 타당성은 남아 있다.

[기존 Hyperon 조사](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)의 persistent metagraph와 neural read/write bridge는 필수 비교 대상이다. 기존 조사에 고정된 MeTTa `0.2.10`, commit `3f76dc460da6961f57f69f6c3e550c59c74ada83`와 각 bridge의 구현·prototype·설계 수준을 구분한다. 이 run은 Hyperon을 실행하지 않았으며 backend 채택이나 우위를 판정하지 않는다. 비교할 것은 같은 관측·비용 아래 관계 수정이 새 판단에 미치는 효과와 합성 보존이다.

새 KG snapshot은 source → principle → 적용 구조 → 관측 → 남은 CR/FCL 의무를 연결한다. 기존 negative 결과와 prior snapshot을 보존한다. RDF projection과 SHACL 통과는 자료 구조·출처의 검증이며 HSWM 인지·학습이나 전체 연구 자료의 완결성 증명이 아니다.
