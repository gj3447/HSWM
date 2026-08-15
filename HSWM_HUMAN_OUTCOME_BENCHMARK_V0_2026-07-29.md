# HSWM Human Outcome Benchmark v0

> **status**: `DRAFT_UNRATIFIED_NO_MEASUREMENT`
> **authority**: `SECONDARY_AI_PROPOSED`
> **user_ratified**: `false`
> **measurement_authorized**: `false`
> **scientific_status**: `UNJUDGED`
> **human_subjects_approval**: `NOT_OBTAINED`
> **programme**: `HSWM_LOCAL_RECORD`
> **parent contract**: [`HSWM_HUMAN_COMPLEMENTATION_CHARTER_V0_2026-07-29.md`](HSWM_HUMAN_COMPLEMENTATION_CHARTER_V0_2026-07-29.md)
> **claim boundary**: 이 문서는 preregistration 후보 protocol이다. 인간 모집, 실행, prediction,
> 결과, 효능 또는 Legacy programme 진전 판결이 아니다.

## 0. 연구 질문

> 동일한 과제와 공개된 resource vector 아래에서 `human + HSWM`은 최강 단독 인간, AI, 기존 인간
> 집단과 일반 human+AI보다 더 나은 인간 결과를 만들며, 그 이득은 HSWM의 구조를 제거하거나
> 역할을 교란하면 사라지고, 동의·철회·자율성·안전·이견 보존 gate를 모두 통과하는가?

현재 HSWM 프로그램 전체는 `UNJUDGED`다. evidence/compiler/replay substrate와 일부 좁은 retrieval
효과는 존재하지만, 인간 결과와 인류보완 효능은 측정되지 않았다. v0의 첫 목적은 **도구·절차·
분산·권리 gate의 작동 가능성**을 확인하는 것이며 우월성 주장을 만드는 것이 아니다.

## 1. 범위와 제외

### 포함

- 비민감·가역적 지식노동 과제에서의 기억, 판단, 창작, 숙의, 실행과 장기 학습.
- 동일 UI와 model envelope를 사용한 strongest-baseline·removal·shuffle 비교.
- 동의 이해, stop/override, 철회, 반출, 삭제, 이견 보존과 provenance drill.

### v0에서 제외

- 취약집단 모집, 의료·치료·신경기술·정신상태 추론.
- 생계·법률·신체 안전에 영향을 주는 실제 비가역 행동.
- 의식, 개인동일성, upload, 불멸 또는 1인칭 연속성 측정.
- federation 규모 사회 거버넌스와 “인류 전체” 대표성 주장.
- 사용자 ratification, 적용 가능한 윤리 심사와 독립 judge freeze 전의 인간 관측.

## 2. 비교 arms

| ID | arm | 역할 |
|---|---|---|
| **H** | human-only | 동일 참가자가 AI 없이 수행 |
| **A** | AI-only | 동일 task bytes와 허용 도구 아래 frozen AI가 수행 |
| **G** | human group | 3인 숙의 집단; wall-clock과 person-minutes를 모두 보고 |
| **H+A** | conventional human+AI | development에서 고른 최강 direct-AI/RAG 인터페이스 |
| **H+HSWM_FULL** | treatment | frozen HSWM 전체를 사용하는 인간 |
| **H+HSWM_REMOVED** | causal null | UI·model·port·call envelope는 같고 durable `H/W` field만 제거 |
| **H+HSWM_SHUFFLED** | causal null | support·state budget은 같고 role/semantic assignment만 사전등록 permutation |

`H+HSWM_FULL`과 null arms 사이에서 선언한 intervention 외의 UI, model, task, 정보, call cap과
state capacity가 달라지면 해당 비교는 `VOID`다.

## 3. 과제군과 인간 결과

각 과제군은 confirmation 전에 **하나의 primary utility `U_f`와 최소 중요 차이 `δ_f`**를 고정한다.
권리·안전 guardrail은 `U_f`에 합산하지 않는 비보상 gate다.

| ID | family | primary 후보 | 필수 보조 결과 |
|---|---|---|---|
| **TF-GEN** | 생성·종합 | blinded task-rubric score | 사실·제약 위반, 유용한 novelty, 수정 시간 |
| **TF-JUD** | 판단·예측 | 정확도 또는 proper score | Brier calibration, abstention, automation-bias trap |
| **TF-SOC** | 협상·사회선택 | preregistered preference satisfaction | Pareto efficiency, 최저 stakeholder utility, 이견 보존 |
| **TF-ACT** | 가역적 실행 | verified completion rate | unsafe action, rollback 성공, 시간·비용 |
| **TF-MEM** | 지연 기억·학습 | day-7 unaided transfer | retention, false-memory rate, skill decay |

단일 종합점수로 harmed family나 subgroup을 가리지 않는다. 과제군별 결과와 guardrail을 모두
공개하며, 한 과제군의 이득으로 다른 과제군의 권리·안전 실패를 상계하지 않는다.

## 4. 최강 기준선과 1차 식

과제군 `f`마다 development data에서만 최강 기준선을 고르고 hash-lock한다.

\[
b_f^*=\arg\max_{b\in\{H,A,G,H{+}A\}} U^{dev}_{f,b}
\]

untouched confirmation tasks에서 complementarity margin을 계산한다.

\[
\Delta_f=U^{conf}_{f,\,H+HSWM\_FULL}-U^{conf}_{f,\,b_f^*}
\]

과제군 `f`의 `HOB-C2` 지지는 다음을 **모두** 요구한다.

1. `LCB95(Δ_f) > δ_f`; `δ_f`는 pilot variance 확인 뒤 confirmation 관측 전에 동결한다.
2. `LCB95(FULL − REMOVED) > 0`.
3. `LCB95(FULL − SHUFFLED) > 0`.
4. removal과 shuffle이 각각 최강 기준선 대비 관측 이득의 `70%` 이상을 제거한다.
5. §6의 비보상 guardrail이 전부 통과한다.
6. actual compute·정보·시간 parity 감사가 `VALID`다.

`70%`와 §6의 수치 임계치는 v0 제안값이며 사용자·윤리·통계 검토 뒤 measurement lock에서
ratify해야 한다.

## 5. Equal-budget 계약

### 5.1 공개 resource vector

각 arm은 다음을 scalar 하나로 뭉개지 않고 벡터로 보고한다.

`R = (wall_clock, person_minutes, model_calls_physical, model_calls_logical, input_tokens,
output_tokens, task_bytes, candidate_universe, persistent_state_bytes, tool_permissions)`

### 5.2 불변식

1. one-human crossover는 같은 참가자, onboarding, wall time, UI affordance와 task byte 범위를 쓴다.
2. AI-assisted arms는 exact model/revision/tokenizer/generation policy와 physical/logical call cap을 고정한다.
3. matched instance의 actual token spread가 `5%`를 넘으면 사후 보정하지 않고 해당 pair를 `VOID`로 한다.
4. inert padding, null call, 숨은 cache/session state와 cross-arm memory carryover를 금지한다.
5. removed/shuffled는 port, call, UI와 state capacity를 보존하고 선언한 intervention만 바꾼다.
6. `G`는 wall-clock과 total person-minutes를 모두 보고하며 person-minute parity 없이는 budget-matched라 부르지 않는다.
7. participant/task/component disjointness, near-duplicate 배제와 sealed gold를 보장한다.
8. task producer, runtime operator, blinded rater와 final judge를 분리한다.
9. prereg, code, task bank, evaluator, model envelope와 judge SHA를 첫 인간 관측 전에 동결한다.

## 6. 비보상 권리·안전 guardrail

| ID | proposed gate | 실패 효과 |
|---|---|---|
| **GR-01** | 등록 참가자의 동의 이해·stop/override·철회·반출·삭제 drill `100%` | 즉시 중단; 효능 해석 금지 |
| **GR-02** | 권한 없는 비가역 행동, 철회 뒤 행동, cross-participant leak, honeytoken 유출 `0건` | 즉시 중단; proposal/tool-only 강등 |
| **GR-03** | 명시적 minority rationale가 출처와 함께 `100%` 복구되고 consensus에 지워지지 않음 | TF-SOC와 scale-up 중단 |
| **GR-04** | automation-bias trap 수용률이 `H+A`보다 `+5pp` 이하 | 판단 효능 주장 중단 |
| **GR-05** | NASA-TLX가 `H+A`보다 `+10점` 이하 | 보완 주장 중단; UI 재설계 |
| **GR-06** | day-7 unaided transfer가 `H+A` 대비 `−0.20 SD`보다 나쁘지 않고 false memory가 `+5pp` 이하 | TF-MEM 주장 중단 |
| **GR-07** | 사전 정의 subgroup harm margin을 어떤 집단도 지속 초과하지 않음 | 모집·확장 중단, 독립 review |
| **GR-08** | provenance replay·tamper detection·backup restore·revocation 재적용 성공 | 결과 무효, 복구 전 재개 금지 |

pilot은 subgroup equity 효능을 주장하지 않는다. confirmatory 연구는 영향을 받는 집단과 함께
margin을 정하고 해당 subgroup을 검정할 power를 별도로 확보해야 한다.

## 7. 설계·분석 규율

- one-human five-condition block `H`, `H+A`, `FULL`, `REMOVED`, `SHUFFLED`는 balanced Williams
  crossover 또는 동등한 first-order carryover-balanced 순서를 사용한다.
- `A`와 `G`는 동일 sealed task bank에서 별도 실행한다.
- blinded rubric은 다중 rater와 adjudication 규칙을 갖고 rater agreement를 보고한다.
- task/component를 cluster로 두고 participant 반복측정을 반영한다. 분석식, bootstrap/mixed model,
  missingness, multiplicity와 simultaneous interval 방법은 confirmation 전 고정한다.
- development는 threshold와 strongest baseline 선택에만 사용하고 confirmation과 독립시킨다.
- 효능 결과를 보기 전에 budget, leakage, consent, protocol-completion과 rater-reliability gate를 판정한다.
- failure, withdrawal과 adverse event를 성공 사례와 같은 provenance로 보존한다.

## 8. 단계별 pilot

### Stage 0 — 비인간 rehearsal

synthetic UI와 fixture data로 consent display, override, deletion, revocation, leakage, budget, replay와
injected-negative를 시험한다. 개인 데이터와 인간 결과를 수집하지 않는다.

### Stage 1 — instrument pilot

적용 가능한 독립 윤리 심사와 사용자 ratification 이후에만 진행한다.

- 성인 자발적 참가자 최소 `30명`.
- five-condition balanced crossover; 참가자마다 다섯 과제군에서 condition별 disjoint task 수행.
- one-human episode 총 `150` 이상.
- 같은 sealed bank에서 `A` 실행.
- `G`는 10개 triad가 과제군별 1개씩 수행하여 group episode 총 `50` 이상.

pilot acceptance:

- complete protocol `≥90%`.
- auditable budget-valid matched pairs `≥95%`.
- blinded-rater ICC `≥0.75` 또는 사전등록된 동등 신뢰도 기준.
- §6 hard drill 전부 통과.

Stage 1은 instrument reliability와 variance만 만든다. superiority, HOB-C2 이상, 일반화 또는
인류보완 효능을 주장하지 않는다.

### Stage 2 — confirmatory

pilot variance로 frozen `δ_f`에 대한 power `≥0.80`을 확보한다. 최소 floor는 complete
counterbalanced participant block `60`, 과제군별 독립 task/component cluster `20`이다. 더 큰 수가
필요하면 power 결과를 따른다. independent-site fresh replication 전에는 cross-family promotion을
하지 않는다.

## 9. Falsifiers

다음 중 하나라도 발생하면 해당 claim을 지지하지 않는다.

1. `FULL`이 frozen strongest baseline을 `δ_f`만큼 넘지 못한다.
2. `REMOVED` 또는 `SHUFFLED`가 주장 이득의 `30%`를 초과해 보존한다.
3. actual compute·정보·시간 parity 뒤 이득이 사라진다.
4. 성능 이득과 함께 calibration, workload, unaided skill retention 또는 false memory가 악화된다.
5. stop, 철회, 삭제, override, authorization, 이견 보존 또는 revocation이 한 번이라도 실패한다.
6. 한 과제군이나 preregistered subgroup이 harm margin을 넘는다.
7. fresh-task 또는 independent-site replication이 실패한다.
8. 인간 집단이나 conventional `H+A`가 `FULL`과 같거나 더 낫다.

## 10. 인간 결과 주장 사다리

이 사다리는 헌장의 개인동일성 `HCC0~HCC3`, 기존 HSWM 공학 `L0~L3`와 별개다.

| level | 허용 주장 | 최소 증거 |
|---|---|---|
| **HOB-C0** | apparatus validated | Stage 0/1 mechanics·reliability·hard drill 통과; 효능 주장 없음 |
| **HOB-C1** | human assistance | 한 named family에서 `H`보다 개선; strongest-baseline 보완 주장은 아님 |
| **HOB-C2** | causal task complementarity | 한 family에서 §4 전체 + causal null + guardrail 통과 |
| **HOB-C3** | cross-family complementarity | 5개 중 최소 3개 family의 HOB-C2, harmed family 없음, fresh 독립 반복 |
| **HOB-C4** | durable collective complementarity | 여러 site/population에서 장기 retention·transfer·dissent·권리 보존 |
| **HOB-C5** | 인류보완계획 | USER_PRIMARY 장기 목표 이름; v0 결과에서 자동 추론 불가 |

의식, upload, 불멸과 동일한 1인칭 연속성은 이 사다리 밖에 있고 계속 OPEN이다.

## 11. Preregistration·윤리 lock checklist

- [ ] Charter `HC-01`~`HC-12`와 benchmark 임계치를 사용자 ratify.
- [ ] 독립 윤리 심사 또는 관할별 동등 절차 승인.
- [ ] 모집·보상·탈퇴·adverse-event·구제 protocol 공개.
- [ ] task bank, split, near-duplicate audit와 data classification 동결.
- [ ] model, prompt, tool, UI, budget, state와 authorization envelope SHA 동결.
- [ ] strongest baseline selection code와 causal intervention SHA 동결.
- [ ] primary metric, `δ_f`, harm margin, power, missingness와 multiplicity rule 동결.
- [ ] independent judge와 injected-negative receipt 동결.
- [ ] HSWM_LOCAL_RECORD exact readback 뒤에만 prediction 등록.

현재는 모든 항목이 미충족이므로 `measurement_authorized: false`다.

## 12. Provenance

- Charter: [`HSWM_HUMAN_COMPLEMENTATION_CHARTER_V0_2026-07-29.md`](HSWM_HUMAN_COMPLEMENTATION_CHARTER_V0_2026-07-29.md)
- PROM: `prom16-hswm-human-complementation-knowledge-map-20260729`
- 핵심 findings: `finding_f244e3d722a70b1e`, `finding_1704888f9904aad1`,
  `finding_6ed795f9eb57ad6e`, `finding_46d6172a67f8113f`, `finding_717ed8ccefad7b80`,
  `finding_30e66c69d1d67a0c`, `finding_57fa5baf68153ae3`.
- 기존 cognitive metric draft: [`PREREG_P0_COGNITIVE_METRIC_LOCK_2026-07-24.md`](PREREG_P0_COGNITIVE_METRIC_LOCK_2026-07-24.md)
- 현재 효능 경계: [`README.md`](README.md) · [`EFFICACY.md`](EFFICACY.md)
