# HSWM research atlas — 2026-10-02

[한국어 연구 지도](../../docs/research/HSWM_RESEARCH_ATLAS_2026-10-02.md)에서 13개 주제와
157개 주 연구 문서의 요약을 읽는다. 이 디렉터리는 그 지도와 같은 curation을 사용하는
국소 조회기, 고정 원문 catalog, 출처별 ontology UID index와 재현 도구를 담는다.

## 원문과 해석

원문은 Git cut `a7272a13cd6d304b7f8a1911dca0158e0bc67f29`에 고정한다. 모든 tracked
파일 5,005개의 path, blob OID, SHA-256, bytes를 보존한다. 직접 `docs/research/*.md`
157개에는 개별 AI 요약·자료 역할·원문 상태·한계·locator·복수 topic 배치가 있다.
정전, 보조 연구, 운영, 결과, 역사, 실험 메모, Lean과 ontology를 포함한 764개에는
구조 색인이 있다. 나머지 파일은 inventory와 정확한 full-text read의 대상이다.

`curation-{a,b,c}.v1.json`은 cut 뒤의 `SECONDARY_AI` 해석이다. 이를 원문 cut 안에
있던 데이터로 취급하지 않는다. 생성기·조회기·검증기·curation·query·shape의 현재
바이트는 새 bundle의 artifact bindings에 별도로 묶고, 실행한 native toolchain은
검증 receipt에 별도로 기록한다. 이전 atlas/map과 원문은 덮어쓰지 않는다.

Unicode 원문 경로는 그대로 둔다. Native v2의 artifact path 문자 제약에 맞지 않는
경로는 `catalog.v1.json`의 SHA binding을 거쳐 원문의 SHA/bytes/Git blob에 연결된다.
조회기는 실제 Git 원문을 읽고 해시를 확인한다. worktree의 수정본을 섞지 않는다.

## 조회

저장소 root에서 기존 로컬 Node/Effect 환경으로 실행한다. 새 의존성은 없다.

```bash
node _research/research_atlas_2026-10-02/cli.mts overview
node _research/research_atlas_2026-10-02/cli.mts topic constructive_realizability_and_proof
node _research/research_atlas_2026-10-02/cli.mts search HSWM_LEAN_VALIDATION_REVIEW
node _research/research_atlas_2026-10-02/cli.mts context - proof HSWM_LEAN_VALIDATION_REVIEW 10000
node _research/research_atlas_2026-10-02/cli.mts show docs/research/HSWM_LEAN_VALIDATION_REVIEW_2026-09-28.md
node _research/research_atlas_2026-10-02/cli.mts read docs/research/HSWM_LEAN_VALIDATION_REVIEW_2026-09-28.md full
node _research/research_atlas_2026-10-02/cli.mts gaps
```

`show`의 section ID를 `read PATH SECTION_ID`에 전달하면 정확한 UTF-8 바이트 범위의
절을 읽는다. ATX Markdown heading을 색인하며 fenced code의 heading은 제외한다.
상위 절은 하위 절을 포함한다. Setext heading이나 전체 Markdown AST를 구현하지 않는다.
Lean/JSON은 full read를 제공한다. binary 원문은 UTF-8 text read 대상이 아니다.

`context TOPIC|- FACET|- QUERY|- BYTES`는 전체 요약 item을 모으는 명시적 선택이다.
budget은 JSON `items`의 UTF-8 바이트 예산이며 응답 envelope나 모델 token 수가 아니다.
초과하면 `NEEDS_NARROWING`과 필요한 bytes를 반환하고 items는 비워 둔다. 원문을
자동으로 활성화하지 않는다. query는 대소문자 무시 literal token conjunction이다.

`entities UID [SOURCE_PATH]`는 239개 ontology JSON의 `nodes` 배열에서 수집한 13,226개
node occurrence를 찾는다. 여러 source에 같은 UID가 있으면 source 선택을 요구한다.
선택한 노드는 source SHA와 JSON pointer를 확인해 반환한다. source 밖 관계/anchor,
live KG, 또는 임의 JSON 객체의 모든 ID를 색인한 것은 아니다.

## 역할과 표준 projection

`MAP_BINDING`은 topic, research unit, original source의 세 참여 역할을 가진다.
context facets와 ordering은 배치의 속성이다. 같은 문서를 여러 관점에 배치해도
원문·증거·권위는 복제하거나 승격하지 않는다. 요약은 `SUMMARIZES`로 원문에 연결된다.
topic view는 기존 13개 topic identity를 anchor로 참조한다.

새 graph는 1,258 nodes, 13 anchors, 3,173 relations의 native v2 projection이다.
RDF N-Quads, SHACL Core, SPARQL과 PROV-O JSON-LD는 기존 도구를 그대로 쓴다.
[질의·shape 계약](../../ontology/queries/hswm_research_atlas_2026-10-02/README.md)에
각 predicate, 참여 역할, 8개 질의와 검증 책임을 적었다.

q5는 764개 indexed source의 집계다. q7의 `CITES`는 그 문서들 사이 1,257 file pair만
나타내며 fragment 차이 2건을 합친다. catalog는 명시적 inline Markdown local-link
추출 결과를 fragment와 함께 보존한다. resolved 1,995건 중 indexed corpus 밖 artifact로
향하는 736건은 catalog에 남고 `read PATH full`로 접근한다. target이 cut에 없는 59건은
`gaps`에서 확인한다. reference-style link, HTML link와 code-path 의미 분석은 범위 밖이다.
이 인용들은 support·dependency·과학적 참 판정이 아니다.

## 생성과 검증

```bash
node _research/research_atlas_2026-10-02/build.mts --write
node _research/research_atlas_2026-10-02/verify.mts
src/hswm/effect-runtime/bin/hswm-workspace show research-atlas-1002
src/hswm/effect-runtime/bin/hswm-workspace query research-atlas-1002 q3-formal
src/hswm/effect-runtime/bin/hswm-workspace validate research-atlas-1002
```

`build --write`는 catalog/entities/bundle과 13개 주제 page를 생성한다. 일반 `verify`는
읽기 전용이며 fixed-cut source 바이트, 생성물 일치, 전체 주 연구 curation, section,
entity pointer, CLI 원문 복귀, native/local SHACL, 8개 질의, 거부해야 할 변이와
4개 고정 retrieval 사례를 확인한다. 저장된 exports가 있으면 재생성 바이트와 대조한다.

새 artifact directory가 없을 때만 `verify.mts --record`로 RDF gzip, descriptor,
provenance, validation receipt를 최초 기록한다. 이미 발표된 receipt를 갱신하는
명령이 아니다. 후속 연구 cut은 새 날짜·버전으로 만든다.

workspace bindings는 active checkout과 역사적 해시를 비교한다. 이번 작업으로 바뀐
`ontology/workspace/HSWM_WORKSPACE.v1.json` 등의 `WORKTREE_DIFFERS`는 고정 cut과의
차이이며 이를 숨기려고 옛 해시를 갱신하지 않는다. 원문 revision은 atlas catalog와
SOURCE_VIEW의 `source_revision`에서 확인한다.

4개 고정 retrieval 사례는 원문 복귀와 예산 처리를 검증한다. 사용자 질의 분포에서의
의미 검색 품질, 학습된 W, HSWM 실행 효과 또는 Lean 증명을 새로 측정한 결과는 아니다.
