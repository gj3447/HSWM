# PROM16 negative-improvement agent-8 :: AXIS=C LENS=theory

> item: AXIS=C n-ary | LENS=최신이론 | FOCUS=2025~26 higher-order/hypergraph 구조가 pairwise 대비 실측 우위를 보인 최신 사례 — hypergraph neural nets, n-ary fact retrieval, HippoRAG 계열 후속, HAGE류, higher-order GNN. 'clique 축약으로 전량 재현 가능'을 깬 조건(태스크/스케일/구조)이 문헌에 있는가.

**한 줄**: 2025~26 문헌은 n-ary 우위가 **표현(representation) 층이 아니라 검색·추론 경로(retrieval path) 층**에서 발생함을 일관되게 보이며, 우리 C1 kill(가중치장 층에서 clique 전량 재현)은 오히려 최신 GNN 실측과 정합적이다.

**핵심 발견**:

- **반증부터 — clique/expansion이 종종 이긴다 (NeurIPS 2025)**: Pellegrin·Fesser·Weber는 자연적 하이퍼그래프 입력에서조차 graph-level 아키텍처 + hypergraph expansion이 hypergraph-level 아키텍처를 자주 능가함을 체계적 실측으로 입증. 단 **hypergraph-level 인코딩(고차 통계)을 graph-level 모델에 결합하면 표현력이 증명 가능하게 상승 + 상당한 성능 향상**. → HSWM C1 결과와 정확히 일치: n-ary *구조 자체*가 아니라 *인코딩/활용 방식*이 효과를 만든다. [arXiv 2502.09570](https://arxiv.org/abs/2502.09570)
- **n-ary 우위는 검색 경로 층에서 큼**: PRoH (WWW'26) — HyperGraphRAG 대비 평균 **F1 +19.73%**, 특히 3–6 hop long-range QA에서 Agriculture F1 **81.01 vs 52.40**. ablation으로 EWO(entity-weighted overlap) 경로 탐색 제거 시 −5.3%, target hyperedge 매칭 제거 시 −8.6%. n-ary 팩트를 *단위로 한 경로 추론*이 이득의 원천. [arXiv 2510.12434](https://arxiv.org/html/2510.12434v2)
- **표현 층 비교 수치 (PRoH Table 1, cross-verified)**: HyperGraphRAG(n-ary) F1 35.35~48.71 vs StandardRAG 27.90~43.20 vs **HippoRAG2 12.63~21.53** — KHQA 도메인에서 n-ary 하이퍼그래프가 HippoRAG2 구문그래프를 큰 폭으로 상회. HyperGraphRAG 원문: [arXiv 2503.21322](https://arxiv.org/abs/2503.21322)
- **순서 축 = clique가 원리적으로 못 깨는 조건**: OKH-RAG (2026) — 동일 하이퍼그래프·동일 검색 내용에서 순서만 셔플하면 정확도 **0.534→0.487** (−4.7pp, 최대 낙폭). permutation-invariant 방법의 불충분성을 명제로 정식화. [arXiv 2604.12185](https://arxiv.org/html/2604.12185v1)
- **형식적 한계 정리**: HyperRAG (2026) — n-ary 팩트의 *any straightforward binary scheme*이 faithful-reduction 조건 중 ≥1개를 반드시 위반함을 정식화(구조적 완전성 손실). HotpotQA/MuSiQue/2Wiki에서 최강 baseline 대비 MRR +2.95%, Hits@10 +1.23%. [arXiv 2602.14470](https://arxiv.org/abs/2602.14470)
- HippoRAG 2 자체는 passage recall@5 평균 87.1(MuSiQue 74.7/2Wiki 90.4/HotpotQA 96.3)로 강력하나, 위 비교에서 n-ary 구조에 밀림. [arXiv 2502.14802](https://arxiv.org/abs/2502.14802)

**HSWM 이식 설계** (C1 재설계안):

1. **태스크를 n-ary-경로 의존으로 교체**: 기존 C1은 lesson *주입 가중치장*에서 비교 — 문헌상 이 층은 clique가 이기는 층. 대신 정답이 **≥3개 lesson의 동시 결합**(어떤 pairwise 부분집합으로도 불충분, planted conjunctive ground truth)을 요구하는 QA를 설계.
2. **Arms**: (a) hswm hyperedge 단위 검색, (b) clique + **Weber식 hypergraph 인코딩 결합**(공정한 최강 baseline — 이걸 이겨야 함), (c) EWO식 entity-weighted overlap 점수 clique. 메트릭: joint-fact recovery rate, reasoning-path recall.
3. **Kill 조건 (사전등록)**: clique+인코딩이 hswm의 2pp 이내면 n-ary claim 영구 보류(shelve), C1은 "검색 경로 층 전용"으로 격하.
4. **무료 이식품** (claim 무관하게 채택): HippoRAG2식 **synonym hyperedge**(엔티티 동의어 병합, PRoH ablation −5.2% 효과), EWO 점수(검색 정밀 +5.3%) — 둘 다 clique 구조에도 적용 가능한 순수 이득.

**references**:
- https://arxiv.org/abs/2502.09570 (Pellegrin/Fesser/Weber, NeurIPS 2025) ✅
- https://arxiv.org/html/2510.12434v2 (PRoH, WWW'26) ✅ 전문 검증
- https://arxiv.org/abs/2503.21322 (HyperGraphRAG) ✅ 초록 검증
- https://arxiv.org/html/2604.12185v1 (OKH-RAG) ✅ 전문 검증
- https://arxiv.org/abs/2602.14470 (HyperRAG n-ary) ✅ 초록 검증
- https://arxiv.org/abs/2502.14802 (HippoRAG 2) ⚠️ 수치는 2차 스니펫 경유

**caveats**: OKH-RAG는 항만·사이클론 단일 도메인 — 순서 효과의 일반성 미검증. KHQA 벤치마크는 LLM 생성 데이터(자기상관 위험). arXiv 2602/2604 계열은 2026 프리프린트로 피어리뷰 미통과. HyperRAG 본문 표는 미열람(초록 수치만). HippoRAG2 vs HyperGraphRAG 비교는 PRoH 측 재현 수치로 독립 복제 아님.
