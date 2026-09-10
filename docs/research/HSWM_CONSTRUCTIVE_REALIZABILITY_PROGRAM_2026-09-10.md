# HSWM 구성적 실현가능성: 증명할 경로와 남은 가정

2026-09-10 · `SECONDARY_AI / PROOF_PROGRAM_AND_ANALYTIC_DERIVATION`.

**현재 판정:** 전체 실현가능성은 미증명이다. 아래에는 기존 정리의 전제 감사,
고전적 유한 선택 학습의 작은 유도, 전체 목표를 향한 미해결 증명 의무를 둔다.
새 Lean 정리, 실제 모델 효능, FCL 통과 또는 새 과학적 발견을 보고하지 않는다.

## 1. 사용자 방향, 정본 역할과 개념적 변화

사용자는 나비에–스토크 연구처럼 과학적으로 정밀하게 진행하고, 먼저
“이러한 조건과 구성으로 HSWM 목표를 달성할 수 있다”는 근거를 세우라고 요청했다.
이 방향은 `USER_PRIMARY`이며 아래 정리 분해·가정·연구 순서는 `SECONDARY_AI`다.

목표는 [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 token-native
LLM-function macro-neural HSWM이다. 같은 evolving canonical hypergraph가
living harness, world/self model, continuous learner로 작동하고, cognition-bearing
HSWM이 다시 상위 HSWM의 cell이 되어야 한다.
[FCL-1..8](../canon/USER_PRIMARY_HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.md),
[과학적 연결과 비주장](HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md),
[목표 유지·방법 교체 원칙](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)을 유지한다.

**개념적 변화:** 이미 좋은 결과가 있다는 증거를 연결하는 조건부 정리에서 더 나아가,
명시한 환경 가정 아래 실제 알고리즘이 그 결과를 만들어내는지를 증명 대상으로 삼는다.
이는 기존 안전성 정리를 버리거나, 실험을 영구히 미루는 새 승인 조건을 만드는 일이 아니다.
구성적 증명과 가정 점검용 작은 실험은 서로를 수정하며 진행한다.

이 문서는 schema·canonical atom·owner를 새로 만들지 않는다. 후속 구성은 기존
schema-relative single owner, typed reference, provenance-bound Step/Learn,
Inv/Permit 경계에 매핑해야 한다. 문서와 연구 그래프는 그 연구의 bounded projection이다.

## 2. OpenAI 사례에서 가져오는 구체적인 기준

OpenAI의 [공식 형식화 저장소](https://github.com/openai/NavierStokesAndEuler/blob/main/README.md)는
양의 점성 각각에 대해 초기조건·외력의 존재와 해의 붕괴를 명시하고 Lean 형식화를 제공한다.
HSWM에 적용할 기준은 **정확한 양화·가정·구성·결론, 읽을 수 있는 증명,
기계 검증과 별도 검토**다. 이 문서 작성 중 그 Lean 프로젝트를 빌드하거나 증명을
독립 검증한 것은 아니다. 에이전트의 합의도 증명 검사나 외부 실험을 대신하지 않는다.

수학 모델 안의 달성 정리와 실제 LLM·도구·세계가 그 모델에 맞는다는 근거를 분리한다.
명세를 만족하는 것이 유용한 학습·인지의 실현인지도 별도로 판별해야 한다.

## 3. 기존 증명은 어디까지 닫혔는가

[기존 proof-status graph](HSWM_PROOF_STATUS_GRAPH_2026-09-02.md)의 여섯 의무와
과거 판정을 그대로 보존한다. 이번 source inspection은 이전 Lean build의 재실행이 아니다.

| 기존 증거 | 실제로 확인하는 것 | 구성적 실현 증명에 남는 것 |
| --- | --- | --- |
| [verifiedAdmissionKernelSound](../../formal/HSWMVerifiedAdmissionKernel.lean) | 선언한 kernel 모델에서 수락된 변경의 admission 조건 | 현실 실행·세계 outcome·학습 효능 |
| [conditionalEvidenceBundleYieldsBoundedClaim](../../formal/HSWMEndToEndRuntimeRefinement.lean) | 공급된 runtime·outcome·측정 증거의 조건부 결속 | 그 증거가 실제로 발생하는 구성법 |
| 같은 파일의 `RuntimeBehaviorMeasurementWitness.strictAggregateGain` | 입력 증거가 이미 엄격한 점수 향상을 담음 | 향상을 가정하지 않고 알고리즘에서 도출하기 |
| 같은 파일의 `ExternalOutcomeSemanticWitness.observationTrue` | 외부 관측의 진실성을 전제로 사용 | 평가기·세계 연결과 독립적 측정 |
| [causal efficacy bridge](../../formal/HSWMCausalEfficacyBridge.lean)의 `causallyIdentified` | 주어진 `causalIdentification` 의미론과 occurrence 결속 | 명시한 배정·개입 모델에서 식별식을 유도하기 |

이 정리들은 유효한 조건부 연결 정리다. 그 용도를 “성능 향상을 만들어내는 정리”로
확대하면 결론을 전제에서 받아오는 문제가 생긴다. PS-3/5/6, G0/G1와 기존 RED 경로를
이 문서로 승격하지 않는다. [최근 라운드](HSWM_RELATION_RESEARCH_ROUND_1_2026-09-10.md)의
14개 공개 사례 고정 프로그램 결과와 RR-1 설계 제외도 그대로다.

## 4. 목표 명제의 형태와 비순환 조건

먼저 환경족, 관측·개입, score, 자원 상한, 시간 구간과 합성 깊이를 고정한다.
연구할 전체 명제의 **THEOREM TEMPLATE — NOT PROVED**는 다음과 같다.
환경족 `E_assump`는 알고리즘의 성공 여부와 독립적인 선행 조건으로 정의해야 하며 비어 있지
않아야 한다. `D>=2`, 양의 유한 `T,R`, `0<delta<1`과 초기 상태 분포 `nu_e`도 명시한다.

```math
\exists A\quad\forall e\in\mathcal E_{\mathrm{assump}}:\quad
\Pr_{A,e,S_0\sim\nu_e}
[\mathrm{OperationalFCL}_{1:8}(A,e;0{:}D,T,R)]\ge1-\delta.
```

`A`는 유한하게 기술되고 실행 가능하며 token-labelled transition과 명시한 LLM-function
realization을 포함하는 구성·갱신·합성 규칙이다. CR-7은 그 realization과 실제 모델 실행의
연결을 따로 증명·평가한다. 확률은 초기 상태, 선언한 LLM kernel, 환경과 배정의 무작위성에
대해 정의한다. 그 확률 공간도 아직 형식화하지 않았다.

`D`는 주장할 유한 합성 깊이이며 `0..D`의 모든 scale에서 같은 transition grammar와 해당
운영 계약을 요구한다. FCL-2/8의 합성 관계는 이 범위의 모든 인접 scale `d -> d+1`에 대해
검사하며 마지막 깊이 밖의 합성을 주장하지 않는다. `OperationalFCL`은 기존 여덟 계약의
trace·intervention·대조군·estimand·필요 margin·불확실성·판정 규칙을 펼쳐 적을 자리다.
새 axiom, opaque Boolean이나 이미 성공했다는 supplied witness로 대체할 수 없다.
구체적인 `E_assump,D,T,R,delta,nu_e`와 전체 술어의 형식화는 아직 미완료다.

환경족에는 실제 후보와 무관하게 기술할 수 있는 식별 가능성, 허용된 개입, 관측 노이즈,
자원과 통신 조건을 적는다. “A가 성공하는 환경들의 집합”이라고 정의하면 안 된다.
빈 환경족, 이미 성공하는 oracle, 실제 의미 없는 null cell도 존재 증명의 witness가 아니다.

무제한 환경에 대한 보편적 엄격 향상은 주장할 수 없다. 모든 행동의 보상이 같은 환경에서는
엄격한 향상이 불가능하다. 관측 이력은 같지만 필요한 다음 행동이 반대인 두 세계는 그
이력만으로 완전히 구별할 수 없다. 합성 후 쓰기 충돌·지연·외부 권한 거부도 독립적인
실패 원인이다. 이 조건들을 제외하는 범위와 비용을 숨기지 않는다.

유한 깊이의 정리가 나와도 무한 확장·전 인류 규모 효능·의식·personhood를 도출하지 않는다.
최대 목표는 유지하고, 증명이 실제로 다룬 범위만 결론으로 남긴다.
구성된 운영 모형의 witness는 그 모형의 존재·비공허성을 보여준다. 실제 cognition-bearing
시스템과 외부 세계의 유용한 능력을 실현했다는 판단에는 경험적 연결이 계속 필요하다.

## 5. 작은 출발점: 결과로 선택을 바꾸는 규칙의 분석적 유도

전체 HSWM 정리의 대용품을 만들지 않기 위해 먼저 **하나의 학습 원리**만 분리한다.
아래는 알려진 bounded-reward 집중 부등식을 적용한 초보적 유도이며 새로운 학습 알고리즘이
아니다. 아직 Lean으로 형식화하지 않았고, 현재 `adaptive-domain.ts`가 이 규칙을 구현하거나
그 가정을 만족한다고 주장하지 않는다. FCL-1을 통과시키는 증명도 아니다.

### 5.1 가정과 실제 선택 규칙

- 평가 전에 고정한 유한 정책 집합 `P={p_0,...,p_(K-1)}`, `K>=2`가 있다.
  `p_0`는 갱신하지 않는 기준 정책이며 후보 집합에 포함된다. 정책은 실행 가능한 선택·행동
  규칙이고 정답·미래 outcome을 입력받지 않는다.
- 각 정책을 동일한 고정 환경 분포에서 `n`회 평가한다. 해당 정책 내 reward는 독립 동일분포,
  범위 `[0,1]`, 평균 `mu_i`다. 상태 carry-over·공유 메모리·모델 변경·평가기 drift가 없다는
  제한된 reset 모델이다. 후보 간 독립성은 아래 union bound에 필요하지 않다.
- 후보·표본 수·score·delta는 결과를 보기 전에 고정하고 모든 `K*n` 평가 비용을 센다.
  각 고정 정책의 다음 평가 reward는 같은 분포에서 뽑은 fresh draw이며, 선택에 사용한
  전체 `K*n` 표본과 독립이다. 정책 실행과 선택 revision은 허용된 것이어야 한다.

각 표본 평균을 `hat(mu_i)`라 하고 다음을 계산한다.

```math
\epsilon=\sqrt{\frac{\log(2K/\delta)}{2n}},
\qquad
\widehat\mu_{\widehat i}=\max_{0\le i<K}\widehat\mu_i.
```

동률 선택 규칙을 미리 정한다. `hat(mu_hat_i)-hat(mu_0)>2 epsilon`이면 선택을
`p_hat_i`로 갱신하고, 아니면 `p_0`를 유지한다. 알고리즘은 진짜 평균이나 아래의
`Delta`를 알 필요가 없다.

### 5.2 유도: 향상을 전제로 넣지 않고 언제 나타나는지 계산하기

Chernoff–Hoeffding bound와 union bound에서 다음 동시 사건의 확률은 `1-delta` 이상이다.
인용하는 부등식은 [Auer·Cesa-Bianchi·Fischer (2002), Fact 1](https://link.springer.com/content/pdf/10.1023/A:1013689704352.pdf)에 있다.
아래 선택 규칙·상수 계산은 그 논문의 UCB1 정리를 그대로 부른 것이 아니라 이 문서의 유도다.

```math
\Pr\!\left[\max_i|\widehat\mu_i-\mu_i|\le\epsilon\right]\ge1-\delta,
\qquad
2K\exp(-2n\epsilon^2)=\delta.
```

이 사건 위에서 갱신이 수락되면

```math
\mu_{\widehat i}-\mu_0
\ge\widehat\mu_{\widehat i}-\widehat\mu_0-2\epsilon>0.
```

또한 `mu_*=max_i mu_i`와 `Delta=mu_*-mu_0`를 두면, 경험 평균 최대화에서

```math
\mu_{\widehat i}\ge\mu_*-2\epsilon,
\qquad
\widehat\mu_{\widehat i}-\widehat\mu_0\ge\Delta-2\epsilon.
```

따라서 `Delta>4 epsilon`이면 실제 갱신이 발생하며, 선택한 정책의 다음 평가 기대 점수는
기준보다 적어도 `Delta-2 epsilon>0` 높다. 이를 보장하는 충분 표본 조건은

```math
n>\frac{8}{\Delta^2}\log\frac{2K}{\delta}.
```

이 확률은 학습용 표본의 무작위성에 대한 것이다. 다음 한 번의 실행이 반드시 성공하거나,
각 갱신 때마다 단조 향상하거나, 탐색 비용까지 포함한 누적 순효용이 양수라는 결론은 아니다.
반복 갱신에는 후보 재선정·환경 drift·누적 오류 확률을 다루는 별도 정리가 필요하다.

`Delta>0`은 “우리 학습기가 이미 성공했다”는 가정이 아니라 **허용된 후보 중 개선할
여지가 있다**는 환경·표현 가정이다. 이 여지가 현실 과제에 있는지는 별도 연구다.
이 원리를 넣은 어떤 구조든 같은 유도를 사용할 수 있으므로 HSWM 고유 우위를 뜻하지 않는다.

### 5.3 가정이 비어 있지 않은 수학적 예와 강한 반례

고정된 두 행동이 각각 Bernoulli 평균 `1/4`, `3/4`의 reward를 내고 기준이 첫 행동인
환경은 위 가정을 만족한다. `K=2`, `delta=0.05`, `n=200`이면
`epsilon≈0.1047<Delta/4=0.125`이므로 앞의 결과가 적용된다.
이는 **모형의 예시**이며 실제 400회 실험이나 모델 관측을 보고한 숫자가 아니다.
이 예는 유한 선택 학습의 가정이 비어 있지 않다는 것만 보이고, 완전한 HSWM witness는 아니다.

동일 정책 집합·표본·선택 규칙을 쓴 text/program learner도 같은 결과를 얻는다.
따라서 이 정리를 HSWM의 강한 대조군 우위로 승격할 수 없다. 정적 관계 포장 RR-1을
구제하지도 않는다. 새 정책 생성·관계 구조의 재사용·다중규모 credit에서 추가 이득이 있는지는
다음 미해결 의무다. frozen 대비 개선과 strongest learner 대비 개선은 별개의 주장이다.

## 6. 전체 목표에 필요한 증명 의무

아래는 같은 HSWM의 동역학을 검증하는 의무이며 별도 subsystem이나 owner 분해가 아니다.
각 의무의 가정은 그 의무가 증명하려는 결론을 되풀이해서는 안 된다.

| ID | 증명할 연결 | 기존 토대와 미해결 지점 | FCL |
| --- | --- | --- | --- |
| CR-0 | 실제 Step/Learn 규칙이 schema·owner·typed reference·Inv/Permit·계보를 보존 | 기존 Lean kernel 재사용; 전체 trace semantics와 허용된 nontrivial witness는 미완성 | 전체 구조 조건 |
| CR-1 | outcome을 읽는 명시적 갱신 규칙에서 다음 행동의 유용한 변화가 도출 | §5는 좁은 고전적 출발점; 실제 후보 표현·지속 학습·강한 대조 우위는 미증명 | 1 |
| CR-2 | 구체적 무작위 배정·consistency·개입·간섭 범위에서 revision 효과의 식별식 도출 | 현재 opaque `causalIdentification`을 가정으로 넘기지 않기; 실제 custody는 별도 검증 | 1, 4 |
| CR-3 | 같은 외부 outcome의 credit이 cell·incidence·coalition에 중복 집계되지 않고 올바른 변경에 연결 | 단순 합이 맞는 분배와 인과적 credit은 다름; shuffled/uniform/global-only 대조 필요 | 4 |
| CR-4 | 문맥에 따른 n-ary coalition·topology 생성이 고정 router·roster·pairwise·sham보다 유용하고 손상에서 회복 | 갱신 규칙, 표현 적합성, 종료·자원 bound, 독립 대조를 함께 유도해야 함 | 3, 5 |
| CR-5 | 공동 world/self 예측과 계보가 행동을 조건화하고 migration·model/member 변경 뒤 지정 능력을 보존 | world-only/self-only·snapshot-copy와 구별; UID 동일성으로 대체하지 않음 | 6, 7 |
| CR-6 | 구체적 합성 연산이 하위의 계약·효과·권리·exit를 보존하고 상위에도 지속 상태와 학습 효과를 생성 | typed wiring만으로 인지적 합성은 나오지 않음; wrapper/flat 대조와 간섭·오차 bound 미증명 | 2, 8 |
| CR-7 | 한 구성이 CR-0..6을 동시에 만족하며 실제 런타임이 그 trace를 구현 | 서로 다른 toy witness들의 합집합은 금지; bounded refinement와 새 외부 관측 필요 | 전체 통합 |

CR-2에서 배정 확률·potential outcome·관측 식을 실제로 정의하고 대비의 기대값이 해당
인과 효과와 같음을 유도한다. random assignment 자체는 양의 효과를 보장하지 않는다.
delayed/sham/restore가 어떤 대체 설명을 배제하는지도 각각 가정과 식으로 적어야 한다.
현재 DNRD-5의 고정 계약이나 300-block 표본을 이 예시로 덮어쓰지 않는다.

CR-4/5의 빠질 수 없는 수학적 입력은 다음과 같다. FCL-3에는 공개한 scheduler·broadcast
의미론과 성능·안정성·자원 지표, FCL-5에는 명시한 lesion family와 유한 recovery 기준,
FCL-6에는 joint world/self 예측 대상·proper scoring rule·개입과 registry-null,
FCL-7에는 identity invariant 및 보존해야 할 disposition·readout·개입 대응을 둔다.
숨은 중앙 coordinator나 외부 self registry를 넣어 계약을 형식적으로 만족시키지 않는다.

CR-6은 “합성이 효과를 보존한다고 가정하면 보존된다”로 닫을 수 없다. 실제 합성 연산,
쓰기 conflict 해결, typed port와 intervention의 대응, 권한·exit, 지연·간섭 모델을 먼저
정의하고 그로부터 오차와 자원 증가를 도출해야 한다. 먼저 macro intervention map과
matched flat/wrapper 대비의 estimand를 정하고, 그 scale d의 효과 하한을 `b_d`로 둔다.
`b_(d+1)>=b_d-eta_d` 같은 관계가 **유도된다면** 정해진 깊이까지의 손실을 계산할 수 있다.
`eta_d`는 port 추상화·전달·conflict·추정 오차에서 유도되거나 별도로 검증된 bound여야 한다.
구성원의 주소성·provenance·permission·exit도 trace field만이 아니라 simulation/refinement
대응으로 보존해야 한다. 이 식이나 `eta_d`의 작음을 현재 가정 또는 증명 완료로 취급하지 않는다. 구조적 합성의
귀납법과 인과 효과 보존의 귀납 단계는 서로 다른 미해결 의무다.

## 7. 증명·모형·실행·현실의 연결

```text
구체적 환경족·구성 규칙·반례
  → 결과를 전제로 삼지 않는 보조정리
  → 하나의 nontrivial base witness
  → 같은 witness의 합성·효과·계보 보존 증명
  → 명세와 bounded runtime trace의 연결
  → 독립 평가에서 가정과 효과 확인
```

Lean에 옮길 때는 정확한 정리 statement, 사용 공리, 미해결 premise, 증명 소스와 재현 명령을
같이 남긴다. `sorry`, 목표를 선언한 새 axiom, opaque `Cognitive`/`Gain` premise를 추가해
성공으로 표시하지 않는다. 공식 도구의 버전·dependency는 기존 pin을 재사용하고 변경은
구체적인 필요가 생겼을 때 별도로 결정한다.

현실 실험은 같은 모델·같은 이전 경험·같은 도구와 **총 가용 자원 상한**에서 강한
native/text/program learner를 비교한다. 실제 token·시간·비용은 별도로 보고한다.
동일 payload 등가성 검사는 예상되는 동률을 숨기지 않는다. exact revision 제거, 무관한
제거, sham, byte-identical state 복원을 구분하고 비결정적 출력까지 동일하다고 가정하지 않는다.
프랙탈 주장은 최소 두 bounded scale의 같은 측정 문법과 기존 FCL 대조를 모두 요구한다.

수학적 반례나 유효한 음성 실험은 해당 기전을 교체하는 근거다. 계측 실패·누수·포화는
효능 미판정으로 남긴다. 전체 목표를 줄이거나 성공 기준을 사후 변경하지 않는다.

## 8. 이번에 끝낸 것과 바로 이어질 연구

이번에는 기존 정리의 숨겨지기 쉬운 전제를 소스에서 확인하고, §5의 분석적 출발점과
CR-0..7의 열린 의무를 연결했다. 별도 에이전트가 기존 formal 경계와 전체 FCL 누락을
각각 검토했다. 이는 공유 환경의 AI 검토이며 독립 수학계 검증이나 현실 outcome이 아니다.

다음 작업은 [구성적 증명 연구 그래프](../../_research/research_coordination/constructive_realizability.v1.json)에 둔다.
첫 세 갈래는 작은 유도의 형식화 범위 선정, 명시적 인과 식별 모형, 실제로 구성 가능한
하나의 전체 FCL witness/반례 탐색이다. 이를 교차 비평한 뒤 구성 후보와 반증 실험을 통합한다.
전체 FCL witness가 없으면 그렇게 기록하고 쉬운 선택 학습을 HSWM 완성으로 이름 바꾸지 않는다.

기존 [RU-1 계획](../../_research/research_coordination/relation_update_candidate.v1.json)은 남아 있는
실험 후보이며 구현·평가 완료로 바뀌지 않는다. 모델 API가 없어도 수학적 유도·반례 검토는
진행할 수 있다. API·평가 과제·custody는 실제 모델 실험을 수행할 때 채울 조건이다.
이번 문서는 새로운 G0 허가 절차, canonical-write 경로 또는 개인 거버넌스 도구를 추가하지 않는다.
