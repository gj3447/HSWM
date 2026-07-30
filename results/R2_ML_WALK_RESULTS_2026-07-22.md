# R2 ML-material walk 결과 — depth-2 첫 해빙 (2026-07-22→23 심야)

> **판정**: metric **`progressive`** (preregistered 예측 2/2 적중) / 프로그램 Lakatos `degenerating` (BF 0.167 — 누적 하중, B1·ML18과 동일 이중판정). assurance L0(client_asserted, 서버측 replay 환경 부재로 replay_refuted 표시). receipt fold `ok=true`.
> **노드**: `LakatosTree_PromSearchHSWM_20260721 / R2-ml-material-walk` (예측 receipt `a8f0c717…`).
> **한 줄**: P6→B1→T1→R1 내내 0에 박혀 있던 **min kernel-legal depth-2가 처음으로 움직였다** — MuSiQue 0→**3**, 2Wiki 4→6. USER 정전 "연산 많이 해도 똑똑해지면 된다"의 첫 집행이 값을 냈다.

## 사전등록 대비 실측 (PREREG_R2_ML_WALK_2026-07-22.json, 실행 전 동결)

| metric | 예측 | 실측 | 판정 |
|---|---|---:|---|
| `min_over_datasets_A5_kernel_legal_depth2` | ≥1 (baseline 0) | **3** | ✓ |
| `sum_A5_minus_A4_depth2` (novel) | >0 | **+5** | ✓ |
| A4 재현통제 = R1 영수증 | 일치 필수 | t1 2/7·d2 0/4 정확 일치 | ✓ kill#2 미발동 |
| sha-mismatch 문단 | ≤5% | **0** | ✓ |

## 단일변수 A/B (walker·seed·alias·soft 전부 R1과 동일 — 바뀐 건 그래프 재료뿐)

| | 2Wiki A4→A5 | MuSiQue A4→A5 |
|---|---|---|
| T0 admissible chains | 25 → **70** | 6 → **23** |
| entrance 문단 | 10 → 17 | 5 → 14 |
| t1 seed 도달 질의 | 7 → 8 | 2 → 4 |
| **kernel-legal depth-2 질의** | 4 → **6** | **0 → 3** |
| depth-2 도달 target 합 | 5 → 9 | 0 → 18 |

ML weave 규모: arcs 2Wiki 286 / MuSiQue 634. 역할 해소 direct 4,880+5,778 / coref 전파 256+284. 충돌 클러스터 폐기 419+759 (보수 규율 작동). fan cap 발동 0.

## 재료 계보 (전부 receipt·attestation 박제)

- **ReFinED** `wikipedia_model_with_numbers` (era-pin: transformers 4.30.2/tokenizers 0.13.3/numpy 1.26.4 — 2026 스택에선 즉사, A1 조사의 의존성 부패 경고 실증) + **fastcoref FCoref** (transformers 4.49 핀). 둘 다 CPU 고정, 전 span `text[start:end]==exact` 즉석 검증.
- 3,599 문단 추출 receipt 4파일 sha는 PREREG에 동결. Mac 스왑 한계(9.7–10.5/11GB)로 3회 kill → 200문단 체크포인트 + 라운드제(450문단/프로세스) 드라이버로 완주.
- build-time only. query-time LLM/network 0, gold 무소비.

## 해석

1. **R1 kill#2의 답이 나왔다**: depth-2가 0이던 건 어휘도 커널도 아니고 **재료였다**. 진짜 identity 재료(QID+coref)를 넣자 chain 4배(6→23), 그 위에서 커널이 MuSiQue 첫 legal 2-hop 완주. B1(결정론 unlock=공회전 판정)과 대비: 같은 아이디어의 "공짜 버전"은 죽었고 "연산 버전"은 살았다.
2. **정직 경계**: depth-2 질의 3/200·6/200은 구조 해빙이지 검색 품질 주장이 아니다. answer/recall 이득은 미측 — 그 주장은 T3(K2 score digest 변화+null)와 별도 prereg 뒤에서만.
3. **C4 regime 주의 지속**: 이 substrate(조밀·소규모)는 걷기에 불리한 판. 여기서도 움직였다는 건 고무적이나, 본 승부는 R3(2Wiki full-pool)에서.
4. 프로그램 레벨 degenerating은 유효한 냉수: 구조 지표 연쇄가 아직 최종 지표(답 품질)에 닿지 않았다.

## 다음

- **T3 rung**: A5 그래프에서 K2가 K1 score digest를 실제로 바꾸고 second-edge null이 그걸 죽이는지 — 걷기 lane의 최종 관문.
- **R3**: 2Wiki full-corpus pool (걷기 승리 regime) + PhantomWiki density-dial.
- ML lane 확장: ReFinED candidates(top-5 저장돼 있음) 활용한 soft-QID, HippoRAG2식 query-time 필터.

---

## 정정 주석 (2026-07-23, T3 strict 재감사)

본 문서의 depth-2 수치는 R1 계열 워커의 **lenient fallback**(hop-2에서 연속 arc 부재 시 임의 arc 허용 — 커널 정본 아님) 하의 집계였다. strict(커널 정본) 재감사 결과: 2Wiki 6→**3**, MuSiQue 3→**2**. **min>0은 유지되므로 핵심 주장(depth-2 해빙)은 생존**하나 절대값은 위 표보다 작다. 정본 수치·상세 = `T3_SCORE_NULL_RESULTS_2026-07-23.md`. 이후 걷기 실험은 strict 워커를 정본으로 한다.
