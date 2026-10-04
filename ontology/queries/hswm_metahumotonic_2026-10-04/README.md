# HSWM metahumotonic 정의와 연구 조회

[사용자 정의](../../../docs/canon/USER_PRIMARY_HSWM_METAHUMOTONIC_IDEA_2026-10-04.md)와
[연구 적용](../../../docs/research/HSWM_CAVE_METAHUMOTONIC_RESEARCH_2026-10-04.md)을 읽고 다음을 실행한다.
기존 설치된 TypeScript/Effect 조회 도구를 사용한다.

```sh
src/hswm/effect-runtime/bin/hswm-workspace show metahumotonic
src/hswm/effect-runtime/bin/hswm-workspace validate metahumotonic
src/hswm/effect-runtime/bin/hswm-workspace bindings metahumotonic
src/hswm/effect-runtime/bin/hswm-workspace query metahumotonic user-claims
src/hswm/effect-runtime/bin/hswm-workspace query metahumotonic identity-roles
src/hswm/effect-runtime/bin/hswm-workspace query metahumotonic literature
src/hswm/effect-runtime/bin/hswm-workspace query metahumotonic applications
src/hswm/effect-runtime/bin/hswm-workspace query metahumotonic evaluation
src/hswm/effect-runtime/bin/hswm-workspace query metahumotonic violations
```

질문은 순서대로 사용자 주장 2개, 한정된 명명의 역할 3개, 출처 검토 8개,
구현 계약에 연결한 가설 4개, 미실행 평가 4개, 위반 0개를 반환해야 한다.
정확한 UID 집합은 [계약](../../../docs/research/artifacts/hswm_metahumotonic_2026-10-04/graph-contract.v1.json)에 있다.
행 수만 같아서는 충분하지 않다. 구조 검사와 원문 바이트 비교도 별도다.
새 파일을 Git이 아직 추적하지 않으면 workspace bindings는 읽지 않으므로 직접 SHA 비교가 필요하다.

RDF와 PROV-O JSON-LD를 새 디렉터리에 내보내려면:

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle project --source metahumotonic=ontology/identity/hswm_core/HSWM_METAHUMOTONIC_IDEA_ONTOLOGY.v1.json --profile v2 --output-dir .hswm-local/metahumotonic-projection-new
```

생성물은 `dataset.nq`, `descriptor.json`, `provenance.jsonld`다.
이 projection은 출처 artifact의 바이트 본문과 실행 중 canonical state를 포함하지 않으며 쓰기 경로가 없다.
기존 철학 UID는 `identity-roles` 결과의 `legacyUid` 문자열로 반환한다.
옛 철학 설명의 사용자 비준, 개념의 무조건적 동일성, 현재 구현의 완성이나 효능을 추론하지 않는다.
