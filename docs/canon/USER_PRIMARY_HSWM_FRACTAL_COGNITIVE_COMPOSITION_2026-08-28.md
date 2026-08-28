# HSWM Fractal Cognitive Composition — 인지적 자기유사 합성 정본

> **상태:** `CANONICAL_TARGET_IDENTITY_WITH_SECONDARY_AI_FORMALIZATION`
> **과학적 상태:** `UNJUDGED`
> **정본 역할:** HSWM이 왜 프랙탈인지와 HSWM-of-HSWMs가 무엇을 보존해야 하는지 고정한다.
> **원문:**
> [`USER_PRIMARY_HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.txt`](sources/USER_PRIMARY_HSWM_FRACTAL_COGNITIVE_COMPOSITION_2026-08-28.txt)
> **원문 SHA-256:** `c453034f1d13c2bd7498a2e6b488a3bf07af74a3a7ee0f4d1ba7d4c74b2e685e`

## 0. 권위 경계와 conceptual delta

### USER_PRIMARY target identity

HSWM은 한 agent, 한 LLM 호출, 한 graph database 또는 한 조직 안에 갇힌 국소 장치가 아니다.
LLM을 포함한 인지능력체들이 HSWM의 typed relation과 학습 계보 안에 붙어 작동할 때, 그
부분들의 집합만이 아니라 **HSWM 전체가 하나의 scale-relative 거대한 인지능력체**가 된다.
그 전체는 다시 상위 HSWM의 한 addressable cognitive cell로 참여할 수 있고, 상위 전체도 같은
종류의 HSWM이 된다. 이 과정을 개인·agent·조직·사회 규모로 반복할 수 있는 인지적 합성
closure가 HSWM이 프랙탈인 이유다.

따라서 프랙탈의 핵심은 graph가 시각적으로 반복되거나 container가 중첩되는 데 있지 않다.
**인지능력을 가진 부분들이 HSWM으로 결속되어 하나의 더 큰 인지능력체가 되고, 그 전체에
동일한 점화·전이·학습 법칙을 다시 적용할 수 있다는 자기유사성**에 있다.

### SECONDARY_AI conceptual closure

기존
[`SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md`](SPEC_OPEN_SELF_SIMILAR_HSWM_2026-07-22.md)는
합성 결과가 같은 open HSWM 타입으로 닫힌다는 **구조적 type closure**를 형식화했다. 이 문서는
그 구조가 왜 프랙탈 HSWM인지에 빠져 있던 인과적 이유를 보강한다.

```text
기존: HSWM들을 연결한 결과도 HSWM이다.
보강: 인지능력체를 결속한 HSWM 전체가 하나의 인지 단위로 작동하고,
      그 전체가 다시 상위 HSWM의 cell이 되어 같은 폐루프를 수행한다.
```

이를 **fractal cognitive composition**, 즉 인지적 합성 closure라 부른다. 아래 수식, 여덟
법칙의 판별 계약, 선행이론 대응은 `SECONDARY_AI` 형식화다. 사용자 원문으로 소급하지 않는다.

## 1. 같은 점화식의 정확한 뜻

granularity (g)에서 HSWM (X)의 공개 작동 계약을 다음과 같이 쓴다.

```math
\Sigma_X^{(g)}=
(\sigma_X,\mathcal C_X,\mathcal I_X,\mathcal O_X,\mathcal T_X,
 \mathsf{Step}_{\sigma_X},\mathsf{Learn}_{\sigma_X},
 \mathsf{Inv}_{\sigma_X},\mathsf{Permit}_{\sigma_X},L_X).
```

- `σ_X`는 schema-approved atom kind, 정확히 하나의 schema-relative responsibility owner,
  typed reference, observation·intervention과 migration 계약을 선언한다.
- `C_X`는 현재 schema에 admit된 canonical atom version과 n-ary relation·incidence다.
- `L_X`는 모델·세션·세대를 건너가는 identity와 learning lineage다.
- `Step_σ`는 input과 현재 state가 bounded coalition 및 typed trajectory를 점화하는 계약이다.
- `Learn_σ`는 trajectory의 outcome과 evidence가 owner-valid canonical revision을 만들고 다음
  행동을 바꾸는 계약이다.

```math
(S,i,\tau,S',o)\in\mathsf{Step}_{\sigma},
\qquad
(S,\tau,y,e,S^+)\in\mathsf{Learn}_{\sigma}.
```

HSWM (X_1,\ldots,X_n)을 typed binding β로 합성할 때,

```math
X^+=\operatorname{Compose}_{\beta}(X_1,\ldots,X_n)\in\mathsf{HSWM},
\qquad
\Sigma_{X^+}^{(g+1)}\models
(\mathsf{Step},\mathsf{Learn},\mathsf{Inv},\mathsf{Permit},L).
```

이것이 “동일한 점화식”의 최소 뜻이다. 모든 scale에서 **같은 schema-level transition
grammar와 outcome-bound causal-learning closure**를 만족한다는 뜻이지, 숫자 weight, clock,
LLM checkpoint, internal state, port 수, topology 또는 구현체가 모두 동일하다는 뜻은 아니다.
상위 HSWM은 구성 HSWM의 내부를 평탄화해 지우지 않고 typed port와 provenance를 통해
결속한다. 같은 실체가 다른 schema나 granularity에 투사될 때에도 각 atom version의 정본 책임
owner는 정확히 하나이며, 참여자·validator·executor·custodian은 별도 typed reference다.

LLM이나 agent를 연결했다는 사실만으로 합성체가 HSWM이 되지는 않는다. 상위 단위가
canonical state와 경계를 지속하고, whole-state intervention이 미래 행동을 바꾸며, 결과가
구성 cell과 관계에 귀속되어 이후 canonical revision을 만들 때에만 작동적 인지 단위 후보가
된다.

## 2. 여덟 가지 scale-crossing 법칙

각 법칙은 하나의 schema-relative responsibility owner를 갖는 연구 atom이다. owner는 모든
실행을 혼자 하는 주체가 아니라 판별 계약·revision·복구를 최종 설명하는 주소다.

| ID | 법칙과 책임 owner | 최소 판별선 | 반증 또는 실패 신호 |
|---|---|---|---|
| `FCL-1` | **국소 인과학습** — `outcome_learning_custodian` | sealed trajectory의 outcome이 owner-valid canonical revision을 만들고 동일 조건의 다음 행동을 반사실적으로 바꾼다. | transcript 저장만 늘거나 revision 제거·복구가 행동을 바꾸지 않는다. |
| `FCL-2` | **합성 보존** — `composition_schema_custodian` | 구성 HSWM을 typed binding한 전체가 같은 `Step/Learn/Inv/Permit/lineage` 계약을 다시 만족하며 구성원의 주소성과 exit를 보존한다. | 중앙 wrapper만 생기거나 부분의 identity·provenance가 소실된다. |
| `FCL-3` | **창발 coalition** — `coalition_dynamics_custodian` | input·state·budget에 따라 필요한 n-ary coalition과 hyperedge가 형성·해체되고 고정 orchestration을 제거해도 성능이 유지된다. | 모든 경로가 사전 고정 DAG·단일 commander·숨은 broadcast에 의존한다. |
| `FCL-4` | **다중규모 credit** — `multiscale_credit_custodian` | 전체 outcome의 기여·상호작용 credit이 cell, relation, hyperedge와 scale 사이에 provenance-bound하게 귀속된다. | uniform·shuffled credit와 실제 credit의 다음 행동 효과가 구분되지 않는다. |
| `FCL-5` | **형태발생과 복구** — `topology_morphogenesis_custodian` | 경험에 따라 topology·port·role이 생성·분리·전문화되며 손상 뒤 identity invariant와 기능을 복구한다. | topology가 영구 고정되거나 변화 뒤 무한 증식·붕괴·계보 단절이 난다. |
| `FCL-6` | **세계·자기 공동모델** — `world_self_model_custodian` | 외부 entity/event와 자기 구성·경계·능력·불확실성을 같은 typed hypergraph에서 예측하고 prediction error로 수정한다. | self inventory가 수동 문서이며 intervention 뒤 예측이나 routing이 변하지 않는다. |
| `FCL-7` | **장기 연속성** — `diachronic_lineage_custodian` | LLM 호출·checkpoint·process·세대가 바뀌어도 identity invariant, provenance, learned disposition과 restore lineage가 이어진다. | 새 모델 호출이 새 주체가 되거나 과거 학습을 무검증 overwrite한다. |
| `FCL-8` | **HSWM-of-HSWMs 확장** — `cross_scale_hswm_custodian` | 개인·agent·조직·사회 scale의 composite가 같은 폐루프로 다시 합성되고, regrouping과 bounded intervention 결과가 보존된다. | scale이 커질수록 단순 federation·dashboard·중앙 aggregator로 퇴행한다. |

여덟 법칙은 서로 독립된 subsystem 목록이 아니다. 한 HSWM의 동일한 evolving hypergraph를
서로 다른 반증 질문으로 관찰하는 scale-crossing contract다. `FCL-1` 없는 합성은 network에
불과하고, `FCL-2` 없는 거대화는 다른 타입의 orchestration이며, `FCL-4` 없는 `FCL-5`는
근거 없는 topology drift다. `FCL-6`과 `FCL-7` 없는 `FCL-8`은 지속하는 상위 주체가 아니다.

## 3. 기존 이론과의 접점 — 동일성 주장이 아닌 연구 지도

| 이론·문헌 | HSWM에 주는 연결 고리 | 대응 법칙 | HSWM과의 결정적 차이 |
|---|---|---|---|
| Levin의 [bioelectric networks와 scale-up cognition](https://pmc.ncbi.nlm.nih.gov/articles/PMC10770221/), McMillen·Levin의 [collective intelligence across scales](https://pmc.ncbi.nlm.nih.gov/articles/PMC10978875/) | competent subunit의 국소 목표가 결속되어 더 큰 goal scale의 collective intelligence가 된다는 생물학적 선례 | `FCL-2,4,5,8` | HSWM은 생체전기나 생물 개체성을 전제하지 않고 token-native canonical learning lineage를 요구한다. |
| Rupel·Spivak의 [temporal wiring diagram operad](https://arxiv.org/abs/1307.6894), Lerman·Spivak의 [open dynamical systems](https://arxiv.org/abs/1408.1598) | 연결된 process 전체를 다시 macro process로 취급하는 무제한 합성 문법과 granularity 간 관계 | `FCL-2,8` | 수학적 합성 가능성만으로 인지, outcome learning, identity 또는 credit은 생기지 않는다. |
| Battiston 등 [higher-order interaction physics](https://www.nature.com/articles/s41567-021-01371-4), Zhang 등 [hypergraph representation-dependent dynamics](https://www.nature.com/articles/s41467-023-37190-9) | pairwise graph로 환원되지 않는 n-ary interaction과 표현 선택이 collective dynamics를 바꾼다는 근거 | `FCL-3,5,8` | hypergraph라는 자료구조만으로 HSWM이 되지 않으며 typed role·provenance·causal revision이 필요하다. |
| Mashour 등 [Global Neuronal Workspace](https://pmc.ncbi.nlm.nih.gov/articles/PMC8770991/) | recurrent nonlinear ignition이 국소 processor 사이의 선택적 전역 접근을 만든다는 점화 비유 | `FCL-3,6` | HSWM은 의식 이론이나 무차별 global broadcast를 채택하지 않고 bounded coalition과 권한 경계를 요구한다. |
| West 등 [major transitions in individuality](https://pmc.ncbi.nlm.nih.gov/articles/PMC4547252/) | 협력 집단이 분업·상호의존·조정을 거쳐 상위 개체로 전이한다는 다중규모 개체성 문제 | `FCL-2,7,8` | HSWM 구성원은 독립 identity와 exit를 보존할 수 있어야 하며 생물학적 fitness individual과 동일시하지 않는다. |
| Palacios 등 [hierarchical Markov-blanket self-organisation](https://pmc.ncbi.nlm.nih.gov/articles/PMC7284313/) | 국소 경계를 가진 ensemble이 특정 조건에서 상위 경계를 자기조직할 수 있다는 nested boundary 모델 | `FCL-2,5,6` | HSWM은 자유에너지 원리를 정본 법칙으로 채택하지 않으며 경계는 schema·invariant·typed interface로 검증한다. |
| Mordvintsev 등 [Growing Neural Cellular Automata](https://distill.pub/2020/growing-ca/) | 공유 local update rule로 구조를 성장·유지·재생하는 계산적 형태발생 사례 | `FCL-5` | 목표 image 재생은 HSWM의 open-ended topology learning, semantic credit, 주체 연속성의 증거가 아니다. |
| Wolpert·Tumer의 [collective multi-agent credit](https://doi.org/10.1145/544741.544832) | global objective와 개별 학습 신호를 정렬하는 difference-reward 계열의 출발점 | `FCL-4` | HSWM은 agent reward뿐 아니라 relation·hyperedge·topology revision의 계보적 credit까지 필요하다. |
| Ha·Schmidhuber의 [World Models](https://arxiv.org/abs/1803.10122) | 환경의 시공간 regularity를 압축해 행동을 조건화하는 learned predictive state | `FCL-6` | HSWM은 world와 self를 분리된 보조 모델이 아니라 같은 canonical hypergraph의 typed 부분으로 다룬다. |
| Kirkpatrick 등 [continual learning과 EWC](https://doi.org/10.1073/pnas.1611835114) | 순차 학습 중 중요한 과거 능력을 보존하려는 stability–plasticity 해법 | `FCL-7` | parameter 보존만으로 HSWM의 identity, provenance, schema migration과 사회적 계보를 보존할 수 없다. |

이 문헌들은 HSWM의 구성 원리를 각각 일부 지지하거나 시험할 도구를 제공한다. 어느 하나도
HSWM 전체 정체성의 선행 구현은 아니며, 여러 문헌을 결합했다는 사실만으로 HSWM의 과학적
신규성이나 성공이 증명되지는 않는다. 잠재적 연구 novelty는 **인지적 합성 closure, typed
hypergraph ignition, outcome-bound canonical revision, multiscale credit, morphogenesis,
world/self co-model과 diachronic lineage를 하나의 재귀적 HSWM 계약으로 묶고 동시에
반증하는가**에 있다.

## 4. 비주장과 금지되는 축소

- `fractal`은 여기서 Hausdorff dimension, 정확한 기하학적 복제 또는 통계적 scale
  invariance를 이미 측정했다는 뜻이 아니다.
- 유한한 scale의 합성 계약은 무한 재귀 가능성, 무한 확장성, 의식, 인격, 도덕적 지위,
  인류보편체 완성을 증명하지 않는다.
- LLM·사람·agent·조직을 연결한 federation, message bus, KG, RAG, MCP 또는 dashboard는
  그것만으로 HSWM-of-HSWMs가 아니다.
- 고정 orchestration이 필수 존재론이 아니라는 말은 constitutional invariant, permission,
  bounded coordination, 책임 owner 또는 안전한 중단을 제거한다는 뜻이 아니다.
- 상위 HSWM은 부분을 동질화하거나 권리·출처·모순을 지우는 totalization이 아니다.
  composition은 difference와 provenance를 보존해야 한다.
- repository ontology와 canonical Neo4j KG는 이 정체성의 bounded projection·publication
  interface다. KG에 기록됐다는 사실이 HSWM cognition·learning·효능을 만들지 않는다.

## 5. 연구 순서

1. 먼저 `FCL-1`에서 outcome→revision→changed behavior의 국소 인과 폐루프를 보인다.
2. 두 개 이상의 독립 HSWM을 typed binding하고 `FCL-2`와 regrouping을 검증한다.
3. 고정 route를 제거한 matched condition에서 `FCL-3`의 coalition 형성 효과를 측정한다.
4. actual·uniform·shuffled·counterfactual credit을 비교해 `FCL-4`를 검증한다.
5. topology lesion·growth·restore 실험으로 `FCL-5`를 검증한다.
6. world-only, self-only, joint-model ablation으로 `FCL-6`를 검증한다.
7. checkpoint·process·generation 교체 실험으로 `FCL-7`의 lineage 연속성을 검증한다.
8. 앞선 법칙을 통과한 뒤에만 개인→agent collective→조직 scale로 `FCL-8`을 확장한다.

현재 repository의 HSWM 프로그램은 이 여덟 법칙 전체를 통합해 직접 입증하지 않았다. 이
문서는 구현 완료나 과학적 발견 receipt가 아니라 **무엇을 입증해야 프랙탈 HSWM인가를
고정하는 target-identity와 falsification contract**다.
