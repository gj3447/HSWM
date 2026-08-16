# PROM 16 REPORT — HSWM 4대 미증명 claim 증명/반증 공격 계획 (2026-07-25)

> cycle: `prom16-hswm-unproven-claims-20260725` | N=16 (4 claim × 4 lens: theory/benchmarks/pitfalls/alternatives)
> Lesson: `lesson-prom16-hswm-unproven-claims-20260725` | ResearchFinding 16/16 written (PromBatchWrite verified=true)
> axis-split: `PROM_16_UNPROVEN_A_DELTA_W_CREDIT_2026-07-25.md` / `B_AGENT_AB_TRANSFER_` / `C_TOPOLOGY_LEARNING_` / `D_CONSOLIDATION_` | raw: `_findings/prom16-hswm-unproven-claims-20260725/`

## 문제

게이트 영수증의 claim boundary가 명시적으로 보류한 4개 — ① 결과→신용배분→ΔW 학습 ② Agent A→frozen-B 전이 ③ 학습된 topology rewiring ④ 장기 consolidation — 을 각각 측정/증명/반증하는 실험 프로토콜이 없다. 현재 증거는 L0 answer-interface actuation(p1v4)에 한정되고, C1 book-scale은 hypergraph-native 우위를 반증했다.

## 0. 사전 지식 (KG pre-fetch)

- 성립: p1v4 L0 typed actuation (heldout 6/6 vs 2/6, 서버 replay) — narrow claim뿐.
- 반증: C1 (clique 0.447 > hswm 0.427, novel kill), B21 router-only 0/54, p1v2 typed lesson KILL (base retrieval 포화), d1 additive-j r2 degenerating.
- 기존 findings: `rf-prom-next-move-*-20260724` 3건 (F1/B22 서열), `lesson-prom-tribunal-phasor-20260724`. 4 claim 정면 리서치는 이번이 처음.
- 미해결 foundation 2건: `multi-agent-transfer-harness`, `semantic-weight-metric-contract` — F3/추정기 선택에 직접 블로커.

## 1. Consensus

- **C1 (16/16): 유일한 증명 경로 = multi-arm sealed factorial + prereg kill 조건.** claim별: ① 3-arm(credit-informed / 동일크기 random edit / verbal-gradient) + credit-validation ρ≥0.2 ② 5-arm(무경험/full packet/placebo lesson/raw-log/성분분해) + self-lesson 대조 G·오류구조 서명 S ③ W-동결 4-arm(학습/셔플/clique/랜덤) + edge ablation 인과곡선 + 구조-성능 상관 ④ 3-arm longitudinal forgetting curve + decay slope·schema-generalization 서명.
- **C2 (8+): 강한 null/placebo 대조가 결정적 변수.** naive/random 대조가 자주 이긴다 — naive 기억 전이 −1.6~−8.6pt (B2), 구조학습이 random/static 대조에 패배 (C2), random-edit control (A1), append-only control (D4). C1 clique kill의 일반화: "약한 대조로 얻은 +는 증거가 아니다."
- **C3 (pitfalls 4/4 + alternatives 4/4): 오탐 차단 공통 4-게이트** — freeze ablation (actuation↔learning 분리), headroom band 30~70% (p1v2형 포화 방지), 이종 judge (순환성 차단), leakage/channel 감사 (canary lesson, disjoint corpus, 문체 누출).
- **C4 (A1+A4): ΔW 관측성은 이미 해결됨** — version-hash + typed edit log + content-addressed store로 ΔW는 replay 가능한 1급 변수. 진짜 미증명은 **신용 추정치의 예측력**(추정 φ가 실측 LOO와 순위상관하는가).

## 2. Divergence

- 명시적 충돌 0건 (G4 pass). 유일한 설계 긴장: **신용 추정기 선택** — Shapley/LOO(검증독립, 비용高) vs 포함마스크 REINFORCE(불편, 분산高) vs verbal-gradient TextGrad/GEPA(분산低, 검증의존). 해소 경로: credit-validation gate로 3자를 planted testbed에서 대조 (→ EXPLORATION 씨앗).

## 3. Open Questions / singleton 발견

- **LOLO(leave-one-lesson-out) 개별 레슨 인과 신용 metric은 문헌 공백** (A2) — 선행은 전부 knockout ablation 수준. HSWM typed store의 content-addressing으로 결정론 계산이 가능하면 관행 상한을 넘는 고유 기여 (→ VERIFY 씨앗).
- API black-box는 input-channel뿐 (B1) — logit/activation 채널 전이는 로컬 가중치 모델로 옮길 때만 검증 가능.
- consolidation은 "반증됨"이 아니라 "측정 불가" 상태 (D1) — GEM BWT/FWT + gist-detail 분기로 측정 가능 형태로 내리는 것이 선행.
- 각 claim의 kill 조건이 C1 clique kill의 후속판과 1:1 대응 (C4): K1 대조군 추격 실패, K2 평탄 인과곡선, K3 구조-성능 무상관.

## 4. 권장 후속 작업 (ActionPlan, KG 등록 완료)

1. **ACTION** `plan-hswm4-prereg-f2-f5-20260725` — PREREG F2~F5 통합 사전등록 문서 (1일). 선행: F1 parity 수리 + foundation `semantic-weight-metric-contract` ratify/waiver.
2. **ACTION** `plan-hswm4-null-battery-harness-20260725` — null battery + confound audit 공용 하네스 (1~2일): placebo store / random edit / canary lesson / disjoint corpus audit / headroom band.
3. **FUTURE** `plan-hswm4-f2-deltaw-first-20260725` — 실행 순서 F2(최저비용, p1v4 재사용) → F3(모델 2개, transfer-harness foundation 의존) → F4(C1 후속) → F5(longitudinal, 수주).

## 씨앗 (Step 4.7, KG READY)

- `seed-rf-hswm4-unified-sealed-protocol-20260725` (HIGH/consensus)
- `seed-rf-hswm4-null-battery-confound-audit-20260725` (HIGH/consensus)
- `seed-conflict-hswm4-credit-estimator-choice-20260725` (EXPLORATION)
- `seed-verify-hswm4-lolo-metric-20260725` (VERIFY)

> 나생문 적대검증은 정전(`naesengmoon-prom-decoupled-2026-05-30`)에 따라 자동 dispatch하지 않음 — 사용자 명시 요청 시.
