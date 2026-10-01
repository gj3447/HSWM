# HSWM whole map — 2026-10-01

이 디렉터리는 [전체 내용 지도](../../docs/research/HSWM_WHOLE_MAP_2026-10-01.md)의 입력·생성·검증 경로다.
`instruction-routing`과 `kg-ontology`의 출처·권위·표준 그래프 규칙을 적용했다.
기존 native v2 compiler를 재사용하며 새 라이브러리나 live graph가 필요하지 않다.

조사 대상 corpus의 고정 source cut은 `df687475622e0a251a6c0c9124a9f3c92c0b42f3`이다.
전체 재현에는 이 커밋과 **이 지도 배포 커밋의 별도 SHA-bound curation·generator·query 입력**이 함께 필요하다.
새 additions JSON, build/verify, shape/query는 post-cut 작성물이며 고정 corpus 4,983개에 포함되지 않는다.
`artifact_bindings`는 그 입력 해시를, 검증 receipt의 `toolchain`은 실제 사용한 compiler 바이트와 lockfile 해시를 기록한다.
source cut 하나만 checkout하면 새 지도를 생성할 수 있다는 뜻이 아니다.
`git ls-tree`와 `git cat-file --batch`로 그 커밋의 모든 blob 경로 4,983개를 읽고 Git object ID와
SHA-256을 검증한다. 현재 작업트리의 수정·미추적 파일은 출처 바이트에 섞지 않는다.
`corpus.v1.json`에는 경로, mode, Git blob OID, SHA-256, 바이트 수, 물리 영역, disposition을 둔다.
각 경로는 선별 출처 `CURATED_SOURCE` 또는 `INVENTORIED_ONLY` 하나에 속한다.
전체 목록의 완전성과 모든 파일 내용의 의미 검토는 서로 다른 주장이다.

9/13의 13 topic·26 질문, 9/30의 34 연구 기록·16 CR/FCL 의무를 역사 참조로 유지하고,
`research-additions.v1.json` 13개와 `runtime-additions.v1.json` 10개를 별도로 연결한다.
선별 출처 90개만 path-at-cut/content node로 투영한다. 파일 전체를 KG node로 만들지 않는다.
같은 바이트는 content UID 하나를 공유하며, 경로 occurrence는 별도 UID를 가진다.
`anchor_resolutions`는 정확한 UID의 선택된 출처와 모든 로컬 발생 경로를 남긴다.
`OWNED_NODE`와 구형 `BUNDLE_UID_DECLARATION`을 구분하고, live 존재나 전역 유일성을 추정하지 않는다.

## 관계 계약과 손실 경계

| 관계 | 출발 → 도착 | 의미 |
| --- | --- | --- |
| `HAS_CONCEPT` | map → topic reference / corpus coverage | 이 지도에 속한 탐색 항목 |
| `HAS_CONTENT` | path-at-cut → artifact content | 고정 커밋의 정확한 바이트 |
| `DERIVED_FROM` | 추가 설명·역사 참조·질문·topic → path-at-cut | 요약 또는 참조의 근거 파일 |
| `ABOUT` | 추가 설명·역사 참조·질문·의무 → topic reference | AI가 정한 탐색 연결; 동치·정본 분해 아님 |
| `HAS_SOURCE` | topic reference → path-at-cut | 9/13 registry의 읽기 진입점 |
| `REFERENCES` | map / topic / 설명 / 의무 / 출처 → anchor 또는 path | 기존 식별자·역사 지도·보조 근거 참조 |

모든 새 노드·관계의 해석 권위는 `SECONDARY_AI`, 관계 상태는 `PROPOSED`다.
원문 권위는 원래 문서·anchor에 남는다. 이 관계들은 실행 의존성·허가·인과 효과가 아니다.
9/30의 역할/순서 있는 n항 참여 구조는 해당 원본 graph와 UID를 통해 되돌아간다.
여기의 간단한 탐색 reference는 그 실행 의미를 전부 표현하지 않는다.

## 사용법

기존 Node/Effect runtime 의존성과 `src/hswm/effect-runtime/dist/`가 준비된 checkout에서 실행한다.
생성기는 pure `construct`와 Effect에 감싼 Git/file I/O를 구별한다.

```sh
# 현재 날짜 산출물을 명시적으로 생성한다. 과거 snapshot 생성기는 실행하지 않는다.
node _research/whole_map_2026-10-01/build.mts --write

# 읽기 전용: source cut, bundle/corpus, SHACL 2종, 질문 8개, 변조 9종을 검증한다.
node _research/whole_map_2026-10-01/verify.mts

# 최초 receipt/export 작성에만 사용한다. 이미 존재하는 artifact 디렉터리는 거절한다.
node _research/whole_map_2026-10-01/verify.mts --record

src/hswm/effect-runtime/bin/hswm-workspace query whole-map-1001 q2-new-records
src/hswm/effect-runtime/bin/hswm-workspace query whole-map-1001 q7-corpus-coverage
```

검증 receipt와 RDF dataset/descriptor/PROV JSON-LD는
[`docs/research/artifacts/hswm_whole_map_2026-10-01/`](../../docs/research/artifacts/hswm_whole_map_2026-10-01/)에 있다.
기본 verifier는 기존 export 바이트·해시도 비교하며 기록 시각을 갱신하지 않는다.
source pin이 현재 작업트리와 다르면 workspace의 `bindings`에 차이가 나타날 수 있다.
strict v2 bundle의 source cut은 각 노드의 `source_revision`과 corpus에 있다.
현재 workspace의 top-level `sourceCut` 표시는 `null`일 수 있으므로 그 필드를 cut 부재로 해석하지 않는다.
재현 검증의 근거는 위 Git cut이며, 역사 해시를 현재 파일에 맞추어 고치지 않는다.

이 검증은 모델 실행, Lean 재실행, 배포 확인, 과학적 효능 판정을 포함하지 않는다.
