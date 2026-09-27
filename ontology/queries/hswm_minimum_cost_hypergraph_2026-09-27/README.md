# HSWM 최소비용 하이퍼그래프 가설 조회

이 source-bound bundle은 사용자 원문의 강한 가설, `SECONDARY_AI`의 조건부 연구 가설,
문헌의 지지 범위와 제한, 현재 구현 계약 및 미해결 평가를 분리한다. 사용자 범주 3은
정의하지 않는다. RDF view는 읽기 전용이며 canonical state를 쓰지 않는다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source hypothesis=ontology/identity/hswm_core/HSWM_MINIMUM_COST_HYPERGRAPH_ONTOLOGY.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source hypothesis=ontology/identity/hswm_core/HSWM_MINIMUM_COST_HYPERGRAPH_ONTOLOGY.v1.json --profile v2 --query ontology/queries/hswm_minimum_cost_hypergraph_2026-09-27/user_conjecture.rq
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source hypothesis=ontology/identity/hswm_core/HSWM_MINIMUM_COST_HYPERGRAPH_ONTOLOGY.v1.json --profile v2 --query ontology/queries/hswm_minimum_cost_hypergraph_2026-09-27/literature_constraints.rq
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source hypothesis=ontology/identity/hswm_core/HSWM_MINIMUM_COST_HYPERGRAPH_ONTOLOGY.v1.json --profile v2 --query ontology/queries/hswm_minimum_cost_hypergraph_2026-09-27/engineering_gaps.rq
```

`user_conjecture`는 원문에 직접 연결된 최소비용 가설만 돌려준다. `literature_constraints`는
각 자료가 실제로 지지하는 범위와 확대하면 안 되는 결론을 나타낸다. `engineering_gaps`는
현재의 codec·MapSpec view fixture와 전체 비용·진단 연구의 미해결 범위를 함께 보여 준다.
W3C n-ary relations는 informative Working Group Note이며 Recommendation이 아니다.
