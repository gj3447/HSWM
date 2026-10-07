# CHU 운영체제·HSWM·AI 관점 조회

사용자 원문과 조건부 관점, AI 재서술, 참여 역할, HSPINE·KG 게시를 구분한다.

```sh
src/hswm/effect-runtime/bin/hswm-workspace show chu-os-ai
src/hswm/effect-runtime/bin/hswm-workspace query chu-os-ai statement
src/hswm/effect-runtime/bin/hswm-workspace query chu-os-ai roles
src/hswm/effect-runtime/bin/hswm-workspace query chu-os-ai publication
src/hswm/effect-runtime/bin/hswm-workspace validate chu-os-ai
src/hswm/effect-runtime/bin/hswm-workspace bindings chu-os-ai
```

- `statement`: 정확한 원문, 조건·귀결과 USER_PRIMARY 귀속, 별도 AI 재서술 1행.
- `roles`: 대상 / 작동 기전 / 귀결 / 발화 출처의 정확한 UID·역할·순서 4행.
- `publication`: HSPINE thread와 KG note의 실제 식별자·권위·readback 2행.

기존 v2 RDF/PROV-O projection과 SHACL 도구를 재사용한다.
원문 digest, UID 유일성, endpoint, 관계별 domain/range·권위·상태, 정확한 SPARQL
결과를 대조한다. 조건 제거·해석의 USER_PRIMARY 승격·역할 교환·효능 승격·출처 누락
변조는 SHACL이 거부해야 한다. 구조 검증은 이 철학적 관점의 참이나 구현 완료 증명이 아니다.

[관계 계약](../../../docs/canon/artifacts/chu_hswm_os_ai_2026-10-07/graph-contract.v1.json)과
[검증 결과](../../../docs/canon/artifacts/chu_hswm_os_ai_2026-10-07/validation.v1.json)에 정확한 비교 대상을 둔다.
`bindings`는 Git 추적 여부를 함께 보므로 새 파일이 추적되기 전에는 unavailable일 수 있다.
직접 파일 bytes와 SHA-256을 비교한 결과를 별도로 남긴다.

RDF 내보내기:

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle project --source chu-os-ai=ontology/identity/hswm_core/CHU_HSWM_OS_AI_ONTOLOGY.v1.json --profile v2 --output-dir .hswm-local/chu-os-ai-projection-new
```

정체성·역할을 한 claim/participation 구조로 보존한다. CHU와 HSWM의 `sameAs`를 만들지 않는다.
기존 CHU 개념 UID는 범위 snapshot의 anchor로 재사용하며, 새 대상 노드는 이번 주장의
‘HSWM으로 작동하는 CHU 운영체제’라는 한정된 지시 대상이다. AI 전체와 저장소 KG를 합치지 않는다.
