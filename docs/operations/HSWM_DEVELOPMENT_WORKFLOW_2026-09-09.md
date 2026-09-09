# HSWM 개발 작업 흐름

2026-09-09 · `SECONDARY_AI / LOCAL_ENGINEERING_GUIDE`.

이 문서는 [이전 환경 점검](HSWM_DEVELOPMENT_ENVIRONMENT_2026-09-09.md)에 이어 적용한
개발 명령, 환경 분리, 선택적 실행 추적, 백업 방법의 현재 안내다.
HSWM 목표는 [헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)의 하나의 token-native
LLM-function macro-neural network다. 이번 변경은 그 개발을 돕는 도구와 관측 경로다.
canonical atom 소유권, admission, 인과 credit, 학습 성공 기준은 바꾸지 않는다.
검사 통과와 개발 피드백은 HSWM의 과학적 효능 증거가 아니다.

## 준비와 일상 개발

현재 고정 버전은 Node `24.13.0`, npm `11.6.2`, uv `0.12.3`, CPython `3.12.13`,
TypeScript `5.9.3`, Effect `3.22.1`이다. 기존 lockfile의 패키지를 업그레이드하지 않았고,
선택적 관측에 필요한 공식 SDK만 정확한 버전과 integrity로 추가했다.
새 checkout은 위 인터프리터와 CLI가 준비되어 있어야 한다.

```sh
src/hswm/development/bin/hswm-python sync
npm --prefix src/hswm/effect-runtime ci --ignore-scripts --no-audit --no-fund
npm --prefix src/hswm/effect-runtime run build

# 편집 중 빠른 확인
npm --prefix src/hswm/effect-runtime run test:watch
npm --prefix src/hswm/effect-runtime run test:changed

# 변경 완료 후 해당 범위의 검사와 빌드
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime run test -- --maxWorkers=2
npm --prefix src/hswm/effect-runtime run build
```

`test:changed`는 Git 변경과 Vitest의 의존 관계 분석을 활용한다.
검사가 없는 변경에서는 종료 코드가 0이 아닐 수 있으며, 동적 파일 읽기·외부 입력으로
연결되는 검사까지 모두 찾는다는 뜻은 아니다. 필요한 전체 검사는 계속 실행한다.
[공식 Vitest changed 설정](https://vitest.dev/config/changed)과
[watch CLI](https://vitest.dev/guide/cli)를 따른다.

`.vscode/settings.json`은 설치된 workspace TypeScript와 core Python을 선택한다.
VS Code에서 TypeScript 선택 안내가 나오면 **Use Workspace Version**을 선택한다.
[공식 Effect language-service 안내](https://github.com/Effect-TS/language-service#installation)에
따라 이미 고정된 `@effect/language-service@0.23.3`을 사용한다. editor 플러그인의 진단은
`tsc` 실행과 별개이며 기존 Effect 경계 검사를 대체하지 않는다. 현재 머신에는 editor UI가
없으므로 설정 파일을 검증했으며 실제 UI 활성화까지 확인한 것은 아니다.
`.vscode/tasks.json`에는 환경 준비, Effect 검사, changed 검사, watch 작업이 있다.

## Python 환경을 목적별로 분리

| 명령 | 환경 | 잠금과 동작 |
| --- | --- | --- |
| `hswm-python core COMMAND...` | `.hswm-local/envs/core` | 루트 `uv.lock` + dev extra, 실행 시 `--no-sync` |
| `hswm-python graph COMMAND...` | `_research/graph_standards/runtime/.venv` | graph runtime `uv.lock` + graph extra, 실행 시 `--no-sync` |
| `hswm-python infra fabric` | uv script 환경 | 기존 fabric smoke의 PEP 723 `.py.lock` |
| `hswm-python infra phoenix` | uv script 환경 | 기존 Phoenix viewer smoke의 PEP 723 `.py.lock` |

저장소 launcher의 전체 경로는 `src/hswm/development/bin/hswm-python`이다.
이 머신에는 checkout을 가리키는 `~/.local/bin/hswm-python`도 설치했다.
`sync`는 core와 graph만 정확히 동기화하며 기존 루트 `.venv`의 연구 도구는 보존한다.
외부에서 설정한 `UV_PROJECT_ENVIRONMENT`가 환경 선택을 바꾸지 못한다.
환경이 없으면 실행이 실패하고 `sync`를 안내하므로 전역 Python으로 조용히 넘어가지 않는다.
infra smoke는 실제 로컬 서비스에 접속하며 자동 준비 작업에서는 실행하지 않는다.
[uv 환경 설정](https://docs.astral.sh/uv/concepts/projects/config/)과
[script lock 안내](https://docs.astral.sh/uv/guides/scripts/)를 기준으로 구현했다.

```sh
hswm-python core pytest -q tests/test_hswm_python_environments.py
hswm-python graph pytest -q tests/test_graph_standard_tooling.py
```

## HSWM을 통한 개발 기록

활성 profile은 `adaptive_hswm_development.v3.json`이다. Python 검사 명령만 위 환경으로
전환하고 기존 검사항목을 유지했다. v2 파일과 과거 로컬 기록은 보존하며 v3 graph identity로
변경된 명령의 새 개발 관측을 구분한다.

```sh
hswm-dev hswm plan --focus runtime
hswm-dev hswm run --focus runtime --task '변경한 native runtime 검증'
hswm-dev hswm status
hswm-dev hswm feedback --episode <ID> --success true \
  --source 'agent(codex): 변경 범위의 검사 선택과 결과 확인에 유용했음'
```

focus는 `runtime`, `usl`, `ontology`, `docs` 중 변경에 맞게 선택한다.
검사 exit code를 자동으로 유용성 feedback에 연결하지 않는다. `agent(...)` 출처는 실제
사용자 판단과 다르다. 선택된 검사 밖에 필요한 검증이 있으면 별도로 실행한다.

## 선택적 Effect 실행 추적

기본값은 비활성이며 exporter나 네트워크 호출을 만들지 않는다.
활성화하려면 `--otel-endpoint` 또는 `HSWM_OTLP_TRACES_ENDPOINT`를 명시한다.
현재 경계는 `http://127.0.0.1:<port>/v1/traces`만 허용한다. 원격 수집이나 canonical
provenance 연결이 필요하면 별도의 경계 검토가 필요하다.

```sh
# 실행 전에 collector에 맞는 token을 로컬 환경으로 준비한다.
# token 값은 CLI 인자로 넣거나 저장소에 기록하지 않는다.
hswm-dev hswm run --focus runtime --task '실행 경로 관측' \
  --otel-endpoint http://127.0.0.1:6006/v1/traces
```

인증값은 `HSWM_OTLP_BEARER_TOKEN`에서 읽는다. 다른 변수명은
`--otel-token-env VARIABLE_NAME`으로 선택한다. token 자체를 받는 인자는 없다.
기존 `OTEL_EXPORTER_OTLP` 또는 `OTEL_EXPORTER_OTLP_*` 환경변수가 있으면 활성화를
거부한다. SDK가 기존 exporter 설정을 섞지 않도록 전용 실행 환경에서 해당 변수를
제거하고 `HSWM_OTLP_*`만 설정한다. `OTEL_RESOURCE_*` 값도 resource에 가져오지 않는다.
episode와 leaf 실행의 부모·자식 span, 식별자·설정·출력의 SHA-256, 실행 상태와 시간만
보낸다. task, prompt, 응답 본문, 명령 인자, 예외 메시지·stack, 임의 event·link는 exporter
투영에서 제외한다. digest는 암호화가 아니므로 관측 저장소도 private로 다룬다.
성공 판단·reward·canonical `traceRef`를 만들거나 피드백에 연결하지 않는다.

공식 Effect/OpenTelemetry SDK와 OTLP protobuf HTTP exporter를 사용한다.
export/shutdown timeout은 500ms, queue는 256개, batch는 64개로 제한한다.
수집기 장애가 끝난 작업의 결과를 바꾸지 않는지 별도로 검증한다.
[Effect tracing](https://effect.website/docs/v3/observability/tracing)을 따르며
정확한 패키지·라이선스·출처는
[telemetry-source-pins.v1.json](artifacts/development_environment_2026-09-09/telemetry-source-pins.v1.json)에 있다.

기존 Phoenix의 HTTP 포트는 6006이지만 이번 시작 시도는 gRPC 4317의 기존 프로세스와
충돌했다. 관련 없는 프로세스를 종료하지 않았다. 따라서 Phoenix 실서비스 수신은 아직
검증되지 않았다. 테스트용 수집기 및 SDK 검증 결과와 운영 서버 연결 여부를 구분한다.

## SQLite 백업과 복원

`hswm-backup`은 Node `24.13.0`의 [SQLite online backup API](https://nodejs.org/download/release/v24.13.0/docs/api/sqlite.html)를
사용한다. [SQLite 공식 안내](https://sqlite.org/backup.html)에 따라 WAL을 가진 실행 중
DB 파일을 단순 복사하지 않고 일관된 완료 snapshot을 만든다.
이 Node API의 experimental 지위는 그대로다.

```sh
# 예시: source와 destination의 부모 디렉터리는 private 0700이어야 한다.
# 모든 경로는 절대 경로이고 destination은 새 파일이어야 한다.
hswm-backup backup --source /private/state/runtime.sqlite3 \
  --destination /private/backups/snapshot.sqlite3
hswm-backup verify --backup /private/backups/snapshot.sqlite3
hswm-backup restore --backup /private/backups/snapshot.sqlite3 \
  --destination /private/restore/runtime.sqlite3
```

checkout launcher는 `src/hswm/effect-runtime/bin/hswm-backup`이고, 이 머신에는
`~/.local/bin/hswm-backup`도 설치했다. DB와 `.hswm-backup.json` sidecar를 한 쌍으로
보관한다. 백업은 0400, 복원 파일은 쓰기 가능한 0600이며 기존 파일을 덮어쓰지 않는다.
검증은 SHA-256, byte length, SQLite integrity check, schema와 논리 상태 fingerprint를
확인한다. 현재 파일 크기 상한은 512 MiB다. hash와 sidecar는 변조 탐지용이고 서명이나
독립적 신뢰 증명은 아니다. 여러 DB의 snapshot은 각각 일관되지만 DB 전체를 아우르는
원자적 snapshot은 아니다.

복제할 때는 완료된 백업과 sidecar를 함께 복사한 뒤 대상 저장소에서 다시 `verify`한다.
기존 state 경로에 복원하지 말고 새 경로로 복원해 확인한다. 도구는 stale lease를 정리하거나
실행 중인 CLI를 멈추지 않는다. 운영 전환은 별도 작업이다.
로컬 실제 snapshot·NFS 복제·복원 검증의 상세 경로와 기록은 ignored
`.hswm-local/environment-improvements-2026-09-09/`에 보관한다.
이 작업은 수동 snapshot이며 자동 주기 백업 스케줄을 설치하지 않는다.

## Dev Container와 검증 범위

선택적 [Dev Container](HSWM_DEV_CONTAINER_2026-09-09.md)에는 Linux amd64 image digest,
Node·uv archive checksum, 비특권 개발 사용자, checkout별 private volume을 적용했다.
현재 호스트에는 container engine과 필수 rootless helper가 없어서 실제 build는 미검증이다.
컨테이너 없이 이 호스트의 native 개발 환경을 사용할 수 있다.

이 변경의 검증 결과와 source-bound KG snapshot은
[환경 개선 snapshot](../../ontology/infrastructure/HSWM_DEVELOPMENT_WORKFLOW_2026-09-09.v1.json)에
기록한다. private DB, token, 원문 출력은 공개 KG에 포함하지 않는다.

2026-09-09 검증 결과는 다음과 같다. 서로 겹치는 검사 수는 합산하지 않는다.

| 범위 | 결과 |
| --- | --- |
| TypeScript·Effect 경계·함수형 검사 | 통과, allowlist 증가 없음 |
| 전체 native runtime | 957개 통과, 기존 외부 통합 검사 7개 skip |
| 새 telemetry 검사 | 5개 통과, 실제 SDK 오류·환경변수 redaction 포함 |
| SQLite snapshot 검사 | live WAL의 앞선 commit 포함·이후 commit 제외, 변조·덮어쓰기 거부, 새 프로세스 복원 쓰기 통과 |
| Python wrapper / graph 검사 | 각각 6개 / 88개 통과 |
| `hswm-dev` v3 runtime / usl / ontology / docs | 각각 52 / 19 / 9 / 333개 통과, 명시적 `agent(codex):...` 피드백 기록 |
| OTLP 실제 전송 | 임시 loopback HTTP collector가 bearer 인증과 protobuf 해독, 2개 span의 부모 관계·본문 제외 확인 |
| 실제 DB 복구 | 14개 로컬 snapshot과 14개 NFS 복제 검증, 현재 개발 DB를 새 경로로 복원하고 읽기·쓰기 확인 |
| watch / changed | 실제 focused 검사 실행 확인 |
| 빌드 / 패키징 / Markdown | 일반·DNRD 빌드, package dry-run, portable math 처리 통과 |

NFS는 별도 mount의 저장소이며 물리적 장애 도메인의 독립성까지 검증한 것은 아니다.
백업 대상 DB의 부모 디렉터리 네 곳은 private 0700으로 정리했다.
첫 백업 시도에서 발견한 WAL sidecar 문제는 완료본을 DELETE journal mode로 정규화하여
해결했다. 앞선 시도는 실패 맥락과 함께 로컬에 보존했고 NFS로 복제하지 않았다.
