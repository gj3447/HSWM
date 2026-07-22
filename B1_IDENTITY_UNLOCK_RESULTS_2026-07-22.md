# B1 identity-material unlock — T0 결과 (2026-07-22)

> **판정**: metric **`progressive`** (preregistered 예측 2개 모두 적중) / 프로그램 레벨 Lakatos `degenerating` (BF 0.167 — 누적 RED 이력 하중, ML18과 동일 이중 판정 패턴). receipt fold `ok=true`.
> **노드**: `LakatosTree_PromSearchHSWM_20260721 / B1-identity-material-unlock-t0` (예측 receipt `3373440d…`).
> **한 줄**: H3-C0이 진단한 "legal 2-edge chain 0 = identity material 결핍"이 **정확히 맞았다** — 결정론 weave만으로 MuSiQue 0→**6**, 2Wiki 0→**25** chain 해금. LLM/network/embedding 호출 0.

## 사전등록 (PREREG_B1_IDENTITY_UNLOCK_2026-07-22.json, 실행 전 동결)

- primary: `min_over_datasets_c3_admissible_depth2_chains` ≥ 1 (baseline 0) → **6** ✓
- novel: `sum_c3_minus_c1` > 0 (C1 counterfactual은 H3-C0에 이미 공표라 novel 지위 없음) → **+23** ✓
- credence 0.5 · kill 5종 전부 미발동 (가역성 비트동일 PASS, receipt 완비, 예산규율 PASS)

## 실측

| arm | MuSiQue chains | 2Wiki chains | 내용 |
|---|---:|---:|---|
| C0 frozen | 0 | 0 | H3-C0 재확인 |
| C1 +title-subject | 0 | 8 | 공표 counterfactual과 정합 (15 structural → T0 bounds 후 8) |
| C2 +canonical entity | (receipts) | (receipts) | parenthetical-strip title anchor, homonym anchor 드롭 |
| **C3 = C1+C2+handoff** | **6** | **25** | **MuSiQue는 C2/C3 material만으로 해금** — canonical identity가 병목이었다는 직접 증거 |

- 구현: `chain_viability.py` (T0 원장, 커널 admission 미러, 7 tests) + `claim_weave.py` (weave 3종, 전 arc 가역 receipt, strip=비트동일 복원, 7 tests) + `b1_identity_unlock.py` (prereg guard + 하니스).
- 영수증: `EVIDENCE_B1_IDENTITY_UNLOCK_2026-07-22.json` (sha `3a81bfff…`) + 전체 chain/weave receipt = `RECEIPTS_B1_IDENTITY_UNLOCK_2026-07-22.json`.

## 정직 경계

1. **T0 = 구조 생존성이지 검색 효능이 아니다.** T1(seed 도달)–T3(K2 score 변화+null) 및 recall 주장은 별도 prereg 필요 — 이 문서는 그 어떤 효능도 주장하지 않는다.
2. 결정론 sub-lane만 구현 (exact/normalized surface + title anchor). ReFinED-QID/fastcoref ML lane 미구현 — H3-C0 권고의 C2/C3 full lane이 아님.
3. 프로그램 레벨 degenerating은 유효한 경고: 구조 카운트 하나로 프로그램이 살아나지 않는다. 다음 rung(T1–T3)이 죽으면 이 unlock은 공회전이 된다.
4. Phase B 함의 (설계 §4.2): 이 unlock은 field-level merge의 seam binding과 같은 메커니즘 — B2 cross-field 실험의 seam 재료가 검증됨. 단 "같은 메커니즘"은 AI 해석 (SECONDARY_AI).

## 다음

- **T1–T3 rung**: frozen certificate seed가 chain 입구에 도달하는가 → 별도 prereg (embedding은 frozen npz 재사용, 신규 spend 0).
- **ML lane**: ReFinED/fastcoref receipt로 C2/C3 확장 — 결정론 lane이 6/25를 열었으니 상한 추정 가능.
- **B2 (federated merge)**: seam binding 재료 검증 완료 → cross-field merge payoff prereg 가능.
