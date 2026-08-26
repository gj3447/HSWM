# HSWM USER_PRIMARY supersession — schema-relative single responsibility owner

> **상태:** `USER_PRIMARY_DIRECTION / SECONDARY_AI_FORMALIZATION`
> **기준일:** 2026-08-26
> **원문:**
> [`USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.txt`](sources/USER_PRIMARY_HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_2026-08-26.txt)
> **원문 SHA-256:** `2093d9bb68219d6ba859444dc00aeef985a5c9151163e56972516addb2cd0ec6`
> **과학적 상태:** `UNJUDGED`
> **상위 정전:** [`HSWM_CONSTITUTION_2026-08-20.md`](HSWM_CONSTITUTION_2026-08-20.md)
> **amendment 범위:** Constitution의 one-system token-native target은 보존하고,
> 그 안의 fixed-role decomposition·owner registry 해석만 이 후속 USER_PRIMARY가 supersede한다.
> **상세 연구:**
> [`HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_SCIENTIFIC_PHILOSOPHY_2026-08-26.md`](../research/HSWM_SCHEMA_RELATIVE_SINGLE_OWNER_SCIENTIFIC_PHILOSOPHY_2026-08-26.md)

## 0. 권위와 답

사용자가 직접 확정한 것은 다음 세 방향이다.

1. `H/W/A/F`를 HSWM의 정본 분해로 폐기한다.
2. 승인된 정본 원자마다 책임 owner가 하나라는 schema-relative 유일성만 남긴다.
3. 그 토대에서 과학철학에 근거한 HSWM 사고 연구를 먼저 진행한다.

owner의 수식, schema 구성, atom granularity, typed reference, transition,
projection, 권한·권리와 실험 설계는 아래 원문에 없는 `SECONDARY_AI` 형식화다.
고정 `Π` 성분까지 정본 tuple에서 내리고 권리·권한을 전이 불변식과 authorizer
계약으로 재표현하는 결정도 “고정 역할 집합이 아니라 single-owner 원리만 남긴다”는
지시를 모순 없이 구현하기 위한 `SECONDARY_AI` 해석이지 사용자 문장의 소급 인용이 아니다.

## 1. 보존되는 target과 폐기되는 해석

| 구분 | 현재 지위 |
|---|---|
| LLM token event로 작동하는 거대 evolving hypergraph learning structure | `USER_PRIMARY`, 보존 |
| 하나의 시스템이 neural network·living harness·world model·continuous learner 역할을 함께 수행 | 보존 |
| outcome이 이후 구조·전이 disposition·행동을 바꾸는 causal-learning loop | 보존되는 target, 효능은 `UNJUDGED` |
| `S_t=(H_t,W_t,A_t,F_t,Π_t)`를 정본 state decomposition으로 사용 | 폐기 |
| `{H,W,A,F,Π}`를 닫힌 owner 집합으로 사용 | 폐기 |
| graph, weight, activation, function, policy를 독립 존재자처럼 배치 | 폐기 |
| 승인된 원자마다 schema-relative canonical responsibility owner 하나 | 현재 유일한 정본 ownership 원리 |

2026-08-20의 exact USER_PRIMARY token-hypergraph 원문은 `H/W/A/F/Π`를 직접
명령하지 않았다. 그 tuple은 후속 `SECONDARY_AI` 기술 형식화였으므로, 원문과 과학
evidence를 다시 쓰지 않고도 현재 지시가 그 형식화를 supersede한다.

## 2. 현재 canonical ownership 원리

schema version `σ`와 시점 `t` 아래 승인된 canonical atom version 집합을 `C_{σ,t}`, schema가 선언한
responsibility-owner 주소 집합을 `R_σ`라 한다.

```math
\operatorname{owner}_{σ,t}:C_{σ,t}\to R_σ,
\qquad
\forall a\in C_{σ,t}\;\exists!r\in R_σ:
\operatorname{owner}_{σ,t}(a)=r.
```

`C_{σ,t}`는 admission을 통과한 immutable versions만 포함한다. raw·quarantine item은
domain 밖이고, version key는 최소 `(schema_version,lineage_id,atom_uid,revision_id)` 또는
동등한 fork-safe 정보를 가진다. owner 변경은 in-place 덮어쓰기가 아니라 schema migration과
새 atom version으로 기록하며 이전 version의 owner history를 보존한다.

`R_σ`는 `H/W/A/F/Π` 같은 영구적 자연종이 아니다. 각 schema가 관찰 목적,
개입 범위, granularity, provenance와 복구 의무에 맞춰 versioned하게 선언한다.
single owner는 다음만 뜻한다.

> **한 canonical atom의 correctness, revision lineage, validation과 복구 의무를
> 최종적으로 조회할 canonical accountability address는 해당 schema 안에서 하나다.**

이는 한 의미, 한 저장소, 한 작성자, 한 인간 소유자, 한 권한자 또는 세계의 유일한
분해를 뜻하지 않는다. 다른 의미와 사용은 typed reference·projection·transition으로
표현한다.

`Owner_σ(a,p)`, `Claimant(e,p)`, `Subject(a,p)`, `Custodian(a,p)`와
`Authorizer(e,p)`는 서로 다른 typed predicate다. 같은 principal이 여러 역할을 맡을 수는
있지만 ownership만으로 다른 역할이나 effect permission을 도출할 수 없다.

```math
\mathsf{Owner}_{\sigma}(a,p)
\centernot\Rightarrow
\mathsf{Permit}_{\sigma}(S,e).
```

persistent·revisionable·queryable하거나 rollback·permission 효과를 갖는 relation/incidence는
자체 owner가 있는 canonical atom이다. source payload 안의 ephemeral pointer는 독립
lifecycle·commit·rollback·authorization 효과를 가질 수 없다.

## 3. HSWM과 Semantic Weight의 새 독해

- **Hypergraph**는 `H` compartment가 아니라, canonical relation·incidence atom과
  typed reference를 schema가 해석해 만든 HSWM 전체의 관계적 형태다.
- **Semantic Weight**는 `W` compartment가 아니라 schema-approved transition-disposition
  candidate다. 제거·교란·복원 intervention의 단순 차이는 후보일 뿐이며, causal efficacy는
  preregistered estimand, matched token·compute·exposure, sham/negative control, 독립 outcome과
  uncertainty 조건을 통과한 뒤에만 주장한다.
- **Activation**은 `A` compartment가 아니라 episode transition이나 sealed trace의
  현재 사건이며, durable하게 보존될 때에는 새 canonical atom version으로 admit된다.
- **LLM function**은 `F` compartment가 아니라 atom이 참조하는 executable contract와
  schema-admissible transition realization이다.
- **권리·권한**은 `Π` compartment가 아니라 ordinary learning이 우회할 수 없는
  `Invariant/Permit` 조건과 그 결정을 기록하는 canonical atom이다.

따라서 예전 글자들을 다른 이름으로 바꿔 고정 partition을 복원하는 것은 이 지시를
따른 것이 아니다.

## 4. 비파괴 supersession

- exact USER_PRIMARY source, hash-bound evidence, historical result와 compatibility
  record는 고치지 않는다.
- 기존 `H/W/A/F/Π` 문서는 당시의 `SECONDARY_AI` 탐색과 반례 기록으로 보존하되,
  현재 정본 설계 지침으로 사용하지 않는다.
- 기존 실험의 `H`, `W`, `A`, `F` 변수명은 역사적 protocol의 local notation으로
  재현할 수 있다. 그것이 새 HSWM ontology의 fixed owners가 되지는 않는다.
- 새 ontology가 필요하면 fixed five-role artifact를 문구만 바꾸지 않고,
  schema-declared owner registry를 가진 새 major version으로 설계한다.

## 5. 과학적 비주장

single-owner invariant가 provenance 정확도, 오류 격리, rollback, 인과 attribution,
권한 보존 또는 학습 효능을 개선했다는 직접 결과는 아직 없다. 이 문서는 target
형식화를 바꾸며 evidence 상태를 승격하지 않는다. 과학적 가치는 multi-owner,
God-owner, fixed-role, schema-relative single-owner 대조군을 둔 개입 시험에서만
판정한다.
