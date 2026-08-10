# PROM16 negative-improvement agent-3 :: AXIS=A LENS=recipe

> item: AXIS=A 전이 | LENS=이식설계 | FOCUS=PhantomWiki를 대체/보강할 harder transfer testbed 구체 설계안: 어떤 지식 타입으로 모델 역량 축을 만들지 (예: 약한 모델이 못 배우는 multi-step procedural), arm 구성 (naive/abstracted/contrast/B-self/placebo), metric (TRR=Transfer Retention Ratio 등), kill 조건 3종. 대조 증류·abstraction 재작성·meta-knowledge 한정 중 채택 우선순위.

**한 줄**: PhantomWiki 대체 testbed는 **multi-step procedural 환경(ALFWorld/AppWorld형)** 이어야 한다 — 거기만 실측된 모델-역량 축(teacher 0.89 vs student 0.18, 71pp)이 존재하고, 지식 타입은 procedural meta-knowledge > contrast 규범규칙 > raw fact 순으로만 전이된다(naive fact 주입은 역효과 실측).

**핵심 발견**:
- **역량 축은 절차 실행에서 갈린다**: frozen student + teacher 시연 in-context 주입만으로 ALFWorld 0.18→0.87(cascade 시 0.96, teacher 0.89 상회), AppWorld 0.28→0.55→0.66 — 가중치 갱신 없이 input-채널만으로 역량 갭의 97%를 닫음. 난이도分层에서 갭이 유지(쉬움 0.91 vs 0.96 / 어려움 0.43 vs 0.71) → hard tier가 전이 민감 구간 ([In-Context Distillation, 2512.02543](https://arxiv.org/html/2512.02543v1)).
- **추상화 수준이 전이성을 결정**: 6개 코딩 벤치마크 cross-domain/cross-model 실험에서 Insight형 +4.0~8.3% (avg +3.7%), 같은 포맷 내에서도 task-agnostic > task-specific (Table 4), raw Trajectory는 negative transfer (brittle anchoring). 전이 내용의 본체는 meta-knowledge(검증 루틴·워크플로)이고 알고리즘 전략 전이는 이득의 5.5%에 불과 ([MTL, ICML 2604.14004](https://arxiv.org/html/2604.14004v1)).
- **적대적 null — naive 주입은 해롭다**: Track 벤치마크에서 정답 fact를 주어도 open-book이 closed-book 아래로 떨어지는 모델 다수, 주입 fact 수(KAS 1→500) 증가 시 HP 단조 악화 (Qwen-3 1.7B WIKI 83.6→22.2). "지식을 넣으면 오른다"가 기본 가정으로 성립하지 않음 ([Track, 2601.15495](https://arxiv.org/html/2601.15495v1)).
- **사실형 multi-hop QA는 역량 축이 안 된다**: compositionality gap은 모델 스케일이 커져도 감소하지 않음 (GPT-3 family 실측) — PhantomWiki처럼 사실 조합이 지식 타입이면 강·약 모델이 같이 실패/성공해 전이 판별 불가. 이것이 F3 G=0의 문헌상 설명 ([Press et al., 2210.03350](https://arxiv.org/abs/2210.03350)).

**HSWM 이식 설계** (F3v2 prereg 스케치):
- **환경**: TextWorld/ALFWorld형 synthetic procedural world — 서브골프 합성 + 숨은 환경 규칙(예: "X를 하기 전 반드시 Y 상태"). 지식 타입 3종 층: ①환경 규칙 사실(fact) ②절차 워크플로(workflow) ③검증/실패회피 규범(norm). donor 27b가 경험으로 ②③을 학습, receiver 14b는 ZS 실패(사전등록: B-self ZS ≤ 30% on hard tier — 미달 시 환경 재난이도).
- **Arms (6)**: (a) no-memory (b) naive raw lesson (c) abstracted — Insight형 task-agnostic 재작성 (d) contrast — 성공/실패 쌍에서 "do X / avoid Y" 규범만 증류 (e) B-self lesson 상한 (f) placebo generic tips. +xvendor receiver 팔(같은 family면 bias 공유로 전이 과대추정 — b2 MemCollab 교훈).
- **Metric**: 1차 TRR = (arm − no-mem)/(B-self − no-mem), hard/mid tier 분리 보고. 2차 negative-transfer rate(arm < no-mem인 항목 비율, Track 실패 분류: mismatched anchoring / false validation / misapplied practice로 태깅). 지식 타입별 TRR 분리 (①은 ~0, ②③이 양수여야 환경 아닌 전이 claim).
- **Kill 3종**: K1 — c,d 팔 hard-tier TRR ≤ 0 AND B-self ZS ≥ 60% → 역량 축 부재(환경 kill, PhantomWiki 반복). K2 — naive TRR < 0 AND abstracted/contrast가 naive를 bootstrap CI로 못 넘음 → typed store가 naive와 구별 불가 (claim kill). K3 — placebo TRR ≥ abstracted TRR − 0.1 → lift는 generic priming, "전이" 명명 금지.
- **채택 우선순위**: ① **abstraction 재작성** 최우선 (MTL의 최대·가장 재현된 신호, same-family qwen쌍에 충분) → ② **대조 증류** (family 교차 시 유일하게 음수 전이 회피 — xvendor 팔 필수화 조건) → ③ **meta-knowledge 한정** 은 폴백 claim: F3v2가 약하면 claim ② scope를 "procedural meta-knowledge 전이"로 강등 재등록.

**references**:
- https://arxiv.org/html/2512.02543v1
- https://arxiv.org/html/2604.14004v1
- https://arxiv.org/html/2601.15495v1
- https://arxiv.org/abs/2210.03350

**caveats**: MemCollab(2603.23234) 수치는 본 세션에서 직접 fetch 못 함 (b2 서브에이전트 보고 인용, 단일 seed 한계). In-Context Distillation은 cost 절감이 목표라 "전이" 자체의 메커니즘 분석은 얕음; cascade 팔의 teacher fallback이 정확도를 부풀리므로 IC-only 수치(0.87/0.55)만 전이 증거로 사용해야 함. Track의 악화는 conflicting knowledge 조건 — HSWM lesson이 receiver의 parametric 지식과 충돌하지 않으면 직접 적용은 과외推. ALFWorld는 TextWorld 기반이라 PhantomWiki 대비 "환경 결정 지식" 비율이 여전히 높을 수 있음 — ②③ 지식이 donor 경험 없이는 도출 불가함을 canary probe로 사전 확인 필요.
