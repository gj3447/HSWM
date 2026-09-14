# 문헌 성능 관측을 HSWM 성능 증명으로 잇는 조건

2026-09-14 · `SECONDARY_AI_RESEARCH_ROUTE / INTEGRATED_CLAIM_UNJUDGED`

이 노트는 LLM 문헌의 **조건부 실험 관측**을 HSWM의 보편 공리나 완성 증명으로 바꾸지 않는다. HSWM은 역할을 가진 n항 관계, semantic text, 근거·예외·revision을 같은 지속 hypergraph에서 읽고 Step 한 뒤, 외부 outcome 뒤에 Learn으로 다음 읽기를 바꾸려는 하나의 token-native LLM-function macro-neural network다. Semantic Weight는 점수 하나가 아니라 역할·문맥 조건부 전이 성향이며, score·인과효과·근거는 분리한다.

## 1. 직접 확인한 문헌 관측과 한계

| 1차 출처·버전 | 정확한 관측 | HSWM에 주는 동기 | 여기서 나오지 않는 결론 |
|---|---|---|---|
| [Self-Consistency, arXiv:2203.11171v4, Table 1·§3.2](https://arxiv.org/html/2203.11171v4) | PaLM-540B의 GSM8K에서 greedy CoT 56.5, 40개 독립 sample의 majority 74.4였다. 본문은 10회 평균과 run당 40 sample을 보고한다. | 같은 역할·입력의 여러 실행 trace를 보존하고, 선언된 동치 answer 위에서 집계하는 후보 mechanism. | 어떤 LLM, 열린 텍스트, 상관된 sample, 같은 token 비용에서 항상 개선한다는 정리. 특히 논문도 고정 answer set 또는 적절한 consistency metric이 필요하다고 제한한다. |
| [TextGrad, arXiv:2406.07496v1, §3.3](https://arxiv.org/html/2406.07496v1) | 36개 training example, GPT-3.5 forward와 GPT-4o feedback 설정에서 Objects는 77.8→91.9, GSM8K는 72.9→81.1이며 후자는 DSPy와 동률로 보고됐다. validation을 사용한다. | natural-language parameter/semantic text를 제안·수정하는 국소 LLM 연산 후보. | feedback이 독립된 세계 outcome이거나, text revision이 임의의 persistent graph에서 안전·유효하다는 결론. |
| [Verbalized Machine Learning, arXiv:2406.04344v3](https://arxiv.org/html/2406.04344v3) | 자연어 모델·parameter를 LLM 호출로 실행하고 언어 feedback으로 갱신하는 실험 프로그램을 제시한다. 실행 간 분산과 문맥 길이 제한도 기록한다. | semantic text를 단순 설명이 아니라 실행되는 후보 parameter로 다루는 방법 후보. | LLM 호출 수 증가 자체와 구조·갱신 효과를 분리했다는 일반 주장, 또는 인과 credit의 식별. |
| [Verbalized Particle Posterior, arXiv:2607.22961v1](https://arxiv.org/html/2607.22961v1) | 여러 자연어 가설을 particle처럼 보유하고 LLM으로 제안·평가·갱신하는 방식을 제시한다. | 경쟁 relation/revision 후보와 불확실성을 지우지 않는 검색·갱신 후보. | 정확한 Bayes posterior. §3.2는 prior·reverse-proposal ratio 생략으로 exact detailed balance가 깨짐을 명시하고, §3.3은 정식 SMC의 incremental weight ratio를 유지하지 않는다고 명시한다. |
| [Large Language Models Cannot Self-Correct Reasoning Yet, arXiv:2310.01798v1](https://arxiv.org/html/2310.01798v1) | 같은 모델의 사후 self-correction이 일관되게 reasoning 오류를 고치지 못한다는 반례적 평가를 보고한다. | Learn은 Step 뒤의 독립적·검증 가능한 outcome과 실패 보존을 요구해야 한다는 경고. | 자체 비평, 다수결, 높은 confidence가 truth certificate라는 결론. |
| [Hyperon 공식 2026 백서](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf) | Atomspace, MeTTa, MORK 및 neural read/write bridge를 하나의 비교 대상군으로 제시한다. | 관계 상태와 국소 신경/언어 연산을 결합하는 직접 선행 비교 대상으로 삼는다. | HSWM의 독창성·동등성·우위. 같은 outcome-bound revision과 fresh 평가 기준으로 비교해야 한다. |

따라서 위 숫자는 해당 모델·prompt·자료분할·집계·호출 예산에서의 성능 관측이다. 서로 다른 논문의 모델, evaluator, token 비용, train/validation/test 분할은 교환 가능하지 않다. 특히 TextGrad의 feedback과 HSWM이 요구하는 외부 outcome은 같은 물건으로 취급하지 않는다.

## 2. 문헌에서 증명 모델로 넘어갈 때 필요한 다리

| 관측에서 동기화되는 mechanism | Lean에서 실제로 보인 제한 결과 | 전이를 위해 새로 측정·가정할 것 |
|---|---|---|
| 복수 trace의 집계 | `HSWMLocalEnsembleGain.lean`은 세 독립 Boolean voter와 `0 < bad < good`이라는 선언된 product law에서 majority의 정확 질량이 single보다 엄격히 큼을 보인다. `good=2`, `bad=1`이면 single은 `18/27`, majority는 `20/27`이다. | 같은 task·answer 동치·prompt·예산, sample의 결합법칙/오류 상관, aggregate 전후 비용과 fresh test utility를 사전에 고정한다. IID product law는 측정된 LLM 이득이 아닌 참조 모형이다. 완전 상관 반례에서는 이득이 사라지고, 비용을 넣으면 정확도 증가가 순효용 증가를 뜻하지 않는다. |
| outcome 뒤 후보 제거 | `HSWMOutcomeLearningGain.lean`은 유한 후보 list에 true hypothesis가 처음부터 있고, 모든 외부 example이 이를 실현하면, Step을 outcome 전에 실행하고 Learn이 오답 후보만 제거하여 mistake 수가 초기 list 길이 `N`에 대해 최대 `N - 1`임을 보인다. | outcome의 출처·측정·시간순서와 truthfulness를 receipt로 결속하고, held-out/fresh 분포에서 재평가한다. duplicate 후보는 bound를 느슨하게 할 수 있다. 거짓/불일치 feedback은 true 후보를 지울 수 있으므로 training loss나 단조 held-out gain 정리가 아니다. |
| LLM이 semantic text를 읽고 수정 | `HSWMSemanticWeightDefinition.lean`의 `SemanticWeight.fromLlm`은 local read, encode, operator를 둔 **추상 reference operator**다. | pretrained LLM이 role text를 의미 있게 해석·교정·calibrate한다는 가설을 실제 provider, 버전, context 범위, failure rate로 검증한다. Lean 선언은 그 능력의 증명이 아니다. |

역할을 가진 n항 relation은 source/recipient/context와 추가 role의 순서를 보존한다. factor/incidence 표현은 이 구조를 binary address로 구현할 수 있지만, 원 참여자들만 clique로 투영하면 relation payload·role·공동 상호작용을 잃을 수 있다. 반대로 다층 binary network가 AND 같은 상호작용을 계산할 수 있으므로, “hypergraph가 반드시 더 강하다”는 보편 불가능성 명제도 쓰지 않는다.

## 3. 같은 graph에서 검증할 최소 실험 계약

1. **사전 등록된 Step.** role-bearing relation의 semantic text, ordered reference, 예외·근거, backend configuration, task/context와 prediction trace를 content-addressed receipt로 남긴다. 이 prediction request에는 미래 outcome을 넣지 않는다.
2. **외부 outcome.** prediction과 trace에 결속하되, caller가 선언한 source는 독립 검증을 뜻하지 않는다고 기록한다. 동일 trace의 replay·stale revision·역할/owner 변조·누락 근거를 거부한다.
3. **Learn과 다음 Step.** outcome 뒤 LLM revision proposal을 검증·CAS하여 같은 durable graph에 적고, reopen한 다음 실행이 바로 그 새 semantic text와 보존된 예외/근거를 읽는지 확인한다. 이 동작은 성능 개선의 증거가 아니라 학습 경로의 실행 증거다.
4. **비교와 판정.** frozen graph, no-revision, sham revision, equal-token multi-call, plain-context 및 Hyperon 비교를 같은 자료분할·budget·metric에서 둔다. primary metric, 비용, 실패/rollback, uncertainty calibration, fresh test를 먼저 정한다.
5. **인과 credit과 합성.** outcome 하나를 모든 relation에 강화하지 않는다. 선언된 개입·공유 원인·joint coupling을 검사한다. 국소 개선이 전체 효용을 해칠 수 있다는 `HSWMCompositionInterference.lean` 반례를 baseline으로 유지한다.

## 4. 같은 그래프 Step/Learn의 구성적 향상 증명

[HSWMSemanticPerformanceBridge.lean](../../formal/HSWMSemanticPerformanceBridge.lean)은 위 두 기전을 **같은 forward와 graph 후보 갱신**에 연결한다. 새로 검증한 3개 모듈의 정리·axiom·컴파일러는 [Lean 검증 기록](../../_research/semantic_performance_proof_v1/lean-verification.v1.json), 문헌·가정·정리의 연결은 [KG](../../ontology/identity/hswm_core/HSWM_SEMANTIC_PERFORMANCE_PROOF_ONTOLOGY.v1.json)에 결속한다.

- `Graph`는 payload와 역할·endpoint를 가진 4항 관계다. 세 국소 연산자는 endpoint의 한 비트만 받고, 수신 연산자는 관계의 의미 payload와 세 출력을 받는다. `jointWeight`는 기존 `SemanticWeight.fromLlm`으로 구성된다. 함수가 실제 pretrained LLM이라는 가정은 없다.
- 상태는 `[first, majority, alwaysTrue]`라는 **사전 선언된 완전한 graph revision 후보들**이다. 예측 `step`은 첫 후보의 `forward`를 실행한다. 사후 `learn`은 같은 `forward`로 외부 outcome과 불일치하는 후보를 제거한다. 정답 함수·향상량은 두 함수의 입력이 아니다.
- 고정 목표가 `true`인 세계에서 입력 `(false, true, true)`를 먼저 예측하면 오답이다. outcome `true` 뒤 갱신은 `[majority, alwaysTrue]`가 되고, 다음 실행은 기존 majority 관계를 선택한다. **새 문장을 생성하거나 topology를 발명한 것은 아니다.**
- `computed_semantic_update_strictly_improves`는 `good > bad > 0`의 선언된 결합법칙 아래 이 계산된 갱신의 전체 입력 정확 질량이 엄격히 증가함을 증명한다. 결과는 선택된 feedback 한 점의 적합도가 아니라 8개 가능한 입력 전체에 대한 정확한 합이다.
- `concrete_accuracy_mass_gain`: `good=2, bad=1`이면 공통 전체 질량은 27이고 정답 질량은 **18 → 20**, 즉 **2/3 → 20/27**이다. 이 참조 모형에서는 임의의 truthful 첫 observation이 성능을 낮추지 않고, 초기 오답을 낸 4가지 observation 모두 성능을 높인다는 것도 전수 증명했다.
- `same_graph_dynamics_at_most_two_mistakes`는 같은 갱신으로 **임의의 truthful outcome 열**에서 누적 오류가 최대 2임을 보인다. 이는 generic `N - 1` 정리와 Step/Learn projection을 연결한 결과다.

직관적으로 단일 정확도가 `p`일 때 독립된 세 Boolean 연산자의 다수결 정확도는 다음과 같다. Lean은 실수 확률 라이브러리 대신 정수 product mass와 공통 분모로 아래 부등식을 검증한다.

```math
A_3(p)=p^3+3p^2(1-p),\qquad A_3(p)-p=p(1-p)(2p-1)>0\quad(1/2<p<1).
```

여기서 `p`는 같은 task 조건의 동일한 개별 법칙이다. 데이터셋 평균 정확도가 1/2보다 높다는 것만으로 이 결합법칙은 성립하지 않는다. 문헌의 여러 reasoning trace는 이진 voter와도 동일하지 않다. 완전 상관 반례는 동일한 정규화된 개별 정확도를 유지하면서 다수결 이득을 없앤다.

이것은 **제한된 모델에서 조건부 향상을 도출하고, 실제 작동하는 유한 구성을 보인 증명**이다. 후보·순서·세계·연산자는 명시적으로 설계했다. 완전한 `alwaysTrue` 후보는 처음부터 존재하므로 최적 후보 발견이나 열린 의미 학습의 증거도 아니다. 실행 가능한 Lean 값은 durable 저장소/CAS 구현과 같지 않다. 일반 outcome sequence의 매회 held-out 단조 향상, 현실 분포의 식별, 비용 대비 우월성, HSWM만의 고유 효과는 증명하지 않았다.

기존 [HSWMFiniteSelection.lean](../../formal/HSWMFiniteSelection.lean)의 오차 경계 아래 안전한 finite 선택과, [HSWMCompositionInterference.lean](../../formal/HSWMCompositionInterference.lean)의 국소 이득 합성 실패 반례를 대체하지 않는다. 이번 개념적 추가는 **이득 자체를 premise로 넣지 않고 결합법칙에서 도출하고, 동일 그래프 revision의 학습 규칙과 연결한 것**이다.

## 5. 아직 닫히지 않은 의무

**전체 HSWM 범위의 CR-0..7은 모두 미완료로 유지한다.** 이번 정리는 CR-0·CR-1에 연결되는 유한 모형의 부분 결과이며, 그 두 의무의 전체 폐쇄도 뜻하지 않는다.

이 노트와 세 새 Lean 모듈은 finite 집계·후보 갱신·오류 제거의 조건부 성질을 보인다. 새 relation·변수·topology의 발견과 접지(CR-4), 현실 outcome에서의 causal efficacy와 credit(CR-2/3), world/self·예외·불확실성을 보존하는 충분한 상태(CR-5), shared coupling과 복합 HSWM의 Step/Learn 보존(CR-6), 실제 LLM과 환경에서 한 구성으로 모두 연결하는 CR-7은 남아 있다. 따라서 FCL-1..8도 미완료이며, 특히 합성 뒤 학습 능력 보존은 중첩 실행만으로 결론나지 않는다.

이 연구 경로의 판정은 `SCIENTIFICALLY_CONNECTED / INTEGRATED_CLAIM_UNJUDGED`로 유지한다. 성공은 위의 같은 graph 실험에서 사전 고정된 비교를 통과해야 하고, 실패는 정확한 mechanism family를 evidence lineage와 함께 퇴역·우회시켜야 한다. 어느 쪽도 HSWM 목표 자체를 축소하거나 전체 HSWM 효능을 선언하는 근거가 되지 않는다.

## 출처

- Wang et al., [*Self-Consistency Improves Chain of Thought Reasoning in Language Models*, arXiv:2203.11171v4](https://arxiv.org/html/2203.11171v4), Table 1, §3.2.
- Yuksekgonul et al., [*TextGrad: Automatic “Differentiation” via Text*, arXiv:2406.07496v1](https://arxiv.org/html/2406.07496v1), §3.3.
- [*Verbalized Machine Learning: Revisiting Machine Learning with Language Models*, arXiv:2406.04344v3](https://arxiv.org/html/2406.04344v3).
- [*Verbalized Particle Posterior: Bayesian Inference over Natural Language Hypotheses*, arXiv:2607.22961v1](https://arxiv.org/html/2607.22961v1).
- Huang et al., [*Large Language Models Cannot Self-Correct Reasoning Yet*, arXiv:2310.01798v1](https://arxiv.org/html/2310.01798v1).
- SingularityNET, [*Hyperon: The Open-Source Infrastructure for Artificial General Intelligence*, 2026](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf).
