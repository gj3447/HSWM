# 유한 규칙의 전체 조합 표 — 전달 충실도 개발 비교

2026-10-19 · agent(codex)의 구현·직접 측정. 사용자 정본이나 일반 지능의 입증이 아니다.
[앞선 P01 실패](HSWM_SEMANTIC_W_LOOP_2026-10-19.md#실제-실행과-hswm_likeness-연결-확인)의 후속이다.
이전 실패 원본·protocol·receipt는 수정하지 않았다.

**새 표현은 14/16, 기존 표현은 12/16이다. 사전 기준 16/16을 충족하지 못해 P01_FAILED다.**
W 학습과 구조 변경은 이번 실험에서 수행하지 않았다.

## 구현과 의미 보존

`hswm-activation execute`에 선택적 `presentation: "finite_table_tail"`을 추가했다.
기본 `canonical_json`, 기존 `execution_tail`과 그 기록 형식은 유지한다.
전체 canonical frame 뒤에 각 유한 규칙의 모든 허용 값 조합을 표로 제시한다.
현재 event는 표 생성에 사용하지 않는다. event별 정답을 미리 계산해 모델 응답으로 대체하는 경로도 없다.
이는 명시적인 유한 논리식을 컴파일한 보조 표현이며, 모델 단독의 AST 해석 능력과 구별한다.

- `hswm-finite-semantic-program/v1`의 전체 논리곱을 기존 유한 평가기로 열거한다.
  변수 순서·값 문자열·정확한 role occurrence·owner·participant·예외 참조와 원문 hash를 보존한다.
  모순인 규칙의 허용 행은 0개이며, 빈 표를 모든 값 허용으로 바꾸지 않는다.
- 자연어·불완전한 역할·정해진 유한 공간 밖의 프로그램은 거부한다. 프로그램당 변수 16개,
  전체 할당 4,096개 상한을 따른다. 표가 65,536 bytes를 넘으면 일부 행을 자르지 않고 거부한다.
- 전체 prompt는 기존 `maximumContextBytes`에 포함된다. 원문·표·event를 포함한 실제 HTTP body와
  원본 응답을 trace에 결속한다. `learn`은 그 표현을 재생성해 원문·prompt·wire를 대조한다.
- 표는 해석기의 결정적 projection이다. graph-resident 의미를 새로운 정본 atom으로 덮어쓰거나,
  기반 LLM의 weight를 변경하지 않는다. 기존 native RDF/owner 경로를 그대로 사용한다.

소유 구현은 [유한 표 컴파일러](../../src/hswm/effect-runtime/src/semantic-context-finite-presentation-domain.ts),
[표현 선택](../../src/hswm/effect-runtime/src/semantic-context-presentation-domain.ts),
[실행·trace](../../src/hswm/effect-runtime/src/semantic-context-runtime.ts)다.
관련 CLI 사용법은 설치본 `src/hswm/effect-runtime/bin/hswm-activation --help`에서 읽는다.

## 고정한 비교와 관측

새 개발 census는 identity/complement × bit 0/1 × invalid 0/1 × 두 반복, 총 16개다.
두 표현에 같은 event를 전달하고 쌍마다 실행 순서를 번갈아 배치했다. 같은 규칙과 같은 문제의 반복이며
독립 iid 과제·비공개 holdout으로 세지 않는다. 모델은 기존 `qwen3-4b-real`, `max_tokens:512`다.
source/build·cell·원본 저장소와 protocol을 호출 전에 고정했다. 고정 상한은 32회·동시성 1·15분,
호출당 30초다. 의미 오답은 전체 고정 census에서 기록하며, transport/parse/store 실패 시 재시도하지 않는다.

| 관측 | 기존 execution_tail | 새 finite_table_tail |
|---|---:|---:|
| 정확 실행 / 전체 | 12/16 | 14/16 |
| 예외 위반 / 예외 입력 | 0/8 | 0/8 |
| 두 반복의 정확 실행 | 각각 6/8 | 각각 7/8 |
| 전체 prompt UTF-8 bytes 합계 | 234,848 | 203,168 |
| 공급자 보고 total tokens 합계 | 74,325 | 63,425 |
| HTTP 시간 합계 | 20.186초 | 22.305초 |

2026-10-19 14:17–14:18 UTC에 실제 모델 32회, 합계 **137,750 tokens**를 사용했다.
모든 응답의 finish reason은 `stop`이다. 새 표현은 complement/bit=0/invalid=0을 두 번 모두 맞혔으나,
complement/bit=1/invalid=0에서는 두 번 모두 유일한 허용 출력 `0` 대신 `1`을 반환했다.
기존 표현은 네 번의 예외 없는 complement 입력을 모두 틀렸다.
새 표현의 더 작은 prompt/token 합계만으로 동일 품질의 효율 개선을 주장하지 않는다.
HTTP 합계는 오히려 늘었고, 공유 서버 부하·원격 weight revision·sampling은 독립 인증하지 않았다.
GPU FLOPs·전력·자연 과제 일반화도 측정하지 않았다.

독립 checker는 생산 평가기를 import하지 않고 유한 AST를 다시 계산했다. 규칙별 **960개 할당 검사**와
실제 표 행, canonical 원문·역할·예외, 선택한 묶음, HTTP 요청·응답, 변경되지 않은 prediction을 대조했다.
960은 반복된 검사량이며 960개 서로 다른 과제라는 뜻이 아니다.
native journal은 revision 2 그대로이고 W는 초기 상태다. 학습 0회·구조 변경 0회·새 holdout 0회다.

실행 준비에는 두 번의 로컬 복사 실패가 있었다. 첫 복사본의 디렉터리가 0755여서 private-store 검사가
거부했고, 다음 복사본은 journal slot/object의 hardlink identity가 달라 recovery가 거부했다.
두 번 모두 provider 호출 0회이며 원본을 보존했다. 세 번째는 0700과 복사본 내부의 hardlink를 보존하고
원본과 inode를 공유하지 않도록 수정했다. 실제 native reopen과 원본 byte 동일성을 준비 단계에서 확인했다.
원래 저장소의 검사 조건을 완화하지 않았다. 세 번째 실험만 32회 호출했으며 재시작하지 않았다.

## 로컬 검증과 HSWM_LIKENESS 연결

TypeScript·Effect 경계·함수형 검사와 build가 통과했다. 관련 **28개 테스트**가 통과했다.
새 의미 보존 5개 검사는 모든 2변수 truth function, 모순, unless 예외, event 독립성,
문자열 escaping, 역할 누락·열거 및 표 크기 초과를 다룬다.
통합 검사는 두 표현의 실행→수치 학습→원자적 퇴역/reset→별도 프로세스 재사용→복원과 RDF readback을 확인한다.
모의 transport를 사용한 이 통합 검증을 실제 모델의 학습 성과로 합산하지 않는다.

HSWM_LIKENESS에서 흡수한 [유한 의미·역할·예외 보존](HSWM_LIKENESS_RESEARCH_TRANSFER_2026-10-18.md)을
HSWM 안에서 재사용하는 연결이다. 기존의 실제 likeness CLI→owner 정책 채택→재사용·복원 경로는
[앞선 별도 합성 검증](HSWM_SEMANTIC_W_LOOP_2026-10-19.md#hswm_likeness는-어디에-연결되는가)을 참조한다.
이번 작업에서 likeness CLI를 다시 실행하거나 온라인 로그의 자동 왕복을 추가하지 않았다.
LinUCB 기록과 likeness의 고정 무작위 IPS 평가 전제 차이도 그대로다.

## 재검사와 다음 작업의 경계

원본은 ignored `.hswm-local/finite-presentation-2026-10-19/`에 보존한다. 이전 코드의 exact bytes도
private archive에 남겼다. 실행 시점의 일부 native 의존성은 다른 작업자의 미커밋 변경을 포함하므로,
깨끗한 HEAD만으로 같은 runtime을 복원했다고 주장하지 않는다. protocol의 source/build pin으로 구별한다.
기존 실패 receipt의 hash를 새 코드에 맞춰 갱신하지 않았다.

이 결과의 [내용 주소형 receipt](../../evidence/hswm_finite_presentation_2026-10-19/)는 기존 연구 receipt 형식으로
private 원본 manifest·관측·source-bound PROV-O graph를 묶는다. reader는 아래 `check.mjs`다.
원본이 없으면 `NOT_HYDRATED`, byte가 다르면 drift로 거부한다. 공유 KG 게시나 운영 정책 배포는 하지 않았다.

```bash
node _research/finite_presentation_v1/run.mjs --help
node _research/finite_presentation_v1/check.mjs \
  .hswm-local/finite-presentation-2026-10-19 \
  evidence/hswm_finite_presentation_2026-10-19/*.json

# 검사는 모델을 호출하지 않는다. 테스트는 공용 호스트의 managed scratch 안에서 실행한다.
cd src/hswm/effect-runtime
npm run check
npm run build
npm test -- ../../../tests/effect-runtime/semantic-context-finite-presentation.test.ts \
  ../../../tests/effect-runtime/semantic-context-topology.test.ts \
  ../../../tests/effect-runtime/semantic-context-activation.test.ts \
  ../../../tests/effect-runtime/semantic-context.test.ts --maxWorkers=1
```

다음 P01 후보는 **모델 출력의 유한 제약 위반을 검출해 명시적인 실행 실패로 반환하는 경계**다.
이를 도입해도 실패가 정답으로 바뀌는 것은 아니므로, 실행 충실도와 가용성·호출 비용을 함께 평가해야 한다.
유한 해석기로 답을 직접 산출하는 설계는 별도의 계산 경로로 명시해야 하며 모델 성공으로 기록할 수 없다.
현재 14/16을 근거로 P01을 통과시키거나 새 W·허브·병합 비교로 넘어가지 않는다.
