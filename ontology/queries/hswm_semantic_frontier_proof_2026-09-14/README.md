# 추가 증명과 남은 범위 조회

기존 RDF 1.1 projection·SHACL·SPARQL 도구를 저장소 루트에서 실행한다.
로컬 관계 어휘는 HSWM 어휘이며 외부 표준으로 승격하지 않는다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source frontier=ontology/identity/hswm_core/HSWM_SEMANTIC_FRONTIER_PROOF_ONTOLOGY.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source frontier=ontology/identity/hswm_core/HSWM_SEMANTIC_FRONTIER_PROOF_ONTOLOGY.v1.json --profile v2 --query ontology/queries/hswm_semantic_frontier_proof_2026-09-14/theorems_and_scopes.rq
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source frontier=ontology/identity/hswm_core/HSWM_SEMANTIC_FRONTIER_PROOF_ONTOLOGY.v1.json --profile v2 --query ontology/queries/hswm_semantic_frontier_proof_2026-09-14/gaps_and_limits.rq
```

첫 질의는 새 public 정리 72개를 정확한 source/SHA와 범위에 연결한다.
둘째는 관계 생성·상관·피드백·합성·통합의 5개 부분 결과와 남은 전이 의무를 반환한다.
[설명](../../../docs/research/HSWM_SEMANTIC_FRONTIER_PROOFS_2026-09-14.md), [Lean audit](../../../_research/semantic_frontier_proof_v1/lean-verification.v1.json),
[출처](../../../_research/semantic_frontier_proof_v1/source-map.v1.json)를 함께 읽는다.
구조 검증과 정리 조회는 현실 LLM 효능, 인과 credit 또는 CR/FCL 통과 판정이 아니다.
