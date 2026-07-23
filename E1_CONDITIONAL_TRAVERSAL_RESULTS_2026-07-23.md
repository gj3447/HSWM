# E1: Query-Type Conditional Traversal — 측정 결과 (2026-07-23)

## 목적

HSWM query-time traversal(PPR 계열)의 기존 전면 TRAVERSAL_OFF 판정이 질의 타입에
따라 달라지는지 검증. 문헌(arXiv 2502.11371, 2506.05690)은 그래프/전파가
bridge/multi-hop 질의에서만 이기고 factoid에선 진다고 보고하므로, 기존 per-query
데이터를 gold hop 수로 사전 분할해 OFF 판정의 범위를 좁힐 수 있는지 측정했다.

## 설정 (사전등록 고정)

- 입력: `traversal_bench_results.json` (test 179쿼리, val 제외)
  sha256 `5ead7a7e…998698`
- hop 라벨: 파일 내 per-query `n_gold`(정답 evidence 문서 수). 파일 자체의
  `test_per_hop` 계층화와 1:1 일치(musique 2hop/3hop*/4hop* ↔ n_gold 2/3/4).
  조인 커버리지 **179/179 (100%)**.
- 분할: bridge = gold hop ≥ 3 (n=69), factoid = hop ≤ 2 (n=110)
- metric: `sup_recall_at_3` (primary)
- 비교: best traversal arm − `hswm_static`, paired bootstrap 95% CI
  (10,000 resamples, seed=20260723)
- arms: static=`hswm_static`, traversal=`hswm_traversal`/`ppr_pure`/`traversal_wseed`
  (`cosine`은 비-HSWM baseline으로 표기만)

## 측정값 (subset별 × arm별 mean sup_recall_at_3)

| arm | bridge (n=69) | factoid (n=110) |
|---|---|---|
| hswm_static | 0.5785 | 0.7909 |
| hswm_traversal | 0.3575 | 0.6682 |
| ppr_pure | 0.2645 | 0.4636 |
| traversal_wseed | 0.4396 | 0.7182 |
| (baseline) cosine | 0.4952 | 0.7727 |

두 subset 모두 best traversal arm = `traversal_wseed`.

| subset | best-trav − static Δ | 95% CI |
|---|---|---|
| bridge | **−13.89pp** | [−19.44, −8.33] |
| factoid | **−7.27pp** | [−10.91, −3.64] |

## Prereg 판정 대비

- 예측(bridge): Δ ≥ +2.0pp & CI 하한 > 0 → **기각**. 관측 −13.89pp, CI 전 구간 음수.
  (사전 증거상 기대가 낮았던 예측이며, 실제로 실패 확인.)
- novel cross-metric(factoid): Δ < 0pp → **확증**. 관측 −7.27pp, CI 상한 −3.64pp.
- 결론: **전면 TRAVERSAL_OFF 유지**. '조건부 OFF'(bridge에서만 ON) 개정 근거 없음.
  오히려 bridge에서 손해(−13.89pp)가 factoid(−7.27pp)보다 더 크다 — 문헌의
  "그래프는 multi-hop에서 이긴다"는 주장이 이 substrate/bench 조합에서는
  재현되지 않았다.

## Caveat

- best-arm 선택이 subset 내 mean 최대치로 이루어져 선택 편향이 Δ를 0 쪽으로
  끌어당김(그럼에도 유의한 음수). per-arm 전체 표는 evidence JSON에 포함.
- 사후(post-hoc) 분할 분석: 동일 데이터로 OFF가 판정된 뒤의 재분할이므로,
  bridge 긍정 결과가 나왔어도 독립 확인이 필요했을 것. 음수 결과라 이 우려는 무효.
- hop 프록시가 n_gold(문서 수)이며, 2wiki의 추론 깊이와 정확히 동의어는 아님.
- musique 117 / 2wiki 62 혼합 subset; dataset별 이질성은 미분리.

## 산출물

- 측정 스크립트: `e1_conditional_traversal.py`
- evidence: `EVIDENCE_E1_CONDITIONAL_TRAVERSAL_2026-07-23.json`
