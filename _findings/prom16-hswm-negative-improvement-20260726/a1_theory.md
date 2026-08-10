# PROM16 negative-improvement agent-0 :: AXIS=A LENS=theory

> item: AXIS=A 전이 | LENS=최신이론 | FOCUS=2025~26 cross-model/cross-agent memory·knowledge transfer 최신 논문 (MemCollab 2603.23234, MTL 2604.14004, PAM 이후 포함). 어떤 지식 타입이 실제로 모델 간 전이되는가 — model-specific bias(b)와 task structure(s) 분리 최신 기법. donor≠receiver family에서 유효했던 실측 사례.

**한 줄**: 2025~26 최신 실증의 일치 결론 — 모델 간 실제로 전이되는 것은 사실(fact)·궤적(trace)이 아니라 **추상화된 메타지식(검증 루틴·오류 금지 패턴)** 이며, naive 레슨 직접 이식은 model-specific bias(b)가 얽혀 baseline 이하로 떨어진다 → HSWM F3의 G=0은 예상된 null이었고, 해법은 **contrastive distillation(s/b 분리) + capability headroom 설계**다.

**핵심 발견**

- **[MemCollab (arXiv 2603.23234v2, PSU/AG2AI, 2026-05)](https://arxiv.org/html/2603.23234v2)** — τ=f(s,b) 형식화의 정본. naive cross-model 이식은 **열화**: 7B agent에 32B 메모리 주입 시 MATH500 50.6 vs vanilla 52.2, HumanEval 34.1 vs 42.7. donor+receiver 궤적을 동일 task에서 대조해 `(enforce i_k; avoid v_k)` 제약으로 증류하면: 7B 52.2→**67.0** (MATH500), 47.9→57.6 (MBPP). **Cross-family 실측**(Llama-3-8B ↔ Qwen2.5-32B): Llama avg 41.7→**53.9** (self-memory 45.6, 32B-memory 36.3=vanilla 이하), Qwen-32B 70.8→78.2. 검색은 task-category 1차 필터 → model-identity 라벨(ℓ⁺,ℓ⁻) 2차 필터 → top-3 (그 이상은 오히려 감소, 비단조).
- **[MTL (arXiv 2604.14004, ICML 2026, KAIST/NYU)](https://arxiv.org/html/2604.14004v1)** — 6개 코딩 벤치마크 cross-domain +3.7% avg. 전이량은 **추상화 수준이 결정**: Insight > Summary > Workflow > Trajectory; Insight는 4개 벤치에서 +4.0~8.3%. **알고리즘 지식 전이는 이득의 5.5%뿐** — 나머지는 메타지식(검증 루틴, 가드레일, minimal-patch 훈련). 동일 포맷 내에서도 task-agnostic > task-specific (Table 4) → 포맷이 아니라 추상화가 인과. Cross-model 실측: GPT-5-mini → DeepSeek V3.2 **+2.6%**, Qwen3-Coder **+1.8%**, 양방향 유효. 메모리 431개가 AgentKB 5.8k를 이김. 부정 전이 3유형: domain-mismatched anchoring / false validation confidence / misapplied best-practice.
- **[PAM (arXiv 2605.11032, 2026-05)](https://arxiv.org/html/2605.11032v1)** — Claude↔GPT-4↔Gemini 간 TCS 0.83–0.92 (no-memory 0.28–0.45, 2.4×). **전이성 그래디언트: semantic(사실) 가장 깨끗, working/planning 최악 = "working memory는 본질적으로 model-specific"**. RHF는 25% 토큰 예산에서도 0.71 유지.
- **[Memory Transplants (MemAgents Workshop @ ICLR 2026)](https://openreview.net/attachment?id=AIJsjIqfsp&name=pdf)** — HSWM식 적대 설계의 선행 사례: architecture vs content 2×2 분리, 6개 preregistered gate + 4종 null control(random retrieval/placebo/write-only/frozen-store MU). **solver capability가 전이량을 조절: 약한 3B +15pp vs 강한 7B +6.7pp** (headroom 가설). static content 전이는 제한적(ExpeL insight만 유의: 70.0 vs 64.0); 부정 전이로 baseline 이하 조건 다수 관측.

**HSWM 이식 설계 (F3 재설계)**

- **테스트베드**: PhantomWiki에 capability 축 삽입 — donor(27b)만 풀 수 있는 task strata(예: 다중 홉 추론 + 도구 체이닝)를 만들어 receiver(14b)에 headroom 확보. Transplants의 capability-moderation을 사전등록 회귀(gain ~ baseline headroom)로 검정.
- **레슨 포맷**: 하이퍼엣지에 `abstraction_level`(trajectory/workflow/summary/insight 4-tier) + `source_model_id`(MemCollab ℓ 라벨) + `task_category` 타입 부여. donor 전이 arm은 (enforce;avoid) contrast 쌍으로 재증류 — donor·receiver 궤적을 동일 task에서 대조하는 단계가 필수.
- **Arms**: (a) naive donor lessons (null 재현 예상 — ≤0이면 MemCollab 확인), (b) contrast-distilled donor, (c) receiver self-contrast, (d) placebo/random + write-only 통제.
- **Kill conditions**: (b) ≤ (a) → contrastive 가설 kill; (b) ≤ placebo → F3 사망 유지; insight-tier ≤ trajectory-tier → 추상화-전이 상관 kill. 전이량 기대치: MTL 기준 +2~4%p가 realistic ceiling — kill threshold를 그에 맞게 설정.

**references**
- https://arxiv.org/html/2603.23234v2 (verified)
- https://arxiv.org/html/2604.14004v1 (verified)
- https://arxiv.org/html/2605.11032v1 (verified)
- https://openreview.net/attachment?id=AIJsjIqfsp&name=pdf (verified)

**caveats**: PAM은 단일저자 프로토콜 논문, pilot N=50, 저자 스스로 "directional" 명시 — TCS 수치는 약한 증거. Memory Transplants는 workshop 논문, 3B 실험 156/210 불완전, CI 2~8pp로 개별 비교는 directional. MemCollab은 placebo/random-content null이 없음(self/32B source 비교뿐) — "열화" 주장은 vanilla 대비이며 랜덤 메모리 대비는 미측정. MTL 효과크기 +1.8~3.7%로 작아 PhantomWiki급 저분해능 환경에선 검출 불가할 수 있음. MemCollab Table 1의 7B 수치(52.2→67.0)는 본문 텍스트에서만 확인, 표 이미지 수치와 대조 불가.
