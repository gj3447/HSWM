# PROM 16 HSWM 미증명 — claim ③ 학습된 topology rewiring

> cycle `prom16-hswm-unproven-claims-20260725` axis-split (L2). 상위 보고서: `PROM_16_UNPROVEN_CLAIMS_2026-07-25.md`.


## c1 :: theory [HIGH]

**한 줄**: 구조학습 이론은 무gradient 계열(NEAT/WANN/SET-RigL/GPTSwarm)만 HSWM에 이전 가능하며, claim ③ 증명의 열쇠는 WANN식 토폴로지-가중치 분리 프로토콜 + random-rewire 대조군 + 퇴화(chain 붕괴) kill 조건이다.


**rootCause**: 구조학습 이론은 두 계열로 갈리며, HSWM claim ③(topology rewiring)가 미증명인 근본 이유가 여기 있다. (1) 미분가능 계열 — DARTS(1806.09055, bilevel: min_α L_val(w*(α),α)), Gumbel-softmax/Concrete(1611.01144), L0 hard-concrete 게이트(1712.01312), LDS 그래프 구조학습(1903.11960, Bernoulli edge 확률의 hypergradient), Learnable Hypergraph Laplacian(2106.06666, incidence matrix H 파라미터화): 전부 '구조 변수를 연속완화 후 내부 가중치 해를 통해 역전파'를 요구한다. HSWM은 함수 노드=블랙박스 LLM 호출이라 ∂w*/∂α 자체가 정의 불가 → 이 계열의 정식화는 직접 이전 불가하고, 다만 (a) bilevel 분리(외부=토폴로지, 내부=lesson store ΔW) 프레임과 (b) DARTS의 대표 실패모드(α가 skip-connection으로 붕괴, soft score와 이산화 후 성능의 discretization gap)는 경고로 이전된다. (2) 무gradient 계열 — NEAT(Stanley & Miikkulainen 2002, 최소 구조에서 complexification + 역사적 표지 + speciation으로 혁신 보호), WANN(1906.04358, 가중치 학습 없이 공유 랜덤 가중치로 토폴로지 자체 기여 측정), SET(1707.04780)/RigL(1911.11134)(고정 예산 하 주기적 prune-regrow, RigL의 핵심 발견: gradient-informed regrowth > random regrowth), GPTSwarm(2402.16823, LLM 에이전트 그래프의 edge 최적화를 REINFORCE류 score-function으로): 이 계열만 블랙박스 노드에 적용 가능하다. 추가로 C1 book-scale 반증(hswm 0.427 vs clique 0.447)이 보인 '구조 고유 기여 미검출'은 이론상 두 교란으로 설명된다: ① 토폴로지 효과와 가중치/검색 효과의 confound(WANN식 분리 프로토콜 부재), ② 토폴로지 탐색의 퇴화 최소해(chain/skip 붕괴 — DARTS와 에이전트-그래프 문헌 공통 보고). 즉 claim ③은 '측정 변수 미정의 + confound 미분리'이지 개념적 불가능이 아니다.


**recommendation**: sealed 실험 T-REWIRE(claim ③ 게이트)를 다음과 같이 설계한다. 사전등록 측정 변수를 semantic-weight-metric-contract에 먼저 등록: (변수) 하이퍼엣지별 존재확률 π_e(Bernoulli 파라미터, L0 hard-concrete식), drop fraction p, 갱신 주기 ΔT, 밀도 ρ, incidence matrix H, 하이퍼그래프 modularity·spectral gap·diameter, discretization gap(soft π 점수 vs hard 토폴로지 성능차). (고정) p1v4 승자 lesson store를 frozen — 가중치 교란 차단(WANN 원칙: 토폴로지만 변동시켜 효과 귀속). (4 arms, 밀도·갱신횟수 매칭) (i) 학습된 rewiring: credit 상위 유지 + counterfactual-gradient 유사량(lesson 유무 시 heldout 보상차, replay로 측정) 상위 후보에 regrow — RigL analog; (ii) random rewiring — SET control, 이 대조군을 못 이기면 kill; (iii) static 토폴로지 — negative control; (iv) WANN arm: lesson 내용을 run마다 무작위 치환한 상태에서 토폴로지 순위가 안정적인지 — 안정이면 구조 고유 기여 존재, 불안정이면 C1의 clique 근접 결과 재현 확인. (kill 조건, prereg) ① learned ≤ random rewiring → topology-learning 신호 부재로 claim ③ KILL; ② 학습 토폴로지가 chain/star로 퇴화(modularity·diameter 붕괴 감지)하면서 성능 동등 → NUMEROLOGY_HOLD(퇴화 최소해로의 수렴이지 학습 아님); ③ discretization gap > 사전등록 δ → soft 구조 점수 폐기. (게이트 통과 최소조건) learned > random > static의 단조 서열 + replay 검증 + 2 seeds 재현. 비용 상한은 GPTSwarm 사례(edge-opt 수백 달러)를 참조해 사전등록.


**alternatives**:
- NEAT식 점진 복잡화 arm: 완전그래프에서 prune하는 대신 최소 하이퍼그래프(단일 검색 노드)에서 출발해 hyperedge 추가·노드 분할 돌연변이만 허용, speciation analog로 '신규 구조는 N회 평가 전 kill 금지' 보호기간 부여 — 완전그래프 초기화의 퇴화 붕괴 회피, 단 population 비용 증가
- bilevel 대리(surrogate) 해석: LLM 노드의 국소 입출력을 저비용 미분가능 프록시(소형 모델/스코어러)로 근사해 DARTS/LDS식 연속완화 α를 프록시 위에서 학습 후 hard 토폴로지만 실제 HSWM에 이식 — discretization gap을 prereg δ로 강제하는 조건부 채택
- 해석적 대안: claim ③을 '강건성 명제'로 재진술 — 토폴로지가 성능을 올린다가 아니라 '동일 lesson store에서 적대적 rewire(random arm) 대비 학습된 rewire가 성능 저하를 덜 받는다'로 — 반증이 더 쉽고 C1 book-scale 결과와 직접 대화함


**references**:
- https://arxiv.org/abs/1806.09055
- https://arxiv.org/abs/1611.01144
- https://arxiv.org/abs/1712.01312
- https://arxiv.org/abs/1911.11134
- https://arxiv.org/abs/1707.04780
- https://arxiv.org/abs/1906.04358
- https://arxiv.org/abs/1903.11960
- https://arxiv.org/abs/2106.06666
- https://arxiv.org/abs/2402.16823
- https://arxiv.org/abs/2408.08435
- Stanley & Miikkulainen 2002, Evolving Neural Networks through Augmenting Topologies, Evolutionary Computation 10(2)


**caveats**: NEAT 원전(2002)은 2차 인용들로만 확인, PDF 직접 열람 안 함(내용은 학계 정설 수준으로 교차 확인됨). GPTSwarm의 'edge-opt가 chain으로 퇴화' 경향은 후속 서베이(2차 소스) 경유이며 원문 Appendix G는 '내부 노드 토폴로지·스케일 한계'만 명시 — 퇴화 붕괴 주장은 DARTS 측 문헌이 1차 근거. counterfactual-gradient 유사량(lesson 유무 replay 보상차)은 엄밀한 gradient가 아니라 유한차분 추정량으로, 노이즈 분산은 미측정 — semantic-weight-metric-contract에서 신뢰구간 규약 필요. 미분가능 계열(DARTS/LDS/hypergraph Laplacian)은 HSWM 블랙박스 노드에 직접 적용 불가라는 판정은 본 연구의 종합(추론)이며, LLM 호출의 미분가능 프록시 구축 성공 사례가 나오면 재평가 필요.


## c2 :: benchmarks [HIGH]

**한 줄**: 선행 벤치(TGB/OpenGSL/G-Designer/DyLAN)는 토폴로지 개입 효과를 실측 가능함을 보이지만 구조학습이 정적/무작위 대조군을 자주 못 이기므로, HSWM claim ③는 구조변화량(Jaccard churn·GED·spectral shift)과 downstream Δ를 분리한 3-arm(random rewiring 대조) sealed 게이트로만 증명 가능하다.


**rootCause**: claim ③(학습된 topology rewiring)은 원리적으로 실측 가능하다 — 선행 문헌은 구조 개입의 downstream 효과를 표준 벤치에서 수치로 잡아왔다 (TGB에서 TGR rewiring이 tgbl-review +50.5%, tgbl-comment +45.7%, tgbl-wiki +19.3% MRR 개선; G-Designer에서 정적 star/tree 토폴로지는 단일 에이전트 대비 MMLU −1.35%/−0.25%로 오히려 악화, 적응형 토폴로지만 HumanEval +16.81~18.02%; DyLAN importance-score 기반 재편성 MMLU 특정 과목 +25.0%). 그러나 증명이 어려운 근본 이유는 attribution 이중 함정이다: (a) OpenGSL(NeurIPS 2023, 13개 GSL×10 데이터셋 통일 프로토콜)이 구조학습이 vanilla GNN을 일관되게 못 이기며(7/12 방법만 ≥2 데이터셋에서 우위, Roman-empire·Wiki-cooc는 전멸) homophily 같은 구조 프록시와 성능의 상관도 대부분 무의미함을 보였다 — HSWM C1(hypergraph 0.427 vs clique 0.447)은 이 실패 패턴의 그대로 재현이다. (b) G-Designer/GPTSwarm이 보여주듯 토폴로지 효과는 부호가 양방향이라 'rewiring이 일어났다'와 'rewiring이 유용했다'를 반드시 분리 측정해야 한다. 즉 claim ③은 구조 변화량(metric)과 downstream Δ(효과)를 동시에 잡는 2축 게이트 없이는 '변했지만 쓸모없음'과 '안 변했는데 주장함' 두 위양성을 걸러낼 수 없다.


**recommendation**: HSWM 다음 sealed 실험으로 F2-topology-rewiring-gate를 설계한다. (1) 3-arm prereg: arm-A frozen topology(현 p1v4 구성), arm-B random rewiring(동일 churn budget으로 무작위 재배선), arm-C credit-assigned rewiring(①의 신용배분 신호로 edge add/prune). arm-C는 반드시 arm-B를 이겨야 한다 — random churn으로도 이득이 나오면 '학습된' rewiring이 아니라 탐색 노이즈이므로 즉시 kill (p1v2 typed lesson KILL과 동형). (2) 구조변화 metric을 장부에 봉인: 에폭별 edge-set Jaccard churn |E_t Δ E_{t-1}|/|E_t∪E_{t-1}|, 정규화 edit distance (add+del)/|E|, incidence-Laplacian 최소 k개 고유값의 spectral shift ||Δλ_k||₂, 그리고 OpenGSL 교훈상 homophily류 프록시 대신 'typed-edge별 성공률과 연결 밀도의 상관'을 직접 기록. churn이 노이즈 플로어(재시드간 자연 변동) 이하면 'topology learning이 실제로 발생 안 함'으로 claim 공허화 kill. (3) 대조군: G-Designer식 정적 토폴로지(star/tree/clique/chain)를 전부 포함 — HSWM은 자기 ablation뿐 아니라 최선의 정적 토폴로지를 heldout에서 이겨야 성립. (4) TGB식 memorization baseline: 과거 성공 edge를 그대로 재사용하는 EdgeBank류 memorizer가 arm-C와 동등하면 '학습'이 아니라 '기억'이므로 degenerating 판정. (5) 효과 크기 prereg: TGR 사례상 구조 개입 효과는 데이터셋 surprise에 의존하므로, 효과가 나올 조건(높은 edge surprise, frozen보다 새 성공 경로 필요한 태스크)을 사전 명시하고 조건 미충족 태스크에서의 무효과는 반증이 아니라 scope 확인으로 분류. (6) replay 검증: 최종 topology 스냅샷 시퀀스를 장부에 저장해 재실행 시 동일 rewiring 궤적 재현 확인.


**alternatives**:
- 노드 수준으로 격하: DyLAN식 Agent Importance Score로 edge가 아니라 노드(lesson/actuator) pruning만 학습하는 것으로 claim ③ 범위를 축소 — 구조 변화 metric이 노드 활성 벡터 변화로 단순화되고 attribution이 쉬워짐
- '학습' 포기 + '검색' 채택: MASS/AFlow식으로 topology를 offline 검색 공간으로 취급하고 best-of-N 정적 토폴로지를 봉인 — claim ③은 반증 처리하되 실용 효과는 확보, LakatoTree에는 'rewiring은 학습 아닌 선택'으로 기록
- TGR식 외생 rewiring 주입: 학습 대신 expander 기반 rewiring을 주기적으로 삽입해 토폴로지 효과의 상한을 먼저 측정 — 상한 자체가 noise 이하면 claim ③을 태스크 수준에서 조기 kill


**references**:
- https://arxiv.org/abs/2307.01026
- https://tgb.complexdatalab.com/docs/leader_linkprop/
- https://arxiv.org/abs/2406.02362
- https://proceedings.neurips.cc/paper_files/paper/2023/file/39f8ef62e061042cca8c8f46d7e0e31b-Paper-Datasets_and_Benchmarks.pdf
- https://arxiv.org/abs/2402.16823
- https://arxiv.org/abs/2410.11782
- https://arxiv.org/abs/2310.02170
- https://www.ifaamas.org/Proceedings/aamas2021/pdfs/p964.pdf


**caveats**: OpenGSL·G-Designer의 개별 수치(정확한 accuracy 표)는 PDF 표 이미지로만 제공되어 정확값은 snippet 수준에서만 확인함(−1.35%/−0.25% MMLU, +16.81~18.02% HumanEval, TGR +50.5%/+45.7%/+19.3%는 1차 소스 텍스트에서 직접 확인). TGB leaderboard의 현재 모델별 MRR 절대값은 미확인. MAGIC(AAMAS'21)은 hard-attention scheduler로 통신 그래프를 sparsify한다는 점까지만 1차 확인, 구체 성공률 수치 미인용. GPTSwarm의 edge REINFORCE가 adversarial agent를 우회한다는 결과는 본문 부록 D 기반이나 정량치는 미추출. spectral shift·Jaccard churn은 그래프 동역학 표준 지표이나 HSWM hypergraph에의 직접 적용 선례(incidence-Laplacian 스펙트럼)는 본 조사에서 1차 소스를 찾지 못함 — 설계 제안으로 분류.


## c3 :: pitfalls [HIGH]

**한 줄**: 위상 학습 주장의 4대 함정(가중치 교란·metric 무디기·강력한 랜덤 null·축약 소실)이 문헌에서 전부 실증되어 있고, HSWM은 삼분할 랜덤-재배선 null + metric-감도 선행게이트 + hypergraph-native 평가 + 반사실 통제를 prereg kill 조건으로 박아야 한다.


**rootCause**: 위상 학습 주장은 관측상 구조적으로 교란(confounded)되어 있다: (1) 가중치와 위상이 공동 변화하는 시스템에서 최종 성능은 위상 기여를 분리해낼 수 없다 — NAS에서 훈련 프로토콜(가중치 수준 교란)이 아키텍처 선택보다 4배 이상 큰 효과(>3pp vs <0.69pp, Yang et al. ICLR 2020; 214개 랜덤 아키텍처가 1pp 이내 수렴). (2) 구조 metric(차수분포/모듈성/엔트로피) 자체가 재배선 다수에 불변이고 가중치 변화에도 반응해, metric이 움직였다는 것이 실재하는 재배선의 증거가 되지 못한다 — 고정 위상에서 attention/활성 패턴 변화가 출력과 무관하게 임의 변형 가능함이 입증됨(Jain & Wallace 2019). (3) 랜덤 위상 베이스라인이 본질적으로 강력 — 탐색 공간 자체가 평균 구조가 잘 작동하도록 설계되어 대부분의 GSL 알고리즘이 kNN/랜덤 그래프 베이스라인을 넘지 못하는 구간이 존재(GSLB, NeurIPS 2023, 특히 heterophilic TI 시나리오). (4) hypergraph→clique 축약은 연구 대상 객체 자체를 파괴해, 고차 구조 우위가 실재해도 축약 후 측정에서는 탐지 불가(AllSet, Chien et al. ICLR 2022 — clique expansion 기반 HGNN이 표현 불가능한 hypergraph 함수 존재 입증; Llabrés et al. — overlap 정보 소실로 유사 시스템 구분력 하락). 이것은 HSWM C1 kill(hswm 0.427 vs clique 0.447)과 정확히 동형이다. 즉 오탐(가중치 효과를 구조로 오인)과 미탐(실재 재배선을 metric이 못 잡음)이 양방향으로 존재한다.


**recommendation**: HSWM claim-③(위상 rewiring)에 대해 다음 4중 게이트를 prereg에 박아라. (G1) 삼분할 frozen 실험: 학습된 위상 arm vs 차수보존 랜덤 재배선 null arm vs 고정 위상 arm — 동일 가중치/동일 프로토콜/동일 예산. Yang et al.의 RI(relative improvement over random-sampled structure) 지표를 그대로 채용해 RI<미리 정한 margin M이면 kill. 랜덤 arm을 이기지 못하는 '위상 학습'은 허위. (G2) metric-감도 선행 게이트: 구조 변화 metric을 증거로 쓰기 전에, 해당 metric이 알려진 재배선 k종(부분 재배선/전체 재배선/차수보존 셔플)을 실제로 구분함을 합성 실험으로 입증. 구분력 없는 metric으로는 '구조가 바뀌었다/안 바뀌었다' 어느 쪽도 주장 금지 — 이는 미해결 foundation 'semantic-weight-metric-contract'에 직접 해당. (G3) hypergraph-native 평가 강제: clique 축약 그래프에서만 측정된 위상 우위 주장은 자동 기각(C1 kill 재발 차단). hyperedge overlap·고차 경로 등 native metric을 병기하고, 축약 후 우위 소실이 관측되면 '축약 손실'인지 '우위 부재'인지 AllSet식 표현력 분석으로 분리. (G4) Jain-Wallace식 반사실 통제: 고정 위상에서 라우팅 가중치만 셔플/적대 변형했을 때 성능이 불변이면 라우팅 패턴 변화를 구조 학습 증거로 쓰지 못함 — kill 조건에 명시. sealed run + replay 검증은 기존 LakatoTree 장부 체계에 이 4게이트를 prereg kill 조건으로 등록해 HARKing을 원천 차단.


**alternatives**:
- 주장 수준 하향: '위상 학습'이 아니라 'hypergraph-native 인코딩의 설계 우위'만 주장하고 학습 주장은 보류 — GSLB에서 GSL 실제 개선 구간(heterophilic TR)이 존재하듯, HSWM도 자기 태스크에서 우위가 검증된 레짐에만 claim을 한정하는 방어적 전략
- 기능적 증거 경로: 구조 metric 대신 인과적 edge ablation(특정 hyperedge 제거 시 성능 델타)로 재배선의 기능적 효과를 직접 측정 — metric이 재배선을 못 잡는 문제를 우회
- 제약된 위상 가족 내 주장: 임의 rewiring이 아니라 prereg된 좁은 변형 가족(예: hyperedge 분할/병합 연산 2종) 내에서만 적응을 주장해 탐색 공간 교란을 축소


**references**:
- https://openreview.net/pdf?id=HygrdpVKvr (Yang, Esperança, Carlucci — NAS Evaluation is Frustratingly Hard, ICLR 2020)
- https://openreview.net/forum?id=H1loF2NFwr (Sciuto et al. — Evaluating the Search Phase of NAS, ICLR 2020; weight-sharing NAS ≤ random search)
- https://arxiv.org/abs/2310.05174 (Li et al. — GSLB: Graph Structure Learning Benchmark, NeurIPS 2023; 다수 GSL 알고리즘이 kNN/랜덤 베이스라인 미만 구간)
- https://arxiv.org/abs/1902.10186 (Jain & Wallace — Attention is not Explanation, NAACL 2019)
- https://openreview.net/pdf?id=hpBTIv2uy_E (Chien et al. — You are AllSet, ICLR 2022; clique expansion 표현력 한계 입증)
- https://arxiv.org/abs/1911.11134 (Evci et al. 2020 — RigL 원전; random vs gradient growth ablation 맥락) · 코드: https://github.com/google-research/rigl
- https://arxiv.org/html/2510.12096v1 (Rethinking the Role of Dynamic Sparse Training, 2025 — 위상 진화의 역할 재검토)
- https://www.arxiv.org/pdf/2503.16959v2 (고차 시스템 비교에서 clique projection이 구조 정보 소실·구분력 하락 유발)
- http://link.aps.org/doi/10.1103/wy1x-3px8 (Llabrés et al. — Reducibility of higher-order to pairwise interactions)


**caveats**: 함정이 보편적 kill은 아님: GSLB는 heterophilic 그래프 등에서 GSL의 실제 개선도 보고했고, RigL의 gradient growth는 random growth를 이미지 분류에서 유의하게 상회 — 랜덤 동등성은 레짐 의존. Jain & Wallace는 NLP attention 맥락으로 HSWM 라우팅에의 적용은 유추. Llabrés et al.(2026)과 arXiv 2510.12096은 최신이라 독립 재현 미확인. GSLB의 '랜덤 네트워크' 논평은 TI 시나리오 한정 해석이 정확. RigL 본문 ablation 수치는 원문 미열람(2차 인용 수준).


## c4 :: alternatives [MEDIUM]

**한 줄**: 토폴로지 학습 증명의 유일 경로는 W-동결 4-arm(학습/셔플/clique/랜덤) + 엣지 ablation 인과곡선 + 구조-성능 상관의 3축 인과설계이며, 각 축이 C1 clique kill의 후속판인 prereg kill 조건 3개(K1 대조군 추격, K2 평탄곡선, K3 무상관)와 1:1로 대응한다.


**rootCause**: 토폴로지 학습(③)이 증명 어려운 근본 이유는 3중 교란(confound)이다. (i) ΔW(lesson store 내용 변화)와 ΔE(엣지/위상 변화)가 학습 중 공변하므로 성능 향상을 위상 탓으로 돌릴 수 없음 — WANN(Gaier & Ha 2019)이 보여주듯 위상+랜덤공유가중치만으로도 태스크가 풀리고, 반대로 내용만 좋아져도 풀리므로 어느 쪽이 인과인지 분리 필수. (ii) LLM-MAS 선행의 null 결과들 — AgentPrune(ICLR 2025)은 통신 그래프의 대부분 엣지가 인과적으로 불활성(제거해도 성능 유지)임을 formal하게 보였고, 우리 C1 book-scale에서도 clique 축약이 hypergraph-native를 역전(0.447 vs 0.427)했다. 즉 '평탄한 ablation 곡선'이 이 도메인의 디폴트 귀무이며, 관측적 상관(학습과 함께 위상도 바뀌고 성능도 좋아짐)으로는 절대 증명 불가. (iii) 따라서 유일한 증명 경로는 인과 개입 설계뿐: W를 동결하고 위상만 변수로 둔 뒤 (a) 엣지 제거 인과곡선이 학습된 엣지에서 단조·유의하게 가파르고, (b) 학습된 위상이 degree-matched 셔플/랜덤/clique 대조군을 prereg CI margin 밖에서 이기고, (c) 체크포인트 간 위상 편집거리 변화량과 heldout 성능 변화가 상관해야 한다. 이 3개축 각각이 독립 kill 조건을 구성한다.


**recommendation**: 최소 sealed 프로토콜 'T1-topo'를 제안한다. (1) 교란 차단: typed lesson store를 체크포인트 W*에서 동결, LLM·예산·시드 고정, 위상만 변수(WANN식 통제). (2) 4개 arm × fresh heldout n≥30 태스크: A=학습된 위상 E_learned / B=셔플 위상(동일 degree sequence·동일 hyperedge 수, 랜덤 재배선 — C1 clique kill의 직계 후속 대조군) / C=clique 완전그래프(C1 기저 재현) / D=|E| 매칭 랜덤 sparse. (3) 엣지 ablation 인과곡선: arm A에서 hyperedge를 leave-one-out Δ성능(화이트박스 아니므로 EAP 직접 적용 불가, 블랙박스 LOO 중요도) 순위로 정렬, top-k 제거 k=0..|E| 곡선 vs 동일 k의 랜덤 엣지 제거 곡선 비교 — prereg된 AUC gap 효과크기 요구. (4) 구조-성능 상관: 학습 전 과정 체크포인트 간 위상 편집거리와 heldout Δ성능의 Spearman ρ + CI 사전등록. (5) Kill 조건(C1 clique kill 후속판, 전부 prereg): K1=arm B/C/D 중 하나라도 A를 CI margin 내에서 따라잡으면 topology-learning claim kill(구조가 인과적 일을 안 함); K2=top-ranked 엣지 제거와 랜덤 엣지 제거의 AUC gap CI가 0을 포함하면 kill(평탄 곡선=AgentPrune식 null 재현); K3=ρ CI가 0 포함이면 '학습' 부분만 kill(정적 구조 효과로 강등). (6) 봉인: prereg을 LakatoTree 장부에 선기록, 프롬프트/가중치/시드 sha256, 서버측 replay로 표본 재검증(p1v4 방식). 비용: 4arm×n30 + 곡선용 ~|E|스텝×n30 — 대규모 신규 인프라 불요, 기존 게이트 체계에 그대로 탑재 가능.


**alternatives**:
- DyLAN식 기여도-메트릭 재배선(unsupervised importance score로 엣지/노드 선별): 인과곡선보다 싸지만 관측적이라 인과 보증이 약함 — K2를 통과 못할 때 fallback 스크리너로 사용
- AgentDropout Table 6식 전이-증거: 분포 P에서 학습된 위상을 분포 Q에서 랜덤 위상과 대조 — 학습된 구조의 일반화를 보여주는 보조 축이나 인과곡선을 대체하진 못함(multi-agent-transfer-harness foundation과 결합 가능)
- MacNet식 거시 위상-클래스 비교(irregular vs regular, 에이전트 수 스케일에 따른 logistic 성장): '위상 클래스가 문제된다'까지만 보여주고 '학습됐다'는 못 보여줌 — 값싼 pre-screen으로만


**references**:
- https://arxiv.org/abs/2304.14997
- https://arxiv.org/abs/2310.10348
- https://arxiv.org/abs/2410.02506
- https://arxiv.org/abs/2503.18891
- https://arxiv.org/abs/2402.16823
- https://arxiv.org/abs/2310.02170
- https://arxiv.org/abs/2410.11782
- https://arxiv.org/abs/2406.07155
- https://arxiv.org/abs/1906.04358
- https://arxiv.org/abs/2410.10762


**caveats**: EAP/ACDC는 트랜스포머 내부 화이트박스(activation patching) 기법이라 HSWM의 LLM-호출 라우팅 hyperedge엔 직접 적용 불가 — 블랙박스 leave-one-out Δ성능 중요도로 대체 설계가 내 합성이며 검증된 선행은 아님. GPTSwarm/AgentPrune/AgentDropout 결과는 소규모 에이전트·특정 벤치마크라 통계적 설계 패턴(랜덤그래프 대조군, 마스크 프루닝)만 이식 가능하고 효과크기는 이식 불가. MacNet 'irregular>regular'와 AgentDropout 전이표는 초록/HTML 수준 확인이고 원문 수치 재분석은 미수행. WANN은 continuous control/MNIST 도메인이라 LLM lesson-store 그래프로의 비유이지 직접 증거 아님. n≥30, CI margin 등 구체 수치는 내 제안값이며 power analysis 미수행.
