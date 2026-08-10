# PROM16 negative-improvement agent-2 :: AXIS=A LENS=pitfalls

> item: AXIS=A 전이 | LENS=함정 | FOCUS=2025~26 전이/메모리 주장의 오탐·실패 사례 — negative transfer 실측, benchmark gaming, retrieval을 transfer로 위장한 사례, 공유 prior confound (같은 base model·같은 pretraining). harder testbed에서 우리가 또 맞을 함정 예측.

**한 줄**: 2025–26 실측 문헌은 "전이 이득"의 상당수가 placebo 주입·공유 prior·수신자 headroom·깨진 벤치마크/저지의 산물이며, HSWM의 harder testbed는 이 4개 함정을 팔(factorial + negative control)로 미리 잠가야 한다.

**핵심 발견**:
- **Placebo 전이 (최대 함정)**: *When Memories Collide/AIM* (ICLR 2026 AM workshop) 후속 실험에서 **random retrieval placebo가 similarity retrieval과 동급 효과** — 주입된 컨텍스트면 내용 무관하게 code는 ↓, math는 ↑ (도메인 의존 부호). "전이"가 아니라 도메인별 컨텍스트 민감도. 간섭은 상위 30% 아이템에 70–76% 집중, sparse encoding으로 cross-domain 간섭 37% 감소. ([openreview PDF](https://openreview.net/pdf/eca6e05d3129944c0543e432d82860f5f3db74ae.pdf))
- **Architecture/content 미분리 = 전이 위장**: *Memory Transplants* (MemAgents @ ICLR 2026) 2×2 factorial: architecture 전이는 **방향 불일치(보편 방향 없음)**, static content 전이는 대부분 NM 대비 무의미 — 이득 대부분이 dynamic(online learning)에서 발생. **Negative transfer 실측**: 여러 조합이 no-memory baseline 이하. 수신자 capability가 전이 크기 조절: 약한 3B +15pp vs 강한 7B +7pp ("headroom 가설"). 단 7B 효과 2–5pp는 CI 2–8pp에 걸림 = 저전력. ([openreview PDF](https://openreview.net/pdf/f59dcd63f899d31fe643c259ddf32e1096de62fb.pdf))
- **능력 threshold 역설**: AIM 후속 — 모델이 도메인 competence threshold 아래면 **잘 큐레이션된 retrieval도 해로움**. PhantomWiki F3 G=0의 대칭 함정: harder testbed에서 수신자가 너무 약하면 전이가 음수가 됨.
- **벤치마크/저지 gaming**: LoCoMo 감사 — 정답키 **6.4% 오류**(이론상 만점 ~93.6%), gpt-4o-mini 저지가 **의도적 오답의 62.81% 수락**(모호하지만 토픽 일치 답변). 재현 실패 다수(EverMemOS #73, Mem0 #3944). LongMemEval-S는 115K 토큰이 최신 컨텍스트 창에 통째로 들어가 **full-context baseline 60.20%** → "메모리"가 아니라 컨텍스트 관리 측정. ([감사 전문](https://techstarasia.net/article/we-audited-locomo-64-of-the-answer-key-is-wrong-and-the-judge-accepts-up-to-63-of-intentionally))
- **공유 prior / 정렬 confound**: *Neural Incompatibility* (ACL 2025) — cross-scale PKT는 **parametric alignment가 전제조건**, 무정렬 전이 불능. 입력채널 전이는 이를 우회하지만, 같은 패밀리(Qwen 27b→14b)는 pretraining·토크나이저 공유로 donor lesson이 "재활성화"인지 "전이"인지 구분 불가. ([arXiv 2505.14436](https://arxiv.org/html/2505.14436v1), [ACL](https://aclanthology.org/2025.acl-long.1047/))
- **비대칭 전이** (2차 인용): Agent KB — reasoning→SWE는 +, 역방향은 0. LifelongAgentBench — 8B replay로 0.19→0.78이나 **과잉 replay는 성능 하락**. 코딩 에이전트 cross-domain 메모리 이득 평균 **+3.7%뿐, meta-knowledge(워크플로/가드레일)만 전이** ([arXiv 2604.14004](https://arxiv.org/html/2604.14004v1)).

**HSWM 이식 설계** (F3 재설계용):
- **Arms (2×2 + 통제)**: no-memory / self-lessons / donor-content-static / donor-arch-only / full-dynamic + negative control 4종(random lesson, placebo filler, write-only, frozen-store MU). E_TARGET cold-start를 반드시 포함 (없으면 from-scratch 학습 궤적을 "전이"로 오독).
- **수신자 선정**: harder testbed에서 수신자 baseline 40–65% 구간(headroom zone) — 포화(PhantomWiki 오류)도 threshold 이하(AIM 오류)도 피함. donor↔receiver baseline gap ≥15pp 확보.
- **Metrics**: G(=donor-static − no-memory), S(=donor-static − self-static), per-lesson harm rate r_i (AIM ledger 차용, ΔU<0 아이템 quarantine), 저지 adversarial acceptance rate.
- **Kill conditions (사전등록)**: K1 placebo/random이 실 donor와 CI 겹침 → kill (placebo 함정). K2 static G≤0이고 dynamic에서만 이득 → claim을 "content transfer"에서 "architecture effect"로 강등. K3 cross-family donor(예: Llama donor→Qwen receiver)에서 이득 소실 시 shared-prior confound로 표기 — same-family 이득 > cross-family 이득을 요구. K4 저지가 의도적 오답 >15% 수락 → 저지 교체 전 claim 금지. K5 주입 예산(토큰) 2단계에서 부호 비단조 발견 시 단일 예산 claim 금지.

**references**:
- https://openreview.net/pdf/eca6e05d3129944c0543e432d82860f5f3db74ae.pdf (AIM, verified)
- https://openreview.net/pdf/f59dcd63f899d31fe643c259ddf32e1096de62fb.pdf (Memory Transplants, verified)
- https://techstarasia.net/article/we-audited-locomo-64-of-the-answer-key-is-wrong-and-the-judge-accepts-up-to-63-of-intentionally (LoCoMo/LongMemEval 감사, verified)
- https://arxiv.org/html/2505.14436v1 + https://aclanthology.org/2025.acl-long.1047/ (Neural Incompatibility, verified)
- https://arxiv.org/html/2604.14004v1 (cross-domain coding memory, snippet 검증)

**caveats**: AIM·Transplants 모두 workshop 논문(단일 도메인 시프트 code→math, 시드 3개, CI 2–8pp로 저전력). Agent KB 비대칭·LifelongAgentBench 수치는 Transplants 논문 경유 2차 인용(원문 미검증). LoCoMo 감사는 벤더 측 블로그(dev.to 재게재) — 감사 스크립트 repo(locomo-audit) 자체는 미검증. arXiv 2604.14004는 본문 일부만 확인.
