# PROM 16 HSWM 미증명 — claim ④ 장기 consolidation

> cycle `prom16-hswm-unproven-claims-20260725` axis-split (L2). 상위 보고서: `PROM_16_UNPROVEN_CLAIMS_2026-07-25.md`.


## d1 :: theory [HIGH]

**한 줄**: Consolidation claim ④는 반증된 게 아니라 측정 불가 상태 — GEM BWT/FWT + transformation hypothesis의 gist-detail 분기를 prereg kill 조건으로 봉인하면 typed store 수준에서 검증 가능한 sealed 실험으로 내릴 수 있다.


**rootCause**: Claim ④(장기 consolidation)가 미증명인 근본 이유는 HSWM에 'consolidated 상태'의 형식 정의와 측정 변수가 없기 때문이다 — 검증 불가 상태이지 반증 상태가 아니다. 이론 문헌은 이 claim이 실은 3개의 구별되는 현상의 혼합임을 보여준다: (a) systems consolidation = 저장 기질 간 재분배(hippocampus→neocortex; Squire/Alvarez 표준이론, 단 MTT(Nadel & Moscovitch 1997)는 episodic은 hippocampus 의존이 영속한다고 반박), (b) 표상 변환(transformation hypothesis, Winocur & Moscovitch 2011) = context-rich episodic → decontextualized semantic gist로 내용 자체가 변함(상세 손실 + gist 보존이라는 서명(signature) 예측 생성), (c) stability-plasticity 제어(McClelland et al. 1995 CLS: 빠른 hippocampus 학습 vs 느린 neocortex interleaved 학습이 catastrophic interference 회피의 핵심; Kumaran-Hassabis-McClelland 2016 업데이트로 schema-consistent 신지식은 빠른 통합 가능). 측정 도구도 이미 존재한다: GEM(Lopez-Paz & Ranzato 2017)의 ACC/BWT/FWT 형식, Mattar & Daw 2018의 gain-based prioritized replay(재생 순서는 무작위가 아니라 예상 학습 이득 함수), Rasch & Born 2013의 수면 중 active system consolidation, Tononi & Cirelli SHY downscaling. HSWM은 L0 answer-interface 결과(p1v4 6/6)만 측정하고 offline 통합 연산자 C: S_t→S_{t+1}의 사전/사후 상태 변수를 선언한 적이 없어서, C1 book-scale과 동일한 category error(구조는 있으나 metric 없음)가 재현되고 있다. LLM 에이전트 측 구현 선례(SCM 2026: entropy/conflict-density trigger + Hebbian Δs + downscale α + adaptive forgetting threshold; Letta sleep-time compute 2504.13171; Mela 2605.10537의 test-time consolidation)는 변수 선택이 가능함을 보여주지만 모두 weight-free 저장소 수준이라 ΔW claim과는 분리해서 봐야 한다.


**recommendation**: 다음 sealed 실험 'B-consol'(HSWM_LOCAL_RECORD 게이트 적합) 설계: ① 연산자 선언 — hippocampus=원시 세션 trace 로그(episodic buffer), neocortex=typed lesson store+hypergraph edge(semantic). Consolidation 연산자 C를 offline 배치 프로세스로 정의하고 pre/post 상태 스냅샷을 replay 검증 가능하게 봉인. ② 측정 변수 4개를 prereg 등록: (i) BWT = 신규 task 학습 후 기존 heldout task 성능 변화(GEM 형식; stability 축), (ii) FWT = consolidation 후 미노출 유사 task의 zero-shot 성능 이득(schema 추출 축), (iii) gist-fidelity 곡선 = episode→typed lesson 압축률 대비 '상세 질의 정확도' vs 'gist 질의 정확도'의 분기 — transformation hypothesis의 서명 예측(상세는 감소, gist는 유지/증가)이 관측돼야 '진짜 통합', (iv) replay 정책 = Mattar & Daw식 gain 우선순위 vs uniform sampling ablation. ③ Kill 조건(prereg): (K1) consolidation ON vs OFF의 ΔBWT가 CI 포함 0 이하 → kill; (K2) gist-detail 분기 미검출(두 정확도가 동일 궤적) → consolidation이 단순 retrieval과 구별 불가 → p1v2형 kill(개입 효과 0); (K3) append-only/LRU 단순 저장소가 동일 BWT 달성 → 구조 고유 기여 없음 → C1과 같은 novel kill. ④ 선행 조건: semantic-weight-metric-contract가 먼저 닫혀야 edge weight(Hebbian Δs, downscale α)의 의미가 해석 가능 — 미해결 foundation 2건 중 이 실험은 후자에 hard dependency, 전자(multi-agent-transfer-harness)에는 무관하게 실행 가능. ⑤ 간섭 주입 설계: 모순 lesson 세트를 wake phase에 주입해 conflict density(SCM식 ρ=|E_contradicts|/|E|)를 trigger 변수로 사용, 통합이 모순 해소를 하는지를 2차 endpoint로.


**alternatives**:
- MTT 해석 채택: episode를 삭제하지 않고 매 retrieval마다 새 trace(reactivation count)를 추가하는 모델 — forgetting 위험 없고 구현 단순하며 '재활성화 횟수→검색 강건성' 회귀로 검증 가능; 단 KG 팽창 통제 장치 필요(SCM 실험상 forgetting 없이는 저장소가 선형 팽창). Eilu va-Eilu/삭제 금지 정전과도 양립.
- Sleep-time compute 프레이밍(2504.13171): 학습 claim을 세우지 않고 'offline LLM 패스로 trace를 사전 재구조화'하는 공학 claim으로 강등 — metric은 wake 시 쿼리당 latency/cost + 정확도. ΔW 증명 없이도 가치 있는 stepping stone이며 실패해도 consolidation 이론 claim을 오염시키지 않음.
- CLS 이중 저장소 아키텍처: 단일 typed store 대신 빠른 학습률의 hippocampal store와 느린 학습률의 cortical store를 분리하고 interleaved replay로 cortical 측을 점진 갱신 — McClelland 1995의 본래 계산 설계에 가장 충실하나 구현 비용이 가장 크고, schema-consistent 신지식의 빠른 통합(Tse et al. 반례, Kumaran 2016 수용)을 재현하려면 consistency 조건부 fast-path를 추가로 정의해야 함.


**references**:
- https://arxiv.org/html/2604.20943v1
- https://arxiv.org/abs/2512.13564
- https://arxiv.org/html/2504.13171v1
- https://papers.nips.cc/paper/2017/hash/f87522788a2be2d171666752f97ddebb-Abstract.html
- https://pubmed.ncbi.nlm.nih.gov/30349103/
- https://pubmed.ncbi.nlm.nih.gov/21729403/
- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5060006/
- https://arxiv.org/html/2605.10537v1
- doi:10.1037/0033-295X.102.3.419 (McClelland, McNaughton & O'Reilly 1995)
- Kumaran, Hassabis & McClelland 2016, Trends Cogn Sci 20(7):512-534
- Rasch & Born 2013, Physiol Rev 93(2):681-766
- https://arxiv.org/abs/2401.08623


**caveats**: McClelland 1995, Kumaran 2016, Rasch & Born 2013, Tononi & Cirelli 2003은 fetch한 1차 문서(SCM full text, Memory in the Age of AI Agents 관련 페이지) 내 참조 인용으로 확인했으며 원문 full text는 미열람. SCM(2604.20943)은 자칭 research preview이고 벤치마크가 명시적 사실 회상 8개 테스트에서 zero-variance 만점이라 ceiling에 가까움 — 약한 증거로 취급. Mela(2605.10537)는 서칭 스니펫만 확인, full text 미열람. 2604/2605 계열 arXiv id는 2026년 4~5월 투고로 현재 시점(2026-07)과 정합하나 peer-review 상태 불명. BWT/FWT 형식은 지도학습 continual learning에서 유래해 gradient-free typed store로의 이식은 재정의가 필요(정확도 행렬 R_{i,j}를 'task i 학습 시점의 task j heldout 성능'으로 해석). 2026-04-22 이후의 sleep-consolidation LLM 신작은 검색 범위상 SCM/Mela/SleepGate 정도만 확인됐고 추가 선행 사례가 있을 수 있음.


## d2 :: benchmarks [MEDIUM]

**한 줄**: Consolidation 실측 문헌은 풍부하나(BWT/AA, replay 효과 크기, LongMemEval 30-60% 하락, sleep-time compute 13-18% 개선) 모두 '진짜 간섭+천장 회피'를 동시에 만족하는 프로토콜이 없어, HSWM claim ④는 KU/TR 간섭 주입 + 3-arm BWT 측정 + 선등록 kill로만 증명 가능하다.


**rootCause**: Claim ④(장기 consolidation) 증명이 어려운 근본 구조: continual learning과 LLM agent memory 두 문헌이 서로 다른 측정 축을 쓴다. 전통 CL(Split CIFAR/MNIST, CORe50)은 AA/BWT로 '새 태스크 학습 후 옛 태스크 성능'을 재는 반면, agent memory 벤치마크(LOCOMO, LongMemEval)는 단일 정적 히스토리에서의 recall 품질만 재고 '나중에 주입된 지식이 이전 지식을 간섭하는' 진짜 forgetting 상황을 만들지 않는다. 그 결과 append-only retrieval이 이미 천장에 도달해(p1v2 typed lesson KILL과 동일 구조) consolidation 개입 효과가 0으로 측정되거나, 반대로 간섭이 없어 forgetting 자체가 발생하지 않는 프로토콜이 된다. 또한 수치상 regularization/consolidation이 역효과를 낼 수 있음이 실증됨 — Split CIFAR-100 10-task에서 sequential FT 7.27%인데 EWC는 6.16%로 FT보다 나쁘고(SI 8.15%, ER 7.4%, TFC-SR 13.17%), 잘못된 축의 anchoring/merging은 성능을 갉아먹는다. sleep-time compute(Letta/Berkeley, 2504.13171)는 오프라인 단계 효과가 query predictability와 상관한다는 것을 보였다 — 예측 불가 쿼리에서는 sleep 단계 이득이 증발. 즉 consolidation 벤치마크의 핵심 설계 변수는 (a) 진짜 간섭 유발(knowledge update/conflict) (b) base-retrieval 천장 회피 (c) unpredictable heldout 포함, 셋이다.


**recommendation**: HSWM claim ④ sealed 실험을 다음과 같이 설계한다. (1) 태스크 스위트: episode를 시간순 주입하되 후반 episode가 전반 사실을 덮어쓰는 knowledge-update(KU) + temporal-reasoning(TR) 문항을 LongMemEval 스타일로 최소 40% 포함시켜 진짜 간섭을 인위 생성한다(간섭 없는 프로토콜=append-only 승리=p1v2 재발). (2) 3-arm 비교: A) no-consolidation append-only store, B) decay-only(Ebbinghaus R=e^{-t/S} 스타일 strength 감쇠, MemoryBank식), C) offline sleep-phase(lesson merging/abstraction/topology 정리) — C arm에 sleep-time compute 설계를 이식하되 query 예측 가능성을 두 구간(predictable/unpredictable heldout)으로 쪼갠다. (3) Metric: episode별 probe 세트에 대한 Average Accuracy와 BWT(후반 학습 후 초기 episode 성능 변화)를 주 metric으로, LOCOSTyle F1/LLM-judge는 보조. semantic-weight-metric-contract에 BWT/AA 정의를 선등록. (4) Prereg kill 조건: ① C arm의 BWT 개선폭이 B 대비 5점 미만이면 claim ④ as-measured KILL; ② A arm이 이미 probe 천장(≥95%)이면 개입 효과 0 → 프로토콜 무효로 판정하고 간섭 강도를 올려 재시행(1회만); ③ C arm이 A/B보다 유의하게 나쁘면(EWC<FT 사례처럼) intervention-harm으로 기록, consolidation 로직에 harm-check 게이트 추가. (5) HSWM_LOCAL_RECORD 장부에 arm별 BWT 곡선(시간축)을 sealed run + replay 검증으로 봉인.


**alternatives**:
- 기존 벤치마크 그대로 사용: LOCOMO/MemBench/LongMemEval에 HSWM을 그대로 올려 Mem0(LOCOMO LLM-judge 26% 상대개선, p95 latency 91% 절감)이나 Zep(LongMemEval 최대 +18.5%)과 비교 — 빠르지만 static recall만 재므로 claim ④(시간경과 consolidation) 직접 증명에는 부적합
- 생물학적 replay 유사 설계: generative replay/DER++ 스타일로 오프라인 단계에서 합성 쿼리를 생성해 store를 rehearsal — buffer 크기 effect(ER이 tiny buffer로도 joint training 근접)를 HSWM lesson 수 예산에 매핑하는 실험으로 전환
- claim 축소: consolidation을 성능 claim이 아니라 비용 claim으로 재정의(sleep-time compute처럼 test-time 비용 2.5~5x 절감 측정) — 증명 난이도가 낮고 선행 수치 존재


**references**:
- https://arxiv.org/abs/2504.13171
- https://arxiv.org/html/2507.21109v1
- https://arxiv.org/abs/2305.10250
- https://xiaowu0162.github.io/long-mem-eval/
- https://arxiv.org/html/2504.19413v1
- https://arxiv.org/pdf/2112.08654v1.pdf
- https://arxiv.org/html/2606.30067v1
- https://arxiv.org/html/2510.27246v2
- https://arxiv.org/pdf/2604.11243


**caveats**: TFC-SR의 Split CIFAR-100 수치(FT 7.27% 등)는 표준 mammoth protocol보다 훨씬 낮아 protocol 의존성이 큼 — 절대 수치 비교보다 arm 간 상대 비교 구조만 인용해야 함. MemoryBank의 Ebbinghaus 곡선은 정량 forgetting 벤치마크가 아니라 디자인 휴리스틱(실측 시간곡선 미공개). LongMemEval '30~60% 성능 하락'은 프로젝트 페이지 요약 수치. Letta/MemGPT 자체는 공식 LongMemEval 수치 미공개(2026-04 기준). Mem0 26%는 자사 논문 LLM-as-judge 상대개선치로 독립 재현 제한적. Memori 81.95%/1294 tokens는 2차 인용(arXiv 2604.11243 서베이) 경유.


## d3 :: pitfalls [HIGH]

**한 줄**: Consolidation 오탐의 5대 함정(재검색을 통합으로 오인·trivial baseline 미배치·벤치마크 문체 누출·시간/drift confound·SFT식 ΔW 측정 오류)을 막으려면 store-ablation·offline improvement·trivial-baseline·dual-holdout 4게이트를 prereg kill 조건으로 봉인해야 한다.


**rootCause**: Consolidation 주장이 오탐에 취약한 근본 구조는 '통합(consolidation)'의 행동적 정의가 문헌마다 부재하고, 측정 가능한 프록시(store 크기, 로그 누적, 재검색 정확도)가 진짜 표상 변화와 구조적으로 혼동되기 때문이다. Xu et al.(arXiv:2604.27707)이 정식화했듯 현재 배포된 모든 agentic memory는 C(context)만 바꾸고 θ(가중치)는 frozen이라 'memo vs mind' 범주 오류를 범하며, Letta의 sleep-time compute조차 가중치가 아닌 context token을 재작성한다('잘 정리된 초보'). 신경과학의 통합 행동 기준(추가 학습 없는 offline improvement + 간섭 저항성 + episodic→semantic gist 변환, 48h~수주 시간 스케일)을 LLM 에이전트 평가에 적용한 연구는 사실상 없다. 두 번째 구조는 CL 평가 자체의 함정: GDumb(ECCV 2020)과 RanDumb(arXiv:2402.08823)이 보였듯 naive baseline(탐욕적 버퍼 재학습, 심지어 랜덤 표상)이 SOTA continual 방법을 능가해, 매칭된 trivial baseline 없는 '개선'은 진보가 아니라 착시다. 세 번째는 벤치마크 설계 결함(arXiv:2511.10523): LongMemEval의 filler/evidence 문체 불일치는 모델이 기억이 아닌 스타일 단서로 풀게 하고, 카테고리당 n<100(LoCoMo 10개 대화)은 통계적 비교를 불가능하게 하며, 단순 full-context baseline이 Mem0 등 정교한 시스템을 70-82% vs 30-45%로 압도한다. 네 번째는 시간 confound: 과제 순서 민감성·나중 데이터가 쉬워지는 난이도 drift·평가 시점 편향이 있고, concept drift(분포 변화)와 forgetting(간섭)은 별개 현상인데 장기 연구에서는 drift를 '통합' 또는 '망각'으로 오독한다. 다섯 번째는 ΔW 측정 오류(Yao et al. 2024, Ye et al. 2025 — 2604.27707 §5.2 인용): 표준 SFT는 fact memory unit이 아닌 attention router만 수정하므로 '지식 갱신'을 측정한다며 실제로는 접근 재배열을 측정하는 경우가 흔하다. 결론적으로 consolidation claim은 ① store 없이도 살아남는가(통합 vs 재검색) ② trivial baseline을 이기는가 ③ 시간/drift를 분리했는가 — 세 테스트 없이는 반증 불가능한 서사가 된다.


**recommendation**: HSWM claim ④(장기 consolidation)의 sealed 실험은 다음 4개 게이트를 prereg kill 조건으로 등록해야 한다. G1 store-ablation(결정 테스트): consolidation pass 후 t0 이전 raw store의 retrieval을 sealed 상태에서 차단하고 frozen heldout을 평가한다. 차단 상태에서 성능 유지≥prereg threshold일 때만 '통합' — 붕괴하면 재검색이므로 KILL(p1v2 typed lesson KILL과 동일한 개입효과-0 논리를 축 ④에 적용). G2 offline improvement + 간섭 저항: 신경과학 행동 기준을 채택해 consolidation pass 전후 동일 frozen probe 세트로 추가 데이터 없이 개선을 측정하고, 이후 상충 경험 주입 시 통합 지식의 유지율을 비통합 통제군과 비교한다. G3 trivial-baseline 게이트(GDumb/RanDumb 교훈): (a) full-log-dump retrieval baseline, (b) no-op consolidation arm, (c) random topology rewiring arm 3개 통제군을 두고, 어느 하나라도 동률이면 KILL. G4 시간·drift 분리: 과제 순서 counterbalance, 전 시점에 고정난이도 canary probe 삽입, frozen-at-t0 holdout과 fresh-at-tk holdout을 이중 운용해 drift(둘의 괴리)와 학습(frozen에서의 개선)을 분리하고, evidence와 heldout을 동일 생성 파이프라인에서 뽑아 LongMemEval식 문체 누출을 차단하며 카테고리당 n≥100을 확보한다. metric은 store 크기/로그 수가 아니라 구조 델타(topology/가중치 변화량 + semantic-weight-metric-contract 상의 typed metric) × 행동 전이의 결합이어야 하며, replay 검증은 consolidation 전후 store 스냅샷의 sha256 차이와 함께 봉인한다. 현재 HSWM은 L0 answer-interface만 성립하므로, 위 게이트 전부를 통과하기 전에는 claim boundary에 'consolidation 미지원'을 명시 유지하는 것이 HSWM_LOCAL_RECORD 장부상 정직한 상태다.


**alternatives**:
- 주장 격하 경로: consolidation을 증명하려 하지 말고 '외부 store 위의 typed actuation'으로 claim을 한정한다 — 2604.27707의 결론처럼 retrieval-only 시스템은 compositional novelty에서 구조적 상한이 있으므로, HSWM의 정당성을 통합이 아닌 다른 축(재현성·감사가능성)에서 방어하는 전략.
- CGT(Compositional Generalization over Time) metric 채택: T 세션 동안 개념을 격리 노출한 뒤 미견 조합 쿼리로 평가 — 순수 retrieval agent는 flat, 진짜 통합은 T에 대해 단조 증가해야 한다는 2604.27707 §5.2 제안을 HSWM heldout 설계에 직접 이식.
- Trace→distill→adapter 통합 채널 + 버전드 체크포인트: consolidation pass를 LoRA/self-distillation으로 구현하고 regression guard(통합 후 downstream metric 저하 시 자동 롤백)를 달아, ΔW claim(축 ①)과 consolidation claim(축 ④)을 하나의 sealed 파이프라인으로 동시 검증.


**references**:
- https://arxiv.org/html/2604.27707v1
- https://arxiv.org/abs/2511.10523
- https://arxiv.org/pdf/2410.10813
- https://arxiv.org/html/2402.08823
- https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123470511.pdf
- https://proceedings.mlr.press/v232/lesort23a/lesort23a.pdf
- https://homes.esat.kuleuven.be/~konijn/publications/2021/Verwimp1.pdf
- https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2019.02312/full
- https://doi.org/10.1016/j.neuron.2023.03.005 (Brodt, Inostroza, Niethard & Born — Sleep—A brain-state serving systems memory consolidation, Neuron 2023)
- https://arxiv.org/html/2604.20006v1


**caveats**: 2604.27707('Memo, Not True Memory')는 position paper로 Theorem 1의 분리 결과가 Assumption(유계 in-context composition)에 의존하며 ᾱ→1 영역(강한 사전학습 커버리지)에서는 separation이 소멸한다고 저자 스스로 인정 — HSWM의 도메인이 이 영역이면 G1의 변별력이 떨어질 수 있다. Sleep-time compute(arXiv:2504.13171)는 2차 소스(Glasp/implicator 요약)로만 확인했고 원문 미열람. arXiv:2604.20006과 Lesort 2023, Verwimp 2021은 스니펫/초록 수준 확인. GDumb·RanDumb은 이미지 분류 CL 맥락이라 LLM 에이전트 맥락으로의 외삽은 유추다. 신경과학 offline improvement 기준의 LLM 적용은 유사성에 기반한 설계 원칙이지 확립된 표준이 아니다. '드리프트 vs 망각 구분'은 RCCDA(arXiv:2505.24149) 등에서 개념적 구분만 확인했고, 장기 에이전트 연구에서 drift를 통합으로 오독한 구체적 사례 논문은 확보하지 못했다(문헌 공백 자체가 시사점).


## d4 :: alternatives [MEDIUM]

**한 줄**: consolidation 증명은 '보존 효과(append-only control)'와 '검색 효과(offline ablation)'를 3-arm longitudinal forgetting-curve 설계로 분리해야 하며, retention이 아니라 decay slope 차이 + schema-generalization이 통합의 고유 서명이다.


**rootCause**: consolidation claim이 증명 어려운 근본 이유는 '통합(offline restructuring)'의 효과가 두 개의 더 단순한 귀인과 항상 혼재되기 때문이다: (1) 단순 보존 효과 — append-only raw log가 모든 것을 유지하면 재구조화 없이도 retention이 확보되고, (2) 선택/검색 효과 — 성능 향상이 consolidation이 아니라 probe 시점의 retrieval selection에서 올 수 있다. CLS 이론(McClelland et al. 1995; Kumaran-Hassabis-McClelland 2016) 자체가 consolidation의 정의를 'episodic→semantic 변환에 의한 일반화 이득'으로 요구하므로, 단순 retention 우위는 consolidation의 증거가 못 된다. SIESTA(ICML 2023)가 formalize한 wake/sleep 주기 설계와 Nature Comms 2022의 sleep-like replay 실험은 오프라인 위상 ablation의 선례를 주지만, 두 작업 모두 gradient-weight setting이라 HSWM처럼 가중치=외부 store인 setting에선 '무엇이 ΔW인가'를 probe 설계가 먼저 고정해야 한다. HSWM의 C1 kill(hypergraph 0.427 vs clique 0.447)은 정확히 이 패턴 — 구조적 정교함이 단순 대조군을 못 이기면 kill — 이 consolidation에서도 그대로 재현될 위험이 있다.


**recommendation**: 최소 sealed 프로토콜: 3-arm × 8주차(또는 simulated-lag) longitudinal 설계를 HSWM_LOCAL_RECORD 장부에 prereg 후 sealed run. Arm A = full HSWM(wake: typed lesson actuation, sleep: consolidation pass로 store 재구조화·압축·ΔW 갱신), Arm B = raw-log append-only control(통합 없이 전부 보존 + 동일 retrieval budget — 보존 효과 분리), Arm C = consolidation-off HSWM(store는 있으나 sleep phase를 no-op으로 — 오프라인 위상 ablation). 1차 endpoint = preregistered held-out probe set의 retention 곡선 R(t), t=1..8 lag, 주 단위 측정; consolidation '성립' 판정은 ① A가 B·C를 lag≥4에서 prereg δ(예: ≥10pp)로 지배 AND ② A의 decay slope가 계층모형 적합상 유의하게 더 완만해야 함 — 절편 차이만으론 불인정(Ebbinghaus replication, Murre & Dros 2015의 savings/함수형 비교 방식 차용). 2차 endpoint = CLS 예측 기반 schema-generalization probe(학습 에피소드의 novel composition에 대한 전이) — 통합의 고유 서명은 retention이 아니라 일반화라는 Kumaran et al. 2016 논점 반영. Prereg kill 조건 3종: (K1) B가 모든 lag에서 A와 δ 이내 → 보존만으로 충분, 재구조화는 불필요 → claim kill(C1 패턴); (K2) A−C gap이 모든 lag에서 ≤δ → offline phase 기여 0 → kill; (K3) A 우위가 lag 0에서만 성립하고 시간 의존성 없음 → 효과는 consolidation이 아니라 retrieval selection → claim을 retrieval claim으로 재분류(semantic-weight-metric-contract 게이트와 연계). Arm configs·probe set·분석 코드(decay 계층모형)를 run 전 장부에 commit하고 p1v4 방식의 서버 replay 검증으로 봉인. Sleep-time compute(arXiv 2504.13171)는 offline compute가 accuracy+cost 양쪽에서 측정 가능한 이득을 만든다는 선례로, 보조 metric 'latency/token cost per correct answer'를 2차 endpoint에 추가 가능.


**alternatives**:
- Sham-consolidation 4번째 arm 추가: 동일 compute/token budget을 무작위 replay에 소비하는 arm을 두어 '오프라인 compute 자체'가 아니라 '통합 알고리즘'이 효과의 원인임을 분리 (SIESTA의 replay-budget 통제 발상). 비용은 있으나 K2 kill의 해석을 단단하게 함
- 벽시계 주 단위 대신 simulated-lag 설계: LoCoMo/LongMemEval처럼 에피소드 수로 시간을 시뮬레이션(수백 세션 = 수개월)하여 8주를 며칠 내 실험으로 압축. 단, wall-clock decay와 simulated-lag decay의 등가성은 미검증 가정이므로 짧은 wall-clock spot-check arm 병행 필요
- Bayesian sequential 판정: 고정 8주 대신 매주 Bayes factor 갱신으로 조기 kill/조기 성립 허용 — HSWM 과학 피드백 루프의 Bayesian update 단계와 자연스럽게 결합. 단 prereg에 중단 규칙(stopping rule) 자체를 사전 등록해야 optional stopping 오염 방지


**references**:
- https://arxiv.org/pdf/2303.10725v3.pdf
- https://www.nature.com/articles/s41467-022-34938-7
- https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0120644
- https://arxiv.org/html/2504.13171v1
- https://arxiv.org/pdf/2407.12220v1
- https://arxiv.org/html/2311.18807v1
- https://mem0.ai/blog/ai-memory-benchmarks-in-2026
- https://zylos.ai/research/2026-06-08-agent-memory-consolidation-selective-retention-forgetting/
- https://www.greaterwrong.com/posts/wg56edFhuPCsZrncQ/starshard-sleep-inspired-memory-consolidation-for-a-multi


**caveats**: ① 인간 forgetting curve 문헌은 savings 측정 기반이라 HSWM probe 정확도에의 직접 이식은 유추 수준. ② 검색 결과의 다수 2026년 arXiv ID(2601.xxxxx, 2604.xxxxx 등)는 내 훈련 데이터 이후라 원문 전체를 FetchURL로 검증하지 못했고 스니펫 수준 확인에 그침 — 특히 SCM(arXiv 2604.20943)의 'sleep consolidation benefit' 테스트 상세는 미확인. ③ LongMemEval(2410.10813)·LoCoMo(2402.17753)의 정확한 arXiv ID는 2차 인용으로만 확인, 직접 미검증. ④ 'full context가 memory system을 이긴다'는 주장은 LongMemEval 계열 일부 결과에서 관찰되나 context window 한계·lost-in-the-middle(Liu et al. TACL 2024)·context rot(Chroma 2025, 2차 인용)으로 스케일에서 역전 — 즉 append-only control arm의 경쟁력은 probe 규모에 의존하므로 prereg 시 probe 규모를 명시해야 함. ⑤ SIESTA·sleep-replay는 가중치 공간 consolidation이라 HSWM의 store-space consolidation에 직접 대응하지 않음 — ΔW 정의는 semantic-weight-metric-contract 게이트 선결 필요.
