# PREREG P0 — 인지체 metric 잠금 (claim & metric lock)

> **status**: SECONDARY_AI_DRAFT — USER ratify 대상. ratify 시 `CANONICAL_USER_DIRECTION` 하위 실행층으로 편입.
> **schema**: hswm-preregistration/v1 (program-level; 실험 prereg은 JSON 관례, 본 건은 측정 없는 metric/주장 잠금이라 MD).
> **programme**: `HSWM_LOCAL_RECORD` · branch `canon-direction-neural-cognitive-entity-20260723`.
> **상위 정전**: [`CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`](CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md) §3–§4 — 본 문서는 그 §3(인지체 metric)·§4(로드맵 kill)의 **집행 잠금**이다. 정전 텍스트와 충돌 시 정전이 이긴다.
> **registered_before_measurement**: true — 아래 metric으로 계산된 값은 어떤 arm에서도 아직 존재하지 않는다 (2026-07-24 현재 P1 모듈 미구현, `PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json` module_sha256 = PENDING).

## 0. 잠그는 것 3가지

1. **주장의 형태** (tribunal 반영 좁힘) — §1
2. **인지체 metric과 3개 baseline** — §2
3. **평가 3종과 각종별 철회 규칙** — §3

§4는 프로그램 kill 조건 색인, §5는 측정 규율. **이 문서를 어긴 측정은 프로그램 진전으로 계산하지 않는다** (notebook-only).

## 1. 주장의 형태 (claim lock, tribunal-narrowed)

> **방어 가능 청구**: HSWM은 **n-ary 하이퍼그래프 위에서, CRDT 비트수렴 하에, 외부 판결(semantic verdict)-영수증을 제3인자 M으로 하는, LLM-실행 함수 단위들의 공유 시멘틱 회로**다. three-factor plasticity와 sleep-staged consolidation은 **발명이 아니라 채택(adopted)** — Frémaux & Gerstner 2016 원조, Trappe 2026 (Phasor Agents) 인스턴스 선행.

- 금지 표현: "학습하는 시맨틱 신경망" 무수식 사용, three-factor/sleep 조합의 novelty 암시, sleep 안정성-제어 프레이밍의 무인용 사용 (Trappe 2026 인용 의무).
- 시간척도 명시 의무 (tribunal §3): HSWM의 M은 **에피소드~일 단위** regime — wall-clock decay 금지, episode-ID 역참조 tag. Phasor식 초 단위 연속 eligibility와 구별할 것.
- 외부 수치 인용 규율: Phasor 수치는 **self-reported, code unavailable (2026-07-24 실측 404)** 단서 필수 (SYMPOSIUM `HSWM/TRIBUNAL_PHASOR_AGENTS_2026-07-24.md`).

## 2. 인지체 metric (정전 §3의 집행 형태)

> **인지체 학습 ≝ sealed unseen 성능의 에피소드-누적 곡선 slope > 0.**

집계 규칙 (잠금):

- **곡선**: episode e = 1..E에서, 그 에피소드의 **신선·봉인 질의군** 위 성능 s(e). 질의 재사용·리크 = void.
- **판정**: slope(s(1..E)) > 0 AND bootstrap95 하한 > 0 AND 아래 3 baseline과의 **동일 예산** 대비 우위.
- **Baselines (전부 의무, 하나라도 빠지면 무효)**:
  - **B-nomem**: no-memory — 같은 walker/reader, HSWM 쓰기·읽기 전부 OFF.
  - **B-transcript**: raw-transcript — 같은 내용을 원문 로그로 붙여넣는 단순 누적 (ReasoningBank형 통제).
  - **B-fullctx**: full-context — 예산 내 전체 문맥 투입.
- **Context Saturation Gap**: Δ = HSWM − B-fullctx를 모든 보고에 병기. **Δ ≤ 0인 태스크군에서는 그 군의 인지체 주장을 철회** (정전 §3).
- 부품 metric(retrieval F1, recall@k)은 진단용 병기만 — 인지체 판정에 대체 사용 금지.

## 3. 평가 3종 (battery lock)

| # | 축 | 프로토콜 | 철회 규칙 |
|---|---|---|---|
| E-MB | continual feedback | MemoryBench형: 서비스 중 누적 피드백으로 sealed 후속 성능이 개선되는가 | slope ≤ 0이면 continual-feedback 주장 철회 |
| E-FE | forgetting | ForgetEval형 5-family 프로브: supersession / decay / amnesia / purge / drift | 어느 family든 통제 대비 유의 악화 시 해당 쓰기 경로 동결, homeostasis 수선 전 학습 재개 금지 |
| E-CSG | context saturation | Δ = HSWM − B-fullctx (태스크군별) | Δ ≤ 0 태스크군 주장 철회 (§2와 동일 규칙, 독립 병기) |

공통: equal-compute(토큰·호출·벽시계 상한 사전 선언), prereg 선행, sealed split, bootstrap95.

## 4. 프로그램 kill 조건 색인 (정전 §4 잠금 확인)

| kill | 내용 | 소유 prereg |
|---|---|---|
| **K1** | P1 tagged vs untagged 대조 N라운드 내 개선 없음 → three-factor weight-learning 접고 ExpeL식 텍스트 lesson baseline 회귀 | `PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json` (K1–K5 세부, 이미 잠금) |
| **K2** | P2 전이 이득 0 또는 flat/vector baseline과 무차별 → "shared neural memory" 헤드라인 철회, substrate 포지션 영구 고정 | P2 prereg (미작성 — 설계만, 구현은 P1 통과 후) |
| **K3** | P3 shadow-gated 3라운드 연속 수용 0 → topology evolution 유예 | P3 prereg (미작성) |
| **K4** | P4 oracle gate가 B2 in-field −0.065 복구 실패 → merge 자체 결함, 연합 주장 축소 | P4/B2.1 prereg (미작성) |
| **K0 (프로그램)** | E-MB·E-CSG 양축에서 slope ≤ 0 AND Δ ≤ 0이 2개 독립 태스크군에서 재현 → "인지체" 측정 범주 자체를 철회하고 memory substrate 포지션으로 영구 고정 (기존 `correction-p5-category-substrate-not-reasoner`와 동일 논리의 상위층) | 본 문서 |

## 5. 측정 규율 (정전 §5 negative heuristic의 prereg 적용분)

1. 값/trajectory 원문 저장을 학습으로 보고 금지 — **증류만 학습**.
2. 임베딩 리프트(~95%)를 구조 기여로 포장 금지 — E3 ablation 전 "구조 load-bearing" 주장 금지.
3. equal-budget 단일 agent 대조 없는 multi-agent 수치 보고 금지.
4. 깊은 전파/GNN arm 추가 금지 (ML9/11/12, T5, add1584 — 재제안 자체가 차단).
5. 모든 ΔW/ΔH 커밋은 regression canary 통과분만 (GRASP 형태, P1 prereg K4와 동일 규칙).
6. arm 결과는 module sha 잠금 전 열어보지 않는다 (P1 prereg void 조건과 동일).

## 6. 완료 조건 (P0 exit)

- [ ] 본 문서 USER ratify
- [ ] HSWM_LOCAL_RECORD `HSWM_LOCAL_RECORD`에 P0 노드 등록 (theory lock, 판결 없음 — 측정은 P1부터)
- [ ] 정전 §7 "즉시 다음 행동 2" 완료 표기

P0는 측정을 만들지 않는다. 첫 측정 = P1 (`PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json`, 모듈 구현 대기).

## 7. Provenance

- 정전: `CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md` §3–§5, §7-2 (USER ratified 2026-07-23).
- 재판: `TRIBUNAL_PHASOR_AGENTS_PRIOR_ART_2026-07-23.md` (정본) + SYMPOSIUM `HSWM/TRIBUNAL_PHASOR_AGENTS_2026-07-24.md` (404 보충 감사).
- 하위 prereg: `PREREG_P1_CLOSED_LEARNING_LOOP_2026-07-23.json`.
- 원본 PROM: SYMPOSIUM `HSWM/PROM_MACRO_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`.
- Layer: SECONDARY_AI — §1 청구 문안과 §2–§3 잠금은 USER ratify 전까지 제안.
