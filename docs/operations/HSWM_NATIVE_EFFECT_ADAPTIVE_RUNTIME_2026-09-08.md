# 함수형 TypeScript/Effect 적응 실행 경로

2026-09-08 · `SECONDARY_AI / LOCAL_ENGINEERING_IMPLEMENTATION`.
[사용자 원문](../canon/sources/USER_PRIMARY_HSWM_NATIVE_FUNCTIONAL_RUNTIME_2026-09-08.txt)은
LLM 호출부터 평가·학습·다음 행동까지 TS/Effect로 연결하고 함수형 패러다임을 지키라는
`USER_PRIMARY` 지침이다. [Constitution](../canon/HSWM_CONSTITUTION_2026-08-20.md)의
하나의 토큰 신경 HSWM 목표와 FCL-1..8, 기존 실패·판정은 유지한다.

개념적 변화는 Python에 있던 **관측적 국소 적응 실행 경로**를 네이티브 TS로 옮기는 것이다.
계획·문맥 예측·학습 상태 계산은 순수 함수이며, 실행과 저장은 Effect 서비스로 합성한다.
LLM HTTP 응답이 정상이라는 이유로 보상을 만들지 않는다. 선언한 검사 결과 또는 출처가
있는 명시적 피드백이 관계 revision에 반영되고, 다음 프로세스가 그 상태로 선택한다.
이 구현은 canonical admission, 인과적 credit 식별, 과학적 효능이나 FCL 통과를 입증하지 않는다.
기존 Python 실험 전체, 수치 학습 연구와 다른 과학적 실행 경로를 모두 TS로 이식했다는
주장도 아니다. 기존 RED 기록과 hash-bound 연구 자료는 그대로 남는다.

## 실행과 개발

저장소 루트에서 다음을 실행한다. 패키지 잠금은 기존 정확한 버전을 사용하며 새 의존성을
추가하지 않았다.

```sh
npm --prefix src/hswm/effect-runtime ci --ignore-scripts
npm --prefix src/hswm/effect-runtime run build
export PATH="$PWD/src/hswm/effect-runtime/bin:$PATH"
hswm-dev hswm plan --focus runtime
hswm-dev hswm run --focus runtime --task '네이티브 적응 실행 경로 확인'
hswm-dev hswm status
```

출력의 episode ID와 검사 내용을 검토한 뒤 명시적 유용성 판단을 남긴다.

```sh
hswm-dev hswm feedback --episode <ID> --success true \
  --source 'agent(codex): 이번 변경의 실행·저장 회귀를 확인하는 데 유용했음'
```

`hswm-dev`의 자체 개발 profile v2는 `runtime`에서 네이티브 TS 테스트를 실행하고,
확장 관계에서 TS 타입·Effect 경계 검사까지 실행한다. `usl`, `ontology`, `docs`와
외부 프로젝트의 일부 검사 명령은 기존 Python 검증 도구를 호출한다. 이들은 선택한
외부 과제이며 HSWM 실행기·학습기·SQLite·CLI의 Python 의존성이 아니다.
필요한 추가 검사를 선택된 profile에 맞추어 생략하지 않는다.

`pyproject.toml`의 Python `hswm-live`·`hswm-dev` console entry는 제거했다.
Python의 `hswm-task`, `hswm-usl`과 과거 adaptive 모듈은 비교·연구 도구로 남아 있다.
이전 venv를 계속 사용하는 개발 환경은 `uv sync --locked --extra dev`로 오래된 console
entry를 제거한 뒤 위 네이티브 경로를 사용한다. `uv run hswm-dev`를 활성 사용법으로
사용하지 않는다. CLI는 npm의 native bin 또는 checkout의 `bin/` launcher로 실행한다.

## 함수형 경계

| 책임 | 코드 | 경계 |
| --- | --- | --- |
| 검증·계획·예측·갱신·유한 조건 제안 | `adaptive-domain.ts` | `Either`와 readonly 입력·새 모델 반환. HTTP·DB·프로세스 실행 없음 |
| 실행·관측·피드백·관계 revision 연결 | `adaptive-runtime.ts` | Effect 조합, typed failure, 사전 trajectory 기록, 명시적 lease |
| 외부 명령·HTTP 모델 관측 | `adaptive-executor.ts` | byte/time 제한, 취소와 자원 정리, 정상 LLM 응답은 `success=null` |
| 로컬 상태·계보 | `adaptive-store.ts` | scoped Node SQLite, CAS와 revision digest, 원자적 outcome/관계 기록 |
| argv·출력·종료 코드 | `adaptive-cli.ts`, `hswm-*-process.ts` | 공용 process boundary에서 실행. 과제 실패는 exit 1, UNKNOWN은 3, WITHHOLD는 4 |

새 lane의 `lint-adaptive-functional.mjs`는 TypeScript AST로 module `let`/`var`,
raw `throw`/`async`, `Effect.run*`의 import 별칭·namespace 경로, domain의 직접 I/O import를
검사한다. 기존 allowlist를 늘리지 않았다. 이 검사는 지정한 adaptive 파일과 native process
파일의 코드 형태를 검사하며, 모든 JavaScript alias·동적 호출의 의미적 순수성을 증명하는
정리 증명기가 아니다. 상태 계산의 입력 보존과 실제 동작은 별도 테스트로 확인한다.

## LLM과 평가 연결

`hswm-live --program <manifest.json> run --context <JSON> --task <TEXT>`는
`hswm-adaptive-program/v1` manifest를 사용한다. `kind: "llm"` cell은 `base_url`,
`model`, 선택적인 `api_key_env`·`max_tokens`로 HTTP 모델을 호출한다. API key 값은
환경 경계에서 읽으며 manifest나 결과에 복사하지 않는다.

typed port가 맞는 `LLM → command` 멤버 관계를 선언하면 뒤의 명령이 앞 출력의
`previous_output`을 stdin JSON으로 받아 평가할 수 있다. `outcome: "exit_code"`를
명시한 검사만 Boolean 결과를 제공한다. 미지정 command와 LLM 응답은 관측이며, 명시적
feedback 전에는 성공 학습 label을 만들지 않는다. 종료·HTTP 오류·truncation 등
불명확한 결과를 성공으로 바꾸지 않는다.

동일 episode 요청은 저장된 결과를 재생한다. 다른 intent로 같은 ID를 쓰면 거절한다.
실행 중 feedback·restore·다른 실행은 로컬 잠금으로 배제한다. UNKNOWN 또는 중단된
episode의 lease는 유지되며 결과를 확인한 명시적 feedback으로 해소한다. `--frozen`은
관측을 기록하면서 모델 갱신을 멈춘다. `restore`는 과거 내용을 새 revision으로 복원한다.

## 기존 상태와 프로젝트 연결

기존 SQLite의 immutable revision JSON은 **저장된 원시 JSON 문자열**로 digest를 확인한다.
Python `1.0`을 JS `1`로 재직렬화해서 과거 digest를 다시 쓰지 않는다. Node가 추가하는
새 revision과 event만 새로 기록한다. 기존 episode intent의 숫자 표기 차이는 전체 의미를
비교하며 다른 task·context·workspace·manifest·실행 옵션을 같은 요청으로 취급하지 않는다.

기존 stock game·MapleLineage·Supullim profile과 SQLite 위치를 유지한다. 검사 내용이
바뀐 HSWM 자체 개발과 Reluvator는 v2 graph ID를 사용한다. v1의 실행·피드백 이력은
그대로 보존하며 다른 검사에 자동 이전하지 않는다. 사용자 정의 Python float context의
타입·표기까지 일반적으로 동등하다고 주장하지 않는다. 정확한 호환 범위는 아래 합성
이력 검사와 현재 string/Boolean stock profile에 한정한다.

외부 checkout에서는 `../HSWM/src/hswm/effect-runtime/bin/hswm-dev`를 직접 호출한다.
MapleLineage의 프로젝트 전용 wrapper는 `node scripts/maplelineage_hswm.mjs`를 사용한다.
Reluvator v2의 고정 원격 검사 전달기도 Node를 사용한다. 프로젝트 자체의 구현·연구
스크립트를 모두 다른 언어로 바꾸는 작업은 이 전환에 포함하지 않는다.

## 도구 출처와 검증 범위

| 도구 | 고정 버전·출처 | 권한·라이선스 |
| --- | --- | --- |
| Node.js | 24.13.0, 기존 CI executable SHA-256 pin | 공식 런타임, MIT 및 배포물 내 제3자 고지 |
| Effect | 3.22.1, 기존 `package-lock.json` integrity | 공식 라이브러리, MIT |
| TypeScript | 5.9.3, 기존 lockfile integrity | 공식 컴파일러, Apache-2.0 |
| Vitest | 3.2.7, 기존 lockfile integrity | 프로젝트 공식 테스트 도구, MIT |

[Node 24.13.0 SQLite 문서](https://nodejs.org/download/release/v24.13.0/docs/api/sqlite.html)와
[Effect resource management 문서](https://effect.website/docs/resource-management/introduction/)를
확인해 기존 런타임의 scoped adapter로 연결했다. `node:sqlite` 및 사용한 Node entry 기능은
해당 고정 런타임의 실험적 API lane이다. 로컬 filesystem의 SQLite locking에 의존하며
분산 잠금이나 운영 환경 전반의 검증을 주장하지 않는다.

검증 기록은 같은 날짜의
[`HSWM_NATIVE_EFFECT_ADAPTIVE_RUNTIME_2026-09-08.v1.json`](../../ontology/evidence/HSWM_NATIVE_EFFECT_ADAPTIVE_RUNTIME_2026-09-08.v1.json)에
소스 digest와 함께 연결한다. Python·uv가 없는 PATH의 native CLI, 합성 과거 이력의
readback, 실제 로컬 HTTP 서버, 피드백 전후 선택, 취소·잠금·중복·불명확 결과를 검사한다.
자체 개발 profile의 agent feedback은 검사 유용성에 대한 개발 기록이며 사용자 평가나
HSWM 효능의 인과적 증거가 아니다. private SQLite와 실행 출력은 공개 KG에 포함하지 않는다.

## 2026-09-08 검증 결과

| 검사 | 결과 |
| --- | --- |
| `npm test -- --maxWorkers=2` | 122개 파일, 914개 통과. 외부 서비스 통합 검사 7개는 기존 설정에 따라 skip |
| 그중 새 adaptive 검사 | 8개 파일, 36개 통과. 순수 계산 수치 대조·native CLI·실제 HTTP·지연 실행·저장·과거 이력·중단 경계 포함 |
| `npm run check`, `npm run build` | 타입 검사·두 경계 lint·빌드 통과. 기존 allowlist 38개 유지, 새 lane 예외 추가 없음 |
| Python 비교 구현 회귀 | runtime·lifecycle·두 CLI 22개 통과 |
| Markdown·수식·기존 개발 KG 회귀 | 334개 통과, 기존 RDFLib deprecation 경고 3건. portable math compiler 통과 |
| 외부 프로젝트의 기존 상태 | game·Supullim·MapleLineage의 native status/plan에서 기존 관측 확인. Maple native wrapper 회귀 통과 |
| 자체 개발 | `native-functional-runtime-20260908-01`: v2 runtime-extended의 native 검사와 타입·경계 검사 완료. agent feedback 뒤 revision 2·관측 1, pending 없음 |
| Reluvator | `native-reluvator-20260908-01`: Node 기반 SSH 전달기로 기존 중앙 계약 일치 검사 완료. 명시적 agent feedback 기록 |

처음의 전체 병렬 실행은 905개 통과·6개 실패·7개 skip이었다. 실패 중 5개는 여러
프로세스 검사를 함께 실행할 때의 5초 테스트 제한, 1개는 Node 실험 경고가 섞인 stderr를
단일 JSON으로 읽던 새 테스트 문제였다. 여러 native 프로세스를 실행하는 새 CLI 검사의
시간 범위와 stderr 판독을 고쳤고, 기존 검사 기준은 바꾸지 않은 채 worker 2개로 전체를
재검증했다. 실행기 자체의 timeout·UNKNOWN 기준은 완화하지 않았다.

코드 검토 중 Effect 값 구성 시 DB를 먼저 실행하던 결함, output truncation 뒤 exit 0을
보상으로 바꾸던 결함, 기본 옵션의 undefined 직렬화, 과거 intent 재생과 restore 충돌을
발견해 고쳤다. 고정 Python SQLite fixture는 실제 과거 BLOB 행을 Node로 seed하고,
재생 뒤 새 native 관측을 추가해도 이전 payload bytes·digest가 바뀌지 않음을 확인한다.

외부 checkout의 안내·Maple wrapper 변경은 각 저장소의 진행 중인 별도 작업과 함께
작업 트리에 남겼다. 해당 저장소들의 unrelated 코드나 integrity lock을 이 작업에
일괄 포함해 commit하지 않았다. HSWM의 공개 snapshot에는 로컬 구현·검증과 그 한계만
기록한다.
