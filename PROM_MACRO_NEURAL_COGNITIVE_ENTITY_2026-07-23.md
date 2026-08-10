# PROM 4축 — HSWM = 거대 인지 신경망체: 거시 방향성

> **status**: SECONDARY_AI 종합 (USER 질의 2026-07-23: "HSWM이 agent=함수인 하나의 신경망, continual learning하는 거대 인지능력체가 될 수 있나? 지엽 말고 거시 계획·방향성")
> **방법**: 4축 병렬 PROM (A1 로컬캐논 / A2 continual-learning 문헌 / A3 비-backprop credit assignment / A4 multi-agent 아키텍처). 웹 1차소스 + 로컬 정본 대조.
> **성격**: 거시 방향 PROM — prereg 아님. 각 실험 슬라이스는 별도 prereg + USER ratify 필요.

## 0. 한 줄 판정

**필요충분조건이 처음으로 한 문장으로 닫혔다:**
> HSWM이 "신경망"으로 불릴 최대 방어 가능 형태 = **three-factor local rule(eligibility tag × judgment 신호) + associative memory readout + stochastic structural plasticity(Bayesian rewiring)** — 이 세 개의 조합. backprop 신경망이 아니라, 문헌이 지지하는 유일한 "학습하는 망"의 형태다. 그리고 지금 HSWM에는 이 중 **readout만 있고, tag와 M과 stochastic edit이 없다.**

## 1. 축별 수확 요지

### A1 로컬 캐논 (이미 있는 것 / 없는 것)
- 루프의 **"안전한 쓰기" 절반은 실물 코드로 검증됨**: 불변 Field(CAS) + CRDT supersede 원장(비트수렴, teeth 실측) + FSM 흡수 게이트(해로운 후보 3/3 차단) + kernel v2.
- 루프의 **"학습 신호" 절반은 전부 spec 또는 반증 상태**: outcome→judgment 환류 런타임 없음, credit assignment 규칙 없음(dose-graded decay뿐), Δtopology 후보 생성 정책 없음.
- judgment loop 실측 1건 = −0.012(해로움). 비-cosine regime +0.372 신호는 단일샘플 degenerating.
- USER 정전 발화: "구조나 fsm을 개선시키면서 흡수흡수흡수"(2026-07-22), "여러 HSWM을 MoE처럼 연결/분리, agent가 완성시키는 시맨틱 신경망"(동), "연산>절약".

### A2 Continual learning 문헌 (2024–2026)
- **ReasoningBank (Google, arXiv:2509.25140)**: 성공/실패 trajectory를 self-judged로 **증류**해 쓰고 다음 태스크에 주입 — HSWM 비전과 가장 동형이며 실측 우위. 단 k=1 검색이 최적(49.7%→k=4 44.4% 악화): **주입량이 늘면 간섭**.
- **ACE (arXiv:2510.04618)**: incremental delta + grow-and-refine만 살아남음. **재작성/요약식 consolidation = context collapse로 반증**.
- **GRASP**: 회귀 게이트 없이 monotonic 축적하면 이전에 맞던 행동이 깨짐 → **모든 쓰기에 regression probe가 2026년 표준**.
- **ForgetEval (arXiv:2606.15903)**: 생산 환경 지배적 실패는 recall이 아니라 **forgetting 실패**. mutation-time 좁은-JSON hook 하나로 +22~24pt. LLM 자유형 쓰기 게이트(Mem0 infer=True)는 supersession 붕괴.
- **MemoryBench**: continual feedback 학습은 업계 공인 미해결. SOTA도 "far from satisfying" → **HSWM이 노릴 빈 벤치**.
- **그래프 엣지 가중치의 outcome 기반 갱신 + 중요도 보호(EWC 유사) 조합은 문헌 공백** — 선점 가능 지점이자 미검증 지점.

### A3 Credit assignment without backprop
- **Three-factor rule `ΔW = M(t) × eligibility(pre,post)` (Frémaux & Gerstner 2016, e-prop 계열)이 HSWM의 정준 모델.** "judgment = neuromodulatory broadcast", "retrieval 시 tag → verdict 도착 시 commit" = synaptic tagging의 정확한 구현. HSWM의 현재 dose-graded decay는 M이 없는 특수형.
- **순수 Hebbian 단독 = 학습이 아니라 통계 축적** (제3인자 없으면 보상과 무관하게 강화). homeostasis(BCM 가변 임계, W norm 감시)가 learning 켜기 *전* 필수.
- **Kappel–Maass Bayesian rewiring**: rewiring과 가중치 가소성을 하나의 사후분포 샘플링으로 통합 → ADD/SPLIT/MERGE/SUPERSEDE 수용을 binary gate가 아니라 **evidence의 함수인 확률 + prior(타입 쿼터)** 로 재공식화할 근거. PROM_5 shadow-gated absorption과 정확히 호환.
- **Surprise gating**: 기대와 어긋날 때만 judgment 청구 — LLM judgment 예산 절감 + 탐험 신호.
- 반증: Forward-Forward(성능/협업 붕괴), 하이퍼그래프 위 학습된 다층 전파(oversquashing + 남⾶ traversal-OFF 3중 반증), 사실 단위 neuroevolution(비용 발산).
- **경고: Phasor Agents (2026, arXiv:2601.04362)** — 그래프 에이전트 + three-factor plasticity + sleep-staged learning. 거의 동형 선행. prior-art tribunal 필요.

### A4 Agent-as-function 아키텍처
- **MoE routing collapse는 보편 실패 모드** (Switch Transformer aux loss의 존재 이유). Expert-choice inversion(state가 agent를 고름)이 구조적 우위 — HSWM의 W가 이미 이 형태. **라우팅 집중도(Gini, 상위 발화 점유율)를 day-1부터 계측.**
- **MAST (Berkeley 2025)**: MAS 이득은 single agent 대비 종종 미미, 실패는 조직 설계 문제. **budgeted synergy: 고정 예산 하 multi-agent는 역성능 조건이 예측 가능** — equal-budget 대조 없는 스케일아웃은 취미.
- **Stigmergy 3요건 (CodeCRDT)**: observable updates + deterministic convergence + monotonic progress. HSWM은 CRDT로 2번째를 이미 확보 — 3요건을 불변식으로 선언할 자격 있음.
- **GPTSwarm (ICML 2024)**: node/edge 최적화의 학습 루프 선례. **HSWM의 차별점 = 엣지 최적화가 에피소드적이 아니라 영속 구조에 누적된다는 것.** 이것이 유일한 본질적 우위 주장.
- **LbMAS**: 블랙보드(=HSWM) 경유 통신은 token 절감+조정 이득 있으나 어려운 과제서 수렴률 붕괴(29.4%) — 구조화된 상태(W, provenance)로 완화하는 게 차별점.

## 2. 거시 로드맵 — 5단계 (각 단계 = kill 조건 있는 prereg 슬라이스)

```
P0 주장 고정  →  P1 루프 닫기  →  P2 전이 증명  →  P3 구조 가소성  →  P4 연합/수면
 (주장의 형태)   (학습 신호)     (공유망 가치)    (진화하는 회로)    (거대 인지체)
```

### P0 — 주장의 형태를 고정 (지금, 비용 0)
- "신경망"의 정의를 §0 한 줄로 못박고, 마케팅이 이 선을 넘지 않게 함.
- **성공 metric 정의가 선결**: "인지체가 똑똑해졌다" = sealed unseen 성능의 **에피소드-누적 곡선 slope > 0** (full-context baseline 및 no-memory baseline 대비). retrieval F1은 부품 metric일 뿐 인지체 metric이 아님. 이 prereg 없이는 모든 후속 실험이 notebook-only.
- 평가 3종 채택: **MemoryBench(continual feedback) + ForgetEval(forgetting 5-family) + Context Saturation Gap(Δ = HSWM − FullContext)**.

### P1 — 닫힌 루프 최소 수직 슬라이스 (학습 신호의 탄생)
- **eligibility tag**: retrieval/activation 시 태그(강도=activation, episode-ID 역참조 인덱스 — verdict가 수일 뒤 와도 decay로 안 죽게).
- **M 신호**: 외부 verdict 도착 시 `ΔW = (verdict − baseline) × tag_strength` 커밋. baseline 없으면 systematic drift (LLM-as-judge 교정 필수).
- **regression canary**: 모든 ΔW/Δ구조 커밋 전에 "기존에 맞던 회상 N개" 재질의 (GRASP 형태).
- **homeostasis**: W norm 성장 감시 + 활동-의존 가변 임계 — learning 켜기 전 설치.
- 완료 게이트 = PR #3이 요구하는 것과 동일: "LakatoTree verdict이 다음 dispatch를 인과적으로 바꾸는" 영수증 1건.
- **K1**: tagged vs untagged 대조로 N라운드 내 다음-에피소드 개선 없으면 → three-factor 라인 접고 ExpeL식 텍스트 lesson baseline으로 회귀.

### P2 — 공유망 전이 증명 (헤드라인 과학 주장)
- **Q-shared-net-transfer**: Agent A의 write가 Agent B의 zero-shot gain을 만드는가. equal-compute, shared-transcript/vector-DB baseline 대조.
- **Q-W-first-class**: W 절제 시 transfer만 죽고 cosine floor는 사는가 (W가 load-bearing임의 절제 증명).
- **K2**: 이득 0 또는 baseline과 무차별 → "shared neural memory" 헤드라인 철회, substrate 포지션으로 영구 고정.

### P3 — 구조 가소성 (흡수흡수흡수의 정당한 형태)
- Phase B topology 흡수(1차 payload = identity material)를 **Bayesian rewiring으로**: 수용 확률 = f(판결 evidence) × prior(타입 쿼터/희소성). binary FSM 게이트 위에 확률층.
- 음성 신호는 계속 b(supersession)로만 — j≥0 boost-only 규율 유지.
- **K3**: shadow-gated 3라운드 연속 수용 0 → topology evolution 유예 (PROM_5 기존 kill과 통합).

### P4 — 연합 + 수면 (거대 인지체의 형상)
- Federated fields = "뇌 영역": Phase B 대수(ADD/SPLIT/MERGE/SUPERSEDE ≡ field-level 연산) 그대로. B2의 in-field −0.065 비용 복구(learned gate)가 선결 — **oracle gate가 복구 못 하면 merge 자체 결함으로 연합 주장 축소 (K4)**.
- Sleep-time consolidation = async offline 전용 (hot path 격리). 단 SWE-Features 반례처럼 고예산 구간 역효과 kill 조건.
- 라우팅 지표 상시: 상위 10% 엣지/agent가 발화 80% 점유 시 collapse 판정, 보조 균형항 도입.

## 3. 절대 하지 말 것 (4축 교차 확정 dead-end)

1. 값/trajectory 원문 저장을 "학습"이라 부르기 (P6 + ReasoningBank 이중 반증 — **증류만 학습**).
2. 메모리 재요약·재작성식 consolidation (ACE context collapse).
3. LLM 자유형 쓰기 게이트 (Mem0 붕괴) — 좁은 JSON 계약 + regression probe만.
4. 깊은 전파/GNN/다층 message passing (남⾶ 3중 반증 + oversquashing 문헌).
5. agent 간 자유 자연어 대화를 1차 조정 채널로 (telephone game, MAST) — 조정은 HSWM 경유(stigmergy).
6. 보조 균형 없는 자유 라우팅 (MoE collapse).
7. equal-budget 단일 agent 대조 없는 multi-agent 스케일아웃 (budgeted synergy).
8. Forward-Forward, 사실 단위 neuroevolution.
9. 임베딩 리프트(~95%)를 구조 기여로 포장 — E3 ablation 전 "구조 load-bearing" 주장 금지.

## 4. 정직한 천장 (USER에게)

- 문헌이 지지하는 최대치는 "Transformer 대체"가 아니라 **"기반 모델 위에서 함수 단위가 LLM으로 실행되고, 판정으로 가소성이 생기는 공유 시멘틱 회로"** — 이건 지난 대화의 외부 평가와 동일 결론이며, 4축 독립 리서치가 재확인.
- **진짜 미개척지이자 HSWM만이 주장 가능한 것 3개**: ① 엣지 최적화가 *영속 구조*에 누적(GPTSwarm은 에피소드적), ② 그래프 가중치의 outcome 갱신 + 중요도 보호 조합(문헌 공백), ③ n-ary 관계 위의 credit assignment(pairwise 문헌뿐, Shapley/균등 분배 미정).
- **즉시 할 일 = Phasor Agents (2026) prior-art tribunal.** three-factor + 그래프 에이전트 + sleep 조합이 이미 나와 있으므로, HSWM의 차별점을 "n-ary 하이퍼그래프 위에서, CRDT 수렴 하에, 판결-영수증 결합으로" 좁혀야 선점 주장이 산다.

## 5. 즉시 다음 행동 제안 (우선순위)

1. Phasor Agents prior-art tribunal (나생문 또는 PROM 1축).
2. P0 prereg 작성: 인지체 metric(누적 slope) + 평가 3종 + P1 kill 조건.
3. P1 수직 슬라이스 구현 스펙: eligibility tag 스키마 + M 커밋 경로 + canary (기존 FSM/CRDT/kernel v2 재사용, 신규 코드 최소).
4. P2 실험 설계만 (equal-compute multi-agent harness) — 구현은 P1 통과 후.

## 6. Provenance

- USER 질의 2026-07-23 (이 세션). 4축 subagent 리서치 결과 종합.
- 로컬: `HSWM/INDEX.md`, `SPEC_SHARED_HYPERGRAPH_NN_SEMANTIC_WEIGHT`, `SPEC_OPEN_SELF_SIMILAR`, `PROM_P6`, `PROM_8`, `PROM_5`, `AMENDMENT_OPEN_HSWM_KERNEL_V2`, `THEORY/재배맨/HSWM_STANDARD.md`, `내가 주는 말.txt`.
- 웹 1차소스: ReasoningBank 2509.25140 / ACE 2510.04618 / ForgetEval 2606.15903 / MemoryBench 2510.17281 / Frémaux & Gerstner 2016 / e-prop (Bellec 2020) / Kappel–Maass 2015,2017 / Switch (Fedus 2022) / MAST 2503.13657 / CodeCRDT 2510.18893 / GPTSwarm (PMLR v235) / LbMAS 2507.01701 / Phasor Agents 2601.04362.
- Layer: SECONDARY_AI — P0~P4 로드맵 자체는 USER ratification 대기.
