# PROM16 negative-improvement agent-12 :: AXIS=D LENS=theory

> item: AXIS=D 방법론 | LENS=최신이론 | FOCUS=2025~26 LLM 에이전트/메모리 연구의 실험 설계 표준 — preregistration 관행, strong null 대조 설계, LLM eval 통계 파워 (비용 하 n 확보), 이종 judge 구성, LLM eval variance 최신 실측.

**한 줄**: 2025~26 LLM eval 방법론의 수렴점은 "사전등록 + paired/clustered SE + 재표집 K회 + judge panel의 *유효* 독립표본(Kish n_eff) 보고"이며, HSWM의 sealed-run 체계는 이미 절반은 갖췄고 나머지 절반(파워 분석 기반 n 산정, judge 유효투표수, flat-harness 강대조)이 다음 사이클의 kill-survival 조건이다.

**핵심 발견**
- **파워/분산 (Miller, Anthropic, arXiv:2411.00640)**: δ=3pp, α=0.05, power 80% → 독립 문항 **n≈969** 필요. 문항-수준 **paired difference** 분석은 corr 0.5일 때 분산 1/3 감소. 같은 지문/월드에서 문항이 묶이면 **clustered SE** 필수 — naive SE는 최대 **3배 과소**. 재표집 K=2→분산 1/3↓, K=6→5/9↓(상한 2/3). 분산 줄이려고 temperature 내리기 금지(편향 주입).
- **소표본 CLT 붕괴 (Bowyer et al., ICML 2025 position, arXiv:2503.01747)**: 수백 개 미만 문항에서 CLT 기반 CI는 불확실성을 "dramatically underestimate" → Bayesian 대안 + 공식 Python 라이브러리 제공. HSWM처럼 고비용 sealed run(수십~수백 문항)은 정확히 이 영역.
- **Judge 신뢰도 실측 (Yagubyan, arXiv:2606.13685)**: 동일 judge·동일 문항 50회 반복에서 pairwise 판정 **13.6% flip**, 28% 문항이 flip>20%(최대 56%). GPT-4o-mini first-position bias **72% A-majority (p=0.024)**. pointwise 점수차 0.19–0.36/10점 = 유의하지 않은데 pairwise는 승자를 뽑아버림 → 절대점수 아닌 **delta + rerun 불확실성 보고**로 계약해야 함.
- **Judge panel의 착시 (Kohli et al., arXiv:2605.29800)**: 7개 패밀리 9 judge panel이 실제로는 **독립투표 ~2개분**뿐 (공명 독립성의 ~3/4 상실, 같은 문항에서 같은 실수). Panel 정확도가 독립투표 이상치 대비 **8–22pp 열위**, 최고 단일 judge가 panel 전체와 동등 이상. 집계 알고리즘 개선은 갭의 ≤11%만 회복. → **Kish n_eff로 유효 judge 수를 계산해 보고**하지 않으면 panel 구성은 허상.
- 단, 다양 패밀리 소형 모델 panel(PoLL)은 단일 대형 judge보다 intra-model bias 낮고 **7배 저렴**하며 우수 (Verga et al., arXiv:2404.18796) — 두 결과는 양립: 다양성은 돕되 상관오차가 상한을 정한다.
- **Preregistration (Vaccaro et al., arXiv:2606.11217)**: AI 에이전트 실험 전용 사전등록 템플릿 제안 — 연구자 자유도(모델 선택, 프롬프트 문구, 세팅, 결과-조건부 재설계)를 카탈로그화하고 동결을 요구. HSWM의 sealed+kill-condition 관행과 직접 대응.
- **강대조 (Chen et al., AutoMEM, arXiv:2606.04315)**: 메모리 시스템 8종 vs **tool-call로 flat text-file을 자기관리하는 harness** 대조 결과, harness가 cross-task 최고 순위. no-memory/placebo만으론 부족 — "능동 관리형 단순 baseline"이 최신 strong null.
- NIST AI 800-3 (2026.02, GLMM으로 between/within-question 분산 분해) — 실재 확인.

**HSWM 이식 설계**
- **Arms (F3 재설계 포함 전 클레임 공통)**: (a) HSWM, (b) receiver-own lessons, (c) placebo/shuffle lessons, (d) **flat-file self-managed harness**(AutoMEM식 강대조), (e) no-memory. 문항은 모든 arm에서 **동일 세트(paired)**, 시나리오/월드 단위 **cluster** 명시.
- **파워 게이트**: run 전 Miller Eq.9로 MDE 산정 — δ=3pp, power 80% 목표면 문항×재표집 설계를 n≥969에 맞추고, 못 맞추면 MDE를 사전등록에 명시(탐색적 전환 금지). 문항당 K=4~6 재표집으로 within-question 분산 절반으로 축소. 문항 수 수백 미만이면 CLT 대신 Bowyer Bayesian CI.
- **Judge 구성**: 3 judge × 이종 패밀리 + position swap-averaging + 항목당 5회 반복 다수결. 사전 게이트: flip율>20% 문항 비율이 28% 초과하거나 **Kish n_eff<2**면 unblind 전 panel 재구성. 보고는 절대점이 아닌 arm간 delta + rerun CI.
- **Kill conditions (사전등록)**: K1: HSWM−flat-harness < MDE이고 paired clustered CI가 0 포함 → 클레임 kill. K2: placebo−no-memory CI가 0 미포함 → 테스트베드 오염으로 run 전체 무효. K3: judge n_eff<2로 대체 불가 → 결과를 "judge-limited"로 강등.

**references**
- https://arxiv.org/abs/2411.00640 (verified, 본문 수치 인용)
- https://arxiv.org/abs/2503.01747 (verified abstract)
- https://arxiv.org/abs/2406.10229 (verified abstract)
- https://arxiv.org/abs/2606.13685 (verified abstract)
- https://arxiv.org/abs/2404.18796 (verified abstract)
- https://arxiv.org/abs/2605.29800 (verified abstract)
- https://arxiv.org/abs/2606.11217 (verified abstract)
- https://arxiv.org/abs/2606.04315 (verified abstract)
- https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.800-3.pdf (PDF 실재 확인)

**caveats**
- 2606.x/2605.x 논문들은 2026년 신규 preprint로 peer review 미통과; 수치는 저자 보고 그대로.
- "고분산 문항은 다수결 복원에 11–15회 필요"는 2차 소스(Emergent Mind) 경유 — Yagubyan 원문 본문 미검증.
- NIST AI 800-3는 PDF 존재만 확인, 내용 정독 못 함. Madaan(2406.10229)의 구체 분산 수치(예: seed variance 크기)는 abstract 수준에서만 확인.
