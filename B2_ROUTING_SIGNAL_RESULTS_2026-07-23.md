# B-2 Routing Signal Existence — 측정 결과 (2026-07-23)

사전등록(LakatoTree) 실험. 학습 없이 기존 per-query 결과 JSON에서 "우리 쿼리 분포에
per-query routing이 이길 신호가 존재하는가"를 측정. 스크립트: `b2_routing_signal.py`
(실행: `.venv/bin/python b2_routing_signal.py`, seed=20260723, bootstrap 10000 paired,
epsilon=0.01).

## 정의

- **oracle gap (pp)** = mean_q(max_arm score_q) − max_arm(mean score) × 100.
  어떤 per-query router든 낼 수 있는 이득의 상한.
- **tie rate (%)** = 쿼리 중 (1위 − 2위) 점수 차 ≤ 0.01 인 비율.
- **kill 조건 (prereg)**: oracle gap < 2.0pp 또는 tie rate > 80%.

## per-query 데이터 보유 파일

| 파일 | 내용 | 사용 |
|---|---|---|
| `substrate_bench_results.json` | 5 substrates(cosine/bm25/ppr/rrf/hswm) × sup_recall_at_3, ndcg10, 300쿼리(3 run × 100) | ✅ |
| `traversal_bench_results.json` | 5 arms(cosine/hswm_static/hswm_traversal/ppr_pure/traversal_wseed) × sup_recall_at_3, ndcg10, test 179쿼리 (val 121 제외) | ✅ |
| `ab_p5_full_results.json` | 3 arms(cosine/direct/hswm) × f1, em, 300쿼리 (3 run 파일 통합본) | ✅ |
| `ab_p5_full_{2wiki_s7,musique_s7,musique_s13}.json` | 위 통합본의 run별 원천 (중복이므로 별도 집계 안 함) | (중복) |
| `qkv_routing_result.json` | 집계 count/rate만, per-query 점수 없음 | ❌ 보고만 |
| `qkv_b1_development_result.json` | arm별 집계 metric + score_matrix_sha256만, 원시 점수 행렬 미저장 | ❌ 보고만 |

## 측정값 (primary metric: retrieval은 sup_recall_at_3, ab_p5는 f1)

| 데이터셋 | metric | n | oracle gap (pp) | CI95 | tie rate | margin median (pp) |
|---|---|---|---|---|---|---|
| substrate_bench pooled | sup_recall_at_3 | 300 | 6.19 | [4.53, 8.03] | **81.3%** | 0.0 |
| substrate_bench musique_s7 | sup_recall_at_3 | 100 | **9.92** | [6.33, 13.75] | 75.0% | 0.0 |
| substrate_bench musique_s13 | sup_recall_at_3 | 100 | 4.67 | [2.33, 7.33] | 78.0% | 0.0 |
| substrate_bench 2wiki_s7 | sup_recall_at_3 | 100 | 4.00 | [1.75, 6.75] | **91.0%** | 0.0 |
| traversal_bench pooled (test) | sup_recall_at_3 | 179 | 3.68 | [2.05, 5.49] | **87.2%** | 0.0 |
| traversal_bench musique (test) | sup_recall_at_3 | 117 | 4.13 | [1.99, 6.48] | **83.8%** | 0.0 |
| traversal_bench 2wiki (test) | sup_recall_at_3 | 62 | 2.82 | [0.81, 5.65] | **93.5%** | 0.0 |
| ab_p5 pooled | f1 | 300 | 5.61 | [3.36, 8.15] | 76.3% | 0.0 |
| ab_p5 musique_s7 | f1 | 100 | 5.83 | [2.00, 10.30] | 66.0% | 0.0 |
| ab_p5 musique_s13 | f1 | 100 | 3.78 | [1.13, 7.07] | 69.0% | 0.0 |
| ab_p5 2wiki_s7 | f1 | 100 | 3.08 | [0.42, 6.50] | **94.0%** | 0.0 |

보조 지표(ndcg10, em)는 JSON 산출물 참조 — 경향 동일(oracle gap 1.0–7.0pp).

## 판정 (prereg kill 조건 대비)

- **routing에 가장 유리한 상한**(primary verdict 기준): substrate_bench/musique_s7,
  sup_recall_at_3 — **oracle gap 9.92pp** (CI95 [6.33, 13.75]), tie rate 75.0%.
  → kill 조건 둘 다 미발동: gap > 2pp, tie < 80%. **신호 존재 (survives)**.
- 단, pooled 기준으로는 substrate_bench(81.3%)와 traversal(87.2%)이 tie-rate kill
  조건(>80%)에 걸린다. 즉 **전체 분포의 ~4/5 쿼리에서는 어떤 장을 골라도 동점**이고,
  잔여 신호는 musique_s7 슬라이스에 집중되어 있다.
- margin median이 전 데이터셋에서 0.0pp — 1위/2위 무차별 쿼리가 과반. HetDocQA
  (arXiv 2606.28367)의 "tie rate 지배적, oracle router 이득 미미" 관찰과 정성적으로 일치.

**종합**: kill 조건 문구 그대로 가장 유리한 데이터셋에 적용하면 **생존**(9.92pp, tie 75%,
하한 CI 6.3pp > 2pp). 다만 tie rate 75%가 kill 문턱(80%)에 근접하고 pooled 분포는 kill
영역이라, 신호가 "존재하지만 얇고 musique에 편중"으로 읽는 것이 정직하다. learned
router(B2.1) 재시도를 정당화하려면 이 ~15–25%의 비동점 쿼리를 사전 식별 가능한지가
다음 관문이다.

## Caveats

- 각 run당 n=100 (traversal 2wiki test는 62) — CI가 넓다.
- substrate_bench와 traversal_bench는 같은 쿼리셋을 공유(독립 증거 아님); arm 구성만 다름.
- tie 판정 epsilon=0.01은 점수 스케일 의존적 — sup_recall_at_3는 1/3 단위 이산이라
  0.01 미만 차이는 사실상 정확한 동점.
- qkv 계열 2개 파일은 per-query 점수 미보유로 분석 제외(위 표 참조).

## 산출물

- `EVIDENCE_B2_ROUTING_SIGNAL_2026-07-23.json` — 전수치 + 입력 파일 sha256 + seed/epsilon.
- `b2_routing_signal.py` — 측정 스크립트 (재현: `.venv/bin/python b2_routing_signal.py`).
- 본 파일.
