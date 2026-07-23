# CANON — HSWM = 거대 인지 신경망체: 방향 정전

> **status**: `CANONICAL_USER_DIRECTION` — USER가 2026-07-23 “정전으로 만들어 HSWM 레포에 쓰라”고
> 명시 ratify. 단 §6의 문헌 종합과 세부 수치는 `SECONDARY_AI_RESEARCH` 출처를 유지한다.
> **supersedes nothing** — 상위 방향층. 미시 계약은
> [`PROM_HSWM_PLASTICITY_WEIGHT_TOPOLOGY_LEARNING_2026-07-23.md`](PROM_HSWM_PLASTICITY_WEIGHT_TOPOLOGY_LEARNING_2026-07-23.md)(이하 plasticity PROM)이 소유한다.
> **원본 PROM**: SYMPOSIUM 둥지 `HSWM/PROM_MACRO_NEURAL_COGNITIVE_ENTITY_2026-07-23.md` (4축 병렬 리서치).

## 0. 정전 한 줄

> **HSWM의 목표 형태는 Transformer의 대체가 아니라, 기반 모델(LLM)에 결합된 채 판정(judgment)으로
> 가소성을 얻는 하나의 공유 외부 회로다.** agent는 이 회로 위의 함수(뉴론)이고, HSWM 상태는
> 회로의 가중치이며, 검증된 경험만이 회로를 다시 배선한다. 이 회로가 “신경망”으로 불릴 최대
> 방어 가능 형태는 다음 세 조합뿐이다.

\[
\boxed{
\text{신경망적 HSWM}
=
\underbrace{\text{three-factor rule}}_{\text{eligibility} \times \text{judgment}}
+
\underbrace{\text{associative memory readout}}_{\text{1-step, shallow}}
+
\underbrace{\text{stochastic structural plasticity}}_{\text{Bayesian rewiring}}
}
\]

## 1. 권위 경계

### CANONICAL_USER (정전)

1. HSWM은 agent가 완성시키는 semantic neural network다. agent = 함수, 공유 HSWM 상태 = 망의
   가중치·활성. (2026-07-22 발화, `SPEC_OPEN_SELF_SIMILAR` §0)
2. 여러 HSWM은 MoE처럼 나뉘고 전문화되고 다시 연결된다. 고정된 “1층/2층”은 없다. (동)
3. “구조나 fsm을 개선시키면서 흡수흡수흡수” — 학습은 값 저장이 아니라 구조 가소성이다. (2026-07-22)
4. 연산 > 절약. (2026-07-22)
5. **본 문서의 §0·§2·§3·§4·§5를 방향 정전으로 채택한다.** (2026-07-23, 이 세션 ratify)

### SECONDARY_AI (연구 근거, 정전 아님)

- §6의 4축 문헌 종합, 각주 수치, 외부 논문 인용 전부. 정전은 “방향”이지 “문헌 해석”이 아니다.
- plasticity PROM의 수식·FSM 계약·B2.1 실험 설계 — 실행 계약이며 본 정전의 하위층.

## 2. 신경망의 정의 (범주 정정 포함)

신경망 = backprop이 아니다. **가중 연결 + 활성 + 결과 의존 가소성**이 본질이다. HSWM 매핑:

| 신경망 개념 | HSWM 대응 | 상태 |
|---|---|---|
| 뉴로드 좌표 | embedding \(X\) | frozen (리프트 본체 ~95%) |
| 회로 | hypergraph n-ary incidence | 코드 있음 |
| 시냅스 가중치 | semantic weight \(W\) (fast \(\theta\) + slow \(\ell,b\)) | weight-plane 실측 있음 |
| 활성 | activation \(a\) (1-step readout) | 코드 있음, 휘발 |
| **eligibility trace** | retrieval/activation 시 tag | **미구현 — P1 대상** |
| **neuromodulator \(M\)** | 외부 verdict → \(\Delta W = (r-\hat r)\,z\) | **미구현 — P1 대상** |
| 구조 가소성 | ADD/SPLIT/MERGE/SUPERSEDE + 수용 확률 | 게이트만 있음, 확률층 없음 |
| homeostasis | W norm 감시 + 가변 임계 | **학습 켜기 전 필수, 미구현** |

현재의 dose-graded supersession decay는 \(M\) 없는 three-factor의 특수형이다. tag와 \(M\)의
분리가 닫힌 루프의 최소 구현이다(plasticity PROM §7이 미시 계약 소유).

## 3. 인지체 metric — “똑똑해졌다”의 정전 정의

retrieval F1은 부품 metric이지 인지체 metric이 아니다. 정전 metric:

> **인지체 학습 = sealed unseen 성능의 에피소드-누적 곡선 slope > 0**,
> 동일 예산의 (a) no-memory baseline, (b) raw-transcript baseline, (c) full-context baseline
> 대비로 판정한다.

평가 3종을 표준으로 채택한다:

1. **continual feedback 축** — MemoryBench형 프로토콜 (서비스 중 누적 피드백으로 개선되는가).
2. **forgetting 축** — ForgetEval형 5-family 프로브 (supersession/decay/amnesia/purge/drift).
   생산 환경의 지배적 실패는 recall이 아니라 forgetting이다.
3. **Context Saturation Gap** — \(\Delta = \text{HSWM} - \text{FullContext}\)를 항상 명시.
   \(\Delta \le 0\)인 태스크군에서는 그 군의 주장을 철회한다.

## 4. 거시 로드맵 (P0–P4)

```
P0 주장 고정  →  P1 루프 닫기  →  P2 전이 증명  →  P3 구조 가소성  →  P4 연합/수면
 (metric 정의)   (학습 신호)     (공유망 가치)    (진화하는 회로)    (거대 인지체)
```

- **P0 — 완료 조건**: 본 정전 + 인지체 metric prereg. 비용 0.
- **P1 — 루프 닫기**: eligibility tag(episode-ID 역참조, wall-clock decay 금지) → verdict 도착 시
  \(\Delta W=(r-\hat r)z\) 커밋 + regression canary + homeostasis. 완료 게이트 =
  “판정이 다음 dispatch를 인과적으로 바꾼 영수증 1건”. 미시 계약 = plasticity PROM §7–§10.
  **K1**: tagged vs untagged 대조로 N라운드 내 개선 없으면 ExpeL식 텍스트 lesson baseline으로 회귀.
- **P2 — 전이 증명 (헤드라인)**: frozen Agent-B, A의 transcript 차단, equal-compute에서
  A의 write → B의 sealed unseen gain. 절제 증명(W 제거 시 transfer만 사망) 포함.
  **K2**: 이득 0 또는 flat/vector baseline과 무차별 → “shared neural memory” 헤드라인 철회.
- **P3 — 구조 가소성**: topology op 수용을 binary 게이트가 아니라 evidence의 함수인
  확률 × prior(타입 쿼터/희소성)로 (Bayesian rewiring). 한 번에 op 하나.
  **K3**: shadow-gated 3라운드 연속 수용 0 → topology evolution 유예.
- **P4 — 연합 + 수면**: federated fields = 뇌 영역. B2 in-field −0.065 비용 복구(learned gate,
  B2.1)가 선결. sleep consolidation은 async offline 전용. 라우팅 Gini/발화 점유율 상시 계측.
  **K4**: oracle gate가 in-field 손해를 복구 못 하면 merge 자체 결함으로 연합 주장 축소.

## 5. negative heuristic (정전 dead-end — 재제안 금지)

1. 값/trajectory 원문 저장을 “학습”이라 부르기 — P6 + ReasoningBank 이중 반증. **증류만 학습.**
2. 메모리 재요약·재작성식 consolidation — ACE context collapse.
3. LLM 자유형 쓰기 게이트 — Mem0 infer=True 붕괴. 좁은 JSON 계약 + regression probe만.
4. 깊은 전파/GNN/다층 message passing — 남⾶ 3중 반증(ML9/11/12, T5, add1584) + oversquashing 문헌.
5. agent 간 자유 자연어 대화를 1차 조정 채널로 — 조정은 HSWM 경유(stigmergy 3요건:
   observable updates, deterministic convergence, monotonic progress).
6. 보조 균형 없는 자유 라우팅 — MoE routing collapse는 보편 실패 모드.
7. equal-budget 단일 agent 대조 없는 multi-agent 스케일아웃 — budgeted synergy 반증.
8. Forward-Forward, 사실 단위 neuroevolution — 성능·비용 발산.
9. 임베딩 리프트(~95%)를 구조 기여로 포장 — E3 ablation 전 “구조 load-bearing” 주장 금지.
10. 검색 메모리 대량 주입 — k 증가 시 성능 하락 실측 (ReasoningBank 49.7→44.4%).

## 6. 근거 요지 (SECONDARY_AI_RESEARCH — 4축 PROM 수확)

- **A1 로컬 캐논**: 안전한 쓰기 절반(불변 Field, CRDT 원장, FSM 게이트, kernel v2)은 실측됨.
  학습 신호 절반(outcome→judgment→credit→Δtopology)은 전부 spec 또는 반증 상태.
- **A2 continual learning 문헌**: ReasoningBank(증류 write-back 실측 우위), ACE(incremental delta만
  생존), GRASP(regression 게이트 필수), ForgetEval(forgetting이 지배 실패), MemoryBench
  (continual feedback은 업계 공인 미해결 = HSWM이 노릴 빈 벤치).
- **A3 credit assignment**: three-factor/e-prop이 정준 모델. 순수 Hebbian 단독 = 통계 축적이지
  학습 아님. Kappel–Maass Bayesian rewiring이 구조 편집의 normative 근거. surprise gating으로
  judgment 예산 절감.
- **A4 multi-agent 아키텍처**: GPTSwarm 엣지 최적화의 선례 — 단 에피소드적. **HSWM의 유일한
  본질 우위 = 엣지 최적화가 영속 구조에 누적된다는 것.** MAST/budgeted synergy = 조직 설계
  문제이며 equal-budget 대조 없는 MAS는 필패 조건이 예측 가능.

**HSWM만이 주장 가능한 미개척지 3개**:
① 엣지 최적화의 영속 누적(GPTSwarm은 불가), ② 그래프 가중치의 outcome 갱신 + 중요도 보호
(문헌 공백), ③ n-ary 관계 위 credit assignment(pairwise 문헌뿐, 분배 규칙 미정).

**선행 재판 완료 (2026-07-23)**: Phasor Agents (arXiv:2601.04362) —
[`TRIBUNAL_PHASOR_AGENTS_PRIOR_ART_2026-07-23.md`](TRIBUNAL_PHASOR_AGENTS_PRIOR_ART_2026-07-23.md).
판정: novelty kill 아님. 단 “three-factor + sleep-staged consolidation on a graph” **일반 청구는
사망** — HSWM은 이 조합을 발명이 아니라 **채택(adopted)**으로 표기한다. 생존 슬롯 4:
n-ary credit assignment / LLM semantic verdict를 M으로 / topology 가소성 / 다중 agent 공유
시맨틱 망. 시간척도(초 vs 에피소드~일)가 regime을 갈라 episode-ID tag 선택을 재확인.
흡수 목록(dual-timescale eligibility, 안정성 예산, timestamp-shuffle falsifier)은 재판 §5.

## 7. 즉시 다음 행동

1. ~~Phasor Agents prior-art tribunal~~ → **완료** (`TRIBUNAL_PHASOR_AGENTS_PRIOR_ART_2026-07-23.md`).
   다음은 재판 §5 흡수 목록의 P1 편입 검토(USER ratify 대상).
2. P0 prereg 작성: 인지체 metric(slope) + 평가 3종 + P1 kill 조건.
3. P1 수직 슬라이스 스펙: eligibility tag 스키마 + \(M\) 커밋 경로 + canary
   (기존 FSM/CRDT/kernel v2 재사용 — plasticity PROM §9 loop가 앞단).
4. P2 실험 설계만 — 구현은 P1 통과 후.

## 8. provenance

- USER ratify 발화 2026-07-23 (SYMPOSIUM 세션): “그내용 명문화 정전으로 만들어서 hswm 레포에다가 써줘봐봐”.
- 4축 PROM 원본: SYMPOSIUM `HSWM/PROM_MACRO_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`.
- 하위 실행 계약: `PROM_HSWM_PLASTICITY_WEIGHT_TOPOLOGY_LEARNING_2026-07-23.md` (동일자, 독립 수렴).
- 로컬 정본: `SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md`, `SPEC_SHARED_HYPERGRAPH_NN_SEMANTIC_WEIGHT_2026-07-22.md`,
  `DESIGN_PHASE_B_FEDERATED_HSWM_2026-07-22.md`, `EFFICACY.md`.
- 웹 1차소스: ReasoningBank 2509.25140 / ACE 2510.04618 / ForgetEval 2606.15903 /
  MemoryBench 2510.17281 / Frémaux & Gerstner 2016 / e-prop (Bellec 2020, Nat. Comms.) /
  Kappel–Maass 2015·2017 / Switch (Fedus 2022, JMLR) / MAST 2503.13657 / CodeCRDT 2510.18893 /
  GPTSwarm (PMLR v235) / LbMAS 2507.01701 / Phasor Agents 2601.04362.
- 검색·회수 기준일: 2026-07-23.
