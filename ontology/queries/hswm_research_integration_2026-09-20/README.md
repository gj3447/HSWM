# HSWM 연구 통합 그래프 조회

루트 UID: `sym:AbstractNode:hswm-research-integration-2026-09-20`.

- `claims_and_obligations.rq`: 연구 제안·원본 출처·한계·다음 의무, 기대 12행.
- `observations.rq`: DGX 조건별 원래 라벨 일치·토큰·상태, 기대 5행. Brier는 원래 라벨 일치 기준이며 역할 교환의 correctness calibration이 아니다.
- `coverage.rq`: source/claim/observation/occurrence별 노드 수.
- `unsupported_claims.rq`: 근거 없는 구조화 주장, 기대 0행.

```sh
npm --prefix src/hswm/effect-runtime run build
node _research/research_graph_integration_v1/build.mts
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source research=ontology/development/HSWM_RESEARCH_INTEGRATION_2026-09-20.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source research=ontology/development/HSWM_RESEARCH_INTEGRATION_2026-09-20.v1.json --profile v2 --shapes schemas/HSWM_RESEARCH_INTEGRATION_SHACL_2026-09-20.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source research=ontology/development/HSWM_RESEARCH_INTEGRATION_2026-09-20.v1.json --profile v2 --query ontology/queries/hswm_research_integration_2026-09-20/claims_and_obligations.rq
```

그래프 build는 고정된 공개 catalog와 합성 관측만 읽는다. private 연구 DB나 모델 endpoint에 접속하지 않는다. source manifest는 당시 범위를 고정한 snapshot이며 현재 파일 추가분을 자동으로 포함하지 않는다.

live KG에서는 다음 Cypher로 각 주장과 검증 의무를 조회할 수 있다.

```cypher
MATCH (c {ontology_bundle_uid:'sym:AbstractNode:hswm-research-integration-2026-09-20',
          standard_graph_role:'RESEARCH_PROPOSAL'})-[:DERIVED_FROM]->(s),
      (c)-[:RELATES_TO]->(q {standard_graph_role:'OPEN_OBLIGATION'})
RETURN c.name, c.description, c.limitation, s.source_ref, q.description
ORDER BY c.name
```

RDF export는 read-only 파생물이다. live publication은 별도 registry·collision·anchor·readback 검증을 가진 기존 publisher로 수행하며, 기존 정전이나 사용자 기록은 수정하지 않는다.
