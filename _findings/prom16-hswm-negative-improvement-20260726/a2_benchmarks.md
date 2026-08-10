# PROM16 negative-improvement agent-1 :: AXIS=A LENS=benchmarks

> item: AXIS=A 전이 | LENS=벤치마크 | FOCUS=모델 역량이 갈리는 지식 종류를 만드는 벤치마크/데이터셋 생성법 2025~26 — transfer가 측정 가능한 task family 설계 (heldout F2), knowledge-type 분류 (procedural/semantic/meta), 최신 agent memory 벤치 (LongMemEval, LoCoMo 대안, MemoryBench류) 재사용 가능 자산.

검증 완료. 최종 보고서를 작성합니다.

**한 줄**: 전이 실패(F3)의 근본 해법은 "환경 결정 지식"이 아니라 **절차적(procedural) 레슨** — DC/AWM 계열 벤치마크가 이미 "강한 모델만 좋은 레슨을 만든다"는 역량 축을 정량 입증했고, MemDelta 프로토콜이 우리 kill-condition과 동형의 교란 통제를 제공한다.

**핵심 발견**:
- **Dynamic Cheatsheet (EACL 2026, [arXiv 2504.07952](https://arxiv.org/abs/2504.07952))** — 역량 축의 직접 증거. Claude 3.5 Sonnet AIME 2024 23%→50%(+27pp), AIME 2025 +30pp, Game of 24 GPT-4o 10%→99%(Python solver 스니펫 발견·재사용), 방정식 45~50%→98~100%. **결정적 발견: GPT-4o-mini급 약모델은 DC 효과 미미 — "올바른 해를 처음에 거의 생성 못 해 메모리가 결함 전략으로 채워짐. DC는 이미 강한 모델을 증폭할 뿐 기초 격차를 못 메운다."** 지식집약 과제(GPQA-Diamond +9pp, MMLU-Pro +8pp)로 가면 효과 급감 → 절차적 레슨에서만 역량 차가 크다. 코드 공개(github.com/suzgunmirac/dynamic-cheatsheet).
- **AWM ([arXiv 2409.07429](https://arxiv.org/abs/2409.07429))** — 유도된 workflow(절차 지식) 주입으로 Mind2Web +24.6%, WebArena +51.1% 상대 성공률; train-test 분포 격차가 커질수록 +8.9~14.0pp 절대 이득 → heldout 설계와 동형.
- **MemoryAgentBench (ICLR 2026, [arXiv 2507.05257](https://arxiv.org/abs/2507.05257))** — 4 역량 분리: Accurate Retrieval / **Test-Time Learning** / Long-Range Understanding / Conflict Resolution. 기존 long-context 데이터를 incremental multi-turn으로 변환 + 신규 EventQA·FactConsolidation. 제3자 인용 기준 multi-hop conflict resolution은 전 시스템 ≤7% = 역량 차이 최대 구간이지만 저파워 위험.
- **MemDelta ([arXiv 2606.29914](https://arxiv.org/html/2606.29914v1))** — 우리 kill 문화와 동형. 임베딩 교체만으로 +6.2pp(p=0.004) → Mem0-vs-RAG 결론 반전; 모델 패밀리에 따라 같은 비교가 −31pp(Sonnet, 63% 거부)~+14pp(Gemini)로 반전; **agent self-memory 42% < 단순 retrieval 47%** (F5 실패와 같은 방향); Mem0는 cloud-RAG와 동점인데 write 비용 50×. 권고: 임베딩 고정·2+ 모델 패밀리·random retrieval 통제·write-path 비용 보고·McNemar matched-instance.
- **LongMemEval (ICLR 2025, [arXiv 2410.10813](https://arxiv.org/abs/2410.10813))** — 500문항 6유형(추출 70·assistant 56·선호 30·시간 133·**지식갱신 78**·다중세션 133), S=115k/M=1.5M 토큰. knowledge-update 유형이 credit·supersession 시험대로 직접 재사용 가능. **LoCoMo ([arXiv 2402.17753](https://arxiv.org/abs/2402.17753))** — 10대화 ×~300턴, adversarial(무답) 유형은 abstention 교정용.
- **MemoryBench ([arXiv 2510.17281](https://arxiv.org/abs/2510.17281))** — 사용자 피드백 축적 기반 continual learning 시뮬레이션 프레임워크(다도메인·다언어), 절차 메모리 평가에 특화.

**HSWM 이식 설계 (F3 재설계)**:
- *Task family*: PhantomWiki(semantic only)를 유지하되 **procedural split 추가** — Game-of-24류 합성 퍼즐군에 "발견 가능한 최적 전략"(F2의 planted ground truth 관습 유지)을 심고, semantic/meta 레슨은 LongMemEval knowledge-update 유형으로.
- *Arms*: donor(27b)레슨 → receiver(14b) vs receiver 자기레슨 vs random-strategy vs placebo 텍스트(형식 동일·내용 무관). 지표 = Δ(donor−own) 성공률, paired McNemar + bootstrap CI.
- *Kill conditions* (사전등록): (K1) Δ CI가 0 포함 → G=0 재확정; (K2) placebo = donor → 내용 무관 프롬프트 효과로 kill; (K3) 임베딩/검색 교란 배제 — MemDelta식 고정 + random retrieval 대조; (K4) donor-strong→receiver-strong 자기전이는 성립하는데 cross만 G=0이면 "역량 격차 메타레슨" 가설로 분기.

**references**:
- https://arxiv.org/abs/2504.07952 (DC, 검증됨)
- https://arxiv.org/abs/2409.07429 (AWM, 검증됨)
- https://arxiv.org/abs/2507.05257 (MemoryAgentBench, 초록 검증)
- https://arxiv.org/html/2606.29914v1 (MemDelta, 전문 검증)
- https://arxiv.org/abs/2410.10813 (LongMemEval, 초록 검증)
- https://arxiv.org/abs/2402.17753 (LoCoMo, 검증됨)
- https://arxiv.org/abs/2510.17281 (MemoryBench, 초록 검증)

**caveats**: AgentMemoryBench(OpenReview MSXbrNExax, forward/backward transfer·replay/repair 모드)는 봇 차단으로 본문 미검증 — 검색 스니펫만. MemoryAgentBench의 역량별 정확 수치 미추출(≤7% conflict 천장은 제3자 README 인용). DC 논문의 모델 간 메모리 이식(transferability) 실험 절은 미검증 — 역량 게이트 문장만 확인. MemoryBench 규모(~20k)는 2차 서베이 출처.
