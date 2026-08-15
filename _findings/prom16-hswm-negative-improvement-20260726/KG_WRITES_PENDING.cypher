// KG WRITES PENDING — prom16-hswm-negative-improvement-20260726
// KG(data-01, 192.168.0.25) SSH 타임아웃으로 미기록 (2026-07-26 세션). KG 복구 후 이 파일 통째로 실행.
// 관례: PromReport + Lesson(legacy_program_mechanism 필수, HR20) + ResearchFinding 16 (verified=true)

MERGE (p:PromReport {name: 'prom16-hswm-negative-improvement-20260726'})
SET p += {date: '2026-07-26', n_subagents: 16, conflicts: 0, axes: 'A transfer/B consolidation/C n-ary/D methodology',
  path: 'HSWM/PROM_16_NEGATIVE_RESULT_IMPROVEMENT_2026-07-26.md',
  raw: 'HSWM/_findings/prom16-hswm-negative-improvement-20260726/',
  target_negatives: 'F3 G=0 / F5 K1 kill / C1 clique -2.00pp',
  actor: 'kimi-code-cli'};

MERGE (l:Lesson {name: 'lesson-prom16-negative-improvement-20260726'})
SET l += {date: '2026-07-26', actor: 'kimi-code-cli',
  wrongAssumption: 'F3 G=0, F5 K1 kill, C1 clique kill은 연산자/구조의 결함이다',
  truth: '세 kill 모두 "측정 축 부재"의 측정값이다 — capability(F3는 procedural로)/query-predictability(F5는 read-time으로)/불가분성(C1은 clique-불가분 쌍으로) 축을 심으면 재시험 가능. 외부 2025~26 문헌이 독립 재현: naive cross-model 이식은 열화(MemCollab 50.6<52.2), lossy consolidation은 detail 파괴(CogCanvas verbatim +15.9pp, ARC-AGI 54% 회귀), clique expansion이 hypergraph를 자주 능가(Pellegrin NeurIPS25). 전이되는 것은 추상 메타지식뿐(MTL: 알고리즘 전이 5.5%), append-only를 이기는 건 augment-not-replace/dedup+gating/학습된 compact replacement뿐',
  legacy_program_mechanism: 'lemma-incorporation',
  evidence: 'HSWM/PROM_16_NEGATIVE_RESULT_IMPROVEMENT_2026-07-26.md + _findings/prom16-hswm-negative-improvement-20260726/ (16건, URL fetch 검증)',
  followup: 'PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md (ratify 대기)'}
WITH l
MATCH (p:PromReport {name: 'prom16-hswm-negative-improvement-20260726'})
MERGE (l)-[:FROM_CYCLE]->(p);

UNWIND [
  ['a1','theory','전이되는 건 추상 메타지식뿐 — MemCollab naive 열화(50.6<52.2)/대조증류 cross-family 유효(Llama8B 41.7→53.9), MTL Insight>Summary>Workflow>Trajectory·알고리즘 5.5%, Transplants headroom(3B +15pp vs 7B +6.7pp)'],
  ['a2','benchmarks','역량 축은 procedural에 실재 — DC 약모델 효과 미미(결함 전략 축적), AWM +24.6~51.1%, MemoryAgentBench 4역량 분리, MemDelta 통제 규약(임베딩 고정/패밀리 층화)'],
  ['a3','pitfalls','placebo 전이가 최대 함정(random retrieval ≈ similarity retrieval), receiver baseline 40~65% headroom zone, K1~K5 kill 설계(canary/4-cell/sham/judge catch)'],
  ['a4','recipe','harder testbed = ALFWorld형 procedural(ICD 0.18→0.87, hard tier 갭 유지) + 6arm + TRR + kill 3종, fact형 multi-hop은 역량 축 불가(Press 2210.03350)'],
  ['b1','theory','append-only를 이긴 건 학습된 compact replacement(Auto-Dreamer GRPO +7pts·bank 12×)뿐, sleep-time compute는 query 예측가능성과 상관, Letta FS 74.0>Mem0 68.5'],
  ['b2','benchmarks','CogCanvas: verbatim 43.9 vs extracted 28.0(+15.9pp, p<1e-15) + union store만 무해, ARC-AGI 강제 consolidation 정확도 절반, SeqMem-Eval slope/BWT/F(t) 표준'],
  ['b3','pitfalls','F5 kill 외부 독립 재현 — Neuromem 구조화 압축 F1 -50%, dedup-only 생존(97.2% retention·58% 절감), sleep 유비는 input-channel서 파탄(SleepGate 토이)'],
  ['b4','recipe','sleep 재설계 추천 = retrieval-time consolidation(write 위험 0·롤백 0), 차선 dedup/gated supersession, downscale은 adversarial control로만'],
  ['c1','theory','n-ary 우위는 표현층 아닌 검색경로층 — Pellegrin clique>hyper + 인코딩 결합 시만 표현력 상승, PRoH 경로추론 F1 +19.73%, OKH-RAG 순서축 0.534→0.487'],
  ['c2','benchmarks','판별 베드 = clique-불가분 world 쌍(simplicial closure/Hayashi 2006.16377 비식별), ZebraLogic k-ary clue·GraphWalks·PhantomWiki 생성 패턴'],
  ['c3','pitfalls','DHG-Bench heterophilic서 17 HNN 전부 MLP에 패배, homophily≤0.5 regime n-ary 손해(AAAI25), GraphRAG-Bench 토큰 377×/−24pp — 비용정규화 필수'],
  ['c4','recipe','C1 재시험 = 질의 타입≫팬아웃>스케일, marginal-matched null + joint-constraint QA + synergy 기울기, K1 hswm−clique<+3pp 시 shelve'],
  ['d1','theory','파워 Miller δ=3pp→n≈969·paired 1/3·cluster SE 3×, 소표본 CLT 붕괴(Bowyer), judge flip 13.6%·panel n_eff≈2(Kish), strong null=flat-file harness(AutoMEM)'],
  ['d2','benchmarks','부정→전환 사례 공통형 = 축 삽입+연산자 재정의+confound 고정(τ²-bench/Sleep-time/GraphRAG-Bench/Agent KB disagreement gate +18.7pp)'],
  ['d3','pitfalls','noise floor kill — LoCoMo 라벨 오류 6.4%·LongMemEval ~5%, judge catch-rate<90% run 무효, no-context baseline 게이트(LME-V2 ≤14.1%)'],
  ['d4','recipe','통합 prereg 골격 — ability-supported instance-disjoint split + Neuromem(압축 파괴적·결정론 parity) + SPB 패밀리 배제 + MDE +2~3pp 사전 산정']
] AS r
MERGE (f:ResearchFinding {name: 'rf-prom16-neg-imp-' + r[0] + '-' + r[1] + '-20260726'})
SET f += {cycle_id: 'prom16-hswm-negative-improvement-20260726', axis: r[0], lens: r[1],
  verified: true, date: '2026-07-26', summary: r[2]}
WITH f
MATCH (p:PromReport {name: 'prom16-hswm-negative-improvement-20260726'})
MERGE (f)-[:FROM_CYCLE]->(p);
