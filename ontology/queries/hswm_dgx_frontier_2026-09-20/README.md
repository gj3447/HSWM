# DGX 연구 그래프 조회

Bundle: `sym:AbstractNode:hswm-dgx-frontier-research-2026-09-20`.

- `candidates.rq`: 공식 후보, 정확한 revision/license, 남은 검증 의무. 기대 9행.
- `observations.rq`: v2/v3 여섯 조건의 정답·형식 유효성. 기대 12행. v1에는 유효 비교가 없어서 run 실패로만 남는다.
- `unsupported_claims.rq`: 출처 없는 구조화 주장. 기대 0행.

```sh
node _research/dgx_semantic_learning_v1/graph.mts
src/hswm/effect-runtime/bin/hswm-kg-bundle project --source dgx=ontology/development/HSWM_DGX_FRONTIER_RESEARCH_2026-09-20.v1.json --profile v2 --output-dir NEW_PROJECTION_DIRECTORY
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source dgx=ontology/development/HSWM_DGX_FRONTIER_RESEARCH_2026-09-20.v1.json --profile v2 --shapes schemas/HSWM_DGX_FRONTIER_SHACL_2026-09-20.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source dgx=ontology/development/HSWM_DGX_FRONTIER_RESEARCH_2026-09-20.v1.json --profile v2 --query ontology/queries/hswm_dgx_frontier_2026-09-20/candidates.rq
```

기본 RDF projection SHACL과 `HSWM_RESEARCH_INTEGRATION_SHACL_2026-09-20.ttl`도 함께 검증한다. proposal은 candidate/source/qualification 세 ordered participation으로, 관측은 experiment/evidence/identity-boundary 세 participation으로 표현한다. 이는 n-ary 연구 설명을 잃지 않는 투영이며 HSWM의 실행 상태 자체가 아니다.
