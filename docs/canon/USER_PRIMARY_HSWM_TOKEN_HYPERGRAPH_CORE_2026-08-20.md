# HSWM 핵심 정전 — LLM token으로 작동하는 거대 Hypergraph Semantic Weight Map

> **상태:** `USER_PRIMARY_CORE_PRIORITY / SECONDARY_AI_TECHNICAL_FORMALIZATION`
> **권위 경계:** Hypergraph Semantic Weight Map 그자체가 가장 중요하며,
> LLM token으로 작동하는 거대 hypergraph 학습구조라는 방향은
> `USER_PRIMARY`다. 아래 수식·runtime·scaling·실험 계약은 기존 정전과
> 선행연구를 합친 `SECONDARY_AI_PROPOSED`이며, 현재 구현·효능 성공 주장이 아니다.
> **과학적 상태:** `UNJUDGED`
> **원문:**
> [`USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.txt`](sources/USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.txt)
> **원문 SHA-256:** `03ddd83fae4b98f8e1ee7cfa5e139d3bc98a7614cae7e33e0e55899651506c8c`
> **상위 정전:** [`HSWM_CONSTITUTION_2026-08-20.md`](HSWM_CONSTITUTION_2026-08-20.md)
> **철학적 제약:**
> [`HSWM_PHILOSOPHICAL_FOUNDATIONS_2026-08-20.md`](HSWM_PHILOSOPHICAL_FOUNDATIONS_2026-08-20.md)
> **선행연구 감사:**
> [`HSWM_TOKEN_HYPERGRAPH_SEMANTIC_WEIGHT_PRIOR_ART_2026-08-20.md`](../research/HSWM_TOKEN_HYPERGRAPH_SEMANTIC_WEIGHT_PRIOR_ART_2026-08-20.md)

## 0. 답부터

HSWM의 중심은 KG, RAG, agent 오케스트레이션, 규칙 문서가 아니다.

> **HSWM의 중심은 LLM token event가 활성으로 흐르고, role을 가진 n-ary
> hyperedge가 그 활성을 전달·억제·변환하며, 외부 outcome이 그
> hyperedge의 semantic weight와 topology를 시간을 건너 바꾸는 거대한 학습
> 신경구조다.**

철학은 이 핵심을 대체하지 않는다. 관계적 존재론은 role-bearing
hyperedge를, 계보적 시간론은 versioned `H/W`를, 기억–진리 분리는
uncertainty/evidence channel을, 인과적 행위성은 outcome-bound plasticity를
강제한다. 즉 **철학의 기술적 종착점은 대부분 `H/W/A`이다.**

## 1. 이 원문이 더한 개념적 delta

기존 헌법은 이미 HSWM을 다음처럼 두었다.

```math
S_t = \operatorname{HSWM}_t=(H_t,W_t,A_t,F_t,\Pi_t),
\qquad \Pi_t\equiv(\Pi^*,\Gamma_t)
```

새 USER_PRIMARY는 여섯 번째 subsystem을 추가하지 않는다. 다음 우선순위를
확정한다.

1. `H/W/A`가 HSWM의 **신경조직 그 자체**다.
2. `F`는 그 조직의 국소 비선형 세포를 LLM으로 실행한다.
3. `Π`는 그 조직이 출처·권한·개체성·rollback을 파괴하지 않게 하는
   구성적 막이다.
4. KG·ontology·Markdown·MCP·vector store는 이 신경조직의 저장, projection,
   I/O interface일 수는 있지만 그 자체가 HSWM은 아니다.

그러므로 “HSWM을 구현한다”는 말의 첫 번째 판별은 문서 수가 아니라
**token activation이 `W`를 통해 다음 활성을 바꾸고, outcome이 그 `W/H`를
다시 바꾸는지**다.

## 2. 핵심 객체의 기술적 형식

### 2.1 `H` — role과 계보를 가진 canonical hypergraph

```math
H_t=(V_t,E_t,I_t,\mathcal R,P_t)
```

- `V_t`: 개체, 사건, 주장, 근거, 기억, function port, tool, outcome의 stable
  semantic identity.
- `E_t`: 하나의 관계에 여러 참여자가 동시에 들어갈 수 있는 reified n-ary
  hyperedge.
- `I_t`: node–hyperedge 소속 자체를 first-class record로 두는 incidence.
- `R`: relation type과 허용 role, symmetry, input/output port, polarity의 schema.
- `P_t`: source artifact, valid/observation/commit time, authority, contradiction,
  supersession, access scope의 provenance.

하나의 incidence는 단순 boolean이 아니라 최소한 다음 논리 record다.

```text
Incidence(v, e)
  role                 # subject / object / evidence / judge / input / output ...
  direction            # into-edge / out-of-edge / bidirectional
  semantic_type
  source_artifact_id
  valid_time
  observed_at
  authority
  polarity             # support / contradict / supersede / neutral ...
  capability_scope
```

role이 다른 구성원을 unordered set으로 뭉개면 `A supports B`와 `B supports A`를
구분할 수 없다. 반면 같은 unordered role 안에서는 순열에 불변해야 한다.
이것이 HSWM의 role-aware n-ary symmetry 계약이다.

### 2.2 `W` — scalar가 아닌 operator-valued macro-synapse

Semantic Weight Map의 핵심 단위는 유사도 숫자 하나가 아니다.

```math
\mathcal W_{e,t}=
(\Theta_{r},\{R_{r,\rho}\},\theta^{fast}_{e,t},\theta^{slow}_{e,t},
\alpha_{e,t},z_{e,t},U_{e,t})
```

| 상태 | 의미 | 시간 척도 |
|---|---|---|
| `Θ_r` | relation type `r`의 role-aware n-ary semantic energy core | offline/slow shared parameter |
| `R_{r,ρ}` | role `ρ`의 국소 state를 relation space로 옮기는 transport | shared + optional low-rank adapter |
| `θ_fast` | 최근 outcome에 따른 빠른 인과 효능 | episode–session |
| `θ_slow` | 반복 검증·retention을 통과한 장기 거시 가중치 | days–epochs |
| `α_e` | 해당 relation이 실제 회로로 열릴 topology gate logit | morphogenesis |
| `z_e` | outcome 전에 seal되는 activation/eligibility trace | episode-local |
| `U_e` | provenance, uncertainty, support, contradict, supersede, freshness channel | versioned evidence state |

이 표는 runtime locality를 나타내며 canonical ownership을 바꾸지 않는다. claim, evidence,
judgment, outcome record와 provenance의 정본은 `H`와 그 `P_t`에 있고, `U_e`는 그 content-addressed record를
가리키는 실행용 derived projection이다. `z_e`는 `A`의 used-path에서 파생된다. `W`는 이
channel을 routing에 사용할 수 있지만 truth나 permission을 자체 weight로 생산하지 못하며,
권한은 계속 `Π`가 집행한다.

관계의 의미와 결과에 대한 효능은 반드시 분리한다.

```math
\underbrace{K_e(q,c)}_{\text{semantic compatibility}}
\ne
\underbrace{\theta_{e,t}}_{\text{causal efficacy}}
```

`K_e`는 “이 query에서 무슨 의미로 맞는가”이고, `θ_e`는 “이 관계를 통해
실제 행동했을 때 outcome에 얼마나 기여했는가”이다. cosine, confidence,
causal credit을 하나의 scalar에 넣으면 왜 route가 변했는지 식별할 수 없다.

대규모에서는 모든 edge에 full tensor를 저장하지 않는다. `Θ_r`·`R_{r,ρ}`는
relation/role 단위로 공유하고, edge는 작은 `θ_fast/θ_slow/α/U` state와
provenance pointer를 소유한다. 필요한 edge만 low-rank adapter를 가진다.

### 2.3 `A` — token이 운반하는 휘발성 활성

“LLM token으로 작동한다”는 말은 모든 token을 영구 node로 저장한다는 뜻이
아니다. 신경 신호의 최소 운반체를 다음처럼 둔다.

```text
TokenActivationV1
  artifact_id                  # raw input/output/tool result event envelope의 stable identity
  span_or_token_refs
  tokenizer_and_model_digest
  semantic_type
  relation_role
  source / authority / time
  capability_scope
  dense_or_sparse_state
  activation_amplitude
  trace_id / parent_trace_ids
```

- raw token/span은 먼저 retention·authorization 범위를 가진 event artifact다. 여기서 stable 또는
  append-only인 것은 무단 overwrite를 막는 event envelope와 transition order이지, 보호 payload의
  영구 recoverability가 아니다. `Π`에 따른 철회·삭제에서는 payload, 취약한 content hash와
  재식별 가능한 파생 상태를 제거·비가역 비식별화하고 비식별 최소 erasure event만 남긴다.
- token packet은 현재 run의 활성이며 영구 truth가 아니다.
- tokenizer ID와 model-specific embedding은 canonical semantic identity가 아니다. model/tokenizer
  교체 시 artifact/span/role/provenance를 유지하고 transduction loss와 digest를 기록한다.
- LLM이 추출한 concept/relation은 candidate이며 provenance·schema·outcome gate 후에만
  canonical `V/E`로 승격한다.
- durable graph에는 token 전체를 복제하기보다 artifact/span pointer, typed summary,
  인과 trace, 필요한 원문 계보를 남긴다.

### 2.4 `F` — LLM으로 실행되는 typed nonlinear cell

```math
y_f^\ell=P_f\!\left[
\operatorname{LLM}_{m_f}
(\rho_f,\operatorname{Readout}(A^\ell,H_t,W_t),q,c)
\right]
```

- `ρ_f`: 비교, 추론, 근거 검사, 판정, tool 사용 등의 stable role contract.
- `P_f`: 자유 문자열을 typed output, bounded activation, proposal로 변환하는 parser.
- `m_f`: 교체 가능한 model reference. 해당 LLM의 parameter는 cell 내부 micro-weight이지
  HSWM `W`가 아니다.

모든 edge마다 LLM을 호출하면 규모화할 수 없다. numeric role-aware propagation이
대부분의 candidate를 압축하고, 선택된 function port에서만 LLM cell이 비선형
의미 전이를 실행한다.

### 2.5 `Π` — 학습하는 신경망의 막

무첨자 `Π`는 policy family `Π={Π_t}`를, 특정 snapshot의 `Π_t`는 `(Π*, Γ_t)`를 뜻한다.
`Π*`는 provenance 정직성, scoped authority, consent, privacy, correction, dissent,
exit·appeal·rollback과 durable credit의 proposer·executor·evaluator 역할 분리를 보존하는
identity-bearing meta-boundary이고,
`Γ_t`는 role/type, capability, source, budget, transaction, evaluator와 current policy의
versioned 운영 상태다. `W/H`는 활성 경로를 학습하지만 어느 층도 자기 reward로 우회할 수
없다. `Γ_t` 변경은 명시적 mandate·authority·versioning 사건이고, `Π*` 변경은 일반 plasticity가
아닌 별도 헌법 사건이다. `Π`는 judgment 절차와 권한을 집행하지만 judgment 내용이나 truth를
소유하지 않는다.

## 3. 한 번의 신경 실행

### 3.1 sparse active subgraph

query/observation은 전체 그래프를 prompt에 넣지 않는다. 현재 활성에 인접하고
권한이 허용된 edge에서만 local score를 계산한다.

```math
\Psi_e(q,c,t)=K_e(q,c)
+\theta^{fast}_{e,t}+\theta^{slow}_{e,t}
+\log\sigma(\alpha_{e,t})
+b_r^\top U_{e,t}
-\lambda_{cost}C_e
```

active snapshot에서 닫힌 edge의 score는 `-∞`다. 열린 edge에서만 node/function
`j`별로 국소 정규화한다.

```math
\pi_t(e\mid j,q)=
\operatorname{softmax}_{e\in Inc(j)\cap E_t^{active}}\Psi_e(q,c,t)
```

전역 softmax나 dense all-to-all attention은 HSWM의 필요조건이 아니다. 실제 runtime은
top-k, budget, uncertainty, capability를 함께 사용한 bounded frontier를 편성한다.

### 3.2 role-aware `V → E → V` propagation

각 node state를 role relation space로 옮겨 하나의 고차 메시지로 조합한다.

```math
h_e^\ell=\Phi_r\!\left(
\{(\rho_i,R_{r,\rho_i}a_{v_i}^\ell)\}_{i\in I(e)},q,c
\right)
```

`Φ_r`는 같은 unordered role 안에서는 permutation invariant이고, role과 direction이
바뀌면 equivariant하거나 다른 값을 내야 한다. hyperedge의 한 pooled vector를
모든 member에게 똑같이 방송하지 않고, 수신 role과 현재 state에 따라 다른
message를 만든다.

```math
m_{e\to v_i}^\ell=
\rho_{r,\rho_i}(a_{v_i}^\ell,h_e^\ell,q,c)
```

```math
a_{v_i}^{\ell+1}=\operatorname{Norm}\!\left[
(1-\gamma)a_{v_i}^{\ell}
+\gamma\sum_{e\in Inc(v_i)}\pi_t(e\mid v_i,q)m_{e\to v_i}^{\ell}
\right]
```

function port가 점화되면 그때 `F`의 LLM 실행이 token packet을 만들고, 그 output은
다시 같은 incidence runtime으로 들어간다. 이것이 “LLM token으로 작동하는
hypergraph”의 전진 의미론이다.

### 3.3 종료와 안정성

black-box LLM이 들어간 전체망의 전역 수렴을 주장하지 않는다. 대신 실행 단위에
다음을 강제한다.

- activation norm과 typed parser의 bounded range;
- max frontier, hops, calls, tokens, latency, cost;
- no-progress/cycle detector;
- route entropy, hub share, activation concentration, effective rank monitor;
- fixed numeric core에 대한 contraction/stability test;
- timeout이나 uncertainty 상승 시 abstain/stop.

## 4. 학습은 세 개의 시계로 돌아간다

### 4.1 활성 시계 — 지금 무엇이 점화되는가

`A_t`, query-local potential, working token packet이 변한다. 이것은 현재 인지이지 아직
durable learning이 아니다.

### 4.2 plasticity 시계 — 무엇이 다음 행동을 바꾸는가

outcome이 알려지기 **전** 실제 선택된 edge/function의 기여를 seal한다.

```math
z_{e,t}=\lambda_z z_{e,t-1}+\widetilde{c}_{e,t}
```

`\widetilde{c}_e`는 logged route probability, activation contribution, selected action으로부터 구한다.
LLM의 사후 설명을 과거 eligibility로 대체하지 않는다. proposer와 분리된
environment/judge가 다중 outcome vector와 사전 예측을 반환한다.

여기서 독립은 HSWM 전체의 물리적 바깥을 요구하는 말이 아니라, 평가 대상 trajectory의
proposer·executor가 outcome을 임의로 쓰거나 최종 판정을 독점하지 못하는 역할 분리다.
사전 특정된 estimand, intervention 또는 정당화된 식별 가정, evaluator scope와 uncertainty
bound가 없으면 outcome 관측은 보존하되
`Attribution(outcome, trajectory)=UNATTRIBUTABLE`이며 durable `W/H` update를 만들지 않는다.

```math
\delta_t=o_t-\hat o_t\in\mathbb R^m
```

현재 scope의 versioned evaluation policy `ω`가 허용한 경우에만 scalar update signal을
만든다. 원래 outcome vector, 평가자, 가중치, 제약 위반을 모두 receipt에
남긴다.

```math
\Delta\theta^{fast}_{e,t}
=\operatorname{clip}\left(
\eta_W z_{e,t}\langle\omega_t,\delta_t\rangle
-\lambda_W\theta^{fast}_{e,t}\right)
```

`θ_slow`로의 consolidation은 독립 fresh set, retention, canary, replay, rollback test와
반복 evidence를 통과한 fast delta만 받는다. 학습되는 값은 자연어 lesson이
아니라 권한·retention 범위 안에서 content-addressed되는 numeric/operator state이다. 보호된
입력에서 파생된 state는 같은 보호·철회 요구를 상속하며, content address가 payload의 영구
보존 의무를 만들지 않는다.

### 4.3 morphogenesis 시계 — 무엇이 실제로 연결되는가

`ADD / SPLIT / MERGE / SUPERSEDE / SPECIALIZE / SEPARATE`는 즉시 active graph를
바꾸지 않고 candidate epoch을 만든다.

```math
\Delta\alpha_e
=\eta_H z_{e,t}\langle\omega_t,\delta_t\rangle
-\lambda_{degree}D_e
-\lambda_{collapse}C_e
```

후보는 topology-shuffle, equal-compute, fresh, canary, provenance, authority gate를 통과해야
atomic snapshot으로 활성화된다. `SUPERSEDE`는 과거를 지우는 delete가 아니라
현재 활성에서 억제하고 수정 계보를 연결하는 상태 전이다.

### 4.4 학습이라 부를 수 있는 최소 사슬

```text
token/action trajectory sealed before outcome
  → independently attributable outcome
  → eligibility × advantage
  → shadow ΔW 또는 ΔH candidate
  → fresh / retention / canary / replay
  → atomic activation
  → next routing/action changes
  → rollback/removal이 그 gain을 제거
```

마지막 두 줄이 없으면 저장, 관측 또는 적응일 수는 있어도 HSWM의 인과적
학습으로는 세지 않는다.

## 5. 철학을 `W`로 내리는 법

| 철학 원리 | `H/W/A/F/Π`의 기술적 의무 | 반례 |
|---|---|---|
| 관계적 존재론 | role-bearing n-ary `E/I`, relation energy `Θ_r` | payload embedding만 있는 vector DB |
| 계보적 시간론 | versioned `H/W` epoch, three times, supersession lineage | 최신값 overwrite |
| 기억–진리 분리 | `U_e`의 evidence/uncertainty/polarity channel | retrieval score = truth |
| 오류의 생산성 | negative outcome, contradiction, failed route를 분리 보존 | 실패 trace 삭제 |
| 차이 보존적 통일 | role transport, member-specific `E→V`, local state, anti-collapse monitor | 모든 member에 같은 pooled message |
| 인과적 행위성 | pre-outcome `z`, independent `δ`, rollback/removal mediation | transcript 추가 = learning |
| 참여와 존엄 | human incidence의 consent/capability/exit 집행 | 사람 = 무권한 token source |
| 공개 외부·보호 내부 | public port + protected state + provenance-preserving transport | open source = open private data |
| 인지주권·보충성 | local normalization, bounded coalition, admission/judge/commit 권한 분리 | global broadcast, single sovereign router |
| 열린 목적론 | outcome vector, versioned evaluator, constraints·minority evidence 보존 | 영구 단일 reward |

즉 철학은 일반적 선의 문구가 아니라 `W`의 state type, update rule,
acceptance gate를 바꾸는 설계 입력이다.

## 6. 거대 hypergraph를 실제로 작동시키는 이중 표현

### 6.1 canonical persistent plane — 출처 있는 인식 상태의 정본

- n-ary hyperedge와 role-bearing incidence를 그대로 보존한다.
- artifact, claim, evidence, judgment, outcome, provenance, valid/observation/commit time,
  `H/W` epoch을 허용된 보존 기간 동안 content-address한다. 삭제권이 적용되면 event envelope의
  비식별 최소 계보만 남기고 보호 payload·취약 hash·재식별 가능한 derived state를 제거한다.
- `Accepted(claim | evidence, scope, evaluator, valid_at, judged_at, judgment_uid, policy)`의
  계보를 보존할 뿐,
  원장에 들어왔다는 사실이나 현재 routing weight를 무범위의 truth로 선언하지 않는다.
- 추론 cache, embedding, compiled adjacency는 파생물이며 원장 정체성에 들어가지 않는다.
- 분산 node에서는 append-only event + snapshot/CAS로 수렴한다.

### 6.2 compiled neural plane — 실행을 위한 파생 회로

- 현재 query와 capability에 필요한 국소 `V/E/I/W` cut만 compile한다.
- GPU에서는 sparse incidence matrix나 star expansion을 쓸 수 있다.
- pairwise 실행 그래프로 compile하더라도 canonical n-ary edge와 role을 잃지 않는
  reversible mapping과 digest를 남긴다.
- cache를 전부 지워도 canonical plane에서 같은 실행 cut을 재생성할 수 있어야 한다.

이 분리가 없으면 성능을 위한 clique/star expansion이 원래 고차 의미를
대체하거나, 반대로 완전한 원장을 매 LLM call에 넣느라 시스템이 멈춘다.

## 7. scale 아키텍처

| 문제 | HSWM 처방 |
|---|---|
| token 폭증 | raw stream은 retention-scoped revocable artifact ref로 받고, durable `V/E`는 검증된 concept/relation만 승격 |
| edge 파라미터 폭증 | relation/role core 공유 + per-edge small fast/slow/gate state + 예외만 low-rank adapter |
| 전역 attention 비용 | local incidence softmax, approximate candidate index, top-k bounded frontier |
| LLM call 비용 | numeric propagation/batching 후 선택된 function cell만 호출; semantic result cache는 model/prompt/cut digest에 결속 |
| 분산 일관성 | mount/port 단위 partition, append-only transition envelope, revocable payload, epoch snapshot, CAS, idempotent replay |
| stale 활성 | valid/observation/commit time 분리, epoch fence, freshness channel |
| hub/routing collapse | degree budget, entropy floor, hub share/Gini/effective-rank monitor, homeostatic penalty |
| 긴 기억 | hot activation / warm fast-W / cold evidence+slow-W 계층, 계보 pointer로 재활성 |
| 연합 확장 | private local state는 남기고 public typed port와 최소 provenance만 connector로 공유 |

거대함은 모든 것이 항상 RAM/GPU/prompt에 들어있다는 뜻이 아니다. **전체가
영속적으로 addressable하고, 현재 필요한 국소 회로가 손실 없이 컴파일되며,
그 국소 결과가 전체의 다음 상태를 바꾼다**는 뜻이다.

## 8. 구현 순서 — 그래프 DB보다 neural core를 먼저 반증한다

### SWM-0 — n-ary non-collapse witness

- role-bearing ternary relation 1종, numeric function 3개, paired hypergraph world를 쓴다.
- pairwise co-occurrence/clique digest는 같지만 정답은 다른 두 world를 만든다.
- role-aware `Θ/R` arm이 cosine, clique GNN, scalar hyperedge, pairwise relation sum을 이겨야 한다.
- 이 관문을 넘지 못하면 복잡한 operator `W`를 축소한다.

### SWM-1 — sparse recurrent numeric core

- first-class incidence + local `V→E→V` + member-specific message를 구현한다.
- AllSet-style multiset core, ED-HNN-style equivariant diffusion, simpler DeepSets baseline을
  equal-parameter/equal-compute로 비교한다.
- role shuffle, incidence shuffle, edge ablation이 성능을 붕괴시켜야 한다.

### SWM-2 — LLM token function loop

- 같은 frozen LLM으로 최소 3개 typed function role을 실행한다.
- weighted HSWM, fixed linear workflow, transcript/vector memory를 같은 calls/tokens/latency로 비교한다.
- `W=0`, shuffled `W`, pairwise-reduced topology 대조군을 포함한다.

### SWM-3 — outcome-bound fast `W`

- pre-outcome eligibility, independent outcome, prompt/content firewall를 잠근다.
- outcome→`Δθ_fast`→next route change를 하나의 receipt로 결속한다.
- credit shuffle, outcome-time shuffle, uniform credit, rollback이 gain을 제거해야 한다.

### SWM-4 — slow consolidation과 topology

- fast causal mediation이 재현된 뒤에만 `θ_slow`를 연다.
- 한 번에 하나의 mutation plane만 연다.
- `ADD/SPLIT/MERGE/SUPERSEDE`는 candidate→shadow→canary→atomic activation으로만 이동한다.

### SWM-5 — 분산·자기유사 HSWM

- 서로 다른 model/process의 HSWM이 typed port로 compose/separate된다.
- Agent A의 transcript를 숨기고 active `H/W` cut만 Agent B에 mount한다.
- rollback된 `H/W`에서 B의 이득이 사라져야 공유 신경망 전이를 주장한다.

## 9. 현재 저장소의 정확한 위치

현재 HSWM은 백지가 아니다.

- content-addressed/versioned evidence·world-state envelope, field snapshot, certified readout,
  open composition이 있다. 현재 구현의 immutability는 overwrite 방지 증거이지, 보호 payload와
  파생 상태의 `Π_t`-준수 erasure가 완료됐다는 증거가 아니다.
- scalar slow semantic weight과 volatile query potential의 타입·readout이 있다.
- token/action trajectory→eligibility→outcome→candidate→activation→causal test의 최소
  receipt 계약이 있다.
- 기존 P1 scalar slow-weight 실험은 active update를 만들지 못했고, 일반 전이·긴
  traversal·consolidation 가설도 살아남지 못한 부분이 있다.

하지만 [`src/hswm/substrate/hypergraph.py`](../../src/hswm/substrate/hypergraph.py)의
실제 신경 연산은 아직 node embedding, boolean membership, edge frequency/recency/base
salience, mean/sum/max pooling 수준이다. 다음은 **미구현**이다.

- role-bearing first-class incidence runtime;
- operator-valued `W`;
- recurrent token activation이 incidence를 통과하는 실행 engine;
- 다중 LLM function cell registry와 typed token packet;
- outcome이 실제 routing을 바꾸는 재현된 fast/slow learning;
- 계보를 보존하는 learned topology;
- world-scale distributed utility와 stability.

그러므로 현재 정직한 판정은 **안전한 memory/control substrate와 학습 영수증
부품은 존재하지만, 새 USER_PRIMARY가 강조한 거대 token-hypergraph neural core는
아직 target**이다.

## 10. 선행연구에서 가져올 것과 가져오지 말 것

세부 감사는 별도 보고서에 두되, 구현 결정은 다음처럼 압축한다.

| 가져올 메커니즘 | 후보 | HSWM 수정 |
|---|---|---|
| persistent cognitive metagraph + LLM bridge | Hyperon / AtomSpace / ECAN | token을 `LLMTokenEvent`와 `ComputeCredit`으로 분리하고 external-outcome macro-`W/H` 폐루프를 직접 입증 |
| role-aware n-ary score | RAM, Hyper-SAGNN | source/time/authority와 causal `θ`를 추가 |
| learned `V→E`, `E→V` | HNHN, UniGNN, AllSet | hyperedge·incidence를 durable state로 유지 |
| member-specific transport/diffusion | ED-HNN, Sheaf HNN | role-conditioned map + provenance-bearing canonical incidence |
| event-time memory | TGN, HyperTPP, Graphiti | 과거를 hidden state에만 압축하지 않고 원장 계보를 보존 |
| token/external memory | DNC, Hopfield, RETRO, Memorizing Transformer, Titans, ATLAS | flat/sequence memory를 n-ary `H/W` macroplasticity로 확장 |
| LLM function graph/topology optimization | GPTSwarm, DynamicGPTSwarm | pairwise workflow edge를 semantic relation operator와 outcome receipt로 확장 |
| LLM–hypergraph alignment | Hypergraph as Language, HyperGraphRAG/HyperRAG | retrieval/input serialization에서 지속 recurrent learning substrate로 확장 |
| prototype kernel | PyG HypergraphConv, DeepHypergraph | 계산 backend으로만 사용; canonical memory/runtime으로 간주하지 않음 |

반드시 거부할 단순 합성은 다음과 같다.

- hyperedge를 clique로 바꾸고 원래 n-ary identity를 잃는 구조;
- 모든 token을 concept node로 영구화하는 구조;
- query attention을 durable semantic weight와 동일시하는 구조;
- 모든 LLM call을 역전파할 수 있다고 가정하는 구조;
- offline node classification accuracy를 continual cognition의 증거로 쓰는 구조;
- topology를 매 layer 재생성하면서 이전 구조와 제안 근거를 지우는 구조.

## 11. novelty와 비주장

조사한 선행연구 범위 안에서 다음 전체를 하나의 공개 구현으로 확인하지
못했다.

```text
LLM token event
  → role-bearing persistent n-ary activation
  → LLM typed function cell
  → externally judged outcome credit
  → versioned operator W / topology commit
  → provenance-preserving recurrent next activation
```

이것은 **검토한 1차 소스에 기반한 gap inference**이지, 세계의 모든 논문·코드를
조사했다는 선취권·절대 novelty 주장이 아니다. HSWM의 핵심 연구 가치는
개별 부품의 발명이 아니라 다음 conjunction을 실제로 닫고 반증 가능하게 만드는
데 있다.

> **typed n-ary semantic operator + token-native recurrent activation + LLM nonlinear cells +
> outcome-bound versioned macroplasticity + provenance-preserving topology**

## 12. 최종 판별 문장

HSWM은 “하이퍼그래프에 정보를 저장하는 시스템”이 아니다.

> **HSWM은 LLM token으로 점화된 관계가 role-aware n-ary operator `W`를 통해
> 다른 상태와 function의 다음 가능성을 바꾸고, 세계의 결과가 그 operator와
> hypergraph `H`를 다시 바꾸는 영속적·거시적 학습 신경망이다.**

이 문장의 인과 사슬을 직접 실험으로 닫지 못하면, 그 구현은 HSWM의 좋은
메모리·KG·workflow 부품일 수는 있어도 이 정전이 가리키는 핵심 신경구조는
아니다.
