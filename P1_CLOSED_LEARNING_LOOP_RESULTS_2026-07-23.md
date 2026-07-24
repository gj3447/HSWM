# P1 closed learning loop — implementation GREEN, scientific RED, LakatoTree unjudged

> **한 줄 판정:** `outcome → eligibility → M → ΔW candidate → fresh/canary → CAS` 실행 경로는 구현됐지만, 실측 후보 12개가 fresh recall@10을 단 한 건도 움직이지 못해 전부 기각됐다. A1과 no-commit A2의 paired gain은 정확히 `0.0`; prereg K1에 따라 이 substrate의 three-factor slow-weight 경로는 중단하고 typed verdict-to-lesson baseline으로 돌아간다. 단, 역사 evidence가 measurement 자체에서 `FAIL`을 썼으므로 LakatoTree kernel 상태는 공식 `rejected`가 아니라 절차상 `unjudged`다.

## 1. 무엇이 실제로 구현됐나

| 경계 | 구현 |
|---|---|
| immutable slow weights | `hswm_weight_snapshot.py` — content-addressed snapshot/candidate/delta, `ell <= 0` |
| durable activation | `hswm_weight_store.py` — SQLite WAL/FULL, stage, epoch CAS, idempotent activation receipt |
| eligibility | `p1_eligibility_tag.py` — episode-ID indexed activation trace와 normalized per-edge tag |
| modulation/commit | `p1_m_commit.py` — expanding baseline, `M=r-r_hat`, clipped tagged/uniform candidate |
| weighted behavior | `p1_weighted_walk.py` — strict K<=2 max-product walker에 `exp(ell)` 결합, path trace 방출 |
| four-arm loop | `p1_loop_harness.py` — A1/A2/A3/A4 격리, 기존 absorption FSM, fresh/canary, CAS |
| LLM function | `p1_llm_answerer.py` — frozen Qwen OpenAI-compatible typed answer function, first-write receipt/cache, gold 입력 불가 |
| sealed environment | `p1_phantom_environment.py` — PhantomWiki split, retrieval, post-answer gold 평가, evidence close |
| generic feedback atomicity | `feedback_store.py`의 lookup→decide→append를 `BEGIN IMMEDIATE` 단일 transaction으로 수정 |

synthetic harness에서는 candidate가 FSM `active`까지 가고, 동시 candidate 두 개 중 하나만 CAS 승리하며, canary 실패 시 active snapshot이 바뀌지 않는 것을 테스트했다. 전체 관련 회귀는 Mac과 Dell 모두 `523 passed, 1 skipped`였다.

## 2. 사전등록과 preflight

- prereg: [`PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json`](PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json), R2 SHA-256 `136405ba5d0006195e9fe4c1a9899eb4ef098bbe22fa725599936479baa0e91d`
- frozen outcome-affecting modules: 17개 SHA-256, guard로 로컬·Dell 양쪽 확인
- live model: `Qwen/Qwen3.6-35B-A3B-FP8` revision `95a723d...`, PID/argv/model snapshot을 deployment receipt로 재증명
- R1은 outcome 전 split preflight에서 `eligible=390 < required=400`으로 fail-closed했다. [refusal](P1_PREFLIGHT_REFUSAL_R1_2026-07-23.json)에 LLM call 0, arm outcome 0을 기록했다.
- R2 amendment는 episode `5×40=200`을 유지하고 disjoint fresh gate만 `5×38=190`으로 바꿨다. learning rule, arms, eta, thresholds, model, bootstrap은 불변이다.

R2 substrate는 5,057 articles, 45,834 bound facts, 0 unbound facts, 25,606 person arcs였다. graph construction과 fresh gate는 LLM 0콜이며, answer function은 800 logical calls/200 unique content-addressed receipts/0 error로 닫혔다. sealed gold는 answer 반환 뒤 evaluator에서만 열렸다.

## 3. 측정 결과

원본 evidence: [`EVIDENCE_P1_CLOSED_LEARNING_LOOP_2026-07-23.json`](EVIDENCE_P1_CLOSED_LEARNING_LOOP_2026-07-23.json), SHA-256 `880de2841d33d04a1e615984287dbd2ab855bd8e288fc7999f19687d57233bfe`, experiment receipt `70cf72a18da617a3494b00848f349f0fd96c6dce444639413c21ace41e24f758`.

| metric | result | gate |
|---|---:|---|
| A1−A2 mean paired recall@10, episodes 2–5 | `0.0` | threshold `> 0.01` 실패 |
| bootstrap 95% lower | `0.0` | threshold `> 0` 실패 |
| A1 episode slope | `-0.0270833` | secondary `> 0` 실패 |
| later mean recall@10 A1/A2/A3/A4 | 모두 `0.1651042` | causal separation 없음 |
| tag utility Spearman | `null` | active commit 0이라 K5 실패 |
| canary regression | 없음 | K4만 비발화 |

회차별 A1 recall@10은 `[0.2375, 0.23333, 0.12292, 0.17083, 0.13333]`, reward는 `[0.125, 0.025, 0.0, 0.025, 0.05]`였다. 네 팔이 byte-equivalent starting/ending active snapshot을 가졌고 같은 회차 곡선을 냈다.

## 4. 왜 변화가 없었나

A1은 episode 2–5에서 각각 L1 약 `0.005`, `0.00375`, `0.00125`, `0.0003125`인 tagged candidate를 실제로 만들었다. A3/A4까지 합쳐 후보는 12개였다. 그러나 12개 모두 absorption FSM의 fresh evaluation에서 `rejected`되어 active snapshot은 genesis에서 한 번도 바뀌지 않았다.

final receipt가 gate 숫자를 직접 노출하지 않은 관측성 결손을 보완하기 위해 frozen staged snapshot과 frozen fresh split만 retrieval-only 재생했다. [`P1_GATE_DIAGNOSTIC_R2_2026-07-23.json`](P1_GATE_DIAGNOSTIC_R2_2026-07-23.json)은 12/12에서 `unseen_delta=0.0`, `unseen_ci_low=0.0`, pass 0을 확인한다. 따라서 실패 원인은 canary나 CAS가 아니라 **eta-scaled edge update가 top-10 rank를 움직일 만큼 표현력/크기가 없었던 것**이다.

추가 [`P1_RANK_INVARIANCE_DIAGNOSTIC_R2_2026-07-23.json`](P1_RANK_INVARIANCE_DIAGNOSTIC_R2_2026-07-23.json)은 12 candidates × fresh 38 = 456 query-cell을 exact score 수준으로 재생했다. updated edge가 selected path에 닿은 것은 21/456, score가 조금이라도 바뀐 것도 21/456이었고, top-10 order/membership 변화는 모두 0이었다. 최대 score delta는 `3.2359e-5`, rank-10/11 gap 대비 최대 비율은 `0.102697`이었다.

두 post-hoc 진단은 새 arm outcome이 아니다. 원 실험의 staged bytes와 disjoint fresh retrieval 비교만 재생했다. 다만 다음 harness는 gate delta/CI와 rank actuation을 final measurement 본문에 직접 넣어야 한다.

## 5. LakatoTree 절차 경계

위 수치는 이 보호대의 scientific RED를 지지한다. 그러나 당시
`p1_phantom_environment.py`가 measurement artifact에 `verdict: FAIL`을 직접
기록했고, 현재 retrievable한 server experiment tag, neutral judge-script
receipt, injected-negative judge receipt가 없다. measurement와 judgment의
분리가 깨졌으므로 유효한 LakatoTree kernel 상태는 **UNJUDGED — procedural
block**이다. 사후 adapter는 prereg chronology와 judge independence를 복구할
수 없다.

독립 audit와 정확한 신호/credit/actuation 분해, 다음 falsifier는
[`RESEARCH_P1_FAILURE_LAKATOTREE_2026-07-24.md`](RESEARCH_P1_FAILURE_LAKATOTREE_2026-07-24.md)에 있다.

## 6. 정직한 현재 상태

| 원 질문 | 2026-07-23 현재 상태 |
|---|---|
| LLM 함수망 runtime | **부분 구현** — receipt된 단일 Qwen answer function과 weighted retrieval dispatch는 실행됨. 다중 typed function network는 아직 아님. |
| 결과→credit→ΔW 폐루프 | **공학 구현·실측 완료, 효능 RED** — candidate까지 닫혔지만 real fresh gate 0/12, active ΔW 0, 다음 행동 변화 0. |
| Agent A→B 학습 전이 | **미구현·유예** — P1 causal state가 살아남지 못했으므로 P2로 진행할 근거 없음. |
| learned topology 재배선 | **미증명** — 기존 shadow gate 0/3 결과 유지. weight 실패를 이유로 gate를 완화하지 않음. |
| consolidation/sleep | **미구현** — active 학습 신호가 없으므로 현 단계에서 붙이면 원인 불명 복잡도만 늘어남. |

## 7. 다음 결정

prereg K1 commitment를 그대로 집행한다.

1. 이 PhantomWiki substrate에서 같은 `eta·M·tag` slow-weight 실험을 gate/eta 튜닝으로 재시도하지 않는다.
2. 다음 비교는 **typed verdict-to-lesson baseline**이다. 기존 P1 질문은 재사용하지 않고 새 untouched universe에서 frozen Qwen, calls/tokens parity, no-memory와 raw-transcript 대조를 둔다. 측정 금지 상태의 계약은 [`PREREG_P1V2_TYPED_VERDICT_LESSON_2026-07-24.json`](PREREG_P1V2_TYPED_VERDICT_LESSON_2026-07-24.json)에 있다.
3. lesson이 fresh unseen을 움직이면 HSWM의 학습 plane은 당분간 numeric edge weight가 아니라 evidence-bound lesson retrieval로 축소한다.
4. lesson도 실패하면 P2/P3/P4를 진행하지 않고 “compiler + safe graph memory” 경계로 주장 범위를 줄인다.
5. P1-v2를 열 수 있는 유일한 조건은 새 evidence가 기존 update와 다른 행동공간(예: query-conditioned fast potential 또는 typed lesson)을 정당화할 때다. 기존 RED를 gate 완화로 덮지 않는다.
