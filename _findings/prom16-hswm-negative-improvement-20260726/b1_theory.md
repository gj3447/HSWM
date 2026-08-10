# PROM16 negative-improvement agent-4 :: AXIS=B LENS=theory

> item: AXIS=B consolidation | LENS=최신이론 | FOCUS=2025~26 LLM 에이전트 메모리 consolidation 최신 기법 — sleep-time compute (Letta/MemGPT 계열), hierarchical/typed memory (A-MEM, Zep/Graphiti, Mem0), summarization 기반 consolidation, selective forgetting, memory distillation. 핵심 질문: 어떤 연산이 append-only를 실측으로 이겼는가 (있으면 수치).

검증 완료. 최종 보고서를 작성한다.

**한 줄**: 2025~26 문헌에서 append-only를 실측으로 이긴 sleep 연산은 **hand-designed decay/downscale이 아니라 end-task reward로 학습된 "compact replacement + supersede" consolidation**(Auto-Dreamer +7pts/12× 작은 bank, Memory-R1)뿐이며, 무조건적 요약·축소는 HSWM K1 kill과 같은 방향으로 반복 실패하고 있다.

**핵심 발견**:

- **Auto-Dreamer (2026, 가장 직접적 대응)**: 세션 내 writer는 의도적으로 append-only, offline consolidator(GRPO, reward = end-to-end agent 성능)가 typed memory bank의 read-only region을 검사 후 **compact replacement set으로 supersede**. ScienceWorld +7점(고정 규칙/RL/prompted baseline 대비), active bank **12× 축소**, ALFWorld/WebArena 무재학습 전이(ALFWorld 6× 절감). → sleep 연산이 이기려면 **손설계 heuristic이 아니라 end-task reward로 학습**돼야 함. [arXiv:2605.20616](https://arxiv.org/abs/2605.20616)
- **Memory-R1 (2025)**: ADD/UPDATE/DELETE/NOOP를 outcome-driven RL(PPO/GRPO)로 학습, **152개 QA만으로** LoCoMo/MSC/LongMemEval SOTA, 3B–14B 일반화. UPDATE/DELETE가 유효하려면 정책 학습 필요. [arXiv:2508.19828](https://arxiv.org/abs/2508.19828)
- **Sleep-time Compute (Letta/Berkeley 2025)**: 동일 정확도에 test-time compute **~5× 절감**(Stateful GSM-Symbolic/AIME), sleep scaling 시 정확도 +13%/+18%, multi-query amortization 2.5×. 단 **효과는 query 예측가능성과 상관** — SWE-Features 사례에서 고예산에선 test-time-only가 역승(무조건 sleep은 손해). [arXiv:2504.13171](https://arxiv.org/abs/2504.13171)
- **적대적 증거 — Letta Filesystem (2025-08)**: LoCoMo에 대화 이력을 **통째로 파일에 넣고**(사실상 append-only) grep/semantic search만 준 GPT-4o mini 에이전트가 **74.0%** — Mem0 그래프 변형 68.5%를 능가. "에이전트 도구 사용 능력 > 메모리 구조 정교함". HSWM F5 K1 kill의 외부 에코. [letta.com/blog](https://www.letta.com/blog/benchmarking-ai-agent-memory)
- **Mem0**: LOCOMO LLM-Judge OpenAI 대비 +26% 상대, 그래프 +2%, p95 지연 −91%, 토큰 −90% (vs full-context). 단 자체 J=66.9 수준 — Letta FS 74.0에 아래. [arXiv:2504.19413](https://arxiv.org/abs/2504.19413)
- **Zep/Graphiti**: DMR 94.8% vs MemGPT 93.4%(**격차 1.4pp에 불과**), LongMemEval temporal +18.5%, 지연 −90%. 구조화 이득은 단순 검색이 아니라 **temporal/multi-hop에서만** 큼 — HSWM C1 음수 결과와 정합. [arXiv:2501.13956](https://arxiv.org/abs/2501.13956)
- **LightMem**: 3-stage(sensory→STM→LTM) + sleep-time offline update. QA 정확도 최대 +7.7%/+29.3%, 토큰 −38×/−20.9× ("up to" 수치). [arXiv:2510.18866](https://arxiv.org/abs/2510.18866)
- **MemoryOS**: STM/MTM/LTM + heat-based promotion, LoCoMo 평균 F1 +49.11% — 단 baseline이 약한 GPT-4o-mini 단순군. [arXiv:2506.06326](https://arxiv.org/abs/2506.06326)
- **ReasoningBank**: 성공+실패 궤적 양쪽에서 전략 수준 메모리 증류, raw-trajectory/성공-only 메모리 대비 우위(abstract 수준). HSWM typed lesson + ΔW와 구조 유사. [arXiv:2509.25140](https://arxiv.org/abs/2509.25140)

**HSWM 이식 설계 (F5 재설계)**:

- Arms: (A) append-only(현 K1 승자, null 유지) / (B) **Auto-Dreamer형**: prompted consolidator가 provenance 링크된 lesson region을 읽고 compact replacement hyperedge 생성 + `SUPERSEDES` 엣지(원본 보존, HSWM 정전의 supersession과 호환) / (C) downscale-decay(기살해군, 적대 대조로 유지) / (D) **query-conditioned sleep**: 예측된 미래 retrieval 빈도 > τ인 lesson만 consolidation 발동(sleep-time compute의 predictability 상관 이식).
- Metrics: detail 보존 slope(기존 F5 지표) + downstream QA 성공률 + bank 크기/토큰 비용 + supersede 후 원본 필요 시 회수율.
- Kill 조건: B가 A 대비 detail slope 또는 task 성공 중 하나라도 ≤이면 kill(= downscale paradox 재현이면 consolidation 계열 전체 shelve 확정). D는 예측 쿼리 분포와 실제 retrieval의 상관 ρ<0.3이면 kill.
- 2단계(후속): consolidator를 GRPO로 학습(reward = sealed task 성공) — Memory-R1/Auto-Dreamer 레시피.

**references** (fetch 검증 완료):
- https://arxiv.org/abs/2605.20616 · https://arxiv.org/abs/2508.19828 · https://arxiv.org/abs/2504.13171 · https://arxiv.org/abs/2504.19413 · https://arxiv.org/abs/2501.13956 · https://arxiv.org/abs/2510.18866 · https://arxiv.org/abs/2506.06326 · https://arxiv.org/abs/2509.25140 · https://www.letta.com/blog/benchmarking-ai-agent-memory · https://arxiv.org/abs/2502.12110 (A-MEM)

**caveats**: ① A-MEM은 abstract만 검증(정량 수치 미추출, "6개 모델서 SOTA" 정성 주장만). ② Sleep-time SWE-Features 고예산 역전은 논문 case study를 인용한 2차 요약(중국어 블로그·mnemoverse) 경유 — 원문 PDF 본문 직접 확인 못함. ③ Nemori(0.744) vs EMem(0.780)/full-context(0.806) 수치는 2차(chatpaper) — 미검증. ④ MemoryOS +49.11%는 약한 baseline 대비이며 append-only ablation 아님. ⑤ LightMem/Mem0 수치는 "up to" 마케팅형 상한. ⑥ LoCoMo 교차 논문 점수 비교는 논쟁 중(Letta가 Mem0의 MemGPT 재현 수치에 이의 제기, Mem0 무응답).
