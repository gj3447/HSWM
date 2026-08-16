# PROM 16 HSWM 미증명 — claim ② Agent A→frozen-B 지식 전이

> cycle `prom16-hswm-unproven-claims-20260725` axis-split (L2). 상위 보고서: `PROM_16_UNPROVEN_CLAIMS_2026-07-25.md`.


## b1 :: theory [HIGH]

**한 줄**: frozen-B 전이는 input/logit/activation 3채널로 형식화되고, HSWM(API-블랙박스)은 input-채널만 가능하므로 'self-lesson 대조 G + 오류구조 서명 S' 이중 판별자를 prereg kill 조건으로 가진 4-arm sealed 게이트가 claim ②의 유일한 엄밀 검증 경로다.


**rootCause**: frozen-B 전이 claim이 증명 어려운 근본 이유는 '전이'가 가중치 갱신 없이 관측될 때 세 가지 confound와 구별 불가하기 때문이다: (a) retrieval/priming — B가 원래 할 수 있던 것을 lesson이 꺼내줄 뿐(p1v2 KILL이 정확히 이 경우), (b) generic prompt-engineering lift — A 고유 내용이 아니라 아무 좋은 팁이나 효과, (c) train/test 태스크 분포 leakage. 문헌상 frozen-B 조건의 전이는 인터페이스 깊이별 3채널로 형식화된다. ① input-채널(블랙박스, 텍스트 매개): ExpeL(arXiv:2308.10144)은 경험→자연어 insight 추출→가중치 갱신 없이 추론 시 주입, source→heldout target 태스크로의 forward transfer를 실증 — HSWM typed lesson store의 직접 대응물. ② logit-채널(디코딩 시점): proxy-tuning(arXiv:2401.08565)은 frozen 대형 B의 가중치를 건드리지 않고 소형 proxy의 tuned−untuned 로짓 차이로 B의 출력분포를 이동(z' = z_B + α(z+ − z−)) — 'frozen B에 대한 출력분포 Δ'가 측정 가능하게 정의됨을 존재성으로 증명, 단 동일 tokenizer 필요. ③ activation-채널(화이트박스): model stitching(2106.07682), Patchscopes cross-model patching(2401.06102), cross-model steering vector의 선형변환 전이(2501.02009 — 개념 표현이 단순 선형변환으로 LLM 간 정렬되고 weak-to-strong 전이 성립), Platonic Representation Hypothesis(2405.07987)가 이론적 근거. 측정 형식화의 두 축: Hinton의 dark knowledge(1503.02531)는 전이 내용의 본질이 정답이 아니라 오답 공간의 상대확률 구조임을 보였고, Knockoff Nets(1812.02766)는 블랙박스 기능 전이를 fidelity(agreement rate)와 performance recovery ratio(0.91x~0.97x)로 측정했다. 이 둘을 합성하면 frozen-B 전이의 판별자는 'B가 전이 후 A의 특이적 오류 구조까지 재현하는가'(transfer signature) — 정확도 lift는 priming으로 위장 가능하지만 오류 구조의 상관은 위장이 어렵다.


**recommendation**: HSWM claim ②를 위한 sealed 게이트 T1을 4-arm 대조로 설계하라. A가 태스크 패밀리 F1에서 경험→typed lesson을 store에 축적하고, frozen B(API 모델은 본질적으로 frozen — 가중치 불변 자동 만족)를 heldout F2에서 평가한다. Arm: (1) no-memory (2) B-self lessons — B가 F1에서 스스로 생성한 lesson (3) A-lessons — 진짜 크로스에이전트 전이 (4) placebo generic tips. 1차 metric: G = Acc(3) − Acc(2) > 0, prereg 효과크기 지정(p1v4 포맷이면 6문항 중 ≥2문항 차이 또는 bootstrap CI가 0 배제). 2차 판별자: transfer signature S = corr(B의 arm-3 응답분포[오류 포함], A의 응답분포) − corr(arm-2 응답분포, A의 응답분포). HSWM_LOCAL_RECORD prereg kill 조건 3종: (a) G ≤ 0이면 크로스에이전트 전이는 self-generated lesson 대비 부가가치 없음 → claim ②는 claim ①(에이전트 내부 신용배분)으로 환원, novel kill; (b) S ≤ 0이면 dark-knowledge 전이 부재, lift는 generic priming — 개입 효과를 '전이'로 부르는 것 금지; (c) no-memory arm이 5/6 이상이면 태스크 포화(p1v2 교훈) → 더 어려운 F2로 재등록 후 재실행. sealed run + 서버 replay 검증은 p1v4 절차 계승. 로컬 오픈모델 페어 확보 시 T2(logit-채널, proxy-tuning형 로짓산술)와 T3(activation-채널, cross-model SV 전이)를 상위 형식화로 추가하되 API-only B에서는 out-of-scope로 명시. 이 설계는 미해결 foundation 'multi-agent-transfer-harness'의 게이트 스펙을 직접 채운다.


**alternatives**:
- Activation-채널 우선 형식화: 로컬 오픈모델 A·B 쌍에서 A의 steering vector를 선형변환으로 B에 이식(arXiv:2501.02009의 cross-model transfer)하고 patching success rate + 행동제어 정확도로 측정 — 인과적으로 가장 강한 '전이' claim이 되나 화이트박스 접근이 필요해 HSWM의 API-에이전트 주력 설정과 충돌, 로컬 모델 도입 시에만 유효
- 행동-전용 Knockoff 형식화: 메커니즘 주장 없이 전이 = fidelity(probe set에서 B의 A-모사율) × generalization split 상의 recovery ratio로만 정의 — 정의가 깨끗하고 블랙박스 호환이지만 parroting(A 출력 베끼기)과 진짜 전이를 구별하려면 반드시 heldout 일반화 split과 distractor probe가 필요
- 정보이론(MDL/prequential) 형식화: 전이 = M_A 조건 하 B의 F2에 대한 prequential code-length(누적 log-loss) 감소분. logprob 접근 가능 시 연속형 metric으로 G보다 분산이 작으나, API가 logprob를 주지 않으면 측정 불가라는 실무적 한계


**references**:
- https://arxiv.org/abs/1503.02531
- https://arxiv.org/abs/2305.02301
- https://arxiv.org/abs/2308.10144
- https://arxiv.org/abs/2401.08565
- https://arxiv.org/abs/1812.02766
- https://arxiv.org/abs/2106.07682
- https://arxiv.org/abs/2401.06102
- https://arxiv.org/abs/2501.02009
- https://arxiv.org/abs/2310.01405
- https://arxiv.org/abs/2308.10248
- https://arxiv.org/html/2603.18908v4


**caveats**: 1차 소스 대부분 abstract/HTML 수준 확인(전문 정독 아님). Platonic Representation Hypothesis(2405.07987)는 다수 1차 논문의 인용으로 교차 확인했으나 abs 페이지 직접 열람은 안 함. Cross-model SV 전이(2501.02009)와 proxy-tuning은 주로 동일 tokenizer/모델 계열 내에서 검증 — 임의 이종 API 모델 쌍으로의 일반화는 미확립. 'transfer signature S'(오류구조 상관)는 dark knowledge + Knockoff fidelity의 본 셀 합성 제안이지 단일 문헌의 기성 정식 정의가 아니며, 분산/검정력은 미측정. ExpeL의 forward transfer 실증은 동일 backbone LLM 내 에이전트 간 전이라 이종 모델 A→B에는 간접 증거.


## b2 :: benchmarks [HIGH]

**한 줄**: 선행 실측: 모델 간 naive 기억 전이는 성능을 깎지만(MATH500 -1.6~-8.6pt), 추상화/대조 증류된 기억은 family를 넘어 +12~15pt까지 유효 — HSWM A→B claim은 s/b 분리를 통제한 4-arm TRR 게이트로만 증명 가능.


**rootCause**: Cross-LLM 전이의 성패는 '무엇을 옮기는가'가 아니라 '기억이 task-relevant structure(s)와 model-specific bias(b)를 얼마나 분리하는가'에 달려 있다. MemCollab(2603.23234)이 실측으로 보여준 핵심: 한 모델의 trajectory에서 만든 기억을 그대로 다른 모델에 주입하면 b가 딸려가서 오히려 성능이 하락한다 (Qwen2.5-7B + 32B-기억: MATH500 50.6 vs vanilla 52.2, HumanEval 34.1 vs 42.7; Llama3-8B + Qwen32B-기억: MATH500 18.8 vs 27.4). 반면 대조(contrast)로 s만 증류한 기억은 family를 넘어서도 유효하다 (7B 52.2→67.0, Llama3-8B 평균 41.7→53.9, Qwen32B 70.8→78.2). MTL(2604.14004, ICML)도 같은 구조를 도메인 축에서 확인: 추상 Insight 형식은 cross-model 양방향 유효(+2.6% DeepSeek V3.2, +1.8% Qwen3-Coder)하지만 저추상 Trajectory는 negative transfer를 유발하고, 자기생성 기억이 항상 최고(모델 편향 잔존). 즉 HSWM claim ②(A→frozen-B)가 증명 어려운 이유는 전이 자체가 아니라 'naive ΔW 주입은 순음수가 될 수 있다'는 반증 가능성이 선행 문헌에서 이미 실측됐기 때문이며, 증명하려면 s/b 분리를 실험 설계에 통제변수로 박아야 한다.


**recommendation**: HSWM A→B 전이 sealed 실험을 다음과 같이 설계하라. (1) 교차 family 필수: source A와 frozen B는 서로 다른 모델 family(예: Claude→Qwen 또는 GPT→DeepSeek) — 같은 family면 b 공유로 전이 효과가 과대추정된다(MemCollab 교훈). (2) 4-arm 구조: (a) B no-memory baseline, (b) B + A의 raw lesson 그대로 주입(naive), (c) B + A lesson을 abstraction/contrast로 재작성한 typed lesson, (d) B + B 자기생성 lesson(상한). MemCollab/MTL이 모두 (c)>(d)>(b) 순서이고 (b)는 (a) 아래로 떨어질 수 있음을 보였으므로 이 순서 자체가 검증 대상. (3) Metric을 prereg contract로: Transfer Retention Ratio TRR = (score_arm − score_no-memory)/(score_self − score_no-memory) (PAM의 TCS=target_after/source_before 일반화) + negative-transfer rate(heldout 항목 중 memory arm이 no-memory보다 나쁜 비율). 이것이 미해결 foundation 'semantic-weight-metric-contract'의 구체 후보다. (4) Kill 조건 사전등록: naive arm TRR<0이면 'HSWM typed store는 naive와 구별 안 됨'으로 해당 설계 KILL; abstraction arm TRR≥0.5 & negative-transfer rate≤10%를 성립 기준으로. (5) lesson type별 층별 측정: PAM에서 semantic이 가장 잘 전이되고 working/procedural이 가장 많이 degrade했으므로 HSWM typed lesson도 type별 TRR을 분리 보고. (6) 임베딩 모델은 전 arm에서 고정(Voyager 커뮤니티의 embedding-mixing 실패 재발 방지) + retrieval top-k=3 부근에서 비단조 곡선 확인(MemCollab: k 초과 시 성능 하락).


**alternatives**:
- Contrastive 경로 채택: A와 B(또는 제3의 강한 모델)의 쌍 trajectory를 대조해 (enforce invariant; avoid violation) 형태의 normative lesson만 저장 — MemCollab이 cross-family에서 유일하게 음수 전이를 피한 방식이며 HSWM lesson store의 생성 절차로 직접 이식 가능
- 전이를 '지식'이 아니라 '메타-지식'으로 한정: MTL에서 알고리즘 전략 전이는 이득의 5.5%에 불과하고 검증 루틴·워크플로 등 meta-knowledge가 주된 이득 원천 — HSWM claim ②의 scope를 'procedural meta-knowledge 전이'로 좁혀 prereg하면 증명 난이도가 낮아짐
- PAM식 protocol-level 전이(직렬화+re-hydration)를 baseline arm으로 추가 — 모델 교체 시 TCS 0.83~0.92 재현 여부를 HSWM store와 비교해 '구조화 포맷만으로 충분한가 vs hypergraph 구조가 추가 기여하는가'를 C1 반증(hypergraph 고유 기여 미검출)과 연결해 재시험


**references**:
- https://arxiv.org/html/2603.23234v2
- https://arxiv.org/html/2604.14004v1
- https://arxiv.org/html/2605.11032v1
- https://arxiv.org/pdf/2603.02766
- https://memorytransfer.github.io/


**caveats**: PAM(2605.11032)은 N=50 pilot으로 저자 스스로 'directional not definitive'라 명시했고 arXiv ID/날짜 표기에 이상(2025-01-15 접근일 vs 2026-05-10 v1)이 있어 수치 신뢰도는 낮게 봐야 함. MemCollab 수치는 단일 seed(42), temperature 0, 500 heldout 기준 — 분산은 appendix에만. MTL은 gpt-5-mini가 기억 생성·judge·agent를 겸해 self-preference 편향 가능. Voyager→AutoGPT 스킬 전이(+) 및 self-verification 제거 시 -73%는 2차 소스(beancount 리서치 로그)라 미검증. EvoSkill의 +5.3pp(SealQA→BrowseComp)는 단일 스킬 사례. 이들 모두 '전이가 된다'는 존재 증명이지 HSWM 식 credit-assigned ΔW의 전이를 직접 검증한 것은 아님 — 모두 inference-time memory 주입이며 가중치 갱신 실험은 없음.


## b3 :: pitfalls [HIGH]

**한 줄**: A→B 전이 주장의 오탐은 채널 공유·공유 prior·평가 오염의 세 경로로 구조적으로 발생하며, 카나리 레슨+4-cell 분해+closed-book/xvendor 대조+sham 음성대조를 prereg kill 조건으로 박아야 '검색을 전이로 위장'하는 자기기만을 설계 수준에서 차단할 수 있다.


**rootCause**: A→B 전이 주장이 오탐에 취약한 근본 이유는 '전이 채널'과 '정답 유출 채널'이 물리적으로 동일하기 때문이다. receiver 성능 향상은 (i) donor 산출물/코퍼스에의 직접 접근(retrieval/누수), (ii) 공유 사전분포(같은 base model, 같은 pretraining 데이터, 같은 system prompt/few-shot), (iii) 진짜 증류된 절차 지식, 의 세 성분으로 분해되는데 표준 평가는 이를 분리하지 않는다. 문헌상 실패 사례가 재현 가능하게 보고되어 있다: (1) 벤치마크 오염 — 'Don't Make Your LLM an Evaluation Benchmark Cheater'(arXiv:2311.01964)는 소규모 누수만으로 평가가 무의미해짐을 실증; (2) 메모리 벤치마크 위장 — LoCoMo(~20k token)는 모델 컨텍스트 안에 들어가 외부 메모리 자체가 불필요하고(arXiv:2602.19320), LongMemEval ~5% / LoCoMo 6-7% 라벨 노이즈(arXiv:2604.22085), 프로덕션 엔진 >90% vs 학계 베이스라인 25-40점 차는 게이밍/포화 신호; (3) 공유 prior를 합의/전이로 오독 — stage-gated 리뷰 실험에서 80+ 에이전트가 존재하지 않는 취약점을 만장일치로 지지(공유 training-data prior), 'PoC self-contamination'(자기 산출물을 측정하고 표적 행동으로 오인)이 명명된 실패 모드(arXiv:2604.19049); (4) 채널 공유 = 무엇이든 전파 — LLM-to-LLM prompt infection(arXiv:2505.23847)과 메모리 추출 공격 MEXTRA(arXiv:2502.13172, ACL 2025 acl-long.1227)는 donor→receiver 채널이 열리면 '학습된 지식'이 아니라 임의 콘텐츠가 이동함을 보인다; (5) RAG 평가에서 eval 케이스와 코퍼스 중복이 알려진 confound라 decontamination이 표준 절차가 됨(emergentmind 2605.03344), retrieve-then-filter에서 29.5% answer leakage(ACL 2026 trustnlp-main.15); (6) Voyager 계열 'lifelong learning'은 실제로는 외부 코드 라이브러리 검색+주입이지 가중치 업데이트가 아니라는 점이 커뮤니티에서 자체 지적됨 — '검색을 학습/전이로 위장'한 원조 사례.


**recommendation**: HSWM의 A→frozen-B 전이 sealed 실험에 다음 오탐 차단 장치를 게이트로 박는다. (1) 카나리 레슨: donor store에만 합성 고유 사실(watermark lesson, 실제 태스크와 무관)을 주입하고 채널 차단 상태에서 receiver가 답하면 즉시 누수 판정 → run void. (2) 4-cell 분해 설계: {donor-store on/off} × {eval 항목-코퍼스 overlap/disjoint} — 전이 주장은 on/disjoint > off/disjoint 일 때만 유효하고, on/overlap − on/disjoint 차이가 크면 그 차이는 전이가 아니라 검색으로 라벨링(claim boundary에 명시). (3) closed-book receiver 베이스라인(DRIFT식 parametric control)으로 공유 사전분포 성분을 감산하고, xvendor receiver(다른 base model) 팔을 유지해 same-base-model prior 부풀림을 격리. (4) sham-transfer 음성대조: 무관 도메인 랜덤 레슨 주입 팔이 진짜 팔과 통계적으로 구분되지 않으면 KILL. (5) prereg kill 조건: eval 항목이 donor store와 n-gram/embedding 유사도 임계 초과 시 해당 항목 격리, 격리율 >k%면 sealed run 전체 무효; donor 경험 생성 시각이 eval 세트 확정 이전임을 receipt로 봉인(시간적 누수 차단). (6) retrieval-only 팔을 명시적 대조군으로 두고, 전이 팔이 이를 못 넘으면 p1v2와 동일하게 '개입 효과 0' KILL — '검색≠전이' 선언을 결과가 아니라 설계가 강제하게 만든다.


**alternatives**:
- 주장 경계를 낮추는 대안: retrieval을 전이의 정당한 기질로 인정하되 명명을 'actuation-level transfer'(L0 typed actuation 확장)로 강등하고 ΔW/지식전이 주장은 별도 parametric 증거(파인튠 후 채널 차단 평가)가 있을 때만 허용
- 카나리 주입 대신 membership-inference 스타일 사후 감사: receiver 출력에서 donor store 고유 엔트로피 시퀀스 검출 — 개입 없이 기존 run을 감사 가능하지만 검출력이 낮고 사후성이라 sealed prereg 체계와는 (1)안을 병용하는 것이 적합


**references**:
- https://arxiv.org/pdf/2311.01964v1
- https://arxiv.org/html/2406.04244v1
- https://www.arxiv.org/pdf/2602.19320
- https://www.arxiv.org/pdf/2604.22085
- https://arxiv.org/html/2604.19049v1
- https://arxiv.org/pdf/2505.23847
- https://pdf.arxiv.org/pdf/2502.13172
- https://aclanthology.org/2025.acl-long.1227.pdf
- https://aclanthology.org/2026.trustnlp-main.15.pdf
- https://www.emergentmind.com/papers/2605.03344
- https://arxiv.org/html/2510.10815v4
- https://arxiv.org/abs/2305.16291
- https://www.giskard.ai/knowledge/cross-session-leak-when-your-ai-assistant-becomes-a-data-breach
- https://arxiv.org/html/2601.08237v1


**caveats**: 다수 1차 소스가 2025-2026 arXiv 프리프린트로 피어리뷰 미완. 80+ 에이전트 오합의 사례·PoC self-contamination 수치는 단일 논문(arXiv:2604.19049)의 자기보고. Giskard cross-session leak는 벤더 블로그(2차 소스). LongMemEval/LoCoMo 라벨 노이즈 비율은 수동 검사 기반 추정치. '검색=위장 전이' 판정 기준(유사도 임계, 격리율 k)의 구체 수치는 HSWM 자체 pilot에서 캘리브레이션 필요.


## b4 :: alternatives [HIGH]

**한 줄**: A→frozen-B 전이는 5-arm(무경험/full packet/placebo lesson/raw-log/성분분해) sealed factorial + 3등급 disjoint 코퍼스 감사 + 사전등록 kill 조건으로만 증명 가능 — 단일 arm 개선은 crossover(무관 문서도 효과)와 raw-data 충분성 때문에 증거가 안 된다.


**rootCause**: A→frozen-B 전이가 증명 어려운 근본 이유는 'B가 좋아졌다'는 관측이 전이 claim 외 최소 4개 경쟁 가설로 설명되기 때문이다. (1) 코퍼스 유출 — donor 경험과 receiver 평가 항목의 겹침. AgentHER(arXiv 2603.21357)도 held-out에서 task overlap을 제거하고도 cross-environment 잔존 겹침이 지적됐다. (2) generic-context 효과 — Crossover 실험(arXiv 2605.04361, 10과제×7조건×2700런)은 무관 문서(irrelevant document)가 관련 artifact만큼 성능을 올리거나(최대 20×) 해치는(최대 -46%) 것을 실증했고 방향이 baseline 수준 하나로 예측됨(r=-0.82). 즉 '내용 주입 자체'의 효과와 'A의 지식'의 효과를 통제 arm으로 분리하지 않으면 단일 개선은 증거가 아니다. (3) raw-log 충분성 — A의 원시 로그만 줘도 동일하게 좋아지면 typed lesson/ΔW 패킷의 고유 기여는 0이 되는데, 이는 우리 C1 book-scale(hswm 0.427 vs clique 0.447)과 p1v2 typed lesson KILL에서 이미 겪은 동형 함정이다. (4) receiver 오염 — B의 prompt/tools/readout/budget이 미세하게라도 달라지면 개선은 전이가 아니라 receiver 재구성이다. 결국 증명력은 donor 알고리즘이 아니라 통제 arm 배치와 disjoint 감사에서 나오며, arm 설계가 곧 claim boundary다.


**recommendation**: P2 게이트를 5-arm sealed factorial로 확정하라. 절차: (1) DONOR — A만 코퍼스 D_A(시드 s_A)에서 경험, 생성된 typed lesson+ΔW packet을 p2-transfer-packet.json으로 봉인(sha256 + Merkle provenance root + donor corpus manifest hash — Portable Agent Memory, arXiv 2605.11032의 provenance-DAG 패턴 차용). (2) FREEZE — B의 deployment/prompt/tools/readout/budget manifest를 byte-freeze(기존 Gate C 요건 그대로)하고 PREREG_P2_TRANSFER_<date>.json을 판정 전 등록: claim_boundary.included='byte-frozen B가 모든 통제 arm 대비 disjoint heldout에서 개선', excluded=[ΔW 메커니즘 단정, topology, consolidation], credence/direction/minimum_improvements(p1v4식) 명시. (3) ARMS — B0=무경험, B1=full packet, B2=placebo lesson(스키마·토큰 동일·타 도메인 내용; crossover 논문의 irrelevant-doc 조건), B3=A raw log만(토큰 등가), B4=성분분해(lessons-only / ΔW-only). n≥100/arm, 사전 생성된 동일 token envelope(F1 교훈), arm당 동일 call 수. (4) DISJOINT — Mind2Web식 3등급(cross-task→cross-split→cross-domain) 중 최소 cross-split 이상을 prereg에 지정 + exact-query/entity/template overlap=0 + 임베딩 near-dup 감사 임계값 사전등록(2607.05458의 Appendix D leakage-control 패턴). (5) KILL — B1≤max(B0,B2,B3) 중 하나라도 성립 시 해당 하위 claim 사망(특히 B1≤B3이면 'typed 패킷 필요' 사망 → 'raw 데이터 공유 효과'로 강등, C1 판례와 동일 처리); leakage>0이면 run 무효; freeze 해시 변경 시 무효. (6) PASS — paired bootstrap LCB>0 AND prereg 최소 개선 수 AND deterministic judge sha256 lock + server replay(기존 p1v4 replay 계열 재사용).


**alternatives**:
- Cross-model receiver (예: A=qwen3.5, B=llama 계열) — Portable Agent Memory가 GPT-4/Claude/Gemini/Llama 간 이식을 시연한 선례; 일반성 주장은 강해지지만 rehydration(모델별 lesson 재서식화)이 새 교란이 되므로 동일모델 P2 통과 후 Phase-2로 분리
- Isomorphic reproduction held-out — donor task와 워크플로 동형·엔티티만 재표본화한 receiver 평가셋을 생성해 '절차 전이 vs 정답 암기'를 분리 (SPARK, arXiv 2605.09192의 300 task-variants 패턴; Voyager 2305.16291의 fresh-world zero-shot과 같은 계열이지만 통제 강화판)
- Shuffled-ΔW placebo arm — packet의 ΔW를 엣지 permutation으로 norm은 유지하고 구조만 파괴한 가중치 위약 (Phasor tribunal에서 수입한 timestamp-shuffle falsifier의 가중치판). B1 > shuffled-ΔW여야만 '가중치의 topology-의존 내용'이 active ingredient라는 주장이 서며, 이는 lesson-text 전이(ExpeL 2308.10144/AWM 2409.07429 선례로 novelty 낮음)와 weight 전이(우리 생존 슬롯)를 가르는 결정적 arm
- Round-trip / multi-hop transfer (A→B→fresh A′) — hop 누적 열화 곡선으로 패킷 안정성과 provenance 추적성을 동시 측정; Memory Sharing(INMS, 2404.09982)의 pool 공유 선례를 hop-제한 실험으로 엄밀화


**references**:
- https://arxiv.org/abs/2605.04361
- https://arxiv.org/abs/2605.11032
- https://arxiv.org/html/2607.05458v1
- https://arxiv.org/abs/2308.10144
- https://arxiv.org/abs/2409.07429
- https://arxiv.org/abs/2509.25140
- https://arxiv.org/abs/2505.23187
- https://arxiv.org/html/2603.21357v4
- https://arxiv.org/abs/2404.09982
- https://arxiv.org/abs/2305.16291
- https://arxiv.org/html/2605.09192


**caveats**: Voyager/ExpeL/AWM/ReasoningBank/MAEL 모두 주 평가가 '같은 에이전트의 자기 경험 재사용'이고, 위약 lesson·raw-log 통제를 갖춘 엄밀한 A→frozen-B RCT는 문헌에서 미발견 — 본 5-arm 설계는 선례 조합의 extrapolation이지 기검증 프로토콜이 아니다. Crossover 논문(2605.04361)은 소프트웨어 설계 탐색 과제라 정답형 QA로의 외연은 제한적(2차 소스 없이 abstract만 확인, full text 미정독). Portable Agent Memory는 54개 단위테스트 수준의 공학 프로토콜 데모이며 인과적 전이 효능 증거는 아니다. 2607.05458(harness offline RL)은 frozen LLM + disjoint split + leakage-control 부록의 가장 가까운 방법론 템플릿이나 '학습된 controller'라 수동 packet 전이와 메커니즘이 다르다. SPARK(2605.09192)는 2차 소스(Bytez 요약) 경유 확인 — 300 variants 수치는 원문 재확인 권장.
