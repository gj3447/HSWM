# 상태·국소 LLM 연산자·필수 비교 대상 조회

[정전](../../../docs/canon/USER_PRIMARY_HSWM_STATE_LOCAL_OPERATOR_HYPERON_2026-09-14.md)의 사용자 진술을 조회한다.
저장소 루트에서 이미 빌드된 TypeScript/Effect CLI를 사용한다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source identity=ontology/identity/hswm_core/HSWM_STATE_LOCAL_OPERATOR_HYPERON_ONTOLOGY.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source identity=ontology/identity/hswm_core/HSWM_STATE_LOCAL_OPERATOR_HYPERON_ONTOLOGY.v1.json --profile v2 --query ontology/queries/hswm_state_local_operator_hyperon_2026-09-14/state_operator.rq
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source identity=ontology/identity/hswm_core/HSWM_STATE_LOCAL_OPERATOR_HYPERON_ONTOLOGY.v1.json --profile v2 --query ontology/queries/hswm_state_local_operator_hyperon_2026-09-14/core_comparator.rq
```

첫 조회는 `state`, `local-input`, `operator`의 `USER_PRIMARY` 3행,
둘째는 `MANDATORY_CORE_COMPARATOR`인 Hyperon 개념 UID의 `USER_PRIMARY` 1행을 반환해야 한다.
원문 발췌·경로·SHA를 함께 반환한다. HSWM의 로컬 typed vocabulary를 기존 RDF 1.1 projection으로
조회하며, source-map의 owner snapshot과 anchor를 대조한다. 문서·그래프 검증은 인지 효능 검증이 아니다.
