# PROM — HSWM 연결·분리·전문화 학습: weight만이 아니라 plasticity 전체

> **cycle**: `prom-hswm-plasticity-weight-topology-learning-2026-07-23`
> **lane**: ENGINEERING / HSWM
> **status**: `SECONDARY_AI_RESEARCH_AND_DESIGN`
> **USER_PRIMARY question**: “연결분리 전문화 학습 여기서 학습한다는게 hswm 의 웨이트 조절을 한다는거지 ㅇㅇ?”
> **claim boundary**: 기존 정전·코드·실측과 1차 문헌을 종합한 설계안이다. 새 성능 실험이나 LakatoTree 판정을 만들지 않았다.

## 0. 바로 답

**맞다. 하지만 그것만은 아니다.**

- 이미 존재하는 semantic bond의 강약을 바꾸는 것은 **weight learning**이다.
- 어떤 port/field가 실제로 결합되어 있는지를 바꾸는 것은 **topology learning**이다.
- 현재 query에서 어느 HSWM 조합을 쓸지 고르는 것은 **routing-policy learning**이다.
- 한 번 선택된 route나 activation은 순간 상태다. 그 선택만으로는 학습이 아니다.

따라서 HSWM의 연결·분리·전문화 학습은 다음 세 상태를 함께 다루되, 서로 같은 것으로
취급하지 않아야 한다.

\[
\boxed{
\text{HSWM learning}
=
\text{weight learning}
+
\text{routing learning}
+
\text{topology learning}
}
\]

한 문장으로 줄이면:

> **weight는 무엇이 중요한지를 배우고, topology는 무엇이 존재하며 묶이는지를 배우고,
> routing은 지금 무엇을 실행할지를 배운다.**

## 1. 권위 경계

### CANONICAL_USER

기존 문서에 보존된 사용자 방향은 다음 네 가지다.

1. HSWM은 여러 개가 존재하고 서로 연결·분리될 수 있다.
2. 연결체도 원자 HSWM과 같은 타입이며, 고정된 “1층/2층” 번호가 없다.
3. 여러 HSWM은 MoE처럼 전문화될 수 있다.
4. 이 가소성을 수행하며 semantic neural network를 완성하는 주체가 agent다.

원문과 권위 경계는
[`SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md`](SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md)에
보존돼 있다.

### SECONDARY_AI

이 문서의 수식, 세 상태면, 보상식, 승격 게이트, 실험 순서는 위 방향을 실행 가능한
계약으로 옮긴 연구·설계 제안이다. 사용자의 새 정전 판정이나 과학적 `progressive` 판정을
대신하지 않는다.

## 2. 지금 HSWM에서 실제로 “학습되는 것”

| 상태 | 현재 구현 | 정확한 판정 |
|---|---|---|
| embedding \(X\) | frozen encoder inference | 학습 안 함 |
| fast scorer \(\theta=M\), additive residual \(j\) | offline fitting과 validation 선택 | **weight/scorer 학습은 있음** |
| slow salience \(b(e)\), open-kernel \(\ell_e\) | 외부 입력·supersession dose 반영 | 값은 바뀌지만 선택 정책은 아직 없음 |
| mounts/ports/connectors \(H\) | caller가 결정론적으로 compose/separate/specialize | **연산은 있음, 학습은 없음** |
| route/gate \(\phi\) | fixed lexical/RRF 또는 직접 선택 | **learned router 없음** |
| candidate 승격 | immutable candidate, fresh eval, canary, CAS | 고정 governance이며 learned policy는 아님 |

현재 `W(e\mid c)`는 [`weight_field.py`](weight_field.py)의
`fast contextual alpha + slow base salience`이고, [`learned_v3_additive.py`](learned_v3_additive.py)는
frozen cosine 위의 boost-only residual을 offline으로 학습한다. 이 static additive-j는 공개
효능 장부에서 cosine 대비 support recall@3 `+0.0364`, nDCG@10 `+0.0259`, downstream F1
`+0.0729`를 냈다([`EFFICACY.md`](EFFICACY.md)). 이것은 **weight-plane의 실측**이지 learned
CONNECT/SEPARATE/SPECIALIZE의 실측이 아니다.

또 [`llm_judgment_loop.py`](llm_judgment_loop.py)는 주석에서 “gradient-free”라고 쓰지만 실제
구현은 judge label로 \(M\)에 gradient step을 수행하며, default judge도 real LLM이 아니라
synthetic gold oracle다. 그러므로 이것은 loop 가능성의 prototype이지 운영 학습 증거가 아니다.

## 3. 기존 실험이 강제하는 설계 제약

### B2: 연결은 실제로 이기지만 간섭도 실제다

[`B2_CROSSFIELD_MERGE_RESULTS_2026-07-22.md`](prom_search_hswm/docs/B2_CROSSFIELD_MERGE_RESULTS_2026-07-22.md):

- cross-field `merged − best_single = +0.2137`, bootstrap95 `[+0.183,+0.244]`;
- seam ablation `+0.0342`, bootstrap95 `[+0.017,+0.052]`;
- in-field no-harm는 `−0.0648`, bootstrap95 `[−0.092,−0.041]`로 실패;
- 값싼 affinity 신호 AUC `0.538`, top1-gap AUC `0.571`로 kill 기준 `0.75` 미달.

즉 “많이 연결”이 아니라 **질의마다 필요한 연합만 여는 learned gate**가 먼저다.

### P5: 고정 전문화는 아직 답이 아니다

[`PROM_P5_MULTIVIEW_HARDHOP_2026-07-22.md`](PROM_P5_MULTIVIEW_HARDHOP_2026-07-22.md)의
fixed lexical routing + late RRF는 hard-4 `Δ=0`, full-chain `−0.0125`였다. 분리된 view가
있다는 사실만으로 전문화가 생기지 않는다. 학습된 gate와 독립된 specialist state가 필요하다.

### P6: 흡수는 “저장”이 아니라 “전이”로 판정해야 한다

[`PROM_P6_CONTINUAL_ABSORPTION_FSM_2026-07-22.md`](PROM_P6_CONTINUAL_ABSORPTION_FSM_2026-07-22.md)의
semantic-KV 후보는 fresh unseen에서 `−0.0604`, `−0.0188`, `−0.0583`으로 세 번 모두
손해였고 전부 거부됐다. sealed active delta는 `0`이었다. 여기서 살아남은 것은 성능 메커니즘이
아니라 **immutable candidate + replay + retention + canary + CAS rollback 규율**이다.

## 4. PROM prior-art matrix

| 개념 | 무엇을 학습하나 | HSWM에 가져올 것 | 그대로 가져오면 안 되는 것 |
|---|---|---|---|
| [HGNN](https://ojs.aaai.org/index.php/AAAI/article/view/4235) | 고정 incidence 위 weight/feature transform | \(W\) 변화와 incidence 변화를 분리 | weight 변화만 topology 학습이라 부르기 |
| [Hypergraph Structure Learning](https://www.ijcai.org/proceedings/2022/0267) | hyperedge/node membership mask | CONNECT/SEPARATE 후보 생성 | stochastic mask를 정본에 즉시 반영 |
| [Learning Discrete Structures](https://proceedings.mlr.press/v97/franceschi19a.html) | train weight와 validation topology를 bilevel로 분리 | topology는 독립 holdout으로 판정 | 같은 점수가 생성과 승인 모두 소유 |
| [RigL](https://proceedings.mlr.press/v119/evci20a.html) | 고정 예산에서 prune/grow mask | bounded swap budget | magnitude를 semantic truth로 해석 |
| [DARTS](https://openreview.net/forum?id=S1eYHoC5FX) | soft architecture score 후 discrete compile | soft search와 active snapshot 분리 | relaxed score의 자동 승격 |
| [NRI](https://proceedings.mlr.press/v80/kipf18a.html) | context별 latent relation graph | per-query graph를 routing overlay로 해석 | 순간 relation을 정본 topology로 저장 |
| [Sparsely-Gated MoE](https://research.google/pubs/outrageously-large-neural-networks-the-sparsely-gated-mixture-of-experts-layer/) | gate와 expert parameter를 함께 학습 | gate와 specialist identity/state 분리 | gate 선호만을 전문화라 부르기 |
| [Switch Transformer](https://www.jmlr.org/papers/v23/21-0998.html) | top-1 routing과 load balance | capacity·fallback를 명시 | overflow를 조용히 drop |
| [Routing Networks](https://openreview.net/forum?id=ry8dvM-R-) | 같은 타입 module의 재귀 route | 고정 층 없는 자기유사 조합 | 무제한 depth/fanout/cycle |
| [three-factor plasticity / e-prop](https://www.nature.com/articles/s41467-020-17236-y) | local eligibility를 나중 outcome이 commit | coactivation과 외부 결과를 분리 | 함께 쓰였다는 이유만으로 강화 |
| [Conservative Contextual Bandits](https://papers.nips.cc/paper_files/paper/2017/hash/bdc4626aa1d1df8e14d80d345b2a442d-Abstract.html) · [SPIBB](https://proceedings.mlr.press/v97/laroche19a.html) | baseline보다 안전한 action policy | 불확실하면 frozen/NOOP fallback | 평균 reward 하나로 no-harm 대체 |
| [EWC](https://doi.org/10.1073/PNAS.1611835114) · [GEM](https://proceedings.neurips.cc/paper/2017/hash/f87522788a2be2d171666752f97ddebb-Abstract.html) | 이전 능력 보존 제약 | retention importance/replay | 보존 penalty만으로 실제 회귀 검증 대체 |

문헌의 공통 구조는 단순하다. **연속 점수로 탐색하더라도, 배포되는 구조는 별도의 이산
아티팩트로 compile하고 validation·retention으로 승인한다.**

## 5. 제안: 한 타입, 세 learning plane, 네 시간척도

기존 open-HSWM 정규형을 유지한다.

\[
H_t=\operatorname{NF}(M_t,P_t,C_t,X_t,\ell_t,\Pi_t)
\]

학습 가능한 전체 상태를 다음처럼 둔다.

\[
\boxed{\Omega_t=(H_t,\theta_t,\phi_t,R_t)}
\]

- \(H_t\): mounts, ports, connectors, semantic coordinates, slow salience, provenance;
- \(\theta_t\): query-edge scorer와 weight update parameter;
- \(\phi_t\): query-time coalition/router policy;
- \(R_t\): candidate, verdict, replay, activation, rollback receipt.

추론은 다음 한 식이다.

\[
a_t(q)=\operatorname{Readout}(H_t,q;\theta_t,\pi_{\phi_t})
\]

여기서 \(a_t\)와 선택된 route는 **volatile**하다. 학습이라고 부르려면 이후에도 남는
\(\ell,\theta,\phi,C\) 중 하나가 검증된 새 snapshot으로 바뀌어야 한다.

| 시간척도 | 상태 | 수명 | 정본 여부 |
|---|---|---|---|
| 0. 순간 | activation, selected route | 한 query/run | 아니오 |
| 1. 빠름 | eligibility trace, shadow utility | 한 episode/평가 창 | 아니오 |
| 2. 중간 | \(\ell,\theta,\phi\) candidate | 여러 task | 승격 전에는 아니오 |
| 3. 느림 | connectors, split/merge, specialist lineage | topology epoch | 승격 후 예 |
| 불변 | source/evidence/provenance, frozen baseline | append-only | 예 |

고정 층은 필요 없다. 모든 specialist와 aggregate는 동일한 `OpenHSWM` 타입이고, typed port로
다시 연결된다. 단 runtime은 `max_depth`, `max_fanout`, `visited_set`, stable tie-break를 가진다.

## 6. semantic weight가 hypergraph라는 직관을 살리는 법

개별 weight 값을 다시 hypergraph로 만들면 equality와 학습이 무한 재귀한다. 대신 **semantic
weight의 정의역을 semantic bond 전체로 넓힌다.**

\[
\mathcal{B}=E_{atomic}\;\uplus\;C_{connector},
\qquad
\ell:\mathcal{B}\rightarrow[\ell_{min},0]
\]

즉 atomic fact edge뿐 아니라 HSWM 사이 connector도 1급 semantic bond이며 slow salience를
가질 수 있다. 하지만 다음 값은 합치지 않는다.

- \(\Pi_b\): 무엇이 사실/근거인지 — provenance;
- \(\ell_b\): 이미 존재하는 bond의 느린 semantic salience;
- \(g_\phi(b\mid q)\): 현재 query에서의 routing utility;
- \(U(\Delta\mid x)\): 아직 정본이 아닌 구조 후보의 예상 효용.

**근거, 진실성, query relevance, 사용 빈도, 신선도, 전이 이득을 scalar 하나에 섞지 않는 것**이
중요하다. weight가 provenance를 덮어쓸 수 없고, 높은 router score가 새 edge의 존재를 증명할
수도 없다.

## 7. credit assignment: 같이 켜짐은 eligibility, 결과가 learning signal

Agent가 어떤 bond들을 함께 사용했다는 사실만으로 강화하면 인기 편향과 오류 증폭이 생긴다.
three-factor 형태를 쓴다.

### 7.1 빠른 trace

\[
z_t(b)=\rho z_{t-1}(b)+\operatorname{use}_t(b)
\]

`use`는 co-activation, selected route, supporting evidence contribution을 기록한다. \(z\)는
candidate credit일 뿐 정본 weight가 아니다.

### 7.2 외부 결과

\[
\delta_t=r_t-\widehat r_t
\]

\(r_t\)는 Agent 자기평가가 아니라 environment result, independent evaluator, 사용자 verdict처럼
행동 이후 얻은 결과여야 한다.

### 7.3 weight candidate

\[
\ell'_t(b)=
\operatorname{clip}
\left(
\ell_t(b)+\eta_\ell\delta_t z_t(b)-\lambda_\ell d_t(b),
\ell_{min},0
\right)
\]

현재 open kernel의 \(\ell\le0\) 계약과 맞는다. 긍정 결과는 0 쪽으로, 부정 결과는 더 작은
값으로 이동한다. 단 이것도 즉시 active state를 바꾸지 않고 candidate snapshot을 만든다.

### 7.4 router candidate

초기에는 full RL보다 conservative contextual bandit가 알맞다.

\[
\phi' = \phi + \eta_\phi\delta_t\nabla_\phi
\log\pi_\phi(u_t\mid x_t),
\qquad
u_t\in\{A,B,MERGED,ABSTAIN\}
\]

support가 부족하거나 confidence set이 baseline no-harm을 증명하지 못하면 `ABSTAIN` 또는 frozen
route로 돌아간다.

### 7.5 topology candidate

\[
u_t\in\{
NOOP,CONNECT,SEPARATE,SPECIALIZE,EXPOSE,HIDE,SUPERSEDE
\}
\]

모델·gradient·LLM은 \(u_t\)를 **제안**할 수 있다. deterministic compiler만 typed incidence,
arity, visibility, stable ID, cycle/budget, provenance를 검사해 immutable candidate를 만든다.

## 8. CONNECT / SEPARATE / SPECIALIZE의 정확한 두 의미

| verb | soft form | structural form |
|---|---|---|
| `CONNECT` | 기존 connector/bond의 \(\ell\) 또는 route probability 증가 | 새 typed connector 또는 incidence membership 추가 |
| `SEPARATE` | route 억제, \(\ell\) 감소 | connector cut 또는 child split 생성, old aggregate supersede |
| `SPECIALIZE` | 기존 module을 더 자주 선택 | stable child identity, 독립 state/parameter, typed ports, `SPECIALIZES` lineage 생성 |

따라서 “웨이트가 거의 0이니 분리됐다”는 운영 최적화일 수는 있어도 구조적 분리가 아니다.
또 “gate가 자주 골랐으니 전문화됐다”도 부족하다. 전문화에는 독립된 상태와 lineage가 남아야
한다.

## 9. agent plasticity loop

stochastic learner와 정본 HSWM 사이에 deterministic control plane을 둔다.

```text
OBSERVE
  -> CREDIT          coactivation을 eligibility로만 기록
  -> PROPOSE         Δweight | Δrouter | Δtopology 중 하나를 제안
  -> COMPILE         typed/provenance/budget 검사
  -> FREEZE          candidate hash + base epoch 고정
  -> EVALUATE        fresh/query-disjoint/equal-budget/replay
  -> CANARY
  -> APPROVE
  -> CAS ACTIVATE
  -> MONITOR
       -> KEEP | ROLLBACK | SUPERSEDE

어느 gate라도 불명확/실패/동률/낡은 base면 NO_CHANGE 또는 REJECT
```

기존 P6의 [`hswm_absorption_fsm.v1.json`](prom_search_hswm/fsm/hswm_absorption_fsm.v1.json)이
`FREEZE → EVALUATE → CANARY → ACTIVATE → ROLLBACK/SUPERSEDE`를 이미 소유한다. 이를 복제하지
않고, 새 [`hswm_plasticity_loop.v1.json`](prom_search_hswm/fsm/hswm_plasticity_loop.v1.json)이
앞단 `OBSERVE → CREDIT → PROPOSE → COMPILE`과 실행 예산·checkpoint·effect ledger를 묶는다.

### loop invariants

1. learner는 proposal producer이며 자기 proposal의 성공 판관이 아니다.
2. 한 초기 candidate는 mutation plane 하나만 바꾼다. 원인 식별 전 joint update 금지.
3. candidate는 `(base_epoch, candidate_hash, mutation_class, evidence_hashes)`로 고정한다.
4. 같은 intent는 idempotency key로 한 번만 적용한다. same ID/different payload는 reject한다.
5. activation은 CAS이며 unknown outcome을 맹목 재시도하지 않고 receipt로 reconcile한다.
6. topology 변화는 embedding/index/materialization cache invalidation 범위를 명시한다.
7. no-progress 3회, retry exhaustion, wall/cost/step budget은 typed terminal outcome을 낸다.
8. rollback은 역연산이 아니라 이전 immutable epoch로 append-only supersession한다.

## 10. reward는 proposal ranking이고, promotion은 vector gate다

탐색용 utility는 둘 수 있다.

\[
J(\Delta)=
\Delta task
+\kappa\Delta transfer_{A\to B}
-\beta I_{interference}
-\gamma C_{compute}
-\chi E_{stale}
\]

하지만 이 scalar 하나로 승격하지 않는다. 승격은 다음 conjunction이다.

\[
\boxed{
LCB(\Delta fresh)>0
\;\land\;
retention\ge-\epsilon_r
\;\land\;
canary\ge-\epsilon_c
\;\land\;
replay
\;\land\;
equal\_budget
\;\land\;
typed+provenance
}
\]

평균 이득이 일부 field/role의 큰 손해를 숨기지 않도록 affected-neighborhood와 role별 no-harm도
별도로 본다.

## 11. 가장 작은 다음 실험: B2.1 gate-only learning

아직 CONNECT/SEPARATE를 직접 학습시키지 않는다. 먼저 B2가 이미 보여 준 연결 이득과 간섭을
**route 하나로 동시에 통제 가능한지** 시험한다.

### 동결

- embeddings \(X\);
- edge/connector weights \(\ell,\theta\);
- topology \(H\);
- B2 score matrices와 candidate budget;
- open-kernel manifest와 readout.

### 유일한 학습 변수

\[
g_\phi(q,S_A,S_B,S_M)
\rightarrow
\{A,B,MERGED,ABSTAIN\}
\]

feature는 query와 각 field/merged의 top-k score distribution(max, mean, entropy, margin,
cross-field affinity)만 쓴다. test gold, hop label, query ID는 금지한다. uncertainty가 큰 구간은
Mondrian conformal abstention으로 frozen baseline에 보낸다.

### controls

1. always-merged;
2. best-single oracle은 headroom 진단만;
3. P5 fixed lexical gate;
4. capacity-matched shuffled-label gate;
5. router 없는 frozen HSWM.

### prereg gates

- query-disjoint train/validation/sealed test, 3 seeds;
- equal candidate/scorer budget;
- cross-field gain이 기존 noise band `+0.02`를 넘고 CI lower `>0`;
- in-field delta versus best-single `≥−0.02`;
- overall gain versus always-merged의 paired CI lower `>0`;
- shuffled-label control은 통과하지 못함;
- private-ID/direct-answer-edge deletion;
- 일반 hard-hop 주장 전 second benchmark.

이 실험이 죽으면 관측 가능한 query/score feature만으로는 B2 간섭을 통제할 수 없다는 뜻이다.
그 상태에서 full topology learning으로 가면 원인 불명 joint search가 된다.

## 12. 그다음 실험: 한 번에 topology op 하나

B2.1이 통과한 뒤에만 `CONNECT_struct` 한 종류를 연다.

1. Agent A가 task를 수행하되 activation과 eligibility만 shadow ledger에 기록한다.
2. 독립 결과가 positive credit을 준 경우 최대 한 개 typed connector 후보를 만든다.
3. compiler와 기존 absorption FSM을 통과한 candidate만 평가한다.
4. Agent B의 model, prompt, embeddings, readout, budget은 완전히 frozen한다.
5. B는 A transcript를 볼 수 없다.

동일 compute arms:

1. frozen HSWM, A 정보 없음;
2. A transcript only;
3. flat/vector memory write;
4. W-only candidate;
5. router-only candidate;
6. topology-only candidate;
7. 세 plane joint candidate — 앞의 원인 분리가 끝난 뒤에만.

headline metric은 **Agent-A write → frozen Agent-B fresh unseen gain**이다. exact-ID cache나 B의
추가 parameter update는 zero-shot shared-memory transfer로 세지 않는다.

## 13. 반증기와 kill conditions

1. B2.1이 cross-field 이득과 in-field no-harm를 동시에 만족하지 못한다.
2. topology candidate가 fresh validation에서 positive lower CI를 한 번도 만들지 못한다.
3. 이득이 direct-answer-edge deletion 또는 private-ID 통제에서 사라진다.
4. Agent B가 A transcript를 못 보면 이득이 사라진다.
5. flat/vector memory가 equal compute에서 HSWM candidate 이상이다.
6. retention/canary 손해가 prereg band를 넘는다.
7. route collapse, specialist starvation, unbounded recursion, silent overflow가 발생한다.
8. LLM 자기평가만 제거하면 credit이 사라진다.
9. topology hash 또는 provenance가 없는 proposal이 active가 된다.

가장 강한 다음 반증 질문은 이것이다.

> **B를 완전히 frozen하고 A의 transcript를 숨긴 상태에서, 외부 결과로 보상된 단 하나의 typed
> topology operation이 frozen/flat-memory baseline보다 B의 sealed transfer를 높이면서 retention을
> 보존하는가?**

## 14. 결정

### 채택

- `learning = (W, router, topology)`의 세 plane;
- query activation과 durable learning의 분리;
- coactivation은 eligibility, 외부 결과가 third factor;
- soft search 뒤 immutable discrete compile;
- deterministic fail-closed inference와 CAS activation;
- B2.1 router-only를 첫 rung으로 실행.

### 기각

- `learning = W 조절뿐`;
- low weight를 실제 separation으로 간주;
- gate preference만으로 specialization 선언;
- LLM judgment를 truth/승격 authority로 사용;
- 여러 plane을 처음부터 joint optimize;
- exact-query memory gain을 unseen learning으로 보고.

## 15. 실행 상태와 남은 구현

이번 PROM이 고정한 것은 학습 의미론과 control contract다. 아직 구현되지 않은 것은 다음이다.

1. legacy `b\in(0,1]`와 open-kernel `\ell\le0`의 명시적 adapter;
2. connector까지 포함하는 bond-weight storage/readout;
3. B2.1 learned/conformal router;
4. typed `StructuralProposal` compiler;
5. proposal ledger와 loop reducer의 production binding;
6. multi-agent transfer harness와 server-owned certificate.

따라서 현재의 정직한 표현은 **“학습 가능한 HSWM의 설계와 검증 경계가 생겼다”**이지
“HSWM이 이미 연결·분리·전문화를 학습한다”가 아니다.

## 16. 출처 장부

### local canon / code / receipts

- [`SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md`](SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md)
- [`SPEC_SHARED_HYPERGRAPH_NN_SEMANTIC_WEIGHT_2026-07-22.md`](SPEC_SHARED_HYPERGRAPH_NN_SEMANTIC_WEIGHT_2026-07-22.md)
- [`DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md`](DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md)
- [`weight_field.py`](weight_field.py), [`learned_v3_additive.py`](learned_v3_additive.py),
  [`llm_judgment_loop.py`](llm_judgment_loop.py)
- [`EFFICACY.md`](EFFICACY.md)
- [`PROM_P5_MULTIVIEW_HARDHOP_2026-07-22.md`](PROM_P5_MULTIVIEW_HARDHOP_2026-07-22.md)
- [`PROM_P6_CONTINUAL_ABSORPTION_FSM_2026-07-22.md`](PROM_P6_CONTINUAL_ABSORPTION_FSM_2026-07-22.md)
- [`B2_CROSSFIELD_MERGE_RESULTS_2026-07-22.md`](prom_search_hswm/docs/B2_CROSSFIELD_MERGE_RESULTS_2026-07-22.md)
- [`hswm_absorption_fsm.v1.json`](prom_search_hswm/fsm/hswm_absorption_fsm.v1.json)

### external primary sources

- Feng et al., [Hypergraph Neural Networks](https://ojs.aaai.org/index.php/AAAI/article/view/4235), AAAI 2019.
- Cai et al., [Hypergraph Structure Learning for Hypergraph Neural Networks](https://www.ijcai.org/proceedings/2022/0267), IJCAI 2022.
- Franceschi et al., [Learning Discrete Structures for Graph Neural Networks](https://proceedings.mlr.press/v97/franceschi19a.html), ICML 2019.
- Kipf et al., [Neural Relational Inference](https://proceedings.mlr.press/v80/kipf18a.html), ICML 2018.
- Evci et al., [Rigging the Lottery](https://proceedings.mlr.press/v119/evci20a.html), ICML 2020.
- Liu et al., [DARTS](https://openreview.net/forum?id=S1eYHoC5FX), ICLR 2019.
- Shazeer et al., [Sparsely-Gated Mixture-of-Experts](https://research.google/pubs/outrageously-large-neural-networks-the-sparsely-gated-mixture-of-experts-layer/), ICLR 2017.
- Fedus et al., [Switch Transformers](https://www.jmlr.org/papers/v23/21-0998.html), JMLR 2022.
- Rosenbaum et al., [Routing Networks](https://openreview.net/forum?id=ry8dvM-R-), ICLR 2018.
- Bellec et al., [e-prop](https://www.nature.com/articles/s41467-020-17236-y), Nature Communications 2020.
- Kazerouni et al., [Conservative Contextual Linear Bandits](https://papers.nips.cc/paper_files/paper/2017/hash/bdc4626aa1d1df8e14d80d345b2a442d-Abstract.html), NeurIPS 2017.
- Laroche et al., [SPIBB](https://proceedings.mlr.press/v97/laroche19a.html), ICML 2019.
- Kirkpatrick et al., [EWC](https://doi.org/10.1073/PNAS.1611835114), PNAS 2017.
- Lopez-Paz and Ranzato, [GEM](https://proceedings.neurips.cc/paper/2017/hash/f87522788a2be2d171666752f97ddebb-Abstract.html), NeurIPS 2017.

검색·회수 기준일: `2026-07-23`.

## 17. 설계 검증 영수증

```text
plasticity loop contract: OK, 0 warnings
existing absorption FSM static validation: OK, 2 warnings
existing absorption FSM abstract traces: OK, 14 cases
plasticity-relevant regression suite: 100 passed in 0.43s
local Markdown links: OK
```

FSM의 두 warning은 `evaluating/EVALUATION_RECORDED`와
`promotion_pending/ACTIVATION_FAILED` guarded branch에 명시적 default transition이 없다는
것이다. 현재 `invalid_event_policy=reject-and-audit`와 guard-false traces 때문에 silent mutation은
없지만, production reducer binding 전에는 guard partition의 완전성을 증명하거나 explicit default를
추가해야 한다. 새 loop contract의 runtime reducer와 model-to-implementation conformance는 아직
`PENDING`이다.
