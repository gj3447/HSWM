# P6 — Continual Absorption FSM (Phase A: semantic KV residual) 재판 (2026-07-22)

> **USER_PRIMARY (2026-07-22)**: "hswm 은 고정된게 아니라 흡수흡수흡수 하면서 성능을 발전시켜야해 구조나 fsm 을 개선시키면서"
> **판정**: metric `equivalent` / Lakatos **`degenerating`** — 노드 `P6-continual-absorption-fsm-unseen-r2`, receipt fold `ok=true` (rederived=degenerating).
> **한 줄**: 의미 key-value residual 흡수(Phase A)는 unseen 질의에 전이 안 됨 — 3라운드 전부 fresh validation에서 **오히려 해침** → FSM 승격 게이트가 전부 기각 → sealed Δ=0. **FSM 가드레일 자체는 설계대로 작동** (손해를 한 번도 안 실음).

## 1. 설계 (사전등록 `PREREG_p6_continual_absorption_fsm_20260722.json`)

- **conjecture**: 불변 후보 3세대의 FSM-gated 흡수가 frozen equal-budget HSWM readout 대비 sealed unseen 2Wiki recall@10을 **+0.03** 이상 개선 (credence 0.35).
- **anti-memorization**: exact normalized query overlap 0 강제, query-ID feature 금지, exact-ID cache는 진단 전용, unseen-document 층화.
- **승격 게이트(라운드당)**: fresh unseen epoch gain ≥ +0.01 AND bootstrap95 하한 > 0 AND retention ≥ −0.01 AND canary full-chain ≥ −0.01 AND replay 검증 AND equal budget.
- 2Wiki n=900 결정론 분할: train 3×120 / validation 3×120 / **sealed holdout 180**. FSM 명세 4종(`fsm/`) + reducer(`hswm_absorption_fsm.py`, 단위테스트 10/10) sha 동결.

## 2. Amendment (정직 기록)

원 등록 스크립트(sha `bc601704…`)는 `compact_metric`의 int/iterable TypeError로 **어떤 지표도 방출하기 전에 결정론적으로 크래시** — 관측된 결과 0인 상태에서 표현-전용 타입 처리만 수정(sha `43055692…`). 원 태그의 예측은 도달 불가(서버 409 재등록 금지)라 **자식 노드 `-r2`에 동일 예측을 재등록**(파라미터·분할·시드·임계값·FSM 아티팩트 전부 무변경). 전문 = PREREG `amendments[0]` + `judgments/P6_continual_absorption_fsm/register-*-r2.json`.

## 3. 실측 (`EVIDENCE_p6_continual_absorption_fsm_20260722.json`, sha `8d73635e…`)

| round | fresh Δrecall@10 | bootstrap95 | Δfull-chain@20 | FSM 종착 | 승격 |
|---|---|---|---|---|---|
| 1 | **−0.0604** | [−0.0938, −0.0292] | −0.0167 | rejected | ✗ |
| 2 | −0.0188 | [−0.0417, +0.0063] | −0.0250 | rejected | ✗ |
| 3 | **−0.0583** | [−0.0875, −0.0333] | −0.0417 | rejected | ✗ |

- **sealed holdout (n=180)**: active=frozen 동일 → Δrecall@10 **0.0** (CI [0,0]), Δfull-chain 0.0. control recall@10 0.7167.
- **novel** (joint_promotion_and_final_gain_margin) = **−1.0** — 승격 0건.
- **exact-ID cache 진단**: 저장 ID에선 recall 1.0이지만 sealed unseen에선 frozen과 완전 동일(Δ0) — "암기 이득 ≠ 전이 학습" 통제 확인.
- kill condition #1 발동: "No candidate passes a fresh unseen-query promotion gate."

## 4. 해석 (exception-barring, local_and_global)

- **폐기되는 것**: Phase A — *의미 연상 residual(semantic key-value memory)을 흡수하면 unseen 성능이 오른다*. 전이는커녕 fresh 질의를 유의하게 해침(R1/R3 CI 완전 음수). 흡수 주장은 "의미 residual 경유"가 아닌 것으로 축소.
- **건드리지 않는 것**: HSWM substrate hard core (n-ary 하이퍼그래프, semantic=SEED/structure=EDGE). USER의 흡수 직관 원문은 "**구조나 fsm 을 개선시키면서**" — Phase A는 구조(topology)를 아예 안 건드렸다. 진짜 시험대는 **Phase B: n-ary ADD/SPLIT/MERGE/SUPERSEDE topology 흡수** (사전등록 scope_boundary에 명시적 deferred).
- **살아남은 공학 가치**: FSM 승격 게이트 — 해로운 후보 3개를 전부 차단하고 retention·canary 무손상 유지. ML18의 solidity 축과 같은 결(성능 아닌 안전 축). immutable candidate + CAS receipt 규율도 그대로 재사용 가능.
- **eureka seam**: felt=true / true=false / **hallucinated=true** (novel 미확증 + BF 0.584) — 서버가 공회전으로 정확히 분류.

## 5. 다음 frontier (next_directions readback)

1. `Q-continual-absorption-fsm-unseen` (priority 0.72, 2 visits) — **재도전은 메커니즘을 바꿔야만** (Phase B topology 흡수). Phase A 재실행은 무의미.
2. `Q-learned-gate-privateid-hardhop` (0.58, 미방문) — P5가 열어둔 learned specialist gate.
3. 판관 캘리브레이션 주의: issuer ECE 0.2559 (과신 표면화).

## 6. 산출물

- 영수증: `prom_search_hswm/evidence/EVIDENCE_p6_continual_absorption_fsm_20260722.json`
- 사전등록(+amendment): `prom_search_hswm/evidence/PREREG_p6_continual_absorption_fsm_20260722.json`
- 판정 패킷 11파일: `prom_search_hswm/judgments/P6_continual_absorption_fsm/`
- FSM: `prom_search_hswm/hswm_absorption_fsm.py` + `fsm/` 명세 4종 + 테스트 10/10
- receipt chain: prediction `047823fa…` → verdict `8c4d85db…` (fold 검증 ok)
