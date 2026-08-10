# PROM16 negative-improvement agent-14 :: AXIS=D LENS=pitfalls

> item: AXIS=D 방법론 | LENS=함정 | FOCUS=2025~26 커뮤니티가 지적한 LLM 메모리 연구의 방법론 결함 — 포화 벤치마크, 라벨 노이즈 (LoCoMo 6~7%, LongMemEval ~5%), leakage, self-judge 편향. 우리 다음 라운드가 외부 리뷰어에게 맞을 비판 예측.

검증 완료. 최종 보고서 작성.

---

**한 줄**: 2025~26 커뮤니티 감사 결과 LLM 메모리 벤치마크의 4대 결함(라벨 노이즈 5~7%, 포화, retrieval-only 평가, 관대한 self-judge)이 확인됐고, 우리 다음 라운드는 "효과 < 노이즈 플로어" kill 조건과 judge catch-rate 검증을 내장해야 외부 리뷰에서 생존한다.

**핵심 발견**:
- **LoCoMo 라벨 노이즈 6.4% (score-corrupting)**: [locomo-audit](https://github.com/dial481/locomo-audit/blob/main/AUDIT_REPORT.md) (2026-02, Opus 4.6+인간 검수, SHA256 고정) — 1,540문항 중 99개 채점 오염 (hallucinated golden 33 / temporal 계산 오류 26 / 화자 attribution 오류 24). 이론적 점수 천장 **93.6%**. Multi-hop 카테고리는 9.9% 오류로 최악, single-hop 4.3%가 가장 신뢰 가능. 기존 신고(snap-research/locomo#27, 29건)의 5배. Northcutt 2021 기준(3.3% 오류로 랭킹 불안정)의 2배.
- **LongMemEval ~5%, LoCoMo 6~7%**: [Memanto (arXiv 2604.22085)](https://arxiv.org/abs/2604.22085) — 수동 검사로 라벨 불일치 확인, "label noise establishes a practical performance ceiling independent of memory architecture quality" + 두 벤치마크 모두 포화 임박 명시.
- **Retrieval-only 평가 함정**: [MemPalace issue #314](https://github.com/MemPalace/mempalace/issues/314) — R@K는 검색만 측정, reasoning 없는 raw vector 검색도 **R@5 96%** 달성; K 키우면 recall 인위 부풀림; "store everything"이 최적 전략(노이즈 페널티 부재); 공식 train/dev/test split 부재 → **test-set leakage·heuristic overfitting** 경고.
- **Judge 관대성 정량화**: [Mnemoverse 분석](https://mnemoverse.com/docs/research/evaluation/llm-as-judge-patterns) — Mem0의 LoCoMo grader 프롬프트가 "be generous, same topic = CORRECT"(gpt-4o-mini, 생성과 채점이 같은 모델). Penfield Labs 감사: **의도적으로 틀린 토픽-인접 답변 62.81%를 정답 처리** (단, 구체적 사실 오류는 ~89% 검출). Jain et al. 2025 agreeableness: TPR 96% vs **TNR <25%**. 하네스 의존성: Zep 65.99→75.14 (9pt 스윙), Mem0 반박분석 84%→58.44.
- **포화 대응 신세대 벤치마크**: [LongMemEval-V2 (arXiv 2605.12493, 원저자팀 UCLA)](https://arxiv.org/html/2605.12493v1) — 451 수동 큐레이션 문항, **frontier 4개 모델 no-context 정답률 최고 14.1% 검증 후 채택** (parametric 오염 방지), 잘못된 전제 탐지 abstention 문항, 고정 reader + 200k context cap, 최고 시스템도 74.9%. [HaluMem (arXiv 2511.03506)](https://arxiv.org/abs/2511.03506) — extraction/update/QA 단계별 hallucination·omission 분리 측정 (end-to-end만으로는 오류 국소화 불가).

**HSWM 이식 설계**:
- **Judge 적격성 게이트 (run 무효화 조건)**: 매 sealed run마다 planted "wrong-but-topical" 답변 세트를 judge에 통과시켜 catch rate 측정. **<90%면 run 무효**. judge는 generator와 다른 family + 2~3모델 jury, 200~500건 수동 라벨로 Cohen's κ 보고.
- **노이즈 플로어 kill 조건**: 새 testbed QA gold의 독립 재주석 샘플(≥10%)로 오류율 추정 → **효과 크기 < 라벨 노이즈 플로어면 claim 자동 kill**. 천장 보정 delta 보고 (raw accuracy 금지).
- **No-context baseline 게이트**: F3 신 testbed에서 donor/receiver 무주입 조건 정답률이 threshold 초과 시 "너무 쉬움/오염"으로 kill — LME-V2의 14.1% 패턴 모방.
- **F5 재설계용 단계별 메트릭**: HaluMem식으로 consolidation의 extraction/update/QA 단계별 hallucination·omission 분리 — "sleep이 detail을 깎았다"를 어느 단계 손실인지 국소화.
- **이중 보고**: retrieval (R@1 strict + MRR)와 end-to-end 분리, latency/token budget 동시 보고; dev/test split 고정으로 heuristic overfitting 차단.

**references**:
- https://github.com/dial481/locomo-audit/blob/main/AUDIT_REPORT.md (verified)
- https://arxiv.org/abs/2604.22085 (verified — abs 페이지 확인, 5%/6~7% 수치는 PDF 본문 검색 스니펫 원문)
- https://github.com/MemPalace/mempalace/issues/314 (verified)
- https://mnemoverse.com/docs/research/evaluation/llm-as-judge-patterns (verified)
- https://arxiv.org/html/2605.12493v1 (verified, 본문 직접 fetch)
- https://arxiv.org/abs/2511.03506 (verified — abstract)

**caveats**: Penfield Labs 62.81% 수치는 Mnemoverse 인용 2차 소스(원문 dev.to 미fetch, 비peer-review). Jain et al. 2025 TNR<25%는 Python 코드 검증 도메인 — QA judge로의 외삽 주의. LongMemEval ~5%는 Memanto 논문의 "manual inspection" 추정으로 체계 감사 아님. BEAM 벤치마크(LME-V2 Table 1 경유)는 원논문 미검증.
