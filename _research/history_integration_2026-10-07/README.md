# HSWM 작업 이력 연결

HSWM Git 이력, SYMPOSIUM 분리 전후 자료, 관련 저장소의 HSWM 출처와 KG 원문
발생 위치를 연결하는 로컬 조회기다. 기존 지도·정전·실험 결과를 수정하지 않는다.
새로운 의미 해석이나 현재 판정의 정본이 아니라, 정확한 원문으로 돌아가는 탐색 투영이다.

공유 KG 진입점은 `sym:Note:chatgpt-hswm-history-integration-20261007`이다.
owner-managed Relay KG의 기존 draft writer로 저장하고 HSWM·저장소·USL·9월 16일
연구 진입점·9월 28일 정정 노트에 5개 `PROPOSED` 링크를 추가했다. 정확한 UID·권위·
원문 속성과 각 관계의 방향·종류·상태를 다시 읽어 확인했다. 이전 노드나 관계는 수정하지
않았다. 7월 25일 legacy session은 조회됐지만 writer가 `Target is not available`로
링크를 거절해, 로컬 관측과 본문 참조로 남겼다. 다른 경로로 쓰기를 우회하지 않았다.

2026-10-07 캡처에서 8개 저장소의 출처 5,062개, 선택한 경로의 변경 12,584건을
연결했다. HSWM 자체는 `c8b68108b3e5694b8d90a1b829cfb277fced3363`을 source cut으로
삼는다. 캡처한 branches/tags/remote-tracking refs에서 도달하는 HSWM 커밋은 884개이며
2026-07-19부터 2026-10-07까지다. stash와 reflog-only 객체는 이 수에 포함하지 않는다.
다른 저장소의 전체 commit DAG도 보존하므로 통합 3,264개를 전부 HSWM 작업이라고
해석하면 안 된다.

관련 소유자는 HSWM, SYMPOSIUM, CHU, USL, HSPINE, HSWM_LIKENESS,
ICE_ORCA_DRAGON, ORCA_SETTING이다. HSWM·HSWM_LIKENESS는 제외 규칙을 통과한
텍스트 자료 전체, 다른 저장소는 현재 경로나 내용에 `HSWM`이 나타나는 자료를
선택한다. 그 현재 경로와 과거 `HSWM` 경로의 변경을 추적한다. 문자열 선택은
의미 전체를 검토했다는 주장이 아니다.

## 지금 열기

이 작업환경의 [대화형 이력 지도](../../.hswm-local/history-integration-20261007/hswm-history.html)를
브라우저에서 연다. 서버·외부 CDN·모델 호출이 필요 없다. 출처 검색, 월별 커밋,
파일 변경·삭제 이력, KG UID별 원문 위치, 제한된 라이브 KG 관측과 끊어진 인용을 조회한다.
이 HTML과 통합 catalog에는 여러 소유자의 자료가 들어 있어 Git에서 제외한 로컬
디렉터리에 보관한다. 공개 저장소에는 조회기와 형식 계약만 둔다.

고정 Git 판본 밖에 있던 현재 파일 603개는 별도 working-copy snapshot에 추가했다.
수정·미추적 파일과 source cut 이후 바이트를 관측 시각·기준 cut·SHA-256으로 보존하고,
603개의 읽은 바이트를 내용 주소로 복사한 뒤 다시 해시 검증했다. 이 발생은 고정 Git
출처 5,062개와 합쳐 세지 않는다. HTML의 `현재 파일 관측`에서 조회한다.

```sh
node _research/history_integration_2026-10-07/cli.mts \
  .hswm-local/history-integration-20261007/snapshot-v4 overview

node _research/history_integration_2026-10-07/cli.mts \
  .hswm-local/history-integration-20261007/snapshot-v4 timeline HSWM 2026-08

node _research/history_integration_2026-10-07/cli.mts \
  .hswm-local/history-integration-20261007/snapshot-v4 search negative

node _research/history_integration_2026-10-07/cli.mts \
  .hswm-local/history-integration-20261007/snapshot-v4 path SYMPOSIUM HSWM/README.md

node _research/history_integration_2026-10-07/cli.mts \
  .hswm-local/history-integration-20261007/snapshot-v4 kg sym:Concept:hswm

node _research/history_integration_2026-10-07/cli.mts \
  .hswm-local/history-integration-20261007/snapshot-v4 read \
  .hswm-local/history-integration-20261007/local-v2.json \
  HSWM docs/canon/HSWM_CONSTITUTION_2026-08-20.md
```

`timeline REPO [TERM] [OFFSET] [LIMIT]`, `search TERM [OFFSET] [LIMIT]`,
`path REPO PATH [OFFSET] [LIMIT]`, `kg UID [OFFSET] [LIMIT]`, `gaps [OFFSET] [LIMIT]`는
총수와 `next_offset`을 반환한다. 디렉터리 인용은 `DIRECTORY_VIEW_AT_CAPTURED_CUT`으로 구분한다. 기본 50개, 최대 1,000개이며 생략을 감추지 않는다.
`search`는 제목·경로·UID·커밋 제목의 literal 검색이다. 본문 전체 의미 검색은 아니다.
`read CONFIG REPO PATH [BLOB_OID]`는 고정 Git object를 검증해 읽는다. 삭제된 파일은
`path`의 old/new OID를 명시하면 된다. 작업트리의 최신 바이트와 섞지 않는다.

`usl REPO PATH [KG_UID]`는 원문과 revision, 선택적으로 해당 원문에 실제로 등장하는
KG UID를 named-role 관계로 내보낸다. `kg://hswm-history-local/`은 로컬 논리적 ID이며
등록된 원격 서비스가 아니다. 기존 USL property-graph/v2 adapter에서 컴파일할 수 있다.
관측·resolver 접근·HSWM 실행·admission은 수행하지 않는다.

## 연결 계약

- `HAS_VIEW`: 통합 지도 → 선택 저장소의 탐색 view. 소유권 위임이 아니다.
- `HAS_SOURCE`: 저장소 view → 특정 source cut의 문서 occurrence. 여러 자료를 허용한다.
- `HAS_CONTENT`: 저장소 → 도달 가능한 commit, 또는 출처 → 동일 SHA-256 내용.
  각각 scope를 명시한다. 같은 바이트는 entity 동치나 인과적 이관을 뜻하지 않는다.
- `REFERENCES`: commit → parent(`GIT_PARENT_INDEX_n`), 출처 → 고정 commit,
  commit → 변경한 경로의 view, 출처 → 인용 출처, 원문 UID occurrence → 라이브 관측 view.
  scope로 의미를 구분한다. 변경 경로 view는 최신 파일 바이트가 과거 변경의
  preimage라는 뜻이 아니다. 정확한 old/new OID는 catalog에 있다.

모든 신규 노드의 해석 권위는 `SECONDARY_AI / PENDING_OR_PRELIMINARY`, 관계는
`PROPOSED`다. 인용·역사 참조를 실행 의존성이나 새 과학적 근거로 바꾸지 않는다.
기존 KG의 node·relation 객체는 source SHA와 JSON pointer를 유지한 채 별도 배열에
보존한다. 기존 n항 참여자·순서·상태를 이항 간선으로 덮어쓰지 않는다. RDF 탐색 graph는
그 원본 배열의 손실 있는 view다. 여러 snapshot의 동일 UID를 한 record로 합치지 않는다.

각 repository cut의 전체 Git tree 목록은 `inventory`, 출처 해시·원문 제목은 `sources`,
전체 commit DAG는 `commits`, 선택 경로의 첫 부모 diff는 `changes`다. merge의 다른 부모는
commit DAG에 남으며 diff는 첫 부모 기준이다. rename 유사도 판정은 하지 않고 삭제·추가를
그대로 보존한다. 같은 blob이 다른 경로에서 쓰인 경우 `path` 조회가 별도 연결을 보여 준다.

## 생성과 검증

기존 Node/Effect 환경과 build된 HSWM·USL 모듈을 사용한다. 새 라이브러리는 없다.
출처 scope와 실제 checkout root는 ignored local config에 둔다. config는
`recorded_at`, `repositories: [{id, root, cut, refs: [{name, oid}], worktree_status,
maximum_text_bytes?}]`, 선택적 `kg_snapshot`을 가진다. refs는 호출자가 먼저 확정한
commit OID이며 builder가 원격 fetch나 새로운 저장소 검색을 하지 않는다.
현재 HSWM의 9.8 MB 출처 archive까지 포함하도록 HSWM만 16 MiB, 다른 저장소는
8 MiB의 파일 읽기 상한을 사용한다. override의 최대값은 32 MiB다.

```sh
node _research/history_integration_2026-10-07/build.mts \
  PRIVATE_CONFIG NEW_SNAPSHOT_DIRECTORY
node _research/history_integration_2026-10-07/verify.mts \
  SNAPSHOT_DIRECTORY PRIVATE_CONFIG --record
node _research/history_integration_2026-10-07/render.mts \
  SNAPSHOT_DIRECTORY PRIVATE_CONFIG NEW_EXPLORER.html
```

현재 파일을 별도로 추가하려면 `worktree.mts capture PRIVATE_CONFIG NEW_DIRECTORY`를
실행한다. 이 단계는 source cut과 다른 파일과 미추적 파일만 읽고, 심링크·개인 도구 설정·
credential-looking 경로·상한 초과·읽는 중 바뀐 파일을 건너뛴다. `worktree.json`은
관측 목록과 생략 이유, `blobs/SHA256`은 정확한 바이트다.
`worktree.mts read DIRECTORY REPO PATH`는 복사한 바이트의 해시를 확인하고 읽는다.
render의 마지막 선택 인수로 이 디렉터리를 전달하면 고정 Git 자료와 구분해 표시한다.

새 snapshot만 생성하며 기존 산출물을 덮어쓰지 않는다. 동일 config의 기존 inventory를
재사용하려면 build 뒤에 `--from PREVIOUS_SNAPSHOT_DIRECTORY`를 붙인다. 재사용은
검증을 대신하지 않는다. manifest가 catalog/bundle/tooling을 결속하고, bundle의
`artifact_bindings`는 snapshot 디렉터리를 기준으로 `catalog.json`을 가리킨다.

`verify`는 모든 선택 출처 바이트, JSON pointer, 캡처 refs의 commit 집합, 선택 경로의
모든 diff, graph endpoint, SHACL 및 SPARQL의 실제 답을 대조한다. 중복 source,
없는 endpoint, 권위 승격을 거절하는 검사와 SYMPOSIUM 이관 원문·음성 결과 탐색·
정전 원문 복원·USL 컴파일 확인을 포함한다. `--record`를 빼면 읽기 전용이다.
RDF N-Quads gzip, descriptor, PROV-O JSON-LD, USL 예제와 검증 결과는 snapshot에 남는다.
기존 snapshot v1/v2/v3는 작업 중 산출물이다. 현재 최종 검증 대상은 v4다.

## 명시적으로 남기는 공백

라이브 KG는 조회 27건의 제한된 응답이며 전체 export가 아니다. UID 없는 이웃과
상한 50개에 닿은 조회, `RATIFIED`·`UNSPECIFIED` 등 기존 상태는 원래 응답 그대로
남긴다. API 검색 결과 없음은 부재나 삭제의 증거가 아니다.

고정 Git 색인에는 미커밋 파일의 상태만 기록하며, 후속 working-copy 관측은 별도 보존한다.
개인 대화 저장소·다른 호스트·ignored 실험 payload·
submodule 본문·symlink 대상·credential-looking 파일을 읽지 않는다. 아직 도달하지 못한
원격 자료까지 전부 연결됐다는 주장은 하지 않는다. 원문 내용 전체에 대한 의미 검토와
완전한 HSWM의 실현·효능 평가도 이 작업의 결과가 아니다.

특히 `sym:Concept:hswm`의 구형 definition과 8월 26일 single-owner 정정은 별도 출처로
남는다. 정정 노트 `sym:Note:chatgpt-hswm-graph-program-direction-20260928`을 함께 조회하며
옛 정의를 최신 정체성으로 자동 선택하지 않는다.
