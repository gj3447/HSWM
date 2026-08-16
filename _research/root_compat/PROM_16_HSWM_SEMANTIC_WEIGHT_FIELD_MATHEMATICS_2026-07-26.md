# PROM-16 — HSWM Semantic Weight Field mathematics

> **status**: `SECONDARY_AI_RESEARCH / PROPOSED_MATHEMATICAL_BELT`
> **cycle_id**: `prom-hswm-semantic-weight-field-math-20260726`
> **date**: 2026-07-26
> **lanes**: `BRIDGE + ENGINEERING`
> **canon boundary**: USER_CANON은 HSWM을 작은 LLM이 실행하는 의미 함수망,
> hypergraph `H`, Semantic Weight Map `W`, recurrent plastic state가 합쳐진 더 큰 AI로
> 둔다. 이 문서의 수식과 `HSWM-SWF-v0` 명칭은 그 정전을 교체하지 않는 반증 가능한
> protective-belt 제안이다.
> **Naesengmoon**: 사용자 요청이 없었으므로 출격하지 않았다.

## 0. 답부터

가능하다. 다만 **임베딩 벡터에 cosine scalar 하나를 붙이는 방식은 HSWM이 말하는
Semantic Weight Map에 부족하다.**

이번 PROM의 결론은 다음과 같다.

> **임베딩은 의미의 좌표계이고, semantic weight는 그 좌표 위에서 타입·인자 역할·문맥·시간·
> 결과 이력을 함께 평가하는 n항 관계 연산자다.**

따라서 `W`는 단일 실수가 아니라 다음 묶음이어야 한다.

\[
W=\{\Theta_{rel},\ R_{v\to e},\ \theta_e,\ \alpha_e,\ z_e,\ U_e\}_{e\in E}
\]

- `Θ_rel`: 관계 종류별 저랭크 n항 tensor/energy;
- `R_{v→e}`: 서로 다른 함수·개념의 국소 좌표를 관계 공간으로 옮기는 transport map;
- `θ_e`: 개별 hyperedge의 학습된 fast/slow strength;
- `α_e`: hyperedge가 실제 회로에 열릴 topology gate logit;
- `z_e`: 결과가 늦게 와도 과거 활성에 credit을 주는 eligibility trace;
- `U_e`: uncertainty, provenance, support/contradict/supersede channel.

이 구조를 이 문서에서는 편의상 **HSWM Semantic Weight Field v0 (`HSWM-SWF-v0`)**라고
부른다. 이것은 새 사용자 정전명이 아니다.

## 1. 현재 코드와 목표 사이의 정확한 간극

현재 구현에서 살아 있는 기반은 좋다.

- `hswm_field_algebra.py`: merge의 commutative/associative/idempotent 성질과 reversible split;
- `hswm_hypergraph.py`: vertex와 hyperedge를 first-class object로 보존;
- `hswm_open_kernel.py`: immutable snapshot, provenance, connector, weight seam;
- `hswm_fusion.py`: confidence/agreement 기반 field fusion;
- `hswm_hypergraph_readout.py`: 후보 vertex/hyperedge를 cosine으로 읽고 1-hop 확장;
- `learned.py`, `learned_v2.py`: single full bilinear score도 시험했으나 `768^2` 규모 parameter와
  real-KG residual 부족 때문에 과적합·식별성 문제가 드러남.

따라서 문제는 단순히 “bilinear를 추가하자”가 아니다. 현재 기본 readout은 대체로

\[
w(v,q)=\cos(x_v,x_q)
\]

이고, full bilinear는 너무 크고 relation/role/n항 구조를 공유하지 않는다. 둘 다 다음을 안정적으로
구분하지 못한다.

1. `A supports B`와 `A contradicts B`;
2. `A precedes B`와 `B precedes A`;
3. `A supersedes B`와 단순 유사성;
4. `(A,B,C)`가 함께 있을 때만 성립하는 n항 의미;
5. 같은 관계가 질문·시간·outcome에 따라 달라지는 가중치;
6. 어떤 작은 LLM 함수의 출력이 실제 성공에 기여했는지.

즉 현재 `H`는 구조를 보존하지만, `W`는 아직 그 구조 위에서 식별 가능하게 학습되는 신경
회로가 아니다. v0은 full `d x d` matrix를 늘리는 대신 relation/role 사이에서 core를 공유하는
저랭크 tensor로 parameter 수를 줄인다.

## 2. PROM consensus

### C1. 하나의 embedding space로 모든 관계를 설명하면 안 된다

분포적 유사성은 Euclidean/cosine에 잘 맞지만, 계층은 hyperbolic geometry가 더 자연스럽고,
방향성·비대칭·인자 역할은 relation-specific transformation이 필요하다. Euclidean 공간에 모든
관계를 억지로 넣을 수 있는지에는 표현력·차원 한계가 있다.

따라서 v0의 좌표계는 다음 product space로 둔다.

\[
\mathcal M
=\mathbb R^{d_s}\times\mathbb B_{\kappa}^{d_h}\times\Delta^{d_u-1}
\]

- `R^{d_s}`: 내용 유사성, analogy, local composition;
- `B_κ^{d_h}`: taxonomy, subsumption, abstraction depth;
- `Δ^{d_u-1}`: epistemic state의 확률 좌표—support, contradict, unknown 등.

모든 관계가 세 공간을 똑같이 쓰지 않는다. 관계 `r`와 query `q`가 gate를 정한다.

\[
g_r(q)=\operatorname{softmax}(G_r q),\qquad \sum_c g_{r,c}(q)=1
\]

### C2. 의미는 node pair가 아니라 typed n-ary relation에 놓여야 한다

hyperedge를

\[
e=(r;v_1\!:\!\rho_1,\ldots,v_k\!:\!\rho_k)
\]

로 둔다. `r`은 relation type, `ρ_i`는 subject/object/evidence/judge/function-input 같은
argument role이다. 순서가 없는 관계만 permutation invariant여야 하고, 역할이 있는 관계를
무조건 대칭화하면 의미가 사라진다.

Euclidean semantic channel의 저랭크 n항 potential은 다음처럼 둘 수 있다.

\[
\phi^{sem}_e(q)
=\sum_{\ell=1}^{R}a_{r\ell}(q)
\prod_{i=1}^{k}\langle u_{r,\rho_i,\ell},s_{v_i}\rangle
\]

이는 full tensor의 지수적 비용을 CP/Tucker 계열 저랭크 분해로 줄이면서도 pairwise sum에는
없는 순수한 n항 interaction을 남긴다.

계층 channel은 단순 cosine 대신 관계별 hyperbolic distance를 쓴다.

\[
\phi^{hier}_e(q)
=-\sum_i \omega_{r,i}(q)
d_{\mathbb B_\kappa}
\bigl(T_{r,\rho_i}h_{v_i},c_{r,i}(q)\bigr)^2
\]

### C3. semantic compatibility와 causal efficacy를 분리해야 한다

가장 중요한 분리는 다음이다.

\[
\underbrace{K_e(q)}_{\text{무슨 의미로 맞는가}}
\quad\ne\quad
\underbrace{\theta_e(t)}_{\text{실제 결과에 얼마나 유효했는가}}
\]

`K_e`는 frozen embedding 위 relation/role compatibility이고, `θ_e`는 독립 outcome으로 학습된
macro-synaptic efficacy다. 실제 routing logit에서만 합친다.

\[
\Psi_e(q,t)=K_e(q)/\tau_r+\theta_e^{fast}(t)+\theta_e^{slow}(t)+\cdots
\]

둘을 한 scalar로 학습하면 embedding drift, 의미 적합도, 성공 이력을 구별할 수 없다. 궁극적인
behavioral importance는 edge 제거 개입으로 정의할 수 있다.

\[
I_e=\mathbb E_q D_{KL}\!\left[
p(y\mid q,H,W)\;\|\;p(y\mid q,H\setminus e,W)
\right]
\]

log-probability를 못 얻는 작은 LLM에는 sealed task outcome distribution의 divergence로 근사한다.

### C4. semantic weight는 scalar가 아니라 energy + transport다

각 작은 LLM 함수와 개념 node는 서로 다른 local state/port를 가질 수 있다. 연결 강도만 두면
서로 다른 표현을 어떻게 옮길지가 없다. 따라서 incidence마다 transport를 둔다.

\[
R^{(r,\rho)}_{v\to e}:\mathbb R^{d_v}\to\mathbb R^{d_e}
\]

이는 sheaf의 restriction map과 비슷한 공학적 역할을 한다. 모든 node를 동일 벡터 공간이라고
가정하지 않고, 관계 공간에서 비교·합성한 뒤 목적 node의 공간으로 되돌린다.

방향과 대칭 관계를 한 metric에 뭉개지 않기 위해 binary auxiliary operator는 다음처럼 분해할
수 있다.

\[
B_r=S_r+A_r,\qquad S_r=L_rL_r^\top\succeq0,\qquad A_r=-A_r^\top
\]

`S_r`은 relation-local distance/compatibility, `A_r`은 cause→effect나 caller→callee 같은 방향을
담는다. support/contradict/supersede는 별도 signed channel로 보존한다.

통합 log-potential은 다음과 같다.

\[
\begin{aligned}
\Psi_e(q,t)=\;&
g_{r,sem}(q)\phi^{sem}_e(q)
+g_{r,hier}(q)\phi^{hier}_e(q)\\
&+\theta_e^{fast}+\theta_e^{slow}
+b_r^\top u_e(t)
-\lambda_{unc}\,\mathcal U_e(t)
+\alpha_e .
\end{aligned}
\]

여기서 `u_e(t)`는 freshness, provenance class, past success, contradiction/supersession 상태를
담는다. 관계 polarity를 하나의 부호에 뭉개지 않고 channel로 보존한다.

목적 node `j`에 들어오는 hyperedge들의 routing probability는 국소 정규화한다.

\[
\pi_t(e\mid j,q)
=\frac{\exp(\Psi_e(q,t)/\tau)}
{\sum_{e'\in Inc(j)}\exp(\Psi_{e'}(q,t)/\tau)}
\]

따라서 `Ψ`는 의미 에너지, `π`는 실제 activation/routing weight다. raw score와 확률을
동일시하지 않는다.

### C5. 작은 LLM은 neuron이 아니라 typed nonlinear function node다

작은 LLM 함수 node `f_i`는 다음 계약을 가진다.

\[
y_i^t
=P_i\!\left[
LLM_{\varphi}
\left(\rho_i,\operatorname{Read}_i(S_t),q_t\right)
\right]
\]

- `φ`: 여러 역할이 공유할 수 있는 frozen small foundation model;
- `ρ_i`: 함수 역할과 typed port contract;
- `P_i`: 자유 텍스트를 고정 schema와 bounded numeric activation으로 파싱하는 projection;
- `S_t`: HSWM 전체의 recurrent state.

같은 작은 모델을 여러 함수가 공유해도 HSWM은 성립한다. 차이는 micro-parameter가 아니라
각 node의 read/write 권한, relation position, 외부 state, routing과 outcome history다.

전체 상태는 다음과 같이 분리한다.

\[
S_t=(X_t,H_t,\Theta_t,\alpha_t,A_t,Z_t,P_t)
\]

- `X`: embedding coordinates;
- `H`: versioned hypergraph;
- `Θ`: relation/edge weights;
- `α`: topology logits;
- `A`: current activation;
- `Z`: eligibility traces;
- `P`: provenance and immutable evidence receipts.

이 분리는 중요하다. **embedding 변화, weight 변화, topology 변화, activation 변화는 서로 다른
사건**이며 같은 `vector update`로 기록하면 학습 원인을 증명할 수 없다.

### C6. hypergraph propagation은 incidence를 통과해야 한다

각 hyperedge 안에서 함수 출력과 node state를 먼저 관계 공간으로 옮겨 합성한다.

\[
m_e^t
=F_r\left(
R_{v_1\to e}a_{v_1}^t,\ldots,
R_{v_k\to e}a_{v_k}^t,y_{f_e}^t,q_t
\right)
\]

목적 node로 돌아가는 message는

\[
m_{e\to j}^t
=\pi_t(e\mid j,q)
R_{j\to e}^{\top}P_{r,j}m_e^t
\]

이고 recurrent activation은

\[
a_j^{t+1}
=(1-\gamma)a_j^t
+\gamma\,\operatorname{Norm}
\left(\sum_{e\in Inc(j)}m_{e\to j}^t\right).
\]

`Norm`과 bounded parser로 activation explosion을 막고, event budget·no-progress detector로
black-box LLM loop를 종료한다. LLM 자체가 비연속 black box이므로 전체 시스템의 전역 수렴을
증명했다고 과장하지 않는다. 수렴/안정성 정리는 deterministic numeric core에만 적용한다.

고차 의미가 실제로 남는지의 미분 가능한 필요조건은 positive-measure 입력 영역에서

\[
\frac{\partial^{|e|-1}\tau_{e\to i}}
{\prod_{j\in e\setminus i}\partial x_j}\ne0
\]

인 것이다. unary/pairwise 항의 합은 3차 이상 mixed derivative가 0이므로 이 조건을 통과하지
못한다. attention은 참여자를 고를 수 있지만 그 자체로 conjunction을 보장하지 않는다.

### C7. 결과가 `W`를 바꾸려면 three-factor learning이 필요하다

실행 전에 선택된 hyperedge와 route probability로 eligibility를 고정한다.

\[
z_{e,t}=\lambda_z z_{e,t-1}
+\nabla_{\Theta}\log\pi_{\Theta}(e_t\mid S_t,q_t)
\]

독립 outcome `r_t`와 preregistered predictor `rhat_t`로

\[
\delta_t=r_t-\hat r_t
\]

를 만든 뒤 fast weight를 갱신한다.

\[
\Theta^{fast}_{t+1}
=\operatorname{clip}
\left(\Theta^{fast}_{t}
+\eta_W\delta_t Z_t
-\lambda_W\Theta^{fast}_t\right)
\]

discrete topology gate `g_e~Bernoulli(σ(α_e))`는 LLM을 미분하는 척하지 않고 logged stochastic
routing의 score-function update를 쓴다.

\[
\Delta\alpha_e
=\eta_H\delta_t z_{e,t}(g_e-\sigma(\alpha_e))
-\lambda_0-\mu\,homeostasis(e)
\]

자연어 verdict나 새 lesson을 `W`라고 부르지 않는다. 학습 state는 versioned numeric artifact로
저장하고 rollback할 수 있어야 한다.

## 3. 이 조합이 기존 방식과 다른 점

| 방식 | node/function | relation | weight learning | HSWM과의 차이 |
|---|---|---|---|---|
| cosine RAG | chunk | pairwise similarity | 대개 없음 | 관계 type, n항성, recurrence 없음 |
| KG embedding | entity | 주로 triple score | offline gradient | 실행 함수·outcome 폐루프 없음 |
| hypergraph NN | numeric node | n항 incidence | end-to-end gradient | black-box LLM function과 provenance seam 없음 |
| MoE/router | expert | dispatch edge | router gradient | durable semantic hypergraph와 topology history 없음 |
| LLM agent graph | LLM operation | control-flow edge | prompt/edge optimization 가능 | semantic relation operator와 recurrent macro-weight가 약함 |
| **HSWM-SWF-v0** | typed small-LLM function | typed n항 energy + transport | outcome-driven numeric `ΔW/ΔH` | 전체 회로가 하나의 학습 주체인지 검증 대상 |

핵심 독창성 후보는 개별 구성요소가 아니라 다음 conjunction이다.

> **typed n-ary semantic energy + local coordinate transport + small-LLM nonlinear functions +
> outcome-driven versioned macroplasticity**

이는 아직 과학적 성과가 아니라 가장 강한 구현·반증 후보이다.

## 4. 반드시 지켜야 할 수학·시스템 invariant

1. **Local normalization**:
   `Σ_{e∈Inc(j)} π(e|j,q)=1`.
2. **Role symmetry**:
   unordered role만 permutation invariant; typed ordered role은 permutation equivariant.
3. **N-ary non-collapse**:
   같은 모든 pairwise marginal을 가진 두 hypergraph에 대해 일부 query에서
   `|Ψ_H1-Ψ_H2|≥m`인 사례가 존재해야 한다.
4. **Bounded activation**:
   parser output과 activation norm은 사전 고정 범위 안에 있어야 한다.
5. **No post-outcome trace**:
   `Z_t` receipt가 outcome보다 먼저 seal되어야 한다.
6. **Numeric mediation**:
   training answer·verdict·새 lesson text는 다음 agent의 prompt에 직접 들어갈 수 없다.
7. **Rollback necessity**:
   learned `W/H`를 이전 epoch로 되돌리면 gain의 대부분이 사라져야 한다.
8. **Snapshot integrity**:
   `H`, `W`, relation schema, embedding model/version을 각각 content-address한다.
9. **Field algebra preservation**:
   기존 merge/split/reassembly 결과는 derived embedding·weight cache와 독립이어야 한다.
10. **Homeostasis**:
    degree, route entropy, activation mass, edge budget이 사전 범위를 벗어나면 slow commit 금지.
11. **Geometry/effect identifiability**:
    embedding model과 `tau_r`를 measurement 동안 동결하고 `K_e`와 `theta_e`를 별도 ledger에 기록.
12. **Directed consistency**:
    `S_r`는 PSD, `A_r`는 skew-symmetric, inverse relation은 `B_inverse(r) ~= B_r^T`.
13. **Epoch stability**:
    fixed-routing numeric core의 projected operator norm과 damping이 contraction margin을 통과하거나,
    통과하지 못하면 fixed-point가 아닌 bounded recurrent execution이라고 보고.

## 5. 결정적 수학 실험 M1 — pairwise로는 절대 못 푸는 세계

### 5.1 paired worlds

동일한 7개 vertex를 가진 서로 다른 labeled Steiner triple systems 두 개를 만든다. 각 세계에서
모든 vertex pair는 정확히 한 번 나타나므로 pairwise co-occurrence matrix와 clique graph는
완전히 같다. 그러나 실제 ternary hyperedge 집합은 다르다.

```text
H1 = {123, 145, 167, 246, 257, 347, 356}
H2 = {123, 145, 167, 346, 357, 247, 256}
```

질문은 특정 세 tuple이 유효할 때만 올바른 작은 LLM 함수 조합을 선택할 수 있게 만든다.
entity surface와 prompt template은 train/fresh에서 분리한다.

### 5.2 arms

1. `FULL_SWF`: typed n-ary tensor + transport + product geometry;
2. `EUCLIDEAN_COSINE`: 현재 readout;
3. `CLIQUE_GNN`: 동일 pairwise weighted graph;
4. `HYPERGRAPH_SCALAR`: n항 incidence는 보지만 relation/role tensor 없음;
5. `PAIRWISE_RELATION`: relation-specific bilinear pair score의 합;
6. `TENSOR_SHUFFLE`: full 구조에서 relation tensor를 episode 간 shuffle;
7. `W_ROLLBACK`: learned tensor/edge weights를 initial epoch로 rollback.

모든 arm은 같은 small LLM, function library, input/output token, call count, candidate universe를
사용한다.

### 5.3 primary acceptance

- `FULL_SWF` fresh routing accuracy가 strongest equal-compute baseline보다 `>=10pp`;
- paired cluster-bootstrap 95% CI lower bound `>0`;
- 5 seeds 중 4개 이상 같은 방향;
- `TENSOR_SHUFFLE`과 `W_ROLLBACK`이 full gain의 `>=70%` 제거;
- H1/H2에서 clique input digest가 bit-identical;
- relation-role permutation이 사전예측한 방향으로 output을 바꿈;
- current/cosine arm은 chance band를 유의하게 벗어나지 못함.

### 5.4 kill criteria

- pairwise arm이 `FULL_SWF`와 ROPE `+-2pp` 안이면 n항 tensor 필요성 claim을 kill;
- tensor shuffle 후 gain이 50% 이상 남으면 relation energy가 원인이 아님;
- hidden tuple ID, prompt 문자열, candidate order로 world를 구분할 수 있으면 run VOID;
- full arm의 이득이 calls/tokens 증가에서 오면 run VOID;
- fresh entity/relation paraphrase에서 이득이 사라지면 lookup이지 semantic field가 아님.

## 6. geometry 실험 M2 — 왜 product space인가

세 relation family를 한 benchmark에 함께 둔다.

- semantic similarity/analogy;
- taxonomy/subsumption;
- directed support/contradict/supersede.

`Euclidean-only`, `hyperbolic-only`, `single learned MLP`, `product geometry + relation gate`를
equal-parameter로 비교한다.

acceptance:

- product arm의 macro-average가 strongest single geometry보다 `>=5pp`;
- 각 relation family에서 worst-group regression `<=2pp`;
- gate entropy가 collapse하지 않고 relation family와 mutual information을 가짐;
- geometry gate shuffle이 gain의 `>=50%` 제거.

실패하면 product space를 정전으로 올리지 말고 Euclidean + typed tensor의 더 단순한 모델을
선택한다.

## 7. 구현 순서

### Phase SWF-0 — cosine 대체 최소 수직 slice

1. 기존 embedding과 immutable `H`는 그대로 둔다.
2. 3-ary relation 1종, small-LLM function 3개만 연다.
3. `RelationSchema`, role-aware CP score, local softmax를 구현한다.
4. readout receipt에 `raw_energy`, `route_probability`, `relation_type`, `role_order`, `W_epoch`를
   기록한다.
5. M1 synthetic paired-world unit test를 먼저 GREEN으로 만든다.

### Phase SWF-1 — outcome plasticity

1. pre-outcome eligibility receipt;
2. independent scalar outcome;
3. fast `Theta/alpha` update;
4. credit-shuffle, tensor-shuffle, rollback;
5. prompt/content firewall.

### Phase SWF-2 — mixed geometry

M1이 통과한 뒤에만 Poincare channel과 relation gate를 추가한다. 처음부터 거대한 heterogeneous
embedding stack을 만들지 않는다.

### Phase SWF-3 — topology와 transfer

Agent A가 학습한 numeric `W/H` epoch만 frozen Agent B에 mount한다. A transcript와 자연어
verdict는 전달하지 않는다. shared weight가 B의 route를 바꾸고 rollback이 gain을 지우는지 본다.

### Phase SWF-4 — consolidation

fast loop와 causal mediation이 먼저 양성이 된 뒤에만 slow consolidation을 연다. 이전 F5의
단순 age-downscale는 재사용하지 않는다.

## 8. 외부 1차 소스 장부

| source | 흡수할 내용 | HSWM에 그대로 적용할 수 없는 점 |
|---|---|---|
| [TuckER, EMNLP 2019](https://aclanthology.org/D19-1522/) | relation-specific tensor factorization과 full expressivity | 주로 binary KG triple completion |
| [RESCAL, ICML 2011](https://icml.cc/2011/papers/438_icmlpaper.pdf) | relation별 bilinear operator의 고전적 선례 | full matrix는 현 HSWM 데이터에서 과적합 위험 |
| [GETD, 2020](https://arxiv.org/abs/2007.03988) | n-ary relation에 Tucker/Tensor-Ring factorization 적용 | KB completion이며 HSWM causal plasticity 증거가 아님 |
| [ComplEx, ICML 2016](https://proceedings.mlr.press/v48/trouillon16.pdf) | symmetric·antisymmetric 관계를 함께 표현 | binary triple model |
| [Poincare Embeddings, NeurIPS 2017](https://proceedings.neurips.cc/paper_files/paper/2017/hash/59dfa2df42d9e3d41f5b02bfc32229dd-Abstract.html) | latent hierarchy에 맞는 hyperbolic representation | HSWM의 heterogeneous relation 전체를 설명하지 않음 |
| [Learning with Hypergraphs, NeurIPS 2006](https://proceedings.neurips.cc/paper_files/paper/2006/hash/dff8e9c2ac33381546d96deea9922999-Abstract.html) | pairwise 축약이 multiway 정보를 잃을 수 있음 | LLM function·typed directed relation·plasticity 없음 |
| [Neural Sheaf Diffusion, NeurIPS 2022](https://proceedings.neurips.cc/paper_files/paper/2022/hash/75c45fca2aa416ada062b26cc4fb7641-Abstract-Conference.html) | node/edge local spaces와 learned restriction maps | graph 기반이며 HSWM hyperedge/LLM runtime은 별도 설계 필요 |
| [Sparse and Local Networks for Hypergraph Reasoning, LoG 2022](https://proceedings.mlr.press/v198/xiao22a.html) | sparse tensor로 n항 relation을 국소적으로 처리 | supervised reasoning network |
| [Recurrent Independent Mechanisms, ICLR 2021](https://openreview.net/forum?id=BylaUTNtPS) | 독립적인 recurrent mechanism과 sparse communication | small LLM 외부 함수망을 직접 다루지 않음 |
| [Modern Hopfield Networks, ICLR 2021](https://openreview.net/forum?id=tL89RnzIiCd) | energy와 normalized associative update의 연결 | HSWM semantic relation과 outcome plasticity는 별도 |
| [GPTSwarm, ICML 2024](https://proceedings.mlr.press/v235/zhuge24a.html) | LLM operation을 graph node로 두고 edge를 최적화 가능 | pairwise control graph이며 semantic hypergraph weight가 아님 |
| [Directed Hypergraph Representation Learning, AISTATS 2024](https://proceedings.mlr.press/v238/ma24b.html) | 방향 있는 hyperedge의 head/tail 구분 | HSWM typed function ports와 credit loop는 추가 필요 |
| [What relations are reliably embeddable in Euclidean space?, ALT 2020](https://proceedings.mlr.press/v117/bhattacharjee20a.html) | relation별 Euclidean embedding의 표현 한계 분석 | HSWM의 product-space 선택을 직접 증명하지 않음 |
| [REINFORCE, Williams 1992](https://link.springer.com/article/10.1007/BF00992696) | black-box stochastic route의 score-function update | 고분산이므로 baseline·여러 seed·logged propensity 필요 |
| [e-prop, Nature Communications 2020](https://www.nature.com/articles/s41467-020-17236-y) | eligibility trace와 delayed learning signal의 곱 | differentiable spiking RNN이며 HSWM 적용은 synthesis |

## 9. divergence와 열린 문제

1. **product geometry가 정말 필요한가?** typed tensor만으로 충분할 수 있다. M2가 결정한다.
2. **transport map을 learned linear map으로 둘 것인가, symbolic schema adapter로 둘 것인가?**
   v0은 둘을 구분해 receipt에 남긴다.
3. **LLM function output을 어디까지 embedding으로 압축할 것인가?** 과도한 압축은 provenance와
   예외를 지운다. symbolic payload와 numeric bottleneck을 함께 보존한다.
4. **negative relation을 signed scalar로 둘 것인가 channel로 둘 것인가?** v0은 support,
   contradict, supersede를 별도 channel로 두고 최종 action에서만 합성한다.
5. **전역 energy가 존재하는가?** black-box 비동기 LLM network에는 아직 증명하지 않는다.
   bounded numeric core와 finite execution semantics부터 증명한다.
6. **semantic gauge invariance**: embedding basis가 회전/재학습돼도 적절히 변환된 relation
   operator가 같은 routing을 내야 한다. v1의 중요한 이론 과제다.

## 10. 최종 finding

```yaml
finding_id: hswm-semantic-weight-is-typed-nary-operator
claim: >
  HSWM의 semantic weight는 embedding cosine scalar가 아니라, product embedding
  coordinates 위에서 typed roles를 n항으로 결합하고 local state spaces를 transport하며,
  context와 outcome history에 따라 routing을 정하는 versioned relation operator여야 한다.
status: PROPOSED_MATHEMATICAL_BELT
novelty_candidate: >
  typed n-ary semantic energy + local coordinate transport + small-LLM nonlinear
  functions + outcome-driven macroplasticity
first_falsifier: HSWM-SWF-M1
implementation_first_step: SWF-0 role-aware CP score replacing cosine-only readout
confidence: 0.91
```

결론적으로 사용자의 직관은 수학적으로 살릴 수 있다. 그러나 “큰 LLM”이라는 주장은 node
수나 embedding 크기로 얻는 것이 아니다. **작은 LLM 함수들의 실행 결과가 typed semantic
operator를 통해 재귀적으로 흐르고, 검증된 결과가 그 operator와 topology를 실제로 바꾸며,
그 상태 변화가 다음 행동의 원인이 될 때** HSWM 전체가 더 큰 학습 주체라는 주장이 선다.
