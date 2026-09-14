# Semantic Weight 정의와 표현 정리 조회

저장소 루트에서 기존 TypeScript/Effect KG 도구로 조회한다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source definition=ontology/identity/hswm_core/HSWM_SEMANTIC_WEIGHT_DEFINITION_ONTOLOGY.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source definition=ontology/identity/hswm_core/HSWM_SEMANTIC_WEIGHT_DEFINITION_ONTOLOGY.v1.json --profile v2 --query ontology/queries/hswm_semantic_weight_definition_2026-09-14/theorems_and_scopes.rq
```

`theorems_and_scopes.rq`는 named theorem 22개를 각각 정확한 source/SHA와 모델 범위에 연결한다.
기존 RDF 1.1 projection·SHACL·SPARQL을 사용하며, relation vocabulary는 HSWM의 로컬 어휘다.
[Lean 검증 기록](../../../_research/semantic_weight_definition_v1/lean-verification.v1.json)과
[연구 설명](../../../docs/research/HSWM_SEMANTIC_WEIGHT_DEFINITION_AND_HYPERGRAPH_2026-09-14.md)을 함께 읽는다.
구조 검증과 정리 조회는 현실 학습 효능이나 CR/FCL 통과의 판정이 아니다.
