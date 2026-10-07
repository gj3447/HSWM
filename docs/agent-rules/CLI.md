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
전체 구문: `hswm-workspace <status|doctor|inventory|show ID|bindings ID|validate ID|query ID QUERY>`.
`--uid`와 `--details`는 `inventory`에만 적용한다.

## Bundle usage

```sh
src/hswm/effect-runtime/bin/hswm-kg-bundle --help
src/hswm/effect-runtime/bin/hswm-kg-bundle project --source rules=ontology/identity/hswm_core/HSWM_OPTIMIZATION_RULES_ONTOLOGY.v1.json --profile v2 --output-dir .hswm-local/optimization-rules-new
```

`--output-dir`은 새 디렉터리여야 한다. `query --source ID=PATH --query FILE`과
`validate --source ID=PATH --shapes FILE`을 지원한다. `--source`는 반복 가능하며
기존 내용 번들은 v2 profile을 사용한다. 로컬 projection은 실행 중인 AI 상태의 write 경로가 아니다.
