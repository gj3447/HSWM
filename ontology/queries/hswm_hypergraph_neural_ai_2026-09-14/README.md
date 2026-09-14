# HSWM 기본 정체성 조회

[정체성 snapshot](../../identity/hswm_core/HSWM_HYPERGRAPH_NEURAL_AI_IDENTITY_ONTOLOGY.v1.json)은
14개 node, 기존 개념의 9개 anchor, 30개 typed relation을 포함한다.
[사용자 원문과 설명](../../../docs/canon/USER_PRIMARY_HSWM_HYPERGRAPH_NEURAL_AI_2026-09-14.md)을
기존 HSWM 정체성에 연결하며, 새 독립 시스템을 정의하지 않는다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source identity=ontology/identity/hswm_core/HSWM_HYPERGRAPH_NEURAL_AI_IDENTITY_ONTOLOGY.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source identity=ontology/identity/hswm_core/HSWM_HYPERGRAPH_NEURAL_AI_IDENTITY_ONTOLOGY.v1.json --profile v2 --query ontology/queries/hswm_hypergraph_neural_ai_2026-09-14/basic_identity.rq
```

조회는 **하나의 AI / 하이퍼그래프 신경망 / LLM 기본 계산 / Semantic Weight 작동**의
4개 행과 각 진술의 `USER_PRIMARY` 권위, 원문 발췌, source path와 SHA-256을 반환한다.
상세한 작동 해석은 별도의 `SECONDARY_AI` node로 연결되어 있다.

관계 이름은 HSWM의 typed vocabulary이며 RDF 1.1·SHACL·SPARQL은 이를 교환·검증·조회하는
기존 표준 도구다. 이 checked-in projection은 현재 구현·과학적 판정을 변경하지 않는다.
