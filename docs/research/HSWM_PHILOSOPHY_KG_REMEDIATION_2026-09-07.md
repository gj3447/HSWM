# HSWM 철학 KG 수리 후속 기록

**상태:** `SECONDARY_AI / ENGINEERING_REMEDIATION_APPLIED / BOUNDED_LIVE_READBACK_VERIFIED`.

이 기록은 [적대적 검토](HSWM_PHILOSOPHY_KG_ADVERSARIAL_REVIEW_2026-09-07.md)의 원본과 실행 기록을 바꾸지 않는 후속이다. HSWM의 목표 정체성, FCL-1..8, 그리고 철학적 연결이 현재의 학습·효능·의식 증거가 아니라는 경계는 그대로다. 이번 변화는 bundle projection이 선언한 관계를 덜 잃고 잘못된 연결을 더 이르게 거부하게 만든 공학적 수리다. KG, SHACL 통과, UID 제약, provenance가 HSWM cognition, canonical admission, Permit, 사용자 비준, 과학적 지지를 뜻하지 않는다.

## 적용한 local 수리

| 항목 | 수리와 확인 범위 |
|---|---|
| A1 | [선택된 source revision의 role inventory](../../src/hswm/infrastructure/kg_bundle_semantics.py)를 v2 compiler가 확인한다. 알려진 plan에서 역할을 `UNCLASSIFIED`로 바꾸거나 역할 수를 줄여 domain target을 피하는 경로는 거부한다. |
| A2 | v2는 `authority_class`와 `ontology_authority_class_v1`의 불일치, claim의 존재하지 않거나 맞지 않는 `current_decision_uid`, authored scene의 관측 결과 승격을 거부한다. unknown bundle에는 채워진 조건부 필드의 정합성만 적용하며, legacy 권위를 현재 권위로 임의 통일하지 않는다. |
| A3 | [v2 graph compiler](../../src/hswm/infrastructure/kg_bundle_graph_view.py)는 같은 projection 안에서 cross-bundle anchor의 `required_labels`가 소유 node labels의 부분집합인지 확인한다. 유효한 선언은 bundle별 `AnchorReference` occurrence로 target·name·required labels를 보존한다. |
| A4 | 같은 content SHA의 경로별 binding은 content entity와 bundle/path별 binding occurrence로 분리한다. 따라서 같은 내용의 두 경로가 하나의 `ArtifactBinding`으로 합쳐지지 않는다. |
| A5 | 한 `LEARNING_ASSERTION` 아래 participation ordinal은 유일해야 한다. 이는 role enumeration 계약이며 시간·인과 순서를 증명하는 규칙이 아니다. |

기본 projection은 `hswm-kg-bundle-rdf-projection/v2`다. hash-bound v1 shape와 historical source bytes는 변경하지 않았다. `profile="v1"`은 명시적으로만 사용할 수 있고, [회귀 테스트](../../tests/test_kg_bundle_graph_view.py)는 v2 이전 source commit `3aff4b38a2611da84688e451da438a6bb6c0c79d`에서 동결한 N-Quads SHA-256와 byte 동등성을 확인한다. v2 shape는 [별도 파일](../../schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl)에 있으며, v1 shape를 소급 수정하지 않는다.

A1·A2·A5의 source-revision 선택 검사는 [semantic module](../../src/hswm/infrastructure/kg_bundle_semantics.py)와 [그 테스트](../../tests/test_kg_bundle_semantics.py)에, A3·A4·v1/v2 profile 경계는 [graph-view 테스트](../../tests/test_kg_bundle_graph_view.py)에 있다. Hypergraph plan의 binding, n-ary participation, domain SHACL은 [plan projection 테스트](../../tests/test_fractal_learning_plan_projection.py)가 계속 확인한다.

## publication과 revision 경계

A6에는 [UID-kind constraint와 registry transaction serialization](../../src/hswm/infrastructure/kg_publication_integrity.py)을 publisher의 단일 write transaction 앞에 연결했다. 이는 publish하려는 UID kind별 Neo4j uniqueness constraint가 존재할 때만 진행하고, registry lock으로 같은 publisher 경로의 transaction을 직렬화하는 local 구현이다. label/type 범위의 Neo4j constraint가 전체 KG의 전역 UID 정체성을 자동 증명하지 않으며, historic exact readback의 labels를 바꾸는 migration도 아니다.

A7에는 source의 artifact binding이 실제로 소유 ontology를 지정할 때 live anchor의 bundle UID와 raw projection digest를 확인하는 경로를 추가했다. legacy 소유 bundle에는 bundle identity만 추가 확인하며, raw revision digest는 추정하지 않는다. 소유 source가 결속되지 않은 anchor는 `UNPINNED_NO_BOUND_OWNER`로 반환한다. 따라서 legacy 철학 bundle의 참조 최신성이나 전체 철학 MCP/discovery coverage가 수리되었다고 주장할 수 없다.

## local validation

focused root run은 10 test files에서 **87 passed, disposable-only 3 skipped**였다. 여기에는 v2의 cross-bundle label mismatch 거부, anchor descriptor 보존, same-digest/different-path binding 분리, closure decision-pointer mutation 거부, known role inventory 변이 거부, 그리고 explicit v1 byte compatibility가 포함된다. 이 수치는 해당 local 경계의 검사 결과이며 live KG 상태, publication 성공, 철학의 참·효능을 뜻하지 않는다.

## live 적용과 독립 확인

구현 commit은 `2fc01c81057a8d361b2fae4f609985a1de07fede`다.
[격리 Neo4j CI](https://github.com/gj3447/HSWM/actions/runs/34082173038)에서 Python publication 검증 **11 passed**(동시 게시·충돌·제약 부재를 포함), Effect live integration **1 passed**, bounded projection의 SHACL·적용·exact readback·rebuild가 통과했다. Neo4j는 기존 CI가 digest로 고정한 `2026.02.3-community` 이미지다.

그 뒤 실제 KG를 다음 범위로 수리했다. 접속 정보와 무관한 KG 내용은 기록하지 않은 [운영 확인 JSON](../../_research/graph_standards/results/HSWM_PHILOSOPHY_KG_REMEDIATION_READBACK_2026-09-07.json)에 source digest, 이전 snapshot digest, 제약 목록과 readback을 보존했다. 이는 routine engineering 기록이며 새 과학 결과 receipt가 아니다.

| 대상 | 적용·확인 결과 |
|---|---|
| UID 제약 | HSWM bundle node의 UID kind 15종 모두 해당 label을 이미 보유함을 확인. `SchemaRegistry`를 더한 16종에 `uid IS UNIQUE`를 추가. 전체 UID 중복 group은 전·후 모두 0. `ontology_bundle_uid`에 유일성 제약을 걸지 않음. |
| Adaptive strategy | exact predecessor **34 nodes / 161 relations**를 기존에 검토된 정본 **35 / 170**으로 migration. 기존 migration 계약에 따라 node 34개 metadata 갱신·1개 추가, relation 4개 교체 삭제·157개 갱신·13개 추가. 정본 파일 SHA는 `b44c13a76724f545c492a36b5a32cf02339f6fa89846aae5ec218de14d1e6cbb`. |
| Hypergraph plan | **63 / 247 exact**, 생성 0. modern raw digest anchor 2개·legacy bundle identity 1개 확인. HSWM root와 FCL-1..8의 9개 참조는 revision 미결속으로 명시. |
| Workshop C1–C3 | **29 / 107 exact**, 생성 0. plan에 결속된 anchor 8개 모두 raw digest 확인. 작성된 사례라는 지위 유지. |
| Registry | transaction 잠금의 임시 속성이 제거되고 최종 label·속성 digest가 전후 동일함을 확인. |

제약은 기존 UID-kind label 범위이며, 그 label을 생략하는 다른 writer까지 전역으로 보호하지 않는다. 관계 동시성은 이 공통 publisher와 수리한 adaptive publisher가 같은 registry transaction lock을 사용한다는 범위에서 검증했다. 현재 코드가 사용한 임시 속성 write-lock 방식은 [Neo4j 동시 접근 공식 문서](https://neo4j.com/docs/operations-manual/current/database-internals/concurrent-data-access/)의 transaction lock 패턴에 따른다.

전체 저장소 [CI](https://github.com/gj3447/HSWM/actions/runs/34082173007)는 이 기록 작성 시 진행 중이므로 전체 통과로 보고하지 않는다. 기존 CI의 RDFLib 환경 누락과 sdist shape 목록 누락도 함께 수정했으며, graph tests는 locked graph 환경에서 수행하도록 이동했다.

## 표준과 별도 연구 메모

이 수리는 SHACL target이 실제로 존재해야 constraint가 적용된다는 [W3C SHACL 1.0](https://www.w3.org/TR/shacl/#targets), source·derivation와 주장 진실을 구분하는 [PROV-O](https://www.w3.org/TR/prov-o/), 관계 occurrence를 보존하는 [RDF n-ary relations Note](https://www.w3.org/TR/swbp-n-aryRelations/), 그리고 label/type 범위 constraint의 [Neo4j 공식 문서](https://neo4j.com/docs/cypher-manual/current/schema/constraints/create-constraints/)에 맞춘다. 이 표준들은 위 공학적 표현·검증 범위를 설명할 뿐 HSWM 기전을 승인하지 않는다.

저장소와 접근 가능한 live KG의 문자열·문자열 배열 속성을 읽어 검색했을 때, USL의 유의미한 일치는 PROM-16 병렬 처리 관련 Gunther의 **Universal Scalability Law** 기록(`sym:AbstractNode:finding-prom16-parallelism-a2-7a3f9c2d`)이었다. 이 결과는 **read-only**이며 개발 프로젝트를 식별한 결과가 아니다. 개발 중인 project의 정식 이름과 repository path가 아직 식별되지 않았으므로, 이 문서는 USL을 HSWM 설계·성능·효능의 근거로 연결하지 않는다. 식별 정보와 source binding이 생긴 뒤에만 별도 기록에서 검토한다.


후속 확인: USL은 SYMPOSIUM의 **유니버셜 시멘틱 링크**이며 정전 UID는 `sym:Concept:usl`이다. 새로 확인한 게시 영수증 시각은 2026-09-07 04:42:30 UTC로, 앞선 04:24 재조회 이후다. 앞선 raw fallback의 별칭 배열 타입 판별 오류도 확인했으나, 이를 게시 전 USL 미식별의 원인으로 단정하지 않는다. [HSWM 연결 설계와 온톨로지](HSWM_USL_SEMANTIC_ENGINEERING_BRIDGE_2026-09-07.md)에 출처·시각·제안 범위를 구별해 후속 정리했다.
