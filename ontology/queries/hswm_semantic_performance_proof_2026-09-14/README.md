# 문헌·기전·조건부 성능 증명 조회

저장소 루트에서 기존 TypeScript/Effect RDF 1.1 projection·SHACL·SPARQL 도구로 실행한다.
관계 어휘는 HSWM 로컬 어휘이며 외부 표준 어휘로 승격하지 않는다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source performance=ontology/identity/hswm_core/HSWM_SEMANTIC_PERFORMANCE_PROOF_ONTOLOGY.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source performance=ontology/identity/hswm_core/HSWM_SEMANTIC_PERFORMANCE_PROOF_ONTOLOGY.v1.json --profile v2 --query ontology/queries/hswm_semantic_performance_proof_2026-09-14/theorems_and_scopes.rq
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source performance=ontology/identity/hswm_core/HSWM_SEMANTIC_PERFORMANCE_PROOF_ONTOLOGY.v1.json --profile v2 --query ontology/queries/hswm_semantic_performance_proof_2026-09-14/observations_and_transfer.rq
```

첫 질의는 새 public 정리 39개와 정확한 source/SHA·범위를 반환한다.
둘째 질의는 1차 출처 6개를 관측·한계·후보 기전에 연결한다. `MOTIVATES_ONLY`는
논문 관측이 Lean 공리나 HSWM 효능 증거로 바뀌지 않는다는 연결이다.

[연구 설명](../../../docs/research/HSWM_LITERATURE_TO_PERFORMANCE_PROOF_2026-09-14.md), [Lean 검증 기록](../../../_research/semantic_performance_proof_v1/lean-verification.v1.json),
[출처 지도](../../../_research/semantic_performance_proof_v1/source-map.v1.json)를 함께 읽는다.
구조 적합성과 조회 성공은 외부 outcome 진실성, 인과 credit 또는 HSWM 완성 판정이 아니다.
