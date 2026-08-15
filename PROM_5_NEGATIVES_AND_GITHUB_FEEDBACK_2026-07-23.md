# PROM 5 — 부정 결과 5종 해결 전략 + GitHub 외부 피드백 대응 (2026-07-23)

> 트리거: USER "reasoner REFUTED / traversal OFF / 리프트=임베딩 95% / 책-단위 미실측 / P6 degenerating — 이 부분 어케 해결할지 PROM + Git repo 피드백 확인"
> 5축 병렬 리서치 (축A traversal/구조, 축B reasoner/routing, 축C 책-단위, 축D absorption, 축E 외부피드백 실험설계).
> 상태: SECONDARY_AI 리서치 종합. 실험 채택은 사용자 ratify + HSWM_LOCAL_RECORD prereg 필요.

## 0. GitHub 피드백 현황 (확인 완료)

| 항목 | 상태 | 내용 |
|---|---|---|
| Issue #1 (OPEN) | **미해결 — 이번 PROM의 주 대상** | 외부 리뷰어: "범용 Hypergraph RAG 주장은 혼잡(HyperGraphRAG·SiReRAG·HippoRAG2·GFM-RAG·Zep·AriGraph). 방어 가능한 유일 가설 = **하나의 버전드 시맨틱 웨이트 場이 retrieval+selection+revision을 분리 헤드보다 낫게 서빙하는가**". 현 미확립 근거 3점: `plan()`은 alias일 뿐 / `supersede()`는 단순 decay / additive-j 실험서 HSWM만 offline LLM judgment 수혜(불공정). 요구: equal-budget 5-arm prereg. 성공 경계: equal cost 품질↑ **또는** 품질 유지 + cross-head inconsistency↓ + audit/replay↑. |
| Issue #2 (CLOSED) | 해결됨 | 기본 pytest가 `prom_search_hswm/` 120테스트 조용히 제외 + `gold_badiou24.json` fixture 부재 + README 라이선스 불일치(Apache 표기 vs AGPL/상용 듀얼). → PR #5 머지로 흡수 완료. |
| PR #3 (DRAFT) | 진행 중 | "endogenous hypergraph agent" thesis + `GENERIC_FEEDBACK_RUNTIME_ACCEPTANCE.md` — HSWM_LOCAL_RECORD verdict이 다음 dispatch를 인과적으로 바꾸는 수직 슬라이스를 완료 게이트로. |

## 1. 문제 ① — reasoner REFUTED / P5·B2.1 routing REJECTED (축B)

**문헌 판정: 우리 실패는 특이 사례가 아니라 재현된 보편 실패 모드다.**

- HetDocQA (arXiv 2606.28367): 강한 reranker 하에서 per-query routing·RRF·graph expansion **전부 유의 이득 없음**, oracle router조차 이득 미미 — "route할 신호 자체가 부재". HSWM late-RRF REJECTED의 **독립 외부 corroboration**. RRF 재투자 금지가 정답.
- EquiRouter (arXiv 2602.03478): routing collapse 원인 = scalar 예측→argmax 결정의 objective mismatch + small-margin regime(94.9% 쿼리서 margin≈0). train=test여도 붕괴. 처방 = ranking 목적함수.
- 성공 router(RouteLLM, MoE)의 공통 조건: 실재하는 신호 + 수만~수십억 라벨 — HSWM 규모에선 구조적으로 불가.

**처방:**
1. **주장 재포지셔닝**: "reasoner"가 아니라 LongMemEval 3-stage 모델의 indexing+retrieval stage. 벤치 표준 용어이며 F1 +0.073 1위가 정확히 이 stage 책임 범위. 후퇴 아님.
2. **실험 B-1 (oracle-recall ceiling 분해)**: LongMemEval_S에서 (a) HSWM top-k (b) oracle evidence (c) no-memory 3조건. (b)−(c) < 3pp면 "메모리가 reasoning을 향상" 주장 자체 REFUTED → 가치 축을 cost/latency/continuity로 이동. kill 조건 명확.
3. **실험 B-2 (routing 신호 존재성 측정, 학습 없는 하루짜리 측정)**: oracle gap < 2pp 또는 tie rate > 80%면 learned router 라인(B2.2+) 전부 prereg 단계 kill. 수개월 낭비 차단.
4. 다시 라우팅한다면 대상은 "전략"이 아니라 **reading 스타일/abstention** (HetDocQA서 유일 유의했던 레버).
5. Temporal 축 노리면 timestamp를 하이퍼엣지 메타데이터로 명시 색인 (Zep +18.5pp, LongMemEval time-aware +6.8~11.3% — 양쪽이 일치하는 유일한 레버).

## 2. 문제 ② — traversal OFF (축A)

**문헌 판정: 우리 관측은 문헌 예측과 일치한다. "모든 질의서 OFF"가 아니라 "Level-1 성향 평가서 OFF"일 가능성이 높다.**

- RAG vs GraphRAG (arXiv 2502.11371): fact 질의는 RAG가 이기고 multi-hop/reasoning 질의만 그래프가 이김. GraphRAG-only 13.6% vs RAG-only 11.6% — **보완적**. 라우팅/통합이 단일 방법보다 일관 우위.
- GraphRAG-Bench (arXiv 2506.05690): "basic RAG matches or outperforms GraphRAG in simple fact retrieval" — 우리 단조 악화와 동일 관측.
- 성공 조건 5종: 진정한 bridge 질의 / **이종 typed 엣지**(HippoRAG2 = relation+synonym+passage 3종) / 고품질 시드(LLM 필터링) / 그래프 커버리지(정답 entity 존재율이 상한) / query-aware 동적 엣지 가중 (arXiv 2602.01965가 HippoRAG2 PPR 위에서 유효 실증).
- **핵심 추측(검증 필요)**: 유사도 엣지만으로 propagation = cosine 재정렬 + 허브 바이어스라 구조가 추가 정보를 공급하지 않음 → 우리 "조밀 소풀 substrate 단조 악화"와 정합.

**처방:**
1. **실험 E1 (query-type 조걶부 traversal)**: bridge vs factoid subset 사전 분할, per-subset PPR ON/OFF. bridge에서 ΔF1 ≥ +0.02 & p<0.05면 판정을 "조걶부 OFF"로 개정, 아니면 "전 질의 OFF" 확정.
2. **실험 E2 (엣지 타입 통제 ablation)**: 실패가 확인된 조밀 substrate에서 (a) 전체 엣지 (b) typed 구조 엣지만 (c) +동적 가중. 신규 정답 evidence 도달율(정적 top-k에 없던 gold를 끌어온 비율)을 직접 측정 — 구조 기여의 정의.
3. 시드를 임베딩 top-k가 아니라 필터링된 entity 매칭으로; PPR restart α 스윕.
4. LinearRAG/SPRIG급 무학습 baseline 필수 포함(학습 GNN은 명시적 non-goal). LinearRAG이 우리 전파를 이기면 문제는 substrate가 아니라 구현.

## 3. 문제 ③ — 리프트 95% = 임베딩 (축A + 축C)

- 구조 load-bearing의 직접 ablation 선례: HyperGraphRAG (arXiv 2503.21322) — entity+hyperedge retrieval 동시 제거 시 StandardRAG 수준 붕괴. HGRAG (arXiv 2508.11247) — 구조 기여 실재하나 F1 +2% 상대로 **소수점 크기**. 문헌 전체가 "구조는 작게 싣는다"와 정합.
- HGMem (arXiv 2512.23959): 책-단위 NoCha/PRELUDE/NarrativeQA서 hypergraph working memory가 NaiveRAG/GraphRAG/LightRAG 상회. **핵심 ablation: hyperedge merging(고차 상관) 제거 시 최대 폭 하락** = 고차 구조 실효의 직접 증거. 단 LightRAG 대비 +1.6~3.2pt로 폭은 작음.

**처방 — 실험 E3 (hyperedge-as-unit load-bearing, 리프트 진단의 정면 falsification):**
- (a) 임베딩-only (b) +n-ary hyperedge 단위 검색 (c) +typed PPR, 제거 ablation 역방향 병행.
- **반드시 책-단위 substrate에서 1차 실행** (구조 이득은 정보 밀도 높은 코퍼스서 큼 — 문제 ④와 실험 통합).
- Kill: 책-단위에서조차 (b) < +0.01 F1 → "하이퍼엣지 구조는 리프트에 기여 없음" CONFIRMED → 연구를 임베딩-중심으로 재편. (b) ≥ +0.02 → 구조 load-bearing 최초 실측.

## 4. 문제 ④ — 책-단위 미실측 (축C)

**슬롯 선택 판정: NoCha는 최소비용 prereg에 부적합** (저작권 책 67권 직접 구매 + hidden test + pretraining 오염 논란). 대안:

- **1순위: PRELUDE (arXiv 2508.09848)** — 4권 public domain(몬테크리스토·봉신연의·삼국지연의·베른) 262 instances 저작권 프리, 88% 비국소 증거 요구, human 81.7 vs 최고 모델 ~65 headroom.
- **2순위: NarrativeQA** — Gutenberg 프리, HGMem의 10권 >100k tok 선례 재현 가능.
- QASPER = 문서-길이 축 하단 앵커.

**처방:**
1. **실험 C-1**: PRELUDE-public + NarrativeQA 10권서 (a) HSWM (b) 동일 임베딩 dense (c) HSWM→pairwise 그래프 환원 ablation. 1차 metric macro-F1 + evidence recall + **$/권 ingest 비용** (LazyGraphRAG 0.1% 사례가 비교 앵커 — embedding-only ingest의 저비용은 그 자체로 판매 포인트). 통계력 caveat: n=262는 ±6pt CI → 두 벤치 합산 prereg 명시.
2. **실험 C-2 (길이×홉 factorial)**: QASPER → NarrativeQA → 책-단위 3단계서 HSWM−cosine gap 단조성 = 합성 단조성이 실데이터 aboutness로 일반화되는지의 직접 검정.
3. 평가는 retrieval/evidence 단계 분리(GraphRAG-Bench식 2단) — reasoner REFUTED 상태에서 substrate 효과만 분리.

## 5. 문제 ⑤ — P6 absorption degenerating (축D)

**문헌 판정: 게이트가 "해롭다"와 "도움 안 된다"를 구분 못 했을 가능성. 되돌릴 수 있는 쓰기 + 2단계 게이트가 표준 처방.**

- 주류 게이트 3패턴: LLM 4-way 결정(Mem0 — 단, 2026년 비용/불안정으로 ADD-only 회귀 사례) / **temporal invalidation(Zep: mutation 대신 `t_valid/t_invalid` — 게이트 틀려도 롤백 공짜)** / deferral radius(GRACE: 편집 적용 범위 사전 판정).
- Sequential editing 붕괴의 mechanistic signature = norm growth (Gupta et al., arXiv 2502.01636) → 구조적 버전 = 신규 type quota.
- n-ary 흡수는 **schema induction 문제와 동형**: align→extend→new 3단 분류가 acceptance 전제 (arXiv 2604.02618).
- **검색 부재 확인: "메모리 쓰기 수용에 conformal risk 보증"을 단 문헌 없음 — HSWM이 선점 가능한 공백.**

**처방 — Prereg B-1 (shadow-gated n-ary absorption):**
1. 후보를 shadow subgraph에 먼저 적용 → canary probe(기존 지식 회귀, RippleEdits Preservation 대응) + fresh unseen probe(P6 동일 프로토콜) pre/post 실행 → canary 회귀 ≤ ε **그리고** fresh F1 비열등(Δ ≥ −δ)일 때만 PASS. **기각 사유가 "해로움" vs "무득"으로 진단 가능해짐** — Phase A 3/3 기각의 원인 규명을 겸함.
2. Mutation 금지, Zep식 supersession(valid_at/invalid_at)만 — Prereg B-2로 supersession vs mutation 대조.
3. Schema 3단 게이트 + new type quota(라운드당 ≤k).
4. 게이트 비용 상한: 1차 결정적 필터, 2차 LLM 판결은 통과분만 (mem0 퇴행 교훈).
5. Kill: 3라운드 연속 acceptance 0 → δ 완화 1회만 허용, 그래도 0이면 "현 metric 하 topology absorption 통과 불가" verdict.

## 6. 종합 — 외부 피드백(Issue #1)이 요구하는 마스터 실험 (축E)

리뷰어 가설("shared field ≥ separate heads, equal budget")은 **문헌이 지지하지 않는다** — MTL은 조걶부(공유는 상관 높은 task만), CocoCON은 통일 모델도 inconsistency 높다는 반증적 초기 조건. 즉 이건 확인 실험이 아니라 **진짜 falsification 설계**여야 하고, 그래서 가치가 있다.

**HSWM-E1 prereg 초안 (축E 산출, 리뷰어 arm 정의 그대로):**
- Arms: A1 frozen cosine / A2 HippoRAG2 또는 HyperGraphRAG / A3 분리 retriever+selector+revision 헤드(ConflictRAG급, strawman 방지) / A4 HSWM / A5 ablation×4.
- 데이터: TEMPRAGEVAL식 perturbation multi-hop temporal + TemporalWiki diff revision stream(k∈{1,3,10} 연속 revision + as-of + ripple 질의) + FreshQA식 outdated 슬라이스.
- Primary: **(P1) cross-decision disagreement rate — 표준 metric 부재, 자체 정의가 곧 기여**(retriever top-k에 정답 있는데 selector가 stale 선택한 비율 등, KILT provenance의 일반화로 방어) / (P2) stale rate × current preservation 쌍 / (P3) as-of EM / (P4) revision confluence(부활률+ripple 파괴율 — RippleEdits가 경고하는 실패 모드, 우리 `supersede()` decay가 정확히 취약).
- Equal budget: 전 arm 동일 offline judgment 예산 **또는** judgment-free metric 통일, 2안 모두 prereg 명시 + sensitivity 보고(불공정 지적 해소). 인덱스 빌드 비용까지 장부 등록.
- Kill: K1 A4≯A3 disagreement → 가설 reject/축소(리뷰어 경계 그대로). K2 A4≯A1 stale rate → supersession 무효 판정. K4 ablation 중 구분 불가 → 해당 요소 Occam 제거. K5 정산 2안 간 결론 뒤집힘 → 승리 주장 금지.
- 전제: HSWM 버전드 가중을 TGMS식 valid/transaction 이원 시간 의미론에 명시 매핑 못 하면 as-of 항목은 범위서 제외.

## 7. 우선순위 제안 (비용 대 정보 이득)

| 순위 | 실험 | 비용 | 답하는 것 |
|---|---|---|---|
| 1 | **B-2 routing 신호 측정** | ~하루, 학습 없음 | router 라인 전체의 생사 |
| 2 | **E1 query-type 조걶부 traversal** | 기존 substrate 재분석 수준 | TRAVERSAL_OFF의 범위 (전면 vs 조걶부) |
| 3 | **B-1 oracle-recall 분해** | LongMemEval_S 500문항 | reasoner REFUTED의 attribution (recall vs utilization) |
| 4 | **B-1(D축) shadow-gated absorption** | P6 파이프라인 재사용 | P6 기각 원인 규명 + Phase B 게이트 |
| 5 | **C-1+E3 통합 (PRELUDE 책-단위)** | 저작권 프리 4권, 중간 | 책-단위 + 구조 load-bearing 동시 판정 |
| 6 | **HSWM-E1 마스터 실험** | 최대 (A2/A3 구현 필요) | Issue #1 종결 — 1~5 이후 착수가 맞음 |

## 8. 정직한 caveat

- 2026년 arXiv(2602.x~2607.x) 다수는 미심사 프리프린트 + abstract/snippet 기반 인용. 수치 인용 전 원문 확인 필요(축별 리포트에 미fetch 목록 명시).
- Zep/Mem0/Hindsight의 효과 수치는 전부 vendor 자체 보고 — Memory Atlas 기준 측정 주첳별 수십 점 편차. 독립 재현만 신뢰.
- 문헌 성공 조건은 hotpot/musique/2wiki/도메인 코퍼스 측정 — E1~E3은 문헌 조건의 **재현 검정**이지 적용 보증 아님.
- 대화 메모리 벤치(LongMemEval/LoCoMo) 결과가 HSWM 표적(지식 substrate)에 전이되는지는 별도 검증 문제.
- "승자 시스템을 흡수하면 HSWM 고유 기여가 뭐냐"는 연구 정체성 문제는 실증이 답할 수 없음 — 사용자 판단 영역.
