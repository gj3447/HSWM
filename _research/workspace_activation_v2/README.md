# Workspace 내용 → 국소 연산 → 신경 W

2026-10-24 · 구현·평가 설계: `agent(codex) / SECONDARY_AI`.

이 consumer는 현재 workspace의 각 출처를 기존 native canonical runtime에 결속한다.
헌법 entry에서 선언된 route를 따라 출처를 찾고, 문서의 절 색인에서 선택한 완전한 절을
LLM에 전달한다. 외부 결과로 작은 신경 gate를 갱신하고 기존 owner가 다음 policy revision을
저장한다. 역사적 SOURCE_ONLY 자료는 계속 역사적 자료다.

## 사용

```sh
node _research/workspace_activation_v2/run.mjs --help
node _research/workspace_activation_v2/run.mjs prepare NEW_PRIVATE_ROOT MODEL_ID
# 기존 관리 작업 안에서 실행한다. 서비스 설치·변경은 하지 않는다.
node _research/workspace_activation_v2/run.mjs run NEW_PRIVATE_ROOT
node _research/workspace_activation_v2/check.mjs NEW_PRIVATE_ROOT
node _research/workspace_activation_v2/run.mjs measure NEW_PRIVATE_ROOT identity
```

prepare는 49개 출처·상대 import 의존 모듈·package lock·manifest·runner를 고정하고 구현 바이트를 로컬에 보존한다. 2시간 scope 안에서 기존 loopback의
모델 도달성을 확인하고 최대 49 TRAIN + 3 새 프로세스 AUDIT 호출을 수행한다. 각 요청에
vLLM tokenizer를 한 번 호출해 실제 입력 토큰과 출력 예약량을 비교한다. 예산을 넘는 완전한
절은 잘라 보내지 않는다. partial 실행을 같은 root로 재시도하지 않는다. access.json의
`revoked`는 매 호출 전에 검사한다. 원본과 native 상태는 private root에만 보존한다.

진단 질문은 원문의 첫 ATX level-one 제목을 그대로 복사하는 것이다. 이를 포함하는 **완전한
절 하나를 명시적으로 선택**한다. 문서 전체와 모든 절의 native 원자는 보존하지만 그 모든
절을 모델로 실행했다는 의미는 아니다. 질문의 정답은 노출된 출처에서 독립 정규식으로 구한다.
이 기준은 내용 연결과 저장·재사용 검사이며 자연 과제 일반화·최소 문맥 증명이 아니다.

## 일반 consumer API

`workspace-activation-runtime.ts`의 `readWorkspaceActivationSource`는 실제
`workspace-navigation-runtime.ts`를 통해 선언된 홉을 따라가며 방문 bundle을 고정한다.
문서 전체의 현재 관측과 과거 bundle의 바인딩을 구분한다. 과거 hash를 갱신하지 않는다.

반환된 `units`에는 절 ID, UTF-8 바이트 범위, hash와 ATX 제목이 있다.
`selectWorkspaceSourceUnit(source, unitId)`로 정확한 절을 선택하거나 전체 문서를 유지한다.
이 선택은 새로운 sourceId를 만든다. 코드 fence 안의 `#`는 경로가 아니며 모든 절을
순서대로 결합하면 원문과 바이트가 일치한다. Setext 제목은 이 판본의 경계로 사용하지 않는다.
선택한 절 밖의 의존성·예외까지 충분하다는 판정은 하지 않는다. 더 필요한 자료는 새 선택으로
명시하거나 UNKNOWN으로 남긴다. 무제한 문서를 작은 모델에 넣는 자동 fallback은 없다.

`seedWorkspaceActivation(runtime, source)`는 기존 명령당 64개 쓰기 한도 안에서 묶음을 나눈다.
첫 묶음만 BOOTSTRAP이며 이후는 입장한 원문을 sourceRef로 갖는 DERIVATION이다.
최대 256개 절을 허용하고, seed가 중단되면 policy가 없어 실행할 수 없다.
새 native partition에 원문, 모든 절, 역할 있는
절 색인, 선택한 evidence, required/extract/explain 관계와 neural policy를 저장한다.
`executeWorkspaceActivation`은 실제 question·intent·TRAIN/AUDIT·LLM cell과
`http/evaluate/admit` capability를 받는다. 평가자는 실제 관측을 제공해야 하며 unknown reward는
null이다. 문서에 적힌 shell 명령이나 설명으로 도구 실행 권한이 생기지 않는다.

절/출처별 partition은 **같은 기존 native runtime의 별도 owner scope**다. 여러 partition을
통과하는 원자적 transaction이나 전역 policy 공유를 제공하지 않는다. sourceId가 달라지면
과거 W를 조용히 복사하지 않는다. 이 consumer의 경로는 정확한 entry ID 기반이며 미지의
다음 경로를 자연어로 학습하는 기능은 아니다.

## 신경 선택과 저장소 읽기

policy/v2는 `tanh` 은닉층, 연산별 sigmoid reward head, 제곱 손실의 clipped SGD를 사용한다.
관측한 연산의 결과만 target으로 쓴다. 공유 은닉층이 다른 연산의 score에 영향을 줄 수 있다.
탐험 항은 `alpha / sqrt(observations + 1)`이라는 count heuristic이다. 기존 필드명
`uncertaintyRadius`가 있어도 calibrated 불확실성이나 NeuralUCB의 신뢰구간이 아니다.
v1 LinUCB 형식과 의미는 유지하며 자동 migration하지 않는다.

extract/explain은 같은 동결 LLM을 쓰는 서로 다른 그래프 내 의미 프로그램이다. gate의 실제
신경 파라미터를 학습하지만 LLM 내부 FFN 전문가나 tokenizer·자연어 embedding을 학습하지
않는다. 최종 보상을 경로별 인과 credit으로 복제하지 않는다.

`withLocalActivationSession`은 시작과 종료에서 native 전체 복원을 수행하고, 그 사이 동일한
head를 inode·hash·후속 slot 부재로 검사해 snapshot을 재사용한다. 선택 content는 여전히
정확한 hash로 읽는다. 쓰기는 전체 검증을 수행하는 기존 native submit만 사용한다. 외부 writer의
head 진전, 디렉터리 교체, head 변조와 종료 후 사용은 거부한다. 무관한 오래된 파일 손상은
매번이 아니라 종료의 전체 audit에서 발견한다. append-only owner 계약 아래의 최적화다.
차가운 복원과 commit은 **선택한 partition 내부에서는 전역**이며 복잡도 O(1) 증명이 아니다.

## 실패 보존과 확인 범위

첫 실행은 문서 전체를 중복 prompt에 넣었다. 두 번의 실제 생성·W 갱신 후 세 번째 요청에서
전송이 실패했다. 첫 응답은 한국어 제목을 영어로 번역해 reward 0, 두 번째는 reward 1이었다.
실패한 정확한 prompt를 이후 `/tokenize`로 관측한 값은 8,711 tokens이며 모델 공개 한도는
8,192다. 원래 HTTP 오류 body는 당시 adapter가 보존하지 않았으므로 context overflow는
그 후 관측으로 지지되는 원인 판단이다. 원래 root와 pins를 보존하고 새 source 선택 계약과
별도 root로 수정 실행한다. 초기 1/2를 후속 결과에 섞어 성공률을 높이지 않는다.

두 번째 실행은 11/11 생성·W 갱신 후 56개 절을 가진 fractal 출처의 seed에서 멈췄다.
65개 원자를 한 명령에 넣어 기존 64개 상한이 거부한 것이다. 모델 실패가 아니며 해당 출처의
provider 호출은 없었다. native 상한을 유지하는 순차 admission으로 고친 뒤 49개 실제
출처의 전체 catalog 입장을 모델 없이 검사했다. 이 partial root도 그대로 남긴다.

검사기는 실행기의 학습 함수를 가져오지 않고 scalar chain rule과 clipping을 재계산한다.
native의 최초·후속 policy, 원문·절 색인, wire/trace/outcome, 실제 token budget과 별도 OS
프로세스 재사용을 대조한다. reward·필수 역할·가중치 변조도 거부한다.
단위 검사는 수치 미분, XOR의 비선형 경계, stale/중복 보호, 외부 writer, 잘못된 범위와
UTF-8/fence를 다룬다. 실제 관측 수치는 [실행 보고서](../../docs/operations/HSWM_WORKSPACE_ACTIVATION_2026-10-24.md)에 기록한다.

## 검색한 1차 자료와 적용 판단

- [Shazeer 등, 2017, §§2·4·Appendix B](https://arxiv.org/html/1701.06538v1):
  희소·계층 gate와 사용 편중 문제의 근거. 이번 MLP reward gate를 논문의 FFN-MoE와 동일시하지 않는다.
- [NeuralUCB, ICML 2020](https://proceedings.mlr.press/v119/zhou20a/zhou20a.pdf):
  비선형 reward 표현과 탐험을 구분하는 비교. 해당 UCB 알고리즘·regret 보증은 구현하지 않았다.
- [SQLite isolation](https://sqlite.org/isolation.html): snapshot·writer 경계 검토.
  기존 file journal을 유지했으며 NFS에 WAL을 추가하지 않았다.
- [GraphRAG DRIFT](https://microsoft.github.io/graphrag/query/drift_search/):
  지역·전역 후속 탐색 비교. 여기의 명시적 ID/section 경로는 DRIFT 구현이 아니다.
- [vLLM Tokenize API](https://docs.vllm.ai/en/stable/serving/openai_compatible_server/):
  chat template를 적용한 실제 토큰 예산 검사에 사용했다.
- [Hyperon experimental v0.2.10 고정 commit](https://github.com/trueagi-io/hyperon-experimental/tree/3f76dc460da6961f57f69f6c3e550c59c74ada83):
  구조·해석·지속 상태 비교 대상. 소스 비교이며 이번 구성요소 성능을 실행 비교하지 않았다.
