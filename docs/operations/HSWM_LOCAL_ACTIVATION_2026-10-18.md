# HSWM 문맥별 국지 활성화와 온라인 학습

사용자 방향은 [국지 활성화 정전 원문](../canon/USER_PRIMARY_HSWM_LOCAL_ACTIVATION_INTELLIGENCE_2026-10-18.md)이다.
국지 활성화를 지능의 구성 원리로 다룬다는 사용자 요구와, 그 보편적 과학적 증명 여부는 구분한다.
이번 구현은 **문맥 → 규칙 묶음 활성화 → 실제 실행 → 관측 보상 → 그래프 정책 revision → 다음 문맥의 선택**을 연결한다.

## 구현 계약

`semantic-context-activation-domain.ts`는 disjoint LinUCB를 구현한다. 각 후보 묶음에
ridge 행렬 A와 보상 벡터 b를 두고, θ = A⁻¹b를 Cholesky solve로 계산한다.
EXPLORE는 θ·x + α√(x·A⁻¹x), EXPLOIT는 θ·x로 선택한다. 실행한 후보만
A ← A + xxᵀ, b ← b + rx로 갱신한다. 미실행 후보의 결과는 만들지 않는다.
동점은 선언된 후보 순서로 결정하며, 점수와 불확실성 반경은 성공 확률이 아니다.

후보는 하나 이상의 역할 있는 하이퍼관계 묶음이다. 선택한 한 묶음과 필수 관계의 전체
역할·원문·예외가 LLM의 국소 입력을 구성한다. 필수 관계는 gating으로 제거하지 않는다.
부분 원문으로 예산을 맞추지 않으며, 완전한 문맥이 예산을 넘으면 실행을 거부한다.
비선택 묶음은 모델 입력에 포함하지 않는다. 저장소 복구나 계획 수립의 전체 I/O가
항상 국소적이라는 주장은 아니다.

특성은 버전이 명시된 caller encoder가 전달한다. 최대 16차원, 각 값 [-1,1], 비영 벡터다.
누락된 특성을 0으로 채우지 않는다. 같은 규칙 revision·역할·후보·필수 보존 범위 안에서는
event가 달라져도 같은 정책을 사용한다. 규칙이나 역할이 바뀌면 재결속이 필요하다.
현재 알고리즘은 희소 활성화의 첫 구현이다. 신경망 MoE의 공동 역전파 학습,
자연어 encoder 학습, 관계 생성·삭제, 조합 내부 기여도 분해를 구현한 것은 아니다.

## 그래프 저장과 결과 결속

학습 상태는 기존 `semantic_context_policy` atom의 새 media type
`application/vnd.hswm.context-activation-policy-v1+json`에 저장한다. 후보 관계는 기존
`hswm:context-policy:scope` / `candidate-root`, 후속 revision은 기존 supersedes로 연결한다.
기존 static policy 계약을 재해석하지 않는다. 역할·순서와 source key/content hash는 그대로 남는다.
TS는 해석기이며, 학습마다 TS를 수정하지 않는다. 기반 LLM 가중치도 바꾸지 않는다.

학습 API는 저장된 실행 trace·요청·실제 응답을 다시 읽고 현재 정책의 선택/조립과 대조한다.
event, 특성, policy revision, 선택, response 내용 중 하나라도 어긋나면 거부한다.
같은 trace를 successor에 다시 학습시키는 중복·stale feedback도 거부한다.
보상은 [0,1]의 명시적 관측과 출처가 필요하다. 자기 확신도는 보상이 아니다.
출처의 진실성과 evaluator의 독립성은 자동 인증되지 않으며, caller-declared로 기록한다.

초기화와 학습은 제안만 만든다. 기존 owner writer가 schema, owner, authorization,
expected revision, read/write set과 content envelope를 검사해 admit한 뒤에만 선택이 바뀐다.
아래 실험의 isolated owner schema 승인은 운영 DNRD5/GE-2 권한을 대신하지 않는다.
동시에 진행한 오래된 실행의 feedback은 최신 revision에 자동 합치지 않는다.

기존 durable RDF 1.1 N-Quads projection을 그대로 사용한다. 정책 atom의 type, source,
owner, revision, typed reference와 ordinal은 투영되며 A/b 숫자 자체는 content hash를 따라
원본 JSON에서 읽는다. 별도의 표준이나 KG predicate를 새로 만들지 않았다.

## 사용

Effect runtime을 build한 다음 `src/hswm/effect-runtime/bin/hswm-activation --help`를 사용한다.
한 요청을 stdin JSON으로 전달한다. 계약은 `hswm-context-activation-cli/v1`이다.
공통 입력은 `durableRoot`, `journalLineageId`, 전체 native `schema`, 기존 context `spec`이다.

1. `prepare`: 현재 plan을 읽는다.
2. `initialize`: plan hash, encoder/config, owner target으로 초기 정책 제안을 만든다. owner가 admit한다.
3. `prepare` 후 `select`/`assemble`/`execute`: 정확한 policy key, event hash, features, EXPLORE/EXPLOIT로 선택한다.
4. `learn`: 동일 실행 plan과 trace descriptor, 실제 reward/observed/source, successor target으로 제안한다.
5. owner admission 이후 새 process에서 다시 `prepare`/`execute`한다.

최대 8개 후보와 16개 특성, 후보별 최대 100만 관측을 지원한다. α는 [0,10]이며 자동 조정하지 않는다.
EXPLOIT도 동점/미학습 상태에서는 첫 후보를 고른다. 안전한 기권이나 OOD 검출기는 별도로 필요하다.
누적 ridge 학습이므로 과거 기억을 유지하지만, 분포 변화의 망각/적응 속도 보장은 없다.
정책이 결정적이므로 기존 HSWM_LIKENESS 고정 무작위 IPS 평가기에 이 adaptive stream을 넣지 않는다.

## 사전 고정 비교와 검증

`_research/local_activation_v1/run.mjs --help`는 새 private 출력 디렉터리, cell, 현재 범위의
등록 정보를 요구한다. authored Boolean 규칙 identity/complement와 signal 특성만 사용한다.
완료한 v3는 초기 동일 정책 holdout 8회 → online train 8회 → 동일 holdout 8회 → 별도
OS process 2회, 총 26회다. train 신호는 ±1, holdout은 ±0.7/±0.4, 재시작은 ±0.9다.
정답은 신호 부호에 따른 Boolean 결과이며 실제 모델 prediction을 정확히 비교한다.
holdout은 학습에 사용하지 않고 평가 기준·α·후보·횟수를 결과에 따라 변경하지 않는다.
독립 자연 과제, 분포 이동, 전체 HSWM 지능이나 OpenCog Hyperon 대비 우월성 실험이 아니다.
Hyperon 구성요소 실행 비교는 이번 범위에서 수행하지 않는다.

검증: TypeScript 검사, Effect 경계/함수형 검사, build 통과. 새 activation 검사 3개와
기존 policy 검사 5개, 총 8개를 통과했다. 초기 30초 통합 검사 제한은 저장소 재개를 포함한
35.3초 실행을 수용하지 못해 120초로 늘렸으며, 같은 12개 갱신과 assertion을 유지했다.
공용 실행 한도에서 대기한 후 2026-10-18 실제 모델 비교를 완료했다.

| 실측 | 결과 |
|---|---|
| Qwen3-4B 학습 전 → 후 holdout | **4/8 → 4/8, 개선 0%p** |
| online train 실제 응답 | 4/8 |
| 별도 OS process의 revision 8 실행 | 1/2; 정확도와 저장 상태 재사용 성공은 구분 |
| 학습 상태 | policy revision 0 → 8; canonical state revision 10 |
| 규칙 본문·역할 | 변경 없음; 필수 관계와 선택한 관계만 모델 입력에 전달 |
| 원본 응답/산술 재검사 | 26개 응답 대조, A/b 독립 재계산, 요청과 완전한 역할 조립 일치 |
| 표준 그래프 | 기존 durable RDF 재검증 및 N-Quads parse: 591 quads, 4 named graphs |

실행에서는 complement를 선택한 3회 모두 모델이 입력 bit를 그대로 반환했다.
예를 들어 bit=0에 반전 규칙이 전달됐지만 prediction=0이었다. 해당 모델 실행으로는
반전 규칙의 기대 효용을 얻지 못했고, 최종 EXPLOIT 선택도 두 문맥 모두 identity였다.
이는 **실행 기록의 관측**이다. prompt 표현, 모델 크기, 추론 설정 중 무엇이 원인인지는
별도 통제 비교를 하지 않아 확정하지 않는다. α를 바꾸거나 holdout 결과로 정책을 수정하지 않았다.
숫자 가중치 학습·저장·재사용은 구현됐지만, 이번 실제 모델의 성능 개선은 입증되지 않았다.

초기 v1은 2회째 응답이 1,024 token 한도에 도달해 content=null로 중단했다.
v2는 1회 응답이 Markdown fence를 포함해 엄격한 JSON 계약에서 중단했다. 둘 다 학습 전이다.
원본과 실패 상태를 보존하고, v3는 기존 owner vLLM의 구조화 JSON/비추론 설정을 모든
단계에 동일 적용했다. 원본 예측은 수정하지 않았다. 새 holdout 수치와 8 train을 사전 고정해
초기 30회 예산 안에서 총 **29회, 50,265 provider 보고 토큰**을 사용했다. 완료 v3는
26회·43,296토큰이다. 단일 seed 17, 모델 가중치 revision은 미인증이다.

재검사: `node _research/local_activation_v1/check.mjs COMPLETED_V3_DIRECTORY`.
원본은 ignored `.hswm-local/local-activation-2026-10-18/`이며
`_research/local_activation_v1/evidence-lock.json`은 원본 bytes와 당시 소스의 hash만 묶는다.
모델 출력 형식 수리를 성능 개선으로 계산하지 않는다. 다음 유효 비교는 선택된 규칙을
국소 모델이 정확히 실행하는 조건을 먼저 확인하고, 새 보류 입력으로 측정해야 한다.

## 근거

- [Li et al., 2010, Algorithm 1](https://www.schapire.net/papers/www10.pdf): disjoint LinUCB의 ridge 통계·상한 선택·선택 arm 갱신을 적용했다. 논문의 regret 가정이나 수치를 HSWM에 전용하지 않는다.
- [Shazeer et al., 2017](https://arxiv.org/html/1701.06538v1): 입력별 일부 expert 활성화라는 비교 근거다. 이 구현은 해당 논문의 neural MoE 재현이 아니다.
- [Qwen3 공식 안내](https://qwenlm.github.io/blog/qwen3/): thinking/non-thinking 전환의 출처다. v2의 soft switch만으로 JSON 형식까지 보장되지는 않았다.

새 외부 runtime dependency나 외부 코드 복사는 없다. 기존 Effect 3.22.1과 native graph 저장/투영을 재사용한다.
