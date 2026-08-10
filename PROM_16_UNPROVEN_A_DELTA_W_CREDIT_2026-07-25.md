# PROM 16 HSWM 미증명 — claim ① 결과→신용배분→ΔW 학습

> cycle `prom16-hswm-unproven-claims-20260725` axis-split (L2). 상위 보고서: `PROM_16_UNPROVEN_CLAIMS_2026-07-25.md`.


## a1 :: theory [MEDIUM]

**한 줄**: frozen-LLM+외부 스토어의 ΔW는 '버전 해시+typed 편집 로그'로 관측성은 공짜이고, 진짜 미증명은 신용 추정치의 예측력 — Shapley/LOO(최적합) 또는 포함마스크 REINFORCE로 추정한 신용이 동일 크기 무작위 편집을 fresh heldout에서 이기는가가 claim ①의 유일한 결정 실험이다.


**rootCause**: claim ①(결과→신용배분→ΔW)가 증명 어려운 근본 구조는 '파라미터 공간의 이산성 + 이중 귀속 문제'다. frozen-LLM에서 외부 가중치 W는 실수 벡터가 아니라 이산 텍스트 객체 집합(레슨/엣지)이라 ∇J(W)가 정의되지 않고, 귀속도 2단계다: (a) 결과→어떤 레슨 탓인가(localization), (b) 어떤 편집이 그 행동 변화를 만들었는가(mechanism). 문헌상 5개 후보 이론의 적합성 판정: (1) policy gradient(REINFORCE, Williams 1992)는 W의 '레슨 포함 여부'를 확률적 마스크로 재매개변수화하면 원리상 불편 추정 가능하나 분산이 치명적 — baseline 필수; (2) REBAR(1703.07370)는 미분가능 relaxation을 전제하므로 텍스트 보상에 직접 부적합, RELAX식 학습된 critic으로 퇴화시키면 미검증 학습자를 하나 더 믿어야 해 최약 후보; (3) ES(1703.03864)는 0차 추정이라 frozen-LLM에 원리상 적합하나 섭동 공간(의미 미터릭)이 필요 — 정확히 미해결 foundation 'semantic-weight-metric-contract'에 블록됨; (4) black-box credit(Data Shapley 1904.02868, LOO)은 V(S)=스토어 부분집합 S로의 held-out 기대성능으로 정의되므로 frozen-LLM에 가장 자연스럽고 검증독립적, 단 비용과 pairwise 상호작용(hyperedge) 귀속이 한계 — C1(clique>hypergraph) 결과와 정합: 엣지 귀속 측정 전까지 아이템 단위 귀속만 신뢰; (5) weight-diff probe(DIT 2510.05092, Watch the Weights 2508.00161, Task Arithmetic)는 ΔW를 1급 관측 객체로 다루는 형식 입장을 제공하되, HSWM은 오히려 이 문제가 반전됨 — 외부 스토어라 ΔW 관측성은 버전 해시+편집 로그로 공짜로 해결되고, 어려운 것은 'ΔW의 의미론(어떤 편집→어떤 행동변화)' 즉 인과 귀속이다. 결론적으로 claim ①의 정확한 형식화는: W_t=버전 해시된 typed 스토어 스냅샷, ΔW=편집 연산자 집합 {insert,delete,reweight,add_edge,remove_edge}의 커밋된 레코드(ΔW 자체가 완전 관측 가능 변수), 신용 φ_i = Shapley/LOO 또는 확률적 포함-REINFORCE 추정치, 업데이트 = 검증 게이트를 통과한 argmax 편집. 입증된 선행 구현체들(ExpeL 2308.10144, DSPy 2310.03714, OPRO 2309.03409, Promptbreeder 2309.16797, TextGrad 2406.07496, Trace 2406.16218, GEPA 2507.19457)은 모두 형식 신용이론 없이 '결과→편집' 루프가 frozen-LLM에서 작동함을 보여주므로, HSWM이 증명해야 할 것은 루프의 존재가 아니라 '신용 추정치가 무작위 편집 대비 예측력을 갖는가'다.


**recommendation**: 다음 sealed 실험 'delta-w-credit-1' 설계: (1) 태스크 선정에 난이도 게이트 — p1v2 킬(base retrieval이 이미 6/6 해결해 개입효과 0) 재발 방지로, frozen+base retrieval 정답률 30~70% 구간의 heldout만 채택. (2) 3-arm prereg: (a) credit-informed 편집 — TMC-Shapley(예산 캡) 또는 Bernoulli 포함마스크 REINFORCE+baseline으로 검색된 레슨별 φ_i 추정 후 상위 신용/하위 반신용에만 편집 적용; (b) 동일 크기 무작위 편집(삽입/삭제/reweight 수 동일, 타깃만 랜덤) — '아무 변화나 도움' 대조; (c) verbal-gradient arm(TextGrad/Trace식 LLM critic이 trace 보고 편집 제안) — 휴리스틱 귀속 vs 기계적 귀속 비교. (3) 신용 자체의 falsifiable metric 신설: credit-validation gate — 추정 φ_i와 probe 부분집합 실측 LOO ΔV의 순위상관(Spearman)을 사전등록하고, 상관 ρ<0.2면 '신용 추정치가 무정보'로 해당 arm 폐기. (4) 최종 kill 조건: fresh heldout(서버 replay 검증, p1v4 방식)에서 (a)−(b) ≤ 0 이면 claim ① 미증명 유지; (a)−(b)>0 AND ρ≥0.2 AND (a)≥(c) 시에만 '기계적 신용배분 성립' 1차 판정. (5) ΔW 관측성은 Longinus sha256 결합 그대로: 스토어 스냅샷 해시 + typed 편집 로그를 장부에 기록해 ΔW를 replay 가능한 1급 변수로 고정. (6) 하이퍼엣지 귀속은 금지(C1 교훈) — 아이템 단위만, 엣지 귀속은 Shapley interaction index 비용이 감당될 때 별도 사이클. (7) 보조 해석: ES/GEPA 계열은 진화론적 프레임(레슨 population fitness)이므로, 그래디언트 유사 ΔW가 반증되더라도 계통 기반 변형으로 claim ①을 재서술하는 escape hatch를 prereg에 명시.


**alternatives**:
- 진화론적 재서술: ΔW를 그래디언트 유사 업데이트가 아니라 Promptbreeder/GEPA식 population-based 진화로 형식화 — 레슨 계통(lineage)에 fitness를 붙이고 신용배분 문제 자체를 우회. DSPy/MIPRO가 이미 이 경로로 실용 성공, 단 '학습'의 최소 정의(fitness 단조 증가 재현)만 요구하도록 claim을 약화해야 함
- 학습된 critic 경로(RELAX 변형): outcome→텍스트 피드백 critic을 별도 학습해 control variate로 쓰면 분산 감소 가능하나, critic 검증이 새로운 미증명 claim을 추가하므로 sealed 체계와 충돌 위험 — 2순위
- 조합 게임 프레임 확장: Shapley interaction index로 (레슨, 엣지) 쌍 귀속까지 확장 — hypergraph 고유 기여를 직접 측정하는 유일한 정통 경로이나 비용이 지수적이라 Monte Carlo truncation + 소규모 probe 스토어(≤30 레슨)에서만 실행 가능


**references**:
- https://arxiv.org/abs/2406.07496
- https://arxiv.org/abs/2406.16218
- https://arxiv.org/abs/2507.19457
- https://arxiv.org/abs/2309.16797
- https://arxiv.org/abs/2309.08532
- https://arxiv.org/abs/2309.03409
- https://arxiv.org/abs/2310.03714
- https://arxiv.org/abs/1703.03864
- https://arxiv.org/abs/1703.07370
- https://arxiv.org/abs/1904.02868
- https://arxiv.org/abs/2510.05092
- https://arxiv.org/abs/2508.00161
- https://arxiv.org/abs/2308.10144
- https://arxiv.org/abs/2502.16863
- https://arxiv.org/abs/2604.09459
- https://arxiv.org/abs/2605.02801
- https://doi.org/10.1007/BF00992696


**caveats**: ① Data Shapley와 LLM-MAS credit 서베이(2605.02801), credit 서베이(2604.09459)는 초록/초록+HTML 일부 확인, 전문 정독 아님. ② GEPA(2507.19457)는 타 논문 참조문헌 인용으로 확인, 원문 미열람 — 'RL outperform' 주장은 저자 자체 보고. ③ TextGrad의 Nature 게재는 2차 블로그 출처라 미검증, arXiv 본문 기준으로만 인용. ④ 제안한 Bernoulli 포함마스크 REINFORCE 추정치는 본 셀의 신규 합성(직접 검증된 선행 구현 아님) — 불편성은 score-function 항등식에서 따라오나 실제 분산/수렴은 미측정. ⑤ REBAR '최약' 판정은 frozen-LLM에 미분가능 surrogate가 없다는 구조 논증이며, 텍스트 연속완화 연구가 생기면 재평가 필요. ⑥ Shapley 비용: V(S) 평가 1회 = rollout 배치라 예산 현실성은 sealed run 설계 시 별도 산정 필요.


## a2 :: benchmarks [MEDIUM]

**한 줄**: 결과→ΔW 갱신의 선행 실측은 전부 knockout ablation 기반(Reflexion +22pt/Voyager random-curriculum −93%/ExpeL insights-retrieve 분해/AWM +24.6~51.1% relative/TextGrad 23→36%)이며, 개별 레슨 단위 인과 신용배분(LOLO) metric은 공백 — HSWM은 ablation parity + LOLO 2중 게이트로 관행 상한을 넘어야 한다.


**rootCause**: 선행 에이전트 메모리/레슨 시스템에서 '결과→가중치/정책 갱신'을 실측으로 보고한 사례는 다수 존재하나, 그 증거 형태가 전부 '개입 vs 무개입/부분개입 간 다운스트림 태스크 성능 차이 + 구성요소 knockout ablation' 한 종류다. ΔW 자체를 측정하는 metric(의미적 가중치 변화량, 개별 레슨 단위 인과 기여도)은 어느 시스템도 보고하지 않았다. 검증된 수치: (1) Reflexion (arXiv:2303.11366, 초록 확인): HumanEval pass@1 91% vs GPT-4 80%; 2차 요약(Emergent Mind) 기준 AlfWorld +22pt, HotPotQA +8pt, 코드 +11pt, 버퍼 길이 1~3 통제. (2) Voyager (arXiv:2305.16291, 논문 PDF ablation 섹션 확인): random curriculum 교체 시 발견 아이템 수 −93%, 수동 curriculum은 자동 curriculum의 28%만 달성; skill library 제거 시 후반부 성능 plateau — curriculum/skill-library가 ΔW 갱신의 인과 요소임을 knockout으로 입증. 통제는 동일 GPT-4 기반 AutoGPT/ReAct 베이스라인(3.3× items). (3) ExpeL (arXiv:2308.10144, 정문+부록 표 확인): ALFWorld put 환경 Act 46 / ReAct 50 / insights-only 61 / retrieve-only 73 / full 83, clean 환경 39/61/87/74/74 — 레슨 store를 insights/retrieve로 분해해 각각의 기여를 분리 측정한 드문 사례. train/test 태스크 집합 분리(heldout single-try) 통제. HotpotQA에서 Reflexion R3 39%와 ExpeL 40% 대등. (4) AWM (arXiv:2409.07429, 초록 확인): Mind2Web +24.6%, WebArena +51.1% relative success, online/offline 모드 + cross-task/website/domain heldout 일반화. (5) TextGrad (arXiv:2406.07496): LeetCode Hard completion 23%→36% (Reflexion 31% 상회), GPQA zero-shot 51%→55%, MMLU ML 85.7→88.4 — 'textual gradient'라는 이름의 ΔW지만 측정은 역시 최종 정확도뿐. (6) MemoryLLM (arXiv:2402.04624): 7B에 1B memory pool, ~1M self-update 후 기능 저하 없음 — ΔW=실제 latent 파라미터이지만 outcome-driven credit이 아닌 지식 주입 지표(zsRE/CounterFact/LongBench)만 보고. 공통 구조: '갱신 메커니즘 존재'의 증명 수준은 knockout ablation이 상한이며, 개별 레슨→개별 결과의 신용배분 정량화(leave-one-lesson-out)는 아무도 안 했다. 이것이 HSWM claim①이 참조할 benchmark 관행의 실체다.


**recommendation**: 선행 관행의 상한(knockout ablation)을 그대로 받되 한 단계 올린 sealed 실험을 설계한다. (a) 게이트 G-DW1 'ablation parity': prereg 4-arm — full typed-lesson / random-order lesson injection(Voyager의 random curriculum 대응) / retrieve-only / no-memory. Voyager 패턴에 따라 full 대비 random-order arm의 성능 붕괴가 재현되어야 하고, ExpeL 패턴에 따라 retrieve-only가 full의 부분집합 효과여야 한다. kill 조건: full − max(나머지 arm) < prereg δ(예: heldout success +5pt)이면 claim① 해당 span novel kill 발동(p1v2 KILL 전례와 동일 규약: base retrieval이 이미 해결하는 과제는 개입 효과 0으로 폐기). (b) 게이트 G-DW2 'per-lesson credit': 선행 어디에도 없는 leave-one-lesson-out(LOLO) 측정 — store에서 레슨 i를 하나씩 제거한 replay를 돌려 Δsuccess_i를 산출, 양(+)의 인과 기여를 가진 레슨 비율을 metric으로 prereg. kill 조건: 양의 기여 레슨 비율이 유의수준 내에서 0과 구분 불가면 ΔW credit 미검출 선언. (c) 통제: AWM/ExpeL처럼 train/test 태스크 heldout 분리 + 동일 backbone 동일 프롬프트 + p1v4식 서버 replay 검증을 전 arm 공통 적용. effect size는 절대 포인트 + bootstrap CI로 보고(relative %만 보고한 AWM식 보고 금지). (d) 이 두 게이트는 LakatoTree 장부에 'benchmark 관행 대비 초과 증거(knockout 상한 돌파)'로 기록되어 semantic-weight-metric-contract foundation과 연결된다.


**alternatives**:
- 대안 A: LOLO 대신 Shapley-style 레슨 기여도(부분집합 샘플링 근사)를 쓰면 비용은 증가하지만 상호작용 효과까지 포착 가능 — 단 sealed replay 비용이 arm 수×샘플 수로 폭증하므로 1차는 LOLO, Shapley는 G-DW2 통과 후 2차 정밀화로 유보
- 대안 B: TextGrad식 'textual gradient' 프레임을 채택해 ΔW를 자연어 diff로 정의하고 diff 크기(토큰/임베딩 거리)를 중간 metric으로 삼는 경로 — 단 이는 outcome credit이 아니라 update 형식의 명명일 뿐이라는 점에서 claim①의 증거로는 약하고, semantic-weight-metric-contract 쪽 subaxis에 더 적합


**references**:
- https://arxiv.org/abs/2303.11366
- https://arxiv.org/abs/2305.16291
- https://voyager.minedojo.org/assets/documents/voyager.pdf
- https://arxiv.org/html/2308.10144v2
- https://ar5iv.labs.arxiv.org/html/2308.10144
- https://arxiv.org/abs/2409.07429
- https://arxiv.org/abs/2406.07496
- https://www.emergentmind.com/papers/2406.07496
- https://arxiv.org/abs/2402.04624
- https://www.emergentmind.com/topics/reflexion-memory
- https://arxiv.org/abs/2304.03442


**caveats**: Reflexion의 AlfWorld +22pt/HotPotQA +8pt/코드 +11pt 및 '130/134(97%)'는 2차 요약(Emergent Mind) 출처로 논문 본문 표를 직접 대조하지 못함(초록의 HumanEval 91%/80%만 1차 확인). ExpeL 전체 평균 성공률은 환경별 표(put/clean)만 직접 확인했고 전체 합산 수치는 미확인. Generative Agents (2304.03442)는 ablation 정성 결과(observation/planning/reflection 각각이 believability에 critical)만 초록으로 확인했고 component별 정량 점수는 검색 네트워크 오류로 미확정 — 정량 인용 불필요하다 판단하여 제외. MemoryLLM '~1M updates 무저하'는 2개 2차 소스 일치이나 논문 표 직접 대조는 못 함. AWM steps 7.9→5.9는 Emergent Mind 단일 2차 출처. Voyager 3.3×/15.3×는 프로젝트 사이트/초록 계열 출처.


## a3 :: pitfalls [HIGH]

**한 줄**: ΔW 오탐의 4대 함정(actuation↔learning 혼동, headroom 포화, judge 순환성, freeze ablation 생략)은 문헌상 실증되어 있고, 4-arm(frozen/learned/shuffle/no-memory)+headroom 밴드+이종 judge 설계가 유일한 차단책이다.


**rootCause**: ΔW 학습 주장의 오탐은 구조적이다: HSWM류 시스템에서 '가중치'는 외부 스토어의 메타데이터이고, 그것을 쓰고·읽고·평가하는 주체가 전부 같은 LLM 계열이라 네 단계(검색→행동→결과해석→갱신) 모두가 분리 불가능하게 얽힌다. 문헌상 동형 함정이 확인된다: (1) actuation을 learning으로 표기 — Reflexion(2303.11366)은 스스로 '가중치를 갱신하지 않고 언어적 피드백으로 강화'한다고 명시하고, ACE/Dynamic Cheatsheet(2510.04618)도 'weights를 바꾸지 않는 context adaptation'으로 자기 분류하는데, 2차 인용에서는 둘 다 'self-improving/learning'으로 뭉뚱그려진다. (2) headroom 소멸 — Supersede(2606.27472)에서 full-context 정확도는 92%로 포화하고 bounded memory는 77%로 떨어지는데, 이는 우리 p1v2 KILL(base retrieval이 이미 6/6)과 정확히 동형: base가 포화하면 개입효과는 정의상 0이고, 포화 태스크에서의 '학습 성공' 보고는 측정 불가능한 claim이다. (3) 순환 평가 — Dietz의 Evaluation Tropes(dietz2025principles) 'Eval Trope 1: Circularity'는 시스템 내부 LLM judge를 공식 평가자로 쓰면 최적화=평가 목표가 동일해져 자기강화된다고 명시; ICLR26 리뷰 사례(teacher가 테스트셋 생성+ judge 겸임 → 성능 부풀림)와 emergentmind의 leakage 사례(F1이 leak 비율에 선형 상승)가 실증 사례다. (4) frozen vs learned 구분 실패 — OpenReview structured-memory 연구(2cbf...)만이 'weight update disable' ablation(uniform edge weight 동결)으로 learned 신용배분의 필요성을 보였는데, 이 절차가 없는 메모리 에이전트 논문 대부분은 frozen-store 개선(순수 actuation)을 ΔW 효과로 보고할 위험이 있다. 즉 증명 어려움의 근본은: 신용배분 대상(어느 레슨이 원인인가)과 신용배분 행위(가중치 갱신)와 신용배분 평가(성능 향상 판정)가 하나의 LLM 루프 안에서 동질 집단(homogeneous)으로 실행된다는 점이다.


**recommendation**: HSWM의 ΔW claim(①)을 게이트화하려면 다음 4-arm sealed 설계를 prereg할 것: (A) no-memory, (B) memory-frozen(레슨 존재·가중치 uniform·결과피드백 차단 — actuation만 측정), (C) memory-learned(결과→신용배분→가중치 갱신), (D) learned+weight-shuffle(학습 후 가중치를 레슨 간 셔플/부호반전 — 인과성 검증). ΔW 성립 조건 = C>B AND D<C(셔플이 frozen 이하로 떨어져야 신용이 가중치에 실재); B>A는 actuation 효과로 별도 보고(이것은 이미 p1v4에서 확보됨). 태스크 선정에 headroom 스크린 의무화: no-memory와 base-retrieval 베이스라인이 모두 [0.2, 0.8] 밴드 안에 있는 항목만 sealed run에 포함, base retrieval ≥0.9 시 해당 태스크셋 kill(p1v2 규칙의 일반화). 순환성 차단 3조: (i) 신용배분의 결과 신호는 반드시 programmatic verifier/환경 ground truth(LLM self-judge 금지), (ii) 평가 judge는 레슨 생성·갱신에 쓰인 모델과 다른 패밀리, (iii) 레슨 스토어에 provenance 태그를 남겨 평가 항목에서 유래한 레슨이 그 항목 검색에 쓰이지 않도록 store-level train/test 분리(Dietz contamination 경로 차단). Kill 조건: learned−frozen Δ의 95% CI가 0 포함, 셔플 테스트 비유의, judge 교체 시 verdict 반전 중 하나라도 해당되면 claim 폐기. claim ②(전이)에는 frozen-B arm을 추가해 B가 스토어에 재기록 불가능하게 봉인.


**alternatives**:
- 대안 해석 1 — actuation-first 포지셔닝: ΔW를 아예 주장하지 않고 HSWM을 'typed actuation 시스템'으로 재정의(claim 축소). 이 경우 B-arm 강화 + 전이 시 read-only export만으로 라인업 완성 가능. 단, 이는 프로그램의 핵심 야심(신경망 유사 학습) 포기이므로 fallback으로만.
- 대안 설계 2 — counterfactual credit assignment 차용: RL의 CCA(Mesnard et al. 2021)처럼 개별 레슨을 one-at-a-time 제거/주입하는 leave-one-lesson-out(LOLO) 절차로 레슨별 한계기여를 측정, 셔플 테스트보다 세분화된 신용 지도 작성. 비용이 크지만 레슨 수가 적을 때(초기 HSWM) 실행 가능.
- 대안 설계 3 — Supersede형 supersession 태스크를 ΔW 전용 벤치로: 사실이 갱신되는 multi-session 시나리오에서 stale 가중치가 유지되는지 갱신되는지를 직접 관측. actuation과 learning을 시간축으로 분리할 수 있어 headroom 문제를 우회함.


**references**:
- https://arxiv.org/abs/2303.11366
- https://arxiv.org/pdf/2510.04618
- https://arxiv.org/abs/2606.27472
- https://www.cs.unh.edu/~dietz/papers/dietz2025principles.pdf
- https://cseweb.ucsd.edu/~jmcauley/reviews/iclr26c.pdf
- https://openreview.net/pdf/2cbf3ea7143fd3d382533081b9d28376c99ba3aa.pdf
- https://www.emergentmind.com/topics/pitfalls-in-llm-security-research
- https://arxiv.org/html/2605.03354v2


**caveats**: Supersede(2606.27472)와 ICLR26 리뷰 인용은 검색 스니펫/초록 수준 확인이며 본문 전체 정독은 못했다(수치는 초록에 명시된 것만 인용). OpenReview structured-memory ablation 논문의 제목·저자를 확정하지 못해 URL로만 식별. '대부분의 메모리 에이전트 논문이 freeze ablation을 생략한다'는 주장은 표본 조사가 아니라 대표 사례 기반 추론이다. Reflexion/ACE가 '학습이 아니다'는 것은 저자들 자신의 명시적 한정이지 반증이 아니며, 2차 커뮤니티 인용에서의 혼동은 체계적 서베이 없이 관찰된 것임.


## a4 :: alternatives [HIGH]

**한 줄**: PoPE식 2-gate(신호→내용)+SHA-deranged placebo store+planted-ground-truth credit testbed+content-addressed store-hash 봉인으로 ΔW claim을 falsifiable하게 닫을 수 있다 — kill 조건 'ΔW=0인데 향상'과 'form≡content 효과' 둘 다 prereg 가능.


**rootCause**: ΔW claim이 증명/반증 어려운 근본 이유는 3중 confound다. (1) 형식-내용 confound(PoPE가 명명): typed lesson store에 ΔW를 적용하면 내용 신호뿐 아니라 프롬프트 형식·토큰 예산·retrieval 분포가 동시에 변해, 성능 향상을 '내용=ΔW'에 귀속할 수 없다 — PoPE(2607.12962)는 frozen 모델에서 prompt 채널과 weight 채널 모두 content-attribution이 확인되지 않음을 preregistered null로 보고했다(8-8 tie, placebo가 수치상 앞섬). (2) 신용의 ground truth 부재: 신경망 weight든 외부 store든 '진짜 기여도' 라벨은 관측 불가라, 자연 상태에서는 credit assignment 정확도를 채점할 수 없다 — COSAC(2604.17693)이 closed-form ground-truth advantage testbed를 만든 이유. (3) self-assessed binary feedback + 자기생성 lesson + persistent retrieval 조합은 confabulated lesson을 store에 기록하는 구조적 취약점(2605.29463) — 즉 ΔW 자체가 오염될 수 있어 'ΔW가 있고 성능도 올랐다'만으로는 인과가 안 닫힌다.


**recommendation**: LakatoTree 호환 최소 sealed 프로토콜 2개를 제안한다. [D1: ΔW 귀속 스크린 — PoPE 2-gate 이식] 고정 retrieval scaffold·매칭 토큰예산 하에 3개 arm: Ct=live typed store(실ΔW 적용), Sf=SHA-deranged placebo store(lesson 수·typed-weight 분포·표면 형식 동일, lesson↔outcome 매핑만 derange = 내용 제거된 ΔW), Fr=no-store 기선(p1v4 no-memory arm 재사용). store는 t0/t1 content-addressed hash로 봉인·장부 기록. 게이트: G_s=net(Ct−Fr)≥τ_s(정확 단측 McNemar, preregistered +k units), G_c=net(Ct−Sf)≥τ_c. Kill 조건: ①성능 향상인데 hash(t0)=hash(t1)이면 'ΔW 없는 향상'→REFUTED(효과는 ΔW 아닌 seed/예산 drift); ②G_s∧¬G_c → 'form not content'→ΔW 내용 claim REFUTED; ③discovery seed 결과는 fresh-seed 재측정 없이 claim 불가, negative screen 시 대규모 spend 금지(gate-as-result). [D2: credit intervention test — planted ground truth] 실제 효과가 조작된 m개 lesson을 심은 합성 testbed(특정 lesson이 특정 task family 정답을 결정)에서 HSWM credit ĉ와 ground truth c*의 MSE/top-k precision 측정, 기준선=uniform·recency·frequency. 여기에 datamodels식 검증 결합: store 부분집합 S로 재실행→perf(S) 선형 datamodel 적합→LDS(예측 vs 실측 LOO 효과 Spearman)가 prereg 미달이면 credit assignment REFUTED. 부가 guard: lesson admission 전 sealed heldout replay 검증 실패 시 write 거부(confabulation 차단). 선행 조건: semantic-weight-metric-contract를 최소 3단계(hash 존재 → typed-weight L1 → embedding 거리)로 확정해야 'ΔW=0' 판정이 가능.


**alternatives**:
- datamodels-over-store 풀버전(Ilyas 2202.00622): 수백 개 랜덤 store 부분집합으로 재실행해 subset→성능 회귀 적합 — 가장 강한 counterfactual attribution이나 비용이 커서 D2의 LDS 부분만 축소 채택 가능
- COSAC식 closed-form advantage testbed(2604.17693): sequential multi-agent bandit에서 해석적 ground-truth advantage로 per-agent MSE 검증 — 미해결 foundation 'multi-agent-transfer-harness'와 합쳐 전이 claim 게이트로 재사용 가능
- Weight Patching 번역(모듈 weight 교체 localization): store를 lesson family 단위로 partition해 특정 파티션만 placebo로 교체하는 store-patching — ΔW 효과의 국소화 층위까지 측정 가능하나 설계 복잡도 상승
- 단순 retrieval-shuffle placebo(기존 B21과 유사, store 레벨): 최소 비용으로 form confound만 통제 — credit 품질 자체는 미측정이라 D1의 cheap pre-screen으로만 가치
- TRAK(2303.14186) 관점: attribution 방법 자체를 counterfactual 예측기로 평가 — HSWM credit 함수를 'LOO 효과 예측기'로 재정의해 방법 간 LDS 비교 벤치마크화


**references**:
- https://arxiv.org/html/2607.12962v1
- https://arxiv.org/abs/2202.00622
- https://proceedings.mlr.press/v162/ilyas22a/ilyas22a.pdf
- https://arxiv.org/pdf/2303.14186
- https://arxiv.org/html/2605.29463v1
- https://arxiv.org/html/2604.17693v2
- https://openreview.net/pdf?id=ZgQ0t3zYTQ


**caveats**: PoPE(2607.12962)는 frozen 0.5–1.5B 코드모델·단일저자 preprint이며 저자 스스로 'equivalence/비열등성 주장 아님, public-tier screen 한정'이라 명시 — null을 일반화 금지, 다만 2-gate+placebo-hierarchy+gate-as-result 장치 자체는 실제 구현·실행됨을 원문에서 확인. Memory confabulation(2605.29463)은 Reflexion 단일 아키텍처 관측(저자가 구조적 일반화를 주장하나 검증은 제한적). Datamodels/TRAK은 gradient-trained 신경망 대상이라 외부 typed store로의 번역은 유추(단 counterfactual 정의 자체는 모델-무관). 2026년 preprint 다수는 peer-review 미완. MemoryAgentBench 등 메모리 벤치마크는 write→query interleaved 평가를 지원하나 credit 정확도 메트릭은 없어 D2의 planted testbed가 별도 필요.
