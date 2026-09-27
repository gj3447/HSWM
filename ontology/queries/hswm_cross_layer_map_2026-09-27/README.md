# HSWM cross-layer Map 조회

이 snapshot은 2026-09-27 사용자 발화의 세 방향, 별도 `SECONDARY_AI` HSPINE 해석,
그리고 아직 실행하지 않은 매핑 연구 제안을 구분한다.

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle validate --source identity=ontology/identity/hswm_core/HSWM_CROSS_LAYER_MAP_ONTOLOGY.v1.json --profile v2 --shapes schemas/HSWM_KG_BUNDLE_RDF_PROJECTION_SHACL_1_0_V2.ttl
src/hswm/effect-runtime/bin/hswm-kg-bundle query --source identity=ontology/identity/hswm_core/HSWM_CROSS_LAYER_MAP_ONTOLOGY.v1.json --profile v2 --query ontology/queries/hswm_cross_layer_map_2026-09-27/user_direction.rq
```

조회는 `USER_PRIMARY`의 agent 위치, 뇌 모델링 층 선택, M = Map의 세 행만 반환한다.
HSPINE의 AI 작성 기록과 `EXPERIMENT_NOT_RUN` 연구 proposal은 이 조회에 섞이지 않는다.
