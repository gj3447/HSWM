# HSWM 연구 지도 생성 자료

[연구 설명](../../docs/research/HSWM_RESEARCH_MAP_2026-09-30.md)과
[조회 안내](../../ontology/queries/hswm_research_map_2026-09-30/README.md)를 위한 출처 결속 자료다.

- `curation.v1.json`: 9개 주제, 34개 선정 기록, 문장별 출처 위치·해석 범위·기존 의무 연결.
- `source-pins.v1.json`: 45개 기존 파일의 실제 bytes SHA-256·길이·Git revision.
- `build.mts`: 고정된 출처 확인 후 기존 bundle 형식으로 생성하는 로컬 Effect I/O와 순수 생성 함수.
- `verify.mts`: 기존 RDF·SHACL·SPARQL 엔진으로 출처·질문·거절 조건을 확인한다.

```sh
node _research/research_map_2026-09-30/build.mts
node _research/research_map_2026-09-30/verify.mts
```

source pin에 없는 working-tree 변경을 수집하거나 live KG·runtime store를 수정하지 않는다.
node와 관계의 수는 생성 결과이며 연구 품질이나 효능 지표가 아니다.
