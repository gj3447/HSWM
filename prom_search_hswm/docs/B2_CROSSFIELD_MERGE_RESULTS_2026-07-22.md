# B2 cross-field merge payoff — 결과 (2026-07-22)

> **판정**: LakatoTree **`progressive`** — 프로그램(`LakatosTree_PromSearchHSWM_20260721`) 첫 완전 progressive, eureka seam **true** (BF 6.0, hallucinated=false). receipt fold `ok=true`. 노드 `B2-crossfield-merge-payoff` (예측 receipt `ba0c3718…`).
> **단 복합 conjecture 원문은 불성립**: L5 no-harm이 위반돼 lemma_incorporation으로 편입 — "merge는 cross-field에서 크게 이기지만 in-field에 측정된 비용을 낸다"로 주장 축소. USER 정전 "여러 HSWM 연결로 큰 망"의 **첫 실측 긍정 증거이자 첫 실측 비용**.

## 실측 (2Wiki n_q=400, title-parity 2필드, seam arc 2,355개, prereg 동결 후 실행)

| falsifier | delta | bootstrap95 | 판정 |
|---|---:|---|---|
| **F-B2a** cross-field: merged − best_single | **+0.2137** | [+0.183, +0.244] | ✅ 확증 (noise band 0.02의 10배) |
| **F-B2c** seam ablation: merged − no_seam | **+0.0342** | [+0.017, +0.052] | ✅ seam이 이득 일부를 실제 담지 |
| **F-B2b** in-field no-harm (L5) | **−0.0648** | [−0.092, −0.041] | ❌ **위반** (허용 −0.02 초과) |

클래스별 recall@10: cross-field에선 merged 0.688 vs best-single 0.474 (거대) / in-field에선 merged 0.758 vs best-single 0.822 (간섭 비용).

## 해석

1. **망의 존재 이유 확증**: gold가 두 field에 걸친 질의(234/400)에서 단일 field로는 구조적으로 불가능한 회수를 merge가 해냄 — field-of-fields의 최초 정량 증거. seam ablation이 유의(+0.034)라 "연결" 메커니즘 자체가 담지자임도 확인 (단 이득 대부분은 union 자체에서 옴 — no_seam도 0.654).
2. **공짜가 아니다 (L5 위반)**: 자기 field 안에서 답이 끝나는 질의는 merge된 큰 場에서 오히려 −6.5pt 손해 — ML15 "노이즈 다리" 간섭의 field-level 재현. **다음 frontier = 간섭 통제** (질의별 field 라우팅/gating — 단 P5가 cheap fixed routing을 죽였으므로 learned/certified gate 필요, `Q-learned-gate-privateid-hardhop`과 합류).
3. T1 RED(같은 날)와의 대비: fact-level 결정론 weave는 죽고(seed 도달 불가) field-level merge는 살았다 — Phase B의 살길이 kernel-순회가 아니라 **field 합성 쪽**임을 가리킴. (AI 해석, SECONDARY_AI.)
4. ML8/ML10 방어 통과: coverage-artifact가 아니라 paired bootstrap + no-harm 동시 측정 프로토콜에서 나온 숫자.

## 산출물

- 하니스: `prom_b2_crossfield_merge.py` (subagent 빌드, parent 재검증 18 tests) + `test_hswm_b2_crossfield.py`
- 사전등록: `evidence/PREREG_b2_crossfield_merge_20260722.json` (실행 전 커밋 8e0bfa7)
- 영수증: `evidence/EVIDENCE_b2_crossfield_merge_20260722.json` (sha `125cd7ff…`)
- B0 대수 재사용: `hswm_field_algebra.py` merge/compose/SeamArc — field_id 4종 전부 영수증에 앵커

## 다음

- **B2.1 간섭 통제**: merged 큰 場 + in-field 질의 손해 복구 (learned gate / certified per-query field 선택). L5 회복이 망 배포의 관문.
- **B2.2 외부 타당도**: 2번째 벤치 + seed sweep (prereg scope에 명시 유보).
- **B3**: continual topology 흡수 재도전은 T1 RED 이후 ML lane 선결.

## 부록: R4 oracle headroom 진단 (2026-07-22, DIAGNOSTIC_NO_CLAIM)

`b2_oracle_headroom.py` — 판정 하니스 무수정, 동일 seed 결정론 재계산. 영수증 `evidence/DIAG_b2_oracle_headroom_20260722.json`.

1. **merge는 결함이 아니다 — 완벽 게이트는 L5를 전액 복구**: oracle(질의별 최적 route)은 in-field 0.822(=best_single 그대로, −6.5pt 전액 회복) + cross-field 0.697(merged 0.688보다 오히려 +0.009). 게이트 방향 생존 확정.
2. **결정 구조가 극도로 유리**: in-field에서 merged가 이기는 질의 **0/166** (single 23승, tie 143) / cross-field에선 merged 123승 vs single 7승. 즉 게이트는 질의별 승자가 아니라 **"이 질의 gold가 두 場에 걸치나"(class)만 맞히면 사실상 oracle 도달**.
3. **단 값싼 신호 2종은 사망**: top-1 기반 affinity-margin AUC 0.538 / top1-gap AUC 0.571 — A4 kill 기준(0.75) 크게 미달. A안(무학습)의 crude 신호는 기각. 남은 순서 = ReDDE/CORI식 top-k 분포 affinity 1회 시도 → 미달 시 **B안(train-only 학습형 + Mondrian conformal, leave-field-out 전이 증명)** 직행.
