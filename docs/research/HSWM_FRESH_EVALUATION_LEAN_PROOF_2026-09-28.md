# 독립 평가에서 canonical graph 선택까지 — Lean4 통계 학습 증명

2026-09-28 · `SECONDARY_AI_BOUNDED_FORMAL_RESULT`

[사용자 요청](../canon/sources/USER_PRIMARY_HSWM_STATISTICAL_LEAN_REQUEST_2026-09-28.txt)에 따라 [직전 문헌 계획](HSWM_LEARNING_COMPOSITION_PROOF_LITERATURE_2026-09-28.md)의 첫 목표 T1 중 하나의 frozen round를 구현했다. **평가 오차가 작다는 결론을 가정하지 않고, 표본의 독립성·유계성·평균 조건에서 동시 오차 상계를 도출한 뒤 비용 포함 후보 선택과 검정력에 연결한다.** 같은 후보들은 후보별 revise wrapper를 통한 기존 canonical graph `Learn`의 successor이며, 점수는 그 상태를 읽는 `Step`의 출력에서 정의한다. 무작위 과거 기록에 조건부인 적응 라운드의 fresh-sampling 정리는 아직 남는다.

대상은 [HSWM 헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 거대한 AI, 하이퍼그래프 신경망 조직, 기본 LLM 계산 단위, Semantic Weight를 통한 작동이다. [그래프가 상태 자체이고 LLM은 국소 연산자](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md)라는 정의를 유지한다. 이번 추가는 통계적 후보 선택의 수학적 연결이며 living harness·world/self model·continuous learner를 별개 시스템으로 만들지 않는다. 실제 LLM 효능과 CR/FCL 상태는 그대로 미완료다.

## 무엇을 도출했는가

후보 수 M, 행 수 n>0, 관측 전에 고정한 candidate graph·baseline·연산자·평가 함수·비용을 둔다. 후보 k의 깨끗한 gain D_i(k)는 [-1,1]에 있고 행끼리 독립이며 기대값이 Δ_k다. **후보끼리는 독립일 필요가 없다.** 같은 task draw를 모든 후보가 공유할 수 있다. iid는 충분하지만, 증명은 독립·공통 평균이라는 더 약한 조건도 허용한다.

반지름 r≥0에 대해 Mathlib의 Hoeffding lemma에서 각 centered row의 sub-Gaussian 성질을 도출하고, 양쪽 꼬리와 유한 후보 union bound를 결합한다.

```math
\Pr\{\exists k:\left|\overline D_k-\Delta_k\right|>r\}
\le 2M\exp(-nr^2/2).
```

M>0, 0<δ<1일 때 아래 반지름을 대입하면 실패 상계가 정확히 δ가 된다는 대수적 보정도 증명했다. 뒤의 채택 타당성과 검정력은 합쳐서 실패 외측도 ≤δ를 만족한다. 관측 과정이 가측이면 실패 확률 ≤δ라는 뜻이다.

```math
r=\sqrt{\frac{2\log(2M/\delta)}{n}}.
```

오염은 별도 경로다. 각 후보에서 **최대 b개 행만 교체되고**, 깨끗한 값과 관측값 모두 [-1,1]이며 나머지 행은 같다는 구체적 `ReplacementWitness`에서 평균 차이 ≤2b/n을 증명한다. Huber 분포 오염과 같은 모형으로 취급하지 않는다. 관측 평균으로 계산하는 하한과 선택은 다음과 같다.

```math
L_k=\widehat\Delta_k-r-2b/n,\qquad
\mathrm{certified}={k:C_k<L_k}.
```

선택기는 인증 집합에서 가장 작은 후보 index를 반환하거나, 집합이 비면 `none`을 반환한다. 선택 시 깨끗한 값이나 Δ를 읽지 않는다. 확률적으로 보장되는 **하나의 같은 사건**에서 아래 두 성질을 함께 얻는다.

```math
\mathrm{selected}=k\ \Longrightarrow\ \Delta_k-C_k>0,
```

```math
\exists k:\Delta_k>C_k+2(r+2b/n)
\ \Longrightarrow\ \mathrm{selected}\ne\mathrm{none}.
```

둘째는 충분한 margin의 후보가 존재할 때 선택기가 비어 있지 않다는 결과다. LLM이 그런 후보를 발견한다거나 특정 후보가 최종 선택된다는 주장은 아니다. 비용은 같은 효용 단위로 선언한다. 생성·평가·실행 비용의 측정·배포 기간 배분은 실제 적용의 의무다.

확률 표현은 Lean에서 `μ.real`을 사용한다. 관측·선택 사건이 가측이면 통상적인 확률이며, 임의의 오염 함수에는 외측도 상계로도 성립한다. 입력의 표본 조건은 실제 환경에서 검증한 결과가 아니라 이 정리의 명시적 전제다.

## 실행되는 그래프와 연결한 부분

[`CanonicalBridge.lean`](../../formal/statistical-learning/HSWMStatisticalLearning/CanonicalBridge.lean)의 `FrozenGraphRound`는 baseline, 하나의 고정 실행 연산자, 과거 trace·outcome, 후보 proposal과 비용을 묶는다. 과거 outcome과 trace의 일치가 필요하고, 각 후보는 기존 [`HSWMLLMSemanticGraph.learn`](../../formal/HSWMLLMSemanticGraph.lean)의 successor다. 정확히는 `withRevision`이 후보별 proposal로 revise 분기를 대체하고 execute 분기를 보존한다. 따라서 모든 proposal을 하나의 실제 LLM이 생성했다는 결과가 아니다. 후보 생성은 새 평가 행을 받기 전에 끝난 매개변수로 둔다.

- `candidate_is_bound_learn`: 후보가 기존 trace/snapshot/serialization 검사와 결속된 Learn 결과다.
- `candidate_keeps_owner_and_roles`, `candidate_keeps_prior_history`: 해당 유한 모형의 owner·roles·extra roles와 이전 relation history를 보존한다.
- `future_step_reads_selected_graph`: 선택한 정확한 graph state를 다음 Step의 serialization이 읽는다.
- `graphGain`과 `expectedGraphGain`: 선언된 payoff·task law 아래 canonical Step의 출력 효용 차이와 그 적분으로 population gain을 정의한다.
- `canonical_graph_selection_failure_bound`, `canonical_graph_selection_failure_le_delta`: 위 같은 graph family와 task draws에 통계 정리를 적용한다. 전체 후보가 동일한 무작위 task를 공유해도 된다.

이는 HSWM의 모든 schema·Permit·권리·causal credit이 닫혔다는 정리가 아니다. 과거 outcome의 필드 일치는 진위나 독립 수집을 인증하지 않는다. 새 평가 자료가 과거 기록과 독립이라는 현실 시간 순서도 고정된 family라는 수학 매개변수만으로 입증되지 않는다.

## 구현·검증 경계

| 파일 | 역할 |
|---|---|
| [Concentration](../../formal/statistical-learning/HSWMStatisticalLearning/Concentration.lean) | bounded rows→Hoeffding→양쪽 꼬리→유한 후보 동시 상계 |
| [Selection](../../formal/statistical-learning/HSWMStatisticalLearning/Selection.lean) | 교체 오염의 계산된 상계, 실제 유한 선택, soundness·power와 반례 |
| [Integration](../../formal/statistical-learning/HSWMStatisticalLearning/Integration.lean) | row 평균을 적분에 결속하고 같은 sample 사건에서 채택·검정력의 실패 상계 도출 |
| [CanonicalBridge](../../formal/statistical-learning/HSWMStatisticalLearning/CanonicalBridge.lean) | 기존 graph Learn/Step과 통계 선택의 결합 |

새 패키지는 `formal/statistical-learning`에 격리했다. Lean 4.32.1, Mathlib commit `520045ab14e26149ee970e2e617ca04b09bde5d6`과 전이 의존성은 [Lake lock](../../formal/statistical-learning/lake-manifest.json), [출처·라이선스](../../formal/statistical-learning/SOURCE_PINS.md)에 고정한다. 기존 parent package와 과거 증명·receipt를 수정하지 않는다.

[TS/Effect 검증기](../../src/hswm/effect-runtime/src/statistical-learning-proof-process.ts)는 새 OLean 디렉터리에서 선언 소스를 다시 컴파일하고 정리별 공리를 검사한다. [검증 기록](../../_research/statistical_learning_proof_v1/lean-verification.v1.json)은 최종 결과를 기록한다. `sorry`, 새 axiom, `native_decide`로 결과를 우회하지 않는다. 표준 Lean 공리와 Mathlib의 compiled imports는 명시된 신뢰 기반이다. dependency source revision과 clean worktree를 확인하지만 cached OLean bytes를 source부터 재빌드·인증하거나 독립 kernel 검증을 수행한 것은 아니다.

2026-09-28 최종 검증은 기존 graph를 포함한 5개 모듈 fresh compile, 새 정리·보조정리 37개(Concentration 10·Selection 9·Integration 7·CanonicalBridge 11)의 개별 공리 검사에 통과했다. 사용 공리는 `propext`, `Quot.sound`, `Classical.choice`뿐이다. package 전체 Lake build, TS check/build, 기존 공리 parser 3개·Markdown 8개·개발 workflow 55개 검사도 통과했다. 이 검사 수는 LLM 성능 지표가 아니다.

선택기는 **정확한 실수 위의 수학 함수**다. 현재 TS runtime에서 동일 수치 판정이 실행된다고 증명한 것이 아니다. 실제 적용에는 보수적 반올림 또는 exact-grid 경계, 입력 결속, 동결된 split, outcome 검증과 deployment law 연결이 남는다. TS/Effect 정본 원칙은 유지한다.

## 반례와 남은 의무

작은 witness는 인증 집합이 실제로 비어 있지 않을 수 있음을 보인다. 또 관측은 +1인데 모형의 clean target은 −1인 상황에서 오염량을 근거 없이 0으로 두면 악화 후보가 선택되는 반례를 보존한다. 그 반례에는 0개 교체의 `ReplacementWitness`가 존재하지 않음도 증명한다. witness의 작은 표본을 높은 신뢰수준의 통계 성능으로 해석하지 않는다.

기존 [미관측 세계 반례](HSWM_INTEGRATED_CLOSED_LOOP_PROOF_2026-09-27.md)는 계속 유효하다. 이번에는 선언한 target distribution의 새 표본이라는 전제가 들어가며, 임의의 모든 세계에 대한 정확성을 주장하지 않는다. [DGX 의미 학습의 무개선 결과](../../results/HSWM_DGX_SEMANTIC_LEARNING_2026-09-20.md)와 [JEV 한계](../../results/HSWM_JEV_PRINCIPLES_2026-09-21.md)도 유지한다.

완료된 것은 한 번의 frozen round에 대해 전제를 명시한 통계 정리와 canonical graph 모형 연결이다. 측도 μ는 무조건부이며 무작위 prior transcript에 조건부인 반복 정리는 아니다. 다음 의무는 실제 LLM 국소 의미 실행, 독립 outcome/오염 상계, 비용, 수정 후보 발견, 현실 split 및 runtime refinement다. 반복 adaptive round의 conditional fresh sampling·오류 예산 배분, 두 셀의 joint credit와 Step/Learn coupling, 재귀적 world/self·lineage·FCL-1..8은 이번 결과에 포함되지 않는다. Hyperon은 [정확한 구현 버전과 성숙도](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)에 따른 필수 핵심 비교 대상으로 남는다.
