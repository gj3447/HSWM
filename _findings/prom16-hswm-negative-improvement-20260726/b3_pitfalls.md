# PROM16 negative-improvement agent-6 :: AXIS=B LENS=pitfalls

> item: AXIS=B consolidation | LENS=함정 | FOCUS=consolidation/summarization/decay 연산이 실패한 선행 사례 2025~26 — 요약이 detail을 죽인 실측, importance/salience 감쇠의 역효과, 인간 sleep consolidation 유비가 LLM에서 깨진 사례. 우리 downscale 역설(consolidation arm slope −0.158 vs no-op −0.097, CI 유의)의 외부 대응물.

**한 줄**: 2025~26 실측 문헌이 HSWM F5 kill과 정확히 같은 결론을 보고한다 — LLM consolidation은 detail을 파괴하고(verbatim 대비 −15.9~−22.0pp), 강제 consolidation은 no-memory baseline 이하로 떨어지며(GPT-5.4가 이미 푼 문제의 54% 실패), 살아남는 건 "요약/감쇠"가 아니라 "dedup·supersession·gating"뿐이다.

**핵심 발견**

- **Lossy distillation이 detail을 죽인다 (우리 downscale 역설의 직접 대응물)**. 통제 ablation(모델·retriever·judge 고정, 저장 표현만 교체)에서 verbatim chunk가 추출 artifact를 LoCoMo 43.9% vs 28.0%(+15.9pp), LongMemEval-S 67.4% vs 45.4%(+22.0pp)로 압살. 메커니즘은 구조가 아니라 **손실 압축 자체** — "accuracy tracks how much source text survives". 구조화 메모리는 verbatim을 *대체*하면 실패, *병존*(augment)하면 유지 ([arXiv 2601.00821](https://arxiv.org/abs/2601.00821)).
- **Consolidation이 진행될수록 utility가 상승 후 하락, no-memory baseline 이하로**. ARC-AGI Stream에서 Retain/Delete/Consolidate 액션 노출 시 에이전트는 raw episode 보존을 디폴트로 선택, 강제 consolidation 대비 **정확도 2배**; consolidation 전면 비활성화(episodic-only)가 auto regime과 동률. 심지어 ground-truth solution에서 consolidate해도 GPT-5.4가 이전에 풀었던 문제의 **54%를 실패**. 회귀 원인은 경험이 아니라 consolidation step 자체 ([arXiv 2605.12978](https://arxiv.org/abs/2605.12978)).
- **살아남은 consolidation = 요약 없는 dedup**. 6-기제 인간 유사 아키텍처(sleep consolidation 포함)가 LongMemEval 200K 예산에서 raw retrieval과 통계적 동률(70.1% vs 71.2%, CI 중첩), S-tier preference recall +13.3pp, 58% store 절감에 97.2% retention precision — 단 핵심 기제가 "summarizing이 아니라 **deduplicating**"이며, MemGPT식 rolling summarization은 "error를 누적(compounds)한다"고 명시 ([arXiv 2605.08538](https://arxiv.org/abs/2605.08538)).
- **Sleep 유비는 input-channel에서는 깨진다**. SleepGate는 proactive interference를 O(n)→O(log n)으로 줄였다 주장하지만 (a) KV-cache 수술 + dual-phase **학습**이 필요하고 (b) 검증은 793K 파라미터 토이 모델. 프롬프트/저장소 수준 sleep 유사체(baseline 5종 전부 <18%)로는 재현 불가 — LLM 가중치 동결 + input-channel 제약의 HSWM에는 이식 불가 ([arXiv 2603.14517](https://arxiv.org/abs/2603.14517)).
- **실무자 증거: decay는 건너뛰는 레버, summarize-and-drop은 deprecated**. 4-lever 프레임워크(importance/merge/decay/eviction)에서 decay "너무 공격적으로 튠하면 사용자 이름을 잃는다"; LangChain `ConversationSummaryMemory` 계열은 "compaction이지 consolidation이 아니"며 entity detail 손실로 폐기 수순; eviction은 compliance 전용 ([Hindsight 블로그](https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation)).

**HSWM 이식 설계 (F5 재설계안)**

- Arm 구성: (C) no-op append-only [기존 컨트롤] / (D) **dedup+supersession**: 동일 referent lesson의 구버전에 `invalid_at` 마킹, 본문은 verbatim 유지(2605.08538식) / (E) **augment-not-replace**: consolidation 출력을 원본 lesson *옆에* 추가, 원본 절대 치환 금지(2601.00821식) / (G) **gated consolidation**: 주기적 발화 금지, conflict/supersession 검출 시에만 발화(2605.12978의 "gate explicitly").
- Metrics: detail preservation slope(기존), planted-fact verbatim recall, supersession QA 정확도, store 크기, per-turn token.
- Kill conditions: 어떤 arm도 detail slope가 C 대비 유의하게 낮으면 kill(기존 K1 재사용); E/D/G가 episodic-only(C)를 이기지 못하면 해당 arm kill — "consolidation은 이점을 입증해야 하고, 디폴트 발화는 증거 없이 정당화 불가"가 2026 컨센서스.

**references** (전부 fetch 검증 완료)
- https://arxiv.org/abs/2601.00821
- https://arxiv.org/abs/2605.12978
- https://arxiv.org/abs/2605.08538
- https://arxiv.org/abs/2603.14517
- https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation

**caveats**: 2605.12978의 "정확도 2배"·54% 수치는 abstract 수준(본문 테이블 미확인); SleepGate 수치는 토이 스케일 abstract 자기보고; Hindsight 블로그의 벤더 리더보드 수치(94.6% 등)는 벤더 자체 측정이라 독립 검증 안 됨; importance/salience *감쇠* 단독의 역효과를 분리 측정한 정량 연구는 찾지 못함(decay 실패는 주로 요약/강제발화와 혼재).
