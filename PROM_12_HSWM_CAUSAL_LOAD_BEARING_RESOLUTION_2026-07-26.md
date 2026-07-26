# PROM-12 — HSWM causal load-bearing resolution

> **status**: `SECONDARY_AI_RESEARCH / PROPOSED_FALSIFIER`
> **cycle_id**: `prom-hswm-causal-loadbearing-resolution-20260726`
> **date**: 2026-07-26
> **lanes**: `BRIDGE + ENGINEERING`
> **canon boundary**: 이 문서는 USER_CANON을 해석·교체하지 않는다. 아래 메커니즘과
> 실험은 반증 가능한 protective-belt 제안이며, 사용자 ratification 전에는 정전이 아니다.
> **Naesengmoon**: 사용자 요청이 없었으므로 출격하지 않았다.

## 0. 답부터

HSWM의 의의는 단순한 RAG나 agent workflow가 아니다.

> **LLM으로 실행되는 의미 함수들이 하이퍼그래프 `H`와 Semantic Weight Map `W`를
> 공유하고, 결과 판정이 그 외부 회로를 학습·전이·재배선하여 전체가 하나의 더 큰 AI로
> 동작하게 만드는 것**이다.

현재 가장 큰 과학적 문제는 이 의의가 틀렸다는 것이 아니라, 현 구현에서 역할·credit·전이·
topology가 서로 분리된 실험으로 존재하여 **HSWM 고유 구조가 다음 행동의 원인이라는 단일
폐루프 증거가 없다는 것**이다.

해결책은 다음 세 줄이다.

1. `QF/BF/AF`를 prompt persona가 아니라 **독점 read/write set과 역할별 `W_i`를 가진
   상태 전이 연산자**로 만든다.
2. 학습정보는 새 자연어 lesson이 아니라 **versioned numeric `W/H`에만 저장**하고,
   credit·eligibility shuffle 및 `W/H` rollback으로 효과를 제거해 본다.
3. 정적 QA 한 번의 점수가 아니라 **반복 episode의 학습 slope, frozen Agent-B 전이,
   intervention 결과**를 conjunction으로 판정한다.

따라서 현 F1 sealed가 양성이더라도 HSWM 전체의 증명은 아니다. 반대로 음성이면 hard core가
아니라 현재 prompt-only 3-role belt를 중단하고 아래 `HSWM-CPL1`로 교체한다.

## 1. 권위와 현재 사실

### 1.1 USER_CANON

- KG `user-canon-hswm-is-the-larger-ai-containing-consensus-2026-07-23`:
  **HSWM 자체가 합의를 포함하는 더 큰 범위의 AI**다.
- [`CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`](CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md):
  HSWM = LLM-executed functions + `H` + `W` + recurrent plastic state.
- [`HSWM_CANONICAL_RESEARCH_DIRECTION_20260724.md`](HSWM_CANONICAL_RESEARCH_DIRECTION_20260724.md):
  LLM 호출, prompt 변경, static memory가 아니라 결과가 `W/H`를 바꾸고 그 변화가 다음
  dispatch를 바꿀 때만 HSWM 학습이다.

### 1.2 LakatoTree 상태

`LakatosTree_HSWM_20260719` live read 기준:

- 62 nodes, open questions 39, closed 4;
- registered novel predictions 19, confirmed 3 (`fertility=0.158`);
- server-anchored novel 6/27 (`0.222`);
- self-report green 15개는 receipt 부재로 progress 집계에서 제외;
- tree assurance는 `notebook`, canonical path는 아직 없다.

즉 아이디어와 하네스는 많지만, 현재 연구프로그램 자체도 실증이 설계를 따라잡지 못했다고
판정한다.

### 1.3 F1–F5 evidence ledger

| gate | 현재 영수증 | 정직한 판정 |
|---|---|---|
| F1 typed function network | r6 dev: typed `0.50`, vector `0.50`, flat `0.25`, role-shuffle `0.50`; equal token envelope는 통과 | prompt-only 역할 전문화 미확증 |
| F2 credit | credit `0.68`, random `0.53`, verbal `0.59`, placebo `0.16`, rho `0.8857`; base `0.05`, headroom fail | text-lesson 선택용 conditional signal; numeric `Delta W` 아님 |
| F3 A→B | full packet `0.02`, B-self `0.02`, deltaW-only `0`; `G=0`, `S=0` | donor-specific transfer 없음 |
| F3v2 dev-4 | no-memory `0`, abstracted `0.25`, contrast `0.25`, B-self `0`, placebo `0.25` | TRR denominator 0, placebo confound; sealed 금지 |
| F4 topology | learned `0.90`, shuffled `0.46`, clique `0.48`, random `0.52`; rho `0.957` | synthetic key-to-lesson topology 양성; real n-ary plasticity 아님 |
| F5 sleep | `A-C slope=-0.0605`, 95% `[-0.0982,-0.0238]`; 두 success condition false | age-downscale sleep 반증 |

주의: F2–F5 파일명에 `sealed`가 있어도 receipt 내부 `mode`는 모두 `development`다. replay
검증은 artifact 신뢰성을 올리지만 과학 판정을 자동 승격하지 않는다.

## 2. 근본 원인

### R1. role 이름과 port가 분리되어 있다

현재 shuffle arm은 QF/BF/AF의 **instruction만 교환**하고 각 call의 port schema와 실제
dataflow는 그대로 보존한다. 강한 LLM은 잘못 붙은 역할 문구보다 구조화된 입력과 출력 schema를
따르는 것이 자연스럽다. 그러므로 shuffle이 `0.50`을 유지한 것은 우연만이 아니라 현 ablation의
구조적 약점이다.

### R2. removal이 역할 고유성 대신 정보 삭제를 측정한다

현재 BF removal은 `ordered_bond_ids=[]`, `abstain=true`를 강제한다. AF에 증거가 하나도 가지
않으므로 점수 하락은 “BF 의미 함수가 필요하다”보다 “증거가 없으면 답할 수 없다”를 보인다.

### R3. baseline의 정보 plane이 같지 않다

typed arm은 전체 observable을 보지만 flat/vector arm은 각각 제한된 field만 본다. 동일 candidate
universe와 token 수는 지켰어도 raw information이 다르면 구조의 이득과 feature의 이득을 분리할
수 없다.

### R4. 정적 2Wiki QA는 HSWM의 고유 claim과 어긋난다

HSWM의 독자적 주장은 한 번의 retrieval이 아니라 **episode 결과가 외부 회로에 누적되고 다음
행동과 다른 agent를 바꾸는 것**이다. full context가 충분한 작은 iid QA에서는 strong flat/vector가
이기는 것이 hard core의 반증이 아닐 수 있다. 정적 F1은 runtime prerequisite로 남기되 주
falsifier는 recurrent, non-stationary, composition-disjoint 환경이어야 한다.

### R5. F2의 `Delta W`는 실제로 text lesson subset selection이다

F2의 Shapley/LOO는 valuable offline audit다. 그러나 candidate lesson이 정답 policy를 자연어로
담고 있고, credit 결과는 낮은 lesson을 삭제하여 prompt context를 바꾼다. 이것은 numeric
macro-synapse의 온라인 학습과 다르다.

### R6. F4의 양성은 F2/F1과 결합되지 않았다

F4 r2는 class-tag와 정답 lesson 사이의 bipartite adjacency를 학습했다. edge weight는 모두 1이고,
독립 outcome modulator·eligibility·확률 topology가 없다. 좋은 causal control 패턴은 흡수하되
HSWM n-ary topology 학습의 증명으로 확대하면 안 된다.

### R7. F3/F3v2에는 donor-specific information과 receiver actuation headroom이 동시에 없다

F3 r3에서는 donor와 B-self가 같은 orientation을 만들었다. F3v2는 donor `87.5%`와 receiver
`12.5%`의 능력 차는 만들었지만, live dev에서 `B-self=no-memory=0`이어서 memory가 receiver를
움직일 수 있는지조차 판정할 수 없다. placebo도 abstracted/contrast와 같은 `0.25`였다.

### R8. F5는 consolidation이 아니라 age-based lossy decay였다

오래된 lesson에 `x0.8`, threshold 아래 gist 변환을 적용했지만 미래 오류·interference·outcome을
예측하는 목적함수가 없었다. sleep이 append-only보다 더 빨리 붕괴한 것은 rate tuning 문제가
아니라 연산자 정의 문제다.

## 3. PROM-12 findings

| # | finding | HSWM 흡수 | confidence |
|---:|---|---|---:|
| 1 | prompt persona만으로 module specialization은 생기지 않는다 | 역할별 state bank `W_i`와 write ownership | high |
| 2 | modularity는 private observation과 제한된 통신에서 생긴다 | QF/BF/AF read-set 분리 + 작은 typed sufficient statistic | high |
| 3 | baseline에는 typed roles가 받은 정보의 합집합을 줘야 한다 | feature-plane parity; baseline 약화 금지 | high |
| 4 | role causal claim은 label shuffle이 아니라 interchange intervention이 필요하다 | matched item의 plan/proposal/state를 교환하고 예측된 counterfactual 확인 | high |
| 5 | 역할별 local reward가 없으면 global reward credit은 식별 불가능하다 | QF plan validity, BF evidence utility, AF outcome + shared global reward | medium-high |
| 6 | delayed outcome에는 pre-outcome eligibility와 독립 learning signal이 필요하다 | `Delta W_e = eta * delta * z_e` | high |
| 7 | discrete routing/topology는 확률과 propensity를 기록해야 한다 | stochastic gate logit + score-function update + sparsity/homeostasis | medium-high |
| 8 | 학습 state는 text가 아니라 rollback 가능한 numeric artifact여야 한다 | versioned `W_fast/W_slow/H`, prompt library freeze | high |
| 9 | A→B는 generic lift가 아니라 donor×capability interaction이어야 한다 | matched/mismatched 2-donor DSI | high |
| 10 | receiver가 self-memory로도 움직이지 않으면 transfer metric은 퇴화한다 | `B-self - B-no-memory >=15pp` adoption gate | high |
| 11 | consolidation은 age compression이 아니라 predictive replay다 | semantic rule + exception ledger + immutable episodic provenance | high |
| 12 | 한 평균점수로 여러 실패를 가리면 안 된다 | baseline/role/credit/W/transfer/topology의 conjunctive causal surplus | high |

## 4. 제안 메커니즘 — HSWM causal plasticity seam

### 4.1 역할을 상태 전이 연산자로 바꾼다

```text
QF_QUERY_COMPILER
  reads: query, relation schema
  writes: GoalState, executable plan

BF_BOND_PROPOSER
  reads: GoalState, opaque candidate features, W/H neighborhood
  writes: ActivationTrace, selected bond IDs
  cannot read: answer text, gold, full evidence body

AF_ANSWER_SYNTHESIZER
  reads: GoalState, selected evidence, ActivationTrace
  writes: proposed action/answer
  cannot read: full candidate universe, retrieval score table
```

각 역할은 foundation LLM을 공유해도 된다. 서로 다른 것은 모델 parameter가 아니라 역할별
external state `W_QF/W_BF/W_AF`, read/write capability, local outcome이다.

flat strong baseline에는 위 raw information의 합집합과 같은 총 useful-token·memory budget을
허용한다. typed가 정보 분할의 귀납편향으로 이겨야지 baseline 정보 삭제로 이기면 안 된다.

### 4.2 episode-scoped eligibility

모델 호출 전에 append-only trace를 고정한다.

```json
{
  "episode_id": "...",
  "base_epoch_sha256": "...",
  "function_ids": ["QF", "BF", "AF"],
  "edge_ids": ["..."],
  "route_probabilities": [0.0],
  "activation_strengths": [0.0],
  "pre_outcome_receipt_sha256": "..."
}
```

verdict가 온 뒤 trace를 생성·교체할 수 없어야 한다.

### 4.3 independent third factor와 numeric W

자연어 critic rationale를 학습값으로 직접 쓰지 않는다.

\[
\delta_t=r_t-\hat r_t,
\qquad
\theta^{fast}_e\leftarrow
\operatorname{clip}(\theta^{fast}_e+\eta_W\delta_t z_{e,t}-\lambda_W\theta^{fast}_e)
\]

역할별 local signal과 final global outcome을 함께 쓴다.

\[
\Delta W_i=\eta z_i[(r-\hat r)+\lambda_i(r_i-\hat r_i)]
\]

새 lesson text, answer, verdict rationale는 candidate W에 저장하지 않는다. frozen vocabulary의
edge/hyperedge ID와 numeric delta만 저장한다.

### 4.4 stochastic sparse topology

후보 incidence set을 사전 동결하고 edge/hyperedge logit `alpha_e`에서 gate를 샘플한다.

\[
p_e=\sigma(\alpha_e),\qquad
\Delta\alpha_e=\eta_H\delta z_e(g_e-p_e)-\lambda_0-\mu\,homeostasis
\]

외부 LLM 호출은 end-to-end differentiable하지 않으므로 hard-concrete backprop을 했다고
주장하지 않는다. logged probability를 쓰는 score-function estimator로 취급한다. 한 epoch에는
한 mutation class만 열고, shadow fresh/canary/retention을 통과해야 slow topology로 승격한다.

### 4.5 fast/slow와 readout firewall

- `W_fast/H_fast`: episode 결과로 변하는 shadow candidate, 완전 rollback 가능.
- `W_slow/H_slow`: disjoint episode 반복 지지 + fresh/canary/retention 통과 후만 CAS commit.
- Agent B가 받는 packet: `(shared_schema_hash, edge_id, numeric_delta, confidence, provenance_hash)`.
- 금지: A transcript, training answer, verdict 자연어, 새 lesson instruction, hidden cache.

prompt가 최종 readout에 영향을 주는 것은 허용한다. 증명할 것은 **새 학습정보가 prompt text가
아니라 versioned numeric state에 있고, 그것을 rollback하면 행동도 되돌아가는가**다.

## 5. 다음 결정실험 — `HSWM-CPL1`

상세 draft는
[`prom_search_hswm/evidence/PREREG_CPL1_hswm_causal_plasticity_20260726.draft.json`](prom_search_hswm/evidence/PREREG_CPL1_hswm_causal_plasticity_20260726.draft.json)에 둔다.

### 5.1 testbed adoption gate

F3v2 procedural foundry world를 재사용하되 sealed 전 다음을 모두 만족해야 한다.

- donor vanilla `>=70%`;
- receiver no-memory `[35%,65%]`;
- `receiver B-self - no-memory >=15pp`;
- placebo와 no-memory 차이의 절댓값 `<=5pp`;
- donor-exclusive stratum gap `>=20pp`.

현재 F3v2의 `12.5%` receiver와 dev의 `0% vs 0%`는 이 gate를 통과하지 못한다.

### 5.2 Phase A — role causalization

팔: learned typed / prompt-only typed / strongest flat / vector / role-state interchange.

통과:

- `learned typed - max(flat, vector, prompt-only) >=5pp`, paired 95% LCB `>0`;
- QF와 BF interchange의 average causal effect LCB `>0`;
- 개입 결과가 사전 고수준 causal model의 counterfactual 방향과 일치;
- 세 useful-token budget 중 최소 두 개에서 Pareto 열위가 아님.

### 5.3 Phase B — closed-loop plasticity

팔: FULL / FROZEN / strongest TEXT-VECTOR / CREDIT_SHUFFLE / ELIGIBILITY_SHUFFLE /
W_ROLLBACK / H_SHUFFLE.

통과:

- FULL이 FROZEN과 strongest text/vector를 `>=5pp`, paired LCB `>0`으로 이김;
- episode-누적 unseen slope LCB `>0`;
- credit 또는 eligibility shuffle이 FULL gain의 `>=70%` 제거;
- W rollback이 FULL gain의 `>=70%` 제거;
- H shuffle의 효과가 ROPE `+/-2pp` 밖이면 topology claim 생존, 아니면 W-only로 축소;
- old-regime retention 손실 `<=3pp`.

### 5.4 Phase C — 2-donor frozen-B transfer

두 donor `A1/A2`가 서로 다른 procedural invariant를 독점한다. matched, mismatched,
source-shuffled, B-self, placebo packet을 frozen B에 적용한다.

\[
G_{match}=score(matched)-\max(score(Bself),score(mismatch),score(shuffle),score(placebo))
\]

\[
DSI=[matched-mismatch]_{donor-exclusive}-[matched-mismatch]_{common}
\]

두 metric의 paired 95% LCB가 모두 `>0`이어야 donor-specific transfer다. 전체 정확도만 오르고
DSI가 0이면 generic memory injection으로 판정한다.

### 5.5 conjunctive verdict

```text
CS_role     = LCB(learned_typed - strongest_equal_information_baseline)
CS_credit   = removed_gain_fraction(credit/eligibility shuffle)
CS_weight   = removed_gain_fraction(W rollback)
CS_transfer = LCB(G_match) AND LCB(DSI)
CS_topology = LCB(FULL - H_shuffle)
```

- `NEURAL_PLASTIC_NETWORK_SUPPORTED_NARROW`: role, credit, weight 모두 통과.
- `SHARED_HSWM_TRANSFER_SUPPORTED_NARROW`: 위 + transfer 통과.
- `TOPOLOGY_PLASTICITY_SUPPORTED_NARROW`: 위 + topology 통과.
- 평균 하나가 다른 실패 seam을 상쇄하지 못한다.

## 6. consolidation은 그 뒤에 연다

F5v2는 CPL1에서 real numeric packet과 provenance가 나온 후에만 실행한다.

```text
Wake:
  episode -> outcome -> credit -> immutable episodic record

Sleep:
  contrast successful/failed trajectories
  -> candidate semantic hyperedge rule
  -> minimal exception ledger
  -> frozen replay + novel-composition shadow test
  -> promote to slow W/H, never delete raw provenance
```

연산자 목적함수:

\[
utility(rule)=heldout\ loss\ reduction+interference\ reduction
+donor\ specificity-active\ bytes-exception\ cost
\]

필수 대조는 append-only, no-op, sham/random replay, 기존 age-downscale, exact replay upper bound다.
offline 구간에는 새 관측을 금지하고 `post-sleep - pre-sleep`을 측정한다. episodic detail 손실
`>5pp` 또는 sleep 후 donor DSI 보존 `<80%`면 consolidation을 기각한다.

## 7. 실행 순서

1. 현재 F1 sealed는 끝까지 돌려 등록된 질문에 판정한다. 결과를 폐기하지 않는다.
2. sealed 결과와 별개로 F1 대조군의 information/ablation 약점을 `CPL1 Phase A`에서 수리한다.
3. F3v2 world 난이도를 receiver `[35,65]%` 및 `B-self gain >=15pp`가 되게 재조정한다.
4. dev에서 testbed adoption gate와 prompt-overlap firewall을 통과한다.
5. prereg를 사용자 ratify하고 machine-lock한 뒤 Phase A→B→C 순으로 sealed한다.
6. role/credit/W가 모두 서기 전에는 topology 기능 추가나 sleep 재시도를 하지 않는다.

## 8. 1차 소스 ledger

검색·회수일: 2026-07-26. 외부 소스는 USER_CANON이 아니라 설계 근거다.

| source | 흡수 claim | caveat | confidence |
|---|---|---|---:|
| [Recurrent Independent Mechanisms](https://arxiv.org/abs/1909.10893) | 독립 dynamics와 sparse communication이 module specialization과 조합 일반화를 유도 | differentiable recurrent cells, LLM 함수 아님 | high |
| [Neural Module Networks, CVPR 2016](https://openaccess.thecvf.com/content_cvpr_2016/papers/Andreas_Neural_Module_Networks_CVPR_2016_paper.pdf) | 이름이 아니라 실제 함수를 동적 조합하고 jointly train | VQA 범위 | high |
| [Modular Meta-Learning](https://proceedings.mlr.press/v87/alet18a.html) | 학습된 module 재조합이 unseen composition을 지원 | robotics 중심 | high |
| [Causal Abstractions of Neural Networks](https://arxiv.org/abs/2106.02997) | interchange intervention으로 내부 변수의 인과 역할 검증 | 고수준 causal model을 먼저 정의해야 함 | high |
| [e-prop, Nature Communications 2020](https://www.nature.com/articles/s41467-020-17236-y) | local eligibility와 delayed learning signal의 곱으로 temporal credit 배분 | spiking RNN; HSWM 적용은 macro-level analogy | high |
| [REINFORCE](https://link.springer.com/article/10.1007/BF00992696) | stochastic discrete route의 logged probability로 expected reward gradient 추정 | 고분산 estimator | high |
| [Learning Sparse Neural Networks through L0 Regularization](https://openreview.net/forum?id=H1Y8hhg0b) | stochastic gate와 sparsity penalty | HSWM은 end-to-end gradient가 없어 parameterization만 흡수 | high |
| [Learning Discrete Structures for Graph Neural Networks](https://proceedings.mlr.press/v97/franceschi19a.html) | edge probability와 validation을 포함한 graph structure learning | supervised GCN | high |
| [Using Fast Weights to Attend to the Recent Past](https://papers.nips.cc/paper/2016/hash/9f44e956e3a2b7b5598c625fcc802c36-Abstract.html) | activation보다 느리고 long-term weight보다 빠른 상태층 | persistent multi-agent topology는 다루지 않음 | high |
| [Data Shapley](https://proceedings.mlr.press/v97/ghorbani19c.html) | Shapley는 data/lesson 가치의 offline audit에 적합 | online temporal credit 자체는 아님 | high |
| [MemCollab](https://arxiv.org/abs/2603.23234) | 여러 agent trajectory의 대조로 generic invariant와 model-specific bias를 분리 | 2026 preprint, inference-time memory | medium-high |
| [Measuring Information Transfer](https://arxiv.org/abs/nlin/0001042) | 공통 입력·history를 조건화해야 방향성 정보전달을 구별 | packet DSI 적용은 본 PROM의 synthesis | medium-high |
| [Experience Replay for Continual Learning](https://proceedings.neurips.cc/paper_files/paper/2019/hash/fa7cdfad1a5aaf8370ebeda47a1ff1c3-Abstract.html) | replay로 stability와 plasticity를 분리 평가 | parametric RL | high |
| [Computational principles of synaptic memory consolidation](https://www.nature.com/articles/nn.4401) | fast 상태에서 여러 slow timescale로 이전해 overwrite를 완화 | 생물학적 synapse model | high |
| [SIESTA](https://arxiv.org/abs/2303.10725) | bounded sleep replay와 pre/post-sleep 성능을 직접 비교 | image continual learning | high |
| [Deep Generative Replay](https://arxiv.org/abs/1705.08690) | meaningful replay와 random/noise replay를 구별해야 함 | generator 품질 의존 | high |

## 9. 최종 판단

HSWM의 의의는 그대로 살아 있다. 그러나 현재 구현은 그 의의를 구성하는 조각을 각각 보여
줬을 뿐 하나의 인지 신경망으로 묶지 못했다.

가장 중요한 problemshift는 다음이다.

> **“typed가 vector보다 한 번 더 맞았는가?”에서 “학습정보가 numeric `W/H`에 외재화되고,
> 그 상태가 역할·다른 agent·다음 episode를 인과적으로 바꾸며, rollback하면 효과가 사라지는가?”로
> 주 판정선을 옮긴다.**

이 판정선을 통과하면 HSWM은 구조화 memory가 아니라 shared external neural substrate라는 좁지만
강한 과학적 주장을 얻는다. 실패하면 정직하게 replayable semantic memory/agent harness로 범위를
축소하고, 같은 prompt-only 3-role belt를 다시 튜닝하지 않는다.
