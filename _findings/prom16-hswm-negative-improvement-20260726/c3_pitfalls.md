# PROM16 negative-improvement agent-10 :: AXIS=C LENS=pitfalls

> item: AXIS=C n-ary | LENS=함정 | FOCUS=higher-order 구조 주장이 clique/pairwise에 밀린 선행 부정 사례 2025~26 — hypergraph GNN이 pairwise GNN과 동률/열세였던 실측, n-ary가 오버헤드만 남긴 사례. 언제 higher-order가 비용 대비 손해인가.

1차 소스 검증 완료. 보고서를 작성합니다.

---

**한 줄**: higher-order 구조는 "신호가 그룹-일관적(homophilic)일 때만" pairwise를 이기고, 그 조건이 무너지면 HNN 17종 전부가 feature-only MLP에도 지거나 동률이며 토큰·시간 오버헤드만 9~406× 남긴다 — HSWM C1의 n-ary 패배는 예외가 아니라 문헌상 반복되는 정상 귀결이다.

**핵심 발견**:

- **DHG-Bench (ICLR 2026, 17 HNN × 22 데이터셋, 통일 프로토콜)** — 가장 강력한 부정 실측. 이질성(heterophilic) 데이터셋에서 **MLP가 전체 17개 HNN을 전부 이김**: Twitch-gamers MLP 52.57 vs 최고 HNN 52.50; Actor MLP 86.06 vs HGNN 77.83·CEGCN 67.41 (최고 HNN도 86.21 = +0.15pp 동률). Pubmed에서는 **clique reduction이 MLP보다 못함** (CEGCN 86.03 < MLP 86.62) — 구조 추가가 음의 기여. homophilic 공저 네트워크에서만 HNN이 CE 대비 +4~6pp (DBLP-CA 91.83 vs 89.75). 효율: Yelp에서 ED-HNN 9×, EHNN 23× 학습시간(이득은 marginal), T-HyperGNN 406× 느림, 17종 중 8종 OOM. hyperedge 예측에선 **최신 HNN들이 최고참 HGNN/HyperGCN에 패배** (TF-HNN −13.76 AUROC) — 구조 복잡화 ≠ 진전. [arXiv 2508.12244v2](https://arxiv.org/html/2508.12244v2)
- **When Hypergraph Meets Heterophily (AAAI 2025)** — 합성 HSBM 통제 실험: **Hedge ≤ 0.5이면 HNN 전부 MLP에 패배**, > 0.5에서만 역전. 즉 n-ary 이득의 존재 조건이 명시적으로 측정됨. 또한 기존 "heterophilic 벤치마크"(Congress/Senate/Walmart/House)의 CE homophily가 실은 >0.5로 **벤치마크 자체가 오분류**돼 있었다는 지적 — 구조 주장 검증 전에 데이터셋 homophily부터 재라는 함정. [PDF (CityU mirror, AAAI 39:18377)](https://staffweb1.cityu.edu.hk/xzhuang7/pubs/2025-LGWFBZL-AAAI.pdf)
- **GraphRAG-Bench (2025, ICLR'26 제출)** — LLM 컨텍스트 주입 채널에서의 구조 오버헤드 = HSWM과 동일 채널. 단순 사실 검색에서 GraphRAG(global) ACC **36.92 vs vanilla RAG 60.92 (−24pp)**, context relevance 9.37–19.40 vs RAG 74.66–82.84로 붕괴. 토큰 비용: V-RAG 879 vs GraphRAG(global) **331,375 tokens (377×)**, LightRAG ~100k. 구조 이득은 복합 추론에서만 (HippoRAG2 53.38 vs 42.93, +10.5pp). (내부 인용: Han et al. 2025 — GraphRAG가 NQ −13.4%, 시간민감 −16.6%, HotpotQA +4.5%에 2.3× 지연.) [arXiv 2506.05690](https://arxiv.org/html/2506.05690v1)
- **Telyatnikov et al. (TMLR, 2310.07684)** — 방법론적 함정: 기존 HNN 방법론과 벤치마크 대부분이 graph에서 lifting된 것이라 hypergraph 고유 특성이 가려졌고, "기존 데이터셋은 HNN의 유의미한 벤치마크가 아니다" 결론. [arXiv 2310.07684](https://arxiv.org/abs/2310.07684)

**HSWM 이식 설계** (C1 재시험용):

- **전제조건 게이트 (측정-구동 dispatch)**: n-ary arm 개시 전에 lesson hyperedge별 "ΔW-부호 일관성"(동일 hyperedge 내 lesson들의 credit 부호/방향 동조율 = homophily 대응물)을 측정. 일관성 ≤0.5 regime에서는 n-ary arm을 실행하지 않음 (AAAI 2025 Obs 2 직접 이식).
- **Arms**: (1) n-ary HSWM, (2) clique reduction, (3) star-expansion MPNN (최고참 단순 baseline — DHG-Bench에서 최신이 구형에 진 함정 방지), (4) **MLP-null**: 토폴로지 제거, lesson 텍스트 임베딩 유사도만. Kill: (4)가 (1) 이상이면 topology 전체가 오버헤드 → 즉시 kill (Gamers 사례 재현 조건).
- **심어진 이중 regime**: testbed에 homophilic lesson bundle(같은 정답을 지지하는 lesson 집합)과 heterophilic bundle(혼합)을 둘 다 심는다. Kill 조건 이원화: homophilic regime에서조차 n-ary ≤ clique면 C1 완전 사망; homophilic에서만 이기면 "조건부 기여"로 claim 축소 (전면 사망 아님).
- **비용 정규화 지표**: 정확도뿐 아니라 acc/1k-token(주입 채널)과 acc/학습시간을 공동 보고. Kill: n-ary의 비용-정규화 점수 < clique (GraphRAG 377×/−24pp 유형의 재앙 차단). 효율 상한: n-ary arm 총비용 ≤ 2× clique (ED-HNN 9×, EHNN 23×는 거부 선례).

**references**:
- https://arxiv.org/html/2508.12244v2 (검증됨, 전체 Table 1 수치 확인)
- https://staffweb1.cityu.edu.hk/xzhuang7/pubs/2025-LGWFBZL-AAAI.pdf (검증됨, Obs 1–3 확인)
- https://arxiv.org/html/2506.05690v1 (검증됨, Table 2/3 + 토큰 통계 확인)
- https://arxiv.org/abs/2310.07684 (검증됨, abstract)
- https://arxiv.org/abs/2207.06680 (ED-HNN abstract만 검증 — 본문 수치 미추출)

**caveats**: MDPI Kurashkin 2026 체계적 리뷰("feature-only baseline이 확립된 hypergraph 방법들을 지배 가능")는 Akamai 차단으로 본문 미검증 — 수치 인용 보류. arXiv 2510.10114의 context relevance 수치(36.86–54.61% vs 62.87%)는 검색 스니펫 수준, 미검증. Han et al. 2502.11371의 −13.4%/−16.6% 수치는 GraphRAG-Bench 본문 경유 인용(2차). DHG-Bench/AAAI 수치는 node classification GNN 맥락이며, HSWM의 "frozen LLM + 입력 주입" 설정과는 채널이 달라 직접 외삽 불가 — 이식 시 위 게이트/이원 kill 조건이 그 간극을 메우는 장치임.
