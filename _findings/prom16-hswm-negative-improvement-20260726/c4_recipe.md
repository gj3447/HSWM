# PROM16 negative-improvement agent-11 :: AXIS=C LENS=recipe

> item: AXIS=C n-ary | LENS=이식설계 | FOCUS=HSWM n-ary 고유기여 재시험 설계: 어떤 task family에서 hyperedge가 clique를 이길 것인가 (예: n≥3 joint constraint, provenance 보존 병합), arm (hswm/clique/dense/pairwise-hyper), metric, kill 조건. C1 book-scale (n=262×4권, clique에 −2.00pp kill) 설계의 어느 축(코퍼스 스케일/질의 타입/팬아웃)을 바꿀지.

검증 완료. 최종 보고서를 작성합니다.

---

**한 줄**: C1의 kill는 스케일 문제가 아니라 **질의 타입** 문제였다 — n-ary 고유기여는 "pairwise 투영으로는 원리적으로 구분 불가능한" joint-constraint 질의 + marginal-matched null에서만 검출 가능하며, 통제된 통합 비교(RAGSearch)에서조차 hypergraph backend는 entity-graph에 졌으므로 팬아웃-기울기까지 사전등록해야 한다.

**핵심 발견**:
- **질의 타입이 지배 변수**: RAGSearch(통일 백본/예산/전체 테스트셋 통제 비교)에서 GraphRAG 계열 이득은 multi-hop QA 평균 **+27.23 EM**인 반면 general QA는 **+0.47**에 불과. 구조의 고유기여는 질의가 구조를 *요구*할 때만 나타남. C1의 book-scale 질의가 pairwise 경로로 풀렸다면 clique가 이기는 것은 당연 ([RAGSearch, 2026](https://arxiv.org/html/2604.09666v1)).
- **적대적 증거 — hypergraph backend가 졌다**: 동일 프로토콜에서 HyperGraphRAG(hyperedge)는 HippoRAG2(entity graph)에 multi-hop 전반에서 열세 (GraphSearch HotpotQA 46.83 vs 58.64, avg rank 2.33 vs 1.33). "n-ary 저장" 자체는 승리 조건이 아님 ([RAGSearch, 2026](https://arxiv.org/html/2604.09666v1)).
- **n-ary 이득은 복잡도-기울기 claim**: Hyper-RAG는 직접 LLM 대비 +12.3%, GraphRAG/LightRAG 대비 +6.3/+6.0pp이나, 핵심은 "질의 복잡도 증가 시 기존 방법은 하락하는데 Hyper-RAG는 안정" — 평균이 아니라 **기울기**가 판별 metric ([Hyper-RAG, 2025](https://arxiv.org/abs/2504.08758)).
- **원리적 구분 불가 조건 확립됨**: clique 투영은 "환원불가 3체 사건 1개"와 "독립 쌍 사건 3개"를 구별 못 함 (Benson의 open/closed triangle 문제; 고차 link prediction 문헌의 표준 null) ([Simplicial Closure, PNAS 2018](https://ora.ox.ac.uk/objects/uuid:ee41a004-0a9b-4726-8e31-df214d6133a8/files/m0ceca0162e6feb47b619135880e8f48a)). 즉 marginal-matched 설계가 유일하게 정당한 판별 베드.
- **HNN 벤치마크의 교훈**: DHG-Bench(17 HNN × 22 데이터셋)에서 HNN > clique-expansion GNN이 일반적이나, heterophilic 데이터에선 대부분 MLP에도 패배 + 데이터셋 특성이 방법 차이를 지배 — task family 선택이 실험의 전부 ([DHG-Bench, 2025](https://arxiv.org/abs/2508.12244)).

**HSWM 이식 설계** (C1 재시험 — 바꿀 축: 질의 타입 ≫ 팬아웃 > 코퍼스 스케일):
- **테스팃**: PhantomWiki 확장. planted n-ary 사건 `e=(A,B,C,장소P,날짜D)` (n=3,4). 대조 world는 **동일 엔티티·동일 pairwise 공발생 marginal, 다른 그룹핑** (marginal-matched null — clique는 원리상 구분 불가).
- **Task family 2종**: (a) n≥3 joint-constraint QA — 답이 n개 엔티티 동시 결합을 요구; (b) provenance 보존 병합 — 두 world 병합 시 clique는 cross-world phantom triangle 생성, hyperedge는 사건 단위 유지.
- **Arms**: hswm(typed hyperedge+provenance) / clique(동일 ΔW, pairwise 전개) / dense(무구조 lesson 리스트) / pairwise-hyper(hyperedge 저장·pairwise 주입 — 저장 vs 주입 축 분리).
- **Metric**: joint-QA 정확도(주), provenance F1(주입된 사건 단위), phantom-edge rate, n∈{2,3,4}에 대한 정확도-기울기.
- **Kill 조건 (사전등록)**: K1: marginal-matched n=3에서 hswm−clique < +3pp → n-ary 고유기여 부재, claim shelve. K2: n에 대한 hswm 우위 기울기 ≤ 0 → 복잡도-스케일링 부정. K3: provenance 병합에서 clique phantom rate가 hswm 대비 유의하게 높지 않음 → provenance claim kill. K4: +5pp 검출 80% power 미달 표본이면 결과는 inconclusive로 보고 (C1의 low-power 전철 반복 금지).
- **코퍼스 스케일은 축소**: 262×4권 유지 불필요 — 소형 합성에서 구조 null이 깨끗함. 스케일은 K1 통과 후 2차 실험.

**references**:
- https://arxiv.org/html/2604.09666v1 (RAGSearch 벤치마크 — verified)
- https://arxiv.org/abs/2504.08758 (Hyper-RAG — verified)
- https://arxiv.org/abs/2508.12244 (DHG-Bench — verified, 본문 HTML 확인)
- https://arxiv.org/abs/2503.21322 (HyperGraphRAG — abstract verified)
- https://ora.ox.ac.uk/objects/uuid:ee41a004-0a9b-4726-8e31-df214d6133a8/files/m0ceca0162e6feb47b619135880e8f48a (Benson et al., Simplicial Closure — verified)

**caveats**: HyperGraphRAG 본문의 정확한 효과 크기는 abstract에 없어 미검증(정량 수치 미확보). HGRAG(2508.11247) "6× 속도·SOTA"는 abstract만 확인, 수치표 미검증. "Order-Aware Hypergraph RAG"(2604.12185)·HyperSU(2606.28351)는 검색 스니펫만 — 미검증. RAGSearch의 HyperGraphRAG 열세는 7B 백본 기준이며 27b급 donor/receiver 조건으로 일반화 불확실.
