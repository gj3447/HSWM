# HSWM CLI entry

작업에 해당하는 안내만 선택한다. 저장소 루트의 `src/hswm/effect-runtime/bin/` launcher를
사용하며, 설치본 `--help`와 아래 소유 문서를 대조한다. 버전 기준은
`src/hswm/effect-runtime/package.json`과 lockfile이다. 전체 README는 프로젝트 소개다.

| 작업 | CLI | 필요한 안내 |
|---|---|---|
| 내용·출처·규칙 조회, SPARQL, SHACL | `hswm-workspace` | [Workspace usage](#workspace-usage) |
| RDF/PROV-O 내보내기 | `hswm-kg-bundle` | [Bundle usage](#bundle-usage) |
| manifest 실행·학습·피드백 | `hswm-live` | [네이티브 실행 계약](../operations/HSWM_NATIVE_EFFECT_ADAPTIVE_RUNTIME_2026-09-08.md) |
| 선택적인 개발 실행·피드백 | `hswm-dev` | [자체 개발 사용법](../operations/HSWM_SELF_DEVELOPMENT_2026-09-08.md) |
| USL 참조·조건 preview | `hswm-usl` | [KG·작업환경 안내](../operations/HSWM_KG_WORKSPACE_2026-09-22.md)와 설치본 도움말 |

## Workspace usage

읽기용이다. 모델 호출·DB 변경·워크플로 실행을 수행하지 않는다.

```sh
src/hswm/effect-runtime/bin/hswm-workspace --help
src/hswm/effect-runtime/bin/hswm-workspace show optimization-rules
src/hswm/effect-runtime/bin/hswm-workspace query optimization-rules rules
src/hswm/effect-runtime/bin/hswm-workspace validate optimization-rules
src/hswm/effect-runtime/bin/hswm-workspace bindings optimization-rules
```

`show ID`에서 등록된 query 별칭과 shape를 확인한 뒤 `query ID QUERY`로 읽는다.
`validate`는 구조, `bindings`는 추적 파일 바이트의 hash를 확인한다. 다른 checkout은
`--checkout PATH`로 지정한다. `inventory --uid UID`는 번들별 발생 위치를 조회한다.
`--details`는 `inventory`에만 적용한다.

내용은 `navigate ID`에서 한 노드의 이웃을 보고, 외부 anchor를 명시적으로 따라가고,
선택한 노드의 원문을 읽는다. 전체 번들을 합치거나 전역 UID 검색을 자동 수행하지 않는다.

```sh
src/hswm/effect-runtime/bin/hswm-workspace navigate constitution
src/hswm/effect-runtime/bin/hswm-workspace follow constitution --uid sym:AbstractNode:hswm-constitution-activation
src/hswm/effect-runtime/bin/hswm-workspace read constitution-activation --uid sym:AbstractNode:hswm-constitution-activation
```

- `navigate ID [--uid UID]`: 기본 UID는 bundle UID다. bundle UID가 로컬 node가 아닌
  역사 자료는 실제 node UID를 명시한다. 간선 방향·원래 상태·권위와 endpoint 지위를 분리한다.
- `follow ID --uid UID`: 해당 entry의 `anchor_routes`에 명시된 외부 anchor 하나를
  목적지 bundle의 SHA-256·UID·required labels로 확인한다. `next`의 entry/uid/sha256으로
  다음 읽기를 이어간다. 명시되지 않은 경로·SOURCE_ONLY 목적지는 거절한다.
- `read ID --uid UID`: node의 `source_path/source_sha256`과 bundle artifact binding이
  일치하는 UTF-8 원문 전체를 읽는다. source fragment는 안내이며 본문을 잘라 주지 않는다.
- 세 명령의 `--sha256 SHA`는 앞서 관측한 **현재 entry bundle**의 판본을 고정한다.
  후속 source/target 바이트가 달라지면 실패하며 과거 pin을 갱신하지 않는다.
- `navigate/follow`의 `--offset N` 기본값은 0, `--limit N`은 16(1–50)이다.
  `complete=false`이면 같은 판본과 `nextOffset`으로 나머지를 읽는다.
- `--max-bytes N`은 반환 JSON의 UTF-8 바이트 예산이다. 기본 65,536, 범위
  1,024–1,048,576. 초과하면 실패하며 잘린 원문을 성공으로 반환하지 않는다.

현재 entry 선언과 선택한 bundle만 읽는다. `follow`만 목적지 bundle 하나를 추가로 읽고,
`read`만 선택한 원문 파일을 추가로 읽는다. 다른 source의 payload나 workflow는 실행하지 않는다.
구문·판본·참조·출처·경로·예산 오류는 기존 process refusal로 nonzero 종료한다.
이 도구의 탐색 성공은 실행 문맥의 충분성·native 학습 성공과 별도다.

## Bundle usage

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle --help
src/hswm/effect-runtime/bin/hswm-kg-bundle project --source rules=ontology/identity/hswm_core/HSWM_OPTIMIZATION_RULES_ONTOLOGY.v1.json --profile v2 --output-dir .hswm-local/optimization-rules-new
```

`--output-dir`은 새 디렉터리여야 한다. `query --source ID=PATH --query FILE`과
`validate --source ID=PATH --shapes FILE`을 지원한다. `--source`는 반복 가능하며
기존 내용 번들은 v2 profile을 사용한다. 로컬 projection은 실행 중인 AI 상태의 write 경로가 아니다.
