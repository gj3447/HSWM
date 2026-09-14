# HSWM: Transformer 아키텍처·최신 학습 기법과 수학적 기반

조사 기준: **2026-09-14 UTC**. 원 논문, 학회·출판사, 저자 공식 자료를 확인했다. 최근 제안과 오래된 기반 기법을 함께 비교하며, 이 목록이 전체 분야의 망라나 사용량 순위라는 주장은 하지 않는다. 검색 결과·Hugging Face 논문 검색은 발견에만 사용했다. 논문별 확인 버전과 읽은 범위는 [출처 카탈로그](artifacts/hswm_transformer_math_2026-09-14/research.v1.json)에 기록한다.

## 1. HSWM에서 이 조사의 역할

HSWM의 목표는 진화하는 typed hypergraph 자체가 실행 조직, 세계모형, 지속 학습을 수행하는 **하나의 token-native LLM-function macro-neural network**이다. 인지 기능을 가진 HSWM cell들이 같은 typed, outcome-bound dynamics 아래 더 큰 HSWM을 이루는 목표와 FCL-1..8을 유지한다. 현재 통합 과학적 지위는 `SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`이다. [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md), [프랙털 연결](HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md), [적응적 연구 전략](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)이 우선한다.

이번 개념적 변화는 기존 [학습 이론 지도](HSWM_FRONTIER_LEARNING_THEORY_KG_2026-09-07.md)와 [학습 문헌 검토](HSWM_AI_LEARNING_LITERATURE_REVIEW_2026-09-08.md)를 **구체적 연산 → 수학적 가정 → 변경되는 상태와 수명 → 구현 접근권 → 반증 가능한 HSWM 적용 가설**로 상세화하는 것이다. 아래 분류는 문헌 탐색 축이며 HSWM의 고정 하위 시스템이나 canonical atom 분해가 아니다.

이 문서는 문헌 조사·설계 연결이다. 구현, 실험 재현, 새 Lean 증명, 관계의 causal admission, HSWM 효능을 보고하지 않는다. [세 학습 간극](HSWM_THREE_LEARNING_GAPS_IMPLEMENTATION_RESEARCH_2026-09-14.md)의 G1 관계 의미 발견, G2 원인별 교정, G3 합성 후 학습 유지와 기존 RED 결과·판정 조건을 그대로 연결한다.

## 2. 무엇을 바꾸는 기법인가

일반 attention의 기준 연산은 다음과 같다. Q, K, V는 각각 query, key, value이다. shape는 Q: n_q × d_k, K: n_k × d_k, V: n_k × d_v, M: n_q × n_k이다. Additive mask M은 허용 위치 0, 차단 위치 −∞이며 각 query에 허용 key가 적어도 하나 있다고 가정한다. softmax는 key 방향에 적용한다.

```math
A(Q,K,V)=\mathrm{softmax}\left(\frac{QK^{\mathsf T}}{\sqrt{d_k}}+M\right)V.
```

가중합은 어떤 정보를 읽을지 결정한다. 이 가중치 자체가 진실 확률이나 원인별 공헌도는 아니다. 원래 Transformer의 normalization·FFN 구성과 후속 RMSNorm·gated FFN 변형도 구분해야 한다. [원 Transformer §3](https://arxiv.org/html/1706.03762v7)

| 계열·확인한 자료 | 실제 변경 | 얻으려는 효과 | HSWM 연결의 한계 |
|---|---|---|---|
| [GQA, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.298/), [MLA, DeepSeek-V3 v2, 2025](https://arxiv.org/html/2412.19437v2) | 여러 query head가 KV를 공유하거나 latent KV로 압축 | decode의 cache·대역폭 감소 | 압축된 기억이 드문 예외와 근거 구분을 보존하는지는 별도 측정 |
| [FlashAttention-2, 2023](https://arxiv.org/abs/2307.08691), [FlashAttention-4, 2026-03](https://arxiv.org/html/2603.05451v1) | attention의 GPU 입출력·병렬 스케줄·수치 계산 | 하드웨어 이용률과 실행 속도 개선 | 새로운 관계 학습기가 아니다. FA4는 수치 근사도 사용하며 bitwise 동일성·subquadratic FLOPs를 뜻하지 않음 |
| [Native Sparse Attention, 2025-02, 읽은 버전 v1](https://arxiv.org/html/2502.11089v1) | 압축 block, 선택 block, sliding window의 결합 | 긴 문맥의 선택적 읽기 | 읽지 않은 근거가 무관하다는 보장은 없음 |
| [DeepSeek MoE](https://arxiv.org/html/2412.19437v2), [Mixture of Layers, 2026-05](https://arxiv.org/html/2605.09516v1) | token별 일부 expert·layer를 활성화 | 계산량 배분·용량 확장 | 부하 균형은 의미 있는 전문성이나 causal credit이 아니다. MoL 보고에서는 희소화에도 학습 시간이 증가한 설정이 있음 |
| [RoPE, 2021, 읽은 버전 v5](https://arxiv.org/html/2104.09864v5) | Q/K를 위치 의존 회전으로 변환 | 내적에 상대 위치 구조 반영 | 임의 길이 외삽이나 hyperedge의 의미적 역할 보존을 보장하지 않음 |
| [mHC, 2025-12 공개·2026-01 개정](https://arxiv.org/html/2512.24880v1), [Attention Residuals, 2026-03](https://arxiv.org/abs/2603.15031v1) | residual stream의 제약된 혼합 또는 깊이 방향 attention | 층 사이 정보 전달과 최적화 개선 | mHC의 혼합 행렬 성질을 전체 의미·예외 보존으로 확대할 수 없음. AttnRes는 이번 조사에서 초록 수준 확인 |
| [Mamba, COLM 2024](https://arxiv.org/html/2312.00752v2), [Mamba-3, ICLR 2026](https://arxiv.org/html/2603.15569v1) | 선택적 state-space recurrence; Mamba-3는 discretization·complex state·MIMO 확장 | 압축된 sequence state로 효율적 처리 | 고정 크기 상태는 정확한 과거 회상의 병목이 될 수 있으며 영속적 세계 지식과 같지 않음 |
| [Gated DeltaNet-2, 2026-05](https://arxiv.org/html/2605.22791v1) | 기존 연상 기억의 오차를 기준으로 erase/write·decay 제어 | 기억 덮어쓰기와 보존 조절 | 예측 오차 교정은 관찰된 연상의 교정이며 원인 식별을 자동 수행하지 않음 |
| [Kalman Delta Networks, 2026-09-07](https://arxiv.org/html/2609.07816v1) | 기억 평균과 공분산에 기반한 gain으로 delta update | 불확실성을 반영하는 메모리 쓰기 | 매우 최근 preprint. 효율화한 공분산 근사와 모델 가정을 포함하며 HSWM 주장 신뢰도의 보정이 아님 |
| [TTT, 2024·v4 2025](https://arxiv.org/html/2407.04620v4), [Titans, 2024-12 공개](https://arxiv.org/html/2501.00663v1), [Nested Learning/Hope, 2025](https://arxiv.org/html/2512.24695v1) | fast weight·기억을 추론 중 갱신하거나 서로 다른 시간척도로 학습 | 문맥 적응과 기억 유지 | sequence reset, optimizer state, 영속 저장, base weight 갱신을 구분해야 함 |
| [Recurrent Transformer, 2026-04](https://arxiv.org/html/2604.21215v1) | 같은 층의 갱신된 출력에서 미래 token용 KV를 저장 | 시간축을 통한 더 깊은 계산의 표현 | 단순 반복 prompting과 다르며 표현 가능성은 학습 성공 보장이 아님 |
| [Nemotron-Labs-TwoTower, 2026-06 v2](https://arxiv.org/html/2606.26493v2) | causal context tower와 block denoising tower 결합 | block 내부 병렬 정련·생성 비용 절충 | denoising은 외부 사실 검증이 아니다. backbone·학습량·품질 조건에 종속 |
| [LoRA, 2021](https://arxiv.org/html/2106.09685v2), [DeepSeek-R1/GRPO, 2025·v2 2026](https://arxiv.org/html/2501.12948v2) | 작은 rank의 parameter update; 그룹 상대 보상에 의한 후학습 | adaptation 비용 감소; 평가 가능한 행동 최적화 | backbone 구조 변경과 별개의 학습 기법. reward는 관계별 인과 공헌도가 아님 |

2026년 자료도 모두 동일한 증거 수준은 아니다. Mamba-3는 [공식 학회 기록](https://openreview.net/forum?id=HwCvaJOiCj)이 있고, KDN·GDN-2 등은 이번 조사에서 저자 preprint를 확인했다. 독립 재현은 수행하지 않았다. mHC와 NSA는 최신 메타데이터가 v2이지만 방법 설명은 v1을 읽었다. FA4의 속도는 GPU·dtype·shape·비교 구현에 종속되며, [저자 공식 글](https://tridao.me/blog/2026/flash4/)은 이후 cuDNN의 유사 기법·유사 성능도 명시한다.

## 3. 함께 가져와야 하는 수학

### 3.1 연상 기억과 에너지: attention이 무엇을 계산하는가

Modern Hopfield memory에서 패턴을 column으로 저장한 R의 shape는 d × N, 현재 상태 ξ의 차원은 d, inverse-temperature β는 양수라 하면 다음 retrieval update를 사용한다.

```math
\xi^+=R\,\mathrm{softmax}(\beta R^{\mathsf T}\xi).
```

적절한 projection·scaling 아래 attention과 연산적으로 연결된다. 기억 회복·에너지 결과는 해당 에너지 구성과 패턴 분리 조건에 의존한다. 임의 Transformer가 올바른 세계 관계를 회복한다는 정리는 아니다. HSWM에서는 읽기 분포와 읽힌 근거를 기록하되 분포 집중도를 진실의 확률로 부르지 않는 데 도움이 된다. [Ramsauer et al.](https://arxiv.org/abs/2008.02217)

### 3.2 선형대수: 저랭크 압축으로 무엇을 잃는가

A의 SVD를 `A=U diag(σ_i)Vᵀ`로 쓰고 singular value를 내림차순 정렬한다. Eckart–Young의 Frobenius norm 결과에서 상위 r개 성분의 truncated SVD를 A_r라 하면:

```math
\min_{\mathrm{rank}(B)\le r}\|A-B\|_F^2
=\|A-A_r\|_F^2=\sum_{i>r}\sigma_i^2.
```

이는 주어진 행렬의 근사 오차에 대한 정리다. LoRA의 학습된 업데이트 `ΔW=(α/r)BA`가 downstream task에서 최적이거나 MLA가 중요한 예외를 보존한다는 정리가 아니다. HSWM의 압축 실험에는 평균 성능과 함께 희귀 예외·출처 복원·반례 검색을 측정해야 한다. [Eckart–Young, 1936](https://doi.org/10.1007/BF02288367), [LoRA §4.1](https://arxiv.org/html/2106.09685v2)

### 3.3 온라인 최적화: delta rule은 예측 오차를 어떻게 쓰는가

기억 S의 shape가 d_k × d_v, key k와 value v가 각각 d_k, d_v 차원 column vector이고 step size η>0일 때:

```math
\ell(S;k,v)=\tfrac12\|S^{\mathsf T}k-v\|^2,
\qquad S^+=S+\eta k(v-S^{\mathsf T}k)^{\mathsf T}.
```

한 관측에 대한 Frobenius gradient는 `∇_S ℓ=k(Sᵀk−v)ᵀ`이므로 위 update는 제곱오차의 gradient step이다. 반복 갱신의 안정성은 별도로 확인해야 한다. TTT는 학습 가능한 내부 모델·자기지도 loss로 확장하고, GDN 계열은 쓰기·지우기·감쇠를 제어한다. 관찰된 예측 오차를 줄이는 것과 어떤 관계가 실제 결과를 바꾸었는지 식별하는 것은 별도 문제다. [TTT](https://arxiv.org/html/2407.04620v4), [GDN-2](https://arxiv.org/html/2605.22791v1)

Robbins–Monro의 고전 조건에는 step size의 합이 발산하고 제곱합은 수렴하는 조건 외에 관찰·평균 함수에 대한 정칙성이 필요하다. Online Gradient Descent의 `O(DG√T)` regret는 직경 D인 convex domain과 bounded subgradient G 등에서 최선의 고정 비교자에 대한 결과다. 이것들을 그대로 비볼록 LLM의 수렴·인과 학습 정리로 사용할 수 없다. [Robbins–Monro 원문](https://www.columbia.edu/~ww2040/8100F16/RM51.pdf), [Hazan, OCO](https://mitpress.mit.edu/9780262046985/introduction-to-online-convex-optimization/)

### 3.4 확률과 필터링: 오차의 크기와 확신을 함께 다루기

선형 관측 `y=Hx+noise`에서 Gaussian prior `x~N(m⁻,P⁻)`와 x에 독립인 zero-mean Gaussian noise의 covariance R을 가정한다. `HP⁻Hᵀ+R`이 가역일 때 Kalman update는:

```math
K=P^-H^{\mathsf T}(HP^-H^{\mathsf T}+R)^{-1},
\qquad m^+=m^-+K(y-Hm^-),
\qquad P^+=(I-KH)P^-.
```

정확한 posterior 해석에는 지정된 선형 Gaussian 모형과 잡음 가정이 필요하다. KDN은 이 관점을 associative memory로 가져오지만, 효율적인 scan을 위해 대각·등방 공분산 근사를 사용한다. 대각 prior 아래 한 step의 mean update가 정확한 경우와 전체 sequence posterior가 정확하다는 주장은 다르다. HSWM에서는 모델 내부 불확실성, 관찰 신뢰도, 실험으로 보정된 주장 불확실성을 구분해야 한다. [Kalman, 1960](https://doi.org/10.1115/1.3662552), [KDN §3](https://arxiv.org/html/2609.07816v1)

### 3.5 정보이론과 인과 식별: 짧은 설명이 원인인가

MDL은 명시한 유효 code class(예: Kraft 조건을 만족하는 prefix code) 아래 `L(model)+L(data|model)`이라는 코드 길이 절충으로 설명을 선택하는 관점이다. 그러나 관찰 분포가 같은 여러 causal DAG가 존재할 수 있다. Markov equivalence를 깨려면 개입이나 추가 구조 가정 등 식별 조건이 필요하다. 환경 변화도 명시된 다중 환경·불변성 가정 등이 있어야 식별에 사용할 수 있다. HSWM의 relation/library 합성에서 간결성은 후보 선별 기준으로 쓸 수 있지만 causal admission의 대체물이 아니다. Algorithmic Markov 관점의 Kolmogorov complexity도 일반적으로 계산 가능하지 않다. [Elements of Causal Inference](https://web.math.ku.dk/~peters/jonas_files/ElementsOfCausalInference.pdf), [Algorithmic Markov Condition](https://arxiv.org/abs/0804.3678)

### 3.6 하이퍼그래프와 스펙트럼: n항 관계와 pairwise 연산의 차이

Incidence matrix H, hyperedge weight W, node·edge degree D_v, D_e로 구성하는 대표적 정규화 연산은:

```math
L=I-D_v^{-1/2}HW D_e^{-1}H^{\mathsf T}D_v^{-1/2}.
```

이는 양의 degree 또는 별도 isolated-node 처리 아래 smoothness를 측정하는 연산이다. 이름 붙은 hyperedge column을 유지한 H는 incidence와 edge 식별을 보존할 수 있지만, pairwise co-membership에서 파생된 L만 남기면 서로 다른 고차 관계가 같은 pairwise 연산으로 뭉개질 수 있다. HSWM에서는 방향·역할·예외·출처를 가진 원래 typed hyperedge를 보존하고 스펙트럼 표현을 제한된 projection으로 다뤄야 한다. [Zhou–Huang–Schölkopf, 2006](https://papers.nips.cc/paper/2006/file/dff8e9c2ac33381546d96deea9922999-Paper.pdf)

### 3.7 합성과 안정성: 어떤 정리를 실제로 요구할 것인가

- **mHC의 행렬 조건:** 원소가 비음수이고 각 행·열의 합이 정확히 1인 doubly stochastic matrix는 곱에 대해 닫혀 있다. 수치 Sinkhorn은 유한 반복 오차를 가지며, 평균을 보존하는 혼합도 서로 다른 상태를 구분하지 못하게 할 수 있다. 행렬 closure와 학습 능력 보존은 다른 명제다. [mHC](https://arxiv.org/html/2512.24880v1)
- **인과 추상화:** Exact transformation은 상태 사상 τ와 허용 개입 사이의 순서 보존·전사 사상 ω를 두고, 모든 허용 개입 i에 대해 pushforward 분포 `τ_#P_L^{do(i)}=P_H^{do(ω(i))}`를 요구한다. 이는 학습 규칙의 개선·수렴 보장까지 포함하지 않는다. [Causal Consistency of Structural Equation Models](https://arxiv.org/abs/1707.00819)
- **Small-gain:** 두 구성요소의 input-to-state stability와 well-posed interconnection 등 해당 정리의 가정 아래 `γ12∘γ21(s)<s`는 연결 안정성의 충분조건이다. 유계·안정 상태가 유용한 지식 획득을 뜻하지는 않는다. [Jiang–Teel–Praly, 1994](https://web.ece.ucsb.edu/~teel/ECE236/jiang-teel-praly-1994)
- **표현력:** RASP의 구성적 프로그램–Transformer 연결이나 Recurrent Transformer의 emulation은 가능한 연산을 이해하는 도구다. 학습 과정이 그 해를 찾는다는 증명은 아니다. [RASP, ICML 2021](https://proceedings.mlr.press/v139/weiss21a.html), [Recurrent Transformer](https://arxiv.org/html/2604.21215v1)

## 4. HSWM에 적용 가능한 범위와 우선순위

**기반 모델 내부를 바꾸는 구현**은 weight·hidden state·attention kernel·학습 과정에 대한 접근이 필요하다. 일반적인 hosted LLM API 호출만으로 FA4, MLA, Mamba, GDN/KDN, model-internal TTT를 주입할 수 없다. 지원되는 fine-tuning API가 있더라도 노출된 조정 범위를 개별 확인해야 한다.

**HSWM의 TypeScript/Effect 실행·학습 과정에 적용하는 가설**은 별도로 가능하다. 예를 들어 예측과 outcome의 residual 기록, 상태별 reset·지속·갱신 계약, 불확실성에 따른 검토 후보 배분, 원본 근거를 보존하는 압축 projection을 pure immutable domain function과 typed Effect I/O로 표현할 수 있다. 이는 외부 구현에서 시험할 연산적 유추이며 논문 모델의 동등 구현이라는 주장이 아니다. 기존 코드에도 제한된 feature의 residual update가 있으므로 새로 필요한 것은 단순한 오차식 추가보다 표현 발견·신뢰할 수 있는 credit·다음 행동 변화의 연결이다.

| 기존 간극 | 이번 문헌이 제공하는 후보 | 여전히 필요한 결정적 근거 |
|---|---|---|
| G1: 관계의 의미·변수·새 관계를 경험에서 발견 | attention/연상 기억으로 후보 조회, MDL·저랭크로 후보 표현 비교, TTT로 적응 가능한 상태 | 고정 feature·DSL 바깥의 실제 관측 가능한 변수/관계 제안, held-out 식별·행동 개선, 허위·빈 표현 통제 |
| G2: 성공·실패의 원인별 교정 | delta residual, KDN식 불확실성, 다중 시간척도 기억 갱신 | 관계별 제거·복원/개입, 교란·선택 편향 처리, 오염된 reward 통제, 수정 전 예측과 수정 후 새로운 결과 |
| G3: 합성 후에도 학습·예외·불확실성 유지 | residual mixing의 제약된 혼합, causal abstraction, state-space/small-gain 분석 | 같은 구성에서 개입·credit·갱신이 실제 연결되는지, 공유 원인·상충 예외, 두 scale의 새로운 결과와 학습 변화 |

다음 비교 실험을 설계한다면 **같은 정보와 총비용** 아래 원본 근거 조회, 제한된 갱신 기억, 원본+압축 기억을 비교하는 것이 유용하다. reset 후 효과가 사라지는지, 새 상황에도 남는지, no-update·sham·shuffle·관계 제거/복원에 어떻게 반응하는지 측정한다. 압축으로 숨겨진 반례, 나쁜 관찰에 대한 과잉 갱신, 합성 시 중복 공헌도와 상쇄 실패가 주요 반증 대상이다. 이는 [기존 개발 계획](../operations/HSWM_NEXT_DEVELOPMENT_GRAPH_PLAN_2026-09-13.md)의 판정 기준을 바꾸거나 하위 실패를 상위 scale로 구제하는 제안이 아니다.

현재 우선해서 상세 검토할 조합은 **delta/TTT의 갱신 연산 + 확률적 불확실성의 명시 + 인과 식별 조건 + 합성 보존 조건**이다. FA4·MLA·MoE는 실제 계산·메모리 병목이 측정되고 해당 모델 내부에 접근할 때 backend 후보로 평가한다. 이 우선순위는 HSWM의 기존 세 간극에 대한 SECONDARY_AI 연구 판단이다.

## 5. 출처·KG·도구 기록

출처 카탈로그는 아키텍처·학습 방법 22개 기록과 수학 연결 8개 기록을 담는다. 일부 기록은 복수 원문을 연결하므로 **30편의 독립 논문 수와 같지 않다**. 논문 버전, 읽기 깊이, 상태 수명, 접근권, 성립 가정, 비보장 범위를 보존한다. 원문은 EXTERNAL_PRIMARY, 요약·적용 가설은 SECONDARY_AI, 사용자의 조사 요청은 USER_PRIMARY로 구분한다.

[KG bundle](../../ontology/development/HSWM_TRANSFORMER_ARCHITECTURE_AND_MATH_2026-09-14.v1.json)은 출처→수학 연결→적용 가설→기존 G1/G2/G3를 typed edge로 연결한다. 이 KG는 검토 가능한 문헌 projection이며 HSWM의 인지·routing·학습 실체가 아니다. checked-in RDF projection/SHACL 1.0 v2 경로로 검증하며, 전체 주장에 관한 과학적 증명이 되는 것은 아니다. [검증 기록](artifacts/hswm_transformer_math_2026-09-14/validation.v1.json)

새 SDK·모델·kernel·Skill은 설치하지 않았다. 발견한 논문·저자 구현은 연구 후보이며 표준이나 생산 환경 적합성 인증으로 승격하지 않는다. 실제 도입 시 공식 source, 정확한 version/commit·artifact digest·lockfile·license·접근권과 해당 workload의 비교 실험을 기록한다. 이번 변경은 문헌·문서/KG 작업이므로 새 실험 결과나 `F1_R8_RESULTS_LOG.md` 항목을 만들지 않는다.
