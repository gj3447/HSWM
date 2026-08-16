# PROM 16 — HSWM 부정결과 개선: 최신 AI 기술 흡수 (2026-07-26)

> cycle `prom16-hswm-negative-improvement-20260726`. 16 subagent (4축: A 전이 / B consolidation / C n-ary / D 방법론 × 4렌즈: theory/benchmarks/pitfalls/recipe), 16/16 완주, 충돌 0.
> 대상 부정결과: **F3 전이 G=0/S=0** (환경-결정 지식) / **F5 consolidation K1 kill** (downscale 역설) / **C1 n-ary 고유기여 미검출** (clique −2.00pp kill).
> raw: `_findings/prom16-hswm-negative-improvement-20260726/` (a1~d4, 16건, URL fetch 검증 표기).

---

## 0. 사전 지식

- F3 r3 sealed (`receipts/f3r3_agent_ab_transfer_sealed_1784996298.json`): donor 27b → receiver 14b, G=0.0 (CI [0,0]), S=0.0. 삼중 실증으로 PhantomWiki엔 모델-품질 축 없음 (`lesson-f3-environment-determined-knowledge-20260725`).
- F5 sealed (`receipts/f5_consolidation_sealed_1784998952.json`): A(wake+sleep) slope −0.158 vs C(no-op) −0.097, CI [−0.098,−0.024] — sleep 감쇠가 detail 보존을 유의하게 해침. append-only 전 lag δ 이내.
- C1 PRELUDE (`GIT/HSWM/C1_PRELUDE_BOOKSCALE_RESULTS_2026-07-25.md`): hswm−dense +3.16pp low-power, hswm−clique −2.00pp kill.
- 선행 PROM: `PROM_16_UNPROVEN_CLAIMS_2026-07-25.md` (4-arm sealed + prereg kill이 유일 경로) + axis B 전이 설계 (`PROM_16_UNPROVEN_B_AGENT_AB_TRANSFER_2026-07-25.md` — MemCollab/MTL/PAM 1차 소스 확보済).

---

## 1. Consensus

**C1 — F3 G=0은 예상된 null이었다: 모델 간 실제로 전이되는 것은 "추상화된 메타지식"뿐.** (a1/a4/b2)
2025~26 실증이 일치: MTL(ICML 2026, 2604.14004) — 전이량은 추상화 수준이 결정 (Insight > Summary > Workflow > Trajectory, Insight +4.0~8.3%), **알고리즘 전략 전이는 이득의 5.5%뿐**, 본체는 검증 루틴·가드레일·워크플로 메타지식. MemCollab(2603.23234) — naive cross-model 이식은 **열화** (7B+32B메모리: MATH500 50.6 vs vanilla 52.2, HumanEval 34.1 vs 42.7); 대조 증류 `(enforce; avoid)`는 cross-family 유효 (Llama-3-8B 41.7→53.9, Qwen-32B 70.8→78.2). 사실형 multi-hop QA는 compositionality gap이 스케일 불변(Press 2210.03350)이라 **역량 축 자체가 안 생김** — PhantomWiki의 F3 null과 정확히 대응.

**C2 — 역량 축은 "procedural"에만 실재한다: harder testbed = 절차 환경 + receiver headroom 40~65% + disagreement gate.** (a2/a4/d2)
Dynamic Cheatsheet(2504.07952): Claude AIME +27~30pp, GPT-4o Game-of-24 10%→99% (Python solver 전략 발견·재사용) — 단 **약모델은 DC 효과 미미: "올바른 해를 처음에 못 만들어 메모리가 결함 전략으로 채워진다"** = 역량 축의 직접 실증. In-Context Distillation(2512.02543): frozen student ALFWorld 0.18→0.87 (teacher 시연 주입만으로, hard tier에서 갭 유지 0.43 vs 0.71). Agent KB(2507.06229): 이종 에이전트 전이는 raw 복사로 실패 → **disagreement gate**(검색 지식이 추론 방해 시 폐기)로 성립, GAIA pass@3 55.2→73.9 (+18.7pp). Memory Transplants(ICLR 2026 wksp): **약한 receiver +15pp vs 강한 receiver +6.7pp** (headroom 가설). 수신자는 baseline 40~65% 구간, donor↔receiver gap ≥15pp, cross-family 팔 필수 (same-family는 shared-prior confound).

**C3 — F5 K1 kill은 외부에서 독립 재현됐다: lossy consolidation은 detail을 죽인다 (우리 downscale 역설의 대응물 다수).** (b1/b2/b3/d4)
CogCanvas(2601.00821): 저장 표현만 교체하는 통제 ablation에서 verbatim 43.9% vs LLM-extracted 28.0% (+15.9pp, p<10⁻¹⁵), LongMemEval-S +22.0pp, budget-matched control도 1.2pp만 회복 → **"결핍은 할당이 아니라 정보 손실"**. ARC-AGI(2605.12978): 강제 consolidation 시 정확도 절반, ground-truth로 consolidate핵도 기존 정답의 **54% 실패**, episodic-only ≥ 전 consolidator. Neuromem(2602.13967): LLM 주도 consolidation은 unmaintained와 동일 ~22% 열화, 구조화 압축 시 F1 −50%+, 결정론 휴리스틱(heat migration)이 생성형 개입과 parity. Letta Filesystem: 통째 파일+grep 74.0% > Mem0 그래프 68.5%.

**C4 — append-only를 이기는 consolidation은 3가지뿐: augment-not-replace / dedup+supersession gating / (학습된) compact replacement. sleep 재설계 1차 추천 = retrieval-time consolidation.** (b1/b3/b4)
생존 arm: ① union store (verbatim 보존 + gist 증강, CogCanvas에서 유일 무해) ② dedup+supersession (2605.08538: 97.2% retention·58% 절감, "핵심은 요약이 아니라 dedup", rolling summarization은 오류 누적으로 명시 기각) ③ Auto-Dreamer(2605.20616): end-task reward GRPO consolidator +7pts·bank 12× 축소 — **손설계 heuristic이 아니라 학습된 연산만이 이김**. Sleep-time compute(2504.13171)는 query 예측가능성과 상관 (고예산 역전 사례 존재). **재설계안 (b4 추천 채택): 1차 = retrieval-time consolidation** (write=순수 append-only 유지, read 시 쿼리별 재조립 — 저장층 위험 0, 롤백 비용 0) + 차선 = dedup/gated supersession (충돌 검출 시에만 발화). downscale-decay는 기살해군(adversarial control)으로만 유지.

**C5 — C1 kill도 외부 정합: n-ary 우위는 표현층이 아니라 "검색·추론 경로층"에서만 발생하며, 판별은 clique-불가분 world 쌍뿐.** (c1/c2/c3/c4)
Pellegrin/Fesser/Weber(NeurIPS 2025, 2502.09570): 자연 하이퍼그래프 입력에서도 graph-level + clique expansion이 hypergraph-level을 자주 능가 — 단 **hypergraph 인코딩을 graph 모델에 결합하면 증명 가능한 표현력 상승+성능 향상** (C1 결과와 정확히 일치: 구조 자체가 아니라 활용 방식). DHG-Bench(2508.12244): heterophilic에서 17종 HNN 전부 MLP에 패배/동률, 효율 9~406× 손해 — **homophily ≤0.5 regime에선 n-ary 실행 자체가 손해** (AAAI 2025). PRoH(WWW'26, 2510.12434): n-ary 경로추론으로 HyperGraphRAG 대비 F1 +19.73% (3~6홉서 81.01 vs 52.40) — 이득의 원천은 경로 탐색. 판별 베드: **clique projection은 동일하지만 hyperedge가 다른 world 쌍** (simplicial closure 문제; Hayashi/Aksoy 2006.16377 — weighted clique+dual로도 비식별) + marginal-matched null. RAGSearch(2604.09666): 구조 이득은 multi-hop +27.23 EM vs general +0.47 — **질의 타입이 지배 변수** (C1의 실패는 스케일이 아니라 질의 타입).

**C6 — 방법론: 파워·judge·noise floor 3종을 공통 섀시에 신설해야 다음 라운드가 외부 리뷰에서 생존한다.** (d1/d3/d4)
파워: Miller(2411.00640) — δ=3pp·power 80% → n≈969 (paired 분석 시 분산 1/3, cluster SE는 naive의 3배); 소표본(<수백) CLT 붕괴 → Bowyer(2503.01747) Bayesian. Judge: 동일 judge 50회 반복에서 13.6% flip (2606.13685), 9-judge panel의 유효 독립투표 ≈2 (Kish n_eff, 2605.29800), Qwen 계열 self-preference 최대 (SPB 2604.22891) → **이종 패밀리 panel + position swap + planted "wrong-but-topical" catch-rate <90% 시 run 무효**. Noise floor: LoCoMo 라벨 오류 6.4% (locomo-audit), LongMemEval ~5% — **효과 크기 < noise floor면 claim 자동 kill**, no-context baseline 게이트 (LME-V2: frontier 4개 모델 ≤14.1% 검증 후 채택). Strong null: AutoMEM(2606.04315) — **tool-call flat-file 자기관리 harness**가 메모리 시스템 8종을 이김 → 다음 라운드 대조군에 필수 편입.

**C7 — 세 kill의 공통 패턴: "축이 없었다"는 측정이지 실패가 아니다. 다음 라운드는 축을 심는다.** (전 축)
F3 = capability 축 부재 (procedural로 삽입) / F5 = query-predictability 축 부재 (read-time으로 이동) / C1 = 불가분성 축 부재 (clique-불가분 쌍으로 삽입). kill 조건이 설계를 좁히는 전형적 progressive 패턴 — 부정→전환한 선행(τ²-bench, GraphRAG-Bench, Sleep-time Compute)도 전부 "난이도/조건 축 삽입 + 연산자 목적 재정의 + confound 1개씩 고정"의 같은 형태.

---

## 2. Divergence

- **D1 — 전이 testbed 선택**: 신환경(ALFWorld/TextWorld형, a4 — 실측 역량갭 71pp의 직접 계보) vs **기존 PhantomWiki 생성기 확장 + procedural split** (a2/d2 — planted ground truth 관습·sealed 인프라 재사용). 보고서 판단: 후자 우선(인프라 재사용), 단 hard-tier 역량갭 ≥15pp 사전검증을 환경 채택 게이트로.
- **D2 — sleep: learned consolidator 즉시 착수(b1, Auto-Dreamer식 GRPO) vs 단계적(b4: retrieval-time → dedup gating → GRPO)**. K1 교훈상 무학습 변형부터 kill 검증하는 단계적이 우세; GRPO는 R0/R1 생존 시 2단계.
- **D3 — n-ary 재시험 축**: c2(불가분 world 쌍 생성) vs c4(질의 타입 ≫ 팬아웃 > 스케일) — 모순 아님, 병합: 불가분 쌍 + joint-constraint 질의 + homophily 사전게이트를 한 생성기(PhantomCliqueTrap)로.

---

## 3. Open Questions

1. 로컬 vLLM(192.168.0.23:8000)에 **비-Qwen family 모델**(Gemma/Llama/GLM) 서빙 가능한가 — cross-family donor + 이종 judge panel의 물리적 전제.
2. 파워 n≈969 vs 공유 vLLM 비용(F2가 400문항에 4901콜/5.3h) — MDE를 +2pp로 고집할지, +3~5pp로 완화해 n을 줄일지 (prereg에 MDE 명시 의무).
3. procedural world 생성기: PhantomWiki 확장 vs TextWorld 외부 의존 도입 — canary probe("②③ 지식이 donor 경험 없이 도출 불가" 확인)로 결정.
4. judge catch-rate 게이트를 기존 F1~F5 영수증에 소급 적용할지 (과거 run의 judge 적격성은 미측정).

---

## 4. 권장 후속 작업

- **P0**: ① **F3v2 harder transfer prereg 착수** — `PREREG_F3V2_HARDER_TRANSFER_2026-07-26.md` (본 세션 작성: procedural split + 6arm + TRR + kill 5종) ② **F1 sealed 재발사** (r3 유실 확인 — 이전 세션 백그라운드 발사분 미완, 승인 필요) ③ 공통 섀시에 judge catch-rate 게이트 + noise-floor kill 편입.
- **P1**: F5v2 prereg (retrieval-time consolidation 1차 + dedup gating 차선, downscale은 adversarial control) / PhantomCliqueTrap 생성기 스펙 (불가분 쌍 + joint-constraint + homophily 게이트).
- **P2**: GRPO consolidator (R0/R1 생존 시) / 비-Qwen 모델 확보 / flat-file strong-null arm 표준화 / Zenodo DOI.

---

## 부록. 1차 소스 (전부 fetch 검증, 각 finding에 per-claim 표기)

- 전이: MemCollab 2603.23234 / MTL 2604.14004 / PAM 2605.11032 / Memory Transplants (ICLR26 wksp) / Dynamic Cheatsheet 2504.07952 / In-Context Distillation 2512.02543 / Agent KB 2507.06229 / Track 2601.15495 / Press 2210.03350 / EvoAgentBench 2607.05202
- consolidation: Auto-Dreamer 2605.20616 / Memory-R1 2508.19828 / Sleep-time Compute 2504.13171 / CogCanvas 2601.00821 / ARC-AGI consolidation 2605.12978 / Neuromem 2602.13967 / dedup-arch 2605.08538 / RMM 2503.08026 (ACL 2025) / Infini-Memory 2606.10677 / Mem0 2504.19413 / Zep 2501.13956 / Letta FS blog
- n-ary: Pellegrin/Weber 2502.09570 (NeurIPS25) / PRoH 2510.12434 (WWW'26) / HyperGraphRAG 2503.21322 / OKH-RAG 2604.12185 / HyperRAG 2602.14470 / DHG-Bench 2508.12244 / AAAI heterophily (CityU PDF) / GraphRAG-Bench 2506.05690 / RAGSearch 2604.09666 / Simplicial Closure (PNAS 2018) / Hayashi-Aksoy 2006.16377 / ZebraLogic 2502.01100
- 방법론: Miller 2411.00640 / Bowyer 2503.01747 / judge-flip 2606.13685 / panel-n_eff 2605.29800 / PoLL 2404.18796 / SPB 2604.22891 / prereg-template 2606.11217 / AutoMEM 2606.04315 / MemDelta 2606.29914 / locomo-audit (github dial481) / Memanto 2604.22085 / LME-V2 2605.12493 / HaluMem 2511.03506 / SeqMem-Eval 2605.15384 / NIST AI 800-3
