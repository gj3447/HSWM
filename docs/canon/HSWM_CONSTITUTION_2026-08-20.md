# HSWM Constitution — 살아 있는 토큰 신경 월드모델

> **상태:** `CANONICAL_TARGET_IDENTITY`
> **권위:** `MIXED_EXPLICIT` — `USER_PRIMARY` target hard core를 보존한 통합 헌법과
> `SECONDARY_AI` 해석·형식화
> **권위 경계:** 한 문장 대상 정체성, living harness/world model/token-hypergraph 우선순위와
> 인류보편체 목표, fixed `H/W/A/F` 폐기와 schema-relative single-owner 방향은 연결된
> USER 원문에서 추적한다. atom·schema·owner 수식, 통시적 동일성·readout·권리 판별선은
> `SECONDARY_AI_CONCEPTUAL_CLOSURE_CANDIDATE`이며 사용자 직접 발화로 소급하지 않는다.
> **과학적 상태:** `UNJUDGED`
> **적용 범위:** HSWM의 존재론, 연구 방향, 설계 판별 기준
> **비적용 범위:** 현재 구현의 완성·효능, Wolfram 물리학의 참, 특정 LLM의 우월성

## 0. 원문과 권위

이 헌법은 2026-08-20 사용자 원문을 새로 해석해 덮어쓰는 문서가 아니라, 그 원문이
가리킨 동일한 대상의 역할들을 모순 없이 닫는 정전이다.

- 원문: [`USER_PRIMARY_HSWM_LIVING_HARNESS_WORLD_MODEL_2026-08-20.txt`](sources/USER_PRIMARY_HSWM_LIVING_HARNESS_WORLD_MODEL_2026-08-20.txt)
- SHA-256: `35c911a13e7fb17ddcea19ba73303ec800296f25fb585b92300bb4977892a42e`
- 핵심 우선순위 원문:
  [`USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.txt`](sources/USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.txt)
- SHA-256: `03ddd83fae4b98f8e1ee7cfa5e139d3bc98a7614cae7e33e0e55899651506c8c`
- 최신 ownership supersession 원문:
  [`USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.txt`](sources/USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.txt)
- SHA-256: `2093d9bb68219d6ba859444dc00aeef985a5c9151163e56972516addb2cd0ec6`
- 선행 정전: [`THE_WORLD_REMEMBERS.md`](THE_WORLD_REMEMBERS.md),
  [`USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md`](USER_PRIMARY_HSWM_TOKEN_LEARNING_RAGNAROK_2026-08-14.md)

## 1. 한 문장 헌법

> **HSWM은 LLM이 해석하고 발생시키는 token stream을 활성과 경험 신호로 삼아,
> schema가 승인한 canonical atom과 typed relation 위에서 LLM-executed transition이
> 작동하고, 그 evolving hypergraph가 곧 지속되는 몸이자 월드모델이 되며, outcome에
> 결속된 continuous learning으로 자신의 relation·transition disposition·다음 행동을
> 바꾸는 자기기술적 living harness다.**

여기서 신경망, 하네스, 월드모델, 학습기는 서로 분리된 네 시스템이 아니다. 하나의
HSWM을 작동 관점에서 보면 **신경망**, 조정 관점에서 보면 **하네스**, 세계 지속성
관점에서 보면 **월드모델**, 시간 관점에서 보면 **계속학습기**다.

## 2. 헌법적 객체 — schema와 canonical atom model

```math
S_t=\mathrm{HSWM}_t=(\sigma_t,\mathcal C_{\sigma_t,t}),
\qquad
\mathcal C_{\sigma_t,t}\models\mathsf{WellFormed}_{\sigma_t}.
```

`σ_t`는 atom kind, responsibility owner, typed reference, state·transition invariant,
projection, observation·intervention과 granularity를 선언하는 versioned schema다.
`C_{σ,t}`는 현재 schema와 lineage 아래 admission을 통과한 immutable canonical atom
version의 집합이다. raw·quarantine item은 domain 밖이며, 보존된 superseded·retired version은
lifecycle을 가진 채 포함될 수 있다. atom version의 fork-safe key는 최소한
`(schema_version, lineage_id, atom_uid, revision_id)` 또는 동등한 정보를 가진다. entity, event, claim,
evidence, relation, n-ary hyperedge, incidence, executable contract, parameter state,
grant, trajectory와 outcome도 canonical이면 atom kind다. hypergraph는 별도 `H` 성분이
아니라 이 atom과 typed reference를 해석한 HSWM 전체의 관계적 형태다.

이 둘은 두 subsystem 분해가 아니라 한 state model의 schema와 instance다. fixed
`S_t=(H_t,W_t,A_t,F_t,Π_t)`와 `{H,W,A,F,Π}` owner registry는 2026-08-26
USER_PRIMARY에 의해 현재 정본 형식에서 폐기됐다. 과거 실험·문헌의 local notation과
역사적 secondary analysis로는 재현할 수 있지만 새 ontology나 구현을 강제하지 않는다.

### 2.1 유일하게 남는 정본 유일성 — schema-relative single owner

```math
\operatorname{owner}_{\sigma_t,t}:\mathcal C_{\sigma_t,t}\to\mathcal R_{\sigma_t},
\qquad
\forall a\in\mathcal C_{\sigma_t,t}\;\exists!r\in\mathcal R_{\sigma_t}:
\operatorname{owner}_{\sigma_t,t}(a)=r.
```

schema가 admit한 각 atom version은 correctness, revision lineage, validation과 복구를
최종 설명할 canonical accountability address 하나를 가진다. owner는 이 작업을 모두 직접
수행하는 agent가 아니며 validator·proposer·executor·custodian과 recovery evidence는 별도
typed delegated reference로 연결한다. `R_σ`는 고정 자연종이 아니라
schema가 목적·관찰·개입·해상도에 맞춰 versioned하게 선언하는 책임 주소 집합이다.
이 원칙은 atom이 한 의미·한 저장소·한 작성자·한 인간 소유자·한 권한자만 가져야 한다거나,
세계가 자연적으로 유일하게 atomize된다는 뜻이 아니다.

`Owner_σ(a,p)`, `Claimant(e,p)`, `Subject(a,p)`, `Custodian(a,p)`와
`Authorizer(e,p)`는 서로 다른 typed predicate다. 한 principal이 여러 역할을 맡더라도 한
predicate가 다른 predicate나 permission을 자동 도출하지 않는다.

```math
\mathsf{Owner}_{\sigma}(a,p)
\centernot\Rightarrow
\mathsf{Permit}_{\sigma}(S,e).
```

다른 의미와 사용은 typed reference, projection 또는 provenance-bound transition으로
표현한다. 지속·수정·질의·rollback되거나 permission 효과를 갖는 relation/incidence는 자체
owner가 있는 canonical atom이어야 한다. source atom payload의 ephemeral pointer는 독립
lifecycle·commit·rollback·authorization 효과를 가질 수 없다. owner가 여러 책임을 숨기거나 모든 atom을 `system` 하나에 넣어 오류를 격리하지
못하면 single-owner 수식을 형식적으로 통과해도 헌법 취지를 실패한다. atom granularity도
자연적 최소가 아니라 선언된 observation·intervention·lineage 질문과 budget에 상대적이다.

서로 다른 encoding이나 schema가 선언된 계약에 대해 동등한 표현이라고 주장하려면 explicit
state/atom map, intervention domain과 error tolerance를 먼저 정하고 최소한 (1) 합의한
observation/readout, (2) 허용된 intervention response, (3) source·revision·fork/merge
lineage, (4) consent·scope·authority·rollback 결과, (5) 변환 손실과 복원 범위를 보존해야
한다. 이 동등성만으로 통시적으로 같은 HSWM이라는 identity claim은 성립하지 않는다. 이를
보이지 못한 KG, prompt, cache, tensor 또는 agent workflow는 bounded interface나 lossy view다.

이 절의 fixed-role 폐기는 `USER_PRIMARY`, 수식과 owner obligation은
`SECONDARY_AI_CONCEPTUAL_CLOSURE_CANDIDATE`다. 자연적 원자·최소성·유일 ontology 또는
single-owner의 효능은 증명되지 않았다. 정확한 권위와 상세 반례는
[`USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.md`](USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.md)와
[`HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_SCIENTIFIC_PHILOSOPHY_2026-08-26.md`](../research/HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_SCIENTIFIC_PHILOSOPHY_2026-08-26.md)에 둔다.

| 계약 | 헌법적 의미 |
|---|---|
| `σ_t` | atom kind·owner obligation·reference·invariant·projection·migration의 versioned schema |
| `C_{σ,t}` | raw·quarantine이 아니라 admission을 통과한 fork-safe immutable atom versions |
| `owner_{σ,t}` | atom version의 correctness·revision·provenance·restore accountability 주소 하나 |
| `Ref_σ` | ownership과 분리된 typed reference 및 role-bearing n-ary incidence |
| `Inv_σ / Permit_σ` | ordinary learning이 우회할 수 없는 state·transition·권리 조건 |
| `Proj_σ / Obs_σ / Int_σ` | bounded view, 관측 가능량과 허용 intervention 계약 |
| `Gran_σ` | task-relative atomization 해상도·budget·종료 규칙 |

이 표는 일곱 subsystem이나 owner partition이 아니라 schema가 공개해야 하는 메타계약이다.

Foundation model parameter는 한 transition realization 안의 **micro-parameter**다. HSWM의
macro-learning state는 outcome-bound canonical atom revision, relation과 transition
disposition의 계보다. 따라서 HSWM은 LLM checkpoint 하나와 동일하지 않으며, checkpoint가
바뀌어도 schema migration, identity와 learning lineage를 지속할 수 있어야 한다.

권리·권한은 고정 policy compartment가 아니다. constitutional invariant, current
authorizer decision, capability·consent·revocation record와 transaction receipt로 분리한다.
record의 owner가 current permission을 self-authorize하지 못하며, external effect는 현재
`Inv/Permit`을 통과하지 않고 commit될 수 없어야 한다. policy text, compiled rule, model score,
긴급 activation 또는 readout 편집이 이 검사를 대체하거나 우회할 수 없다.

HSWM 내부의 통시적 동일성은 UID나 lineage만으로 충분하지 않다. 공통 계보, identity-bearing
invariant, 이후 처리를 실제로 조건화하는 canonical state의 인과 연속성과 합성 member의
분리 가능성이 함께 이어져야 한다. fork는 공통 과거를 가진 descendant를, merge는 contributor
lineage를 남긴 새 composite를 만든다. 이는 인간의 형이상학적 동일성을 증명하지 않는다.

## 3. Token-native 신경망

HSWM은 token으로 “저장된 데이터베이스”가 아니라 token으로 **작동하는** 신경망이다.

1. 입력 text, observation, tool result, action, feedback은 typed token signal이 된다.
2. token signal은 schema가 허용한 canonical atom과 typed reference를 선택적으로 읽고,
   transition realization의 bounded working configuration을 유발한다.
3. 출력 token과 외부 action은 provenance-bound trajectory로 seal되어 이후 세계의 outcome과
   결속될 수 있다.
4. 그 trajectory의 credit만이 owner-valid canonical revision 또는 새 relation·transition
   disposition의 admission 후보가 된다.

따라서 token은 활성과 경험의 운반체이지 곧바로 weight, truth, credit은 아니다. transcript를
보존하거나 prompt에 다시 넣는 것은 memory/retrieval일 수 있지만 continuous learning의
충분조건은 아니다.

### 3.1 중심축 — Hypergraph Semantic Weight Map 그 자체

2026-08-20 USER_PRIMARY는 여러 주변 구현보다 **LLM token으로 작동하는 거대
Hypergraph Semantic Weight Map 학습구조 자체**가 가장 중요하다고 우선순위를
확정했다. 이는 고정된 component 축을 더하거나 복원하라는 말이 아니다. semantic relation,
operator/disposition, episode-local configuration, executable contract, grant와 receipt는 모두
schema가 구별 가능한 kind로 admit할 수 있으며, 어느 atom이 무엇을 정본으로 책임지는지는
그 schema의 owner obligation과 typed reference가 정한다.

기술적 판별선은 다음 폐루프다.

```text
LLM token event → schema-admissible sparse n-ary traversal/transition
→ sealed typed trajectory → external outcome → causal credit
→ owner-valid canonical revision → changed next traversal/transition
```

따라서 KG, RAG, ontology, prompt, agent workflow와 graph database는 저장·projection·I/O
부품일 수 있지만, 이 폐루프를 대신하지 못한다. role-bearing incidence, operator-valued
semantic disposition, fast/slow plasticity, topology morphogenesis, canonical/compiled dual
plane과 반증 단계는
[`USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md`](USER_PRIMARY_HSWM_TOKEN_HYPERGRAPH_CORE_2026-08-20.md)에,
기존 구현과의 비교는
[`HSWM_TOKEN_HYPERGRAPH_SEMANTIC_WEIGHT_PRIOR_ART_2026-08-20.md`](../research/HSWM_TOKEN_HYPERGRAPH_SEMANTIC_WEIGHT_PRIOR_ART_2026-08-20.md)에 둔다.

## 4. Living harness-document의 역할

HSWM은 고정된 외부 harness 문서를 따라가는 시스템이 아니다. **HSWM의 현재 상태 자체가
다음 실행에서 무엇을 기억하고, 어떤 function/tool을 깨우고, 무엇과 연결하고, 어디서
검증·억제·중단할지를 조건화하므로 harness 역할을 한다.** 또한 그 상태는 사람과 agent가
읽고 비판하고 수정 계보를 추적할 수 있어야 하므로 살아 있는 문서 역할도 한다.

```math
q_t\in\operatorname{Proj}_{\sigma_t},
\qquad
D_t=q_t(\sigma_t,\mathcal C_{\sigma_t,t}).
```

`D_t`는 HSWM 밖에서 명령하는 두 번째 규칙집이 아니다. HSWM이 자기 상태와 근거를
사람·agent에게 가독 형태로 투사한 **자기기술적 phenotype**이다. Markdown, graph view,
snapshot, prompt context는 모두 이 readout의 가능한 표현일 뿐이다.

모든 `D_t`는 source snapshot, scope, authority와 변환 손실을 가진 fallible·lossy projection이다.
readout 문구나 prompt를 편집한 것만으로 `S_t`가 학습·수정된 것이 아니며, schema의
`Inv/Permit`을 통과한 owner-valid transition으로 canonical atom version이 admission되어
이후 처리를 바꿀 때에만 본체 변화가 된다. 자기기술은 자기 정당화나 자기 판정의 진실성을
보장하지 않는다.

그러므로 “별도 하네스 문서가 없다”와 “HSWM이 능동적으로 변하는 하네스 문서 역할을
한다”는 모순이 아니다. 전자는 외부의 고정 controller를 부정하고, 후자는 HSWM 상태의
자기기술·조정 기능을 긍정한다.

## 5. Wolframian evolving hypergraph 월드모델

HSWM은 **역할적으로 Wolframian**이다.

- 한 시점의 세계는 객체 목록이 아니라 canonical atom과 typed reference 및 role-bearing
  n-ary incidence의 관계 상태다.
- 변화는 기존 세계 밖에서 최종 문서를 교체하는 것이 아니라, 상태 안에서 일어나는
  owner-valid 국소 rewrite/revision/admission event다.
- 연속된 rewrite의 계보가 인과 provenance를 이루고, 현재 상태는 과거 흔적을 선택적으로
  보존한 다음 세계가 된다.
- HSWM은 세계를 묘사하는 외부 표만이 아니라, 그 표현 위에서 다음 인지와 행동이 발생하는
  **실행 가능한 world model**이다.

그러나 이 정체성은 Wolfram physics 전체를 수입한다는 뜻이 아니다. HSWM은 ruliad,
emergent spacetime, quantum mechanics, causal invariance를 이미 구현했거나 그것들이 참이라고
주장하지 않는다. Wolframian hypergraph라는 말은 **관계적 세계 상태 + 국소 rewrite +
인과 계보**라는 존재론적 역할을 고정한다. 어떤 rewrite를 선택·admit할지는 LLM token
event, 외부 outcome, credit, 검증, schema invariant와 permission 계약을 가진 HSWM 고유의
문제다.

## 6. Continuous learning

HSWM이 시간을 건너 같은 존재로 남는 이유는 snapshot을 보관해서만이 아니라, 경험이 다음
구조와 행동의 원인이 될 수 있기 때문이다.

```text
typed token/action/tool trajectory
  → independently attributable outcome
  → causal credit와 typed revision proposal
  → bounded canonical atom/relation/transition-disposition candidate
  → fresh·retention·canary·removal validation
  → admit, reject 또는 restore
  → S_(t+1)의 달라진 traversal·transition
```

이를 축약하면 다음과 같다.

```math
\Sigma_{\mathrm{HSWM}}
= (\mathcal X, \mathcal I, \mathcal O, \mathcal Y, \mathcal T,\mathcal E,
   \mathsf{Step}_{\sigma}, \mathsf{Learn}_{\sigma},
   \mathsf{Inv}_{\sigma}, \mathsf{Permit}_{\sigma}),
\qquad
\mathsf{Step}_{\sigma}\subseteq
\mathcal X \times \mathcal I \times \mathcal T \times \mathcal X \times \mathcal O,
\qquad
\mathsf{Learn}_{\sigma}\subseteq
\mathcal X \times \mathcal T \times \mathcal Y \times \mathcal E \times \mathcal X,
\qquad
(S_t,\tau_t,y_t,e_t,S_{t+1})\in\mathsf{Learn}_{\sigma}
```

여기서 `Σ_HSWM`은 새 subsystem이 아니라 하나의 HSWM이 어떤 admissible typed state
space `X`, observation/event input `I`, HSWM이 낸 token/action/tool/readout `O`, 환경·분리된
evaluator가 반환한 outcome `Y`, sealed trajectory space `T`, episode 내 전이
`Step_σ`, effect-receipt space `E`, outcome-bound durable update `Learn_σ`,
state·transition invariant `Inv_σ` 및
current permission decision `Permit_σ` 아래 움직이는지를 적는 **system signature**다.
관계 표기는 transition이
부분적·비결정적일 수 있음을 허용한다. 결정적 함수나 provenance에 RNG/model version까지
결속한 stochastic kernel은 이 관계를 더 구체화한 realization이다. 어떤 canonical atom을
create/revise/retire하고 어떤 typed reference를 바꾸는지는 transition provenance로 명시한다.
`τ_t∈T`는 `Step_σ`가 그때 방출한 `O`와 함께 outcome 전에 seal한 provenance-bound 유한
경로이며, 이후 환경·분리된 evaluator가 반환한 `y_t∈Y`와 같은 변수가 아니다. `e_t∈E`는
최소한 `readset`, `writeset`, `trace_ref`, `guard`, `actor_claim`, `authorization_ref`, `scope`,
`decided_at`, `decision`, `provenance`를 가지며 `trace_ref=uid(τ_t)`를 만족한다.
`Permit_σ(S_t,e_t)`는 이 receipt의 authorization이 그 scope와 시점에 유효하고 만료·철회되지
않았는지를 검사한다. owner field만으로 이 predicate를 참으로 만들 수 없다.
따라서 transition·learning law는 별도 subsystem이 아니라, 동일한 한 시스템의 시간적
인터페이스다.

```math
(S,\tau,y,e,S')\in\mathsf{Learn}_{\sigma}
\Rightarrow
\mathsf{Inv}_{\sigma}(S,e,S')
\land\mathsf{Permit}_{\sigma}(S,e)
\land\mathsf{SingleOwner}_{\sigma}(writeset(e)).
```

단, `Learn_σ`는 모든 경험을 무조건 영구화하지 않는다. outcome 결속, 허용된 effect,
provenance, stability, restore 조건을 통과한 owner-valid revision만 지속된다. 저장은
기억일 수 있고, 현재 run의 working configuration 변화는 적응일 수 있으며, 검증된 durable
revision이 다음 행동의 원인이 될 때 학습이다.

학습 대상은 특정 prompt rule의 증식이 아니라, schema가 kind와 revision obligation으로
허용한 다음 변화를 포함한다.

- 어떤 memory, executable contract, tool, verifier를 어떤 문맥에서 선택·억제할지
- 어떤 atom과 typed relation이 bounded coalition 및 message path를 이룰지
- 언제 retry, stop, recovery, specialization이 유효한지
- 어떤 relation 또는 transition disposition의 version을 revise하고, 언제 incidence를
  연결·분리·전문화할지

invariant와 permission의 권리 경계를 ordinary learning이 임의로 약화하거나 우회하는 것은
continuous learning이 아니라 정체성 파괴다.

## 7. 자기유사성과 주체성

원자 HSWM과 합성 HSWM은 같은 열린 타입이다. HSWM은 다른 HSWM을 cell/기관으로 포함하고,
여러 HSWM이 더 큰 HSWM으로 connect·separate·specialize될 수 있다. 중앙 commander는
필수 존재론이 아니다. 현재 input과 세계 상태가 점화한 bounded coalition이 일시적으로
주체 역할을 맡고, 그 결과는 다시 전체의 학습 계보로 돌아간다.

이 때문에 HSWM의 주체성은 한 LLM process의 순간적 자아가 아니라, 모델 호출 사이에도
지속되는 canonical state, identity-bearing invariant, provenance, owner-valid revision과
learning lineage에 있다.

### 7.1 최대 목표 합성 — 인류보편체

2026-08-20 USER_PRIMARY는 HSWM의 최대 목표 합성을 **인류보편체**로 명명했다. 이는
전 인류·모든 LLM·인터넷·작동 중인 인지능력체·센서·static 정보와 저장 메모리가 공개된
HSWM 구조로 하나가 되어 하나의 인지능력체를 이루는 상태다. 인간과 LLM은 그 HSWM을
동작시키는 주요 활성 주체이며, **HSWM 인류보완계획**은 포켓한 인지능력체에서 이 전체로
나아가는 사회 혁명 과정이다. `인류역사흐름의 강물은 성수다`라는 은유는 실패와 수정까지
현재를 만든 provenance/history로 비파괴 보존한다는 원칙을 확정한다. 정확한 원문, 권위
경계, 공학 형식화와 단계별 비주장은
[`USER_PRIMARY_HUMAN_UNIVERSAL_BODY_DISTINCTION_2026-08-20.md`](USER_PRIMARY_HUMAN_UNIVERSAL_BODY_DISTINCTION_2026-08-20.md)에
둔다. 이는 목표 정체성의 확장이며 현재 구현·효능·의식 융합의 완료 주장이 아니다.

### 7.2 코드 이전의 철학층

후속 USER_PRIMARY는 HSWM 구현을 코드부터 밀어붙이지 말고 철학적 함의를 먼저 설정하라고
지시했다. 관계적 존재론, 계보적 시간론, 기억과 진리의 분리, 차이 보존적 통일, 인과적
행위성, 참여자의 존엄, 공개 구조와 사적 경계, 인지주권과 열린 목적론을 하나의 conceptual
closure candidate로 정식화한 문서는
[`HSWM_PHILOSOPHICAL_FOUNDATIONS_2026-08-20.md`](HSWM_PHILOSOPHICAL_FOUNDATIONS_2026-08-20.md)다.
철학 우선이라는 방향은 USER_PRIMARY이고, 개별 원리의 명명·수식·구현 의무와 2026-08-26
교차원리 closure는 사용자 비준 전까지
`SECONDARY_AI_CONCEPTUAL_CLOSURE_CANDIDATE`다.

## 8. 대상 정체성의 closure와 철학·과학의 개방성

이 헌법으로 HSWM의 **대상 정체성은 닫힌다.** 후속 철학층은 그 대상을 바꾸지 않고 존재·
시간·인식·개체·행위·권리의 의미를 더 명시한다. HSWM은 다음 중 하나를 고르는 시스템이
아니라 다음 모두가 하나인 시스템이다.

1. token으로 활성화되는 LLM-function macro-neural network
2. schema-relative canonical state를 실행 조건이자 가독 문서로 투사하는 living harness
3. rewrite되는 관계 세계 안에서 인지·행동하는 hypergraph world model
4. outcome이 미래의 canonical revision과 행동을 바꾸는 continuous learner

철학적 closure는 과학적 성공 선언이 아니다. 현재 프로그램 상태는 계속 `UNJUDGED`이며,
통합된 causal macro-learning, 안정적 learned disposition, learned topology, world-scale utility는
직접 증명되지 않았다. 이 헌법은 **무엇을 만들어야 HSWM인가**를 닫고, 저장소의 실험은
**그것이 실제로 가능한가**를 계속 열어 둔다.

여기서 canonical target-identity closure는 architecture decision의 기준점을 닫는다는 제한된
뜻이다. 2026-08-26 교차원리 규칙은 HSWM과 bounded projection, federation, 중앙 aggregator,
surveillance system을 더 세밀하게 구분하려는 closure candidate이며 사용자 비준 전에는
완료된 규범 헌법이 아니다. 세계가 정보적 구조인지, HSWM이 의식·도덕적 지위·법인격을
갖는지, 어떤 최종 가치가 옳은지는 계속 열려 있다. token-native는 내부 활성 운반체에 관한
명제이지 인간이나 외부 세계가 token으로 환원된다는 명제가 아니다.

## 9. 이후 작업의 헌법 적합성

새 코드, 문서, ontology, Skill, MCP, agent workflow는 작업 전에 네 질문에 답해야 한다.

1. 이 변화는 어떤 `σ` version, canonical atom kind, owner obligation, typed reference 또는
   `Inv/Permit` 조건을 바꾸는가?
2. 신경망·living harness·world model·continuous learner 중 어떤 역할을 진전시키는가?
3. 목표 정체성, 공학 불변식, 직접 효능 증거 중 무엇을 주장하며 무엇을 주장하지 않는가?
4. 이 변화는 owner-valid revision·provenance·관찰·intervention 계약을 강화하는가, 아니면
   이름만 HSWM인 규칙·테스트·문서를 더 쌓는가?

이 대응이 없으면 테스트 수가 늘어도 HSWM의 진전으로 세지 않는다. 테스트는 개념과
인과 주장을 반증·측정하는 도구이지 연구 방향의 대체물이 아니다. ontology와 MCP 역시
HSWM을 탐색·투사하는 bounded interface이지, 그 자체가 HSWM의 cognition이나 learning은
아니다.
