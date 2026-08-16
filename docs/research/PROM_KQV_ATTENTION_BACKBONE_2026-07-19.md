# PROM — KQV/attention as weight-hypergraph: HSWM의 이론 등뼈

> 2026-07-19 · 20-agent PROM (16 리서치 + 합성 + 3 적대렌즈, 전원 SOUND_WITH_ADJUSTMENTS)
> 씨앗 = USER 직관: "KQV 어텐션도 사실상 토큰들을 웨이트 하이퍼그래프로 묶어 연산하려는 시도"
> 전문 = 세션 tasks/wirl1ejd3.output · 자매편 = `PROM_PRIOR_ART_TRIBUNAL_2026-07-19.md`(novelty 재판) + `PROM_6_EFFICACY_RESEARCH_2026-07-19.md`(실험 B)

## 0. 한 줄

attention 이론이 HSWM에게 **완전하고 인용 가능한 등뼈**를 준다 — 검증된 연산자 가족(fast weights ·
Hopfield · 외부 KV · KV-eviction)의 "느리고 · 영속적이고 · 거버넌스 있는" 쌍대(dual)로서. 단 이건
전부 **정당화이지 novelty가 아니고**(재판의 CROWDED 판결 그대로), HSWM의 novelty는 단 하나 —
supersession-as-field-readout — 로 좁혀지며 그 운명은 재설계된 실험 B의 측정에 달려 있다.

## 1. USER 직관의 판정 (정리-등급으로 검증됨, 교정 3개 부착)

**검증됨:** attention은 형식적으로 ①완전 토큰그래프 위 GAT식 이방성 message passing(Joshi 2025
eqs 17-19), ②즉석 프로그래밍되는 연상 가중치 행렬 W=Σvkᵀ(Schlag/Irie ICML'21 — linear attention
의 증명된 대수), ③1-step modern-Hopfield readout(Ramsauer, Eq.3=Eq.10), ④연산 수준에서 외부저장
소 kNN과 동일(Unlimiformer의 QKᵀ 재작성). **HSWM = 이 연산자 가족의 slow·persistent·거버넌스형
구성원** — 렌즈를 항등으로 동결(실측: cosine 0.956 vs learned 0.649 — 단 형식 판정은
EXCLUDED-by-ceiling이며 이 캐비앳은 인용 시 항상 동행)하고 softmax 정규화를 threshold 거버넌스로
대체한 것.

**교정 3 (정리-등급):**
- W_QKV 파라미터는 그래프가 아니라 그래프를 **유도하는 렌즈** (런타임 score가 그래프).
- 표준 attention은 **엄격히 pairwise** — 진짜 k-항 관계합성은 triangular ⊙ 곱(Edge Transformer
  = 2-FWL/3-WL 정리)이 필요. **집합-arity와 관계-합성은 직교 축**: 하이퍼그래프 집계는 어떤
  pooling으로도 ~1-WL에 머묾.
- 표현력은 토큰/튜플 수준에서만 산다: 하이퍼엣지는 **1급 채점 단위**로 물질화될 때만 힘을 더함
  (TokenGT ≥ 2-IGN; star-expansion ≡ reified pairwise라 "하이퍼그래프가 이겼다" 수치는 실은
  readout-granularity 효과).

## 2. 핵심 정리 수확 (설계를 구속하는 것들)

- **Dong ICML'21 rank-collapse**: 정규화된 유사도 연산자를 반복하면 rank-1로 이중지수 붕괴;
  length-0(skip) 경로만이 rank를 보존. → HSWM의 **single-read-at-threshold 정본 설계를 형식적
  으로 면책**(비반복·비정규화라 붕괴 레짐 밖), multi-hop 전파 변형은 skip항+hop cap 필수.
- **HippoRAG 자체 ablation**: naive 1-hop spreading은 오히려 해침(25.4 < 37.1 < 40.9 PPR);
  저-hop 질문에서 graph readout 순손실(HotpotQA −4.2). → C5: 전파는 위험한 별도 축.
- **cosine>learned의 문헌 집 4곳**: kNN-LM 무학습 readout / UHN 이론(threshold 분리 하에선 부하
  전부가 유사도 커널에) / AllSet의 사전학습-임베딩 레짐 역전 / 에이전트 메모리에서 query-cosine
  이 gold 유지 0.979-0.993 포화. → 동결-cosine+구조 거버넌스는 **후퇴가 아니라 인용 가능한 설계**.
- **KV-cache eviction = fast 메모리의 supersession**(H2O/TOVA/SnapKV) + delta-rule의 표적 소거
  (I−βkkᵀ, Gated DeltaNet) + Hopfield 에너지의 준안정 병합 — 세 문헌이 수렴해 HSWM 생존 청구항의
  개연성을 높이되, **전부 fast-lane이고 slow/persistent 시스템 중엔 아무도 안 함**(Zep/Mem0=LLM
  판정, Kumiho=AGM 연산자). 단 critic 교정: H2O/TOVA는 **budget-triggered**라 HSWM이 chance(0.286)
  로 실측·부인한 바로 그 readout 모드 — "선례"가 아니라 analogy-grade로만 인용할 것.

## 3. 설계 이식 (critic 교정 반영 랭킹)

**지금 채택:**
- **T1 도착-트리거 제한 supersession readout**: 구조 허용술어(같은 앵커 ∧ t_new>t_old, LLM 0회)
  먼저 → cos≥θ_sup이면 supersede, 항상 archive-not-delete. budget-트리거 eviction은 field readout
  으로 **명시 부인**(query-blind cosine=0.286≈chance) — Occam의 구조 거버넌스 몫.
- **T3 합성 가드 코드경로**: 추이적 supersession(A⊐B⊐C)·관계합성 질의는 threshold가 아니라
  명시적 그래프 순회로 라우팅 — pairwise cosine은 2-FWL 밖(정리). 정직 제약을 코드로.
- **T2 hub 감사 + CSLS 보정** — 단 **critic이 원 논리를 뒤집음**: T1 정의상 hub는 "영원히 관련
  있어 안 지워지는" 게 아니라 도착 유사도 인플레로 **오히려 더 쉽게 superseded**. 채택 근거는
  hub의 4-fold readout 동시 편향(검색·계획까지)이고, supersession 방향 효과는 실험 B에서 실측.
- **경계**: 이 축 전체 novelty 델타 = 0. 생존 청구항도 합성-선례 테스트(H2O×외부메모리 조합)를
  재판과 같은 기준으로 통과해야 하며(OQ), T5/T8이 실험서 이겨도 그건 HyperGraphRAG/HippoRAG
  메커니즘의 **채택**이지 novelty 크레딧이 아님을 사전 약정.

**측정 게이트 뒤 (실험 B 조건부):** T5 하이퍼엣지 1급 채점(V∪E readout — HyperGraphRAG ablation
−9.0 F1 근거, 단 저-hop 회귀 리스크), T6 보정 readout head(~6-10 스칼라, grid/isotonic — SGD 아님),
T8 skip+hop cap 2단 전파(τ=∞ arm ≡ clique-PPR 정리 = 공짜 원칙적 baseline).

**강등/기각:** T4 ln N threshold 법칙(critic: Ramsauer 가정 불충족 — 방향성 휴리스틱으로만),
T7 감쇠 스칼라(ablation 전용 — C2 실측상 장식), T9 다리는 text-bridge에 머묾(주소가능성이
supersession의 전제조건; KV주입·test-time weight는 철회된 learned 축의 재입장이라 배제).

## 4. 실험 B 재설계 (critic이 잡은 P0 blocker 포함)

- **⛔ P0 (actionability critic)**: 조정안 전체가 **문서→하이퍼그래프 빌더를 전제하는데 그게
  없다** — HSWM의 실증 기반은 curated KG. E-시리즈 착수 전에 빌더를 만들거나(비용 산정), 벤치를
  curated-KG 호환으로 재선정해야 함. hop-diameter 공변량도 NoCha/NarrativeQA에선 측정 불가(gold
  evidence 부재) — QASPER류 evidence-span 벤치 우선으로 재배열.
- **핵심 재키잉(E1)**: 상호작용 축을 raw 길이에서 **기전 담지 공변량**으로 — 최소 증거 부분그래프
  의 hop 지름 + 증거 청크 수(binding load)가 1차(NoCha의 scope 효과 18.2pp vs "불명" 길이 효과),
  key-crosstalk·Δ-collapse·arity 밀도·코퍼스 churn을 조절변수로. 길이는 공변량으로만.
- **readout-swap 2×2(E2)**: 같은 임베딩·코퍼스에서 {flat cosine kNN} vs {HSWM 자기 그래프 위
  PPR} — PPR이 기울기를 재현하면 場이 장식, flat kNN이 재현하면 그래프가 장식. 교차 사전등록:
  hop≤1에서 HSWM ≤ baseline.
- **거버넌스 정면승부(E4 — 생존 청구항을 직접 재는 유일한 arm)**: LongMemEval 지식-갱신+abstain
  슬라이스, Zep(LLM 판정)이 baseline. H_sup: field-threshold supersession이 Zep의 KU 정확도 CI
  안에 들면서 판정비용 ≥10× 절감 + LLM 호출 0. **+ 적대 프로브**(고-cosine·같은 앵커·비모순 정교
  화 쌍)의 false-supersession율 공표 — Kumiho형 반론 선제.
- 계측 위생: entity-mention-recall 2차지표(F1이 global-binding을 가림 — Unlimiformer 10.0→20.3),
  주입토큰 예산 매칭+순서 셔플 ablation(Lost-in-the-Middle 교란 차단), top-k 대신 95% mass-coverage
  정지규칙, HTML 발췌 수치 전부 pdftotext 재검증 후 prereg 동결.

## 5. 포지셔닝 문장 (인용용, 정당화·novelty 분리)

> "Attention은 완전 토큰그래프 위에서 매 pass마다 건설되는 일시적·정규화·학습렌즈 유사도 場이다
> (Joshi 2025; Schlag/Irie 2021의 fast-weight 대수; Ramsauer 2021의 Hopfield readout). HSWM은 그
> 같은 스칼라 pairwise 場의 느린 쌍대 — 영속·외부화하고, 렌즈를 항등으로 동결하며(자체 KG 실측
> cosine 0.956 vs learned 0.649, 형식 판정 EXCLUDED-by-ceiling), softmax를 threshold 거버넌스로
> 대체한 것이다. 우리는 새 메커니즘이 아니라 **영속성/거버넌스 레짐 전환**을 주장하며, 유일한
> 미선점 기여는 시간축 거버넌스(supersession)를 같은 場의 threshold readout으로 접는 것 — 그
> 방어는 개념이 아니라 실험 B의 측정(갱신 정확도/판정 비용)으로만 선다."
