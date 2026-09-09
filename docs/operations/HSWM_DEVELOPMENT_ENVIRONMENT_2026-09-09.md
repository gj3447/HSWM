# HSWM 개발 환경 안내

2026-09-09 · `SECONDARY_AI / LOCAL_ENGINEERING_GUIDE`.

이 문서는 HSWM의 현재 TypeScript/Effect 개발 경로와 범위별 Python 검증을 재현하기 위한
실용 환경 안내다. 이 환경, 통과한 검사, 로컬 상태는 HSWM의 canonical admission, causal
credit, continuous learning 효능 또는 과학적 성공을 뜻하지 않는다. 목표 정체성과 주장 한계는
[헌법](../canon/HSWM_CONSTITUTION_2026-08-20.md)을 따른다.

기존 스냅샷과 과거 Python 흐름은 보존한다. 특히
[`HSWM_SELF_DEVELOPMENT_2026-09-08.md`](HSWM_SELF_DEVELOPMENT_2026-09-08.md)의
`uv run hswm-dev` 예시는 당시 흐름의 기록이다. 현재 활성 CLI는 Python console entry가 아니라
이 저장소의 native launcher다.

## 현재 기준과 출처

| 도구 | 이 체크아웃의 기준 | 잠금·출처·라이선스 |
| --- | --- | --- |
| Node.js | `24.13.0` | CI가 executable SHA-256까지 확인하는 [공식 Node 24.13.0 SQLite 문서](https://nodejs.org/download/release/v24.13.0/docs/api/sqlite.html)의 런타임. MIT 및 배포물 고지. |
| npm | `11.6.2` | `src/hswm/effect-runtime/package.json`의 `packageManager`와 CI가 고정한다. [공식 npm ci 문서](https://docs.npmjs.com/cli/v11/commands/npm-ci/)의 npm CLI이며 Artistic-2.0. |
| uv | `0.12.3` | CI의 graph acceptance 경로가 정확한 버전을 확인한다. [공식 uv sync 문서](https://docs.astral.sh/uv/concepts/projects/sync/)와 uv의 MIT 또는 Apache-2.0 라이선스. |
| Python | root `.venv`는 CPython `3.12.13`; CI core는 `3.11`, graph/acceptance는 `3.12.13` | CPython은 PSF License. 정확한 scorer 실행 파일은 CI SHA-256 pin을 따른다. 두 `uv.lock`은 Python 의존 패키지 버전·배포물 hash를 고정하며, 인터프리터 자체의 pin은 아니다. |
| Effect | `3.22.1` | `src/hswm/effect-runtime/package-lock.json` integrity가 고정한다. [공식 Effect resource-management 문서](https://effect.website/docs/resource-management/introduction/)의 라이브러리, MIT. |

이 체크아웃에서는 Node/npm/uv와 root `.venv`의 Python 3.12.13이 위 기준에 맞는다.
관리형 Python 3.11.15도 설치되어 있다. 다른 Python 버전의 CI 재현에는
`UV_PROJECT_ENVIRONMENT=.hswm-local/python311`과 `--python 3.11.15`를 함께 지정해
현재 `.venv`를 교체하지 않는다.
새 패키지는 기본 개발을 위해 필요하지 않다. 외부 도구·표준 도입은 `AGENTS.md`의
standard-first, source pin, license 기록 규칙을 먼저 따른다.

## 처음 준비하거나 기존 체크아웃을 정리할 때

저장소 루트에서 실행한다.

```sh
# 이 기존 checkout의 graph/observability/Temporal 도구를 유지한다.
uv sync --locked --extra dev --inexact

# graph 검증은 root 환경에 섞지 않고 전용 runtime에 준비한다.
uv sync --project _research/graph_standards/runtime --locked --extra graph

# active native runtime
npm --prefix src/hswm/effect-runtime ci --ignore-scripts --no-audit --no-fund
npm --prefix src/hswm/effect-runtime run build
```

주의: 현재 root에서 `uv sync --locked --extra dev --dry-run`은 이미 설치된 graph,
observability, Temporal 관련 패키지 33개를 제거하겠다고 표시한다. 이 체크아웃에서는 위의
`--inexact`를 사용한다. 깨끗한 새 clone에서 필요한 범위만 설치하는 경우에는 그 상태를
확인한 뒤 일반 locked sync를 선택할 수 있다.

`npm ci`와 build 뒤에는 다음 native launcher를 사용한다. repository-local `bin` launcher는
빌드 산출물 `dist/`를 실행하므로 fresh clone에서 build 전에는 실행할 수 없다.

```sh
src/hswm/effect-runtime/bin/hswm-dev hswm plan --focus runtime
src/hswm/effect-runtime/bin/hswm-dev hswm status
```

이 머신에는 `~/.local/bin/hswm-dev`와 `~/.local/bin/hswm-live` 편의 wrapper를 설치했고,
새 login shell에서도 명령을 찾는 것을 확인했다. 이들은 checkout launcher를 호출하며 별도
runtime 사본을 만들지 않는다. checkout을 옮기면 wrapper의 경로도 갱신해야 한다.
이는 clone의 전제 조건이 아니며 문서, CI, 자동화는 위 checkout-relative 경로를 기준으로 한다.

## 변경별 확인 경로

일반 Python 변경은 위 locked sync로 준비한 환경과 해당 변경의 집중 검사를 사용한다.
예를 들어 USL 어댑터는 추가 동기화 없이 실행한다:

```sh
uv run --no-sync pytest -q \
  tests/test_usl_adapter.py tests/test_usl_adapter_v2.py
```

CI 전체 재현 시에는 [현재 workflow](../../.github/workflows/ci.yml)의 job별 명령을 따른다.
historical byte replay의 Python·CPU 요구와 graph 전용 검사를 단일 `pytest tests`로 합치지 않는다.

graph/ontology projection 관련 검증은 전용 환경을 사용한다.

```sh
uv run --project _research/graph_standards/runtime --locked --extra graph \
  pytest -q tests/test_graph_standard_tooling.py \
  tests/test_research_evidence_graph_view.py
```

Effect runtime 변경은 package-local 검사를 사용한다. 병렬 process 검사가 있는 현재 환경에서는
테스트 worker를 둘로 제한한다.

```sh
npm --prefix src/hswm/effect-runtime run check
npm --prefix src/hswm/effect-runtime run test -- --maxWorkers=2
npm --prefix src/hswm/effect-runtime run build
```

HSWM 자신의 개발 작업은 변경과 맞는 focus를 선택해 실행 결과를 local state에 남긴다.
`plan`은 선택을 보여주고, `run`은 `.hswm-local/`에 episode와 관측을 기록한다.
`plan`과 `status`도 첫 실행 시 ignored 로컬 SQLite를 생성·초기화할 수 있다.
검사 exit code만으로 유용성이 확정되지는 않는다.

```sh
src/hswm/effect-runtime/bin/hswm-dev hswm plan --focus runtime
src/hswm/effect-runtime/bin/hswm-dev hswm run --focus runtime \
  --task '변경한 native runtime 검사'
src/hswm/effect-runtime/bin/hswm-dev hswm status
src/hswm/effect-runtime/bin/hswm-dev hswm feedback --episode <ID> --success true \
  --source 'agent(codex): 변경 범위의 검사 선택과 결과 확인에 유용했음'
```

`agent(...)` 판단은 사용자 피드백과 구분하며, 통과 자체를 HSWM 효능이나 인과 credit으로
기록하지 않는다. 관련 변경에 필요한 추가 검사는 선택 profile 밖이라도 생략하지 않는다.

## 선택적 통합 경로

일반 편집·단위 검증에 Docker나 Neo4j는 필요 없다. disposable Neo4j readback, graph publication,
external LLM, standards requalification처럼 무겁거나 외부 상태를 쓰는 경로는 기존 CI와 해당
운영 계약의 별도 범위다. 로컬 Docker/Neo4j 부재를 정상 개발의 실패로 취급하지 않으며,
이를 위해 새로운 승인 gate를 추가하지 않는다.

작업 전후에는 사용자 소유의 dirty file, private `.hswm-local/` 상태, 과거 evidence snapshot을
보존한다. material research result가 아닌 일상 환경 정리·문서·코드 작업에는 새 research
receipt나 결과 로그를 만들지 않는다.

## 이 환경에서 확인한 결과

2026-09-09의 로컬 작업 트리에서 아래 범위를 확인했다. 검사 수는 범위가 겹치므로 합산하지 않는다.

| 확인 범위 | 결과 |
| --- | --- |
| Node 24.13.0·CPython 3.12.13 실행 파일 | 기존 CI SHA-256 pin과 일치 |
| root·graph 환경 locked sync 및 `uv pip check` | 기존 패키지를 보존했고 두 환경 모두 의존성 호환 |
| TypeScript·Effect 경계 검사, 일반·DNRD 빌드 | 통과 |
| 전체 Effect runtime 검사, worker 2개 | 951개 통과, 기존 외부 서비스 통합 검사 7개 skip |
| 전용 graph 환경 검사 | 88개 통과, 기존 RDFLib deprecation 경고 |
| `hswm-dev` runtime / usl / docs / ontology | 각각 47 / 19 / 333 / 9개 통과; 검사 유용성은 명시적 `agent(codex):...` 피드백으로 기록 |
| portable Markdown math compiler | 정전·연구·ontology 155개 및 새 안내·기여 문서 2개 처리 통과 |
| 사용자 PATH | 새 login shell에서 두 native CLI 접근 확인 |

개발 환경 관측과 소스 digest는
[`HSWM_DEVELOPMENT_ENVIRONMENT_2026-09-09.v1.json`](../../ontology/infrastructure/HSWM_DEVELOPMENT_ENVIRONMENT_2026-09-09.v1.json)에
기록한다. private 실행 출력과 SQLite는 `.hswm-local/`에만 보존한다. 실제 외부 LLM 호출,
원격 DB publication, GPU 학습, CI 전체 재실행은 이번 확인 범위에 포함하지 않았다.
