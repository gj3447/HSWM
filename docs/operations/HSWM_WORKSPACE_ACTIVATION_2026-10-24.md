# Workspace의 국소 실행·신경 선택·저장소 읽기

2026-10-24 · `agent(codex) / SECONDARY_AI`. 앞선
[발표–헌법–다단계 실행 검사](HSWM_MULTIHOP_ACTIVATION_2026-10-24.md)의 후속 구현이다.
사용자 원문이나 HSWM_LIKENESS의 점수·프로파일을 변경하지 않는다.

현재 판정은 **구현 검사 통과, 최종 실모델 집단 검증 대기**다. 공유 실행기의 CPU headroom
제한 때문에 수정 완료판의 49 TRAIN + 3 새 프로세스 AUDIT는 아직 시작하지 못했다.
앞선 partial 실행을 최종 완료판의 성공으로 대신 세지 않는다.
구현 검사는 413개 절 판본에서 수행했다. 이후 다른 writer의 헌법 지도 개정으로 현재
관측은 **49개 출처·416개 절**이며, 이 판본의 실행 준비·source pin까지 확인했다.

## 이번에 연결한 범위

```text
헌법 진입점 → 선언된 주제별 route → 정확한 문서 판본
→ 역할 있는 절 색인 → 선택한 완전한 절 + 필수 조건
→ 신경 gate의 연산 선택 → 실제 LLM → 외부 관측
→ 기존 native owner의 W 개정 → 새 프로세스의 다음 사용
```

현재 등록된 49개 출처의 413개 완전한 ATX 절을 기존 native 원자로 저장하고, catalog가
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

## 재현·구현·근거

확인한 검사는 새 신경·workspace·손상 검사 12개, 기존 다단계 9개, 활성화 3개, 내용 탐색
16개로 총 **40개**다. 수치 미분과 XOR, v1 호환, 원문/범위 변조, stale·중복·외부 writer,
선택 content와 head 손상, 무관 content 손상의 종료 audit를 확인했다.
49개 실제 출처의 전체 catalog admission도 이 검사에 포함한다.
최종 runtime의 `npm run check`와 `npm run build`, 변경 문서의 portable math 검사도 통과했다.

| 실제 모델 관측 | 생성·W 저장 | 결과 |
| --- | --- | --- |
| 초기 전체 문서 전달판 | 2회·2회 | 1/2; 세 번째 요청 transport 중단 |
| 절 선택 도입판 | 11회·11회 | 11/11; 다음 출처의 seed가 64개 쓰기 상한에서 중단 |
| 최종 batch 수정판 | 시작 전 | source·구현 49개 파일·package lock·runner 고정; 52회 최대 예산으로 준비 |

최종 집단의 성공률·별도 프로세스 재사용·독립 checker PASS와 파일 읽기 감소율은 아직
미측정이다. 관리 대기 세 번은 명령 시작 전에 종료됐다. 그 사이 한 번 입장이 허용됐을 때는
다른 writer가 개정한 manifest를 감지해 `NOT_READY`로 중단했다. 모두 모델 호출은 없었다.
기존 pin을 덮어쓰지 않고 416개 절 판본을 별도 root에 등록했으나 마지막 입장 대기도
CPU headroom·기존 대기열 때문에 만료됐다. 현재 활성 작업이나 자동 재시도는 남기지 않는다.
준비된 root의 scope가 만료되면 자동 갱신하지 않고 새 등록이 필요하다.
원시 request/response, 과거 실패, native 상태와 구현 archive는 ignored 로컬 root에 있다.
다른 writer의 수정이 있는 작업 트리에서 검증했으므로 실행 당시의 정확한 구현 pins를 보존한다.

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
