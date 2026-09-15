# 다음 증명 연구 — 출처에서 다음 작업으로

[연구 계획](../../../docs/research/HSWM_NEXT_PROOF_RESEARCH_2026-09-15.md)의 문헌·가정·다음 작업을 기존 RDF 1.1 projection과 SPARQL로 조회한다. HSWM 관계 어휘는 로컬 어휘다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source next=ontology/development/HSWM_NEXT_PROOF_RESEARCH_2026-09-15.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source next=ontology/development/HSWM_NEXT_PROOF_RESEARCH_2026-09-15.v1.json --profile v2 --query ontology/queries/hswm_next_proof_research_2026-09-15/sources_to_next_work.rq
```

문헌의 수학 정리와 실험적 제안은 `evidenceKind`, HSWM 전이 한계는 `limit`에 둔다. N1–N6은 제안이며 Lean으로 새로 검증된 정리가 아니다. 기존 source-bound CR/FCL anchors를 참조하고 그 상태를 변경하지 않는다. 구조 검증은 문헌의 참, 실모델 효능, 전체 HSWM의 증명이 아니다.
