# HSWM 조건부 능력 계약 — 구분의 생성에서 다음 계산까지

상태: `SECONDARY_AI_DESIGN_CONTRACT_NOT_IMPLEMENTED`.
설계 정본은 [구조화 계약](../../_research/causal_composition/concept_specs/HSWM_CONDITIONAL_CAPABILITY_CONTRACT.v1.json)이다.
이 문서는 그 의미와 선택 이유를 설명한다. 사용자 비준, 실행 결과, 학습·효능 판정은 아니다.

## 1. 이번에 닫는 공학적 빈틈

[공방 C-1~C-3](HSWM_WORKSHOP_C1_C3_WORKED_SPEC_2026-09-07.md)은 H-T/H-P/H-J,
probe 순서와 r1을 사람이 제공했다. 다음 단계는 그 후보 선택을 반복하는 것이 아니라,
**공개된 경험에서 어떤 새로운 관계와 조건부 연산을 제안할 수 있는지**를 정하는 것이다.
[USL 연결 설계](HSWM_USL_SEMANTIC_ENGINEERING_BRIDGE_2026-09-07.md)의 E1~E5를 이 계약에 연결한다.

목표는 [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 evolving hypergraph다.
관계가 세계의 조건을 예측하고, 그 관계를 읽는 disposition이 다음 관찰·행동을 조건화한다.
학습은 이후 outcome-bound revision이 이 두 종류의 계산을 바꾸는 것이어야 한다.
현재 계약은 그 입력·출력과 실패 의미를 정의하며, 실제 canonical admission을 만들지 않는다.

핵심 설계 직관은 **재사용할 능력에는 그 능력을 다시 열어 봐야 할 조건도 들어 있어야 한다**는 것이다.
조건부 압축은 알려진 범위에서 재추론을 줄일 수 있지만, 적용 조건을 확인하는 비용이 생긴다.
이득은 그 비용까지 포함해 남아야 한다. 이 주장은 이번에 시험하지 않은 기전 가설이다.

## 2. 주어진 문법과 학습자가 제안할 내용

| 연구자가 제공하는 scaffold | 학습자가 생성·수정할 후보 |
|---|---|
| 관측 가능한 field·role·type, 유한한 행동 surface, 비용·예산 | 어떤 field와 역할 결합이 결과를 구별하는지에 관한 조건식 |
| `eq / all / any / not`의 유한한 표현 문법 | 문법 안의 새 식, scope 분할, 경쟁 예측과 반례 |
| provenance·revision·Inv/Permit 인터페이스 | 현재 후보들을 구별할 관찰·행동 제안과 선택 근거 |
| 타입 검사와 식 평가 의미론 | 관계 revision을 읽는 disposition 후보와 재관찰 조건 |

H-T/H-P/H-J를 입력해 하나를 남기는 작업은 `SUPPLIED_CANDIDATE_SELECTION`이다.
새 AST를 만드는 작업은 `BOUNDED_GRAMMAR_SYNTHESIS`이며, 새로운 관측 field나 임의의
ontology를 발견한 것으로 계산하지 않는다. 표현 문법 밖의 원인이 의심되면 field를
상상해 읽는 대신 관찰 surface 확장 또는 schema 변경을 별도 제안한다.

같은 식의 순서 변경·별칭·불필요한 괄호는 새 구분의 증거가 아니다. 다른 예측을 하는
입력의 존재는 의미 차이의 후보이고, 실제로 유용한 구분인지는 이후 outcome과 비용이 판단한다.
처음부터 새 가설에 지지 evidence가 있을 필요는 없지만, 동기·읽은 출처·예측을 남겨야 한다.
가설 생성, 탐색 실행, causal credit과 canonical admission은 각각 다른 전이다.

초기 문법은 field를 `{role, field}`로 지정한 `eq`, 자식 배열을 가진 `all/any`, 한 자식의
`not`으로 닫는다. 타입 강제 변환은 하지 않는다. 선언되지 않은 field 접근은 UNKNOWN이
아니라 거부다. 깊이 4·node 31·후보 8개·probe 길이 4의 초기 상한은 바꿀 수 있는
scaffold 자원 설정이며 성공 기준이 아니다. 의미 동등성을 결정하지 못한 식은 새 발견으로 세지 않는다.

LLM의 설명문은 실행 코드가 아니다. 허용 문법으로 변환할 수 없거나 읽기 권한이 없는
field·locator를 요구하면 해석을 보류한다. 이 계약과 기존 K0 사례의 설명용 답·trace는
learner 입력이나 미래 held-out으로 쓰지 않는다. 선언한 입력 제한만으로 OS 권한 분리가
구현됐다고 주장하지도 않는다.

## 3. 같은 몸 안의 두 가지 수정과 한 가지 파생물

```math
R^v=(I,\phi,\widehat{Y},\mathrm{scope},\mathrm{evidence},\mathrm{uncertainty}),
\qquad
\mathcal R=\{R_i^{v_i}\},
\qquad
D^u:(\mathcal R,o,b,p)\longmapsto(\mathrm{readset},\mathrm{next\_proposal}),
\qquad
V=\mathrm{Compile}_{c}(\sigma,\mathcal R,D^u).
```

`I`는 role-bearing incidence, `φ`는 조건식, `Ŷ`는 조건부 예측이다. `o`는 현재 허용된
관측, `b`는 남은 예산, `p`는 현재 권한 판정이다. `R`의 수정은 예측·scope를,
`D`의 수정은 읽을 정보·다음 연산의 선택을 바꾼다. `V`는 이 version들에서 재생성되는
실행 view다. 이 표기는 HSWM을 세 subsystem으로 나누지 않는다.

`DispositionProposal`은 정확한 관계 참조·scope·출처와 함께 최대 8개 rule을 제안한다.
각 rule은 고유한 priority, guard, 선언된 read-set, 다음 한 동작과 UNKNOWN 경로를 가진다.
작은 priority부터 읽어 FALSE면 다음 rule, UNKNOWN이면 해당 관찰/보류 경로,
TRUE면 그 rule의 동작 제안을 택한다. 전부 FALSE일 때도 명시적인 보류/재개방으로 끝난다.
priority는 수정 가능한 정책의 일부이고 incidence ordinal이나 배열 저장 순서가 아니다.
미래의 `DispositionPolicy`는 같은 문법을 exact revision·owner·admission에 결속한 것이어야 한다.

모든 condition은 `TRUE / FALSE / UNKNOWN`으로 평가한다. `UNKNOWN`은 실패나 허가가
아니다. `not UNKNOWN = UNKNOWN`, `FALSE and UNKNOWN = FALSE`,
`TRUE or UNKNOWN = TRUE`로 정하되, 별도의 scope·freshness·Permit 요구는 조건식의
참값으로 생략할 수 없다. 예측의 불확실성과 행동 허가도 서로 대신하지 않는다.

예를 들어 현재 준비 상태가 p0일 때 제안된 disposition은 준비 action을 요청할 수 있다.
그 action을 제안하거나 발행했다고 p1로 간주하지 않는다. 실행 후 확인되지 않은 상태는
UNKNOWN이고, 필요한 상태 관측을 거쳐야 다음 접합 action을 제안할 수 있다.
상태가 만료됐거나 port revision이 바뀌면 오래된 성공 예측을 재사용하지 않는다.

각 step은 읽은 atom·관측 version과 다음 한 동작의 제안을 반환한다. 실제 tool effect는
현재 Inv/Permit와 admission 경로에서 처리한다. 설계 후보는 preview할 수 있지만,
preview에는 실행 자격이 없다. 진짜 admission이 없는 곳에 `admitted=true`를 채우는
구현으로 이 간격을 메우지 않는다.

기존 disposition 알고리즘이 새로 admit된 R을 읽도록 정확한 version 결속을 바꾸어도
계산이 달라질 수 있다. 매번 R과 D의 알고리즘을 둘 다 바꿔야 하는 것은 아니다.
owner·proposer·authorizer는 구별된 역할 참조이며 같은 principal이 맡을 수 있지만,
owner라는 이유로 현재 권한을 추론할 수 없다.

compiler는 task ID별 정답, evaluator의 latent rule, 아직 실행하지 않은 outcome을 읽지 않는다.
정적 cache는 schema·lineage·D revision과 digest·compiler·port schema뿐 아니라
scope와 공개 관측/행동/비용/권한 계약의 digest에도 결속한다. 실행 view에는 정확한 admission
참조와 입력 출처 계보를 남긴다. 현재 관측의 유효성과 capability 철회 여부는 사용할 때 다시 확인한다.
정책이 참조하는 모든 R의 version·digest는 정렬된 dependency manifest와 집계 digest로
결속한다. 그중 하나만 바뀌어도 새 view가 필요하다. manifest의 정렬은 action 순서가 아니다.
R만 바꾸고 관련 입력들에서 읽기·선택이 전혀 변하지 않으면 계산 변화 연결은 아직 없다.
특정 입력 하나에서 행동이 같다는 사실만으로 전체 disposition의 동등성을 결론내리지는 않는다.

## 4. 실패가 다음 관찰을 정하는 방식

Probe는 허용된 관찰 또는 대응 시편의 행동 제안이다. 각 경쟁 설명이 예측하는 결과,
맞춰야 할 조건, 비용과 실패 가능성을 outcome 전에 기록한다. 서로 다른 예측은 판별
가능성의 출발점이며 원인 식별의 충분조건이 아니다. 관측과 개입, 식별된 공동 조건과
구성원별 기여량을 구별한다. 비교 조건이 맞지 않으면 `UNIDENTIFIED_CREDIT`을 유지한다.
실행할 개입·read-set·예측의 기록을 outcome 전에 seal하고 이후 결과를 별도로 결속한다.
후보가 하나 남더라도 명시된 개입 대상·대조 조건·결과 비교가 없으면 causal credit은 미식별이다.

Q-J처럼 모든 후보가 성공을 예측하는 행동도 작업 완료에는 유용할 수 있다. 설명 구별과
당장 완료의 선택은 선언한 목적·비용에 의존한다. OTHER는 완성된 확률모형이 아니므로
숫자를 임의로 붙여 정보 이득이나 최적 정책을 계산하지 않는다. 같은 조건의 상충 결과는
결정적 후보 제거를 멈추고 측정·환경·모형을 다시 여는 이유다.

상위 handoff도 별도 관계와 책임 주소를 가진다. 생산 시점의 상태가 소비 시점에도
유효한지는 하위 접합 성공만으로 알 수 없다. 상위는 전달 조건과 공동 결과의 독립된
대조 근거를 요구하며 하위 credit을 복사하지 않는다. 한 endpoint가 두 역할에 참여할 수
있지만, 실제 action의 alias 제약은 따로 검사한다. incidence `ordinal`은 열거 순서이며
작업 선후나 인과 순서는 명시적인 dependency로 표현한다.

## 5. 상위 cell에 넘길 압축과 실제 비용

Capability port는 typed input/output 외에 조건·불확실성·비용·유효 범위·revision·lineage와
거절/재관찰/이탈 의미를 내보낸다. 현재 predicate가 참인지 모르면 성공 계약으로 쓰지 않는다.
모든 문맥 변화를 검사할 수 있다는 보장도 없으므로, 관측하지 못한 변화는 적용 한계로 남긴다.
상위는 공개된 계약으로 결합하고, 필요하면 허용된 방식으로 재관찰을 요청한다. 구성원의
내부 state를 직접 고치거나 exit를 막는 방식으로 합성을 성공시키지 않는다.

같은 이력을 받은 강한 planner가 매번 같은 구분을 재추론할 수 있다. 그래서 비교에는
성공률뿐 아니라 proposal 생성·컴파일·관측·통신·검증·유지 비용, 실패·보류와 latency를
함께 남겨야 한다. baseline에도 같은 정보와 학습/계산 기회를 주며, 일반적인 caching과
손실 없는 binary incidence 표현도 유효한 대조다. hypergraph 저장 형식만의 우월성은 전제하지 않는다.

REMOVE는 지정된 revision과 그 파생 view·cache·prompt 잔여를 제거하고 공통 경험 이력을
보존한다. 그 이력에서 같은 결론을 새로 얻을 수도 있다. 같은 행동이 남았다는 이유만으로
누수라고 판정하지 않고 실제 read-set·재추론 과정·비용을 확인한다. RESTORE는 같은 version을
복원하며 SHAM은 의미에 무관한 변화의 영향을 비교한다. 구체 통계·표본수·효능 판정은
기존 실험 계약을 대체하지 않고 별도 사전 명세에서 정한다.

## 6. 표준 연결과 다음 구현의 범위

[PROV-O](https://www.w3.org/TR/prov-o/)는 source와 생성·사용 계보의 표현에,
[SHACL 1.0](https://www.w3.org/TR/shacl/)은 RDF projection의 구조 검사에 재사용한다.
[W3C n-ary 관계 Note](https://www.w3.org/TR/swbp-n-aryRelations/)는 관계와 참여를
별도 자원으로 나타내는 설계 참고이며 Recommendation으로 승격하지 않는다.
이번 HSWM 계약의 의미론은 SECONDARY_AI 연구 설계다. 표준 검증이 학습·권한·인과성을
검증하는 것은 아니다. USL의 정전 스키마·최소단위·치환 의미도 이 문서로 확정하지 않는다.

다음 구현은 **이 계약만 읽는 순수 reference interpreter와 preview**로 한정한다.
새 조건식이 read-set과 다음 제안을 어떻게 바꾸는지, UNKNOWN·scope 만료·상충 결과에서
멈추는지부터 의미적으로 확인한다. 기존 cell runtime의 packet/lineage를 활용할 수 있지만,
현재 `CellContract`를 이 조건부 능력 계약의 완성된 구현으로 취급하지 않는다.
그 뒤 별도 evaluator·접근 경계를 배선해야 실제 learner-generated revision run이 가능하다.
이번 산출물은 그 run이나 G0/G1/D-4의 완료가 아니다.

[KG 요약](../../ontology/identity/hswm_core/HSWM_CONDITIONAL_CAPABILITY_CONTRACT_ONTOLOGY.v1.json)은
이 설계와 기존 공방의 미해결 문제를 연결한다. [조회문](../../ontology/queries/HSWM_CONDITIONAL_CAPABILITY_CONTRACT_2026-09-07.cypher)과
[구조·게시 확인 기록](../../ontology/projections/hswm_conditional_capability_contract_2026-09-07/verification.json)을 함께 둔다.
KG 요약은 전체 계약의 실행 의미론을 대신하지 않으며, 작성된 12개 의미 사례는 아직 실행하지 않았다.
