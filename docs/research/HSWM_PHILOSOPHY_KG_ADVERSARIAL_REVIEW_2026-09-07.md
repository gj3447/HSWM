# HSWM 철학 KG — 적대적 검증과 표준 기반 보완안

기준 checkout: `fdb88fafefa091d60a1826e2e970c7d1caadcc12`, 2026-09-07.
권위·상태: `SECONDARY_AI / ENGINEERING_REVIEW / REMEDIATION_PROPOSED_NOT_APPLIED`.

**철학 내용과 최근 projection은 존재하지만, 잘못 연결한 의미까지 걸러내는 체계는
불완전하다.** 앞선 감사의 노드 존재·차수·정확한 bundle 비교를 철학적 정합성이나
질의의 정확성으로 확대하면 안 된다. 이번에는 원본을 메모리에서 변형해 거부 여부를
확인하고, live DB 제약을 읽고, W3C·Neo4j 공식 문서에서 수리 방법을 확인했다.

개념적 보완은 **내용의 존재, 선언한 계약의 보존, 조회 가능성, 출처·권위의 정확성,
과학적 지지를 각각 구별해 확인하는 것**이다. HSWM의 하나인 몸과 schema-relative
single-owner, FCL-1~8 목표는 유지한다. 저장소 bundle의 소유와 canonical atom의 책임
owner도 다른 개념이다. 이 감사는 HSWM 실행·학습·효능을 평가하지 않는다.

## 1. 실제로 재현한 반례

[재현 프로그램](../../_research/graph_standards/audit_philosophy_projection_adversarial.py)과
[실행 기록](../../_research/graph_standards/results/HSWM_PHILOSOPHY_PROJECTION_ADVERSARIAL_AUDIT_2026-09-07.json)에
입력·code·shape·lockfile digest, 사용 버전과 각 결과를 남겼다. 변형본은 KG에 게시하지 않았다.

| 발견 | 관측한 결과 | 정확한 의미와 보완 |
|---|---|---|
| A1. 검사 대상 자체를 지우면 통과 | plan의 assertion/participation 역할을 `UNCLASSIFIED`로 바꾸고 incidence 관계를 지워도 generic+domain SHACL과 plan `validate_data`의 dict 사전 검증이 통과 | domain target이 없어져 관련 검사가 적용되지 않음. source에 결속된 역할별 대상 목록·수와 shape 적용 범위를 별도로 확인 |
| A2. 의미가 충돌하는 필드도 통과 | `authority_class=SECONDARY_AI`를 유지한 채 discovery authority를 `USER_PRIMARY`로 바꿔도 generic+domain SHACL 통과. 존재하지 않는 `current_decision_uid`도 generic 통과 | 권위 mapping과 실제 decision 연결을 서로 대조하는 제약이 필요. 공방의 `AUTHORED_SCENE`에 `OBSERVED_SUCCESS`를 넣어도 generic은 통과하므로 작성된 예시와 관측의 양립 조건도 검사 |
| A3. bundle 간 anchor 계약 소실 | 소유 node는 `Concept`뿐인데 다른 bundle이 `Concept+Guardrail`을 요구해도 construction과 generic SHACL 통과 | 다른 bundle에 소유된 anchor는 required labels 검사를 생략하고 RDF에도 그 요구를 남기지 않음. 요구를 별도 reference occurrence로 보존하고 소유 node와 대조 |
| A4. 다른 경로의 같은 내용이 잘못 합쳐짐 | 서로 다른 두 path에 같은 SHA를 선언하면 raw bundle 검증은 허용하지만 RDF에서 같은 ArtifactBinding으로 합쳐져 `bindingPath maxCount 1` 실패 | content entity와 경로별 binding occurrence를 분리해야 함. 이 fixture의 추가 path는 선언만 했으며 실제 파일 검증의 성공을 주장하지 않음 |
| A5. 역할 번호 중복을 구별하지 못함 | 동일 assertion의 두 participation ordinal을 같게 바꿔도 generic+domain SHACL 통과 | 역할 열거 번호의 유일성 계약을 정하고 assertion 내부에서 검사. 현 ordinal은 시간 순서가 아니므로 인과 순서 오류를 관측했다고 말하지 않음 |

A1은 schema가 다른 legacy 파일을 거부한 이전 결과와 다르다. 현행 plan schema의 입력이
도메인 검사 대상을 없앤 상태에서도 통과하는 반례다. 대상 수는 전체 연구에 임의의 고정
숫자를 강요하는 대신 각 source revision의 선언에서 얻어야 한다. 서로 다른 assertion에
같은 ordinal이 있는 것, 같은 target이 다른 역할로 참여하는 것은 오류가 아니다.

코드 근거는 [generic compiler](../../src/hswm/infrastructure/kg_bundle_graph_view.py)의
`_validate_bundle`, `from_bundles` 안 artifact/anchor 처리,
[generic shapes](../../schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0.ttl)의
Node/Claim/Decision/ArtifactBinding shape,
[domain shapes](../../schemas/HSWM_HYPERGRAPH_LEARNING_PLAN_SHACL_1_0.ttl)의 target과
ParticipationShape다. 기존 [closure 질의 테스트](../../tests/test_kg_bundle_graph_view.py)는
일부 의미 조건을 검사하지만 `current_decision_uid`와 연결된 decision의 UID까지 비교하지 않는다.

**기존 방어가 작동한 부분도 확인했다.** TARGET 하나만 제거하면 기존 domain SHACL은
실패한다. 실제 source digest를 틀리게 쓰면 plan adapter는 파일을 재해시해 거부한다.
plan의 `--apply`에는 reviewed raw SHA pin이 있어 변형본은 일치하지 않는다. 따라서 위
반례는 현행 publication pin 우회나 canonical 권한 획득의 증거가 아니다. 새 내용을
검토·버전 갱신할 때 shape 통과만으로 의미 검토를 대신할 수 없다는 증거다.

## 2. live publication과 revision의 추가 약점

**A6. DB가 UID 유일성을 강제하지 않는다.** 읽기 전용 `SHOW CONSTRAINTS`에서 `uid` 또는
`ontology_bundle_uid`를 속성에 포함한 제약은 0개였다.
[제한된 schema 조회 기록](../../_research/graph_standards/results/HSWM_KG_UID_CONSTRAINT_AUDIT_2026-09-07.json)에
접속 정보 없이 질의·필터·결과를 보존했다.
[publisher](../../scripts/upsert_hswm_graph_and_loop_engineering.py)의 `publish`는 조회 뒤
`CREATE`하며 중복 사후 확인도 수행한다. 그러나 동시에 두 transaction이 부재를 읽는
상황까지 DB 유일성 제약으로 막지는 않는다. **경쟁 실행이나 실제 중복 발생은 이번에
재현하지 않았다.** 이는 코드와 live schema로 뒷받침되는 위험이다.

보완은 기존 UID 중복·label coverage를 먼저 읽고, 게시 가능한 모든 node에 이미 공통으로
존재하는 label이 있는지도 전수 확인한 뒤, 현 identity 규칙을 충분히 덮는
유일성 제약과 publication transaction을 격리된 DB에서 검증하는 것이다. Neo4j 유일성
제약은 label/type 범위이므로 한 label에만 걸고 전역 보장이라고 말하면 안 된다.
`ontology_bundle_uid` 단독 유일성도 잘못이다: 한 bundle에 여러 node가 있다.
공통 label을 추가하는 선택은 기존 exact readback에 영향을 주므로 migration 설계에
포함해야 한다. `CREATE`를 무조건 `MERGE`로 바꾸는 것으로 완료되지 않는다. 공식 문서는
node 식별 속성의 uniqueness constraint와 concurrent MERGE의 경계를 설명한다.
[Neo4j constraints](https://neo4j.com/docs/cypher-manual/current/schema/constraints/create-constraints/),
[Neo4j MERGE](https://neo4j.com/docs/cypher-manual/current/clauses/merge/#query-merge-using-constraints).

**A7. 최신 bundle의 정확성이 참조 대상의 최신성을 보장하지 않는다.** live publisher의
`_assert_anchors`는 UID·이름·label을 검사하므로 A3의 offline RDF 문제와 같지 않다.
다만 anchor revision digest는 확인하지 않는다. 앞선 감사에서 최신 plan의 자체 내용은
정확했지만 adaptive anchor는 `EXACT_PREDECESSOR`였던 사실이 그 구별을 보여준다.
의미가 특정 revision에 의존하는 참조는 expected revision/digest를 선언하고 확인해야 한다.
역사를 가리키려는 참조는 그대로 역사 revision을 표시한다. 일괄 최신화는 수리가 아니다.
기존 anchor 입력 계약을 소급 변경하지 말고 새 profile 또는 병렬 reference 표현에서
revision 결속을 추가해야 한다.

## 3. 철학에 관한 앞선 결론을 더 엄격하게 제한한다

P1의 두 연결은 인류보편체와 철학 묶음에서 들어오는 `PROPOSED / SECONDARY_AI`
관계다. P3도 제안된 개념 연결을 포함한다. 이 연결은 내용의 조직화를 보여주지만
사용자 원문, 현행 구현 선택, 반증 관측까지 이어지는 경로를 보장하지 않는다.
`10/10`, `8/8`, 차수 `2~5`는 그 범위의 inventory 결과다.

철학적 함의를 점검할 다음 질의는 아래처럼 질문 자체를 명확하게 해야 한다.

| 질문 | 필요한 답과 오류 검출 |
|---|---|
| 이 명제의 어느 부분을 누가 말했는가? | 원문 revision·해당 구절·해석자를 구별. FCL-8의 사용자 법칙과 AI falsifier를 모두 USER_PRIMARY로 승격시키는 답을 검출 |
| 기억과 진실의 구별이 어디에 적용되는가? | 저장된 assertion, 그것의 지지/반박 evidence, 현재 판단과 적용 scope를 구별. 저장·HAS_SOURCE만으로 참이 되는 경로를 검출 |
| 재귀 합성이 구성원의 경계와 이탈을 보존하는가? | 제안된 계약·정의·구현·관측을 따로 반환. member/owner/authorizer 역할의 자동 동일시를 검출 |
| Wolfram 연결로 무엇을 추론할 수 있는가? | 관계 상태·국소 rewrite·계보라는 한정된 bridge와 비추론 항목 반환. physics 동일성·순서 독립성·효능으로의 승격을 검출 |
| 현재 설계는 무엇이고 무엇이 폐기됐는가? | schema-relative owner 정본과 fixed-role 역사 자료의 관계 반환. compatibility consumer와 새 canonical write selector를 별도 조사 |

검색에서 누락된 legacy 철학을 발견 가능한 projection으로 만드는 제안은 여전히 타당하다.
그러나 필드를 일괄 NORMAL로 채우거나 오래된 권위 필드를 무조건 현재 문자열에 복사하면
A2를 확대할 수 있다. 공개 범위·권위 mapping·supersession을 검토하고, 실제 MCP 질의의
정답 집합에 대해 누락과 부당한 승격을 함께 확인해야 한다. 이번에는 앞선 MCP 누락 관측을
참조했으며 서버 내부 filtering을 추가로 입증하지 않았다.

## 4. 공식 자료에서 확인한 보완 방법

**SHACL 1.0 + SPARQL 1.1:** SHACL은 선언한 target과 constraint에 대해서 검증한다.
따라서 `conforms=true`와 함께 예상 대상이 실제 검사됐는지도 기록하고, decision UID의
일치·권위 mapping·assertion 내부 ordinal 등 관계 조건을 명시해야 한다. 새 SHACL-SPARQL
기능을 선택하면 기존 Core qualification만으로 커버됐다고 하지 말고 선택한 기능을
검증한다. 이미 사용하는 read-only SPARQL 질의로 시작하는 것도 가능하다.
[SHACL targets](https://www.w3.org/TR/shacl/#targets),
[SPARQL 1.1](https://www.w3.org/TR/sparql11-query/).

**PROV-O + Web Annotation:** 파일 content, 특정 경로에 묶인 occurrence, 그것을 해석한
activity, 주장과 원문 구절을 구별한다. revision 관계에는 `prov:wasRevisionOf`를,
원문 구절 지정에는 immutable source와 TextQuoteSelector 등의 조합을 검토할 수 있다.
이는 HSWM에 적용할 제안이며 이 표준이 주장의 참이나 사용자 승인을 인증한다는 뜻이 아니다.
[PROV-O](https://www.w3.org/TR/prov-o/),
[Web Annotation Text Quote Selector](https://www.w3.org/TR/annotation-model/#text-quote-selector).

**RDF와 n-ary 표현:** 내용이 같다는 것과 경로별 binding이 같다는 것을 분리하고,
anchor 요구·participant 역할·scope를 projection 후에도 질의 가능하게 보존한다.
W3C n-ary 패턴은 관계 instance를 나타내는 참고 지침이며 Recommendation이 아닌
Working Group Note다. RDF 저장 형식 자체가 HSWM world model을 실현했다는 증거가 되지 않는다.
[RDF 1.1](https://www.w3.org/TR/rdf11-concepts/),
[n-ary relations Note](https://www.w3.org/TR/swbp-n-aryRelations/).

**품질 표시는 여러 차원으로:** 존재율, source 추적, authority 일관성, 현재 revision
해결, MCP 검색, 반례 거부를 따로 보고한다. 하나의 KG 크기나 shape pass 수로 합산하지
않는다. DQV는 이런 측정 metadata를 표현하는 참고 vocabulary지만 Working Group Note이고
품질 인증이 아니다. 새 의존성 설치 없이 기존 기록에서 시작할 수 있다.
[W3C DQV](https://www.w3.org/TR/vocab-dqv/).

## 5. 수리 우선순위와 완료 확인

| 순서 | 작은 변경 범위 | 완료를 확인할 방법 |
|---|---|---|
| 1 | 공통 projection의 A3 anchor 요구 보존·검사, A4 binding occurrence 분리 | 정상 multi-bundle은 유지되고 label 불일치는 거부; 동일 내용의 두 경로는 각각 보존되고 shape 통과. 의미 변경이면 새 compiler/profile revision을 사용 |
| 2 | plan/철학 역할 적용 범위와 A1·A2·A5 의미 조건 | 빈 domain target, 상충 authority, 잘못된 decision UID, authored→observed 전환을 각각 거부. 정당한 반복 target·다른 assertion의 같은 번호는 허용 |
| 3 | A6 DB identity 제약과 동시 publication | 격리 DB에서 같은 UID를 동시에 게시해도 중복 없음; 기존 exact·partial·collision 거부 동작 유지. 이후 live migration 범위 확정 |
| 4 | A7 참조 revision과 legacy discovery/derived RDF | 알려진 predecessor와 current를 구별; 철학 질의가 원문·해석·역사·관측을 구별하고 부당한 승격을 반환하지 않음 |

이들은 연구 기록을 정확히 읽고 교환하기 위한 수리다. canonical learning gate나 개인
governance 도구를 새로 만드는 계획이 아니다. HSWM 기전과 다음 경험 선택 연구를 대체하지 않는다.

이번에는 위 수리를 적용하지 않았다. 기존 ontology·과학 결과·live KG는 보존했고,
재현 프로그램·감사 자료만 추가했다. 전체 Python/effect-runtime suite 재실행 대신
이 경계의 실제 반례와 정상 대조를 실행했다.

```bash
uv run --locked --project _research/graph_standards/runtime --extra graph python _research/graph_standards/audit_philosophy_projection_adversarial.py
```

추가로 generic PROV는 원래 선언한 artifact digest를 표현할 뿐 실제 파일 검증을 보장하지
않고, `source_id`가 identity 입력인 현 deterministic profile에서 alias를 바꾸면 결과가
달라진다. 둘은 명시된 경계 안에서는 단독 결함으로 과장하지 않는다. RDFC 역시 이처럼
IRI·literal 자체가 다른 dataset을 같은 의미로 판정해 주지 않는다. canonicalization과
source 진위·인지적 동등성을 혼동하지 않는다.
[RDFC 1.0](https://www.w3.org/TR/rdf-canon/).
