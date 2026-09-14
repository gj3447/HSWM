# LLM이 실행하는 Semantic Weight와 HSWM의 학습 이론

**HSWM의 이론은 사전학습된 LLM을 의미 해석·관계 생성·실행·수정의 중심에 놓아야 한다.** 모든 단어의 의미와 관계 법칙을 사람이 먼저 완성해야 하는 설계가 아니다. LLM이 이미 배운 의미를 출발점으로 사용하고, 그 의미가 특정 세계에 적용되는 조건을 경험으로 교정하며, 그 교정이 같은 HSWM의 다음 실행과 합성에도 남도록 구성하는 것이 연구 대상이다.

이는 [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 LLM-executed transition과 일치한다. [LLM 엔진에 관한 원문](../canon/sources/USER_PRIMARY_HSWM_LLM_ENGINE_2026-09-14.txt)은 설계 방향의 USER_PRIMARY 근거다. 아래 문헌 해석·수식·실현 경로는 SECONDARY_AI이며, 원문이 이를 직접 승인하거나 과학적으로 증명한 것은 아니다. 검토 시점은 2026-09-14다.

개념적 변화는 [기존 Semantic Weight 이론](HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md)의 역할·문맥별 전이 성향에 **LLM의 사전학습 의미와 문맥 안에서의 학습을 실제 구성 요소로 명시하는 것**이다. 앞선 유한 Boolean 증명은 완전 관측 후의 관계 복원을 다뤘다. 그 증명은 LLM의 의미 prior를 이용한 적은 경험에서의 일반화를 다루지 않았다. 따라서 그것을 확대하는 일만으로 이번 문제를 해결할 수는 없다.

문헌에는 직접 쓸 만한 선행 구성이 있다. VML은 자연어를 LLM 함수의 학습 파라미터로 사용한다. VPP는 여러 자연어 가설을 LLM으로 수정한다. Pinductor는 LLM의 지식을 세계모델 후보에 활용한다. 다만 세 방법의 결과를 합쳤다는 이유로 동일한 구성에서 HSWM 전체가 성립하는 것은 아니다. 다음의 연결은 [CR-0..7](HSWM_CONSTRUCTIVE_REALIZABILITY_PROGRAM_2026-09-10.md)과 [FCL-1..8](HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md)을 그대로 남긴 연구 경로다.[^1][^2][^3]

## 1. LLM이 엔진이면 무엇을 직접 맡길 수 있는가

LLM은 자연어의 관계·유사성·예외·역할을 활용해 입력에서 중요한 조건을 찾고, 새 관계 설명과 실행을 제안할 수 있다. HSWM이 이를 활용하려면 관계를 단순한 검색용 설명으로 저장하는 데 그치지 않고, **그 관계를 읽은 LLM의 실제 전이가 바뀌게 해야 한다.** 관계의 적용 조건과 예외를 고친 뒤 같은 종류의 새 입력에서 선택·예측·행동이 달라져야 한다.

| 기존 간극 | LLM의 의미 능력에 맡길 수 있는 일 | HSWM에서 연결할 일 |
|---|---|---|
| 중요한 변수·새 관계 발견 | 관측 설명에서 누락된 조건, 매개 변수, 역할 조합, 새로운 관계 형태를 제안 | 해당 변수를 읽는 관측 경로와 경쟁 가설을 구별하는 결과를 연결 |
| 성공·실패 원인 교정 | 기대와 결과의 불일치를 설명하고 예외·범위·관계 수정안을 생성 | 자기 설명과 외부 결과를 구별하고, 수정이 새 사례에 준 효과를 확인 |
| 작은 HSWM의 합성 | 하위 관계의 역할과 조건을 해석해 상위 과제에 조합 | 하위 예외·공유 원인·미해결 가설·수정 계보가 상위 실행과 학습에 남게 구성 |

이 표의 역할은 독립 subsystem이나 고정 owner 분해가 아니다. 하나의 진화하는 canonical hypergraph를 읽고 바꾸는 같은 LLM-function 동역학의 서로 다른 사용이다. TypeScript/Effect는 그 실행의 I/O·저장·타입·허용성 경계를 구현한다. LLM이 의미를 해석하는 능력을 스칼라 점수 갱신으로 대신했다고 볼 수 없다. 반대로 정확한 산술이나 외부 동작을 도구에 위임한다고 LLM 엔진이라는 정체성이 없어지는 것도 아니다.

RAP은 LLM이 자연어 상태의 다음 변화를 예측하고 행동을 제안하는 세계모델·계획 구성을 실험했다. 이는 LLM이 코드 작성자에 머물지 않고 실행 중 상태 의미를 해석할 수 있다는 선행 근거다. MCTS와 과제별 보상·상태 표현을 사용한 실험이므로, 자기 rollout의 세계 적합성이나 지속 학습을 일반적으로 증명한 결과는 아니다.[^11]

## 2. 의미 전체보다 의미를 사용하는 계약을 먼저 정한다

“문이 잠겨 있다”의 모든 언어학적 의미를 형식화할 필요는 없다. 그러나 HSWM이 어느 문의 상태를 말하는지, 어떤 관측에 근거하는지, 그 판단으로 무엇을 하려는지는 명확해야 한다. **자연어 개념은 LLM이 해석하게 하고, 관측·행동·수정에 미치는 의미를 검사 가능하게 정의한다.** 기존 이론의 D2a grounding contract를 이 방식으로 구체화한다.

필요한 경계는 여섯 가지다.

1. **지시 대상:** 어떤 entity·event·관측을 가리키며, 이름이 바뀌어도 어느 대상을 추적하는가.
2. **역할과 문맥:** 원인 후보·대상·조건·수신자가 누구이며, 어느 상황에 적용되는가.
3. **관측 가능성:** 값을 어떤 도구·센서·문서에서 읽는가. 추측과 관측을 어떻게 구별하는가.
4. **실행 의미:** 이 관계를 사용할 때 어떤 예측·추론·행동 선택이 달라지는가.
5. **교정 조건:** 어떤 새로운 관측이 적용 범위를 줄이거나 가설을 폐기하게 하는가.
6. **불확실성과 계보:** 아직 구별하지 못한 가설, 알려진 예외, 출처와 revision을 어떻게 남기는가.

세 가지 의미를 구별하면 불필요한 선행 과제가 줄어든다. **언어적 의미**는 LLM이 활용하는 지식·연상·추론 능력이다. **실행 의미**는 특정 상태와 관계를 읽은 LLM이 만드는 전이의 법칙이다. **세계에 대한 적합성**은 그 전이가 특정 관측·개입의 결과와 맞는가라는 주장이다. 앞의 두 가지를 활용해 세 번째를 배울 수 있다. 세 번째가 이미 참이라고 정의해 놓으면 학습의 목표를 전제로 삼는 순환이 된다.

LLM 사전학습은 실제로 추가 정보다. 같은 현장 관측만 가진 무지한 학습기보다 나을 수 있다. 식별 불가능성은 **관측·허용 개입·주어진 prior까지 같아도 구별되지 않는 두 세계**를 모두 맞힐 수 없다는 경계이지, 사전 지식을 쓰지 말라는 뜻이 아니다. 반대로 익숙한 단어가 참조하는 세계 법칙이 바뀌었을 때에는 LLM이 기존 상식을 고칠 수 있어야 한다.

## 3. 가장 직접적인 AI 선행 연구

### VML: 자연어 파라미터를 LLM이 실행하고 수정한다

Xiao 등의 VML은 입력과 학습할 규칙을 토큰으로 표현하고, 고정된 LLM을 그 규칙에 의해 조건화되는 함수로 사용한다. 다른 역할의 LLM 호출은 예측·정답·현재 규칙을 보고 규칙을 수정한다. 회귀·분류와 패턴 학습 실험을 제시하며, v3에는 실패 사례와 도구를 통한 산술 오차 완화도 포함한다. 최초 공개는 2024년, 읽은 TMLR 표기 개정판은 2025-02-14 v3다.[^1]

**HSWM 적용 판단:** Semantic Weight의 자연어 내용은 설명문이면서 동시에 전이를 조건화하는 학습 가능한 상태가 될 수 있다. 기반 모델의 숫자 파라미터가 고정돼도, 경험에 따라 이 상태가 바뀌고 그 변화가 지속적으로 다음 실행에 사용되면 macro 수준의 학습을 구성할 수 있다. VML의 learner/optimizer 역할을 새 영구 subsystem으로 옮길 이유는 없다. 같은 HSWM의 입력 처리와 결과 처리에 해당하는 LLM 호출로 연결할 수 있다. 자연어 수정 사유가 읽힌다는 사실만으로 실제 내부 원인이 모두 해명되지는 않는다.

### VPP: 한 가지 설명에 고정되지 않는 자연어 가설 학습

2026-07-25의 VPP v1은 자연어 가설 여러 개를 유지하고 LLM으로 예측·수정하며, 관측 label에 대한 손실로 가설을 평가한다. 작은 회귀·분류·규칙 발견 benchmark에서 단일 VML보다 좋은 결과를 보고한다. 다만 §3.2는 MH의 prior 및 역방향 proposal 비율을 생략해 exact detailed balance가 깨진다고 명시한다. §3.3의 가중치 갱신도 정식 SMC의 incremental ratio를 보존하지 않는다. 따라서 정확한 Bayesian posterior 수렴이 증명된 방법으로 채택할 수 없다.[^2]

**HSWM 적용 판단:** 경쟁하는 의미 관계와 예외를 함께 유지하는 구성은 직접적인 후보다. 여기서 가설의 증거 가중치와 그 가설이 나타내는 Semantic Weight disposition은 다르다. “사후확률”이라는 이름이 필요하다면 실제 prior·likelihood·proposal·갱신 규칙을 먼저 정해야 한다. 이름에 맞는 정리가 없는 상태에서는 경험으로 재가중한 가설 집합으로 다룬다.

### Pinductor: 의미 prior와 부분 관측 세계모델

2026-05-13의 Pinductor v1은 LLM이 POMDP 코드를 제안하고, 관측·행동 trajectory에 대한 belief 기반 점수와 오류 진단으로 수정한다. 숨은 상태의 정답 label을 제공하지 않는 MiniGrid 실험에서 기존 LLM 기준과 비슷한 성과를 보고했다. 의미 있는 환경·객체 이름을 덜 유익한 이름으로 바꾸면 성능이 하락했다. 다만 상태·행동·관측 공간의 API, 수집된 trajectory와 관측 거리 정의가 제공된다. 새로운 latent ontology 전체를 발견한 실험은 아니다.[^3]

**HSWM 적용 판단:** LLM 의미 지식을 무시한 전수 탐색보다 좋은 관계 후보를 먼저 만드는 방향을 뒷받침한다. 이 논문은 생성한 코드를 실행하는 구성이므로, LLM이 매번 관계를 해석하는 HSWM 전이와의 동등성을 그대로 주장할 수는 없다. HSWM에서는 LLM이 실행하는 관계 후보를 유지한 채, 사전 예측과 실제 outcome의 불일치를 수정 입력으로 되돌리는 원리를 취한다.

### 최신 인과 발견과 지속 기억의 시사점

Li–Russo의 UAI 2026 표기 논문은 LLM이 제안한 인과 제약과 통계적 조건부 독립 증거를 결합한다. 2026-08-11 v2가 사용하는 Causal ABA의 기호적 틀은 입력 제약과 산출 그래프의 대응을 다룬다. 이 논문이 LLM 제약의 참에 관한 새 정리를 증명한 것은 아니다. 낮은 품질의 LLM 제약이 최종 그래프를 악화시키는 ablation과, 정답 그래프에서 생성한 metadata를 사용한 평가 한계도 명시한다.[^9]

EvoMemBench의 2026-06-15 v2는 기억 보존과 기억 수정을 나눠 비교한다. 원본 긴 문맥이 강한 기준이며, 검색·요약 기억은 특히 기존 정보를 수정하는 과제에서 어려움을 보인다. **HSWM 적용 판단:** LLM에 의미가 풍부한 문맥을 주는 설계 자체를 약한 기준으로 취급하면 안 된다. 같은 LLM이 원본 경험을 읽는 경우보다 그래프의 관계 revision이 언제 도움이 되는지 비교해야 한다.[^10]

## 4. 이미 증명된 수학을 어디에 사용할 수 있는가

| 근거 | 논문에서 증명한 범위 | HSWM에서 사용할 연결 | 추가 의무 |
|---|---|---|---|
| Xie 등, ICLR 2022 | HMM latent concept들의 문서 생성 모형과 distinguishability 조건에서 정확한 분포 예측기의 ICL이 prompt의 Bayes-optimal risk로 수렴 | 사전학습 분포와 문맥이 관계 가설 추론을 가능하게 하는 이론 | 실제 LLM·환경의 근사 오차, 영속 기억, 행동·개입 연결 |
| von Oswald 등, ICML 2023 | 선형 self-attention 한 층에 선형 회귀 GD 한 단계를 구현하는 가중치 구성 | forward pass 자체가 학습 연산을 실현할 수 있음 | 일반 softmax LLM에서 해당 동작이 학습됐는가와 반복 안정성 |
| Wakayama–Suzuki, 2026-06 v3 | squared risk 분해와, 지정된 uniform-attention·meta-learning 조건의 유한 표본 Bayes Gap 상계 | 모델이 잘못 해석한 오차와 자료가 부족해서 남는 불확실성의 분리 | 순서·drift·능동 개입을 포함한 HSWM 데이터에서의 새 상계 |
| Hutter, JMLR 2003 | 선언한 확률모형족과 양의 prior를 사용하는 정확한 혼합 예측의 손실·수렴 경계 | 의미 prior를 가진 관계 가설의 경험 갱신을 정량화 | 실제 LLM 갱신이 혼합 규칙을 실현하는가, 참 모형 지원·계산 비용 |
| Ahuja 등, 개입적 표현 학습 | 다항 decoder의 rank·support·재구성 조건과 지정된 do 개입에서 개입된 좌표의 shift/scale 식별 | 가정을 구현한 관측모형에서 잠재 좌표 식별을 시험하는 경로 | 그 관측·개입 조건 확보, 남은 좌표·referent 대응, 유한 표본 학습 |

앞의 첫 두 정리는 일반 사전학습 LLM의 내부가 항상 Bayes 또는 GD라는 주장이 아니다.[^4][^5] 세 번째 논문의 risk identity는 구조에 덜 의존하지만, 유한 표본 상계는 조건부 IID 예시, boundedness·regularity와 uniform attention에 의존한다. 능동적으로 고른 관측이나 시간 순서가 중요한 관계에 mean pooling을 그대로 적용할 수 없다.[^6]

다섯 번째 결과의 중요한 전제는 단순한 “개입이 있다”보다 강하다. Ahuja 등의 §4–5에는 full-column-rank 다항 decoder, 비어 있지 않은 support 내부, 재구성·noncollapsing encoder 및 개입 출력 좌표에 대한 제약이 있다. Theorem 5.3은 관측 분포와 특정 좌표를 고정하는 hard intervention으로 **그 개입 좌표**를 shift/scale까지 식별한다. 일반 diffeomorphism으로 넓힌 부록 결과는 더 많은 개입과 근사적인 식별을 다룬다. 이 정리에서 자연어 이름의 고유한 의미나 현실의 잠재 변수를 자동으로 얻는 것은 아니다.[^8]

## 5. 의미 prior의 이득을 먼저 정리로 만들 수 있다

다음은 고전적인 혼합 예측 부등식을 HSWM의 관계 가설에 연결한 **분석적 유도**다. 새로운 발견이나 Lean 검증 결과가 아니다.[^7] 임의의 LLM이 아래 갱신을 이미 수행한다고 가정하지 않는다.

유한한 가설 집합을 H라 하자. 각 h는 LLM이 해석하는 역할·조건·예측 규칙을 가진다. 평가 구간이 시작되기 전에 가설별 정규화된 예측 법칙 p_h와 prior π₀를 정한다. π₀(h)>0이고 합은 1이다. 가설 생성에 쓴 경험은 prefix로 조건화하고, 아래 결과는 이후의 새로운 outcome 구간에 적용한다. h의 내부 예측 상태가 변한다면 그 갱신 법칙도 사전에 정의된 p_h의 일부여야 한다.

```math
q_t(y)=\sum_{h\in H}\pi_{t-1}(h)\,p_h(y\mid\mathcal F_{t-1},a_t),
```

```math
\pi_t(h)=\frac{\pi_{t-1}(h)\,p_h(y_t\mid\mathcal F_{t-1},a_t)}{q_t(y_t)}.
```

여기서 F는 허용된 과거 관측 이력이다. a_t는 과거 이력과 outcome 이전에 계산된 예측에만 의존하는 non-anticipatory 정책으로 선택하며, 무작위 정책이면 그 외부 난수도 정보 범위를 명시한다. 모든 p_h는 같은 실제 행동 이력에 조건화된 sequential predictive law다. q_t(y_t)>0인 구간에서 Bayes 갱신을 정확히 수행하면 telescoping으로 다음이 성립한다.

```math
\prod_{t=1}^{T}q_t(y_t)
=\sum_{h\in H}\pi_0(h)\prod_{t=1}^{T}p_h(y_t\mid\mathcal F_{t-1},a_t)
\geq\pi_0(h_*)\prod_{t=1}^{T}p_{h_*}(y_t\mid\mathcal F_{t-1},a_t).
```

따라서 비교 가설 h_*도 관측 결과에 양의 확률을 주는 경우, 자연로그 log-loss에는 다음 경계가 있다.

```math
\sum_{t=1}^{T}\big[-\log q_t(y_t)+\log p_{h_*}(y_t\mid\mathcal F_{t-1},a_t)\big]
\leq\log\frac{1}{\pi_0(h_*)}.
```

**의미 지식과의 연결:** 유용한 가설에 더 큰 초기 질량을 주면 이 상계의 prior 비용이 작아진다. LLM이 언어적 지식으로 그 가설을 더 잘 생성하고 우선시할 수 있는지는 측정할 가설이다. LLM이라는 이름만으로 좋은 prior가 되는 것은 아니다. 가설의 언어적 확신·token likelihood와 외부 outcome의 p_h는 서로 다른 양이다.

이 부등식 자체는 실제 선택한 행동 경로에서의 상대적 예측 손실이다. 참 환경이 가설족에 들어 있다는 가정 없이도 비교 가설에 대한 형태는 성립하지만, 그 비교 가설이 세계에 잘 맞는다는 결론은 생기지 않는다. 탐색하지 않은 행동의 인과 효과·좋은 제어 정책·다음 과제 효용 향상도 따라오지 않는다. 가설족 누락과 나쁜 prior는 그대로 실패 원인이다.

**현실 LLM로 옮기는 방법:** LLM이 만든 유한 후보를 잠시 고정하고, 선언한 관측모형으로 정확히 재가중하면 black-box LLM의 제안 확률을 몰라도 후보 집합에 조건부인 정리를 만들 수 있다. 구조를 계속 바꾸려면 새 후보를 도입하는 전이까지 포함한 확장 정리가 필요하다. 또는 계산 가능한 prior·정방향/역방향 proposal과 정확한 likelihood를 사용해 MH를 구성할 수 있다. 이 경우에도 invariant distribution과 유한 시간의 혼합·계산 효율은 별도로 증명해야 한다. prior 비율을 계산할 수 있다는 사실만으로 실제 세계에 맞는 likelihood가 생기지는 않는다.

LLM이 정확한 q 대신 근사 예측을 실행한다면 그 오차도 정리에 넣는다. 예를 들어 실제 평가 경로에서 두 예측 모두 관측 outcome에 양의 확률을 주고 log probability 차이의 절댓값이 회당 η_t 이하라는 가정을 확보하면, 전체 경계에는 그 합이 추가된다. 이를 이름만 있는 oracle 전제로 남기지 않고 실제 LLM·프롬프트·읽기 범위에서 확보하는 것이 CR-7의 의무다.

## 6. 하나의 LLM 동역학으로 연결하는 구성

동일한 schema-approved state S_t와 LLM θ가 있다고 하자. e_t는 실행할 typed relation이고, z_t는 현재 입력 또는 이미 도착한 outcome 사건이다. 관계의 의미와 허용된 현재 상태를 인코딩해 LLM이 다음 전이 제안을 산출한다.

```math
u_t\sim\mathrm{LLM}_{\theta}\!\left(
\mathrm{Encode}_{\sigma_t}(e_t,\mathrm{Read}_{\sigma_t}(S_t),z_t)
\right).
```

u_t에는 그 event kind가 허용하는 예측·행동·관계 revision 후보가 들어간다. 예측과 의미 변환은 이 LLM 호출 자체가 실행한 결과다. 영속 상태 변화와 외부 동작은 기존 schema의 타입·owner·Inv/Permit·lineage를 따라 적용하며, 이 경계가 LLM의 의미 판단을 대신하지 않는다. 이 수식은 한 HSWM에서 실행과 학습을 표현하는 후보 문법이며, 별도 인지 엔진을 추가하는 분해가 아니다. 모델 revision·decoding·cache처럼 결과에 영향을 주는 조건도 실행 상태나 명시된 주변 조건에 포함한다.

```text
같은 graph의 관계·예외·근거를 LLM이 읽음
→ 예측과 행동을 생성하고 outcome 이전의 사용 관계를 기록
→ 외부 세계가 결과를 제공
→ 같은 graph와 결과를 LLM이 읽어 관계의 조건·예외·구조를 수정 제안
→ 유효한 revision이 다음 실행의 읽기와 행동을 조건화
```

Semantic Weight의 실행 성향은 이때 LLM·관계 내용·문맥·상태에 의해 유도되는 전이 법칙이다. 자연어 문장만 떼어 독립적인 함수라고 간주하면 LLM 버전과 문맥에 따른 차이를 놓친다. 반대로 상태마다 전부 독립인 black box라고만 정의하면 재사용·합성·학습에 관한 이론을 만들기 어렵다. 고정된 해석 조건 아래 어떤 표현 변화가 행동을 바꾸며, 어떤 변화는 같은 의미로 보존되는지를 다룬다.

가설·반례·미확정 주장도 schema가 허용하면 canonical claim atom으로 저장할 수 있다. LLM 제안, 관측상 지지, 개입 근거에 의한 지지, 반증·폐기를 각각 출처·가정과 함께 구별한다. **canonical 저장, 내용의 진실성, causal efficacy는 각각 다른 판정**이다. 관측 결과와 맞았다는 사실은 인과 식별 가정을 대신하지 않는다. 전이가 관계를 읽고 결과로 교정되는 연결이 있어야 macro-learning의 후보가 되며, 단지 KG에 문헌 노드를 추가하는 일은 그 학습이 아니다.

## 7. 합성에서 LLM의 의미 이해를 어떻게 활용할 것인가

상위 LLM은 하위 셀의 결과를 단순 문자열로 이어 붙이는 것보다, 관계의 적용 범위와 예외를 읽어 조합할 수 있다. 따라서 합성 인터페이스에는 필요에 따라 하위의 예측, 경쟁 가설, 근거 공유 여부, 알려진 반례와 revision 참조가 들어가야 한다. 항상 전체 하위 상태를 복제하라는 뜻은 아니다. **상위의 실행뿐 아니라 새 outcome을 받은 뒤 하위 관계를 고치는 데 충분한 정보**를 보존해야 한다.

기존 P1과 Lean quotient 결과는 바로 이 보존 조건을 다룬다. 실제로 작동하는 LLM 의미 요약을 제시하고 그 조건을 확인하는 것은 남아 있다. 예를 들어 두 하위 셀이 같은 잘못된 관측을 사용했다면, 상위가 이를 두 개의 독립 증거로 취급해서는 안 된다. 하위의 답이 각각 그럴듯해도 결합 불확실성은 주변 확률만으로 결정되지 않는다.

확률적 확장에서는 유한 step 수와 공동 상태를 먼저 정할 수 있다. 비교하는 두 실행의 초기 상태가 같고, 모든 공통 prefix의 동일한 공동 상태·이력에서 다음 **공동 전이**의 total variation 차이가 회당 ε_t 이하라고 하자. 유한 공간에서 처음 달라질 때까지 단계별 최대 coupling을 유지하면, union bound로 두 trace가 달라질 확률과 전체 trace 법칙의 TV 거리를 min(1, Σε_t) 이하로 제한할 수 있다. 이 전이는 실행·학습·허용성 관련 출력까지 포함하며, 서로 다른 초기 분포에는 초기 TV 오차도 더해야 한다. 개별 child의 주변 출력 오차만으로 이 전제를 확보할 수 없다.

이 역시 조건부 분석이다. 실제 LLM에서 작은 ε_t를 보이거나, 관계 요약이 비용을 줄이면서 그 경계를 유지한다는 정리를 만들어야 유용하다. 유한 trace 근접성 자체가 상위 인지의 추가 효용, 다중 규모 credit, identity·exit·restore의 보존을 모두 증명하지는 않는다.

## 8. 다음 증명과 실험의 우선순위

다음 이정표는 **LLM이 의미 관계를 생성하고 실행하며, 제한된 새로운 경험으로 그 관계를 교정하는 하나의 구성**이다. 모든 입력의 정답을 관측한 후 복원하는 이전 유한 모형과 구별해야 한다. 그렇다고 최종 목표를 작은 학습기로 축소하지 않는다. 기존 [적응적 연구 전략](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)에 따라 이 구성의 실패 범위를 보존하고 경로를 바꿀 수 있다.

| 순서 | 구체적인 의무 | 완료를 주장하기 위한 근거 | 기존 연결 |
|---|---|---|---|
| 1 | LLM이 읽고 실행하는 관계 언어와 관측·행동 의미를 지정 | 의미가 같은 paraphrase, 역할 교환, 실제 법칙 변경을 구별하는 명시적 전이·오차 계약 | CR-0/4/7, FCL-3/5 |
| 2 | 의미 prior가 관계 탐색에 유용한지 확인 | 같은 LLM·정보·예산의 강한 기준과 비교한 후보 품질·샘플 비용; 실패 비용 포함 | CR-1/4, FCL-1/5 |
| 3 | 경쟁 관계를 outcome으로 교정 | §5의 실제 갱신 규칙과 가정, 허용 개입 범위의 식별, 새 사례 예측과 효용을 별도 측정 | CR-1/2/3, FCL-1/4 |
| 4 | 영속 의미 상태가 다음 실행과 학습에 사용됨을 확인 | 같은 LLM에서 revision 제거·복원·sham, 예외 보존, 새 사건의 행동 변화 | CR-5/7, FCL-6/7 |
| 5 | 셀 합성이 실행·학습·불확실성을 보존 | 공동 상태와 요약 사상, 공유 원인·지연·간섭, 유한 깊이 오차·비용·권리 경계 | CR-3/6/7, FCL-2/4/8 |

예를 들어 문 제어의 언어적 micro-world를 사용할 수 있다. LLM은 “잠김”·“전원”·“센서 지연”을 해석하고 관계 후보를 만든다. 초기 구성에 없는 조건이 실패를 설명하면, 그 조건을 읽을 수 있는 관측을 제안한다. 환경이 결과를 준 뒤 관계를 수정하고 새 상황에서 실행한다. 이는 제안된 실험이며 수행한 결과가 아니다.

판별에는 익숙한 의미가 맞는 세계, 익숙한 의미에 예외가 있는 세계, 새 명칭이지만 동일 법칙인 세계를 포함한다. 의미 있는 이름을 완전히 숨기는 실험은 prior 정보를 제거하는 ablation이지, 모든 이름 변화에 불변이어야 한다는 요구가 아니다. 관측에도 없는 정답을 맞히라는 과제를 만들지 않는다. 기준은 동일한 LLM의 원본 긴 문맥, frozen relation, 단일 자연어 가설 학습, graph revision 학습이며 관측·token·실패한 후보 생성 비용을 함께 맞춘다.

먼저 확보할 수 있는 범위는 조건부 예측·교정·유한 합성이다. 전체 HSWM을 위해서는 여전히 새로운 변수·상호작용의 실질적 발견, 인과 credit, 같은 graph의 world/self prediction, 통시적 연속성, 재귀적 인지 합성이 필요하다. 여기의 구성은 그 질문을 LLM의 실제 의미 능력 위에서 연구하기 위한 제안이다. **LLM의 의미 능력을 전부 다시 만드는 문제가 아니라, 그 능력이 경험을 통해 안정적으로 바뀌는 HSWM 동역학을 만드는 문제로 설정한다.**

## 9. 현재 근거와 연구 기록

[기존 구성적 증명](HSWM_SEMANTIC_WEIGHT_CONSTRUCTIVE_PROOF_2026-09-14.md)의 Lean 결과는 고정된 세 Boolean 입력, 전수 관측, 정확한 유한 관계 복원과 일부 refinement다. 이번 조사에서 실제 LLM 실행, 효율적 의미 일반화, causal credit 또는 FCL 전체의 새 증명은 추가하지 않았다. 본문의 고전 부등식 적용과 유한 coupling 설명도 Lean kernel에서 새로 확인한 결과가 아니다.

문헌별 source version·읽은 절·가정·연결은 [연구 catalog](artifacts/hswm_llm_semantic_engine_2026-09-14/research.v1.json), 그 관계 투영은 [KG snapshot](../../ontology/development/HSWM_LLM_SEMANTIC_ENGINE_RESEARCH_2026-09-14.v1.json)에 둔다. 그래프는 원문 결과, HSWM 적용 제안, 기존 미완료 의무를 구별한다. [검증 기록](artifacts/hswm_llm_semantic_engine_2026-09-14/validation.v1.json)은 파일·출처·그래프 구조 검사이며 과학적 실현 증명이 아니다.

## Sources

[^1]: Tim Z. Xiao, Robert Bamler, Bernhard Schölkopf, Weiyang Liu. [Verbalized Machine Learning: Revisiting Machine Learning with Language Models](https://arxiv.org/html/2406.04344v3). 최초 2024-06-06, v3 2025-02-14; TMLR 표기. §3, §4.10, §5, Appendix G·K.
[^2]: Yan Zhang, Shikan Lian, Shibo Li. [Verbalized Particle Posterior: Bayesian Inference over Natural Language Hypotheses](https://arxiv.org/html/2607.22961v1). 2026-07-25 v1, preprint. §2–3, §5–6.
[^3]: Valentin Six et al. [Learning POMDP World Models from Observations with Language-Model Priors](https://arxiv.org/html/2605.13740v1). 2026-05-13 v1, preprint. §3–6, Appendix G·H.
[^4]: Sang Michael Xie, Aditi Raghunathan, Percy Liang, Tengyu Ma. [An Explanation of In-context Learning as Implicit Bayesian Inference](https://arxiv.org/html/2111.02080v2). ICLR 2022. Condition 1, Theorems 1–3 and setup.
[^5]: Johannes von Oswald et al. [Transformers Learn In-Context by Gradient Descent](https://proceedings.mlr.press/v202/von-oswald23a.html). ICML 2023, PMLR 202, pp.35151–35174. Proposition 1 and linear-regression construction.
[^6]: Tomoya Wakayama, Taiji Suzuki. [In-Context Learning Is Provably Bayesian Inference: A Generalization Theory for Meta-Learning](https://arxiv.org/html/2510.10981v3). 2026-06-14 v3, preprint. Definition 2.2, Proposition 3.1, Theorem 3.2, Appendix C.
[^7]: Marcus Hutter. [Optimality of Universal Bayesian Sequence Prediction for General Loss and Alphabet](https://www.jmlr.org/papers/volume4/hutter03a/hutter03a.pdf). JMLR 4, 2003, pp.971–1000. §2.2–2.5, especially mixture dominance (2) and Theorem 1. 본문의 행동 조건부 경로 부등식은 그 유한 혼합 논리를 명시적으로 적용한 유도다.
[^8]: Kartik Ahuja, Divyat Mahajan, Yixin Wang, Yoshua Bengio. [Interventional Causal Representation Learning](https://arxiv.org/html/2209.11924v4). 2024-02-22 v4. Assumptions 4.1–4.2, Constraints 4.3/5.2, Theorem 5.3, Appendix A.12.
[^9]: Zihao Li, Fabrizio Russo. [Leveraging Large Language Models for Causal Discovery: a Constraint-based, Argumentation-driven Approach](https://arxiv.org/html/2602.16481v2). 2026-08-11 v2; UAI 2026 표기. §3–6, metadata and prior-quality limitations.
[^10]: Yuyao Wang et al. [EvoMemBench: Benchmarking Agent Memory from a Self-Evolving Perspective](https://arxiv.org/html/2605.18421v2). 2026-06-15 v2, preprint. §3–5, especially §5.2.1.
[^11]: Shibo Hao et al. [Reasoning with Language Model is Planning with World Model](https://aclanthology.org/2023.emnlp-main.507/). EMNLP 2023, pp.8154–8173. LLM world-model/action-policy and MCTS construction.
