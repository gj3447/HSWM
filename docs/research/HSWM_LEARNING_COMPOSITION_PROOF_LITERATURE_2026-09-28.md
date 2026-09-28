# 실제 LLM 학습과 두 셀 합성의 Lean 증명을 위한 추가 문헌

2026-09-28 · `SECONDARY_AI_RESEARCH_SYNTHESIS / PROPOSED_NOT_LEAN_CHECKED`

**먼저 증명할 것은 독립 평가 자료에서 계산한 개선 하한의 타당성이다.** 그다음 실제 LLM과 참조 모형 사이의 오차, 두 셀의 실행·학습 계약 보존을 연결한다. 아래에는 추가 원논문 6편과 구체적인 다음 명제를 정리했다. 이번 작업은 문헌 조사와 증명 설계이며 새 Lean 증명이나 실제 모델 성능 결과가 아니다.

[요청 원문](../canon/sources/USER_PRIMARY_HSWM_PROOF_LITERATURE_REQUEST_2026-09-28.txt)은 `USER_PRIMARY`; 문헌 선택·수식·개발 순서는 AI의 해석이다. 대상은 [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 **LLM을 기본 계산 단위로 하고 하이퍼그래프 Semantic Weight로 작동하는 하나의 거대한 하이퍼그래프 신경망 AI**다. [거대한 그래프 자체가 상태이고 LLM은 작은 국소 입력을 받는 내부 연산자](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md)라는 정의를 유지한다. 같은 evolving graph의 harness·world/self model·continuous learning 역할을 별도 시스템으로 분해하지 않는다. CHU는 이 LLM 기반 HSWM보다 넓은 개념이다.

## 기존 연구에서 추가되는 것

[9월 15일 계획](HSWM_NEXT_PROOF_RESEARCH_2026-09-15.md)은 이미 VML·TextGrad·GEPA·Howard confidence sequences·Rischel causal abstraction을 연결했다. 이를 새 발견으로 반복하지 않는다. 이번 추가는 **후보 집합 전체의 잘못된 채택 확률**, **분포 오염과 유한 표본 교체의 차이**, **실행 오차의 정확한 누적**, **순환 계약의 초기 조건**이다.

[9월 27일 통합 증명](HSWM_INTEGRATED_CLOSED_LOOP_PROOF_2026-09-27.md)의 `training_agreement_is_insufficient_for_universal_improvement`는 유지한다. 같은 학습 기록에 합치하는 두 세계에서 동일한 수정이 반대 평가 결과를 만든다. 더 많은 셀이나 논문 인용으로 이 반례가 사라지지 않는다. 과제 분포·새 관측·구조적 가정 중 무엇으로 두 세계를 구별할지 명시해야 한다.

실제 [DGX 의미 학습 결과](../../results/HSWM_DGX_SEMANTIC_LEARNING_2026-09-20.md)는 해당 구성에서 frozen 155/320, learned 155/320, evidence-only 156/320이었다. 이번 문헌은 이 실패를 뒤집는 증거가 아니다. [JEV 결과](../../results/HSWM_JEV_PRINCIPLES_2026-09-21.md), CR-0..7, FCL-1..8과 기존 RED 경로도 그대로 남는다.

## 가져올 원논문 6편

원문 결과는 `EXTERNAL_PRIMARY_SOURCE_REPORTED`, HSWM 적용은 `SECONDARY_AI_PROPOSED`다. 논문을 통째로 복제하거나 외부 코드를 설치하지 않았다. arXiv는 버전을, 학회 논문은 출판본을 지정한다.

| ID · 원문과 읽은 부분 | 원문이 제공하는 결과 | HSWM 적용과 제한 |
|---|---|---|
| P1 · Angelopoulos 등, **Learn then Test**, [arXiv:2110.01052v5](https://arxiv.org/html/2110.01052v5), 2022-09-29. §1.1, §2.1 Theorem 1, §2.2–2.3 | 각 잘못된 후보에 대한 유효한 p-value와 family-wise error rate(FWER) 제어로 선택된 모든 후보의 위험을 확률적으로 제한한다. 독립 calibration 자료와 유효한 검정이 핵심이다. | 생성한 relation revision을 동결한 뒤 여러 후보를 평가할 때 적용. 선택된 집합 안에서 다시 고르는 것은 허용되지만, 평가 label을 보고 새 후보를 만든 뒤 같은 보장을 물려줄 수는 없다. 유익한 후보의 존재·발견·채택 가능성은 별도다. 기존 저장소의 LTT 단순 언급을 구체적 정리로 연결한다. |
| P2 · Wang–Ramdas, **Huber-Robust Confidence Sequences**, [AISTATS 2023 출판본](https://proceedings.mlr.press/v206/wang23p/wang23p.pdf). §2, Lemma 3, Theorem 1–2, §4.1 | 깨끗한 분포와 관측 분포의 TV 거리 상계, 알려진 모멘트 상계 아래 시간 전체에 유효한 평균 구간을 구성한다. 주 정리는 고정 깨끗한 분포 주변의 오염을 다룬다. Lemma 3 뒤에는 같은 TV 근방 안의 조건부 관측 법칙 확장도 명시한다. | 반복 평가와 오염된 feedback에 연결할 후속 후보. 정해진 표본 중 최대 b개가 교체되는 기존 유한 오염 모형과 동일하지 않다. 오염 상계 자체를 LLM 확신으로 인증할 수 없고, 분포 변화나 수정 후보 변경을 자동 처리하지 않는다. |
| P3 · Lobel–Parr, **An Optimal Tightness Bound for the Simulation Lemma**, RLC 2024 / [arXiv:2406.16249v2](https://arxiv.org/html/2406.16249v2), 2024-10-25. §3.2–3.3, Appendix B | 동일 상태·행동 공간과 동일 정책을 두 MDP에서 비교하고, uniform 전이 L1 오차·보상 오차에서 가치 오차를 제한한다. overlap 확률을 직접 추적해 누적 상계를 개선한다. | 실제 LLM 실행과 참조 셀의 차이를 성능 단위로 환산할 후보. baseline과 revision 각각에 model-to-real bound를 적용해야 한다. baseline 정책과 revision 정책이 같다고 가정하는 정리가 아니다. 오차상계만으로 개선이 생기지는 않는다. |
| P4 · Haesaert–Soudjani–Abate, **Verification of General MDPs by Approximate Similarity Relations and Policy Refinement**, SIAM JCO 2017 [저자 원문](https://www.cs.ox.ac.uk/people/alessandro.abate/publications/HSA17.pdf). Definition 9, Theorem 3 | 출력 거리, 상태 관계, 초기·전이 coupling과 policy interface를 갖춘 approximate simulation으로 유한 horizon 명세 확률을 이전한다. | 서로 다른 micro/macro 상태 공간과 국소 read를 연결할 이론. 출력 오차 ε와 관계 이탈 확률 δ는 다른 양이다. 실제 coupling·read 충분성·Learn 보존을 따로 구성해야 하며, 분포의 주변값만 맞춰 공동 법칙을 대신할 수 없다. |
| P5 · Kim–Arcak–Seshia, **A Small Gain Theorem for Parametric Assume-Guarantee Contracts**, HSCC 2017 [저자 원문](https://people.eecs.berkeley.edu/~sseshia/pubdir/hscc17-gain.pdf). Definition 2, §4.1 Theorem 1–2 | 각 셀의 조건부 계약, 상대 guarantee가 자기 feedback assumption을 충족하는 연결, 외부 조건과 초기 feedback 조건에서 합성 계약을 유도한다. limit 결과에는 추가 metric·연속성·극한 조건이 필요하다. | 두 HSWM 셀의 Step/Learn과 feedback을 합성할 출발점. A가 B를 가정하고 B가 A를 가정한다는 순환만으로 보장을 만들 수 없다. 계약 보존은 학습 이득·상위 인지·인과 credit의 증명이 아니다. |
| P6 · **Generalizing Experience for Language Agents with Hierarchical MetaFlows**, [NeurIPS 2025 출판본](https://proceedings.neurips.cc/paper_files/paper/2025/file/5c882988ce5fac487974ee4f415b96a9-Paper-Conference.pdf). §3.1–3.3, §4, checklist theory 항목 | 경험 workflow를 계층적으로 결합·검색한다. 정적 code/tool 단계와 동적 LLM 단계가 mutable context를 공유하며, 생성기는 SFT와 GRPO로 학습한다. AppWorld·WorkBench에서 실험하고 잘못된 계층 node 선택의 손실도 보고한다. | 재사용할 typed local cell과 합성 후보 생성의 실험 비교군. 논문은 이론 정리가 없다고 명시한다. 파라미터 학습된 생성기의 성능을 고정 LLM의 Semantic Weight revision 효과로 이전할 수 없다. code 도입·실행·HSWM 재현은 아직 하지 않았다. |

P1 HTML의 자동 생성 날짜와 arXiv submission 날짜를 혼동하지 않는다. 확인 버전은 v5다. P4/P5는 저자 호스팅 출판 원문을 읽었으며, 외부 페이지의 영구 불변성을 주장하지 않는다. HF CLI 1.29.0은 P1 발견 메타데이터에만 사용했고 정리는 위 원문에서 확인했다.

추가로 검토한 [High Confidence Policy Improvement, ICML 2015](https://proceedings.mlr.press/v37/thomas15.pdf)는 정책 성능 하한을 이용한 개선 선택의 선행이다. 과거 trajectory를 재사용하는 off-policy 경로에는 행동 확률·support 등 추가 조건이 필요하므로 첫 증명은 새 paired evaluation으로 시작한다. [Conformal Risk Control](https://arxiv.org/abs/2208.02814)은 임의 relation rewrite의 기본 해법으로 채택하지 않는다. loss의 단조성·교환가능성 아래 기대 위험을 제어하는 결과와, 선택된 수정의 고확률 순이득은 서로 다르다.

## 첫 Lean 목표: 계산한 경계에서 학습 채택까지

아래는 P1의 다중 비교 원리를 **Hoeffding 부등식 + 유한 오염 보정**으로 구체화한 자체 유도안이다. P1/P2 논문의 정리를 그대로 옮긴 결과도, 이미 Lean으로 확인한 결과도 아니다.

후보 생성에 사용한 과거 기록 F를 고정한다. F를 조건으로 baseline과 M≥1개의 후보 graph revision, 모델·prompt·read 규칙, 평가 함수, n≥1, 0<δ<1, 비용 상계 C_k≥0, 오염 개수 상계 b를 평가 전에 고정한다. 후보 간 독립은 필요하지 않다. 대신 **각 후보의 깨끗한 평가 행은 F를 조건으로 iid**이고, 실제 배포에서 주장할 같은 과제 분포의 gain을 측정해야 한다.

과제 하나의 [0,1] 효용 차이를 D_i(k)∈[-1,1], 기대 차이를 Δ_k로 둔다. 복원 가능한 과제에서 baseline/revision을 같은 선행 상태로 실행하거나, 별도로 증명한 무작위 실험 추정량을 쓴다. 이 정의만으로 현실 처치 효과가 식별되지는 않는다. LLM seed와 외부 session을 포함한 실행 난수의 행 간 표집 조건도 필요하다.

관측된 차이와 깨끗한 차이는 후보별 최대 b개 행에서만 다르고 둘 다 [-1,1] 안에 있다고 하자. 이때 b는 증명 안에서는 replacement witness로 주고, 현실에서는 독립 검증 근거가 있어야 한다. 근거 없이 주입한 숫자는 조건부 분석만 만든다.

```math
r=\sqrt{\frac{2\log(2M/\delta)}{n}},\qquad
c=\frac{2b}{n},\qquad
L_k=\widehat\Delta_k-r-c.
```

목표는 각 고정 후보의 깨끗한 평균에 Hoeffding을 적용하고, 두 꼬리와 M개 후보의 union bound, 교체 행의 결정적 오차를 결합해 다음을 **표본 모형에서 도출**하는 것이다.

```math
\Pr\left\{\forall k:\left|\widehat\Delta_k-\Delta_k\right|\le r+c\right\}
\ge 1-\delta.
```

이 사건 안에서는 아래 두 결론이 함께 성립한다.

```math
L_k>C_k\ \Longrightarrow\ \Delta_k-C_k>0,
\qquad
\Delta_k>C_k+2(r+c)\ \Longrightarrow\ L_k>C_k.
```

첫째는 잘못된 채택 제어, 둘째는 충분한 참 margin이 있는 후보가 인증 집합에 들어갈 **검정력**이다. 최종 선택은 인증된 후보 중 하나이므로 특정 후보가 최종 선택된다고까지 주장하지 않는다. 후보 생성기가 그런 후보를 만들 확률·비용은 별도 의무다. 이미 [HSWMFiniteSelection](../../formal/HSWMFiniteSelection.lean)은 uniform error를 가정한 결정적 선택을 다룬다. 다음 증명은 그 가정을 새 자료에서 유도해야 한다. `LCBValid`를 전제로 다시 붙이는 것만으로 완료하지 않는다.

비용은 효용과 같은 단위여야 한다. 후보 생성·검증·graph read/write·실행 비용을 어떤 배포 horizon에 배분하는지 명시한다. latency·token·성공률을 변환 규칙 없이 더하지 않는다. 유한한 검정력은 저렴한 학습이나 동등 비용 우위를 보장하지 않는다.

반복 revision의 round j≥1에는 과거 전체를 조건으로 새 평가 자료와 δ_j=δ/[j(j+1)] 같은 총합 δ 이하의 오류 예산을 쓴다. 이는 **계속되는 잘못된 채택의 확률 제어안**이며 미래 분포 변화나 무한 인지 합성의 보장이 아니다. 평가를 보고 mutation한 후보가 예전 자료를 재사용하면 이 증명을 다시 적용할 수 없다.

## 두 셀에서 재귀로 가는 연결

P3를 적용할 동일 정책의 두 모델에는 [0,1] 보상, 0≤γ<1, 전이 L1 오차 ε_T∈[0,2], 보상 오차 ε_R∈[0,1]을 사용한다. 논문 §3.3의 상계는 다음과 같다. TV=ε_T/2라는 정규화를 보존한다.

```math
B(\epsilon_R,\epsilon_T,\gamma)=
\frac{1}{1-\gamma}-\frac{1-\epsilon_R}{1-\gamma(1-\epsilon_T/2)}.
```

기계 증명은 우선 Appendix B의 **유한 horizon** overlap 재귀로 시작하는 편이 적합하다. 각 j∈{0,1}에서 abstract/real 쌍은 같은 상태·행동 공간, 같은 정책 π_j, 같은 초기 상태 또는 초기 분포, 같은 할인율을 사용하고 양쪽 보상을 [0,1]로 정규화한다. baseline과 candidate 각각에서 이렇게 얻은 가치 오차가 B_0, B_1 이하이면, 삼각부등식으로 아래 전이 명제를 얻는다. π_0와 π_1이 서로 같을 필요는 없다. abstract/real 사이에 행동 공간이나 정책 구현이 다르면 먼저 P4의 interface/refinement로 연결해야 한다.

```math
\Delta_{\mathrm{real}}\ge
\Delta_{\mathrm{abstract}}-B_0-B_1.
```

이는 제안된 HSWM 연결이며, 실제 LLM 전이·보상 오차의 uniform 상계를 확보해야 적용할 수 있다. 출력이 큰 자연어 공간이면 직접 검증하기 어려워 task readout/coupling의 범위부터 정한다. 이미 실제 실행에서 Δ를 직접 평가했다면 같은 실행 오차를 다시 차감하지 않는다.

상태 공간이 다르면 P4처럼 상태 관계·typed port/interface·joint coupling을 둔다. 초기 coupling이 관계 밖에 둘 확률이 최대 δ_0이고, 두 실행의 joint history에서 지금까지 관계가 유지됐을 때 다음 transition coupling의 조건부 실패 확률이 최대 δ이면, N회 전이 동안 관계 유지 확률의 목표는 `(1−δ_0)(1−δ)^N`이다. P4의 초기·전이 공통 δ에서는 `(1−δ)^(N+1)`과 연결된다. 이는 독립 실패를 가정한 곱이 아니라 **이전까지 관계가 유지된 조건에서의 보장**을 순차 적용하는 방식이다. Step뿐 아니라 outcome을 받은 Learn 뒤에도 같은 종류의 관계를 다시 구성해야 한다.

두 셀은 공유 world/context와 공동 오류를 가진 joint state 위에서 비교한다. P5의 계약을 역할·문맥·예외·권한·outcome/credit·revision 이력에 연결하고, 상대의 Learn이 내 입력 가정을 깨뜨리지 않는지 검사한다. 서로의 계약을 가정하는 순환만 남기지 않고 시작 조건을 실제 구성한다. 전체 목적의 개선은 여전히 별도 비교가 필요하며 국소 점수 두 개를 단순히 합하지 않는다.

재귀 오차에 `E_(d+1)≤ρ E_d+ε`, 0≤ρ<1이 **실제 Step/Learn 합성에서 유도된 경우에만** 유한 깊이 상계 `E_d≤ρ^d E_0+ε(1−ρ^d)/(1−ρ)`를 사용할 수 있다. 이 점화식은 P5 정리의 문자 그대로의 결론이 아닌 추가 specialization이다. 분기 트리에서는 모든 child의 영향 계수 합과 결합 손실을 반영해야 한다. 각 edge만 수축적이라고 전체가 수축하는 것은 아니다. ρ≥1, 공유 원인 소거, 충돌하는 revision은 보존할 반례다. bounded error도 FCL-8의 cognition-bearing 합성을 증명하지 않는다.

## 구현으로 연결할 최소 작업

[공식 Mathlib 문서](https://leanprover-community.github.io/mathlib4_docs/Mathlib/Probability/Moments/SubGaussian.html)에서 `HasSubgaussianMGF.measure_sum_range_ge_le_of_iIndepFun`와 `hasSubgaussianMGF_of_mem_Icc_of_integral_eq_zero`를 확인했다. 확률 부등식부터 전부 새로 만들 필요는 없다. 다만 현재 `formal/lakefile.toml`에는 Mathlib 의존성이 없고, 이번에 설치·호환성 확인·컴파일은 하지 않았다. 적용 시 Lean 4.32.1과 맞는 Mathlib commit·license·Lake lock을 먼저 고정한다. live 문서의 API 존재를 현 checkout의 import 성공으로 보고하지 않는다.

| 순서 | 제안 산출물 · 완료 조건 | 기존 의무와 실패 조건 |
|---|---|---|
| T1 | 유한 후보·paired outcome 분포에서 계산한 r+c가 동시에 유효함을 증명하고 비용 포함 채택·검정력까지 연결 | CR-1/2/7. clean distribution과 b의 근거 부재, calibration 재사용을 별도 반례로 유지 |
| T2 | 실제 TS/Effect 경로의 canonical graph→local read→LLM→outcome→revision→다음 read에 T1의 frozen 후보·표본·비용 계약 연결 | CR-0/1/2/7. [기존 lifecycle selection](../../src/hswm/effect-runtime/src/semantic-lifecycle-selection.ts)은 자동 commit 경로와 통계 정리가 연결됐다는 증거가 아님 |
| T3 | 유한 확률 커널의 initial/step/learn coupling, bounded-return 오차와 strict margin 전이 | CR-5/7. 가상의 정확한 LLM을 정의해서 실제 모델 오차를 없애지 않음 |
| T4 | 같은 두 셀 구성에서 초기 feedback 조건과 상호 계약·joint outcome 학습을 보존. 전체 목적을 직접 비교 | CR-3/6, FCL-2/4. marginal 독립 재결합, 이중 credit, 서로의 가정 파괴를 반례로 검사 |
| T5 | 유한 깊이로 T4 반복, 누적 오차·오류 확률·비용을 함께 추적하고 같은 구성의 world/self·lineage 의무로 확장 | CR-4/5/6/7, FCL-1..8. 다른 toy witness들의 합집합으로 전체 성공을 선언하지 않음 |

실제 구현의 정본은 계속 **TypeScript/Effect**다. 통계 입력·후보 선택은 pure immutable 함수로, 모델 호출·outcome 수집·저장은 typed Effect service로 유지한다. 확률 증명의 실수 경계를 TS 부동소수점 값으로 내릴 때는 보수적 반올림/오차 상계와 refinement가 필요하다. source hash는 split 독립성·label 진위·인과성을 증명하지 않는다.

P6는 T4의 후보 구성 비교군으로만 둔다. baseline에는 같은 LLM의 frozen graph, evidence-only, semantic-preserving sham revision, flat/plain workflow 및 동등 정보의 tagged incidence 표현을 포함한다. [Hyperon 직접 선행 감사](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)의 정확한 구현 버전도 필수 핵심 비교 대상으로 유지한다. [고정 README](https://github.com/trueagi-io/hyperon-experimental/blob/3f76dc460da6961f57f69f6c3e550c59c74ada83/README.md)의 interpreter를 백서 전체 neural 구성의 완성품으로 취급하지 않는다. 비교 대상으로 정한 사실과 backend 채택은 다르다.

이 작업의 [KG snapshot](../../ontology/development/HSWM_LEARNING_COMPOSITION_PROOF_LITERATURE_2026-09-28.v1.json)은 논문·이전 반례·제안 목표를 출처별로 연결한다. RDF projection/SHACL의 구조 검증은 논문의 참, Lean 증명 또는 HSWM 효능을 판정하지 않는다. 연구 결과를 새로 얻은 작업이 아니므로 F1 결과 로그와 content-addressed 연구 성과 receipt는 추가하지 않는다.
