# Definition — HSWM cellular metaneural system

> **definition_id**: `hswm-cellular-metaneural-definition-20260726`
> **date**: 2026-07-26
> **authority split**: §0은 `USER_PRIMARY`; §1 이후 수식·조건·명칭은
> `SECONDARY_AI_FORMALIZATION`이며 사용자 정전을 교체하지 않는다.
> **formal witness**: `formal/HSWMCellular.lean`
> **Longinus**: `LONGINUS_HSWM_CELLULAR_DEFINITION_BINDING_2026-07-26.json`

## 0. USER_PRIMARY core

사용자 원문:

> “cell 같은 존재인거야 하나의 llm 이 그 신경망 하나의 함수처럼 동작하는거지 신경망 웨이트 함수처럼 뭔말인지 아냐 ㅇㅇ? hswm 를 좀 전체적 추상적으로 접근좀 해줘봐 ㅇㅇ”

기존 사용자 정전과 이번 원문이 함께 고정하는 핵심은 다음이다.

1. HSWM은 LLM을 호출하는 외부 orchestration이 아니라 **LLM이 함수세포로 실행되는 거대한
   semantic neural system**이다.
2. 논리적 LLM cell은 국소 상태와 typed port를 가진 semantic function이다.
3. hypergraph는 여러 cell·상태·증거가 이루는 n-ary connectivity다.
4. Semantic Weight Map은 cell 사이의 macro-synapse이며, HSWM 전체가 activation, credit,
   acceptance, weight와 topology 변화를 소유한다.
5. HSWM 집단도 같은 인터페이스로 다시 연결·분리·전문화될 수 있고 고정 층 번호가 없다.

## 1. 한 문장 정의

> **HSWM은 typed stateful LLM-cell들의 출력이 operator-valued n-ary semantic synapse를 통해
> 다른 cell의 입력으로 변환되고, 그 recurrent trajectory의 외부 결과가 fast/slow synapse와
> topology를 인과적으로 바꾸며, 합성된 전체도 다시 하나의 open stateful cell로 작동하는
> 자기유사 가소성 metaneural system이다.**

`metaneural`은 새 정전 이름이 아니라 “신경망 내부 cell 자체가 다시 neural language model”인
두 스케일을 구분하기 위한 설명어다.

## 2. 전체 객체

\[
\boxed{
\Omega_t=
(F_t,H_t,\mathcal W_t,\alpha_t,A_t,S_t,Z_t,M_t,G_t,P_t)
}
\]

| symbol | object | 책임 |
|---|---|---|
| `F` | logical LLM-cell family | typed semantic nonlinear transformation |
| `H` | directed typed hypergraph | n-ary incidence와 role, 공개 port |
| `W` | operator-valued semantic synapses | relation, transport, contextual gate, efficacy, uncertainty |
| `alpha` | topology gate/proposal state | 어떤 incidence가 회로에 존재·활성화되는지 |
| `A` | semantic activation packets | 주장·증거·계획·belief·tool result 같은 순간 상태 |
| `S` | local + global recurrent state | cell private state, workspace, scheduler state |
| `Z` | sealed eligibility traces | outcome 이전 사용 cell·synapse·route 기록 |
| `M` | episodic/fast/slow/exception memory | 경험 보존과 consolidation |
| `G` | control and acceptance plane | budget, homeostasis, canary, rollback, commit |
| `P` | immutable provenance plane | source, version, receipt, causal intervention log |

`CAS`, `CRDT`, replay, signature와 fail-closed validation은 `G/P`의 안전·증거 평면이다. 그것들이
LLM-cell이나 semantic synapse 자체인 것은 아니다.

## 3. Cell

논리 cell `i`는 다음 stateful stochastic semantic function이다.

\[
f_i:\mathcal X_i\times S_i
\longrightarrow
\operatorname{Dist}(\mathcal Y_i\times S_i')
\]

\[
f_i=P_i\circ LLM_{\phi_i}(\rho_i,\operatorname{Read}_i(\cdot))
\]

- `phi_i`: 내부 micro neural weight를 가진 model checkpoint;
- `rho_i`: 역할과 typed contract;
- `Read_i`: HSWM state에서 읽을 수 있는 범위;
- `P_i`: 자유 출력을 bounded typed packet으로 투영;
- `S_i`: 국소 기억과 활성 상태.

같은 `phi`가 여러 논리 cell을 실행할 수 있다. cell identity는 모델 파일 하나만이 아니라
`(role, ports, local state, position, read/write authority)`다. 서로 다른 model을 쓰는 것도 허용한다.

## 4. Semantic synapse

hyperedge `e`가 `k`개 tail cell에서 head cell `j`로 갈 때:

\[
\mathcal W_{e,t}:
\prod_{i\in tail(e)}\mathcal Y_i\times Context_t
\longrightarrow
\operatorname{Dist}(\mathcal X_j)
\]

따라서 semantic weight는 단일 cosine이나 scalar가 아니라 다음 묶음이다.

\[
\mathcal W_e=
(K_e,T_e,g_e,\theta_e^{fast},\theta_e^{slow},U_e,z_e)
\]

- `K`: relation/argument-role compatibility;
- `T`: 서로 다른 local semantic space 사이 transport;
- `g`: contextual activation gate;
- `theta_fast/slow`: outcome으로 학습한 causal efficacy;
- `U`: uncertainty, support/contradict/supersede, provenance;
- `z`: pre-outcome eligibility.

즉 **의미는 embedding 좌표 자체가 아니라, 특정 문맥에서 다른 cell의 이후 계산과 외부 결과를
어떻게 바꾸는가라는 conditional causal disposition**이다. scalar weight는 이 operator의 한
parameter 또는 projection일 수는 있어도 전체 정의가 아니다.

## 5. 세 nested clock

### 5.1 inference/activation clock

\[
A_{t+1}=\Phi_{F,H,W,G}(A_t,S_t,u_t)
\]

한 forward pass는 고정 layer를 한 번 통과하는 연산이 아니라 budget 또는 stop condition까지의
bounded asynchronous recurrent trajectory다. inference episode 안에서는 topology version을 고정한다.

### 5.2 plasticity clock

\[
z_n=Seal(trajectory_n)
\]

\[
\delta_n=outcome_n-\widehat{outcome}_n,
\qquad
W_{n+1}^{fast}=Apply(W_n^{fast},Credit(z_n,\delta_n))
\]

`Seal` 타입에는 outcome이 들어가지 않는다. candidate update는 rollback 가능해야 하고,
`W` 제거·shuffle에서 이후 gain이 사라져야 한다.

### 5.3 morphogenesis clock

\[
(F,H,\alpha)_{k+1}
=Develop((F,H,\alpha)_k,validated\ evidence_k)
\]

한 structural epoch은 `cell | synapse | topology | interface` 중 한 mutation class만 제안한다.
shadow execution, fresh utility, retention, complexity, canary를 통과한 proposal만 commit한다.

## 6. 자기유사성과 전체 인지체

내부 cell과 state를 감춘 realized HSWM은 다시 같은 open-cell interface다.

\[
Expose(\mathfrak H):(Input,S_{global})\to(Output,S_{global}')
\in\mathsf{Cell}
\]

\[
Compose(\mathfrak H_1,\ldots,\mathfrak H_n,connectors)
\in\mathsf{HSWM}
\]

재귀는 저장 tree가 아니라 **interface closure**에 있다. aggregate의 port를 다른 aggregate에
연결해도 된다. 고정 `layer/depth`는 정본 state가 아니다.

## 7. Agent, MoE, consensus와의 관계

| 인접 개념 | HSWM에서의 위치 | HSWM 전체와 다른 점 |
|---|---|---|
| agent | cell을 실행하거나 구조 mutation을 제안하는 control actor | 독립 agent들의 대화망이 정본 substrate가 아님 |
| MoE/router | query-time cell coalition을 고르는 특수 routing regime | persistent n-ary `W/H`, outcome plasticity, self-similar composition이 더 큼 |
| RAG/vector memory | 후보 packet 생성·좌표 channel | macro-synapse나 causal learning 그 자체가 아님 |
| workflow | frozen `H/W`의 한 실행 snapshot | HSWM은 weight·topology가 학습됨 |
| consensus | `G` 또는 collective subnetwork의 claim-local aggregation operator | agreement는 truth가 아니며 HSWM은 합의를 포함하는 더 큰 AI |
| monolithic LLM | cell 내부 `phi` 또는 강한 baseline | HSWM의 macro state와 synapse는 모델 밖에서 지속·검사·재배선됨 |

## 8. 형식 조건, 공학 조건, 과학 조건

### 8.1 Lean으로 검사

- cell input/output contract preservation;
- compatible cell composition;
- nonempty n-ary tail과 typed head transport;
- disabled route fail-closed;
- realized network의 macro-cell interface;
- outcome-before-trace leakage를 막는 타입 순서;
- candidate rollback;
- 한 proposal당 한 mutation class;
- reject된 structural proposal의 no-op;
- 단순 연결만으로 larger-AI 조건이 나오지 않는 negative theorem.

### 8.2 runtime에서 검사

- version-pinned state와 deterministic replay;
- bounded scheduler와 visited/budget guard;
- CAS conflict, signature, provenance completeness;
- candidate/shadow/commit/rollback FSM;
- equal-information/equal-compute comparison arms.

### 8.3 sealed experiment로만 검사

1. persistent macro state;
2. closed outcome→credit→`Delta W`;
3. learned `W`의 causal mediation;
4. learned topology의 causal mediation;
5. transcript 없는 A→frozen-B transfer;
6. strongest-cell/full-context baseline 초과;
7. retention·exception preservation·rollback.

이 일곱 conjunction을 `HSWM.LargerAIConditions`로 둔다. Lean은 논리 shape만 보존하며 runtime이
조건을 충족했다고 선언하지 않는다.

## 9. 현재 구현과 정의의 Longinus gap

| definition element | current materialization | binding state |
|---|---|---|
| typed logical cell | `hswm_function_registry.FunctionSpecV1` | `PARTIAL`: typed role은 있으나 cell-local transition 없음 |
| cell execution | `hswm_function_network.run_item` | `PARTIAL`: function sequence는 있으나 general recurrent cell dynamics 아님 |
| self-similar open composition | `hswm_open_composition.OpenHSWM/compose` | `STRUCTURAL_EXACT`: fixed-depth-free closure 구현 |
| operator semantic synapse | `hswm_open_composition.SemanticWeight` | `PARTIAL`: 현재 slow scalar `log_salience` |
| candidate numeric weight | `hswm_weight_snapshot.WeightSnapshotV1/apply_candidate` | `PARTIAL`: snapshot/commit seam은 있으나 operator update 아님 |
| recurrent control state | `feedback_runtime.FeedbackState/evolve` | `PARTIAL`: deterministic event state, semantic cell recurrence와 분리 |
| learned topology | `f4_topology_learning_r2.learn_anchor_edges` | `CONFOUNDED`: class-tag→lesson lookup 성격 |
| three nested clocks | Lean definition only | `UNIMPLEMENTED_AS_ONE_RUNTIME` |
| larger-AI conjunction | Lean condition + PROM falsifiers | `UNPROVEN` |

## 10. 금지되는 과대해석

- Lean compile을 scientific progress라고 부르지 않는다.
- `OpenHSWM.compose` closure를 collective intelligence라고 부르지 않는다.
- scalar `log_salience`가 존재한다고 operator-valued synapse가 구현됐다고 하지 않는다.
- LLM 호출 횟수나 agent 수를 cell differentiation의 증거로 쓰지 않는다.
- synthetic lookup positive를 topology learning 일반 증거로 승격하지 않는다.
- consensus, criticality, consciousness, organism을 task score 하나에서 추론하지 않는다.

## 11. 다음 결정실험

`HSWM-CELL-0`는 frozen LLM-cell 3개, irreducible ternary synapse 1개, bounded recurrence 1개로
제한한다. scalar/shuffle/removal/full-context/strongest-cell controls를 동일 예산으로 비교한다.
outcome 뒤 operator `W`만 바뀌고, learned `W` rollback이 gain의 최소 70%를 제거하며,
세-cell motif를 macro-cell로 합성해도 공개 behavior가 보존될 때 다음 단계로 간다.

## 12. 권위 경로

1. USER_PRIMARY: 본 문서 §0 literal utterance;
2. canonical direction: `HSWM_CANONICAL_RESEARCH_DIRECTION_20260724.md`;
3. open self-similar structure: `SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md`;
4. semantic weight mathematics: `PROM_16_HSWM_SEMANTIC_WEIGHT_FIELD_MATHEMATICS_2026-07-26.md`;
5. holistic theory map: `PROM_16_HSWM_HOLISTIC_SCIENTIFIC_ARCHITECTURE_2026-07-26.md`;
6. Lean: `formal/HSWMCellular.lean`;
7. runtime/test/receipt bindings: Longinus manifest.

KG는 이번 write scope에 포함하지 않는다. Longinus manifest의 `kg_anchor`는 local proposed
reference identity이며 operational KG materialization으로 읽으면 안 된다.
