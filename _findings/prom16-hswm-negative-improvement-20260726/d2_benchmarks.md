# PROM16 negative-improvement agent-13 :: AXIS=D LENS=benchmarks

> item: AXIS=D 방법론 | LENS=벤치마크 | FOCUS=부정 결과를 positive로 전환한 선행 사례 2025~26 — kill/failure 후 testbed나 연산자를 재설계해 성립시킨 연구 스토리 (메모리/전이/그래프 검색 분야). 재사용 가능한 testbed 생성 코드·파이프라인.

**한 줄**: kill 후 testbed/연산자 재설계로 긍정 전환한 2025–26 사례들의 공통 패턴 = "난이도 축 삽입 + 연산자 목적 재정의(decay→재구조화) + confound 1개씩 고정하는 통제 벤치마크"이며, HSWM의 F3/F5/C1 세 kill에 직접 이식 가능한 코드가 전부 공개돼 있다.

**핵심 발견**:

- **τ-bench → τ²-bench → τ³-bench (Sierra)**: τ-bench는 "아무것도 안 하기" 전략으로 **38%의 태스크가 통과**하는 결함이 감사(SABER)로 드러나 kill 수준이었으나, dual-control(사용자도 도구 조작) + telecom 도메인 **2,285개 프로그램 생성 태스크** + **no-user 모드**(추론 vs 통신 실패 분리, ~20% pass¹ 하락 확인)로 재설계해 표준 벤치마크로 부활. 코드 실재: [tau2-bench](https://github.com/sierra-research/tau2-bench). → 교훈: 환경 자체에 "모드 분리 축"을 박아 어느 요인이 실패인지 분해.
- **F5 sleep 연산자의 긍정 버전 = Sleep-time Compute** ([arXiv 2504.13171](https://arxiv.org/abs/2504.13171)): sleep = decay/downscale이 아니라 **쿼리 예측 + 오프라인 재구조화**. Stateful GSM-Symbolic/AIME라는 *새 testbed를 만들어* test-time compute ~5× 절감, 정확도 +13%/+18% 상승. 효능은 **쿼리 예측가능성과 상관** — sleep이 항상 좋은 게 아니라 조건부임을 스스로 측정해 보고한 점이 HSWM의 preregistered kill 문화와 동일.
- **F3 전이 실패의 직접 대응 = Agent KB** ([arXiv 2507.06229](https://arxiv.org/abs/2507.06229)): 이종 에이전트 프레임워크 간 전이는 날것 경험 복사로 실패(knowledge interference) → **disagreement gate**(검색 지식이 추론을 방해하면 폐기) 도입으로 전이 성립: smolagents GAIA pass@3 55.2→73.9%(**+18.7pp**), OpenHands SWE-bench +4.0pp. **ReasoningBank** ([arXiv 2509.25140](https://arxiv.org/abs/2509.25140)): 성공+**실패** 궤적 모두에서 전략 수준 메모리 증류, WebArena +8.3/+7.2/+4.6pp (3개 백본). 추가 경고: [ICML 2026 "faithful self-evolvers"](https://arxiv.org/abs/2601.22436) — 요약된 lesson(system prompt)은 raw trajectory보다 충실히 사용되지 않는다는 부정 결과.
- **C1 그래프 고유 기여 탐지 = GraphRAG-Bench** ([arXiv 2506.02404](https://arxiv.org/abs/2506.02404), 코드 [jeremycp3/GraphRAG-Bench](https://github.com/jeremycp3/GraphRAG-Bench)) + "When to use Graphs in RAG" ([arXiv 2506.05690](https://arxiv.org/abs/2506.05690)): "GraphRAG가 RAG보다 자주 못하다"는 부정 보고들(Han et al., Xiang et al.)에 대응해 **난이도 증가 태스크(fact→complex reasoning→creative) + 파이프라인 단계별 분해(구축/검색/추론)**로 재설계 → 그래프가 이기는 *조건*을 사상(mapping). n-ary도 동일: "언제 이기는가"를 축으로 만들어야 기여가 탐지됨.
- **통제 방법론 정본 = MemDelta** ([arXiv 2606.29914](https://arxiv.org/abs/2606.29914)): 임베딩 모델 하나만 바꿔도 +6.2pp(p=0.004)로 결론이 뒤집히고, RAG vs full-context 순위가 모델 패밀리마다 반전(Sonnet full-context 쿼리 63% 거부). 메모리 평가는 변수 1개씩, 임베딩 고정, 패밀리별 층화, write-path 비용 보고를 권고.
- **재사용 파이프라인**: [PhantomWiki](https://github.com/kilian-group/phantom-wiki) — `--question-depth 20`(난이도∝depth), universe 25~1M, seed 통제, vLLM 평가 스크립트 내장. [LongMemEval](https://github.com/xiaowu0162/LongMemEval) — `sample_haystack_and_timestamp.py`로 임의 길이 히스토리 합성 + **oracle split**(evidence만 제공 = retrieval confound 제거) + index expansion 코드.

**HSWM 이식 설계**:

- **F3-v2 (capability 축 삽입)**: PhantomWiki depth hard-split — 14b가 self-study 후에도 F1<0.4, 27b는 >0.7인 split만 선별(τ² no-user 모드 식 사전 분리). Arms: (a) donor-lesson+**disagreement gate** (b) donor-lesson no-gate (c) receiver-own (d) placebo-lesson. Metric: hard-split F1 lift (a)−(c). Kill: (a)−(c) ≤ 0 (CI 상한 포함) 또는 gate-off ablation (b)≥(a)이면 gate 필요성 부정.
- **F5-v2 (sleep 재설계)**: 연산자를 downscale→**쿼리 예측 기반 재구조화**(Sleep-time Compute 방식)로 교체. LongMemEval oracle split으로 detail 보존 측정 시 retrieval confound 제거, 임베딩 고정(MemDelta 규약). Kill: 재구조화 arm이 no-op보다 detail 슬로프 나쁘면 재-kill; 쿼리 예측가능성 낮은 world에서는 효과 없음을 *사전 예측*하고 등록.
- **C1-v2**: GraphRAG-Bench 식으로 "n-ary가 이기는 조건 축"(hyperedge ≥3개 실체가 정답에 필수인 쿼리 비율)을 사전 등록하고, 파이프라인 단계별(구축/검색/추론) 분해 평가. Kill: 해당 축에서도 clique−hswm ≤ 0이면 n-ary 고유 기여 최종 부정.

**references**: https://arxiv.org/abs/2504.13171 · https://github.com/sierra-research/tau2-bench · https://arxiv.org/abs/2507.06229 · https://arxiv.org/abs/2509.25140 · https://arxiv.org/abs/2506.02404 · https://arxiv.org/abs/2506.05690 · https://arxiv.org/abs/2606.29914 · https://github.com/kilian-group/phantom-wiki · https://github.com/xiaowu0162/LongMemEval

**caveats**: τ-bench 38% do-nothing 수치는 OpenReview PDF(SABER 계열 감사) 스니펫 경유 — 원문 단독 검증 못 함. ReasoningBank 수치는 v1 HTML 표 요약 기준. "When to use Graphs in RAG"의 조건 사상(mapping) 구체 수치는 미추출. Sleep-time Compute의 Stateful AIME +18%는 sleep compute scaling 상한 시나리오. 2601.22436(ICML 2026)은 이슈 글 경유 인용이라 1차 검증 부분적.
