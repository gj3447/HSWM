# HSWM 연구 지도 조회와 재현

이 지도는 2026-09-30에 선정한 연구 기록을 원문·기존 의무에 연결한 로컬 projection이다.
루트 UID는 `sym:AbstractNode:hswm-research-map-2026-09-30`이다.
요약 권위는 `SECONDARY_AI`, 관계 상태는 `PROPOSED`이며 current canonical state를 쓰지 않는다.

| 질문 | 파일 | 확인하는 답 |
| --- | --- | --- |
| 어떤 연구 축이 있는가 | [Q1](q1.rq) | 9개 주제와 주제별 선정 기록 수 |
| 각 주장은 무슨 종류이고 어디서 왔는가 | [Q2](q2.rq) | 34개 기록의 본문·종류·파일·원문 위치·해시·권위·범위 |
| 실패와 제한 결과는 무엇인가 | [Q3](q3.rq) | 6개 음성 또는 한계 관측, 사건 날짜와 주장 범위 |
| CR와 FCL의 원래 의무와 상태는 무엇인가 | [Q4](q4.rq) | 16개 원래 UID·역사적 상태·시점·참조 상태 |
| 아직 제안이나 질문인 것은 무엇인가 | [Q5](q5.rq) | 4개 미해결 질문과 2개 미실행 제안 |
| 출처 연결이나 해시가 빠진 주장이 있는가 | [Q6](q6.rq) | 정상 지도에서 0행; 출처 edge 제거 시 해당 주장 반환 |
| 다자 관계의 역할과 순서가 보존되는가 | [Q7](q7.rq) | 의미 학습 결과의 subject·source·3개 obligation slot과 `PROPOSED` edge 상태 |
| Hyperon 비교의 식별과 한계는 무엇인가 | [Q8](q8.rq) | 과거 component version·commit·비교 범위 1행 |

Q2의 요약은 인용문이 아니다. 사용자 원문은 summary의 `REFERENCES`와 `original` slot을
따라간다. Q4의 `historicalStatus`는 원래 source 날짜의 값이며 최신 완료 판정이 아니다.
Q7의 ordinal은 주장 관계의 slot 순서이며 실험 사건의 시간 순서를 뜻하지 않는다.

준비된 Node 환경과 기존 native graph build를 사용한다.
새 DB·네트워크·모델·Python 환경은 필요하지 않다.

```sh
node _research/research_map_2026-09-30/build.mts
node _research/research_map_2026-09-30/verify.mts
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source research=ontology/development/HSWM_RESEARCH_MAP_2026-09-30.v1.json --profile v2 --query ontology/queries/hswm_research_map_2026-09-30/q2.rq
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source research=ontology/development/HSWM_RESEARCH_MAP_2026-09-30.v1.json --profile v2 --shapes ontology/queries/hswm_research_map_2026-09-30/shapes.ttl
```

표준 N-Quads와 PROV JSON-LD를 원하는 새 디렉터리로 내보낼 수 있다.
이미 존재하는 출력 파일을 자동 교체하는 명령이 아니다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle project --source research=ontology/development/HSWM_RESEARCH_MAP_2026-09-30.v1.json --profile v2 --output-dir /tmp/hswm-research-map-export
```

기존 [v2 SHACL](../../../schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl)과
[이 지도 shape](shapes.ttl)를 verifier가 모두 실행한다. UID·endpoint·source byte·
slot cardinality·ordinal·권위 경계와 질문별 실제 답을 검사한다.
출처 없는 주장, USER_PRIMARY 승격, 의무 완료 위조, edge 상태 승격,
중복 UID·ordinal, 없는 endpoint를 넣은 거절 검사도 수행한다.

출처 pin이 달라지면 새 hash로 자동 갱신하지 않는다. 저장된 source revision에서 재현하거나
새 snapshot을 작성한다. 검증은 구조·추적성에 한정되며 실제 모델 효능이나 Lean replay를
수행하지 않는다. 전체 설명과 predicate 계약은 [연구 지도](../../../docs/research/HSWM_RESEARCH_MAP_2026-09-30.md)에 있다.
