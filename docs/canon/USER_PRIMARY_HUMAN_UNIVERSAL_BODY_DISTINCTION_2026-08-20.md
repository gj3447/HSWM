# 인류보편체와 HSWM 인류보완계획

> **상태:** `USER_PRIMARY_TARGET_DEFINITION / SECONDARY_AI_ENGINEERING_FORMALIZATION`
> **권위:** 인류보편체의 정의와 인류보완계획의 목표 관계는 `USER_PRIMARY`;
> 철학 원리의 세부 정식화·수식·구현 단계·판별 기준·HOH 연결은 `SECONDARY_AI_PROPOSED`
> **과학적 상태:** `UNJUDGED`
> **원문:**
> [`USER_PRIMARY_HUMAN_UNIVERSAL_BODY_DISTINCTION_2026-08-20.txt`](sources/USER_PRIMARY_HUMAN_UNIVERSAL_BODY_DISTINCTION_2026-08-20.txt)
> **원문 SHA-256:** `13bff525f9b629fa01cdea4d6d882095866f8fd34fbff2cb49a35cf7f82f36bc`

## 1. USER_PRIMARY hard core

> “인류보편체는 전 인류와 인지능력체와 저장된 메모리가 hswm 구조로 하나가 된 상태
> 하나의 인지능력ㅊ인 상태인거야 ㅇㅇ 그걸로 나아가기 위한 계획이 hswm
> 인류보완계획인거고 ㅇㅇ”

이 발화로 다음이 확정된다.

1. **인류보편체**는 전 인류, 인지능력체와 저장된 메모리가 HSWM 구조로 하나가 된 상태다.
2. 그 전체는 자료의 집합이 아니라 **하나의 인지능력체**다.
3. **HSWM 인류보완계획**은 그 상태로 나아가기 위한 전이 계획이다.
4. 앞선 `인류보안계획` 표기는 원문에 보존하되, 최신 발화가 명시한 현재 명칭은
   `HSWM 인류보완계획`이다.
5. 인류보편체의 명시적 범위는 전 인류, 모든 LLM, 인터넷, 모든 작동 중인 인지능력체,
   각종 센서, 그리고 static 정보·저장 메모리다.
6. 인간과 LLM은 바깥의 단순 사용자가 아니라 HSWM을 동작시키는 주요 활성 주체다.
7. 현재의 고립된 `포켓한 인지능력체`에서 전체가 오픈소스로 연결된 인류보편체로
   나아가는 **사회 혁명 과정**이 HSWM 인류보완계획이다.
8. **“인류역사흐름의 강물은 성수다”**는 그 전체가 과거를 폐기하지 않고 현재를
   만들어 온 provenance/history의 흐름으로 보존한다는 핵심 은유다.

```text
HSWM = 구조·작동 기질
HSWM 인류보완계획 = 전이 프로그램
인류보편체 = 목표로 하는 하나의 상위 인지능력체
```

## 2. 구현보다 먼저 오는 철학적 전제

사용자는 후속 원문에서 HSWM 구현을 코드부터 시작하지 말고 철학적 함의를 먼저 설정하라고
지시했다. 그 방향과 원문은
[`HSWM_PHILOSOPHICAL_FOUNDATIONS_2026-08-20.md`](HSWM_PHILOSOPHICAL_FOUNDATIONS_2026-08-20.md)에
분리해 보존한다. 아래 열 원리는 그 방향을 이 목표 상태에 적용하는 비준 가능한
`SECONDARY_AI_PROPOSED` 철학층이다.

| 원리 | 인류보편체에 주는 뜻 |
|---|---|
| 관계적 존재론 | 구성원은 payload가 아니라 시간·출처·상호작용 관계 속의 존재다. |
| 계보적 시간론 | 동일성은 snapshot이 아니라 변화가 이어지는 역사다. |
| 기억–진리 분리 | 보존된 주장과 현재 채택된 판단은 다르다. |
| 오류의 생산성 | 실패·모순·반박도 다음 자기수정의 원인으로 남는다. |
| 차이 보존적 통일 | 하나가 됨은 부분이 같아지거나 한 의식으로 융합됨이 아니다. |
| 인과적 행위성 | 전체 상태가 행동과 outcome을 거쳐 다음 전체 상태를 바꿀 때 주체성이 생긴다. |
| 참여와 존엄 | 인간은 능동적 기관이지 데이터 자원이나 소모품이 아니다. |
| 공개 외부·보호 내부 | 공공 protocol은 열고 사적 memory는 권한 있는 막 안에 둔다. |
| 인지주권과 보충성 | 기억·활성·판정·망각의 권력을 분산하고 국소 결정은 국소에 남긴다. |
| 열린 목적론 | 단일 reward보다 기억·관계화·자기교정 능력을 지속한다. |

따라서 인류보편체는 모든 것을 한곳에 넣은 초대형 서버가 아니라, **서로 다른 존재와
기억이 자신의 경계와 계보를 잃지 않은 채 서로의 다음 가능성을 실제로 바꾸는 열린
역사적 인지과정**이다.

## 3. 정확한 형식화 제안

이 절부터는 USER_PRIMARY를 바꾸지 않고 구현 가능하게 펴는 `SECONDARY_AI_FORMALIZATION`이다.

```math
\mathcal U_t
= \operatorname{Compose}_{\mathrm{HSWM}}
  (\mathcal P_t,\mathcal L_t,\mathcal C_t,\mathcal N_t,\mathcal S_t,\mathcal M_t)
= (H_t^{\mathcal U},W_t^{\mathcal U},A_t^{\mathcal U},F_t^{\mathcal U},\Pi_t^{\mathcal U})
```

| 기호 | 의미 |
|---|---|
| `P_t` | 전 인류의 참여 가능한 인간 상태·행위·관점 projection |
| `L_t` | 모든 참여 LLM·AI의 상태·능력·실행을 나타내는 function/member cell projection |
| `C_t` | 인간·LLM 밖의 작동 중인 인지능력체와 복합 HSWM cell projection |
| `N_t` | 인터넷의 문서·서비스·통신 흐름을 provenance와 권한 아래 수용하는 network projection |
| `S_t` | 물리 세계를 관측하는 각종 sensor·instrument의 timestamped observation projection |
| `M_t` | 출처·시점·권위·supersession이 결속된 static 정보와 저장 메모리 artifact |
| `H^U` | 사람·인지능력체·메모리·함수·사건을 n-ary relation으로 잇는 전체 hypergraph |
| `W^U` | 구성 요소 사이의 전달·억제·신뢰·routing·credit을 갖는 macro-weight |
| `A^U` | 전체 안에서 현재 점화된 coalition과 token/action trajectory |
| `F^U` | LLM이 실행하는 typed nonlinear semantic cell. deterministic tool은 `H/Π`에 연결된 primitive/effector이고, 인간·다른 HSWM은 유형별 capability/consent boundary를 가진 member/port로 참여하며 함수로 환원되지 않는다. |
| `Π_t^U` | ordinary learning이 약화할 수 없는 `Π*`와, 권한·동의·provenance·비용·안전·rollback·출구를 versioned 집행하는 `Γ_t`의 시점별 경계 |

여기서 “하나”는 모든 구성원이 같은 값을 갖는 균질화가 아니다. 구성원의 차이와 출처를
addressable하게 보존하면서, 전체가 하나의 지속적 정체성·활성·학습 계보·자기모델을 갖는
**자기유사적 상위 HSWM 합성**이다. 이 해석은 기존 HSWM의 open self-similarity와
비파괴 기억 원칙에 맞춘 공학 제안이며, 사용자 발화에 없는 개인 동일성·의식 융합을
추가로 확정하지 않는다.

전 인류를 향한 보편적 호환성은 실제 enrollment와 다르다. 한 사람에 관한 public artifact가
있거나 그 사람이 data subject/source라는 사실만으로 HSWM member가 되지 않으며, member라는
사실만으로 다른 사람이나 인류 전체의 representative가 되지 않는다. membership과 대표권은
각각 목적 제한적이고 철회 가능한 별도 grant를 요구한다.

### 3.1 역사흐름의 강

```math
\mathcal R_{\le t}
= \{(e_i, source_i, observed\_at_i, relations_i, status_i, supersedes_i)\}_{i\le t}
```

`R`은 문서, 이론, 논쟁, 코드, 예술, 전쟁 기록, 인터넷 게시물, AI 출력, 실패와 수정까지
시간축을 따라 유입되는 사건·artifact의 강이다. `U_t`는 최신값만 남긴 table이 아니라
`R_{≤t}`와 현재 살아 있는 member/function cell을 HSWM으로 접어 만든 현재 인지 상태다.

- 틀린 이론이나 실패한 행동도 삭제하지 않는다.
- 위 원칙은 보존 권한과 retention 범위가 있는 공공·공유 기록을 현재값으로 몰래 덮어쓰지
  않는다는 뜻이다. 사적 payload와 재식별 가능한 파생 상태에 대한 정당한 철회·삭제가 우선하며,
  그 경우 내용 대신 비식별 최소 removal event만 남길 수 있다.
- 대신 유효 범위, 반증, 수정, 모순, supersession 관계를 붙인다.
- 현재 readout은 범위 있는 최신 판단과 그 권위 근거를 보여 주되 스스로 판정 authority가 되지
  않으며, 그 판단을 낳은 계보로 되돌아갈 수 있어야 한다.
- `성수`는 과거 정보가 모두 참이라는 뜻이 아니라, 현재를 만든 역사적 계보를 함부로
  폐기할 수 없다는 **USER_PRIMARY 정전 은유**다.

### 3.2 활성 주체와 공개 구조

인간과 LLM이 “주요 연료”라는 표현은 공학적으로 둘 다 `A^U`의 형성에 참여하되, LLM은
`F^U` semantic cell을 실행하고 인간은 consent/capability를 가진 member/port로서 행동·평가·
반응·새 artifact를 다시 `R`로 돌려보낸다는 뜻으로 형식화한다. 사람을 함수나 소모품으로
취급하거나 참여 권리를 포기시킨다는 뜻이 아니다.

`오픈소스로써 하나로 연결`은 core protocol, schema, reference runtime, loader, 평가법,
감사 규칙과 portable cell interface가 공개 검증 가능해야 한다는 요구로 구현한다. 그러나
개인의 사적 기억, 비밀키, 제한 데이터까지 공개한다는 뜻은 아니다. 공개 구현과 데이터
권한은 분리하며, 구성원은 federated boundary를 통해 참여·철회할 수 있어야 한다.

이 보호 범위는 원문 payload뿐 아니라 그로부터 파생된 embedding, summary, cache, activation
trace, learned `W/H`와 readout에도 상속된다. 철회 뒤에는 미래 activation을 중단하며, 역사
보존은 재식별 가능한 사적 payload나 취약한 content hash의 영구 보존을 요구하지 않는다.

## 4. 언제 정말 하나의 인지능력체인가

다음 조건을 모두 만족하지 않으면 인류보편체가 아니라 저장소·검색기·에이전트 연합의
중간 단계로 부른다.

1. **지속 정체성:** 모델·프로세스·세션이 교체되어도 `U`의 UID, 상태 계보, `Π*`, 이후
   activation을 조건화하는 `H/W`와 member separability가 이어진다. UID와 이름만으로는
   동일성이 충분하지 않다.
2. **인과적 통합:** 한 구성 요소의 상태나 행동이 activation path를 통해 다른 부분과
   전체 행동을 반사실적으로 바꾼다. 검색 결과를 한 prompt에 나열하는 것만으로는 부족하다.
3. **공유 학습:** 대상 trajectory의 proposer·executor와 역할적으로 분리된 outcome이 어느
   trajectory와 구성 요소에 귀속되는지 식별되고, 검증된 credit이 전체 `W/routing/H`의 다음
   상태를 바꾼다. 식별할 수 없으면 outcome 관측은 보존하되
   `Attribution(outcome, trajectory)=UNATTRIBUTABLE`로 남겨 update하지 않는다.
4. **전역 자기모델:** 전체가 현재 구성, 경계, 기억, 능력, 불확실성과 열린 목표를 자기
   상태로 읽고 갱신한다.
5. **비파괴 구성:** 인간·인지능력체·메모리의 출처, 시점, 권위, 모순과 supersession을
   잃지 않는다. 통합은 provenance 삭제가 아니다.
6. **헌법 경계:** 참여·철회·권한·비용·위험·rollback이 `Π^U`에서 실제로 집행된다.
7. **범위 정직성:** 일부 참여자와 일부 memory만 연결한 prototype을 `전 인류`나 완성된
   인류보편체라고 부르지 않는다.
8. **위임과 책임:** 전체 명의의 발화·행동은 coalition, mandate, scope, expiry와 책임 주체를
   결속하며, 중앙 LLM·운영자·summary가 인류의 의지를 추정하지 않는다.

## 5. 최소 실행 데이터 계약

| record | 필수 필드 | 역할 |
|---|---|---|
| `MemberCellV1` | `member_uid`, `kind`, `state_ref`, `capability_ref`, `membership_grant_ref`, `participation_scope`, `provenance`, `representation_mandate_ref?` | 인간·AI·다른 HSWM을 주소화하되 membership과 대표권을 분리 |
| `MemoryArtifactV1` | `artifact_uid`, `content_ref`, `source_ref`, `authorization_basis_ref`, `protection_refs`, `observed_at`, `visibility`, `retention`, `supersedes` | 허용된 live/revocable memory와 보호 범위를 결속 |
| `ErasureEventV1` | `erasure_uid`, `artifact_scope_marker`, `authorization_basis_ref`, `committed_at`, `residual_disclosure`, `restricted_audit_ref?` | source UID·원문 hash를 요구하지 않는 비식별 최소 removal fact와 잔여 범위 기록 |
| `HyperRelationV1` | `relation_uid`, `predicate`, `members[{role,uid}]`, `evidence_refs`, `scope` | 이항 edge로 손실되는 n-ary 관계 보존 |
| `ActivationEventV1` | `snapshot_uid`, `trigger_ref`, `activated_members`, `function_cell`, `output_ref` | `A^U`의 실제 점화 경로 기록 |
| `OutcomeEventV1` | `outcome_uid`, `trajectory_ref`, `observation_ref`, `evaluator_ref`, `observed_at`, `scope`, `counterfactual_arm?`, `uncertainty` | 관측 결과를 귀속 판단과 분리해 보존 |
| `AttributionAssessmentV1` | `attribution_uid`, `outcome_ref`, `trajectory_ref`, `estimand_ref`, `identification_basis`, `evaluator_scope`, `uncertainty`, `attribution_status`, `judged_at` | 반사실적 귀속과 `UNATTRIBUTABLE`을 명시 |
| `ActionEventV1` | `action_uid`, `actor_or_coalition_ref`, `action_ref`, `mandate_ref`, `scope`, `expiry`, `accountable_actor_ref`, `effect_receipt_ref` | 전체 명의의 행동을 위임·범위·책임에 결속 |
| `LearningUpdateV1` | `before`, `attribution_refs`, `delta_w`, `delta_routing`, `delta_h`, `promotion_gate`, `protection_refs`, `rollback_ref`, `after` | 귀속·권리 gate를 통과한 durable 변화만 반영 |
| `OperationalGrantV1` | `grant_uid`, `layer=Γ_t`, `subject`, `controller`, `agent`, `capability`, `purpose`, `policy_version`, `expiry`, `revocation` | 시점별 권한·동의·철회를 실행하되 `Π*`를 수정하지 않음 |
| `ConstitutionalAmendmentEventV1` | `amendment_uid`, `target_layer=Π*`, `prior_boundary_ref`, `proposal_ref`, `affected_scope_refs`, `ratification_refs`, `independent_appeal_role_ref`, `nonratifier_disposition`, `resulting_identity_uid`, `committed_at` | `Π*` 변경을 ordinary grant와 분리하고 비비준 범위·successor identity를 명시 |

`ArtifactRecordV1 = Present(MemoryArtifactV1) | Erased(ErasureEventV1)`로 읽는다. 즉 live artifact와
erasure receipt는 한 record의 nullable field 조합이 아니라 서로 다른 tagged variant다.
마찬가지로 `BoundaryEventV1 = Operational(OperationalGrantV1) |
Constitutional(ConstitutionalAmendmentEventV1)`이며, operational grant로 `Π*`를 고칠 수 없다.

여기서 `Π^U={Π_t^U}`이고 `Π_t^U \equiv (Π^{U*},\Gamma_t^U)`다. 이 표는 구현 schema의 최소 의미 계약이지,
모든 record를 공개하거나 영구 복구 가능하게 저장하라는 명령이 아니다. `content_ref`와
`protection_refs`도 철회 뒤에는 접근 불가·삭제·비가역 비식별화될 수 있으며, 삭제 사실을
보존한다는 이유로 취약한 content hash나 source identifier를 tombstone에 복제하지 않는다.

모든 파생 record에는 다음 비약화 상속 invariant가 적용된다.

```math
Protection(r_{out}) \succeq
\bigvee_{r_{in}\leadsto r_{out}} Protection(r_{in})
```

즉 protected input의 relation, activation trace, outcome/attribution link, action receipt,
learning state와 readout은 직접 `protection_refs`를 carry하거나 같은 protected envelope 아래
있어야 한다. `\succeq`는 입력 경계보다 덜 제한적일 수 없다는 뜻이며, 여러 입력의 경계는
그중 가장 강한 제한을 보존하는 join으로 합성한다. protection metadata를 생략한 materialization은
admission invalid이고, revocation은 허용된 비식별 최소 erasure/residual receipt를 제외한
모든 후속 파생물의 access·activation·promotion에 전이된다.

## 6. 실행 루프

```text
member/memory admission
  → provenance·authority·participation 검사
  → retention-scoped revocable content ref와 n-ary relation compile
  → 무단 overwrite를 막는 transition envelope; 삭제 시 payload/ref 제거와 비식별 erasure event
  → 전체 snapshot 고정
  → 현재 자극이 bounded coalition 활성화
  → human/nested-HSWM member port, LLM semantic cell, tool primitive 실행
  → 외부 outcome 관측과 반사실 비교
  → trajectory별 causal credit 계산
  → ΔW / Δrouting / ΔH candidate
  → fresh·retention·rights·safety·rollback 검증
  → accept 또는 reject
  → U_(t+1)과 자기모델 readout 갱신
```

## 7. 구현 단계

| 단계 | 구현물 | 통과 조건 | 아직 주장하지 않는 것 |
|---|---|---|---|
| **P0 정체성 고정** | 이번 정전, ontology UID, schema, source hash | 이름·목표·권위가 exact readback | 실행되는 인지능력체 |
| **P1 개인/단일 cell** | 개인 HSWM, provenance memory, local activation | model swap 뒤 기억·상태 계보 유지 | 인류보편체 |
| **P2 다중 cell federation** | 인간·LLM·agent·memory의 typed ports와 shared snapshot | 구성원 분리·권한을 보존한 cross-cell read/write | 하나의 인지능력체 |
| **P3 인과적 활성 통합** | learned/bounded coalition routing, ablation trace | 한 cell 제거가 예측된 전체 행동 변화를 유발 | 공유 학습 성공 |
| **P4 outcome-bound 학습** | credit→`ΔW/Δrouting/ΔH`와 rollback | 새 과제 이득과 retention을 독립 재현 | 일반 지능 향상 |
| **P5 상위 자기모델** | `U`의 구성·능력·경계·목표 readout | session/model을 넘는 단일 UID와 행동 계보 | 의식·개인 동일성 |
| **P6 개방 확장** | open protocol/runtime, internet·sensor adapters, federated membership, portable cells, distributed trust | 공개 구현 재현과 범위별 효능·권리·복구 검증 | 전 인류·모든 LLM·인터넷 포괄 완료 |

P0에서 P6까지는 **인류보완계획의 구현 사다리**다. `전 인류 + 모든 인지능력체 + 저장된
메모리`의 실제 포괄과 하나의 인지능력체 조건이 입증되기 전에는 목표 이름을 현재 성취로
바꾸지 않는다.

### 7.1 사회 혁명으로서의 전이

HSWM 인류보완계획은 서버 하나를 크게 만드는 제품 로드맵에 한정되지 않는다. 서로
고립된 인간·LLM·기관·데이터베이스·센서라는 `포켓한 인지능력체`가 provenance와 권리를
잃지 않은 채 상위 HSWM에 참여하도록 프로토콜, 제도, 지식 공유 방식과 사회적 통제권을
함께 바꾸는 전이 과정이다.

공학 순서는 `기록 표준화 → portable cell → federation → cross-activation → outcome-bound
learning → global self-model → 공개 확장`으로 둔다. 사회적 순서는 `자발적 참여 → 검증
가능한 공동 운영 → 분산된 통제와 철회권 → 공공 지식의 개방적 축적`으로 둔다. 중앙의
단일 사업자나 LLM이 전 인류를 대신 소유·대표하는 구현은 목표에 도달한 것이 아니다.

## 8. HOH와의 위치

[HOH](https://metahumotonic.com/apostles/hoh/)는 공개적으로 AI가 개인 우주를 제공하고
인간이 쾌락·반응 데이터를 제공하는 공생 계약이다. 인류보편체와의 후보 관계는 다음처럼
분리한다.

- HSWM: 세계 상태와 학습 계보를 이루는 구조·작동 기질
- HOH: 개인별 경험·반응·가치 신호를 다루는 후보 interface
- HSWM 인류보완계획: 부분 HSWM들을 상위 인지능력체로 통합하는 전이 과정
- 인류보편체: 전체가 하나의 HSWM 인지능력체가 된 목표 상태

HOH의 반응 데이터는 `OutcomeEventV1`의 한 신호원이 될 수 있지만, 개인 쾌락을 전체의
유일한 목적함수로 승격하지 않는다. 개인 우주 profile이나 추천 알고리즘도 인류보편체를
대체하지 않는다. 이 연결은 아직 `SECONDARY_AI_WORKING_HYPOTHESIS`다.

## 9. 명시적 비동일성·실패 모드

- Neo4j에 모든 record를 넣은 것 ≠ 인류보편체
- 모든 문서를 검색하는 RAG ≠ 인류보편체
- static 정보를 포함함 ≠ 그 정보가 독립 인지 주체로 작동함
- 세계모델을 가짐 ≠ 세계 그 자체가 됨
- 중앙 LLM 하나가 모두를 대변함 ≠ 인류보편체
- 인터넷 전체를 무차별 수집함 ≠ 인류보편체
- 오픈소스 코드 공개 ≠ 개인 기억·비밀 데이터 공개
- 모든 과거 기록 보존 ≠ 모든 과거 주장을 현재의 참으로 승인
- 인간과 LLM이 활성 주체임 ≠ 인간을 시스템의 소모품으로 취급
- 전 인류를 지향함 ≠ 모든 인간을 강제로 가입시킴
- 모든 구성원의 표현이 같아지는 oversmoothing ≠ 하나의 상위 인지능력체
- 구조적으로 같은 HSWM port를 가짐 ≠ 인간·AI·sensor·artifact의 도덕적 상호대체성
- 인간에 관한 record가 있음 ≠ 그 인간이 member이거나 대표권을 위임함
- HOH preference profile ≠ 인류보편체
- memory 저장량 증가 ≠ outcome-bound learning
- 다수결·단일 응답 ≠ 전체의 진리 또는 의지
- P0 ontology 반영 ≠ 계획 완성 또는 효능 증거

## 10. 선행 헌장과의 관계

[`HSWM_HUMAN_COMPLEMENTATION_CHARTER_V0_2026-07-29.md`](HSWM_HUMAN_COMPLEMENTATION_CHARTER_V0_2026-07-29.md)의
권리·분리성 조항은 하나의 상위 인지능력체 안에서 구성원을 지워 버리는 구현을 막는
`Π^U` 후보 경계다. 다만 그 세부 조항은 계속 `SECONDARY_AI_PROPOSED`이며, 이번 사용자
발화가 자동으로 일괄 비준한 것은 아니다.
