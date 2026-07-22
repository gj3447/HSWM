# T3 결과 — K2 mechanism 확증 + null 완벽 사멸 + R1/R2 관대집계 정정 (2026-07-23)

> **판정**: metric **`progressive`** (예측 2/2) / 프로그램 Lakatos `degenerating` (BF 하중, 동일 이중판정). receipt fold `ok=true`. 노드 `T3-score-digest-null` (예측 receipt `47fffa24…`).
> **한 줄**: A5(ML-woven) 그래프에서 K2가 K1 score digest를 실제로 바꾸고(양 데이터셋), **연속성-파괴 null에서 변화가 0으로 완전 소멸** — 걷기의 이득이 진짜 claim 연속을 타고 흐른다는 mechanism 확증. H3-C0 waterfall (T0→T1→T2→T3) 전 rung 완주.

## 실측 (strict kernel-canonical continuity, n=200/dataset)

| | digest 변화 (real) | digest 변화 (null) | strict d2 | lenient d2 (구 워커) |
|---|---:|---:|---:|---:|
| 2Wiki | **2** | **0** | 3 | 6 |
| MuSiQue | **1** | **0** | 2 | 3 |

- primary min = 1 ≥ 1 ✓ / novel real−null = +3 > 0 ✓ / **null 완전 사멸(0/0)** — 점수 변화의 담지자가 claim 연속성임을 부정 대조로 입증.
- kill 조건 3종 전부 미발동.

## 자기감사 결과 — R1/R2 정정 (self_audit_commitment 이행)

R1/R2 워커의 hop-2에는 **lenient fallback**(연속 arc 부재 시 임의 outgoing arc 허용)이 있었고, 이는 커널 정본이 아니다. strict 재감사:

- **R2의 핵심 주장(min depth-2 > 0)은 생존** — strict min = 2 (2Wiki 3 / MuSiQue 2). R2 판정 철회 불필요.
- **단 수치는 부풀려져 있었다**: 2Wiki 6→3, MuSiQue 3→2 (lenient→strict). R1의 "2Wiki d2 0→4"도 같은 워커라 lenient 수치다.
- 정정 조치: 본 문서 + R2 결과 문서 주석 + LakatoTree 본 노드 touched_assumptions에 `r1_r2_lenient_fallback_inflation` 박제. 이후 걷기 실험은 strict 워커(`t3_score_null.walk_scores_strict`)를 정본으로 사용할 것.

## 의미

1. **걷기 lane의 mechanism 사슬 완성**: 재료 있음(B1→R2, T0) → seed 도달(R1→R2, T1) → predicate 통과(R2, T2) → **점수 실변화 + null 검증(T3)**. 남은 것은 mechanism이 아니라 **효용**: 이 digest 변화가 답 품질(recall/answer)을 올리는가 — 그건 걷기 승리 regime(R3 판)에서만 공정하게 측정 가능 (C4).
2. 정직 경계: digest 변화 1~2질의/200은 이 substrate(조밀·소규모=걷기 불리 판)의 천장. 효용 주장 없음.
3. 자기감사가 실측으로 작동: 자기 워커의 결함을 스스로 공표·정정하고도 프로그램이 산다 — 이게 이 방법론의 존재 이유.

## 산출물

`t3_score_null.py`(strict 워커+null) · `PREREG_T3_SCORE_NULL_2026-07-23.json`(자기감사 약속 포함 동결) · `EVIDENCE_T3_SCORE_NULL_2026-07-23.json` (sha `753e281d…`)
