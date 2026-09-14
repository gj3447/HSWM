# HSWM 추가 증명 — 관계 생성·상관·오염된 피드백·비용·재귀 학습

2026-09-14 · `SECONDARY_AI_BOUNDED_FORMAL_RESULT / INTEGRATED_CLAIM_UNJUDGED`

HSWM의 대상은 여전히 **상태 자체인 거대한 Semantic Weight 하이퍼그래프와, 작은 국소 입력을 받는 내부 LLM 연산자들이 이루는 하나의 AI**다. 이번에는 [이전 성능 증명](HSWM_LITERATURE_TO_PERFORMANCE_PROOF_2026-09-14.md)의 고정 후보·IID·정확한 feedback 가정을 일부 확장한다. 전체 HSWM을 유한 Boolean 모델로 재정의하지 않는다.

개념적 추가는 **실제로 후보를 생성하는 문법, 임의의 공동 오류 분포, 관측 라벨 오염에서 유도한 채택 기준, 재귀적으로 실행하는 관계의 학습 보존**이다. 아래 결과는 정확한 참조 연산자에 대한 정리이며, 실제 pretrained LLM의 신뢰성이나 비용을 측정한 결과가 아니다. 전체 HSWM 범위의 CR-0..7과 FCL-1..8은 미완료로 유지한다.

## 1. 이전 조건에서 무엇을 더 증명했나

| 남았던 문제 | 새로 검증한 결과 | 정확한 범위 |
|---|---|---|
| 기존 의미 후보만 선택 | 입력 primitive들로부터 실제 문법 확장을 실행한다. 깊이 n 이하의 모든 해당 문법 표현식이 생성됨을 구조적 귀납으로 증명한다. 처음에 없는 3항 AND 관계를 네 관측으로 합성한다. | 문법과 변수 3개가 주어진 유한 프로그램 합성. 새 변수·열린 자연어 의미·임의 topology 발견은 아님. |
| IID 국소 오류 가정 | 임의의 공동 질량에서 다수결 이득의 정확한 조건을 증명한다. 상관 때문에 이득·동률·악화가 생기는 구성을 모두 둔다. | 현실 LLM의 공동 오류 분포를 추정하거나 식별한 것은 아님. |
| 피드백이 전부 정확 | 실제 라벨 오염 질량 B에서 점수 오차 경계를 유도하고, 관측 이득이 `2B + 비용`보다 크면 참 점수의 순이득이 남음을 증명한다. | B 자체의 신뢰성은 외부 가정. 임의의 오류 상관은 허용하나, 표본에서 미관측 모집단으로의 일반화는 별도 의무. |
| 비용을 넣으면 이득 불명 | 같은 보상 단위로 표현한 비용과 연산자 불일치량을 이득 조건에 함께 포함한다. 통합 예제는 실제 guard가 양의 debit을 지불하고도 채택함을 계산한다. | 토큰·시간·돈을 측정하거나 단위 변환을 인증한 결과는 아님. |
| 합성 뒤 학습 보존 | 실제 재귀 AND 실행, 전체 공동 후보의 outcome filtering, Step/Learn trace와 누적 오류 경계를 연결한다. XOR 반례로 독립 marginal 재결합이 틀린 후보를 되살림을 증명한다. | 유한 tree와 명시한 결합 연산. 분산 국소 인과 credit, 확률 calibration, 효과적인 압축·확장성, cognition은 미증명. |

## 2. 새 의미 관계의 생성

[HSWMConstructiveRelationSynthesis.lean](../../formal/HSWMConstructiveRelationSynthesis.lean)의 초기 후보는 `x0`, `x1`, `x2`뿐이다. `grow`는 기존 표현식을 보존하고 두 표현식을 AND로 결합한 프로그램을 실제 목록에 추가한다.

```math
G_0=\{x_0,x_1,x_2\},\qquad
G_{n+1}=G_n\cup\{a\land b\mid a,b\in G_n\}.
```

`generated_complete`는 문법 표현식의 깊이가 n 이하이면 실제 `generated n`에 포함된다는 정리다. 단순히 정답 후보가 있다고 가정한 이전 finite learner보다 생성 조건이 구체적이다. 하지만 문법 밖의 XOR, 새로운 관측 변수, 자연어 개념 전체를 포괄하지 않는다. 중복 표현식도 남아 있어 이 생성기는 효율성 보장이 없다.

`synthesize`는 생성 목록과 관측만 읽는다. 입력 `111→true`, `110→false`, `101→false`, `011→false`에서 `x0 AND (x1 AND x2)`를 계산해 얻는다. 이 관계는 각 입력 primitive와 의미적으로 다르며, 합성에 사용하지 않은 `000`도 false로 예측한다. 네 관측은 이 문법을 구분하도록 설계한 정확한 관측이다. 데이터 수집 전략이나 실제 LLM의 발명 능력을 증명한 것은 아니다.

## 3. 독립성이 없어도 판단할 수 있는 이득

[HSWMCorrelatedReliability.lean](../../formal/HSWMCorrelatedReliability.lean)은 세 국소 출력의 correctness bit에 대한 임의의 비음수 공동 질량을 다룬다. C는 첫 연산자의 오답을 다른 둘이 고치는 `(false,true,true)`의 질량, D는 첫 연산자의 정답을 다른 둘이 망치는 `(true,false,false)`의 질량이다.

```math
S_{\mathrm{majority}}+D=S_{\mathrm{first}}+C.
```

따라서 다수결의 엄격한 이득은 정확히 `C > D`와 동치다. 이는 이득을 자동 보장하는 추가 가정이 아니라, **어떤 공동 오류 사건을 측정해야 하는지 보여 주는 필요충분 조건**이다. 실제 출력 규칙이 이상적인 다수결과 다른 사건 질량이 최대 δ이고 추가 비용이 c이면 `C > D + δ + c`에서 순이득이 남는다. δ에 대한 점수 오차는 사건 질량의 합에서 직접 유도한다. 현실의 C, D, δ가 이 조건을 만족하는지는 아직 측정하지 않았다.

## 4. 틀린 라벨이 있을 때의 학습 채택

[HSWMNoisyFeedback.lean](../../formal/HSWMNoisyFeedback.lean)의 관측은 입력·라벨·비음수 질량으로 구성된다. true score와 observed score의 양방향 차이는 실제 잘못된 라벨 질량 이하임을 목록에 대한 귀납으로 증명한다. 오류의 독립성은 필요하지 않다.

```math
|S_{\mathrm{observed}}(f)-S_{\mathrm{true}}(f)|\le B,
\qquad
S_{\mathrm{observed}}(f_{\mathrm{new}})-S_{\mathrm{observed}}(f_{\mathrm{old}})>2B+c
\Rightarrow
S_{\mathrm{true}}(f_{\mathrm{new}})-S_{\mathrm{true}}(f_{\mathrm{old}})>c.
```

실행 함수 `choose`는 truth 함수에 접근하지 않는다. 관측 점수·허용 오염량·debit만으로 채택한다. `choose_nondecreases_true_score`는 그 계산된 선택의 비악화를 보이고, 충분한 참 margin이 있으면 실제로 채택한다는 정리도 있다. 반대로 B를 실제보다 낮게 선언하면 오히려 나쁜 규칙을 채택하는 반례를 보존했다. 이 증명은 self-confidence나 receipt가 라벨의 진실성을 인증한다는 뜻이 아니다.

## 5. 재귀 합성에서 보존해야 하는 것

[HSWMRecursiveLearningComposition.lean](../../formal/HSWMRecursiveLearningComposition.lean)은 leaf에 실행 규칙·불확실성 값·예외 목록을 보존하고, 공동 후보 하나를 완전한 재귀 tree로 저장한다. 임의의 유한 비어 있지 않은 fanout을 binary bracketing으로 표현한다. `flatten`과 별도의 `shape`를 함께 쓰면 원래 tree를 복원한다. **flatten만으로 원형을 복원한다는 정리는 아니다.**

일반 `forward`는 선언된 집계와 flat leaf 출력의 관계를 정의한다. 이에 더해 `recursiveAnd`는 실제로 내부 branch마다 AND를 실행하며, `recursiveAnd_flatten`은 그 결과와 flat 집계의 동치를 귀납으로 증명한다. 학습도 그 실제 재귀 출력으로 전체 후보를 거른다. 생성된 관계 프로그램을 이 tree로 변환해도 실행·학습 filtering·오염 guard 선택이 동일하다는 통합 정리가 있다.

공유 결과가 XOR=true일 때 허용되는 공동 후보는 `(false,true)`, `(true,false)`다. 실제 posterior에서 각 marginal을 추출한 뒤 독립 재결합하면 이미 배제했던 `(false,false)`, `(true,true)`가 다시 생긴다. 그래서 공동 후보를 보존하는 것이 필요하다. 단순한 국소 점수 강화나 child별 독립 posterior는 이 보존을 보장하지 않는다.

`recursive_tree_mistake_bound`는 실제 tree Step을 먼저 실행하고 outcome 뒤 Learn하는 오류 수가, realizability 가정 아래 초기 공동 후보 수 N에 대해 최대 N−1임을 보인다. 불확실성·예외는 **필드와 상관 후보의 보존**이며, 확률 calibration 또는 예외가 행동에 미치는 효과까지 증명하지 않는다. 후보 조합을 전부 보유하므로 계산량은 크게 늘 수 있다.

## 6. 한 구성에서 연결한 결과

[HSWMGeneratedLearningBridge.lean](../../formal/HSWMGeneratedLearningBridge.lean)은 생성한 프로그램을 기존 `NaryRelation`과 `SemanticWeight.fromLlm`에 연결한다. Canonical endpoint를 읽는 관계와 재귀적인 작은 AND 연산의 일치를 증명한다. LLM은 여기서 정확한 참조 연산자로 추상화돼 있다.

참조 세계의 정답은 비상수 함수 `x0 AND x1 AND x2`다. 네 정확한 합성 관측에서 후보를 생성하고, 별도로 선언한 **전체 유한 평가 질량**에서 noisy guard를 실행한다. 평가 목록은 합성 입력 네 개도 포함하므로 독립 validation split이나 fresh test가 아니다. `000`의 질량 2를 정확 라벨 1과 틀린 라벨 1로 나눈 중복 기록을 사용한다. 각 Boolean 입력의 총 질량은 2, 전체는 16이라고 증명했다.

| 양 | 기존 x0 관계 | 생성된 3항 관계 |
|---|---:|---:|
| 참 정답 질량 | 10/16 = 5/8 | 16/16 = 1 |
| 오염된 관측의 정답 질량 | 9/16 | 15/16 |
| 추가 비용 debit | 0 | 1/16 |
| 참 순보상 | 10/16 | 15/16 |

관측 이득 6은 `2 × 오염 허용량 1 + debit 1`보다 커서 실제 guard가 생성된 관계를 채택한다. 참 순보상 이득은 5/16이다. 비용 단위는 정답 1회의 보상을 기준으로 **선언한 모형의 단위**이며 실제 LLM 비용 측정이 아니다.

같은 세계·같은 질량에서 세 primitive 출력의 다수결은 정확 질량 10/16으로 기존과 동률이다. 이 모델에서는 단순 투표 수 증가로 얻지 못한 성능을 생성된 결합 관계가 얻는다. 모든 가능한 기전에 대한 인과 attribution이나 HSWM 고유 우위의 증명은 아니다.

## 7. 문헌 연결과 다음 미폐쇄 조건

- [Solar-Lezama et al., Combinatorial Sketching for Finite Programs, ASPLOS 2006](https://people.eecs.berkeley.edu/~sseshia/pubdir/asplos06-final.pdf)은 명세·탐색 공간을 명시하고 verifier와 함께 유한 프로그램을 구성하는 직접 선행 연구다. 이번 문법은 훨씬 좁고, 해당 논문의 completeness나 효율성을 HSWM에 이전하지 않는다.
- [Angluin·Laird, Learning from Noisy Examples, 1988](https://link.springer.com/article/10.1007/BF00116829)은 독립적인 random classification noise 아래의 학습을 다룬다. 이번 정리는 다른 가정인 유한 adversarial corruption mass를 사용한다. 원 논문의 PAC·표본 복잡도 보장을 구현하거나 인용만으로 획득한 것은 아니다.
- [Fong·Spivak·Tuyéras, Backprop as Functor, v3 / LICS 2019](https://arxiv.org/abs/1711.10455v3)는 명시된 조건에서 parameterized function과 학습 규칙의 합성을 연결한다. 이번 tree 정리는 그 범주론 정리의 재증명이나 일반 LLM gradient 정리가 아니다.
- Self-Consistency, TextGrad, VML, VPP의 정확한 관측·버전·한계는 [이전 조사](HSWM_LITERATURE_TO_PERFORMANCE_PROOF_2026-09-14.md)를 보존한다. [OpenCog Hyperon](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)은 계속 필수 핵심 비교 대상이다. 해당 도구나 표준을 새로 설치·실행하지 않았다.

현재 남는 핵심은 실제 LLM이 이 국소 의미 연산을 어느 오류량으로 실현하는지, 열린 문법에서 유용한 변수를 어떻게 생성하는지, B·δ와 공동 오류 법칙을 독립 자료로 어떻게 보증하는지, 압축·공유 원인이 있는 HSWM-of-HSWMs에서도 비용과 학습을 어떻게 보존하는지다. 수학적 부분 결과로 기존 RED 경로를 지우거나 CR/FCL을 통과 처리하지 않는다.

[검증 명령과 기록](../../_research/semantic_frontier_proof_v1/README.md), [정리·범위 KG](../../ontology/identity/hswm_core/HSWM_SEMANTIC_FRONTIER_PROOF_ONTOLOGY.v1.json), [정리와 미폐쇄 조건 조회](../../ontology/queries/hswm_semantic_frontier_proof_2026-09-14/README.md)에 정확한 source/SHA와 의존 관계를 기록한다.
