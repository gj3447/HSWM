# Workspace의 국소 실행·신경 선택·저장소 읽기

2026-10-24 · `agent(codex) / SECONDARY_AI`. 앞선
[발표–헌법–다단계 실행 검사](HSWM_MULTIHOP_ACTIVATION_2026-10-24.md)의 후속 구현이다.
사용자 원문이나 HSWM_LIKENESS의 점수·프로파일을 변경하지 않는다.

현재 판정은 **선언된 출처 읽기·제목 추출 범위의 실행–피드백–native W 개정–다음 프로세스
재사용 검증 완료**다. 사용자 재개 요청에 따라 현재 판본 **49개 출처·416개 절**을 고정하고
실모델 49 TRAIN + 별도 OS 프로세스 3 AUDIT를 실행했다. 독립 checker는 PASS다.
제목 추출은 47/49, 재개방은 3/3이며, 오답 2건의 원본과 reward 0도 보존했다.
이 결과는 임의 질문의 충분성·최소성, 자연 과제 일반화나 HSWM 전체 효능을 입증하지 않는다.
2026-10-25 후속에서는 이 두 오답에 정확 추출 계약과 원문 표시 형식을 적용해
실모델 2/2·별도 프로세스 2/2를 확인했다. 최초 수정의 0/4도 아래에 보존한다.

## 이번에 연결한 범위

```text
헌법 진입점 → 선언된 주제별 route → 정확한 문서 판본
→ 역할 있는 절 색인 → 선택한 완전한 절 + 필수 조건
→ 신경 gate의 연산 선택 → 실제 LLM → 외부 관측
→ 기존 native owner의 W 개정 → 새 프로세스의 다음 사용
```

현재 등록된 49개 출처의 416개 완전한 ATX 절을 기존 native 원자로 저장하고, catalog가
역할 있는 참조로 각 절을 가리키게 했다. 현재 관측한 문서 hash, 과거 bundle, 명시적
route, 선택한 절의 범위·hash를 구분한다. `fractal`의 SOURCE_ONLY 지위는 유지한다.
모든 저장소 파일이나 각 문서에 적힌 모든 프로그램을 실행한 것은 아니다.

실행 consumer는 질문·출처·절을 받을 수 있다. 이번 실측은 첫 level-one 제목을 포함하는
완전한 절을 선택해 제목을 그대로 읽는 과제다. 필요한 절 밖의 예외·의존성이 없다고
보증하지 않는다. 일반 질문의 충분성은 추가 탐색·보류 판단이 필요하다.

신경 선택기는 작은 tanh 은닉층과 연산별 sigmoid reward head의 clipped SGD다.
실행한 연산의 외부 결과만 target으로 쓴다. 기존 policy/v1 LinUCB를 보존하고 새 v2로
구분했다. extract/explain은 동결 LLM에서 실행하는 그래프 내 의미 프로그램이다.
LLM 내부 MoE의 FFN 가중치 학습이나 자연어 embedding 학습은 포함하지 않는다.

저장소는 출처·선택별 기존 native partition을 사용한다. hot snapshot은 같은 head를
확인해 재사용하고 선택 content를 hash로 검사한다. 시작·종료 audit와 실제 commit은
그 partition 전체를 검증한다. 외부 writer, 바뀐 head, 종료된 session 사용을 거부한다.
이전의 무관한 파일 손상 검사는 매 snapshot에서 종료 audit로 늦춰진다. append-only
owner 계약 아래의 opt-in 최적화이며 모든 파일의 상시 무결성 검사와 같지 않다.

## 헌법·발표·검사 대응

| 요구 | 구현·검사 | 판정 경계 |
| --- | --- | --- |
| 4조·발표 36쪽: 상황에 맞는 국소 활성화 | 신경 gate, 원문 역할·예외 유지, 실제 token preflight | top-1은 현재 구현 선택이며 헌법의 상수 아님 |
| 5–6조·발표 11·34쪽: 여러 지도를 거쳐 필요한 내용 | 기존 route follow → native 절 catalog → 정확한 UTF-8 범위 | 정확한 entry/절 ID 기반; 미지의 경로를 자연어로 생성하지 않음 |
| 8–9조·발표 17쪽: 실행과 지속 학습 | 실제 wire → 관측 → owner policy/v2 → 별도 OS 프로세스 | 업데이트 연결과 자연 과제 효능은 별도 |
| 5조: 저장소 복원까지 비용에 포함 | 동일 assembly의 실제 파일 읽기 바이트 비교 | 파일에서 반환된 bytes이며 물리 디스크 I/O·O(1) 증명 아님 |
| 13–14조: 실패 보존·평가기 검사 | 독립 gradient 계산, reward/role/W 변조 거부, 실제 출처 전체 admission | 노출된 제목 기준의 진단이며 독립 자연 과제 평가 아님 |

## 실패에서 고친 문제

1. 문서 전체를 중복 전달하던 첫 실행은 두 번의 생성 뒤 세 번째 요청에서 중단했다.
   첫 제목 번역 오답은 reward 0으로 보존했다. 이후 정확한 prompt의 tokenizer 관측은
   8,711 tokens, 모델 공개 한도는 8,192였다. 원래 HTTP 오류 body가 없어 이 원인 판단은
   후속 관측에 따른 추론이다. 내용 절 선택과 실제 토큰 예산 검사를 추가했다.
2. 두 번째 실행은 11/11 생성·W 저장 뒤 56개 절 출처의 seed에서 중단했다. 65개 원자를
   한 번에 입장시키려 하자 native의 64개 쓰기 상한이 거부했다. 첫 묶음은 BOOTSTRAP,
   이후는 입장한 원문을 sourceRef로 갖는 DERIVATION으로 나눴다. 기존 상한은 유지한다.
   수정 뒤 49개 실제 출처의 전체 catalog admission을 모델 없이 먼저 검사했다.

두 partial root는 보존하며 같은 root를 재시도하거나 과거 hash를 현재에 맞춰 덮어쓰지 않는다.
후속 실행은 수정한 구현·범위로 별도 등록한다. 성공률에 이전 집단을 임의로 섞지 않는다.

## 실제 실행과 독립 검사

확인한 검사는 새 신경·workspace·손상 검사 12개, 기존 다단계 9개, 활성화 3개, 내용 탐색
16개로 총 **40개**다. 수치 미분과 XOR, v1 호환, 원문/범위 변조, stale·중복·외부 writer,
선택 content와 head 손상, 무관 content 손상의 종료 audit를 확인했다.
49개 실제 출처의 전체 catalog admission도 이 검사에 포함한다. 당시 단위 검사 판본은
413개 절이었고, 이번 실제 실행은 개정된 416개 절 판본 전체를 admission·readback했다.
최종 runtime의 `npm run check`와 `npm run build`, 변경 문서의 portable math 검사도 통과했다.
이번 재개에서는 runtime을 바꾸지 않았고 구현·의존 파일 및 package lock의 총 49개 pin이
일치함을 확인했다. 이어서 실제 모델·영속 상태·읽기 비교를 실행했다.

| 실제 모델 관측 | 생성·W 저장 | 결과 |
| --- | --- | --- |
| 초기 전체 문서 전달판 | 2회·2회 | 1/2; 세 번째 요청 transport 중단 |
| 절 선택 도입판 | 11회·11회 | 11/11; 다음 출처의 seed가 64개 쓰기 상한에서 중단 |
| 최종 batch 수정판 TRAIN | 49회·49회 | 47/49; 전 출처의 policy 0→1 개정·정확한 readback |
| 별도 OS 프로세스 AUDIT | 3회·0회 | identity·fractal·tool-harness에서 저장된 policy 1판 사용; 3/3 |

최종 집단은 모델 ID `qwen3-4b-real`로 실제 생성 **52회**, 공급자 보고 **230,630 tokens**를
사용했다. 정확한 checkpoint hash는 미확인이고 LLM 본체 가중치는 동결했다. 최대 입력은
5,562 tokens이며 출력 예약 384를 더해도 관측한 8,192 한도 안이다. 논리 prompt 총합은
634,360 bytes다. 관리 작업은 약 173.0초, 모델 HTTP 구간 합은 약 127.2초였다. 관리 작업
시간에는 실행·checker·아래 세 읽기 비교가 포함되며, 준비와 이전 실패·대기는 제외한다.

오답은 `performance-proof`와 `optimization-rules`다. 두 prediction은 원문의 첫 제목 대신
각 workspace 요약 제목과 일치했다. 정답·허용 오차를 바꾸거나 재시도하지 않았고 실제 0
reward가 해당 source의 신경 파라미터를 갱신했다. 이 두 오류가 이후 질문에서 교정됐다는
주장은 하지 않는다. 사전에 정한 재개방 세 출처는 위 표의 별도 집단이다.

checker는 실행기의 학습 함수를 재사용하지 않고 scalar chain rule과 clipping을 계산해
49개 신경 파라미터 갱신을 대조했다. 최초·후속 native policy, 완전한 원문·절 catalog,
선택 역할·실제 wire·trace·outcome을 확인했다. 명시적인 native content 대조는 404회,
reward·필수 역할·W 변조 거부는 3건이다. checker 전후 **2,659개 native 파일의 경로와
바이트 hash가 동일**했다. checker PASS는 원래 추출 오답을 성공으로 바꾸지 않는다.

이전 관리 대기 세 번은 명령 시작 전에 종료됐고, 한 번은 대기 중 개정된 manifest를
감지해 `NOT_READY`로 중단했다. 모두 모델 호출은 없었다. 만료된 scope와 과거 pin은
그대로 보존했다. 이번 사용자 재개 요청으로 같은 프로젝트·기존 transport·52회 상한을
새로 등록하고, 도달성을 확인한 후 실행했다. 이번 입장 대기는 약 0.006초였다.
실행 완료 후 활성 작업이나 자동 재시도를 남기지 않는다.

## 동일 문맥의 파일 읽기 비교

각각 같은 source·policy·질문·단일 실행 조건에서 기존 native snapshot 조립과 scoped
session 조립을 비교했다. 세 경우 모두 반환된 assembly가 정확히 같고 native submit은 0회다.
실제 `readRegularBounded`가 반환한 바이트를 세었으며, 파일 경로별 원본 집계도 보존했다.

| 출처 | 기존 읽기 bytes | session 읽기 bytes | 감소 | 기존/session 시간 ms |
| --- | ---: | ---: | ---: | ---: |
| identity | 658,689 | 227,215 | 65.5% | 309.2 / 76.3 |
| fractal | 2,420,279 | 618,765 | 74.4% | 1,143.6 / 243.0 |
| tool-harness | 1,274,184 | 366,731 | 71.2% | 505.3 / 93.0 |

각 session은 snapshot 요청 9회를 시작·종료의 전체 복원 2회와 head 검사로 처리했다.
계수는 runtime layer 최초 열기를 제외하고 **session 자체의 시작·종료 전체 audit를 포함**한다.
모델 호출·tokenizer·workspace 탐색 비용이나 물리 디스크 I/O를 측정한 값은 아니다.
각 출처에서 기존 조립 다음 session 조립을 한 번씩 측정했으므로 시간에는 cache·순서 효과가
있을 수 있다. 지연 분포·동시성·큰 저널의 점근 성능이나 전체 시스템 읽기량으로 일반화하지 않는다.
선택 partition의 차가운 복원과 commit은 여전히 그 partition 전체를 검증한다.

## 재현·구현·근거

원시 request/response, native 상태, source snapshot과 실행 구현 archive는 ignored
`.hswm-local/workspace-activation-finish-2026-10-24/`에 있다. 다른 writer의 수정이 있는 작업
트리에서 검증했으므로 Git HEAD만으로 동일한 실측 구성을 추정하지 않고 정확한 pins를 보존한다.
checker와 `measure`는 모델 호출 없이 이 root를 읽는다. scope가 만료됐거나 집단이 이미 실행된
root로 생성 호출을 다시 실행하지 않는다.

| 로컬 재검사 대상 | SHA-256 |
| --- | --- |
| plan.json | `d2f8025e476e2ec73842289c3941a13d6ad6916b474332c863e98a1dc51874ba` |
| verification.json | `7ddd184c178d7eb388489e8c85659a14f88f3ce4d13e8e231819da9adb44b8f1` |
| checker 구현 | `cb70265f14b15e78111e8fe0c622e44e980ba3a39bf2f6eba35e1a353cd27e38` |

[실행·재검사 방법과 1차 문헌](../../_research/workspace_activation_v2/README.md),
[consumer](../../src/hswm/effect-runtime/src/workspace-activation-runtime.ts),
[신경 수치 연산](../../src/hswm/effect-runtime/src/semantic-context-neural-domain.ts),
[snapshot 재사용](../../src/hswm/effect-runtime/src/semantic-context-read-session.ts),
[반례·49개 출처 admission](../../tests/effect-runtime/neural-workspace-activation.test.ts)을 연결한다.

Shazeer 2017의 희소·계층 gate와 NeuralUCB 2020의 비선형 reward 표현을 조사했다.
현재의 count 탐험 항은 NeuralUCB 신뢰구간·regret 보증이 아니다. DRIFT의 후속 탐색,
SQLite snapshot 경계, Hyperon experimental v0.2.10의 고정 commit도 비교했다.
새 DB 엔진이나 Hyperon 성능 비교 실험을 추가하지 않았다. 원문 링크와 적용하지 않은
부분은 위 방법 문서에 명시한다.

## 2026-10-25: 색인 제목 혼동과 정확 추출 계약

기존 두 오답은 모두 원문 H1이 실제 활성 문맥에 있었는데도 `source.binding.title`과
같은 색인 제목을 출력한 사례다. 모델 내부 원인은 직접 관측하지 않았으며, 역할 혼동이라는
진단은 이 출력 대응에 근거한다.

| 출처 | 원문 H1 | 기존 모델 출력 |
| --- | --- | --- |
| performance-proof | 문헌 성능 관측을 HSWM 성능 증명으로 잇는 조건 | 문헌 결과와 HSWM 전이 의무 |
| optimization-rules | HSWM 최적화 6원칙과 7군단장의 연결 | HSWM 최적화 6원칙과 7군단장 대응 |

`FIRST_ATX_H1_TEXT_V1`을 명시한 호출은 원문 판본·첫 H1의 UTF-8 범위·활성 evidence를
실행 전에 결속하고 출력과 정확히 대조한다. 틀린 모델 출력과 평가자 판단을 따로 보존하며,
불일치는 `verifiedPrediction=null`, reward 0이다. 정답 대입이나 자동 재시도는 없다.
새 seed는 탐색용 제목의 역할을 명시한다. `source_evidence_tail`은 기존 canonical frame
전체와 필수 조건을 보존하고, 선택된 완전한 절을 JSON escape 없는 원문으로 다시 제시한다.
원문 hash·선택·기존 정답 기준은 바꾸지 않는다. 이 검사는 명시한 추출 consumer 경계에
적용되며 임의 자연어 질문이나 문서 주장 자체의 진실성을 검증하는 헌법 전체의 증명은 아니다.

첫 수정(역할 설명 + source verifier, 기존 execution_tail)은 실제 2 TRAIN + 별도 OS
2 AUDIT에서 **0/2 + 0/2**였다. 네 번 모두 같은 색인 제목을 출력했고 verifier가 모두
MISMATCH로 차단했다. W 개정 2회와 재개방 W 1판 사용은 확인됐지만 모델 정답 생성은
개선되지 않았다. 독립 checker PASS는 이 실패·차단·갱신의 증거 일치를 뜻한다.
원시 기록은 `.hswm-local/workspace-extraction-fix-2026-10-25/`에 보존한다.

원문 표시 형식을 추가한 최종 수정은 같은 두 출처에서 **2/2 TRAIN + 2/2 AUDIT**였다.
위 표의 원문 H1을 실제 모델이 반환했으며, verifier의 정답 대입은 없었다. 원문·선택·질문은
10-24 실패 사례와 동일하다. 새 partition의 신경 W는 0→1로 실제 갱신됐고 별도 OS
프로세스가 1판을 사용했다. 예전 partition을 수정하거나 기존 W를 복사하지 않았다.
초기 W에서도 맞았으므로 이를 학습 효능이나 인과 기여 증명으로 해석하지 않는다.

최종 독립 checker PASS: native 110개 파일 전후 불변, 원본·판정·W 대조 28회,
reward·필수 역할·가중치 변조 거부 3종. 호출 4회·22,140 tokens이며 최대 입력 5,636과
출력 예약 384는 모델 한도 8,192 이내다. 첫 수정의 최대 입력 5,264보다 증가했으므로
이번 표현을 최소 비용 문맥이라고 주장하지 않는다. 관련 회귀 23개·타입/경계 검사·빌드도
통과했다.

최종 private root는 `.hswm-local/workspace-extraction-literal-2026-10-25/`다.
`plan.json` SHA-256은 `0b572a9db95c707bbc7855d09b928003764c36097a059941ddf18f629c620a89`,
`verification.json`은 `3d0510dec2bb1db28759f81f4d79668d8663301b1cd03359e262be03056dbf16`이다.
실행은 관리 job `617e26629e0243ea98ddb7ce1639be53`에서 종료 코드 0으로 끝났다.
예전 실행은 당시 pins의 결과로 남기며 현재 구현이 바뀌면 과거 root의 live-pin 재검사는
변경을 거부한다. 과거 hash를 새 구현에 맞춰 바꾸지 않는다. 기존 전체 47/49를 49/49로
고쳐 쓰거나 두 사례 재검사를 자연 과제 일반화·MoE 본체 학습의 증거로 확대하지 않는다.
