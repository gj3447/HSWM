# TRIBUNAL — Phasor Agents (arXiv:2601.04362) prior-art 재판

> **date**: 2026-07-23 · **mode**: Naesengmoon (적대적 novelty 재판)
> **trigger**: [`CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`](CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md) §6 선행 경보 → 정전 §7 즉시 다음 행동 1순위
> **피고**: Rodja Trappe (Zauberzeug GmbH), "Phasor Agents: Oscillatory Graphs with Three-Factor Plasticity and Sleep-Staged Learning", [arXiv:2601.04362v1](https://arxiv.org/abs/2601.04362) (2026-01-07), 코드 공개 ([github.com/zauberzeug/phasor-agents-paper](https://github.com/zauberzeug/phasor-agents-paper), PyPI `phasor-agents`)
> **원고(방어 대상)**: HSWM 정전 §0–§6의 신경망 정체성 주장
> **1차 소스**: abstract + [HTML full text v1](https://arxiv.org/html/2601.04362v1) 직독. 실재 검증 통과.

## 0. 판정 한 줄

**novelty kill 아님.** 단 "three-factor plasticity + sleep-staged consolidation on a graph"의 **일반 청구는 사망** — 그 조합은 더 이상 HSWM의 것으로 주장 못 한다. HSWM 특유 슬롯 4개(n-ary / LLM 판정 변조 / 구조 가소성 / 다중 agent 공유 시맨틱 망)는 **전원 생존**.

## 1. 피고가 실제로 한 것 (겹침 지도)

| 메커니즘 | Phasor Agents | HSWM 정전 대응물 | 겹침 판정 |
|---|---|---|---|
| three-factor `ΔW = η·g·M·u·e` | ✅ 구현·실측 (식 6) | P1 설계 (미구현) | **완전 겹침 — 일반 청구 사망** |
| dual-timescale eligibility (fast tag τ 0.1–0.3s / slow capture τ 1–10s) | ✅ (식 7) | 단일 tag 설계 | 겹침 + **우리가 수입해야 할 개선** |
| wake/NREM/REM 위상 분리 (tag→capture→replay) | ✅ +67% 안정 학습 (matched norm budget) | P4 sleep 계획 (spec) | **일반 청구 사망**, 세부(시맨틱 replay)는 열림 |
| homeostasis (W decay, weakest-prune, norm budget) | ✅ | 정전 §2 "필수, 미구현" | 겹침 — 수입 대상 |
| 안정성 진단 (order parameter R, synchrony collapse 감시) | ✅ | 없음 | **우리에게 없는 것 — 수입 1순위** |
| 연상기억 readout | holographic phase-interference, 4× diffusive baseline | 1-step additive-j / Hopfield 대응 | 유사 범주, 기질 상이 |
| falsifier 문화 (timestamp-shuffle, ablation, 음수 결과 공표) | ✅ | HSWM receipts 문화 | 동일 문화 — 인용 자격 |

## 2. 피고에게 없는 것 (생존 슬롯)

| HSWM 슬롯 | Phasor 근접도 | 판정 |
|---|---|---|
| **n-ary 하이퍼그래프 credit assignment** | pairwise coupling만. 심지어 triadic term도 delay의 2차 근사로만 언급(§2.1), 학습 대상 아님 | **생존 — 문헌 전체가 pairwise** |
| **LLM 판정(semantic verdict) = 변조 신호 M** | M = scalar reward + compression-progress. 언어 판정 없음 | **생존** |
| **구조 가소성 (ADD/SPLIT/MERGE/SUPERSEDE)** | 구조 마스크 A 고정, 학습은 W뿐. topology는 학습하지 않음 | **생존 — 인접 선행은 Bayesian rewiring(Kappel–Maass)이지 Phasor가 아님** |
| **다중 agent 공유 영속 시맨틱 망 + provenance/CRDT/영수증** | 단일 agent, maze 규모, 시맨틱 내용 0 | **생존 — 범주 자체가 다름** |

## 3. 시간척도 판정 (중요한 방어)

Phasor의 eligibility는 **초 단위**(τ_f 0.1–0.3s, τ_s 1–10s) 연속 시간 역학이다. HSWM의 verdict는 **에피소드~일 단위**로 지연된다. 이 간극은 decay 상수로 못 메운다 — 그래서 정전 P1이 "wall-clock decay 금지, episode-ID 역참조 tag"를 선택한 것은 Phasor와의 차별점이자 이 regime의 필연 설계다. **시간척도 구분을 모든 후속 문서에 명시할 것.**

## 4. 청구항 판정 (격추/생존)

| # | 청구 | 판정 | 근거 |
|---|---|---|---|
| C1 | "그래프 위 three-factor plasticity" | **격추** | Phasor + e-prop + Frémaux & Gerstner. 사용 가능, 주장 불가 |
| C2 | "wake tag → sleep commit 위상 분리" | **격추** | Phasor + SRC(Tadros 2022) + Baradaran 2025 + Kubo 2025 |
| C3 | "n-ary 하이퍼엣지 credit assignment" | **생존** | §2 표. 분배 규칙(균등/Shapley)은 미개척 그대로 |
| C4 | "LLM semantic verdict = neuromodulator" | **생존** | scalar reward와 language judgment는 다른 신호 종류 |
| C5 | "topology 자체의 학습(구조 편집 승격)" | **생존** | Phasor는 mask 고정. 승격 게이트+확률 수용 조합은 미선점 |
| C6 | "다중 agent 공유 영속 시맨틱 망(CRDT+영수증)" | **생존** | 다중 agent·시맨틱·provenance 전무 |
| C7 | "엣지 학습의 에피소드 누적 영속성" | **부분 격추** | Phasor가 그래프 위 지속 가중치 학습을 이미 실증. HSWM의 것은 "영속성"이 아니라 **영속 + 공유 + 시맨틱 + 구조**의 결합 |

## 5. 흡수 목록 (USER "흡수흡수흡수" 지시에 따른 수입 후보)

1. **dual-timescale eligibility** — fast tag / slow capture 분리는 정전 P1 tag 설계의 즉시 개선.
2. **안정성 예산 + 붕괴 진단** — Phasor의 핵심 발견("sleep의 주 이득은 기억 유지가 아니라 **synchrony collapse 방지**")를 HSWM에 번역: consolidation 없는 ΔW 누적의 붕괴 시그니처 = 활성 집중도/허브 지배율/유효 랭크. HSWM판 order parameter를 P1 homeostasis와 함께 정의할 것.
3. **timestamp-shuffle falsifier** — M(판정) 타이밍이 인과적인지 검증하는 통제. P1 prereg에 편입 가치 높음.
4. **"correlation ≠ causation" 시간 필터 논증** — outcome 시점과 tag가 겹칠 때만 커밋한다는 three-factor의 정당화 논리. 우리 정전의 인용 근거로 사용.
5. **REM replay의 planning 이득(+45.5pp maze)** — P4 sleep 단계의 외부 지지 증거.
6. **정직 프레이밍** — "TGC는 새 가소성 법칙이 아니라 기존 패턴의 편의명"이라고 자기 선언한 태도. HSWM 정전이 이미 지키는 규율이며, 논문/문서 작성 시 동일 수위 유지.

## 6. 감시 사항

- Zauberzeug은 코드를 여는 회사다. 이들이 LLM agent/시맨틱 메모리로 확장하면 C4–C6가 위협받는다. repo watch 권장.
- 라이선스 확인 미실시 — 흡수(코드 수입) 전 `phasor-agents` 라이선스 확인 필요.

## 7. 정전 반영 사항

- 정전 §6의 "차별점 = n-ary 하이퍼그래프 + CRDT 수렴 + 판결 영수증"을 본 재판이 확증. 단 C1/C2/C7 사망에 따라 **"three-factor + sleep"을 HSWM 발명처럼 쓴 표현은 전 문서에서 금지** — "채택(adopted)"으로 표기.
- 정전 로드맵 변경 없음. P1에 §5-1(dual trace)·§5-2(안정성 진단)·§5-3(shuffle 통제) 편입을 권고(정전 개정은 USER ratify 대상).

## 8. provenance

- 1차 소스: [arXiv:2601.04362](https://arxiv.org/abs/2601.04362) abstract + [HTML v1 full text](https://arxiv.org/html/2601.04362v1) (§1–§4 직독, methods/plasticity/sleep 전량).
- 방어 근거: `CANON_DIRECTION_NEURAL_COGNITIVE_ENTITY_2026-07-23.md`, `PROM_HSWM_PLASTICITY_WEIGHT_TOPOLOGY_LEARNING_2026-07-23.md`.
- layer: SECONDARY_AI (재판 결과의 정전 반영은 USER ratify 대상).
