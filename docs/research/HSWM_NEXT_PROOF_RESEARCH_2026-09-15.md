# 실제 LLM이 작동하는 HSWM으로 이어지는 다음 증명 연구

2026-09-15 · `SECONDARY_AI_RESEARCH_PLAN / INTEGRATED_CLAIM_UNJUDGED`

**현재 형식 증명은 Lean 4다.** [toolchain](../../formal/lean-toolchain)은 `leanprover/lean4:v4.32.1`이며, [기존 검증 기록](../../_research/semantic_frontier_proof_v1/lean-verification.v1.json)은 실제 LLM refinement와 전체 HSWM을 미증명으로 둔다. 아래 내용은 원문을 확인한 후속 연구 계획이다. 이번에 새 Lean 정리를 검사하거나 실제 모델을 실험했다는 뜻은 아니다.

대상은 [사용자가 정한 상태와 연산자](../canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md), 즉 **거대한 Semantic Weight 하이퍼그래프가 AI 상태 자체이고 LLM이 작은 국소 입력을 받는 내부 신경 연산자인 하나의 AI**다. 같은 상태가 living harness, world/self model, continuous learner 역할을 함께 한다. [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md), [FCL-1..8](HSWM_FRACTAL_SCIENTIFIC_CONNECTIONS_2026-08-28.md), [목표 유지·방법 교체](../canon/HSWM_ADAPTIVE_RESEARCH_STRATEGY_2026-08-30.md)를 보존한다.

개념적 추가는 [제한된 참조 모형 증명](HSWM_SEMANTIC_FRONTIER_PROOFS_2026-09-14.md)을 실제 LLM에 연결하는 **국소 확률 연산·개입에 의한 효과 추정·새 자료에서의 수정 채택·합성 오차**를 하나의 연구 경로로 묶는 것이다. [기존 이론 D2/P1](HSWM_SEMANTIC_WEIGHT_THEORETICAL_FOUNDATIONS_2026-09-14.md)의 확률 커널과 Step/Learn 충분성, [이미 구현된 TS/Effect 의미 실행·revision](HSWM_LLM_SEMANTIC_GRAPH_IMPLEMENTATION_2026-09-14.md)을 재사용한다. 새로운 승인 계층이나 별도 인지 시스템을 만들자는 계획이 아니다.

## 1. 바로 연결할 기존 연구

문헌의 결과, 적용 해석, 앞으로 증명할 명제는 서로 다른 지위다. 다음 표의 적용은 모두 HSWM 측 가설이다. 수치 성능을 HSWM에 이전하지 않는다. 확인한 arXiv 버전이나 학회 출판본을 지정하며, 최신성 자체를 채택 이유로 삼지 않는다.

| 연구와 확인한 원문 | 원문이 제공하는 것 | HSWM에서 쓸 부분과 보장되지 않는 부분 |
|---|---|---|
| **VML**, 2024 최초 공개 / 2025-02-14 v3, TMLR 표기. [원문](https://arxiv.org/html/2406.04344v3) | 자연어 파라미터를 LLM이 실행하고 예측·label로 수정하는 구성과 실험 | 관계의 의미·조건·예외가 실제 실행 파라미터가 되는 직접 선행. 일반 의미 정확성·수렴·인과 학습 정리는 아니다. 기존 HSWM 조사에 이미 포함된 기반이다. |
| **TextGrad**, 2024-06-11 v1. [원문](https://arxiv.org/html/2406.07496v1) | 계산 그래프의 변수에 자연어 피드백을 전달해 수정하는 방법과 실험 | 결과에서 관계 수정 후보로 돌아가는 제안 방법. textual gradient를 실제 미분, 정당한 인과 credit, 단조 개선으로 해석하지 않는다. |
| **GEPA**, 2026-02-14 v2, 최초 공개 2025. [저자 원문 기록](https://arxiv.org/abs/2507.19457v2) | 실행 trajectory를 반성해 prompt를 제안·시험하고 Pareto 후보를 결합하는 실험적 최적화 | scalar reward 외에 의미 있는 실패 내용을 후보 생성에 사용. HSWM의 typed relation rewrite로 옮기는 것은 새 작업. 일반 최적성이나 새 의미의 참을 보장하지 않는다. v2 HTML 접근 실패로 이번 확인 범위는 저자 abstract·버전 기록이며, 세부 알고리즘 정리를 새로 주장하지 않는다. |
| **DreamCoder**, PLDI 2021. [공식 발표](https://pldi21.sigplan.org/details/pldi-2021-papers/55/DreamCoder-Bootstrapping-Inductive-Program-Synthesis-with-Wake-Sleep-Library-Learnin) · [저자 PDF](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf) | 프로그램 합성, 재사용 가능한 library abstraction 학습, 신경 탐색을 교대로 개선 | 고정 AND 후보를 넘어 관계 조합의 문법·라이브러리도 자라게 하는 구성 후보. 주어진 DSL·과제족을 사용하며 관측 변수의 의미 접지와 열린 세계 발견을 해결하지 않는다. |
| **C3: Exact Is Easier**, 2026-05-08 v2. [원문](https://arxiv.org/html/2603.06859v2) | 고정된 완전 history와 continuation 정책 아래 대안 행동을 재실행하고 leave-one-out advantage의 불편성을 유도 | 같은 상태에서 한 결정을 바꿨을 때의 효과를 비교하는 직접 선행. 복원 가능한 text-history 모형과 표본 조건에 한정. 실제 외부 세계의 인과 효과, semantic truth 또는 학습 후 성능 향상까지 증명하지 않는다. 검색 결과의 이전 제목은 현재 v2 제목과 구별한다. |
| **Memory-R2**, 2026-05-20 v1, preprint. [원문](https://arxiv.org/html/2605.21768v1) | 서로 다른 memory write가 만든 상태 차이를 지적하고, 같은 중간 기억에서 local rerollout하는 LoGo-GRPO를 실험 | graph revision 후보들을 동일 predecessor 상태에서 비교할 이유. local 비교와 global 목적을 섞는 방법이며 전체 인과 credit의 불편성 정리가 아니다. text dialogue 밖 실현도 미검증이다. |
| **Doubly Robust Off-policy Value Evaluation**, Jiang–Li, ICML 2016. [출판본](https://proceedings.mlr.press/v48/jiang16.pdf) | 순차 정책 가치 추정의 불편성과 분산 재귀식, safe policy improvement의 사용례 | 행동 확률·지원 범위와 독립 평가 표본이 있을 때 기존 기록을 활용할 방법. §3.2/§4의 자료 분리 조건이 필요하고 긴 horizon의 분산은 남는다. 자유 텍스트 후보의 알려지지 않은 제안 확률을 자신감 점수로 대신할 수 없다. |
| **Time-uniform confidence sequences**, Howard 등, Annals of Statistics 2021 / 확인판 2022-08-06 v9. [원문 §4](https://arxiv.org/html/1810.08240v9) | 정해진 조건 아래 반복 관측·선택적 중단에도 유효한 구간. Theorem 4와 §4.2는 bounded process 및 무작위 처치 효과를 다룸 | 관측 개선량의 통계적 하한을 만들 기반. 후보 mutation, 여러 후보 선택, 오염된 label, 미래 분포 이동까지 자동 보장하지 않는다. |
| **Compositional abstraction error**, Rischel–Weichwald, UAI 2021. [출판본](https://proceedings.mlr.press/v161/rischel21a/rischel21a.pdf) | 유한 개입적 인과모형 사이의 변환과 Jensen–Shannon distance 기반 오차. Proposition 2.12는 합성 오차의 가산 상계를 증명 | child→macro 상태·개입 사상을 정의하고 오차를 추적할 기반. LLM이 유용한 압축을 발견하거나 Learn까지 보존한다는 결과는 아니다. HSWM이 Step·Learn·환경 연결 각각을 구성해야 한다. |
| **OpenCog Hyperon**, 공식 July 2026 백서. [원문](https://hyperon.dev/__l5e/assets-v1/ed61e255-d234-4af2-b22b-da96a4548a4d/HyperonWhitepaper2026.pdf) | 지속 metagraph, 실행 언어·Space API, neural 연결 방향과 구현/실험/연구 상태의 구분 | 필수 아키텍처·실험 비교 대상. §1.9의 성숙도와 §10의 neural 경로를 [기존 고정 소스 감사](HYPERON_2026_DIRECT_PRIOR_DEEP_DIVE_2026-08-20.md)에 연결한다. 전체 설계를 실행 가능한 baseline으로 간주하지 않는다. |

공유 원인을 포함한 확률 의미론은 기존에 조사한 [Fritz의 Markov categories](https://arxiv.org/abs/1908.07021v8)를 재사용할 수 있다. 조건부 독립을 명시하는 언어이며 독립성을 만들어 주는 정리는 아니다. [Backprop as Functor](https://arxiv.org/abs/1711.10455v3)는 지정한 지도 gradient 학습의 합성을 다루므로 임의의 LLM 자연어 revision에 적용할 수 없다.

## 2. 먼저 풀 질문: 작은 국소 입력이 무엇을 보존해야 하는가

관계 의미를 모두 사람이 먼저 발명할 필요는 없다. 사전학습된 LLM은 후보 의미를 제공한다. 그러나 어떤 관측을 읽었고, 어떤 차이를 예측하며, 어떤 결과로 수정되는지는 정의해야 한다. Semantic Weight는 [기존 정의](HSWM_SEMANTIC_WEIGHT_DEFINITION_AND_HYPERGRAPH_2026-09-14.md)의 **역할·문맥 조건부 공동 전이 성향**이다. 관계 설명, 후보의 증거 가중치, 측정한 인과 효과는 서로 다르다.

고정 backend 계약 아래 출력 법칙을 `Kβ(output | localRead)`로 다룬다. 실제 실행에 필요한 cache·session·진행 중 상태가 있으면 operational configuration에 포함하거나 정해진 분포로 주변화한다. 정본 snapshot만으로 자동 Markov라고 가정하지 않는다.

다음 Lean 목표는 이미 증명된 exact read 충돌 반례의 **근사 확장**이다. 같은 read를 가진 두 상태에서 요구되는 출력 법칙의 거리가 D라면, 동일한 국소 연산자가 두 상태 모두에서 오차 ε 이하이려면 D≤2ε여야 한다. metric·출력·허용 문맥을 먼저 고정한다. 이 조건은 가능성의 필요조건이지 유용한 read를 구성했다는 정리가 아니다.

실질적 과제는 read를 작게 유지하면서 누락된 관련 변수에 접근할 수 있는 다단계 국소 읽기 규칙을 만드는 것이다. 불충분하면 추가 읽기·관측 또는 판단 보류가 가능해야 한다. full graph나 숨은 정답을 read에 넣어 조건을 자명하게 만들 수 없다. token·호출 비용도 함께 센다. 선언한 관측·개입으로 구별할 수 없는 세계는 구별 불가능으로 남긴다.

## 3. 동일 상태에서 관계 수정의 기여를 식별한다

C3를 옮길 때 고정할 대상은 graph hash 하나가 아니다. 당시 canonical revision, read-set, 역할, prompt/model 설정, 도구·session 상태, continuation 정책, outcome 평가 규칙이 비교 가능한 실행 법칙을 정해야 한다. 외부의 복원 불가능한 세계 상태는 HSWM이 알고 있다고 가정하지 않는다.

두 평가를 구별한다.

- **복원 가능한 실행에서의 국소 기여:** 완전 history를 맞추고 대안 행동과 continuation을 표집한다. C3의 조건은 같은 history에서 독립적으로 얻은 n≥2 행동, 사전에 정한 rollout 수, frozen continuation law, 자기 표본을 제외한 baseline이다. 불편한 advantage도 표본 변동이 있으며 최적 행동이나 개선을 보장하지 않는다.
- **현실 outcome에서의 revision 효과:** baseline/revision의 처치 단위, 무작위 배정 확률, 상호 간섭, 지연 outcome, 환경 변화와 비용을 선언한다. 실제 무작위 비교가 우선 후보다. 과거 기록의 DR 추정은 그에 필요한 propensities·overlap·자료 분리 조건을 확보했을 때만 후보가 된다.

Memory-R2의 같은 기억 anchor 원리를 따라 변경 후보는 같은 predecessor state에서 분기한다. 정본 relation 제거·복원은 관계 존재의 효과를 묻는 별도 개입으로 유지한다. 그것을 고정 history에서의 한 행동 advantage와 혼동하지 않는다. 기존 RED·반증 대조군도 유지한다.

## 4. 평가 결과로부터 채택을 도출하는 학습 규칙

VML/GEPA/TextGrad의 LLM은 제안 분포를 구성하는 후보이고, 전이가 유익하다고 판정하는 oracle이 아니다. 새 관계나 변수에는 source-grounded 관측 경로와 구별 가능한 예측을 붙인다. 기존 TS/Effect의 canonical revision·outcome 연결을 사용해 다음 실행이 실제로 바뀐 의미를 읽도록 한다.

**다음 증명 대상은 채택 조건의 통계적 타당성이다.** 먼저 한 후보 버전을 고정하고, 생성에 쓰지 않은 평가 자료에서 정해진 과제 분포·효용의 효과 Δ를 추정한다. 필요한 확률 조건과 오염·전이 오차 보정으로 동시 신뢰 하한 L을 구성한다. 같은 효용 단위의 추가 비용 상계 C보다 L이 클 때만 순이득을 주장한다.

```math
\Pr\{\forall t:\ L_t\le\Delta_t\}\ge 1-\alpha,
\qquad L_t>C_t\ \Longrightarrow\ \Delta_t-C_t>0
\quad\text{on the coverage event}.
```

이 식의 마지막 부등식만 Lean으로 옮기면 핵심이 해결되지 않는다. **데이터에서 계산한 L이 실제 효과를 덮는다는 앞부분**을 식별·표본·오염 가정에서 유도해야 한다. 오염량을 임의 상수로 선언하거나 LLM의 자기 확신으로 인증하지 않는다. 새 후보마다 오류 예산을 배정하는 등 여러 비교를 통제하고, 결과를 본 뒤 mutation한 후보는 이전 평가의 보장을 자동 상속하지 않게 한다.

Confidence sequence는 선언된 stream과 estimand의 반복 관측을 다룬다. 과거의 평균 조건부 효과가 양수라는 결과를 미래의 모든 과제에 대한 보장으로 바꿀 수 없다. 배포 분포·정책 변화에는 별도 연결 가정과 검증이 필요하다. 평가자가 오염됐거나 결과가 누락·검열됐을 때도 별도 모형이 필요하다. 데이터 분할만으로 내용 중복이나 평가자 누수가 사라지는 것은 아니다.

‘아무것도 채택하지 않는다’는 규칙은 안전해도 학습을 실현하지 않는다. 따라서 일정한 참 효과 margin과 검증 가능한 관측 조건에서 유한한 표본·비용으로 채택될 수 있는 **검정력·종료 결과**도 같이 요구한다. 유익한 후보를 LLM이 발견할 확률·탐색 효율은 추가 의무다. 이를 개선 가정 하나로 숨기지 않는다.

## 5. 합성은 실행과 다음 학습을 모두 보존해야 한다

기존 exact Step/Learn 요약 기준을 확률적 근사로 확장한다. 하위 상태를 상위 상태로 보내는 사상 q, 허용 개입 사상, 관측 metric과 horizon을 정한다. 하위에서 한 번 실행·학습한 뒤 q로 옮기는 경로와, q로 옮긴 뒤 상위에서 실행·학습하는 경로의 차이를 각각 제한해야 한다.

Rischel–Weichwald의 합성 오차 정리는 이 작업의 직접 선행이다. 그 논문의 Jensen–Shannon distance를 total variation 등 다른 거리로 바꾼다면 합성의 비팽창성·삼각부등식 등 필요한 성질을 다시 연결해야 한다. 단순히 논문의 가산 상계를 새 metric에 인용하지 않는다.

child들의 독립성을 기본값으로 두지 않는다. 공동 오류, 공유 world/context, revision 순서와 경쟁을 보존한 joint transition을 둔다. 예외·불확실성은 저장 필드가 유지되는지에 더해 실제 예측과 Learn에 영향을 주는지 검사한다. q=id 또는 모든 공동 후보의 보관은 보존 증명의 출발점일 수 있지만 작은 read·유용한 압축·확장성을 증명하지 않는다.

## 6. 다음 작업의 순서와 완료 판별선

| 순서 | 산출물과 완료 기준 | 기존 의무 | 실패하면 남길 것 |
|---|---|---|---|
| N1 | 기존 SemanticWeight의 Law를 정규화된 유한 공동 커널로 구체화. 실제 backend/read 계약과 근사 read 충돌 하한, 작은 read 확장 규칙의 조건을 명시 | CR-0/5/7 | 읽기 정보 부족, 실행 상태 누락, 예측·학습의 서로 다른 충분성 반례 |
| N2 | 같은 predecessor에서의 국소 credit 추정과 현실 revision 처치 효과를 별도 정의. 관측·개입 가정에서 적어도 한 식별/추정 정리를 유도 | CR-2/3 | 상태 불일치, 지원 범위 없음, 공유 원인·간섭, 잘못된 원인 강화 |
| N3 | 실제 평가 자료에서 얻는 신뢰 하한과 noisy/cost 채택의 타당성, 충분한 margin에서의 검정력·종료를 함께 증명 | CR-1/2/7 | 아무 수정도 못 하는 학습기, 선택 편향, 평가 누수, 오염·비용 보정 실패 |
| N4 | LLM이 새 관계·관측 변수를 제안하고, 접지·탐색 조건·이력 보존을 가진 revision으로 연결. N3와 동일한 평가 규칙으로 유용성을 시험 | CR-4 | 관측할 수 없는 변수, 반복 문장만 만든 ‘발견’, 비용 폭증 |
| N5 | 같은 구성의 Step와 Learn, 환경·개입을 함께 보존하는 유용한 macro 사상과 합성 오차. 공유 원인·예외가 있는 반례도 통과 | CR-3/5/6 | marginal 재결합 오류, 소거된 예외, 학습 오차 누적, 압축 불가능 |
| N6 | 실제 TS/Effect 경로·고정 모델·독립 outcome에 연결하고 같은 과제·예산의 강한 기준과 비교. 세계 및 자기 구조의 예측·계보 지속성도 검사 | CR-5/7, FCL-1..8 | real-model correspondence, world/self·장기 연속성·scale evidence 부족 |

N1–N3이 첫 핵심 묶음이다. N4의 제안 알고리즘은 함께 연구할 수 있으나 그 성능 판정은 N2–N3의 식별·평가 조건에 의존한다. 하위 단계 실패를 더 큰 그래프의 성적으로 구제하지 않는다. 이 단계들은 기존 CR/FCL의 완료 기준을 바꾸지 않는 실행 계획이다.

기준에는 동일 LLM의 원본 경험/긴 문맥, fixed semantic graph, 의미를 바꾸지 않는 sham revision, matched-budget proposal/ensemble, 손실 없는 tagged incidence 표현, 그리고 실행 가능한 정확한 버전의 Hyperon 구성을 포함한다. 각 비교의 질문은 별도로 정한다. 손실 없는 factor/incidence graph는 하이퍼그래프 의미의 동등 구현 후보이므로 열등한 기준으로 가정할 수 없다. Hyperon의 대응 구현을 확보하지 못한 항목은 미평가로 남긴다.

전체 HSWM의 실현은 계속 미증명이다. 이 계획의 목표는 의미 있는 후보 생성과 outcome 학습, 합성 보존을 **동일한 실제 LLM 확률 동역학**에 연결하는 것이다. 세계·자기 모델, 장기 연속성, 인지적 합성의 기존 의무를 작은 참조 과제로 대체하지 않는다.

## 7. 출처와 KG

[KG snapshot](../../ontology/development/HSWM_NEXT_PROOF_RESEARCH_2026-09-15.v1.json)은 원문 기록, 문헌 확인, HSWM 연결 가설, N1–N6와 기존 이론·CR/FCL을 분리한다. [조회·검증 명령](../../ontology/queries/hswm_next_proof_research_2026-09-15/README.md)은 기존 RDF 1.1 projection·SHACL·SPARQL 도구를 사용한다. 로컬 관계 어휘는 HSWM 어휘이며 외부 표준이 과학적 의미를 인증하지 않는다. KG는 문헌과 계획의 projection이고 runtime learning·causal admission이 아니다. 새 의존성 설치, live KG 게시, 실제 모델 실험은 수행하지 않았다.
